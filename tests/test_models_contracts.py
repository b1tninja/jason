"""The contracts group's document models: insurance policies, evidence of insurance, contracts, proposals, leases, and
settlements. The fixtures are synthetic excerpts in the real layouts; every name, number, and address in them is made up
(the street ranges are the community's buildings, not anyone's home)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.community.base import BuildingRange, Policy
from jason.community.document_models import ModelContext, Severity, read
from jason.community.models import contracts_insurance
from jason.community.models.contracts_agreements import ContractForm, Period
from jason.community.models.contracts_insurance import Coverage, Declaration, InsurancePolicy
from jason.community.models.contracts_signing import Execution, SignMethod, read_signing
from jason.community.sources import Sender, SourceKind
from jason.community.symbols import Building, DocumentKind, Parity, PolicyKind, Street

TODAY = date(2026, 9, 29)


class FakeCommunity:
    name = "Example Community Association"

    def units(self):
        return tuple(str(n) for n in range(81))

    def buildings(self):
        return (BuildingRange(Building.BLDG_1, Street.MACON_DR, 3024, 3044, Parity.EVEN),
                BuildingRange(Building.BLDG_2, Street.ENCHANTED_WALK, 3007, 3039, Parity.ODD))

    def insurance(self):
        return SimpleNamespace(policies=(
            Policy(PolicyKind.MASTER, "XM100-01", date(2026, 9, 28), prior_numbers=("XM100-00",)),
            Policy(PolicyKind.UMBRELLA, "UM200200", date(2026, 9, 28), prior_numbers=("UM100100",)),
            Policy(PolicyKind.FIDELITY, "CR300300", date(2027, 9, 28)),
            Policy(PolicyKind.DIRECTORS_AND_OFFICERS, "DO400-00", date(2026, 9, 28)),
            Policy(PolicyKind.FLOOD, "5019990001", date(2027, 4, 5), building=Building.BLDG_1),
        ))

    def senders(self):
        return (Sender("Example Roofing", SourceKind.VENDOR, ("EXAMPLE ROOFING",)),
                Sender("Sample Security", SourceKind.VENDOR, ("SAMPLE SECURITY",)),
                Sender("Acme Management", SourceKind.MANAGER, ("ACME MANAGEMENT",), role="prior manager"),
                Sender("Gardenia Landscape", SourceKind.VENDOR, ("GARDENIA LANDSCAPE",), role="landscaping"))


def ctx(**kw) -> ModelContext:
    return ModelContext(community=FakeCommunity(), today=TODAY, **kw)


def codes(reading):
    return {f.code: f for f in reading.findings}


# Insurance policies ---------------------------------------------------------------------------------------------------

NFIP = """EXAMPLE INSURANCE AGENCY
Policy Number:
5019990001
RATE CATEGORY —
RATING ENGINE
EXAMPLE COMMUNITY ASSOCIATION
INSURED NAME(S) AND MAILING ADDRESS
3024-3044 MACON DR
REPLACEMENT COST VALUE:
$2,800,000.00
NUMBER OF UNITS:
7 UNITS
COVERAGE
BUILDING:
$874.00
DEDUCTIBLE
CONTENTS:
$1,750,000
N/A
$0.00
$2,000
N/A
CASE NO:
PHILADELPHIA INDEMNITY INSURANCE COMPANY
Policy issued by:
RATING INFORMATION
FEMA DETERMINED
($35.00)
ANNUAL INCREASE CAP DISCOUNT:
$17.00
TOTAL ANNUAL PREMIUM:
RESERVE FUND ASSESSMENT:
MITIGATION DISCOUNT:
PROBATION SURCHARGE:
$110.00
FEDERAL POLICY FEE:
$1,301.00
INCREASED COST OF COMPLIANCE (ICC) PREMIUM:
HFIAA SURCHARGE:
$250.00
Insurer NAIC Number:
RENEWAL FLOOD INSURANCE POLICY DECLARATIONS
NFIP Policy Number:
5019990001
Policy Term:
04/05/2026 12:01 AM - 04/05/2027 12:01 AM
Agent:
Agency Phone:
PAT AGENT
(000) 555-0100
NATIONAL FLOOD INSURANCE PROGRAM
FULL RISK PREMIUM:
$625.00
STATUTORY DISCOUNTS:
($0.00)
DISCOUNTED PREMIUM:
$612.00
$329.00
($13.00)
18058
CURRENT FLOOD ZONE:
A99
Policy Form:
RCBAP
"""

NFIP_REVISED = """This is a Residential Condominium Building Association Policy.
EXAMPLE COMMUNITY ASSOCIATION
INSURED NAME(S) AND MAILING ADDRESS
3007-3039 ENCHANTED WALK
BLDG 2
COVERAGE
$2,500,000
$0
BUILDING
$798.00
DEDUCTIBLE
CONTENTS
$0
$2,500,000
$0
$0.00
$2,000
PHILADELPHIA INDEMNITY INSURANCE COMPANY
REVISED FLOOD INSURANCE POLICY DECLARATIONS
NFIP Policy Number:
5019990009
Policy Term:
02/27/2024 12:01 AM
STANDARD POLICY - RCBAP
02/27/2025 12:01 AM
ANNUAL SUBTOTAL:
$1,424.00
National Flood Insurance Program
"""


def test_nfip_declarations_read_the_term_limits_and_premium_parts():
    reading = read(DocumentKind.INSURANCE_POLICY, NFIP, ctx())
    r = reading.record
    assert reading.model == "nfip-flood-declarations" and reading.complete
    assert (r.policy_number, r.term_start, r.term_end) == ("5019990001", date(2026, 4, 5), date(2027, 4, 5))
    assert (r.limit, r.deductible, r.premium, r.units, r.building) == (175_000_000, 200_000, 130_100, 7, Building.BLDG_1)
    assert r.declaration is Declaration.RENEWAL and r.form == "RCBAP" and r.naic == "18058" and r.agent == "PAT AGENT"
    assert sum(c.amount for c in r.charges) == r.premium
    found = codes(reading)
    assert "premium-parts" not in found and "insured-not-association" not in found
    assert found["summary-items-present"].authority == "CIV 5300(b)(9)"
    # "N/A" beside the building coverage: the policy insures no association contents.
    assert r.contents_limit == 0
    # $1,750,000 for 7 units is the NFIP maximum, so the co-insurance test the page prints is met at 62% of value.
    assert found["coverage-to-value"].authority == "44 CFR 61.6" and "NFIP maximum" in found["coverage-to-value"].message


def test_nfip_coverage_under_the_coinsurance_test_is_a_check():
    text = NFIP.replace("$1,750,000", "$1,500,000")
    reading = read(DocumentKind.INSURANCE_POLICY, text, ctx())
    assert reading.record.limit == 150_000_000 and reading.record.contents_limit == 0
    # The lesser of 80% of $2,800,000 ($2,240,000) and 7 x $250,000 ($1,750,000) is $1,750,000.
    found = codes(reading)
    assert found["coverage-below-coinsurance"].severity is Severity.CHECK and "$1,750,000" in found["coverage-below-coinsurance"].message


def test_nfip_revised_declarations_and_the_policy_sheet():
    reading = read(DocumentKind.INSURANCE_POLICY, NFIP_REVISED, ctx())
    r = reading.record
    assert (r.building, r.term_end, r.limit, r.deductible, r.premium) == (Building.BLDG_2, date(2025, 2, 27), 250_000_000, 200_000, 142_400)
    assert r.contents_limit == 0
    found = codes(reading)
    # The sheet carries no flood policy for building 2 in this fake community, so the ended term is a lead.
    assert found["term-ended"].severity is Severity.CHECK and found["term-ended"].authority == "CIV 5810"


def test_a_lower_limit_than_the_last_term_and_an_overlapping_policy_are_flagged(tmp_path: Path):
    prior = InsurancePolicy(policy_number="5019990001", building=Building.BLDG_1, term_start=date(2025, 4, 5), term_end=date(2026, 4, 5),
                            limit=200_000_000, deductible=100_000, premium=120_000)
    other = InsurancePolicy(policy_number="5019990002", building=Building.BLDG_1, term_start=date(2026, 6, 1), term_end=date(2027, 6, 1))
    contracts_insurance._LIBRARY_CACHE[(str(tmp_path.resolve()), "insurance_policy")] = [({}, prior), ({}, other)]
    try:
        found = codes(read(DocumentKind.INSURANCE_POLICY, NFIP, ctx(data_dir=tmp_path)))
    finally:
        contracts_insurance._LIBRARY_CACHE.clear()
    assert found["limit-reduced"].authority == "CIV 5810" and found["deductible-raised"].severity is Severity.CHECK
    assert "premium-change" in found and "overlapping-flood-policy" in found


def test_an_insured_other_than_the_association_is_a_problem():
    text = NFIP.replace("EXAMPLE COMMUNITY ASSOCIATION\nINSURED NAME", "ACME MANAGEMENT INC\nINSURED NAME")
    found = codes(read(DocumentKind.INSURANCE_POLICY, text, ctx()))
    assert found["insured-not-association"].severity is Severity.PROBLEM


def test_other_declarations_pages_use_the_labels():
    text = """Commercial Package Policy Declarations
