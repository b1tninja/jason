"""The approvals engine: plan, decide, submit, confirm, apply, and withdraw, each recorded in the audit log.

- ``plan(kind, live, by=...)`` runs the kind's planner on a live read and stores an ``Approval``; an open approval of
  the same kind and scope is superseded by it.
- ``decide(id, items, by=..., decision=...)`` records a named person's decision on approvable items. An item that is
  not approvable (held for the board, for a person, to confirm with the owner, informational) is refused, and so is a
  completion whose writes are not approved.
- ``submit(id, by=...)`` signs the decisions: approved, partially approved, or withdrawn when nothing was approved.
  ``confirm`` is the second, distinct person, needed when the kind is two-person or an approved item is high stakes;
  ``decline`` sends it back to review.
- ``check(id, live)`` re-plans and compares, writing nothing: what ``apply`` would do.
- ``apply(id, live, by=...)`` re-plans live. When an approved item's basis moved, is gone, or is now held, nothing is
  written: the approval is superseded and a new one is made from the re-plan. Otherwise only the approved items are
  applied, through the kind's applier, each result recorded as it comes.

jason never approves its own plan: every decision and signature names a person, and no ``jason-mcp`` tool calls these.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from jason.approvals import audit, registry, store
from jason.approvals.model import (OPEN, Approval, ApprovalStatus, Decision, DecisionRecord, Evidence, ItemClass,
                                   PlanItem, Result, Signature, basis_fingerprint, plan_fingerprint, same_person,
                                   transition)

S = ApprovalStatus


class Refused(ValueError):
    """The engine will not do what was asked. Nothing was changed."""


@dataclass
class Live:
    """What a planner and an applier reach: the system's client (PayHOA's, for a PayHOA kind), its organization, the
    profile's data folder, the .env, and today."""
    client: Any = None
    org_id: int = 0
    data_dir: Path | None = None
    env: Any = None
    today: date | None = None


@dataclass
class Planned:
    """A planner's answer: the items (each approvable one with its basis), the scope it planned, and what the reader
    sees beside them. ``context`` is the kind's own, in memory only, for its applier."""
    items: list[PlanItem]
    scope: dict[str, Any] = field(default_factory=dict)
    title: str = ""
    summary: dict[str, Any] = field(default_factory=dict)
    evidence: tuple[Evidence, ...] = ()
    cost_cents: int | None = None
    clock: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)
    context: Any = None


@dataclass
class Changed:
    id: str
    op: str
    label: str
    then: str                                  # the basis reviewed
    now: str                                   # the basis read now ("" when the item is gone)
    why: str


@dataclass
class Recheck:
    """A re-plan compared with an approval: what ``apply`` would do."""
    approval: Approval
    planned: Planned | None
    changed: list[Changed]
    new: list[PlanItem]                        # approvable items in the re-plan the approval does not have
    then: str                                  # the approved items' basis fingerprint at review
    now: str                                   # the same items' basis fingerprint now
    problems: list[str]                        # why apply is refused before any re-plan (status, second, age)

    @property
    def ok(self) -> bool:
        return not self.changed and not self.problems


@dataclass
class Applied:
    approval: Approval
    superseded_by: Approval | None = None
    changed: list[Changed] = field(default_factory=list)
    new: list[PlanItem] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _named(by: str, what: str) -> str:
    by = (by or "").strip()
    if not by:
        raise Refused(f"{what} names the person (by)")
    return by


def _profile() -> str:
    try:
        from jason.community.profile import profile_name

        return profile_name()
    except Exception:  # noqa: BLE001 - a missing profile leaves the field empty
        return ""


def _check_items(items: list[PlanItem]) -> None:
    from jason.community.intake import secret_reason

    seen: set[str] = set()
    for i in items:
        if i.id in seen:
            raise ValueError(f"the planner gave item {i.id} twice")
        seen.add(i.id)
        if i.approvable and not i.basis:
            raise ValueError(f"approvable item {i.id} has no basis: an apply could not tell whether it changed")
        if secret_reason(i.value):
            raise ValueError(f"item {i.id}'s value looks like a secret; jason never carries one")


