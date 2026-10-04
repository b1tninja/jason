"""A legal case's file from Drive, on disk and as its own confidential catalog in the passage index.

A case in the specification (the profile's ``legal_cases()``) with a ``drive_folder`` has a case file: every Drive file
under that folder, as the last ``jason drive --sync`` listed it. ``fetch`` downloads the readable files into
``data/cases/<key>/files`` (a Google Doc as PDF, a caption transcript as text) and writes ``manifest.json`` with every file
and what became of it. A file whose name matches the case's ``held_back`` globs (medical and veterinary records) is not
downloaded unless a person passes ``include_held``, and a copy from an earlier run that included it is removed.
Images, recordings, archives, and shortcuts are listed, not taken.

``extract_text`` writes a text extract beside each file that is not text already: ``<name>.pdf.txt`` beside
``<name>.pdf``, in the same subfolder, so a hit's file name says which PDF it came from. The readers are the
library's (``jason.tasks.library.text_of``, ``jason.community.ocr``): the PDF's text layer; for a page that is a scan,
the local OCR engines; and the local vision model only when a person asks for it. The manifest's ``extracts`` records
how each was read and the file's SHA-256, so an unchanged file is not read again and a changed one is. A file no reader
can read is recorded and listed, never skipped in silence. A held-back file is never extracted, even when a person had
a copy fetched.

``index_sources`` gives each such case its own catalog in the passage index (``case-<key>``), which ``jason index
--build`` includes: confidential, so a search sees it only when it names the catalog or asks for confidential files,
with the standing ``evidence`` (neither the association's record nor the law). The index reads the ``.md`` and ``.txt``
files (the caption transcripts, and the extracts); an extract's context line names its source file and how it was
read, so a hit shows how far its words can be trusted. A file with no extract is on disk but not searched, and
``jason index --plan`` counts it.
Nothing in Drive is changed.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


CASES_DIR = "cases"
MANIFEST = "manifest.json"
_DOCUMENT = "application/vnd.google-apps.document"
_SHORTCUT = "application/vnd.google-apps.shortcut"
# Read as they are; a caption transcript is text under another name.
_TAKEN = (".pdf", ".txt", ".md", ".docx", ".doc", ".csv", ".xlsx", ".pptx", ".html", ".htm", ".eml")
_AS_TEXT = (".vtt", ".srt")
# What the index reads as it is. An extract is one of these, named for its source: "<name>.pdf" + EXTRACT_SUFFIX.
_TEXT = (".md", ".txt")
_IMAGES = (".png", ".jpg", ".jpeg", ".tif", ".tiff")
EXTRACT_SUFFIX = ".txt"
EXTRACT_VERSION = 1            # raise it when the reading changes, and every extract is made again
# A page that carries an image and whose text layer holds fewer characters is a scan (an exhibit inside a typed
# filing, with at most a stamped header or page number in its layer): it goes to OCR.
PAGE_MIN = 100
HELD = "held back by the case's rule"
NO_EXTRACT = "no text extract yet: jason cases --extract-text"
UNREADABLE = "no reader could read it"
SUPERSEDED = "a note beside a file whose extract holds its words"
CASE_FILE = "a legal case's file"


def case_dir(data_dir: Path, case: Any) -> Path:
    return Path(data_dir) / CASES_DIR / case.key


CATALOG_PREFIX = "case-"


def catalog_name(case: Any) -> str:
    return f"{CATALOG_PREFIX}{case.key}"


def is_case_catalog(name: str) -> bool:
    return name.strip().lower().startswith(CATALOG_PREFIX)


def is_held(name: str, case: Any) -> bool:
    return any(fnmatch.fnmatchcase(name, glob) for glob in case.held_back)


def _safe(part: str) -> str:
    """A Drive name as a Windows file name: no reserved characters, no trailing dots or spaces."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", part).rstrip(". ") or "_"


# --- the manifest -----------------------------------------------------------------------------------------------------


