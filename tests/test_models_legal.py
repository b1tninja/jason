"""The legal group's document models, on synthetic excerpts in the real layouts.

Every name, street number, parcel, account, and amount here is made up; the street names are the development's so the
address reader finds them.
"""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.document_models import ModelContext, Severity, read, to_plain
from jason.community.models.legal_collections import (
    OwnerHistoryModel,
    OwnerStatementModel,
    PreLienElement,
    PreLienNoticeModel,
    ReimbursementNoticeModel,
    SenderKind,
)
from jason.community.models.legal_inspections import InspectionReportModel, Result, SignalServiceReportModel
from jason.community.models.legal_letters import LegalBriefModel, LegalLetterModel, LetterType, Recipient
from jason.community.models.legal_liens import AssessmentLienModel, LienReleaseBondModel, MechanicsLienModel
from jason.community.models.legal_records import EscrowRequestModel, FormModel, FormType, MembershipListModel
from jason.community.models.legal_shared import ChargeKind, former_sections, late_charge_cap, words_to_cents
from jason.community.symbols import Building, DocumentKind

TODAY = date(2026, 9, 29)
FAKE_NAME = "Quincy Zephyr"


class FakeCommunity:
    """The slice of the specification the checks consult, with made-up units and parcels."""

    _buildings = {"3101 ENCHANTED WALK": Building.BLDG_2, "3102 ENCHANTED WALK": Building.BLDG_3, "3101 MAGICAL WALK": Building.BLDG_4,
                  "3101 MACON DR": Building.BLDG_1, "5601 WHIMSICAL LN": Building.BLDG_8}

    def units(self):
        return tuple(f"2011170099{n:04d}" for n in range(1, 82))

    def parcels(self):
        return self.units() + ("20111700990900",)

    def building_for_address(self, address):
        b = self._buildings.get(address)
        return SimpleNamespace(number=b) if b else None

    def mail_addresses(self):
        return (SimpleNamespace(kind=SimpleNamespace(name="CURRENT"), words=("901 H ST",), requires=("PMB 188",)),)

    def senders(self):
        from jason.community.sources import Sender, SourceKind

        return (Sender("Example Management Group", SourceKind.MANAGER, ("EXAMPLE MANAGEMENT",)),
                Sender("Example Collections Law", SourceKind.LAW_FIRM, ("EXAMPLE & SAMPLE",), role="assessment collections"),
                Sender("Sample & Counsel LLP", SourceKind.LAW_FIRM, ("SAMPLE & COUNSEL",)),
                Sender("Example Roofing", SourceKind.VENDOR, ("EXAMPLE ROOFING",)))

    def obligations(self):
        return (SimpleNamespace(name="Backflow assembly test", every_years=1, authority="annual test notice"),
                SimpleNamespace(name="Fire sprinkler inspection and test", every_years=1, authority="NFPA 25"))


def ctx(name: str = "") -> ModelContext:
    return ModelContext(community=FakeCommunity(), today=TODAY, name=name)


def codes(findings, severity: Severity | None = None) -> set[str]:
    return {f.code for f in findings if severity is None or f.severity is severity}


def no_name(record) -> None:
    assert "zephyr" not in json.dumps(to_plain(record), default=str).lower()


# ---------------------------------------------------------------------------------------------------- shared helpers

def test_late_charge_cap_is_ten_percent_or_ten_dollars():
    assert late_charge_cap(32000) == 3200
    assert late_charge_cap(5000) == 1000


def test_words_to_cents_reads_a_written_sum():
    assert words_to_cents("in the sum of Two Hundred Forty-nine Thousand Four Hundred Ten & 26/100 lawful") == 24941026
    assert words_to_cents("no sum here") is None


def test_former_sections():
    assert former_sections("In accordance with Civil Code Section 1366 (c) and Section 1369.520 of the Civil Code") == ("1366", "1369.520")


# ---------------------------------------------------------------------------------------------------- pre-lien notice

LETTER_2022 = f"""MYSTIQUE COMMUNITY ASSOCIATION
{FAKE_NAME}

3101 Enchanted Walk
Sacramento, CA 95835

Mystique Community Association - Notice of Default and Demand for Payment (Civ. §  5660)
December 22, 2022

MYSTIQUE COMMUNITY ASSOCIATION
Board of Directors - board@example.org
Manager - manager@helsing.example

RE: NOTICE OF DEFAULT AND DEMAND FOR PAYMENT

Dear {FAKE_NAME}:

Our records as of 12/22/22 indicate that you are more than 45 days delinquent in
payment of your assessment installments together with any late charges, interest and costs
incurred.
A general description of the collection and lien enforcement procedures of the
association and the method of calculation of the amount owed can be found in our Assessment
Collection Policy, a copy of which has been enclosed. In accordance with our collection policy
we are sending this written Notice of Default and Demand for Payment informing you that it is
the intent of the Association to either take civil action in Small Claims Court or, if the delinquent
amount exceeds $1,800.00, by recording a "Notice of Delinquent
Assessment". A decision about the recording of the lien would be made at an Open Board
Meeting.
If payment in full is not received within 15 days of receipt of this written notice of default
and demand for payment, a "Notice of Delinquent Assessment" may be recorded.
If payment in full is not received within 30 days of the recording of the "Notice of
Delinquent Assessment", the Association may initiate a judicial or nonjudicial foreclosure.

Page 1 of 1
Transactions From Last Zero Dollar Balance
Account Transaction Report
Example & Sample, PC
Zephyr, Quincy
3101 Enchanted Walk Bldg 2 #99
Property Address
Owner Name
Account Number
ARDM-BEGBAL-1111111-1
Incoming Beginning Balance
100.00
100.00
12/31/21
RAS-2022M1-2222222-1
Assessment for January 2022
295.00
395.00
01/01/22
LFC-2022M1-3333333
Late Payment Charges for January
2022
29.50
424.50
01/16/22
FCC-2022M1-4444444
Finance Charges for January 2022
3.95
428.45
02/01/22
1234567890
Payment
100.00
328.45
02/05/22
328.45
Total Due:
12/22/2022 7:59:06 AM

IMPORTANT NOTICE: IF YOUR SEPARATE INTEREST IS PLACED IN
FORECLOSURE BECAUSE YOU ARE BEHIND IN YOUR
ASSESSMENTS, IT MAY BE SOLD WITHOUT COURT ACTION.

Statement of Rights
● You have the right to inspect the association records pursuant to Civil Code § 5205.
● You shall not be liable to pay the charges, interest, and costs of collection, if it is
determined the assessment was paid on time to the association.
● You have the right to request a meeting with the board to discuss a payment plan as
provided in Civil Code Section 5665.
● You have the right to dispute the assessment debt by submitting a written request for
dispute resolution to the association pursuant to the association's "meet and confer"
program.
● You have the right to request alternative dispute resolution with a neutral third party.

MYSTIQUE COMMUNITY ASSOCIATION
ASSESSMENT COLLECTION POLICY
EFFECTIVE: September 1, 2007
In accordance with Civil Code Section 1366 (c), installments shall be delinquent 15 days thereafter.
3.
A late charge not exceeding 10% of the delinquent assessment installment or
$10.00, whichever is greater.
4.
Interest on all sums specified above at the rate of 12% per
annum.

California Civil Code
§ 5660.
At least 30 days prior to recording a lien upon the separate interest
of the owner of record to collect a debt that is past due under
Section 5650, the association shall notify the owner of record in
writing by certified mail of the following:
(d) The right to request a meeting with the board as provided in
Section 5665.
"""


