"""The approvals engine: plan, decide, submit, confirm, apply, and withdraw, each recorded in the audit log.

- ``plan(kind, live, by=...)`` runs the kind's planner on a live read and stores an ``Approval``; an open approval of
  the same kind and scope is superseded by it.
- ``decide(id, items, by=..., decision=...)`` records a named person's decision on approvable items. An item that is
  not approvable (for a person, to confirm with the owner, informational) is refused, and so is a completion whose
  writes are not approved. An item **flagged for review** (held for the board by jason's policy finding) is refused
  too, unless the caller passes ``exception=True`` with a reason in words: then it is decided as a one-off exception
  (docs/held-items.md). An exception approved is high stakes (a second, distinct person signs, by the rule that
  already exists), and each exception decision is a line in the exceptions log (``jason.approvals.exceptions``).
  ``refer`` puts the finding before the board and decides nothing.
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

from jason.approvals import audit, exceptions, registry, store
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
    terminal: bool = False                     # set only by the command a person runs at a terminal, for a terminal-only kind


@dataclass
class Planned:
    """A planner's answer: the items (each approvable one with its basis), the scope it planned, and what the reader
    sees beside them. ``context`` is the kind's own, in memory only, for its applier. ``read_at`` is when the planner
    read the live state ("" for now). ``snapshots`` is what it read of each record its evidence names, by address
    (``{address: {label, kind, readAt, digest, status, fields: [{name, value, ...}]}}``): the engine writes it beside
    the approval (``store.save_snapshots``) so the evidence can be opened later from disk."""
    items: list[PlanItem]
    scope: dict[str, Any] = field(default_factory=dict)
    title: str = ""
    summary: dict[str, Any] = field(default_factory=dict)
    evidence: tuple[Evidence, ...] = ()
    cost_cents: int | None = None
    clock: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)
    context: Any = None
    read_at: str = ""
    snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)


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
            "byResult": dict(Counter(i.result.value for i in a.items if i.result is not Result.PENDING)),
            "flaggedCount": len(a.flagged),
            "decidedByException": sum(1 for i in a.flagged if i.exception and i.decision is Decision.APPROVED)}


def _approval_from(kind: registry.ActionKind, planned: Planned, *, by: str, via: str, scope: dict[str, Any],
                   supersedes: str = "") -> Approval:
    now = _now()
    return Approval(store.new_id(), kind.key, planned.title or kind.title, planned.items,
                    plan_fingerprint(kind.key, scope, planned.items), read_at=planned.read_at or now, requested_by=by,
                    requested_at=now,
                    requested_via=via, scope=scope, profile=_profile(), evidence=tuple(planned.evidence),
                    cost_cents=planned.cost_cents if kind.has_cost else None, clock=planned.clock,
                    summary=dict(planned.summary), notes=list(planned.notes), supersedes=supersedes)


def needs_second(a: Approval, kind: registry.ActionKind | None = None, *, data_dir: Path | None = None) -> bool:
    """Whether a second, distinct person must sign before apply: a two-person kind, a high-stakes approved item, or a
    control the board adopted (``jason.controls``; it only adds, and asks nothing when none is configured)."""
    kind = kind or registry.get(a.kind)
    if kind.approver is registry.Approver.TWO_PERSON or any(i.high_stakes for i in a.approved):
        return True
    from jason.controls.effective import requires_second

    return requires_second(kind.key, a.scope, amount_cents=a.cost_cents, data_dir=data_dir, kind=kind)


def control_refusals(a: Approval, kind: registry.ActionKind | None = None, *, data_dir: Path | None = None) -> list[str]:
    """Why the controls the board adopted refuse this plan (a control in force the roster cannot satisfy); empty when
    none is configured. A control binds from its effective date whether or not the roster can satisfy it."""
    kind = kind or registry.get(a.kind)
    from jason.controls.effective import refusals

    return refusals(kind.key, a.scope, amount_cents=a.cost_cents, data_dir=data_dir, kind=kind)


def signer_refusals(a: Approval, signers: Iterable[str], *, final: bool, kind: registry.ActionKind | None = None,
                    data_dir: Path | None = None) -> list[str]:
    """Why these signers do not hold the offices the controls the board adopted ask for on this plan (``roles``: the
    offices that may sign; ``must_include``: offices among the signers, asked only when ``final``, the set complete).
    A signer's offices come from the roster by name; a name not on it holds none. Empty when none is configured."""
    kind = kind or registry.get(a.kind)
    from jason.controls.effective import signer_refusals as asked

    return asked(kind.key, a.scope, list(signers), final=final, amount_cents=a.cost_cents, data_dir=data_dir, kind=kind)


