"""The clocks each board meeting starts, read forward, so a late notice or late minutes is seen before the day passes.

``jason schedule-evidence`` reads backward: what the record shows was done for each occurrence that fell due. This
module reads the same records forward (``jason schedule-evidence --watch``, and the ``meetings`` section of
``jason attention``). For each board meeting from ``past`` days plus the minutes' 30 back to ``ahead`` days on, it
gives two clocks and what is on record for each so far:

- **the notice to members** (Civil Code 4920): the notice catalog's ``board-meeting`` clock, made stricter by any
  governing document that asks more (``notice_catalog.effective``; 4920(b)(3)); for a meeting the Zoom index shows
  held solely in executive session, ``board-meeting-executive`` (4920(b)(2)). The record is read by the shared notice
  reader (``notice_evidence.meeting_notices``): the delivery ledger's notice for the day (delivered, sent with its
  follow-ups owed, or sent and not synced), the catalog's notice sent, the notice's file (or, failing a notice, the
  agenda). A delivery, or a send with its follow-ups listed, on time meets the clock; a file never does
  (``Standing.FILE_ONLY``). The clock names the notice's address (``jason://notice/KEY``) when the ledger holds it.
- **the minutes available to members** (4950(a)): the ``minutes-available`` clock, for a meeting that was not solely
  an executive session. The record is the earliest dated copy of the minutes or of a draft marked as one: the
  evidence finder's ``minutes_on_record``.

Which meetings: each regular meeting the schedule sets (``schedule.anchors_for``, monthly as the practice is), each
day the meeting catalog holds a record of (an agenda drafted, a notice sent: a special meeting or a moved one), and
each meeting on record in the window behind. A completion a person recorded for the assignment that owns a clock
(``jason schedule --done``) counts as a record, so a posting, which jason does not see, can be recorded once.

A miss stays a miss: "none on record" is not "none given". The watch reads disk only, writes nothing, and decides
nothing: it says which day a clock ends and what the record shows, and a person gives the notice, posts the minutes,
or records what was done.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.notices import Anchor as NoticeAnchor

PAST_DAYS = 30                         # how far back a passed clock is still shown
AHEAD_DAYS = 60                        # how far ahead the watch looks for meetings
NOTICE = "board-meeting"               # the notice catalog's rows
EXECUTIVE_NOTICE = "board-meeting-executive"
MINUTES = "minutes-available"
SUBDIVISION = {NOTICE: "CIV 4920(a)", EXECUTIVE_NOTICE: "CIV 4920(b)(2)", MINUTES: "CIV 4950(a)"}
BOARD_KINDS = {"board meeting"}                                   # the Zoom index's kinds (``zoom.models.MeetingKind``)
EXECUTIVE_KINDS = {"executive session", "disciplinary hearing"}  # held solely in executive session when alone
COMMAND = "jason schedule-evidence --watch"
CAVEATS = (
    "None on record is not none given: a notice posted (general delivery, Civil Code 4045) or minutes made available "
    "where jason does not look are not on disk. Once a person confirms one, record it (jason schedule --done KEY DUE "
    "--by NAME --evidence TEXT) and the watch counts it.",
    "Every meeting ahead is read as an open board meeting (at least four days' notice). One held solely in executive "
    "session needs two (4920(b)(2)); an emergency meeting under 4923 needs none, and the minutes are its evidence.",
    "Minutes on record in time means a copy dated by the deadline (sent, or created on Drive); when members could "
    "first read it is not kept.",
    "Read from the meeting catalog as last built: a notice sent or minutes filed since are not on record until it is "
    "rebuilt (jason meetings --sync reads Zoom and PayHOA's communications log first, then rebuilds it).",
)


class Standing(Enum):
    MET = "on record in time"
    LATE = "on record late"
    FILE_ONLY = "a file in time; its delivery is not on record"
    FILE_LATE = "a file, written after the deadline; its delivery is not on record"
    UNDATED = "on record, undated"
    OPEN = "none on record yet"
    PASSED = "none on record; the deadline passed"


@dataclass(frozen=True)
class Clock:
    what: str                          # "notice" or "minutes"
    requirement: str                   # the notice catalog's key
    authority: str                     # the statute and subdivision
    timing: str                        # the clock in words
    deadline: date                     # the last day it is met
    standing: Standing
    record: str = ""                   # the record found: its name and where it is kept
    on: date | None = None             # the record's date
    note: str = ""
    assignment: str = ""               # the schedule's assignment that owns the clock
    due: date | None = None            # that assignment's due day for this meeting
    strength: str = ""                 # a notice's: delivered, sent with follow-ups owed, sent, or file
    notice: str = ""                   # the notice's address (jason://notice/KEY) when the delivery ledger holds it

    @property
    def done(self) -> bool:
        return self.standing is Standing.MET

    @property
    def unsynced(self) -> bool:
        """A notice clock met by a send whose outcomes are not synced: a person syncs it, or records the posting."""
        return self.what == "notice" and self.standing in (Standing.MET, Standing.LATE) and self.strength == "sent"

    def row(self) -> dict[str, Any]:
        return {"what": self.what, "requirement": self.requirement, "authority": self.authority,
                "timing": self.timing, "deadline": self.deadline.isoformat(), "standing": self.standing.value,
                "record": self.record, "on": self.on.isoformat() if self.on else None, "note": self.note,
                "assignment": self.assignment, "due": self.due.isoformat() if self.due else None,
                "strength": self.strength, "notice": self.notice}


@dataclass
class WatchedMeeting:
    day: date
    kind: str                          # "board meeting", or "executive session only"
    basis: str                         # why jason knows of it: the schedule, records on disk
    titles: tuple[str, ...] = ()
    held: bool | None = None           # past: a record shows it held (True), only its notice (None); ahead: None
    clocks: list[Clock] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def row(self) -> dict[str, Any]:
        return {"date": self.day.isoformat(), "kind": self.kind, "basis": self.basis, "titles": list(self.titles),
                "held": self.held, "clocks": [c.row() for c in self.clocks], "notes": self.notes}


@dataclass
class Watch:
    on: date
    start: date
    until: date
    meetings: list[WatchedMeeting]
    gaps: list[tuple[date, date]] = field(default_factory=list)   # a scheduled day behind with nothing on record,
    notes: list[str] = field(default_factory=list)                # and the day its minutes are due if it was held

    @property
    def next(self) -> WatchedMeeting | None:
        return next((m for m in self.meetings if m.day >= self.on), None)

    def as_dict(self) -> dict[str, Any]:
        return {"asOf": self.on.isoformat(), "from": self.start.isoformat(), "until": self.until.isoformat(),
                "meetings": [m.row() for m in self.meetings],
                "unrecorded": [{"scheduled": d.isoformat(), "minutesDueIfHeld": due.isoformat()} for d, due in self.gaps],
                "notes": self.notes, "caveats": list(CAVEATS)}

    def lines(self) -> list[str]:
        out = [f"Board meetings from {self.start} to {self.until}, as of {self.on}: the notice each is owed and the "
               "minutes each owes."]
        for m in self.meetings:
            head = f"{m.day}  {m.kind}" + (f" ({'; '.join(m.titles)})" if m.titles else "") + f"; {m.basis}"
            out.append(head)
            for c in m.clocks:
                rec = f": {c.record}" + (f", {c.on}" if c.on else "") if c.record else ""
                owner = f" [{c.assignment} due {c.due}]" if c.assignment and c.due else ""
                out.append(f"    {c.what:8} by {c.deadline} ({c.timing}, {c.authority}): {c.standing.value}{rec}{owner}"
                           + (f" [{c.notice}]" if c.notice else ""))
                if c.note:
                    out.append(f"        {c.note}")
            out += [f"    * {n}" for n in m.notes]
        if not self.meetings:
            out.append("No board meeting in the window: the profile sets no meeting schedule, and the catalog holds none.")
        for d, due in self.gaps:
            out.append(f"* The schedule set a meeting on {d} and nothing is on record near it: if it was held, its "
                       f"minutes are due by {due} (rebuild the catalog: jason meetings --sync).")
        out += [f"* {n}" for n in self.notes]
        out += [f"_{c}_" for c in CAVEATS]
        return out


# ---------------------------------------------------------------------------------------------------------------
# The clocks, from the notice catalog.


def _clock(key: str, community: Any) -> tuple[str, Any]:
    """The requirement's clock from the meeting (the statute's, made stricter by the documents) and its authority."""
    from jason.community.notice_catalog import effective

    row, clocks, _, _ = effective(key, community)
    timing = next(t for t in clocks if t.anchor is NoticeAnchor.MEETING)
    return SUBDIVISION.get(key, row.statute), timing


def _owner(ref: str, day: date, rows: tuple[Any, ...]) -> tuple[str, date | None]:
    """The assignment anchored on the board meeting that owns ``ref``, and its due day for the meeting on ``day``."""
    from jason.community.schedule import Anchor, Trigger, covering

    for a in covering(ref, rows):
        if a.trigger is Trigger.ANCHORED and a.anchor is Anchor.BOARD_MEETING:
            return a.key, day + timedelta(days=a.offset_days)
    return "", None


def _recorded(done: dict[tuple[str, str], dict[str, Any]], key: str, due: date | None) -> tuple[date, str] | None:
    row = done.get((key, due.isoformat())) if key and due else None
    if not row:
        return None
    try:
        when = date.fromisoformat(str(row.get("done"))[:10])
    except ValueError:
        return None
    return when, f"recorded done by {row.get('by')}: {row.get('evidence')}"


VERDICTS = {"met": Standing.MET, "late": Standing.LATE, "file": Standing.FILE_ONLY, "file late": Standing.FILE_LATE,
            "undated": Standing.UNDATED, "open": Standing.OPEN, "passed": Standing.PASSED}


def _notice_clock(stores: Any, day: date, key: str, on: date, community: Any, rows: tuple[Any, ...],
                  done: dict[tuple[str, str], dict[str, Any]]) -> Clock:
    """The notice's clock, judged by the shared reader (``notice_evidence``): a delivery, or a send with its follow-ups
    listed, on time meets it; a file never does. A person's record of the notice given (a posting) is a delivery."""
    from jason.tasks.notice_evidence import NoticeRecord, Strength, judge, meeting_notices

    authority, timing = _clock(key, community)
    deadline = timing.window(day)[1]
    owner, due = _owner(f"notice:{key}", day, rows)
    found = meeting_notices(stores, day)
    person = _recorded(done, owner, due)
    if person:
        found.append(NoticeRecord(person[1], person[0], Strength.DELIVERED, "jason schedule --done",
                                  note="a person recorded it given"))
    verdict, r = judge(found, deadline, on)
    standing = VERDICTS[verdict.value]
    if r is None:
        return Clock("notice", key, authority, timing.describe(), deadline, standing, assignment=owner, due=due)
    how = r.describe() if r.key else (r.note if r.strength is Strength.DELIVERED else
                                      f"{r.strength.value}" + (f" ({r.note})" if r.note else ""))
    if r.strength.counts:
        lead = (day - r.on).days
        text = f"given {lead} day{'s' if lead != 1 else ''} before the meeting; {how}"
        if standing is Standing.LATE:
            text += f"; at least {timing.least} are required"
    else:
        text = (f"{how}: the notice's file is on record, not that it went out; if it did, sync it (jason notices "
                f"KEY --sync) or record the posting")
    return Clock("notice", key, authority, timing.describe(), deadline, standing, r.what, r.on, text, owner, due,
                 r.strength.value, r.address)


