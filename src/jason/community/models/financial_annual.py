"""The annual financial documents: the budget, the annual budget report and policy statement, the insurance summary, and
the CPA's review of the financial statements.

Civil Code 5300(a) has the association distribute an annual budget report 30 to 90 days before its fiscal year ends; 5300(b)
lists what it holds: (1) a pro forma operating budget on an accrual basis, (2) the reserve summary prepared under 5565,
(3) the reserve funding plan's summary with notice that the full plan is available on request, (4) a statement on deferred
repairs, (5) one on special assessments, (6) the funding mechanisms, (7) the reserve calculation procedures, (8) loans over
one year, (9) the insurance summary with the statutory statement, (10) and (11) the FHA and VA statements, and (12) the
completed "Charges for Documents Provided" form; (e) the Assessment and Reserve Funding Disclosure Summary (5570) goes with
it. Civil Code 5310(a) has the board distribute an annual policy statement in the same window with items (1) through (12).
Civil Code 5305 has a licensee of the California Board of Accountancy review the financial statement for any year in which
gross income exceeds $75,000, and a copy go to members within 120 days after the fiscal year closes.

The association's fiscal year is the calendar year.

Models, most specific first:

- ``PayhoaBudgetModel``: PayHOA's "Pro Forma Budget" packet (Budget Summary, Budget - Monthly) and its "Monthly Budget"
  report (the 2025 draft).
- ``DreBudgetWorksheetModel``: the developer's Bureau of Real Estate budget worksheets (form RE 623), prepared by the first
  manager for the public report.
- ``InsuranceSummaryModel``: the insurance summary disclosure (5300(b)(9)) filed on its own.
- ``AnnualReportModel``: an annual budget report or disclosure packet, from CiraConnect's "Resident Budget Package" or the
  association's own "Annual Disclosures", read for which 5300(b), 5300(e), and 5310(a) items it carries, with its budget
  (PayHOA's, or CiraConnect's operating, replacement, and consolidated fund budget, ``read_fund_budget``).
- ``FinancialReviewModel``: an independent accountant's review report (Propp, Christensen and Caniglia's layout) and the
  engagement's other papers (a representation letter, the tax returns).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from jason.community.document_models import DocumentModel, Finding, ModelContext, Severity, date_after, dates_in, register, squash
from jason.community.models.financial_common import MONEY_LINE, disk_studies, dollars, long_date, signed_cents, spec_units
from jason.community.reserve_study import ReserveDisclosure, read_disclosure
from jason.community.sources import manager_name
from jason.community.symbols import DocumentKind

FISCAL_YEAR_END = (12, 31)          # the association's fiscal year is the calendar year
REVIEW_DAYS = 120                   # CIV 5305
REVIEW_THRESHOLD_CENTS = 7_500_000  # CIV 5305: gross income over $75,000


def fiscal_year_end(year: int) -> date:
    return date(year, *FISCAL_YEAR_END)


def distribution_window(fiscal_year: int) -> tuple[date, date]:
    """The 30-to-90-day window before the end of the fiscal year *before* ``fiscal_year`` (CIV 5300(a), 5310(a))."""
    end = fiscal_year_end(fiscal_year - 1)
    return end - timedelta(days=90), end - timedelta(days=30)


def _window_findings(prepared: date | None, fiscal_year: int | None, what: str, authority: str) -> list[Finding]:
    if not fiscal_year:
        return []
    first, last = distribution_window(fiscal_year)
    if prepared is None:
        return [Finding("no-distribution-date", f"the text shows no date; the {what} for {fiscal_year} must go out between {first} and "
                        f"{last}", Severity.CHECK, authority)]
    if prepared > last:
        return [Finding("prepared-after-window", f"the {what} for {fiscal_year} is dated {prepared}, after the last day to distribute it "
                        f"({last})", Severity.PROBLEM, authority)]
    if prepared < first:
        return [Finding("prepared-before-window", f"the {what} for {fiscal_year} is dated {prepared}; it must be distributed between "
                        f"{first} and {last}", Severity.CHECK, authority)]
    return [Finding("distribution-window", f"dated {prepared}; distribution must fall between {first} and {last}", Severity.INFO, authority)]


# PayHOA's budget reports.

@dataclass(frozen=True)
class BudgetItem:
    label: str
    cents: int


@dataclass
class Budget:
    layout: str = ""                  # "payhoa pro forma", "payhoa monthly"
    title: str = ""
    fiscal_year: int | None = None
    generated: date | None = None
    draft: bool = False
    basis: str = ""                   # "cash" or "accrual" when the report names it
    items: tuple[BudgetItem, ...] = ()
    total_income_cents: int | None = None
    total_expenses_cents: int | None = None
    net_cents: int | None = None
    assessments_cents: int | None = None
    monthly_assessments_cents: int | None = None
    per_unit_monthly_cents: int | None = None
    reserve_transfer_cents: int | None = None
    reserve_lines: tuple[str, ...] = ()
    reserve_expenditures_cents: int | None = None   # a fund budget's planned spending from reserves (CiraConnect)


_RESERVE_LINE = re.compile(r"^(?:Transfer to )?Reserves?(?: Funding| Contribution| Transfer)?$|^Repayment$", re.I)
_PAYHOA_BUDGET = re.compile(r"^\s*[^\n]+\n\s*(Pro Forma Budget|Budget Summary|Monthly Budget|Budget - Monthly)\s*\n", re.I)


def _reserve_names(context: ModelContext) -> set[str]:
    lines = getattr(context.community, "reserve_budget_lines", None)
    try:
        return {str(v).casefold() for v in (lines() if callable(lines) else lines or {}).values()}
    except Exception:
        return set()


def read_payhoa_budget(text: str, context: ModelContext) -> Budget | None:
    """PayHOA's Budget Summary (label, total) or Monthly Budget (label, twelve months, total), wherever it sits in the text."""
    summary = re.search(r"\nBudget Summary\s*\n\s*Jan 1, (20\d\d) - Dec 31, 20\d\d\s*\nCategory\s*\nTotal\s*\n", "\n" + text)
    monthly = re.search(r"\n(?:Monthly Budget|Budget - Monthly)\s*\n\s*Jan 1, (20\d\d) - Dec 31, 20\d\d\s*\nCategory\s*\n", "\n" + text)
    if not summary and not monthly:
        return None
    b = Budget()
    flat_text = "\n" + text
    items: list[BudgetItem] = []
    if summary:
        b.layout = "payhoa pro forma" if re.search(r"Pro Forma Budget", text[:400]) else "payhoa budget summary"
        b.fiscal_year = int(summary.group(1))
        end = flat_text.find("Net Total", summary.end())
        body = flat_text[summary.end(): end + 40 if end > 0 else summary.end() + 8000]
        body = re.sub(r"\nGenerated [^\n]*\nPage \d+ of \d+[^\n]*\n\s*\n?[^\n]*\nBudget Summary\n[^\n]*\nCategory\nTotal\n", "\n", body)
        for m in re.finditer(r"^[ \t]*([^\n$]*[A-Za-z][^\n$]*?)[ \t]*\n[ \t]*(" + MONEY_LINE + r")[ \t]*$", body, re.M):
            items.append(BudgetItem(m.group(1).strip(), signed_cents(m.group(2)) or 0))
    else:
        b.layout = "payhoa monthly"
        b.fiscal_year = int(monthly.group(1))
        pattern = re.compile(r"^[ \t]*([^\n$]*[A-Za-z][^\n$]*?)[ \t]*\n((?:[ \t]*" + MONEY_LINE + r"[ \t]*\n){13})", re.M)
        for m in pattern.finditer(flat_text, monthly.end()):
            values = [signed_cents(v) or 0 for v in re.findall(MONEY_LINE, m.group(2))]
            label = m.group(1).strip()
            if label in ("Category", "Total") or label.startswith(("Jan '", "Dec '")):
                continue
            if not any(i.label == label for i in items):
                items.append(BudgetItem(label, values[-1]))
            if label == "Assessments" and b.monthly_assessments_cents is None:
                b.monthly_assessments_cents = values[0]
    b.items = tuple(items)
    by = {i.label.casefold(): i.cents for i in items}
    b.total_income_cents = by.get("total income")
    b.total_expenses_cents = by.get("total expenses")
    b.net_cents = by.get("net total")
    b.assessments_cents = by.get("assessments")
    if b.monthly_assessments_cents is None:
        month = re.search(r"\n[ \t]*Assessments[ \t]*\n[ \t]*(" + MONEY_LINE + r")[ \t]*\n(?:[ \t]*" + MONEY_LINE + r"[ \t]*\n){12}", flat_text)
        b.monthly_assessments_cents = signed_cents(month.group(1)) if month else (
            round(b.assessments_cents / 12) if b.assessments_cents else None)
    units = spec_units(context)
    if units and b.monthly_assessments_cents:
        b.per_unit_monthly_cents = round(b.monthly_assessments_cents / units)
    names = _reserve_names(context)
    reserve = [i for i in items if i.label.casefold() in names or _RESERVE_LINE.match(i.label)]
    if reserve:
        b.reserve_lines = tuple(i.label for i in reserve)
        b.reserve_transfer_cents = sum(i.cents for i in reserve)
    generated = re.search(r"Generated (\d\d-\d\d-\d{4})", text)
    b.generated = long_date(generated.group(1)) if generated else None
    b.draft = bool(re.search(r"\bDRAFT\b", text))
    head = text[:600]
    b.basis = "cash" if re.search(r"\bCash\b", head) else "accrual" if re.search(r"\bAccrual\b", head, re.I) else ""
    b.title = next((line.strip() for line in text.splitlines()[1:4] if re.search(r"budget", line, re.I)), "")
    return b


