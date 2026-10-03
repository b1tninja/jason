"""People's own Google Tasks and calendar events, read beside what jason tracks (``jason.community.people_tasks``).

``read_google`` reads the calendar's events (two years back, a year ahead) and every Google Tasks list the Tasks token
signs in to, and keeps them in ``data/schedule/google-read.json``, which is private: a title can name an owner or a unit.
It reads only; nothing is created, completed, or changed. ``classify`` sets each item beside jason's own records:

- jason's own items are left out: a task carrying jason's marker (``jason:<key>`` in its notes) or on a schedule role
  list, an event carrying jason's private key, or (in a read made before the key was kept) an event titled as the board
  calendar titles its own; a calendar event that is only a task's mirror is left out too;
- each other task and event is matched (``match_item``): the profile's rule rows first, then an action register item,
  an assignment, or a recurring deadline by its exact title, then the calendar policy's words for a board meeting;
- what matches nothing is untracked recurring (a calendar series, a title that comes back in different months, or a rule
  that says so) or a one-off; an open task past its due day is stale.

The counts are of what is current: open tasks, and calendar items with a day ahead. Completed tasks and past events are
read for what recurs. ``proposals`` gathers the untracked recurring items, one per rule or title. A match is a lead: jason
never completes or closes a person's task.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jason.community.people_tasks import (
    TASK_MIRROR,
    Kind,
    Match,
    PeopleTaskRule,
    Source,
    Tracker,
    normal_title,
)

STORE = Path("schedule") / "google-read.json"
DAYS_BACK = 730                          # how far back the calendar is read
DAYS_AHEAD = 365                         # how far ahead
STALE_READ_DAYS = 14                     # a read older than this is said to be old
CAVEATS = (
    "Read from Google Tasks and the calendar as last read (jason schedule --read-google). A match is a lead for a "
    "person: jason completes, edits, and closes nothing in Google.",
    "Titles are people's own words and can name an owner or a unit: they stay in private outputs; a shared one prints "
    "the rule's label instead.",
)


def store_path(data_dir: Path) -> Path:
    return Path(data_dir) / STORE


def load(data_dir: Path) -> dict[str, Any] | None:
    path = store_path(data_dir)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# --- Reading Google ---------------------------------------------------------------------------------------------------

EVENT_FIELDS = ("id", "summary", "description", "start", "end", "recurrence", "recurringEventId", "status",
                "extendedProperties")
TASK_FIELDS = ("id", "title", "notes", "due", "status", "completed", "updated", "parent")


def read_google(calendar: Any, tasks: Any, data_dir: Path, *, calendar_id: str = "primary", today: date | None = None,
                days_back: int = DAYS_BACK, days_ahead: int = DAYS_AHEAD, write: bool = True) -> dict[str, Any]:
    """Read the calendar's events and every Tasks list, and keep them in the private store. Reads only. A part that
    Google refuses (a scope the token lacks) is kept as its error; a missing token raises (``GoogleAuthRequired``)
    before anything is read."""
    from jason.google.errors import GoogleError

    now = datetime.now(timezone.utc)
    day = today or now.date()
    low = datetime.combine(day - timedelta(days=days_back), datetime.min.time(), tzinfo=timezone.utc)
    high = datetime.combine(day + timedelta(days=days_ahead), datetime.min.time(), tzinfo=timezone.utc)
    out: dict[str, Any] = {"read": now.isoformat(timespec="seconds"), "from": low.date().isoformat(),
                           "until": high.date().isoformat(), "calendars": [], "tasklists": []}
    row: dict[str, Any] = {"id": calendar_id, "events": []}
    if calendar is not None:
        try:
            for e in calendar.events(calendar_id, time_min=low, time_max=high):
                row["events"].append({k: e.get(k) for k in EVENT_FIELDS if e.get(k) is not None})
        except GoogleError as exc:
            row["error"] = str(exc)[:200]
        out["calendars"].append(row)
    if tasks is not None:
        try:
            for tl in tasks.task_lists():
                items = tasks.tasks(tl["id"])
                out["tasklists"].append({"id": tl.get("id"), "title": tl.get("title"),
                                         "tasks": [{k: t.get(k) for k in TASK_FIELDS if t.get(k) is not None}
                                                   for t in items]})
        except GoogleError as exc:
            out["tasks_error"] = str(exc)[:200]
    if write:
        path = store_path(data_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return out


def read_lines(result: dict[str, Any]) -> list[str]:
    events = sum(len(c.get("events") or []) for c in result.get("calendars") or [])
    tasks = sum(len(t.get("tasks") or []) for t in result.get("tasklists") or [])
    out = [f"Read {events} calendar events ({result.get('from')} to {result.get('until')}) and {tasks} tasks on "
           f"{len(result.get('tasklists') or [])} lists; kept in data/{STORE.as_posix()} (private)."]
    for c in result.get("calendars") or []:
        if c.get("error"):
            out.append(f"* calendar {c.get('id')}: {c['error']}")
    if result.get("tasks_error"):
        out.append(f"* tasks: {result['tasks_error']}")
    return out


# --- The items --------------------------------------------------------------------------------------------------------

@dataclass
class PersonItem:
    source: Source
    where: str                           # the task list's or the calendar's title
    title: str
    dates: tuple[date, ...]              # a task's due or completed day; an event's days
    open: bool                           # an open task; an event with a day ahead
    due: date | None = None              # a task's due day; an event's next day
    series: bool = False                 # a calendar series (a recurring event)
    repeats: bool = False                # the same title in different months
    match: Match | None = None
    rule: PeopleTaskRule | None = None
    kind: Kind = Kind.ONE_OFF
    stale: bool = False
    done: bool = False                   # a completed task

    @property
    def retire(self) -> str:
        return self.rule.retire if self.rule else ""

    def label(self, private: bool = False) -> str:
        """The title, or in a shared output what jason knows it as: the rule's label, or what it matched."""
        if not private:
            return self.title
        if self.rule is not None:
            return self.rule.label
        if self.match is not None:
            return f"a {self.source.value} matching {self.match.tracker.value} {self.match.ref}".rstrip()
        return f"a person's {self.source.value} with no match"

    def matched(self) -> str:
        if self.match is None:
            return ""
        miss = "" if self.match.valid else " (not kept by jason: a miss)"
        return f"{self.match.tracker.value} {self.match.ref}".rstrip() + miss

    def row(self, private: bool = False) -> dict[str, Any]:
        return {"source": self.source.value, "list": "" if private else self.where, "title": self.label(private),
                "kind": self.kind.value, "open": self.open, "stale": self.stale, "done": self.done,
                "due": self.due.isoformat() if self.due else None,
                "dates": [d.isoformat() for d in self.dates[-6:]], "times": len(self.dates),
                "series": self.series, "repeats": self.repeats,
                "matched": self.matched(), "how": self.match.how if self.match else "",
                "rule": self.rule.key if self.rule else "", "retire": self.retire}


