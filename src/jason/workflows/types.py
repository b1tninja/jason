"""The types of a durable workflow: a definition (a row, like a rule row), a run's events, and the view a fold gives.

Enums, not strings: JSON stores the word and the loader turns it into the symbol before a task sees it. Nothing here
names an association: a definition names its subject, roles, and statutes as data (docs/workflows-engine.md, section 2).

``ClockBasis`` is defined here with all five bases. ``jason.tasks.followups.Basis`` has four (no ``counterparty`` yet);
``followup_basis`` maps one to the other and answers ``None`` for the one it lacks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Callable, Mapping


class StepKind(Enum):
    CHECK = "check"
    JOB = "job"
    PLAN = "plan"
    PERSON = "person"
    DECISION = "decision"
    WAIT = "wait"
    BRANCH = "branch"


class StepState(Enum):
    NOT_STARTED = "not started"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    NEEDS_PERSON = "needs a person"
    DONE = "done"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class RunState(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    WAITING = "waiting"
    DONE = "done"
    CANCELLED = "cancelled"
    FAILED = "failed"


class EventKind(Enum):
    OPENED = "opened"
    STEP_READY = "step-ready"
    CHECK_RAN = "check-ran"
    JOB_QUEUED = "job-queued"
    JOB_FINISHED = "job-finished"
    PLAN_MADE = "plan-made"
    APPROVAL_DECIDED = "approval-decided"
    APPLIED = "applied"
    ATTESTED = "attested"
    DECIDED = "decided"
    WAITED = "waited"
    ARRIVED = "arrived"
    SKIPPED = "skipped"
    PAUSED = "paused"
    RESUMED = "resumed"
    REOPENED = "reopened"
    CHANGED = "changed"
    NOTE = "note"
    CANCELLED = "cancelled"
    SPAWNED = "spawned"        # a step started a child run (the engine doc's "child run"; the design page's list lacks it)


class ClockBasis(Enum):
    LAW = "law"
    DOCUMENTS = "documents"
    COUNTERPARTY = "counterparty"
    PROPOSED_POLICY = "proposed policy"
    PERSON = "person"


def followup_basis(basis: ClockBasis):
    """The ``jason.tasks.followups.Basis`` with the same word, or ``None`` (``counterparty`` has no member there yet).
    Imported when asked, so importing the engine loads nothing of the follow-ups."""
    from jason.tasks.followups import Basis

    try:
        return Basis(basis.value)
    except ValueError:
        return None


class Role(Enum):
    """Who may act on a step. The offices are the holders in ``jason.web.access.SEE_RULES`` (a test keeps the two in
    step); ``jason`` and ``scheduler`` are the engine's own names; ``anyone`` is any signed-in person."""

    MANAGER = "manager"
    PRESIDENT = "president"
    VICE_PRESIDENT = "vice president"
    SECRETARY = "secretary"
    TREASURER = "treasurer"
    DIRECTOR = "director"
    ADMINISTRATOR = "administrator"
    JASON = "jason"
    SCHEDULER = "scheduler"
    ANYONE = "anyone"

    @classmethod
    def parse(cls, value: "Role | str") -> "Role | None":
        if isinstance(value, Role):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            return None


OFFICES = frozenset(r for r in Role if r not in (Role.JASON, Role.SCHEDULER, Role.ANYONE, Role.ADMINISTRATOR))
SYSTEM_NAMES = frozenset({"jason", "scheduler"})


def is_system(by: str) -> bool:
    """``jason`` and ``scheduler`` are the engine's own names; a person's act is never recorded under them."""
    return by.strip().lower() in SYSTEM_NAMES


class Repeat(Enum):
    ONCE = "once"
    PER_ITEM = "per item"
    PER_PERIOD = "per period"


class Elapsed(Enum):
    """What a ``wait`` does when its clock passes. ``OVERDUE`` keeps waiting and says so (the arrival ends it);
    ``ENDS`` lets the date end the wait."""

    OVERDUE = "overdue"
    ENDS = "ends"


class OnWithdrawn(Enum):
    """What a ``plan`` step becomes when its approval is withdrawn: the definition says."""

    FAIL = "fail"
    SKIP = "skip"


class LinkKind(Enum):
    APPROVAL = "approval"
    JOB = "job"
    FOLLOWUP = "followup"
    BOARD_ITEM = "board-item"
    TASK = "task"
    DOC = "doc"
    CAMPAIGN = "campaign"
    RUN = "run"


FINAL_OUTCOMES = frozenset({"adopted", "approved", "denied", "rejected", "withdrawn"})
"""A ``decision`` step is done when the board's decision has one of these outcomes; "tabled" or "pending" is recorded
and the step stays open."""


