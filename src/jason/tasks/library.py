"""Ingest the association's document library: fetch, read, classify, refine, and store.

The chain, per file in the PayHOA catalog:

1. classify by name and folder (the specification's rules);
2. find the file: ``data/library/files/<library path>``, else a copy of the
   same name elsewhere under ``data`` (the Drive mirror, the deed scans),
   else fetch it from PayHOA when a client is given (bulk zips of 40);
3. read its text once and cache it under ``data/library/text/<id>.txt``:
   a sibling ``.pdf.md`` extract, the PDF's text layer, an OCR engine when
   one is installed and the page is image-only, a CSV or text file, or the
   words of a Word document;
4. for a file the rules missed, the phrase rules over the text, then the
   local model when one is asked for;
5. for every file with text, the record refinements and a period from the
   text when the name gave none;
6. store each row in ``data/library/library.db`` with its method.

Templates are classified by name and not fetched; an image is fetched and read
by the OCR engines (the local vision model first). Nothing is
sent anywhere but the PayHOA fetch, which reads the association's own
library, and the local model.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sqlite3
import zipfile
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.content import ModelClassifier, ModelUnavailable, classify_text, period_from_text, private_content, records_from_text
from jason.community.library import Classified, LibraryDocument, Method, classify_library, payhoa_documents
from jason.community.symbols import AssociationRecord, DocumentKind

LIBRARY_DIR = "library"
FILES_DIR = "library/files"
TEXT_DIR = "library/text"
STORE = "library/library.db"
# Where copies of library files already live on disk, searched by file name.
MIRRORS = ("artifacts/site-docs", "governing", "insurance-pdfs", "reserve-studies", "dre")
# Blank platform templates have nothing to read. Images are fetched: the vision model reads a screenshot's words.
SKIP_FETCH = frozenset({DocumentKind.TEMPLATE})
BATCH = 40


@dataclass
class IngestReport:
    documents: int = 0
    fetched: int = 0
    found_local: int = 0
    with_text: int = 0
    by_content: int = 0
    by_model: int = 0
    refined: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f"library documents={self.documents} fetched={self.fetched} local={self.found_local} text={self.with_text} "
                f"content={self.by_content} model={self.by_model} refined={self.refined} errors={len(self.errors)}")


def mirror_index(root: Path) -> dict[str, Path]:
    """Every file under the mirror folders, by lower-cased name; the first found wins."""
    found: dict[str, Path] = {}
    for folder in MIRRORS:
        base = root / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and not path.name.endswith(".md"):
                found.setdefault(path.name.casefold(), path)
    return found


def local_path(root: Path, doc: LibraryDocument, mirrors: dict[str, Path]) -> Path | None:
    own = root / FILES_DIR / doc.path
    if own.is_file():
        return own
    return mirrors.get(doc.name.casefold())


def fetch(client, org_id: int, docs: list[LibraryDocument], root: Path, *, batch: int = BATCH) -> tuple[int, list[str]]:
    """Bulk-download ``docs`` from PayHOA into ``data/library/files`` by their library paths."""
    fetched, errors = 0, []
    out = root / FILES_DIR
    for start in range(0, len(docs), batch):
        chunk = docs[start: start + batch]
        target = root / LIBRARY_DIR / "_bulk.zip"
        try:
            client.bulk_download_documents(org_id, [int(doc.id) for doc in chunk], target)
            with zipfile.ZipFile(target) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    dest = out / info.filename
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(archive.read(info))
                    fetched += 1
        except Exception as exc:
            errors.append(f"batch {start // batch}: {exc}")
        finally:
            if target.exists():
                target.unlink()
    return fetched, errors


def _pdf_layer(path: Path) -> str:
    """A PDF's own text layer, or "" when PyMuPDF cannot read it."""
    try:
        import pymupdf

        with pymupdf.open(str(path)) as doc:
            return "\n".join(page.get_text() for page in doc)
    except Exception:
        return ""


