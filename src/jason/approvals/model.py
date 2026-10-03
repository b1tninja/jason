"""The approval records: pure data, no disk and no PayHOA.

An ``Approval`` is one plan of writes outside jason, made from a live read, with every item a person reviews. Each
``PlanItem`` is one change (before and after, or a tag added or removed), why, its rule and evidence, and its class:
approvable, or never approvable (held for the board with its board item, for a person, to confirm with the owner, or
informational). A person decides approvable items one by one (``Decision``); the decisions are submitted under a
``Signature``, and a second, distinct person signs too when the kind or a high-stakes item needs one. ``apply`` reads
live again and refuses when the basis of an approved item moved (``Result.CHANGED``).

The states and their transitions are ``ApprovalStatus`` and ``TRANSITIONS``; ``transition`` is the only way a status
changes. The design is docs/console/approval-workflow.md.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


class ApprovalStatus(Enum):
    PLANNED = "planned"                        # jason made the plan; nobody has decided an item
    IN_REVIEW = "in_review"                    # at least one item decided, not yet submitted
    APPROVED = "approved"                      # submitted: every approvable item approved
    PARTIALLY_APPROVED = "partially_approved"  # submitted: some approved, the rest rejected or held
    APPLYING = "applying"                      # the re-plan matched; writes under way
    APPLIED = "applied"                        # every approved item applied
    FAILED = "failed"                          # one or more approved items failed; waits for a person
    SUPERSEDED = "superseded"                  # the live state changed, or a newer plan replaced it
    WITHDRAWN = "withdrawn"                    # withdrawn before apply, or nothing was approved


S = ApprovalStatus
TERMINAL = frozenset({S.APPLIED, S.FAILED, S.SUPERSEDED, S.WITHDRAWN})
OPEN = frozenset({S.PLANNED, S.IN_REVIEW, S.APPROVED, S.PARTIALLY_APPROVED})

# Every allowed move (docs/console/approval-workflow.md, the transition table). Nothing leaves a terminal state.
TRANSITIONS: dict[ApprovalStatus, frozenset[ApprovalStatus]] = {
    S.PLANNED: frozenset({S.IN_REVIEW, S.SUPERSEDED, S.WITHDRAWN}),
    S.IN_REVIEW: frozenset({S.IN_REVIEW, S.APPROVED, S.PARTIALLY_APPROVED, S.SUPERSEDED, S.WITHDRAWN}),
    S.APPROVED: frozenset({S.APPLYING, S.IN_REVIEW, S.SUPERSEDED, S.WITHDRAWN}),
    S.PARTIALLY_APPROVED: frozenset({S.APPLYING, S.IN_REVIEW, S.SUPERSEDED, S.WITHDRAWN}),
    S.APPLYING: frozenset({S.APPLIED, S.FAILED, S.SUPERSEDED}),
    S.APPLIED: frozenset(),
    S.FAILED: frozenset(),
    S.SUPERSEDED: frozenset(),
    S.WITHDRAWN: frozenset(),
}


class TransitionError(ValueError):
    """A status change the table does not allow."""


class ItemClass(Enum):
    APPROVABLE = "approvable"
    HELD_FOR_BOARD = "held_for_board"            # a question of policy (Outcome.BOARD): never approvable
    FOR_A_PERSON = "for_a_person"                # a person does it in the system itself (Outcome.PERSON)
    CONFIRM_WITH_OWNER = "confirm_with_owner"    # ask the owner first (Outcome.CONFIRM); a message is its own kind
    INFORMATIONAL = "informational"              # what follows: a request that stays open, and why


class Decision(Enum):
    UNDECIDED = "undecided"
    APPROVED = "approved"
    REJECTED = "rejected"                      # a person leaves it out; a reason is required
    HELD = "held"                              # a person holds it (for the board, or until something else); a reason


class Result(Enum):
    PENDING = "pending"
    APPLIED = "applied"
    NOT_APPLIED = "not_applied"                # rejected, held, never approvable, or not attempted
    CHANGED = "changed"                        # refused at apply: its basis moved since review
    BLOCKED = "blocked"                        # something it waits on was not applied
    FAILED = "failed"
    UNCERTAIN = "uncertain"                    # the request went out and no answer came back: verify first


class ChangeOp(Enum):
    ADD = "add"
    REMOVE = "remove"
    SET = "set"


@dataclass(frozen=True)
class Change:
    """What the item changes: a value added to or removed from a field, or a field set from one value to another.
    ``before`` and ``after`` are the field as read and as it will be."""
    op: ChangeOp
    field: str                                 # "member tags", "unit tags", "request status"
    value: str = ""
    before: str = ""
    after: str = ""

    def text(self) -> str:
        if self.op is ChangeOp.SET:
            return f"{self.field}: {self.before or '(none)'} -> {self.after}"
        return f"{'+' if self.op is ChangeOp.ADD else '-'} {self.value} ({self.field})"


@dataclass(frozen=True)
class Evidence:
    label: str                                 # "PayHOA request 1234", "Civil Code 4040(a)(2)"
    address: str = ""                          # a citation jason cite resolves, a command, or a record's address


@dataclass
class PlanItem:
    id: str                                    # stable: item_id(kind, op, target, value)
    op: str                                    # the kind's verb: "member tag +", "complete request"
    target: str                                # "member:123", "unit:45", "submission:678"
    label: str                                 # who or what, for the reader
    value: str                                 # the tag, the status, the text
    why: str                                   # the planner's reason
    group: str = ""                            # the items read together: one owner
    change: Change | None = None
    rule: str = ""                             # the rule that calls for it, as a citation or a rule row's address
    evidence: tuple[Evidence, ...] = ()
    basis: str = ""                            # sha256 of the live state this item relies on
    klass: ItemClass = ItemClass.APPROVABLE
    board_item: str = ""                       # held for the board: the board item it waits on
    depends_on: tuple[str, ...] = ()           # item ids that must apply first
    high_stakes: bool = False                  # a second, distinct person must sign before it applies
    cost_cents: int = 0                        # what applying it charges the association (integer cents)
    decision: Decision = Decision.UNDECIDED
    decided_by: str = ""
    decided_at: str = ""
    reason: str = ""
    result: Result = Result.PENDING
    result_detail: str = ""

    @property
    def approvable(self) -> bool:
        return self.klass is ItemClass.APPROVABLE


@dataclass(frozen=True)
class DecisionRecord:
    """One decision as made: who, when, which items, what, why, and the plan fingerprint it was made on."""
    by: str
    at: str
    items: tuple[str, ...]
    decision: Decision
    reason: str = ""
    fingerprint: str = ""
    via: str = "cli"


@dataclass(frozen=True)
class Signature:
    name: str                                  # the named person
    at: str                                    # UTC, ISO 8601, seconds
    fingerprint: str                           # the plan fingerprint signed
    role: str = "manager"
    via: str = "cli"


@dataclass
class Approval:
    id: str                                    # "apr-" + UTC stamp + 4 hex: apr-20990101T120000-1a2b
    kind: str                                  # an ActionKind key
    title: str
    items: list[PlanItem]
    fingerprint: str                           # plan_fingerprint(kind, scope, items)
    read_at: str                               # when the live state was read
    requested_by: str
    requested_at: str
    requested_via: str = "cli"
    scope: dict[str, Any] = field(default_factory=dict)
    profile: str = ""
    status: ApprovalStatus = ApprovalStatus.PLANNED
    evidence: tuple[Evidence, ...] = ()
    decisions: list[DecisionRecord] = field(default_factory=list)
    first: Signature | None = None             # who submitted the decisions
    second: Signature | None = None            # the second person, where one is needed
    cost_cents: int | None = None              # the plan's cost; None when the kind has none
    clock: dict[str, Any] | None = None        # the legal clock it serves: {"what", "due", "daysLeft"}
    summary: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    supersedes: str = ""
    superseded_by: str = ""
    notes: list[str] = field(default_factory=list)

    def item(self, ident: str) -> PlanItem:
        """An item by its id or a unique prefix of at least six characters, as git names a commit."""
        found = [i for i in self.items if i.id == ident]
        if not found and len(ident) >= 6:
            found = [i for i in self.items if i.id.startswith(ident)]
        if len(found) != 1:
            raise KeyError(f"{'no' if not found else 'more than one'} item {ident} in {self.id}")
        return found[0]

    @property
    def approvable(self) -> list[PlanItem]:
        return [i for i in self.items if i.approvable]

    @property
    def approved(self) -> list[PlanItem]:
        return [i for i in self.items if i.approvable and i.decision is Decision.APPROVED]


# --- transitions --------------------------------------------------------------------------------------------------------

def can_transition(src: ApprovalStatus, dst: ApprovalStatus) -> bool:
    return dst in TRANSITIONS[src]


def transition(approval: Approval, dst: ApprovalStatus) -> Approval:
    """Move ``approval`` to ``dst``, or raise ``TransitionError`` when the table does not allow it."""
    if not can_transition(approval.status, dst):
        raise TransitionError(f"{approval.id} is {approval.status.value}: it cannot become {dst.value}")
    approval.status = dst
    return approval


def same_person(a: str, b: str) -> bool:
    """Names compared trimmed and case folded, as ``intake.confirm`` compares them."""
    return bool(a) and bool(b) and a.strip().casefold() == b.strip().casefold()


# --- fingerprints -------------------------------------------------------------------------------------------------------

def canonical(value: Any) -> str:
    """The canonical JSON: sorted keys, no spaces, so a digest is the same on any machine."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def item_id(kind: str, op: str, target: str, value: str) -> str:
    """The same id for the same change on every re-plan."""
    return hashlib.sha256(f"{kind}|{op}|{target}|{value}".encode("utf-8")).hexdigest()[:16]