def counts(a: Approval) -> dict[str, Any]:
    from collections import Counter

    return {"items": len(a.items), "byClass": dict(Counter(i.klass.value for i in a.items)),
            "byDecision": dict(Counter(i.decision.value for i in a.approvable)),
            "byResult": dict(Counter(i.result.value for i in a.items if i.result is not Result.PENDING))}


def _approval_from(kind: registry.ActionKind, planned: Planned, *, by: str, via: str, scope: dict[str, Any],
                   supersedes: str = "") -> Approval:
    now = _now()
    return Approval(store.new_id(), kind.key, planned.title or kind.title, planned.items,
                    plan_fingerprint(kind.key, scope, planned.items), read_at=now, requested_by=by, requested_at=now,
                    requested_via=via, scope=scope, profile=_profile(), evidence=tuple(planned.evidence),
                    cost_cents=planned.cost_cents if kind.has_cost else None, clock=planned.clock,
                    summary=dict(planned.summary), notes=list(planned.notes), supersedes=supersedes)


def needs_second(a: Approval, kind: registry.ActionKind | None = None) -> bool:
    """Whether a second, distinct person must sign before apply: a two-person kind, or a high-stakes approved item."""
    kind = kind or registry.get(a.kind)
    return kind.approver is registry.Approver.TWO_PERSON or any(i.high_stakes for i in a.approved)


# --- plan ---------------------------------------------------------------------------------------------------------------

def plan(kind_key: str, live: Live, *, by: str, via: str = "cli", scope: dict[str, Any] | None = None) -> Approval:
    """Run the kind's planner on a live read and store the approval, superseding an open one of the same kind and
    scope."""
    by = _named(by, "a plan")
    kind = registry.get(kind_key)
    scope = {**kind.default_scope, **(scope or {})}
    try:
        planned = kind.plan(live, scope)
        _check_items(planned.items)
    except Exception as exc:
        audit.append(live.data_dir, "plan.failed", kind=kind.key, actor=by, via=via,
                     detail=f"{type(exc).__name__}: {exc}")
        raise
    approval = _approval_from(kind, planned, by=by, via=via, scope=planned.scope or scope)
    _store_new(approval, live.data_dir, by=by, via=via)
    return approval


def _store_new(approval: Approval, data_dir: Path | None, *, by: str, via: str) -> None:
    replaced = []
    with store.locked("plan"):
        for old in store.load_all(data_dir):
            if old.kind == approval.kind and old.scope == approval.scope and old.status in OPEN:
                transition(old, S.SUPERSEDED)
                old.superseded_by = approval.id
                old.notes.append(f"superseded by {approval.id}, a newer plan of the same kind and scope")
                store.save(old, data_dir)
                replaced.append(old)
        store.save(approval, data_dir)
    for old in replaced:
        audit.append(data_dir, "approval.superseded", approval=old.id, kind=old.kind, actor=by, via=via,
                     fingerprint=old.fingerprint, detail=f"a newer plan: {approval.id}")
    audit.append(data_dir, "plan.created", approval=approval.id, kind=approval.kind, actor=by, via=via,
                 fingerprint=approval.fingerprint, result=counts(approval)["byClass"],
                 detail=f"supersedes {approval.supersedes}" if approval.supersedes else "")


# --- decide, submit, confirm, decline, withdraw -----------------------------------------------------------------------

def _why_not(i: PlanItem) -> str:
    if i.klass is ItemClass.HELD_FOR_BOARD:
        board = f" (board item {i.board_item})" if i.board_item else ""
        return f"{i.id} is held for the board{board}: never approvable"
    return f"{i.id} is {i.klass.value.replace('_', ' ')}: never approvable"


