"""The treasurer's report PDFs checked against PayHOA's saved runs and month-end balance sheets."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from jason.tasks.ledger_reports import printed_amount, run_period, validate
from jason.tasks.reserves import merge_reserve_sources


def _run(name: str, completed: str, sheet: dict | None = None, ledger: dict | None = None, digest: str = "") -> dict:
    return {"id": 1, "name": name, "completedAt": completed, "totalPages": 8, "uploadedFile": {"fileHash": digest},
            "criteria": [{"report": "balance-sheet", "criteria": sheet or {"asOfDate": "PREVIOUS_MONTH_END"}},
                         {"report": "general-ledger", "criteria": ledger or {"startDate": "PREVIOUS_MONTH_START", "endDate": "PREVIOUS_MONTH_END"}}]}


def test_run_period_reads_relative_and_stored_dates() -> None:
    assert run_period(_run("Treasurer's Report - 2026-08", "2026-09-11 00:16:39")) == ("2026-08", [])
    assert run_period(_run("Treasurer's Report - 2025-12", "2026-01-06 19:09:40")) == ("2025-12", [])
    period, notes = run_period(_run("Treasurer's Report - 2026-04", "2026-05-15 00:57:29", {"asOfDate": "2026-04-30T07:00:00.000Z"},
                                    {"startDate": "2026-01-01T08:00:00.000Z", "endDate": "2026-04-30T07:00:00.000Z"}))
    assert period == "2026-04" and notes == ["its general ledger runs 2026-01-01 to 2026-04-30, not one month"]
    period, notes = run_period(_run("Treasurer's Report", "2024-09-05 19:17:51", {"asOfDate": "2024-03-01T08:00:00.000Z"}))
    assert period == "2024-03" and "not a month end" in notes[0] and "no month" in notes[1]
    assert run_period(_run("Treasurer's Report - 2025-02", "2025-04-14 00:18:13"))[1] == ["it is named 2025-02 but reports 2025-03"]


def test_printed_amount_reads_the_balance_sheet_only() -> None:
    text = "Reserve Account (Chase)\n$1,049.15\nTotal Assets\n$1.00\nReserve Account (Chase)\n$80,000.00\n"
    assert printed_amount(text, "Reserve Account (Chase)") == 104915
    assert printed_amount(text, "Operating Account (Chase)") is None


def test_validate_matches_runs_by_hash_and_names_what_the_ledger_dropped(tmp_path: Path) -> None:
    report_text = ("C/D Settlement - 12Mth CD 7/3/26 (First Citizens Bank)\n$165,123.03\nReserve Account (Chase)\n$1,049.15\n"
                   "Reserve C/D (Chase)\n$181,858.18\nTotal Assets\n")
    digest = hashlib.sha256(b"december").hexdigest()
    payhoa = tmp_path / "payhoa"
    payhoa.mkdir()
    (payhoa / "saved-reports.json").write_text(json.dumps({"runs": [_run("Treasurer's Report - 2025-12", "2026-01-06 19:09:40", digest=digest)]}))
    sheet = {"asOf": "2025-12-31", "lastUpdated": "", "accounts": [
        {"section": "Bank Accounts", "label": "Reserve Account (Chase)", "accountId": 29523, "accountType": "asset", "cents": 104915},
        {"section": "Bank Accounts", "label": "Reserve C/D (Chase)", "accountId": 45973, "accountType": "asset", "cents": 18185818}]}
    later = {"asOf": "2026-08-31", "lastUpdated": "", "accounts": sheet["accounts"] + [
        {"section": "Bank Accounts", "label": "C/D Settlement - 12Mth CD 7/3/26 (First Citizens Bank)", "accountId": 27845, "accountType": "asset", "cents": 16999076}]}
    (payhoa / "balance-sheets.json").write_text(json.dumps({"sheets": {"2025-12": sheet, "2026-08": later}}))
    (payhoa / "ledger-accounts.json").write_text(json.dumps({"assets": [{"id": 27845, "label": "C/D Settlement - 12Mth CD 7/3/26 (First Citizens Bank)",
                                                                           "startingBalance": 16999076, "startingBalanceDate": "2026-07-03"}]}))
    (tmp_path / "library" / "text").mkdir(parents=True)
    with sqlite3.connect(tmp_path / "library" / "library.db") as conn:
        conn.execute("CREATE TABLE documents (id TEXT, path TEXT, kind TEXT, period TEXT, sha256 TEXT)")
        conn.execute("INSERT INTO documents VALUES ('1', 'Treasurer''s Report - 2025-12.pdf', 'treasurer_report', '2025-12', ?)", (digest,))
    (tmp_path / "library" / "text" / "1.txt").write_text(report_text, encoding="utf-8")
    result = validate(tmp_path)
    assert result["runs"][0]["libraryCopies"] == ["Treasurer's Report - 2025-12.pdf"]
    assert result["balanceChanges"] == [] and result["balancesChecked"] == 2
    (dropped,) = result["accountsTheLedgerDropped"]
    assert dropped["account"].startswith("C/D Settlement") and dropped["printedCents"] == 16512303


def test_reserve_sources_merge_the_ledger_with_what_the_report_printed() -> None:
    printed = {"2024-12": {"accounts": {"Reserve Account": 919783, "Reserve C/D": 10000000, "C/D Settlement - 12Mth CD 7/3/24": 15779821}}}
    ledger = {"2024-12": {"accounts": {"Reserve Account (Chase)": 919783, "Reserve C/D (Chase)": 10000000}}}
    merged = merge_reserve_sources(printed, ledger)["2024-12"]
    assert merged["totalCents"] == 26699604 and merged["source"] == "ledger + report"
    assert merged["fromReportOnly"] == ["C/D Settlement - 12Mth CD 7/3/24"]
