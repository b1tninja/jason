"""The registry and ``validate`` (engine doc section 2 and tests 7 and 9)."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from jason.workflows import definitions
from jason.workflows.types import (
    Choice, ClockBasis, ClockDef, DateSlot, InvalidWorkflow, Phase, Role, SkipRule, StepDef, StepKind, Workflow,
)
from test_workflows_support import C1, C2, C3, C4, C5, C6, example_cycle

KINDS, JOBS = {"example-plan"}, {"example-report"}


def check(wf, **kw):
    return definitions.validate(wf, plan_kinds=kw.pop("plan_kinds", KINDS), jobs=kw.pop("jobs", JOBS), **kw)


def codes(problems):
    return sorted((p.row, p.code) for p in problems)


def with_step(wf, step_id, **changes):
    return replace(wf, steps=tuple(replace(s, **changes) if s.id == step_id else s for s in wf.steps))


@pytest.fixture(autouse=True)
def _clean():
    definitions.reset()
    yield
    definitions.reset()


def test_the_example_definition_is_valid():
    assert check(example_cycle()) == []


def test_a_missing_step_a_repeat_and_a_cycle_are_refused():
    wf = with_step(example_cycle(), C3, needs=("example-cycle.99",))
    assert codes(check(wf)) == [(C3, "needs")]
    assert "example-cycle.99" in str(check(wf)[0])                      # the failure names the row and what is wrong
    dup = replace(example_cycle(), steps=example_cycle().steps + (example_cycle().steps[0],))
    assert (C1, "duplicate") in codes(check(dup))
    loop = with_step(with_step(example_cycle(), C1, needs=(C3,), check=None), C2, needs=(C1,))
    problems = check(loop)
    assert any(p.code == "cycle" for p in problems) and "->" in next(p.message for p in problems if p.code == "cycle")
    assert codes(check(with_step(example_cycle(), C1, needs=(C1,)))) == [(C1, "cycle")]


def test_a_plan_kind_or_a_job_that_is_not_registered_is_refused():
    assert codes(check(example_cycle(), plan_kinds={"another-plan"})) == [(C3, "plan")]
    assert codes(check(example_cycle(), jobs={"another-job"})) == [(C4, "job")]
    assert codes(check(with_step(example_cycle(), C3, plan_kind=""))) == [(C3, "plan")]
    assert codes(check(with_step(example_cycle(), C4, job=""))) == [(C4, "job")]
    # with no registry given the engine skips the job check (there is no job registry to ask), and asks the approvals
    # registry for the plan kinds
    assert definitions.validate(example_cycle(), plan_kinds=KINDS) == []
    unregistered = definitions.validate(example_cycle(), jobs=JOBS)
    assert [(p.row, p.code) for p in unregistered] == [(C3, "plan")]    # "example-plan" is not a real approvals kind


def test_a_legal_step_with_a_skip_rule_is_refused():
    assert codes(check(with_step(example_cycle(), C5, skip=SkipRule((Role.MANAGER,))))) == [(C5, "legal-skip")]
    by_flag = with_step(example_cycle(), C2, legal=True)                 # the person step already has a skip rule
    assert codes(check(by_flag)) == [(C2, "legal-skip")]


def test_a_law_clock_must_cite_a_section_that_resolves():
    wf = example_cycle()
    assert check(wf, resolve_law=lambda cite: True) == []
    assert check(wf) == []                                               # no resolver: skipped
    assert check(wf, resolve_law=lambda cite: None) == []                # cannot tell: skipped
    assert codes(check(wf, resolve_law=lambda cite: cite != "EX 123.4")) == [(C5, "law")]
    uncited = with_step(wf, C5, clock=ClockDef(ClockBasis.LAW, "answers_by"))
    assert codes(check(uncited)) == [(C5, "law")]
    on_run = replace(wf, clocks=wf.clocks + (ClockDef(ClockBasis.LAW, "answers_by", cite="EX 9.9"),))
    assert [p.code for p in check(on_run, resolve_law=lambda cite: cite != "EX 9.9")] == ["law"]
    assert codes(check(with_step(wf, C5, clock=ClockDef(ClockBasis.LAW, "no_such_slot", cite="EX 1")))) == [(C5, "clock")]


def test_spawns_must_name_a_definition_when_the_definitions_are_known():
    wf = with_step(example_cycle(), C4, spawns="child-run")
    assert check(wf) == []                                               # not known: skipped at registration
    assert codes(check(wf, workflows={"example-cycle"})) == [(C4, "spawns")]
    assert check(wf, workflows={"example-cycle", "child-run"}) == []


def test_roles_phases_branches_and_dates_are_checked():
    wf = example_cycle()
    assert codes(check(with_step(wf, C6, role=Role.ANYONE))) == [(C6, "role")]
    assert codes(check(with_step(wf, C6, role=Role.JASON))) == [(C6, "role")]
    assert codes(check(with_step(wf, C2, role=Role.JASON))) == [(C2, "role")]
    assert codes(check(replace(wf, phases=(Phase("p", "P", ("nope",)),)))) == [("p", "phase")]
    assert ("a", "date") in codes(check(replace(wf, dates=(DateSlot("a", after="zzz"),))))
    branch = StepDef("b.1", "Which", StepKind.BRANCH, choices=(Choice("x", ("b.9",)),))
    assert (branch.id, "choice") in codes(check(Workflow("b", "B", "f", "unit", steps=(branch,))))
    assert (branch.id, "choice") in codes(check(Workflow("b", "B", "f", "unit", steps=(replace(branch, choices=()),))))
    assert (C1, "sop") in codes(check(with_step(wf, C1, sop="not an address")))


def test_a_definition_that_fails_does_not_register_and_the_failure_names_the_row():
    bad = with_step(example_cycle(), C3, needs=("nope",))
    with pytest.raises(InvalidWorkflow) as err:
        definitions.register(bad, plan_kinds=KINDS, jobs=JOBS)
    assert C3 in str(err.value) and err.value.problems[0].row == C3
    assert definitions.all_definitions() == ()
    with pytest.raises(KeyError, match="no workflow definition"):
        definitions.get("example-cycle")


def test_register_get_override_and_the_extra_hook():
    wf = definitions.register(example_cycle(), plan_kinds=KINDS, jobs=JOBS)
    assert definitions.get("example-cycle") is wf and definitions.find("nope") is None
    other = replace(wf, title="A community's own title")
    asked = []

    def provider():
        asked.append(1)
        return [other, with_step(wf, C3, needs=("broken",))]

    definitions.extra(provider, plan_kinds=KINDS, jobs=JOBS)
    definitions.extra(provider)                                          # a provider is added once
    assert asked == []                                                   # read when asked, not when added
    assert definitions.get("example-cycle").title == "A community's own title"      # the later row overrides
    assert [p.code for p in definitions.rejected()] == ["needs"]         # a provider's bad row is left out, and listed
    definitions.unregister("example-cycle")
    assert definitions.get("example-cycle").title == "A community's own title"       # still the provider's
    definitions.reset()
    assert definitions.all_definitions() == ()


def test_a_step_that_names_a_procedure_step_that_no_longer_exists_is_drift():
    procedures = {"example-procedure": SimpleNamespace(steps=(1, 2, 3))}
    find = procedures.get
    wf = example_cycle()                                                 # C1 is example-procedure#1
    assert definitions.drift([wf], find=find) == []
    gone = with_step(wf, C1, sop="example-procedure#4")
    assert [(p.row, p.code) for p in definitions.drift([gone], find=find)] == [(C1, "drift")]
    assert definitions.drift([with_step(wf, C1, sop="example-procedure#0")], find=find)
    assert definitions.drift([with_step(wf, C1, sop="other#1")], find=find)
    assert definitions.drift([replace(wf, procedure="vanished")], find=find)
    assert definitions.drift([with_step(wf, C1, sop="no address")], find=find)


def test_drift_reads_the_real_procedures_by_default():
    wf = example_cycle(procedure="", steps=(StepDef("x.1", "Do it", StepKind.PERSON, sop="no-such-procedure#1"),))
    assert [p.code for p in definitions.drift([wf])] == ["drift"]
