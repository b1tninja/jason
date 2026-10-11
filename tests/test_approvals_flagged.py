"""Flagged items: an item held for the board by jason's policy finding is a flag for review, decided only as a one-off
exception (docs/held-items.md).

Example Village (tests/test_approvals.py): four fake owners on a fake PayHOA client. Its plan has two flagged items, the
unit-1 occupancy tags the response policy holds (finding ``occupancy-vs-tag``). Nothing here reaches PayHOA. The engine
refuses a flagged item without the exception flag; with it and a reason it records the exception, makes the item high
stakes (a second, distinct person signs), keeps an append-only log, and applies exactly the approved item's write.
"""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
import webclient

from jason.approvals import audit, engine, exceptions, model, store
from jason.approvals.engine import Refused
from jason.approvals.model import ApprovalStatus as S
from jason.approvals.model import Decision, ItemClass, Result
from jason.web.app import create_app
from test_approvals import _by, _validator, village  # noqa: F401 - fixtures

BY, SECOND = "A Manager", "B Director"
WHY = "the owner confirmed in writing that the unit is owner-occupied"


def _plan(village):
    return engine.plan("owner-info-tags", village.live, by=BY)


def _flagged(a):
    """The two flagged items: the Rental tag's removal and Owner Occupied's addition, both on unit 1."""
    return {i.value: i for i in _by(a, ItemClass.HELD_FOR_BOARD)}


def _exception(village, a, item, decision=Decision.APPROVED, reason=WHY, by=BY):
    return engine.decide(a.id, [item.id], by=by, decision=decision, reason=reason, exception=True,
                         data_dir=village.data_dir)


def _reject_the_rest(village, a, by=BY):
    """Every approvable item rejected, so a flagged exception is all a plan approves."""
    return engine.decide(a.id, "all", by=by, decision=Decision.REJECTED, reason="not in this plan",
                         data_dir=village.data_dir)


def _log_text(village):
    return exceptions.path(village.data_dir).read_text(encoding="utf-8")


# --- decide -------------------------------------------------------------------------------------------------------------

def test_a_flagged_item_is_refused_without_the_exception_flag_and_the_message_says_how(village):
    a = _plan(village)
    held = _flagged(a)["Rental"]
    assert held.klass is ItemClass.HELD_FOR_BOARD and held.board_item == "rental-approvals-4-15"
    with pytest.raises(Refused) as err:
        engine.decide(a.id, [held.id], by=BY, reason=WHY, data_dir=village.data_dir)
    assert "held for the board (board item rental-approvals-4-15)" in str(err.value)
    assert "exception flag" in str(err.value) and "reason" in str(err.value)
    after = store.load(a.id, village.data_dir)
    assert after.status is S.PLANNED and not after.item(held.id).exception           # nothing changed
    assert not exceptions.path(village.data_dir).exists()


def test_an_exception_is_approved_with_a_reason_in_words_and_is_high_stakes_with_a_second_signature(village):
    a = _plan(village)
    held = _flagged(a)["Owner Occupied"]
    with pytest.raises(Refused, match="in words"):
        _exception(village, a, held, reason="ok")
    with pytest.raises(Refused, match="in words"):
        _exception(village, a, held, reason="  ")
    with pytest.raises(Refused, match="says why"):
        _exception(village, a, held, decision=Decision.REJECTED, reason="")
    assert engine.needs_second(store.load(a.id, village.data_dir), data_dir=village.data_dir) is False
    after = _exception(village, a, held)
    i = after.item(held.id)
    assert (i.decision, i.exception, i.high_stakes, i.decided_by, i.reason) == (Decision.APPROVED, True, True, BY, WHY)
    assert after.status is S.IN_REVIEW and [x.id for x in after.approved] == [held.id]
    assert engine.needs_second(after, data_dir=village.data_dir) is True            # the existing rule: no new path
    assert after.decisions[-1].items == (held.id,) and after.decisions[-1].decision is Decision.APPROVED
    assert [e["event"] for e in audit.read(village.data_dir, a.id)][-1] == "item.decided"
    assert "one-off exception" in audit.read(village.data_dir, a.id)[-1]["detail"]


