"""The meetings group of document models: agendas, minutes, executive sessions, notices, resolutions, committee reports,
election results, and ballots. The excerpts follow the real layouts with made-up people, places, and numbers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from jason.community.document_models import ModelContext, read
from jason.community.models import meetings
from jason.community.models.meetings import ExecutiveSubject, MeetingBody, MeetingType, MinutesLayout, Outcome
from jason.community.models.meetings_notices import NoticeType
from jason.community.models.meetings_resolutions import ResolutionSubject, ResolutionType, Vote
from jason.community.symbols import DocumentKind

TODAY = date(2026, 9, 29)


def ctx(**kw) -> ModelContext:
    return ModelContext(community=kw.pop("community", None), data_dir=kw.pop("data_dir", None), today=kw.pop("today", TODAY), **kw)


def codes(reading) -> dict[str, str]:
    return {f.code: f.severity.value for f in reading.findings}


# --- Agendas ----------------------------------------------------------------------------------------------------

BOARD_AGENDA = """\
EXAMPLE COMMUNITY ASSOCIATION
Regular Meeting of the Board of Directors
To be held on:
at 7:00pm
Mar 17, 2026
via Zoom
(555) 010-2000
Meeting ID: 800 1234 5678
Join via Zoom
I.​
Call to Order
II.​
Approval of minutes of previous meeting
See:
Minutes of 2/17/26
III.​
Treasurer’s Report
See:
Treasurer's Report - 2026-02_Redacted.pdf
IV.​
Notice of Intent to Borrow
Borrow money from the reserve funds to meet short-term cash flow requirements.
V.​
Consider qualified candidates elected by acclamation (Civ. §5103 (e))
Certified Election Results 2026.pdf
VI.​
Legal - Policy Proposals
●​ Pet Waste Policy
VII.​
Proposals
i.​
Gutter Cleaning \U0001F4F7
Sample Gutters - Estimate - 000123.pdf
ii.​
Tree Pruning
EXAMPLE COMMUNITY ASSOCIATION
-
(Zoom)
Regular Meeting of the Board of Directors
Mar 17, 2026 7:00 PM PDT

