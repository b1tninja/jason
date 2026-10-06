"""The response inbox uses the sent-copy catalog (docs/arrivals-design.md, build step 1b): a Gmail candidate whose subject
carries a sent reference is kept with no attachment and no download, a reading records the copy as sent (owner, unit,
membership id, channel, rung) and compares it with the unit written and the owner the sender matches, and a
disagreement is noted in plain words.

Made-up and offline, with the fakes of ``test_response_inbox``: nothing reaches a service, a mailbox, or an owner's data."""

from __future__ import annotations

import json

import pytest

from jason.community.fillable import stamp_reference
from jason.community.form_refs import Channel as MarkerChannel, make
from jason.community.ocr import PyMuPdfTesseract
from jason.community.pdf_fields import fill
from jason.community.response_inbox import Channel, State
from jason.tasks import response_inbox as ri
from jason.tasks.form_references import record
from jason.tasks.response_inbox import OwnerRef
from tests.test_response_inbox import (NOW, Assoc, FakeGmail, _lab_blank, _lab_request, clients, data, make_request,  # noqa: F401
                                       msg, payhoa_rows, read_stub)

MARKER = make("AC", 2027, MarkerChannel.EMAIL, membership_id=11, unit_id=1).text          # the copy sent to Pat, unit 1
OTHER = make("AC", 2027, MarkerChannel.EMAIL, membership_id=12, unit_id=2).text           # the copy sent to Ben, unit 2
NEVER = make("AC", 2027, MarkerChannel.EMAIL, membership_id=99, unit_id=99).text          # nobody was sent this one
PAT = {"pat@example.org": OwnerRef("101 Example Way", "Pat Example", 1, 11)}
BEN = {"ben@example.org": OwnerRef("102 Example Way", "Ben Sample", 2, 12)}


@pytest.fixture
def sent(data):
    record(data, MARKER, form="owner-info", year=2027, membershipId=11, unitId=1, unit="101 Example Way", channel="email")
    record(data, OTHER, form="owner-info", year=2027, membershipId=12, unitId=2, unit="102 Example Way", channel="email")
    return data


class NoDownload(FakeGmail):
    """A mailbox whose attachments must never be fetched."""

    def get_attachment(self, mid, attachment_id):
        raise AssertionError(f"downloaded {mid}/{attachment_id}")


def stub(reference=MARKER, answers=None):
    def reader(path, request, layout, model):
        out = read_stub(path, request, layout, model)
        out.reference = reference
        out.reference_how = "text" if reference else ""
        out.answers = {**out.answers, **(answers or {})}
        return out
    return reader


def read_one(data, *, subject="My form", owners=PAT, reader=None, who="Pat <pat@example.org>", mid="m1"):
    gmail = FakeGmail(msg(mid, subject=subject, frm=who))
    ri.check(data, Assoc(), clients=clients(gmail), by="scheduler", channels=[Channel.GMAIL], now=NOW, owners=owners)
    return ri.read(data, Assoc(), f"gmail:{mid}", by="Secretary", clients=clients(gmail), owners=owners,
                   reader=reader or stub())


# -- the Gmail candidate rule: rung 1 on the headers it already has -----------------------------------------------------------

def test_a_reply_whose_subject_carries_a_sent_reference_is_kept_with_no_attachment_and_nothing_is_downloaded(sent):
    gmail = NoDownload(msg("m1", subject=f"Re: Owner information request [Ref {MARKER}]", files=()),
                       msg("m2", subject="a question about parking", files=()),
                       msg("m3", subject=f"Re: Owner information request [Ref {NEVER}]", files=()),
                       msg("m4", subject=f"Re: [Ref {OTHER}]", files=(), frm="Staff <staff@assoc.example>"))
    report = ri.check(sent, Assoc(), clients=clients(gmail), by="scheduler", channels=[Channel.GMAIL], now=NOW, owners={})
    assert [a.id for a in report.kept] == ["gmail:m1"]                  # m2 has no reference; m3's was never sent; m4 is ours
    kept = report.kept[0]
    assert MARKER in kept.note and "101 Example Way" in kept.note and "subject" in kept.note
    assert kept.unit == "" and kept.attachments == ()                    # the sender is not matched to a unit by a hint
    assert gmail.downloaded == []                                        # rung 1 read headers only
    stored = ri.load_inbox(sent).arrivals["gmail:m1"]
    assert stored.note == kept.note and stored.state is State.NEW


