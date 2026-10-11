"""The approvals kind ``payhoa-attach-bills``: the attach engine's dry run as a plan, and the approved items uploaded.

Made-up transactions and bills (Example Electric, 123 Main St) in tmp_path. ``FakePayhoa`` records every upload and
fails the test if anything approves a transaction; ``FakeSource`` is a bill source whose cache, re-resolve, and PDF
fetch each test can bend. Nothing reaches PayHOA or a portal."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

import pytest

from jason.approvals import engine, registry, store
from jason.approvals.engine import Live
from jason.approvals.kinds import attach_bills as kind
from jason.approvals.model import ApprovalStatus as S
from jason.approvals.model import Decision, Result
from jason.sources.registry import BillSourceRegistry
from jason.sources.types import ResolvedBill

KEY = "payhoa-attach-bills"
DAY = date(2026, 10, 7)


class FakePayhoa:
    """Transactions with attachments; an upload adds an attachment; ``update_transaction`` is an approval and is never
    allowed."""

    def __init__(self, txs):
        self.txs = txs
        self.uploads: list[tuple[int, str]] = []
        self.updates: list[tuple] = []
        self.fail_on: set[int] = set()

    def iter_transactions(self, org_id, reviewed=False):
        yield from [t for t in self.txs if t.get("approved") is not True]

    def get_transaction(self, org_id, tx_id):
        return next(t for t in self.txs if t["id"] == tx_id)

    def upload_attachment(self, org_id, tx_id, path):
        if tx_id in self.fail_on:
            raise RuntimeError("PayHOA refused the file")
        self.uploads.append((tx_id, path.name))
        next(t for t in self.txs if t["id"] == tx_id)["attachments"].append({"id": 900 + tx_id, "deletedAt": None})
        return {"url": "x"}

    def update_transaction(self, org_id, tx_id, **kw):
        self.updates.append((tx_id, kw))
        raise AssertionError("the kind never approves a PayHOA transaction")


class FakeSource:
    name = "example-electric"

    def __init__(self, root, bills):
        self.root, self.bills = root, bills                  # bills: amount -> [ResolvedBill]
        self.resolve_as: dict[int, ResolvedBill] = {}        # amount -> what a re-resolve now gives
        self.resolves: list[int] = []

    def matches_transaction(self, tx):
        return "EXAMPLE ELECTRIC" in str(tx.get("description", "")).upper()

    def find_cached(self, need):
        return [b for b in self.bills.get(need.amount_cents, []) if abs((b.bill_date - need.around).days) <= need.window_days]

    def resolve(self, needs, *, ensure_pdfs=True):
        out = {}
        for n in needs:
            self.resolves.append(n.transaction_id)
            found = self.resolve_as.get(n.amount_cents) or next(iter(self.find_cached(n)), None)
            if found is not None:
                out[n.key] = found
        return out

    def ensure_pdf(self, bill):
        path = self.root / f"{bill.bill_id}.pdf"
        path.write_bytes(b"%PDF-1.4 fake")
        return path


def bill(root, bill_id, amount, *, pdf=True, account="123 Main St", day=DAY):
    path = root / f"{bill_id}.pdf" if pdf else None
    if path:
        path.write_bytes(b"%PDF-1.4 fake")
    return ResolvedBill("example-electric", bill_id, account, day, amount, pdf_path=path)


def tx(tx_id, amount, description="ACH EXAMPLE ELECTRIC 123 MAIN ST", attachments=()):
    return {"id": tx_id, "amount": amount, "transactionDate": "2026-10-07", "description": description,
            "approved": False, "attachments": list(attachments)}


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Five transactions: one matched (101), one matched with a PDF to fetch (102), one ambiguous (103), one with no
    bill (104), one already attached (105), and one no source owns (106)."""
    source = FakeSource(tmp_path, {
        5760: [bill(tmp_path, "E-5760", 5760)],
        8120: [bill(tmp_path, "E-8120", 8120, pdf=False)],
        3000: [bill(tmp_path, "E-3000a", 3000, account="1"), bill(tmp_path, "E-3000b", 3000, account="2")],
        7777: [bill(tmp_path, "E-7777", 7777)],
    })
    client = FakePayhoa([tx(101, 5760), tx(102, 8120), tx(103, 3000), tx(104, 4242), tx(105, 7777, attachments=[
        {"id": 5, "deletedAt": None}]), tx(106, 100, description="ACH EXAMPLE WATER")])

    @contextmanager
    def open_registry(live, names):
        yield BillSourceRegistry([source]).filter(names or None)

    monkeypatch.setattr(kind, "open_registry", open_registry)
    live = Live(client, 1, tmp_path, None, DAY)
    return SimpleNamespace(source=source, client=client, live=live, data_dir=tmp_path, root=tmp_path)


