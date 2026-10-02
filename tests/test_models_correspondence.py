"""The correspondence models: synthetic letters, notices, and handouts in the real layouts, with made-up parties and numbers."""

from __future__ import annotations

from datetime import date

from jason.community.base import AccountPurpose, BankAccount
from jason.community.document_models import ModelContext, Severity, read
from jason.community.models.correspondence import Direction, Form, Request, Role, add_business_days
from jason.community.sources import Sender, SourceKind
from jason.community.symbols import DocumentKind

TODAY = date(2026, 9, 29)


class StubCommunity:
    corporate_name = "SAMPLEVILLE COMMUNITY ASSOCIATION"

    def senders(self):
        return (Sender("Example Bank", SourceKind.BANK, ("EXAMPLE BANK",)),
                Sender("Example Cameras", SourceKind.VENDOR, ("EXAMPLE CAMERAS",)))

    def bank_accounts(self):
        return (BankAccount("1111", AccountPurpose.OPERATING, "Example Bank", "Operating"),
                BankAccount("2222", AccountPurpose.RESERVE, "Example Bank", "Reserve CD"))


def ctx(name=""):
    return ModelContext(StubCommunity(), None, TODAY, name, "")


def codes(reading):
    return {f.code: f for f in reading.findings}


BANK_LETTER = """Example Bank, N.A. Member FDIC
Dear SAMPLEVILLE COMMUNITY ASSOCIATION:
Thank you for banking with us. Your CD ending in 2222 will mature on 05/20/2026.
Projected Value at Maturity: $100,000.50
You'll only be able to make changes starting on 05/20/2026 through 05/30/2026.
To schedule a meeting, please visit our site or call us.
Sincerely,
Customer Service
May 05, 2026
Important: Your CD is maturing soon; let's review your options
SAMPLEVILLE COMMUNITY ASSOCIATION
100 EXAMPLE WAY
"""


def test_bank_letter_reads_parties_dates_and_reserve_account():
    reading = read(DocumentKind.CORRESPONDENCE, BANK_LETTER, ctx())
    r = reading.record
    assert reading.model == "letter" and reading.complete, reading.missing
    assert r.form is Form.LETTER and r.dated == date(2026, 5, 5)
    assert (r.sender, r.sender_role) == ("Example Bank", Role.BANK)
    assert r.recipient_role is Role.ASSOCIATION and r.direction is Direction.INBOUND
    assert r.subject.startswith("Important: Your CD is maturing")
    assert r.accounts == ("2222",)
    assert [d.on for d in r.deadlines] == [date(2026, 5, 20), date(2026, 5, 30)]
    assert r.amounts[0].cents == 10_000_050
    assert r.closing == "Sincerely" and r.signer_role == "Customer Service"
    assert r.response_requested and r.respond_by == date(2026, 5, 30)
    found = codes(reading)
    assert "(past)" in found["response-deadline"].message
    assert found["reserve-account"].authority == "CIV 5200(a)(7), 5510, 5515"
    unknown = read(DocumentKind.CORRESPONDENCE, BANK_LETTER.replace("2222", "9999"), ctx())
    assert codes(unknown)["unknown-account"].severity is Severity.CHECK


RECORDS_REQUEST = """June 1, 2026
Dear Board of Directors,
I own the unit at 9999 Macon Drive. Under Civil Code section 5205 I request copies of the association records listed below:
the 2025 bank statements and the 2026 budget. Please respond within ten (10) business days.
Sincerely,
A. Member
"""


def test_owner_records_request_sets_the_5210_clocks():
    reading = read(DocumentKind.CORRESPONDENCE, RECORDS_REQUEST, ctx())
    r = reading.record
    assert (r.sender, r.sender_role) == ("an owner", Role.OWNER)
    assert r.recipient_role is Role.BOARD and r.direction is Direction.INBOUND
    assert "A. Member" not in (r.sender, r.recipient)
    assert r.addresses == ("9999 MACON DR",) and r.statutes == ("CIV 5205",)
    assert Request.RECORDS in r.requests
    assert r.respond_by == add_business_days(date(2026, 6, 1), 10) == date(2026, 6, 15)
    found = codes(reading)
    assert found["records-request"].severity is Severity.CHECK and found["records-request"].authority == "CIV 5205(f), 5210(b)"
    assert "June 15, 2026" in found["records-request"].message and "July 1, 2026" in found["records-request"].message


IDR_REQUEST = """July 2, 2026
Dear Board,
I dispute the fine on my unit and request internal dispute resolution (meet and confer) under Civil Code 5910.
Sincerely,
"""


def test_idr_request_is_a_check_on_the_association():
    found = codes(read(DocumentKind.CORRESPONDENCE, IDR_REQUEST, ctx()))
    assert found["idr-request"].authority == "CIV 5910(c), (g); 5915(b)"


HEARING_NOTICE = """SAMPLEVILLE COMMUNITY ASSOCIATION
August 1, 2026
Dear Homeowner:
RE: Notice of Board Hearing
The Board will hold a hearing on August 6, 2026 at 7:00 pm on Zoom to consider the alleged violation of CC&Rs §4.15 at your unit.
You have the right to attend and may address the Board.
Sincerely,
Board of Directors
"""


