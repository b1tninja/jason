"""The resume check: what opening a run appends.

``resume(run, workflow, today, readers)`` re-reads the world a run points at and appends, under the run's lock, only what
changed:

- each ``check`` step that is ready or failed is run again (an identical result appends nothing);
- each done step's evidence addresses are compared with the stores now: a moved hash is one ``changed`` event, and the
  step reads "changed since" with the difference. A ``changed`` event never un-does a done step; a person reopens it;
- each ``plan`` step's approval status and each ``job`` step's job state are read, and ``approval-decided``, ``applied``,
  or ``job-finished`` is appended for what moved;
- a ``wait`` step's arrival is read (not for one that ends only by a person's note: no reader ends that).

It appends nothing when nothing changed, so a second open is a no-op. It never marks a person's step done, never decides,
submits, or applies an approval, and never sends. ``readers`` is everything it reads and the two things it may start (a
job in the queue, a plan in the approvals store); each is found again by the idempotence key
``sha1(run, step, subject, item)`` before another is made, and the key is stored in the event.

The reads are an injected object, so a test needs no real store and the engine imports no client. A run that is not
active (a draft, paused, cancelled, or done) is left alone.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from jason.workflows import fold, store
from jason.workflows.steps import Act, ACTING
from jason.workflows.types import (
    CheckResult, Event, EventKind, RunView, StepDef, StepKind, StepState, Workflow,
)


@dataclass(frozen=True)
class ApprovalState:
    id: str
    status: str                  # an ``ApprovalStatus`` word: planned, in_review, approved, applied, withdrawn, ...
    reason: str = ""


@dataclass(frozen=True)
class JobState:
    id: str
    state: str                   # queued, running, finished, failed
    message: str = ""


def idem_key(run: str, step: str, subject: str, item: str = "") -> str:
    """How a job or a plan is found again before another is made: ``sha1(run, step, subject, item)``."""
    return hashlib.sha1("\0".join((run, step, subject, item)).encode("utf-8")).hexdigest()


class Readers:
    """Everything a resume reads. The default knows nothing (every read is a miss, nothing is started); a caller subclasses
    it, or passes an object with the same methods. A read that cannot be made returns ``None`` and appends nothing."""

    def check(self, step: StepDef, view: RunView, item: str = "") -> CheckResult | None:
        return step.check(view) if step.check is not None else None

    def approval(self, key: str) -> ApprovalState | None:
        return None

    def make_plan(self, kind: str, key: str, step: StepDef, view: RunView, item: str = "") -> str | None:
        return None

    def job(self, key: str) -> JobState | None:
        return None

    def queue_job(self, name: str, key: str, step: StepDef, view: RunView, item: str = "") -> str | None:
        return None

    def evidence(self, address: str) -> str | None:
        return None

    def arrival(self, step: StepDef, view: RunView, item: str = "") -> str | None:
        return None

    def child_state(self, run_id: str) -> str | None:
        return None

    def holidays(self) -> frozenset[date]:
        """The days a business-day clock skips besides weekends. The default is none (an empty calendar); a reader that knows the
        community's holidays returns them. The fold is handed them as an argument and reads no calendar itself."""
        return frozenset()


def _last(events: list[Event]) -> dict[tuple[str, str, EventKind], Event]:
    """The latest event of each kind for each (step, item), forgetting what a ``reopened`` event reopened."""
    out: dict[tuple[str, str, EventKind], Event] = {}
    for e in events:
        if not e.step:
            continue
        item = str(e.detail.get("item", ""))
        if e.kind is EventKind.REOPENED:
            for key in [k for k in out if k[0] == e.step and (not item or k[1] == item)]:
                del out[key]
            continue
        out[(e.step, item, e.kind)] = e
    return out


class Outside(dict):
    """What the fold is told about the world outside the events: the child runs' state words (the mapping itself) and the
    calendar of holidays (``holidays``). It is a plain dict to every old caller; ``fold.state`` reads ``holidays`` from it."""

    holidays: frozenset[date] = frozenset()


def holidays_of(readers: Readers) -> frozenset[date]:
    """The readers' holidays as days. A calendar that cannot be read is an empty one, never an error."""
    try:
        return fold.holiday_days(readers.holidays())
    except Exception:  # noqa: BLE001 - no calendar means weekends only; the clock is then the earliest it can fall
        return frozenset()


def children_of(events: list[Event], readers: Readers) -> dict[str, str]:
    out = Outside()
    out.holidays = holidays_of(readers)
    for e in events:
        child = str(e.detail.get("child", "")) if e.kind is EventKind.SPAWNED else ""
        if child:
            state = readers.child_state(child)
            if state:
                out[child] = state
    return out


def _read_check(readers: Readers, sd: StepDef, view: RunView, item: str) -> CheckResult | None:
    try:
        return readers.check(sd, view, item)
    except Exception as exc:  # noqa: BLE001 - a check that cannot read is failed with the reason, never ok
        return CheckResult(False, (), f"cannot read: {exc}")


def _hashes(readers: Readers, addresses: tuple[str, ...]) -> list[str]:
    out = []
    for a in addresses:
        h = readers.evidence(a)
        if h:
            out.append(f"{a}@{h}")
    return out


