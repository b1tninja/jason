"""Minutes in the layouts the board's own template does not use: the former manager's typed minutes, hand-typed narrative
minutes, the board's annotated agenda titled "Board of Directors Open Meeting", a manager's "Board Meeting Minutes" with
M/S/P shorthand, and an emergency meeting held by email with the directors' signed consents. The excerpts follow the real
layouts with made-up people, places, and numbers."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from jason.community.document_models import ModelContext, read
from jason.community.models.meetings import MeetingBody, MeetingType, MinutesLayout, Outcome, meeting_title
from jason.community.symbols import DocumentKind

TODAY = date(2026, 9, 30)


def ctx(community=None) -> ModelContext:
    return ModelContext(community=community, data_dir=None, today=TODAY)


def minutes(text: str, community=None):
    return read(DocumentKind.MINUTES, text, ctx(community))


def codes(reading) -> set[str]:
    return {f.code for f in reading.findings}


FORMER_MANAGER = """\
EXAMPLE COMMUNITY ASSOCIATION
Regular Board of Director’s meeting
March 10, 2021 5:40 pm via zoom
Roll call:
Directors Present: Ann Able, Ben Baker, Cal Cole.
Directors Absent: None
Also present:
Management - Dee Dunn of Example Management
Members – Eve Ewing, Fay Fox, Does 1-4
Agenda approved as presented.
Minutes for the December 2020 meeting presented and approved
Financials for February 2021 were reviewed.
New Business
Board status – Sales have been fast. Director Baker was appointed and both Director Able and Director
Baker’s terms are up. Call for Candidates should go out soon.
Report from the developer – Cal Cole said the goal was to be done in about a year. Director
6. Baker asked about a staging area for construction.
Delinquencies were moved to the executive session.
Meeting Adjourned 8:36
"""


def test_former_manager_regular_meeting():
    r = minutes(FORMER_MANAGER)
    assert r is not None and r.model == "meeting-minutes"
    m = r.record
    assert (m.meeting_type, m.body, m.meeting_date) == (MeetingType.REGULAR, MeetingBody.BOARD, date(2021, 3, 10))
    assert m.layout is MinutesLayout.NARRATIVE
    assert m.directors_present == ("Ann Able", "Ben Baker", "Cal Cole")
    assert m.directors_absent == ()          # "None" is no one
    assert m.prior_minutes_approved is True
    assert m.adjourned == "8:36"
    assert m.items == ()                     # a wrapped line that begins "6." is not an item
    texts = [a.text for a in m.actions]
    assert any("was appointed" in t and t.endswith("terms are up.") for t in texts)
    assert not any("were moved" in t for t in texts)   # "Delinquencies were moved" is not "Jane Doe moved"


HAND_TYPED = """\
Board of Director’s meeting
August 26, 2021 via zoom
Meeting called to order only one Board member present numerous
homeowners
Review and approval of minutes – approve at next meeting
Developer report – remaining homes anticipated to be completed by spring
Open homeowner forum –
Landscape designs were discussed.
Adjournment - meeting adjourned at 8:15
"""


def test_hand_typed_minutes_with_one_director_lack_a_quorum():
    r = minutes(HAND_TYPED)
    assert r is not None
    m = r.record
    assert m.meeting_date == date(2021, 8, 26) and m.meeting_type is None and m.body is MeetingBody.BOARD
    assert m.quorum is False and m.layout is MinutesLayout.NO_QUORUM
    assert m.adjourned == "8:15" and m.actions == ()
    assert "no-quorum" in codes(r) and "items" not in r.missing


OPEN_MEETING = """\
Example Community Association
DRAFT Minutes of
Board of Directors Open Meeting
Held on 5/11/2022 at 6:00 pm on Zoom
Attendees: Ann Able
I.
Call to Order: Meeting called to order at
II.
Homeowner Forum:
Members may address issues during the open forum portion of the meeting.
III.
Discussion - Counsel / Developer hand-off - Tabled
IV.
Proposal - Sign Company - Revised - Approved - $30,848.13
V.
Proposal - Painting Company - Approved with modifications - $67,660
VI.
Proposal - Electrical Contractor:
a.
LED Lighting installation - Approved, Follow up with counsel -
$7,044.00
b. 1234 Deck (Dry out and Inspect) - Approved - $5,427.00
VII.
Proposal - Tree Company - $11,401 - Let's spend less on landscape repairs.
VIII.
Proposal - Landscaping Company - Tabled - $6,600
IX.
Rules and Regulations Policy, Approved plant list - Tabled
X.
FINAL ADJOURNMENT
"""


def test_open_meeting_items_marked_with_their_outcome():
    r = minutes(OPEN_MEETING)
    assert r is not None
    m = r.record
    assert m.meeting_date == date(2022, 5, 11) and m.draft is True
    assert m.layout is MinutesLayout.ANNOTATED_AGENDA
    got = {(a.outcome, a.amount) for a in m.actions}
    assert (Outcome.APPROVED, 3084813) in got
    assert (Outcome.APPROVED, 6766000) in got
    assert (Outcome.APPROVED, 704400) in got           # the amount alone on the line under the title
    assert (Outcome.APPROVED, 542700) in got
    assert (Outcome.TABLED, 660000) in got
    assert not any("Tree Company" in a.text for a in m.actions)       # no outcome marked
    plant = [a for a in m.actions if "plant list" in a.text]
    assert len(plant) == 1 and plant[0].outcome is Outcome.TABLED     # "Approved plant list" is a title, not an outcome


MANAGER_MINUTES = """\
Board Meeting Minutes
Example Community Association | November 13th, 2023 Board Meeting