_FUND_VALUE = r"\(?\$[\d,]+\)?|-"


def _fund_rows(section: str) -> list[tuple[str, list[int | None]]]:
    """A fund budget's rows: a label line, then one line per column ("$311,040", "($81,515)", or "-" for none)."""
    rows = []
    for m in re.finditer(r"^[ \t]*([A-Za-z][^\n$]*?)[ \t]*\n((?:[ \t]*(?:" + _FUND_VALUE + r")[ \t]*\n)+)", section, re.M):
        values = [None if v == "-" else signed_cents(v) for v in re.findall(_FUND_VALUE, m.group(2))]
        rows.append((m.group(1).strip(), values))
    return rows


def _consolidated(values: list[int | None]) -> int | None:
    """The consolidated column. Three values are operating, replacement, consolidated; with two, a pair that cancels is a
    transfer between the funds (consolidated nil), and otherwise the last is the consolidated figure."""
    present = [v for v in values if v is not None]
    if not present:
        return None
    if len(values) == 2 and None not in values and values[0] + values[1] == 0:
        return 0
    return values[-1]


def read_fund_budget(text: str, context: ModelContext) -> Budget | None:
    """CiraConnect's "Revenue and Expense Budget Summary for FY yyyy": operating fund, replacement fund, and consolidated
    columns. The assessment allocation moves the reserve contribution from the operating fund to the replacement fund, and
    the replacement fund's capital expenditures are the year's planned spending from reserves."""
    head = re.search(r"Revenue and Expense Budget Summary for FY (20\d\d)\s*\n\s*Operating Fund\s*\n", text)
    if not head:
        return None
    end = re.search(r"\n[ \t]*Net Surplus \(Deficit\)[ \t]*\n(?:[ \t]*(?:" + _FUND_VALUE + r")[ \t]*\n)+", text[head.end():])
    section = text[head.end(): head.end() + (end.end() if end else 6000)]
    rows = _fund_rows(section)
    b = Budget(layout="ciraconnect fund budget", title=f"Revenue and Expense Budget Summary for FY {head.group(1)}",
               fiscal_year=int(head.group(1)))
    b.items = tuple(BudgetItem(label, cents) for label, values in rows if (cents := _consolidated(values)) is not None
                    and not label.startswith(("Replacement", "Fund", "Consolidated")))
    by = {label.casefold(): values for label, values in rows}
    b.total_income_cents = _consolidated(by.get("total of revenues", []))
    b.total_expenses_cents = _consolidated(by.get("total of expenses", []))
    b.net_cents = _consolidated(by.get("net surplus (deficit)", []))
    b.assessments_cents = _consolidated(by.get("regular assessments", []))
    if b.assessments_cents:
        b.monthly_assessments_cents = round(b.assessments_cents / 12)
        units = spec_units(context)
        b.per_unit_monthly_cents = round(b.monthly_assessments_cents / units) if units else None
    allocation = by.get("assessment allocation") or []
    reserve = [v for v in allocation if v is not None and v > 0]
    transfer = [v for v in by.get("total of transfer to reserves & other expenses", []) if v]
    if reserve or transfer:
        b.reserve_lines = tuple(x for x, have in (("Assessment Allocation", reserve), ("Transfer to Reserves", transfer)) if have)
        b.reserve_transfer_cents = (reserve[0] if reserve else 0) + (transfer[-1] if transfer else 0)
    capital = by.get("total of capital expenditures (non-capitalized)") or by.get("total of capital expenditures") or []
    if len(capital) >= 2 and capital[-2] is not None:
        b.reserve_expenditures_cents = capital[-2]
    printed = re.search(r"Printed on (\d{1,2}/\d{1,2}/\d{4})", text[head.end():])
    b.generated = long_date(printed.group(1)) if printed else None
    b.draft = bool(re.search(r"^\s*Draft\s*$", section, re.M | re.I))
    return b


