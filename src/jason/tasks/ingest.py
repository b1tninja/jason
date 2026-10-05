"""``jason ingest SOURCE``: take a box of documents into the library as one step of onboarding.

A source is a local folder, a zip, a Drive folder (by link or ``drive:ID``; read-only), or a list of files. The chain:

1. **Inventory.** Every file, with its sha256, type, size, where it came from, and the dates it carries: the file's own
   times, a PDF's metadata, a zip entry's time, Drive's last change, and a date in its name (later, a date its words
   print). Files with the same hash are one file (``duplicate_of``); a hash the library already holds is noted
   (``library_path``) and not taken in again.
2. **Extract and classify.** The library's readers (``jason.tasks.library.text_of``): a text layer first, OCR when it is
   empty. The library's chain: a person's earlier answer, the profile's kind rules by name and folder, the phrase rules
   over the text, then the local model, only when one is given (``ModelClassifier`` runs preflight and holds the GPU
   lock). A miss, or a model's answer below ``LOW_CONFIDENCE``, is a ``CLASSIFY`` question with its evidence.
3. **Version.** A file that holds at least ``VERSION_MIN`` of a known document's current text (the revision detector's
   test, by shared letter runs) is a version of it: the current text, a version on record, or one not on record. A new
   version of a living or citable document is reported, never applied. A file whose own words are mostly something
   else (a packet carrying the document, ``OWN_MIN``) is a copy, not a version. Files no known document claims are grouped with
   each other the same way (living kinds only: monthly statements share boilerplate, not a text).
4. **File.** Where each file goes: its book (``Community.book_entries`` for a known document, else the kind's book), its
   Civil Code 5200 records, and its library folder (where the library files that kind, preferring a folder pinned to
   its record). A classified file with no folder is a ``MAP`` question. ``apply`` copies the files that have both into
   ``data/library/files`` and records them in ``library.db`` (``documents`` and ``ingested``) with hash, provenance, and
   classification. Nothing goes to Drive or PayHOA.
5. **Report.** ``data/onboarding/ingest-<day>.md`` and ``.json`` (private: they name the files): counts by kind, book,
   and record; duplicates; versions; the questions (parked only with ``park``); and the onboarding checklist items and
   stage gates that moved, the checklist run before and after (after: as if the files were filed and the questions
   parked).

``gate`` reads the last report for the onboarding session's "ingest" stage. Staged copies (zip members, Drive
downloads) and the text read from each file are kept under ``data/onboarding/ingest/`` so a second run reads nothing
twice.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
import sqlite3
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from jason.community.intake import Ask, AskKind, AskStatus, ask_id

FOLDER = "onboarding"
WORK = "onboarding/ingest"                   # staged copies and text read, by hash
REPORT_PREFIX = "ingest-"
LOW_CONFIDENCE = 0.7                         # a model's answer below this is asked, even when taken
MODEL_FLOOR = 0.5                            # ... and below this is not taken (as ``jason library``)
GROUP_MIN = 0.5                              # shared runs (Dice) that make two unknown files versions of one text
OWN_MIN = 0.5                                # a version's own words are mostly the document's; less is a packet that
                                             # carries a copy of it
VERSION_STATUSES = frozenset({"current", "on record", "not on record", "excerpt"})
HEAD_WORDS = 40                              # the first words shown with a question
CHOICES = 6
SKIP_NAMES = frozenset({"thumbs.db", "desktop.ini", ".ds_store"})
LOCK = "intake-asks"


# --- The inventory ----------------------------------------------------------------------------------------------------

@dataclass
class FileItem:
    source: str                              # folder, zip, drive, file
    origin: str                              # where it came from: a path, "<zip>!<member>", "drive:<id>"
    rel: str                                 # its path under the source, the source's own name first
    local: Path                              # the bytes on disk: the original, or a staged copy
    sha256: str
    size: int
    type: str
    dates: list[tuple[str, str]] = field(default_factory=list)      # (YYYY-MM-DD, what the date is)
    duplicate_of: str = ""                   # the first file in this run with the same bytes
    library_path: str = ""                   # the library already holds these bytes, here
    library_id: str = ""
    text_source: str = ""
    text_chars: int = 0
    kind: str = ""
    method: str = ""                         # ``library.Method`` name
    evidence: str = ""
    confidence: float | None = None
    period: str = ""
    records: tuple[str, ...] = ()
    category: str = ""
    confidential: bool = False
    candidates: tuple[str, ...] = ()
    version: dict[str, Any] = field(default_factory=dict)
    book: str = ""
    book_how: str = ""
    folder: str = ""
    folder_how: str = ""
    target: str = ""                         # the library path it is filed at
    questions: list[str] = field(default_factory=list)
    filed: bool = False
    analysis: dict[str, Any] = field(default_factory=dict)       # the preliminary kind analysis (``kind_analysis``)
    readings: dict[str, dict[str, Any]] = field(default_factory=dict)   # each kind reader's summary, by reader key

    @property
    def terms(self) -> dict[str, Any]:
        """The contract-terms reader's summary, when the file is an agreement."""
        return self.readings.get("contract-terms", {})

    @property
    def key(self) -> str:
        return self.sha256[:16]

    @property
    def subject(self) -> str:
        return f"ingest:{self.key}"

    @property
    def name(self) -> str:
        return self.rel.rsplit("/", 1)[-1]

    @property
    def library_doc_id(self) -> str:
        return f"ingest-{self.key}"

    @property
    def status(self) -> str:
        if self.duplicate_of:
            return "duplicate"
        if self.library_path:
            return "in the library"
        if self.filed:
            return "filed"
        if not self.kind:
            return "held: no kind"
        if not self.folder:
            return "held: no folder"
        if self.questions:
            return "held: a question is open"
        return "ready"

    def row(self) -> dict[str, Any]:
        return {"rel": self.rel, "source": self.source, "origin": self.origin, "sha256": self.sha256, "size": self.size,
                "type": self.type, "dates": [list(d) for d in self.dates], "duplicateOf": self.duplicate_of,
                "libraryPath": self.library_path, "text": {"source": self.text_source, "chars": self.text_chars},
                "kind": self.kind, "method": self.method, "evidence": self.evidence, "confidence": self.confidence,
                "period": self.period, "records": list(self.records), "category": self.category,
                "confidential": self.confidential, "version": self.version, "book": self.book, "bookHow": self.book_how,
                "folder": self.folder, "folderHow": self.folder_how, "target": self.target,
                "questions": list(self.questions), "status": self.status, "analysis": dict(self.analysis),
                "readings": {k: dict(v) for k, v in self.readings.items()}}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def drive_folder_id(source: str) -> str:
    """The Drive folder id a source names ("drive:ID", a folder link, an ``?id=`` link), or ""."""
    if source.startswith("drive:"):
        return source[len("drive:"):].strip()
    if "drive.google.com" in source or "docs.google.com" in source:
        m = re.search(r"/folders/([A-Za-z0-9_-]{10,})", source) or re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", source)
        return m.group(1) if m else ""
    return ""


def _type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or (path.suffix.lower().lstrip(".") or "unknown")


def _pdf_date(value: str) -> str:
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})", value or "")
    if not m:
        return ""
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return ""