def plan_fingerprint(kind: str, scope: dict[str, Any], items: Iterable[PlanItem]) -> str:
    """sha256 over the kind, the scope, and each approvable item's id and basis (the live state it relies on)."""
    return digest({"kind": kind, "scope": scope,
                   "items": sorted([i.id, i.basis] for i in items if i.klass is ItemClass.APPROVABLE)})


def basis_fingerprint(items: Iterable[PlanItem]) -> str:
    """sha256 over the given items' id and basis: what an apply compares for the approved items."""
    return digest(sorted([i.id, i.basis] for i in items))


def short(fingerprint: str) -> str:
    return fingerprint[:12]


# --- JSON ---------------------------------------------------------------------------------------------------------------

def _evidence(e: Evidence) -> dict[str, Any]:
    return {"label": e.label, "address": e.address}


def _signature(s: Signature | None) -> dict[str, Any] | None:
    return None if s is None else {"name": s.name, "at": s.at, "fingerprint": s.fingerprint, "role": s.role,
                                   "via": s.via}


def item_dict(i: PlanItem) -> dict[str, Any]:
    change = None if i.change is None else {"op": i.change.op.value, "field": i.change.field, "value": i.change.value,
                                            "before": i.change.before, "after": i.change.after, "text": i.change.text()}
    return {"id": i.id, "op": i.op, "target": i.target, "label": i.label, "value": i.value, "why": i.why,
            "group": i.group, "change": change, "rule": i.rule, "evidence": [_evidence(e) for e in i.evidence],
            "basis": i.basis, "class": i.klass.value, "boardItem": i.board_item, "dependsOn": list(i.depends_on),
            "highStakes": i.high_stakes, "costCents": i.cost_cents, "decision": i.decision.value,
            "decidedBy": i.decided_by, "decidedAt": i.decided_at, "reason": i.reason, "result": i.result.value,
            "resultDetail": i.result_detail}