def items_of(a):
    return {i.target: i for i in a.items}


def approve(world, a, *targets, by="A Manager"):
    ids = [items_of(a)[f"transaction:{t}"].id for t in targets]
    engine.decide(a.id, ids, by=by, data_dir=world.data_dir)
    rest = [i.id for i in a.approvable if i.id not in ids]
    if rest:
        engine.decide(a.id, rest, by=by, decision=Decision.REJECTED, reason="not now", data_dir=world.data_dir)
    return engine.submit(a.id, by=by, data_dir=world.data_dir)


class Recorder:
    def __init__(self):
        self.done_calls, self.started = {}, []

    def applying(self, ids):
        self.started += list(ids)

    def done(self, ident, result, detail=""):
        self.done_calls[ident] = (result, detail)


# --- the row ------------------------------------------------------------------------------------------------------------

def test_the_kind_is_registered_with_its_alias_and_a_short_plan_life():
    k = registry.get(KEY)
    assert registry.get("payhoa.attach-bills") is k
    assert k.cli == "jason sync-bills --yes" and k.system == "payhoa" and k.max_age_hours == 6
    assert k.risk is registry.Risk.R1 and k.approver is registry.Approver.ONE_PERSON
    assert "approved" in k.reversible and k.rule == kind.RULE


def test_the_web_routes_list_it_with_no_other_wiring():
    from jason.web import approvals

    assert KEY in {k["key"] for k in approvals.kinds()["kinds"]}


# --- the plan -----------------------------------------------------------------------------------------------------------

def test_a_plan_has_an_item_for_each_matched_result_and_none_for_the_rest(world):
    a = engine.plan(KEY, world.live, by="A Manager")
    assert a.status is S.PLANNED and a.kind == KEY
    by_target = items_of(a)
    assert set(by_target) == {"transaction:101", "transaction:102"}
    one = by_target["transaction:101"]
    assert one.op == "attach bill" and one.approvable and len(one.basis) == 64 and one.rule == kind.RULE
    assert "E-5760" in one.why and "$57.60" in one.label and "on disk" in one.why
    assert "fetched from the source" in by_target["transaction:102"].why
    assert one.change.text() == "+ bill PDF (transaction attachments)"
    assert a.scope == {"sources": [], "date_window_days": 7}
    assert a.summary["matched"] == 2 and a.summary["ambiguous"] == 1 and a.summary["noMatch"] == 1
    assert a.summary["skipped"] == 1 and a.summary["matchedCents"] == 5760 + 8120 and a.summary["withPdf"] == 1
    notes = " ".join(a.notes)
    assert "transaction 103" in notes and "ambiguous" in notes and "transaction 104" in notes and "no_match" in notes
    assert "transaction 105" in notes and "skipped" in notes and "106" not in notes     # unrouted: not listed


def test_planning_is_read_only(world):
    engine.plan(KEY, world.live, by="A Manager")
    assert world.client.uploads == [] and world.client.updates == [] and world.source.resolves == []


def test_the_same_transaction_and_bill_are_the_same_item_on_every_plan(world):
    first = engine.plan(KEY, world.live, by="A Manager")
    second = engine.plan(KEY, world.live, by="A Manager")
    assert {i.id: i.basis for i in first.items} == {i.id: i.basis for i in second.items}
    assert store.load(first.id, world.data_dir).status is S.SUPERSEDED


def test_scope_narrows_to_the_named_sources(world):
    a = engine.plan(KEY, world.live, by="A Manager", scope={"sources": ["somebody-else"]})
    assert a.items == [] and a.scope["sources"] == ["somebody-else"]


# --- apply --------------------------------------------------------------------------------------------------------------

def test_apply_uploads_only_the_approved_items_and_never_approves_a_transaction(world):
    a = engine.plan(KEY, world.live, by="A Manager")
    a = approve(world, a, 101)
    assert a.status is S.PARTIALLY_APPROVED
    done = engine.apply(a.id, world.live, by="A Manager")
    assert done.superseded_by is None and done.approval.status is S.APPLIED
    assert world.client.uploads == [(101, "E-5760.pdf")] and world.client.updates == []
    stored = store.load(a.id, world.data_dir)
    assert items_of(stored)["transaction:101"].result is Result.APPLIED
    assert items_of(stored)["transaction:102"].result is Result.NOT_APPLIED


