"""The board's responses tools (``new_responses``, ``response``; jason.mcp.response_inbox): the inbox read from disk, never
a live call, never an exception, nothing private in the output.

Made-up everything: a fake Gmail and PayHOA to fill the inbox through the real check, a stub reader for the scan, and a tmp
data folder. No service, Keeper, mailbox, or owner's data is reached."""

from __future__ import annotations

import json
import re
import socket
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason import api
from jason.community import form_refs
from jason.community.forms import (AnswerCycle, FormImport, FormKey, FormQuestion, FormTemplate, ImportRule, QuestionKind,
                                   CONTACT)
from jason.community.response_inbox import Channel, ResponseRequest, State
from jason.mcp import response_inbox as tools
from jason.mcp.server import ALL_TOOLS, PROFILES, tools_for
from jason.tasks import form_references
from jason.tasks import response_inbox as ri
from jason.tasks.response_inbox import OwnerRef

UTC = timezone.utc
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=2, minutes=30)
CYCLE = AnswerCycle(2027, date(2026, 10, 1), return_by=date(2026, 10, 23), reports_mailed=date(2026, 12, 1))
FORM = FormTemplate(FormKey.OWNER_INFO, "Owner information", "Civil Code 4041", "A made-up form.", (
    FormQuestion("Your name", key="name"),
    FormQuestion("Unit address", key="unit-address", required=False),
    FormQuestion("Delivery", QuestionKind.CHECKBOX, required=False, options=("By email", "By mail"), key="delivery"),
    FormQuestion("Email", QuestionKind.EMAIL, required=False, key="email"),
    FormQuestion("Phone", QuestionKind.SHORT, required=False, key="phone"),
    FormQuestion("Second mailing address", QuestionKind.SHORT, required=False, key="second-mailing-address")))
GOOGLE = FormImport("copy-2027", "gform1", FormKey.OWNER_INFO, "Google copy", (
    ImportRule("Unit", "unit-address"), ImportRule("Your name", f"{CONTACT}name", role="owner")))
EMAIL_MARK = "AC27E"
MARKER = form_refs.make("AC", 2027, form_refs.Channel.EMAIL, membership_id=11, unit_id=1).text    # the copy sent to unit 1
UNIT = "101 Example Way"
OWNERS = {"pat@example.org": OwnerRef(UNIT, "Pat Example", 1, 11)}
CHECK_LINE = "this reads what the last check kept; `jason responses --check` is the live read"


class Assoc:
    org_id = 7

    def response_requests(self):
        return (ResponseRequest("survey-2027", "Owner survey", FORM, CYCLE, payhoa_form="owner-info", imports=(GOOGLE,),
                                marker_campaigns=(EMAIL_MARK,)),)

    def email_domains(self):
        return ("assoc.example",)

    def payhoa_tags(self):
        return ()


def msg(mid, frm="Pat Example <pat@example.org>", day=4, subject="My form", hour=15):
    ms = int(datetime(2026, 10, day, hour, tzinfo=UTC).timestamp() * 1000)
    return {"id": mid, "threadId": f"t{mid}", "internalDate": str(ms), "labels": ["INBOX"],
            "headers": {"From": frm, "To": "Office <office@assoc.example>", "Subject": subject},
            "attachments": [{"name": "form.pdf", "type": "application/pdf", "size": 90_000, "attachmentId": f"att-{mid}"}]}


class FakeGmail:
    def __init__(self, *messages):
        self.messages = {m["id"]: m for m in messages}

    def iter_messages(self, query, *, page_size=100, limit=2000):
        for mid, m in self.messages.items():
            yield {"id": mid, "threadId": m["threadId"]}

    def get_metadata(self, mid, headers=()):
        return self.messages[mid]

    def get_attachment(self, mid, attachment_id):
        return b"%PDF-1.4 made up"


class FakePayhoa:
    ROWS = {1001: ("pending", 11, "2026-10-04T10:00:00Z", UNIT, "Ana Example"),
            1002: ("complete", 12, "2026-10-03T10:00:00Z", "102 Example Way", "Ben Sample")}

    def list_form_submissions(self, form_id):
        return [{"id": i, "status": r[0]} for i, r in self.ROWS.items()]

    def get_form_submission(self, org, sid):
        status, member, created, unit, name = self.ROWS[sid]
        return {"submission": {"id": sid, "membershipId": member, "createdAt": created, "unit": {"title": unit},
                               "membership": {"name": name}}}


def clients(gmail=None, payhoa=None):
    out = {}
    if gmail is not None:
        out[Channel.GMAIL] = lambda: gmail
    if payhoa is not None:
        out[Channel.PAYHOA] = lambda: payhoa
    return out


