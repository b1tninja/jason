# Design brief: Notices and the Mailroom (a notice from its requirement to its proof, and the letter that carries it)

One page of orientation for the design agent, for two screens that tell one story: [screens/notices.md](screens/notices.md) (`#/notices`) and [screens/mailroom.md](screens/mailroom.md) (`#/mailroom`). It does not repeat the specs; it says what to read in what order, each screen and component to draw, what can be drawn today, and a made-up community to draw against. The reference for the law is [../notices.md](../notices.md); the run that links to both is in [screens/work.md](screens/work.md) and [../workflows/members-cycles.md](../workflows/members-cycles.md) (`notice-delivery`, `mailroom-letter`). **Neither screen is built in `ui/src`** (checked 2026-10-11: no `#/notices` or `#/mailroom` route, view, or loader; only the parts in section D exist). The CLI and the stores behind them are built, so every screen below is drawn from the sample in section H.

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, bank, or private fact; made-up samples only ("123 Main St", "A. Owner", "Example County", dates in 2099).

## A. The idea, and the rules that run through it

**The idea, in seven sentences.**

1. A notice has one story: **required, drafted, mailed or emailed, delivered, followed up, proved.** Notices shows the whole story for a notice; the Mailroom shows one chapter, the paper letter, in the detail a mistake needs.
2. Notices answers: **what does the law require, what exactly went out, to whom, what became of each delivery, what is still owed, and what is the evidence?** Six bands, always in that order.
3. The Mailroom answers: **what will this letter do before anyone mails it?** Whom it reaches and at which address, how it prints, what it costs, what must be true first, and the one line a person types.
4. A letter cannot be recalled (lesson `letters-cannot-be-recalled`; the cancel window is minutes). So the page puts the whole cost of a mistake in front of the person before they type.
5. A preview is not a promise: the send asks PayHOA for the recipients again. The **fingerprint** (a short hash of the PDF, the recipients, and the options) is what a person checks the later send against.
6. A returned or bounced notice is not a failed notice: the delivery was made on deposit or transmission, and the address is not good. What is owed next carries its **basis word**: required by the law, or the association's policy.
7. The page reads; a person acts at a terminal. **No button on these screens mails, cancels, or queues a send.**

**The rules** (each is in the specs; a screen that breaks one is wrong):

- **jason never mails on its own initiative.** Only a person's `--send --yes` mails. The send is a `Command` with the exact line, the count, the cost, and "This mails N letters and charges the association $X. A letter cannot be recalled." This holds even when the server runs with `--allow-apply`.
- **Directors and officers have the same access to information.** One page serves the manager, the president, the vice president, a director, the secretary, and the treasurer at the same level. They differ in duties, not in what they may read. The secretary records the board's decisions and postings; the treasurer is the usual second signer where money is spent.
- **Recite, then label the reading.** The statute's operative words come first in a `Recitation` with their citation; jason's reading follows in a `ReadingLabel` ("jason's reading, not the statute's"). The kept text of a notice is **quoted** (a block with its source and sha256), styled apart from a recitation so no one takes a notice's words for the governing words.
- **Proof of notice is evidence.** Whether notice was sufficient is for the board or counsel. A window missed reads "OUTSIDE the window", with: "Whether notice was sufficient is for the board or counsel; often the cure is a new date."
- **Counts by default.** Every band is counts only. A member's name, unit, and address are P2 and appear only in the private view; until masking is built the recipient table is not drawn for real, only counts, flags by count, and cost. A URL carries a key, an id, or a fingerprint, never a unit, name, or address.
- **Every figure says how old it is** (the status read, the units table sync, the preview, the ledger sync). A store never read is "not read" with its command, never a zero.
- **Amounts are integer cents**, shown through `Money`. The guide is "a price list with a date, not a law".
- **State is a word and a glyph, never colour alone.**

## B. Reading order

