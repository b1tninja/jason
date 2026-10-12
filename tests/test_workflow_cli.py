"""``jason workflow``: every command driven through the argument parser, in a temporary data folder, over the made-up
``example-cycle`` definition (tests/test_workflows_support.py). The people are made up too; the roster is a table the test
supplies in place of the community's officers.
"""

from __future__ import annotations

import json

import pytest

from jason.commands import workflow as cli
from jason.community.base import Officer, OfficerRole
from jason.workflows import definitions
from test_workflows_support import (
    C1, C2, C5, DATES, OWNER, SECRETARY, TREASURER, VISITOR, data, example,
)

REGISTER_GENERAL, READERS = cli._register_general, cli._readers          # the real ones, before the fixture replaces them
ASOF = ["--as-of", "2099-09-20"]
_PARSER = []


def parser():
    if not _PARSER:
        from jason.cli import build_parser

        _PARSER.append(build_parser())
    return _PARSER[0]


@pytest.fixture
def run(data, example, monkeypatch, capsys):
    """``run("--list")`` -> (exit code, stdout, stderr), with the data folder and the roster made up."""
    monkeypatch.setattr("jason.commands._shared.data_dir", lambda args=None: data)
    monkeypatch.setattr(cli, "_officers", lambda: (Officer(OfficerRole.MANAGER, OWNER),
                                                    Officer(OfficerRole.SECRETARY, SECRETARY),
                                                    Officer(OfficerRole.TREASURER, TREASURER)))
    monkeypatch.setattr(cli, "_admins", lambda: ())
    # the made-up definition only: no general one, and the engine's bare readers (the tests that use the real ones say so)
    monkeypatch.setattr(cli, "_register_general", lambda args: None)
    monkeypatch.setattr(cli, "_readers", lambda root, today=None: None)

    def go(*argv):
        args = parser().parse_args(["workflow", *argv])
        code = args.func(args)
        out = capsys.readouterr()
        return code, out.out, out.err

    go.data = data
    return go


def start_args(*extra, by=OWNER):
    dates = [x for k, v in DATES.items() for x in ("--date", f"{k}={v}")]
    return ["--start", "example-cycle", "--subject", "campaign:EX-2099", "--label", "Example cycle 2099", *dates,
            "--by", by, *extra, *ASOF]


def started(run) -> str:
    code, out, err = run(*start_args("--yes", "--json"))
    assert code == 0, err
    return json.loads(out)["run"]["id"]


def opened(run) -> str:
    rid = started(run)
    code, out, err = run("--open", rid, "--by", OWNER, "--yes", *ASOF)
    assert code == 0, err
    return rid


def states(run, rid) -> dict[str, str]:
    code, out, err = run("--show", rid, "--json", *ASOF)
    assert code == 0, err
    return {s["id"]: s["state"] for s in json.loads(out)["steps"]}


# --- the parser -----------------------------------------------------------------------------------------------------

def test_help_works(capsys):
    with pytest.raises(SystemExit) as stop:
        parser().parse_args(["workflow", "--help"])
    assert stop.value.code == 0
    text = capsys.readouterr().out
    for option in ("--list", "--definitions", "--start", "--open", "--show", "--attest", "--skip", "--pause", "--resume",
                   "--reopen", "--note", "--cancel", "--verify", "--reindex", "--from-sop", "--by", "--yes", "--json"):
        assert option in text


def test_the_command_is_registered_in_the_module_list():
    from jason.commands import MODULES

    assert "workflow" in MODULES


def test_one_act_at_a_time(run):
    code, out, err = run("--list", "--definitions")
    assert code == 2 and "one act at a time" in err
    code, out, err = run("--show", "run-x", "--verify", "run-x")
    assert code == 2 and "one act at a time" in err


# --- reading --------------------------------------------------------------------------------------------------------

def test_no_workflows_registered(run):
    definitions.reset()
    code, out, err = run("--definitions")
    assert code == 0 and out.strip() == "No workflows are registered."
    code, out, err = run("--list")
    assert code == 0 and "No runs." in out and "No workflows are registered." in out
    code, out, err = run("--start", "example-cycle", "--subject", "s", "--by", OWNER)
    assert code == 2 and "No workflows are registered." in err


def test_definitions_list_and_family_filter(run):
    code, out, err = run("--definitions")
    assert code == 0 and "example-cycle" in out and "legal clock" in out and "answers_by" in out
    code, out, err = run("--definitions", "--family", "other")
    assert code == 0 and "example-cycle" not in out and "No workflows are registered in the family other." in out
    code, out, err = run("--definitions", "--json")
    rows = json.loads(out)
    assert code == 0 and rows[0]["key"] == "example-cycle" and rows[0]["legalClock"] is True and rows[0]["steps"] == 6


def test_list_show_and_json(run):
    rid = opened(run)
    code, out, err = run("--list")
    assert code == 0 and rid in out and "example-cycle" in out and "active" in out
    code, out, err = run("--list", "--definition", "nothing-here")
    assert code == 0 and "No runs." in out
    code, out, err = run("--list", "--state", "done")
    assert code == 0 and "No runs." in out
    code, out, err = run("--list", "--json")
    rows = json.loads(out)
    assert [r["id"] for r in rows] == [rid] and rows[0]["state"] == "active"

    code, out, err = run("--show", rid, *ASOF)
    assert code == 0 and "Steps" in out and C2 in out and "needs a person" in out and "Clocks" in out
    assert "Events" not in out
    code, out, err = run("--show", rid, "--events", *ASOF)
    assert code == 0 and "Events" in out and "resumed" in out and "check-ran" in out
    code, out, err = run("--show", rid, "--events", "--json", *ASOF)
    body = json.loads(out)
    assert code == 0 and body["id"] == rid and body["state"] == "active" and len(body["events"]) == body["n"]


