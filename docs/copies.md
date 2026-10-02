# One document, many copies

The same invoice or bill often reaches the association more than once:

- as the **issuer's own record**: the i-doxs and SMUD portal PDFs jason downloads, or the vendor portal's invoice (FieldPortals for ProActive);
- as an **email attachment** from the vendor or agent;
- as a **PDF a person attached** to the PayHOA payment;
- as a **paper letter** PostScanMail scanned.

The catalog keeps every copy as it is, duplicates included, so it stays true to what it holds. `jason copies` finds the copies that are one document, records why, picks the best copy to read, and matches the document to its PayHOA payment. The model is `jason.community.copies`, and the channel priority is `mystique/copies.py`.

```bash
jason gmail --sync --files   # email headers, then the PDF attachments that look like documents
jason copies                 # every document with copies in more than one channel
jason copies --issuer Signal # every document from one issuer
```

## Identity

A copy records its channel, where it is, and what identifies it: issuer (the named sender), document number, account, date issued, amount, the content hash, and when it arrived. Two copies are one document under the first rule that holds:

1. **the same file** (content hash), whoever sent it;
2. **the same issuer and number**;
3. **the same issuer, account, and date** (a utility bill);
4. **the same issuer and amount**, dated within three days, when neither prints a number;
5. **the same issuer and amount**, when one copy is a letter with neither a date nor a number of its own that arrived up to 21 days after the other copy's date.

Rules join strongest first, and each join records its rule. A copy with no issuer joins only on rule 1. A number read by OCR can be wrong, so a join on it is a reading.

A paper letter becomes a copy only when it reads as a bill, meaning an amount or a number. The City's backflow test notices are sorted with its utility mail but are not bills. A date on a letter after the day it arrived is a due or expiration date, not the day it was issued.

## The best copy

`COPY_PRIORITY` orders the channels:

1. the issuer's portal: the issuer's record, fetched and verified by jason;
2. email: the issuer's original file;
3. PayHOA: a file a person chose, which is how a bill ends up on the wrong payment;
4. paper: read by OCR;
5. the library.

A readable copy always comes before an unreadable one. The best copy is only the one to read; the others stay.

## The payment

A document's payment is either the one a PayHOA copy hangs on (attached by a person) or a candidate: a payment to the issuer's PayHOA vendor of the document's amount, from 20 days before the document to 90 after. A letter with no date is anchored on the day it arrived. When a bill of the same amount comes every month, the nearest payment on or after the bill is taken and the others are listed.

A document attached to more than one live payment is listed with what explains it. First what jason's other audits say (`audit_notes`): the utility payment audit (`jason utilities --payments`) finds a bill paid twice, or a bill attached to another month's payment, and a vendor portal's verification (`jason vendors --verify`) finds the invoice the vendor applied a payment to against the one attached. Then the utility store (`next_bill_credit`): a bill paid twice shows as the account's next bill asking less than its charges by the bill's amount; when that next bill on file came more than 45 days later, a month's bill is missing between them and the credit paid it, and the remainder shows on the bill on file (a utility portal that keeps only two years of bills is how a month goes missing). Split lines of one payment share a parent, and one month's recurring bill on several months' payments of its amount (within a few cents, at least 20 days apart, such as a small monthly cloud charge) is read from the payments. A bill paid in parts reads from the payments too, such as two fines on one notice paid separately. A deposit is never a payment: an insurer's claim check deposited and the check paying it out to the contractor are backup and payment, listed as `deposits`. A deposit request on two payments to one vendor is a deposit and its balance: a vendor that asks part of the price before ordering materials has its deposit email hang on both payments of the one job. A quote for work in parts hangs on each part's payment; a proposal on payments 20 days or more apart reads as one quote for several jobs.

A vendor can reuse an invoice number on invoices months apart; the same number on another amount more than a month away is another document. Two accounts' bills are two documents, however alike their issuer, amount, and date: two accounts billed the same amount the same day are each paid once.

## Proposals and the invoices that follow them

A vendor often sends an estimate, quote, or proposal before the board accepts the bid, and a matching invoice once the work is done. Each copy carries its stage, read by the rules the repair paperwork uses (`jason.community.incidents.STAGE_RULES`): proposal (estimate, quote, bid, scope of work), contract (signed, agreement, work authorization), change order, or invoice. A bill jason fetched from a portal, a PayHOA attachment, or a paper bill that names no other stage is an invoice.

- **Two documents.** A proposal and an invoice join only when they are the same file, however alike their issuer, amount, and date.
- **Linked forward.** Each proposal is linked to the invoice that followed it: the same issuer, issued on or after the proposal within a year, the same amount, else within 10% (a final bill moves a little). The nearest such invoice wins, and an invoice fulfils one proposal.
- **The invoice is paid.** A proposal gets no payment candidate of its own; its row shows its invoice and that invoice's payment. A proposal attached to a payment by a person keeps that attachment.
- **Paid on the proposal.** A person sometimes pays from the estimate and attaches it to the payment. The report lists those as paid with the proposal attached.
- **Searched in PayHOA.** A proposal with no invoice and no attachment is searched for among PayHOA's payments to the same vendor (its PayHOA vendor, or its words in a vendorless payment's description) after it, within a year. One of the same amount is taken as its payment ("paid with no invoice on file"); payments within 10%, and pairs within 1% (a deposit and a final bill), are listed as candidates for a person to confirm, since a monthly fee can match a bid by chance.
- **No invoice or payment found.** What is left was declined, is still open, was paid by the insurer (a claim's estimates), or was billed in a way no rule reads. Whether the board accepted a bid is in the minutes.

A payment PayHOA holds with no vendor (a bank transfer read from the feed, "Online Payment ... To Flock Group Inc") is a candidate when its description carries one of the issuer's words from `mystique/senders.py`, whole. An emailed document's issuer is the sender it came from (the From, or the writer behind a Google Group), before anyone else copied on the message: Flock's invoices with the prior manager copied are Flock's. A platform (`SourceKind.PLATFORM`: PayHOA's notices, PostScanMail's scans) only carries another's document, so its issuer comes from the document's letterhead, else the subject, else it stays unknown. What the association emailed out takes no issuer from the people it went to, and the words name an issuer only on a bill, proposal, or contract (minutes that approved a bid are not the vendor's). An emailed invoice from a billing service whose domain names no vendor (QuickBooks sends from intuit.com) takes its issuer the same way ("SUMMIT ROOFING - Invoice 905").

Mystique's findings are in the private notes (mystique/notes/copies.md).