EXAMPLE COMMUNITY ASSOCIATION
Regular Meeting of the Board of Directors - Agenda
VIII.​
Open Forum - 2 minutes per member
Open Forum is devoted to comments by homeowners and discussion of those comments. (Civ. §4930).
IX.​
Time and Place of next Regular Meeting
on Zoom
Apr 21, 2026 7:00 PM PDT
X.​
Adjourn to Executive Session
Only directors, managers, recording secretaries, the association's attorney may attend executive session meetings.
i.​
Member Discipline
ii.​
Delinquencies
iii.​
Holiday Party Planning
Decorum Rules
No audio or video recording allowed by attendees.
"""


def test_board_agenda_template():
    reading = read(DocumentKind.AGENDA, BOARD_AGENDA, ctx())
    a = reading.record
    assert reading.model == "meeting-agenda" and reading.complete
    assert a.layout == "association" and a.meeting_type is MeetingType.REGULAR and a.body is MeetingBody.BOARD
    assert a.meeting_date == date(2026, 3, 17) and a.meeting_time == "7:00pm"
    assert a.teleconference and a.dial_in and a.meeting_id == "800 1234 5678" and not a.physical_location
    assert [i.number for i in a.items] == ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
    proposals = a.items[6]
    assert [s.title for s in proposals.subitems] == ["Gutter Cleaning", "Tree Pruning"]
    assert proposals.subitems[0].attachments == ("Sample Gutters - Estimate - 000123.pdf",)
    assert a.prior_minutes == (date(2026, 2, 17),)
    assert a.next_meeting == date(2026, 4, 21)
    assert a.executive_topics == ("Member Discipline", "Delinquencies", "Holiday Party Planning")
    assert a.member_comment
    found = codes(reading)
    assert found["teleconference-notice"] == "check"          # no help contact, no individual-delivery reminder
    assert found["borrowing-notice"] == "check"               # no repayment options, no special assessment statement
    assert found["rule-change"] == "check"
    assert found["acclamation-names"] == "check"
    assert found["executive-topic"] == "check"                # the party is not a 4935 subject
    assert found["posting-date-not-shown"] == "info"
    assert "notice-late" not in found


def test_agenda_posted_late_is_a_problem():
    text = BOARD_AGENDA.replace("Join via Zoom\n", "Join via Zoom\nPosted: Mar 15, 2026\n", 1)
    found = codes(read(DocumentKind.AGENDA, text, ctx()))
    assert found["notice-late"] == "problem"
    assert "posting-date-not-shown" not in found


def test_agenda_notice_follows_a_longer_period_in_the_documents():
    from types import SimpleNamespace

    from jason.community.base import NoticePeriod

    text = BOARD_AGENDA.replace("Join via Zoom\n", "Join via Zoom\nPosted: Mar 11, 2026\n", 1)     # six days before
    assert "notice-late" not in codes(read(DocumentKind.AGENDA, text, ctx()))                   # the statute's four days
    longer = SimpleNamespace(board_notice_period=lambda: NoticePeriod(days=10, source="Bylaws 1.2"))
    late = next(f for f in read(DocumentKind.AGENDA, text, ctx(community=longer)).findings if f.code == "notice-late")
    assert "due 10 days before" in late.message and late.authority == "Bylaws 1.2; CIV 4920(b)(3)"


MANAGER_AGENDA = """\
Example Management Group, Inc.
100 Business Parkway, Ste. 1
Board of Directors Meeting
January 23, 2024 7:00 PM
Via Zoom
Meeting ID: 800 0000 1111
Board Meeting Agenda
Example Community Association | January 23rd, 2024 Board Meeting
1. Call to Order
2. Consent Agenda (Items on the consent agenda will not normally be discussed as the Board receives
their Board packet in advance.)
a. Minutes of Previous Meeting dated November 20th, 2023
3. Action Items (These are items for which the Board is anticipating making decisions.)
a. Appointment Of Board Of Directors Positions
4. Member Comment Period (This is time set aside for homeowners to provide input to the Board.)
5. Adjournment
"""


def _mail(monkeypatch, *rows):
    monkeypatch.setattr(meetings, "_mailings", lambda d: tuple({"subject": s, "sent": at} for s, at in rows))
    monkeypatch.setattr(meetings, "_library", lambda d: ())


def test_agenda_notice_email_from_payhoa(monkeypatch):
    # Sent 6:30 pm Pacific on the 14th for the 17th: three days.
    _mail(monkeypatch, ("Regular Meeting of the Board of Directors - March 17th at 7:00 pm", "2026-03-15T01:30:00.000000Z"),
          ("(Preview) Regular Meeting of the Board of Directors - March 17th at 7:00 pm", "2026-03-01T01:30:00.000000Z"),
          ("Regular Meeting of the Board of Directors - February 17th at 7:00 pm", "2026-02-12T01:30:00.000000Z"))
    reading = read(DocumentKind.AGENDA, BOARD_AGENDA, ctx(data_dir=Path(".")))
    assert reading.record.notice_sent == date(2026, 3, 14) and "March 17th" in reading.record.notice_subject
    found = codes(reading)
    assert found["notice-sent-late"] == "check" and "posting-date-not-shown" not in found


def test_agenda_with_no_notice_email_in_the_log(monkeypatch):
    _mail(monkeypatch, ("Regular Meeting of the Board of Directors - February 17th at 7:00 pm", "2026-02-12T01:30:00.000000Z"))
    reading = read(DocumentKind.AGENDA, BOARD_AGENDA, ctx(data_dir=Path(".")))
    assert reading.record.notice_sent is None
    assert codes(reading)["posting-date-not-shown"] == "check"      # the log covers the meeting and has no mailing for it


def test_members_meeting_notice_email(monkeypatch):
    _mail(monkeypatch, ("Annual Membership Meeting - November 18th at 7:00 pm PST", "2025-11-15T04:56:00.000000Z"))
    reading = read(DocumentKind.AGENDA, ANNUAL_AGENDA, ctx(data_dir=Path(".")))
    found = codes(reading)
    assert reading.record.notice_sent == date(2025, 11, 14) and found["members-notice"] == "check"
    assert "notice-sent-late" not in found


def test_manager_agenda_layout():
    a = read(DocumentKind.AGENDA, MANAGER_AGENDA, ctx()).record
    assert a.meeting_date == date(2024, 1, 23)
    assert [i.title for i in a.items] == ["Call to Order", "Consent Agenda", "Action Items", "Member Comment Period", "Adjournment"]
    assert a.items[1].subitems[0].title.startswith("Minutes of Previous Meeting")
    assert a.prior_minutes == (date(2023, 11, 20),)
    assert a.member_comment


ANNUAL_AGENDA = """\
EXAMPLE COMMUNITY ASSOCIATION
Annual Membership Meeting
To be held on:
November 18, 2025 at 7:00pm
via Zoom
Meeting ID: 800 2222 3333
Agenda
I.
Annual Statement to Members
II.
Elections
a.
Board of Directors
Three seats are up for election this year.
III.
Time and Place of Next Meetings
"""


def test_annual_agenda_counts_ballots_online():
    reading = read(DocumentKind.AGENDA, ANNUAL_AGENDA, ctx())
    assert reading.record.meeting_type is MeetingType.ANNUAL and reading.record.body is MeetingBody.MEMBERS
    found = codes(reading)
    assert found["ballot-count-online"] == "check"
    assert "no-member-comment" not in found and "posting-date-not-shown" not in found


# --- Minutes ----------------------------------------------------------------------------------------------------

ANNOTATED_MINUTES = """\
DRAFT
EXAMPLE COMMUNITY ASSOCIATION
Special Meeting of the Board of Directors
Held
February 6, 2024 at 7:00pm
via Zoom
I.
Call to Order
The meeting was called to order at 7:05 pm.
II.
Notice of Intent to Borrow
Special Resolution - Borrowing Reserve Funds
The board resolved to borrow $16,000 from the reserve account to fund a new operating account, which will be
repaid when the association receives the funds held in trust by the former manager.
III.
Adopt Revised Budget - TABLED
The board decided that it would be best to revisit the budget in April.
IV.
Time and Place of Next Meeting
on Zoom at 7:00 pm.
Apr 16, 2024
V.
Adjourn to Executive Session
The board met in Executive Session to discuss delinquencies and a landscaping contract.
"""


def test_annotated_minutes():
    reading = read(DocumentKind.MINUTES, ANNOTATED_MINUTES, ctx())
    m = reading.record
    assert m.layout is MinutesLayout.ANNOTATED_AGENDA and m.draft
    assert m.meeting_type is MeetingType.SPECIAL and m.meeting_date == date(2024, 2, 6)
    assert m.called_to_order == "7:05 pm"
    assert m.next_meeting == date(2024, 4, 16)
    borrow = [a for a in m.actions if a.amount == 1_600_000]
    assert borrow and borrow[0].outcome is Outcome.APPROVED
    assert any(a.outcome is Outcome.TABLED for a in m.actions)
    assert "delinquencies" in m.executive_summary
    found = codes(reading)
    assert found["draft-after-next-meeting"] == "check"
    assert found["reserve-transfer"] == "info"
    assert "executive-session-not-noted" not in found


AI_MINUTES = """\
EXAMPLE COMMUNITY ASSOCIATION
Regular Meeting of the Board of Directors
Held on
via Zoom
Sep 23, 2025 7:00 PM PDT
I.​
Call to Order
II.​
Approval of minutes of previous meeting(s)
Minutes of 8/19/25
III.​
Proposals
i.​
Pressure Washing
iv.​
Adjourn to Executive Session
IV.​
Adjourn to Executive Session
i.​
Member Discipline
Quick recap
The board approved several service contracts.
Next steps
●​ Alex to sign the pressure washing proposal.
●​ Sam to get gutter quotes.
Summary
Budget and Contracts
The group agreed to proceed with the current meeting despite the lack of quorum, with Pat joining late.
The board approved the meeting minutes.
The board discussed and approved a $5,200 pressure washing proposal, with all present members voting in favor.
They decided to table the $2,535 tree fertilization proposal.
AI can make mistakes. Review for accuracy.
"""


def test_ai_summary_minutes():
    reading = read(DocumentKind.MINUTES, AI_MINUTES, ctx())
    m = reading.record
    assert m.layout is MinutesLayout.AI_SUMMARY and m.ai_summary and not m.draft
    assert m.meeting_date == date(2025, 9, 23)
    assert len(m.next_steps) == 2
    assert m.prior_minutes == (date(2025, 8, 19),) and m.prior_minutes_approved
    washing = [a for a in m.actions if a.amount == 520_000]
    assert washing and washing[0].unanimous
    assert any(a.outcome is Outcome.TABLED and a.amount == 253_500 for a in m.actions)
    assert m.quorum is None and "despite the lack of quorum" in m.quorum_note
    found = codes(reading)
    # A summary retells the call: the roll call and the attendance it lacks are one lead, not three.
    assert found["ai-summary"] == "check"
    assert "no-roll-call" not in found and "quorum-not-shown" not in found and "votes-not-recorded" not in found
    message = next(f for f in reading.findings if f.code == "ai-summary")
    assert "who attended" in message.message and "roll call" in message.message and "4926(a)(3)" in message.authority
    assert found["quorum-question"] == "check"
    assert found["executive-session-not-noted"] == "check"


def test_ai_summary_and_the_executive_session():
    noted = AI_MINUTES.replace("They decided to table", "The board agreed to reconvene at 7:30 for an executive session to address a "
                               "disciplinary hearing. They decided to table")
    reading = read(DocumentKind.MINUTES, noted, ctx())
    assert reading.record.executive_summary.startswith("The board agreed to reconvene")
    assert "executive-session-not-noted" not in codes(reading)
    deferred = AI_MINUTES.replace("They decided to table", "They noted the need for future executive sessions when all board members "
                                  "are present. They decided to table")
    m = read(DocumentKind.MINUTES, deferred, ctx()).record
    assert m.executive_session is False and not m.executive_summary
    told = AI_MINUTES.replace("They decided to table", "During the executive session, the board discussed a disciplinary matter. "
                              "They decided to table")
    found = codes(read(DocumentKind.MINUTES, told, ctx()))
    assert found["executive-detail"] == "check" and "executive-session-not-noted" not in found


def test_ai_summary_that_confirms_the_quorum():
    text = AI_MINUTES.replace("The group agreed to proceed with the current meeting despite the lack of quorum, with Pat joining late.",
                              "The meeting began with only two members present initially, but eventually reached quorum with four "
                              "directors attending.")
    m = read(DocumentKind.MINUTES, text, ctx()).record
    assert m.quorum is True and m.directors_count == 4 and m.quorum_note.startswith("The meeting began")
    reading = read(DocumentKind.MINUTES, text, ctx())
    found = codes(reading)
    assert "quorum-question" not in found
    message = next(f.message for f in reading.findings if f.code == "ai-summary")
    assert "who attended" not in message and "roll call" in message


def test_ai_summary_waiting_for_a_quorum():
    late = AI_MINUTES.replace("The group agreed to proceed with the current meeting despite the lack of quorum, with Pat joining late.",
                              "Board Quorum and Contracts\nThe meeting began with a discussion about quorum requirements, confirming "
                              "that three board members were needed to approve motions, with Alex and Sam present and waiting for Pat.")
    m = read(DocumentKind.MINUTES, late, ctx()).record
    assert m.quorum is None and m.quorum_note.startswith("The meeting began with a discussion about quorum")
    assert codes(read(DocumentKind.MINUTES, late, ctx()))["quorum-question"] == "check"
    joined = AI_MINUTES.replace("The group agreed to proceed with the current meeting despite the lack of quorum, with Pat joining late.",
                                "The meeting began with Alex noting the need for one more board member to start the meeting, which "
                                "was then joined by Pat.")
    assert read(DocumentKind.MINUTES, joined, ctx()).record.quorum is True
    needed = AI_MINUTES.replace("with Pat joining late.", "with Pat joining late. Sam noted they needed three board members present.")
    assert read(DocumentKind.MINUTES, needed, ctx()).record.directors_count is None


NARRATIVE_MINUTES = """\
EXAMPLE COMMUNITY ASSOCIATION
Minutes of the Regular Meeting of the Board of Directors
Held on March 3, 2026 at 6:30 pm at the Clubhouse, 100 Sample Way
Directors Present: Alex Rivera, Morgan Lee, Sam Park
Absent: Pat Quinn
Also Present: Jordan Blake (manager)
The meeting was called to order at 6:32 pm. A quorum was present.
Motion by Alex Rivera, seconded by Morgan Lee, to approve the landscape contract for $12,000.00. The board approved the motion 3-0 by roll call vote.
The meeting was adjourned at 7:45 pm.
"""


def test_narrative_minutes():
    reading = read(DocumentKind.MINUTES, NARRATIVE_MINUTES, ctx())
    m = reading.record
    assert m.layout is MinutesLayout.NARRATIVE
    assert m.directors_present == ("Alex Rivera", "Morgan Lee", "Sam Park")
    assert m.directors_absent == ("Pat Quinn",) and m.others_present == ("Jordan Blake",)
    assert m.quorum is True and m.called_to_order == "6:32 pm" and m.adjourned == "7:45 pm"
    act = m.actions[0]
    assert (act.mover, act.seconder, act.yes, act.no, act.amount, act.roll_call) == ("Alex Rivera", "Morgan Lee", 3, 0, 1_200_000, True)
    found = codes(reading)
    assert "no-roll-call" not in found and "quorum-not-shown" not in found and "missing-items" in found


NO_QUORUM = """\
EXAMPLE COMMUNITY ASSOCIATION
Regular Meeting of the Board of Directors
Held on
at 7:00pm via Zoom
Aug 19, 2025
Quorum requirements not met
Alex Rivera and Sam Park were present for the meeting, but quorum requirements
were not met, and so the meeting was adjourned.
"""


def test_no_quorum_minutes_are_complete():
    reading = read(DocumentKind.MINUTES, NO_QUORUM, ctx())
    assert reading.record.layout is MinutesLayout.NO_QUORUM and reading.record.quorum is False
    assert reading.complete and reading.record.directors_present == ("Alex Rivera", "Sam Park")
    assert codes(reading)["no-quorum"] == "info"


def test_minutes_due_within_thirty_days():
    found = codes(read(DocumentKind.MINUTES, AI_MINUTES, ctx(today=date(2025, 10, 1))))
    assert found["minutes-due"] == "info"


def test_minutes_checked_against_library_agenda(monkeypatch):
    agenda = BOARD_AGENDA.replace("Mar 17, 2026", "Sep 23, 2025")
    rows = ({"id": "a1", "name": "Agenda for 9_23_25.pdf", "period": "2025-09-23", "kind": "agenda"},)
    monkeypatch.setattr(meetings, "_library", lambda d: rows)
    monkeypatch.setattr(meetings, "_library_text", lambda d, i: meetings.normalize(agenda))
    found = codes(read(DocumentKind.MINUTES, AI_MINUTES, ctx(data_dir=Path("."), name="Minutes of 9_23_25.pdf")))
    assert found["not-on-agenda"] == "check"      # "Pressure Washing" is not on that agenda
    reading = read(DocumentKind.MINUTES, AI_MINUTES, ctx(data_dir=Path("."), name="Minutes of 9_23_25.pdf"))
    message = next(f.message for f in reading.findings if f.code == "not-on-agenda")
    assert "Pressure Washing" in message and "Call to Order" not in message


def test_agenda_without_minutes_on_file(monkeypatch):
    monkeypatch.setattr(meetings, "_library", lambda d: ())
    found = codes(read(DocumentKind.AGENDA, BOARD_AGENDA, ctx(data_dir=Path("."))))
    assert found["no-minutes-on-file"] == "check"
    assert found["prior-minutes-not-on-file"] == "check"


ANNUAL_MINUTES_AS_NOTICE = """\
EXAMPLE COMMUNITY ASSOCIATION
Annual Membership Meeting
Held on:
Nov 18, 2025 7:00 PM PST
via Zoom
I.
Annual Statement to Members
II.
Elections
a. Board of Directors
The Association members elected to refund any excess income.
EXAMPLE COMMUNITY ASSOCIATION
Annual Membership Meeting - 2025 - Minutes
"""


def test_minutes_filed_as_notice():
    reading = read(DocumentKind.NOTICE, ANNUAL_MINUTES_AS_NOTICE, ctx())
    assert reading.model == "meeting-minutes" and reading.record.meeting_type is MeetingType.ANNUAL
    found = codes(reading)
    assert found["filed-as-notice"] == "info"
    # The members vote by ballot: no roll call is expected, but the minutes record the memberships present (Bylaws 10.10).
    assert found["membership-not-shown"] == "check"
    assert "no-roll-call" not in found and "quorum-not-shown" not in found and "votes-not-recorded" not in found


# --- Executive session and committee report ------------------------------------------------------------------------

EXECUTIVE = """\
DRAFT
EXAMPLE COMMUNITY ASSOCIATION
Executive Session of the Board of Directors
To be held on:
February 6, 2024 at 7:15pm
via Zoom
EXECUTIVE SESSION
I.
Member Discipline
II.
Delinquencies
A. Consider Payment Plan
III.
Formation of contracts
A. Handyman
IV.
Summer Picnic
EXAMPLE COMMUNITY ASSOCIATION
Special Meeting of the Board of Directors -
(Zoom)
Feb 6, 2024 7:15 PM PST
"""


def test_executive_session():
    reading = read(DocumentKind.EXECUTIVE_SESSION, EXECUTIVE, ctx())
    r = reading.record
    assert r.meeting_date == date(2024, 2, 6) and r.meeting_time == "7:15pm" and r.draft
    assert r.parent_meeting is MeetingType.SPECIAL
    assert set(r.subjects) == {ExecutiveSubject.DISCIPLINE, ExecutiveSubject.ASSESSMENTS, ExecutiveSubject.CONTRACTS}
    assert r.unlisted_topics == ("Summer Picnic",)
    assert codes(reading)["executive-topic"] == "check"


COMMITTEE = """\
EXAMPLE COMMUNITY ASSOCIATION
Community Improvement Committee Report
The community improvement committee proposes the following community
improvements:
1.
Replace bark with Crushed Stone
2.
Park Benches
If the board likes any of the proposals it could direct management to gather proposals to
consider at a future meeting.
EXAMPLE COMMUNITY ASSOCIATION
Community Improvement Committee - 2024 Report