def test_a_message_with_no_catalog_on_disk_is_judged_as_before(data):
    gmail = NoDownload(msg("m1", subject=f"Re: [Ref {MARKER}]", files=()), msg("m2"))
    report = ri.check(data, Assoc(), clients=clients(gmail), by="scheduler", channels=[Channel.GMAIL], now=NOW, owners={})
    assert [a.id for a in report.kept] == ["gmail:m2"]                   # a PDF from outside; the bare subject proves nothing


def test_a_pdf_from_an_owner_who_was_sent_a_copy_and_has_not_answered_says_so(sent):
    channel = ri.GmailChannel(FakeGmail(), make_request(), own=["assoc.example"], owners={**PAT, **BEN}, data_dir=sent)
    assert channel.judge(msg("a1", frm="Quinn <quinn@example.org>")).reason == "carries a PDF or an image"   # unknown sender
    asked = channel.judge(msg("a2", frm="Pat <pat@example.org>"))
    assert asked.candidate and asked.reason == "carries a PDF or an image, from an owner who was sent a copy and has not answered"
    assert channel.asked(PAT["pat@example.org"]) is True and channel.asked(None) is None
    assert channel.asked(OwnerRef("103 Example Way", "Cy Other", 3, 13)) is False   # sent no copy
    # once Pat has answered (a kept arrival for the unit), the same message is no longer "asked and silent"
    ri.check(sent, Assoc(), clients=clients(FakeGmail(msg("m1", frm="Pat <pat@example.org>"))), by="s",
             channels=[Channel.GMAIL], now=NOW, owners=PAT)
    again = ri.GmailChannel(FakeGmail(), make_request(), own=["assoc.example"], owners=PAT, data_dir=sent)
    assert again.asked(PAT["pat@example.org"]) is False
    assert again.judge(msg("a3", frm="Pat <pat@example.org>")).reason == "carries a PDF or an image"
    assert ri.GmailChannel(FakeGmail(), make_request(), own=["assoc.example"], owners=PAT).asked(
        PAT["pat@example.org"]) is None                                  # no data folder: nothing to ask the catalog


# -- reading: the copy as sent, kept on the reading -----------------------------------------------------------------------------

def test_a_reading_records_the_copy_as_sent_and_compares_it_with_the_sender_and_the_page(sent):
    reading = read_one(sent, reader=stub(answers={"unit-address": "101 Example Way, Sacramento, CA"}))
    copy = reading["copy"]
    assert copy["found"] and copy["reference"] == MARKER and copy["membershipId"] == 11 and copy["unitId"] == 1
    assert copy["unit"] == "101 Example Way" and copy["owner"] == "Pat Example" and copy["channel"] == "email"
    assert copy["year"] == 2027 and copy["form"] == "owner-info" and copy["firstSent"] and copy["identity"] == "copy"
    assert (copy["matchesUnit"], copy["matchesOwner"], copy["matchesWritten"]) == (True, True, True)
    assert copy["rung"] == "mark" and copy["sure"] == "high" and copy["putRight"] is False
    assert reading["owner"]["membershipId"] == 11                                   # the reading keeps the membership id
    assert reading["recognition"]["outcome"] == "recognized" and "copy" not in reading["recognition"]
    assert not any("sent to" in n for n in reading["notes"])                        # nothing disagrees: nothing is said
    assert json.loads((sent / "responses" / "readings" / "gmail-m1.json").read_text(encoding="utf-8"))["copy"] == copy
    assert ri.copy_of(sent, reading)["membershipId"] == 11                          # what the command and the tool read