def _day(value: Any) -> date | None:
    if isinstance(value, dict):
        value = value.get("date") or value.get("dateTime")
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _own_event(event: dict[str, Any], policy: Any) -> bool:
    """An event jason made: its private key, or (in a read made before the key was kept) a title only jason gives."""
    if ((event.get("extendedProperties") or {}).get("private") or {}).get("jason"):
        return True
    if policy is None:
        return False
    title = str(event.get("summary") or "")
    prefixes = tuple(p for p in (policy.schedule_prefix, policy.schedule_done_prefix, policy.deadline_prefix) if p)
    exact = {policy.notice_title, policy.hearing_title, policy.hearing_notice_title, policy.hearing_decision_title}
    return title.startswith(prefixes) or title in exact


def _own_task(task: dict[str, Any], list_title: str) -> bool:
    from jason.google.tasks import marker_of
    from jason.tasks.schedule_sync import LIST_PREFIX

    return bool(marker_of(task)) or str(list_title or "").startswith(LIST_PREFIX)


def items(raw: dict[str, Any], *, today: date, policy: Any = None) -> tuple[list[PersonItem], Counter]:
    """The people's items in a stored read, and a count of what was left out (jason's own, task mirrors)."""
    left: Counter = Counter()
    out: list[PersonItem] = []
    for tl in raw.get("tasklists") or []:
        where = str(tl.get("title") or "")
        for t in tl.get("tasks") or []:
            if _own_task(t, where):
                left["jason's own tasks"] += 1
                continue
            done = t.get("status") == "completed"
            due, completed = _day(t.get("due")), _day(t.get("completed"))
            dates = tuple(d for d in (due if not done else completed or due,) if d)
            out.append(PersonItem(Source.TASK, where, str(t.get("title") or "").strip(), dates, not done, due,
                                  done=done, stale=bool(not done and due and due < today)))
    for cal in raw.get("calendars") or []:
        where = str(cal.get("summary") or cal.get("id") or "")
        series: dict[str, list[dict[str, Any]]] = {}
        for e in cal.get("events") or []:
            if e.get("status") == "cancelled":
                continue
            if str(e.get("description") or "").startswith(TASK_MIRROR):
                left["calendar mirrors of tasks"] += 1
                continue
            if _own_event(e, policy):
                left["jason's own events"] += 1
                continue
            sid = e.get("recurringEventId")
            key = f"series:{sid}" if sid else f"one:{e.get('id') or ''}:{normal_title(e.get('summary') or '')}:{_day(e.get('start'))}"
            series.setdefault(key, []).append(e)
        for key, group in series.items():
            days = tuple(sorted(d for d in (_day(e.get("start")) for e in group) if d))
            ahead = [d for d in days if d >= today]
            title = str(group[-1].get("summary") or "").strip()
            out.append(PersonItem(Source.EVENT, where, title, days, bool(ahead), ahead[0] if ahead else None,
                                  series=key.startswith("series:") or any(e.get("recurrence") for e in group)))
    # A title that comes back in different months recurs, whether a person re-made the task or the event.
    months: dict[str, set[tuple[int, int]]] = {}
    for i in out:
        if not i.series:
            months.setdefault(normal_title(i.title), set()).update((d.year, d.month) for d in i.dates)
    for i in out:
        if not i.series and len(months.get(normal_title(i.title), ())) >= 2:
            i.repeats = True
    return out, left


