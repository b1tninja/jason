"""What the terminal command, the web loaders, and the MCP tools call: plain dicts in, plain dicts out.

Every function takes ``data_dir`` first and ``by`` (a signed-in name, or ``jason``/``scheduler``) for a write, and none
opens a browser or prints. A write reads the run under its lock, applies the step-kind contract (``jason.workflows.steps``),
and appends one event; ``expect`` is the ``n`` the caller last saw, and a run that has moved on is refused with
``RunChanged`` naming the changed ``n`` (two persons at once). ``roles_of(by)`` says which roles a name holds; the caller
(the web layer from the sign-in, a test from a table) supplies it, and none supplied means no roles, so every act that
needs one is refused. ``readers`` is the injectable world a resume and a ``show`` read (see ``jason.workflows.resume``).

``gates`` is the one place a caller adds a requirement to a person's attestation, skip, or not-applicable record (an adopted control, say):
``gates(StepAsk) -> GateVerdict``. None means the default, which is looked up when an act is made and not before
(``_default_gates``), so importing the engine loads no control and no profile; a gate that adds nothing leaves the act as
it was. A gate may refuse (the act is refused with its sentence and nothing is written) or ask for a second, different
person: the first person's act is then recorded as a note (``first_of_two``), the step stays open, and the act of a
different person completes it with ``confirms`` naming the first.

Nothing here sends, files, or writes outside ``data_dir``.
"""

from __future__ import annotations

import secrets
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from jason.workflows import definitions, fold, resume as resume_mod, steps, store
from jason.workflows.resume import Readers
from jason.workflows.types import (
    ClockView, DateView, EventKind, Gates, GateVerdict, GroupView, Link, RunChanged, RunState, RunView, StepAsk, StepRefused,
    StepView, Workflow, WorkflowError,
)

OPEN_STATES = frozenset({"draft", "active", "paused", "waiting", "failed"})


def _today(today: date | None) -> date:
    return today or date.today()


def _workflow(definition: str) -> Workflow:
    try:
        return definitions.get(definition)
    except KeyError as exc:
        raise StepRefused(str(exc.args[0])) from None


def _view(run: store.Run, wf: Workflow, today: date, readers: Readers | None) -> RunView:
    events = list(run.events)
    return fold.state(events, wf, today, resume_mod.children_of(events, readers or Readers()), run_id=run.id)


# --- dicts ----------------------------------------------------------------------------------------------------------

def _clock(c: ClockView) -> dict[str, Any]:
    out = {"key": c.key, "basis": c.basis.value, "due": c.due, "label": c.label, "cite": c.cite, "status": c.status,
           "days": c.days, "step": c.step}
    if c.item:
        out["item"] = c.item
    return out


def _step(s: StepView) -> dict[str, Any]:
    return {"id": s.id, "title": s.title, "kind": s.kind.value, "role": s.role.value, "state": s.state.value,
            "reason": s.reason, "by": s.by, "at": s.at, "record": s.record, "blockedBy": list(s.blocked_by),
            "changed": [dict(c) for c in s.changed], "items": [{"item": i, "state": st.value} for i, st in s.items],
            "choice": s.choice, "roles": [r.value for r in s.roles] or [s.role.value], "na": s.na,
            "children": list(s.children), **_extra_step(s)}


def _extra_step(s: StepView) -> dict[str, Any]:
    """What round three adds to a step row, only when there is something to add: the step that remedies a failed check, and how
    many items are in each state."""
    out: dict[str, Any] = {}
    if s.remedy:
        out["remedy"] = s.remedy
    if s.item_counts:
        out["itemCounts"] = {st.value: n for st, n in s.item_counts}
    return out


def _group(g: GroupView) -> dict[str, Any]:
    return {"key": g.key, "title": g.title, "steps": list(g.steps), "state": g.state.value, "done": g.done, "total": g.total,
            "expanded": g.expanded, "current": g.current}


def _slot(d: DateView) -> dict[str, Any]:
    return {"name": d.name, "label": d.label, "value": d.value, "required": d.required, "late": d.late,
            "settable": d.settable, "correction": d.correction, "timing": d.timing, "setBy": d.set_by, "setAt": d.set_at,
            "record": d.record, "sets": d.sets}


def _link(link: Link) -> dict[str, str]:
    return {"kind": link.kind, "address": link.address, "step": link.step, "label": link.label}


