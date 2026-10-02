"""The monthly financial reports the board reviews (Civil Code 5500): PayHOA's treasurer's report packet and the prior
manager's (The Helsing Group) monthly financial statements.

Civil Code 5500 has the board review each month a current reconciliation of the operating (a) and reserve (b) accounts,
actual revenue and expenses against the budget (c), the banks' statements (d), an income and expense statement for the
operating and reserve accounts (e), and the check register, general ledger, and delinquent assessment receivable
reports (f). Both packets carry most of these; the models record which.

``TreasurerReportModel`` reads PayHOA's "Treasurer's Report" packet (the index of included reports, the balance sheet,
the aging total, profit vs loss, and each bank reconciliation's summary). The packet is generated from the ledger, so a
copy can be checked against itself (the balance sheet foots; each reconciliation's arithmetic holds), against the month
it is filed under (copies named 2025-06 and 2025-07 were the November 2025 report), and against PayHOA's month-end balance
sheet today (``data/payhoa/balance-sheets.json``, from ``jason ledger --fetch``).

``HelsingStatementModel`` reads The Helsing Group's "Monthly Financial Statements" (2023 to January 2024): the fund
balance sheet (operating, reserve, total), and the operating budget comparison with the reserve contribution. Its
"Due to Reserve" liability is money the operating fund owes the reserve fund.

Both packets carry owners' balances (aging, prepaids, ledgers); the records keep totals only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from jason.community.document_models import DocumentModel, Finding, ModelContext, Severity, register
from jason.community.models.financial_common import (
    MONEY_LINE,
    data_json,
    dollars,
    file_period,
    line_amount,
    long_date,
    month_end,
    signed_cents,
    spec_bank_accounts,
)
from jason.community.content import aging_units as aged_units
from jason.community.symbols import DocumentKind

SHEETS = "payhoa/balance-sheets.json"
MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


@dataclass(frozen=True)
class AccountBalance:
    label: str
    cents: int


@dataclass(frozen=True)
class ReconciliationSummary:
    """One "Bank Reconciliation" page's summary block."""

    account: str                      # "Operating Account", "Reserve Account"
    start: date | None = None
    end: date | None = None
    beginning_cents: int | None = None
    payments_cleared: int | None = None
    payments_cleared_cents: int | None = None
    deposits_cleared: int | None = None
    deposits_cleared_cents: int | None = None
    ending_cents: int | None = None
    payments_open_cents: int | None = None
    deposits_open_cents: int | None = None
    register_cents: int | None = None


@dataclass
class TreasurerReport:
    title: str = ""
    title_period: str = ""            # the month the title names ("2025-11", "August 2024" -> "2024-08")
    period: str = ""                  # the month the balance sheet reports
    balance_sheet_date: date | None = None
    generated: date | None = None
    ledger_start: date | None = None
    ledger_end: date | None = None
    included: tuple[str, ...] = ()
    bank_accounts: tuple[AccountBalance, ...] = ()
    total_bank_cents: int | None = None
    total_assets_cents: int | None = None
    total_liabilities_cents: int | None = None
    total_equity_cents: int | None = None
    total_liabilities_equity_cents: int | None = None
    reserve_accounts: tuple[AccountBalance, ...] = ()
    reserve_cents: int | None = None
    receivable_cents: int | None = None        # the aging report's total due
    pl_start: date | None = None
    pl_end: date | None = None
    income_cents: int | None = None
    expenses_cents: int | None = None
    net_cents: int | None = None
    reconciliations: tuple[ReconciliationSummary, ...] = field(default_factory=tuple)
    redacted: bool = False                     # the member version: no unit in the receivables aging table
    named_redacted: bool = False               # the file name says "Redacted"
    aging_units: int = 0                       # units the aging table lists (the board version lists them all)


