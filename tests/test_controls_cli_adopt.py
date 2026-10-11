"""``jason controls --adopt / --decline / --defer``: the secretary records what the board decided at a meeting. Driven through
the argument parser in a temporary data folder, over a stub community and made-up names (everyone is "Person N office"),
and 2099 dates. It records a decision a person states; it decides nothing, lowers no floor, and writes nothing without
``--yes``."""

from __future__ import annotations

import pytest

from controls_support import make, roster
from controls_world import Home
from jason.community.base import OfficerRole as R
from jason.controls import store
from jason.controls.types import Basis, ControlAct, ControlState

MEETING = "2099-03-01"
EFFECTIVE = "2099-04-01"
SECRETARY = "Person 1 secretary"           # the second row of controls_support.FULL
DIRECTOR = "Person 3 director"
STRANGER = "Nobody Onroster"

_PARSER = []


def parser():
    if not _PARSER:
        from jason.cli import build_parser

        _PARSER.append(build_parser())
    return _PARSER[0]


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    monkeypatch.setattr("jason.commands._shared.data_dir", lambda args=None: tmp_path)
    home = Home()
    monkeypatch.setattr("jason.community.community", lambda: home)
    home.root = tmp_path
    return home


@pytest.fixture
def run(world, capsys):
    def go(*argv):
        args = parser().parse_args(["controls", *argv])
        code = args.func(args)
        out = capsys.readouterr()
        return code, out.out, out.err

    go.world = world
    return go


def proposed(root, key="payment-signers", type_key="payment-signers", floor=None):
    """A control the board has been asked about: suggested by jason, then put before the board."""
    control = make(type_key, key=key, basis=Basis("Example Bylaws 9.1", "All checks shall be signed by two directors.",
                                                  floor or {}))
    store.record(ControlAct.SUGGEST, key, by="jason", why="read the provision", control=control, data_dir=root)
    store.record(ControlAct.PROPOSE, key, by="A Person", why="put before the board", data_dir=root)


def decide(run, act, *more, key="payment-signers", by=SECRETARY, meeting=MEETING, decision=f"{MEETING}--payment-signers",
           reason="", effective=EFFECTIVE, yes=True):
    argv = [f"--{act}", key, "--by", by, "--meeting", meeting]
    if decision:
        argv += ["--decision", decision]
    if reason:
        argv += ["--reason", reason]
    if act == "adopt" and effective:
        argv += ["--effective", effective]
    if yes:
        argv.append("--yes")
    return run(*argv, *more)


def log(root):
    return store.acts(root)


def record_decision(root, outcome="approved", meeting=MEETING):
    from jason.tasks import decisions

    return decisions.record(root, meeting, "Payment signers", "Adopt the payment signers control.", outcome=outcome)


# --- the flags ------------------------------------------------------------------------------------------------------------------

def test_the_flags_are_registered_and_the_help_says_it_decides_nothing():
    sub = next(a for a in parser()._actions if a.__class__.__name__ == "_SubParsersAction")
    text = " ".join(sub.choices["controls"].format_help().split())
    for flag in ("--adopt", "--decline", "--defer", "--effective", "--meeting", "--decision", "--reason", "--yes"):
        assert flag in text, flag
    assert "it decides nothing" in text and "--retire" not in text


# --- a dry run writes nothing ---------------------------------------------------------------------------------------------------

def test_without_yes_it_prints_what_would_be_recorded_and_writes_nothing(run):
    proposed(run.world.root)
    before = log(run.world.root)
    code, out, err = decide(run, "adopt", yes=False)
    assert code == 0, err
    assert "Would record" in out and "to adopt payment-signers" in out and "Nothing recorded" in out
    assert f"takes effect: {EFFECTIVE}" in out and "proposed to adopted" in out
    assert SECRETARY in out and "it decides nothing" in out
    assert log(run.world.root) == before
    assert store.get("payment-signers", run.world.root).state is ControlState.PROPOSED


def test_a_dry_run_refuses_what_the_real_run_would_refuse(run):
    proposed(run.world.root)
    code, _, err = decide(run, "adopt", by=STRANGER, yes=False)
    assert code == 2 and "not on the roster" in err
    code, _, err = run("--adopt", "payment-signers", "--by", SECRETARY, "--meeting", MEETING, "--decision", "d",
                       "--effective", EFFECTIVE, "--param", "signers=0")
    assert code == 2 and "too low" in err


# --- adopt, decline, defer are logged -------------------------------------------------------------------------------------------

