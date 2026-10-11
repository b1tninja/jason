"""The whole lifecycle of a made-up run (engine doc, section 9, test 10), in a temporary data folder with fake readers:
start, open, a check, a person's attestation, a plan, a job, a wait, a decision, then reopen, pause, cancel, verify, reindex."""

from __future__ import annotations

import pytest

from jason.workflows import api, definitions, resume, store
from jason.workflows.resume import ApprovalState, JobState
from jason.workflows.types import RunChanged, StepRefused
from test_workflows_support import (
    C1, C2, C3, C4, C5, C6, DATES, OWNER, SECRETARY, TODAY, TREASURER, VISITOR, FakeReaders, data, example, roles_of,
)

SUBJECT = "campaign:EX-2099"


def start(data, **kw):
    return api.start(data, "example-cycle", SUBJECT, "Example cycle 2099", DATES, OWNER, yes=True, today=TODAY,
                     at="2099-09-15T09:00:00Z", **kw)["run"]["id"]


def states(shown):
    return {s["id"]: s["state"] for s in shown["steps"]}


def test_a_run_from_start_to_the_last_step(data, example):
    rd = FakeReaders()
    rid = start(data)
    assert rid.startswith("run-") and len(rid) == 14
    shown = api.show(data, rid, today=TODAY)
    assert shown["state"] == "draft"
    assert all(c["status"] in ("not running", "undated") for c in shown["clocks"])

    # open: the draft becomes active, the check runs and passes, the person's step is next
    opened = api.open_run(data, rid, OWNER, readers=rd, yes=True, today=TODAY, at="2099-09-15T09:01:00Z")
    kinds = [e["kind"] for e in opened["appended"]]
    assert kinds == ["resumed", "check-ran"]
    assert opened["run"]["state"] == "active" and opened["run"]["current"] == C2
    assert states(opened["run"])[C1] == "done" and states(opened["run"])[C2] == "needs a person"
    assert any(c["status"] == "upcoming" and c["basis"] == "law" for c in opened["run"]["clocks"])
    assert api.open_run(data, rid, OWNER, readers=rd, today=TODAY)["appended"] == []     # a second open is a no-op

    # the person's step: only a holder of the role, and only with the record
    with pytest.raises(StepRefused, match="does not hold"):
        api.attest(data, rid, C2, VISITOR, roles_of=roles_of, record="notice-1", today=TODAY)
    with pytest.raises(StepRefused, match="record"):
        api.attest(data, rid, C2, OWNER, roles_of=roles_of, today=TODAY)
    done = api.attest(data, rid, C2, OWNER, roles_of=roles_of, record="notice-1", readers=rd, today=TODAY)
    assert done["event"]["detail"]["evidence"] == ["store:notices@n111"]
    assert states(done["run"])[C2] == "done"

    # the plan: made once, found again by its key, decided and applied elsewhere
    api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    assert len(rd.plans_made) == 1
    key = resume.idem_key(rid, C3, SUBJECT)
    assert rd.plans_made == [key]
    assert states(api.show(data, rid, today=TODAY))[C3] == "waiting"
    with pytest.raises(StepRefused, match="plan step"):
        api.attest(data, rid, C3, OWNER, roles_of=roles_of, record="x", today=TODAY)
    rd.approvals[key] = ApprovalState("ap-1", "approved")
    ev = api.open_run(data, rid, OWNER, readers=rd, today=TODAY)["appended"]
    assert [e["kind"] for e in ev] == ["approval-decided"]
    rd.approvals[key] = ApprovalState("ap-1", "applied")
    ev = api.open_run(data, rid, OWNER, readers=rd, today=TODAY)["appended"]
    assert [e["kind"] for e in ev] == ["applied", "job-queued"]      # the next step's job starts in the same open
    assert len(rd.jobs_queued) == 1
    api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    assert len(rd.jobs_queued) == 1

    # the job finishes; the wait begins
    jkey = resume.idem_key(rid, C4, SUBJECT)
    rd.jobs[jkey] = JobState("job-1", "finished")
    ev = api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    assert [e["kind"] for e in ev["appended"]] == ["job-finished", "waited"]
    assert ev["run"]["state"] == "waiting" and states(ev["run"])[C5] == "waiting"
    with pytest.raises(StepRefused, match="cannot be skipped"):
        api.skip(data, rid, C5, OWNER, roles_of=roles_of, reason="no", today=TODAY)

    # a store moved under a done step: one changed event, the step stays done
    rd.hashes["store:notices"] = "n222"
    ev = api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    assert [e["kind"] for e in ev["appended"]] == ["changed"]
    step2 = next(s for s in ev["run"]["steps"] if s["id"] == C2)
    assert step2["state"] == "done" and step2["changed"][0]["was"] == "n111" and step2["changed"][0]["now"] == "n222"
    assert api.open_run(data, rid, OWNER, readers=rd, today=TODAY)["appended"] == []

    # the answer arrives; the decision is the secretary's
    rd.arrivals[C5] = "answer received"
    ev = api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    assert [e["kind"] for e in ev["appended"]] == ["arrived"]
    assert states(ev["run"])[C6] == "needs a person"
    with pytest.raises(StepRefused, match="opening the run gives no standing"):
        api.attest(data, rid, C6, OWNER, roles_of=roles_of, record="minutes-1", outcome="adopted", today=TODAY)
    tabled = api.attest(data, rid, C6, SECRETARY, roles_of=roles_of, record="minutes-1", outcome="tabled", today=TODAY)
    assert states(tabled["run"])[C6] == "needs a person"        # not a final outcome
    final = api.attest(data, rid, C6, SECRETARY, roles_of=roles_of, record="minutes-2", outcome="adopted", today=TODAY)
    assert final["run"]["state"] == "done" and final["run"]["current"] == ""

    # the chain, the index, and the list
    assert api.verify(data, rid)["ok"]
    assert api.runs(data) == []                                  # a done run is not open
    assert [r["id"] for r in api.runs(data, state="all")] == [rid]
    before = store.index_read(data)
    rows = api.reindex(data, today=TODAY)["rows"]
    assert {r["id"]: r["state"] for r in rows} == {r["id"]: r["state"] for r in before.values()}

    # a person reopens a done step; the others stay done
    shown = api.reopen(data, rid, C2, OWNER, roles_of=roles_of, reason="the notice was wrong", today=TODAY)
    assert states(shown["run"])[C2] == "needs a person" and states(shown["run"])[C6] == "done"
    assert shown["run"]["state"] == "active"


