"""The approvals: the records and their state machine, the store and its append-only audit log, the engine, the
owner-information kind against a fake PayHOA client (Example Village: four fake owners), and the CLI's dry run.

Nothing here reaches PayHOA: ``FakePayhoa`` holds the units, people, and requests, counts every read, and keeps every
write. The four problems in the owner-information apply the console spec names each have a test: a result for every
write, completion only after the writes were made, one live read, and the profile reached through ``Community``."""

from __future__ import annotations

import argparse
import copy
import inspect
import json
from collections import Counter
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.approvals import audit, engine, model, registry, store
from jason.approvals.engine import Live, Planned, Refused
from jason.approvals.model import ApprovalStatus as S
from jason.approvals.model import Decision, ItemClass, PlanItem, Result
from jason.community.forms import (AnswerCycle, EarlierElections, FormAnswers, FormKey, FormQuestion, FormTemplate,
                                   QuestionKind)
from jason.community.tags import PayhoaTag, TagPurpose, TagScope

FIXTURES = Path(__file__).parent / "fixtures" / "approvals"
SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "jason" / "approvals" / "schemas"
SRC = Path(__file__).resolve().parents[1] / "src" / "jason"

M, U = TagScope.MEMBER, TagScope.UNIT
TAGS = (PayhoaTag("Notices by Email", M, TagPurpose.NOTICE_DELIVERY, "email"),
        PayhoaTag("Notices by Mail", M, TagPurpose.NOTICE_DELIVERY, "mail"),
        PayhoaTag("Owner Info 2027", M, TagPurpose.ANSWERED, "2027"),
        PayhoaTag("Rental", U, TagPurpose.OCCUPANCY, "Rented out", answer="occupancy"),
        PayhoaTag("Owner Occupied", U, TagPurpose.OCCUPANCY, "Owner-occupied", answer="occupancy"))
CYCLE = AnswerCycle(2027, date(2026, 10, 1), return_by=date(2026, 10, 23), reports_mailed=date(2026, 12, 1))
TODAY = date(2026, 10, 10)
FORM = FormTemplate(FormKey.OWNER_INFO, "Owner information", "Civil Code 4041", "A fake form for the tests.", (
    FormQuestion("Delivery", QuestionKind.CHECKBOX, required=False, options=("By email", "By mail"), key="delivery"),
    FormQuestion("Occupancy", QuestionKind.CHOICE, required=False, options=("Owner-occupied", "Rented out"),
                 key="occupancy"),
    FormQuestion("Second mailing address", QuestionKind.SHORT, required=False, key="second-mailing-address")))
FORMS = SimpleNamespace(OWNER_INFO=FORM, OWNER_INFO_CYCLE=CYCLE, EARLIER_ELECTIONS=EarlierElections(apply=False),
                        FORM_IMPORTS=(), OWNER_INFO_COMPLETED_COMMENT="<p>Thank you. Your preferences are recorded.</p>")


class FakeCommunity:
    def payhoa_tags(self):
        return TAGS

    def owner_information(self):
        return FORMS


def _unit(uid, label, members, tags=()):
    return {"id": uid, "label": label, "title": label, "tags": [{"tag": t} for t in tags],
            "owners": [{"membershipId": m, "deletedAt": None} for m in members]}


def _person(pid, name, tags=()):
    given, family = name.split(" ", 1)
    return {"id": pid, "email": "", "tags": [{"tag": t, "id": 9000 + pid} for t in tags],
            "profile": {"givenNames": given, "familyName": family, "updatedAt": "2024-01-14T00:00:00Z"}}


def _answer(sid, mid, uid, **answers):
    return FormAnswers(FormKey.OWNER_INFO, answers, source=f"payhoa:{sid}", submitted="2026-10-05T00:00:00Z",
                       membership_id=mid, unit_id=uid)