def test_a_copy_sent_to_another_unit_and_owner_is_noted_plainly(sent):
    reading = read_one(sent, reader=stub(OTHER, {"unit-address": "105 Example Way"}))      # Pat wrote back with Ben's copy
    copy = reading["copy"]
    assert copy["found"] and copy["unit"] == "102 Example Way" and copy["membershipId"] == 12
    assert (copy["matchesUnit"], copy["matchesOwner"], copy["matchesWritten"]) == (False, False, False)
    notes = reading["notes"]
    assert any("the copy was sent to 102 Example Way, but the sender's address belongs to 101 Example Way" in n for n in notes)
    assert any("the form names 105 Example Way" in n for n in notes)
    assert any("the copy was sent to Ben Sample, but the sender's address belongs to Pat Example" in n for n in notes) is False
    # (the owner note is left out when the unit already disagrees: one difference is said once)


def test_a_co_owner_answering_on_the_same_unit_is_a_different_owner_not_a_different_unit(sent):
    people = {**PAT, "cy@example.org": OwnerRef("101 Example Way", "Cy Example", 1, 13)}
    reading = read_one(sent, owners=people, who="Cy <cy@example.org>")
    copy = reading["copy"]
    assert copy["matchesUnit"] is True and copy["matchesOwner"] is False
    assert any("the copy was sent to Pat Example, but the sender's address belongs to Cy Example" in n
               for n in reading["notes"]), reading["notes"]


def test_a_reference_no_sent_copy_carries_is_noted_as_one_we_did_not_send(sent):
    reading = read_one(sent, reader=stub(NEVER))
    assert reading["copy"]["found"] is False and reading["copy"]["unsent"] is True
    assert any("did not send" in n for n in reading["notes"]) and reading["recognition"]["unsent"] is True
    assert ri.copy_of(sent, reading)["unsent"] is True


def test_with_no_catalog_a_reference_is_not_called_one_we_did_not_send(data):
    reading = read_one(data, reader=stub(NEVER))
    assert reading["copy"]["found"] is False and not reading["copy"]["unsent"]
    assert not any("did not send" in n for n in reading["notes"])


def test_a_page_with_no_marker_takes_its_copy_from_the_subject(sent):
    reading = read_one(sent, subject=f"Re: Owner information request [Ref {MARKER}]", reader=stub(""))
    assert reading["reference"] == "" and reading["copy"]["found"] and reading["copy"]["reference"] == MARKER
    assert reading["copy"]["rung"] == "subject" and reading["recognition"]["rung"] == "subject"
    assert reading["copy"]["matchesUnit"] is True and reading["copy"]["matchesOwner"] is True


def test_where_the_subject_and_the_page_name_different_copies_the_page_is_used_and_the_difference_noted(sent):
    reading = read_one(sent, subject=f"Re: [Ref {OTHER}]", reader=stub(MARKER))
    assert reading["copy"]["reference"] == MARKER and reading["copy"]["rung"] == "mark"
    assert any("subject names the copy sent to 102 Example Way, but the page's marker names the copy sent to 101 Example Way"
               in n for n in reading["notes"]), reading["notes"]
    same = read_one(sent, subject=f"Re: [Ref {MARKER}]", reader=stub(MARKER), mid="m2")   # the same copy twice: the cheaper rung
    assert same["copy"]["rung"] == "subject" and not any("names the copy" in n for n in same["notes"])


def test_a_mailed_scan_is_recognized_by_the_mail_services_text(data):
    campaign = make("AC", 2027, MarkerChannel.MAIL).text
    record(data, campaign, form="owner-info", year=2027, channel="MAIL", identity="campaign", batch="owner-info-2027-mail")
    mail = data / "mail"
    (mail / "500").mkdir(parents=True)
    (mail / "items.json").write_text(json.dumps({"items": [
        {"mailId": "500", "sender": "", "received": "2026-10-03 09:00:00", "scanned": True}]}), encoding="utf-8")
    (mail / "500" / "text.txt").write_text(f"Owner Information  Ref {campaign}", encoding="utf-8")
    (mail / "500" / "contents.pdf").write_bytes(b"made-up bytes")
    ri.check(data, Assoc(), clients={}, by="scheduler", channels=[Channel.MAIL], now=NOW)
    reading = ri.read(data, Assoc(), "mail:500", by="Secretary", clients={}, owners={}, reader=stub(""))
    copy = reading["copy"]
    assert copy["found"] and copy["identity"] == "campaign" and copy["unit"] == "" and copy["rung"] == "text-layer"
    assert (copy["matchesUnit"], copy["matchesOwner"]) == (None, None)               # a mailing names no unit or owner


