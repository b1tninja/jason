from __future__ import annotations

import base64
import email
import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from jason.google.forms import FormKey, GoogleForms, QuestionKind
from jason.google.gmail_drafts import DraftMessage, GmailDrafts
from jason.tasks import drafts as drafts_task
from jason.tasks import forms as forms_task


class Recorder:
    """A MockTransport handler that records every request and fails any /send call."""

    def __init__(self, answer):
        self.requests: list[httpx.Request] = []
        self.answer = answer

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert "/send" not in request.url.path, "a request reached a send endpoint"
        return self.answer(request)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


HEARING = {
    "address": "1234 Example Way", "building": "2", "start": "2026-10-27T19:00", "timezone": "America/Los_Angeles",
    "noticeBy": "2026-10-17", "zoom": {"id": 1, "joinUrl": "https://zoom.us/j/1", "passcode": "abc", "dialIn": []},
    "noticeDoc": {"id": "DOC1", "url": "https://docs.google.com/document/d/DOC1/edit", "unfilled": []},
}


def _write_hearing(tmp_path: Path) -> None:
    path = tmp_path / "zoom" / "hearings.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"hearings": [HEARING]}), encoding="utf-8")


def test_gmail_drafts_client_has_no_send():
    assert not [name for name in dir(GmailDrafts) if "send" in name.lower()]


def test_hearing_draft_created_never_sent(tmp_path):
    _write_hearing(tmp_path)
    hearing = drafts_task.find_hearing(tmp_path, "1234 example way", today=date(2026, 10, 1))
    plan = drafts_task.hearing_draft(hearing, "member@example.org", "Test Association")
    assert "1234" not in plan.message.subject
    assert drafts_task.CONSENT_REMINDER in plan.reminders
    assert "4040" not in plan.message.text
    assert "https://zoom.us/j/1" in plan.message.text and HEARING["noticeDoc"]["url"] in plan.message.text

    rec = Recorder(lambda r: httpx.Response(200, json={"id": "d1", "message": {"id": "m1"}}))
    created = drafts_task.save(plan, GmailDrafts("tok", http=rec.client()))
    assert created["id"] == "d1"
    [request] = rec.requests
    assert request.method == "POST" and request.url.path == "/gmail/v1/users/me/drafts"
    raw = json.loads(request.content)["message"]["raw"]
    parsed = email.message_from_bytes(base64.urlsafe_b64decode(raw))
    assert parsed["To"] == "member@example.org"
    assert parsed["Subject"].startswith("Notice of Hearing")


def test_draft_attachment(tmp_path):
    pdf = tmp_path / "notice.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    message = DraftMessage(to=("a@example.org",), cc=("b@example.org",), subject="s", text="t", html="<p>t</p>",
                           attachments=(pdf,)).email()
    names = [part.get_filename() for part in message.iter_attachments()]
    assert names == ["notice.pdf"] and message["Cc"] == "b@example.org"


def test_meeting_notice_from_agenda(tmp_path):
    agenda = tmp_path / "board" / "agenda-2026-10-20.md"
    agenda.parent.mkdir(parents=True)
    agenda.write_text("# DRAFT Agenda for 10/20/26\n\n_Notice with this agenda must go out by Friday, October 16 "
                      "(CIV 4920(a))._\n\n1. **Call to Order**\n", encoding="utf-8")
    plan = drafts_task.meeting_notice_draft(tmp_path, date(2026, 10, 20), "board@example.org", "Test Association")
    assert plan.message.text.startswith("# DRAFT Agenda")
    assert any("DRAFT" in r for r in plan.reminders)
    assert any("Friday, October 16" in r for r in plan.reminders)


def test_list_drafts():
    rec = Recorder(lambda r: httpx.Response(200, json={"drafts": [{"id": "d1"}]}))
    assert GmailDrafts("tok", http=rec.client()).list() == [{"id": "d1"}]
    assert rec.requests[0].method == "GET"


def test_form_templates_are_spec_rows():
    idr = forms_task.template("idr")
    records = forms_task.template(FormKey.RECORDS)
    assert "5910" in idr.authority and "5205" in records.authority
    assert any(q.kind is QuestionKind.CHOICE for q in records.questions)


