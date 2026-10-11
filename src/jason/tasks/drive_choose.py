"""The Drive chooser's backend (docs/record-intake.md, "Choosing the files"): jason's own dialog over the server's Drive token.

Three reads, all through one Drive client the caller opens (``open_client``; never a browser, ``interactive=False``, so a
missing sign-in is a ``DriveUnavailable`` with the words a console shows and the command that fixes it):

- ``list_folder``: a folder's children (My Drive's top when none is named, with the shared drives the account is in), a page
  at a time;
- ``search``: files whose name holds some text, across the account's drives. The text goes to Google, so the web route is a
  POST and the text is never in a URL;
- ``resolve``: a pasted link or id, read for its metadata so a person sees what they pasted before they pick it.

Each answers only what a chooser needs: id, name, type, size, the day modified, parents, the owner's display name, whether
the file is on a shared drive, whether jason's account can read it, and what jason itself knows of it (in the library as a
kind, in a folder a sync rule covers, pinned for a slot). Reads only: no call here creates, updates, moves, shares, or
trashes a file, and a Google refusal is told in jason's words, never with the exception's text (which can hold an id).

A name is masked like any other file's: a file the library or the kind rules read as a confidential kind is shown as "a
confidential file (kind: ...)" with no id until the private view is open.

``propose_sync_rule`` is the text of a profile change a person may apply for a folder bound to a Civil Code 5200 record. It
edits nothing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jason.community.record_slots import parse_drive_ref
from jason.google.drive import DOCX_MIME_TYPE, FOLDER_MIME_TYPE, GOOGLE_DOC_MIME_TYPE
from jason.google.errors import GoogleAuthRequired, GoogleError, GoogleHttpError

log = logging.getLogger(__name__)

PAGE = 50
MAX_PAGE = 100
MIN_SEARCH = 2
MAX_SEARCH = 100
FIELDS = ("id,name,mimeType,size,modifiedTime,parents,driveId,owners(displayName,emailAddress),"
          "capabilities(canDownload,canListChildren)")
CAVEATS = (
    "jason lists what its own Drive account sees. A file that account cannot see is not listed: share it with that account, "
    "or upload it.",
    "Choosing a file names it for a slot and copies nothing. jason reads Drive here and writes nothing: it never changes a "
    "file, its sharing, or its place.",
    "A Google Doc is kept by jason as a Word copy; the Doc stays the original.",
)
TYPES = {
    "application/pdf": "pdf", GOOGLE_DOC_MIME_TYPE: "doc", FOLDER_MIME_TYPE: "folder",
    "application/vnd.google-apps.spreadsheet": "sheet", "application/vnd.google-apps.presentation": "slides",
    "application/vnd.google-apps.form": "form", "application/vnd.google-apps.shortcut": "shortcut",
    DOCX_MIME_TYPE: "word", "application/msword": "word", "text/plain": "text",
}


class DriveUnavailable(ValueError):
    """jason cannot read Drive in this process: there is no sign-in, or it lacks the permission. ``command`` is what fixes
    it. A ValueError so a caller that does not know it still shows the sentence."""

    def __init__(self, message: str, command: str = "") -> None:
        super().__init__(message)
        self.command = command


NOT_SIGNED_IN = ("jason cannot read Drive: it has no Google sign-in on this machine. A person signs in once at a terminal; "
                 "until then, paste a link (jason resolves nothing without a sign-in) or upload the file.")
NEEDS_VAULT = "jason cannot read Drive: the credential vault (Keeper) needs a person to sign in first."


def open_client(agent: Any = None, *, interactive: bool = False) -> Any:
    """A read-only-use Drive client from jason's server token: the vault's OAuth client and refresh token. Never a browser
    unless a person passed ``interactive`` (a terminal's ``--interactive``). ``agent`` is a ``Jason`` (a command passes its
    own); the default builds one. Fails fast as ``DriveUnavailable``."""
    from jason.secrets import KeeperAuthRequired

    try:
        if agent is None:
            from jason.agent import Jason

            agent = Jason(interactive=interactive)
        return agent.drive(interactive=interactive)
    except GoogleAuthRequired as exc:
        raise DriveUnavailable(NOT_SIGNED_IN, "jason google sign-in --name drive --interactive") from exc
    except KeeperAuthRequired as exc:
        raise DriveUnavailable(NEEDS_VAULT, "jason login") from exc
    except GoogleError as exc:
        raise DriveUnavailable("jason cannot read Drive: its Google sign-in is not usable "
                               f"({type(exc).__name__}). Run the Google status check.", "jason google status") from exc


def unavailable_answer(exc: DriveUnavailable) -> dict[str, Any]:
    """What a console shows when Drive is not connected: a state, the sentence, and the command (never a field)."""
    return {"found": False, "driveConnected": False, "why": str(exc), "command": exc.command, "caveats": list(CAVEATS)}


def _shorten(text: str, limit: int = 300) -> str:
    return " ".join(str(text or "").split())[:limit]


def refusal_words(exc: Exception) -> str:
    """A Google refusal in jason's words. Never the exception's text: Google's messages can hold a file id."""
    status = getattr(exc, "status", 0)
    if isinstance(exc, GoogleHttpError):
        if status in (403, 404):
            return ("jason's Drive account cannot open that (not found, or not shared with it). Share it with the account "
                    "shown, or upload the file. Nothing was picked.")
        if status == 429 or getattr(exc, "reason", "") in ("rateLimitExceeded", "userRateLimitExceeded"):
            return "Google is limiting jason's requests just now. Nothing was picked; try again in a minute."
        if status == 401:
            return "Google no longer accepts jason's sign-in. A person signs in again. Nothing was picked."
        return f"Google answered with an error (HTTP {status or 'unknown'}). Nothing was picked."
    return f"jason could not reach Drive ({type(exc).__name__}). Nothing was picked."