def view_dict(view: RunView, run: store.Run | None = None) -> dict[str, Any]:
    out = {"id": view.id, "definition": view.definition, "subject": view.subject, "label": view.label, "owner": view.owner,
           "opened": view.opened_at, "state": view.state.value, "current": view.current, "n": view.n,
           "updated": view.updated, "dates": dict(view.dates), "items": list(view.items), "parent": view.parent,
           "pausedReason": view.paused_reason, "cancelledReason": view.cancelled_reason,
           "steps": [_step(s) for s in view.steps], "clocks": [_clock(c) for c in view.clocks],
           "links": [_link(l) for l in view.links], "orphans": list(view.orphans), "children": list(view.children),
           "pastLaw": list(view.past_law), "dateSlots": [_slot(d) for d in view.date_slots],
           "openSlots": [d.name for d in view.date_slots if d.settable]}
    if view.groups:
        out["groups"] = [_group(g) for g in view.groups]
    named = {k: list(v) for k, v in view.item_sets.items() if k}
    if named:
        out["itemSets"] = named
    if run is not None:
        out["torn"] = run.torn
        out["corrupt"] = run.corrupt
    return out


def _summary(run: store.Run, wf: Workflow | None, today: date, readers: Readers | None = None) -> dict[str, Any]:
    first = run.events[0] if run.events else None
    row = {"id": run.id, "definition": run.definition, "label": str(first.detail.get("label", "")) if first else "",
           "subject": str(first.detail.get("subject", "")) if first else "", "state": "unknown definition", "current": "",
           "due": "", "owner": first.by if first else "", "updated": run.events[-1].at if run.events else "", "n": run.n,
           "tip": run.tip}
    if wf is None or first is None:
        return row
    view = _view(run, wf, today, readers)
    dues = sorted(c.due for c in view.clocks if c.due and c.status in ("upcoming", "due", "overdue"))
    row.update(state=view.state.value, current=view.current, due=dues[0] if dues else "")
    return row


def _index(data_dir: Path | str, run: store.Run, today: date, readers: Readers | None = None) -> None:
    try:
        wf = definitions.find(run.definition)
        store.index_put(data_dir, _summary(run, wf, today, readers))
    except Exception:  # noqa: BLE001 - the index is a cache; a write has already succeeded
        pass


def _person(by: str) -> str:
    return steps._person(by)


# --- a write --------------------------------------------------------------------------------------------------------

def _do(data_dir: Path | str, run_id: str, by: str, make: Callable[..., steps.Act], *, expect: int | None,
        today: date | None, at: str | None, readers: Readers | None = None, extra: Mapping[str, Any] | None = None,
        needs_run: bool = False) -> dict[str, Any]:
    day = _today(today)
    definition = store.locate(data_dir, run_id)
    wf = _workflow(definition)
    with store._lock(run_id, "workflow write"):
        run = store.read(data_dir, definition, run_id)
        if expect is not None and expect != run.n:
            last = run.events[-1]
            raise RunChanged(f"run {run_id} changed: you saw n={expect}, it is now n={run.n} "
                             f"({last.kind.value} by {last.by or '?'} at {last.at}); read it again", expected=expect, actual=run.n)
        view = _view(run, wf, day, readers)
        act = make(wf, view, run) if needs_run else make(wf, view)
        detail = dict(act.detail)
        detail.update(extra or {})
        event = store.append(data_dir, definition, run_id, act.kind, by=by, step=act.step, detail=detail, at=at or "", n=run.n + 1)
        run = store.read(data_dir, definition, run_id)
    _index(data_dir, run, day, readers)
    return {"ok": True, "event": event.to_dict(), "run": view_dict(_view(run, wf, day, readers), run)}


def _evidence_for(wf: Workflow, readers: Readers | None, step_id: str) -> list[str]:
    sd = wf.step(step_id)
    if sd is None or readers is None:
        return []
    out = []
    for address in sd.evidence:
        digest = readers.evidence(address)
        if digest:
            out.append(f"{address}@{digest}")
    return out


# --- gates ----------------------------------------------------------------------------------------------------------

def _default_gates() -> Gates | None:
    """The gate the controls module gives, found when an act is made. It is looked up by name, not imported at the top, so the
    engine's import loads no control and no profile (tests/test_workflows_boundaries.py); a build without it has none."""
    import importlib

    try:
        return importlib.import_module("jason.controls.effective").workflow_gate
    except ImportError:
        return None