def file_dates(path: Path, name: str, *, own_times: bool = True) -> list[tuple[str, str]]:
    """The dates a file carries: its own times (not for a staged copy), a PDF's metadata, and a date in its name."""
    from jason.community.library import period_of
    from jason.community.revision_detection import name_dates

    out: list[tuple[str, str]] = []
    if own_times:
        st = path.stat()
        out.append((datetime.fromtimestamp(st.st_mtime).date().isoformat(), "file modified"))
        born = getattr(st, "st_birthtime", None) or (st.st_ctime if sys.platform == "win32" else None)
        if born:
            out.append((datetime.fromtimestamp(born).date().isoformat(), "file created"))
    if path.suffix.lower() == ".pdf":
        try:
            import pymupdf

            with pymupdf.open(str(path)) as doc:
                meta = doc.metadata or {}
            for key, how in (("creationDate", "PDF created"), ("modDate", "PDF modified")):
                d = _pdf_date(str(meta.get(key) or ""))
                if d:
                    out.append((d, how))
        except Exception:  # noqa: BLE001 - an unreadable PDF carries no metadata date
            pass
    found = [d.isoformat() for d in name_dates(name)]
    out += [(d, "printed in the file's name") for d in found]
    if not found:
        period = period_of(name)
        if period:
            out.append((period, "a period in the file's name"))
    return sorted(set(out))


def _skip(path: Path) -> bool:
    name = path.name
    if name.casefold() in SKIP_NAMES or name.startswith((".", "~$")):
        return True
    # An extract beside its file ("x.pdf.md") is read with the file, not taken in on its own.
    return name.lower().endswith(".md") and path.with_name(name[:-3]).is_file()


def _stage_zip(path: Path, data_dir: Path, notes: list[str]) -> list[FileItem]:
    sha = sha256_of(path)
    stage = Path(data_dir) / WORK / "staging" / f"zip-{sha[:12]}"
    out: list[FileItem] = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            member = info.filename.replace("\\", "/")
            if info.is_dir() or member.startswith("__MACOSX/"):
                continue
            parts = [p for p in member.split("/") if p not in ("", ".")]
            if not parts or ".." in parts:
                notes.append(f"{path.name}!{member}: not read (a path outside the archive)")
                continue
            dest = stage.joinpath(*parts)
            if _skip(dest):
                continue
            if not dest.is_file() or dest.stat().st_size != info.file_size:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(archive.read(info))
            dates = file_dates(dest, parts[-1], own_times=False)
            try:
                dates.append((date(*info.date_time[:3]).isoformat(), "zip entry time"))
            except ValueError:
                pass
            out.append(FileItem("zip", f"{path}!{member}", f"{path.stem}/{'/'.join(parts)}", dest, sha256_of(dest),
                                info.file_size, _type(dest), sorted(set(dates))))
    return out


def _stage_drive(drive: Any, folder_id: str, data_dir: Path, notes: list[str]) -> list[FileItem]:
    """Every file under a Drive folder, downloaded (a Google Doc exported as Word) into the staging folder. Reads only."""
    from jason.google.drive import DOCX_MIME_TYPE, FOLDER_MIME_TYPE, GOOGLE_DOC_MIME_TYPE

    root = drive.get_file(folder_id)
    top = str(root.get("name") or folder_id)
    stage = Path(data_dir) / WORK / "staging" / f"drive-{folder_id}"
    out: list[FileItem] = []
    pending: list[tuple[str, list[str]]] = [(folder_id, [top])]
    while pending:
        fid, parts = pending.pop(0)
        for f in sorted(drive.list_folder(fid), key=lambda r: str(r.get("name") or "")):
            name = str(f.get("name") or f.get("id"))
            mime = str(f.get("mimeType") or "")
            if mime == FOLDER_MIME_TYPE:
                pending.append((str(f["id"]), parts + [name]))
                continue
            if mime == GOOGLE_DOC_MIME_TYPE:
                name = name if name.lower().endswith(".docx") else name + ".docx"
            elif mime.startswith("application/vnd.google-apps."):
                notes.append(f"{'/'.join(parts + [name])}: a {mime.rsplit('.', 1)[-1]} is not taken in (no file to read)")
                continue
            dest = stage.joinpath(*parts[1:], re.sub(r'[<>:"/\\|?*]', "_", name))
            if not dest.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    if mime == GOOGLE_DOC_MIME_TYPE:
                        dest.write_bytes(drive.export_bytes(str(f["id"]), DOCX_MIME_TYPE))
                    else:
                        drive.download(str(f["id"]), dest)
                except Exception as exc:  # noqa: BLE001 - one file Drive will not give is a note, not a stop
                    notes.append(f"{'/'.join(parts + [name])}: not downloaded: {exc}")
                    continue
            dates = file_dates(dest, name, own_times=False)
            if f.get("modifiedTime"):
                dates.append((str(f["modifiedTime"])[:10], "Drive modified"))
            out.append(FileItem("drive", f"drive:{f['id']}", "/".join(parts + [name]), dest, sha256_of(dest),
                                dest.stat().st_size, mime or _type(dest), sorted(set(dates))))
    return out


def inventory(sources: Iterable[str | Path], data_dir: Path, *, drive: Any = None) -> tuple[list[FileItem], list[str]]:
    """Every file the sources hold, hashed and dated, with duplicates and the library's own copies marked."""
    notes: list[str] = []
    items: list[FileItem] = []
    for source in sources:
        text = str(source)
        folder_id = drive_folder_id(text)
        if folder_id:
            if drive is None:
                raise ValueError(f"{text} is a Drive folder: a Drive client is needed to read it")
            items += _stage_drive(drive, folder_id, data_dir, notes)
            continue
        path = Path(text)
        if path.is_dir():
            for p in sorted(path.rglob("*"), key=lambda x: x.as_posix().casefold()):
                if p.is_file() and not _skip(p):
                    rel = f"{path.name}/{p.relative_to(path).as_posix()}"
                    items.append(FileItem("folder", str(p), rel, p, sha256_of(p), p.stat().st_size, _type(p),
                                          file_dates(p, p.name)))
        elif path.is_file() and path.suffix.lower() == ".zip":
            items += _stage_zip(path, data_dir, notes)
        elif path.is_file():
            items.append(FileItem("file", str(path), path.name, path, sha256_of(path), path.stat().st_size, _type(path),
                                  file_dates(path, path.name)))
        else:
            notes.append(f"{text}: not found")
    first: dict[str, FileItem] = {}
    held = library_hashes(data_dir)
    for item in items:
        seen = first.get(item.sha256)
        if seen is not None:
            item.duplicate_of = seen.rel
            continue
        first[item.sha256] = item
        if item.sha256 in held:
            item.library_id, item.library_path = held[item.sha256]
    return items, notes


def library_hashes(data_dir: Path) -> dict[str, tuple[str, str]]:
    """The library's files by sha256: (id, library path)."""
    db = Path(data_dir) / "library" / "library.db"
    if not db.is_file():
        return {}
    out: dict[str, tuple[str, str]] = {}
    with sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True) as conn:
        for doc_id, path, sha in conn.execute("SELECT id, path, sha256 FROM documents WHERE sha256 != ''"):
            out.setdefault(str(sha), (str(doc_id), str(path)))
    return out


# --- Text -------------------------------------------------------------------------------------------------------------

def read_text(item: FileItem, data_dir: Path, *, ocr: bool = True) -> str:
    """The file's words: the library's cached text for a file it holds, else the library's readers (a text layer, then
    OCR when it is empty), kept by hash under ``data/onboarding/ingest/text``."""
    from jason.tasks import library as library_task

    if item.library_id:
        text = library_task.text_for(Path(data_dir), item.library_id)
        if text.strip():
            item.text_source, item.text_chars = "the library's text", len(text)
            return text
    cache = Path(data_dir) / WORK / "text" / f"{item.sha256}.txt"
    note = cache.with_suffix(".json")
    if cache.is_file() and note.is_file():
        text = cache.read_text(encoding="utf-8", errors="ignore")
        try:
            item.text_source = str(json.loads(note.read_text(encoding="utf-8")).get("source") or "")
        except (OSError, ValueError):
            item.text_source = "cached"
        item.text_chars = len(text)
        return text
    if ocr:
        text, source = library_task.text_of(item.local)
    else:
        text, source = _without_ocr(item.local)
    item.text_source, item.text_chars = source, len(text)
    if text.strip() or ocr:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text, encoding="utf-8")
        note.write_text(json.dumps({"file": item.rel, "source": source, "chars": len(text)}), encoding="utf-8")
    return text