def test_hearing_notice_short_of_ten_days():
    reading = read(DocumentKind.CORRESPONDENCE, HEARING_NOTICE, ctx())
    r = reading.record
    assert (r.sender, r.sender_role) == ("SAMPLEVILLE COMMUNITY ASSOCIATION", Role.BOARD)
    assert r.direction is Direction.OUTBOUND and r.recipient_role is Role.OWNER
    assert r.hearing_on == date(2026, 8, 6) and r.document_sections == ("CC&Rs 4.15",)
    found = codes(reading)
    assert found["hearing-notice-days"].severity is Severity.PROBLEM and found["hearing-notice-days"].authority == "CIV 5855(a)"
    assert "hearing-notice-elements" not in found
    ok = read(DocumentKind.CORRESPONDENCE, HEARING_NOTICE.replace("August 1, 2026", "July 20, 2026"), ctx())
    assert codes(ok)["hearing-notice-days"].severity is Severity.INFO


RFR = """SAMPLEVILLE COMMUNITY ASSOCIATION
March 2, 2026
Dear Homeowner:
RE: Request for Resolution
The Association requests alternative dispute resolution of the dispute over the balcony at your unit.
You must respond within 30 days of receipt or the request will be deemed rejected.
Sincerely,
Board of Directors
"""


def test_request_for_resolution_needs_the_adr_article():
    found = codes(read(DocumentKind.CORRESPONDENCE, RFR, ctx()))
    assert "April 1, 2026" in found["request-for-resolution"].message
    assert found["adr-article-not-included"].authority == "CIV 5935(a)(4)"
    with_article = RFR + "\n5925. (a) As used in this article:\n"
    assert "adr-article-not-included" not in codes(read(DocumentKind.CORRESPONDENCE, with_article, ctx()))


ESCROW = """SAMPLEVILLE COMMUNITY ASSOCIATION
INSTRUCTIONS FOR ESCROW
We do not currently charge a transfer fee, or for digital copies of Civ. §4525 documents.
Owner Occupancy: see §4.15 of the CC&Rs. See: VA Loan - Presale Conditions.pdf
Sampleville Community Association - Instructions for Escrow
"""


def test_escrow_handout():
    reading = read(DocumentKind.CORRESPONDENCE, ESCROW, ctx())
    r = reading.record
    assert reading.model == "handout" and reading.complete, reading.missing
    assert (r.title, r.recipient_role, r.direction) == ("Instructions for Escrow", Role.ESCROW, Direction.OUTBOUND)
    assert r.sender == "SAMPLEVILLE COMMUNITY ASSOCIATION" and r.statutes == ("CIV 4525",)
    assert r.document_sections == ("CC&Rs 4.15",) and r.enclosures == ("VA Loan - Presale Conditions.pdf",)
    assert codes(reading)["resale-documents"].authority == "CIV 4530(a), (b)"


FLYER = """MOST SPOOKY UNIT CONTEST
Sampleville Community Association - Halloween Decoration Contest
The HOA is thrilled to announce our first contest. Have your decorations up and ready by October 30, 2025.
1st Place - $100.00 gift card
"""


def test_notice_without_an_issue_date():
    reading = read(DocumentKind.CORRESPONDENCE, FLYER, ctx("Halloween Contest Poster.pdf"))
    r = reading.record
    assert reading.model == "member-notice" and r.form is Form.NOTICE
    assert r.recipient_role is Role.MEMBERS and r.title == "Halloween Decoration Contest"
    assert r.deadlines[0].on == date(2025, 10, 30) and r.amounts[0].label == "1st Place"
    assert reading.missing == ("dated",)
    assert "October 30, 2025" in codes(reading)["missing-dated"].message


RECORD = """Example Cameras, and the Custodian of Record herein, certifies that this record is a true and accurate exact copy of
the original record made and kept in the course of regularly conducted business activity.
Custodian of Records
Investigative Summary
Report ID: 0000-1111
Date Created: 9/28/2025, 8:58 AM PDT
Sampleville Community Association (CA)
"""


def test_certified_record():
    reading = read(DocumentKind.CORRESPONDENCE, RECORD, ctx())
    r = reading.record
    assert reading.model == "certified-record" and reading.complete, reading.missing
    assert (r.sender, r.sender_role, r.dated) == ("Example Cameras", Role.VENDOR, date(2025, 9, 28))
    assert r.subject == "Investigative Summary" and r.signer_role == "Custodian of Records"


GUIDE = """Section D. Condos, Coops, Timeshares
The Residential Condominium Building Association Policy (RCBAP) of the National Flood Insurance Program (NFIP) insures the
building. Refer to the NFIP Flood Insurance Manual.
"""


def test_publication_and_a_miss():
    reading = read(DocumentKind.CORRESPONDENCE, GUIDE, ctx())
    assert reading.model == "publication" and reading.record.sender_role is Role.AGENCY
    assert reading.record.subject == "Section D. Condos, Coops, Timeshares"
    assert read(DocumentKind.CORRESPONDENCE, "a page of numbers 12 34 56", ctx()) is None
