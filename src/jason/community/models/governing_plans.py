"""The subdivider's public reports and the drawings: the Bureau (DRE) public reports, the maps, the condominium plans,
and the city's entitlement files (plan sets).

A public report is the Department of Real Estate's permit to sell one phase: its file number (``160779SA`` with a form
suffix, ``-F00`` final, ``-A01`` amended, ``-C00`` conditional, ``-S00`` preliminary), the issue, amendment, and
expiration dates, the units and building it covers, the phase, and the budget it reviewed. The record is checked against
the specification's phase table (``mystique/reports.py``: ``PublicReport`` rows, joined by ``reports.report_file_number``).

The drawings are kept light: most are sheets with little text. A map records its kind, subdivision number, book and page,
date, and sheets; a condominium plan its stamp, the buildings and units it describes, the earlier plan it divides, and
its sheet count; a plan set the city file number, the project, the units and buildings, and the decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from jason.community.document_models import DocumentModel, Finding, ModelContext, Severity, date_after, dates_in, register, squash
from jason.community.reviews import AS_OF
from jason.community.symbols import DocumentKind

from .governing_deeds import copy_findings, copy_recording
from .governing_shared import (
    Recording,
    book_page_numbers,
    map_reference,
    ordinal,
    spec_reports,
)

_MONTH = r"(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)"


class ReportType(Enum):
    PRELIMINARY = "preliminary"
    CONDITIONAL = "conditional"
    FINAL = "final"
    AMENDED = "amended"


@dataclass
class PublicReportRecord:
    file_number: str = ""                 # "160779SA-F00"
    base_file_number: str = ""            # "160779SA": every copy and amendment of the report
    report_type: ReportType | None = None
    subdivider: str = ""
    subdivision: str = ""
    issued: date | None = None
    amended: date | None = None
    expires: date | None = None
    phase: int | None = None
    total_phases: int | None = None
    total_units: int | None = None
    first_unit: int | None = None
    last_unit: int | None = None
    units: int | None = None
    building: int | None = None
    common_area: int | None = None        # "ASSOCIATION COMMON AREA 8"
    built_out_assessment_cents: int | None = None
    phase_assessment_cents: int | None = None
    built_out_reserve_cents: int | None = None       # "of which $15.25 is a monthly contribution to long-term reserves"
    cost_center_assessment_cents: int | None = None  # "Under the Cost Center built-out budget, monthly assessment ... will be $116.60"
    cost_center_reserve_cents: int | None = None     # the cost center assessment's monthly contribution to reserves
    phase_reserve_cents: int | None = None           # "Of these amounts ... reserves ... are $15.25 and $28.75, respectively": the second
    cost_center_phase_assessment_cents: int | None = None  # "Under the 3rd phase Cost Center budget, the monthly assessment ... is $120.15"
    cost_center_phase_reserve_cents: int | None = None
    adopted_assessment_cents: int | None = None      # "Current Adopted Budget (Phase 2): $275 per month", the association's rate then


def _file_number(flat: str) -> tuple[str, str]:
    hit = re.search(r"(\d{6}SA)\s?-?\s?([A-Z][O0\d]{2}(?:\s?/\s?[A-Z][O0\d]{2})?)", flat)
    if not hit:
        return "", ""
    suffix = re.sub(r"(?<=[A-Z0-9])O|O(?=[0-9])", "0", re.sub(r"\s", "", hit.group(2)))
    suffix = suffix[0] + suffix[1:].replace("O", "0")
    return f"{hit.group(1)}-{suffix}", hit.group(1)


_SUBDIVISION_LABEL = re.compile(r"Public\s+Report\s+on\s*$|TRACT\s+OR\s+MAP\s+NAME\s+AND\s+NUMBER", re.I)
_SUBDIVISION_SKIP = re.compile(r"^(?:EXPIRES|ISSUED|AMENDED|ISSUANCE\s+DATE|EXPIRATION\s+DATE)\b|^" + _MONTH + r"\s+\d", re.I)


def _subdivision(text: str) -> str:
    """The subdivision's name: the two lines after "Public Report on" (or the preliminary report's "tract or map name"
    box), skipping the date lines a two-column header interleaves."""
    lines = [ln.strip() for ln in text[:5000].splitlines()]
    for i, line in enumerate(lines):
        if not _SUBDIVISION_LABEL.search(line):
            continue
        taken: list[str] = []
        for nxt in lines[i + 1: i + 8]:
            if not nxt or _SUBDIVISION_SKIP.search(nxt):
                continue
            if re.match(r"(?:DEPARTMENT|SACRAMENTO|\(|NAME\s+OF|ADVERTISING|COUNTY)", nxt, re.I):
                break
            taken.append(nxt)
            if len(taken) == 2:
                break
        return " ".join(" ".join(taken).split()).strip(' "-')
    return ""


_RESERVE_PAIR = re.compile(r"Of\s+these\s+amounts,.{0,220}?reserves.{0,160}?\bare\s+\$\s?([\d,]+\.\d\d)(?:\s+and\s+\$\s?([\d,]+\.\d\d))?",
                           re.I)


def _cents(amount: str) -> int:
    return int(amount.replace(",", "").replace(".", ""))


def _money(pattern: str, flat: str) -> int | None:
    hit = re.search(pattern + r"[^$]{0,80}?\$\s?([\d,]+\.\d\d)", flat, re.I)
    return int(hit.group(1).replace(",", "").replace(".", "")) if hit else None


@AS_OF.check("report-expiry", PublicReportRecord, fields=("expires",))
def report_expiry(r, as_of: date, _facts=None) -> list[Finding]:
    """As of a date: whether the public report has expired."""
    if r.expires and r.expires < as_of:
        return [Finding("report-expired", f"the report expired on {r.expires}; it is a historical record of what buyers were "
                        "told", Severity.INFO)]
    return []


class PublicReportModel(DocumentModel):
    kind = DocumentKind.DRE_REPORT
    name = "dre-public-report"
    required = ("file_number", "report_type", "issued", "expires")
    lens_checks = (report_expiry,)

    def parse(self, text: str, context: ModelContext) -> PublicReportRecord | None:
        flat = re.sub(r"\b(" + _MONTH + r"\s+\d{1,2})\.\s+(\d{4})\b", r"\1, \2", squash(text), flags=re.I)  # "MAY 5. 2025"
        head = flat[:4000]
        if not re.search(r"PUBLIC\s+REPORT", head, re.I) or not re.search(r"Real\s+Estate", head, re.I):
            return None
        r = PublicReportRecord()
        r.file_number, r.base_file_number = _file_number(head) if _file_number(head)[0] else _file_number(flat)
        kind = re.search(r"(PRELIMINARY|CONDITIONAL|FINAL|AMENDED)\s+(?:SUBDIVISION\s+)?PUBLIC\s+REPORT", head, re.I)
        r.report_type = ReportType(kind.group(1).lower()) if kind else None
        hit = re.search(r"application\s+of\s+(.{3,90}?(?:LLC|INC\.?|COMPANY))\b", head)
        r.subdivider = re.sub(r"^(?:(?:PLANNED\s+DEVELOPMENT|CONDOMINIUM|STOCK\s+COOPERATIVE|COMMUNITY\s+APARTMENT|ad)\s+)+", "",
                              hit.group(1).strip()) if hit else ""
        if not r.subdivider:
            hit = re.search(r"NAME\s+OF\s+SUBDIVIDER\s+\(SELLER\)\s*\|?\s*DRE\s+FILE\s+NUMBER\s+(.{3,80}?),", head)
            r.subdivider = hit.group(1).strip() if hit else ""
        r.subdivision = _subdivision(text)
        r.issued = date_after(r"ISSUED:", flat[:4000], window=40) or date_after(r"ISSUANCE\s+DATE", flat[:4000], window=200)
        r.amended = date_after(r"AMENDED:", flat[:4000], window=40)
        r.expires = date_after(r"EXPIRES:", flat[:4000], window=60) or date_after(r"EXPIRATION\s+DATE", flat[:4000], window=200)
        hit = re.search(r"\((?:DRE\s+)?PHASE\s+(\d{1,2})\)", head, re.I)
        if hit:
            r.phase = int(hit.group(1))
        else:
            hit = re.search(r"This\s+is\s+the\s+(\w+)(?:\s+and\s+final)?\s+phase", flat, re.I)
            r.phase = ordinal(hit.group(1)) if hit else None
        hit = re.search(r"total\s+of\s+(\d{1,2})\s+phases\s+containing\s+(\d{1,3})\s+units", flat, re.I)
        if hit:
            r.total_phases, r.total_units = int(hit.group(1)), int(hit.group(2))
        covers = re.search(r"REPORT\s+COVERS\s+ONLY\s+(.{0,240})", flat, re.I)
        if covers:
            window = covers.group(1)
            units = re.search(r"UNITS?\s+(\d{1,3})\s+THROUGH\s+(\d{1,3})", window, re.I)
            if units:
                r.first_unit, r.last_unit = int(units.group(1)), int(units.group(2))
                r.units = r.last_unit - r.first_unit + 1 if r.last_unit >= r.first_unit else None
            building = re.search(r"BUILDING\s+NO\.?\s*(\d{1,2})", window, re.I)
            r.building = int(building.group(1)) if building else None
            area = re.search(r"ASSOCIATION\s+COMMON\s+AREA\s+(\d{1,2})", window, re.I)
            r.common_area = int(area.group(1)) if area else None
        r.built_out_assessment_cents = _money(r"built-out\s+budget,\s+(?:the\s+)?monthly\s+assessment", flat)
        r.phase_assessment_cents = _money(r"(?:interim|phase)\s+budget,\s+the\s+monthly\s+assessment\s+per\s+interest", flat)
        regular = re.search(r"Under this built-out budget,\s+monthly assessment[^$]{0,80}\$\s?[\d,]+\.\d\d\s+of which\s+\$\s?([\d,]+\.\d\d)", flat, re.I)
        r.built_out_reserve_cents = int(regular.group(1).replace(",", "").replace(".", "")) if regular else None
        r.cost_center_assessment_cents = _money(r"Under the Cost Center built-out budget,\s+monthly\s+assessment", flat)
        center = re.search(r"Cost Center built-out budget,[^$]{0,80}\$\s?[\d,]+\.\d\d\s+of which\s+\$\s?([\d,]+\.\d\d)", flat, re.I)
        r.cost_center_reserve_cents = int(center.group(1).replace(",", "").replace(".", "")) if center else None
        # "Of these amounts, the monthly contributions toward long-term reserves ... are $15.25 and $28.75, respectively": the
        # built-out budget's reserve, then the phase's. The first such sentence is the regular budget's; the one after "Cost
        # Center built-out budget" is the cost center's.
        center_at = re.search(r"Cost\s+Center\s+built-out\s+budget", flat, re.I)
        regular_part, center_part = (flat[:center_at.start()], flat[center_at.start():]) if center_at else (flat, "")
        pair = _RESERVE_PAIR.search(regular_part)
        if pair:
            r.built_out_reserve_cents = r.built_out_reserve_cents or _cents(pair.group(1))
            r.phase_reserve_cents = _cents(pair.group(2)) if pair.group(2) else None
        pair = _RESERVE_PAIR.search(center_part)
        if pair:
            r.cost_center_reserve_cents = r.cost_center_reserve_cents or _cents(pair.group(1))
            r.cost_center_phase_reserve_cents = _cents(pair.group(2)) if pair.group(2) else None
        # "monthy": the vision model's reading of 154410SA-A01 drops the l; the amount beside it reads right.
        r.cost_center_phase_assessment_cents = _money(r"phase\s+Cost\s+Center\s+budget,\s+the\s+month(?:ly|y)\s+assessment\s+per\s+interest",
                                                      center_part)
        adopted = re.search(r"Current Adopted Budget[^$]{0,40}\$\s?([\d,]+)(?:\.(\d\d))?\s+per month", flat, re.I)
        r.adopted_assessment_cents = int(adopted.group(1).replace(",", "")) * 100 + int(adopted.group(2) or 0) if adopted else None
        return r

    def check(self, r: PublicReportRecord, context: ModelContext) -> list[Finding]:
        found: list[Finding] = [report_expiry]   # the as-of lens's place: the report has expired
        reports = spec_reports(context.community)
        if not reports or not r.base_file_number:
            return found
        spec = next((p for p in reports if getattr(p, "file_number", "") == r.base_file_number), None)
        if spec is None:
            found.append(Finding("file-not-in-spec", f"the specification's phase table has no file {r.base_file_number}", Severity.CHECK))
            return found
        if r.phase and spec.phase != r.phase:
            found.append(Finding("phase-differs", f"the report is phase {r.phase}; the specification has file {r.base_file_number} as phase "
                                 f"{spec.phase}", Severity.CHECK))
        if r.units and spec.units and r.units != spec.units:
            found.append(Finding("unit-count-differs", f"covers {r.units} units; the specification's phase has {spec.units}", Severity.CHECK))
        if r.building and int(spec.building) != r.building:
            found.append(Finding("building-differs", f"covers building {r.building}; the specification has building {int(spec.building)}",
                                 Severity.CHECK))
        issued = getattr(spec, "issued", None)
        if issued and r.issued and issued != r.issued:
            found.append(Finding("issued-differs", f"issued {r.issued}; the specification has {issued}", Severity.CHECK))
        units = _unit_count(context.community)
        if r.total_units and units and r.total_units != units:
            found.append(Finding("projected-units-differ", f"the report projects {r.total_units} units; the association has {units}",
                                 Severity.INFO))
        return found


def _unit_count(community) -> int | None:
    fn = getattr(community, "units", None)
    try:
        return len(fn()) if callable(fn) else None
    except Exception:  # a spec without the roll
        return None


# Maps.

class MapKind(Enum):
    FINAL_MAP = "final map"
    PARCEL_MAP = "parcel map"
    ASSESSOR_MAP = "assessor's parcel map"
    IMPROVEMENT_PLANS = "improvement plans"
    FIRE_INSURANCE_MAP_REPORT = "fire insurance map report"
    OTHER = "other"


_MAP_KINDS: tuple[tuple[MapKind, str], ...] = (
    (MapKind.FIRE_INSURANCE_MAP_REPORT, r"Sanborn"),
    (MapKind.FINAL_MAP, r"FINAL\s+MAP\s+OF"),
    (MapKind.ASSESSOR_MAP, r"ASSESSOR|\bDEED\s+\d{8}/\d{3,4}"),
    (MapKind.PARCEL_MAP, r"PARCEL\s+MAP\s+(?:OF|NO)"),
    (MapKind.IMPROVEMENT_PLANS, r"SHEET\s+INDEX|GRADING|IMPROVEMENT\s+PLANS|STREET\s+SECTIONS"),
)


@dataclass
class MapRecord:
    title: str = ""
    map_kind: MapKind = MapKind.OTHER
    subdivision_number: str = ""          # "P05-164"
    map_reference: str = ""               # "Book 194 of Parcel Maps, page 18"
    dated: str = ""                       # the map's own date line ("AUGUST 2006"), as printed
    sheets: int | None = None
    apns: tuple[str, ...] = ()
    instruments: tuple[str, ...] = ()     # recorded plans or deeds the sheet names by number
    surveyor_statement: bool = False
    owner_consent: bool = False
    dedications: bool = False


class MapModel(DocumentModel):
    kind = DocumentKind.MAP
    name = "map"
    required = ("title", "map_kind")

    def parse(self, text: str, context: ModelContext) -> MapRecord | None:
        flat = squash(text)
        if len(flat) < 200:
            return None
        r = MapRecord()
        r.map_kind = next((k for k, p in _MAP_KINDS if re.search(p, f"{context.name} {flat[:20000]}", re.I)), MapKind.OTHER)
        hit = re.search(r"(FINAL\s+MAP\s+OF\s+[A-Z0-9 ,\"'-]{3,60}?PARCEL\s+\d+)", flat[:6000]) or \
            re.search(r"(Sanborn\W?\s+Library\s+search\s+results)", flat[:6000], re.I)
        r.title = " ".join(hit.group(1).split()) if hit else (context.name.rsplit(".", 1)[0] if context.name else r.map_kind.value)
        hit = re.search(r"SUBDIVISION\s+NO\.?\s*(P\d{2}-\d{3})", flat, re.I) or re.search(r"\b(P\d{2}-\d{3})\b", flat)
        r.subdivision_number = hit.group(1) if hit else ""
        r.map_reference = map_reference(flat)
        hit = re.search(r"\b(" + _MONTH + r"\s+\d{4})\b", flat[:8000])
        r.dated = hit.group(1).title() if hit else ""
        sheets = [int(n) for n in re.findall(r"SHEET\s+\d{1,3}\s+OF\s+(\d{1,3})", flat, re.I)]
        r.sheets = max(sheets) if sheets else None
        r.apns = tuple(dict.fromkeys(re.sub(r"\W+", "-", m.group(0)).strip("-")
                                     for m in re.finditer(r"\b\d{3}\W{1,3}\d{4}\W{1,3}\d{3}\W{1,3}\d{4}\b", flat)))[:40]
        r.instruments = tuple(dict.fromkeys(f"{a}{int(b):04d}" for a, b in re.findall(r"\bDEED\s+(\d{8})/(\d{3,4})\b", flat)))
        r.surveyor_statement = bool(re.search(r"SURVEYOR.?S\s+STATEMENT", flat, re.I))
        r.owner_consent = bool(re.search(r"HEREBY\s+CONSENT\s+TO\s+THE\s+PREPARATION", flat, re.I))
        r.dedications = bool(re.search(r"HEREBY\s+DEDICATE", flat, re.I))
        return r

    def check(self, r: MapRecord, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.map_kind is MapKind.FINAL_MAP and not r.map_reference:
            found.append(Finding("filing-blank", "the map's own book and page are blank in this copy (a pre-filing print); the filed map "
                                 "is cited by later instruments", Severity.INFO))
        if r.map_kind is MapKind.OTHER:
            found.append(Finding("map-kind-unknown", "the text does not say what kind of map this is", Severity.CHECK))
        return found


# Condominium plans.

@dataclass
class CondominiumPlanRecord:
    title: str = ""
    recording: Recording = field(default_factory=Recording)
    certification_differs: str = ""      # a title company's certification that disagrees with the file name
    number: str = ""
    recorded: date | None = None
    buildings: tuple[int, ...] = ()
    unit_ranges: tuple[tuple[int, int], ...] = ()
    units: int | None = None
    association_common_areas: tuple[int, ...] = ()
    sheets: int | None = None
    divides_plan: str = ""                # the earlier plan whose units this one further divides
    map_reference: str = ""
    surveyor_statement: bool = False
    no_deeds_of_trust: bool = False       # "there are currently no deeds of trust of record"
    legend_defines_common_areas: bool = False  # the legend: "A.C.A. ASSOCIATION COMMON AREA", "C.C.A. CONDOMINIUM COMMON AREA"
    aca_plan_sheet: bool = False          # the "LOCATION / A.C.A. PLAN" sheet
    condominium_common_areas: tuple[int, ...] = ()


class CondominiumPlanModel(DocumentModel):
    kind = DocumentKind.CONDOMINIUM_PLAN
    name = "condominium-plan"
    required = ("title", "number", "recorded", "sheets")

    def parse(self, text: str, context: ModelContext) -> CondominiumPlanRecord | None:
        flat = squash(text)
        if not re.search(r"CONDOMIN\w{0,3}\s*(?:UM|IUM)?\s+PLAN|CONDO\w*\s+PLAN", flat[:8000], re.I):
            return None
        r = CondominiumPlanRecord()
        hit = re.search(r"(CONDOMIN\w*\s+PLAN\s+FOR\s+[A-Z]+(?:\s+BUILDINGS?\s+[\d, ]+(?:AND\s+\d+)?)?)", flat[:8000])
        r.title = " ".join(hit.group(1).replace("CONDOMINUM", "CONDOMINIUM").split()).strip(" ,") if hit else "CONDOMINIUM PLAN"
        r.recording, r.certification_differs = copy_recording(text, context.name)
        r.number, r.recorded = r.recording.number, r.recording.recorded
        hit = re.search(r"BUILDINGS?\s+((?:\d{1,2}\s*,?\s*(?:AND\s+)?)+)", r.title)
        r.buildings = tuple(int(n) for n in re.findall(r"\d{1,2}", hit.group(1))) if hit else ()
        legal = re.search(r"LEGAL\s+DESCRIPTION\s+(.{0,500}?)(?:AS\s+SHOWN|BEING)", flat[:12000], re.I)
        if legal:
            ranges = [(int(a), int(b)) for a, b in re.findall(r"(\d{1,3})\s+THROUGH\s+(\d{1,3})", re.sub(r"(\d)\.(\d)", r"\1\2", legal.group(1)))
                      if int(a) <= int(b)]
            r.unit_ranges = tuple(ranges)
            r.units = sum(b - a + 1 for a, b in ranges) or None
            aca = re.search(r"ASSOCIATION\s+COMMON\s+AREAS?\s*\(?A\.?\s?C\.?\s?A\.?\)?\s*([\d, :]+(?:AND\s+\d+)?)", legal.group(1), re.I)
            r.association_common_areas = tuple(int(n) for n in re.findall(r"\d{1,2}", aca.group(1))) if aca else ()
        sheets = [int(n) for n in re.findall(r"SHEET\s+\d{1,3}\s+OF\s+(\d{1,3})", flat, re.I)]
        hit = re.search(r"CONSISTING\s+OF\s+(\d{1,3})\s+SHEETS", flat, re.I)
        r.sheets = max(sheets) if sheets else (int(hit.group(1)) if hit else None)
        prior = [n for n in book_page_numbers(flat[:12000]) if n != r.number]
        hit = re.search(r"CONDOMINIUM\s+PLAN\s+FOR\s+[A-Z]+,?\s+IN\s+BOOK\s+(\d{8})[.,]?\s+OF\s+OFFICIAL\s+RECORDS[.,]?\s+AT\s+PAGE\s+(\d{1,4})", flat,
                        re.I)
        r.divides_plan = f"{hit.group(1)}{int(hit.group(2)):04d}" if hit else ""
        if not r.divides_plan and prior and re.search(r"FURTHER\s+DIVISION", flat, re.I):
            r.divides_plan = prior[0]
        r.map_reference = map_reference(flat)
        r.surveyor_statement = bool(re.search(r"S\w?R\s?VEY\s?OR\W{0,3}S\s+STATEMENT|LICENSED\s+LAND\s+SURVEYOR", flat, re.I))
        r.no_deeds_of_trust = bool(re.search(r"NO\s+DEEDS\s+OF\s+TRUST\s+OF\s+RECORD", flat, re.I))
        r.legend_defines_common_areas = bool(re.search(r"A\.?\s?C\.?\s?A\.?\s+ASSOCIATION\s+COMMON\s+AR\S*", flat, re.I)) and \
            bool(re.search(r"C\.?\s?C\.?\s?A\.?\s+CONDOMINIUM\s+COMMON\s+AR\S*", flat, re.I))
        r.aca_plan_sheet = bool(re.search(r"LOCATION\s*/?\s*A\.?\s?C\.?\s?A\.?\s+PLAN", flat, re.I))
        if legal:
            cca = re.search(r"CONDOMINIUM\s+COMMON\s+AREAS?\s*\(?C\.?\s?C\.?\s?A\.?\)?\s*([\d, :]+(?:AND\s+\d+)?)", legal.group(1), re.I)
            r.condominium_common_areas = tuple(int(n) for n in re.findall(r"\d{1,2}", cca.group(1))) if cca else ()
        return r

    def check(self, r: CondominiumPlanRecord, context: ModelContext) -> list[Finding]:
        found = copy_findings(r.recording, r.certification_differs, context.name)
        if r.divides_plan:
            found.append(Finding("divides-earlier-plan", f"further divides units of the plan recorded as {r.divides_plan}; a deed of these "
                                 "units cites this plan, not the earlier one", Severity.INFO))
        if not r.surveyor_statement:
            found.append(Finding("no-surveyor-statement", "the text shows no surveyor's statement (it may be an image)", Severity.CHECK))
        return found


# Plan sets: the city's entitlement and design-review files.

class PlanSetKind(Enum):
    DECISION = "record of decision"
    STAFF_REPORT = "staff report"
    APPLICATION = "application"
    DRAWINGS = "drawings"
    OTHER = "other"


@dataclass
class PlanSetRecord:
    title: str = ""
    plan_kind: PlanSetKind = PlanSetKind.OTHER
    file_number: str = ""                 # the city's file ("DR18-052", "P05-164")
    related_files: tuple[str, ...] = ()
    project_address: str = ""
    apns: tuple[str, ...] = ()
    dated: date | None = None
    units: int | None = None
    buildings: int | None = None
    acres: str = ""
    decision: str = ""                    # "approved", "approved with conditions", "denied"


class PlanSetModel(DocumentModel):
    kind = DocumentKind.PLAN_SET
    name = "plan-set"
    required = ("file_number", "plan_kind")

    def parse(self, text: str, context: ModelContext) -> PlanSetRecord | None:
        flat = squash(text)
        if len(flat) < 300:
            return None
        r = PlanSetRecord()
        files = list(dict.fromkeys(re.findall(r"\b((?:DR|P|Z|PB|PL)\d{2}-\d{3})\b", flat)))
        named = re.search(r"\b((?:DR|P|Z|PB|PL)\d{2}-\d{3})", context.name or "")
        r.file_number = named.group(1) if named else (files[0] if files else "")
        r.related_files = tuple(f for f in files if f != r.file_number)
        lower = flat[:6000].lower()
        if re.search(r"record\s+of\s+decision|notice\s+of\s+decision|staff\s+level\s+site\s+plan", lower) or "_ROD" in (context.name or ""):
            r.plan_kind = PlanSetKind.DECISION
        elif "application" in lower[:3000] and re.search(r"applicant\s+information|project\s+narrative", lower):
            r.plan_kind = PlanSetKind.APPLICATION
        elif re.search(r"staff\s+report|planning\s+commission|recommendation", lower):
            r.plan_kind = PlanSetKind.STAFF_REPORT
        elif re.search(r"sheet|plot\s+date|architect", lower):
            r.plan_kind = PlanSetKind.DRAWINGS
        r.title = f"{r.plan_kind.value} {r.file_number}".strip()
        hit = re.search(r"(?:PROJECT\s+ADDRESS|Site\s+address\s+or\s+location\s+of\s+property)\s*:\s*([^:]{5,80}?\bCA\b(?:\s+\d{5})?)", flat, re.I)
        r.project_address = hit.group(1).strip() if hit else ""
        r.apns = tuple(dict.fromkeys(re.findall(r"\b\d{3}-\d{4}-\d{3}(?:-\s?\d{4})?\b", flat)))[:30]
        found = dates_in(flat[:6000])
        r.dated = date_after(r"D?\s?ATE\s+OF\s+ACTION:?", flat, window=40) or date_after(r"APPLICATION\s+FILED:?", flat, window=40) or \
            (found[0] if found else None)
        hit = re.search(r"(?:totaling|total\s+of|for\s+a\s+total\s+of)\s+(\d{1,3})\s+units", flat, re.I) or \
            re.search(r"(\d{1,3})-unit\s+condominium", flat, re.I)
        r.units = int(hit.group(1)) if hit else None
        hit = re.search(r"(\w+)\s+(?:proposed\s+)?(?:condominium\s+)?buildings\s+totaling", flat, re.I) or \
            re.search(r"within\s+(\w+)\s+buildings", flat, re.I)
        if hit:
            word = hit.group(1).lower()
            r.buildings = int(word) if word.isdigit() else {"six": 6, "eight": 8, "seven": 7, "two": 2, "five": 5}.get(word)
        hit = re.search(r"(\d+(?:\.\d+)?)\s*(?:\+/-\s*)?(?:partially\s+developed\s+|gross\s+)?acres", flat, re.I)
        r.acres = hit.group(1) if hit else ""
        hit = re.search(r"C?TION:\s*(approved\s+with\s+conditions|approved|denied)\b", flat[:20000], re.I) or \
            re.search(r"\b(approved\s+(?:with\s+conditions|subject\s+to)|approved|denied)\b", flat[:20000], re.I)
        r.decision = hit.group(1).lower() if hit and r.plan_kind is PlanSetKind.DECISION else ""
        return r

    def check(self, r: PlanSetRecord, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.plan_kind is PlanSetKind.DECISION and not r.decision:
            found.append(Finding("no-decision-in-text", "the decision's outcome is not in the text", Severity.CHECK))
        return found


register(PublicReportModel())
register(MapModel())
register(CondominiumPlanModel())
register(PlanSetModel())

__all__ = ["ReportType", "PublicReportRecord", "PublicReportModel", "MapKind", "MapRecord", "MapModel", "CondominiumPlanRecord",
           "CondominiumPlanModel", "PlanSetKind", "PlanSetRecord", "PlanSetModel"]
