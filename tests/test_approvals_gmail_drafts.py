"""The approvals kind ``gmail-drafts``: a prepared email saved as a Gmail draft, never sent.

Made-up data only (Example Village HOA, 1234 Example Way, example.org addresses) in tmp_path. ``FakeDrive`` is a Google
Drive stand-in whose HTTP client records every request and fails the test on any path with ``/send``; it has no send
method at all. The composers' data sources (the inspection record, the vendor directory, the saved hearing, the agenda
file) are made up, and the community is a stand-in whose name is the association's."""

from __future__ import annotations

import base64
import email
import json
from contextlib import contextmanager
from datetime import date
from email import policy
from types import SimpleNamespace

import httpx
import pytest

from jason.approvals import engine, registry, store
from jason.approvals.engine import Live
from jason.approvals.kinds import gmail_drafts as kind
from jason.approvals.model import ApprovalStatus as S
from jason.approvals.model import Result
from jason.tasks import drafts, proposal_request as pr
from jason.tasks.inspections import Coverage, Period

KEY = "gmail-drafts"
DAY = date(2026, 10, 7)
ASSOCIATION = "Example Village HOA"
TO = "office@example.org"
HEARING = {
    "address": "1234 Example Way", "building": "2", "start": "2026-10-27T19:00", "timezone": "America/Los_Angeles",
    "noticeBy": "2026-10-17", "zoom": {"id": 1, "joinUrl": "https://zoom.us/j/1", "passcode": "abc123", "dialIn": []},
    "noticeDoc": {"id": "DOC1", "url": "https://docs.google.com/document/d/DOC1/edit", "unfilled": []},
}
AGENDA = ("# DRAFT Agenda for 10/20/26\n\n_Notice with this agenda must go out by Friday, October 16 (CIV 4920(a))._\n\n"
          "1. **Call to Order**\n")


class FakeDocs:
    def __init__(self):
        self.exports: list[tuple[str, str]] = []

    def export_pdf(self, doc_id, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"%PDF-1.4 fake")
        self.exports.append((doc_id, dest.name))
        return dest


class FakeDrive:
    """What ``GmailDrafts.on`` takes (a token and an HTTP client), recording each request. No send method exists, and a
    request to a send path fails the test."""

    def __init__(self, answer=None):
        self.requests: list[httpx.Request] = []
        self.answer = answer or (lambda r: httpx.Response(200, json={"id": f"draft-{len(self.requests)}"}))
        self._token = "tok"
        self._http = httpx.Client(transport=httpx.MockTransport(self._handle))
        self._docs = FakeDocs()

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert "/send" not in request.url.path, "a request reached a send endpoint"
        return self.answer(request)

    def docs(self):
        return self._docs

    @property
    def drafts(self):
        return [r for r in self.requests if r.method == "POST" and r.url.path == "/gmail/v1/users/me/drafts"]

    def parsed(self, request=None):
        request = request or self.drafts[-1]
        raw = json.loads(request.content)["message"]["raw"]
        return email.message_from_bytes(base64.urlsafe_b64decode(raw), policy=policy.default)


def _row(name, authority, months=12):
    return SimpleNamespace(name=name, authority=authority, months=months, fixed=False,
                           cadence=lambda: f"every {months} months" if months != 12 else "every 1 year")


ANNUAL = _row("Annual inspection and test", "19 CCR 904 (NFPA 25), form AES 2.1")


def _records(servicer="Example Fire Protection, Inc."):
    system = SimpleNamespace(key="sprinklers-a", name="Fire sprinklers, building A", serves_label="building A",
                             servicer=servicer)
    ob = SimpleNamespace(row=ANNUAL, calendar={"next": "2024-03-14", "standing": "overdue", "lastDone": "2023-03-14"},
                         periods=(), counted_from=date(2023, 3, 14), earlier=())
    return SimpleNamespace(as_of=DAY, community=ASSOCIATION,
                           systems=(SimpleNamespace(system=system, obligations=(ob,), not_read=()),))


DIRECTORY = {"vendors": [{"vendor": "Example Fire Protection, Inc.", "sender": "Example Fire Protection, Inc.",
                          "onFile": {"email": "office@example.org", "contactName": ""},
                          "people": [{"address": "pat@example.org", "names": ["Pat Example"], "last": "2025-06-18",
                                      "wroteUs": 3}]}]}


