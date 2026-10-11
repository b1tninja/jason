# Design brief: the payments workbench (bill attach and the investigation) and the mail workbench

One page of orientation for the design agent, for the two manager workflows in [handoff-mail-and-payment-attachments.md](handoff-mail-and-payment-attachments.md). It does not repeat the handoff; it says what to read in what order, which parts can be drawn from real data today, each screen and component with its data and states, the words to use, and a made-up community to design against. Where the handoff and this page disagree, the handoff's "Checked against the code" and "What the build adds" win, and this page is corrected.

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, bank, or private fact; made-up samples only ("123 Main St", "Example County", "Example Alarm").

## A. The idea, and the rules that run through it

**The idea, in six sentences.**

1. The bank feed brings PayHOA payments with no document; the treasurer reviews them only when a bill is attached, so the manager's job is to **find the bill, or say plainly why it cannot be found**.
2. Most waiting payments are not mysteries: a transfer between the association's own accounts, interest, and a platform fee have no bill at all, and the screen **hides those by default** and says how many it hid.
3. The rest are work items. A payment a bill source owns is found by that source's own sync; a payment no source owns (a county tax collector, an insurer, an unknown ACH) gets an **investigation**: what jason searched, what each store held, and one recommended next step.
4. A document and a proof of payment are different things. A bank notice or a county receipt proves a payment was sent; only a bill can be attached as the bill.
5. jason attaches nothing from this screen yet: every sync and every attach is a command a person runs, and the person's **outcome** (attached the bill, attached the receipt only, not our bill, waiting for mail, escalated) is the one thing the screen records, in their name.
6. The mail workbench is the same shape for email: what is awaiting us, whose move it is, a suggested follow-up with its basis, and a draft a person saves; jason never sends.

**The rules** (each is in the handoff's hard rules; a screen that breaks one is wrong):

- **Nothing here attaches, approves, sends, or pays.** Every act is a `Command` ("A person runs this") until a console write exists, and then a `Confirm` recorded by name. No `Stamp`: nothing here is a decision of the board.
- **Every number says how old it is.** The queue is as old as the PayHOA snapshot; the dry run is as old as its run and says which snapshot it ran against; each store the investigation searched shows its own age. A store never read is "not read" with its command, never a zero.
- **A match is a lead until a person attaches it.** Exact amount, a date in the window, and no other bill that fits. Say which date matched. Two documents that fit attach neither.
- **A reading or a hit is evidence.** "A message whose subject names this amount" is a lead; it is never "the bill".
- **No row without a reason.** A row's status is the engine's own word (below); the page never invents a state.
- **Names, amounts, and ids only.** No owner address, no message body, no account holder. An APN shows its last four; a bank account shows its last four, and only to an office that opens P2.
- **A proposed number is labeled proposed** ("proposed: ask again in 7 days"). A date the board has not adopted carries no stamp.
- **Color is never alone.** Every status is a word and a glyph.

## B. Reading order

1. [handoff-mail-and-payment-attachments.md](handoff-mail-and-payment-attachments.md): the table "Checked against the code" first, then Parts A to C.
2. This page's section D (the components) beside section H (the sample).
3. [handoff-admin-components.md](handoff-admin-components.md) for `Command`/`TerminalStep` and the freshness pattern; [handoff-forms-and-arrivals.md](handoff-forms-and-arrivals.md) for the two-view idea (forms and campaigns, deadlines and follow-ups) this page reuses for bills and mail.
4. [handoff-draft-from-item.md](handoff-draft-from-item.md) and [handoff-conversations-and-policies.md](handoff-conversations-and-policies.md) for the mail side.
5. The county tax collector's portal note, [the profile's county-tax-portal.md](../../mystique/docs/county-tax-portal.md), only for the receipt candidate's meaning.

## C. The screens

