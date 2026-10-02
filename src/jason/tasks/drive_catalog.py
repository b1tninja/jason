"""Where each association record is: every Drive file, every library file, and every copy elsewhere, by content.

``sync`` lists every file the signed-in account can see in Drive (read-only): id, name, folder path, type, size,
MD5, modified time, owner. Drive gives an MD5 for every uploaded file; a Google Doc, Sheet, or Slide has none.

``holdings`` then reads each Drive file the way the PayHOA library is read. A file under one of the specification's
Drive roots (``Mystique.drive_roots()``) takes the library path of that root's PayHOA folder plus its own subpath, so
the same name and path rules (``classify_document``) give its kind, its Civil Code 5200 records, and whether it is
confidential. A file under no root keeps its Drive path and is classified by name alone; it has no path rule.

Every copy is then identified by content (MD5, computed for the files on disk): the PayHOA library's files, the
PayHOA attachments, the email attachments, and the scanned mail. The result, for each document:

- every place it appears (Drive paths, library paths, a payment, an email, a letter), and which is under a path rule;
- the same content in several Drive folders (a duplicate), and the same name with different content (a version);
- the records each kind stands for, so a record's holdings can be listed by where they are.

It reads disk and Drive only; it moves, renames, and deletes nothing.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

DRIVE_DIR = "drive"
FILES = "files.json"
MD5_CACHE = "md5-cache.json"
REPORT = "holdings.json"
FOLDER = "application/vnd.google-apps.folder"
FIELDS = "id,name,mimeType,size,md5Checksum,createdTime,modifiedTime,parents,owners(emailAddress),driveId,trashed,webViewLink"


def drive_dir(data_dir: Path) -> Path:
    return Path(data_dir) / DRIVE_DIR


def sync(drive: Any, data_dir: Path, *, log: Callable[[str], None] | None = None) -> dict[str, int]:
    """List every non-trashed file and folder the account can see, and save them with their folder paths."""
    say = log or (lambda _m: None)
    rows = drive.list_files("trashed = false", page_size=1000, fields=FIELDS)
    by_id = {r["id"]: r for r in rows}
    paths: dict[str, str] = {}
    # The account is the most common owner. A file whose folder is not listed sits in its My Drive root, or was shared
    # with it from a folder it cannot see.
    owners: dict[str, int] = {}
    for r in rows:
        who = ((r.get("owners") or [{}])[0]).get("emailAddress", "")
        owners[who] = owners.get(who, 0) + 1
    me = max(owners, key=owners.get) if owners else ""

    def top(row: dict[str, Any]) -> str:
        who = ((row.get("owners") or [{}])[0]).get("emailAddress", "")
        if row.get("driveId"):
            return "Shared drive"
        return "My Drive" if who == me else f"Shared with me ({who or 'no owner'})"

    def path_of(file_id: str, depth: int = 0) -> str:
        if file_id in paths:
            return paths[file_id]
        row = by_id.get(file_id)
        if row is None or depth > 40:
            return ""
        parent = (row.get("parents") or [""])[0]
        head = path_of(parent, depth + 1) if parent in by_id else top(row)
        paths[file_id] = f"{head}/{row['name']}"
        return paths[file_id]

    files = []
    for r in rows:
        if r.get("mimeType") == FOLDER:
            continue
        parent = (r.get("parents") or [""])[0]
        files.append({"id": r["id"], "name": r["name"], "path": path_of(r["id"]), "folderId": parent,
                      "folderIds": _ancestors(parent, by_id), "mimeType": r.get("mimeType", ""), "size": int(r.get("size") or 0),
                      "md5": r.get("md5Checksum", ""), "created": r.get("createdTime", ""), "modified": r.get("modifiedTime", ""),
                      "owner": ((r.get("owners") or [{}])[0]).get("emailAddress", ""), "link": r.get("webViewLink", "")})
    root = drive_dir(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / FILES).write_text(json.dumps({"syncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                          "folders": sum(1 for r in rows if r.get("mimeType") == FOLDER), "files": files}, indent=1),
                              encoding="utf-8")
    say(f"Drive: {len(files)} files in {sum(1 for r in rows if r.get('mimeType') == FOLDER)} folders")
    return {"files": len(files)}


def _ancestors(folder_id: str, by_id: dict[str, dict[str, Any]]) -> list[str]:
    out = []
    while folder_id and folder_id in by_id and len(out) < 40:
        out.append(folder_id)
        folder_id = (by_id[folder_id].get("parents") or [""])[0]
    if folder_id and folder_id not in out:
        out.append(folder_id)
    return out


def load_files(data_dir: Path) -> list[dict[str, Any]]:
    path = drive_dir(data_dir) / FILES
    return json.loads(path.read_text(encoding="utf-8")).get("files", []) if path.is_file() else []


def library_path(community: Any, file: dict[str, Any]) -> tuple[str, str]:
    """(the library path this Drive file takes under the root that holds it, the root's Drive folder), or ("", "")."""
    folders = {f.folder: f for f in community.library_folders()}
    parts = file["path"].split("/")
    for root in community.drive_roots():
        target = folders.get(root.payhoa_folder)
        if target is None:
            continue
        at = None
        if root.drive is not None and root.drive.value in file.get("folderIds", []):
            # The root is a known folder id: the subpath is everything below that folder's name in the path.
            at = next((i for i, part in enumerate(parts[:-1]) if part.casefold() == root.drive_folder.casefold()), None)
            if at is None:
                return target.path + parts[-1], root.drive_folder
        else:
            at = next((i for i, part in enumerate(parts[:-1]) if part.casefold() == root.drive_folder.casefold()), None)
        if at is not None:
            return target.path + "/".join(parts[at + 1:]), root.drive_folder
    return "", ""


def _md5(path: Path, cache: dict[str, Any]) -> str:
    try:
        stat = path.stat()
    except OSError:
        return ""
    key = str(path)
    hit = cache.get(key)
    if hit and hit[0] == stat.st_size and hit[1] == int(stat.st_mtime):
        return hit[2]
    digest = hashlib.md5(path.read_bytes()).hexdigest()
    cache[key] = [stat.st_size, int(stat.st_mtime), digest]
    return digest


def local_places(data_dir: Path, community: Any) -> list[dict[str, Any]]:
    """Every file on disk the association holds outside Drive, with its MD5 and where it is."""
    from jason.tasks.library import load as load_library

    data_dir = Path(data_dir)
    cache_path = drive_dir(data_dir) / MD5_CACHE
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    places: list[dict[str, Any]] = []
    library_root = data_dir / "library" / "files"
    by_path = {str(r["path"]).casefold(): r for r in load_library(data_dir)}
    for path in sorted(library_root.rglob("*")) if library_root.is_dir() else []:
        if path.is_file():
            rel = str(path.relative_to(library_root)).replace("\\", "/")
            row = by_path.get(rel.casefold()) or {}
            places.append({"channel": "PayHOA library", "where": rel, "name": row.get("name") or path.name,
                           "md5": _md5(path, cache), "kind": row.get("kind", ""), "records": row.get("records", [])})
    for pattern, channel in (("transactions/*/*/invoices/*", "PayHOA attachment"), ("payhoa/attachments/*/*", "PayHOA attachment"),
                             ("gmail/files/*/*", "email attachment"), ("mail/*/*.pdf", "paper mail scan")):
        for path in sorted(data_dir.glob(pattern)):
            if path.is_file():
                places.append({"channel": channel, "where": str(path.relative_to(data_dir)).replace("\\", "/"), "name": path.name,
                               "md5": _md5(path, cache), "kind": "", "records": []})
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    return places


def holdings(data_dir: Path, community: Any, *, log: Callable[[str], None] | None = None) -> dict[str, Any]:
    from jason.community.library import LibraryDocument, classify_by_name

    say = log or (lambda _m: None)
    files = load_files(data_dir)
    places = local_places(data_dir, community)
    say(f"Drive files {len(files)}; files on disk {len(places)}")
    by_md5: dict[str, list[dict[str, Any]]] = {}
    for p in places:
        if p["md5"]:
            by_md5.setdefault(p["md5"], []).append(p)
    drive_rows = []
    for f in files:
        lib_path, root = library_path(community, f)
        doc = LibraryDocument("drive", f["id"], lib_path or f["path"], f["name"], "")
        c = classify_by_name(community, doc)
        records = [r.value for r in c.records]
        elsewhere = [{"channel": p["channel"], "where": p["where"]} for p in by_md5.get(f["md5"], [])] if f["md5"] else []
        drive_rows.append({"id": f["id"], "name": f["name"], "drivePath": f["path"], "libraryPath": lib_path, "root": root,
                           "pathRule": bool(lib_path), "kind": c.kind.value if c.kind else "", "records": records,
                           "confidential": bool(c.confidential), "md5": f["md5"], "mimeType": f["mimeType"], "modified": f["modified"][:10],
                           "owner": f["owner"], "elsewhere": elsewhere})
    # Duplicates in Drive (same content, several paths) and versions (same name, different content).
    by_content: dict[str, list[dict[str, Any]]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for r in drive_rows:
        if r["md5"]:
            by_content.setdefault(r["md5"], []).append(r)
        by_name.setdefault(r["name"].casefold(), []).append(r)
    duplicates = [{"name": rows[0]["name"], "paths": [r["drivePath"] for r in rows], "kind": rows[0]["kind"]}
                  for rows in by_content.values() if len(rows) > 1]
    versions = [{"name": rows[0]["name"], "copies": [{"path": r["drivePath"], "modified": r["modified"], "md5": r["md5"][:8]} for r in rows]}
                for rows in by_name.values() if len({r["md5"] or r["id"] for r in rows}) > 1]
    # Each record's holdings, by where they are.
    by_record: dict[str, dict[str, Any]] = {}
    for r in drive_rows:
        for record in r["records"]:
            entry = by_record.setdefault(record, {"drive": 0, "underRule": 0, "outsideRules": [], "alsoInPayhoa": 0})
            entry["drive"] += 1
            entry["underRule"] += int(r["pathRule"])
            entry["alsoInPayhoa"] += int(any(e["channel"] == "PayHOA library" for e in r["elsewhere"]))
            if not r["pathRule"]:
                entry["outsideRules"].append(r["drivePath"])
    drive_md5 = {r["md5"] for r in drive_rows if r["md5"]}
    library_only = [{"where": p["where"], "name": p["name"], "kind": p["kind"]} for p in places
                    if p["channel"] == "PayHOA library" and p["md5"] and p["md5"] not in drive_md5]
    unruled = [r for r in drive_rows if not r["pathRule"]]
    result = {
        "found": bool(files),
        "driveFiles": len(drive_rows),
        "underPathRule": len(drive_rows) - len(unruled),
        "classified": sum(1 for r in drive_rows if r["kind"]),
        "googleNative": sum(1 for r in drive_rows if not r["md5"]),
        "alsoOnDisk": sum(1 for r in drive_rows if r["elsewhere"]),
        "records": dict(sorted(by_record.items())),
        "duplicatesInDrive": sorted(duplicates, key=lambda d: -len(d["paths"])),
        "versionsInDrive": sorted(versions, key=lambda v: -len(v["copies"])),
        "libraryNotInDrive": library_only,
        "unruledFolders": _folders(unruled),
        "rows": drive_rows,
        "caveats": [
            "A file is placed by the specification's Drive roots and classified by the same name and path rules as the library; "
            "a file under no root has no path rule, and its kind is from its name alone.",
            "Content is compared by MD5; a Google Doc, Sheet, or Slide has none in Drive and is matched by name only.",
            "A duplicate or version is for a person to reconcile; jason moves and deletes nothing.",
        ],
    }
    out = drive_dir(data_dir) / REPORT
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def _folders(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The Drive folders holding files no path rule covers, with counts and the kinds the names suggest."""
    found: dict[str, dict[str, Any]] = {}
    for r in rows:
        folder = r["drivePath"].rsplit("/", 1)[0]
        entry = found.setdefault(folder, {"folder": folder, "files": 0, "kinds": {}})
        entry["files"] += 1
        if r["kind"]:
            entry["kinds"][r["kind"]] = entry["kinds"].get(r["kind"], 0) + 1
    return sorted(found.values(), key=lambda e: -e["files"])


def holdings_lines(result: dict[str, Any], *, record: str = "") -> list[str]:
    if not result["found"]:
        return ["No Drive listing on disk; run jason drive --sync."]
    out = [f"Drive: {result['driveFiles']} files; {result['underPathRule']} under a path rule; {result['classified']} classified; "
           f"{result['googleNative']} Google files (no MD5); {result['alsoOnDisk']} also held elsewhere by content", ""]
    out.append("Association records (Civil Code 5200) in Drive")
    for name, e in result["records"].items():
        if record and record.lower() not in name.lower():
            continue
        out.append(f"  {name}: {e['drive']} files, {e['underRule']} under a path rule, {e['alsoInPayhoa']} also in the PayHOA library")
        for path in e["outsideRules"][:5 if not record else 50]:
            out.append(f"    outside the rules: {path}")
    if result["duplicatesInDrive"]:
        out.append("")
        out.append(f"Same content in several Drive folders ({len(result['duplicatesInDrive'])})")
        for d in result["duplicatesInDrive"][:12]:
            out.append(f"  {d['name']} ({d['kind'] or 'unclassified'}): " + " | ".join(d["paths"][:4]))
    if result["versionsInDrive"]:
        out.append("")
        out.append(f"Same name, different content ({len(result['versionsInDrive'])})")
        for v in result["versionsInDrive"][:12]:
            out.append(f"  {v['name']}: " + " | ".join(f"{c['path']} ({c['modified']})" for c in v["copies"][:3]))
    if result["libraryNotInDrive"]:
        out.append("")
        out.append(f"In the PayHOA library, not in Drive by content ({len(result['libraryNotInDrive'])})")
        for l in result["libraryNotInDrive"][:12]:
            out.append(f"  {l['where']} ({l['kind'] or 'unclassified'})")
    if result["unruledFolders"]:
        out.append("")
        out.append("Drive folders no path rule covers")
        for f in result["unruledFolders"][:15]:
            kinds = ", ".join(f"{k} {n}" for k, n in sorted(f["kinds"].items(), key=lambda kv: -kv[1])[:3])
            out.append(f"  {f['folder']}: {f['files']} files{'; ' + kinds if kinds else ''}")
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["sync", "holdings", "holdings_lines", "library_path", "load_files"]
