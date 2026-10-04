"""Life-safety and building-system inspection reports: fire alarm, fire sprinkler, backflow, roof, and the like.

No Davis-Stirling section shapes these reports; the vendor's standard does (NFPA 72 for a fire alarm, NFPA 25 for a
sprinkler system), and jason holds neither. The specification's ``obligations`` give the cadence where it has one (the
fire sprinkler inspection and the backflow test are yearly); a report of a system the specification gives no cadence
for gets no due date. The SB 326 balcony report is ``elevated_elements``; these models leave it alone.

``SignalServiceReport`` reads Signal Service's NFPA 72 fire alarm report (one per building, the September 2025 pair):
the tested-by and accepted-by blocks, the company's licenses, the monitoring company, the testing summary by equipment
type, the outstanding deficiencies, and each device's result. ``InspectionReportModel`` reads the same facts where
another vendor prints them with the usual labels. A report names the vendor's technician; it names no owner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum

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
from jason.community.models.legal_shared import building_number, building_of, site_address
from jason.community.reviews import AS_OF
from jason.community.symbols import Building, DocumentKind


class InspectedSystem(Enum):
    FIRE_ALARM = "fire alarm"
    FIRE_SPRINKLER = "fire sprinkler"
    BACKFLOW = "backflow assembly"
    FIRE_EXTINGUISHER = "fire extinguishers"
    ROOF = "roof"
    ELEVATOR = "elevator"
    OTHER = "other"


class Result(Enum):
    PASSED = "passed"
    FAILED = "failed"            # a device or item failed
    INCOMPLETE = "incomplete"    # nothing failed, but some items were not tested


# The words that name each system in a title, and the obligation name the specification uses for its cadence.
_SYSTEMS = ((InspectedSystem.FIRE_ALARM, r"fire alarm|NFPA 72|FACP|smoke detector", "fire alarm"),
            (InspectedSystem.FIRE_SPRINKLER, r"fire sprinkler|NFPA 25|sprinkler system|riser", "fire sprinkler"),
            (InspectedSystem.BACKFLOW, r"backflow", "backflow"),
            (InspectedSystem.FIRE_EXTINGUISHER, r"extinguisher", "extinguisher"),
            (InspectedSystem.ROOF, r"\broof", "roof"),
            (InspectedSystem.ELEVATOR, r"elevator", "elevator"))


def _system(text: str) -> InspectedSystem:
    head = text[:4000]
    for system, pattern, _ in _SYSTEMS:
        if re.search(pattern, head, re.I):
            return system
    return InspectedSystem.OTHER


@dataclass(frozen=True)
class EquipmentTally:
    equipment: str
    total: int
    tested: int
    passed: int
    failed: int


@dataclass(frozen=True)
class Deficiency:
    location: str
    device: str
    comment: str
    status: str                  # "Open", "Resolved"


@dataclass
class InspectionReport:
    system: InspectedSystem = InspectedSystem.OTHER
    standard: str = ""                   # "NFPA 72 (2013)"
    inspector_firm: str = ""
    inspector_license: str = ""
    technician: str = ""                 # the vendor's tester
    inspection_date: date | None = None
    building: Building | None = None
    site_address: str = ""
    customer_city: str = ""              # the vendor's customer record for the association
    monitoring_company: str = ""
    accepted_by: str = ""                # the association's signer; "N A" when nobody signed
    equipment: tuple[EquipmentTally, ...] = ()
    devices_total: int | None = None
    devices_tested: int | None = None
    devices_passed: int | None = None
    devices_failed: int | None = None
    devices_not_tested: int = 0
    deficiencies: tuple[Deficiency, ...] = ()
    open_deficiencies: int = 0
    result: Result | None = None
    comments: str = ""
    next_due: date | None = None         # from the report when it prints one


_TALLY = re.compile(r"\n([A-Z][A-Za-z ]+?)\n(\d+)\n(\d+) \(\d+%\)\n(\d+) \(\d+%\)\n(\d+) \(\d+%\)")
_DEFICIENCY = re.compile(r"Status\s*\n(.*?)\s*Resolved Deficiencies", re.S)


def _due(r, cadence: tuple[int, str] | None) -> tuple[date | None, str]:
    """When the next inspection is due and on what authority: the date the report prints, else the specification's
    cadence counted from the inspection."""
    if r.next_due is None and cadence and r.inspection_date:
        months, authority = cadence
        return _add_months(r.inspection_date, months), authority
    return r.next_due, ""


def _system_cadence(r, community) -> tuple[int, str] | None:
    """What the next-due check reads from the specification: the cadence for the report's system."""
    return _cadence(community, r.system)


