"""The meeting room's executive session, kept apart from the open record (Civil Code 4935(e), 4950(a)).

4935(e) as stored on disk: "Any matter discussed in executive session shall be generally noted in the minutes of the
immediately following meeting that is open to the entire membership." These tests check that what the board does in
executive session goes to the executive record (``meetings/room-<date>-executive.json``, P3), that the open log notes
only the 4935 subject in general terms with the times and the return, that a decision made there is marked executive,
that the loader shows the executive record only in the private view, and that the one-time check counts without
printing. Made-up directors, matters, and data folders only.
"""

import json
import os
import sys
import types

import pytest
import webclient

os.environ.setdefault("JASON_SPEC_DIR", "/home/user/jason/tests/fixtures/spec")
os.environ["JASON_PROFILE"] = "mystique"

from jason.tasks import decisions
from jason.tasks import meeting_room as store

DAY = "2026-10-21"
FIVE = ["D. Okafor", "E. Lind", "F. Marsh", "G. Petrov", "H. Quinn"]
TITLE = "Hearing, unit 7 (made-up owner Q. Sample)"          # an item title that names the member: never in the open record
MOTION = "Move to fine the owner of unit 7 $100 for the made-up violation."
HEARING = {"id": "hearing-7", "subject": "member_discipline", "title": TITLE}


def _room(tmp_path):
    store.update(tmp_path, DAY, {"action": "attendance", "attendance": {n: "present" for n in FIVE[:4]}}, "S. Clerk", directors=FIVE)
    return store.update(tmp_path, DAY, {"action": "call_to_order", "chair": "the president"}, "S. Clerk")


def _executive(tmp_path):
    """Into executive session on the hearing; the item opened, a motion moved, voted, and decided; back to open."""
    _room(tmp_path)
    store.update(tmp_path, DAY, {"action": "executive_start", "matters": [HEARING], "note": "the owner asked to attend"}, "S. Clerk")
    store.update(tmp_path, DAY, {"action": "go_to", "item": 3, "title": TITLE}, "S. Clerk")
    room = store.update(tmp_path, DAY, {"action": "motion_draft", "itemId": "hearing-7", "title": TITLE, "text": MOTION,
                                        "mover": FIVE[0], "second": FIVE[1]}, "S. Clerk")
    assert room["motions"] == []                                  # the motion is not in the open record
    for n in FIVE[:4]:
        store.update(tmp_path, DAY, {"action": "vote", "motion": "x1", "name": n, "vote": "aye"}, "S. Clerk")
    store.update(tmp_path, DAY, {"action": "decide", "motion": "x1"}, "S. Clerk")
    return store.update(tmp_path, DAY, {"action": "executive_end"}, "S. Clerk")


def _open_text(tmp_path) -> str:
    return (tmp_path / "meetings" / f"room-{DAY}.json").read_text(encoding="utf-8")


def test_an_entry_in_executive_session_lands_in_the_executive_log_not_the_open_one(tmp_path):
    room = _executive(tmp_path)
    record = store.load_executive(tmp_path, DAY)
    shut = [e["title"] for e in record["log"]]
    assert f"Item opened: {TITLE}" in shut
    assert any(MOTION in t for t in shut) and any(t.startswith("Roll call: ") for t in shut)
    assert record["motions"][0]["id"] == "x1" and record["motions"][0]["result"] == "carried"
    assert record["motions"][0]["session"] == "executive session"
    assert record["sessions"][0]["matters"] == [HEARING] and record["sessions"][0]["endedAt"]
    assert "the owner asked to attend" in record["log"][0]["title"]
    # The open record holds none of it: not the title, the motion, the roll call, or the free note.
    text = _open_text(tmp_path)
    for secret in (TITLE, "unit 7", MOTION, "Roll call", "the owner asked to attend", "hearing-7"):
        assert secret not in text
    assert room["motions"] == [] and all("motion_draft" not in h and "vote" not in h for h in room["history"])
    assert store.executive_path(tmp_path, DAY).name == f"room-{DAY}-executive.json"