def _manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _lock(case: Any, purpose: str):
    """The store lock on one case's manifest: ``fetch`` and ``extract_text`` both read it, change it, and write it."""
    from jason.locks import Resource, hold

    return hold(Resource.STORE, f"case-files-{case.key}", purpose=purpose)


class ReadMethod(Enum):
    """How an extract's words were read, which is how far they can be trusted."""

    TEXT_LAYER = "text layer"        # the PDF's own text: what the file says
    OCR = "ocr"                      # a local OCR engine read the page images: it may misread
    VISION = "vision"                # the local vision model read the page images: it may misread
    DOCUMENT = "document"            # the words of a Word file or a table, read from the file itself
    UNREADABLE = "unreadable"        # no reader gave words: a miss, recorded so it is listed


@dataclass(frozen=True)
class Extract:
    """One case file's text extract, as the manifest records it under the file's path in ``files``."""

    source: str                       # the file's path under files/, with forward slashes
    method: ReadMethod
    sha256: str                       # of the source file's bytes when it was read
    text: str = ""                    # the extract's path under files/; empty when unreadable
    engine: str = ""                  # the engine that read the scanned pages ("a+b" when two did)
    model: str = ""                   # the vision model, when one read
    chars: int = 0
    pages: int = 0
    scan_pages: int = 0               # pages (or an image) with no text layer of their own
    unread_pages: int = 0             # scanned pages no reader gave words for: not in the extract
    reason: str = ""                  # why it is unreadable
    tried: tuple[str, ...] = ()       # the engines on offer when it was read
    read_at: str = ""
    version: int = EXTRACT_VERSION

    @property
    def readable(self) -> bool:
        return self.method is not ReadMethod.UNREADABLE and bool(self.text)

    @property
    def partial(self) -> bool:
        return self.readable and self.unread_pages > 0

    def _reader(self) -> str:
        return f"vision model: {self.model or self.engine}" if self.model else f"OCR: {self.engine}"

    @property
    def label(self) -> str:
        """The method as the counts name it."""
        read = self.scan_pages - self.unread_pages
        if self.method is ReadMethod.TEXT_LAYER:
            return f"text layer, scanned pages by {self._reader()}" if read else "text layer"
        if self.method in (ReadMethod.OCR, ReadMethod.VISION):
            return self._reader()
        return "the file's own words" if self.method is ReadMethod.DOCUMENT else UNREADABLE

    @property
    def context(self) -> str:
        """The index's context line: the source file, and how its words were read."""
        if self.method is ReadMethod.TEXT_LAYER:
            how = "text layer"
            read = self.scan_pages - self.unread_pages
            if read:
                how += f"; {read} of {self.pages} pages read by {self._reader()}, which may misread"
            if self.unread_pages:
                how += f"; {self.unread_pages} of {self.pages} pages are images no reader gave words for"
        elif self.method in (ReadMethod.OCR, ReadMethod.VISION):
            how = f"{self._reader()}; may misread"
            if self.unread_pages:
                how += f"; {self.unread_pages} of {self.pages} pages are images no reader gave words for"
        else:
            how = "the file's own words"
        return f"{self.source}: {how}"

    def as_json(self) -> dict[str, Any]:
        row = {"text": self.text, "method": self.method.value, "engine": self.engine, "model": self.model,
               "sha256": self.sha256, "chars": self.chars, "pages": self.pages, "scanPages": self.scan_pages,
               "unreadPages": self.unread_pages, "reason": self.reason, "tried": list(self.tried),
               "readAt": self.read_at, "version": self.version}
        return {key: value for key, value in row.items() if value not in ("", 0, []) or key in ("method", "sha256")}

    @classmethod
    def from_json(cls, source: str, row: dict[str, Any]) -> "Extract":
        return cls(source, ReadMethod(row["method"]), str(row.get("sha256") or ""), str(row.get("text") or ""),
                   str(row.get("engine") or ""), str(row.get("model") or ""), int(row.get("chars") or 0),
                   int(row.get("pages") or 0), int(row.get("scanPages") or 0), int(row.get("unreadPages") or 0),
                   str(row.get("reason") or ""), tuple(row.get("tried") or ()), str(row.get("readAt") or ""),
                   int(row.get("version") or 0))


