"""Who was sent a copy and has not responded (docs/arrivals-design.md, "The sent-copy catalog"): the sent-copy catalog less the
answers kept on disk, the owners never sent a copy, the ages of what it was read from, and its three faces: the task, the
command (``jason responses --outstanding``), and the board's tool (``outstanding_responses``).

Made-up and offline: the fakes of ``test_response_inbox`` and ``test_responses_command``, a made-up PayHOA catalog on disk,
and a socket that refuses every connection. Nothing reaches a service, a mailbox, or an owner's data."""

from __future__ import annotations

import json
import os
import socket
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from test_response_inbox import Assoc, FakeGmail, FakePayhoa, clients, data, msg  # noqa: F401
from test_responses_command import Agent, clock, env, hand, no_private, run  # noqa: F401

from jason import api
from jason.community.form_refs import Channel as MarkerChannel, make
from jason.community.response_inbox import Channel
from jason.mcp import response_inbox as tools
from jason.tasks import response_inbox as ri
from jason.tasks.form_references import STORE, record
from jason.tasks.response_inbox import OwnerRef, ResponseError
from jason.tasks.response_outstanding import outstanding

UTC = timezone.utc
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=2)
PEOPLE = ((11, "Pat Example", "pat@example.org", 1, "101 EXAMPLE WAY"), (12, "Ben Sample", "ben@example.org", 2, "102 EXAMPLE WAY"),
          (13, "Cy Other", "cy@example.org", 3, "103 EXAMPLE WAY"), (14, "Dee Fictional", "dee@example.org", 4, "104 EXAMPLE WAY"),
          (15, "Eve Holder", "eve@example.org", 5, "105 EXAMPLE WAY"))


def ref(n: int) -> str:
    return make("AC", 2027, MarkerChannel.EMAIL, membership_id=10 + n, unit_id=n).text


def catalog_on_disk(data, *, copies=(1, 2, 3), sent_stamp=True):
    """Copies for the first three owners (Pat, Ben, Cy), a mailing, and a copy of another year's request that is not this one's."""
    for n in copies:
        record(data, ref(n), form="owner-info", year=2027, membershipId=10 + n, unitId=n, unit=f"10{n} Example Way",
               channel="email")
    record(data, make("AC", 2027, MarkerChannel.MAIL).text, form="owner-info", year=2027, channel="MAIL",
           identity="campaign", batch="owner-info-2027-mail")
    record(data, make("AC", 2026, MarkerChannel.EMAIL, membership_id=11, unit_id=1).text, form="owner-info", year=2026,
           membershipId=11, unitId=1, unit="101 Example Way", channel="email")           # last year's: not this request's
    path = data / STORE
    stored = json.loads(path.read_text(encoding="utf-8"))
    for key, entry in stored.items():                                                    # sent on known days
        entry["firstSent"] = entry["lastSent"] = "2026-10-01T15:00:00+00:00"
    path.write_text(json.dumps(stored), encoding="utf-8")
    stamp = (NOW - timedelta(hours=5)).timestamp()
    os.utime(path, (stamp, stamp))


def owners_on_disk(data):
    con = sqlite3.connect(data / "payhoa.db")
    con.execute("create table people (id, name, email)")
    con.execute("create table units (id, label, raw_json)")
    for pid, name, email, unit, label in PEOPLE:
        con.execute("insert into people values (?, ?, ?)", (pid, name, email))
        con.execute("insert into units values (?, ?, ?)", (unit, label, json.dumps({"owners": [{"membershipId": pid, "deletedAt": None}]})))
    con.commit()
    con.close()
    stamp = (NOW - timedelta(hours=30)).timestamp()
    os.utime(data / "payhoa.db", (stamp, stamp))


class Submissions(FakePayhoa):
    """PayHOA's list: Ben (102) and Eve (105, who was never sent a copy) signed in and answered."""

    def __init__(self) -> None:
        super().__init__({1002: ("pending", 12, "2026-10-03T10:00:00Z", "102 Example Way", "Ben Sample"),
                          1005: ("pending", 15, "2026-10-04T10:00:00Z", "105 Example Way", "Eve Holder")})


@pytest.fixture
def board(data):
    """Three copies sent (Pat, Ben, Cy), a mailing; Pat answered by email, Ben and Eve through PayHOA; Cy has not."""
    catalog_on_disk(data)
    owners_on_disk(data)
    ri.check(data, Assoc(), clients=clients(FakeGmail(msg("m1", frm="Pat <pat@example.org>")), Submissions()), by="scheduler",
             now=NOW, tests=(), owners={"pat@example.org": OwnerRef("101 Example Way", "Pat Example", 1, 11)})
    return data


@pytest.fixture
def offline(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a network connection was attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)