Policy Number: XM100-01
Named Insured: Example Community Association
Policy Period: 09/28/2025 to 09/28/2026
Example Mutual Insurance Company
Limit of Insurance: $1,000,000
Deductible: $10,000
Total Annual Premium: $12,345.00
"""
    reading = read(DocumentKind.INSURANCE_POLICY, text, ctx())
    r = reading.record
    assert reading.model == "policy-declarations"
    assert (r.policy_number, r.term_end, r.limit, r.deductible, r.premium) == ("XM100-01", date(2026, 9, 28), 100_000_000, 1_000_000, 1_234_500)
    # The term ended yesterday and the sheet shows no later one.
    assert codes(reading)["term-ended"].authority == "CIV 5810"


# Evidence of insurance ------------------------------------------------------------------------------------------------

ACORD_LABELS = """SHOULD ANY OF THE ABOVE DESCRIBED POLICIES BE CANCELLED BEFORE
INSURER(S) AFFORDING COVERAGE
INSURER B :
INSURER A :
NAIC #
PRODUCER
INSURED
CERTIFICATE NUMBER:
COVERAGES
$
EACH OCCURRENCE
POLICY NUMBER
TYPE OF INSURANCE
DESCRIPTION OF OPERATIONS / LOCATIONS / VEHICLES  (ACORD 101, Additional Remarks Schedule, may be attached if more space is required)
CERTIFICATE OF LIABILITY INSURANCE
DATE (MM/DD/YYYY)
ACORD 25 (2016/03)
CERTIFICATE HOLDER
The ACORD name and logo are registered marks of ACORD
HIRED
AUTOS ONLY
"""

ACORD_25 = ACORD_LABELS + """9/25/2025
Example Insurance Agency
1 Example Plaza
Anytown CA 90000
000-555-0100
proof@example-agency.test
Example National Insurance
11111
EXCOM-01
Sample Federal Insurance
22222
Example Community Association
c/o Board of Directors
100 Example Street
Anytown CA 90000
Sample Crime Insurance
33333
Sample Casualty Company
44444
1234567890
A
X
1,000,000
X
100,000
5,000
1,000,000
2,000,000
X
Y
XM100-01
9/28/2025
9/28/2026
2,000,000
A
1,000,000
X
X
XM100-01
9/28/2025
9/28/2026
B
X
X
1,000,000
UM100100
9/28/2025
9/28/2026
1,000,000
X
1,000
A
C
D
Property
Crime/Fidelity Bond
Directors & Officers
Y
Y
XM100-01
CR300300
DO400-01
9/28/2025
9/28/2025
9/28/2025
9/28/2026
9/28/2026
9/28/2026
$10,000 Deductible
$1,000 Deductible
$1,000 Deductible
$30,000,000
$400,000
$1,000,000
HOA consists of 81 units. Located in Anytown.
Management Company is Additionally Insured on the General Liability, D&O Liability, and Fidelity Bond.
See Attached...
Board of Directors
100 Example Street
Anytown CA 90000

