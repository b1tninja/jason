"""A page for every owners' association the county's map and index show: its parcels, maps, documents, and changes.

The footprint comes from the land itself: a common-area parcel's last deed names the association that took it
(``asspy.land.common_area_owners``), that parcel's final map holds the community's other parcels, and a condominium
plan tied to the association (by the name the map gives it) holds its units. Each page has:

- the association as the index knows it (names, kind, standing, first and last recording, evidence);
- its maps and plans (recorder numbers and days), and the governing instruments tied to it;
- its parcels: units and common areas by land use, the common parcels it owns with the deeds that conveyed them;
- turnover: each parcel's last transfer, transfers by year;
- its recorded history: liens, releases, and other filings under its name, by year;
- what changed: the land store's events for its parcels and the watch's filings that name it or its owners;
- maps: ``map.svg`` drawn from the county's shapes, ``footprint.kml`` for Google Earth, ``footprint.geojson``, and,
  with ``map_books``, the assessor's map book pages as PDFs.

Owners are never named unless ``names``: the map publishes none, and a deed's names stay in the cache. Every tie is a
reading of the records, a lead, not a pin. Pages go under ``data/reports/hoa/<county>/`` and are never committed.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable

from asspy import County
from asspy.geo import kml, svg
from asspy.sacramento.gis import map_extension
from asspy.land import (
    COMMON_LAND_USES,
    LandStore,
    common_area_owners,
    events_for,
    footprint,
    read_deeds,
    recorded_number,
    sync_land_uses,
)

# Land uses a community holds in common, beyond the codes its deeds prove: the assessor's miscellaneous family.
_COMMONISH = re.compile(r"^(AQ|M)")


@dataclass
class HoaPage:
    """One association's page and what went into it."""

    key: str
    slug: str
    path: Path
    parcels: int = 0
    owned: int = 0
    maps: list[str] = field(default_factory=list)
    events: int = 0


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "association"


def _day(number: str) -> date | None:
    try:
        return date(int(number[:4]), int(number[4:6]), int(number[6:8])) if recorded_number(number) else None
    except ValueError:
        return None


