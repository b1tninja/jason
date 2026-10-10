"""The key documents checklist for the active profile, read from disk, and the writes a person makes to it.

``checklist`` reads the specification (the declaration and its amendments, the supersessions, the Drive pins, the
public reports), the association's record in the index cache (``load_association_record``), the locator's leads, and
the recorded copies on disk; expands the list (``jason.community.key_documents.expected_entries``); and joins what
people did from ``data/key-documents/<profile>.json``. Nothing here calls the county, Drive, or PayHOA.

The writes: ``link`` (a file under data/, a Drive id or link, a PayHOA library document id), ``upload`` (a file a
person chose, by a path the server can read or by its bytes, copied under ``data/key-documents/<profile>/files/``),
``unlink``, and ``status``. Each names its person.
"""

from __future__ import annotations

import base64
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from jason.community.key_documents import (
    KEY_DOCUMENTS,
    MAX_UPLOAD_BYTES,
    STATUS_MEANING,
    UPLOAD_SUFFIXES,
    Entry,
    KeyDocumentStore,
    KeyStatus,
    LinkKind,
    drive_id,
    drive_url,
    expected_entries,
    file_digest,
    item_of,
    numbers_in,
    payhoa_id,
    safe_name,
    status_of,
    valid_key,
    why_of,
)

CAVEATS = (
    "A located recording number is a lead, not a pin: the recorded copy is read before it is pinned in the specification.",
    "None on record is not none given. Missing is a person's word, recorded with what was looked for.",
    "Held means jason sees a copy (a Drive pin, or a recorded copy on disk whose stamp or name carries the number); "
    "whether it is the complete recorded copy is for a person to read.",
    "Unlinking removes the link, never the file; the store keeps who linked and unlinked each copy.",
)