@pytest.fixture
def world(tmp_path, monkeypatch):
    (tmp_path / "zoom").mkdir()
    (tmp_path / "zoom" / "hearings.json").write_text(json.dumps({"hearings": [HEARING]}), encoding="utf-8")
    (tmp_path / "board").mkdir()
    (tmp_path / "board" / "agenda-2026-10-20.md").write_text(AGENDA, encoding="utf-8")
    monkeypatch.setattr("jason.community.community", lambda *a, **k: SimpleNamespace(name=ASSOCIATION))
    monkeypatch.setattr("jason.tasks.inspections.review", lambda data_dir, community, **k: _records())
    monkeypatch.setattr("jason.tasks.contacts.directory", lambda data_dir, community, **k: DIRECTORY)
    drive = FakeDrive()
    live = Live(drive, 0, tmp_path, None, DAY)
    return SimpleNamespace(drive=drive, live=live, data_dir=tmp_path)


def scope(case="proposal-request", **kw):
    key = {"proposal-request": "sprinklers-a", "hearing": "1234 Example Way", "meeting-notice": "2026-10-20"}[case]
    return {"case": case, "key": key, **kw}


def approve(world, a, by="A Manager"):
    engine.decide(a.id, "all", by=by, data_dir=world.data_dir)
    return engine.submit(a.id, by=by, data_dir=world.data_dir)


class Recorder:
    def __init__(self):
        self.done_calls, self.started = {}, []

    def applying(self, ids):
        self.started += list(ids)

    def done(self, ident, result, detail=""):
        self.done_calls[ident] = (result, detail)


# --- the row ------------------------------------------------------------------------------------------------------------

def test_the_kind_is_registered_with_its_alias_and_its_declared_facts():
    k = registry.get(KEY)
    assert registry.get("google.gmail-drafts") is k
    assert k.cli == "jason draft --yes" and k.system == "google" and k.max_age_hours == 6
    assert k.risk is registry.Risk.R1 and k.approver is registry.Approver.ONE_PERSON
    assert "nothing is sent" in k.reversible and k.rule == kind.RULE
    from jason.locks import Resource

    assert k.resource is Resource.GOOGLE


def test_the_web_routes_list_it_with_no_other_wiring():
    from jason.web import approvals

    assert KEY in {k["key"] for k in approvals.kinds()["kinds"]}


def test_the_rule_is_an_address_the_approvals_screen_recites_with_no_statutes_shelf():
    from jason.web import approvals

    whole = approvals.recite(registry.get(KEY).rule)
    assert whole["found"], whole
    for case in kind.CASES:
        one = approvals.recite(f"gmail_drafts.CASES: {case.key}")
        assert one["found"] and one["kind"] == "row" and case.composer in one["text"], one
        assert "never" in one["text"]


def test_the_fake_has_no_send_method_and_neither_has_the_drafts_client():
    from jason.google.gmail_drafts import GmailDrafts

    assert not [n for n in dir(FakeDrive) if "send" in n.lower()]
    assert not [n for n in dir(GmailDrafts) if "send" in n.lower()]


# --- the scope ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["office", "a b@example.org", "office@example.org\nBcc: x@example.org",
                                 "Office <office@example.org>", "a@example.org,b@example.org", "a@b", "@example.org",
                                 "a@@example.org", "a@example.org;b@example.org"])
def test_an_address_that_is_not_one_plain_address_is_refused(world, bad):
    with pytest.raises(ValueError, match="not an email address"):
        engine.plan(KEY, world.live, by="A Manager", scope=scope(to=[bad]))
    with pytest.raises(ValueError, match="cc"):
        engine.plan(KEY, world.live, by="A Manager", scope=scope(to=[TO], cc=[bad]))
    assert world.drive.requests == [] and store.load_all(world.data_dir) == []


def test_a_bad_case_key_date_or_pdf_is_refused(world):
    for bad in ({"case": "send-it", "key": "x"}, {"case": "hearing", "key": ""}, scope("meeting-notice") | {"key": "soon"},
                scope("meeting-notice", pdf=True), scope(signer="a\nb"), scope(horizon=0)):
        with pytest.raises(ValueError):
            engine.plan(KEY, world.live, by="A Manager", scope={**bad, "to": [TO]})


def test_a_system_hearing_or_agenda_that_does_not_exist_is_refused(world):
    with pytest.raises(LookupError, match="no system 'nope'.*sprinklers-a"):
        engine.plan(KEY, world.live, by="A Manager", scope={**scope(), "key": "nope", "to": [TO]})
    with pytest.raises(LookupError, match="no saved hearing"):
        engine.plan(KEY, world.live, by="A Manager", scope={**scope("hearing"), "key": "9 Nowhere Ln", "to": [TO]})
    with pytest.raises(FileNotFoundError):
        engine.plan(KEY, world.live, by="A Manager", scope={**scope("meeting-notice"), "key": "2026-11-17", "to": [TO]})