class FakePayhoa:
    """Example Village: four units and four fake owners, each with a this-cycle answer in a pending request."""

    def __init__(self, fail_on: str = "") -> None:
        self.units = [_unit(1, "101 EXAMPLE WAY", [10], ["Rental"]), _unit(2, "102 EXAMPLE WAY", [11], ["Owner Occupied"]),
                      _unit(3, "103 EXAMPLE WAY", [12], ["Owner Occupied"]),
                      _unit(4, "104 EXAMPLE WAY", [13], ["Owner Occupied"])]
        self.people = [_person(10, "Ana Example", ["Notices by Email"]), _person(11, "Ben Sample"),
                       _person(12, "Cy Placeholder"), _person(13, "Dee Fictional")]
        self.requests = {
            # says owner-occupied; the unit is tagged a rental: its unit tags are held for the board
            501: _answer(501, 10, 1, delivery=["By mail"], occupancy=["Owner-occupied"]),
            # tags only: completes once they are written
            502: _answer(502, 11, 2, delivery=["By email"], occupancy=["Owner-occupied"]),
            # a second address: a person enters it, so the request stays open
            503: _answer(503, 12, 3, delivery=["By email"], occupancy=["Owner-occupied"],
                         **{"second-mailing-address": "PO Box 12, Example City"}),
            504: _answer(504, 13, 4, delivery=["By email", "By mail"], occupancy=["Owner-occupied"]),
        }
        self.status = {sid: "pending" for sid in self.requests}
        self.reads: Counter[str] = Counter()
        self.writes: list[tuple] = []
        self.fail_on = fail_on
        self._row = 9500

    # reads
    def list_units(self, org, page=1):
        self.reads["list_units"] += 1
        return {"data": copy.deepcopy(self.units), "meta": {"lastPage": 1}}

    def iter_people(self, org):
        self.reads["iter_people"] += 1
        return iter(copy.deepcopy(self.people))

    def list_form_submissions(self, form_id):
        self.reads["list_form_submissions"] += 1
        return [{"id": sid, "status": self.status[sid]} for sid in self.requests]

    def get_form_submission(self, org, sid):
        self.reads["get_form_submission"] += 1
        return {"id": sid}

    # writes
    def _person(self, mid):
        return next(p for p in self.people if p["id"] == mid)

    def update_member_tags(self, org, ids, *, add=(), remove=()):
        if self.fail_on and self.fail_on in add:
            raise RuntimeError(f"PayHOA refused {self.fail_on}")
        self.writes.append(("member", tuple(ids), tuple(add), tuple(remove)))
        for mid in ids:
            p = self._person(mid)
            for tag in add:
                self._row += 1
                p["tags"].append({"tag": tag, "id": self._row})
            p["tags"] = [t for t in p["tags"] if t["id"] not in remove]

    def add_unit_tag(self, org, ids, tag):
        self.writes.append(("unit +", tuple(ids), tag))

    def remove_unit_tag(self, org, ids, tag):
        self.writes.append(("unit -", tuple(ids), tag))

    def set_submission_complete(self, org, sid):
        self.writes.append(("complete", sid))
        self.status[sid] = "complete"

    def add_submission_comment(self, sid, message, *, notify_admins=True, recipient_member_ids=()):
        self.writes.append(("comment", sid, tuple(recipient_member_ids)))


def _fetch(client, org, record, form):
    rows = client.list_form_submissions(int(record["formId"]))
    return [(client.get_form_submission(org, r["id"]), client.requests[r["id"]])[1] for r in rows]


@pytest.fixture
def village(tmp_path, monkeypatch):
    """A fake PayHOA, the profile reached through a fake ``Community``, and the store in ``tmp_path``."""
    (tmp_path / "payhoa").mkdir()
    (tmp_path / "payhoa" / "forms.json").write_text(json.dumps({"forms": [{"key": "owner-info", "formId": 900}]}),
                                                    encoding="utf-8")
    monkeypatch.setattr("jason.tasks.payhoa_forms.fetch_submissions", _fetch)
    monkeypatch.setattr("jason.config.test_memberships", lambda *a, **k: set())
    monkeypatch.setattr("jason.community.community", lambda: FakeCommunity())
    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: tmp_path)
    client = FakePayhoa()
    return SimpleNamespace(client=client, data_dir=tmp_path, live=Live(client, 1, tmp_path, None, TODAY))


def _by(a, klass):
    return [i for i in a.items if i.klass is klass]


def _writes(a, member=None):
    return [i for i in a.approvable if i.op != "complete request" and (member is None or i.target == f"member:{member}")]


def _completion(a, sid):
    return next(i for i in a.items if i.op == "complete request" and i.target == f"submission:{sid}")


# --- the plan -----------------------------------------------------------------------------------------------------------

