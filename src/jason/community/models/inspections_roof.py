"""The roof inspection report: RoofChecks' per-building estimate (North American Home Services, later Good Life Inspections).

No statute sets a roof inspection. The declaration makes the roof coverings, roof structures, gutters, and downspouts
the association's to maintain, repair, and replace (Article 7, Association Maintenance Responsibility), and its mold
program has the association keep rain gutters and roof drainage clean and check the common area for leaks (Article 7,
Mold Contamination). A leak's damage inside a unit is the owner's unless the association was grossly negligent (Article
7, Owner Responsibility for Consequential Damage). The reserve study carries each tile roof's remaining life.

RoofChecks sells the inspection as the step to a 24-month roof certification: the report is an estimate, one section per
building (roof info, findings, repairs), then the price. ``RoofInspection`` reads both layouts the association holds:
the July 2023 report (NAHS; one roof info block and one subtotal per building) and the January 2026 report (Good Life;
one roof info block, findings and repairs per building, one subtotal). A change order in the same form ("Building 3:
Replace ...") reads as one more report. The report's own age and life remaining are the inspector's; the checks set
them beside the building's public report and the reserve study, and say where they disagree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from jason.community.document_models import (
    DocumentModel,
    Finding,
    ModelContext,
    Severity,
    cents,
    date_after,
    first,
    register,
    squash,
)
from jason.community.models.legal_shared import building_number
from jason.community.symbols import Building, ComponentMajor, CostCenter, DocumentKind

_TITLE = re.compile(r"ROOF (?:INFO|FINDINGS|REPAIRS):", re.I)
_HEADING = re.compile(r"ROOF (INFO|FINDINGS|REPAIRS):[ \t]*(?:Building[ \t]*(\d))?", re.I)
_END = re.compile(r"We hereby propose|A complete set of roof pictures|SUBTOTAL:|Terms and Conditions|To schedule repairs", re.I)
# Lines every section repeats; they say how the inspection was done, not what it found.
_BOILERPLATE = re.compile(r"price subject to change|no way to confirm|repairs are discovered during|reflected on final invoice|"
                          r"inspection was completed with a drone|has been inspected via drone|drone inspections are|"
                          r"chimney and sidewall flashings cannot|surroundings clues|prime and painting", re.I)
_SOLAR = re.compile(r"under solar panels could not be inspected", re.I)
_DEBRIS = re.compile(r"debris|bird|pigeon|nest", re.I)
_METAL = re.compile(r"metal roof specialist|standing seam", re.I)


@dataclass(frozen=True)
class RoofSection:
    """One building's part of the report."""

    building: Building | None
    covering: str = ""                 # "Monier Flat Tile", "Tile"
    layers: int | None = None
    stated_age_years: int | None = None
    stated_life_remaining: str = ""    # "30+ yrs"
    pitch: str = ""                    # "4/12"
    findings: tuple[str, ...] = ()
    repairs: tuple[str, ...] = ()
    subtotal: int | None = None        # cents, when the report prices each building
    tiles_replaced: int = 0
    tiles_reset: int = 0
    joints_sealed: int = 0
    valleys_cleaned: int = 0
    not_inspected_under_solar: bool = False
    debris: bool = False               # debris, bird nesting, or blocked flashing noted
    metal_referral: bool = False       # standing-seam metal sections referred to another trade


@dataclass
class RoofInspection:
    firm: str = ""
    license: str = ""
    job_id: str = ""
    dated: date | None = None
    inspector: str = ""                # "Proposed By"
    site_address: str = ""
    drone: bool = False
    change_order: bool = False
    sections: tuple[RoofSection, ...] = ()
    total: int | None = None           # cents: the report's one subtotal, or the buildings' subtotals added


def _firm(text: str) -> str:
    """The name the estimate asks to be called for repairs; CuttingEdge Home Solutions traded as NAHS, then Good Life
    Inspections, and a later payment form attached to an older estimate carries the newer name."""
    contact = first(r"To schedule repairs please contact (?:the )?([A-Z][A-Za-z ]+?) Office", text)
    if contact:
        return contact
    if re.search(r"Good Life Inspections|GOODLIFE INSPECTIONS", text, re.I):
        return "Good Life Inspections"
    if re.search(r"NORTH AMERICAN|\bNAHS\b|nahspro", text, re.I):
        return "North American Home Services"
    return first(r"CuttingEdge Home Solutions[^\n]*?dba ([A-Z][A-Za-z ]+?)(?:\s*\(|\s+will|\n)", text)


def _items(body: str) -> list[str]:
    out = []
    for chunk in re.split(r"\n\s*-\s+", "\n" + body):
        line = squash(chunk)
        if line and not _BOILERPLATE.search(line) and not line.startswith("**"):
            out.append(line)
    return out


def _count(pattern: str, lines: tuple[str, ...]) -> int:
    return sum(int(m.group(1)) for line in lines for m in re.finditer(pattern, line, re.I))