def test_the_open_log_has_the_general_note_with_its_4935_words_and_the_times(tmp_path):
    room = _executive(tmp_path)
    titles = [e["title"] for e in room["log"]]
    start, end = room["log"][-2], room["log"][-1]
    assert len(titles) == 3                                       # the call to order, the adjournment, the return
    assert start["title"].startswith("The board adjourned to executive session at ")
    assert "to discuss member discipline (Civil Code 4935(a), (b))." in start["title"]
    assert start["startedAt"] == start["at"] == room["executive"]["startedAt"]
    assert end["title"].startswith("The board met in executive session from ")
    assert "to discuss member discipline (Civil Code 4935(a), (b)). The board returned to open session." in end["title"]
    assert end["startedAt"] == start["at"] and end["endedAt"] == end["at"] == room["executive"]["endedAt"]
    assert room["executive"]["note"] == "member discipline (Civil Code 4935(a), (b))"
    assert room["executive"]["sessions"] == [{"startedAt": start["at"], "endedAt": end["at"], "subjects": ["member_discipline"]}]
    assert not any("Hearing" in t for t in titles)


def test_the_general_words_are_the_statutes(tmp_path):
    from jason.community.models.meetings import ExecutiveSubject, executive_general_note

    assert executive_general_note(["litigation", "personnel"]) == "litigation and personnel matters (Civil Code 4935(a))"
    assert executive_general_note([ExecutiveSubject.FORECLOSURE]) == "whether to foreclose on a lien (Civil Code 4935(d))"
    assert executive_general_note(["assessment_payment", "formation_of_contracts", "litigation"]) == (
        "a member's payment of assessments, matters relating to the formation of contracts with third parties and litigation "
        "(Civil Code 4935(a), (c))")
    assert executive_general_note(["", "a title"]) == ""
    # Each subject's words appear in 4935 as stored on disk, when the authorities are there.
    from pathlib import Path

    law = Path("data/authorities/CIV/CIV-4900-4955.md")
    if law.is_file():
        text = law.read_text(encoding="utf-8").replace("’", "'")
        for words in ("litigation", "matters relating to the formation of contracts with third parties", "member discipline",
                      "personnel matters", "payment of assessments", "foreclose on a lien"):
            assert words in text


def test_decide_in_executive_session_is_recorded_executive(tmp_path):
    _executive(tmp_path)
    [d] = decisions.for_meeting(tmp_path, DAY)
    assert d.session == "executive session" and d.subject == "member_discipline" and d.motion == MOTION
    assert decisions.open_only([d]) == []
    assert decisions.general_notes([d]) == ["The board met in executive session to discuss member discipline (Civil Code 4935(a), (b))."]


def test_a_motion_is_voted_in_the_session_it_was_moved_in(tmp_path):
    _room(tmp_path)
    store.update(tmp_path, DAY, {"action": "motion_draft", "itemId": "budget", "title": "Budget", "text": "Move to adopt the budget.",
                                 "mover": FIVE[0], "second": FIVE[1]}, "S. Clerk")
    with pytest.raises(ValueError, match="motion on the floor"):
        store.update(tmp_path, DAY, {"action": "executive_start", "matters": [HEARING]}, "S. Clerk")
    for n in FIVE[:4]:
        store.update(tmp_path, DAY, {"action": "vote", "motion": "m1", "name": n, "vote": "aye"}, "S. Clerk")
    store.update(tmp_path, DAY, {"action": "decide", "motion": "m1"}, "S. Clerk")
    store.update(tmp_path, DAY, {"action": "executive_start", "matters": [HEARING]}, "S. Clerk")
    store.update(tmp_path, DAY, {"action": "motion_draft", "itemId": "hearing-7", "title": TITLE, "text": MOTION,
                                 "mover": FIVE[0], "second": FIVE[1]}, "S. Clerk")
    with pytest.raises(ValueError, match="open session"):
        store.update(tmp_path, DAY, {"action": "vote", "motion": "m1", "name": FIVE[0], "vote": "no"}, "S. Clerk")
    for action, body in (("poll", {"question": "Q?", "results": {"Yes": 1}}), ("suggest", {"text": "a line"})):
        with pytest.raises(ValueError, match="executive session"):
            store.update(tmp_path, DAY, {"action": action, **body}, "S. Clerk")
    store.update(tmp_path, DAY, {"action": "executive_end"}, "S. Clerk")
    with pytest.raises(ValueError, match="executive session"):
        store.update(tmp_path, DAY, {"action": "vote", "motion": "x1", "name": FIVE[0], "vote": "aye"}, "S. Clerk")
    [open_decision] = decisions.for_meeting(tmp_path, DAY)
    assert open_decision.session == "open session" and decisions.open_only([open_decision]) == [open_decision]


