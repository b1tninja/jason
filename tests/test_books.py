"""Reports rebuilt from PayHOA's general ledger rows."""

from __future__ import annotations

from datetime import date

from jason.community.ledger import (
    BANK,
    EXPENSE,
    INCOME,
    balances,
    by_month,
    cash_flow,
    entries,
    payee_of,
    profit_and_loss,
    query,
    receivables,
    vendors,
)


def _row(kind, account, day, description, debit=0, credit=0, balance=0, category="", vendor="", starting=False):
    return {"type": kind, "label": account, "date": day, "description": description, "category": category, "memo": "",
            "vendor": vendor, "debit": debit, "credit": credit, "balance": balance, "starting": starting}


ROWS = [
    _row(BANK, "Operating Account (Chase)", "2026-09-01", "Starting Balance", 1235865, 0, 1235865, starting=True),
    _row(BANK, "Operating Account (Chase)", "2026-09-03", "ORIG CO NAME:Pro Active Pest ORIG ID:1 TRN", 0, 27250, 1208615, "Pest Control", "Pro Active Pest Control"),
    _row(BANK, "Operating Account (Chase)", "2026-09-04", "ORIG CO NAME:SMUD ORIG ID:2946001157 DESC", 0, 6129, 1202486, "Electricity (SMUD)"),
    _row(BANK, "Operating Account (Chase)", "2026-09-05", "PayHOA Deposit", 315860, 0, 1518346),
    _row(EXPENSE, "Pest Control", "2026-09-03", "ORIG CO NAME:Pro Active Pest ORIG ID:1 TRN", 27250, 0, 27250, "Pest Control", "Pro Active Pest Control"),
    _row(EXPENSE, "Electricity (SMUD)", "2026-09-04", "ORIG CO NAME:SMUD ORIG ID:2946001157 DESC", 6129, 0, 6129, "Electricity (SMUD)"),
    _row(EXPENSE, "Electricity (SMUD)", "2026-08-04", "ORIG CO NAME:SMUD ORIG ID:2946001157 DESC", 6000, 0, 6000, "Electricity (SMUD)"),
    _row(EXPENSE, "Flood", "2026-09-06", "Flood Insurance Refund", 0, 9800, -9800, "Flood"),
    _row(INCOME, "Assessments", "2026-09-01", "3006 ENCHANTED WALK: Regular Assessment (monthly)", 0, 28500, 28500, "Assessments"),
    _row("Accounts Receivable", "3006 ENCHANTED WALK", "2026-09-01", "Regular Assessment (monthly)", 28500, 0, 28500, "Assessments"),
    _row("Accounts Receivable - Prepaids", "3010 MAGICAL WALK", "2026-09-01", "Prepayment", 0, 0, 5000),
]


def test_profit_and_loss_and_months() -> None:
    items = entries(ROWS)
    pl = profit_and_loss(items, date(2026, 9, 1), date(2026, 9, 30))
    assert pl["income"] == {"Assessments": 28500}
    assert pl["expense"] == {"Pest Control": 27250, "Electricity (SMUD)": 6129, "Flood": -9800}
    assert pl["netCents"] == 28500 - (27250 + 6129 - 9800)
    assert by_month(items)["Electricity (SMUD)"] == {"2026-08": 6000, "2026-09": 6129}


def test_vendors_cash_flow_balances_and_receivables() -> None:
    items = entries(ROWS)
    top = vendors(items, date(2026, 9, 1), date(2026, 9, 30))
    assert [(v["payee"], v["cents"]) for v in top][:2] == [("Pro Active Pest Control", 27250), ("Smud", 6129)]
    flow = cash_flow(items, date(2026, 9, 1), date(2026, 9, 30))["Operating Account (Chase)"]
    assert (flow["startCents"], flow["inCents"], flow["outCents"], flow["endCents"]) == (1235865, 315860, 33379, 1518346)
    assert balances(items, date(2026, 9, 30)) == {"Assets: Operating Account (Chase)": 1518346}
    assert receivables(items, date(2026, 9, 30)) == {"asOf": "2026-09-30", "owedCents": 28500, "unitsOwing": 1, "prepaidCents": 5000, "unitsPrepaid": 1}


def test_query_leaves_owner_accounts_out_unless_asked() -> None:
    items = entries(ROWS)
    assert {r["type"] for r in query(items, text="assessment")} == {INCOME}
    assert "Accounts Receivable" in {r["type"] for r in query(items, text="assessment", owners=True)}
    assert [r["account"] for r in query(items, payee="smud", kind="expense")] == ["Electricity (SMUD)", "Electricity (SMUD)"]
    assert [r["debitCents"] for r in query(items, minimum=20000, maximum=30000, kind="expense")] == [27250]


def test_payee_names_from_bank_lines() -> None:
    items = entries([
        _row(EXPENSE, "ALPR", "2026-08-03", "Online Payment 30262092659 To Flock Group Inc 08/03", 500000),
        _row(EXPENSE, "Transfer to Reserves", "2026-08-20", "Online Transfer to CHK ...6177 transaction#: 30077969120", 736467),
        _row(EXPENSE, "Electrical", "2026-02-19", "AMAZON MKTPL*B98E30N Amzn.com/bill WA 02/18", 7613),
    ])
    # Entries sort by date: the Amazon card line, then the bill payment, then the reserve transfer.
    assert payee_of(items[0]) == "AMAZON MKTPL Amzn.com/bill"
    assert payee_of(items[1]) == "Flock Group Inc"
    assert payee_of(items[2]) == "Transfer to account ...6177"