# What jason itself knows of a file --------------------------------------------------------------------------------------------

class Knowledge:
    """What jason's own records say about a Drive file, read once: the library's rows by name, the Drive catalog's names by
    id, the slots a file is pinned for, and the folders the sync rules cover. Disk only."""

    def __init__(self, community: Any, root: Path, profile: str) -> None:
        from jason.tasks import record_slots as rs

        self.community, self.root, self.profile = community, Path(root), profile
        self.library = rs.Library(self.root)
        self.slots = rs.assemble(community).slots
        self.pinned: dict[str, list[str]] = {}
        for row in rs.load_store(profile)["pins"]:
            pin = rs._pin_of(row)
            if pin and pin.active and pin.kind.value == "drive":
                self.pinned.setdefault(pin.ref, []).append(pin.slot)
        for slot in self.slots:
            if slot.key_document:
                for pin in rs._key_document_records(self.root, profile, slot)[0]:
                    if pin.active and pin.kind.value == "drive":
                        self.pinned.setdefault(pin.ref, []).append(slot.key)
        self.rule_folders: set[str] = set()
        try:
            for rule in tuple(getattr(community, "sync_rules", ()) or ()):
                if getattr(rule, "drive_folder", ""):
                    self.rule_folders.add(str(rule.drive_folder))
        except Exception:  # noqa: BLE001 - a profile with no rules covers no folder
            pass

    def kind_of(self, name: str) -> tuple[str, bool]:
        """The kind jason reads a file's name as (the library's row, else the kind rules) and whether that kind is held
        back. A miss is ("", False): never a guess."""
        from jason.community.library import CONFIDENTIAL_KINDS
        from jason.community.symbols import DocumentKind

        rows = self.library.by_name.get(str(name or "").casefold(), [])
        kinds = {r.get("kind") for r in rows if r.get("kind")}
        if len(kinds) == 1 and rows:
            kind = str(next(iter(kinds)))
            return kind, any(bool(r.get("confidential")) for r in rows) or _kind_is_held(kind)
        try:
            found = self.community.classify_document(name, None, name) if self.community is not None else None
        except Exception:  # noqa: BLE001 - a rule that cannot answer is a miss
            found = None
        if isinstance(found, DocumentKind):
            return found.value, found in CONFIDENTIAL_KINDS
        return "", False

    def for_item(self, meta: dict[str, Any]) -> dict[str, Any]:
        name = str(meta.get("name") or "")
        kind, held = self.kind_of(name)
        parents = [str(p) for p in meta.get("parents") or ()]
        return {"inLibrary": kind if self.library.by_name.get(name.casefold()) else "", "kind": kind,
                "ruleCovers": any(p in self.rule_folders for p in parents) if self.rule_folders else False,
                "pinnedFor": sorted(set(self.pinned.get(str(meta.get("id") or ""), []))), "held": held}


def _kind_is_held(kind: str) -> bool:
    from jason.community.library import CONFIDENTIAL_KINDS
    from jason.community.symbols import DocumentKind

    try:
        return DocumentKind(kind) in CONFIDENTIAL_KINDS
    except ValueError:
        return False