@pytest.mark.parametrize("body", [{}, {"matters": []}, {"matters": [{"id": "hearing-7", "title": TITLE}]},
                                  {"matters": [{"id": "hearing-7", "subject": "a hearing"}]}, {"subjects": ["discipline of unit 7"]}])
def test_an_item_without_a_4935_subject_cannot_go_executive(tmp_path, body):
    _room(tmp_path)
    with pytest.raises(ValueError, match="name the 4935 subject first"):
        store.update(tmp_path, DAY, {"action": "executive_start", **body}, "S. Clerk")
    room = store.load(tmp_path, DAY)
    assert not room["executive"]["active"] and not store.executive_path(tmp_path, DAY).exists()


def test_the_executive_file_is_p3_and_the_open_one_p1(tmp_path):
    from jason.web.access import Level, level_of_path

    assert level_of_path(f"meetings/room-{DAY}-executive.json", tmp_path) is Level.P3
    assert level_of_path(f"meetings/room-{DAY}-executive.md", tmp_path) is Level.P3
    assert level_of_path(f"meetings/room-{DAY}.json", tmp_path) is Level.P1
    assert level_of_path(f"meetings/plan-{DAY}.json", tmp_path) is Level.P1


# -- the loader, the writer, and /api/file -----------------------------------------------------------------------------

@pytest.fixture
def web(tmp_path, monkeypatch):
    """A fake county module (the data root), a fake ``meeting`` loader with one executive matter, no agenda plan, and
    an app with made-up sign-in serving the meeting room."""
    saved = {k: sys.modules.get(k) for k in ("jason.mcp", "jason.mcp.county", "jason.web.extra.agenda_plan")}
    county = types.ModuleType("jason.mcp.county")
    county._data_dir = lambda _: tmp_path
    pkg = types.ModuleType("jason.mcp")
    pkg.__path__ = []
    pkg.county = county
    sys.modules["jason.mcp"], sys.modules["jason.mcp.county"] = pkg, county
    import jason.web.sources as sources

    base = {"found": True, "date": DAY, "today": "2026-10-03", "directors": FIVE, "decisions": [], "notes": [],
            "items": [{"id": "landscape", "title": "Renew the landscape contract", "agendaSession": "open session"},
                      {"id": "hearing-7", "title": TITLE, "agendaSession": "executive session"}],
            "commands": {}}
    monkeypatch.setattr(sources, "meeting", lambda args, **_: base)
    plan = types.ModuleType("jason.web.extra.agenda_plan")
    plan.agenda_plan = lambda args, **_: {"found": False, "note": "no plan"}
    sys.modules["jason.web.extra.agenda_plan"] = plan
    from jason.web.app import create_app
    from jason.web.extra.meeting_room import meeting_room

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><html></html>", encoding="utf-8")
    app = create_app(dist, {"meeting-room": meeting_room, "decisions": sources.decisions}, approvals_live=None,
                     sign_in=webclient.roster_sign_in())
    try:
        yield types.SimpleNamespace(app=app, root=tmp_path, base=base)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def _served(root):
    log = root / "access" / "served.jsonl"
    return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []


