"""Document references: what a loader returns for each document a screen names (docs/console/doc-component.md).

A screen shows a document with the console's ``Doc`` component, fed a ``DocRef`` from its loader. A reference names the
document by its evidence address (``jason.approvals.evidence``), never by a URL into data/, an absolute path, or its
contents::

    {address, document?, name, kind, level?, source?, readAt?, size?, thumb?, original?: {url, label},
     refreshable?: {system, what}, stale?}

- ``doc_ref(address, name=None, document=None)`` is a **light resolve**: it reads only the copy's metadata (a file's
  size and modified time, a copy's record, whether a thumbnail is on disk, the level), never the document. ``kind`` is
  the kind of the address's first document (``pdf``, ``image``, ``text``, ``submission``, ...). Keys with no value are
  left out, as the TypeScript type's optional fields are.
- ``file_ref``, ``drive_ref``, ``library_ref``, ``submission_ref``, and ``citation_ref`` build one kind each.
- ``refs_from_strings`` maps the free-text evidence strings older stores hold (a board item's ``evidence``) to
  references: ``library: <path>`` and ``library:<id>``, ``Drive: <name>`` (only when exactly one file in Drive's
  listing has that name), ``data/<path>`` (only a file on disk in a place ``jason.web.access`` names), and a citation
  ``jason cite`` parses. A command (``jason ...``) stays ``{command}``; anything else stays ``{text}``, never a guess.

A name is masked as the evidence masks it (an email address or a phone number in it is dotted out). Reads disk only:
nothing here reaches PayHOA, Google, or Keeper.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path, PurePosixPath
from typing import Any

# The kinds a document renders as (docs/console/documents.md, "The model"); the renderer is chosen by kind.
DOC_KINDS = ("submission", "form", "pdf", "image", "text", "table", "html", "message", "audio", "file")
LEVELS = ("P0", "P1", "P2", "P3", "P4")

# Which copy a reference is, by the place a file under data/ is kept: the first prefix that matches names it.
FILE_SOURCES: tuple[tuple[str, str], ...] = (
    ("governing/", "Recorded copy"),
    ("artifacts/site-docs/", "Recorded copy"),
    ("key-documents/", "Recorded copy"),
    ("mail/", "Scan"),
    ("mailroom/", "Mailroom"),
    ("payhoa-files/", "PayHOA"),
    ("gmail/files/", "Gmail attachment"),
    ("library/", "Library copy"),
    ("drive/copies/", "Drive copy"),
)
FILE_ON_DISK = "File on disk"
DRIVE_SOURCE = "Drive copy"
LIBRARY_SOURCE = "Library copy"
PAYHOA_SOURCE = "PayHOA"
STATUTES_SOURCE = "Statutes on disk"
DOCUMENTS_SOURCE = "Documents on disk"
OPEN_IN_GOOGLE = "Open in Google"
OPEN_IN_PAYHOA = "Open in PayHOA"

_ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/]|~)")
_STATUTE = re.compile(r"^[A-Z]{2,5} \d")


def _root(data_dir: Path | None) -> Path:
    from jason.approvals.evidence import _root as evidence_root

    return evidence_root(data_dir)


def _masked(name: str) -> str:
    from jason.approvals.evidence import mask_text

    return mask_text(" ".join(str(name or "").split()))[0]


def _mtime(path: Path) -> str:
    from jason.approvals.evidence import _mtime as mtime

    return mtime(path)


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _clean(ref: dict[str, Any]) -> dict[str, Any]:
    """The reference with its keys in the spec's order and the empty ones left out (``address``, ``name``, and
    ``kind`` always stay)."""
    order = ("address", "document", "name", "kind", "level", "source", "readAt", "size", "thumb", "original",
             "refreshable", "stale")
    out: dict[str, Any] = {}
    for key in order:
        value = ref.get(key)
        if key in ("address", "name", "kind") or value not in (None, "", 0, False, {}):
            out[key] = value
    return out


def _first(docs: list[Any]) -> Any:
    """The document a reference opens first: the file itself (a PDF, an image, a submission), else its text."""
    for kind in ("submission", "pdf", "image", "text"):
        found = next((d for d in docs if d.kind == kind), None)
        if found is not None:
            return found
    return docs[0] if docs else None


# --- one kind each ------------------------------------------------------------------------------------------------------

def _rel(rel_path: str) -> str:
    """A path under the data folder as the ``file:`` address takes it: posix, no leading ``data/``. An absolute path, a
    path outside the folder, or none is ``ValueError``: a reference never carries one."""
    text = str(rel_path or "").strip().replace("\\", "/")
    if not text or "\x00" in text or _ABSOLUTE.match(text):
        raise ValueError(f"{text[:60] or '(none)'} is not a path under the data folder")
    text = text.removeprefix("./").removeprefix("data/")
    parts = PurePosixPath(text).parts
    if not parts or ".." in parts:
        raise ValueError(f"{text[:60]} is not a path under the data folder")
    return "/".join(parts)


def _file(root: Path, rel: str, name: str | None, document: str | None) -> dict[str, Any]:
    from jason.approvals.evidence_documents import file_place, kind_of
    from jason.web.access import level_of_path

    found = file_place(root, rel)
    posix = found[0] if found is not None else rel
    level = level_of_path(posix, root).value
    source = next((said for prefix, said in FILE_SOURCES if posix.lower().startswith(prefix)), FILE_ON_DISK)
    kind = kind_of(posix)
    ref: dict[str, Any] = {"address": f"file:{posix}", "name": name or PurePosixPath(posix).name, "kind": kind,
                           "level": level, "source": source}
    if found is not None:
        path = found[1]
        ref.update(document=document or kind, readAt=_mtime(path), size=_size(path), thumb=kind == "pdf")
    return ref


def _drive(root: Path, drive_id: str, name: str | None, document: str | None) -> dict[str, Any]:
    from jason.approvals.evidence import DRIVE_CHANGED, _against_drive, drive_link, rule_for
    from jason.approvals.evidence_documents import drive_documents
    from jason.tasks import drive_copies

    record = drive_copies.read_record(root, drive_id) or {}
    synced_at, listing = _catalog(root)
    listed = listing.get(drive_id) or {}
    holding = drive_copies.holdings_row(root, drive_id) or {}
    mime = str(record.get("mimeType") or listed.get("mimeType") or holding.get("mimeType") or "")
    docs = drive_documents(root, drive_id, private=True)        # names and sizes only; the level says who opens them
    first = next((d for d in docs if d.id == document), None) if document else _first(docs)
    try:
        level = drive_copies.level_of(root, drive_id)
    except (OSError, ValueError):
        level = "P2"
    rule, _ = rule_for(f"drive:{drive_id}")
    ref: dict[str, Any] = {
        "address": f"drive:{drive_id}",
        "name": name or str(record.get("name") or listed.get("name") or holding.get("name") or f"Drive file {drive_id}"),
        "kind": first.kind if first is not None else _mime_kind(mime), "level": level, "source": DRIVE_SOURCE,
        "thumb": drive_copies.thumbnail(root, drive_id) is not None,
        "original": {"url": drive_link(drive_id, mime, str(record.get("webViewLink") or ""), str(listed.get("link") or "")),
                     "label": OPEN_IN_GOOGLE},
        "refreshable": rule.refresher.as_dict() if rule.refresher is not None else None}
    if first is not None:
        ref.update(document=first.id, size=first.size)
    if record.get("readAt"):
        ref["readAt"] = str(record["readAt"])
    if record and listed and _against_drive(record, listed, synced_at)[0]:
        ref["stale"] = DRIVE_CHANGED
    return ref


def _mime_kind(mime: str) -> str:
    """The kind jason's copy of a Drive file will be, by its type, before there is a copy: a Doc, Sheet, Slides file,
    or PDF exports as a PDF; an image is kept as an image."""
    if mime.startswith("application/vnd.google-apps.") or mime == "application/pdf":
        return "pdf"
    if mime.startswith("image/"):
        return "image"
    return "file"


def _library(root: Path, doc_id: str, name: str | None, document: str | None) -> dict[str, Any]:
    from jason.approvals.evidence import library_row
    from jason.approvals.evidence_documents import kind_of
    from jason.web.access import level_of_library

    row = library_row(root, doc_id) or {}
    path = str(row.get("path") or "")
    ref: dict[str, Any] = {"address": f"library:{doc_id}",
                           "name": name or str(row.get("name") or PurePosixPath(path).name or f"Library document {doc_id}"),
                           "kind": kind_of(path) if path else "file", "level": level_of_library(doc_id, root).value,
                           "source": LIBRARY_SOURCE}
    file = root / "library" / "files" / path if path else None
    if file is not None and file.is_file():
        ref.update(document=document or f"library:{doc_id}", readAt=_mtime(file), size=_size(file),
                   thumb=ref["kind"] == "pdf")
    return ref


def _submission(root: Path, sid: int, name: str | None, document: str | None) -> dict[str, Any]:
    from jason.approvals.evidence import _catalog_path, _catalog_row, _files_root, rule_for
    from jason.tasks.payhoa_forms import requests_link
    from jason.tasks.submission_cache import FILE

    row = _catalog_row(_catalog_path(root), sid) or {}
    kept = _files_root(root) / "requests" / str(sid) / FILE
    rule, _ = rule_for(f"payhoa:submission:{sid}")
    form = str(row.get("form_name") or "")
    ref: dict[str, Any] = {"address": f"payhoa:submission:{sid}",
                           "name": name or (f"{form} (request {sid})" if form else f"PayHOA request {sid}"),
                           "kind": "submission", "level": "P2", "source": PAYHOA_SOURCE,
                           "refreshable": rule.refresher.as_dict() if rule.refresher is not None else None}
    if kept.is_file():
        ref.update(document=document or "submission", readAt=_mtime(kept))
    if row.get("unit_id"):
        ref["original"] = {"url": requests_link(int(row["unit_id"])), "label": OPEN_IN_PAYHOA}
    return ref


def _citation_ref(expression: str, name: str | None, document: str | None) -> dict[str, Any]:
    statute = bool(_STATUTE.match(expression))
    return {"address": expression, "document": document or "section", "name": name or expression, "kind": "text",
            "level": "P0", "source": STATUTES_SOURCE if statute else DOCUMENTS_SOURCE}


# --- the light resolve --------------------------------------------------------------------------------------------------

def doc_ref(address: str, *, name: str | None = None, document: str | None = None,
            data_dir: Path | None = None) -> dict[str, Any]:
    """The reference for one evidence address (the module doc), from the copy's metadata only. ``name`` replaces the
    name jason would give it; ``document`` names one of the address's documents (default: its first). An address no
    reader takes is still a reference (kind ``file``, level P2): the ``Doc`` it feeds asks the evidence and says why.
    ``ValueError`` for no address, and for a ``file:`` address with an absolute path or one outside the folder."""
    from jason.approvals.evidence import EvidenceKind, rule_for

    address = " ".join(str(address or "").split())
    if not address:
        raise ValueError("a document reference names an evidence address")
    root = _root(data_dir)
    given = _masked(name) if name else None
    rule, found = rule_for(address)
    if rule.kind is EvidenceKind.FILE and found is not None:
        ref = _file(root, _rel(found.group(1)), given, document)
    elif rule.kind is EvidenceKind.DRIVE and found is not None:
        ref = _drive(root, found.group(1), given, document)
    elif rule.kind is EvidenceKind.LIBRARY and found is not None:
        ref = _library(root, found.group(1), given, document)
    elif rule.kind is EvidenceKind.PAYHOA_SUBMISSION and found is not None:
        ref = _submission(root, int(found.group(1)), given, document)
    elif rule.kind is EvidenceKind.CITATION:
        ref = _citation_ref(address, given, document)
    elif rule.kind is EvidenceKind.BOARD_ITEM and found is not None:
        ref = {"address": address, "name": given or f"Board item {found.group(1).strip()}", "kind": "text",
               "level": "P1", "source": "Board items"}
    else:
        ref = {"address": address, "name": given or address, "kind": "file", "level": "P2", "document": document}
    ref["name"] = _masked(ref["name"])
    return _clean(ref)


def file_ref(rel_path: str, *, name: str | None = None, data_dir: Path | None = None) -> dict[str, Any]:
    """A file under the data folder (``file:<path>``): ``rel_path`` relative to it (a leading ``data/`` is dropped);
    an absolute path is ``ValueError``."""
    return doc_ref(f"file:{_rel(rel_path)}", name=name, data_dir=data_dir)


def drive_ref(drive_id: str, *, name: str | None = None, data_dir: Path | None = None) -> dict[str, Any]:
    """A Drive file (``drive:<id>``): jason's copy of it, when it keeps one."""
    from jason.tasks.drive_copies import valid_id

    if not valid_id(drive_id):
        raise ValueError(f"{str(drive_id)[:40] or '(none)'} is not a Drive file id")
    return doc_ref(f"drive:{drive_id}", name=name, data_dir=data_dir)


