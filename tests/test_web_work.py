"""The Work loaders and writer (``jason.web.extra.work``): the open runs by whose move it is, one run, the catalog of
definitions, and the small acts in the signer's own name. Made-up definitions ("example-cycle"), people, and dates (2099) in a
tmp data folder with its own lock folder; nothing reaches Google, Keeper, or PayHOA.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
import webclient

from jason.approvals import model
from jason.workflows import api, definitions, resume, store
from jason.workflows.readers import StoreReaders
from jason.workflows.types import ClockBasis, ClockDef, EventKind
from test_workflows_readers import make_approval
from test_workflows_support import C1, C2, C3, C4, C5, C6, DATES, example_cycle

ROWS = webclient.ROSTER + (("Rae Roster", "", "rae@example.org", False),)
TODAY = date(2099, 9, 20)
LOADERS = ("work", "work-run", "work-definitions")
SUBJECT = "campaign:EX-2099"
MANAGER, TREASURER, SECRETARY, ADMIN = "A Manager", "Pat Example", "Sam Secretary", "Ada Admin"
ROLES = {MANAGER: ["manager"], TREASURER: ["treasurer"], SECRETARY: ["secretary"]}


def roles_of(by):
    return ROLES.get(by, ())


def variant(key, *, c5=None, dates=True):
    """example-cycle under another key: its wait step with a document's date (not the law's), or with no date at all."""
    base = example_cycle()
    steps = tuple(replace(s, clock=c5, legal=False) if s.id == C5 else s for s in base.steps)
    over = dict(key=key, title=f"Variant {key}", steps=steps, clocks=())
    if not dates:
        over["dates"] = ()
    return example_cycle(**over)


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    monkeypatch.setenv("JASON_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: tmp_path)
    monkeypatch.setattr("jason.web.extra.work._today", lambda: TODAY)
    monkeypatch.setattr("jason.web.extra.work._community", lambda: None)
    definitions.reset()
    kw = dict(plan_kinds={"example-plan"}, jobs={"example-report"})
    definitions.register(example_cycle(), **kw)
    definitions.register(variant("example-plain", c5=ClockDef(ClockBasis.DOCUMENTS, "answers_by", 0, cite="the example document")), **kw)
    definitions.register(variant("example-undated", dates=False), **kw)
    yield tmp_path
    definitions.reset()


@pytest.fixture
def app(world):
    from jason.web.app import create_app
    from jason.web.extra import work as w

    dist = world / "dist"
    dist.mkdir(exist_ok=True)
    loaders = {"work": w.work, "work-run": w.work_run, "work-definitions": w.work_definitions}
    return create_app(dist, loaders, approvals_live=None, extra_writes=True, sign_in=webclient.roster_sign_in(ROWS, dev=True))


def as_(app, name):
    return webclient.sign_in(webclient.client(app), name, rows=ROWS)


def start(root, definition="example-cycle", *, subject=SUBJECT, label="Example cycle 2099", dates=None, by=MANAGER, open_=True,
          items=()):
    dates = DATES if dates is None else dates
    rid = api.start(root, definition, subject, label, dates, by, items=items, yes=True, today=TODAY, at="2099-09-15T09:00:00Z")["run"]["id"]
    if open_:
        api.open_run(root, rid, by, readers=StoreReaders(root, today=TODAY), yes=True, today=TODAY, at="2099-09-15T09:01:00Z")
    return rid


def to_wait(root, rid):
    """C1 to C4 done, so the wait at C5 begins."""
    api.attest(root, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", today=TODAY)
    store.append(root, "example-cycle", rid, EventKind.APPLIED, by="jason", step=C3, detail={"approval": "ap-1"})
    store.append(root, "example-cycle", rid, EventKind.JOB_FINISHED, by="jason", step=C4, detail={"ok": True, "job": "job-1"})


def to_decision(root, rid):
    to_wait(root, rid)
    api.arrived(root, rid, C5, MANAGER, roles_of=roles_of, what="the answer", today=TODAY)


def listed(app, who, query=""):
    r = as_(app, who).get("/api/work" + query)
    assert r.status_code == 200, (who, query, r.status_code, r.get_data(as_text=True)[:300])
    return r.json


def page(app, who, rid, definition="example-cycle"):
    r = as_(app, who).get(f"/api/work-run?definition={definition}&id={rid}")
    assert r.status_code == 200, (who, r.status_code, r.get_data(as_text=True)[:300])
    return r.json


def post(c, key, body):
    return c.post(f"/api/write/work/{key}", json=body)


def snapshot(root: Path):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file() and "locks" not in p.parts}


# --- who may read them ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", LOADERS)
def test_signed_out_is_a_401_and_a_roster_person_with_no_office_is_a_403(app, world, name):
    rid = start(world)
    url = f"/api/{name}?definition=example-cycle&id={rid}"
    assert webclient.client(app).get(url).status_code == 401
    r = as_(app, "Rae Roster").get(url)
    assert r.status_code == 403
    assert "open contact details and members' submissions (P2)" in r.json["error"]        # access.may_see's sentence


@pytest.mark.parametrize("name", LOADERS)
def test_an_admin_with_no_office_passes_the_gate_and_reads_the_board_s_runs_not_at_all(app, world, name):
    """The administrator's own definitions need the administrator; the board's runs stay the board's (``work_scope``)."""
    rid = start(world)
    r = as_(app, ADMIN).get(f"/api/{name}?definition=example-cycle&id={rid}")
    assert r.status_code == (404 if name == "work-run" else 200), r.get_data(as_text=True)[:200]
    admins = {"integration-connect", "service-run", "check-in"}
    if name == "work":
        assert r.json["runs"] == [] and r.json["counts"]["open"] == 0
        assert {d["key"] for d in r.json["definitions"]} == admins
    if name == "work-definitions":
        assert {d["key"] for d in r.json["definitions"]} == admins


@pytest.mark.parametrize("who", ("Pat Example", "Dana Director", "Sam Secretary", "Lee President", "Vic Vice", "Tess Two", "A Manager"))
def test_the_manager_and_every_board_office_read_all_three(app, world, who):
    rid = start(world)
    assert listed(app, who)["found"] is True
    assert page(app, who, rid)["run"]["id"] == rid
    r = as_(app, who).get("/api/work-definitions")
    assert r.status_code == 200 and r.json["counts"]["definitions"] >= 3


def test_the_owner_view_never_reads_them_and_they_are_no_owner_source(app):
    from jason.web.extra.owner_view import OWNER_SOURCES
    from jason.web.sources import EXTRA_LOADERS, EXTRA_WRITERS

    c = as_(app, TREASURER)
    for name in LOADERS:
        assert name not in OWNER_SOURCES
        assert EXTRA_LOADERS[name].startswith("jason.web.extra.work:")
        assert c.get(f"/api/{name}?view=owner").status_code in (401, 403)
    assert EXTRA_WRITERS["work"] == "jason.web.extra.work:write"


def test_a_missing_argument_is_a_400_after_the_gate_and_a_missing_run_a_404(app, world):
    assert webclient.client(app).get("/api/work-run").status_code == 401
    assert as_(app, "Rae Roster").get("/api/work-run").status_code == 403
    assert as_(app, TREASURER).get("/api/work-run").status_code == 400
    rid = start(world)
    assert as_(app, TREASURER).get(f"/api/work-run?definition=example-cycle&id=run-0000000000").status_code == 404
    assert as_(app, TREASURER).get(f"/api/work-run?definition=example-plain&id={rid}").status_code == 404      # not that definition's run


def test_a_bad_filter_is_a_400(app):
    c = as_(app, TREASURER)
    for q in ("state=nope", "role=chairman", "due=never"):
        assert c.get(f"/api/work?{q}").status_code == 400, q


# --- the list: groups, order, counts -------------------------------------------------------------------------------------------


@pytest.fixture
def runs(world):
    """Five open runs, one of each kind of move, and a draft."""
    ids = {
        "legal": start(world, label="Legal run", dates={"answers_by": "2099-10-23", "closes_on": "2099-11-01"}),
        "plain": start(world, "example-plain", label="Plain run", dates={"answers_by": "2099-10-01", "closes_on": "2099-11-01"}, subject="campaign:P"),
        "undated": start(world, "example-undated", label="Undated run", dates={}, subject="campaign:U"),
        "clock": start(world, label="Clock run", subject="campaign:C"),
        "board": start(world, label="Board run", subject="campaign:B"),
        "draft": start(world, "example-plain", label="Draft run", subject="campaign:D", open_=False,
                       dates={"answers_by": "2099-10-05", "closes_on": "2099-11-01"}),
    }
    to_wait(world, ids["clock"])
    to_decision(world, ids["board"])
    return ids


