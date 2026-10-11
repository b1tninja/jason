"""The owner-information cycle as a workflow (src/jason/workflows/definitions_general.py), against the family page's table
(docs/workflows/members-cycles.md, 2.1): the definition, its checks, its drift from the procedure, and one run from start to
done in a temporary data folder over made-up stores, with a plan that follows a real approval record. Everything is made up
("A. Admin", "123 Main St", 2099); no real store, no network, no profile.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import date, timedelta

import pytest

from jason import jobs
from jason.approvals import model, registry
from jason.community.response_inbox import State
from jason.tasks import notice_ledger
from jason.tasks import response_inbox as inbox
from jason.workflows import api, definitions, store
from jason.workflows import definitions_general as general
from jason.workflows.readers import JOBS, StoreReaders
from jason.workflows.types import ClockBasis, EventKind as K, InvalidWorkflow, Role, StepKind, StepState, parse_sop
from test_workflows_readers import (
    BEGAN, DATES, Community, arrival, make_approval, request, seed_campaign, seed_inbox, tree,
)
from test_workflows_support import data  # noqa: F401 - the `data` fixture

P = {"A. Admin": {"administrator"}, "J. Manager": {"manager"}, "S. Secretary": {"secretary", "director"}}
ADMIN, MANAGER, SECRETARY = "A. Admin", "J. Manager", "S. Secretary"


def roles_of(by):
    return P.get(by, ())


def n(step: str) -> str:
    return general.sid(step)


@pytest.fixture(autouse=True)
def fresh():
    definitions.reset()
    yield
    definitions.reset()


@pytest.fixture
def wf():
    return general.owner_info_cycle()


# --- the definition ---------------------------------------------------------------------------------------------------

def test_it_has_the_tables_25_steps_and_the_two_the_response_intake_group_adds(wf):
    ids = [s.id for s in wf.steps]
    assert len(ids) == len(set(ids)) == 27
    table = [n(str(i)) for i in range(1, 26)]
    assert [i for i in ids if i in table] == table                            # OI-01 to OI-25, in the table's order
    assert [i for i in ids if i not in table] == [n("17.6"), n("17.7")]       # IN-06 and IN-07
    assert wf.key == "owner-info-cycle" and wf.procedure == "owner-info-cycle" and wf.family == "members"


def test_each_step_has_the_kind_the_table_gives_it(wf):
    kinds = {s.id: s.kind for s in wf.steps}
    P_, C, J, PL, D, W = (StepKind.PERSON, StepKind.CHECK, StepKind.JOB, StepKind.PLAN, StepKind.DECISION, StepKind.WAIT)
    want = {"1": P_, "2": C, "3": D, "4": P_, "5": P_, "6": J, "7": P_, "8": P_, "9": J, "10": P_, "11": J, "12": P_, "13": J,
            "14": W, "15": P_, "16": P_, "17": P_, "17.6": D, "17.7": PL, "18": C, "19": P_, "20": P_, "21": W, "22": C,
            "23": P_, "24": W, "25": P_}
    assert {k: kinds[n(k)] for k in want} == want
    # the table's `plan` rows whose approvals kind is not built are a person's step with the command, never a plan nothing can make
    plans = [s for s in wf.steps if s.kind is StepKind.PLAN]
    assert [(s.id, s.plan_kind) for s in plans] == [(n("17.7"), "owner-info-tags")]


def test_each_step_has_the_role_the_table_gives_it(wf):
    roles = {s.id: s.role for s in wf.steps}
    M, A, S, J = Role.MANAGER, Role.ADMINISTRATOR, Role.SECRETARY, Role.JASON
    want = {"1": A, "2": J, "3": S, "4": M, "12": M, "16": M, "17": M, "17.6": S, "17.7": M, "18": J, "22": J, "25": A, "21": M}
    assert {k: roles[n(k)] for k in want} == want
    assert all(s.role is S for s in wf.steps if s.kind is StepKind.DECISION)     # the board decides; the secretary records
    assert all(s.role not in (Role.JASON, Role.SCHEDULER) for s in wf.steps if s.kind is StepKind.PERSON)


def test_every_step_says_why_and_a_command_or_a_check_shows_what_to_do(wf):
    for s in wf.steps:
        assert s.why, s.id
        assert s.command or s.check is not None or s.kind in (StepKind.WAIT, StepKind.PERSON, StepKind.DECISION), s.id
        if s.kind is StepKind.PERSON and s.id not in (n("7"), n("15")):
            assert s.command, s.id                                               # the two link tests have no command: jason never signs in
        if s.kind is StepKind.PERSON:
            assert s.record, s.id                                                # an attestation points at what shows it


def test_the_needs_follow_the_table(wf):
    needs = {s.id: set(s.needs) for s in wf.steps}
    table = {"2": {"1"}, "3": {"1"}, "4": {"1"}, "5": {"4"}, "6": {"5"}, "7": {"5"}, "8": {"5"}, "9": {"4"}, "10": {"9"},
             "11": {"10", "4"}, "12": {"11", "7"}, "13": {"12"}, "14": {"12"}, "15": {"14"}, "16": {"15", "13"}, "17": {"12"},
             "17.6": {"17"}, "17.7": {"17", "17.6"}, "18": {"12"}, "19": {"18"}, "20": {"13"}, "21": {"12"},
             "22": {"17.7", "21"}, "23": {"22"}, "24": {"22"}, "25": {"23"}}
    assert {k: needs[n(k)] for k in table} == {k: {n(x) for x in v} for k, v in table.items()}
    assert needs[n("1")] == set()


def test_the_dates_are_slots_asked_at_start_and_the_entry_day_is_reports_mailed_less_30_days(wf):
    assert [d.name for d in wf.dates] == ["opens_on", "return_by", "reports_mailed"]
    assert wf.check_dates(DATES) == []
    assert wf.check_dates({**DATES, "return_by": "2099-09-01"})                  # before the cycle opens
    assert wf.check_dates({k: v for k, v in DATES.items() if k != "reports_mailed"})
    for sid_ in (n("17.7"), n("22")):
        clock = wf.step(sid_).clock
        assert (clock.basis, clock.slot, clock.days, clock.cite) == (ClockBasis.LAW, "reports_mailed", -30, "CIV 4041(b)(1)")
    from jason.community.forms import AnswerCycle

    assert -general.ENTRY.days == AnswerCycle.ENTRY_LEAD_DAYS                    # the profile's cycle and the definition agree
    proposed = {s.id: s.clock for s in wf.steps if s.clock and s.clock.basis is ClockBasis.PROPOSED_POLICY}
    assert (proposed[n("19")].slot, proposed[n("19")].days) == ("return_by", -7)
    assert (proposed[n("23")].slot, proposed[n("23")].days) == ("return_by", 7)
    assert wf.step(n("21")).clock.basis is ClockBasis.PERSON and wf.step(n("21")).elapsed.value == "ends"


def test_a_legal_step_cannot_be_skipped_and_the_skippable_ones_are_the_tables(wf):
    assert {s.id for s in wf.steps if s.is_legal} == {n("17.7"), n("22")}
    assert all(s.skip is None for s in wf.steps if s.is_legal)
    assert {s.id for s in wf.steps if s.skip is not None} == {n("2"), n("19")}
    assert wf.has_legal_clock()


def test_it_names_no_association_and_no_amount_of_money_or_person(wf):
    text = repr(wf).lower()
    for word in ("mystique", "123 main", "example village"):
        assert word not in text
    assert all(isinstance(c, str) for s in wf.steps for c in s.evidence)


def test_it_validates_against_the_real_registries_and_the_jobs_it_names(wf):
    assert definitions.validate(wf, jobs=set(JOBS)) == []
    assert {s.job for s in wf.steps if s.job} <= set(JOBS)
    assert {s.plan_kind for s in wf.steps if s.plan_kind} <= {k.key for k in registry.kinds()}
    assert {s.job for s in wf.steps if s.job} == {"payhoa-form-test", "owner-info-send-plan", "owner-info-email-test", "notices-sync"}


def test_an_unregistered_kind_or_job_stops_it_registering_and_names_the_step():
    with pytest.raises(InvalidWorkflow) as bad:
        general.register_general(plan_kinds={"example-plan"})
    assert n("17.7") in str(bad.value) and "owner-info-tags" in str(bad.value)
    with pytest.raises(InvalidWorkflow) as bad:
        general.register_general(jobs={"notices-sync"})
    assert "owner-info-send-plan" in str(bad.value)
    assert definitions.find("owner-info-cycle") is None


def test_a_law_clock_that_does_not_resolve_stops_it_registering():
    with pytest.raises(InvalidWorkflow) as bad:
        general.register_general(resolve_law=lambda cite: False)
    assert "CIV 4041(b)(1)" in str(bad.value)
    assert general.register_general(resolve_law=lambda cite: None) and definitions.find("owner-info-cycle")   # cannot tell: a skip


def test_register_general_is_explicit_idempotent_and_loads_no_profile():
    assert definitions.find("owner-info-cycle") is None                          # importing the module registered nothing
    first = general.register_general()
    again = general.register_general()
    assert [w.key for w in first] == [w.key for w in again] == ["owner-info-cycle"]
    assert [w.key for w in definitions.all_definitions()] == ["owner-info-cycle"]
    code = (
        "import sys, json\n"
        "from jason.workflows import definitions_general as g, definitions\n"
        "assert definitions.find('owner-info-cycle') is None\n"
        "g.register_general()\n"
        "print(json.dumps({'profile': sorted(m for m in sys.modules if 'mystique' in m), 'n': len(definitions.all_definitions())}))\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout.strip().splitlines()[-1]) == {"profile": [], "n": 1}


def test_the_shelf_resolver_is_true_false_or_cannot_tell(tmp_path):
    assert general.shelf_resolver(None) is None
    assert general.shelf_resolver(tmp_path)("CIV 4041(b)(1)") is None            # no shelf here
    (tmp_path / "authorities" / "CIV").mkdir(parents=True)
    assert general.shelf_resolver(tmp_path)("CIV 4041(b)(1)") is False           # the code is on the shelf, the section is not


# --- drift from the procedure -----------------------------------------------------------------------------------------

def test_the_sop_addresses_exist_in_the_real_procedure(wf):
    assert definitions.drift([wf]) == []
    from jason.community.procedures import find

    proc = find("owner-info-cycle")
    assert len(proc.steps) == 20
    for s in wf.steps:
        if s.sop:
            key, index = parse_sop(s.sop)
            assert key == "owner-info-cycle" and 1 <= index <= len(proc.steps), s.id


def test_a_step_with_a_command_is_built_over_the_procedure_step_with_that_command(wf):
    """The index is a position in the procedure; these pin the ones where the command is the same words."""
    from jason.community.procedures import find

    proc = find("owner-info-cycle")

    def command(step_id):
        return proc.steps[parse_sop(wf.step(n(step_id)).sop)[1] - 1].command

    assert "--send-plan" in command("9") and "--email-batch" in command("12") and "--mail-batch" in command("16")
    assert "--payhoa-test" in command("6") and "campaigns" in command("4") and "notices" in command("13")
    assert "jason responses" in command("17") and "approvals plan owner-info-tags" in command("17.7")
    assert "followups" in command("18") and "--follow-up reminder" in command("19") and "lessons" in command("25")
    assert "broadcast" in command("10") and "packet" in command("8") and "--payhoa" in command("5")
    # and every step that has a person flag in the procedure is a person's or the board's here
    for s in wf.steps:
        if s.sop and proc.steps[parse_sop(s.sop)[1] - 1].person and s.kind not in (StepKind.PERSON, StepKind.DECISION, StepKind.CHECK):
            pytest.fail(f"{s.id} is a person's step in the procedure and {s.kind.value} here")


# --- a plan that follows a real approval record -----------------------------------------------------------------------

def start(data, wf=None, *, at=BEGAN):
    general.register_general()
    out = api.start(data, "owner-info-cycle", "campaign:OI-2099", "Owner information 2099", DATES, ADMIN, yes=True, at=at,
                    today=date(2099, 9, 1))
    return out["run"]["id"]


def readers_for(data, day):
    return StoreReaders(data, community=Community(request()), today=day)


def open_run(data, rid, day):
    return api.open_run(data, rid, ADMIN, readers=readers_for(data, day), yes=True, roles_of=roles_of, today=day)


def step_state(data, rid, step, day):
    return next(s for s in api.show(data, rid, today=day)["steps"] if s["id"] == n(step))


def attest(data, rid, step, by, day, record="the record", **more):
    return api.attest(data, rid, n(step), by, roles_of=roles_of, record=record, readers=readers_for(data, day), today=day, **more)


def test_the_recording_plan_follows_the_approval_a_person_makes(data):
    """The plan step makes nothing: a person plans (jason approvals plan owner-info-tags); the run finds it, then follows its
    status from planned through review to applied, and is done only when it is applied."""
    day = date(2099, 10, 1)
    rid = start(data)
    run_to_plan(data, rid, day)               # the steps before it, done by their people
    assert step_state(data, rid, "17.7", day)["state"] == "ready"
    open_run(data, rid, day)
    assert step_state(data, rid, "17.7", day)["state"] == "ready"                  # no approval yet: nothing was made for it
    assert not (data / "approvals").exists()                                       # and jason made none
    approval = make_approval(data, status=model.ApprovalStatus.PLANNED)
    res = open_run(data, rid, day)
    made = [e for e in res["appended"] if e["kind"] == "plan-made"]
    assert len(made) == 1 and made[0]["detail"]["approval"] == approval.id and made[0]["step"] == n("17.7")
    assert step_state(data, rid, "17.7", day)["state"] == "waiting"
    assert open_run(data, rid, day)["appended"] == []                              # a second open changes nothing
    for status, expected in ((model.ApprovalStatus.IN_REVIEW, "in_review"), (model.ApprovalStatus.APPROVED, "approved"),
                             (model.ApprovalStatus.PARTIALLY_APPROVED, "partially_approved")):
        make_approval(data, status=status)
        res = open_run(data, rid, day)
        decided = [e for e in res["appended"] if e["kind"] == "approval-decided"]
        assert [e["detail"]["status"] for e in decided] == [expected]
        assert step_state(data, rid, "17.7", day)["state"] == "waiting"
    make_approval(data, status=model.ApprovalStatus.APPLIED)
    res = open_run(data, rid, day)
    assert [e["kind"] for e in res["appended"] if e["step"] == n("17.7")] == ["applied"]
    assert step_state(data, rid, "17.7", day)["state"] == "done"
    assert any(l["kind"] == "approval" and l["address"] == approval.id for l in res["run"]["links"])


def test_a_withdrawn_approval_fails_the_plan_step_and_a_replacement_is_followed(data):
    day = date(2099, 10, 1)
    rid = start(data)
    run_to_plan(data, rid, day)
    first = make_approval(data, status=model.ApprovalStatus.PLANNED, ident="apr-20990101T120000-aaaa")
    open_run(data, rid, day)
    make_approval(data, status=model.ApprovalStatus.SUPERSEDED, ident=first.id, superseded_by="apr-20990101T130000-bbbb")
    make_approval(data, status=model.ApprovalStatus.IN_REVIEW, ident="apr-20990101T130000-bbbb")
    res = open_run(data, rid, day)
    assert [e["detail"]["approval"] for e in res["appended"] if e["kind"] == "approval-decided"] == ["apr-20990101T130000-bbbb"]
    make_approval(data, status=model.ApprovalStatus.WITHDRAWN, ident="apr-20990101T130000-bbbb", notes=("withdrawn: wrong list",))
    open_run(data, rid, day)
    s = step_state(data, rid, "17.7", day)
    assert s["state"] == "failed" and "withdrawn" in s["reason"]
    assert api.show(data, rid, today=day)["state"] == "failed"


def test_an_attestation_never_does_the_plan_step(data):
    day = date(2099, 10, 1)
    rid = start(data)
    run_to_plan(data, rid, day)
    from jason.workflows.types import StepRefused

    with pytest.raises(StepRefused, match="plan step"):
        attest(data, rid, "17.7", MANAGER, day)


# --- one run, from start to done --------------------------------------------------------------------------------------

def mark_job(data, job_id, status, summary=""):
    with sqlite3.connect(data / "jobs.db") as con:
        con.execute("update jobs set status = ?, summary = ? where id = ?", (status, summary, job_id))


def do_job(data, rid, step, argv, day, confirmed_by=""):
    """Step ``step`` is ready; a person queues the command; the run adopts it, then sees the worker finish it (the test ends it
    in the queue's own file; the run only reads it)."""
    assert step_state(data, rid, step, day)["state"] == "ready", step_state(data, rid, step, day)
    open_run(data, rid, day)
    assert step_state(data, rid, step, day)["state"] == "ready"                  # nothing queued yet: the run queued nothing
    job = jobs.add(data, argv, confirmed_by=confirmed_by)       # a person queues the command
    res = open_run(data, rid, day)
    queued = [e for e in res["appended"] if e["kind"] == "job-queued" and e["step"] == n(step)]
    assert len(queued) == 1 and queued[0]["detail"]["job"] == str(job.id)
    assert step_state(data, rid, step, day)["state"] == "running"
    assert open_run(data, rid, day)["appended"] == []
    mark_job(data, job.id, "done", "finished")
    res = open_run(data, rid, day)
    assert [e["kind"] for e in res["appended"] if e["step"] == n(step)] == ["job-finished"]
    assert step_state(data, rid, step, day)["state"] == "done"


def run_to_plan(data, rid, day):
    """Steps 1 to 17.6 done, so 17.7 (the recording plan) is ready. Seeds the stores those steps read."""
    seed_campaign(data)
    open_run(data, rid, day)
    attest(data, rid, "1", ADMIN, day)
    open_run(data, rid, day)
    attest(data, rid, "3", SECRETARY, day, outcome="adopted")
    attest(data, rid, "4", MANAGER, day, record="EM99E")
    for step in ("5",):
        attest(data, rid, step, MANAGER, day)
    for step in ("7", "8"):
        attest(data, rid, step, MANAGER, day)
    do_job(data, rid, "6", ["forms", "--payhoa-test", "owner-info", "--yes"], day, confirmed_by=MANAGER)
    do_job(data, rid, "9", ["owner-info", "--send-plan"], day)
    attest(data, rid, "10", MANAGER, day)
    do_job(data, rid, "11", ["owner-info", "--email-batch", "--message", "A.md", "--only", "me", "--yes"], day, confirmed_by=MANAGER)
    attest(data, rid, "12", MANAGER, day, record="owner-info-2099-email, confirmed by S. Secretary")
    do_job(data, rid, "13", ["notices", "owner-info-2099", "--sync"], day)
    notice_ledger.save(data, [notice_ledger.Attempt("owner-info-2099", 1, 1, "123 Main St", "email", "b", "ref-1",
                                                    status=notice_ledger.Delivery.DELIVERED)])
    open_run(data, rid, day)
    attest(data, rid, "17", MANAGER, day)
    attest(data, rid, "17.6", SECRETARY, day, outcome="adopted", record="minutes 2099-10-20")


def test_one_run_from_start_to_done_over_made_up_stores(data, monkeypatch):
    day = date(2099, 10, 1)
    rid = start(data)
    assert api.show(data, rid, today=day)["state"] == "draft"
    assert api.runs(data)[0]["definition"] == "owner-info-cycle"

    # the clocks: the entry day is the reports-mailed day less 30, in the law's citation
    shown = api.show(data, rid, today=day)
    entry = [c for c in shown["clocks"] if c["step"] == n("22")][0]
    assert (entry["due"], entry["basis"], entry["cite"]) == ("2099-11-01", "law", "CIV 4041(b)(1)")

    before_opening = tree(data)
    run_to_plan(data, rid, day)
    states = {s["id"]: s["state"] for s in api.show(data, rid, today=day)["steps"]}
    assert states[n("2")] == "done" and states[n("14")] == "done"                 # the checks passed on the stores; the wait ended on the ledger
    ev = [e for e in store.open_run(data, rid).events if e.kind is K.CHECK_RAN and e.step == n("2")]
    assert ev and ev[0].detail["ok"] is True and "days after the cycle opens" in ev[0].detail["message"]
    assert (data / "approvals").exists() is False                                  # no approval was made by the run
    assert not any(k.startswith("approvals") for k in tree(data) if k not in before_opening)

    # the evidence a done step was attested against is kept, and a moved store reads "changed since"
    campaign_step = next(s for s in store.open_run(data, rid).events if s.kind is K.ATTESTED and s.step == n("4"))
    assert campaign_step.detail["evidence"][0].startswith("file:forms/campaigns.json@")
    seed_campaign(data, "EM99M", "mail")
    res = open_run(data, rid, day)
    changed = [e for e in res["appended"] if e["kind"] == "changed"]
    assert [e["step"] for e in changed] == [n("4")]
    assert step_state(data, rid, "4", day)["state"] == "done" and step_state(data, rid, "4", day)["changed"]

    # the plan, planned and applied by people
    make_approval(data, status=model.ApprovalStatus.PLANNED)
    open_run(data, rid, day)
    make_approval(data, status=model.ApprovalStatus.APPLIED)
    open_run(data, rid, day)
    assert step_state(data, rid, "17.7", day)["state"] == "done"

    # the second test of the link, then the letters: a person's steps, with the second person named in the record
    attest(data, rid, "15", MANAGER, day, record="2099-09-17, the emailed link opened as an owner")
    attest(data, rid, "16", MANAGER, day, record="owner-info-2099-mail, 10 letters, 1250 cents, confirmed by S. Secretary")

    # the follow-up steps: the outstanding read (the follow-ups module is read; here it holds nothing)
    from jason.tasks import followups

    monkeypatch.setattr(followups, "items", lambda d, c, today=None: [])
    open_run(data, rid, day)
    assert step_state(data, rid, "18", day)["state"] == "done"
    api.skip(data, rid, n("19"), MANAGER, roles_of=roles_of, reason="nobody is outstanding", readers=readers_for(data, day), today=day)
    attest(data, rid, "20", MANAGER, day, record="0 owed")

    # the return-by date passes: the wait ends by its date; the entry-day check fails on a confirmed, unrecorded answer
    after = date(2099, 10, 24)
    seed_inbox(data, [arrival("gmail:1", State.KEYED)])
    open_run(data, rid, after)
    assert step_state(data, rid, "21", after)["state"] == "done"
    failed = step_state(data, rid, "22", after)
    assert failed["state"] == "failed" and failed["reason"] == "0 arrival(s) unread or unconfirmed; 1 confirmed and not recorded; 0 plan(s) open"
    assert api.show(data, rid, today=after)["state"] == "failed"
    seed_inbox(data, [arrival("gmail:1", State.RECORDED)])
    open_run(data, rid, after)
    assert step_state(data, rid, "22", after)["state"] == "done"

    # close, the reports, the lessons
    attest(data, rid, "23", MANAGER, after, record="EM99E and EM99M closed")
    assert step_state(data, rid, "24", after)["state"] == "waiting"
    api.arrived(data, rid, n("24"), MANAGER, roles_of=roles_of, what="reports mailed 2099-12-01", readers=readers_for(data, after), today=after)
    attest(data, rid, "25", ADMIN, after, record="lessons added")
    final = api.show(data, rid, today=after)
    assert final["state"] == "done" and final["current"] == "", [(s["id"], s["state"], s["reason"]) for s in final["steps"] if s["state"] not in ("done", "skipped")]
    assert all(s["state"] in ("done", "skipped") for s in final["steps"])
    assert api.verify(data, rid)["ok"]
    assert api.open_run(data, rid, ADMIN, readers=readers_for(data, after), today=after)["appended"] == []


def test_the_run_refuses_the_wrong_people_and_a_missing_record(data):
    day = date(2099, 10, 1)
    rid = start(data)
    open_run(data, rid, day)
    from jason.workflows.types import StepRefused

    with pytest.raises(StepRefused, match="administrator"):
        attest(data, rid, "1", MANAGER, day)                                        # the profile's dates are the administrator's
    with pytest.raises(StepRefused, match="record"):
        api.attest(data, rid, n("1"), ADMIN, roles_of=roles_of, readers=readers_for(data, day), today=day)
    attest(data, rid, "1", ADMIN, day)
    open_run(data, rid, day)
    with pytest.raises(StepRefused, match="secretary"):
        attest(data, rid, "3", MANAGER, day, outcome="adopted")                      # the board's decision is recorded by the secretary
    with pytest.raises(StepRefused):
        api.skip(data, rid, n("3"), MANAGER, roles_of=roles_of, reason="no", readers=readers_for(data, day), today=day)   # no skip rule
    with pytest.raises(StepRefused):
        api.skip(data, rid, n("22"), MANAGER, roles_of=roles_of, reason="no", readers=readers_for(data, day), today=day)  # a legal step


def test_the_dates_that_leave_no_room_fail_the_second_step_and_block_the_run(data):
    general.register_general()
    tight = {**DATES, "return_by": "2099-09-18"}
    rid = api.start(data, "owner-info-cycle", "campaign:OI-2099", "tight", tight, ADMIN, yes=True, at=BEGAN, today=date(2099, 9, 1))["run"]["id"]
    day = date(2099, 9, 16)
    open_run(data, rid, day)
    attest(data, rid, "1", ADMIN, day)
    open_run(data, rid, day)
    s = step_state(data, rid, "2", day)
    assert s["state"] == "failed" and "no room" in s["reason"]
    assert api.show(data, rid, today=day)["state"] == "failed"                        # the run says so; it does not go on as if it passed
    api.skip(data, rid, n("2"), ADMIN, roles_of=roles_of, reason="the board chose a short cycle", readers=readers_for(data, day), today=day)
    assert step_state(data, rid, "2", day)["state"] == "skipped"
    assert api.show(data, rid, today=day)["state"] == "active"
