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
- A step may name several roles (``StepDef.roles`` beside the primary ``role``): a person holding any of them may act.
- A step that declares ``na`` is recorded as not applicable by a person holding one of its roles, with a reason and a record.
  That is not a skip: a legal step may carry it, and its clock reads "not applicable, recorded".
- A date slot that is ``late`` (or optional) is set after the start by a person, with a record; a later act corrects it, with a
  reason (append-only: the latest wins in the fold).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
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


def may_act(sd: StepDef, by: str, roles_of: RolesOf | None) -> bool:
    """Whether ``by`` may act on a step: one of its roles (the primary or any other) is held."""
    return any(may(r, by, roles_of) for r in sd.acting_roles)


def role_phrase(sd: StepDef) -> str:
    """The step's roles in words for a refusal: "the manager role" for one, "one of the roles manager or treasurer" for more."""
    roles = sd.acting_roles
    if len(roles) == 1:
        return f"the {roles[0].value} role"
    return "one of the roles " + " or ".join(r.value for r in roles)


def _no_standing(by: str, sd: StepDef, extra: str = "") -> StepRefused:
    if len(sd.acting_roles) == 1:
        return StepRefused(f"{by} does not hold the {sd.role.value} role that {sd.id} needs{extra}")
    return StepRefused(f"{by} does not hold a role that {sd.id} needs ({' or '.join(r.value for r in sd.acting_roles)}){extra}")


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
    if not may_act(sd, by, roles_of):
        extra = ""
        if sd.kind is StepKind.DECISION and by == view.owner:
            extra = f"; opening the run gives no standing to record it, the {sd.role.value} records the board's decision"
        raise _no_standing(by, sd, extra)
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
    if not may_act(sd, by, roles_of):
        raise _no_standing(by, sd)
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
    allowed = sd.skip.roles or sd.acting_roles
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


def na_act(workflow: Workflow, view: RunView, step_id: str, *, by: str, roles_of: RolesOf | None, reason: str = "",
           record: str = "", item: str = "") -> Act:
    """A person records that a step does not apply: the step is done as not applicable, which satisfies what needs it. Only a
    step whose definition declares ``na``; by a person holding one of its roles (``na.roles``, or the step's own); with the
    reason and the record the declaration asks for. A legal step may be recorded this way. It is not a skip."""
    _acting(view)
    sd, sv = _step(workflow, view, step_id)
    by = _person(by)
    if sd.na is None:
        raise StepRefused(f"{sd.id} cannot be recorded as not applicable: its definition gives no not-applicable outcome")
    allowed = sd.na.roles or sd.acting_roles
    if not any(may(r, by, roles_of) for r in allowed):
        raise StepRefused(f"{by} may not record {sd.id} as not applicable: only {', '.join(r.value for r in allowed)}")
    reason, record = (reason or "").strip(), (record or "").strip()
    if sd.na.reason_required and not reason:
        raise StepRefused(f"{sd.id}: recording a step as not applicable needs a reason")
    if sd.na.record_required and not record:
        raise StepRefused(f"{sd.id}: recording a step as not applicable needs the record that shows it")
    state = _unit_state(view, sd, item)
    if state in (StepState.DONE, StepState.SKIPPED, StepState.SUPERSEDED):
        raise StepRefused(f"{sd.id} is already {state.value}")
    detail: dict[str, Any] = {}
    if reason:
        detail["reason"] = reason
    if record:
        detail["record"] = record
    if item:
        detail["item"] = item
    return Act(EventKind.NOT_APPLICABLE, sd.id, detail)


def date_set_act(workflow: Workflow, view: RunView, *, slot: str, day: str, by: str, roles_of: RolesOf | None, record: str = "",
                 reason: str = "", today: date | None = None) -> Act:
    """A person gives a date slot a day after the start. Only a slot the definition declares and lets be set later (``late``,
    or not required), by a person holding one of the slot's roles (none named: any named person), with the record that shows the
    day. A slot that already has a day is corrected, which needs a reason; the earlier day stays in the events (append-only,
    the latest wins). The day is checked against the slot's own past or future rule and its order with the slots around it."""
    by = _person(by)
    if view.state in (RunState.DONE, RunState.CANCELLED):
        raise StepRefused(f"the run is {view.state.value}; a date is not set on it")
    slot_def = workflow.slot(slot)
    if slot_def is None:
        raise StepRefused(f"no date slot {slot} in {workflow.key}")
    if slot_def.roles and not any(may(r, by, roles_of) for r in slot_def.roles):
        raise StepRefused(f"{by} may not set date {slot}: only {', '.join(r.value for r in slot_def.roles)}")
    record, reason, day = (record or "").strip(), (reason or "").strip(), (day or "").strip()
    problems = workflow.check_date_set(slot, day, view.dates, today or date.today())
    if problems:
        raise StepRefused("; ".join(problems))
    if not record:
        raise StepRefused(f"date {slot}: setting a date needs the record that shows it")
    detail: dict[str, Any] = {"slot": slot, "day": day, "record": record}
    previous = view.dates.get(slot, "")
    if previous:
        if not reason:
            raise StepRefused(f"date {slot} is already {previous}: correcting it needs a reason")
        detail.update({"reason": reason, "was": previous})
    elif reason:
        detail["reason"] = reason
    return Act(EventKind.DATE_SET, "", detail)


def reopen_act(workflow: Workflow, view: RunView, step_id: str, *, by: str, roles_of: RolesOf | None, reason: str = "",
               item: str = "") -> Act:
    """A person opens a done, skipped, or failed step again. The engine never does: a ``changed`` event does not."""
    if view.state in (RunState.CANCELLED, RunState.DRAFT):
        raise StepRefused(f"the run is {view.state.value}")
    sd, sv = _step(workflow, view, step_id)
    by = _person(by)
    if not may_act(sd, by, roles_of):
        raise _no_standing(by, sd)
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


__all__ = ["ACTING", "Act", "CANCEL_ROLES", "RolesOf", "activate_act", "arrived_act", "attest_act", "cancel_act", "date_set_act",
           "may", "may_act", "na_act", "note_act", "pause_act", "reopen_act", "resume_act", "role_phrase", "roles_held", "skip_act"]
