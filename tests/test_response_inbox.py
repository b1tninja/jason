"""Checking for new responses (docs/responses-design.md, step 1): the records, the four channels' candidate rules, the
check and its inbox on disk, reading an arrival, a person's confirmation, keyed answers reaching the owner-information
apply as one more channel, and an arrival marked recorded once its writes are made.

Everything is made up and offline: a fake Gmail, a fake PayHOA, a fake association (``Assoc``), and a throwaway second
profile. Nothing here reaches a service, Keeper, a real mailbox, or an owner's data."""

from __future__ import annotations

import json
import sys
import textwrap
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.community.forms import (AnswerCycle, CONTACT, EarlierElections, FormAnswers, FormImport, FormKey, FormQuestion,
                                   FormTemplate, ImportRule, QuestionKind)
from jason.community.response_inbox import Arrival, Channel, ResponseRequest, State, Window
from jason.community.tags import PayhoaTag, TagPurpose, TagScope
from jason.google.errors import GoogleAuthRequired
from jason.tasks import response_inbox as ri
from jason.tasks.response_inbox import Ended, OwnerRef, ResponseError

UTC = timezone.utc
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
CYCLE = AnswerCycle(2027, date(2026, 10, 1), return_by=date(2026, 10, 23), reports_mailed=date(2026, 12, 1))

FORM = FormTemplate(FormKey.OWNER_INFO, "Owner information", "Civil Code 4041", "A made-up form.", (
    FormQuestion("Your name", key="name"),
    FormQuestion("Unit address", key="unit-address", required=False),
    FormQuestion("Delivery", QuestionKind.CHECKBOX, required=False, options=("By email", "By mail"), key="delivery"),
    FormQuestion("Occupancy", QuestionKind.CHOICE, required=False, options=("Owner-occupied", "Rented out"), key="occupancy"),
    FormQuestion("Email", QuestionKind.EMAIL, required=False, key="email"),
    FormQuestion("Second mailing address", QuestionKind.SHORT, required=False, key="second-mailing-address")))
GOOGLE = FormImport("copy-2027", "gform1", FormKey.OWNER_INFO, "Google copy", (
    ImportRule("Unit", "unit-address"), ImportRule("Your name", f"{CONTACT}name", role="owner")))
EMAIL_MARK, MAIL_MARK = "AC27E", "AC27M"


def make_request(form: FormTemplate = FORM, **more) -> ResponseRequest:
    base = dict(key="survey-2027", title="Owner survey", form=form, cycle=CYCLE, payhoa_form="owner-info",
                imports=(GOOGLE,), marker_campaigns=(EMAIL_MARK, MAIL_MARK))
    return ResponseRequest(**{**base, **more})


class Assoc:
    """A made-up association: only what the inbox asks of a ``Community``."""

    org_id = 7

    def __init__(self, *requests: ResponseRequest, tags=()) -> None:
        self._requests, self._tags = requests or (make_request(),), tags

    def response_requests(self):
        return self._requests

    def email_domains(self):
        return ("assoc.example",)

    def payhoa_tags(self):
        return self._tags


# -- fakes --------------------------------------------------------------------------------------------------------------

def msg(mid, *, frm="Pat Example <pat@example.org>", to="Office <office@assoc.example>", subject="My form", day=4,
        files=(("form.pdf", "application/pdf", 90_000),), labels=("INBOX",), extra=None):
    ms = int(datetime(2026, 10, day, 15, tzinfo=UTC).timestamp() * 1000)
    return {"id": mid, "threadId": f"t{mid}", "internalDate": str(ms), "labels": list(labels),
            "headers": {"From": frm, "To": to, "Subject": subject, **(extra or {})},
            "attachments": [{"name": n, "type": t, "size": s, "attachmentId": f"att-{mid}-{i}"}
                            for i, (n, t, s) in enumerate(files)]}


class FakeGmail:
    def __init__(self, *messages, attachments=None) -> None:
        self.messages = {m["id"]: m for m in messages}
        self.attachments = attachments or {}
        self.queries: list[str] = []
        self.fetched: list[str] = []
        self.downloaded: list[tuple[str, str]] = []

    def iter_messages(self, query, *, page_size=100, limit=2000):
        self.queries.append(query)
        wanted = query.split('from:"')[1].rstrip('"') if 'from:"' in query else ""
        for mid, m in self.messages.items():
            if not wanted or wanted in m["headers"]["From"]:
                yield {"id": mid, "threadId": m["threadId"]}

    def get_metadata(self, mid, headers=()):
        self.fetched.append(mid)
        return self.messages[mid]

    def get_attachment(self, mid, attachment_id):
        self.downloaded.append((mid, attachment_id))
        return self.attachments.get((mid, attachment_id), b"%PDF-1.4 made up")


class FakePayhoa:
    def __init__(self, rows) -> None:
        self.rows = rows            # id -> (status, membership id, created, unit title, name)
        self.reads: list[str] = []

    def list_form_submissions(self, form_id):
        self.reads.append(f"list {form_id}")
        return [{"id": i, "status": r[0]} for i, r in self.rows.items()]

    def get_form_submission(self, org, sid):
        self.reads.append(f"get {sid}")
        status, member, created, unit, name = self.rows[sid]
        return {"submission": {"id": sid, "membershipId": member, "createdAt": created, "unit": {"title": unit},
                               "membership": {"name": name}}}


@pytest.fixture
def data(tmp_path):
    (tmp_path / "payhoa").mkdir()
    (tmp_path / "payhoa" / "forms.json").write_text(json.dumps({"forms": [{"key": "owner-info", "formId": 900}]}),
                                                    encoding="utf-8")
    return tmp_path


def payhoa_rows():
    return {1001: ("pending", 11, "2026-10-04T10:00:00Z", "101 Example Way", "Ana Example"),
            1002: ("complete", 12, "2026-10-03T10:00:00Z", "102 Example Way", "Ben Sample"),
            1003: ("pending", 99, "2026-10-04T11:00:00Z", "103 Example Way", "A Test Account"),
            1004: ("pending", 13, "2026-09-20T10:00:00Z", "104 Example Way", "Dee Fictional")}   # before the request opened


# -- the records --------------------------------------------------------------------------------------------------------

def test_an_arrival_round_trips_and_names_its_file_without_a_colon():
    a = Arrival("gmail:abc123", "survey-2027", Channel.GMAIL, "2026-10-04T15:00:00+00:00", "Pat Example", "101 Example Way",
                "My form", ("form.pdf",), State.READ, "2026-10-05T12:00:00+00:00", "gmail:zzz", "a note")
    assert Arrival.from_json(json.loads(json.dumps(a.to_json()))) == a
    assert a.native == "abc123" and a.stem == "gmail-abc123" and not a.structured
    assert Arrival("payhoa:1", "k", Channel.PAYHOA, "", "x").structured


