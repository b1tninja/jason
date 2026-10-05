"""The invoice, utility bill, and tax return models over synthetic excerpts in the real layouts.

Names, numbers, and addresses here are made up; the layouts (line order, labels) are the vendors' own.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.base import BuildingRange, Policy
from jason.community.document_models import ModelContext, read
from jason.community.invoice_formats import INVOICE_FORMATS
from jason.community.invoices import read_invoice
from jason.community.models.invoices import bill_to, line_items, loose_date
from jason.community.sources import Sender, SourceKind
from jason.community.symbols import Building, DocumentKind, Parity, PolicyKind, Street, Utility
from jason.community.utility import UtilityAccount

TODAY = date(2026, 9, 29)


class Spec:
    name = "Mystique Community Association"

    def index_association(self) -> str:
        return "MYSTIQUE COMMUNITY"

    def name_pattern(self) -> str:
        # The name word a vendor's layout prints for the property (E&R's "<name> Condos"): the profile's, not the row's.
        return "myst[il1]que"

    def senders(self):
        return (Sender("Example Plumbing Co", SourceKind.VENDOR, ("EXAMPLE PLUMBING",), payhoa_vendor="Example Plumbing Co"),)

    def vendor_portals(self):
        return ()

    def utility_accounts(self):
        return (UtilityAccount(Utility.SMUD, "1234567", "Building 9 house meter"),
                UtilityAccount(Utility.CITY_OF_SACRAMENTO, "9876543210", "Common area"))

    def insurance(self):
        return SimpleNamespace(policies=(Policy(PolicyKind.FLOOD, "5010000001", building=Building.BLDG_1),))

    def buildings(self):
        return (BuildingRange(Building.BLDG_1, Street.MACON_DR, 9000, 9050, Parity.ANY),)


def ctx() -> ModelContext:
    return ModelContext(community=Spec(), today=TODAY)


def invoice(text: str):
    reading = read(DocumentKind.INVOICE, text, ctx())
    assert reading is not None
    return reading


def codes(reading) -> set[str]:
    return {f.code for f in reading.findings}


# QuickBooks Desktop's printed invoice (LeDoux Backflow's layout): Total, Balance Due, Payments/Credits at the end.
QUICKBOOKS = """Invoice
Date
6/23/2026
Invoice #
29766
Bill To
Mystique Community Association
attn: Pat Example
100 Example St, Ste 1
Sacramento, CA 95814
LeDoux Backflow Testing Services, Inc
PO Box 1
Orangevale, CA 95662
P.O. No.
Terms
Due on receipt
Total
Balance Due
Payments/Credits
PLEASE REFERENCE INVOICE NUMBER ON CHECK.
Description
Qty
Rate
Amount
Service Date: 06-23-26
1
425.00
425.00
Check Rubber Repair Kit
1
230.91
230.91
Sacramento County Tag Fee
1
36.00
36.00
LABOR & REPAIR SERVICES
1
$691.91
$691.91
$0.00
"""


def test_quickbooks_layout_total_is_the_first_of_the_closing_run() -> None:
    reading = invoice(QUICKBOOKS)
    r = reading.record
    assert (r.vendor, r.number, r.invoice_date, r.total_cents) == ("LeDoux Backflow Testing Services", "29766", date(2026, 6, 23), 69191)
    assert r.method == "format:LeDoux Backflow Testing Services"
    assert [i.amount_cents for i in r.line_items] == [42500, 23091, 3600]  # the closing "1 / $691.91" run is not an item
    assert reading.complete
    assert "line-items-differ" not in codes(reading) and "billed-to-other" not in codes(reading)
    assert "enhanced-association-record" in codes(reading)


def test_line_items_that_do_not_add_up_are_a_finding() -> None:
    short = QUICKBOOKS.replace("$691.91\n$691.91", "$791.91\n$791.91").replace("Total\nBalance Due", "Subtotal\n$791.91\nBalance Due")
    reading = invoice(short)
    assert reading.record.total_cents == 79191
    assert "line-items-differ" in codes(reading)


def test_an_ocr_misread_row_suppresses_the_sum_check() -> None:
    misread = QUICKBOOKS.replace("1\n230.91\n230.91", "1\n280.91\n230.91").replace("$691.91\n$691.91", "$791.91\n$791.91")
    reading = invoice(misread)
    assert reading.record.line_items_partial and "line-items-differ" not in codes(reading)


E_AND_R = """E.R
04-28-2026
Extra Work 2026
42726
Sacramento
Trimming (43) trees
Rowmeeka Example
Mystique Condos Properties
Sacramento, CA 95835
1-Trimming clearance (43) trees,,,,,,,,,,,,,$2,365.
2- Remove (2) dead trees,,,,,,,,,,$800.
3-Restake (5) trees,,,,,,,,,$200.
3,365.
"""


def test_e_and_r_number_and_total_are_whole_lines() -> None:
    r = invoice(E_AND_R).record
    assert (r.vendor, r.number, r.invoice_date, r.total_cents) == ("E&R Landscaping", "42726", date(2026, 4, 28), 336500)


FLOOD_RENEWAL = """See reverse of this notice for important additional information
Coverage Options
Coverage Amounts
Deductibles
Premium
A. Current coverage
B. Increased coverage
Building
Contents
Building
Contents
2,500,000.00
N/A
N/A
N/A
2,000.00
N/A
N/A
N/A
1,402.00
N/A
9001-9049 MACON DR
SACRAMENTO, CA 95835
RENEWAL NOTICE
5010000001
Policy Expiration Date :
Notice Date :
Policy Number :
11/20/2026 12:01 am
Your flood insurance policy will expire 11/20/2026. Renewal
premium is required to renew your policy.
09/12/2026
Option B
$
$1,402
12345678-123456789
Amount Enclosed:
Renewal Date :
5010000001
Insured Name :
Mystique Community Association
Make check or money order payable to :
PHILADELPHIA INDEMNITY INSURANCE COMPANY
"""


def test_flood_renewal_notice_reads_policy_premium_and_building() -> None:
    reading = invoice(FLOOD_RENEWAL)
    assert reading.model == "flood-premium-notice"
    r = reading.record
    assert r.number == "12345678-123456789" and r.policy_number == "5010000001"
    assert (r.invoice_date, r.expiration_date) == (date(2026, 9, 12), date(2026, 11, 20))
    assert (r.building_coverage_cents, r.deductible_cents, r.premium_cents, r.total_cents) == (250000000, 200000, 140200, 140200)
    assert r.property_location == "9001-9049 MACON DR" and r.building is Building.BLDG_1
    assert reading.complete
    assert "flood-renewal-due" in codes(reading) and "unknown-flood-policy" not in codes(reading)


def test_flood_notice_for_a_policy_the_specification_lacks() -> None:
    reading = invoice(FLOOD_RENEWAL.replace("5010000001", "5010000999"))
    assert "unknown-flood-policy" in codes(reading)


FLOOD_RECEIPT = """Insured Information
Policy Number
MYSTIQUE COMMUNITY ASSOCIATION
5010000001
Payor Information
Date
Receipt Number
MYSTIQUE COMMUNITY ASSOC
2/6/2025 5:52:24 PM
035220
Activity
Account Number
Amount
Total:
Credit Card
$1424.00
$1424.00
Renewal
Payment:
Please retain this receipt for your records.
"""

FARMERS = """Payor Name & Address
MONTHLY BILLING STATEMENT
Business Insurance
March 11, 2024
Billing Summary
Account Number:
F000000000-001-00001
Your Farmers Agent
$2,815.08*
March 28, 2024
Payment Stub
Amount Due:
Due Date:
Do Not Pay. You are enrolled in an automatic
pay plan. The total amount due will be withdrawn on the
due date.
$2,815.08
March 28, 2024
Payor Name:  COMMUNITY, MYSTIQUE
FARMERS INSURANCE EXCHANGE
"""

LABARRE = """Invoice # 72591
Page:
1 of 1
   Account Number
   Date
