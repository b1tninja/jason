"""A legal case's file from Drive, on disk and as its own confidential catalog in the passage index.

A case in the specification (the profile's ``legal_cases()``) with a ``drive_folder`` has a case file: every Drive file
under that folder, as the last ``jason drive --sync`` listed it. ``fetch`` downloads the readable files into
``data/cases/<key>/files`` (a Google Doc as PDF, a caption transcript as text) and writes ``manifest.json`` with every file
and what became of it. A file whose name matches the case's ``held_back`` globs (medical and veterinary records) is not
downloaded unless a person passes ``include_held``, and a copy from an earlier run that included it is removed.
Images, recordings, archives, and shortcuts are listed, not taken.

``index_sources`` gives each such case its own catalog in the passage index (``case-<key>``), which ``jason index
--build`` includes: confidential, so a search sees it only when it names the catalog or asks for confidential files,
with the standing ``evidence`` (neither the association's record nor the law). The index reads the ``.md`` and ``.txt``
files only (the caption transcripts, and any text extract); a PDF, Word file, or e-mail without one is on disk but
not searched.
Nothing in Drive is changed.
"""

from __future__ import annotations

import fnmatch
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


CASES_DIR = "cases"
_DOCUMENT = "application/vnd.google-apps.document"
_SHORTCUT = "application/vnd.google-apps.shortcut"
# Read as they are; a caption transcript is text under another name.
_TAKEN = (".pdf", ".txt", ".md", ".docx", ".doc", ".csv", ".xlsx", ".pptx", ".html", ".htm", ".eml")
_AS_TEXT = (".vtt", ".srt")


def case_dir(data_dir: Path, case: Any) -> Path:
    return Path(data_dir) / CASES_DIR / case.key


CATALOG_PREFIX = "case-"


def catalog_name(case: Any) -> str:
    return f"{CATALOG_PREFIX}{case.key}"


def is_case_catalog(name: str) -> bool:
    return name.strip().lower().startswith(CATALOG_PREFIX)


def index_sources(cases: tuple) -> tuple:
    """One confidential ``IndexSource`` per case with a Drive folder: its fetched files' text, as catalog case-<key>."""
    from jason.community.passage_index import IndexSource, Standing

    return tuple(IndexSource(catalog_name(case), f"{CASES_DIR}/{case.key}/files", Standing.EVIDENCE, confidential=True)
                 for case in cases if getattr(case, "drive_folder", ""))


def is_held(name: str, case: Any) -> bool:
    return any(fnmatch.fnmatchcase(name, glob) for glob in case.held_back)


def _safe(part: str) -> str:
    """A Drive name as a Windows file name: no reserved characters, no trailing dots or spaces."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", part).rstrip(". ") or "_"


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
    manifest_path = root / "manifest.json"
    before = {r["id"]: r for r in json.loads(manifest_path.read_text(encoding="utf-8"))["files"]} if manifest_path.is_file() else {}
    counts = {"files": 0, "downloaded": 0, "kept": 0, "heldBack": 0, "listed": 0, "errors": 0}
    rows = plan(data_dir, case)
    for row in rows:
        counts["files"] += 1
        if row["action"] == "listed":
            counts["listed"] += 1
            continue
        target = files / row["local"]
        if row["heldBack"] and not include_held:
            # jason's own copy from a run that included it goes, so the index cannot take it; Drive keeps the file.
            if target.is_file():
                target.unlink()
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
    manifest_path.write_text(json.dumps({"case": case.key, "caseNumber": case.case_number, "driveFolder": case.drive_folder,
                                         "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                         "includeHeld": include_held, "files": rows}, indent=1), encoding="utf-8")
    return counts


__all__ = ["CASES_DIR", "CATALOG_PREFIX", "case_dir", "catalog_name", "fetch", "index_sources", "is_case_catalog",
           "is_held", "plan"]
