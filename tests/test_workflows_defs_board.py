"""The board family's general workflow definitions (src/jason/workflows/defs/board.py; docs/workflows/board-governance.md).

Table-driven: the expected kinds, roles, and procedure addresses are written out here from the family page, so a change to a
step is a change to this file too. Everything is made up ("S. Secretary", 2099); no real store, no network, no profile.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from jason.community import procedures
from jason.workflows import api, definitions
from jason.workflows import definitions_general as general
from jason.workflows.defs import all_builders, board
from jason.workflows.readers import CHECKS, JOBS
from jason.workflows.resume import Readers
from jason.workflows.types import CheckResult, ClockBasis, Role, StepKind, StepState, Visibility, parse_sop
import shelf_support
from shelf_support import needs_shelf
from test_workflows_support import data  # noqa: F401 - the `data` fixture

REPO = Path(__file__).resolve().parents[1]
SHELF = REPO / "data"
KINDS = {"p": StepKind.PERSON, "pl": StepKind.PLAN, "d": StepKind.DECISION, "w": StepKind.WAIT, "b": StepKind.BRANCH,
         "c": StepKind.CHECK}
ROLES = {"m": Role.MANAGER, "s": Role.SECRETARY, "t": Role.TREASURER, "a": Role.ADMINISTRATOR, "j": Role.JASON,
         "any": Role.ANYONE}

# key -> (builder, rows "number kind role sop"); "-" is no procedure address
TABLE = {
    "board-meeting": (board.board_meeting, """
        1 p m board-packet#1;  2 c j board-packet#1;  3 b s board-packet#2;  4 p m board-packet#5;  5 p m board-packet#7
        6 p t board-packet#7;  7 p m board-packet#8;  8 p m board-packet#8;  9 p s board-packet#9;  10 p s -
        11 pl s -;  12 p s -;  13 w j -;  14 p s board-packet#10;  15 p s -;  16 d s -;  17 c j -;  18 p s board-packet#3
        19 c j board-packet#3;  20 p s board-packet#4;  21 d s board-packet#4;  22 c j -"""),
    "rule-change": (board.rule_change, """
        0 c j -;  1 b any rule-change#1;  2 c j -;  3 p any rule-change#2;  4 p m rule-change#2;  5 p m -
        6 c j rule-change#4;  7 p s rule-change#3;  8 p s rule-change#5;  9 w s rule-change#5;  10 p s -;  11 w s -
        12 w j -;  13 d s -;  14 c j rule-change#6;  15 p s -;  16 w s -;  17 w s -;  18 b s -;  19 p m rule-change#7
        20 p m -"""),
    "election": (board.election, """
        1 b s election#1;  2 p any election#2;  2.1 d s -;  2.2 b s -;  3 c j -;  4 p s -;  5 p s -;  6 p s -
        7 p s election#4;  8 p s -;  9 p s -;  10 b s -;  10.1 d s -;  11 p s election#4;  12 pl m -;  12.1 p m -
        13 w j -;  14 p s -;  15 b s -;  15.1 p s -;  16 p s -;  17 p s election#6;  18 w s -"""),
    "hearing": (board.hearing, """
        1 p m -;  2 c j -;  3 w s -;  4 p m -;  5 p m -;  6 pl m -;  7 p m -;  8 c j -;  9 w s -;  10 p s -;  11 d s -
        12 b s -;  13 p m -;  14 w s -;  15 c j -;  16 c j -"""),
    "law-review": (board.law_review, """
        1 p m law-review#1;  2 c j law-review#2;  3 p m law-review#3;  4 c j law-review#4;  5 p m law-review#5
        6 p m law-review#6;  7 p m law-review#7;  8 p a law-review#8;  9 p m law-review#9;  10 c j law-review#10
        11 p m law-review#11;  12 d s law-review#12;  13 d s -;  14 p m -"""),
    "duty-schedule": (board.duty_schedule, """
        1 c j duty-schedule#1;  2 p m duty-schedule#2;  3 p m duty-schedule#3;  4 p any duty-schedule#4
        5 b m duty-schedule#5;  5.1 pl m duty-schedule#5;  5.2 d s duty-schedule#5;  6 p m duty-schedule#6
        7 c j duty-schedule#7;  8 d s duty-schedule#8"""),
    "document-duties": (board.document_duties, """
        1 p m document-duties#1;  2 p m document-duties#2;  3 p m document-duties#3;  4 p m document-duties#4
        5 p a document-duties#5"""),
    "owners-manual": (board.owners_manual, """
        1 p m owners-manual#1;  2 p m rule-history#1;  3 c j owners-manual#2;  4 p m owners-manual#3;  5 c j owners-manual#4
        6 c j owners-manual#5;  7 p m owners-manual#6;  8 p m owners-manual#7;  9 d s owners-manual#9;  10 p m owners-manual#8
        11 p m owners-manual#10"""),
}

