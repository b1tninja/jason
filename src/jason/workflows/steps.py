"""The step-kind contracts: what a person may record on a step, and what the engine refuses.

Each function takes the run's folded view and the step's definition and returns an ``Act`` (the event to append) or raises
``StepRefused`` with the reason. They write nothing themselves, so a refusal is testable without a store. The engine takes
``by`` as an argument and trusts no caller: whether ``by`` holds the step's role is asked of ``roles_of(by)``, a function
the caller supplies (the web layer from the sign-in, a test from a table). A caller that supplies none gets no roles, and
every act that needs one is refused.

The rules (docs/workflows-engine.md, section 5):

- ``person``: an attestation by a person holding the step's role, with the record the step asks for. Never for someone else.
- ``decision``: recorded only by the role the step names (the secretary), never because one opened the run, with a motion
  outcome and the record; it is done only by a final outcome.
- ``plan``: never attested. It is done by the approval's status (applied, or withdrawn where the definition says skip).
- ``check`` and ``job``: done by their results. ``wait``: ended by an arrival. ``branch``: by a fact, or by a person's
  answer when the step has no fact to read.
- A step with no skip rule (a legal step among them) cannot be skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from jason.workflows.types import (
    EventKind, Role, RunState, RunView, StepDef, StepKind, StepRefused, StepState, Workflow, is_system,
)

RolesOf = Callable[[str], Iterable["Role | str"]]

CANCEL_ROLES = (Role.SECRETARY, Role.MANAGER)
"""Who may cancel a run with a legal clock: the engine doc recommends the secretary or the manager, with a reason. It is a
decision for the board (the doc's section 10); a caller passes other roles to ``cancel_act``."""

ACTING = (RunState.ACTIVE, RunState.WAITING, RunState.FAILED)


@dataclass(frozen=True)
class Act:
    """The event to append: its kind, its step, and its detail."""

    kind: EventKind
    step: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)


def roles_held(by: str, roles_of: RolesOf | None) -> frozenset[Role]:
    if roles_of is None or not by:
        return frozenset()
    out = set()
    for r in roles_of(by) or ():
        role = Role.parse(r)
        if role is not None:
            out.add(role)
    return frozenset(out)


def may(role: Role, by: str, roles_of: RolesOf | None) -> bool:
    """Whether ``by`` may act under ``role``: a system role only for its own name, ``anyone`` for any named person, an
    office only for a person who holds it."""
    by = (by or "").strip()
    if not by:
        return False
    if role in (Role.JASON, Role.SCHEDULER):
        return by.lower() == role.value
    if is_system(by):
        return False
    if role is Role.ANYONE:
        return True
    return role in roles_held(by, roles_of)


def _person(by: str) -> str:
    by = (by or "").strip()
    if not by:
        raise StepRefused("an act needs a name: by is empty")
    if is_system(by):
        raise StepRefused(f"{by} is the engine's own name; a person's act is recorded under the person's name")
    return by


def _acting(view: RunView) -> None:
    if view.state not in ACTING:
        raise StepRefused(f"the run is {view.state.value}; steps are acted on when it is active")


def _step(workflow: Workflow, view: RunView, step_id: str) -> tuple[StepDef, Any]:
    sd = workflow.step(step_id)
    sv = view.step(step_id)
    if sd is None or sv is None:
        raise StepRefused(f"no step {step_id} in {workflow.key}")
    return sd, sv


def _unit_state(view: RunView, sd: StepDef, item: str) -> StepState:
    sv = view.step(sd.id)
    if item and sv.items:
        known = dict(sv.items)
        if item not in known:
            raise StepRefused(f"{sd.id} has no item {item}")
        return known[item]
    if item and not sv.items:
        raise StepRefused(f"{sd.id} is not a per-item step; item {item} has no meaning")
    if sv.items and not item:
        raise StepRefused(f"{sd.id} is done item by item: say which item")
    return sv.state


def _expect(state: StepState, wanted: StepState, sd: StepDef, why: str = "") -> None:
    if state is not wanted:
        raise StepRefused(f"{sd.id} is {state.value}, not {wanted.value}" + (f": {why}" if why else ""))


