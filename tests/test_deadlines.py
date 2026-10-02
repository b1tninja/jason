"""The association calendar of recurring deadlines: fixed yearly dates, intervals, and the payments that show each done."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from jason.community.obligations import Obligation, Standing
from jason.tasks.deadlines import calendar
from jason.tasks.sources import money_in

TAX = Obligation("Property tax, second installment", "RTC 2617", month=4, day=10, window_days=160, grace_days=150,
                 categories=("Property Tax",))
BACKFLOW = Obligation("Backflow test", "City notice", every_years=1, payee_words=("LEDOUX",))
BALCONY = Obligation("Balcony inspection", "Civil Code 5551", every_years=9, first_due=date(2025, 1, 1), payee_words=("DECK INSPECTION",))
BUDGET = Obligation("Budget report", "Civil Code 5300", month=12, day=1)


def _community(*obligations: Obligation):
    return SimpleNamespace(obligations=lambda: obligations, insurance=lambda: SimpleNamespace(policies=()))


def _write(tmp_path, txs: list[dict]) -> None:
    (tmp_path / "payhoa").mkdir()
    snap = {"syncedAt": "2026-09-29T00:00:00+00:00", "transactions": txs, "vendors": {"5": "LeDoux Backflow Testing Services"},
            "categories": {"1": {"name": "Property Tax"}, "2": {"name": "Backflow Prevention"}}}
    (tmp_path / "payhoa" / "transactions.json").write_text(json.dumps(snap), encoding="utf-8")


def _tx(tx_id: int, day: str, cents: int, category: int = 0, vendor: int = 0, description: str = "") -> dict:
    return {"id": tx_id, "transactionDate": day, "amount": cents, "originalAmount": cents, "categoryId": category,
            "vendorId": vendor, "description": description}


def test_a_fixed_deadline_is_judged_each_year_on_time_late_or_missing(tmp_path) -> None:
    _write(tmp_path, [_tx(1, "2023-10-01", 100, 2), _tx(2, "2024-02-06", 14154, 1), _tx(3, "2025-05-16", 17788, 1)])
    result = calendar(tmp_path, _community(TAX), today=date(2026, 9, 29))
    [row] = [r for r in result["obligations"] if r["name"] == TAX.name]
    history = {h["deadline"]: h for h in row["history"]}
    assert history["2024-04-10"]["standing"] == Standing.DONE.value
    assert history["2025-04-10"]["standing"] == Standing.LATE.value and history["2025-04-10"]["daysLate"] == 36
    assert history["2026-04-10"]["standing"] == Standing.MISSED.value
    assert row["next"] == "2027-04-10" and row["standing"] == Standing.UPCOMING.value
    assert {h["deadline"] for h in result["lateOrMissed"]} == {"2025-04-10", "2026-04-10"}


def test_an_interval_runs_from_the_last_payment_or_the_first_due_date(tmp_path) -> None:
    _write(tmp_path, [_tx(1, "2025-07-08", 69600, vendor=5)])
    rows = {r["name"]: r for r in calendar(tmp_path, _community(BACKFLOW, BALCONY), today=date(2026, 9, 29))["obligations"]}
    assert rows["Backflow test"]["next"] == "2026-07-08" and rows["Backflow test"]["standing"] == Standing.OVERDUE.value
    assert rows["Balcony inspection"]["next"] == "2025-01-01" and rows["Balcony inspection"]["standing"] == Standing.OVERDUE.value


def test_a_deadline_no_store_shows_is_listed_not_judged(tmp_path) -> None:
    _write(tmp_path, [])
    [row] = [r for r in calendar(tmp_path, _community(BUDGET), today=date(2026, 9, 29))["obligations"] if r["name"] == "Budget report"]
    assert row["standing"] == Standing.UNTRACKED.value and row["next"] == "2026-12-01"


def test_money_coming_in_is_never_evidence_of_a_payment() -> None:
    assert money_in({"amount": 7742975, "description": "FEDWIRE CREDIT VIA: FIRST-CITIZENS BANK"})
    assert money_in({"originalAmount": -5000, "description": "check"})
    assert not money_in({"amount": 97500, "description": "ORIG CO NAME:IRS CO ENTRY DESCR:USATAXPYMTS"})


def test_an_interval_counts_from_the_records_date_not_the_payment_for_it(tmp_path) -> None:
    balcony = Obligation("Balcony inspection", "Civil Code 5551", every_years=9, first_due=date(2025, 1, 1),
                         done_on=date(2023, 11, 17), payee_words=("DECK INSPECTION",))
    _write(tmp_path, [_tx(1, "2024-03-14", 480000, description="Online Payment To California Deck Inspection, LLC")])
    [row] = [r for r in calendar(tmp_path, _community(balcony), today=date(2026, 9, 29))["obligations"] if r["name"] == "Balcony inspection"]
    assert row["lastDone"] == "2023-11-17" and row["next"] == "2032-11-17"


def test_month_intervals_count_from_the_last_report():
    from jason.tasks.deadlines import _interval, add_months

    assert add_months(date(2025, 8, 31), 6) == date(2026, 2, 28) and add_months(date(2025, 11, 15), 3) == date(2026, 2, 15)
    alarm = Obligation("Fire alarm", "NFPA 72", every_months=6, done_on=date(2025, 9, 19))
    assert alarm.tracked and alarm.cadence() == "semiannually" and Obligation("x", "y", every_months=3).cadence() == "quarterly"
    row = _interval(alarm, [], date(2026, 9, 29))
    assert (row["next"], row["standing"], row["lastDone"]) == ("2026-03-19", "overdue", "2025-09-19")
