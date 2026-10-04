"""The governing documents source: each of the association's governing documents with the copies a screen previews.

``governing_documents(args)`` (``GET /api/governing-documents``) lists the profile's governing documents (the
declaration and its amendments, ``Community.ccrs``, and the documents others cite, ``Community.citable_documents``),
each once, with:

- ``driveCopy``: the Drive file the specification binds it to (a working copy: a Google Doc, or a stored PDF), as a
  document reference (``drive:<id>``, source "Drive copy"), previewed as jason's copy (``jason.tasks.drive_copies``);
- ``recordedCopy``: the recorded or adopted PDF on disk under the data folder (``RECORDED_FOLDERS``), as a document
  reference (``file:<path>``, source "Recorded copy"), previewed as a page-1 thumbnail (``GET /api/thumb?path=``). A
  recorded instrument's PDF is the copy that governs; the Drive Doc is a working copy (AGENTS.md, "Recite the version
  that governs").

Each reference has the shape docs/console/doc-component.md names (``DocRef``: ``address``, ``document``, ``name``,
``kind``, ``level``, ``source``, ``readAt``, ``size``, ``thumb``, ``original``, ``refreshable``, ``stale``): never a raw
URL into data/ or an absolute path.

A PDF is matched to a document by the Drive id its text extract's header names (``<name>.pdf.md``, ``- drive_id:``),
else by its name (the document's title, with or without ``.pdf``), else by the recording number in its name. A PDF in
those folders that no document claims is a row of its own, its kind by the profile's kind rules (or none).

**Levels.** Each row's level is the higher of its recorded copy's (``jason.web.access.level_of_path``) and its Drive
file's (``drive_copies.level_of``). A confidential row (P3) is held back unless the person's private view is open
(``heldBack``); P4 is never listed.

Reads disk and the profile only; nothing reaches Drive, PayHOA, or the county.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

Args = dict[str, str]

# Where the association's recorded governing documents are kept as PDFs, under the data folder.
RECORDED_FOLDERS = ("artifacts/site-docs/governing_documents", "governing")
_DRIVE_ID = re.compile(r"^- drive_id:\s*`?([A-Za-z0-9_-]{10,200})`?\s*$", re.MULTILINE)
_LEVELS = ("P0", "P1", "P2", "P3", "P4")
RECORDED_COPY = "Recorded copy"                # the copies' sources, as docs/console/doc-component.md names them
DRIVE_COPY = "Drive copy"
CAVEATS = (
    "A recorded instrument's PDF is the copy that governs; a Google Doc in Drive is a working copy. Recite the version "
    "in force on the date that matters.",
    "jason's copies are read from disk; reading a Drive file again is a person's click (Read from Drive), never on load.",
)
MIMES = {"application/vnd.google-apps.document": "doc", "application/vnd.google-apps.spreadsheet": "sheet",
         "application/vnd.google-apps.presentation": "slides", "application/pdf": "pdf"}


def _iso(value: Any) -> str:
    return value.isoformat() if isinstance(value, date) else str(value or "")


def _fold(text: str) -> str:
    stem = re.sub(r"\.pdf$", "", str(text or "").strip(), flags=re.IGNORECASE)
    return " ".join(re.sub(r"[^0-9a-z]+", " ", stem.casefold()).split())


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").casefold()).strip("-")[:60] or "document"


def _kind_value(kind: Any) -> str:
    return str(getattr(kind, "value", kind) or "")


def _drive_kind(doc_id: str, title: str, file_kind: Any, listing: dict[str, dict[str, Any]]) -> str:
    """``doc``, ``sheet``, ``slides``, ``pdf``, or ``drive``: the catalog's type when it lists the file, else the
    specification's file kind, a ``.pdf`` title being a stored PDF."""
    mime = str((listing.get(doc_id) or {}).get("mimeType") or "")
    if mime in MIMES:
        return MIMES[mime]
    if mime.startswith("image/"):
        return "image"
    if str(title).lower().endswith(".pdf"):
        return "pdf"
    word = _kind_value(file_kind)
    return {"google_doc": "doc", "google_sheet": "sheet"}.get(word, "doc" if not word else "drive")