def test_a_plan_reads_payhoa_once_writes_nothing_and_sorts_every_item(village):
    from jason.tasks.owner_responses import RULES

    a = engine.plan("owner-info-tags", village.live, by="A Manager")
    # one live read: the planner, the response policy, and the fingerprint share it (problem 3)
    assert village.client.reads == {"list_units": 1, "iter_people": 1, "list_form_submissions": 1,
                                    "get_form_submission": 4}
    assert village.client.writes == []
    assert a.status is S.PLANNED and a.kind == "owner-info-tags" and a.requested_by == "A Manager"
    assert len(_writes(a)) == 10 and Counter(i.op for i in _writes(a)) == {"member tag +": 9, "member tag -": 1}
    held = _by(a, ItemClass.HELD_FOR_BOARD)
    board_item = next(r.board_item for r in RULES if r.key == "occupancy-vs-tag")
    assert len(held) == 2 and {i.board_item for i in held} == {board_item}
    assert {i.target for i in held} == {"unit:1"} and all(not i.approvable for i in held)
    person = _by(a, ItemClass.FOR_A_PERSON)
    assert [i.value for i in person] == ["a person enters the secondary delivery"]
    # a request with nothing left but its writes is a completion that waits on them
    done = _completion(a, 502)
    assert set(done.depends_on) == {i.id for i in _writes(a, 11)} and done.approvable
    assert {i.target for i in _by(a, ItemClass.INFORMATIONAL)} == {"submission:501", "submission:503"}
    assert all(len(i.basis) == 64 for i in a.approvable)
    rule = {i.value: i.rule for i in _writes(a, 13)}
    assert "delivery" in rule["Notices by Mail"]
    assert a.summary["writes"] == 10 and a.summary["held"] == 2 and a.clock["due"] == "2026-10-23"
    assert store.load(a.id, village.data_dir).fingerprint == a.fingerprint


def test_the_cli_dry_run_plans_the_same_writes_and_holds(village, capsys):
    """``jason owner-info --apply --payhoa`` and the approvals kind call one planner: the same 10 writes, 2 held."""
    from jason.commands.owner_info import _apply

    args = argparse.Namespace(payhoa=True, yes=False, show=50, env=None, by=None, confirmed_by=None)
    assert _apply(args, _factory(village.client), FakeCommunity(), FORMS, CYCLE, village.data_dir, TODAY) == 0
    out = capsys.readouterr().out
    assert "Dry run (10 writes" in out and out.count("held for the board (occupancy-vs-tag)") == 2
    assert "request 502 (102 EXAMPLE WAY: Ben Sample) stays open: member tag + Notices by Email" in out
    assert village.client.writes == [] and village.client.reads["list_units"] == 1
    a = engine.plan("owner-info-tags", village.live, by="A Manager")
    assert len(_writes(a)) == 10 and len(_by(a, ItemClass.HELD_FOR_BOARD)) == 2


def test_contexts_takes_the_plans_read_and_no_task_imports_a_command():
    src = (SRC / "tasks" / "owner_responses.py").read_text(encoding="utf-8")
    assert "jason.commands" not in src
    assert "jason.commands" not in (SRC / "tasks" / "owner_info_apply.py").read_text(encoding="utf-8")


def test_the_profile_is_reached_through_community_not_mystique_or_spec_module():
    """Problem 4: the apply's code reads the profile's forms through ``Community.owner_information``."""
    from jason.commands import owner_info

    for text in (inspect.getsource(owner_info._apply), inspect.getsource(owner_info._complete_requests),
                 (SRC / "tasks" / "owner_info_apply.py").read_text(encoding="utf-8"),
                 *(p.read_text(encoding="utf-8") for p in (SRC / "approvals").rglob("*.py"))):
        assert "mystique(" not in text and "spec_module(" not in text
    from jason.community.base import Community

    assert Community.owner_information(None) is None       # a miss, not a crash


def test_a_planning_client_refuses_to_write():
    from jason.tasks.owner_info_apply import ReadOnce, WriteRefused

    reader = ReadOnce(FakePayhoa())
    with pytest.raises(WriteRefused):
        reader.update_member_tags(1, [10], add=["x"])
    reader.list_units(1, page=1)
    reader.list_units(1, page=1)
    assert reader._client.reads["list_units"] == 1


# --- decide -------------------------------------------------------------------------------------------------------------