ACORD 101 (2008/01)
ADDITIONAL REMARKS SCHEDULE
AGENCY CUSTOMER ID:
EXCOM-01
Example Insurance Agency
25
CERTIFICATE OF LIABILITY INSURANCE
Coverage Includes:
Computer Fraud & Funds Transfer Fraud
Commercial Flood:
04/05/2026 - 04/05/2027 5019990001 Bldg 1 - $1,750,000 / Ded $2,000
"""


def test_an_acord_25_reads_producer_insurers_rows_and_remarks():
    reading = read(DocumentKind.EVIDENCE_OF_INSURANCE, ACORD_25, ctx())
    r = reading.record
    assert reading.model == "acord-certificate" and reading.complete
    assert (r.issued, r.producer, r.insured, r.certificate_number) == (date(2025, 9, 25), "Example Insurance Agency",
                                                                      "Example Community Association", "1234567890")
    assert [(i.letter, i.naic) for i in r.insurers] == [("A", "11111"), ("B", "22222"), ("C", "33333"), ("D", "44444")]
    kinds = [l.coverage for l in r.lines]
    assert kinds == [Coverage.GENERAL_LIABILITY, Coverage.AUTO, Coverage.UMBRELLA, Coverage.PROPERTY, Coverage.CRIME,
                     Coverage.DIRECTORS_AND_OFFICERS, Coverage.FLOOD]
    gl, _auto, umbrella, prop, crime, dno, flood = r.lines
    assert (gl.limit, gl.aggregate, umbrella.limit, umbrella.deductible) == (100_000_000, 200_000_000, 100_000_000, 100_000)
    assert (prop.limit, prop.deductible, crime.limit, dno.policy_number) == (3_000_000_000, 1_000_000, 40_000_000, "DO400-01")
    assert (flood.building, flood.limit, flood.expiration) == (Building.BLDG_1, 175_000_000, date(2027, 4, 5))
    assert r.holder == "Board of Directors, 100 Example Street, Anytown CA 90000" and r.units == 81


def test_the_certificate_checks_expiry_numbers_and_the_statutes():
    found = codes(read(DocumentKind.EVIDENCE_OF_INSURANCE, ACORD_25, ctx()))
    assert found["lines-expired"].severity is Severity.CHECK          # the master lines ended 9/28/2026
    assert "DO400-01" in found["number-not-on-sheet"].message
    assert "UM100100" in found["prior-number-for-current-term"].message   # the sheet's umbrella number is UM200200 for that term
    assert found["volunteer-immunity-coverage"].severity is Severity.INFO and found["volunteer-immunity-coverage"].authority == "CIV 5800(a)(4)"
    assert found["owner-tort-coverage"].severity is Severity.INFO and found["owner-tort-coverage"].authority == "CIV 5805(b)"
    assert "named" in found["crime-coverage"].message and found["crime-coverage"].authority == "CIV 5806"
    assert found["holder-is-association"].severity is Severity.INFO
    assert "unit-count" not in found


def test_a_certificate_without_naic_numbers_and_with_labeled_limits():
    text = ACORD_LABELS + """09/29/2022