def read_budget(text: str, context: ModelContext) -> Budget | None:
    """The first budget layout the text carries: PayHOA's reports, then a fund budget."""
    return read_payhoa_budget(text, context) or read_fund_budget(text, context)


def _study_plan(context: ModelContext, year: int) -> tuple[Any, Any] | None:
    """The newest study whose funding plan has ``year``, and that year's row."""
    rows = [(s, s.year(year)) for s in disk_studies(context) if s.year(year) and (s.fiscal_year or 0) <= year]
    return max(rows, key=lambda pair: (pair[0].fiscal_year or 0, pair[0].prepared or date.min)) if rows else None


def budget_findings(b: Budget, context: ModelContext) -> list[Finding]:
    found: list[Finding] = []
    if None not in (b.total_income_cents, b.total_expenses_cents, b.net_cents) and b.total_income_cents - b.total_expenses_cents != b.net_cents:
        found.append(Finding("budget-does-not-foot", f"income {dollars(b.total_income_cents)} less expenses {dollars(b.total_expenses_cents)} "
                             f"is not the net total {dollars(b.net_cents)}", Severity.PROBLEM))
    drawdown = (b.reserve_expenditures_cents is not None and b.reserve_transfer_cents is not None and b.net_cents is not None
                and b.net_cents == b.reserve_transfer_cents - b.reserve_expenditures_cents)
    if b.net_cents is not None and b.net_cents < 0 and drawdown:
        # A fund budget's deficit that is all reserve spending over the year's contribution draws on the reserve balance.
        found.append(Finding("reserve-drawdown", f"the consolidated budget shows a deficit of {dollars(-b.net_cents)}: the replacement fund "
                             f"plans {dollars(b.reserve_expenditures_cents)} of repairs and replacements against a contribution of "
                             f"{dollars(b.reserve_transfer_cents)}, drawing on reserves; the operating fund balances", Severity.INFO,
                             "CIV 5510(b)"))
    elif b.net_cents is not None and b.net_cents < 0:
        found.append(Finding("deficit-budget", f"the budget plans a deficit of {dollars(-b.net_cents)}", Severity.CHECK))
    if b.draft:
        found.append(Finding("draft-budget", "the budget is marked DRAFT; the adopted budget is the record members receive",
                         Severity.CHECK, "CIV 5300(b)(1)"))
    if b.basis == "cash":
        found.append(Finding("cash-basis", "the report is labeled cash basis; the pro forma operating budget shows revenue and expenses on "
                             "an accrual basis", Severity.CHECK, "CIV 5300(b)(1)"))
    if b.reserve_transfer_cents is None:
        found.append(Finding("no-reserve-line", "no reserve transfer line is in the budget", Severity.CHECK, "CIV 5300(b)(3)"))
    elif b.fiscal_year:
        plan = _study_plan(context, b.fiscal_year)
        if plan:
            study, row = plan
            gap = b.reserve_transfer_cents - row.contribution_cents
            if abs(gap) > 10_000:
                found.append(Finding("reserve-transfer-vs-study", f"the budget moves {dollars(b.reserve_transfer_cents)} to reserves in "
                                     f"{b.fiscal_year}; the FY{study.fiscal_year} study by {study.preparer} plans "
                                     f"{dollars(row.contribution_cents)}", Severity.CHECK, "CIV 5300(b)(3); CIV 5560(a)"))
            else:
                found.append(Finding("reserve-transfer-matches-study", f"the reserve transfer matches the FY{study.fiscal_year} study's "
                                     f"plan for {b.fiscal_year} ({dollars(row.contribution_cents)})", Severity.INFO, "CIV 5560(a)"))
    if b.fiscal_year and b.generated:
        first, last = distribution_window(b.fiscal_year)
        if b.generated > last:
            # A later run of the same budget prints a later date, so the stamp is not the distribution date.
            found.append(Finding("generated-after-window", f"this copy was generated {b.generated}, after the last day to distribute the "
                                 f"{b.fiscal_year} budget ({last}); confirm the copy members received went out by then", Severity.CHECK,
                                 "CIV 5300(a)"))
        elif b.generated >= first:
            found.append(Finding("distribution-window", f"generated {b.generated}; the report must reach members between {first} and "
                                 f"{last}", Severity.INFO, "CIV 5300(a)"))
    return found