# --- the plan -----------------------------------------------------------------------------------------------------------

def test_a_plan_with_no_recipient_has_no_item_and_lists_the_suggested_addresses(world):
    a = engine.plan(KEY, world.live, by="A Manager", scope=scope())
    assert a.items == [] and a.scope["to"] == []
    notes = "\n".join(a.notes)
    assert "No recipient chosen" in notes and "never picks" in notes
    assert "office@example.org: the contact on file in PayHOA" in notes and "pat@example.org (Pat Example)" in notes
    assert "Request for proposal and reports: Fire sprinklers, building A" in notes
    assert world.drive.requests == []


@pytest.mark.parametrize("case", ["hearing", "meeting-notice"])
def test_the_other_cases_without_a_recipient_have_no_item_either(world, case):
    a = engine.plan(KEY, world.live, by="A Manager", scope=scope(case))
    assert a.items == [] and "No recipient chosen" in "\n".join(a.notes)


def test_a_plan_with_a_recipient_has_one_item_that_matches_what_jason_draft_prints(world):
    a = engine.plan(KEY, world.live, by="A Manager", scope=scope(to=[TO, "second@example.org"], cc=["board@example.org"]))
    [item] = a.items
    assert a.status is S.PLANNED and item.approvable and item.op == kind.OP and len(item.basis) == 64
    # the same functions `jason draft --proposal-request` calls
    request = pr.request_for(_records(), "sprinklers-a", horizon=120)
    expected = pr.draft(request, TO, agreements=[], waiting=[])
    assert item.label == expected.message.subject
    assert f"To: {TO}, second@example.org" in item.value and "Cc: board@example.org" in item.value
    assert f"Subject: {expected.message.subject}" in item.value
    for line in expected.message.text.splitlines():
        assert line in item.value.splitlines()
    for reminder in expected.reminders:
        assert f"Reminder: {reminder}" in a.notes
    assert item.rule == "gmail_drafts.CASES: proposal-request" and item.change.text() == "+ 1 draft (Gmail drafts)"
    assert "sends nothing" in item.why and any("not sent" in n for n in a.notes)
    assert a.scope == {"case": "proposal-request", "key": "sprinklers-a", "to": [TO, "second@example.org"],
                       "cc": ["board@example.org"], "signer": "", "horizon": 120, "pdf": False}


def test_planning_creates_nothing(world):
    for case in ("proposal-request", "hearing", "meeting-notice"):
        engine.plan(KEY, world.live, by="A Manager", scope=scope(case, to=[TO]))
    assert world.drive.requests == [] and world.drive.docs().exports == []


def test_a_hearing_names_its_unit_in_a_note_and_withholds_the_passcode_line_from_the_record(world):
    a = engine.plan(KEY, world.live, by="A Manager", scope=scope("hearing", to=[TO]))
    [item] = a.items
    assert "1234 Example Way" in item.value and "https://zoom.us/j/1" in item.value
    assert "abc123" not in item.value and kind.WITHHELD in item.value
    assert any("body names a unit" in n and "recipient you chose" in n for n in a.notes)
    assert "abc123" not in json.dumps(store.load(a.id, world.data_dir).__dict__, default=str)


def test_a_statute_cited_in_the_body_is_kept_in_the_record_and_another_code_is_withheld():
    from jason.community.intake import secret_reason
    from jason.google.gmail_drafts import DraftMessage

    text = "Notice under Civil Code 5855 and Government Code 12950.\nMeeting Code 123456\nPIN: 4821"
    shown = kind.preview(DraftMessage(to=(TO,), subject="s", text=text))
    assert "Civil Code § 5855 and Government Code § 12950" in shown
    assert "123456" not in shown and "4821" not in shown and shown.count(kind.WITHHELD) == 2
    assert not secret_reason(shown)


def test_the_same_email_is_the_same_item_on_every_plan_and_another_recipient_is_another_item(world):
    first = engine.plan(KEY, world.live, by="A Manager", scope=scope(to=[TO]))
    second = engine.plan(KEY, world.live, by="A Manager", scope=scope(to=[TO]))
    assert [(i.id, i.basis) for i in first.items] == [(i.id, i.basis) for i in second.items]
    assert store.load(first.id, world.data_dir).status is S.SUPERSEDED
    other = engine.plan(KEY, world.live, by="A Manager", scope=scope(to=["other@example.org"]))
    assert other.items[0].id != first.items[0].id