def pending_first(events: Iterable[Any], step_id: str, act: str, item: str = "") -> str:
    """Who made the first of two on this step for this act and item, "" when no first is waiting: the latest ``first_of_two``
    note of the same act, not followed by an event that finished, skipped, or reopened the step."""
    for e in reversed(list(events)):
        if e.step != step_id or (item and str(e.detail.get("item", "")) != item):
            continue
        if e.kind in (EventKind.ATTESTED, EventKind.DECIDED, EventKind.SKIPPED, EventKind.NOT_APPLICABLE, EventKind.REOPENED):
            return ""
        if e.kind is EventKind.NOTE and e.detail.get("first_of_two"):
            return e.by if e.detail["first_of_two"] == act else ""
    return ""


def _gated(act: steps.Act, wf: Workflow, view: RunView, run: store.Run, step_id: str, name: str, by: str, *,
           roles_of: Callable[[str], Iterable[Any]] | None, gates: Gates | None, data_dir: Path | str, run_id: str,
           day: date, item: str, words: Iterable[str]) -> steps.Act:
    """The act the step contract accepted, after the gates: refused with their sentences, the first of two (a note), the
    confirming act (naming the first), or the act unchanged."""
    gate = gates if gates is not None else _default_gates()
    if gate is None:
        return act
    sd = wf.step(step_id)
    first = pending_first(run.events, step_id, name, item)
    texts = tuple(t for t in (*words, view.subject, view.label, *(s.record for s in view.steps)) if t)
    ask = StepAsk(data_dir, run_id, wf.key, wf.family, step_id, sd.role.value if sd else "", name, by,
                  tuple(sorted(r.value for r in steps.roles_held(by, roles_of))), first, texts, day,
                  tuple(r.value for r in sd.acting_roles) if sd else ())
    try:
        verdict = gate(ask)
    except WorkflowError:
        raise
    except Exception as exc:  # noqa: BLE001 - a gate that cannot be read refuses; it never lets the act through
        raise StepRefused(f"the controls could not be read, so nothing was recorded: {type(exc).__name__}: {exc}") from exc
    if not isinstance(verdict, GateVerdict):
        return act
    if verdict.refusals:
        raise StepRefused("; ".join(dict.fromkeys(verdict.refusals)))
    if not verdict.second:
        return act
    if first:
        return steps.Act(act.kind, act.step, {**act.detail, "confirms": first})
    kept = {k: v for k, v in act.detail.items() if k in ("item", "record", "reason")}
    did = {"attest": "attested", "skip": "skipped", "na": "recorded as not applicable"}.get(name, name)
    return steps.Act(EventKind.NOTE, act.step, {
        **kept, "first_of_two": name, "text": f"{did} as the first of two; a second, different person confirms"})


# --- start, open, show, list ----------------------------------------------------------------------------------------

def start(data_dir: Path | str, definition: str, subject: str, label: str, dates: Mapping[str, str], by: str, *,
          items: Iterable[str] = (), parent: str = "", yes: bool = False, at: str | None = None,
          today: date | None = None) -> dict[str, Any]:
    """Start a run as a draft: no clock runs until it is opened. A definition with a legal clock needs ``yes``."""
    by = _person(by)
    wf = _workflow(definition)
    if not (subject or "").strip():
        raise StepRefused("a run is about a subject")
    problems = wf.check_dates(dates)
    if problems:
        raise StepRefused("; ".join(problems))
    if wf.has_legal_clock() and not yes:
        raise StepRefused(f"{wf.key} has a legal clock: starting it needs yes")
    detail: dict[str, Any] = {"dates": {k: str(v) for k, v in dates.items() if v}, "draft": True}
    if items:
        detail["items"] = [str(i) for i in items]
    if parent:
        detail["parent"] = parent
    run = store.create(data_dir, definition, subject.strip(), by=by, label=label, detail=detail, at=at or "",
                       salt=secrets.token_hex(8))      # the id is a handle: nothing of the subject (a unit, a parcel) can be tried to recover it
    day = _today(today)
    _index(data_dir, run, day)
    return {"ok": True, "run": view_dict(_view(run, wf, day, None), run)}


