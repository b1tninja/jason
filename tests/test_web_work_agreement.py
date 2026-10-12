"""Work, Today, and the due report name the same step and the same holder (``GET /api/work``, ``GET /api/office-view``,
``GET /api/work-due``), and a run's age counts on the same day as "today". Made-up definitions, people, and 2099 dates in a tmp
data folder; runs are built through the engine API (``jason.workflows.api``), never by writing a file.

The one rule under test: a run is read through one dry fold (``step_guide.folded``), its step is the pressing step
(``work._pressing``), and whose move it is comes from ``work._group``. Today's "Your work" band is those rows the viewer holds, not
the run index's first open step.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
import webclient

from jason.community.base import Officer, OfficerRole
from jason.workflows import api, definitions, nudge
from jason.workflows.types import CheckResult, ClockBasis, ClockDef, Role, StepDef, StepKind, Workflow
from test_workflows_support import C1, C2, DATES, FakeReaders, example_cycle

MANAGER, TREASURER, SECRETARY = "A Manager", "Pat Example", "Sam Secretary"
ROWS = webclient.ROSTER + (("Rae Roster", "", "rae@example.org", False),)
DAY = date(2099, 10, 23)                                   # the day the law's clock on the example person step falls
KW = dict(plan_kinds={"example-plan"}, jobs={"example-report"})
OFFICERS = (
    Officer(OfficerRole.MANAGER, "A Manager", ("the manager",), "a.manager@example.org"),
    Officer(OfficerRole.TREASURER, "Pat Example", ("the treasurer",), "pat@example.org"),
    Officer(OfficerRole.SECRETARY, "Sam Secretary", ("the secretary",), "sam@example.org"),
)
SPLIT = "example-split"
S1, S2 = f"{SPLIT}.1", f"{SPLIT}.2"


def split_flow() -> Workflow:
    """A manager's person step (S1) beside a jason check that fails (S2): the first open step is the manager's, the pressing one is
    jason's failed check."""
    return Workflow(
        key=SPLIT, title="Example split", family="example", subject="campaign", procedure="",
        steps=(
            StepDef(S1, "Refresh the example books", StepKind.PERSON, role=Role.MANAGER, record="the refreshed books"),
            StepDef(S2, "Read the example statements", StepKind.CHECK, role=Role.JASON,
                    check=lambda view: CheckResult(False, (), "the statements are not on file")),
        ))


GATED = "example-gated"
G1, G2 = f"{GATED}.1", f"{GATED}.2"


def gated_flow() -> Workflow:
    """A manager's person step that waits on a jason check that keeps failing: the person step is not started."""
    return Workflow(
        key=GATED, title="Example gated", family="example", subject="campaign", procedure="",
        steps=(
            StepDef(G1, "Read the example statements", StepKind.CHECK, role=Role.JASON,
                    check=lambda view: CheckResult(False, (), "the statements are not on file")),
            StepDef(G2, "Send the example letter", StepKind.PERSON, role=Role.MANAGER, needs=(G1,), record="the letter reference"),
        ))


def law_flow() -> Workflow:
    """example-cycle with its person step on the law's clock, so the due report lists it LEGAL on its day."""
    base = example_cycle()
    c2 = replace(base.step(C2), clock=ClockDef(ClockBasis.LAW, "answers_by", 0, cite="EX 123.4"), legal=True, skip=None)
    return replace(base, steps=tuple(c2 if s.id == C2 else s for s in base.steps))


