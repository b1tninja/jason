"""Reports computed from PayHOA's general ledger rows: profit and loss, category months, vendors, cash flow, balances, queries.

PayHOA's general ledger groups every entry by type: the bank accounts ("Assets"), each unit's
receivable and prepayment accounts, and the income and expense categories. A row has the date,
description, category, memo, vendor, debit, credit, and running balance, in integer cents.

An expense category row's debit is spending and its credit a refund; an income category row's
credit is income and its debit a reversal. A bank row's debit is money in and its credit money
out. Every function here is a pure fold over those rows, so a report PayHOA renders on its own
(the Profit vs Loss Summary, the check register) can be rebuilt, and checked, from the ledger.

Unit accounts carry owners' names and balances. ``query`` leaves them out unless asked.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

BANK = "Assets"
INCOME = "Income Categories"
EXPENSE = "Expense Categories"
OWNER_TYPES = ("Accounts Receivable", "Accounts Receivable - Prepaids")


@dataclass(frozen=True)
class Entry:
    type: str
    account: str
    day: date
    description: str
    category: str
    memo: str
    vendor: str
    debit: int
    credit: int
    balance: int
    starting: bool = False

    @property
    def net(self) -> int:
        """The entry's effect in its account's natural direction: income and money in positive, spending positive for expenses."""
        if self.type == EXPENSE:
            return self.debit - self.credit
        if self.type == INCOME:
            return self.credit - self.debit
        return self.debit - self.credit


def entries(rows: Iterable[dict[str, Any]]) -> list[Entry]:
    """Ledger rows (``payhoa.reports.ledger_rows`` shape, or the ledger store's) as entries, oldest first."""
    found = []
    for row in rows:
        day = row.get("date") or row.get("day")
        if not day:
            continue
        found.append(Entry(str(row.get("type") or ""), str(row.get("label") or row.get("account") or ""), date.fromisoformat(str(day)[:10]),
                           str(row.get("description") or ""), str(row.get("category") or ""), str(row.get("memo") or ""),
                           str(row.get("vendor") or ""), int(row.get("debit") or 0), int(row.get("credit") or 0),
                           int(row.get("balance") or 0), bool(row.get("starting"))))
    return sorted(found, key=lambda e: (e.day, e.type, e.account))


def _within(entry: Entry, start: date | None, end: date | None) -> bool:
    return (start is None or entry.day >= start) and (end is None or entry.day <= end)


def profit_and_loss(items: list[Entry], start: date | None = None, end: date | None = None) -> dict[str, Any]:
    """Income and expense by category over a period, and the net, in cents."""
    income: dict[str, int] = defaultdict(int)
    expense: dict[str, int] = defaultdict(int)
    for e in items:
        if e.starting or not _within(e, start, end):
            continue
        if e.type == INCOME:
            income[e.account] += e.net
        elif e.type == EXPENSE:
            expense[e.account] += e.net
    total_in, total_out = sum(income.values()), sum(expense.values())
    return {"start": start.isoformat() if start else None, "end": end.isoformat() if end else None,
            "income": dict(sorted(income.items(), key=lambda kv: -kv[1])), "expense": dict(sorted(expense.items(), key=lambda kv: -kv[1])),
            "incomeCents": total_in, "expenseCents": total_out, "netCents": total_in - total_out}


def by_month(items: list[Entry], kind: str = EXPENSE, start: date | None = None, end: date | None = None) -> dict[str, dict[str, int]]:
    """Each income or expense category's total per month: {category: {YYYY-MM: cents}}."""
    found: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for e in items:
        if e.type == kind and not e.starting and _within(e, start, end):
            found[e.account][f"{e.day.year}-{e.day.month:02d}"] += e.net
    return {k: dict(sorted(v.items())) for k, v in sorted(found.items())}


def payee_of(entry: Entry) -> str:
    """The vendor PayHOA recorded, else the bank line's company name ("ORIG CO NAME:SMUD ..."), else the description."""
    if entry.vendor:
        return entry.vendor
    m = re.search(r"ORIG CO NAME:([^:]+?)\s+ORIG ID", entry.description)
    if m:
        return m.group(1).strip().title()
    billpay = re.match(r"(?:Credit Return: )?Online Payment \d+ To (.+?)(?:\s+\d{2}/\d{2})?$", entry.description.strip(), re.I)
    if billpay:
        return billpay.group(1).strip()
    transfer = re.match(r"Online Transfer (to|from) (CHK|SAV|CD)\s*\.*(\d{4})", entry.description, re.I)
    if transfer:
        return f"Transfer {transfer.group(1).lower()} account ...{transfer.group(3)}"
    # Card lines end in a city, state, and date ("AMAZON MKTPL*B98E30N Amzn.com/bill WA 02/18"); keep the merchant.
    text = re.sub(r"\s+transaction#:?\s*\d+.*$", "", entry.description.strip(), flags=re.I)
    text = re.sub(r"\s+[A-Z]{2}\s+\d{2}/\d{2}$", "", text)
    text = re.sub(r"\*\w+", "", text)
    return re.sub(r"\s+\d{2}/\d{2}$", "", text)[:60]


def vendors(items: list[Entry], start: date | None = None, end: date | None = None) -> list[dict[str, Any]]:
    """Spending by payee over a period: total, payments, categories, and the first and last date."""
    found: dict[str, dict[str, Any]] = {}
    for e in items:
        if e.type != EXPENSE or e.starting or not _within(e, start, end):
            continue
        row = found.setdefault(payee_of(e), {"payee": payee_of(e), "cents": 0, "payments": 0, "categories": defaultdict(int),
                                              "first": e.day, "last": e.day})
        row["cents"] += e.net
        row["payments"] += 1
        row["categories"][e.account] += e.net
        row["first"], row["last"] = min(row["first"], e.day), max(row["last"], e.day)
    return sorted(({**r, "categories": dict(r["categories"]), "first": r["first"].isoformat(), "last": r["last"].isoformat()}
                   for r in found.values()), key=lambda r: -r["cents"])


def cash_flow(items: list[Entry], start: date | None = None, end: date | None = None) -> dict[str, Any]:
    """Each bank account's starting balance, money in and out by category, and ending balance over a period."""
    found: dict[str, dict[str, Any]] = {}
    for e in items:
        if e.type != BANK:
            continue
        acct = found.setdefault(e.account, {"account": e.account, "startCents": None, "endCents": None,
                                            "in": defaultdict(int), "out": defaultdict(int)})
        if start and e.day < start:
            acct["startCents"] = e.balance
            continue
        if end and e.day > end:
            continue
        if e.starting:
            if acct["startCents"] is None:
                acct["startCents"] = e.balance
        else:
            label = e.category or ("transfer" if "transfer" in e.description.lower() else "uncategorized")
            if e.debit:
                acct["in"][label] += e.debit
            if e.credit:
                acct["out"][label] += e.credit
        acct["endCents"] = e.balance
    # An account with no entry in the period (a closed account from years back) is left out.
    return {name: {**a, "in": dict(sorted(a["in"].items(), key=lambda kv: -kv[1])), "out": dict(sorted(a["out"].items(), key=lambda kv: -kv[1])),
                   "inCents": sum(a["in"].values()), "outCents": sum(a["out"].values())}
            for name, a in sorted(found.items()) if a["endCents"] is not None}


def balances(items: list[Entry], as_of: date, *, owners: bool = False) -> dict[str, int]:
    """Each bank (and, with ``owners``, each unit) account's balance on a date: its last running balance on or before it."""
    found: dict[str, int] = {}
    for e in items:
        if e.day > as_of or e.type in (INCOME, EXPENSE) or (e.type in OWNER_TYPES and not owners):
            continue
        found[f"{e.type}: {e.account}"] = e.balance
    return dict(sorted(found.items()))


def receivables(items: list[Entry], as_of: date) -> dict[str, Any]:
    """What the units owe on a date, without names: total owed, total prepaid, and how many units carry each."""
    owed = balances(items, as_of, owners=True)
    due = [v for k, v in owed.items() if k.startswith("Accounts Receivable:") and v > 0]
    prepaid = [v for k, v in owed.items() if k.startswith("Accounts Receivable - Prepaids:") and v]
    return {"asOf": as_of.isoformat(), "owedCents": sum(due), "unitsOwing": len(due), "prepaidCents": sum(prepaid), "unitsPrepaid": len(prepaid)}


def query(items: list[Entry], *, text: str = "", payee: str = "", category: str = "", account: str = "", kind: str = "",
          minimum: int | None = None, maximum: int | None = None, start: date | None = None, end: date | None = None,
          owners: bool = False, limit: int = 200) -> list[dict[str, Any]]:
    """Entries matching every filter given (case-insensitive substrings; amounts in cents on the larger of debit and credit)."""
    t, p, c, a, k = (s.casefold() for s in (text, payee, category, account, kind))
    found = []
    for e in items:
        if e.starting or not _within(e, start, end):
            continue
        if e.type in OWNER_TYPES and not owners:
            continue
        amount = max(e.debit, e.credit)
        if (t and t not in f"{e.description} {e.memo}".casefold()) or (p and p not in payee_of(e).casefold()):
            continue
        if (c and c not in f"{e.category} {e.account if e.type in (INCOME, EXPENSE) else ''}".casefold()) or (a and a not in e.account.casefold()):
            continue
        if (k and k not in e.type.casefold()) or (minimum is not None and amount < minimum) or (maximum is not None and amount > maximum):
            continue
        found.append({"date": e.day.isoformat(), "type": e.type, "account": e.account, "payee": payee_of(e), "description": e.description[:140],
                      "category": e.category, "memo": e.memo, "debitCents": e.debit, "creditCents": e.credit, "balanceCents": e.balance})
        if len(found) >= limit:
            break
    return found


__all__ = ["Entry", "entries", "profit_and_loss", "by_month", "vendors", "cash_flow", "balances", "receivables", "query", "payee_of",
           "BANK", "INCOME", "EXPENSE", "OWNER_TYPES"]