def prefs_for(kind: registry.ActionKind, data_dir: Path | None = None) -> Any:
    """The apply preferences that hold for a kind (``jason.controls.apply_prefs``): where apply happens, who may apply, a
    pause, a typed count, and a reminder. The defaults until the board adopts one; reads nothing when no controls source is
    configured. They never change who signs or how many."""
    from jason.controls import apply_prefs

    return apply_prefs.effective(kind, data_dir=data_dir)


def apply_refusals(a: Approval, *, by: str, typed_count: int | None = None, data_dir: Path | None = None,
                   kind: registry.ActionKind | None = None) -> list[str]:
    """Why the preferences the board adopted refuse this person's apply of this plan, empty when none does: who may apply
    (a person who signed, or who did not), and the typed count above the board's number of changes. The pause is judged by
    ``problems``, which needs no actor. The console's own choice (``where``) is the web route's."""
    from jason.controls import apply_prefs

    kind = kind or registry.get(a.kind)
    prefs = prefs_for(kind, data_dir)
    out: list[str] = []
    if prefs.who_adopted or prefs.who == "clash":
        from jason.controls.effective import _community_roster

        out += apply_prefs.who_problems(prefs, by, [s.name for s in (a.first, a.second) if s is not None],
                                        _community_roster())
    typed = apply_prefs.typed_problem(prefs, len(a.approved), typed_count)
    return out + ([typed] if typed else [])


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
    _store_new(approval, live.data_dir, by=by, via=via, snapshots=planned.snapshots)
    return approval


def _store_new(approval: Approval, data_dir: Path | None, *, by: str, via: str,
               snapshots: dict[str, Any] | None = None) -> None:
    """Store a new approval, superseding an open one of the same kind and scope, with the plan's snapshot of what it
    read beside it, under one lock."""
    replaced = []
    with store.locked("plan"):
        for old in store.load_all(data_dir):
            if old.kind == approval.kind and old.scope == approval.scope and old.status in OPEN:
                transition(old, S.SUPERSEDED)
                old.superseded_by = approval.id
                old.notes.append(f"superseded by {approval.id}, a newer plan of the same kind and scope")
                store.save(old, data_dir)
                replaced.append(old)
        store.save_snapshots(approval.id, snapshots or {}, data_dir)
        store.save(approval, data_dir)
    for old in replaced:
        audit.append(data_dir, "approval.superseded", approval=old.id, kind=old.kind, actor=by, via=via,
                     fingerprint=old.fingerprint, detail=f"a newer plan: {approval.id}")
    audit.append(data_dir, "plan.created", approval=approval.id, kind=approval.kind, actor=by, via=via,
                 fingerprint=approval.fingerprint, result=counts(approval)["byClass"],
                 detail=f"supersedes {approval.supersedes}" if approval.supersedes else "")


# --- decide, submit, confirm, decline, withdraw -----------------------------------------------------------------------

def _why_not(i: PlanItem) -> str:
    if i.flagged:
        board = f" (board item {i.board_item})" if i.board_item else ""
        return (f"{i.id} is held for the board{board}, flagged for review: it is decided only as a one-off exception "
                "(pass the exception flag and a reason in words)")
    return f"{i.id} is {i.klass.value.replace('_', ' ')}: never approvable"


