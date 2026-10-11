"""The fold (engine doc section 4, tests 1): pure, deterministic, prefix-replayable, and the step and run states."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from pathlib import Path

from jason.workflows import fold
from jason.workflows.types import (
    Choice, ClockBasis, ClockDef, Elapsed, Event, EventKind as K, OnWithdrawn, Repeat, RunState, StepDef, StepKind,
    StepState as S, Workflow, Role,
)
from test_workflows_support import C1, C2, C3, C4, C5, C6, DATES, OWNER, SECRETARY, TODAY, example_cycle


def evs(*rows, draft=False, items=(), dates=DATES):
    """Events from (kind, step, detail) rows, numbered in order; the first is the opening."""
    opened = {"subject": "campaign:EX-2099", "label": "Example", "dates": dates}
    if draft:
        opened["draft"] = True
    if items:
        opened["items"] = list(items)
    out = [Event(1, K.OPENED, OWNER, "2099-09-15T09:00:00Z", detail=opened)]
    for i, row in enumerate(rows, 2):
        kind, step, *rest = row
        out.append(Event(i, kind, "jason", f"2099-09-15T09:{i:02d}:00Z", step=step, detail=rest[0] if rest else {}))
    return out


def st(view):
    return {s.id: s.state for s in view.steps}


CHECK_OK = (K.CHECK_RAN, C1, {"ok": True, "evidence": ["store:example@aaaa11"]})
ATTESTED = (K.ATTESTED, C2, {"record": "notice-1"})


def test_the_fold_is_pure_and_a_prefix_gives_the_earlier_view():
    wf = example_cycle()
    events = evs(CHECK_OK, ATTESTED)
    a = fold.state(events, wf, TODAY, run_id="run-x")
    b = fold.state(events, wf, TODAY, run_id="run-x")
    assert a == b
    earlier = fold.state(events[:2], wf, TODAY, run_id="run-x")
    assert st(earlier)[C2] is S.NEEDS_PERSON and st(a)[C2] is S.DONE
    assert earlier.n == 2 and a.n == 3
    assert fold.state(events[:2], wf, TODAY, run_id="run-x") == earlier        # replaying the prefix again is the same
    assert fold.state(events, wf, TODAY, run_id="run-x") == a                  # and the full run is unchanged by it


def test_no_wall_clock_is_read_inside_the_fold():
    text = (Path(fold.__file__)).read_text(encoding="utf-8")
    assert not re.search(r"date\.today|datetime\.(now|utcnow|today)|time\.(time|monotonic)|import time", text)
    wf = example_cycle()
    events = evs(CHECK_OK)
    early = fold.state(events, wf, date(2099, 9, 1))
    late = fold.state(events, wf, date(2099, 12, 1))
    assert st(early) == st(late)                                                # states do not depend on the day...
    assert [c.status for c in early.clocks] != [c.status for c in late.clocks]  # ...only the clocks do


def test_readiness_blocking_and_the_current_step():
    wf = example_cycle()
    v = fold.state(evs(), wf, TODAY)
    assert st(v)[C1] is S.READY and st(v)[C2] is S.NOT_STARTED and v.current == C1
    v = fold.state(evs((K.CHECK_RAN, C1, {"ok": False, "message": "missing"})), wf, TODAY)
    assert st(v)[C1] is S.FAILED and st(v)[C2] is S.BLOCKED and v.state is RunState.FAILED
    assert v.step(C1).reason == "missing" and v.step(C2).blocked_by == (C1,)
    v = fold.state(evs(CHECK_OK), wf, TODAY)
    assert st(v)[C2] is S.NEEDS_PERSON and v.current == C2 and v.state is RunState.ACTIVE


def test_each_kind_reaches_done_and_the_run_is_done_at_the_end():
    wf = example_cycle()
    rows = [CHECK_OK, ATTESTED,
            (K.PLAN_MADE, C3, {"approval": "ap-1"}), (K.APPROVAL_DECIDED, C3, {"status": "approved"}),
            (K.APPLIED, C3, {}), (K.JOB_QUEUED, C4, {"job": "job-1"}), (K.JOB_FINISHED, C4, {"ok": True}),
            (K.WAITED, C5, {}), (K.ARRIVED, C5, {"what": "answer"}),
            (K.DECIDED, C6, {"outcome": "adopted", "record": "minutes-1"})]
    states = []
    for i in range(1, len(rows) + 1):
        states.append(fold.state(evs(*rows[:i]), wf, TODAY))
    assert st(states[2])[C3] is S.WAITING and states[2].step(C3).reason == "approval planned"
    assert st(states[3])[C3] is S.WAITING and states[3].step(C3).reason == "approval approved"
    assert st(states[5])[C4] is S.RUNNING
    assert st(states[7])[C5] is S.WAITING and states[7].state is RunState.WAITING
    assert st(states[8])[C6] is S.NEEDS_PERSON
    last = states[-1]
    assert last.state is RunState.DONE and set(st(last).values()) == {S.DONE} and last.current == ""
    assert [l.address for l in last.links] == ["ap-1", "job-1"]
    assert [l.kind for l in last.links] == ["approval", "job"]


def test_a_decision_is_done_only_by_a_final_outcome():
    wf = example_cycle()
    base = [CHECK_OK, ATTESTED, (K.APPLIED, C3), (K.JOB_FINISHED, C4, {"ok": True}), (K.ARRIVED, C5)]
    v = fold.state(evs(*base, (K.DECIDED, C6, {"outcome": "tabled"})), wf, TODAY)
    assert st(v)[C6] is S.NEEDS_PERSON and "not final" in v.step(C6).reason
    v = fold.state(evs(*base, (K.DECIDED, C6, {"outcome": "tabled"}), (K.DECIDED, C6, {"outcome": "rejected", "record": "m"})), wf, TODAY)
    assert st(v)[C6] is S.DONE


def test_a_changed_event_never_undoes_a_step_but_a_reopen_does():
    wf = example_cycle()
    changed = (K.CHANGED, C2, {"differences": [{"address": "store:notices", "was": "n1", "now": "n2"}],
                               "evidence": ["store:notices@n2"]})
    v = fold.state(evs(CHECK_OK, ATTESTED, changed), wf, TODAY)
    assert st(v)[C2] is S.DONE and v.step(C2).changed[0]["now"] == "n2" and v.step(C2).evidence == ("store:notices@n2",)
    v = fold.state(evs(CHECK_OK, ATTESTED, changed, (K.REOPENED, C2, {"reason": "again"})), wf, TODAY)
    assert st(v)[C2] is S.NEEDS_PERSON and v.step(C2).changed == ()


def test_skipped_superseded_and_a_withdrawn_plan():
    wf = example_cycle()
    v = fold.state(evs(CHECK_OK, (K.SKIPPED, C2, {"reason": "not needed"})), wf, TODAY)
    assert st(v)[C2] is S.SKIPPED and st(v)[C3] is S.READY and v.step(C2).reason == "not needed"
    v = fold.state(evs(CHECK_OK, ATTESTED, (K.PLAN_MADE, C3, {"approval": "ap-1"}),
                       (K.APPROVAL_DECIDED, C3, {"status": "withdrawn", "reason": "wrong list"})), wf, TODAY)
    assert st(v)[C3] is S.FAILED and "wrong list" in v.step(C3).reason and v.state is RunState.FAILED
    skip_wf = example_cycle(steps=tuple(
        replace(s, on_withdrawn=OnWithdrawn.SKIP) if s.id == C3 else s for s in wf.steps))
    v = fold.state(evs(CHECK_OK, ATTESTED, (K.PLAN_MADE, C3, {"approval": "ap-1"}),
                       (K.APPROVAL_DECIDED, C3, {"status": "withdrawn"})), skip_wf, TODAY)
    assert st(v)[C3] is S.SKIPPED and st(v)[C4] is S.READY
    v = fold.state(evs(CHECK_OK, (K.PLAN_MADE, C3, {"approval": "ap-2", "supersedes": C2})), wf, TODAY)
    assert st(v)[C2] is S.SUPERSEDED and st(v)[C3] is S.NOT_STARTED       # a superseded step does not satisfy a needs


def test_draft_paused_and_cancelled_runs():
    wf = example_cycle()
    v = fold.state(evs(draft=True), wf, TODAY)
    assert v.state is RunState.DRAFT and all(c.status in ("not running", "undated") for c in v.clocks)
    v = fold.state(evs((K.RESUMED, "", {"activated": True}), (K.PAUSED, "", {"reason": "hold"})), wf, TODAY)
    assert v.state is RunState.PAUSED and v.paused_reason == "hold"
    v = fold.state(evs((K.RESUMED, "", {"activated": True}), (K.PAUSED, "", {"reason": "hold"}), (K.RESUMED, "")), wf, TODAY, )
    assert v.state is RunState.ACTIVE
    v = fold.state(evs((K.CANCELLED, "", {"reason": "dropped"})), wf, TODAY)
    assert v.state is RunState.CANCELLED and v.cancelled_reason == "dropped"


def test_clocks_have_a_basis_and_a_past_law_clock_is_named():
    wf = example_cycle()
    v = fold.state(evs(CHECK_OK), wf, date(2099, 10, 20))
    law = next(c for c in v.clocks if c.basis is ClockBasis.LAW)
    assert (law.due, law.status, law.days, law.cite, law.step) == ("2099-10-23", "upcoming", 3, "EX 123.4", C5)
    assert fold.state(evs(CHECK_OK), wf, date(2099, 10, 23)).clocks[1].status == "due"
    late = fold.state(evs(CHECK_OK), wf, date(2099, 10, 24))
    assert late.past_law == (C5,) and next(c for c in late.clocks if c.step == C5).status == "overdue"
    assert [c.basis for c in late.clocks] == [ClockBasis.PERSON, ClockBasis.LAW]
    arrived = fold.state(evs(CHECK_OK, ATTESTED, (K.APPLIED, C3), (K.JOB_FINISHED, C4, {"ok": True}), (K.ARRIVED, C5)), wf,
                         date(2099, 10, 24))
    assert arrived.past_law == () and next(c for c in arrived.clocks if c.step == C5).status == "satisfied"
    assert fold.state(evs(CHECK_OK, dates={}), wf, TODAY).clocks[0].status == "undated"


def test_a_wait_the_date_ends_and_one_that_stays_overdue():
    ends = ClockDef(ClockBasis.COUNTERPARTY, "answers_by", 0, label="the vendor's quote")
    wf = Workflow("w", "W", "f", "unit", dates=example_cycle().dates, steps=(
        StepDef("w.1", "Wait for the quote", StepKind.WAIT, clock=ends, elapsed=Elapsed.ENDS),
        StepDef("w.2", "Wait for a reply", StepKind.WAIT, clock=ends)))
    before = fold.state(evs(), wf, date(2099, 10, 1))
    assert st(before) == {"w.1": S.WAITING, "w.2": S.WAITING} and before.state is RunState.WAITING
    after = fold.state(evs(), wf, date(2099, 11, 1))
    assert st(after) == {"w.1": S.DONE, "w.2": S.WAITING} and "past" in after.step("w.2").reason


def test_per_item_steps_and_a_branch_and_a_child_run():
    wf = Workflow("w", "W", "f", "campaign", dates=(), steps=(
        StepDef("w.1", "Mail each building's notice", StepKind.PERSON, repeat=Repeat.PER_ITEM),
        StepDef("w.2", "Choose the path", StepKind.BRANCH, role=Role.MANAGER, needs=("w.1",),
                choices=(Choice("fast", ("w.3",)), Choice("slow", ("w.4",)))),
        StepDef("w.3", "Fast path", StepKind.PERSON, needs=("w.2",)),
        StepDef("w.4", "Slow path", StepKind.PERSON, needs=("w.2",)),
        StepDef("w.5", "Start the delivery run", StepKind.JOB, job="delivery", spawns="delivery", needs=("w.3",))))
    events = evs((K.ATTESTED, "w.1", {"item": "building-a"}), items=("building-a", "building-b"), dates={})
    v = fold.state(events, wf, TODAY)
    assert v.step("w.1").items == (("building-a", S.DONE), ("building-b", S.NEEDS_PERSON))
    assert v.step("w.1").state is S.NEEDS_PERSON and "1 of 2" in v.step("w.1").reason
    both = events + [Event(3, K.ATTESTED, OWNER, "x", "w.1", {"item": "building-b"})]
    v = fold.state(both, wf, TODAY)
    assert st(v)["w.1"] is S.DONE and st(v)["w.2"] is S.NEEDS_PERSON       # no check: a person's answer
    chose = both + [Event(4, K.ATTESTED, OWNER, "x", "w.2", {"choice": "fast"})]
    v = fold.state(chose, wf, TODAY)
    assert st(v)["w.3"] is S.NEEDS_PERSON and st(v)["w.4"] is S.SKIPPED and v.step("w.4").by == "jason"
    assert "fast" in v.step("w.4").reason
    spawned = chose + [Event(5, K.ATTESTED, OWNER, "x", "w.3", {}), Event(6, K.SPAWNED, OWNER, "x", "w.5", {"child": "run-child"})]
    v = fold.state(spawned, wf, TODAY)
    assert st(v)["w.5"] is S.WAITING and v.children == ("run-child",) and "not finished" in v.step("w.5").reason
    assert [l.kind for l in v.links] == ["run"]
    v = fold.state(spawned, wf, TODAY, children={"run-child": "running"})
    assert st(v)["w.5"] is S.WAITING and "running" in v.step("w.5").reason
    for child_state in ("done", "cancelled"):
        v = fold.state(spawned, wf, TODAY, children={"run-child": child_state})
        assert st(v)["w.5"] is S.DONE and v.state is RunState.DONE


def test_events_for_a_step_the_definition_no_longer_has_are_listed():
    v = fold.state(evs((K.NOTE, "example-cycle.99", {"text": "old"})), example_cycle(), TODAY)
    assert v.orphans == ("example-cycle.99",)