| Screen | Route | Reads | Status |
|---|---|---|---|
| **Bill attach** | a tab of `#/payments`, beside "Invoice review" | `GET /api/bill-attach?source=&status=` | **Built (loader).** Draw from real rows |
| **Investigation** | a drawer over the queue; `#/payments/attach?tx=ID` for a link | `GET /api/bill-investigation?tx=ID`; writes `POST /api/write/bill-investigation/<tx>` | **Built (loader and writer)** |
| **Invoice gaps** (band) | `#/payments`, Invoice review | `GET /api/invoices` | Built |
| **Inbox, email awaiting us** | `#/inbox`, tab "Email awaiting us" | `open_items.threadsAwaitingUs` | Built (read-only table); the workbench is this brief's design |
| **Thread drawer** | over the Inbox row; later `#/conversations/<id>` | `email_threads`, the draft cases | Drawer: design now. Route waits on the Gmail catalog |

### C1. Bill attach (the tab)

```
+--------------------------------------------------------------------------------------------+
| Bill attachments                                                                             |
| PayHOA snapshot Oct 9, 02:10 (1 day old)  [fetch again: jason invoices --fetch]              |
| Last dry run Oct 9, 11:40 by Pat Example, against this snapshot   [run it: jason sync-bills]  |
+--------------------------------------------------------------------------------------------+
| 19 waiting on a bill      Sources to sync: idoxs             26 expect no bill [show]        |
|  1 not checked · 8 no source yet · 10 unrouted                                               |
+--------------------------------------------------------------------------------------------+
| Filter: [Source v] [Status v]                                       [ ] Show "expects no bill"|
| Date    Payee line                        Amount     Class         Source   Status        |
| Oct 9   ACH CITY OF EXAMPLE               $28.26     —             idoxs    matched (cache)|
| Oct 7   ACH EXAMPLE COUNTY TAX COLLECTOR  $363.57    county-tax    —        no source yet  |
| Oct 5   ACH SOMEONE ELSE                  $412.00     unknown       —        unrouted       |
+--------------------------------------------------------------------------------------------+
| (a selected row opens the Investigation drawer, or the Match panel for a routed row)         |
+--------------------------------------------------------------------------------------------+
```

