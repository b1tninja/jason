"""Shared fakes for the workflow engine tests: a made-up 6-step definition (``example-cycle``), fake readers, a role table.

Everything here is plainly fake: "A. Manager", "Example Alarm", "123 Main St", dates in 2099. Nothing reads a real store.
"""

from __future__ import annotations

from datetime import date

import pytest

from jason.workflows import definitions
from jason.workflows.resume import ApprovalState, JobState, Readers
from jason.workflows.types import (
    CheckResult, Choice, ClockBasis, ClockDef, DateSlot, Elapsed, Phase, Role, SkipRule, StepDef, StepKind, Workflow,
)

TODAY = date(2099, 9, 20)
OWNER = "A. Manager"
SECRETARY = "S. Placeholder"
TREASURER = "T. Treasurer"
VISITOR = "V. Visitor"

ROLES = {OWNER: {"manager"}, SECRETARY: {"secretary", "director"}, TREASURER: {"treasurer"}, VISITOR: set()}


def roles_of(by: str):
    return ROLES.get(by, ())


def example_check(view):
    return CheckResult(True, ("store:example@aaaa11",), "the example facts are on file")


C1, C2, C3, C4, C5, C6 = (f"example-cycle.{i}" for i in range(1, 7))


def example_cycle(**over) -> Workflow:
    steps = (
        StepDef(C1, "Confirm the example facts are on file", StepKind.CHECK, role=Role.JASON, check=example_check,
                evidence=("store:example",), sop="example-procedure#1"),
        StepDef(C2, "Send the example notice to 123 Main St", StepKind.PERSON, role=Role.MANAGER, needs=(C1,),
                record="the sent-notice reference", evidence=("store:notices",), skip=SkipRule((Role.MANAGER,)),
                command="example notice --send"),
        StepDef(C3, "Apply the example tags", StepKind.PLAN, role=Role.MANAGER, needs=(C2,), plan_kind="example-plan"),
        StepDef(C4, "Build the example report", StepKind.JOB, role=Role.JASON, needs=(C3,), job="example-report",
                evidence=("store:report",)),
        StepDef(C5, "Wait for the Example Alarm answer", StepKind.WAIT, role=Role.MANAGER, needs=(C4,),
                clock=ClockDef(ClockBasis.LAW, "answers_by", 0, cite="EX 123.4"), legal=True),
        StepDef(C6, "The board adopts the example result", StepKind.DECISION, role=Role.SECRETARY, needs=(C5,),
                record="the minutes reference"),
    )
    base = dict(
        key="example-cycle", title="Example cycle", family="example", subject="campaign", steps=steps,
        dates=(DateSlot("answers_by", "Answers by"), DateSlot("closes_on", "Closes on", after="answers_by")),
        phases=(Phase("prepare", "Prepare", (C1, C2)), Phase("act", "Act", (C3, C4)), Phase("close", "Close", (C5, C6))),
        procedure="example-procedure", clocks=(ClockDef(ClockBasis.PERSON, "closes_on", 0, label="the cycle closes"),),
    )
    base.update(over)
    return Workflow(**base)


DATES = {"answers_by": "2099-10-23", "closes_on": "2099-11-01"}


class FakeReaders(Readers):
    """Reads from dictionaries the test fills, and counts what it was asked to start."""

    def __init__(self):
        self.checks: dict[str, CheckResult] = {}
        self.approvals: dict[str, ApprovalState] = {}
        self.jobs: dict[str, JobState] = {}
        self.hashes: dict[str, str] = {"store:notices": "n111", "store:report": "r111", "store:example": "aaaa11"}
        self.arrivals: dict[str, str] = {}
        self.children: dict[str, str] = {}
        self.plans_made: list[str] = []
        self.jobs_queued: list[str] = []
        self.unreadable: set[str] = set()

    def check(self, step, view, item=""):
        if step.id in self.unreadable:
            raise OSError("the store is not readable")
        return self.checks.get(step.id) or (step.check(view) if step.check else None)

    def approval(self, key):
        return self.approvals.get(key)

    def make_plan(self, kind, key, step, view, item=""):
        self.plans_made.append(key)
        self.approvals[key] = ApprovalState(f"ap-{len(self.plans_made)}", "planned")
        return self.approvals[key].id

    def job(self, key):
        return self.jobs.get(key)

    def queue_job(self, name, key, step, view, item=""):
        self.jobs_queued.append(key)
        self.jobs[key] = JobState(f"job-{len(self.jobs_queued)}", "queued")
        return self.jobs[key].id

    def evidence(self, address):
        return self.hashes.get(address)

    def arrival(self, step, view, item=""):
        return self.arrivals.get(step.id)

    def child_state(self, run_id):
        return self.children.get(run_id)


@pytest.fixture
def data(tmp_path, monkeypatch):
    """A temporary data folder, and a lock folder of its own, so nothing is shared with the machine."""
    monkeypatch.setenv("JASON_LOCK_DIR", str(tmp_path / "locks"))
    return tmp_path / "data"


@pytest.fixture
def example():
    """The made-up definition, registered for the length of one test."""
    definitions.reset()
    wf = definitions.register(example_cycle(), plan_kinds={"example-plan"}, jobs={"example-report"})
    yield wf
    definitions.reset()


def test_the_support_definition_is_valid():
    assert definitions.validate(example_cycle(), plan_kinds={"example-plan"}, jobs={"example-report"}) == []