def test_pre_lien_notice_with_ledger_and_policy():
    reading = read(DocumentKind.DELINQUENCY_NOTICE, LETTER_2022, ctx())
    assert reading is not None and reading.model == "pre-lien-notice" and reading.complete
    r = reading.record
    assert r.notice_date == date(2022, 12, 22)
    assert r.property_address == "3101 ENCHANTED WALK" and r.building is Building.BLDG_2 and r.unit == "99"
    assert r.names_owner and r.cure_days == 15 and r.lien_threshold == 180000 and r.board_decides_lien
    # The board's own letterhead: the association sent it, and the firm the directory lists printed the ledger.
    assert r.sender_kind is SenderKind.ASSOCIATION and r.ledger_by == "Example Collections Law"
    assert [c.kind for c in r.charges] == [ChargeKind.BALANCE_FORWARD, ChargeKind.ASSESSMENT, ChargeKind.LATE_CHARGE,
                                           ChargeKind.INTEREST, ChargeKind.PAYMENT]
    assert r.total_due == 32845 and r.late_charges == 2950 and r.payments == 10000
    assert set(r.elements) == set(PreLienElement)
    assert r.policy_effective == date(2007, 9, 1) and r.policy_late_charge_percent == 10 and r.policy_interest_percent == 12
    assert r.statute_reprinted and r.former_sections == ("1366",)
    found = reading.findings
    assert "lien-sooner-than-30-days" in codes(found, Severity.PROBLEM)
    assert {"certified-mail-not-shown", "cites-former-sections"} <= codes(found, Severity.CHECK)
    assert "pre-lien-element-missing" not in codes(found)
    no_name(r)


def test_a_pre_lien_notice_takes_its_attorney_from_the_sender_directory():
    """The sender is the attorney only when the head names a law firm the directory lists and is not the board's own
    letterhead. A firm it does not list, or a vendor, is not the sender: the association is."""
    counsel = LETTER_2022.replace("MYSTIQUE COMMUNITY ASSOCIATION\nBoard of Directors - board@example.org\n",
                                  "Example & Sample, PC\nAttorneys at Law\n", 1)
    r = PreLienNoticeModel().parse(counsel, ctx())
    assert (r.sender, r.sender_kind) == ("Example Collections Law", SenderKind.ATTORNEY)
    for head in ("Another Firm, PC\nAttorneys at Law\n", "Example Roofing\n"):
        other = PreLienNoticeModel().parse(counsel.replace("Example & Sample, PC\nAttorneys at Law\n", head, 1), ctx())
        assert other.sender_kind is SenderKind.ASSOCIATION
    # A community with no sender directory names no firm at all.
    bare = PreLienNoticeModel().parse(counsel, ModelContext(community=object(), today=TODAY))
    assert bare.sender_kind is SenderKind.ASSOCIATION and bare.ledger_by == "" and bare.manager == ""


def test_statute_reprint_does_not_count_as_the_notice():
    letter = LETTER_2022.split("IMPORTANT NOTICE")[0] + LETTER_2022[LETTER_2022.index("California Civil Code\n§ 5660."):]
    r = PreLienNoticeModel().parse(letter, ctx())
    assert PreLienElement.BOARD_MEETING not in r.elements
    assert PreLienElement.FORECLOSURE_WARNING not in r.elements
    missing = [f for f in PreLienNoticeModel().check(r, ctx()) if f.code == "pre-lien-element-missing"]
    assert {f.authority for f in missing} >= {"CIV 5660(a)", "CIV 5660(c)", "CIV 5660(d)"}
    assert all(f.severity is Severity.PROBLEM for f in missing)


LETTER_2024 = f"""Oct 1, 2024
MYSTIQUE COMMUNITY ASSOCIATION
Board of Directors - board@example.org
{FAKE_NAME}
3101 ENCHANTED WALK
Sacramento, CA 95835
RE: NOTICE OF DEFAULT AND DEMAND FOR PAYMENT
Dear {FAKE_NAME.upper()}:
According to our records as of
you are more than 45 days delinquent in
Oct 1, 2024
payment of your assessment installments. The board of directors would like to offer to set up a payment plan, which will help
avoid additional late fees, and interest. If a payment plan is not set up, and the balance exceeds
$1,500 we will refer the account to collections. If they are unable to collect the amount, and the
delinquent assessments exceed $1,800 they may begin foreclosure proceedings.
A general description of the collection and lien enforcement procedures of the
association and the method of calculation of the amount owed can be found in our Assessment
Collection Policy, a copy of which has been enclosed.
If payment in full is not received within 15 days of receipt of this written notice of default
and demand for payment, a "Notice of Delinquent Assessment" may be recorded.
Mystique Community Association - Pre-Lien Notice (Civ. § 5660)
"""