def test_an_unknown_run_is_refused(run):
    code, out, err = run("--show", "run-nope")
    assert code == 2 and "no run run-nope" in err and out == ""
    code, out, err = run("--verify", "run-nope")
    assert code == 2 and "no run" in err


# --- start and open -------------------------------------------------------------------------------------------------

def test_start_makes_a_draft_and_needs_by_and_yes_for_a_legal_clock(run):
    code, out, err = run(*start_args(by=""))
    assert code == 2 and "--start is a write: it needs --by" in err
    code, out, err = run(*start_args())
    assert code == 2 and "legal clock" in err and "yes" in err
    code, out, err = run(*start_args("--yes"))
    assert code == 0 and "started as a draft" in out and "the run is draft" in out
    rid = out.split(":")[0]
    assert rid.startswith("run-")
    code, out, err = run("--show", rid, "--json")
    assert json.loads(out)["state"] == "draft"


def test_start_refuses_bad_dates_and_a_missing_subject(run):
    code, out, err = run("--start", "example-cycle", "--subject", "s", "--date", "answers_by=soon", "--by", OWNER, "--yes")
    assert code == 2 and "not YYYY-MM-DD" in err
    code, out, err = run("--start", "example-cycle", "--subject", "s", "--date", "answers_by", "--by", OWNER, "--yes")
    assert code == 2 and "NAME=YYYY-MM-DD" in err
    code, out, err = run("--start", "example-cycle", "--subject", "s", "--by", OWNER, "--yes")
    assert code == 2 and "date answers_by is required" in err
    code, out, err = run("--start", "example-cycle", *("--date", "answers_by=2099-10-23", "--date", "closes_on=2099-11-01"),
                         "--by", OWNER, "--yes")
    assert code == 2 and "a run is about a subject" in err
    code, out, err = run("--start", "no-such", "--subject", "s", "--by", OWNER, "--yes")
    assert code == 2 and "no workflow definition no-such" in err and "example-cycle" in err


def test_open_needs_yes_for_a_legal_clock_and_a_second_open_appends_nothing(run):
    rid = started(run)
    code, out, err = run("--open", rid, "--by", OWNER, *ASOF)
    assert code == 2 and "legal clock" in err and "needs yes" in err
    assert states(run, rid)[C1] != "done"
    code, out, err = run("--open", rid, "--yes", *ASOF)
    assert code == 2 and "--open is a write: it needs --by" in err
    code, out, err = run("--open", rid, "--by", OWNER, "--yes", *ASOF)
    assert code == 0 and "opened by" in out and "2 event(s) appended" in out and "check-ran" in out
    assert states(run, rid)[C1] == "done" and states(run, rid)[C2] == "needs a person"
    code, out, err = run("--open", rid, "--by", OWNER, *ASOF)
    assert code == 0 and "0 event(s) appended" in out


# --- the person's acts ----------------------------------------------------------------------------------------------

def test_attest_refuses_the_wrong_role_and_a_missing_record(run):
    rid = opened(run)
    code, out, err = run("--attest", rid, C2, "--record", "notice-1", "--by", VISITOR)
    assert code == 2 and "does not hold the manager role" in err
    code, out, err = run("--attest", rid, C2, "--record", "notice-1", "--by", TREASURER)
    assert code == 2 and "does not hold the manager role" in err
    code, out, err = run("--attest", rid, C2, "--by", OWNER)
    assert code == 2 and "record" in err
    code, out, err = run("--attest", rid, C2, "--record", "notice-1")
    assert code == 2 and "needs --by" in err
    code, out, err = run("--attest", rid, "example-cycle.99", "--record", "x", "--by", OWNER)
    assert code == 2 and "no step example-cycle.99" in err
    code, out, err = run("--attest", rid, C2, "--record", "notice-1", "--by", "jason")
    assert code == 2 and "engine's own name" in err
    assert states(run, rid)[C2] == "needs a person"


def test_attest_records_the_person_under_the_rosters_spelling(run):
    rid = opened(run)
    code, out, err = run("--attest", rid, C2, "--record", "notice-1", "--by", OWNER.lower(), *ASOF)
    assert code == 0, err
    assert f"attested {C2} by {OWNER}" in out and "record=notice-1" in out
    assert states(run, rid)[C2] == "done"
    code, out, err = run("--attest", rid, C2, "--record", "notice-1", "--by", OWNER)
    assert code == 2 and "done, not needs a person" in err
    code, out, err = run("--show", rid, "--events", "--json")
    last = json.loads(out)["events"][-1]
    assert last["kind"] == "attested" and last["by"] == OWNER and last["detail"]["record"] == "notice-1"


