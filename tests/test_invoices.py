"""The invoice reader, vendor formats, and the payment review's rules."""

from __future__ import annotations

from collections import Counter
from datetime import date

from jason.community.invoice_formats import INVOICE_FORMATS
from jason.community.invoices import money_values, names_vendor, parse_date, read_invoice, readable
from jason.tasks.invoice_review import Payment, needs_document, rare_category

PRO_ACTIVE = """Invoice
INVOICE NO.
ACCOUNT NUMBER
785584
47362
INVOICE DATE
02/06/2024
AMOUNT DUE
$0.00
Subtotal
$250.00
Invoice
Total
$250.00
Amount
Paid
$250.00
Invoice #
785584
Pro Active Pest
Control
"""

AWS = """Amazon Web Services, Inc. Invoice
Invoice Number:
2801513957
Invoice Date:
September 1 , 2026
TOTAL AMOUNT DUE ON September 1 , 2026
USD 1.49
"""

E_AND_R = """E.R
Monthly Landscaping service of August 2026.
08-31-2026
80126
Sacramento
August 2026 service invoice
2,832.
"""
# The format names its customer line by a phrase; the fixture takes it from the format rather than repeating a person's name.
E_AND_R += " ".join(p for p in next(f for f in INVOICE_FORMATS if f.vendor == "E&R Landscaping").phrases if p != "E.R") + " Example & Board\n"


def test_a_paid_invoice_reads_its_total_not_its_zero_amount_due() -> None:
    inv = read_invoice(PRO_ACTIVE)
    assert inv.number == "785584" and inv.invoice_date == date(2024, 2, 6) and inv.total_cents == 25000
    assert inv.shows(25000) and not inv.shows(9900)


def test_aws_dates_with_a_spaced_comma_and_usd_amounts() -> None:
    inv = read_invoice(AWS)
    assert inv.number == "2801513957" and inv.invoice_date == date(2026, 9, 1) and inv.total_cents == 149


def test_a_vendor_format_reads_what_the_general_reader_cannot() -> None:
    inv = read_invoice(E_AND_R, formats=INVOICE_FORMATS)
    assert inv.method == "format:E&R Landscaping" and inv.vendor == "E&R Landscaping"
    assert inv.number == "80126" and inv.invoice_date == date(2026, 8, 31) and inv.total_cents == 283200


def test_amounts_dates_and_vendor_names() -> None:
    assert money_values("pay 2,750. now, 1,234.56 or $5.00; 2026.") == (275000, 123456, 500)
    assert parse_date("08-31-2026") == date(2026, 8, 31) and parse_date("Jul 10 2026") == date(2026, 7, 10)
    assert names_vendor("PRO ACTIVE PEST CONTROL PO Box 327", "Pro Active Pest Control")
    assert names_vendor("Thank you, Summit Roofing", "SUMMIT ROOFING COMPANY, INC.")
    assert not names_vendor("Landscaping services", "E&R Landscaping")


def test_a_glyph_coded_text_layer_is_not_readable() -> None:
    assert readable(PRO_ACTIVE)
    assert not readable("\x00\x01\x02\x03\x04 \x05\x06\x07\x08 \x0e\x0f abc")
    assert not readable("   ")


def _pay(payee: str, category: str, *, description: str = "", kind: str = "expense") -> Payment:
    return Payment(1, date(2026, 1, 1), 100, payee, description,
                   rows=[{"txId": 1, "amountCents": 100, "category": category, "categoryType": kind, "parentCategory": "",
                          "bank": 1, "excluded": False}])


def test_transfers_income_and_returns_need_no_document() -> None:
    assert needs_document(_pay("E&R Landscaping", "Landscaping"))
    assert not needs_document(_pay("", "Transfer to Reserves"))
    assert not needs_document(_pay("", "Dues", kind="income"))
    assert not needs_document(_pay("", "Landscaping", description="Credit Return: Online Payment 26502139784 To E&R"))
    assert not needs_document(_pay("", "", description="Online Transfer to CHK ...5286 transaction#: 1"))


def test_a_rare_category_is_flagged_and_a_vendor_that_bills_several_things_is_not() -> None:
    counts = {"Post Scan Mail": Counter({"Mail / Registered Agent": 27, "Postage": 1}),
              "PayHOA": Counter({"Fees": 142, "PayHOA": 20, "Postage": 19})}
    assert rare_category(_pay("Post Scan Mail", "Postage"), counts).startswith("category Postage; 27 of Post Scan Mail's")
    assert rare_category(_pay("PayHOA", "PayHOA"), counts) == ""
    assert rare_category(_pay("PayHOA", "Postage"), counts) == ""


def test_vendor_ledger_matching_settles_which_invoice_each_payment_paid() -> None:
    from types import SimpleNamespace

    from jason.community.invoices import Invoice
    from jason.tasks.invoice_review import Document, LedgerPayment, match_ledgers

    portal = SimpleNamespace(vendor="ProActive Pest Control", payhoa_words=("PRO ACTIVE PEST",))

    def pay(key: int, day: date, attached: str) -> Payment:
        p = Payment(key, day, 25000, "Pro Active Pest Control", "ORIG CO NAME:Pro Active Pest ORIG ID:1")
        p.documents = [Document(key, f"{attached}.pdf", "x", invoice=Invoice(number=attached))]
        return p

    ledger = [LedgerPayment(portal.vendor, date(2024, 3, 1), 25000, ("775388",)),
              LedgerPayment(portal.vendor, date(2024, 3, 2), 25000, ("785584",)),
              LedgerPayment(portal.vendor, date(2024, 3, 2), 25000, ("800175",))]
    # The second March 4 payment carries a copy of the March 3 invoice; its twin's attachment must not lose its record.
    pays = [pay(1, date(2024, 3, 3), "785584"), pay(2, date(2024, 3, 4), "785584"), pay(3, date(2024, 3, 4), "800175")]
    found = match_ledgers(pays, {"proactive": (portal, ledger)})
    assert {k: v[1].invoice_ids for k, v in found.items()} == {1: ("785584",), 3: ("800175",), 2: ("775388",)}
