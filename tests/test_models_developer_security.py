"""The subdivider's DRE securities: security agreements, subsidy agreements, surety bonds, releases, and the register."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from jason.community import mystique
from jason.community.document_models import ModelContext, read
from jason.community.models.developer_security import ReleaseGround, SecurityType, split_instruments
from jason.community.symbols import DocumentKind

AGREEMENT = """STATE OF CALIFORNIA DEPARTMENT OF REAL ESTATE
ASSESSMENT SECURITY AGREEMENT AND INSTRUCTIONS TO ESCROW DEPOSITORY - REG. 2792.9
RE 643 (Rev. 8/10)
NAME OF OWNERS ASSOCIATION
MYSTIQUE COMMUNITY ASSOCIATION
ADDRESS, CITY, STATE, ZIP CODE
NAME OF SUBDIVIDER
Example Homes LLC, a California limited liability company
ADDRESS, CITY, STATE, ZIP CODE
NAME OF SUBDIVISION
JMA - North Natomas Parcel 4 - "Mystique" (DRE Phase 7)
COUNTY Sacramento
NAME OF ESCROW-HOLDER
Example Title Company
ADDRESS, CITY, STATE, ZIP CODE
ESCROW ACCOUNT NUMBER P-400000-2 DRE FILE NUMBER 165814SA-F00
PART ONE - ASSESSMENT SECURITY AGREEMENT
1. This Assessment Security Agreement ("Agreement") is made this 14th day of December 2020, by and between the Subdivider
and the Association identified above.
2. Recitals. A. Property to Which Agreement Applies. Subdivider is the owner of certain real property described as: Units 18
through 27, inclusive in Building 4 (herein "the Subdivision").
the Subdivider has procured the issuance of the surety bond in the sum of Seventeen Thousand One Hundred Sixty Dollars ($17,160.00)
"""

BOND = """STATE OF CALIFORNIA DEPARTMENT OF REAL ESTATE SURETY BOND (Regulation 2792.9) RE 643J (Rev. 12/16)
JMA - North Natomas Parcel 4 - "Mystique" (DRE Phase 7) KNOW ALL MEN BY THESE PRESENTS: That we, Example Homes LLC, a California
limited liability company as Principal, and Example Surety Company BOND NUMBER 1099999 SUBDIVISIONS PREMIUM $129.00 (Name of Subdivider)
(Name of Surety), a corporation organized and doing business under the laws of the State of California as Surety, are firmly held
and bound unto MYSTIQUE COMMUNITY ASSOCIATION (Name of Association), a community association described in Civil Code Section 4800,
as Obligee, in the penal sum of Seventeen Thousand One Hundred Sixty Dollars ($ 17,160.00 ), for the payment of which we bind ourselves.
Surety waives the right granted under California Civil Code Section 2845. this 14th day of December, 2020.
"""

RELEASE = """Example Title Company
September 18, 2024
Example Surety Company
RE: Mystique (DRE Phase 7)
Phase Bond# Description Amount
Mystique Phase 7 1099999 Phase 7 Assessment Bond $17,160
Please be advised that the undersigned, as Escrow Holder, has held the above referenced bond for an Assessment Guarantee, pursuant to
Regulation 2792.9. We have received from "Mystique Community Association", a Resolution stating that the subdivider has
satisfactorily performed its obligations and the Association is authorizing the release of the within bond.
"""

SUBSIDY = """MYSTIQUE SUBSIDY AGREEMENT - PHASE 3
MYSTIQUE COMMUNITY ASSOCIATION AND EXAMPLE HOMES LLC
1. Parties to Agreement. This Subsidy Agreement ("Agreement") is made this 1st day of December, 2019, by and between the Mystique
Community Association, a California nonprofit mutual benefit corporation ("Association"), and Example Homes LLC, a California limited
liability company ("Declarant").
C. Declaration. "Declaration" shall mean the Restated Declaration of Covenants, Conditions and Restrictions for Mystique, recorded on
September 20, 2007, in Book 20070920, at Page 0938, in the Official Records of Sacramento County, California.
L. Subdivision. Phase 3 of the subdivision development consists of seven (7) residential Units.
C. Difference in Assessment Amounts. The Association's estimated Regular Assessment per Unit per month under the Interim Budget is
$30.00 greater than Declarant desires owners of Units be obligated to pay.
4. Term of Subsidy. The term of the Subsidy ("Term") shall commence on the 1st day of the 1st month following the close of the first
Unit in Phase 3, and shall continue until the earlier of: (a) six (6) months from that day; or (b) the date Regular Assessments commence
for the first Unit within a subsequent Phase. 5. Extension.
A. Payment of Subsidy. Declarant shall pay the difference by which the monthly Regular Assessment levied against the Unit exceeds
$295.25. Declarant shall pay the Subsidy on or before the 10th calendar day of the month. a late charge of 5% of such delinquent amount.
"""


def ctx(name: str = "") -> ModelContext:
    return ModelContext(mystique(), None, date(2026, 9, 29), name)


def test_the_assessment_security_agreement_reads_its_form_fields():
    reading = read(DocumentKind.SECURITY_AGREEMENT, AGREEMENT, ctx())
    r = reading.record
    assert reading.complete and (r.form, r.security_type, r.phase, r.dre_file) == ("RE 643", SecurityType.ASSESSMENT, 7, "165814SA")
    assert (r.escrow_holder, r.escrow_account, r.units, r.made_on) == ("Example Title Company", "P-400000-2", (18, 27), date(2020, 12, 14))
    assert r.bond_amount_cents == 1716000
    assert any(f.code == "assessment-release-rule" and f.authority == "10 CCR 2792.9(b)(4)" for f in reading.findings)


def test_the_surety_bond_reads_number_sum_parties_and_waiver():
    reading = read(DocumentKind.SURETY_BOND, BOND, ctx())
    r = reading.record
    assert reading.complete and (r.bond_number, r.form, r.phase, r.penal_sum_cents) == ("1099999", "RE 643J", 7, 1716000)
    assert r.obligee == "MYSTIQUE COMMUNITY ASSOCIATION" and r.surety == "Example Surety Company" and r.waives_2845
    assert r.signed_on == date(2020, 12, 14) and r.security_type is SecurityType.ASSESSMENT


def test_the_release_reads_the_escrow_holders_table():
    reading = read(DocumentKind.BOND_RELEASE, RELEASE, ctx())
    r = reading.record
    assert reading.complete and r.dated == date(2024, 9, 18) and r.cites_resolution and not r.by_association
    assert [(b.number, b.phase, b.amount_cents) for b in r.bonds] == [("1099999", 7, 1716000)]
    assert ReleaseGround.PERFORMED in r.grounds


def test_the_subsidy_agreement_reads_the_gap_and_checks_the_declaration_it_cites():
    reading = read(DocumentKind.SUBSIDY_AGREEMENT, SUBSIDY, ctx())
    r = reading.record
    assert (r.phase, r.units_in_phase, r.target_assessment_cents, r.gap_cents, r.due_day, r.late_charge_percent) == (3, 7, 29525, 3000, 10, 5)
    assert r.declaration_book_page == "20070920 0938" and r.term_end.startswith("earlier of")
    # The citation agrees with the pinned Restated Declaration, 200709200938.
    assert "declaration-citation" not in {f.code for f in reading.findings}


def test_a_production_splits_into_its_instruments():
    pieces = split_instruments("cover letter text. " + AGREEMENT + " power of attorney pages " + BOND)
    assert [k for k, _ in pieces] == [DocumentKind.SECURITY_AGREEMENT, DocumentKind.SURETY_BOND]


def test_the_register_joins_bonds_to_phases_and_releases(tmp_path: Path):
    from jason.tasks.developer_security import register

    folder = tmp_path / "developer-security"
    folder.mkdir()
    files = {"security agreement phase 7": AGREEMENT, "Mystique Bond # 1099999": BOND, "Bond Release Letter Phase 7": RELEASE}
    index = []
    for name, text in files.items():
        (folder / f"{name}.txt").write_text(text, encoding="utf-8")
        index.append({"id": name, "name": f"{name}.pdf", "file": f"{name}.pdf"})
    (folder / "index.json").write_text(json.dumps(index), encoding="utf-8")
    result = register(tmp_path, mystique(), today=date(2026, 9, 29))
    bond = next(b for b in result["bonds"] if b["number"] == "1099999")
    assert (bond["phase"], bond["penalSumCents"], bond["status"]) == (7, 1716000, "released")
    phase7 = next(p for p in result["phases"] if p["phase"] == 7)
    assert phase7["bonds"] == ["1099999"] and phase7["agreements"][0]["type"] == "assessment"


def test_each_association_common_area_is_its_buildings_parcel():
    m = mystique()
    acas = m.association_common_areas()
    assert [a.number for a in acas] == list(range(1, 9)) and all(int(a.building) == a.number for a in acas)
    assert {a.apn for a in acas} <= set(m.common_areas())
    blocks = {b.block: b for b in m.unit_blocks()}
    for a in acas:
        block = blocks[a.apn[7:10]]
        assert (block.building, block.first_unit, block.first_unit + block.count - 1) == (a.building, *a.units)
    reports = {r.phase: r for r in m.public_reports()}
    assert all(reports[a.phase].building == a.building for a in acas)
    labels = {u.label: u.account for u in m.utility_accounts()}
    # The real City account numbers stay in the private specification; check that each ACA has its own ten-digit account.
    assert all(len(labels[k]) == 10 and labels[k].isdigit() for k in ("ACA 3", "ACA 8")) and labels["ACA 3"] != labels["ACA 8"]