def _without_ocr(path: Path) -> tuple[str, str]:
    from jason.tasks import library as library_task

    suffix = path.suffix.lower()
    if suffix in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
        return "", "image; OCR skipped (--no-ocr)"
    if suffix == ".pdf" and not path.with_name(path.name + ".md").is_file():
        layer = library_task._pdf_layer(path)
        if len(layer.strip()) < 200:
            return layer, "image-only; OCR skipped (--no-ocr)"
    return library_task.text_of(path)


def head_of(text: str, words: int = HEAD_WORDS) -> str:
    return " ".join(text.split()[:words])


# --- Classification ---------------------------------------------------------------------------------------------------

def classify(community: Any, item: FileItem, text: str, *, model: Any = None, chosen: dict[str, dict] | None = None,
             state: dict[str, Any] | None = None) -> Any:
    """The library's chain over one file: a person's answer, the kind rules, the phrase rules, then the model (only
    when given); then the record refinements, the confidential check, and a period from the text. Returns the
    ``Classified`` row and, when the model was asked, its answer."""
    from jason.community.content import (ModelUnavailable, classify_text, period_from_text, private_content,
                                         records_from_text)
    from jason.community.library import LibraryDocument, Method, classify_by_name
    from jason.community.symbols import DocumentKind

    state = state if state is not None else {}
    folder = item.rel.rsplit("/", 1)[0] + "/" if "/" in item.rel else ""
    doc = LibraryDocument("ingest", item.library_doc_id, item.rel, item.name, folder, item.size)
    row = classify_by_name(community, doc)
    pick = (chosen or {}).get(item.subject)
    if pick:
        try:
            row = replace(row, kind=DocumentKind(pick["kind"]), method=Method.PERSON, confidence=1.0,
                          evidence=f"chosen by {pick.get('by', '?')} on {pick.get('on', '?')}")
        except ValueError:
            pass
    answer = None
    if row.kind is None and text.strip():
        kind, evidence = classify_text(text)
        if kind is not None:
            row = replace(row, kind=kind, method=Method.CONTENT, evidence=evidence)
        elif model is not None and state.get("model", True):
            try:
                answer = model.classify(item.name, text)
            except ModelUnavailable as exc:
                state["model"] = False
                state.setdefault("notes", []).append(f"the model is not read: {exc}")
            if answer is not None and answer.kind is not None and answer.confidence >= MODEL_FLOOR:
                row = replace(row, kind=answer.kind, method=Method.MODEL, evidence=f"model: {answer.reason}",
                              confidence=answer.confidence, period=row.period or answer.period)
    if text.strip():
        extras = records_from_text(row.kind, text)
        if extras:
            row = replace(row, extra_records=tuple(r for r, _ in extras),
                          evidence=(row.evidence + "; " if row.evidence else "") + "; ".join(w for _, w in extras))
        private = private_content(row.kind, text)
        if private:
            row = replace(row, private=private,
                          evidence=(row.evidence + "; " if row.evidence else "") + "confidential: " + private)
        if not row.period:
            found = period_from_text(text)
            if found:
                row = replace(row, period=found)
    return row, answer


def _take(item: FileItem, row: Any) -> None:
    item.kind = row.kind.value if row.kind else ""
    item.method = row.method.name
    item.evidence = row.evidence
    item.confidence = row.confidence
    item.period = row.period
    item.records = tuple(r.value for r in row.records)
    item.category = row.category.value if row.category else ""
    item.confidential = row.confidential


def _from_library(item: FileItem, rows: dict[str, dict[str, Any]]) -> None:
    """A file the library holds keeps the library's classification (``rows``: the library's rows by id)."""
    r = rows.get(item.library_id)
    if r is None:
        return
    item.kind, item.method, item.evidence = str(r.get("kind") or ""), str(r.get("method") or ""), str(r.get("evidence") or "")
    item.confidence, item.period = r.get("confidence"), str(r.get("period") or "")
    item.records, item.category = tuple(r.get("records") or ()), str(r.get("category") or "")
    item.confidential = bool(r.get("confidential"))


def needs_kind(item: FileItem) -> bool:
    """A miss, a model's answer too weak to file on its own word, or a kind the analysis of the text disagrees with
    (``kind_analysis``: another kind reads better, or an agreement the association is not a party to)."""
    return (not item.kind or (item.method == "MODEL" and (item.confidence or 0) < LOW_CONFIDENCE)
            or item.analysis.get("verdict") in ("disagrees", "weak"))


# --- Versions ---------------------------------------------------------------------------------------------------------

def _runs(text: str) -> frozenset[str]:
    from jason.community.embedded_copies import stream
    from jason.community.revision_detection import SHINGLE, clean

    s = stream(clean(text))
    return frozenset(s[j:j + SHINGLE] for j in range(max(0, len(s) - SHINGLE + 1)))


@dataclass
class Known:
    key: str
    title: str
    kind: str
    living: bool
    citable: bool
    runs: frozenset[str]
    current_hash: str                        # text_hash of the current text
    current_id: str = ""                     # the stored history's current version
    hashes: dict[str, str] = field(default_factory=dict)       # text_hash[:16] -> version id
    files: dict[str, str] = field(default_factory=dict)        # a version file's sha256 -> version id
    on: dict[str, str] = field(default_factory=dict)           # version id -> its date


def known_documents(community: Any, data_dir: Path) -> list[Known]:
    """The documents jason compares versions of, each with its current text: the stored history's current version
    (``jason revisions``), else the Doc's outline."""
    from jason.community.revision_detection import text_hash
    from jason.tasks import revision_detection as rd

    root = Path(data_dir)
    citable = {d.key: d for d in tuple(getattr(community, "citable_documents", lambda: ())() or ())}
    living = {ld.key: ld for ld in tuple(getattr(community, "living_documents", lambda: ())() or ())}
    out: list[Known] = []
    for key in dict.fromkeys(list(rd.keys(community)) + list(living)):
        stored = rd.load(root, key) or {}
        text, versions = "", stored.get("versions") or []
        current = next((v for v in versions if v.get("id") == stored.get("current")), None)
        for f in (current or {}).get("files") or ():
            cache = root / rd.TEXTS / f"{f.get('sha256')}.json"
            if cache.is_file():
                try:
                    text = str(json.loads(cache.read_text(encoding="utf-8")).get("text") or "")
                except (OSError, ValueError):
                    text = ""
            if text:
                break
        if not text:
            fallback = rd._outline_fallback(root, key)
            text = fallback.text if fallback is not None else ""
        if not text.strip():
            continue
        doc = citable.get(key) or living.get(key)
        k = Known(key, getattr(doc, "title", key), getattr(getattr(doc, "kind", None), "value", ""), key in living,
                  key in citable, _runs(text), text_hash(text), str(stored.get("current") or ""))
        for v in versions:
            k.hashes[str(v.get("hash") or "")[:16]] = str(v.get("id") or "")
            k.on[str(v.get("id") or "")] = str(v.get("on") or "")
            for f in v.get("files") or ():
                k.files[str(f.get("sha256") or "")] = str(v.get("id") or "")
        out.append(k)
    return out


def is_version(version: dict[str, Any]) -> bool:
    """A version of a known document or of a group of unknown files (not a copy carried inside another file)."""
    return bool(version.get("group")) or version.get("status") in VERSION_STATUSES