def test_start_checks_its_dates_and_the_legal_clock(data, example):
    with pytest.raises(StepRefused, match="legal clock"):
        api.start(data, "example-cycle", SUBJECT, "x", DATES, OWNER, today=TODAY)
    with pytest.raises(StepRefused, match="before answers_by"):
        api.start(data, "example-cycle", SUBJECT, "x", {"answers_by": "2099-11-02", "closes_on": "2099-11-01"}, OWNER,
                  yes=True, today=TODAY)
    with pytest.raises(StepRefused, match="is required"):
        api.start(data, "example-cycle", SUBJECT, "x", {"answers_by": "2099-11-02"}, OWNER, yes=True, today=TODAY)
    with pytest.raises(StepRefused, match="engine's own name"):
        api.start(data, "example-cycle", SUBJECT, "x", DATES, "jason", yes=True, today=TODAY)
    with pytest.raises(StepRefused, match="no workflow definition"):
        api.start(data, "no-such", SUBJECT, "x", DATES, OWNER, yes=True, today=TODAY)
    rid = start(data)
    with pytest.raises(StepRefused, match="legal clock"):
        api.open_run(data, rid, OWNER, readers=FakeReaders(), today=TODAY)


def test_pause_note_cancel_and_a_changed_run(data, example):
    rd = FakeReaders()
    rid = start(data)
    api.open_run(data, rid, OWNER, readers=rd, yes=True, today=TODAY)
    paused = api.pause(data, rid, OWNER, reason="waiting on the board", today=TODAY)
    assert paused["run"]["state"] == "paused" and paused["run"]["pausedReason"] == "waiting on the board"
    # a paused run is left alone by the resume check, and its steps are not acted on
    assert api.open_run(data, rid, OWNER, readers=rd, today=TODAY)["appended"] == []
    with pytest.raises(StepRefused, match="paused"):
        api.attest(data, rid, C2, OWNER, roles_of=roles_of, record="r", today=TODAY)
    assert api.resume_run(data, rid, OWNER, today=TODAY)["run"]["state"] == "active"
    api.note(data, rid, OWNER, text="called the Example Alarm office", step=C2, today=TODAY)

    n = api.show(data, rid, today=TODAY)["n"]
    with pytest.raises(RunChanged, match=f"it is now n={n}"):
        api.note(data, rid, OWNER, text="stale", expect=n - 1, today=TODAY)
    api.note(data, rid, OWNER, text="fresh", expect=n, today=TODAY)

    with pytest.raises(StepRefused, match="only secretary, manager"):
        api.cancel(data, rid, VISITOR, roles_of=roles_of, reason="no", yes=True, today=TODAY)
    with pytest.raises(StepRefused, match="needs yes"):
        api.cancel(data, rid, OWNER, roles_of=roles_of, reason="no longer needed", today=TODAY)
    with pytest.raises(StepRefused, match="reason"):
        api.cancel(data, rid, OWNER, roles_of=roles_of, reason="", yes=True, today=TODAY)
    gone = api.cancel(data, rid, OWNER, roles_of=roles_of, reason="no longer needed", yes=True, today=TODAY)
    assert gone["run"]["state"] == "cancelled" and gone["run"]["cancelledReason"] == "no longer needed"
    assert [r["id"] for r in api.runs(data, state="cancelled")] == [rid]       # listed for the board
    assert api.runs(data) == []
    assert api.open_run(data, rid, OWNER, readers=rd, today=TODAY)["appended"] == []


def test_a_failing_check_fails_the_run_and_a_better_reading_recovers_it(data, example):
    from jason.workflows.types import CheckResult

    rd = FakeReaders()
    rd.checks[C1] = CheckResult(False, (), "the example facts are missing")
    rid = start(data)
    opened = api.open_run(data, rid, OWNER, readers=rd, yes=True, today=TODAY)
    assert opened["run"]["state"] == "failed" and states(opened["run"])[C2] == "blocked"
    assert api.open_run(data, rid, OWNER, readers=rd, today=TODAY)["appended"] == []        # same reading, nothing appended
    rd.unreadable.add(C1)
    unreadable = api.open_run(data, rid, OWNER, readers=rd, today=TODAY)
    assert "cannot read" in next(s for s in unreadable["run"]["steps"] if s["id"] == C1)["reason"]
    rd.unreadable.clear()
    rd.checks[C1] = CheckResult(True, ("store:example@aaaa11",), "ok")
    assert api.open_run(data, rid, OWNER, readers=rd, today=TODAY)["run"]["state"] == "active"