class PayhoaBudgetModel(DocumentModel):
    kind = DocumentKind.BUDGET
    name = "payhoa-budget"
    required = ("fiscal_year", "total_income_cents", "total_expenses_cents", "reserve_transfer_cents")

    def parse(self, text: str, context: ModelContext) -> Budget | None:
        if not _PAYHOA_BUDGET.search(text or ""):
            return None
        return read_payhoa_budget(text, context)

    def check(self, b: Budget, context: ModelContext) -> list[Finding]:
        found = budget_findings(b, context)
        found.append(Finding("operating-budget-only", "a pro forma budget is item (1) of the annual budget report; the report also "
                             "carries the reserve summaries, statements, insurance summary, and the 5570 disclosure form",
                             Severity.INFO, "CIV 5300(b), (e)"))
        return found


# The developer's Bureau of Real Estate budget worksheets.

@dataclass(frozen=True)
class PhaseAssessment:
    phase: int
    lots: int | None
    cumulative_lots: int | None
    monthly_cents: int | None
    reserves_cents: int | None


@dataclass
class DreBudgetWorksheet:
    form: str = ""
    preparer: str = ""
    prepared: str = ""
    phases: tuple[PhaseAssessment, ...] = ()
    total_lots: int | None = None


class DreBudgetWorksheetModel(DocumentModel):
    kind = DocumentKind.BUDGET
    name = "dre-budget-worksheet"
    required = ("form", "phases")

    def parse(self, text: str, context: ModelContext) -> DreBudgetWorksheet | None:
        if not re.search(r"BUDGET WORKSHEET", text or "") or not re.search(r"RE 623|Bureau of Real Estate|Department of Real Estate", text, re.I):
            return None
        w = DreBudgetWorksheet(form="RE 623" if "RE 623" in text else "budget worksheet")
        w.preparer = manager_name(text, context.community)
        prepared = re.search(r"(?:January|February|March|April|May|June|July|August|September|October|November|December),? 20\d\d", text[:2000],
                             re.I)
        w.prepared = prepared.group(0) if prepared else ""
        flat = squash(text[:3000])
        phases = []
        for m in re.finditer(r"\b(\d)\s+(\d+)\s*\((\d+)\)\s*\$([\d,.]+)\s*\$([\d,.]+)", flat):
            phases.append(PhaseAssessment(int(m.group(1)), int(m.group(2)), int(m.group(3)), signed_cents(m.group(4)), signed_cents(m.group(5))))
        w.phases = tuple(phases)
        w.total_lots = max((p.cumulative_lots or 0 for p in phases), default=None) or None
        return w

    def check(self, w: DreBudgetWorksheet, context: ModelContext) -> list[Finding]:
        found = [Finding("developer-budget", "a developer's budget prepared for the public report, not an annual budget the association "
                         "adopted", Severity.INFO)]
        units = spec_units(context)
        if w.total_lots and units and w.total_lots != units:
            found.append(Finding("lot-count", f"the worksheet's phases reach {w.total_lots} lots; the specification has {units} units",
                                 Severity.CHECK))
        return found


# The insurance summary disclosure.

@dataclass(frozen=True)
class CoverageLine:
    kind: str                          # "general liability", "property", "earthquake", "flood", "fidelity"
    none: bool = False                 # the summary says "None"


@dataclass
class InsuranceSummary:
    lines: tuple[CoverageLine, ...] = ()
    insurers: tuple[str, ...] = ()
    policy_periods: tuple[str, ...] = ()
    statutory_statement: bool = False  # the 5300(b)(9) paragraph
    nonrenewal_notice: bool = False    # the 5810 paragraph
    distribution_claim: bool = False   # "distributed not less than 30 days nor more than 90 days"


_COVERAGES = (("general liability", r"GENERAL LIABILITY INSURANCE"), ("property", r"PROPERTY INSURANCE"),
              ("earthquake", r"EARTHQUAKE INSURANCE"), ("flood", r"FLOOD INSURANCE"), ("fidelity", r"FIDELITY BOND INSURANCE|FIDELITY"))
_STATEMENT = r"should not be considered a substitute for the complete policy terms"


def read_insurance_summary(text: str) -> InsuranceSummary:
    s = InsuranceSummary()
    lines = []
    for kind, pattern in _COVERAGES:
        m = re.search(r"(?:^|\n)[ \t]*(?:" + pattern + r")[ \t]*\n[ \t]*(None)?", text)
        if m:
            lines.append(CoverageLine(kind, bool(m.group(1))))
    s.lines = tuple(lines)
    s.insurers = tuple(dict.fromkeys(squash(m.group(0)) for m in re.finditer(
        r"^[ \t]*[A-Z][A-Za-z&.,' ]*(?:Insurance Company|Insurance Group|Insurance Co\.?|Indemnity Company|Casualty Company)[ \t]*$", text, re.M)))
    s.policy_periods = tuple(dict.fromkeys(re.findall(r"\d\d/\d\d/\d{4} - \d\d/\d\d/\d{4}", text)))
    flat = squash(text)
    s.statutory_statement = bool(re.search(_STATEMENT, flat, re.I))
    s.nonrenewal_notice = bool(re.search(r"5810|notice of nonrenewal", flat, re.I))
    s.distribution_claim = bool(re.search(r"not less than 30 days nor more than 90 days", flat, re.I))
    return s