def _versioned(kind: str) -> bool:
    """Kinds whose files may be versions of one text: a living book's kinds and a policy (not a series: one month's
    statement is not a version of the last)."""
    from jason.community.books import default_book
    from jason.community.symbols import DocumentKind

    if not kind or kind == DocumentKind.POLICY.value:
        return True
    if kind in (DocumentKind.AMENDMENT.value, DocumentKind.ANNEXATION.value):
        return False
    book = default_book(kind)
    return book is not None and book.living


def _span(item: FileItem) -> dict[str, str]:
    """When the file's words existed by (the earliest date it carries) and the latest date its words claim."""
    existed = [(d, how) for d, how in item.dates if how != "printed in the text" and len(d) == 10]
    claims = [(d, how) for d, how in item.dates if how == "printed in the text"]
    out = {}
    if existed:
        d, how = min(existed)
        out.update(existedBy=d, existedHow=how)
    if claims:
        d, how = max(claims)
        out.update(claims=d)
    return out


def find_versions(items: list[FileItem], texts: dict[str, str], known: list[Known]) -> list[dict[str, Any]]:
    """Mark each file that is a version of a known document (``item.version``), and group the rest that share their
    words. Returns the groups of unknown versions (two or more texts)."""
    from jason.community.revision_detection import PARTIAL_BELOW, VERSION_MIN, contained, dice, text_hash
    from jason.tasks import revision_detection as rd

    runs: dict[str, frozenset[str]] = {}
    for item in items:
        text = texts.get(item.sha256, "")
        if item.duplicate_of or not text.strip():
            continue
        runs[item.sha256] = r = _runs(text)
        best, share = None, 0.0
        for k in known:
            s = contained(k.runs, r)
            if s > share:
                best, share = k, s
        if best is None or share < VERSION_MIN:
            continue
        own = contained(r, best.runs)            # the share of the file that is the document's text
        base = {"document": best.key, "title": best.title, "kind": best.kind, "living": best.living,
                "citable": best.citable, "share": round(share, 3), "own": round(own, 3), **_span(item)}
        if own < OWN_MIN:
            # A packet that carries the document (an annual disclosure with the collection policy inside): a copy
            # inside another file, not a version of it.
            item.version = {**base, "status": "carries a copy" if share >= PARTIAL_BELOW else "carries part"}
            continue
        version_id = best.files.get(item.sha256, "")
        how = "the same file as a version on record" if version_id else ""
        if not version_id:
            read = rd.read_file(item.local).get("text") or text
            h = text_hash(read)
            if h == best.current_hash:
                version_id, how = best.current_id or "current", "the current text's words"
            elif h[:16] in best.hashes:
                version_id, how = best.hashes[h[:16]], "the words of a version on record"
        if version_id and version_id in (best.current_id, "current"):
            status = "current"
        elif version_id:
            status = "on record"
        else:
            status = "excerpt" if share < PARTIAL_BELOW else "not on record"
        item.version = {**base, "status": status, "versionId": version_id, "how": how,
                        "versionOn": best.on.get(version_id, "")}
    # The files no known document claims, grouped by the words they share.
    loose = [i for i in items if i.sha256 in runs and not i.version and _versioned(i.kind)]
    parent = {i.sha256: i.sha256 for i in loose}

    def top(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a_i, a in enumerate(loose):
        for b in loose[a_i + 1:]:
            if dice(runs[a.sha256], runs[b.sha256]) >= GROUP_MIN:
                parent[top(b.sha256)] = top(a.sha256)
    groups: dict[str, list[FileItem]] = defaultdict(list)
    for i in loose:
        groups[top(i.sha256)].append(i)
    out = []
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda i: (_span(i).get("existedBy") or "9999", i.rel))
        texts_seen = {text_hash(texts[i.sha256]) for i in members}
        gid = f"group-{members[0].key[:8]}"
        for n, i in enumerate(members, 1):
            i.version = {"group": gid, "status": "a version of a text jason does not know", "order": n, **_span(i)}
        out.append({"group": gid, "files": [i.rel for i in members], "texts": len(texts_seen),
                    "dates": [_span(i) for i in members],
                    "kind": next((i.kind for i in members if i.kind), "")})
    return out


# --- Filing -----------------------------------------------------------------------------------------------------------

def propose(community: Any, items: list[FileItem], data_dir: Path, *, answered: dict[str, str] | None = None) -> None:
    """Each file's book, records, library folder, and library path."""
    from jason.community.books import Books, default_book
    from jason.tasks.library import load

    books = Books.of(community)
    folders = tuple(getattr(community, "library_folders", lambda: ())() or ())
    library = load(Path(data_dir))
    by_kind: dict[str, Counter] = defaultdict(Counter)
    for r in library:
        path = str(r.get("path") or "")
        if "/" not in path or not r.get("kind"):
            continue
        parent = path.rsplit("/", 1)[0] + "/"
        row = max((f for f in folders if parent.casefold().startswith(f.path.casefold())), key=lambda f: len(f.path),
                  default=None)
        by_kind[str(r["kind"])][row.path if row is not None else parent] += 1
    taken: set[str] = {str(r.get("path") or "").casefold() for r in library}
    files_dir = Path(data_dir) / "library" / "files"
    for item in items:
        if item.duplicate_of:
            continue
        document = str(item.version.get("document") or "") if is_version(item.version) else ""
        entry = books.entry(document) if document else None
        if entry is not None:
            item.book, item.book_how = entry.key, f"Community.book_entries maps {document}"
        elif item.kind:
            book = default_book(item.kind)
            if book is not None:
                item.book, item.book_how = book.value, f"the book of a {item.kind}"
                if book.restricted:
                    item.book_how += f" (restricted: {book.restricted})"
        if item.library_path:
            item.folder = item.library_path.rsplit("/", 1)[0] + "/" if "/" in item.library_path else ""
            item.folder_how, item.target = "the library already holds this file", item.library_path
            continue
        chosen = (answered or {}).get(item.subject, "")
        if chosen:
            item.folder, item.folder_how = (chosen if chosen.endswith("/") else chosen + "/"), "a person's answer"
        elif item.kind:
            pinned = [f.path for f in folders if set(r.value for r in f.records) & set(item.records)]
            counts = by_kind.get(item.kind) or Counter()
            if counts:
                best = max(counts, key=lambda p: (p in pinned, counts[p], -len(p)))
                item.folder = best
                item.folder_how = (f"where the library files {counts[best]} {item.kind} file"
                                   f"{'' if counts[best] == 1 else 's'}" + (", pinned to its record" if best in pinned else ""))
            elif pinned:
                item.folder, item.folder_how = pinned[0], f"the folder pinned to the {item.records[0]} record" \
                    if item.records else "a pinned folder"
        if not item.folder:
            continue
        target = item.folder + item.name
        if target.casefold() in taken or ((files_dir / target).is_file() and sha256_of(files_dir / target) != item.sha256):
            stem, dot, ext = item.name.rpartition(".")
            target = item.folder + (f"{stem} ({item.key[:8]}).{ext}" if dot else f"{item.name} ({item.key[:8]})")
        taken.add(target.casefold())
        item.target = target


# --- Questions --------------------------------------------------------------------------------------------------------