def test_pre_lien_notice_without_itemized_statement():
    reading = read(DocumentKind.DELINQUENCY_NOTICE, LETTER_2024, ctx())
    r = reading.record
    assert r.title == "Pre-Lien Notice" and r.notice_date == date(2024, 10, 1)
    assert r.payment_plan_offered and r.collections_threshold == 150000
    # A letter without its itemized statement has no total to read: the reading is complete, and the shortfall is a finding.
    assert reading.complete and r.total_due is None and "missing-total-due" not in codes(reading.findings)
    assert "no-itemized-statement" in codes(reading.findings, Severity.CHECK)
    assert {"policy-not-in-text", "collections-referral"} <= codes(reading.findings, Severity.INFO)
    # The collection agency, not the board, is said to begin foreclosure.
    assert r.foreclosure_by_agent and "foreclosure-by-agent" in codes(reading.findings, Severity.CHECK)
    assert r.lien_threshold == 180000 and "foreclosure-floor-not-stated" not in codes(reading.findings)
    earlier = LETTER_2024.replace("$1,500 we will refer the account to collections. If they are unable to collect the amount, and the\n"
                                  "delinquent assessments exceed $1,800 they may begin foreclosure proceedings.",
                                  "$1,800 we will be forced to refer the account to collections. If they are unable to collect the\n"
                                  "amount, they will begin foreclosure proceedings.")
    reading = read(DocumentKind.DELINQUENCY_NOTICE, earlier, ctx())
    assert reading.record.collections_threshold == 180000 and reading.record.lien_threshold is None
    assert codes(reading.findings, Severity.CHECK) >= {"foreclosure-by-agent", "foreclosure-floor-not-stated"}


REIMBURSEMENT = f"""
ZEPHYR QUINCY
3101 MAGICAL WALK

RE: Reimbursement Assessment for Necessary Repairs to address water leak

Dear ZEPHYR QUINCY:

As you know the leak that caused the water damage to the garage emanated from the water line in your unit.
The Association hired Example Construction to make repairs, and since it originated from
the plumbing in your unit (CC&R §7.4(e)), we are levying a reimbursement assessment for the
cost of the repairs, totalling $1,250. The invoices from the contractor are attached.
Attached Invoices:
Inv_100_from_Example_Construction.pdf

Mystique Community Association
Board of Directors
Reimbursement Assessment -
May 1, 2025
"""


def test_reimbursement_notice():
    reading = read(DocumentKind.DELINQUENCY_NOTICE, REIMBURSEMENT, ctx())
    assert reading.model == "reimbursement-assessment-notice" and reading.complete
    r = reading.record
    assert r.amount == 125000 and r.notice_date == date(2025, 5, 1) and r.building is Building.BLDG_4
    assert r.ccr_sections == ("7.4(e)",) and r.invoices == ("Inv_100_from_Example_Construction.pdf",)
    assert "no-hearing-notice" in codes(reading.findings, Severity.CHECK)
    assert ReimbursementNoticeModel().parse(LETTER_2024, ctx()) is None


# ---------------------------------------------------------------------------------------------------- owner statement

def _statement(amount_due: str) -> str:
    return f"""Mystique Community Association
901 H St Ste 120
PMB 188
Sacramento, California 95814
{FAKE_NAME}
3101 MAGICAL WALK
Sacramento, California 95835
Unit: 3101 MAGICAL WALK
Sacramento, California 95835
ALL CURRENT CHARGES
DUE DATE
AMOUNT
Regular Assessment (monthly)
Member Dues
Pay before 04/16/2024 to avoid a late fee of 10.00% of the remaining balance.
Pay before 05/01/2024 to avoid a late fee of 0.83% of the remaining balance, repeating every month until paid
in full.
04/01/2024
$320.00
Late Fee
10% ($32.00) late fee for charge "Regular Assessment (monthly)" due on 04/01/2024
04/16/2024
$32.00
Late Fee
10% ($32.00) late fee for charge "Regular Assessment (monthly)" due on 04/01/2024
04/16/2024
$32.00
Interest
0.83% ($2.66) late fee for charge "Regular Assessment (monthly)" due on 04/01/2024
05/01/2024
$2.66
Generated on: 05-12-2024 09:16am PDT
AMOUNT DUE: {amount_due}
Please detach along this line and return this slip with your payment to ensure proper posting.
"""


def test_owner_statement_repeated_text_lines():
    reading = read(DocumentKind.OWNER_STATEMENT, _statement("$354.66"), ctx())
    r = reading.record
    assert reading.complete and r.statement_date == date(2024, 5, 12) and r.building is Building.BLDG_4
    assert r.duplicated_lines == 1 and r.unique_total == 35466 and r.lines_total == 38666
    assert r.late_fee_percent == 10 and r.interest_percent_monthly == 0.83
    assert r.late_fee_after_days == (15,) and r.interest_after_days == (30,)
    assert codes(reading.findings) == {"repeated-lines-in-text"}
    no_name(r)


def test_owner_statement_duplicate_billed():
    reading = read(DocumentKind.OWNER_STATEMENT, _statement("$386.66"), ctx())
    assert "duplicate-charges-billed" in codes(reading.findings, Severity.PROBLEM)


# ---------------------------------------------------------------------------------------------------- owner history