def decision_dict(d: DecisionRecord) -> dict[str, Any]:
    return {"by": d.by, "at": d.at, "items": list(d.items), "decision": d.decision.value, "reason": d.reason,
            "fingerprint": d.fingerprint, "via": d.via}


def to_dict(a: Approval) -> dict[str, Any]:
    return {"id": a.id, "kind": a.kind, "title": a.title, "status": a.status.value, "scope": a.scope,
            "profile": a.profile, "fingerprint": a.fingerprint, "readAt": a.read_at, "requestedBy": a.requested_by,
            "requestedAt": a.requested_at, "requestedVia": a.requested_via,
            "evidence": [_evidence(e) for e in a.evidence], "items": [item_dict(i) for i in a.items],
            "decisions": [decision_dict(d) for d in a.decisions], "first": _signature(a.first),
            "second": _signature(a.second), "costCents": a.cost_cents, "clock": a.clock, "summary": a.summary,
            "result": a.result, "supersedes": a.supersedes, "supersededBy": a.superseded_by, "notes": list(a.notes)}


def _evidence_from(rows: Any) -> tuple[Evidence, ...]:
    return tuple(Evidence(r.get("label", ""), r.get("address", "")) for r in rows or ())


def _signature_from(row: Any) -> Signature | None:
    return None if not row else Signature(row["name"], row["at"], row.get("fingerprint", ""), row.get("role", "manager"),
                                          row.get("via", "cli"))


