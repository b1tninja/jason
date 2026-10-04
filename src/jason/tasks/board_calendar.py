"""The board's Google Calendar: the meetings, notice deadlines, hearings, and recurring deadlines jason knows of.

``plan`` builds the events from what is already on disk and in the specification:

- the board's meetings for the next months, by the schedule (monthly in practice), at its hour, with the Zoom link
  the last agendas carry for the board's meeting ID;
- each meeting's notice deadline, four days before (CIV 4920(a)), all day;
- each saved disciplinary hearing (``data/zoom/hearings.json``) titled "Board hearing" with no owner or address, and
  its notice deadline (CIV 5855(a); Corp 7341(c)) and decision deadline (CIV 5855(f)), all day;
- each recurring deadline ``jason.tasks.deadlines.calendar`` gives a date in the window, all day.

Every event carries a stable key in ``extendedProperties.private.jason``. ``diff`` sets the plan beside the calendar:
an event with the key missing is created, one that differs is patched, and a keyed event jason no longer plans is
reported, never deleted. An event without a key is jason's to read only; a board meeting already on the calendar by
another invitation (the policy's ``covered_words`` on the same day) is left to it. A plan names the kinds it keeps
(``kinds``): the schedule's own events (``EventKind.SCHEDULE``, ``jason.tasks.schedule_sync``) go through the same
``sync``, and each run leaves the other's keyed events alone.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jason.community.board_calendar import BOARD_KINDS, NOTICE_DAYS, CalendarPolicy, EventKind
from jason.zoom.models import schedule_time

KEY = "jason"
ZOOM_LINK = re.compile(r"https://[a-z0-9.]*zoom\.us/j/(\d{9,11})(?:\?pwd=[A-Za-z0-9._-]+)?")
CAVEATS = (
    "The plan is what jason knows from disk: the schedule, the saved hearings, and the deadlines' evidence. A meeting the "
    "board moved or cancelled is not known until the schedule or the hearing is changed.",
    "An event without jason's key is never changed; a keyed event jason no longer plans is reported for a person to remove.",
    "A hearing's title and description name no owner and no address (Civil Code 4935).",
)


@dataclass
class PlannedEvent:
    """One event jason keeps on the calendar. ``start`` and ``end`` are a ``date`` (all day, end exclusive) or an aware
    ``datetime``."""

    key: str
    kind: EventKind
    summary: str
    start: date | datetime
    end: date | datetime
    description: str = ""
    location: str = ""
    timezone: str = ""

    @property
    def all_day(self) -> bool:
        return not isinstance(self.start, datetime)

    @property
    def day(self) -> date:
        return self.start.date() if isinstance(self.start, datetime) else self.start

    def _when(self, value: date | datetime) -> dict[str, str]:
        if isinstance(value, datetime):
            return {"dateTime": value.isoformat(), "timeZone": self.timezone}
        return {"date": value.isoformat()}

    def body(self) -> dict[str, Any]:
        """The Calendar API event: all-day events do not block time."""
        out: dict[str, Any] = {"summary": self.summary, "description": self.description, "location": self.location,
                               "start": self._when(self.start), "end": self._when(self.end),
                               "extendedProperties": {"private": {KEY: self.key}}}
        if self.all_day:
            out["transparency"] = "transparent"
        return out

    def row(self) -> dict[str, Any]:
        return {"key": self.key, "kind": self.kind.value, "summary": self.summary, "start": self.start.isoformat(),
                "end": self.end.isoformat(), "allDay": self.all_day, "location": self.location}


# --- the specification ---------------------------------------------------------------------------------------------

def policy_for(community: Any) -> CalendarPolicy:
    """The community's calendar policy: its ``calendar_policy()`` hook, else the ``board_calendar`` module beside its
    class, else the defaults."""
    hook = getattr(community, "calendar_policy", None)
    if callable(hook):
        found = hook()
        if found is not None:
            return found
    package = type(community).__module__.rpartition(".")[0]
    if package:
        try:
            return importlib.import_module(f"{package}.board_calendar").CALENDAR_POLICY
        except (ImportError, AttributeError):
            pass
    return CalendarPolicy()


def _timezone(community: Any) -> str:
    policy = community.hearing_policy() if hasattr(community, "hearing_policy") else None
    return getattr(policy, "timezone", "") or "America/Los_Angeles"


def _digest(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48]


# --- the Zoom link -------------------------------------------------------------------------------------------------

def board_zoom_link(data_dir: Path) -> str:
    """The join link for the board's usual Zoom meeting: the meeting ID of the last board meeting in
    ``data/zoom/meetings.json``, and the link with that ID the saved agendas carry (one with a passcode first)."""
    data_dir = Path(data_dir)
    index = data_dir / "zoom" / "meetings.json"
    meeting_id = ""
    if index.is_file():
        rows = json.loads(index.read_text(encoding="utf-8")).get("meetings") or []
        board = sorted((r for r in rows if r.get("kind") == "board meeting" and r.get("meetingId")), key=lambda r: r.get("start") or "")
        meeting_id = str(board[-1]["meetingId"]) if board else ""
    if not meeting_id:
        return ""
    links: list[str] = []
    for folder, pattern in ((data_dir / "board", "agenda-*.md"), (data_dir / "meetings" / "agenda-docs", "*.json")):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob(pattern)):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            links += [m.group(0) for m in ZOOM_LINK.finditer(text) if m.group(1) == meeting_id]
    if not links:
        return ""
    with_code = [link for link in links if "?pwd=" in link]
    return (with_code or links)[0]


# --- the plan ------------------------------------------------------------------------------------------------------

def board_meetings(community: Any, policy: CalendarPolicy, *, start: date, until: date, tz: str,
                   zoom_link: str = "") -> list[PlannedEvent]:
    """Each meeting in the window, and its notice deadline."""
    schedule = community.meeting_schedule()
    if schedule is None:
        return []
    from jason.tasks.board_items import notice_period

    hour = schedule_time(schedule.time) or time(19, 0)
    zone = ZoneInfo(tz)
    # The statute's four days (NOTICE_DAYS), or the governing documents' longer period (CIV 4920(b)(3)).
    days, basis = notice_period(community=community)
    days = max(days, NOTICE_DAYS)
    out: list[PlannedEvent] = []
    day = schedule.next_meeting(start - timedelta(days=1), monthly=True)
    while day <= until:
        regular = not schedule.regular_months or day.month in schedule.regular_months
        begins = datetime.combine(day, hour, tzinfo=zone)
        basis = "; ".join(t for t in (schedule.resolution, f"in practice {schedule.practice}" if schedule.practice else "") if t)
        # Whether a month outside the resolution's is a regular meeting is the board's open question
        # (meeting-schedule-resolution); the event says which months the resolution names and does not decide it.
        lines = [("Meeting of the board in a regular month" if regular else "Meeting of the board in a month the resolution "
                  "does not make regular; whether it is a regular or special meeting is before the board")
                 + (f" ({basis})." if basis else "."),
                 f"Notice and agenda to members by {day - timedelta(days=days)} ({basis})."]
        if schedule.annual_month and day.month == schedule.annual_month:
            lines.append("The annual meeting of members falls in this month.")
        if zoom_link:
            lines.append(f"Join: {zoom_link}")
        out.append(PlannedEvent(key=f"{EventKind.BOARD_MEETING.value}:{day.isoformat()}", kind=EventKind.BOARD_MEETING,
                                summary=policy.regular_title if regular else policy.special_title, start=begins,
                                end=begins + timedelta(minutes=policy.meeting_minutes), description="\n".join(lines),
                                location=zoom_link or schedule.place, timezone=tz))
        notice = day - timedelta(days=days)
        if notice >= start:
            out.append(PlannedEvent(key=f"{EventKind.MEETING_NOTICE.value}:{day.isoformat()}", kind=EventKind.MEETING_NOTICE,
                                    summary=policy.notice_title, start=notice, end=notice + timedelta(days=1),
                                    description=f"Last day to give members notice and the agenda of the {day:%B %d, %Y} "
                                                f"board meeting ({basis}; two days for a meeting solely in "
                                                f"executive session, 4920(b)(2)).",
                                    timezone=tz))
        day = schedule.next_meeting(day, monthly=True)
    return out


def hearings(data_dir: Path, community: Any, policy: CalendarPolicy, *, start: date, tz: str) -> list[PlannedEvent]:
    """Each saved hearing not yet past, with its notice and decision deadlines. The key is a digest of the address and
    start, so the calendar never carries the address."""
    path = Path(data_dir) / "zoom" / "hearings.json"
    if not path.is_file():
        return []
    hearing_policy = community.hearing_policy() if hasattr(community, "hearing_policy") else None
    minutes = getattr(hearing_policy, "duration_minutes", 30)
    out: list[PlannedEvent] = []
    for row in json.loads(path.read_text(encoding="utf-8")).get("hearings") or []:
        if not row.get("start"):
            continue
        begins = datetime.fromisoformat(row["start"])
        zone = row.get("timezone") or tz
        if begins.tzinfo is None:
            begins = begins.replace(tzinfo=ZoneInfo(zone))
        tag = _digest(str(row.get("address") or ""), row["start"])
        link = str((row.get("zoom") or {}).get("joinUrl") or "")
        if begins.date() >= start:
            lines = ["Disciplinary hearing (Civil Code 5855), held in executive session (4935).",
                     "The member is admitted from the waiting room."]
            if row.get("executiveNoticeBy"):
                lines.append(f"Members' notice of the executive session by {row['executiveNoticeBy']} (4920(b)(2)).")
            if link:
                lines.append(f"Join: {link}")
            out.append(PlannedEvent(key=f"{EventKind.HEARING.value}:{tag}", kind=EventKind.HEARING, summary=policy.hearing_title,
                                    start=begins, end=begins + timedelta(minutes=minutes), description="\n".join(lines),
                                    location=link or "Zoom", timezone=zone))
        notice_by = date.fromisoformat(row["noticeBy"]) if row.get("noticeBy") else None
        if notice_by and notice_by >= start:
            delivered = f" Delivered {row['noticeOn']}." if row.get("noticeOn") else ""
            out.append(PlannedEvent(key=f"{EventKind.HEARING_NOTICE.value}:{tag}", kind=EventKind.HEARING_NOTICE,
                                    summary=policy.hearing_notice_title, start=notice_by, end=notice_by + timedelta(days=1),
                                    description=f"Last day to deliver the notice of the {begins.date()} hearing "
                                                f"(Civil Code 5855(a); 15 days to suspend membership rights, Corp 7341(c)).{delivered}",
                                    timezone=zone))
        decision_by = date.fromisoformat(row["decisionByIfHeld"]) if row.get("decisionByIfHeld") else None
        if decision_by and decision_by >= start:
            out.append(PlannedEvent(key=f"{EventKind.HEARING_DECISION.value}:{tag}", kind=EventKind.HEARING_DECISION,
                                    summary=policy.hearing_decision_title, start=decision_by, end=decision_by + timedelta(days=1),
                                    description=f"Written notice of the board's decision on the {begins.date()} hearing is "
                                                f"due by {decision_by} (Civil Code 5855(f)).",
                                    timezone=zone))
    return out


def deadlines(rows: list[dict[str, Any]], policy: CalendarPolicy, *, start: date, until: date, tz: str) -> list[PlannedEvent]:
    """Each recurring deadline whose next date falls in the window. The key holds the name and the date, so a done
    deadline's next year is a new event and the old one stays."""
    out: list[PlannedEvent] = []
    for row in rows:
        if not row.get("next"):
            continue
        day = date.fromisoformat(row["next"])
        if not start <= day <= until:
            continue
        lines = [text for text in (row.get("authority"), row.get("rule")) if text]
        out.append(PlannedEvent(key=f"{EventKind.DEADLINE.value}:{_slug(row['name'])}:{day.isoformat()}", kind=EventKind.DEADLINE,
                                summary=f"{policy.deadline_prefix}{row['name']}", start=day, end=day + timedelta(days=1),
                                description="\n".join(lines), timezone=tz))
    return out


