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
