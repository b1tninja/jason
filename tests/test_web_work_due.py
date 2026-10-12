"""The work-due loader (``jason.web.extra.work_due``, ``GET /api/work-due``): the person steps waiting on the viewer, by band
(docs/workflows/person-steps.md, section 6). A reading of the runs on disk: nothing is sent, snoozed, or stored. Made-up
definitions ("example-cycle"), people, and 2099 dates in a tmp data folder; nothing reaches Google, Keeper, or PayHOA.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date

import pytest
import webclient

from jason.workflows import api, definitions
from jason.workflows.readers import StoreReaders
from jason.workflows.types import ClockBasis, ClockDef, Role, Visibility
from test_workflows_support import C1, C2, C5, DATES, example_cycle

ROWS = webclient.ROSTER + (("Rae Roster", "", "rae@example.org", False),)
MANAGER, TREASURER, SECRETARY, PRESIDENT, ADMIN = "A Manager", "Pat Example", "Sam Secretary", "Lee President", "Ada Admin"
DAY = {"early": date(2099, 10, 1), "soon": date(2099, 10, 13), "legal": date(2099, 10, 23), "late": date(2099, 10, 29)}
NOW = {"day": DAY["legal"]}                                    # the day the loader reads as today
KW = dict(plan_kinds={"example-plan"}, jobs={"example-report"})


def person_step(wf, **over):
    """example-cycle with ``over`` applied to its person step (C2)."""
    c2 = replace(wf.step(C2), skip=None, **over)
    return replace(wf, steps=tuple(c2 if s.id == C2 else s for s in wf.steps))


def legal():
    """The person step on the law's clock: LEGAL the day it falls."""
    return person_step(example_cycle(), clock=ClockDef(ClockBasis.LAW, "answers_by", 0, cite="EX 123.4"), legal=True)


def documents():
    """The same step on a documents' clock, in a definition of its own."""
    wf = person_step(example_cycle(), clock=ClockDef(ClockBasis.DOCUMENTS, "answers_by", 0, cite="the example document"))
    return replace(wf, key="example-documents", title="Example documents cycle")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    monkeypatch.setenv("JASON_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: tmp_path)
    monkeypatch.setattr("jason.web.extra.work._community", lambda: None)
    NOW["day"] = DAY["legal"]
    monkeypatch.setattr("jason.web.extra.work._today", lambda: NOW["day"])
    definitions.reset()
    definitions.register(legal(), **KW)
    definitions.register(documents(), **KW)
    yield tmp_path
    definitions.reset()


@pytest.fixture
def app(world):
    from jason.web.app import create_app
    from jason.web.extra import work as w, work_due

    dist = world / "dist"
    dist.mkdir(exist_ok=True)
    return create_app(dist, {"work": w.work, "work-due": work_due.work_due}, approvals_live=None, extra_writes=False,
                      sign_in=webclient.roster_sign_in(ROWS))


def as_(app, name):
    return webclient.sign_in(webclient.client(app), name, rows=ROWS)


def start(root, definition="example-cycle", *, label="Example cycle 2099", subject="campaign:EX-2099", dates=None, by=MANAGER):
    rid = api.start(root, definition, subject, label, DATES if dates is None else dates, by, yes=True, today=DAY["early"],
                    at="2099-09-15T09:00:00Z")["run"]["id"]
    api.open_run(root, rid, by, readers=StoreReaders(root, today=DAY["early"]), yes=True, today=DAY["early"], at="2099-09-15T09:01:00Z")
    return rid


def due(app, who, day=None, world=None, query=""):
    if day is not None:
        NOW["day"] = day
    r = as_(app, who).get("/api/work-due" + query)
    assert r.status_code == 200, (who, r.status_code, r.get_data(as_text=True)[:300])
    return r.json


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file() and "locks" not in p.parts}


# --- who may read it -------------------------------------------------------------------------------------------------------------


def test_signed_out_is_a_401_and_a_roster_person_with_no_office_a_403(app):
    assert webclient.client(app).get("/api/work-due").status_code == 401
    r = as_(app, "Rae Roster").get("/api/work-due")
    assert r.status_code == 403 and "(P2)" in r.json["error"]                                   # access.may_see's sentence


def test_an_admin_with_no_office_reads_but_holds_none_of_the_board_s_steps(app, world):
    start(world)
    got = due(app, ADMIN, DAY["legal"], world)
    assert got["mine"] == [] and got["escalated"] == [] and got["counts"]["total"] == 0
    assert got["empty"]


@pytest.mark.parametrize("who", (MANAGER, TREASURER, SECRETARY, PRESIDENT, "Dana Director", "Vic Vice"))
def test_the_manager_and_every_board_office_read_it(app, world, who):
    assert due(app, who)["found"] is True


def test_a_bad_within_is_a_400_after_the_gate(app):
    assert webclient.client(app).get("/api/work-due?within=x").status_code == 401
    assert as_(app, MANAGER).get("/api/work-due?within=x").status_code == 400
    assert as_(app, MANAGER).get("/api/work-due?within=-1").status_code == 400