def attest_act(workflow: Workflow, view: RunView, step_id: str, *, by: str, roles_of: RolesOf | None, record: str = "",
               what: str = "", item: str = "", outcome: str = "", motion: str = "", choice: str = "",
               evidence: Iterable[str] = ()) -> Act:
    """A person's act on a ``person`` step (an attestation), a ``decision`` step (the board's decision, recorded by the
    secretary), or a ``branch`` step with no fact to read (the person's answer)."""
    _acting(view)
    sd, sv = _step(workflow, view, step_id)
    by = _person(by)
    if sd.kind is StepKind.PLAN:
        raise StepRefused(f"{sd.id} is a plan step: it is done when its approval is applied, never attested; "
                          "decide, submit, and apply the approval in the approvals inbox")
    if sd.kind in (StepKind.CHECK, StepKind.JOB):
        raise StepRefused(f"{sd.id} is a {sd.kind.value} step: it is done by its result, not by a person's word")
    if sd.kind is StepKind.WAIT:
        raise StepRefused(f"{sd.id} is a wait step: an arrival ends it (arrived), not an attestation")
    if sd.kind is StepKind.BRANCH and sd.check is not None:
        raise StepRefused(f"{sd.id} is a branch decided by a fact jason reads, not by a person's answer")
    if not may(sd.role, by, roles_of):
        extra = ""
        if sd.kind is StepKind.DECISION and by == view.owner:
            extra = f"; opening the run gives no standing to record it, the {sd.role.value} records the board's decision"
        raise StepRefused(f"{by} does not hold the {sd.role.value} role that {sd.id} needs{extra}")
    _expect(_unit_state(view, sd, item), StepState.NEEDS_PERSON, sd, "it is not waiting on a person now")
    record = (record or "").strip()
    detail: dict[str, Any] = {}
    if item:
        detail["item"] = item
    evidence = [str(e) for e in evidence]
    if evidence:
        detail["evidence"] = evidence
    if sd.kind is StepKind.DECISION:
        if not (outcome or "").strip():
            raise StepRefused(f"{sd.id}: a decision is recorded with its outcome")
        if not record:
            raise StepRefused(f"{sd.id}: a decision is recorded with the record that shows it ({sd.record or 'the minutes or the decision'})")
        detail.update({"motion": (motion or sd.title).strip(), "outcome": outcome.strip().lower(), "record": record})
        if what:
            detail["what"] = what
        return Act(EventKind.DECIDED, sd.id, detail)
    if sd.kind is StepKind.BRANCH:
        keys = [c.key for c in sd.choices]
        if choice not in keys:
            raise StepRefused(f"{sd.id}: choose one of {', '.join(keys) or '(none defined)'}")
        detail.update({"choice": choice, "what": what or f"chose {choice}"})
        if record:
            detail["record"] = record
        return Act(EventKind.ATTESTED, sd.id, detail)
    if sd.record and not record:
        raise StepRefused(f"{sd.id}: the step asks for a record ({sd.record}); an attestation without one is refused")
    detail.update({"what": what or sd.title})
    if record:
        detail["record"] = record
    return Act(EventKind.ATTESTED, sd.id, detail)


def arrived_act(workflow: Workflow, view: RunView, step_id: str, *, by: str, roles_of: RolesOf | None, what: str = "",
                item: str = "") -> Act:
    """A person's note that what a ``wait`` step waits for has come."""
    _acting(view)
    sd, sv = _step(workflow, view, step_id)
    by = _person(by)
    if sd.kind is not StepKind.WAIT:
        raise StepRefused(f"{sd.id} is not a wait step")
    if not may(sd.role, by, roles_of):
        raise StepRefused(f"{by} does not hold the {sd.role.value} role that {sd.id} needs")
    _expect(_unit_state(view, sd, item), StepState.WAITING, sd)
    detail: dict[str, Any] = {"what": what or sd.title}
    if item:
        detail["item"] = item
    return Act(EventKind.ARRIVED, sd.id, detail)


def skip_act(workflow: Workflow, view: RunView, step_id: str, *, by: str, roles_of: RolesOf | None, reason: str = "",
             item: str = "") -> Act:
    _acting(view)
    sd, sv = _step(workflow, view, step_id)
    by = _person(by)
    if sd.skip is None or sd.is_legal:
        raise StepRefused(f"{sd.id} cannot be skipped: " + ("it is a legal step" if sd.is_legal else "its definition gives no skip rule"))
    allowed = sd.skip.roles or (sd.role,)
    if not any(may(r, by, roles_of) for r in allowed):
        raise StepRefused(f"{by} may not skip {sd.id}: only {', '.join(r.value for r in allowed)}")
    if sd.skip.reason_required and not (reason or "").strip():
        raise StepRefused(f"{sd.id}: a skip needs a reason")
    state = _unit_state(view, sd, item)
    if state in (StepState.DONE, StepState.SKIPPED, StepState.SUPERSEDED):
        raise StepRefused(f"{sd.id} is already {state.value}")
    detail: dict[str, Any] = {"reason": reason.strip()}
    if item:
        detail["item"] = item
    return Act(EventKind.SKIPPED, sd.id, detail)