Board Members:


Ann Able, President


Ben Baker, Treasurer (Absent)


Cal Cole, Secretary


Management Representative:

Dee Dunn, Example Management

Location:
Via Zoom

1. Call to Order at 5:40 PM
2. Consent Agenda – Motion to approve the consent Agenda – M/S/P
a. Minutes of Previous Meeting dated October 17th, 2023
3. Review Items – Reviewed
a. Most recent financials
4. Action Items
a. Motion to approve the 2024 Budget with a PUPM $328.49 -M/S/P
5. Member Comment Period
6. Motion to Adjourn – M/S/P
a. Being no further business before the Board of Directors, the meeting adjourned at 6:14pm.

The undersigned does hereby certify that the foregoing is a true and correct copy of the Minutes of Example Community
Association Board Meeting held on November 13th, 2017 as approved by the attending Board Members.
"""


def test_manager_minutes_with_roster_and_shorthand():
    r = minutes(MANAGER_MINUTES)
    assert r is not None
    m = r.record
    assert m.meeting_date == date(2023, 11, 13)           # not the certification's stale template date
    assert m.directors_present == ("Ann Able", "Cal Cole")
    assert m.directors_absent == ("Ben Baker",)
    assert m.called_to_order == "5:40 PM" and m.adjourned == "6:14pm"
    amounts = sorted((a.amount or 0) for a in m.actions if a.outcome is Outcome.APPROVED)
    assert amounts == [0, 32849]                          # the consent agenda and the budget; adjourning is not a decision
    assert not any("hereby certify" in a.text for a in m.actions)


EMAIL_MEETING = """\
Example Community Association
EMERGENCY MEETING OF THE BOARD OF DIRECTORS
Friday, Jul 29, 2022
via EMAIL
I.
Consent To Emergency Meeting (Civ. § 4910):
President
Vice-President
Secretary
II.
Adopt -
Special Resolution - Emergency Repair.pdf
III.
Formation of Contracts -
Example Plumbing - Quote 100.pdf
Ann Able (Aug 24, 2022 20:01 PDT)
Ben baker (Aug 24, 2022 22:31 PDT)
Ben baker
Cal Cole (Aug 25, 2022 10:31 PDT)
"""


def test_emergency_meeting_by_email_reads_as_written_consent():
    assert meeting_title(EMAIL_MEETING)[0] is MeetingType.EMERGENCY
    r = minutes(EMAIL_MEETING, SimpleNamespace(board=lambda: SimpleNamespace(seats=5)))
    assert r is not None and r.complete
    m = r.record
    assert m.layout is MinutesLayout.WRITTEN_CONSENT and m.meeting_date == date(2022, 7, 29)
    assert [n for n, _ in m.consents] == ["Ann Able", "Ben Baker", "Cal Cole"]
    assert m.consents[-1][1] == date(2022, 8, 25)
    assert [a.text for a in m.actions] == ["Adopt Special Resolution - Emergency Repair.pdf",
                                           "Formation of Contracts Example Plumbing - Quote 100.pdf"]
    finding = next(f for f in r.findings if f.code == "written-consent")
    assert finding.severity.value == "check" and "after the meeting date" in finding.message and "5 seats" in finding.message
    assert not codes(r) & {"no-roll-call", "votes-not-recorded", "quorum-not-shown"}


def test_title_variants_keep_their_kind():
    assert meeting_title("MINUTES OF THE\nORGANIZATIONAL BOARD OF DIRECTOR'S MEETING\nfollowing the Annual Members Meeting")[:2] == \
        (None, MeetingBody.BOARD)
    assert meeting_title("MINUTES OF\nRegular Board of Director’s meeting\nAdjourn to executive session of the board")[0] is \
        MeetingType.REGULAR
    assert meeting_title("Annual Meeting of the Members")[:2] == (MeetingType.ANNUAL, MeetingBody.MEMBERS)
