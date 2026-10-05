"""The paint tools: the association's color schedule against the maker's catalog copy on disk. Read only.

Three tools. ``paint_colors`` is the schedule with each color's catalog data (or one color, with its coordinating and
similar colors), ``paint_check`` is what differs from the catalog, and ``paint_match`` is the closest current colors to
one. None calls Sherwin-Williams, Google, or PayHOA: the catalog is the copy ``jason paint --refresh`` keeps on disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jason.tasks.paint_view import CAVEATS


def _root(data_dir: Path | None) -> Path:
    from jason.mcp.county import _data_dir

    return _data_dir(data_dir)


def paint_colors(code: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """The association's paint schedule: each surface as printed, each scheme's color with its code, the maker's current
    name, hex, light reflectance (LRV), and whether it matches the catalog; with the reserve study's planned painting
    expenditures. With ``code`` (SW 7027), that one color: its families, coordinating and similar colors, where the
    schedule uses it, and for a discontinued color the closest current ones. Reads disk only. A reading is evidence,
    not a pin; the catalog is the maker's current one; screens are not paint; the number on the schedule governs."""
    from jason.community import community
    from jason.tasks import paint_view as pv

    root = _root(data_dir)
    if code:
        return pv.color_detail(root, community(), code)
    return pv.view(root, community())


def paint_check(data_dir: Path | None = None) -> dict[str, Any]:
    """Each schedule color that differs from the maker's catalog copy: renamed, discontinued, or not found (a color from
    another maker is not checked). Names compare ignoring case, spacing, punctuation, and grey/gray. jason changes no
    row; the board decides. Reads disk only. A reading is evidence, not a pin; the catalog is the maker's current one;
    screens are not paint; the number on the schedule governs."""
    from jason.community import community
    from jason.tasks import paint_view as pv

    out = pv.view(_root(data_dir), community())
    if not out.get("found"):
        return out
    findings = [
        {"schedule": s["title"], "surface": r["label"], **c}
        for s in out["schedules"] for r in s["rows"] for c in r["colors"] if c["status"] not in ("ok", "not checked")
    ]
    return {"found": True, "catalog": out["catalog"], "findings": findings, "count": len(findings),
            "checked": out["catalog"]["available"], "caveats": out["caveats"],
            **({"note": out["note"]} if out.get("note") else {})}


def paint_match(code: str, count: int = 5, exterior: bool = True, data_dir: Path | None = None) -> dict[str, Any]:
    """The closest current colors to ``code`` (SW 7027) in the maker's catalog copy, by CIE76 distance (about 2.3 is the
    least a person notices), for a discontinued color or a touch-up question; ``exterior`` limits them to colors the
    maker lists for exteriors. Reads disk only. A reading is evidence, not a pin; the catalog is the maker's current one;
    screens are not paint, so confirm against a chip; the number on the schedule governs."""
    from jason.tasks import paint_view as pv

    return pv.match(_root(data_dir), code, count=max(1, int(count)), exterior=bool(exterior))


TOOLS = (paint_colors, paint_check, paint_match)

__all__ = [t.__name__ for t in TOOLS] + ["TOOLS", "CAVEATS"]