def library_ref(doc_id: str, *, name: str | None = None, data_dir: Path | None = None) -> dict[str, Any]:
    """A library document (``library:<id>``)."""
    from jason.approvals.evidence import LIBRARY_ID

    if not re.fullmatch(LIBRARY_ID, str(doc_id or "")):
        raise ValueError(f"{str(doc_id)[:40] or '(none)'} is not a library document id")
    return doc_ref(f"library:{doc_id}", name=name, data_dir=data_dir)


def submission_ref(number: int | str, *, name: str | None = None, data_dir: Path | None = None) -> dict[str, Any]:
    """A PayHOA request's submission (``payhoa:submission:<n>``)."""
    sid = int(number)
    if sid <= 0:
        raise ValueError(f"{number} is not a PayHOA request number")
    return doc_ref(f"payhoa:submission:{sid}", name=name, data_dir=data_dir)


def citation_ref(expression: str, *, name: str | None = None) -> dict[str, Any]:
    """A citation ``jason cite`` reads (``CIV 4920(a)``, ``jason://decl/6.2(a)``): its whole section, as text. The
    grammar is checked; the words are not read. ``ValueError`` for one the grammar does not take."""
    text = " ".join(str(expression or "").split())
    if not _is_citation(text):
        raise ValueError(f"{text[:60] or '(none)'} is not a citation jason cite reads")
    return _clean(_citation_ref(text, _masked(name) if name else None, None))