def decide(approval_id: str, items: Iterable[str] | str, *, by: str, decision: Decision = Decision.APPROVED,
           reason: str = "", via: str = "cli", data_dir: Path | None = None) -> Approval:
    """Record ``by``'s decision on ``items`` (ids, unique prefixes, or "all" for every approvable item). A rejection
    or a hold says why. An item that is not approvable is refused, and so is approving a completion whose writes are
    not approved. Rejecting or holding a write makes a completion that waits on it undecided again."""
    by = _named(by, "a decision")
    if decision is Decision.UNDECIDED:
        raise Refused("a decision approves, rejects, or holds")
    if decision is not Decision.APPROVED and not (reason or "").strip():
        raise Refused(f"an item {decision.value} says why (reason)")
    with store.locked("decide"):
        a = store.load(approval_id, data_dir)
        if a.status not in (S.PLANNED, S.IN_REVIEW):
            raise Refused(f"{a.id} is {a.status.value}: items are decided before it is submitted")
        if items == "all" or list(items) == ["all"]:
            chosen = list(a.approvable)
        else:
            try:
                chosen = [a.item(i) for i in items]
            except KeyError as exc:
                raise Refused(str(exc.args[0])) from exc
        if not chosen:
            raise Refused("no items named")
        refused = [_why_not(i) for i in chosen if not i.approvable]
        if refused:
            raise Refused("; ".join(refused))
        ids = {i.id for i in chosen}
        if decision is Decision.APPROVED:
            for i in chosen:
                waits = [d for d in i.depends_on if d not in ids and a.item(d).decision is not Decision.APPROVED]
                if waits:
                    raise Refused(f"{i.id} ({i.op}: {i.label}) waits on {', '.join(waits)}: approve those first; "
                                  "until they are, it stays open")
        now = _now()
        for i in chosen:
            i.decision, i.decided_by, i.decided_at, i.reason = decision, by, now, reason
        reset = []
        if decision is not Decision.APPROVED:
            for other in a.items:
                if other.decision is Decision.APPROVED and ids & set(other.depends_on):
                    other.decision, other.decided_by, other.decided_at, other.reason = Decision.UNDECIDED, "", "", ""
                    reset.append(other.id)
        a.decisions.append(DecisionRecord(by, now, tuple(sorted(ids)), decision, reason, a.fingerprint, via))
        transition(a, S.IN_REVIEW)
        store.save(a, data_dir)
    audit.append(data_dir, "item.decided", approval=a.id, kind=a.kind, actor=by, via=via, items=sorted(ids),
                 result=decision.value, detail=(reason + (f"; undecided again: {', '.join(reset)}" if reset else "")),
                 fingerprint=a.fingerprint)
    return a


def submit(approval_id: str, *, by: str, role: str = "manager", via: str = "cli",
           data_dir: Path | None = None) -> Approval:
    """Sign the decisions: every approvable item decided. All approved: approved; some: partially approved; none:
    withdrawn ("nothing approved")."""
    by = _named(by, "a submission")
    with store.locked("submit"):
        a = store.load(approval_id, data_dir)
        if a.status is not S.IN_REVIEW:
            raise Refused(f"{a.id} is {a.status.value}: decide its items first")
        undecided = [i.id for i in a.approvable if i.decision is Decision.UNDECIDED]
        if undecided:
            raise Refused(f"{len(undecided)} approvable item(s) undecided: {', '.join(undecided[:8])}")
        orphans = [i.id for i in a.approved if any(a.item(d).decision is not Decision.APPROVED for d in i.depends_on)]
        if orphans:
            raise Refused(f"approved item(s) wait on items not approved: {', '.join(orphans)}")
        a.first, a.second = Signature(by, _now(), a.fingerprint, role, via), None
        approved = a.approved
        if not approved:
            transition(a, S.WITHDRAWN)
            a.notes.append("nothing approved")
        else:
            transition(a, S.APPROVED if len(approved) == len(a.approvable) else S.PARTIALLY_APPROVED)
        store.save(a, data_dir)
    audit.append(data_dir, "approval.submitted", approval=a.id, kind=a.kind, actor=by, via=via, role=role,
                 fingerprint=a.fingerprint, result=a.status.value,
                 items=sorted(i.id for i in a.approved))
    if a.status is S.WITHDRAWN:
        audit.append(data_dir, "approval.withdrawn", approval=a.id, kind=a.kind, actor=by, via=via,
                     detail="nothing approved")
    return a


