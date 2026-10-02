"""The board calendar: the plan from disk, the diff against the calendar, and the Calendar client (MockTransport)."""

from __future__ import annotations

import json
from datetime import date, datetime

import httpx
import pytest

from jason.community import mystique
from jason.community.board_calendar import EventKind
from jason.google.calendar import GoogleCalendar
from jason.google.errors import GoogleError
from jason.tasks.board_calendar import changes, plan, policy_for, sync, sync_lines

TODAY = date(2026, 9, 29)
LINK = "https://us05web.zoom.us/j/81392024127?pwd=abc123"
ADDRESS = "123 Example Way"


def _data(tmp_path):
    zoom = tmp_path / "zoom"
    zoom.mkdir()
    (zoom / "meetings.json").write_text(json.dumps({"meetings": [
        {"meetingId": "81392024127", "kind": "board meeting", "start": "2026-09-15T18:58-07:00"},
        {"meetingId": "89999999999", "kind": "hearing", "start": "2026-09-20T18:30-07:00"}]}), encoding="utf-8")
    (zoom / "hearings.json").write_text(json.dumps({"hearings": [{
        "address": ADDRESS, "building": "2", "violation": "dog off leash", "start": "2026-10-20T18:30-07:00",
        "timezone": "America/Los_Angeles", "noticeBy": "2026-10-10", "noticeOn": None, "executiveNoticeBy": "2026-10-18",
        "decisionByIfHeld": "2026-11-03", "zoom": {"id": 1, "joinUrl": "https://zoom.us/j/111"}}]}), encoding="utf-8")
    board = tmp_path / "board"
    board.mkdir()
    (board / "agenda-2026-10-20.md").write_text(f"Join via Zoom {LINK} or https://us06web.zoom.us/j/81392024127", encoding="utf-8")
    return tmp_path


DEADLINES = [
    {"name": "Budget report to members", "authority": "Civil Code 5300", "rule": "yearly by November 1", "next": "2026-11-01"},
    {"name": "Statement of Information", "authority": "Corp 8210", "rule": "every 2 years", "next": "2027-06-30"},
    {"name": "Reviewed statement", "authority": "Civil Code 5305", "rule": "listed", "next": None},
]


def _plan(tmp_path, **kw):
    return plan(_data(tmp_path), mystique(), months=2, today=TODAY, deadline_rows=DEADLINES, **kw)


def test_the_plan_has_meetings_notices_hearing_dates_and_deadlines_in_the_window(tmp_path) -> None:
    planned = _plan(tmp_path)
    keys = [e.key for e in planned["events"]]
    assert "board-meeting:2026-10-20" in keys and "board-meeting:2026-11-17" in keys
    assert "meeting-notice:2026-10-20" in keys
    meeting = next(e for e in planned["events"] if e.key == "board-meeting:2026-10-20")
    assert meeting.summary == "Regular Meeting of the Board of Directors" and meeting.location == LINK
    assert meeting.start.hour == 19 and meeting.timezone == "America/Los_Angeles"
    november = next(e for e in planned["events"] if e.key == "board-meeting:2026-11-17")
    assert november.summary == "Meeting of the Board of Directors" and "before the board" in november.description   # the board decides regular or special
    kinds = {e.kind for e in planned["events"]}
    assert {EventKind.HEARING, EventKind.HEARING_NOTICE, EventKind.HEARING_DECISION} <= kinds
    assert [e.key for e in planned["events"] if e.kind is EventKind.DEADLINE] == ["deadline:budget-report-to-members:2026-11-01"]
    assert planned["until"] == date(2026, 11, 29)
    notice = next(e for e in planned["events"] if e.kind is EventKind.MEETING_NOTICE)
    assert notice.all_day and notice.body()["end"] == {"date": "2026-10-17"} and notice.body()["transparency"] == "transparent"


def test_a_hearing_names_no_owner_address_or_violation(tmp_path) -> None:
    planned = _plan(tmp_path)
    hearing = [e for e in planned["events"] if e.kind in (EventKind.HEARING, EventKind.HEARING_NOTICE, EventKind.HEARING_DECISION)]
    assert len(hearing) == 3 and next(e for e in hearing if e.kind is EventKind.HEARING).summary == "Board hearing"
    text = json.dumps([e.body() for e in hearing])
    assert "Example" not in text and "123" not in text and "leash" not in text
    assert next(e for e in hearing if e.kind is EventKind.HEARING).location == "https://zoom.us/j/111"


def test_the_policy_comes_from_the_specification() -> None:
    assert policy_for(mystique()).regular_title == "Regular Meeting of the Board of Directors"