def test_a_pdf_the_source_must_fetch_is_fetched_then_uploaded(world):
    a = approve(world, engine.plan(KEY, world.live, by="A Manager"), 102, 101)
    engine.apply(a.id, world.live, by="A Manager")
    assert sorted(world.client.uploads) == [(101, "E-5760.pdf"), (102, "E-8120.pdf")]
    assert world.client.updates == []


def test_a_re_plan_after_apply_shows_the_transaction_as_skipped(world):
    a = approve(world, engine.plan(KEY, world.live, by="A Manager"), 101)
    engine.apply(a.id, world.live, by="A Manager")
    again = engine.plan(KEY, world.live, by="A Manager")
    assert set(items_of(again)) == {"transaction:102"}
    assert again.summary["skipped"] == 2 and any("transaction 101" in n and "skipped" in n for n in again.notes)


def test_a_transaction_that_gained_an_attachment_since_the_plan_is_not_uploaded(world):
    a = approve(world, engine.plan(KEY, world.live, by="A Manager"), 101)
    world.client.txs[0]["attachments"].append({"id": 7, "deletedAt": None})
    done = engine.apply(a.id, world.live, by="A Manager")
    assert done.superseded_by is not None and world.client.uploads == []      # the re-plan sees it: gone from the plan
    assert items_of(store.load(a.id, world.data_dir))["transaction:101"].result is Result.CHANGED


def test_the_applier_itself_skips_a_transaction_attached_between_its_plan_and_its_write(world):
    planned = kind.plan(world.live, {})
    world.client.txs[0]["attachments"].append({"id": 7, "deletedAt": None})
    rec = Recorder()
    kind.apply(world.live, planned, planned.items, rec)
    by_target = {i.target: rec.done_calls[i.id] for i in planned.items}
    assert by_target["transaction:101"][0] is Result.NOT_APPLIED and "attachment" in by_target["transaction:101"][1]
    assert by_target["transaction:102"][0] is Result.APPLIED
    assert world.client.uploads == [(102, "E-8120.pdf")] and world.client.updates == []


def test_a_bill_that_changed_on_re_resolve_is_an_error_not_an_upload(world):
    a = approve(world, engine.plan(KEY, world.live, by="A Manager"), 101)
    world.source.resolve_as[5760] = bill(world.root, "E-5760-REISSUED", 5760)
    done = engine.apply(a.id, world.live, by="A Manager")
    assert done.approval.status is S.FAILED and world.client.uploads == []
    item = items_of(store.load(a.id, world.data_dir))["transaction:101"]
    assert item.result is Result.FAILED and "the bill changed" in item.result_detail and "E-5760-REISSUED" in item.result_detail


def test_a_bill_whose_amount_changed_on_re_resolve_is_an_error_too(world):
    a = approve(world, engine.plan(KEY, world.live, by="A Manager"), 101)
    world.source.resolve_as[5760] = bill(world.root, "E-5760", 5761)
    engine.apply(a.id, world.live, by="A Manager")
    assert world.client.uploads == []


def test_one_items_failure_does_not_stop_the_next(world):
    a = approve(world, engine.plan(KEY, world.live, by="A Manager"), 101, 102)
    world.client.fail_on = {101}
    done = engine.apply(a.id, world.live, by="A Manager")
    assert done.approval.status is S.FAILED
    stored = items_of(store.load(a.id, world.data_dir))
    assert stored["transaction:101"].result is Result.FAILED and "PayHOA refused" in stored["transaction:101"].result_detail
    assert stored["transaction:102"].result is Result.APPLIED
    assert world.client.uploads == [(102, "E-8120.pdf")] and world.client.updates == []


def test_the_applier_attaches_for_no_item_it_was_not_given(world):
    planned = kind.plan(world.live, {})
    only = [i for i in planned.items if i.target == "transaction:102"]
    rec = Recorder()
    kind.apply(world.live, planned, only, rec)
    assert world.client.uploads == [(102, "E-8120.pdf")] and list(rec.done_calls) == [only[0].id]
    rec2 = Recorder()
    kind.apply(world.live, planned, [], rec2)
    assert rec2.done_calls == {} and len(world.client.uploads) == 1


def test_a_bill_the_source_no_longer_resolves_fails_the_item(world):
    a = approve(world, engine.plan(KEY, world.live, by="A Manager"), 101)
    world.source.resolve = lambda needs, ensure_pdfs=True: {}
    engine.apply(a.id, world.live, by="A Manager")
    item = items_of(store.load(a.id, world.data_dir))["transaction:101"]
    assert item.result is Result.FAILED and "no longer resolves" in item.result_detail and world.client.uploads == []
