"""The paint screen's loaders: ``GET /api/paint`` and ``GET /api/paint/color?code=``.

Reads disk only: the schedule from the profile, the catalog copy on disk, and the reserve study's planned expenditures.
Nothing here calls Sherwin-Williams, Google, or PayHOA; the catalog is fetched only by a person's ``jason paint --refresh``.

The schedule and the catalog are the association's own, not a member's: a signed-in roster person reads them (401 signed
out); the owner view does not.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]


def _roster_person() -> None:
    """In a request, a signed-in roster person (401 otherwise); outside one (a script, the Python API) nothing to check."""
    from flask import has_request_context

    from jason.web import access

    if has_request_context():
        access.allow(access.signed_in(), access.Level.P0)


def paint_view(args: Args) -> dict[str, Any]:
    """Each schedule with its colors checked against the catalog copy, and the painting components' reserve dates."""
    from jason.community import community
    from jason.mcp.county import _data_dir
    from jason.tasks import paint_view as pv

    _roster_person()
    return pv.view(_data_dir(None), community())


def paint_color(args: Args) -> dict[str, Any]:
    """One color by ``code``: coordinating and similar colors from the catalog copy, and the closest current colors when
    the maker has discontinued it. ``ValueError`` (a 400) without a code."""
    from jason.community import community
    from jason.mcp.county import _data_dir
    from jason.tasks import paint_view as pv

    _roster_person()
    return pv.color_detail(_data_dir(None), community(), args.get("code", ""))