# key -> {step number: (cite, slot, days)}: the law clocks, the statute on the shelf and the day-count from the slot
LAW = {
    "board-meeting": {"2": ("CIV 4920(a)", "meeting_on", -4), "9": ("CIV 4920(d)", "", 0), "11": ("CIV 4920(a)", "meeting_on", -4),
                      "12": ("CIV 4920(a)", "meeting_on", -4), "13": ("CIV 4920(a)", "meeting_on", -4),
                      "20": ("CIV 4950(a)", "meeting_on", 30)},
    "rule-change": {"7": ("CIV 4360(a)", "decision_on", -28), "8": ("CIV 4360(a)", "decision_on", -28),
                    "9": ("CIV 4360(a)", "decision_on", -28), "10": ("CIV 4360(b)", "decision_on", 0),
                    "11": ("CIV 4920(a)", "decision_on", -4), "15": ("CIV 4360(c)", "decision_on", 15),
                    "16": ("CIV 4360(c)", "decision_on", 15), "17": ("CIV 4365(b)", "", 0)},
    "election": {"3": ("CIV 5105(h)(4)(B)(iii)", "count_on", -90), "4": ("CIV 5110(a)", "", 0),
                 "6": ("CIV 5105(a)(7)", "ballots_out", -30), "7": ("CIV 5115(a)", "nomination_deadline", -30),
                 "8": ("CIV 5103(b)(1)", "nomination_deadline", -90), "9": ("CIV 5103(c)", "", 0),
                 "11": ("CIV 5115(b)", "ballots_out", -30), "12": ("CIV 5115(c)", "voting_deadline", -30),
                 "14": ("CIV 5120(a)", "count_on", 0), "15.1": ("CIV 5115(d)(3)", "", 0),
                 "16": ("CIV 5120(b)", "count_on", 15), "18": ("CIV 5145(a)", "", 0)},
    "hearing": {"2": ("CIV 5855(a)", "hearing_on", -10), "4": ("CIV 5855(a)", "hearing_on", -10),
                "6": ("CIV 5855(a)", "hearing_on", -10), "7": ("CIV 5855(a)", "hearing_on", -10),
                "8": ("CIV 5855(a)", "hearing_on", -10), "9": ("CIV 5855(c)", "", 0),
                "13": ("CIV 5855(f)", "action_on", 14), "14": ("CIV 5855(f)", "action_on", 14)},
    "law-review": {}, "duty-schedule": {}, "document-duties": {}, "owners-manual": {},
}

BUILT = tuple(TABLE)


def rows(key):
    out = []
    for raw in TABLE[key][1].replace("\n", ";").split(";"):
        parts = raw.split()
        if parts:
            n, kind, role, sop = parts
            out.append((f"{key}.{n}", KINDS[kind], ROLES[role], "" if sop == "-" else sop))
    return out


@pytest.fixture(autouse=True)
def fresh():
    definitions.reset()
    yield
    definitions.reset()


def build_all():
    return {key: TABLE[key][0]() for key in TABLE}


# --- which definitions, and which are left out ---------------------------------------------------------------------------