HELSING = f"""Mystique Community Association
Example Management Group, Inc.
100 Example Parkway, Suite 100
Anytown, CA 90000
 {FAKE_NAME}
3101 Enchanted Walk Bldg 2  #99
Sacramento, CA 95835
Property Address:
3101 Enchanted Walk  99
Account #:
00000
Code
Date
Amount
Balance Check#
Memo
Balance Forward:
0.00
ASSOC ASSESSMENT
1/1/2023
320.00
320.00
Monthly Assessment
ASSOC ASSESSMENT
2/1/2023
320.00
640.00
Monthly Assessment
LATE FEE
2/15/2023
64.00
704.00
Delinquent
Interest - Delinquent Accts
2/28/2023
7.04
711.04
Delinquent
PAYMENT
3/1/2023
-711.04
0.00 1234567
FILE.DAT
Current
30 - 59 Days
60 - 89 Days
>90 Days
Balance:
0.00
0.00
0.00
0.00
0.00
3/7/2024
"""


def test_owner_history_ledger():
    reading = read(DocumentKind.OWNER_HISTORY, HELSING, ctx())
    r = reading.record
    assert reading.complete and r.manager == "Example Management Group" and r.report_date == date(2024, 3, 7) and r.names_owner
    (a,) = r.accounts
    assert a.property_address == "3101 ENCHANTED WALK" and a.building is Building.BLDG_2 and a.unit == "99"
    assert (a.entries, a.assessments, a.late_fees, a.interest, a.payments, a.balance) == (5, 64000, 6400, 704, 71104, 0)
    assert a.aging == (0, 0, 0, 0) and a.balance_breaks == 0
    assert a.early_late_fees == 1 and a.several_installment_late_fees == 1 and a.over_cap_late_fees == 0
    found = codes(reading.findings)
    assert {"late-fee-before-delinquent", "late-charge-several-installments"} <= found
    assert "late-charge-over-cap" not in found and "aging-disagrees" not in found
    no_name(r)


# ---------------------------------------------------------------------------------------------------- liens

LIEN = f"""Recording Requested by and
Sacramento County
When Recorded Mail to:
Doc # 202401020111
Fees
$101.00
EXAMPLE & SAMPLE, PC
1/2/2024
1:18:08 PM
1787 Tribute Road, Suite D
Sacramento, California 95815
NOTICE OF CLAIM OF LIEN FOR DELINQUENT ASSESSMENTS
NOTICE IS HEREBY GIVEN that MYSTIQUE COMMUNITY ASSOCIATION, a
California nonprofit mutual benefit corporation (the "Association"), whose address for the
purpose of all matters addressed herein is 1787 Tribute Road, Suite D, Sacramento, California
95815, pursuant to the authority of that certain Restated Declaration, recorded on September 20, 2007, in
Book 20070920, at Page 937, in the Official Records, does hereby declare its continuing lien against
the property described in Exhibit "A", to secure payment of unpaid assessments and other
amounts due to the Association from {FAKE_NAME.upper()}, owner, in the aggregate total amount of $2,000.00 as of December 1,
2023, as specified in the Itemized Statement attached as Exhibit "B" hereto.
To secure payment of said amounts, the Association hereby elects to sell the Property,
and designates EXAMPLE FORECLOSURE SERVICES, a California corporation, whose
address is 100 Example Road, Suite 1, Auburn, California 95603, as the trustee authorized
by the Association to enforce said assessment lien by private sale.
Dated: December 1, 2023
Pursuant to Civil Code section
5675 (e), the claimant will mail
copy of lien via certified and
regular mail to named party(ies)
within ten days of recording.
MYSTIQUE COMMUNITY ASSOCIATION
By
Alex Counsel
Attorney and Authorized Agent
- NOTARIAL ACKNOWLEDGMENT ATTACHED -

EXHIBIT "A"
A Condominium comprised of:
PARCEL ONE:
Unit 99, in Building 2 as depicted, described and defined in the Condominium Plan for Mystique
APN: 201-1170-099-0001
Notary Public

EXHIBIT "B"
ITEMIZED STATEMENT OF AMOUNT DUE
AS OF December 1, 2023
Re: Mystique Community Assn/Liens - Zephyr (000-L-000)
3101 Enchanted Walk - Sacramento
Unpaid and delinquent regular assessment, due for
the months of January through May, 2023
(5
@
$320.00/month) . . . . . . . . . . . . . . . . . . . $ 1,600.00
Unpaid late charges, at 10% for each month . . . . . $
160.00
Association's Costs of Collection ........................ $
200.00
Interest(@ 12% annum) through 11/30/23 ................. $
40.00
Total Now Due ................................. $ 2,000.00
"""


def test_assessment_lien():
    reading = read(DocumentKind.RECORDED_LIEN, LIEN, ctx())
    assert reading.model == "notice-of-delinquent-assessment" and reading.complete
    r = reading.record
    assert r.document_number == "202401020111" and r.recorded == date(2024, 1, 2) and r.recording_fee == 10100
    assert r.amount == 200000 and r.items_total == 200000 and len(r.items) == 4
    assert r.items[0].months == 5 and r.items[0].rate == 32000 and r.items[0].kind is ChargeKind.ASSESSMENT
    assert r.delinquent_assessments == 160000 and r.interest_rate_percent == 12 and r.late_charge_percent == 10
    assert r.trustee == "EXAMPLE FORECLOSURE SERVICES" and r.trustee_address.startswith("100 Example Road")
    assert r.building is Building.BLDG_2 and r.unit == "99" and r.apn == "20111700990001" and r.names_owner
    assert r.signer_capacity == "Attorney and Authorized Agent" and r.mailing_statement and r.dated == date(2023, 12, 1)
    found = reading.findings
    assert {"signed-by-agent", "mail-copy", "pre-lien-notice", "board-vote"} <= codes(found, Severity.CHECK)
    assert "not-foreclosable" in codes(found, Severity.INFO)          # $1,600 of assessments over 5 months
    assert not codes(found, Severity.PROBLEM)
    no_name(r)
    # The requester is the law firm the sender directory lists, by its name there. One it does not list is not named
    # as that firm: the reader falls back to the first line of the recorder's block.
    assert r.requested_by == "Example Collections Law"
    other = read(DocumentKind.RECORDED_LIEN, LIEN.replace("EXAMPLE & SAMPLE, PC", "ANOTHER FIRM, PC"), ctx()).record
    assert other.requested_by == "Sacramento County"