def text_of(path: Path) -> tuple[str, str]:
    """The words of a file and where they came from; ("", reason) when none could be read."""
    suffix = path.suffix.lower()
    sibling = path.with_name(path.name + ".md")
    if sibling.is_file():
        extract = sibling.read_text(encoding="utf-8", errors="ignore")
        # A site export of a scan is only its header ("# name", drive id, mime, path); read the PDF itself then.
        body = "\n".join(line for line in extract.splitlines() if line.strip() and not line.startswith(("#", "- drive_id", "- mime", "- path")))
        if suffix != ".pdf":
            return extract, "extract"
        if len(body.strip()) >= 200:
            # An extract can stop short (the bylaws' ends at page 25 of 42); the PDF's own layer wins when it is longer.
            layer = _pdf_layer(path)
            if len(layer.strip()) > 1.1 * len(body.strip()):
                return layer, "text layer (longer than the extract)"
            return extract, "extract"
    if suffix in (".txt", ".csv"):
        return path.read_text(encoding="utf-8", errors="ignore"), "file"
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml)).strip(), "docx"
        except (KeyError, zipfile.BadZipFile):
            return "", "unreadable docx"
    if suffix in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
        # An image is a one-page scan: OCR is the only reader.
        from jason.community.ocr import engines

        for engine in engines():
            if engine.name == "anythingllm-collector":
                continue
            try:
                read = engine.text_of(path)
            except Exception:
                continue
            if read.strip():
                return read, f"ocr: {engine.name}"
        return "", "image; no OCR engine read it"
    if suffix != ".pdf":
        return "", "no text reader for this type"
    try:
        import pymupdf
    except ImportError:
        return "", "PyMuPDF not installed"
    try:
        with pymupdf.open(str(path)) as doc:
            text = "\n".join(page.get_text() for page in doc)
    except Exception as exc:
        return "", f"unreadable PDF: {exc}"
    if len(text.strip()) >= 200:
        return text, "text layer"
    from jason.community.ocr import engines

    for engine in engines():
        try:
            ocr = engine.text_of(path)
        except Exception:
            continue
        if len(ocr.strip()) >= 200:
            return ocr, f"ocr: {getattr(engine, 'name', type(engine).__name__)}"
    return text, "image-only; no OCR engine read it"


def ingest(community, root: Path, *, client=None, org_id: int | None = None, model: ModelClassifier | None = None,
           refresh_text: bool = False) -> tuple[tuple[Classified, ...], IngestReport]:
    report = IngestReport()
    docs = payhoa_documents(root / "payhoa.db")
    rows = list(classify_library(community, docs))
    report.documents = len(rows)
    mirrors = mirror_index(root)
    if client is not None and org_id is not None:
        wanted = [row.document for row in rows if row.kind not in SKIP_FETCH and local_path(root, row.document, mirrors) is None]
        report.fetched, errors = fetch(client, org_id, wanted, root)
        report.errors.extend(errors)
    text_dir = root / TEXT_DIR
    text_dir.mkdir(parents=True, exist_ok=True)
    model_ok = model is not None
    from jason.tasks.agenda_kinds import decisions

    agenda_kinds = decisions(root, "PayHOA library")      # the agenda items' recorded kinds, by library id
    for index, row in enumerate(rows):
        if row.kind in SKIP_FETCH:
            continue
        path = local_path(root, row.document, mirrors)
        if path is None:
            continue
        if not path.is_relative_to(root / FILES_DIR):
            report.found_local += 1
        text = _cached_text(text_dir, row.document, path, refresh_text)
        if not text.strip():
            continue
        report.with_text += 1
        if row.kind is None:
            kind, evidence = classify_text(text)
            agenda = agenda_kinds.get(str(row.document.id)) if kind is None else None
            if kind is not None:
                row = replace(row, kind=kind, method=Method.CONTENT, evidence=evidence)
                report.by_content += 1
            elif agenda is not None:
                row = replace(row, kind=DocumentKind(agenda["kind"]), method=Method.AGENDA, evidence=agenda["evidence"],
                              confidence=agenda["confidence"])
            elif model_ok:
                try:
                    answer = model.classify(row.document.name, text)
                except ModelUnavailable as exc:
                    report.errors.append(str(exc))
                    model_ok = False
                    answer = None
                if answer is not None and answer.kind is not None and answer.confidence >= 0.5:
                    row = replace(row, kind=answer.kind, method=Method.MODEL, evidence=f"model: {answer.reason}", confidence=answer.confidence,
                                  period=row.period or answer.period)
                    report.by_model += 1
        extras = records_from_text(row.kind, text)
        if extras:
            row = replace(row, extra_records=tuple(record for record, _ in extras),
                          evidence=(row.evidence + "; " if row.evidence else "") + "; ".join(why for _, why in extras))
            report.refined += 1
        private = private_content(row.kind, text)
        if private:
            row = replace(row, private=private, evidence=(row.evidence + "; " if row.evidence else "") + "confidential: " + private)
        if not row.period:
            found = period_from_text(text)
            if found:
                row = replace(row, period=found)
        rows[index] = row
    rows_t = tuple(rows)
    save(root, rows_t)
    return rows_t, report