MYSTCOM-01
9/27/2024
   Balance Due On
9/28/2024
Mystique Community Association
Item #
Description
Amount
326,195
9/28/2024
NEWB
$1,292.95
Billing / D&O / 24-25
$1,292.95
Total Invoice Balance:
Pay By Check
Payable to LaBarre/Oksnee Insurance Agency, LLC
"""

ARDEN = """Installment # 3 of 8 - Property
$2,014.42
Installment # 3 of 8 - General Liability
$266.79
$2,281.21
TOTAL AMOUNT DUE
Date:
September 28, 2025
INVOICE #:
Mystique Community Association
PREMIUM SUMMARY
INVOICE
171263
Due Date: 12/28/2025
ARDEN INSURANCE SERVICES LLC PO BOX 1
"""

SIGNAL_MAILED = """Signal Seivice Inc
Invoice Number
Date
( (Signal Stwice)
))
Angels Camp, CA 95222
404603
06/16/2025
Customer Number
Due Date
15520
07/01/2025
Customer Name
Mystique Community Association
Quantity
Description
Rate
Amount
3.00
Basic Monitoring Service
36.00
108.00
Invoice Balance Due:
$108.00
"""

AMAZON = """Order Summary
Order placed March 6, 2026
 Order # 113-0000000-0000000