def test_decide_needs_a_name_refuses_held_items_and_records_a_partial_review(village):
    a = engine.plan("owner-info-tags", village.live, by="A Manager")
    ben = [i.id for i in _writes(a, 11)]
    with pytest.raises(Refused, match="names the person"):
        engine.decide(a.id, ben, by="  ", data_dir=village.data_dir)
    held = _by(a, ItemClass.HELD_FOR_BOARD)[0]
    with pytest.raises(Refused, match="held for the board"):
        engine.decide(a.id, [held.id], by="A Manager", data_dir=village.data_dir)
    with pytest.raises(Refused, match="never approvable"):
        engine.decide(a.id, [_by(a, ItemClass.FOR_A_PERSON)[0].id], by="A Manager", data_dir=village.data_dir)
    with pytest.raises(Refused, match="says why"):
        engine.decide(a.id, ben, by="A Manager", decision=Decision.HELD, data_dir=village.data_dir)
    after = engine.decide(a.id, [i[:8] for i in ben], by="A Manager", data_dir=village.data_dir)   # a unique prefix
    assert after.status is S.IN_REVIEW and {i.id for i in after.approved} == set(ben)
    assert after.decisions[-1].by == "A Manager" and after.decisions[-1].fingerprint == a.fingerprint
    with pytest.raises(Refused, match="undecided"):
        engine.submit(a.id, by="A Manager", data_dir=village.data_dir)
    assert store.load(a.id, village.data_dir).status is S.IN_REVIEW


def test_a_completion_waits_on_its_writes(village):
    a = engine.plan("owner-info-tags", village.live, by="A Manager")
    done = _completion(a, 502)
    with pytest.raises(Refused, match="waits on"):
        engine.decide(a.id, [done.id], by="A Manager", data_dir=village.data_dir)
    engine.decide(a.id, [*done.depends_on, done.id], by="A Manager", data_dir=village.data_dir)
    after = engine.decide(a.id, [done.depends_on[0]], by="A Manager", decision=Decision.REJECTED,
                          reason="the owner called: wants mail", data_dir=village.data_dir)
    assert after.item(done.id).decision is Decision.UNDECIDED          # its write is out: it stays open


def _approve_partly(village):
    """Ben's and Dee's writes and requests approved; Ana's and Cy's writes rejected."""
    a = engine.plan("owner-info-tags", village.live, by="A Manager")
    keep = [i.id for i in _writes(a, 11) + _writes(a, 13)] + [_completion(a, 502).id, _completion(a, 504).id]
    engine.decide(a.id, keep, by="A Manager", data_dir=village.data_dir)
    rest = [i.id for i in a.approvable if i.id not in keep]
    engine.decide(a.id, rest, by="A Manager", decision=Decision.REJECTED, reason="next week",
                  data_dir=village.data_dir)
    return engine.submit(a.id, by="A Manager", data_dir=village.data_dir)


# --- apply --------------------------------------------------------------------------------------------------------------

def test_apply_with_nothing_changed_writes_only_the_approved_items(village):
    a = _approve_partly(village)
    assert a.status is S.PARTIALLY_APPROVED and a.first.name == "A Manager"
    done = engine.apply(a.id, village.live, by="A Manager")
    assert done.superseded_by is None and done.approval.status is S.APPLIED
    members = {m for w in village.client.writes if w[0] == "member" for m in w[1]}
    assert members == {11, 13}                                         # Ana's and Cy's writes were rejected
    assert not any(w[0].startswith("unit") for w in village.client.writes)        # held for the board: never written
    assert ("complete", 502) in village.client.writes and ("complete", 504) in village.client.writes
    assert ("comment", 502, (11,)) in village.client.writes
    assert {sid for _, sid, *rest in [w for w in village.client.writes if w[0] == "complete"]} == {502, 504}
    stored = store.load(a.id, village.data_dir)
    assert all(i.result is Result.APPLIED for i in stored.approved)
    assert all(i.result is Result.NOT_APPLIED for i in stored.items if i not in stored.approved)
    events = [e["event"] for e in audit.read(village.data_dir, a.id)]
    assert events.index("item.applying") < events.index("item.applied") and events[-1] == "approval.applied"