EXAMPLE COMMUNITY ASSOCIATION
Community Improvement Committee Report
Crushed Stone
Recycled Drain Rock
$60 per cu. yard
EXAMPLE COMMUNITY ASSOCIATION
Community Improvement Committee - 2024 Report
"""


def test_committee_report():
    reading = read(DocumentKind.COMMITTEE_REPORT, COMMITTEE, ctx())
    r = reading.record
    assert reading.complete and r.committee == "Community Improvement Committee" and r.year == 2024
    assert [p.title for p in r.proposals] == ["Replace bark with Crushed Stone", "Park Benches"]
    assert r.proposals[0].amounts == (6000,)
    assert r.recommendation.startswith("If the board likes")


# --- Resolutions ------------------------------------------------------------------------------------------------

RESOLUTION_INLINE = """\
# Special Resolution - Investment of Reserve Funds.pdf

- drive_id: `x`
- mime: `application/pdf`

Special Resolution
EXAMPLE COMMUNITY ASSOCIATION
SPECIAL RESOLUTION NUMBER 20230130-2
Relating to the Investment of Reserve Moneys
WHEREAS, Section 5515 of the California Civil Code requires prudent fiscal management.
WHEREAS, the board finds a certificate of deposit prudent.
NOW, THEREFORE, BE IT RESOLVED that the Board of Directors authorizes the investment of $150,000.00 of
reserve moneys in a Certificate of Deposit.
IN WITNESS WHEREOF, we, the Board of Directors, by the signatures of the President and Treasurer, adopt this resolution.
________________________________
Alex Rivera
President
________________________________
Morgan Lee
Treasurer
Alex Rivera (Feb 3, 2023 10:52 PST)
RESOLUTION ACTION RECORD
Director Vote
President
X YES
NO
ABSTAIN
Vice President
X YES
NO
ABSTAIN
Treasurer
X YES
NO
ABSTAIN
ATTESTATION:
__________________________
Sam Park
Secretary
____________________
Date
3
Special
20230130-2
Investment of Reserve Moneys
Alex Rivera
Sam Park
Sam Park (Feb 4, 2023 23:48 PST)
Feb 4, 2023
"""


def test_resolution_inline_votes():
    reading = read(DocumentKind.RESOLUTION, RESOLUTION_INLINE, ctx())
    r = reading.record
    assert reading.complete
    assert r.resolution_type is ResolutionType.SPECIAL and r.number == "20230130-2"
    assert r.subject is ResolutionSubject.INVEST_RESERVES and r.amounts == (15_000_000,)
    assert r.adopted_on == date(2023, 1, 30)
    assert [(s.name, s.title, s.signed_on) for s in r.signers] == [("Alex Rivera", "President", date(2023, 2, 3)), ("Morgan Lee", "Treasurer", None)]
    assert [v.vote for v in r.votes] == [Vote.YES, Vote.YES, Vote.YES]
    assert (r.motion_by, r.seconded_by) == ("Alex Rivera", "Sam Park")
    assert r.attested_by == "Sam Park" and r.attestation_signed and r.attested_on == date(2023, 2, 4)
    found = codes(reading)
    assert found["signature-missing"] == "check" and found["vote"] == "info"
    assert "no-vote-record" not in found and "attestation-unsigned" not in found


BORROWING = """\
EXAMPLE COMMUNITY ASSOCIATION
SPECIAL RESOLUTION
Relating to the Borrowing of Reserve Funds to meet short-term cash flow requirements
WHEREAS, the manager has terminated its agreement and will not return the association's funds immediately, which
will result in short-term cash flow issues.
WHEREAS, The association will restore the funds within a year.
NOW, THEREFORE, BE IT RESOLVED that the Board of Directors authorizes the borrowing of $16,000.00 of reserve monies.
________________________________
Alex Rivera
President
Alex Rivera (Feb 6, 2024 20:07 PST)
RESOLUTION ACTION RECORD
Resolution Type: ______________ No. ________
Motion by: ______________ Seconded by: ______________
Director Vote
Alex Rivera
President
YES
NO
ABSTAIN
Morgan Lee
Treasurer
YES
NO
ABSTAIN
ATTESTATION:
__________________________
Sam Park
Secretary
____________________
Date
2
Special
2024-02-06-3
Borrowing and withdrawal of reserve funds
Treasurer Lee
President Rivera
X
X
"""


def test_borrowing_resolution():
    reading = read(DocumentKind.RESOLUTION, BORROWING, ctx())
    r = reading.record
    assert r.subject is ResolutionSubject.BORROW_RESERVES and r.number == "2024-02-06-3"
    assert r.adopted_on == date(2024, 2, 6) and r.amounts == (1_600_000,)
    assert (r.motion_by, r.seconded_by) == ("Treasurer Lee", "President Rivera")
    assert r.vote_marks == 2 and all(v.vote is None for v in r.votes)
    found = codes(reading)
    assert found["vote-marks"] == "check"
    assert found["attestation-unsigned"] == "check"
    assert found["borrowing-special-assessment"] == "check"
    assert found["borrowing-notice"] == "check"
    assert found["restore-reserves"] == "info"
    assert "borrowing-reasons" not in found and "borrowing-repayment" not in found


def test_resolution_without_action_record():
    text = BORROWING.split("RESOLUTION ACTION RECORD")[0]
    found = codes(read(DocumentKind.RESOLUTION, text, ctx()))
    assert found["no-vote-record"] == "check"


# --- Elections --------------------------------------------------------------------------------------------------

RESULTS = """\
PRO ELECTIONS LLC
P.O. Box 1 | Anytown, CA 95000 | info@example.com
Official Election Results
Example Community Association
2023 Board Election

