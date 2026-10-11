"""The board's apply preferences through jason-web (``jason.controls.apply_prefs``; docs/console/approval-clarity.md, section 5).

The server's ``--allow-apply`` is still required, and the console's button is the board's choice besides: a terminal is the
default, the real owner-information and Mailroom kinds never reach the console, and a pause, who may apply, and a typed count
are refused by the engine in its own words before any sign-in. Example Village (tests/test_approvals.py) on a fake PayHOA."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
import webclient

from controls_support import adopt_preference
from jason.approvals import registry, store
from jason.approvals.model import ApprovalStatus as S
from test_approvals import village  # noqa: F401 - fixture
from test_web_approvals import _apply_on, _plan, _post, _review, web  # noqa: F401 - fixtures


def _signed(web):
    a = _plan(web)
    _review(web, a)
    return store.load(a.id)


def _long_ago(web, a, minutes):
    """The plan signed ``minutes`` ago (the stored signature moved back in time)."""
    a = store.load(a.id)
    a.first = replace(a.first, at=(datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(timespec="seconds"))
    store.save(a, web.data_dir)


def _apply(c, a, **body):
    return _post(c, a.id, "apply", by="A Manager", confirm=a.fingerprint, **body)


def test_the_console_does_not_apply_until_the_board_adopts_a_button_even_when_the_server_allows_it(web):
    from jason.web.app import create_app
    from test_web_approvals import _dist

    a = _signed(web)
    c = webclient.client(create_app(_dist(web.data_dir), None, approvals_live=web.factory, allow_apply=True))
    r = _apply(c, a)
    assert r.status_code == 403 and r.json["consoleRefused"] is True and "apply is at a terminal" in r.json["error"]
    assert "jason approvals apply ID --yes --by NAME" in r.json["error"]
    assert web.client.writes == [] and web.factory.calls == [] and store.load(a.id).status is S.PARTIALLY_APPROVED


def test_with_a_console_button_adopted_the_server_flag_is_still_required(web):
    a = _signed(web)
    adopt_preference(web.data_dir, "where-apply", {"where": "console"})
    registry.register(replace(registry.get("owner-info-tags"), sends=""))
    r = _apply(web.c, a)                                                      # the server was started without --allow-apply
    assert r.status_code == 403 and "--allow-apply" in r.json["error"]
    assert web.client.writes == []


def test_the_real_owner_information_kind_never_reaches_the_console_whatever_the_board_adopts(web):
    from jason.web.app import create_app
    from test_web_approvals import _dist

    a = _signed(web)
    adopt_preference(web.data_dir, "where-apply", {"where": "console"})
    c = webclient.client(create_app(_dist(web.data_dir), None, approvals_live=web.factory, allow_apply=True))
    r = _apply(c, a)
    assert r.status_code == 403 and r.json["consoleRefused"] is True
    assert "the board chose the console, but the console never applies this kind" in r.json["error"]
    assert "sends something" in r.json["error"]
    assert web.client.writes == [] and web.factory.calls == []
    shown = web.c.get(f"/api/approvals/{a.id}").json["applyPrefs"]
    assert shown["where"] == "terminal" and shown["consoleAllowed"] is False and shown["consoleFloored"] is True


def test_a_pause_is_refused_before_any_sign_in_and_the_plan_can_be_withdrawn_meanwhile(web):
    a = _signed(web)
    c = _apply_on(web)
    adopt_preference(web.data_dir, "pause-before-apply", {"minutes": 30})
    r = _apply(c, a)
    assert r.status_code == 400 and "a pause before apply is in force" in r.json["error"]
    assert web.client.writes == [] and web.factory.calls == []                 # refused before the live context was built
    shown = web.c.get(f"/api/approvals/{a.id}").json
    hold = shown["applyHold"]
    assert 0 < hold["secondsLeft"] <= 1800 and hold["endsAt"].endswith("+00:00") and "withdrawn" in hold["words"]
    assert shown["applyPrefs"]["pauseMinutes"] == 30
    listed = web.c.get("/api/approvals").json["approvals"][0]
    assert listed["pausing"] is True and listed["pauseEndsAt"] == hold["endsAt"]
    _long_ago(web, a, 31)
    assert web.c.get(f"/api/approvals/{a.id}").json["applyHold"] is None
    assert _apply(c, a).status_code == 200


def test_withdraw_during_the_pause_writes_nothing(web):
    a = _signed(web)
    adopt_preference(web.data_dir, "pause-before-apply", {"minutes": 30})
    r = _post(web.c, a.id, "withdraw", by="A Manager", reason="a mistake seen in the pause")
    assert r.status_code == 200 and r.json["status"] == "withdrawn" and web.client.writes == []


def test_who_may_apply_is_asked_of_the_person_applying(web):
    a = _signed(web)                                   # signed by A Manager
    c = _apply_on(web)
    adopt_preference(web.data_dir, "who-may-apply", {"who": "not_signer"})
    r = _apply(c, a)
    assert r.status_code == 400 and "does not let a person who signed this plan also apply it" in r.json["error"]
    assert web.client.writes == [] and web.factory.calls == []
    assert _post(c, a.id, "apply", by="B Director", confirm=a.fingerprint).status_code == 200


def test_a_typed_count_is_asked_above_the_boards_number_and_must_be_the_plans(web):
    a = _signed(web)
    c = _apply_on(web)
    changes = len(a.approved)
    adopt_preference(web.data_dir, "typed-count-over", {"over": changes - 1})
    shown = web.c.get(f"/api/approvals/{a.id}").json["typedCount"]
    assert shown == {"needed": True, "over": changes - 1, "changes": changes}
    r = _apply(c, a)
    assert r.status_code == 400 and "type the number this plan makes" in r.json["error"]
    r = _apply(c, a, count=changes + 1)
    assert r.status_code == 400 and f"{changes + 1} is not the number of changes" in r.json["error"]
    assert _apply(c, a, count="many").status_code == 400
    assert web.client.writes == [] and web.factory.calls == []
    r = _apply(c, a, count=str(changes))
    assert r.status_code == 200 and r.json["status"] == "applied"


def test_a_count_over_the_boards_number_is_not_asked_when_the_plan_is_at_or_under_it(web):
    a = _signed(web)
    c = _apply_on(web)
    adopt_preference(web.data_dir, "typed-count-over", {"over": len(a.approved)})
    assert web.c.get(f"/api/approvals/{a.id}").json["typedCount"]["needed"] is False
    assert _apply(c, a).status_code == 200


def test_the_plan_carries_the_five_settings_in_words_with_where_each_comes_from(web):
    a = _signed(web)
    adopt_preference(web.data_dir, "pause-before-apply", {"minutes": 45})
    shown = web.c.get(f"/api/approvals/{a.id}").json
    rows = {r["setting"]: r for r in shown["applyPrefs"]["rows"]}
    assert list(rows) == ["where", "who", "pause", "typed", "reminder"]
    assert rows["pause"]["source"] == "the board adopted this on 2099-01-01" and rows["where"]["default"] is True
    assert shown["serverNow"] and shown["kindFacts"]["sends"].startswith("the board's completion comment")


def test_a_waiting_row_says_when_a_reminder_is_due_and_nothing_is_sent(web):
    a = _signed(web)
    listed = web.c.get("/api/approvals").json["approvals"][0]
    assert listed["waitingToApply"] is True and listed["reminderDue"] is False and listed["reminderHours"] == 24
    _long_ago(web, a, 60 * 25)
    assert web.c.get("/api/approvals").json["approvals"][0]["reminderDue"] is True
    adopt_preference(web.data_dir, "reminder-hours", {"off": True})
    row = web.c.get("/api/approvals").json["approvals"][0]
    assert row["reminderDue"] is False and row["reminderHours"] is None