def plan(data_dir: Path, community: Any, *, months: int | None = None, today: date | None = None,
         deadline_rows: list[dict[str, Any]] | None = None, zoom_link: str | None = None) -> dict[str, Any]:
    """Every event jason would keep, in date order, and the window they fall in. ``deadline_rows`` defaults to
    ``jason.tasks.deadlines.calendar``'s obligations."""
    policy = policy_for(community)
    tz = _timezone(community)
    start = today or date.today()
    count = policy.months if months is None else months
    until = _add_months(start, count)
    notes: list[str] = []
    link = board_zoom_link(data_dir) if zoom_link is None else zoom_link
    if not link:
        notes.append("No Zoom link for the board's meeting was found in the saved agendas; the location is the schedule's place.")
    if deadline_rows is None:
        try:
            from jason.tasks.deadlines import calendar as deadline_calendar

            deadline_rows = deadline_calendar(Path(data_dir), community, today=start)["obligations"]
        except Exception as exc:  # the meetings and hearings still stand without the deadlines
            deadline_rows = []
            notes.append(f"The recurring deadlines were not read: {exc}")
    events = (board_meetings(community, policy, start=start, until=until, tz=tz, zoom_link=link)
              + hearings(data_dir, community, policy, start=start, tz=tz)
              + deadlines(deadline_rows, policy, start=start, until=until, tz=tz))
    events.sort(key=lambda e: (e.day, e.all_day, e.key))
    last = max([until] + [e.day for e in events])
    return {"from": start, "until": last, "timezone": tz, "events": events, "policy": policy, "notes": notes,
            "kinds": BOARD_KINDS}


