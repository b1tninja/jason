"""Controls on workflow steps: what an adopted control adds to a step (a resolution on record first, a second and different
person, a narrower set of offices), the run page's ``controls`` per step, and the engine's refusal in the same words.

Everything is made up: the example-cycle definition, its people, and the controls. With no controls source configured, nothing
changes and nothing is read."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

from controls_support import FULL, LONG_AGO, adopted, make, roster
from jason.community.base import OfficerRole as R
from jason.controls import effective, store, view
from jason.controls.catalog import CATALOG, get
from jason.controls.types import Basis, ControlAct, ControlState, Scope, ScopeKind
from jason.tasks import decisions
from jason.workflows import api, store as runs
from jason.workflows.types import EventKind, GateVerdict, StepAsk, StepRefused
from test_web_work import TODAY, app, as_, page, post, start, world  # noqa: F401 - fixtures
from test_workflows_support import C1, C2, C6, example_cycle

MANAGER, MANAGER_B, SECRETARY, TREASURER, BOTH = "A Manager", "B. Manager", "S. Placeholder", "T. Treasurer", "C. Both"
ROLES = {MANAGER: {"manager"}, MANAGER_B: {"manager"}, SECRETARY: {"secretary", "director"}, TREASURER: {"treasurer"},
         BOTH: {"manager", "secretary"}}
OFFICERS = roster(R.MANAGER, R.MANAGER, R.SECRETARY, R.TREASURER)
OFFICERS = [replace(o, name=n) for o, n in zip(OFFICERS, (MANAGER, MANAGER_B, SECRETARY, TREASURER))] + [
    replace(roster(R.MANAGER)[0], name=BOTH), replace(roster(R.SECRETARY)[0], name=BOTH)]


def roles_of(by):
    return ROLES.get(by, ())


def adopt(root, key, type_key, params, scope, *, effective_on=LONG_AGO.isoformat()):
    """Put a control through the store the way the secretary's record does."""
    control = make(type_key, params, scope=scope, basis=Basis("Bylaws 1.1"), key=key)
    for act, extra in ((ControlAct.SUGGEST, {"control": control}), (ControlAct.PROPOSE, {}),
                       (ControlAct.ADOPT, {"decision": "dec-1", "effective": effective_on})):
        store.record(act, key, by="A Secretary", why="a test", data_dir=root, profile="alpha",
                     now=datetime(2099, 1, 1, tzinfo=timezone.utc), **extra)


@pytest.fixture
def seated(world, monkeypatch):
    """The world of test_web_work plus a profile name, a roster the gates can read, and a spec folder of their own."""
    monkeypatch.setenv("JASON_PROFILE", "alpha")
    monkeypatch.setattr(effective, "_community_roster", lambda: OFFICERS)
    return world


def kinds_of(rid, root):
    return [e.kind for e in runs.read(root, "example-cycle", rid).events]


def step(c2_scope=None):
    return Scope(ScopeKind.KIND, C2) if c2_scope is None else c2_scope


# --- the pure lookup -----------------------------------------------------------------------------------------------------------

def test_a_control_that_governs_a_step_adds_its_gates_and_only_when_adopted_and_in_force():
    resolution = adopted("contract-authorization", {"resolution_first": True}, scope=Scope(ScopeKind.KIND, C2), key="res")
    got = effective.step_gates("example-cycle", C2, "manager", controls=[resolution], roster=OFFICERS, today=TODAY)
    assert got.resolution and not got.second and got.roles == () and got.controls == (resolution,)
    assert [g.gate for g in got.gates] == ["resolution"] and not got.gates[0].future
    assert got.gates[0].reason.startswith("a control the board adopted on 2099-01-01 requires a board resolution on record")
    assert not effective.step_gates("example-cycle", C1, "manager", controls=[resolution], today=TODAY).any    # another step
    for state in (ControlState.SUGGESTED, ControlState.PROPOSED, ControlState.DECLINED, ControlState.DEFERRED,
                  ControlState.RETIRED):
        assert not effective.step_gates("example-cycle", C2, "manager", controls=[replace(resolution, state=state)],
                                        today=TODAY).any