def known(community: Any = None, root: Path | None = None, profile: str | None = None) -> Knowledge:
    from jason.tasks import record_slots as rs

    root = rs._root(root)
    return Knowledge(community, root, rs._profile(profile, community))


# The shapes ----------------------------------------------------------------------------------------------------------------

def type_word(mime: str) -> str:
    if mime in TYPES:
        return TYPES[mime]
    if mime.startswith("image/"):
        return "image"
    return "file"


def readable(meta: dict[str, Any]) -> tuple[bool, str]:
    """Whether jason's account can read the file (not whether it should): a stored file it may download, a Doc it may
    export, a folder it may list. Everything else is listed but marked, with why."""
    mime = str(meta.get("mimeType") or "")
    caps = meta.get("capabilities") if isinstance(meta.get("capabilities"), dict) else {}
    if mime == FOLDER_MIME_TYPE:
        return (caps.get("canListChildren") is not False), ("" if caps.get("canListChildren") is not False else
                                                           "jason's account cannot list this folder")
    if mime == GOOGLE_DOC_MIME_TYPE:
        return True, ""
    if mime.startswith("application/vnd.google-apps."):
        return False, f"a {type_word(mime)} has no document for jason to read; export it as a PDF or Word file and upload that"
    if caps.get("canDownload") is False:
        return False, "the owner has turned downloading off for this file; ask them, or upload a copy"
    return True, ""


def _size(meta: dict[str, Any]) -> int | None:
    try:
        return int(meta["size"]) if meta.get("size") not in (None, "") else None
    except (TypeError, ValueError):
        return None


def item_of(meta: dict[str, Any], knows: Knowledge | None, *, private: bool) -> dict[str, Any]:
    """One file as the chooser lists it. A file read as a confidential kind is named by its kind and carries no id outside the
    private view."""
    mime = str(meta.get("mimeType") or "")
    folder = mime == FOLDER_MIME_TYPE
    ok, why = readable(meta)
    jason = knows.for_item(meta) if knows is not None else {"inLibrary": "", "kind": "", "ruleCovers": False, "pinnedFor": [], "held": False}
    held = bool(jason.pop("held")) and not folder
    owners = [o for o in (meta.get("owners") or ()) if isinstance(o, dict)]
    name = str(meta.get("name") or "")
    masked = held and not private
    if masked:
        name = f"a confidential file (kind: {(jason.get('kind') or 'unclassified').replace('_', ' ')})"
        jason = {**jason, "pinnedFor": []}
    return {
        "id": "" if masked else str(meta.get("id") or ""), "name": name, "type": type_word(mime), "mime": mime,
        "size": _size(meta), "modified": str(meta.get("modifiedTime") or "")[:10],
        "parents": [] if masked else [str(p) for p in meta.get("parents") or ()],
        "owner": "" if masked else str(owners[0].get("displayName") or "") if owners else "",
        "sharedDrive": bool(meta.get("driveId")), "readable": ok, "why": why, "held": held,
        "opens": "opens in the private view" if masked else "", "children": None,
        "doc": "A Doc: jason keeps a Word copy; the Doc stays the original." if mime == GOOGLE_DOC_MIME_TYPE else "",
        "jason": jason,
    }


def _account(drive: Any) -> str:
    try:
        who = drive.about_user()
    except Exception:  # noqa: BLE001 - the header falls back to saying nothing rather than failing the list
        return ""
    return _shorten(who.get("emailAddress") or who.get("displayName") or "", 120)


def _path(drive: Any, folder_id: str, name: str) -> list[dict[str, str]]:
    """The breadcrumb up from a folder (names only, to the top or six folders up). Ids are not in it: a breadcrumb is text."""
    names = [name]
    seen = {folder_id}
    cursor = folder_id
    for _ in range(6):
        try:
            meta = drive.file_metadata(cursor, "id,name,parents")
        except Exception:  # noqa: BLE001 - a path that cannot be walked is shown as far as it got
            break
        parents = [str(p) for p in meta.get("parents") or ()]
        if not parents or parents[0] in seen:
            break
        cursor = parents[0]
        seen.add(cursor)
        try:
            up = drive.file_metadata(cursor, "id,name,parents")
        except Exception:  # noqa: BLE001
            break
        names.append(str(up.get("name") or ""))
        if not up.get("parents"):
            break
    return [{"name": n} for n in reversed(names) if n]