Election Date:  November 21, 2023
Number of Ownership Units: 81
Number of Ballots Received: 32
Rescheduled Meeting Date(s): none
Quorum Achieved:  Yes

 BOARD ELECTION
Number of Seats Up for Election: 2 board seats
Result:

Alex Rivera

24 votes - ELECTED

Morgan Lee

20 votes – ELECTED*

Sam Park

20 votes - not elected*

*The Inspector of Elections resolved the tie vote by coin toss, pursuant to the Bylaws.

 IRS RESOLUTION
Vote on Resolution Regarding IRS Revenue Ruling No. 70-604:

Yes

31 votes - APPROVED

No

0 votes

No Response

1 ballot

I certify that the foregoing election results are true and accurate.
By: Jamie Inspector
Independent third-party Inspector of Elections
Pro Elections' Scope
Call for Candidates:
6/8/2023
Nomination Deadline:
9/8/2023
Pre-Ballot Notice:
9/18/2023
Ballot Package:
11/1/2023
Ballot Tally:
11/21/2023
"""


class _Spec:
    def units(self):
        return list(range(81))


def test_election_results():
    reading = read(DocumentKind.ELECTION_RESULTS, RESULTS, ctx(community=_Spec()))
    r = reading.record
    assert reading.complete and r.inspector == "Pro Elections LLC" and r.inspector_name == "Jamie Inspector"
    assert r.election_date == date(2023, 11, 21) and r.ownership_units == 81 and r.ballots_received == 32
    assert r.quorum_achieved is True and r.seats == 2
    assert [(c.name, c.votes, c.elected, c.tie_break) for c in r.candidates] == [
        ("Alex Rivera", 24, True, False), ("Morgan Lee", 20, True, True), ("Sam Park", 20, False, True)]
    assert r.measures[0].yes == 31 and r.measures[0].no == 0 and r.measures[0].no_response == 1 and r.measures[0].outcome == "APPROVED"
    found = codes(reading)
    assert found["ballot-timing"] == "problem"      # ballots 20 days before the tally
    assert found["tie-break"] == "info" and found["results-notice"] == "info"
    assert "unit-count" not in found and "seats-filled" not in found


ACCLAMATION = """\
PROFESSIONAL
PO Box 1
Anytown, CA 95000
ELECTION INSPECTORS
Post-Election Results and Meeting Notice
Example Community Association
2021 Election of Board Members
Pursuant to Civil Code §5120(b), the tabulated results of the board election are as follows:
Election Date:
October 6, 2021
Number of Ownership Units:
51
Number of Candidates/Seats:
3 candidates for 3 board seats
Board Term:
2 years
Candidates declared elected:
Alex Rivera, Morgan Lee, Sam Park
The number of qualified candidates was less than or equal to the number of board
seats up for election. Therefore the candidates were declared elected.
Certification:
This election is certified by
Jamie Inspector, Inspector of Elections
www.pro-ei.com
"""


def test_acclamation_results():
    reading = read(DocumentKind.ELECTION_RESULTS, ACCLAMATION, ctx(community=_Spec()))
    r = reading.record
    assert r.acclamation and r.seats == 3 and [c.name for c in r.candidates] == ["Alex Rivera", "Morgan Lee", "Sam Park"]
    assert r.inspector_name == "Jamie Inspector" and r.term == "2 years"
    found = codes(reading)
    assert found["acclamation-notices"] == "check"
    assert found["unit-count"] == "info"


BALLOT = """\
Please fill in marks like this:    ⚫                Not like this:      ✓
SECRET BALLOT
Example Community Association
2023 Board Election
   Your HOA uses cumulative voting. There are 2 Board seats up for
