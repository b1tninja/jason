"""The record checklist's sources and write (docs/record-intake.md, docs/console/handoff-record-intake.md).

``record_slots(args)`` is ``GET /api/record-slots`` (``?group=``, ``?state=``): the checklist by group, with every state,
count, and the biggest unknowns worked out here, so the page computes nothing. ``record_slot(args)`` is
``GET /api/record-slot?key=``: one slot with its law, holders, the library's reading of each, collisions, candidates, the
person's answer, what the office may do, and the trail. Both read disk only. A file in a confidential slot, or read as a
confidential kind, is named by its kind and its id shortened unless the private view is open for the signed-in person; the
key of a slot is in the URL, never a file's name or id.

``write(key, body)`` is ``POST /api/write/records/<slot key>`` (behind the write guard's token), with ``by``:

- ``{"act": "pick", "file": LINK_OR_ID, "period": "", "entry": "", "note": ""}``: a Drive link or id (or ``library:ID``);
  its name comes from the Drive catalog on disk when it holds the id (resolving a link in Drive, read-only, is the
  chooser's ``GET /api/drive/resolve`` of phase 2: the server opens no Google sign-in here);
- ``{"act": "answer", "value": "not_applicable"|"none"|"waiting", "note": ..., "who": ...}``;
- ``{"act": "unpin", "pin": ID}``.

The folder binding, the upload, the replacement, the wrong-slot overrides, and the confirmed split of the design come
later; asking for one is a 400 that says so. Writes jason's own stores only (``records.json``, the key documents' store for a
recorded instrument, and the history); nothing reaches Drive, PayHOA, or the county, and the picked file is never touched.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]

ACTS = ("pick", "answer", "unpin")
LATER = ("bind", "upload", "replace", "keep", "repin", "more", "split", "current")
VALUES = {"not_applicable": "notApplicable", "notapplicable": "notApplicable", "notApplicable": "notApplicable", "none": "none", "waiting": "waiting"}


def _private() -> bool:
    """Whether the private view is open on this request for a person whose offices open P3 in it."""
    try:
        from jason.web import access

        return bool(access.private_open())
    except Exception:  # noqa: BLE001 - outside a request (a script, a test) there is no private view
        return False


def _community() -> Any:
    from jason.community import community

    return community()


def _root() -> Any:
    from jason.mcp.county import _data_dir

    return _data_dir(None)


def record_slots(args: Args) -> dict[str, Any]:
    from jason.tasks import record_slots as rs

    return rs.view(_community(), _root(), group=(args.get("group") or "").strip(), state=(args.get("state") or "").strip(),
                   private=_private())


def record_slot(args: Args) -> dict[str, Any]:
    from jason.tasks import record_slots as rs

    key = (args.get("key") or "").strip()
    if not key:
        raise ValueError("a slot is named by its key: ?key=records/5200/minutes")
    return rs.slot_view(key, _community(), _root(), private=_private())


def _actor(by: str) -> str:
    """Who is doing this: while someone is signed in, that person (a different name is refused); else ``by``. Never jason."""
    who = " ".join(str(by or "").split())
    try:
        from jason.web import signin

        acting = signin.acting_as()
        if acting is not None:
            raise ValueError(f"viewing as {acting.name or 'the ' + acting.role} (admin view): a pick or an answer is made as yourself")
        signed = signin.signed_in_name()
    except RuntimeError:          # outside a request (a test, a script): no session to read
        signed = ""
    if signed:
        if who and who.casefold() != signed.casefold():
            raise ValueError(f"signed in as {signed}: the pick goes on the record under the signed-in name, not {who}")
        who = signed
    if not who:
        raise ValueError("A pick names who made it.")
    return who


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    from jason.tasks import record_slots as rs

    act = str(body.get("act") or "").strip()
    if act in LATER:
        raise ValueError(f"{act} is not built yet: the chooser, uploads, and the reading of a pick come in the next phases")
    if act not in ACTS:
        raise ValueError(f"act is one of {', '.join(ACTS)}")
    by = _actor(str(body.get("by") or ""))
    community, root = _community(), _root()
    try:
        if act == "pick":
            out = rs.pick(key, str(body.get("file") or ""), by=by, period=str(body.get("period") or ""),
                          note=str(body.get("note") or ""), entry=str(body.get("entry") or ""), dry_run=False,
                          community=community, root=root)
        elif act == "answer":
            value = VALUES.get(str(body.get("value") or "").strip())
            if value is None:
                raise ValueError("value is not_applicable, none, or waiting")
            out = rs.answer(key, value, by=by, reason=str(body.get("note") or ""), who=str(body.get("who") or ""), dry_run=False,
                            community=community, root=root)
        else:
            out = rs.unpin(key, by=by, pin=str(body.get("pin") or ""), note=str(body.get("note") or ""), dry_run=False,
                           community=community, root=root)
    except KeyError:
        raise KeyError(key) from None
    return {"ok": True, "act": act, "key": key, **{k: v for k, v in out.items() if k in ("written", "pin", "answer", "already", "reading")}}
