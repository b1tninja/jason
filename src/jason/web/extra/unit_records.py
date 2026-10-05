"""The loaders for community facts, a unit's record, and the loss packet: ``GET /api/facts``, ``/api/unit-record``,
``/api/loss-packet``. Disk only (jason.tasks.unit_records_view); nothing here calls PayHOA, Google, or a model."""

from __future__ import annotations

from typing import Any

Args = dict[str, str]


def _root():
    from jason.mcp.county import _data_dir

    return _data_dir(None)


def facts(args: Args) -> dict[str, Any]:
    from jason.community import community
    from jason.tasks import unit_records_view as v

    return v.facts_view(_root(), community(), topic=args.get("topic", "").strip(), q=args.get("q", ""),
                        scope=args.get("scope", "").strip(), status=args.get("status", "").strip())


def unit_record(args: Args) -> dict[str, Any]:
    """``unit`` (the PayHOA unit id) is required (a 400 without it); ``plan`` names the unit's floor plan."""
    from jason.community import community
    from jason.tasks import unit_records_view as v

    return v.unit_record_view(_root(), community(), args.get("unit", "").strip(), plan=args.get("plan", "").strip())


def loss_packet(args: Args) -> dict[str, Any]:
    from jason.community import community
    from jason.tasks import unit_records_view as v

    return v.loss_packet_view(_root(), community(), args.get("unit", "").strip(), args.get("incident", "").strip(),
                              address=args.get("address", "").strip())


def _by(body: dict[str, Any]) -> str:
    """The person who makes the record: the signed-in name when there is one, else the ``by`` the request names."""
    from jason.web import signin

    try:
        signed = signin.signed_in_name()
    except RuntimeError:  # called outside a request (a script, a test): only the name the caller gives
        signed = ""
    return signed or str(body.get("by", "")).strip()


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