@AS_OF.check("next-inspection-due", InspectionReport, fields=("system", "inspection_date", "next_due"), facts=_system_cadence)
def next_inspection_due(r, as_of: date, cadence: tuple[int, str] | None = None) -> list[Finding]:
    """As of a date: how long until the system's next inspection is due."""
    due, authority = _due(r, cadence)
    if not due:
        return []
    left = (due - as_of).days
    severity = Severity.PROBLEM if left < 0 else Severity.CHECK if left < 60 else Severity.INFO
    return [Finding("next-due", f"the next {r.system.value} inspection is due by {due} ({left} days)", severity, authority)]


def _is_balcony_report(text: str) -> bool:
    return bool(re.search(r"exterior elevated elements?|SB\s*-?\s*326|\b5551\b", text or "", re.I))


class SignalServiceReportModel(DocumentModel):
    kind = DocumentKind.INSPECTION_REPORT
    name = "signal-service-fire-alarm"
    required = ("inspection_date", "inspector_firm", "inspector_license", "building", "result")
    lens_checks = (next_inspection_due,)

    def parse(self, text: str, context: ModelContext) -> InspectionReport | None:
        if _is_balcony_report(text) or not re.search(r"Signal Service", text or "") or not re.search(r"TESTING SUMMARY", text or ""):
            return None
        r = InspectionReport(system=_system(text), inspector_firm="Signal Service Inc.")
        r.standard = first(r"Fire Alarm System - (NFPA \d+ \(\d{4}\))", text) or first(r"(NFPA \d+(?: \(\d{4}\))?)", text)
        r.inspector_license = first(r"License:\s*\n([^\n]+)", text)
        r.technician = first(r"Tested By:\s*\n([^\n]+)", text)
        r.inspection_date = date_after(r"Completed:", text, window=60)
        r.building = building_number(first(r"Bldg\.?\s*#?\s*(\d)", text))
        r.site_address = site_address(first(r"BUILDING INFORMATION(.*?)COMPANY INFORMATION", text, flags=re.I | re.S)) or site_address(text[:400])
        r.customer_city = first(r"CUSTOMER INFORMATION.*?City:\s*\n([^\n]+)", text, flags=re.I | re.S)
        # The company block, else the supervising station the equipment table names.
        r.monitoring_company = first(r"MONITORING COMPANY\s*\nName:\s*\n([^\n]+)", text) or \
            first(r"Supervising Station Monitoring\s*\nSpecification\s*\nType/Make/Model\s*\n([A-Za-z][^\n]{2,40})\n", text)
        r.accepted_by = first(r"Accepted By:\s*\n([^\n]+)", text)
        tallies = [EquipmentTally(m.group(1).strip(), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)))
                   for m in _TALLY.finditer(text)]
        r.equipment = tuple(tallies)
        if tallies:
            r.devices_total = sum(t.total for t in tallies)
            r.devices_tested = sum(t.tested for t in tallies)
            r.devices_passed = sum(t.passed for t in tallies)
            r.devices_failed = sum(t.failed for t in tallies)
        r.devices_not_tested = len(re.findall(r"Result\s*\nNot Tested", text))
        block = _DEFICIENCY.search(text)
        rows = []
        if block and block.group(1).strip():
            body = block.group(1)
            status = first(r"\b(Open|Resolved|Closed)\s*$", body.strip())
            dated = re.search(r"\n([A-Z][a-z]{2} \d{1,2},\s*\n?\d{4})", body)
            before = body[:dated.start()] if dated else body
            after = body[dated.end():] if dated else ""
            parts = [ln.strip() for ln in before.strip().split("\n") if ln.strip()]
            device_at = next((i for i, ln in enumerate(parts) if " / " in ln and re.search(r"[A-Z][a-z]+ / ", ln)), len(parts))
            location = squash(" ".join(parts[:device_at]))
            device = squash(" ".join(parts[device_at:]))
            comment_lines = [ln.strip() for ln in after.strip().split("\n") if ln.strip()]
            comment = squash(" ".join(comment_lines[2:] if len(comment_lines) > 2 else comment_lines))
            comment = re.sub(r"\s*(Open|Resolved|Closed)$", "", comment)
            rows.append(Deficiency(re.sub(r"^\d+\s+", "", location), device, comment, status))
        r.deficiencies = tuple(rows)
        r.open_deficiencies = sum(1 for d in rows if d.status.lower() == "open") or \
            int(first(r"Deficiencies\s*\n(\d+)\s*\nResolutions", text) or 0)
        r.comments = first(r"COMMENT\s*\nIMAGE\s*\n\d+\s*\n(.*?)\n\s*\.\s*\n", text, flags=re.S)
        if r.devices_failed or r.open_deficiencies or re.search(r"Result\s*\nFailed", text):
            r.result = Result.FAILED
        elif r.devices_not_tested:
            r.result = Result.INCOMPLETE
        elif tallies:
            r.result = Result.PASSED
        r.next_due = date_after(r"Next (?:Inspection|Test)(?: Due)?:?", text, window=40)
        return r

    def check(self, r: InspectionReport, context: ModelContext) -> list[Finding]:
        return _report_findings(r, context)


