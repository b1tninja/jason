"""The meetings screens' document references (docs/console/doc-component.md): a meeting's records as ``DocRef``s, a
hearing's notice at P3, and the minutes review's paths under the data folder with the Zoom transcript beside the draft.
Every reference resolves (``resolve(address)["found"]``). Everything here is made up."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from jason.approvals.evidence import resolve

DRIVE_ID = "1ExampleMinutesDoc1"
NOTICE_ID = "1ExampleHearingDoc01"
SPEC_KEYS = {"address", "document", "name", "kind", "level", "source", "readAt", "size", "thumb", "original",
             "refreshable", "stale"}
ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|/)")
DAY = "2099-10-20"
FOLDER = "meetings/2099-10-20-abc1234567"


def _drive_copy(root: Path, file_id: str, name: str) -> None:
    copies = root / "drive" / "copies"
    copies.mkdir(parents=True, exist_ok=True)
    (copies / f"{file_id}.pdf").write_bytes(b"%PDF-1.4 copy")
    (copies / f"{file_id}.json").write_text(json.dumps({
        "readAt": "2099-10-21T00:00:00+00:00", "modifiedTime": "2099-10-20T00:00:00+00:00", "name": name,
        "mimeType": "application/vnd.google-apps.document"}), encoding="utf-8")


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


@pytest.fixture
def data(tmp_path, monkeypatch):
    """A made-up data folder: a meeting's catalog (posted minutes in the library, a Drive copy, jason's draft, a Gmail
    message, Zoom's cloud), the Zoom index with the board meeting's transcript, a minutes draft, and a hearing's notice
    (a Doc and jason's draft)."""
    from tests.test_docref import _library

    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PAYHOA_CATALOG", str(tmp_path / "payhoa.db"))
    _library(tmp_path, [("abc1234", "Minutes/Minutes 2099-10-20.pdf", False, "aaa"),
                        ("def5678", "Minutes/Executive 2099-10-20.pdf", True, "bbb")])
    for rel in ("Minutes/Minutes 2099-10-20.pdf", "Minutes/Executive 2099-10-20.pdf"):
        (tmp_path / "library" / "files" / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "library" / "files" / rel).write_bytes(b"%PDF-1.4 lib")
    _drive_copy(tmp_path, DRIVE_ID, "Minutes 2099-10-20")
    _drive_copy(tmp_path, NOTICE_ID, "Hearing notice")
    (tmp_path / "board").mkdir()
    (tmp_path / "board" / f"agenda-{DAY}.md").write_text("# Agenda\n", encoding="utf-8")
    (tmp_path / "board" / f"minutes-draft-{DAY}.md").write_text("# DRAFT Minutes\n\nCalled to order at {time}.\n", encoding="utf-8")
    zoom = tmp_path / "zoom"
    (zoom / FOLDER).mkdir(parents=True)
    (zoom / FOLDER / "transcript.txt").write_text("[7:02 PM] A Director: I call the meeting to order.\n", encoding="utf-8")
    (zoom / "meetings.json").write_text(json.dumps({"meetings": [
        {"uuid": "u1", "date": DAY, "topic": "Board meeting", "kind": "board", "folder": FOLDER, "duration": 60}]}), encoding="utf-8")
    (zoom / "hearings").mkdir()
    (zoom / "hearings" / f"{DAY}-123-main-st-12.md").write_text("# Notice of hearing\n", encoding="utf-8")
    (zoom / "hearings.json").write_text(json.dumps({"hearings": [{
        "address": "123 Main St #12", "start": f"{DAY}T18:00", "noticeBy": "2099-10-10", "decisionByIfHeld": "2099-11-03",
        "notice": f"hearings/{DAY}-123-main-st-12.md", "noticeDoc": {"id": NOTICE_ID, "url": "", "unfilled": []}}]}),
        encoding="utf-8")
    records = [
        {"kind": "minutes", "where": "Drive", "name": "Minutes 2099-10-20", "location": "Board/Minutes 2099-10-20", "ref": DRIVE_ID},
        {"kind": "minutes", "where": "PayHOA library", "name": "Minutes 2099-10-20.pdf", "location": "Minutes/Minutes 2099-10-20.pdf", "ref": "abc1234"},
        {"kind": "executive session agenda", "where": "PayHOA library", "name": "Executive 2099-10-20.pdf", "location": "Minutes/Executive 2099-10-20.pdf", "ref": "def5678", "confidential": True},
        {"kind": "agenda", "where": "jason draft", "name": f"agenda-{DAY}.md", "location": f"data/board/agenda-{DAY}.md", "ref": ""},
        {"kind": "transcript", "where": "jason's copy", "name": "Board meeting (transcript)", "location": f"data/zoom/{FOLDER}/transcript.txt", "ref": "u1"},
        {"kind": "meeting notice", "where": "Gmail", "name": "Notice of the board meeting", "location": "gmail:thread1", "ref": "m1"},
        {"kind": "meeting notice", "where": "PayHOA communication", "name": "Board meeting notice", "location": "PayHOA communications (email)", "ref": ""},
        {"kind": "audio recording", "where": "Zoom cloud", "name": "Board meeting (M4A)", "location": "zoom:u1", "ref": "u1"},
        {"kind": "chat", "where": "jason's copy", "name": "Board meeting (chat)", "location": f"data/zoom/{FOLDER}/chat.txt", "ref": "u1"},
    ]
    (tmp_path / "meetings").mkdir()
    (tmp_path / "meetings" / "catalog.json").write_text(json.dumps({"builtAt": "2099-10-22T00:00:00+00:00", "count": 1, "meetings": [
        {"date": DAY, "titles": ["Board meeting"], "has": {}, "checks": [], "sameFile": [], "records": records}]}), encoding="utf-8")
    return tmp_path


def _resolves(ref: dict, root: Path) -> None:
    assert set(ref) <= SPEC_KEYS, ref
    assert not any(ABSOLUTE.match(s) for s in _strings(ref)), ref
    got = resolve(ref["address"], data_dir=root, private=True)
    assert got["found"], (ref["address"], got.get("note"))


# --- a meeting's records ----------------------------------------------------------------------------------------------

def test_a_meetings_records_are_references_by_kind_the_posted_copy_first(data):
    from jason.web.extra.meeting_docs import record_refs
    from jason.tasks.meeting_catalog import load

    records = load(data)["meetings"][0]["records"]
    groups = record_refs(records, data)
    assert [g["kind"] for g in groups] == ["agenda", "executive session agenda", "minutes", "transcript"]
    minutes = next(g for g in groups if g["kind"] == "minutes")["docs"]
    assert [d["address"] for d in minutes] == ["library:abc1234", f"drive:{DRIVE_ID}"]      # the posted copy first
    assert next(g for g in groups if g["kind"] == "executive session agenda")["docs"][0]["level"] == "P3"
    agenda = next(g for g in groups if g["kind"] == "agenda")["docs"][0]
    assert agenda["address"] == f"file:board/agenda-{DAY}.md" and agenda["level"] == "P1"
    transcript = next(g for g in groups if g["kind"] == "transcript")["docs"][0]
    assert transcript["address"] == f"file:zoom/{FOLDER}/transcript.txt" and transcript["level"] == "P1"
    for group in groups:
        for ref in group["docs"]:
            _resolves(ref, data)


def test_a_record_no_resolver_reads_stays_out(data):
    from jason.web.extra.meeting_docs import record_refs

    assert record_refs([{"kind": "minutes", "where": "Gmail", "location": "gmail:thread9", "ref": "m9", "name": "x"},
                        {"kind": "audio recording", "where": "Zoom cloud", "location": "zoom:u9", "ref": "u9", "name": "y"},
                        {"kind": "minutes", "where": "Drive", "location": "Board/x", "ref": "not an id", "name": "z"},
                        {"kind": "minutes", "where": "jason draft", "location": "C:\\Users\\x\\minutes.md", "ref": "", "name": "w"}],
                       data) == []


def test_the_meetings_loader_answers_one_meetings_documents(data):
    from jason.web.sources import meetings

    listing = meetings({})
    assert listing["found"] and "docs" not in listing                       # the list stays light: badges only
    one = meetings({"date": DAY})
    assert [g["kind"] for g in one["docs"]] == ["agenda", "executive session agenda", "minutes", "transcript"]


# --- a hearing's notice ------------------------------------------------------------------------------------------------

def test_a_hearings_notice_is_the_doc_then_jasons_draft_both_p3(data):
    from jason.web.sources import hearings

    row = hearings({})["hearings"][0]
    refs = row["noticeRefs"]
    assert [r["address"] for r in refs] == [f"drive:{NOTICE_ID}", f"file:zoom/hearings/{DAY}-123-main-st-12.md"]
    assert [r["level"] for r in refs] == ["P3", "P3"]
    assert "123 Main" not in " ".join(r["name"] for r in refs)              # named by the day, not the unit
    for ref in refs:
        _resolves(ref, data)


def test_a_hearing_with_no_notice_has_no_references(data):
    from jason.web.extra.meeting_docs import hearing_refs

    assert hearing_refs({"start": f"{DAY}T18:00"}, data) == []
    assert hearing_refs({"start": f"{DAY}T18:00", "noticeDoc": {"id": "bad id"}, "notice": "/etc/passwd"}, data) == []


# --- the minutes review -----------------------------------------------------------------------------------------------

def test_the_minutes_review_names_files_under_the_data_folder_with_their_references(data):
    from jason.web.extra.minutes_review import minutes_review

    listing = minutes_review({})
    row = listing["drafts"][0]
    assert row["file"] == f"board/minutes-draft-{DAY}.md" and row["minutesFile"] == ""
    assert row["draftDoc"]["address"] == f"file:board/minutes-draft-{DAY}.md" and row["minutesDoc"] is None
    one = minutes_review({"date": DAY})
    assert one["transcriptDoc"]["address"] == f"file:zoom/{FOLDER}/transcript.txt"
    assert one["transcriptDoc"]["level"] == "P1" and one["transcriptDoc"]["kind"] == "text"
    for ref in (one["draftDoc"], one["transcriptDoc"]):
        _resolves(ref, data)
    assert not any(ABSOLUTE.match(s) for s in _strings(listing))


def test_the_filled_copy_is_a_reference_once_saved(data):
    from jason.web.extra.minutes_review import write

    out = write(DAY, {"values": {"b1": "7:02 PM"}, "by": "Secretary"})
    assert out["minutesFile"] == f"board/minutes-{DAY}.md"
    assert out["minutesDoc"]["address"] == f"file:board/minutes-{DAY}.md" and out["minutesDoc"]["level"] == "P1"
    _resolves(out["minutesDoc"], data)
    kept = json.loads((data / "board" / f"minutes-draft-{DAY}.review.json").read_text(encoding="utf-8"))
    assert kept["draft"] == f"board/minutes-draft-{DAY}.md"                  # the stored review names no absolute path
    assert not any(ABSOLUTE.match(s) for s in _strings(out))


def test_an_executive_sessions_transcript_is_p3(data):
    from jason.web.extra.minutes_review import minutes_review

    index = data / "zoom" / "meetings.json"
    rows = json.loads(index.read_text(encoding="utf-8"))
    rows["meetings"][0]["confidential"] = True
    index.write_text(json.dumps(rows), encoding="utf-8")
    assert minutes_review({"date": DAY})["transcriptDoc"]["level"] == "P3"


def test_no_board_meeting_that_day_is_no_transcript(data):
    from jason.web.extra.minutes_review import minutes_review

    (data / "zoom" / "meetings.json").write_text(json.dumps({"meetings": []}), encoding="utf-8")
    assert minutes_review({"date": DAY})["transcriptDoc"] is None
