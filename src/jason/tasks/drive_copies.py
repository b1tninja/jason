"""jason's own copies of Drive files: exported on a person's click, kept on disk, read from disk ever after.

docs/console/documents.md ("Google Docs, Sheets, and Slides", "Drive PDFs and images"). The console never frames a
private Google file; it shows jason's copy, read through the Drive API with the association's OAuth (drive.readonly)
when a person asks (``jason.approvals.evidence``'s ``drive:<id>`` refresher). Nothing here runs on a page load.

**The store.** ``data/drive/copies/``, one set of files a Drive file:

- ``<id>.pdf``: a Doc, Sheet, or Slides file exported as PDF (``files.export``), or a stored PDF (``files.get?alt=media``);
- ``<id>.md``: a Doc's text, exported as Markdown (``text/markdown``), or as plain text when Google refuses Markdown;
- ``<id>.csv``: a Sheet's first sheet (``text/csv``);
- ``<id>.image.png`` (or ``.jpg``, ``.gif``, ``.webp``): a stored image's bytes;
- ``<id>.png`` (or ``<id>.jpg``): the file's thumbnail, read from its short-lived ``thumbnailLink`` with jason's token
  at once, and kept; none when Drive gives none;
- ``<id>.json``: the record ``{readAt, via, by, modifiedTime, mimeType, name, md5?, sizes, webViewLink, textMime?,
  reused?}``. ``sizes`` names each file kept by its extension.

A stored PDF or image the Drive holdings (``drive/holdings.json``) already place on disk (``elsewhere``: a library file,
an email attachment) is not downloaded again: the record names that copy (``reused``, a path under the data folder).

**Restrictions.** A file whose owner turned off downloading, printing, and copying (``capabilities.canDownload`` false,
``copyRequiresWriterPermission``, or ``downloadRestrictions``) is refused (``CopyRefused``): jason keeps no copy, and
the console links the original. Google exports at most 10 MB; a larger file is refused the same way, "too large to
export; open it in Google".

**Writing.** Under the store lock ``drive-copies`` (``jason.locks``); each file is written to a temporary name and then
replaced, the record last, so a reader never sees half a copy. A copy's earlier files the new read did not produce are
removed.

**Levels.** ``level_of``: a file the holdings mark confidential is P3; a Doc a saved hearing names (its notice Doc,
``zoom/hearings.json``'s ``noticeDoc``) is P3, a member's discipline, whatever folder it sits in; a letter template's
Doc (the profile's templates) is P0; a file the holdings place under one of the specification's Drive roots (a path
rule), not confidential, is P0, as a library file is; any other is P2, closed (``jason.web.access``'s rule for a path
no row places). While the hearings cannot be read, no file is P0: a P0 file is P2 until they can.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jason import limits

COPIES = Path("drive") / "copies"
HOLDINGS = Path("drive") / "holdings.json"
HEARINGS = Path("zoom") / "hearings.json"      # jason hearing's plans; a plan's notice Doc is P3
CATALOG = Path("drive") / "files.json"
LOCK = "drive-copies"                          # the store lock an export holds while it writes one copy
EXPORT_LIMIT = 10 * 1024 * 1024                # Google's export limit

DOC = "application/vnd.google-apps.document"
SHEET = "application/vnd.google-apps.spreadsheet"
SLIDES = "application/vnd.google-apps.presentation"
PDF = "application/pdf"
IMAGES = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}
THUMBS = ("png", "jpg")
# Every extension a copy may have, so a fresh copy can remove what an earlier one left.
EXTENSIONS = ("pdf", "md", "csv", "image.png", "image.jpg", "image.gif", "image.webp", *THUMBS)

FIELDS = ("id,name,mimeType,size,md5Checksum,modifiedTime,webViewLink,thumbnailLink,hasThumbnail,"
          "capabilities(canDownload,canCopy,canEdit),copyRequiresWriterPermission,downloadRestrictions")

GOOGLE_SIGN_IN = ("Google is not signed in for jason's Drive access; run `jason drive --sync --interactive` in a "
                  "terminal (docs/setup.md), then read it again.")
TOO_LARGE = "{name} is too large to export (Google exports up to 10 MB); open it in Google."
CAVEAT = ("jason's copy, exported from Drive when a person last read it; the file in Drive governs, and editing "
          "happens there.")

_ID = re.compile(r"^[A-Za-z0-9_-]{10,200}$")


class CopyRefused(RuntimeError):
    """jason keeps no copy of this file, and why, in words for the person: the file forbids copies, it is too large to
    export, or it is a kind jason does not copy."""


def valid_id(file_id: str) -> bool:
    """Whether ``file_id`` looks like a Drive id: letters, digits, ``-`` and ``_`` only, so it never names a path."""
    return bool(_ID.match(str(file_id or "")))


def _need_id(file_id: str) -> str:
    if not valid_id(file_id):
        raise ValueError(f"{str(file_id)[:40] or '(none)'} is not a Drive file id")
    return file_id


def data_root() -> Path:
    """The active profile's data folder, as the evidence reads it (``jason.config.data_dir``)."""
    from jason.config import data_dir

    return data_dir()