def questions(items: list[FileItem], texts: dict[str, str], community: Any, *, guesses: dict[str, Any]) -> list[Ask]:
    """A ``CLASSIFY`` for each file with no kind or a weak one; a ``MAP`` for each classified file with no folder."""
    from jason.community.books import Book
    from jason.community.symbols import AssociationRecord
    from jason.tasks.onboarding_session import _item_for

    folders = tuple(getattr(community, "library_folders", lambda: ())() or ())
    siblings: dict[str, Counter] = defaultdict(Counter)
    for i in items:
        if i.kind and not i.duplicate_of:
            siblings[i.rel.rsplit("/", 1)[0]][i.kind] += 1
    out: list[Ask] = []
    for item in items:
        if item.duplicate_of or item.library_path:
            continue
        text = texts.get(item.sha256, "")
        head = head_of(text)
        base = [f"file: {item.rel}", f"from: {item.origin}"]
        if needs_kind(item):
            candidates: list[str] = []
            guess = guesses.get(item.sha256)
            if item.kind:
                candidates.append(item.kind)
            if guess is not None and guess.kind is not None:
                candidates.append(guess.kind.value)
            if item.version.get("kind"):
                candidates.append(str(item.version["kind"]))
            analysed = [c["kind"] for c in item.analysis.get("candidates", [])[:3]]
            candidates += analysed
            candidates +=[k for k, _ in siblings[item.rel.rsplit("/", 1)[0]].most_common(3)]
            candidates = list(dict.fromkeys(c for c in candidates if c))[:CHOICES]
            evidence = base + [f"begins: {head}" if head else f"no text read ({item.text_source or 'no reader'})"]
            if guess is not None:
                evidence.append(f"model: {guess.kind.value if guess.kind else 'unknown'} at {guess.confidence:.2f}: "
                                f"{guess.reason}")
            disagrees = item.analysis.get("verdict") in ("disagrees", "weak")
            if item.kind and not disagrees:
                evidence.append(f"classified {item.kind} by {item.method} at {item.confidence or 0:.2f}, below "
                                f"{LOW_CONFIDENCE}")
            for c in item.analysis.get("candidates", [])[:3]:
                evidence.append(f"analysis: {c['kind']} {c['score']}: {'; '.join(c['reasons'][:4])}")
            evidence += [f"analysis: {n}" for n in item.analysis.get("notes", [])]
            if candidates:
                evidence.append("candidates: " + ", ".join(candidates))
            if item.version:
                evidence.append(f"shares its words with {item.version.get('document') or item.version.get('group')}")
            question = ("No rule classified this file with confidence. Which kind of document is it? (a DocumentKind "
                        "value; 'dismiss' to leave it out)")
            if disagrees:
                question = (f"The {item.method.lower()} rule calls this file {item.kind}, but its text "
                            f"{'reads otherwise' if item.analysis.get('verdict') == 'disagrees' else 'barely supports it'}"
                            " (see the analysis). Which kind of document is it? (a DocumentKind value; 'dismiss' to "
                            "leave it out)")
            verdict = item.analysis.get("verdict")
            if verdict == "disagrees" or (verdict in ("proposed", "weak") and item.analysis.get("suggestion")):
                suggestion = str(item.analysis.get("suggestion") or "")
            else:
                suggestion = candidates[0] if item.kind or (guess is not None and guess.kind is not None) else ""
            a = Ask(ask_id(AskKind.CLASSIFY, item.subject, ""), AskKind.CLASSIFY, item.subject,
                    question,
                    choices=tuple(candidates) + ("another kind (type its value)",),
                    suggestion=suggestion,
                    evidence=tuple(evidence), serves="",
                    detail={"path": item.subject, "file": item.rel, "sha256": item.sha256, "ingest": True})
            out.append(a)
            item.questions.append(a.id)
        if item.kind and not item.folder:
            from jason.community.onboarding import Record

            record = next((AssociationRecord(r) for r in item.records), None)
            serves = _item_for(Record, record) if record is not None else ""
            book = next((b for b in Book if b.value == item.book.split(".")[0]), None) if item.book else None
            pinned = [f.path for f in folders if set(r.value for r in f.records) & set(item.records)]
            choices = tuple(dict.fromkeys(pinned + [f.path for f in folders]))[:CHOICES]
            evidence = base + [f"kind: {item.kind} ({item.method}{': ' + item.evidence[:120] if item.evidence else ''})",
                               f"records: {', '.join(item.records) or 'none'}",
                               f"book: {item.book or 'none'}" + (f" ({book.info.title})" if book else ""),
                               f"the library holds no {item.kind} file, and no folder is pinned to its record"]
            if head:
                evidence.append(f"begins: {head}")
            a = Ask(ask_id(AskKind.MAP, item.subject, ""), AskKind.MAP, item.subject,
                    f"No library folder holds a {item.kind.replace('_', ' ')}. Which folder does this file go in? "
                    f"The answer files it on the next run, and becomes a proposed profile change (a folder for the "
                    f"kind), for a person to apply.",
                    choices=choices + ("not kept in the library: dismiss",), evidence=tuple(evidence), serves=serves,
                    detail={"map": "folder", "method": "library_folders", "kind": item.kind, "file": item.rel,
                            "sha256": item.sha256, "records": list(item.records), "item": serves})
            out.append(a)
            item.questions.append(a.id)
    return out


def answered_folders(asks: Iterable[Ask]) -> dict[str, str]:
    """A person's folder for a file, from an answered MAP question about it."""
    return {a.subject: a.answer.strip() for a in asks
            if a.kind is AskKind.MAP and a.subject.startswith("ingest:") and a.answer.strip()
            and a.status in (AskStatus.ANSWERED, AskStatus.APPLIED) and a.answer.strip().lower() not in ("dismiss",)
            and not a.answer.lower().startswith("not kept")}


# --- The checklist before and after -----------------------------------------------------------------------------------

def _library_row(item: FileItem, now: str) -> dict[str, Any]:
    return {"id": item.library_doc_id, "source": "ingest", "path": item.target, "name": item.name, "kind": item.kind,
            "category": item.category, "records": list(item.records), "method": item.method, "period": item.period,
            "confidential": item.confidential, "evidence": item.evidence, "confidence": item.confidence,
            "classified_at": now, "sha256": item.sha256}


def contexts(community: Any, data_dir: Path, *, rows: list[dict[str, Any]], asks: tuple, settings: Any = None,
             after_asks: tuple | None = None) -> tuple[Any, Any]:
    """The checklist's context now, and with ``rows`` added to the library and ``after_asks`` as the queue."""
    from jason.community.onboarding import Context
    from jason.community.private import facts
    from jason.tasks.library import distinct, load as load_library
    from jason.tasks.onboarding import counter

    root = Path(data_dir)
    try:
        raw = list(load_library(root))
    except Exception:  # noqa: BLE001 - no library yet
        raw = []
    governing = None
    if (root / "index-cache.db").is_file():
        try:
            from jason.tasks.property_history import load_association_record

            governing = load_association_record(community, root).governing
        except Exception:  # noqa: BLE001
            governing = None

    def holdings(library: tuple) -> tuple:
        try:
            from jason.community.readings import read_folder
            from jason.community.records_inventory import inventory as records_inventory
            from jason.tasks.association_pages import GOVERNING_FOLDERS, catalog_paths

            readings = read_folder(*(root / f for f in GOVERNING_FOLDERS[:2]), root / "governing")
            return tuple(records_inventory(community, catalog_paths(root, community.org_id), readings=readings,
                                           governing=governing, library=library))
        except Exception:  # noqa: BLE001 - an inventory that cannot be read is a miss for the record checks
            return ()

    try:
        from jason.community.profile import profile_name

        profile = profile_name()
    except Exception:  # noqa: BLE001
        profile = ""
    before_lib = tuple(distinct(raw))
    after_lib = tuple(distinct(raw + rows)) if rows else before_lib
    count = counter(root)
    before = Context(community=community, library=before_lib, holdings=holdings(before_lib), count=count,
                     private=lambda name: facts(name, profile=profile), settings=settings, profile=profile,
                     asks=tuple(asks))
    after = replace(before, library=after_lib, holdings=holdings(after_lib) if rows else before.holdings,
                    asks=tuple(after_asks if after_asks is not None else asks))
    return before, after