def open_run(data_dir: Path | str, run_id: str, by: str, *, readers: Readers | None = None, yes: bool = False,
             roles_of: Callable[[str], Iterable[Any]] | None = None, expect: int | None = None, at: str | None = None,
             today: date | None = None) -> dict[str, Any]:
    """Open a run: a draft becomes active (its clocks start; a legal clock needs ``yes``), then the resume check runs
    and appends only what changed. Opening an active run again appends nothing when nothing changed."""
    by = _person(by)
    day = _today(today)
    definition = store.locate(data_dir, run_id)
    wf = _workflow(definition)
    activated = None
    with store._lock(run_id, "workflow open"):
        run = store.read(data_dir, definition, run_id)
        if expect is not None and expect != run.n:
            raise RunChanged(f"run {run_id} changed: you saw n={expect}, it is now n={run.n}; read it again", expected=expect, actual=run.n)
        view = _view(run, wf, day, readers)
        if view.state is RunState.DRAFT:
            if wf.has_legal_clock() and not yes:
                raise StepRefused(f"{wf.key} has a legal clock: opening the run starts it and needs yes")
            act = steps.activate_act(view, by=by)
            activated = store.append(data_dir, definition, run_id, act.kind, by=by, detail=act.detail, at=at or "", n=run.n + 1)
        appended = resume_mod.resume(run, wf, day, readers)
        run = store.read(data_dir, definition, run_id)
    _index(data_dir, run, day, readers)
    events = ([activated] if activated else []) + appended
    return {"ok": True, "appended": [e.to_dict() for e in events], "run": view_dict(_view(run, wf, day, readers), run)}


def show(data_dir: Path | str, run_id: str, *, today: date | None = None, readers: Readers | None = None,
         events: bool = False) -> dict[str, Any]:
    """A run as it stands now. It reads only: opening a run (``open_run``) is what appends."""
    definition = store.locate(data_dir, run_id)
    wf = _workflow(definition)
    run = store.read(data_dir, definition, run_id)
    out = view_dict(_view(run, wf, _today(today), readers), run)
    if events:
        out["events"] = [e.to_dict() for e in run.events]
    return out


def runs(data_dir: Path | str, *, definition: str = "", state: str = "open") -> list[dict[str, Any]]:
    """The run list, read from the index (``reindex`` rebuilds it). ``state`` is ``open`` (not done or cancelled),
    ``all``, or one state word."""
    rows = list(store.index_read(data_dir).values())
    if definition:
        rows = [r for r in rows if r.get("definition") == definition]
    if state == "open":
        rows = [r for r in rows if r.get("state") in OPEN_STATES]
    elif state != "all":
        rows = [r for r in rows if r.get("state") == state]
    return sorted(rows, key=lambda r: (str(r.get("due") or "9999"), str(r.get("id"))))


# --- the small acts -------------------------------------------------------------------------------------------------

def attest(data_dir: Path | str, run_id: str, step_id: str, by: str, *, roles_of: Callable[[str], Iterable[Any]] | None = None,
           record: str = "", what: str = "", item: str = "", outcome: str = "", motion: str = "", choice: str = "",
           readers: Readers | None = None, expect: int | None = None, at: str | None = None,
           today: date | None = None, gates: Gates | None = None) -> dict[str, Any]:
    """Record a person's attestation (a ``person`` step), the board's decision (a ``decision`` step, ``outcome`` given),
    or a person's answer on a ``branch`` with no fact to read (``choice``). Refused for a name without the step's role,
    and for a gate that is not met (``gates``; see the module note)."""
    day = _today(today)

    def make(wf: Workflow, view: RunView, run: store.Run) -> steps.Act:
        act = steps.attest_act(wf, view, step_id, by=by, roles_of=roles_of, record=record, what=what, item=item,
                               outcome=outcome, motion=motion, choice=choice, evidence=_evidence_for(wf, readers, step_id))
        return _gated(act, wf, view, run, step_id, "attest", by, roles_of=roles_of, gates=gates, data_dir=data_dir,
                      run_id=run_id, day=day, item=item, words=(record,))
    return _do(data_dir, run_id, by, make, expect=expect, today=today, at=at, readers=readers, needs_run=True)


def arrived(data_dir: Path | str, run_id: str, step_id: str, by: str, *, roles_of: Callable[[str], Iterable[Any]] | None = None,
            what: str = "", item: str = "", readers: Readers | None = None, expect: int | None = None,
            at: str | None = None, today: date | None = None) -> dict[str, Any]:
    return _do(data_dir, run_id, by, lambda wf, v: steps.arrived_act(wf, v, step_id, by=by, roles_of=roles_of, what=what, item=item),
               expect=expect, today=today, at=at, readers=readers)