def _existing(planned):
    meeting = next(e for e in planned["events"] if e.key == "board-meeting:2026-10-20").body()
    notice = next(e for e in planned["events"] if e.key == "meeting-notice:2026-10-20").body()
    return [
        {**meeting, "id": "e1", "location": "Zoom",                                    # changed: gets a patch
         "start": {"dateTime": "2026-10-21T02:00:00Z"}, "end": {"dateTime": "2026-10-21T03:30:00Z"}},
        {**notice, "id": "e2"},                                                        # the same
        {"id": "e3", "summary": "old", "start": {"date": "2026-10-01"}, "end": {"date": "2026-10-02"},
         "extendedProperties": {"private": {"jason": "deadline:gone:2026-10-01"}}},  # no longer planned
        {"id": "e4", "summary": "Regular Meeting of the Board of Directors", "recurringEventId": "r",
         "start": {"dateTime": "2026-11-17T19:00:00-08:00"}, "end": {"dateTime": "2026-11-17T20:00:00-08:00"},
         "organizer": {"email": "board@example.org"}},                                 # covers Nov 17
        {"id": "e5", "summary": "Pool service", "start": {"date": "2026-10-05"}, "end": {"date": "2026-10-06"}},
    ]


def _calendar(existing, seen):
    def handler(r: httpx.Request) -> httpx.Response:
        seen.append(r)
        if r.method == "GET" and r.url.path.endswith("/events"):
            return httpx.Response(200, json={"items": existing})
        if r.method == "POST":
            return httpx.Response(200, json={"id": "new", "htmlLink": "https://calendar.google.com/x"})
        if r.method == "PATCH":
            return httpx.Response(200, json={"id": r.url.path.rsplit("/", 1)[-1]})
        return httpx.Response(405, json={"error": {"message": "not allowed"}})
    return GoogleCalendar("tok", http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_a_dry_run_reads_and_writes_nothing(tmp_path) -> None:
    planned = _plan(tmp_path)
    seen: list[httpx.Request] = []
    result = sync(_calendar(_existing(planned), seen), "primary", planned)
    assert {r.method for r in seen} == {"GET"}
    params = seen[0].url.params
    assert params["singleEvents"] == "true" and params["orderBy"] == "startTime" and params["timeMin"].startswith("2026-09-29T00:00")
    assert [u["key"] for u in result["update"]] == ["board-meeting:2026-10-20"] and result["update"][0]["fields"] == ["location"]
    assert "meeting-notice:2026-10-20" in result["unchanged"]
    assert [c["key"] for c in result["covered"]] == ["board-meeting:2026-11-17"]
    assert [x["key"] for x in result["extra"]] == ["deadline:gone:2026-10-01"]
    assert {o["summary"] for o in result["others"]} == {"Regular Meeting of the Board of Directors", "Pool service"}
    assert "board-meeting:2026-11-17" not in [c["key"] for c in result["create"]]
    assert any("dry run" in line for line in sync_lines(result))


def test_yes_creates_and_patches_and_never_deletes(tmp_path) -> None:
    planned = _plan(tmp_path)
    seen: list[httpx.Request] = []
    result = sync(_calendar(_existing(planned), seen), "board@example.org", planned, write=True)
    posts = [r for r in seen if r.method == "POST"]
    patches = [r for r in seen if r.method == "PATCH"]
    assert len(posts) == len(result["create"]) > 0 and len(patches) == 1
    assert all(r.url.params["sendUpdates"] == "none" for r in posts + patches)
    assert "/calendars/board%40example.org/events/e1" in str(patches[0].url)
    assert json.loads(patches[0].content) == {"location": LINK}
    body = json.loads(posts[0].content)
    assert body["extendedProperties"]["private"]["jason"]
    assert not any(r.method == "DELETE" for r in seen)


def test_a_time_given_in_another_zone_is_the_same_instant(tmp_path) -> None:
    planned = _plan(tmp_path)
    meeting = next(e for e in planned["events"] if e.key == "board-meeting:2026-10-20")
    existing = {**meeting.body(), "start": {"dateTime": "2026-10-21T02:00:00Z"}, "end": {"dateTime": "2026-10-20T20:30:00-07:00"}}
    assert changes(meeting, existing) == {}


def test_the_client_pages_and_filters_by_private_property() -> None:
    seen: list[httpx.Request] = []

    def handler(r: httpx.Request) -> httpx.Response:
        seen.append(r)
        if "pageToken" in r.url.params:
            return httpx.Response(200, json={"items": [{"id": "b"}]})
        return httpx.Response(200, json={"items": [{"id": "a"}], "nextPageToken": "p2"})

    cal = GoogleCalendar("tok", http=httpx.Client(transport=httpx.MockTransport(handler)))
    got = list(cal.events("primary", time_min=datetime(2026, 10, 1), time_max=datetime(2026, 11, 1), private={"jason": "k"}))
    assert [e["id"] for e in got] == ["a", "b"]
    assert seen[0].url.params["privateExtendedProperty"] == "jason=k"
    assert seen[0].headers["Authorization"] == "Bearer tok"


def test_calendar_list_without_its_scope_is_refused_plainly() -> None:
    cal = GoogleCalendar("tok", http=httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(403, json={"error": {"message": "Insufficient Permission"}}))))
    with pytest.raises(GoogleError, match="403"):
        list(cal.calendars())


def test_the_client_takes_the_drive_token() -> None:
    class Drive:
        def _headers(self):
            return {"Authorization": "Bearer abc"}

    assert GoogleCalendar.from_drive(Drive())._token == "abc"
