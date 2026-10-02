# Invoices, utility bills, and tax returns

Models in `jason.community.models.invoices` and `jason.community.models.invoices_utility`:

| Model | Kind | Registered | Reads |
|---|---|---|---|
| `flood-premium-notice` | invoice | first | Philadelphia Indemnity's NFIP flood renewal notice and new-application invoice |
| `invoice` | invoice | after it | any invoice, receipt, or statement for services: the vendor rows, then the general labels |
| `utility-bill` | utility_bill | | SMUD's and the City of Sacramento's bills, through the existing readers |
| `tax-return` | tax_return | | the preparer's filing letter and the returns behind it |

## The law

The law says nothing about what an invoice holds. It says what the association keeps:

- An invoice, receipt, or statement for services for a payment the association made is an "enhanced association record" (CIV 5200(b)). So is a reimbursement request.
- The board's written approval of a vendor's invoice is an association record (CIV 5200(a)(5)).
- State and federal tax returns are association records (CIV 5200(a)(6)).
- Members may inspect these for the current fiscal year and the two before it (CIV 5210(a)(1)).

Each reading carries one INFO finding that cites these sections. Every other check is about the document's own consistency, so none is a PROBLEM.

## Invoice

### Record

`InvoiceRecord` has these fields. Amounts are integer cents.

- **Who and which:** `vendor`, `number`, `bill_to`, `association_named`.
- **Dates:** `invoice_date`, `due_date`.
- **Amounts:** `total_cents` (what the document asks for, or on a receipt what was paid), `subtotal_cents`, `amount_due_cents`, `paid` (True when the text shows the payment: "Amount due $0.00", "Total Paid", a receipt), and `amounts` (every amount printed).
- **Lines:** `line_items` (description, quantity, rate, amount), and `line_items_partial` when a row read as quantity, rate, amount does not multiply out (usually an OCR misread).
- **How it was read:** `method`, which is `format:<vendor>` when a vendor row read it.

`required` is vendor, number, invoice date, and total. A document that has no number of its own therefore reads incomplete with `missing-number`. Examples are Farmers' monthly statement and Twilio's receipt.

### How it reads

1. `read_invoice` runs with `INVOICE_FORMATS` and the vendor names. The names come from the format rows, the specification's counterparties (`senders()`), its vendor portals, and PayHOA's vendor directory (`data/payhoa/vendor-info.json`) when the data directory is given.
2. A date the row captured but `parse_date` cannot read gets a looser parse: "23-MAR-2026", "08 May, 2024", "Jul 16,2024".
3. More date labels follow: "Date of issue", "Order placed", "Statement date", "Posted date", "Receipt date", "Payment date".
4. A vendor still unnamed is the counterparty whose words are in the letterhead (`sources.resolve`).
5. Line items are the triples where quantity times rate is the amount printed. A closing "1 / $691.91" run that sums the items above it is dropped, and so is a repeated page.

A text is not an invoice when it is unreadable (glyph codes), has no vendor row and no invoice cue (invoice, receipt, statement, order, bill, amount due, total, premium, estimate), or has no number, total, or amount.

### Vendor layouts

These are the `InvoiceFormat` rows in `jason.community.invoice_formats`. `jason invoices` uses the same rows.

| Vendor | Layout |
|---|---|
| ProActive Pest Control | FieldRoutes' printed invoice (existing row) |
| E&R Landscaping | number and total each on a line of their own; items print inline amounts |
| Philadelphia Indemnity (flood) | renewal notice: Bill ID, notice date, coverage row; new-application invoice; the portal's payment receipt |
| Farmers Insurance | monthly billing statement (no invoice number) |
| LaBarre/Oksnee | Applied Epic invoice: "Total Invoice Balance", "Balance Due On" |
| Arden Insurance Services | installment invoice: number under "INVOICE", total above "TOTAL AMOUNT DUE" |
| CAIS | crime policy invoice row |
| Signal Service | the mailed (envelope-scan) invoice; the emailed one's "Invoice Date:(" OCR |
| Amazon | order details page: order number and "Order placed" |
| Zoom | all labels, then all values |
| Adobe | values above labels; DD-MON-YYYY date |
| PayHOA | Stripe invoice: "Date of issue", "Date due" |
| Twilio | receipt: day-first date, "Total Paid" |
| Berding & Weil | statement: unlabeled date under the client name, "TOTAL THIS INVOICE" |
| Newman CPA | QuickBooks Online header row |
| LeDoux Backflow, California Builder Services, GoodLife | QuickBooks Desktop: the total is the first of the closing run of amounts |
| GoodLife | Joist-style deposit or progress invoice ("4514-2"); Buildertrend invoice ("Invoice ID:") |
| Sacramento County Tax Collector | Payment Express card receipt |
| Post Scan Mail | monthly invoice (never prints its name) and PayPal receipt |
| Aero-Lite Plastics | Shopify order |

