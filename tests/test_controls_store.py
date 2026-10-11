"""Controls: the facts a community's controls start from, the append-only log of acts, and the fold that gives the
current state."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from controls_support import make, two_person_kind  # noqa: F401 - fixture
from jason.community.base import OfficerRole as R
from jason.controls import store
from jason.controls.types import (Basis, ControlAct, ControlRefused, ControlState, Scope, ScopeKind, to_dict)

A = ControlAct


def at(day: int) -> datetime:
    return datetime(2099, 10, day, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def spec(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    return tmp_path / "spec"


def put_facts(spec, controls, profile="alpha"):
    folder = spec / profile
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "controls.json").write_text(json.dumps({"controls": controls}), encoding="utf-8")


def rec(tmp_path, act, key="pay", **kw):
    kw.setdefault("by", "A Secretary")
    kw.setdefault("why", "the board voted")
    return store.record(act, key, data_dir=tmp_path, profile="alpha", **kw)


def suggestion(**kw):
    kw.setdefault("basis", Basis("Bylaws 1.1", "words whole"))
    return make(params={"signers": 2, "over_cents": 250000}, reading="jason's reading", **kw)


def test_nothing_is_configured_until_a_facts_file_or_a_log_exists(tmp_path, spec):
    assert not store.configured(tmp_path, "alpha")
    assert store.load(tmp_path, "alpha") == []
    put_facts(spec, [])
    assert store.configured(tmp_path, "alpha") and store.load(tmp_path, "alpha") == []
    assert not store.configured(tmp_path / "other", "beta")


def test_the_facts_are_read_as_controls_and_a_loosening_in_them_is_refused(tmp_path, spec):
    good = to_dict(make(params={"signers": 2}, state=ControlState.PROPOSED))
    put_facts(spec, [good])
    assert [c.key for c in store.load(tmp_path, "alpha")] == ["payment-signers"]
    bad = to_dict(make(params={"signers": 1}, basis=Basis("Bylaws 99.9", floor={"signers": 2})))
    put_facts(spec, [bad])
    with pytest.raises(ControlRefused, match="Bylaws 99.9"):
        store.load(tmp_path, "alpha")


def test_a_control_goes_from_suggested_to_adopted_with_every_act_recorded(tmp_path, spec):
    c = rec(tmp_path, A.SUGGEST, by="jason", why="found in the bylaws", control=suggestion(), now=at(1))
    assert c.state is ControlState.SUGGESTED and c.key == "pay" and len(c.history) == 1
    c = rec(tmp_path, A.PROPOSE, by="A Member", why="to the October meeting", now=at(2))
    assert c.state is ControlState.PROPOSED
    c = rec(tmp_path, A.ADOPT, parameters={"signers": 2, "over_cents": 100000, "roles": [R.DIRECTOR.value]},
            decision="2099-10-03#4", effective="2099-11-14", now=at(3))
    assert c.state is ControlState.ADOPTED and c.parameters["over_cents"] == 100000
    assert c.decision == "2099-10-03#4" and c.effective.isoformat() == "2099-11-14" and c.adopted_at == "2099-10-03"
    assert [h.act for h in c.history] == [A.SUGGEST, A.PROPOSE, A.ADOPT]
    again = store.get("pay", tmp_path, "alpha")                      # the fold of the log is the same control
    assert again == c
    rows = store.acts(tmp_path)
    assert [r["seq"] for r in rows] == [1, 2, 3] and rows[2]["decision"] == "2099-10-03#4"
    assert store.verify(tmp_path) == (True, None, "the chain is whole")
    c = rec(tmp_path, A.RETIRE, why="superseded", now=at(4))
    assert c.state is ControlState.RETIRED and len(c.history) == 4


def test_an_act_names_a_person_and_says_why(tmp_path, spec):
    with pytest.raises(ControlRefused, match="names the person"):
        rec(tmp_path, A.SUGGEST, by=" ", control=suggestion())
    with pytest.raises(ControlRefused, match="says why"):
        rec(tmp_path, A.SUGGEST, why="", control=suggestion())
    assert not store.acts_path(tmp_path).exists()                    # nothing was written


def test_a_move_the_lifecycle_does_not_allow_is_refused_and_writes_nothing(tmp_path, spec):
    rec(tmp_path, A.SUGGEST, control=suggestion(), now=at(1))
    for act in (A.ADOPT, A.DECLINE, A.DEFER, A.RETIRE):
        with pytest.raises(ControlRefused, match="cannot"):
            rec(tmp_path, act, decision="d", effective="2099-11-01", again_on="2099-12-01")
    with pytest.raises(ControlRefused, match="cannot suggest"):
        rec(tmp_path, A.SUGGEST, control=suggestion())               # a second suggestion of the same key
    with pytest.raises(ControlRefused, match="cannot propose|no control"):
        rec(tmp_path, A.PROPOSE, key="nobody")
    assert len(store.acts(tmp_path)) == 1


def test_an_adoption_needs_the_decision_and_the_effective_date(tmp_path, spec):
    rec(tmp_path, A.SUGGEST, control=suggestion(), now=at(1))
    rec(tmp_path, A.PROPOSE, now=at(2))
    with pytest.raises(ControlRefused, match="decision"):
        rec(tmp_path, A.ADOPT, effective="2099-11-01")
    with pytest.raises(ControlRefused, match="effective date"):
        rec(tmp_path, A.ADOPT, decision="d1")
    with pytest.raises(ControlRefused, match="effective date"):
        rec(tmp_path, A.ADOPT, decision="d1", effective="soon")


def test_an_adoption_below_the_provisions_floor_is_refused(tmp_path, spec):
    rec(tmp_path, A.SUGGEST, control=suggestion(basis=Basis("Bylaws 99.9", floor={"signers": 2})), now=at(1))
    rec(tmp_path, A.PROPOSE, now=at(2))
    with pytest.raises(ControlRefused, match="Bylaws 99.9"):
        rec(tmp_path, A.ADOPT, parameters={"signers": 1}, decision="d1", effective="2099-11-01")
    assert store.get("pay", tmp_path, "alpha").state is ControlState.PROPOSED


def test_a_suggestion_that_would_loosen_a_floor_is_not_recorded(tmp_path, spec):
    with pytest.raises(ControlRefused, match="floor"):
        rec(tmp_path, A.SUGGEST, control=make(params={"signers": 1}, basis=Basis("Bylaws 99.9", floor={"signers": 2})))
    assert not store.acts_path(tmp_path).exists()


def test_a_suggestion_naming_a_two_person_kind_below_two_is_refused(tmp_path, spec, two_person_kind):
    scoped = make(params={"signers": 1}, scope=Scope(ScopeKind.KIND, two_person_kind.key))
    with pytest.raises(ControlRefused, match="two-person kind"):
        rec(tmp_path, A.SUGGEST, control=scoped)


def test_a_declined_control_is_asked_again_only_after_the_date_the_board_set(tmp_path, spec):
    rec(tmp_path, A.SUGGEST, control=suggestion(), now=at(1))
    rec(tmp_path, A.PROPOSE, now=at(2))
    rec(tmp_path, A.DECLINE, why="not this year", again_on="2099-12-01", now=at(3))
    with pytest.raises(ControlRefused, match="may be asked again on 2099-12-01"):
        rec(tmp_path, A.PROPOSE, now=at(20))
    c = rec(tmp_path, A.PROPOSE, now=datetime(2099, 12, 2, tzinfo=timezone.utc))
    assert c.state is ControlState.PROPOSED
    rec(tmp_path, A.DECLINE, why="again no", now=datetime(2099, 12, 3, tzinfo=timezone.utc))
    with pytest.raises(ControlRefused, match="no date to ask again"):
        rec(tmp_path, A.PROPOSE, now=datetime(2100, 6, 1, tzinfo=timezone.utc))


def test_a_deferred_control_comes_back_when_its_date_is_reached(tmp_path, spec):
    rec(tmp_path, A.SUGGEST, control=suggestion(), now=at(1))
    rec(tmp_path, A.PROPOSE, now=at(2))
    rec(tmp_path, A.DEFER, why="after the audit", again_on="2099-11-01", now=at(3))
    with pytest.raises(ControlRefused, match="2099-11-01"):
        rec(tmp_path, A.PROPOSE, now=at(10))
    assert rec(tmp_path, A.PROPOSE, now=datetime(2099, 11, 1, tzinfo=timezone.utc)).state is ControlState.PROPOSED


def test_the_log_is_hash_chained_and_an_edit_is_found(tmp_path, spec):
    rec(tmp_path, A.SUGGEST, control=suggestion(), now=at(1))
    rec(tmp_path, A.PROPOSE, now=at(2))
    file = store.acts_path(tmp_path)
    lines = file.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[1])["prev"] == json.loads(lines[0])["hash"]
    file.write_text(lines[0].replace("the board voted", "tampered") + "\n" + lines[1] + "\n", encoding="utf-8")
    ok, line, why = store.verify(tmp_path)
    assert not ok and line == 1 and "hash" in why


def test_acts_fold_over_the_controls_in_the_facts(tmp_path, spec):
    put_facts(spec, [to_dict(make(params={"signers": 2}, state=ControlState.PROPOSED))])
    c = rec(tmp_path, A.ADOPT, key="payment-signers", decision="d1", effective="2099-11-01", now=at(3))
    assert c.state is ControlState.ADOPTED and [x.state for x in store.load(tmp_path, "alpha")] == [ControlState.ADOPTED]
    with pytest.raises(ControlRefused, match="cannot suggest"):
        rec(tmp_path, A.SUGGEST, key="payment-signers", control=suggestion())      # the key is taken by the facts


def test_a_log_line_that_could_not_have_been_written_is_refused_when_read(tmp_path, spec):
    rec(tmp_path, A.SUGGEST, control=suggestion(), now=at(1))
    with store.acts_path(tmp_path).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"seq": 2, "key": "pay", "act": "retire", "by": "X", "why": "y", "at": "2099-10-02"}) + "\n")
    with pytest.raises(ControlRefused, match="act 2 on pay"):
        store.load(tmp_path, "alpha")


def test_the_communitys_own_controls_are_loaded_beside_the_facts(tmp_path, spec):
    class Mine:
        def controls(self):
            return (make("recorder", {"recorded_by": (R.SECRETARY,)}, key="mine", state=ControlState.PROPOSED),)

    assert [c.key for c in store.load(tmp_path, "alpha", Mine())] == ["mine"]
    put_facts(spec, [to_dict(make("recorder", {"recorded_by": ["secretary"]}, key="mine"))])
    with pytest.raises(ControlRefused, match="both the facts and the profile"):
        store.load(tmp_path, "alpha", Mine())