def test_a_profile_with_no_officers_refuses_role_gated_acts_and_says_so(run, monkeypatch):
    rid = opened(run)
    monkeypatch.setattr(cli, "_officers", lambda: ())
    code, out, err = run("--attest", rid, C2, "--record", "notice-1", "--by", OWNER)
    assert code == 2 and "does not hold the manager role" in err and "names no officers" in err
    assert states(run, rid)[C2] == "needs a person"

    def broken():
        raise RuntimeError("officers.json is unreadable")

    monkeypatch.setattr(cli, "_officers", broken)
    code, out, err = run("--attest", rid, C2, "--record", "notice-1", "--by", OWNER)
    assert code == 2 and "could not be read" in err and "officers.json is unreadable" in err


def test_skip_is_refused_on_a_legal_step_and_needs_a_reason_elsewhere(run):
    rid = opened(run)
    code, out, err = run("--skip", rid, C5, "--reason", "not needed", "--by", OWNER)
    assert code == 2 and "cannot be skipped" in err and "legal step" in err
    code, out, err = run("--skip", rid, C2, "--by", OWNER)
    assert code == 2 and "needs a reason" in err
    code, out, err = run("--skip", rid, C2, "--reason", "done by the board", "--by", VISITOR)
    assert code == 2 and "may not skip" in err
    code, out, err = run("--skip", rid, C2, "--reason", "done by the board", "--by", OWNER, *ASOF)
    assert code == 0 and f"skipped {C2} by {OWNER}" in out and "reason=done by the board" in out
    assert states(run, rid)[C2] == "skipped"


def test_pause_resume_note_and_reopen(run):
    rid = opened(run)
    code, out, err = run("--pause", rid, "--by", OWNER)
    assert code == 2 and "a pause needs a reason" in err
    code, out, err = run("--pause", rid, "--reason", "waiting on the board", "--by", OWNER, *ASOF)
    assert code == 0 and "the run is paused" in out
    code, out, err = run("--attest", rid, C2, "--record", "r", "--by", OWNER)
    assert code == 2 and "the run is paused" in err
    code, out, err = run("--resume", rid)
    assert code == 2 and "needs --by" in err
    code, out, err = run("--resume", rid, "--by", OWNER, *ASOF)
    assert code == 0 and "the run is active" in out
    code, out, err = run("--resume", rid, "--by", OWNER)
    assert code == 2 and "not paused" in err

    code, out, err = run("--note", rid, "--by", OWNER)
    assert code == 2 and "a note needs text" in err
    code, out, err = run("--note", rid, "--text", "called the example alarm company", "--step", C2, "--by", OWNER, *ASOF)
    assert code == 0 and "note" in out and "called the example alarm company" in out

    run("--attest", rid, C2, "--record", "notice-1", "--by", OWNER)
    code, out, err = run("--reopen", rid, C2, "--by", OWNER)
    assert code == 2 and "reopening needs a reason" in err
    code, out, err = run("--reopen", rid, C1, "--reason", "x", "--by", OWNER)
    assert code == 2 and "does not hold the jason role" in err
    code, out, err = run("--reopen", rid, C2, "--reason", "the notice was wrong", "--by", OWNER, *ASOF)
    assert code == 0 and f"reopened {C2}" in out
    assert states(run, rid)[C2] == "needs a person"


def test_cancel_needs_yes_a_reason_and_the_right_role(run):
    rid = opened(run)
    code, out, err = run("--cancel", rid, "--reason", "wrong subject", "--by", OWNER)
    assert code == 2 and "--cancel needs --yes" in err
    code, out, err = run("--cancel", rid, "--yes", "--by", OWNER)
    assert code == 2 and "a cancel needs a reason" in err
    code, out, err = run("--cancel", rid, "--reason", "wrong subject", "--yes", "--by", TREASURER)
    assert code == 2 and "may not cancel a run with a legal clock" in err
    assert states(run, rid)[C1] == "done"
    code, out, err = run("--cancel", rid, "--reason", "wrong subject", "--yes", "--by", SECRETARY, *ASOF)
    assert code == 0 and "the run is cancelled" in out
    code, out, err = run("--show", rid, *ASOF)
    assert "cancelled: wrong subject" in out
    code, out, err = run("--list")
    assert rid not in out                                  # open runs only
    code, out, err = run("--list", "--state", "all")
    assert rid in out and "cancelled" in out
    code, out, err = run("--cancel", rid, "--reason", "again", "--yes", "--by", SECRETARY)
    assert code == 2 and "already cancelled" in err


def test_a_run_that_moved_on_is_refused(run):
    rid = opened(run)
    code, out, err = run("--show", rid, "--json")
    n = json.loads(out)["n"]
    code, out, err = run("--note", rid, "--text", "first", "--by", OWNER, "--expect", str(n))
    assert code == 0
    code, out, err = run("--note", rid, "--text", "second", "--by", OWNER, "--expect", str(n))
    assert code == 2 and "changed" in err and f"n={n}" in err and "read it again" in err


# --- verify, reindex ------------------------------------------------------------------------------------------------

def test_verify_reports_a_tampered_line(run):
    rid = opened(run)
    code, out, err = run("--verify", rid)
    assert code == 0 and "whole" in out and rid in out
    file = next(run.data.glob(f"workflows/*/{rid}.jsonl"))
    lines = file.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 3
    first = json.loads(lines[0])
    first["detail"]["label"] = "Edited after the fact"
    lines[0] = json.dumps(first, separators=(",", ":"))
    file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    code, out, err = run("--verify", rid)
    assert code == 1 and "BROKEN at n=2" in out and "was edited" in out
    code, out, err = run("--verify", rid, "--json")
    body = json.loads(out)
    assert code == 1 and body["ok"] is False and body["n"] == 2