def test_the_writer_takes_the_chairs_subject_by_ref_and_refuses_none(web):
    from jason.web.extra.meeting_room import write

    write(DAY, {"action": "attendance", "by": "S. Clerk", "directors": FIVE, "attendance": {n: "present" for n in FIVE[:3]}})
    with pytest.raises(ValueError, match="name the 4935 subject first"):
        write(DAY, {"action": "executive_start", "by": "S. Clerk", "directors": FIVE})          # the agenda names none
    room = write(DAY, {"action": "executive_start", "by": "S. Clerk", "directors": FIVE, "matters": [{"ref": "1", "subject": "member_discipline"}]})
    assert room["executive"]["active"] and "member discipline (Civil Code 4935(a), (b))" in room["log"][-1]["title"]
    assert "executive" not in room or "record" not in room["executive"]                      # the answer is the open room
    assert store.load_executive(web.root, DAY)["sessions"][0]["matters"] == [HEARING]          # id and title from the agenda


def test_the_loader_shows_the_executive_log_only_in_the_private_view(web):
    _executive(web.root)
    anyone = webclient.client(web.app)
    held = anyone.get(f"/api/meeting-room?date={DAY}").json
    assert held["executive"]["record"] is None and held["executive"]["shown"] is False
    assert held["executive"]["note"] == "Executive session: the record is kept apart (open the private view to see it)."
    assert TITLE not in json.dumps(held) and MOTION not in json.dumps(held)
    treasurer = webclient.sign_in(webclient.client(web.app), "Pat Example").get(f"/api/meeting-room?date={DAY}").json
    assert treasurer["executive"]["record"] is None
    director = webclient.sign_in(webclient.client(web.app), "Dana Director")
    assert director.get(f"/api/meeting-room?date={DAY}").json["executive"]["record"] is None   # signed in, no private view
    assert _served(web.root) == []
    assert director.post("/api/private", json={"reason": "executive session minutes"}).status_code == 200
    shown = director.get(f"/api/meeting-room?date={DAY}").json
    assert shown["executive"]["shown"] is True and shown["executive"]["note"] == ""
    assert any(MOTION in e["title"] for e in shown["executive"]["record"]["log"])
    assert shown["executive"]["record"]["motions"][0]["tally"]["state"] == "carries"
    exec_item = next(i for i in shown["items"] if i["kind"] == "exec")
    assert exec_item["executiveMatters"][0]["title"] == TITLE
    line = _served(web.root)[-1]
    assert line["path"] == f"meetings/room-{DAY}-executive.json" and line["level"] == "P3" and line["private"] is True
    # The decisions screen: the executive decision only in the private view; otherwise held back with its general note.
    assert len(director.get(f"/api/decisions?meeting={DAY}").json["decisions"]) == 1
    plain = anyone.get(f"/api/decisions?meeting={DAY}").json
    assert plain["decisions"] == [] and plain["heldBack"] == 1 and MOTION not in json.dumps(plain)
    assert plain["executiveNotes"] == [{"meeting": DAY, "notes": ["The board met in executive session to discuss member discipline (Civil Code 4935(a), (b))."]}]


def test_api_file_serves_an_executive_export_only_in_the_private_view(web):
    folder = web.root / "meetings"
    folder.mkdir(exist_ok=True)
    (folder / f"room-{DAY}-executive.md").write_text("made-up executive minutes", encoding="utf-8")
    (folder / f"room-{DAY}.md").write_text("made-up open minutes", encoding="utf-8")
    director = webclient.sign_in(webclient.client(web.app), "Dana Director")
    r = director.get(f"/api/file?path=meetings/room-{DAY}-executive.md")
    assert r.status_code == 403 and "only in the private view" in r.json["error"]
    assert director.get(f"/api/file?path=meetings/room-{DAY}.md").status_code == 200
    assert director.post("/api/private", json={"reason": "executive session minutes"}).status_code == 200
    ok = director.get(f"/api/file?path=meetings/room-{DAY}-executive.md")
    assert ok.status_code == 200 and _served(web.root)[-1]["level"] == "P3"