election. You may cast a maximum of 2 votes by filling in a maximum of 2 circles below.
 BOARD ELECTION
Alex Rivera   →
Morgan Lee   →
Sam Park   →
O
O
O
 IRS REVENUE RULING 70-604
O
O
Independent Election Management by Pro Elections LLC
SECRET BALLOT INSTRUCTIONS
Example Community Association
A ballot counter, election timeline, candidate statements and the rules governing this election may be
found here:   pro-ei.com/hoa/example
Ballots must be returned by mail so they are received by the Inspector of Elections no later
than 12pm on Nov. 21, 2023.
Ballots will be counted on Nov. 21, 2023 at 7:00pm at the Annual Meeting. The Annual
Meeting will take place by Zoom.
Members wishing to meet in person may gather at Sample Park, 100 Sample Dr, Anytown, CA 95000 (connection to the Zoom meeting will still be necessary).
The number of ballots received in this election must constitute a quorum, which is 27
ballots (i.e. 1/3 of Association Members), pursuant to Bylaws Sec. 4.6(a).
"""


def test_ballot():
    reading = read(DocumentKind.BALLOT, BALLOT, ctx())
    b = reading.record
    assert reading.complete and b.secret and b.cumulative_voting and b.seats == 2 and b.max_votes == 2
    assert b.candidates == ("Alex Rivera", "Morgan Lee", "Sam Park") and b.measures == ("IRS REVENUE RULING 70-604",)
    assert b.due == date(2023, 11, 21) and b.due_time == "12pm" and b.count_time == "7:00pm"
    assert b.count_online and b.count_location.startswith("Sample Park") and b.quorum_ballots == 27
    assert b.rules_phrase and not b.voter_identified
    found = codes(reading)
    assert "ballot-count-online" not in found and "rules-phrase" not in found


def test_ballot_that_identifies_the_voter():
    text = BALLOT.replace(" BOARD ELECTION\n", "Unit Number: ______\n BOARD ELECTION\n", 1)
    assert codes(read(DocumentKind.BALLOT, text, ctx()))["voter-identified"] == "problem"


PRE_BALLOT = """\
Notice Date: 9/20/2024
PRO ELECTIONS    PO Box 1, Anytown, CA 95000  |  info@example.com
PRE-BALLOT NOTICE FOR
EXAMPLE COMMUNITY ASSOCIATION
2024 BOARD ELECTION
THIS NOTICE IS NOT A BALLOT - BALLOTS WILL BE MAILED OUT 10/10/2024
1. The list of all candidates' names that will appear on the ballot and how to report errors or
omissions:
Alex Rivera      Morgan Lee      Sam Park
There are 3 board seats up for election. The deadline to report errors or omissions is 9/13/2024.
Owners may verify the accuracy of their individual information on the voting list by contacting Pro Elections.
2. Ballots must be received by the Inspector of Elections no later than 12pm on Nov. 19, 2024. Mail to:
P.O. Box 1, Anytown CA 95000.
3. Ballots will be counted on Nov. 19, 2024 at 7:00pm at a meeting open to all members. The meeting
will take place online.
Pursuant to Corp. Code § 7512(e), the meeting may be rescheduled to a date 20+ days later if quorum has not been
met, at which time the rescheduled meeting quorum shall be 20% (17 ballots).
"""


def test_pre_ballot_notice():
    reading = read(DocumentKind.NOTICE, PRE_BALLOT, ctx())
    n = reading.record
    assert reading.model == "pre-ballot-notice" and reading.complete
    assert n.candidates == ("Alex Rivera", "Morgan Lee", "Sam Park") and n.seats == 3
    assert n.return_deadline == date(2024, 11, 19) and n.count_date == date(2024, 11, 19)
    assert n.reconvene_statement and n.reconvene_quorum == "20% (17 ballots)"
    found = codes(reading)
    assert found["pre-ballot-late"] == "problem"      # 20 days before the ballots
    assert found["ballot-count-online"] == "check"


# --- Notices ----------------------------------------------------------------------------------------------------

HEARING = """\
EXAMPLE COMMUNITY ASSOCIATION
OWNER NAME
100 SAMPLE WALK
ANYTOWN, CA 95000
Re: Notice of Violation and Hearing
In this case, there is alleged to have been a violation of CC&Rs §4.12; that the garage door is regularly left open.
Accordingly, a hearing has been scheduled so that you may have an opportunity to appear before
the board to discuss the matter. You may attend the hearing and present evidence in your defense.
This first violation would carry a fine of $40.
The hearing will be held as indicated below:
Date:
Sep 24, 2024
Time:
7:00 pm
Location:
https://zoom.us/j/000 (Zoom)
Regrettably,
Board of Directors
NOTICE OF VIOLATION AND HEARING
"""


def test_hearing_notice():
    reading = read(DocumentKind.NOTICE, HEARING, ctx())
    n = reading.record
    h = n.violation.hearing
    assert n.notice_type is NoticeType.HEARING and h.hearing_date == date(2024, 9, 24) and h.hearing_time == "7:00 pm"
    assert h.place == "Zoom" and n.violation.fine == 4000 and h.right_to_attend and n.provisions == ("CC&Rs §4.12",)
    assert n.litigation is None and n.work is None and n.recording is None     # only the sub-type's facts
    found = codes(reading)
    assert found["hearing-notice-date"] == "check"
    assert "hearing-notice-content" not in found


def test_hearing_notice_short_and_late():
    text = HEARING.replace("You may attend the hearing and present evidence in your defense.", "").replace(
        "EXAMPLE COMMUNITY ASSOCIATION\n", "EXAMPLE COMMUNITY ASSOCIATION\nSep 20, 2024\n", 1).replace("to appear before", "to meet")
    found = codes(read(DocumentKind.NOTICE, text, ctx()))
    assert found["hearing-notice-content"] == "problem"
    assert found["hearing-notice-late"] == "problem"


def test_recorded_instrument_filed_as_notice():
    text = "Sacramento County\nRECORDING REQUESTED BY:\nDoc # 2019 0000 0001\n(Space Above Line For Recorder's Use Only)\n" \
           "NOTICE OF ELECTION UNDER THE RIGHT TO REPAIR LAW\nAND BINDING COVENANTS\n" + "text " * 30
    reading = read(DocumentKind.NOTICE, text, ctx())
    assert reading.record.notice_type is NoticeType.RECORDED_INSTRUMENT
    assert codes(reading)["recorded-instrument"] == "info"


def test_litigation_disclosure():
    text = """\
