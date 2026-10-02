"""The schedule where people see it: each dated occurrence on the board's Google Calendar, and each open one as a Google
Task on its role's list.

**The calendar.** ``calendar_plan`` makes one all-day event per CADENCE or ANCHORED occurrence in the window (from
``past`` days back, for marking done, to ``months`` ahead), keyed ``schedule:<assignment>:<due day>`` in
``extendedProperties.private.jason``, so a re-run patches the event rather than adding a second. The plan has the board
calendar's shape (``jason.tasks.board_calendar.plan``) and goes through its ``sync``: a missing key is created, a changed
event patched, nothing deleted, and an event without jason's key never touched. The title is the policy's prefix ("Due: ",
"Done: " once a completion is recorded), the assignment's title, and its role: an office, never a person, and no address.
An occurrence the board calendar already carries on the same day (the meeting itself, its notice deadline, a recurring
deadline the assignment covers, ``CARRIED_BY``) is left to ``jason calendar`` and not added twice.

**Google Tasks.** ``sync_tasks`` keeps one list per role (``Schedule: <role>``) in the signed-in account. Each open
occurrence in the window is a task with its due day and jason's marker (``jason:schedule:<assignment>:<due day>``) in its
notes; an occurrence recorded done completes its task. A task a person checks off in Google is recorded back as a
completion in ``data/schedule/done.jsonl``: done on the day Google says it was completed, by ``Google Tasks`` (the Tasks
API names neither the account nor who checked it off), with the evidence "checked off in Google Tasks on DATE". That is
weaker evidence than the minutes: it says someone with the account marked it, not that the duty was met. A task jason
no longer plans is reported, never deleted. A dry run (``write=False``) reads and changes nothing, and creates no list.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jason.community.board_calendar import CalendarPolicy, EventKind
from jason.community.schedule import Adoption, Assignment, Role, assignments
from jason.tasks.board_calendar import PlannedEvent, _slug, _timezone, policy_for
from jason.tasks.schedule import Occurrence, agenda, completions, record_done

MONTHS = 3                              # how far ahead, by default
PAST_DAYS = 30                          # how far back, so an occurrence done since the last run is marked done
LIST_PREFIX = "Schedule: "              # one Google Tasks list per role: "Schedule: treasurer"
MARKER_KIND = EventKind.SCHEDULE.value  # the calendar key's and the task marker's first part
TASKS_BY = "Google Tasks"

# What the board calendar's own events stand for, by the duty references the law gives them: an occurrence of an
# assignment covering one of these, on the day such an event falls, is already on the calendar (``jason calendar``).
CARRIED_BY: dict[EventKind, tuple[str, ...]] = {
    EventKind.BOARD_MEETING: ("CIV 4900",),                         # the meeting itself (the Open Meeting Act)
    EventKind.MEETING_NOTICE: ("CIV 4920", "notice:board-meeting"),  # its notice and agenda, four days before
}

CAVEATS = (
    "The plan is the schedule's assignments, proposed until the board adopts them, and the completions recorded in jason.",
    "An event or task without jason's key is never changed; one jason no longer plans is reported for a person to remove.",
    "Titles name the assignment and its role (an office), never a person or an address.",
)


def key_of(a: Assignment, due: date) -> str:
    """The stable key of one occurrence: the calendar event's private key and the task's marker."""
    return f"{MARKER_KIND}:{a.key}:{due.isoformat()}"


def parse_key(key: str) -> tuple[str, date] | None:
    """(assignment key, due day) from ``schedule:<key>:<due>``, or None for another kind's key."""
    kind, _, rest = key.partition(":")
    assignment, _, due = rest.rpartition(":")
    if kind != MARKER_KIND or not assignment:
        return None
    try:
        return assignment, date.fromisoformat(due)
    except ValueError:
        return None


def window(today: date, *, months: int = MONTHS, past: int = PAST_DAYS) -> tuple[date, date]:
    from jason.tasks.deadlines import add_months

    return today - timedelta(days=past), add_months(today, months)


def _owner(a: Assignment) -> str:
    return f"the {a.role.value}" + (f" (backup: the {a.backup.value})" if a.backup else "")


def _adoption(a: Assignment) -> str:
    if a.adoption is Adoption.ADOPTED:
        return f"Adopted by the board{': ' + a.adopted if a.adopted else ''}."
    return "Proposed by jason; the board has not adopted this assignment."