1. [screens/notices.md](screens/notices.md): the list, the six bands, the states.
2. [screens/mailroom.md](screens/mailroom.md): the five bands, "The mail options", "The send plan: a proposal" (a proposal, not built), and the states.
3. [../notices.md](../notices.md): "Two kinds of notice", "When an owner cannot be reached", "Proof of notice", "A notice as a record".
4. [../workflows/members-cycles.md](../workflows/members-cycles.md) sections 2.2 (`notice-delivery`, ND-01 to ND-13) and 2.3 (`mailroom-letter`, ML-01 to ML-07).
5. This page's section D beside section H. Then [screens/work.md](screens/work.md) and [design-brief-work.md](design-brief-work.md) for how a run links in (G below).

## C. The screens

### C1. Notices (`#/notices`), the list

A header ("12 notices in the ledger · 2 with follow-ups owed · 10 with none") and **[The catalog]**. A table: key, reached ("46 of 48", "posted"), follow-ups owed (the count, the action, a basis pill), synced (time, or a dash). A row's whole width links to `?key=`. Draw: the empty state ("No notices in the delivery ledger. `jason notices KEY --sync` reads one."), a row never synced, a row with follow-ups owed by law, one posted (general notice, no sync), and the catalog (`?catalog=KEY`: recipients, methods, clocks, content, the documents' clauses).

### C2. One notice (`?key=KEY`), six bands

Above the bands: breadcrumb, the record address `jason://notice/KEY` and the proof address, each with Copy, and `jason notices KEY` as a `Command`. Then, always in this order:

1. **The requirement.** Title and catalog key, how the key was matched, to whom, by what method, the clock in words. The statute's words in a `Recitation` (passage marked), each governing-document clause in its own `Recitation` followed by its `ReadingLabel`. Draw: a match; no requirement fits the key (the fix is named).
2. **The text as sent.** Subject; the kept text in the quoted style; source, sha256, and "unchanged since kept" or the **EDITED** line; who kept it and when; the fill records. Draw: kept, edited, and not kept.
3. **Recipients.** The plan's counts (emails, letters, secondary) and each batch with its sent count and state. Ids and counts only.
4. **Delivery.** "46 of 48 reached", the outcome counts (ten outcomes, one word and glyph each), the sync time with `jason notices KEY --sync` as a `Command`, and **Owed**, one line per follow-up with its basis word. Draw: synced, never synced, synced a week ago.
5. **Proof of notice.** The window, "went out Oct 1: in time" or "OUTSIDE the window", the evidence items (on file, to attach, owed), who was reached only after the last day, "Not yet complete." Draw an edited text counted as not on file.
6. **The stage it served.** A meeting's notice, a rule change's stage, or the minutes' availability, linking out.

Below: the caveat, verbatim (`notice_record.CAVEAT`).

### C3. The proof page (`jason://notice/KEY/proof`)

Band 5 as a printable page: a `Doc` with the notice's label, the requirement, the window, the evidence list, the reached/unreached/late counts, and the caveat. A date field (event day, and for a general notice the day posted) re-renders it and stores nothing. Draw the print layout, and a page with a window missed.

### C4. Follow-ups owed and the resend