@dataclass(frozen=True)
class CheckResult:
    """What a ``check`` returns. ``evidence`` entries are ``address@hash`` strings; ``choice`` is a ``branch`` check's
    answer. A check that cannot read returns ``ok=False`` with the reason, never ``ok``."""

    ok: bool
    evidence: tuple[str, ...] = ()
    message: str = ""
    choice: str = ""


@dataclass(frozen=True)
class SkipRule:
    """Who may skip a step and with what reason. A step with no rule cannot be skipped."""

    roles: tuple[Role, ...] = ()           # empty: the step's own role
    reason_required: bool = True


@dataclass(frozen=True)
class DateSlot:
    """A date a run is started with, and the checks on it."""

    name: str
    label: str = ""
    required: bool = True
    after: str = ""                        # another slot's name: this date may not come before it


@dataclass(frozen=True)
class ClockDef:
    """When something is due and on what basis: ``slot`` is a date slot's name, ``days`` an offset from it."""

    basis: ClockBasis
    slot: str = ""
    days: int = 0
    cite: str = ""                         # a law clock cites its section; a documents clock its document
    label: str = ""


@dataclass(frozen=True)
class Choice:
    """A ``branch`` path: the step ids that belong to it alone."""

    key: str
    steps: tuple[str, ...] = ()


@dataclass(frozen=True)
class Phase:
    key: str
    title: str
    steps: tuple[str, ...] = ()


@dataclass(frozen=True)
class StepDef:
    id: str                                # "example-cycle.2": stable; a step is never renumbered, only added to
    title: str
    kind: StepKind
    role: Role = Role.MANAGER              # who may act; for a decision, who records it
    needs: tuple[str, ...] = ()
    why: str = ""
    command: str = ""                      # the terminal command: shown and copied, never run by the engine
    check: Callable[..., Any] | None = None
    plan_kind: str = ""
    job: str = ""
    evidence: tuple[str, ...] = ()         # store addresses a done step must still match
    clock: ClockDef | None = None
    repeat: Repeat = Repeat.ONCE
    skip: SkipRule | None = None
    group: str = ""
    spawns: str = ""
    sop: str = ""                          # "procedure-key#4": the Procedure step it was built from (1-based)
    record: str = ""                       # what a person's attestation must point to; empty: no record needed
    legal: bool = False                    # also true for any step with a law clock; a legal step cannot be skipped
    elapsed: Elapsed = Elapsed.OVERDUE
    on_withdrawn: OnWithdrawn = OnWithdrawn.FAIL
    choices: tuple[Choice, ...] = ()

    @property
    def is_legal(self) -> bool:
        return self.legal or (self.clock is not None and self.clock.basis is ClockBasis.LAW)


@dataclass(frozen=True)
class Workflow:
    key: str
    title: str
    family: str
    subject: str                           # subject kind: "campaign", "unit", "meeting", "period"
    steps: tuple[StepDef, ...]
    dates: tuple[DateSlot, ...] = ()
    phases: tuple[Phase, ...] = ()
    procedure: str = ""
    clocks: tuple[ClockDef, ...] = ()      # deadlines on the whole run

    def step(self, step_id: str) -> StepDef | None:
        return next((s for s in self.steps if s.id == step_id), None)

    def check_dates(self, dates: Mapping[str, str]) -> list[str]:
        """The problems with a run's start dates: a missing required one, a malformed one, one out of order, or one the
        definition has no slot for."""
        out: list[str] = []
        names = {d.name for d in self.dates}
        parsed: dict[str, date] = {}
        for slot in self.dates:
            raw = str(dates.get(slot.name, "") or "")
            if not raw:
                if slot.required:
                    out.append(f"date {slot.name} is required")
                continue
            try:
                parsed[slot.name] = date.fromisoformat(raw)
            except ValueError:
                out.append(f"date {slot.name} is not YYYY-MM-DD: {raw}")
        for slot in self.dates:
            if slot.after and slot.name in parsed and slot.after in parsed and parsed[slot.name] < parsed[slot.after]:
                out.append(f"date {slot.name} ({parsed[slot.name]}) comes before {slot.after} ({parsed[slot.after]})")
        out += [f"no date slot {k}" for k in dates if k not in names]
        return out

    def has_legal_clock(self) -> bool:
        return any(c.basis is ClockBasis.LAW for c in self.clocks) or any(s.is_legal for s in self.steps)


# --- events ---------------------------------------------------------------------------------------------------------

_KEYS = ("n", "kind", "step", "by", "at", "detail", "prev")