def _is_citation(text: str) -> bool:
    """A citation the cite grammar names: a statute or a document's section, or a ``jason://`` address; a ``book#n``
    form only when it is one word (``decl#6.2(a)``), so a sentence with "#" in it is not taken."""
    if not text:
        return False
    if text.lower().startswith("jason://"):
        return True
    if re.fullmatch(r"[\w.-]+#\S+", text):
        return True
    from jason.community.cite import Target, parse

    try:
        return isinstance(parse(text, {}), Target)
    except Exception:  # noqa: BLE001 - the grammar never takes it: not a citation
        return False


# --- the older stores' free text ------------------------------------------------------------------------------------------

_CATALOG: dict[str, tuple[tuple[int, int], tuple[str, dict[str, dict[str, Any]]]]] = {}


def _catalog(root: Path) -> tuple[str, dict[str, dict[str, Any]]]:
    """Drive's listing (``drive/files.json``) by id, read once a version of the file (it is large)."""
    from jason.tasks import drive_copies

    path = Path(root) / "drive" / "files.json"
    try:
        stat = path.stat()
    except OSError:
        return "", {}
    stamp = (stat.st_mtime_ns, stat.st_size)
    cached = _CATALOG.get(str(path))
    if cached is not None and cached[0] == stamp:
        return cached[1]
    got = drive_copies.catalog(root)
    _CATALOG[str(path)] = (stamp, got)
    return got