def extracts(data_dir: Path, case: Any) -> dict[str, Extract]:
    """The case's recorded extracts, by the source file's path under files/. A row this code cannot read is left out,
    so its file is read again."""
    out: dict[str, Extract] = {}
    for source, row in (_manifest(case_dir(data_dir, case)).get("extracts") or {}).items():
        try:
            out[source] = Extract.from_json(source, row)
        except (KeyError, ValueError, TypeError):
            continue
    return out


def _held_here(rel: str, case: Any, rows: dict[str, dict[str, Any]]) -> bool:
    """Whether the file at ``rel`` under files/ is one the case holds back: by its name on disk, or by its name in
    Drive (a Google Doc is stored with ".pdf" added, and a character Windows reserves is replaced)."""
    row = rows.get(rel)
    return is_held(rel.rsplit("/", 1)[-1], case) or bool(row and is_held(row.get("name") or "", case))


def _rows_by_local(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["local"]: row for row in manifest.get("files") or [] if row.get("local")}


# --- the fetch --------------------------------------------------------------------------------------------------------


def plan(data_dir: Path, case: Any) -> list[dict[str, Any]]:
    """Every file under the case's Drive folder, from data/drive/files.json, with what fetch does with it."""
    listing = Path(data_dir) / "drive" / "files.json"
    if not listing.is_file():
        raise FileNotFoundError("run jason drive --sync first: the case file is read from its Drive listing")
    prefix = f"My Drive/{case.drive_folder}/"
    rows = []
    for f in json.loads(listing.read_text(encoding="utf-8"))["files"]:
        if not f["path"].startswith(prefix):
            continue
        rel = f["path"][len(prefix):]
        suffix = Path(f["name"]).suffix.lower()
        if f["mimeType"] == _SHORTCUT:
            # The target lives elsewhere (a governing document, the minutes) and is cataloged there, not in the case.
            action, local = "listed", ""
        elif f["mimeType"] == _DOCUMENT:
            action, local = "export", rel + ".pdf"
        elif suffix in _TAKEN:
            action, local = "download", rel
        elif suffix in _AS_TEXT:
            action, local = "download", rel + ".txt"
        else:
            action, local = "listed", ""
        rows.append({"id": f["id"], "name": f["name"], "path": rel, "mimeType": f["mimeType"], "md5": f.get("md5") or "",
                     "modified": f.get("modified") or "", "heldBack": is_held(f["name"], case), "action": action,
                     "local": "/".join(_safe(p) for p in local.split("/")) if local else ""})
    return rows


