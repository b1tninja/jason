"""Mystique's recurring deadlines, each with its authority and the PayHOA evidence that shows it done.

The fiscal year is the calendar year (the reserve studies are by fiscal year, FY26 starting January 2026). The PayHOA
categories are the ones the association books these payments to (read September 29, 2026). Insurance renewals come
from ``insurance.py`` and the reserve study's site visit from the studies on disk, not from rows here.
"""

from __future__ import annotations

from datetime import date

from jason.community.applicability import ELEVATED_ELEMENTS_INSPECTION, Fact, Is, SystemKind
from jason.community.fire_protection import FIRE_ALARM_SYSTEM, NFPA_25_SPRINKLERS
from jason.community.obligations import Obligation

# What each fire protection row reaches, asked of each system in life_safety.py (jason applies). NFPA_25_SPRINKLERS is a
# fire sprinkler system, except one installed under NFPA 13D; that exclusion is NFPA 25's scope as secondary sources
# give it (docs/fire-protection.md), not read from the standard.
_BACKFLOW_ASSEMBLY = Is(Fact.SYSTEM, SystemKind.BACKFLOW)

OBLIGATIONS: tuple[Obligation, ...] = (
    Obligation("Property tax, first installment (common-area parcels)", "Rev. & Tax. Code 2617, 2618: due Nov 1, delinquent after Dec 10",
               month=12, day=10, window_days=160, grace_days=150, categories=("Property Tax", "Delinquent Taxes"),
               note="Paid as early as September (the county's receipt of Sep 22, 2025 names the 1st installment). The "
                    "receipt names the bill and installment; a payment's date is PayHOA's posting date."),
    Obligation("Property tax, second installment (common-area parcels)", "Rev. & Tax. Code 2617, 2618: due Feb 1, delinquent after Apr 10",
               month=4, day=10, window_days=160, grace_days=150, categories=("Property Tax", "Delinquent Taxes"),
               note="PayHOA posts a payment days after it is made: the Dec 31, 2025 payment of the 2nd installment "
                    "posted Jan 5, 2026."),
    # Listed, not judged: the payments mix estimated payments ("Payment Confirmation IRS Estimated Tax Payment 26-09" is
    # attached to the September 11, 2026 payment) and balances due, and a date alone does not say which deadline one met.
    Obligation("Income tax payments (IRS, FTB)", "IRC 6072, 6655; Rev. & Tax. Code 18601, 19025: balances by the 15th day of the "
               "fourth month after the fiscal year; estimates in the fourth, sixth, ninth, and twelfth months",
               categories=("Income Tax", "State", "Federal"),
               payee_words=("FRANCHISE TAX", "CALIFORNIA FRAN", "ORIG CO NAME:IRS", "USATAXPYMT"),
               note="The attached confirmation says whether a payment is an estimate or a balance due; no payment is owed "
                    "without taxable income."),
    Obligation("Income tax returns prepared", "IRC 6072, 6081; Rev. & Tax. Code 18601, 18604: April 15, or October 15 on extension",
               every_years=1, categories=("Tax Preparation (CPA)",),
               note="The CPA's invoice shows the returns were prepared, not when they were filed."),
    # Corp. Code 8210(a), (c) and Civil Code 5405(b), read October 2, 2026: biennially in the filing period, the month the
    # articles were filed (May 2007) and the five months before it, so December 1 to May 31 of each odd year.
    Obligation("Statement of information and SI-CID", "Corp. Code 8210(a), (c); Civil Code 5405(b): every two years, "
               "December 1 to May 31 of each odd year (articles filed May 16, 2007)",
               every_years=2, categories=("Secretary of State",), done_on=date(2025, 5, 5),
               note="Last filed May 5, 2025 (bizfile's approval, attached to the May 12, 2025 payment); the next is due "
                    "by May 31, 2027. Counted from the filing, so the date shown runs a few weeks early. The $5 "
                    "payment of December 2025 is not counted: it comes within the interval, and what it paid for is not on disk."),
    # Read October 4, 2026. State: CCCPH 3.3.3(a), (b) (adopted December 19, 2023, effective July 1, 2024; amended April 21,
    # 2026): "BPAs must be field tested at least annually" by "certified backflow prevention assembly testers"; HSC 116407
    # directs the State Water Board to adopt the standards, and the Title 17 articles (7583-7605) it replaced are repealed.
    # City: its notices of April 16 and June 2, 2026 cite "California Health and Safety Code, Section 116407, City of
    # Sacramento Code 13.04.240, and the Cross Connection Control Policy Section 9" and warn of "Water Service Termination
    # ... per City Code 13.04.245". Code 13.04.240 (as the Council's 2024 ordinance packet reads) has the customer comply
    # with the standards the Council adopts by resolution and makes a violation an infraction; the annual test, the tester,
    # and the 15 days are in those standards and the notices, and the standards' own text was not found. County: for 2024
    # and 2025 the County's Environmental Management Department ran the program for the City and cited Sacramento County
    # Code 6.30.110 (the County's FAQ says the owner tests at least annually and repairs a failed assembly). Details:
    # mystique/docs/backflow-program.md.
    Obligation("Backflow assembly test", "California Health and Safety Code 116407 and the State Water Board's Cross-Connection "
               "Control Policy Handbook 3.3.3(b): \"BPAs must be field tested at least annually\" by a certified tester; City of "
               "Sacramento Code 13.04.240 and 13.04.245, and the City's Cross Connection Control Policy Section 9, as its "
               "annual notices cite them; Sacramento County Code 6.30.110 (County notices of 2024 and 2025)",
               month=5, day=31, categories=("Backflow Prevention",), payee_words=("LEDOUX", "LE DOUX"),
               applies=_BACKFLOW_ASSEMBLY,
               note="Six assemblies at 3000 Macon Dr on the City account (the County's and the City's lists agree): a 2\" "
                    "irrigation RP (meter 34049156), a 4\" domestic RP (meter 70226482), and four fire-line double "
                    "checks (6\" and 8\"). A City-registered tester tests each, the City's tag goes on each that passes, and "
                    "the tester files the report in the City's portal. The due date was June 1 in the County's 2024 and "
                    "2025 notices and May 31 in the City's 2026 notices (the 2026 reports show May 31, 2027). A failed assembly "
                    "is repaired or replaced within 15 days of the failed test, then retested and tagged; the County's 2025 "
                    "notice also had a failed report filed within 5 days and passing reports within 20. 2026: five passed May 1; "
                    "the domestic RP failed May 5 (\"RV FAILED TO OPEN\") and its repair report is June 18. The City's "
                    "repair notice is dated June 2, was postmarked June 11, and was scanned July 3. NFPA 25's forward-flow "
                    "test is separate."),
    # Fire protection, researched 2026-09-29: HSC 13195 and 19 CCR 904 adopt NFPA 25 (California edition) for sprinklers;
    # the 2025 California Fire Code (901.6, 907.8) adopts NFPA 72-2025 for the alarm. Checked October 2, 2026: 19 CCR 904
    # as Cornell LII prints it adopts "NFPA 25 (2011 edition) ... (Published as NFPA 25, 2013 California Edition)"
    # (whether the State Fire Marshal has adopted a later edition is unverified); CFC 901.6 ("maintained in an operative
    # condition at all times") and Table 901.6.1 (NFPA 72 for fire alarms, NFPA 25 for water-based systems) as UpCodes
    # prints them. The frequencies inside NFPA 25 and NFPA 72 are the standards' own, not freely published: unverified
    # from their text here. The sprinkler and alarm rows count
    # from the last report on record, not from payments: Signal Service's quarterly payments are monitoring and the panel
    # lease, and The Fire Sprinkler Company's payments since 2024 are repairs (their invoices say so).
    Obligation("Fire alarm inspection and test", "Cal. Fire Code 907.8 (NFPA 72-2025, ch. 14): waterflow and tamper switches and "
               "batteries semiannually; initiating and notification devices, the panel, and the communicator yearly",
               every_months=6, done_on=date(2026, 3, 11), applies=FIRE_ALARM_SYSTEM,
               note="The last reports are Signal Service's of March 11, 2026 (buildings 3 and 8), which the vendor's public "
                    "report portal lists and the association never received by email (jason vendors --reports found them on "
                    "October 4, 2026; they are in the library and in Drive). Neither lists a failed device. Building 3's says "
                    "\"WF and tampers tested okay\"; building 8's adds \"2x 12v 12ah batts need to be replaced upon next "
                    "inspection\". Six devices in building 3 and nine in building 8 are marked Not Tested, the in-unit smoke "
                    "detectors as in September 2025: a question of access. The September 19, 2025 reports had building 3's "
                    "waterflow alarm failing, and The Fire Sprinkler Company's $995 invoice of December 15, 2025 was to "
                    "\"investigate water flow switch issue\" (the association's email of December 10 said \"the issue isn't "
                    "solved quite yet\"); the March 2026 comment is the first record that it passes, and a person reads the "
                    "report for the waterflow device's own result. Signal bills the semi-annual inspection with the quarterly "
                    "monitoring (systems P320-4785, building 3, and P320-4786, building 8); no report since March 2026 is on "
                    "file, so the next was due about September 11, 2026. The master policy's P-1 protective safeguard "
                    "(CP 04 11, buildings 1-8) includes the sprinklers' supervisory services, so these reports are its evidence "
                    "too: mystique/notes/fire-protection-records.md."),
    Obligation("Fire sprinkler quarterly inspection", "19 CCR 904 (NFPA 25, California edition), form AES 2.1: control valves, "
               "gauges, waterflow and supervisory devices, the fire department connection, and the backflow preventer",
               every_months=3, applies=NFPA_25_SPRINKLERS,
               note="No quarterly record is on file. 19 CCR 904.1(a) as the State Fire Marshal adopted it (2014 text): \"A "
                    "license shall not be required to perform inspections. Inspections may be conducted by ... an employee "
                    "designated by the building owner or occupant who has developed competence through training and "
                    "experience\"; a business inspecting for a fee needs an SFM A or C-16 license. The association has no "
                    "employees, so whether a trained director or the manager qualifies is a question for the fire authority "
                    "or counsel. NFPA 25 Table 5.1.1.2 (California amendment) puts waterflow alarm and valve supervisory "
                    "devices, wet-system gauges, and spare sprinklers at quarterly inspection."),
    Obligation("Fire sprinkler annual inspection and test", "19 CCR 904 (NFPA 25, California edition), form AES 2.1: sprinklers, "
               "piping, main drain, waterflow alarm, control valve operation, backflow forward flow",
               every_years=1, done_on=date(2023, 3, 14), applies=NFPA_25_SPRINKLERS,
               note="The last documented annual inspection is March 14, 2023 (buildings 3 and 8, on the prior manager's April 2023 "
                    "statement). A licensed (State Fire Marshal A or C-16) firm must do it; records are kept five years. PayHOA's "
                    "payments from January 2024 bound it: The Fire Sprinkler Company quoted the annual at $895 a riser (two "
                    "risers), the quarterly at $350, and the five-year at $1,000 on March 25, 2024, and every payment to it since "
                    "is a repair ($4,245 February 2024; a bell, $1,249.12, September 2024; building 8's OS&Y, $1,245.22, June "
                    "2025; a sprinkler head, $1,150, September 2025; investigating the waterflow switch, $995, December 2025). "
                    "The board signed The Fire Sprinkler Company's 2024 proposal on April 17, 2024 with annual and quarterly "
                    "inspections marked; no inspection followed, and the company's June 18, 2025 email offering to schedule the July "
                    "annual has no reply. Buildings 1, 2, and 4-7 are NFPA 13D systems (the board's July 2022 reading: no NFPA 25 "
                    "inspection) and have no inspection record. The master policy "
                    "makes the sprinklers a P-1 protective safeguard for buildings 1-8 (CP 04 11): no fire coverage if a "
                    "known impairment was not reported or the system was not kept in working order "
                    "(mystique/notes/fire-protection-records.md). 19 CCR 904.2(j): \"It is the responsibility of the "
                    "contractor, company, or licensee to provide a written report of the test and maintenance results to the "
                    "building owner and the local fire authority having jurisdiction\"; 904.2(c): records are kept \"on the "
                    "premises ... for a period of five years after the next required test or maintenance\"; 904.2(d): a tag "
                    "goes on \"only after all deficiencies have been corrected\" (the 2022 job walk found no tags on the risers)."),
    # NFPA 25 Table 5.1.1.2 as California amended it (the State Fire Marshal's 2014 text): wet-system gauges replaced or
    # tested every 5 years; fast-response sprinklers sample-tested at 20 years and every 10 years after. Read October 4,
    # 2026 from the OSFM's published final text; the standard's own text is not on disk.
    Obligation("Fire sprinkler gauges replaced or tested", "NFPA 25 5.3.2 (California edition, Table 5.1.1.2): every 5 years",
               every_years=5, first_due=date(2023, 3, 14), applies=NFPA_25_SPRINKLERS,
               note="The March 2023 annual report found both risers' gauges \"dated 2006\" and its correction quotation listed "
                    "replacing them; the June 2023 repairs (invoice 1674, $10,974.24) are not itemized, so whether they were "
                    "replaced is unconfirmed. Ask The Fire Sprinkler Company; the next annual report should show the gauge dates."),
    Obligation("Fire sprinkler sample test (fast-response, 20 years)", "NFPA 25 5.3.1.1.1.3 (California edition, Table "
               "5.1.1.2): fast-response sprinklers at 20 years and every 10 years after, by a lab, a sample of each kind",
               every_years=10, first_due=date(2027, 11, 15), applies=NFPA_25_SPRINKLERS,
               note="Counted from installation, which is not on file: building 8 was conveyed from November 2007 and building 3 "
                    "from February 2008, so about late 2027 and early 2028. That residential sprinklers are fast-response is a "
                    "reading; the system's records or the heads' markings confirm it. The test is the annual inspector's to "
                    "schedule (AES 2.1 item 2.1, \"Field Service Test Required\")."),
    Obligation("Fire sprinkler five-year internal inspection", "19 CCR 904, 906.4 (NFPA 25), form AES 2.2, filed with the fire authority",
               every_years=5, applies=NFPA_25_SPRINKLERS,
               note="Internal inspection of valves and piping, and gauges replaced or tested; no record is on file. The Fire "
                    "Sprinkler Company's November 7, 2022 \"Five Year Inspection Correction Quotation\" followed a job walk, "
                    "not an AES 2.2 inspection; the 2023 and 2024 proposals priced the five-year and neither was ordered."),
    # California Deck Inspection's SB 326 report (Drive "My Drive/Reports/Mystique Community SB 326 Report.pdf", id
    # 1Qodo170LjfNzaxeSxb2b2Iv85z8k_1ES): all 24 elevated elements examined November 8, 2023, signed and stamped by the
    # architect November 17, 2023; the next inspection is due "Nine years from the date of this report". The $4,800
    # invoice for it was paid from reserves March 14, 2024; that payment is not the inspection's date.
    # What 5551 reaches is the section's own condition (ELEVATED_ELEMENTS_INSPECTION): a condominium project, elevated
    # elements the association maintains or repairs, and a building of three or more attached units. The profile does
    # not state those three facts as data (applicability_facts()), so jason applies leaves the row undetermined and
    # asks each one; the report on file is evidence for a person's answer, not a fact jason infers.
    Obligation("Exterior elevated elements (balconies) inspection", "Civil Code 5551: first by January 1, 2025, then every nine years",
               every_years=9, first_due=date(2025, 1, 1), done_on=date(2023, 11, 17), payee_words=("CALIFORNIA DECK INSPECTION",),
               applies=ELEVATED_ELEMENTS_INSPECTION,
               note="Counted from the report's date (November 17, 2023); the report must be kept for two inspection cycles."),
    Obligation("Annual budget report and policy statement", "Civil Code 5300, 5310: 30 to 90 days before the fiscal year ends",
               month=12, day=1, window_days=60,
               note="Distributed by mail or email; no store jason keeps shows it."),
    Obligation("Reviewed financial statement", "Civil Code 5305: within 120 days after the fiscal year closes (gross income over $75,000)",
               month=4, day=30, window_days=120,
               note="The CPA's review report; no store jason keeps shows it yet."),
)