def reopen_act(workflow: Workflow, view: RunView, step_id: str, *, by: str, roles_of: RolesOf | None, reason: str = "",
               item: str = "") -> Act:
    """A person opens a done, skipped, or failed step again. The engine never does: a ``changed`` event does not."""
    if view.state in (RunState.CANCELLED, RunState.DRAFT):
        raise StepRefused(f"the run is {view.state.value}")
    sd, sv = _step(workflow, view, step_id)
    by = _person(by)
    if not may(sd.role, by, roles_of):
        raise StepRefused(f"{by} does not hold the {sd.role.value} role that {sd.id} needs")
    if not (reason or "").strip():
        raise StepRefused(f"{sd.id}: reopening needs a reason")
    state = _unit_state(view, sd, item)
    if state not in (StepState.DONE, StepState.SKIPPED, StepState.FAILED):
        raise StepRefused(f"{sd.id} is {state.value}; only a done, skipped, or failed step is reopened")
    detail: dict[str, Any] = {"reason": reason.strip()}
    if item:
        detail["item"] = item
    return Act(EventKind.REOPENED, sd.id, detail)


def pause_act(view: RunView, *, by: str, reason: str) -> Act:
    by = _person(by)
    if view.state not in ACTING:
        raise StepRefused(f"the run is {view.state.value}; only a running run is paused")
    if not (reason or "").strip():
        raise StepRefused("a pause needs a reason")
    return Act(EventKind.PAUSED, "", {"reason": reason.strip()})


def resume_act(view: RunView, *, by: str) -> Act:
    _person(by)
    if view.state is not RunState.PAUSED:
        raise StepRefused(f"the run is {view.state.value}, not paused")
    return Act(EventKind.RESUMED, "", {})


def activate_act(view: RunView, *, by: str) -> Act:
    """A draft becomes active: its clocks start."""
    _person(by)
    if view.state is not RunState.DRAFT:
        raise StepRefused(f"the run is {view.state.value}, not a draft")
    return Act(EventKind.RESUMED, "", {"activated": True})


def note_act(view: RunView, *, by: str, text: str, step: str = "") -> Act:
    _person(by)
    if not (text or "").strip():
        raise StepRefused("a note needs text")
    return Act(EventKind.NOTE, step, {"text": text.strip()})


def cancel_act(workflow: Workflow, view: RunView, *, by: str, roles_of: RolesOf | None, reason: str, yes: bool = False,
               roles: tuple[Role, ...] = CANCEL_ROLES) -> Act:
    """Cancel a run, with a reason. A run with a legal clock still to come is cancelled only with ``yes`` and only by
    one of ``roles``; the cancelled run stays listed for the board."""
    by = _person(by)
    if view.state in (RunState.CANCELLED, RunState.DONE):
        raise StepRefused(f"the run is already {view.state.value}")
    if not (reason or "").strip():
        raise StepRefused("a cancel needs a reason")
    legal = any(c.basis.value == "law" and c.status not in ("satisfied",) for c in view.clocks) or any(
        (workflow.step(s.id) is not None and workflow.step(s.id).is_legal and s.state not in (StepState.DONE, StepState.SKIPPED))
        for s in view.steps)
    if legal:
        if not any(may(r, by, roles_of) for r in roles):
            raise StepRefused(f"{by} may not cancel a run with a legal clock: only {', '.join(r.value for r in roles)}")
        if not yes:
            raise StepRefused("this run has a legal clock still to come: cancelling it needs yes")
    return Act(EventKind.CANCELLED, "", {"reason": reason.strip(), "legal_clock": legal})


__all__ = ["ACTING", "Act", "CANCEL_ROLES", "RolesOf", "activate_act", "arrived_act", "attest_act", "cancel_act", "may",
           "note_act", "pause_act", "reopen_act", "resume_act", "roles_held", "skip_act"]
