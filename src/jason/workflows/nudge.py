"""When a person step is due, late, or has sat open, and who else sees it: a pure reading of a run's view (docs/workflows/person-steps.md,
section 6). Nothing is stored and nothing is sent. A line is computed from the folded run, the day, and the defaults below; the same
view and day give the same answer, and a prefix of the events gives the earlier one.

Each person step gets at most one **band**, the first that applies: ``legal`` (a law clock due today or past), ``late`` (any other
clock past), ``date`` (a settable date slot with no value that a clock reads from, on a step that is ready), ``soon`` (a clock within
the lead), ``stale`` (open a while, with no clock), ``quiet`` (everything else, never listed). A step that is not ready, a run that is
paused or still a draft, and a step that is over are always quiet.

**Escalation is visibility, not a message.** A step that is late for its escalation delay (none for a law clock: the day it falls), or
whose offices nobody holds, also shows for the escalation office. ``escalated_to`` names it; nothing is sent to anyone.

**The numbers are proposals.** The lead, the open-a-while threshold, the escalation delay, and the table are ``proposed policy``
(section 4.3 and 6.5): the board adopts or changes them like a control. Until adopted they are defaults, labeled ``PROPOSED`` and never
drawn as the law's. A step's own ``Reminds`` may make a nudge earlier or louder; it can never shorten a legal date, remove a legal line,
or let a legal step be snoozed.

Imports only the engine's types, so it loads no profile and no client.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, tzinfo
from enum import Enum
from typing import Any, Iterable, Mapping

from jason.workflows.types import (
    ClockBasis, ClockView, Event, EventKind, Role, RunState, RunView, StepDef, StepKind, StepState, StepView, Workflow,
)

PROPOSED_NOTE = "proposed, not the law's"
BOARD = "the whole board"

LIVE = ("upcoming", "due", "overdue")
"""The clock statuses that still mean a date is coming or has passed (``satisfied``, ``undated``, ``not running``, and a recorded
not-applicable are none of them)."""

ACTIVE_RUNS = (RunState.ACTIVE, RunState.WAITING, RunState.FAILED)


class Band(Enum):
    LEGAL = "legal"
    LATE = "late"
    DATE = "date"
    SOON = "soon"
    STALE = "stale"
    QUIET = "quiet"


WORDS: Mapping[Band, str] = {Band.LEGAL: "LEGAL", Band.LATE: "OVERDUE", Band.DATE: "needs a date", Band.SOON: "due soon",
                             Band.STALE: "open", Band.QUIET: ""}
"""The digest's own words for a band (``jason attention``: LEGAL, OVERDUE, due soon, open, and the new "needs a date")."""

ORDER = {Band.LEGAL: 0, Band.LATE: 1, Band.DATE: 2, Band.SOON: 3, Band.STALE: 4, Band.QUIET: 5}


@dataclass(frozen=True)
class Prefs:
    """The three numbers the board adopts (section 4.3, 6.8). The defaults are proposed policy: 14 days (the schedule's two weeks), 7 days,
    72 hours. ``adopted`` is false until a decision makes them the board's."""

    lead_days: int = 14
    after_hours: int = 168
    escalate_after_hours: int = 72
    adopted: bool = False


DEFAULTS = Prefs()

ESCALATION: Mapping[str, Role] = {
    Role.MANAGER.value: Role.PRESIDENT, Role.PRESIDENT.value: Role.VICE_PRESIDENT, Role.VICE_PRESIDENT.value: Role.PRESIDENT,
    Role.TREASURER.value: Role.PRESIDENT, Role.DIRECTOR.value: Role.PRESIDENT, Role.SECRETARY.value: Role.PRESIDENT,
    Role.ANYONE.value: Role.PRESIDENT,
}
"""The default escalation table (section 6.5): who also sees a late step, by the office that holds it. A proposal; the profile holds the
board's adopted one. A legal clock is seen by the whole board whoever holds it, and an office with no row escalates to the board."""


def escalation_office(sd: StepDef) -> str:
    """The office that also sees the step when it is late: the step's own ``Reminds.escalate_to``, else the table's row for its
    primary office, else the whole board."""
    own = sd.support.reminds.escalate_to if sd.support is not None else None
    if own is not None:
        return own.value
    row = ESCALATION.get(sd.role.value)
    return row.value if row is not None else BOARD


# --- claims ---------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Claim:
    """Who said they are on a step, and when. It is a note, not an assignment: it grants nothing and blocks nobody."""

    by: str
    at: str


_ENDS = (EventKind.ATTESTED, EventKind.DECIDED, EventKind.SKIPPED, EventKind.NOT_APPLICABLE, EventKind.ARRIVED, EventKind.REOPENED)