def copies_dir(root: Path) -> Path:
    return Path(root) / COPIES


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- reading what is kept ------------------------------------------------------------------------------------------------

def read_record(root: Path, file_id: str) -> dict[str, Any] | None:
    """The copy's record (``<id>.json``), or None when there is none or it cannot be read."""
    if not valid_id(file_id):
        return None
    path = copies_dir(root) / f"{file_id}.json"
    try:
        got = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) else None


def kept(root: Path, file_id: str) -> dict[str, Path]:
    """The files kept for a copy, by extension (``pdf``, ``md``, ``csv``, ``image.png``, ``png`` the thumbnail...), each on
    disk."""
    if not valid_id(file_id):
        return {}
    folder = copies_dir(root)
    return {ext: folder / f"{file_id}.{ext}" for ext in EXTENSIONS if (folder / f"{file_id}.{ext}").is_file()}


def thumbnail(root: Path, file_id: str) -> Path | None:
    """The kept thumbnail, or None."""
    files = kept(root, file_id)
    return next((files[t] for t in THUMBS if t in files), None)


def _json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (OSError, ValueError):
        return None


def holdings_row(root: Path, file_id: str) -> dict[str, Any] | None:
    """The Drive holdings' row for the file (``jason drive``'s ``drive/holdings.json``), or None."""
    got = _json_file(Path(root) / HOLDINGS)
    rows = got.get("rows") if isinstance(got, dict) else None
    return next((r for r in rows or () if isinstance(r, dict) and r.get("id") == file_id), None)


def catalog(root: Path) -> tuple[str, dict[str, dict[str, Any]]]:
    """The Drive catalog's last sync (``syncedAt``) and its files by id (``drive/files.json``, ``jason drive --sync``)."""
    got = _json_file(Path(root) / CATALOG)
    if not isinstance(got, dict):
        return "", {}
    files = {str(f.get("id")): f for f in got.get("files") or () if isinstance(f, dict) and f.get("id")}
    return str(got.get("syncedAt") or ""), files


_HEARING_IDS: dict[str, tuple[tuple[int, int], frozenset[str] | None]] = {}


def hearing_ids(root: Path) -> frozenset[str] | None:
    """The Drive ids the saved hearings name (``zoom/hearings.json``: each plan's ``noticeDoc``, and any other
    ``...Doc`` it keeps with an ``id``), read once a version of the file; none when there are no hearings; None when
    the file is there but cannot be read."""
    path = Path(root) / HEARINGS
    try:
        stat = path.stat()
    except FileNotFoundError:
        return frozenset()
    except OSError:
        return None
    stamp = (stat.st_mtime_ns, stat.st_size)
    cached = _HEARING_IDS.get(str(path))
    if cached is not None and cached[0] == stamp:
        return cached[1]
    found: frozenset[str] | None
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("hearings") or []
        ids: set[str] = set()
        for row in rows:
            for key, value in (row.items() if isinstance(row, dict) else ()):
                if str(key).endswith("Doc") and isinstance(value, dict) and valid_id(str(value.get("id") or "")):
                    ids.add(str(value["id"]))
        found = frozenset(ids)
    except (OSError, ValueError, AttributeError, TypeError):
        found = None
    _HEARING_IDS[str(path)] = (stamp, found)
    return found


def confidential(root: Path, file_id: str) -> bool:
    """Whether the file's copy is held back outside the private view: the holdings mark it confidential, or a saved
    hearing names it."""
    if (holdings_row(root, file_id) or {}).get("confidential"):
        return True
    return file_id in (hearing_ids(root) or frozenset())


