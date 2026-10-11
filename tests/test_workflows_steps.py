"""The step-kind contracts (engine doc section 5 and test 6): who may record what, and what is refused."""

from __future__ import annotations

import pytest

from jason.workflows import fold, steps
from jason.workflows.types import (
    Choice, Event, EventKind as K, Role, SkipRule, StepDef, StepKind, StepRefused, Workflow,
)
from test_workflows_fold import ATTESTED, CHECK_OK, evs
from test_workflows_support import C1, C2, C3, C4, C5, C6, OWNER, SECRETARY, TODAY, TREASURER, VISITOR, example_cycle, roles_of

WF = example_cycle()
THROUGH_5 = [CHECK_OK, ATTESTED, (K.APPLIED, C3), (K.JOB_FINISHED, C4, {"ok": True}), (K.ARRIVED, C5)]


def view(*rows, **kw):
    return fold.state(evs((K.RESUMED, "", {"activated": True}), *rows, draft=True, **kw), WF, TODAY, run_id="run-x")


def attest(v, step, by, **kw):
    return steps.attest_act(WF, v, step, by=by, roles_of=roles_of, **kw)


def test_a_person_step_refuses_a_name_without_the_role_and_a_missing_record():
    v = view(CHECK_OK)
    act = attest(v, C2, OWNER, record="notice-1")
    assert act.kind is K.ATTESTED and act.detail["record"] == "notice-1"
    for who in (VISITOR, TREASURER, SECRETARY):
        with pytest.raises(StepRefused, match="does not hold the manager role"):
            attest(v, C2, who, record="notice-1")
    with pytest.raises(StepRefused, match="asks for a record"):
        attest(v, C2, OWNER)
    with pytest.raises(StepRefused, match="asks for a record"):
        attest(v, C2, OWNER, record="   ")


def test_an_attestation_is_never_recorded_for_someone_else_or_for_the_engine():
    v = view(CHECK_OK)
    for system in ("jason", "Scheduler", ""):
        with pytest.raises(StepRefused):
            attest(v, C2, system, record="r")
    # a caller that supplies no roles gets none: every act that needs one is refused
    with pytest.raises(StepRefused, match="does not hold"):
        steps.attest_act(WF, v, C2, by=OWNER, roles_of=None, record="r")
    # a role the table does not know is ignored, not trusted
    with pytest.raises(StepRefused, match="does not hold"):
        steps.attest_act(WF, v, C2, by=OWNER, roles_of=lambda by: ["owner of the run", "wizard"], record="r")
    # the step must be waiting on a person now
    with pytest.raises(StepRefused, match="not waiting on a person"):
        attest(view(), C2, OWNER, record="r")
    with pytest.raises(StepRefused, match="not waiting on a person"):
        attest(view(CHECK_OK, ATTESTED), C2, OWNER, record="r")


def test_a_decision_is_recorded_only_by_the_named_role_never_by_the_runs_owner():
    v = view(*THROUGH_5)
    act = attest(v, C6, SECRETARY, record="minutes-1", outcome="Adopted")
    assert act.kind is K.DECIDED and act.detail["outcome"] == "adopted" and act.detail["motion"] == WF.step(C6).title
    with pytest.raises(StepRefused, match="opening the run gives no standing"):
        attest(v, C6, OWNER, record="minutes-1", outcome="adopted")          # the owner of the run, a manager
    with pytest.raises(StepRefused, match="does not hold the secretary"):
        attest(v, C6, TREASURER, record="minutes-1", outcome="adopted")
    with pytest.raises(StepRefused, match="outcome"):
        attest(v, C6, SECRETARY, record="minutes-1")
    with pytest.raises(StepRefused, match="record that shows it"):
        attest(v, C6, SECRETARY, outcome="adopted")
    # an owner who is also the secretary is the secretary
    both = lambda by: ["manager", "secretary"]  # noqa: E731
    assert steps.attest_act(WF, v, C6, by=OWNER, roles_of=both, record="m", outcome="adopted").kind is K.DECIDED


def test_a_plan_step_is_never_attested_and_a_check_or_job_is_done_by_its_result():
    v = view(CHECK_OK, ATTESTED)
    for who in (OWNER, SECRETARY):
        with pytest.raises(StepRefused, match="plan step"):
            attest(v, C3, who, record="r")
    with pytest.raises(StepRefused, match="check step"):
        attest(view(), C1, OWNER, record="r")
    with pytest.raises(StepRefused, match="job step"):
        attest(view(CHECK_OK, ATTESTED, (K.APPLIED, C3)), C4, OWNER, record="r")
    with pytest.raises(StepRefused, match="wait step"):
        attest(view(CHECK_OK, ATTESTED, (K.APPLIED, C3), (K.JOB_FINISHED, C4, {"ok": True})), C5, OWNER, record="r")


def test_a_person_says_what_arrived_and_only_in_the_steps_role():
    v = view(CHECK_OK, ATTESTED, (K.APPLIED, C3), (K.JOB_FINISHED, C4, {"ok": True}))
    act = steps.arrived_act(WF, v, C5, by=OWNER, roles_of=roles_of, what="the Example Alarm reply")
    assert act.kind is K.ARRIVED and act.detail["what"] == "the Example Alarm reply"
    with pytest.raises(StepRefused, match="does not hold"):
        steps.arrived_act(WF, v, C5, by=VISITOR, roles_of=roles_of)
    with pytest.raises(StepRefused, match="not a wait step"):
        steps.arrived_act(WF, v, C2, by=OWNER, roles_of=roles_of)


