"""Plans signed and waiting to be applied (docs/console/approval-clarity.md, section 4): ``engine.waiting_to_apply``.

Made-up kinds and plans written straight into a tmp store, so every signature and read time is chosen by the test. A
plan waits to be applied only when it is signed by everyone it needs; the clock starts at the last signature; a plan read
longer ago than its kind allows is stale (apply plans it again first); a terminal-only kind says so; and a row carries
the plan's title and counts, never an item's contents.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from jason.approvals import engine, model, registry, store
from jason.approvals.model import Approval, ApprovalStatus as S, Decision, PlanItem, Signature
from jason.locks import Resource

NOW = datetime.now(timezone.utc).replace(microsecond=0)        # real, so the attention section (which reads the clock) agrees
SECRET_VALUE = "a-distinct-value-an-owner-chose"


def _iso(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def _noop(*a, **k):                                                   # pragma: no cover - never planned or applied here
    raise AssertionError("waiting_to_apply plans and applies nothing")


@pytest.fixture(autouse=True)
def kinds():
    made = (
        registry.ActionKind("wait-one", "One person kind", "jason none", "local", Resource.STORE, registry.Risk.R1,
                            registry.Approver.ONE_PERSON, "yes", _noop, _noop),
        registry.ActionKind("wait-short", "Short-lived kind", "jason none", "local", Resource.STORE, registry.Risk.R1,
                            registry.Approver.ONE_PERSON, "yes", _noop, _noop, max_age_hours=2),
        registry.ActionKind("wait-two", "Two person kind", "jason none", "local", Resource.STORE, registry.Risk.R2,
                            registry.Approver.TWO_PERSON, "yes", _noop, _noop),
        registry.ActionKind("wait-terminal", "Terminal kind", "jason wait-terminal --send --yes", "local",
                            Resource.STORE, registry.Risk.R3, registry.Approver.ONE_PERSON, "no", _noop, _noop,
                            terminal_only=True),
    )
    for k in made:
        registry.register(k)
    yield made
    for k in made:
        registry.unregister(k.key)


def _plan(tmp_path, ident, kind="wait-one", *, status=S.APPROVED, first=None, second=None, read=1.0, title=None):
    """A stored plan: one approved item whose value is private (it must never come out of a waiting row)."""
    item = PlanItem(model.item_id(kind, "set", "member:1", SECRET_VALUE), "set", "member:1", "Owner Example",
                    SECRET_VALUE, "a test", basis="b", decision=Decision.APPROVED, decided_by="A Manager")
    a = Approval(ident, kind, title or f"Plan {ident}", [item], "fp", _iso(read), "A Manager", _iso(read))
    a.status = status
    a.first = None if first is None else Signature("A Manager", _iso(first), "fp")
    a.second = None if second is None else Signature("B Treasurer", _iso(second), "fp")
    store.save(a, tmp_path)
    return a


def _ids(tmp_path):
    return [r["id"] for r in engine.waiting_to_apply(tmp_path, NOW)]


def test_only_a_signed_plan_not_yet_applied_waits(tmp_path):
    _plan(tmp_path, "apr-20990110T000000-0001", first=3)                                  # approved: waits
    _plan(tmp_path, "apr-20990110T000000-0002", status=S.PARTIALLY_APPROVED, first=3)     # partly approved: waits
    for n, status in enumerate((S.PLANNED, S.IN_REVIEW, S.APPLYING, S.APPLIED, S.FAILED, S.SUPERSEDED, S.WITHDRAWN), 3):
        _plan(tmp_path, f"apr-20990110T000000-000{n}", status=status, first=3 if status is not S.PLANNED else None)
    assert sorted(_ids(tmp_path)) == ["apr-20990110T000000-0001", "apr-20990110T000000-0002"]


def test_a_signed_status_with_no_signature_does_not_wait(tmp_path):
    _plan(tmp_path, "apr-20990110T000000-0001", first=None)
    assert _ids(tmp_path) == []


def test_the_clock_starts_at_the_last_signature(tmp_path):
    _plan(tmp_path, "apr-20990110T000000-0001", "wait-two", first=50, second=5)
    (row,) = engine.waiting_to_apply(tmp_path, NOW)
    assert row["waitingHours"] == 5.0 and row["signedAt"] == _iso(5) and row["needsSecond"] is True
    _plan(tmp_path, "apr-20990110T000000-0002", first=30)
    rows = {r["id"]: r for r in engine.waiting_to_apply(tmp_path, NOW)}
    assert rows["apr-20990110T000000-0002"]["waitingHours"] == 30.0 and rows["apr-20990110T000000-0002"]["needsSecond"] is False


def test_a_plan_still_waiting_for_its_second_signature_waits_on_a_signature_not_an_apply(tmp_path):
    _plan(tmp_path, "apr-20990110T000000-0001", "wait-two", first=10, second=None)
    assert _ids(tmp_path) == []


def test_the_longest_waiting_comes_first(tmp_path):
    _plan(tmp_path, "apr-20990110T000000-0001", first=2)
    _plan(tmp_path, "apr-20990110T000000-0002", first=70)
    _plan(tmp_path, "apr-20990110T000000-0003", first=20)
    assert _ids(tmp_path) == ["apr-20990110T000000-0002", "apr-20990110T000000-0003", "apr-20990110T000000-0001"]


def test_stale_is_judged_against_each_kinds_own_age_limit(tmp_path):
    _plan(tmp_path, "apr-20990110T000000-0001", "wait-one", first=1, read=30)         # 24-hour kind, read 30 hours ago
    _plan(tmp_path, "apr-20990110T000000-0002", "wait-one", first=1, read=23)         # still current
    _plan(tmp_path, "apr-20990110T000000-0003", "wait-short", first=1, read=3)        # 2-hour kind, read 3 hours ago
    _plan(tmp_path, "apr-20990110T000000-0004", "wait-short", first=1, read=1)        # still current
    rows = {r["id"][-4:]: r for r in engine.waiting_to_apply(tmp_path, NOW)}
    assert {k: rows[k]["stale"] for k in rows} == {"0001": True, "0002": False, "0003": True, "0004": False}
    assert rows["0001"]["maxAgeHours"] == 24 and rows["0003"]["maxAgeHours"] == 2


def test_stale_follows_the_read_time_that_apply_judges_not_the_signature(tmp_path):
    """Signed an hour ago on a read that was 30 hours old when it was signed: apply would plan it again."""
    _plan(tmp_path, "apr-20990110T000000-0001", first=1, read=31)
    (row,) = engine.waiting_to_apply(tmp_path, NOW)
    assert row["stale"] is True and row["waitingHours"] == 1.0
    assert any("plan again" in p for p in engine.problems(store.load("apr-20990110T000000-0001", tmp_path), tmp_path))


def test_a_terminal_only_kind_says_so_and_names_its_command(tmp_path):
    _plan(tmp_path, "apr-20990110T000000-0001", "wait-terminal", first=4)
    _plan(tmp_path, "apr-20990110T000000-0002", "wait-one", first=3)
    rows = {r["id"][-4:]: r for r in engine.waiting_to_apply(tmp_path, NOW)}
    assert rows["0001"]["terminalOnly"] is True and rows["0001"]["applyCommand"] == "jason wait-terminal --send --yes"
    assert rows["0002"]["terminalOnly"] is False
    assert rows["0002"]["applyCommand"] == "jason approvals apply apr-20990110T000000-0002 --yes --by NAME"


def test_a_kind_this_checkout_no_longer_has_is_listed_not_stale(tmp_path):
    _plan(tmp_path, "apr-20990110T000000-0001", "wait-gone", first=4, read=500)
    (row,) = engine.waiting_to_apply(tmp_path, NOW)
    assert row["kind"] == "wait-gone" and row["stale"] is False and row["terminalOnly"] is False
    assert row["applyCommand"] == "" and row["maxAgeHours"] is None


def test_a_row_is_counts_and_the_title_never_an_items_contents(tmp_path):
    _plan(tmp_path, "apr-20990110T000000-0001", first=4, title="A sample plan of tag changes")
    (row,) = engine.waiting_to_apply(tmp_path, NOW)
    assert set(row) == {"id", "kind", "title", "signedAt", "waitingHours", "stale", "maxAgeHours", "needsSecond",
                        "terminalOnly", "applyCommand", "reminderHours", "reminderDue", "pausing", "pauseEndsAt"}
    assert row["title"] == "A sample plan of tag changes"
    assert SECRET_VALUE not in repr(row) and "Owner Example" not in repr(row)


def test_it_reads_the_store_and_changes_nothing(tmp_path):
    _plan(tmp_path, "apr-20990110T000000-0001", first=4)
    before = {p.name: p.read_bytes() for p in (tmp_path / "approvals").iterdir()}
    engine.waiting_to_apply(tmp_path, NOW)
    assert {p.name: p.read_bytes() for p in (tmp_path / "approvals").iterdir()} == before
    assert not (tmp_path / "approvals" / "audit.jsonl").exists()


def test_an_empty_store_waits_on_nothing(tmp_path):
    assert engine.waiting_to_apply(tmp_path, NOW) == []


@pytest.mark.parametrize("hours, said", ((0.2, "less than an hour"), (1, "1 hour"), (5.9, "5 hours"), (47, "47 hours"),
                                         (48, "2 days"), (80, "3 days")))
def test_how_long_in_words(hours, said):
    assert engine.ago(hours) == said


def test_the_console_words_for_a_waiting_plan_and_a_stale_one():
    row = {"waitingHours": 72.0, "stale": False}
    assert engine.waiting_words(row) == "signed, waiting to be applied · 3 days"
    assert engine.waiting_words({"waitingHours": 120.0, "stale": True}) == (
        "signed 5 days ago; it will be planned again before it is applied")


def test_the_attention_digest_has_an_approvals_section_with_one_line_a_plan(tmp_path):
    from jason.tasks import attention

    _plan(tmp_path, "apr-20990110T000000-0001", first=0.2)
    _plan(tmp_path, "apr-20990110T000000-0002", first=100, read=101)
    found = attention.approvals_section(tmp_path)
    assert found.key == "approvals" and found.available
    assert found.counts == {"waiting": 2, "stale": 1, "terminalOnly": 0}
    assert found.summary.startswith("2 plans signed, waiting to be applied (1 older than its kind allows")
    assert all(i.urgency is attention.Urgency.OPEN for i in found.items) and len(found.items) == 2
    assert SECRET_VALUE not in " ".join(i.text for i in found.items)
    whole = attention.digest(object(), tmp_path, on=date.today(), sections=("approvals",))
    assert whole.totals()["open"] == 2                                  # counted in the heading's "waiting on a person"
    assert attention.approvals_section(tmp_path / "none").summary == "No plan is signed and waiting to be applied."
