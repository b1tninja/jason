"""Controls and the approvals engine: with no controls the engine is unchanged, and with an adopted control in force
the second, distinct person is required and named (the hook is ``engine.needs_second``)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from controls_support import (FULL, LONG_AGO, TODAY, make, one_person_kind, roster,  # noqa: F401 - fixtures
                              two_person_kind)
from jason.approvals import engine
from jason.approvals.engine import Live, Refused
from jason.approvals.model import ApprovalStatus as S
from jason.community.base import OfficerRole as R
from jason.controls import effective, store
from jason.controls.types import Basis, ControlAct, ControlRefused, ControlState, Scope, ScopeKind, to_dict


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A data folder and a spec folder of their own, and a roster the hook can read."""
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    monkeypatch.setattr(effective, "_community_roster", lambda: FULL)
    return tmp_path


def adopt(world, kind_key, params, key="pay", effective=LONG_AGO.isoformat(), **kw):
    """Put a control through the store the way the secretary's record does, effective long ago."""
    control = make(params=params, scope=kw.pop("scope", None) or Scope(ScopeKind.KIND, kind_key),
                   basis=kw.pop("basis", Basis("Bylaws 1.1")), key=key)
    for act, extra in ((ControlAct.SUGGEST, {"control": control}), (ControlAct.PROPOSE, {}),
                       (ControlAct.ADOPT, {"decision": "dec-1", "effective": effective})):
        store.record(act, key, by="A Secretary", why="a test", data_dir=world, profile="alpha",
                     now=datetime(2099, 1, 1, tzinfo=timezone.utc), **extra)


def run(world, kind_key, cost=None):
    live = Live(None, 1, world)
    a = engine.plan(kind_key, live, by="A Manager", scope={"cost": cost} if cost is not None else None)
    engine.decide(a.id, "all", by="A Manager", data_dir=world)
    return live, engine.submit(a.id, by="A Manager", data_dir=world)


def use_profile(monkeypatch, name="alpha"):
    # the engine asks for the active profile's facts and data folder; the tests name theirs
    monkeypatch.setenv("JASON_PROFILE", name)