def _minutes_clock(stores: Any, day: date, on: date, community: Any, rows: tuple[Any, ...],
                   done: dict[tuple[str, str], dict[str, Any]]) -> Clock:
    from jason.tasks.schedule_evidence import minutes_on_record

    authority, timing = _clock(MINUTES, community)
    deadline = timing.window(day)[1]
    owner, due = _owner(f"notice:{MINUTES}", day, rows)
    dated, undated = minutes_on_record(stores, day)
    person = _recorded(done, owner, due)
    if person:
        dated = sorted(dated + [person])
    if dated:
        first, record = dated[0]
        after = (first - day).days
        standing = Standing.MET if first <= deadline else Standing.LATE
        note = f"the earliest dated copy is {after} day{'s' if after != 1 else ''} after the meeting"
        if standing is Standing.LATE:
            note += "; an earlier copy may be where jason does not look"
        return Clock("minutes", MINUTES, authority, timing.describe(), deadline, standing, record, first, note, owner,
                     due)
    if undated:
        return Clock("minutes", MINUTES, authority, timing.describe(), deadline, Standing.UNDATED, undated[0], None,
                     "on file with no date: when members could read it is not kept", owner, due)
    standing = Standing.PASSED if on > deadline else Standing.OPEN
    return Clock("minutes", MINUTES, authority, timing.describe(), deadline, standing, assignment=owner, due=due)