def test_skip_needs_a_rule_a_role_and_a_reason_and_a_legal_step_has_none():
    v = view(CHECK_OK)
    act = steps.skip_act(WF, v, C2, by=OWNER, roles_of=roles_of, reason="the owners were told by the board")
    assert act.kind is K.SKIPPED
    with pytest.raises(StepRefused, match="needs a reason"):
        steps.skip_act(WF, v, C2, by=OWNER, roles_of=roles_of)
    with pytest.raises(StepRefused, match="may not skip"):
        steps.skip_act(WF, v, C2, by=VISITOR, roles_of=roles_of, reason="x")
    with pytest.raises(StepRefused, match="no skip rule"):
        steps.skip_act(WF, view(CHECK_OK, ATTESTED), C3, by=OWNER, roles_of=roles_of, reason="x")
    with pytest.raises(StepRefused, match="legal step"):
        steps.skip_act(WF, view(*THROUGH_5[:4]), C5, by=OWNER, roles_of=roles_of, reason="x")
    with pytest.raises(StepRefused, match="already done"):
        steps.skip_act(WF, view(CHECK_OK, ATTESTED), C2, by=OWNER, roles_of=roles_of, reason="x")


def test_reopen_is_a_persons_act_with_a_reason():
    v = view(CHECK_OK, ATTESTED)
    assert steps.reopen_act(WF, v, C2, by=OWNER, roles_of=roles_of, reason="wrong notice").kind is K.REOPENED
    with pytest.raises(StepRefused, match="reason"):
        steps.reopen_act(WF, v, C2, by=OWNER, roles_of=roles_of)
    with pytest.raises(StepRefused, match="does not hold"):
        steps.reopen_act(WF, v, C2, by=VISITOR, roles_of=roles_of, reason="x")
    with pytest.raises(StepRefused, match="engine's own name"):
        steps.reopen_act(WF, v, C2, by="jason", roles_of=roles_of, reason="x")
    with pytest.raises(StepRefused, match="only a done"):
        steps.reopen_act(WF, view(CHECK_OK), C2, by=OWNER, roles_of=roles_of, reason="x")


def test_a_branch_with_no_fact_is_answered_by_a_person_from_its_paths():
    wf = Workflow("w", "W", "f", "unit", dates=(), steps=(
        StepDef("w.1", "Ask which", StepKind.BRANCH, role=Role.MANAGER, choices=(Choice("a", ()), Choice("b", ()))),
        StepDef("w.2", "Read which", StepKind.BRANCH, role=Role.JASON, check=lambda v: None, choices=(Choice("a", ()),))))
    v = fold.state([Event(1, K.OPENED, OWNER, "x", detail={"subject": "s"})], wf, TODAY)
    act = steps.attest_act(wf, v, "w.1", by=OWNER, roles_of=roles_of, choice="a")
    assert act.detail["choice"] == "a"
    with pytest.raises(StepRefused, match="choose one of a, b"):
        steps.attest_act(wf, v, "w.1", by=OWNER, roles_of=roles_of, choice="c")
    with pytest.raises(StepRefused, match="fact jason reads"):
        steps.attest_act(wf, v, "w.2", by=OWNER, roles_of=roles_of, choice="a")


def test_run_acts_pause_resume_note_activate_and_cancel():
    active = view(CHECK_OK)
    assert steps.pause_act(active, by=OWNER, reason="hold").kind is K.PAUSED
    with pytest.raises(StepRefused, match="needs a reason"):
        steps.pause_act(active, by=OWNER, reason="")
    paused = view(CHECK_OK, (K.PAUSED, "", {"reason": "hold"}))
    assert steps.resume_act(paused, by=OWNER).kind is K.RESUMED
    with pytest.raises(StepRefused, match="not paused"):
        steps.resume_act(active, by=OWNER)
    with pytest.raises(StepRefused, match="needs text"):
        steps.note_act(active, by=OWNER, text=" ")
    with pytest.raises(StepRefused, match="legal clock"):
        steps.cancel_act(WF, active, by=OWNER, roles_of=roles_of, reason="stop")
    assert steps.cancel_act(WF, active, by=OWNER, roles_of=roles_of, reason="stop", yes=True).detail["legal_clock"] is True
    gone = view((K.CANCELLED, "", {"reason": "stop"}))
    with pytest.raises(StepRefused, match="already cancelled"):
        steps.cancel_act(WF, gone, by=OWNER, roles_of=roles_of, reason="again", yes=True)
    # a run with no legal clock cancels without yes
    plain = Workflow("w", "W", "f", "unit", dates=(), steps=(StepDef("w.1", "Do it", StepKind.PERSON),))
    v = fold.state([Event(1, K.OPENED, OWNER, "x", detail={"subject": "s"})], plain, TODAY)
    assert steps.cancel_act(plain, v, by=VISITOR, roles_of=roles_of, reason="stop").detail["legal_clock"] is False