def _row(key: str, title: str, kind: str, drive_id: str, drive_kind: str, **dates: str) -> dict[str, Any]:
    return {"key": key, "title": title, "kind": kind, "kindWord": kind.replace("_", " "),
            "recorded": dates.get("recorded", ""), "adopted": dates.get("adopted", ""),
            "written": dates.get("written", ""), "number": dates.get("number", ""),
            "driveId": drive_id, "driveKind": drive_kind if drive_id else "", "recordedCopy": None,
            "names": [], "ids": {drive_id} - {""}, "level": "P0"}


def disk_names(root: Path) -> dict[str, set[str]]:
    """The names the exports on disk give each Drive file: a ``.md`` in ``RECORDED_FOLDERS`` whose header names its
    ``drive_id`` (a Doc's export, a PDF's extract) names that file by its own name, folded."""
    out: dict[str, set[str]] = {}
    base = Path(root)
    for folder in RECORDED_FOLDERS:
        where = base / folder
        if not where.is_dir():
            continue
        for md in where.glob("*.md"):
            try:
                head = md.read_text(encoding="utf-8", errors="replace")[:2000]
            except OSError:
                continue
            found = _DRIVE_ID.search(head)
            name = _fold(re.sub(r"\.md$", "", md.name, flags=re.IGNORECASE))
            if found and name:
                out.setdefault(found.group(1), set()).add(name)
    return out


def _merge(row: dict[str, Any], other: dict[str, Any]) -> None:
    """``other`` (a document others cite) into ``row`` (an instrument) when they are one document under two Drive
    files: the Doc is the working copy a preview reads, a stored PDF the recorded one."""
    row["ids"] |= other["ids"]
    row["names"] = list(dict.fromkeys(row["names"] + other["names"]))
    if other["driveId"] and (not row["driveId"] or (row["driveKind"] == "pdf" and other["driveKind"] != "pdf")):
        row["driveId"], row["driveKind"] = other["driveId"], other["driveKind"]
    for k in ("written", "adopted", "recorded", "number"):
        row[k] = row[k] or other[k]
    if other["title"] and other["key"]:
        row["title"], row["key"] = other["title"], other["key"]


def _profile_rows(community: Any, listing: dict[str, dict[str, Any]], names: dict[str, set[str]]) -> list[dict[str, Any]]:
    """The declaration and its amendments in the order they apply, then each other document others cite, once each:
    a citable document bound to the same Drive file as an instrument, or named the same on disk, is that instrument's
    row."""
    rows: list[dict[str, Any]] = []
    try:
        citable = tuple(community.citable_documents() or ())
    except Exception:  # noqa: BLE001 - a profile that sets none lists none
        citable = ()
    try:
        instruments = tuple(community.ccrs.instruments)
    except Exception:  # noqa: BLE001 - a profile with no declaration bound lists the rest
        instruments = ()
    for doc in instruments:
        drive_id = str(getattr(doc, "drive_id", "") or "")
        title = str(getattr(doc, "title", "") or "")
        row = _row(_slug(re.sub(r"\.pdf$", "", title, flags=re.IGNORECASE)), title,
                   _kind_value(getattr(doc, "document_kind", None)), drive_id,
                   _drive_kind(drive_id, title, getattr(doc, "kind", None), listing),
                   recorded=_iso(getattr(doc, "recorded", None)), adopted=_iso(getattr(doc, "adopted", None)),
                   number=str(getattr(doc, "recorder_number", "") or ""))
        row["names"] = [n for n in dict.fromkeys([_fold(title), *sorted(names.get(drive_id, ()))]) if n]
        rows.append(row)
    for c in citable:
        drive_id = str(getattr(c, "drive_id", "") or "")
        title = str(getattr(c, "title", "") or "")
        row = _row(str(getattr(c, "key", "") or _slug(title)), title, _kind_value(getattr(c, "kind", None)), drive_id,
                   _drive_kind(drive_id, title, None, listing), written=str(getattr(c, "written", "") or ""))
        row["names"] = [n for n in dict.fromkeys([_fold(title), *(_fold(a) for a in getattr(c, "aliases", ()) or ()),
                                                  *sorted(names.get(drive_id, ()))]) if n]
        same = next((r for r in rows[:len(instruments)] if (drive_id and drive_id in r["ids"])
                     or set(r["names"]) & set(row["names"])), None)
        if same is not None:
            _merge(same, row)
        else:
            rows.append(row)
    return rows