def moved(before: Any, after: Any) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """The checklist items whose status changed, and each stage gate before and after."""
    from jason.community.onboarding import check, gates

    rb, ra = check(before), check(after)
    now = {r.item.key: r for r in ra}
    items = [{"key": r.item.key, "title": r.item.title, "before": r.status.value, "after": now[r.item.key].status.value,
              "evidence": now[r.item.key].evidence}
             for r in rb if now[r.item.key].status is not r.status]
    gb, ga = gates(rb, before), gates(ra, after)
    gate_rows = [{"stage": b.gate.stage.value, "before": "open" if b.open else "closed",
                  "after": "open" if a.open else "closed", "waiting": a.evidence} for b, a in zip(gb, ga)]
    return items, gate_rows


# --- Apply ------------------------------------------------------------------------------------------------------------

def apply(items: list[FileItem], texts: dict[str, str], data_dir: Path, *, report: str = "") -> list[FileItem]:
    """Copy each ready file into ``data/library/files`` at its library path, keep its text in the library's cache, and
    record it in ``library.db`` (``documents`` and ``ingested``). A file with a question open, no kind, or no folder
    is held."""
    from jason.locks import Resource, hold
    from jason.tasks.library import COLUMNS, INGESTED, SCHEMA, STORE, TEXT_DIR

    ready = [i for i in items if i.status == "ready"]
    if not ready:
        return []
    root = Path(data_dir)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    done = []
    with hold(Resource.STORE, "library", timeout=120, purpose="jason ingest --apply"):
        db = root / STORE
        db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db) as conn:
            conn.execute(SCHEMA)
            conn.execute(INGESTED)
            for item in ready:
                dest = root / "library" / "files" / item.target
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.is_file():
                    shutil.copy2(item.local, dest)
                text_dir = root / TEXT_DIR
                text_dir.mkdir(parents=True, exist_ok=True)
                text = texts.get(item.sha256, "")
                (text_dir / f"{item.library_doc_id}.txt").write_text(text, encoding="utf-8")
                (text_dir / f"{item.library_doc_id}.json").write_text(json.dumps(
                    {"path": item.target, "file": str(dest), "source": item.text_source, "sha256": item.sha256,
                     "chars": len(text), "ingestedFrom": item.origin}), encoding="utf-8")
                row = _library_row(item, now)
                values = [",".join(row["records"]) if c == "records" else int(row["confidential"])
                          if c == "confidential" else row[c] for c in (x.strip() for x in COLUMNS.split(","))]
                conn.execute(f"INSERT OR REPLACE INTO documents ({COLUMNS}) VALUES ({','.join('?' * len(values))})",
                             values)
                conn.execute(f"INSERT OR REPLACE INTO ingested ({COLUMNS}, origin, dates, book, version, ingested_at, "
                             f"report) VALUES ({','.join('?' * (len(values) + 6))})",
                             values + [item.origin, json.dumps(item.dates), item.book, json.dumps(item.version), now,
                                       report])
                item.filed = True
                done.append(item)
    return done


# --- The run ----------------------------------------------------------------------------------------------------------

@dataclass
class Result:
    day: str
    sources: list[str]
    applied: bool
    parked: bool
    items: list[FileItem]
    notes: list[str]
    asks: list[Ask]
    groups: list[dict[str, Any]]
    moved: list[dict[str, str]]
    gates: list[dict[str, Any]]
    filed: list[FileItem] = field(default_factory=list)
    report: Path | None = None

    @property
    def unique(self) -> list[FileItem]:
        return [i for i in self.items if not i.duplicate_of]

    def counts(self) -> dict[str, Any]:
        u = self.unique
        status = Counter(i.status for i in u)
        methods = Counter(i.method or "NONE" for i in u if not i.library_path)
        return {"files": len(self.items), "distinct": len(u), "duplicates": len(self.items) - len(u),
                "inLibrary": sum(1 for i in u if i.library_path), "new": sum(1 for i in u if not i.library_path),
                "withText": sum(1 for i in u if i.text_chars), "ocr": sum(1 for i in u if i.text_source.startswith("ocr")),
                "noText": sum(1 for i in u if not i.text_chars), "byMethod": dict(methods.most_common()),
                "byStatus": dict(status.most_common()), "filed": len(self.filed),
                "versions": sum(1 for i in u if is_version(i.version)),
                "copies": sum(1 for i in u if i.version and not is_version(i.version)), "questions": len(self.asks),
                "confidential": sum(1 for i in u if i.confidential)}

    def as_dict(self) -> dict[str, Any]:
        u = self.unique
        return {"day": self.day, "sources": self.sources, "mode": "applied" if self.applied else "dry run",
                "parked": self.parked, "counts": self.counts(),
                "byKind": dict(Counter(i.kind or "(none)" for i in u).most_common()),
                "byBook": dict(Counter(i.book or "(none)" for i in u).most_common()),
                "byRecord": dict(Counter(r for i in u for r in i.records).most_common()),
                "byFolder": dict(Counter(i.folder or "(none)" for i in u).most_common()),
                "duplicates": [{"file": i.rel, "of": i.duplicate_of} for i in self.items if i.duplicate_of],
                "versions": [{"file": i.rel, **i.version} for i in u if is_version(i.version)],
                "copies": [{"file": i.rel, **i.version} for i in u if i.version and not is_version(i.version)],
                "groups": self.groups, "questions": [{"id": a.id, "kind": a.kind.value, "subject": a.subject,
                                                      "file": a.detail.get("file", ""), "question": a.question,
                                                      "suggestion": a.suggestion, "choices": list(a.choices)}
                                                     for a in self.asks],
                "moved": self.moved, "gates": self.gates, "notes": self.notes, "files": [i.row() for i in self.items]}


def read_by_kind(items: list[FileItem], texts: dict[str, str], root: Path, *, community: Any = None,
                 backend: Any = None, allow_remote: bool = False, today: date | None = None,
                 log: Callable[[str], None] = lambda s: None) -> list[str]:
    """The kind stage: each new file's kind weighed (``kind_analysis.analyze``), then the readers for that kind run
    (``kind_readers``): its document model, a contract's terms, a governing document's norms. A kind the analysis only
    proposes or questions is read too, so a person answering the question sees what each reading found; a file with
    no kind and no proposal is not read. ``backend`` (a person's choice) reviews a contract's terms; a remote backend
    skips a confidential file unless ``allow_remote``. Returns notes."""
    from jason.community.kind_analysis import Verdict, analyze
    from jason.community.kind_readers import ReaderContext, run_readers

    notes: list[str] = []
    for item in items:
        text = texts.get(item.sha256, "")
        if item.duplicate_of or item.library_path or not text.strip():
            continue
        analysis = analyze(item.name, text, classified=item.kind, method=item.method, confidence=item.confidence,
                           community=community, data_dir=root, today=today)
        item.analysis = analysis.as_dict()
        kinds = [analysis.kind] if analysis.kind else []
        if analysis.verdict is Verdict.DISAGREES and analysis.suggestion and analysis.suggestion != item.kind:
            kinds.append(analysis.suggestion)
        for n, kind in enumerate(kinds):
            ctx = ReaderContext(key=f"ingest-{item.key}" + (f"-as-{kind}" if n else ""), name=item.rel, kind=kind,
                                community=community, data_dir=root, today=today, confidential=item.confidential,
                                backend=backend if n == 0 else None, allow_remote=allow_remote, log=log)
            for key, summary in run_readers(text, ctx).items():
                item.readings[key if n == 0 else f"{key} (as {kind})"] = summary
            notes += ctx.notes
    return notes


def read_terms(items: list[FileItem], texts: dict[str, str], root: Path, **kw: Any) -> list[str]:
    """The kind stage over the given files (kept for callers that read only contracts)."""
    return read_by_kind(items, texts, root, **kw)