def _info(body: str) -> dict:
    labels = re.sub(r"Type:|Layers:|Estimated Age:|Est\. Life Remaining:|\|?\s*Roof Pitch:", " ", body)
    years = re.findall(r"(\d+\+?)\s*yrs", labels)
    covering = first(r"((?:Monier\s+)?(?:Flat\s+|Spanish\s+|Concrete\s+|Clay\s+)?Tile|Composition Shingle|Shingle|Metal)", labels)
    return {"covering": covering,
            "layers": int(first(r"(?:^|\s)([1-3])(?:\s|$)", labels) or 0) or None,
            "stated_age_years": int(years[0]) if years and years[0].isdigit() else None,
            "stated_life_remaining": f"{years[1]} yrs" if len(years) > 1 else "",
            "pitch": first(r"\b(\d{1,2}/12)\b", labels)}


def _section(building: Building | None, info: dict, findings: list[str], repairs: list[str], subtotal: int | None) -> RoofSection:
    rep = tuple(repairs)
    everything = " ".join(findings + repairs)
    return RoofSection(
        building, info.get("covering", ""), info.get("layers"), info.get("stated_age_years"), info.get("stated_life_remaining", ""),
        info.get("pitch", ""), tuple(findings), rep, subtotal,
        tiles_replaced=_count(r"(?:replace|mend)\s+(?:up to\s+|the\s+)?(\d+)\s+(?:broken\s+)?(?:field\s+|rake\s+|ridge\s+)?tiles?", rep),
        tiles_reset=_count(r"reset and secure\s+(?:up to\s+)?(\d+)", rep),
        joints_sealed=_count(r"seal\s+(\d+)\s+joints?", rep),
        valleys_cleaned=_count(r"\((\d+)\)\s*valley", rep),
        not_inspected_under_solar=bool(_SOLAR.search(everything)),
        debris=bool(_DEBRIS.search(everything)),
        metal_referral=bool(_METAL.search(everything)))


def read_sections(text: str) -> tuple[list[RoofSection], int | None]:
    """The report's buildings in order, and its one subtotal when it prices the whole job at once."""
    heads = list(_HEADING.finditer(text))
    info_all: dict = {}
    per: dict[int | None, dict] = {}
    order: list[int | None] = []
    subtotals: list[tuple[int, int]] = [(m.start(), cents("$" + m.group(1)) or 0)
                                        for m in re.finditer(r"SUBTOTAL:\s*\n?\s*\$\s*([\d,]+(?:\.\d\d)?)", text)]
    for i, head in enumerate(heads):
        stop = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[head.end():stop]
        end = _END.search(body)
        body = body[:end.start()] if end else body
        part, number = head.group(1).upper(), head.group(2)
        building = int(number) if number else None
        if part == "INFO":
            info = _info(body)
            if building is None:
                info_all = info
            else:
                per.setdefault(building, {"findings": [], "repairs": []})["info"] = info
            continue
        items = _items(body)
        if building is None:
            # A change order: "Building 3: Replace up to 40 ft sq of damaged sheathing near valley."
            for item in items:
                prefix = re.match(r"Building\s*(\d)\s*:\s*(.*)", item, re.I)
                key = int(prefix.group(1)) if prefix else None
                slot = per.setdefault(key, {"findings": [], "repairs": []})
                if key not in order:
                    order.append(key)
                slot["findings" if part == "FINDINGS" else "repairs"].append(prefix.group(2) if prefix else item)
            continue
        slot = per.setdefault(building, {"findings": [], "repairs": []})
        if building not in order:
            order.append(building)
        slot["findings" if part == "FINDINGS" else "repairs"].extend(items)
        if part == "REPAIRS":
            later = [s for pos, s in subtotals if pos > head.start() and (i + 1 >= len(heads) or pos < heads[i + 1].start())]
            if later and len(subtotals) > 1:
                slot["subtotal"] = later[0]
    sections = [_section(building_number(b), per[b].get("info") or info_all, per[b]["findings"], per[b]["repairs"], per[b].get("subtotal"))
                for b in order]
    whole = subtotals[0][1] if len(subtotals) == 1 else None
    return sections, whole


def _built_years(context: ModelContext) -> dict[Building, int]:
    """Each building's first year of sales, from its public report: the roof went on before it."""
    community = context.community
    if community is None or not hasattr(community, "public_reports"):
        return {}
    out: dict[Building, int] = {}
    for rep in community.public_reports():
        days = [d for d in (getattr(rep, "opened", None), getattr(rep, "issued", None), rep.first_conveyance) if d]
        if days:
            year = min(days).year
            out[rep.building] = min(year, out.get(rep.building, year))
    return out


def _phases(context: ModelContext) -> dict[Building, int]:
    community = context.community
    if community is None or not hasattr(community, "public_reports"):
        return {}
    return {rep.building: rep.phase for rep in community.public_reports()}


def _tile_components(context: ModelContext) -> dict[CostCenter, object]:
    community = context.community
    if community is None or not hasattr(community, "reserve_components"):
        return {}
    return {c.cost_center: c for c in community.reserve_components()
            if c.major is ComponentMajor.ROOFING and re.search(r"\bTile\b", c.description)}