def test_the_owner_view_never_reads_it():
    from jason.web.extra.owner_view import OWNER_SOURCES
    from jason.web.sources import EXTRA_LOADERS

    assert "work-due" not in OWNER_SOURCES
    assert EXTRA_LOADERS["work-due"] == "jason.web.extra.work_due:work_due"


# --- the bands -------------------------------------------------------------------------------------------------------------------


def test_nothing_is_listed_before_the_lead_time(app, world):
    start(world)
    got = due(app, MANAGER, DAY["early"], world)
    assert got["mine"] == [] and got["counts"]["total"] == 0 and "No step waiting on you" in got["empty"]


def test_a_law_clock_is_due_soon_then_legal_the_day_it_falls_then_still_legal(app, world):
    rid = start(world)
    soon = due(app, MANAGER, DAY["soon"], world)["mine"]
    assert [(r["band"], r["word"], r["days"], r["basisLabel"]) for r in soon] == [("soon", "due soon", 10, "LEGAL")]
    for day in (DAY["legal"], DAY["late"]):
        got = due(app, MANAGER, day, world)
        row = got["mine"][0]
        assert row["band"] == "legal" and row["word"] == "LEGAL" and row["legal"] is True and row["cite"] == "EX 123.4"
        assert row["run"] == rid and row["definition"] == "example-cycle" and row["n"] == 2 and row["holder"] == "the manager"
        assert got["counts"]["legal"] == 1 and got["counts"]["total"] == 1
        assert [b["count"] for b in got["bands"]] == [1, 0, 0, 0, 0]


def test_another_clock_past_is_late_and_not_legal(app, world):
    start(world, "example-documents")
    got = due(app, MANAGER, DAY["late"], world)
    row = got["mine"][0]
    assert row["band"] == "late" and row["word"] == "OVERDUE" and row["legal"] is False and row["days"] == -6
    assert got["counts"]["late"] == 1 and got["counts"]["legal"] == 0


def test_a_step_open_a_while_with_no_clock_is_open(app, world):
    definitions.register(replace(person_step(example_cycle(), clock=None), key="example-noclock", title="Example no-clock cycle"), **KW)
    start(world, "example-noclock")
    got = due(app, MANAGER, DAY["late"], world)
    assert [r["band"] for r in got["mine"]] == ["stale"] and got["mine"][0]["word"] == "open" and got["mine"][0]["due"] is None


def test_the_lead_time_is_labeled_a_proposal_and_the_viewer_s_roles_are_said(app, world):
    start(world)
    got = due(app, MANAGER, DAY["soon"], world)
    assert got["numbers"] == {"leadDays": 14, "afterHours": 168, "escalateAfterHours": 72, "adopted": False,
                              "note": "proposed, not the law's"}
    assert got["viewer"]["roles"] == ["manager"] and any("never moved" in c or "proposals" in c for c in got["caveats"])


def test_within_keeps_a_due_soon_line_only_if_its_date_is_that_near(app, world):
    start(world)
    assert due(app, MANAGER, DAY["soon"], world, "?within=3")["mine"] == []
    assert len(due(app, MANAGER, DAY["soon"], world, "?within=10")["mine"]) == 1


# --- the board sees what is escalated, and only that ----------------------------------------------------------------------------


def test_a_legal_date_is_shown_to_the_whole_board_the_day_it_falls_and_nothing_is_sent(app, world):
    start(world)
    for who in (SECRETARY, TREASURER, PRESIDENT):
        got = due(app, who, DAY["legal"], world)
        assert got["mine"] == [] and len(got["escalated"]) == 1, who
        row = got["escalated"][0]
        assert row["band"] == "legal" and row["escalatedTo"] == "the whole board" and row["holder"] == "the manager"
    assert due(app, SECRETARY, DAY["soon"], world)["escalated"] == []                            # not before the day it falls


def test_a_late_step_is_escalated_to_its_office_after_the_delay_and_not_before(app, world):
    start(world, "example-documents")
    NOW["day"] = date(2099, 10, 24)
    assert due(app, PRESIDENT, date(2099, 10, 24), world)["escalated"] == []                      # one day late: under the delay
    got = due(app, PRESIDENT, date(2099, 10, 29), world)                                         # six days late
    assert [r["escalatedTo"] for r in got["escalated"]] == ["president"]
    assert due(app, SECRETARY, date(2099, 10, 29), world)["escalated"] == []                      # not the board's office to see


# --- what a row holds ------------------------------------------------------------------------------------------------------------


def test_a_row_names_no_item_address_subject_or_person(app, world):
    start(world, label="Example cycle 2099 (a.owner@example.org)", subject="unit:77 Sample Row")
    text = json.dumps(due(app, MANAGER, DAY["legal"], world))
    for leak in ("77 Sample Row", "a.owner@example.org", "unit:", "store:", "campaign:EX", "A Manager"):
        assert leak not in text, leak