- **Top band.** Two ages, in this order: the snapshot (the queue is as old as it) and the last dry run (applied only if it ran against *this* snapshot; otherwise "an earlier dry run, from snapshot DATE, is shown greyed"). Each age has the command that refreshes it as a `Command` with copy.
- **Counts.** One line of counts by status, then "N expect no bill" with a toggle. A count that cannot be made is a dash with its reason.
- **Table.** One `DataTable`; amounts right-aligned in tabular figures; the date column sorts newest first; selecting a row opens the drawer. A row's payee line is the bank text as PayHOA holds it (P1), cut to one line with the full text on focus.
- **Status words** (the engine's, and the glyph for each): `not checked` (clock), `matched` (check), `ambiguous` (alert), `no match` (minus), `already attached` (paperclip), `uploaded` (check), `error` (alert), `unrouted` (question), `no source yet` (route), `no bill expected` (minus-circle). A matched row also says which date matched ("by due date" for the electric utility; "by bill date" otherwise) and whether the PDF is local or will download lazily.
- **Hidden by default:** `no bill expected`. The toggle shows them with a quieter row style, never removes the count.

### C2. Investigation (the drawer)

```
+------------------------------------------------------------------+
| Oct 7 · $363.57 · ACH EXAMPLE COUNTY TAX COLLECTOR                  |
| Class: county-tax (by the row "the county tax collector's ACH line")|
| Source: none yet                                                    |
+------------------------------------------------------------------+
| Recommended                                                         |
|  Read the county tax catalog, then look for this amount             |
|  [Copy: jason sync-tax]   Why: a county payment is found in the     |
|  tax catalog or the mailed bill, not a utility portal; the bank     |
|  notice found is proof of payment only.                             |
+------------------------------------------------------------------+
| What jason searched                      result        read          |
|  The profile's payee rows                matched       —             |
|  Other attachments of the same amount    none          Oct 9         |
|  The county tax catalog                  not read      —  jason sync-tax|
|  The library's readings                  none          —             |
|  Paper mail                              none          —             |
|  Gmail headers                           near          Oct 9         |
|  Vendor portals                          none          —             |
|  The county's or a vendor's own site     not read      a person's step|
+------------------------------------------------------------------+
| Found                                                               |
|  PAYMENT PROOF · lead  A message whose subject names this amount    |
|  (Oct 7) — a bank notice: proof a payment was sent, not the bill    |
+------------------------------------------------------------------+
| Record what happened   ( ) Attached the bill  ( ) Attached the     |
|  receipt only  ( ) Not our bill  ( ) Waiting for mail  ( ) Escalated|
|  [record in my name]   History: waiting for mail — Pat, Oct 8      |
+------------------------------------------------------------------+
```

- **Header.** The payment as the bank printed it, the class, the row that selected it (or "No row selects this payee: propose one"), and the source. A routed payment's header says which source owns it and sends the reader to the dry run (the recommendation is "Run the dry run for SOURCE").
- **Recommended** is one sentence, one command at most, one reason. It never offers a bank notice or an earlier same-amount attachment as the bill.
- **What jason searched** is a table of the stores, in a fixed order, each with its result word (`none`, `near`, `exact`, `ambiguous`, `not read`) and its age. A `not read` row carries the command or the human step that would read it. This table is the page's honesty: a person can see what was not looked at.
- **Found** lists at most five candidates per store, document candidates before proofs of payment, each with a **kind** (bill, receipt, bank notice, mail scan, tax catalog, portal invoice), a **confidence** word (exact, near, lead), an **evidence** chip (DOCUMENT or PAYMENT PROOF), its date and what the date means (bill, due, sent, received), and one sentence on why it matches. A store with more than five shows "N more of the same amount not shown". P2 candidates (mail, Gmail) show "a scanned letter names this amount" or "a message whose subject names this amount" to an office that does not open P2, with no subject, sender, or file.
- **Record what happened.** Five outcomes, in the handoff's words. `Attached the bill` and `Attached the receipt only` ask for the record they point to (a library id, or `gmail:ID`) and refuse words. The note is optional (300 characters). The `Confirm` text: "Record NAME's outcome 'waiting for mail' for the payment of $363.57 on Oct 7. This attaches nothing and approves nothing." History lists every earlier outcome, oldest first; the last one stands; none is erased.

### C3. The match panel (a routed row)

For a row a source owns, the drawer shows the **Match panel** instead of the search table first: the bill the dry run chose (bill id, bill date, which date matched, amount, local or lazy PDF, a `Doc` preview when the PDF is local), the transaction beside it, and the command to attach (`jason sync-bills --yes --source SOURCE`, copy). If the dry run said `ambiguous`, both bills are listed and neither has an attach command. If it said `no match`, the investigation table follows. A match panel for a dry run older than the snapshot is greyed with "run it again".

### C4. The mail workbench (the Inbox's email tab and its drawer)

```
+--------------------------------------------------------------------------------------------+
| Email awaiting us (14)        Gmail read Oct 9, 06:10 (1 day old)  [read again: jason gmail --sync]|
| "A thread is listed when the last message was not ours. Someone may have answered by phone or at|
|  a meeting; jason cannot see that."                                                             |
+--------------------------------------------------------------------------------------------+
| Likely  Subject                    From (role)        Age     Usual reply   Suggestion         |
|  yes    Parking permit             owner of 123 Main   0 d     within 2 d    reply by Oct 12 (proposed)|
|  no     Quarterly newsletter       vendor              6 d     —             no usual reply time on record|
+--------------------------------------------------------------------------------------------+
```

- A row opens a **drawer**: the thread's headers (never a body), the people by role ("owner of 123 Main St", never an address), `RelatedLeads` (a payment, a paper letter, a Drive filing, a unit request near the thread, each labeled a lead), the `FollowUpSuggestion` with its basis, and the entries "Draft a reply" and "Mark handled offline".
- **Draft a reply** shows the existing draft command (`jason draft ...`) as a `Command`; the person saves the draft in Gmail themselves. It never says "send". When a draft approvals kind exists, a `Confirm` replaces the command.
- **Mark handled offline** is a person's word with a name and a date in a store of jason's own; it never changes Gmail, and a later message from the sender reopens the row.
- **Stale warning.** If the Gmail read is older than the integration's stale-after, the page's first line says "what is awaiting us may be out of date".

## D. The shared components, each once

Reuse (built): `DataTable`, `Tabs`, `Card`, `Stat`, `Pill`, `Badge`, `Glyph`, `Caveats`, `Command`, `Confirm`, `Doc`, `DueDate` (with `settled` for a satisfied date), `Findings`, `RemoteView`, `Evidence`. Spec'd, not built (draw from the built parts and say so): `ConversationList`, `DraftFromItem`, `ComposedEmail`, `DraftTrail`.

| Component | What it is | Data (the real field names) | States |
|---|---|---|---|
| `AgeBand` | The page's top band: the snapshot's age and the dry run's age, each with its command | `snapshot{syncedAt, ageDays, staleAfterDays, stale, command}`, `dryRun{ranAt, by, windowDays, snapshotSyncedAt, currentWithSnapshot, command}`, `dryRunCommand` | fresh; stale (the page's first line is the warning); missing snapshot (`found:false`, `reason`, `command`); no dry run yet ("none kept; run it"); dry run older than the snapshot (greyed) |
| `PendingUtilityQueue` | The table | `rows[]{transactionId, amountCents, date, description, category, vendor, excluded, attachments, source, payeeClass, status, dryRun{status, detail, bill{id, source, date, hasPdf}}, earlier}`, `counts`, `withoutPdf`, `sourcesNeeded` | loading; error with Retry; empty ("Nothing waits on a PDF in the snapshot of DATE", never "all caught up"); missing; a filter that matches nothing |
| `StatusWord` | The status as a word and a glyph | `status` | the ten words above; unknown word → neutral, with the word shown |
| `MatchPanel` | A routed row's chosen bill | `dryRun.bill`, `source`, the row | matched; ambiguous (two bills, no attach); no match; earlier (greyed) |
| `InvestigationCard` | The drawer | `routing{payeeClass, source, byRule}`, `tried[]{source, result, readAt, note}`, `candidates[]{kind, label, amountCents, date, dateMeaning, confidence, evidence, why, hasPdf, doc, link}`, `recommend{action, command, reason}`, `outcome`, `history[]`, `outcomes[]`, `private`, `snapshotSyncedAt`, `caveats[]` | found; `found:false` with `reason` and `command`; held (P2 candidates without detail); recorded (an outcome stands) |
| `SearchedStores` | The "What jason searched" table | `tried[]` | per row: none, near, exact, ambiguous, not read |
| `CandidateRow` | One found item | `candidates[]` | document / payment proof; exact / near / lead; with and without a `Doc`; held label |
| `OutcomePicker` | The five outcomes, the record field, the note, the `Confirm` | `outcomes[]`, `history[]` | pick; asks for a record (two outcomes); recording; recorded; refused while viewing as someone else (403, the page says so) |
| `SyncBanner` | Mail: the Gmail store's age and the command | `syncedAt` of the Gmail store | fresh; stale; never read |
| `FollowUpSuggestion` | One line: action, proposed date, basis, command | basis word (`response standard`, `reply rate: 4 of 5`, `stalled handoff`) | proposed; no basis ("no usual reply time on record"); accepted by a person (their date) |
| `RelatedLeads` | Leads near a thread | kind, label, why near, a `Doc` or link | none; some; P2 held |