def reason_in_words(reason: str) -> bool:
    """Whether a reason is words and not a token: at least ``exceptions.REASON_WORDS`` words ("ok" is not a reason)."""
    return len((reason or "").split()) >= exceptions.REASON_WORDS


def decide(approval_id: str, items: Iterable[str] | str, *, by: str, decision: Decision = Decision.APPROVED,
           reason: str = "", via: str = "cli", exception: bool = False, data_dir: Path | None = None) -> Approval:
    """Record ``by``'s decision on ``items`` (ids, unique prefixes, or "all" for every approvable item). A rejection
    or a hold says why. An item that is not approvable is refused, and so is approving a completion whose writes are
    not approved. Rejecting or holding a write makes a completion that waits on it undecided again.

    ``exception=True`` is for items **flagged for review** (held for the board by jason's policy finding), and only
    for them: each is approved as a one-off exception (a reason in words; the item becomes high stakes, so a second,
    distinct person signs), rejected (a reason), or kept flagged (``Decision.HELD``, a reason). Without the flag a
    flagged item is refused, and no other non-approvable class is ever decided. ``"all"`` never includes one."""
    by = _named(by, "a decision")
    if decision is Decision.UNDECIDED:
        raise Refused("a decision approves, rejects, or holds")
    if decision is not Decision.APPROVED and not (reason or "").strip():
        raise Refused(f"an item {decision.value} says why (reason)")
    if exception and decision is Decision.APPROVED and not reason_in_words(reason):
        raise Refused(f"an exception says why in words (reason): at least {exceptions.REASON_WORDS} words")
    with store.locked("decide"):
        a = store.load(approval_id, data_dir)
        if a.status not in (S.PLANNED, S.IN_REVIEW):
            raise Refused(f"{a.id} is {a.status.value}: items are decided before it is submitted")
        if items == "all" or list(items) == ["all"]:
            if exception:
                raise Refused('an exception names the flagged item (items): "all" never includes one')
            chosen = list(a.approvable)
        else:
            try:
                chosen = [a.item(i) for i in items]
            except KeyError as exc:
                raise Refused(str(exc.args[0])) from exc
        if not chosen:
            raise Refused("no items named")
        if exception:
            refused = [f"{i.id} is not flagged for review: the exception flag is for flagged items only"
                       for i in chosen if not i.flagged]
            refused += [f"{i.id} has no basis: an apply could not tell whether it changed since review"
                        for i in chosen if i.flagged and decision is Decision.APPROVED and not i.basis]
        else:
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
            if exception:
                # an approved exception is high stakes: the second, distinct person signs, by the rule that exists
                i.exception, i.high_stakes = True, decision is Decision.APPROVED
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
                 result=decision.value,
                 detail=(("one-off exception: " if exception else "") + reason
                         + (f"; undecided again: {', '.join(reset)}" if reset else "")),
                 fingerprint=a.fingerprint)
    if exception:
        for i in chosen:
            exceptions.record(a.id, i, by=by, decision=decision, reason=reason, kind=a.kind, at=now, data_dir=data_dir)
    return a


