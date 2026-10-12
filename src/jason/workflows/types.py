"""The types of a durable workflow: a definition (a row, like a rule row), a run's events, and the view a fold gives.

Enums, not strings: JSON stores the word and the loader turns it into the symbol before a task sees it. Nothing here
names an association: a definition names its subject, roles, and statutes as data (docs/workflows-engine.md, section 2).

``ClockBasis`` is defined here with all six bases. ``jason.tasks.followups.Basis`` has four (no ``counterparty`` or
``provider`` yet); ``followup_basis`` maps one to the other and answers ``None`` for one it lacks.
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
    NOT_APPLICABLE = "not-applicable"   # a person recorded a step as not applicable, with a reason and a record (not a skip)
    DATE_SET = "date-set"      # a person set (or corrected) a date slot after the run started, with a record


class ClockBasis(Enum):
    LAW = "law"
    DOCUMENTS = "documents"
    COUNTERPARTY = "counterparty"
    PROVIDER = "provider"                  # a date a service provider stated
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
    step); ``jason`` and ``scheduler`` are the engine's own names; ``anyone`` is any signed-in person. ``administrator``,
    ``developer`` and ``reviewer`` are not offices: a roster names who holds them (the board's roster names none of the
    last two)."""

    MANAGER = "manager"
    PRESIDENT = "president"
    VICE_PRESIDENT = "vice president"
    SECRETARY = "secretary"
    TREASURER = "treasurer"
    DIRECTOR = "director"
    ADMINISTRATOR = "administrator"
    DEVELOPER = "developer"                # the subdivider's side of a turnover or a delivery
    REVIEWER = "reviewer"                  # a person who checks another's work (a second reader, counsel's review)
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


def role_words(role: "Role | str") -> str:
    """A role as a sentence names it: "the manager" for an office, but "jason", "scheduler" and "anyone" bare (the engine's own names
    and "any signed-in person" take no article: "waiting on jason", never "the jason")."""
    word = role.value if isinstance(role, Role) else str(role)
    return word if word in ("jason", "scheduler", "anyone") else f"the {word}"


OFFICES = frozenset(r for r in Role if r not in (Role.JASON, Role.SCHEDULER, Role.ANYONE, Role.ADMINISTRATOR, Role.DEVELOPER,
                                                 Role.REVIEWER))
SYSTEM_NAMES = frozenset({"jason", "scheduler"})


def is_system(by: str) -> bool:
    """``jason`` and ``scheduler`` are the engine's own names; a person's act is never recorded under them."""
    return by.strip().lower() in SYSTEM_NAMES


class Visibility(Enum):
    """Who the Work screens show a definition and its runs to. ``BOARD``: every office that opens P2. ``ADMIN``: an
    administrator only (the definition is not listed, read, or started for anyone else). ``HELD``: the run concerns a
    member's discipline, a parcel and a balance, or restricted records (CIV 4935(e): the open record names the matter
    generally), so outside the private view a run shows only its ``held_title`` and its state."""

    BOARD = "board"
    ADMIN = "admin"
    HELD = "held"


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
class NotApplicable:
    """The outcome a step may declare when it does not apply, recorded by a person with a reason and a record. It is not a
    skip: a legal step may carry it (it has no skip rule), and a clock on the step reads "not applicable, recorded" rather
    than being dropped. ``roles`` empty: the step's own roles."""

    roles: tuple[Role, ...] = ()
    reason_required: bool = True
    record_required: bool = True


class DateTiming(Enum):
    """A rule on a date set after the start, declared by its slot: ``ANY`` (no rule), ``PAST`` (a day that has come: today
    or earlier, such as a postmark or a recording day), or ``FUTURE`` (today or later, such as a scheduled day)."""

    ANY = "any"
    PAST = "past"
    FUTURE = "future"


@dataclass(frozen=True)
class DateSlot:
    """A date a run is started with, and the checks on it. A slot that is ``late`` is known only after the start (a
    recording day, a postmark): it is not asked at the start and a person sets it with ``date-set``. A slot that is not
    ``required`` may also be set later."""

    name: str
    label: str = ""
    required: bool = True
    after: str = ""                        # another slot's name: this date may not come before it
    late: bool = False
    timing: DateTiming = DateTiming.ANY    # a past or future rule for a date set after the start
    roles: tuple[Role, ...] = ()           # who may set it after the start; empty: any named person

    @property
    def settable(self) -> bool:
        """Whether a date-set act may give this slot a date after the start."""
        return self.late or not self.required