def test_a_failed_write_keeps_its_request_open_and_each_write_has_a_result(village):
    """Problems 1 and 2: every write has its own result, and a request completes only after its writes were made."""
    village.client.fail_on = "Notices by Mail"
    a = _approve_partly(village)
    done = engine.apply(a.id, village.live, by="A Manager")
    stored = done.approval
    assert stored.status is S.FAILED
    dee_mail = next(i for i in _writes(stored, 13) if i.value == "Notices by Mail")
    assert dee_mail.result is Result.FAILED and "refused" in dee_mail.result_detail
    assert _completion(stored, 504).result is Result.BLOCKED          # its write was not made: it stays open
    assert ("complete", 504) not in village.client.writes
    assert {i.result for i in _writes(stored, 11)} == {Result.APPLIED}
    results = {e.get("item"): e["event"] for e in audit.read(village.data_dir, a.id) if e.get("item")}
    assert results[dee_mail.id] == "item.failed" and results[_completion(stored, 504).id] == "item.blocked"


def test_apply_after_a_live_change_supersedes_and_writes_nothing(village):
    a = _approve_partly(village)
    village.client._person(11)["tags"].append({"tag": "Notices by Mail", "id": 7777})    # changed since review
    done = engine.apply(a.id, village.live, by="A Manager")
    assert village.client.writes == []
    assert done.approval.status is S.SUPERSEDED and done.superseded_by is not None
    assert {c.id for c in done.changed} >= {i.id for i in _writes(a, 11)}
    fresh = store.load(done.superseded_by.id, village.data_dir)
    assert fresh.status is S.PLANNED and fresh.supersedes == a.id
    assert all(i.decision is Decision.UNDECIDED for i in fresh.items)          # earlier decisions are hints only
    assert any("earlier by A Manager" in n for n in fresh.notes)
    refused = [e for e in audit.read(village.data_dir, a.id) if e["event"] == "apply.refused"]
    assert refused and refused[0]["detail"] == "changed since review"


def test_a_newer_plan_supersedes_an_open_one(village):
    first = engine.plan("owner-info-tags", village.live, by="A Manager")
    second = engine.plan("owner-info-tags", village.live, by="A Manager")
    old = store.load(first.id, village.data_dir)
    assert old.status is S.SUPERSEDED and old.superseded_by == second.id
    assert first.fingerprint == second.fingerprint                    # the same live state, the same fingerprint


# --- the second person ----------------------------------------------------------------------------------------------------

class _Tags:
    """A fake PayHOA with member tags only, for a generic kind."""

    def __init__(self):
        self.tags = {1: ["A"], 2: []}
        self.writes = []


def _fake_plan(live, scope):
    client = live.client
    items = []
    for mid, value, stakes in ((1, "B", False), (2, "C", True)):
        items.append(PlanItem(model.item_id("fake-tags", "tag +", f"member:{mid}", value), "tag +", f"member:{mid}",
                              f"member {mid}", value, "a test", basis=model.digest(sorted(client.tags[mid])),
                              high_stakes=stakes))
    return Planned(items, scope={"test": True})


def _fake_apply(live, planned, items, recorder):
    for i in items:
        recorder.applying([i.id])
        live.client.writes.append((i.target, i.value))
        recorder.done(i.id, Result.APPLIED, "written")


@pytest.fixture
def fake_kind():
    from jason.locks import Resource

    kind = registry.register(registry.ActionKind(
        "fake-tags", "Fake tags", "none", "fake", Resource.STORE, registry.Risk.R2, registry.Approver.ONE_PERSON,
        "yes", _fake_plan, _fake_apply))
    yield kind
    registry.unregister("fake-tags")


def test_a_high_stakes_item_needs_a_second_distinct_person(tmp_path, fake_kind):
    client = _Tags()
    live = Live(client, 1, tmp_path)
    a = engine.plan("fake-tags", live, by="A Manager")
    engine.decide(a.id, "all", by="A Manager", data_dir=tmp_path)
    a = engine.submit(a.id, by="A Manager", data_dir=tmp_path)
    assert a.status is S.APPROVED and engine.needs_second(a)
    with pytest.raises(Refused, match="second, distinct person"):
        engine.apply(a.id, live, by="A Manager")
    with pytest.raises(Refused, match="submitted it"):
        engine.confirm(a.id, by=" a manager ", data_dir=tmp_path)            # the same name, trimmed and folded
    engine.confirm(a.id, by="B Treasurer", data_dir=tmp_path)
    done = engine.apply(a.id, live, by="A Manager")
    assert done.approval.status is S.APPLIED and client.writes == [("member:1", "B"), ("member:2", "C")]
    assert done.approval.second.name == "B Treasurer"