def refer(approval_id: str, item: str, *, by: str, via: str = "cli", data_dir: Path | None = None
          ) -> tuple[Approval, Any]:
    """Put the finding of a flagged item before the board: make or refresh its board item, proposed for the next agenda
    (``jason.tasks.board_items``), with this plan's evidence. It decides nothing and writes nothing outside jason. The
    plan's flagged items of the finding name the board item afterwards. Returns the approval and the board item."""
    by = _named(by, "a referral")
    from jason.tasks import board_items

    if data_dir is None:
        from jason.config import data_dir as profile_data_dir

        data_dir = profile_data_dir()
    with store.locked("refer"):
        a = store.load(approval_id, data_dir)
        try:
            i = a.item(item)
        except KeyError as exc:
            raise Refused(str(exc.args[0])) from exc
        if not i.flagged:
            raise Refused(f"{i.id} is not flagged for review: only a flagged finding is referred to the board")
        found = _board_item_for(a, i, by=by, data_dir=Path(data_dir))
        board_items.propose(Path(data_dir), [found])
        for x in a.items:
            if x.flagged and x.rule == i.rule and x.board_item != found.id:
                x.board_item = found.id
        store.save(a, data_dir)
    audit.append(data_dir, "item.referred", approval=a.id, kind=a.kind, actor=by, via=via, item=i.id, op=i.op,
                 target=i.target, label=i.label, detail=f"board item {found.id}", fingerprint=a.fingerprint)
    return a, found


def board_item_id(i: PlanItem) -> str:
    """The id of the board item for a flagged finding: the item's own, else a slug of the finding's rule."""
    import re

    return i.board_item or "flagged-" + re.sub(r"[^a-z0-9]+", "-", (i.rule or i.op).lower()).strip("-")[:60]


def _board_item_for(a: Approval, i: PlanItem, *, by: str, data_dir: Path) -> Any:
    """The board item for a flagged finding. One already on the list keeps its own title, summary, and ask (the board
    item the finding's rule row names was written by a review) and gains this plan's evidence; a new one says only
    that a finding no adopted rule answers is before the board, and carries no member's name or address."""
    from dataclasses import replace
    from datetime import date

    from jason.community.board_items import BoardItem, ItemCategory
    from jason.tasks import board_items

    finding = i.rule or i.op
    ident = board_item_id(i)
    evidence = (f"jason approvals show {a.id}", f'jason approvals exceptions --finding "{finding}"')
    current = next((b for b in board_items.load(data_dir) if b.id == ident), None)
    if current is not None:
        return replace(current, evidence=tuple(dict.fromkeys((*current.evidence, *evidence))))
    return BoardItem(
        ident, f"A finding no adopted rule answers: {finding.split(': ', 1)[-1]}",
        f"An approvals plan ({a.kind}) holds changes flagged for review because no rule the board has adopted answers "
        f"them (finding: {finding}). A director, an officer, or the manager asked that the board consider it. Until the "
        "board decides, each case is a one-off decision by a named person, recorded in the exceptions log.",
        "decide whether to adopt a written rule for this finding, or to leave each case to a one-off decision",
        ItemCategory.GOVERNANCE, authority="CIV 4350, 4355", evidence=evidence,
        history=[f"{date.today().isoformat()}: referred from {a.id} by {by}"])


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
        approved = a.approved
        refused = control_refusals(a, data_dir=data_dir) if approved else []
        if approved and not refused:
            # a first signature need not hold a required office when a second person follows; it is the last when none does
            refused = signer_refusals(a, [by], final=not needs_second(a, data_dir=data_dir), data_dir=data_dir)
        if refused:
            raise Refused("; ".join(refused))
        a.first, a.second = Signature(by, _now(), a.fingerprint, role, via), None
        if not approved:
            transition(a, S.WITHDRAWN)
            a.notes.append("nothing approved")
        else:
            every = sum(1 for i in approved if i.approvable) == len(a.approvable)
            transition(a, S.APPROVED if every else S.PARTIALLY_APPROVED)
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
        if not needs_second(a, data_dir=data_dir):
            raise Refused(f"{a.id} needs no second person")
        if a.second is not None:
            raise Refused(f"{a.id} is already confirmed by {a.second.name}")
        if a.first is not None and same_person(by, a.first.name):
            raise Refused(f"a second, distinct person confirms: {by} submitted it")
        if same_person(by, a.requested_by):
            raise Refused(f"a second, distinct person confirms: {by} asked for the plan")
        refused = signer_refusals(a, [a.first.name if a.first is not None else "", by], final=True, data_dir=data_dir)
        if refused:
            raise Refused("; ".join(refused))
        a.second = Signature(by, _now(), a.fingerprint, role, via)
        store.save(a, data_dir)
    audit.append(data_dir, "approval.confirmed", approval=a.id, kind=a.kind, actor=by, via=via, role=role,
                 fingerprint=a.fingerprint)
    for i in a.approved:
        if i.exception:                                # the exceptions log: who signed second (a later line)
            exceptions.follow_up(a.id, i, "second", second_by=by, kind=a.kind, data_dir=data_dir)
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