def test_a_control_adopted_but_not_yet_in_force_is_waiting_and_binds_nothing():
    later = adopted("contract-authorization", {"resolution_first": True}, scope=Scope(ScopeKind.KIND, C2),
                    effective=date(2100, 1, 1), key="later")
    got = effective.step_gates("example-cycle", C2, "manager", controls=[later], roster=OFFICERS, today=TODAY)
    assert not got.resolution and got.controls == () and [w.control for w in got.waiting] == [later]
    assert got.gates[0].future and "will require, from 2100-01-01," in got.gates[0].reason
    assert effective.step_unmet(got, by=MANAGER, held=["manager"], approved=[]) == []


def test_the_scopes_and_the_types_step_patterns_say_which_steps_a_control_governs():
    c = adopted("contract-authorization", {"resolution_first": True}, key="all")      # scoped to all: the type's own patterns
    assert get("contract-authorization").categories(effective.GovernsKind.WORKFLOW_STEP) == {"contract-signing"}
    assert effective.step_applies(c, "contract-signing", "contract-signing.3")
    assert not effective.step_applies(c, "example-cycle", C2)
    assert effective.step_applies(replace(c, scope=Scope(ScopeKind.KIND, "example-cycle")), "example-cycle", C2)    # a workflow key
    assert effective.step_applies(replace(c, scope=Scope(ScopeKind.KIND, "example-cycle.[23]")), "example-cycle", C2)   # a pattern
    assert not effective.step_applies(replace(c, scope=Scope(ScopeKind.KIND, C1)), "example-cycle", C2)
    fam = replace(c, scope=Scope(ScopeKind.FAMILY, "example"))
    assert effective.step_applies(fam, "example-cycle", C2, "example") and not effective.step_applies(fam, "example-cycle", C2, "other")
    assert not effective.step_applies(replace(c, scope=Scope(ScopeKind.ACCOUNT, "x")), "example-cycle", C2)
    assert not effective.step_applies(adopted("payment-signers", {"signers": 2}, scope=Scope(ScopeKind.KIND, C2)), "example-cycle", C2)


def test_a_type_that_governs_approvals_and_steps_may_be_scoped_to_a_step():
    c = make("second-person-confirmation", {"required": True}, scope=Scope(ScopeKind.KIND, C2))
    assert effective.validate(c) == []
    assert effective.validate(make("payment-signers", {"signers": 2}, scope=Scope(ScopeKind.KIND, C2)))     # still must name a kind


def test_the_gates_of_every_kind_and_the_narrowing_of_offices():
    both = [adopted("second-person-confirmation", {"required": True}, scope=Scope(ScopeKind.KIND, C2), key="two"),
            adopted("recorder", {"recorded_by": (R.SECRETARY, R.TREASURER)}, scope=Scope(ScopeKind.KIND, C2), key="rec"),
            adopted("recorder", {"recorded_by": (R.SECRETARY,)}, scope=Scope(ScopeKind.KIND, C2), key="rec2")]
    got = effective.step_gates("example-cycle", C2, "secretary", controls=both, roster=OFFICERS, today=TODAY)
    assert got.second and got.roles == (R.SECRETARY,) and not got.clash and not got.resolution
    assert sorted(g.gate for g in got.gates) == ["roles", "roles", "second"]
    clash = both + [adopted("recorder", {"recorded_by": (R.TREASURER,)}, scope=Scope(ScopeKind.KIND, C2), key="rec3")]
    assert "no one in common" in effective.step_gates("example-cycle", C2, "secretary", controls=clash, today=TODAY).clash