def _extract_drive_id(pdf: Path) -> str:
    sidecar = pdf.with_name(pdf.name + ".md")
    try:
        head = sidecar.read_text(encoding="utf-8", errors="replace")[:2000] if sidecar.is_file() else ""
    except OSError:
        return ""
    found = _DRIVE_ID.search(head)
    return found.group(1) if found else ""


def recorded_pdfs(root: Path) -> list[dict[str, Any]]:
    """The PDFs in ``RECORDED_FOLDERS`` under ``root``: ``{path, name, size, extract, driveId}``, by name."""
    out: list[dict[str, Any]] = []
    base = Path(root).resolve()
    for folder in RECORDED_FOLDERS:
        where = base / folder
        if not where.is_dir():
            continue
        for pdf in sorted(where.glob("*.pdf"), key=lambda p: p.name.casefold()):
            try:
                if not pdf.is_file() or not pdf.resolve().is_relative_to(base):
                    continue
                size = pdf.stat().st_size
            except OSError:
                continue
            out.append({"path": pdf.resolve().relative_to(base).as_posix(), "name": pdf.name, "size": size,
                        "extract": pdf.with_name(pdf.name + ".md").is_file(), "driveId": _extract_drive_id(pdf)})
    return out


def _claim(rows: list[dict[str, Any]], pdf: dict[str, Any]) -> dict[str, Any] | None:
    """The row a recorded PDF belongs to: by the Drive id its extract names, by name, then by recording number."""
    open_rows = [r for r in rows if r["recordedCopy"] is None]
    if pdf["driveId"]:
        hit = next((r for r in open_rows if pdf["driveId"] in r["ids"]), None)
        if hit is not None:
            return hit
    name = _fold(pdf["name"])
    hit = next((r for r in open_rows if name and name in r["names"]), None)
    if hit is not None:
        return hit
    return next((r for r in open_rows if r["number"] and r["number"] in pdf["name"]), None)


def _classify(community: Any, name: str) -> str:
    try:
        from jason.community.documents import classify_document

        return _kind_value(classify_document(name, tuple(community.kind_rules() or ())))
    except Exception:  # noqa: BLE001 - a profile without kind rules leaves the kind unknown
        return ""


def _mtime(path: Path) -> str:
    from datetime import datetime, timezone

    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    except OSError:
        return ""


def recorded_ref(root: Path, pdf: dict[str, Any]) -> dict[str, Any]:
    """The recorded PDF as a document reference (docs/console/doc-component.md, ``DocRef``): its ``file:`` address
    under the data folder, its level by ``jason.web.access.level_of_path``, and a thumbnail the server makes from disk.
    Never an absolute path or a URL."""
    from jason.web.access import level_of_path

    return {"address": f"file:{pdf['path']}", "document": "pdf", "name": pdf["name"], "kind": "pdf",
            "level": level_of_path(pdf["path"], root).value, "source": RECORDED_COPY,
            "readAt": _mtime(Path(root) / pdf["path"]), "size": pdf["size"], "thumb": True}