def confirm(approval_id: str, *, by: str, role: str = "manager", via: str = "cli",
            data_dir: Path | None = None) -> Approval:
    """The second person signs the same fingerprint. Refused for the person who submitted or asked for the plan."""
    by = _named(by, "a confirmation")
    with store.locked("confirm"):
        a = store.load(approval_id, data_dir)
        if a.status not in (S.APPROVED, S.PARTIALLY_APPROVED):
            raise Refused(f"{a.id} is {a.status.value}: a second person confirms a submitted approval")
        if not needs_second(a):
            raise Refused(f"{a.id} needs no second person")
        if a.second is not None:
            raise Refused(f"{a.id} is already confirmed by {a.second.name}")
        if a.first is not None and same_person(by, a.first.name):
            raise Refused(f"a second, distinct person confirms: {by} submitted it")
        if same_person(by, a.requested_by):
            raise Refused(f"a second, distinct person confirms: {by} asked for the plan")
        a.second = Signature(by, _now(), a.fingerprint, role, via)
        store.save(a, data_dir)
    audit.append(data_dir, "approval.confirmed", approval=a.id, kind=a.kind, actor=by, via=via, role=role,
                 fingerprint=a.fingerprint)
    return a


def decline(approval_id: str, *, by: str, reason: str, via: str = "cli", data_dir: Path | None = None) -> Approval:
    """The second person declines: back to review, decisions kept, the first signature cleared."""
    by = _named(by, "a decline")
    if not (reason or "").strip():
        raise Refused("a decline says why (reason)")
    with store.locked("decline"):
        a = store.load(approval_id, data_dir)
        if a.status not in (S.APPROVED, S.PARTIALLY_APPROVED):
            raise Refused(f"{a.id} is {a.status.value}: only a submitted approval is declined")
        if a.first is not None and same_person(by, a.first.name):
            raise Refused(f"{by} submitted it: the second person declines")
        transition(a, S.IN_REVIEW)
        a.first = a.second = None
        store.save(a, data_dir)
    audit.append(data_dir, "approval.declined", approval=a.id, kind=a.kind, actor=by, via=via, detail=reason)
    return a


def withdraw(approval_id: str, *, by: str, reason: str, via: str = "cli", data_dir: Path | None = None) -> Approval:
    by = _named(by, "a withdrawal")
    if not (reason or "").strip():
        raise Refused("a withdrawal says why (reason)")
    with store.locked("withdraw"):
        a = store.load(approval_id, data_dir)
        if a.status not in OPEN:
            raise Refused(f"{a.id} is {a.status.value}: it cannot be withdrawn")
        transition(a, S.WITHDRAWN)
        a.notes.append(f"withdrawn by {by}: {reason}")
        store.save(a, data_dir)
    audit.append(data_dir, "approval.withdrawn", approval=a.id, kind=a.kind, actor=by, via=via, detail=reason)
    return a


# --- check and apply ----------------------------------------------------------------------------------------------------

def _problems(a: Approval, kind: registry.ActionKind) -> list[str]:
    out = []
    if a.status not in (S.APPROVED, S.PARTIALLY_APPROVED):
        out.append(f"{a.id} is {a.status.value}: only an approved or partially approved approval is applied")
    elif a.first is None:
        out.append(f"{a.id} is not submitted")
    if a.status in (S.APPROVED, S.PARTIALLY_APPROVED) and needs_second(a, kind) and a.second is None:
        out.append("a second, distinct person must confirm first (jason approvals confirm ID --by NAME)")
    try:
        read = datetime.fromisoformat(a.read_at)
    except ValueError:
        read = None
    if read is not None and datetime.now(timezone.utc) - read > timedelta(hours=kind.max_age_hours):
        out.append(f"planned at {a.read_at}, more than {kind.max_age_hours} hours ago: plan again")
    return out


def problems(a: Approval) -> list[str]:
    """Why ``apply`` would refuse before any live read (its status, a missing second person, its age); empty when it
    would go on to re-plan. A caller that must sign in to read live asks this first."""
    return _problems(a, registry.get(a.kind))


def compare(a: Approval, planned: Planned) -> tuple[list[Changed], list[PlanItem]]:
    """Each approved item against the re-plan: gone, now not approvable, or its basis moved is a change. Approvable
    items the approval does not have are new."""
    now = {i.id: i for i in planned.items}
    changed = []
    for i in a.approved:
        j = now.get(i.id)
        if j is None:
            changed.append(Changed(i.id, i.op, i.label, i.basis, "", "no longer in the plan"))
        elif not j.approvable:
            board = f" (board item {j.board_item})" if j.board_item else ""
            changed.append(Changed(i.id, i.op, i.label, i.basis, j.basis, f"now {j.klass.value}{board}"))
        elif j.basis != i.basis:
            changed.append(Changed(i.id, i.op, i.label, i.basis, j.basis, "what it relies on changed since review"))
    known = {i.id for i in a.items}
    return changed, [j for j in planned.items if j.approvable and j.id not in known]