def run(community: Any, data_dir: Path, sources: list[str], *, drive: Any = None, model: Any = None, ocr: bool = True,
        apply_files: bool = False, park: bool = False, settings: Any = None, today: date | None = None,
        terms_backend: Any = None, allow_remote: bool = False,
        log: Callable[[str], None] = lambda s: None) -> Result:
    """The whole chain. Writes only under ``data/``: staged copies and text, the report, each contract's terms, and with
    ``apply_files`` the library, with ``park`` the intake queue. ``terms_backend`` is the model that reviews a
    contract's terms (``jason.community.term_model``); the grammar reads them without one."""
    from jason.community import intake
    from jason.tasks.library import person_kinds

    root = Path(data_dir)
    day = (today or date.today()).isoformat()
    items, notes = inventory(sources, root, drive=drive)
    log(f"inventory: {len(items)} files, {sum(1 for i in items if i.duplicate_of)} duplicates, "
        f"{sum(1 for i in items if i.library_path)} already in the library")
    stored = intake.load(root)
    chosen = person_kinds(root)
    texts: dict[str, str] = {}
    guesses: dict[str, Any] = {}
    state: dict[str, Any] = {}
    from jason.community.revision_detection import printed_dates
    from jason.tasks.library import load as load_library

    held = {str(r["id"]): r for r in load_library(root)} if any(i.library_path for i in items) else {}
    for n, item in enumerate(items, 1):
        if item.duplicate_of:
            continue
        text = read_text(item, root, ocr=ocr)
        texts[item.sha256] = text
        item.dates = sorted(set(item.dates) | {(d.isoformat(), "printed in the text") for d, _ in printed_dates(text)})
        if item.library_path:
            _from_library(item, held)
        else:
            row, answer = classify(community, item, text, model=model, chosen=chosen, state=state)
            _take(item, row)
            if answer is not None:
                guesses[item.sha256] = answer
        if n % 25 == 0:
            log(f"read {n} of {len(items)}")
    notes += state.get("notes", [])
    notes += read_by_kind(items, texts, root, community=community, backend=terms_backend, allow_remote=allow_remote,
                          today=today, log=log)
    known = known_documents(community, root)
    groups = find_versions(items, texts, known)
    propose(community, items, root, answered=answered_folders(stored))
    asks = questions(items, texts, community, guesses=guesses)
    scope = tuple(i.subject for i in items if not i.duplicate_of)
    queue_after = intake.merge(list(stored), list(asks), scope=scope)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = [_library_row(i, now) for i in items if i.status == "ready"]
    before, after = contexts(community, root, rows=rows, asks=tuple(stored), settings=settings,
                             after_asks=tuple(queue_after))
    result = Result(day, [str(s) for s in sources], apply_files, park, items, notes, asks, groups, [], [])
    report_name = f"{REPORT_PREFIX}{day}"
    if apply_files:
        result.filed = apply(items, texts, root, report=report_name)
        log(f"filed {len(result.filed)} files in the library")
    if park and asks:
        from jason.locks import Resource, hold

        with hold(Resource.STORE, LOCK, timeout=120, purpose="jason ingest --park"):
            intake.save(root, intake.merge(intake.load(root), list(asks), scope=scope))
    if apply_files:
        # Read the library again: it now holds the filed rows.
        _, after = contexts(community, root, rows=[], asks=tuple(queue_after), settings=settings)
    result.moved, result.gates = moved(before, after)
    result.report = write_report(result, root)
    return result


# --- The report -------------------------------------------------------------------------------------------------------

def _cell(text: Any) -> str:
    return " ".join(str(text if text is not None else "").split()).replace("|", "/")