def _about(o: Occurrence) -> list[str]:
    a = o.assignment
    lines = [f"Owner: {_owner(a)}.", f"When: {a.cadence()}; this one is due {o.due.isoformat()}.", _adoption(a)]
    if a.evidence:
        lines.append(f"What shows it done: {a.evidence}.")
    if a.jason:
        lines.append(f"Command: {a.jason}")      # never "jason:", the task marker's prefix (``marker_of``)
    if a.note:
        lines.append(a.note)
    return [("- " + line) if line.startswith("jason:") else line for line in lines]


def _record_line(o: Occurrence) -> str:
    """How an occurrence is recorded done, or that it was. The record's ``by`` may be a person: it stays in jason."""
    if o.done:
        return f"Recorded done on {o.done.get('done')} (jason schedule)."
    return (f"When it is done: jason schedule --done {o.assignment.key} {o.due.isoformat()} --by NAME --evidence TEXT, "
            f"or check off its task in Google Tasks.")


# --- the calendar --------------------------------------------------------------------------------------------------

def event_for(o: Occurrence, policy: CalendarPolicy, tz: str) -> PlannedEvent:
    a = o.assignment
    prefix = policy.schedule_done_prefix if o.standing == "done" else policy.schedule_prefix
    return PlannedEvent(key=key_of(a, o.due), kind=EventKind.SCHEDULE, summary=f"{prefix}{a.title} ({a.role.value})",
                        start=o.due, end=o.due + timedelta(days=1),
                        description="\n".join(_about(o) + [_record_line(o), f"Assignment: {a.key}"]), timezone=tz)


def carried(a: Assignment, due: date, board_events: list[PlannedEvent]) -> str:
    """The key of the board calendar's event that already stands for this occurrence, or ""."""
    obligations = {_slug(c.split(":", 1)[1]) for c in a.covers if c.startswith("obligation:")}
    for event in board_events:
        if event.day != due:
            continue
        if any(a.covers_ref(ref) for ref in CARRIED_BY.get(event.kind, ())):
            return event.key
        if event.kind is EventKind.DEADLINE and event.key.split(":")[1] in obligations:
            return event.key
    return ""