A statement or receipt with no invoice number gets no number pattern. The account or policy number repeats every month, and the review would read it as the same invoice paid twice.

### Checks

| Code | Severity | When |
|---|---|---|
| `missing-number`, `missing-vendor`, `missing-invoice-date`, `missing-total-cents` | check | a required field is not in the text |
| `line-items-differ` | check | the items multiply out, but they do not add to the subtotal (or exceed the total when there is no subtotal); skipped when `line_items_partial` |
| `due-date-passed` | info | due before today and the text does not show it paid; the payment record answers it |
| `due-before-issued` | check | the due date is before the invoice date |
| `dated-in-future` | check | the invoice date is after today |
| `billed-to-other` | check | the bill-to line names someone other than the association (a board member's or an owner's invoice is a reimbursement) |
| `association-not-named` | check | no bill-to, and the text never names the association |
| `enhanced-association-record` | info | always (CIV 5200(b), 5210(a)(1), 5200(a)(5)) |

### Flood premium notice

`FloodPremiumNotice` extends the invoice record with these fields:

- **Carrier and notice:** `carrier`, and `notice` (renewal notice or new-application invoice).
- **Policy:** `policy_number` (the most frequent 50xxxxxxxx number), `expiration_date`.
- **Property:** `property_location`, and `building`, the specification's `Building` for the location through `assign_building`.
- **Money:** `building_coverage_cents`, `deductible_cents`, `premium_cents`.

The invoice's `number` is the Bill ID (or Billing ID), which is unique to each bill.

It adds three checks:

- **`unknown-flood-policy`** (check): the renewal's policy number is not among the specification's flood policies or their prior numbers.
- **`flood-building-mismatch`** (check): the location's building is not the policy's building.
- **`flood-renewal-due`** (check within 45 days, else info): the expiration is still ahead. The notice says a premium received within 30 days after expiry renews without a lapse.

## Utility bill

`UtilityBillRecord` holds these fields:

- **Account:** `provider` (`Utility`), `account`, `account_label` (the specification's purpose for the account).
- **Dates:** `bill_date`, `period_start`, `period_end`.
- **Amounts:** `current_charges_cents`, `charged_cents` (the lines added up), `amount_due_cents`, and `by_service` (cents per `Service`).
- **Detail:** `service_address`, `parcel`, `rate_schedule`, the counts of `charges` and `meter_reads`, and the parsed `UtilityBill`.

`identify` picks the provider and account. `Smud` or `SacramentoUtilities` parses the bill. These are the readers `jason utilities` uses, unchanged.

Checks:

- **`charges-differ`** (check): the charge lines do not add to the current charges (`UtilityBill.reconciles`).
- **`previous-balance`** (check): the amount due exceeds the current charges, so an earlier bill was paid late or not at all. A City balance can reach the tax roll.
- **`credit-applied`** (info): the amount due is less than the current charges.
- **`unknown-account`** (check): the account is not among `Community.utility_accounts()`.
- **`billed-before-period-end`** (check): the bill date is before the period ends.

## Tax return

`TaxReturn` holds these fields:

- **Year and preparer:** `tax_year`, `preparer` (the firm under the signature), `letter_date`.
- **Forms and results:** `forms` (1120-H, 100, 199, 7004, 3539, 8453-C/EO), and `results` (each form's overpayment, balance due, amount due, or no balance due, with the amount).
- **Filing:** `extension`, `deadlines` (the dates the letter sets), `signature_forms`, `estimated_payments_cents`.

Checks:

- **`tax-return-record`** (info): the return is an association record (CIV 5200(a)(6), 5210(a)(1)).
- **`signature-not-in-text`** (check): a board member must sign before filing, and the copy's text cannot show that signature.
- **`tax-due`** (check): a form shows an amount due.
- **`tax-deadline`** (check): a deadline the letter gives is still ahead.

## Coverage

The library holds few invoices of its own, so the readers are measured on the PayHOA attachments (`data/payhoa/attachment-text`), grouped by vendor. For a payment with one attachment, the payment's amount is the ground truth for the total. The measures are how often a number and a date (within a year before the payment) are found, how often the total equals the payment, and how many readings are complete.

Mystique's findings are in the private notes (mystique/notes/document-models/invoices.md).

## What the texts cannot show

- **Payment.** Whether an invoice was paid. The payment record answers that (`jason invoices`).
- **Board approval.** Whether the board approved an invoice (CIV 5200(a)(5)). Minutes or a signed approval answer that.
- **Signatures.** Signatures on returns and estimates.
- **Scanned text.** Figures in a scan without a text layer; OCR text is read when the review cached it.
- **County tax bills.** Their figures are images; `jason tax` holds the bills.
- **Quotes and policy packets.** Flood quotes ("Quote Only") and policy packets are not bills and read without a total.
