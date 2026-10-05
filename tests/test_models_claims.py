"""The insurance claim models, on made-up claims in the carriers' layouts.

Every claim number, policy number, amount, date, and address here is made up; the street names are the development's.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from jason.community.document_models import ModelContext, Severity, read
from jason.community.models.insurance_claims import AuthorizationType, LetterType
from jason.community.symbols import DocumentKind as K

TODAY = date(2026, 9, 29)


class FakeCommunity:
    def insurance(self):
        master = SimpleNamespace(kind=SimpleNamespace(name="MASTER"), carrier="Example National Insurance Company (admitted)",
                                 program="Example Program Services", number="EX-1", prior_numbers=("EX-100200", "EX-100100"))
        return SimpleNamespace(policies=(master,))

    def streets(self):
        from jason.community.symbols import Street

        return (Street.ENCHANTED_WALK, Street.WHIMSICAL_LN)

    def name_pattern(self):
        return "mystique"

    def senders(self):
        from jason.community.sources import Policyholder, Sender, SourceKind

        return (Sender("Example Management Group", SourceKind.MANAGER, ("EXAMPLE MANAGEMENT",)),
                Sender("Elm Mutual Insurance", SourceKind.INSURER, ("ELM MUTUAL", "ELM INSURANCE EXCHANGE")),
                Sender("Cedar Home Insurance", SourceKind.INSURER, ("CEDAR HOME",), role="an owner's own insurer on homeowner claims",
                       holder=Policyholder.OTHER),
                Sender("Example Claims Administrators", SourceKind.INSURER, ("EXAMPLE CLAIMS",)),
                Sender("Elm Roofing", SourceKind.VENDOR, ("ELM ROOFING",)))


def ctx(name: str = "") -> ModelContext:
    return ModelContext(community=FakeCommunity(), today=TODAY, name=name)


def codes(reading):
    return {f.code: f for f in reading.findings}


DISCLAIMER = """ZT0000000
Toll Free: (800) 435-7764
Email: myclaim@elmmutual.example
Elm Insurance Exchange
Please include your claim # on any correspondence
National Document Center
January 28, 2025
MYSTIQUE COMMUNITY
RE:
Insured:
MYSTIQUE COMMUNITY
Claim Number:
7000000001-1
Policy Number:
0600000001
Loss Date:
01/21/2025
Location of Loss:
3102 Enchanted Walk, Sacramento, CA
We acknowledge receipt of the above referenced claim.
We have completed our coverage investigation and have determined your policy canceled per your request
effective September 28, 2024.  Therefore, since the policy was not active at the time of this loss, we must
respectfully disclaim coverage for this loss.
"""

SETTLEMENT = """Please include your claim # on any correspondence
May 23, 2023
RE:
Insured:
Mystique Community
Claim Number:
5020000001-1-1
Policy Number:
0600000001
Loss Date:
02/23/2023
Location of Loss:
5701 Whimsical Lane, Sacramento, CA
Subject:
Settlement Notice
Elm Mutual
payment has been made to Lionsbridge Contractor Group who will distribute the funds as the repairs are completed.
Line of Coverage
Building
Replacement Cost
$1,964.01
Actual Cash Value
$1,964.01
Less: Deductible
$900.57
Coverage conditions: we will not pay; the property is not covered under the policy when ...
"""

PRIMACY = """030000001 - 002
Birch Property and Casualty Insurance Company
COVERAGE FOR YOUR CONDOMINIUM CLAIM
March 6, 2023
We've reviewed your condominium association's Master Policy and your Birch Condominium Policy to determine the primary insurer
Policyholder:
An Owner
Claim number:
030000001–002
Date of loss:
February 23, 2023
"""

NO_CONTACT = """Please include your claim # on any correspondence
January 27, 2023
RE:
Insured:
Mystique Community
Claim Number:
5020000002-1-1
Loss Date:
12/27/2022
Location of Loss:
5607-5693 Whimsical Ln, Sacramento, CA
Subject:
Claim Outcome Letter
We've made several attempts to contact you. As of today, we haven't been able to reach you.
we are currently unable to make payment and have closed your file.
Elm Mutual Insurance
"""


def test_a_disclaimer_for_a_canceled_policy_names_the_master_carrier():
    reading = read(K.CLAIM_LETTER, DISCLAIMER, ctx())
    r = reading.record
    assert (r.carrier, r.claim_number, r.policy_number, r.loss_date) == ("Elm Mutual Insurance", "7000000001-1", "0600000001", date(2025, 1, 21))
    assert r.letter_type is LetterType.DENIAL and r.canceled_effective == date(2024, 9, 28) and r.association_is_insured
    finding = codes(reading)["filed-with-a-prior-carrier"]
    assert finding.severity is Severity.PROBLEM and "Example National Insurance Company (admitted) (EX-1)" in finding.message


def test_a_settlement_notice_is_a_settlement_though_it_quotes_policy_exclusions():
    r = read(K.CLAIM_LETTER, SETTLEMENT, ctx()).record
    assert r.letter_type is LetterType.SETTLEMENT and r.claim_number == "5020000001-1-1"
    assert (r.replacement_cost_cents, r.deductible_cents, r.program_contractor) == (196401, 90057, "Lionsbridge Contractor Group")


def test_primacy_and_no_contact_letters():
    primacy = read(K.CLAIM_LETTER, PRIMACY, ctx())
    assert primacy.record.letter_type is LetterType.PRIMACY and not primacy.record.association_is_insured
    assert primacy.record.claim_number == "030000001-002" and "owner-carrier-defers" in codes(primacy)
    # An owner's own carrier is not in the specification: the letter reads, and its carrier is a miss for a person to list.
    assert primacy.record.carrier == "" and primacy.missing == ("carrier",)
    closed = read(K.CLAIM_LETTER, NO_CONTACT, ctx())
    assert closed.record.letter_type is LetterType.CLOSED_NO_CONTACT and "closed-no-contact" in codes(closed)


def test_statement_of_loss_and_check():
    statement = read(K.CLAIM_PAYMENT, "DATE:\n9/4/2026\nStatement of loss\nNet Loss\n18,516.00\n$\nLess Deductible\n(10,000.00)\n$\n"
                                      "Net Claim at RCV\n8,516.00\nLess Depreciation\n(244.08)\n$\nNet Claim at ACV\n8,271.92\n", ctx()).record
    assert (statement.net_loss_cents, statement.deductible_cents, statement.depreciation_cents, statement.net_claim_cents) == \
        (1851600, 1000000, 24408, 827192)
    check = read(K.CLAIM_PAYMENT, "Remittance advice\nAmount\nCheck Number\nIssued Date\n8271.92\n755000\n09-16-2026\nFrom\n"
                                  "Example National Insurance\nMemo\nAZ000001 Mystique\nDATE OF LOSS\n5/29/2026\n", ctx())
    r = check.record
    # The check prints the master carrier without "Company"; its name comes from the specification's insurance record.
    assert (r.carrier, r.claim_number, r.check_number, r.issued, r.amount_cents, r.date_of_loss) == \
        ("Example National Insurance Company (admitted)", "AZ000001", "755000", date(2026, 9, 16), 827192, date(2026, 5, 29))


def test_the_carrier_is_the_specifications_and_one_it_does_not_list_is_a_miss():
    from jason.community.models.insurance_claims import carrier_of

    c = ctx()
    # A policy's carrier in the insurance record comes first, though a listed administrator and the program are named too.
    assert carrier_of("EXAMPLE CLAIMS ADMINISTRATORS for Example National Insurance Company, through Example Program Services", c) \
        == "Example National Insurance Company (admitted)"
    # Then an insurer in the sender directory, by the words the directory gives it; a vendor is not an insurer.
    assert carrier_of("Example Claims Administrators, for Example Program Services", c) == "Example Claims Administrators"
    assert carrier_of("myclaim@elm-mutual.example", c) == "Elm Mutual Insurance" and carrier_of("Elm Roofing", c) == ""
    # Then a policy's program, by its name.
    assert carrier_of("Issued through Example Program Services", c) == "Example Program Services"
    # A carrier the specification lists nowhere, and a specification with no insurance record or directory: a miss.
    assert carrier_of("Birch Property and Casualty Insurance Company", c) == ""
    assert carrier_of("Elm Mutual Insurance", ModelContext(community=SimpleNamespace(), today=TODAY)) == ""
    assert carrier_of("Elm Mutual Insurance", ModelContext(today=TODAY)) == ""


def test_work_authorization_and_certificate():
    auth = read(K.CLAIM_AUTHORIZATION, "WORK AUTHORIZATION\nFOR REPAIRS AND DIRECTION OF PAYMENT\nDATE:\n5/30/2023\nCLAIM#:\n5020000001-1\n"
                                       "DATE OF LOSS:\n02/23/2023\nADDRESS:\n5701 Whimsical Lane Sacramento, CA 95835\nYour Insurance Carrier "
                                       "Elm Mutual submitted a request to CCA Global Partners, Inc. and its affiliate Lionsbridge Contracting Group\n"
                                       "6/5/2023\nDate\n", ctx()).record
    assert auth.form is AuthorizationType.WORK_AUTHORIZATION and auth.claim_number == "5020000001-1"
    assert (auth.date_of_loss, auth.carrier, auth.signed) == (date(2023, 2, 23), "Elm Mutual Insurance", date(2023, 6, 5))
    cos = read(K.CLAIM_AUTHORIZATION, "Certificate of Satisfaction\nThe work is complete.", ctx("Mystique - 231018 - Cert of satisfaction 5020000001-1 - COS.pdf"))
    assert cos.record.form is AuthorizationType.CERTIFICATE_OF_SATISFACTION and cos.record.claim_number == "5020000001-1"


def test_carrier_estimate_and_police_report():
    estimate = read(K.CLAIM_ESTIMATE, "Insured:\nClaim Number: 1000-00-0001\nType of Loss: WATER\nDate of Loss:\n6/4/2026\nEstimate:\n"
                                      "Elm Mutual estimate\nRCV\n$7,040.72\nLess Depreciation\n$407.22\nACV\n$6,633.50\nLess Deductible\n"
                                      "$500.00\nNet Claim\n$6,133.50\n", ctx()).record
    assert (estimate.carrier, estimate.claim_number, estimate.type_of_loss) == ("Elm Mutual Insurance", "1000-00-0001", "WATER")
    assert (estimate.replacement_cost_cents, estimate.deductible_cents, estimate.net_claim_cents) == (704072, 50000, 613350)
    report = read(K.POLICE_REPORT, "Date: 5/29/26\nSubject: Request for Police Report No. 26-000001\nSacramento Police Department\n"
                                   "The incident at 3101 Enchanted Walk\nDriver: A Person\n", ctx("Police Report.pdf")).record
    assert (report.report_number, report.agency, report.occurred, report.location) == \
        ("26-000001", "Sacramento Police Department", date(2026, 5, 29), "3101 Enchanted Walk")
    assert not hasattr(report, "driver"), "a police report's people are not read"


def test_a_loss_run_lists_its_claims():
    text = ("Claim Detail Report by Policy - P&C\nPolicy #:                   900000001\nCompany:                      Example Exchange\n"
            "Valuation Date:             08/19/2024\nDate Range Selection:  01/01/2019 - 08/19/2024\nClaim Number Date of Loss\nClaim Status\n"
            "Claim Type\nLoss Information\nZZ000001\n02/23/2023\nClosed With Pay\nCommercial Property\nCause of Loss Description:\n"
            "Water Damage\nLocation of Loss:\n5701 Whimsical Lane\nLosses Paid:\n$1,063.44\nLoss Details\n")
    reading = read(K.LOSS_RUN, text, ctx())
    r = reading.record
    assert (r.carrier, r.policy, r.valued, r.period, r.paid_cents) == ("Example Exchange", "900000001", date(2024, 8, 19),
                                                                         "01/01/2019 - 08/19/2024", 106344)
    found = codes(reading)
    assert "claim ZZ000001" in found["claim"].message and found["stale-loss-run"].severity is Severity.CHECK


CASE_REPORT = """Prepared For:                    Mystique Community Association
Date:          February 3, 2023
Days Solving Cases - Current and Last Month
Cases Currently Open
Case Number
Subject
Type
 00000001