def _add_months(day: date, months: int) -> date:
    from jason.tasks.deadlines import add_months

    return add_months(day, months)


# --- the calendar --------------------------------------------------------------------------------------------------

def _instant(when: dict[str, Any] | None) -> str:
    """An event time as a comparable string: the day of an all-day event, the UTC instant of a timed one."""
    when = when or {}
    if when.get("date"):
        return str(when["date"])
    stamp = str(when.get("dateTime") or "")
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return stamp
    if moment.tzinfo is None and when.get("timeZone"):
        moment = moment.replace(tzinfo=ZoneInfo(when["timeZone"]))
    return moment.astimezone(ZoneInfo("UTC")).isoformat() if moment.tzinfo else moment.isoformat()


def changes(planned: PlannedEvent, existing: dict[str, Any]) -> dict[str, Any]:
    """The fields of ``planned`` the existing event does not match, as a patch body."""
    body = planned.body()
    patch: dict[str, Any] = {}
    for name in ("summary", "description", "location"):
        if (existing.get(name) or "") != (body.get(name) or ""):
            patch[name] = body[name]
    for name in ("start", "end"):
        if _instant(existing.get(name)) != _instant(body[name]):
            patch[name] = body[name]
    if planned.all_day and existing.get("transparency") != "transparent":
        patch["transparency"] = "transparent"
    return patch


