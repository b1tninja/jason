"""Money in and out of the reserve accounts, read from PayHOA's general ledger, and what Civil Code 5510 and 5515 ask of it.

Reserve funds are spent only on the major components they were set aside for (5510(b)). The board may lend them to the
operating fund for a short-term cash need (5515): after a noticed agenda item giving the reasons, the repayment options,
and whether a special assessment may be considered; with a written finding in the minutes of why and when and how it
will be repaid; and with the money restored within one year of the transfer, unless the board, after the same notice,
finds a delay is in the association's best interest.

``movements`` reads the reserve accounts' ledger rows into ``ReserveMovement`` records. ``explain`` sorts them:

- a contribution of the year's usual amount is ``REGULAR``; one whose memo names an earlier month is ``CATCH_UP``;
  one that restores a payment the reserve made for operating (a fee, a purchase) is ``RESTORES_PAYMENT``; any other
  money from operating is ``UNSCHEDULED``, which is where a loan's repayment shows;
- a withdrawal to operating that repays an operating expense of the same amount is ``REIMBURSEMENT`` (5510(b) spending,
  when the expense was a reserve component); one that forwards a deposit made to the reserve by mistake is
  ``FORWARDED_DEPOSIT``; any other is ``BORROWING`` (5515);
- a move to a certificate of deposit is ``INVESTMENT``.

``repayments`` sets the unscheduled contributions against the borrowings. A run of them that sums exactly to one
borrowing within its year is its repayment; the rest are applied oldest borrowing first. A match by amount is a lead
the board confirms from its own resolution, not a finding.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any, Iterable

from jason.community.ledger import BANK, EXPENSE, Entry


class MovementKind(Enum):
    CONTRIBUTION = "contribution"   # from operating into the reserve
    WITHDRAWAL = "withdrawal"       # from the reserve to operating
    INVESTMENT = "investment"       # from the reserve to a certificate of deposit
    PAYMENT = "payment"             # paid from the reserve to someone else
    DEPOSIT = "deposit"             # any other money in (a wire, a deposit, interest)


class Purpose(Enum):
    REGULAR = "regular contribution"
    CATCH_UP = "catch-up contribution"
    RESTORES_PAYMENT = "restores a payment the reserve made for operating"
    UNSCHEDULED = "unscheduled contribution"
    REIMBURSEMENT = "reimburses an operating expense (5510(b) if a reserve component)"
    FORWARDED_DEPOSIT = "forwards a deposit made to the reserve"
    BORROWING = "borrowing (5515)"
    INVESTMENT = "investment"
    OTHER = ""


@dataclass
class ReserveMovement:
    day: date
    account: str
    kind: MovementKind
    cents: int
    number: str = ""
    memo: str = ""
    category: str = ""
    description: str = ""
    purpose: Purpose = Purpose.OTHER
    matched: dict[str, Any] | None = None


@dataclass
class Borrowing:
    movement: ReserveMovement
    deadline: date
    repaid: list[ReserveMovement] = field(default_factory=list)
    exact: bool = False

    @property
    def repaid_cents(self) -> int:
        return sum(m.cents for m in self.repaid)

    @property
    def outstanding_cents(self) -> int:
        return max(self.movement.cents - self.repaid_cents, 0)

    @property
    def repaid_on(self) -> date | None:
        total = 0
        for m in self.repaid:
            total += m.cents
            if total >= self.movement.cents:
                return m.day
        return None

    @property
    def on_time(self) -> bool | None:
        day = self.repaid_on
        return None if day is None else day <= self.deadline


_TRANSFER = re.compile(r"Online Transfer (to|from) (?:CHK|SAV)\s*\.*(\d{4})", re.I)
_CD = re.compile(r"Transfer to CDS?\b", re.I)
_NUMBER = re.compile(r"transaction#:\s*(\d+)")
_MONTH = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b", re.I)
_MONTHS = {m: n for n, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august", "september",
                                        "october", "november", "december"), start=1)}


def movements(items: Iterable[Entry], reserve: dict[str, str], operating: set[str]) -> list[ReserveMovement]:
    """Every row on a reserve account, as a movement. ``reserve`` maps each reserve account's ledger label to its last
    four digits; ``operating`` holds the operating accounts' last four. A move between two reserve accounts is kept
    once, from the account it left."""
    found = []
    for e in items:
        if e.type != BANK or e.starting or e.account not in reserve:
            continue
        own = reserve[e.account]
        inflow = e.debit > 0
        cents = e.debit if inflow else e.credit
        if not cents:
            continue
        transfer = _TRANSFER.search(e.description)
        other = transfer.group(2) if transfer else ""
        if _CD.search(e.description):
            if inflow:
                continue  # the certificate's side of a move already counted from the reserve account
            kind = MovementKind.INVESTMENT
        elif transfer and other != own and other in reserve.values():
            if inflow:
                continue
            kind = MovementKind.INVESTMENT
        elif transfer:
            # "Online Transfer from CHK ...6177" on account 6177 itself names no counterparty; the side says which way.
            kind = MovementKind.CONTRIBUTION if inflow else MovementKind.WITHDRAWAL
        else:
            kind = MovementKind.DEPOSIT if inflow else MovementKind.PAYMENT
        number = _NUMBER.search(e.description)
        found.append(ReserveMovement(e.day, e.account, kind, cents, number.group(1) if number else "", e.memo, e.category,
                                     e.description))
    return sorted(found, key=lambda m: (m.day, m.kind.value, m.cents))


def usual_contribution(moves: list[ReserveMovement]) -> dict[int, int]:
    """Each year's usual monthly contribution: the amount transferred most often."""
    by_year: dict[int, Counter] = {}
    for m in moves:
        if m.kind is MovementKind.CONTRIBUTION:
            by_year.setdefault(m.day.year, Counter())[m.cents] += 1
    return {year: counts.most_common(1)[0][0] for year, counts in by_year.items()}


