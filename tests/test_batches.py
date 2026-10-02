"""Bulk writes, slowly: the ledger, rate limits, unknown outcomes checked before a resend, and resuming."""

import random

import httpx
import pytest

from jason import batches
from jason.batches import ItemStatus, Pace
from payhoa.exceptions import PayhoaApiError, PayhoaAuthError


@pytest.fixture(autouse=True)
def _locks(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_LOCK_DIR", str(tmp_path / "locks"))


class Fake:
    """Sends by script: a list of outcomes per key (an exception to raise, or None to succeed); remembers what reached
    the server (``landed``), which ``verify`` reads, as PayHOA's log would."""

    def __init__(self, script=None, verify=None):
        self.script, self.calls, self.landed, self.verify_answer = dict(script or {}), [], set(), verify

    def send(self, item, checkpoint, step):
        self.calls.append(item.key)
        outcome = (self.script.get(item.key) or [None]).pop(0) if self.script.get(item.key) else None
        if isinstance(outcome, tuple):                       # it reached the server, then the reply was lost
            self.landed.add(item.key)
            raise outcome[1]
        if outcome is not None:
            raise outcome
        checkpoint(fileId=7)
        step()
        self.landed.add(item.key)
        return {"ok": True}

    def verify(self, item):
        if self.verify_answer is not None:
            return self.verify_answer
        return item.key in self.landed


def _make(tmp_path, n=3):
    batches.create(tmp_path, "b1", "test", "Test", [(f"k{i}", f"item {i}", {"i": i}) for i in range(n)],
                   confirmed_by="Justin")


def _status(tmp_path):
    return {i.key: i.status for i in batches.items(tmp_path, "b1")}


def _run(tmp_path, handler, **kw):
    waits = []
    kw.setdefault("pace", Pace(interval=1, jitter=0, step=0, backoff=5))
    counts = batches.run(tmp_path, "b1", handler, sleep=waits.append, say=lambda s: None, rng=random.Random(0), **kw)
    return counts, waits


def test_items_go_one_at_a_time_with_a_pause_and_a_rerun_sends_nothing_twice(tmp_path):
    _make(tmp_path)
    fake = Fake()
    counts, waits = _run(tmp_path, fake)
    assert counts == {"sent": 3} and fake.calls == ["k0", "k1", "k2"]
    assert waits.count(1) == 2                                         # paced between items
    assert batches.batch(tmp_path, "b1")["status"] == "done"
    assert batches.create(tmp_path, "b1", "test", "Test", [("k0", "item 0", {})], confirmed_by="Justin") == 0
    counts, _ = _run(tmp_path, fake)
    assert fake.calls == ["k0", "k1", "k2"]                            # nothing resent
    assert batches.items(tmp_path, "b1")[0].result == {"fileId": 7, "ok": True}


def test_a_rate_limit_waits_the_servers_time_and_tries_the_same_item_again(tmp_path):
    _make(tmp_path, 2)
    limited = PayhoaApiError("HTTP 429", status_code=429, retry_after=42)
    fake = Fake({"k0": [limited]})
    counts, waits = _run(tmp_path, fake)
    assert counts == {"sent": 2} and 42 in waits and fake.calls == ["k0", "k0", "k1"]
    assert batches.items(tmp_path, "b1")[0].attempts == 1              # a rate limit is not an attempt
    no_header = Fake({"k1": [PayhoaApiError("HTTP 429", status_code=429)] * 2})
    _make(tmp_path, 2)
    batches.create(tmp_path, "b1", "test", "Test", [("k9", "item 9", {})], confirmed_by="Justin")
    no_header.script = {"k9": [PayhoaApiError("HTTP 429", status_code=429)] * 2}
    _, waits = _run(tmp_path, no_header)
    assert [w for w in waits if w >= 5] == [5, 10]                     # backoff doubles


def test_a_long_rate_limit_pauses_the_batch_to_resume_later(tmp_path):
    _make(tmp_path, 2)
    fake = Fake({"k0": [PayhoaApiError("HTTP 429", status_code=429, retry_after=3600)]})
    counts, _ = _run(tmp_path, fake)
    assert counts == {"pending": 2} and batches.batch(tmp_path, "b1")["status"] == "paused"
    counts, _ = _run(tmp_path, fake)                                    # resumed
    assert counts == {"sent": 2}


def test_an_unknown_outcome_is_checked_before_anything_is_resent(tmp_path):
    _make(tmp_path, 2)
    lost = httpx.ReadTimeout("timed out")
    fake = Fake({"k0": [("landed", lost)], "k1": [httpx.ConnectError("refused")]})
    counts, _ = _run(tmp_path, fake)
    assert counts == {"sent": 2}
    assert fake.calls == ["k0", "k1", "k1"]                            # k0 verified sent; k1 had not landed: sent again
    cannot_tell = Fake({"k2": [httpx.ReadTimeout("timed out")]}, verify=None)
    cannot_tell.verify = lambda item: None
    batches.create(tmp_path, "b1", "test", "Test", [("k2", "item 2", {})], confirmed_by="Justin")
    counts, _ = _run(tmp_path, cannot_tell)
    assert counts["uncertain"] == 1 and cannot_tell.calls == ["k2"]    # never resent blind
    batches.resolve(tmp_path, "b1", "k2", sent=True)
    assert _status(tmp_path)["k2"] is ItemStatus.SENT


def test_a_crash_mid_send_is_recovered_by_checking_payhoa(tmp_path):
    _make(tmp_path, 2)

    class Crash(Fake):
        def send(self, item, checkpoint, step):
            self.calls.append(item.key)
            self.landed.add(item.key)
            raise KeyboardInterrupt

    counts, _ = _run(tmp_path, Crash())
    assert counts == {"pending": 1, "sending": 1} and batches.batch(tmp_path, "b1")["status"] == "paused"
    after = Fake()
    after.landed = {"k0"}                                              # PayHOA's log shows it went out
    counts, _ = _run(tmp_path, after)
    assert counts == {"sent": 2} and after.calls == ["k1"]


def test_rejections_fail_the_item_and_a_streak_pauses_the_batch(tmp_path):
    _make(tmp_path, 4)
    bad = PayhoaApiError("HTTP 422", status_code=422)
    counts, _ = _run(tmp_path, Fake({"k0": [bad], "k1": [bad]}), pace=Pace(interval=0, jitter=0, max_failures=2))
    assert counts == {"failed": 2, "pending": 2} and batches.batch(tmp_path, "b1")["status"] == "paused"
    assert batches.retry_failed(tmp_path, "b1") == 2
    counts, _ = _run(tmp_path, Fake())
    assert counts == {"sent": 4}


def test_a_refused_session_pauses_without_spending_the_item(tmp_path):
    _make(tmp_path, 2)
    counts, _ = _run(tmp_path, Fake({"k0": [PayhoaAuthError("HTTP 401")]}))
    assert counts == {"pending": 2} and batches.items(tmp_path, "b1")[0].attempts == 0


def test_a_limit_stops_after_the_first_few_and_cancel_skips_the_rest(tmp_path):
    _make(tmp_path, 3)
    counts, _ = _run(tmp_path, Fake(), limit=1)
    assert counts == {"sent": 1, "pending": 2}
    batches.cancel(tmp_path, "b1")
    assert batches.batch(tmp_path, "b1")["counts"] == {"sent": 1, "skipped": 2}
    with pytest.raises(ValueError):
        batches.create(tmp_path, "b2", "test", "Test", [], confirmed_by="")


def test_the_run_cools_down_when_payhoa_says_few_requests_are_left(tmp_path):
    _make(tmp_path, 2)
    left = iter([500, 12])
    counts, waits = _run(tmp_path, Fake(), pace=Pace(interval=1, jitter=0, step=0, headroom=50, cooldown=60),
                         remaining=lambda: next(left))
    assert counts == {"sent": 2} and 60 in waits