The ten delivery outcomes are `pending, mailed, delivered, opened, bounced, unknown, skipped, failed, returned, rerouted`. The six follow-up rows are the data (`FOLLOW_UPS`): a bounced email (resend by first class, **required**); an email not shown delivered, or skipped for no email (resend by mail: **policy**, and **required** for no email on file); a letter that never mailed (send again, **required**); a letter returned (**policy**: use another address on file, ask for a current one); a letter forwarded (**policy**: ask the member to confirm the address; no resend). Each shows its authority chip (for example "CIV 4041(e), 4040(a)(2)") and, for a resend, **[Plan]**, which today shows the dry-run command and later creates a two-person approval with the cost shown. "Ask for a working address" is a task for a person, not a console action. The days a resend should follow an outcome (three, in the run's step) are a **proposed policy**, never a stamp.

### C5. The Mailroom list (`#/mailroom`)

A strip ("Can send: return address on file, payment on file; read Oct 3"; "Return address MISSING" or "Payment MISSING" becomes a band above all, with the command dimmed). Saved previews (letter, units, total, age, current or stale). Mailings newest first (batch, date, sent, failed, cancelled, pages, charged against the guide, matches or differs). Draw: no previews yet; cannot send.

### C6. The preview (`?preview=ID`), five bands

Header: "Preview 7f3a, read Oct 3 09:14 (2 h ago) by A. Manager", "Not mailed. This page cannot mail anything." A `ChangedBanner` only when stale. Then:

1. **The letter.** `DocumentPreview` of page 1 (a page strip on the left), page count and sha256, PayHOA's proof (drawn for the first recipient; the address page is not in it), the notice it serves and its last day to send with a basis pill.
2. **Whom it reaches.** "11 letters · 1 left out · 1 not found"; typed 12, matched 11 (the units table, synced); the send-to choice; the recipient table (unit, name, address, resolved from, flag). Flags are words: matched, not found, left out by PayHOA, duplicate, no address, mailing = unit address. Counts-only form first; rows when masking exists.
3. **How it prints and what it costs.** The first line names the class, tracking, color, and sides. `PrintedPages` (address page, p1, p2, p3 on sheets), the per-letter sum, the total (`CostLine`), the guide date. The heavy-postage line at five letter pages.
4. **Before it goes.** `SendChecks`: met or owed, each with its source and time. Owed items offer a signed record behind `Confirm`. Open lessons are listed.
5. **To send it (a person, at a terminal).** The sentence, the `Command`, Copy. No Send button.

### C7. The mail options (inside band 3)

Read from PayHOA's own Mail Options step; the page shows what was chosen and **never offers a combination PayHOA refuses**.

| Option | Choices | Price | Rule shown |
|---|---|---|---|
| Shipping | Standard (2-3 weeks); First class (5-8 business days) | $1.05; $1.25, first page | An invoice goes only first class |
| Tracking | None; Certified; Registered | none; +$10.00; +$25.00 a letter | Offered only with first class |
| Printing | Black and white; Color | none; +$0.20 a page | |
| Sides | One-sided; Two-sided | the same | An invoice cannot be two-sided |
| Send to | Owners' mailing addresses (duplicates removed); the unit's address | | |
| Pages | The first is the base; each after $0.20 | | PayHOA's address page is billed; a sixth billed page adds $2.25 a letter |

**The class a notice needs.** Draw this as a `Recitation`, then a `ReadingLabel`. Recited, Civil Code 4040(a)(2), from the stored text: "If the member has not provided a valid delivery method pursuant to Section 4041, the association shall deliver the document by first-class mail, registered or certified mail, express mail, or overnight delivery by an express service carrier addressed to the recipient at the address last shown on the books of the association." (4040(a)(1) first requires the member's preferred method.) **jason's reading, not the statute's:** an individual notice to a member with no valid method on record goes first class or better, so a standard preview carries the note. Whether a given mailing is an "individual notice" is for the board and counsel; the page does not decide it. A letter kept as a notice defaults to first class; any other defaults to standard; the preview names the class either way.

### C8. Cost, the cancel window, and a letter after the send

- **The cost line.** "$1.85 a letter: $1.25 first page + 3 x $0.20; 11 letters = $20.35". Draw standard, first class, certified, color, and the sixth-page state ("6 billed pages: $2.25 more postage a letter; a page fewer saves it"; not blocked).
- **Processing, cancellable.** The words: "Processing. Lob's cancel window is minutes; PayHOA still shows processing after it closes, so a cancel can fail." Minutes since the send, then the `Command` (`jason mailroom --cancel LETTER_ID --yes`). The page invents no cutoff.
- **Sent, not read back.** "PayHOA accepted the send; its batch is not listed yet. Look in PayHOA's Mailroom before sending again." No second send is offered.
- **Returned, forwarded, failed.** The event word as PayHOA gave it, then jason's reading, labeled; the follow-up links to the notice. No statute is paraphrased on the Mailroom page.

### C9. The link back to the run

Both screens carry a **Run** link: the notice's `notice-delivery` run (`#/work/notice-delivery/KEY`, whose panel is the six bands) and the letter's `mailroom-letter` run (ML-04, "Mail it, only on a person's word", is a step jason never starts). From the run, the child rows link here. Draw the chip ("Part of run: Owner information 2099, step 13 of 25") and the link back from the run's links band.

## D. The shared components, each once

Built (`ui/src/components`): `Recitation`, `ReadingLabel`, `Clock`, `DueDate`, `Evidence`, `Caveats`, `Command`, `Confirm`, `SecondConfirm`, `ChangedBanner`, `CostLine`, `Money`, `DocumentPreview`, `Checklist`, `Timeline`, `Stat`, `Pill`, `Glyph`, `StageSteps`; also `Doc`, `DataTable`, `Card`, `Findings`, `PlanReview`, `RemoteView`. `Freshness` is in `CitedSections.tsx`. Specified, not built (draw from the built parts and say so): `TerminalStep`, `AgeStamp`, `DiffTable`, `MaskedField`. New to draw:

| Component | What it is | Data | States |
|---|---|---|---|
| `NoticeRow` | A list row | `key, reached, total, followUps[], synced, general` | follow-ups owed; none; posted; never synced |
| `NoticeBand` | One of the six bands | `n, title, body` | filled; empty with its sentence; stale |
| `KeptText` | The quoted notice | `words, source, sha256, edited, keptAt, by` | unchanged; EDITED; not kept |
| `OutcomeWord` | A `Pill` preset for the ten outcomes | `outcome` | ten words, each with a glyph; unknown shown plainly |
| `FollowUpLine` | One thing owed | `action, force, authority, count` | required; policy; none |
| `BasisPill` | The basis of a date or duty | `law`, `documents`, `proposed policy`, `person` | four words, each with a glyph |
| `ProofItem` | One evidence item | `evidence, state` | on file; to attach; owed |
| `MailingPreview` | The five bands | the preview record | current; stale; cannot send |
| `PrintedPages` | The address page and the letter's pages on sheets | `pages, sheets, blankBack, heavy` | even; a blank back; heavy |
| `MailOptions` | The chosen options, as words | `mailClass, tracking, color, twoSided, sendTo` | valid; the note for standard |
| `RecipientTable` | A `DataTable` preset | `recipients[]` | counts only; rows; zero matched |
| `ResolveWord` | A `Pill` preset | matched, not found, left out, duplicate, no address, unit address used | six words |
| `SendChecks` | A `Checklist` preset | `checks[]{met, source, at}` | met; owed; with a record |
| `Fingerprint` | The 12-character id with its age | `id, read` | current; differs |
| `TypedCount` | A `Confirm` preset: "type 11" | `n` | matches; does not |
| `MailingRow`, `LetterRow` | The list rows | `batch, sent, failed, charged, guide`; `status, event, tracking, cost` | processing; delivered; returned; failed |

**Fixed words** (use exactly): "Not mailed. This page cannot mail anything."; "This mails N letters and charges the association $X. A letter cannot be recalled."; "OUTSIDE the window"; "Whether notice was sufficient is for the board or counsel; often the cure is a new date."; "EDITED since it was kept: the words above are not the words sent."; "jason's reading, not the clause"; "Sent, not read back"; "required"; "proposed policy".

## E. Glyphs

Use the console's glyphs (`notice` exists). Name any new one for the idea: a *letter in the mail* (mailed), *envelope returned* (returned), *envelope forwarded* (rerouted), *envelope with an alert* (failed), *clock* (pending, unknown), *no address* (skipped), *seal* (the kept text, the fingerprint), *scale* (a legal basis), *locked sheet* (the fixed text). Each beside its word.

## F. Decisions that are the design's, in one list

1. **Notices and Mailroom as two screens** (drawn; the same Governance group) or Mailroom as a tab of Notices. Recommended: two, with the cross-links in C9.
2. **How the six bands fold.** All open (recommended for the proof read), or the done bands collapsed to a line each.
3. **Where the follow-ups owed sit:** inside band 4 (spec) and echoed in a band under the header.
4. **How the mail options show:** a row of words in band 3 (recommended) or a small table, with a disabled option shown and why.
5. **The Confirm's wording** for each signed record (recipients read, links tested, a posting) and whether the note is shown in the band.
6. **The cancel window:** how the minutes since the send show, without inventing a cutoff.
7. **Print layout** of the proof page.
8. **Narrow screens:** the recipient table becomes cards; the bands stack; the command stays one tap to copy.

These are not the design's: the two-person send kind and its key, the preview age limit, whether more than four pages needs a named choice, and which mailings are "individual notices" (the user's and counsel's, in the spec's decisions).

## G. What can be designed now, and what waits

| Part | Now | Waits on |
|---|---|---|
| Notices list, the six bands, the proof page | Yes, from section H | The `notices` and `notice` loaders (the record and the ledger are built) |
| The catalog row | Yes | `notice_requirements` loader |
| Follow-ups owed | Yes | — |
| Record a posting | The `Confirm`, signed by name | The writer |
| Plan a resend | The dry-run `Command` | An approvals kind (none for mail) |
| The kept text against the file now | A `Doc` block only | `DiffTable` |
| The Mailroom list and mailings, the read-back | Yes | The `mailroom` loader over `status.json` and `sent.jsonl` |
| The preview page | Yes | A saved preview record (today the recipients and total are printed and discarded), `--preview`, `--expect` |
| The recipient rows | Counts only | `MaskedField` |
| The mail options | Yes; built in the CLI as `--mail-class`, `--tracking`, `--color` | — |
| The send as a two-person plan | A drawing, labeled proposed | The approvals kind and the board's rule |
| A "Read again" job | The `Command` | `mailroom` in the job classes |
| Cancel a letter | The `Command` | — (never a button) |
| The run link | A chip and a link | The engine (`jason.workflows`) |

Verified in code: `jason mailroom` takes `--mail-class`, `--tracking`, `--color`, `--notice KEY`, `--by NAME`; a `--notice` letter defaults to first class (`default_mail_class`); `check_options` refuses tracking or an invoice with standard and an invoice two-sided; `sent.jsonl` now records `mailClass`, `tracking`, and `by`. No `--preview`, `--expect`, or `--exclude`.

## H. A made-up community to design against

"Oakview" has 12 units on Example Rd and these notices (all dates 2099).

| Notice key | Requirement | State | The point it makes |
|---|---|---|---|
| `owner-info-2099` | Owner information solicitation | 46 of 48 reached; 2 resend by law; synced Oct 3 08:40 | The full six bands; the follow-ups owed |
| `board-meeting-2099-10-07` | Board meeting notice | posted at the place the policy statement names, Oct 2; no sync | A general notice; posted |
| `rule-change-proposed-pets-2099-09-01` | Rule change, proposed | 48 of 48 reached; none owed; synced Sep 20 | A clean notice |
| `mailing-notice-2099-10` | (a key that matches no requirement) | text kept; sent by the Mailroom; one letter returned | The "no requirement fits the key" state |

**The Mailroom sample.** `annual-notice.pdf`, 3 pages, sha256 `9e2f4b7c1d0a5e33...`. The manager (A. Manager) typed 12 addresses; 11 matched (units table synced Oct 3 07:00) and `131 Main St` did not. PayHOA's rows: 12; one left out (no mailing address), one duplicate (a co-owner at one address); 11 letters. Four billed pages. **First class, black and white, two-sided: 125 + 3 x 20 = 185 cents a letter, 2,035 cents for 11 ($20.35).** With certified (+$10.00): 1,185 a letter, 13,035 in all. Standard: 165 a letter, 1,815 in all ($18.15), carrying the 4040(a)(2) note. A fifth letter page bills six pages: first class 450 a letter, 4,950 in all ($49.50). Fingerprint `7f3a91c2d0b4`. Mailing batch 4012, Oct 3 09:40: 11 sent, 0 failed, 0 cancelled, charged $20.35, guide $20.35 (matches). A week on: 9 delivered, 1 re-routed, 1 returned (follow-up owed, linked to the notice).

**States to draw.** The owner-information notice with bands 1 to 6 complete; the same with the text EDITED and the proof "Not yet complete"; the proof page with a window missed ("OUTSIDE the window") and one member reached after the last day; the "no requirement fits" notice; a notice not synced. The Mailroom preview current, then stale (the PDF's sha changed), then "Mailroom cannot send" (Payment MISSING); a standard preview with the note and the recitation; a six-page letter with the heavy line; a `processing` letter with the cancel `Command` and the window words; a send with an empty read-back; a viewer below P2 (counts, pages, price, fingerprint only); a director and the treasurer reading the same page; and the link chip to the run, "Owner information 2099, step 13 of 25".
