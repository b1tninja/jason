"""The ``control-adoption`` workflow (src/jason/workflows/definitions_general.py; docs/controls.md, section 4): the definition,
its reads, and one run per control from jason's suggestion to the day it binds, in a temporary data folder over made-up
controls. The people, the decisions, and the dates are made up ("A. Member", "S. Secretary", 2099). No real store, no network,
and no profile: the community is a stub with a roster.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date

import pytest

from controls_support import FULL, make, roster
from jason.community.base import OfficerRole as R
from jason.controls import propose, store
from jason.controls.types import Basis, ControlAct, ControlState
from jason.tasks import board_items, decisions
from jason.workflows import api, definitions, store as runs
from jason.workflows import definitions_general as general
from jason.workflows.readers import CHECKS, JOBS, StoreReaders
from jason.workflows.types import ClockBasis, EventKind as K, Role, StepKind, StepRefused
from test_workflows_support import data  # noqa: F401 - the `data` fixture

MEMBER, SECRETARY, MANAGER, VISITOR = "A. Member", "S. Secretary", "J. Manager", "V. Visitor"
P = {MEMBER: {"director"}, SECRETARY: {"secretary", "director"}, MANAGER: {"manager"}, VISITOR: ()}
KEY = "pay-two"
MEETING = "2099-10-20"
DECISION = f"{MEETING}--control-{KEY}"
EFFECTIVE = "2099-11-14"
BEFORE, ON = date(2099, 11, 1), date(2099, 11, 14)


def roles_of(by):
    return P.get(by, ())


def n(step: str) -> str:
    return general.cid(step)


class Home:
    """The stub community: the controls it keeps (none) and a roster."""

    def __init__(self, seated=FULL):
        self._seated = tuple(seated)

    def controls(self):
        return ()

    def officers(self):
        return self._seated


@pytest.fixture(autouse=True)
def fresh():
    definitions.reset()
    yield
    definitions.reset()


@pytest.fixture
def wf():
    return general.control_adoption()


# --- the definition -----------------------------------------------------------------------------------------------------

def test_it_has_the_eight_steps_in_the_order_the_design_gives(wf):
    assert wf.key == "control-adoption" and wf.subject == "control" and wf.family == "board"
    kinds = {s.id: s.kind for s in wf.steps}
    P_, C, D, W, B = StepKind.PERSON, StepKind.CHECK, StepKind.DECISION, StepKind.WAIT, StepKind.BRANCH
    assert kinds == {n("1"): C, n("2"): P_, n("3"): D, n("4"): B, n("5"): P_, n("6"): C, n("7"): W, n("8"): W}
    assert [s.id for s in wf.steps] == [n(str(i)) for i in range(1, 9)]
    needs = {s.id: s.needs for s in wf.steps}
    assert needs == {n("1"): (), n("2"): (n("1"),), n("3"): (n("2"),), n("4"): (n("3"),), n("5"): (n("4"),),
                     n("6"): (n("5"),), n("7"): (n("6"),), n("8"): (n("7"),)}


def test_the_roles_are_the_designs_and_the_board_decides_while_the_secretary_records(wf):
    roles = {s.id: s.role for s in wf.steps}
    assert roles[n("2")] is Role.ANYONE                      # any board member may put it before the board
    assert roles[n("3")] is Role.SECRETARY and roles[n("5")] is Role.SECRETARY
    assert roles[n("1")] is roles[n("4")] is roles[n("6")] is roles[n("7")] is Role.JASON
    assert [s.id for s in wf.steps if s.kind is StepKind.DECISION] == [n("3")]


def test_the_effective_date_is_the_boards_a_person_basis_and_no_statute_is_cited(wf):
    assert wf.dates == () and wf.clocks == () and wf.procedure == "" and not wf.has_legal_clock()
    assert all(s.sop == "" for s in wf.steps)
    for s in wf.steps:
        if s.clock is not None:
            assert s.clock.basis is ClockBasis.PERSON and not s.clock.cite, s.id
    assert wf.step(n("5")).clock is not None and wf.step(n("7")).clock is not None
    assert all(s.skip is None for s in wf.steps if s.id != n("6"))


def test_a_declined_control_ends_the_run_at_the_outcome_branch(wf):
    outcome = wf.step(n("4"))
    paths = {c.key: c.steps for c in outcome.choices}
    assert paths == {"adopted": (n("5"), n("6"), n("7"), n("8")), "declined": ()}


def test_every_step_says_why_and_every_read_it_names_is_registered(wf):
    assert all(s.why for s in wf.steps)
    names = {s.check.name for s in wf.steps if s.check is not None}
    assert names == {"control-suggested", "control-outcome", "control-roster", "control-in-force", "control-retired"}
    assert names <= set(CHECKS)
    assert not {s.job for s in wf.steps if s.job}          # it queues no job, so JOBS gains none
    assert {"control-suggested"} .isdisjoint(JOBS)


def test_it_validates_and_names_no_association_or_amount(wf):
    assert definitions.validate(wf, jobs=set(JOBS)) == []
    text = repr(wf).lower()
    for word in ("mystique", "123 main", "payhoa", "$"):
        assert word not in text


def test_it_is_registered_when_asked_and_not_at_import():
    assert definitions.find("control-adoption") is None
    assert "control-adoption" in [w.key for w in general.register_general()]
    assert definitions.find("control-adoption") is not None
    code = (
        "import sys, json\n"
        "from jason.workflows import definitions_general as g, definitions\n"
        "assert definitions.find('control-adoption') is None\n"
        "g.register_general()\n"
        "print(json.dumps({'profile': sorted(m for m in sys.modules if 'mystique' in m), "
        "'found': definitions.find('control-adoption') is not None}))\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout.strip().splitlines()[-1]) == {"profile": [], "found": True}


def test_workflow_definitions_lists_it(data, capsys, monkeypatch):
    from jason.cli import build_parser

    data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("jason.commands._shared.data_dir", lambda args=None: data)
    args = build_parser().parse_args(["workflow", "--definitions", "--family", "board", "--json"])
    assert args.func(args) == 0
    assert "control-adoption" in capsys.readouterr().out


# --- one run over a made-up control -------------------------------------------------------------------------------------

def readers_for(data, day, seated=FULL):
    return StoreReaders(data, community=Home(seated), today=day)


def start(data, key=KEY):
    general.register_general()
    out = api.start(data, "control-adoption", f"control:{key}", "Payment signers", {}, MEMBER, yes=True, today=BEFORE)
    return out["run"]["id"]


def open_run(data, rid, day, seated=FULL):
    return api.open_run(data, rid, MEMBER, readers=readers_for(data, day, seated), roles_of=roles_of, today=day)


def state(data, rid, step, day):
    return next(s for s in api.show(data, rid, today=day)["steps"] if s["id"] == n(step))


def attest(data, rid, step, by, day, seated=FULL, **more):
    return api.attest(data, rid, n(step), by, roles_of=roles_of, readers=readers_for(data, day, seated), today=day, **more)


def suggest(data, key=KEY, params=None):
    control = make(params=params or {"signers": 2}, key=key, basis=Basis("Bylaws 1.1", "Checks shall be signed by two directors."),
                   reading="jason's reading")
    return store.record(ControlAct.SUGGEST, key, by="jason", why="found in the bylaws", control=control, data_dir=data)


def put_before_board(data, key=KEY):
    return propose.propose(key, by=MEMBER, data_dir=data)


def board_decides(data, outcome, key=KEY):
    return decisions.record(data, MEETING, "Payment signers", "Adopt the payment signers control", item=f"control-{key}",
                            outcome=outcome, by=SECRETARY)


def test_one_control_from_suggested_to_in_force_and_then_retired(data):
    rid = start(data)
    assert api.show(data, rid, today=BEFORE)["state"] == "draft"

    # 1: no control in the record yet, so the check fails and says what is missing
    open_run(data, rid, BEFORE)
    assert state(data, rid, "1", BEFORE)["state"] == "failed" and "no control pay-two" in state(data, rid, "1", BEFORE)["reason"]
    suggest(data)
    open_run(data, rid, BEFORE)
    assert state(data, rid, "1", BEFORE)["state"] == "done"
    assert state(data, rid, "2", BEFORE)["state"] == "needs a person"

    # 2: any board member puts it before the board: the board item exists and the control is proposed
    with pytest.raises(StepRefused, match="record"):
        attest(data, rid, "2", MEMBER, BEFORE)                       # the board item id is the record
    assert not (data / "board" / "items.json").exists()               # the run made no board item
    put_before_board(data)
    assert store.get(KEY, data).state is ControlState.PROPOSED
    assert any(i.id == f"control-{KEY}" for i in board_items.load(data))
    attest(data, rid, "2", MEMBER, BEFORE, record=f"control-{KEY}")
    assert state(data, rid, "2", BEFORE)["state"] == "done"

    # 3: the board decides; the secretary records it, and only the secretary
    open_run(data, rid, BEFORE)
    with pytest.raises(StepRefused, match="secretary"):
        attest(data, rid, "3", MEMBER, BEFORE, outcome="approved", record=DECISION)
    board_decides(data, "approved")
    attest(data, rid, "3", SECRETARY, BEFORE, outcome="approved", record=DECISION)
    assert state(data, rid, "3", BEFORE)["state"] == "done"

    # 4: the decision is recorded, but the control's act log does not show it yet
    open_run(data, rid, BEFORE)
    s4 = state(data, rid, "4", BEFORE)
    assert s4["state"] == "failed" and "still proposed" in s4["reason"]
    assert api.show(data, rid, today=BEFORE)["state"] == "failed"
    store.record(ControlAct.ADOPT, KEY, by=SECRETARY, why="the board voted", decision=DECISION, effective=EFFECTIVE, data_dir=data)
    open_run(data, rid, BEFORE)
    s4 = state(data, rid, "4", BEFORE)
    assert s4["state"] == "done" and s4["choice"] == "adopted"
    check = [e for e in runs.open_run(data, rid).events if e.kind is K.CHECK_RAN and e.step == n("4") and e.detail["ok"]]
    assert check and DECISION in check[-1].detail["message"] and EFFECTIVE in check[-1].detail["message"]

    # 5: the secretary confirms the date the board named; nobody else
    with pytest.raises(StepRefused, match="secretary"):
        attest(data, rid, "5", MEMBER, BEFORE, record=EFFECTIVE)
    attest(data, rid, "5", SECRETARY, BEFORE, record=EFFECTIVE)

    # 6 and 7: the roster can satisfy it; the date has not come, so the control waits and binds nothing
    open_run(data, rid, BEFORE)
    assert state(data, rid, "6", BEFORE)["state"] == "done"
    assert state(data, rid, "7", BEFORE)["state"] == "waiting" and state(data, rid, "8", BEFORE)["state"] == "not started"
    assert api.show(data, rid, today=BEFORE)["state"] == "waiting"
    with pytest.raises(StepRefused, match="jason"):
        api.arrived(data, rid, n("7"), SECRETARY, roles_of=roles_of, readers=readers_for(data, BEFORE), today=BEFORE)   # no person turns it on
    assert open_run(data, rid, BEFORE)["appended"] == []             # a second open changes nothing

    # the date comes: the check passes and the control is in force; jason turned nothing on
    res = open_run(data, rid, ON)
    arrived = [e for e in res["appended"] if e["kind"] == "arrived" and e["step"] == n("7")]
    assert len(arrived) == 1 and arrived[0]["by"] == "jason" and "jason turned nothing on" in arrived[0]["detail"]["what"]
    assert state(data, rid, "7", ON)["state"] == "done" and state(data, rid, "8", ON)["state"] == "waiting"

    # 8: the yearly review is the secretary's; the board retiring the control also ends it
    store.record(ControlAct.RETIRE, KEY, by=SECRETARY, why="superseded", data_dir=data)
    open_run(data, rid, ON)
    final = api.show(data, rid, today=ON)
    assert final["state"] == "done" and all(s["state"] == "done" for s in final["steps"]), [
        (s["id"], s["state"], s["reason"]) for s in final["steps"]]
    assert api.verify(data, rid)["ok"]


def test_the_secretary_notes_the_first_yearly_review_and_the_run_closes(data):
    rid = start(data)
    suggest(data)
    put_before_board(data)
    board_decides(data, "approved")
    store.record(ControlAct.ADOPT, KEY, by=SECRETARY, why="the board voted", decision=DECISION, effective=EFFECTIVE, data_dir=data)
    open_run(data, rid, ON)
    attest(data, rid, "2", MEMBER, ON, record=f"control-{KEY}")
    attest(data, rid, "3", SECRETARY, ON, outcome="approved", record=DECISION)
    open_run(data, rid, ON)
    attest(data, rid, "5", SECRETARY, ON, record=EFFECTIVE)
    open_run(data, rid, ON)
    assert state(data, rid, "7", ON)["state"] == "done" and state(data, rid, "8", ON)["state"] == "waiting"
    api.arrived(data, rid, n("8"), SECRETARY, roles_of=roles_of, what="the yearly review, held", readers=readers_for(data, ON), today=ON)
    assert api.show(data, rid, today=ON)["state"] == "done"


# --- a declined control closes the run -----------------------------------------------------------------------------------

def test_a_declined_control_closes_the_run_and_skips_the_steps_after_it(data):
    rid = start(data)
    suggest(data)
    put_before_board(data)
    open_run(data, rid, BEFORE)
    attest(data, rid, "2", MEMBER, BEFORE, record=f"control-{KEY}")
    board_decides(data, "denied")
    attest(data, rid, "3", SECRETARY, BEFORE, outcome="denied", record=DECISION)
    store.record(ControlAct.DECLINE, KEY, by=SECRETARY, why="the board voted no", decision=DECISION, again_on="2100-01-01", data_dir=data)
    open_run(data, rid, BEFORE)
    s4 = state(data, rid, "4", BEFORE)
    assert s4["state"] == "done" and s4["choice"] == "declined"
    for step in ("5", "6", "7", "8"):
        assert state(data, rid, step, BEFORE)["state"] == "skipped", step
        assert "declined" in state(data, rid, step, BEFORE)["reason"]
    final = api.show(data, rid, today=BEFORE)
    assert final["state"] == "done" and final["current"] == ""
    assert store.get(KEY, data).state is ControlState.DECLINED          # and the run turned nothing on


def test_a_tabled_decision_leaves_the_step_open_and_a_deferred_control_decides_nothing(data):
    rid = start(data)
    suggest(data)
    put_before_board(data)
    open_run(data, rid, BEFORE)
    attest(data, rid, "2", MEMBER, BEFORE, record=f"control-{KEY}")
    board_decides(data, "tabled")
    attest(data, rid, "3", SECRETARY, BEFORE, outcome="tabled", record=DECISION)
    s3 = state(data, rid, "3", BEFORE)
    assert s3["state"] == "needs a person" and "tabled" in s3["reason"]        # recorded, not final
    store.record(ControlAct.DEFER, KEY, by=SECRETARY, why="the board tabled it", decision=DECISION, again_on="2100-01-01", data_dir=data)
    open_run(data, rid, BEFORE)
    assert state(data, rid, "4", BEFORE)["state"] == "not started"


def test_the_outcome_check_refuses_a_decision_that_is_missing_or_says_otherwise(data):
    rid = start(data)
    suggest(data)
    put_before_board(data)
    open_run(data, rid, BEFORE)
    attest(data, rid, "2", MEMBER, BEFORE, record=f"control-{KEY}")
    board_decides(data, "approved")
    attest(data, rid, "3", SECRETARY, BEFORE, outcome="approved", record=DECISION)
    store.record(ControlAct.ADOPT, KEY, by=SECRETARY, why="the board voted", decision="2099-01-01--nothing", effective=EFFECTIVE, data_dir=data)
    open_run(data, rid, BEFORE)
    assert "not in the decisions store" in state(data, rid, "4", BEFORE)["reason"]
    decisions.record(data, "2099-01-01", "Other", "A motion", item="nothing", outcome="denied", by=SECRETARY)
    open_run(data, rid, BEFORE)
    assert "recorded as denied" in state(data, rid, "4", BEFORE)["reason"]
    assert state(data, rid, "4", BEFORE)["state"] == "failed"
    decisions.update(data, "2099-01-01--nothing", outcome="approved")
    open_run(data, rid, BEFORE)
    assert state(data, rid, "4", BEFORE)["state"] == "done"


# --- the roster check warns and blocks nothing ---------------------------------------------------------------------------

def test_a_roster_that_lacks_a_signer_warns_and_does_not_block(data):
    thin = roster(R.PRESIDENT)                                        # one board member seated; the control asks for two signers
    rid = start(data)
    suggest(data)
    put_before_board(data)
    board_decides(data, "approved")
    store.record(ControlAct.ADOPT, KEY, by=SECRETARY, why="the board voted", decision=DECISION, effective=EFFECTIVE, data_dir=data)
    open_run(data, rid, BEFORE, thin)
    attest(data, rid, "2", MEMBER, BEFORE, thin, record=f"control-{KEY}")
    attest(data, rid, "3", SECRETARY, BEFORE, thin, outcome="approved", record=DECISION)
    open_run(data, rid, BEFORE, thin)
    attest(data, rid, "5", SECRETARY, BEFORE, thin, record=EFFECTIVE)
    open_run(data, rid, BEFORE, thin)
    s6 = state(data, rid, "6", BEFORE)
    assert s6["state"] == "done"                                      # a warning, not a failure
    warned = [e for e in runs.open_run(data, rid).events if e.kind is K.CHECK_RAN and e.step == n("6")]
    assert warned[-1].detail["ok"] is True and warned[-1].detail["message"].startswith("Warning: the roster lacks")
    assert "blocks nothing" in warned[-1].detail["message"]
    assert state(data, rid, "7", BEFORE)["state"] == "waiting"
    assert api.show(data, rid, today=BEFORE)["state"] == "waiting"    # the run goes on to wait for the date
    # on the date the control binds, and the run says the roster cannot satisfy it (the acts it governs are refused)
    open_run(data, rid, ON, thin)
    assert state(data, rid, "7", ON)["state"] == "done"
    came = [e for e in runs.open_run(data, rid).events if e.kind is K.ARRIVED and e.step == n("7")]
    assert "cannot satisfy it" in came[0].detail["what"]


def test_a_roster_that_cannot_be_read_skips_the_roster_check_and_says_so(data):
    class Unread(Home):
        def officers(self):
            raise OSError("the roster is not readable")

    rid = start(data)
    suggest(data)
    put_before_board(data)
    board_decides(data, "approved")
    store.record(ControlAct.ADOPT, KEY, by=SECRETARY, why="the board voted", decision=DECISION, effective=EFFECTIVE, data_dir=data)
    open_run(data, rid, BEFORE)
    attest(data, rid, "2", MEMBER, BEFORE, record=f"control-{KEY}")
    attest(data, rid, "3", SECRETARY, BEFORE, outcome="approved", record=DECISION)
    readers = StoreReaders(data, community=Unread(), today=BEFORE)
    api.open_run(data, rid, MEMBER, readers=readers, roles_of=roles_of, today=BEFORE)
    api.attest(data, rid, n("5"), SECRETARY, roles_of=roles_of, readers=readers, today=BEFORE, record=EFFECTIVE)
    api.open_run(data, rid, MEMBER, readers=readers, roles_of=roles_of, today=BEFORE)
    s6 = [e for e in runs.open_run(data, rid).events if e.kind is K.CHECK_RAN and e.step == n("6")]
    assert s6[-1].detail["ok"] is True and "could not be read" in s6[-1].detail["message"]


# --- what the reads leave alone ----------------------------------------------------------------------------------------

def test_the_reads_write_nothing_and_a_run_about_something_else_is_refused(data):
    suggest(data)
    before = {p.relative_to(data).as_posix(): p.read_bytes() for p in sorted(data.rglob("*")) if p.is_file()}
    readers = readers_for(data, ON)
    view = type("V", (), {"subject": f"control:{KEY}", "steps": (), "dates": {}})()
    for name in CHECKS:
        if name.startswith("control-"):
            CHECKS[name](readers, view, "")
    assert {p.relative_to(data).as_posix(): p.read_bytes() for p in sorted(data.rglob("*")) if p.is_file()} == before
    other = type("V", (), {"subject": "campaign:X", "steps": (), "dates": {}})()
    res = CHECKS["control-suggested"](readers, other, "")
    assert not res.ok and "not a control" in res.message
    assert not CHECKS["control-suggested"](readers, type("V", (), {"subject": "control:nope", "steps": (), "dates": {}})(), "").ok