def reader(answers, marker=""):
    def read(path, request, layout, model):
        return ri.FileReading(path.name, "scan", {"delivery.by-mail": SimpleNamespace(value=True, how="mark", confidence=0.9),
                                                  "email": SimpleNamespace(value=answers.get("email", ""), how="writing",
                                                                           confidence=0.6)},
                              dict(answers), marker, "text" if marker else "", ["a note from the reader"], 12, 0.4)
    return read


def not_the_form(path, request, layout, model):
    return ri.FileReading(path.name, "not the form", notes=["its printed lines do not match"])


@pytest.fixture
def data(tmp_path):
    (tmp_path / "payhoa").mkdir()
    (tmp_path / "payhoa" / "forms.json").write_text(json.dumps({"forms": [{"key": "owner-info", "formId": 900}]}),
                                                    encoding="utf-8")
    return tmp_path


@pytest.fixture
def clock(monkeypatch):
    """The inbox's clock, so an age is the same on any day."""
    monkeypatch.setattr(ri, "now_utc", lambda: LATER)


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def fill(data):
    """One arrival in each state: new (m2), seen (PayHOA 1002, complete), read (m3), keyed (m1), recorded (PayHOA 1001),
    dismissed (m4)."""
    gmail = FakeGmail(msg("m1"), msg("m2", frm="Sam Newcomer <sam@example.net>", day=5, hour=9), msg("m3", frm="Quinn Writer <quinn@example.net>", day=3),
                      msg("m4", frm="Rae Other <rae@example.net>", day=2))
    ri.check(data, Assoc(), clients=clients(gmail, FakePayhoa()), by="scheduler", now=NOW, tests=(), owners=OWNERS)
    ri.read(data, Assoc(), "gmail:m1", by="Secretary", clients=clients(gmail), owners=OWNERS,
            reader=reader({"name": "Pat Example 916-555-0142", "email": "pat.private@example.org", "delivery": ["By mail"],
                           "phone": "(916) 555-0199", "second-mailing-address": "12 Other Street, Anytown, CA 95000",
                           "unit-address": UNIT}, MARKER))
    ri.confirm(data, Assoc(), "gmail:m1", by="Treasurer", why="checked against the scan")
    ri.read(data, Assoc(), "gmail:m3", by="Secretary", clients=clients(gmail), owners={},
            reader=reader({"name": "Quinn Writer", "email": "quinn@example.net"}))
    ri.dismiss(data, "gmail:m4", by="Treasurer", why="a flyer, not the form")
    ri.mark_recorded(data, "payhoa:1001", by="Treasurer", why="the writes were made")
    return gmail


# -- a miss is a reason, never an exception ------------------------------------------------------------------------------

def test_an_empty_inbox_is_a_miss_with_its_reason_and_every_tool_says_it_is_the_last_check(data):
    out = tools.new_responses(data_dir=data)
    assert out["found"] is False and "no check has been run" in out["reason"] and out["arrivals"] == [] and out["count"] == 0
    assert out["note"] == CHECK_LINE and out["caveats"][0].startswith(CHECK_LINE)
    assert [c["channel"] for c in out["checked"]] == ["payhoa", "gmail", "mail", "forms", "manual"]
    checked = [c for c in out["checked"] if c["channel"] != "manual"]
    assert all(c["ended"] == "never checked" and c["ageHours"] is None and c["lastOk"] == "" for c in checked)
    assert out["checked"][-1]["ended"] == "keyed by a person (nothing to check)"          # a person adds these: none is checked
    for miss in (tools.response("gmail:nope", data_dir=data), tools.response("", data_dir=data),
                 tools.response("  ", data_dir=data)):
        assert miss["found"] is False and miss["reason"] and miss["note"] == CHECK_LINE and miss["caveats"]
    assert "give an arrival's id" in tools.response("", data_dir=data)["reason"]


def test_a_bad_filter_or_an_unreadable_inbox_is_a_miss_not_an_exception(data):
    assert "no state 'bogus'" in tools.new_responses(state="bogus", data_dir=data)["reason"]
    assert "no channel 'fax'" in tools.new_responses(channel="fax", data_dir=data)["reason"]
    (data / "responses").mkdir()
    (data / "responses" / "inbox.json").write_text("{not json", encoding="utf-8")
    broken = tools.new_responses(data_dir=data)
    assert broken["found"] is False and "could not be read" in broken["reason"] and broken["caveats"]
    assert tools.response("gmail:m1", data_dir=data)["found"] is False