# -- the minutes draft and the one-time check ----------------------------------------------------------------------------

def test_the_minutes_draft_reads_only_the_open_room_and_notes_executive_generally(tmp_path):
    from datetime import date
    from pathlib import Path

    from jason.tasks.minutes_draft import room_general

    _executive(tmp_path)
    assert room_general(tmp_path, date.fromisoformat(DAY)) == [
        "The board met in executive session to discuss member discipline (Civil Code 4935(a), (b))."]
    src = Path("src/jason/tasks/minutes_draft.py").read_text(encoding="utf-8")
    assert "load_executive" not in src and "executive_path" not in src and "open_only(recorded)" in src


def _legacy(tmp_path):
    """A room file as the room wrote it before the executive record was kept apart: three entries, one motion, and one
    poll between the start and end lines."""
    (tmp_path / "meetings").mkdir(parents=True, exist_ok=True)
    log = [("18:30", "Called to order."), ("19:00", "The board adjourned to executive session to discuss a made-up matter (CIV 4935)."),
           ("19:01", "Item opened: a made-up title"), ("19:05", "Motion by A, seconded by B: a made-up motion"),
           ("19:06", "Roll call: A aye, B aye. Carried."), ("19:30", "The board returned to open session. The host resumes."),
           ("19:31", "Item opened: an open item")]
    room = {**store.empty(DAY), "log": [{"at": f"{DAY}T{t}:00+00:00", "title": x} for t, x in log],
            "motions": [{"id": "m1", "movedAt": f"{DAY}T19:05:00+00:00", "decidedAt": f"{DAY}T19:06:00+00:00"},
                        {"id": "m2", "movedAt": f"{DAY}T19:40:00+00:00", "decidedAt": ""}],
            "polls": [{"at": f"{DAY}T19:10:00+00:00", "question": "q"}], "transcriptSuggestions": []}
    room["executive"] = {"active": False, "startedAt": "", "endedAt": "", "note": ""}       # an older file: no sessions
    store.save(tmp_path, room)


def test_the_check_counts_entries_inside_an_executive_window_without_their_text(tmp_path, monkeypatch, capsys):
    _legacy(tmp_path)
    assert store.check_executive(tmp_path, DAY) == {"date": DAY, "found": True, "windows": 1, "log": 3, "motions": 1, "polls": 1,
                                                    "suggestions": 0, "total": 5}
    assert store.check_executive(tmp_path, "2026-11-18")["found"] is False
    monkeypatch.setattr("jason.config.data_dir", lambda *a: tmp_path)
    assert store.main(["--check-executive", "all"]) == 0
    out = capsys.readouterr().out
    assert out.strip() == f"{DAY}: 1 executive window(s); inside them 3 log entries, 1 motion(s), 1 poll(s), 0 suggestion(s); total 5"
    assert "made-up" not in out


# -- the meeting page's loader: executive items' titles only in the private view ------------------------------------------

EXEC_TITLE = "Payment plan for made-up owner Q. Sample"
EXEC_ASK = "Accept Q. Sample's offer of twelve months."