def test_verify_covers_an_edited_last_line_through_the_index(run):
    rid = opened(run)
    file = next(run.data.glob(f"workflows/*/{rid}.jsonl"))
    lines = file.read_text(encoding="utf-8").splitlines()
    last = json.loads(lines[-1])
    last["by"] = "someone else"
    lines[-1] = json.dumps(last, separators=(",", ":"))
    file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    code, out, err = run("--verify", rid)
    assert code == 1 and "BROKEN" in out


def test_a_torn_last_line_is_reported_and_the_next_write_goes_on(run):
    rid = opened(run)
    file = next(run.data.glob(f"workflows/*/{rid}.jsonl"))
    with open(file, "ab") as handle:
        handle.write(b'{"n":99,"kind":"no')
    code, out, err = run("--show", rid)
    assert code == 0 and "last line is torn" in out
    code, out, err = run("--verify", rid)
    assert code == 0 and "torn" in out
    code, out, err = run("--note", rid, "--text", "after the crash", "--by", OWNER)
    assert code == 0
    code, out, err = run("--verify", rid)
    assert code == 0 and "torn" not in out


def test_reindex_rebuilds_the_list_from_the_events(run):
    rid = opened(run)
    index = run.data / "workflows" / "index.json"
    assert index.is_file()
    index.unlink()
    code, out, err = run("--list")
    assert code == 0 and "No runs." in out
    code, out, err = run("--reindex", *ASOF)
    assert code == 0 and "1 run(s)" in out
    code, out, err = run("--list")
    assert rid in out


# --- from a procedure -----------------------------------------------------------------------------------------------

def test_from_sop_prints_a_draft_and_registers_nothing(run):
    from jason.community.procedures import PROCEDURES

    proc = PROCEDURES[0]
    before = {w.key for w in definitions.all_definitions()}
    code, out, err = run("--from-sop", proc.key)
    assert code == 0 and "DRAFT" in out and "is not registered" in out
    assert f"key='{proc.key}'" in out and out.count("StepDef(") == len(proc.steps)
    assert f"sop='{proc.key}#1'" in out and f"sop='{proc.key}#{len(proc.steps)}'" in out
    namespace: dict = {}
    exec(compile(out, "<draft>", "exec"), namespace)           # it is valid Python, and building it registers nothing
    assert namespace["DRAFT"].key == proc.key and len(namespace["DRAFT"].steps) == len(proc.steps)
    assert {w.key for w in definitions.all_definitions()} == before
    assert definitions.find(proc.key) is None
    assert not (run.data / "workflows").exists()
    code, out, err = run("--from-sop", "no-such-procedure")
    assert code == 2 and "no procedure no-such-procedure" in err


def test_the_draft_maps_a_procedure_steps_kinds():
    from jason.community.procedures import Procedure, Step

    proc = Procedure(key="example-procedure", title="Example", when="yearly", areas=(), purpose="p", steps=(
        Step("Look at the figures", check="the figures match"),
        Step("Run the report", command="jason example --report"),
        Step("The board decides", person=True),
    ))
    text = cli.draft_definition(proc)
    assert "StepKind.CHECK" in text and "StepKind.JOB" in text and "StepKind.PERSON" in text
    assert "needs=('example-procedure.1',)" in text and "command='jason example --report'" in text
    assert "TODO" in text


# --- the general definitions and the stores' readers ----------------------------------------------------------------

def test_the_general_definitions_are_registered_when_a_command_asks_and_not_before(run, monkeypatch):
    assert definitions.find("owner-info-cycle") is None                      # nothing registered them at import
    monkeypatch.setattr(cli, "_register_general", REGISTER_GENERAL)
    code, out, err = run("--definitions")
    assert code == 0 and "owner-info-cycle" in out and "example-cycle" in out and "opens_on" in out and "(has a legal clock)" in out
    code, out, err = run("--definitions", "--family", "members", "--json")
    rows = json.loads(out)
    assert "owner-info-cycle" in [r["key"] for r in rows] and {r["family"] for r in rows} == {"members"}
    definitions.unregister("owner-info-cycle")
    code, out, err = run("--list")
    assert code == 0 and definitions.find("owner-info-cycle") is not None   # listing registers them too


def test_a_general_definition_that_fails_its_checks_is_left_out_and_named(run, monkeypatch, capsys):
    from jason.workflows import definitions_general

    real = definitions_general.register_general
    monkeypatch.setattr(definitions_general, "register_general", lambda root=None, **kw: real(root, plan_kinds={"nothing"}))
    monkeypatch.setattr(cli, "_register_general", REGISTER_GENERAL)
    code, out, err = run("--definitions")
    assert code == 0 and "owner-info-cycle" not in out and "a general definition is left out" in err and "owner-info-tags" in err


