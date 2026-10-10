"""The inspections and portals loaders (docs/console/handoff-inspections-and-portals.md).

``GET /api/document-codes``, ``/api/report-portal``, ``/api/filing-plan``, ``/api/backflow``, and ``/api/watchlist``. Each
reads jason's stores on disk and answers ``{found: false, note, command}`` when one is missing. None calls Gmail, Drive,
PayHOA, or a vendor's portal: a sync, a plan, and a fetch of the tester lists are jobs a person starts with the command
the answer names.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]


def _data_dir():
    from jason.mcp.county import _data_dir as data

    return data(None)


def _community():
    from jason.community import community

    return community()


def _vendor(key: str) -> Any:
    """The vendor portal row (``VendorPortal``) with a public report portal: the one named, else the first."""
    rows = [p for p in _community().vendor_portals() if p.reports]
    if key:
        rows = [p for p in rows if p.key == key]
    return rows[0] if rows else None


def _none(note: str = "The specification names no vendor with a public report portal (VendorPortal.reports).") -> dict[str, Any]:
    return {"found": False, "note": note}


def document_codes(args: Args) -> dict[str, Any]:
    from jason.tasks.document_codes import view

    return view(_data_dir(), args.get("doc", ""))


def report_portal(args: Args) -> dict[str, Any]:
    from jason.tasks.report_portals import portal_view

    portal = _vendor(args.get("key", ""))
    return portal_view(_data_dir(), portal) if portal else _none()


def filing_plan(args: Args) -> dict[str, Any]:
    from jason.tasks.report_portals import filing_plan_view

    portal = _vendor(args.get("key", ""))
    return filing_plan_view(_data_dir(), portal.key) if portal else _none()


def backflow(args: Args) -> dict[str, Any]:
    from jason.tasks.backflow import view

    return view(_data_dir(), _community())


def watchlist(args: Args) -> dict[str, Any]:
    from jason.tasks.backflow import watchlist as build

    return build(_data_dir(), _community())


__all__ = ["backflow", "document_codes", "filing_plan", "report_portal", "watchlist"]