@pytest.mark.skipif(not PyMuPdfTesseract.available(), reason="needs Tesseract's language data")
def test_a_typed_pdf_is_recognized_through_the_real_reader_and_the_catalog(sent):
    blank = _lab_blank(sent)
    stamped = sent / "stamped.pdf"
    stamped.write_bytes(blank.read_bytes())
    stamp_reference(stamped, MARKER)
    filled = sent / "typed.pdf"
    fill(stamped, {"owner-names": "Pat Example", "unit-address": "101 Example Way", "delivery.by-mail": True}, filled)
    gmail = FakeGmail(msg("m1", subject="My form"), attachments={("m1", "att-m1-0"): filled.read_bytes()})
    assoc = Assoc(_lab_request())
    ri.check(sent, assoc, clients=clients(gmail), by="scheduler", channels=[Channel.GMAIL], now=NOW, owners=PAT)
    reading = ri.read(sent, assoc, "gmail:m1", by="Secretary", clients=clients(gmail), owners=PAT)
    assert reading["how"] == "typed" and reading["reference"] == MARKER
    copy = reading["copy"]
    assert copy["found"] and copy["unit"] == "101 Example Way" and copy["membershipId"] == 11
    assert copy["rung"] == "text-layer" and (copy["matchesUnit"], copy["matchesOwner"], copy["matchesWritten"]) == (True, True, True)
    assert gmail.downloaded == [("m1", "att-m1-0")]                                   # one download, for the reading


# -- who has answered -----------------------------------------------------------------------------------------------------------

def test_answers_are_the_arrivals_readings_and_keyed_answers_that_were_not_dismissed(sent):
    ri.check(sent, Assoc(), clients=clients(FakeGmail(msg("m1", frm="Pat <pat@example.org>"), msg("m2", frm="Ben <ben@example.org>")),
                                            FakePayhoaOf()), by="s", now=NOW, tests={99}, owners={**PAT, **BEN})
    copies = {c.reference: c for c in ri.Catalog.load(sent).copies()}
    answers = ri.answered_by(sent, "survey-2027")
    assert answers.of(copies[MARKER]) == ["gmail:m1", "payhoa:1001"] and answers.of(copies[OTHER]) == ["gmail:m2", "payhoa:1002"]
    ri.dismiss(sent, "gmail:m2", by="Secretary", why="a question, not the form")
    after = ri.answered_by(sent, "survey-2027")
    assert after.of(copies[OTHER]) == ["payhoa:1002"] and "gmail:m2" not in after.arrivals          # dismissed is not an answer
    assert ri.answered_by(sent, "another-request").arrivals == {}
    ri.read(sent, Assoc(), "gmail:m1", by="Secretary", clients=clients(FakeGmail(msg("m1"))), owners=PAT, reader=stub(OTHER))
    assert "gmail:m1" in ri.answered_by(sent, "survey-2027").of(copies[OTHER])      # the copy the reading names is answered too


class FakePayhoaOf:
    """Two PayHOA submissions, from units 101 and 102."""

    def list_form_submissions(self, form_id):
        return [{"id": 1001, "status": "pending"}, {"id": 1002, "status": "pending"}]

    def get_form_submission(self, org, sid):
        unit = {1001: "101 Example Way", 1002: "102 Example Way"}[sid]
        return {"submission": {"id": sid, "membershipId": 50 + sid % 10, "createdAt": "2026-10-04T10:00:00Z",
                               "unit": {"title": unit}, "membership": {"name": "A Name"}}}
