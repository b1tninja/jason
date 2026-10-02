"""The schedule on Google: the calendar plan and its keys, the sync beside the board calendar's events, and the Tasks
lists by role, with a task checked off recorded back as a completion (fake Google clients)."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.base import MeetingSchedule
from jason.community.board_calendar import EventKind
from jason.community.schedule import Anchor, Assignment, Role, Trigger
from jason.google.errors import GoogleAuthRequired
from jason.google.tasks import marker_of
from jason.tasks import schedule as task
from jason.tasks import schedule_sync as sync
from jason.tasks.board_calendar import diff, plan as board_plan, sync as calendar_sync, sync_lines

TODAY = date(2026, 10, 2)
ROWS = (
    Assignment("review", "The monthly financial review", Role.TREASURER, ("CIV 5500",), Trigger.ANCHORED,
               anchor=Anchor.BOARD_MEETING, evidence="the minutes", backup=Role.BOARD),
    Assignment("notice", "Notice and agenda of each board meeting", Role.SECRETARY, ("CIV 4920",), Trigger.ANCHORED,
               anchor=Anchor.BOARD_MEETING, offset_days=-4),
    Assignment("meetings", "The board's meetings", Role.BOARD, ("CIV 4900",), Trigger.ANCHORED,
               anchor=Anchor.BOARD_MEETING),
    Assignment("filing", "The example filing", Role.SECRETARY, ("obligation:Example filing",), Trigger.CADENCE,
               every_months=12, month=10, day=1),
    Assignment("yearly", "The yearly example report", Role.SECRETARY, ("bylaws#9.9",), Trigger.CADENCE,
               every_months=12, month=12, day=1, jason="jason report example"),
    Assignment("requests", "Records requests", Role.SECRETARY, ("CIV 5205",), Trigger.EVENT, handled_by="x"),
)


def _community():
    return SimpleNamespace(assignments=lambda: ROWS, fiscal_year_end=lambda: (12, 31),
                           meeting_schedule=lambda: MeetingSchedule(1, 3, "7:00 pm", "Zoom", annual_month=11))


def _board(tmp_path, community):
    start, _ = sync.window(TODAY)
    return board_plan(tmp_path, community, months=5, today=start, zoom_link="",
                      deadline_rows=[{"name": "Example filing", "next": "2026-10-01"}])


def _plan(tmp_path):
    c = _community()
    return sync.calendar_plan(tmp_path, c, today=TODAY, board=_board(tmp_path, c))


def test_keys_are_stable_per_assignment_and_due_day() -> None:
    key = sync.key_of(ROWS[0], date(2026, 10, 20))
    assert key == "schedule:review:2026-10-20" and sync.parse_key(key) == ("review", date(2026, 10, 20))
    assert sync.parse_key("board-meeting:2026-10-20") is None and sync.parse_key("schedule:x:soon") is None


def test_the_calendar_plan_skips_what_the_board_calendar_carries(tmp_path) -> None:
    planned = _plan(tmp_path)
    assert planned["from"] == date(2026, 9, 2) and planned["until"] == date(2027, 1, 2)
    assert [e.key for e in planned["events"]] == [
        "schedule:review:2026-09-15", "schedule:review:2026-10-20", "schedule:review:2026-11-17",
        "schedule:yearly:2026-12-01", "schedule:review:2026-12-15"]
    # the meeting itself, its notice deadline, and the obligation's deadline are the board calendar's own events
    on = {r["key"]: r["on"] for r in planned["carried"]}
    assert on["schedule:notice:2026-10-16"] == "meeting-notice:2026-10-20"
    assert on["schedule:meetings:2026-10-20"] == "board-meeting:2026-10-20"
    assert on["schedule:filing:2026-10-01"] == "deadline:example-filing:2026-10-01"
    event = planned["events"][1]
    assert event.kind is EventKind.SCHEDULE and event.all_day
    assert event.summary == "Due: The monthly financial review (treasurer)"
    body = event.body()
    assert body["start"] == {"date": "2026-10-20"} and body["end"] == {"date": "2026-10-21"}
    assert body["extendedProperties"]["private"]["jason"] == "schedule:review:2026-10-20"
    assert body["transparency"] == "transparent"
    assert "backup: the board" in body["description"] and "jason schedule --done review 2026-10-20" in body["description"]
    assert "not adopted" in body["description"]


def test_an_occurrence_recorded_done_is_marked_done_without_the_name(tmp_path) -> None:
    task.record_done(tmp_path, "review", date(2026, 9, 15), date(2026, 9, 16), "A Person", "minutes 2026-09-15 item 4")
    event = next(e for e in _plan(tmp_path)["events"] if e.key == "schedule:review:2026-09-15")
    assert event.summary == "Done: The monthly financial review (treasurer)"
    assert "Recorded done on 2026-09-16" in event.description and "A Person" not in json.dumps(event.body())


class _Calendar:
    def __init__(self, items):
        self.items, self.inserted, self.patched = list(items), [], []

    def events(self, calendar_id, *, time_min, time_max):
        return self.items

    def insert(self, calendar_id, body):
        self.inserted.append(body)
        return {"id": f"n{len(self.inserted)}"}

    def patch(self, calendar_id, event_id, body):
        self.patched.append((event_id, body))
        return {"id": event_id}


def _keyed(key, summary, day):
    return {"id": key, "summary": summary, "start": {"date": day}, "end": {"date": day},
            "extendedProperties": {"private": {"jason": key}}}


def test_the_sync_keeps_to_its_own_kind_and_never_deletes(tmp_path) -> None:
    planned = _plan(tmp_path)
    review = next(e for e in planned["events"] if e.key == "schedule:review:2026-10-20")
    existing = [{**review.body(), "id": "r1", "summary": "Due: old title"},
                _keyed("board-meeting:2026-10-20", "Regular Meeting", "2026-10-20"),
                _keyed("schedule:gone:2026-10-05", "Due: gone", "2026-10-05")]
    fake = _Calendar(existing)
    dry = calendar_sync(fake, "primary", planned)
    assert not fake.inserted and not fake.patched
    assert [u["key"] for u in dry["update"]] == ["schedule:review:2026-10-20"] and dry["update"][0]["fields"] == ["summary"]
    assert [x["key"] for x in dry["extra"]] == ["schedule:gone:2026-10-05"]    # the board's event is not the schedule's
    assert dry["elsewhere"] == 1 and len(dry["create"]) == 4
    assert any("other kinds" in line for line in sync_lines(dry))
    written = calendar_sync(fake, "primary", planned, write=True)
    assert len(fake.inserted) == 4 and fake.patched == [("r1", {"summary": review.summary})]
    assert {d["action"] for d in written["done"]} == {"created", "updated"}
    # jason calendar, in turn, reads the schedule's events as another run's, not as its own stale ones
    board = diff(_board(tmp_path, _community()), existing)
    assert board["extra"] == [] and board["elsewhere"] == 2


class _Tasks:
    def __init__(self):
        self.lists: dict[str, str] = {}
        self.items: dict[str, list[dict]] = {}
        self.inserted, self.patched = [], []

    def task_lists(self):
        return [{"id": i, "title": t} for t, i in self.lists.items()]

    def task_list(self, title):
        if title not in self.lists:
            self.lists[title] = f"L{len(self.lists)}"
            self.items[self.lists[title]] = []
        return self.lists[title]

    def tasks(self, list_id):
        return self.items.get(list_id, [])

    def insert(self, list_id, body):
        made = {"id": f"T{len(self.inserted)}", **body}
        self.inserted.append(body)
        self.items[list_id].append(made)
        return made

    def patch(self, list_id, task_id, body):
        self.patched.append((task_id, body))
        next(t for t in self.items[list_id] if t["id"] == task_id).update(body)
        return body


def _task(fake, key):
    return next(t for rows in fake.items.values() for t in rows if marker_of(t) == key)


def test_tasks_by_role_and_a_check_off_recorded_back(tmp_path) -> None:
    c, fake = _community(), _Tasks()
    dry = sync.sync_tasks(fake, tmp_path, c, today=TODAY)
    assert not fake.lists and not fake.inserted                      # a dry run creates no list and no task
    assert dry["missingLists"] == ["Schedule: board", "Schedule: secretary", "Schedule: treasurer"]
    assert len(dry["create"]) == 14                                   # every open dated occurrence; no event-driven ones
    sync.sync_tasks(fake, tmp_path, c, today=TODAY, write=True)
    assert sorted(fake.lists) == dry["missingLists"] and len(fake.inserted) == 14
    review = _task(fake, "schedule:review:2026-10-20")
    assert review in fake.items[fake.lists["Schedule: treasurer"]]
    assert review["title"] == "The monthly financial review" and review["due"] == "2026-10-20T00:00:00.000Z"
    assert review["status"] == "needsAction" and "weaker evidence than the minutes" in review["notes"]
    # the assignment's command is not read as jason's marker ("jason:"), so a re-run finds the task, not a new one
    assert "Command: jason report example" in _task(fake, "schedule:yearly:2026-12-01")["notes"]

    # A person checks the review off in Google Tasks (at 8 pm in the association's zone); a stray task is reported.
    review.update(status="completed", completed="2026-10-21T03:00:00.000Z")
    fake.items[fake.lists["Schedule: board"]].append({"id": "X", "title": "gone", "status": "needsAction",
                                                      "notes": "jason:schedule:gone:2026-10-05"})
    again = sync.sync_tasks(fake, tmp_path, c, today=TODAY)
    assert again["checkedOff"] == [{"key": "review", "due": "2026-10-20", "done": "2026-10-20", "by": "Google Tasks",
                                    "evidence": "checked off in Google Tasks on 2026-10-20 (Schedule: treasurer)"}]
    assert task.completions(tmp_path) == [] and not fake.patched     # the dry run records nothing
    assert [r["key"] for r in again["stale"]] == ["schedule:gone:2026-10-05"]
    assert all(u["key"] != "schedule:review:2026-10-20" or "status" not in u["fields"] for u in again["update"])

    sync.sync_tasks(fake, tmp_path, c, today=TODAY, write=True)
    [done] = task.completions(tmp_path)
    assert (done["key"], done["due"], done["done"], done["by"]) == ("review", "2026-10-20", "2026-10-20", "Google Tasks")
    assert review["status"] == "completed" and "Recorded done on 2026-10-20" in review["notes"]
    found = task.agenda(c, tmp_path, start=date(2026, 10, 20), end=date(2026, 10, 20), today=TODAY)
    assert {o.assignment.key: o.standing for o in found}["review"] == "done"

    # A completion recorded in jason completes its task at the next run; nothing is ever deleted.
    task.record_done(tmp_path, "notice", date(2026, 10, 16), date(2026, 10, 15), "the secretary", "posting proof")
    third = sync.sync_tasks(fake, tmp_path, c, today=TODAY, write=True)
    assert _task(fake, "schedule:notice:2026-10-16")["status"] == "completed"
    assert third["checkedOff"] == [] and len(fake.inserted) == 14
    assert any("weaker evidence" in line for line in sync.tasks_lines(third))


def test_the_command_plans_from_disk_and_fails_fast_without_google(tmp_path, monkeypatch, capsys) -> None:
    import jason.community as community_module
    from jason.cli import build_parser
    from jason.commands import schedule as command

    monkeypatch.setattr(community_module, "community", _community)
    monkeypatch.setattr(command, "_data_dir", lambda args: tmp_path)
    monkeypatch.setattr(sync, "calendar_plan", lambda data_dir, c, **kw: {
        "from": date(2026, 9, 2), "until": date(2027, 1, 2), "events": [], "notes": []})
    args = build_parser().parse_args(["schedule", "--tasks", "--calendar", "--plan-only"])
    called = []
    args.agent_factory = lambda a: called.append(a)
    assert command.cmd_schedule(args) == 0 and not called
    out = capsys.readouterr().out
    assert "Google Tasks: 14 open occurrences" in out and "[Schedule: treasurer] The monthly financial review" in out

    class Agent:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def google_tasks(self):
            raise GoogleAuthRequired("Google sign-in needs a browser. Pass interactive=True.")

    args = build_parser().parse_args(["schedule", "--tasks"])
    assert args.yes is False and args.interactive is False
    args.agent_factory = lambda a: Agent()
    with pytest.raises(GoogleAuthRequired):
        command.cmd_schedule(args)