def _cached_text(text_dir: Path, doc: LibraryDocument, path: Path, refresh: bool) -> str:
    cache = text_dir / f"{doc.id}.txt"
    if cache.is_file() and not refresh:
        return cache.read_text(encoding="utf-8", errors="ignore")
    text, source = text_of(path)
    cache.write_text(text, encoding="utf-8")
    (text_dir / f"{doc.id}.json").write_text(json.dumps({"path": doc.path, "file": str(path), "source": source,
                                                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "chars": len(text)}), encoding="utf-8")
    return text


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, source TEXT, path TEXT, name TEXT, kind TEXT, category TEXT, records TEXT, method TEXT,
    period TEXT, confidential INTEGER, evidence TEXT, confidence REAL, classified_at TEXT, sha256 TEXT
)
"""


def save(root: Path, rows: tuple[Classified, ...]) -> Path:
    path = root / STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE IF EXISTS documents")
        conn.execute(SCHEMA)
        conn.executemany(
            "INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(r.document.id, r.document.source, r.document.path, r.document.name, r.kind.value if r.kind else "",
              r.category.value if r.category else "", ",".join(x.value for x in r.records), r.method.name, r.period,
              int(r.confidential), r.evidence, r.confidence, now, _sha(root, r.document.id)) for r in rows],
        )
    return path


def _sha(root: Path, doc_id: str) -> str:
    """The file's SHA-256 from its text cache note, or "" when it was never read."""
    note = root / TEXT_DIR / f"{doc_id}.json"
    if not note.is_file():
        return ""
    try:
        return str(json.loads(note.read_text(encoding="utf-8")).get("sha256") or "")
    except json.JSONDecodeError:
        return ""


def distinct(rows) -> list[dict[str, Any]]:
    """One row per distinct file: the same PDF filed in two folders (a meeting's minutes, and the copy in Email
    Attachments) is kept once, under the first path. A file never read is told apart by its name and period."""
    by_key: dict[str, dict[str, Any]] = {}
    kept: list[dict[str, Any]] = []
    for row in rows:
        key = row.get("sha256") or f"{row['name'].casefold()}|{row.get('period') or ''}|{row['kind']}"
        first = by_key.get(key)
        if first is None:
            merged = dict(row, copies=[row["path"]], records=list(row["records"]))
            by_key[key] = merged
            kept.append(merged)
            continue
        # A copy's folder can add a record (the resale packet's copy is also a 4525 transfer document); keep both.
        first["copies"].append(row["path"])
        first["records"] += [record for record in row["records"] if record not in first["records"]]
        first["confidential"] = first["confidential"] or row["confidential"]
    return kept


def load(root: Path) -> tuple[dict[str, Any], ...]:
    """The stored rows as dicts, newest period first within each kind."""
    path = root / STORE
    if not path.is_file():
        return ()
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in conn.execute("SELECT * FROM documents ORDER BY kind, period DESC, path")]
    finally:
        conn.close()
    for row in rows:
        row["records"] = [r for r in (row.get("records") or "").split(",") if r]
        row["confidential"] = bool(row.get("confidential"))
    return tuple(rows)


VISION_MARK = "--- ocr: ollama-vision ---"
VISION_END = "--- end ocr: ollama-vision ---"