# --- Matching ---------------------------------------------------------------------------------------------------------

@dataclass
class Known:
    """What jason tracks, as the matcher reads it."""

    assignments: tuple = ()
    obligations: tuple = ()
    board_items: list = field(default_factory=list)
    policies: tuple = ()
    policy: Any = None                   # the board calendar's ``CalendarPolicy``
    meeting_keys: tuple[str, ...] = ()   # the assignments that cover the board's meetings (CIV 4900)

    @classmethod
    def read(cls, community: Any, data_dir: Path) -> Known:
        from jason.community.schedule import Adoption, assignments, covering

        rows = tuple(a for a in assignments(community) if a.adoption is not Adoption.DECLINED)
        try:
            from jason.tasks.board_items import load as load_items

            board = load_items(Path(data_dir))
        except Exception:  # a broken register is read as empty; the rest still matches
            board = []
        try:
            catalog = getattr(community, "insurance", lambda: None)()
            policies = tuple(getattr(catalog, "policies", ()) or ())
        except Exception:
            policies = ()
        try:
            from jason.tasks.board_calendar import policy_for

            policy = policy_for(community)
        except Exception:
            policy = None
        return cls(rows, tuple(getattr(community, "obligations", lambda: ())()), board, policies, policy,
                   tuple(a.key for a in covering("CIV 4900", rows)))

    def exists(self, tracker: Tracker, ref: str) -> bool:
        if tracker is Tracker.ASSIGNMENT:
            return ref in {a.key for a in self.assignments}
        if tracker is Tracker.OBLIGATION:
            return ref in {o.name for o in self.obligations}
        if tracker is Tracker.BOARD_ITEM:
            return not ref or ref in {b.id for b in self.board_items}
        if tracker is Tracker.INSURANCE:
            kinds = {getattr(getattr(p, "kind", None), "value", "") for p in self.policies}
            return bool(self.policies) and (not ref or ref in kinds)
        if tracker is Tracker.REQUEST:
            from jason.community.responses import ResponseKind

            return not ref or ref in {k.value for k in ResponseKind}
        return True                       # the board's meetings: the board calendar plans them


