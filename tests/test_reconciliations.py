"""PayHOA's bank reconciliations read from disk, and the ledger's months against PayHOA's own profit and loss."""

from __future__ import annotations

import json
from datetime import date

from jason.community.ledger import BANK, EXPENSE, entries
from jason.tasks.books import compare_months
from jason.tasks.reconciliations import in_transit, open_transfers, review, review_lines


def _rec(rid, account, account_id, start, end, ending, payments=(), deposits=()):
    return {"id": rid, "account": account, "accountId": account_id, "last4": "5286" if account_id == 1 else "6177",
            "start": start, "end": end, "endingBalance": ending,
            "report": {"summary": {"Statement ending balance": ending, "Register Balance as of x": ending - 100},
                       "discrepancies": 0, "unreconciledPayments": list(payments), "unreconciledDeposits": list(deposits)}}


def _write(tmp_path, recs, ledger_accounts):
    folder = tmp_path / "payhoa"
    folder.mkdir()
    (folder / "reconciliations.json").write_text(json.dumps({"fetchedAt": "2026-09-29", "reconciliations": recs}), encoding="utf-8")
    (folder / "ledger-accounts.json").write_text(json.dumps({"assets": ledger_accounts}), encoding="utf-8")


def test_review_reports_gaps_open_items_and_transfers(tmp_path, monkeypatch):
    transfer_out = {"date": "2024-03-14", "description": "Online Transfer to CHK ...6177", "amount": 701400}
    transfer_in = {"date": "2024-03-15", "description": "Online Transfer from CHK ...5286", "amount": 701400}
    lockbox = {"date": "2026-08-31", "description": "Lockbox Deposit", "amount": 28500}
    recs = [
        _rec(1, "Operating Account", 1, "2025-12-01", "2025-12-31", 1000000),
        _rec(2, "Operating Account", 1, "2026-02-01", "2026-02-28", 1200000),
        _rec(3, "Operating Account", 1, "2026-08-01", "2026-08-31", 1207365, payments=[transfer_out], deposits=[lockbox]),
        _rec(4, "Reserve Account", 2, "2026-08-01", "2026-08-31", 5765749, deposits=[transfer_in]),
    ]
    # Two ledger accounts share the friendly name; the bank account id picks the right one.
    _write(tmp_path, recs, [
        {"label": "Operating Account (First Citizens Bank)", "ownerType": "App\\Models\\Entities\\UnifiedBankAccount", "ownerId": 9,
         "startingBalanceDate": "2024-03-01"},
        {"label": "Operating Account (Chase)", "ownerType": "App\\Models\\Entities\\UnifiedBankAccount", "ownerId": 1,
         "startingBalanceDate": "2026-01-01"},
    ])
    ledger = entries([
        {"type": BANK, "label": "Operating Account (First Citizens Bank)", "date": "2026-08-30", "description": "x", "balance": 5},
        {"type": BANK, "label": "Operating Account (Chase)", "date": "2026-02-27", "description": "x", "balance": 1200000},
        {"type": BANK, "label": "Operating Account (Chase)", "date": "2026-08-31", "description": "Lockbox Deposit", "balance": 1235865},
    ])
    monkeypatch.setattr("jason.tasks.books.load", lambda data_dir: ledger)
    result = review(tmp_path, today=date(2026, 9, 29))
    ops, reserve = result["accounts"]
    assert ops["gaps"] == ["2026-01", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07"]
    assert ops["ledgerAccount"] == "Operating Account (Chase)" and ops["beforeLedger"] == 1
    assert ops["ledgerMismatches"] == [{"end": "2026-08-31", "statementCents": 1207365, "ledgerCents": 1235865, "differenceCents": 28500,
                                        "inTransitCents": 28500, "explained": True}]
    assert [i["ageDays"] for i in ops["openItems"]] == [929, 29] and len(ops["staleOpenItems"]) == 1
    assert reserve["ledgerAccount"] is None and reserve["openDepositsCents"] == 701400
    assert result["openTransfers"] == [{"from": "Operating Account", "to": "Reserve Account", "paid": "2024-03-14", "deposited": "2024-03-15",
                                        "amount": 701400, "description": "Online Transfer to CHK ...6177", "recordedTwice": False}]
    text = "\n".join(review_lines(result))
    assert "items in transit" in text and "Transfers open on both sides" in text


def test_in_transit_counts_only_the_period():
    rec = _rec(1, "Operating Account", 1, "2026-08-01", "2026-08-31", 0,
               payments=[{"date": "2026-08-30", "description": "check", "amount": 1000}, {"date": "2024-01-02", "description": "old", "amount": 5}],
               deposits=[{"date": "2026-08-31", "description": "lockbox", "amount": 28500}])
    assert in_transit(rec) == 27500


def test_open_transfers_pair_once_and_only_across_accounts():
    item = lambda kind, day: {"kind": kind, "date": day, "amount": 100, "description": "t"}
    accounts = [{"account": "A", "openItems": [item("payment", "2026-01-01"), item("payment", "2026-01-01"), item("deposit", "2026-01-01")]},
                {"account": "B", "openItems": [item("deposit", "2026-01-02")]}]
    assert len(open_transfers(accounts)) == 1


def test_review_without_a_fetch(tmp_path):
    assert review(tmp_path)["found"] is False


def test_compare_months_against_payhoa_profit_and_loss():
    items = entries([
        {"type": EXPENSE, "label": "Landscaping", "date": "2026-01-05", "description": "E&R", "debit": 283200, "balance": 283200},
        {"type": EXPENSE, "label": "Landscaping", "date": "2026-02-05", "description": "E&R", "debit": 283200, "balance": 566400},
        {"type": "Income Categories", "label": "Prepayments", "date": "2026-08-31", "description": "Lockbox", "credit": 28500, "balance": 28500},
    ])
    payhoa = [{"side": "Expenses", "name": "Landscaping", "total": 566400, "columns": {"202601": 283200, "202602": 280000}},
              {"side": "Income", "name": "Uncategorized Account Credits", "total": 45750, "columns": {}},
              {"side": "Expenses", "name": "Security", "total": 0, "columns": {"202601": 0}}]
    result = compare_months(items, payhoa, 2026)
    assert result["cells"] == 2 and result["agree"] == 1
    assert result["differ"] == [{"category": "Landscaping", "month": "2026-02", "payhoaCents": 280000, "ledgerCents": 283200, "differenceCents": 3200}]
    assert result["onlyPayhoa"] == [{"side": "Income", "category": "Uncategorized Account Credits", "cents": 45750}]
    assert result["onlyLedger"] == [{"category": "Prepayments", "cents": 28500}]


def test_diagnose_compares_whole_bank_lines():
    from jason.tasks.reconciliations import diagnose

    city = "ORIG CO NAME:CITY OF SACRAMEN ORIG ID:9003215002 DESC DATE:JUL 24 TRACE#:{} EED:240731"
    open_items = [
        {"kind": "payment", "date": "2024-07-30", "description": city.format("795"), "amount": 2079, "ageDays": 791},
        {"kind": "payment", "date": "2024-07-30", "description": city.format("795"), "amount": 564, "ageDays": 791},
        {"kind": "payment", "date": "2024-07-28", "description": city.format("111"), "amount": 564, "ageDays": 793},
        {"kind": "deposit", "date": "2025-08-21", "description": "Void/Cancel: Invoice 1447173 for $250.00", "amount": 25000, "ageDays": 404},
        {"kind": "deposit", "date": "2026-08-31", "description": "Lockbox Deposit", "amount": 28500, "ageDays": 29},
    ]
    cleared = [
        {"date": "2024-07-30", "description": city.format("795"), "payment": 2079, "deposit": 0},
        {"date": "2024-07-30", "description": city.format("795"), "payment": 564, "deposit": 0},
        # Another account's $5.64 fire-service piece: the same amount, not the same line.
        {"date": "2024-07-21", "description": city.format("238"), "payment": 11815, "deposit": 0},
        {"date": "2024-07-21", "description": city.format("238"), "payment": 564, "deposit": 0},
    ]
    diagnose(open_items, cleared)
    assert [i["reason"] for i in open_items] == ["same bank line", "same bank line", "", "voided bill payment", "in transit"]
    assert open_items[0]["splitOf"] == 2 and open_items[0]["lineCents"] == 2643 and open_items[0]["twin"]["trace"] == "795"