def drive_ref(root: Path, row: dict[str, Any], catalog: dict[str, dict[str, Any]], synced_at: str) -> dict[str, Any]:
    """The Drive file as a document reference: its ``drive:`` address, jason's copy's age and thumbnail when it keeps
    one, the original in Google, the refresher, and "Changed in Drive since this copy" when the catalog says so."""
    from jason.approvals.evidence import DRIVE_CHANGED, _against_drive, drive_link
    from jason.tasks import drive_copies

    drive_id = row["driveId"]
    record = drive_copies.read_record(root, drive_id) or {}
    listed = catalog.get(drive_id) or {}
    try:
        level = drive_copies.level_of(root, drive_id)
    except (OSError, ValueError):
        level = "P2"
    ref: dict[str, Any] = {
        "address": f"drive:{drive_id}", "name": str(record.get("name") or listed.get("name") or row["title"]),
        "kind": "pdf", "level": level, "source": DRIVE_COPY,
        "thumb": drive_copies.thumbnail(root, drive_id) is not None,
        "original": {"url": drive_link(drive_id, str(record.get("mimeType") or listed.get("mimeType") or ""),
                                       str(record.get("webViewLink") or ""), str(listed.get("link") or "")),
                     "label": "Open in Google"},
        "refreshable": {"system": "Google Drive", "what": "Export this file again from Drive"}}
    if record.get("readAt"):
        ref["readAt"] = str(record["readAt"])
    if record and listed and _against_drive(record, listed, synced_at)[0]:
        ref["stale"] = DRIVE_CHANGED
    return ref


def listing(community: Any, root: Path, *, private: bool = False) -> dict[str, Any]:
    """The governing documents of ``community`` with their copies under ``root`` (the module doc). ``private`` is the
    person's private view, open: confidential rows are listed too, marked.

    Each row: ``{key, title, kind, kindWord, recorded, adopted, written, number, driveKind, recordedCopy, driveCopy,
    level, confidential}``; ``recordedCopy`` and ``driveCopy`` are document references (``DocRef``, sources "Recorded
    copy" and "Drive copy") or null, and ``level`` is the higher of theirs."""
    from jason.tasks import drive_copies

    root = Path(root)
    synced_at, catalog = drive_copies.catalog(root)
    rows = _profile_rows(community, catalog, disk_names(root))
    for pdf in recorded_pdfs(root):
        row = _claim(rows, pdf)
        if row is None:
            title = re.sub(r"\.pdf$", "", pdf["name"], flags=re.IGNORECASE)
            row = _row(f"file-{_slug(title)}", title, _classify(community, pdf["name"]), "", "")
            rows.append(row)
        row["recordedCopy"] = recorded_ref(root, pdf)
    shown: list[dict[str, Any]] = []
    held = 0
    for row in rows:
        row.pop("names", None)
        row.pop("ids", None)
        drive_id = row.pop("driveId")
        row["driveCopy"] = (drive_ref(root, {**row, "driveId": drive_id}, catalog, synced_at)
                            if drive_id and drive_copies.valid_id(drive_id) else None)
        levels = ["P0"] + [c["level"] for c in (row["recordedCopy"], row["driveCopy"]) if c]
        row["level"] = max(levels, key=lambda v: _LEVELS.index(v) if v in _LEVELS else len(_LEVELS))
        row["confidential"] = row["level"] == "P3"
        if row["level"] == "P4" or (row["confidential"] and not private):
            held += 1
            continue
        shown.append(row)
    out: dict[str, Any] = {"found": True, "count": len(shown), "rows": shown, "heldBack": held,
                           "folders": list(RECORDED_FOLDERS), "caveats": list(CAVEATS)}
    if held:
        out["note"] = f"{held} held back (confidential); open the private view to see them."
    if not shown and not held:
        out["note"] = ("No governing document is bound in the specification and none is on disk under "
                       + " or ".join(RECORDED_FOLDERS) + ".")
    return out


def _private() -> bool:
    try:
        from jason.web.access import private_open

        return private_open()
    except Exception:  # noqa: BLE001 - outside a request, or sign-in not set up: the private view is closed
        return False


def governing_documents(args: Args) -> dict[str, Any]:
    """``GET /api/governing-documents``: the active profile's governing documents with their recorded and Drive copies."""
    from jason.community import community
    from jason.config import data_dir

    del args
    return listing(community(), data_dir(), private=_private())


__all__ = ["CAVEATS", "DRIVE_COPY", "RECORDED_COPY", "RECORDED_FOLDERS", "drive_ref", "governing_documents", "listing",
           "recorded_pdfs", "recorded_ref"]
