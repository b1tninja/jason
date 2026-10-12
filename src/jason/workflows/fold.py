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

Round three adds, again without a new event or a changed old log: a step that ``remedy_of`` a failed check may open while the check
stays failed; a step that repeats over a named item set (``StepDef.item_set``) whose items are supplied while the run goes (a
``note`` event whose detail has ``items_supplied``), with per-item ``needs``, branch choices, and clocks and a roll-up of the
items by what is most pressing; step groups folded into one row each (``RunView.groups``); a clock counted in business days
against a calendar of holidays the caller supplies (the fold reads none); and a wait that only a person's note ends.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Any, Iterable, Mapping, Sequence

from jason.workflows.types import (
    ClockBasis, ClockDef, ClockView, DateView, Elapsed, Event, EventKind, FINAL_OUTCOMES, GroupView, Link, OnWithdrawn, Repeat,
    RunState, RunView, StepDef, StepKind, StepState, StepView, Workflow, is_system, role_words,
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


def holiday_days(values: Iterable[Any] | None) -> frozenset[date]:
    """A calendar of holidays as days: ``date`` values or ``YYYY-MM-DD`` strings; what is not a day is left out."""
    out = set()
    for v in values or ():
        d = v if isinstance(v, date) else _day(str(v))
        if d is not None:
            out.add(d)
    return frozenset(out)


def is_business_day(day: date, holidays: Iterable[date] = ()) -> bool:
    return day.weekday() < 5 and day not in holidays


def add_business_days(base: date, days: int, holidays: Iterable[date] = ()) -> date:
    """``days`` business days from ``base`` (Monday to Friday, less ``holidays``): the day ``base`` is not counted, so a result
    other than ``base`` is always a business day. ``0`` is ``base`` itself; a negative count goes back."""
    skip = holidays if isinstance(holidays, (set, frozenset)) else frozenset(holidays)
    step = 1 if days > 0 else -1
    left, day = abs(days), base
    while left:
        day += timedelta(days=step)
        if is_business_day(day, skip):
            left -= 1
    return day


def clock_due(clock: ClockDef, dates: Mapping[str, str], holidays: Iterable[date] = ()) -> date | None:
    base = _day(dates.get(clock.slot, "")) if clock.slot else None
    if not base:
        return None
    if clock.business_days:
        return add_business_days(base, clock.days, holidays)
    return base + timedelta(days=clock.days)


SEVERITY = (StepState.FAILED, StepState.NEEDS_PERSON, StepState.READY, StepState.RUNNING, StepState.WAITING, StepState.BLOCKED,
            StepState.NOT_STARTED)
"""The open states from the most pressing to the least, for a roll-up of items or of a group's steps."""


def rollup(states: Sequence[StepState]) -> StepState:
    """One state for many: done when every one is finished (skipped when none was done), else the most pressing open state."""
    if not states:
        return StepState.NOT_STARTED
    if all(s in TERMINAL for s in states):
        return StepState.DONE if any(s is StepState.DONE for s in states) else StepState.SKIPPED
    return next(s for s in SEVERITY if s in states)


def _counts(states: Iterable[StepState]) -> tuple[tuple[StepState, int], ...]:
    seen = list(states)
    return tuple((s, seen.count(s)) for s in StepState if s in seen)


def _supplies(events: Sequence[Event], slot_names: set[str]) -> tuple[dict[str, list[str]], dict[tuple[str, str], dict[str, str]]]:
    """The item sets a run's events give: the opening's ``items`` (the set named ``""``), then each ``note`` event whose detail
    carries ``items_supplied`` (``{"set": name, "items": [id | {"id", "dates"}]}``). An item is in a set once; a later supply of
    it may give or correct its dates (the latest wins). Malformed entries are left out, never an error."""
    sets: dict[str, list[str]] = {"": [str(i) for i in (events[0].detail.get("items") or ())]}
    dates: dict[tuple[str, str], dict[str, str]] = {}
    for e in events[1:]:
        raw = e.detail.get("items_supplied") if e.kind is EventKind.NOTE else None
        if not isinstance(raw, Mapping) or not isinstance(raw.get("items"), (list, tuple)):
            continue
        name = str(raw.get("set", ""))
        for entry in raw["items"]:
            item, given = (str(entry.get("id", "")), entry.get("dates")) if isinstance(entry, Mapping) else (str(entry), None)
            if not item:
                continue
            members = sets.setdefault(name, [])
            if item not in members:
                members.append(item)
            if isinstance(given, Mapping):
                dates.setdefault((name, item), {}).update(
                    {str(k): str(v) for k, v in given.items() if str(k) in slot_names and _day(str(v)) is not None})
    return sets, dates


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
          run_id: str = "", holidays: Iterable[Any] | None = None) -> RunView:
    """``holidays`` is the calendar a business-day clock counts against (days or ``YYYY-MM-DD`` strings). The fold reads no
    calendar of its own: none given means the ``holidays`` attribute of ``children`` (what ``resume.children_of`` returns, from
    the readers), and none there means weekends only."""
    events = list(events)
    if not events or events[0].kind is not EventKind.OPENED:
        raise ValueError("a run's first event is opened")
    calendar = holiday_days(holidays if holidays is not None else getattr(children, "holidays", ()))
    children = dict(children or {})
    opened = events[0]
    dates = {str(k): str(v) for k, v in (opened.detail.get("dates") or {}).items()}
    steps_by_id = {s.id: s for s in workflow.steps}
    item_lists, item_dates = _supplies(events, {d.name for d in workflow.dates})
    items = tuple(item_lists[""])

    def unit_ids(sd: StepDef) -> list[str]:
        """The items a step repeats over: its set's, when the step repeats and the set has any."""
        return list(item_lists.get(sd.item_set, ())) if sd.repeat is not Repeat.ONCE else []

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
        repeats = bool(unit_ids(sd))
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
            if not (sd.ends_by_note and is_system(e.by)):      # only a person's note ends such a wait
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
    item_skipped: dict[tuple[str, str], tuple[str, str]] = {}      # (step, item) -> (branch, choice), for a branch chosen per item

    def unchosen(sd: StepDef, choice: str) -> list[str]:
        chosen = {s for c in sd.choices if c.key == choice for s in c.steps}
        return [sid for c in sd.choices if c.key != choice for sid in c.steps if sid not in chosen]

    for sd in workflow.steps:
        if sd.kind is StepKind.BRANCH and sd.choices:
            if sd.item_aware and unit_ids(sd):
                for u in unit_ids(sd):          # one choice for each item: its own path's steps are skipped for it alone
                    choice = accs[(sd.id, u)].choice if (sd.id, u) in accs else ""
                    for sid in (unchosen(sd, choice) if choice else ()):
                        item_skipped[(sid, u)] = (sd.id, choice)
                continue
            choice = acc_for(sd.id, "").choice if (sd.id, "") in accs else ""
            if choice:
                for sid in unchosen(sd, choice):
                    branch_skipped[sid] = (sd.id, choice)

    states: dict[str, StepView] = {}
    unit_info: dict[str, dict[str, tuple[StepState, Event | None]]] = {}    # each step's item -> (state, the event that ended it)

    def due_of(sd: StepDef, item: str = "") -> date | None:
        if not sd.clock:
            return None
        on = {**dates, **item_dates.get((sd.item_set, item), {})} if (item and sd.clock.per_item) else dates
        return clock_due(sd.clock, on, calendar)

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
        due = due_of(sd, item)
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
            if due and due <= today and sd.elapsed is Elapsed.ENDS and not sd.ends_by_note:
                return StepState.DONE, f"the date {due.isoformat()} passed", a.waited
            note = f"until {due.isoformat()}" if due else "for an arrival"
            if sd.ends_by_note:
                note = f"for {role_words(sd.role)} to record a note that it arrived" + (f" (due {due.isoformat()})" if due else "")
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
        need_views = [view_of(n) for n in needs if n not in sd.item_needs]
        per_item_needs = {n: view_of(n) for n in needs if n in sd.item_needs}      # read item by item below
        visiting.discard(step_id)

        def remedied(v: StepView) -> bool:
            """The check this step remedies stays failed and does not hold this step back."""
            return bool(sd.remedy_of) and v.id == sd.remedy_of and v.kind is StepKind.CHECK and v.state is StepState.FAILED

        failed = tuple(v.id for v in need_views if v.state in (StepState.FAILED, StepState.BLOCKED) and not remedied(v))
        needs_ok = all(v.state in (StepState.DONE, StepState.SKIPPED) or remedied(v) for v in need_views)
        branch = branch_skipped.get(sd.id)
        aware = sd.item_aware
        repeats = bool(unit_ids(sd))
        units = unit_ids(sd) if repeats else [""]
        if branch:
            sv = StepView(sd.id, sd.title, sd.kind, sd.role, StepState.SKIPPED, f"not on the path {branch[1]} chosen at {branch[0]}",
                          by="jason", roles=sd.acting_roles)
            states[step_id] = sv
            return sv
        results = []
        for u in units:
            a = accs.get((sd.id, u)) or _Acc()
            taken = item_skipped.get((sd.id, u))
            if taken:                  # the branch chose another path for this item
                results.append((u, a, StepState.SKIPPED, f"not on the path {taken[1]} chosen at {taken[0]} for item {u}", None))
                continue
            ok_u, blocked_u = needs_ok, failed
            for n, nv in per_item_needs.items():      # an item waits only for its own item of these steps
                theirs = dict(nv.items).get(u) if u else None
                if theirs not in (StepState.DONE, StepState.SKIPPED):
                    ok_u = False
                    if theirs in (StepState.FAILED, StepState.BLOCKED):
                        blocked_u = (*blocked_u, n)
            results.append((u, a) + unit(sd, a, ok_u, blocked_u, u))
        unit_info[sd.id] = {u: (st_, ev_) for u, _, st_, _, ev_ in results}
        item_counts: tuple[tuple[StepState, int], ...] = ()
        item_states: tuple[tuple[str, StepState], ...] = ()
        if aware and not repeats:             # the set has no items yet: the step waits for them
            _, a, st, reason, ev = results[0]
            if st not in TERMINAL and st not in (StepState.BLOCKED, StepState.NOT_STARTED):
                st, reason = StepState.WAITING, f"no items in {'the set ' + sd.item_set if sd.item_set else 'the run'} yet"
            by_na = st is StepState.DONE and ev is not None and ev.kind is EventKind.NOT_APPLICABLE
        elif len(results) == 1 and not aware:
            _, a, st, reason, ev = results[0]
            by_na = st is StepState.DONE and ev is not None and ev.kind is EventKind.NOT_APPLICABLE
        elif aware:
            item_states = tuple((u, st) for u, _, st, _, _ in results)
            sts = [st for _, _, st, _, _ in results]
            item_counts = _counts(sts)
            st = rollup(sts)
            if st in TERMINAL:
                a, reason, ev = results[-1][1], "", results[-1][4]
                done_evs = [e_ for _, _, s_, _, e_ in results if s_ is StepState.DONE]
                by_na = st is StepState.DONE and all(e_ is not None and e_.kind is EventKind.NOT_APPLICABLE for e_ in done_evs)
            else:                              # the most pressing item speaks for the step
                _, a, st, reason, ev = next(r for r in results if r[2] is st)
                done_n = sum(1 for s in sts if s in TERMINAL)
                reason = f"{done_n} of {len(sts)} items done" + (f"; {reason}" if reason else "")
                by_na = False
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
            item_counts=item_counts,
        )
        states[step_id] = sv
        return sv

    step_views = tuple(view_of(s.id) for s in workflow.steps)

    # a failed check whose remedy step is open: the check stays failed on record, and the run goes on through the remedy
    held: set[str] = set()
    if any(sd.remedy_of for sd in workflow.steps):
        views = {v.id: v for v in step_views}
        patched = []
        for v in step_views:
            fix = next((sd.id for sd in workflow.steps if sd.remedy_of == v.id and views[sd.id].state not in TERMINAL), "")
            if v.state is StepState.FAILED and fix:
                if views[fix].state in (StepState.READY, StepState.RUNNING, StepState.WAITING, StepState.NEEDS_PERSON):
                    held.add(v.id)
                v = replace(v, remedy=fix)
            patched.append(v)
        step_views = tuple(patched)

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
    elif any(v.state is StepState.FAILED and v.id not in held for v in step_views):
        run_state = RunState.FAILED
    elif open_views and all(v.state is StepState.WAITING for v in open_views):
        run_state = RunState.WAITING
    else:
        run_state = RunState.ACTIVE

    current = ""
    for v in step_views:
        if v.state in _CURRENT and v.id not in held:      # a failed check with its remedy open is not the one to look at
            current = v.id
            break

    # --- clocks
    clocks: list[ClockView] = []
    running = run_state not in (RunState.DRAFT,)

    def clock_view(key: str, clock: ClockDef, satisfied: bool, step: str, title: str = "", na: bool = False,
                   on: Mapping[str, str] | None = None, item: str = "") -> ClockView:
        due = clock_due(clock, dates if on is None else on, calendar)
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
                         cite=clock.cite, status=status, days=days, step=step, item=item)

    for i, c in enumerate(workflow.clocks):
        clocks.append(clock_view(f"run.{i}", c, run_state is RunState.DONE, ""))
    for sd, sv in zip(workflow.steps, step_views):
        if sd.clock and sd.clock.per_item and sv.items:
            for item, _ in sv.items:          # one clock for each item, read from the item's own dates before the run's
                st_, ev_ = unit_info[sd.id][item]
                gone = st_ is StepState.DONE and ev_ is not None and ev_.kind is EventKind.NOT_APPLICABLE
                clocks.append(clock_view(f"{sd.id}[{item}]", sd.clock, st_ in TERMINAL, sd.id, sd.title, na=gone,
                                         on={**dates, **item_dates.get((sd.item_set, item), {})}, item=item))
        elif sd.clock:
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

    # --- step groups: one row each, expanded while it holds the current step (or a failed one), collapsed when done or not reached
    titles = {g.key: g.title for g in workflow.groups}
    group_views = []
    for key in dict.fromkeys(sd.group for sd in workflow.steps if sd.group):
        members = [v for sd, v in zip(workflow.steps, step_views) if sd.group == key]
        ids = tuple(v.id for v in members)
        live = run_state not in (RunState.DONE, RunState.CANCELLED)
        group_views.append(GroupView(
            key=key, title=titles.get(key) or key, steps=ids, state=rollup([v.state for v in members]),
            done=sum(1 for v in members if v.state in TERMINAL), total=len(members),
            expanded=live and (current in ids or any(v.state is StepState.FAILED for v in members)),
            current=current if current in ids else ""))

    return RunView(
        id=run_id, definition=workflow.key, subject=str(opened.detail.get("subject", "")),
        label=str(opened.detail.get("label", "")), owner=opened.by, opened_at=opened.at, state=run_state, steps=step_views,
        current=current, clocks=tuple(clocks), links=tuple(links.values()), dates=dates, n=events[-1].n, updated=events[-1].at,
        parent=str(opened.detail.get("parent", "")), paused_reason=paused if is_paused else "",
        cancelled_reason=cancelled, orphans=tuple(orphans), children=tuple(spawned), past_law=past_law, items=items,
        date_slots=tuple(slot_views), groups=tuple(group_views), item_sets={k: tuple(v) for k, v in item_lists.items()},
    )


__all__ = ["OPEN", "SEVERITY", "TERMINAL", "add_business_days", "clock_due", "evidence_entries", "holiday_days", "is_business_day",
           "parse_evidence", "rollup", "state"]
