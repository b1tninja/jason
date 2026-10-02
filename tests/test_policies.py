"""The policy packets' readers and the policy report, on made-up policies in the carriers' layouts.

Every number, amount, date, and address here is made up.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from jason.community.base import Policy
from jason.community.document_models import ModelContext, Severity, read
from jason.community.symbols import Building, DocumentKind, PolicyKind
from jason.tasks.policies import SheetRow, build, role_of, sheet_row_for

TODAY = date(2026, 9, 30)
MASTER = Policy(PolicyKind.MASTER, "N000XX0000-01", date(2026, 9, 28), carrier="Example National", prior_numbers=("N000XX0000-00",),
                deductible_cents=1_000_000)
CRIME = Policy(PolicyKind.FIDELITY, "4126000000000Y", date(2027, 9, 28), prior_numbers=("4125000000000Y",))
FLOOD3 = Policy(PolicyKind.FLOOD, "5010000003", date(2026, 12, 3), building=Building.BLDG_3)


class FakeCommunity:
    def insurance(self):
        return SimpleNamespace(policies=(MASTER, CRIME, FLOOD3), master=lambda: MASTER)

    def mail_addresses(self):
        return (SimpleNamespace(kind=SimpleNamespace(name="CURRENT"), words=("901 H ST",)),)

    def units(self):
        return tuple(range(81))


def ctx() -> ModelContext:
    return ModelContext(community=FakeCommunity(), today=TODAY)


PACKAGE = """Arden Insurance Services
Accelerant
POLICY DECLARATIONS - Condominium Assoc.
 $
N000XX0000-01
POLICY NUMBER:
POLICY PERIOD:  FROM                                                TO
09/28/2025
09/28/2026
PREMIUM
20,000.00
          COMMERCIAL PROPERTY COVERAGE PART
 $
3,000.00
          COMMERCIAL GENERAL LIABILITY COVERAGE PART
 $