def _names_earlier_month(m: ReserveMovement) -> bool:
    found = _MONTH.search(m.memo)
    if not found:
        return False
    named = (int(found.group(2)), _MONTHS[found.group(1).lower()])
    return named < (m.day.year, m.day.month)


def explain(moves: list[ReserveMovement], items: Iterable[Entry], operating_labels: set[str], *,
            reimburse_days: int = 60, forward_days: int = 10, restore_days: int = 45) -> list[ReserveMovement]:
    """Set each movement's ``purpose`` (and ``matched``, the row that explains it). Each explaining row is used once."""
    items = list(items)
    usual = usual_contribution(moves)
    expenses = [e for e in items if not e.starting and ((e.type == EXPENSE and e.debit) or (e.type == BANK and e.account in operating_labels and e.credit))]
    used: set[int] = set()

    def find(rows, cents: int, before: date, days: int, amount) -> Any:
        for row in rows:
            if id(row) in used or amount(row) != cents:
                continue
            if before - timedelta(days=days) <= row.day <= before:
                used.add(id(row))
                return row
        return None

    deposits = [m for m in moves if m.kind is MovementKind.DEPOSIT and not m.description.lower().startswith("interest")]
    payments = [m for m in moves if m.kind is MovementKind.PAYMENT]
    for m in moves:
        if m.kind is MovementKind.INVESTMENT:
            m.purpose = Purpose.INVESTMENT
        elif m.kind is MovementKind.WITHDRAWAL:
            forwarded = find(deposits, m.cents, m.day, forward_days, lambda d: d.cents)
            if forwarded:
                m.purpose, m.matched = Purpose.FORWARDED_DEPOSIT, {"day": forwarded.day.isoformat(), "description": forwarded.description}
                continue
            expense = find(expenses, m.cents, m.day, reimburse_days, lambda e: e.debit if e.type == EXPENSE else e.credit)
            if expense:
                m.purpose = Purpose.REIMBURSEMENT
                m.matched = {"day": expense.day.isoformat(), "description": expense.description, "category": expense.category}
            else:
                m.purpose = Purpose.BORROWING
        elif m.kind is MovementKind.CONTRIBUTION:
            # January's transfer often still carries last year's amount.
            if m.cents in (usual.get(m.day.year), usual.get(m.day.year - 1)):
                m.purpose = Purpose.CATCH_UP if _names_earlier_month(m) else Purpose.REGULAR
            elif _names_earlier_month(m):
                m.purpose = Purpose.CATCH_UP
            else:
                restored = find(payments, m.cents, m.day, restore_days, lambda p: p.cents)
                if restored:
                    m.purpose = Purpose.RESTORES_PAYMENT
                    m.matched = {"day": restored.day.isoformat(), "description": restored.description}
                else:
                    m.purpose = Purpose.UNSCHEDULED
    return moves


def _exact_run(pool: list[ReserveMovement], cents: int) -> list[ReserveMovement] | None:
    """The shortest prefix of ``pool`` (oldest first) that sums to exactly ``cents``."""
    total = 0
    for n, m in enumerate(pool):
        total += m.cents
        if total == cents:
            return pool[: n + 1]
        if total > cents:
            return None
    return None