def test_a_request_is_watched_from_its_opening_to_a_week_past_its_return_by_date():
    request = make_request()
    window = request.window()
    assert window == Window(date(2026, 10, 1), date(2026, 10, 30))
    assert window.contains(date(2026, 10, 30)) and not window.contains(date(2026, 9, 30)) and not window.closed(date(2026, 10, 30))
    assert window.closed(date(2026, 10, 31))
    later = request.window(date(2026, 11, 15))                    # a person's --since: from that day, no end
    assert later == Window(date(2026, 11, 15), None) and not later.closed(date(2030, 1, 1))
    assert request.names_campaign("ac27e") and not request.names_campaign("AC26E")


def test_a_profile_that_names_no_request_watches_none_and_the_profile_row_is_read_through_community():
    from jason.community import community
    from jason.community.base import Community

    assert Community.response_requests(object()) == ()               # the default: an empty tuple, a miss for any profile
    row = community().response_requests()[0]                        # the active profile's own row
    assert row.form is community().owner_information().OWNER_INFO and row.cycle is community().owner_information().OWNER_INFO_CYCLE
    assert row.payhoa_form == row.form.key.value and row.imports == community().owner_information().FORM_IMPORTS
    from jason.community.form_refs import Channel as MarkerChannel, campaign

    assert {campaign(row.form.code, row.cycle.year, c) for c in MarkerChannel} == set(row.marker_campaigns)
    assert row.blank.endswith("owner-info-fillable.pdf")


# -- the channels' candidate rules ---------------------------------------------------------------------------------------

def test_payhoa_candidates_are_new_submissions_in_the_window_and_test_accounts_are_left_out(data):
    request = make_request()
    record = {"formId": 900}
    channel = ri.PayhoaChannel(FakePayhoa(payhoa_rows()), request, org_id=7, record=record, known=["payhoa:1002"], tests={99})
    kept = {a.id: a for a in channel.check(datetime(2026, 10, 1, tzinfo=UTC))}
    assert set(kept) == {"payhoa:1001"} and channel.excluded == 1                 # 1003 is a test account, 1004 is too old
    a = kept["payhoa:1001"]
    assert (a.state, a.who, a.unit, a.request, a.at) == (State.NEW, "Ana Example", "101 Example Way", "survey-2027",
                                                         "2026-10-04T10:00:00+00:00")
    assert channel.statuses["payhoa:1002"] == "complete"                           # every row's status is seen
    assert [r for r in channel.client.reads if r.startswith("get")] == ["get 1001", "get 1003", "get 1004"]   # the kept id is not read
    done = ri.PayhoaChannel(FakePayhoa(payhoa_rows()), request, org_id=7, record=record, tests={99})
    assert {a.id: a.state for a in done.check(datetime(2026, 10, 1, tzinfo=UTC))}["payhoa:1002"] is State.SEEN   # complete: nothing waits
    with pytest.raises(ResponseError, match="no PayHOA form is recorded"):
        ri.PayhoaChannel(FakePayhoa({}), request, org_id=7, record=None).check(NOW)


def test_gmail_candidates_follow_the_design_and_keep_no_address():
    owners = {"owen@example.org": OwnerRef("105 Example Way", "Owen Holder", 5, 15)}
    group = {"List-Id": "<office.assoc.example>"}
    gmail = FakeGmail(
        msg("m1"),                                                                     # a PDF, from outside
        msg("m2", files=()),                                                           # no attachment, not an owner
        msg("m3", frm="Owen <owen@example.org>", files=(), subject="I rent it out"),   # an owner's address
        msg("m4", frm="Staff <staff@assoc.example>"),                                  # from the association's domain
        msg("m5", labels=("SENT",)),                                                   # sent by the association
        msg("m6", frm='"Pat Example" via Office <office@assoc.example>', to="Members <members@assoc.example>",
            extra={"X-Original-From": "Quinn Writer <quinn@example.org>", **group}),   # group-rewritten
        msg("m7", to="Someone Else <else@elsewhere.example>"),                         # never reached the association
        msg("m8", files=(("image001.png", "image/png", 3_000),)),                      # a signature's logo
        msg("m9", files=(("scan.jpg", "image/jpeg", 400_000),), subject="Reach me at pat@example.org or 916-555-0100"),
        msg("m10", day=2),                                                             # before the window start below
    )
    channel = ri.GmailChannel(gmail, make_request(), own=["assoc.example"], owners=owners)
    messages = {m.id: m for m in channel.messages(datetime(2026, 10, 3, tzinfo=UTC))}
    assert {k: m.candidate for k, m in messages.items()} == {
        "m1": True, "m2": False, "m3": True, "m4": False, "m5": False, "m6": True, "m7": False, "m8": False, "m9": True}
    assert "m10" not in messages
    assert messages["m3"].who == "Owen Holder" and messages["m3"].unit == "105 Example Way"      # the owner, not the address
    assert messages["m6"].who == "Quinn Writer"                                    # read from X-Original-From
    assert messages["m2"].reason.startswith("no PDF or image") and messages["m7"].reason.startswith("did not reach")
    kept = ri.GmailChannel(gmail, make_request(), own=["assoc.example"], owners=owners, known=["gmail:m1"]).check(
        datetime(2026, 10, 3, tzinfo=UTC))
    assert {a.id for a in kept} == {"gmail:m3", "gmail:m6", "gmail:m9"}              # m1 is already kept
    text = json.dumps([a.to_json() for a in kept])
    assert "@" not in text and "916-555" not in text and "[email]" in text            # a subject is scrubbed of addresses
    assert "after:2026/10/03" in gmail.queries[0] and "-in:sent" in gmail.queries[0]


def test_a_sender_search_lists_every_message_from_the_address_and_keeps_only_candidates():
    gmail = FakeGmail(msg("a1"), msg("a2", files=(), subject="a question"), msg("b1", frm="Other <other@example.net>"))
    channel = ri.GmailChannel(gmail, make_request(), own=["assoc.example"])
    kept = channel.check(datetime(2026, 10, 1, tzinfo=UTC), sender="pat@example.org")
    assert 'from:"pat@example.org"' in gmail.queries[0]
    assert {m.id for m in channel.listed} == {"a1", "a2"} and {a.id for a in kept} == {"gmail:a1"}
    assert all("@" not in m.who and "@" not in m.subject for m in channel.listed)