def check(approval_id: str, live: Live, *, data_dir: Path | None = None) -> Recheck:
    """Re-plan live and compare, writing nothing: what ``apply`` would do."""
    data_dir = data_dir if data_dir is not None else live.data_dir
    a = store.load(approval_id, data_dir)
    kind = registry.get(a.kind)
    problems = _problems(a, kind)
    then = basis_fingerprint(a.approved)
    if a.status not in OPEN:
        return Recheck(a, None, [], [], then, "", problems)
    planned = kind.plan(live, a.scope)
    changed, new = compare(a, planned)
    now_items = {j.id: j for j in planned.items}
    now = basis_fingerprint([now_items[i.id] for i in a.approved if i.id in now_items])
    return Recheck(a, planned, changed, new, then, now, problems)


_EVENT = {Result.APPLIED: "item.applied", Result.FAILED: "item.failed", Result.UNCERTAIN: "item.uncertain",
          Result.BLOCKED: "item.blocked", Result.NOT_APPLIED: "item.not_applied"}


class Recorder:
    """What the applier reports through: the intent before a request (``applying``), and each item's result as it
    comes (``done``), saved and logged at once so a crash leaves the record."""

    def __init__(self, approval: Approval, data_dir: Path | None, *, actor: str, via: str) -> None:
        self.approval, self.data_dir, self.actor, self.via = approval, data_dir, actor, via
        self.in_flight: set[str] = set()

    def _log(self, event: str, item: PlanItem, **fields: Any) -> None:
        audit.append(self.data_dir, event, approval=self.approval.id, kind=self.approval.kind, actor=self.actor,
                     via=self.via, item=item.id, op=item.op, target=item.target, label=item.label, value=item.value,
                     basis=item.basis, fingerprint=self.approval.fingerprint, **fields)

    def applying(self, ids: Iterable[str]) -> None:
        for ident in ids:
            self.in_flight.add(ident)
            self._log("item.applying", self.approval.item(ident))

    def result(self, ident: str) -> Result:
        return self.approval.item(ident).result

    def done(self, ident: str, result: Result, detail: str = "") -> None:
        item = self.approval.item(ident)
        item.result, item.result_detail = result, audit.mask(detail)
        self.in_flight.discard(ident)
        with store.locked("apply"):
            store.save(self.approval, self.data_dir)
        self._log(_EVENT.get(result, "item.failed"), item, result=result.value, detail=detail)


def apply(approval_id: str, live: Live, *, by: str, via: str = "cli", data_dir: Path | None = None) -> Applied:
    """Re-plan live; refuse and supersede when an approved item changed; else apply only the approved items."""
    from jason.locks import Resource, hold

    by = _named(by, "an apply")
    data_dir = data_dir if data_dir is not None else live.data_dir
    ident = store.resolve(approval_id, data_dir)
    with hold(Resource.STORE, f"approval-{ident}", timeout=5, purpose=f"apply {ident}"):
        a = store.load(ident, data_dir)
        kind = registry.get(a.kind)
        problems = _problems(a, kind)
        if problems:
            audit.append(data_dir, "apply.refused", approval=a.id, kind=a.kind, actor=by, via=via,
                         fingerprint=a.fingerprint, detail="; ".join(problems))
            raise Refused("; ".join(problems))
        with hold(kind.resource, f"approval-{ident}", timeout=60, purpose=f"apply {ident}"):
            try:
                planned = kind.plan(live, a.scope)
                _check_items(planned.items)
            except Exception as exc:
                audit.append(data_dir, "plan.failed", approval=a.id, kind=a.kind, actor=by, via=via,
                             detail=f"re-plan before apply: {type(exc).__name__}: {exc}")
                raise
            changed, new = compare(a, planned)
            if changed:
                return _supersede(a, kind, planned, changed, new, by=by, via=via, data_dir=data_dir)
            return _run(a, kind, planned, new, live, by=by, via=via, data_dir=data_dir)


