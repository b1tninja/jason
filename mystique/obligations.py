"""Mystique's recurring deadlines, each with its authority and the PayHOA evidence that shows it done.

The fiscal year is the calendar year (the reserve studies are by fiscal year, FY26 starting January 2026). The PayHOA
categories are the ones the association books these payments to (read September 29, 2026). Insurance renewals come
from ``insurance.py`` and the reserve study's site visit from the studies on disk, not from rows here.
"""

from __future__ import annotations

from datetime import date

from jason.community.obligations import Obligation

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
    Obligation("Statement of information and SI-CID", "Corp. Code 8210; Civil Code 5405: every two years",
               every_years=2, categories=("Secretary of State",),
               note="Filed in the period set by the month of incorporation."),
    Obligation("Backflow assembly test", "State Water Board Cross-Connection Control Policy Handbook and the City of Sacramento's "
               "annual test notice: each assembly tested yearly by a certified tester",
               every_years=1, categories=("Backflow Prevention",), payee_words=("LEDOUX", "LE DOUX"),
               note="LeDoux tests the six assemblies (June 2024, June 2025, May 2026). NFPA 25's forward-flow test is separate."),
    # Fire protection, researched 2026-09-29: HSC 13195 and 19 CCR 904 adopt NFPA 25 (California edition) for sprinklers;
    # the 2025 California Fire Code (901.6, 907.8) adopts NFPA 72-2025 for the alarm. The sprinkler and alarm rows count
    # from the last report on record, not from payments: Signal Service's quarterly payments are monitoring and the panel
    # lease, and The Fire Sprinkler Company's payments since 2024 are repairs (their invoices say so).
    Obligation("Fire alarm inspection and test", "Cal. Fire Code 907.8 (NFPA 72-2025, ch. 14): waterflow and tamper switches and "
               "batteries semiannually; initiating and notification devices, the panel, and the communicator yearly",
               every_months=6, done_on=date(2025, 9, 19),
               note="Signal Service's reports of September 19, 2025 (buildings 3 and 8) are the last in the library; building 3's "
                    "waterflow switch failed, two in-unit detectors were not tested, and the batteries (2021, 2022) are past "
                    "their three-year replacement. Its quarterly invoices (systems P320-4785, building 3, and P320-4786, building 8) "
                    "bill monitoring and the semi-annual inspection in advance, paid without a gap from February 2024; the visits "
                    "in the email are March 2025, September 19, 2025, January 28, 2026 (building 3), and an OS&Y tamper test in "
                    "August 2026, with no report since September 2025."),
    Obligation("Fire sprinkler quarterly inspection", "19 CCR 904 (NFPA 25, California edition), form AES 2.1: control valves, "
               "gauges, waterflow and supervisory devices, the fire department connection, and the backflow preventer",
               every_months=3,
               note="A trained employee of the owner may do the quarterly inspection (19 CCR 904.1); no quarterly record is on file."),
    Obligation("Fire sprinkler annual inspection and test", "19 CCR 904 (NFPA 25, California edition), form AES 2.1: sprinklers, "
               "piping, main drain, waterflow alarm, control valve operation, backflow forward flow",
               every_years=1, done_on=date(2023, 3, 14),
               note="The last documented annual inspection is March 14, 2023 (buildings 3 and 8, on the prior manager's April 2023 "
                    "statement). A licensed (State Fire Marshal A or C-16) firm must do it; records are kept five years. PayHOA's "
                    "payments from January 2024 bound it: The Fire Sprinkler Company quoted the annual at $895 a riser (two "
                    "risers), the quarterly at $350, and the five-year at $1,000 on March 25, 2024, and every payment to it since "
                    "is a repair ($4,245 February 2024; a bell, $1,249.12, September 2024; building 8's OS&Y, $1,245.22, June "
                    "2025; a sprinkler head, $1,150, September 2025; a flow switch, $995, December 2025)."),
    Obligation("Fire sprinkler five-year internal inspection", "19 CCR 904, 906.4 (NFPA 25), form AES 2.2, filed with the fire authority",
               every_years=5,
               note="Internal inspection of valves and piping, and gauges replaced or tested; no record is on file."),
    # California Deck Inspection's SB 326 report (Drive "My Drive/Reports/Mystique Community SB 326 Report.pdf", id
    # 1Qodo170LjfNzaxeSxb2b2Iv85z8k_1ES): all 24 elevated elements examined November 8, 2023, signed and stamped by the
    # architect November 17, 2023; the next inspection is due "Nine years from the date of this report". The $4,800
    # invoice for it was paid from reserves March 14, 2024; that payment is not the inspection's date.
    Obligation("Exterior elevated elements (balconies) inspection", "Civil Code 5551: first by January 1, 2025, then every nine years",
               every_years=9, first_due=date(2025, 1, 1), done_on=date(2023, 11, 17), payee_words=("CALIFORNIA DECK INSPECTION",),
               note="Counted from the report's date (November 17, 2023); the report must be kept for two inspection cycles."),
    Obligation("Annual budget report and policy statement", "Civil Code 5300, 5310: 30 to 90 days before the fiscal year ends",
               month=12, day=1, window_days=60,
               note="Distributed by mail or email; no store jason keeps shows it."),
    Obligation("Reviewed financial statement", "Civil Code 5305: within 120 days after the fiscal year closes (gross income over $75,000)",
               month=4, day=30, window_days=120,
               note="The CPA's review report; no store jason keeps shows it yet."),
)