**Fixed words** (use exactly): "expects no bill" (the group), "no source yet", "unrouted", "not checked", "the bank notice proves a payment was sent; it is not the bill", "a lead until a person attaches it", "no rule selects this payee: propose one", "not read — the command", "Run the dry run for SOURCE".

## E. Glyphs

Use the glyphs the console already has; propose a new one only for what no existing glyph can say, and name it for the idea. Needed: a clock (not checked), a check (matched, uploaded), an alert triangle (ambiguous, error, stale), a minus (no match, no bill expected), a paperclip (already attached), a question (unrouted), a route or signpost (no source yet), a receipt (payment proof), a document (bill), an envelope (mail), a lock (held). Every glyph sits beside a word.

## F. Decisions that are the design's, in one list

1. **A tab or a route.** A tab of `#/payments` beside "Invoice review" (recommended): the two read the same payments. A drawer, not a page, for the card, so the queue stays in view.
2. **How `no bill expected` is hidden.** A toggle with the count always shown (recommended), versus a separate tab. The live data had 26 of 74 in this group; a person must see that they were set aside.
3. **How the status filter and the source filter combine** with the toggle.
4. **Whether the Match panel and the Investigation are one drawer with two modes** (recommended) or two.
5. **The Confirm's wording for the five outcomes**, and whether an outcome that points to a record shows a `Doc` preview of it.
6. **Mail: a drawer first or a route first.** The drawer ships on what is built; the route waits for the conversations loader. The drawer's parts must move to the route unchanged.
7. **How a stale snapshot shows**: the whole queue greyed, or the first line only (recommended: the first line; the data is still the best there is).
8. **Narrow widths** (under 720 px): the table becomes cards (payee, amount, status word); the drawer becomes a full page; the age band stacks.