def test_adopt_appends_one_act_and_the_control_takes_the_board_s_values(run):
    root = run.world.root
    proposed(root)
    made = record_decision(root)
    n = len(log(root))
    code, out, err = decide(run, "adopt", "--param", "signers=2", "--param", "must_include=treasurer",
                            "--param", "roles=treasurer,director,president", reason="Voted 3 to 0.", decision=made.id)
    assert code == 0, err
    assert "Recording" in out and "in Decisions, recorded as approved" in out and "Recorded: payment-signers is adopted" in out
    rows = log(root)
    assert len(rows) == n + 1
    row = rows[-1]
    assert (row["act"], row["by"], row["decision"], row["effective"]) == ("adopt", SECRETARY, made.id, EFFECTIVE)
    assert MEETING in row["why"] and "Voted 3 to 0." in row["why"]
    assert row["parameters"]["signers"] == 2 and row["parameters"]["must_include"] == ["treasurer"]
    control = store.get("payment-signers", root)
    assert control.state is ControlState.ADOPTED and control.effective.isoformat() == EFFECTIVE
    assert control.decision == made.id and control.value("signers") == 2
    assert store.verify(root)[0]


def test_adopt_with_no_values_keeps_the_control_as_proposed_at_its_floor(run):
    proposed(run.world.root, floor={"signers": 2})
    code, out, err = decide(run, "adopt")
    assert code == 0, err
    assert store.get("payment-signers", run.world.root).value("signers") == 2


def test_decline_is_logged_with_the_reason_and_the_decision(run):
    root = run.world.root
    proposed(root)
    code, out, err = decide(run, "decline", reason="Not now.", decision=f"{MEETING}--declined-item")
    assert code == 0, err
    row = log(root)[-1]
    assert (row["act"], row["by"], row["decision"]) == ("decline", SECRETARY, f"{MEETING}--declined-item")
    assert "Not now." in row["why"] and "effective" not in row
    control = store.get("payment-signers", root)
    assert control.state is ControlState.DECLINED and control.effective is None


def test_defer_is_logged_with_the_date_to_look_again(run):
    root = run.world.root
    proposed(root)
    code, out, err = run("--defer", "payment-signers", "--by", SECRETARY, "--meeting", MEETING,
                         "--reason", "Wait for the budget.", "--again-on", "2099-09-01", "--yes")
    assert code == 0, err
    row = log(root)[-1]
    assert (row["act"], row["againOn"]) == ("defer", "2099-09-01") and "decision" not in row
    assert store.get("payment-signers", root).state is ControlState.DEFERRED
    assert "may be asked again on: 2099-09-01" in out


# --- only adds ------------------------------------------------------------------------------------------------------------------

def test_an_adoption_below_a_floor_is_refused_and_nothing_is_written(run):
    root = run.world.root
    proposed(root, floor={"signers": 2})
    before = log(root)
    for yes in (False, True):
        code, _, err = decide(run, "adopt", "--param", "signers=1", yes=yes)
        assert code == 2 and "below" in err and "only adds" in err
    assert log(root) == before
    assert store.get("payment-signers", root).state is ControlState.PROPOSED


def test_an_unknown_value_or_a_bad_one_is_refused(run):
    proposed(run.world.root)
    code, _, err = decide(run, "adopt", "--param", "colour=red")
    assert code == 2 and "no parameter colour" in err
    code, _, err = decide(run, "adopt", "--param", "signers=many")
    assert code == 2 and "whole number" in err
    code, _, err = decide(run, "adopt", "--param", "roles=janitor")
    assert code == 2 and "not an office" in err
    code, _, err = decide(run, "adopt", "--param", "signers")
    assert code == 2 and "NAME=VALUE" in err
    assert [r["act"] for r in log(run.world.root)] == ["suggest", "propose"]


# --- the secretary records ------------------------------------------------------------------------------------------------------

def test_someone_not_on_the_roster_is_refused(run):
    proposed(run.world.root)
    code, _, err = decide(run, "adopt", by=STRANGER)
    assert code == 2 and "is not on the roster" in err
    assert len(log(run.world.root)) == 2


def test_someone_on_the_roster_who_is_not_the_secretary_is_refused(run):
    proposed(run.world.root)
    code, _, err = decide(run, "decline", by=DIRECTOR, reason="No.")
    assert code == 2 and "does not hold the secretary's office" in err
    assert len(log(run.world.root)) == 2


def test_the_name_is_matched_without_regard_to_case_and_spacing(run):
    proposed(run.world.root)
    code, _, err = decide(run, "adopt", by=f"  {SECRETARY.upper()} ")
    assert code == 0, err


def test_an_unreadable_roster_refuses(run):
    proposed(run.world.root)
    run.world._roster = ()
    code, _, err = decide(run, "adopt")
    assert code == 2 and "roster could not be read" in err


def test_a_person_who_holds_two_offices_may_record_as_secretary(run):
    from jason.community.base import Officer

    proposed(run.world.root)
    run.world._roster = (*roster(R.PRESIDENT), Officer(R.SECRETARY, "Person 0 president"))
    code, _, err = decide(run, "adopt", by="Person 0 president")
    assert code == 0, err


