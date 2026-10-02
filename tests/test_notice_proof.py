"""Proof of notice: the evidence a requirement calls for, the window, and who was reached late, from the ledger."""

from __future__ import annotations

from datetime import date

from jason.community.notice_catalog import requirement
from jason.community.notices import Evidence
from jason.tasks import notice_ledger as nl
from jason.tasks.notice_proof import Status, build, lines


def _attempt(member: int, channel: str, status: nl.Delivery, sent: str, unit: str = "") -> nl.Attempt:
    return nl.Attempt("n", member, member, unit or f"unit {member}", channel, "b", f"k{member}{channel}{sent}", sent,
                      status)


def test_an_individual_notice_in_time_with_a_bounce_resent_after_the_deadline():
    attempts = [
        _attempt(1, "email", nl.Delivery.DELIVERED, "2026-11-20T10:00:00"),
        _attempt(2, "email", nl.Delivery.BOUNCED, "2026-11-20T10:00:00"),
        _attempt(2, "letter", nl.Delivery.MAILED, "2026-12-10T10:00:00"),
        _attempt(3, "letter", nl.Delivery.MAILED, "2026-11-20T10:00:00"),
    ]
    row = requirement("assessment-increase")
    proof = build(row, event=date(2027, 1, 1), standings=nl.standing(attempts), have=[Evidence.TEXT_AS_SENT])
    assert proof.delivered == date(2026, 11, 20) and proof.on_time is True
    assert proof.reached == 3 and not proof.unreached
    assert len(proof.late) == 1 and "member 2" in proof.late[0]
    status = {i.evidence: i.status for i in proof.items}
    assert status[Evidence.TEXT_AS_SENT] is Status.HAVE
    assert status[Evidence.DELIVERY_LEDGER] is Status.HAVE
    assert status[Evidence.MAILING_DECLARATION] is Status.MISSING
    assert not proof.complete
    assert any("late" in line for line in lines(proof))


def test_a_send_outside_the_window_is_flagged():
    proof = build(requirement("assessment-increase"), event=date(2027, 1, 1), sent=date(2026, 12, 15))
    assert proof.on_time is False


def test_a_posted_general_notice_covers_the_members_its_messages_missed():
    attempts = [_attempt(1, "email", nl.Delivery.BOUNCED, "2026-10-14T09:00:00"),
                _attempt(2, "email", nl.Delivery.DELIVERED, "2026-10-14T09:00:00")]
    found = nl.standing(attempts, general=True)
    proof = build(requirement("board-meeting"), event=date(2026, 10, 20), posted=date(2026, 10, 15), standings=found,
                  general=True)
    assert proof.on_time is True and not proof.unreached
    assert {i.evidence: i.status for i in proof.items}[Evidence.POSTING] is Status.HAVE
    # A member who asked for individual delivery (4045(b)) is not covered by the posting.
    proof = build(requirement("board-meeting"), event=date(2026, 10, 20), posted=date(2026, 10, 15), standings=found,
                  general=True, individual={1})
    assert proof.unreached and "member 1" in proof.unreached[0]


def test_an_unposted_general_notice_must_reach_everyone():
    attempts = [_attempt(1, "email", nl.Delivery.BOUNCED, "2026-10-14T09:00:00")]
    proof = build(requirement("board-meeting"), event=date(2026, 10, 20), standings=nl.standing(attempts))
    assert proof.unreached
    posting = next(i for i in proof.items if i.evidence is Evidence.POSTING)
    assert posting.status is Status.MISSING and "4045(a)(1)" in posting.detail
    follow = next(i for i in proof.items if i.evidence is Evidence.FOLLOW_UPS)
    assert follow.status is Status.OWED


def test_a_clock_for_another_act_does_not_judge_the_delivery():
    attempts = [_attempt(1, "letter", nl.Delivery.MAILED, "2026-10-02T09:00:00")]
    proof = build(requirement("owner-info-solicitation"), event=date(2026, 10, 31), standings=nl.standing(attempts))
    assert proof.on_time is None and not proof.late


def test_a_requirement_with_everything_on_file_is_complete():
    row = requirement("discipline-decision")
    attempts = [_attempt(1, "letter", nl.Delivery.MAILED, "2026-10-05T09:00:00")]
    have = [e for e in row.proof() if e not in (Evidence.DELIVERY_LEDGER, Evidence.RECIPIENTS, Evidence.FOLLOW_UPS,
                                                 Evidence.ANCHOR_DATE)]
    proof = build(row, event=date(2026, 10, 1), standings=nl.standing(attempts), have=have)
    assert proof.on_time is True and proof.complete