def test_a_run_of_the_owner_information_cycle_starts_and_opens_through_the_terminal_over_the_stores(run, monkeypatch):
    monkeypatch.setattr(cli, "_register_general", REGISTER_GENERAL)
    monkeypatch.setattr(cli, "_readers", READERS)
    dates = [x for k, v in {"opens_on": "2099-09-15", "return_by": "2099-10-23", "reports_mailed": "2099-12-01"}.items()
             for x in ("--date", f"{k}={v}")]
    code, out, err = run("--start", "owner-info-cycle", "--subject", "campaign:OI-2099", "--label", "Owner information 2099",
                         *dates, "--by", OWNER, "--yes", "--json", *ASOF)
    assert code == 0, err
    rid = json.loads(out)["run"]["id"]
    code, out, err = run("--open", rid, "--by", OWNER, "--yes", "--json", *ASOF)
    assert code == 0, err
    body = json.loads(out)
    assert body["run"]["state"] == "active" and body["run"]["current"] == "owner-info-cycle.1"
    code, out, err = run("--show", rid, *ASOF)
    assert code == 0 and "Set the cycle's dates" in out and "CIV 4041(b)(1)" in out and "2099-11-01" in out


def test_the_default_readers_are_the_stores_readers_for_the_data_folder_and_the_day():
    from datetime import date

    from jason.workflows.readers import StoreReaders

    got = READERS("somewhere", date(2099, 9, 20))
    assert isinstance(got, StoreReaders) and str(got.data_dir) == "somewhere" and got.today == date(2099, 9, 20)


def test_opening_through_the_stores_readers_runs_a_plain_check_as_before(run, monkeypatch):
    monkeypatch.setattr(cli, "_readers", READERS)
    rid = opened(run)
    assert states(run, rid)[C1] == "done" and states(run, rid)[C2] == "needs a person"


# --- item sets: --supply --------------------------------------------------------------------------------------------

@pytest.fixture
def items(run):
    """``run`` with the made-up item flow (steps over the set ``requests``, a per-item clock) registered beside example-cycle."""
    from test_workflows_engine_v3 import ITEMS, item_flow

    definitions.register(item_flow())
    code, out, err = run("--start", ITEMS, "--subject", "period:2099-10", "--label", "Item flow", "--by", OWNER, "--yes", "--json", *ASOF)
    assert code == 0, err
    rid = json.loads(out)["run"]["id"]
    code, out, err = run("--open", rid, "--by", OWNER, "--yes", *ASOF)
    assert code == 0, err
    return rid


def shown(run, rid) -> dict:
    code, out, err = run("--show", rid, "--json", *ASOF)
    assert code == 0, err
    return json.loads(out)


def supply(run, rid, *extra, by=OWNER):
    return run("--supply", rid, "--set", "requests", "--by", by, *extra, *ASOF)


def test_supply_is_in_the_help_and_is_a_write_that_needs_by(run, capsys):
    with pytest.raises(SystemExit):
        parser().parse_args(["workflow", "--help"])
    text = capsys.readouterr().out
    for option in ("--supply", "--set NAME", "--item-date"):
        assert option in text
    code, out, err = run("--supply", "run-x", "--item", "a")
    assert code == 2 and "--supply is a write: it needs --by" in err


def test_supply_without_yes_prints_what_would_be_recorded_and_writes_nothing(items, run):
    before = shown(run, items)["n"]
    code, out, err = supply(run, items, "--item", "req:1", "--item", "req:2", "--item", "req:1")
    assert code == 0, err
    assert "would supply 2 items to the set requests" in out and "nothing is written without --yes" in out
    assert "new: req:1, req:2" in out
    assert shown(run, items)["n"] == before and "itemSets" not in shown(run, items)
    code, out, err = supply(run, items, "--item", "req:1", "--json")
    body = json.loads(out)
    assert code == 0 and body["dryRun"] is True and body["wouldAdd"] == ["req:1"] and body["set"] == "requests"


def test_supply_with_yes_records_the_items_in_order_and_a_second_supply_adds_only_new_ones(items, run):
    code, out, err = supply(run, items, "--item", "req:1", "--item", "req:2", "--yes")
    assert code == 0, err
    assert "supplied 2 items to the set requests by " + OWNER in out and "note" in out
    body = shown(run, items)
    assert body["itemSets"] == {"requests": ["req:1", "req:2"]} and body["n"] == shown(run, items)["n"]
    step1 = next(s for s in body["steps"] if s["id"] == "i.1")
    assert [i["item"] for i in step1["items"]] == ["req:1", "req:2"]
    code, out, err = supply(run, items, "--item", "req:2", "--item", "req:3")
    assert code == 0 and "would supply 1 item to" in out and "already in the set: req:2" in out and "(1 already there)" in out
    code, out, err = supply(run, items, "--item", "req:2", "--yes")
    assert code == 2 and "those items are already in the set" in err
    code, out, err = supply(run, items, "--item", "req:3", "--yes")
    assert code == 0 and shown(run, items)["itemSets"]["requests"] == ["req:1", "req:2", "req:3"]


def test_supply_refuses_a_name_or_an_address_with_the_engines_own_words_with_or_without_yes(items, run):
    n = shown(run, items)["n"]
    for bad in ("Jane Doe", "jane@example.org", "123 Main St"):
        for extra in ((), ("--yes",)):
            code, out, err = supply(run, items, "--item", bad, *extra)
            assert code == 2 and "is not an item id" in err and "an opaque handle, never a name or an address" in err, (bad, err)
    assert shown(run, items)["n"] == n