def supply_items(data_dir: Path | str, run_id: str, item_set: str, items: Iterable[Any], by: str, *,
                 roles_of: Callable[[str], Iterable[Any]] | None = None, record: str = "", readers: Readers | None = None,
                 expect: int | None = None, at: str | None = None, today: date | None = None) -> dict[str, Any]:
    """Give a named item set (``""`` is the run's own) more items while the run goes. Each item is an opaque id, or
    ``{"id": ..., "dates": {slot: "YYYY-MM-DD"}}`` for the dates its own clocks read (those need a ``record``). The log gets a
    ``note`` event whose detail has ``items_supplied``; the steps that repeat over the set then take the items."""
    return _do(data_dir, run_id, by, lambda wf, v: steps.supply_items_act(wf, v, item_set=item_set, items=items, by=by,
                                                                          roles_of=roles_of, record=record),
               expect=expect, today=today, at=at, readers=readers)


def skip(data_dir: Path | str, run_id: str, step_id: str, by: str, *, roles_of: Callable[[str], Iterable[Any]] | None = None,
         reason: str = "", item: str = "", readers: Readers | None = None, expect: int | None = None, at: str | None = None,
         today: date | None = None, gates: Gates | None = None) -> dict[str, Any]:
    day = _today(today)

    def make(wf: Workflow, view: RunView, run: store.Run) -> steps.Act:
        act = steps.skip_act(wf, view, step_id, by=by, roles_of=roles_of, reason=reason, item=item)
        return _gated(act, wf, view, run, step_id, "skip", by, roles_of=roles_of, gates=gates, data_dir=data_dir,
                      run_id=run_id, day=day, item=item, words=(reason,))
    return _do(data_dir, run_id, by, make, expect=expect, today=today, at=at, readers=readers, needs_run=True)


def not_applicable(data_dir: Path | str, run_id: str, step_id: str, by: str, *,
                   roles_of: Callable[[str], Iterable[Any]] | None = None, reason: str = "", record: str = "", item: str = "",
                   readers: Readers | None = None, expect: int | None = None, at: str | None = None,
                   today: date | None = None, gates: Gates | None = None) -> dict[str, Any]:
    """Record a step as not applicable (its definition must declare ``na``): a person holding one of its roles, with a reason
    and a record. The step is done as not applicable, which satisfies what needs it; the legal clock on it is kept and reads
    "not applicable, recorded". It is not a skip, and a legal step may be recorded this way. The same gates apply as to a skip."""
    day = _today(today)

    def make(wf: Workflow, view: RunView, run: store.Run) -> steps.Act:
        act = steps.na_act(wf, view, step_id, by=by, roles_of=roles_of, reason=reason, record=record, item=item)
        return _gated(act, wf, view, run, step_id, "na", by, roles_of=roles_of, gates=gates, data_dir=data_dir,
                      run_id=run_id, day=day, item=item, words=(reason, record))
    return _do(data_dir, run_id, by, make, expect=expect, today=today, at=at, readers=readers, needs_run=True)


def set_date(data_dir: Path | str, run_id: str, slot: str, day: str, by: str, *,
             roles_of: Callable[[str], Iterable[Any]] | None = None, record: str = "", reason: str = "",
             readers: Readers | None = None, expect: int | None = None, at: str | None = None,
             today: date | None = None) -> dict[str, Any]:
    """Give a date slot a day after the run started (the slot must be ``late`` or optional on the definition). A person, with
    the record that shows the day; a slot that already has a day is corrected, which needs a ``reason``. Append-only: the
    latest ``date-set`` wins and every clock is read from the dates as they stand."""
    day_now = _today(today)
    return _do(data_dir, run_id, by,
               lambda wf, v: steps.date_set_act(wf, v, slot=slot, day=day, by=by, roles_of=roles_of, record=record, reason=reason,
                                                today=day_now),
               expect=expect, today=today, at=at, readers=readers)


def reopen(data_dir: Path | str, run_id: str, step_id: str, by: str, *, roles_of: Callable[[str], Iterable[Any]] | None = None,
           reason: str = "", item: str = "", readers: Readers | None = None, expect: int | None = None, at: str | None = None,
           today: date | None = None) -> dict[str, Any]:
    return _do(data_dir, run_id, by, lambda wf, v: steps.reopen_act(wf, v, step_id, by=by, roles_of=roles_of, reason=reason, item=item),
               expect=expect, today=today, at=at, readers=readers)


