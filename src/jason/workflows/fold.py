"""The fold: events to a run's state. Pure.

``state(events, workflow, today, children=None, run_id="") -> RunView``. No clock is read here: ``today`` is an argument, so the same
events and the same day give the same view, and replaying a prefix of the events gives the earlier view. ``children``
maps a child run's id to its state word (``"done"``, ``"cancelled"``, ...) for the steps that spawned one; a missing child
is simply not finished.

The step states follow docs/workflows-engine.md, section 4: a step is ``ready`` when every ``needs`` is done or skipped and
it is not superseded; ``waiting`` when a ``wait`` (or a child run) holds it; ``needs a person`` when it is ready and its kind
is ``person`` or ``decision``; ``blocked`` when a ``needs`` has failed; a run is ``waiting`` when every open step is
waiting. A ``changed`` event never un-does a step: only a ``reopened`` event does.

Three later events fold in without touching an older log. ``not-applicable`` makes a step done (``StepView.na``; it satisfies
a ``needs``, and a clock on it reads "not applicable, recorded", neither satisfied nor dropped). ``date-set`` gives a date slot
a value after the start (the latest wins, and every clock is read from the dates as they stand). A step with
``waits_on_child`` is done only when its own act is on record and every child run spawned from it is done or cancelled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable, Mapping, Sequence

from jason.workflows.types import (
    ClockBasis, ClockDef, ClockView, DateView, Elapsed, Event, EventKind, FINAL_OUTCOMES, Link, OnWithdrawn, Repeat,
    RunState, RunView, StepDef, StepKind, StepState, StepView, Workflow,
)

NA_STATUS = "not applicable, recorded"
"""What a clock on a step recorded as not applicable reads: neither satisfied nor dropped."""
TERMINAL = frozenset({StepState.DONE, StepState.SKIPPED, StepState.SUPERSEDED})
OPEN = frozenset({StepState.READY, StepState.RUNNING, StepState.WAITING, StepState.NEEDS_PERSON, StepState.FAILED})
_CURRENT = (StepState.FAILED, StepState.NEEDS_PERSON, StepState.READY, StepState.RUNNING, StepState.WAITING)


def parse_evidence(entries: Iterable[Any]) -> dict[str, str]:
    """``["address@hash", ...]`` as {address: hash}; an entry with no ``@`` has an empty hash."""
    out: dict[str, str] = {}
    for entry in entries or ():
        text = str(entry)
        address, _, digest = text.rpartition("@")
        if not address:
            address, digest = text, ""
        out[address] = digest
    return out


def evidence_entries(hashes: Mapping[str, str]) -> list[str]:
    return [f"{a}@{h}" for a, h in hashes.items()]


@dataclass
class _Acc:
    """What the events say about one step (or one item of a step)."""

    attested: Event | None = None
    decided: Event | None = None           # a decision with a final outcome
    decided_any: Event | None = None
    check: Event | None = None
    job_queued: Event | None = None
    job_done: Event | None = None
    plan: Event | None = None
    plan_status: str = ""
    plan_reason: str = ""
    applied: Event | None = None
    waited: Event | None = None
    arrived: Event | None = None
    skipped: Event | None = None
    spawned: Event | None = None
    na: Event | None = None
    children: list[str] = field(default_factory=list)      # every child run spawned from this step, in order
    superseded: bool = False
    choice: str = ""
    evidence: dict[str, str] = field(default_factory=dict)
    changed: list[dict[str, str]] = field(default_factory=list)
    reopened: int = 0


def _day(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def clock_due(clock: ClockDef, dates: Mapping[str, str]) -> date | None:
    base = _day(dates.get(clock.slot, "")) if clock.slot else None
    return base + timedelta(days=clock.days) if base else None


def _item(event: Event, repeats: bool) -> str:
    return str(event.detail.get("item", "")) if repeats else ""


def _links(event: Event) -> list[Link]:
    out: list[Link] = []
    for raw in event.detail.get("links", ()) or ():
        if isinstance(raw, Mapping) and raw.get("address"):
            out.append(Link(str(raw.get("kind", "")), str(raw["address"]), event.step, str(raw.get("label", ""))))
    for key, kind in (("job", "job"), ("approval", "approval"), ("child", "run")):
        if event.detail.get(key):
            out.append(Link(kind, str(event.detail[key]), event.step))
    return out


def state(events: Sequence[Event], workflow: Workflow, today: date, children: Mapping[str, str] | None = None, *,
          run_id: str = "") -> RunView:
    events = list(events)
    if not events or events[0].kind is not EventKind.OPENED:
        raise ValueError("a run's first event is opened")
    children = dict(children or {})
    opened = events[0]
    dates = {str(k): str(v) for k, v in (opened.detail.get("dates") or {}).items()}
    items = tuple(str(i) for i in (opened.detail.get("items") or ()))
    steps_by_id = {s.id: s for s in workflow.steps}

    accs: dict[tuple[str, str], _Acc] = {}
    links: dict[tuple[str, str], Link] = {}
    orphans: list[str] = []
    spawned: list[str] = []
    date_sets: dict[str, list[Event]] = {}
    slot_names = {d.name for d in workflow.dates}
    paused = ""
    is_paused = False
    activated = False
    cancelled = ""
    is_cancelled = False

    def acc_for(step_id: str, item: str) -> _Acc:
        return accs.setdefault((step_id, item), _Acc())

    for e in events:
        for link in _links(e):
            links.setdefault((link.kind, link.address), link)
        if e.detail.get("supersedes"):
            target = str(e.detail["supersedes"])
            for (sid, _), a in list(accs.items()):
                if sid == target:
                    a.superseded = True
            if target in steps_by_id:
                acc_for(target, "").superseded = True
        k = e.kind
        if k is EventKind.OPENED:
            continue
        if k is EventKind.PAUSED:
            is_paused, paused = True, str(e.detail.get("reason", ""))
            continue
        if k is EventKind.RESUMED:
            if not activated and opened.detail.get("draft"):
                activated = True
            else:
                is_paused, paused = False, ""
            continue
        if k is EventKind.CANCELLED:
            is_cancelled, cancelled = True, str(e.detail.get("reason", ""))
            continue
        if k is EventKind.DATE_SET:
            slot, day = str(e.detail.get("slot", "")), str(e.detail.get("day", ""))
            if slot in slot_names and _day(day) is not None:      # the latest wins; a slot the definition lacks is ignored
                dates[slot] = day
                date_sets.setdefault(slot, []).append(e)
            continue
        if k is EventKind.NOTE and not e.step:
            continue
        if not e.step:
            continue
        sd = steps_by_id.get(e.step)
        if sd is None:
            if e.step not in orphans:
                orphans.append(e.step)
            continue
        repeats = sd.repeat is not Repeat.ONCE and bool(items)
        item = _item(e, repeats)
        if k is EventKind.REOPENED:
            targets = [key for key in accs if key[0] == sd.id and (not repeats or not e.detail.get("item") or key[1] == item)]
            for key in targets:
                accs[key] = _Acc(reopened=accs[key].reopened + 1, children=accs[key].children)
            if not targets:
                acc_for(sd.id, item).reopened += 1
            continue
        a = acc_for(sd.id, item)
        if k is EventKind.CHECK_RAN:
            a.check = e
            if e.detail.get("ok"):
                a.evidence = parse_evidence(e.detail.get("evidence"))
                if e.detail.get("choice"):
                    a.choice = str(e.detail["choice"])
        elif k is EventKind.JOB_QUEUED:
            a.job_queued = e
        elif k is EventKind.JOB_FINISHED:
            a.job_done = e
            if e.detail.get("ok"):
                a.evidence = parse_evidence(e.detail.get("evidence"))
        elif k is EventKind.PLAN_MADE:
            a.plan, a.plan_status, a.plan_reason = e, "planned", ""
        elif k is EventKind.APPROVAL_DECIDED:
            a.plan_status, a.plan_reason = str(e.detail.get("status", "")), str(e.detail.get("reason", ""))
        elif k is EventKind.APPLIED:
            a.applied, a.plan_status = e, "applied"
            a.evidence = parse_evidence(e.detail.get("evidence")) or a.evidence
        elif k is EventKind.ATTESTED:
            a.attested = e
            if e.detail.get("choice"):
                a.choice = str(e.detail["choice"])
            a.evidence = parse_evidence(e.detail.get("evidence")) or a.evidence
        elif k is EventKind.DECIDED:
            a.decided_any = e
            if str(e.detail.get("outcome", "")).lower() in FINAL_OUTCOMES:
                a.decided = e
                a.evidence = parse_evidence(e.detail.get("evidence")) or a.evidence
        elif k is EventKind.WAITED:
            a.waited = e
        elif k is EventKind.ARRIVED:
            a.arrived = e
        elif k is EventKind.SKIPPED:
            a.skipped = e
        elif k is EventKind.NOT_APPLICABLE:
            a.na = e
        elif k is EventKind.SPAWNED:
            a.spawned = e
            if e.detail.get("child"):
                if str(e.detail["child"]) not in spawned:
                    spawned.append(str(e.detail["child"]))
                if str(e.detail["child"]) not in a.children:
                    a.children.append(str(e.detail["child"]))
        elif k is EventKind.CHANGED:
            a.changed = [dict(d) for d in (e.detail.get("differences") or ()) if isinstance(d, Mapping)]
            if e.detail.get("evidence") is not None:
                a.evidence = parse_evidence(e.detail.get("evidence"))

    # a branch's chosen path: the steps on the other paths are skipped by jason, derived, not recorded
    branch_skipped: dict[str, tuple[str, str]] = {}
    for sd in workflow.steps:
        if sd.kind is StepKind.BRANCH and sd.choices:
            choice = acc_for(sd.id, "").choice if (sd.id, "") in accs else ""
            if choice:
                chosen = {s for c in sd.choices if c.key == choice for s in c.steps}
                for c in sd.choices:
                    for sid in c.steps:
                        if c.key != choice and sid not in chosen:
                            branch_skipped[sid] = (sd.id, choice)

    states: dict[str, StepView] = {}

    def due_of(sd: StepDef) -> date | None:
        return clock_due(sd.clock, dates) if sd.clock else None

    def unit(sd: StepDef, a: _Acc, needs_ok: bool, blocked: tuple[str, ...], item: str) -> tuple[StepState, str, Event | None]:
        """One step's (or one item's) state, from what the events say, then from whether its needs hold."""
        if a.skipped:
            return StepState.SKIPPED, str(a.skipped.detail.get("reason", "")), a.skipped
        if a.superseded:
            return StepState.SUPERSEDED, "replaced by a re-plan", None
        if a.na:
            why = str(a.na.detail.get("reason", ""))
            return StepState.DONE, f"recorded as not applicable by {a.na.by or '?'}" + (f": {why}" if why else ""), a.na
        done: Event | None = None
        if sd.kind is StepKind.CHECK and a.check and a.check.detail.get("ok"):
            done = a.check
        elif sd.kind is StepKind.JOB and a.job_done and a.job_done.detail.get("ok"):
            done = a.job_done
        elif sd.kind is StepKind.PLAN and a.applied:
            done = a.applied
        elif sd.kind is StepKind.PERSON and a.attested:
            done = a.attested
        elif sd.kind is StepKind.DECISION and a.decided:
            done = a.decided
        elif sd.kind is StepKind.WAIT and a.arrived:
            done = a.arrived
        elif sd.kind is StepKind.BRANCH and a.choice:
            done = a.check if a.check and a.check.detail.get("ok") else a.attested
        if sd.spawns and sd.waits_on_child:
            # the step's own act and every child spawned from it: not done until each child is done or cancelled
            unfinished = [c for c in a.children if children.get(c) not in ("done", "cancelled")]
            if unfinished:
                total = len(a.children)
                if total == 1:
                    return StepState.WAITING, f"child run {unfinished[0]} is {children.get(unfinished[0]) or 'not finished'}", None
                return StepState.WAITING, (f"{total - len(unfinished)} of {total} child runs finished; waiting on "
                                           + ", ".join(unfinished)), None
            if done is not None and a.children:
                return StepState.DONE, (f"child run {a.children[0]} is {children[a.children[0]]}" if len(a.children) == 1
                                        else f"all {len(a.children)} child runs finished"), done
        elif sd.spawns and a.spawned:
            child = str(a.spawned.detail.get("child", ""))
            if children.get(child) in ("done", "cancelled"):
                return StepState.DONE, f"child run {child} is {children[child]}", a.spawned
            if not done:
                return StepState.WAITING, f"child run {child} is {children.get(child) or 'not finished'}", None
        if done is not None:
            return StepState.DONE, "", done
        if sd.kind is StepKind.PLAN and a.plan_status == "withdrawn" and sd.on_withdrawn is OnWithdrawn.SKIP:
            return StepState.SKIPPED, "approval withdrawn" + (f": {a.plan_reason}" if a.plan_reason else ""), None
        if not needs_ok:
            if blocked:
                return StepState.BLOCKED, "blocked by " + ", ".join(blocked), None
            return StepState.NOT_STARTED, "", None
        due = due_of(sd)
        if sd.kind is StepKind.CHECK:
            if a.check:
                return StepState.FAILED, str(a.check.detail.get("message", "")) or "the check did not pass", None
            return StepState.READY, "", None
        if sd.kind is StepKind.JOB:
            if a.job_done:
                return StepState.FAILED, str(a.job_done.detail.get("message", "")) or "the job failed", None
            if a.job_queued:
                return StepState.RUNNING, "queued", None
            return StepState.READY, "", None
        if sd.kind is StepKind.PLAN:
            if a.plan_status == "failed":
                return StepState.FAILED, "the approval failed" + (f": {a.plan_reason}" if a.plan_reason else ""), None
            if a.plan_status == "withdrawn":
                return StepState.FAILED, "approval withdrawn" + (f": {a.plan_reason}" if a.plan_reason else ""), None
            if a.plan:
                return StepState.WAITING, f"approval {a.plan_status or 'planned'}", None
            return StepState.READY, "", None
        if sd.kind is StepKind.DECISION:
            return StepState.NEEDS_PERSON, (f"recorded as {a.decided_any.detail.get('outcome', '?')}, not final" if a.decided_any else ""), None
        if sd.kind is StepKind.WAIT:
            if due and due <= today and sd.elapsed is Elapsed.ENDS:
                return StepState.DONE, f"the date {due.isoformat()} passed", a.waited
            note = f"until {due.isoformat()}" if due else "for an arrival"
            if due and due < today:
                note += f" (past {due.isoformat()})"
            return StepState.WAITING, note, None
        if sd.kind is StepKind.BRANCH:
            if a.check and not a.check.detail.get("ok"):
                return StepState.FAILED, str(a.check.detail.get("message", "")) or "the fact could not be read", None
            return (StepState.READY if sd.check else StepState.NEEDS_PERSON), "", None
        return StepState.NEEDS_PERSON, "", None   # person

    visiting: set[str] = set()

    def view_of(step_id: str) -> StepView:
        if step_id in states:
            return states[step_id]
        sd = steps_by_id[step_id]
        if step_id in visiting:       # a cycle (validate refuses one); treat it as not started
            return StepView(sd.id, sd.title, sd.kind, sd.role, StepState.NOT_STARTED, roles=sd.acting_roles)
        visiting.add(step_id)
        needs = [n for n in sd.needs if n in steps_by_id]
        need_views = [view_of(n) for n in needs]
        visiting.discard(step_id)
        failed = tuple(v.id for v in need_views if v.state in (StepState.FAILED, StepState.BLOCKED))
        needs_ok = all(v.state in (StepState.DONE, StepState.SKIPPED) for v in need_views)
        branch = branch_skipped.get(sd.id)
        repeats = sd.repeat is not Repeat.ONCE and bool(items)
        units = list(items) if repeats else [""]
        if branch:
            sv = StepView(sd.id, sd.title, sd.kind, sd.role, StepState.SKIPPED, f"not on the path {branch[1]} chosen at {branch[0]}",
                          by="jason", roles=sd.acting_roles)
            states[step_id] = sv
            return sv
        results = []
        for u in units:
            a = accs.get((sd.id, u)) or _Acc()
            results.append((u, a) + unit(sd, a, needs_ok, failed, u))
        if len(results) == 1:
            _, a, st, reason, ev = results[0]
            item_states: tuple[tuple[str, StepState], ...] = ()
            by_na = st is StepState.DONE and ev is not None and ev.kind is EventKind.NOT_APPLICABLE
        else:
            item_states = tuple((u, st) for u, _, st, _, _ in results)
            sts = [st for _, _, st, _, _ in results]
            if all(s is StepState.DONE or s is StepState.SKIPPED for s in sts):
                st = StepState.DONE if any(s is StepState.DONE for s in sts) else StepState.SKIPPED
                a, reason, ev = results[-1][1], "", results[-1][4]
                done_evs = [e_ for _, _, s_, _, e_ in results if s_ is StepState.DONE]
                by_na = st is StepState.DONE and all(e_ is not None and e_.kind is EventKind.NOT_APPLICABLE for e_ in done_evs)
            else:
                pick = next(((u, a_, s_, r_, e_) for u, a_, s_, r_, e_ in results if s_ not in TERMINAL), results[0])
                _, a, st, reason, ev = pick
                done_n = sum(1 for s in sts if s in TERMINAL)
                reason = (f"{done_n} of {len(sts)} items done" + (f"; {reason}" if reason else ""))
                by_na = False
        chosen = a.choice if a else ""
        sv = StepView(
            id=sd.id, title=sd.title, kind=sd.kind, role=sd.role, state=st, reason=reason,
            by=(ev.by if ev else ""), at=(ev.at if ev else ""),
            record=str(ev.detail.get("record", "")) if ev else "",
            blocked_by=failed if st is StepState.BLOCKED else (),
            changed=tuple(a.changed) if a else (), items=item_states,
            detail=dict(ev.detail) if ev else {}, evidence=tuple(evidence_entries(a.evidence)) if a else (),
            choice=chosen, roles=sd.acting_roles, na=by_na, children=tuple(a.children) if a else (),
        )
        states[step_id] = sv
        return sv

    step_views = tuple(view_of(s.id) for s in workflow.steps)

    # --- run state
    all_terminal = all(v.state in TERMINAL for v in step_views)
    open_views = [v for v in step_views if v.state in OPEN or v.state is StepState.BLOCKED]
    if is_cancelled:
        run_state = RunState.CANCELLED
    elif opened.detail.get("draft") and not activated:
        run_state = RunState.DRAFT
    elif all_terminal:
        run_state = RunState.DONE
    elif is_paused:
        run_state = RunState.PAUSED
    elif any(v.state is StepState.FAILED for v in step_views):
        run_state = RunState.FAILED
    elif open_views and all(v.state is StepState.WAITING for v in open_views):
        run_state = RunState.WAITING
    else:
        run_state = RunState.ACTIVE

    current = ""
    for v in step_views:
        if v.state in _CURRENT:
            current = v.id
            break

    # --- clocks
    clocks: list[ClockView] = []
    running = run_state not in (RunState.DRAFT,)

    def clock_view(key: str, clock: ClockDef, satisfied: bool, step: str, title: str = "", na: bool = False) -> ClockView:
        due = clock_due(clock, dates)
        if due is None:
            status, days = "undated", None
        elif na:                      # recorded as not applicable: the clock is kept and says so, never dropped as a skip
            status, days = NA_STATUS, (due - today).days
        elif satisfied:
            status, days = "satisfied", (due - today).days
        elif not running:
            status, days = "not running", (due - today).days
        else:
            days = (due - today).days
            status = "overdue" if days < 0 else ("due" if days == 0 else "upcoming")
        return ClockView(key=key, basis=clock.basis, due=due.isoformat() if due else "", label=clock.label or title,
                         cite=clock.cite, status=status, days=days, step=step)

    for i, c in enumerate(workflow.clocks):
        clocks.append(clock_view(f"run.{i}", c, run_state is RunState.DONE, ""))
    for sd, sv in zip(workflow.steps, step_views):
        if sd.clock:
            clocks.append(clock_view(sd.id, sd.clock, sv.state in TERMINAL, sd.id, sd.title, na=sv.na))
    past_law = tuple(c.key for c in clocks if c.basis is ClockBasis.LAW and c.status == "overdue")

    slot_views = []
    for slot in workflow.dates:
        sets = date_sets.get(slot.name, [])
        last = sets[-1] if sets else None
        value = dates.get(slot.name, "")
        slot_views.append(DateView(
            name=slot.name, label=slot.label, value=value, required=slot.required, late=slot.late,
            settable=slot.settable and run_state not in (RunState.DONE, RunState.CANCELLED), correction=bool(value),
            timing=slot.timing.value, set_by=last.by if last else "", set_at=last.at if last else "",
            record=str(last.detail.get("record", "")) if last else "", sets=len(sets)))

    return RunView(
        id=run_id, definition=workflow.key, subject=str(opened.detail.get("subject", "")),
        label=str(opened.detail.get("label", "")), owner=opened.by, opened_at=opened.at, state=run_state, steps=step_views,
        current=current, clocks=tuple(clocks), links=tuple(links.values()), dates=dates, n=events[-1].n, updated=events[-1].at,
        parent=str(opened.detail.get("parent", "")), paused_reason=paused if is_paused else "",
        cancelled_reason=cancelled, orphans=tuple(orphans), children=tuple(spawned), past_law=past_law, items=items,
        date_slots=tuple(slot_views),
    )


__all__ = ["OPEN", "TERMINAL", "clock_due", "evidence_entries", "parse_evidence", "state"]