def test_a_filter_that_matches_nothing_says_what_the_inbox_holds(data, clock):
    fill(data)
    out = tools.new_responses(unit="999 Nowhere", state="all", data_dir=data)
    assert out["found"] is False and "no arrival matches" in out["reason"] and out["count"] == 0
    assert out["inbox"] == {"new": 1, "seen": 1, "read": 1, "keyed": 1, "recorded": 1, "dismissed": 1}
    assert out["checked"]                                              # even a miss says when each channel was last checked


# -- the list: states, channels, ages ------------------------------------------------------------------------------------

def test_new_responses_lists_each_state_with_the_channels_last_check_and_its_age(data, clock):
    fill(data)
    new = tools.new_responses(data_dir=data)
    assert new["found"] and new["state"] == "new" and [a["id"] for a in new["arrivals"]] == ["gmail:m2"]
    row = new["arrivals"][0]
    assert (row["channel"], row["who"], row["state"], row["attachments"], row["request"]) == (
        "gmail", "Sam Newcomer", "new", ["form.pdf"], "survey-2027")
    assert row["unit"] == "" and row["at"] == "2026-10-05T09:00:00+00:00" and row["ageHours"] == 5.5
    # the channels: the ones checked say when and how it ended, and their age at the (fixed) clock
    by_channel = {c["channel"]: c for c in new["checked"]}
    assert by_channel["gmail"]["ended"] == "ok" and by_channel["gmail"]["ageHours"] == 2.5
    assert by_channel["gmail"]["lastOk"] == "2026-10-05T12:00:00+00:00" and by_channel["payhoa"]["ageHours"] == 2.5
    assert by_channel["mail"]["ended"] == "ok" and by_channel["forms"]["ageHours"] == 2.5          # read from disk: no client
    assert new["note"] == CHECK_LINE and new["caveats"][0].startswith(CHECK_LINE)
    everything = tools.new_responses(state="all", data_dir=data)
    assert everything["count"] == 6 and everything["state"] == "all"
    assert [a["id"] for a in everything["arrivals"]] == sorted((a["id"] for a in everything["arrivals"]), key=lambda i: (
        next(x["at"] for x in everything["arrivals"] if x["id"] == i), i), reverse=True)           # newest first
    assert {a["state"] for a in everything["arrivals"]} == {"new", "seen", "read", "keyed", "recorded", "dismissed"}
    for state in ("seen", "read", "keyed", "recorded", "dismissed"):
        got = tools.new_responses(state=state, data_dir=data)
        assert got["count"] == 1 and got["arrivals"][0]["state"] == state, state
    assert tools.new_responses(state="ALL", data_dir=data)["count"] == 6 and tools.new_responses(state="", data_dir=data)["count"] == 6
    assert [a["id"] for a in tools.new_responses(channel="payhoa", state="all", data_dir=data)["arrivals"]] == [
        "payhoa:1001", "payhoa:1002"]
    assert {a["id"] for a in tools.new_responses(unit="101 example", state="all", data_dir=data)["arrivals"]} >= {
        "gmail:m1", "payhoa:1001"}
    assert tools.new_responses(request="another-request", state="all", data_dir=data)["found"] is False
    recent = tools.new_responses(days=1, state="all", data_dir=data)                     # the last day before the fixed clock
    assert {a["id"] for a in recent["arrivals"]} == {"gmail:m2", "gmail:m1"}


def test_a_failed_channel_shows_how_it_ended_and_its_age(data, monkeypatch):
    from jason.google.errors import GoogleAuthRequired

    def refuse():
        raise GoogleAuthRequired("sign in again")

    ri.check(data, Assoc(), clients={Channel.PAYHOA: lambda: FakePayhoa(), Channel.GMAIL: refuse}, by="scheduler", now=NOW,
             tests=(), owners={})
    monkeypatch.setattr(ri, "now_utc", lambda: NOW + timedelta(hours=30))
    out = tools.new_responses(state="all", data_dir=data)
    gmail = next(c for c in out["checked"] if c["channel"] == "gmail")
    assert gmail["ended"] == "sign-in" and gmail["lastOk"] == "" and gmail["ageHours"] is None and gmail["reason"]
    payhoa = next(c for c in out["checked"] if c["channel"] == "payhoa")
    assert payhoa["ended"] == "ok" and payhoa["ageHours"] == 30.0                         # old: the board can see how old


# -- one arrival ---------------------------------------------------------------------------------------------------------