def test_a_second_person_who_declines_sends_it_back_to_review(tmp_path, fake_kind):
    live = Live(_Tags(), 1, tmp_path)
    a = engine.plan("fake-tags", live, by="A Manager")
    engine.decide(a.id, "all", by="A Manager", data_dir=tmp_path)
    engine.submit(a.id, by="A Manager", data_dir=tmp_path)
    back = engine.decline(a.id, by="B Treasurer", reason="C is not for this cycle", data_dir=tmp_path)
    assert back.status is S.IN_REVIEW and back.first is None


# --- the state machine ------------------------------------------------------------------------------------------------

def test_the_state_machine_allows_only_the_table():
    T = model.TRANSITIONS
    assert all(not T[s] for s in model.TERMINAL)
    assert T[S.PLANNED] == {S.IN_REVIEW, S.SUPERSEDED, S.WITHDRAWN}
    assert S.APPLYING in T[S.APPROVED] and S.APPLYING in T[S.PARTIALLY_APPROVED]
    assert S.APPLYING not in T[S.IN_REVIEW] and S.APPLIED not in T[S.APPROVED]
    assert T[S.APPLYING] == {S.APPLIED, S.FAILED, S.SUPERSEDED}
    a = model.Approval("apr-x", "k", "t", [], "f" * 64, "", "A", "")
    for step in (S.IN_REVIEW, S.APPROVED, S.APPLYING, S.APPLIED):
        model.transition(a, step)
    with pytest.raises(model.TransitionError):
        model.transition(a, S.WITHDRAWN)                                  # nothing leaves a terminal state
    b = model.Approval("apr-y", "k", "t", [], "f" * 64, "", "A", "")
    with pytest.raises(model.TransitionError):
        model.transition(b, S.APPLYING)                                   # never applied without a review


def test_nothing_approved_withdraws_it(tmp_path, fake_kind):
    live = Live(_Tags(), 1, tmp_path)
    a = engine.plan("fake-tags", live, by="A Manager")
    engine.decide(a.id, "all", by="A Manager", decision=Decision.REJECTED, reason="not now", data_dir=tmp_path)
    assert engine.submit(a.id, by="A Manager", data_dir=tmp_path).status is S.WITHDRAWN


# --- the store and the audit log ----------------------------------------------------------------------------------------

def test_the_store_is_in_the_profiles_data_folder(tmp_path, monkeypatch):
    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: tmp_path / "profile")
    assert store.store_dir() == tmp_path / "profile" / "approvals"
    assert audit.path() == tmp_path / "profile" / "approvals" / "audit.jsonl"
    from test_profile_data import _data_literals

    for path in (SRC / "approvals").rglob("*.py"):
        assert _data_literals(path.read_text(encoding="utf-8")) == 0, path