def test_create_form_and_responses(tmp_path):
    def answer(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path == "/v1/forms":
            return httpx.Response(200, json={"formId": "F1"})
        if path == "/v1/forms/F1:batchUpdate":
            return httpx.Response(200, json={"replies": []})
        if path == "/v1/forms/F1/responses":
            return httpx.Response(200, json={"responses": [{
                "responseId": "r1", "lastSubmittedTime": "2026-10-01T00:00:00Z",
                "answers": {"q1": {"questionId": "q1", "textAnswers": {"answers": [{"value": "A. Member"}]}}}}]})
        if path == "/v1/forms/F1":
            return httpx.Response(200, json={"formId": "F1", "responderUri": "https://forms/F1",
                                             "items": [{"title": "Your name", "questionItem": {"question": {"questionId": "q1"}}}]})
        return httpx.Response(404)

    rec = Recorder(answer)
    forms = GoogleForms("tok", http=rec.client())
    record = forms_task.create(forms, forms_task.template("idr"), tmp_path)
    assert record["formId"] == "F1"
    update = json.loads(rec.requests[1].content)["requests"]
    questions = forms_task.template("idr").questions                       # one item a question, and one heading a section
    assert "updateFormInfo" in update[0] and len(update) == 1 + len(questions) + sum(1 for q in questions if q.section)
    assert json.loads(rec.requests[0].content) == {"info": {"title": "Request for Internal Dispute Resolution",
                                                            "documentTitle": "Request for Internal Dispute Resolution"}}

    saved = forms_task.fetch_responses(forms, "F1", tmp_path)
    assert saved == tmp_path / "forms" / "F1" / "responses.json"
    rows = forms_task.load_rows(tmp_path, "F1")
    assert rows == [{"responseId": "r1", "submitted": "2026-10-01T00:00:00Z", "Your name": "A. Member"}]


def test_draft_command_dry_run_makes_no_request(tmp_path, monkeypatch, capsys):
    import argparse

    from jason.commands import drafts_forms

    _write_hearing(tmp_path)
    monkeypatch.setattr(drafts_forms, "_data_dir", lambda args: tmp_path)

    def no_agent(args):
        pytest.fail("a dry run opened the agent")

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    drafts_forms.register(sub, lambda p: p.add_argument("--env"), no_agent)
    args = parser.parse_args(["draft", "--hearing", "1234 Example Way", "--to", "member@example.org"])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "Dry run" in out and "4041" in out
    args = parser.parse_args(["forms", "--create", "records"])
    assert args.func(args) == 0


# --- editing a saved draft in place ---------------------------------------------------------------------------------

def _saved(text="Dear board,\nAs discussed in executive session.\n", to="a@x.org, b@x.org", files=()):
    parts = [{"mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(text.encode()).decode()}}]
    parts += [{"mimeType": "application/pdf", "filename": f, "body": {"attachmentId": "A"}} for f in files]
    return {"id": "r1", "message": {"id": "m1", "threadId": "t9", "payload": {
        "mimeType": "multipart/mixed", "headers": [{"name": "To", "value": to}, {"name": "Subject", "value": "Hold notice"}],
        "parts": parts}}}


class DraftStore:
    def __init__(self, saved):
        self.saved, self.puts = saved, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert "/send" not in request.url.path
        if request.method == "GET":
            return httpx.Response(200, json=self.saved)
        if request.method == "PUT":
            body = json.loads(request.content)
            self.puts.append(body)
            return httpx.Response(200, json={"id": body["id"], "message": {"id": "m2"}})
        return httpx.Response(405)


def _gmail(store):
    return GmailDrafts("token", http=httpx.Client(transport=httpx.MockTransport(store)))


def test_an_edit_updates_in_place_and_keeps_the_recipients_typed_in_gmail() -> None:
    store = DraftStore(_saved())
    edit = _gmail(store).edit("r1", replace=(("executive session.", "executive session on August 18, 2026."),), yes=True)
    assert "+As discussed in executive session on August 18, 2026." in edit.diff()
    put = store.puts[0]
    assert put["id"] == "r1" and put["message"]["threadId"] == "t9"
    sent = email.message_from_bytes(base64.urlsafe_b64decode(put["message"]["raw"]))
    assert sent["To"] == "a@x.org, b@x.org" and sent["Subject"] == "Hold notice"


def test_a_replacement_that_misses_changes_nothing_and_a_dry_run_writes_nothing() -> None:
    from jason.google.errors import GoogleError

    store = DraftStore(_saved())
    with pytest.raises(GoogleError):
        _gmail(store).edit("r1", replace=(("not in the draft", "x"),), yes=True)
    _gmail(store).edit("r1", subject="Hold notice - revised")
    assert store.puts == []


def test_an_edit_never_drops_an_attachment() -> None:
    from jason.google.errors import GoogleError

    store = DraftStore(_saved(files=("notice.pdf",)))
    with pytest.raises(GoogleError, match="attachments"):
        _gmail(store).edit("r1", subject="changed", yes=True)
    assert store.puts == []
