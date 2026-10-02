"""The rules and corporate models' statute checks: the hearing procedure (CIV 5855), the collection terms (5650-5685), the fee
schedule, what a missing adoption date says, the leads from other library files, and the bylaws' rule-change and voting
provisions. Synthetic excerpts, made-up names and numbers."""

from __future__ import annotations

from datetime import date

import pytest

from jason.community.document_models import ModelContext, Severity, read
from jason.community.models import governing_rules
from jason.community.models.governing_rules import FineRow, collection_findings, collection_terms, fee_findings, hearing_findings, hearing_terms
from jason.community.models.governing_shared import number_word
from jason.community.symbols import DocumentKind

TODAY = date(2026, 9, 29)


class StubCommunity:
    corporate_name = "SAMPLEVILLE COMMUNITY ASSOCIATION"


def ctx(name="", data_dir=None):
    return ModelContext(StubCommunity(), data_dir, TODAY, name, "")


def codes(reading_or_findings):
    findings = getattr(reading_or_findings, "findings", reading_or_findings)
    return {f.code: f for f in findings}


def test_number_words():
    assert (number_word("ten"), number_word("fifteen (15)"), number_word("30"), number_word("many")) == (10, 15, 30, None)


HEARING = """b. Due Process Requirements
2. The Board must mail a Notice of Board Hearing to the homeowner at least ten days before thehearing, stating the time, date and
place of the hearing, and that the homeowner has the right to attend and may address the Board.
4. Within fifteen days after the hearing, the Board shall send written notice to the homeowner of its decision.
"""


def test_hearing_terms_against_5855():
    h = hearing_terms(HEARING)
    assert (h.notice_days, h.decision_days, h.notice_contents) == (10, 15, True)
    found = codes(hearing_findings(h))
    assert found["decision-notice-days"].severity is Severity.PROBLEM and found["decision-notice-days"].authority == "CIV 5855(f)"
    assert {"no-cure-before-hearing", "no-idr-after-hearing", "no-executive-session-on-request"} <= set(found)
    assert "hearing-notice-short" not in found
    short = codes(hearing_findings(hearing_terms(HEARING.replace("at least ten days", "at least five (5) days"))))
    assert short["hearing-notice-short"].authority == "CIV 5855(a)"
    current = HEARING.replace("fifteen days", "fourteen (14) days") + (
        "The member may cure the violation before the hearing. The hearing is held in executive session if the member requests. "
        "If the Board and the member do not agree after the hearing, the member may request internal dispute resolution.")
    assert codes(hearing_findings(hearing_terms(current))) == {}
    assert hearing_terms("The pool closes at dusk.") is None


COLLECTION = """ASSESSMENT COLLECTION POLICY
It shall be effective on the date of adoption.
Any assessment is delinquent if not received 15 days after it becomes due.
Beginning 15 days after the assessment becomes due, the entire unpaid balance shall bear interest at 12 percent.
Payments shall be applied first to principal owed, then to late fees, interest, and collection expenses.
The owner will be notified that a lien will be recorded unless the balance is paid within 30 days after the date of such notice.
Upon the decision of the Board at an open Board meeting, a lien shall be recorded against the owner's unit.
The Association shall record a Release of Lien within 21 days of the payment.
An owner may submit a written request to meet with the Board to discuss a payment plan.
"""


def test_collection_terms_against_article_2():
    c = collection_terms(COLLECTION)
    assert (c.delinquent_days, c.interest_starts_days, c.pre_lien_days, c.release_days) == (15, 15, 30, 21)
    assert c.payments_to_assessments_first and c.lien_decision_open_meeting and c.payment_plan_meeting
    found = codes(collection_findings(c))
    assert set(found) == {"interest-starts-early"} and found["interest-starts-early"].authority == "CIV 5650(b)(3)"
    worse = COLLECTION.replace("within 21 days", "within 45 days").replace("first to principal owed", "first to late fees")
    found = codes(collection_findings(collection_terms(worse.replace("at an open Board meeting", ""))))
    assert {"lien-release-late", "payments-not-to-assessments-first", "lien-decision-not-stated"} <= set(found)
    assert found["lien-release-late"].severity is Severity.PROBLEM


def test_collection_policy_reads_its_terms():
    reading = read(DocumentKind.POLICY, "SAMPLEVILLE COMMUNITY ASSOCIATION\n" + COLLECTION, ctx())
    assert reading.record.collection.interest_starts_days == 15
    assert codes(reading)["interest-starts-early"].severity is Severity.PROBLEM


def test_fee_schedule_lines_the_statute_limits():
    rows = (FineRow("Late Fee", "15% of Regular Assessment"), FineRow("Interest on unpaid assessments", "18%"),
            FineRow("Copies of Records (Civ. 5205)", "$20 per document", 2000, 2000),
            FineRow("Demand & Transfer Fee", "$285", 28500, 28500), FineRow("IDR Fee", "$50", 5000, 5000),
            FineRow("Late Fee", "10% of Regular Assessment"), FineRow("Returned Check Fee", "$25", 2500, 2500))
    found = [f.code for f in fee_findings(rows)]
    assert found == ["late-charge-over-cap", "interest-over-cap", "records-copy-fee", "resale-document-fee", "idr-fee"]


ETHICS = """SAMPLEVILLE COMMUNITY ASSOCIATION
ETHICS POLICY FOR DIRECTORS & COMMITTEE MEMBERS
adopted ______________
Confidential information includes disciplinary actions against members of the Association.
Anyone in violation of this policy may be subject to disciplinary action.
"""


