"""The paint screen's data and the paint tools' answers: the schedule against the catalog copy on disk.

Reads disk only. The catalog is the copy ``jason paint --refresh`` keeps at ``<data dir>/paint/sherwin-williams-colors.json``,
read whatever its age and never fetched here (``SherwinWilliams.load_offline``); with no copy every color is "not checked"
and the answer names the command. Reserve figures come from ``jason.mcp.county.reserve_study`` and are the preparer's.

A last-painted date is never made up: with no recorded source it is ``{"source": "needs input"}``.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.paint import FindingKind, Maker, PaintSchedule, check

CATALOG_FILE = Path("paint") / "sherwin-williams-colors.json"
REFRESH_COMMAND = "jason paint --refresh"
CAVEATS = (
    "A reading is evidence, not a pin.",
    "The catalog is the maker's current one, as of the copy's date; a color renamed or discontinued there may still be what was approved.",
    "Screens are not paint: a swatch's hex is the maker's screen value, so match from the chip or the sheen on the wall.",
    "The number on the schedule governs; jason changes no row, and the board decides what a renamed or discontinued color means.",
)
REPORTED_NOT_CHECKED = FindingKind.NOT_CHECKED.value
_DRIVE_ID = re.compile(r"\bDrive[:\s]+([A-Za-z0-9_-]{20,})")


def catalog_path(data_dir: Path) -> Path:
    return Path(data_dir) / CATALOG_FILE


def open_catalog(data_dir: Path) -> Any | None:
    """The catalog copy on disk, or None when there is none (or it cannot be read). Never calls the API."""
    from jason.sources.sherwin_williams import SherwinWilliams

    sw = SherwinWilliams(catalog_path(data_dir))
    try:
        loaded = sw.load_offline()
    except Exception:                       # a damaged copy is a missing one: the screen says to refresh it
        sw.close()
        return None
    if not loaded:
        sw.close()
        return None
    return sw


def _catalog_block(sw: Any | None) -> dict[str, Any]:
    if sw is None:
        return {"available": False, "command": REFRESH_COMMAND,
                "note": f"No catalog copy on disk, so no color is checked. A person runs `{REFRESH_COMMAND}` to fetch it."}
    return {"available": True, "fetched": sw.fetched.isoformat() if sw.fetched else None, "colors": len(sw.load()),
            "command": REFRESH_COMMAND}


def _source(source: str) -> dict[str, Any]:
    """The schedule's original as the profile names it, with its evidence address and document reference when it is a
    Drive file."""
    out: dict[str, Any] = {"source": source}
    found = _DRIVE_ID.search(source or "")
    if found:
        out["sourceAddress"] = f"drive:{found.group(1)}"
    return out


def _color_row(spec: Any, finding: Any | None, color: Any | None) -> dict[str, Any]:
    row: dict[str, Any] = {"scheme": spec.scheme, "code": spec.code, "maker": spec.maker.value,
                           "status": finding.kind.value if finding is not None else REPORTED_NOT_CHECKED}
    if finding is None or finding.kind in (FindingKind.NOT_CHECKED, FindingKind.NOT_FOUND):
        row["name"] = spec.name           # the printed name is all there is; the swatch is not filled from anything
        return row
    row["name"] = finding.catalog_name
    if finding.printed_name != finding.catalog_name:
        row["printedName"] = finding.printed_name
    row.update(hex=finding.hex, lrv=finding.lrv, exterior=finding.exterior)
    if color is not None:
        row["families"] = list(color.families)
    return row


def schedule_view(schedule: PaintSchedule, sw: Any | None) -> dict[str, Any]:
    findings = check(schedule, sw) if sw is not None else ()
    by_key = {(f.surface, f.scheme, f.code): f for f in findings}
    rows = []
    for row in schedule.rows:
        colors = []
        for spec in row.specs:
            finding = by_key.get((row.label, spec.scheme, spec.code))
            color = sw.color(spec.code) if sw is not None and spec.maker is Maker.SHERWIN_WILLIAMS else None
            colors.append(_color_row(spec, finding, color))
        rows.append({"label": row.label, "surface": row.surface.value, "note": row.note, "colors": colors})
    counts: dict[str, int] = {}
    for r in rows:
        for c in r["colors"]:
            counts[c["status"]] = counts.get(c["status"], 0) + 1
    return {"title": schedule.title, **_source(schedule.source), "prepared": schedule.prepared,
            "buildings": list(schedule.buildings), "schemes": list(schedule.scheme_numbers()), "rows": rows,
            "counts": counts, "needsAPerson": sum(f.needs_a_person for f in findings)}


def painting_expenditures(data_dir: Path, *, today: date | None = None, years: int = 12,
                          study: Any = None) -> dict[str, Any]:
    """The reserve study's planned painting expenditures for the next ``years`` fiscal years, each labeled with where it
    came from. Last painted is ``needs input``: the study's useful life is not read here, so no date is implied."""
    out: dict[str, Any] = {
        "next": [], "source": "reserve study (jason.mcp.county.reserve_study), the preparer's figures",
        "lastPainted": {"source": "needs input"},
        "note": "Last painted is not recorded here. An implied date needs the component's useful life, which this read does "
                "not return; it is left as needs input rather than guessed.",
    }
    if study is None:
        from jason.mcp.county import reserve_study as study
    first = (today or date.today()).year + 1
    try:
        for year in range(first, first + years):
            brief = study(year=year, data_dir=data_dir)
            if not brief.get("found"):
                out["reserveNote"] = brief.get("note") or "no reserve study on disk"
                break
            out.setdefault("study", brief.get("study"))
            for e in brief.get("plannedExpenditures") or ():
                text = f"{e.get('category', '')} {e.get('description', '')}"
                if "paint" in text.lower():
                    out["next"].append({"year": year, "description": e.get("description", ""),
                                        "category": e.get("category", ""), "costCents": int(e.get("costCents") or 0),
                                        "source": "reserve study"})
    except Exception as exc:                # the schedule stands without the reserve
        out["reserveNote"] = f"the reserve study could not be read: {type(exc).__name__}: {exc}"
        out["next"] = []
    return out