# --- what a decision has to say -------------------------------------------------------------------------------------------------

def test_a_decision_states_its_meeting_and_an_adoption_its_date_and_decision(run):
    proposed(run.world.root)
    code, _, err = run("--adopt", "payment-signers", "--by", SECRETARY, "--decision", "d", "--effective", EFFECTIVE)
    assert code == 2 and "--meeting" in err
    code, _, err = decide(run, "adopt", meeting="March first")
    assert code == 2 and "YYYY-MM-DD" in err
    code, _, err = decide(run, "adopt", effective="")
    assert code == 2 and "--effective" in err
    code, _, err = decide(run, "adopt", effective="soon")
    assert code == 2 and "--effective" in err
    code, _, err = decide(run, "adopt", decision="")
    assert code == 2 and "--decision" in err
    code, _, err = decide(run, "decline", decision="", reason="No.")
    assert code == 2 and "--decision" in err
    code, _, err = decide(run, "decline")
    assert code == 2 and "--reason" in err
    code, _, err = run("--defer", "payment-signers", "--by", SECRETARY, "--meeting", MEETING)
    assert code == 2 and "--reason" in err
    assert len(log(run.world.root)) == 2


def test_an_effective_date_or_values_go_only_with_adopt(run):
    proposed(run.world.root)
    code, _, err = run("--decline", "payment-signers", "--by", SECRETARY, "--meeting", MEETING, "--decision", "d",
                       "--reason", "No.", "--effective", EFFECTIVE)
    assert code == 2 and "go with --adopt" in err
    code, _, err = decide(run, "adopt", "--again-on", "2099-09-01")
    assert code == 2 and "--again-on" in err
    code, _, err = run("--show", "payment-signers", "--meeting", MEETING)
    assert code == 2 and "goes with --adopt" in err


def test_a_recorded_decision_that_contradicts_the_act_is_refused(run):
    root = run.world.root
    proposed(root)
    made = record_decision(root, outcome="denied")
    code, _, err = decide(run, "adopt", decision=made.id)
    assert code == 2 and "recorded as denied" in err
    code, _, err = decide(run, "decline", reason="No.", decision=made.id)
    assert code == 0, err                                                # a denied motion is the board declining


def test_a_decision_recorded_for_another_meeting_is_refused(run):
    root = run.world.root
    proposed(root)
    made = record_decision(root, meeting="2099-02-01")
    code, _, err = decide(run, "adopt", decision=made.id)
    assert code == 2 and "2099-02-01" in err and MEETING in err
    assert len(log(root)) == 2


def test_a_decision_not_in_decisions_yet_is_said_and_still_recorded(run):
    root = run.world.root
    proposed(root)
    code, out, err = decide(run, "adopt")
    assert code == 0, err
    assert "not in Decisions yet" in out
    assert log(root)[-1]["decision"] == f"{MEETING}--payment-signers"


# --- the moves the record allows --------------------------------------------------------------------------------------------------

def test_only_a_proposed_control_may_be_decided(run):
    root = run.world.root
    control = make(key="reserve-signers", type_key="reserve-signers")
    store.record(ControlAct.SUGGEST, "reserve-signers", by="jason", why="read it", control=control, data_dir=root)
    code, _, err = decide(run, "adopt", key="reserve-signers")
    assert code == 2 and "suggested cannot adopt" in err
    proposed(root)
    assert decide(run, "adopt")[0] == 0
    code, _, err = decide(run, "decline", reason="Changed our minds.")
    assert code == 2 and "adopted cannot decline" in err
    assert [r["act"] for r in log(root)][-1] == "adopt"


def test_no_such_control_is_said(run):
    code, _, err = decide(run, "adopt", key="nope")
    assert code == 2 and "no control nope" in err


def test_one_act_at_a_time_and_a_declined_control_may_not_be_asked_again_without_a_date(run):
    proposed(run.world.root)
    code, _, err = run("--adopt", "payment-signers", "--decline", "payment-signers")
    assert code == 2 and "one act at a time" in err
    assert decide(run, "decline", reason="No.")[0] == 0
    from jason.controls.propose import propose

    with pytest.raises(ValueError, match="no date to ask again"):
        propose("payment-signers", by="A Person", data_dir=run.world.root)


def test_the_list_and_show_see_the_adoption(run):
    import json

    root = run.world.root
    proposed(root)
    assert decide(run, "adopt")[0] == 0
    code, out, _ = run("--show", "payment-signers")
    assert code == 0 and "3 WHAT THE BOARD DECIDED" in out and f"effective {EFFECTIVE}" in out
    body = json.loads(run("--list", "--json")[1])
    row = next(r for r in body["controls"] if r["key"] == "payment-signers")
    assert row["state"] == "adopted"