def test_the_builders_are_the_eight_and_hearing_is_a_held_definition():
    keys = [b().key for b in board.BUILDERS]
    assert keys == list(BUILT) and len(set(keys)) == 8
    assert "hearing" in keys and board.LEFT_OUT == ()
    wf = board.hearing()
    assert wf.visibility is Visibility.HELD and wf.held_title == "A member's hearing"
    assert all(w.visibility is Visibility.BOARD and not w.held_title for w in build_all().values() if w.key != "hearing")
    assert board.hearing.__doc__ and "Held" in board.hearing.__doc__ and "left out" not in board.__doc__


def test_the_aggregator_picks_the_family_up():
    ours = {b for b in board.BUILDERS}
    assert ours <= set(all_builders())
    assert not board.LEFT_OUT


def test_each_definition_is_a_board_family_row_and_names_its_procedure():
    for key, wf in build_all().items():
        assert wf.key == key and wf.family == "board" and wf.title and wf.subject and all(s.why or s.kind is StepKind.PERSON for s in wf.steps)
    procs = {"board-meeting": "board-packet", "rule-change": "rule-change", "election": "election", "hearing": "",
             "law-review": "law-review", "duty-schedule": "duty-schedule", "document-duties": "document-duties",
             "owners-manual": "owners-manual"}
    assert {k: w.procedure for k, w in build_all().items()} == procs


# --- the checks against the real registries ------------------------------------------------------------------------------

def test_every_definition_validates_against_the_real_registries_including_the_left_out_one():
    resolver = shelf_support.resolver(SHELF)
    every = build_all()
    for key, wf in every.items():
        problems = definitions.validate(wf, jobs=set(JOBS), resolve_law=resolver, workflows=set(every) | {"election", "owners-manual"})
        assert problems == [], (key, [str(p) for p in problems])


@needs_shelf(SHELF)
def test_every_law_clock_resolves_on_the_shelf_and_corporations_code_7341_is_not_cited():
    resolve = shelf_support.resolver(SHELF)
    seen = set()
    for wf in build_all().values():
        for s in wf.steps:
            if s.clock is not None and s.clock.basis is ClockBasis.LAW:
                assert resolve(s.clock.cite) is True, (s.id, s.clock.cite)
                seen.add(s.clock.cite)
    assert "CIV 4920(a)" in seen and not any(c.startswith("CORP") for c in seen)
    for wf in build_all().values():
        assert "7341" not in "".join(s.clock.cite for s in wf.steps if s.clock)


def test_sop_addresses_exist_in_the_procedures():
    assert definitions.drift(build_all().values()) == []
    found = 0
    for wf in build_all().values():
        for s in wf.steps:
            if s.sop:
                key, index = parse_sop(s.sop)
                assert 1 <= index <= len(procedures.find(key).steps), s.id
                found += 1
    assert found == sum(1 for key in TABLE for r in rows(key) if r[3])


# --- the page's tables, written out ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("key", list(TABLE))
def test_step_ids_kinds_roles_and_procedure_addresses_are_the_pages(key):
    wf = TABLE[key][0]()
    assert [(s.id, s.kind, s.role, s.sop) for s in wf.steps] == rows(key)


def test_step_counts():
    counts = {k: len(w.steps) for k, w in build_all().items()}
    assert counts == {"board-meeting": 22, "rule-change": 21, "election": 23, "hearing": 16, "law-review": 14,
                      "duty-schedule": 10, "document-duties": 5, "owners-manual": 11}


def test_every_decision_step_is_recorded_by_the_secretary_and_no_person_step_is_jasons():
    for wf in build_all().values():
        for s in wf.steps:
            if s.kind is StepKind.DECISION:
                assert s.role is Role.SECRETARY, s.id
            if s.kind is StepKind.PERSON:
                assert s.role not in (Role.JASON, Role.SCHEDULER), s.id
    assert sum(1 for w in build_all().values() for s in w.steps if s.kind is StepKind.DECISION) == 11


