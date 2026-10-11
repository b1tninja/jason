"""The money family's reads (src/jason/workflows/checks/money.py): twelve ``check`` names over made-up stores in a temporary
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
         "review-reconciliations", "review-budget", "reserve-study-due", "insurance-due", "tax-standing", "tax-bill-files")
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

def test_the_twelve_reads_are_registered_by_name_and_only_once():
    checks.load_all()
    assert set(NAMES) <= set(CHECKS)
    assert len(set(NAMES)) == 12
    before = dict(CHECKS)
    checks.load_all()
    assert CHECKS == before
    with pytest.raises(ValueError):
        checks.check("bill-handed")(lambda r, v, i="": CheckResult(True))


def test_every_read_on_an_empty_data_folder_is_not_ok_says_why_and_writes_nothing(tmp_path):
    root = tmp_path / "data"                         # the folder does not even exist
    for name in NAMES:
        res = result(name, root, "month:2026-09" if name != "payee-class-read" else "transaction:1", comm=community())
        assert res.ok is False and res.message, name
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