def test_an_exception_rejected_or_kept_flagged_is_not_high_stakes_and_is_never_written(village):
    a = _plan(village)
    held = _flagged(a)
    _exception(village, a, held["Rental"], decision=Decision.REJECTED, reason="the owner's answer was a mistake")
    after = _exception(village, a, held["Owner Occupied"], decision=Decision.HELD, reason="wait for the board's rule")
    assert after.item(held["Rental"].id).decision is Decision.REJECTED and after.approved == []
    assert after.item(held["Owner Occupied"].id).decision is Decision.HELD
    assert not any(i.high_stakes for i in after.items) and engine.needs_second(after, data_dir=village.data_dir) is False
    assert all(i.exception and i.klass is ItemClass.HELD_FOR_BOARD for i in after.flagged)   # still flagged
    # approved, then rejected on a second look: the high-stakes mark goes with the approval
    approved = _exception(village, a, held["Rental"])
    assert approved.item(held["Rental"].id).high_stakes is True
    again = _exception(village, a, held["Rental"], decision=Decision.REJECTED, reason="looked again, not needed")
    assert again.item(held["Rental"].id).high_stakes is False and again.approved == []


def test_every_other_class_stays_never_approvable_even_with_the_exception_flag(village):
    a = _plan(village)
    for klass in (ItemClass.FOR_A_PERSON, ItemClass.INFORMATIONAL):
        item = _by(a, klass)[0]
        with pytest.raises(Refused, match="never approvable"):
            engine.decide(a.id, [item.id], by=BY, reason=WHY, data_dir=village.data_dir)
        with pytest.raises(Refused, match="not flagged for review"):
            _exception(village, a, item)
    approvable = a.approvable[0]                                           # and the flag is not a way round the rules
    with pytest.raises(Refused, match="not flagged for review"):
        _exception(village, a, approvable)
    with pytest.raises(Refused, match="not flagged for review"):             # one wrong item refuses the whole decision
        engine.decide(a.id, [approvable.id, _flagged(a)["Rental"].id], by=BY, reason=WHY, exception=True,
                      data_dir=village.data_dir)
    assert store.load(a.id, village.data_dir).status is S.PLANNED


def test_all_never_includes_a_flagged_item(village):
    a = _plan(village)
    after = engine.decide(a.id, "all", by=BY, data_dir=village.data_dir)
    assert {i.id for i in after.approved} == {i.id for i in a.approvable}
    assert all(i.decision is Decision.UNDECIDED and not i.exception for i in after.flagged)
    with pytest.raises(Refused, match="never includes"):
        engine.decide(a.id, "all", by=BY, reason=WHY, exception=True, data_dir=village.data_dir)
    with pytest.raises(Refused, match="never includes"):
        engine.decide(a.id, ["all"], by=BY, reason=WHY, exception=True, data_dir=village.data_dir)


def test_a_flagged_item_left_undecided_does_not_hold_up_a_signature(village):
    a = _plan(village)
    engine.decide(a.id, "all", by=BY, data_dir=village.data_dir)
    signed = engine.submit(a.id, by=BY, data_dir=village.data_dir)
    assert signed.status is S.APPROVED                                     # the flag is not part of the ordinary approval
    assert all(i.decision is Decision.UNDECIDED for i in signed.flagged)


# --- the exceptions log -------------------------------------------------------------------------------------------------

def test_the_log_is_appended_to_and_a_later_fact_is_a_later_line(village):
    a = _plan(village)
    held = _flagged(a)["Owner Occupied"]
    _exception(village, a, held)
    first = _log_text(village).splitlines()
    assert len(first) == 1
    line = json.loads(first[0])
    assert {"at", "event", "approval", "item", "finding", "boardItem", "by", "secondBy", "decision", "reason",
            "applied"} <= set(line)
    assert (line["event"], line["approval"], line["item"], line["finding"], line["boardItem"]) == (
        "decided", a.id, held.id, "owner_responses.RULES: occupancy-vs-tag", "rental-approvals-4-15")
    assert (line["by"], line["secondBy"], line["decision"], line["reason"], line["applied"]) == (
        BY, "", "approved", WHY, False)
    _reject_the_rest(village, a)
    engine.submit(a.id, by=BY, data_dir=village.data_dir)
    engine.confirm(a.id, by=SECOND, data_dir=village.data_dir)
    engine.apply(a.id, village.live, by=BY)
    text = _log_text(village).splitlines()
    assert text[0] == first[0]                                              # the first line is exactly as written
    assert [json.loads(t)["event"] for t in text] == ["decided", "second", "applied"]
    folded = exceptions.for_finding("owner_responses.RULES: occupancy-vs-tag", village.data_dir)
    assert len(folded) == 1 and (folded[0]["secondBy"], folded[0]["applied"], folded[0]["decision"]) == (
        SECOND, True, "approved")


