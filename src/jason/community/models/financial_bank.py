"""The association's bank statements (JPMorgan Chase business checking).

The board reviews each month the latest statements from the banks that hold the operating and reserve accounts, and a
current reconciliation of each (Civil Code 5500(a), (b), (d)). A statement says what the bank holds: the period, the
account (its last four digits; the statement file names carry them, "20250829-statements-5286-.pdf"), the beginning and
ending balance, and the checking summary (deposits, checks paid, card and electronic withdrawals, fees), each with its
count. The fee page computes the period's service charges and debits them early in the next period ("Total Service
Charge (Will be assessed on 12/3/25)"), so a charge shows twice: computed on one statement, debited on the next. Reserve money leaves only with two signatures and for reserve purposes (5510), and a transfer above the lesser of
$10,000 or 5 percent of budgeted income needs the board's prior written approval (5502(a)(2)).

``ChaseStatementModel`` reads Chase's layout: "Beginning Balance / $x / Ending Balance / n / $y", then the product name
("Chase Business Complete Checking", "Chase Performance Business Checking") and the summary as label, count, amount.
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
    long_date,
    signed_cents,
    spec_bank_accounts,
)
from jason.community.symbols import DocumentKind

RECONCILIATIONS = "payhoa/reconciliations.json"


@dataclass(frozen=True)
class SummaryLine:
    """One line of the checking summary: "Electronic Withdrawals / 34 / -26,127.04"."""

    label: str
    count: int
    cents: int          # signed as printed: deposits positive, withdrawals negative


@dataclass
class BankStatement:
    bank: str = ""
    product: str = ""                 # "Chase Business Complete Checking"
    account_last4: str = ""           # from the statement's own account line
    name_last4: str = ""              # from the file name, when it carries one
    period_start: date | None = None
    period_end: date | None = None
    beginning_cents: int | None = None
    ending_cents: int | None = None
    transactions: int | None = None   # "instances" the summary counts
    summary: tuple[SummaryLine, ...] = field(default_factory=tuple)
    deposits_cents: int | None = None
    withdrawals_cents: int | None = None   # the sum of the withdrawal lines (negative)
    checks_paid_cents: int | None = None
    checks_paid: int | None = None
    fees_cents: int | None = None
    interest_cents: int | None = None
    service_fee_waived: bool = False
    service_charge_cents: int | None = None   # "Total Service Charge(s)" on the fee page
    service_charge_assessed: date | None = None   # "(Will be assessed on 12/3/25)": the charge posts on the next statement
    service_charges: tuple[str, ...] = ()     # the fee page's charged services ("Stop Payment - Online")
    purpose: str = ""                 # "operating" or "reserve", from the specification


_PERIOD = re.compile(r"([A-Z][a-z]+ \d{1,2}, \d{4})\s+through\s+([A-Z][a-z]+ \d{1,2}, \d{4})")
_LABELS = ("Deposits and Additions", "Checks Paid", "ATM & Debit Card Withdrawals", "Electronic Withdrawals", "Other Withdrawals",
           "Fees", "Service Fees", "Interest Paid", "Card Purchases")
_SUMMARY_ROW = re.compile(r"^[ \t]*(" + "|".join(re.escape(x) for x in _LABELS) + r")[ \t]*\n[ \t]*(\d+)[ \t]*\n[ \t]*(-?\$?[\d,]+\.\d\d)[ \t]*$", re.M)
_PRODUCT = re.compile(r"^[ \t]*(Chase [A-Za-z ]*?(?:Checking|Savings)[A-Za-z ]*?)[ \t]*\n(?=[ \t]*(?:" + "|".join(re.escape(x) for x in _LABELS) + r")[ \t]*\n\d)", re.M)
_NAME_LAST4 = re.compile(r"statements?-(\d{4})\b", re.I)


class ChaseStatementModel(DocumentModel):
    kind = DocumentKind.BANK_STATEMENT
    name = "chase-statement"
    required = ("account_last4", "period_start", "period_end", "beginning_cents", "ending_cents", "deposits_cents")

    def parse(self, text: str, context: ModelContext) -> BankStatement | None:
        text = text or ""
        if not re.search(r"JPMorgan Chase Bank|Chase\.com", text, re.I) or "Beginning Balance" not in text:
            return None
        s = BankStatement(bank="JPMorgan Chase")
        head = text[:400]
        number = re.search(r"^\s*0*\d{6,}?(\d{4})\s*$", head, re.M)
        s.account_last4 = number.group(1) if number else ""
        name = _NAME_LAST4.search(context.name or "")
        s.name_last4 = name.group(1) if name else ""
        period = _PERIOD.search(text)
        if period:
            s.period_start, s.period_end = long_date(period.group(1)), long_date(period.group(2))
        begin = re.search(r"Beginning Balance\s*\n\s*(" + MONEY_LINE + ")", text)
        s.beginning_cents = signed_cents(begin.group(1)) if begin else None
        end = re.search(r"Ending Balance\s*\n\s*(?:(\d+)\s*\n\s*)?(" + MONEY_LINE + ")", text)
        if end:
            s.transactions = int(end.group(1)) if end.group(1) else None
            s.ending_cents = signed_cents(end.group(2))
        product = _PRODUCT.search(text)
        rows: list[SummaryLine] = []
        if product:
            s.product = product.group(1).strip()
            pos = product.end()
            while True:
                m = _SUMMARY_ROW.match(text, pos)
                if not m:
                    break
                rows.append(SummaryLine(m.group(1), int(m.group(2)), signed_cents(m.group(3)) or 0))
                pos = m.end() + 1
        s.summary = tuple(rows)
        by = {r.label: r for r in rows}
        if "Deposits and Additions" in by:
            s.deposits_cents = by["Deposits and Additions"].cents
        elif rows or product:
            s.deposits_cents = 0
        else:
            total = re.search(r"Total Deposits and Additions\s*\n\s*(" + MONEY_LINE + ")", text)
            s.deposits_cents = signed_cents(total.group(1)) if total else None
        out = [r for r in rows if r.cents < 0]
        s.withdrawals_cents = sum(r.cents for r in out) if rows else None
        if "Checks Paid" in by:
            s.checks_paid_cents, s.checks_paid = by["Checks Paid"].cents, by["Checks Paid"].count
        fees = [r for r in rows if r.label in ("Fees", "Service Fees")]
        s.fees_cents = sum(r.cents for r in fees) if fees else (0 if rows else None)
        if "Interest Paid" in by:
            s.interest_cents = by["Interest Paid"].cents
        s.service_fee_waived = bool(re.search(r"waived the \$[\d.]+ Monthly Service Fee|service fee of \$[\d.,]+ was waived|"
                                              r"Waived Monthly Service Fee", text, re.I))
        charge = re.search(r"Total Service Charges?[ \t]*(?:\(Will be assessed on (\d{1,2}/\d{1,2}/\d{2,4})\))?[ \t]*\n\s*(" + MONEY_LINE + ")", text)
        if charge:
            s.service_charge_cents = signed_cents(charge.group(2))
            s.service_charge_assessed = long_date(charge.group(1)) if charge.group(1) else None
        if s.service_charge_cents:
            # The fee page's rows: service, volume, allowed, charged, price per unit, total; a charged row names the fee.
            s.service_charges = tuple(dict.fromkeys(m.group(1).strip() for m in re.finditer(
                r"^[ \t]*([A-Z][A-Za-z &/-]+?)[ \t]*\n[ \t]*\d+[ \t]*\n[ \t]*\d+[ \t]*\n[ \t]*[1-9]\d*[ \t]*\n[ \t]*\$[\d,.]+[ \t]*\n"
                r"[ \t]*\$(?!0\.00\b)[\d,]+\.\d\d[ \t]*$", text, re.M)))
        suffix = s.account_last4 or s.name_last4
        for account in spec_bank_accounts(context):
            if account.suffix == suffix:
                s.purpose = account.purpose.value
        return s

    def check(self, s: BankStatement, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        known = {a.suffix: a for a in spec_bank_accounts(context)}
        if s.account_last4 and s.name_last4 and s.account_last4 != s.name_last4:
            found.append(Finding("name-account-mismatch", f"the file name says account ...{s.name_last4}; the statement is for "
                                 f"...{s.account_last4}", Severity.PROBLEM))
        suffix = s.account_last4 or s.name_last4
        if known and suffix and suffix not in known:
            found.append(Finding("unknown-account", f"account ...{suffix} is not one of the association's accounts in the "
                                 f"specification ({', '.join('...' + k for k in known)})", Severity.CHECK))
        m = re.search(r"(20\d\d)(\d\d)(\d\d)-statements", context.name or "")
        if m and s.period_end:
            named = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if named != s.period_end:
                found.append(Finding("name-date-mismatch", f"the file name dates the statement {named}; its period ends {s.period_end}",
                                     Severity.CHECK))
        if s.beginning_cents is not None and s.ending_cents is not None and s.summary:
            moved = sum(r.cents for r in s.summary)
            if s.beginning_cents + moved != s.ending_cents:
                found.append(Finding("balance-does-not-foot", f"beginning {dollars(s.beginning_cents)} plus the summary lines "
                                     f"({dollars(moved)}) is {dollars(s.beginning_cents + moved)}, not the ending balance "
                                     f"{dollars(s.ending_cents)}", Severity.PROBLEM))
        what = f" ({', '.join(s.service_charges)})" if s.service_charges else ""
        pending = bool(s.service_charge_cents and s.service_charge_assessed)
        if s.fees_cents:
            found.append(Finding("service-fee", f"the bank debited {dollars(abs(s.fees_cents))} in fees this period", Severity.CHECK))
        elif s.service_charge_cents and not pending:
            found.append(Finding("service-fee", f"the bank charged {dollars(abs(s.service_charge_cents))} in fees this period{what}",
                                 Severity.CHECK))
        if pending:
            # Chase computes a period's service charges on its fee page and debits them early the next period, so the next
            # statement's "Fees" line is this same charge.
            found.append(Finding("service-charge-next-period", f"the fee page computes {dollars(abs(s.service_charge_cents))} in service "
                                 f"charges{what}, assessed {s.service_charge_assessed}; the next statement debits it",
                                 Severity.INFO))
        if s.ending_cents is not None and s.ending_cents < 0:
            found.append(Finding("overdrawn", f"the account ended the period overdrawn ({dollars(s.ending_cents)})", Severity.PROBLEM))
        out = -sum(r.cents for r in s.summary if r.cents < 0 and r.label not in ("Fees", "Service Fees"))
        if s.purpose == "reserve" and out > 0:
            over = " (over $10,000)" if out > 1_000_000 else ""
            found.append(Finding("reserve-withdrawal", f"{dollars(out)} left the reserve account this period{over}; each withdrawal "
                                 "needs two signers and a reserve purpose, and a transfer over the lesser of $10,000 or 5% of budgeted "
                                 "income needs the board's prior written approval", Severity.CHECK, "CIV 5510(a), (b); CIV 5502(a)(2)"))
        found += self._reconciliation(s, context)
        return found

    @staticmethod
    def _reconciliation(s: BankStatement, context: ModelContext) -> list[Finding]:
        data = data_json(context, RECONCILIATIONS)
        suffix = s.account_last4 or s.name_last4
        if not data or not suffix or not s.period_end:
            return []
        rows = [r for r in data.get("reconciliations", []) if str(r.get("last4")) == suffix]
        if not rows:
            return []
        authority = "CIV 5500(b)" if s.purpose == "reserve" else "CIV 5500(a)"
        same = [r for r in rows if r.get("end") == s.period_end.isoformat()]
        if not same:
            first = min(r.get("end") or "" for r in rows)
            if s.period_end.isoformat() < first:
                return []   # before PayHOA's first reconciliation of this account
            return [Finding("no-reconciliation", f"PayHOA holds no reconciliation of ...{suffix} for the period ending {s.period_end}",
                            Severity.CHECK, authority)]
        r = same[0]
        found = []
        if s.ending_cents is not None and r.get("endingBalance") is not None and int(r["endingBalance"]) != s.ending_cents:
            found.append(Finding("reconciliation-ending-differs", f"the reconciliation for {s.period_end} uses an ending balance of "
                                 f"{dollars(int(r['endingBalance']))}; the statement says {dollars(s.ending_cents)}", Severity.PROBLEM, authority))
        if s.beginning_cents is not None and r.get("startingBalance") is not None and int(r["startingBalance"]) != s.beginning_cents:
            found.append(Finding("reconciliation-beginning-differs", f"the reconciliation for {s.period_end} starts at "
                                 f"{dollars(int(r['startingBalance']))}; the statement's beginning balance is {dollars(s.beginning_cents)}",
                                 Severity.PROBLEM, authority))
        if not found:
            found.append(Finding("reconciled", f"PayHOA's reconciliation for {s.period_end} matches the statement's balances",
                                 Severity.INFO, authority))
        return found


register(ChaseStatementModel())

__all__ = ["BankStatement", "SummaryLine", "ChaseStatementModel"]