def test_mail_candidates_are_scans_whose_text_carries_the_requests_marker(data):
    from jason.community.form_refs import Channel as MarkerChannel, make

    marker = make("AC", 2027, MarkerChannel.MAIL).text
    other = make("AC", 2026, MarkerChannel.MAIL).text
    rows = [
        {"mailId": "500", "sender": "", "received": "2026-10-03 09:00:00", "scanned": True},
        {"mailId": "501", "sender": "", "received": "2026-10-03 09:00:00", "scanned": True},      # last year's marker
        {"mailId": "502", "sender": "", "received": "2026-10-03 09:00:00", "scanned": True},      # no marker
        {"mailId": "503", "sender": "", "received": "2026-09-01 09:00:00", "scanned": True},      # before the window
        {"mailId": "504", "sender": "", "received": "2026-10-03 09:00:00", "scanned": True, "credential": True},
        {"mailId": "505", "sender": "", "received": "2026-10-04 09:00:00", "scanned": True},      # already kept
    ]
    (data / "mail").mkdir()
    (data / "mail" / "items.json").write_text(json.dumps({"items": rows}), encoding="utf-8")
    for mail_id, text in (("500", f"Owner Information  Ref {marker}"), ("501", f"Ref {other}"), ("502", "an advertisement"),
                          ("503", f"Ref {marker}"), ("504", f"Ref {marker}"), ("505", f"Ref {marker}")):
        (data / "mail" / mail_id).mkdir()
        (data / "mail" / mail_id / "text.txt").write_text(text, encoding="utf-8")
    kept = ri.MailChannel(ri.DiskMail(data), make_request(), known=["mail:505"]).check(datetime(2026, 10, 1, tzinfo=UTC))
    assert [(a.id, a.channel, a.attachments) for a in kept] == [("mail:500", Channel.MAIL, ("contents.pdf",))]
    assert kept[0].summary.endswith(EMAIL_MARK.replace("E", "M")) is False or "AC27M" in kept[0].summary


def test_forms_candidates_are_response_ids_not_yet_kept(data):
    saved = {"form": {"items": [{"title": "Unit", "questionItem": {"question": {"questionId": "q1"}}},
                                {"title": "Your name", "questionItem": {"question": {"questionId": "q2"}}}]},
             "responses": [
                 {"responseId": "r1", "lastSubmittedTime": "2026-10-04T10:00:00Z",
                  "answers": {"q1": {"textAnswers": {"answers": [{"value": "101 Example Way"}]}},
                              "q2": {"textAnswers": {"answers": [{"value": "Ana Example"}]}}}},
                 {"responseId": "r2", "lastSubmittedTime": "2024-09-01T10:00:00Z", "answers": {}}]}
    (data / "forms" / "gform1").mkdir(parents=True)
    (data / "forms" / "gform1" / "responses.json").write_text(json.dumps(saved), encoding="utf-8")
    channel = ri.FormsChannel(ri.SavedForms(data), make_request())
    kept = channel.check(datetime(2026, 10, 1, tzinfo=UTC))
    assert [(a.id, a.who, a.unit, a.summary) for a in kept] == [("forms:r1", "Ana Example", "101 Example Way", "Google copy")]
    assert ri.FormsChannel(ri.SavedForms(data), make_request(), known=["forms:r1"]).check(datetime(2026, 10, 1, tzinfo=UTC)) == []


# -- the check ----------------------------------------------------------------------------------------------------------

def clients(gmail=None, payhoa=None):
    out = {}
    if gmail is not None:
        out[Channel.GMAIL] = lambda: gmail
    if payhoa is not None:
        out[Channel.PAYHOA] = lambda: payhoa
    return out


def test_a_check_keeps_only_new_arrivals_dedupes_and_overlaps_a_day(data):
    gmail = FakeGmail(msg("m1"), msg("m2", files=(), subject="a question"))
    payhoa = FakePayhoa(payhoa_rows())
    first = ri.check(data, Assoc(), clients=clients(gmail, payhoa), by="scheduler", now=NOW, tests={99}, owners={})
    assert [(c.channel, c.ended) for c in first.channels] == [
        (Channel.PAYHOA, Ended.OK), (Channel.GMAIL, Ended.OK), (Channel.MAIL, Ended.OK), (Channel.FORMS, Ended.OK)]
    kept = {a.id: a for a in first.kept}
    assert set(kept) == {"payhoa:1001", "payhoa:1002", "gmail:m1"}
    assert all(a.kept_at == "2026-10-05T12:00:00+00:00" for a in kept.values())
    assert kept["payhoa:1002"].state is State.SEEN and kept["payhoa:1001"].state is State.NEW
    assert "after:2026/10/01" in gmail.queries[0]                                  # the request's opening
    inbox = ri.load_inbox(data)
    assert inbox.channels["gmail"]["lastOk"] == "2026-10-05T12:00:00+00:00" and inbox.channels["gmail"]["ended"] == "ok"
    assert inbox.channels["payhoa"]["requests"] == {"survey-2027": "2026-10-05T12:00:00+00:00"}
    # a message that arrives late (dated yesterday, listed after the last check) is not missed, and nothing is kept twice
    gmail.messages["m3"] = msg("m3", day=4)
    gmail.messages["m3"]["internalDate"] = str(int(datetime(2026, 10, 4, 20, tzinfo=UTC).timestamp() * 1000))
    gmail.fetched.clear()
    second = ri.check(data, Assoc(), clients=clients(gmail, FakePayhoa(payhoa_rows())), by="scheduler",
                      now=datetime(2026, 10, 6, 12, tzinfo=UTC), tests={99}, owners={})
    assert [a.id for a in second.kept] == ["gmail:m3"]
    assert "after:2026/10/04" in gmail.queries[-1]                                 # a day before the last that succeeded
    assert "m1" not in gmail.fetched                                               # a kept message is not read again
    assert len(ri.load_inbox(data).arrivals) == 4


def test_one_failing_channel_does_not_stop_the_others_and_a_sign_in_failure_is_reported_as_one(data):
    def no_google():
        raise GoogleAuthRequired("no human is present; pass interactive=True")

    both = {Channel.GMAIL: no_google, Channel.PAYHOA: lambda: FakePayhoa(payhoa_rows())}
    report = ri.check(data, Assoc(), clients=both, by="a person", now=NOW, tests={99}, owners={})
    by_channel = {c.channel: c for c in report.channels}
    assert by_channel[Channel.GMAIL].ended is Ended.SIGN_IN and "GoogleAuthRequired" in by_channel[Channel.GMAIL].reason
    assert by_channel[Channel.PAYHOA].ended is Ended.OK and by_channel[Channel.PAYHOA].kept == 2
    assert {a.id for a in report.kept} == {"payhoa:1001", "payhoa:1002"} and report.failed == [by_channel[Channel.GMAIL]]
    inbox = ri.load_inbox(data)
    assert inbox.channels["gmail"]["ended"] == "sign-in" and "lastOk" not in inbox.channels["gmail"]
    assert "requests" not in inbox.channels["gmail"]                               # a failure covers nothing

    class Boom(FakePayhoa):
        def list_form_submissions(self, form_id):
            raise RuntimeError("PayHOA answered 500 with Bearer abcdefghijklmnopqrstuvwxyz0123456789")

    again = ri.check(data, Assoc(), clients={Channel.PAYHOA: lambda: Boom({})}, by="a person", channels=[Channel.PAYHOA],
                     now=NOW, tests={99})
    only = again.channels[0]
    assert only.ended is Ended.FAILED and "500" in only.reason and "abcdefghijklmnopqrstuvwxyz0123456789" not in only.reason
    skipped = ri.check(data, Assoc(), clients={}, by="a person", channels=[Channel.GMAIL], now=NOW)
    assert skipped.channels[0].ended is Ended.SKIPPED and "no client" in skipped.channels[0].reason


