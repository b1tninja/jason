"""The key-documents and instrument-graph sources, and the key-documents write.

``key_documents(args)`` is the checklist (``jason.tasks.key_documents.checklist``): each key document with its
recording number, status, the copies jason sees, the links people made, and the locator's leads.

``instrument_graph(args)`` is the graph (``jason.tasks.instrument_graph``) as JSON with its Mermaid: ``?scope=``
``association`` (the default), ``parcel`` (``&parcel=APN``, comma-separated), ``unit`` (``&unit=N``), or ``all`` (every
parcel; slow). ``&around=NUMBER&depth=2`` keeps the part around one instrument. ``&view=private`` adds the private
persons, labeled by role and parcel, their names masked. ``reveal`` (``POST /api/write/instrument-graph/reveal`` with
``{by, scope, parcel, unit, around, depth}``) unmasks them: the private view with each private person's names, for the
people who work with the owners (owners' names are P1, ``docs/console/security-and-privacy.md``). It needs a person's
name (never "jason"; while someone is signed in, theirs), in the body because a URL never carries a name, and each
reveal is appended to ``data/console/reveals.jsonl`` (when, who, the scope, the parcel or unit, how many persons were
named, never the names). The default stays masked, so a screenshot or an export holds no name unless a person asked.

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


REVEALS = ("console", "reveals.jsonl")
_YES = ("1", "true", "yes", "on")


def _revealer(by: str) -> str:
    """Who asked to see the names: a person's name, never jason; while someone is signed in, that person."""
    who = " ".join(str(by or "").split())
    signed = ""
    try:
        from jason.web import signin

        acting = signin.acting_as()
        if acting is not None:
            raise ValueError(f"viewing as {acting.name or 'the ' + acting.role} (admin view): owners' names are shown "
                             "only to the person signed in, as themselves")
        signed = signin.signed_in_name()
    except RuntimeError:          # outside a request (a test, a script): no session to read
        signed = ""
    if signed:
        if who and who.casefold() != signed.casefold():
            raise ValueError(f"signed in as {signed}: the reveal goes on the record under the signed-in name, not {who}")
        who = signed
    if not who:
        raise ValueError("showing owners' names is a person's action: give by (your name)")
    if who.casefold() == "jason":
        raise ValueError("jason never asks to see owners' names: give a person's name")
    return who


def _log_reveal(row: dict[str, Any]) -> str:
    """Append one reveal to ``data/console/reveals.jsonl`` in one write (a reader never sees half a line)."""
    import json
    import os

    from jason.tasks.key_documents import _root

    path = _root(None).joinpath(*REVEALS)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0), 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)
    return "/".join(REVEALS)


def instrument_graph(args: Args) -> dict[str, Any]:
    """The graph, masked: the shared view, or with ``view=private`` the private persons labeled by role. A URL never
    carries a person's name (``docs/console/security-and-privacy.md``), so owners' names are shown by ``reveal``."""
    if str(args.get("names") or "").strip().lower() in _YES:
        raise ValueError("owners' names are shown by a person's POST to /api/write/instrument-graph/reveal "
                         "with by (their name), never by a URL")
    return _graph(args, names=False, by="")


def reveal(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /api/write/instrument-graph/reveal``: the graph with owners' names, for the person named in ``by`` (in the
    body, so the name never sits in a URL, a browser's history, or a server log); the reveal is logged."""
    if key != "reveal":
        raise KeyError(key)
    args = {k: str(v) for k, v in body.items() if k in ("scope", "parcel", "unit", "around", "depth") and v not in (None, "")}
    return _graph(args, names=True, by=_revealer(str(body.get("by") or "")))


def _graph(args: Args, *, names: bool, by: str) -> dict[str, Any]:
    from jason.community import community as active
    from jason.community.instrument_graph import View
    from jason.tasks import instrument_graph as ig

    the = active()
    scope = (args.get("scope") or "association").strip()
    view = View.PRIVATE if names or args.get("view") == "private" else View.SHARED
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
    data = ig.payload(graph, view, names=names)
    data["scope"] = scope
    data["names"] = names
    if names:
        from datetime import datetime, timezone

        named = sum(1 for n in data["nodes"] if n.get("partyKind") == "private" and n.get("names"))
        row: dict[str, Any] = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "by": by,
                               "what": "instrument-graph owners' names", "scope": scope, "named": named}
        for key in ("parcel", "unit", "around"):
            if (args.get(key) or "").strip():
                row[key] = args[key].strip()
        data["reveal"] = {**row, "log": _log_reveal(row)}
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
