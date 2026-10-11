"""The loaders for community facts, a unit's record, and the loss packet: ``GET /api/facts``, ``/api/unit-record``,
``/api/loss-packet``. Disk only (jason.tasks.unit_records_view); nothing here calls PayHOA, Google, or a model.

A unit's record and a loss packet are about one member's home (an owner's improvements, a claim): they open to a signed-in
person whose office opens P2 (401 signed out, 403 otherwise), and the owner view never reads them. Their writers record a
person's act in the signed-in name only, refused while an admin views as someone else. Community facts are not about a
member, and stay as they were."""

from __future__ import annotations

from typing import Any

Args = dict[str, str]


ACTING_REFUSED = "Viewing as {who} (admin view): this record is written in a person's own name. Go back to yourself first."


def _root():
    from jason.mcp.county import _data_dir

    return _data_dir(None)


def _viewer(*, writing: bool = False):
    """The signed-in viewer whose offices open P2, or abort: 401 signed out, 403 where the offices do not open P2 (and,
    for a write, while an admin views as someone else). None outside a request (a script or the Python API, where the
    caller is the person at the terminal)."""
    from flask import abort, has_request_context

    from jason.web import access

    if not has_request_context():
        return None
    viewer = access.signed_in()
    if writing and viewer.acting:
        abort(access.refusal(403, ACTING_REFUSED.format(who=viewer.label)))
    access.allow(viewer, access.Level.P2)
    return viewer


def facts(args: Args) -> dict[str, Any]:
    from jason.community import community
    from jason.tasks import unit_records_view as v

    return v.facts_view(_root(), community(), topic=args.get("topic", "").strip(), q=args.get("q", ""),
                        scope=args.get("scope", "").strip(), status=args.get("status", "").strip())


def unit_record(args: Args) -> dict[str, Any]:
    """``unit`` (the PayHOA unit id) is required (a 400 without it); ``plan`` names the unit's floor plan."""
    from jason.community import community
    from jason.tasks import unit_records_view as v

    _viewer()
    return v.unit_record_view(_root(), community(), args.get("unit", "").strip(), plan=args.get("plan", "").strip())


def loss_packet(args: Args) -> dict[str, Any]:
    from jason.community import community
    from jason.tasks import unit_records_view as v

    _viewer()
    return v.loss_packet_view(_root(), community(), args.get("unit", "").strip(), args.get("incident", "").strip(),
                              address=args.get("address", "").strip())


def _by(body: dict[str, Any]) -> str:
    """The person who makes the record: the signed-in person's name. A ``by`` in the body is never trusted over it (the write
    guard already refuses one naming someone else). Outside a request only the name the caller gives."""
    viewer = _viewer(writing=True)
    return viewer.account if viewer is not None else str(body.get("by", "")).strip()


def write_unit_record(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /api/write/unit-record/entry`` (unit, component, kind, what, ...) adds an entry; ``.../visibility`` (unit, id,
    visibility) changes who may see one. A person's act, in their name, into jason's own store."""
    from jason.tasks import unit_records_write as w

    unit = str(body.get("unit", "")).strip()
    if key == "entry":
        return w.add_entry(_root(), unit, body, by=_by(body))
    if key == "visibility":
        return w.set_visibility(_root(), unit, str(body.get("id", "")), str(body.get("visibility", "")), by=_by(body))
    raise KeyError(key)


def write_loss_packet(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /api/write/loss-packet/confirm`` (unit, incident, step, shows, note) records a person's confirmation of one
    step. jason confirms nothing itself."""
    from jason.tasks import unit_records_write as w

    if key != "confirm":
        raise KeyError(key)
    return w.confirm_step(_root(), str(body.get("unit", "")).strip(), str(body.get("incident", "")), body.get("step"),
                          shows=body.get("shows"), by=_by(body), note=str(body.get("note", "")))
