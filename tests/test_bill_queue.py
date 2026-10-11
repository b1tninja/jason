"""The bill-attach queue (``jason.tasks.bill_queue``, ``jason.sources.offline``, ``jason.community.payees``): routing the
stored PayHOA snapshot offline, classing a payment no source owns, and laying the last dry run beside it only when it was
made against this snapshot. Made-up snapshot and rules in tmp_path; nothing is reached.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from jason.community.payees import PayeeClass, PayeeRule, payee_of
from jason.tasks import bill_dry_run, bill_queue

NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
STAMP = "2026-10-09T02:10:00+00:00"


class Source:
    def __init__(self, name, word):
        self.name, self._word = name, word

    def matches_transaction(self, tx):
        return self._word in str(tx.get("description") or "").upper()


class Registry:
    sources = [Source("smud", "ELECTRIC CO"), Source("idoxs", "CITY OF EXAMPLE")]

    def route(self, tx):
        return next((s for s in self.sources if s.matches_transaction(tx)), None)


TAX = PayeeRule(PayeeClass.COUNTY_TAX, description_contains=("EXAMPLE COUNTY TAX",))
COMMUNITY = SimpleNamespace(payee_rules=lambda: (TAX,))


def tx(ident, amount, desc, day="2026-10-07", **kw):
    return {"id": ident, "amount": amount, "description": desc, "transactionDate": day, "approved": False,
            "attachments": [], **kw}


def snapshot(tmp_path, txs, stamp=STAMP):
    path = tmp_path / "payhoa" / "transactions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"syncedAt": stamp,
                                "categories": {"1": {"name": "Utilities", "type": "expense"},
                                               "2": {"name": "Dues", "type": "income"}},
                                "vendors": {"9": "Example Alarm"}, "transactions": txs}), encoding="utf-8")


def rows(out):
    return {r["transactionId"]: r for r in out["rows"]}


def test_no_snapshot_says_so_and_names_the_command(tmp_path):
    out = bill_queue.build(tmp_path, COMMUNITY, Registry(), now=NOW)
    assert out["found"] is False and out["command"] == "jason invoices --fetch" and out["rows"] == []


def test_each_transaction_is_routed_offline_and_a_miss_stays_a_miss(tmp_path):
    snapshot(tmp_path, [tx(1, 6129, "ACH ELECTRIC CO"), tx(2, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR"),
                        tx(3, 41200, "ACH SOMEONE ELSE"), tx(4, 2826, "ACH CITY OF EXAMPLE")])
    r = rows(bill_queue.build(tmp_path, COMMUNITY, Registry(), now=NOW, stale_after=2))
    assert (r[1]["source"], r[1]["status"], r[1]["payeeClass"]) == ("smud", "not checked", None)
    assert (r[2]["source"], r[2]["status"], r[2]["payeeClass"]) == (None, "no source yet", "county-tax")
    assert (r[3]["source"], r[3]["status"], r[3]["payeeClass"]) == (None, "unrouted", "unknown")
    assert r[4]["source"] == "idoxs"


def test_approved_attached_deleted_child_and_income_lines_are_not_waiting(tmp_path):
    snapshot(tmp_path, [tx(1, 100, "ACH ELECTRIC CO", approved=True), tx(2, 200, "ACH ELECTRIC CO", deletedAt="x"),
                        tx(3, 300, "ACH ELECTRIC CO", parentId=9), tx(4, 400, "DUES", categoryId=2),
                        tx(5, 500, "ACH ELECTRIC CO", attachments=[{"id": 1}]),
                        tx(6, 600, "ACH ELECTRIC CO", attachments=[{"id": 2, "deletedAt": "x"}])])
    out = bill_queue.build(tmp_path, COMMUNITY, Registry(), now=NOW)
    r = rows(out)
    assert set(r) == {5, 6} and r[5]["status"] == "already attached" and r[6]["status"] == "not checked"
    assert out["withoutPdf"] == 1 and out["sourcesNeeded"] == ["smud"]


def test_the_snapshots_age_is_judged_against_its_sources_own_limit(tmp_path):
    snapshot(tmp_path, [tx(1, 100, "ACH ELECTRIC CO")])
    old = bill_queue.build(tmp_path, COMMUNITY, Registry(), now=datetime(2026, 10, 14, tzinfo=timezone.utc), stale_after=2)
    assert old["snapshot"]["stale"] is True and old["snapshot"]["ageDays"] > 4
    fresh = bill_queue.build(tmp_path, COMMUNITY, Registry(), now=NOW, stale_after=2)
    assert fresh["snapshot"]["stale"] is False
    assert bill_queue.stale_after_days() == 2          # the PayHOA transactions source's own default


def report(results, pending=(), unrouted=()):
    return SimpleNamespace(sources_needed=["smud"], pending=list(pending), unrouted=list(unrouted),
                           upload=SimpleNamespace(results=results))


def result(ident, status, detail=""):
    bill = SimpleNamespace(bill_id="b1", source="smud", bill_date=date(2026, 10, 5), has_pdf=True)
    return SimpleNamespace(transaction_id=ident, amount_cents=6129, transaction_date=date(2026, 10, 7), status=status,
                           detail=detail, bill=bill if status == "matched" else None)


def test_a_dry_run_made_against_this_snapshot_speaks_for_its_rows(tmp_path):
    snapshot(tmp_path, [tx(1, 6129, "ACH ELECTRIC CO"), tx(2, 7000, "ACH ELECTRIC CO")])
    bill_dry_run.record(tmp_path, report([result(1, "matched"), result(2, "no_match", "no bill")]), window_days=7,
                        by="Pat Example")
    out = bill_queue.build(tmp_path, COMMUNITY, Registry(), now=NOW)
    r = rows(out)
    assert r[1]["status"] == "matched" and r[1]["dryRun"]["bill"]["id"] == "b1" and r[2]["status"] == "no match"
    assert out["dryRun"]["currentWithSnapshot"] is True and out["dryRun"]["by"] == "Pat Example"


def test_a_dry_run_older_than_the_snapshot_is_kept_beside_not_applied(tmp_path):
    snapshot(tmp_path, [tx(1, 6129, "ACH ELECTRIC CO")], stamp="2026-10-01T00:00:00+00:00")
    bill_dry_run.record(tmp_path, report([result(1, "matched")]), window_days=7)
    snapshot(tmp_path, [tx(1, 6129, "ACH ELECTRIC CO")], stamp=STAMP)       # fetched again after the run
    out = bill_queue.build(tmp_path, COMMUNITY, Registry(), now=NOW)
    r = rows(out)[1]
    assert r["status"] == "not checked" and r["dryRun"] is None and r["earlier"]["status"] == "matched"
    assert out["dryRun"]["currentWithSnapshot"] is False


def test_a_dry_run_records_names_amounts_and_ids_only(tmp_path):
    snapshot(tmp_path, [tx(1, 6129, "ACH ELECTRIC CO")])
    path = bill_dry_run.record(tmp_path, report([result(1, "matched")]), window_days=7)
    kept = json.loads(path.read_text(encoding="utf-8"))
    assert kept["snapshotSyncedAt"] == STAMP and kept["results"][0]["bill"] == {
        "id": "b1", "source": "smud", "date": "2026-10-05", "hasPdf": True}
    assert bill_dry_run.load(tmp_path)["windowDays"] == 7


# --- the payee rows ----------------------------------------------------------------------------------------------------

def test_a_payee_row_needs_something_to_match_and_unknown_is_what_no_row_selects():
    with pytest.raises(ValueError, match="needs something to match"):
        PayeeRule(PayeeClass.INSURANCE)
    with pytest.raises(ValueError, match="UNKNOWN"):
        PayeeRule(PayeeClass.UNKNOWN, description_contains=("X",))
    assert payee_of({"description": "ACH nothing"}, (TAX,)) is PayeeClass.UNKNOWN
    assert payee_of({"description": "ach example county tax x"}, (TAX,)) is PayeeClass.COUNTY_TAX
    cat = PayeeRule(PayeeClass.INSURANCE, category_id=7)
    assert payee_of({"description": "x", "categoryId": 7}, (TAX, cat)) is PayeeClass.INSURANCE


def test_an_offline_registry_routes_without_a_store_or_a_client():
    from jason.sources.offline import routing_registry

    c = SimpleNamespace(vendor_portals=lambda: ())
    reg = routing_registry(c, None, "x")
    assert [s.name for s in reg.sources] == ["smud", "idoxs"]
    with pytest.raises(AttributeError):
        reg.sources[0].find_cached(SimpleNamespace(amount_cents=1, around=date(2026, 1, 1), window_days=7))


# --- the route ---------------------------------------------------------------------------------------------------------

def test_the_route_needs_a_sign_in_reads_only_disk_and_filters(tmp_path, monkeypatch):
    import webclient

    from jason.web.app import create_app

    snapshot(tmp_path, [tx(1, 6129, "ACH ELECTRIC CO"), tx(3, 41200, "ACH SOMEONE ELSE")])
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: tmp_path)
    from jason.community import TransactionRule, Utility

    rules = (TransactionRule(Utility.SMUD, None, description_contains=("ELECTRIC CO",)),)
    monkeypatch.setattr("jason.community.community",
                        lambda: SimpleNamespace(payee_rules=lambda: (), vendor_portals=lambda: (), transaction_rules=lambda: rules))
    dist = tmp_path / "dist"
    dist.mkdir()
    app = create_app(dist, {"bill-attach": __import__("jason.web.extra.bill_attach", fromlist=["x"]).bill_attach},
                     approvals_live=None, extra_writes=False, sign_in=webclient.roster_sign_in(dev=True))
    assert webclient.client(app).get("/api/bill-attach").status_code == 401
    assert webclient.sign_in(webclient.client(app), "Pat Example").get("/api/bill-attach?view=owner").status_code == 403
    c = webclient.sign_in(webclient.client(app), "Pat Example")
    resp = c.get("/api/bill-attach")
    assert resp.status_code == 200, resp.json
    out = resp.json
    assert out["found"] is True and {r["status"] for r in out["rows"]} == {"not checked", "unrouted"}
    assert [r["transactionId"] for r in c.get("/api/bill-attach?status=unrouted").json["rows"]] == [3]
    assert [r["transactionId"] for r in c.get("/api/bill-attach?source=smud").json["rows"]] == [1]


def test_it_is_registered_and_no_owner_source():
    from jason.web.extra.owner_view import OWNER_SOURCES
    from jason.web.sources import EXTRA_LOADERS, EXTRA_WRITERS

    assert "bill-attach" not in OWNER_SOURCES and "bill-attach" not in EXTRA_WRITERS
    assert EXTRA_LOADERS["bill-attach"] == "jason.web.extra.bill_attach:bill_attach"


# --- the command -------------------------------------------------------------------------------------------------------

def test_a_dry_run_command_prints_the_unrouted_and_keeps_the_run(tmp_path, monkeypatch, capsys):
    import argparse
    from contextlib import contextmanager

    from jason import cli
    from jason.tasks.sync_bills import PendingUtilityTx, SyncBillsReport, UnroutedTx

    snapshot(tmp_path, [tx(1, 6129, "ACH ELECTRIC CO")])
    rep = SyncBillsReport(
        pending=[PendingUtilityTx(1, 6129, date(2026, 10, 7), "ELECTRIC", "smud")],
        unrouted=[UnroutedTx(3, 41200, date(2026, 10, 5), "ACH SOMEONE\nELSE", "unknown")],
        sources_needed=["smud"], upload=SimpleNamespace(results=[result(1, "matched")], summary=lambda: "1 transactions"),
        skipped_reason="dry-run (portal sync skipped)")
    agent = SimpleNamespace(sync_bills=lambda **kw: rep, settings=SimpleNamespace(payhoa_catalog=tmp_path / "catalog.json"))

    @contextmanager
    def fake_agent(args):
        yield agent

    monkeypatch.setattr(cli, "_agent", fake_agent)
    args = argparse.Namespace(verbose=False, source=None, date_window_days=7, dry_run=True, yes=False, approve=False, skip_sync=False, env=None)
    assert cli.cmd_sync_bills(args) == 0
    out = capsys.readouterr().out
    assert "Not routed to a bill source" in out and "[unknown] tx=3" in out and "ACH SOMEONE ELSE" in out
    assert "last-dry-run.json" in out and bill_dry_run.load(tmp_path)["unrouted"][0]["transactionId"] == 3


def test_a_transfer_a_bank_item_and_a_platform_fee_expect_no_bill(tmp_path):
    rules = (PayeeRule(PayeeClass.TRANSFER, description_contains=("ONLINE TRANSFER",)),
             PayeeRule(PayeeClass.BANK_ITEM, description_contains=("INTEREST ADDED",)),
             PayeeRule(PayeeClass.PLATFORM_FEE, description_contains=("PLATFORM FEE",)),
             PayeeRule(PayeeClass.INSURANCE, description_contains=("EXAMPLE INSURANCE",)))
    snapshot(tmp_path, [tx(1, 1, "ONLINE TRANSFER FROM CHK"), tx(2, 2, "INTEREST ADDED"), tx(3, 3, "ACH PLATFORM FEE"),
                        tx(4, 4, "ACH EXAMPLE INSURANCE"), tx(5, 5, "ACH UNKNOWN CO")])
    out = bill_queue.build(tmp_path, SimpleNamespace(payee_rules=lambda: rules), Registry(), now=NOW)
    assert {k: v["status"] for k, v in rows(out).items()} == {
        1: "no bill expected", 2: "no bill expected", 3: "no bill expected", 4: "no source yet", 5: "unrouted"}
    assert [c for c in PayeeClass if not c.expects_bill] == [PayeeClass.PLATFORM_FEE, PayeeClass.TRANSFER, PayeeClass.BANK_ITEM]


def test_the_profiles_payee_rows_build_and_classify_a_bank_line():
    from mystique.payees import PAYEE_RULES

    assert payee_of({"description": "Online Transfer from CHK ...1234"}, PAYEE_RULES) is PayeeClass.TRANSFER
    assert payee_of({"description": "something no row names"}, PAYEE_RULES) is PayeeClass.UNKNOWN


def _run_command(tmp_path, monkeypatch, **flags):
    import argparse
    from contextlib import contextmanager

    from jason import cli
    from jason.tasks.sync_bills import SyncBillsReport

    calls = []
    rep = SyncBillsReport(upload=SimpleNamespace(results=[], summary=lambda: "0 transactions"))
    agent = SimpleNamespace(sync_bills=lambda **kw: calls.append(kw) or rep,
                            settings=SimpleNamespace(payhoa_catalog=tmp_path / "catalog.json"))

    @contextmanager
    def fake_agent(args):
        yield agent

    monkeypatch.setattr(cli, "_agent", fake_agent)
    base = dict(verbose=False, source=None, date_window_days=7, dry_run=False, yes=False, approve=False, skip_sync=False, env=None)
    return cli.cmd_sync_bills(argparse.Namespace(**{**base, **flags})), calls


def test_sync_bills_without_yes_is_the_dry_run_and_says_what_adds_the_upload(tmp_path, monkeypatch, capsys):
    code, calls = _run_command(tmp_path, monkeypatch)
    out = capsys.readouterr().out
    assert code == 0 and calls[0]["dry_run"] is True
    assert "nothing was synced or uploaded" in out and "add --yes" in out and "last-dry-run.json" in out
    assert bill_dry_run.load(tmp_path) is not None                              # the run is kept for the console


def test_sync_bills_with_yes_syncs_and_uploads_and_keeps_no_dry_run(tmp_path, monkeypatch, capsys):
    code, calls = _run_command(tmp_path, monkeypatch, yes=True)
    assert code == 0 and calls[0]["dry_run"] is False and bill_dry_run.load(tmp_path) is None
    assert "nothing was synced" not in capsys.readouterr().out


def test_an_explicit_dry_run_with_yes_is_still_a_dry_run(tmp_path, monkeypatch):
    code, calls = _run_command(tmp_path, monkeypatch, dry_run=True, yes=True)
    assert code == 0 and calls[0]["dry_run"] is True


def test_approve_goes_with_yes(tmp_path, monkeypatch, capsys):
    code, calls = _run_command(tmp_path, monkeypatch, approve=True)
    assert code == 2 and calls == [] and "goes with --yes" in capsys.readouterr().err