def view(data_dir: Path, community: Any, *, today: date | None = None, study: Any = None) -> dict[str, Any]:
    schedules = tuple(community.paint_schedules())
    if not schedules:
        return {"found": False, "note": "The association has no color schedule yet. `jason paint --read IMAGE` reads one from a picture.",
                "caveats": list(CAVEATS)}
    sw = open_catalog(data_dir)
    try:
        catalog = _catalog_block(sw)
        out: dict[str, Any] = {
            "found": True, "schedules": [schedule_view(s, sw) for s in schedules], "catalog": catalog,
            "catalogFetched": catalog.get("fetched"), "unavailable": [], "caveats": list(CAVEATS),
        }
    finally:
        if sw is not None:
            sw.close()
    if not catalog["available"]:
        out["unavailable"].append({"part": "catalog", "reason": catalog["note"]})
        out["note"] = catalog["note"]
    reserve = painting_expenditures(data_dir, today=today, study=study)
    out["reserve"] = reserve
    if reserve.get("reserveNote"):
        out["unavailable"].append({"part": "reserve", "reason": reserve["reserveNote"]})
    return out


def _where_used(community: Any, code: str) -> list[dict[str, Any]]:
    from jason.sources.sherwin_williams import number_of

    try:
        want = number_of(code)
    except ValueError:
        return []
    used = []
    for schedule in community.paint_schedules():
        for row, spec in schedule.specs():
            try:
                if spec.maker is Maker.SHERWIN_WILLIAMS and number_of(spec.code) == want:
                    used.append({"schedule": schedule.title, "surface": row.label, "scheme": spec.scheme, "printedName": spec.name})
            except ValueError:
                continue
    return used


def _swatch(c: Any) -> dict[str, Any]:
    return {"code": c.code, "name": c.name, "hex": c.hex, "lrv": c.lrv, "exterior": c.exterior, "archived": c.archived}


def color_detail(data_dir: Path, community: Any, code: str, *, near: int = 5) -> dict[str, Any]:
    """One color: its catalog data, coordinating and similar colors (from the catalog on disk), where the schedule uses it,
    and, when the maker has discontinued it, the closest current colors."""
    code = (code or "").strip()
    if not code:
        raise ValueError("a color number is required (SW 7027)")
    sw = open_catalog(data_dir)
    if sw is None:
        return {"found": False, "catalog": _catalog_block(None), "note": _catalog_block(None)["note"], "caveats": list(CAVEATS)}
    try:
        color = sw.color(code)
        if color is None:
            return {"found": False, "code": code, "catalog": _catalog_block(sw),
                    "note": f"The catalog copy has no color {code!r}.", "caveats": list(CAVEATS)}
        related = sw.related(code)
        out: dict[str, Any] = {
            "found": True, **_swatch(color), "families": list(color.families), "collections": list(color.collections),
            "interior": color.interior, "rgb": [color.red, color.green, color.blue],
            "coordinating": related.get("coordinatingColors", []), "similar": related.get("similarColors", []),
            "usedOn": _where_used(community, code), "catalog": _catalog_block(sw), "caveats": list(CAVEATS),
        }
        if color.archived:
            out["nearest"] = nearest(sw, color, count=near)
        return out
    finally:
        sw.close()


def nearest(sw: Any, color: Any, *, count: int = 5, exterior: bool | None = True) -> list[dict[str, Any]]:
    return [{**_swatch(c), "distance": round(d, 1)} for d, c in sw.nearest(color, count=count, exterior=exterior)]


def match(data_dir: Path, code: str, *, count: int = 5, exterior: bool = True) -> dict[str, Any]:
    """The closest current colors to ``code`` by CIE76 distance (about 2.3 is the least a person notices)."""
    sw = open_catalog(data_dir)
    if sw is None:
        return {"found": False, "catalog": _catalog_block(None), "note": _catalog_block(None)["note"], "caveats": list(CAVEATS)}
    try:
        color = sw.color(code)
        if color is None:
            return {"found": False, "code": code, "catalog": _catalog_block(sw),
                    "note": f"The catalog copy has no color {code!r}.", "caveats": list(CAVEATS)}
        return {"found": True, "color": _swatch(color), "exteriorOnly": exterior,
                "nearest": nearest(sw, color, count=count, exterior=True if exterior else None),
                "catalog": _catalog_block(sw), "caveats": list(CAVEATS)}
    finally:
        sw.close()