def test_a_closed_window_is_skipped_until_a_person_gives_a_since(data):
    gmail = FakeGmail(msg("late", day=4))
    after = datetime(2026, 11, 20, 12, tzinfo=UTC)
    report = ri.check(data, Assoc(), clients=clients(gmail), by="scheduler", channels=[Channel.GMAIL], now=after, owners={})
    assert report.channels[0].ended is Ended.SKIPPED and "window is closed" in report.channels[0].reason and not gmail.queries
    asked = ri.check(data, Assoc(), clients=clients(gmail), by="a person", channels=[Channel.GMAIL], now=after,
                     since=date(2026, 10, 1), owners={})
    assert [a.id for a in asked.kept] == ["gmail:late"] and "after:2026/10/01" in gmail.queries[0]
    assert "requests" not in ri.load_inbox(data).channels["gmail"]              # a --since covers nothing for the next default check


def test_from_lists_every_message_from_the_address_but_keeps_only_candidates(data):
    gmail = FakeGmail(msg("a1"), msg("a2", files=(), subject="a question"), msg("b1", frm="Other <other@example.net>"))
    report = ri.check(data, Assoc(), clients=clients(gmail, FakePayhoa(payhoa_rows())), by="a person", now=NOW,
                      sender="pat@example.org", owners={})
    assert [c.channel for c in report.channels] == [Channel.GMAIL]                  # a sender search is Gmail's alone
    assert {m.id for m in report.listed} == {"a1", "a2"} and [a.id for a in report.kept] == ["gmail:a1"]
    assert "requests" not in ri.load_inbox(data).channels["gmail"]
    assert {m.id: m.candidate for m in report.listed} == {"a1": True, "a2": False}


def test_a_test_account_is_left_out_by_the_configured_list(data, monkeypatch):
    monkeypatch.setattr("jason.config.test_memberships", lambda *a, **k: {11})
    report = ri.check(data, Assoc(), clients=clients(payhoa=FakePayhoa(payhoa_rows())), by="a person",
                      channels=[Channel.PAYHOA], now=NOW)
    assert {a.id for a in report.kept} == {"payhoa:1002", "payhoa:1003"}


def test_no_personal_address_reaches_the_inbox_or_the_acts(data):
    gmail = FakeGmail(msg("m1", frm="Pat Example <pat.private@example.org>", subject="from pat.private@example.org"),
                      msg("m2", frm="pat.private@example.org", files=()))
    ri.check(data, Assoc(), clients=clients(gmail), by="a person", channels=[Channel.GMAIL], now=NOW,
             owners={"pat.private@example.org": OwnerRef("101 Example Way", "Pat Example", 1, 11)})
    for path in (data / "responses").rglob("*"):
        if path.is_file():
            assert "pat.private" not in path.read_text(encoding="utf-8"), path
    inbox = ri.load_inbox(data)
    assert {a.who for a in inbox.arrivals.values()} == {"Pat Example"} and inbox.arrivals["gmail:m2"].unit == "101 Example Way"


# -- reading an arrival -------------------------------------------------------------------------------------------------

def read_stub(path, request, layout, model):
    from jason.community.form_refs import Channel as MarkerChannel, make

    marker = make("AC", 2027, MarkerChannel.EMAIL, membership_id=11, unit_id=1).text
    return ri.FileReading(path.name, "scan", {"delivery.by-mail": SimpleNamespace(value=True, how="mark", confidence=0.9)},
                          {"name": "Pat Example", "delivery": ["By mail"], "occupancy": ["Rented out"],
                           "email": "pat@example.org"}, marker, "text", ["a note from the reader"], 12, 0.4)


def kept_email(data, gmail, **more):
    ri.check(data, Assoc(), clients=clients(gmail), by="scheduler", channels=[Channel.GMAIL], now=NOW,
             owners=more.get("owners", {}))
    return "gmail:m1"


def test_read_downloads_the_attachments_and_keeps_a_reading_with_each_fields_confidence(data):
    gmail = FakeGmail(msg("m1", files=(("form.pdf", "application/pdf", 90_000), ("logo.png", "image/png", 1_000),
                                       ("../evil?.pdf", "application/pdf", 5))),
                      attachments={("m1", "att-m1-0"): b"made-up bytes"})
    arrival = kept_email(data, gmail)
    owners = {"pat@example.org": OwnerRef("101 Example Way", "Pat Example", 1, 11)}
    reading = ri.read(data, Assoc(), arrival, by="a person", clients=clients(gmail), owners=owners, reader=read_stub)
    folder = data / "responses" / "files" / "gmail-m1"
    assert sorted(p.name for p in folder.iterdir()) == ["_evil_.pdf", "form.pdf"]      # a name never leaves the folder
    assert all(p.resolve().parent == folder.resolve() for p in folder.iterdir())
    assert (folder / "form.pdf").read_bytes() == b"made-up bytes"
    assert gmail.downloaded == [("m1", "att-m1-0"), ("m1", "att-m1-2")]            # the logo was not downloaded
    assert reading["how"] == "scan" and reading["form"] and reading["fields"]["delivery.by-mail"] == {
        "value": True, "how": "mark", "confidence": 0.9}
    assert reading["owner"] == {"unit": "101 Example Way", "unitId": 1, "membershipId": 11, "name": "Pat Example",
                                "matchedBy": "the sender's address"}          # the reading keeps the membership id
    assert reading["campaignMatches"] and reading["files"][0]["sha256"]
    a = ri.get(data, arrival)
    assert a.state is State.READ and a.unit == "101 Example Way"
    raw = (data / "responses" / "readings" / "gmail-m1.json").read_text(encoding="utf-8")
    assert "pat.example" not in raw and "@" in raw                                  # the form's own email answer, not the sender's
    assert "pat@example.org" in raw                                                 # (the answer is the owner's own entry)
    acts = [(r["act"], r["by"]) for r in ri.acts_for(data, arrival)]
    assert acts == [("kept", "scheduler"), ("read", "a person")]