# -- the task ---------------------------------------------------------------------------------------------------------------

def test_the_copies_sent_less_the_answers_are_who_has_not_responded(board, offline):
    body = outstanding(board, Assoc(), now=LATER)
    [req] = body["requests"]
    assert (req["request"], req["sent"], req["answered"], req["notResponded"]) == ("survey-2027", 3, 2, 1)
    [waiting] = req["outstanding"]
    assert (waiting["unit"], waiting["owner"], waiting["channel"], waiting["sentAt"][:10]) == (
        "103 Example Way", "Cy Other", "email", "2026-10-01")
    assert waiting["daysSinceSent"] == 3 and waiting["reference"] == ref(3)              # sent Oct 1 15:00; now Oct 5 14:00
    done = {row["unit"]: row["answeredBy"] for row in req["answeredCopies"]}
    assert done == {"101 Example Way": ["gmail:m1"], "102 Example Way": ["payhoa:1002"]}
    assert req["returnBy"] == "2026-10-23" and req["year"] == 2027
    assert [m["batch"] for m in req["mailings"]] == ["owner-info-2027-mail"]               # last year's copy is not this request's
    assert all(key in row for row in req["outstanding"] for key in ("unit", "owner", "channel", "sentAt", "lastSent"))
    text = json.dumps(body)
    assert "@" not in text and "pat@example.org" not in text                             # names and units only


def test_owners_never_sent_a_copy_are_a_second_short_list_and_an_answer_without_a_copy_is_not_listed(board, offline):
    [req] = outstanding(board, Assoc(), now=LATER)["requests"]
    assert [(row["unit"], row["owner"]) for row in req["neverAsked"]] == [("104 EXAMPLE WAY", "Dee Fictional")]
    assert req["neverAskedAnswered"] == 1                                               # Eve was never sent a copy, and answered
    assert "no recipients" in req["note"] and "owner-info-2027-mail" in req["note"]      # a mailing lists none


def test_the_ages_of_the_catalog_the_owner_list_and_the_last_check_are_stated(board, offline):
    body = outstanding(board, Assoc(), now=LATER)
    assert body["catalog"]["exists"] and body["catalog"]["ageHours"] == 7.0 and body["catalog"]["copies"] == 4
    assert body["catalog"]["mailings"] == 1 and body["catalog"]["newestSent"].startswith("2026-10-01")
    assert body["ownerList"]["exists"] and body["ownerList"]["ageHours"] == 32.0
    assert body["lastCheck"]["at"] == "2026-10-05T12:00:00+00:00" and body["lastCheck"]["ageHours"] == 2.0
    assert body["at"] == "2026-10-05T14:00:00+00:00" and "catalog" in body["note"]


def test_no_catalog_no_owner_list_and_no_check_are_said_not_assumed(data, offline):
    body = outstanding(data, Assoc(), now=NOW)
    [req] = body["requests"]
    assert not body["catalog"]["exists"] and body["catalog"]["ageHours"] is None and body["catalog"]["copies"] == 0
    assert body["lastCheck"]["at"] == "" and not body["ownerList"]["exists"]
    assert (req["sent"], req["notResponded"], req["outstanding"]) == (0, 0, [])
    assert req["neverAsked"] is None and "no owner list is on disk" in req["neverAskedNote"]


def test_a_request_the_profile_does_not_have_is_refused_and_a_named_one_narrows(board, offline):
    with pytest.raises(ResponseError, match="no request 'another'"):
        outstanding(board, Assoc(), request="another")
    assert [r["request"] for r in outstanding(board, Assoc(), request="survey-2027", now=NOW)["requests"]] == ["survey-2027"]
    assert outstanding(board, type("Quiet", (), {"response_requests": lambda self: (), "payhoa_tags": lambda self: ()})(),
                       now=NOW)["requests"] == []


def test_a_dismissed_arrival_is_not_an_answer_and_a_superseded_one_is(board, offline):
    ri.dismiss(board, "gmail:m1", by="Secretary", why="a question, not the form")
    [req] = outstanding(board, Assoc(), now=LATER)["requests"]
    assert sorted(row["unit"] for row in req["outstanding"]) == ["101 Example Way", "103 Example Way"]
    assert (req["sent"], req["answered"], req["notResponded"]) == (3, 1, 2)


def test_the_owner_list_can_be_given_for_a_unit_with_two_owners(board, offline):
    from types import SimpleNamespace as NS

    units = [NS(unit_id=3, label="103 EXAMPLE WAY", owners=[NS(membership_id=13, name="Cy Other"),
                                                           NS(membership_id=16, name="Dana Other")]),
             NS(unit_id=1, label="101 EXAMPLE WAY", owners=[NS(membership_id=11, name="Pat Example")])]
    [req] = outstanding(board, Assoc(), now=LATER, units=units)["requests"]
    assert [(r["owner"], r["unitHasASentCopy"]) for r in req["neverAsked"]] == [("Dana Other", True)]   # a co-owner, not asked