class Home:
    name = "Example HOA"

    def officers(self):
        return OFFICERS

    def assignments(self):
        return ()


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    monkeypatch.setenv("JASON_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: tmp_path)
    home = Home()
    monkeypatch.setattr("jason.community.community", lambda: home)
    monkeypatch.setattr("jason.access.community_officers", lambda: OFFICERS)
    monkeypatch.setattr("jason.web.extra.work._today", lambda: DAY)
    monkeypatch.setattr("jason.web.extra.office_view._today", lambda: DAY)
    definitions.reset()
    definitions.register(law_flow(), **KW)
    definitions.register(split_flow())
    definitions.register(gated_flow())
    yield tmp_path
    definitions.reset()


@pytest.fixture
def app(world):
    from jason.web.app import create_app
    from jason.web.extra import office_view, work, work_due

    dist = world / "dist"
    dist.mkdir(exist_ok=True)
    return create_app(dist, {"work": work.work, "work-run": work.work_run, "work-due": work_due.work_due, "office-view": office_view.office_view},
                      approvals_live=None, extra_writes=False, sign_in=webclient.roster_sign_in(ROWS))


def get(app, who, path):
    r = webclient.sign_in(webclient.client(app), who, rows=ROWS).get(path)
    assert r.status_code == 200, (path, r.status_code, r.get_data(as_text=True)[:200])
    return r.json


def begin(root, definition, *, label, dates, by=MANAGER, open_it=True, created="2099-10-01T09:00:00Z", today=date(2099, 10, 1)):
    rid = api.start(root, definition, f"campaign:{label}", label, dates, by, yes=True, today=today, at=created)["run"]["id"]
    if open_it:
        api.open_run(root, rid, by, readers=FakeReaders(), yes=True, today=today, at=created.replace("09:00:00", "09:01:00"))
    return rid


# --- D6: one notion of whose move a run is -----------------------------------------------------------------------------------

def test_work_today_and_the_due_report_name_the_same_step_and_the_same_yours_set(app, world):
    agree = begin(world, "example-cycle", label="Example cycle", dates=DATES)             # the manager's law-clocked person step
    split = begin(world, SPLIT, label="Example split", dates={}, created="2099-10-23T09:00:00Z", today=DAY)   # a manager step AND jason's failed check
    draft = begin(world, "example-cycle", label="Example draft", dates=DATES, open_it=False)   # a draft the manager started

    listed = get(app, MANAGER, "/api/work")
    runs = {r["id"]: r for r in listed["runs"]}
    yours = {i for i, r in runs.items() if r["group"] == "yours"}
    assert yours == {agree, draft} and runs[split]["group"] == "others"
    assert runs[agree]["current"]["id"] == C2 and runs[split]["current"]["id"] == S2          # the pressing step, jason's failed check
    assert listed["counts"]["yours"] == 2

    today = get(app, MANAGER, "/api/office-view?office=")
    shown = {r["id"]: r for r in today["bands"]["work"]}
    assert set(shown) == yours                                                              # the same set, the same people
    assert shown[agree]["step"] == runs[agree]["current"]["id"] == C2
    assert shown[draft]["state"] == "draft" and shown[draft]["step"] == runs[draft]["current"]["id"]
    assert split not in shown                                                               # not the manager's move: it waits on jason
    assert today["counts"]["work"] == listed["counts"]["yours"]

    due = get(app, MANAGER, "/api/work-due")
    assert [(r["run"], r["step"]) for r in due["mine"]] == [(agree, C2)]
    assert runs[agree]["current"]["id"] == due["mine"][0]["step"]
    assert any(r["id"] == agree and r["band"] == "legal" for r in today["bands"]["personSteps"])
    assert not any(r["id"] == split for r in today["bands"]["personSteps"])


def test_the_run_a_jason_check_holds_up_is_not_the_managers_move_on_either_screen(app, world):
    """The first open step (the manager's) is not the one a run is about while jason's check has failed: Work and Today agree on that."""
    split = begin(world, SPLIT, label="Example split", dates={}, created="2099-10-23T09:00:00Z", today=DAY)
    view = api.show(world, split, today=DAY)
    assert view["current"] == S1                                                           # the fold's first open step ...
    row = next(r for r in get(app, MANAGER, "/api/work")["runs"] if r["id"] == split)
    assert row["current"]["id"] == S2 and row["waitingOn"]["kind"] == "system"             # ... is not the pressing one
    assert split not in {r["id"] for r in get(app, MANAGER, "/api/office-view?office=manager")["bands"]["work"]}
    assert split not in {r["id"] for r in get(app, MANAGER, "/api/office-view?office=")["bands"]["work"]}


def test_a_lens_on_another_office_holds_no_draft_or_anyone_step_for_it(app, world):
    draft = begin(world, "example-cycle", label="Example draft", dates=DATES, open_it=False)
    assert draft in {r["id"] for r in get(app, MANAGER, "/api/office-view?office=manager")["bands"]["work"]}
    assert draft not in {r["id"] for r in get(app, MANAGER, "/api/office-view?office=treasurer")["bands"]["work"]}
    assert draft not in {r["id"] for r in get(app, TREASURER, "/api/office-view?office=manager")["bands"]["work"]}


# --- D7: a run's age on the day basis of "today" -----------------------------------------------------------------------------

def test_a_run_started_at_23_30_local_is_open_zero_days_not_minus_one(app, world, monkeypatch):
    zone = ZoneInfo("America/Los_Angeles")
    monkeypatch.setattr(nudge, "LOCAL_ZONE", zone)
    local = datetime(2099, 10, 23, 23, 30, tzinfo=zone)                                   # 23:30 on the day the screens read as today
    stamp = local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert stamp.startswith("2099-10-24")                                                  # the UTC stamp is already tomorrow
    rid = begin(world, "example-cycle", label="Example cycle", dates=DATES, created=stamp, today=DAY)
    row = next(r for r in get(app, MANAGER, "/api/work")["runs"] if r["id"] == rid)
    assert row["age"]["days"] == 0 and row["age"]["opened"] == "2099-10-23" and row["age"]["idleDays"] >= 0
    due = get(app, MANAGER, "/api/work-due")["mine"]
    assert due and all(r["openDays"] in (0, None) for r in due)


def test_an_age_is_never_below_zero_and_counts_days_on_the_local_calendar():
    zone = ZoneInfo("America/Los_Angeles")
    before = nudge.LOCAL_ZONE
    nudge.LOCAL_ZONE = zone
    try:
        assert nudge.day_of("2099-10-24T06:30:00Z") == date(2099, 10, 23)
        assert nudge.day_of("2099-10-24T07:30:00Z") == date(2099, 10, 24)                   # after midnight Pacific (PDT is UTC-7)
        assert nudge.day_of("2099-10-23") == date(2099, 10, 23) and nudge.day_of("") is None and nudge.day_of("soon") is None
        assert nudge.days_between(date(2099, 10, 23), nudge.day_of("2099-10-24T06:30:00Z")) == 0
        assert nudge.days_between(date(2099, 10, 23), date(2099, 10, 24)) == 0               # clamped
        assert nudge.days_between(date(2099, 10, 25), date(2099, 10, 23)) == 2
        assert nudge.days_between(date(2099, 10, 25), None) is None
    finally:
        nudge.LOCAL_ZONE = before


# --- D13: a person step that has not started says what it waits on ---------------------------------------------------------

def test_a_person_step_that_has_not_started_says_which_step_it_waits_on(app, world):
    rid = begin(world, GATED, label="Example gated", dates={}, created="2099-10-23T09:00:00Z", today=DAY)
    got = get(app, MANAGER, f"/api/work-run?definition={GATED}&id={rid}")
    step = next(s for s in got["steps"] if s["id"] == G2)
    assert step["state"] in ("not started", "blocked") and step["acts"] == []
    assert step["notOffered"]["attest"] == "Not ready yet: it waits on step 1, Read the example statements."
    assert "not started, not waiting" not in step["notOffered"]["attest"]