def test_the_audit_log_is_append_only_chained_and_holds_no_email(tmp_path, fake_kind):
    live = Live(_Tags(), 1, tmp_path)
    a = engine.plan("fake-tags", live, by="A Manager")
    before = audit.path(tmp_path).read_bytes()
    engine.decide(a.id, "all", by="A Manager", data_dir=tmp_path)
    audit.append(tmp_path, "item.failed", approval=a.id, detail="bounced from someone@example.com")
    after = audit.path(tmp_path).read_bytes()
    assert after.startswith(before)                                    # earlier lines are never rewritten
    assert audit.verify(tmp_path)[0]
    assert "@" not in after.decode("utf-8")
    lines = after.decode("utf-8").splitlines()
    seqs = [json.loads(line)["seq"] for line in lines]
    assert seqs == list(range(1, len(lines) + 1))
    tampered = json.loads(lines[1])
    tampered["actor"] = "Someone Else"
    lines[1] = model.canonical(tampered)
    audit.path(tmp_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok, line, why = audit.verify(tmp_path)
    assert not ok and line == 2


def test_the_cli_yes_is_audited_and_a_failure_completes_nothing(village):
    """The CLI keeps its behavior; a --yes is in the audit log, and a failed write leaves every request open."""
    from jason.commands.owner_info import _apply

    village.client.fail_on = "Notices by Mail"
    args = argparse.Namespace(payhoa=True, yes=True, show=5, env=None, by="A Manager", confirmed_by=None)
    with pytest.raises(RuntimeError, match="refused"):
        _apply(args, _factory(village.client), FakeCommunity(), FORMS, CYCLE, village.data_dir, TODAY)
    assert not any(w[0] == "complete" for w in village.client.writes)
    events = Counter(e["event"] for e in audit.read(village.data_dir))
    assert events["item.failed"] >= 1 and events["cli.applied"] == 1
    assert all(e.get("actor") == "A Manager" for e in audit.read(village.data_dir))


def test_the_cli_yes_writes_and_completes_as_today(village, capsys):
    from jason.commands.owner_info import _apply

    args = argparse.Namespace(payhoa=True, yes=True, show=5, env=None, by=None, confirmed_by="A Manager")
    assert _apply(args, _factory(village.client), FakeCommunity(), FORMS, CYCLE, village.data_dir, TODAY) == 0
    out = capsys.readouterr().out
    assert "written: member tag + 9, member tag - 1" in out
    assert {w[1] for w in village.client.writes if w[0] == "complete"} == {502, 504}
    assert not any(w[0].startswith("unit") for w in village.client.writes)
    assert audit.read(village.data_dir)[-1]["event"] == "cli.applied" and audit.verify(village.data_dir)[0]


# --- the CLI and MCP ----------------------------------------------------------------------------------------------------

@contextmanager
def _agent(client):
    yield SimpleNamespace(payhoa=lambda: client, org_id=1)


def _factory(client):
    return lambda args: _agent(client)


def _cli(client, *argv):
    from jason.commands.approvals import register

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    register(sub, lambda p: p.add_argument("--env"), _factory(client))
    args = parser.parse_args(["approvals", *argv])
    return args.func(args)


def test_the_cli_plans_shows_decides_and_dry_runs_an_apply(village, capsys):
    assert _cli(village.client, "plan", "owner-info-tags", "--by", "A Manager") == 0
    a = store.load_all(village.data_dir)[0]
    out = capsys.readouterr().out
    assert "Held for the board (never approvable) (2)" in out and "nothing written outside jason" in out
    ben = [i.id for i in _writes(a, 11)]
    assert _cli(village.client, "decide", a.id, "--items", *ben, "--by", "A Manager") == 0
    assert _cli(village.client, "decide", a.id, "--items", _by(a, ItemClass.HELD_FOR_BOARD)[0].id,
                "--by", "A Manager") == 2
    rest = [i.id for i in a.approvable if i.id not in ben]
    assert _cli(village.client, "decide", a.id, "--items", *rest, "--reject", "--reason", "later", "--by", "A") == 0
    assert _cli(village.client, "submit", a.id, "--by", "A Manager") == 0
    capsys.readouterr()
    assert _cli(village.client, "apply", a.id) == 0                   # no --yes: a dry run
    out = capsys.readouterr().out
    assert "unchanged" in out and "Dry run" in out and "member tag +" in out
    assert village.client.writes == [] and store.load(a.id, village.data_dir).status is S.PARTIALLY_APPROVED
    village.client._person(11)["tags"].append({"tag": "Notices by Mail", "id": 7777})
    assert _cli(village.client, "apply", a.id) == 1                   # the dry run says it changed, and changes nothing
    assert "changed since review" in capsys.readouterr().out
    assert store.load(a.id, village.data_dir).status is S.PARTIALLY_APPROVED and village.client.writes == []
    assert _cli(village.client, "audit", "--verify") == 0
    capsys.readouterr()
    assert _cli(village.client, "show", a.id, "--json") == 0
    assert json.loads(capsys.readouterr().out)["id"] == a.id


def test_mcp_reads_approvals_and_offers_no_way_to_decide_or_apply(village):
    from jason.mcp import governance

    a = engine.plan("owner-info-tags", village.live, by="A Manager")
    listed = governance.approvals_list(data_dir=village.data_dir)
    assert listed["approvals"][0]["id"] == a.id and "Read only" in listed["caveat"]
    shown = governance.approval_show(a.id[:12], data_dir=village.data_dir)
    assert shown["status"] == "planned" and shown["audit"][0]["event"] == "plan.created"
    names = {t.__name__ for t in governance.TOOLS}
    assert not any(n.startswith(("approval_", "approvals_")) and n not in ("approvals_list", "approval_show")
                   for n in names)
    assert not any(word in n for n in names if "approv" in n for word in ("decide", "apply", "submit", "confirm"))


# --- the contracts ------------------------------------------------------------------------------------------------------

def _validator(name):
    jsonschema = pytest.importorskip("jsonschema")
    referencing = pytest.importorskip("referencing")
    schemas = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in SCHEMAS.glob("*.json")}
    reg = referencing.Registry().with_resources(
        [(s["$id"], referencing.Resource.from_contents(s)) for s in schemas.values()])
    return jsonschema.Draft202012Validator(schemas[name], registry=reg)