def rows_by(listing):
    return {r["label"]: r for r in listing["runs"]}


def test_a_run_is_once_in_the_group_of_its_most_pressing_step(app, runs):
    got = rows_by(listed(app, MANAGER))
    assert {k: v["group"] for k, v in got.items()} == {
        "Legal run": "yours", "Plain run": "yours", "Undated run": "yours", "Clock run": "clock", "Board run": "board",
        "Draft run": "yours"}
    assert len(listed(app, MANAGER)["runs"]) == 6
    others = rows_by(listed(app, TREASURER))
    assert others["Legal run"]["group"] == "others" and others["Legal run"]["waitingOn"]["word"] == "the manager"
    assert others["Draft run"]["group"] == "others" and others["Draft run"]["waitingOn"]["kind"] == "open"
    assert others["Clock run"]["group"] == "clock" and others["Clock run"]["waitingOn"]["word"] == "a clock"
    assert others["Board run"]["group"] == "board" and others["Board run"]["waitingOn"]["word"] == "the board; the secretary records"
    assert rows_by(listed(app, SECRETARY))["Board run"]["mine"] is True and others["Board run"]["mine"] is False


def test_within_a_group_a_legal_date_comes_first_then_the_nearest_then_none(app, runs):
    mine = [r["label"] for r in listed(app, MANAGER)["runs"] if r["group"] == "yours"]
    # the legal date (Oct 23) before the nearer documents dates (Oct 1, then the draft's Oct 5), and the run with no date last
    assert mine == ["Legal run", "Plain run", "Draft run", "Undated run"]
    got = rows_by(listed(app, MANAGER))
    assert got["Legal run"]["due"]["basis"] == "law" and got["Legal run"]["due"]["basisLabel"] == "LEGAL"
    assert got["Plain run"]["due"]["basis"] == "documents" and got["Plain run"]["due"]["date"] == "2099-10-01"
    assert got["Undated run"]["due"] is None
    flat = [r["group"] for r in listed(app, MANAGER)["runs"]]
    assert flat == sorted(flat, key=["yours", "others", "clock", "board"].index)


def test_a_row_carries_the_step_the_role_the_position_and_an_age_and_no_subject_item_or_name(app, runs, world):
    row = rows_by(listed(app, MANAGER))["Legal run"]
    assert row["current"] == {"id": C2, "title": "Send the example notice to 123 Main St", "n": 2, "of": 6, "kind": "person",
                              "state": "needs a person", "role": "manager"}
    assert row["owner"] == "manager" and row["definition"] == "example-cycle" and row["state"] == "active"
    assert row["age"]["opened"] == "2099-09-15" and row["age"]["days"] == 5
    assert "subject" not in row and "items" not in row
    body = json.dumps(listed(app, TREASURER))
    for forbidden in ("campaign:", "EX-2099", MANAGER, "Pat Example"):
        assert forbidden not in body, forbidden


def test_a_run_with_items_never_shows_them_in_the_list(app, world):
    start(world, label="Item run", items=("unit-7", "unit-9"))
    assert "unit-7" not in json.dumps(listed(app, MANAGER))


def test_the_counts_are_the_whole_picture_and_the_filters_narrow_the_list(app, runs):
    got = listed(app, MANAGER)
    assert got["counts"]["open"] == 6 and got["counts"]["yours"] == 4 and got["counts"]["clock"] == 1 and got["counts"]["board"] == 1
    assert got["counts"]["dueThisWeek"] == 0 and got["counts"]["pastLegal"] == 0
    mine = listed(app, MANAGER, "?mine=1")
    assert mine["shown"] == 4 and all(r["group"] == "yours" for r in mine["runs"]) and mine["counts"]["open"] == 6
    assert {r["label"] for r in listed(app, MANAGER, "?definition=example-plain")["runs"]} == {"Plain run", "Draft run"}
    assert {r["label"] for r in listed(app, MANAGER, "?role=secretary")["runs"]} == {"Board run"}
    assert {r["label"] for r in listed(app, MANAGER, "?q=plain")["runs"]} == {"Plain run", "Draft run"}      # the definition's title
    assert {r["label"] for r in listed(app, MANAGER, "?due=legal")["runs"]} == {"Legal run", "Clock run"}      # the board run's law date is met
    assert listed(app, MANAGER, "?state=done")["shown"] == 0


def test_no_open_runs_says_so(app, world):
    got = listed(app, MANAGER)
    assert got["runs"] == [] and got["counts"]["open"] == 0 and got["empty"].startswith("No runs are open")
    assert [g["key"] for g in got["groups"]] == ["yours", "others", "clock", "board"]
    assert [g["title"] for g in got["groups"]] == ["Yours", "Waiting on others", "Waiting on a clock", "The board"]


def test_a_run_past_a_legal_date_is_counted(app, world):
    rid = start(world, dates={"answers_by": "2099-09-01", "closes_on": "2099-11-01"})
    to_wait(world, rid)
    got = listed(app, MANAGER)
    assert got["counts"]["pastLegal"] == 1 and got["counts"]["overdue"] >= 1
    row = got["runs"][0]
    assert row["pastLaw"] is True and row["due"]["status"] == "overdue" and row["due"]["days"] < 0
    assert listed(app, MANAGER, "?due=past")["shown"] == 1 and listed(app, MANAGER, "?due=overdue")["shown"] == 1


def test_a_run_that_cannot_be_read_or_has_no_definition_is_said_not_hidden(app, world):
    start(world)
    bad = world / "workflows" / "example-cycle" / "run-0123456789.jsonl"
    bad.write_text("not an event\n", encoding="utf-8")
    ghost = start(world, "example-plain", dates={"answers_by": "2099-10-01", "closes_on": "2099-11-01"})
    definitions.unregister("example-plain")
    got = listed(app, MANAGER)
    problems = {p["what"]: p["why"] for p in got["problems"]}
    assert "could not be read" in problems["Run run-0123456789"]
    assert "not registered" in problems[f"Run {ghost}"]
    assert len(got["runs"]) == 1
    assert {n["what"] for n in got["notComposed"]} >= {"Executive-session runs (CIV 4935(e))"}


# --- one run -------------------------------------------------------------------------------------------------------------------


def test_one_run_has_its_steps_clocks_links_history_and_what_it_could_not_compose(app, world):
    rid = start(world)
    got = page(app, MANAGER, rid)
    run = got["run"]
    assert run["id"] == rid and run["state"] == "active" and run["label"] == "Example cycle 2099" and run["subject"] == SUBJECT
    assert run["current"] == {"id": C2, "title": "Send the example notice to 123 Main St", "n": 2, "of": 6}
    assert run["dates"] == DATES and run["openedBy"] == MANAGER and run["n"] == 3
    assert [s["id"] for s in got["steps"]] == [C1, C2, C3, C4, C5, C6]
    c1, c2, c3, c4, c5, c6 = got["steps"]
    assert c1["state"] == "done" and c1["by"] == "jason" and c2["state"] == "needs a person" and c2["current"] is True
    assert c2["phase"] == "prepare" and c2["phaseTitle"] == "Prepare" and c2["command"] == "example notice --send"
    assert c2["needsRecord"] == "the sent-notice reference" and c2["yours"] is True and c2["acts"] == ["attest", "skip"]
    assert c2["waitingOn"] == {"kind": "office", "word": "the manager", "role": "manager", "detail": ""}
    assert c3["state"] == "not started" and c3["plan"]["kind"] == "example-plan" and c3["plan"]["screen"] == "approvals"
    assert c4["job"]["name"] == "example-report"
    assert c5["legal"] is True and c5["clock"]["basis"] == "law" and c5["clock"]["cite"] == "EX 123.4"
    assert c5["skip"] is None and c5["notOffered"]["skip"] == "Skip is not offered: this step is required by the law."
    assert c6["kind"] == "decision" and c6["decision"]["recorded"] is False and c6["decision"]["screen"] == "decisions"
    assert "attest" not in c6["acts"] and "Decisions" in c6["notOffered"]["attest"]
    assert [p["key"] for p in got["phases"]] == ["prepare", "act", "close"]
    by_key = {c["key"]: c for c in got["clocks"]}
    assert by_key[C5]["basis"] == "law" and by_key[C5]["basisLabel"] == "LEGAL" and by_key[C5]["due"] == "2099-10-23"
    assert by_key["run.0"]["basis"] == "person" and by_key["run.0"]["scope"] == "run"
    assert got["history"][0]["n"] > got["history"][-1]["n"] and got["history"][-1]["kind"] == "opened"      # newest first
    assert got["history"][-1]["text"] == f"{MANAGER} started the run as a draft"
    assert got["pending"] == [] and got["changed"] == []
    assert {n["what"] for n in got["notComposed"]} >= {"Executive-session runs (CIV 4935(e))", "The decision's mover, second, and vote"}