23,000.00
TOTAL:
Mystique Community Association
8340 Old Manager Blvd. #100
Citrus Heights, CA 95610
AGENCY AND MAILING ADDRESS:
N000XX0000-00
RENEWAL OF NUMBER:
Mortgagee Name And Address
1
1-8
3048 Macon Drive
Sacramento, CA 95835
Limit of Insurance
30,000,000
loc# 1 - Building
BV
GRC
10,000
12- Months
loc# 1 - Business Income with Extra Expense
Equipment Breakdown
$30,100,000
$10,000
Protective Safeguards - Automatic Sprinkler System
Condominiums -
81
units
Each Occurrence Limit
1,000,000
General Aggregate Limit
2,000,000
SCHEDULE OF FORMS AND ENDORSEMENTS
FORM NUMBER &
IL 09 53 01 15
EXCLUSION OF CERTIFIED ACTS OF TERRORISM
N CP 12301 10 20
PROPERTY COVERED – RESIDENTIAL COMMUNITY ASSOCIATIONS – UNIT INTERIOR – SINGLE ENTITY
"""


def codes(reading):
    return {f.code: f for f in reading.findings}


def test_the_master_package_declarations():
    reading = read(DocumentKind.INSURANCE_POLICY, PACKAGE, ctx())
    assert reading.model == "package-declarations"
    r = reading.record
    assert (r.policy_number, r.renewal_of, r.term_start, r.term_end) == ("N000XX0000-01", "N000XX0000-00", date(2025, 9, 28), date(2026, 9, 28))
    assert (r.premium, r.premium_parts) == (2_300_000, {"Property": 2_000_000, "General Liability": 300_000})
    assert (r.building_limit, r.valuation, r.property_deductible, r.business_income) == (3_000_000_000, "guaranteed replacement cost",
                                                                                       1_000_000, "12 months")
    assert (r.each_occurrence, r.general_aggregate, r.units) == (100_000_000, 200_000_000, 81)
    assert r.protective_safeguards == ("Automatic Sprinkler System",) and r.terrorism_excluded and r.unit_interior == "single entity"
    found = codes(reading)
    assert found["mailing-address-not-current"].severity is Severity.PROBLEM and "Old Manager" in found["mailing-address-not-current"].message
    assert "deductible-differs" not in found and "number-not-in-specification" not in found


CRIME_TEXT = """COMMERCIAL CRIME POLICY DECLARATIONS
CR 00 22 SCHEDULE OF FORMS
COMMERCIAL CRIME POLICY
DECLARATIONS
In return for the payment of the premium, and subject to all the terms and conditions of this Policy
Coverage Is Written: Primary
Insuring Agreements Limit Of Insurance Per Occurrence Deductible Amount Per Occurrence 1. Employee Theft
Coverage is provided only if an amount is shown opposite an Insuring Agreement. If the amount is left blank or "Not Covered" is inserted,
such Insuring Agreement and any other reference thereto in this Policy are deleted. $ 400,000 $ 1,000 $ 25,000 $ 1,000 $ 25,000 $ 1,000
$ 25,000 $ 1,000 $ 25,000 $ 1,000 $ 50,000 $ 1,000 $ 25,000 $ 1,000 412600-00-00-00-0Y 09-28-2026 09-28-2027 MANUFACTURERS ALLIANCE
INSURANCE COMPANY MYSTIQUE COMMUNITY
Policy Period Premium From: 09-28-2026 To: 09-28-2027 $ 318.00
"""


def test_the_crime_declarations():
    reading = read(DocumentKind.INSURANCE_POLICY, CRIME_TEXT, ctx())
    assert reading.model == "crime-declarations"
    r = reading.record
    assert (r.policy_number, r.term_start, r.term_end, r.premium) == ("4126000000000Y", date(2026, 9, 28), date(2027, 9, 28), 31_800)
    assert [(a.name, a.limit) for a in r.agreements][:1] == [("Employee Theft", 40_000_000)]
    assert next(a for a in r.agreements if a.name == "Computer And Funds Transfer Fraud").limit == 5_000_000


def test_the_dno_binder():
    text = ("MG Skinner & Associates\nD&O/Crime Binder - Renewal\nBinder #: 1-XXX-CA-00000000-01\nD&O:\nCarrier: Example Surety Company\n"
            "DECLARATIONS - D&O\nNOTICE: THIS IS A CLAIMS-MADE POLICY.\nPOLICY NUMBER: 1-XXX-CA-00000000-01\nPhysical\nMailing\n3048 Macon Dr\n"
            "8340 Old Manager Blvd. #100\nSACRAMENTO, CA 95835\nCITRUS HEIGHTS, CA 95610\nInception Date:\n9/28/2025\nExpiration Date:_9/28/2026\n"
            "LIMIT OF LIABILITY:\n$1,000,000\nRETENTION:\n$1,000\nPRIOR LITIGATION DATE:\n9/28/2024\nPREMIUM:\n$1,292.95\n")
    reading = read(DocumentKind.INSURANCE_POLICY, text, ctx())
    assert reading.model == "dno-declarations"
    r = reading.record
    assert (r.carrier, r.policy_number, r.limit, r.retention, r.premium) == ("Example Surety Company", "1-XXX-CA-00000000-01", 100_000_000,
                                                                           100_000, 129_295)
    assert r.claims_made and r.prior_litigation == date(2024, 9, 28)
    found = codes(reading)
    assert found["dno-limit"].severity is Severity.INFO and "mailing-address-not-current" in found


def test_the_umbrella_evidence():
    text = ("McGowan Program Administrators Umbrella Program\nEvidence of Insurance and Purchasing Group Membership\nINSURER:\n"
            "Federal Insurance Company\nEVIDENCE NUMBER:\nG00000000-G00000001\n09/28/2025  to  09/28/2026\nLIMIT:\n$1,000,000 / $1,000,000\n"
            "$1,106.00\nTotal Premium, Fees, Surcharges, and Taxes\n")
    r = read(DocumentKind.INSURANCE_POLICY, text, ctx()).record
    assert (r.carrier, r.evidence_number, r.term_end, r.each_occurrence, r.premium) == ("Federal Insurance Company", "G00000000-G00000001",
                                                                                         date(2026, 9, 28), 100_000_000, 110_600)


def test_roles_by_name_and_text():
    assert role_of("FLOOD POLICY 26-27 BLDG 3.pdf") == "declarations"
    assert role_of("Certificate of Insurance 2025-2026.pdf") == "certificate"
    assert role_of("CAIS - 4125011561232Y Renewal 09-28-2025.pdf") == "invoice"
    assert role_of("Status letter to insured dated July 9, 2026.pdf") == "claim"
    assert role_of("Annual Disclosures 25-26.pdf") == "disclosure"


def test_the_report_compares_the_sheet_the_specification_and_the_declarations():
    sheet = [SheetRow("Master", "", "N000XX0000-00", "abc", date(2026, 9, 28), {2025: 2_600_000}),
             SheetRow("Fidelity", "", "4125000000000Y", "", date(2026, 9, 28), {2026: 31_800}),
             SheetRow("Flood", "3", "5010000003", "", date(2027, 12, 3), {2026: 159_600})]
    assert sheet_row_for(MASTER, sheet).number == "N000XX0000-00"
    docs = [
        {"id": "a", "name": "Policy ARD PKG 25-26.pdf", "path": "a", "local": "a", "policies": ["master"], "role": "declarations", "modified": "",
         "model": "package-declarations", "fields": {"policy_number": "N000XX0000-01", "term_start": "2025-09-28", "term_end": "2026-09-28",
                                                      "premium": 2_300_000, "property_deductible": 1_000_000, "building_limit": 3_000_000_000},
         "findings": [{"code": "mailing-address-not-current", "message": "old address", "severity": "problem"}]},
        {"id": "b", "name": "FLOOD POLICY 26-27 BLDG 3.pdf", "path": "b", "local": "b", "policies": ["flood-3"], "role": "declarations",
         "modified": "", "model": "nfip-flood-declarations",
         "fields": {"policy_number": "5010000003", "building": 3, "term_start": "2026-12-03", "term_end": "2027-12-03", "premium": 159_600,
                    "deductible": 200_000, "limit": 300_000_000}, "findings": []},
    ]
    report = {p["key"]: p for p in build(FakeCommunity(), sheet, docs, today=TODAY)}
    master = {f["code"] for f in report["master"]["findings"]}
    assert {"sheet-number", "sheet-premium-missing", "declarations-ended", "mailing-address-not-current"} <= master
    fidelity = {f["code"]: f for f in report["fidelity"]["findings"]}
    assert fidelity["sheet-renewal"]["message"].startswith("the sheet's renewal date is 2026-09-28") and "no-declarations" in fidelity
    flood = {f["code"]: f for f in report["flood-3"]["findings"]}
    assert flood["sheet-next-term"]["severity"] == "info" and "sheet-renewal" not in flood
    assert report["flood-3"]["terms"][0]["limits"] == {"limit": 300_000_000}
