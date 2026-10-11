"""Apply preferences (docs/console/approval-clarity.md, section 5; ``jason.controls.apply_prefs``): where apply happens, who may
apply, a pause after the last signature, a typed count over some number of changes, and a reminder for a signed plan.

Opt-in and board-adopted like a control (the act log, an effective date, a history); the defaults hold until one is adopted;
the floors hold whatever is adopted (the console never applies a kind that is terminal-only, costs money, or sends mail;
a preference never touches a signature count or a control). Made-up kinds, a made-up roster, and 2099 dates."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from controls_support import FULL, LONG_AGO, adopt_preference, make
from jason.approvals import engine, model, registry, store as approvals
from jason.approvals.engine import Live, Planned, Refused
from jason.approvals.model import ApprovalStatus as S
from jason.approvals.model import PlanItem, Result, Signature
from jason.community.base import OfficerRole as R
from jason.controls import apply_prefs, catalog, effective, store
from jason.controls.types import Basis, ControlAct, ControlFamily, ControlRefused, GovernsKind, ParamKind, Scope, ScopeKind
from jason.locks import Resource

PRESIDENT, SECRETARY, TREASURER, DIRECTOR, OTHER_DIRECTOR = (o.name for o in FULL)
STRANGER = "Nobody Onroster"
EVERYONE = (PRESIDENT, SECRETARY, TREASURER, DIRECTOR, OTHER_DIRECTOR)


def _plan(live, scope):
    n = int(scope.get("n", 1))
    items = [PlanItem(model.item_id("fake", "tag +", f"member:{i}", "x"), "tag +", f"member:{i}", f"member {i}", "x",
                      "a test", basis=model.digest(f"b{i}")) for i in range(n)]
    return Planned(items, scope=dict(scope))


def _apply(live, planned, items, recorder):
    for i in items:
        recorder.applying([i.id])
        recorder.done(i.id, Result.APPLIED, "written")


def _kind(key, **kw) -> registry.ActionKind:
    return registry.register(registry.ActionKind(key, key, kw.pop("cli", "none"), "fake", Resource.STORE, registry.Risk.R2,
                                                 kw.pop("approver", registry.Approver.ONE_PERSON), "yes", _plan, _apply, **kw))


@pytest.fixture
def kinds():
    made = {"plain": _kind("fake-plain"), "other": _kind("fake-other"), "cost": _kind("fake-cost", cost="made up"),
            "sends": _kind("fake-sends", sends="a made-up email"),
            "terminal": _kind("fake-terminal", terminal_only=True, cli="jason fake --send --yes"),
            "two": _kind("fake-two", approver=registry.Approver.TWO_PERSON)}
    yield made
    for k in made.values():
        registry.unregister(k.key)


@pytest.fixture
def world(tmp_path, monkeypatch, kinds):
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    monkeypatch.setattr(effective, "_community_roster", lambda: FULL)
    return tmp_path


def adopt(world, type_key, params, *, key=None, scope=None, day: date = LONG_AGO):
    adopt_preference(world, type_key, params, key=key, scope=scope, day=day)


def signed(world, kind_key="fake-plain", n=1, by=PRESIDENT, minutes_ago: float | None = None):
    """A plan decided and signed by ``by`` (and confirmed by a second person where the kind needs one)."""
    live = Live(None, 1, world)
    a = engine.plan(kind_key, live, by=by, scope={"n": n})
    engine.decide(a.id, "all", by=by, data_dir=world)
    a = engine.submit(a.id, by=by, data_dir=world)
    if engine.needs_second(a, data_dir=world):
        a = engine.confirm(a.id, by=SECRETARY, data_dir=world)
    if minutes_ago is not None:
        then = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat(timespec="seconds")
        a.first = replace(a.first, at=then)
        a.second = replace(a.second, at=then) if a.second is not None else None
        approvals.save(a, world)
    return live, a


# --- the catalog -----------------------------------------------------------------------------------------------------------

def test_five_preferences_are_catalog_rows_in_their_own_family_and_are_not_safeguards():
    assert [t.key for t in catalog.PREFERENCES] == ["where-apply", "who-may-apply", "pause-before-apply", "typed-count-over",
                                                    "reminder-hours"]
    assert not {t.key for t in catalog.PREFERENCES} & {t.key for t in catalog.CATALOG}
    for t in catalog.PREFERENCES:
        assert t.family is ControlFamily.APPLYING and t.governs_apply and not t.governs_approvals
        assert [g.kind for g in t.governs] == [GovernsKind.APPLY] and t.sources and t.parameters
        assert catalog.get(t.key) is t
    assert catalog.get("typed-count-over").spec("over").kind is ParamKind.CEILING


def test_the_choices_are_symbols_the_catalog_lists_weakest_first():
    assert catalog.get("where-apply").spec("where").options == apply_prefs.WHERE == ("console", "terminal")
    assert catalog.get("who-may-apply").spec("who").options == apply_prefs.WHO
    assert apply_prefs.Who.CLASH.value not in apply_prefs.WHO                  # a result, never a choice
    p = apply_prefs.ApplyPrefs("k")
    assert p.where is apply_prefs.Where.TERMINAL and p.who is apply_prefs.Who.BOARD_OR_MANAGER


def test_the_ceiling_is_stricter_when_lower_and_allows_zero():
    spec = catalog.get("typed-count-over").spec("over")
    assert stricter_of(spec, 10, 3) == 3 and stricter_of(spec, None, 3) == 3
    from jason.controls.types import normalize

    assert normalize(spec, 0) == 0
    for bad in (-1, True, "3", 100001):
        with pytest.raises(ControlRefused):
            normalize(spec, bad)
    with pytest.raises(ControlRefused):
        normalize(catalog.get("reminder-hours").spec("hours"), 0)           # a reminder is at least an hour


def stricter_of(spec, a, b):
    from jason.controls.types import stricter

    return stricter(spec, a, b)


def test_a_preference_is_adopted_through_the_same_lifecycle_with_a_history(world):
    adopt(world, "pause-before-apply", {"minutes": 30})
    (c,) = [c for c in store.load(world) if c.key == "pause-before-apply"]
    assert c.state.value == "adopted" and c.parameters == {"minutes": 30} and c.decision == "dec-1"
    assert [h.act.value for h in c.history] == ["suggest", "propose", "adopt"]
    assert store.verify(world)[0]


# --- the defaults hold until a preference is adopted ---------------------------------------------------------------------

def test_the_defaults_hold_and_nothing_is_read_when_no_control_is_configured(world, monkeypatch):
    monkeypatch.setattr(store, "load", lambda *a, **k: (_ for _ in ()).throw(AssertionError("controls were read")))
    p = apply_prefs.effective("fake-plain", data_dir=world)
    assert (p.where, p.who, p.pause_minutes, p.pause_until_next_day, p.typed_count_over, p.reminder_hours) == (
        "terminal", "board_or_manager", 0, False, None, 24)
    assert not p.pausing and not p.who_adopted and not p.sources


def test_the_default_rows_say_so_in_words(world):
    got = {r["setting"]: r for r in apply_prefs.rows(apply_prefs.effective("fake-plain", data_dir=world))}
    assert set(got) == {"where", "who", "pause", "typed", "reminder"}
    assert all(r["default"] and r["source"].startswith("the default") for r in got.values())
    assert "terminal" in got["where"]["words"] and "Any board member or the manager" in got["who"]["words"]
    assert "No pause" in got["pause"]["words"] and "No typed count" in got["typed"]["words"]
    assert "24 hours" in got["reminder"]["words"] and "nothing is sent" in got["reminder"]["words"]


def test_a_signed_plan_applies_under_the_defaults_by_any_named_person(world):
    live, a = signed(world)
    assert engine.problems(a, world) == [] and engine.apply_refusals(a, by=STRANGER, data_dir=world) == []
    assert engine.apply(a.id, live, by=STRANGER, data_dir=world).approval.status is S.APPLIED


# --- the floors ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("key, words", (("terminal", "terminal"), ("cost", "costs money"), ("sends", "sends something")))
def test_a_console_choice_scoped_to_a_floored_kind_is_refused_when_adopted_with_the_reason(world, kinds, key, words):
    with pytest.raises(ControlRefused) as err:
        adopt(world, "where-apply", {"where": "console"}, scope=Scope(ScopeKind.KIND, kinds[key].key))
    assert "whatever a board prefers" in str(err.value) and words in str(err.value)
    assert not store.acts_path(world).is_file() or all(r["act"] != "adopt" for r in store.acts(world))


def test_a_console_choice_for_all_binds_only_the_kinds_the_floors_allow(world, kinds):
    adopt(world, "where-apply", {"where": "console"})
    assert apply_prefs.effective("fake-plain", data_dir=world).where == "console"
    assert apply_prefs.effective("fake-other", data_dir=world).where == "console"
    for key, why in (("terminal", "terminal"), ("cost", "costs money"), ("sends", "sends something")):
        p = apply_prefs.effective(kinds[key], data_dir=world)
        assert p.where == "terminal" and why in p.floored
        assert why in apply_prefs.where_refusal(p, kinds[key])


def test_the_real_mailroom_and_owner_information_kinds_never_reach_the_console(world):
    adopt(world, "where-apply", {"where": "console"})
    adopt(world, "where-apply", {"where": "console"}, key="where-apply--family-payhoa",
          scope=Scope(ScopeKind.FAMILY, "payhoa"))
    mail = apply_prefs.effective("payhoa-mailroom-send", data_dir=world)
    info = apply_prefs.effective("owner-info-tags", data_dir=world)
    assert mail.where == "terminal" and "terminal" in mail.floored
    assert info.where == "terminal" and "sends something" in info.floored          # a completion comment is emailed
    assert apply_prefs.effective("payhoa-attach-bills", data_dir=world).where == "console"
    assert apply_prefs.effective("gmail-drafts", data_dir=world).where == "console"


def test_a_hand_edited_facts_file_cannot_pass_the_floors(world, kinds, tmp_path):
    row = {"key": "where-apply", "type": "where-apply", "parameters": {"where": "console"}, "scope": {"kind": "all"},
           "basis": {"citation": "x"}, "state": "adopted", "decision": "dec-1", "effective": "2020-01-01", "history": []}
    spec = tmp_path / "spec"
    spec.mkdir(exist_ok=True)
    (spec / "alpha").mkdir(exist_ok=True)
    (spec / "alpha" / "controls.json").write_text(json.dumps({"controls": [row]}), encoding="utf-8")
    controls = store.seed("alpha")
    assert apply_prefs.resolve(kinds["terminal"], controls, date.today()).where == "terminal"
    assert apply_prefs.resolve(kinds["plain"], controls, date.today()).where == "console"
    scoped = [{**row, "scope": {"kind": "kind", "value": kinds["terminal"].key}}]
    (spec / "alpha" / "controls.json").write_text(json.dumps({"controls": scoped}), encoding="utf-8")
    with pytest.raises(ControlRefused, match="whatever a board prefers"):
        store.seed("alpha")


def test_a_preference_never_lowers_a_signature_count_or_removes_a_control(world, kinds):
    adopt(world, "payment-signers", {"signers": 2}, key="pay",
          scope=Scope(ScopeKind.KIND, "fake-plain"))
    before = effective.effective_approver("fake-plain", controls=store.load(world), roster=FULL)
    for t, params in (("where-apply", {"where": "console"}), ("who-may-apply", {"who": "any_signer"}),
                      ("pause-before-apply", {"minutes": 5}), ("typed-count-over", {"over": 0}),
                      ("reminder-hours", {"off": True})):
        adopt(world, t, params)
    after = effective.effective_approver("fake-plain", controls=store.load(world), roster=FULL)
    assert (after.second_always, after.roles, after.must_include, [c.key for c in after.controls]) == (
        before.second_always, before.roles, before.must_include, [c.key for c in before.controls])
    live, a = signed(world, "fake-plain", by=TREASURER)
    assert a.second is not None and engine.needs_second(a, data_dir=world)               # still needs the second signer
    assert [p for p in engine.problems(a, world) if "pause" not in p] == []
    assert effective.requires_second("fake-two", {}, controls=store.load(world), roster=FULL) is True


def test_the_preferences_are_not_consulted_by_the_signer_checks(world):
    adopt(world, "who-may-apply", {"who": "not_signer"})
    live, a = signed(world)
    assert engine.signer_refusals(a, [PRESIDENT], final=True, data_dir=world) == []


def test_no_automatic_apply_exists_as_a_row_a_parameter_or_a_flag():
    names = {t.key for t in (*catalog.CATALOG, *catalog.PREFERENCES)} | {p.key for t in catalog.PREFERENCES for p in t.parameters}
    assert not [n for n in names if "auto" in n]


# --- the effective date and the stricter of two ------------------------------------------------------------------------------

def test_a_preference_binds_from_its_effective_date_and_not_before(world, kinds):
    adopt(world, "pause-before-apply", {"minutes": 60}, day=date(2099, 6, 1))
    before = apply_prefs.effective("fake-plain", data_dir=world, today=date(2099, 5, 31))
    on = apply_prefs.effective("fake-plain", data_dir=world, today=date(2099, 6, 1))
    assert before.pause_minutes == 0 and before.waiting and before.waiting[0][0] == "pause-before-apply"
    assert "not in force until 2099-06-01" in before.waiting[0][2]
    assert on.pause_minutes == 60 and on.sources["pause-before-apply"] == ("pause-before-apply",) and not on.waiting
    assert on.adopted["pause-before-apply"] == "2099-01-01"


def test_a_preference_that_is_proposed_declined_or_retired_binds_nothing(world):
    control = make("pause-before-apply", key="p", basis=Basis("x"))
    store.record(ControlAct.SUGGEST, "p", by="jason", why="a test", control=control, data_dir=world)
    assert apply_prefs.effective("fake-plain", data_dir=world).pause_minutes == 0
    store.record(ControlAct.PROPOSE, "p", by="A Person", why="a test", data_dir=world)
    assert apply_prefs.effective("fake-plain", data_dir=world).pause_minutes == 0


def test_the_stricter_of_two_preferences_governs_in_each_respect(world, kinds):
    adopt(world, "where-apply", {"where": "console"})
    adopt(world, "where-apply", {"where": "terminal"}, key="where-one", scope=Scope(ScopeKind.KIND, "fake-plain"))
    adopt(world, "pause-before-apply", {"minutes": 10, "until_next_day": False})
    adopt(world, "pause-before-apply", {"minutes": 90}, key="pause-one", scope=Scope(ScopeKind.KIND, "fake-plain"))
    adopt(world, "typed-count-over", {"over": 20})
    adopt(world, "typed-count-over", {"over": 5}, key="typed-one", scope=Scope(ScopeKind.FAMILY, "fake"))
    adopt(world, "reminder-hours", {"hours": 48})
    adopt(world, "reminder-hours", {"hours": 6}, key="remind-one", scope=Scope(ScopeKind.KIND, "fake-plain"))
    mine = apply_prefs.effective("fake-plain", data_dir=world)
    other = apply_prefs.effective("fake-other", data_dir=world)
    assert (mine.where, mine.pause_minutes, mine.typed_count_over, mine.reminder_hours) == ("terminal", 90, 5, 6)
    assert (other.where, other.pause_minutes, other.typed_count_over, other.reminder_hours) == ("console", 10, 5, 48)
    assert set(mine.sources["pause-before-apply"]) == {"pause-before-apply", "pause-one"}


def test_no_reminder_holds_only_when_no_other_preference_asks_for_one(world):
    adopt(world, "reminder-hours", {"off": True})
    assert apply_prefs.effective("fake-plain", data_dir=world).reminder_hours is None
    adopt(world, "reminder-hours", {"hours": 12}, key="remind-12")
    assert apply_prefs.effective("fake-plain", data_dir=world).reminder_hours == 12


def test_a_reminder_is_off_or_after_some_hours_not_both(world):
    with pytest.raises(ControlRefused, match="either off or due after some hours"):
        adopt(world, "reminder-hours", {"off": True, "hours": 5})


def test_an_adoption_must_name_its_value(world):
    for t in catalog.PREFERENCES:
        with pytest.raises(ControlRefused, match="an adoption names"):
            adopt(world, t.key, {}, key=f"empty-{t.key}")


def test_a_preference_names_a_kind_or_a_family_never_an_account(world):
    with pytest.raises(ControlRefused, match="not an account"):
        adopt(world, "pause-before-apply", {"minutes": 5}, scope=Scope(ScopeKind.ACCOUNT, "acct"))
    with pytest.raises(ControlRefused, match="no action kind nope"):
        adopt(world, "pause-before-apply", {"minutes": 5}, scope=Scope(ScopeKind.KIND, "nope"))


# --- the pause --------------------------------------------------------------------------------------------------------------

def test_a_pause_refuses_an_apply_until_it_has_elapsed_and_the_plan_can_be_withdrawn(world):
    adopt(world, "pause-before-apply", {"minutes": 30})
    live, a = signed(world, minutes_ago=5)
    (why,) = engine.problems(a, world)
    assert "a pause before apply is in force" in why and "the board adopted it on 2099-01-01" in why and "withdrawn" in why
    with pytest.raises(Refused, match="pause before apply"):
        engine.apply(a.id, live, by=PRESIDENT, data_dir=world)
    assert approvals.load(a.id, world).status is S.APPROVED
    log = [e for e in __import__("jason.approvals.audit", fromlist=["x"]).read(world, a.id) if e["event"] == "apply.refused"]
    assert log and "pause" in log[-1]["detail"]
    live, a = signed(world, minutes_ago=31)
    assert engine.problems(a, world) == []
    assert engine.apply(a.id, live, by=PRESIDENT, data_dir=world).approval.status is S.APPLIED


def test_a_pause_can_be_ended_only_by_the_clock_and_a_withdrawal_during_it_is_allowed(world):
    adopt(world, "pause-before-apply", {"minutes": 30})
    live, a = signed(world, minutes_ago=1)
    assert engine.withdraw(a.id, by=SECRETARY, reason="a mistake caught in the pause", data_dir=world).status is S.WITHDRAWN


def test_the_pause_starts_at_the_last_signature_of_a_two_person_plan(world):
    adopt(world, "pause-before-apply", {"minutes": 30})
    live, a = signed(world, "fake-two", minutes_ago=40)           # both signatures long ago
    assert engine.problems(a, world) == []
    live2 = Live(None, 1, world)
    b = engine.plan("fake-two", live2, by=PRESIDENT)
    engine.decide(b.id, "all", by=PRESIDENT, data_dir=world)
    b = engine.submit(b.id, by=PRESIDENT, data_dir=world)
    b.first = Signature(PRESIDENT, (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat(timespec="seconds"), b.fingerprint)
    approvals.save(b, world)
    engine.confirm(b.id, by=SECRETARY, data_dir=world)            # the second signs now: the pause starts now
    assert any("pause before apply" in p for p in engine.problems(approvals.load(b.id, world), world))


def test_until_the_next_day_ends_at_the_next_midnight():
    p = apply_prefs.ApplyPrefs("k", pause_until_next_day=True)
    tz = timezone(timedelta(hours=-7))
    signed_at = datetime(2099, 3, 4, 22, 30, tzinfo=tz)
    assert apply_prefs.pause_ends(signed_at, p, tz) == datetime(2099, 3, 5, 0, 0, tzinfo=tz)
    both = apply_prefs.ApplyPrefs("k", pause_minutes=60 * 40, pause_until_next_day=True)
    assert apply_prefs.pause_ends(signed_at, both, tz) == signed_at + timedelta(minutes=2400)
    assert apply_prefs.pause_ends(None, p) is None and apply_prefs.pause_ends(signed_at, apply_prefs.ApplyPrefs("k")) is None


def test_how_long_is_said_in_words():
    now = datetime(2099, 1, 1, tzinfo=timezone.utc)
    for seconds, said in ((30, "less than a minute"), (75, "1 minute"), (600, "10 minutes"), (3 * 3600, "3 hours"),
                          (72 * 3600, "3 days")):
        assert apply_prefs.left(now + timedelta(seconds=seconds), now) == said


# --- who may apply -----------------------------------------------------------------------------------------------------------

def test_any_signer_lets_only_a_person_who_signed_apply(world):
    adopt(world, "who-may-apply", {"who": "any_signer"})
    live, a = signed(world, "fake-two", by=PRESIDENT)             # signed by the president, confirmed by the secretary
    for name in (PRESIDENT, SECRETARY):
        assert engine.apply_refusals(a, by=name, data_dir=world) == []
    (why,) = engine.apply_refusals(a, by=TREASURER, data_dir=world)
    assert "lets only a person who signed this plan apply it" in why and "adopted on 2099-01-01" in why
    with pytest.raises(Refused, match="did not sign it"):
        engine.apply(a.id, live, by=TREASURER, data_dir=world)
    assert engine.apply(a.id, live, by=SECRETARY, data_dir=world).approval.status is S.APPLIED


def test_not_signer_is_a_separation_of_duties_for_either_signer(world):
    adopt(world, "who-may-apply", {"who": "not_signer"})
    live, a = signed(world, "fake-two", by=PRESIDENT)
    for name in (PRESIDENT, SECRETARY, PRESIDENT.upper()):
        assert any("does not let a person who signed" in p for p in engine.apply_refusals(a, by=name, data_dir=world))
    assert engine.apply_refusals(a, by=TREASURER, data_dir=world) == []
    with pytest.raises(Refused, match="another board member or the manager applies"):
        engine.apply(a.id, live, by=PRESIDENT, data_dir=world)
    assert engine.apply(a.id, live, by=DIRECTOR, data_dir=world).approval.status is S.APPLIED


def test_an_adopted_who_asks_the_roster_but_the_default_does_not(world):
    live, a = signed(world)
    assert engine.apply_refusals(a, by=STRANGER, data_dir=world) == []                  # the default: not checked
    adopt(world, "who-may-apply", {"who": "board_or_manager"})
    (why,) = engine.apply_refusals(a, by=STRANGER, data_dir=world)
    assert "holds no such office on the roster" in why
    assert engine.apply_refusals(a, by=OTHER_DIRECTOR, data_dir=world) == []


def test_two_preferences_that_leave_no_one_refuse_every_apply(world):
    adopt(world, "who-may-apply", {"who": "any_signer"})
    adopt(world, "who-may-apply", {"who": "not_signer"}, key="who-two")
    live, a = signed(world)
    (why,) = engine.apply_refusals(a, by=PRESIDENT, data_dir=world)
    assert "leave no one who may apply" in why


def test_who_binds_a_kind_that_is_applied_at_a_terminal_too(world, kinds):
    adopt(world, "who-may-apply", {"who": "not_signer"})
    live, a = signed(world, "fake-terminal", by=PRESIDENT)
    live.terminal = True
    with pytest.raises(Refused, match="signed it"):
        engine.apply(a.id, live, by=PRESIDENT, data_dir=world)
    assert engine.apply(a.id, live, by=DIRECTOR, data_dir=world).approval.status is S.APPLIED


# --- the typed count --------------------------------------------------------------------------------------------------------

def test_a_plan_over_the_boards_number_is_applied_only_with_the_right_count_typed(world):
    adopt(world, "typed-count-over", {"over": 2})
    live, a = signed(world, n=3)
    for typed, said in ((None, "type the number this plan makes"), (2, "2 is not the number of changes"),
                        (4, "4 is not the number of changes")):
        with pytest.raises(Refused, match=said):
            engine.apply(a.id, live, by=PRESIDENT, data_dir=world, typed_count=typed)
    assert approvals.load(a.id, world).status is S.APPROVED
    done = engine.apply(a.id, live, by=PRESIDENT, data_dir=world, typed_count=3)
    assert done.approval.status is S.APPLIED and len(done.approval.approved) == 3


def test_a_plan_at_or_under_the_number_asks_for_no_count(world):
    adopt(world, "typed-count-over", {"over": 3})
    live, a = signed(world, n=3)
    assert engine.apply_refusals(a, by=PRESIDENT, data_dir=world) == []
    assert engine.apply(a.id, live, by=PRESIDENT, data_dir=world).approval.status is S.APPLIED


def test_zero_asks_for_the_count_on_every_plan_and_a_count_typed_unasked_is_harmless(world):
    adopt(world, "typed-count-over", {"over": 0})
    live, a = signed(world, n=1)
    assert engine.apply_refusals(a, by=PRESIDENT, data_dir=world)
    assert engine.apply(a.id, live, by=PRESIDENT, data_dir=world, typed_count=1).approval.status is S.APPLIED
    live2, b = signed(world, "fake-other", n=1)
    assert engine.apply_refusals(b, by=PRESIDENT, data_dir=world)


def test_the_count_is_the_plans_approved_changes_not_its_rejected_ones(world):
    adopt(world, "typed-count-over", {"over": 1})
    live = Live(None, 1, world)
    a = engine.plan("fake-plain", live, by=PRESIDENT, scope={"n": 4})
    engine.decide(a.id, [a.items[0].id, a.items[1].id], by=PRESIDENT, data_dir=world)
    engine.decide(a.id, [a.items[2].id, a.items[3].id], by=PRESIDENT, decision=model.Decision.REJECTED, reason="not now",
                  data_dir=world)
    a = engine.submit(a.id, by=PRESIDENT, data_dir=world)
    assert a.status is S.PARTIALLY_APPROVED
    assert "is not the number of changes" in engine.apply_refusals(a, by=PRESIDENT, typed_count=4, data_dir=world)[0]
    assert engine.apply_refusals(a, by=PRESIDENT, typed_count=2, data_dir=world) == []


# --- the reminder -----------------------------------------------------------------------------------------------------------

def test_a_waiting_plan_is_a_reminder_due_after_the_default_24_hours_and_sends_nothing(world):
    live, a = signed(world, minutes_ago=60 * 25)
    (row,) = engine.waiting_to_apply(world)
    assert row["reminderHours"] == 24 and row["reminderDue"] is True and row["pausing"] is False
    live, b = signed(world, n=2, minutes_ago=60 * 3)                  # another scope: it does not replace the first plan
    rows = {r["id"]: r for r in engine.waiting_to_apply(world)}
    assert rows[b.id]["reminderDue"] is False and rows[a.id]["reminderDue"] is True
    assert not (world / "outbox").exists()


def test_the_boards_reminder_hours_replace_the_default_and_none_turns_it_off(world):
    live, a = signed(world, minutes_ago=60 * 3)
    adopt(world, "reminder-hours", {"hours": 2})
    assert engine.waiting_to_apply(world)[0]["reminderDue"] is True
    adopt(world, "reminder-hours", {"off": True}, key="remind-off", scope=Scope(ScopeKind.KIND, "fake-plain"))
    row = engine.waiting_to_apply(world)[0]
    assert row["reminderDue"] is True and row["reminderHours"] == 2                  # an hours control still asks
    (world / "controls" / "acts.jsonl").unlink()
    adopt(world, "reminder-hours", {"off": True})
    row = engine.waiting_to_apply(world)[0]
    assert row["reminderHours"] is None and row["reminderDue"] is False


def test_a_row_in_a_pause_says_when_it_ends(world):
    adopt(world, "pause-before-apply", {"minutes": 30})
    live, a = signed(world, minutes_ago=5)
    (row,) = engine.waiting_to_apply(world)
    assert row["pausing"] is True and row["pauseEndsAt"].endswith("+00:00")
    live, b = signed(world, n=2, minutes_ago=50)
    assert {r["id"]: r["pausing"] for r in engine.waiting_to_apply(world)}[b.id] is False


def test_the_attention_line_says_reminder_due_only_when_it_is(world):
    from jason.tasks import attention

    signed(world, minutes_ago=60 * 30)
    signed(world, n=2, minutes_ago=60)
    texts = sorted(i.text for i in attention.approvals_section(world).items)
    assert sum("reminder due" in t for t in texts) == 1


# --- the console's choice ---------------------------------------------------------------------------------------------------

def test_where_is_a_terminal_by_default_and_in_words_says_how(world, kinds):
    p = apply_prefs.effective("fake-plain", data_dir=world)
    why = apply_prefs.where_refusal(p, kinds["plain"])
    assert "apply is at a terminal" in why and "jason approvals apply ID --yes --by NAME" in why
    adopt(world, "where-apply", {"where": "console"})
    assert apply_prefs.where_refusal(apply_prefs.effective("fake-plain", data_dir=world), kinds["plain"]) == ""


def test_the_terminal_only_kind_names_its_own_command_whatever_is_chosen(world, kinds):
    adopt(world, "where-apply", {"where": "console"})
    p = apply_prefs.effective(kinds["terminal"], data_dir=world)
    assert "jason fake --send --yes" in apply_prefs.where_refusal(p, kinds["terminal"])


def test_the_plan_view_words_each_setting_and_where_it_comes_from(world):
    adopt(world, "pause-before-apply", {"minutes": 45})
    adopt(world, "typed-count-over", {"over": 9})
    got = apply_prefs.as_dict(apply_prefs.effective("fake-plain", data_dir=world))
    rows = {r["setting"]: r for r in got["rows"]}
    assert rows["pause"]["words"].startswith("A pause of 45 minutes") and rows["pause"]["source"] == (
        "the board adopted this on 2099-01-01")
    assert rows["typed"]["words"] == "Above 9 changes the person applying types the number of changes."
    assert rows["where"]["default"] and rows["pause"]["default"] is False
    assert got["pauseMinutes"] == 45 and got["typedCountOver"] == 9 and got["reminderHours"] == 24


# --- offering one, from the command ---------------------------------------------------------------------------------------

@pytest.fixture
def cli(world, monkeypatch, capsys):
    from controls_world import Home
    from jason.cli import build_parser

    parser = build_parser()
    home = Home()
    monkeypatch.setattr("jason.commands._shared.data_dir", lambda args=None: world)
    monkeypatch.setattr("jason.community.community", lambda: home)

    def go(*argv):
        args = parser.parse_args(["controls", *argv])
        code = args.func(args)
        out = capsys.readouterr()
        return code, out.out, out.err
    return go


def test_a_preference_is_offered_proposed_and_adopted_from_the_command(cli, world, kinds):
    code, out, err = cli("--offer", "pause-before-apply", "--by", "A Person")
    assert code == 0 and "It adopts nothing" in out
    assert cli("--propose", "pause-before-apply", "--by", "A Person")[0] == 0
    code, out, err = cli("--adopt", "pause-before-apply", "--by", "Person 1 secretary", "--meeting", "2099-03-01",
                         "--decision", "dec-1", "--effective", "2099-04-01", "--param", "minutes=20", "--param",
                         "until_next_day=true")
    assert code == 0 and "Nothing recorded" in out
    assert cli("--adopt", "pause-before-apply", "--by", "Person 1 secretary", "--meeting", "2099-03-01", "--decision",
               "dec-1", "--effective", "2020-04-01", "--param", "minutes=20", "--yes")[0] == 0
    p = apply_prefs.effective("fake-plain", data_dir=world)
    assert p.pause_minutes == 20 and p.pausing
    code, out, err = cli("--list", "--family", "applying")
    assert code == 0 and "pause-before-apply" in out


def test_the_command_refuses_a_console_for_a_floored_kind_and_a_bad_scope(cli, world, kinds):
    assert cli("--offer", "where-apply", "--scope", "kind:fake-terminal", "--by", "A Person")[0] == 0     # no value yet
    assert cli("--propose", "where-apply--kind-fake-terminal", "--by", "A Person")[0] == 0
    code, out, err = cli("--adopt", "where-apply--kind-fake-terminal", "--by", "Person 1 secretary", "--meeting",
                         "2099-03-01", "--decision", "dec-1", "--effective", "2020-04-01", "--param", "where=console", "--yes")
    assert code == 2 and "whatever a board prefers" in err and "terminal" in err
    assert cli("--adopt", "where-apply--kind-fake-terminal", "--by", "Person 1 secretary", "--meeting", "2099-03-01",
               "--decision", "dec-1", "--effective", "2020-04-01", "--param", "where=terminal", "--yes")[0] == 0
    assert cli("--offer", "where-apply", "--scope", "everything", "--by", "A Person")[0] == 2
    assert cli("--offer", "where-apply", "--scope", "kind:fake-plain")[0] == 2                    # --by is needed
    assert cli("--offer", "where-apply", "--scope", "kind:fake-plain", "--by", "A Person")[0] == 0
    assert cli("--propose", "where-apply--kind-fake-plain", "--by", "A Person")[0] == 0
    code, out, err = cli("--adopt", "where-apply--kind-fake-plain", "--by", "Person 1 secretary", "--meeting", "2099-03-01",
                         "--decision", "dec-1", "--effective", "2020-04-01", "--param", "where=console", "--yes")
    assert code == 0
    assert apply_prefs.effective("fake-plain", data_dir=world).where == "console"
    assert apply_prefs.effective("fake-other", data_dir=world).where == "terminal"


def test_a_scope_with_nothing_to_offer_is_refused(cli):
    code, out, err = cli("--list", "--scope", "all")
    assert code == 2 and "--scope" in err


def test_the_terminal_shows_how_a_signed_plan_is_applied(world, monkeypatch):
    from jason.commands.approvals import show_lines

    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: world)

    adopt(world, "typed-count-over", {"over": 0})
    live, a = signed(world)
    text = "\n".join(show_lines(a))
    assert "how it is applied:" in text and "Above 0 changes the person applying types" in text
    assert "(the default; the board has not adopted one)" in text