def _clamp(size: Any) -> int:
    try:
        return max(1, min(int(size), MAX_PAGE))
    except (TypeError, ValueError):
        return PAGE


def list_folder(drive: Any, *, folder: str = "", page_token: str = "", drive_id: str = "", page_size: Any = PAGE,
                community: Any = None, root: Path | None = None, profile: str | None = None, private: bool = False) -> dict[str, Any]:
    """A folder's children, a page at a time, folders first. With no ``folder``: the top of My Drive, and (on its first page)
    the shared drives the account is in. ``folder`` may be a Drive link or id. Reads Drive and disk."""
    knows = known(community, root, profile)
    parent_id = "root"
    if str(folder or "").strip():
        try:
            parent_id = parse_drive_ref(folder).id
        except ValueError as exc:
            return {"found": False, "why": str(exc), "caveats": list(CAVEATS)}
    query = f"'{parent_id}' in parents and trashed = false"
    try:
        rows, nxt = drive.list_page(query, page_token=str(page_token or ""), page_size=_clamp(page_size), fields=FIELDS,
                                    drive_id=str(drive_id or ""), order_by="folder,name")
        parent: dict[str, Any] = {"name": "My Drive", "path": [{"name": "My Drive"}]}
        drives: list[dict[str, str]] = []
        if parent_id != "root":
            meta = drive.file_metadata(parent_id, "id,name,parents,mimeType")
            if meta.get("mimeType") not in (None, FOLDER_MIME_TYPE):
                return {"found": False, "why": "That is a file, not a folder.", "caveats": list(CAVEATS)}
            parent = {"name": str(meta.get("name") or ""), "path": _path(drive, parent_id, str(meta.get("name") or ""))}
        elif not page_token:
            drives = [{"name": str(d.get("name") or ""), "id": str(d.get("id") or ""), "type": "drive"}
                      for d in drive.list_shared_drives()]
    except Exception as exc:  # noqa: BLE001 - a Google refusal is an answer
        log.info("drive list refused: %s", type(exc).__name__)
        return {"found": False, "driveConnected": True, "why": refusal_words(exc), "caveats": list(CAVEATS)}
    items = [item_of(r, knows, private=private) for r in rows]
    log.info("drive list: %d items", len(items))
    return {"found": True, "driveConnected": True, "account": _account(drive), "parent": parent, "items": items, "drives": drives,
            "empty": ("This folder is empty." if not items and not nxt and not page_token else ""),
            "next": nxt or None, "caveats": list(CAVEATS)}


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'")


def search(drive: Any, text: str, *, page_token: str = "", drive_id: str = "", page_size: Any = PAGE, community: Any = None,
           root: Path | None = None, profile: str | None = None, private: bool = False) -> dict[str, Any]:
    """Files whose name holds ``text``, across My Drive and the shared drives, a page at a time. The text is sent to Google, so
    a caller sends it as a POST body; this function never logs it."""
    clean = " ".join(str(text or "").split())
    if len(clean) < MIN_SEARCH:
        return {"found": False, "why": f"Type at least {MIN_SEARCH} letters of the file's name.", "caveats": list(CAVEATS)}
    if len(clean) > MAX_SEARCH:
        return {"found": False, "why": f"A search is at most {MAX_SEARCH} characters.", "caveats": list(CAVEATS)}
    knows = known(community, root, profile)
    try:
        rows, nxt = drive.list_page(f"name contains '{_escape(clean)}' and trashed = false", page_token=str(page_token or ""),
                                    page_size=_clamp(page_size), fields=FIELDS, drive_id=str(drive_id or ""),
                                    order_by="modifiedTime desc")
    except Exception as exc:  # noqa: BLE001
        log.info("drive search refused: %s", type(exc).__name__)
        return {"found": False, "driveConnected": True, "why": refusal_words(exc), "caveats": list(CAVEATS)}
    items = [item_of(r, knows, private=private) for r in rows]
    log.info("drive search: %d items", len(items))
    return {"found": True, "driveConnected": True, "account": _account(drive), "items": items,
            "empty": ("Nothing in jason's Drive account has a name like that. A file it cannot see is not listed: share it "
                      "with the account, or upload it." if not items and not nxt else ""),
            "next": nxt or None, "caveats": list(CAVEATS)}


