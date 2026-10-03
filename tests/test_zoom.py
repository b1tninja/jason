"""Zoom: the client's token and paging, the transcript and summary readers, the sync to disk, and hearings."""

from __future__ import annotations

import base64
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from jason.community import mystique
from jason.tasks.zoom import hearings, meeting_text, meetings_brief, plan_board_meeting, plan_hearing, save_hearing, sync
from jason.zoom.client import Zoom, ZoomAuthError, ZoomCredentials, encode_uuid
from jason.zoom.models import MeetingKind, classify_meeting, notice_text, parse_vtt, summary_record, zoom_details

CREDS = ZoomCredentials("acct", "cid", "secret")
VTT = """WEBVTT

1
00:00:01.000 --> 00:00:03.000
Jane Director: Let's call the meeting to order.

2
00:00:03.500 --> 00:00:05.000
Jane Director: Roll call first.

3
00:01:10.250 --> 00:01:12.000
Sam Treasurer: The reserve balance is up.
"""
BOARD = {"uuid": "abc/+def==", "id": 81234567890, "topic": "Mystique HOA Board Meeting", "start_time": "2026-09-16T02:00:00Z",
         "duration": 75}
HEARING = {"uuid": "//hear==", "id": 89999999999, "topic": "Mystique board hearing 2026-09-01", "start_time": "2026-09-02T01:30:00Z",
           "duration": 20}


def _zoom(handler, seen: list[httpx.Request] | None = None) -> Zoom:
    def wrapped(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if request.url.host == "zoom.us":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return handler(request)

    return Zoom(CREDS, http=httpx.Client(transport=httpx.MockTransport(wrapped)))


def test_the_token_is_the_apps_credentials_and_every_call_carries_it() -> None:
    seen: list[httpx.Request] = []
    client = _zoom(lambda r: httpx.Response(200, json={"meetings": [{"id": 1}], "next_page_token": ""}), seen)
    assert [m["id"] for m in client.meetings("previous_meetings")] == [1]
    token_call, call = seen
    assert token_call.headers["authorization"] == "Basic " + base64.b64encode(b"cid:secret").decode()
    assert b"grant_type=account_credentials" in token_call.content and b"account_id=acct" in token_call.content
    assert call.headers["authorization"] == "Bearer tok" and call.url.params["type"] == "previous_meetings"


def test_a_refused_app_fails_fast() -> None:
    client = Zoom(CREDS, http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401))))
    with pytest.raises(ZoomAuthError):
        list(client.meetings())


def test_a_missing_credential_field_is_named() -> None:
    with pytest.raises(ZoomAuthError, match="client_secret"):
        ZoomCredentials.from_fields({"Account ID": "a", "client_id": "b"})
    assert ZoomCredentials.from_fields({"Account ID": "a", "Client-ID": "b", "client secret": "c"}) == ZoomCredentials("a", "b", "c")


def test_a_uuid_with_a_leading_or_double_slash_is_encoded_twice() -> None:
    assert encode_uuid("abc/+def==") == "abc%2F%2Bdef%3D%3D"
    assert encode_uuid("/abc==") == "%252Fabc%253D%253D"
    assert encode_uuid("a//b") == "a%252F%252Fb"


def test_recordings_are_asked_a_month_at_a_time() -> None:
    seen: list[httpx.Request] = []
    client = _zoom(lambda r: httpx.Response(200, json={"meetings": []}), seen)
    list(client.recordings(date(2026, 1, 1), date(2026, 3, 15)))
    windows = [(r.url.params["from"], r.url.params["to"]) for r in seen if "recordings" in r.url.path]
    assert windows == [("2026-01-01", "2026-01-30"), ("2026-01-31", "2026-03-01"), ("2026-03-02", "2026-03-15")]