def calendar_plan(data_dir: Path, community: Any, *, months: int = MONTHS, past: int = PAST_DAYS,
                  today: date | None = None, board: dict[str, Any] | None = None) -> dict[str, Any]:
    """The schedule's events in the window, in the board calendar's plan shape (``board_calendar.sync`` takes it).
    ``board`` is the board calendar's plan from the window's first day; it defaults to ``board_calendar.plan``."""
    from jason.tasks.board_calendar import plan as board_plan

    today = today or date.today()
    start, until = window(today, months=months, past=past)
    policy = policy_for(community)
    tz = _timezone(community)
    notes: list[str] = []
    if board is None:
        board = board_plan(Path(data_dir), community, months=months + past // 28 + 1, today=start)
    board_events = [e for e in board.get("events") or [] if e.kind is not EventKind.SCHEDULE]
    events: list[PlannedEvent] = []
    left: list[dict[str, str]] = []
    for o in agenda(community, Path(data_dir), start=start, end=until, today=today):
        by = carried(o.assignment, o.due, board_events)
        if by:
            left.append({"key": key_of(o.assignment, o.due), "title": o.assignment.title, "on": by})
            continue
        events.append(event_for(o, policy, tz))
    events.sort(key=lambda e: (e.day, e.key))
    if left:
        notes.append(f"{len(left)} occurrences are the board calendar's own events on the same day, kept by `jason "
                     "calendar` (run it with --yes too, or they are on no calendar): "
                     + "; ".join(f"{r['key']} as {r['on']}" for r in left))
    return {"from": start, "until": until, "timezone": tz, "events": events, "policy": policy, "notes": notes,
            "kinds": frozenset({EventKind.SCHEDULE}), "carried": left, "caveats": list(CAVEATS)}


# --- Google Tasks --------------------------------------------------------------------------------------------------

def list_title(role: Role) -> str:
    return f"{LIST_PREFIX}{role.value}"


@dataclass
class PlannedTask:
    key: str                     # schedule:<assignment>:<due>
    role: Role
    due: date
    done: bool
    body: dict[str, Any]

    @property
    def list_title(self) -> str:
        return list_title(self.role)

    def row(self) -> dict[str, Any]:
        return {"key": self.key, "list": self.list_title, "title": self.body["title"], "due": self.due.isoformat(),
                "done": self.done}


def task_for(o: Occurrence) -> PlannedTask:
    from jason.google.tasks import MARKER

    a = o.assignment
    notes = _about(o) + [_record_line(o) if o.done else
                         "Check this off when it is done: jason records it at its next run (weaker evidence than the "
                         "minutes; record the evidence too with jason schedule --done).",
                         f"{MARKER}{key_of(a, o.due)}"]
    body = {"title": a.title, "notes": "\n".join(notes), "status": "completed" if o.done else "needsAction",
            "due": f"{o.due.isoformat()}T00:00:00.000Z"}
    return PlannedTask(key_of(a, o.due), a.role, o.due, bool(o.done), body)


def _completed_on(task: dict[str, Any], tz: str, today: date) -> date:
    stamp = str(task.get("completed") or "")
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return today
    return moment.astimezone(ZoneInfo(tz)).date() if moment.tzinfo else moment.date()


def _existing(tasks: Any) -> tuple[dict[str, str], dict[str, list[tuple[str, dict[str, Any]]]]]:
    """The schedule's lists already in the account ({title: id}) and jason's schedule tasks on them, by marker."""
    from jason.google.tasks import marker_of

    lists = {str(tl.get("title")): str(tl["id"]) for tl in tasks.task_lists()
             if str(tl.get("title") or "").startswith(LIST_PREFIX)}
    found: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for title, list_id in lists.items():
        for task in tasks.tasks(list_id):
            marker = marker_of(task)
            if parse_key(marker):
                found.setdefault(marker, []).append((title, task))
    return lists, found


def _changes(body: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for name, value in body.items():
        have = str(task.get(name) or "")
        if (have[:10] != value[:10]) if name == "due" else (have != value):
            out[name] = value
    return out


def sync_tasks(tasks: Any, data_dir: Path, community: Any, *, months: int = MONTHS, past: int = PAST_DAYS,
               today: date | None = None, write: bool = False) -> dict[str, Any]:
    """Read the schedule's lists, record what was checked off there, and set each open occurrence beside its task.
    With ``write``, record the completions, create the missing lists and tasks, and patch the changed ones."""
    today = today or date.today()
    start, until = window(today, months=months, past=past)
    tz = _timezone(community)
    known = {a.key for a in assignments(community)}
    lists, found = _existing(tasks)
    recorded = {(r["key"], r["due"]) for r in completions(Path(data_dir))}
    checked: list[dict[str, Any]] = []
    for marker, places in sorted(found.items()):
        key, due = parse_key(marker) or ("", today)
        if key not in known or (key, due.isoformat()) in recorded:
            continue
        done = [(title, t) for title, t in places if t.get("status") == "completed"]
        if not done:
            continue
        title, task = done[0]
        on = _completed_on(task, tz, today)
        checked.append({"key": key, "due": due.isoformat(), "done": on.isoformat(), "by": TASKS_BY,
                        "evidence": f"checked off in Google Tasks on {on.isoformat()} ({title})"})
    if write:
        for row in checked:
            record_done(Path(data_dir), row["key"], date.fromisoformat(row["due"]), date.fromisoformat(row["done"]),
                        row["by"], row["evidence"])
    occurrences = agenda(community, Path(data_dir), start=start, end=until, today=today)
    pending = {(r["key"], r["due"]): r for r in checked}       # a dry run shows them done all the same
    planned = [task_for(o if o.done or (o.assignment.key, o.due.isoformat()) not in pending else
                        Occurrence(o.assignment, o.due, "done", pending[(o.assignment.key, o.due.isoformat())]))
               for o in occurrences]
    create, update, same, elsewhere, done = [], [], [], [], []
    wanted = set()
    for p in planned:
        wanted.add(p.key)
        places = found.get(p.key) or []
        if not places:
            if not p.done:
                create.append(p)
            continue
        title, task = places[0]
        if title != p.list_title:
            elsewhere.append({**p.row(), "on": title})
        patch = _changes(p.body, task)
        if patch:
            update.append((p, title, task, patch))
        else:
            same.append(p)
    if write:
        for p in create:
            list_id = lists.get(p.list_title) or tasks.task_list(p.list_title)
            lists[p.list_title] = list_id
            made = tasks.insert(list_id, p.body)
            done.append({"action": "created", "key": p.key, "list": p.list_title, "id": made.get("id")})
        for p, title, task, patch in update:
            tasks.patch(lists[title], task["id"], patch)
            done.append({"action": "updated", "key": p.key, "list": title, "fields": sorted(patch)})
    stale, before = [], []
    for marker, places in sorted(found.items()):
        if marker in wanted:
            continue
        key, due = parse_key(marker) or ("", today)
        for title, task in places:
            row = {"key": marker, "list": title, "title": task.get("title") or "", "status": task.get("status") or ""}
            (before if due < start else stale).append(row)
    duplicates = [{"key": m, "lists": [t for t, _ in places[1:]]} for m, places in sorted(found.items()) if len(places) > 1]
    return {"from": start.isoformat(), "until": until.isoformat(), "written": write,
            "lists": sorted({p.list_title for p in planned if not p.done} | set(lists)),
            "missingLists": sorted({p.list_title for p in create} - set(lists)) if not write else [],
            "planned": [p.row() for p in planned], "checkedOff": checked,
            "create": [p.row() for p in create],
            "update": [{**p.row(), "list": title, "fields": sorted(patch)} for p, title, _, patch in update],
            "unchanged": [p.key for p in same], "elsewhere": elsewhere,
            "stale": [r for r in stale if r["status"] != "completed"],
            "beforeWindow": [r for r in before if r["status"] != "completed"],
            "duplicates": duplicates, "done": done, "caveats": list(CAVEATS) + [
                "A task checked off is recorded by 'Google Tasks': weaker evidence than the minutes, since Google "
                "reports neither the account nor who checked it off."]}


def task_plan(data_dir: Path, community: Any, *, months: int = MONTHS, past: int = PAST_DAYS,
              today: date | None = None) -> list[PlannedTask]:
    """The tasks from disk alone, with no Google call: each open occurrence in the window."""
    today = today or date.today()
    start, until = window(today, months=months, past=past)
    return [task_for(o) for o in agenda(community, Path(data_dir), start=start, end=until, today=today) if not o.done]


def tasks_lines(result: dict[str, Any]) -> list[str]:
    mode = "written" if result["written"] else "dry run; --yes writes"
    out = [f"Google Tasks, one list per role ({', '.join(result['lists']) or 'none yet'}), {result['from']} to "
           f"{result['until']} ({mode})", ""]
    if result["missingLists"]:
        out.append(f"Lists to create: {', '.join(result['missingLists'])}")
    sections = (
        ("Checked off in Google Tasks, to record as done", result["checkedOff"],
         lambda r: f"{r['due']}  {r['key']}: {r['evidence']}"),
        ("To create", result["create"], lambda r: f"{r['due']}  [{r['list']}] {r['title']}"),
        ("To update", result["update"], lambda r: f"{r['due']}  [{r['list']}] {r['title']}: {', '.join(r['fields'])}"),
        ("On another role's list (left there; move it by hand if wrong)", result["elsewhere"],
         lambda r: f"{r['due']}  {r['title']}: on {r['on']}, owned by {r['list']}"),
        ("jason's tasks no longer planned, still open (remove in Tasks if wrong)", result["stale"],
         lambda r: f"[{r['list']}] {r['title']}  [{r['key']}]"),
        ("Open tasks due before the window (still open in Google)", result["beforeWindow"],
         lambda r: f"[{r['list']}] {r['title']}  [{r['key']}]"),
        ("Duplicate tasks", result["duplicates"], lambda r: f"{r['key']}: also on {', '.join(r['lists'])}"),
    )
    for title, rows, show in sections:
        out += ["", f"{title} ({len(rows)})"] + [f"  {show(r)}" for r in rows]
    out += ["", f"Unchanged: {len(result['unchanged'])}"]
    if result["done"]:
        out += ["", "Done"] + [f"  {d['action']} {d['key']} ({d['list']})" for d in result["done"]]
    out += [""] + [f"* {c}" for c in result["caveats"]]
    return out


__all__ = ["CARRIED_BY", "LIST_PREFIX", "MONTHS", "PAST_DAYS", "PlannedTask", "TASKS_BY", "calendar_plan", "carried",
           "event_for", "key_of", "list_title", "parse_key", "sync_tasks", "task_for", "task_plan", "tasks_lines",
           "window"]