def test_assessment_lien_items_disagree():
    reading = read(DocumentKind.RECORDED_LIEN, LIEN.replace("$ 1,600.00", "$ 1,700.00"), ctx())
    assert "items-disagree" in codes(reading.findings, Severity.PROBLEM)


MECHANICS = """Recording Requested By And When Recorded Mail To:
EXAMPLE LAW LLP
100 Capitol Mall
Sacramento, CA 95814
Sacramento County
Clerk/Recorder
Doc # 202203010001
3/1/2022
NOTICE AND CLAIM OF MECHANIC'S LIEN
The undersigned Example Lumber Company, Inc. ("Claimant"), whose address is 1 Mill Way,
Boise, Idaho 83642, claims a mechanic's lien upon the following real
property located at:
3101 Magical Walk (also known as APN: 201-1170-099-0001)
3102 Enchanted Walk (also known as APN: 201-1170-099-0002)
Together, all of the aforementioned parcels are referred to as the "Properties."
The sum of $10,000.00 together with interest thereon at the legal rate is due Claimant, after
deducting all just credits and offsets, for lumber and building materials that were furnished by
Claimant. Claimant furnished said material at the request of, and under contract with, Example Framing, Inc.
whose address is 1 Frame Court, Rocklin, CA 95677. The name and address of the
reputed prime contractor is Example Development, Inc. whose address is 1 Ocean Blvd., Santa Monica, CA 90405.
The name and address of the owner or
reputed owner of the Properties is Example Builders LLC whose address is 1 Ocean Blvd., Santa Monica, CA 90405.
NOTICE OF MECHANIC'S LIEN ATTENTION!
Upon the recording of the enclosed MECHANIC'S LIEN ... GO TO THE CONTRACTORS' STATE LICENSE
BOARD WEB SITE AT www.cslb.ca.gov.
VERIFICATION
I declare under penalty of perjury under the laws of the State of California that the foregoing is
true and correct.
PROOF OF SERVICE AFFIDAVIT
Certified Mail, Return Receipt Requested
Signed on March 1, 2022, at Sacramento, California.
RELEASE OF CLAIM OF LIEN
Example Lumber Company, Inc. hereby releases in its entirety that certain Mechanic's Lien
which Claimant caused to be recorded in the Official Records of the County Recorder of Sacramento
on March I, 2022, document number 2022-020 I 0005 upon the following real property:
DATED: March 30, 2022
PROOF OF SERVICE AFFIDAVIT
"""


def test_mechanics_lien_with_release():
    reading = read(DocumentKind.RECORDED_LIEN, MECHANICS, ctx("MECHANICS LIEN 202203010002.pdf"))
    assert reading.model == "mechanics-lien" and reading.complete
    r = reading.record
    assert r.claimant == "Example Lumber Company, Inc." and r.amount == 1000000 and r.work == "lumber and building materials"
    assert r.hired_by == "Example Framing, Inc." and r.reputed_owner == "Example Builders LLC"
    assert r.properties == ("3101 MAGICAL WALK", "3102 ENCHANTED WALK") and r.buildings == (Building.BLDG_3, Building.BLDG_4)
    assert r.statutory_notice and r.verified and r.proof_of_service and r.service_method == "certified mail"
    (release,) = r.releases
    assert release.released_number == "202202010005" and release.released_recorded == date(2022, 3, 1)
    found = reading.findings
    assert "action-deadline-passed" in codes(found, Severity.INFO)
    assert "file-name-number-differs" in codes(found, Severity.CHECK)
    assert "lien-part-not-in-text" not in codes(found)


def _bond(sum_words: str) -> str:
    return f"""SPACE DIRECTLY ABOVE RESERVED FOR RECORDER'S USE
BOND FOR RELEASE OF MECHANIC'S LIEN
That we,
Example Builders LLC
_ as Principal and
Example Surety Company
,
a corporation organized and existing under the laws of the State of Ohio
, as Surety, are held and firmly
bound unto
Example Lumber Company, Inc.
Obligee, in the sum of
{sum_words}
lawful money of the United States of America.
WHEREAS, that certain real property located at 3101 Magical Walk is subject to a claim of mechanic's lien recorded in the County
of Sacramento, State of California, on
March 30,2022
__, whereby Example Lumber Company, Inc. claims a lien on said real property in the
amount of
Ten Thousand & 00/100
DOLLARS
($10,000.00
).
WHEREAS, said Principal desires to record a bond pursuant to the provisions of Section 8424 of the Civil Code.
WITNESS the hand and seal this
29th
day of April
2022
.
By: Attorney-in-Fact
Notary Public
"""


def test_release_bond_at_125_percent():
    reading = read(DocumentKind.RECORDED_LIEN, _bond("Twelve Thousand Five Hundred & 00/100"), ctx("BOND 202205030001.pdf"))
    assert reading.model == "mechanics-lien-release-bond" and reading.complete
    r = reading.record
    assert (r.principal, r.surety, r.obligee) == ("Example Builders LLC", "Example Surety Company", "Example Lumber Company, Inc.")
    assert r.bond_amount == 1250000 and r.lien_amount == 1000000 and r.lien_recorded == date(2022, 3, 30)
    assert r.statute == "CIV 8424" and r.dated == date(2022, 4, 29) and r.document_number == "202205030001"
    assert "bond-covers-claim" in codes(reading.findings, Severity.INFO)
    assert "document-number-from-name" in codes(reading.findings, Severity.CHECK)


def test_release_bond_under_125_percent():
    reading = read(DocumentKind.RECORDED_LIEN, _bond("Twelve Thousand & 00/100"), ctx())
    assert "bond-under-125-percent" in codes(reading.findings, Severity.PROBLEM)


# ---------------------------------------------------------------------------------------------------- letters and brief