These are not the design's: the treasurer's rule on whether a receipt may stand in for a bill (the handoff's open decision 4), what a county payee row says, and whether `sync-bills` ever runs on a schedule.

## G. What can be designed now, and what waits

| Part | Now | Waits on |
|---|---|---|
| Bill attach tab, queue, `AgeBand`, `StatusWord` | Yes, from real rows | — |
| Investigation card, `SearchedStores`, `CandidateRow`, `OutcomePicker` | Yes, from real cards and the outcome writer | — |
| Match panel's `Doc` preview | Yes for a local PDF | The kept dry run holds the bill id and `hasPdf`, not a path; the preview needs the bill's `DocRef` (a build item) |
| The attach itself (a `Confirm`) | The `Command` only | An approvals kind `payhoa-attach-bills` |
| A county receipt candidate (kind `receipt`) | Draw it (an exact payment proof naming the bill) | The county-tax receipts store (in progress) |
| Mail drawer and `SyncBanner` | Yes | — |
| Conversation route, `ConversationList` | No | `gmail_catalog` and its loaders |
| Gmail draft as a `Confirm` | No | A draft approvals kind |

## H. A made-up community to design against

"Oakview" has these waiting payments (amounts in dollars here; the loaders send integer cents). Use them for every state.

| Payment | Bank line | Amount | Class | Source | Status | The point it makes |
|---|---|---|---|---|---|---|
| A | ACH CITY OF EXAMPLE | $28.26 | — | `idoxs` | matched (cache), bill date | The happy path |
| B | ACH EXAMPLE ELECTRIC | $61.29 | — | `smud` | matched, **by due date** | A date that is not the bill date |
| C | ACH EXAMPLE COUNTY TAX COLLECTOR | $363.57 | county-tax | — | no source yet | The case study: a bank-notice lead, the tax catalog not read |
| D | ACH SOMEONE ELSE | $412.00 | unknown | — | unrouted | "No rule selects this payee: propose one" |
| E | EXAMPLE ALARM | $150.00 | field-vendor | `example-alarm` | ambiguous | Two bills fit; neither is attached |
| F | ONLINE TRANSFER FROM CHK ...1234 | $2,000.00 | transfer | — | no bill expected | Hidden by default |
| G | INTEREST ADDED | $1.12 | bank-item | — | no bill expected | Hidden by default |
| H | ACH EXAMPLE INSURANCE | $740.00 | insurance | — | no source yet | The insurance letters and the agency's email |

Card states to draw: C with only a Gmail proof (the recommendation: read the catalog; "the bank notice found is proof of payment only"); C after `sync-tax`, with a tax-catalog bill that has a PDF (recommendation: "Check tax bill B1 (2026) against the payment, then attach it", a lead until attached); C with a county receipt (exact, payment proof, naming the bill); D with nothing found ("Hold for a person"); E with two documents ("Choose between the documents that fit; attach none"); a payment whose outcome is `waiting for mail` (history shows it, the card says what would reopen it); a viewer who does not open P2 (labels held, no link). Mail: "Parking permit" from the owner of 123 Main St, awaiting us, age 0, a usual reply within two days, a related pending PayHOA request as a lead; a thread with no usual reply time on record; Gmail read three days ago (stale).