@dataclass(frozen=True)
class ClockDef:
    """When something is due and on what basis: ``slot`` is a date slot's name, ``days`` an offset from it.

    ``business_days`` counts the offset in business days (Monday to Friday, less the holidays the world supplies: the fold takes
    them as an argument, and an empty calendar means weekends only). ``per_item`` gives a step that repeats over items one clock
    for each item, read from the item's own dates (see ``StepDef.item_set``) before the run's."""

    basis: ClockBasis
    slot: str = ""
    days: int = 0
    cite: str = ""                         # a law clock cites its section; a documents clock its document
    label: str = ""
    business_days: bool = False
    per_item: bool = False


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


# --- the guidance record a person step may carry (docs/workflows/person-steps.md, section 4) -----------------------------

@dataclass(frozen=True)
class LookAt:
    """One thing to look at before acting: a label and the name of a registered guide read (``jason.workflows.guide_reads``)
    that counts it. ``args`` are opaque words the read may take."""

    label: str
    read: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class Check:
    """One line of the checklist: one thing to look at or do. A ``required`` item is ticked before the step is marked done."""

    text: str
    required: bool = False


@dataclass(frozen=True)
class Cmd:
    """One command, shown and copied and never run by a page. ``NAME``, ``KEY``, ``RUN`` and ``ID`` stand for what the page or
    the person fills in; ``terminal_only`` says the command is applied only at a terminal (``note`` says why)."""

    text: str
    note: str = ""
    terminal_only: bool = False


@dataclass(frozen=True)
class Cite:
    """A provision the step rests on: a shelf key (``CIV 9999(a)``) or a document key with a section (``key#section``). The panel
    recites its words, then the ``reading`` (jason's, labeled). No reading is allowed: the words alone are then shown."""

    key: str
    reading: str = ""


@dataclass(frozen=True)
class Guides:
    """The words and the evidence (section 4.1). Every field has a derivation from what the step already holds (see
    ``jason.workflows.guide``), so a step with none is never empty."""

    instruction: str = ""
    why: str = ""
    look_at: tuple[LookAt, ...] = ()
    checklist: tuple[Check, ...] = ()
    commands: tuple[Cmd, ...] = ()
    lessons: tuple[str, ...] = ()
    cites: tuple[Cite, ...] = ()
    done_when: str = ""
    blocked: str = ""
    not_applicable: str = ""
    ask: tuple["Role", ...] = ()


@dataclass(frozen=True)
class Enables:
    """Can this person do it now (section 4.2). ``second_person`` and ``terminal`` are ``None`` to derive them."""

    in_hand: tuple[str, ...] = ()
    integrations: tuple[str, ...] = ()
    access_note: str = ""
    second_person: bool | None = None
    terminal: bool | None = None


@dataclass(frozen=True)
class Reminds:
    """When, to whom, how loud (section 4.3). Each ``None`` is the proposed default (``jason.workflows.nudge.Prefs``); a number
    here is the definition's own and the board may adopt another. A step's due date is its ``clock``, never a field here."""

    lead_days: int | None = None
    after_hours: int | None = None
    escalate_to: "Role | None" = None
    escalate_after_hours: int | None = None
    snoozable: bool | None = None
    per_item: bool = False


@dataclass(frozen=True)
class Support:
    """The guidance record on a person step: ``enables``, ``reminds``, ``guides``. Frozen data in the definition, like a rule
    row; it names no association."""

    enables: Enables = Enables()
    reminds: Reminds = Reminds()
    guides: Guides = Guides()


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
    roles: tuple[Role, ...] = ()           # further roles that may act on the step; ``role`` stays the primary, the one listed
    na: NotApplicable | None = None        # the not-applicable outcome; a legal step may carry it though it cannot be skipped
    waits_on_child: bool = False           # not done until every child run spawned from this step is done or cancelled
    public_title: bool = False             # a ``held`` run may show this step's title outside the private view (it names no matter)
    remedy_of: str = ""                    # a check this step remedies: the check may stay failed while this step is open (see fold)
    item_set: str = ""                     # a named set of items this step repeats over, supplied while the run goes ("": the run's own)
    item_needs: tuple[str, ...] = ()       # steps in ``needs`` read item by item: an item waits only for its own item of them
    ends_by_note: bool = False             # a wait that only a person's recorded note ends (no reader, no date ends it)
    support: Support | None = None         # the guidance record of a person step (enable, remind, guide); None: derived from the fields above

    @property
    def item_aware(self) -> bool:
        """Whether the step uses the item-set rules (a named set, or per-item needs): a roll-up by what is most pressing, one
        branch choice and one clock for each item, and a wait for items not yet supplied."""
        return bool(self.item_set or self.item_needs)

    @property
    def is_legal(self) -> bool:
        return self.legal or (self.clock is not None and self.clock.basis is ClockBasis.LAW)

    @property
    def acting_roles(self) -> tuple[Role, ...]:
        """Every role that may act on the step: the primary first, then the others, each once."""
        return tuple(dict.fromkeys((self.role, *self.roles)))