EXAMPLE COMMUNITY ASSOCIATION
Disclosure of Pending Litigation
Jul 25, 2026
Re: Statutory Disclosure of Pending Litigation
Case Name: Doe v. Example Community Association.
Court: Sample County Superior Court.
Case Number: 26CV000001.
Date Filed: July 6, 2026.
Sincerely,
Board of Directors
"""
    n = read(DocumentKind.NOTICE, text, ctx()).record
    assert n.notice_type is NoticeType.LITIGATION_DISCLOSURE and n.litigation.case_number == "26CV000001"
    assert n.litigation.filed_on == date(2026, 7, 6) and n.notice_date == date(2026, 7, 25)
    assert n.violation is None


class _Cases:
    """A specification with one suit the association defends."""

    def legal_cases(self):
        from jason.community.legal_cases import CaseEvent, CaseRole, CaseStatus, Forum, LegalCase

        return (LegalCase("suit", "Example", Forum.SUPERIOR_COURT, CaseRole.DEFENDANT, CaseStatus.PENDING, case_number="26CV000001",
                          events=(CaseEvent(date(2026, 5, 1), "incident"), CaseEvent(date(2026, 7, 6), "complaint filed"))),)


NO_LITIGATION = """\
EXAMPLE COMMUNITY ASSOCIATION
Disclosure Regarding Pending Litigation
100 Sample St
Aug 3, 2026
To Whom It May Concern,
RE: Disclosure Regarding Pending Litigation
As of the date of this letter, the Association is not a party to any pending litigation.
Sincerely,
Board of Directors
"""


def test_litigation_letters_against_the_cases_on_file():
    found = codes(read(DocumentKind.NOTICE, NO_LITIGATION, ctx(community=_Cases())))
    assert found["no-litigation-contradicted"] == "check"          # the suit was filed July 6
    earlier = NO_LITIGATION.replace("Aug 3, 2026", "Jun 19, 2026")
    assert "no-litigation-contradicted" not in codes(read(DocumentKind.NOTICE, earlier, ctx(community=_Cases())))
    other = "EXAMPLE COMMUNITY ASSOCIATION\nDisclosure of Pending Litigation\nJul 25, 2026\nRe: Statutory Disclosure of Pending " \
            "Litigation\nCourt: Sample County Superior Court.\nCase Number: 26CV000999.\nDate Filed: July 6, 2026.\nSincerely,\nBoard\n"
    assert codes(read(DocumentKind.NOTICE, other, ctx(community=_Cases())))["case-not-tracked"] == "check"


def test_work_notice():
    text = """\