def test_ethics_policy_is_not_a_member_discipline_rule():
    reading = read(DocumentKind.POLICY, ETHICS, ctx())
    assert reading.record.subjects == ()
    found = codes(reading)
    assert "rule-change-procedure" not in found
    assert found["missing-adopted"].message == 'no adoption date is printed in the text: the adoption line is blank ("adopted ____")'


def test_missing_adoption_messages():
    collection = codes(read(DocumentKind.POLICY, "SAMPLEVILLE COMMUNITY ASSOCIATION\n" + COLLECTION, ctx()))["missing-adopted"]
    assert "takes effect \"on the date of adoption\"" in collection.message and collection.authority == "CIV 4360(b)"
    bare = codes(read(DocumentKind.POLICY, "SAMPLEVILLE COMMUNITY ASSOCIATION\nRESERVE FUND POLICY\nThe board invests reserves.\n", ctx()))
    assert bare["missing-adopted"].message.endswith("it carries no adoption line, date, or certificate")
    rules = ("Election Rules\nThese Election Rules shall be effective on the date of adoption.\nI, ______, am the Secretary, and certify that "
             "these Election Rules were duly adopted by the Board and came into effect on the ____ day of ________, 2022.\n")
    election = codes(read(DocumentKind.ELECTION_RULES, rules, ctx()))["missing-adopted"]
    assert election.message.startswith("no adoption date is printed in the text: the secretary's certificate of adoption is blank")
    assert "2022" in election.message


def test_leads_from_other_library_files(monkeypatch):
    files = {
        DocumentKind.OPERATING_RULES: [("Owner's Manual.pdf", "SAMPLEVILLE ASSESSMENT COLLECTION POLICY EFFECTIVE: April 18, 2023")],
        DocumentKind.MINUTES: [("Minutes 1.pdf", "The board approved the budget."), ("Minutes 2.pdf", "Parking was discussed.")],
        DocumentKind.ANNUAL_DISCLOSURE: [("Annual Disclosures 2024.pdf", "... ASSESSMENT COLLECTION POLICY This document sets forth ...")],
    }
    monkeypatch.setattr(governing_rules, "_files", lambda context, *kinds: [f for k in kinds for f in files.get(k, [])])
    reading = read(DocumentKind.POLICY, "SAMPLEVILLE COMMUNITY ASSOCIATION\n" + COLLECTION, ctx())
    found = codes(reading)
    assert "April 18, 2023" in found["effective-date-in-compilation"].message
    assert found["missing-adopted"].message.endswith("none of the library's 2 minutes mentions adopting it")
    assert "Annual Disclosures 2024.pdf" in found["annual-policy-statement"].message


BYLAWS = """BYLAWS OF SAMPLEVILLE COMMUNITY ASSOCIATION
TABLE OF CONTENTS
CERTIFICATE OF ADOPTION ...................................................... 33
5.1 Number. The Board of Directors shall consist of not less than three (3) nor more than five (5) Directors.
5.2 Term. Directors shall serve terms of two (2) years.
4.3 Quorum. Members entitled to cast one-third (1/3) of the Total Voting Power shall constitute a quorum.
7.10 A majority of the number of Directors then in office shall constitute a quorum for the transaction of business.
8.2 Rules. (a) Notice of Proposed Rule Change. The Board shall provide written notice of a proposed Rule Change concerning Section
8.2(i) matters to the Members at least 21 days before adopting the same.
(g) Reversal of Rule Change. The Rule Change adopted by the Board may be reversed by the affirmative vote of a majority of a quorum.
8.5 (b) Suspension of Rights. The Board shall have the power to suspend the voting or other membership rights of a Member during
any period in which such Member shall be in default in the payment of any Assessment.
Inman - 25 - 9-17-07 v3
"""


def test_bylaws_rule_change_voting_and_certificate():
    reading = read(DocumentKind.BYLAWS, BYLAWS, ctx())
    r = reading.record
    assert (r.rule_notice_days, r.certificate_page, r.suspends_voting_for_default) == (21, 33, True)
    assert r.rule_reversal_vote == "the affirmative vote of a majority of a quorum"
    found = codes(reading)
    assert found["rule-notice-short"].severity is Severity.PROBLEM and found["rule-notice-short"].authority == "CIV 4360(a)"
    assert found["vote-suspension-for-default"].authority == "CIV 5105(h)(1)"
    assert "page 33, past page 25" in found["no-adoption-certificate-in-text"].message


def test_articles_statement_of_information():
    articles = ("ARTICLES OF INCORPORATION\nOF\nSAMPLEVILLE COMMUNITY ASSOCIATION\nFILED\nin the office of the Secretary of State\n"
                "of the State of California\nMAY 1 6 2007\nThe name of this corporation is SAMPLEVILLE COMMUNITY ASSOCIATION.\n")
    finding = codes(read(DocumentKind.ARTICLES, articles, ctx()))["statement-of-information"]
    assert finding.authority == "CIV 4280(b), 5405(a)-(c); CORP 8210" and "2007-08-14" in finding.message


@pytest.fixture(autouse=True)
def _no_library(monkeypatch):
    """No test reads the real library unless it patches ``_files`` itself."""
    monkeypatch.setattr(governing_rules, "_library", lambda data_dir: ())