SETTLEMENT = """November 15, 2023
PRIVILEGED AND CONFIDENTIAL
MEMBERSHIP COMMUNICATION
Membership
Mystique Community Association
Re:
Mystique Community Association
Notice of Settlement
Dear Member:
In accordance with Civil Code section 6100, we are pleased to report the Association has
reached a negotiated settlement of claims against Watt Communities at Mystique, LLC and WC
Development Services, Inc.; the claims related to Buildings 1, 2, and 4.
1. The Settlement Amount. The total settlement amount is $50,000.00.
2. Limited Release of Claims: The claims included are limited to those construction defects, damages, and issues
identified in the consultant's report. Please note that the Settlement Agreement does not include the following claims:
(a) windows.
The Board will provide more details regarding the extent, nature, and timing of repairs as soon as reasonably practicable.
Username:
example
Password:
example
Very truly yours,
SAMPLE & COUNSEL LLP
"""


def test_settlement_disclosure():
    reading = read(DocumentKind.LEGAL_CORRESPONDENCE, SETTLEMENT, ctx())
    r = reading.record
    assert r.letter_type is LetterType.SETTLEMENT_DISCLOSURE and r.recipient is Recipient.MEMBERSHIP
    assert r.sender == "Sample & Counsel LLP" and r.sender_is_counsel and r.letter_date == date(2023, 11, 15) and r.settlement_amount == 5000000
    assert r.buildings_named == (Building.BLDG_1, Building.BLDG_2, Building.BLDG_4)
    assert r.defects_described and r.other_claims_status and not r.repair_estimate and r.prints_credentials
    assert {"no-repair-estimate", "prints-credentials"} <= codes(reading.findings, Severity.CHECK)
    assert "no-other-claims-status" not in codes(reading.findings)


IDR_OFFER = f"""MYSTIQUE COMMUNITY ASSOCIATION
OFFER TO PARTICIPATE IN DISPUTE RESOLUTION (IDR & ADR)
Subject: OFFER TO PARTICIPATE IN DISPUTE RESOLUTION (IDR & ADR)
Date:
Sep 3, 2026
To: {FAKE_NAME}
Property Address: 3101 Enchanted Walk, Sacramento, CA 95835
Dear Homeowner,
This letter serves as a formal invitation to participate in the Association's dispute resolution programs.
The Board of Directors is initiating this process following its decision on July 7, 2026, to pursue remedies.
Under CC&Rs Section 4.15(k), the Association may act.
We request that you contact the Association in writing within ten (10) days to indicate which process you would like to initiate.
The Board will proceed as outlined in the Notice of Board Decision dated July 14, 2026.
Sincerely,
Board of Directors
Mystique Community Association
EXHIBIT "B"
The Association follows the dispute resolution procedures described in California Civil Code Section 1369.510 et seq.
A member may refuse a request to meet and confer.
"""


def test_dispute_resolution_offer():
    reading = read(DocumentKind.LEGAL_CORRESPONDENCE, IDR_OFFER, ctx())
    r = reading.record
    assert r.letter_type is LetterType.DISPUTE_RESOLUTION_OFFER and r.recipient is Recipient.OWNER and r.names_owner
    assert r.letter_date == date(2026, 9, 3) and r.building is Building.BLDG_2 and r.response_days == 10
    assert r.board_decision == date(2026, 7, 7) and r.decision_notice == date(2026, 7, 14)
    found = reading.findings
    assert {"adr-response-window", "adr-article-not-attached", "cites-former-sections"} <= codes(found, Severity.CHECK)
    assert "decision-notice-days" in codes(found, Severity.INFO)
    no_name(r)


def test_draft_membership_update_without_date():
    letter = "DRAFT\nVIA U.S. MAIL\nMembership\nMystique Community Association\nRE:\nMYSTIQUE COMMUNITY ASSOCIATION\nReminder re: Window Claims\n" \
             "Dear Member:\nPlease recall that our office represents the Association.\nVery truly yours,\nSAMPLE & COUNSEL LLP\n"
    reading = LegalLetterModel().read(letter, ctx())
    assert reading.record.letter_type is LetterType.MEMBERSHIP_UPDATE and reading.record.draft
    assert reading.record.subject == "Reminder re: Window Claims" and reading.missing == ("letter_date",)


BRIEF = """Protected from disclosure by California Evidence Code §§ 1115 et seq. and 1152.
July 2, 2023
CONFIDENTIAL MEDIATION-PRIVILEGED
Example ADR
1 Example Ave.
Re:
Mystique Community Association v. Watt Communities at Mystique, LLC
Mystique Community Association's Brief re: July 7th Mediation
Please allow this to serve as the Association's mediation brief in advance of the July 7, 2023, virtual mediation.
Mystique is a condominium community featuring eight buildings enclosing eighty-one (81) townhouse-style units.
The claims are limited to SB800 violations.
Very truly yours,
SAMPLE & COUNSEL LLP
PRELIMINARY COST OF REPAIR
Date: 1/19/2023
TOTAL COST TO REPAIR
$500,000
"""


def test_mediation_brief():
    reading = read(DocumentKind.LEGAL_BRIEF, BRIEF, ctx())
    r = reading.record
    assert reading.complete and r.brief_date == date(2023, 7, 2) and r.event_date == date(2023, 7, 7)
    assert r.caption == "Mystique Community Association v. Watt Communities at Mystique, LLC" and r.addressed_to == "Example ADR"
    assert (r.units_stated, r.buildings_stated, r.claims_basis, r.cost_of_repair) == (81, 8, "SB800", 50000000)
    assert r.privilege_basis == ("1115",) and "mediation-privileged" in codes(reading.findings, Severity.INFO)
    assert r.author_firm == "Sample & Counsel LLP"
    # A firm the sender directory does not list is not named: the brief reads incomplete, a miss.
    unlisted = read(DocumentKind.LEGAL_BRIEF, BRIEF.replace("SAMPLE & COUNSEL LLP", "ANOTHER FIRM LLP"), ctx())
    assert unlisted.record.author_firm == "" and unlisted.missing == ("author_firm",)