class InspectionReportModel(DocumentModel):
    """Any other vendor's inspection or test report, read by its labels."""

    kind = DocumentKind.INSPECTION_REPORT
    name = "inspection-report"
    required = ("inspection_date", "inspector_firm", "system")
    lens_checks = (next_inspection_due,)

    def parse(self, text: str, context: ModelContext) -> InspectionReport | None:
        if _is_balcony_report(text):
            return None
        system = _system(text)
        titled = re.search(r"inspection report|test report|report of inspection|inspection (?:and|&) test", (text or "")[:3000], re.I)
        labeled = re.search(r"(?:Inspection|Test) Date:|Date of (?:Inspection|Test)|Date (?:Tested|Inspected):", text or "", re.I)
        if not (titled or (labeled and system is not InspectedSystem.OTHER)):
            return None
        flat = squash(text)
        r = InspectionReport(system=system)
        r.standard = first(r"\b(NFPA \d+(?: \(\d{4}\))?)", flat)
        r.inspector_firm = first(r"(?:Inspected|Tested|Performed) By:?\s*\n?([A-Z][^\n]{2,60})", text) or \
            first(r"^\s*([A-Z][A-Za-z&.,' ]+(?:Inc\.?|LLC|Company|Services?|Co\.))\s*$", text[:800], flags=re.M)
        r.inspector_license = first(r"(?:Contractor'?s )?Lic(?:ense)?\.?\s*(?:No\.?|#)?\s*:?\s*([A-Z0-9-]{4,}(?:\s*(?:and|/)\s*[A-Z0-9/ -]{4,})?)", flat)
        r.technician = first(r"(?:Technician|Inspector|Tester)(?: Name)?:\s*([A-Z][a-z]+ [A-Z][a-z]+)", flat)
        r.inspection_date = date_after(r"(?:Inspection|Test|Service) Date:?", text, window=40) or \
            date_after(r"Date (?:of (?:Inspection|Test)|Tested|Inspected):?", text, window=40) or (dates_in(text[:1500]) or [None])[0]
        r.site_address = site_address(text)
        r.building = building_number(first(r"Bldg\.?\s*#?\s*(\d)", text)) or building_of(context, r.site_address)
        passes = len(re.findall(r"\bpass(?:ed)?\b", flat, re.I))
        fails = len(re.findall(r"\bfail(?:ed|ure)?\b", flat, re.I))
        r.devices_failed = fails or None
        r.devices_passed = passes or None
        r.deficiencies = tuple(Deficiency("", "", squash(m.group(1))[:200], "Open")
                               for m in re.finditer(r"Deficienc(?:y|ies)[:\s]+([^\n]{8,200})", text) if not re.match(r"\s*(?:none|0)\b", m.group(1), re.I))
        r.open_deficiencies = len(r.deficiencies)
        r.result = Result.FAILED if fails or r.open_deficiencies else Result.PASSED if passes else None
        r.next_due = date_after(r"Next (?:Inspection|Test|Service)(?: Due)?(?: Date)?:?", text, window=40)
        return r

    def check(self, r: InspectionReport, context: ModelContext) -> list[Finding]:
        return _report_findings(r, context)