def test_with_no_controls_a_one_person_kind_needs_no_second_and_reads_nothing(world, one_person_kind, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the controls were read although none is configured")

    monkeypatch.setattr(store, "load", boom)
    monkeypatch.setattr(effective, "_community_roster", boom)
    live, a = run(world, one_person_kind.key)
    assert a.status is S.APPROVED and not engine.needs_second(a, data_dir=world)
    assert all("second" not in p for p in engine.problems(a, world))
    assert effective.requires_second(one_person_kind.key, {}, data_dir=world) is False


def test_a_two_person_kind_still_needs_a_second_whatever_the_controls(world, two_person_kind):
    _, a = run(world, two_person_kind.key)
    assert engine.needs_second(a, data_dir=world)


def test_an_adopted_control_in_force_requires_a_second_person_before_apply(world, one_person_kind, monkeypatch):
    use_profile(monkeypatch)
    adopt(world, one_person_kind.key, {"signers": 2})
    live, a = run(world, one_person_kind.key)
    assert engine.needs_second(a, data_dir=world)
    with pytest.raises(Refused, match="second, distinct person"):
        engine.apply(a.id, live, by="A Manager")
    with pytest.raises(Refused, match="submitted it"):
        engine.confirm(a.id, by="a manager", data_dir=world)
    engine.confirm(a.id, by="B Treasurer", data_dir=world)
    assert engine.apply(a.id, live, by="A Manager").approval.status is S.APPLIED


def test_a_control_for_another_kind_changes_nothing_here(world, one_person_kind, two_person_kind, monkeypatch):
    use_profile(monkeypatch)
    adopt(world, two_person_kind.key, {"signers": 2})
    _, a = run(world, one_person_kind.key)
    assert not engine.needs_second(a, data_dir=world)


def test_a_threshold_control_asks_for_the_second_only_above_the_amount(world, one_person_kind, monkeypatch):
    use_profile(monkeypatch)
    adopt(world, one_person_kind.key, {"signers": 2, "over_cents": 250000})
    _, below = run(world, one_person_kind.key, cost=250000)
    _, above = run(world, one_person_kind.key, cost=250001)
    assert not engine.needs_second(below, data_dir=world) and engine.needs_second(above, data_dir=world)


def test_a_control_in_force_the_roster_cannot_satisfy_refuses_the_act_and_never_falls_back(world, one_person_kind,
                                                                                         monkeypatch):
    use_profile(monkeypatch)
    monkeypatch.setattr(effective, "_community_roster", lambda: roster(R.PRESIDENT, R.DIRECTOR))
    adopt(world, one_person_kind.key, {"signers": 2, "roles": [R.DIRECTOR.value]})
    live = Live(None, 1, world)
    plan = engine.plan(one_person_kind.key, live, by="A Manager")
    engine.decide(plan.id, "all", by="A Manager", data_dir=world)
    with pytest.raises(Refused, match="a control the board adopted on 2099-01-01 requires two signers; "
                                      "the roster lacks a second director"):
        engine.submit(plan.id, by="A Manager", data_dir=world)
    assert store_status(plan.id, world) is S.IN_REVIEW                       # nothing was signed
    # the roster fills the seat: the same plan is submitted, and needs the second person
    monkeypatch.setattr(effective, "_community_roster", lambda: roster(R.PRESIDENT, R.DIRECTOR, R.DIRECTOR))
    a = engine.submit(plan.id, by="Person 1 director", data_dir=world)       # a director signs, as the control names
    assert engine.needs_second(a, data_dir=world) and engine.control_refusals(a, data_dir=world) == []
    # and if the seat empties again after the signature, apply and check name the reason as a problem
    monkeypatch.setattr(effective, "_community_roster", lambda: roster(R.PRESIDENT, R.DIRECTOR))
    assert any("the roster lacks a second director" in p for p in engine.problems(a, world))
    with pytest.raises(Refused, match="the roster lacks a second director"):
        engine.apply(a.id, live, by="A Manager")


def test_a_control_before_its_date_warns_but_does_not_bind(world, one_person_kind, monkeypatch):
    use_profile(monkeypatch)
    monkeypatch.setattr(effective, "_community_roster", lambda: roster(R.PRESIDENT, R.DIRECTOR))
    adopt(world, one_person_kind.key, {"signers": 2, "roles": [R.DIRECTOR.value]}, effective="2999-01-01")
    _, a = run(world, one_person_kind.key)
    assert not engine.needs_second(a, data_dir=world) and engine.control_refusals(a, data_dir=world) == []
    got = effective.effective_approver(one_person_kind.key, {}, controls=store.load(world, "alpha"),
                                       roster=roster(R.PRESIDENT, R.DIRECTOR), today=TODAY)
    assert "the roster could not satisfy it now: the roster lacks a second director" in got.waiting[0].reason


def store_status(ident, world):
    from jason.approvals import store as approvals

    return approvals.load(ident, world).status


def test_a_roster_that_cannot_be_read_is_not_checked_so_the_control_binds(world, one_person_kind, monkeypatch):
    use_profile(monkeypatch)
    monkeypatch.setattr(effective, "_community_roster", lambda: None)
    adopt(world, one_person_kind.key, {"signers": 2, "roles": [R.DIRECTOR.value]})
    _, a = run(world, one_person_kind.key)
    assert engine.needs_second(a, data_dir=world)


def test_a_control_in_the_private_facts_binds_too(world, one_person_kind, monkeypatch):
    use_profile(monkeypatch)
    folder = world / "spec" / "alpha"
    folder.mkdir(parents=True)
    c = make(params={"signers": 2}, scope=Scope(ScopeKind.KIND, one_person_kind.key), state=ControlState.ADOPTED,
             effective=LONG_AGO, decision="d")
    (folder / "controls.json").write_text(json.dumps({"controls": [to_dict(c)]}), encoding="utf-8")
    _, a = run(world, one_person_kind.key)
    assert engine.needs_second(a, data_dir=world)


def test_a_control_log_that_cannot_be_read_stops_the_check_rather_than_loosen_it(world, one_person_kind, monkeypatch):
    use_profile(monkeypatch)
    adopt(world, one_person_kind.key, {"signers": 2})
    lines = store.acts_path(world).read_text(encoding="utf-8").splitlines()
    store.acts_path(world).write_text("\n".join(lines[:-1] + ['{"seq": 9, "key": "pay", "act": "adopt"}']) + "\n",
                                      encoding="utf-8")
    with pytest.raises(ControlRefused):
        run(world, one_person_kind.key)                                     # submit reads the controls and stops



# --- who may sign -----------------------------------------------------------------------------------------------------
# FULL: Person 0 president, Person 1 secretary, Person 2 treasurer, Person 3 director, Person 4 director.

PRES, SEC, TREAS, DIR_A, DIR_B = (f"Person {i} {r}" for i, r in enumerate(("president", "secretary", "treasurer",
                                                                           "director", "director")))


def prepare(world, kind_key, by="A Manager"):
    live = Live(None, 1, world)
    a = engine.plan(kind_key, live, by=by)
    engine.decide(a.id, "all", by=by, data_dir=world)
    return live, a


def test_a_required_office_binds_the_signers_as_a_whole_and_refuses_at_the_last_signature(world, one_person_kind,
                                                                                         monkeypatch):
    use_profile(monkeypatch)
    adopt(world, one_person_kind.key, {"signers": 2, "must_include": [R.TREASURER.value]})
    live, plan = prepare(world, one_person_kind.key)
    a = engine.submit(plan.id, by=DIR_A, data_dir=world)                     # the first signer need not be the treasurer
    assert a.status is S.APPROVED
    with pytest.raises(Refused, match="a control the board adopted on 2099-01-01 requires the treasurer among the "
                                      "signers"):
        engine.confirm(a.id, by=DIR_B, data_dir=world)
    from jason.approvals import store as approvals

    assert approvals.load(a.id, world).second is None                        # nothing was signed
    with pytest.raises(Refused, match="second, distinct person"):
        engine.apply(a.id, live, by="A Manager")                              # and until the second signs, it is not applied
    engine.confirm(a.id, by=TREAS, data_dir=world)
    assert engine.apply(a.id, live, by="A Manager").approval.status is S.APPLIED


def test_a_treasurer_may_sign_first_and_a_director_second(world, one_person_kind, monkeypatch):
    use_profile(monkeypatch)
    adopt(world, one_person_kind.key, {"signers": 2, "must_include": [R.TREASURER.value]})
    live, plan = prepare(world, one_person_kind.key)
    a = engine.submit(plan.id, by=TREAS, data_dir=world)
    engine.confirm(a.id, by=DIR_A, data_dir=world)
    assert engine.apply(a.id, live, by="A Manager").approval.status is S.APPLIED


def test_the_offices_are_asked_again_before_apply_if_the_roster_changed_after_the_signatures(world, one_person_kind,
                                                                                            monkeypatch):
    use_profile(monkeypatch)
    adopt(world, one_person_kind.key, {"signers": 2, "must_include": [R.TREASURER.value]})
    live, plan = prepare(world, one_person_kind.key)
    a = engine.submit(plan.id, by=DIR_A, data_dir=world)
    a = engine.confirm(a.id, by=TREAS, data_dir=world)
    assert engine.problems(a, world) == []
    # the treasurer's seat now belongs to someone else (the roster no longer names that signer as treasurer)
    monkeypatch.setattr(effective, "_community_roster", lambda: roster(R.PRESIDENT, R.SECRETARY, R.DIRECTOR, R.DIRECTOR,
                                                                         R.DIRECTOR))
    assert any("requires the treasurer among the signers" in p for p in engine.problems(a, world))
    with pytest.raises(Refused, match="requires the treasurer among the signers"):
        engine.apply(a.id, live, by="A Manager")


def test_a_lone_signer_must_hold_the_required_office_since_no_second_follows(world, one_person_kind, monkeypatch):
    use_profile(monkeypatch)
    adopt(world, one_person_kind.key, {"signers": 1, "must_include": [R.TREASURER.value]})
    live, plan = prepare(world, one_person_kind.key)
    with pytest.raises(Refused, match="requires the treasurer among the signers"):
        engine.submit(plan.id, by=DIR_A, data_dir=world)
    assert store_status(plan.id, world) is S.IN_REVIEW
    assert engine.submit(plan.id, by=TREAS, data_dir=world).status is S.APPROVED


def test_the_eligible_offices_bind_every_signer_and_a_name_off_the_roster_holds_none(world, one_person_kind,
                                                                                   monkeypatch):
    use_profile(monkeypatch)
    adopt(world, one_person_kind.key, {"signers": 2, "roles": [R.DIRECTOR.value, R.TREASURER.value]})
    live, plan = prepare(world, one_person_kind.key)
    with pytest.raises(Refused, match=r"allows only the director or the treasurer to sign; Person 0 president does "
                                      r"not hold one of those offices"):
        engine.submit(plan.id, by=PRES, data_dir=world)
    with pytest.raises(Refused, match="Somebody Else does not hold"):
        engine.submit(plan.id, by="Somebody Else", data_dir=world)
    a = engine.submit(plan.id, by=DIR_A.upper(), data_dir=world)               # names compare trimmed and case folded
    with pytest.raises(Refused, match="Person 1 secretary does not hold"):
        engine.confirm(a.id, by=SEC, data_dir=world)
    engine.confirm(a.id, by=TREAS, data_dir=world)
    assert engine.apply(a.id, live, by="A Manager").approval.status is S.APPLIED


def test_a_control_that_asks_only_above_an_amount_asks_its_offices_only_there(world, one_person_kind, monkeypatch):
    use_profile(monkeypatch)
    adopt(world, one_person_kind.key,
          {"signers": 2, "over_cents": 250000, "must_include": [R.TREASURER.value]})
    live = Live(None, 1, world)
    below = engine.plan(one_person_kind.key, live, by="A Manager", scope={"cost": 250000})
    engine.decide(below.id, "all", by="A Manager", data_dir=world)
    assert engine.submit(below.id, by=DIR_A, data_dir=world).status is S.APPROVED       # no second, no treasurer
    above = engine.plan(one_person_kind.key, live, by="A Manager", scope={"cost": 250001})
    engine.decide(above.id, "all", by="A Manager", data_dir=world)
    a = engine.submit(above.id, by=DIR_A, data_dir=world)
    with pytest.raises(Refused, match="requires the treasurer among the signers"):
        engine.confirm(a.id, by=DIR_B, data_dir=world)


def test_two_controls_with_no_office_in_common_leave_no_one_who_may_sign(world, one_person_kind, monkeypatch):
    use_profile(monkeypatch)
    monkeypatch.setattr(effective, "_community_roster",                       # each office has two holders
                        lambda: roster(R.PRESIDENT, R.DIRECTOR, R.DIRECTOR, R.TREASURER, R.TREASURER))
    adopt(world, one_person_kind.key, {"signers": 2, "roles": [R.DIRECTOR.value]}, key="pay")
    adopt(world, one_person_kind.key, {"signers": 2, "roles": [R.TREASURER.value]}, key="pay-2")
    live, plan = prepare(world, one_person_kind.key)
    for who in ("Person 1 director", "Person 3 treasurer"):
        with pytest.raises(Refused, match="allows only"):
            engine.submit(plan.id, by=who, data_dir=world)


def test_with_no_controls_who_signs_is_not_asked_and_nothing_is_read(world, two_person_kind, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the controls or the roster were read although no controls are configured")

    monkeypatch.setattr(store, "load", boom)
    monkeypatch.setattr(effective, "_community_roster", boom)
    live, plan = prepare(world, two_person_kind.key)
    a = engine.submit(plan.id, by="Nobody On The Roster", data_dir=world)
    engine.confirm(a.id, by="Also Not On It", data_dir=world)
    assert engine.apply(a.id, live, by="A Manager").approval.status is S.APPLIED


def test_a_roster_that_cannot_be_read_leaves_the_offices_unchecked_but_the_second_still_signs(world, one_person_kind,
                                                                                            monkeypatch):
    use_profile(monkeypatch)
    monkeypatch.setattr(effective, "_community_roster", lambda: None)
    adopt(world, one_person_kind.key, {"signers": 2, "must_include": [R.TREASURER.value]})
    live, plan = prepare(world, one_person_kind.key)
    a = engine.submit(plan.id, by="Anyone", data_dir=world)
    assert engine.needs_second(a, data_dir=world)
    with pytest.raises(Refused, match="second, distinct person"):
        engine.apply(a.id, live, by="A Manager")


def test_registered_kinds_carry_categories_as_data_and_none_is_a_money_kind_yet():
    from jason.approvals import registry

    assert registry.ActionKind.__dataclass_fields__["categories"].default == ()
    assert all(k.categories == () for k in registry.KINDS if k.key != "payhoa-mailroom-send")   # attaching a bill pays nothing
    assert registry.get("payhoa-mailroom-send").categories == ("payment",)     # a mailing is charged postage: docs/controls.md


def test_a_payment_signers_control_scoped_to_all_binds_the_mailroom_send_kind(world, monkeypatch):
    """The first registered kind that moves the association's money: a control of a payment type scoped to all now applies
    to it, with no change to the control. A kind that carries no category is untouched (tests/test_controls_effective.py)."""
    from mailroom_support import ORG, kept

    use_profile(monkeypatch)
    monkeypatch.setattr("jason.tasks.mailroom.READ_BACK", (0.0,))
    mail = kept(world, mail_class="first-class")
    key = "payhoa-mailroom-send"
    adopt(mail.data, key, {"signers": 2, "must_include": [R.TREASURER.value]}, scope=Scope())     # payment-signers, all kinds
    assert effective.effective_approver(key, {}, controls=store.load(data_dir=mail.data), roster=FULL, today=TODAY
                                        ).must_include == (R.TREASURER,)
    live = Live(mail.client, ORG, mail.data, terminal=True)
    a = engine.plan(key, live, by="A Manager", scope={"preview": mail.record["id"]})
    assert a.cost_cents == mail.record["totalCents"]                       # the amount a threshold control would read
    engine.decide(a.id, "all", by="A Manager", data_dir=mail.data)
    president = FULL[0].name
    engine.submit(a.id, by=president, data_dir=mail.data)                  # a first signature need not be the treasurer
    with pytest.raises(Refused, match="requires the treasurer among the signers"):
        engine.confirm(a.id, by=FULL[1].name, data_dir=mail.data)          # the secretary is not the treasurer
    engine.confirm(a.id, by=FULL[2].name, data_dir=mail.data)
    done = engine.apply(a.id, live, by=president, data_dir=mail.data)
    assert done.approval.status is S.APPLIED and len(mail.client.sent) == 1


def test_the_community_interface_has_an_empty_default():
    from jason.community.base import Community

    assert Community.controls(object()) == ()