def test_supply_needs_a_person_on_the_roster_and_the_role_the_engine_asks(items, run):
    code, out, err = supply(run, items, "--item", "a", "--yes", by=VISITOR)
    assert code == 2 and "is not on the roster" in err and VISITOR in err
    code, out, err = supply(run, items, "--item", "a", "--yes", by="jason")
    assert code == 2 and "is not on the roster" in err
    # on the roster, not the run's owner, holding no role a step over the set needs
    code, out, err = supply(run, items, "--item", "a", "--yes", by=TREASURER)
    assert code == 2 and "holds no role that a step over the set requests needs" in err
    # a role a step needs is enough (the secretary is not the owner either, and holds none of the manager's)
    code, out, err = supply(run, items, "--item", "a", "--yes", by=SECRETARY)
    assert code == 2 and "holds no role" in err
    assert "itemSets" not in shown(run, items)


def test_supply_names_the_roster_when_the_profile_has_none(items, run, monkeypatch):
    monkeypatch.setattr(cli, "_officers", lambda: ())
    code, out, err = supply(run, items, "--item", "a", "--yes")
    assert code == 2 and "is not on the roster" in err and "the profile names no officers" in err


def test_supply_refuses_an_unknown_set_no_items_and_a_closed_run(items, run):
    code, out, err = run("--supply", items, "--set", "nope", "--item", "a", "--by", OWNER, "--yes", *ASOF)
    assert code == 2 and "no step of item-flow repeats over the set nope" in err
    code, out, err = supply(run, items, "--yes")
    assert code == 2 and "no items to supply" in err
    run("--cancel", items, "--reason", "r", "--yes", "--by", OWNER, *ASOF)
    code, out, err = supply(run, items, "--item", "a", "--yes")
    assert code == 2 and "the run is cancelled; items are supplied while it is a draft or going" in err


def test_supply_gives_an_item_its_own_dates_with_a_record_and_the_clock_reads_them(items, run):
    code, out, err = supply(run, items, "--item", "a", "--item-date", "b", "due_on=2099-09-30", "--yes")
    assert code == 2 and "need the record" in err
    code, out, err = supply(run, items, "--item", "a", "--item-date", "b", "due_on=2099-09-30", "--item-date", "b", "nope=2099-09-30",
                            "--record", "mail:1", "--yes")
    assert code == 2 and "no date slot nope" in err
    code, out, err = supply(run, items, "--item", "a", "--item-date", "b", "due_on=2099-09-30", "--record", "mail:1")
    assert code == 0 and "with their own dates: b" in out and "record: mail:1" in out
    code, out, err = supply(run, items, "--item", "a", "--item-date", "b", "due_on=2099-09-30", "--record", "mail:1", "--yes")
    assert code == 0, err
    clocks = {c["key"]: c for c in shown(run, items)["clocks"]}
    assert "i.2[b]" in clocks and clocks["i.2[b]"]["item"] == "b" and clocks["i.2[b]"]["due"] == "2099-10-03"
    code, out, err = run("--show", items, *ASOF)
    assert code == 0 and "i.2[b]" in out and "item a:" in out and "items:" in out


def test_supply_expect_refuses_a_run_that_moved_on(items, run):
    code, out, err = supply(run, items, "--item", "a", "--yes", "--expect", "1")
    assert code == 2 and "changed" in err and "you saw n=1" in err


def test_show_names_a_group_and_the_check_a_remedy_stays_failed_for(run):
    from test_workflows_engine_v3 import GROUPS, group_flow
    from jason.workflows.types import StepGroup

    definitions.register(group_flow(groups=(StepGroup("intake", "Intake"), StepGroup("board", "The board"))))
    code, out, err = run("--start", GROUPS, "--subject", "period:2099-10", "--by", OWNER, "--yes", "--json", *ASOF)
    rid = json.loads(out)["run"]["id"]
    run("--open", rid, "--by", OWNER, "--yes", *ASOF)
    code, out, err = run("--show", rid, *ASOF)
    assert code == 0 and "group intake (Intake): needs a person, 0 of 2 done, expanded" in out
    assert "group board (The board): not started, 0 of 2 done, collapsed" in out
    from jason.commands.workflow import show_lines

    page = {"id": "run-x", "definition": "d", "label": "L", "subject": "s", "owner": "o", "opened": "", "state": "failed", "n": 3,
            "dates": {}, "pausedReason": "", "cancelledReason": "", "current": "r.2", "clocks": [], "pastLaw": [], "links": [],
            "children": [], "orphans": [], "steps": [{"id": "r.1", "state": "failed", "kind": "check", "role": "jason", "title": "T",
                                                      "by": "", "at": "", "record": "", "reason": "", "changed": [], "items": [],
                                                      "remedy": "r.2", "itemCounts": {"done": 2, "ready": 1}}]}
    text = "\n".join(show_lines(page))
    assert "stays recorded as failed; the step r.2 remedies it" in text and "items: 2 done, 1 ready" in text


# --- boundaries -----------------------------------------------------------------------------------------------------

