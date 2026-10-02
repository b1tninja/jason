"""The meeting catalog: file names to record kinds and dates, and the per-meeting checks."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date

import pytest

from jason.community import mystique
from jason.community.meeting_records import RecordKind, meeting_date, record_kind
from jason.tasks.meeting_catalog import build, meeting, write

M = mystique()


@pytest.mark.parametrize("name,path,expected", [
    ("Minutes of 6_17_25.pdf", "", date(2025, 6, 17)),
    ("Agenda for 9/15/26", "", date(2026, 9, 15)),
    ("GMT20250521-015946_Recording.m4a", "", date(2025, 5, 20)),          # 01:59 UTC is the evening before in Sacramento
    ("Disciplinary Hearing's transcript Apr 14, 2026 07:16 PM.txt", "", date(2026, 4, 14)),
    ("Mystique - 230130 - Open Meeting Minutes.pdf", "", date(2023, 1, 30)),
    ("Mystique DRAFT Meeting Minutes 2022.05.11.pdf", "", date(2022, 5, 11)),
    ("Meeting Summary 26-02-17", "", date(2026, 2, 17)),
    ("proof of notice of meeting 083022.pdf", "", date(2022, 8, 30)),
    ("Emergency Meeting Minutes 72922.pdf", "", date(2022, 7, 29)),
    ("Minutes of 2024 Annual Membership Meeting.pdf", "", date(2024, 11, 19)),
    ("DRAFT Minutes.pdf", "Meetings/2024/0206/DRAFT Minutes.pdf", date(2024, 2, 6)),
    ("Regular Meeting of the Board of Directors's transcript (1).txt", "", None),
])
def test_a_meeting_date_is_read_from_the_name(name, path, expected) -> None:
    assert meeting_date(name, path, schedule=M.meeting_schedule()) == expected


@pytest.mark.parametrize("name,path,kind", [
    ("Executive Session Agenda - 5/16/23", "My Drive", RecordKind.EXECUTIVE_AGENDA),
    ("Mystique - 231017 - DRAFT Open Minutes.pdf", "My Drive", RecordKind.DRAFT_MINUTES),
    ("Minutes of 7/15/25", "My Drive", RecordKind.MINUTES),
    ("GMT20250618-020153_Recording.transcript.vtt", "My Drive", RecordKind.TRANSCRIPT),
    ("GMT20250618-020153_RecordingnewChat.txt", "My Drive", RecordKind.CHAT),
    ("GMT20250618-020153_Recording_3840x2100.mp4", "My Drive", RecordKind.VIDEO),
    ("2021-03-10 17-33-20.mp3", "My Drive/Meetings/2021", RecordKind.AUDIO),
    ("1000001779.mp4", "My Drive/Disciplinary", None),                       # evidence, not a meeting
])
def test_a_file_is_named_by_the_rules_in_order(name, path, kind) -> None:
    assert record_kind(name, path, M.meeting_record_rules()) is kind


class FakePayhoa:
    def __init__(self, rows):
        self.rows = rows

    def iter_communications(self, org_id, *, search=""):
        return iter([r for r in self.rows if search.lower() in r["subject"].lower()])


def _comm(i, status, sent="2026-03-17T20:29:00.000000Z", subject="Regular Meeting of the Board of Directors - March 19th at 7:00 pm"):
    return {"activityId": i, "subject": subject, "sentAt": sent, "type": "email", "category": "In-Group Communication",
            "senderName": "Secretary", "status": status, "recipientName": f"Owner {i}", "recipientEmail": f"o{i}@example.com",
            "fileAttachments": []}


def test_payhoa_notices_are_one_row_per_mailing_with_no_member_details_and_a_late_one_is_flagged(tmp_path) -> None:
    from jason.tasks.meeting_catalog import sync_communications

    rows = [_comm(1, "opened"), _comm(2, "delivered"), _comm(3, "failed"), _comm(3, "failed")]   # the last repeats under another term
    assert sync_communications(FakePayhoa(rows), 1, tmp_path, M) == {"rows": 3, "mailings": 1}
    stored = (tmp_path / "payhoa" / "communications.json").read_text(encoding="utf-8")
    assert "example.com" not in stored and "Owner" not in stored
    catalog = build(tmp_path, M, today=date(2026, 9, 29))
    march = next(m for m in catalog["meetings"] if m["date"] == "2026-03-19")
    assert march["has"]["meeting notice"] == {"PayHOA communication": 1}
    assert any("2 days before the meeting" in c and "CIV 4920(a)" in c for c in march["checks"])
    assert any("failed or bounced for 1" in c for c in march["checks"])


def test_same_bytes_in_two_places_are_one_document() -> None:
    from jason.community.meeting_records import MeetingRecord, Where
    from jason.tasks.meeting_catalog import same_file

    recs = [MeetingRecord(RecordKind.AGENDA, Where.GMAIL, "Agenda for 9_15_26.pdf", "gmail/files/a.pdf", md5="m1", sha256="s1"),
            MeetingRecord(RecordKind.AGENDA, Where.PAYHOA, "Agenda for 9_15_26.pdf", "Email Attachments/a.pdf", sha256="s1"),
            MeetingRecord(RecordKind.AGENDA, Where.DRIVE, "Agenda for 9/15/26", "My Drive/Meetings/2026/Agenda for 9/15/26")]
    groups = same_file(recs)
    assert len(groups) == 1 and len(groups[0]["copies"]) == 2


def test_digests_are_cached_by_size_and_time(tmp_path) -> None:
    from jason.tasks.digests import Digests

    f = tmp_path / "a.txt"
    f.write_bytes(b"agenda")
    d = Digests(tmp_path)
    md5, sha = d.of(f)
    assert md5 == hashlib.md5(b"agenda").hexdigest() and sha == hashlib.sha256(b"agenda").hexdigest()
    d.save()
    assert Digests(tmp_path).of(f) == (md5, sha) and Digests(tmp_path).of(tmp_path / "missing") == ("", "")


def test_propose_adds_and_proposes_but_keeps_the_boards_status(tmp_path) -> None:
    from jason.community.board_items import BoardItem, ItemCategory
    from jason.tasks.board_items import load, propose, set_fields

    item = BoardItem(id="x", title="X", summary="s", ask="decide", category=ItemCategory.RECORDS)
    assert propose(tmp_path, [item])["proposed"] == ["x"]
    set_fields(tmp_path, "x", status="deferred")
    again = BoardItem(id="x", title="X, updated", summary="s2", ask="decide", category=ItemCategory.RECORDS)
    assert propose(tmp_path, [again])["proposed"] == []
    current = load(tmp_path)[0]
    assert current.status.value == "deferred" and current.title == "X, updated"


def test_minutes_with_zoom_recap_are_read_for_executive_subjects(tmp_path) -> None:
    from jason.tasks.meeting_catalog import _recap_note

    minutes = tmp_path / "m.txt"
    minutes.write_text("I. Call to Order\nII. Open forum\nQuick recap\nThe board imposed a $40 fine after the hearing and "
                       "reviewed delinquencies.\n", encoding="utf-8")
    assert _recap_note(minutes) == "AI recap appended; it names delinquencies, fine, hearing"
    minutes.write_text("I. Call to Order\nThe hearing on the budget was held.\n", encoding="utf-8")   # no recap, no note
    assert _recap_note(minutes) == ""


def test_the_catalog_joins_zoom_drive_and_the_library_and_checks_each_meeting(tmp_path) -> None:
    (tmp_path / "zoom" / "meetings" / "2026-06-16-a").mkdir(parents=True)
    (tmp_path / "zoom" / "meetings" / "2026-06-16-a" / "transcript.txt").write_text("we adjourn to executive session", encoding="utf-8")
    (tmp_path / "zoom" / "meetings.json").write_text(json.dumps({"meetings": [
        {"uuid": "u1", "date": "2026-06-16", "topic": "Regular Meeting", "kind": "board meeting", "folder": "meetings/2026-06-16-a",
         "files": {"transcript": "meetings/2026-06-16-a/transcript.txt"}, "cloud": ["M4A", "MP4", "TRANSCRIPT"], "cloudCheckedAt": "2026-09-29"},
        {"uuid": "u2", "date": "2026-07-21", "topic": "Special Meeting", "kind": "board meeting", "files": {}}]}), encoding="utf-8")
    (tmp_path / "drive").mkdir()
    (tmp_path / "drive" / "files.json").write_text(json.dumps([
        {"id": "d1", "name": "Minutes of 6/16/26", "path": "My Drive/Meetings/2026/Minutes of 6/16/26", "mimeType": "application/vnd.google-apps.document"},
        {"id": "d2", "name": "104-Regular Meetings.mp3", "path": "My Drive/Governing Documents/Audio Book/HOA BYLAWS/104-Regular Meetings.mp3", "mimeType": "audio/mpeg"},
        {"id": "d3", "name": "Regular Meeting transcript (1).txt", "path": "My Drive/Case/Regular Meeting transcript (1).txt", "mimeType": "text/plain"},
    ]), encoding="utf-8")
    (tmp_path / "library").mkdir()
    with sqlite3.connect(tmp_path / "library" / "library.db") as con:
        con.execute("create table documents (id text, source text, path text, name text, kind text, category text, records text, method text,"
                    " period text, confidential integer, evidence text, confidence real, classified_at text, sha256 text)")
        con.execute("insert into documents (id, path, name, kind, period, confidential) values ('9', 'Meetings/2026/Agenda for 6_16_26.pdf',"
                    " 'Agenda for 6_16_26.pdf', 'agenda', '2026-06-16', 0)")
    catalog = build(tmp_path, M, today=date(2026, 9, 29))
    june = next(m for m in catalog["meetings"] if m["date"] == "2026-06-16")
    assert june["has"]["minutes"] == {"Drive": 1} and june["has"]["agenda"] == {"PayHOA library": 1}
    assert june["has"]["audio recording"] == {"Zoom cloud": 1} and june["has"]["transcript"] == {"Zoom cloud": 1, "jason's copy": 1}
    assert any("still held after the minutes" in c for c in june["checks"]) and any("CIV 4935" in c for c in june["checks"])
    july = next(m for m in catalog["meetings"] if m["date"] == "2026-07-21")
    assert any("no minutes found" in c for c in july["checks"])
    assert [r["name"] for r in catalog["unplaced"]] == ["Regular Meeting transcript (1).txt"]   # the audio book is not a meeting
    write(tmp_path, catalog)
    assert meeting(tmp_path, "2026-06-16")["found"] and (tmp_path / "reports" / "meetings.md").is_file()
