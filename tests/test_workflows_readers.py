"""``StoreReaders`` (src/jason/workflows/readers.py): the engine's world read from jason's own stores, in a temporary data
folder with made-up stores. Nothing here reads a real store, reaches the network, or loads a profile; every reader is
read-only, and a test pins that by comparing the folder before and after.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason import jobs
from jason.approvals import model, store as approvals
from jason.community.response_inbox import Arrival, Channel, State
from jason.tasks import campaigns, notice_ledger
from jason.tasks import response_inbox as inbox
from jason.workflows import api, definitions
from jason.workflows.readers import CHECKS, JOBS, JobSpec, NamedCheck, StoreReaders, named_check
from jason.workflows.resume import ApprovalState, JobState
from jason.workflows.types import (
    CheckResult, ClockBasis, ClockDef, DateSlot, EventKind as K, Role, StepDef, StepKind, Workflow,
)
from test_workflows_support import OWNER, TODAY, data  # noqa: F401 - the `data` fixture

BEGAN = "2020-01-01T00:00:00Z"         # a run "opened" long ago, so anything the tests make now is since it opened
RETURN_BY = date(2099, 10, 23)
DATES = {"opens_on": "2099-09-15", "return_by": "2099-10-23", "reports_mailed": "2099-12-01"}


def tree(root: Path) -> dict[str, bytes]:
    """Every file under a folder, with its bytes: what a read must leave exactly as it was."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def make_approval(data_dir, *, status=model.ApprovalStatus.PLANNED, kind="owner-info-tags", scope=None, requested_at=None,
                  ident="apr-20990101T120000-1a2b", superseded_by="", notes=()):
    approval = model.Approval(
        id=ident, kind=kind, title="Owner information", items=[], fingerprint="f" * 12, read_at="2099-01-01T00:00:00+00:00",
        requested_by="A. Manager", requested_at=requested_at or "2099-01-01T12:00:00+00:00", scope=dict(scope or {}),
        status=status, superseded_by=superseded_by, notes=list(notes))
    with approvals.locked("test"):
        approvals.save(approval, data_dir)
    return approval


def view_for(readers_data, *, opened=BEGAN, dates=None, subject="campaign:EX-2099"):
    """A RunView-shaped object for the reads that take only a few fields of it."""
    return SimpleNamespace(id="run-test", opened_at=opened, dates=dict(dates or DATES), subject=subject)


class Community:
    """A profile's say on the one thing the checks ask: its response requests."""

    def __init__(self, *requests):
        self._requests = requests

    def response_requests(self):
        return self._requests


def request(key="owner-info-2099", return_by=RETURN_BY):
    return SimpleNamespace(key=key, cycle=SimpleNamespace(return_by=return_by))


def one_step(**over):
    base = dict(id="w.1", title="A step", kind=StepKind.PLAN, role=Role.MANAGER, plan_kind="owner-info-tags")
    base.update(over)
    return StepDef(**base)


@pytest.fixture
def readers(data):
    data.mkdir(parents=True, exist_ok=True)
    return StoreReaders(data, community=Community(request()), today=date(2099, 10, 1))


# --- evidence ---------------------------------------------------------------------------------------------------------

def test_evidence_hashes_a_file_a_glob_and_nothing_else(data, readers):
    (data / "forms").mkdir()
    (data / "forms" / "campaigns.json").write_text('{"A": 1}', encoding="utf-8")
    first = readers.evidence("file:forms/campaigns.json")
    assert first and len(first) == 12
    assert readers.evidence("file:forms/campaigns.json") == first
    (data / "forms" / "campaigns.json").write_text('{"A": 2}', encoding="utf-8")
    assert readers.evidence("file:forms/campaigns.json") != first
    assert readers.evidence("file:forms/missing.json") is None and readers.evidence("store:nothing") is None
    (data / "owner-info").mkdir()
    assert readers.evidence("glob:owner-info/send-plan-*.md") is None
    (data / "owner-info" / "send-plan-2099-09-12.md").write_text("plan", encoding="utf-8")
    g = readers.evidence("glob:owner-info/send-plan-*.md")
    (data / "owner-info" / "send-plan-2099-09-13.md").write_text("plan again", encoding="utf-8")
    assert readers.evidence("glob:owner-info/send-plan-*.md") not in (None, g)


