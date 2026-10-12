"""Held and administrator runs on the Work screens (``jason.web.extra.work``, ``work_scope``, ``office_view``).

A ``HELD`` definition (a hearing, a delinquent account, a records request) shows a run outside the private view as its
general title and its state, with an opaque handle: no label, subject, step title, evidence address, link, or history
sentence. Inside the private view (for an office that opens P3 in it) the whole run, and each opening is a line in
``access/served.jsonl`` under the run id. An act on a held run outside the private view is the 404 a missing run gets, and
starting one a 403. An ``ADMIN`` definition is listed, read, and started by an administrator only. Made-up people, units, and
dates (2099) in a tmp data folder; nothing reaches Google, Keeper, or PayHOA.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date

import pytest
import webclient

from jason.workflows import api, definitions, store
from jason.workflows.readers import StoreReaders
from jason.workflows.types import Visibility
from test_workflows_support import C1, C2, DATES, example_cycle

ROWS = webclient.ROSTER + (("Rae Roster", "", "rae@example.org", False), ("Bea Both", "treasurer", "bea@example.org", True))
TODAY = date(2099, 9, 20)
MANAGER, TREASURER, ADMIN, BOTH, ROSTER_ONLY = "A Manager", "Pat Example", "Ada Admin", "Bea Both", "Rae Roster"
ADDRESS = "123 Main St"
SUBJECT = f"unit:{ADDRESS}"
LABEL = f"Hearing for {ADDRESS}"
HELD_TITLE = "A member's matter"
AT = "2099-09-15T09:00:00Z"
OFFICERS = ()


def held_def(key="example-held", *, public=False, **over):
    base = example_cycle()
    steps = tuple(replace(s, title="Send the notice" if public and s.id == C2 else s.title, public_title=public and s.id == C2)
                  for s in base.steps)
    return example_cycle(key=key, title="Example hearing", steps=steps, visibility=Visibility.HELD, held_title=HELD_TITLE, **over)


def admin_def(key="example-admin", **over):
    return example_cycle(key=key, title="Example administrator run", visibility=Visibility.ADMIN, **over)


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    monkeypatch.setenv("JASON_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: tmp_path)
    monkeypatch.setattr("jason.web.extra.work._today", lambda: TODAY)
    monkeypatch.setattr("jason.web.extra.work._community", lambda: None)
    monkeypatch.setattr("jason.web.extra.office_view._today", lambda: TODAY)
    monkeypatch.setattr("jason.access.community_officers", lambda: OFFICERS)
    definitions.reset()
    kw = dict(plan_kinds={"example-plan"}, jobs={"example-report"})
    definitions.register(example_cycle(), **kw)
    definitions.register(held_def(), **kw)
    definitions.register(held_def("example-public", public=True), **kw)
    definitions.register(admin_def(), **kw)
    definitions.register(example_cycle(key="example-terminal", title="Example terminal procedure", visibility=Visibility.ADMIN,
                                       console_start=False), **kw)
    yield tmp_path
    definitions.reset()


@pytest.fixture
def app(world):
    from jason.web.app import create_app
    from jason.web.extra import office_view as ov
    from jason.web.extra import work as w

    dist = world / "dist"
    dist.mkdir(exist_ok=True)
    loaders = {"work": w.work, "work-run": w.work_run, "work-definitions": w.work_definitions, "office-view": ov.office_view}
    return create_app(dist, loaders, approvals_live=None, extra_writes=True, sign_in=webclient.roster_sign_in(ROWS, dev=True))


def as_(app, name, *, private=False):
    c = webclient.sign_in(webclient.client(app), name, rows=ROWS)
    if private:
        assert c.post("/api/private", json={"reason": "hearing prep"}).status_code == 200
    return c


def start(root, definition="example-held", *, subject=SUBJECT, label=LABEL, open_=True, dates=None, by=MANAGER):
    rid = api.start(root, definition, subject, label, DATES if dates is None else dates, by, yes=True, today=TODAY, at=AT)["run"]["id"]
    if open_:
        api.open_run(root, rid, by, readers=StoreReaders(root, today=TODAY), yes=True, today=TODAY, at="2099-09-15T09:01:00Z")
    return rid


def served(root):
    f = root / "access" / "served.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.is_file() else []


def rows_by(r):
    return {x["id"]: x for x in r.json["runs"]}


# strings that name the matter: the unit, the label, the subject, a step's own title, and the opening person
LEAKS = (ADDRESS, "Main St", LABEL, SUBJECT, "unit:", "example notice", "Send the", "A Manager", "notice --send", "sent-notice", "answers_by",
         "closes_on", "EX 123.4")


def no_leak(r, *, but=()):
    """Nothing that names the matter is in the response (or in the given JSON value)."""
    blob = r.get_data(as_text=True) if hasattr(r, "get_data") else json.dumps(r)
    for word in LEAKS:
        if word not in but:
            assert word not in blob, word


# --- a held run outside the private view ------------------------------------------------------------------------------------


def test_a_held_run_in_the_list_is_its_general_title_and_state_and_nothing_else(app, world):
    rid = start(world)
    plain = start(world, "example-cycle", subject="campaign:EX-2099", label="Plain run")
    r = as_(app, TREASURER).get("/api/work")
    assert r.status_code == 200
    got = rows_by(r)
    row = got[rid]
    no_leak(row)
    assert row["held"] is True and row["handle"] == rid and row["visibility"] == "held"
    assert row["label"] == HELD_TITLE and row["definitionTitle"] == HELD_TITLE and row["subjectKind"] == ""
    assert row["state"] == "active" and row["group"] in ("yours", "others", "clock", "board")
    assert row["current"]["title"] == "a step" and row["current"]["id"] == "" and row["current"]["n"] == 0
    assert row["pausedReason"] == "" and row["age"]["opened"] is None and row["age"]["updated"] == ""
    due = row["due"]
    assert due["date"] and due["basis"] and due["basisLabel"] and due["label"] == "" and due["cite"] == "" and due["step"] == ""
    assert row["waitingOn"]["detail"] == ""
    assert got[plain]["held"] is False and got[plain]["label"] == "Plain run"          # the board's own run is as it was
    assert rid in {x["id"] for x in r.json["runs"]} and r.json["counts"]["open"] == 2   # counted, not hidden


def test_a_held_run_cannot_be_found_by_searching_for_its_matter(app, world):
    start(world)
    c = as_(app, TREASURER)
    for q in ("main", "123", "hearing for", "unit:", "notice", "send the"):
        assert c.get(f"/api/work?q={q}").json["runs"] == [], q
    assert len(c.get(f"/api/work?q={HELD_TITLE.split()[1]}").json["runs"]) == 1          # its general title is findable


def test_a_held_run_page_outside_the_private_view_is_the_reduced_page(app, world):
    rid = start(world)
    r = as_(app, TREASURER).get(f"/api/work-run?definition=example-held&id={rid}")
    assert r.status_code == 200
    no_leak(r)
    page = r.json
    assert page["held"] is True and page["heldTitle"] == HELD_TITLE and "private view" in page["heldWhy"]
    assert page["steps"] == [] and page["clocks"] == [] and page["links"] == [] and page["history"] == [] and page["changed"] == []
    assert page["pending"] == [] and page["phases"] == [] and page["problems"] == [] and page["notComposed"] == []
    run = page["run"]
    assert run["id"] == rid and run["label"] == HELD_TITLE and run["subject"] == "" and run["dates"] == {} and run["openedBy"] == ""
    assert run["state"] == "active" and run["current"]["title"] == "a step" and run["due"]["cite"] == ""
    assert all(a["offered"] is False for a in run["acts"].values())
    assert not served(world)                                                      # nothing was opened: nothing is logged


def test_a_held_run_page_carries_the_slot_and_parent_keys_the_page_types_name_all_empty(app, world):
    """A comment once swallowed these keys of the reduced page's dict; ``ui/src/lib/work.ts`` types them (``dateSlots``,
    ``openSlots``, ``parent``), so the page reads them without a guard."""
    rid = start(world)
    run = as_(app, TREASURER).get(f"/api/work-run?definition=example-held&id={rid}").json["run"]
    assert run["dateSlots"] == [] and run["openSlots"] == [] and run["parent"] == ""
    assert run["itemTotal"] == 0 and run["children"] == []


def test_a_step_title_shows_outside_the_private_view_only_where_the_definition_marks_it_public(app, world):
    rid = start(world, "example-public")
    row = rows_by(as_(app, TREASURER).get("/api/work"))[rid]
    assert row["current"]["title"] == "Send the notice" and row["current"]["n"] == 2
    page = as_(app, TREASURER).get(f"/api/work-run?definition=example-public&id={rid}").json
    assert page["run"]["current"]["title"] == "Send the notice"
    no_leak(row, but=("Send the",))


def test_an_act_on_a_held_run_outside_the_private_view_is_the_404_a_missing_run_gets(app, world):
    rid = start(world)
    n = store.read(world, "example-held", rid).n
    c = as_(app, MANAGER)
    missing = c.post("/api/write/work/example-held/run-0000000000", json={"act": "note", "text": "hello"})
    assert missing.status_code == 404
    for body in ({"act": "note", "text": "hello"}, {"act": "attest", "step": C2, "record": "x"}, {"act": "pause", "reason": "x"},
                 {"act": "cancel", "reason": "x", "yes": True}):
        r = c.post(f"/api/write/work/example-held/{rid}", json=body)
        assert r.status_code == 404, body
        assert r.get_data(as_text=True).replace(rid, "RID") == missing.get_data(as_text=True).replace("run-0000000000", "RID")
    assert store.read(world, "example-held", rid).n == n
    assert not served(world)


def test_starting_a_held_run_outside_the_private_view_is_a_403_even_as_a_dry_run(app, world):
    c = as_(app, MANAGER)
    for extra in ({}, {"dryRun": True}):
        r = c.post("/api/write/work/example-held/start", json={"subject": SUBJECT, "label": LABEL, "dates": DATES, "yes": True, **extra})
        assert r.status_code == 403 and "private view" in r.json["error"], extra
    assert store.list_runs(world) == []


def test_the_catalog_says_a_held_definition_starts_only_in_the_private_view(app, world):
    rows = {d["key"]: d for d in as_(app, TREASURER).get("/api/work-definitions").json["definitions"]}
    held = rows["example-held"]
    assert held["held"] is True and held["heldTitle"] == HELD_TITLE and held["visibility"] == "held"
    assert held["startable"] is False and "private view" in held["startableWhy"]
    assert rows["example-cycle"]["startable"] is True and rows["example-cycle"]["held"] is False
    inside = {d["key"]: d for d in as_(app, TREASURER, private=True).get("/api/work-definitions").json["definitions"]}
    assert inside["example-held"]["startable"] is True


def test_the_real_held_definitions_are_registered_and_reduced(app, world):
    from jason.workflows.definitions_general import register_general

    register_general(world)
    hearing = start(world, "hearing", dates={"hearing_on": "2099-10-30"})
    delinquency = start(world, "delinquency-account", dates={})
    records = start(world, "records-production", dates={"received_on": "2099-09-10"})
    r = as_(app, TREASURER).get("/api/work")
    got = rows_by(r)
    assert got[hearing]["label"] == "A member's hearing" and got[delinquency]["label"] == "A delinquent account"
    assert got[records]["label"] == "A records request"
    assert all(got[i]["held"] is True and got[i]["current"]["title"] in ("a step", "") for i in (hearing, delinquency, records))
    no_leak(list(got.values()))
    for i, d in ((hearing, "hearing"), (delinquency, "delinquency-account"), (records, "records-production")):
        page = as_(app, TREASURER).get(f"/api/work-run?definition={d}&id={i}")
        assert page.json["held"] is True and page.json["steps"] == [] and page.get_data(as_text=True).count(ADDRESS) == 0


# --- the same run inside the private view -----------------------------------------------------------------------------------


def test_inside_the_private_view_the_whole_run_shows_and_each_opening_is_logged(app, world):
    rid = start(world)
    c = as_(app, TREASURER, private=True)
    listed = c.get("/api/work")
    row = rows_by(listed)[rid]
    assert row["held"] is False and row["label"] == LABEL and row["current"]["title"] == "Send the example notice to 123 Main St"
    page = c.get(f"/api/work-run?definition=example-held&id={rid}")
    assert page.status_code == 200 and page.json.get("held") is None
    assert page.json["run"]["label"] == LABEL and page.json["run"]["subject"] == SUBJECT and len(page.json["steps"]) == 6
    lines = served(world)
    assert [x["address"] for x in lines] == ["api/work", f"api/work-run/{rid}"]
    assert all(x["level"] == "P3" and x["private"] is True and x["privateId"] and x["reason"] == "hearing prep" for x in lines)
    assert all(x["by"] == TREASURER for x in lines) and lines[0]["runs"] == 1
    assert LABEL not in json.dumps(lines) and ADDRESS not in json.dumps(lines)             # the log names the run, never the matter


def test_inside_the_private_view_an_act_is_recorded_and_logged_and_a_start_works(app, world):
    rid = start(world)
    c = as_(app, MANAGER, private=True)
    r = c.post(f"/api/write/work/example-held/{rid}", json={"act": "note", "text": "noted"})
    assert r.status_code == 200 and r.json["run"]["run"]["label"] == LABEL
    made = c.post("/api/write/work/example-held/start", json={"subject": SUBJECT, "label": LABEL, "dates": DATES, "yes": True})
    assert made.status_code == 200 and made.json["id"] != rid
    assert [x["address"] for x in served(world)] == [f"api/write/work/{rid}", "api/write/work/example-held/start"]


def test_a_roster_person_with_no_office_cannot_open_the_private_view_so_the_run_stays_reduced(app, world):
    rid = start(world)
    assert as_(app, ROSTER_ONLY).get("/api/work").status_code == 403
    c = webclient.sign_in(webclient.client(app), ADMIN, rows=ROWS)
    assert c.post("/api/private", json={"reason": "x"}).status_code == 403
    assert c.get(f"/api/work-run?definition=example-held&id={rid}").status_code == 404


def test_the_private_view_belongs_to_the_one_who_opened_it(app, world):
    rid = start(world)
    a = as_(app, TREASURER, private=True)
    b = as_(app, "Dana Director")
    assert rows_by(a.get("/api/work"))[rid]["held"] is False
    assert rows_by(b.get("/api/work"))[rid]["held"] is True


def test_a_failed_log_serves_nothing(app, world, monkeypatch):
    rid = start(world)
    c = as_(app, TREASURER, private=True)

    def broken(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr("jason.web.access.served", broken)
    r = c.get(f"/api/work-run?definition=example-held&id={rid}")
    assert r.status_code == 503 and LABEL not in r.get_data(as_text=True)
    assert c.post(f"/api/write/work/example-held/{rid}", json={"act": "note", "text": "x"}).status_code == 503


# --- the office view --------------------------------------------------------------------------------------------------------


def test_the_office_view_names_a_held_run_by_its_general_title_outside_the_private_view(app, world):
    rid = start(world)
    plain = start(world, "example-cycle", subject="campaign:EX-2099", label="Plain run")
    r = as_(app, TREASURER).get("/api/office-view?office=manager")
    assert r.status_code == 200
    rows = {x["id"]: x for x in r.json["bands"]["work"]}
    no_leak(rows[rid])
    assert rows[rid]["held"] is True and rows[rid]["label"] == HELD_TITLE and rows[rid]["title"] == HELD_TITLE
    assert rows[rid]["step"] == "" and rows[rid]["stepTitle"] == "a step" and rows[rid]["text"] == f"{HELD_TITLE}: a step"
    assert rows[plain]["held"] is False and rows[plain]["label"] == "Plain run"
    assert not served(world)


def test_the_office_view_names_it_in_full_inside_the_private_view_and_logs_it(app, world):
    rid = start(world)
    r = as_(app, TREASURER, private=True).get("/api/office-view?office=manager")
    rows = {x["id"]: x for x in r.json["bands"]["work"]}
    assert rows[rid]["held"] is False and rows[rid]["label"] == LABEL
    assert [x["address"] for x in served(world)] == ["api/office-view"] and served(world)[0]["runs"] == 1


# --- an administrator's definition and its runs -----------------------------------------------------------------------------


def test_an_administrator_with_no_office_reads_starts_and_acts_on_the_administrators_definitions(app, world):
    c = as_(app, ADMIN)
    cat = {d["key"] for d in c.get("/api/work-definitions").json["definitions"]}
    assert {"example-admin", "example-terminal", "integration-connect", "service-run", "check-in"} <= cat
    assert not cat & {"example-cycle", "example-held", "hearing", "board-meeting"}
    made = c.post("/api/write/work/example-admin/start", json={"subject": "service:example", "label": "A service", "dates": DATES, "yes": True})
    assert made.status_code == 200, made.get_data(as_text=True)[:200]
    rid = made.json["id"]
    listed = c.get("/api/work?state=all")
    assert [x["id"] for x in listed.json["runs"]] == [rid] and listed.json["counts"]["open"] == 1
    assert c.get(f"/api/work-run?definition=example-admin&id={rid}").status_code == 200


def test_a_board_member_who_is_not_an_administrator_gets_the_administrators_definitions_neither_listed_nor_read_nor_started(app, world):
    rid = start(world, "example-admin", subject="service:example", label="A service")
    for who in (TREASURER, MANAGER):
        c = as_(app, who)
        cat = c.get("/api/work-definitions")
        assert not {"example-admin", "example-terminal", "integration-connect", "service-run", "check-in"} & {d["key"] for d in cat.json["definitions"]}
        assert c.get("/api/work-definitions?key=example-admin").status_code == 404
        listed = c.get("/api/work?state=all")
        assert rid not in {x["id"] for x in listed.json["runs"]} and listed.json["counts"]["open"] == 0
        assert "example-admin" not in {d["key"] for d in listed.json["definitions"]}
        assert "A service" not in listed.get_data(as_text=True)
        read = c.get(f"/api/work-run?definition=example-admin&id={rid}")
        missing = c.get("/api/work-run?definition=example-admin&id=run-0000000000")
        assert read.status_code == missing.status_code == 404
        assert read.get_data(as_text=True).replace(rid, "RID") == missing.get_data(as_text=True).replace("run-0000000000", "RID")
        act = c.post(f"/api/write/work/example-admin/{rid}", json={"act": "note", "text": "x"})
        assert act.status_code == 404
        started = c.post("/api/write/work/example-admin/start", json={"subject": "s", "label": "l", "dates": DATES, "yes": True})
        unknown = c.post("/api/write/work/example-nothing/start", json={"subject": "s", "label": "l", "dates": DATES, "yes": True})
        assert started.status_code == unknown.status_code == 400
        assert started.get_data(as_text=True).replace("example-admin", "NAME") == unknown.get_data(as_text=True).replace("example-nothing", "NAME")
    assert len(store.read(world, "example-admin", rid).events) == store.read(world, "example-admin", rid).n


def test_an_administrator_who_also_holds_an_office_sees_both(app, world):
    admin_run = start(world, "example-admin", subject="service:example", label="A service")
    board_run = start(world, "example-cycle", subject="campaign:EX-2099", label="Plain run")
    c = as_(app, BOTH)
    got = rows_by(c.get("/api/work"))
    assert got[admin_run]["label"] == "A service" and got[board_run]["label"] == "Plain run"
    assert c.get(f"/api/work-run?definition=example-admin&id={admin_run}").status_code == 200


def test_the_office_view_lists_an_administrators_run_for_an_administrator_only(app, world):
    admin_run = start(world, "example-admin", subject="service:example", label="A service")
    seen = lambda who: {x["id"] for x in as_(app, who).get("/api/office-view?office=manager").json["bands"]["work"]}   # noqa: E731
    assert admin_run in seen(BOTH) and admin_run not in seen(TREASURER)


def test_a_terminal_procedure_is_listed_to_an_administrator_and_never_started_from_the_console(app, world):
    c = as_(app, ADMIN)
    row = {d["key"]: d for d in c.get("/api/work-definitions").json["definitions"]}["example-terminal"]
    assert row["startable"] is False and "terminal" in row["startableWhy"]
    r = c.post("/api/write/work/example-terminal/start", json={"subject": "s", "label": "l", "dates": DATES, "yes": True})
    assert r.status_code == 403 and "never starts it" in r.json["error"]
    assert store.list_runs(world) == []


def test_the_real_administrator_definitions_are_registered_and_check_in_is_not_started_from_the_console(app, world):
    c = as_(app, ADMIN)
    rows = {d["key"]: d for d in c.get("/api/work-definitions").json["definitions"]}
    assert {"integration-connect", "service-run", "check-in"} <= set(rows)
    assert rows["check-in"]["startable"] is False and rows["integration-connect"]["startable"] is True
    assert rows["check-in"]["visibility"] == "admin"
    assert c.post("/api/write/work/check-in/start", json={"subject": "change:x", "label": "l", "dates": {}, "yes": True}).status_code == 403
    for key in ("integration-connect", "service-run", "check-in"):
        assert as_(app, TREASURER).get(f"/api/work-definitions?key={key}").status_code == 404


# --- the run id is a handle -------------------------------------------------------------------------------------------------


def test_a_run_id_is_not_derived_from_its_subject_and_cannot_be_recovered_by_trying_addresses(world):
    a = start(world, open_=False)
    b = start(world, open_=False)                           # the same definition, subject, and open time
    assert a != b and a.startswith("run-") and len(a) == 14
    streets = [f"unit:{n} Main St" for n in range(1, 400)]
    guesses = {store.run_id("example-held", s, AT) for s in streets}
    assert a not in guesses and b not in guesses            # the unsalted hash of the subject is not the id
    assert ADDRESS not in a and "main" not in a
    first = store.read(world, "example-held", a).events[0]
    assert "salt" not in json.dumps(first.to_dict())         # the random part is kept nowhere


def test_the_scope_outside_a_request_is_the_person_at_the_terminal(world):
    from jason.web.extra import work

    rid = start(world, "example-admin", subject="service:example", label="A service")
    held = start(world)
    out = work.work({})
    got = {r["id"]: r for r in out["runs"]}
    assert got[rid]["label"] == "A service" and got[held]["held"] is False and got[held]["label"] == LABEL
    assert not served(world)


# --- item sets in a held run -------------------------------------------------------------------------------------------------


def held_items(world):
    """A held item flow with two items supplied; the item ids are the only thing a leak test looks for."""
    from test_workflows_engine_v3 import item_flow

    definitions.register(item_flow(key="item-held", title="Example item hearing", visibility=Visibility.HELD, held_title=HELD_TITLE))
    rid = start(world, "item-held", subject=SUBJECT, label=LABEL, dates={})
    api.supply_items(world, rid, "requests", ["req:7001", "req:7002"], MANAGER, today=TODAY, at=AT)
    return rid


def test_a_held_run_outside_the_private_view_gives_a_count_of_items_and_no_item_id(app, world):
    rid = held_items(world)
    r = as_(app, TREASURER).get(f"/api/work-run?definition=item-held&id={rid}")
    assert r.status_code == 200 and r.json["held"] is True
    blob = r.get_data(as_text=True)
    for word in ("req:7001", "req:7002", "7001", "requests", "Read each request", LABEL, SUBJECT):
        assert word not in blob, word
    run = r.json["run"]
    assert run["itemTotal"] == 2 and run["itemCount"] == 0 and "itemSets" not in run
    assert r.json["steps"] == [] and r.json["clocks"] == [] and r.json["history"] == [] and "groups" not in r.json
    assert run["acts"]["supplyItems"]["offered"] is False and run["acts"]["supplyItems"]["sets"] == []
    listed = as_(app, TREASURER).get("/api/work")
    assert "req:7" not in listed.get_data(as_text=True)
    assert "req:7" not in json.dumps(rows_by(listed)[rid])
    assert not served(world)


def test_supplying_items_to_a_held_run_outside_the_private_view_is_the_404_a_missing_run_gets_and_a_dry_run_too(app, world):
    rid = held_items(world)
    n = store.read(world, "item-held", rid).n
    c = as_(app, MANAGER)
    missing = c.post("/api/write/work/item-held/run-0000000000", json={"act": "supply-items", "set": "requests", "items": ["req:1"]})
    assert missing.status_code == 404
    for extra in ({}, {"dryRun": True}):
        r = c.post(f"/api/write/work/item-held/{rid}", json={"act": "supply-items", "set": "requests", "items": ["req:1"], **extra})
        assert r.status_code == 404, extra
        assert r.get_data(as_text=True).replace(rid, "RID") == missing.get_data(as_text=True).replace("run-0000000000", "RID")
    assert store.read(world, "item-held", rid).n == n and not served(world)


def test_inside_the_private_view_the_items_show_and_may_be_supplied_and_each_opening_is_logged_without_an_id(app, world):
    rid = held_items(world)
    c = as_(app, MANAGER, private=True)
    page = c.get(f"/api/work-run?definition=item-held&id={rid}")
    assert page.status_code == 200 and page.json.get("held") is None
    step = {s["id"]: s for s in page.json["steps"]}["i.1"]
    assert [i["item"] for i in step["items"]] == ["req:7001", "req:7002"]
    assert page.json["run"]["acts"]["supplyItems"]["offered"] is True
    made = c.post(f"/api/write/work/item-held/{rid}", json={"act": "supply-items", "set": "requests", "items": ["req:7003"]})
    assert made.status_code == 200, made.json
    assert "req:7003" not in json.dumps(made.json["run"]["history"])
    lines = served(world)
    assert [x["address"] for x in lines] == [f"api/work-run/{rid}", f"api/write/work/{rid}"]
    assert "req:7" not in json.dumps(lines)                                              # the log names the run, never an item


# --- the step guide on a held run: general titles only outside the private view -----------------------------------------------------

GUIDE_WORDS = ("Seal the envelope before dawn", "Check the seal", "Ask the keeper of the seal", "guided-held")


def held_guided(key="example-held-guided"):
    """A held definition whose person step carries a Support with words that name the matter, so a leak is easy to see."""
    from jason.workflows.types import Check, Cmd, Guides, Reminds, Role, Support

    support = Support(reminds=Reminds(after_hours=24),
                      guides=Guides(instruction=GUIDE_WORDS[0], checklist=(Check(GUIDE_WORDS[1], required=True),),
                                    commands=(Cmd("example notice --send --by NAME"),), done_when="The seal is intact.",
                                    blocked=GUIDE_WORDS[2], ask=(Role.MANAGER,)))
    base = held_def(key)
    return replace(base, steps=tuple(replace(s, support=support) if s.id == C2 else s for s in base.steps))


def test_a_held_run_outside_the_private_view_carries_no_enable_nudge_or_guide(app, world):
    definitions.register(held_guided(), plan_kinds={"example-plan"}, jobs={"example-report"})
    rid = start(world, "example-held-guided")
    for who in (TREASURER, MANAGER):
        r = as_(app, who).get(f"/api/work-run?definition=example-held-guided&id={rid}")
        assert r.status_code == 200 and r.json["held"] is True
        text = r.get_data(as_text=True)
        for word in GUIDE_WORDS:
            assert word not in text, (who, word)
        for key in ("guide", "enable", "nudge", "lookAt", "checklist", "doneWhen"):
            assert f'"{key}"' not in text, (who, key)
    listing = as_(app, TREASURER).get("/api/work").get_data(as_text=True)
    assert not any(word in listing for word in GUIDE_WORDS) and '"guide"' not in listing
    catalog = as_(app, TREASURER).get("/api/work-definitions?key=example-held-guided").get_data(as_text=True)
    assert not any(word in catalog for word in GUIDE_WORDS)                       # the catalog says what is covered in words, not the words
    c = as_(app, MANAGER)
    assert c.post(f"/api/write/work/example-held-guided/{rid}", json={"act": "claim", "step": C2}).status_code == 404       # the 404 a missing run gets
    assert not served(world)


def test_inside_the_private_view_the_whole_panel_shows(app, world):
    definitions.register(held_guided(), plan_kinds={"example-plan"}, jobs={"example-report"})
    rid = start(world, "example-held-guided")
    r = as_(app, MANAGER, private=True).get(f"/api/work-run?definition=example-held-guided&id={rid}")
    assert r.status_code == 200 and r.json.get("held") is None
    step = r.json["steps"][1]
    assert step["guide"]["instruction"] == GUIDE_WORDS[0] and step["guide"]["blocked"] == GUIDE_WORDS[2]
    assert step["enable"]["state"] == "ready" and step["nudge"]["band"] in ("quiet", "stale")
    assert [x["address"] for x in served(world)] == [f"api/work-run/{rid}"]       # the opening is logged, as it is for the whole run


def test_held_guidance_with_an_address_is_refused_when_the_definition_registers():
    from jason.workflows.types import Guides, Support

    bad = Support(guides=Guides(instruction="Write to a.owner@example.org."))
    base = held_def("example-held-bad")
    wf = replace(base, steps=tuple(replace(s, support=bad) if s.id == C2 else s for s in base.steps))
    found = definitions.validate(wf, plan_kinds={"example-plan"}, jobs={"example-report"})
    assert any("an address or handle" in p.message for p in found)