# ---------------------------------------------------------------------------------------------------------------
# The meetings.


def owned_keys(community: Any) -> frozenset[str]:
    """The schedule's assignments whose occurrences the watch reads against the record (the notice and the minutes of
    each board meeting), so a digest need not list them twice."""
    from jason.community.schedule import assignments

    rows = assignments(community)
    found = {_owner(f"notice:{key}", date.min + timedelta(days=400), rows)[0]
             for key in (NOTICE, EXECUTIVE_NOTICE, MINUTES)}
    return frozenset(k for k in found if k)


def _zoom_kinds(data_dir: Path) -> dict[date, set[str]]:
    """The Zoom index's kinds of meeting held each day."""
    from jason.tasks.zoom import load_index

    out: dict[date, set[str]] = {}
    for row in load_index(data_dir).get("meetings", []) or []:
        try:
            day = date.fromisoformat(str(row.get("date") or "")[:10])
        except ValueError:
            continue
        out.setdefault(day, set()).add(str(row.get("kind") or ""))
    return out


def _has(meeting: dict[str, Any]) -> list[str]:
    return sorted(k for k in (meeting.get("has") or {}) if k != "correspondence")


def watch(community: Any, data_dir: Path, *, on: date | None = None, past: int = PAST_DAYS, ahead: int = AHEAD_DAYS,
          stores: Any = None) -> Watch:
    """Every board meeting from ``past`` plus the minutes' days back to ``ahead`` days on, with its clocks."""
    from jason.community.schedule import Anchor, anchors_for, assignments
    from jason.tasks.schedule import completions
    from jason.tasks.schedule_evidence import HELD_KINDS, MEETING_SLACK_DAYS, Stores

    on = on or date.today()
    root = Path(data_dir)
    stores = stores or Stores(root, community)
    _, minutes_timing = _clock(MINUTES, community)
    start = on - timedelta(days=past + (minutes_timing.most or 0))
    until = on + timedelta(days=ahead)
    rows = assignments(community)
    done = {(r["key"], r["due"]): r for r in completions(root)}
    kinds = _zoom_kinds(root)
    catalog = stores.catalog()
    by_day: dict[date, dict[str, Any]] = {}
    for m in catalog.get("meetings", []) or []:
        try:
            by_day[date.fromisoformat(str(m.get("date"))[:10])] = m
        except ValueError:
            continue
    held_days = set(stores.held())
    scheduled = [d for d in anchors_for(community, start, until)[Anchor.BOARD_MEETING]]
    days = {d for d in held_days if start <= d < on}
    days |= {d for d in by_day if on <= d <= until}
    days |= {d for d in scheduled if d >= on}
    notes: list[str] = []
    # A scheduled day behind with nothing on record near it: whether it was held is not known.
    gaps = [(d, minutes_timing.window(d)[1]) for d in scheduled
            if d < on and not any(abs((d - h).days) <= MEETING_SLACK_DAYS for h in held_days)]
    out: list[WatchedMeeting] = []
    for day in sorted(days):
        m = by_day.get(day, {})
        zoom = kinds.get(day, set())
        if zoom and not zoom & (BOARD_KINDS | EXECUTIVE_KINDS):
            continue                                 # a members' or committee meeting: not the board's clocks
        executive = bool(zoom) and not zoom & BOARD_KINDS
        has = _has(m)
        basis = []
        if day in scheduled:
            basis.append("set by the meeting schedule")
        if has:
            basis.append("on record: " + ", ".join(has))
        held = None
        if day < on:
            held = True if set(has) & HELD_KINDS or stores.minutes().get(day) or zoom else None
        w = WatchedMeeting(day, "executive session only" if executive else "board meeting",
                           "; ".join(basis) or "on record", tuple(m.get("titles") or ()), held)
        w.clocks.append(_notice_clock(stores, day, EXECUTIVE_NOTICE if executive else NOTICE, on, community, rows,
                                      done))
        if executive:
            w.notes.append("Held solely in executive session: no open minutes are owed (4950(a)); its matters are "
                           "generally noted in the next open meeting's minutes (4935(e)).")
        elif day < on:
            w.clocks.append(_minutes_clock(stores, day, on, community, rows, done))
            if held is None:
                w.notes.append("Only its notice is on record: whether it was held is not shown.")
        out.append(w)
    built = str(catalog.get("builtAt") or "")
    if not catalog:
        notes.append("No meeting catalog on disk (jason meetings builds it): nothing is on record for any meeting.")
    elif built:
        notes.append(f"The meeting catalog was built {built[:10]}.")
    return Watch(on, start, until, out, gaps, notes)


__all__ = ["AHEAD_DAYS", "CAVEATS", "COMMAND", "Clock", "PAST_DAYS", "Standing", "Watch", "WatchedMeeting", "owned_keys",
           "watch"]
