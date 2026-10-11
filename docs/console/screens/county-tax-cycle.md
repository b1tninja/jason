# County tax cycle

A new screen, `#/county-tax` (`?year=2099`, `?apn=` for one parcel), in the Money group · phase 2 · the run page `#/work/county-tax-cycle/2099` embeds it · CLI: `jason sync-tax`, `jason county-tax --list`, `jason county-tax --import-receipts / --import-bill`; MCP: `tax_status`, `tax_account`, `tax_reassessments`

## In the console

None for the tax store. `#/payments` (bill attach tab) lists a county ACH as class `county-tax`, "no source yet" or matched, and its investigation card shows a receipt candidate; `#/members-and-units` has a one-line taxes band per unit (`unit_brief`). Nothing lists the association's own parcels, their bills, installments, receipts, or the chain that attaches a bill to a payment. There is no `ui/src` view that reads a tax loader (checked 2026-10-11), and no `county-tax-cycle` definition in `src/jason/workflows` (only the annual owner information request and control adoption are registered).

**This spec is the whole screen, as proposed.** It is the `county-tax-cycle` definition of [money.md](../../workflows/money.md) section 2.8 drawn as one screen. It reads; a person acts. jason never pays a tax bill, never signs in to the county's site (a person signs in, and a refresh token needs a person to try it once), and never attaches without the approvals kind `payhoa-attach-bills`. Draw it from built parts and say which are not built.

## Purpose and personas

The association's own parcels for one tax year, in one line of sight: what each bill says, what is owed, what was paid and from which account, which payment each receipt proves, and whether the bill PDF is attached to that payment in PayHOA.

- **Treasurer:** reads standing, saves the missing bill and receipts, decides a receipt that paid several bills, plans the attach. Reviews every payment.
- **Manager:** runs the reads at a terminal and hands the year to the treasurer.
- **President, vice president, directors, secretary:** read what the treasurer reads at the same level (the board's decision of 2026-10-11).
- **Counsel:** on grant, the recited law and the delinquency band.
- **Reviewer, owner view, roster below P2:** counts only, or nothing (`view=owner` is refused, as for `bill-attach`).

## Data

| Part | Source | State |
|---|---|---|
| Parcels, stored bills (number, year, land, improvement, net assessed, ad valorem, direct charges, total, payments, balance, PDF), levy lines of the latest bill | `TaxStore` (`data/tax.db`) via MCP `tax_status`, `tax_account`; the parcel list is `Community.parcels()` | Built; no loader |
| Standing: unpaid (newest year with a balance), delinquent (older years with a balance), years with no bill | `community/standing.tax_standing` | Built; reads annual bills only |
| Catalog age | `sync_runs` / `synced_at`; cadence `county-tax` (monthly, stale after 35 days: proposed policy, `integrations.registry`) | Built (Status screen reads it) |
| Receipts: confirmation, posted day, each paid item (cents, parcel, bill number and name, tax year, installment), fee, tender type and last four, `importedAt`, `by` | `tasks/tax_receipts` over `data/tax/receipts.json` (append only) | Built; no loader |
| Bill PDF per bill | `TaxBill.pdf_path`, `pdf_sha256`; `jason county-tax --import-bill`, logged in `data/tax/bill-imports.jsonl` | Built; no loader |
| The attach chain per payment | `sources/county_tax.CountyTaxBillSource`: (1) payee row `county-tax`; (2) one receipt with the payment's amount (or amount plus fee), posted in the window, from the association's account; (3) the receipt names **one** catalog bill; (4) that bill's PDF is on disk. Any short link is no match | Built; the per-link result is not exposed |
| The payment and its attachment | `bill-attach` loader rows (class `county-tax`, status), the kept dry run, `payhoa-attach-bills` plan status | Built |
| The investigation and a person's outcome | `bill-investigation` loader and writer (`attached-bill`, `attached-receipt-only`, `not-our-bill`, `waiting-for-mail`, `escalated`) | Built |
| Mailed tax bills against the catalog | `mail_links.tax_bill_checks` (matched by bill number or by amount; "a supplemental or corrected bill" when neither fits) | Built; P2 |
| Which account paid | receipt `tenderLast4` against `Community.bank_accounts()` suffix and purpose | Built logic; not shown |
| Installment due and delinquent dates | **Not stored.** `TaxBill` has no date field; a receipt item has only the installment label. The county's bill (the PDF) is the source | **To add** |
| Supplemental and escape bills | **Not stored as a class.** `parse_bill` reads "Secured Annual Bill" only; a bill with no tax year files under `supplemental/` and `tax_standing` skips it; escape has no trace | **To add** |
| Loaders | `tax-status` (parcels, standing, bills, PDFs, ages, receipts count) and `tax-receipts` (receipts, each with its chain and attach state) | **To add** (named in money.md section 5) |

**The law.** Checked against `data/authorities` on 2026-10-11: the Revenue and Taxation Code shelf holds only **RTC 2191.3 to 2191.6** (unsecured lien certificate) and **RTC 3691** (power to sell tax-defaulted property). **Not on the shelf, so not recited and no law clock shown:** 2605, 2617, 2618, 2922, 75.52 (named in [insurance-and-deadlines.md](../../insurance-and-deadlines.md), a table written without a stored text), 4985, and the sections for penalties, supplemental, and escape assessments. Every installment and delinquency date is therefore marked **from the county's bill (documents)** and never LEGAL. 3691 may be recited in `Recitation` (jason's consolidated copy, not an official restatement); it does not state the day a parcel becomes tax-defaulted, so `power_to_sell` (July 1 of the oldest delinquent year plus six) is jason's reading from code, labeled `ReadingLabel`, for the tax collector or counsel.