def test_a_decision_that_is_never_applied_stays_applied_false(village):
    a = _plan(village)
    _exception(village, a, _flagged(a)["Rental"])
    engine.withdraw(a.id, by=BY, reason="planned again instead", data_dir=village.data_dir)
    (row,) = exceptions.rows(village.data_dir)
    assert row["applied"] is False and row["secondBy"] == ""


def test_the_log_masks_contact_details_in_a_reason(village):
    a = _plan(village)
    _exception(village, a, _flagged(a)["Rental"], reason="the owner wrote from ana@example.org and 916-555-0100")
    text = _log_text(village)
    assert "ana@example.org" not in text and "555-0100" not in text and "[email]" in text


def test_the_nudge_comes_at_the_threshold_and_counts_only_exceptions_approved(village):
    finding = "owner_responses.RULES: occupancy-vs-tag"
    assert exceptions.EXCEPTION_NUDGE == 2
    a = _plan(village)
    held = _flagged(a)
    _exception(village, a, held["Rental"])
    assert exceptions.counts(village.data_dir) == {finding: 1} and exceptions.nudge(finding, village.data_dir) is False
    _exception(village, a, held["Owner Occupied"], decision=Decision.REJECTED, reason="not this one, the owner moved")
    assert exceptions.count(finding, village.data_dir) == 1                 # a rejection is history, not an exception
    assert len(exceptions.for_finding(finding, village.data_dir)) == 2
    _exception(village, a, held["Owner Occupied"])
    assert exceptions.count(finding, village.data_dir) == 2 and exceptions.nudge(finding, village.data_dir) is True
    again = _exception(village, a, held["Rental"], decision=Decision.REJECTED, reason="looked again, not needed")
    assert again is not None and exceptions.count(finding, village.data_dir) == 1      # the latest decision counts


# --- refer ----------------------------------------------------------------------------------------------------------------

def test_refer_makes_the_board_item_and_proposes_it_and_decides_nothing(village):
    from jason.community.board_items import ItemStatus
    from jason.tasks import board_items

    a = _plan(village)
    held = _flagged(a)["Rental"]
    assert board_items.load(village.data_dir) == []
    after, found = engine.refer(a.id, held.id[:8], by=BY, data_dir=village.data_dir)
    assert found.id == "rental-approvals-4-15"
    (stored,) = board_items.load(village.data_dir)
    assert stored.id == found.id and stored.status is ItemStatus.PROPOSED
    assert any(a.id in e for e in stored.evidence) and "ana example" not in (stored.summary + stored.title).lower()
    assert all(i.decision is Decision.UNDECIDED and not i.exception for i in after.items)       # nothing decided
    assert store.load(a.id, village.data_dir).status is S.PLANNED
    assert village.client.writes == []
    last = audit.read(village.data_dir, a.id)[-1]
    assert last["event"] == "item.referred" and last["actor"] == BY and "rental-approvals-4-15" in last["detail"]
    again, same = engine.refer(a.id, held.id, by="B Director", data_dir=village.data_dir)         # refreshed, not copied
    assert same.id == found.id and len(board_items.load(village.data_dir)) == 1
    _validator("audit-entry.schema.json").validate(last)


def test_refer_names_a_board_item_from_the_finding_when_the_item_has_none(village):
    from jason.tasks import board_items

    a = _plan(village)
    held = _flagged(a)["Rental"]
    stored = store.load(a.id, village.data_dir)
    for i in stored.flagged:
        i.board_item = ""
    store.save(stored, village.data_dir)
    after, found = engine.refer(a.id, held.id, by=BY, data_dir=village.data_dir)
    assert found.id == "flagged-owner-responses-rules-occupancy-vs-tag"
    assert {i.board_item for i in after.flagged} == {found.id}                                     # the plan now names it
    assert [b.id for b in board_items.load(village.data_dir)] == [found.id]


