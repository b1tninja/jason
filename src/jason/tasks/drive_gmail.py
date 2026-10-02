"""Which Drive files are saved copies of email attachments, and from which message.

Neither side records the link. A file saved from Gmail to Drive carries no source in its Drive metadata (no
description, properties, or app properties; its original file name is only its name), and the Gmail API gives an
attachment's name, type, size, and an id to fetch its bytes, with no mark that it was saved. The link is the content:

1. for each candidate Drive file, Gmail is searched for messages with an attachment of that name (``filename:``);
2. each such attachment is fetched (read-only) and its MD5 taken; the hashes are cached by message and name;
3. a Drive file whose MD5 equals an attachment's is a copy of it. When the Drive copy was created after the message
   arrived, it is a saved copy; when before, the message carried a file that was already in Drive.

The candidates are the Drive files with content (not Google Docs, Sheets, or Slides, which have no MD5): by default
those under no path rule and those with the same content in more than one folder, where a source says the most. The
result is ``data/drive/gmail-links.json``: each Drive file with the messages it matches (date, direction, domains,
subject), and each message's attachments that no Drive file holds.

Read-only on both sides. It saves nothing to Drive and changes no label in Gmail.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

LINKS = "gmail-links.json"
CACHE = "gmail-attachment-md5.json"
PERSONAL_HINT = ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com")


def _when(meta: dict[str, Any]) -> str:
    ms = int(meta.get("internalDate") or 0)
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(timespec="seconds") if ms else ""


def candidates(data_dir: Path, *, everything: bool = False) -> list[dict[str, Any]]:
    """The Drive files to look for in Gmail: with content, and (unless ``everything``) outside the path rules or duplicated."""
    from jason.tasks.drive_catalog import REPORT, drive_dir, load_files

    files = [f for f in load_files(data_dir) if f.get("md5")]
    if everything:
        return files
    report_path = drive_dir(data_dir) / REPORT
    rows = {r["id"]: r for r in json.loads(report_path.read_text(encoding="utf-8")).get("rows", [])} if report_path.is_file() else {}
    by_md5: dict[str, int] = {}
    for f in files:
        by_md5[f["md5"]] = by_md5.get(f["md5"], 0) + 1
    return [f for f in files if not (rows.get(f["id"]) or {}).get("pathRule") or by_md5[f["md5"]] > 1]


def link(gmail: Any, data_dir: Path, *, everything: bool = False, per_name: int = 25,
         log: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Match candidate Drive files to the email attachments of the same name by content; save and return the links."""
    from jason.tasks.drive_catalog import drive_dir

    say = log or (lambda _m: None)
    root = drive_dir(data_dir)
    cache_path = root / CACHE
    cache: dict[str, dict[str, Any]] = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    files = candidates(data_dir, everything=everything)
    names = sorted({f["name"] for f in files})
    say(f"{len(files)} candidate Drive files, {len(names)} distinct names")
    searched: set[str] = set(cache.get("__searched__", {}).get("names", []))
    for n, name in enumerate(names, 1):
        if name in searched:
            continue
        query = f'filename:"{name}"'
        for row in gmail.iter_messages(query, limit=per_name):
            meta = gmail.get_metadata(row["id"], headers=("From", "To", "Subject", "Date"))
            for part in meta["attachments"]:
                if part["name"].casefold() != name.casefold() or not part.get("attachmentId"):
                    continue
                key = f"{meta['id']}|{part['name']}"
                if key in cache:
                    continue
                data = gmail.get_attachment(meta["id"], part["attachmentId"])
                head = meta["headers"]
                cache[key] = {"messageId": meta["id"], "threadId": meta["threadId"], "at": _when(meta), "name": part["name"],
                              "md5": hashlib.md5(data).hexdigest(), "bytes": len(data), "sent": "SENT" in meta["labels"],
                              "from": head.get("From", ""), "to": head.get("To", ""), "subject": head.get("Subject", "")}
        searched.add(name)
        if n % 100 == 0:
            cache["__searched__"] = {"names": sorted(searched)}
            cache_path.write_text(json.dumps(cache), encoding="utf-8")
            say(f"  {n} of {len(names)} names searched")
    cache["__searched__"] = {"names": sorted(searched)}
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    return build(data_dir, files, cache)


def _party(value: str) -> str:
    """A sender or recipient as its domain only; a personal address is shown as "personal"."""
    host = value.rsplit("@", 1)[-1].strip(" >").lower() if "@" in value else ""
    return "personal" if host in PERSONAL_HINT else host


def build(data_dir: Path, files: list[dict[str, Any]], cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    from jason.tasks.drive_catalog import drive_dir

    attachments = [v for k, v in cache.items() if k != "__searched__"]
    by_md5: dict[str, list[dict[str, Any]]] = {}
    for a in attachments:
        by_md5.setdefault(a["md5"], []).append(a)
    linked = []
    for f in files:
        hits = sorted(by_md5.get(f["md5"], []), key=lambda a: a["at"])
        if not hits:
            continue
        created = f.get("created") or ""
        saved_from = [a for a in hits if a["at"] and created and a["at"] <= created]
        linked.append({"driveId": f["id"], "drivePath": f["path"], "created": created[:19], "md5": f["md5"],
                       "savedFrom": saved_from[-1]["messageId"] if saved_from else None,
                       "messages": [{"messageId": a["messageId"], "at": a["at"][:19], "direction": "out" if a["sent"] else "in",
                                     "from": _party(a["from"]), "subject": a["subject"][:90]} for a in hits]})
    drive_md5 = {f["md5"] for f in files}
    not_in_drive = sorted(({"name": a["name"], "at": a["at"][:10], "subject": a["subject"][:80], "from": _party(a["from"])}
                           for a in attachments if a["md5"] not in drive_md5), key=lambda a: a["at"], reverse=True)
    result = {
        "found": bool(attachments),
        "candidates": len(files),
        "attachmentsRead": len(attachments),
        "linkedDriveFiles": len(linked),
        "savedCopies": sum(1 for l in linked if l["savedFrom"]),
        "links": sorted(linked, key=lambda l: l["drivePath"]),
        "sameNameDifferentContent": not_in_drive[:200],
        "caveats": [
            "Neither Gmail nor Drive records that an attachment was saved; the link is equal content (MD5) under the same name.",
            "A Drive copy created after the message arrived is taken to be saved from it; the latest such message is named.",
            "Attachments of the same name whose content no candidate Drive file holds are listed: another version, or a "
            "file never saved.",
        ],
    }
    (drive_dir(data_dir) / LINKS).write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def link_lines(result: dict[str, Any], *, limit: int = 30) -> list[str]:
    out = [f"{result['candidates']} candidate Drive files; {result['attachmentsRead']} email attachments of the same names read; "
           f"{result['linkedDriveFiles']} Drive files match an attachment by content, {result['savedCopies']} saved after the email", ""]
    for l in result["links"][:limit]:
        first = l["messages"][0]
        out.append(f"{l['drivePath']} (created {l['created'][:10]})")
        out.append(f"  {len(l['messages'])} message(s); first {first['at'][:10]} {first['direction']} {first['from'] or '-'}: {first['subject'][:70]}")
    if result["sameNameDifferentContent"]:
        out.append("")
        out.append(f"Attachments with a candidate's name but not its content ({len(result['sameNameDifferentContent'])})")
        for a in result["sameNameDifferentContent"][:12]:
            out.append(f"  {a['at']} {a['name']} from {a['from'] or '-'}: {a['subject'][:60]}")
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["link", "build", "candidates", "link_lines"]