def resolve(drive: Any, ref: str, *, community: Any = None, root: Path | None = None, profile: str | None = None,
            private: bool = False) -> dict[str, Any]:
    """A pasted link or id read for its metadata (read-only), so the person sees what they are about to pick. A link that is
    not Drive's, a file jason's account cannot open, and a folder are each told in a sentence."""
    try:
        parsed = parse_drive_ref(ref)
    except ValueError as exc:
        return {"found": False, "why": str(exc), "caveats": list(CAVEATS)}
    try:
        meta = drive.file_metadata(parsed.id, FIELDS)
    except Exception as exc:  # noqa: BLE001
        log.info("drive resolve refused: %s", type(exc).__name__)
        return {"found": False, "driveConnected": True, "account": _account(drive), "why": refusal_words(exc),
                "caveats": list(CAVEATS)}
    meta = {**meta, "id": parsed.id}
    item = item_of(meta, known(community, root, profile), private=private)
    owners = [o for o in (meta.get("owners") or ()) if isinstance(o, dict)]
    domain = str(owners[0].get("emailAddress") or "").rpartition("@")[2] if owners else ""
    folder = item["type"] == "folder"
    return {"found": True, "driveConnected": True, "kind": "folder" if folder else "file", **item,
            "ownerDomain": "" if item["held"] and not private else domain,
            "offer": "Choose this folder to read its files as candidates for the slot." if folder else "",
            "caveats": list(CAVEATS)}


def bound_files(drive: Any, folder: str, slot_key: str, *, community: Any = None, root: Path | None = None,
                profile: str | None = None, private: bool = False, page_size: Any = MAX_PAGE) -> dict[str, Any]:
    """The files in a bound folder as candidates for a slot: each read by name as a kind, and whether that kind belongs to
    this slot ("here"), to another slot ("elsewhere", with the slots), or to none ("nowhere"). Nothing is pinned or moved;
    one page of the folder, and the answer says whether there is more."""
    from jason.tasks import record_slots as rs

    page = list_folder(drive, folder=folder, page_size=page_size, community=community, root=root, profile=profile, private=private)
    if not page.get("found"):
        return page
    slots = rs.assemble(community).slots
    mine = next((s for s in slots if s.key == slot_key), None)
    if mine is None:
        raise KeyError(slot_key)
    fits: dict[str, list[str]] = {}
    for s in slots:
        for k in s.kinds:
            fits.setdefault(k.value, []).append(s.key)
    rows = []
    counts = {"here": 0, "elsewhere": 0, "nowhere": 0}
    for it in page["items"]:
        if it["type"] == "folder":
            continue
        kind = it["jason"].get("kind") or ""
        where = "here" if kind and kind in {k.value for k in mine.kinds} else "elsewhere" if kind and fits.get(kind) else "nowhere"
        counts[where] += 1
        rows.append({**it, "where": where, "readsAs": kind or None,
                     "offeredFor": [] if where == "here" else fits.get(kind, []) if where == "elsewhere" else []})
    _remember_listing(known(community, root, profile).root, slot_key, folder, rows, bool(page["next"]))
    return {"found": True, "folder": page["parent"], "files": rows, "counts": {**counts, "files": len(rows)},
            "more": page["next"], "caveats": [*CAVEATS, "A file in a bound folder is a candidate for the slot, never a pin; "
                                                  "a person picks it."]}


# What a bound folder held when it was last listed -----------------------------------------------------------------------------

LISTINGS = ("records", "binding-listings.json")


def _listings_path(root: Path) -> Path:
    return Path(root).joinpath(*LISTINGS)