def _template_ids(root: Path) -> frozenset[str]:
    """The Drive ids of the profile's letter templates (built or adopted), or none when the profile cannot be read."""
    try:
        from jason.community import community
        from jason.community.profile import profile_name
        from jason.tasks.template_gen import load_state, templates

        state = load_state(Path(root), profile_name())
        return frozenset(t.drive_id for t in templates(community(), state) if t.drive_id)
    except Exception:  # noqa: BLE001 - a profile that cannot be read places no template
        return frozenset()


def level_of(root: Path, file_id: str) -> str:
    """The data level of a Drive file's copy (``"P0"``, ``"P2"``, ``"P3"``): confidential by the holdings is P3; a Doc
    a saved hearing names is P3; a letter template is P0; a file under a Drive root's path rule is P0, as a library
    file is; any other is P2. While the hearings cannot be read, P0 is P2 (closed)."""
    row = holdings_row(root, file_id)
    if row is not None and row.get("confidential"):
        return "P3"
    hearings = hearing_ids(root)
    if hearings is not None and file_id in hearings:
        return "P3"
    if file_id in _template_ids(root) or (row is not None and row.get("pathRule")):
        return "P0" if hearings is not None else "P2"
    return "P2"


# --- restrictions ------------------------------------------------------------------------------------------------------

def restriction(meta: dict[str, Any]) -> str:
    """Why the file forbids a copy, from its metadata, or "" when it does not."""
    caps = meta.get("capabilities") if isinstance(meta.get("capabilities"), dict) else {}
    if caps.get("canDownload") is False:
        return "its owner has turned off downloading it"
    if meta.get("copyRequiresWriterPermission"):
        return "its owner has turned off copying, printing, and downloading it for readers"
    limits = meta.get("downloadRestrictions") if isinstance(meta.get("downloadRestrictions"), dict) else {}
    for key in ("itemDownloadRestriction", "effectiveDownloadRestrictionWithContext"):
        said = limits.get(key) if isinstance(limits.get(key), dict) else {}
        if said.get("restrictedForReaders") or said.get("restrictedForWriters"):
            return "Drive restricts downloading it"
    return ""


# --- writing a copy ----------------------------------------------------------------------------------------------------

def _write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _image_ext(data: bytes) -> str:
    """``png``, ``jpg``, ``gif``, or ``webp`` by the bytes' own signature (never by what a server said), else ""."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return ""


def _reusable(root: Path, file_id: str, mime: str) -> str:
    """A copy the holdings already place on disk for a stored PDF or image (``elsewhere``), as a path under the data
    folder, or ""."""
    if mime != PDF and mime not in IMAGES:
        return ""
    row = holdings_row(root, file_id) or {}
    base = Path(root).resolve()
    for place in row.get("elsewhere") or ():
        if not isinstance(place, dict) or not place.get("where"):
            continue
        where = str(place["where"]).replace("\\", "/")
        rel = f"library/files/{where}" if place.get("channel") == "PayHOA library" else where
        path = (base / rel).resolve()
        try:
            if path.is_relative_to(base) and path.is_file():
                return path.relative_to(base).as_posix()
        except OSError:
            continue
    return ""


def _export(drive: Any, file_id: str, mime: str, name: str) -> bytes:
    from jason.google.errors import GoogleExportTooLarge

    try:
        data = drive.export_file(file_id, mime)
    except GoogleExportTooLarge as exc:
        raise CopyRefused(TOO_LARGE.format(name=name)) from exc
    if len(data) > EXPORT_LIMIT:
        raise CopyRefused(TOO_LARGE.format(name=name))
    return data


def _text(drive: Any, file_id: str, name: str) -> tuple[bytes, str]:
    """A Doc's text: Markdown, or plain text when Google will not export Markdown."""
    from jason.google.errors import GoogleHttpError

    try:
        return _export(drive, file_id, "text/markdown", name), "text/markdown"
    except GoogleHttpError as exc:
        if exc.status not in (400, 403, 415):
            raise
    return _export(drive, file_id, "text/plain", name), "text/plain"