def match_item(title: str, rules: tuple[PeopleTaskRule, ...], known: Known) -> tuple[Match | None, PeopleTaskRule | None]:
    """What a person's task or event stands for: the first rule row that fits, else a register item, an assignment, or
    a recurring deadline by its exact title, else a board meeting by the calendar policy's words. None: no match."""
    for rule in rules:
        if rule.matches(title):
            if rule.tracker is None:
                return None, rule
            return Match(rule.tracker, rule.ref, f"rule {rule.key}", known.exists(rule.tracker, rule.ref)), rule
    folded = normal_title(title)
    if not folded:
        return None, None
    for b in known.board_items:
        if normal_title(b.title) == folded:
            return Match(Tracker.BOARD_ITEM, b.id, "board item title"), None
    for a in known.assignments:
        if normal_title(a.title) == folded:
            return Match(Tracker.ASSIGNMENT, a.key, "assignment title"), None
    for o in known.obligations:
        if normal_title(o.name) == folded:
            return Match(Tracker.OBLIGATION, o.name, "recurring deadline name"), None
    policy = known.policy
    if policy is not None:
        words = tuple(w.casefold() for w in policy.covered_words)
        if any(w in title.casefold() for w in words) or title in (policy.regular_title, policy.special_title):
            return Match(Tracker.BOARD_MEETING, ", ".join(known.meeting_keys) or "jason calendar", "calendar words"), None
    return None, None


# --- The reading ------------------------------------------------------------------------------------------------------

@dataclass
class Reading:
    on: date
    read: str                            # when the store was read from Google ("" when there is none)
    found: list[PersonItem]
    left: Counter
    notes: list[str] = field(default_factory=list)

    @property
    def current(self) -> list[PersonItem]:
        """What is current: open tasks, and calendar items with a day ahead."""
        return [i for i in self.found if i.open]

    def counts(self) -> dict[str, Any]:
        now = self.current
        kinds = Counter(i.kind.value for i in now)
        return {"open": len(now), "openTasks": sum(1 for i in now if i.source is Source.TASK),
                "calendarItems": sum(1 for i in now if i.source is Source.EVENT),
                **{k.value: kinds.get(k.value, 0) for k in Kind},
                "stale": len(self.stale()), "undated": sum(1 for i in now if i.source is Source.TASK and i.due is None),
                "retire": sum(1 for i in now if i.retire),
                "doneTasks": sum(1 for i in self.found if i.done),
                "pastEvents": sum(1 for i in self.found if i.source is Source.EVENT and not i.open),
                "leftOut": dict(self.left)}

    def stale(self) -> list[PersonItem]:
        """Open tasks past their due day, oldest first."""
        return sorted((i for i in self.found if i.stale), key=lambda i: (i.due or date.min, i.title))

    def proposals(self) -> list[dict[str, Any]]:
        """The untracked recurring items, one per rule or title: a clock jason should have, for the board to decide.
        Past and completed items count, since they show what recurs."""
        groups: dict[str, list[PersonItem]] = {}
        for i in self.found:
            if i.kind is Kind.RECURRING and not i.retire:
                groups.setdefault(i.rule.key if i.rule else normal_title(i.title), []).append(i)
        out = []
        for key, group in groups.items():
            days = sorted({d for i in group for d in i.dates})
            first = group[0]
            out.append({"key": key, "title": first.title, "label": first.rule.label if first.rule else "",
                        "rule": first.rule.key if first.rule else "", "seen": [d.isoformat() for d in days],
                        "open": any(i.open for i in group), "sources": sorted({i.source.value for i in group}),
                        "series": any(i.series for i in group), "note": first.rule.note if first.rule else ""})
        out.sort(key=lambda p: p["seen"][-1] if p["seen"] else "", reverse=True)    # the latest seen first
        out.sort(key=lambda p: not p["open"])                                        # then the open ones first
        return out

    def as_dict(self, private: bool = False) -> dict[str, Any]:
        def proposal(p: dict[str, Any]) -> dict[str, Any]:
            shown = dict(p)
            if private:
                shown["title"] = p["label"] or "a recurring item with no rule"
                shown["key"] = p["rule"]
            return shown

        return {"asOf": self.on.isoformat(), "read": self.read, "counts": self.counts(),
                "stale": [i.row(private) for i in self.stale()],
                "proposals": [proposal(p) for p in self.proposals()],
                "retire": [i.row(private) for i in self.current if i.retire],
                "items": [i.row(private) for i in self.current], "notes": self.notes, "caveats": list(CAVEATS)}