def claims_of(events: Iterable[Event]) -> dict[str, Claim]:
    """The standing claims, by step id, from the ``note`` events that carry a ``claim`` key: the latest claim wins, its maker's release
    ends it, and the step's ending (done, skipped, not applicable, arrived) or a reopen ends it too. Pure: events in, claims out."""
    out: dict[str, Claim] = {}
    for e in events:
        if not e.step:
            continue
        if e.kind in _ENDS:
            out.pop(e.step, None)
        elif e.kind is EventKind.NOTE and "claim" in e.detail:
            if e.detail.get("claim"):
                out[e.step] = Claim(e.by, e.at)
            elif e.step in out and out[e.step].by.casefold() == e.by.casefold():
                out.pop(e.step)
    return out


# --- one step's nudge -----------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Nudge:
    band: Band
    due: str = ""                          # the date the band is about, "" for none
    days: int | None = None                # days from the day asked to the date; negative once past
    basis: str = ""
    basis_label: str = ""
    legal: bool = False
    proposed: bool = False                 # the date's basis is jason's proposal, not the law's
    label: str = ""
    cite: str = ""
    open_days: int | None = None           # days since the step could be acted on
    escalated_to: str = ""                 # the office (or "the whole board") that also sees the step; "" for none
    escalated_why: str = ""
    lead_days: int = DEFAULTS.lead_days
    after_hours: int = DEFAULTS.after_hours
    snoozable: bool = False
    items: Mapping[str, Any] | None = None      # a per-item step: {total, notDone, earliest}
    claim: Claim | None = None
    claim_stale: bool = False

    @property
    def word(self) -> str:
        return WORDS[self.band]


BASIS_LABELS = {"law": "LEGAL", "documents": "DOCUMENTS", "counterparty": "COUNTERPARTY", "provider": "PROVIDER",
                "proposed policy": "PROPOSED", "person": "PERSON"}


LOCAL_ZONE: tzinfo | None = None
"""The zone whose calendar day a stored time falls on. None is the machine's own zone, the one ``date.today()`` reads, so a time and
"today" are compared on the same day basis. A test may set a fixed zone."""


def day_of(value: Any) -> date | None:
    """The calendar day of a stored time or date, on the day basis of ``today``. A run's events are stamped in UTC (``2026-10-12T06:30:00Z``)
    while "today" is the local date, so a run opened at 23:30 Pacific has a UTC stamp on the next day; the stamp is brought to the local
    day before it is compared. A bare ``YYYY-MM-DD`` is a day already. None when it is neither."""
    text = str(value or "").strip()
    if len(text) > 10 and text[10] in "T ":
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            moment = None
        if moment is not None:
            if moment.tzinfo is not None:
                moment = moment.astimezone(LOCAL_ZONE)
            return moment.date()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def days_between(later: date, earlier: date | None) -> int | None:
    """Whole days from ``earlier`` to ``later``, never below 0 (a time just before midnight cannot make a run older than it is)."""
    return None if earlier is None else max(0, (later - earlier).days)


def is_person_step(sd: StepDef) -> bool:
    """A step a human does: a person step, the board's decision the secretary records, or a wait only a person's note ends."""
    return sd.kind in (StepKind.PERSON, StepKind.DECISION) or (sd.kind is StepKind.WAIT and sd.ends_by_note)


def open_for_person(sd: StepDef, sv: StepView) -> bool:
    """Whether the step is waiting on a person now: a person or decision step that needs one, or a note-ended wait that is waiting."""
    if sd.kind is StepKind.WAIT:
        return bool(sd.ends_by_note) and sv.state is StepState.WAITING
    return sv.state in (StepState.NEEDS_PERSON, StepState.READY)


def ready_since(sd: StepDef, view: RunView) -> date | None:
    """The day the step could first be acted on, as far as the run's events show: the latest of the days its ``needs`` finished, and the
    day the run opened. Day-grained, so the same view and day give the same answer."""
    days = [d for n in sd.needs for d in [day_of(getattr(view.step(n), "at", ""))] if d is not None]
    opened = day_of(view.opened_at)
    if opened is not None:
        days.append(opened)
    return max(days) if days else None


def _clocks_of(view: RunView, step_id: str) -> list[ClockView]:
    return [c for c in view.clocks if c.step == step_id]