Sample Insurance Agency
2 Sample Road
Anytown, CA  90000
000-555-0101
agent@sample-agency.test
Example Community Association
c/o Example Manager
PO Box 1
Anytown, CA 90000
Sample Truck Insurance Exchange
A
Y
60000-00-00
09/28/2022
09/28/2023
2,000,000
75,000
5,000
2,000,000
4,000,000
2,000,000
A
Directors & Officers Liability
Y
60000-00-00
09/28/2022
09/28/2023
Limit:
$250,000
Deductible:
$1,000
Condominium Association Located at: 1 Example Drive, Anytown.
Example Manager
PO Box 1
Anytown, CA 90000
"""
    reading = read(DocumentKind.EVIDENCE_OF_INSURANCE, text, ctx())
    r = reading.record
    assert [i.name for i in r.insurers] == ["Sample Truck Insurance Exchange"] and r.insurers[0].naic == ""
    assert [(l.coverage, l.limit, l.deductible) for l in r.lines] == [(Coverage.GENERAL_LIABILITY, 200_000_000, None),
                                                                      (Coverage.DIRECTORS_AND_OFFICERS, 25_000_000, 100_000)]
    found = codes(reading)
    assert found["certificate-expired"].severity is Severity.CHECK
    assert found["volunteer-immunity-coverage"].severity is Severity.CHECK and "D&O $250,000" in found["volunteer-immunity-coverage"].message
    assert r.holder == "Example Manager, PO Box 1, Anytown, CA 90000"


def test_an_owners_guide_to_ordering_a_certificate_is_not_a_certificate():
    assert read(DocumentKind.EVIDENCE_OF_INSURANCE, "Obtaining a custom Certificate of Insurance with your Property Address. "
                "Register at the website and order evidence of insurance.", ctx()) is None


# Signing ---------------------------------------------------------------------------------------------------------------

def test_signing_reads_stamps_certificates_and_blank_lines():
    adobe = "By signing below\nPat Example (Feb 8, 2023 08:04 PST)\nPat Example\nPresident\nFeb 8, 2023\nCEO\nFeb 9, 2023\n"
    s = read_signing(adobe)
    assert [(x.name, x.signed, x.title) for x in s.signatures] == [("Pat Example", date(2023, 2, 8), "President"), ("", date(2023, 2, 9), "CEO")]
    assert s.execution(one_side=False) is Execution.EXECUTED
    docusign = """DocuSign Envelope ID: 0AAA1111-2BBB-3CCC-4DDD-5EEE6FFF7000
Certificate Of Completion
Envelope Id: 0AAA11112BBB3CCC4DDD5EEE6FFF7000
Status: Completed
Signer Events
Alex Vendor
alex@vendor.test
President
Sent: 1/13/2022 1:20:55 PM
Signed: 1/13/2022 1:21:15 PM
Sam Board
sam@example.test
Signed: 1/13/2022 5:03:29 PM
In Person Signer Events
Completed
Security Checked
1/13/2022 5:03:31 PM
"""
    s = read_signing(docusign)
    assert s.completed and len(s.envelopes) == 1 and s.envelopes[0].completed_on == date(2022, 1, 13)
    assert [x.name for x in s.signatures] == ["Alex Vendor", "Sam Board"] and s.signatures[0].method is SignMethod.DOCUSIGN
    s = read_signing("Date:               __________________            Signature:       ______________\nBy:________________\n")
    assert s.blank_lines == 2 and s.execution(one_side=True) is Execution.NOT_IN_TEXT


# Contracts -------------------------------------------------------------------------------------------------------------

AGREEMENT = """ SAMPLE SECURITY SERVICES AGREEMENT
 This Service Agreement is entered into as of  February  07, 2023  (the “Effective Date”) by and between  Sample
 Security Services  (“SSS”), a California corporation, and  Example HOA ,  located  at  1 Example Drive (the “Premises”).
 Termination:  This Agreement is terminable at any time by SSS or Client upon thirty (30) days written notice to the other Party.
DocuSign Envelope ID: 0EFCE8BB-CE6F-4D36-BACB-2AFA20424147
 IN  WITNESS  WHEREOF ,  each  of  the  Parties  has  caused  this  Agreement  to  be  executed.
 Date:               __________________            Signature:       _____________________________
Pat Guard (Feb 8, 2023 08:04 PST)
Pat Guard
President
Sam Board (Feb 8, 2023 08:36 PST)
Sam Board
Operations Manager
 Service:
 Unarmed Security Officer Random Patrol  Rounds
 Term (if applicable):
 Yearly with option to cancel  with thirty (30) days written notice
 Regular Rate:
 $30.00 / per patrol
