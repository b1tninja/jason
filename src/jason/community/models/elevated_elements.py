"""The exterior elevated elements (balcony) inspection report, Civil Code 5551 (SB 326).

The law shapes this report. The board has a licensed structural or civil engineer or architect visually inspect a
random, statistically significant sample of the exterior elevated elements at least every nine years (5551(b)); the
first by January 1, 2025 (5551(i)). The report identifies the load-bearing components and waterproofing, their
condition and any immediate threat, their expected future performance and remaining life, and recommendations
(5551(e)(1)-(4)); its first page gives the inspection date, the units in the project, the units with elevated
elements, the elevated elements in all and inspected, those posing an immediate threat and the units affected, and a
certification of a statistically significant sample (5551(e)(5)). It is stamped or signed by the inspector, presented to
the board, and incorporated into the reserve study (5551(f)), and kept for two inspection cycles (5551(i)).

``ElevatedElementReport`` reads California Deck Inspection's layout (the association's November 2023 report) and the
same facts where another inspector prints them with the usual labels.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from jason.community.document_models import (
    DocumentModel,
    Finding,
    ModelContext,
    Severity,
    date_after,
    dates_in,
    first,
    register,
    squash,
)
from jason.community.reviews import AS_OF
from jason.community.symbols import DocumentKind

AUTHORITY = "CIV 5551"
CYCLE_YEARS = 9
FIRST_DUE = date(2025, 1, 1)


@dataclass(frozen=True)
class ElementType:
    """One type of elevated element on the summary page: decks, landings, walkways, stairs."""

    name: str
    total: int | None = None
    inspected: int | None = None
    non_eee: int | None = None
    eee: int | None = None


@dataclass(frozen=True)
class InspectedElement:
    building: str
    unit: str
    description: str
    immediate_hazard: bool | None = None


@dataclass
class ElevatedElementReport:
    inspector_firm: str = ""
    inspector_license: str = ""       # the firm's license on the letterhead
    signer: str = ""                  # the licensed architect or engineer who stamps or signs
    signer_title: str = ""            # "Architect", "Structural Engineer", "Civil Engineer"
    signer_license: str = ""          # the design professional's license, when the text gives it
    inspection_date: date | None = None
    report_date: date | None = None
    order: str = ""
    site_name: str = ""
    site_address: str = ""
    property_owner: str = ""          # as the report names it
    units: int | None = None
    buildings: int | None = None
    stories: int | None = None
    construction: str = ""
    units_with_elements: int | None = None
    element_types: tuple[ElementType, ...] = ()
    elements_total: int | None = None
    elements_inspected: int | None = None
    immediate_threats: int | None = None
    units_affected: int | None = None
    certifies_statistical_sample: bool = False
    random_list: bool = False
    reinspection: str = ""            # what the report says about the next inspection
    next_inspection: date | None = None
    inspected: tuple[InspectedElement, ...] = field(default_factory=tuple)
    photos: int = 0


_TYPE_BLOCK = re.compile(r"\n(Deck|Landing|Walkway|Stairs?)\n((?:\d+\n){4})", re.I)
_ROW = re.compile(r"BLDG\s*(\d+)\s*\n\s*Unit\s*(\w+)\s*\n\s*([^\n]+)\n\s*(None|Yes|No)?", re.I)
_TITLE = re.compile(r"exterior elevated elements?|SB\s*-?\s*326|5551", re.I)


def _int_before(label: str, text: str) -> int | None:
    m = re.search(r"(\d+)\s*\n\s*" + label, text, re.I)
    return int(m.group(1)) if m else None


def _plus_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # February 29
        return day.replace(year=day.year + years, day=28)


@AS_OF.check("next-elevated-inspection", ElevatedElementReport, fields=("next_inspection",))
def next_inspection(r, as_of: date, _facts=None) -> list[Finding]:
    """As of a date: how long until the next inspection is due."""
    if not r.next_inspection:
        return []
    left = (r.next_inspection - as_of).days
    severity = Severity.PROBLEM if left < 0 else Severity.CHECK if left < 365 else Severity.INFO
    return [Finding("next-inspection", f"the next inspection is due by {r.next_inspection} ({left} days)", severity, "CIV 5551(b), (i)")]


class ElevatedElementReportModel(DocumentModel):
    kinds = (DocumentKind.ELEVATED_ELEMENT_INSPECTION, DocumentKind.INSPECTION_REPORT)
    name = "sb326-report"
    required = ("inspection_date", "report_date", "signer", "units", "elements_total", "elements_inspected", "immediate_threats")
    lens_checks = (next_inspection,)

    def parse(self, text: str, context: ModelContext) -> ElevatedElementReport | None:
        if not _TITLE.search(text or "") or not re.search(r"elevated|balcon|deck", text or "", re.I):
            return None
        flat = squash(text)
        r = ElevatedElementReport()
        r.inspector_firm = "California Deck Inspection" if re.search(r"CALIFORNIA DECK INSPECTION|californiadeckinspection", text, re.I) else \
            first(r"Signed:\s*\n?\s*([A-Z][A-Z &,.]+)\n", text)
        r.inspector_license = first(r"\bLic\.?\s*#?\s*(\d{5,})", text)
        r.inspection_date = date_after(r"Examination Date:?", text) or date_after(r"Date of Inspection:?", text) or \
            (dates_in(first(r"([^\n]+)\n\s*Examination Date", text)) or [None])[0]
        r.order = first(r"Order:?\s*0*(\d+)", text)
        r.site_name = first(r"\n([^\n]+)\n\s*Site Name\b", text) or first(r"Site Name:\s*([^\n]+)", text)
        r.site_address = first(r"\n([^\n]+)\n\s*Site Address", text)
        r.property_owner = first(r"\n([^\n]+)\n\s*Property Owner", text)
        r.units = _int_before(r"Units\b", text)
        r.buildings = _int_before(r"Buildings\b", text)
        r.stories = _int_before(r"Stories\b", text)
        r.construction = first(r"\n([^\n]+)\n\s*Type of Construction", text)
        types = []
        for m in _TYPE_BLOCK.finditer(text):
            numbers = [int(n) for n in m.group(2).split()]
            # The summary prints Total, Non EEEs, EEEs, Inspected in that order under each type.
            types.append(ElementType(m.group(1).title(), numbers[0], numbers[3], numbers[1], numbers[2]))
        r.element_types = tuple(types)
        if types:
            r.elements_total = sum(t.eee or 0 for t in types)
            r.elements_inspected = sum(t.inspected or 0 for t in types)
        rows = [InspectedElement(m.group(1), m.group(2), squash(m.group(3)),
                                 None if not m.group(4) else m.group(4).lower() == "yes") for m in _ROW.finditer(text)]
        r.inspected = tuple(rows)
        hazard = re.search(r"Immediate Threat to Safety of Occupants:?", text, re.I)
        if hazard:
            yes = [e for e in rows if e.immediate_hazard]
            r.immediate_threats = len(yes) if rows else None
            r.units_affected = len({(e.building, e.unit) for e in yes}) if rows else None
        r.units_with_elements = _int_before(r"Units with (?:exterior )?elevated", text)
        r.certifies_statistical_sample = bool(re.search(r"statistically significant", flat, re.I))
        r.random_list = bool(re.search(r"random list", flat, re.I))
        r.reinspection = first(r"([^\n]*years? from the date of this report[^\n]*)", text) or first(r"Re-?Inspection[:\s]+([^\n]+)", text)
        signed = re.search(r"By\s+([A-Z][a-z]+ [A-Z][a-z]+)\s*\n\s*([A-Z][a-z]+ [A-Z][a-z]+)\s*\n\s*(\w[\w ]*)\n\s*(Architect|Structural Engineer|Civil Engineer|Engineer)\b",
                           text)
        if signed:
            r.signer, r.signer_title = signed.group(2), signed.group(4)
        else:
            r.signer = first(r"\n([A-Z][a-z]+ [A-Z][a-z]+)\s*,?\s*\n?\s*(?:Architect|P\.?E\.?|S\.?E\.?|Structural Engineer|Civil Engineer)\b", text)
            r.signer_title = first(r"\b(Architect|Structural Engineer|Civil Engineer)\b", text)
        r.signer_license = first(r"\b(?:C-?|S\.?E\.?\s*|C\.?E\.?\s*|RCE\s*|Architect\s*(?:No\.?|#)?\s*)(\d{4,6})\b(?![\d-])", text) \
            if re.search(r"\bC-?\d{4,6}\b|RCE|S\.E\.|Architect (?:No|#)", text) else ""
        signature_block = text[signed.end():] if signed else text
        dated = dates_in(signature_block[:80])
        r.report_date = dated[0] if dated else None
        if r.report_date and re.search(r"nine years from the date of this report", flat, re.I):
            r.next_inspection = _plus_years(r.report_date, CYCLE_YEARS)
        elif r.inspection_date:
            r.next_inspection = _plus_years(r.inspection_date, CYCLE_YEARS)
        r.photos = len(re.findall(r"\b\d+-\d{3}\.JPG\b", text, re.I))
        return r

    def check(self, r: ElevatedElementReport, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.inspection_date and r.inspection_date > FIRST_DUE:
            found.append(Finding("first-inspection-late", f"the inspection on {r.inspection_date} came after the first deadline, "
                                 f"{FIRST_DUE}", Severity.PROBLEM, "CIV 5551(i)"))
        found.append(next_inspection)   # the as-of lens's place: how long until the next inspection is due
        if r.signer and r.signer_title not in ("Architect", "Structural Engineer", "Civil Engineer"):
            found.append(Finding("signer-not-licensed-type", f"the signer {r.signer} is not shown as an architect or a structural or civil "
                                 "engineer", Severity.PROBLEM, "CIV 5551(b)(1)"))
        if r.signer and not r.signer_license:
            found.append(Finding("signer-license-not-in-text", f"{r.signer}'s license number is not in the text (a stamp image may carry it); "
                                 "confirm it with the licensing board", Severity.CHECK, "CIV 5551(b)(1), (f)"))
        if r.units_with_elements is None:
            found.append(Finding("no-units-with-elements", "the first page does not give the number of units with elevated elements",
                                 Severity.CHECK, "CIV 5551(e)(5)(C)"))
        if r.immediate_threats and r.immediate_threats > 0:
            found.append(Finding("immediate-threat", f"{r.immediate_threats} elevated elements pose an immediate threat to occupants "
                                 f"({r.units_affected} units); the association must bar access and the inspector must send the report to "
                                 "code enforcement within 15 days", Severity.PROBLEM, "CIV 5551(g)"))
        if not r.certifies_statistical_sample:
            found.append(Finding("no-statistical-sample-certification", "the report does not certify a statistically significant sample "
                                 "in those words (it may say it inspected the minimum sample)", Severity.CHECK, "CIV 5551(e)(5)(G)"))
        if not r.random_list:
            found.append(Finding("no-random-list", "the report does not mention the random list of element locations the inspector must "
                                 "give the association for later inspections", Severity.CHECK, "CIV 5551(c), (h)"))
        if r.elements_total and r.elements_inspected is not None and r.elements_inspected < r.elements_total:
            share = r.elements_inspected / r.elements_total
            found.append(Finding("sample-share", f"{r.elements_inspected} of {r.elements_total} elevated elements inspected ({share:.0%})",
                                 Severity.INFO, "CIV 5551(a)(4), (b)(1)"))
        spec_units = _spec_units(context)
        if r.units and spec_units and r.units != spec_units:
            found.append(Finding("unit-count", f"the report counts {r.units} units; the specification has {spec_units}", Severity.CHECK,
                                 "CIV 5551(e)(5)(B)"))
        if r.property_owner and re.search(r"\b(group|management|inc)\b", r.property_owner, re.I) and "association" not in r.property_owner.lower():
            found.append(Finding("owner-is-manager", f"the report names {r.property_owner!r} as the property owner, not the association",
                                 Severity.CHECK))
        found.append(Finding("keep-two-cycles", "keep this report for two inspection cycles (18 years) as an association record",
                             Severity.INFO, "CIV 5551(i)"))
        found.append(Finding("incorporate-into-reserve-study", "the report must be incorporated into the reserve study; check the "
                             "current study cites it", Severity.INFO, "CIV 5551(f)"))
        return found


def _spec_units(context: ModelContext) -> int | None:
    units = getattr(context.community, "units", None)
    if units is None:
        return None
    try:
        return len(units() if callable(units) else units)
    except TypeError:
        return None


register(ElevatedElementReportModel())

__all__ = ["ElevatedElementReport", "ElementType", "InspectedElement", "ElevatedElementReportModel"]