_TITLE = re.compile(r"Treasurer'?s Report(?:[ \t]*-?[ \t]*([^\n]*))?", re.I)
_RECON = re.compile(r"Bank Reconciliation:[ \t]*([^\n]+?)[ \t]*\n[ \t]*([A-Z][a-z]+\.? \d{1,2}, \d{4})[ \t]*-[ \t]*([A-Z][a-z]+\.? \d{1,2}, \d{4})[ \t]*\n"
                    r"[ \t]*Statement beginning balance")
_OLD_RESERVE = re.compile(r"^[ \t]*(Old Reserve (?:Account|C/?D)[^\n$]{0,40}?)[ \t]*\n[ \t]*(" + MONEY_LINE + r")[ \t]*$", re.M)
_DOTS = r"[ .]*\s*(" + MONEY_LINE.replace(r"\(?-?\$?\s?-?", r"\(?-?\$?-?") + ")"


def _named_period(text: str) -> str:
    """"2025-11", "2025 03", "August 2024" as YYYY-MM."""
    m = re.search(r"(20\d\d)[-_ ](\d\d)\b", text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"\b(" + "|".join(MONTH_NAMES) + r")\s+(20\d\d)", text or "")
    if m:
        return f"{m.group(2)}-{MONTH_NAMES.index(m.group(1)) + 1:02d}"
    return ""


def _reconciliation(text: str, m: re.Match) -> ReconciliationSummary:
    block = text[m.start(): m.start() + 3000]

    def amount(label: str) -> int | None:
        found = re.search(label + _DOTS, block)
        return signed_cents(found.group(1)) if found else None

    def count(label: str) -> int | None:
        found = re.search(label + r"\s*\((\d+)\)", block)
        return int(found.group(1)) if found else None

    return ReconciliationSummary(
        account=m.group(1).strip(), start=long_date(m.group(2)), end=long_date(m.group(3)),
        beginning_cents=amount(r"Statement beginning balance"),
        payments_cleared=count(r"Checks and payments cleared"), payments_cleared_cents=amount(r"Checks and payments cleared\s*\(\d+\)"),
        deposits_cleared=count(r"Deposits and other credits cleared"),
        deposits_cleared_cents=amount(r"Deposits and other credits cleared\s*\(\d+\)"),
        ending_cents=amount(r"Statement ending balance"),
        payments_open_cents=amount(r"Checks and payments not reconciled\s*\(\d+\)"),
        deposits_open_cents=amount(r"Deposits and other credits not reconciled\s*\(\d+\)"),
        register_cents=amount(r"Register Balance as of [\d-]+"),
    )


def _bank_names(context: ModelContext) -> set[str]:
    words: set[str] = set()
    for account in spec_bank_accounts(context):
        words |= {w.casefold() for w in re.findall(r"[A-Za-z]{3,}", account.bank or "")}
    return words