def test_response_shows_the_reading_as_evidence_the_keyed_answers_the_acts_and_what_is_left(data, clock):
    fill(data)
    one = tools.response("gmail:m1", data_dir=data)
    assert one["found"] and one["arrival"]["state"] == "keyed" and one["files"] == ["form.pdf"]
    reading = one["reading"]
    assert "never an answer" in reading["label"] and reading["isTheForm"] and reading["how"] == "scan"
    assert reading["by"] == "Secretary" and reading["fields"]["delivery.by-mail"] == {"value": True, "how": "mark",
                                                                                      "confidence": 0.9}
    assert reading["fields"]["email"]["confidence"] == 0.6 and reading["fields"]["email"]["how"] == "writing"
    assert reading["owner"] == {"unit": UNIT, "name": "Pat Example", "matchedBy": "the sender's address"}
    assert reading["reference"]["text"] == MARKER and reading["reference"]["campaignMatchesRequest"]
    assert reading["reference"]["copy"]["found"] is False and "no sent copy" in reading["reference"]["copy"]["reason"]
    keyed = one["keyed"]
    assert keyed["by"] == "Treasurer" and keyed["source"] == "email:m1" and "reaches PayHOA only through" in keyed["label"]
    assert keyed["answers"]["unit-address"] == UNIT                                       # a unit's own address is the unit's
    assert [(a["act"], a["by"]) for a in one["acts"]] == [("kept", "scheduler"), ("read", "Secretary"), ("confirm", "Treasurer")]
    assert [s["step"] for s in one["left"]] == ["apply"] and "--yes" in one["left"][0]["says"]
    assert one["note"] == CHECK_LINE and one["checked"] and one["caveats"]


def test_what_is_left_follows_the_state(data, clock):
    fill(data)
    left = lambda i: [s["step"] for s in tools.response(i, data_dir=data)["left"]]          # noqa: E731
    assert left("gmail:m2") == ["read", "confirm", "apply"]                                  # an email nobody has read
    assert left("gmail:m3") == ["confirm", "apply"]                                          # read, a form found
    assert left("gmail:m1") == ["apply"]                                                     # keyed
    assert left("payhoa:1002") == ["apply"]                                                  # structured, seen
    assert left("payhoa:1001") == [] and left("gmail:m4") == []                              # recorded, dismissed
    assert tools.response("gmail:m3", data_dir=data)["reading"]["owner"] == {}               # no owner matched the sender
    assert "recorded" not in dump(tools.response("gmail:m3", data_dir=data)["left"])


def test_a_reading_that_found_no_form_leaves_a_decision(data, clock):
    gmail = FakeGmail(msg("m9"))
    ri.check(data, Assoc(), clients=clients(gmail), by="scheduler", channels=[Channel.GMAIL], now=NOW, owners={})
    ri.read(data, Assoc(), "gmail:m9", by="Secretary", clients=clients(gmail), owners={}, reader=not_the_form)
    one = tools.response("gmail:m9", data_dir=data)
    assert one["reading"]["isTheForm"] is False and one["reading"]["how"] == "not the form" and one["keyed"] is None
    assert [s["step"] for s in one["left"]] == ["decide"] and "dismiss" in one["left"][0]["says"]


def test_the_printed_reference_is_compared_with_the_copy_jason_sent(data, clock):
    fill(data)
    marker = MARKER
    form_references.record(data, marker, form="owner-info", year=2027, membershipId=11, unitId=1, unit=UNIT, channel="email")
    copy = tools.response("gmail:m1", data_dir=data)["reading"]["reference"]["copy"]
    assert copy["found"] and copy["matchesUnit"] is True and copy["sentToUnit"] == UNIT and copy["readUnit"] == UNIT
    assert copy["channel"] == "email" and copy["year"] == 2027 and copy["reference"] == marker
    form_references.record(data, marker, unit="202 Example Way", unitId=2)                    # the copy went to another unit
    other = tools.response("gmail:m1", data_dir=data)["reading"]["reference"]["copy"]
    assert other["found"] and other["matchesUnit"] is False and other["sentToUnit"] == "202 Example Way"


def test_a_hyphenated_id_is_the_same_arrival(data, clock):
    fill(data)
    assert tools.response("gmail-m1", data_dir=data)["arrival"]["id"] == "gmail:m1"
    assert tools.response("payhoa-1001", data_dir=data)["arrival"]["id"] == "payhoa:1001"


def test_a_superseded_arrival_is_marked_and_leaves_nothing_to_do(data, clock):
    gmail = FakeGmail(msg("m1", day=3), msg("m2", day=5))
    ri.check(data, Assoc(), clients=clients(gmail), by="scheduler", channels=[Channel.GMAIL], now=NOW, owners=OWNERS)
    one = tools.response("gmail:m1", data_dir=data)
    assert one["arrival"]["supersededBy"] == "gmail:m2" and "later answer" in one["superseded"] and one["left"] == []
    assert tools.response("gmail:m2", data_dir=data)["superseded"] == ""