def test_evidence_never_leaves_the_data_folder(data, readers):
    (data.parent / "outside.txt").write_text("secret", encoding="utf-8")
    assert readers.evidence("file:../outside.txt") is None
    assert readers.evidence("glob:../*.txt") is None
    assert readers.evidence("file:" + str(data.parent / "outside.txt")) is None


# --- an approval ------------------------------------------------------------------------------------------------------

def test_an_approval_is_found_by_its_scope_key_and_reports_its_status(data, readers):
    assert readers.approval("k1") is None
    make_approval(data, scope={"workflow": "k1"}, status=model.ApprovalStatus.IN_REVIEW)
    assert readers.approval("k1") == ApprovalState("apr-20990101T120000-1a2b", "in_review", "")
    assert readers.approval("other") is None


def test_an_approval_is_found_by_the_plan_made_event_that_recorded_its_key(data, readers):
    definitions.reset()
    wf = Workflow("w", "W", "f", "campaign", steps=(one_step(),), dates=(DateSlot("d"),))
    definitions.register(wf)
    rid = api.start(data, "w", "campaign:X", "X", {"d": "2099-01-01"}, OWNER, at=BEGAN, today=TODAY)["run"]["id"]
    make_approval(data, status=model.ApprovalStatus.APPROVED)           # no scope key: the event is the link
    from jason.workflows import store

    store.append(data, "w", rid, K.PLAN_MADE, by="jason", step="w.1", detail={"key": "k2", "approval": "apr-20990101T120000-1a2b"})
    assert readers.approval("k2").status == "approved"
    definitions.reset()


def test_a_superseded_plan_is_followed_to_the_plan_that_replaced_it(data, readers):
    make_approval(data, scope={"workflow": "k3"}, status=model.ApprovalStatus.SUPERSEDED, ident="apr-20990101T120000-aaaa",
                  superseded_by="apr-20990102T120000-bbbb")
    make_approval(data, status=model.ApprovalStatus.PARTIALLY_APPROVED, ident="apr-20990102T120000-bbbb",
                  superseded_by="apr-20990103T120000-cccc", scope={"x": 1})
    make_approval(data, status=model.ApprovalStatus.WITHDRAWN, ident="apr-20990103T120000-cccc", notes=("withdrawn: wrong list",))
    state = readers.approval("k3")
    assert state.id == "apr-20990103T120000-cccc" and state.status == "withdrawn" and "wrong list" in state.reason


def test_make_plan_adopts_a_plan_a_person_made_since_the_run_opened_and_makes_none(data, readers):
    view = view_for(data)
    step = one_step()
    assert readers.make_plan("owner-info-tags", "k", step, view) is None
    make_approval(data, requested_at="2019-01-01T00:00:00+00:00", ident="apr-20190101T000000-0001")      # before the run
    make_approval(data, kind="gmail-drafts", ident="apr-20990101T120000-0002")                              # another kind
    assert readers.make_plan("owner-info-tags", "k", step, view) is None
    made = make_approval(data, ident="apr-20990101T120000-0003")
    assert readers.make_plan("owner-info-tags", "k", step, view) == made.id
    assert readers.make_plan("owner-info-tags", "k", step, view_for(data, opened="2100-01-01T00:00:00Z")) is None
    assert readers.make_plan("no-such-kind", "k", step, view) is None
    assert readers.make_plan("payhoa.owner-info.tags", "k", step, view) == made.id         # an alias reads as its kind


def test_make_plan_leaves_a_plan_another_run_holds(data, readers):
    definitions.reset()
    wf = Workflow("w", "W", "f", "campaign", steps=(one_step(),), dates=(DateSlot("d"),))
    definitions.register(wf)
    rid = api.start(data, "w", "campaign:X", "X", {"d": "2099-01-01"}, OWNER, at=BEGAN, today=TODAY)["run"]["id"]
    held = make_approval(data, ident="apr-20990101T120000-0003")
    from jason.workflows import store

    store.append(data, "w", rid, K.PLAN_MADE, by="jason", step="w.1", detail={"key": "someone-else", "approval": held.id})
    assert readers.make_plan("owner-info-tags", "k", one_step(), view_for(data)) is None
    assert readers.make_plan("owner-info-tags", "someone-else", one_step(), view_for(data)) == held.id    # its own holder keeps it
    definitions.reset()


# --- a job ------------------------------------------------------------------------------------------------------------