Notices of Default and Demands for Payment
Board_Committee_Activity
 00000002
Mystique - 3102 Enchanted Walk - Garage Repairs
RFP/Proposals
 00000003
Mystique - 5703 Whimsical - Claim No. 5020000002-1-1, Claim Outcome Letter
Insurance
This chart shows the average
"""


def test_a_manager_case_report_lists_its_open_cases_and_the_work_among_them():
    from jason.community.models.manager_reports import is_work_case, open_cases

    reading = read(K.MANAGER_CASE_REPORT, CASE_REPORT + " Example Management Group", ctx())
    r = reading.record
    assert r.as_of == date(2023, 2, 3) and r.manager == "Example Management Group"
    # A manager the specification does not list is not named: a miss.
    assert read(K.MANAGER_CASE_REPORT, CASE_REPORT + " Another Company", ctx()).record.manager == ""
    assert [c.number for c in r.open_cases] == ["00000001", "00000002", "00000003"]
    assert r.open_cases[1].case_type == "RFP/Proposals"
    assert [c.number for c in r.open_cases if is_work_case(c)] == ["00000002", "00000003"]
    rows = "Cases Currently Open\n00000009     Mystique - 5705 Whimsical - Roof Leak          Work Order\n"
    assert open_cases(rows)[0].subject == "Mystique - 5705 Whimsical - Roof Leak"


def test_case_report_evidence_places_each_case_once():
    from jason.tasks.incidents import case_report_evidence
    from jason.community.base import BuildingRange
    from jason.community.symbols import Building, Parity, Street

    ctx_ = {"buildings": (BuildingRange(Building.BLDG_8, Street.WHIMSICAL_LN, 5701, 5751, Parity.ANY),), "site_words": (), "known": {},
            "parcels": None, "streets": (Street.WHIMSICAL_LN,)}
    rows = case_report_evidence(CASE_REPORT, ref="gmail/x.pdf", channel="email", ctx=ctx_)
    assert [r.sha256 for r in rows] == ["case:00000002", "case:00000003"]
    claim = rows[1]
    assert claim.claim == "5020000002-1-1" and claim.claimed and [p.address for p in claim.where] == ["5703 WHIMSICAL LN"]


# -- whose policy a claim paper is on ----------------------------------------------------------------------------------

OWNER_ESTIMATE = """Insured:
An Owner
Claim Number: 8800-00-0001
Type of Loss: WATER
Date of Loss:
6/4/2026
Estimate:
Cedar Home estimate
RCV
$7,040.72
Less Deductible
$500.00
Net Claim
$6,540.72
"""

OWNER_LETTER = """Subject:
Status of your claim
June 20, 2026
Insured:
An Owner
Claim Number:
9900-00-0002
Policy Number:
HO-7000123
Loss Date:
06/04/2026
"""


def holder(kind, text, name=""):
    return read(kind, text, ctx(name)).record.policyholder


def test_a_paper_on_a_carrier_the_insurance_record_lists_is_the_associations():
    from jason.community.sources import Policyholder

    check = "Remittance advice\nAmount\nCheck Number\nIssued Date\n8271.92\n755000\n09-16-2026\nFrom\nExample National Insurance\nMemo\nAZ000001\n"
    reading = read(K.CLAIM_PAYMENT, check, ctx())
    assert reading.record.policyholder is Policyholder.ASSOCIATION and "owner-carrier-paper" not in codes(reading)
    # The program the record names is the association's too.
    assert holder(K.CLAIM_PAYMENT, "Statement of loss\nNet Loss\n100.00\nExample Program Services\n") is Policyholder.ASSOCIATION
    # The association's own letters keep the findings they had: the insured says so.
    for letter in (DISCLAIMER, SETTLEMENT, NO_CONTACT):
        r = read(K.CLAIM_LETTER, letter, ctx())
        assert r.record.policyholder is Policyholder.ASSOCIATION and "owner-carrier-paper" not in codes(r)


def test_a_policy_number_the_specification_lists_is_the_associations_whatever_the_carrier():
    from jason.community.sources import Policyholder

    text = OWNER_LETTER.replace("HO-7000123", "EX-100200")
    r = read(K.CLAIM_LETTER, text, ctx())
    assert r.record.carrier == "" and r.record.policyholder is Policyholder.ASSOCIATION and "owner-carrier-paper" not in codes(r)


def test_a_carrier_the_directory_says_writes_an_owners_policies_is_other_and_the_paper_carries_the_lead():
    from jason.community.sources import Policyholder

    r = read(K.CLAIM_ESTIMATE, OWNER_ESTIMATE, ctx())
    assert (r.record.carrier, r.record.policyholder) == ("Cedar Home Insurance", Policyholder.OTHER)
    found = codes(r)["owner-carrier-paper"]
    assert found.severity is Severity.CHECK
    # It names whose policy and the association's carriers, and says it is a lead for a person, not a determination.
    assert "Cedar Home Insurance's policy, not the association's" in found.message
    assert "Example National Insurance Company (admitted)" in found.message and "not a determination" in found.message
    # The same on a payment (its own findings stay) and a work authorization.
    paid = read(K.CLAIM_PAYMENT, "Statement of loss\nNet Loss\n100.00\nLess Depreciation\n(10.00)\nCedar Home Insurance\n", ctx())
    assert paid.record.policyholder is Policyholder.OTHER and {"owner-carrier-paper", "depreciation-held-back"} <= set(codes(paid))
    auth = read(K.CLAIM_AUTHORIZATION, "WORK AUTHORIZATION\nCLAIM#:\n8800000001-1\nYour Insurance Carrier Cedar Home submitted a request\n", ctx())
    assert auth.record.policyholder is Policyholder.OTHER and "owner-carrier-paper" in codes(auth) and "authorized" in codes(auth)


def test_a_letter_that_is_not_the_associations_and_prints_a_policy_number_the_specification_lacks_is_other():
    from jason.community.sources import Policyholder

    r = read(K.CLAIM_LETTER, OWNER_LETTER, ctx())
    assert r.record.carrier == "" and not r.record.association_is_insured and r.record.policyholder is Policyholder.OTHER
    assert "this paper is on another insurer's policy, not the association's" in codes(r)["owner-carrier-paper"].message.lower()


def test_a_primacy_letter_is_one_finding_on_another_policy_and_a_carrier_nobody_listed_is_unknown():
    from jason.community.sources import Policyholder

    primacy = read(K.CLAIM_LETTER, PRIMACY, ctx())
    assert primacy.record.policyholder is Policyholder.OTHER, "the letter says it is the owner's carrier deferring to the master policy"
    assert [f.code for f in primacy.findings if f.code.startswith("owner-carrier")] == ["owner-carrier-defers"]
    defers = codes(primacy)["owner-carrier-defers"]
    assert defers.severity is Severity.CHECK and "not a determination" in defers.message and "()" not in defers.message
    cedar = read(K.CLAIM_LETTER, PRIMACY.replace("Birch Property and Casualty Insurance Company", "Cedar Home Insurance"), ctx())
    assert cedar.record.carrier == "Cedar Home Insurance" and "(Cedar Home Insurance)" in codes(cedar)["owner-carrier-defers"].message
    # A directory carrier with no holder stated, and a letter naming no insured and no policy number, are not guessed at.
    assert holder(K.CLAIM_PAYMENT, "Statement of loss\nNet Loss\n100.00\nElm Mutual\n") is Policyholder.UNKNOWN
    unlisted = read(K.CLAIM_LETTER, "Birch Insurance\nClaim Number: 4400-00-0001\nLoss Date:\n01/02/2026\n", ctx())
    assert unlisted.record.carrier == "" and unlisted.record.policyholder is Policyholder.UNKNOWN
    assert not [f for f in unlisted.findings if f.code.startswith("owner-carrier")]


def test_a_claim_paper_on_another_policy_marks_its_evidence():
    from jason.community.incidents import OTHER_POLICY, Stage
    from jason.tasks.incidents import enrich_claim
    from tests.test_incidents import ev

    context = {"community": FakeCommunity()}
    other = enrich_claim(ev(OWNER_ESTIMATE, title="Cedar estimate.pdf"), OWNER_ESTIMATE, context)
    assert other.claim_of == OTHER_POLICY and other.claimed and other.stage is Stage.CLAIM and other.claim == "8800-00-0001"
    mine = ev(SETTLEMENT, title="Settlement.pdf")
    assert enrich_claim(mine, SETTLEMENT, context).claim_of == "", "the association's claim paper is not marked"