def _drive_named(root: Path, said: str) -> str:
    """The id of the one file in Drive's listing whose name, or path, is ``said`` exactly, or whose path ends with it
    whole folder by folder (``Folder/Name.pdf``); "" for none or several. A folder's name is not a file."""
    _, listing = _catalog(root)
    if said in listing:
        return said
    tail = "/" + said.strip("/")
    hits = {fid for fid, f in listing.items()
            if said == str(f.get("name") or "") or ("/" in said and ("/" + str(f.get("path") or "")).endswith(tail))}
    return next(iter(hits)) if len(hits) == 1 else ""


def _library_named(root: Path, said: str) -> str:
    """The id of the library document ``said`` names: its id; else its library path, its name, or its file's name,
    exactly, when they name one file (copies of one path are one file: the first id). "" for none or several."""
    db = Path(root) / "library" / "library.db"
    if not said or not db.is_file():
        return ""
    try:
        conn = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
        try:
            if conn.execute("SELECT 1 FROM documents WHERE id = ?", (said,)).fetchone():
                return said
            rows = conn.execute("SELECT id, path, name FROM documents ORDER BY id").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return ""
    wanted = said.casefold()
    hits = [(str(i), str(p or "")) for i, p, n in rows
            if wanted in (str(p or "").casefold(), str(n or "").casefold(), PurePosixPath(str(p or "")).name.casefold())]
    paths = {p for _, p in hits}
    return hits[0][0] if hits and len(paths) == 1 else ""