def test_refer_is_for_a_flagged_item_and_a_named_person(village):
    a = _plan(village)
    with pytest.raises(Refused, match="not flagged"):
        engine.refer(a.id, a.approvable[0].id, by=BY, data_dir=village.data_dir)
    with pytest.raises(Refused, match="names the person"):
        engine.refer(a.id, _flagged(a)["Rental"].id, by=" ", data_dir=village.data_dir)


# --- the plan JSON --------------------------------------------------------------------------------------------------------

def test_a_stored_plan_without_the_new_field_loads_and_the_json_stays_the_same(village):
    a = _plan(village)
    doc = model.to_dict(a)
    assert all("exception" not in row for row in doc["items"])                  # absent when false: the old shape
    old = json.loads(json.dumps(doc))
    loaded = model.from_dict(old)
    assert all(i.exception is False for i in loaded.items) and model.to_dict(loaded) == doc
    _validator("approval.schema.json").validate(doc)
    decided = _exception(village, a, _flagged(a)["Rental"])
    doc = model.to_dict(decided)
    row = next(r for r in doc["items"] if r.get("exception") is True)
    assert row["class"] == "held_for_board" and row["decision"] == "approved" and row["highStakes"] is True
    _validator("approval.schema.json").validate(doc)
    assert model.from_dict(doc) == decided


def test_the_schema_refuses_a_decided_flagged_item_that_does_not_say_it_was_an_exception(village):
    a = _plan(village)
    doc = model.to_dict(_exception(village, a, _flagged(a)["Rental"]))
    row = next(r for r in doc["items"] if r.get("exception"))
    del row["exception"]
    jsonschema = pytest.importorskip("jsonschema")
    with pytest.raises(jsonschema.ValidationError):
        _validator("approval.schema.json").validate(doc)


def test_the_counts_say_how_many_are_flagged_and_decided_by_exception(village):
    a = _plan(village)
    assert engine.counts(a)["flaggedCount"] == 2 and engine.counts(a)["decidedByException"] == 0
    after = _exception(village, a, _flagged(a)["Rental"])
    assert engine.counts(after)["decidedByException"] == 1


# --- apply: exactly the approved write, and nothing unapproved -------------------------------------------------------------

def test_an_approved_flagged_item_applies_exactly_its_write_and_an_unapproved_one_is_never_applied(village):
    a = _plan(village)
    held = _flagged(a)
    _exception(village, a, held["Owner Occupied"])
    _exception(village, a, held["Rental"], decision=Decision.HELD, reason="keep this one flagged for the board")
    _reject_the_rest(village, a)
    signed = engine.submit(a.id, by=BY, data_dir=village.data_dir)
    assert signed.status is S.PARTIALLY_APPROVED
    with pytest.raises(Refused, match="second, distinct person"):             # the existing rule binds an exception
        engine.apply(a.id, village.live, by=BY)
    with pytest.raises(Refused, match="submitted it"):
        engine.confirm(a.id, by=BY, data_dir=village.data_dir)
    engine.confirm(a.id, by=SECOND, data_dir=village.data_dir)
    done = engine.apply(a.id, village.live, by=BY)
    assert done.superseded_by is None and done.approval.status is S.APPLIED
    assert village.client.writes == [("unit +", (1,), "Owner Occupied")]       # exactly the approved write; nothing else
    stored = store.load(a.id, village.data_dir)
    assert stored.item(held["Owner Occupied"].id).result is Result.APPLIED
    kept = stored.item(held["Rental"].id)
    assert kept.result is Result.NOT_APPLIED and "held by" in kept.result_detail and "keep this one" in kept.result_detail
    assert all(i.result is Result.NOT_APPLIED for i in stored.items if i not in stored.approved)


