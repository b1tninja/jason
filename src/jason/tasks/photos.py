"""Photos a person picks from a shared Google Photos album, kept as association records.

Since March 31, 2025 no app can open a shared album or read a person's library. So the person picks: ``pick`` opens a
Picker session, prints its link, waits until the person is done, and saves each picked photo under
``data/photos/<slug>/`` with a ``manifest.json`` (the album's share URL, its agenda labels and likely incidents, and each
file's digests). ``publish`` keeps the photos in an album jason created, named by the spec's rule, each captioned with
its agenda labels; sharing that album is done by a person in the Google Photos app. ``to_drive`` copies the photos into
a Drive folder named like the album. Every write needs ``yes``; without it each returns what it would do.

Google strips a photo's location when the Picker hands it over; the rest of its Exif stays.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jason.google.errors import GoogleError
from jason.tasks.digests import Digests

ROOT = Path("photos")
MANIFEST = "manifest.json"
LOCATION_NOTE = ("Google removes location metadata from photos handed over by the Picker API; "
                 "the rest of each photo's Exif is kept.")
SHARING_NOTE = "Sharing the album is done by a person in the Google Photos app; the API cannot share it."
DEFAULT_POLL = 5.0
DEFAULT_TIMEOUT = 1800.0


class PickTimeout(GoogleError):
    """The person did not finish picking before the timeout."""


def _spec(community: Any) -> Any:
    """The mystique ``photos`` module (``ALBUM_NAME``, ``PHOTOS_DRIVE_FOLDER``), beside the community's own module."""
    if community is None:
        from jason.community import community as active

        community = active()
    package = type(community).__module__.rsplit(".", 1)[0]
    return importlib.import_module(f"{package}.photos")


def _hook(community: Any, name: str) -> Any:
    """A community's hook: a method (the Community classes) or a plain value (a stand-in)."""
    hook = getattr(community, name, None)
    return hook() if callable(hook) else hook


def album_rule(community: Any = None) -> Any:
    """The community's ``photo_album_rule()``, else ``ALBUM_NAME`` in the spec's ``photos`` module."""
    return _hook(community, "photo_album_rule") or _spec(community).ALBUM_NAME


def drive_folder(community: Any = None) -> str:
    """The community's ``photos_drive_folder()``, else ``PHOTOS_DRIVE_FOLDER`` in the spec's ``photos`` module."""
    return _hook(community, "photos_drive_folder") or _spec(community).PHOTOS_DRIVE_FOLDER


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")


def slug_for(url: str, labels: list[dict[str, Any]]) -> str:
    """``{date}-{item}-{hash}`` from the album's newest label; ``unlabeled-{hash}`` without one. The hash is the URL's."""
    tag = hashlib.sha1(url.encode("utf-8")).hexdigest()[:6]
    if not labels:
        return f"unlabeled-{tag}"
    head = _slug(f"{labels[0].get('date') or ''} {labels[0].get('item') or ''}")[:60].strip("-")
    return f"{head}-{tag}" if head else f"unlabeled-{tag}"


def _duration(value: Any, default: float) -> float:
    """A protobuf Duration (``"5s"``, ``"1.5s"``) in seconds."""
    if value in (None, ""):
        return default
    try:
        return float(str(value).rstrip("s"))
    except ValueError:
        return default


def folder(data_dir: Path, slug: str) -> Path:
    return Path(data_dir) / ROOT / slug


def load_manifest(data_dir: Path, slug: str) -> dict[str, Any]:
    path = folder(data_dir, slug) / MANIFEST
    if not path.is_file():
        raise FileNotFoundError(f"no imported album {slug!r} (data/photos/{slug}/manifest.json)")
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(data_dir: Path, manifest: dict[str, Any]) -> Path:
    path = folder(data_dir, manifest["slug"]) / MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return path


def _target(data_dir: Path, album_url: str) -> dict[str, Any] | None:
    from jason.community.agenda_links import LinkKind
    from jason.tasks.agenda_links import lookup

    hits = lookup(data_dir, album_url)
    photos = [t for t in hits if t.get("kind") == LinkKind.PHOTOS.value] or hits
    return photos[0] if photos else None


def _file_name(item: dict[str, Any], taken: dict[str, str]) -> str:
    """The item's own file name; a second item with the same name and another createTime gets the time appended."""
    media = item.get("mediaFile") or {}
    name = media.get("filename") or f"{item.get('id', 'item')}"
    created = item.get("createTime") or ""
    if name not in taken or taken[name] == created:
        return name
    stem, dot, ext = name.rpartition(".")
    stamp = re.sub(r"[^0-9]", "", created)[:14] or str(item.get("id", ""))[:8]
    return f"{stem}-{stamp}.{ext}" if dot else f"{name}-{stamp}"