def test_read_refuses_a_structured_arrival_a_missing_name_and_a_keyed_one(data):
    gmail = FakeGmail(msg("m1"))
    ri.check(data, Assoc(), clients=clients(gmail, FakePayhoa(payhoa_rows())), by="s", now=NOW, tests={99}, owners={})
    with pytest.raises(ResponseError, match="needs no reading"):
        ri.read(data, Assoc(), "payhoa:1001", by="a person", clients=clients(gmail), reader=read_stub)
    with pytest.raises(ResponseError, match="--by is required"):
        ri.read(data, Assoc(), "gmail:m1", by="", clients=clients(gmail), reader=read_stub)
    with pytest.raises(ResponseError, match="no arrival"):
        ri.read(data, Assoc(), "gmail:nope", by="a person", clients=clients(gmail), reader=read_stub)
    ri.read(data, Assoc(), "gmail:m1", by="a person", clients=clients(gmail), reader=read_stub)
    ri.confirm(data, Assoc(), "gmail:m1", by="a person")
    with pytest.raises(ResponseError, match="not read again"):
        ri.read(data, Assoc(), "gmail:m1", by="a person", clients=clients(gmail), reader=read_stub)


def test_the_local_model_is_used_only_when_asked_and_only_after_preflight(data, monkeypatch):
    from jason.local_ai import LocalAIUnavailable

    gmail = FakeGmail(msg("m1"))
    arrival = kept_email(data, gmail)
    gmail.fetched.clear()

    def refuse(model, **kw):
        raise LocalAIUnavailable("Ollama is not answering")

    monkeypatch.setattr("jason.local_ai.preflight", refuse)
    with pytest.raises(LocalAIUnavailable):
        ri.read(data, Assoc(), arrival, by="a person", clients=clients(gmail), model="some-model", reader=read_stub)
    assert gmail.fetched == [] and not (data / "responses" / "files").exists()      # nothing was downloaded
    seen = []
    monkeypatch.setattr("jason.local_ai.preflight", lambda model, **kw: seen.append(model))
    got = []

    def reader(path, request, layout, model):
        got.append(model)
        return read_stub(path, request, layout, model)

    ri.read(data, Assoc(), arrival, by="a person", clients=clients(gmail), reader=reader)        # not asked: no model
    assert got == [None] and seen == []


LAB_REQUEST = None


def _lab_request():
    from jason.tasks.form_lab import LAB_FORM

    return make_request(LAB_FORM, imports=(), blank="packets/lab/blank.pdf")


def _lab_blank(data):
    from jason.tasks import form_lab as fl

    blank = data / "packets" / "lab" / "blank.pdf"
    blank.parent.mkdir(parents=True)
    fl.render(fl.Layout(), blank)
    return blank


def test_a_typed_fillable_pdf_is_read_by_its_fields(data):
    from jason.community.pdf_fields import fill

    blank = _lab_blank(data)
    filled = data / "typed.pdf"
    fill(blank, {"owner-names": "Pat Example", "email": "pat@example.org", "delivery.by-mail": True,
                 "occupancy": "rented-out"}, filled)
    request = _lab_request()
    reading = ri.read_file(filled, request, None, None)
    assert reading.how == "typed" and reading.answers["owner-names"] == "Pat Example"
    assert reading.answers["delivery"] == ["By mail"] and reading.answers["occupancy"] == ["Rented out"]
    assert reading.fields["email"].how == "typed" and reading.fields["email"].confidence > 0.9
    blank_read = ri.read_file(blank, request, None, None)                              # an unfilled form is not an answer
    assert blank_read.how == "not the form" and "no blank form" in blank_read.notes[0]


def test_a_simulated_scan_is_found_and_read_end_to_end(data):
    from jason.community.ocr import PyMuPdfTesseract
    from jason.community.pdf_fields import fill
    from jason.tasks.form_scans import simulate

    if not PyMuPdfTesseract.available():
        pytest.skip("needs Tesseract's language data")
    blank = _lab_blank(data)
    filled = data / "filled.pdf"
    fill(blank, {"delivery.by-mail": True, "occupancy": "rented-out", "email": "pat@example.org"}, filled)
    scan = simulate(filled, data / "scan.pdf", angle=0.8, noise=0.002)
    import pymupdf

    flyer = pymupdf.open()                                  # another PDF in the same message: not the form
    flyer.new_page().insert_text((72, 100), "Spring picnic: bring a dish to share and a chair.", fontsize=12)
    gmail = FakeGmail(msg("m1", files=(("flyer.pdf", "application/pdf", 90_000), ("return.pdf", "application/pdf", 90_000))),
                      attachments={("m1", "att-m1-0"): flyer.tobytes(), ("m1", "att-m1-1"): scan.read_bytes()})
    request = _lab_request()
    assoc = Assoc(request)
    ri.check(data, assoc, clients=clients(gmail), by="scheduler", channels=[Channel.GMAIL], now=NOW, owners={})
    reading = ri.read(data, assoc, "gmail:m1", by="a person", clients=clients(gmail), owners={})
    assert reading["form"] and reading["how"] == "scan"
    assert reading["answers"]["delivery"] == ["By mail"] and reading["answers"]["occupancy"] == ["Rented out"]
    assert "example" in reading["fields"]["email"]["value"] and reading["fields"]["delivery.by-mail"]["confidence"] > 0
    assert [(f["name"], f["how"]) for f in reading["files"]] == [("flyer.pdf", "not the form"), ("return.pdf", "scan")]
    assert reading["files"][1]["linesMatched"] >= 4 and any("flyer.pdf" in n for n in reading["notes"])


# -- confirming ---------------------------------------------------------------------------------------------------------

def read_one(data, **more):
    gmail = FakeGmail(msg("m1"))
    ri.check(data, Assoc(), clients=clients(gmail), by="scheduler", channels=[Channel.GMAIL], now=NOW, owners={})
    owners = {"pat@example.org": OwnerRef("101 Example Way", "Pat Example", 1, 11)}
    ri.read(data, Assoc(), "gmail:m1", by="a person", clients=clients(gmail), owners=owners, reader=read_stub)
    return "gmail:m1"