def test_job_specs_recognize_a_command_by_its_words():
    spec = JOBS["notices-sync"]
    assert spec.matches(["notices", "owner-info-2099", "--sync"])
    assert not spec.matches(["notices", "board-2099-10", "--sync"])           # another notice
    assert not spec.matches(["notices", "owner-info-2099"])                    # not a sync
    assert JOBS["owner-info-email-test"].matches(["owner-info", "--email-batch", "--message", "A.md", "--only", "me", "--yes"])
    assert not JOBS["owner-info-email-test"].matches(["owner-info", "--email-batch", "--message", "A.md", "--yes"])
    assert JobSpec("x", ("a",), forbid=("b",)).matches(["a"]) and not JobSpec("x", ("a",), forbid=("b",)).matches(["a", "b"])


def test_queue_job_adopts_the_matching_job_since_the_run_opened_and_reports_its_state(data, readers):
    step = one_step(kind=StepKind.JOB, job="owner-info-send-plan", plan_kind="")
    view = view_for(data)
    assert readers.queue_job("owner-info-send-plan", "k", step, view) is None        # no queue yet: nothing is created
    assert not (data / "jobs.db").exists()
    jobs.add(data, ["gmail", "--sync"])
    assert readers.queue_job("owner-info-send-plan", "k", step, view) is None
    mine = jobs.add(data, ["owner-info", "--send-plan"])
    assert readers.queue_job("owner-info-send-plan", "k", step, view) == str(mine.id)
    assert readers.queue_job("owner-info-send-plan", "k", step, view_for(data, opened="2100-01-01T00:00:00Z")) is None
    assert readers.queue_job("no-such-job", "k", step, view) is None
    # the state is read through the key the run recorded
    definitions.reset()
    wf = Workflow("w", "W", "f", "campaign", steps=(one_step(kind=StepKind.JOB, job="owner-info-send-plan", plan_kind=""),),
                  dates=(DateSlot("d"),))
    definitions.register(wf, jobs=set(JOBS))
    rid = api.start(data, "w", "campaign:X", "X", {"d": "2099-01-01"}, OWNER, at=BEGAN, today=TODAY)["run"]["id"]
    from jason.workflows import store

    store.append(data, "w", rid, K.JOB_QUEUED, by="jason", step="w.1", detail={"key": "k", "job": str(mine.id)})
    assert readers.job("k") == JobState(str(mine.id), "queued", "")
    assert readers.job("unknown") is None
    with sqlite3.connect(data / "jobs.db") as con:
        con.execute("update jobs set status = 'running' where id = ?", (mine.id,))
    assert readers.job("k").state == "running"
    with sqlite3.connect(data / "jobs.db") as con:
        con.execute("update jobs set status = 'done', summary = 'plan written' where id = ?", (mine.id,))
    assert readers.job("k") == JobState(str(mine.id), "finished", "plan written")
    with sqlite3.connect(data / "jobs.db") as con:
        con.execute("update jobs set status = 'failed', summary = 'exit 1' where id = ?", (mine.id,))
    assert readers.job("k") == JobState(str(mine.id), "failed", "exit 1")
    definitions.reset()


def test_a_cancelled_job_is_not_adopted(data, readers):
    step = one_step(kind=StepKind.JOB, job="owner-info-send-plan", plan_kind="")
    gone = jobs.add(data, ["owner-info", "--send-plan"])
    jobs.cancel(data, gone.id)
    assert readers.queue_job("owner-info-send-plan", "k", step, view_for(data)) is None


# --- reads write nothing ----------------------------------------------------------------------------------------------

def test_every_read_leaves_the_data_folder_exactly_as_it_was(data, readers):
    (data / "forms").mkdir()
    (data / "forms" / "campaigns.json").write_text("{}", encoding="utf-8")
    jobs.add(data, ["owner-info", "--send-plan"])
    make_approval(data, scope={"workflow": "k"})
    before = tree(data)
    view = view_for(data)
    step = one_step()
    readers.approval("k")
    readers.make_plan("owner-info-tags", "k2", step, view)
    readers.job("k")
    readers.queue_job("owner-info-send-plan", "k", one_step(kind=StepKind.JOB, job="owner-info-send-plan", plan_kind=""), view)
    readers.evidence("file:forms/campaigns.json")
    readers.evidence("glob:forms/*.json")
    readers.child_state("run-nothing")
    assert tree(data) == before
    empty = data.parent / "empty"
    empty.mkdir()
    bare = StoreReaders(empty)
    bare.approval("k"), bare.job("k"), bare.make_plan("owner-info-tags", "k", step, view)
    bare.queue_job("owner-info-send-plan", "k", step, view), bare.child_state("run-x")
    assert tree(empty) == {}                                                   # not even a jobs.db or an approvals folder


