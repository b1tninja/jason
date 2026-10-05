"""Vendor invoice layouts the general reader gets wrong, one ``InvoiceFormat`` row each.

A row is added when the reader scorecard (``jason invoices``) shows a vendor whose invoices
rarely yield their number, date, or amount. Order matters: the first row whose phrases all
appear wins. A field a row leaves out, or whose pattern finds nothing, is left to the general
reader. A document that carries no invoice number (a monthly statement, a card receipt) gets
no number pattern: an account or policy number repeats every month and would read as the same
invoice paid twice.
"""

from __future__ import annotations

from jason.community.invoices import InvoiceFormat

_MDY = r"(\d{1,2}/\d{1,2}/\d{4})"
_LONG = r"([A-Z][a-z]{2,8}\.? \d{1,2}, \d{4})"
_MONEY = r"(\$\s?[\d,]+\.\d\d)"

INVOICE_FORMATS: tuple[InvoiceFormat, ...] = (
    # FieldRoutes' printed invoice (ProActive Pest Control, "Pro Active North"): labels in one column, values in the
    # next, so "INVOICE NO." and "ACCOUNT NUMBER" precede the invoice number and the account; "Invoice Total" is the charge.
    InvoiceFormat(
        "ProActive Pest Control",
        ("INVOICE NO.", "ACCOUNT NUMBER", "Pro Active"),
        number=r"INVOICE NO\.\s*\n\s*ACCOUNT NUMBER\s*\n\s*(\d+)",
        invoice_date=r"INVOICE DATE\s*\n\s*(\d{1,2}/\d{1,2}/\d{4})",
        due_date=r"DUE DATE[^\n]*\n\s*(\d{1,2}/\d{1,2}/\d{4})",
        total=r"Invoice\s*\n\s*Total\s*\n\s*\$?([\d,]+\.\d\d)",
    ),
    # E&R Landscaping: a one-page form, "E.R" header, the customer line naming the property ("<the association> Condos",
    # on every invoice and proposal: the name word is the profile's, ``names_association`` the word after it), the
    # service month's last day as MM-DD-YYYY, a number on a line of its own made of a date's digits ("80126", "110725"),
    # and the amount on a line of its own with no cents ("2,832."). Line items print their own amounts inside the line
    # ("...,,,$850."), so only a whole line is the total.
    InvoiceFormat(
        "E&R Landscaping",
        ("E.R",),
        names_association="Condos",
        number=r"(?m)^[\s|]*(\d{5,6})\s*$",
        invoice_date=r"(\d{2}-\d{2}-\d{4})",
        total=r"(?m)^[\s$]*(\d{1,3},\d{3}\.(?:\d\d)?)\s*$",
    ),
    # Philadelphia Indemnity's NFIP flood renewal notice (phlyflood.manageflood.com). The text layer prints the labels
    # and the values in separate runs, so a label is rarely beside its value. The Bill ID ("30040342-232458492") is the
    # bill's own number (the policy number repeats every year); the notice date follows the expiry sentence; the premium
    # is the third figure of the coverage row (building coverage, deductible, premium).
    InvoiceFormat(
        "Philadelphia Indemnity Insurance Company",
        ("RENEWAL NOTICE", "PHILADELPHIA INDEMNITY", "Coverage Options"),
        number=r"\b(\d{8}-\d{9})\b",
        invoice_date=r"(?:renew your policy\.|Notice Date\s*:?)[\s:]*" + _MDY,
        due_date=r"Policy Expiration Date\s*:?[\s:]*" + _MDY,
        total=r"\n\s*\d{1,3}(?:,\d{3})+\.\d\d\s*\n(?:\s*N/A\s*\n)+\s*[\d,]+\.\d\d\s*\n(?:\s*N/A\s*\n)+\s*([\d,]+\.\d\d)",
    ),
    # Philadelphia's new-application invoice: the premium follows the title; the Billing ID is the bill's number.
    InvoiceFormat(
        "Philadelphia Indemnity Insurance Company",
        ("New Application Invoice", "PHILADELPHIA INDEMNITY"),
        number=r"Billing ID\s*:\s*0*(\d{6,})",
        total=r"New Application Invoice\s*\n\s*" + _MONEY,
    ),
    # The flood portal's payment receipt (manageflood.com): the date and time under "Receipt Number", then the method
    # and two amounts under "Total:"; the second is the total charged.
    InvoiceFormat(
        "Philadelphia Indemnity Insurance Company",
        ("Payor Information", "Receipt Number", "Please retain this receipt"),
        number=r"\d{1,2}:\d\d:\d\d [AP]M\s*\n\s*(\d{5,})\s*\n",
        invoice_date=r"Receipt Number\s*\n(?:[^\n]*\n){0,4}?\s*" + _MDY + r"\s+\d",
        total=r"Total:\s*\n[^\n$]+\n\s*\$?[\d,]+\.\d\d\s*\n\s*" + _MONEY,
    ),
    # Farmers Insurance's monthly billing statement (commercial billing, autopay): a statement of the billing account,
    # not an invoice, so it has no number of its own. The date is under "Business Insurance"; the payment stub prints
    # the amount due and the draft date under "due date.".
    InvoiceFormat(
        "Farmers Insurance",
        ("MONTHLY BILLING STATEMENT", "FARMERS"),
        invoice_date=r"Business Insurance\s*\n\s*" + _LONG,
        due_date=r"due date\.\s*\n\s*\$[\d,]+\.\d\d\s*\n\s*" + _LONG,
        total=r"due date\.\s*\n\s*" + _MONEY,
    ),
    # LaBarre/Oksnee Insurance Agency's invoice (Applied Epic): account and date under their labels, "Balance Due On",
    # and the total printed above "Total Invoice Balance:".
    InvoiceFormat(
        "LaBarre/Oksnee Insurance Agency, LLC",
        ("Total Invoice Balance", "LaBarre/Oksnee"),
        invoice_date=r"Account Number\s*\n\s*Date\s*\n\s*\S+\s*\n\s*" + _MDY,
        due_date=r"Balance Due On\s*\n\s*" + _MDY,
        total=_MONEY + r"\s*\n\s*Total Invoice Balance",
    ),
    # Arden Insurance Services (premium finance and installments, epaypolicy.com): the number under "INVOICE" and the
    # total above "TOTAL AMOUNT DUE".
    InvoiceFormat(
        "Arden Insurance Services",
        ("ARDEN INSURANCE", "TOTAL AMOUNT DUE"),
        number=r"\nINVOICE\s*\n\s*(\d{5,})",
        invoice_date=r"Date:\s*\n\s*" + _LONG,
        due_date=r"Due Date:\s*" + _MDY,
        total=_MONEY + r"\s*\n\s*TOTAL AMOUNT DUE",
    ),
    # CAIS (crime and fidelity policies): the invoice date, due date, amount, paid, and total in one row.
    InvoiceFormat(
        "CAIS",
        ("CAIS", "caislive.com"),
        number=r"Invoice Number:\s*(\d{5,})",
        invoice_date=r"Statement Date:\s*" + _MDY,
        due_date=r"Due Date:\s*" + _MDY,
        total=r"DUE DATE\s*\n\s*AMOUNT\s*\n\s*PAID\s*\n\s*TOTAL\s*\n(?:[^\n]*\n){0,6}?\s*\d{1,2}/\d{1,2}/\d{4}\s*\n\s*\d{1,2}/\d{1,2}/\d{4}"
              r"\s*\n\s*" + _MONEY,
    ),
    # Signal Service's mailed invoice (the envelope scan): "Invoice Number" and "Date" labels, the letterhead, then the
    # number and the date. Its emailed invoice labels each value ("Invoice Date:(12/17/2025"), which the general
    # reader misses when OCR prints a stray parenthesis.
    InvoiceFormat(
        "Signal Service Inc",
        ("Invoice Balance Due", "Customer Number", "Signal S"),
        number=r"Invoice Number\s*\n\s*Date\s*\n(?:[^\n]*\n){0,6}?\s*([A-Z]?-?\d{6})\s*\n\s*\d{1,2}/\d{1,2}/\d{4}",
        invoice_date=r"(?:Invoice Date:\s*\(?\s*|Invoice Number\s*\n\s*Date\s*\n(?:[^\n]*\n){0,6}?\s*[A-Z]?-?\d{6}\s*\n\s*)" + _MDY,
    ),
    # Amazon's order details page (a receipt): the order number is the document's number, "Order Placed" its date.
    InvoiceFormat(
        "Amazon",
        ("Amazon.com, Inc.",),
        number=r"Order\s*(?:#|number:?)\s*:?\s*\n?\s*(\d{3}-\d{7}-\d{7})",
        invoice_date=r"Order Placed:?\s*" + _LONG,
        total=r"Grand Total:\s*\n?\s*" + _MONEY,
    ),
    # Zoom's invoice: every label first, then every value; the number starts "INV", the date follows "Bill To Address:".
    InvoiceFormat(
        "Zoom",
        ("Zoom", "Charge Details", "Invoice Balance"),
        number=r"\b(INV\d{6,})\b",
        invoice_date=r"Bill To Address:\s*\n\s*" + _LONG,
        due_date=r"Bill To Address:\s*\n\s*[A-Z][a-z]{2} \d{1,2}, \d{4}\s*\n\s*\S+\s*\n[^\n]*\n\s*" + _LONG,
        total=r"Total \(Including Taxes, Fees & Surcharges\)\s*\n\s*" + _MONEY,
    ),
    # Adobe's invoice: each value above its label; the date as 23-MAR-2026.
    InvoiceFormat(
        "Adobe",
        ("Adobe Inc.", "Invoice Information"),
        number=r"(\d{8,})\s*\n\s*Invoice Number",
        invoice_date=r"(\d{1,2}-[A-Z]{3}-\d{4})\s*\n\s*Invoice Date",
        total=r"GRAND TOTAL \(USD\)\s*\n\s*([\d,]+\.\d\d)",
    ),
    # PayHOA's own invoice (Stripe): "Date of issue" and "Date due".
    InvoiceFormat(
        "PayHOA",
        ("PayHOA, Inc", "Date of issue"),
        number=r"Invoice number\s+([A-Z0-9]{6,}-\d{3,})",
        invoice_date=r"Date of issue\s*\n?\s*" + _LONG,
        due_date=r"Date due\s*\n?\s*" + _LONG,
        total=r"Amount due\s*\n\s*" + _MONEY,
    ),
    # Twilio's receipt: no invoice number (the account SID is not one); the payment date as "08 May, 2024".
    InvoiceFormat(
        "Twilio",
        ("Twilio, Inc.", "RECEIPT"),
        invoice_date=r"Amount\s*\n\s*(\d{1,2} [A-Z][a-z]{2,8},? \d{4})",
        total=r"Total Paid\s*\n\s*" + _MONEY,
    ),
    # Berding & Weil's statement: the date on its own line under the client's name; "TOTAL THIS INVOICE".
    InvoiceFormat(
        "Berding & Weil LLP",
        ("TOTAL THIS INVOICE", "Berding"),
        number=r"Invoice No\.\s*\n?\s*(\d{5,})",
        invoice_date=r"Association\s*\n\s*" + _LONG,
        total=r"TOTAL THIS INVOICE\s*\n?\s*" + _MONEY,
    ),
    # Newman CPA (QuickBooks Online): INVOICE #, DATE, TOTAL DUE, TERMS, ENCLOSED labels, then the values in order.
    InvoiceFormat(
        "Newman Certified Public Accountant, PC",
        ("Newman Certified Public Accountant", "TOTAL DUE"),
        number=r"INVOICE #\s*\n\s*DATE\s*\n\s*TOTAL DUE\s*\n(?:[A-Z ]+\n){0,3}?\s*(\d{3,})\s*\n",
        invoice_date=r"INVOICE #\s*\n\s*DATE\s*\n\s*TOTAL DUE\s*\n(?:[A-Z ]+\n){0,3}?\s*\d{3,}\s*\n\s*" + _MDY,
        total=r"BALANCE DUE\s*\n?\s*" + _MONEY,
    ),
    # QuickBooks Desktop's printed invoice ("Invoice / Date / Invoice #"), as LeDoux Backflow, California Builder
    # Services, GoodLife Construction, and The Fire Sprinkler Company print it: Total, Balance Due, and
    # Payments/Credits print their values in a run at the end of the page; the first of that run is the total.
    InvoiceFormat(
        "LeDoux Backflow Testing Services",
        ("LeDoux Backflow", "Invoice #"),
        total=r"(\$[\d,]+\.\d\d)(?:\s*\n\s*\$[\d,]+\.\d\d)+\s*\Z",
    ),
    InvoiceFormat(
        "California Builder Services",
        ("Tollhouse Rd", "Invoice #", "Contract Billed"),
        total=r"(\$[\d,]+\.\d\d)(?:\s*\n\s*\$[\d,]+\.\d\d)+\s*\Z",
    ),
    InvoiceFormat(
        "GoodLife Construction Inc.",
        ("GoodLife Construction Inc.", "Invoice #"),
        total=r"(\$[\d,]+\.\d\d)(?:\s*\n\s*\$[\d,]+\.\d\d)*\s*\Z",
    ),
    # Good Life's Joist-style billing ("Deposit 4514-2", "Progress Invoice 4514-3"): the number in the title, the
    # invoice and due dates printed together after the terms.
    InvoiceFormat(
        "GoodLife Construction Inc.",
        ("Good Life Construction", "PREPARED FOR"),
        number=r"(?:Deposit|Progress Invoice|Final Payment|Invoice)\s+(\d{3,6}-\d{1,3})\b",
        invoice_date=r"\n\s*" + _LONG + r"\s*\n\s*[A-Z][a-z]{2,8} \d{1,2}, \d{4}\s*\n",
        due_date=r"\n\s*[A-Z][a-z]{2,8} \d{1,2}, \d{4}\s*\n\s*" + _LONG + r"\s*\n",
        total=r"\bTOTAL\s*\n\s*" + _MONEY,
    ),
    # Good Life Restoration's Buildertrend invoice: "Invoice ID:", "Invoice date:", "Invoice amount:".
    InvoiceFormat(
        "GoodLife Construction Inc.",
        ("Good Life", "Invoice ID:"),
        number=r"Invoice ID:\s*(\d+)",
        invoice_date=r"Invoice date:\s*" + _LONG,
        due_date=r"Due date:\s*" + _LONG,
        total=r"Invoice amount:\s*" + _MONEY,
    ),
    # The Sacramento County Tax Collector's card receipt (Payment Express): a confirmation number and a posted date.
    InvoiceFormat(
        "Sacramento County Tax Collector",
        ("Payment Express", "Tax Collector"),
        number=r"Confirmation\s+([A-Z]\d{6,})",
        invoice_date=r"Posted Date:\s*" + _MDY,
        total=r"Total \(Payment\s*\+\s*Fee[})]?:\s*" + _MONEY,
    ),
    # PostScanMail's monthly invoice never prints the company's name; its "Mailbox Address" block does. The general
    # labels read the rest. Its PayPal receipt prints a receipt code, the amount and the date under their labels.
    InvoiceFormat("Post Scan Mail", ("Mailbox Address", "Bill to")),
    InvoiceFormat(
        "Post Scan Mail",
        ("Receipt From PostScan Mail",),
        number=r"Receipt #\s*(\w+)",
        invoice_date=r"Payment Method\s*\n\s*\$[\d,]+\.\d\d\s*\n\s*([A-Z][a-z]{2} \d{1,2}, ?\d{4})",
        total=r"Amount Charged\s*\n\s*" + _MONEY,
    ),
    # Aero-Lite Plastics (a Shopify order): "Order #", the order's date and time.
    InvoiceFormat(
        "Aero-Lite Plastics",
        ("Aero-Lite", "Order #"),
        number=r"Order #(\d{4,})",
        invoice_date=r"\n" + _LONG + r", \d{1,2}:\d\d",
        total=r"\nTotal\s*\n\s*" + _MONEY,
    ),
)

__all__ = ["INVOICE_FORMATS"]