Ship to
Pat Example
Item(s) Subtotal:
$86.98
Total before tax:
$82.63
Grand Total:
$89.86
Conditions of Use
(c) 1996-2026, Amazon.com, Inc. or its affiliates
"""

ZOOM = """Invoice
Zoom Communications, Inc.
Invoice Date:
Invoice #:
Payment Terms:
Due Date:
Account Number:
Currency:
Payment Method:
Account Information:
Sold To Address:
Bill To Address:
Dec 30, 2025
INV335777570
Due Upon Receipt
Dec 30, 2025
1234567890
USD
Mystique Community Association
Charge Details
Subtotal
$147.84
Total (Including Taxes, Fees & Surcharges)
$158.19
Invoice Balance
$0.00
"""

ADOBE = """Bill To
Mystique Community Association
INVOICE
Invoice Information
3404950848
Invoice Number
23-MAR-2026
Invoice Date
Adobe Inc.
345 Park Avenue
GRAND TOTAL (USD)
19.99
"""

TWILIO = """Twilio, Inc.
RECEIPT
Mystique Community Association
Date
Description
Payment Method
Amount
08 May, 2024
API Services
$19.00
Total Paid
$19.00
"""

PAYHOA = """Invoice
Invoice number CCE0B6A5-0039
Date of issue
January 14, 2026
Date due
January 14, 2026
PayHOA, Inc
Bill to
Mystique Community Association
Total
$1,069.20
Amount due
$1,069.20 USD
"""

NEWMAN = """Newman Certified Public Accountant, PC
Invoice
BILL TO
Mystique Community
Association
INVOICE #
DATE
TOTAL DUE
TERMS
ENCLOSED
41903
11/13/2024
$1,600.00
Due on receipt
BALANCE DUE
$1,600.00
"""

GOODLIFE_JOIST = """1 of 1
Deposit 4514-2
Invoice Date
Payment Due
Good Life Construction
PREPARED FOR
Mystique Community Association
Stucco Repairs
TOTAL
$996.80
A deposit is required to secure scheduling.
December 16, 2025
January 15, 2026
DESCRIPTION
"""

POSTSCANMAIL = """Invoice#
136226868
Date:
12/16/2025
Bill to:
Mystique Community Association
Mailbox Address
Item Description
Price
Mail Shredding
$10.00
Current Charges
$10.00
Total Paid | Card
$10.00
"""


@pytest.mark.parametrize("text, vendor, number, day, total", [
    (FLOOD_RECEIPT, "Philadelphia Indemnity Insurance Company", "035220", date(2025, 2, 6), 142400),
    (FARMERS, "Farmers Insurance", "", date(2024, 3, 11), 281508),
    (LABARRE, "LaBarre/Oksnee Insurance Agency, LLC", "72591", date(2024, 9, 27), 129295),
    (ARDEN, "Arden Insurance Services", "171263", date(2025, 9, 28), 228121),
    (SIGNAL_MAILED, "Signal Service Inc", "404603", date(2025, 6, 16), 10800),
    (AMAZON, "Amazon", "113-0000000-0000000", date(2026, 3, 6), 8986),
    (ZOOM, "Zoom", "INV335777570", date(2025, 12, 30), 15819),
    (ADOBE, "Adobe", "3404950848", date(2026, 3, 23), 1999),
    (TWILIO, "Twilio", "", date(2024, 5, 8), 1900),
    (PAYHOA, "PayHOA", "CCE0B6A5-0039", date(2026, 1, 14), 106920),
    (NEWMAN, "Newman Certified Public Accountant, PC", "41903", date(2024, 11, 13), 160000),
    (GOODLIFE_JOIST, "GoodLife Construction Inc.", "4514-2", date(2025, 12, 16), 99680),
    (POSTSCANMAIL, "Post Scan Mail", "136226868", date(2025, 12, 16), 1000),
])
def test_vendor_layouts(text: str, vendor: str, number: str, day: date, total: int) -> None:
    r = invoice(text).record
    assert (r.vendor, r.number, r.invoice_date, r.total_cents) == (vendor, number, day, total)
    assert r.method.startswith("format:")


def test_rows_serve_jason_invoices_too() -> None:
    """The review reads with read_invoice and the rows, and parse_date reads Adobe's "23-MAR-2026"."""
    inv = read_invoice(LABARRE, formats=INVOICE_FORMATS)
    assert (inv.number, inv.invoice_date, inv.due_date, inv.total_cents) == ("72591", date(2024, 9, 27), date(2024, 9, 28), 129295)
    assert read_invoice(ADOBE, formats=INVOICE_FORMATS).invoice_date == date(2026, 3, 23)