def _problems(a: Approval, kind: registry.ActionKind, data_dir: Path | None = None) -> list[str]:
    out = []
    if a.status not in (S.APPROVED, S.PARTIALLY_APPROVED):
        out.append(f"{a.id} is {a.status.value}: only an approved or partially approved approval is applied")
    elif a.first is None:
        out.append(f"{a.id} is not submitted")
    if a.status in (S.APPROVED, S.PARTIALLY_APPROVED) and needs_second(a, kind, data_dir=data_dir) and a.second is None:
        out.append("a second, distinct person must confirm first (jason approvals confirm ID --by NAME)")
    if a.status in (S.APPROVED, S.PARTIALLY_APPROVED):
        out += control_refusals(a, kind, data_dir=data_dir)
        signed = [s.name for s in (a.first, a.second) if s is not None]
        if signed:
            # the set is final once the second has signed, or when no second is needed; until then it is incomplete
            # and the missing second is already a problem above
            final = a.second is not None or not needs_second(a, kind, data_dir=data_dir)
            out += signer_refusals(a, signed, final=final, kind=kind, data_dir=data_dir)
            if final:                       # the pause starts at the last signature
                out += _pause_problems(a, kind, data_dir)
    try:
        read = datetime.fromisoformat(a.read_at)
    except ValueError:
        read = None
    if read is not None and datetime.now(timezone.utc) - read > timedelta(hours=kind.max_age_hours):
        out.append(f"planned at {a.read_at}, more than {kind.max_age_hours} hours ago: plan again")
    return out


def _pause_problems(a: Approval, kind: registry.ActionKind, data_dir: Path | None,
                    now: datetime | None = None) -> list[str]:
    """The pause the board adopted between the last signature and apply, while it lasts (``apply_prefs.pause_problem``)."""
    from jason.controls import apply_prefs

    prefs = prefs_for(kind, data_dir)
    if not prefs.pausing:
        return []
    why = apply_prefs.pause_problem(prefs, last_signed_at(a), now or datetime.now(timezone.utc))
    return [why] if why else []


def problems(a: Approval, data_dir: Path | None = None) -> list[str]:
    """Why ``apply`` would refuse before any live read (its status, a missing second person, its age); empty when it
    would go on to re-plan. A caller that must sign in to read live asks this first."""
    return _problems(a, registry.get(a.kind), data_dir)


def last_signed_at(a: Approval) -> datetime | None:
    """When the plan was last signed: the later of the first and the second signature (the second, when there is one);
    None for a plan nobody has signed or a time that cannot be read."""
    stamps = []
    for s in (a.first, a.second):
        if s is None:
            continue
        try:
            at = datetime.fromisoformat(s.at)
        except ValueError:
            continue
        stamps.append(at if at.tzinfo else at.replace(tzinfo=timezone.utc))
    return max(stamps) if stamps else None