def test_a_lifecycle_writes_only_under_the_workflows_folder(run):
    rid = opened(run)
    run("--attest", rid, C2, "--record", "notice-1", "--by", OWNER)
    run("--note", rid, "--text", "n", "--by", OWNER)
    run("--pause", rid, "--reason", "r", "--by", OWNER)
    run("--resume", rid, "--by", OWNER)
    run("--cancel", rid, "--reason", "r", "--yes", "--by", OWNER)
    run("--reindex")
    top = sorted(p.name for p in run.data.iterdir())
    assert top == ["workflows"]
    names = {p.name for p in (run.data / "workflows").rglob("*") if p.is_file()}
    assert names == {f"{rid}.jsonl", "index.json"}


def test_the_module_names_no_sending_or_filing_client():
    import inspect

    source = inspect.getsource(cli)
    for word in ("payhoa", "smtplib", "googleapiclient", "requests", "mailroom", "lob"):
        assert word not in source.lower().replace("jason.access", ""), word


# --- the person step's guide, what is due, and a claim (docs/workflows/person-steps.md, sections 5.4, 6.3, and 7.4) -------------

HEADINGS = ("Do this", "Look at", "Check before you go on", "The command", "Done when", "If you are blocked", "If it does not apply", "Ask")


def legal_example():
    """example-cycle with a law clock on its person step, so a due date can be LEGAL, and a skip rule it cannot have removed."""
    from dataclasses import replace

    from jason.workflows.types import ClockBasis, ClockDef
    from test_workflows_support import example_cycle

    base = example_cycle()
    c2 = replace(base.step(C2), clock=ClockDef(ClockBasis.LAW, "answers_by", 0, cite="EX 123.4"), legal=True, skip=None)
    wf = example_cycle(steps=tuple(c2 if s.id == C2 else s for s in base.steps))
    definitions.register(wf, plan_kinds={"example-plan"}, jobs={"example-report"})
    return wf


def test_help_lists_the_new_acts(capsys):
    with pytest.raises(SystemExit):
        parser().parse_args(["workflow", "--help"])
    text = capsys.readouterr().out
    for option in ("--guide", "--due", "--for", "--within", "--claim", "--release"):
        assert option in text


def test_guide_prints_the_panels_sections_in_order_with_the_commands_on_their_own_lines(run):
    rid = opened(run)
    code, out, err = run("--guide", f"{rid}:{C2}", "--for", OWNER, *ASOF)
    assert code == 0, err
    assert "Yours: you hold the manager office. Nothing is missing." in out
    at = [out.index(h) for h in HEADINGS if h in out]
    assert at == sorted(at) and out.index("Do this") < out.index("The command")
    assert "\n  1. example notice --send" in out                               # the command as written, on its own line
    assert "Done when you can point to: the sent-notice reference." in out
    assert "Skip is not offered" not in out and "it may be skipped with a reason" in out


def test_guide_of_a_run_alone_is_the_current_person_step_and_names_nobody_without_for(run):
    rid = opened(run)
    code, out, err = run("--guide", rid, *ASOF)
    assert code == 0, err
    assert out.startswith("2. Send the example notice") and "name a person with --for NAME" in out
    assert "Yours:" not in out


def test_guide_of_a_definition_step_needs_no_run(run):
    code, out, err = run("--guide", C2)
    assert code == 0, err
    assert "Do this" in out and "Send the example notice" in out and "Yours:" not in out and "Due " not in out


def test_guide_refuses_a_step_that_is_jasons_and_a_name_it_does_not_know(run):
    rid = opened(run)
    code, out, err = run("--guide", f"{rid}:{C1}", *ASOF)
    assert code == 2 and "is a check step" in err and "has no guide" in err
    code, out, err = run("--guide", f"{rid}:nope.9", *ASOF)
    assert code == 2 and "no step 'nope.9'" in err
    code, out, err = run("--guide", "run-nothere")
    assert code == 2 and "neither a run" in err


def test_guide_json_has_the_three_objects_and_opens_nothing(run):
    rid = opened(run)
    before = json.loads(run("--show", rid, "--json", *ASOF)[1])["n"]
    code, out, err = run("--guide", f"{rid}:{C2}", "--for", OWNER, "--json", *ASOF)
    assert code == 0, err
    got = json.loads(out)
    assert got["step"] == C2 and got["enable"]["state"] == "ready" and got["nudge"]["band"] in ("quiet", "stale") and got["guide"]["instruction"]
    assert json.loads(run("--show", rid, "--json", *ASOF)[1])["n"] == before         # a read, never an open


def test_guide_says_not_yours_to_a_person_who_holds_none_of_the_offices(run):
    rid = opened(run)
    code, out, err = run("--guide", f"{rid}:{C2}", "--for", TREASURER, *ASOF)
    assert code == 0 and "Waiting on the manager." in out and "You are the treasurer." in out


def test_due_needs_a_person_and_says_nothing_is_due_when_nothing_is(run):
    opened(run)
    code, out, err = run("--due", *ASOF)
    assert code == 2 and "--for NAME" in err
    code, out, err = run("--due", "--for", OWNER)                              # today: the run was opened a moment ago
    assert code == 0 and "Nothing is due, late, or open a while." in out


