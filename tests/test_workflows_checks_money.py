"""The money family's reads (src/jason/workflows/checks/money.py): twenty-seven ``check`` names over made-up stores in a temporary
data folder. Nothing here reads a real store, reaches the network, or loads a profile. Every read is pinned read-only by
comparing the folder byte for byte before and after; a store that is missing or cannot be read gives ``ok=False`` with the
reason, never an exception and never ``ok`` by default. Plainly fake: "A. Manager", "123-456-789-0000", dates in 2026 or 2099.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.community.payees import PayeeClass, PayeeRule
from jason.community.reserve_study import StudyLevel
from jason.workflows import api, checks, definitions, store
from jason.workflows import definitions_general as general
from jason.workflows.checks import money as reads
from jason.workflows.defs import money as defs
from jason.workflows.readers import CHECKS, StoreReaders, named_check
from jason.workflows.types import CheckResult, EventKind, Role, StepDef, StepKind
from test_workflows_support import data  # noqa: F401 - the `data` fixture

TODAY = date(2026, 10, 10)
STAMP = "2026-10-09T02:10:00+00:00"
NAMES = ("bill-snapshot-fresh", "bill-queue-read", "bill-handed", "payee-class-read", "stores-tried-read", "bill-mail-arrived",
         "review-reconciliations", "review-budget", "reserve-study-due", "insurance-due", "tax-standing", "tax-bill-files",
         "review-statements", "review-income-expense", "review-registers", "fiscal-window", "reserve-plan-match",
         "disclosure-reserve-summary", "disclosure-insurance-summary", "insurance-limits", "insurance-changed", "insurance-summary",
         "disclosure-delivery-read", "reserve-notice", "reserve-restored", "tax-years-closed", "insurance-answer")
SUGGESTS = ("insurance-changed",)
"""Reads that only suggest: they pass whenever they were made, and say there is no suggestion when a store gives none."""
TAX = PayeeRule(PayeeClass.COUNTY_TAX, description_contains=("EXAMPLE COUNTY TAX",), note="the county tax collector's ACH line")


def tree(root: Path) -> dict[str, bytes]:
    """Every file under a folder with its bytes: what a read must leave exactly as it was."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()} if root.exists() else {}


def community(*rules, policies=()):
    return SimpleNamespace(payee_rules=lambda: tuple(rules), vendor_portals=lambda: (), bank_accounts=lambda: (), senders=lambda: (),
                           insurance=lambda: SimpleNamespace(policies=list(policies)), units=lambda: ())


def run_view(subject="", dates=None, label=""):
    return SimpleNamespace(id="run-test", subject=subject, dates=dict(dates or {}), label=label, opened_at="2020-01-01T00:00:00Z")


def readers_of(root, *rules, policies=(), today=TODAY, comm=None):
    root.mkdir(parents=True, exist_ok=True)
    return StoreReaders(root, community=comm or community(*rules, policies=policies), today=today)


def result(name, root, subject="", item="", *rules, policies=(), today=TODAY, dates=None, label="", comm=None):
    """Run the named read; assert it leaves the folder as it was; return its result."""
    readers = readers_of(root, *rules, policies=policies, today=today, comm=comm)
    before = tree(root)
    res = CHECKS[name](readers, run_view(subject, dates, label), item)
    assert isinstance(res, CheckResult)
    assert tree(root) == before, f"{name} changed the data folder"
    return res


def tx(ident, amount, desc, day="2026-10-07", **kw):
    return {"id": ident, "amount": amount, "description": desc, "transactionDate": day, "approved": False, "attachments": [], **kw}


def snapshot(root, txs, stamp=STAMP):
    path = root / "payhoa" / "transactions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"syncedAt": stamp, "categories": {"1": {"name": "Utilities", "type": "expense"}},
                                "vendors": {}, "transactions": txs}), encoding="utf-8")


def tax_db(root, rows):
    """rows: (apn, number, year, total, payments, balance, pdf_path)."""
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(root / "tax.db")
    conn.execute("CREATE TABLE bills (apn TEXT, number TEXT, year INTEGER, total_cents INTEGER, payments_cents INTEGER, "
                 "balance_cents INTEGER, pdf_path TEXT, synced_at TEXT)")
    conn.executemany("INSERT INTO bills VALUES (?, ?, ?, ?, ?, ?, ?, '2026-10-01T00:00:00+00:00')", rows)
    conn.commit()
    conn.close()


# --- the registry ---------------------------------------------------------------------------------------------------------

def test_the_twenty_seven_reads_are_registered_by_name_and_only_once():
    checks.load_all()
    assert set(NAMES) <= set(CHECKS)
    assert len(set(NAMES)) == 27
    before = dict(CHECKS)
    checks.load_all()
    assert CHECKS == before
    with pytest.raises(ValueError):
        checks.check("bill-handed")(lambda r, v, i="": CheckResult(True))


def test_every_read_on_an_empty_data_folder_is_not_ok_says_why_and_writes_nothing(tmp_path):
    root = tmp_path / "data"                         # the folder does not even exist
    for name in NAMES:
        res = result(name, root, "month:2026-09" if name != "payee-class-read" else "transaction:1", comm=community())
        assert res.message, name
        assert res.ok is (name in SUGGESTS) and res.choice == "", name           # a suggestion with nothing to go on makes none
    assert not root.exists() or not tree(root)