def test_the_unmet_gates_are_listed_in_the_sentences_the_page_shows():
    got = effective.step_gates("example-cycle", C2, "manager", roster=OFFICERS, today=TODAY, controls=[
        adopted("contract-authorization", {"resolution_first": True}, scope=Scope(ScopeKind.KIND, C2), key="res"),
        adopted("recorder", {"recorded_by": (R.SECRETARY,)}, scope=Scope(ScopeKind.KIND, C2), key="rec"),
        adopted("second-person-confirmation", {"required": True}, scope=Scope(ScopeKind.KIND, C2), key="two")])
    unmet = effective.step_unmet(got, by=MANAGER, held=["manager"], first_by=MANAGER, texts=["no id here"], approved=["d-1"])
    assert [g.reason for g in got.gates if g.gate == "resolution"][0] in unmet
    assert [g.reason for g in got.gates if g.gate == "roles"][0] in unmet
    assert any(u.endswith("A Manager made the first, so a different person confirms") for u in unmet)
    met = effective.step_unmet(got, by=BOTH, held=["manager", "secretary"], first_by=MANAGER, texts=["see d-1."], approved=["d-1"])
    assert met == []
    assert effective.step_unmet(got, by=BOTH, held=["manager", "secretary"], texts=["see d-10"], approved=["d-1"])   # whole id only


def test_a_roster_that_cannot_satisfy_a_gate_in_force_refuses_and_never_weakens_it():
    two = adopted("second-person-confirmation", {"required": True}, scope=Scope(ScopeKind.KIND, C2), key="two")
    one_manager = roster(R.MANAGER, R.SECRETARY)
    got = effective.step_gates("example-cycle", C2, "manager", controls=[two], roster=one_manager, today=TODAY)
    assert got.refusals == (got.gates[0].reason + "; the roster lacks a second manager",)
    assert effective.step_unmet(got, by=MANAGER, held=["manager"])
    rec = adopted("recorder", {"recorded_by": (R.TREASURER,)}, scope=Scope(ScopeKind.KIND, C2), key="rec")
    assert effective.step_gates("example-cycle", C2, "manager", controls=[rec], roster=one_manager, today=TODAY).refusals[0].endswith(
        "the roster has no treasurer")
    assert effective.step_gates("example-cycle", C2, "manager", controls=[rec], roster=None, today=TODAY).refusals == ()   # not read


# --- the engine ----------------------------------------------------------------------------------------------------------------