@dataclass(frozen=True)
class Event:
    """One line of a run: ``{n, kind, step, by, at, detail, prev}``. ``detail`` holds addresses and counts, never an
    owner's contact details or an answer."""

    n: int
    kind: EventKind
    by: str = ""
    at: str = ""
    step: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    prev: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"n": self.n, "kind": self.kind.value}
        if self.step:
            out["step"] = self.step
        out.update({"by": self.by, "at": self.at, "detail": dict(self.detail), "prev": self.prev})
        return out

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "Event":
        try:
            kind = EventKind(row["kind"])
            n = int(row["n"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"not an event: {exc}") from exc
        detail = row.get("detail") or {}
        if not isinstance(detail, dict):
            raise ValueError("an event's detail is an object")
        return cls(n=n, kind=kind, by=str(row.get("by", "")), at=str(row.get("at", "")),
                   step=str(row.get("step", "")), detail=detail, prev=str(row.get("prev", "")))


# --- the view a fold gives ------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Link:
    kind: str
    address: str
    step: str = ""
    label: str = ""


@dataclass(frozen=True)
class ClockView:
    key: str                               # a step id, or "run.<index>" for a clock on the whole
    basis: ClockBasis
    due: str                               # YYYY-MM-DD, "" when its date slot has no date
    label: str = ""
    cite: str = ""
    status: str = ""                       # not running, upcoming, due, overdue, satisfied, undated
    days: int | None = None                # days from today to due; negative when past
    step: str = ""


@dataclass(frozen=True)
class StepView:
    id: str
    title: str
    kind: StepKind
    role: Role
    state: StepState
    reason: str = ""                       # why it is waiting, blocked, failed, or skipped
    by: str = ""
    at: str = ""
    record: str = ""
    blocked_by: tuple[str, ...] = ()
    changed: tuple[Mapping[str, str], ...] = ()    # "changed since": address, was, now
    items: tuple[tuple[str, StepState], ...] = ()
    detail: Mapping[str, Any] = field(default_factory=dict)
    evidence: tuple[str, ...] = ()         # address@hash, the baseline a resume compares with
    choice: str = ""


@dataclass(frozen=True)
class RunView:
    id: str
    definition: str
    subject: str
    label: str
    owner: str
    opened_at: str
    state: RunState
    steps: tuple[StepView, ...]
    current: str
    clocks: tuple[ClockView, ...]
    links: tuple[Link, ...]
    dates: Mapping[str, str]
    n: int
    updated: str
    parent: str = ""
    paused_reason: str = ""
    cancelled_reason: str = ""
    orphans: tuple[str, ...] = ()          # step ids in events that the definition no longer has
    children: tuple[str, ...] = ()         # child run ids, in the order spawned
    past_law: tuple[str, ...] = ()         # keys of law clocks that are past; each opens a follow-up (a person's act)
    items: tuple[str, ...] = ()

    def step(self, step_id: str) -> StepView | None:
        return next((s for s in self.steps if s.id == step_id), None)

    def state_of(self, step_id: str) -> StepState | None:
        s = self.step(step_id)
        return s.state if s else None


# --- the gates a caller may add to a step ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StepAsk:
    """What a gate is asked before a person's attestation or skip is recorded: the run, the step, the act, who, the offices
    that person holds, who made the first of two (when a second person is pending), and the words the act and the run
    carry (a record, the subject, the records of the done steps), so a gate can look for a citation. Plain data."""

    data_dir: Any
    run_id: str
    workflow: str
    family: str
    step: str
    role: str
    act: str                                # "attest" or "skip"
    by: str
    roles: tuple[str, ...] = ()
    first_by: str = ""
    texts: tuple[str, ...] = ()
    today: date | None = None


@dataclass(frozen=True)
class GateVerdict:
    """A gate's answer: the reasons the act is refused (each a sentence), and whether a second, different person must
    confirm (so this act is the first of two, or the confirmation)."""

    refusals: tuple[str, ...] = ()
    second: bool = False


Gates = Callable[[StepAsk], GateVerdict]
"""A gate: ``gates(ask) -> GateVerdict``. The engine knows no control; ``jason.controls.effective.workflow_gate`` is the one
it is given by default, loaded only when an act is made."""


# --- helpers --------------------------------------------------------------------------------------------------------

_SOP = re.compile(r"^(?P<key>[^#\s]+)#(?P<index>\d+)$")


def parse_sop(address: str) -> tuple[str, int] | None:
    """``"procedure-key#4"`` as (key, 4); the index counts from 1, as ``jason sop`` numbers them."""
    m = _SOP.match(address.strip())
    return (m.group("key"), int(m.group("index"))) if m else None


class WorkflowError(Exception):
    """Base of what the engine refuses."""


class StepRefused(WorkflowError):
    """A step-kind contract refused the act, with the reason."""


class RunChanged(WorkflowError):
    """An append whose expected ``n`` is not the last plus one: someone else appended first."""

    def __init__(self, message: str, *, expected: int = 0, actual: int = 0):
        super().__init__(message)
        self.expected = expected
        self.actual = actual


class InvalidWorkflow(WorkflowError):
    def __init__(self, problems: list["Problem"]):
        self.problems = problems
        super().__init__("; ".join(str(p) for p in problems))


@dataclass(frozen=True)
class Problem:
    row: str                               # the step id or definition key the problem is about
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.row}: {self.message}"