def pending(view: RunView, events: list[Event], workflow: Workflow, readers: Readers) -> list[Act]:
    """What a resume would append now, in order. Pure of the store: it reads through ``readers`` only."""
    acts: list[Act] = []
    if view.state not in ACTING:
        return acts
    last = _last(events)
    for sd in workflow.steps:
        sv = view.step(sd.id)
        if sv is None:
            continue
        units = list(sv.items) if sv.items else [("", sv.state)]
        for item, state in units:
            tag = {"item": item} if item else {}
            ev = lambda kind: last.get((sd.id, item, kind))  # noqa: E731
            key = idem_key(view.id, sd.id, view.subject, item)
            if sd.kind in (StepKind.CHECK, StepKind.BRANCH) and sd.check is not None and state in (StepState.READY, StepState.FAILED):
                res = _read_check(readers, sd, view, item)
                if res is None:
                    continue
                ok, message = res.ok, res.message
                if sd.kind is StepKind.BRANCH and ok and res.choice not in [c.key for c in sd.choices]:
                    ok, message = False, f"the fact gave {res.choice!r}, which is not one of the paths"
                prev = ev(EventKind.CHECK_RAN)
                same = prev is not None and (bool(prev.detail.get("ok")), str(prev.detail.get("message", "")),
                                             tuple(prev.detail.get("evidence") or ()), str(prev.detail.get("choice", ""))) == (
                    ok, message, tuple(res.evidence), res.choice)
                if not same:
                    detail: dict[str, Any] = {"ok": ok, "message": message, "evidence": list(res.evidence), **tag}
                    if res.choice:
                        detail["choice"] = res.choice
                    acts.append(Act(EventKind.CHECK_RAN, sd.id, detail))
            elif sd.kind is StepKind.JOB:
                if state is StepState.READY and sd.job:
                    st = readers.job(key)
                    if st is not None:
                        acts.append(Act(EventKind.JOB_QUEUED, sd.id, {"key": key, "job": st.id, "found": True, **tag}))
                    else:
                        made = readers.queue_job(sd.job, key, sd, view, item)
                        if made:
                            acts.append(Act(EventKind.JOB_QUEUED, sd.id, {"key": key, "job": str(made), **tag}))
                elif state is StepState.RUNNING:
                    st = readers.job(key)
                    if st is not None and st.state == "finished":
                        acts.append(Act(EventKind.JOB_FINISHED, sd.id, {
                            "key": key, "job": st.id, "ok": True, "evidence": _hashes(readers, sd.evidence), **tag}))
                    elif st is not None and st.state == "failed":
                        acts.append(Act(EventKind.JOB_FINISHED, sd.id, {
                            "key": key, "job": st.id, "ok": False, "message": st.message or "the job failed", **tag}))
            elif sd.kind is StepKind.PLAN:
                if state is StepState.READY and sd.plan_kind:
                    st = readers.approval(key)
                    if st is not None:
                        acts.append(Act(EventKind.PLAN_MADE, sd.id, {"key": key, "approval": st.id, "found": True, **tag}))
                    else:
                        made = readers.make_plan(sd.plan_kind, key, sd, view, item)
                        if made:
                            acts.append(Act(EventKind.PLAN_MADE, sd.id, {"key": key, "approval": str(made), **tag}))
                elif state is StepState.WAITING:
                    st = readers.approval(key)
                    if st is None:
                        continue
                    made_ev, seen = ev(EventKind.PLAN_MADE), ev(EventKind.APPROVAL_DECIDED)
                    status_now = str(seen.detail.get("status")) if seen and made_ev and seen.n > made_ev.n else "planned"
                    if st.status == "applied":
                        acts.append(Act(EventKind.APPLIED, sd.id, {"key": key, "approval": st.id, "evidence": _hashes(readers, sd.evidence), **tag}))
                    elif st.status != status_now:
                        acts.append(Act(EventKind.APPROVAL_DECIDED, sd.id, {
                            "key": key, "approval": st.id, "status": st.status, **({"reason": st.reason} if st.reason else {}), **tag}))
            elif sd.kind is StepKind.WAIT and state is StepState.WAITING:
                if ev(EventKind.WAITED) is None:
                    due = fold.clock_due(sd.clock, view.dates) if sd.clock else None
                    acts.append(Act(EventKind.WAITED, sd.id, {"until": due.isoformat() if due else "", **tag}))
                came = None if sd.ends_by_note else readers.arrival(sd, view, item)
                if came:
                    acts.append(Act(EventKind.ARRIVED, sd.id, {"what": str(came), **tag}))
        # a done step whose evidence moved: one changed event, not an un-doing
        if sv.state is StepState.DONE and sv.evidence and not sv.items:
            baseline = fold.parse_evidence(sv.evidence)
            now = dict(baseline)
            diffs = []
            for address, was in baseline.items():
                cur = readers.evidence(address)
                if cur is not None and cur != was:
                    diffs.append({"address": address, "was": was, "now": cur})
                    now[address] = cur
            if diffs:
                acts.append(Act(EventKind.CHANGED, sd.id, {"differences": diffs, "evidence": fold.evidence_entries(now)}))
    return acts


def resume(run: store.Run, workflow: Workflow, today: date, readers: Readers | None = None, *, by: str = "jason",
           data_dir: Path | str | None = None) -> list[Event]:
    """Append what changed, under the run's lock, and return the events appended (none when nothing changed). Passes
    repeat until nothing more follows, since a check that passes makes the next step ready."""
    readers = readers or Readers()
    data = Path(data_dir) if data_dir is not None else run.data_dir
    appended: list[Event] = []
    with store._lock(run.id, "workflow resume"):
        current = store.read(data, run.definition, run.id)
        for _ in range(len(workflow.steps) * 3 + 5):
            events = list(current.events)
            view = fold.state(events, workflow, today, children_of(events, readers), run_id=run.id)
            acts = pending(view, events, workflow, readers)
            if not acts:
                break
            for act in acts:
                appended.append(store.append(data, run.definition, run.id, act.kind, by=by, step=act.step, detail=act.detail))
            current = store.read(data, run.definition, run.id)
    return appended


__all__ = ["ApprovalState", "JobState", "Outside", "Readers", "children_of", "holidays_of", "idem_key", "pending", "resume"]
