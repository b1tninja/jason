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
