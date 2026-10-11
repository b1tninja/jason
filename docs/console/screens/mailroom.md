# Mailroom

A new screen, `#/mailroom` (`?preview=ID` one saved preview, `?batch=ID` one mailing), in the Governance group beside Notices · phase 2 for the preview and the read-back, phase 4 for the send plan · CLI: `jason mailroom`

## In the console

None. The nearest are `#/approvals` (a letter's approved stage shows `jason mailroom --send --yes` as a command), `#/owner-info` (the cycle's mail batch), `#/jobs`, and `#/notices` (proposed; a mailed notice's outcomes). Nothing shows a letter's recipients, page count, or price before it is mailed.

**This spec is the whole screen, as proposed.** It previews and reads. It never mails, cancels, or queues a send: a person does that at a terminal ([AGENTS.md](../../../AGENTS.md) Boundaries). Verified against the repo on 2026-10-11:

| Built | To add |
|---|---|
| `jason mailroom`: `--pdf FILE --units U` previews (`--send-to`, `--with-invoices`, `--double-sided`); `--send --yes` mails; `--cancel ID --yes`; `--batch`, `--letters`, `--events`, `--months`, `--prices` read; `--notice KEY --by NAME` keeps the letter (`cli.cmd_mailroom`) | `--json` for the preview (only status, `--letters`, `--batch` have it); `--preview ID` (send exactly a saved preview); `--expect FINGERPRINT`; `--by` on every send |
| `jason.tasks.mailroom`: `resolve_units`, `prepare`, `send`, `printed`, `page_count`, `status`, `price_check`, `charged_letters`, `letter_history`, `keep_notice`; `payhoa.pricing.PRICING` (guide read 2026-10-01); the PayHOA client's `mail_*`, `send_mail_pdf`, `cancel_mail` | A saved preview record (today the recipients and total are printed and discarded; only PayHOA's preview PDF is kept); the `mailroom` loader |
| Stores: `data/mailroom/status.json`, `price-check.json`, `previews/*.pdf`, `sent.jsonl`; `data/notices/KEY/letter.pdf`. Path level P2 (`access.PATH_RULES`, `mailroom/*`) | A log line for a cancel (nothing in `src/` writes one; a `cancelled.jsonl` is on this checkout's disk, origin not verified) |
| SOP `mailroom-letter` (6 steps); lessons `letters-cannot-be-recalled` (open), `test-as-an-owner` (open), `letter-link-per-unit` (decision), `form-link-needs-unit` (fixed) | An approvals kind: the registry has three (`owner-info-tags`, `payhoa-attach-bills`, `gmail-drafts`), none for mail |
| jason-ui: `Doc`, `DocumentPreview`, `CostLine`, `Money`, `Command`, `Confirm`, `SecondConfirm`, `ChangedBanner`, `PlanReview`, `DataTable`, `Pill`, `Stat`, `Caveats`, `Findings` | `TerminalStep` and `AgeStamp` are named in other specs, not in `ui/src`; `Confirm` has no typed-count form; `mailroom` is not in `jobs._CLASS_OF_COMMAND`, so a queued preview would not take PayHOA's lane |

## Purpose and personas

One letter, from the PDF to the mail slot to the mailbox: what it is, whom it reaches and at which address (and where each fact came from), how it prints, what it costs, what must be true before it goes, and what became of each piece. A mailing cannot be recalled (lesson `letters-cannot-be-recalled`), so the screen puts the whole cost of a mistake in front of the person before they type the command.

- **Manager:** prepares the preview, checks it, runs the command, reads the mailing back.
- **President, vice president, director, secretary, treasurer:** read what the manager reads (directors and officers have the same access to information; they differ in duties). Under the proposal (below) two of them sign; the treasurer is the usual second on a money act. The secretary records the board's decision when the board decided on the letter or its cost.
- **Reviewer:** opens a send approval's evidence only. **Administrator** with no office: counts only. **Counsel:** none. **Owner:** never sees this screen (`OWNER_SOURCES` does not list it).

## Data

| Part | Source |
|---|---|
| Can the Mailroom send | `status.json` (`verify.hasAddress`, `hasPayment`; the year's `counts`), with its read time; `jason mailroom` refreshes it |
| Mailings | `status.json` `pdfBatches[]`, `invoiceBatches[]`: `id`, `created`, `costCents`, `sent`, `failed`, `cancelled`, `pages`, `sendTo`, `certified`, `color`, `standard`, `twoSided`, `completed`, `cancelledAt` |
| Sent log | `sent.jsonl`, one line a send, written by `send()` (also by the owner-information mail batch, whose `MailHandler` calls it): `sent` (UTC), `pdf` (the path as given), `pages`, `sendTo`, `units` and `ownerIds` (ids), `doubleSided`, `withInvoices`, `color`, `mailClass`, `tracking`, `by` (who sent it; from 2026-10-11), `guideCents` (one letter by the guide), `batches[]` (as above), `letters[]` (`id`, `communication`, `costCents`, `status` as read back seconds after the send), `preview`. It holds no name, address, sha256, or notice key |
| The pricing guide | `PRICING`: standard $1.05 or first class $1.25 for the first page, $0.20 each page after, color $0.20 a page, +$2.25 from 6 billed pages, certified $10.00, registered $25.00; PayHOA's address page is billed (`ADDRESS_PAGES`); read 2026-10-01. "A price list with a date, not a law" |
| Charged against the guide | `price-check.json` (`price_check`): per kind, month, pages, options: letters, charged, guide, `matches` (`guide`, `guide, address page not billed`, `differs`) |
| A letter after the send | live PayHOA only: `--batch ID` (status, last event, tracking), `--letters KIND`, `--events COMMUNICATION` (Lob's events). On disk afterward only through the notice ledger (`data/notices/deliveries.db`, `jason notices KEY --sync`), and only for a send with a notice key |
| Lessons for the area | `for_area(Area.MAILROOM, open_only=True)`: the dry run prints them for owner-information sends today |
| **The preview record (to add)** | `data/mailroom/previews/STAMP-STEM.json` beside PayHOA's PDF: `id`, `read`, `by`; `pdf` (`name`, `sha256`, `pages`); options (`sendTo`, `withInvoices`, `doubleSided`, `mailClass`, `tracking`, `color`); `named[]` and `missing[]` (what the person typed and what matched no unit); `units[]` (`id`, `title`, and the `payhoa.db` sync time); `recipients[]` (`unitTitles`, `name`, `address`, `ownerId`, `isIncluded`, `isDuplicate`); `printed` (billed pages, sheets, blank back, heavy); `lettersExpected`, `totalCents`; `fingerprint`; `notice` (key, if any); `linksTested` (`by`, `at`) |
| The fingerprint (to add) | first 12 hex of sha256 over the PDF's sha256, the sorted included `ownerId`s with a hash of each address, and the options. Safe to show and to put in a command: it carries no address |

`resolve_units` reads the local `data/payhoa.db` units table (street address after `_address_key` normalizing, or a unit id, or `all`); a name that matches none is a miss and stays one. `mail_recipients` then asks PayHOA live whom a letter to those units reaches, at the owner's mailing address (`mailing`) or the unit's own (`unit`). A count, a total, or an address is never computed from memory: it is the record's.

## Layout: the preview

Five bands, always in this order. The rail on the left of the first band is the letter's page strip.

```
+------------------------------------------------------------------------------------------+
| Mailroom > Preview 7f3a      read Oct 3 09:14 (2 h ago) by A. Manager     jason mailroom  |
| Not mailed. This page cannot mail anything.                                              |
+------------------------------------------------------------------------------------------+
| [ChangedBanner: only when stale] The PDF changed after this preview (sha 9e2f... -> c41b...)|
|   Read it again:  jason mailroom --pdf "annual-notice.pdf" --units "..."                 |
+------------------------------------------------------------------------------------------+
| 1 THE LETTER                                                                             |
| [DocumentPreview: annual-notice.pdf, page 1]  3 pages · sha256 9e2f4b7c1d0a5e33           |
| PayHOA's proof (drawn for the first recipient; the address page is not in it) [Open]     |
| Notice: mailing-notice-2099-10 (last day to send: Oct 12, DOCUMENTS) -> #/notices         |
+------------------------------------------------------------------------------------------+
| 2 WHOM IT REACHES                                  11 letters · 1 left out · 1 not found |
| Typed 12 -> matched 11 (units table, synced Oct 3 07:00) · 1 matched no unit: 131 Main St |
| Sent to: owners' mailing addresses (PayHOA read Oct 3 09:14)                              |
| Unit            Name          Address                    Resolved from              Flag |
| 123 Main St     A. Owner      123 Main St                 mailing = unit address      -   |
| 125 Main St     B. Owner      9 Example Rd, Example City  mailing address            -   |
| 127 Main St     C. Owner      (none)                      PayHOA left it out   [LEFT OUT] |
| 129 Main St     D. Owner      129 Main St                 mailing = unit address [DUPLICATE]|
+------------------------------------------------------------------------------------------+
| 3 HOW IT PRINTS AND WHAT IT COSTS                                                        |
| [address page][p1][p2][p3]  4 billed pages · 2 sheets double-sided · first class, b&w    |
| $1.85 a letter: $1.25 first page + 3 x $0.20      11 letters = $20.35       [CostLine]   |
| Guide read 2026-10-01. Four letter pages is the most before the $2.25 postage.           |
+------------------------------------------------------------------------------------------+
| 4 BEFORE IT GOES                                                                         |
| [met] Return address and payment on file (status read Oct 3)  [met] Within four pages    |
| [owed] Links and QR codes tested as an owner, recorded by NAME  [Record...]              |
| [owed] Recipients read by a person   [met] Not mailed before: no earlier send, same units |
| Open lessons: letters-cannot-be-recalled, test-as-an-owner (jason lessons --area mailroom)|
+------------------------------------------------------------------------------------------+
| 5 TO SEND IT  (a person, at a terminal)                                                  |
| This mails 11 letters and charges the association $20.35. A letter cannot be recalled.   |
| Command  jason mailroom --preview 7f3a --send --yes --by "NAME"   [Copy]                 |
+------------------------------------------------------------------------------------------+
```

**The list (`#/mailroom`).** A strip ("Can send: return address on file, payment on file; read Oct 3"), the saved previews (letter, units, total, age, stale or current), and the mailings (`status.json`) newest first: batch, date, sent, failed, cancelled, pages, charged against guide, and a row link. **One mailing (`?batch=ID`)** is its letters: one `LetterRow` each (status, last event, tracking, cost), its Lob events on open, the sent-log line as sent, and a notice's follow-ups owed for a returned or failed letter, linked to `#/notices?key=`.

## Components

Built: `ScreenHeader`, `Card`, `DataTable`, `Doc`, `DocumentPreview`, `CostLine`, `Money`, `Command`, `ChangedBanner`, `Pill`, `Stat`, `Checklist`, `Findings`, `Caveats` (verbatim), `Confirm`, `SecondConfirm`, `PlanReview`, `RemoteView`, `Timeline`, `AuditLog`. `Freshness` is in `CitedSections.tsx` though [components.md](../components.md) lists it as proposed; reuse it if it fits, else add `AgeStamp`. To add: `MailingPreview` (the five bands), `PrintedPages` (the address page and the letter's pages on sheets, with the heavy-postage line), `RecipientTable` (a `DataTable` preset), `ResolveWord` (a `Pill` preset: matched, not found, left out by PayHOA, duplicate, no address, unit address used), `SendChecks` (a `Checklist` preset), `MailingRow`, `LetterRow`, `TypedCount` (a `Confirm` preset: "this mails N letters; type N"), and `TerminalStep` where [handoff-admin-components.md](../handoff-admin-components.md) specifies it. Every state is a word beside its glyph.

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Read a preview again | Phase 2: a `Command`. Later, a `Confirm` that queues the read as a PayHOA-lane job in the person's name (a read, no `--yes`); needs `mailroom` in `_CLASS_OF_COMMAND` | No | `jason mailroom --pdf FILE --units U` |
| Record: recipients read | A signed note on the preview record (`by`, `at`), behind `Confirm` | No: a signed record in `data/` | (to add) |
| Record: links tested as an owner | The same, with a free-text note ("opened in a private window, signed out and in"); jason never signs in for it. The `--link-tested-by NAME` of lesson `letters-cannot-be-recalled` | No | (to add) |
| Send | **No button.** `Command` with the exact line, the count, the cost, and the sentence "This mails N letters and charges the association $X. A letter cannot be recalled." | See the proposal | `jason mailroom --pdf FILE --units U --send --yes [--notice KEY --by NAME]` (built); `--preview ID --send --yes --by NAME` (to add) |
| Cancel a letter | **No button.** On a `LetterRow` in `processing`: a `Command` with the letter id and the lesson's words | No | `jason mailroom --cancel LETTER_ID --yes` |
| Read the mailing back | `Command` | No | `jason mailroom --batch ID`; `jason notices KEY --sync` |
| Record the send on its letter | The built letters writer: the `sent` stage with `sentRef` = a communication id from the log. `Stamp sent` renders only with it | A signed record | (the `approvals` letters writer) |
| Open the notice | `#/notices?key=KEY` (its requirement, text as sent, proof, follow-ups) | No | `jason notices KEY` |

The console never queues `--send` or `--cancel` (a queued send would mail from a worker, unattended). To add: `jobs.add` refuses a `mailroom` command with either flag.

## The mail options (read from PayHOA's own Mail Options step, captured 2026-10-11)

The options the page shows, and the rules PayHOA's page itself applies. The command takes them as `--mail-class`, `--tracking`, and `--color` (built); the page shows what was chosen and never offers a combination PayHOA refuses.

| Option | Choices | Cost | Rule |
|---|---|---|---|
| Shipping | Standard (delivers in 2-3 weeks); First class (5-8 business days) | $1.05; $1.25 for the first page | An invoice goes only first class |
| Tracking | None; Certified mail; Registered mail | none; +$10.00; +$25.00 a letter | Offered only with first class |
| Printing | Black and white; Color | none; +$0.20 a page | |
| Two-sided | One-sided; Two-sided | the same price (saves paper) | An invoice cannot be double-sided |
| Send to | Unit address; owner mailing addresses (duplicates removed; the unit's address where an owner has none) | | |
| Pages | The first is the base cost; each after, $0.20 | | PayHOA's address page is billed; a sixth billed page adds $2.25 a letter |

The captured page also shows a return-envelope stub at $0.10 (a `return_envelope` field in a letter's options). The command does not offer it.

**Which class a notice needs.** Civil Code 4040(a)(2), from the stored text: "If the member has not provided a valid delivery method pursuant to Section 4041, the association shall deliver the document by first-class mail, registered or certified mail, express mail, or overnight delivery by an express service carrier addressed to the recipient at the address last shown on the books of the association." (4040(a)(1) first requires delivery by the member's preferred method.) Standard class is not among those methods. **jason's reading, not the statute's:** an individual notice to a member with no valid delivery method on record goes first class or better, so the preview shows the class in the first line, and a standard preview carries the note (`STANDARD_NOTE`, citing the section, not paraphrasing it). Whether a given mailing is an "individual delivery" or "individual notice" is the board's and counsel's to say; the page does not decide it. A letter kept as a notice (`--notice KEY`) defaults to first class; any other letter defaults to standard unless asked, and the preview names the class either way. The board has the question of the earlier standard mailings (board item `mailroom-class-individual-notice`).

**What the logs show.** `data/mailroom/sent.jsonl` records the class, tracking, and who sent it (`by`) from now on; sends before this change logged the class and no tracking or sender.

## The send plan: a proposal

**Recommendation: yes, a two-person approvals kind `payhoa-mailroom-send` (alias `payhoa.mailroom.send`; the registry's convention is the hyphenated key), apply at the terminal only, in phase 4. In phase 2, the preview record and the fingerprint come first, without the kind.** Labeled a proposal: the kind is not built and the board has not adopted a two-person rule for mail.

Why:
- **A preview is not a promise today.** `cmd_mailroom` calls `prepare` and `send` in one run: `--send --yes` resolves units and asks PayHOA for recipients again at that moment, and compares nothing to the preview a person read earlier. The fingerprint (`--expect` or `--preview ID`) closes this at the cost of one flag, and needs no new kind.
- **It is the most irreversible, costly write jason has** (R3 in [approval-workflow.md](../approval-workflow.md); the cancel window is minutes). The survey in approval-workflow.md already marks it two-person (no kind is built), and the engine's re-plan check is what the screen's "stale" state needs.
- **Shape.** One item (the letter is one thing, not item by item): the PDF, the recipients, the cost (`CostLine`), and the notice's clock. Basis: the fingerprint. First signer: the manager or an officer; second: a different named person, the treasurer where money is the question (`SecondConfirm`, with the typed count: "this mails 11 letters; type 11"). A re-plan that differs supersedes it (`ChangedBanner`). Max age: 24 hours, the registry default (a decision). A letter with a `DraftLetter` is planned only when that letter is at `approved`; the approval of the words never stands in for the approval of the write ([approval-workflow.md](../approval-workflow.md) section 11). The letter records its words and `sentRef` but no PDF hash (verified), so matching the PDF to the approved words is a person's check.
- **Apply stays out of the browser.** The approved stage shows the `Command` (`jason mailroom --preview 7f3a --send --yes --approval APR_ID --by NAME`), even when the server runs with `--allow-apply`. This keeps AGENTS.md's rule that a person at `--send --yes` mails. Once the kind exists, bare `--yes` is refused for it (mvp.md step 3). AGENTS.md would then name `--approval` beside `--send --yes`; that edit is the user's.
- **Cancel is not a kind.** Its value is speed and it only reduces harm. A command with a logged line is enough; this contradicts the registry row `payhoa.mailroom.cancel` (R2, one person), which should be dropped or kept as a command.

## States

- **No previews:** "No letter has been prepared. `jason mailroom --pdf FILE --units UNITS` reads PayHOA and saves a preview here. Nothing is mailed."
- **Mailroom cannot send:** a band above all: "Return address MISSING" or "Payment MISSING" from `verify`, with its read time. The command is shown dimmed with the reason.
- **Preview stale:** `ChangedBanner` says which: the PDF's sha256 differs from the file on disk; `payhoa.db` was synced after the preview was read (the unit list or an owner may have changed); the record is older than the limit; or the fingerprint a read just made differs. Nothing is hidden; the command to read again is shown.
- **A unit not found:** "No PayHOA unit matched '131 Main St'" (`missing[]`). It stays a miss and does not stop the rest. Zero matched: no recipient table, "no unit matched any name typed".
- **An address not resolved:** a recipient with no address reads "no address" and is counted out of the letters; one PayHOA leaves out (`isIncluded` false) reads "left out by PayHOA" (it gives no reason; none is guessed); `isDuplicate` reads "duplicate" (it is still counted unless left out). Under `mailing`, an address equal to the unit's reads "mailing = unit address" (PayHOA mails at the unit when an owner has no mailing address). A secondary owner record is shown as such: the command mails every included row and cannot leave one out.
- **Counts differ:** letters expected (included rows) against distinct owners and distinct addresses, when they differ: "PayHOA decides how many letters it makes; the read-back is the count."
- **Too many pages:** five or more letter pages: "6 billed pages: $2.25 more postage a letter ($24.75 in all); a page fewer saves it." Not blocked; mailing it is a person's choice and the choice is named in the plan ("four pages at most unless a person chooses otherwise").
- **Already mailed:** an earlier `sent.jsonl` line with the same units and the same file name (the log has no hash): "Units mailed this file on Oct 1." A warning, not a refusal.
- **Sent, not read back:** `batches` empty: "PayHOA accepted the send; its batch is not listed yet. Look in PayHOA's Mailroom before sending again." No second send is offered.
- **Processing, cancellable:** `status` processing: "Processing. Lob's cancel window is minutes; PayHOA still shows processing after it closes, so a cancel can fail." Shows minutes since the send and the `Command`. No threshold is invented.
- **Failed:** the batch's `failed` count or a Failed or Issue event: "Never went into the mail: not delivered." The notice ledger's follow-up, with its authority chip, links to `#/notices`; the fix is a new preview and a new send, never a retry.
- **Returned or forwarded:** the event word as PayHOA gave it, then jason's reading beside it, labeled ("jason's reading"): returned, or re-routed (delivered, address likely old). The follow-up and its authority are on the Notices screen, where the statute is recited; no statute is paraphrased here.
- **Not synced since the send:** "Status as read seconds after the send. `jason notices KEY --sync` reads the rest."
- **Cannot read a store / PayHOA not signed in:** the loader's reason and the command, not a blank table.

## Privacy

- **Recipients' names, units, and addresses are P2** (the store is P2 by `PATH_RULES`). `SEE_RULES` opens P2 to manager, president, vice president, director, secretary, and treasurer alike. Reviewer, counsel, and an administrator with no office see counts, pages, price, and fingerprint only. The owner view is refused.
- **Server-side masking (`MaskedField`) is proposed, not built.** Until it exists, the recipient table is not built: the screen shows counts, flags by count, and the cost. When it exists, names and addresses are masked and revealed a row at a time, each reveal logged.
- PayHOA's proof PDF has the first recipient's name and address on it: it opens only through `Doc` at P2, logged; never an `/api/file` link, never an absolute path (the sent log's `pdf` is shown as a file name).
- A URL carries a preview id, a batch id, or a notice key; never a unit, name, or address. The fingerprint holds a hash, not an address. The audit log masks addresses (`audit.mask`).
- Samples in this spec and the previews are made up ("123 Main St", "A. Owner").

## A made-up sample

Example Village HOA, 11 units on Example Rd. The PDF `annual-notice.pdf`, 3 pages, sha256 `9e2f4b7c1d0a5e33...`. The manager typed 12 street addresses; 11 matched the units table (synced Oct 3 07:00) and `131 Main St` did not. PayHOA's recipients: 12 rows; one left out (no mailing address), one flagged duplicate (a co-owner at one address); 11 letters expected. Mailed first class (a `--notice` letter's default), black and white, double-sided: 4 billed pages on 2 sheets, 125 + 3 x 20 = 185 cents a letter, 2,035 cents for 11 (`$20.35`); standard would be 105 + 3 x 20 = 165 cents and 1,815 in all, with the 4040(a)(2) note. A fifth page would bill 6 pages, 125 + 5 x 20 + 225 = 450 cents a letter, 4,950 in all. Fingerprint `7f3a91c2d0b4`. Mailing batch 4012, Oct 3 09:40: 11 sent, 0 failed, 0 cancelled, charged $20.35, guide $20.35 (matches). A week on: 9 delivered, 1 re-routed, 1 returned (follow-up owed, linked to the notice `mailing-notice-2099-10`). `sent.jsonl` for it: `{"sent":"2099-10-03T09:40:12+00:00","pdf":"annual-notice.pdf","pages":3,"units":[...],"mailClass":"standard","guideCents":165,"batches":[{"id":4012,"costCents":1815,...}],"letters":[{"id":9001,"communication":7001,"costCents":165,"status":"processing"},...]}`.

## Decisions for the user

1. **Adopt the two-person kind** `payhoa-mailroom-send` (recommended: phase 4, terminal apply only, after the fingerprint ships), or keep a command with `--preview ID --expect`? And the key: `payhoa-mailroom-send` (the registry's style, members-cycles.md) or `mailroom-send`? Adopting changes the AGENTS.md sentence on who mails.
2. **Drop the `payhoa.mailroom.cancel` kind** (recommended) and log cancels as commands?
3. **Mail class (settled in part, 2026-10-11).** First class or better is what 4040(a)(2) lists for an individual notice to a member with no valid delivery method; the command now takes `--mail-class first-class`. Decided 2026-10-11: a `--notice` letter defaults to first class, and the earlier standard mailings are a board item (`mailroom-class-individual-notice`). Open for counsel: which mailings are individual deliveries, so when standard is allowed. Lesson `mailroom-class-for-individual-notice`.
4. **Co-owners and secondary records.** The command mails every `isIncluded` row, with no way to leave one out. Add `--exclude OWNER_ID`? And whether PayHOA bills one letter per owner row or per address for a one-off send is not verified; the read-back's count settles it after the fact.
5. **Where the PDF comes from.** A path under `data/` the person names, the approved letter's file, or a Drive export? A picker needs a folder the loader may list.
6. **More than four pages.** Warn only (as drawn), or require a named person's choice recorded in the plan?
7. **A console "Read again" job** (PayHOA lane), with `mailroom` added to the job classes, or terminal only through phase 2?
8. **Preview age limit** (24 hours proposed) and whether "links tested as an owner" is required before the command is shown (lesson `letters-cannot-be-recalled`).
9. **Group and phase.** Governance beside Notices (drawn), or Money, since postage is money? Phase 2 for the preview, phase 4 for the kind.

## Acceptance criteria

1. The preview page renders its five bands in order from the saved record for a fixture, and shows "Not mailed" with no control that mails, cancels, or queues anything.
2. Every money figure is integer cents shown as dollars by `Money`; the page total equals letters x cents a letter; the guide's date is shown beside it.
3. For 4 PDF pages the page shows 5 billed pages, $1.85 a letter at standard class ($2.05 first class), no heavy line; for 5 PDF pages, 6 billed, $4.30 standard ($4.50 first class), and the "$2.25 more postage" line with the saving.
4. A named address that matches no unit is listed as not found and never dropped silently; the matched, left-out, and duplicate counts add up to the PayHOA rows (as counts before masking exists, as rows after).
5. Once masking exists, each recipient row says what resolved it: the units table (with its sync time) and PayHOA's mailing or unit address (with its read time).
6. Changing the PDF, syncing `payhoa.db` after the read, or ageing past the limit each shows `ChangedBanner` naming the cause and the command to read again.
7. The send `Command` names the count and total and the sentence that a letter cannot be recalled; the page has no Send button even when the server runs with `--allow-apply`.
8. A `processing` letter shows the cancel `Command` and the minutes-window words; no cancel button exists, and the page invents no cutoff.
9. A returned, re-routed, or failed letter shows the event word, then jason's reading labeled as jason's, and links the notice's follow-up; no statute text is paraphrased on this page.
10. A send with an empty read-back shows "Sent, not read back" and offers no second send.
11. With the viewer's offices below P2 the response carries counts, pages, price, and fingerprint, and no name, unit, or address (checked in the HTML and the JSON); the owner view is refused.
12. No `/api/file` link, absolute path, address, or name appears in a URL; PayHOA's proof opens through `Doc` and is logged.
13. Under the proposal: the plan has one item, two distinct signers, the cost, and the fingerprint; a re-plan that differs supersedes it; nothing is sent until a person runs the printed command.
14. A director reads the same page an officer reads at the same level.
15. The preview's first line names the class, tracking, color, and sides; a standard preview shows the note and the 4040(a)(2) words in a `Recitation` before jason's labeled reading; a combination PayHOA refuses (tracking or an invoice with standard; an invoice two-sided) is never offered.