"""


def test_a_two_sided_agreement_with_adobe_sign_stamps():
    reading = read(DocumentKind.CONTRACT, AGREEMENT, ctx())
    r = reading.record
    assert reading.model == "contract" and reading.complete
    assert (r.vendor, r.client, r.form, r.execution) == ("Sample Security", "Example HOA", ContractForm.AGREEMENT, Execution.EXECUTED)
    assert (r.dated, r.signed_on, r.term_months, r.notice_days, r.term_end) == (date(2023, 2, 7), date(2023, 2, 8), 12, 30, date(2024, 2, 8))
    assert r.prices[0].per is Period.VISIT and r.prices[0].amount == 3000
    found = codes(reading)
    assert found["association-record"].authority == "CIV 5200(a)(4), 5210(a)(1)"
    assert "no-signing-certificate" in found and found["term-ended"].severity is Severity.INFO


MANAGEMENT = """MANAGEMENT SERVICE AGREEMENT
1.1 Real Property Covered by this Agreement:
# of residential living units: 92
1.3 Manager as Party to this Agreement:
Name:  Acme Management, Inc.
2.1 Retention of MANAGER.  The Association hereby engages the Manager to manage the Association.  The Association retains
Manager for a term of twelve (12) months commencing on ________________________________. This
Agreement shall automatically renew for a like term at each anniversary of the commencement date.
Notwithstanding the foregoing, Manager is authorized to cause transfers of funds, without regard to dollar
amount, between the Association’s accounts.
5.8 Invoice Payment.  Manager shall not make any single unapproved expenditure nor incur any obligation exceeding
$1,500.00 without prior Board approval.
At 92 Units:  $2,025.00     (up to 20 hours per month)
10.1 Notice of Termination. Either party may terminate with thirty (30) days written notice.
IN WITNESS WHEREOF, the parties hereto agree.
Pat Example (Nov 8, 2022 07:40 PST)
Pat Example
Vice President
Nov 8, 2022
CEO
Nov 8, 2022
"""


def test_a_management_agreement_brings_the_managing_agent_statutes():
    reading = read(DocumentKind.CONTRACT, MANAGEMENT, ctx())
    r = reading.record
    assert (r.vendor, r.vendor_role, r.spending_limit, r.unlimited_transfers, r.units) == ("Acme Management", "prior manager", 150_000, True, (92,))
    assert r.prices[0].label == "base monthly fee" and r.prices[0].amount == 202_500
    found = codes(reading)
    assert found["manager-disclosure"].authority == "CIV 5375"
    assert found["transfers-without-approval"].authority == "CIV 5380(b)(6)(B)"
    assert found["commencement-blank"].severity is Severity.CHECK and "unit-count" in found
    assert "counterparty-ended" in found and "auto-renewal" not in found
    assert r.manager_statement == () and "manager-statement" not in found


def test_a_management_agreement_carrying_the_managing_agents_statement():
    statement = ("11.16 Managing Agent Statement of Information.  The following information is being provided to the Association\n"
                 "pursuant to California Civil Code Section 5375:\nAcme Management, Inc. is a California corporation.  Its Board of "
                 "Directors is as follows:\nPat Example, President\nPat Example holds the following professional designations:\n- "
                 "Certified Community Association Manager (CCAM); Issue Date 2/24/2007\nAcme Management, Inc. holds Class B California "
                 "contractor’s license #123456.\nIssue Date: 6/10/1993\nExpiration Date: 6/30/2023\n")
    text = MANAGEMENT.replace("IN WITNESS WHEREOF", statement + "IN WITNESS WHEREOF")
    reading = read(DocumentKind.CONTRACT, text, ctx())
    r = reading.record
    assert [i.name for i in r.manager_statement] == ["OWNERS", "LICENSES", "CERTIFICATIONS"]
    found = codes(reading)
    assert "manager-disclosure" not in found and found["manager-statement"].severity is Severity.INFO
    assert found["manager-statement-incomplete"].authority == "CIV 5375(d), (e)"
    # A landscape management agreement is not a management agreement.
    landscape = read(DocumentKind.CONTRACT, "MASTER LANDSCAPE MANAGEMENT AGREEMENT\nTHIS AGREEMENT is made between Gardenia Landscape "
                     "and Example Community Association.\nmonthly service price of $2,450.00 per month.\nLic # 1234567\n", ctx())
    assert landscape.record.title == "MASTER LANDSCAPE MANAGEMENT AGREEMENT" and "manager-disclosure" not in codes(landscape)


def test_titles_stay_on_their_line_and_heading_rows_are_not_titles():
    heading = read(DocumentKind.CONTRACT, "ACO 1\nSAMPLE ALARM, INC.\nCOMMERCIAL LEASE INSTALLATION, MONITORING, SERVICE, & INSPECTION\n"
                   "AGREEMENT\nC10 654321\nTotal Monthly Charge: $106.00\n", ctx())
    assert heading.record.title == "COMMERCIAL LEASE INSTALLATION, MONITORING, SERVICE, & INSPECTION AGREEMENT"
    assert heading.record.license == "654321"
    logo = read(DocumentKind.CONTRACT, "EXAMPLE ROOFING\nS\nESTIMATE\nFor:\nExample Community Association\nQuote Total $540.00\n", ctx())
    assert logo.record.title == "ESTIMATE"
    parties = read(DocumentKind.CONTRACT, "INSPECTION AGREEMENT\nCompany\nExample Roofing\nPARTIES TO THE AGREEMENT\nTotal Fee: $1,680.00\n"
                   "This Agreement is entered into between the Company and Client.\n", ctx())
    assert parties.record.title == "INSPECTION AGREEMENT"
    # An inspection is not construction work, so no license number is asked of it.
    assert "license-not-printed" not in codes(parties)
    proposal = read(DocumentKind.CONTRACT, "Proposal\nEXAMPLE PAINTING\nLicense#: 830584\nSUBJECT:  Exterior Painting\n"
                    "1. Exterior repainting 24 units\n$64,800.00\n4. Price per unit to replace Lattice Enclosures\n$1,225.00\n"
                    "By signing below, I agree to have the work described above for the quoted price(s).\n", ctx())
    assert proposal.record.title == "Proposal" and [p.per for p in proposal.record.prices] == [Period.ONE_TIME, Period.UNIT]
    assert proposal.record.total == 6_480_000


def test_a_pest_control_operators_license_has_letters():
    text = "SERVICE AGREEMENT\nSample Pest Control\nLicense #: PR1234\nRecurring Charge:\n$150.00\nCustomer signed on: Wednesday,\n09/13/2023\n"
    assert read(DocumentKind.CONTRACT, text, ctx()).record.license == "PR1234"


ROOF_ESTIMATE = """DocuSign Envelope ID: 7B647C02-461D-4852-A59A-6B0C374B4827
EXAMPLE ROOFING
ESTIMATE
For:
Example Community Association
Date:
07/25/2023
ROOF INFO: Building 1
SUBTOTAL:
$540
THIS PROPOSAL MAY BE WITHDRAWN IF NOT ACCEPTED WITHIN 30 DAYS
ROOF INFO: Building 2
SUBTOTAL:
$1,950
THIS PROPOSAL MAY BE WITHDRAWN IF NOT ACCEPTED WITHIN 30 DAYS
Payment Authorization Form for Roof Repairs
AUTHORIZED AMOUNT:
1 Example Drive
2,600
CLIENT SIGNATURE:
DocuSigned by:
DATE: Nov-21-2023
"""


def test_the_roof_estimate_adds_its_buildings_against_the_authorization():
    reading = read(DocumentKind.CONTRACT, ROOF_ESTIMATE, ctx())
    r = reading.record
    assert reading.model == "nahs-roof-estimate"
    assert [i.amount for i in r.items] == [54_000, 195_000] and (r.total, r.authorized) == (249_000, 260_000)
    assert (r.vendor, r.signed_on, r.execution, r.validity_days) == ("Example Roofing", date(2023, 11, 21), Execution.EXECUTED, 30)
    found = codes(reading)
    assert found["authorized-differs"].severity is Severity.PROBLEM
    assert "accepted-after-validity" in found
    proposal = read(DocumentKind.PROPOSAL, ROOF_ESTIMATE, ctx())
    assert proposal.model == "nahs-roof-estimate" and proposal.record.total == 249_000


def test_an_unsigned_bid_and_a_contract_naming_the_manager_as_client():
    bid = "Landscape\nMaintenance\nBid\nGardenia Landscape\nLic # 1234567\nDESCRIPTION\nTOTAL\nWeekly Clean Up\nMonthly Charge:        $2,500\nEstimate\nDate:09/18/2023\n"
    reading = read(DocumentKind.CONTRACT, bid, ctx())
    assert reading.record.form is ContractForm.ACCEPTED_PROPOSAL and reading.record.scope == "Weekly Clean Up"
    assert codes(reading)["unsigned-in-text"].severity is Severity.CHECK
    master = ("MASTER LANDSCAPE MANAGEMENT AGREEMENT\nTHIS AGREEMENT is made this ____________ day of ___, 2022, by and between Gardenia "
              "Landscape, LLC and\nAcme Management, Northern Branch. (Client).\n2. TERM: The term of this agreement is MONTH to\nMONTH from "
              "the commencement date. Either party may terminate this agreement with 30 days written notice.\n4. You agree to pay us a "
              "monthly service price of $2,450.00 per month.\n")
    reading = read(DocumentKind.CONTRACT, master, ctx())
    found = codes(reading)
    assert reading.record.client == "Acme Management, Northern Branch" and found["client-not-association"].severity is Severity.CHECK
    assert "commencement-blank" in found and reading.record.auto_renews and reading.record.renewal_months == 1


def test_an_attorney_fee_agreement_and_a_vendor_portal_signature():
    fee = ("ATTORNEY FEE AGREEMENT - EXAMPLE\nThis Legal Services Agreement is made between EXAMPLE COMMUNITY ASSOCIATION and Sample "
           "Law LLP.\nAttorneys’ fee shall be twenty-eight percent (28%) of the net recovery obtained.\nDATED: ____________________\n")
    reading = read(DocumentKind.CONTRACT, fee, ctx())
    assert reading.record.prices[0].per is Period.PERCENT and reading.record.prices[0].percent == 28.0
    assert codes(reading)["may-be-privileged"].authority == "CIV 5200(a)(4)"
    portal = ("SERVICE AGREEMENT\nRecurring Charge:\n$150.00\nThis agreement is for an initial period of 12 month(s).\nCustomer signed on: "
              "Wednesday,\n09/13/2023\nAfter the initial term of months, service will continue until 30 day advance notice is received in "
              "writing.\n")
    reading = read(DocumentKind.CONTRACT, portal, ctx())
    r = reading.record
    assert (r.form, r.execution, r.term_months, r.renewal_months, r.notice_days) == (ContractForm.VENDOR_FORM, Execution.EXECUTED, 12, 1, 30)
    assert "month-to-month" in codes(reading)


def test_an_order_form_that_renews_itself():
    text = ("EXHIBIT A\nORDER FORM\nCustomer:\nExample Community Association\nInitial Term:\n24 Months\nRenewal Term:\n24 Months\n"
            "Annual Recurring Subtotal:\n$5,000.00\nContract Total:\n$10,702.00\nThis Agreement will automatically renew for successive "
            "renewal terms unless either Party gives the other Party notice of non-renewal at least thirty (30) days prior to the end.\n"
            "The Parties have executed this Agreement.\nDate:\n\\FSDateSigned2\\\nDate:\n\\FSDateSigned1\\\n"
            "DocuSign Envelope ID: 445C09D6-6CE8-45AE-847C-5F9CBA389783\nPat Vendor\n11/10/2024\nGeneral Counsel\n11/10/2024\nSam Board\n")
    reading = read(DocumentKind.CONTRACT, text, ctx())
    r = reading.record
    assert (r.signed_on, r.term_end, r.current_term_end, r.notice_days) == (date(2024, 11, 10), date(2026, 11, 10), date(2026, 11, 10), 30)
    assert codes(reading)["auto-renewal"].severity is Severity.CHECK   # notice due 2026-10-11, twelve days out


# Proposals -------------------------------------------------------------------------------------------------------------

QUOTE = """QUOTE
Sample Pressure Washing
Customer Details
Example Community Association
Quote Date
5/19/2024
Valid Until
6/19/2024
Description
Qty
Unit price
Total price
Pressure washing of walkways
1
$850.00
$850.00
Sub total
$850.00
Quote Total
$850.00
Customer Acceptance
x
Signature
"""


def test_a_quote_that_lapsed_unaccepted():
    reading = read(DocumentKind.PROPOSAL, QUOTE, ctx())
    r = reading.record
    assert reading.model == "proposal" and reading.complete
    assert (r.proposal_date, r.valid_until, r.total, r.scope) == (date(2024, 5, 19), date(2024, 6, 19), 85_000, "Pressure washing of walkways")
    assert codes(reading)["offer-lapsed"].severity is Severity.INFO


PANDADOC = """WE HEREBY SUBMIT SPECIFICATIONS AND ESTIMATES FOR:
PRICE
CONCRETE REPAIR
SAWCUT, REMOVE AND REPLACE 26 SQ FT CONCRETE IN 3 LOCATIONS FOR THE WALKWAY
$3,250.00
CRACK SEAL
CLEAN AND PREPARE CRACKS TO BE SEALED WITH HOT CRACK SEAL MATERIAL
$2,100.00
Total
$5,350.00
PROPOSAL / CONTRACT
DATE:
PROPOSAL #
ESTIMATOR
2023-10-17
23-0001
Note: This proposal may be withdrawn by us if not
accepted within 10 days.
Signature Certificate
Reference number: ABCDE-FGHIJ
Document completed by all parties on:
20 Oct 2023 20:41:46 UTC
Pat Vendor
Email: pat@vendor.test
Signed:
20 Oct 2023 16:43:26 UTC
Sam Board
Email: sam@example.test
Signed:
20 Oct 2023 20:41:46 UTC
Signed with PandaDoc
"""


def test_an_accepted_pandadoc_proposal_needs_the_board_approval_on_file():
    reading = read(DocumentKind.PROPOSAL, PANDADOC, ctx())
    r = reading.record
    assert [i.description for i in r.items] == ["CONCRETE REPAIR", "CRACK SEAL"] and r.total == 535_000
    assert (r.number, r.proposal_date, r.valid_until, r.accepted_on) == ("23-0001", date(2023, 10, 17), date(2023, 10, 27), date(2023, 10, 20))
    found = codes(reading)
    assert found["accepted"].authority == "CIV 5200(a)(5)" and "items-differ-from-total" not in found


def test_a_jobtread_proposal_whose_payment_schedule_does_not_add_up():
    text = """PROPOSAL