## Layout

```
+------------------------------------------------------------------------------------------+
| County tax cycle · 2099 · Oakview                                                        |
| Catalog read Oct 1 (10 days) · receipts imported Oct 7 · PayHOA snapshot Oct 9           |
| 2 parcels · 1 unpaid · 0 delinquent · 1 bill PDF missing · 1 receipt to attach            |
+------------------------------------------------------------------------------------------+
| 1 PARCELS            Parcel   Standing  Bill 2099      Balance   PDF         Mailed bill |
|                      ..0000   due       #00000001     $363.57   on file     matches      |
|                      ..0001   paid      #00000002     $0.00     MISSING     not received |
|                                          [Command: jason county-tax --import-bill ...]    |
+------------------------------------------------------------------------------------------+
| 2 INSTALLMENTS       Bill #00000001      Due             Delinquent after   Paid          |
|   from the county's  1st installment     2099-11-01      2099-12-10         $363.57 paid  |
|   bill (documents)   2nd installment     2100-02-01      2100-04-10         $363.57 owed  |
|   [DOCUMENTS] Not the law's: the sections are not on the authorities shelf. Date not on   |
|   record is a state. [Enter from the bill]                                                |
+------------------------------------------------------------------------------------------+
| 3 PAYMENTS AND RECEIPTS  [PAYMENT PROOF - not the bill]                                   |
|   Oct 7  $363.57  confirmation EX-0001  paid 1st installment, parcel ..0000               |
|          from the operating account ending 1234 (P2)   PayHOA tx 1042                     |
| 4 ATTACH CHAIN for tx 1042   1 payee row ok · 2 one receipt ok · 3 one bill ok · 4 PDF ok |
|   Matched: bill #00000001 (receipt EX-0001). Attached: no. Plan ap-2099-0040 in review.   |
|   (a lead until a person attaches it)       [Open the plan]  [Open the investigation]     |
+------------------------------------------------------------------------------------------+
| 5 SUPPLEMENTAL AND ESCAPE   Not read: the catalog holds no class for them. Mail letters   |
|   that match no stored bill: 1 (P2)                                                       |
| 6 DELINQUENCY   None. (If any: the oldest year, the amounts, jason's reading of 3691)     |
+------------------------------------------------------------------------------------------+
| Caveats (verbatim from tax_receipts.CAVEATS and the investigation)                         |
+------------------------------------------------------------------------------------------+
```

## Components