def test_a_read_that_raises_is_not_ok_with_the_reason_never_an_exception(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("the disk is full of cats")

    monkeypatch.setattr("jason.tasks.bill_queue.build", boom)
    res = result("bill-snapshot-fresh", tmp_path / "data")
    assert res.ok is False and "cannot read" in res.message and "cats" in res.message


def test_the_step_reads_by_name_through_the_engine_readers(tmp_path):
    root = tmp_path / "data"
    snapshot(root, [])
    readers = readers_of(root)
    step = StepDef("x.1", "Is the snapshot fresh", StepKind.CHECK, role=Role.JASON, check=named_check("bill-snapshot-fresh"))
    assert readers.check(step, run_view("month:2026-09")).ok is True
    wait = StepDef("x.2", "Wait for mail", StepKind.WAIT, role=Role.MANAGER, check=named_check("bill-mail-arrived"))
    assert readers.arrival(wait, run_view("transaction:1")) is None                  # nothing arrived: no such transaction either


# --- bill-snapshot-fresh ------------------------------------------------------------------------------------------------------

def test_a_snapshot_inside_the_stale_after_is_fresh(tmp_path):
    root = tmp_path / "data"
    snapshot(root, [tx(1, 100, "ACH X")])
    res = result("bill-snapshot-fresh", root)
    assert res.ok and "2026-10-09" in res.message and "days old" in res.message and "stale-after" in res.message
    assert len(res.evidence) == 1 and res.evidence[0].startswith("file:payhoa/transactions.json@")


def test_a_snapshot_past_the_stale_after_fails_and_names_the_command(tmp_path):
    root = tmp_path / "data"
    snapshot(root, [])
    res = result("bill-snapshot-fresh", root, today=date(2026, 10, 15))
    assert res.ok is False and "past its stale-after" in res.message and "jason invoices --fetch" in res.message


def test_a_snapshot_with_an_unreadable_time_or_body_or_no_file_fails(tmp_path):
    root = tmp_path / "data"
    assert "No PayHOA snapshot" in result("bill-snapshot-fresh", root).message
    snapshot(root, [], stamp="last Tuesday")
    res = result("bill-snapshot-fresh", root)
    assert res.ok is False and "cannot be read as a time" in res.message
    (root / "payhoa" / "transactions.json").write_text("{not json", encoding="utf-8")
    assert result("bill-snapshot-fresh", root).ok is False


# --- bill-queue-read ----------------------------------------------------------------------------------------------------------

def test_the_queue_counts_the_rows_by_status_and_passes_when_it_reads(tmp_path):
    root = tmp_path / "data"
    snapshot(root, [tx(1, 41200, "ACH SOMEONE ELSE"), tx(2, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR"),
                    tx(3, 500, "ACH SOMEONE ELSE", attachments=[{"id": 1}]), tx(4, 700, "ACH SOMEONE ELSE", approved=True)])
    res = result("bill-queue-read", root, "month:2026-09", "", TAX)
    assert res.ok and "3 payment(s) wait on a bill" in res.message
    assert "1 unrouted" in res.message and "1 not checked" in res.message and "1 already attached" in res.message
    assert "Sources with a payment waiting: county-tax" in res.message                     # the county source owns the tax payment
    assert len(res.evidence) == 1 and res.evidence[0].startswith("file:payhoa/transactions.json@")      # no dry run kept yet


def test_the_queue_says_when_the_snapshot_is_missing_or_the_profile_cannot_answer(tmp_path):
    root = tmp_path / "data"
    assert result("bill-queue-read", root).ok is False
    snapshot(root, [tx(1, 100, "ACH X")])
    broken = SimpleNamespace(payee_rules=lambda: (_ for _ in ()).throw(RuntimeError("no rows")), vendor_portals=lambda: ())
    res = result("bill-queue-read", root, comm=broken)
    assert res.ok is False and "cannot read" in res.message


# --- bill-handed --------------------------------------------------------------------------------------------------------------

@pytest.fixture
def registered():
    definitions.reset()
    general.register_general()
    yield
    definitions.reset()


def start_bill_attach(root, month):
    out = api.start(root, defs.BA, f"month:{month}", month, {}, "A. Manager", yes=True, today=TODAY)
    rid = out["run"]["id"]
    api.open_run(root, rid, "A. Manager", yes=True, today=TODAY)
    return rid


def test_a_bill_attach_run_that_has_handed_the_pass_ends_the_wait(tmp_path, data, registered):
    month = "2026-09"
    assert result("bill-handed", data, f"month:{month}").message.startswith("no bill-attach run")
    rid = start_bill_attach(data, month)
    res = result("bill-handed", data, f"month:{month}")
    assert res.ok is False and rid in res.message and "not handed yet" in res.message
    assert result("bill-handed", data, "month:2026-08").ok is False                 # another month's run does not count
    store.append(data, defs.BA, rid, EventKind.ATTESTED, by="A. Manager", step=defs.step_id(defs.BA, "hand"),
                 detail={"what": "Hand the pass to the treasurer", "record": "three payments left open: no bill yet"})
    res = result("bill-handed", data, f"month:{month}")
    assert res.ok and "handed the pass to the treasurer" in res.message and rid in res.message


def test_a_cancelled_run_is_not_a_hand_over_and_a_run_with_no_month_cannot_be_looked_for(tmp_path, data, registered):
    rid = start_bill_attach(data, "2026-09")
    store.append(data, defs.BA, rid, EventKind.ATTESTED, by="A. Manager", step=defs.step_id(defs.BA, "hand"),
                 detail={"what": "hand", "record": "x"})
    api.cancel(data, rid, "A. Manager", reason="opened by mistake", today=TODAY)
    assert result("bill-handed", data, "month:2026-09").ok is False
    assert "names no month" in result("bill-handed", data, "the review").message


def test_without_the_definition_registered_the_read_says_so(tmp_path):
    definitions.reset()
    res = result("bill-handed", tmp_path / "data", "month:2026-09")
    assert res.ok is False and "not registered" in res.message


# --- payee-class-read ---------------------------------------------------------------------------------------------------------

def test_the_payee_class_is_named_with_the_row_that_chose_it_and_a_miss_stays_a_miss(tmp_path):
    root = tmp_path / "data"
    snapshot(root, [tx(7, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR"), tx(8, 41200, "ACH SOMEONE ELSE")])
    res = result("payee-class-read", root, "transaction:7", "", TAX)
    assert res.ok and "county-tax" in res.message and "the county tax collector's ACH line" in res.message
    miss = result("payee-class-read", root, "transaction:8", "", TAX)
    assert miss.ok and "payee class unknown" in miss.message and "a miss stays a miss" in miss.message
    assert result("payee-class-read", root, "unused", "8", TAX).ok                       # the item can name it instead


def test_the_payee_class_fails_for_an_unknown_transaction_a_subject_with_none_or_no_snapshot(tmp_path):
    root = tmp_path / "data"
    assert "No PayHOA snapshot" in result("payee-class-read", root, "transaction:7").message
    snapshot(root, [tx(7, 100, "ACH X")])
    assert "transaction 99 is not in the snapshot" in result("payee-class-read", root, "transaction:99").message
    assert "names no PayHOA transaction" in result("payee-class-read", root, "the pass for September").message


# --- stores-tried-read and bill-mail-arrived -----------------------------------------------------------------------------------

def test_every_store_is_searched_by_amount_and_a_candidate_is_a_lead(tmp_path):
    root = tmp_path / "data"
    snapshot(root, [tx(7, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR")])
    (root / "bills").mkdir()
    (root / "bills" / "b.pdf").write_bytes(b"%PDF")
    tax_db(root, [("123-456-789-0000", "B1", 2026, 36357, 0, 36357, "bills/b.pdf")])
    res = result("stores-tried-read", root, "transaction:7", "", TAX)
    assert res.ok and "stores read" in res.message and "1 candidate(s), 1 exact" in res.message
    assert "a lead until a person attaches it" in res.message and "not read:" in res.message
    assert "123-456" not in res.message and "0000" not in res.message                # no parcel number, not even its tail


def test_no_candidate_still_passes_and_a_store_that_cannot_be_read_is_named_not_read(tmp_path, monkeypatch):
    root = tmp_path / "data"
    snapshot(root, [tx(7, 36357, "ACH SOMEONE ELSE")])
    res = result("stores-tried-read", root, "transaction:7")
    assert res.ok and "0 candidate(s)" in res.message

    def unreadable(_root):
        raise OSError("the library is locked")

    monkeypatch.setattr("jason.tasks.library.load", unreadable)
    res = result("stores-tried-read", root, "transaction:7")
    assert res.ok and "not read:" in res.message and "the library's readings" in res.message


def mail(root, *rows):
    path = root / "mail" / "items.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"items": list(rows)}), encoding="utf-8")


def test_a_scanned_letter_naming_the_amount_ends_the_wait_and_is_not_described(tmp_path):
    root = tmp_path / "data"
    snapshot(root, [tx(7, 6129, "ACH SOMEONE ELSE")])
    assert result("bill-mail-arrived", root, "transaction:7").ok is False
    mail(root, {"mailId": "m1", "kind": "vendor invoice or statement", "received": "2026-10-05", "from": "Example Alarm",
                "text": "Invoice. Amount due $61.29. Thank you."})
    res = result("bill-mail-arrived", root, "transaction:7")
    assert res.ok and "a scanned letter" in res.message and "Example Alarm" not in res.message and "m1" not in res.message
    mail(root, {"mailId": "m2", "kind": "advertisement", "received": "2026-10-05", "text": "Save $61.29 today"})
    assert result("bill-mail-arrived", root, "transaction:7").ok is False                 # not a bill-bearing kind of letter


def test_the_arrival_the_engine_asks_is_the_same_read(tmp_path):
    root = tmp_path / "data"
    snapshot(root, [tx(7, 6129, "ACH SOMEONE ELSE")])
    mail(root, {"mailId": "m1", "kind": "utility bill", "received": "2026-10-05", "text": "Total due $61.29"})
    readers = readers_of(root)
    wait = StepDef("x.2", "Wait for mail", StepKind.WAIT, role=Role.MANAGER, check=named_check("bill-mail-arrived"))
    assert "a scanned letter" in (readers.arrival(wait, run_view("transaction:7")) or "")


# --- review-reconciliations ---------------------------------------------------------------------------------------------------

def rec(account, end, *, ident=1, start=None, open_payments=(), account_id=1):
    return {"id": ident, "account": account, "accountId": account_id, "last4": "1234", "start": start or end[:8] + "01", "end": end,
            "startingBalance": 100, "endingBalance": 200, "totalPayments": 0, "totalDeposits": 0, "completedAt": end,
            "report": {"summary": {}, "unreconciledPayments": list(open_payments), "unreconciledDeposits": [], "discrepancies": 0},
            "cleared": []}


def reconciliations(root, *recs):
    path = root / "payhoa" / "reconciliations.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetchedAt": "2026-10-05T00:00:00+00:00", "reconciliations": list(recs)}), encoding="utf-8")


def test_every_account_reconciled_through_the_month_with_no_gap_passes_and_counts_the_open_items(tmp_path):
    root = tmp_path / "data"
    open_payment = {"date": "2026-09-20", "amount": 1200, "description": "Check 1001"}
    reconciliations(root, rec("Operating", "2026-08-31", ident=1), rec("Operating", "2026-09-30", ident=2, open_payments=[open_payment]),
                    rec("Reserve", "2026-09-30", ident=3, account_id=2))
    res = result("review-reconciliations", root, "month:2026-09")
    assert res.ok and "2 account(s) reconciled through 2026-09" in res.message and "1 open item(s)" in res.message
    assert "1200 cents of payments" in res.message and "reviewer's judgment" in res.message
    assert res.evidence and res.evidence[0].startswith("file:payhoa/reconciliations.json@")
    assert result("review-reconciliations", root, "", "Reserve", dates={"month_end": "2026-09-30"}).ok       # one account, month from the date


def test_an_account_behind_the_month_or_with_a_skipped_month_fails_and_a_missing_account_is_said(tmp_path):
    root = tmp_path / "data"
    reconciliations(root, rec("Operating", "2026-09-30", ident=1), rec("Reserve", "2026-08-31", ident=2, account_id=2),
                    rec("Savings", "2026-05-31", ident=3, account_id=3), rec("Savings", "2026-09-30", ident=4, account_id=3))
    res = result("review-reconciliations", root, "month:2026-09")
    assert res.ok is False and "not reconciled through 2026-09: Reserve" in res.message and "a month skipped: Savings" in res.message
    assert "no reconciliation is on file for the account Checking" in result("review-reconciliations", root, "month:2026-09", "Checking").message
    assert "names no month" in result("review-reconciliations", root, "the review").message


def test_reconciliations_that_are_missing_or_unreadable_fail_with_the_reason(tmp_path):
    root = tmp_path / "data"
    assert "jason reconcile --fetch" in result("review-reconciliations", root, "month:2026-09").message
    reconciliations(root)
    assert "holds no account" in result("review-reconciliations", root, "month:2026-09").message
    (root / "payhoa" / "reconciliations.json").write_text("{broken", encoding="utf-8")
    res = result("review-reconciliations", root, "month:2026-09")
    assert res.ok is False and "cannot read" in res.message


# --- review-budget ------------------------------------------------------------------------------------------------------------

def finance(root, year=2026, through=9):
    path = root / "payhoa" / f"finance-{year}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "year": year, "throughMonth": through, "syncedAt": "2026-10-05T00:00:00+00:00",
        "expenseYtd": {"items": [{"name": "Landscaping", "expected": 1000, "actual": 1500}, {"name": "Water", "expected": 500, "actual": 400}]},
        "revenueYtd": {"items": [{"name": "Dues", "expected": 9000, "actual": 8000}]}}), encoding="utf-8")


def test_the_budget_snapshot_through_the_month_counts_the_categories_off_budget(tmp_path):
    root = tmp_path / "data"
    finance(root)
    res = result("review-budget", root, "month:2026-09")
    assert res.ok and "2 expense and 1 revenue categories" in res.message and "1 expense categories over budget" in res.message
    assert "Landscaping, by 500 cents" in res.message and "1 revenue categories under budget" in res.message
    assert res.evidence and res.evidence[0].startswith("file:payhoa/finance-2026.json@")


def test_a_snapshot_that_stops_short_of_the_month_or_is_missing_or_unreadable_fails(tmp_path):
    root = tmp_path / "data"
    assert "no finance snapshot for 2026" in result("review-budget", root, "month:2026-09").message
    finance(root, through=8)
    res = result("review-budget", root, "month:2026-09")
    assert res.ok is False and "runs through month 8, not 9" in res.message
    assert "names no month" in result("review-budget", root, "").message
    (root / "payhoa" / "finance-2026.json").write_text("[", encoding="utf-8")
    assert result("review-budget", root, "month:2026-09").ok is False


# --- reserve-study-due --------------------------------------------------------------------------------------------------------

def study(fiscal_year, prepared, level=StudyLevel.FULL):
    return SimpleNamespace(fiscal_year=fiscal_year, prepared=prepared, level=level)


def test_a_site_visit_or_review_that_falls_due_by_the_fiscal_year_passes_and_says_which(tmp_path, monkeypatch):
    monkeypatch.setattr("jason.tasks.reserves.load_studies", lambda root: [study(2024, date(2024, 3, 1))])
    root = tmp_path / "data"
    res = result("reserve-study-due", root, "fiscal-year:2027")
    assert res.ok and "the site visit and the annual review fall due by fiscal year 2027" in res.message
    assert "next site visit is for fiscal year 2027" in res.message and "5550" not in res.message
    assert "threshold" in res.message                                                   # applicability is a person's answer
    only_review = result("reserve-study-due", root, "fiscal-year:2026")
    assert only_review.ok and "the annual review falls due by fiscal year 2026" in only_review.message


def test_nothing_due_or_no_study_or_an_unreadable_study_fails(tmp_path, monkeypatch):
    root = tmp_path / "data"
    monkeypatch.setattr("jason.tasks.reserves.load_studies", lambda r: [study(2030, date(2030, 3, 1))])
    res = result("reserve-study-due", root, "fiscal-year:2027")
    assert res.ok is False and "nothing falls due by fiscal year 2027" in res.message
    monkeypatch.setattr("jason.tasks.reserves.load_studies", lambda r: [])
    assert "no reserve study on disk" in result("reserve-study-due", root, "fiscal-year:2027").message

    def unreadable(_r):
        raise ValueError("the study is a scan with no text")

    monkeypatch.setattr("jason.tasks.reserves.load_studies", unreadable)
    assert "cannot read" in result("reserve-study-due", root, "fiscal-year:2027").message


def test_a_study_with_no_site_visit_cannot_date_the_visit(tmp_path, monkeypatch):
    monkeypatch.setattr("jason.tasks.reserves.load_studies",
                        lambda r: [study(2025, date(2025, 3, 1), StudyLevel.UPDATE_WITHOUT_SITE_VISIT)])
    res = result("reserve-study-due", tmp_path / "data", "fiscal-year:2026")
    assert res.ok and "no study with a site visit is on file" in res.message and "annual review" in res.message


# --- insurance-due ------------------------------------------------------------------------------------------------------------

def policy(number="EX-1000", renewal=date(2026, 12, 1), kind="MASTER"):
    return SimpleNamespace(kind=SimpleNamespace(name=kind, value=kind.lower()), numbers=(number,), number=number, prior_numbers=(),
                           renewal=renewal, carrier="Example Mutual", program="", agent="Example Agency", building=None,
                           premium_categories=())


def test_a_term_end_inside_the_window_is_read_with_its_days_and_standing(tmp_path):
    res = result("insurance-due", tmp_path / "data", "policy:EX-1000", "", policies=(policy(),))
    assert res.ok and "the named policy" in res.message and "in 52 days" in res.message
    assert "inside the 90-day renewal window (proposed policy)" in res.message and "master" in res.message


def test_a_term_end_outside_the_window_still_passes_so_an_early_renewal_is_not_blocked(tmp_path):
    res = result("insurance-due", tmp_path / "data", "policy:ending-2027", "", policies=(policy(renewal=date(2027, 6, 30)),))
    assert res.ok and "2 policies" not in res.message and "1 policies" in res.message and "outside the 90-day" in res.message
    ended = result("insurance-due", tmp_path / "data", "policy:EX-1000", "", policies=(policy(renewal=date(2026, 9, 1)),))
    assert ended.ok and "39 days ago" in ended.message


def test_the_policy_the_run_names_is_the_one_read_else_the_soonest_of_all(tmp_path):
    both = (policy("EX-1000", date(2027, 1, 1)), policy("EX-2000", date(2026, 11, 1), "UMBRELLA"))
    res = result("insurance-due", tmp_path / "data", "policy:EX-1000", "", policies=both)
    assert "the named policy" in res.message and "in 83 days" in res.message
    soonest = result("insurance-due", tmp_path / "data", "policy:next-term", "", policies=both)
    assert "2 policies" in soonest.message and "in 22 days" in soonest.message and "umbrella" in soonest.message


def test_no_policy_or_no_term_end_fails(tmp_path):
    assert "lists no policy" in result("insurance-due", tmp_path / "data", "policy:EX-1000").message
    res = result("insurance-due", tmp_path / "data", "policy:EX-1000", "", policies=(policy(renewal=None),))
    assert res.ok is False and "has a term end" in res.message


# --- tax-standing and tax-bill-files ------------------------------------------------------------------------------------------

PAID, DUE, OLD = "123-456-789-0001", "123-456-789-0002", "123-456-789-0003"


def test_each_parcels_standing_is_counted_and_a_delinquent_year_is_said_without_blocking(tmp_path):
    root = tmp_path / "data"
    tax_db(root, [(PAID, "P24", 2024, 1000, 1000, 0, ""), (PAID, "P25", 2025, 1000, 1000, 0, ""),
                  (DUE, "D25", 2025, 1000, 0, 1000, ""),
                  (OLD, "O24", 2024, 1000, 0, 1000, ""), (OLD, "O25", 2025, 1000, 1000, 0, "")])
    res = result("tax-standing", root)
    assert res.ok and "3 parcel(s) read" in res.message and "1 delinquent" in res.message and "1 due" in res.message and "1 paid" in res.message
    assert "ending 0003 (2024)" in res.message and "never delinquent, until a bill date is entered" in res.message
    assert "123-456" not in res.message
    one = result("tax-standing", root, "", DUE)
    assert one.ok and "1 parcel(s) read: 1 due" in one.message
    assert result("tax-standing", root, "", "999-999-999-9999").ok is False


def test_a_year_with_no_bill_between_two_bills_is_a_gap_in_the_bills(tmp_path):
    root = tmp_path / "data"
    tax_db(root, [(PAID, "P23", 2023, 1000, 1000, 0, ""), (PAID, "P25", 2025, 1000, 1000, 0, "")])
    res = result("tax-standing", root)
    assert res.ok and "1 gap in the bills" in res.message and "years with no bill on file: ending 0001" in res.message


def test_a_missing_or_unreadable_tax_catalog_fails_and_is_not_created_or_changed(tmp_path):
    root = tmp_path / "data"
    for name in ("tax-standing", "tax-bill-files"):
        res = result(name, root)
        assert res.ok is False and "jason sync-tax" in res.message
        assert not (root / "tax.db").exists()                                      # the store's constructor would have made it
    (root / "tax.db").write_bytes(b"this is not a database at all")
    for name in ("tax-standing", "tax-bill-files"):
        assert result(name, root).ok is False
    (root / "tax.db").unlink()
    sqlite3.connect(root / "tax.db").close()                                       # a database with no bills table
    for name in ("tax-standing", "tax-bill-files"):
        assert "no readable bills table" in result(name, root).message


def test_every_bill_of_the_tax_year_with_its_file_passes_with_the_files_as_evidence(tmp_path):
    root = tmp_path / "data"
    (root / "tax-bills").mkdir(parents=True)
    (root / "tax-bills" / "a.pdf").write_bytes(b"%PDF-a")
    (root / "tax-bills" / "b.pdf").write_bytes(b"%PDF-b")
    tax_db(root, [(PAID, "P24", 2024, 1000, 1000, 0, "tax-bills/old-missing.pdf"), (PAID, "P25", 2025, 1000, 0, 1000, "tax-bills/a.pdf"),
                  (DUE, "D25", 2025, 1000, 0, 1000, "tax-bills/b.pdf")])
    res = result("tax-bill-files", root, "tax-year:2025")
    assert res.ok and "2 of 2 bill(s) of tax year 2025" in res.message and len(res.evidence) == 2
    assert all(e.startswith("file:tax-bills/") for e in res.evidence)
    assert result("tax-bill-files", root).ok                                         # no year named: the newest year in the catalog


def test_a_bill_with_no_file_fails_and_is_named_by_its_tail_only(tmp_path):
    root = tmp_path / "data"
    (root / "tax-bills").mkdir(parents=True)
    (root / "tax-bills" / "a.pdf").write_bytes(b"%PDF-a")
    tax_db(root, [(PAID, "P25", 2025, 1000, 0, 1000, "tax-bills/a.pdf"), (DUE, "D25", 2025, 1000, 0, 1000, "tax-bills/gone.pdf"),
                  (OLD, "O25", 2025, 1000, 0, 1000, "")])
    res = result("tax-bill-files", root, "2025")
    assert res.ok is False and "1 of 3 bill(s) of tax year 2025" in res.message
    assert "ending 0002 bill D25" in res.message and "ending 0003 bill O25" in res.message and "123-456" not in res.message
    assert len(res.evidence) == 1
    assert result("tax-bill-files", root, "tax-year:2031").ok is False
    assert result("tax-bill-files", root, "", "D25").ok is False                       # one bill by its number
    assert result("tax-bill-files", root, "", PAID).ok is True                          # one parcel by its number


def test_a_pdf_path_that_leaves_the_data_folder_is_no_file(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    (tmp_path / "outside.pdf").write_bytes(b"%PDF")
    tax_db(root, [(PAID, "P25", 2025, 1000, 0, 1000, "../outside.pdf")])
    assert result("tax-bill-files", root, "2025").ok is False


# === round two ================================================================================================================
# Made up: "A. Manager", "Example Bank", 2099 or 2026 dates, "123-456-789-000N". The ledger, library, policy report, and notice
# ledger are written here with sqlite or json; the reserve transfers' review and the studies are replaced where their own tests
# hold the readers.

from jason.community.base import AccountPurpose, BankAccount
from jason.community.reserve_study import ProjectionYear, ReserveDisclosure, ReserveStudy
from jason.tasks import books, library as lib

OPERATING = BankAccount("1111", AccountPurpose.OPERATING, "Example Bank", "Operating")
RESERVE = BankAccount("2222", AccountPurpose.RESERVE, "Example Bank", "Reserve")


def bank_community(*accounts, **extra):
    return SimpleNamespace(**{**vars(community()), "bank_accounts": lambda: tuple(accounts), **extra})


def ledger_rows(root, month, rows, fetched="2026-10-05T00:00:00+00:00"):
    """rows: (type, account, day, description, category, debit, credit, balance, starting)."""
    path = root / "payhoa" / books.STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(books.SCHEMA)
    conn.execute("DELETE FROM entries WHERE month = ?", (month,))
    conn.executemany("INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     [(month, i, t, a, d, desc, cat, "", "", dr, cr, bal, int(st)) for i, (t, a, d, desc, cat, dr, cr, bal, st) in enumerate(rows)])
    conn.execute("INSERT OR REPLACE INTO months VALUES (?,?,?,?,?)", (month, fetched, len(rows), len(rows), None))
    conn.commit()
    conn.close()


SEPTEMBER = [
    ("Assets", "Operating", "2026-09-01", "Opening", "", 5000, 0, 5000, True),
    ("Income Categories", "Dues", "2026-09-03", "Dues", "Dues", 0, 40000, 0, False),
    ("Assets", "Operating", "2026-09-03", "Dues deposit", "Dues", 40000, 0, 45000, False),
    ("Expense Categories", "Landscaping", "2026-09-10", "Check 1001", "Landscaping", 12000, 0, 0, False),
    ("Assets", "Operating", "2026-09-10", "Check 1001", "Landscaping", 0, 12000, 33000, False),
    ("Accounts Receivable", "Accounts Receivable:Unit 1", "2026-09-15", "Assessment", "", 7000, 0, 7000, False),
]


# --- review-statements ----------------------------------------------------------------------------------------------------------

def library_with(root, *rows):
    """rows: (id, name, path, kind, period)."""
    path = root / lib.STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(lib.SCHEMA)
    conn.executemany(f"INSERT INTO documents ({lib.COLUMNS}) VALUES ({','.join('?' * 14)})",
                     [(i, "payhoa", pth, name, kind, "", "", "name", period, 1, "", 1.0, "2026-10-01", f"sha-{i}") for i, name, pth, kind, period in rows])
    conn.commit()
    conn.close()


def test_every_account_with_a_statement_of_the_month_in_the_library_passes_and_no_number_is_said(tmp_path):
    root = tmp_path / "data"
    library_with(root, ("a", "Statement 1111 Sep.pdf", "Bank/Statement 1111 Sep.pdf", "bank_statement", "2026-09"),
                 ("b", "Statement 2222 Sep.pdf", "Bank/Statement 2222 Sep.pdf", "bank_statement", "2026-09"),
                 ("c", "Statement 1111 Aug.pdf", "Bank/Statement 1111 Aug.pdf", "bank_statement", "2026-08"))
    res = result("review-statements", root, "month:2026-09", comm=bank_community(OPERATING, RESERVE))
    assert res.ok and "2 of 2 bank account(s) have a statement of 2026-09" in res.message and "2 statement file(s)" in res.message
    assert "1111" not in res.message and "2222" not in res.message and res.evidence[0].startswith("file:library/library.db@")


def test_an_account_with_no_statement_of_the_month_fails_and_is_named_by_its_label(tmp_path):
    root = tmp_path / "data"
    library_with(root, ("a", "Statement 1111 Sep.pdf", "Bank/Statement 1111 Sep.pdf", "bank_statement", "2026-09"),
                 ("b", "Statement 2222 Aug.pdf", "Bank/Statement 2222 Aug.pdf", "bank_statement", "2026-08"))
    res = result("review-statements", root, "month:2026-09", comm=bank_community(OPERATING, RESERVE))
    assert res.ok is False and "1 of 2" in res.message and "none filed for Reserve" in res.message
    one = result("review-statements", root, "month:2026-09", "operating", comm=bank_community(OPERATING, RESERVE))
    assert one.ok and "1 of 1" in one.message
    assert result("review-statements", root, "month:2026-09", "nothing", comm=bank_community(OPERATING)).ok is False


def test_statements_without_a_month_an_account_or_a_library_say_so(tmp_path):
    root = tmp_path / "data"
    assert "names no month" in result("review-statements", root, "the review", comm=bank_community(OPERATING)).message
    assert "names no bank account" in result("review-statements", root, "month:2026-09").message
    assert "no library on disk" in result("review-statements", root, "month:2026-09", comm=bank_community(OPERATING)).message
    assert not (root / "library").exists()


# --- review-income-expense and review-registers ----------------------------------------------------------------------------------

def test_the_income_and_expense_of_a_month_read_after_it_ended_is_counted_in_cents(tmp_path):
    root = tmp_path / "data"
    ledger_rows(root, "2026-09", SEPTEMBER)
    res = result("review-income-expense", root, "month:2026-09")
    assert res.ok and "1 income categories, 40000 cents" in res.message and "1 expense categories, 12000 cents" in res.message
    assert "net 28000 cents" in res.message and "1 bank account(s) moved money" in res.message and "reviewer's judgment" in res.message
    assert res.evidence[0].startswith("file:payhoa/ledger.db@") and "$" not in res.message


def test_a_month_read_before_it_ended_or_not_stored_or_with_no_income_or_expense_fails(tmp_path):
    root = tmp_path / "data"
    assert "no ledger on disk" in result("review-income-expense", root, "month:2026-09").message
    ledger_rows(root, "2026-09", SEPTEMBER, fetched="2026-09-20T00:00:00+00:00")
    assert "before the month ended" in result("review-income-expense", root, "month:2026-09").message
    assert "before the month ended" in result("review-registers", root, "month:2026-09").message
    assert "holds no rows of 2026-08" in result("review-income-expense", root, "month:2026-08").message
    assert "names no month" in result("review-registers", root, "the review").message
    ledger_rows(root, "2026-07", [SEPTEMBER[0], SEPTEMBER[5]], fetched="2026-08-05T00:00:00+00:00")
    assert "no income or expense entry in 2026-07" in result("review-income-expense", root, "month:2026-07").message


def test_the_three_registers_are_drawn_from_the_stored_ledger_without_a_name(tmp_path):
    root = tmp_path / "data"
    ledger_rows(root, "2026-09", SEPTEMBER)
    res = result("review-registers", root, "month:2026-09")
    assert res.ok and "holds 6 row(s)" in res.message and "1 payment(s) out, 12000 cents" in res.message
    assert "1 unit(s) owe 7000 cents" in res.message and "Unit 1" not in res.message
    assert result("review-registers", root, "", dates={"month_end": "2026-09-30"}).ok


# --- fiscal-window --------------------------------------------------------------------------------------------------------------

def test_the_window_is_computed_from_the_catalog_and_the_dated_day_must_fall_inside_it(tmp_path):
    root = tmp_path / "data"
    res = result("fiscal-window", root, "fiscal-year:2099", dates={"fiscal_year_end": "2099-12-31", "dated_day": "2099-10-15"})
    assert res.ok and "2099-10-02 to 2099-12-01" in res.message and "CIV 5300, 5310 the same" in res.message
    assert "2099-10-15 is inside it" in res.message
    early = result("fiscal-window", root, "fiscal-year:2099", dates={"fiscal_year_end": "2099-12-31", "dated_day": "2099-09-01"})
    assert early.ok is False and "outside it" in early.message
    late = result("fiscal-window", root, "fiscal-year:2099", dates={"fiscal_year_end": "2099-12-31", "dated_day": "2099-12-20"})
    assert late.ok is False and "outside it" in late.message


def test_a_date_not_on_record_is_a_state_never_a_guess(tmp_path):
    root = tmp_path / "data"
    res = result("fiscal-window", root, "fiscal-year:2099")
    assert res.ok is False and "fiscal year's end is not on record" in res.message
    res = result("fiscal-window", root, "fiscal-year:2099", dates={"fiscal_year_end": "2099-12-31"})
    assert res.ok is False and "2099-10-02 to 2099-12-01" in res.message and "date not on record" in res.message


# --- reserve-plan-match and disclosure-reserve-summary ---------------------------------------------------------------------------

def make_study(year=2099, contribution=1200000):
    row = ProjectionYear(year, 0, contribution, 5000, 300000, 4500000, 6000000, 75.0)
    return ReserveStudy("Example Reserve Analysts", date(2098, 3, 1), 2098, StudyLevel.FULL, 24, "study.pdf",
                        ReserveDisclosure(current_balance_cents=3900000), projection=(row,))


def budget_snapshot(root, year, transfer):
    path = root / "payhoa" / f"finance-{year}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"year": year, "throughMonth": 12, "syncedAt": "2099-01-05T00:00:00+00:00",
                                "expense": {"items": [{"name": "Transfer to Reserves", "expected": transfer}, {"name": "Water", "expected": 5}]}}),
                    encoding="utf-8")


def test_the_budgets_transfer_to_reserves_matches_the_studys_contribution_for_the_year(tmp_path, monkeypatch):
    root = tmp_path / "data"
    monkeypatch.setattr("jason.tasks.reserves.load_studies", lambda r: [make_study()])
    budget_snapshot(root, 2099, 1200000)
    res = result("reserve-plan-match", root, "fiscal-year:2099")
    assert res.ok and "transfers 1200000 cents" in res.message and "plans 1200000 cents" in res.message and "they agree" in res.message
    assert res.evidence[0].startswith("file:payhoa/finance-2099.json@")
    budget_snapshot(root, 2099, 1200050)
    assert result("reserve-plan-match", root, "fiscal-year:2099").message.endswith("inside a dollar")
    budget_snapshot(root, 2099, 1000000)
    off = result("reserve-plan-match", root, "fiscal-year:2099")
    assert off.ok is False and "differ by -200000 cents" in off.message


def test_the_plan_match_and_the_reserve_summary_say_what_is_missing(tmp_path, monkeypatch):
    root = tmp_path / "data"
    monkeypatch.setattr("jason.tasks.reserves.load_studies", lambda r: [])
    for name in ("reserve-plan-match", "disclosure-reserve-summary"):
        assert "no reserve study on disk" in result(name, root, "fiscal-year:2099").message
    monkeypatch.setattr("jason.tasks.reserves.load_studies", lambda r: [make_study(2099)])
    assert "has no plan row for 2031" in result("disclosure-reserve-summary", root, "fiscal-year:2031").message
    assert "no finance snapshot for 2099" in result("reserve-plan-match", root, "fiscal-year:2099").message
    budget_snapshot(root, 2099, 1)
    (root / "payhoa" / "finance-2099.json").write_text(json.dumps({"expense": {"items": []}}), encoding="utf-8")
    assert "no 'Transfer to Reserves' line" in result("reserve-plan-match", root, "fiscal-year:2099").message


def test_the_reserve_summary_reads_the_years_figures_from_the_latest_study_in_cents(tmp_path, monkeypatch):
    monkeypatch.setattr("jason.tasks.reserves.load_studies", lambda r: [make_study()])
    res = result("disclosure-reserve-summary", tmp_path / "data", "fiscal-year:2099")
    assert res.ok and "contribution 1200000 cents" in res.message and "projected end 4500000 cents" in res.message
    assert "fully funded 6000000 cents, 75.0 percent funded" in res.message and "current balance is 3900000 cents" in res.message
    assert "treasurer's to confirm against the bank" in res.message and "$" not in res.message


# --- the policy report: insurance summary, limits, changes -----------------------------------------------------------------------

def term(start, end, number="EX-1000", **limits):
    return {"start": start, "end": end, "number": number, "carrier": "Example Mutual", "deductible": 2500000,
            "limits": limits or {"building_limit": 90000000, "each_occurrence": 100000000}}


def policy_report(root, *policies):
    path = root / "reports" / "policies.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"found": True, "builtAt": "2099-01-01T00:00:00", "documents": 3, "policies": list(policies)}), encoding="utf-8")


def pol(key="master", number="EX-1000", terms=(), findings=(), kind=None, prior=()):
    return {"key": key, "kind": kind or key, "building": None, "number": number, "priorNumbers": list(prior), "renewal": None,
            "terms": list(terms), "findings": list(findings)}


def finding(code, severity, authority=""):
    return {"code": code, "message": "a finding", "severity": severity, "authority": authority}


def test_every_policy_with_a_term_in_force_on_the_first_day_of_the_year_makes_the_summary_complete(tmp_path):
    root = tmp_path / "data"
    policy_report(root, pol(terms=[term("2098-06-01", "2099-06-01")]),
                  pol("umbrella", "EX-2000", terms=[term("2098-06-01", "2099-06-01", "EX-2000", each_occurrence=500000000)]))
    res = result("disclosure-insurance-summary", root, "fiscal-year:2099")
    assert res.ok and "3 summary row(s) for fiscal year 2099 from 2 policy(ies)" in res.message
    assert res.evidence[0].startswith("file:reports/policies.json@")
    one = result("insurance-summary", root, "policy:EX-2000", "", dates={"term_end": "2099-06-01"})
    assert one.ok and "the named policy" in one.message and "1 summary row(s) for fiscal year 2099 from 1 policy(ies)" in one.message


def test_a_policy_with_no_term_on_the_first_day_leaves_a_gap_and_fails(tmp_path):
    root = tmp_path / "data"
    policy_report(root, pol(terms=[term("2097-06-01", "2098-06-01")]))
    res = result("disclosure-insurance-summary", root, "fiscal-year:2099")
    assert res.ok is False and "1 gap(s)" in res.message and "master has no term on file in force on 2099-01-01" in res.message
    assert result("insurance-summary", root, "policy:EX-1000", "", dates={"term_end": "2099-06-01"}).ok is False
    policy_report(root)
    assert "lists no policy" in result("insurance-summary", root, "policy:EX-1000").message


def test_the_insurance_reads_without_a_report_say_how_to_build_it(tmp_path):
    for name in ("disclosure-insurance-summary", "insurance-summary", "insurance-limits"):
        assert "jason policies --fetch" in result(name, tmp_path / "data", "policy:EX-1000").message
    assert not (tmp_path / "data").exists() or not tree(tmp_path / "data")


def test_the_limits_read_counts_findings_by_severity_and_passes_when_the_declarations_were_read(tmp_path):
    root = tmp_path / "data"
    policy_report(root, pol(findings=[finding("d-and-o", "problem", "CIV 5800(a)(4)"), finding("crime", "check", "CIV 5806(a)"),
                                       finding("flood", "info", "CIV 5805(b)"), finding("sheet", "check", "")],
                            terms=[term("2098-06-01", "2099-06-01")]))
    res = result("insurance-limits", root, "policy:EX-1000")
    assert res.ok and "the named policy: 3 finding(s)" in res.message and "1 problem, 1 to look at, 1 for information" in res.message
    assert "0 without declarations read" in res.message and "weighs it before it decides" in res.message      # a shortfall never blocks the decision
    policy_report(root, pol(findings=[finding("no-declarations", "problem")]))
    assert result("insurance-limits", root, "policy:EX-1000").ok is False
    policy_report(root, pol(terms=[term("2098-06-01", "2099-06-01")]), pol("umbrella", "EX-2000", findings=[finding("no-declarations", "problem")]))
    mixed = result("insurance-limits", root, "policy:next-term")
    assert mixed.ok is False and "2 policy(ies)" in mixed.message and result("insurance-limits", root, "policy:EX-1000").ok


def decisions(root, number="EX-1000", notice=False, decision="renew as quoted"):
    path = root / "insurance" / "renewals.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"renewals": {number: {"number": number, "decision": decision, "memberNoticeNeeded": notice}}}), encoding="utf-8")


def test_the_read_suggests_changed_when_the_board_recorded_a_notice_or_the_declarations_show_a_cut(tmp_path):
    root = tmp_path / "data"
    decisions(root)
    res = result("insurance-changed", root, "policy:EX-1000")
    assert res.ok and res.choice == "unchanged" and res.message.startswith("suggested unchanged:") and "A suggestion only" in res.message
    decisions(root, notice=True, decision="let lapse")
    res = result("insurance-changed", root, "policy:EX-1000")
    assert res.ok and res.choice == "changed" and "memberNoticeNeeded is yes" in res.message and "let lapse" in res.message
    decisions(root)
    cut = pol(terms=[term("2097-06-01", "2098-06-01", building_limit=90000000, each_occurrence=100000000),
                     term("2098-06-01", "2099-06-01", building_limit=80000000, each_occurrence=100000000)])
    policy_report(root, cut)
    res = result("insurance-changed", root, "policy:EX-1000", dates={"term_end": "2098-06-01"})
    assert res.ok and res.choice == "changed" and "1 change(s), 1 the statute names" in res.message
    assert result("insurance-changed", root, "policy:EX-1000", dates={"term_end": "2099-05-01"}).choice == "changed"


def test_the_read_makes_no_suggestion_without_the_boards_decision_on_record_and_the_manager_answers_by_hand(tmp_path):
    root = tmp_path / "data"
    res = result("insurance-changed", root, "policy:EX-1000")
    assert res.ok and res.choice == "" and "no suggestion" in res.message and "board's decision comes first" in res.message
    assert "the manager answers by hand" in res.message
    decisions(root, "EX-9999")
    other = result("insurance-changed", root, "policy:EX-1000")
    assert other.ok and other.choice == "" and "no suggestion" in other.message
    assert result("insurance-changed", root, "policy:ending-2099").choice == ""


def test_a_decision_store_that_cannot_be_read_leaves_no_suggestion_rather_than_a_failed_step(tmp_path):
    root = tmp_path / "data"
    path = root / "insurance" / "renewals.json"
    path.parent.mkdir(parents=True)
    path.write_text("[", encoding="utf-8")
    res = result("insurance-changed", root, "policy:EX-1000")
    assert res.ok and res.choice == "" and "no suggestion" in res.message


def answer_view(answer="", suggested="", message="", record=""):
    """A run's view with the two steps the answer check looks at, by their ids in the definition."""
    ids = {defs.step_id(defs.IR, "chg"): SimpleNamespace(choice=answer, record=record, detail={}),
           defs.step_id(defs.IR, "read"): SimpleNamespace(choice=suggested, record="", detail={"message": message})}
    return SimpleNamespace(id="run-test", subject="policy:EX-1000", dates={}, label="", step=lambda sid: ids.get(sid))


def answered(tmp_path, **kw):
    readers = readers_of(tmp_path / "data")
    return CHECKS["insurance-answer"](readers, answer_view(**kw), "")


def test_the_answer_check_records_that_the_person_overrode_the_read_and_judges_nothing(tmp_path):
    same = answered(tmp_path, answer="changed", suggested="changed")
    assert same.ok and same.message == "the answer changed agrees with the read's suggestion"
    over = answered(tmp_path, answer="unchanged", suggested="changed", record="the declarations were corrected")
    assert over.ok and over.message.startswith("the person overrode the read: answered unchanged where the read suggested changed")
    assert "a record came with it" in over.message and "the answer stands as the person's" in over.message
    bare = answered(tmp_path, answer="unchanged", suggested="changed")
    assert bare.ok and "no record or reason came with it" in bare.message
    hand = answered(tmp_path, answer="changed", message="no suggestion: no renewal decision is recorded")
    assert hand.ok and "given by hand" in hand.message and "no suggestion to compare" in hand.message
    assert answered(tmp_path).ok is False and "no answer" in answered(tmp_path).message
    stranger = CHECKS["insurance-answer"](readers_of(tmp_path / "data"), run_view("policy:EX-1000"), "")
    assert stranger.ok is False and "not an insurance renewal" in stranger.message


# --- disclosure-delivery-read ----------------------------------------------------------------------------------------------------

def deliveries(root, *rows):
    path = root / "notices" / "deliveries.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("create table attempts (notice text, membership_id integer, unit_id integer, unit text, channel text, batch text, "
                 "key text, sent_at text, status text, status_at text, reason text, synced_at text)")
    conn.executemany("insert into attempts values (?, ?, 1, 'Unit 1', ?, 'b', ?, '', ?, '', '', '')",
                     [(n, i, ch, f"k{i}", st) for i, (n, ch, st) in enumerate(rows)])
    conn.commit()
    conn.close()


def test_a_send_with_no_attempt_pending_is_read_and_the_follow_ups_are_counted(tmp_path):
    root = tmp_path / "data"
    deliveries(root, *[("annual-budget-report-2099", "email", "delivered")] * 3, ("annual-budget-report-2099", "email", "bounced"),
               ("annual-budget-report-2099", "letter", "returned"), ("annual-budget-report-2098", "email", "pending"))
    res = result("disclosure-delivery-read", root, "fiscal-year:2099")
    assert res.ok and "5 attempt(s) for annual-budget-report-2099" in res.message and "3 delivered" in res.message
    assert "1 bounced" in res.message and "2 need a follow-up" in res.message and "Unit 1" not in res.message
    assert res.evidence[0].startswith("file:notices/deliveries.db@")


def test_a_pending_attempt_or_no_send_on_record_does_not_end_the_wait(tmp_path):
    root = tmp_path / "data"
    assert "none on record" in result("disclosure-delivery-read", root, "fiscal-year:2099").message
    assert not (root / "notices").exists()                                              # the ledger's own opener would have made it
    deliveries(root, ("annual-budget-report-2099", "email", "delivered"), ("annual-budget-report-2099", "email", "pending"))
    res = result("disclosure-delivery-read", root, "fiscal-year:2099")
    assert res.ok is False and "1 still pending" in res.message
    assert "no attempt for annual-budget-report-2031" in result("disclosure-delivery-read", root, "fiscal-year:2031").message
    assert result("disclosure-delivery-read", root, "fiscal-year:2031", "annual-budget-report-2099").ok is False
    (root / "notices" / "deliveries.db").write_bytes(b"not a database")
    assert result("disclosure-delivery-read", root, "fiscal-year:2099").ok is False


# --- reserve-notice and reserve-restored -----------------------------------------------------------------------------------------

def loan(**more):
    return {"day": "2099-02-03", "cents": 500000, "number": "12345", "deadline": "2100-02-03", "repaidCents": 500000,
            "outstandingCents": 0, "repaidOn": "2099-08-01", "documents": {"notice": {"meeting": "2099-01-20", "id": "a"},
                                                                             "minutes": {"id": "m", "draft": False}, "resolution": None}, **more}


def with_loans(monkeypatch, *loans):
    monkeypatch.setattr("jason.tasks.reserve_transfers.review", lambda *a, **k: {"found": True, "borrowings": list(loans)})


def test_an_agenda_with_the_notice_of_intent_within_the_window_passes(tmp_path, monkeypatch):
    with_loans(monkeypatch, loan())
    res = result("reserve-notice", tmp_path / "data", "borrowing:2099-02-03-12345")
    assert res.ok and "meeting of 2099-01-20" in res.message and "minutes of that meeting are in the library" in res.message
    assert result("reserve-notice", tmp_path / "data", "borrowing", dates={"transfer_on": "2099-02-03"}).ok
    with_loans(monkeypatch, loan(documents={"notice": {"meeting": "2099-01-20"}, "minutes": {"draft": True}}))
    assert "a draft only" in result("reserve-notice", tmp_path / "data", "borrowing:2099-02-03").message
    with_loans(monkeypatch, loan(documents={"notice": {"meeting": "2099-01-20"}, "minutes": None}))
    assert "no minutes of that meeting" in result("reserve-notice", tmp_path / "data", "borrowing:2099-02-03").message


def test_a_borrowing_with_no_notice_or_no_day_or_no_ledger_fails_with_the_reason(tmp_path, monkeypatch):
    root = tmp_path / "data"
    with_loans(monkeypatch, loan(documents={"notice": None, "minutes": None, "resolution": None}))
    res = result("reserve-notice", root, "borrowing:2099-02-03")
    assert res.ok is False and "no agenda in the library gives notice of intent" in res.message
    assert "names no day" in result("reserve-notice", root, "the borrowing").message
    assert "no borrowing of 2099-03-01 among the 1" in result("reserve-notice", root, "borrowing:2099-03-01").message
    result_ = result("reserve-restored", root, "borrowing:2099-02-03")
    assert result_.ok
    monkeypatch.setattr("jason.tasks.reserve_transfers.review", lambda *a, **k: {"found": False, "note": "no ledger on disk"})
    assert "no ledger on disk" in result("reserve-notice", root, "borrowing:2099-02-03").message


def test_the_number_picks_among_borrowings_of_the_same_day(tmp_path, monkeypatch):
    with_loans(monkeypatch, loan(number="1", cents=100), loan(number="2", cents=200, repaidCents=0, outstandingCents=200, repaidOn=None))
    root = tmp_path / "data"
    assert result("reserve-restored", root, "borrowing:2099-02-03-1").ok
    assert result("reserve-restored", root, "borrowing:2099-02-03-2").ok is False


def test_a_restoration_found_by_amount_is_a_lead_and_says_whether_it_was_inside_the_year(tmp_path, monkeypatch):
    root = tmp_path / "data"
    with_loans(monkeypatch, loan())
    res = result("reserve-restored", root, "borrowing:2099-02-03")
    assert res.ok and "500000 cents were restored by 2099-08-01, inside the year that ended 2100-02-03" in res.message and "a lead" in res.message
    with_loans(monkeypatch, loan(repaidOn="2100-03-01"))
    assert "after the year" in result("reserve-restored", root, "borrowing:2099-02-03").message
    with_loans(monkeypatch, loan(repaidCents=200000, outstandingCents=300000, repaidOn=None))
    short = result("reserve-restored", root, "borrowing:2099-02-03")
    assert short.ok is False and "200000 of 500000 cents are restored; 300000 cents are not" in short.message


def test_the_reserve_reads_over_a_real_empty_ledger_say_what_to_run(tmp_path):
    res = result("reserve-notice", tmp_path / "data", "borrowing:2099-02-03", comm=bank_community(RESERVE))
    assert res.ok is False and "jason books --sync" in res.message


# --- tax-years-closed ----------------------------------------------------------------------------------------------------------------

def test_a_tax_year_with_every_balance_at_zero_is_closed_and_one_left_open_is_counted_in_cents(tmp_path):
    root = tmp_path / "data"
    tax_db(root, [(PAID, "P25", 2025, 1000, 1000, 0, ""), (DUE, "D25", 2025, 1000, 1000, 0, ""), (DUE, "D24", 2024, 1000, 0, 1000, "")])
    res = result("tax-years-closed", root, "tax-year:2025")
    assert res.ok and "2 of 2 parcel(s) have every bill of tax year 2025 at a zero balance" in res.message
    (root / "tax.db").unlink()
    tax_db(root, [(PAID, "P25", 2025, 1000, 1000, 0, ""), (DUE, "D25", 2025, 1000, 400, 600, ""), (OLD, "O25", 2025, 1000, 0, 1000, "")])
    open_ = result("tax-years-closed", root, "tax-year:2025")
    assert open_.ok is False and "1 of 3 parcel(s)" in open_.message and "2 bill(s)" in open_.message and "1600 cents in all" in open_.message
    assert "ending 0002" in open_.message and "ending 0003" in open_.message and "123-456" not in open_.message
    assert result("tax-years-closed", root, "", PAID).ok
    assert result("tax-years-closed", root, "", DUE).ok is False


def test_a_tax_year_with_no_bill_or_no_catalog_is_not_closed(tmp_path):
    root = tmp_path / "data"
    assert "jason sync-tax" in result("tax-years-closed", root).message
    assert not (root / "tax.db").exists()
    tax_db(root, [(PAID, "P25", 2025, 1000, 1000, 0, "")])
    assert "no bill for tax year 2031" in result("tax-years-closed", root, "tax-year:2031").message
    assert "no bill for that parcel" in result("tax-years-closed", root, "", "999-999-999-9999").message
    assert result("tax-years-closed", root).ok                                                     # no year named: the newest in the catalog


# --- the wired steps -----------------------------------------------------------------------------------------------------------------

def test_the_steps_that_name_these_reads_run_them_through_the_engine_readers(tmp_path):
    root = tmp_path / "data"
    ledger_rows(root, "2026-09", SEPTEMBER)
    readers = readers_of(root)
    for name, subject in (("review-income-expense", "month:2026-09"), ("review-registers", "month:2026-09")):
        step = StepDef("x.1", name, StepKind.CHECK, role=Role.JASON, check=named_check(name))
        assert readers.check(step, run_view(subject)).ok is True
    wait = StepDef("x.2", "Wait", StepKind.WAIT, role=Role.MANAGER, check=named_check("disclosure-delivery-read"))
    assert readers.arrival(wait, run_view("fiscal-year:2099")) is None
    deliveries(root, ("annual-budget-report-2099", "email", "delivered"))
    assert "1 attempt(s)" in (readers.arrival(wait, run_view("fiscal-year:2099")) or "")
    suggest = StepDef("x.3", "Read whether coverage changed", StepKind.CHECK, role=Role.JASON, check=named_check("insurance-changed"))
    decisions(root)
    assert readers.check(suggest, run_view("policy:EX-1000")).choice == "unchanged"


# --- the module's new reads touch no network, library writer, or constructor that creates a table -----------------------------

def test_no_new_read_opens_a_store_through_a_constructor_that_creates_tables():
    text = Path(reads.__file__).read_text(encoding="utf-8")
    for token in ("TaxStore(", "notice_ledger.load", "notice_ledger._db", "IndexCache(", "OwnershipStore("):
        assert token not in text, token


# --- the module itself --------------------------------------------------------------------------------------------------------

def test_the_module_imports_no_profile_and_names_no_association():
    import ast

    text = Path(reads.__file__).read_text(encoding="utf-8")
    assert "mystique" not in text.lower() and "jason.web" not in text
    tree_ = ast.parse(text)
    defined = [n.name for n in ast.walk(tree_) if isinstance(n, ast.FunctionDef)]
    assert len(defined) == len(set(defined))


def test_amounts_in_a_message_are_integer_cents_and_no_check_reports_a_balance_or_a_name(tmp_path):
    root = tmp_path / "data"
    reconciliations(root, rec("Operating", "2026-09-30", open_payments=[{"date": "2026-09-20", "amount": 1234, "description": "Check 9"}]))
    res = result("review-reconciliations", root, "month:2026-09")
    assert "1234 cents" in res.message and "$" not in res.message
    finance(root)
    assert "$" not in result("review-budget", root, "month:2026-09").message
    assert isinstance(datetime.fromisoformat(STAMP), datetime)