def test_a_flagged_item_nobody_decided_is_never_written_whatever_else_is_approved(village):
    a = _plan(village)
    engine.decide(a.id, "all", by=BY, data_dir=village.data_dir)
    engine.submit(a.id, by=BY, data_dir=village.data_dir)
    engine.apply(a.id, village.live, by=BY)
    assert not any(w[0].startswith("unit") for w in village.client.writes)
    stored = store.load(a.id, village.data_dir)
    assert all(i.result is Result.NOT_APPLIED and i.result_detail == "held for board" for i in stored.flagged)


def test_the_planner_keeps_the_write_of_a_flagged_item_for_the_applier(village):
    planned = engine.registry.get("owner-info-tags").plan(village.live, {})
    ctx = planned.context
    flagged = [i for i in planned.items if i.klass is ItemClass.HELD_FOR_BOARD]
    assert len(flagged) == 2 and all(i.id in ctx.writes for i in flagged)
    assert {(ctx.writes[i.id].kind, ctx.writes[i.id].value) for i in flagged} == {
        ("unit tag -", "Rental"), ("unit tag +", "Owner Occupied")}


def test_a_flagged_item_whose_basis_moved_since_review_is_void_and_replanned(village):
    a = _plan(village)
    held = _flagged(a)["Owner Occupied"]
    _exception(village, a, held)
    _reject_the_rest(village, a)
    engine.submit(a.id, by=BY, data_dir=village.data_dir)
    engine.confirm(a.id, by=SECOND, data_dir=village.data_dir)
    village.client.units[0]["tags"] = [{"tag": "Rental"}, {"tag": "Vacant"}]     # someone changed the unit in PayHOA
    done = engine.apply(a.id, village.live, by=BY)
    assert done.superseded_by is not None and village.client.writes == []
    assert [c.id for c in done.changed] == [held.id] and "relies on changed" in done.changed[0].why
    fresh = done.superseded_by
    assert fresh.item(held.id).decision is Decision.UNDECIDED and not fresh.item(held.id).exception
    (row,) = exceptions.rows(village.data_dir)
    assert row["applied"] is False                                                  # it stays in the log, not applied


# --- controls bind an exception as any approved item -----------------------------------------------------------------------

def test_a_control_the_board_adopted_binds_an_exception_like_any_approved_item(village, monkeypatch):
    from controls_support import FULL
    from jason.community.base import OfficerRole as R
    from jason.controls import effective
    from test_controls_engine import DIR_A, DIR_B, TREAS, adopt

    monkeypatch.setenv("JASON_SPEC_DIR", str(village.data_dir / "spec"))
    monkeypatch.setattr(effective, "_community_roster", lambda: FULL)
    adopt(village.data_dir, "owner-info-tags", {"signers": 2, "must_include": [R.TREASURER.value]})
    a = _plan(village)
    _exception(village, a, _flagged(a)["Owner Occupied"], by=DIR_A)
    _reject_the_rest(village, a, by=DIR_A)
    signed = engine.submit(a.id, by=DIR_A, data_dir=village.data_dir)          # the first signer need not be the treasurer
    assert signed.status is S.PARTIALLY_APPROVED
    with pytest.raises(Refused, match="requires the treasurer among the signers"):
        engine.confirm(a.id, by=DIR_B, data_dir=village.data_dir)
    assert store.load(a.id, village.data_dir).second is None
    engine.confirm(a.id, by=TREAS, data_dir=village.data_dir)
    assert engine.apply(a.id, village.live, by=BY).approval.status is S.APPLIED
    assert village.client.writes == [("unit +", (1,), "Owner Occupied")]


# --- the console's routes ------------------------------------------------------------------------------------------------------

def _dist(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "index.html").write_text("<!doctype html><html><head><title>t</title></head><body></body></html>",
                                     encoding="utf-8")
    return dist


@pytest.fixture
def web(village, monkeypatch):
    """The app over Example Village with sign-in set up over the made-up roster (a manager, officers, an admin)."""
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: village.data_dir / "letters")

    @contextmanager
    def factory(kind):
        yield village.live

    village.app = create_app(_dist(village.data_dir), None, approvals_live=factory,
                             sign_in=webclient.roster_sign_in())
    return village


def _signed_in(web, name):
    return webclient.sign_in(webclient.client(web.app), name)


def _decide(c, a, item, **extra):
    return c.post(f"/api/approvals/{a.id}/decide", json={"items": [item.id], "decision": "approved", "reason": WHY,
                                                         "exception": True, **extra})