def text_for(root: Path, doc_id: str) -> str:
    """The file's cached text; a vision reading (``vision_read``) comes first, and replaces it when it read every page.

    A reading of only some pages sits between ``VISION_MARK`` and ``VISION_END``, and the older text (which repeats
    those pages, OCR'd worse) follows."""
    if str(doc_id).startswith("drive-"):             # a file read from Drive, not the library (jason.tasks.drive_minutes)
        kept = root / "meetings" / "minutes-files" / f"{str(doc_id)[6:]}.txt"
        return kept.read_text(encoding="utf-8", errors="ignore") if kept.is_file() else ""
    folder = root / TEXT_DIR
    cache = folder / f"{doc_id}.txt"
    text = cache.read_text(encoding="utf-8", errors="ignore") if cache.is_file() else ""
    vision = folder / f"{doc_id}.vision.txt"
    if not vision.is_file():
        return text
    read = vision.read_text(encoding="utf-8", errors="ignore")
    try:
        note = json.loads((folder / f"{doc_id}.vision.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        note = {}
    if note.get("pagesRead") and note.get("pagesRead") == note.get("pages"):
        return read
    return f"{VISION_MARK}\n{read}\n{VISION_END}\n\n{text}" if text else read


def vision_read(root: Path, doc_id: str, *, pages: int | None = None, engine: Any = None, refresh: bool = False) -> str:
    """Read a library file's first ``pages`` (all when None) with the local vision model; kept beside its cached text.

    Tesseract drops or garbles what a vision model reads: a recorder's stamp, a
    table, handwriting. The reading is a second text layer, never a fact.
    """
    from jason.community.ocr import OllamaVisionOcr

    folder = root / TEXT_DIR
    target = folder / f"{doc_id}.vision.txt"
    if target.is_file() and not refresh:
        return target.read_text(encoding="utf-8", errors="ignore")
    try:
        note = json.loads((folder / f"{doc_id}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    path = Path(str(note.get("file") or ""))
    if not path.is_file() or path.suffix.lower() not in (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"):
        return ""
    reader = engine or OllamaVisionOcr(max_pages=pages)
    total = 1
    if path.suffix.lower() == ".pdf":
        import pymupdf

        with pymupdf.open(path) as document:
            total = document.page_count
    text = reader.text_of(path)
    if not text.strip():
        return ""
    target.write_text(text, encoding="utf-8")
    (folder / f"{doc_id}.vision.json").write_text(json.dumps({
        "file": str(path), "engine": getattr(reader, "name", ""), "model": getattr(reader, "model", ""),
        "pages": total, "pagesRead": min(total, pages) if pages else total, "chars": len(text),
        "readAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}), encoding="utf-8")
    return text


def _unused(_: Any) -> None:
    return None


@dataclass
class Scorecard:
    """How a text classifier agrees with the name rules on files both can read."""

    reader: str
    cases: int = 0
    agree: int = 0
    silent: int = 0
    per_kind: dict[str, list[int]] = field(default_factory=dict)
    misses: list[dict[str, str]] = field(default_factory=list)
    errors: int = 0

    @property
    def accuracy(self) -> float:
        answered = self.cases - self.silent
        return self.agree / answered if answered else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {"reader": self.reader, "cases": self.cases, "agree": self.agree, "silent": self.silent, "errors": self.errors,
                "accuracyWhenAnswering": round(self.accuracy, 3),
                "perKind": {k: {"cases": v[0], "agree": v[1], "silent": v[2]} for k, v in sorted(self.per_kind.items())},
                "misses": self.misses[:40]}


# Kinds a name decides better than any text (a template's words are a minutes form; a photo has none).
_NOT_SCORED = frozenset({DocumentKind.TEMPLATE, DocumentKind.IMAGE, DocumentKind.GRANT_DEED})


def score(root: Path, rows: tuple[Classified, ...], *, model: ModelClassifier | None = None, limit: int | None = None,
          per_kind: int | None = None) -> Scorecard:
    """Score the phrase rules, or the model when given, against the name rules' answers on files with text.

    The name rules are the answer key: they read the association's own
    naming, which is reliable where it exists. A disagreement is either a
    phrase rule to fix or a file misnamed, and the misses list says which
    files to read. ``limit`` caps the cases for a slow model.
    """
    card = Scorecard("model: " + model.model if model is not None else "phrase rules")
    labelled = [row for row in rows if row.method is Method.NAME and row.kind is not None and row.kind not in _NOT_SCORED]
    taken: dict[DocumentKind, int] = {}
    seen: set[str] = set()
    failures = 0
    for row in labelled:
        if limit is not None and card.cases >= limit:
            break
        if per_kind is not None and taken.get(row.kind, 0) >= per_kind:
            continue
        text = text_for(root, row.document.id)
        if len(text.strip()) < 200 or row.document.path in seen:
            continue
        seen.add(row.document.path)
        taken[row.kind] = taken.get(row.kind, 0) + 1
        if model is not None:
            try:
                answer = model.classify(row.document.name, text)
                failures = 0
            except ModelUnavailable:
                # One failed call is a hiccup; three in a row is a model that is not there.
                failures += 1
                card.errors += 1
                if failures >= 3:
                    break
                continue
            guess = answer.kind
        else:
            guess, _ = classify_text(text)
        card.cases += 1
        entry = card.per_kind.setdefault(row.kind.value, [0, 0, 0])
        entry[0] += 1
        if guess is None:
            card.silent += 1
            entry[2] += 1
        elif guess is row.kind:
            card.agree += 1
            entry[1] += 1
        else:
            card.misses.append({"path": row.document.path, "name": row.kind.value, "text": guess.value})
    return card


__all__ = ["ingest", "load", "save", "text_of", "text_for", "fetch", "score", "Scorecard", "IngestReport", "AssociationRecord", "io"]