def step_nudge(wf: Workflow, sd: StepDef, view: RunView, today: date, *, prefs: Prefs = DEFAULTS,
               vacant: Iterable[str] = (), claims: Mapping[str, Claim] | None = None) -> Nudge:
    """The nudge for one step on ``today``. ``vacant`` is the offices (their words) that nobody holds; a step whose acting offices are
    all vacant is escalated at once. ``claims`` are the standing claims (``claims_of``)."""
    sv = view.step(sd.id)
    reminds = sd.support.reminds if sd.support is not None else None
    lead = prefs.lead_days if reminds is None or reminds.lead_days is None else reminds.lead_days
    after = prefs.after_hours if reminds is None or reminds.after_hours is None else reminds.after_hours
    legal = sd.is_legal
    snoozable = not legal and (reminds is None or reminds.snoozable is not False)
    base = Nudge(Band.QUIET, lead_days=lead, after_hours=after, snoozable=snoozable)
    if sv is None or view.state not in ACTIVE_RUNS or not open_for_person(sd, sv):
        return base
    claim = (claims or {}).get(sd.id)
    claim_stale = False
    since = ready_since(sd, view)
    open_days = days_between(today, since)
    if claim is not None:
        said = day_of(claim.at)
        claim_stale = said is not None and (days_between(today, said) or 0) * 24 >= after
    live = [c for c in _clocks_of(view, sd.id) if c.due and c.status in LIVE]
    pick = min(live, key=lambda c: (c.days if c.days is not None else 10 ** 6, c.key)) if live else None
    band, extra = Band.QUIET, {}
    if pick is not None:
        days = pick.days if pick.days is not None else (day_of(pick.due) - today).days if day_of(pick.due) else None
        extra = dict(due=pick.due, days=days, basis=pick.basis.value, basis_label=BASIS_LABELS.get(pick.basis.value, pick.basis.value.upper()),
                     legal=pick.basis is ClockBasis.LAW, proposed=pick.basis is ClockBasis.PROPOSED_POLICY, label=pick.label, cite=pick.cite)
        if days is not None:
            if pick.basis is ClockBasis.LAW and days <= 0:
                band = Band.LEGAL
            elif days < 0:
                band = Band.LATE
            elif days <= lead:
                band = Band.SOON
    elif sd.clock is not None and sd.clock.slot and any(c.status == "undated" for c in _clocks_of(view, sd.id)):
        slot = wf.slot(sd.clock.slot)
        if slot is not None and slot.settable and not view.dates.get(sd.clock.slot):
            band = Band.DATE
            extra = dict(basis=sd.clock.basis.value, basis_label=BASIS_LABELS.get(sd.clock.basis.value, sd.clock.basis.value.upper()),
                         legal=sd.clock.basis is ClockBasis.LAW, proposed=sd.clock.basis is ClockBasis.PROPOSED_POLICY,
                         label=sd.clock.label, cite=sd.clock.cite)
    if band is Band.QUIET and pick is None and not extra:
        if open_days is not None and open_days * 24 >= after and sv.state in (StepState.NEEDS_PERSON, StepState.WAITING):
            band = Band.STALE
    # escalation: visibility, never a message
    to, why = "", ""
    if band in (Band.LEGAL, Band.LATE):
        late_hours = -(extra.get("days") or 0) * 24
        delay = 0 if band is Band.LEGAL else (prefs.escalate_after_hours if reminds is None or reminds.escalate_after_hours is None
                                              else reminds.escalate_after_hours)
        if band is Band.LEGAL:
            to, why = BOARD, "a legal date falls today or has passed"
        elif late_hours >= delay:
            to, why = escalation_office(sd), (f"late for {delay} hours or more ({PROPOSED_NOTE})" if delay else "late")
    acting = [r.value for r in sd.acting_roles if r.value not in ("anyone", "jason", "scheduler")]
    gone = {str(v) for v in vacant}
    if acting and all(a in gone for a in acting):
        to = BOARD if band is Band.LEGAL or to == BOARD else escalation_office(sd)
        why = f"No one holds the {acting[0]} office"
    items = None
    if sv.items:
        notdone = [s for _, s in sv.items if s not in (StepState.DONE, StepState.SKIPPED, StepState.SUPERSEDED)]
        item_dues = sorted(c.due for c in _clocks_of(view, sd.id) if c.item and c.due and c.status in LIVE)
        items = {"total": len(sv.items), "notDone": len(notdone), "earliest": item_dues[0] if item_dues else ""}
    return Nudge(band, lead_days=lead, after_hours=after, snoozable=snoozable, open_days=open_days, escalated_to=to, escalated_why=why,
                 items=items, claim=claim, claim_stale=claim_stale, **extra)


def order_key(n: Nudge) -> tuple[int, int, int]:
    """Within a band: legal dates first (the band), then days to the date (earliest first), then the step open longest."""
    return (ORDER[n.band], n.days if n.days is not None else 10 ** 6, -(n.open_days or 0))


def run_nudges(wf: Workflow, view: RunView, today: date, *, prefs: Prefs = DEFAULTS, vacant: Iterable[str] = (),
               claims: Mapping[str, Claim] | None = None, quiet: bool = False) -> list[tuple[StepDef, Nudge]]:
    """Every person step of a run that is not quiet (with ``quiet``, every one that is open), most urgent first. Pure: the same view
    and day give the same list."""
    out = []
    for sd in wf.steps:
        if not is_person_step(sd):
            continue
        sv = view.step(sd.id)
        n = step_nudge(wf, sd, view, today, prefs=prefs, vacant=vacant, claims=claims)
        if n.band is not Band.QUIET or n.escalated_to or (quiet and sv is not None and view.state in ACTIVE_RUNS and open_for_person(sd, sv)):
            out.append((sd, n))
    return sorted(out, key=lambda r: order_key(r[1]))


__all__ = ["BASIS_LABELS", "BOARD", "Band", "Claim", "DEFAULTS", "ESCALATION", "LIVE", "Nudge", "ORDER", "PROPOSED_NOTE", "Prefs", "WORDS",
           "claims_of", "escalation_office", "is_person_step", "open_for_person", "order_key", "ready_since", "run_nudges", "step_nudge"]