def _spec_policy_kinds(context: ModelContext) -> set[str]:
    insurance = getattr(context.community, "insurance", None)
    try:
        catalog = insurance() if callable(insurance) else insurance
        return {p.kind.value for p in catalog.policies}
    except Exception:
        return set()


def insurance_findings(s: InsuranceSummary, context: ModelContext) -> list[Finding]:
    found: list[Finding] = []
    if not s.statutory_statement:
        found.append(Finding("no-insurance-statement", "the summary lacks the statement that it is no substitute for the policies' terms",
                             Severity.PROBLEM, "CIV 5300(b)(9)"))
    else:
        found.append(Finding("statement-typeface", "the statement must be in at least 10-point boldface; the text cannot show the type",
                             Severity.INFO, "CIV 5300(b)(9)"))
    listed = {line.kind for line in s.lines}
    for kind in ("property", "general liability", "earthquake", "flood", "fidelity"):
        if kind not in listed:
            found.append(Finding("insurance-summary-lacks-" + kind.replace(" ", "-"), f"the summary has no {kind} line", Severity.CHECK,
                                 "CIV 5300(b)(9)"))
    policies = _spec_policy_kinds(context)
    for line in s.lines:
        if line.none and line.kind == "flood" and "flood" in policies:
            found.append(Finding("flood-listed-as-none", "the summary says the association has no flood insurance; the specification lists "
                                 "a flood policy for each building", Severity.PROBLEM, "CIV 5300(b)(9)"))
    return found


class InsuranceSummaryModel(DocumentModel):
    kind = DocumentKind.ANNUAL_DISCLOSURE
    name = "insurance-summary-disclosure"
    required = ("lines", "insurers")

    def parse(self, text: str, context: ModelContext) -> InsuranceSummary | None:
        text = text or ""
        if not re.search(r"INSURANCE SUMMARY DISCLOSURE", text) or re.search(r"Annual Disclosures|Annual Policy Statement", text):
            return None
        return read_insurance_summary(text)

    def check(self, s: InsuranceSummary, context: ModelContext) -> list[Finding]:
        return insurance_findings(s, context)


# The annual budget report and policy statement packets.

BUDGET_REPORT_ITEMS: dict[str, tuple[str, str]] = {
    "5300(b)(1)": ("pro forma operating budget", r"pro forma|operating budget|budget summary|Revenue and Expense Budget"),
    "5300(b)(2)": ("reserve summary", r"summary of (?:the )?(?:association.s )?reserves|reserve summary|summary of association reserves|"
                   r"component funding summary|funding summary|5565|estimated replacement cost,? (?:and )?estimated remaining"),
    "5300(b)(3)": ("reserve funding plan summary", r"reserve funding plan|funding plan"),
    "5300(b)(4)": ("statement on deferred repairs", r"\bdefer|not (?:to )?undertake|5300\s*\(b\)\s*\(4\)"),
    "5300(b)(5)": ("statement on special assessments", r"special assessments? (?:will|is|are|would) (?:not )?be required|anticipate[sd]? "
                   r"(?:the levy of )?(?:any |one or more )?special assessments?|5300\s*\(b\)\s*\(5\)"),
    "5300(b)(6)": ("reserve funding mechanisms", r"mechanism"),
    "5300(b)(7)": ("reserve calculation procedures", r"procedures (?:used )?for (?:the )?calculat|calculation and establishment|"
                   r"5300\s*\(b\)\s*\(7\)|method of calculation"),
    "5300(b)(8)": ("statement on loans", r"outstanding loans?|loans? with an original term"),
    # A row of the charges form ("Insurance summary Sections 5300 and 4525(a)(3) 15.00") prices the item; it is not the item.
    "5300(b)(9)": ("insurance summary", r"summary of the association.s policies of insurance|insurance summary(?!\W+Sections? \d)"),
    "5300(b)(10)": ("FHA statement", r"Federal Housing Administration"),
    "5300(b)(11)": ("VA statement", r"Veterans Affairs"),
    # The form's heading can drop out of the text; its first lines stay.
    "5300(b)(12)": ("Charges for Documents Provided form", r"charges? for documents provided|Check or Complete Applicable Column"),
    "5300(e)": ("Assessment and Reserve Funding Disclosure Summary", r"Assessment and Reserve Funding Disclosure(?! summary\W+Sections? \d)"),
}
POLICY_STATEMENT_ITEMS: dict[str, tuple[str, str]] = {
    "5310(a)(1)": ("person designated for official communications", r"official communications"),
    "5310(a)(2)": ("notice to two addresses", r"two (?:different )?(?:specified )?addresses|secondary address"),
    "5310(a)(3)": ("general notice posting location", r"posting (?:of )?general notices|general notice location|location for posting"),
    # The member's option to receive general notices by individual delivery (4045(b)); a hearing notice "by personal or
    # individual delivery" is not it.
    "5310(a)(4)": ("option of individual delivery", r"\b(?:option|right|request|elect)\b[^.]{0,80}individual delivery|individual delivery"
                   r"[^.]{0,80}(?:general notice|4045)"),
    "5310(a)(5)": ("right to minutes", r"minutes"),
    "5310(a)(6)": ("assessment collection policy", r"collection polic|assessment collection"),
    "5310(a)(7)": ("lien enforcement policy", r"\blien"),
    "5310(a)(8)": ("discipline policy", r"disciplin|schedule of (?:fines|penalties)|fine schedule|rules enforcement"),
    "5310(a)(9)": ("dispute resolution summary", r"dispute resolution"),
    "5310(a)(10)": ("architectural approval requirements", r"architectural|physical change|improvement request"),
    "5310(a)(11)": ("overnight payment address", r"overnight"),
}


