"""What the terminal command, the web loaders, and the MCP tools call: plain dicts in, plain dicts out.

Every function takes ``data_dir`` first and ``by`` (a signed-in name, or ``jason``/``scheduler``) for a write, and none
opens a browser or prints. A write reads the run under its lock, applies the step-kind contract (``jason.workflows.steps``),
and appends one event; ``expect`` is the ``n`` the caller last saw, and a run that has moved on is refused with
``RunChanged`` naming the changed ``n`` (two persons at once). ``roles_of(by)`` says which roles a name holds; the caller
(the web layer from the sign-in, a test from a table) supplies it, and none supplied means no roles, so every act that
needs one is refused. ``readers`` is the injectable world a resume and a ``show`` read (see ``jason.workflows.resume``).

Nothing here sends, files, or writes outside ``data_dir``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from jason.workflows import definitions, fold, resume as resume_mod, steps, store
from jason.workflows.resume import Readers
from jason.workflows.types import (
    ClockView, EventKind, Link, RunChanged, RunState, RunView, StepRefused, StepView, Workflow,
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
    return {"key": c.key, "basis": c.basis.value, "due": c.due, "label": c.label, "cite": c.cite, "status": c.status,
            "days": c.days, "step": c.step}


def _step(s: StepView) -> dict[str, Any]:
    return {"id": s.id, "title": s.title, "kind": s.kind.value, "role": s.role.value, "state": s.state.value,
            "reason": s.reason, "by": s.by, "at": s.at, "record": s.record, "blockedBy": list(s.blocked_by),
            "changed": [dict(c) for c in s.changed], "items": [{"item": i, "state": st.value} for i, st in s.items],
            "choice": s.choice}


def _link(link: Link) -> dict[str, str]:
    return {"kind": link.kind, "address": link.address, "step": link.step, "label": link.label}


def view_dict(view: RunView, run: store.Run | None = None) -> dict[str, Any]:
    out = {"id": view.id, "definition": view.definition, "subject": view.subject, "label": view.label, "owner": view.owner,
           "opened": view.opened_at, "state": view.state.value, "current": view.current, "n": view.n,
           "updated": view.updated, "dates": dict(view.dates), "items": list(view.items), "parent": view.parent,
           "pausedReason": view.paused_reason, "cancelledReason": view.cancelled_reason,
           "steps": [_step(s) for s in view.steps], "clocks": [_clock(c) for c in view.clocks],
           "links": [_link(l) for l in view.links], "orphans": list(view.orphans), "children": list(view.children),
           "pastLaw": list(view.past_law)}
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

def _do(data_dir: Path | str, run_id: str, by: str, make: Callable[[Workflow, RunView], steps.Act], *, expect: int | None,
        today: date | None, at: str | None, readers: Readers | None = None, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
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
        act = make(wf, view)
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
    run = store.create(data_dir, definition, subject.strip(), by=by, label=label, detail=detail, at=at or "")
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
           today: date | None = None) -> dict[str, Any]:
    """Record a person's attestation (a ``person`` step), the board's decision (a ``decision`` step, ``outcome`` given),
    or a person's answer on a ``branch`` with no fact to read (``choice``). Refused for a name without the step's role."""
    def make(wf: Workflow, view: RunView) -> steps.Act:
        return steps.attest_act(wf, view, step_id, by=by, roles_of=roles_of, record=record, what=what, item=item,
                                outcome=outcome, motion=motion, choice=choice, evidence=_evidence_for(wf, readers, step_id))
    return _do(data_dir, run_id, by, make, expect=expect, today=today, at=at, readers=readers)


def arrived(data_dir: Path | str, run_id: str, step_id: str, by: str, *, roles_of: Callable[[str], Iterable[Any]] | None = None,
            what: str = "", item: str = "", readers: Readers | None = None, expect: int | None = None,
            at: str | None = None, today: date | None = None) -> dict[str, Any]:
    return _do(data_dir, run_id, by, lambda wf, v: steps.arrived_act(wf, v, step_id, by=by, roles_of=roles_of, what=what, item=item),
               expect=expect, today=today, at=at, readers=readers)


def skip(data_dir: Path | str, run_id: str, step_id: str, by: str, *, roles_of: Callable[[str], Iterable[Any]] | None = None,
         reason: str = "", item: str = "", readers: Readers | None = None, expect: int | None = None, at: str | None = None,
         today: date | None = None) -> dict[str, Any]:
    return _do(data_dir, run_id, by, lambda wf, v: steps.skip_act(wf, v, step_id, by=by, roles_of=roles_of, reason=reason, item=item),
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
    its ``parent`` naming this run."""
    def make(wf: Workflow, v: RunView) -> steps.Act:
        sd = wf.step(step_id)
        if sd is None or not sd.spawns:
            raise StepRefused(f"{step_id} does not spawn a run")
        if definition and definition != sd.spawns:
            raise StepRefused(f"{step_id} spawns {sd.spawns}, not {definition}")
        if v.state not in steps.ACTING:
            raise StepRefused(f"the run is {v.state.value}")
        _person(by)
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


__all__ = ["arrived", "attest", "cancel", "note", "open_run", "pause", "reindex", "reopen", "resume_run", "runs", "show",
          "skip", "spawned", "start", "verify", "view_dict"]