def test_a_plan_and_its_audit_match_the_schemas(village):
    a = _approve_partly(village)
    engine.apply(a.id, village.live, by="A Manager")
    _validator("approval.schema.json").validate(model.to_dict(store.load(a.id, village.data_dir)))
    entries = _validator("audit-entry.schema.json")
    for e in audit.read(village.data_dir):
        entries.validate(e)
    assert model.from_dict(model.to_dict(a)) == a                      # the JSON round-trips


def test_the_example_village_fixture_matches_the_schemas():
    """tests/fixtures/approvals: a fake plan (Example Village: four fake owners, ten writes, two held for the board,
    one for a person), the same approval after a partial approval and an apply, and its audit log."""
    planned = json.loads((FIXTURES / "example-village-planned.json").read_text(encoding="utf-8"))
    applied = json.loads((FIXTURES / "example-village-applied.json").read_text(encoding="utf-8"))
    for doc in (planned, applied):
        _validator("approval.schema.json").validate(doc)
        model.from_dict(doc)
    classes = Counter(i["class"] for i in planned["items"])
    writes = [i for i in planned["items"] if i["class"] == "approvable" and i["op"] != "complete request"]
    assert len(writes) == 10 and classes["held_for_board"] == 2 and classes["for_a_person"] == 1
    assert planned["profile"] == "example-village" and applied["status"] == "applied"
    entries = _validator("audit-entry.schema.json")
    for line in (FIXTURES / "example-village-audit.jsonl").read_text(encoding="utf-8").splitlines():
        entries.validate(json.loads(line))


def write_example(out: Path, tmp: Path, monkeypatch) -> None:
    """Regenerate tests/fixtures/approvals from Example Village, by hand:
    ``python -c "import sys; sys.path.insert(0, 'tests'); import test_approvals as t; t.regenerate()"``."""
    village_setup(monkeypatch, tmp)
    monkeypatch.setattr("jason.approvals.engine._profile", lambda: "example-village")
    monkeypatch.setattr("jason.approvals.audit.os_actor", lambda: "os:manager")
    (tmp / "payhoa").mkdir(exist_ok=True)
    (tmp / "payhoa" / "forms.json").write_text(json.dumps({"forms": [{"key": "owner-info", "formId": 900}]}),
                                               encoding="utf-8")
    client = FakePayhoa()
    village = SimpleNamespace(client=client, data_dir=tmp, live=Live(client, 1, tmp, None, TODAY))
    a = engine.plan("owner-info-tags", village.live, by="A Manager")
    out.mkdir(parents=True, exist_ok=True)
    (out / "example-village-planned.json").write_text(json.dumps(model.to_dict(a), indent=1) + "\n", encoding="utf-8")
    store.save(a, tmp)
    b = _approve_partly(village)
    engine.apply(b.id, village.live, by="A Manager")
    (out / "example-village-applied.json").write_text(
        json.dumps(model.to_dict(store.load(b.id, tmp)), indent=1) + "\n", encoding="utf-8")
    (out / "example-village-audit.jsonl").write_text(audit.path(tmp).read_text(encoding="utf-8"), encoding="utf-8")


def village_setup(monkeypatch, tmp_path):
    monkeypatch.setattr("jason.tasks.payhoa_forms.fetch_submissions", _fetch)
    monkeypatch.setattr("jason.config.test_memberships", lambda *a, **k: set())
    monkeypatch.setattr("jason.community.community", lambda: FakeCommunity())
    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: tmp_path)


def regenerate() -> None:                                   # pragma: no cover - by hand
    import tempfile

    os_env = __import__("os").environ
    os_env.setdefault("JASON_LOCK_DIR", tempfile.mkdtemp())
    with pytest.MonkeyPatch.context() as mp, tempfile.TemporaryDirectory() as tmp:
        write_example(FIXTURES, Path(tmp), mp)