def repayments(moves: list[ReserveMovement]) -> list[Borrowing]:
    """Each borrowing with the unscheduled contributions that repay it. Newest borrowing first, a run of unscheduled
    contributions after it that sums exactly to it within its year is its repayment; what is left is applied to the
    borrowings oldest first."""
    loans = [Borrowing(m, m.day.replace(year=m.day.year + 1) if not (m.day.month == 2 and m.day.day == 29) else date(m.day.year + 1, 3, 1))
             for m in moves if m.purpose is Purpose.BORROWING]
    pool = [m for m in moves if m.purpose is Purpose.UNSCHEDULED]
    for loan in sorted(loans, key=lambda b: b.movement.day, reverse=True):
        after = [m for m in pool if loan.movement.day < m.day <= loan.deadline]
        run = _exact_run(after, loan.movement.cents)
        if run:
            loan.repaid, loan.exact = run, True
            pool = [m for m in pool if m not in run]
    for loan in sorted(loans, key=lambda b: b.movement.day):
        if loan.exact:
            continue
        for m in [m for m in pool if m.day > loan.movement.day]:
            if loan.outstanding_cents <= 0:
                break
            loan.repaid.append(m)
            pool.remove(m)
    return loans


def budget_months(tree: dict[str, Any], name: str) -> dict[tuple[int, int], int]:
    """One budget line's own amount per (year, month) from PayHOA's budget tree (``list_budgets``); its children's
    amounts are theirs, not the line's."""
    def find(rows):
        for row in rows or []:
            if (row.get("name") or row.get("label")) == name:
                return row
            found = find(row.get("children"))
            if found:
                return found
        return None

    row = find(tree.get("expense")) or find(tree.get("income"))
    if not row:
        return {}
    return {(int(i["year"]), int(i["month"])): int(i.get("amount") or 0) for i in row.get("budgetItems") or []}


def month_for(m: ReserveMovement) -> tuple[int, int]:
    """The month a contribution pays: the one its memo names, else the month it was made."""
    found = _MONTH.search(m.memo)
    if found:
        return int(found.group(2)), _MONTHS[found.group(1).lower()]
    return m.day.year, m.day.month


def schedule(moves: list[ReserveMovement], contribution: dict[tuple[int, int], int],
             repayment: dict[tuple[int, int], int], *, through: tuple[int, int]) -> list[dict[str, Any]]:
    """Each budgeted month through ``through``: the contribution and repayment budgeted, the transfers that paid them,
    and when. A regular or catch-up contribution pays the month its memo names, else the month it was made; a second
    one in a month already paid goes to the earliest unpaid month before it (``inferred``). Unscheduled contributions
    pay the repayment budgeted for the month they were made."""
    months = sorted(k for k in set(contribution) | set(repayment) if k <= through and (contribution.get(k) or repayment.get(k)))
    rows = {k: {"month": f"{k[0]}-{k[1]:02d}", "contributionBudgetCents": contribution.get(k, 0), "contributions": [],
                "repaymentBudgetCents": repayment.get(k, 0), "repayments": []} for k in months}
    for m in moves:
        if m.purpose in (Purpose.REGULAR, Purpose.CATCH_UP):
            key, inferred = month_for(m), False
            if key in rows and rows[key]["contributions"] and not _MONTH.search(m.memo):
                earlier = [k for k in months if k < key and rows[k]["contributionBudgetCents"] and not rows[k]["contributions"]]
                if earlier:
                    key, inferred = earlier[0], True
            if key in rows:
                rows[key]["contributions"].append({"day": m.day.isoformat(), "cents": m.cents, "memo": m.memo, "inferred": inferred})
        elif m.purpose is Purpose.UNSCHEDULED:
            key = (m.day.year, m.day.month)
            if key in rows:
                rows[key]["repayments"].append({"day": m.day.isoformat(), "cents": m.cents, "memo": m.memo})
    out = []
    for k in months:
        row = rows[k]
        row["contributionPaidCents"] = sum(c["cents"] for c in row["contributions"])
        row["repaymentPaidCents"] = sum(c["cents"] for c in row["repayments"])
        end = date(k[0] + (k[1] == 12), k[1] % 12 + 1, 1) - timedelta(days=1)
        paid = [date.fromisoformat(c["day"]) for c in row["contributions"]]
        row["daysLate"] = max((d - end).days for d in paid) if paid and max(paid) > end else 0
        out.append(row)
    return out


__all__ = ["MovementKind", "Purpose", "ReserveMovement", "Borrowing", "movements", "usual_contribution", "explain", "repayments",
           "budget_months", "month_for", "schedule"]
