"""A legal case's file from Drive, on disk and as its own AnythingLLM catalog.

A case in the specification (``mystique/cases.py``) with a ``drive_folder`` has a case file: every Drive file under that
folder, as the last ``jason drive --sync`` listed it. ``fetch`` downloads the files AnythingLLM can read into
``data/cases/<key>/files`` (a Google Doc as PDF, a caption transcript as text) and writes ``manifest.json`` with every file
and what became of it. A file whose name matches the case's ``held_back`` globs (medical and veterinary records) is not
downloaded unless a person passes ``include_held``. Images, recordings, archives, and shortcuts are listed, not taken.

``case_catalogs`` gives each such case its own catalog: its own folder and workspace, never the shared Mystique
workspace, and synced only when named. Titles carry the case number, so a case file is never taken for, or moved
out of, the association's records. Nothing in Drive is changed.
"""

from __future__ import annotations

import fnmatch
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jason.tasks.anythingllm_sync import Catalog, Root, Source

CASES_DIR = "cases"
_DOCUMENT = "application/vnd.google-apps.document"
_SHORTCUT = "application/vnd.google-apps.shortcut"
# Read as they are; a caption transcript is text under another name.
_TAKEN = (".pdf", ".txt", ".md", ".docx", ".doc", ".csv", ".xlsx", ".pptx", ".html", ".htm", ".eml")
_AS_TEXT = (".vtt", ".srt")


def case_dir(data_dir: Path, case: Any) -> Path:
    return Path(data_dir) / CASES_DIR / case.key


def catalog_name(case: Any) -> str:
    return f"case-{case.key}"


def case_catalogs(cases: tuple) -> tuple[Catalog, ...]:
    """One confidential catalog per case with a Drive folder."""
    return tuple(
        Catalog(
            catalog_name(case), catalog_name(case), f"Case {case.case_number or case.key}", "the association's case file",
            f"a file in the association's case file for {case.title} ({case.case_number or case.key}): evidence, pleadings, "
            "correspondence, and invoices gathered for the matter; confidential, for directors and counsel; not the "
            "association's record and not an authority",
            (Source(Root.DATA, f"{CASES_DIR}/{case.key}/files", "*", recursive=True, prefix=case.case_number or case.key,
                    relative_title=True),),
            shared=False, explicit=True, confidential=True,
        )
        for case in cases if getattr(case, "drive_folder", "")
    )


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
            # jason's own copy from a run that included it goes, so the catalog cannot take it; Drive keeps the file.
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


__all__ = ["CASES_DIR", "case_catalogs", "case_dir", "catalog_name", "fetch", "is_held", "plan"]