# step id -> the read it names (jason.workflows.checks.board): the person steps that became checks
CHECKED = {
    "board-meeting.2": "meeting-clocks", "board-meeting.13": "notice-delivery-read", "board-meeting.19": "minutes-checks",
    "board-meeting.22": "run-complete", "rule-change.14": "rule-stages", "hearing.2": "hearing-dates",
    "law-review.2": "readings-stale", "law-review.4": "shelf-cites", "duty-schedule.1": "schedule-due",
    "duty-schedule.7": "schedule-coverage",
    # the twelve that waited for a read (checks/board.py): each step now names it
    "board-meeting.17": "executive-note-open", "rule-change.0": "rule-in-force", "rule-change.2": "rule-authority",
    "rule-change.6": "notice-text", "election.3": "election-rules-window", "hearing.8": "hearing-delivery-read",
    "hearing.15": "hearing-requirements-met", "hearing.16": "hearing-minutes-note", "law-review.10": "retire-reasons",
    "owners-manual.3": "manual-headings", "owners-manual.5": "manual-concordance", "owners-manual.6": "manual-template-equal",
}


def test_plans_use_only_the_registered_kinds_and_every_check_a_step_names_is_registered_and_no_job_is_named():
    plans = sorted((s.id, s.plan_kind) for w in build_all().values() for s in w.steps if s.kind is StepKind.PLAN)
    assert plans == [("board-meeting.11", "gmail-drafts"), ("duty-schedule.5.1", "gmail-drafts"),
                     ("election.12", "payhoa-mailroom-send"), ("hearing.6", "gmail-drafts")]
    from jason.workflows.checks import load_all

    load_all()
    named = {s.id: s.check.name for w in build_all().values() for s in w.steps if s.check is not None}
    assert named == CHECKED
    assert all(name in CHECKS for name in named.values())
    assert not [s.id for w in build_all().values() for s in w.steps if s.job or s.kind is StepKind.JOB]
    for w in build_all().values():
        for s in w.steps:
            if s.check is not None:
                assert s.role is Role.JASON and s.kind in (StepKind.CHECK, StepKind.WAIT) and "Becomes" not in s.why, s.id
    assert "payhoa-mailroom-send" in (definitions.default_plan_kinds() or {"payhoa-mailroom-send"})


@pytest.mark.parametrize("key", list(LAW))
def test_the_law_clocks_are_the_pages_with_their_day_counts(key):
    wf = TABLE[key][0]()
    got = {s.id.split(".", 1)[1]: (s.clock.cite, s.clock.slot, s.clock.days)
           for s in wf.steps if s.clock is not None and s.clock.basis is ClockBasis.LAW}
    assert got == LAW[key]
    for s in wf.steps:
        if s.clock is not None and s.clock.slot:
            assert s.clock.slot in {d.name for d in wf.dates}
        if s.is_legal:
            assert s.skip is None, s.id
    for s in wf.steps:
        if s.clock is not None and s.clock.basis is ClockBasis.LAW and s.clock.slot:
            assert "computed" in s.clock.label and "plain day-count" in s.clock.label, s.id


def test_a_clock_that_is_not_the_laws_says_what_it_is():
    for wf in build_all().values():
        for s in wf.steps:
            if s.clock is not None and s.clock.basis is ClockBasis.PROPOSED_POLICY:
                assert "proposed policy" in s.clock.label, s.id


# --- what it wants, and what it does not touch ----------------------------------------------------------------------------

def test_wanted_is_what_the_whys_say_each_step_becomes():
    text = " ".join(s.why for w in build_all().values() for s in w.steps)
    assert len(board.WANTED) == len(set(board.WANTED))
    for item in board.WANTED:
        kind, _, name = item.partition(":")
        if kind == "case":
            assert f"case `{name.split('/')[1]}`" in text, item
        elif kind == "kind":
            assert all(f"`{n}`" in text for n in name.split("+")), item
        else:
            assert f"`{name}`" in text, item
    for item in board.WANTED:
        kind, _, name = item.partition(":")
        if kind == "check":
            assert name not in CHECKS, f"{name} is registered now: use it"
        if kind == "job":
            assert name not in JOBS, f"{name} is registered now: use it"