def waiting_row(a: Approval, now: datetime | None = None, data_dir: Path | None = None) -> dict[str, Any] | None:
    """One plan as ``waiting_to_apply`` lists it, or None when it is not signed and waiting: status approved or partially
    approved, every signature the plan needs given (a plan still waiting for its second person waits on a signature, not
    on an apply). Fields: ``id``, ``kind``, ``title``, ``signedAt`` (the **last** signature's time, where the waiting
    clock starts), ``waitingHours``, ``stale`` (read longer ago than the kind's ``max_age_hours``, so apply plans it
    again first), ``maxAgeHours``, ``needsSecond``, ``terminalOnly`` (only a person at a terminal applies it), and
    ``applyCommand`` (the terminal command; NAME stands for the person). The apply preferences the board adopted
    (``jason.controls.apply_prefs``) add ``reminderHours`` (None: no reminder), ``reminderDue`` (the plan has waited that
    long: it only surfaces, nothing is sent), ``pausing`` and ``pauseEndsAt`` (a pause after the last signature).
    A kind this checkout no longer has is listed, not stale, with no command and the default preferences."""
    if a.status not in (S.APPROVED, S.PARTIALLY_APPROVED) or a.first is None:
        return None
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    try:
        kind: registry.ActionKind | None = registry.get(a.kind)
    except KeyError:
        kind = None
    second = needs_second(a, kind, data_dir=data_dir) if kind is not None else a.second is not None
    if second and a.second is None:
        return None
    signed = last_signed_at(a)
    hours = max(0.0, (now - signed).total_seconds() / 3600) if signed is not None else 0.0
    try:
        read = datetime.fromisoformat(a.read_at)
        read = read if read.tzinfo else read.replace(tzinfo=timezone.utc)
    except ValueError:
        read = None
    stale = bool(kind is not None and read is not None and now - read > timedelta(hours=kind.max_age_hours))
    terminal = bool(kind is not None and kind.terminal_only)
    command = (kind.cli if terminal else f"jason approvals apply {a.id} --yes --by NAME") if kind is not None else ""
    from jason.controls import apply_prefs

    prefs = prefs_for(kind, data_dir) if kind is not None else apply_prefs.ApplyPrefs(a.kind)
    ends = apply_prefs.pause_ends(signed, prefs)
    return {"id": a.id, "kind": a.kind, "title": a.title,
            "signedAt": signed.isoformat(timespec="seconds") if signed else "", "waitingHours": round(hours, 1),
            "stale": stale, "maxAgeHours": kind.max_age_hours if kind is not None else None, "needsSecond": second,
            "terminalOnly": terminal, "applyCommand": command,
            "reminderHours": prefs.reminder_hours, "reminderDue": apply_prefs.reminder_due(prefs, hours),
            "pausing": bool(ends is not None and now < ends),
            "pauseEndsAt": ends.astimezone(timezone.utc).isoformat(timespec="seconds") if ends is not None else ""}


def ago(hours: float) -> str:
    """How long, in words: "less than an hour", "5 hours", "3 days"."""
    if hours < 1:
        return "less than an hour"
    if hours < 48:
        n = int(hours)
        return f"{n} hour{'s' if n != 1 else ''}"
    return f"{int(hours // 24)} days"


def waiting_words(row: dict[str, Any]) -> str:
    """A waiting row in the console's words: "signed, waiting to be applied · 3 days", or, for a plan read longer ago
    than its kind allows, "signed 5 days ago; it will be planned again before it is applied"."""
    waited = ago(float(row["waitingHours"]))
    if row["stale"]:
        return f"signed {waited} ago; it will be planned again before it is applied"
    return f"signed, waiting to be applied · {waited}"


def waiting_to_apply(data_dir: Path | None = None, now: datetime | None = None) -> list[dict[str, Any]]:
    """The plans signed and not yet applied (docs/console/approval-clarity.md, section 4), longest waiting first, each as
    ``waiting_row`` gives it. Counts, times, and the plan's title only: never an item's contents. Reads disk only."""
    found = (waiting_row(a, now, data_dir) for a in store.load_all(data_dir))
    return sorted((r for r in found if r is not None), key=lambda r: (-r["waitingHours"], r["id"]))