# -- the command ------------------------------------------------------------------------------------------------------------

def test_the_command_prints_who_has_not_responded_with_the_ages_and_no_address(env, board, capsys, monkeypatch, clock):
    clock.now = LATER
    code, out, err = run(env, capsys, "responses", "--outstanding")
    assert code == 0 and not err
    no_private(out)
    assert "Who was sent a copy and has not responded" in out and "Disk only" in out
    assert "survey-2027: Owner survey (return by 2026-10-23)" in out
    assert "3 copies sent, 2 answered, 1 not responded" in out
    assert "103 Example Way" in out and "Cy Other" in out and "email" in out and "sent 2026-10-01 (3d)" in out
    assert "101 Example Way" not in out.split("Sent a copy and not responded")[1].split("Never")[0]    # the answered are not listed
    assert "Never sent a copy (no copy recorded; 1 more answered anyway)" in out and "Dee Fictional" in out
    assert "Eve Holder" not in out
    assert "sent-copy catalog: data/forms/references.json, written 2026-10-05 07:00 (7h ago); 4 copies on record, 1 mailing(s)" in out
    assert "owner list: data/payhoa.db, written 2026-10-04 06:00 (32h ago)" in out
    assert "last check that succeeded: 2026-10-05 12:00 (2h ago)" in out
    assert "owner-info-2027-mail" in out and "answered" in out
    code, out, _ = run(env, capsys, "responses", "--outstanding", "--json")
    body = json.loads(out)
    assert code == 0 and body["requests"][0]["notResponded"] == 1 and body["catalog"]["ageHours"] == 7.0
    assert "@" not in out and no_private(out) is None


def test_the_command_says_what_is_missing_and_refuses_a_stray_option_or_an_unknown_request(env, capsys, monkeypatch, clock):
    code, out, _ = run(env, capsys, "responses", "--outstanding")
    assert code == 0 and "none on disk" in out and "last check: none has succeeded yet" in out
    assert "No emailed copy is on record for this request." in out and "no owner list is on disk" in out
    code, _, err = run(env, capsys, "responses", "--outstanding", "--state", "new")
    assert code == 2 and "--state does not go with --outstanding" in err
    code, _, err = run(env, capsys, "responses", "--outstanding", "--request", "another")
    assert code == 2 and err.startswith("jason responses: the profile has no request 'another'")
    code, _, err = run(env, capsys, "responses", "--outstanding", "--list")
    assert code == 2                                                                      # one action at a time


# -- the tool and the python interface ---------------------------------------------------------------------------------------

def test_the_board_tool_reads_disk_only_and_carries_its_caveats(board, monkeypatch, offline):
    monkeypatch.setattr("jason.community.community", lambda: Assoc())
    monkeypatch.setattr(ri, "now_utc", lambda: LATER)
    out = tools.outstanding_responses(data_dir=board)
    assert out["found"] and out["requests"][0]["notResponded"] == 1 and out["requests"][0]["outstanding"][0]["owner"] == "Cy Other"
    assert out["catalog"]["ageHours"] == 7.0 and out["lastCheck"]["ageHours"] == 2.0
    assert {c["channel"] for c in out["lastCheck"]["channels"]} == {c.value for c in Channel}      # never checked ones say so
    assert any("catalog" in c and "live read" in c for c in out["caveats"]) and any("Names and units only" in c for c in out["caveats"])
    assert "@" not in json.dumps(out)
    assert "repeat the caveats" in tools.outstanding_responses.__doc__ and "disk only" in tools.outstanding_responses.__doc__.lower()
    assert api.outstanding_responses is tools.outstanding_responses
    unknown = tools.outstanding_responses(request="another", data_dir=board)
    assert unknown["found"] is False and "no request 'another'" in unknown["reason"] and unknown["caveats"]


def test_the_board_tool_says_when_the_profile_watches_nothing_or_the_store_is_unreadable(data, monkeypatch, offline):
    monkeypatch.setattr("jason.community.community", lambda: type("Quiet", (), {
        "response_requests": lambda self: (), "payhoa_tags": lambda self: ()})())
    quiet = tools.outstanding_responses(data_dir=data)
    assert quiet["found"] is False and "watches no request" in quiet["reason"] and quiet["caveats"]

    def broken():
        raise RuntimeError("the profile would not load")

    monkeypatch.setattr("jason.community.community", broken)
    out = tools.outstanding_responses(data_dir=data)
    assert out["found"] is False and "could not be read" in out["reason"] and out["caveats"]