class RoofInspectionModel(DocumentModel):
    kind = DocumentKind.INSPECTION_REPORT
    name = "roofchecks-roof-inspection"
    required = ("firm", "dated", "sections")

    def parse(self, text: str, context: ModelContext) -> RoofInspection | None:
        if not _TITLE.search(text or "") or not re.search(r"roof inspection|ROOFCHECKS|visual roof", text or "", re.I):
            return None
        r = RoofInspection(firm=_firm(text))
        r.license = first(r"Contractor'?s License Number:\s*(\d{5,})", text) or first(r"Roof License #:\s*(\d{5,})", text)
        r.job_id = first(r"Job ID:\s*([\d-]{8,})", text)
        r.dated = date_after(r"\bDate:", text, window=40)
        r.inspector = first(r"Proposed By:\s*\n?\s*([A-Z][a-z]+(?: [A-Z][a-z]+)+)", text)
        r.site_address = first(r"(\d{3,5} [A-Z][a-z]+ (?:Drive|Dr|Walk|Lane|Ln))\b", text[:1500])
        r.drone = bool(re.search(r"\bdrone\b", text, re.I))
        r.change_order = bool(re.search(r"change order", context.name or "", re.I)) or \
            bool(re.search(r"ROOF REPAIRS:\s*\n\s*-\s*Building\s*\d\s*:", text, re.I))
        sections, whole = read_sections(text)
        r.sections = tuple(sections)
        priced = [s.subtotal for s in sections if s.subtotal]
        r.total = whole if whole is not None else (sum(priced) if priced else None)
        return r

    def check(self, r: RoofInspection, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if not r.license and not r.change_order:
            found.append(Finding("license-not-in-text", "the report prints no contractor's license number; confirm the firm's CSLB "
                                 "license before repairs", Severity.CHECK, "BPC 7030.5"))
        if r.drone:
            found.append(Finding("drone-limited", "the roofs were inspected by drone, a limited visual inspection: valleys, wall "
                                 "flashings, and chimneys were not checked", Severity.INFO))
        unseen = [s.building for s in r.sections if s.not_inspected_under_solar and s.building]
        if unseen:
            found.append(Finding("not-inspected-under-solar", f"the roof under the solar panels was not inspected on buildings "
                                 f"{_names(unseen)}; the roof certification excludes it", Severity.CHECK))
        found += _age_findings(r, context)
        debris = [s.building for s in r.sections if s.debris and s.building]
        if debris:
            found.append(Finding("debris-at-flashings", f"debris or bird nesting at valleys or wall flashings on buildings "
                                 f"{_names(debris)}; the declaration's mold program keeps roof drainage clean", Severity.INFO))
        metal = [s.building for s in r.sections if s.metal_referral and s.building]
        if metal:
            found.append(Finding("metal-roof-referral", f"the standing-seam metal sections on buildings {_names(metal)} were referred to "
                                 "a metal roof specialist; nobody has priced them", Severity.CHECK))
        return found


def _names(buildings: list) -> str:
    return ", ".join(str(int(b)) for b in dict.fromkeys(buildings))


def _age_findings(r: RoofInspection, context: ModelContext) -> list[Finding]:
    found: list[Finding] = []
    if not r.dated:
        return found
    built, phases, tiles = _built_years(context), _phases(context), _tile_components(context)
    stated = {s.stated_age_years for s in r.sections if s.stated_age_years is not None}
    wrong = []
    for s in r.sections:
        if s.building is None or s.stated_age_years is None or s.building not in built:
            continue
        actual = r.dated.year - built[s.building]
        if abs(actual - s.stated_age_years) >= 3:
            wrong.append(f"building {int(s.building)} to {built[s.building]} (about {actual} year{'' if actual == 1 else 's'})")
    if wrong:
        same = f"{next(iter(stated))} years for every building" if len(stated) == 1 else "roof ages"
        found.append(Finding("stated-roof-age", f"the report states {same}; the public reports date {'; '.join(wrong)} "
                             "at the inspection. Read the reserve study's ages, not the inspector's", Severity.CHECK))
    for s in r.sections:
        if s.building is None or not s.stated_life_remaining or s.building not in phases:
            continue
        center = CostCenter.PHASE_1_AND_2 if phases[s.building] <= 2 else CostCenter.PHASE_3_TO_8
        tile = tiles.get(center)
        if tile is None or tile.last_completed_year is None:
            continue
        due = tile.last_completed_year + tile.useful_life_years
        stated_more = int(re.match(r"(\d+)", s.stated_life_remaining).group(1))
        left = due - r.dated.year
        if stated_more - left >= 10:
            found.append(Finding("life-remaining-vs-reserve-study",
                                 f"building {int(s.building)}: the report says {s.stated_life_remaining} left; the reserve study's "
                                 f"'{tile.description}' is due in {due} ({left} years)", Severity.INFO))
    return found


register(RoofInspectionModel())


__all__ = ["RoofSection", "RoofInspection", "RoofInspectionModel", "read_sections"]