def _data_file(root: Path, said: str) -> str:
    """The path under the data folder ``data/<path>`` names, when it is a file on disk in a place jason's access rules
    name; "" otherwise."""
    from jason.web.access import placed

    try:
        rel = _rel(said)
    except ValueError:
        return ""
    path = Path(root) / rel
    return rel if path.is_file() and placed(rel, Path(root)) else ""


_DOC_ADDRESS = re.compile(r"^(?:drive|file|library|payhoa:submission):\S")


def ref_from_string(text: str, *, data_dir: Path | None = None) -> dict[str, Any]:
    """One free-text evidence string as a reference (``refs_from_strings``)."""
    from jason.approvals.evidence import mask_text

    said = " ".join(str(text or "").split())
    root = _root(data_dir)
    if not said:
        return {"text": ""}
    if said.startswith("jason "):
        return {"command": mask_text(said)[0]}
    if _DOC_ADDRESS.match(said) and not said.lower().startswith("library: "):
        from jason.approvals.evidence import EvidenceKind, rule_for

        rule, found = rule_for(said)
        if found is not None and rule.kind in (EvidenceKind.DRIVE, EvidenceKind.FILE, EvidenceKind.LIBRARY,
                                                EvidenceKind.PAYHOA_SUBMISSION):
            if rule.kind is not EvidenceKind.LIBRARY or _library_named(root, found.group(1)):
                try:
                    return doc_ref(said, data_dir=root)
                except ValueError:
                    pass
    head, sep, rest = said.partition(":")
    rest = rest.strip()
    if sep and head.casefold() == "library" and rest:
        found_id = _library_named(root, rest)
        if found_id:
            return library_ref(found_id, data_dir=root)
    if sep and head.casefold() == "drive" and rest:
        found_id = _drive_named(root, rest)
        if found_id:
            return drive_ref(found_id, data_dir=root)
    if said.startswith("data/"):
        rel = _data_file(root, said)
        if rel:
            return file_ref(rel, data_dir=root)
    if _is_citation(said):
        return citation_ref(said)
    return {"text": mask_text(said)[0]}


def refs_from_strings(strings: Any, *, data_dir: Path | None = None) -> list[dict[str, Any]]:
    """The free-text evidence strings of an older store as references, in order: a ``DocRef`` for each string that
    names a document jason can show (the module doc), ``{command}`` for a ``jason ...`` command, and ``{text}`` (masked)
    for anything else. Never a guess: a name that matches no file, or several, stays text."""
    if isinstance(strings, str):
        strings = [strings]
    root = _root(data_dir)
    return [ref_from_string(str(s), data_dir=root) for s in strings or () if str(s or "").strip()]


__all__ = ["DOC_KINDS", "FILE_SOURCES", "LEVELS", "citation_ref", "doc_ref", "drive_ref", "file_ref", "library_ref",
           "ref_from_string", "refs_from_strings", "submission_ref"]