def test_a_created_meeting_never_returns_the_hosts_start_link() -> None:
    seen: list[httpx.Request] = []
    created = {"id": 85550001111, "join_url": "https://us02web.zoom.us/j/85550001111?pwd=x", "password": "123456",
               "start_url": "https://us02web.zoom.us/s/85550001111?zak=secret",
               "settings": {"global_dial_in_numbers": [{"country": "US", "number": "+1 669 900 6833", "city": "San Jose"}]}}
    client = _zoom(lambda r: httpx.Response(201, json=created), seen)
    answer = client.create_meeting({"topic": "t"})
    assert "start_url" not in answer and seen[-1].method == "POST" and seen[-1].url.path == "/v2/users/me/meetings"
    details = zoom_details(answer)
    assert details["passcode"] == "123456" and details["dialIn"] == ["+1 669 900 6833 (San Jose)"]
    assert "zak" not in json.dumps(details)


def test_the_transcript_joins_a_speakers_cues() -> None:
    turns = parse_vtt(VTT)
    assert [(t.speaker, t.text) for t in turns] == [
        ("Jane Director", "Let's call the meeting to order. Roll call first."), ("Sam Treasurer", "The reserve balance is up.")]
    assert turns[1].line() == "[0:01:10] Sam Treasurer: The reserve balance is up."


def test_the_hosts_edited_summary_wins() -> None:
    body = {"summary_title": "Board", "summary_overview": "draft", "next_steps": ["zoom's"],
            "summary_details": [{"label": "Budget", "summary": "discussed"}],
            "edited_summary": {"next_steps": ["Treasurer to send the budget"]}}
    record = summary_record(body)
    assert record["nextSteps"] == ["Treasurer to send the budget"] and record["edited"] and record["details"][0]["label"] == "Budget"


@pytest.mark.parametrize("line", [
    "Okay, if no one had anything else, I guess we will adjourn to the executive session.",
    "Alright. Well, then, let's adjourn to the executive session part of the meeting. If you're not a board member, I'll kick you out.",
    "Okay, well, so we'll adjourn, adjourn the regular portion of the meeting, so that the board will meet in the executive session",
    "So if there's no one else we'll go ahead and adjourn the meeting, and the next meeting is April 15th and then board members stick around",
    "Does anyone have anything else for the open forum, and then the board we can meet at the end of this",
])
def test_the_break_is_the_chairs_adjournment_line(line) -> None:
    from jason.zoom.models import Turn, find_executive_break

    turns = [Turn(60, "Chair", "We'll talk about delinquencies in the executive session at the end."), Turn(600, "Chair", line),
             Turn(700, "Chair", "Now the delinquencies.")]
    brk = find_executive_break(turns, mystique().executive_break_patterns(), departures=[620.0, 900.0, 5000.0, 5000.0])
    assert brk.method == "adjournment" and brk.at == 600 and brk.turn == 2    # a mention is not the break
    assert (brk.departed, brk.remained) == (2, 2)


def test_without_an_adjournment_line_departures_mark_the_break_or_nothing_does() -> None:
    from jason.zoom.models import Turn, find_executive_break

    turns = [Turn(t, "Chair", "words") for t in (0, 600, 1200, 1500, 1900)]
    brk = find_executive_break(turns, (), departures=[1250.0, 1260.0, 2000.0, 2000.0])
    assert brk.method == "departures" and brk.turn == 3
    assert find_executive_break(turns, (), departures=[1900.0, 1900.0]) is None


def test_a_meeting_is_classified_by_its_topic_then_by_the_schedule() -> None:
    m = mystique()
    rules, schedule = m.zoom_meeting_rules(), m.meeting_schedule()
    tz = ZoneInfo("America/Los_Angeles")
    assert classify_meeting("Mystique Board Meeting - Executive Session", None, rules)[0] is MeetingKind.EXECUTIVE
    assert classify_meeting("Hearing: board", None, rules)[0] is MeetingKind.HEARING
    # 2026-09-15 is the third Tuesday.
    kind, why = classify_meeting("Justin's Zoom Meeting", datetime(2026, 9, 15, 19, 2, tzinfo=tz), rules, schedule)
    assert kind is MeetingKind.BOARD and "schedule" in why[0]
    assert classify_meeting("Justin's Zoom Meeting", datetime(2026, 9, 16, 19, 0, tzinfo=tz), rules, schedule)[0] is MeetingKind.OTHER