# --- the named checks -------------------------------------------------------------------------------------------------

def result(name, readers, dates=None):
    return CHECKS[name](readers, view_for(readers.data_dir, dates=dates), "")


def test_a_named_check_called_on_its_own_says_it_needs_the_stores():
    res = named_check("dates-room")(None)
    assert isinstance(named_check("x"), NamedCheck) and res.ok is False and "needs the stores" in res.message


def test_the_check_of_a_step_is_found_by_name_and_a_plain_callable_still_runs(readers):
    view = view_for(readers.data_dir)
    step = StepDef("w.1", "Dates", StepKind.CHECK, role=Role.JASON, check=named_check("dates-room"))
    assert readers.check(step, view).ok is True
    plain = StepDef("w.2", "Plain", StepKind.CHECK, role=Role.JASON, check=lambda v: CheckResult(True, (), "plain"))
    assert readers.check(plain, view).message == "plain"
    unknown = StepDef("w.3", "Unknown", StepKind.CHECK, role=Role.JASON, check=named_check("no-such-read"))
    assert readers.check(unknown, view).ok is False


def test_dates_room_wants_room_for_a_sync_and_a_resend_and_an_entry_day_after_return_by(readers):
    assert result("dates-room", readers).ok
    ok = result("dates-room", readers, {**DATES, "return_by": "2099-09-19"})
    assert ok.ok is False and "no room" in ok.message                         # 4 days: the sync (1) and a resend (3) fill them
    assert result("dates-room", readers, {**DATES, "return_by": "2099-09-20"}).ok is True
    early = result("dates-room", readers, {**DATES, "reports_mailed": "2099-11-10"})
    assert early.ok is False and "comes before the return-by" in early.message  # the entry day, 2099-10-11, is before 10-23
    assert result("dates-room", readers, {"opens_on": "2099-09-15"}).ok is False


def seed_inbox(data, arrivals):
    inbox.save_inbox(data, inbox.Inbox({a.id: a for a in arrivals}, {}))


def arrival(ident, state, channel=Channel.GMAIL, request_key="owner-info-2099", note="", superseded_by=""):
    return Arrival(ident, request_key, channel, "2099-09-20T10:00:00+00:00", "A. Owner", "123 Main St", "", (), state,
                   note=note, superseded_by=superseded_by)


def test_entry_day_gap_counts_what_is_unread_unrecorded_and_planned(data, readers):
    ok = result("entry-day-gap", readers)
    assert ok.ok and "0 arrival(s) unread" in ok.message
    seed_inbox(data, [
        arrival("gmail:1", State.NEW), arrival("gmail:2", State.READ), arrival("gmail:3", State.KEYED),
        arrival("payhoa:4", State.NEW, Channel.PAYHOA), arrival("payhoa:5", State.NEW, Channel.PAYHOA, note="status: complete"),
        arrival("gmail:6", State.RECORDED), arrival("gmail:7", State.DISMISSED), arrival("gmail:8", State.NEW, superseded_by="gmail:9"),
        arrival("gmail:10", State.NEW, request_key="another-request"),
    ])
    make_approval(data, status=model.ApprovalStatus.IN_REVIEW)
    gap = result("entry-day-gap", readers)
    assert gap.ok is False
    assert gap.message == "2 arrival(s) unread or unconfirmed; 2 confirmed and not recorded; 1 plan(s) open"
    assert any(e.startswith("file:responses/inbox.json@") for e in gap.evidence)


def test_entry_day_gap_cannot_tell_without_a_request_for_the_run(data):
    res = result("entry-day-gap", StoreReaders(data, community=Community(request(return_by=date(2099, 1, 1)))))
    assert res.ok is False and "no response request" in res.message
    assert result("entry-day-gap", StoreReaders(data, community=Community())).ok is False


def seed_campaign(data, code="EM99E", channel="email", year=2099, return_by="2099-10-23"):
    row = campaigns.Campaign(code=code, form="owner-information", handler="owner-information", channel=channel, year=year,
                             opened="2099-09-15", return_by=return_by, procedure="owner-info-cycle").to_json()
    path = data / campaigns.STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    rows[code] = row
    path.write_text(json.dumps(rows), encoding="utf-8")