def classify(community: Any, data_dir: Path, *, on: date | None = None, raw: dict[str, Any] | None = None) -> Reading:
    """Every person's task and event in the stored read, matched and classified. No store: an empty reading."""
    on = on or date.today()
    raw = load(data_dir) if raw is None else raw
    if raw is None:
        return Reading(on, "", [], Counter(), ["No read of Google Tasks or the calendar is on disk: jason schedule "
                                               "--read-google reads one."])
    known = Known.read(community, data_dir)
    rules = tuple(getattr(community, "people_task_rules", lambda: ())())
    found, left = items(raw, today=on, policy=known.policy)
    for i in found:
        i.match, i.rule = match_item(i.title, rules, known)
        recurs = i.series or i.repeats or bool(i.rule and i.rule.recurring)
        i.kind = (Kind.COVERED if i.match is not None and i.match.valid
                  else Kind.RECURRING if recurs else Kind.ONE_OFF)
    notes = []
    read = str(raw.get("read") or "")
    if read:
        age = (on - date.fromisoformat(read[:10])).days
        if age > STALE_READ_DAYS:
            notes.append(f"The read is {age} days old (jason schedule --read-google).")
    else:
        notes.append("The read carries no date: refresh it with jason schedule --read-google.")
    for c in raw.get("calendars") or []:
        if c.get("error"):
            notes.append(f"The calendar {c.get('id')} was not read: {c['error']}")
    if raw.get("tasks_error"):
        notes.append(f"Google Tasks was not read: {raw['tasks_error']}")
    misses = sorted({i.rule.key for i in found if i.match is not None and not i.match.valid and i.rule})
    if misses:
        notes.append(f"Rules that name something jason does not keep (read as untracked): {', '.join(misses)}.")
    return Reading(on, read, found, left, notes)


def lines(reading: Reading, *, private: bool = False, every: bool = False) -> list[str]:
    c = reading.counts()
    out = [f"As of {reading.on} (read {reading.read[:10] or '?'}): {c['open']} open ({c['openTasks']} tasks, "
           f"{c['calendarItems']} calendar items): {c['covered']} covered, {c['untracked recurring']} untracked "
           f"recurring, {c['one-off']} one-off; {c['stale']} stale (an open task past its due day); "
           f"{c['undated']} open tasks with no due day.",
           f"Left out: {', '.join(f'{n} {k}' for k, n in sorted(c['leftOut'].items())) or 'nothing'}; read for what "
           f"recurs: {c['doneTasks']} completed tasks, {c['pastEvents']} past calendar items.", ""]
    stale = reading.stale()
    out.append(f"Stale, oldest first ({len(stale)})")
    for i in stale:
        what = f"; matches {i.matched()}" if i.match else ""
        out.append(f"  {i.due}  {(reading.on - i.due).days:4} days  {i.label(private)} [{i.kind.value}{what}]"
                   + (f"; propose closing it: {i.retire}" if i.retire else ""))
    out += ["", "Untracked recurring: proposed clocks"]
    for p in reading.proposals():
        name = (p["label"] or "a recurring item with no rule") if private else p["title"]
        out.append(f"  {name} (seen {', '.join(p['seen'][-4:])}; {len(p['seen'])} days{'; open' if p['open'] else ''}"
                   f"{'; a calendar series' if p['series'] else ''})")
    retire = [i for i in reading.current if i.retire and not i.stale]
    if retire:
        out += ["", "Proposed to close"]
        out += [f"  {i.label(private)}: {i.retire}" for i in retire]
    if every:
        for kind in Kind:
            rows = [i for i in reading.current if i.kind is kind]
            out += ["", f"Open, {kind.value} ({len(rows)})"]
            for i in rows:
                what = f" [{i.matched()}; {i.match.how}]" if i.match else ""
                out.append(f"  {i.due or '-'}  {i.source.value:5} {i.label(private)}{what}")
    out += [""] + [f"* {n}" for n in reading.notes] + [f"_{c}_" for c in CAVEATS]
    return out


__all__ = ["CAVEATS", "Known", "PersonItem", "Reading", "STORE", "classify", "items", "lines", "load", "match_item",
           "read_google", "read_lines", "store_path"]