def test_the_decide_route_takes_an_exception_from_a_signed_in_office_only(web):
    a = _plan(web)
    held = _flagged(a)["Owner Occupied"]
    out = webclient.client(web.app)
    assert _decide(out, a, held).status_code == 401                              # signed out
    assert _decide(_signed_in(web, "Ada Admin"), a, held).status_code == 403     # an administrator holds no office
    assert store.load(a.id).status is S.PLANNED and not exceptions.path(web.data_dir).exists()
    r = _decide(_signed_in(web, "Dana Director"), a, held)
    assert r.status_code == 200, r.json
    row = next(i for i in r.json["items"] if i["id"] == held.id)
    assert (row["decision"], row["exception"], row["highStakes"], row["decidedBy"]) == (
        "approved", True, True, "Dana Director")                                  # the signed-in name, not the body's
    from jason.web.signin import VIA

    assert r.json["decisions"][-1]["via"] == VIA
    assert row["exceptionCount"] == 1 and [e["by"] for e in row["exceptions"]] == ["Dana Director"]
    assert r.json["flagged"] == {"flagged": 2, "decidedByException": 1, "nudge": exceptions.EXCEPTION_NUDGE}
    other = _signed_in(web, "A Manager")                                          # the manager may too
    assert _decide(other, a, _flagged(a)["Rental"]).status_code == 200
    # the body's name must be the signed-in person's
    assert _signed_in(web, "Sam Secretary").post(
        f"/api/approvals/{a.id}/decide", json={"items": [held.id], "decision": "approved", "reason": WHY,
                                               "exception": True, "by": "Someone Else"}).status_code == 403


def test_an_exception_over_the_web_is_refused_in_the_engines_words(web):
    a = _plan(web)
    held = _flagged(a)["Owner Occupied"]
    c = _signed_in(web, "A Manager")
    r = c.post(f"/api/approvals/{a.id}/decide", json={"items": [held.id], "decision": "approved", "reason": "ok",
                                                      "exception": True})
    assert r.status_code == 400 and "in words" in r.json["error"]
    r = c.post(f"/api/approvals/{a.id}/decide", json={"items": [held.id], "decision": "approved", "reason": WHY})
    assert r.status_code == 400 and "exception flag" in r.json["error"]             # no flag: still refused
    r = c.post(f"/api/approvals/{a.id}/decide", json={"items": [held.id], "decision": "approved", "reason": WHY,
                                                      "exception": "yes"})
    assert r.status_code == 400                                                       # only the boolean true is the flag
    assert store.load(a.id).status is S.PLANNED


def test_an_admin_viewing_as_someone_else_cannot_decide_an_exception(village, monkeypatch):
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: village.data_dir / "letters")

    @contextmanager
    def factory(kind):
        yield village.live

    app = create_app(_dist(village.data_dir), None, approvals_live=factory,
                     sign_in=webclient.roster_sign_in(dev=True))
    a = _plan(village)
    c = webclient.sign_in(webclient.client(app), "Ada Admin")
    assert c.post("/auth/act-as", json={"role": "director"}).status_code == 200
    r = _decide(c, a, _flagged(a)["Rental"])
    assert r.status_code == 403 and "writes are refused" in r.json["error"]
    assert not exceptions.path(village.data_dir).exists()


def test_the_show_route_carries_the_exceptions_under_each_flagged_finding(web):
    a = _plan(web)
    held = _flagged(a)
    _exception(web, a, held["Rental"], by="Dana Director")
    r = webclient.client(web.app).get(f"/api/approvals/{a.id}")
    assert r.status_code == 200
    rows = {i["id"]: i for i in r.json["items"]}
    assert rows[held["Owner Occupied"].id]["exceptionCount"] == 1                    # the same finding
    assert rows[held["Owner Occupied"].id]["exceptions"][0]["decision"] == "approved"
    assert all("exceptions" not in i for i in r.json["items"] if i["class"] != "held_for_board")
    assert r.json["flagged"]["decidedByException"] == 1
    _validator("approval.schema.json").validate({k: v for k, v in r.json.items()
                                                 if k not in ("kindFacts", "needsSecond", "recitations", "waitingToApply",
                                                              "waitingHours", "signedAt", "waitingStale", "terminalOnly", "reminderDue", "reminderHours", "pausing", "pauseEndsAt", "applyPrefs", "applyHold", "typedCount", "serverNow")})
    listed = _signed_in(web, "A Manager").get("/api/approvals").json["approvals"][0]
    assert listed["flaggedCount"] == 2 and listed["decidedByException"] == 1