def test_confirm_makes_the_answers_a_submission_becomes_with_a_persons_corrections(data):
    arrival = read_one(data)
    with pytest.raises(ResponseError, match="--by is required"):
        ri.confirm(data, Assoc(), arrival, by=" ")
    with pytest.raises(ResponseError, match="not a question"):
        ri.confirm(data, Assoc(), arrival, by="Treasurer", corrections={"no-such-field": "x"})
    keyed = ri.confirm(data, Assoc(), arrival, by="Treasurer", why="checked against the scan",
                       corrections={"email": "pat@example.com", "delivery": "By email; By mail", "occupancy": "owner-occupied",
                                    "second-mailing-address": ""})
    answers = keyed.answers
    assert answers.source == "email:m1" and answers.form is FormKey.OWNER_INFO
    assert answers.submitted == "2026-10-04T15:00:00+00:00" and answers.signed == "2026-10-04"
    assert answers.answers == {"name": "Pat Example", "delivery": ["By email", "By mail"], "occupancy": ["Owner-occupied"],
                               "email": "pat@example.com"}
    assert keyed.corrected == ["email", "delivery", "occupancy", "second-mailing-address"] and keyed.problems == []
    assert answers.unit_id == 1 and answers.membership_id is None                     # not a sign-in: matched by name, not claimed
    assert answers.contacts == [{"role": "owner", "name": "Pat Example", "email": "pat@example.com"}]
    assert ri.get(data, arrival).state is State.KEYED
    stored = json.loads((data / "responses" / "keyed" / "gmail-m1.json").read_text(encoding="utf-8"))
    assert stored["by"] == "Treasurer" and stored["corrected"] == keyed.corrected
    assert ri.answers_from_json(stored) == answers
    assert [a.source for a in ri.keyed_answers(data, FormKey.OWNER_INFO)] == ["email:m1"]
    assert ri.keyed_answers(data, FormKey.IDR) == []
    last = ri.acts_for(data, arrival)[-1]
    assert last["act"] == "confirm" and last["by"] == "Treasurer" and last["corrected"] == keyed.corrected
    assert "pat@example.com" not in json.dumps(ri.acts_for(data))                    # the act names fields, never values
    with pytest.raises(ResponseError, match="only a read arrival"):
        ri.confirm(data, Assoc(), arrival, by="Treasurer")


def test_confirm_refuses_a_reading_that_found_no_form_and_dismiss_sets_keyed_answers_aside(data):
    gmail = FakeGmail(msg("m1"), msg("m2"))
    ri.check(data, Assoc(), clients=clients(gmail), by="s", channels=[Channel.GMAIL], now=NOW, owners={})
    ri.read(data, Assoc(), "gmail:m1", by="p", clients=clients(gmail),
            reader=lambda f, r, l, m: ri.FileReading(f.name, "not the form", notes=["does not match"]))
    with pytest.raises(ResponseError, match="found no form"):
        ri.confirm(data, Assoc(), "gmail:m1", by="Treasurer")
    with pytest.raises(ResponseError, match="--why is required"):
        ri.dismiss(data, "gmail:m1", by="Treasurer", why="")
    assert ri.dismiss(data, "gmail:m1", by="Treasurer", why="a flyer, not the form").state is State.DISMISSED
    ri.read(data, Assoc(), "gmail:m2", by="p", clients=clients(gmail), reader=read_stub)
    ri.confirm(data, Assoc(), "gmail:m2", by="Treasurer")
    assert len(ri.keyed_answers(data)) == 1
    ri.dismiss(data, "gmail:m2", by="Treasurer", why="a duplicate")
    assert ri.keyed_answers(data) == [] and (data / "responses" / "keyed" / "withdrawn" / "gmail-m2.json").is_file()
    with pytest.raises(ResponseError, match="cannot be dismissed"):
        ri.dismiss(data, "gmail:m2", by="Treasurer", why="again")


def test_seen_moves_only_new_arrivals_and_every_act_is_logged(data):
    ri.check(data, Assoc(), clients=clients(FakeGmail(msg("m1"), msg("m2")), FakePayhoa(payhoa_rows())), by="s", now=NOW,
             tests={99}, owners={})
    assert ri.seen(data, ["gmail:m1"], by="Secretary") == ["gmail:m1"]
    assert ri.seen(data, ["gmail:m1"], by="Secretary") == []                          # already seen
    with pytest.raises(ResponseError):
        ri.seen(data, ["gmail:m2", "gmail:nope"], by="Secretary")
    assert ri.get(data, "gmail:m2").state is State.NEW                                # no partial change
    assert sorted(ri.seen_all(data, by="Secretary")) == ["gmail:m2", "payhoa:1001"]
    assert not ri.list_arrivals(data, new=True)
    assert {a.id for a in ri.list_arrivals(data, state="seen", channel="gmail")} == {"gmail:m1", "gmail:m2"}
    assert [a.id for a in ri.list_arrivals(data, channel="payhoa")] == ["payhoa:1001", "payhoa:1002"]       # newest first
    acts = ri.acts_for(data)
    assert all({"at", "by", "act", "id", "why"} <= set(row) for row in acts) and {r["by"] for r in acts} == {"s", "check", "Secretary"}


def test_an_owner_directory_is_built_from_the_stored_catalog_in_memory_only(data):
    import sqlite3

    assert ri.owner_directory(data, Assoc()) == {}                                    # no catalog on disk: no directory
    con = sqlite3.connect(data / "payhoa.db")
    con.execute("create table people (id, name, email)")
    con.execute("create table units (id, label, raw_json)")
    con.execute("insert into people values (11, 'Pat Example', 'Pat@Example.org')")
    con.execute("insert into units values (1, '101 EXAMPLE WAY', ?)", (json.dumps({"owners": [{"membershipId": 11, "deletedAt": None}]}),))
    con.commit()
    con.close()
    assert ri.owner_directory(data, Assoc()) == {"pat@example.org": OwnerRef("101 EXAMPLE WAY", "Pat Example", 1, 11)}
    gmail = FakeGmail(msg("m1", frm="Pat <pat@example.org>", files=()))
    report = ri.check(data, Assoc(), clients=clients(gmail), by="a person", channels=[Channel.GMAIL], now=NOW)
    assert [(a.id, a.who, a.unit) for a in report.kept] == [("gmail:m1", "Pat Example", "101 EXAMPLE WAY")]
    assert "pat@example.org" not in (data / "responses" / "inbox.json").read_text(encoding="utf-8").lower()


def test_only_a_keyed_or_structured_arrival_is_marked_recorded(data):
    ri.check(data, Assoc(), clients=clients(FakeGmail(msg("m1")), FakePayhoa(payhoa_rows())), by="s", now=NOW, tests={99},
             owners={})
    assert ri.mark_recorded(data, "gmail:m1", by="Treasurer") is False                 # an email nobody has read and confirmed
    assert ri.mark_recorded(data, "payhoa:1001", by="Treasurer", why="request completed") is True      # already structured
    assert ri.get(data, "payhoa:1001").state is State.RECORDED
    assert ri.mark_recorded(data, "payhoa:nope", by="Treasurer") is False
    with pytest.raises(ResponseError, match="cannot be dismissed"):
        ri.dismiss(data, "payhoa:1001", by="Treasurer", why="a mistake")                # PayHOA was written from it