def pick(photos: Any, data_dir: Path, community: Any, album_url: str, *, poll: float | None = None,
         timeout: float = DEFAULT_TIMEOUT, log: Callable[[str], None] = print,
         sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    """Have a person pick the album's photos, save them, and write the manifest. Picking again adds to the same folder."""
    target = _target(data_dir, album_url)
    labels = list((target or {}).get("labels") or [])
    incidents = list((target or {}).get("incidents") or [])
    share = (target or {}).get("shareUrl") or album_url
    slug = slug_for((target or {}).get("url") or album_url, labels)
    rule = album_rule(community)
    try:
        manifest = load_manifest(data_dir, slug)
    except FileNotFoundError:
        manifest = {"slug": slug, "items": [], "picks": []}
    manifest.update({"albumUrl": (target or {}).get("url") or album_url, "shareUrl": share, "labels": labels,
                     "incidents": incidents, "topics": (target or {}).get("topics") or [],
                     "label": None if labels else rule.unlabeled, "locationStripped": True, "locationNote": LOCATION_NOTE})
    if target is None:
        log(f"no agenda links {album_url}; the photos are saved as {rule.unlabeled}")

    session = photos.create_session()
    session_id = session["id"]
    try:
        log("Open this link, find the album, select its photos, and press Done:")
        log(f"  {session['pickerUri']}")
        config = session.get("pollingConfig") or {}
        interval = poll if poll is not None else _duration(config.get("pollInterval"), DEFAULT_POLL)
        limit = min(timeout, _duration(config.get("timeoutIn"), timeout))
        start = clock()
        while not session.get("mediaItemsSet"):
            if clock() - start >= limit:
                raise PickTimeout(f"no photos were picked within {int(limit)} seconds")
            sleep(interval)
            session = photos.session(session_id)
            config = session.get("pollingConfig") or config
            if poll is None:
                interval = _duration(config.get("pollInterval"), interval)

        picked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        items: list[dict[str, Any]] = manifest["items"]
        known = {(i["filename"], i["createTime"]) for i in items}
        by_id = {i["id"] for i in items}
        taken = {i["path"].rsplit("/", 1)[-1]: i["createTime"] for i in items}
        digests = Digests(data_dir)
        added = skipped = 0
        base = folder(data_dir, slug)
        for item in photos.picked(session_id):
            media = item.get("mediaFile") or {}
            filename = media.get("filename") or str(item.get("id"))
            created = item.get("createTime") or ""
            if (filename, created) in known or item.get("id") in by_id:
                skipped += 1
                continue
            name = _file_name(item, taken)
            dest = photos.download(item, base / name)
            md5, sha = digests.of(dest)
            taken[name] = created
            known.add((filename, created))
            items.append({"id": item.get("id"), "filename": filename, "createTime": created,
                          "mimeType": media.get("mimeType") or "", "type": item.get("type") or "",
                          "path": f"{ROOT.as_posix()}/{slug}/{name}", "md5": md5, "sha256": sha, "pickedAt": picked_at})
            added += 1
        digests.save()
        manifest["pickedAt"] = picked_at
        manifest["picks"].append({"pickedAt": picked_at, "added": added, "skipped": skipped})
        save_manifest(data_dir, manifest)
        log(f"saved {added} new items to data/photos/{slug} ({skipped} already there)")
        return {"slug": slug, "added": added, "skipped": skipped, "items": len(items), "labels": labels}
    finally:
        try:
            photos.delete_session(session_id)
        except GoogleError:
            pass


def publish(photos: Any, data_dir: Path, slug: str, *, yes: bool = False, community: Any = None) -> dict[str, Any]:
    """Keep the picked photos in an album jason created. Without ``yes``, only say what would be done."""
    manifest = load_manifest(data_dir, slug)
    rule = album_rule(community)
    title = (manifest.get("published") or {}).get("title") or rule.title(
        manifest.get("labels") or [], manifest.get("incidents") or [], picked=manifest.get("pickedAt") or "")
    description = rule.description(manifest.get("labels") or [])
    pending = [i for i in manifest["items"] if not i.get("mediaItemId")]
    album_id = (manifest.get("published") or {}).get("albumId") or ""
    plan = {"slug": slug, "title": title, "albumId": album_id or None, "toUpload": len(pending),
            "description": description, "note": SHARING_NOTE, "dryRun": not yes}
    if not yes or not pending and album_id:
        return plan
    if not album_id:
        found = next((a for a in photos.albums() if a.get("title") == title), None)
        album = found or photos.create_album(title)
        album_id = album["id"]
        manifest["published"] = {"albumId": album_id, "title": title, "productUrl": album.get("productUrl"),
                                 "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        save_manifest(data_dir, manifest)
    tokens: dict[str, dict[str, Any]] = {}
    for item in pending:
        token = photos.upload(Path(data_dir) / item["path"], item.get("mimeType") or "application/octet-stream")
        tokens[token] = item
    results = photos.add_to_album(album_id, [(t, i["path"].rsplit("/", 1)[-1], description) for t, i in tokens.items()])
    failed = []
    for r in results:
        item = tokens.get(r.get("uploadToken") or "")
        media = r.get("mediaItem") or {}
        if item is not None and media.get("id"):
            item["mediaItemId"] = media["id"]
            item["productUrl"] = media.get("productUrl")
        elif item is not None:
            failed.append({"path": item["path"], "status": (r.get("status") or {}).get("message", "")})
    save_manifest(data_dir, manifest)
    return {**plan, "albumId": album_id, "uploaded": len(pending) - len(failed), "failed": failed, "dryRun": False}


def to_drive(drive: Any, data_dir: Path, slug: str, folder_id: str, *, yes: bool = False,
             community: Any = None) -> dict[str, Any]:
    """Copy the picked photos into a Drive folder named like the album, under ``folder_id``."""
    if not folder_id:
        raise ValueError("no Drive folder: pass --drive-folder until the board picks one (PHOTOS_DRIVE_FOLDER)")
    manifest = load_manifest(data_dir, slug)
    rule = album_rule(community)
    name = (manifest.get("published") or {}).get("title") or rule.title(
        manifest.get("labels") or [], manifest.get("incidents") or [], picked=manifest.get("pickedAt") or "")
    pending = [i for i in manifest["items"] if not i.get("driveId")]
    plan = {"slug": slug, "folder": name, "parentId": folder_id, "toCopy": len(pending), "dryRun": not yes}
    if not yes:
        return plan
    from jason.tasks.letters import matter_folder

    sub = (manifest.get("drive") or {}).get("folderId") if (manifest.get("drive") or {}).get("parentId") == folder_id else None
    sub = sub or matter_folder(drive, folder_id, name)
    manifest["drive"] = {"folderId": sub, "parentId": folder_id, "name": name}
    for item in pending:
        path = Path(data_dir) / item["path"]
        item["driveId"] = drive.upload_bytes(path.name, path.read_bytes(), mime_type=item.get("mimeType") or "application/octet-stream",
                                             parent_id=sub)
        save_manifest(data_dir, manifest)
    save_manifest(data_dir, manifest)
    return {**plan, "folderId": sub, "copied": len(pending), "dryRun": False}


def status(data_dir: Path) -> list[dict[str, Any]]:
    """Each imported album: items, how many are in jason's album and in Drive, and where."""
    rows = []
    for path in sorted((Path(data_dir) / ROOT).glob(f"*/{MANIFEST}")):
        m = json.loads(path.read_text(encoding="utf-8"))
        items = m.get("items") or []
        rows.append({"slug": m.get("slug") or path.parent.name, "shareUrl": m.get("shareUrl"),
                     "labels": [f"{l.get('date')} {l.get('item')}" for l in (m.get("labels") or [])] or [m.get("label") or "unlabeled"],
                     "items": len(items), "pickedAt": m.get("pickedAt"),
                     "published": sum(1 for i in items if i.get("mediaItemId")),
                     "album": (m.get("published") or {}).get("title"),
                     "inDrive": sum(1 for i in items if i.get("driveId")),
                     "driveFolder": (m.get("drive") or {}).get("folderId")})
    return rows


def status_lines(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["no albums imported (jason photos --pick URL)"]
    lines = []
    for r in rows:
        lines.append(f"- {r['slug']}: {r['items']} items, picked {r['pickedAt'] or '?'}")
        lines.append(f"    labels: {'; '.join(r['labels'][:3])}")
        lines.append(f"    album: {r['album'] or 'not published'} ({r['published']}/{r['items']}); "
                     f"Drive: {r['driveFolder'] or 'not copied'} ({r['inDrive']}/{r['items']})")
    return lines


__all__ = ["LOCATION_NOTE", "PickTimeout", "SHARING_NOTE", "album_rule", "drive_folder", "load_manifest", "pick",
           "publish", "slug_for", "status", "status_lines", "to_drive"]
