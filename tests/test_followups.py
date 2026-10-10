"""Follow-ups, the campaign funnel, and the manual intake channel (docs/followups-design.md, build steps 1 and 2).

Made up and offline: a made-up association (``World``, which only says what its forms and requests are), temporary data folders,
a fake clock (``TODAY``), and a socket that refuses every connection. Nothing reaches a service, a mailbox, a model, or an
owner's data, and no profile's facts are used.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest
from test_campaigns import CYCLE as CAMPAIGN_CYCLE, PROCESS, Stub
from test_response_outstanding import owners_on_disk

from jason import api
from jason.community.form_library import Clock, DayKind, SetBy
from jason.community.form_refs import Channel as MarkerChannel, make
from jason.community.forms import AnswerCycle
from jason.community.response_inbox import Arrival, Channel, ResponseRequest, State
from jason.mcp import followups as tools
from jason.mcp.server import ALL_TOOLS, PROFILES, tools_for
from jason.tasks import campaign_funnel, campaigns, followups as fu, form_references, notice_ledger, response_inbox as ri
from jason.tasks.notice_ledger import Attempt, Delivery
from jason.tasks.response_inbox import ResponseError

UTC = timezone.utc
TODAY = date(2026, 10, 5)                         # a Monday
NOON = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
CYCLE = AnswerCycle(2027, date(2026, 10, 1), return_by=date(2026, 10, 23), reports_mailed=date(2026, 12, 1))
REQUEST = ResponseRequest("annual-2027", "Annual information", PROCESS.template, CYCLE, payhoa_form="owner-info",
                          marker_campaigns=("KM27E", "KM27M"))
PRIVATE = ("pat@example.org", "eve@example.org", "916-555-0100", "PO Box 9")


class World(Stub):
    """A made-up association: its one form, its one request, and what the inbox asks of a ``Community``."""

    org_id = 7

    def __init__(self, *forms, requests=(REQUEST,)) -> None:
        super().__init__(*(forms or (PROCESS,)), requests=requests)

    def email_domains(self):
        return ("assoc.example",)

    def payhoa_tags(self):
        return ()


class Quiet(World):
    """An association whose profile watches no request, so no campaign is run from it."""

    def __init__(self) -> None:
        super().__init__(requests=())


def reference(n: int) -> str:
    return make("KM", 2027, MarkerChannel.EMAIL, membership_id=10 + n, unit_id=n).text


def sent(data, *numbers):
    """A copy sent to each owner (membership 10+n, unit n) on Oct 1, and one mailing; the catalog written 7 hours ago."""
    for n in numbers:
        form_references.record(data, reference(n), form="owner-info", year=2027, membershipId=10 + n, unitId=n,
                               unit=f"10{n} Example Way", channel="email")
    form_references.record(data, make("KM", 2027, MarkerChannel.MAIL).text, form="owner-info", year=2027, channel="MAIL",
                           batch="mail-b1")
    path = data / form_references.STORE
    stored = json.loads(path.read_text(encoding="utf-8"))
    for entry in stored.values():
        entry["firstSent"] = entry["lastSent"] = "2026-10-01T15:00:00+00:00"
    path.write_text(json.dumps(stored), encoding="utf-8")
    stamp = (NOON - timedelta(hours=7)).timestamp()
    os.utime(path, (stamp, stamp))


def arrival(aid, channel, unit, who, state=State.NEW, at="2026-10-03T10:00:00+00:00", **more):
    return Arrival(aid, "annual-2027", channel, at, who, unit, "Owner information", (), state, at, **more)


def keep(data, *rows, checked=True):
    inbox = ri.load_inbox(data)
    for row in rows:
        inbox.arrivals[row.id] = row
    if checked:
        inbox.channels["gmail"] = {"lastOk": "2026-10-05T10:00:00+00:00", "lastTried": "2026-10-05T10:00:00+00:00", "ended": "ok"}
    ri.save_inbox(data, inbox)


def ledger(data, *attempts):
    notice_ledger.save(data, attempts)


def bounced(n=4):
    return [Attempt("notice-1", 10 + n, n, f"10{n} Example Way", "email", "b1", reference(n), "2026-10-02T10:00:00+00:00",
                    Delivery.BOUNCED, "2026-10-03T10:00:00+00:00", "550 no such user"),
            Attempt("notice-1", 10 + n, n, f"10{n} Example Way", "letter", "mail-b1", "9001", "2026-10-01T09:00:00+00:00",
                    Delivery.RETURNED, "2026-10-04T10:00:00+00:00", "return to sender")]


@pytest.fixture
def data(tmp_path):
    return tmp_path


@pytest.fixture
def board(data):
    """Two campaigns for one request (emailed copies KM27E, a mailing KM27M). Copies went to owners 1 to 5 and a mailing.
    Owner 1 answered by email (not yet read), 2 by PayHOA, 3 by a person keying a phone call; 4's email bounced and the letter
    came back; 5 has not answered."""
    for channel in ("email", "mail"):
        campaigns.open_campaign(World(), "annual-info", channel=channel, cycle=CAMPAIGN_CYCLE, by="Pat Example", data_dir=data,
                                now=NOON)
    sent(data, 1, 2, 3, 4, 5)
    owners_on_disk(data)
    keep(data, arrival("gmail:m1", Channel.GMAIL, "101 Example Way", "Ana Example", at="2026-10-04T15:00:00+00:00"),
         arrival("payhoa:1002", Channel.PAYHOA, "102 Example Way", "Ben Sample"))
    ri.add_manual(data, World(), "annual-2027", by="Secretary", how="by phone", who="Cy Other", unit="103 Example Way", now=NOON)
    ledger(data, *bounced())
    return data


@pytest.fixture
def offline(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a network connection was attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)


def derived(data, world=None, **kw):
    return fu.derive(data, world or World(), today=TODAY, **kw)


def one(found, kind, **match):
    rows = [i for i in found if i.kind is kind and all(getattr(i, k) == v for k, v in match.items())]
    assert len(rows) == 1, [(i.kind.value, i.subject) for i in found]
    return rows[0]


# -- derived from a campaign's cycle ------------------------------------------------------------------------------------------

def test_a_campaigns_cycle_gives_the_reminder_the_return_by_the_entry_day_and_the_reports(board, offline):
    found = derived(board)
    remind = one(found, fu.FollowUpKind.REMIND, subject="KM27E")
    assert remind.due == date(2026, 10, 16) and remind.window_end == date(2026, 10, 23)        # 7 days before the return-by date
    assert remind.basis is fu.Basis.PROPOSED_POLICY and "proposed" in remind.cite and "proposed" in remind.due_note
    assert "board has not adopted a number" in remind.cite
    assert remind.outstanding == 1 and remind.names == ("105 Example Way (Eve Holder)",) and remind.state is fu.FollowUpState.UPCOMING
    assert remind.command.startswith("jason owner-info --email-batch --follow-up reminder") and remind.source == "campaign"
    back = one(found, fu.FollowUpKind.RETURN_BY, subject="KM27E")
    assert back.due == date(2026, 10, 23) and back.basis is fu.Basis.PERSON and "Pat Example" in back.cite
    enter = one(found, fu.FollowUpKind.ENTER_BY)
    assert enter.due == date(2026, 11, 1) and enter.basis is fu.Basis.LAW and "4041(b)(1)" in enter.cite
    assert enter.subject == "annual-2027" and enter.outstanding == 1 and enter.names == ("102 Example Way",)   # the PayHOA answer
    reports = one(found, fu.FollowUpKind.REPORTS_MAILED)
    assert reports.due == date(2026, 12, 1) and reports.basis is fu.Basis.LAW and "5300" in reports.cite
    close = one(found, fu.FollowUpKind.CLOSE, subject="KM27E")
    assert close.due == date(2026, 10, 30) and close.basis is fu.Basis.PROPOSED_POLICY
    assert len({i.id for i in found}) == len(found), "every item has its own id"
    assert [i.due for i in found] == sorted(i.due for i in found), "date order"


def test_a_campaigns_own_reminder_setting_is_a_persons_not_a_proposal(data, offline):
    campaigns.open_campaign(World(), "annual-info", channel="email", cycle=CAMPAIGN_CYCLE, by="Pat Example", data_dir=data,
                            options={fu.REMIND_OPTION: "10"}, now=NOON)
    remind = one(derived(data), fu.FollowUpKind.REMIND, subject="KM27E")      # KM27M, which the request also names, is read from it
    assert remind.due == date(2026, 10, 13) and remind.basis is fu.Basis.PERSON and remind.due_note == ""
    assert "10 days before" in remind.cite and "Pat Example" in remind.cite
    assert remind.outstanding is None and remind.reason                         # no catalog on disk: not known, with the reason


def test_a_closed_campaign_gives_no_items(board, offline):
    campaigns.close_campaign(board, "KM27E", by="Pat Example")
    campaigns.close_campaign(board, "KM27M", by="Pat Example")
    kinds = {i.kind for i in derived(board)}
    assert not kinds & {fu.FollowUpKind.REMIND, fu.FollowUpKind.RETURN_BY, fu.FollowUpKind.CLOSE, fu.FollowUpKind.ENTER_BY}


# -- derived from the notice ledger and the inbox ----------------------------------------------------------------------------

def test_a_bounced_notice_is_resent_by_mail_and_a_returned_letter_asks_for_an_address_each_with_its_authority(board, offline):
    found = derived(board)
    mail = one(found, fu.FollowUpKind.RESEND, cite="CIV 4041(e), 4040(a)(2)")
    assert mail.basis is fu.Basis.LAW and mail.due == date(2026, 10, 6)                # the outcome was read Oct 3, +3 days
    assert "first-class mail" in mail.what and mail.outstanding == 1 and mail.names == ("104 Example Way",)
    assert "proposed: 3 days after the outcome was read (2026-10-03)" in mail.due_note and "the law sets no day" in mail.due_note
    assert mail.command.startswith('jason owner-info --mail-batch --only "104 Example Way" --resend') and "--yes" in mail.command
    assert "dry run" in mail.command and mail.source == "ledger" and mail.subject == "notice-1"
    letter = one(found, fu.FollowUpKind.RESEND, cite="CIV 4050(b), 4041(c)")
    assert letter.basis is fu.Basis.PROPOSED_POLICY and letter.due == date(2026, 10, 7)


def test_a_member_another_delivery_reached_is_not_owed_a_resend(board, offline):
    ledger(board, Attempt("notice-1", 14, 4, "104 Example Way", "letter", "mail-b2", "9002", "2026-10-02T09:00:00+00:00",
                          Delivery.MAILED, "2026-10-04T09:00:00+00:00", ""))
    cites = {i.cite for i in derived(board) if i.kind is fu.FollowUpKind.RESEND}
    assert "CIV 4041(e), 4040(a)(2)" not in cites                                    # no resend: ``standing`` asks for an address only


def test_an_arrival_awaiting_review_is_a_review_item_at_each_stage(board, offline):
    keep(board, arrival("gmail:m2", Channel.GMAIL, "105 Example Way", "Eve Holder", State.READ, at="2026-10-02T10:00:00+00:00"),
         arrival("gmail:m3", Channel.GMAIL, "106 Example Way", "Fay Third", State.KEYED, at="2026-09-20T10:00:00+00:00"),
         arrival("gmail:m4", Channel.GMAIL, "107 Example Way", "Gus Fourth", State.RECORDED),
         arrival("gmail:m5", Channel.GMAIL, "108 Example Way", "Hal Fifth", State.DISMISSED))
    found = derived(board)
    reviews = {i.subject: i for i in found if i.kind is fu.FollowUpKind.REVIEW}
    assert set(reviews) == {"gmail:m1", "payhoa:1002", "gmail:m2", "gmail:m3"} | {i.subject for i in found if i.subject.startswith("manual:")}
    read = reviews["gmail:m1"]
    assert read.what.startswith("Read the returned form") and read.due == date(2026, 10, 7) and read.basis is fu.Basis.PROPOSED_POLICY
    assert read.command == "jason responses --read gmail:m1 --by NAME" and read.source == "inbox"
    assert "no number is adopted" in read.cite and read.due_note == "proposed: 3 days after 2026-10-04"
    assert reviews["gmail:m2"].what.startswith("Confirm the reading") and reviews["gmail:m2"].due == date(2026, 10, 5)
    assert reviews["gmail:m3"].what.startswith("Record the confirmed answer") and reviews["gmail:m3"].state is fu.FollowUpState.OVERDUE
    assert "needs no reading" not in reviews["payhoa:1002"].what and reviews["payhoa:1002"].what.startswith("Record the payhoa answer")
    assert all("@" not in i.what and i.outstanding == 1 for i in reviews.values())


def test_the_forms_association_clocks_give_a_requests_items_where_one_applies(data, offline):
    clocks = (Clock("acknowledge", "receipt", 1, DayKind.BUSINESS, SetBy.PROPOSED_POLICY, "", "nothing in the law"),
              Clock("respond", "receipt or service, whichever is earlier", 30, DayKind.CALENDAR, SetBy.STATUTE, "CIV 5935(a)(3)"),
              Clock("complete", "the acceptance received", 90, DayKind.CALENDAR, SetBy.STATUTE, "CIV 5940(a)"))
    world = World(replace(PROCESS, association_clocks=clocks))
    campaigns.open_campaign(world, "annual-info", channel="email", cycle=CAMPAIGN_CYCLE, by="Pat Example", data_dir=data, now=NOON)
    keep(data, arrival("gmail:m1", Channel.GMAIL, "101 Example Way", "Ana Example", at="2026-10-04T15:00:00+00:00"))   # a Sunday
    found = derived(data, world)
    ack = one(found, fu.FollowUpKind.ACKNOWLEDGE)
    assert ack.due == date(2026, 10, 5) and ack.state is fu.FollowUpState.DUE and ack.basis is fu.Basis.PROPOSED_POLICY
    assert "proposed" in ack.due_note and ack.subject == "gmail:m1"
    answer = one(found, fu.FollowUpKind.ANSWER_DUE)
    assert answer.due == date(2026, 11, 3) and answer.basis is fu.Basis.LAW and answer.cite == "CIV 5935(a)(3)"
    assert "complete" not in " ".join(i.what.lower() for i in found if i.source == "clock")      # a clock with no kind is skipped
    assert not [i for i in derived(data) if i.source == "clock"]                                  # a form with no clocks gives none


# -- stable ids and a person's acts -----------------------------------------------------------------------------------------

def test_ids_are_stable_across_runs_and_a_persons_acts_survive_a_re_derive(board, offline):
    first = {i.id: i for i in fu.items(board, World(), today=TODAY)}
    assert set(first) == {i.id for i in fu.items(board, World(), today=TODAY)} and all(k.startswith("fu-") for k in first)
    remind = one(list(first.values()), fu.FollowUpKind.REMIND, subject="KM27E")
    resend = one(list(first.values()), fu.FollowUpKind.RESEND, cite="CIV 4041(e), 4040(a)(2)")
    ending = one(list(first.values()), fu.FollowUpKind.CLOSE, subject="KM27E")
    fu.done(board, World(), remind.id, by="Pat Example", note="sent the reminder email", today=TODAY)
    fu.defer(board, World(), resend.id, to=date(2026, 10, 9), by="Pat Example", why="waiting for the owner to call back", today=TODAY)
    fu.drop(board, World(), ending.id, by="Pat Example", why="the board keeps it open", today=TODAY)
    again = {i.id: i for i in fu.items(board, World(), today=TODAY)}
    assert set(again) == set(first)
    assert again[remind.id].state is fu.FollowUpState.DONE and again[remind.id].by == "Pat Example" and again[remind.id].why == "sent the reminder email"
    assert again[resend.id].state is fu.FollowUpState.DEFERRED and again[resend.id].deferred_to == date(2026, 10, 9)
    assert again[resend.id].why == "waiting for the owner to call back"
    assert again[ending.id].state is fu.FollowUpState.DROPPED and again[ending.id].why == "the board keeps it open"
    log = fu.acts(board)
    assert [(r["act"], r["by"]) for r in log] == [("done", "Pat Example"), ("defer", "Pat Example"), ("drop", "Pat Example")]
    assert all(r["at"] and r["id"] for r in log)
    # a deferral comes back on its day: due, then overdue from it
    after = {i.id: i for i in fu.items(board, World(), today=date(2026, 10, 9))}
    assert after[resend.id].state is fu.FollowUpState.DUE
    assert {i.id: i for i in fu.items(board, World(), today=date(2026, 10, 12))}[resend.id].state is fu.FollowUpState.OVERDUE
    # the default view drops what is done, dropped, or deferred; --all keeps them
    shown = {i.id for i in fu.select(fu.items(board, World(), today=TODAY), today=TODAY)}
    assert not {remind.id, resend.id, ending.id} & shown
    assert {remind.id, resend.id, ending.id} <= {i.id for i in fu.select(fu.items(board, World(), today=TODAY), today=TODAY, everything=True)}


def test_an_id_changes_when_what_fixes_the_day_does_but_not_when_a_count_does(board, offline):
    before = one(derived(board), fu.FollowUpKind.REMIND, subject="KM27E")
    keep(board, arrival("gmail:m9", Channel.GMAIL, "105 Example Way", "Eve Holder"))             # the last outstanding owner answers
    after = one(derived(board), fu.FollowUpKind.REMIND, subject="KM27E")
    assert after.id == before.id and (before.outstanding, after.outstanding) == (1, 0)
    assert after.what.startswith("Nobody is outstanding")                                       # shown, not done for the person
    assert after.state is fu.FollowUpState.UPCOMING
    assert ri.load_inbox(board).arrivals["gmail:m9"].state is State.NEW                         # and the inbox is as it was


def test_defer_needs_a_later_day_and_a_reason_and_every_act_needs_a_person_and_a_known_id(board, offline):
    item = one(derived(board), fu.FollowUpKind.REMIND, subject="KM27E")
    with pytest.raises(fu.FollowUpError, match="--to must be a day after today"):
        fu.defer(board, World(), item.id, to=TODAY, by="Pat Example", why="later", today=TODAY)
    with pytest.raises(fu.FollowUpError, match="--to is required"):
        fu.defer(board, World(), item.id, to=None, by="Pat Example", why="later", today=TODAY)
    with pytest.raises(fu.FollowUpError, match="--why is required with --defer"):
        fu.defer(board, World(), item.id, to=date(2026, 10, 9), by="Pat Example", why=" ", today=TODAY)
    with pytest.raises(fu.FollowUpError, match="--why is required with --drop"):
        fu.drop(board, World(), item.id, by="Pat Example", why="", today=TODAY)
    with pytest.raises(fu.FollowUpError, match="--by is required"):
        fu.done(board, World(), item.id, by="  ", today=TODAY)
    with pytest.raises(fu.FollowUpError, match="no follow-up 'fu-nothing'"):
        fu.done(board, World(), "fu-nothing", by="Pat Example", today=TODAY)
    assert fu.acts(board) == [], "a refused act writes nothing"


def test_a_persons_own_item_is_kept_listed_and_can_be_marked_done(board, offline):
    added = fu.add_manual(board, due=date(2026, 10, 8), text="Call the printer about the mailing", by="Pat Example",
                          campaign="km27e", today=TODAY)
    assert added.kind is fu.FollowUpKind.MANUAL and added.basis is fu.Basis.PERSON and added.campaign == "KM27E"
    assert added.id in {i.id for i in fu.items(board, World(), today=TODAY)}
    with pytest.raises(fu.FollowUpError, match="already kept"):
        fu.add_manual(board, due=date(2026, 10, 8), text="Call the printer about the mailing", by="Pat Example", campaign="KM27E")
    with pytest.raises(fu.FollowUpError, match="--text is required"):
        fu.add_manual(board, due=date(2026, 10, 8), text=" ", by="Pat Example")
    with pytest.raises(fu.FollowUpError, match="--by is required"):
        fu.add_manual(board, due=date(2026, 10, 8), text="x", by="")
    with pytest.raises(fu.FollowUpError, match="--date is required"):
        fu.add_manual(board, due=None, text="x", by="Pat Example")
    assert fu.done(board, World(), added.id, by="Pat Example", today=TODAY).state is fu.FollowUpState.DONE
    assert [i.id for i in fu.select(fu.items(board, World(), today=TODAY), today=TODAY, campaign="KM27E", kind="manual", everything=True)] == [added.id]


def test_the_default_view_is_overdue_today_and_the_next_fourteen_days(board, offline):
    everything = fu.items(board, World(), today=TODAY)
    shown = fu.select(everything, today=TODAY)
    assert all(i.due <= TODAY + timedelta(days=14) for i in shown) and fu.select(everything, today=TODAY, within=0) == [
        i for i in everything if i.due <= TODAY]
    assert [i.id for i in fu.select(everything, today=TODAY, overdue=True)] == [
        i.id for i in everything if i.state is fu.FollowUpState.OVERDUE]
    assert one(shown, fu.FollowUpKind.REMIND, subject="KM27E")                                    # Oct 16 is within 14 days
    assert not [i for i in shown if i.kind is fu.FollowUpKind.REPORTS_MAILED]                     # Dec 1 is not
    with pytest.raises(fu.FollowUpError, match="no kind 'nope'"):
        fu.select(everything, kind="nope")
    assert fu.kind_of("return_by") is fu.FollowUpKind.RETURN_BY


def test_a_request_the_profile_already_runs_is_derived_from_before_its_campaign_row_is_written(data, offline):
    found = derived(data)                                          # nothing on disk but the profile's request
    assert {i.campaign for i in found if i.source == "campaign"} == {"KM27E", "KM27M"}
    remind = one(found, fu.FollowUpKind.REMIND, subject="KM27E")
    assert remind.outstanding is None and remind.reason, "an unknown count says why; it is not a zero"


def test_a_store_with_nothing_in_it_gives_no_items_and_says_which_sources_are_missing(data, offline):
    assert fu.items(data, Quiet(), today=TODAY) == []
    known = fu.ages(data, Quiet(), today=TODAY)
    assert not known["campaign"]["exists"] and "no campaign is recorded" in known["campaign"]["reason"]
    assert not known["catalog"]["exists"] and not known["inbox"]["exists"] and not known["ledger"]["exists"]
    assert "no check has been run" in known["inbox"]["reason"] and "jason notices KEY --sync" in known["ledger"]["reason"]
    assert not (data / "notices").exists() and not (data / "followups").exists(), "reading creates nothing"


def test_the_ages_of_the_sources_are_stated(board, offline):
    known = fu.ages(board, World(), now=NOON)
    assert known["catalog"]["ageHours"] == 7.0 and known["inbox"]["lastCheck"] == "2026-10-05T10:00:00+00:00"
    assert known["inbox"]["lastCheckAgeHours"] == 2.0 and known["ledger"]["exists"]
    item = one(derived(board), fu.FollowUpKind.RESEND, cite="CIV 4041(e), 4040(a)(2)")
    assert fu.source_age(item, known)["says"].startswith("the notice ledger was synced")
    review = one(derived(board), fu.FollowUpKind.REVIEW, subject="gmail:m1")
    assert fu.source_age(review, known)["says"] == "the inbox was last checked 2026-10-05T10:00:00+00:00"
    assert "no check has succeeded" in fu.source_age(review, {**known, "inbox": {**known["inbox"], "lastCheck": ""}})["says"]


# -- the funnel --------------------------------------------------------------------------------------------------------------

def test_the_funnel_counts_asked_answered_by_channel_outstanding_by_owner_and_unreachable(board, offline):
    f = campaign_funnel.funnel(board, World(), "km27e", today=TODAY)
    assert f["found"] and f["campaign"] == "KM27E" and f["request"] == "annual-2027" and f["status"] == "open"
    assert (f["asked"]["total"], f["asked"]["byChannel"], f["asked"]["mailings"]) == (5, {"email": 5}, 0)     # the mailing is KM27M's
    a = f["answered"]
    assert (a["answered"], a["read"], a["confirmed"], a["recorded"]) == (3, 1, 1, 0)             # PayHOA is its own confirmation
    assert {k: v["answered"] for k, v in a["byChannel"].items()} == {"payhoa": 1, "gmail": 1, "mail": 0, "forms": 0, "manual": 1}
    assert a["byChannel"]["manual"]["checked"] == "keyed by a person: nothing to check"
    assert a["byChannel"]["gmail"]["checkedHoursAgo"] is not None
    out = f["outstanding"]
    assert out["count"] == 1 and [(o["unit"], o["name"]) for o in out["owners"]] == [("105 Example Way", "Eve Holder")]
    assert out["neverAsked"] == 0 and out["ageHours"] == 7.0
    lost = f["unreachable"]
    assert lost["count"] == 1 and lost["owners"][0]["unit"] == "104 Example Way" and lost["owners"][0]["why"] == "email bounced"
    assert "104 Example Way" not in json.dumps(out), "an unreachable owner is never counted as outstanding"
    assert f["ages"]["catalogHours"] == 7.0 and f["ages"]["ledgerHours"] is not None and f["missing"] == []
    assert "annual-2027" in " ".join(f["notes"]) and "several campaigns" in " ".join(f["notes"])    # the answers are the request's
    assert campaign_funnel.line(f) == "asked 5; answered 3 (payhoa 1, gmail 1, manual 1); outstanding 1; unreachable 1"
    text = json.dumps(f)
    assert not [p for p in PRIVATE if p in text] and "@" not in text


def test_the_mailing_campaign_lists_the_returned_letter_as_unreachable(board, offline):
    f = campaign_funnel.funnel(board, World(), "KM27M", today=TODAY)
    assert f["asked"]["total"] == 0 and f["asked"]["mailings"] == 1
    assert f["unreachable"]["count"] == 1 and f["unreachable"]["owners"][0]["why"] == "letter returned"
    assert f["outstanding"]["count"] is None and "no emailed copy" in f["outstanding"]["reason"]    # a mailing names no recipient


@pytest.mark.parametrize("channel", ["payhoa", "gmail", "mail", "forms", "manual"])
def test_an_owner_who_answered_by_any_method_is_not_outstanding(board, offline, channel):
    assert campaign_funnel.funnel(board, World(), "KM27E", today=TODAY)["outstanding"]["count"] == 1
    if channel == "manual":
        ri.add_manual(board, World(), "annual-2027", by="Secretary", how="handed in at the office", who="Eve Holder",
                      unit="105 Example Way", now=NOON)
    else:
        keep(board, arrival(f"{channel}:x1", Channel(channel), "105 Example Way", "Eve Holder"))
    f = campaign_funnel.funnel(board, World(), "KM27E", today=TODAY)
    assert f["outstanding"]["count"] == 0 and f["outstanding"]["owners"] == []
    assert f["answered"]["byChannel"][channel]["answered"] == (2 if channel in ("payhoa", "gmail", "manual") else 1)
    assert f["answered"]["answered"] == 4


def test_an_owner_who_answered_is_not_unreachable_and_one_with_a_delivery_pending_is_outstanding(board, offline):
    keep(board, arrival("gmail:m7", Channel.GMAIL, "104 Example Way", "Dee Fictional"))
    f = campaign_funnel.funnel(board, World(), "KM27E", today=TODAY)
    assert f["unreachable"]["count"] == 0 and f["unreachable"]["owners"] == []          # reached: they answered
    ledger(board, Attempt("notice-2", 15, 5, "105 Example Way", "email", "b2", reference(5), "2026-10-04T10:00:00+00:00",
                          Delivery.PENDING, "", ""))
    g = campaign_funnel.funnel(board, World(), "KM27E", today=TODAY)
    assert g["outstanding"]["count"] == 1 and g["unreachable"]["count"] == 0                  # still in flight, so still outstanding


def test_a_missing_source_says_so_with_its_reason_and_a_count_that_cannot_be_made_is_none_not_zero(data, offline):
    campaigns.open_campaign(World(), "annual-info", channel="email", cycle=CAMPAIGN_CYCLE, by="Pat Example", data_dir=data, now=NOON)
    f = campaign_funnel.funnel(data, World(), "KM27E", today=TODAY)
    sources = {m["source"]: m["reason"] for m in f["missing"]}
    assert set(sources) == {"sent-copy catalog", "response inbox", "notice ledger"}
    assert "no copy has been recorded as sent" in sources["sent-copy catalog"]
    assert "no check has been run" in sources["response inbox"] and "jason notices KEY --sync" in sources["notice ledger"]
    assert f["outstanding"]["count"] is None and f["unreachable"]["count"] is None and f["asked"]["ageHours"] is None
    assert f["answered"]["answered"] == 0 and f["answered"]["inboxExists"] is False
    assert campaign_funnel.line(f).endswith("outstanding -; unreachable -")
    unknown = campaign_funnel.funnel(data, World(), "ZZ99X", today=TODAY)
    assert unknown["found"] is False and "no campaign 'ZZ99X'" in unknown["reason"]


def test_a_campaign_no_request_watches_cannot_count_answers(data, offline):
    class Quiet(World):
        def response_requests(self):
            return ()

    world = Quiet()
    campaigns.open_campaign(world, "annual-info", channel="email", cycle=CAMPAIGN_CYCLE, by="Pat Example", data_dir=data, now=NOON)
    f = campaign_funnel.funnel(data, world, "KM27E", today=TODAY)
    assert f["answered"] is None and f["outstanding"]["count"] is None and "no request watches" in f["outstanding"]["reason"]
    assert any("no request watches" in m["reason"] for m in f["missing"])
    assert campaign_funnel.line(f).startswith("asked 0; answered - (-)")


# -- the manual intake channel -----------------------------------------------------------------------------------------------

def test_a_manual_arrival_names_how_it_came_keeps_the_scan_and_stores_no_address(data, tmp_path_factory, offline):
    scan = tmp_path_factory.mktemp("scans") / "form 2027.pdf"
    scan.write_bytes(b"%PDF-1.4 made up")
    got = ri.add_manual(data, World(), "annual-2027", by="Secretary", how="handed in at the office, call 916-555-0100",
                        who="Eve Holder eve@example.org", unit="105 Example Way", files=[scan], note="PO Box 9", now=NOON)
    assert got.id.startswith("manual:20261005-120000-") and got.channel is Channel.MANUAL and got.state is State.NEW
    assert got.attachments == ("form 2027.pdf",) and got.summary.startswith("handed in at the office")
    assert got.unit == "105 Example Way" and not got.structured and got.request == "annual-2027"
    stored = (data / ri.ROOT / ri.INBOX).read_text(encoding="utf-8")
    assert "@" not in stored and "916-555-0100" not in stored and "[email]" in stored and "[phone]" in stored
    assert (data / ri.ROOT / ri.FILES / got.stem / "form 2027.pdf").read_bytes() == b"%PDF-1.4 made up"
    [act] = ri.acts_for(data, got.id)
    assert act["act"] == "manual" and act["by"] == "Secretary" and act["files"] == 1 and "@" not in json.dumps(act)
    twin = ri.add_manual(data, World(), "annual-2027", by="Secretary", how="handed in at the office, call 916-555-0100",
                         who="Eve Holder eve@example.org", unit="105 Example Way", now=NOON)
    assert twin.id != got.id and twin.id.endswith("-2")                                       # the same second, the same person


def test_a_manual_arrival_is_refused_without_a_person_a_method_a_name_a_known_request_or_a_form_file(data, tmp_path, offline):
    def refused(match, **kw):
        base = dict(by="Secretary", how="by phone", who="Eve Holder", now=NOON)
        with pytest.raises(ResponseError, match=match):
            ri.add_manual(data, World(), kw.pop("request", "annual-2027"), **{**base, **kw})

    refused("--by is required", by=" ")
    refused("--how is required", how="")
    refused("--who is required", who="")
    refused("no request 'another'", request="another")
    refused("no file 'missing.pdf'", files=[tmp_path / "missing.pdf"])
    note = tmp_path / "notes.txt"
    note.write_text("x", encoding="utf-8")
    refused("is not a PDF or an image", files=[note])
    assert not (data / ri.ROOT).exists(), "a refused arrival writes nothing"


def test_a_manual_arrival_goes_through_read_and_confirm_like_any_other(data, tmp_path, offline):
    scan = tmp_path / "scan.pdf"
    scan.write_bytes(b"%PDF-1.4 made up")
    with_scan = ri.add_manual(data, World(), "annual-2027", by="Secretary", how="handed in at the office", who="Ana Example",
                              unit="101 Example Way", files=[scan], now=NOON)
    by_phone = ri.add_manual(data, World(), "annual-2027", by="Secretary", how="by phone", who="Ben Sample", unit="102 Example Way",
                             now=NOON + timedelta(minutes=5))
    assert (with_scan.id, by_phone.id) != ("", "") and with_scan.id != by_phone.id

    def reader(path, request, layout, model):
        return ri.FileReading(path.name, "scan", {}, {"name": "Ana Example"}, "", "", [], 12, 0.1)

    reading = ri.read(data, World(), with_scan.id, by="Secretary", clients={}, reader=reader)
    assert reading["form"] and reading["how"] == "scan" and reading["files"][0]["name"] == "scan.pdf"
    assert any("added by a person for Ana Example" in n for n in reading["notes"])
    assert ri.get(data, with_scan.id).state is State.READ
    keyed = ri.confirm(data, World(), with_scan.id, by="Secretary", corrections={"name": "Ana Example"})
    assert keyed.answers.source == f"manual:{with_scan.native}" and ri.get(data, with_scan.id).state is State.KEYED
    phone = ri.read(data, World(), by_phone.id, by="Secretary", clients={})                    # nothing to read: a person keys each answer
    assert phone["form"] and phone["how"] == "keyed by a person" and any("keys each answer" in n for n in phone["notes"])
    typed = ri.confirm(data, World(), by_phone.id, by="Secretary", corrections={"name": "Ben Sample"})
    assert typed.answers.answers == {"name": "Ben Sample"} and ri.arrival_id_for(typed.answers.source) == by_phone.id
    assert [a.source for a in ri.keyed_answers(data)] == [f"manual:{with_scan.native}", f"manual:{by_phone.native}"]


def test_a_check_never_looks_for_the_manual_channel(data, offline):
    from test_response_inbox import FakeGmail, FakePayhoa, clients

    report = ri.check(data, World(), clients=clients(FakeGmail(), FakePayhoa({})), by="scheduler", now=NOON, tests=(), owners={})
    assert Channel.MANUAL not in {c.channel for c in report.channels}
    assert ri.uses(REQUEST, Channel.MANUAL) is False and "manual" not in ri.load_inbox(data).channels


# -- the board's tools -------------------------------------------------------------------------------------------------------

@pytest.fixture
def served(monkeypatch):
    monkeypatch.setattr("jason.community.community", lambda: World())
    monkeypatch.setattr(tools, "_today", lambda: TODAY)
    monkeypatch.setattr(campaign_funnel.ri, "now_utc", lambda: NOON)


def test_the_followups_tool_reads_disk_only_masked_with_ages_and_caveats(board, served, offline):
    out = tools.followups(data_dir=board)
    assert out["found"] and out["asOf"] == "2026-10-05" and out["count"] == len(out["items"])
    kinds = {i["kind"] for i in out["items"]}
    assert {"remind", "resend", "return-by", "review"} <= kinds and "reports-mailed" not in kinds        # the default is 30 days
    remind = next(i for i in out["items"] if i["kind"] == "remind" and i["subject"] == "KM27E")
    assert remind["basis"] == "proposed policy" and "proposed" in remind["cite"] and remind["outstanding"] == 1
    assert remind["names"] == ["105 Example Way (Eve Holder)"] and remind["sourceAge"]["source"] == "the campaign record"
    assert out["ages"]["catalog"]["ageHours"] is not None and out["ages"]["ledger"]["exists"] is True
    assert any("sends nothing, resends nothing" in c for c in out["caveats"]) and any("proposed policy" in c for c in out["caveats"])
    assert any("unreachable" in c for c in out["caveats"]) and out["note"] == tools.LIVE_LINE
    assert not [p for p in PRIVATE if p in json.dumps(out)] and "@" not in json.dumps(out)
    assert "repeat the caveats" in tools.followups.__doc__ and "disk only" in tools.followups.__doc__.lower()
    narrow = tools.followups(days=400, campaign="KM27E", kind="enter-by", data_dir=board)
    assert [i["kind"] for i in narrow["items"]] == ["enter-by"] and narrow["items"][0]["basis"] == "law"
    resolved = tools.followups(state="upcoming", kind="reports_mailed", data_dir=board)
    assert [i["kind"] for i in resolved["items"]] == ["reports-mailed"]                                  # a state shows every date
    bad = tools.followups(kind="nope", data_dir=board)
    assert bad["found"] is False and "no kind 'nope'" in bad["reason"] and bad["caveats"]


def test_the_followups_tool_on_an_empty_store_is_a_miss_with_its_reason(data, served, offline, monkeypatch):
    monkeypatch.setattr("jason.community.community", lambda: Quiet())
    out = tools.followups(data_dir=data)
    assert out["found"] is False and out["count"] == 0 and out["items"] == [] and out["caveats"]
    assert "no follow-up matches as of 2026-10-05" in out["reason"] and "0 follow-up(s) in all" in out["reason"]
    assert "no campaign is recorded" in out["reason"] and "no check has been run" in out["reason"]
    assert out["ages"]["ledger"]["exists"] is False
    once = tools.campaign_status(data_dir=data)
    assert once["found"] is False and "no campaign is recorded" in once["reason"] and once["campaigns"] == [] and once["caveats"]


def test_the_campaign_status_tool_gives_the_funnel_and_the_next_follow_up(board, served, offline):
    out = tools.campaign_status("km27e", data_dir=board)
    assert out["found"] and out["count"] == 1
    [c] = out["campaigns"]
    assert c["campaign"] == "KM27E" and c["outstanding"]["count"] == 1 and c["unreachable"]["count"] == 1
    assert c["asked"]["byChannel"] == {"email": 5} and c["answered"]["byChannel"]["manual"]["answered"] == 1
    assert c["nextFollowUp"]["kind"] in ("resend", "review", "remind") and c["ages"]["catalogHours"] is not None
    assert [x["campaign"] for x in tools.campaign_status(data_dir=board)["campaigns"]] == ["KM27E", "KM27M"]
    miss = tools.campaign_status("ZZ99X", data_dir=board)
    assert miss["found"] is False and "no campaign 'ZZ99X'" in miss["reason"] and "KM27E" in miss["reason"] and miss["caveats"]
    assert not [p for p in PRIVATE if p in json.dumps(out)]
    assert "repeat the caveats" in tools.campaign_status.__doc__


def test_the_tools_write_nothing_and_make_no_network_call(board, served, monkeypatch):
    def snapshot():
        return {str(p.relative_to(board)): p.read_bytes() for p in sorted(board.rglob("*")) if p.is_file()}

    def boom(*a, **k):
        raise AssertionError("a tool made a network call")

    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    before = snapshot()
    tools.followups(days=400, data_dir=board)
    tools.followups(state="overdue", data_dir=board)
    tools.campaign_status(data_dir=board)
    assert snapshot() == before


def test_the_tools_are_in_the_board_profile_the_full_set_and_the_python_interface():
    assert {"followups", "campaign_status"} <= set(PROFILES["board"])
    assert "followups" not in PROFILES["governance"] and "campaign_status" not in PROFILES["onboarding"]
    assert len(PROFILES["board"]) == 48 and len(tools_for("board")) == 48
    served_by_name = {t.__name__: t for t in ALL_TOOLS}
    assert served_by_name["followups"] is tools.followups and served_by_name["campaign_status"] is tools.campaign_status
    assert len(served_by_name) == len(ALL_TOOLS)
    assert api.followups is tools.followups and api.campaign_status is tools.campaign_status
    assert {"followups", "campaign_status"} <= set(api.__all__)
    for tool in tools.TOOLS:
        assert tool.__doc__ and "Read-only" in tool.__doc__