# -- nothing private -----------------------------------------------------------------------------------------------------

def test_no_email_address_or_phone_number_reaches_the_output(data, clock):
    fill(data)
    everything = [tools.new_responses(state="all", data_dir=data)] + [
        tools.response(a, data_dir=data) for a in ("gmail:m1", "gmail:m2", "gmail:m3", "gmail:m4", "payhoa:1001", "payhoa:1002")]
    text = dump(everything)
    assert "@" not in text and not re.search(r"\d{3}[-. ]\d{3}[-. ]\d{4}", text) and "(916)" not in text
    assert "pat.private" not in text and "quinn@" not in text
    keyed = tools.response("gmail:m1", data_dir=data)["keyed"]
    assert keyed["answers"]["email"] == "[email]" and keyed["answers"]["phone"] == "[phone]"
    assert keyed["answers"]["second-mailing-address"] == "[address]"
    assert keyed["answers"]["name"] == "Pat Example [phone]"                              # masked where it sits
    assert keyed["contacts"] == [{"role": "owner", "name": "Pat Example", "email": "[email]"}]
    reading = tools.response("gmail:m1", data_dir=data)["reading"]
    assert reading["answers"]["email"] == "[email]" and reading["fields"]["email"]["value"] == "[email]"
    # the stored files hold what a person confirmed (the owner's own entry); the tool is what masks it
    assert "pat.private@example.org" in (data / "responses" / "keyed" / "gmail-m1.json").read_text(encoding="utf-8")


def test_a_contact_value_in_a_note_or_an_act_is_masked_too(data, clock):
    fill(data)
    ri.log_act(data, "note", "gmail:m2", "Secretary", "call back at 916-555-0100 or pat.private@example.org")
    text = dump(tools.response("gmail:m2", data_dir=data))
    assert "@" not in text and "916-555-0100" not in text and "[phone]" in text and "[email]" in text


# -- read only, no live call ---------------------------------------------------------------------------------------------

def test_the_tools_write_nothing_and_make_no_network_call(data, clock, monkeypatch):
    fill(data)

    def snapshot():
        return {str(p.relative_to(data)): (p.stat().st_mtime_ns, p.stat().st_size) for p in data.rglob("*") if p.is_file()}

    before = snapshot()

    def boom(*args, **kwargs):
        raise AssertionError("a tool made a network call")

    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    tools.new_responses(state="all", data_dir=data)
    for arrival in ("gmail:m1", "gmail:m2", "payhoa:1001"):
        assert tools.response(arrival, data_dir=data)["found"]
    assert tools.response("gmail:nope", data_dir=data)["found"] is False
    assert snapshot() == before


# -- where the tools are served ------------------------------------------------------------------------------------------

def test_the_tools_are_in_the_board_profile_the_full_set_and_the_python_interface():
    assert {"new_responses", "response", "outstanding_responses"} <= set(PROFILES["board"])
    assert "new_responses" not in PROFILES["governance"] and "response" not in PROFILES["onboarding"]
    assert "outstanding_responses" not in PROFILES["governance"] and "outstanding_responses" not in PROFILES["onboarding"]
    assert len(PROFILES["board"]) == 45 and len(tools_for("board")) == 45 and tools_for("board")[0].__name__ == "board_digest"
    served = {t.__name__: t for t in ALL_TOOLS}
    assert served["new_responses"] is tools.new_responses and served["response"] is tools.response
    assert served["outstanding_responses"] is tools.outstanding_responses
    assert len(served) == len(ALL_TOOLS)                                                  # no tool is listed twice
    assert api.new_responses is tools.new_responses and api.response is tools.response
    assert api.outstanding_responses is tools.outstanding_responses
    assert {"new_responses", "response", "outstanding_responses"} <= set(api.__all__)


def test_each_tool_carries_its_caveats_and_names_the_live_read():
    assert tools.CHECK_LINE == CHECK_LINE
    for tool in tools.TOOLS:
        assert "repeat the caveats" in (tool.__doc__ or ""), tool.__name__
    assert "`jason responses --check` is the live read" in tools.new_responses.__doc__
    assert any("evidence" in c and "never an answer" in c for c in tools.CAVEATS)
    assert any("jason owner-info --apply --yes" in c for c in tools.CAVEATS)
    assert not any("@" in c for c in tools.CAVEATS)