def test_due_lists_a_legal_date_for_its_holder_and_shows_it_to_the_whole_board_the_same_day(run):
    legal_example()
    rid = opened(run)
    for day, word in (("2099-10-23", "LEGAL"), ("2099-10-29", "LEGAL")):
        code, out, err = run("--due", "--for", OWNER, "--as-of", day)
        assert code == 0, err
        assert f"{word} " in out and "Example cycle 2099 · step 2" in out and f"jason workflow --show {rid}" in out
        assert "[LEGAL]" in out and "(EX 123.4)" in out and "1 on a legal clock" in out
        assert "Escalated to you" not in out                                  # the holder's own line is unchanged
    code, out, err = run("--due", "--for", SECRETARY, "--as-of", "2099-10-23")
    assert code == 0 and "Escalated to you (1)" in out and "(the manager)" in out and "nothing was sent to anyone" in out
    code, out, err = run("--due", "--for", SECRETARY, "--as-of", "2099-10-01")                     # not yet: the whole board sees only the day it falls
    assert "Escalated to you" not in out and "Nothing is due" in out
    code, out, err = run("--due", "--for", OWNER, "--as-of", "2099-10-09", "--json")
    rows = json.loads(out)["mine"]
    assert [r["band"] for r in rows] == ["soon"] and rows[0]["basisLabel"] == "LEGAL" and rows[0]["days"] == 14 and rows[0]["numbers"]["note"]
    code, out, err = run("--due", "--for", OWNER, "--as-of", "2099-10-09", "--within", "3")
    assert "Nothing is due" in out


def test_due_reads_and_writes_nothing(run):
    legal_example()
    rid = opened(run)
    before = {p: p.read_bytes() for p in sorted(run.data.rglob("*")) if p.is_file() and "locks" not in p.parts}
    run("--due", "--for", OWNER, "--as-of", "2099-10-23")
    run("--guide", f"{rid}:{C2}", "--for", OWNER, "--as-of", "2099-10-23")
    after = {p: p.read_bytes() for p in sorted(run.data.rglob("*")) if p.is_file() and "locks" not in p.parts}
    assert before == after


def test_claim_without_yes_checks_and_writes_nothing_then_records_a_note_and_the_guide_shows_it(run):
    rid = opened(run)
    n = json.loads(run("--show", rid, "--json", *ASOF)[1])["n"]
    code, out, err = run("--claim", rid, C2, "--by", OWNER, *ASOF)
    assert code == 0, err
    assert f"would record that {OWNER} is on it on {C2}" in out and "nothing is written without --yes" in out
    assert json.loads(run("--show", rid, "--json", *ASOF)[1])["n"] == n
    code, out, err = run("--claim", rid, C2, "--by", OWNER, "--yes", *ASOF)
    assert code == 0, err
    assert "note" in out and C2 in out
    assert json.loads(run("--show", rid, "--json", *ASOF)[1])["n"] == n + 1
    code, out, err = run("--guide", f"{rid}:{C2}", "--for", SECRETARY, *ASOF)
    assert f"{OWNER} is on it since" in out
    code, out, err = run("--claim", rid, C2, "--by", OWNER, "--yes", *ASOF)
    assert code == 2 and "already on" in err
    code, out, err = run("--claim", rid, C2, "--by", OWNER, "--release", "--yes", *ASOF)
    assert code == 0, err
    assert "is on it since" not in run("--guide", f"{rid}:{C2}", "--for", SECRETARY, *ASOF)[1]


def test_claim_is_for_the_roster_and_the_step_s_holders(run):
    rid = opened(run)
    code, out, err = run("--claim", rid, C2, "--by", VISITOR, "--yes", *ASOF)
    assert code == 2 and "not on the roster" in err
    code, out, err = run("--claim", rid, C2, "--by", TREASURER, "--yes", *ASOF)
    assert code == 2 and "does not hold the manager role" in err
    code, out, err = run("--claim", rid, C2, "--yes", *ASOF)
    assert code == 2 and "needs --by" in err
    code, out, err = run("--claim", rid, C1, "--by", OWNER, "--yes", *ASOF)
    assert code == 2 and "a claim is for a step a person does" in err


def test_due_shows_a_held_run_as_its_general_title_and_never_the_matter(run):
    """A held run's line is the definition's general title, the state, the office, the date and its basis word, and nothing else."""
    from dataclasses import replace

    from jason.workflows import api
    from jason.workflows.types import Visibility

    base = legal_example()
    held = replace(base, key="example-held", title="Example hearing", visibility=Visibility.HELD, held_title="A member's matter")
    definitions.register(held, plan_kinds={"example-plan"}, jobs={"example-report"})
    rid = api.start(run.data, "example-held", "unit:123 Main St", "Hearing for 123 Main St", DATES, OWNER, yes=True)["run"]["id"]
    api.open_run(run.data, rid, OWNER, yes=True, roles_of=lambda by: ("manager",))
    code, out, err = run("--due", "--for", OWNER, "--as-of", "2099-10-23")
    assert code == 0, err
    assert "A member's matter: a step is due" in out and "[LEGAL]" in out
    for leak in ("123 Main St", "Send the example notice", "EX 123.4", "answers_by", "Hearing for"):
        assert leak not in out, leak
    code, out, err = run("--due", "--for", OWNER, "--as-of", "2099-10-23", "--json")
    row = next(r for r in json.loads(out)["mine"] if r["held"])
    assert row["title"] == "a step" and row["runLabel"] == "A member's matter" and row["cite"] == "" and row["label"] == "" and row["claim"] is None