# Suffixes the console opens as a document (a `file:` reference the document service views).
_SERVED = frozenset({".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".md", ".txt"})
_EXTRACT_FOLDERS = (
    ("artifacts", "site-docs", "governing_documents"),
    ("artifacts", "site-docs", "governing_documents_Annexations"),
    ("governing",),
)
_NAME_FOLDERS = (("artifacts", "site-docs"), ("payhoa-files",), ("governing",), ("key-documents",))
# A located label as the locator prints it: "NUMBER (DAY, FILING; TIE (VIA))".
_LABEL = re.compile(r"^(?P<number>\S+) \((?P<day>[^,]+), (?P<filing>.*?); (?P<how>.*)\)$")


def _root(root: Path | None) -> Path:
    if root is not None:
        return Path(root)
    from jason.mcp.county import _data_dir

    return _data_dir(None)


def _profile(profile: str | None) -> str:
    if profile:
        return profile
    from jason.community.profile import profile_name

    return profile_name()


def located_rows(root: Path, profile: str, *, spec_dir: Path | None = None) -> list[dict[str, Any]]:
    """The locator's finds for the profile: ``onboarding/<profile>-documents-located.json`` when present (a list of
    rows, or an object with ``found`` or ``located``), and the leads the onboarding lookup saved in the private facts
    (``located-<item>``, whose choices are the locator's labels). Each row: number, recorded, filing, item, tie, via."""
    rows: list[dict[str, Any]] = []
    path = Path(root) / "onboarding" / f"{profile}-documents-located.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            data = []
        items = data if isinstance(data, list) else (data.get("found") or data.get("located") or []) if isinstance(data, dict) else []
        # The locator's own shape (``Location.to_dict``): each checklist item with the instruments located for it.
        for group in (data.get("items") or []) if isinstance(data, dict) else []:
            for found in (group.get("located") or []) if isinstance(group, dict) else []:
                if isinstance(found, dict) and found.get("number"):
                    rows.append({**found, "item": group.get("item", ""), "tie": found.get("tie_label") or found.get("tie", ""),
                                 "source": path.name})
        for item in items:
            if isinstance(item, dict) and item.get("number"):
                rows.append({**item, "source": path.name})
            elif isinstance(item, str):
                parsed = _parse_label(item)
                if parsed:
                    rows.append({**parsed, "source": path.name})
    try:
        if spec_dir is None:
            from jason.community.private import spec_dir as default_spec_dir

            spec_dir = default_spec_dir()
        facts = json.loads((Path(spec_dir) / f"{profile}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        facts = {}
    for lead in (facts.get("leads") or []) if isinstance(facts, dict) else []:
        if not isinstance(lead, dict) or not str(lead.get("key", "")).startswith("located-"):
            continue
        for choice in lead.get("choices") or []:
            parsed = _parse_label(str(choice))
            if parsed:
                rows.append({**parsed, "item": lead.get("item", ""), "source": "onboarding leads"})
    seen: set[tuple[str, str]] = set()
    out = []
    for row in rows:
        mark = (str(row.get("number")), str(row.get("item", "")))
        if mark not in seen:
            seen.add(mark)
            out.append(row)
    return out


def _parse_label(label: str) -> dict[str, Any] | None:
    hit = _LABEL.match(label.strip())
    if not hit or not any(ch.isdigit() for ch in hit.group("number")):
        return None
    how = hit.group("how")
    via = ""
    tail = re.match(r"^(.*) \(([^()]*)\)$", how)
    if tail:
        how, via = tail.group(1), tail.group(2)
    day = hit.group("day")
    return {"number": hit.group("number"), "recorded": "" if day == "undated" else day, "filing": hit.group("filing"),
            "tie": how, "via": via}


def copies_on_disk(root: Path) -> dict[str, str]:
    """Each recording number a copy on disk carries (its stamp, read from the extract, or its file name), with the
    copy's path under data/; a PDF is preferred to its text extract."""
    from jason.community.readings import numbers_on_disk, read_folder

    root = Path(root)
    found: dict[str, Path] = {}
    try:
        for number, path in numbers_on_disk(read_folder(*(root.joinpath(*parts) for parts in _EXTRACT_FOLDERS))).items():
            found[number] = Path(path)
    except Exception:  # noqa: BLE001 - an unreadable extract leaves the names to place the copies
        pass
    for parts in _NAME_FOLDERS:
        folder = root.joinpath(*parts)
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() in (".json", ".tmp", ".part"):
                continue
            for number in numbers_in(path.name):
                held = found.get(number)
                if held is None or (held.suffix.lower() != ".pdf" and path.suffix.lower() == ".pdf"):
                    found[number] = path
    out: dict[str, str] = {}
    for number, path in found.items():
        pdf = path.with_suffix("") if path.suffix.lower() == ".md" and path.with_suffix("").suffix.lower() == ".pdf" else path
        chosen = pdf if pdf.is_file() else path
        try:
            out[number] = chosen.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    return out


def _county(community: Any) -> str:
    region = str(getattr(community, "region", "") or "")
    if "/" in region:
        return region.split("/", 1)[1].replace("-", " ").title()
    # The stores jason's walks fill (ownership.db, index-cache.db) are the Sacramento recorder's unless a profile sets
    # its region.
    return "Sacramento"


def entries_for(community: Any, root: Path, profile: str, *, record: Any = None) -> tuple[list[Entry], list[str]]:
    """The expected entries for the profile and the notes on what could not be read."""
    notes: list[str] = []
    if record is None:
        try:
            from jason.tasks.property_history import load_association_record

            record = load_association_record(community, root) if (root / "index-cache.db").is_file() else None
            if record is None:
                notes.append("no index cache on disk: the recording numbers come from the specification and the leads only "
                             "(jason sync-liens, or the onboarding locator, fills the index)")
        except Exception as exc:  # noqa: BLE001 - the specification alone still lists the documents
            notes.append(f"the association's record could not be read from the index cache ({type(exc).__name__}: {exc})")
            record = None
    try:
        document = community.ccrs
    except Exception:  # noqa: BLE001 - a profile with no declaration in the specification yet
        document = None
    entries = expected_entries(
        governing_document=document,
        governing=tuple(getattr(record, "governing", ()) or ()),
        unplaced=tuple(getattr(record, "unplaced", ()) or ()),
        supersessions=tuple(community.supersessions() or ()),
        pins=tuple(community.pins() or ()),
        public_reports=tuple(community.public_reports() or ()),
        located=located_rows(root, profile),
        on_disk=copies_on_disk(root),
    )
    return entries, notes


def checklist(community: Any = None, root: Path | None = None, profile: str | None = None, *, record: Any = None) -> dict[str, Any]:
    """The checklist as JSON: groups in list order, each entry with its status, copies, links, leads, and log."""
    if community is None:
        from jason.community import community as active

        community = active()
    root = _root(root)
    profile = _profile(profile)
    entries, notes = entries_for(community, root, profile, record=record)
    store = KeyDocumentStore(root, profile)
    stored = store.load()["entries"]
    by_key = {e.key: e for e in entries}
    for key, held in stored.items():
        if key not in by_key and valid_key(key):
            entry = Entry(key, item_of(key), held.get("title") or key.split("/", 1)[-1].replace("-", " ").capitalize())
            entries.append(entry)
            by_key[key] = entry
    groups: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    # The same slot reader the record checklist uses, so the two screens cannot disagree: each key document's slot (its state
    # and pins) and, for each instrument, how many files are linked, read, and read as another kind. Reading only: a pick on
    # a recorded-instrument slot is still this store's link.
    try:
        from jason.tasks.record_readback import key_document_summary

        slot_summary = key_document_summary(community, root, profile)
    except Exception as exc:  # noqa: BLE001 - the checklist stands without the slot reader
        slot_summary = {}
        notes.append(f"the record slots could not be read for the counts ({type(exc).__name__})")
    empty_slot = {"pins": 0, "read": 0, "wrongSlot": 0, "held": 0}
    for row in [*KEY_DOCUMENTS, None]:
        item = row.key if row is not None else "other"
        mine = [e for e in entries if e.item == item]
        if row is None and not mine:
            continue
        rows = []
        for entry in mine:
            status, why = status_of(entry, stored.get(entry.key))
            counts[status.value] = counts.get(status.value, 0) + 1
            made = entry_dict(entry, stored.get(entry.key), status, why, root)
            made["slot"] = (slot_summary.get(item) or {}).get("entries", {}).get(entry.key, dict(empty_slot)) if item in slot_summary else None
            rows.append(made)
        groups.append({
            "slot": ({k: v for k, v in slot_summary[item].items() if k != "entries"} if item in slot_summary else None),
            "item": item,
            "title": row.title if row else "Other documents a person added",
            "why": why_of(row) if row else "",
            "source": row.source if row else "",
            "recorded": bool(row and row.recorded),
            "repeats": bool(row and row.repeats),
            "entries": rows,
        })
    return {
        "found": True,
        "profile": profile,
        "association": getattr(community, "name", ""),
        "county": _county(community),
        "store": f"key-documents/{profile}.json",
        "counts": counts,
        "slotCounts": {"pins": sum(v["pins"] for v in slot_summary.values()), "read": sum(v["read"] for v in slot_summary.values()),
                       "wrongSlot": sum(v["wrongSlot"] for v in slot_summary.values()),
                       "held": sum(v["held"] for v in slot_summary.values())} if slot_summary else None,
        "statuses": [{"value": s.value, "meaning": STATUS_MEANING[s]} for s in KeyStatus],
        "groups": groups,
        "limits": {"maxUploadBytes": MAX_UPLOAD_BYTES, "suffixes": sorted(UPLOAD_SUFFIXES)},
        "notes": notes,
        "caveats": list(CAVEATS),
    }


def entry_dict(entry: Entry, stored: dict[str, Any] | None, status: KeyStatus, why: str, root: Path) -> dict[str, Any]:
    stored = stored or {}
    links = [_link_dict(link, root) for link in stored.get("links", [])]
    return {
        "key": entry.key,
        "item": entry.item,
        "title": stored.get("title") or entry.title,
        "number": entry.number,
        "recorded": entry.recorded,
        "phase": entry.phase,
        "role": entry.role,
        "filing": entry.filing,
        "supersededBy": entry.superseded_by,
        "sections": list(entry.sections),
        "status": status.value,
        "statusWhy": why,
        "statusBy": (stored.get("status") or {}).get("by", "") if isinstance(stored.get("status"), dict) else "",
        "copies": [_copy_dict(c, root) for c in entry.copies],
        "links": [link for link in links if not link["unlinked"]],
        "unlinked": [link for link in links if link["unlinked"]],
        "leads": entry.leads,
        "notes": entry.notes,
        "sources": entry.sources,
        "log": list(stored.get("log", []))[-8:],
    }


RECORDED_COPY = "Recorded copy"


def _file_doc(rel: str, name: str, root: Path, source: str = "") -> dict[str, Any] | None:
    """A file under data/ as a document reference (``file:<path>``), when it is one the console can open: on disk and of
    a type it shows. ``source`` names the copy ("Recorded copy") over the place's own word."""
    from jason.approvals.docref import file_ref

    if not rel or Path(rel).suffix.lower() not in _SERVED or not (root / rel).is_file():
        return None
    try:
        ref = file_ref(rel, name=name or None, data_dir=root)
    except ValueError:
        return None
    return {**ref, "source": source} if source else ref


def _drive_doc(ident: str, name: str, root: Path) -> dict[str, Any] | None:
    """A Drive file as a document reference (``drive:<id>``): jason's copy of it, with Open in Google as its original."""
    from jason.approvals.docref import drive_ref

    try:
        return drive_ref(ident, name=name or None, data_dir=root) if ident else None
    except ValueError:
        return None


def _copy_dict(copy: Any, root: Path) -> dict[str, Any]:
    """One copy jason sees, with ``doc``, its document reference: a recorded copy on disk as "Recorded copy", a Drive pin
    as jason's copy of it. A file on disk carries no URL into data/; a Drive pin keeps its Google ``url``."""
    out = copy.as_dict()
    if copy.kind == "disk":
        out.pop("url", None)
        doc = _file_doc(copy.ref, copy.name, root, RECORDED_COPY)
    else:
        doc = _drive_doc(copy.ref, copy.name, root)
    if doc:
        out["doc"] = doc
    return out


def _link_dict(link: dict[str, Any], root: Path) -> dict[str, Any]:
    """One copy a person linked, with ``doc``, its document reference: a file under data/ or an upload (``file:``), a
    Drive file (``drive:``), or a PayHOA library document by its copy on disk. A file carries no URL into data/."""
    out = {k: v for k, v in link.items() if k != "url"}
    kind = link.get("kind")
    name = str(link.get("name") or "")
    doc = None
    if kind in (LinkKind.FILE.value, LinkKind.UPLOAD.value):
        doc = _file_doc(str(link.get("ref") or ""), name, root)
    elif kind == LinkKind.DRIVE.value:
        out["url"] = drive_url(link.get("ref", ""))
        doc = _drive_doc(str(link.get("ref") or ""), name, root)
    elif kind == LinkKind.PAYHOA.value and link.get("localPath"):
        doc = _file_doc(str(link["localPath"]), name, root)
    if doc:
        out["doc"] = doc
    return out


def _check_key(key: str) -> str:
    key = str(key or "").strip()
    if not valid_key(key):
        raise ValueError(f"{key!r} is not a key document: a row of the list ({', '.join(r.key for r in KEY_DOCUMENTS)}), "
                         "<row>/<recording number>, or other/<name>")
    return key


def _under(root: Path, path: str) -> Path:
    """A path under data/ (relative to it, or absolute inside it); ValueError otherwise."""
    target = Path(path)
    target = (target if target.is_absolute() else root / target).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"{path}: a linked file is one under the data folder; upload a file from elsewhere instead")
    if not target.is_file():
        raise ValueError(f"{path}: no such file under the data folder")
    return target


def _payhoa_document(root: Path, ident: str) -> tuple[str, str]:
    """The library file's name and its local copy under data/, from the catalog on disk when it holds the id."""
    catalog = root / "payhoa.db"
    if not catalog.is_file():
        return "", ""
    try:
        with sqlite3.connect(f"file:{catalog}?mode=ro", uri=True) as conn:
            row = conn.execute("SELECT file_name, path, directory FROM documents WHERE id = ?", (int(ident),)).fetchone()
    except sqlite3.Error:
        return "", ""
    if row is None:
        raise ValueError(f"PayHOA library document {ident} is not in the catalog on disk (jason sync-catalog reads it again)")
    if row[2]:
        raise ValueError(f"PayHOA library item {ident} is a folder, not a document")
    local = root / "payhoa-files" / "documents" / str(row[1] or "")
    return str(row[0] or ""), (local.relative_to(root).as_posix() if row[1] and local.is_file() else "")


def link(key: str, *, by: str, file: str = "", drive: str = "", payhoa: str = "", note: str = "", title: str = "",
         root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """Link one existing copy to a key document: exactly one of ``file`` (under data/), ``drive``, or ``payhoa``."""
    root = _root(root)
    key = _check_key(key)
    given = [x for x in (file, drive, payhoa) if str(x or "").strip()]
    if len(given) != 1:
        raise ValueError("link one copy: a file under data/, a Drive id or link, or a PayHOA library document id")
    store = KeyDocumentStore(root, _profile(profile))
    if file:
        target = _under(root, file)
        digest, size = file_digest(target)
        out = store.link(key, LinkKind.FILE, target.relative_to(root.resolve()).as_posix(), by=by, name=target.name,
                         sha256=digest, size=size, note=note, title=title)
    elif drive:
        ident = drive_id(drive)
        out = store.link(key, LinkKind.DRIVE, ident, by=by, name=_drive_name(root, ident) or ident, note=note, title=title)
    else:
        ident = payhoa_id(payhoa)
        name, local = _payhoa_document(root, ident)
        out = store.link(key, LinkKind.PAYHOA, ident, by=by, name=name or f"PayHOA document {ident}", note=note, title=title)
        if local and not out.get("localPath"):
            _set_link_field(store, key, out["id"], "localPath", local)
            out["localPath"] = local
    return _link_dict(out, root)


def _drive_name(root: Path, ident: str) -> str:
    """The file's name in the Drive catalog on disk (``jason drive --sync``), when it holds the id."""
    try:
        raw = json.loads((root / "drive" / "files.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return next((str(f.get("name") or "") for f in raw.get("files", []) if f.get("id") == ident), "")


def _set_link_field(store: KeyDocumentStore, key: str, link_id: str, field: str, value: str) -> None:
    def change(entry: dict[str, Any]) -> None:
        for held in entry["links"]:
            if held["id"] == link_id:
                held[field] = value

    store._change(key, change, purpose="key documents: link")


def upload(key: str, *, by: str, name: str = "", data: bytes | None = None, base64_body: str = "", path: str = "",
           note: str = "", title: str = "", root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """Copy a file a person chose into ``key-documents/<profile>/files/`` and link it. The bytes come from ``data``,
    from ``base64_body`` (the browser's upload, at most ``MAX_UPLOAD_BYTES`` decoded), or from ``path``, a file the
    server can read (a regular file with a document suffix, under the same limit)."""
    root = _root(root)
    key = _check_key(key)
    if not str(by or "").strip():
        raise ValueError("say who is doing this: a write records its person (by)")
    store = KeyDocumentStore(root, _profile(profile))
    if path:
        source = Path(path).expanduser()
        if not source.is_file():
            raise ValueError(f"{path}: no such file on this machine")
        if source.stat().st_size > MAX_UPLOAD_BYTES:
            raise ValueError(f"{source.name} is over {MAX_UPLOAD_BYTES // (1024 * 1024)} MB; put it on Drive and link it there")
        name = name or source.name
        data = source.read_bytes()
    elif base64_body:
        if len(base64_body) > (MAX_UPLOAD_BYTES // 3 + 2) * 4 + 4:
            raise ValueError(f"the file is over {MAX_UPLOAD_BYTES // (1024 * 1024)} MB; put it on Drive and link it there")
        try:
            data = base64.b64decode(base64_body.split(",", 1)[-1] if base64_body.startswith("data:") else base64_body, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("the upload is not base64") from exc
    if data is None:
        raise ValueError("upload needs the file: a path the server can read, or its bytes")
    rel, digest, size = store.save_upload(safe_name(name), data)
    out = store.link(key, LinkKind.UPLOAD, rel, by=by, name=safe_name(name), sha256=digest, size=size, note=note, title=title)
    return _link_dict(out, root)


def unlink(key: str, link_id: str, *, by: str, note: str = "", root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    root = _root(root)
    out = KeyDocumentStore(root, _profile(profile)).unlink(_check_key(key), link_id, by=by, note=note)
    return _link_dict(out, root)


def set_status(key: str, value: str, *, by: str, note: str = "", root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    try:
        status = KeyStatus(str(value or "").strip())
    except ValueError as exc:
        raise ValueError(f"{value!r} is not a status: one of expected, located, held, missing") from exc
    return KeyDocumentStore(_root(root), _profile(profile)).set_status(_check_key(key), status, by=by, note=note)


def markdown(data: dict[str, Any]) -> str:
    """The checklist as a page: each group, each entry with its number, status, and copies."""
    lines = [f"# Key documents: {data.get('association', '')}", "",
             " · ".join(f"{k} {v}" for k, v in sorted(data.get("counts", {}).items())), ""]
    for group in data["groups"]:
        lines += [f"## {group['title']}", ""]
        if group.get("why"):
            lines += [group["why"], ""]
        lines += ["| Document | Number | Recorded | Status | Copies |", "| --- | --- | --- | --- | --- |"]
        for e in group["entries"]:
            copies = "; ".join([c["name"] for c in e["copies"]] + [l["name"] for l in e["links"]])
            title = e["title"] + (f" (superseded by {e['supersededBy']})" if e.get("supersededBy") else "")
            lines.append(f"| {_cell(title)} | {e['number']} | {e['recorded']} | {e['status']} | {_cell(copies)} |")
        lines.append("")
    lines += [*(f"- {n}" for n in data.get("notes", [])), *(f"> {c}" for c in data.get("caveats", [])), ""]
    return "\n".join(lines)


def _cell(text: str) -> str:
    return " ".join(str(text).replace("|", "/").split())


__all__ = ["CAVEATS", "checklist", "copies_on_disk", "entries_for", "entry_dict", "link", "located_rows", "markdown",
           "set_status", "unlink", "upload"]