def test_the_module_imports_only_the_engine_types_and_the_standard_library():
    tree = ast.parse((REPO / "src" / "jason" / "workflows" / "defs" / "board.py").read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mods.add(node.module)
        elif isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
    assert mods == {"__future__", "typing", "jason.workflows.readers", "jason.workflows.types"}


def test_the_reads_of_this_family_are_the_twenty_two_in_checks_board_and_no_job_was_added():
    from jason.workflows.checks import board as reads, load_all

    load_all()
    assert {n for n in CHECKS if CHECKS[n].__module__ == reads.__name__} == set(CHECKED.values())
    assert not [n for n in board.WANTED if n.partition(":")[2] in CHECKED.values()]
    assert not [n for n in board.WANTED if n.startswith("check:")]           # every read this family wanted is built
    assert set(JOBS) >= {"payhoa-form-test", "notices-sync"}


def test_no_title_or_subject_carries_a_unit_an_address_or_a_matter():
    for wf in build_all().values():
        banned = ("unit", "123 main", "violation") + (("member", "address") if wf.key == "hearing" else ())
        for text in [wf.title, wf.subject, *(s.title for s in wf.steps)]:
            assert not any(w in text.lower() for w in banned), (wf.key, text)
    assert board.hearing().subject == "hearing"


# --- the paths ------------------------------------------------------------------------------------------------------------

def test_a_branch_skips_the_steps_of_the_paths_not_taken():
    from jason.workflows import fold

    wf = board.board_meeting()
    choices = {c.key: set(c.steps) for c in wf.step("board-meeting.3").choices}
    n = lambda *xs: {f"board-meeting.{x}" for x in xs}                       # noqa: E731
    assert choices["ordinary"] == n(9, 10, 11, 12, 13, 20) and choices["executive_only"] == n(9, 10, 11, 12, 13)
    assert choices["emergency"] == n(20)
    rc = {c.key: set(c.steps) for c in board.rule_change().step("rule-change.1").choices}
    m = lambda *xs: {f"rule-change.{x}" for x in xs}                          # noqa: E731
    assert rc["listed"] == m(6, 7, 8, 9, 10, 17, 18) and rc["not_reached"] == m(17, 18) and rc["emergency"] == set()
    el = {c.key: set(c.steps) for c in board.election().step("election.1").choices}
    assert set(el) == set(board.KIND_PATHS)
    assert el["directors"] == el["recall"] == {f"election.{x}" for x in ("2.1", "2.2", "7", "8", "9", "10", "10.1", "11")}
    assert all(not el[k] for k in ("assessment", "amendment", "exclusive_use", "other"))
    assert fold  # the fold reads these choices; the run below shows it


class Pass(Readers):
    """Every named read passes: these tests are about the paths, not the stores (the reads have tests of their own)."""

    def check(self, step, view, item=""):
        return CheckResult(True, (), "read") if step.check is not None else None


ROLES_OF = {"J. Manager": {"manager"}, "S. Secretary": {"secretary"}, "T. Treasurer": {"treasurer"}, "A. Admin": {"administrator"}}


def roles_of(by):
    return ROLES_OF.get(by, ())


def start(data, key, dates, subject="subject-1", label="A run"):
    general.register_general()
    out = api.start(data, key, subject, label, dates, "J. Manager", yes=True, today=date(2099, 9, 1))
    rid = out["run"]["id"]
    api.open_run(data, rid, "J. Manager", roles_of=roles_of, yes=True, today=date(2099, 9, 1))
    return rid


def states(data, rid, day=date(2099, 9, 1)):
    return {s["id"]: s["state"] for s in api.show(data, rid, today=day)["steps"]}


def settle(data, rid):
    """Open the run again with readers that pass every read, so a ready ``check`` step is done."""
    api.open_run(data, rid, "J. Manager", readers=Pass(), roles_of=roles_of, today=date(2099, 9, 1))


def attest(data, rid, step, by, **more):
    return api.attest(data, rid, step, by, roles_of=roles_of, record=more.pop("record", "recorded"), today=date(2099, 9, 1), **more)


def test_an_emergency_meeting_skips_the_notice_steps_and_an_executive_only_one_skips_the_minutes_availability(data):
    day = date(2099, 10, 20)
    rid = start(data, "board-meeting", {"meeting_on": day.isoformat()})
    attest(data, rid, "board-meeting.1", "J. Manager")
    settle(data, rid)
    attest(data, rid, "board-meeting.3", "S. Secretary", choice="emergency")
    got = states(data, rid)
    assert [got[f"board-meeting.{i}"] for i in (9, 10, 11, 12, 13)] == ["skipped"] * 5 and got["board-meeting.20"] != "skipped"
    rid2 = start(data, "board-meeting", {"meeting_on": day.isoformat()}, subject="2099-10-21")
    attest(data, rid2, "board-meeting.1", "J. Manager")
    settle(data, rid2)
    attest(data, rid2, "board-meeting.3", "S. Secretary", choice="executive_only")
    got2 = states(data, rid2)
    assert got2["board-meeting.20"] == "skipped" and got2["board-meeting.9"] != "skipped"


def test_an_emergency_rule_change_skips_the_member_notice_and_the_reversal_window(data):
    rid = start(data, "rule-change", {"decision_on": "2099-10-20"}, subject="change-1")
    settle(data, rid)                                                  # step 0 is jason's read now
    attest(data, rid, "rule-change.1", "S. Secretary", choice="emergency")
    got = states(data, rid)
    assert [got[f"rule-change.{i}"] for i in (6, 7, 8, 9, 10, 17, 18)] == ["skipped"] * 7
    assert got["rule-change.13"] != "skipped" and got["rule-change.15"] != "skipped"
    rid2 = start(data, "rule-change", {"decision_on": "2099-10-20"}, subject="change-2")
    settle(data, rid2)
    attest(data, rid2, "rule-change.1", "S. Secretary", choice="not_reached")
    got2 = states(data, rid2)
    assert got2["rule-change.7"] == "skipped" and got2["rule-change.17"] != "skipped"


def test_a_member_vote_has_no_nominations_and_an_acclamation_skips_the_ballots(data):
    dates = {"ballots_out": "2100-04-01", "voting_deadline": "2100-05-03", "count_on": "2100-05-04"}
    rid = start(data, "election", dates, subject="vote-1")
    attest(data, rid, "election.1", "S. Secretary", choice="assessment")
    got = states(data, rid)
    assert [got[f"election.{i}"] for i in ("2.1", "2.2", "7", "8", "9", "10", "10.1", "11")] == ["skipped"] * 8
    assert got["election.12"] != "skipped" and got["election.14"] != "skipped"
    rid2 = start(data, "election", dict(dates, nomination_deadline="2100-03-01"), subject="vote-2")
    attest(data, rid2, "election.1", "S. Secretary", choice="directors")
    attest(data, rid2, "election.2", "J. Manager")
    attest(data, rid2, "election.2.1", "S. Secretary", outcome="approved", motion="make acclamation available")
    attest(data, rid2, "election.2.2", "S. Secretary", choice="not_available")
    assert states(data, rid2)["election.8"] == "skipped"
    settle(data, rid2)                                                 # step 3, the election rules' window, is jason's read now
    for n, who in (("4", "S. Secretary"), ("5", "S. Secretary")):
        attest(data, rid2, f"election.{n}", who)
    attest(data, rid2, "election.7", "S. Secretary")
    attest(data, rid2, "election.9", "S. Secretary")
    attest(data, rid2, "election.10", "S. Secretary", choice="acclaim")
    got2 = states(data, rid2)
    assert all(got2[f"election.{i}"] == "skipped" for i in ("11", "12", "12.1", "13", "14", "15", "15.1"))
    assert got2["election.10.1"] != "skipped" and got2["election.16"] != "skipped"


def test_the_clocks_are_computed_from_the_runs_dates_and_labeled(data):
    rid = start(data, "board-meeting", {"meeting_on": "2099-10-20"})
    clocks = {c["step"]: c for c in api.show(data, rid, today=date(2099, 9, 1))["clocks"]}
    assert clocks["board-meeting.2"]["due"] == "2099-10-16" and clocks["board-meeting.2"]["cite"] == "CIV 4920(a)"
    assert clocks["board-meeting.20"]["due"] == "2099-11-19" and clocks["board-meeting.20"]["basis"] == "law"
    assert "plain day-count" in clocks["board-meeting.20"]["label"]
    rid2 = start(data, "rule-change", {"notice_on": "2099-09-21", "decision_on": "2099-10-20"}, subject="change-3")
    c2 = {c["step"]: c for c in api.show(data, rid2, today=date(2099, 9, 1))["clocks"]}
    assert c2["rule-change.7"]["due"] == "2099-09-22" and c2["rule-change.15"]["due"] == "2099-11-04"
    assert c2["rule-change.4"]["basis"] == "proposed policy" and c2["rule-change.17"]["status"] == "undated"
    rid3 = start(data, "election", {"nomination_deadline": "2100-03-01", "ballots_out": "2100-04-01",
                                    "voting_deadline": "2100-05-03", "count_on": "2100-05-04"}, subject="vote-3")
    c3 = {c["step"]: c for c in api.show(data, rid3, today=date(2099, 9, 1))["clocks"]}
    assert c3["election.8"]["due"] == "2099-12-01" and c3["election.7"]["due"] == "2100-01-30"
    assert c3["election.11"]["due"] == "2100-03-02" and c3["election.12"]["due"] == "2100-04-03"
    assert c3["election.16"]["due"] == "2100-05-19" and c3["election.3"]["due"] == "2100-02-03"


def test_dates_are_checked_at_start():
    wf = board.rule_change()
    assert wf.check_dates({"decision_on": "2099-10-20"}) == []
    assert wf.check_dates({"notice_on": "2099-10-21", "decision_on": "2099-10-20"})
    assert board.election().check_dates({"ballots_out": "2100-04-01", "voting_deadline": "2100-03-01", "count_on": "2100-05-04"})
    assert board.board_meeting().check_dates({}) == ["date meeting_on is required"]
    assert board.law_review().check_dates({}) == []


# --- registration ---------------------------------------------------------------------------------------------------------

def test_register_general_registers_the_family_beside_the_existing_two_with_hearing_held():
    registered = general.register_general(resolve_law=shelf_support.resolver(SHELF))
    keys = {w.key for w in registered}
    assert {"owner-info-cycle", "control-adoption"} <= keys
    assert set(BUILT) <= keys and "hearing" in keys
    assert {w.key for w in definitions.all_definitions()} >= keys
    assert definitions.find("hearing").visibility is Visibility.HELD and definitions.find("board-meeting").subject == "meeting"


def test_the_held_hearing_validates():
    wf = board.hearing()
    assert definitions.validate(wf, jobs=set(JOBS), resolve_law=shelf_support.resolver(SHELF)) == []
    assert wf.has_legal_clock() and all(s.sop == "" for s in wf.steps) and not any(s.public_title for s in wf.steps)


# --- one run, end to end ---------------------------------------------------------------------------------------------------

def test_document_duties_runs_from_start_to_done_in_a_temporary_data_folder(data):
    rid = start(data, "document-duties", {}, subject="document:example-bylaws", label="Duties of the example bylaws")
    got = states(data, rid)
    assert got["document-duties.1"] == "needs a person" and got["document-duties.2"] == "not started"
    attest(data, rid, "document-duties.1", "J. Manager")
    assert states(data, rid)["document-duties.2"] == "needs a person"
    with pytest.raises(Exception):
        attest(data, rid, "document-duties.2", "S. Secretary")           # the secretary does not hold the manager's step
    for n in ("2", "3", "4"):
        attest(data, rid, f"document-duties.{n}", "J. Manager")
    attest(data, rid, "document-duties.5", "A. Admin")
    final = api.show(data, rid, today=date(2099, 9, 1))
    assert final["state"] == "done" and all(s["state"] == StepState.DONE.value for s in final["steps"])
    assert api.verify(data, rid)["ok"] is True
