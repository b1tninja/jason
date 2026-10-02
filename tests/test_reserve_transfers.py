"""Reserve account movements sorted into contributions, borrowings, reimbursements, and repayments (Civil Code 5510, 5515)."""

from __future__ import annotations

from datetime import date

from jason.community.ledger import BANK, EXPENSE, entries
from jason.community.reserve_transfers import MovementKind, Purpose, explain, movements, repayments

RESERVE = {"Reserve Account (Chase)": "6177", "Reserve C/D (Chase)": "7476"}
OPERATING = {"5286"}


def _row(day, description, debit=0, credit=0, memo="", account="Reserve Account (Chase)", kind=BANK, category=""):
    return {"type": kind, "label": account, "date": day, "description": description, "category": category, "memo": memo,
            "vendor": "", "debit": debit, "credit": credit, "balance": 0, "starting": False}


def _explained(rows):
    items = entries(rows)
    return explain(movements(items, RESERVE, OPERATING), items, {"Operating Account (Chase)"})


def test_contributions_regular_catch_up_restoring_and_unscheduled():
    moves = _explained([
        _row("2024-03-14", "Online Transfer from CHK ...5286 transaction#: 1", debit=701400, memo="January 2024"),
        _row("2024-04-20", "Online Transfer from CHK ...5286 transaction#: 2", debit=701400),
        _row("2024-05-20", "Online Transfer from CHK ...5286 transaction#: 3", debit=701400),
        _row("2025-01-23", "Online Transfer from CHK ...5286 transaction#: 4", debit=701400),
        _row("2025-02-20", "Online Transfer from CHK ...5286 transaction#: 5", debit=725950),
        _row("2025-03-20", "Online Transfer from CHK ...5286 transaction#: 6", debit=725950),
        _row("2025-02-20", "Online Transfer from CHK ...5286 transaction#: 7", debit=134000),
        _row("2025-12-13", "TREES OUTLET SACRAMENTO CA 12/13", credit=468000),
        _row("2025-12-15", "Online Transfer from CHK ...5286 transaction#: 8", debit=468000),
    ])
    contributions = [(m.day.isoformat(), m.purpose) for m in moves if m.kind is MovementKind.CONTRIBUTION]
    assert contributions == [("2024-03-14", Purpose.CATCH_UP), ("2024-04-20", Purpose.REGULAR), ("2024-05-20", Purpose.REGULAR),
                             ("2025-01-23", Purpose.REGULAR), ("2025-02-20", Purpose.UNSCHEDULED), ("2025-02-20", Purpose.REGULAR),
                             ("2025-03-20", Purpose.REGULAR), ("2025-12-15", Purpose.RESTORES_PAYMENT)]


def test_withdrawals_borrowing_reimbursement_forwarded_and_investment():
    moves = _explained([
        _row("2024-03-14", "FEDWIRE CREDIT VIA: FIRST-CITIZENS BANK", debit=1188016),
        _row("2024-03-14", "Online Transfer to CHK ...5286 transaction#: 10", credit=1188016),
        _row("2024-03-14", "Online Transfer to CHK ...5286 transaction#: 11", credit=1600000, memo="Borrowed Reserve Funds"),
        _row("2026-02-23", "4TE*SIGNAL SERVICE", debit=62079, kind=EXPENSE, account="FACP", category="FACP"),
        _row("2026-03-16", "Online Transfer to CHK ...5286 transaction#: 12", credit=62079, memo="FACP - Bldg 3"),
        _row("2024-12-20", "Transfer to CDS XXXXXXXX7476 12/20", credit=10000000),
        _row("2024-12-20", "Transfer to CDS XXXXXXXX7476 12/20", debit=10000000, account="Reserve C/D (Chase)"),
        # The bank names the reserve itself on this line; the side says the money left.
        _row("2024-12-26", "Online Transfer from CHK ...6177 transaction#: 13", credit=1608000),
    ])
    out = [(m.day.isoformat(), m.cents, m.purpose) for m in moves if m.kind in (MovementKind.WITHDRAWAL, MovementKind.INVESTMENT)]
    assert out == [("2024-03-14", 1188016, Purpose.FORWARDED_DEPOSIT), ("2024-03-14", 1600000, Purpose.BORROWING),
                   ("2024-12-20", 10000000, Purpose.INVESTMENT), ("2024-12-26", 1608000, Purpose.BORROWING),
                   ("2026-03-16", 62079, Purpose.REIMBURSEMENT)]