def compare(a: Approval, planned: Planned) -> tuple[list[Changed], list[PlanItem]]:
    """Each approved item against the re-plan: gone, now not approvable, or its basis moved is a change. Approvable
    items the approval does not have are new."""
    now = {i.id: i for i in planned.items}
    changed = []
    for i in a.approved:
        j = now.get(i.id)
        if j is None:
            changed.append(Changed(i.id, i.op, i.label, i.basis, "", "no longer in the plan"))
        elif j.klass is not i.klass:
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
    problems = _problems(a, kind, data_dir)
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


def apply(approval_id: str, live: Live, *, by: str, via: str = "cli", data_dir: Path | None = None,
          typed_count: int | None = None) -> Applied:
    """Re-plan live; refuse and supersede when an approved item changed; else apply only the approved items. Before any live
    read it also asks the apply preferences the board adopted (``jason.controls.apply_prefs``): a pause not yet over, who
    may apply, and the typed count (``typed_count``, the number of changes the person typed) above the board's number."""
    from jason.locks import Resource, account, hold

    by = _named(by, "an apply")
    data_dir = data_dir if data_dir is not None else live.data_dir
    ident = store.resolve(approval_id, data_dir)
    with hold(Resource.STORE, f"approval-{ident}", timeout=5, purpose=f"apply {ident}"):
        a = store.load(ident, data_dir)
        kind = registry.get(a.kind)
        problems = _problems(a, kind, data_dir)
        if kind.terminal_only and not live.terminal:
            problems.append(kind.terminal_note)
        if a.status in (S.APPROVED, S.PARTIALLY_APPROVED):
            problems += apply_refusals(a, by=by, typed_count=typed_count, data_dir=data_dir, kind=kind)
        if problems:
            audit.append(data_dir, "apply.refused", approval=a.id, kind=a.kind, actor=by, via=via,
                         fingerprint=a.fingerprint, detail="; ".join(problems))
            raise Refused("; ".join(problems))
        # A service's lock is the community's account (one writer per account); any other resource, the approval.
        service = kind.resource in (Resource.PAYHOA, Resource.GOOGLE)
        with hold(kind.resource, account() if service else f"approval-{ident}", timeout=60, purpose=f"apply {ident}"):
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
    _store_new(fresh, data_dir, by=by, via=via, snapshots=planned.snapshots)
    return Applied(current, fresh, changed, new)


def _run(a: Approval, kind: registry.ActionKind, planned: Planned, new: list[PlanItem], live: Live, *, by: str,
         via: str, data_dir: Path | None) -> Applied:
    with store.locked("apply"):
        a = store.load(a.id, data_dir)
        transition(a, S.APPLYING)
        for i in a.items:
            if not i.takes_effect:
                i.result = Result.NOT_APPLIED
                i.result_detail = (f"{i.decision.value} by {i.decided_by}: {i.reason}" if i.approvable or i.exception
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
    _log_exceptions_applied(a, data_dir)
    return Applied(a, None, [], new)


def _log_exceptions_applied(a: Approval, data_dir: Path | None) -> None:
    """The exceptions log hears whether each approved exception was written (a later line; none is edited). A log that
    cannot be written does not undo the apply: the approval says so."""
    try:
        for i in a.approved:
            if i.exception:
                exceptions.follow_up(a.id, i, "applied", applied=i.result is Result.APPLIED,
                                     second_by=a.second.name if a.second else "", kind=a.kind, data_dir=data_dir)
    except OSError as exc:
        with store.locked("apply"):
            a.notes.append(f"the exceptions log could not be written: {type(exc).__name__}: {exc}")
            store.save(a, data_dir)


__all__ = ["Applied", "Changed", "Live", "Planned", "Recheck", "Recorder", "Refused", "ago", "apply", "apply_refusals",
           "board_item_id", "check", "compare", "confirm", "counts", "decide", "decline", "last_signed_at", "needs_second",
           "plan", "prefs_for", "problems", "reason_in_words", "refer", "submit", "waiting_row", "waiting_to_apply",
           "waiting_words", "withdraw"]