class TreasurerReportModel(DocumentModel):
    kind = DocumentKind.TREASURER_REPORT
    name = "payhoa-treasurers-report"
    required = ("period", "generated", "total_assets_cents", "total_liabilities_equity_cents", "reconciliations")

    def parse(self, text: str, context: ModelContext) -> TreasurerReport | None:
        text = text or ""
        title = _TITLE.search(text[:600])
        if not title or "Balance Sheet" not in text:
            return None
        from jason.tasks.reserves import _ACCOUNT_LINE

        r = TreasurerReport(title=" ".join(title.group(0).split()))
        r.title_period = _named_period(title.group(1) or "")
        # The index is the cover page: the list of reports sits after "Included Reports:" (2026) or before it (2024-2025).
        cover_end = text.find("\n\n", title.end())
        index = text[title.end(): cover_end if 0 < cover_end < 1500 else title.end() + 700]
        r.included = tuple(line.strip() for line in index.splitlines() if line.strip() and ":" not in line.strip()[-1:]
                           and re.match(r"(Bank Reconciliation|General Ledger|Profit vs Loss|Budget|Aging|Balance Sheet|Delinquent|Check Register)",
                                        line.strip()))
        sheet = re.search(r"\nBalance Sheet\s*\n\s*As of ([A-Z][a-z]+\.? \d{1,2}, \d{4})", text)
        start = sheet.end() if sheet else 0
        if sheet:
            r.balance_sheet_date = long_date(sheet.group(1))
        else:
            dated = re.search(r"Balance Sheet as of:? (\d\d/\d\d/\d{4})", text[:1500])
            r.balance_sheet_date = long_date(dated.group(1)) if dated else None
        stop = text.find("Total Liabilities and Equity", start)
        body = text[start: stop + 80] if stop > 0 else text[start: start + 4000]
        banks = re.search(r"Bank Accounts\s*\n(.*?)\n[ \t]*Total Bank Accounts", body, re.S)
        if banks:
            r.bank_accounts = tuple(AccountBalance(" ".join(m.group(1).split()), signed_cents(m.group(2)) or 0) for m in
                                    re.finditer(r"^[ \t]*([^\n$]*[A-Za-z][^\n$]*?)[ \t]*\n[ \t]*(" + MONEY_LINE + r")[ \t]*$", banks.group(1), re.M))
        r.total_bank_cents = line_amount(r"Total Bank Accounts", body)
        r.total_assets_cents = line_amount(r"Total Assets", body)
        r.total_liabilities_cents = line_amount(r"Total Liabilities", body)
        r.total_equity_cents = line_amount(r"Total Equity", body)
        r.total_liabilities_equity_cents = line_amount(r"Total Liabilities and Equity", body)
        head = text[start: stop if stop > 0 else start + 6000]
        r.reserve_accounts = tuple(AccountBalance(" ".join(m.group(1).split()), int(m.group(2).replace(",", "").replace(".", "")))
                                   for m in _ACCOUNT_LINE.finditer(head))
        if not r.reserve_accounts:
            # The first PayHOA packet (as of February 1, 2024) carries the prior manager's accounts as other assets.
            r.reserve_accounts = tuple(AccountBalance(" ".join(m.group(1).split()), signed_cents(m.group(2)) or 0)
                                       for m in _OLD_RESERVE.finditer(head))
        r.reserve_cents = sum(a.cents for a in r.reserve_accounts) if r.reserve_accounts else None
        generated = re.search(r"Generated (\d\d-\d\d-\d{4})", text)
        r.generated = long_date(generated.group(1)) if generated else None
        ledger = re.search(r"General Ledger:? ?(\d\d/\d\d/\d{4}) - (\d\d/\d\d/\d{4})", text[:1500])
        if ledger:
            r.ledger_start, r.ledger_end = long_date(ledger.group(1)), long_date(ledger.group(2))
        day = r.balance_sheet_date or r.ledger_end
        if day:
            # A balance sheet "as of February 01" is January's close (the 2024-01 packet).
            if day.day == 1 and r.ledger_end and r.ledger_end.month != day.month:
                day = r.ledger_end
            r.period = f"{day.year}-{day.month:02d}"
        aging = re.search(r"\nAging of Accounts\s*\n.*?\nTotals\s*\n[ \t]*(" + MONEY_LINE + ")", text, re.S)
        r.receivable_cents = signed_cents(aging.group(1)) if aging else None
        pl = re.search(r"\nProfit vs Loss(?: Cash| Summary)?\s*\n\s*([A-Z][a-z]+\.? \d{1,2}, \d{4}) - ([A-Z][a-z]+\.? \d{1,2}, \d{4})", text)
        if pl:
            r.pl_start, r.pl_end = long_date(pl.group(1)), long_date(pl.group(2))
            end = text.find("Net Total", pl.end())
            section = text[pl.end(): end + 60 if end > 0 else pl.end() + 8000]
            r.income_cents = line_amount(r"Total Income", section)
            r.expenses_cents = line_amount(r"Total Expenses", section)
            r.net_cents = line_amount(r"Net Total", section)
        seen: dict[str, ReconciliationSummary] = {}
        for m in _RECON.finditer(text):
            rec = _reconciliation(text, m)
            seen.setdefault(rec.account, rec)
        r.reconciliations = tuple(seen.values())
        # The member version (shared with the agendas) keeps the receivables totals and leaves the units out of the
        # aging table; the board version lists each unit's balance by age (Civil Code 5215(a)(4), (a)(5)(B)).
        r.aging_units = len(aged_units(text))
        r.redacted = r.aging_units == 0
        r.named_redacted = bool(re.search(r"redact", context.name or "", re.I))
        return r

    def check(self, r: TreasurerReport, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.named_redacted and r.aging_units:
            found.append(Finding("redaction-incomplete", f"the file is named redacted, but its receivables aging still lists "
                                 f"{r.aging_units} units with their balances; keep it with the board's records, not the members'",
                                 Severity.PROBLEM, "CIV 5215(a)(4), (a)(5)(B)"))
        elif r.aging_units:
            found.append(Finding("member-receivables", f"the board version: the receivables aging lists {r.aging_units} units with "
                                 "their balances; members receive the version without them", Severity.INFO,
                                 "CIV 5215(a)(4), (a)(5)(B)"))
        filed = file_period(context)
        if r.period and filed and filed != r.period:
            found.append(Finding("copy-under-another-month", f"the file is filed as {filed}; its balance sheet reports {r.period}",
                                 Severity.PROBLEM))
        if r.period and r.title_period and r.title_period != r.period:
            found.append(Finding("title-period-differs", f"the packet is titled {r.title_period} but its balance sheet reports {r.period}",
                                 Severity.PROBLEM))
        if r.ledger_start and r.ledger_end and (r.ledger_start.year, r.ledger_start.month) != (r.ledger_end.year, r.ledger_end.month):
            found.append(Finding("ledger-not-one-month", f"the general ledger runs {r.ledger_start} to {r.ledger_end}, not one month",
                                 Severity.CHECK, "CIV 5500(f)"))
        if r.generated and r.period:
            year, month = (int(x) for x in r.period.split("-"))
            late = (r.generated - month_end(year, month)).days
            if late > 60:
                found.append(Finding("generated-later", f"this copy was generated {r.generated}, {late} days after the month it reports; "
                                     "the board may have seen an earlier run", Severity.CHECK))
        if r.bank_accounts and r.total_bank_cents is not None:
            listed = sum(a.cents for a in r.bank_accounts)
            if listed != r.total_bank_cents:
                found.append(Finding("bank-total-does-not-foot", f"the bank accounts add to {dollars(listed)}; the balance sheet's total "
                                     f"is {dollars(r.total_bank_cents)}", Severity.PROBLEM))
        if r.total_assets_cents is not None and r.total_liabilities_equity_cents is not None \
                and r.total_assets_cents != r.total_liabilities_equity_cents:
            found.append(Finding("balance-sheet-does-not-balance", f"total assets {dollars(r.total_assets_cents)} differ from liabilities "
                                 f"and equity {dollars(r.total_liabilities_equity_cents)}", Severity.PROBLEM))
        if None not in (r.income_cents, r.expenses_cents, r.net_cents) and r.income_cents - r.expenses_cents != r.net_cents:
            found.append(Finding("net-does-not-foot", f"income {dollars(r.income_cents)} less expenses {dollars(r.expenses_cents)} is not "
                                 f"the net total {dollars(r.net_cents)}", Severity.PROBLEM))
        for rec in r.reconciliations:
            parts = (rec.beginning_cents, rec.payments_cleared_cents, rec.deposits_cleared_cents, rec.ending_cents)
            if None not in parts:
                expected = rec.beginning_cents - rec.payments_cleared_cents + rec.deposits_cleared_cents
                if expected != rec.ending_cents:
                    found.append(Finding("reconciliation-does-not-foot", f"the {rec.account} reconciliation: beginning "
                                         f"{dollars(rec.beginning_cents)} less cleared payments plus cleared deposits is {dollars(expected)}, "
                                         f"not the statement ending balance {dollars(rec.ending_cents)}", Severity.PROBLEM,
                                         "CIV 5500(b)" if "reserve" in rec.account.lower() else "CIV 5500(a)"))
            if rec.end and r.period and f"{rec.end.year}-{rec.end.month:02d}" != r.period:
                found.append(Finding("reconciliation-other-month", f"the {rec.account} reconciliation covers {rec.start} to {rec.end}, not "
                                     f"{r.period}", Severity.CHECK))
        names = " ".join(rec.account.lower() for rec in r.reconciliations) + " " + " ".join(i.lower() for i in r.included)
        if "operating" not in names:
            found.append(Finding("no-operating-reconciliation", "the packet has no reconciliation of the operating account",
                                 Severity.CHECK, "CIV 5500(a)"))
        if "reserve" not in names:
            found.append(Finding("no-reserve-reconciliation", "the packet has no reconciliation of the reserve account",
                                 Severity.CHECK, "CIV 5500(b)"))
        index = " ".join(r.included).lower()
        for words, what, authority in ((("budget",), "budget against actual report", "CIV 5500(c)"),
                                       (("profit", "income"), "income and expense statement", "CIV 5500(e)"),
                                       (("general ledger",), "general ledger", "CIV 5500(f)"),
                                       (("aging", "delinquent"), "delinquent assessment receivable report", "CIV 5500(f)")):
            if r.included and not any(w in index for w in words):
                found.append(Finding("packet-lacks-" + what.split()[0].lower(), f"the packet's index lists no {what}", Severity.CHECK,
                                     authority))
        banks = _bank_names(context)
        for account in r.reserve_accounts:
            bank = re.search(r"\(([^)]+)\)", account.label)
            if banks and bank and not ({w.casefold() for w in re.findall(r"[A-Za-z]{3,}", bank.group(1))} & banks):
                found.append(Finding("reserve-at-unnamed-bank", f"'{account.label}' ({dollars(account.cents)}) holds reserve money at a bank the "
                                     "specification's bank accounts do not name", Severity.CHECK))
        found += self._ledger(r, context)
        return found

    @staticmethod
    def _ledger(r: TreasurerReport, context: ModelContext) -> list[Finding]:
        """Printed bank balances against PayHOA's balance sheet for the same month end, as the ledger stands today."""
        data = data_json(context, SHEETS)
        sheet = (data or {}).get("sheets", {}).get(r.period) if r.period else None
        if not sheet:
            return []
        printed = {a.label: a.cents for a in r.bank_accounts}
        changed = []
        for account in sheet.get("accounts", []):
            if account.get("section") != "Bank Accounts" or account.get("label") not in printed:
                continue
            if printed[account["label"]] != account.get("cents"):
                changed.append(f"{account['label']} printed {dollars(printed[account['label']])}, ledger now {dollars(account.get('cents'))}")
        if not changed:
            return []
        return [Finding("ledger-changed-since", f"PayHOA's balance sheet for {sheet.get('asOf', r.period)} no longer matches this copy: "
                        + "; ".join(changed) + "; the printed report is the record of what the board was told", Severity.CHECK)]


# The Helsing Group's monthly financial statements.

@dataclass(frozen=True)
class BudgetLine:
    """One row of the operating budget comparison: month and year-to-date actual and budget, and the annual budget."""

    label: str
    month_actual_cents: int | None = None
    month_budget_cents: int | None = None
    ytd_actual_cents: int | None = None
    ytd_budget_cents: int | None = None
    annual_budget_cents: int | None = None


@dataclass
class HelsingStatement:
    preparer: str = ""
    period_end: date | None = None
    period: str = ""
    sections: tuple[str, ...] = ()
    excerpt: bool = False                      # "Pages from ..." carries only some of the packet
    operating_cash_cents: int | None = None
    reserve_cash_cents: int | None = None      # the "Reserve" bank accounts, without the certificate of deposit
    certificate_cents: int | None = None
    total_assets: tuple[int, ...] = ()         # operating, reserve, total as printed
    reserve_receivable_cents: int | None = None   # "A/R Reserve Fund" on the reserve side
    due_to_reserve_cents: int | None = None       # "Due to Reserve" on the operating side
    total_liabilities: tuple[int, ...] = ()
    total_liabilities_equity: tuple[int, ...] = ()
    income: BudgetLine | None = None
    expenses: BudgetLine | None = None
    excess: BudgetLine | None = None
    reserve_contribution: BudgetLine | None = None
    notes: tuple[str, ...] = ()


_NUM = r"\(?-?[\d,]+\.\d\d\)?"
_SECTION_TITLES = ("GL Balance Sheet", "GL Income Statement", "Budget Comparison", "AP Aging|Accounts Payable Aging", "Check Register",
                   "Accounts Receivable Aging|AR Aging|Aging Report", "Prepaid", "GL Ledger|General Ledger", "Bank Reconciliation",
                   "Bank Statement|Bank Reconciliation and Statements")


def _numbers_after(text: str, label: str, count: int) -> tuple[int, ...]:
    """The first ``count`` amounts after a line starting with ``label`` (numbers may share a line)."""
    m = re.search(r"(?:^|\n)[ \t]*" + label + r"[^\n]*\n", text, re.I)
    if not m:
        return ()
    values = []
    for n in re.finditer(_NUM + r"|%", text[m.end(): m.end() + 400]):
        token = n.group(0)
        if token == "%":
            continue
        values.append(signed_cents(token) or 0)
        if len(values) == count:
            break
    return tuple(values)


def _row_numbers(text: str, label: str) -> list[int]:
    """The amounts on the lines after ``label`` up to the next line that carries letters."""
    m = re.search(r"(?:^|\n)[ \t]*" + label + r"[^\n]*\n", text, re.I)
    if not m:
        return []
    values = []
    for line in text[m.end():].splitlines():
        if re.search(r"[A-Za-z]", line):
            break
        values += [signed_cents(x) or 0 for x in re.findall(_NUM, line)]
    return values


def _budget_line(section: str, label: str, name: str) -> BudgetLine | None:
    m = re.search(r"(?:^|\n)[ \t]*(?:\d{5}\s+)?" + label + r"[^\n]*\n", section, re.I)
    if not m:
        return None
    values: list[int] = []
    for token in re.finditer(r"\(?-?[\d,]+\.\d\d\)?%?", section[m.end(): m.end() + 500]):
        if token.group(0).endswith("%"):
            continue
        values.append(signed_cents(token.group(0)) or 0)
        if len(values) == 7:
            break
    if len(values) < 7:
        return None
    # Actual, budget, $ variance for the month; actual, budget, $ variance year to date; annual budget.
    return BudgetLine(name, values[0], values[1], values[3], values[4], values[6])


class HelsingStatementModel(DocumentModel):
    kind = DocumentKind.FINANCIAL_STATEMENT
    name = "helsing-financial-statements"
    required = ("period_end", "total_assets", "total_liabilities_equity", "reserve_contribution")

    def parse(self, text: str, context: ModelContext) -> HelsingStatement | None:
        text = text or ""
        if not re.search(r"GL Balance Sheet|GL Income Statement|Monthly Financial Statements", text):
            return None
        s = HelsingStatement()
        s.preparer = "The Helsing Group" if re.search(r"Helsing", text, re.I) else ""
        s.excerpt = "Monthly Financial Statements" not in text[:400]
        s.sections = tuple(t.split("|")[0] for t in _SECTION_TITLES if re.search(r"(?:^|\n)[ \t]*(?:" + t + r")", text, re.I))
        sheet_at = text.find("GL Balance Sheet")
        dated = re.search(r"GL Balance Sheet[^\n]*\n\s*Transaction (\d{1,2}/\d{1,2}/\d{4})", text)
        s.period_end = long_date(dated.group(1)) if dated else None
        if s.period_end is None:
            ranged = re.search(r"Transaction \d{1,2}/\d{1,2}/\d{4} To (\d{1,2}/\d{1,2}/\d{4})", text)
            s.period_end = long_date(ranged.group(1)) if ranged else None
        if s.period_end is None:
            cover = re.search(r"Monthly Financial Statements\s*\n\s*(" + "|".join(MONTH_NAMES) + r") (20\d\d)", text)
            if cover:
                s.period_end = month_end(int(cover.group(2)), MONTH_NAMES.index(cover.group(1)) + 1)
        if s.period_end:
            s.period = f"{s.period_end.year}-{s.period_end.month:02d}"
        end = text.find("Total Liabilities & Equity", max(sheet_at, 0))
        sheet = text[max(sheet_at, 0): end + 200 if end > 0 else max(sheet_at, 0) + 6000]
        cash = _row_numbers(sheet, r"Total Cash")
        s.operating_cash_cents = cash[-1] if cash else None
        reserve = _row_numbers(sheet, r"Total Reserve")
        s.reserve_cash_cents = reserve[-1] if reserve else None
        cd = re.search(r"\n([^\n]*\bCD\b[^\n]*)\n((?:\s*" + _NUM + r"\s*\n)+)", sheet)
        if cd:
            values = [signed_cents(x) or 0 for x in re.findall(_NUM, cd.group(2))]
            s.certificate_cents = values[-1] if values else None
        s.total_assets = tuple(_row_numbers(sheet, r"Total Assets"))
        receivable = _row_numbers(sheet, r"A/R Reserve Fund")
        s.reserve_receivable_cents = receivable[-1] if receivable else None
        due = _row_numbers(sheet, r"Due to Reserve")
        s.due_to_reserve_cents = due[-1] if due else None
        s.total_liabilities = tuple(_row_numbers(sheet, r"Total Liability"))
        s.total_liabilities_equity = tuple(_row_numbers(sheet, r"Total Liabilities & Equity"))
        budget_at = text.find("Budget Comparison")
        if budget_at >= 0:
            reserve_side = text.find("Current Month Reserve", budget_at)
            section = text[budget_at: reserve_side if reserve_side > 0 else budget_at + 20000]
            # The operating side's grand total follows "Other Revenue"; its expense total is "TOTAL Expense".
            other = section.find("TOTAL Other Revenue")
            s.income = _budget_line(section[other:] if other >= 0 else section, r"TOTAL Income", "Total income")
            s.expenses = _budget_line(section, r"TOTAL Expense\b", "Total expense")
            s.excess = _budget_line(section, r"Excess Revenue / Expense", "Excess revenue over expense")
            s.reserve_contribution = _budget_line(section, r"Reserve Contributi", "Reserve contribution")
        flat = " ".join(text.split())
        s.notes = tuple(dict.fromkeys(m.group(0).strip() for m in re.finditer(
            r"[^.:]*\b(?:was|were|has|have)\s+not\s+(?:been\s+)?(?:made|transferred|deposited|funded|paid)\b[^.]*\.?", flat, re.I)
            if re.search(r"reserve", m.group(0), re.I)))
        return s

    def check(self, s: HelsingStatement, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        filed = file_period(context)
        if s.period and filed and filed != s.period:
            found.append(Finding("copy-under-another-month", f"the file is filed as {filed}; its balance sheet is as of {s.period_end}",
                                 Severity.PROBLEM))
        if s.total_assets and s.total_liabilities_equity and s.total_assets[-1] != s.total_liabilities_equity[-1]:
            found.append(Finding("balance-sheet-does-not-balance", f"total assets {dollars(s.total_assets[-1])} differ from liabilities and "
                                 f"equity {dollars(s.total_liabilities_equity[-1])}", Severity.PROBLEM))
        if s.due_to_reserve_cents:
            found.append(Finding("due-to-reserve", f"the operating fund owes the reserve fund {dollars(s.due_to_reserve_cents)} "
                                 "('Due to Reserve'): money set for reserves had not been moved to the reserve account. If it was borrowed "
                                 "from reserves, it must be restored within one year", Severity.PROBLEM, "CIV 5515(d)"))
            if s.reserve_receivable_cents is not None and s.reserve_receivable_cents != s.due_to_reserve_cents:
                found.append(Finding("interfund-mismatch", f"the reserve side's receivable ({dollars(s.reserve_receivable_cents)}) differs from "
                                     f"the operating side's 'Due to Reserve' ({dollars(s.due_to_reserve_cents)})", Severity.CHECK))
        rc = s.reserve_contribution
        if rc and rc.ytd_actual_cents is not None and rc.ytd_budget_cents is not None and rc.ytd_actual_cents < rc.ytd_budget_cents:
            found.append(Finding("reserve-contribution-short", f"the reserve contribution year to date is {dollars(rc.ytd_actual_cents)} against "
                                 f"a budget of {dollars(rc.ytd_budget_cents)}", Severity.PROBLEM))
        for note in s.notes:
            found.append(Finding("manager-note", f"the statements note: {note[:160]}", Severity.PROBLEM))
        if s.operating_cash_cents is not None and s.operating_cash_cents < 0:
            found.append(Finding("operating-cash-negative", f"operating cash is {dollars(s.operating_cash_cents)} at {s.period_end}",
                                 Severity.PROBLEM))
        if s.excess and s.income and s.expenses and None not in (s.income.ytd_actual_cents, s.expenses.ytd_actual_cents, s.excess.ytd_actual_cents):
            if s.income.ytd_actual_cents - s.expenses.ytd_actual_cents != s.excess.ytd_actual_cents:
                found.append(Finding("budget-comparison-does-not-foot", "income less expenses year to date is not the excess the budget "
                                     "comparison prints", Severity.CHECK))
        if s.excess and s.excess.ytd_actual_cents is not None and s.excess.ytd_actual_cents < 0:
            found.append(Finding("operating-deficit", f"the operating fund ran {dollars(s.excess.ytd_actual_cents)} year to date against a "
                                 f"budgeted {dollars(s.excess.ytd_budget_cents)}", Severity.INFO, "CIV 5500(c)"))
        if not s.excerpt:
            have = " ".join(s.sections).lower()
            for words, what, authority in ((("bank reconciliation",), "bank reconciliation", "CIV 5500(a), (b)"),
                                           (("budget comparison",), "budget comparison", "CIV 5500(c)"),
                                           (("bank statement", "reconciliation and statements"), "bank statements", "CIV 5500(d)"),
                                           (("gl income statement",), "income statement", "CIV 5500(e)"),
                                           (("check register",), "check register", "CIV 5500(f)"),
                                           (("gl ledger",), "general ledger", "CIV 5500(f)"),
                                           (("accounts receivable aging",), "receivable aging", "CIV 5500(f)")):
                if not any(w in have for w in words):
                    found.append(Finding("packet-lacks-" + what.split()[0], f"the packet has no {what}", Severity.CHECK, authority))
        return found


register(TreasurerReportModel())
register(HelsingStatementModel())

__all__ = ["TreasurerReport", "ReconciliationSummary", "AccountBalance", "TreasurerReportModel", "HelsingStatement", "BudgetLine",
           "HelsingStatementModel"]