def report_markdown(result: Result) -> str:
    d = result.as_dict()
    c = d["counts"]
    mode = "applied: the ready files were copied into the library" if result.applied else \
        "dry run: nothing was filed (--apply files the ready ones)"
    out = [f"# Ingest {result.day}", "",
           f"Sources: {', '.join(result.sources)}. {mode[0].upper()}{mode[1:]}. "
           f"Questions {'parked in the intake queue' if result.parked else 'listed, not parked (--park parks them)'}.",
           "", "This report is private: it names the association's files.", "",
           "| | Files |", "| --- | ---: |",
           f"| in the sources | {c['files']} |", f"| distinct (by sha256) | {c['distinct']} |",
           f"| duplicates | {c['duplicates']} |", f"| already in the library | {c['inLibrary']} |",
           f"| new | {c['new']} |", f"| with text | {c['withText']} |", f"| read by OCR | {c['ocr']} |",
           f"| no text | {c['noText']} |", f"| versions of a document | {c['versions']} |",
           f"| confidential | {c['confidential']} |", f"| filed | {c['filed']} |", f"| questions | {c['questions']} |",
           ""]
    out += ["## By status", "", "| Status | Files |", "| --- | ---: |"]
    out += [f"| {k} | {v} |" for k, v in c["byStatus"].items()] + [""]
    out += ["## How the new files were classified", "", "| Method | Files |", "| --- | ---: |"]
    out += [f"| {k} | {v} |" for k, v in c["byMethod"].items()] + [""]
    for title, key in (("By kind", "byKind"), ("By book", "byBook"), ("By Civil Code 5200 record", "byRecord"),
                       ("By library folder", "byFolder")):
        out += [f"## {title}", "", "| | Files |", "| --- | ---: |"]
        out += [f"| {_cell(k)} | {v} |" for k, v in d[key].items()] + [""]
    out += ["## Duplicates", ""]
    out += [f"- {_cell(x['file'])} is the same file as {_cell(x['of'])}" for x in d["duplicates"]] or ["None."]
    out += ["", "## Versions", "",
            "A file holding enough of a known document's current text is a version of it. A version not on record of "
            "a living or citable document is reported here and never applied: a person reads it beside the current "
            "text, and `jason revisions KEY` keeps the document's history.", ""]
    rows = [v for v in d["versions"] if v.get("document")]
    if rows:
        out += ["| File | Document | Holds | Version | Existed by | Claims |", "| --- | --- | ---: | --- | --- | --- |"]
        for v in rows:
            tags = "/".join(t for t, on in (("living", v.get("living")), ("citable", v.get("citable"))) if on)
            label = v["status"] + (f" ({v['versionId']}" + (f", {v['versionOn']}" if v.get("versionOn") else "") + ")"
                                   if v.get("versionId") else "")
            out.append(f"| {_cell(v['file'])} | {v['document']}{f' ({tags})' if tags else ''} | {v['share']:.0%} | "
                       f"{_cell(label)} | {v.get('existedBy', '')} {_cell(v.get('existedHow', ''))} | "
                       f"{v.get('claims', '')} |")
        new = [v for v in rows if v["status"] == "not on record" and (v.get("living") or v.get("citable"))]
        if new:
            out += ["", f"**{len(new)} new version{'s' if len(new) != 1 else ''} of a living or citable document** "
                        "(reported, not applied): " + "; ".join(f"{_cell(v['file'])} ({v['document']})" for v in new)]
    else:
        out.append("No file is a version of a document jason knows.")
    if d["copies"]:
        out += ["", "Files that carry a known document inside them (a packet, a notice quoting it): a copy, not a "
                    "version; `jason section-refs` follows such copies of a section.", ""]
        out += [f"- {_cell(v['file'])}: {v['status']} of {v['document']} (holds {v['share']:.0%} of it; it is "
                f"{v['own']:.0%} of the file)" for v in d["copies"]]
    if d["groups"]:
        out += ["", "Files that share their words with each other and with no known document:", ""]
        for g in d["groups"]:
            out.append(f"- {g['group']} ({g['kind'] or 'no kind'}, {g['texts']} distinct text"
                       f"{'s' if g['texts'] != 1 else ''}): " + "; ".join(
                           f"{_cell(f)} ({s.get('existedBy', 'undated')})" for f, s in zip(g["files"], g["dates"])))
    out += ["", "## Questions", "",
            "Parked in the intake queue: answer them with `jason intake --answer ID TEXT --by NAME` or in the "
            "onboarding session." if result.parked else
            "Not parked: `jason ingest ... --park` parks them in the intake queue.", ""]
    for q in d["questions"]:
        out.append(f"- [{q['id']}] {q['kind']} {_cell(q['file'])}: {_cell(q['question'])}"
                   + (f" Suggested: {q['suggestion']}." if q["suggestion"] else "")
                   + (f" Choices: {', '.join(q['choices'][:CHOICES])}." if q["choices"] else ""))
    if not d["questions"]:
        out.append("None.")
    out += ["", "## The onboarding checklist", "",
            "The checklist run before and after: after, as if the ready files were filed and the questions parked."
            if not result.applied else "The checklist run before and after filing (and as if the questions were "
                                       "parked).", ""]
    if d["moved"]:
        out += ["| Item | Before | After | Evidence |", "| --- | --- | --- | --- |"]
        out += [f"| {m['key']} | {m['before']} | {m['after']} | {_cell(m['evidence'])} |" for m in d["moved"]]
    else:
        out.append("No checklist item moved.")
    out += ["", "| Stage | Before | After |", "| --- | --- | --- |"]
    out += [f"| {g['stage']} | {g['before']} | {g['after']} |" for g in d["gates"]]
    out += ["", "## Files", "", "| File | Status | Kind | Method | Book | Records | Folder | Dates |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for f in d["files"]:
        dates = "; ".join(f"{on} {how}" for on, how in f["dates"][:4])
        out.append(f"| {_cell(f['rel'])} | {f['status']} | {f['kind']} | {f['method']} | {f['book']} | "
                   f"{', '.join(f['records'])} | {_cell(f['folder'])} | {_cell(dates)} |")
    if d["notes"]:
        out += ["", "## Notes", ""] + [f"- {_cell(n)}" for n in d["notes"]]
    return "\n".join(out) + "\n"


def write_report(result: Result, data_dir: Path) -> Path:
    folder = Path(data_dir) / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{REPORT_PREFIX}{result.day}.md"
    path.write_text(report_markdown(result), encoding="utf-8")
    path.with_suffix(".json").write_text(json.dumps(result.as_dict(), indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def lines(result: Result) -> list[str]:
    """The run in a few lines: counts only, no file names."""
    c = result.counts()
    out = [f"{c['files']} files: {c['distinct']} distinct, {c['duplicates']} duplicates, {c['inLibrary']} already in the "
           f"library, {c['new']} new",
           f"text: {c['withText']} read ({c['ocr']} by OCR), {c['noText']} without",
           "new files by method: " + (", ".join(f"{k.lower()} {v}" for k, v in c["byMethod"].items()) or "none"),
           "status: " + ", ".join(f"{k} {v}" for k, v in c["byStatus"].items()),
           f"versions of a document: {c['versions']}"
           + (f"; {len(result.groups)} groups of unknown versions" if result.groups else "")
           + (f"; {c['copies']} files carry a copy of one" if c["copies"] else ""),
           f"questions: {c['questions']}" + (" (" + ", ".join(f"{k} {v}" for k, v in Counter(
               a.kind.value for a in result.asks).most_common()) + ")" if result.asks else "")
           + ("" if not result.asks else ", parked" if result.parked else ", not parked: --park parks them"),
           f"filed: {c['filed']}" if result.applied else "dry run: nothing filed (--apply files the ready ones)"]
    verdicts = Counter(i.analysis.get("verdict") for i in result.unique if i.analysis)
    if verdicts:
        out.append("kind analysis: " + ", ".join(f"{k} {v}" for k, v in verdicts.most_common()))
    termed = [i for i in result.unique if i.terms]
    if termed:
        out.append(f"contract terms: {len(termed)} contracts read, {sum(len(i.terms.get('deliverables', [])) for i in termed)} "
                   f"deliverables, {sum(len(set(i.terms.get('findings', []))) for i in termed)} kinds of finding")
    for m in result.moved:
        out.append(f"checklist {m['key']}: {m['before']} -> {m['after']}")
    for g in result.gates:
        if g["before"] != g["after"]:
            out.append(f"gate {g['stage']}: {g['before']} -> {g['after']}")
    if result.report is not None:
        out.append(f"wrote {result.report}")
    return out


# --- The session's "ingest" stage -------------------------------------------------------------------------------------

def last_report(data_dir: Path) -> Path | None:
    """The newest ingest report's JSON, or None."""
    folder = Path(data_dir) / FOLDER
    found = sorted(folder.glob(f"{REPORT_PREFIX}*.json")) if folder.is_dir() else []
    return max(found, key=lambda p: (p.stem, p.stat().st_mtime)) if found else None


def gate(data_dir: Path) -> dict[str, Any] | None:
    """What the last ingest says, for the onboarding session's "ingest" stage (read-only): when and what it read, the
    files filed and held, the versions found, the checklist items it moved, and how many of its questions are still
    open in the intake queue. None when nothing was ever ingested. Counts and keys only."""
    from jason.community import intake

    path = last_report(data_dir)
    if path is None:
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    c = d.get("counts") or {}
    ids = {q.get("id") for q in d.get("questions") or ()}
    queue = {a.id: a for a in intake.load(Path(data_dir))}
    still = sum(1 for i in ids if i in queue and queue[i].status is AskStatus.OPEN)
    held = sum(v for k, v in (c.get("byStatus") or {}).items() if str(k).startswith("held"))
    return {"report": f"data/{FOLDER}/{path.with_suffix('.md').name}", "day": d.get("day", ""), "mode": d.get("mode", ""),
            "files": c.get("files", 0), "distinct": c.get("distinct", 0), "new": c.get("new", 0),
            "filed": c.get("filed", 0), "held": held, "versions": c.get("versions", 0),
            "newVersions": sum(1 for v in d.get("versions") or () if v.get("status") == "not on record"
                               and (v.get("living") or v.get("citable"))),
            "questions": len(ids), "parked": bool(d.get("parked")),
            "inQueue": sum(1 for i in ids if i in queue), "stillOpen": still,
            "moved": [{"key": m.get("key"), "before": m.get("before"), "after": m.get("after")}
                      for m in d.get("moved") or ()]}


def gate_lines(data_dir: Path) -> list[str]:
    """The "ingest" stage's lines for the session view."""
    g = gate(data_dir)
    if g is None:
        return ["Ingest: nothing taken in yet (jason ingest SOURCE)"]
    out = [f"Ingest: last run {g['day']} ({g['mode']}): {g['files']} files, {g['new']} new, {g['filed']} filed, "
           f"{g['held']} held; report {g['report']}"]
    if g["versions"]:
        out.append(f"  versions found: {g['versions']}"
                   + (f", {g['newVersions']} new of a living or citable document (reported, not applied)"
                      if g["newVersions"] else ""))
    if g["questions"]:
        out.append(f"  questions: {g['questions']}, " + (f"{g['stillOpen']} still open in the queue" if g["parked"]
                                                         else "not parked (jason ingest ... --park)"))
    for m in g["moved"]:
        out.append(f"  moved {m['key']}: {m['before']} -> {m['after']}")
    return out


__all__ = ["FileItem", "Known", "Result", "answered_folders", "apply", "classify", "contexts", "drive_folder_id",
           "file_dates", "find_versions", "gate", "gate_lines", "inventory", "known_documents", "last_report", "lines",
           "is_version", "moved", "needs_kind", "propose", "questions", "read_text", "report_markdown", "run", "write_report"]