def test_with_no_controls_configured_nothing_changes_and_nothing_is_read(seated, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the controls were read although none is configured")

    monkeypatch.setattr(store, "load", boom)
    monkeypatch.setattr(effective, "_community_roster", boom)
    rid = start(seated)
    out = api.attest(seated, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", today=TODAY)
    assert out["event"]["kind"] == "attested" and out["run"]["steps"][1]["state"] == "done"


def test_an_injected_gate_refuses_with_its_sentence_and_writes_nothing(seated):
    rid = start(seated)
    n = runs.read(seated, "example-cycle", rid).n
    asked = []

    def gate(ask: StepAsk):
        asked.append(ask)
        return GateVerdict(("because a gate says so",))

    with pytest.raises(StepRefused, match="because a gate says so"):
        api.attest(seated, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", today=TODAY, gates=gate)
    with pytest.raises(StepRefused, match="because a gate says so"):
        api.skip(seated, rid, C2, MANAGER, roles_of=roles_of, reason="not needed", today=TODAY, gates=gate)
    assert runs.read(seated, "example-cycle", rid).n == n
    assert [(a.act, a.step, a.by, a.roles, a.workflow, a.family, a.role) for a in asked] == [
        ("attest", C2, MANAGER, ("manager",), "example-cycle", "example", "manager"),
        ("skip", C2, MANAGER, ("manager",), "example-cycle", "example", "manager")]
    assert "notice-1" in asked[0].texts and "campaign:EX-2099" in asked[0].texts


def test_a_gate_that_cannot_run_refuses_rather_than_letting_the_act_through(seated):
    rid = start(seated)

    def gate(ask):
        raise OSError("the store is not readable")

    with pytest.raises(StepRefused, match="the controls could not be read, so nothing was recorded: OSError"):
        api.attest(seated, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", today=TODAY, gates=gate)
    assert runs.read(seated, "example-cycle", rid).events[-1].kind is not EventKind.ATTESTED


def test_a_resolution_must_be_on_record_before_the_step(seated):
    adopt(seated, "res", "contract-authorization", {"resolution_first": True}, step())
    rid = start(seated)
    with pytest.raises(StepRefused) as caught:
        api.attest(seated, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", today=TODAY)
    why = str(caught.value)
    assert why.startswith("a control the board adopted on 2099-01-01 requires a board resolution on record before this step")
    d = decisions.record(seated, "2099-09-01", "The example notice", "Approve sending the example notice", outcome="tabled")
    with pytest.raises(StepRefused, match="resolution on record"):                  # tabled is not a resolution
        api.attest(seated, rid, C2, MANAGER, roles_of=roles_of, record=f"notice-1 {d.id}", today=TODAY)
    decisions.update(seated, d.id, outcome="approved")
    with pytest.raises(StepRefused, match="resolution on record"):                  # an id that is not cited is not found
        api.attest(seated, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", today=TODAY)
    out = api.attest(seated, rid, C2, MANAGER, roles_of=roles_of, record=f"notice-1, under {d.id}.", today=TODAY)
    assert out["run"]["steps"][1]["state"] == "done"
    other = runs.read(seated, "example-cycle", rid)
    assert other.events[-1].kind is EventKind.ATTESTED


def test_a_step_the_control_does_not_name_is_not_gated(seated):
    adopt(seated, "res", "contract-authorization", {"resolution_first": True}, step(Scope(ScopeKind.KIND, C6)))
    rid = start(seated)
    assert api.attest(seated, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", today=TODAY)["event"]["kind"] == "attested"


def test_a_skip_is_gated_too(seated):
    adopt(seated, "res", "contract-authorization", {"resolution_first": True}, step())
    rid = start(seated)
    with pytest.raises(StepRefused, match="resolution on record"):
        api.skip(seated, rid, C2, MANAGER, roles_of=roles_of, reason="not needed", today=TODAY)
    d = decisions.record(seated, "2099-09-01", "Skip the example notice", "Skip the example notice", outcome="approved")
    assert api.skip(seated, rid, C2, MANAGER, roles_of=roles_of, reason=f"not needed, {d.id}", today=TODAY)["event"]["kind"] == "skipped"


def test_only_the_offices_a_control_names_may_record_the_step(seated):
    adopt(seated, "rec", "recorder", {"recorded_by": (R.SECRETARY,)}, step())
    rid = start(seated)
    with pytest.raises(StepRefused, match="allows only the secretary to record this step"):
        api.attest(seated, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", today=TODAY)
    out = api.attest(seated, rid, C2, BOTH, roles_of=roles_of, record="notice-1", today=TODAY)       # holds the step's role and the office
    assert out["event"]["by"] == BOTH and out["run"]["steps"][1]["state"] == "done"


def test_a_second_person_confirms_and_the_first_cannot_do_both(seated):
    adopt(seated, "two", "second-person-confirmation", {"required": True}, step())
    rid = start(seated)
    first = api.attest(seated, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", today=TODAY)
    assert first["event"]["kind"] == "note" and first["event"]["detail"]["first_of_two"] == "attest"
    assert first["run"]["steps"][1]["state"] == "needs a person"            # the step is not done by one person
    assert api.pending_first(runs.read(seated, "example-cycle", rid).events, C2, "attest") == MANAGER
    with pytest.raises(StepRefused, match="A Manager made the first, so a different person confirms"):
        api.attest(seated, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", today=TODAY)
    with pytest.raises(StepRefused, match="does not hold the manager role"):                  # the engine's own rule still holds
        api.attest(seated, rid, C2, TREASURER, roles_of=roles_of, record="notice-1", today=TODAY)
    second = api.attest(seated, rid, C2, MANAGER_B, roles_of=roles_of, record="notice-1", today=TODAY)
    assert second["event"]["kind"] == "attested" and second["event"]["detail"]["confirms"] == MANAGER
    assert second["run"]["steps"][1]["state"] == "done" and second["run"]["steps"][1]["by"] == MANAGER_B
    assert api.pending_first(runs.read(seated, "example-cycle", rid).events, C2, "attest") == ""


def test_a_roster_with_one_manager_refuses_a_second_person_gate_in_force(seated, monkeypatch):
    monkeypatch.setattr(effective, "_community_roster", lambda: roster(R.MANAGER, R.SECRETARY))
    adopt(seated, "two", "second-person-confirmation", {"required": True}, step())
    rid = start(seated)
    with pytest.raises(StepRefused, match="the roster lacks a second manager"):
        api.attest(seated, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", today=TODAY)
    assert EventKind.NOTE not in kinds_of(rid, seated)


def test_a_control_not_yet_in_force_does_not_gate(seated):
    adopt(seated, "res", "contract-authorization", {"resolution_first": True}, step(), effective_on="2100-01-01")
    rid = start(seated)
    assert api.attest(seated, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", today=TODAY)["event"]["kind"] == "attested"


# --- the run page and the writer -----------------------------------------------------------------------------------------------

def test_the_run_page_has_no_controls_key_when_none_are_configured(app, world):
    rid = start(world)
    got = page(app, MANAGER, rid)
    assert all("controls" not in s for s in got["steps"])
    assert not [p for p in got["problems"] if "control" in p["what"].lower()]


def test_the_run_page_names_the_control_for_each_gate_on_the_steps_it_bites(app, seated):
    adopt(seated, "res", "contract-authorization", {"resolution_first": True}, step())
    adopt(seated, "two", "second-person-confirmation", {"required": True}, step())
    adopt(seated, "soon", "recorder", {"recorded_by": (R.SECRETARY,)}, step(), effective_on="2100-01-01")
    rid = start(seated)
    got = page(app, MANAGER, rid)
    by_id = {s["id"]: s for s in got["steps"]}
    assert all("controls" not in s for i, s in by_id.items() if i != C2)
    rows = {r["gate"]: r for r in by_id[C2]["controls"]}
    assert set(rows) == {"resolution", "second", "roles"}
    res = rows["resolution"]
    assert (res["key"], res["title"], res["state"], res["effective"]) == ("res", "Contract authorization", "in force", "2020-01-01")
    assert res["why"].startswith("a control the board adopted on 2099-01-01 requires a board resolution on record")
    assert rows["second"]["state"] == "in force" and "firstBy" not in rows["second"]
    assert rows["roles"]["state"] == "waiting" and rows["roles"]["effective"] == "2100-01-01" and rows["roles"]["roles"] == ["secretary"]
    assert "will allow, from 2100-01-01, only the secretary" in rows["roles"]["why"]
    assert not [p for p in got["problems"] if "control" in p["what"].lower()]


def test_the_run_page_says_who_made_the_first_of_two(app, seated):
    adopt(seated, "two", "second-person-confirmation", {"required": True}, step())
    rid = start(seated)
    api.attest(seated, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", today=TODAY)
    got = page(app, MANAGER, rid)
    row = {s["id"]: s for s in got["steps"]}[C2]["controls"][0]
    assert row["gate"] == "second" and row["firstBy"] == MANAGER
    assert "as the first of two" in got["history"][0]["text"]


def test_the_writer_answers_with_the_controls_sentence(app, seated):
    adopt(seated, "res", "contract-authorization", {"resolution_first": True}, step())
    adopt(seated, "rec", "recorder", {"recorded_by": (R.SECRETARY,)}, step())
    rid = start(seated)
    n = runs.read(seated, "example-cycle", rid).n
    r = post(as_(app, MANAGER), f"example-cycle/{rid}", {"act": "attest", "step": C2, "record": "notice-1"})
    shown = [g["why"] for g in page(app, MANAGER, rid)["steps"][1]["controls"]]
    assert r.status_code == 403
    assert "allows only the secretary" in r.json["error"] and "board resolution on record" in r.json["error"]
    assert all(why in r.json["error"] for why in shown)        # the page and the refusal say it in the same words
    assert runs.read(seated, "example-cycle", rid).n == n


def test_every_workflow_step_type_in_the_catalog_names_a_pattern():
    for t in CATALOG:
        for pattern in t.categories(effective.GovernsKind.WORKFLOW_STEP):
            assert pattern and " " not in pattern
