"""The finance snapshot: PayHOA's budget against actual and the bank balances, named from the specification."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from jason.community import mystique
from jason.tasks.finance import balances, dollars, finance_summary, latest_year, load, snapshot, variances


class _FakePayhoa:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def _range(self, name, kwargs):
        self.calls.append((name, kwargs.get("start_year"), kwargs.get("end_month", 12)))

    def budget_summary(self, org_id, **kwargs):
        self._range("summary", kwargs)
        full = kwargs.get("end_month", 12) == 12
        return {"revenue": {"budgeted": 27702000 if full else 20776500, "actual": 23793419, "variance": 0},
                "expense": {"budgeted": 27702000 if full else 20168537, "actual": 19231824, "variance": 0},
                "net": {"budgeted": 0, "actual": 4561595, "variance": 4561595}}

    def budget_monthly_income(self, org_id, **kwargs):
        self._range("monthly-income", kwargs)
        return {"months": [{"label": "Jan '26", "month": 1, "year": 2026, "budget": 2308500, "actual": 2286250}]}

    def budget_monthly_expense(self, org_id, **kwargs):
        self._range("monthly-expense", kwargs)
        return {"months": [{"label": "Jan '26", "month": 1, "year": 2026, "budget": 2106122, "actual": 2011554}]}

    def budget_revenue_distribution(self, org_id, **kwargs):
        self._range("revenue", kwargs)
        return {"totalExpected": 1, "totalActual": 1, "items": [{"id": 1, "name": "Assessments", "actual": 20776500, "expected": 20776500, "child": False, "rollup": False}]}

    def budget_expense_distribution(self, org_id, **kwargs):
        self._range("expense", kwargs)
        return {"totalExpected": 1, "totalActual": 1, "items": [
            {"id": 2, "name": "Repairs", "actual": 1588230, "expected": 675000, "child": False, "rollup": False},
            {"id": 2, "name": "Total for Repairs", "actual": 2212573, "expected": 832500, "child": False, "rollup": True},
            {"id": 3, "name": "Plumbing", "actual": 624343, "expected": 157500, "child": True, "rollup": False},
            {"id": 4, "name": "Insurance", "actual": 1745507, "expected": 2689230, "child": False, "rollup": False},
        ]}

    def list_bank_accounts(self, org_id):
        return [
            {"id": 39351, "friendlyName": "Operating Account", "last4": "1111", "plaidBalance": 1928622, "lastPlaidWebhook": "2026-09-29 06:12:53", "plaidAccountId": "secret"},
            {"id": 39352, "friendlyName": "Reserve Account", "last4": "2222", "plaidBalance": 6502216},
            {"id": 44542, "friendlyName": "Reserve C/D", "last4": "", "plaidBalance": 18604869},
            {"id": 39763, "friendlyName": "Operating Account (Helsing)", "last4": "", "plaidBalance": None},
        ]

    def list_deposit_accounts(self, org_id):
        return [{"id": 36500, "friendlyName": "Operating Account", "pendingFunds": 28255, "lastDeposit": {"amount": -28255, "transactionDate": "2026-09-21", "description": "PayHOA Deposit"}}]

    def collection_progress(self, org_id, *, year):
        return {"data": [], "totals": {"invoiced": 29741841, "collected": 20759003}}


def test_the_snapshot_keeps_the_year_and_year_to_date_and_drops_tokens(tmp_path: Path):
    client = _FakePayhoa()
    path = snapshot(client, 27889, tmp_path, year=2026, today=date(2026, 9, 29))
    assert path == tmp_path / "payhoa" / "finance-2026.json" and latest_year(tmp_path) == 2026
    snap = load(tmp_path, 2026)
    assert snap["throughMonth"] == 9 and snap["yearToDate"]["revenue"]["budgeted"] == 20776500
    assert ("summary", 2026, 9) in client.calls and ("expense", 2026, 9) in client.calls and ("expense", 2026, 12) in client.calls
    assert "plaidAccountId" not in snap["bankAccounts"][0]
    assert snap["depositAccounts"][0]["lastDeposit"]["amount"] == -28255


def test_accounts_are_named_from_the_specification_by_suffix_or_name(tmp_path: Path):
    snapshot(_FakePayhoa(), 27889, tmp_path, year=2026, today=date(2026, 9, 29))
    named = balances(load(tmp_path, 2026), mystique().bank_accounts())
    assert [(b.label, b.suffix, b.payhoa_name, b.balance_cents) for b in named] == [
        ("Operating", "1111", "Operating Account", 1928622),
        ("Reserve", "2222", "Reserve Account", 6502216),
        ("Reserve CD", "3333", "Reserve C/D", 18604869),
        # The settlement CD has no Plaid feed and no last four in PayHOA, so the snapshot gives no balance for it.
        ("Reserve CD (First Citizens)", "4444", "", None),
    ]
    assert named[0].refreshed == "2026-09-29 06:12:53"


def test_the_gaps_are_year_to_date_and_a_total_stands_for_its_own_line(tmp_path: Path):
    snapshot(_FakePayhoa(), 27889, tmp_path, year=2026, today=date(2026, 9, 29))
    snap = load(tmp_path, 2026)
    rows = variances(snap, "expense")
    assert [row["category"] for row in rows] == ["Repairs", "Insurance"]
    assert rows[0] == {"category": "Repairs", "budgeted": 832500, "actual": 2212573, "gap": 1380073}
    brief = finance_summary(snap, mystique().bank_accounts())
    assert brief["reserveTotalCents"] == 6502216 + 18604869 and brief["collection"]["collected"] == 20759003
    assert brief["months"][0]["incomeActual"] == 2286250
    assert dollars(-936713) == "-$9,367.13" and dollars(None) == "n/a"
