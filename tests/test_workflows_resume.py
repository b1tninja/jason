"""The resume check (engine doc section 4, tests 4 and 5): appends only what changed, finds earlier jobs and plans by key,
and never does a person's work."""

from __future__ import annotations

from dataclasses import replace

import pytest

from jason.workflows import api, definitions, resume, store
from jason.workflows.resume import ApprovalState, JobState, Readers
from jason.workflows.types import CheckResult, EventKind as K, OnWithdrawn
from test_workflows_support import (
    C1, C2, C3, C4, C5, C6, DATES, OWNER, TODAY, FakeReaders, data, example, example_cycle, roles_of,
)

SUBJECT = "campaign:EX-2099"


def active(data, rd=None):
    rid = api.start(data, "example-cycle", SUBJECT, "Example", DATES, OWNER, yes=True, today=TODAY)["run"]["id"]
    api.open_run(data, rid, OWNER, readers=rd or FakeReaders(), yes=True, today=TODAY)
    return rid


def kinds(res):
    return [e["kind"] for e in res["appended"]]


def test_resume_appends_nothing_when_nothing_changed(data, example):
    rd = FakeReaders()
    rid = active(data, rd)
    n = api.show(data, rid, today=TODAY)["n"]
    for _ in range(3):
        assert api.open_run(data, rid, OWNER, readers=rd, today=TODAY)["appended"] == []
    assert api.show(data, rid, today=TODAY)["n"] == n
    run = store.open_run(data, rid)
    assert resume.resume(run, example, TODAY, rd) == []


def test_a_changed_store_appends_one_changed_event_and_does_not_undo_the_step(data, example):
    rd = FakeReaders()
    rid = active(data, rd)
    api.attest(data, rid, C2, OWNER, roles_of=roles_of, record="notice-1", readers=rd, today=TODAY)
    assert kinds(api.open_run(data, rid, OWNER, readers=rd, today=TODAY)) == ["plan-made"]
    rd.hashes["store:notices"] = "n999"
    res = api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    assert kinds(res) == ["changed"]
    ev = res["appended"][0]
    assert ev["step"] == C2 and ev["by"] == "jason"
    assert ev["detail"]["differences"] == [{"address": "store:notices", "was": "n111", "now": "n999"}]
    step = next(s for s in res["run"]["steps"] if s["id"] == C2)
    assert step["state"] == "done" and step["changed"]
    assert api.open_run(data, rid, OWNER, readers=rd, today=TODAY)["appended"] == []
    rd.hashes["store:notices"] = "n1000"
    assert kinds(api.open_run(data, rid, OWNER, readers=rd, today=TODAY)) == ["changed"]    # a further move is a further event
    # an unreadable store (None) is not a change
    rd.hashes.pop("store:notices")
    assert api.open_run(data, rid, OWNER, readers=rd, today=TODAY)["appended"] == []


def test_a_job_and_a_plan_are_found_again_by_their_key(data, example):
    """If the engine queued the job but crashed before it wrote the event, the next open finds the job, not a second one."""
    rd = FakeReaders()
    rid = active(data, rd)
    api.attest(data, rid, C2, OWNER, roles_of=roles_of, record="r", today=TODAY)
    key = resume.idem_key(rid, C3, SUBJECT)
    rd.approvals[key] = ApprovalState("ap-early", "planned")            # a plan made by an earlier open that died
    res = api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    assert rd.plans_made == []
    assert res["appended"][0]["detail"] == {"key": key, "approval": "ap-early", "found": True}
    rd.approvals[key] = ApprovalState("ap-early", "applied")
    jkey = resume.idem_key(rid, C4, SUBJECT)
    rd.jobs[jkey] = JobState("job-early", "running")
    res = api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    assert rd.jobs_queued == []
    assert [e["detail"].get("job") for e in res["appended"] if e["kind"] == "job-queued"] == ["job-early"]
    assert resume.idem_key("a", "b", "c") != resume.idem_key("a", "b", "c", "item") == resume.idem_key("a", "b", "c", "item")


def test_opening_twice_makes_one_job_and_one_plan(data, example):
    rd = FakeReaders()
    rid = active(data, rd)
    api.attest(data, rid, C2, OWNER, roles_of=roles_of, record="r", today=TODAY)
    for _ in range(3):
        api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    assert len(rd.plans_made) == 1 and rd.jobs_queued == []             # the job waits for the plan to be applied
    key = resume.idem_key(rid, C3, SUBJECT)
    rd.approvals[key] = ApprovalState("ap-1", "applied")
    for _ in range(3):
        api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    assert len(rd.plans_made) == 1 and len(rd.jobs_queued) == 1