def _supersede(a: Approval, kind: registry.ActionKind, planned: Planned, changed: list[Changed], new: list[PlanItem],
               *, by: str, via: str, data_dir: Path | None) -> Applied:
    """Nothing is written: the approval is superseded, and the re-plan is a new approval to review."""
    fresh = _approval_from(kind, planned, by=by, via=via, scope=a.scope, supersedes=a.id)
    known = {i.id for i in fresh.items}
    fresh.notes += [f"{i.id}: {i.decision.value} earlier by {i.decided_by} (a hint, not counted)"
                    for i in a.items if i.decision is not Decision.UNDECIDED and i.id in known]
    with store.locked("apply"):
        current = store.load(a.id, data_dir)
        for c in changed:
            item = current.item(c.id)
            item.result, item.result_detail = Result.CHANGED, c.why
        transition(current, S.SUPERSEDED)
        current.superseded_by = fresh.id
        current.result = {"refused": "changed since review", "changed": [c.id for c in changed], "at": _now()}
        store.save(current, data_dir)
    audit.append(data_dir, "apply.refused", approval=a.id, kind=a.kind, actor=by, via=via, fingerprint=a.fingerprint,
                 detail="changed since review",
                 result={"changed": [{"item": c.id, "op": c.op, "label": c.label, "then": c.then, "now": c.now,
                                      "why": c.why} for c in changed]})
    audit.append(data_dir, "approval.superseded", approval=a.id, kind=a.kind, actor=by, via=via,
                 fingerprint=a.fingerprint, detail=f"changed since review: re-planned as {fresh.id}")
    _store_new(fresh, data_dir, by=by, via=via)
    return Applied(current, fresh, changed, new)


def _run(a: Approval, kind: registry.ActionKind, planned: Planned, new: list[PlanItem], live: Live, *, by: str,
         via: str, data_dir: Path | None) -> Applied:
    with store.locked("apply"):
        a = store.load(a.id, data_dir)
        transition(a, S.APPLYING)
        for i in a.items:
            if not (i.approvable and i.decision is Decision.APPROVED):
                i.result = Result.NOT_APPLIED
                i.result_detail = (f"{i.decision.value} by {i.decided_by}: {i.reason}" if i.approvable
                                   else i.klass.value.replace("_", " "))
        if new:
            a.notes.append(f"{len(new)} approvable item(s) new since review, not included: plan again for them")
        store.save(a, data_dir)
    audit.append(data_dir, "apply.started", approval=a.id, kind=a.kind, actor=by, via=via, fingerprint=a.fingerprint,
                 items=sorted(i.id for i in a.approved),
                 detail=f"{len(new)} new since review, not included" if new else "")
    approved = {i.id for i in a.approved}
    recorder = Recorder(a, data_dir, actor=by, via=via)
    ready = []
    for j in planned.items:
        if j.id not in approved:
            continue
        missing = [d for d in j.depends_on if d not in approved]
        if missing:
            recorder.done(j.id, Result.BLOCKED, f"waits on items not approved: {', '.join(missing)}")
        else:
            ready.append(j)
    try:
        kind.apply(live, planned, ready, recorder)
    except Exception as exc:  # noqa: BLE001 - every item still open is recorded with the error
        for j in ready:
            if recorder.result(j.id) is Result.PENDING:
                recorder.done(j.id, Result.UNCERTAIN if j.id in recorder.in_flight else Result.FAILED,
                              f"{type(exc).__name__}: {exc}")
    for j in ready:
        if recorder.result(j.id) is Result.PENDING:
            recorder.done(j.id, Result.FAILED, "the applier gave no result")
    a = recorder.approval
    with store.locked("apply"):
        transition(a, S.APPLIED if all(i.result is Result.APPLIED for i in a.approved) else S.FAILED)
        a.result = {**counts(a)["byResult"], "at": _now(), "by": by}
        store.save(a, data_dir)
    audit.append(data_dir, "approval.applied" if a.status is S.APPLIED else "approval.failed", approval=a.id,
                 kind=a.kind, actor=by, via=via, fingerprint=a.fingerprint, result=counts(a)["byResult"])
    return Applied(a, None, [], new)


__all__ = ["Applied", "Changed", "Live", "Planned", "Recheck", "Recorder", "Refused", "apply", "check", "compare",
           "confirm", "counts", "decide", "decline", "needs_second", "plan", "problems", "submit", "withdraw"]
