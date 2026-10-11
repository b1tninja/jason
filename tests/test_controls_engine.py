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
    control = make(params=params, scope=Scope(ScopeKind.KIND, kind_key), basis=kw.pop("basis", Basis("Bylaws 1.1")),
                   key=key)
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
    a = engine.submit(plan.id, by="A Manager", data_dir=world)
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



def test_the_community_interface_has_an_empty_default():
    from jason.community.base import Community

    assert Community.controls(object()) == ()