def test_an_exact_run_repays_its_borrowing_and_an_unrepaid_one_stays_open():
    rows = [
        _row("2024-03-14", "Online Transfer to CHK ...5286 transaction#: 1", credit=1600000),
        _row("2024-12-26", "Online Transfer from CHK ...6177 transaction#: 2", credit=1608000),
    ]
    rows += [_row(f"2025-{m:02d}-18", f"Online Transfer from CHK ...5286 transaction#: 5{m}", debit=725950) for m in range(1, 13)]
    rows += [_row(f"2025-{m:02d}-20", f"Online Transfer from CHK ...5286 transaction#: 1{m}", debit=134000) for m in range(2, 10)]
    rows.append(_row("2025-10-20", "Online Transfer from CHK ...5286 transaction#: 99", debit=536000))
    loans = repayments(_explained(rows))
    march, december = loans
    assert december.exact and december.repaid_cents == 1608000 and december.repaid_on == date(2025, 10, 20) and december.on_time
    assert march.repaid == [] and march.outstanding_cents == 1600000 and march.deadline == date(2025, 3, 14)


def test_budgeted_months_against_the_transfers_that_paid_them():
    from jason.community.reserve_transfers import budget_months, schedule

    def items(amounts, year):
        return [{"id": m, "month": m, "year": year, "amount": a} for m, a in enumerate(amounts, start=1)]

    tree = {"expense": [{"name": "Transfer to Reserves", "budgetItems": items([701400] * 4, 2024), "children": [
        {"name": "Repayment", "budgetItems": items([0, 134000, 134000, 0], 2024)},
        {"name": "Reserve Analyst", "budgetItems": items([0, 0, 125000, 0], 2024)}]}], "income": []}
    contribution, repayment = budget_months(tree, "Transfer to Reserves"), budget_months(tree, "Repayment")
    assert contribution[(2024, 1)] == 701400 and repayment[(2024, 2)] == 134000 and (2024, 3) not in budget_months(tree, "Nope")
    moves = _explained([
        _row("2024-03-15", "Online Transfer from CHK ...5286 transaction#: 1", debit=701400, memo="January 2024"),
        _row("2024-03-15", "Online Transfer from CHK ...5286 transaction#: 2", debit=701400, memo="February 2024"),
        _row("2024-03-20", "Online Transfer from CHK ...5286 transaction#: 3", debit=701400),
        _row("2024-02-20", "Online Transfer from CHK ...5286 transaction#: 4", debit=134000),
    ])
    rows = {r["month"]: r for r in schedule(moves, contribution, repayment, through=(2024, 4))}
    assert rows["2024-01"]["contributionPaidCents"] == 701400 and rows["2024-01"]["daysLate"] == 44
    assert rows["2024-03"]["contributionPaidCents"] == 701400 and rows["2024-03"]["daysLate"] == 0
    assert rows["2024-04"]["contributionPaidCents"] == 0
    assert rows["2024-02"]["repaymentPaidCents"] == 134000 and rows["2024-03"]["repaymentPaidCents"] == 0


def test_a_deleted_due_to_reserves_account_is_reported(tmp_path):
    import json

    from jason.tasks.reserve_transfers import deleted_reserve_liabilities

    (tmp_path / "payhoa").mkdir()
    (tmp_path / "payhoa" / "ledger-accounts.json").write_text(json.dumps({"liabilities": [
        {"id": 25013, "label": "Accounts Payable", "deletedAt": None},
        {"id": 28409, "label": "Due to Reserves", "startingBalanceDate": "2024-03-15", "deletedAt": "2024-04-03T17:57:59.000000Z"}]}),
        encoding="utf-8")
    assert deleted_reserve_liabilities(tmp_path) == [{"id": 28409, "label": "Due to Reserves", "startingBalanceDate": "2024-03-15",
                                                      "deletedAt": "2024-04-03"}]