def pause(data_dir: Path | str, run_id: str, by: str, *, reason: str = "", readers: Readers | None = None,
          expect: int | None = None, at: str | None = None, today: date | None = None) -> dict[str, Any]:
    return _do(data_dir, run_id, by, lambda wf, v: steps.pause_act(v, by=by, reason=reason), expect=expect, today=today, at=at,
               readers=readers)


def resume_run(data_dir: Path | str, run_id: str, by: str, *, readers: Readers | None = None, expect: int | None = None,
               at: str | None = None, today: date | None = None) -> dict[str, Any]:
    """Lift a person's pause (the resume check is ``open_run``)."""
    return _do(data_dir, run_id, by, lambda wf, v: steps.resume_act(v, by=by), expect=expect, today=today, at=at, readers=readers)


def note(data_dir: Path | str, run_id: str, by: str, *, text: str, step: str = "", readers: Readers | None = None,
         expect: int | None = None, at: str | None = None, today: date | None = None) -> dict[str, Any]:
    return _do(data_dir, run_id, by, lambda wf, v: steps.note_act(v, by=by, text=text, step=step), expect=expect, today=today,
               at=at, readers=readers)


def cancel(data_dir: Path | str, run_id: str, by: str, *, roles_of: Callable[[str], Iterable[Any]] | None = None, reason: str = "",
           yes: bool = False, readers: Readers | None = None, expect: int | None = None, at: str | None = None,
           today: date | None = None) -> dict[str, Any]:
    return _do(data_dir, run_id, by, lambda wf, v: steps.cancel_act(wf, v, by=by, roles_of=roles_of, reason=reason, yes=yes),
               expect=expect, today=today, at=at, readers=readers)


def spawned(data_dir: Path | str, run_id: str, step_id: str, by: str, *, child: str, definition: str = "",
            readers: Readers | None = None, expect: int | None = None, at: str | None = None,
            today: date | None = None) -> dict[str, Any]:
    """Record that a step started a child run (the parent step then waits on it). The child is started with ``start``,
    its ``parent`` naming this run. A step may start several: call this once for each (a child already recorded from this
    step is refused). A step with ``waits_on_child`` is not done until each of them is done or cancelled."""
    def make(wf: Workflow, v: RunView) -> steps.Act:
        sd = wf.step(step_id)
        if sd is None or not sd.spawns:
            raise StepRefused(f"{step_id} does not spawn a run")
        if definition and definition != sd.spawns:
            raise StepRefused(f"{step_id} spawns {sd.spawns}, not {definition}")
        if v.state not in steps.ACTING:
            raise StepRefused(f"the run is {v.state.value}")
        _person(by)
        if not (child or "").strip():
            raise StepRefused(f"{step_id}: a child run is named by its id")
        sv = v.step(step_id)
        if sv is not None and child in sv.children:
            raise StepRefused(f"child run {child} is already recorded from {step_id}")
        return steps.Act(EventKind.SPAWNED, step_id, {"child": child, "definition": sd.spawns})
    return _do(data_dir, run_id, by, make, expect=expect, today=today, at=at, readers=readers)


# --- verify, reindex ------------------------------------------------------------------------------------------------

def verify(data_dir: Path | str, run_id: str) -> dict[str, Any]:
    """Check a run's hash chain; a broken link names the event (and the index's remembered tip covers an edited last line)."""
    definition = store.locate(data_dir, run_id)
    run = store.read(data_dir, definition, run_id)
    row = store.index_read(data_dir).get(run_id, {})
    result = store.verify(run, tip=str(row.get("tip", "")), tip_n=int(row.get("n", 0) or 0))
    return {"ok": result.ok, "run": run_id, "n": result.n, "message": result.message, "torn": run.torn, "events": result.events}


def reindex(data_dir: Path | str, *, today: date | None = None) -> dict[str, Any]:
    day = _today(today)
    rows = store.reindex(data_dir, lambda run: _summary(run, definitions.find(run.definition), day))
    return {"ok": True, "runs": len(rows), "rows": rows}


__all__ = ["arrived", "attest", "cancel", "not_applicable", "note", "open_run", "pause", "pending_first", "reindex", "reopen",
           "resume_run", "runs", "set_date", "show", "skip", "spawned", "start", "supply_items", "verify", "view_dict"]