Proposal 1000-1
Issue Date
Expires
PREPARED FOR
Sam Board
Example Community Association
PROPOSAL DETAILS
Example Lane, Anytown, CA 90000, USA
Any additional work will be an additional proposal.
Stucco Repairs
December 16, 2025
June 16, 2026
TOTAL
$9,968.00
PAYMENT SCHEDULE
Name
Amount
Deposit (10%)
$996.80
Final Payment
$8,000.00
This document is an addendum to the Master Contract.
"""
    reading = read(DocumentKind.PROPOSAL, text, ctx())
    r = reading.record
    assert (r.number, r.scope, r.proposal_date, r.valid_until) == ("1000-1", "Stucco Repairs", date(2025, 12, 16), date(2026, 6, 16))
    assert codes(reading)["schedule-differs-from-total"].severity is Severity.PROBLEM


def test_a_repair_proposal_without_a_license_number_or_billing_ahead_of_the_work():
    text = """PROPOSAL
Proposal 1000-2
Issue Date
Expires
PREPARED FOR
Example Community Association
PROPOSAL DETAILS
Example Lane, Anytown, CA 90000, USA
Stucco Repairs
December 16, 2025
December 16, 2026
TOTAL
$10,000.00
PAYMENT SCHEDULE
Name
Amount
Deposit (15%)
$1,500.00
Mobilization Invoice (45%)
$4,500.00
Final Payment
$4,000.00
This document is an addendum to the Master Contract.
"""
    found = codes(read(DocumentKind.PROPOSAL, text, ctx()))
    assert found["license-not-printed"].authority == "BPC 7030.5"
    # The deposit is over the lesser of $1,000 or 10 percent, and mobilization bills ahead of the work.
    assert found["down-payment-over-limit"].authority == "BPC 7159.5(a)(3)" and "$1,000" in found["down-payment-over-limit"].message
    assert found["payment-ahead-of-work"].authority == "BPC 7159.5(a)(5)"
    assert "schedule-differs-from-total" not in found
    licensed = codes(read(DocumentKind.PROPOSAL, text.replace("PREPARED FOR", "CA STATE LICENSE #654321\nPREPARED FOR")
                          .replace("Deposit (15%)\n$1,500.00", "Deposit (10%)\n$1,000.00").replace("$4,000.00", "$4,500.00"), ctx()))
    assert "license-not-printed" not in licensed and "down-payment-over-limit" not in licensed


def test_a_letter_proposal_with_two_prices():
    text = ("April 18, 2023\nExample Community Association\nThank you for contacting Sample Elections regarding the Board Election for "
            "Example (the Association).\nThe total cost is based on a full-service election for 81 ownership\nunits.\n"
            "TOTAL COST if Election by Acclamation:       $895\nTOTAL COST if Ballots Are Required:        $1,132\nPROPOSAL\n")
    reading = read(DocumentKind.PROPOSAL, text, ctx())
    r = reading.record
    assert [o.amount for o in r.options] == [89_500, 113_200] and r.price == 89_500 and r.units == (81,)
    assert "unit-count" not in codes(reading) and "no-acceptance" in codes(reading)


# Leases and settlements --------------------------------------------------------------------------------------------------

LEASE = """RESIDENTIAL LEASE
On 11/16/2025, Sample Homes, Inc. ("Sample"), as agent for Owner, and Resident One and Resident Two ("Resident") agree as follows ("Lease"):
Sample rents to Resident the real property described as: 1 Nowhere Road, Anytown, CA 90000 ("Home").
TERM:
The term begins on 11/28/2025 ("Commencement Date”) and shall terminate on
11/27/2026 at 11:59 PM ("Termination Date").
RENT: Resident agrees to pay $2,400 per month for the term of the Lease.
SECURITY DEPOSIT: Resident agrees to pay $2,400 as a security deposit.
Signed on 11/18/2025 02:36:51 UTC
Signed on 11/18/2025 02:35:22 UTC
Signed on 11/18/2025 02:36:51 UTC
ADDENDUM - WAIVER OF SECURITY DEPOSIT
the requirement of payment of a Security Deposit, as set forth in Paragraph 4 of the Lease, is waived.
monthly rent is adjusted to $2,460.
"""


def test_a_lease_keeps_counts_not_names():
    reading = read(DocumentKind.LEASE, LEASE, ctx())
    r = reading.record
    assert reading.complete and (r.agent, r.residents, r.signers, r.execution) == ("Sample Homes, Inc.", 2, 3, Execution.EXECUTED)
    assert (r.term_start, r.term_end, r.rent, r.adjusted_rent, r.deposit_waived) == (date(2025, 11, 28), date(2026, 11, 27), 240_000, 246_000, True)
    found = codes(reading)
    assert found["premises-not-placed"].severity is Severity.CHECK and "lease-ending" in found and "rent-adjusted" in found
    assert "Resident One" not in str(r)


def test_a_short_lease_meets_the_short_term_rental_rule():
    text = LEASE.replace("shall terminate on\n11/27/2026", "shall terminate on\n12/20/2025")
    assert codes(read(DocumentKind.LEASE, text, ctx()))["short-term-rental"].authority == "CIV 4741(c)"


def test_a_builder_settlement_asks_for_the_member_disclosure():
    text = """SETTLEMENT AGREEMENT AND LIMITED RELEASE
This Settlement Agreement and Limited Release is entered into by and between Claimant
Example Community Association (“Claimant” or “Association”), and Respondents Sample Builders, LLC; and Sample Development, Inc.
(“Respondents”).
1.1 “Dispute” shall mean the pre-litigation dispute resolution proceeding Claimant initiated by serving a Notice to Builder upon
Respondents on October 24, 2022.
3.1 Settlement Payment to Claimant.  Respondents, through their insurer, hereby agree to pay Claimant the sum of $135,000.00. The
Settlement Payment shall be made within thirty (30) days of the Settling Parties’ execution of this Agreement. The Settlement
Payment shall be made payable to the “Sample Law LLP Client Trust Account”.
Waiver of California Civil Code section 1542.
AGREED AND ACCEPTED BY:
Date:
Name:
Title:
EXHIBIT “A”
"""
    reading = read(DocumentKind.SETTLEMENT, text, ctx())
    r = reading.record
    assert reading.complete and [p.role for p in r.parties] == ["claimant", "respondent", "respondent"]
    assert (r.payment, r.payment_due_days, r.dispute_began, r.builder_claim, r.waives_1542) == (13_500_000, 30, date(2022, 10, 24), True, True)
    found = codes(reading)
    assert found["member-disclosure"].authority == "CIV 6100(a)" and found["unsigned-in-text"].severity is Severity.CHECK


@pytest.mark.parametrize("kind", [DocumentKind.INSURANCE_POLICY, DocumentKind.CONTRACT, DocumentKind.PROPOSAL, DocumentKind.LEASE,
                                  DocumentKind.SETTLEMENT, DocumentKind.EVIDENCE_OF_INSURANCE])
def test_a_text_of_another_kind_is_a_miss(kind):
    assert read(kind, "Minutes of the board meeting. The meeting was called to order at 6 pm.", ctx()) is None


def test_a_vision_readings_table_layout_gives_the_authorized_amount_and_the_signature_date():
    from jason.community.models.contracts_agreements import _authorized

    table = "PROPERTY/CLIENT INFORMATION\nPROPERTY ADDRESS: | AUTHORIZED AMOUNT:\n100 Example Dr | 16,275\nCLIENT NAME: | COMPLETION DATE:\n"
    lines = "PROPERTY ADDRESS:\nAUTHORIZED AMOUNT:\n100 Example Dr\n16,275\nCLIENT NAME:\n"
    assert _authorized(table) == _authorized(lines) == 1627500
    before = "CLIENT SIGNATURE: | DATE: Nov-21-2023\nDocuSigned by:\nA Signer\n387EA622F8D34C0\n"
    after = "DocuSigned by:\n;\nDATE: Nov-21-2023\nA Signer\n"
    assert [s.signed for s in read_signing(before).signatures] == [s.signed for s in read_signing(after).signatures] == [date(2023, 11, 21)]