def fetch(drive: Any, data_dir: Path, case: Any, *, include_held: bool = False,
          log: Callable[[str], None] | None = None) -> dict[str, int]:
    """Download the case file's readable files; a copy whose Drive MD5 and modified time are unchanged is kept."""
    say = log or (lambda _m: None)
    root = case_dir(data_dir, case)
    files = root / "files"
    manifest_path = root / MANIFEST
    before = {r["id"]: r for r in _manifest(root).get("files") or []}
    counts = {"files": 0, "downloaded": 0, "kept": 0, "heldBack": 0, "listed": 0, "errors": 0}
    rows = plan(data_dir, case)
    for row in rows:
        counts["files"] += 1
        if row["action"] == "listed":
            counts["listed"] += 1
            continue
        target = files / row["local"]
        if row["heldBack"] and not include_held:
            # jason's own copy from a run that included it goes, and any extract of it, so the index cannot take it;
            # Drive keeps the file.
            for copy in (target, target.with_name(target.name + EXTRACT_SUFFIX)):
                if copy.is_file():
                    copy.unlink()
            row["action"] = "held back"
            counts["heldBack"] += 1
            continue
        prior = before.get(row["id"])
        if target.is_file() and prior and prior.get("md5") == row["md5"] and prior.get("modified") == row["modified"]:
            row["stored"] = True
            counts["kept"] += 1
            continue
        try:
            if row["action"] == "export":
                drive.export_pdf(row["id"], target)
            else:
                drive.download(row["id"], target)
            row["stored"] = True
            counts["downloaded"] += 1
            say(f"  {row['path']}")
        except Exception as exc:  # one unreadable file does not stop the case file
            row["error"] = str(exc)
            counts["errors"] += 1
    root.mkdir(parents=True, exist_ok=True)
    with _lock(case, "write the case file's manifest"):
        # The extracts' rows are ``extract_text``'s: read again under the lock and carried over as they are.
        kept = _manifest(root).get("extracts") or {}
        manifest_path.write_text(json.dumps({"case": case.key, "caseNumber": case.case_number, "driveFolder": case.drive_folder,
                                             "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                             "includeHeld": include_held, "files": rows, "extracts": kept}, indent=1),
                                 encoding="utf-8")
    return counts


# --- the text extracts ------------------------------------------------------------------------------------------------


@dataclass
class ExtractReport:
    """What one ``extract_text`` run did, and what the case's file holds now."""

    extracted: dict[str, int] = field(default_factory=dict)       # read in this run, by method
    unchanged: int = 0                                            # read before, and the file's bytes are the same
    has_text: int = 0                                             # a text file not jason's already sits beside it
    held_back: int = 0
    removed: int = 0                                              # extracts of files that are gone or now held back
    unreadable: list[tuple[str, str]] = field(default_factory=list)       # the file, and why
    partial: list[Extract] = field(default_factory=list)          # read, with scanned pages no reader gave words for
    rows: list[Extract] = field(default_factory=list)             # every file's record after the run

    def lines(self) -> list[str]:
        made = sum(self.extracted.values())
        by = f" ({', '.join(f'{label} {n}' for label, n in sorted(self.extracted.items()))})" if made else ""
        out = [f"text: extracted {made}{by}, unchanged {self.unchanged}, held back {self.held_back}, "
               f"unreadable {len(self.unreadable)}"
               + (f", already text {self.has_text}" if self.has_text else "")
               + (f", removed {self.removed}" if self.removed else "")]
        out += [f"unreadable: {source} ({why})" for source, why in self.unreadable]
        out += [f"partly read: {e.source} ({e.unread_pages} of {e.pages} pages are images no reader gave words for: "
                f"photographs, or scans to read with --vision)" for e in self.partial]
        return out


def vision_reader(model: str = "") -> Any:
    """The local vision model as a reader for ``extract_text(vision=...)``. It runs ``local_ai.preflight`` first and
    raises ``LocalAIUnavailable`` when the model would not load or would run on the CPU."""
    from jason.community.ocr import OllamaVisionOcr
    from jason.local_ai import preflight

    reader = OllamaVisionOcr(model=model)
    preflight(reader.model, ollama_url=reader.base_url)
    return reader


def _name(reader: Any) -> str:
    return str(getattr(reader, "name", "") or type(reader).__name__)


def _settled(record: Extract, offered: tuple[str, ...], vision: str) -> bool:
    """Whether reading an unchanged file again could give anything more."""
    if record.scan_pages == 0:
        return True                                     # a text layer, the file's own words, or a type with no reader
    if record.unread_pages == 0:
        # Every scanned page was read. Only a person asking for the vision model has them read again, once.
        return not vision or vision in record.engine.split("+")
    return set(offered) <= set(record.tried)            # pages still unread: only an engine not tried yet is worth a run


def _page_layers(path: Path) -> list[tuple[str, bool]]:
    """Each page's own text layer, and whether the page carries an image."""
    import pymupdf

    with pymupdf.open(str(path)) as document:
        return [(page.get_text(), bool(page.get_images())) for page in document]


_EXISTING = "extract"          # ``text_of``'s word for a text file already beside the file


def _read(path: Path, readers: Sequence[Any], vision: Any, purpose: str) -> tuple[str, dict[str, Any]]:
    """The file's words and how they were read, as ``Extract`` fields; ``{"existing": True}`` when a text file beside
    it already holds them. The library's readers do the reading."""
    from jason.community import ocr
    from jason.locks import Resource, hold
    from jason.tasks.library import text_of

    suffix = path.suffix.lower()
    if suffix != ".pdf":
        if suffix in _IMAGES and vision is not None and not path.with_name(path.name + ".md").is_file():
            with hold(Resource.GPU, purpose=purpose):
                try:
                    seen = vision.text_of(path)
                except Exception:
                    seen = ""
            if ocr.reads_as_words(seen):
                return seen, {"method": ReadMethod.VISION, "engine": _name(vision),
                              "model": str(getattr(vision, "model", "") or _name(vision)), "pages": 1, "scan_pages": 1}
        text, how = text_of(path, ocr_engines=readers)
        scan = 1 if suffix in _IMAGES else 0
        if how == _EXISTING:
            return text, {"existing": True}
        if how.startswith("ocr: ") and not ocr.reads_as_words(text):
            text, how = "", "image; OCR read no words"
        if not text.strip():
            return "", {"method": ReadMethod.UNREADABLE, "reason": how or "no words in the file", "pages": scan,
                        "scan_pages": scan, "unread_pages": scan}
        if how.startswith("ocr: "):
            return text, {"method": ReadMethod.OCR, "engine": how[5:], "pages": 1, "scan_pages": 1}
        return text, {"method": ReadMethod.DOCUMENT}

    text, how = text_of(path, ocr_engines=())           # the text layer only: no page is sent anywhere yet
    if how == _EXISTING:
        return text, {"existing": True}
    if not how.startswith(("text layer", "image-only")):
        return "", {"method": ReadMethod.UNREADABLE, "reason": how}
    try:
        layers = _page_layers(path)
    except Exception as exc:
        return "", {"method": ReadMethod.UNREADABLE, "reason": f"unreadable PDF: {exc}"}
    scans = [n for n, (layer, image) in enumerate(layers) if image and len(layer.strip()) < PAGE_MIN]
    read: dict[int, tuple[str, str]] = {}
    if scans and vision is not None:
        with hold(Resource.GPU, purpose=purpose):
            read = ocr.pages_text(path, scans, (vision,))
    rest = [n for n in scans if n not in read]
    if rest and readers:
        read.update(ocr.pages_text(path, rest, readers))
    used = list(dict.fromkeys(engine for _, engine in read.values()))
    by_vision = vision is not None and _name(vision) in used
    model = str(getattr(vision, "model", "") or _name(vision)) if by_vision else ""
    fields: dict[str, Any] = {"pages": len(layers), "scan_pages": len(scans), "unread_pages": len(scans) - len(read),
                              "engine": "+".join(used), "model": model}
    if not read:
        body = text
    else:
        parts = []
        for n, (layer, _image) in enumerate(layers):
            if n not in read:
                parts.append(layer)
                continue
            words, engine = read[n]
            reader = f"vision model: {model}" if by_vision and engine == _name(vision) else f"OCR: {engine}"
            parts.append("\n".join(part for part in (layer.strip(), f"[page {n + 1}: {reader}; may misread]",
                                                     words.strip()) if part))
        body = "\n".join(parts)
    if not body.strip():
        if not scans:
            why = "no text layer and no page image to read"
        elif readers or vision is not None:
            why = "image-only; no reader gave words"
        else:
            why = "image-only; no OCR engine is installed"
        return "", {**fields, "method": ReadMethod.UNREADABLE, "reason": why}
    if how.startswith("text layer") or not read:
        method = ReadMethod.TEXT_LAYER                  # the file's own words, with any scanned pages filled in
    else:
        method = ReadMethod.VISION if by_vision else ReadMethod.OCR
    return body, {**fields, "method": method}


def extract_text(data_dir: Path, case: Any, *, engines: Sequence[Any] | None = None, vision: Any = None,
                 refresh: bool = False, log: Callable[[str], None] | None = None) -> ExtractReport:
    """Write a text extract beside each of the case's fetched files that has none, and record each in the manifest.

    - A PDF with a text layer is read from it and goes to no OCR engine. A page that is a scan (an image, and almost
      no text layer) goes to ``engines`` (None: the local engines this machine can run, ``ocr.local_engines``; never
      the vision model), page by page.
    - ``vision`` is the vision model's reader (``vision_reader``, which runs the preflight): only when a person asked.
      It reads the scanned pages in place of the local engines, holding the GPU lock.
    - A file whose bytes are unchanged since its extract is not read again; ``refresh`` reads every file again.
    - A held-back file is never read, and an extract of one is removed. An extract whose file is gone is removed.
    - A file no reader can read is recorded as unreadable and listed.

    Each file's row is written to the manifest, under the case's store lock, as soon as the file is read, so a run that
    is stopped keeps what it did."""
    from jason.community import ocr

    say = log or (lambda _m: None)
    root = case_dir(data_dir, case)
    files = root / "files"
    report = ExtractReport()
    if not files.is_dir():
        return report
    readers = tuple(ocr.local_engines() if engines is None else engines)
    offered = tuple(_name(r) for r in readers) + ((_name(vision),) if vision is not None else ())
    manifest = _manifest(root)
    rows = _rows_by_local(manifest)
    known = extracts(data_dir, case)
    on_disk = {path.relative_to(files).as_posix(): path for path in sorted(files.rglob("*")) if path.is_file()}

    def record(source: str, row: Extract | None) -> None:
        with _lock(case, "record a case file's text extract"):
            now = _manifest(root) or {"case": case.key, "caseNumber": case.case_number,
                                      "driveFolder": case.drive_folder, "files": []}
            kept = now.setdefault("extracts", {})
            if row is None:
                kept.pop(source, None)
            else:
                kept[source] = row.as_json()
            root.mkdir(parents=True, exist_ok=True)
            (root / MANIFEST).write_text(json.dumps(now, indent=1), encoding="utf-8")

    def drop(row: Extract) -> None:
        if row.text and (files / row.text).is_file():
            (files / row.text).unlink()
        record(row.source, None)
        report.removed += 1

    for source, row in list(known.items()):
        if source not in on_disk:                       # the file is gone (fetch removes a held copy): so is its text
            drop(row)
            del known[source]
    for rel, path in on_disk.items():
        if path.suffix.lower() in _TEXT:
            continue                                    # text already: the index reads it as it is
        prior = known.get(rel)
        if _held_here(rel, case, rows):
            if prior is not None:
                drop(prior)
            report.held_back += 1
            continue
        target = rel + EXTRACT_SUFFIX
        if target in on_disk and target in rows:
            report.has_text += 1                        # a file of that name came from Drive: it is never overwritten
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if (prior is not None and not refresh and prior.sha256 == sha and prior.version == EXTRACT_VERSION
                and (not prior.text or (files / prior.text).is_file())
                and _settled(prior, offered, _name(vision) if vision is not None else "")):
            if prior.readable:
                report.unchanged += 1
            row = prior
        else:
            text, how = _read(path, readers, vision, f"read {catalog_name(case)}'s scanned pages")
            if how.get("existing"):
                if prior is not None:
                    drop(prior)
                report.has_text += 1
                continue
            row = Extract(rel, sha256=sha, text=target if text.strip() else "", chars=len(text), tried=offered,
                          read_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), **how)
            if row.readable:
                (files / target).write_text(text, encoding="utf-8")
                report.extracted[row.label] = report.extracted.get(row.label, 0) + 1
                say(f"  {rel}: {row.label}, {row.chars} characters")
            elif prior is not None and prior.text and (files / prior.text).is_file():
                (files / prior.text).unlink()           # the old words are of other bytes
            record(rel, row)
        report.rows.append(row)
        if not row.readable:
            report.unreadable.append((rel, row.reason or UNREADABLE))
        elif row.partial:
            report.partial.append(row)
    return report


# --- the index --------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CaseSource:
    """One case's fetched file for the passage index (``passage_index.build``): its text files and its extracts, as the
    confidential catalog ``case-<key>`` with the standing ``evidence``. An extract's context line names its source file
    and how it was read. A held-back file's text is never given, whatever is on disk."""

    case: Any

    @property
    def catalog(self) -> str:
        return catalog_name(self.case)

    @property
    def catalogs(self) -> tuple[str, ...]:
        return (self.catalog,)

    @property
    def folder(self) -> str:
        return f"{CASES_DIR}/{self.case.key}/files"

    @property
    def standing(self) -> Any:
        from jason.community.passage_index import Standing

        return Standing.EVIDENCE

    confidential = True
    generated = False

    def plan(self, data_dir: Path) -> Any:
        """The entries, and what is left out and why: held back, not extracted yet, or unreadable. Reads only."""
        from jason.community.passage_index import IndexFile
        from jason.tasks.index_sources import Plan

        made = Plan(self.catalog)
        files = Path(data_dir) / self.folder
        if not files.is_dir():
            return made
        rows = _rows_by_local(_manifest(case_dir(data_dir, self.case)))
        known = extracts(data_dir, self.case)
        by_text = {row.text: row for row in known.values() if row.readable}
        on_disk = {path.relative_to(files).as_posix(): path for path in sorted(files.rglob("*")) if path.is_file()}
        for rel, path in on_disk.items():
            if path.suffix.lower() not in _TEXT:
                row = known.get(rel)
                if _held_here(rel, self.case, rows):
                    made.leave(HELD)
                elif row is not None and not row.readable:
                    made.leave(UNREADABLE)
                elif row is None and not any(rel + suffix in on_disk for suffix in _TEXT):
                    made.leave(NO_EXTRACT)
                continue
            row = by_text.get(rel)
            beside = rel.rsplit(".", 1)[0]              # "<name>.pdf" for "<name>.pdf.txt" or "<name>.pdf.md"
            # A text file is held back by its own name, or as the text of a held file.
            if any(_held_here(name, self.case, rows) for name in {rel, beside, row.source if row else rel}):
                if beside not in on_disk:
                    made.leave(HELD)                    # beside its file, the file was counted above
                continue
            if row is None and beside + EXTRACT_SUFFIX in by_text:
                made.leave(SUPERSEDED)                  # "<name>.pdf.md" beside "<name>.pdf.txt": one text a file
                continue
            made.take(IndexFile(path, self.catalog, self.standing, confidential=True,
                                context=row.context if row is not None else ""), CASE_FILE)
        return made

    def entries(self, data_dir: Path) -> Iterable[Any]:
        return self.plan(data_dir).entries


def index_sources(cases: tuple) -> tuple:
    """One confidential ``CaseSource`` per case with a Drive folder: its fetched files' text, as catalog case-<key>."""
    return tuple(CaseSource(case) for case in cases if getattr(case, "drive_folder", ""))


__all__ = ["CASES_DIR", "CATALOG_PREFIX", "CaseSource", "EXTRACT_SUFFIX", "Extract", "ExtractReport", "ReadMethod",
           "case_dir", "catalog_name", "extract_text", "extracts", "fetch", "index_sources", "is_case_catalog",
           "is_held", "plan", "vision_reader"]