@dataclass
class AnnualReport:
    preparer: str = ""                # the manager the report names, else "the association"
    fiscal_year: int | None = None
    prepared: date | None = None
    monthly_assessment_cents: int | None = None
    annual_assessment_cents: int | None = None
    total_revenue_cents: int | None = None
    total_expenses_cents: int | None = None
    net_cents: int | None = None
    budget: Budget | None = None
    budget_report_items: tuple[str, ...] = ()     # the 5300(b) and (e) items the text carries
    policy_items: tuple[str, ...] = ()            # the 5310(a) items the text carries
    insurance: InsuranceSummary | None = None
    disclosure: ReserveDisclosure | None = None   # the 5570 form's figures, when the packet carries it
    full_plan_notice: bool = False                # 5300(b)(3): the full reserve plan is available on request
    request_instructions: bool = False            # 5320(a)(2): how to request a complete copy at no cost
    flood_policies_enclosed: tuple[str, ...] = () # flood policy numbers the packet's own certificate or declarations list


# The association's packets open with a table of contents naming every item ("Reserve Funding Mechanism", "Statement
# regarding outstanding loans"); a phrase that matches there says nothing about the item itself.
_CONTENTS = re.compile(r"following information and disclosures|Annual Disclosures - Civ\.?\s*§?\s*5310", re.I)
_CONTENTS_END = re.compile(r"\n[ \t]*(?:[A-Z][A-Z &]+ASSOCIATION[ \t]*\n[ \t]*Contact Information|Annual Policy Statement)[ \t]*\n")


def _after_contents(text: str) -> int:
    """Where the packet's body starts: after its table of contents, when it has one."""
    toc = _CONTENTS.search(text[:8000])
    if not toc:
        return 0
    end = _CONTENTS_END.search(text, toc.end(), toc.end() + 6000)
    return end.start() if end else toc.end()


def _items(body: str, rules: dict[str, tuple[str, str]]) -> tuple[str, ...]:
    return tuple(key for key, (_what, pattern) in rules.items() if re.search(pattern, body, re.I))