def _md_table(header: list[str], rows: Iterable[Iterable[Any]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for row in rows:
        lines.append("| " + " | ".join(str(cell if cell not in (None, "") else "") .replace("|", "/") for cell in row) + " |")
    return lines


class _Context:
    """What every page reads, read once: the directory, the land store, plans and maps, links."""

    def __init__(self, county: County, land: LandStore) -> None:
        self.county = county
        self.land = land
        with county.associations() as directory:
            self.associations = {a.key: a for a in directory.associations()}
            self.sightings = directory.sightings_by_association()
            self.governing = {g.number: g for g in directory.governing()}
            self.links: dict[str, list] = defaultdict(list)
            for item in directory.links():
                self.links[item.association].append(item)
        self.divisions = self.land.divisions()
        self.maps = {f"S{d['map_book']}{d['map_page']}": d for d in self.divisions if d["kind"] == "final map" and d["map_book"]}
        self.plans = {d["number"]: d for d in self.divisions if d["kind"] == "condominium plan" and d["number"]}
        self.owners = common_area_owners(land)

    def find(self, key: str):
        """The directory's association for a key a deed spelled: the same key, or the one association whose key
        holds every word of it (or whose words it holds); None when none or several do."""
        if key in self.associations:
            return self.associations[key]
        words = set(key.split())
        found = [a for a in self.associations.values() if words <= set(a.key.split()) or set(a.key.split()) <= words and len(a.key.split()) > 2]
        return found[0] if len(found) == 1 else None

    def label(self, code: str) -> str:
        found = self.land.land_use(code) if code else None
        return " / ".join(p for p in (found["general"], found["specific"], found["occupancy"]) if p) if found else code


def _plan_parcels(gis, plan: dict) -> list[dict]:
    """The active parcels inside a condominium plan's polygon, as the land store keeps rows."""
    from asspy.sacramento.gis import LandDivision

    division = LandDivision("condominium plan", int(plan["object_id"]), plan["name"] or "", plan["number"] or "", None)
    return [vars(p) | {"subdivision_name": p.subdivision_name} for p in gis.parcels_in(division)]


def _rows_from_mapped(rows: list[dict]) -> list[dict]:
    """Mapped parcels (``MappedParcel`` fields) in the land store's row shape."""
    return [{"apn": r["apn"], "status": r.get("status", ""), "land_use": r.get("land_use", ""), "subdivision": r.get("subdivision", ""),
             "subdivision_name": r.get("subdivision_name", ""), "lot": r.get("lot", ""), "unit": r.get("unit", ""),
             "block": r.get("block", ""), "legal": r.get("legal", ""), "document_type": r.get("document_type", ""),
             "document_number": r.get("document_number", ""), "lot_size": r.get("lot_size")} for r in rows]


def association_page(ctx: _Context, key: str, out: Path, *, gis=None, recorder=None, names: bool = False,
                     map_books: bool = False, deeds: bool = False, today: date | None = None,
                     book_cache: Path | None = None) -> HoaPage:
    """Write one association's page (``README.md``) and its maps under ``out``; what went into it."""
    today = today or date.today()
    out.mkdir(parents=True, exist_ok=True)
    item = ctx.find(key)
    owned = ctx.owners.get(key, [])
    found = footprint(ctx.land, key, owned)
    parcels = {p["apn"]: p for p in found.parcels}
    plans = []
    for link in ctx.links.get(key, []):
        plan = ctx.plans.get(link.number)
        if plan is not None:
            plans.append((plan, link))
            if gis is not None:
                for row in _rows_from_mapped(_plan_parcels(gis, plan)):
                    parcels.setdefault(row["apn"], row)
    owned_apns = {p["apn"] for p in owned}
    if deeds and recorder is not None:
        read_deeds(recorder, ctx.land, [p["document_number"] for p in parcels.values()])
    codes = {p["land_use"] for p in parcels.values() if p["land_use"]}
    if gis is not None:
        sync_land_uses(gis, ctx.land, most=0, codes=codes)
    sightings = ctx.sightings.get(item.key if item else key, ())
    governing_numbers = {l.number for l in ctx.links.get(key, [])} | {
        g.number for g in ctx.governing.values() if key in g.associations}
    governing = sorted((ctx.governing[n] for n in governing_numbers if n in ctx.governing), key=lambda g: (g.recorded or date.min, g.number))
    events = events_for(ctx.land, apns=tuple(parcels), association=key)

    name = item.name if item else key
    lines = [f"# {name}", ""]
    if item:
        evidence = ", ".join(f"{label} {count}" for label, count in item.evidence.most_common())
        lines += [f"- Kind: {item.kind.value}; standing: {item.standing.value}",
                  f"- Recorded under its name: {item.first or '?'} to {item.last or '?'} ({evidence})"]
        spellings = sorted(set(item.names) - {item.name})
        if spellings:
            lines.append(f"- Also indexed as: {'; '.join(spellings[:8])}")
    else:
        lines.append("- Not yet in the association directory: found by the deed of a common-area parcel.")
    lines += [f"- Parcels on its map: {len(parcels)}; common parcels its deeds took: {len(owned)}; "
              f"maps: {', '.join(found.maps) or 'none'}; condominium plans: {len(plans)}",
              f"- Written {today.isoformat()} from the county's map (parcels, plans, maps) and recorder index. "
              "Each tie is a reading of the records, a lead, not a pin.", ""]

    # Formation: maps, plans, governing instruments, first recordings.
    timeline: list[tuple[date | None, str, str, str]] = []
    for map_id in found.maps:
        made = ctx.maps.get(map_id)
        if made:
            timeline.append((date.fromisoformat(made["recorded"]) if made["recorded"] else None,
                             made["number"] if recorded_number(made["number"] or "") else "",
                             "final map", f"{made['name']} (map {map_id}; {made['lots'] or '?'} lots, {made['lettered_lots'] or 0} lettered)"))
    for plan, link in plans:
        timeline.append((date.fromisoformat(plan["recorded"]) if plan["recorded"] else None, plan["number"], "condominium plan",
                         f"{plan['name']} (tied by {link.reason})"))
    for g in governing:
        timeline.append((g.recorded, g.number, g.filing.lower(), "; ".join([*g.parties[:3], *g.tracts[:2]])))
    if sightings:
        first = sightings[0]
        timeline.append((first.recorded, first.number, "first recording under its name", first.filing.lower()))
    timeline.sort(key=lambda row: (row[0] or date.min, row[1]))
    lines += ["## Formation", ""]
    lines += _md_table(["Recorded", "Number", "What", "Detail"], ((d or "", n, w, t) for d, n, w, t in timeline)) if timeline else ["None found."]
    lines.append("")

    # Parcels.
    by_use = Counter(p["land_use"] for p in parcels.values())
    lines += ["## Parcels", ""]
    lines += _md_table(["Land use", "Meaning", "Parcels"], ((code, ctx.label(code), n) for code, n in by_use.most_common()))
    lines += ["", "### Common parcels its deeds took", ""]
    if owned:
        lines += _md_table(["APN", "Lot", "Land use", "Deed", "Recorded", "Filing"],
                           ((p["apn"], p["lot"], ctx.label(p["land_use"]), p["deed"], _day(p["deed"]) or "", p["deed_filing"].lower()) for p in owned))
    else:
        lines.append("None found by deed.")
    others = [p for p in parcels.values() if p["apn"] not in owned_apns and _COMMONISH.match(p["land_use"] or "")]
    if others:
        lines += ["", "### Other parcels set apart from the homes (owner not read)", ""]
        lines += _md_table(["APN", "Lot", "Land use", "Last transfer"],
                           ((p["apn"], p["lot"], ctx.label(p["land_use"]), p["document_number"]) for p in others))
    lines.append("")

    # Turnover.
    years = Counter(d.year for d in (_day(p["document_number"] or "") for p in parcels.values()) if d)
    kinds = Counter(p["document_type"] for p in parcels.values() if p["document_type"])
    lines += ["## Turnover", "", "Each parcel's last transfer, by the year it was recorded (a parcel sold twice counts once, "
              "at its latest):", ""]
    lines += _md_table(["Year", "Parcels last transferred"], sorted(years.items(), reverse=True)[:25]) if years else ["None."]
    lines += ["", "Last transfers by the assessor's document type: " + ", ".join(f"{k} {n}" for k, n in kinds.most_common()) or "none", ""]
    homes = sorted((p for p in parcels.values() if not _COMMONISH.match(p["land_use"] or "")), key=lambda p: p["apn"])
    owner_col = names and deeds
    header = ["APN", "Lot", "Unit", "Land use", "Last transfer", "Recorded", "Type"] + (["Owners (last deed)"] if owner_col else [])

    def owner(p: dict) -> str:
        found_deed = ctx.land.deed(p["document_number"] or "")
        return "; ".join(found_deed.grantees) if found_deed else ""

    lines += ["### Every home parcel", ""]
    lines += _md_table(header, ((p["apn"], p["lot"], p["unit"], p["land_use"], p["document_number"], _day(p["document_number"] or "") or "",
                                 p["document_type"], *([owner(p)] if owner_col else [])) for p in homes))
    lines.append("")

    # Recorded history under its name.
    lines += ["## Recorded under its name", ""]
    if sightings:
        table: dict[int, Counter] = defaultdict(Counter)
        for s in sightings:
            table[s.recorded.year if s.recorded else 0][s.filing.split(";")[-1].strip().lower()] += 1
        lines += _md_table(["Year", "Filings"], ((y or "?", ", ".join(f"{f} {n}" for f, n in c.most_common())) for y, c in sorted(table.items(), reverse=True)))
        lines += ["", "<details><summary>Every recording</summary>", ""]
        lines += _md_table(["Recorded", "Number", "Filing", "As indexed"], ((s.recorded or "", s.number, s.filing.lower(), s.name) for s in sightings))
        lines += ["", "</details>"]
    else:
        lines.append("Nothing indexed under its name yet.")
    lines.append("")

    # Changes.
    lines += ["## What changed", ""]
    if events:
        lines += _md_table(["Detected", "Kind", "Parcel or document", "Recorded", "Why"],
                           ((e.detected[:10], e.kind, e.key, e.day or "", why) for e, why in events[:200]))
    else:
        lines.append("No changes since the land store began watching.")
    lines.append("")

    # Maps.
    lines += ["## Maps", ""]
    if gis is not None and parcels:
        apns = sorted(parcels)
        where = (f"SUBDIVISION IN ({','.join(repr(m) for m in found.maps)})" if found.maps and not plans
                 else "APN_DASH IN ({})".format(",".join(f"'{a}'" for a in apns[:900])))
        shapes = gis.features(where)
        if shapes:
            for shape in shapes:
                props = shape.setdefault("properties", {})
                props["owned"] = props.get("APN_DASH") in owned_apns
            (out / "footprint.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": shapes}), encoding="utf-8")

            def look(props: dict) -> dict:
                if props.get("owned"):
                    return {"fill": "#7fbf7f", "stroke": "#2f6f2f"}
                if _COMMONISH.match(props.get("LANDUSE") or ""):
                    return {"fill": "#cfe8c4", "stroke": "#5f8f5f"}
                return {"fill": "#dce6f2", "stroke": "#4a6785"}

            def lot(props: dict) -> str:
                text = (props.get("LOT") or "").strip()
                return text if text.isalpha() else ""

            (out / "map.svg").write_text(svg(shapes, style=look, title=name, label=lot), encoding="utf-8")
            (out / "footprint.kml").write_text(kml(shapes, name=name, title=lambda p: p.get("APN_DASH") or "",
                                                   color=lambda p: "a07fbf7f" if p.get("owned") else "7fdce6f2"), encoding="utf-8")
            lines += ["![The parcels on its maps: dark green the common parcels its deeds took, light green other land "
                      "set apart, blue the homes](map.svg)", "",
                      "- [footprint.kml](footprint.kml) opens in Google Earth; [footprint.geojson](footprint.geojson) in any GIS."]
    else:
        lines.append("Shapes not read (no map service given).")
    pages = sorted({re.sub(r"\D", "", a)[:6] for a in parcels if len(re.sub(r"\D", "", a)) >= 6})
    if pages:
        lines += ["", "Assessor's map book pages: " + ", ".join(f"{p[:3]}-{p[3:]}" for p in pages)]
        if map_books and gis is not None:
            folder = out / "map-book"
            folder.mkdir(exist_ok=True)
            for page in pages[:40]:
                held = next(iter(sorted(folder.glob(f"{page}.*"))), None)
                if held is None:
                    cached = next(iter(sorted(book_cache.glob(f"{page}.*"))), None) if book_cache and book_cache.exists() else None
                    body = cached.read_bytes() if cached is not None else gis.assessor_map(page)
                    kind = map_extension(body)
                    if kind:
                        held = folder / f"{page}.{kind}"
                        held.write_bytes(body)
                        if cached is None and book_cache is not None:
                            book_cache.mkdir(parents=True, exist_ok=True)
                            (book_cache / held.name).write_bytes(body)
                if held is not None:
                    lines.append(f"- [{page[:3]}-{page[3:]}](map-book/{held.name})")
    lines.append("")
    (out / "README.md").write_text("\n".join(lines), encoding="utf-8")
    return HoaPage(key, out.name, out / "README.md", len(parcels), len(owned), list(found.maps), len(events))


