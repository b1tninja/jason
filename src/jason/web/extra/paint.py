"""The paint screen's loaders: ``GET /api/paint`` and ``GET /api/paint/color?code=``.

Reads disk only: the schedule from the profile, the catalog copy on disk, and the reserve study's planned expenditures.
Nothing here calls Sherwin-Williams, Google, or PayHOA; the catalog is fetched only by a person's ``jason paint --refresh``.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]


def paint_view(args: Args) -> dict[str, Any]:
    """Each schedule with its colors checked against the catalog copy, and the painting components' reserve dates."""
    from jason.community import community
    from jason.mcp.county import _data_dir
    from jason.tasks import paint_view as pv

    return pv.view(_data_dir(None), community())


def paint_color(args: Args) -> dict[str, Any]:
    """One color by ``code``: coordinating and similar colors from the catalog copy, and the closest current colors when
    the maker has discontinued it. ``ValueError`` (a 400) without a code."""
    from jason.community import community
    from jason.mcp.county import _data_dir
    from jason.tasks import paint_view as pv

    return pv.color_detail(_data_dir(None), community(), args.get("code", ""))