def _account(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/recordings"):
        if request.url.params["from"] > "2026-09-16" or request.url.params["to"] < "2026-09-01":
            return httpx.Response(200, json={"meetings": []})
        files = [{"file_type": "TRANSCRIPT", "download_url": "https://us02web.zoom.us/rec/download/t1"},
                 {"file_type": "MP4", "download_url": "https://us02web.zoom.us/rec/download/v1"}]
        return httpx.Response(200, json={"meetings": [{**BOARD, "recording_files": files}, {**HEARING, "recording_files": [
            {"file_type": "TRANSCRIPT", "download_url": "https://us02web.zoom.us/rec/download/t2"}]}]})
    if path.endswith("/meeting_summaries"):
        return httpx.Response(200, json={"summaries": [{"meeting_uuid": BOARD["uuid"], "meeting_topic": BOARD["topic"],
                                                        "meeting_start_time": BOARD["start_time"]}]})
    if path.endswith("/meeting_summary"):
        return httpx.Response(200, json={"summary_title": "Board", "next_steps": ["Secretary to post the minutes"]})
    if path.endswith("/users/me/meetings"):
        return httpx.Response(200, json={"meetings": [{"id": BOARD["id"]}]})
    if path.endswith("/instances"):
        return httpx.Response(200, json={"meetings": [{"uuid": BOARD["uuid"], "start_time": BOARD["start_time"]}]})
    if path.endswith("/participants"):
        return httpx.Response(200, json={"participants": [{"name": "Jane Director", "join_time": "x"}]})
    if "/past_meetings/" in path:
        return httpx.Response(200, json={"participants_count": 9})
    if "/rec/download/t" in path:
        return httpx.Response(200, text=VTT)
    return httpx.Response(404)


def test_the_sync_saves_each_meeting_and_the_brief_reads_it(tmp_path) -> None:
    seen: list[httpx.Request] = []
    counts = sync(_zoom(_account, seen), tmp_path, mystique(), since=date(2026, 8, 1), until=date(2026, 9, 29))
    assert counts["occurrences"] == 2 and counts["transcripts"] == 2 and counts["summaries"] == 1 and counts["media"] == 0
    assert not any("/rec/download/v1" in str(r.url) for r in seen)   # no video without --media
    brief = meetings_brief(tmp_path, mystique(), today=date(2026, 9, 29))
    board = next(m for m in brief["meetings"] if m["kind"] == "board meeting")
    assert board["date"] == "2026-09-15" and board["start"].startswith("2026-09-15T19:00")
    assert board["nextSteps"] == ["Secretary to post the minutes"] and board["participants"] == 9
    hearing = next(m for m in brief["meetings"] if m["kind"] == "disciplinary hearing")
    assert hearing["confidential"] and "nextSteps" not in hearing
    # August 18 is before the account's first meeting (the hearing, September 1): not a gap.
    assert brief["scheduleGaps"] == []
    text = meeting_text(tmp_path, "2026-09-15")
    assert "Sam Treasurer" in text["speakers"] and "[0:00:01] Jane Director" in text["transcript"]
    assert text["participants"] == ["Jane Director"]
    assert "transcript" not in meeting_text(tmp_path, hearing["uuid"]) and meeting_text(tmp_path, hearing["uuid"])["heldBack"]
    assert "transcript" in meeting_text(tmp_path, hearing["uuid"], include_confidential=True)
    # With the chair's adjournment in the transcript, the open portion is read and the rest is held back.
    board_row = next(r for r in json.loads((tmp_path / "zoom" / "meetings.json").read_text())["meetings"] if r["date"] == "2026-09-15")
    vtt = tmp_path / "zoom" / board_row["folder"] / "transcript.vtt"
    vtt.write_text(VTT + "\n4\n00:20:00.000 --> 00:20:05.000\nJane Director: Okay, we will adjourn to the executive session.\n\n"
                   "5\n00:21:00.000 --> 00:21:05.000\nSam Treasurer: The owner at the corner unit owes three months.\n", encoding="utf-8")
    split = meeting_text(tmp_path, "2026-09-15")
    assert split["executiveSession"]["minute"] == 20.0 and "adjourn to the executive session" in split["transcript"]
    assert "owes three months" not in split["transcript"] and "summary" not in split and "executive session from 20.0" in split["heldBack"]
    assert "owes three months" in meeting_text(tmp_path, "2026-09-15", include_confidential=True)["transcript"]
    vtt.write_text(VTT, encoding="utf-8")
    # A board meeting whose recording runs into the executive session is held back by what it says, not its topic.
    folder = tmp_path / "zoom" / next(r["folder"] for r in json.loads((tmp_path / "zoom" / "meetings.json").read_text())["meetings"]
                                      if r["date"] == "2026-09-15")
    (folder / "transcript.txt").write_text("[1:10:00] Jane Director: We now adjourn to executive session.\n", encoding="utf-8")
    assert meeting_text(tmp_path, "2026-09-15")["heldBack"].startswith("its recording mentions executive session")
    board = next(m for m in meetings_brief(tmp_path, mystique(), today=date(2026, 9, 29))["meetings"] if m["date"] == "2026-09-15")
    assert board["mentions"] == ["executive session"] and "nextSteps" not in board
    # A second sync knows the meetings and fetches no file again.
    seen.clear()
    again = sync(_zoom(_account, seen), tmp_path, mystique(), since=date(2026, 8, 1), until=date(2026, 9, 29))
    assert again["new"] == 0 and again["transcripts"] == 0 and not any("/rec/download/" in str(r.url) for r in seen)


def test_a_hearing_is_the_first_meeting_day_the_notice_can_reach(tmp_path) -> None:
    m = mystique()
    plan = plan_hearing(m, address="3030 Macon Dr", violation="Trash cans left in front of the garage", today=date(2026, 10, 8))
    # October 8 + 10 days = October 18; the next third Tuesday is October 20.
    assert plan.start.isoformat() == "2026-10-20T19:00:00-07:00" and plan.building == "1"
    assert plan.notice_by == date(2026, 10, 10) and plan.decision_by_if_held == date(2026, 11, 3)
    assert plan.executive_notice_by == date(2026, 10, 18) and not plan.problems
    body = plan.meeting_body()
    assert "3030" not in json.dumps(body) and body["settings"]["waiting_room"] and body["settings"]["auto_recording"] == "none"
    assert body["start_time"] == "2026-10-20T19:00:00" and body["timezone"] == "America/Los_Angeles"
    notice = notice_text(plan, m.name)
    assert "Trash cans" in notice and "executive session if you ask" in notice and "October 10, 2026" in notice
    record = save_hearing(tmp_path, plan, m.name)
    assert (tmp_path / "zoom" / record["notice"]).is_file()
    listed = hearings(tmp_path, today=date(2026, 10, 12))["hearings"]
    assert "no delivery is recorded" in listed[0]["standing"] and not listed[0]["scheduled"]


def test_a_late_notice_or_a_stranger_address_is_refused() -> None:
    m = mystique()
    late = plan_hearing(m, address="3030 Macon Dr", violation="x", on=date(2026, 10, 20), at="6:30 pm", notice_on=date(2026, 10, 15))
    assert late.start.hour == 18 and late.start.minute == 30
    assert late.problems and "2026-10-25" in late.problems[0]
    assert plan_hearing(m, address="3030 Macon Dr", violation=" ", on=date(2026, 11, 17)).problems
    with pytest.raises(ValueError):
        plan_hearing(m, address="1 Main St", violation="x")


def test_a_board_meeting_follows_the_profiles_policy_and_schedule() -> None:
    plan = plan_board_meeting(mystique(), today=date(2026, 10, 3))
    body = plan.meeting_body()
    assert plan.start.date() == mystique().meeting_schedule().next_meeting(date(2026, 10, 3), monthly=True)
    assert body["settings"]["auto_recording"] == "cloud" and body["settings"]["waiting_room"] is True and body["type"] == 2
    assert body["topic"].endswith(plan.start.date().isoformat()) and "start_url" not in body
    assert plan.record()["zoom"] == {} and plan.record()["date"] == plan.start.date().isoformat()
    with pytest.raises(ValueError):
        plan_board_meeting(mystique(), at="noonish")