def test_a_changed_body_is_a_changed_basis(world, monkeypatch):
    before = engine.plan(KEY, world.live, by="A Manager", scope=scope(to=[TO])).items[0]
    (world.data_dir / "board" / "agenda-2026-10-20.md").write_text(AGENDA + "2. **Adjournment**\n", encoding="utf-8")
    a = engine.plan(KEY, world.live, by="A Manager", scope=scope("meeting-notice", to=[TO]))
    b = engine.plan(KEY, world.live, by="A Manager", scope=scope("meeting-notice", to=[TO]))
    assert a.items[0].basis == b.items[0].basis != before.basis
    (world.data_dir / "board" / "agenda-2026-10-20.md").write_text(AGENDA + "2. **New business**\n", encoding="utf-8")
    c = engine.plan(KEY, world.live, by="A Manager", scope=scope("meeting-notice", to=[TO]))
    assert c.items[0].basis != b.items[0].basis


# --- apply --------------------------------------------------------------------------------------------------------------

def _plain(parsed):
    return parsed.get_body(("plain",)).get_content().rstrip("\n")


@pytest.mark.parametrize("case", ["proposal-request", "hearing", "meeting-notice"])
def test_apply_creates_exactly_one_draft_with_the_planned_recipients_subject_and_body(world, case):
    a = engine.plan(KEY, world.live, by="A Manager", scope=scope(case, to=[TO, "second@example.org"],
                                                                 cc=["board@example.org"]))
    item = a.items[0]
    a = approve(world, a)
    done = engine.apply(a.id, world.live, by="A Manager")
    assert done.superseded_by is None and done.approval.status is S.APPLIED
    [request] = world.drive.drafts
    assert len(world.drive.requests) == 1 and request.url.path == "/gmail/v1/users/me/drafts"
    parsed = world.drive.parsed(request)
    assert parsed["To"] == f"{TO}, second@example.org" and parsed["Cc"] == "board@example.org"
    assert parsed["Subject"] == item.label
    # the planned body, whole (a passcode line withheld from the record is in the draft)
    composed = kind.compose(kind.parse_scope(store.load(a.id, world.data_dir).scope), world.live)
    assert _plain(parsed) == composed.plan.message.text.rstrip("\n")
    if case == "hearing":
        assert "Passcode: abc123" in _plain(parsed)
    stored = store.load(a.id, world.data_dir).items[0]
    assert stored.result is Result.APPLIED
    assert stored.result_detail == "saved as Gmail draft draft-1; review it and send it from Gmail"


def test_a_hearing_pdf_is_exported_at_plan_and_apply_and_attached_by_name(world):
    a = engine.plan(KEY, world.live, by="A Manager", scope=scope("hearing", to=[TO], pdf=True))
    assert a.items[0].value.count("Attachment: Notice of Hearing 2026-10-27.pdf") == 1
    assert "Written notice: https://docs.google" not in a.items[0].value          # attached, not linked
    engine.apply(approve(world, a).id, world.live, by="A Manager")
    names = [p.get_filename() for p in world.drive.parsed().iter_attachments()]
    assert names == ["Notice of Hearing 2026-10-27.pdf"]
    assert {doc for doc, _ in world.drive.docs().exports} == {"DOC1"}


def test_a_pdf_for_a_hearing_with_no_notice_doc_is_refused(world):
    HEARING_NO_DOC = {**HEARING, "noticeDoc": {}}
    (world.data_dir / "zoom" / "hearings.json").write_text(json.dumps({"hearings": [HEARING_NO_DOC]}), encoding="utf-8")
    with pytest.raises(LookupError, match="no notice Doc"):
        engine.plan(KEY, world.live, by="A Manager", scope=scope("hearing", to=[TO], pdf=True))


def test_only_the_approved_item_is_saved_and_a_rejected_one_saves_nothing(world):
    from jason.approvals.model import Decision

    a = engine.plan(KEY, world.live, by="A Manager", scope=scope(to=[TO]))
    engine.decide(a.id, "all", by="A Manager", decision=Decision.REJECTED, reason="not now", data_dir=world.data_dir)
    a = engine.submit(a.id, by="A Manager", data_dir=world.data_dir)
    assert a.status is S.WITHDRAWN
    with pytest.raises(engine.Refused):
        engine.apply(a.id, world.live, by="A Manager")
    assert world.drive.requests == []