def item_from(row: dict[str, Any]) -> PlanItem:
    ch = row.get("change")
    change = None if not ch else Change(ChangeOp(ch["op"]), ch.get("field", ""), ch.get("value", ""),
                                        ch.get("before", ""), ch.get("after", ""))
    return PlanItem(row["id"], row["op"], row["target"], row.get("label", ""), row.get("value", ""), row.get("why", ""),
                    group=row.get("group", ""), change=change, rule=row.get("rule", ""),
                    evidence=_evidence_from(row.get("evidence")), basis=row.get("basis", ""),
                    klass=ItemClass(row.get("class", "approvable")), board_item=row.get("boardItem", ""),
                    depends_on=tuple(row.get("dependsOn") or ()), high_stakes=bool(row.get("highStakes")),
                    cost_cents=int(row.get("costCents") or 0), decision=Decision(row.get("decision", "undecided")),
                    decided_by=row.get("decidedBy", ""), decided_at=row.get("decidedAt", ""),
                    reason=row.get("reason", ""), result=Result(row.get("result", "pending")),
                    result_detail=row.get("resultDetail", ""))


def from_dict(row: dict[str, Any]) -> Approval:
    return Approval(
        row["id"], row["kind"], row.get("title", ""), [item_from(i) for i in row.get("items") or []],
        row.get("fingerprint", ""), row.get("readAt", ""), row.get("requestedBy", ""), row.get("requestedAt", ""),
        requested_via=row.get("requestedVia", "cli"), scope=dict(row.get("scope") or {}), profile=row.get("profile", ""),
        status=ApprovalStatus(row.get("status", "planned")), evidence=_evidence_from(row.get("evidence")),
        decisions=[DecisionRecord(d["by"], d["at"], tuple(d.get("items") or ()), Decision(d["decision"]),
                                  d.get("reason", ""), d.get("fingerprint", ""), d.get("via", "cli"))
                   for d in row.get("decisions") or []],
        first=_signature_from(row.get("first")), second=_signature_from(row.get("second")),
        cost_cents=row.get("costCents"), clock=row.get("clock"), summary=dict(row.get("summary") or {}),
        result=dict(row.get("result") or {}), supersedes=row.get("supersedes", ""),
        superseded_by=row.get("supersededBy", ""), notes=list(row.get("notes") or ()))


__all__ = ["Approval", "ApprovalStatus", "Change", "ChangeOp", "Decision", "DecisionRecord", "Evidence", "ItemClass",
           "OPEN", "PlanItem", "Result", "Signature", "TERMINAL", "TRANSITIONS", "TransitionError", "basis_fingerprint",
           "can_transition", "canonical", "digest", "from_dict", "item_dict", "item_from", "item_id", "plan_fingerprint",
           "same_person", "short", "to_dict", "transition"]
