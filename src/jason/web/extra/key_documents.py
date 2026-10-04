"""The key-documents and instrument-graph sources, and the key-documents write.

``key_documents(args)`` is the checklist (``jason.tasks.key_documents.checklist``): each key document with its
recording number, status, the copies jason sees, the links people made, and the locator's leads.

``instrument_graph(args)`` is the graph (``jason.tasks.instrument_graph``) as JSON with its Mermaid: ``?scope=``
``association`` (the default), ``parcel`` (``&parcel=APN``, comma-separated), ``unit`` (``&unit=N``), or ``all`` (every
parcel; slow). ``&around=NUMBER&depth=2`` keeps the part around one instrument. ``&view=private`` adds the private
persons, labeled by role and parcel; the console never receives their names.

``write(key, body)`` takes one action on one entry (``POST /api/write/key-documents/<key>``), with ``by``:

- ``{"action": "link", "kind": "file"|"drive"|"payhoa", "ref": ...}``: a file under data/, a Drive id or link, or a
  PayHOA library document id;
- ``{"action": "upload-ref", "path": ...}``: a file the server can read, copied into ``data/key-documents/<profile>/
  files/`` and linked;
- ``{"action": "upload", "name": ..., "base64": ...}``: the browser's file, at most ``MAX_UPLOAD_BYTES`` (25 MB)
  decoded, kept the same way; a larger file goes on Drive and is linked there;
- ``{"action": "unlink", "link": "<link id>"}``: the link is marked removed; the file stays;
- ``{"action": "status", "value": "missing"|"held"|"located"|"expected", "note": ...}``.

Reads and writes jason's own store only; nothing reaches Drive, PayHOA, or the county.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]

ACTIONS = ("link", "unlink", "upload-ref", "upload", "status")


def key_documents(args: Args) -> dict[str, Any]:
    from jason.tasks.key_documents import checklist

    return checklist()


def instrument_graph(args: Args) -> dict[str, Any]:
    from jason.community import community as active
    from jason.community.instrument_graph import View
    from jason.tasks import instrument_graph as ig

    the = active()
    scope = (args.get("scope") or "association").strip()
    view = View.PRIVATE if args.get("view") == "private" else View.SHARED
    if scope == "association":
        graph = ig.association_graph(the)
    elif scope in ("parcel", "unit"):
        apns = [a.strip() for a in (args.get("parcel") or "").split(",") if a.strip()]
        if scope == "unit":
            unit = (args.get("unit") or "").strip()
            if not unit.isdigit():
                raise ValueError("scope=unit needs &unit=N")
            apns = ig.unit_apns(the, int(unit))
            if not apns:
                return {"found": False, "note": f"unit {unit}: no parcel carries that number on this community"}
        if not apns:
            raise ValueError("scope=parcel needs &parcel=APN")
        association = ig.association_graph(the, readings=False, located=False, land=False)
        graph = ig.parcel_graph(the, None, apns, association=association)
    elif scope == "all":
        graph = ig.community_graph(the)
    else:
        raise ValueError("scope is association, parcel, unit, or all")
    if args.get("around"):
        try:
            graph = ig.focus(graph, args["around"].strip(), int(args.get("depth") or 2))
        except KeyError:
            return {"found": False, "note": f"{args['around']} is not on this graph"}
    data = ig.payload(graph, view)
    data["scope"] = scope
    return data


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    from jason.tasks import key_documents as kd

    action = str(body.get("action") or "").strip()
    by = str(body.get("by") or "")
    note = str(body.get("note") or "")
    title = str(body.get("title") or "")
    if action == "link":
        kind = str(body.get("kind") or "").strip()
        ref = str(body.get("ref") or "").strip()
        if kind not in ("file", "drive", "payhoa"):
            raise ValueError("link kind is file (under data/), drive, or payhoa")
        result = kd.link(key, by=by, note=note, title=title, **{kind: ref})
    elif action == "upload-ref":
        result = kd.upload(key, by=by, path=str(body.get("path") or ""), name=str(body.get("name") or ""), note=note, title=title)
    elif action == "upload":
        result = kd.upload(key, by=by, name=str(body.get("name") or ""), base64_body=str(body.get("base64") or ""), note=note, title=title)
    elif action == "unlink":
        result = kd.unlink(key, str(body.get("link") or ""), by=by, note=note)
    elif action == "status":
        result = kd.set_status(key, str(body.get("value") or ""), by=by, note=note)
    else:
        raise ValueError(f"action is one of {', '.join(ACTIONS)}")
    return {"ok": True, "action": action, "key": key, "result": result}