@dataclass(frozen=True)
class StepGroup:
    """A named group of steps (``StepDef.group`` names it). The fold and the readers fold a group into one row that expands while
    it holds the current step and collapses when it is done or not yet reached; the steps stay what they are."""

    key: str
    title: str = ""


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
    visibility: Visibility = Visibility.BOARD
    held_title: str = ""                   # the general words a ``held`` run shows outside the private view ("A member's hearing")
    console_start: bool = True             # whether the console may start a run (False: a terminal procedure the console never starts)
    groups: tuple[StepGroup, ...] = ()     # titles for the groups steps name; a group no row declares is titled by its key

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
                if slot.required and not slot.late:
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

    def slot(self, name: str) -> DateSlot | None:
        return next((d for d in self.dates if d.name == name), None)

    def check_date_set(self, name: str, day: str, dates: Mapping[str, str], today: date) -> list[str]:
        """The problems with setting slot ``name`` to ``day`` after the start, given the dates the run now has: a slot the
        definition does not declare, one that is fixed at the start, a day that is not YYYY-MM-DD, one that breaks the
        slot's own past or future rule, and one out of order with the slot it comes after (or a slot that comes after it)."""
        slot = self.slot(name)
        if slot is None:
            return [f"no date slot {name}"]
        if not slot.settable:
            return [f"date {name} is fixed when the run starts; it is not set later"]
        try:
            value = date.fromisoformat(str(day))
        except ValueError:
            return [f"date {name} is not YYYY-MM-DD: {day}"]
        out: list[str] = []
        if slot.timing is DateTiming.PAST and value > today:
            out.append(f"date {name} ({value}) is in the future; this slot takes a day that has come")
        if slot.timing is DateTiming.FUTURE and value < today:
            out.append(f"date {name} ({value}) is in the past; this slot takes a day that has not come")
        known = {k: v for k, v in dates.items() if k != name}
        if slot.after and known.get(slot.after):
            try:
                if value < date.fromisoformat(known[slot.after]):
                    out.append(f"date {name} ({value}) comes before {slot.after} ({known[slot.after]})")
            except ValueError:
                pass
        for other in self.dates:
            if other.after == name and known.get(other.name):
                try:
                    if date.fromisoformat(known[other.name]) < value:
                        out.append(f"date {other.name} ({known[other.name]}) would come before {name} ({value})")
                except ValueError:
                    pass
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
    item: str = ""                         # the item a per-item clock is for ("" for a clock on a step or the whole)


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
    roles: tuple[Role, ...] = ()           # every role that may act on the step, the primary first
    na: bool = False                       # done as not applicable (a person's recorded outcome, not a skip)
    children: tuple[str, ...] = ()         # child runs spawned from this step, in order
    remedy: str = ""                       # for a failed check: the step that remedies it, while that step is open
    item_counts: tuple[tuple[StepState, int], ...] = ()    # for a step with items: how many items are in each state


@dataclass(frozen=True)
class GroupView:
    """A step group as the fold reads it: its steps, a roll-up state, how many are finished, and whether it is expanded (it
    holds the run's current step or a failed one) or collapsed (done, or not yet reached)."""

    key: str
    title: str
    steps: tuple[str, ...]
    state: StepState
    done: int
    total: int
    expanded: bool
    current: str = ""                      # the group's step that is the run's current one, "" when it holds none


@dataclass(frozen=True)
class DateView:
    """One date slot of a run as it stands: its value, who set it after the start, and whether a person may set it now.
    ``correction`` is true when a value is already there, so a later date-set needs a reason."""

    name: str
    label: str = ""
    value: str = ""
    required: bool = True
    late: bool = False
    settable: bool = False
    correction: bool = False
    timing: str = "any"
    set_by: str = ""
    set_at: str = ""
    record: str = ""
    sets: int = 0                          # how many date-set events this slot has


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
    date_slots: tuple[DateView, ...] = ()  # each slot the definition declares, with whether a person may set it now
    groups: tuple[GroupView, ...] = ()     # each step group, in the order the definition's steps first name it
    item_sets: Mapping[str, tuple[str, ...]] = field(default_factory=dict)   # each named set's items ("" is the run's own, ``items``)

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
    act: str                                # "attest", "skip", or "na" (not applicable)
    by: str
    roles: tuple[str, ...] = ()
    first_by: str = ""
    texts: tuple[str, ...] = ()
    today: date | None = None
    step_roles: tuple[str, ...] = ()        # every role that may act on the step (``role`` is the primary)


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