def test_the_refer_route_puts_the_finding_before_the_board_and_decides_nothing(web):
    from jason.tasks import board_items

    a = _plan(web)
    held = _flagged(a)["Rental"]
    path = f"/api/approvals/{a.id}/refer"
    assert webclient.client(web.app).post(path, json={"item": held.id}).status_code == 401
    assert _signed_in(web, "Ada Admin").post(path, json={"item": held.id}).status_code == 403
    assert _signed_in(web, "A Manager").post(path, json={}).status_code == 400
    r = _signed_in(web, "Lee President").post(path, json={"item": held.id})
    assert r.status_code == 200, r.json
    assert r.json["boardItem"] == "rental-approvals-4-15" and r.json["status"] == "planned"
    assert [b.id for b in board_items.load(web.data_dir)] == ["rental-approvals-4-15"]
    assert audit.read(web.data_dir, a.id)[-1]["actor"] == "Lee President"
    assert all(i["decision"] == "undecided" for i in r.json["items"])
    r = _signed_in(web, "A Manager").post(path, json={"item": a.approvable[0].id})
    assert r.status_code == 400 and "not flagged" in r.json["error"]


# --- the CLI ---------------------------------------------------------------------------------------------------------------------

def _cli(village, monkeypatch, capsys, *argv):
    """``jason approvals ...`` through its own parser (the full CLI's builds the profile's choices), data in tmp."""
    import argparse

    from jason.commands.approvals import register

    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: village.data_dir)
    parser = argparse.ArgumentParser()
    register(parser.add_subparsers(), lambda p: None, lambda args: None)
    args = parser.parse_args(["approvals", *argv])
    code = args.func(args)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_the_cli_decides_an_exception_shows_the_flag_and_lists_the_log(village, monkeypatch, capsys):
    a = _plan(village)
    held = _flagged(a)["Owner Occupied"]
    code, _, err = _cli(village, monkeypatch, capsys, "decide", a.id, "--item", held.id[:10], "--reason", WHY,
                        "--by", BY)
    assert code == 2 and "exception flag" in err                                    # without --exception: refused
    code, out, _ = _cli(village, monkeypatch, capsys, "decide", a.id, "--item", held.id[:10], "--exception",
                        "--reason", WHY, "--by", BY)
    assert code == 0 and "One-off decision, not a rule." in out and "second, distinct person" in out
    code, out, _ = _cli(village, monkeypatch, capsys, "show", a.id)
    assert "Flagged for review" in out and "FLAGGED, decided by exception" in out
    assert "exceptions under owner_responses.RULES: occupancy-vs-tag: 1 decision(s), 1 approved" in out
    assert WHY in out
    code, out, _ = _cli(village, monkeypatch, capsys, "exceptions")
    assert code == 0 and "1 approved by exception" in out and f"by {BY}" in out
    _exception(village, a, _flagged(a)["Rental"])
    code, out, _ = _cli(village, monkeypatch, capsys, "exceptions", "--finding", "owner_responses.RULES: occupancy-vs-tag")
    assert "decided by exception 2 times. The board may want to write a rule" in out
    code, out, _ = _cli(village, monkeypatch, capsys, "exceptions", "--json")
    assert json.loads(out)["nudge"] == 2 and len(json.loads(out)["exceptions"]) == 2
    code, out, _ = _cli(village, monkeypatch, capsys, "refer", a.id, "--item", held.id[:10], "--by", BY)
    assert code == 0 and "rental-approvals-4-15" in out and "nothing was decided" in out


def test_the_cli_refuses_all_with_the_exception_flag(village, monkeypatch, capsys):
    a = _plan(village)
    code, _, err = _cli(village, monkeypatch, capsys, "decide", a.id, "--all", "--exception", "--reason", WHY,
                        "--by", BY)
    assert code == 2 and "never includes" in err