def build_reports(county_name: str, root: Path, *, only: Iterable[str] = (), limit: int = 0, shapes: bool = True,
                  names: bool = False, map_books: bool = False, deeds: bool = False, progress: Callable[[str], None] | None = None,
                  today: date | None = None) -> list[HoaPage]:
    """Write a page for every association the land shows (or those whose names hold ``only``'s words), and an index.
    ``shapes`` reads each footprint's shapes from the county's map; ``map_books`` the assessor's map pages; ``deeds``
    reads every parcel's last deed from the recorder (the owners' names, kept in the cache; shown only with ``names``)."""
    county = County(county_name)
    root = root / county.name.lower()
    root.mkdir(parents=True, exist_ok=True)
    gis = getattr(county.assessor, "gis", None) if shapes or map_books else None
    recorder = county.recorder if deeds else None
    pages: list[HoaPage] = []
    with county.land() as land:
        ctx = _Context(county, land)
        keys = sorted(set(ctx.owners) | {k for k, links in ctx.links.items() if any(l.number in ctx.plans for l in links)})
        wanted = [w.upper() for w in only]
        if wanted:
            keys = [k for k in keys if all(w in k for w in wanted)]
        if limit:
            keys = keys[:limit]
        cache = county.db_path.with_name("map-books")
        for key in keys:
            page = association_page(ctx, key, root / slug(key), gis=gis, recorder=recorder, names=names, map_books=map_books,
                                    deeds=deeds, today=today, book_cache=cache)
            pages.append(page)
            if progress is not None:
                progress(f"{key}: {page.parcels} parcels, {page.owned} owned, {page.events} events")
    index = [f"# Owners' associations on {county.name} County's map", "",
             f"{len(pages)} associations whose common land or condominium plan the records tie to them. "
             "Each tie is a reading of the records, a lead, not a pin.", ""]
    index += _md_table(["Association", "Parcels", "Common parcels owned", "Maps", "Changes"],
                       ((f"[{p.key}]({p.slug}/README.md)", p.parcels, p.owned, ", ".join(p.maps), p.events)
                        for p in sorted(pages, key=lambda p: -p.parcels)))
    (root / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return pages
