# Invoices and the payment review

Before jason fetched the utility bills itself, invoices were attached to PayHOA transactions by hand. `jason invoices` checks every expense payment against what is attached to it, so a wrong file, a wrong category, or a double payment surfaces.

## The invoice model

`jason.community.invoices.read_invoice` reads an invoice's vendor, number, date, due date, and payable total. It also keeps every amount the document prints. The general reader knows the common labels ("Invoice #", "Invoice Date", "Amount Due", "Invoice Total", "Total for this invoice"). It skips a zero amount due, which marks a paid invoice, and reads "USD 1.49" and "2,750." as amounts.

A vendor whose layout the general reader gets wrong gets an `InvoiceFormat` row in `jason.community.invoice_formats`. The row lists the phrases that identify the vendor's invoices and patterns for its fields. The first row that matches wins. The general reader fills whatever the row leaves out. E&R Landscaping is the first row.

The review prints a scorecard per payee. It shows how often the reader found a number, a date, a total, and the payment's amount. A payee with low scores is the next format row to write.

A PDF whose text layer is glyph codes (control characters, from a font with no character map) or has no text layer at all is a scan. The review lists these as unchecked until an OCR engine is installed.

## The review

`jason invoices --fetch` reads every transaction, the category tree, and the vendor directory. It reuses attachments already on disk: the monthly export under `data/transactions/`, the utility portals' files, and `data/payhoa/attachments/`. It downloads the rest. It changes nothing in PayHOA. The review then groups split rows into one payment and skips income, transfers between the association's own accounts, and bank service charges. It reports:

- an expense with nothing attached, grouped by payee in the terminal;
- no attachment that prints the payment's amount;
- an attachment that names another vendor from the directory;
- the same file or invoice number on another payment from the same bank account. When the amounts agree, this may be a double payment. A reserve reimbursement that carries the operating invoice is not flagged;
- an invoice dated after the payment, or more than a year before it;
- a category no more than one other payment of this payee carries, when most of its payments carry another;
- an unreadable attachment.

When the vendor has a customer portal in `Mystique.vendor_portals()` and `jason vendors` has saved its ledger under `data/vendors/<key>/`, each bank payment is matched to the payment the vendor recorded. The match takes the same amount recorded up to four days before the bank posted it, which is an autopay. Then, for what is left, it looks up to a week before or three weeks after, which covers a mailed check. A pairing the attachment confirms is settled first. The vendor's record names the invoice the payment paid, so the review says when the attachment is another invoice and points to the vendor's copy of the right one. It also notes a payment the vendor never recorded.

A deposit booked against an expense category (PayHOA's `originalAmount` is negative) is a refund or credit, such as an insurer's refund check. It is noted, not checked for an invoice, and it does not count toward a payee's usual category.

A payment the bank returned, shown as "Credit Return: Online Payment N", is noted and not counted. Utility payments are left to `jason utilities --payments`.

The results are in `data/payhoa/invoice-review.json`, and the `invoice_review` MCP tool reads them. The treasurer re-attaches, re-categorizes, or recovers a payment. Jason does none of those.