`ScreenHeader`, `DataTable`, `Card`, `Money` (integer cents), `Doc` (the bill PDF, a logged P2 view), `Pill`, `StandingPill`, `DueDate`, `BasisPill` (DOCUMENTS only; never LEGAL here), `SourcedDate` (the bill's dates: `recorded` from the bill, else `needs input`), `Findings` (the four-link chain), `Evidence`, `Recitation` (3691), `ReadingLabel`, `Freshness` (the three ages), `Command`, `Confirm`, `PlanReview` (a link to the plan), `Caveats`, `PrivateSwitch`. **Spec'd, not built:** `SourceSyncStrip` (the three ages), `InvestigationCard` (the link target). New: `ChainLinks` (four ordered links, each a word and its fact; the first short link is named).

**A receipt is proof of payment, not the bill.** Every receipt row carries `PAYMENT PROOF` and never offers itself for attach. The attach target is the bill's PDF the receipt names. Where only a receipt exists, the outcome `attached-receipt-only` is a person's word; whether that satisfies the treasurer's review is the board's open question (money.md `policy` step) and the screen does not answer it.

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Read the catalog | shown as a command; reads the county's public pages | No | `jason sync-tax` |
| Save a bill the catalog lacks | shown as a command; files the PDF a person downloaded | No (a signed log line) | `jason county-tax --import-bill FILE --apn A --year Y --by NAME` |
| Keep a receipt | shown as a command; trims and keeps once by confirmation | No (signed, append only) | `jason county-tax --import-receipts FILE --by NAME` |
| Dry run the attach | shown as a command; reads PayHOA, uploads nothing | No | `jason sync-bills --dry-run --source county-tax` |
| Plan the attach | opens `payhoa-attach-bills` (R1, one person, six-hour plan) | Yes: `#/approvals`, decided and applied there | `jason approvals plan payhoa-attach-bills --by NAME` |
| Record an outcome | the investigation's writer, in the signer's name, append only | No | `POST /api/write/bill-investigation/<tx>` |
| Enter a date from the bill (proposed) | `SourcedDate` `recorded`, with the bill as `Doc`, behind `Confirm` | No: a signed record | to add |
| Open a payment, plan, or investigation | links to `#/payments`, `#/approvals` | No | |

No control pays a bill, opens the county's site, signs in, or imports a file by itself. The live receipts reader (`read_live_receipts`) raises `NeedsSignIn` and nothing calls it; the screen says "reading the county's receipts needs a person's sign-in at a terminal" and offers the import command.

## States

- **No catalog:** "No county tax catalog on disk. `jason sync-tax` reads it." No count, no zero.
- **No tax reader for the county:** "jason has no tax reader for this association's county; a person can still import bills and receipts." (`placer.md`)
- **Stale:** first line, "Catalog read N days ago" against 35 days (proposed policy, no stamp).
- **No receipts:** "No county receipts on disk; `jason county-tax --import-receipts FILE` keeps one a person saved."
- **Bill without a PDF:** the row says MISSING with the import command; the chain stops at link 4.
- **Receipt paid several bills, or names none:** "No match: one PDF of all of them would be needed. A person decides." Opens the investigation card; nothing is attached.
- **Tender not an association account:** "Paid from an account that is not on the association's list." The chain stops at link 2.
- **Dates not on record:** "Date not on record: the county's bill states it." A past-due reading is withheld until a date is entered.
- **Newest year unpaid:** reads `due`, never `delinquent`, because `tax_standing` does not know installment dates; once a bill date is entered and passed, the row says "past the bill's delinquent date" (documents).
- **Changed since:** a new sync or import banners the difference.

## Privacy

- Bills and amounts are P1 (`tax-bills/`); a bill PDF, a mailed bill, and a receipt's tender are P2. The tender's last four is shown only to an office that opens P2 and only in the private view; otherwise "an association account". A bank account shows its last four, never its name.
- Lists show a parcel by its last four; the full number appears on one parcel's page. No billing party, address, phone, or email is kept or shown (`tax_receipts` drops them).
- Directors and officers read the same; the owner view and a roster person below P2 see counts.

## Acceptance criteria

1. Every amount renders through `Money` from integer cents; none is a float.
2. Each date reads "from the county's bill (documents)" with `BasisPill` DOCUMENTS; no date is LEGAL while the Revenue and Taxation Code sections are off the shelf.
3. A receipt row says PAYMENT PROOF and has no attach control; the attach target is the bill PDF.
4. The chain shows four ordered links; a receipt that paid two bills shows "no match" at link 3.
5. Without the private view or P2, no tender digits appear in the HTML.
6. No control pays, signs in, mails, or attaches; "Plan the attach" only opens the approval.
7. A missing store reads "not read" with its command, never zero; the three ages show.
8. `power_to_sell` appears only with `ReadingLabel`, beside the recited 3691.
9. A director sees what the treasurer sees; the owner view is refused.
10. Fixtures use "Oakview", "Example County", parcel 000-000-0000, and 2099 dates.

## Decisions for the user

- **Put the Revenue and Taxation Code sections on the shelf** (`jason export-authorities`, rows in `community/authorities.py`): 2605, 2617, 2618, 2922, 75.52, 4985, and the penalty, supplemental, and escape sections, before any law clock is shown. Until then, dates come from the bill.
- **How installment dates enter:** parse them from the bill PDF, or a person enters them (`SourcedDate`)? Recommended: a person first, a parser later.
- **Supplemental and escape bills:** add a bill kind to the catalog (annual, supplemental, escape, corrected) so they are listed and checked.
- **Does a receipt alone satisfy the monthly review** (`attached-receipt-only`)? The board's policy; the screen holds the question.
- **Upload a saved receipt or bill in the console,** or keep the importers at a terminal? Recommended: terminal.
- **Who runs the one-time sign-in and refresh-token check** that any scheduled receipts read needs.
