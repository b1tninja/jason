"""A manager's periodic report of its open cases: the prior manager's weekly "Case Performance" report.

The Helsing Group emailed the board a Case Performance report each week (2023): charts of case ages and counts by
type, then "Cases Currently Open", one row per case with its number and subject ("Mystique - 3022 Enchanted Walk -
Garage Repairs", "Mystique - 5601 Whimsical - Claim No. 5020000018-1-1, Claim Outcome Letter"). The subject is what
the manager was working on; it is the only place some repairs and claims are tied to a unit. ``ManagerCaseReportModel``
reads the report's date and its open cases; the incident history reads each case that names a unit, a claim, or work as
evidence, once per case however many weekly reports carry it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from jason.community.document_models import DocumentModel, Finding, ModelContext, Severity, register
from jason.community.symbols import DocumentKind

_OPEN = re.compile(r"Cases Currently Open.*?\n(.*?)(?:\n\s*This chart|\Z)", re.S | re.I)
_ROW = re.compile(r"^\s*(\d{8})\s+(.*?)(?:\s{2,}([A-Z][A-Za-z_/ ]+?))?\s*$")
_WORK = re.compile(r"repair|leak|claim|damage|roof|water|intrusion|light out|fire sprinkler|backflow|tree|irrigation|mold|gutter|"
                   r"stucco|paint|pest|rodent|termite|garage|door|gate|drain|flood|vandal|break", re.I)


@dataclass(frozen=True)
class OpenCase:
    number: str
    subject: str
    case_type: str = ""


@dataclass
class ManagerCaseReport:
    manager: str = ""
    as_of: date | None = None
    open_cases: tuple[OpenCase, ...] = ()


def _as_of(text: str) -> date | None:
    m = re.search(r"Date:\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(\d{4})",
                  text or "")
    if not m:
        return None
    months = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
    return date(int(m.group(3)), months.index(m.group(1).lower()) + 1, int(m.group(2)))


def open_cases(text: str) -> tuple[OpenCase, ...]:
    """The open cases, from either text layout: one field per line (number, subject, type), or one row per line."""
    block = _OPEN.search(text or "")
    if not block:
        return ()
    lines = [ln.strip() for ln in block.group(1).splitlines() if ln.strip()]
    lines = [ln for ln in lines if ln.lower() not in ("case number", "subject", "type")]
    out = []
    i = 0
    while i < len(lines):
        if re.fullmatch(r"\d{8}", lines[i]):
            subject = lines[i + 1] if i + 1 < len(lines) and not re.fullmatch(r"\d{8}", lines[i + 1]) else ""
            kind = lines[i + 2] if subject and i + 2 < len(lines) and not re.fullmatch(r"\d{8}", lines[i + 2]) else ""
            if subject:
                out.append(OpenCase(lines[i], " ".join(subject.split()), kind))
            i += 1 + bool(subject) + bool(kind)
            continue
        m = _ROW.match(lines[i])
        if m and m.group(2).strip():
            out.append(OpenCase(m.group(1), " ".join(m.group(2).split()), (m.group(3) or "").strip()))
        i += 1
    return tuple(out)


def is_work_case(case: OpenCase) -> bool:
    """A case about the property: work, a claim, or a named unit's problem."""
    return bool(_WORK.search(case.subject))


class ManagerCaseReportModel(DocumentModel):
    kind = DocumentKind.MANAGER_CASE_REPORT
    name = "manager-case-report"
    required = ("as_of", "open_cases")

    def parse(self, text: str, context: ModelContext) -> ManagerCaseReport | None:
        if not re.search(r"Cases Currently Open", text or "", re.I):
            return None
        manager = "The Helsing Group" if re.search(r"helsing", text or "", re.I) else ""
        return ManagerCaseReport(manager, _as_of(text), open_cases(text))

    def check(self, r: ManagerCaseReport, context: ModelContext) -> list[Finding]:
        work = [c for c in r.open_cases if is_work_case(c)]
        return [Finding("open-work", f"case {c.number}: {c.subject}", Severity.INFO) for c in work]


register(ManagerCaseReportModel())


__all__ = ["OpenCase", "ManagerCaseReport", "ManagerCaseReportModel", "open_cases", "is_work_case"]