@pytest.fixture
def meeting_web(tmp_path, monkeypatch):
    """The real ``meeting`` loader over a tmp data folder with one open and one executive board item, the agenda plan
    naming the executive one's 4935 subject, and an app with made-up sign-in serving ``/api/meeting``."""
    from jason.community.board_items import BoardItem, ItemCategory, ItemStatus
    from jason.tasks import agenda_plan
    from jason.tasks.board_items import save

    saved = {k: sys.modules.get(k) for k in ("jason.mcp", "jason.mcp.county")}
    county = types.ModuleType("jason.mcp.county")
    county._data_dir = lambda _=None: tmp_path
    pkg = types.ModuleType("jason.mcp")
    pkg.__path__ = []
    pkg.county = county
    sys.modules["jason.mcp"], sys.modules["jason.mcp.county"] = pkg, county
    save(tmp_path, [BoardItem("sample-payment-plan", EXEC_TITLE, "Owner Q. Sample owes.", EXEC_ASK, ItemCategory.COLLECTIONS,
                              status=ItemStatus.PROPOSED, notes="Offered twelve months."),
                    BoardItem("repaint", "Repaint the carports", "Peeling.", "Approve the bid.", ItemCategory.MAINTENANCE,
                              status=ItemStatus.PROPOSED)])
    agenda_plan.update(tmp_path, DAY, {"items": {"sample-payment-plan": {"subject": "assessment_payment"}}}, by="S. Clerk")
    import jason.web.sources as sources
    from jason.web.app import create_app

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><html></html>", encoding="utf-8")
    app = create_app(dist, {"meeting": sources.meeting}, approvals_live=None, sign_in=webclient.roster_sign_in())
    try:
        yield types.SimpleNamespace(app=app, root=tmp_path, sources=sources)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def test_the_meeting_loader_lists_executive_titles_only_in_the_private_view(meeting_web):
    secrets = (EXEC_TITLE, "Q. Sample", EXEC_ASK, "sample-payment-plan", "Offered twelve months")
    for c in (webclient.client(meeting_web.app),                                                   # nobody signed in
              webclient.sign_in(webclient.client(meeting_web.app), "Pat Example"),                 # an office without P3
              webclient.sign_in(webclient.client(meeting_web.app), "Dana Director")):              # P3, no private view
        out = c.get(f"/api/meeting?date={DAY}").json
        text = json.dumps(out)
        assert all(s not in text for s in secrets), "an executive item's title, ask, notes, or id outside the private view"
        held = next(r for r in out["items"] if r["agendaSession"] == "executive session")
        assert held["held"] is True and held["id"] == "executive-1" and held["subject"] == "assessment_payment"
        assert held["title"] == "An executive-session matter: a member's payment of assessments"
        assert out["executiveHeld"] == 1 and out["executiveCount"] == 1 and "private view" in out["executiveHeldNote"]
        assert any(r["title"] == "Repaint the carports" for r in out["items"])                     # an open item as it is
        assert "a member's payment of assessments (Civil Code 4935(a), (c))" in out["agendaMarkdown"]
    assert _served(meeting_web.root) == []
    director = webclient.sign_in(webclient.client(meeting_web.app), "Dana Director")
    assert director.post("/api/private", json={"reason": "executive session prep"}).status_code == 200
    shown = director.get(f"/api/meeting?date={DAY}").json
    row = next(r for r in shown["items"] if r["agendaSession"] == "executive session")
    assert row["title"] == EXEC_TITLE and row["id"] == "sample-payment-plan" and shown["executiveHeld"] == 0
    # The agenda draft is posted to members: it names the matter by its subject even in the private view.
    assert EXEC_TITLE not in shown["agendaMarkdown"] and EXEC_ASK not in shown["agendaMarkdown"]
    assert EXEC_TITLE not in shown["minutesTemplate"]
    line = _served(meeting_web.root)[-1]
    assert line["path"] == "board/items.json" and line["level"] == "P3" and line["private"] is True
    # Whole for a caller that keeps the private view itself (the meeting room, the agenda plan); no request asked.
    assert any(r["title"] == EXEC_TITLE for r in meeting_web.sources.meeting({"date": DAY}, private=True)["items"])


def test_a_room_kept_apart_counts_nothing_inside_its_windows(tmp_path):
    _executive(tmp_path)
    found = store.check_executive(tmp_path, DAY)
    assert found["windows"] == 1 and found["total"] == 0
    assert [r["date"] for r in store.check_all(tmp_path)] == [DAY]          # the executive record is not checked as a room