def attempt(n, status, channel="email", notice="owner-info-2099"):
    return notice_ledger.Attempt(notice, n, n, f"{n} Main St", channel, "batch", f"ref-{n}", status=status)


def test_delivery_read_waits_for_an_outcome_for_every_emailed_copy(data, readers):
    assert "no email campaign" in result("delivery-read", readers).message
    seed_campaign(data)
    assert "not been synced" in result("delivery-read", readers).message
    D = notice_ledger.Delivery
    notice_ledger.save(data, [attempt(1, D.PENDING), attempt(2, D.DELIVERED)])
    waiting = result("delivery-read", readers)
    assert waiting.ok is False and "1 of 2 emailed copies" in waiting.message
    notice_ledger.save(data, [attempt(1, D.UNKNOWN), attempt(2, D.DELIVERED), attempt(3, D.BOUNCED), attempt(4, D.MAILED, "letter")])
    done = result("delivery-read", readers)
    assert done.ok and done.message == "3 emailed copies: 1 bounced, 1 delivered, 1 unknown"
    # a campaign of another cycle, and a mail campaign, are not this run's
    assert "no email campaign" in result("delivery-read", readers, {**DATES, "return_by": "2099-11-30"}).message


def test_delivery_read_is_the_arrival_of_its_wait_step(data, readers):
    step = StepDef("w.1", "Wait for delivery", StepKind.WAIT, role=Role.MANAGER, check=named_check("delivery-read"))
    view = view_for(data)
    assert readers.arrival(step, view) is None
    seed_campaign(data)
    notice_ledger.save(data, [attempt(1, notice_ledger.Delivery.DELIVERED)])
    assert "1 emailed copies" in readers.arrival(step, view)
    assert readers.arrival(StepDef("w.2", "No read", StepKind.WAIT, role=Role.MANAGER), view) is None
    broken = StepDef("w.3", "Broken", StepKind.WAIT, role=Role.MANAGER, check=named_check("entry-day-gap"))
    assert StoreReaders(data).arrival(broken, view) is None                    # no community: an unreadable store is no arrival


def test_outstanding_read_reads_the_followups_for_the_campaigns_of_the_run(data, readers, monkeypatch):
    from jason.tasks import followups

    seed_campaign(data)
    seed_campaign(data, "EM98E", year=2098, return_by="2098-10-23")
    item = lambda code, outstanding, open_=True: SimpleNamespace(open=open_, campaign=code, outstanding=outstanding)   # noqa: E731
    monkeypatch.setattr(followups, "items", lambda d, c, today=None: [item("EM99E", 41), item("EM99E", 41), item("EM98E", 9),
                                                                      item("EM99E", 3, False), item("", None)])
    res = result("outstanding-read", readers)
    assert res.ok and res.message == "3 follow-up item(s) open; 41 owner(s) outstanding"
    monkeypatch.setattr(followups, "items", lambda d, c, today=None: [])
    assert result("outstanding-read", readers).message == "0 follow-up item(s) open; the outstanding count could not be read"
    assert StoreReaders(data, community=None)._community is None


def test_a_child_run_reads_as_its_state(data, readers):
    definitions.reset()
    wf = Workflow("w", "W", "f", "campaign", steps=(one_step(),), dates=(DateSlot("d"),))
    definitions.register(wf)
    rid = api.start(data, "w", "campaign:X", "X", {"d": "2099-01-01"}, OWNER, at=BEGAN, today=TODAY)["run"]["id"]
    assert readers.child_state(rid) == "draft"
    assert readers.child_state("run-nothing") is None
    definitions.reset()
    assert readers.child_state(rid) is None                                      # a definition that is gone cannot be folded


# --- importing -------------------------------------------------------------------------------------------------------

def test_importing_the_readers_loads_no_profile_and_reading_nothing_needs_one():
    code = (
        "import sys, json, tempfile\n"
        "from jason.workflows.readers import StoreReaders\n"
        "r = StoreReaders(tempfile.mkdtemp())\n"
        "r.evidence('file:x'); r.approval('k'); r.job('k')\n"
        "print(json.dumps(sorted(m for m in sys.modules if 'mystique' in m)))\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout.strip().splitlines()[-1]) == []