def test_a_later_answer_for_the_same_unit_supersedes_an_earlier_and_the_earlier_stays(data):
    ri.check(data, Assoc(), clients=clients(FakeGmail(msg("m1", day=4)), FakePayhoa(payhoa_rows())), by="s", now=NOW,
             tests={99}, owners={"pat@example.org": OwnerRef("101 Example Way", "Pat Example", 1, 11)})
    # the PayHOA submission for 101 Example Way came at Oct 4 10:00; the email, matched to the same unit, at 15:00
    assert ri.get(data, "payhoa:1001").superseded_by == "gmail:m1" and ri.get(data, "gmail:m1").superseded_by == ""
    assert ri.get(data, "payhoa:1002").superseded_by == ""                            # another unit
    assert ri.get(data, "payhoa:1001").state is State.NEW                             # superseded, still kept
    ri.dismiss(data, "gmail:m1", by="Secretary", why="not the form")
    assert ri.get(data, "payhoa:1001").superseded_by == ""                            # a dismissed answer supersedes none
    acts = [r["act"] for r in ri.acts_for(data, "payhoa:1001")]
    assert acts == ["kept", "superseded", "restored"]


# -- keyed answers reach the apply as one more channel ----------------------------------------------------------------------

TAGS = (PayhoaTag("Notices by Email", TagScope.MEMBER, TagPurpose.NOTICE_DELIVERY, "email"),
        PayhoaTag("Notices by Mail", TagScope.MEMBER, TagPurpose.NOTICE_DELIVERY, "mail"),
        PayhoaTag("Owner Info 2027", TagScope.MEMBER, TagPurpose.ANSWERED, "2027"),
        PayhoaTag("Rental", TagScope.UNIT, TagPurpose.OCCUPANCY, "Rented out", answer="occupancy"),
        PayhoaTag("Owner Occupied", TagScope.UNIT, TagPurpose.OCCUPANCY, "Owner-occupied", answer="occupancy"))
FORMS = SimpleNamespace(OWNER_INFO=FORM, OWNER_INFO_CYCLE=CYCLE, EARLIER_ELECTIONS=EarlierElections(apply=False),
                        FORM_IMPORTS=(), OWNER_INFO_COMPLETED_COMMENT="<p>Thank you.</p>")


class Village:
    """Made-up units and owners, with the writes a fake PayHOA takes."""

    def __init__(self, fail_on: str = "") -> None:
        self.units = [{"id": 1, "label": "101 EXAMPLE WAY", "title": "101 EXAMPLE WAY", "tags": [{"tag": "Rental"}],
                       "owners": [{"membershipId": 11, "deletedAt": None}]},
                      {"id": 2, "label": "102 EXAMPLE WAY", "title": "102 EXAMPLE WAY", "tags": [],
                       "owners": [{"membershipId": 12, "deletedAt": None}]}]
        self.people = [{"id": 11, "email": "", "tags": [], "profile": {"givenNames": "Pat", "familyName": "Example",
                                                                        "updatedAt": "2024-01-01T00:00:00Z"}},
                       {"id": 12, "email": "", "tags": [], "profile": {"givenNames": "Ben", "familyName": "Sample",
                                                                        "updatedAt": "2024-01-01T00:00:00Z"}}]
        self.writes, self.fail_on = [], fail_on

    def list_units(self, org, page=1):
        return {"data": self.units, "meta": {"lastPage": 1}}

    def iter_people(self, org):
        return iter(self.people)

    def list_form_submissions(self, form_id):
        return []

    def get_form_submission(self, org, sid):
        return {"id": sid}

    def update_member_tags(self, org, ids, *, add=(), remove=()):
        if self.fail_on and self.fail_on in add:
            raise RuntimeError("PayHOA refused")
        self.writes.append(("member", tuple(ids), tuple(add), tuple(remove)))

    def add_unit_tag(self, org, ids, tag):
        self.writes.append(("unit +", tuple(ids), tag))

    def remove_unit_tag(self, org, ids, tag):
        self.writes.append(("unit -", tuple(ids), tag))


def _community(monkeypatch):
    class Profile:
        def payhoa_tags(self):
            return TAGS

        def owner_information(self):
            return FORMS

    return Profile()


def _plan(data, village, community, answers=None, **more):
    from jason.tasks import owner_info_apply as oia

    units, people = village.units, village.people
    found = oia.ledger_rows(units, people, answers if answers is not None else oia.gather_answers(data, FORMS)[0], data,
                            community, CYCLE, date(2026, 10, 10), earlier=FORMS.EARLIER_ELECTIONS)
    return found


def _keyed(data, answers=None, **more):
    """An email arrival read and confirmed with the made-up reading, for the unit and owner in Village."""
    gmail = FakeGmail(msg("m1", frm="Pat Example <pat@example.org>"))
    ri.check(data, Assoc(), clients=clients(gmail), by="scheduler", channels=[Channel.GMAIL], now=NOW,
             owners={"pat@example.org": OwnerRef("101 EXAMPLE WAY", "Pat Example", 1, 11)})

    def reader(path, request, layout, model):
        return ri.FileReading(path.name, "scan", {}, answers or {"name": "Pat Example", "delivery": ["By mail"],
                                                                   "occupancy": ["Owner-occupied"]}, "", "", [], 12, 0.4)

    ri.read(data, Assoc(), "gmail:m1", by="a person", clients=clients(gmail),
            owners={"pat@example.org": OwnerRef("101 EXAMPLE WAY", "Pat Example", 1, 11)}, reader=reader)
    return ri.confirm(data, Assoc(), "gmail:m1", by="Treasurer", **more)


def test_keyed_answers_make_the_same_writes_as_a_payhoa_submission_with_the_same_answers(data, monkeypatch):
    from jason.tasks import owner_info_apply as oia
    from jason.tasks.owner_info import plan_writes

    community = _community(monkeypatch)
    village = Village()
    _keyed(data)
    answers, titles = oia.gather_answers(data, FORMS)
    assert [a.source for a in answers] == ["email:m1"] and titles["email"].startswith("Returned form (email)")
    found, rows = oia.ledger_rows(village.units, village.people, answers, data, community, CYCLE, date(2026, 10, 10),
                                  earlier=FORMS.EARLIER_ELECTIONS)
    from_email = plan_writes(rows, found, TAGS, earlier=FORMS.EARLIER_ELECTIONS, today=date(2026, 10, 10))
    submission = FormAnswers(FormKey.OWNER_INFO, {"name": "Pat Example", "delivery": ["By mail"], "occupancy": ["Owner-occupied"]},
                             source="payhoa:501", submitted="2026-10-04T15:00:00+00:00", membership_id=11, unit_id=1)
    found2, rows2 = oia.ledger_rows(village.units, village.people, [submission], data, community, CYCLE, date(2026, 10, 10),
                                    earlier=FORMS.EARLIER_ELECTIONS)
    from_payhoa = plan_writes(rows2, found2, TAGS, earlier=FORMS.EARLIER_ELECTIONS, today=date(2026, 10, 10))
    shape = lambda writes: sorted((w.kind, w.target, w.value) for w in writes)
    assert shape(from_email) == shape(from_payhoa) and shape(from_email)             # the same writes, and some
    assert any(w.kind == "member tag +" and w.value == "Notices by Mail" for w in from_email)
    assert {r.status.name for r in rows if r.unit_id == 1} == {"ANSWERED"}
    assert rows[0].answer.how == "name" and rows[0].answer.source == "email:m1"       # matched by the name, not claimed as a sign-in