def test_statement_without_a_number_is_flagged_missing() -> None:
    reading = invoice(FARMERS)
    assert reading.missing == ("number",) and "missing-number" in codes(reading)


def test_billed_to_a_person_and_association_not_named() -> None:
    billed = invoice(QUICKBOOKS.replace("Bill To\nMystique Community Association", "Bill To\nPat Example"))
    assert "billed-to-other" in codes(billed)
    assert "association-not-named" in codes(invoice(AMAZON))


def test_due_dates() -> None:
    unpaid = invoice(ARDEN)  # due 12/28/2025, no amount paid shown
    assert "due-date-passed" in codes(unpaid)
    assert "due-date-passed" not in codes(invoice(POSTSCANMAIL.replace("Date:\n", "Due date: 01/05/2026\nDate:\n")))  # "Total Paid"
    backwards = invoice(ARDEN.replace("Due Date: 12/28/2025", "Due Date: 08/28/2025"))
    assert "due-before-issued" in codes(backwards)


def test_a_letter_is_not_an_invoice() -> None:
    assert read(DocumentKind.INVOICE, "Dear members,\nThe pool opens in May.\nThe board thanks you.\n" * 3, ctx()) is None


def test_helpers() -> None:
    assert loose_date("23-MAR-2026") == date(2026, 3, 23)
    assert loose_date("08 May, 2024") == date(2024, 5, 8)
    assert loose_date("Jul 16,2024") == date(2024, 7, 16)
    assert bill_to("Customer\nWO Number\nMystique HOA\n") == "Mystique HOA"
    assert line_items("Widget\n2\n10.00\n20.00\nCredit\n1\n($5.00)\n($5.00)\n")[1].amount_cents == -500


# Utility bills: the SMUD and City layouts the existing readers parse (account numbers made up).

SMUD = """Your Electric Bill
Account Number: 1234567
Bill Issue Date: 01/28/26
Location: 9000 MACON DR BLDG 9
PUMP UNIT 0
Bill Period: 12/09/25 - 01/08/26 (31 Days)
Rate: C&I TOD Secondary 0-20 kW
Total Amount Due:
${due}
Meter Summary
Meter
Usage
Type
7654321
1,580
kWh
Electricity Charges
Item
Usage
Type
Rate
Amount
Electricity Usage
693
Non-Summer Off Peak kWh @
0.137700
95.43
System Infrastructure Fixed Charge*
29.90
Sacramento City Tax*
3.67
A) TOTAL ELECTRIC SERVICE CHARGES/CREDITS
$129.00
"""

