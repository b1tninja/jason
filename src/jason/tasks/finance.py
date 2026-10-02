"""The association's money as PayHOA reports it: the budget against actual, and the bank balances.

``snapshot`` calls PayHOA (the budget summary for the year and year to date,
the monthly budget and actual, the category distributions, the bank and
deposit accounts, and collection progress) and writes one JSON file per year
under ``data/payhoa/``. Everything else reads that file, so ``jason-mcp``
answers without calling PayHOA. Amounts are integer cents. Each bank account
is named from the specification (``mystique/banking.py``) by its last four
digits, or by its name when PayHOA stores none (the reserve CD).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

FINANCE_DIR = "payhoa"


def snapshot_path(root: Path, year: int) -> Path:
    return root / FINANCE_DIR / f"finance-{year}.json"


def snapshot(client, org_id: int, root: Path, *, year: int, today: date | None = None) -> Path:
    """Fetch the year's budget and actuals and the bank balances; write ``data/payhoa/finance-<year>.json``."""
    day = today or date.today()
    through = day.month if year == day.year else 12
    data: dict[str, Any] = {
        "year": year,
        "throughMonth": through,
        "syncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": client.budget_summary(org_id, start_year=year),
        "yearToDate": client.budget_summary(org_id, start_year=year, end_month=through),
        "monthlyIncome": client.budget_monthly_income(org_id, start_year=year).get("months", []),
        "monthlyExpense": client.budget_monthly_expense(org_id, start_year=year).get("months", []),
        "revenue": client.budget_revenue_distribution(org_id, start_year=year),
        "expense": client.budget_expense_distribution(org_id, start_year=year),
        # The same views through the current month, so a category's actual meets the budget for the same months.
        "revenueYtd": client.budget_revenue_distribution(org_id, start_year=year, end_month=through),
        "expenseYtd": client.budget_expense_distribution(org_id, start_year=year, end_month=through),
        "bankAccounts": [_account(a) for a in client.list_bank_accounts(org_id)],
        "depositAccounts": [_deposit(a) for a in client.list_deposit_accounts(org_id)],
        "collection": client.collection_progress(org_id, year=year),
    }
    path = snapshot_path(root, year)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return path


def _account(row: dict[str, Any]) -> dict[str, Any]:
    """The fields of a bank account worth keeping; tokens and processor ids stay behind."""
    keep = ("id", "friendlyName", "last4", "plaidBalance", "fcBalance", "fcBalanceAsOf", "lastPlaidWebhook", "plaidImportAfter", "currency", "deletedAt")
    return {key: row.get(key) for key in keep}


def _deposit(row: dict[str, Any]) -> dict[str, Any]:
    last = row.get("lastDeposit") or {}
    return {"id": row.get("id"), "friendlyName": row.get("friendlyName"), "pendingFunds": row.get("pendingFunds"),
            "lastDeposit": {"amount": last.get("amount"), "date": last.get("transactionDate"), "description": last.get("description")}}


def load(root: Path, year: int) -> dict[str, Any] | None:
    path = snapshot_path(root, year)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def latest_year(root: Path) -> int | None:
    years = [int(m[1]) for p in (root / FINANCE_DIR).glob("finance-*.json") if (m := re.match(r"finance-(\d{4})\.json$", p.name))]
    return max(years) if years else None


@dataclass(frozen=True)
class AccountBalance:
    label: str
    purpose: str
    suffix: str
    payhoa_name: str
    balance_cents: int | None
    refreshed: str


def _letters(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def balances(snap: dict[str, Any], accounts) -> tuple[AccountBalance, ...]:
    """Each specification account's balance from the snapshot, matched by last four, else by name ("Reserve C/D")."""
    rows = [row for row in snap.get("bankAccounts") or [] if not row.get("deletedAt")]
    found: list[AccountBalance] = []
    used: set[int] = set()
    for account in accounts:
        match = next((row for row in rows if row.get("last4") == account.suffix and row["id"] not in used), None)
        if match is None and account.label:
            match = next((row for row in rows if _letters(row.get("friendlyName") or "") == _letters(account.label) and row["id"] not in used), None)
        if match is not None:
            used.add(match["id"])
        balance = None if match is None else (match.get("plaidBalance") if match.get("plaidBalance") is not None else match.get("fcBalance"))
        refreshed = "" if match is None else str(match.get("lastPlaidWebhook") or match.get("fcBalanceAsOf") or "")
        found.append(AccountBalance(account.label or account.purpose.value, account.purpose.value, account.suffix,
                                    match.get("friendlyName", "") if match else "", balance, refreshed))
    return tuple(found)


TOTAL_PREFIX = "Total for "


def variances(snap: dict[str, Any], side: str, *, top: int = 8, year_to_date: bool = True) -> list[dict[str, Any]]:
    """The categories furthest from budget on one side (``revenue`` or ``expense``), largest gap first, cents.

    Year to date by default, so a category's actual meets the budget for the same months. A parent category
    appears twice in PayHOA's list, as its own line and as "Total for <name>"; the total stands for both.
    """
    view = (snap.get(f"{side}Ytd") if year_to_date else None) or snap.get(side) or {}
    items = [item for item in view.get("items") or [] if not item.get("child")]
    totals = {str(item.get("name") or "")[len(TOTAL_PREFIX):] for item in items if str(item.get("name") or "").startswith(TOTAL_PREFIX)}
    rows = []
    for item in items:
        name = str(item.get("name") or "")
        if name in totals:
            continue
        budgeted, actual = int(item.get("expected") or 0), int(item.get("actual") or 0)
        rows.append({"category": name[len(TOTAL_PREFIX):] if name.startswith(TOTAL_PREFIX) else name,
                     "budgeted": budgeted, "actual": actual, "gap": actual - budgeted})
    rows.sort(key=lambda row: -abs(row["gap"]))
    return rows[:top]


def dollars(cents: int | None) -> str:
    if cents is None:
        return "n/a"
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:,.2f}"


def finance_summary(snap: dict[str, Any], accounts) -> dict[str, Any]:
    """The snapshot as a brief: the year and year to date against budget, the months, the biggest gaps, the balances."""
    ytd = snap.get("yearToDate") or {}
    reserves = [b for b in balances(snap, accounts) if b.purpose == "reserve"]
    return {
        "year": snap.get("year"), "throughMonth": snap.get("throughMonth"), "syncedAt": snap.get("syncedAt"),
        "yearToDate": ytd, "fullYear": snap.get("summary"),
        "months": [{"month": inc.get("label"), "incomeBudget": inc.get("budget"), "incomeActual": inc.get("actual"),
                    "expenseBudget": exp.get("budget"), "expenseActual": exp.get("actual")}
                   for inc, exp in zip(snap.get("monthlyIncome") or [], snap.get("monthlyExpense") or [])],
        "expenseGaps": variances(snap, "expense"), "revenueGaps": variances(snap, "revenue"),
        "accounts": [b.__dict__ for b in balances(snap, accounts)],
        "reserveTotalCents": sum(b.balance_cents or 0 for b in reserves) if reserves else None,
        "collection": (snap.get("collection") or {}).get("totals"),
        "note": "PayHOA's figures as of the sync; balances come from Plaid and can lag the bank. Amounts are integer cents.",
    }