def test_an_arrival_is_recorded_when_the_writes_it_calls_for_are_made(data, monkeypatch):
    from jason.tasks import owner_info_apply as oia

    community, village = _community(monkeypatch), Village()
    _keyed(data)
    plan = oia.plan_apply(village, 7, community=community, forms=FORMS, cycle=CYCLE, data_dir=data, today=date(2026, 10, 10),
                          payhoa=False, by="Treasurer")
    assert plan.observer is not None and plan.writes and ri.get(data, "gmail:m1").state is State.KEYED      # a plan writes nothing
    assert "_observer" not in asdict(plan.writes[0])                                  # a saved plan never sees the observer
    results = oia.execute_each(village, 7, plan.writes, member_tag_rows=plan.member_tag_rows)
    assert all(r.satisfied for r in results) and village.writes
    a = ri.get(data, "gmail:m1")
    assert a.state is State.RECORDED
    last = ri.acts_for(data, "gmail:m1")[-1]
    assert last["act"] == "recorded" and last["by"] == "Treasurer" and "PayHOA write" in last["why"]
    assert ri.mark_recorded(data, "gmail:m1", by="Treasurer") is False                # once


def test_a_failed_write_or_something_left_for_a_person_keeps_the_arrival_keyed(data, monkeypatch):
    from jason.tasks import owner_info_apply as oia

    community = _community(monkeypatch)
    _keyed(data)
    village = Village(fail_on="Notices by Mail")
    plan = oia.plan_apply(village, 7, community=community, forms=FORMS, cycle=CYCLE, data_dir=data, today=date(2026, 10, 10),
                          payhoa=False)
    results = oia.execute_each(village, 7, plan.writes, member_tag_rows=plan.member_tag_rows)
    assert any(r.error for r in results) and ri.get(data, "gmail:m1").state is State.KEYED
    # an answer that asks for what a person enters (a second mailing address) is not recorded by tags alone
    other = data / "second"
    (other / "payhoa").mkdir(parents=True)
    _keyed(other, {"name": "Pat Example", "delivery": ["By mail"], "occupancy": ["Owner-occupied"],
                   "second-mailing-address": "PO Box 9, Example City"})
    clean = Village()
    again = oia.plan_apply(clean, 7, community=community, forms=FORMS, cycle=CYCLE, data_dir=other,
                           today=date(2026, 10, 10), payhoa=False)
    oia.execute_each(clean, 7, again.writes, member_tag_rows=again.member_tag_rows)
    assert ri.get(other, "gmail:m1").state is State.KEYED
    assert [b for e in again.observer.expected for b in e.blockers] == ["a person enters the secondary delivery"]


def test_with_no_inbox_a_plan_has_no_observer_and_the_apply_is_unchanged(data, monkeypatch):
    from jason.tasks import owner_info_apply as oia

    community, village = _community(monkeypatch), Village()
    plan = oia.plan_apply(village, 7, community=community, forms=FORMS, cycle=CYCLE, data_dir=data, today=date(2026, 10, 10),
                          payhoa=False)
    assert plan.observer is None and not (data / "responses").exists()
    oia.execute_each(village, 7, plan.writes, member_tag_rows=plan.member_tag_rows)  # no observer, no inbox, no error


# -- a second profile ---------------------------------------------------------------------------------------------------

_OTHER = """
    from pathlib import Path

    from jason.community.base import Community


    class Other(Community):
        name = "Other Community Association"
        slug = "other"
        org_id = 3
        root = Path(__file__).parent

        def document_sync_rules(self):
            return {"rules": [], "exclude": []}

        def buildings(self):
            return ()

        def document_rules(self):
            return ()

        def transaction_rules(self):
            return ()

        def insurance_workbook_id(self):
            return ""

        def email_domains(self):
            return ("other.example",)

        def response_requests(self):
            from jason.community.response_inbox import ResponseRequest
            from jason.community.forms import AnswerCycle, FormKey, FormTemplate
            from datetime import date

            form = FormTemplate(FormKey.OWNER_INFO, "Other form", "", "", ())
            return (ResponseRequest("other-2027", "Other request", form, AnswerCycle(2027, date(2026, 10, 1))),)
"""


@pytest.fixture
def other_profile(tmp_path, monkeypatch):
    from jason.community import Community
    from jason.community import profile as profiles

    stubs = "".join(f"\n        def {m}(self, *args, **kwargs):\n            return ()\n"
                    for m in sorted(Community.__abstractmethods__)
                    if m not in {"name", "slug", "org_id", "root", "document_sync_rules", "buildings", "document_rules",
                                 "transaction_rules", "insurance_workbook_id"})
    package = tmp_path / "other"
    package.mkdir()
    (package / "__init__.py").write_text(textwrap.dedent(_OTHER + stubs + "\n    PROFILE = Other\n"), encoding="utf-8")
    (package / "forms.py").write_text("OWNER_INFO = {}\n", encoding="utf-8")
    monkeypatch.setenv("JASON_PROFILE", "other")
    monkeypatch.setenv("JASON_PROFILE_DIR", str(package))
    yield package
    for module in [m for m in sys.modules if m == "jason_other" or m.startswith("jason_other.")]:
        del sys.modules[module]
    profiles._LOADED.pop("other", None)


def test_another_profile_is_checked_through_community_with_nothing_of_the_first(other_profile, tmp_path):
    from jason.community import community

    other = community()
    assert other.slug == "other" and other.response_requests()[0].key == "other-2027"
    work = tmp_path / "data"
    work.mkdir()
    gmail = FakeGmail(msg("o1", to="Desk <desk@other.example>"), msg("o2", to="Office <office@assoc.example>"))
    report = ri.check(work, other, clients=clients(gmail), by="scheduler", channels=[Channel.GMAIL], now=NOW, owners={})
    assert [a.id for a in report.kept] == ["gmail:o1"] and report.kept[0].request == "other-2027"   # its own domain, not ours
    assert report.channels[0].ended is Ended.OK


# -- the web access level -----------------------------------------------------------------------------------------------

def test_the_responses_folder_is_a_private_place(tmp_path):
    from jason.web.access import Level, level_of_path, placed

    for rel in ("responses/inbox.json", "responses/files/gmail-m1/return.pdf", "responses/files/gmail-m1/photo.jpg",
                "responses/readings/gmail-m1.json", "responses/keyed/gmail-m1.json", "responses/acts.jsonl"):
        assert level_of_path(rel, tmp_path) is Level.P3 and placed(rel, tmp_path), rel