def test_a_step_that_is_not_the_viewers_shows_who_it_waits_on_and_no_act(app, world):
    rid = start(world)
    c2 = page(app, TREASURER, rid)["steps"][1]
    assert c2["yours"] is False and c2["acts"] == [] and c2["notOffered"]["attest"] == "Waiting on the manager."
    assert c2["waitingOn"]["word"] == "the manager"
    assert "skip" in c2["notOffered"] and "manager" in c2["notOffered"]["skip"]


def test_the_run_acts_follow_its_state_and_a_legal_cancel_needs_yes(app, world):
    rid = start(world)
    acts = page(app, MANAGER, rid)["run"]["acts"]
    assert acts["pause"]["offered"] and acts["note"]["offered"] and not acts["resume"]["offered"] and not acts["open"]["offered"]
    assert acts["cancel"]["offered"] and acts["cancel"]["needsYes"] is True
    assert page(app, TREASURER, rid)["run"]["acts"]["cancel"]["offered"] is False       # only the secretary or the manager
    draft = start(world, subject="campaign:D", open_=False)
    assert page(app, MANAGER, draft)["run"]["acts"]["open"] == {"offered": True, "why": "", "needsYes": True}


def test_a_decision_step_shows_the_record_the_secretary_made_and_a_plan_the_approval_it_links(app, world):
    rid = start(world)
    to_decision(world, rid)
    api.attest(world, rid, C6, SECRETARY, roles_of=roles_of, record="minutes-1", outcome="adopted", motion="Adopt the example result", today=TODAY)
    got = page(app, SECRETARY, rid)
    c3, c6 = got["steps"][2], got["steps"][5]
    assert c3["plan"]["approval"] == "ap-1" and c3["state"] == "done" and c3["acts"] == []          # the secretary holds no manager step
    assert c6["decision"] == {"recorded": True, "motion": "Adopt the example result", "outcome": "adopted", "record": "minutes-1",
                              "by": SECRETARY, "at": c6["at"], "final": True, "screen": "decisions"}
    assert got["run"]["state"] == "done"
    link = next(l for l in got["links"] if l["kind"] == "approval")
    assert link["id"] == "ap-1" and link["read"] is False                      # its store has no such approval
    assert any(p["what"] == "The approval ap-1" for p in got["problems"])


def test_history_names_only_the_accounts_that_acted_and_masks_what_a_person_typed(app, world):
    rid = start(world, items=("unit-7",))
    c = as_(app, MANAGER)
    r = post(c, f"example-cycle/{rid}", {"act": "note", "text": "Call Olive Owner at olive@example.org or 916-555-0100 about unit-7"})
    assert r.status_code == 200, r.json
    got = page(app, TREASURER, rid)
    text = json.dumps(got["history"])
    assert "olive@example.org" not in text and "916-555-0100" not in text
    note = got["history"][0]
    assert note["kind"] == "note" and note["by"] == MANAGER and note["text"].startswith(f"{MANAGER} noted on the run: Call Olive Owner at o")
    opened = got["history"][-1]
    assert opened["detail"]["itemCount"] == 1 and "unit-7" not in json.dumps(opened)
    names = {e["by"] for e in got["history"]}
    assert names <= {MANAGER, "jason"}
    assert "/api/file" not in json.dumps(got)


def test_no_absolute_path_reaches_a_run_page(app, world):
    rid = start(world)
    store.append(world, "example-cycle", rid, EventKind.NOTE, by=MANAGER, detail={"text": "see it", "evidence": ["file:C:\\secret\\x.txt@abc", "file:/etc/x@abc"]})
    text = json.dumps(page(app, MANAGER, rid))
    assert "C:\\" not in text and "/etc/x" not in text and "(a path outside the data folder)" in text


# --- a GET appends nothing, and shows what opening would -----------------------------------------------------------------------------


def test_a_get_appends_nothing_and_shows_what_opening_the_run_would(app, world):
    rid = api.start(world, "example-cycle", SUBJECT, "Example cycle 2099", DATES, MANAGER, yes=True, today=TODAY, at="2099-09-15T09:00:00Z")["run"]["id"]
    store.append(world, "example-cycle", rid, EventKind.RESUMED, by=MANAGER, detail={"activated": True})      # active, never resumed
    before = snapshot(world)
    got = page(app, MANAGER, rid)
    assert [p["kind"] for p in got["pending"]] == ["check-ran"] and got["pending"][0]["step"] == C1
    assert got["steps"][0]["state"] == "done" and got["steps"][1]["state"] == "needs a person"
    assert got["history"][0]["pending"] is True and got["history"][0]["kind"] == "check-ran"
    assert got["run"]["n"] == 2                                  # the stored n, for the compare-and-swap
    for name in ("/api/work", "/api/work-definitions", "/api/work-definitions?key=example-cycle"):
        assert as_(app, MANAGER).get(name).status_code == 200
    assert snapshot(world) == before                              # byte-identical: no run file, no index, no lock written
    assert store.read(world, "example-cycle", rid).n == 2
    # opening it (the act, or the terminal) is what writes the same event
    r = post(as_(app, MANAGER), f"example-cycle/{rid}", {"act": "open", "yes": True})
    assert r.status_code == 200 and [e["kind"] for e in r.json["appended"]] == ["check-ran"]
    assert page(app, MANAGER, rid)["pending"] == []