# ---------------------------------------------------------------------------------------------------- escrow, forms, list

def _escrow(completed: str) -> str:
    return f"""General Information
Association Name : Mystique Community Association
Property Address
Street Address 3101 Mesmerizing Walk
Requestor Information
Company Example Escrow, Inc.
Contact
Sam Officer
Seller Information
Name {FAKE_NAME}
Buyer Information
Name
Casey Zephyr
Is Buyer Occupant?
Yes
Veterans Affairs Loan? No
Transaction Information
Order Type
RESALE
Escrow/File Number
XX-00-00000
Estimated Closing Date 07-20-2026
Sales Price
400000
Date Ordered
07-13-2026
Date Paid
07-13-2026
Expected Completion
07-15-2026
Actual Completion
{completed} 04:58
"""


def test_escrow_order_on_time():
    reading = read(DocumentKind.ESCROW_REQUEST, _escrow("07-15-2026"), ctx())
    r = reading.record
    assert reading.complete and r.requester == "Example Escrow, Inc." and r.order_type == "RESALE"
    assert r.ordered == date(2026, 7, 13) and r.completed == date(2026, 7, 15) and r.sales_price == 40000000
    assert r.names_seller and r.names_buyer and r.buyer_occupant is True and r.va_loan is False
    assert "documents-days" in codes(reading.findings, Severity.INFO)
    assert "fee-not-in-text" in codes(reading.findings, Severity.CHECK)
    no_name(r)


def test_escrow_order_late():
    reading = read(DocumentKind.ESCROW_REQUEST, _escrow("07-28-2026"), ctx())
    assert "documents-days" in codes(reading.findings, Severity.PROBLEM)


PETITION = """Mystique Community Association
Petition requesting a special meeting
Purpose of meeting
Petition date
BYLAWS
4.2 - Special Meetings
Special meetings of the Members may be called pursuant to the written request of Members entitled to cast at least five percent (5%)
of the Total Voting Power of the Membership.
5% of total voting power of the membership
●
Class A - 81 members ( 4 member signatures required )
Reverse a Rule Change

Mystique Community Association
Petition requesting a special meeting
Building 2
Address
Member Signature
3101 ENCHANTED WALK # 10
3102 ENCHANTED WALK # 11
Reverse a Rule Change
"""


def test_special_meeting_petition():
    reading = read(DocumentKind.FORM, PETITION, ctx())
    r = reading.record
    assert r.form_type is FormType.SPECIAL_MEETING_PETITION and r.purpose == "Reverse a Rule Change"
    assert r.threshold_percent == 5 and r.signatures_required == 4 and r.units_listed == 2 and r.building_mismatches == 1
    assert {"signature-count", "units-listed", "building-pages"} <= codes(reading.findings, Severity.CHECK)


def test_architectural_application():
    form = "MYSTIQUE COMMUNITY ASSOCIATION\nHOME IMPROVEMENT REQUEST APPLICATION\nNOTE: Plans should be submitted at least thirty (30) " \
           "days before activity begins.\nNAME:\nDATE:\nApplicant signature\n☐Approved ☐ Not Approved\nBoard signature\n"
    reading = read(DocumentKind.FORM, form, ctx())
    assert reading.record.form_type is FormType.ARCHITECTURAL_APPLICATION and reading.record.lead_days == 30
    assert {"no-response-time", "no-reconsideration"} <= codes(reading.findings, Severity.CHECK)


def test_assessor_change_of_address():
    form = """SACRAMENTO COUNTY ASSESSOR
CHANGE OF MAILING ADDRESS
Assessor Parcel Number(s):_2_0_1-_1_17_0_-_0_99_-_00_0_1 ______
Property Owner: (Please Print)
MYSTIQUE COMMUNITY ASSOCIATION
Property Address:
3101 MACON DR
New Mailing Address as of 02/24/2024 (Date)
901 H St Ste 120
Address 1 (or c/o)
PMB 188
Address 2
Property Owner or Agent: (Please Print)
02 / 24 / 2024
board@example.org (000) 000-0000
"""
    reading = read(DocumentKind.FORM, form, ctx())
    r = reading.record
    assert r.form_type is FormType.ASSESSOR_ADDRESS_CHANGE and r.filled and not r.carries_personal_data
    assert r.apns == ("20111700990001",) and r.new_mailing_address == "901 H St Ste 120 PMB 188" and r.effective == date(2024, 2, 24)
    assert codes(reading.findings) == {"mailing-address-current"}


@pytest.mark.parametrize("filled", [True, False])
def test_resident_registration(filled):
    body = "noise ~ scrawl\nPHONE\nEMAIL\n" if filled else "\n".join(["____________________"] * 4)
    form = f"MYSTIQUE COMMUNITY ASSOCIATION\nRESIDENT REGISTRATION FORM\nPlease complete and return within thirty (30) days.\n{body}\n"
    reading = read(DocumentKind.FORM, form, ctx("3101 Enchanted Walk.pdf"))
    assert reading.record.return_days == 30 and reading.record.filled is filled
    assert ("personal-data" in codes(reading.findings)) is filled
    # A filled form's handwritten address did not survive OCR; the file is named for the unit.
    assert reading.record.property_address == ("3101 ENCHANTED WALK" if filled else "")


MEMBERS = """APN_DASH,Property Address,Mailing Address,Email,Grantee,Rented,Date
201-1170-099-0001,3101 ENCHANTED WALK,"1 Example Ct, Town, CA",qz@example.org,"ZEPHYR QUINCY",FALSE,3/27/2012
201-1170-099-0002,3102 ENCHANTED WALK,"2 Example Ct, Town, CA",,"ZEPHYR CASEY",TRUE,1/12/2024
"""