def _cadence(community, system: InspectedSystem) -> tuple[int, str] | None:
    """The specification's shortest interval (months) and its authority for a system, when it has one.

    The fire alarm's is semiannual (``every_months``); the sprinklers' rows run quarterly, yearly, and five-yearly, and
    the next inspection of any kind is the quarterly one.
    """
    obligations = getattr(community, "obligations", None)
    if obligations is None:
        return None
    word = next((w for s, _, w in _SYSTEMS if s is system), "")
    if not word:
        return None
    rows = [(getattr(row, "every_months", 0) or 12 * getattr(row, "every_years", 0), getattr(row, "authority", ""))
            for row in obligations() if word in getattr(row, "name", "").lower()]
    rows = [r for r in rows if r[0]]
    return min(rows, key=lambda r: r[0]) if rows else None


def _add_months(day: date, months: int) -> date:
    year, month = divmod(day.month - 1 + months, 12)
    return date(day.year + year, month + 1, min(day.day, 28 if month + 1 == 2 else 30 if month + 1 in (4, 6, 9, 11) else 31))


def _report_findings(r: InspectionReport, context: ModelContext) -> list[Finding]:
    found: list[Finding] = []
    for d in r.deficiencies:
        if d.status.lower() == "open":
            found.append(Finding("open-deficiency", f"open deficiency{' at ' + d.location if d.location else ''}: {d.comment or d.device}",
                                 Severity.PROBLEM))
    if r.devices_failed and not r.deficiencies:
        found.append(Finding("failed-devices", f"{r.devices_failed} device(s) or item(s) failed", Severity.PROBLEM))
    if r.devices_not_tested:
        found.append(Finding("not-tested", f"{r.devices_not_tested} device(s) were not tested (in-unit devices need access); schedule the "
                             "rest", Severity.CHECK))
    if r.accepted_by and re.fullmatch(r"N\s*/?\s*A|", r.accepted_by.strip(), re.I):
        found.append(Finding("not-accepted", "no one signed the report's acceptance for the association", Severity.CHECK))
    if r.customer_city and r.customer_city.strip().lower() not in ("sacramento", "-", ""):
        found.append(Finding("customer-record", f"the vendor's customer record places the association in {r.customer_city}; ask the "
                             "vendor to correct it", Severity.CHECK))
    if r.building and r.site_address:
        spec = building_of(context, r.site_address)
        if spec and spec != r.building:
            found.append(Finding("building-disagrees", f"the report calls {r.site_address} building {r.building.value}; the specification "
                                 f"places it in building {spec.value}", Severity.CHECK))
    found.append(next_inspection_due)   # the as-of lens's place: how long until the next inspection is due
    due, _authority = _due(r, _cadence(context.community, r.system))
    if not due and r.inspection_date:
        found.append(Finding("no-cadence", f"the specification gives no inspection cadence for a {r.system.value} system and the report "
                             "prints no next date", Severity.INFO))
    return found


register(SignalServiceReportModel())
register(InspectionReportModel())

__all__ = ["InspectedSystem", "Result", "EquipmentTally", "Deficiency", "InspectionReport", "SignalServiceReportModel", "InspectionReportModel"]