def _thumb(drive: Any, meta: dict[str, Any]) -> tuple[str, bytes] | None:
    """The thumbnail behind ``thumbnailLink``, read now (the link is short-lived); None when there is none or it cannot
    be read (a copy without a thumbnail is still a copy)."""
    link = str(meta.get("thumbnailLink") or "")
    if not link:
        return None
    try:
        data, said = drive.fetch_link(link)
    except Exception:  # noqa: BLE001 - a thumbnail is a convenience: none, rather than no copy
        return None
    del said
    ext = _image_ext(data)
    return (ext, data) if ext in THUMBS else None


def export(drive: Any, root: Path, file_id: str, *, via: str = "", by: str = "") -> dict[str, Any]:
    """Read one Drive file through ``drive`` (``GoogleDrive``, read-only) and keep jason's copy of it in
    ``data/drive/copies``: a Doc as PDF, its text, and a thumbnail; a Sheet as PDF and its first sheet as CSV; Slides as
    PDF; a stored PDF or image as its bytes, or the copy the holdings already place on disk, without a download.

    Refuses (``CopyRefused``, words for the person) a file that forbids copies, one too large to export, and a kind
    jason does not copy; a missing Google sign-in raises as it is (``GoogleAuthRequired``). Writes under the store lock,
    each file atomically, the record last. Returns the record."""
    from jason.locks import Resource, hold

    file_id = _need_id(file_id)
    meta = drive.file_metadata(file_id, FIELDS)
    name = str(meta.get("name") or file_id)
    mime = str(meta.get("mimeType") or "")
    why = restriction(meta)
    if why:
        raise CopyRefused(f"{name}: {why}, so jason keeps no copy; open it in Google.")
    files: dict[str, bytes] = {}
    record: dict[str, Any] = {"readAt": "", "via": via, "by": by, "modifiedTime": str(meta.get("modifiedTime") or ""),
                              "mimeType": mime, "name": name, "webViewLink": str(meta.get("webViewLink") or "")}
    if meta.get("md5Checksum"):
        record["md5"] = str(meta["md5Checksum"])
    if mime == DOC:
        files["pdf"] = _export(drive, file_id, PDF, name)
        files["md"], record["textMime"] = _text(drive, file_id, name)
    elif mime == SHEET:
        files["pdf"] = _export(drive, file_id, PDF, name)
        files["csv"] = _export(drive, file_id, "text/csv", name)
    elif mime == SLIDES:
        files["pdf"] = _export(drive, file_id, PDF, name)
    elif mime == PDF or mime in IMAGES:
        reused = _reusable(root, file_id, mime)
        if reused:
            record["reused"] = reused
        else:
            try:
                limits.check("fetch.max_bytes", int(meta.get("size") or 0))
            except limits.LimitReached as over:
                raise CopyRefused(over.words) from over
            data = drive.download_bytes(file_id)
            if mime == PDF:
                if not data.startswith(b"%PDF"):
                    raise CopyRefused(f"{name}: Drive's bytes are not a PDF, so jason keeps no copy; open it in "
                                      "Google.")
                files["pdf"] = data
            else:
                ext = _image_ext(data)
                if not ext:
                    raise CopyRefused(f"{name}: Drive's bytes are not an image jason shows; open it in Google.")
                files[f"image.{ext}"] = data
    else:
        raise CopyRefused(f"{name} is a kind jason does not copy (a Doc, Sheet, Slides file, PDF, or image); open it "
                          "in Google.")
    thumb = _thumb(drive, meta)
    if thumb is not None:
        files[thumb[0]] = thumb[1]
    folder = copies_dir(root)
    with hold(Resource.STORE, LOCK, timeout=120, purpose=f"drive copy {file_id}"):
        folder.mkdir(parents=True, exist_ok=True)
        for ext, data in files.items():
            _write(folder / f"{file_id}.{ext}", data)
        for ext in EXTENSIONS:
            stale = folder / f"{file_id}.{ext}"
            if ext not in files and stale.is_file():
                stale.unlink()
        record["readAt"] = _now()
        record["sizes"] = {ext: len(data) for ext, data in files.items()}
        _write(folder / f"{file_id}.json", (json.dumps(record, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
               .encode("utf-8"))
    return record


__all__ = ["CAVEAT", "COPIES", "CopyRefused", "EXPORT_LIMIT", "FIELDS", "GOOGLE_SIGN_IN", "LOCK", "TOO_LARGE",
           "catalog", "confidential", "copies_dir", "data_root", "export", "holdings_row", "kept", "level_of",
           "read_record", "restriction", "thumbnail", "valid_id"]