def test_a_source_that_changed_after_the_review_saves_nothing_and_supersedes_the_approval(world):
    a = approve(world, engine.plan(KEY, world.live, by="A Manager", scope=scope("meeting-notice", to=[TO])))
    (world.data_dir / "board" / "agenda-2026-10-20.md").write_text(AGENDA + "2. **Adjournment**\n", encoding="utf-8")
    done = engine.apply(a.id, world.live, by="A Manager")
    assert done.superseded_by is not None and world.drive.requests == []
    assert store.load(a.id, world.data_dir).items[0].result is Result.CHANGED


def test_the_applier_itself_saves_nothing_when_the_email_changes_between_its_plan_and_its_write(world, monkeypatch):
    planned = kind.plan(world.live, scope("proposal-request", to=[TO]))
    original = pr.draft

    def different(*a, **k):
        p = original(*a, **k)
        p.message = type(p.message)(to=p.message.to, subject=p.message.subject, text=p.message.text + "\nP.S. new")
        return p

    monkeypatch.setattr(pr, "draft", different)
    rec = Recorder()
    kind.apply(world.live, planned, planned.items, rec)
    [(result, detail)] = rec.done_calls.values()
    assert result is Result.FAILED and detail == "the source changed since the plan; nothing saved"
    assert world.drive.requests == [] and rec.started == []


def test_a_google_error_fails_the_item_and_marks_nothing_saved(world):
    world.drive.answer = lambda r: httpx.Response(403, text="insufficient permission")
    a = approve(world, engine.plan(KEY, world.live, by="A Manager", scope=scope(to=[TO])))
    done = engine.apply(a.id, world.live, by="A Manager")
    assert done.approval.status is S.FAILED and len(world.drive.drafts) == 1
    item = store.load(a.id, world.data_dir).items[0]
    assert item.result is Result.FAILED and "HTTP 403" in item.result_detail and "nothing saved" in item.result_detail


def test_a_timeout_is_uncertain_not_failed(world):
    def boom(request):
        raise httpx.ReadTimeout("no answer", request=request)

    world.drive.answer = boom
    a = approve(world, engine.plan(KEY, world.live, by="A Manager", scope=scope(to=[TO])))
    engine.apply(a.id, world.live, by="A Manager")
    item = store.load(a.id, world.data_dir).items[0]
    assert item.result is Result.UNCERTAIN and "look in Gmail's drafts" in item.result_detail


def test_nothing_in_a_whole_cycle_reaches_a_send_endpoint(world):
    for case in ("proposal-request", "hearing", "meeting-notice"):
        a = approve(world, engine.plan(KEY, world.live, by="A Manager", scope=scope(case, to=[TO])))
        engine.apply(a.id, world.live, by="A Manager")
    assert len(world.drive.requests) == 3
    assert {(r.method, r.url.path) for r in world.drive.requests} == {("POST", "/gmail/v1/users/me/drafts")}


# --- the command --------------------------------------------------------------------------------------------------------

def test_jason_approvals_plan_takes_a_scope_and_signs_in_to_google_for_the_kind(world, monkeypatch, capsys):
    import argparse

    from jason.commands import approvals as cmd

    monkeypatch.setattr(cmd, "_data_dir", lambda args: world.data_dir)

    @contextmanager
    def drive_live():
        yield SimpleNamespace(client=world.drive, org_id=0)

    monkeypatch.setattr("jason.approvals.evidence.drive_live", drive_live)

    def args(**kw):
        return argparse.Namespace(action="plan", ref=KEY, by="A Manager", scope=json.dumps(scope(to=[TO])), env=None, **kw)

    assert cmd.cmd_approvals(args(), lambda a: pytest.fail("no PayHOA for a Gmail kind")) == 0
    out = capsys.readouterr().out
    assert "save Gmail draft" in out and "rule: gmail_drafts.CASES: proposal-request" in out
    assert cmd.cmd_approvals(argparse.Namespace(action="plan", ref=KEY, by="A Manager", scope="[1]", env=None), None) == 2
    bad = argparse.Namespace(action="plan", ref=KEY, by="A Manager", scope=json.dumps(scope(to=["nope"])), env=None)
    assert cmd.cmd_approvals(bad, None) == 2
    assert "not an email address" in capsys.readouterr().err
    assert world.drive.requests == []