EXAMPLE COMMUNITY ASSOCIATION
NO VEHICLE ACCESS
MAINTENANCE SCHEDULED
through
Apr 26, 2024 6:00 AM
Apr 26, 2024 6:00 PM
The Association has hired Sample Paving to reseal the asphalt in the guest parking lot and driveways.
Any vehicles left parked in the parking lot during the work hours will be towed away at the owner's expense.
EXAMPLE COMMUNITY ASSOCIATION
BOARD OF DIRECTORS
"""
    n = read(DocumentKind.NOTICE, text, ctx()).record
    assert n.notice_type is NoticeType.WORK and n.violation is None
    assert (n.work.work_date, n.work.starts, n.work.ends, n.work.contractor, n.work.towing) == \
        (date(2024, 4, 26), "6:00 AM", "6:00 PM", "Sample Paving", True)


@pytest.mark.parametrize("kind", [DocumentKind.MINUTES, DocumentKind.AGENDA, DocumentKind.RESOLUTION, DocumentKind.ELECTION_RESULTS,
                                  DocumentKind.BALLOT, DocumentKind.EXECUTIVE_SESSION, DocumentKind.COMMITTEE_REPORT])
def test_a_miss_stays_a_miss(kind):
    assert read(kind, "Invoice 1234\nAmount due $50.00\nThank you for your business.", ctx()) is None