class AnnualReportModel(DocumentModel):
    kinds = (DocumentKind.ANNUAL_DISCLOSURE, DocumentKind.BUDGET)
    name = "annual-budget-report"
    required = ("fiscal_year", "budget_report_items", "policy_items")

    def parse(self, text: str, context: ModelContext) -> AnnualReport | None:
        text = text or ""
        if not re.search(r"Annual Budget Report|Annual Disclosures|Annual Policy Statement", text[:6000], re.I):
            return None
        a = AnnualReport()
        a.preparer = manager_name(text[:8000], context.community) or "the association"
        body = squash(text[_after_contents(text):])
        a.budget_report_items = _items(body, BUDGET_REPORT_ITEMS)
        a.policy_items = _items(body, POLICY_STATEMENT_ITEMS)
        head = squash(text[:6000])
        year = (re.search(r"Annual Budget Report for Fiscal Year (20\d\d)", head) or re.search(r"adopted (20\d\d) Annual Budget", head)
                or re.search(r"(20\d\d) Annual Budget", head) or re.search(r"(?:Fiscal Year|FY) (20\d\d)", head)
                or re.search(r"(20\d\d) - Pro Forma Budget|Pro Forma Budget\W+(20\d\d)", head))
        if year:
            a.fiscal_year = int(next(g for g in year.groups() if g))
        a.prepared = date_after(r"Prepared on:?", text[:8000]) or date_after(r"Printed on:?", text[:8000])
        if a.prepared is None:
            letter = re.search(r"\n\s*([A-Z][a-z]+ \d{1,2}, 20\d\d)\s*\n\s*Dear (?:Member|Homeowner|Owner)", text[:8000])
            a.prepared = long_date(letter.group(1)) if letter else None
        amount = re.search(r"levied against each (?:lot|unit)[^$]*\$([\d,]+(?:\.\d\d)?)[^$]*installments in\s*(?:the\s*)?amount of\s*\$([\d,]+\.\d\d)", head)
        if amount:
            a.annual_assessment_cents, a.monthly_assessment_cents = signed_cents(amount.group(1)), signed_cents(amount.group(2))
        cira = re.search(r"TOTAL of Revenues\s*((?:\(?\$[\d,]+\)?\s*|-\s*){1,3})", body)
        if cira:
            values = re.findall(r"\(?\$[\d,]+\)?", cira.group(1))
            a.total_revenue_cents = signed_cents(values[-1]) if values else None
        expenses = re.search(r"TOTAL of Expenses\s*((?:\(?\$[\d,]+\)?\s*|-\s*){1,3})", body)
        if expenses:
            values = re.findall(r"\(?\$[\d,]+\)?", expenses.group(1))
            a.total_expenses_cents = signed_cents(values[-1]) if values else None
        a.budget = read_budget(text, context)
        if a.budget and a.total_revenue_cents is None:
            a.total_revenue_cents, a.total_expenses_cents = a.budget.total_income_cents, a.budget.total_expenses_cents
        a.net_cents = a.budget.net_cents if a.budget else None
        if "5300(b)(9)" in a.budget_report_items:
            a.insurance = read_insurance_summary(text)
            a.flood_policies_enclosed = tuple(dict.fromkeys(re.findall(
                r"^[ \t]*\d\d/\d\d/\d{4} - \d\d/\d\d/\d{4}[ \t]+(\d{8,})[ \t]+Bldg", text, re.M)))
        if "5300(e)" in a.budget_report_items:
            a.disclosure = read_disclosure(text)
        # A linked file's name can land after the sentence it sits in ("A copy of the full / is available free online, and upon
        # request ... / Reserve Study 2026.pdf").
        a.full_plan_notice = bool(re.search(r"(?:full|complete|copy of the)[^.]{0,40}(?:reserve study|reserve plan|study)[^.]{0,120}"
                                            r"(?:available|upon request|on request)|(?:full|complete) (?:reserve )?(?:study |plan )?is "
                                            r"available[^.]{0,60}request[^.]{0,60}reserve study", squash(text), re.I))
        a.request_instructions = bool(re.search(r"request[^.]{0,80}(?:complete|full) copy|(?:complete|full) copy[^.]{0,80}request", body, re.I))
        return a

    def check(self, a: AnnualReport, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        for key, (what, _pattern) in BUDGET_REPORT_ITEMS.items():
            if key not in a.budget_report_items:
                found.append(Finding("lacks-" + key.replace("(", "-").replace(")", ""), f"no {what} was found in the text", Severity.CHECK,
                                     "CIV " + key))
        for key, (what, _pattern) in POLICY_STATEMENT_ITEMS.items():
            if key not in a.policy_items:
                found.append(Finding("lacks-" + key.replace("(", "-").replace(")", ""), f"no {what} was found in the text", Severity.CHECK,
                                     "CIV " + key))
        if "5300(b)(3)" in a.budget_report_items and not a.full_plan_notice:
            found.append(Finding("no-full-plan-notice", "the text does not tell members the full reserve plan is available on request",
                                 Severity.CHECK, "CIV 5300(b)(3)"))
        what, authority = "annual budget report and policy statement", "CIV 5300(a); CIV 5310(a)"
        if a.prepared is None and a.budget and a.budget.generated and a.fiscal_year:
            last = distribution_window(a.fiscal_year)[1]
            late = a.budget.generated > last
            found.append(Finding("packet-after-budget", f"the packet carries no date of its own; its budget was generated {a.budget.generated}, "
                                 + (f"after the last day to distribute ({last}), so the packet went out no earlier" if late else
                                    f"so it went out no earlier; confirm it reached members by {last}"),
                                 Severity.CHECK, authority))
        else:
            found += _window_findings(a.prepared, a.fiscal_year, what, authority)
        if a.insurance:
            for f in insurance_findings(a.insurance, context):
                if f.code.startswith("insurance-summary-lacks"):
                    continue
                if f.code == "flood-listed-as-none" and a.flood_policies_enclosed:
                    f = Finding(f.code, f"{f.message}, and this packet itself encloses {len(a.flood_policies_enclosed)} flood policies "
                                f"({', '.join(a.flood_policies_enclosed)})", f.severity, f.authority)
                found.append(f)
        d = a.disclosure
        if d is not None:
            if d.fiscal_year and a.fiscal_year and d.fiscal_year != a.fiscal_year:
                found.append(Finding("disclosure-other-year", f"the 5570 form enclosed is for the fiscal year ending {d.fiscal_year}; the "
                                     f"budget is for {a.fiscal_year}. Check it reflects the most recent study", Severity.CHECK,
                                     "CIV 5570(a); CIV 5565"))
            if d.sufficient_for_30_years is False:
                found.append(Finding("reserves-insufficient", "the 5570 form answers No: projected reserves will not cover the next 30 "
                                     "years; item (4) must state the additional assessments needed", Severity.INFO, "CIV 5570(a)(3), (4)"))
            if d.percent_funded is not None:
                found.append(Finding("percent-funded", f"the 5570 form reports reserves {d.percent_funded:.0%} funded", Severity.INFO,
                                     "CIV 5570(a)(6)"))
        if a.budget:
            found += [f for f in budget_findings(a.budget, context) if f.code not in ("generated-after-window", "distribution-window",
                                                                                     "prepared-before-window", "no-distribution-date")]
        if a.monthly_assessment_cents and a.budget and a.budget.per_unit_monthly_cents \
                and abs(a.monthly_assessment_cents - a.budget.per_unit_monthly_cents) > 100:
            found.append(Finding("assessment-vs-budget", f"the letter sets {dollars(a.monthly_assessment_cents)} a month per unit; the budget's "
                                 f"assessments come to {dollars(a.budget.per_unit_monthly_cents)} per unit a month", Severity.CHECK))
        found.append(Finding("delivery", "the report goes to every member by individual delivery, in full or as a summary whose first "
                             "page tells how to get the full report free", Severity.INFO, "CIV 5320(a)"))
        return found


# The CPA's review.

@dataclass
class FinancialReview:
    fiscal_year: int | None = None
    firm: str = ""
    report_date: date | None = None
    papers: tuple[str, ...] = ()       # "review report", "financial statements", "representation letter", "tax return", "transmittal"
    conclusion: str = ""               # "no material modifications" or the modified wording
    gross_income_cents: int | None = None
    replacement_fund: bool = False     # supplementary information on future major repairs and replacements


class FinancialReviewModel(DocumentModel):
    kind = DocumentKind.FINANCIAL_REVIEW
    name = "cpa-review"
    required = ("fiscal_year", "firm", "report_date")

    def parse(self, text: str, context: ModelContext) -> FinancialReview | None:
        text = text or ""
        flat = squash(text)
        papers = []
        if re.search(r"ACCOUNTANT'?S REVIEW REPORT|We have reviewed the accompanying financial statements", flat, re.I):
            papers.append("review report")
        if re.search(r"STATEMENTS? OF REVENUES, EXPENSES AND CHANGES IN FUND BALANCES", flat, re.I):
            papers.append("financial statements")
        if re.search(r"We are providing this letter in connection with your review", flat, re.I):
            papers.append("representation letter")
        if re.search(r"Form 1120-?H|Form 199|U\.S\. Income Tax Return", flat):
            papers.append("tax return")
        if re.search(r"Civil Code Section 5305", flat, re.I):
            papers.append("transmittal")
        if not papers:
            return None
        r = FinancialReview(papers=tuple(papers))
        year = (re.search(r"balance sheets? as of December 31, (20\d\d)", flat, re.I) or re.search(r"RE: (20\d\d) Financial Review", flat)
                or re.search(r"For the Years? Ended December 31, (20\d\d)", flat, re.I) or re.search(r"December 31, (20\d\d)", flat))
        r.fiscal_year = int(year.group(1)) if year else None
        firm = (re.search(r"independent accounting firm of ([A-Z][A-Za-z,.& ]+?(?:LLC|LLP|PC|CPAs?|Inc\.?))", flat)
                or re.search(r"\b([A-Z][A-Za-z]+ Certified Public Accountants?,? (?:PC|LLP|LLC|Inc\.?))", flat)
                or re.search(r"\b([A-Z][A-Za-z]+(?:,? [A-Z][A-Za-z]+)*,? (?:and|&) [A-Z][A-Za-z]+,? (?:LLC|LLP))", flat))
        r.firm = firm.group(1).strip() if firm else ""
        if "review report" in papers:
            tail = re.search(r"(?:not aware of any material modifications|do not express an opinion)(.{0,6000})", flat, re.I | re.S)
            dates = [d for d in dates_in(tail.group(1)) if not r.fiscal_year or d.year > r.fiscal_year] if tail else []
            r.report_date = dates[0] if dates else None
        else:
            dates = [d for d in dates_in(text) if r.fiscal_year and d.year > r.fiscal_year]
            r.report_date = dates[0] if dates else None
        if re.search(r"we are not aware of any material modifications that should be made", flat, re.I):
            r.conclusion = "no material modifications"
        else:
            modified = re.search(r"(except for [^.]{0,200}\.|Basis for (?:Qualified|Adverse) Conclusion[^.]{0,200}\.)", flat, re.I)
            r.conclusion = modified.group(1) if modified else ""
        revenues = []
        for m in re.finditer(r"Total revenues\s*((?:\$?\s*[\d,]{3,}\s*){1,4})", flat, re.I):
            revenues += [int(x.replace(",", "")) * 100 for x in re.findall(r"\d{1,3}(?:,\d{3})+", m.group(1))]
        r.gross_income_cents = max(revenues) if revenues else None
        r.replacement_fund = bool(re.search(r"Future Major Repairs and Replacements", flat, re.I))
        return r

    def check(self, r: FinancialReview, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if "review report" not in r.papers:
            found.append(Finding("no-review-report", "the file carries the review engagement's other papers ("
                                 + ", ".join(r.papers) + ") but not the accountant's review report", Severity.CHECK, "CIV 5305"))
        required = r.gross_income_cents is None or r.gross_income_cents > REVIEW_THRESHOLD_CENTS
        if r.fiscal_year and r.report_date:
            due = fiscal_year_end(r.fiscal_year) + timedelta(days=REVIEW_DAYS)
            if "review report" in r.papers and r.report_date > due:
                # 5305 requires the review only in a year gross income exceeds $75,000; the governing documents may require more.
                found.append(Finding("review-after-120-days", f"the review of {r.fiscal_year} is dated {r.report_date}, after the {due} "
                                     "deadline to distribute it to members" + ("" if required else
                                     f"; with gross income of {dollars(r.gross_income_cents)} the statute did not require the review "
                                     "that year, so check the governing documents"), Severity.PROBLEM if required else Severity.CHECK,
                                     "CIV 5305"))
            elif "review report" in r.papers:
                found.append(Finding("review-distribution", f"the review is dated {r.report_date}; members must receive it by {due} by "
                                     "individual delivery", Severity.INFO, "CIV 5305; CIV 4040"))
        if "review report" in r.papers and not r.conclusion:
            found.append(Finding("no-conclusion", "the review report's conclusion was not found in the text", Severity.CHECK, "CIV 5305"))
        if r.conclusion and r.conclusion != "no material modifications":
            found.append(Finding("modified-conclusion", f"the accountant's conclusion is modified: {r.conclusion[:160]}", Severity.PROBLEM,
                                 "CIV 5305"))
        if r.gross_income_cents and r.gross_income_cents > REVIEW_THRESHOLD_CENTS:
            found.append(Finding("review-required", f"gross income of {dollars(r.gross_income_cents)} exceeds $75,000, so the review is "
                                 "required", Severity.INFO, "CIV 5305"))
        elif r.gross_income_cents:
            found.append(Finding("review-not-required", f"gross income of {dollars(r.gross_income_cents)} is not over $75,000, so the statute "
                                 "did not require the review that year", Severity.INFO, "CIV 5305"))
        if r.firm and not re.search(r"Certified Public Accountant|CPA", r.firm, re.I):
            found.append(Finding("confirm-licensee", f"confirm {r.firm} holds a California Board of Accountancy license", Severity.INFO,
                                 "CIV 5305"))
        return found


register(PayhoaBudgetModel())
register(DreBudgetWorksheetModel())
register(InsuranceSummaryModel())
register(AnnualReportModel())
register(FinancialReviewModel())

__all__ = ["Budget", "BudgetItem", "PayhoaBudgetModel", "DreBudgetWorksheet", "PhaseAssessment", "DreBudgetWorksheetModel",
           "InsuranceSummary", "CoverageLine", "InsuranceSummaryModel", "AnnualReport", "AnnualReportModel", "FinancialReview",
           "FinancialReviewModel", "BUDGET_REPORT_ITEMS", "POLICY_STATEMENT_ITEMS", "distribution_window", "read_payhoa_budget",
           "read_fund_budget", "read_budget", "read_insurance_summary"]