CITY = """City of Sacramento
Utility Service Bill
February 02, 2026
MYSTIQUE COMMUNITY ASSOCIATION
Current Charges
0 EXAMPLE LN
{account}
$5.04
$11.04
Service Address:
0 EXAMPLE LN - Common Area
000-0000-000-0000
Service from 1/3/26 - 2/2/26
Storm Drainage - 1996 Fee
8.79
Flat charge for 4,558 sq ft parcel
Storm Drainage - 2022 Fee
2.25
Storm Drainage Property Related Fee - Common Area
Subtotal
$11.04
Current Charges - Due 2/23/26
$11.04
"""


def utility(text: str):
    reading = read(DocumentKind.UTILITY_BILL, text, ctx())
    assert reading is not None
    return reading


def test_smud_bill_reconciles_and_names_its_account() -> None:
    reading = utility(SMUD.format(due="129.00"))
    r = reading.record
    assert (r.provider, r.account, r.account_label) == (Utility.SMUD, "1234567", "Building 9 house meter")
    assert (r.bill_date, r.period_start, r.period_end) == (date(2026, 1, 28), date(2025, 12, 9), date(2026, 1, 8))
    assert (r.current_charges_cents, r.charged_cents, r.amount_due_cents) == (12900, 12900, 12900)
    assert reading.complete and reading.findings == ()


def test_smud_previous_balance_and_charges_that_do_not_add() -> None:
    carried = utility(SMUD.format(due="258.00"))
    assert "previous-balance" in codes(carried)
    off = utility(SMUD.format(due="139.00").replace("$129.00", "$139.00"))
    assert {"charges-differ"} <= codes(off)


def test_city_bill_credit_and_unknown_account() -> None:
    reading = utility(CITY.format(account="9876543210"))
    assert reading.record.by_service == {"storm_drainage": 1104}
    assert "credit-applied" in codes(reading) and "unknown-account" not in codes(reading)
    assert "unknown-account" in codes(utility(CITY.format(account="1111111111")))


def test_an_invoice_is_not_a_utility_bill() -> None:
    assert read(DocumentKind.UTILITY_BILL, QUICKBOOKS, ctx()) is None


TAX_LETTER = """September 26, 2025
CONFIDENTIAL
Mystique Community Association
Dear Client:
We have prepared the following 2024 return(s) for the year ended December 31, 2024 from the
information provided to us:
Sincerely,
Chris Example, CPA
Example Accountancy, PC
Enclosures
U.S. Income Tax Return for Homeowners Associations (Form 1120-H)
California Exempt Organization Annual Information Return (Homeowner's Association Form 199)
Federal Filing Instructions
Your 2024 Form 1120-H shows a balance due of $120, which should be paid by October 15, 2026.
An authorized board member of the corporation should sign and date the return and mail by
October 15, 2026 to:
California Filing Instructions - Form 199
Your 2024 Form 199 shows no balance due.
Form 8453-EO should be signed and dated by an authorized board member.
"""


def test_tax_return_letter() -> None:
    reading = read(DocumentKind.TAX_RETURN, TAX_LETTER, ctx())
    assert reading is not None and reading.complete
    r = reading.record
    assert r.tax_year == 2024 and r.preparer == "Example Accountancy, PC" and r.letter_date == date(2025, 9, 26)
    assert r.forms[:2] == ("1120-H", "199") and "8453-EO" in r.signature_forms
    assert [(x.form, x.result, x.amount_cents) for x in r.results] == [("1120-H", "balance due", 12000), ("199", "no balance due", None)]
    assert r.deadlines == (date(2026, 10, 15),)
    assert {"tax-return-record", "signature-not-in-text", "tax-due", "tax-deadline"} <= codes(reading)