def test_a_per_item_step_is_one_row_with_a_count(app, world):
    rid = api.start(world, "example-cycle", "campaign:EX-2099", "Items run", DATES, MANAGER, items=("item-a", "item-b", "item-c"),
                    yes=True, today=DAY["early"], at="2099-09-15T09:00:00Z")["run"]["id"]
    api.open_run(world, rid, MANAGER, readers=StoreReaders(world, today=DAY["early"]), yes=True, today=DAY["early"], at="2099-09-15T09:01:00Z")
    got = due(app, MANAGER, DAY["legal"], world)
    assert len(got["mine"]) == 1                                                                   # one line, never one per item
    text = json.dumps(got)
    assert "item-a" not in text and "item-b" not in text


def test_a_claim_is_only_whether_it_is_the_viewer_s_and_stale(app, world):
    rid = start(world)
    api.claim(world, rid, C2, MANAGER, roles_of=lambda by: ("manager",), today=DAY["early"])
    claim = due(app, MANAGER, DAY["legal"], world)["mine"][0]["claim"]
    assert claim == {"mine": True, "stale": True}                                  # no name: the Work run page names who
    assert due(app, SECRETARY, DAY["legal"], world)["escalated"][0]["claim"] == {"mine": False, "stale": True}


def test_a_held_run_is_its_general_title_only_even_for_the_manager(app, world):
    held = replace(legal(), key="example-held", title="Example hearing", visibility=Visibility.HELD, held_title="A member's matter")
    definitions.register(held, **KW)
    start(world, "example-held", label="Hearing for 123 Main St", subject="unit:123 Main St")
    row = next(r for r in due(app, MANAGER, DAY["legal"], world)["mine"] if r["held"])
    assert row["label"] == "A member's matter" and row["title"] == "a step" and row["cite"] == "" and row["dueLabel"] == ""
    assert row["band"] == "legal" and row["basisLabel"] == "LEGAL" and row["claim"] is None
    text = json.dumps(row)
    for leak in ("123 Main St", "Hearing for", "EX 123.4", "Send the example notice", "answers_by"):
        assert leak not in text, leak


def test_an_administrators_definition_is_listed_for_an_administrator_and_for_no_one_else(app, world):
    admin_wf = replace(legal(), key="example-admin", title="Example admin cycle", visibility=Visibility.ADMIN)
    admin_wf = person_step(admin_wf, role=Role.ADMINISTRATOR)
    definitions.register(admin_wf, **KW)
    api.start(world, "example-admin", "instance:x", "Admin run", DATES, ADMIN, yes=True, today=DAY["early"], at="2099-09-15T09:00:00Z")
    rid = next(r["id"] for r in api.runs(world, state="all") if r["definition"] == "example-admin")
    api.open_run(world, rid, ADMIN, readers=StoreReaders(world, today=DAY["early"]), yes=True, today=DAY["early"], at="2099-09-15T09:01:00Z")
    mine = due(app, ADMIN, DAY["legal"], world)["mine"]
    assert [(r["run"], r["definition"]) for r in mine] == [(rid, "example-admin")]
    for who in (MANAGER, SECRETARY):
        got = due(app, who, DAY["legal"], world)
        assert rid not in json.dumps(got), who


# --- a read and nothing else ---------------------------------------------------------------------------------------------------


def test_reading_it_writes_nothing_and_opens_no_run(app, world):
    start(world)
    before = snapshot(world)
    for who in (MANAGER, SECRETARY, TREASURER):
        due(app, who, DAY["late"], world)
    assert snapshot(world) == before


def test_the_work_list_row_carries_the_same_band(app, world):
    start(world)
    NOW["day"] = DAY["legal"]
    rows = as_(app, MANAGER).get("/api/work").json["runs"]
    mine = [r for r in rows if r["definition"] == "example-cycle"]
    assert mine and mine[0]["nudge"]["band"] == "legal" and mine[0]["nudge"]["word"] == "LEGAL" and mine[0]["nudge"]["n"] == 2
    NOW["day"] = DAY["early"]
    assert as_(app, MANAGER).get("/api/work").json["runs"][0]["nudge"] is None


def test_the_work_list_row_of_a_held_run_has_the_band_and_the_date_and_no_step(app, world):
    held = replace(legal(), key="example-held", title="Example hearing", visibility=Visibility.HELD, held_title="A member's matter")
    definitions.register(held, **KW)
    start(world, "example-held", label="Hearing for 123 Main St", subject="unit:123 Main St")
    NOW["day"] = DAY["legal"]
    row = next(r for r in as_(app, MANAGER).get("/api/work").json["runs"] if r["definition"] == "example-held")
    assert row["held"] is True and row["nudge"]["band"] == "legal" and row["nudge"]["title"] == "" and row["nudge"]["step"] == ""
    assert "Send the example notice" not in json.dumps(row) and "123 Main St" not in json.dumps(row)
