# Vendor portals

Some vendors bill through a customer portal. There, jason can read the vendor's own record of the account: every invoice, every payment, every visit, and every product applied. That record is more reliable than the PDFs a person once attached in PayHOA by hand. It also shows where those attachments went wrong.

A portal is one row in `mystique/vendors.py`: a `VendorPortal` with the vendor, its platform, its account name on that platform, its PayHOA budget line, and the words its bank line carries. The Keeper login record is named in `.env` as `<key>_record_uid`. jason signs in non-interactively and only reads. It never pays, uploads, or changes reminders.

## FieldRoutes vendors on FieldPortals

Pest control companies on FieldRoutes give customers a portal at `<company>.fieldportals.com`. A commercial customer can hold a master account with a service plan. A master account can also carry other properties, each on its own plan; the client switches between them. This association's vendor and account: `mystique/docs/vendor-portals.md`.

This association's findings are in its private notes (mystique/notes/vendor-portals.md).

`jason.fieldportals.FieldPortals` is the client. It was captured from a HAR of one company's portal on September 29, 2026. That HAR holds the portal password in plain text, so do not commit or share it.

1. `GET /landing/index`. The page's script sets the `x-csrf-token` header value.
2. `POST /resources/session/login` with `username`, `password`, `company=<company>`, and `redirect=`. Success is a 302 to `/home`.
3. `POST /resources/delegates/buildDelegate` with `action=getPage&currentPage=<page>`. It returns JSON, and `data.customer` holds the account:
   - `transactions`: tickets and payments. A ticket's `transactionID` is its invoice number, and its `label` is the appointment. A payment's `invoiceIDs` names the tickets it paid.
   - `services`: on the history page only, the latest 50 visits. Each has the technician, time in and out, notes, the ticket, and `productsUsed` (EPA number, amount, dilution, method, areas, target pests).
   - `documents`: on the files and account pages. These are photos and PDFs behind signed S3 links that expire.
   - `subscriptions` and `properties`: the plan, and the properties on the master account.
4. `POST /resources/delegates/actionDelegate.php` runs a report. `printInvoice&ticketID=<ticket>` returns the invoice PDF as base64 in `data`. `runChemicalUsageReport` returns the products applied in a date range as an HTML table, and `getChemicalUsageReport` returns the same as a PDF. `runNewConditionsReport` returns the conditions the technicians recorded. `switchProperty&customerID=<id>` loads another property on the account.

The wallet page lists payment methods. jason never reads them into a record.

## Sync

```bash
jason vendors --sync            # sign in with the Keeper record; download what is new
jason vendors                   # print each property: plan, balance, latest visits, products this year
```

Each property lands under `data/vendors/<key>/<customer id>/`:

- `account.json` holds the snapshot.
- `invoices/<ticket>.pdf` holds each invoice.
- `files/<document>.<ext>` holds the photos and documents.
- `chemicals/<year>.pdf` holds each year's product report.
- `conditions.html` holds the conditions report.

An invoice is kept only when its own text prints that ticket's number and amount. It is read with the vendor's row in `jason.community.invoice_formats`. A PDF that names another invoice goes to `invoices/_mismatch/`.

## Verify against PayHOA

```bash
jason vendors --verify
```

The verifier matches each PayHOA payment to the vendor with the portal's own payment, in date order for each amount. The portal payment may fall up to 10 days before the bank line or 21 days after it, which covers a mailed check. It reports:

- a payment the portal has no record of;
- a payment that paid another property's ticket;
- a category other than the budget line;
- a payment with nothing attached;
- an attachment that is not the invoice the vendor applied the payment to;
- one invoice attached to two payments;
- portal payments that no PayHOA payment accounts for.

A void line is recognized as the reversal it is. The result is `data/vendors/<key>/verification.json`. It needs the PayHOA snapshot that `jason invoices --fetch` writes.

## Attaching bills

A portal vendor is registered as a bill source. So `jason sync-bills` routes an unreviewed PayHOA payment that carries the vendor's bank words to this portal. It syncs the portal when a payment needs it, and attaches the checked invoice for the ticket that payment paid. Nothing is attached without a portal payment of the same amount.