def _existing_day(event: dict[str, Any], tz: str) -> date | None:
    start = event.get("start") or {}
    if start.get("date"):
        return date.fromisoformat(start["date"])
    try:
        moment = datetime.fromisoformat(str(start.get("dateTime") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment.astimezone(ZoneInfo(tz)).date() if moment.tzinfo else moment.date()


def _shown(event: dict[str, Any]) -> dict[str, Any]:
    start = event.get("start") or {}
    return {"id": event.get("id"), "summary": event.get("summary") or "", "start": start.get("dateTime") or start.get("date"),
            "organizer": (event.get("organizer") or {}).get("email") or "", "recurring": bool(event.get("recurringEventId"))}


def diff(planned: dict[str, Any], existing: list[dict[str, Any]]) -> dict[str, Any]:
    """What to create and patch, and the keyed events jason no longer plans. The events without a key are listed;
    a planned board meeting whose day already has one with the policy's words is ``covered``."""
    policy: CalendarPolicy = planned["policy"]
    tz = planned["timezone"]
    keyed: dict[str, list[dict[str, Any]]] = {}
    others: list[dict[str, Any]] = []
    for event in existing:
        key = ((event.get("extendedProperties") or {}).get("private") or {}).get(KEY)
        if key:
            keyed.setdefault(key, []).append(event)
        elif event.get("status") != "cancelled":
            others.append(event)
    words = tuple(w.casefold() for w in policy.covered_words)
    covering: dict[date, list[dict[str, Any]]] = {}
    for event in others:
        day = _existing_day(event, tz)
        if day and any(w in str(event.get("summary") or "").casefold() for w in words):
            covering.setdefault(day, []).append(event)
    create, update, same, covered = [], [], [], []
    wanted = set()
    for event in planned["events"]:
        wanted.add(event.key)
        found = keyed.get(event.key) or []
        if not found:
            if event.kind is EventKind.BOARD_MEETING and covering.get(event.day):
                covered.append({**event.row(), "by": [_shown(e) for e in covering[event.day]]})
            else:
                create.append(event)
            continue
        patch = changes(event, found[0])
        if patch:
            update.append((event, found[0], patch))
        else:
            same.append(event)
    # A plan names the kinds it keeps (``kinds``); a keyed event of another kind belongs to another run (the board's
    # events to ``jason calendar``, the schedule's to ``jason schedule --calendar``) and is neither extra nor changed.
    kinds = {k.value if isinstance(k, EventKind) else str(k) for k in planned.get("kinds") or ()}
    ours = (lambda key: key.split(":", 1)[0] in kinds) if kinds else (lambda key: True)
    extra = [{**_shown(e), "key": key} for key, rows in keyed.items() if key not in wanted and ours(key) for e in rows]
    duplicates = [{**_shown(e), "key": key} for key, rows in keyed.items() if key in wanted for e in rows[1:]]
    elsewhere = sum(len(rows) for key, rows in keyed.items() if key not in wanted and not ours(key))
    return {"create": create, "update": update, "same": same, "covered": covered, "extra": extra,
            "duplicates": duplicates, "others": [_shown(e) for e in others], "elsewhere": elsewhere}


def window(planned: dict[str, Any]) -> tuple[datetime, datetime]:
    """The listing window: the plan's first day through the day after its last, in the association's zone."""
    zone = ZoneInfo(planned["timezone"])
    return (datetime.combine(planned["from"], time(0), tzinfo=zone),
            datetime.combine(planned["until"] + timedelta(days=1), time(0), tzinfo=zone))


def sync(calendar: Any, calendar_id: str, planned: dict[str, Any], *, write: bool = False) -> dict[str, Any]:
    """Read the calendar in the plan's window and set it beside the plan; with ``write``, create and patch."""
    low, high = window(planned)
    existing = list(calendar.events(calendar_id, time_min=low, time_max=high))
    result = diff(planned, existing)
    done: list[dict[str, Any]] = []
    if write:
        for event in result["create"]:
            made = calendar.insert(calendar_id, event.body())
            done.append({"action": "created", "key": event.key, "id": made.get("id"), "link": made.get("htmlLink")})
        for event, found, patch in result["update"]:
            calendar.patch(calendar_id, found["id"], patch)
            done.append({"action": "updated", "key": event.key, "id": found.get("id"), "fields": sorted(patch)})
    return {"calendar": calendar_id, "from": planned["from"].isoformat(), "until": planned["until"].isoformat(),
            "timezone": planned["timezone"], "written": write,
            "planned": [e.row() for e in planned["events"]],
            "create": [e.row() for e in result["create"]],
            "update": [{**e.row(), "id": found.get("id"), "fields": sorted(patch)} for e, found, patch in result["update"]],
            "unchanged": [e.key for e in result["same"]],
            "covered": result["covered"], "extra": result["extra"], "duplicates": result["duplicates"],
            "others": result["others"], "elsewhere": result["elsewhere"], "done": done, "notes": planned["notes"],
            "caveats": list(planned.get("caveats") or CAVEATS)}


def sync_lines(result: dict[str, Any]) -> list[str]:
    mode = "written" if result["written"] else "dry run; --yes writes"
    out = [f"Calendar {result['calendar']}, {result['from']} to {result['until']} ({result['timezone']}; {mode})", ""]
    out.append(f"Planned ({len(result['planned'])})")
    for e in result["planned"]:
        out.append(f"  {e['start'][:16].replace('T', ' ')}  {e['summary']}  [{e['key']}]")
    sections = (("To create", result["create"], lambda e: f"{e['start'][:16].replace('T', ' ')}  {e['summary']}"),
                ("To update", result["update"], lambda e: f"{e['start'][:16].replace('T', ' ')}  {e['summary']}: {', '.join(e['fields'])}"),
                ("Already on the calendar by another invitation", result["covered"],
                 lambda e: f"{e['start'][:10]}  {e['summary']}: {'; '.join(b['summary'] for b in e['by'])}"),
                ("jason's events no longer planned (remove in Calendar if wrong)", result["extra"],
                 lambda e: f"{str(e['start'])[:16]}  {e['summary']}  [{e['key']}]"),
                ("Duplicate keyed events", result["duplicates"], lambda e: f"{str(e['start'])[:16]}  {e['summary']}  [{e['key']}]"),
                ("Other events in the window (not jason's; read only)", result["others"],
                 lambda e: f"{str(e['start'])[:16]}  {e['summary']}" + (" (recurring)" if e["recurring"] else "")))
    for title, rows, show in sections:
        out += ["", f"{title} ({len(rows)})"] + [f"  {show(r)}" for r in rows]
    out += ["", f"Unchanged: {len(result['unchanged'])}"]
    if result.get("elsewhere"):
        out.append(f"jason's events of other kinds in the window, kept by another run: {result['elsewhere']}")
    if result["done"]:
        out += ["", "Done"] + [f"  {d['action']} {d['key']}" for d in result["done"]]
    out += [""] + [f"* {n}" for n in result["notes"]] + [f"* {c}" for c in result["caveats"]]
    return out


__all__ = ["KEY", "PlannedEvent", "board_meetings", "board_zoom_link", "changes", "deadlines", "diff", "hearings",
           "plan", "policy_for", "sync", "sync_lines", "window"]