def test_resume_never_marks_a_person_done_decides_or_applies(data, example):
    """Whatever the readers say, a person's step and a decision stay open and a plan is only read."""
    rd = FakeReaders()
    rd.arrivals.update({C2: "yes", C6: "yes"})
    rid = active(data, rd)
    for _ in range(2):
        api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    shown = api.show(data, rid, today=TODAY)
    assert {s["id"]: s["state"] for s in shown["steps"]}[C2] == "needs a person"
    events = api.show(data, rid, today=TODAY, events=True)["events"]
    assert not [e for e in events if e["kind"] in ("attested", "decided", "applied", "approval-decided")]
    assert {e["by"] for e in events[1:]} <= {"jason", OWNER}


def test_a_withdrawn_plan_fails_or_skips_as_the_definition_says(data, example):
    rd = FakeReaders()
    rid = active(data, rd)
    api.attest(data, rid, C2, OWNER, roles_of=roles_of, record="r", today=TODAY)
    api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    key = resume.idem_key(rid, C3, SUBJECT)
    rd.approvals[key] = ApprovalState("ap-1", "withdrawn", "wrong list")
    res = api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    assert kinds(res) == ["approval-decided"] and res["run"]["state"] == "failed"
    assert next(s for s in res["run"]["steps"] if s["id"] == C3)["reason"] == "approval withdrawn: wrong list"
    # the same plan, defined to skip on withdrawal
    skipping = replace(example, steps=tuple(replace(s, on_withdrawn=OnWithdrawn.SKIP) if s.id == C3 else s for s in example.steps))
    definitions.register(skipping, plan_kinds={"example-plan"}, jobs={"example-report"})
    rid2 = api.start(data, "example-cycle", "campaign:EX-2100", "Next", DATES, OWNER, yes=True, today=TODAY)["run"]["id"]
    api.open_run(data, rid2, OWNER, readers=rd, yes=True, today=TODAY)
    api.attest(data, rid2, C2, OWNER, roles_of=roles_of, record="r", today=TODAY)
    api.open_run(data, rid2, OWNER, readers=rd, today=TODAY)
    rd.approvals[resume.idem_key(rid2, C3, "campaign:EX-2100")] = ApprovalState("ap-9", "withdrawn")
    res = api.open_run(data, rid2, OWNER, readers=rd, today=TODAY)
    assert {s["id"]: s["state"] for s in res["run"]["steps"]}[C3] == "skipped"


def test_a_job_that_failed_stops_the_step_and_says_why(data, example):
    rd = FakeReaders()
    rid = active(data, rd)
    api.attest(data, rid, C2, OWNER, roles_of=roles_of, record="r", today=TODAY)
    api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    rd.approvals[resume.idem_key(rid, C3, SUBJECT)] = ApprovalState("ap-1", "applied")
    api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    rd.jobs[resume.idem_key(rid, C4, SUBJECT)] = JobState("job-1", "failed", "out of commit")
    res = api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    step = next(s for s in res["run"]["steps"] if s["id"] == C4)
    assert step["state"] == "failed" and step["reason"] == "out of commit" and res["run"]["state"] == "failed"


def test_readers_that_know_nothing_start_nothing(data, example):
    rid = api.start(data, "example-cycle", SUBJECT, "Example", DATES, OWNER, yes=True, today=TODAY)["run"]["id"]
    res = api.open_run(data, rid, OWNER, readers=Readers(), yes=True, today=TODAY)
    assert kinds(res) == ["resumed", "check-ran"]          # the step's own check runs; nothing else exists to read
    api.attest(data, rid, C2, OWNER, roles_of=roles_of, record="r", today=TODAY)
    assert api.open_run(data, rid, OWNER, readers=Readers(), today=TODAY)["appended"] == []


def test_a_wait_notes_when_it_began_and_a_branch_fact_picks_a_path(data):
    from jason.workflows.types import Choice, Role, StepDef, StepKind, Workflow

    wf = Workflow("branching", "B", "f", "unit", dates=(), steps=(
        StepDef("b.1", "Read the fact", StepKind.BRANCH, role=Role.JASON, check=lambda v: CheckResult(True, (), "", "fast"),
                choices=(Choice("fast", ("b.2",)), Choice("slow", ("b.3",)))),
        StepDef("b.2", "Fast", StepKind.WAIT, needs=("b.1",)), StepDef("b.3", "Slow", StepKind.WAIT, needs=("b.1",))))
    definitions.reset()
    try:
        definitions.register(wf)
        rid = api.start(data, "branching", "unit:1", "B", {}, OWNER, today=TODAY)["run"]["id"]
        res = api.open_run(data, rid, OWNER, readers=Readers(), today=TODAY)
        assert kinds(res) == ["resumed", "check-ran", "waited"]
        states = {s["id"]: s["state"] for s in res["run"]["steps"]}
        assert states == {"b.1": "done", "b.2": "waiting", "b.3": "skipped"} and res["run"]["state"] == "waiting"
        assert api.open_run(data, rid, OWNER, readers=Readers(), today=TODAY)["appended"] == []
    finally:
        definitions.reset()