def _read_listings(root: Path) -> dict[str, Any]:
    import json

    try:
        data = json.loads(_listings_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _remember_listing(root: Path, slot_key: str, folder: str, rows: list[dict[str, Any]], more: bool) -> None:
    """Keep what the last listing of a bound folder showed: for each file its Drive id (none for a confidential file), where it fit, and what
    it read as. No name, no size, no owner. The next counts read this, never Drive."""
    import json
    from datetime import datetime, timezone

    try:
        ref = parse_drive_ref(folder).id
    except ValueError:
        return
    from jason.locks import Resource, hold

    entry = {"slot": slot_key, "folder": ref, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "more": more,
             "files": [{"id": r.get("id") or "", "where": r.get("where"), "readsAs": r.get("readsAs")} for r in rows]}
    path = _listings_path(root)
    try:
        with hold(Resource.STORE, "binding-listings", timeout=30, purpose="drive bound listing"):
            data = _read_listings(root)
            data[f"{slot_key}|{ref}"] = entry
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
            tmp.replace(path)
    except Exception as exc:  # noqa: BLE001 - the counts are a convenience; a listing that cannot be kept is still shown
        log.info("binding listing not kept: %s", type(exc).__name__)


def binding_counts(slot_key: str, *, community: Any = None, root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """The counts a folder binding's card shows, **from the last listing already fetched** (``bound_files`` keeps it): how many files the
    folder held, how many are already pinned (for any slot) and how many of those jason has read, and how many read as this slot's kind
    (``here``), another slot's (``elsewhere``), or none (``nowhere``). It never calls Drive: a binding not listed yet says so, with the
    act that lists it. The counts are as old as the listing (``listedAt``); a folder bigger than one page is counted as far as it was
    listed (``more``)."""
    from jason.tasks import record_readback
    from jason.tasks import record_slots as rs

    root = rs._root(root)
    profile = rs._profile(profile, community)
    rs._slot(community, slot_key)
    stored = rs.load_store(profile)
    pins: dict[str, list[tuple[str, str]]] = {}
    for row in stored["pins"]:
        pin = rs._pin_of(row)
        if pin and pin.active and pin.kind.value == "drive":
            pins.setdefault(pin.ref, []).append((pin.slot, pin.id))
    knows = known(community, root, profile)
    listings = _read_listings(root)
    out = []
    for b in stored["bindings"]:
        if b.get("slot") != slot_key or b.get("unbound"):
            continue
        seen = listings.get(f"{slot_key}|{b.get('ref')}")
        card: dict[str, Any] = {"binding": b.get("id"), "slot": slot_key, "by": b.get("by"), "at": b.get("at"), "listed": seen is not None}
        if seen is None:
            card["note"] = "This folder has not been listed yet. Browse it in the chooser (POST /api/write/drive/bound), and the counts appear."
            out.append(card)
            continue
        files = list(seen.get("files") or ())
        ids = [f["id"] for f in files if f.get("id")]
        pinned = [i for i in ids if i in pins or i in knows.pinned]
        read = [i for i in ids if any(record_readback.load(root, profile, pid) is not None for _slot, pid in pins.get(i, ()))]
        card.update({"listedAt": seen.get("at"), "more": bool(seen.get("more")), "files": len(files),
                     "here": sum(1 for f in files if f.get("where") == "here"), "elsewhere": sum(1 for f in files if f.get("where") == "elsewhere"),
                     "nowhere": sum(1 for f in files if f.get("where") == "nowhere"), "pinned": len(pinned), "read": len(read),
                     "notPinned": len(ids) - len(pinned), "held": len(files) - len(ids)})
        out.append(card)
    return {"slot": slot_key, "bindings": out, "caveats": ["Counts come from the folder's last listing, not from Drive now.",
                                                          "A file in a bound folder is a candidate, never a pin."]}


def propose_sync_rule(slot: Any, folder_name: str, folder_id: str) -> dict[str, Any] | None:
    """The text of a profile change a person may apply to read a bound folder every sync: a ``SyncRule`` row for the
    slot's Civil Code 5200 record. It names the folder, the record, and what the person must choose (the rule's id, the
    public drive, and the PayHOA folder are the association's). jason edits nothing; None for a slot that is no 5200 record."""
    if not getattr(slot, "record", ""):
        return None
    from jason.community.symbols import AssociationRecord

    try:
        record = AssociationRecord(slot.record).name
    except ValueError:
        return None
    name = " ".join(str(folder_name or "").split()).replace('"', "'")
    text = (
        "# Proposed for the profile's Drive sync rules (a person applies it; jason edits nothing).\n"
        f"# Folder: {name or '(its name)'}  (Drive id {folder_id})\n"
        "SyncRule(\n"
        "    id=DocumentRule.<choose>,\n"
        f"    drive_folder=\"{name}\",\n"
        "    drive=PublicDrive.<choose>,\n"
        "    glob=\"*\",\n"
        "    destination=PayhoaFolder.<choose>,\n"
        f"    records=(AssociationRecord.{record},),\n"
        ")\n")
    return {"kind": "sync rule", "record": slot.record, "text": text,
            "note": "The rule's id, the public drive, and the PayHOA folder are the association's to choose. Until a person "
                    "applies it, the folder is only read as candidates for this slot."}


__all__ = ["CAVEATS", "DriveUnavailable", "FIELDS", "Knowledge", "LISTINGS", "MAX_PAGE", "binding_counts", "bound_files", "item_of", "known", "list_folder", "open_client",
           "propose_sync_rule", "readable", "refusal_words", "resolve", "search", "type_word", "unavailable_answer"]
