"""The governing group's document models: synthetic excerpts in the real layouts, with made-up parties and numbers."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from jason.community.document_models import ModelContext, Severity, read
from jason.community.governing import Supersession
from jason.community.models.governing_recorded import Approval
from jason.community.models.governing_rules import ElectionElement, PolicySubject, RuleSubject
from jason.community.reports import PlanBlock, PublicReport
from jason.community.symbols import Building, DocumentKind

TODAY = date(2026, 9, 29)


class StubCommunity:
    """Just the facts the governing checks consult."""

    corporate_name = "SAMPLEVILLE COMMUNITY ASSOCIATION"

    def __init__(self, *, ccrs_number="200001010100", reports=(), supersessions=(), units=(), common_areas=(), blocks=()):
        self.ccrs = SimpleNamespace(recorder_number=ccrs_number, amendments=())
        self._reports, self._supersessions = tuple(reports), tuple(supersessions)
        self._units, self._common, self._blocks = tuple(units), tuple(common_areas), tuple(blocks)

    def public_reports(self):
        return self._reports

    def supersessions(self):
        return self._supersessions

    def units(self):
        return self._units

    def common_areas(self):
        return self._common

    def unit_blocks(self):
        return self._blocks


def ctx(community=None, name=""):
    return ModelContext(community or StubCommunity(), None, TODAY, name, "")


def codes(reading):
    return {f.code: f for f in reading.findings}


# The declaration: a title company's certified copy of a restated declaration.

DECLARATION = """RECORDING REQUESTED BY, AND
WHEN RECORDED, MAIL TO:
EXAMPLE LAW LLP
Certified to be a true and correct
copy of original document recorded
in Book ~~ page ~~
of Official Records.
RESTATED DECLARATION
OF
COVENANTS, CONDITIONS AND RESTRICTIONS
FOR
SAMPLEVILLE
Page Number
DEFINITIONS .................................................. 2
AMENDMENT ................................................. 47
- 1 - 9-10-07
RECITALS
A. Declarant is the owner of certain real property, which is more particularly described in attached Exhibit "A" ("Phase I").
E. Phase I consists of 12 Condominium Units with individual garages located within 1 building. Upon the annexation of all of
the Subsequent Phase Property, the Development shall consist of 92 Condominium Units located within 8 buildings.
F. Declarant previously Recorded the Declaration of Covenants, Conditions and Restrictions for Sampleville on September 12,
2007, in Book 20070912, at Page 758, Official Records of Sacramento County (the "Prior Declaration"). Declarant hereby rescinds
and revokes the Prior Declaration. These covenants create a "condominium project" as that term is defined in California Civil
Code section 1351(f), and shall constitute enforceable equitable servitudes as provided in California Civil Code Section 1354.
1.6 Association. "Association" shall mean Sampleville Community Association, a nonprofit mutual benefit corporation.
1.15 Declarant. "Declarant" means Example Homes, LLC, a Delaware limited liability company, and its successors.
4.15 Rental of Condominiums. (a) Not more than twenty percent (20%) of the Units within the Development shall, at any
particular time, be leased or occupied by anyone other than an Owner.
- 24 - 9-10-07
"""


def test_declaration_reads_the_restatement_and_its_prior_declaration():
    reading = read(DocumentKind.DECLARATION, DECLARATION, ctx(StubCommunity(ccrs_number="200709120758")))
    r = reading.record
    assert r.title == "RESTATED DECLARATION OF COVENANTS, CONDITIONS AND RESTRICTIONS FOR SAMPLEVILLE"
    assert r.restated and r.project == "SAMPLEVILLE"
    assert r.declarant == "Example Homes, LLC, a Delaware limited liability company"
    assert (r.phase_one_units, r.total_units, r.buildings) == (12, 92, 8)
    assert r.prior_declaration == "200709120758" and r.prior_declaration_recorded == date(2007, 9, 12)
    assert r.rental_cap_percent == 20
    assert r.recording.certified_copy and not r.number
    assert (r.toc_last_page, r.last_page_seen) == (47, 24)
    found = codes(reading)
    assert found["spec-pins-rescinded-declaration"].severity is Severity.CHECK
    assert found["rental-cap-below-floor"].authority.startswith("CIV 4741(b)")
    assert found["cites-repealed-sections"].authority == "CIV 4235(a)"
    assert "partial-text" in found and "certified-copy" in found
    assert not any(code.startswith("no-") for code in found)  # the 4250(a) contents are all there
    assert set(reading.missing) == {"number", "recorded"}


# Amendments: the declarant's recorded amendment, and the board's unrecorded draft.

DECLARANT_AMENDMENT = """Sacramento County
Example Clerk, Clerk/Recorder
RECORDING REQUESTED BY: Doc# 202001170712 Fees $101.00
1/17/2020 10:55:20 AM Taxes $0.00
Titles 1 Pages 3
AND WHEN RECORDED, MAIL TO:
EXAMPLE LAW LLP
FIRST AMENDMENT TO RESTATED DECLARATION OF COVENANTS,
CONDITIONS AND RESTRICTIONS
FOR
SAMPLEVILLE
If this document contains any restriction based on race, color, religion, that restriction violates state and federal law.
This First Amendment to Restated Declaration of Covenants, Conditions and Restrictions for Sampleville (the "Amendment") is
made by Example Homes LLC, a California limited liability company ("Declarant").
RECITALS
A. That certain Restated Declaration of Covenants, Conditions and Restrictions for Sampleville was Recorded on September 20,
2007, in Book 20070920 at Page 0938, in the Official Records of Sacramento County, California, ("Declaration").
D. Subsection 15.2(d) of the Declaration permits the Declarant to amend the Declaration as set forth below.
NOW, THEREFORE, the Declaration shall be amended as follows:
1. Amendment. Section 4.15 of the Declaration is amended to add the following subsection:
3. Effective Date. This Amendment shall be effective upon its Recording in the Official Records of Sacramento County.
IN WITNESS WHEREOF, the undersigned, Declarant has executed this Amendment.
STATE OF CALIFORNIA ) On , 2020, before me, a Notary Public, personally appeared the signer.
"""

BOARD_AMENDMENT = """RECORDING REQUESTED BY:
AND WHEN RECORDED MAIL TO:
SAMPLEVILLE COMMUNITY ASSOCIATION
(SPACE ABOVE THIS LINE FOR RECORDER'S USE)
SECOND AMENDMENT TO RESTATED DECLARATION OF COVENANTS, CONDITIONS AND RESTRICTIONS FOR SAMPLEVILLE
NOTICE
If this document contains any restriction based on race, that restriction violates state and federal fair housing laws.
This SECOND AMENDMENT (hereinafter the "Second Amendment") is made on the date set forth at the end of this document by
SAMPLEVILLE COMMUNITY ASSOCIATION (referred to in this document as the "Association").
WHEREAS, this Second Amendment is made with respect to that certain RESTATED DECLARATION OF COVENANTS, CONDITIONS AND
RESTRICTIONS FOR SAMPLEVILLE, recorded on September 20, 2007, as Document No. 200709200938, in the Official Records;
WHEREAS, the 2007 Declaration was amended by that First Amendment to the Restated Declaration, recorded on January 17, 2020
as Document No. 202001170712, in the Official Records (the "First Amendment");
WHEREAS, pursuant to Civil Code section 4741, the Declaration must be amended to remove any conflicts with the law. Under
Civil Code section 4741(f), the Board has the authority without Member approval to amend the Declaration;
NOW, THEREFORE, the Association hereby declares that Article 4, Sections 4.15 of the 2007 Declaration is hereby amended and
restated as follows:
1. Article 4, Section 4.15 ("Rental of Condominiums"), subsection (a) ("Restrictions on Number of Units Leased") is hereby
amended and restated as follows: Not more than twenty-five percent (25%) of the Units shall be leased.
IN WITNESS WHEREOF, we, the Board of Directors of the Association, do hereby affirm, approve, and adopt this FIRST AMENDMENT TO
THE RESTATED DECLARATION, which shall be recorded.
DATED: ______________, 2023 SAMPLEVILLE COMMUNITY ASSOCIATION
By: President
By: Secretary
"""


def test_declarant_amendment_is_recorded_and_complete():
    reading = read(DocumentKind.AMENDMENT, DECLARANT_AMENDMENT, ctx(StubCommunity(ccrs_number="200709200938"),
                                                                     "CCRs - 1st Amendment.pdf"))
    r = reading.record
    assert reading.complete, reading.missing
    assert (r.number, r.recorded, r.recording.fees_cents) == ("202001170712", date(2020, 1, 17), 10_100)
    assert r.ordinal == 1 and r.approval is Approval.DECLARANT and "15.2(d)" in r.authorities
    assert r.declaration_number == "200709200938"
    assert r.sections == ("4.15",) and r.effective_on_recording
    assert r.execution.witness_clause and r.execution.acknowledged
    found = codes(reading)
    assert "amends-unpinned-declaration" not in found
    assert found["amendment-not-pinned"].severity is Severity.INFO


def test_board_rental_amendment_draft_findings():
    reading = read(DocumentKind.AMENDMENT, BOARD_AMENDMENT, ctx())
    r = reading.record
    assert r.recording.unrecorded_copy and not r.number
    assert r.ordinal == 2 and r.witness_ordinal == 1 and r.draft_year == 2023
    assert r.approval is Approval.BOARD_RENTAL and "CIV 4741(f)" in r.authorities
    assert r.maker == "SAMPLEVILLE COMMUNITY ASSOCIATION"
    assert r.declaration_number == "200709200938" and r.prior_amendments == ("202001170712",)
    assert r.sections == ("4.15",) and r.subsections == ("4.15(a)",)
    found = codes(reading)
    assert found["ordinal-mismatch"].severity is Severity.PROBLEM
    assert found["unrecorded-copy"].authority == "CIV 4270(a)(3)"
    assert found["unsigned-draft"].severity is Severity.CHECK
    assert found["after-rental-amendment-deadline"].authority == "CIV 4741(f)"
    assert "rental-amendment-notice" in found
    assert found["amends-unpinned-declaration"].severity is Severity.CHECK  # the stub pins another number


# Annexations: an old BOOK/PAGE stamp, and an electronic stamp whose digits OCR split.

OLD_ANNEXATION = """Sacramento County Recording
Example Clerk, Clerk/Recorder
RECORDING REQUESTED BY, AND BOOK 20071217 PAGE 1310
WHEN RECORDED, MAIL TO:
Monday, DEC 17, 2007 2:29:26 PM
Ttl Pd $18.00 Nbr-0005194964
DECLARATION OF ANNEXATION
AND
RESERVATION OF EASEMENTS
FOR
SAMPLEVILLE, PHASE 2
TJH/12/1-4
This Declaration of Annexation and Reservation of Easements for Sampleville, Phase 2 is made by Example Homes, LLC, a
Delaware limited liability company ("Declarant") in reference to the following facts:
RECITALS
A. Association Common Area designated A.C.A. 3, Condominium Common Area designated C.C.A. 3, Units 21 through 32 inclusive,
together with all Exclusive Use Common Areas, as depicted, described and defined in the Condominium Plan recorded September 12,
2007 in Book 20070912, page 757 of Official Records, being a portion of Lot 1 as shown on the Final Map, filed on August 14,
2006 in Book 194 of Parcel Maps, at page 18.
B. Declarant executed that certain Restated Declaration of Covenants, Conditions and Restrictions for Sampleville, which was
Recorded on September 20, 2007, in Book Number 20070920 at Page Number 0938, in the Official Records.
IN WITNESS WHEREOF, the undersigned, Declarant has executed this Declaration of Annexation.
STATE OF CALIFORNIA ) On 2007, before me, a Notary Public, personally appeared the signer.
"""

SPLIT_ANNEXATION = """RECORDING REQUESTED BY Sacramento County - i
EXAMPLE TITLE COMPANY Example Clerk, Clerk/Recorder |
RECORDING REQUESTED BY: Doc # 201 91 2201433 Fees $208.00 |
12/20/2019 3:07:40 PM Taxes $0.00 |
Titles 2 Paid $208.00 !
Pages 7 |
AMENDED AND RESTATED :
DECLARATION OF ANNEXATION i
AND |
RESERVATION OF EASEMENTS
FOR
SAMPLEVILLE, PHASE 6 :
If this document contains any restriction based on race, that restriction is void.
This Amended and Restated Declaration is made by Example Communities LLC, a California limited liability company
("Declarant") in reference to the following facts:
Association Common Area designated A.C.A. 5, Condominium Common Area designated C.C.A. 5, Units 28 through 3 7, inclusive.
D. This instrument replaced and rescinded the previous Declaration of Annexation and Reservation of Easements for Sampleville,
Phase 6, recorded on January 16, 2019, as Document No. 201901161003, in the Official Records.
IN WITNESS WHEREOF the undersigned has executed this instrument.
A notary public or other officer completing this certificate. On 2019, before me, a Notary Public, personally :
appeared the signer, who proved to me on the basis of satisfactory evidence.
"""


def test_old_annexation_stamp_units_and_citations():
    report = PublicReport("999002SA", Building.BLDG_3, 2, 12, date(2008, 2, 29), "Example Homes", annexation=date(2007, 12, 17))
    reading = read(DocumentKind.ANNEXATION, OLD_ANNEXATION, ctx(StubCommunity(ccrs_number="200709200938", reports=(report,)),
                                                                 "Annexation - Phase 2.pdf"))
    r = reading.record
    assert reading.complete, reading.missing
    assert r.title == "DECLARATION OF ANNEXATION AND RESERVATION OF EASEMENTS FOR SAMPLEVILLE, PHASE 2"
    assert (r.phase, r.number, r.recorded) == (2, "200712171310", date(2007, 12, 17))
    assert (r.first_unit, r.last_unit, r.units) == (21, 32, 12)
    assert r.association_common_areas == (3,) and r.condominium_common_areas == (3,)
    assert r.declaration_number == "200709200938" and r.plan_number == "200709120757"
    assert r.map_reference == "Book 194 of Parcel Maps, page 18"
    assert r.execution.acknowledged
    assert reading.findings == ()  # agrees with the stub's phase table and CC&Rs number


def test_split_stamp_and_unit_range_are_joined_and_checked():
    report = PublicReport("999006SA", Building.BLDG_5, 6, 10, date(2021, 11, 30), "Example Communities", annexation=date(2020, 7, 17))
    community = StubCommunity(ccrs_number="200709200938", reports=(report,))
    reading = read(DocumentKind.ANNEXATION, SPLIT_ANNEXATION, ctx(community, "Annexation - Phase 6.pdf"))
    r = reading.record
    assert r.title == "AMENDED AND RESTATED DECLARATION OF ANNEXATION AND RESERVATION OF EASEMENTS FOR SAMPLEVILLE, PHASE 6"
    assert r.amended_restated and r.phase == 6
    assert (r.number, r.recorded, r.recording.source) == ("201912201433", date(2019, 12, 20), "spaced")
    assert (r.first_unit, r.last_unit, r.units) == (28, 37, 10)
    assert r.rescinds == ("201901161003",)
    found = codes(reading)
    assert "name-omits-amended" in found
    assert found["annexation-date-differs"].severity is Severity.CHECK
    assert "supersession-not-pinned" in found
    pinned = StubCommunity(ccrs_number="200709200938", reports=(report,),
                           supersessions=(Supersession("201901161003", "201912201433", phase=6),))
    assert "supersession-not-pinned" not in codes(read(DocumentKind.ANNEXATION, SPLIT_ANNEXATION, ctx(pinned, "x AMENDED.pdf")))


# Bylaws and articles.

BYLAWS = """BYLAWS
OF
SAMPLEVILLE
COMMUNITY ASSOCIATION
TABLE OF CONTENTS
CERTIFICATE OF ADOPTION ...................................................... 33
ARTICLE 1 NAME AND PURPOSE
1.2 Corporate Status. The Association is an "Association" as defined by California Civil Code Section 1351(a).
ARTICLE 4 MEETINGS OF MEMBERS
4.1 Annual Meeting. The first annual meeting of the Members shall be held within 45 days.
4.6 Quorum. (a) Percent of Members Required. The presence at any meeting, in person or by proxy, of Members entitled to cast
at least one-third (1/3) of the Total Voting Power shall constitute a quorum for the transaction of any business.
ARTICLE 5 BOARD OF DIRECTORS
5.1 Number of Directors. The initial Board of Directors shall be comprised of three (3) persons designated by Declarant.
Thereafter, the Board of Directors shall consist of not less than three (3) nor more than five (5) Directors.
5.3 Election of Board of Directors. (a) Staggered Terms of Office. At each annual meeting, the Members shall elect, in
alternating years, three (3) and two (2) Directors, with such Directors serving for terms of two (2) years each.
6.1 Nomination. Elections shall be by secret ballot under the supervision of the inspectors of elections.
7.10 Quorum. A majority of the number of Directors then in office, but not less than two Directors, shall constitute a quorum.
- 25 - 9-17-07 v3
"""

ARTICLES = """ARTICLES OF INCORPORATION
OF
SAMPLEVILLE COMMUNITY ASSOCIATION
FILED
in the office of the Secretary of State
of the State of California
MAY 1 6 2007
I
The name of this corporation is SAMPLEVILLE COMMUNITY ASSOCIATION.
II
This corporation is a nonprofit mutual benefit corporation organized under the Nonprofit Mutual Benefit Corporation Law. It
will enforce the Declaration of Covenants, Conditions and Restrictions for Sampleville.
III
The name and address in this state of the corporation's initial agent for service of process are Example Agent, 1 Example
Road, Sampleton, California 95000.
IV
This corporation is an association formed to manage a common interest development under the Davis-Stirling Common Interest
Development Act. The association has no business or corporate office. The front street and the nearest cross street of the
Development are First Street and Second Avenue. There is no managing agent for the corporation at the time of filing.
Date: May 15, 2007
"""


def test_bylaws_board_terms_quorums_and_partial_text():
    reading = read(DocumentKind.BYLAWS, BYLAWS, ctx())
    r = reading.record
    assert reading.complete, reading.missing
    assert r.title == "BYLAWS OF SAMPLEVILLE COMMUNITY ASSOCIATION" and r.version == "9-17-07 v3"
    assert (r.directors_initial, r.directors_min, r.directors_max, r.term_years) == (3, 3, 5, 2)
    assert r.staggered_terms and r.secret_ballot and r.inspectors_of_election
    assert r.member_quorum == "one-third (1/3)"
    assert r.board_quorum.startswith("A majority of the number of Directors then in office")
    found = codes(reading)
    assert {"no-adoption-certificate-in-text", "partial-text", "cites-repealed-sections"} <= set(found)
    assert "term-exceeds-election-cycle" not in found
    long_terms = read(DocumentKind.BYLAWS, BYLAWS.replace("terms of two (2) years", "terms of five (5) years"), ctx())
    assert codes(long_terms)["term-exceeds-election-cycle"].severity is Severity.PROBLEM


def test_bylaws_adoption_date_comes_from_the_certificate_not_the_contents():
    certificate = ("\nCERTIFICATE OF ADOPTION ........ 33\n" + BYLAWS + "\nCERTIFICATE OF ADOPTION\nThe undersigned, Incorporator of the "
                   "corporation, hereby certifies that the above and foregoing Bylaws were duly adopted by action of the Incorporator on "
                   "September 17, 2007, and that these Bylaws now constitute the Bylaws of the Association.\nDated: October 1, 2007\n")
    r = read(DocumentKind.BYLAWS, certificate, ctx()).record
    assert r.certificate_of_adoption and r.adopted == date(2007, 9, 17)


def test_articles_carry_the_4280_statement():
    reading = read(DocumentKind.ARTICLES, ARTICLES, ctx())
    r = reading.record
    assert reading.complete, reading.missing
    assert r.name == "SAMPLEVILLE COMMUNITY ASSOCIATION" and r.corporation_type == "nonprofit mutual benefit corporation"
    assert (r.filed, r.signed) == (date(2007, 5, 16), date(2007, 5, 15))
    assert r.agent_for_service == "Example Agent"
    assert (r.front_street, r.cross_street) == ("First Street", "Second Avenue")
    assert r.davis_stirling_statement and r.managing_agent_statement
    assert set(codes(reading)) == {"statement-of-information"}
    bare = ARTICLES.replace("formed to manage a common interest development under the Davis-Stirling", "formed under the")
    finding = codes(read(DocumentKind.ARTICLES, bare, ctx()))["no-davis-stirling-statement"]
    assert finding.severity is Severity.CHECK and finding.authority.startswith("CIV 4280(a)(1)")


# Operating rules, policies, and election rules.

RULES = """SAMPLEVILLE
COMMUNITY
ASSOCIATION
OWNER'S
MANUAL
&
RULES
WHAT ARE THE RULES? Members are given at least 28 day notice of any proposed rule change.
RulesEFFECTIVE: SEPTEMBER 15, 2022
A. PREAMBLE
A-1. The authority for the Board of Directors to form and enforce rules is provided by theDeclaration of Covenants, Conditions
and Restrictions under Section 2.5.
B. COMMUNITY REGULATIONS
B-1. REGISTRATION
All residents must register with the manager.
B-7. BARBEQUES
Only gas and electric barbeques are allowed.
B-12. PARKING
Guest parking requires a parking permit.
B-18. ARCHITECTURAL CONTROL
Submit an architectural application before any exterior change.
C. ENFORCEMENT
a) Fine Schedule
To insure compliance with the Rules, the Board may impose the following Monetary Penalties:
1st Violation $40 or warning
Safety Violation Warning or fine up to $300
Noise Violation $150
Continuing Violations $25 per day until cured
Returned Check Fee $25
b) Due Process Requirements
"""

ENFORCEMENT = """SAMPLEVILLE COMMUNITY ASSOCIATION
ENFORCEMENT POLICY
In accordance with the governing documents, the Association must give due process before disciplinary action.
a. Fine Schedule
To insure compliance with the CC&Rs, the Board may impose the following Monetary Penalties and Fines against a homeowner:
1st Violation
$40 or warning
Parking Violation
$50 and/or towing
Late Fee
10% of Regular Assessment
Returned Check Fee
$25
1. Before the Board imposes any fine it holds a hearing.
"""

ETHICS = """SAMPLEVILLE COMMUNITY ASSOCIATION
ETHICS POLICY FOR DIRECTORS & COMMITTEE MEMBERS
adopted ______________
The Board of Directors has adopted the following ethics policy for its directors and committees.
_________________________________________
Sampleville Community Association Board of Directors
"""

COLLECTION = """SAMPLEVILLE COMMUNITY ASSOCIATION
ASSESSMENT COLLECTION POLICY
This document sets forth the Association's policy regarding the collection of assessments. It shall be effective on the date
of adoption, shall supersede any other assessment collection policies of the Association. (CC&Rs §6.4). An owner may request a
payment plan. (CC&Rs §6.12).
"""


def test_operating_rules_sections_fines_and_procedure():
    reading = read(DocumentKind.OPERATING_RULES, RULES, ctx())
    r = reading.record
    assert reading.model == "operating-rules" and reading.complete, reading.missing
    assert r.title == "SAMPLEVILLE COMMUNITY ASSOCIATION OWNER'S MANUAL & RULES"
    assert r.effective == date(2022, 9, 15) and r.authority == "Section 2.5"
    assert [s.code for s in r.rules] == ["B-1", "B-7", "B-12", "B-18"]
    assert {RuleSubject.MEMBER_DISCIPLINE, RuleSubject.PHYSICAL_CHANGE_REVIEW, RuleSubject.COMMON_AREA_USE} <= set(r.subjects)
    fines = {f.label: f for f in r.fines}
    assert fines["Safety Violation"].max_cents == 30_000 and fines["Continuing Violations"].per_day
    assert not fines["Returned Check Fee"].penalty
    assert r.notice_described
    found = codes(reading)
    assert found["penalty-over-cap"].authority == "CIV 5850(c)" and "Noise Violation" in found["penalty-over-cap"].message
    assert found["penalty-over-cap-safety"].severity is Severity.INFO
    assert found["rule-change-procedure"].severity is Severity.CHECK
    assert "no-adoption-date" in found


def test_policies_by_subject():
    enforcement = read(DocumentKind.POLICY, ENFORCEMENT, ctx())
    assert enforcement.record.subject is PolicySubject.ENFORCEMENT
    labels = [f.label for f in enforcement.record.fines]
    assert labels == ["1st Violation", "Parking Violation", "Late Fee", "Returned Check Fee"]
    assert [f.penalty for f in enforcement.record.fines] == [True, True, False, False]
    assert "penalty-schedule-annual" in codes(enforcement) and "penalty-over-cap" not in codes(enforcement)
    ethics = read(DocumentKind.POLICY, ETHICS, ctx())
    assert ethics.record.subject is PolicySubject.ETHICS and ethics.record.adoption.adoption_blank
    assert codes(ethics)["adoption-date-blank"].severity is Severity.CHECK
    collection = read(DocumentKind.POLICY, COLLECTION, ctx())
    assert collection.record.subject is PolicySubject.COLLECTION and collection.record.supersedes_prior
    assert collection.record.declaration_sections == ("6.4", "6.12")
    found = codes(collection)
    assert "effective-on-adoption-undated" in found and found["annual-policy-statement"].severity is Severity.INFO


ELECTION_RULES = """Sampleville Community Association
Election Rules
These Election Rules shall be effective on the date of adoption.
1.1 Member Voting Rights. No Member shall be denied a ballot for any reason other than not being a Member.
1.1.2 General Power of Attorney. A person with general power of attorney for a Member shall not be denied a ballot.
1.2 Voter List. The Association shall maintain a Voter List.
1.3 Voting Power of Each Membership. One vote shall be cast for each separate interest.
1.5 Proxies. Proxies may be used only if authorized in the Bylaws.
2.2 Distribution of Ballots. Ballots shall be distributed a minimum of thirty (30) days prior to the deadline for voting.
3.1 Qualification of Candidates. The Association shall disqualify a nominee for the Board for any of the following reasons:
3.1.3 If the nominee, at the time of nomination, is delinquent in the payment of regular and/or special assessments.
3.2 Nominations. The Association shall provide general notice of the procedure and deadline for submitting a nomination.
3.3 Candidate Registration List. The list of candidates who will appear on the ballot.
4.3 Access to Association Media. If the Board allows any candidate access to Association media, then all qualified candidates
shall be allowed equal access to the same media.
6.3 Appointment of Inspector of Elections. The Board shall appoint one (1) or three (3) Inspectors of Elections.
7 AMENDMENTS. These Election Rules may not be amended less than ninety (90) days prior to an election.
I, ________________________________, am the Secretary of the SAMPLEVILLE COMMUNITY ASSOCIATION, and certify that these
Election Rules were duly adopted by the Board of Directors of the Association and came into effect on the ____ day of
_________________, 2022.
"""


def test_election_rules_record_5105_elements():
    reading = read(DocumentKind.ELECTION_RULES, ELECTION_RULES, ctx())
    r = reading.record
    assert reading.model == "election-rules" and r.certificate and r.adopted is None
    present = set(r.elements)
    assert {ElectionElement.MEDIA_ACCESS, ElectionElement.VOTING_POWER, ElectionElement.PROXIES, ElectionElement.VOTING_PERIOD,
            ElectionElement.INSPECTOR_SELECTION, ElectionElement.CANDIDATE_LIST, ElectionElement.VOTER_LIST,
            ElectionElement.BALLOT_NOT_DENIED, ElectionElement.POWER_OF_ATTORNEY, ElectionElement.NO_LATE_AMENDMENT} <= present
    assert set(r.missing_elements) == {ElectionElement.MEETING_SPACE, ElectionElement.INSPECTOR_HELPERS,
                                       ElectionElement.BALLOT_AND_RULES_DELIVERY}
    assert r.disqualifies_delinquent and not r.directors_must_be_current and not r.excludes_fines
    found = [f for f in reading.findings if f.code == "election-rule-element-not-found"]
    assert {f.authority for f in found} == {"CIV 5105(a)(2)", "CIV 5105(a)(6)", "CIV 5105(h)(4)"}
    by_code = codes(reading)
    assert by_code["directors-not-held-to-nominee-rule"].severity is Severity.PROBLEM
    assert by_code["fines-not-excluded"].authority == "CIV 5105(d)"
    assert by_code["adoption-certificate-blank"].severity is Severity.CHECK


# Grant deeds.

MODERN_DEED = """RECORDING REQUESTED BY:
Example Title Company
When Recorded Mail Document To:
Casey Example
100 Example Way
Sampleton, CA 95000
Sacramento County
Example Clerk, Clerk/Recorder
Doc# 202412130194 Fees
12/13/2024 9:27:00 AM
SPACE ABOVE THIS LINE FOR RECORDER'S USE
APN/Parcel ID(s): 201-1170-099-0023
GRANT DEED
The undersigned grantor(s) declare(s)
The documentary transfer tax is $517.00 and City Tax is $1,292.50 and is computed on the full value.
FOR A VALUABLE CONSIDERATION, receipt of which is hereby acknowledged, Pat Sample, a single person
hereby GRANT(S) to Casey Example, a single person
the following described real property in the City of Sacramento, County of Sacramento, State of California:
Dated: December 6, 2024
UNIT 37, INCLUSIVE IN BUILDING 5 AS DEPICTED, DESCRIBED AND DEFINED IN THE CONDOMINIUM PLAN FOR SAMPLEVILLE BUILDINGS 1, 2, 4,
5, 6, AND 7, RECORDED JANUARY 16, 2019, AS DOCUMENT NO. 201901161002 OF OFFICIAL RECORDS ("PLAN"), AND IN THE RESTATED
DECLARATION OF COVENANTS, CONDITIONS AND RESTRICTIONS, RECORDED SEPTEMBER 20, 2007, IN BOOK 20070920, PAGE 938, OF OFFICIAL
RECORDS.
"""

TITLE_COPY_DEED = """RECORDING REQUESTED BY
Example Title Company
AND WHEN RECORDED MAIL DOCUMENT
AND TAX STATEMENT TO:
Casey Example
_____ space Above This Line for Recorder's Use Only _____
A.P.N.: 201-1170-099-0000
GRANT DEED
DOCUMENTARY TRANSFER TAX $110.00; CITY TRANSFER TAX $999.00
FOR A VALUABLE CONSIDERATION, receipt of which is hereby acknowledged, EXAMPLE HOMES, LLC, A DELAWARE LIMITED LIABILITY COMPANY,
Hereby GRANT{S) ta Casey Example, a single person
The land described herein is situated in the State of California
subject to the covenants recorded September 20, 2007 as (book) 20070920, (page) 938, Official Records.
The following property has been sold. Please update your records to reflect these changes.
"""

TRUSTEE_DEED = """Sacramento County Recorder
BOOK 20120302 PAGE 1601
Friday, MAR 02, 2012 2:30:13 PM
SPACE ABOVE THIS LINE FOR RECORDER'S USE
TRUSTEE'S DEED UPON SALE
APN#
201-1170-099-0006
The amount of the unpaid debt was $ 345,092.09
The amount paid by the Grantee was$ 101,200.01
EXAMPLE TRUST COMPANY, N.A., as the duly appointed Trustee under a Deed of Trust referred to below, and herein called
"Trustee", does hereby grant without covenant or warranty to:
EXAMPLE CAPITAL FUND I, LLC
herein called Grantee, the following described real property situated in Sacramento County.
"""

BLOCK = PlanBlock(Building.BLDG_5, "099", 28, 10, first_subparcel=14, book_page="2011170")


def test_modern_grant_deed_fields_and_spec_checks():
    community = StubCommunity(units=("20111700990023",), blocks=(BLOCK,))
    reading = read(DocumentKind.GRANT_DEED, MODERN_DEED, ctx(community, "GD 202412130195.pdf"))
    r = reading.record
    assert reading.complete, reading.missing
    assert (r.number, r.recorded, r.deed_type) == ("202412130194", date(2024, 12, 13), "grant deed")
    assert r.apn == "201-1170-099-0023" and (r.unit, r.building) == ("37", "5")
    assert (r.grantor, r.grantee) == ("Pat Sample, a single person", "Casey Example, a single person")
    assert (r.county_tax_cents, r.city_tax_cents, r.consideration_cents) == (51_700, 129_250, 47_000_000)
    assert r.dated == date(2024, 12, 6) and r.requested_by == "Example Title Company"
    assert (r.declaration_cited, r.plan_cited) == ("200709200938", "201901161002")
    assert r.recording.fees_cents is None  # the head's largest amount is the transfer tax, not the fee
    assert set(codes(reading)) == {"name-number-differs"}
    other_unit = read(DocumentKind.GRANT_DEED, MODERN_DEED.replace("UNIT 37", "UNIT 36"), ctx(community, "GD 202412130194.pdf"))
    assert codes(other_unit)["unit-apn-mismatch"].severity is Severity.CHECK


def test_title_company_copy_with_scan_slips():
    reading = read(DocumentKind.GRANT_DEED, TITLE_COPY_DEED, ctx(StubCommunity(units=("20111700990023",))))
    r = reading.record
    assert not r.number and r.recording.unrecorded_copy
    assert r.grantee == "Casey Example, a single person" and r.grantor.startswith("EXAMPLE HOMES, LLC")
    assert r.parent_parcel and r.declaration_cited == "200709200938" and r.sale_notice
    found = codes(reading)
    assert {"unrecorded-copy", "parent-parcel", "transfer-taxes-disagree", "sale-notice-attached"} <= set(found)
    assert set(reading.missing) == {"number", "recorded"}


def test_trustees_deed_upon_sale():
    reading = read(DocumentKind.GRANT_DEED, TRUSTEE_DEED, ctx(StubCommunity()))
    r = reading.record
    assert r.deed_type == "trustee's deed upon sale"
    assert (r.number, r.recorded) == ("201203021601", date(2012, 3, 2))
    assert r.apn == "201-1170-099-0006"
    assert (r.grantor, r.grantee) == ("EXAMPLE TRUST COMPANY, N.A.", "EXAMPLE CAPITAL FUND I, LLC")
    assert (r.unpaid_debt_cents, r.amount_paid_cents) == (34_509_209, 10_120_001)


# Public reports, plans, maps, plan sets.

FINAL_REPORT = """Department of Real Estate
of the
State of California
FINAL SUBDIVISION PUBLIC REPORT
In the matter of the application of PLANNED DEVELOPMENT
EXAMPLE COMMUNITIES LLC, FILE NO.: 999004SA-FOO
A California limited liability company
ISSUED: JUNE 28, 2019
EXPIRES: JUNE 27, 2024
for a Final Subdivision Public Report on
EXAMPLE PARCEL 4 -
"SAMPLEVILLE"
DEPARTMENT OF REAL ESTATE
THIS REPORT COVERS ONLY UNITS 48 THROUGH 57, INCLUSIVE OF BUILDING NO. 7.
About This Phase: This is the fourth phase which consists of approximately 3.8 acres.
This phase is part of a total subdivision which, if developed as proposed, will consist of a total of 8 phases containing 81
units within the overall projected subdivision.
Under the built-out budget, monthly assessment against each condominium unit will be $302.75. Under the 4th phase budget, the
monthly assessment per interest is $318.00.
"""

AMENDED_REPORT = """Department of Real Estate
AMENDED SUBDIVISION PUBLIC REPORT
In the matter of the application of
PLANNED DEVELOPMENT
EXAMPLE COMMUNITIES LLC,
FILE NO.:
999003SA-A01
ISSUED:
FEBRUARY 14, 2019
AMENDED:
FEBRUARY 26, 2020
for an Amended Subdivision Public Report on
EXPIRES:
FEBRUARY 13. 2024
EXAMPLE PARCEL 4 -
"SAMPLEVILLE"
(DRE PHASE 3)
THIS AMENDED REPORT COVERS ONLY UNITS 1 THROUGH 7, INCLUSIVE OF BUILDING NO. 1.
"""


def test_public_reports_both_header_layouts_against_the_phase_table():
    reports = (PublicReport("999004SA", Building.BLDG_7, 4, 10, date(2020, 4, 20), "Example Communities", issued=date(2019, 6, 28)),
               PublicReport("999003SA", Building.BLDG_1, 5, 7, date(2020, 2, 28), "Example Communities"))
    community = StubCommunity(reports=reports, units=tuple(str(n) for n in range(81)))
    final = read(DocumentKind.DRE_REPORT, FINAL_REPORT, ctx(community))
    r = final.record
    assert final.complete, final.missing
    assert (r.file_number, r.base_file_number, r.report_type.value) == ("999004SA-F00", "999004SA", "final")
    assert r.subdivider == "EXAMPLE COMMUNITIES LLC" and r.subdivision == 'EXAMPLE PARCEL 4 - "SAMPLEVILLE'
    assert (r.issued, r.expires, r.phase) == (date(2019, 6, 28), date(2024, 6, 27), 4)
    assert (r.first_unit, r.last_unit, r.units, r.building) == (48, 57, 10, 7)
    assert (r.total_phases, r.total_units) == (8, 81)
    assert (r.built_out_assessment_cents, r.phase_assessment_cents) == (30_275, 31_800)
    assert set(codes(final)) == {"report-expired"}
    amended = read(DocumentKind.DRE_REPORT, AMENDED_REPORT, ctx(community))
    a = amended.record
    assert (a.report_type.value, a.issued, a.amended, a.expires, a.phase) == ("amended", date(2019, 2, 14), date(2020, 2, 26),
                                                                               date(2024, 2, 13), 3)
    assert codes(amended)["phase-differs"].severity is Severity.CHECK


CONDO_PLAN = """Sacramento County
Example Clerk, Clerk/Recorder
Doc# 201809211358 Fees
9/21/2018 3:27:32 PM Taxes
Titles 1 Paid
Pages 50
CONDOMINUM PLAN
FOR
SAMPLEVILLE
BUILDINGS 1, 2, 4, 5, 6, AND 7
THERE ARE CURRENTLY NO DEEDS OF TRUST OF RECORD
LEGAL DESCRIPTION
ALL OF UNITS 1 THROUGH 20 INCLUSIVE, 33 THROUGH 80 INCLUSIVE, ASSOCIATION COMMON AREAS (A.C.A.) 1, 2, 4, 5, 6, AND 7, AS SHOWN
ON THE CONDOMINIUM PLAN FOR SAMPLEVILLE, IN BOOK 20070912. OF OFFICIAL RECORDS. AT PAGE 0757, BEING A FURTHER DIVISION OF
PORTIONS OF LOT 1 OF THE PARCEL MAP FILED IN BOOK 194 OF PARCEL MAPS, AT PAGE 18.
SURVEYOR'S STATEMENT
SHEET 1 OF 48
"""

FINAL_MAP = """FINAL MAP OF
EXAMPLE NORTH
PARCEL 4
A CONDOMINIUM PROJECT
SUBDIVISION NO.
SURVEYOR'S STATEMENT
BEING ALL OF PARCEL 4 AS SHOWN ON THE MASTER PARCEL MAP RECORDED IN BOOK OF PARCEL MAPS, AT PAGE
AUGUST 2006
THE UNDERSIGNED HEREBY CONSENT TO THE PREPARATION AND RECORDATION OF THIS FINAL MAP AND DO HEREBY DEDICATE TO PUBLIC USES
THE STREETS SHOWN HEREON.
SHEET 1 OF 4
"""

DECISION = """STAFF LEVEL SITE PLAN AND DESIGN REVIEW
FILE NUMBER: DR99-001
PROJECT ADDRESS: 1 Example Drive, Sacramento, CA 95000
PROJECT APN: 201-1170-099-0000
REQUEST: A request to modify the design for six proposed buildings totaling 57 units within a condominium development on 3.78
partially developed acres.
ANALYSIS: On March 9, 2006, the Planning Commission approved the entitlements (P99-164).
D ATE OF ACTION: May 24, 2018
A CTION: Approved with Conditions
"""


def test_condominium_plan_map_and_plan_set():
    plan = read(DocumentKind.CONDOMINIUM_PLAN, CONDO_PLAN, ctx(name="Condominium Plan 201809211358.pdf"))
    p = plan.record
    assert plan.complete, plan.missing
    assert p.title == "CONDOMINIUM PLAN FOR SAMPLEVILLE BUILDINGS 1, 2, 4, 5, 6, AND 7"
    assert (p.number, p.recorded, p.sheets) == ("201809211358", date(2018, 9, 21), 48)
    assert p.buildings == (1, 2, 4, 5, 6, 7) and p.unit_ranges == ((1, 20), (33, 80)) and p.units == 68
    assert p.association_common_areas == (1, 2, 4, 5, 6, 7) and p.divides_plan == "200709120757"
    assert p.surveyor_statement and p.no_deeds_of_trust
    assert set(codes(plan)) == {"divides-earlier-plan"}
    final_map = read(DocumentKind.MAP, FINAL_MAP, ctx(name="Final Map.pdf"))
    m = final_map.record
    assert m.map_kind.value == "final map" and m.dated == "August 2006" and m.sheets == 4
    assert m.surveyor_statement and m.owner_consent and m.dedications
    assert "filing-blank" in codes(final_map)
    decision = read(DocumentKind.PLAN_SET, DECISION, ctx(name="DR99-001_ROD.pdf"))
    d = decision.record
    assert (d.plan_kind.value, d.file_number, d.related_files) == ("record of decision", "DR99-001", ("P99-164",))
    assert (d.dated, d.units, d.buildings, d.acres, d.decision) == (date(2018, 5, 24), 57, 6, "3.78", "approved with conditions")
    assert d.project_address == "1 Example Drive, Sacramento, CA 95000"


def test_models_decline_other_kinds_text():
    assert read(DocumentKind.ANNEXATION, BYLAWS, ctx()) is None
    assert read(DocumentKind.AMENDMENT, OLD_ANNEXATION, ctx()) is None
    assert read(DocumentKind.GRANT_DEED, BYLAWS, ctx()) is None
    assert read(DocumentKind.DRE_REPORT, MODERN_DEED, ctx()) is None
    assert read(DocumentKind.ELECTION_RULES, ETHICS, ctx()) is None
