"""The office views' loader (``jason.web.extra.office_view``, ``GET /api/office-view?office=ROLE``): a lens that lets any
board member or the manager read any office's landing page. Made-up people, offices, letters, items, duties, and runs in a
tmp data folder; nothing reaches Google, Keeper, or PayHOA.

The matrix: signed out is a 401; a roster person with no office and an administrator with none are a 403 with
``access.may_see``'s sentence; the manager and every board office read ANY office (200); a word that is no office is a 400.
The lens changes nothing about who the viewer is, and the answer carries offices, counts, and titles, never a name.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
import webclient

from jason.community.base import Officer, OfficerRole
from jason.community.board_items import BoardItem, ItemCategory
from jason.community.schedule import Assignment, Role, Trigger
from test_workflows_support import DATES, OWNER, FakeReaders, example  # noqa: F401 - example is a fixture

P, VP, S, T, D, M = (OfficerRole.PRESIDENT, OfficerRole.VICE_PRESIDENT, OfficerRole.SECRETARY, OfficerRole.TREASURER,
                     OfficerRole.DIRECTOR, OfficerRole.MANAGER)
ROWS = webclient.ROSTER + (("Rae Roster", "", "rae@example.org", False),)
TODAY = date(2099, 9, 20)
OFFICES = [r.value for r in OfficerRole]

# A made-up board: one person holds secretary and treasurer, and no one holds vice president.
OFFICERS = (
    Officer(P, "Lee President", ("the president",), "lee@example.org"),
    Officer(S, "Tess Two", ("the secretary",), "tess@example.org"),
    Officer(T, "Tess Two", ("the treasurer",), "tess@example.org"),
    Officer(T, "Pat Example", ("the treasurer",), "pat@example.org"),
    Officer(D, "Dana Director", (), "dana@example.org"),
    Officer(M, "A Manager", ("the manager",), "a.manager@example.org"),
)
DUTIES = (
    Assignment("treasurer-books", "Review the sample reconciliations", Role.TREASURER, ("CIV 0001",), Trigger.CADENCE,
               every_months=1, day=5),
    Assignment("secretary-posting", "Post the sample notice", Role.SECRETARY, ("CIV 0002",), Trigger.CADENCE,
               every_months=1, day=25),
    Assignment("board-review", "Review the sample policy", Role.BOARD, ("CIV 0003",), Trigger.CADENCE, every_months=1,
               day=22),
    Assignment("backup-duty", "Check the sample deposit", Role.SECRETARY, ("CIV 0004",), Trigger.CADENCE, every_months=1,
               day=27, backup=Role.TREASURER),
)


class Home:
    """A made-up association: its officers and its duties, nothing else (every other fact is a miss)."""

    name = "Example HOA"

    def officers(self):
        return OFFICERS

    def assignments(self):
        return DUTIES


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    monkeypatch.setenv("JASON_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: tmp_path)
    home = Home()
    monkeypatch.setattr("jason.community.community", lambda: home)
    monkeypatch.setattr("jason.access.community_officers", lambda: OFFICERS)
    monkeypatch.setattr("jason.web.extra.office_view._today", lambda: TODAY)
    return tmp_path


@pytest.fixture
def app(world):
    from jason.web.app import create_app
    from jason.web.extra import office_view as ov

    dist = world / "dist"
    dist.mkdir(exist_ok=True)
    return create_app(dist, {"office-view": ov.office_view}, approvals_live=None, extra_writes=False,
                      sign_in=webclient.roster_sign_in(ROWS))


def as_(app, name):
    return webclient.sign_in(webclient.client(app), name, rows=ROWS)


def read(app, who, office=""):
    r = as_(app, who).get(f"/api/office-view?office={office}")
    assert r.status_code == 200, (who, office, r.status_code, r.get_data(as_text=True)[:200])
    return r.json


def letters(root, *rows):
    import jason.tasks.approvals as store

    path = store.FILE
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    body = {k: {"key": k, "stage": stage, "kind": kind, "title": "Sample title", "approver": approver, "log": []}
            for k, stage, kind, approver in rows}
    (root / path).write_text(json.dumps({"letters": body}), encoding="utf-8")


def items(root, *rows):
    from jason.tasks import board_items

    found = [BoardItem(id=i, title=t, summary="s", ask="decide", category=ItemCategory.GOVERNANCE, owner=owner)
             for i, t, owner in rows]
    board_items.save(root, found)


# --- who may read it ---------------------------------------------------------------------------------------------------------

def test_signed_out_is_a_401(app):
    assert webclient.client(app).get("/api/office-view?office=treasurer").status_code == 401


@pytest.mark.parametrize("who", ("Rae Roster", "Ada Admin"))
def test_a_roster_person_with_no_office_and_an_admin_with_none_are_a_403_with_the_may_see_sentence(app, who):
    r = as_(app, who).get("/api/office-view?office=treasurer")
    assert r.status_code == 403
    assert "open contact details and members' submissions (P2)" in r.json["error"]


@pytest.mark.parametrize("who", ("A Manager", "Pat Example", "Dana Director", "Sam Secretary", "Lee President", "Vic Vice",
                                 "Tess Two"))
def test_the_manager_and_every_board_office_read_any_office(app, who):
    for office in OFFICES + [""]:
        got = read(app, who, office)
        assert got["office"] == office and got["found"] is True


def test_a_word_that_is_no_office_is_a_400_after_the_gate(app):
    r = as_(app, "Pat Example").get("/api/office-view?office=chairman")
    assert r.status_code == 400 and "not an office" in r.json["error"]
    assert webclient.client(app).get("/api/office-view?office=chairman").status_code == 401
    assert as_(app, "Rae Roster").get("/api/office-view?office=chairman").status_code == 403


def test_a_hash_can_say_vice_president_with_a_hyphen(app):
    assert read(app, "Pat Example", "vice-president")["office"] == "vice president"


def test_it_is_not_an_owner_source_and_the_owner_view_is_refused(app):
    from jason.web.extra.owner_view import OWNER_SOURCES

    assert "office-view" not in OWNER_SOURCES
    r = as_(app, "Pat Example").get("/api/office-view?office=treasurer&view=owner")
    assert r.status_code in (401, 403)


# --- a lens, not impersonation -----------------------------------------------------------------------------------------------

def test_the_answer_names_the_office_asked_for_and_the_viewers_own_as_words(app):
    got = read(app, "Pat Example", "secretary")
    assert got["office"] == "secretary" and got["mine"] == ["treasurer"] and got["ownOffice"] is False
    assert got["reading"] == ["secretary"] and got["title"] == "the secretary"
    own = read(app, "Pat Example", "treasurer")
    assert own["ownOffice"] is True


def test_it_carries_no_name_no_by_and_no_session(app, world):
    letters(world, ("l1", "requested", "Sample notice", "the treasurer"))
    items(world, ("i1", "A sample matter", "the treasurer"), ("i2", "Another matter", "Pat Example"))
    body = json.dumps([read(app, "Sam Secretary", o) for o in OFFICES + [""]])
    for name in ("Lee President", "Tess Two", "Pat Example", "Dana Director", "A Manager", "Sam Secretary", "Ada Admin",
                 "lee@example.org", "tess@example.org", "pat@example.org", "Rae Roster"):
        assert name not in body, name
    got = read(app, "Sam Secretary", "treasurer")
    assert "by" not in got and "session" not in got and "account" not in got

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)

    assert not {"by", "name", "email", "account", "session", "holder"} & set(keys(got))


def test_reading_another_office_changes_nothing_about_the_viewer_and_logs_nothing(app, world):
    from jason.web.app import create_app  # noqa: F401 - the app fixture built it

    c = as_(app, "Pat Example")
    before = c.get("/api/session").json
    served = world / "access" / "served.jsonl"
    c.get("/api/office-view?office=secretary")
    c.get("/api/office-view?office=manager")
    after = c.get("/api/session").json
    assert before["signedIn"] == after["signedIn"] and before["roleClass"] == after["roleClass"]
    assert before["private"] == after["private"]
    assert not served.exists()
    from jason.web.access import Level, Viewer, may_see

    pat = Viewer("Pat Example", frozenset({"treasurer"}))
    assert may_see(pat, Level.P2) == (True, "") and may_see(pat, Level.P3)[0] is False
    assert may_see(pat, Level.P3, private=True) == (True, "")        # the same results with or without the lens


def test_a_person_holding_two_offices_sees_the_union_by_default_and_each_alone(app, world):
    letters(world, ("l1", "requested", "Sample notice", "the treasurer"), ("l2", "requested", "Sample packet", "the secretary"))
    both = read(app, "Tess Two", "")
    assert both["mine"] == ["secretary", "treasurer"] and both["reading"] == ["secretary", "treasurer"]
    assert both["title"] == "the secretary and the treasurer" and both["office"] == ""
    assert {r["office"] for r in both["bands"]["waitingOnOffice"] if r["type"] == "letter"} == {"secretary", "treasurer"}
    alone = read(app, "Tess Two", "treasurer")
    assert {r["office"] for r in alone["bands"]["waitingOnOffice"] if r["type"] == "letter"} == {"treasurer"}


# --- the offices, and a vacancy ----------------------------------------------------------------------------------------------

def test_every_office_the_profile_names_is_in_the_lens_and_a_vacant_one_says_so(app):
    got = read(app, "Sam Secretary", "vice president")
    assert [o["office"] for o in got["offices"]] == OFFICES
    by = {o["office"]: o for o in got["offices"]}
    assert by["vice president"]["vacant"] is True and by["vice president"]["holders"] == 0
    assert by["treasurer"]["vacant"] is False and by["treasurer"]["holders"] == 2
    assert got["vacant"] is True
    assert read(app, "Sam Secretary", "treasurer")["vacant"] is False


def test_a_vacant_office_still_shows_what_waits_with_no_one_to_do_it(app, world):
    letters(world, ("l1", "requested", "Sample notice", "the vice president"))
    # no letter names the VP as an approver in the store's own list, but the band reads whatever is stored
    got = read(app, "Sam Secretary", "vice president")
    assert got["vacant"] is True
    assert [r for r in got["bands"]["waitingOnOffice"] if r["type"] == "letter"][0]["approver"] == "the vice president"


def test_a_profile_that_names_no_officers_lists_no_office(app, monkeypatch):
    monkeypatch.setattr("jason.access.community_officers", lambda: ())
    got = read(app, "Pat Example", "treasurer")
    assert got["offices"] == [] and got["vacant"] is False
    assert any("names no officers" in c for c in got["caveats"])


# --- the bands, from what exists ---------------------------------------------------------------------------------------------

def test_letters_wait_on_the_office_that_approves_them(app, world):
    letters(world,
            ("a", "requested", "Sample notice", "the treasurer"), ("b", "requested", "Sample notice", "the treasurer"),
            ("c", "requested", "Sample packet", "the board"), ("d", "saved", "Sample notice", "the treasurer"),
            ("e", "requested", "Sample reply", "the manager"))
    rows = lambda who, office: [r for r in read(app, who, office)["bands"]["waitingOnOffice"] if r["type"] == "letter"]
    t = rows("Dana Director", "treasurer")
    assert [(r["kind"], r["count"]) for r in t] == [("Sample notice", 2)]        # a saved letter waits on no one yet
    assert [(r["kind"], r["approver"]) for r in rows("Dana Director", "president")] == [("Sample packet", "the board")]
    assert [(r["kind"], r["approver"]) for r in rows("Dana Director", "secretary")] == [("Sample packet", "the board")]
    assert rows("Dana Director", "director") == []
    assert [r["kind"] for r in rows("Dana Director", "manager")] == ["Sample reply"]
    assert "Sample title" not in json.dumps(t)                                    # a letter's title is not shown, only its kind


def test_board_items_the_board_gave_the_office_or_the_board(app, world):
    items(world, ("i1", "Sample matter one", "the treasurer"), ("i2", "Sample matter two", "Pat Example"),
          ("i3", "Sample matter three", "the board"), ("i4", "Sample matter four", ""), ("i5", "Sample matter five", "Lee President"))
    rows = lambda office: {r["id"]: r for r in read(app, "Sam Secretary", office)["bands"]["waitingOnOffice"]
                           if r["type"] == "board-item"}
    t = rows("treasurer")
    assert set(t) == {"i1", "i2", "i3"} and t["i3"]["shared"] is True and t["i1"]["shared"] is False
    assert set(rows("president")) == {"i3", "i5"}
    assert set(rows("manager")) == set()
    assert "owner" not in t["i2"]                          # the board's owner text can be a name: matched, never shown


def test_an_executive_session_item_is_held_back_and_never_by_title(app, world):
    from jason.community.board_items import Session
    from jason.tasks import board_items

    board_items.save(world, [BoardItem(id="x1", title="Sample private matter", summary="s", ask="decide",
                                       category=ItemCategory.LEGAL, owner="the treasurer", session=Session.EXECUTIVE)])
    got = read(app, "Sam Secretary", "treasurer")
    assert "Sample private matter" not in json.dumps(got)


def test_the_secretary_records_the_boards_open_votes(app, world):
    from jason.tasks import decisions

    decisions.record(world, "2099-09-15", "Sample motion title", "Move that the sample be adopted")
    decisions.record(world, "2099-09-15", "Done motion", "Move the other sample", outcome="approved")
    sec = [r for r in read(app, "Pat Example", "secretary")["bands"]["waitingOnOffice"] if r["type"] == "decision"]
    assert [r["title"] for r in sec] == ["Sample motion title"]
    assert [r for r in read(app, "Pat Example", "treasurer")["bands"]["waitingOnOffice"] if r["type"] == "decision"] == []
    assert any("votes to record" in n["what"] for n in read(app, "Pat Example", "treasurer")["notComposed"])


def test_the_schedule_gives_the_offices_duties_overdue_due_soon_and_coming_up(app):
    t = read(app, "Dana Director", "treasurer")
    needs = {r["key"]: r for r in t["bands"]["needsAttention"] if r["type"] == "duty"}
    assert set(needs) == {"treasurer-books", "board-review", "backup-duty"}
    assert needs["treasurer-books"]["standing"] == "overdue" and needs["treasurer-books"]["urgency"] == "LEGAL"
    assert needs["treasurer-books"]["basis"] == "law" and needs["treasurer-books"]["owner"] == "treasurer"
    assert needs["board-review"]["shared"] is True and needs["board-review"]["urgency"] == "due soon"
    assert needs["backup-duty"]["backup"] is True
    assert [r["urgency"] for r in t["bands"]["needsAttention"]][0] == "LEGAL"           # the most urgent first
    coming = [r["key"] for r in t["bands"]["comingUp"]]
    assert "treasurer-books" in coming and "secretary-posting" not in coming
    s = read(app, "Dana Director", "secretary")
    assert {r["key"] for r in s["bands"]["needsAttention"]} == {"secretary-posting", "board-review", "backup-duty"}
    m = read(app, "Dana Director", "manager")
    assert [r for r in m["bands"]["needsAttention"] if r["type"] == "duty"] == []       # the board's duties are not the manager's


def test_open_tasks_an_office_owns_are_a_count_never_a_title(app, world):
    from jason.tasks import dock

    dock.add_task(world, "Call Sample Person about the sample", by="Pat Example", owner="the treasurer", due="2099-09-01")
    dock.add_task(world, "A sample for the board", by="Pat Example", owner="the board", due="")
    got = read(app, "Sam Secretary", "treasurer")
    row = next(r for r in got["bands"]["needsAttention"] if r["type"] == "tasks")
    assert row["count"] == 2 and row["overdue"] == 1
    assert "Sample Person" not in json.dumps(got)


def test_the_runs_whose_current_step_the_office_holds(app, world, example):
    from jason.workflows import api

    rd = FakeReaders()
    started = api.start(world, "example-cycle", "campaign:EX-2099", "Example cycle 2099", DATES, OWNER, yes=True, today=TODAY,
                        at="2099-09-15T09:00:00Z")["run"]["id"]
    api.open_run(world, started, OWNER, readers=rd, yes=True, today=TODAY, at="2099-09-15T09:01:00Z")
    mgr = read(app, "Sam Secretary", "manager")["bands"]["work"]
    assert [(r["id"], r["label"], r["step"]) for r in mgr] == [(started, "Example cycle 2099", "example-cycle.2")]
    assert mgr[0]["stepTitle"] and mgr[0]["office"] == "manager" and "A. Manager" not in json.dumps(mgr)
    assert read(app, "Sam Secretary", "treasurer")["bands"]["work"] == []


def test_a_band_that_fails_says_so_and_the_others_stand(app, world, monkeypatch):
    letters(world, ("l1", "requested", "Sample notice", "the treasurer"))

    def boom(*a, **k):
        raise OSError("the schedule store is not readable")

    monkeypatch.setattr("jason.tasks.schedule.agenda", boom)
    got = read(app, "Sam Secretary", "treasurer")
    assert "OSError" in got["bandErrors"]["needsAttention"] and "comingUp" in got["bandErrors"]
    assert got["bands"]["waitingOnOffice"] and got["bands"]["needsAttention"] == []
    assert any(n["band"] == "needsAttention" and "not readable" in n["why"] for n in got["notComposed"])


def test_it_lists_what_it_could_not_compose_honestly(app):
    got = read(app, "Sam Secretary", "treasurer")
    said = {n["band"] for n in got["notComposed"]}
    assert {"waitingOnOffice", "needsAttention", "nextQuestions"} <= said
    assert all(n["what"] and n["why"] for n in got["notComposed"])
    assert got["caveats"] and "lens" in got["caveats"][0]


def test_a_second_open_run_adds_nothing_here(app, world):
    """The loader reads: the run store is unchanged by a read."""
    before = sorted(p.name for p in world.rglob("*") if p.is_file())
    read(app, "Sam Secretary", "manager")
    assert sorted(p.name for p in world.rglob("*") if p.is_file()) == before


def test_bands_are_capped_with_their_totals_in_counts(app, world):
    items(world, *[(f"i{n}", f"Sample matter {n}", "the treasurer") for n in range(20)])
    got = read(app, "Sam Secretary", "treasurer")
    assert len(got["bands"]["waitingOnOffice"]) == 12 and got["counts"]["waitingOnOffice"] == 20