def test_a_store_that_moved_under_a_done_step_reads_changed_since_and_nothing_done_is_repeated(app, world):
    steps = tuple(replace(s, evidence=("file:forms/f.json",)) if s.id == C2 else s for s in example_cycle().steps)
    definitions.register(example_cycle(key="example-files", steps=steps), plan_kinds={"example-plan"}, jobs={"example-report"})
    (world / "forms").mkdir()
    (world / "forms" / "f.json").write_text('{"questions": 3}', encoding="utf-8")
    rid = start(world, "example-files")
    api.attest(world, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", readers=StoreReaders(world, today=TODAY), today=TODAY)
    assert page(app, MANAGER, rid, "example-files")["changed"] == []
    (world / "forms" / "f.json").write_text('{"questions": 5}', encoding="utf-8")
    before = snapshot(world)
    got = page(app, MANAGER, rid, "example-files")
    assert snapshot(world) == before
    assert len(got["changed"]) == 1 and got["changed"][0]["step"] == C2 and got["changed"][0]["address"] == "file:forms/f.json"
    assert got["changed"][0]["pending"] is True and got["changed"][0]["was"] != got["changed"][0]["now"]
    c2 = got["steps"][1]
    assert c2["state"] == "done" and c2["changed"] and c2["evidence"][0]["changed"] is True
    assert [p["kind"] for p in got["pending"]] == ["changed"]
    # opening records it once; a second open appends nothing
    c = as_(app, MANAGER)
    assert [e["kind"] for e in post(c, f"example-files/{rid}", {"act": "open"}).json["appended"]] == ["changed"]
    assert post(c, f"example-files/{rid}", {"act": "open"}).json["appended"] == []
    again = page(app, MANAGER, rid, "example-files")
    assert len(again["changed"]) == 1 and again["changed"][0]["pending"] is False and again["pending"] == []


def test_a_law_clock_recites_the_statutes_words_whole_then_jasons_reading(app, world, monkeypatch):
    from jason.community import law_text

    rid = start(world)
    missing = page(app, MANAGER, rid)
    law = next(c for c in missing["clocks"] if c["basis"] == "law")["law"]
    assert law["words"] == "" and "does not hold EX 123.4" in law["missing"] and law["readingLabel"] == "jason's reading, not the provision"
    assert any(p["what"] == "The words of EX 123.4" for p in missing["problems"])
    words = law_text.LawText("EX 123", "Whoever must answer shall answer by the day named.", "abc123def456", source="Example Legislature")
    monkeypatch.setattr(law_text, "quoted", lambda cite, root, day=None: law_text.Quoted("EX 123.4", TODAY, (words,), words))
    got = page(app, MANAGER, rid)
    law = next(c for c in got["clocks"] if c["basis"] == "law")["law"]
    assert law["words"] == "Whoever must answer shall answer by the day named." and law["source"] == "Example Legislature"
    assert law["reading"] == "Wait for the Example Alarm answer"
    assert "not an official restatement" in law["restatement"]
    assert not any(p["what"] == "The words of EX 123.4" for p in got["problems"])


# --- the catalog -------------------------------------------------------------------------------------------------------------------


def test_the_catalog_lists_every_definition_once_with_drift_and_reads_one_whole(app, world):
    c = as_(app, MANAGER)
    got = c.get("/api/work-definitions").json
    keys = [d["key"] for d in got["definitions"]]
    assert sorted(keys) == sorted(set(keys)) and {"example-cycle", "example-plain", "example-undated", "owner-info-cycle"} <= set(keys)
    assert got["counts"]["definitions"] == len(keys) == sum(len(f["definitions"]) for f in got["families"])
    one = next(d for d in got["definitions"] if d["key"] == "example-cycle")
    assert one["steps"] == 6 and one["family"] == "example" and one["legalClock"] is True and one["startable"] is True
    assert one["drift"]["ok"] is False and "example-procedure" in one["drift"]["why"][0]       # the made-up procedure does not exist
    assert got["counts"]["drifted"] >= 1
    oi = next(d for d in got["definitions"] if d["key"] == "owner-info-cycle")
    assert oi["drift"]["ok"] is True and oi["procedureSteps"] == 20 and oi["family"] == "members" and oi["lessons"]
    assert {d["name"] for d in oi["dates"]} == {"opens_on", "return_by", "reports_mailed"}
    assert {n["what"] for n in got["notComposed"]} >= {"How often a workflow runs", "Who may start a workflow"}
    whole = c.get("/api/work-definitions?key=example-cycle").json["definition"]
    assert [s["id"] for s in whole["steps"]] == [C1, C2, C3, C4, C5, C6]
    assert whole["steps"][4]["clock"]["basis"] == "law" and whole["steps"][4]["clock"]["law"]["missing"]
    assert whole["steps"][1]["skip"] == {"roles": ["manager"], "reasonRequired": True}
    assert c.get("/api/work-definitions?key=nope").status_code == 404


def test_the_catalog_filters_by_family_role_and_my_office(app, world):
    c = as_(app, TREASURER)
    members = c.get("/api/work-definitions?family=members").json
    assert "owner-info-cycle" in [d["key"] for d in members["definitions"]]
    assert {d["family"] for d in members["definitions"]} == {"members"}
    mine = c.get("/api/work-definitions?mine=1").json                    # the treasurer holds only an `anyone` step: putting a control before the board
    assert "control-adoption" in [d["key"] for d in mine["definitions"]]
    sec = as_(app, SECRETARY).get("/api/work-definitions?mine=1").json
    assert {"example-cycle", "owner-info-cycle"} <= {d["key"] for d in sec["definitions"]}
    admin_defs = as_(app, SECRETARY).get("/api/work-definitions?role=administrator&family=members").json["definitions"]
    assert "owner-info-cycle" in [d["key"] for d in admin_defs]
    assert c.get("/api/work-definitions?role=chairman").status_code == 400


# --- the writer ----------------------------------------------------------------------------------------------------------------------


def test_attest_is_recorded_under_the_signers_own_name_with_the_record_it_asks_for(app, world):
    rid = start(world)
    c = as_(app, MANAGER)
    r = post(c, f"example-cycle/{rid}", {"act": "attest", "step": C2, "record": "notice-1", "what": "sent the notice"})
    assert r.status_code == 200, r.json
    assert r.json["act"] == "attest" and r.json["by"] == MANAGER and r.json["event"]["by"] == MANAGER and r.json["event"]["kind"] == "attested"
    assert r.json["run"]["steps"][1]["state"] == "done" and r.json["run"]["steps"][1]["by"] == MANAGER
    assert store.read(world, "example-cycle", rid).events[-1].by == MANAGER
    assert post(c, f"example-cycle/{rid}", {"act": "attest", "step": C2, "record": "again", "by": MANAGER}).status_code == 400   # already done


def test_a_body_by_naming_someone_else_is_a_403_and_writes_nothing(app, world):
    rid = start(world)
    n = store.read(world, "example-cycle", rid).n
    c = as_(app, MANAGER)
    r = post(c, f"example-cycle/{rid}", {"act": "attest", "step": C2, "record": "notice-1", "by": "Somebody Else"})
    assert r.status_code == 403 and "Somebody Else" in r.json["error"]
    assert store.read(world, "example-cycle", rid).n == n
    assert post(c, f"example-cycle/{rid}", {"act": "attest", "step": C2, "record": "notice-1", "by": MANAGER}).status_code == 200


def test_the_writer_itself_refuses_a_by_naming_someone_else_even_without_the_sign_in_guard(app):
    from werkzeug.exceptions import HTTPException

    from jason.web.extra import work as w

    viewer = type("V", (), {"account": MANAGER, "offices": frozenset({"manager"}), "admin": False, "acting": False, "label": MANAGER})()
    with app.test_request_context("/api/write/work/x", method="POST"):
        with pytest.raises(HTTPException) as caught:
            w._signer(viewer, {"by": "Somebody Else"})
        assert caught.value.response.status_code == 403
        assert w._signer(viewer, {"by": MANAGER.lower()})[0] == MANAGER
        assert w._signer(viewer, {})[1].roles_of(MANAGER) == ("manager",) and w._signer(viewer, {})[1].roles_of("x") == ()


def test_a_wrong_role_is_refused_with_the_engines_sentence(app, world):
    rid = start(world)
    r = post(as_(app, TREASURER), f"example-cycle/{rid}", {"act": "attest", "step": C2, "record": "notice-1"})
    assert r.status_code == 403 and r.json["error"] == f"{TREASURER} does not hold the manager role that {C2} needs"
    assert store.read(world, "example-cycle", rid).n == 3


def test_a_step_that_needs_a_record_refuses_without_it_in_the_definitions_sentence(app, world):
    rid = start(world)
    r = post(as_(app, MANAGER), f"example-cycle/{rid}", {"act": "attest", "step": C2})
    assert r.status_code == 400 and "the step asks for a record (the sent-notice reference)" in r.json["error"]


def test_a_legal_step_has_no_skip_and_the_engines_sentence_is_the_answer(app, world):
    rid = start(world)
    to_wait(world, rid)
    r = post(as_(app, MANAGER), f"example-cycle/{rid}", {"act": "skip", "step": C5, "reason": "not needed"})
    assert r.status_code == 400 and r.json["error"] == f"{C5} cannot be skipped: it is a legal step"
    assert page(app, MANAGER, rid)["steps"][4]["state"] == "waiting"


def test_skip_needs_the_role_and_a_reason_where_the_definition_allows_it(app, world):
    rid = start(world)
    c = as_(app, MANAGER)
    assert post(c, f"example-cycle/{rid}", {"act": "skip", "step": C2}).status_code == 400
    assert post(as_(app, TREASURER), f"example-cycle/{rid}", {"act": "skip", "step": C2, "reason": "x"}).status_code == 403
    r = post(c, f"example-cycle/{rid}", {"act": "skip", "step": C2, "reason": "the notice was hand-delivered"})
    assert r.status_code == 200 and r.json["run"]["steps"][1]["state"] == "skipped"
    assert r.json["event"]["detail"]["reason"] == "the notice was hand-delivered"


def test_a_decision_a_plan_and_a_wait_are_not_taken_here(app, world):
    rid = start(world)
    to_decision(world, rid)
    c = as_(app, SECRETARY)
    r = post(c, f"example-cycle/{rid}", {"act": "attest", "step": C6, "record": "minutes-1", "outcome": "adopted"})
    assert r.status_code == 400 and r.json["error"].startswith("A decision is recorded in Decisions")
    assert store.read(world, "example-cycle", rid).events[-1].kind is EventKind.ARRIVED
    plan = post(as_(app, MANAGER), f"example-cycle/{rid}", {"act": "attest", "step": C3, "record": "x"})
    assert plan.status_code == 400 and "Approvals" in plan.json["error"]


def test_arrived_ends_a_wait_the_role_holds(app, world):
    rid = start(world)
    to_wait(world, rid)
    assert post(as_(app, TREASURER), f"example-cycle/{rid}", {"act": "arrived", "step": C5}).status_code == 403
    r = post(as_(app, MANAGER), f"example-cycle/{rid}", {"act": "arrived", "step": C5, "what": "the answer came"})
    assert r.status_code == 200 and r.json["run"]["steps"][4]["state"] == "done" and r.json["run"]["steps"][5]["state"] == "needs a person"


def test_pause_resume_note_reopen_and_cancel_are_each_the_engines_own(app, world):
    rid = start(world)
    c = as_(app, MANAGER)
    key = f"example-cycle/{rid}"
    assert post(c, key, {"act": "pause"}).status_code == 400                       # a pause needs a reason
    paused = post(c, key, {"act": "pause", "reason": "waiting on the board"})
    assert paused.status_code == 200 and paused.json["run"]["run"]["state"] == "paused"
    assert paused.json["run"]["run"]["pausedReason"] == "waiting on the board"
    row = rows_by(listed(app, MANAGER))["Example cycle 2099"]
    assert row["paused"] is True and row["group"] == "others" and row["waitingOn"]["kind"] == "paused"
    assert post(c, key, {"act": "attest", "step": C2, "record": "r"}).status_code == 400            # a paused run is not acted on
    assert post(c, key, {"act": "resume"}).status_code == 200
    assert post(c, key, {"act": "note", "text": ""}).status_code == 400
    noted = post(c, key, {"act": "note", "text": "check with the board", "step": C2})
    assert noted.status_code == 200 and noted.json["event"]["step"] == C2
    post(c, key, {"act": "attest", "step": C2, "record": "r"})
    assert post(as_(app, TREASURER), key, {"act": "reopen", "step": C2, "reason": "x"}).status_code == 403
    assert post(c, key, {"act": "reopen", "step": C2}).status_code == 400
    assert post(c, key, {"act": "reopen", "step": C2, "reason": "wrong notice"}).json["run"]["steps"][1]["state"] == "needs a person"
    # a run with a legal clock still to come is cancelled only with yes, and only by the secretary or the manager
    assert post(c, key, {"act": "cancel", "reason": "no longer needed"}).json["error"].endswith("cancelling it needs yes")
    assert post(as_(app, TREASURER), key, {"act": "cancel", "reason": "x", "yes": True}).status_code == 403
    done = post(c, key, {"act": "cancel", "reason": "no longer needed", "yes": True})
    assert done.status_code == 200 and done.json["run"]["run"]["state"] == "cancelled"
    assert done.json["run"]["run"]["cancelledReason"] == "no longer needed"
    assert listed(app, MANAGER)["runs"] == []                                      # a cancelled run is no longer open
    assert [r["state"] for r in listed(app, MANAGER, "?state=cancelled")["runs"]] == ["cancelled"]


def test_a_run_that_moved_on_is_a_409_naming_the_n(app, world):
    rid = start(world)
    c = as_(app, MANAGER)
    r = post(c, f"example-cycle/{rid}", {"act": "note", "text": "hello", "expect": 1})
    assert r.status_code == 409 and "changed" in r.json["error"] and r.json["actual"] == 3
    assert post(c, f"example-cycle/{rid}", {"act": "note", "text": "hello", "expect": 3}).status_code == 200
    assert post(c, f"example-cycle/{rid}", {"act": "note", "text": "hello", "expect": "soon"}).status_code == 400


def test_an_unknown_act_run_or_definition_is_refused(app, world):
    rid = start(world)
    c = as_(app, MANAGER)
    assert post(c, f"example-cycle/{rid}", {"act": "approve"}).status_code == 400
    assert post(c, f"example-cycle/{rid}", {}).status_code == 400
    assert post(c, "example-cycle/run-0000000000", {"act": "note", "text": "x"}).status_code == 404
    assert post(c, f"example-plain/{rid}", {"act": "note", "text": "x"}).status_code == 404
    assert post(c, "example-cycle", {"act": "note", "text": "x"}).status_code == 404
    assert post(c, f"example-cycle/{rid}", {"act": "attest"}).status_code == 400            # a step is required


def test_the_writer_needs_a_sign_in_and_an_office(app, world):
    rid = start(world)
    n = store.read(world, "example-cycle", rid).n
    body = {"act": "note", "text": "hello"}
    assert post(webclient.client(app), f"example-cycle/{rid}", body).status_code == 401
    assert post(as_(app, "Rae Roster"), f"example-cycle/{rid}", body).status_code == 403
    assert post(as_(app, ADMIN), f"example-cycle/{rid}", body).status_code == 404       # an administrator with no office: not the board's run
    assert store.read(world, "example-cycle", rid).n == n


def test_nobody_writes_while_an_admin_views_as_someone_else(app, world):
    rid = start(world)
    n = store.read(world, "example-cycle", rid).n
    c = as_(app, ADMIN)
    with c.session_transaction() as s:
        s["acting"] = {"name": MANAGER, "role": "manager"}
    r = post(c, f"example-cycle/{rid}", {"act": "attest", "step": C2, "record": "notice-1"})
    assert r.status_code == 403 and "writes are refused" in r.json["error"]
    assert store.read(world, "example-cycle", rid).n == n
    # the writer's own refusal, for a request that got past the sign-in guard
    from jason.web.extra import work as w

    seen = c.get(f"/api/work-run?definition=example-cycle&id={rid}")
    assert seen.status_code == 200
    assert all(not a["offered"] for k, a in seen.json["run"]["acts"].items())
    assert seen.json["steps"][1]["acts"] == [] and seen.json["steps"][1]["notOffered"]["attest"].startswith("Viewing as ")
    assert w.ACTING_REFUSED.startswith("Viewing as {who} (admin view): go back to yourself first")


# --- start, and open -------------------------------------------------------------------------------------------------------------------


def test_start_makes_a_draft_in_the_signers_name_after_the_definitions_own_date_checks(app, world):
    c = as_(app, MANAGER)
    body = {"subject": SUBJECT, "label": "Started on the web", "dates": {"answers_by": "2099-10-23", "closes_on": "2099-11-01"}, "yes": True}
    r = post(c, "example-cycle/start", body)
    assert r.status_code == 200, r.json
    rid = r.json["id"]
    assert r.json["run"]["run"]["state"] == "draft" and r.json["run"]["run"]["openedBy"] == MANAGER
    assert store.read(world, "example-cycle", rid).events[0].by == MANAGER
    assert rows_by(listed(app, MANAGER))["Started on the web"]["state"] == "draft"
    # the same through the bare route with the definition in the body
    r2 = post(c, "start", {**body, "definition": "example-plain", "label": "Second", "subject": "campaign:S"})
    assert r2.status_code == 200 and r2.json["definition"] == "example-plain"


def test_start_checks_the_dates_says_so_and_needs_yes_for_a_legal_clock(app, world):
    c = as_(app, MANAGER)
    base = {"subject": SUBJECT, "label": "x", "dates": {"answers_by": "2099-11-02", "closes_on": "2099-11-01"}}
    r = post(c, "example-cycle/start", {**base, "yes": True})
    assert r.status_code == 400 and "closes_on (2099-11-01) comes before answers_by (2099-11-02)" in r.json["error"]
    assert post(c, "example-cycle/start", {**base, "dates": DATES}).json["error"].endswith("has a legal clock: starting it needs yes")
    assert post(c, "example-cycle/start", {"dates": DATES, "yes": True}).status_code == 400            # a subject
    assert post(c, "example-cycle/start", {**base, "dates": DATES, "yes": True, "definition": "example-plain"}).status_code == 400
    assert post(c, "nope/start", {**base, "yes": True}).status_code == 400
    assert post(c, "start", {**base, "yes": True}).status_code == 400
    assert not (world / "workflows" / "example-cycle").exists()
    dry = post(c, "example-cycle/start", {**base, "dryRun": True})
    assert dry.status_code == 200 and dry.json["ok"] is False and dry.json["dryRun"] is True
    assert any("comes before answers_by" in p for p in dry.json["problems"]) and any("needs yes" in p for p in dry.json["problems"])
    ok = post(c, "example-cycle/start", {**base, "dates": DATES, "yes": True, "dryRun": True})
    assert ok.json == {"ok": True, "dryRun": True, "definition": "example-cycle", "problems": []}
    assert not (world / "workflows" / "example-cycle").exists()                         # a dry run writes nothing


def test_open_starts_the_clocks_of_a_draft_with_yes_and_runs_the_resume_check(app, world):
    c = as_(app, MANAGER)
    made = post(c, "example-cycle/start", {"subject": SUBJECT, "label": "Draft", "dates": DATES, "yes": True})
    rid = made.json["id"]
    assert post(c, f"example-cycle/{rid}", {"act": "open"}).json["error"].endswith("opening the run starts it and needs yes")
    r = post(c, f"example-cycle/{rid}", {"act": "open", "yes": True})
    assert r.status_code == 200 and [e["kind"] for e in r.json["appended"]] == ["resumed", "check-ran"]
    assert r.json["run"]["run"]["state"] == "active" and r.json["run"]["steps"][0]["state"] == "done"
    assert all(a["offered"] is False for k, a in r.json["run"]["run"]["acts"].items() if k == "open")


def test_the_owner_information_definition_starts_and_opens_through_the_web(app, world):
    c = as_(app, MANAGER)
    dates = {"opens_on": "2099-09-15", "return_by": "2099-10-23", "reports_mailed": "2099-12-15"}
    r = post(c, "owner-info-cycle/start", {"subject": "campaign:EX", "label": "Owner information 2099", "dates": dates, "yes": True})
    assert r.status_code == 200, r.json
    rid = r.json["id"]
    row = rows_by(listed(app, MANAGER))["Owner information 2099"]
    assert row["group"] == "yours" and row["current"]["of"] == 27 and row["state"] == "draft"
    assert rows_by(listed(app, TREASURER))["Owner information 2099"]["group"] == "others"
    opened = post(c, f"owner-info-cycle/{rid}", {"act": "open", "yes": True})
    assert opened.status_code == 200, opened.json
    got = opened.json["run"]
    assert got["run"]["state"] == "active" and got["run"]["current"]["n"] == 1
    assert got["steps"][0]["waitingOn"]["word"] == "the administrator" and got["steps"][0]["yours"] is False
    assert {c["basis"] for c in got["clocks"]} >= {"law", "proposed policy", "person"}
    row = rows_by(listed(app, MANAGER))["Owner information 2099"]
    assert row["group"] == "others" and row["owner"] == "administrator"
    law = next(c for c in got["clocks"] if c["basis"] == "law")
    assert law["cite"] == "CIV 4041(b)(1)" and law["law"]["readingLabel"] == "jason's reading, not the provision"
    assert [g["step"] for g in [{"step": s["id"]} for s in got["steps"] if s["group"] == "17"]] == [
        "owner-info-cycle.17", "owner-info-cycle.17.6", "owner-info-cycle.17.7"]


# --- a plan and a job are read from their own stores, once --------------------------------------------------------------------------------


def test_a_plan_steps_status_is_the_approvals_and_a_second_read_adds_nothing(app, world):
    rid = start(world)
    api.attest(world, rid, C2, MANAGER, roles_of=roles_of, record="notice-1", today=TODAY)
    ident = "apr-20990101T120000-1a2b"
    make_approval(world, kind="owner-info-tags", ident=ident, status=model.ApprovalStatus.PLANNED, scope={"workflow": "x"})
    store.append(world, "example-cycle", rid, EventKind.PLAN_MADE, by="jason", step=C3,
                 detail={"key": resume.idem_key(rid, C3, SUBJECT), "approval": ident})
    got = page(app, MANAGER, rid)
    c3 = got["steps"][2]
    assert c3["state"] == "waiting" and c3["plan"] == {"approval": ident, "status": "planned", "kind": "example-plan", "screen": "approvals"}
    assert c3["waitingOn"]["kind"] == "approval" and rows_by(listed(app, MANAGER))["Example cycle 2099"]["group"] == "others"
    assert got["links"][0]["state"] == "planned" and got["links"][0]["read"] is True
    make_approval(world, kind="owner-info-tags", ident=ident, status=model.ApprovalStatus.APPROVED, scope={"workflow": "x"})
    before = snapshot(world)
    moved = page(app, MANAGER, rid)
    assert [p["kind"] for p in moved["pending"]] == ["approval-decided"] and moved["steps"][2]["reason"] == "approval approved"
    assert moved["links"][0]["state"] == "approved"
    assert page(app, MANAGER, rid)["pending"] == moved["pending"] and snapshot(world) == before        # a read repeats nothing and writes nothing
    assert [e["kind"] for e in post(as_(app, MANAGER), f"example-cycle/{rid}", {"act": "open"}).json["appended"]] == ["approval-decided"]
    assert post(as_(app, MANAGER), f"example-cycle/{rid}", {"act": "open"}).json["appended"] == []


# --- the Python API: no request, the roster names the roles ------------------------------------------------------------------------------


def test_outside_a_request_the_communitys_roster_names_the_roles(world, monkeypatch):
    from jason.community.base import Officer, OfficerRole
    from jason.web.extra import work as w

    monkeypatch.setattr("jason.commands.workflow._officers", lambda: (Officer(OfficerRole.MANAGER, "A. Manager", (), "m@example.org"),))
    monkeypatch.setattr("jason.commands.workflow._admins", lambda: ())
    rid = start(world)
    with pytest.raises(ValueError, match="does not hold the manager role"):
        w.write(f"example-cycle/{rid}", {"act": "attest", "step": C2, "record": "r", "by": "Nobody"})
    with pytest.raises(ValueError, match="by is required"):
        w.write(f"example-cycle/{rid}", {"act": "note", "text": "x"})
    done = w.write(f"example-cycle/{rid}", {"act": "attest", "step": C2, "record": "r", "by": "a. manager"})
    assert done["by"] == "A. Manager" and done["run"]["steps"][1]["by"] == "A. Manager"
    assert w.work({})["runs"][0]["group"] == "others"                       # no viewer, so nothing is anyone's


# --- item sets, step groups, and a remedy (docs/workflows-engine.md, "Engine round three") ----------------------------------------


def item_world(world):
    """The made-up item flow, group flow, and a remedy flow whose check fails, registered beside the others for one test."""
    from test_workflows_engine_v3 import GROUPS, ITEMS, REMEDY, group_flow, item_flow, remedy_flow
    from jason.workflows.types import CheckResult, StepGroup

    definitions.register(item_flow())
    definitions.register(group_flow(groups=(StepGroup("intake", "Intake"), StepGroup("board", "The board"))))
    broken = remedy_flow()
    steps = tuple(replace(s, check=lambda view: CheckResult(False, (), "the roster is incomplete")) if s.id == "r.1" else s
                  for s in broken.steps)
    definitions.register(remedy_flow(steps=steps))
    return ITEMS, GROUPS, REMEDY


def supplied(app, rid, items, *, who=MANAGER, definition="item-flow", **body):
    return post(as_(app, who), f"{definition}/{rid}", {"act": "supply-items", "set": "requests", "items": items, **body})


def item_run(world, **kw):
    return start(world, "item-flow", subject="period:2099-10", label="Item flow", dates=kw.pop("dates", {}), **kw)


def test_the_run_page_has_the_item_sets_the_viewer_may_supply_to_and_nothing_when_none_repeats(app, world):
    item_world(world)
    rid = item_run(world)
    got = page(app, MANAGER, rid, "item-flow")
    assert got["run"]["itemSets"] == [{"name": "requests", "label": "the set requests", "count": 0,
                                       "steps": ["Read each request", "Decide each request", "Which way", "Send the grant",
                                                 "Send the denial"]}]
    assert got["run"]["acts"]["supplyItems"]["offered"] is True
    assert [s["name"] for s in got["run"]["acts"]["supplyItems"]["sets"]] == ["requests"]
    step = {s["id"]: s for s in got["steps"]}["i.1"]
    assert step["itemAware"] is True and step["itemSet"] == "requests" and step["perItem"] is True and step["items"] == []
    assert step["state"] == "waiting" and "no items in the set requests yet" in step["reason"]
    plain = page(app, MANAGER, start(world))["run"]
    assert "itemSets" not in plain
    assert plain["acts"]["supplyItems"] == {"offered": False, "why": "No step of this run repeats over a set of items.", "sets": []}


def test_supplying_items_records_one_note_and_the_page_then_lists_them_with_a_clock_for_each(app, world):
    item_world(world)
    rid = item_run(world, dates={"due_on": "2099-10-01"})
    n = store.read(world, "item-flow", rid).n
    r = supplied(app, rid, ["req:1", {"id": "req:2", "dates": {"due_on": "2099-09-30"}}, "req:1"], record="mail:1")
    assert r.status_code == 200, r.json
    assert r.json["act"] == "supply-items" and r.json["by"] == MANAGER and r.json["event"]["kind"] == "note"
    assert "supplied 2 items to the set requests" in r.json["event"]["text"] and r.json["event"]["by"] == MANAGER
    assert "req:1" not in json.dumps(r.json["event"]) and "req:1" not in json.dumps(r.json["run"]["history"])   # the history holds a count
    assert store.read(world, "item-flow", rid).n == n + 1
    got = r.json["run"]
    step = {s["id"]: s for s in got["steps"]}["i.1"]
    assert [i["item"] for i in step["items"]] == ["req:1", "req:2"] and sum(step["itemCounts"].values()) == 2
    assert got["run"]["itemSets"][0]["count"] == 2
    clocks = {c["key"]: c for c in got["clocks"]}
    assert clocks["i.2[req:1]"]["item"] == "req:1" and clocks["i.2[req:1]"]["step"] == "i.2" and clocks["i.2[req:1]"]["due"] == "2099-10-04"
    assert clocks["i.2[req:2]"]["due"] == "2099-10-03"
    assert all("item" not in c for c in page(app, MANAGER, start(world))["clocks"])


def test_a_dry_run_makes_the_same_checks_and_writes_nothing(app, world):
    item_world(world)
    rid = item_run(world)
    n = store.read(world, "item-flow", rid).n
    r = supplied(app, rid, ["a", "b"], dryRun=True)
    assert r.status_code == 200 and r.json["dryRun"] is True and r.json["wouldAdd"] == ["a", "b"] and r.json["alreadyThere"] == []
    assert store.read(world, "item-flow", rid).n == n
    bad = supplied(app, rid, ["Jane Doe"], dryRun=True)
    assert bad.status_code == 400 and "is not an item id" in bad.json["error"] and "never a name or an address" in bad.json["error"]
    assert store.read(world, "item-flow", rid).n == n
    supplied(app, rid, ["a"])
    again = supplied(app, rid, ["a", "c"], dryRun=True)
    assert again.json["wouldAdd"] == ["c"] and again.json["alreadyThere"] == ["a"]


def test_supply_items_is_refused_in_the_engines_words(app, world):
    item_world(world)
    rid = item_run(world)
    n = store.read(world, "item-flow", rid).n
    for bad in ("Jane Doe", "jane@example.org", "123 Main St", "x" * 65):
        r = supplied(app, rid, [bad])
        assert r.status_code == 400 and "is not an item id" in r.json["error"], bad
    assert supplied(app, rid, []).status_code == 400
    assert supplied(app, rid, "Jane Doe").status_code == 400                       # text is one id a line: a line with a space is refused
    assert supplied(app, rid, {"a": 1}).status_code == 400
    odd = supplied(app, rid, ["a"], set="nope")
    assert odd.status_code == 400 and "no step of item-flow repeats over the set nope" in odd.json["error"]
    stale = supplied(app, rid, ["a"], expect=n - 1)
    assert stale.status_code == 409 and stale.json["actual"] == n
    assert supplied(app, rid, ["a"], by="Pat Example").status_code == 403           # a body by naming someone else
    assert store.read(world, "item-flow", rid).n == n


def test_a_person_with_no_role_a_step_needs_and_not_the_opener_is_a_403(app, world):
    item_world(world)
    rid = item_run(world)
    n = store.read(world, "item-flow", rid).n
    r = supplied(app, rid, ["a"], who=TREASURER)
    assert r.status_code == 403 and "holds no role that a step over the set requests needs" in r.json["error"]
    run = page(app, TREASURER, rid, "item-flow")["run"]
    assert run["acts"]["supplyItems"]["offered"] is False and "Only the person who opened the run" in run["acts"]["supplyItems"]["why"]
    assert store.read(world, "item-flow", rid).n == n
    assert supplied(app, rid, ["a"], who=MANAGER).status_code == 200


def test_a_closed_run_supplies_nothing(app, world):
    item_world(world)
    rid = item_run(world)
    post(as_(app, MANAGER), f"item-flow/{rid}", {"act": "cancel", "reason": "r"})
    r = supplied(app, rid, ["a"])
    assert r.status_code == 400 and "the run is cancelled; items are supplied while it is a draft or going" in r.json["error"]
    run = page(app, MANAGER, rid, "item-flow")["run"]
    assert run["acts"]["supplyItems"]["offered"] is False and "cancelled" in run["acts"]["supplyItems"]["why"]


def test_an_open_group_is_expanded_and_a_not_yet_reached_one_is_collapsed(app, world):
    item_world(world)
    rid = start(world, "group-flow", subject="period:2099-10", label="Group flow", dates={})
    got = page(app, MANAGER, rid, "group-flow")
    groups = {g["key"]: g for g in got["groups"]}
    assert list(groups) == ["intake", "board"] and groups["intake"]["title"] == "Intake" and groups["intake"]["expanded"] is True
    assert groups["intake"]["current"] == "g.1" and groups["board"]["expanded"] is False and groups["board"]["title"] == "The board"
    assert groups["intake"]["steps"] == ["g.1", "g.2"] and groups["intake"]["total"] == 2
    assert "groups" not in page(app, MANAGER, start(world))
    assert "itemSets" not in got["run"]                                              # no step of it repeats over items


def test_a_failed_check_with_a_remedy_names_the_remedy_step_and_the_step_names_the_check(app, world):
    item_world(world)
    rid = start(world, "remedy-flow", subject="period:2099-10", label="Remedy flow", dates={})
    got = page(app, MANAGER, rid, "remedy-flow")
    steps = {s["id"]: s for s in got["steps"]}
    assert steps["r.1"]["state"] == "failed" and steps["r.1"]["remedy"] == "r.2" and "remedyOf" not in steps["r.1"]
    assert steps["r.2"]["remedyOf"] == "r.1" and steps["r.2"]["state"] in ("needs a person", "ready")
    assert steps["r.3"]["state"] == "blocked" and "remedy" not in steps["r.3"]
    assert got["run"]["current"]["id"] == "r.2"


def test_a_run_with_no_item_rules_has_none_of_the_new_fields(app, world):
    rid = start(world)
    got = page(app, MANAGER, rid)
    assert "groups" not in got and "itemSets" not in got["run"]
    assert all(not ({"itemAware", "itemSet", "itemCounts", "remedy", "remedyOf", "perItem"} & set(s)) for s in got["steps"])


# --- the step guide: enable, nudge, and guide (docs/console/screens/work-guide.md) --------------------------------------------------

def guided(key="example-guided"):
    """example-cycle whose person step carries a Support: a read, a rule, a checklist, two commands, a lesson, an ask."""
    from jason.workflows.types import Check, Cite, Cmd, Enables, Guides, LookAt, Reminds, Role, Support

    support = Support(
        enables=Enables(in_hand=("the sent notice",)), reminds=Reminds(after_hours=24),
        guides=Guides(instruction="Send the notice, then write down its reference.",
                      look_at=(LookAt("Answers that have arrived", "responses-new"),),
                      checklist=(Check("It names the right unit", required=True), Check("A copy is kept")),
                      commands=(Cmd("example notice --send --by NAME"), Cmd("example notice --check ID")),
                      lessons=("form-link-needs-unit",), cites=(Cite("EX 123.4", reading="The answer is due by the day named."),),
                      done_when="The reference is written down.", ask=(Role.MANAGER, Role.PRESIDENT)))
    base = example_cycle()
    return example_cycle(key=key, title="Guided cycle", steps=tuple(replace(s, support=support) if s.id == C2 else s for s in base.steps))


@pytest.fixture
def roster(monkeypatch):
    from jason.community.base import Officer, OfficerRole

    rows = (Officer(OfficerRole.MANAGER, MANAGER), Officer(OfficerRole.TREASURER, TREASURER), Officer(OfficerRole.SECRETARY, SECRETARY))
    monkeypatch.setattr("jason.access.community_officers", lambda: rows)
    monkeypatch.setattr("jason.access.admins", lambda: ())
    return rows


@pytest.fixture
def guide_world(world, roster):
    definitions.register(guided(), plan_kinds={"example-plan"}, jobs={"example-report"})
    return world


def test_person_steps_carry_enable_nudge_and_guide_and_jasons_own_steps_carry_none(app, world, roster):
    rid = start(world)
    steps = {s["id"]: s for s in page(app, MANAGER, rid)["steps"]}
    for jasons in (C1, C3, C4, C5):                                              # a check, a plan, a job, a wait no note ends
        assert not {"enable", "nudge", "guide"} & set(steps[jasons]), jasons
    for person in (C2, C6):                                                      # a person step, and the board's decision the secretary records
        assert {"enable", "nudge", "guide"} <= set(steps[person]), person
    c2 = steps[C2]
    assert c2["enable"]["state"] == "ready" and c2["enable"]["word"] == "Yours: you hold the manager office. Nothing is missing."
    assert c2["enable"]["holders"][0]["office"] == "manager" and c2["enable"]["holders"][0]["names"] == [MANAGER]
    assert c2["nudge"]["band"] == "quiet" and c2["nudge"]["numbers"]["note"] == "proposed, not the law's"
    g = c2["guide"]
    assert g["instruction"] == "Send the example notice to 123 Main St" and g["authored"] == []                   # derived: the title
    assert g["commands"][0]["text"] == "example notice --send" and g["doneWhen"] == "Done when you can point to: the sent-notice reference."
    assert g["lookAt"][0]["kind"] == "evidence" and g["lookAt"][0]["rows"] == ["store:notices"]
    assert g["notApplicable"] == "This step has no not-applicable outcome; it may be skipped with a reason."
    c6 = steps[C6]["enable"]
    assert c6["state"] == "not yours" and c6["word"] == "Waiting on the secretary."


def test_a_step_with_a_support_shows_its_guide_with_the_name_filled_and_the_unreadable_said(app, guide_world):
    rid = start(guide_world, "example-guided")
    g = page(app, MANAGER, rid, "example-guided")["steps"][1]["guide"]
    assert g["authored"] == ["instruction", "rule", "checklist", "look-at", "commands", "done-when", "ask", "lessons"] or g["authored"][0] == "instruction"
    assert g["instruction"] == "Send the notice, then write down its reference."
    assert g["checklist"] == [{"text": "It names the right unit", "required": True}, {"text": "A copy is kept", "required": False}] and g["requiredChecks"] == 1
    first, second = g["commands"]
    assert first["text"] == 'example notice --send --by "A Manager"' and first["fillIn"] == []
    assert second["text"] == "example notice --check ID" and second["fillIn"] == ["ID"]                  # an ID stays the person's to fill in
    read = g["lookAt"][0]
    assert read["kind"] == "read" and (read["unavailable"] or isinstance(read["count"], int))
    if read["count"] is None:
        assert read["unavailable"]                                                                           # never "nothing to look at"
    assert g["lessons"] == [{"key": "form-link-needs-unit", "status": "fixed"}]
    assert [a["office"] for a in g["ask"]] == ["manager", "president"] and g["ask"][0]["names"] == [MANAGER]
    assert g["ask"][1]["vacant"] is True and g["ask"][1]["names"] == []                                      # nobody holds the president office here
    treasurer = page(app, TREASURER, rid, "example-guided")["steps"][1]["guide"]
    assert treasurer["commands"][0]["text"] == 'example notice --send --by "Pat Example"'
    assert page(app, MANAGER, rid, "example-guided")["steps"][1]["enable"]["inHand"] == ["the sent notice"]


def test_a_cite_is_recited_whole_then_the_reading_and_a_cite_the_shelf_lacks_is_said_not_paraphrased(app, guide_world, monkeypatch):
    from jason.community import law_text

    rid = start(guide_world, "example-guided")
    rule = page(app, MANAGER, rid, "example-guided")["steps"][1]["guide"]["rule"][0]
    assert rule["missing"] == "The words of EX 123.4 are not on the shelf here." and rule["words"] == "" and rule["command"] == "jason export-authorities"
    assert rule["reading"] == "The answer is due by the day named." and rule["readingLabel"] == "jason's reading"
    words = law_text.LawText("EX 123", "Whoever must answer shall answer by the day named.", "abc123def456", source="Example Legislature")
    monkeypatch.setattr(law_text, "quoted", lambda cite, root, day=None: law_text.Quoted("EX 123.4", TODAY, (words,), words))
    rule = page(app, MANAGER, rid, "example-guided")["steps"][1]["guide"]["rule"][0]
    assert rule["words"] == "Whoever must answer shall answer by the day named." and rule["source"] == "Example Legislature" and rule["missing"] == ""
    assert rule["version"] == "the words in force on 2099-09-20" and "not an official restatement" in rule["restatement"]
    assert rule["reading"] == "The answer is due by the day named."


def test_a_director_reads_the_same_panel_an_officer_reads_at_the_same_level(app, guide_world):
    rid = start(guide_world, "example-guided")
    seen = {who: page(app, who, rid, "example-guided")["steps"][1] for who in (TREASURER, SECRETARY, "Dana Director", "Lee President")}
    base = seen[TREASURER]

    def words(step):                       # a command is filled with the reader's own name; everything else is the same
        return {**step["guide"], "commands": [{k: v for k, v in c.items() if k != "text"} for c in step["guide"]["commands"]]}

    for who, step in seen.items():
        assert words(step) == words(base) and step["nudge"] == base["nudge"], who
        assert step["enable"]["state"] == "not yours" and step["enable"]["word"] == "Waiting on the manager."
        assert step["acts"] == []                                                                            # what differs is the act row, not the words


def test_a_claim_is_a_note_in_the_signers_name_that_the_page_then_shows_and_grants_nothing(app, guide_world):
    rid = start(guide_world, "example-guided")
    n = store.read(guide_world, "example-guided", rid).n
    t = as_(app, TREASURER)
    r = post(t, f"example-guided/{rid}", {"act": "claim", "step": C2})
    assert r.status_code == 403 and "does not hold the manager role" in r.json["error"]                      # a claim is for a holder of the step
    assert store.read(guide_world, "example-guided", rid).n == n
    m = as_(app, MANAGER)
    r = post(m, f"example-guided/{rid}", {"act": "claim", "step": C2, "by": "Someone Else"})
    assert r.status_code == 403 and store.read(guide_world, "example-guided", rid).n == n                      # the signer's own name only
    r = post(m, f"example-guided/{rid}", {"act": "claim", "step": C2})
    assert r.status_code == 200, r.json
    assert r.json["event"]["kind"] == "note" and r.json["event"]["detail"]["claim"] is True and r.json["event"]["text"] == f"{MANAGER} is on step 2, Send the example notice to 123 Main St"
    c2 = r.json["run"]["steps"][1]
    assert c2["nudge"]["claim"]["by"] == MANAGER and c2["nudge"]["claim"]["mine"] is True and "attest" in c2["acts"]            # nothing granted or removed
    other = page(app, TREASURER, rid, "example-guided")["steps"][1]
    assert other["nudge"]["claim"]["by"] == MANAGER and other["nudge"]["claim"]["mine"] is False
    assert post(m, f"example-guided/{rid}", {"act": "claim", "step": C2}).status_code == 400                   # already on it
    r = post(m, f"example-guided/{rid}", {"act": "claim", "step": C2, "release": True})
    assert r.status_code == 200 and r.json["run"]["steps"][1]["nudge"]["claim"] is None
    assert r.json["event"]["text"] == f"{MANAGER} let go of step 2, Send the example notice to 123 Main St"


def test_the_enable_state_for_a_draft_a_paused_run_and_an_admin_viewing_as_someone_else(app, guide_world):
    rid = start(guide_world, "example-guided", open_=False)
    assert page(app, MANAGER, rid, "example-guided")["steps"][1]["enable"]["word"] == "The run has not been opened."
    api.open_run(guide_world, rid, MANAGER, readers=StoreReaders(guide_world, today=TODAY), yes=True, today=TODAY)
    api.pause(guide_world, rid, MANAGER, reason="a holiday", today=TODAY)
    assert page(app, MANAGER, rid, "example-guided")["steps"][1]["enable"]["state"] == "paused"
    api.resume_run(guide_world, rid, MANAGER, today=TODAY)
    c = as_(app, ADMIN)
    with c.session_transaction() as s:
        s["acting"] = {"name": MANAGER, "role": "manager"}
    seen = c.get(f"/api/work-run?definition=example-guided&id={rid}").json["steps"][1]["enable"]
    assert seen["state"] == "viewing as" and seen["word"].startswith("Viewing as ") and seen["word"].endswith("(admin view): go back to yourself first.")


def test_an_integration_that_is_not_signed_in_is_named_and_a_credential_is_never_shown(app, world, roster, monkeypatch):
    from jason.workflows.types import Enables, Guides, Support

    base = example_cycle()
    need = Support(enables=Enables(integrations=("example",)), guides=Guides())
    steps = tuple(replace(s, support=need) if s.id == C2 else s for s in base.steps)
    definitions.register(example_cycle(key="example-needs", title="Needs an integration", steps=steps), plan_kinds={"example-plan"}, jobs={"example-report"})
    monkeypatch.setattr("jason.web.extra.work_guide.integration_states", lambda keys: {k: "needs sign-in" for k in keys})
    monkeypatch.setattr("jason.web.extra.work_guide.integration_names", lambda keys: {k: "The Example Service" for k in keys})
    rid = start(world, "example-needs")
    enable = page(app, MANAGER, rid, "example-needs")["steps"][1]["enable"]
    assert enable["state"] == "needs an integration" and enable["word"] == "Needs The Example Service signed in."
    assert enable["missing"] == [{"what": "The Example Service", "why": "The Example Service is needs sign-in",
                                  "fix": "jason integrations check example --live"}]


def test_the_run_page_calls_no_outside_system(app, guide_world, monkeypatch):
    """The page and its loaders make no call to PayHOA, Google, Zoom, or a mail service: with the network cut, they still answer."""
    import socket

    def cut(*a, **k):
        raise AssertionError("a network call was made")

    rid = start(guide_world, "example-guided")
    monkeypatch.setattr(socket.socket, "connect", cut)
    monkeypatch.setattr(socket, "create_connection", cut)
    assert page(app, MANAGER, rid, "example-guided")["steps"][1]["guide"]["instruction"]
    assert post(as_(app, MANAGER), f"example-guided/{rid}", {"act": "claim", "step": C2}).status_code == 200


def test_the_catalog_lists_each_steps_guidance_coverage_in_words(app, guide_world):
    got = as_(app, MANAGER).get("/api/work-definitions?key=example-guided").json["definition"]["steps"]
    by_id = {s["id"]: s["guidance"] for s in got}
    assert by_id[C2].startswith("instruction, rule, checklist, look-at") and by_id[C1] == "" and by_id[C6] == "derived"