def test_membership_list_counts_only():
    reading = read(DocumentKind.MEMBERSHIP_LIST, MEMBERS, ctx())
    r = reading.record
    assert (r.rows, r.rows_with_email, r.rows_with_mailing_address, r.rows_rented, r.distinct_properties) == (2, 1, 2, 1, 2)
    assert r.has_name and r.has_property_address and r.has_mailing_address and r.has_email and not r.opt_out_column
    assert r.as_of == date(2024, 1, 12) and r.extra_columns == ("APN_DASH", "Rented", "Date")
    assert {"no-opt-out-marker", "property-count"} <= codes(reading.findings, Severity.CHECK)
    plain = json.dumps(to_plain(r))
    for value in ("ZEPHYR", "example.org", "Example Ct", "3101"):
        assert value not in plain


# ---------------------------------------------------------------------------------------------------- inspections

SIGNAL = """Inspection Report
Presented To
Mystique HOA
For
Mystique Community Association -Bldg. 8
5601 Whimsical Ln
Sacramento, CA 95835
Tested By:
Alex Tester
Signal Service
Accepted By:
N A
Completed:
Friday, September 19, 2025
Inspection Information
CUSTOMER INFORMATION
Name:
Mystique HOA
City:
Dallas
BUILDING INFORMATION
Address:
5601 Whimsical Ln
COMPANY INFORMATION
Name:
Signal Service
License:
ACO 0000 and C10 000000
MONITORING COMPANY
Name:
Example Monitoring
TESTING SUMMARY
EQUIPMENT TYPE
TOTAL
TESTED
PASSED
FAILED
Control Unit
1
1 (100%)
1 (100%)
0 (0%)
Alarm Initiated Device
5
3 (60%)
2 (40%)
1 (20%)
Fire Alarm System - NFPA 72 (2013)
Outstanding Deficiencies
Location
Device
Type/Make/Model
Barcode Test Date Inspector
Comment
Photo
Status
1 Riser
waterflow / 4
Water Flow / Potter /
VSR
Sep 19,
2025
Alex
Tester
bell sounded late. not
in compliance
 Open
Resolved Deficiencies
Location
Bldg #8 unit 5601 / 2
Type/Make/Model
Smoke Detector
Result
Not Tested
"""


def test_signal_service_fire_alarm_report():
    reading = read(DocumentKind.INSPECTION_REPORT, SIGNAL, ctx())
    assert reading.model == "signal-service-fire-alarm" and reading.complete
    r = reading.record
    assert r.inspection_date == date(2025, 9, 19) and r.building is Building.BLDG_8 and r.site_address == "5601 WHIMSICAL LN"
    assert r.standard == "NFPA 72 (2013)" and r.inspector_license == "ACO 0000 and C10 000000" and r.monitoring_company == "Example Monitoring"
    assert (r.devices_total, r.devices_tested, r.devices_passed, r.devices_failed, r.devices_not_tested) == (6, 4, 3, 1, 1)
    (d,) = r.deficiencies
    assert d.status == "Open" and d.device.startswith("Water Flow") and "bell sounded late" in d.comment
    assert r.result is Result.FAILED
    found = reading.findings
    assert "open-deficiency" in codes(found, Severity.PROBLEM)
    assert {"not-tested", "not-accepted", "customer-record"} <= codes(found, Severity.CHECK)
    assert "no-cadence" in codes(found, Severity.INFO)


def test_signal_report_reads_a_completed_date_the_text_layer_wraps_before_the_year():
    wrapped = SIGNAL.replace("Completed:\nFriday, September 19, 2025\n", "Completed:\nFriday, September 19, \n2025\n.\n01\n")
    assert wrapped != SIGNAL
    reading = read(DocumentKind.INSPECTION_REPORT, wrapped, ctx())
    assert reading.model == "signal-service-fire-alarm" and "inspection_date" not in reading.missing
    assert reading.record.inspection_date == date(2025, 9, 19)


def test_signal_report_without_a_monitoring_block_names_the_supervising_station():
    text = SIGNAL.replace("MONITORING COMPANY\nName:\nExample Monitoring\n", "") + (
        "Supervising Station Monitoring\nSpecification\nType/Make/Model\nExample Watch\n. \n04\n")
    assert read(DocumentKind.INSPECTION_REPORT, text, ctx()).record.monitoring_company == "Example Watch"


def test_general_backflow_report_uses_the_spec_cadence():
    report = "Backflow Prevention Assembly Test Report\nExample Backflow Services\nContractor's Lic# 123456\nTest Date: 06/20/2025\n" \
             "Site: 3101 Macon Dr\nAssembly 1: Passed\n"
    reading = read(DocumentKind.INSPECTION_REPORT, report, ctx())
    r = reading.record
    assert reading.model == "inspection-report" and r.system.value == "backflow assembly"
    assert r.inspection_date == date(2025, 6, 20) and r.building is Building.BLDG_1 and r.result is Result.PASSED
    due = [f for f in reading.findings if f.code == "next-due"]
    assert due and due[0].severity is Severity.PROBLEM and "2026-06-20" in due[0].message


def test_balcony_report_is_left_to_the_sb326_model():
    report = "EXTERIOR ELEVATED ELEMENTS INSPECTION REPORT\nSB 326 balcony and deck inspection\nInspection Date: 11/08/2023\n"
    assert SignalServiceReportModel().parse(report, ctx()) is None
    assert InspectionReportModel().parse(report, ctx()) is None
    reading = read(DocumentKind.INSPECTION_REPORT, report, ctx())
    assert reading is not None and reading.model == "sb326-report"


def test_models_miss_other_texts():
    other = "Minutes of the board meeting\nCall to order at 6:00 pm\n"
    for model in (PreLienNoticeModel(), OwnerStatementModel(), OwnerHistoryModel(), AssessmentLienModel(), MechanicsLienModel(),
                  LienReleaseBondModel(), LegalBriefModel(), EscrowRequestModel(), MembershipListModel(), SignalServiceReportModel(),
                  InspectionReportModel(), FormModel()):
        assert model.parse(other, ctx()) is None, model.name
