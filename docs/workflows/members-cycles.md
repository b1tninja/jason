# Members' cycles as durable workflows: the owner-information request, notice delivery, the Mailroom, answering requests, owner documents, and standard forms

Status: **design**. The family page for the member-facing cycles, written to the template in [workflows-design.md](../workflows-design.md#5-the-per-family-pages) (the workflow model, the seven step kinds, the run states, and the common screens are defined there and not repeated). Sources read for it: the procedures `owner-info-cycle`, `notice-delivery`, `mailroom-letter`, `respond`, and `owner-document` (`jason sop KEY`, `src/jason/community/procedures.py`), [owner-information.md](../owner-information.md), [notices.md](../notices.md), [batches.md](../batches.md), [responses.md](../responses.md), [response-standards-design.md](../response-standards-design.md), [followups-design.md](../followups-design.md), [responses-design.md](../responses-design.md), [form-library-design.md](../form-library-design.md), [standard-forms.md](../standard-forms.md), the journeys (a), (e), (j) in [console/journeys.md](../console/journeys.md), and the handoffs in [console/](../console/information-architecture.md). Every "exists" claim was checked against the repo on 2026-10-11; what could not be checked says **not verified**.

Rules this family keeps, from [AGENTS.md](../../AGENTS.md): jason never mails a letter on its own initiative, never approves, denies, or assigns a request, never sends a reminder, resends a notice, or completes a follow-up, and never deletes a live PayHOA form. Every write outside jason is a `plan` a person approves or a command a person runs. A number that is not the law's or the documents' is labeled **proposed policy**, and a question the law leaves open is held for the board. Amounts are integer cents.

## 0. How the six relate

Six definitions plus two small ones (the weekly sweep and the adoption of a response standard, in 2.4; the form library's yearly review, in 2.6). A run starts another by a **child run** linked from a step (the "links, not copies" rule): the parent step is `done` when the child is `done`, a failed child shows on the parent's rail, and each run has its own roles and clocks.

```text
owner-info-cycle (one a year; subject: the cycle)
  |-- owner-document ........ the email, the letter, the guide          (OI-10)
  |-- form-campaign ......... the form, one campaign a channel          (OI-04; its arrivals are step group IN)
  |-- notice-delivery ....... key owner-info-YEAR                       (OI-13, then OI-20)
  |       `-- mailroom-letter . each Mailroom send, and each resend      (OI-16, ND-07)
  `-- respond-request ....... an arrival that is also a request         (IN-03, when the answer asks for something)

respond-request (one a request)
  |-- owner-document ........ the acknowledgment, the decision letter   (RQ-06, RQ-17)
  |-- notice-delivery ....... only when the Act makes the answer a noticed act (RQ-17)
  `-- the board loop ........ #/agenda, #/decisions: a decision that is the board's (RQ-15, RQ-16)

form-campaign --(handler owner-information)--> owner-info-tags plan (IN-07)
form-campaign --(handler response-clock)-----> one respond-request per arrival (IN-03)
```

**Step group IN (response intake)** is defined once, in 2.6, and included by `owner-info-cycle` and `form-campaign`: check for arrivals, read, confirm, key a paper return, triage by the response policy, decide what only the board decides, record, enter what only a person can. The spine does not yet allow a definition to include a group or a step to need a child run; both are proposed under [Decisions](#11-decisions-that-are-not-this-pages).

## 1. The tasks

| Key | SOP | Task | Trigger | Subject |
|---|---|---|---|---|
| `owner-info-cycle` | `owner-info-cycle` | Ask every owner each year for delivery method, a second address, a representative, and occupancy; enter the answers in PayHOA | open in mid-September; answers by late October; entered by the day 30 days before the annual reports | the cycle (a fiscal year) |
| `notice-delivery` | `notice-delivery` | Know that each member was reached; deliver again where a message bounced, was skipped, or a letter did not mail; prove the notice | after every notice to members | a notice key (`REQUIREMENT-DATE`) |
| `mailroom-letter` | `mailroom-letter` | Print and mail a letter through PayHOA's Mailroom without a letter that cannot be recalled going out wrong | whenever the association mails owners on paper; started by a person | one letter (a PDF and its units) |
| `respond-request`, `respond-sweep`, `respond-policy` | `respond` | Answer a member's request on its clock; sweep the open requests weekly; adopt a written response standard | a request arrives; each week and the day before each board meeting; the board takes up a standard | a request; a week; a standard |
| `owner-document` | `owner-document` | Write an owner-facing email, guide, or notice once; make the Doc, the PDF, and the email from one file | whenever the association writes to owners | a document (a Markdown source) |
| `form-campaign`, `form-library-review` | `owner-info-cycle` and `respond` (the handlers' procedures); `law-review` | Offer a standard form to members, collect and process what comes back; keep the library current with the law | a form is offered or a cycle opens; each January's law review | a campaign (form, year, channel); a year |

## 2. The definitions

Column legend (the spine's step fields, merged to fit): **step (kind)** is the step's title and its kind (`check`, `job`, `plan`, `person`, `decision`, `wait`, `branch`); **role**: M manager, S secretary, P president, T treasurer, A administrator, B the board (by vote, recorded by S or P with the meeting's date), J jason, N a named person, "2P" a second distinct person; **produces / evidence** is the link kind it makes and what shows the step done; **clock (basis)** gives the basis the spine requires: law, documents, proposed policy, or person; **repeat / skip** is `once`, `per owner`, and so on, and who may skip. A step with a command is shown as the terminal runs it; every command that writes carries `--yes` and a name. No legal step may be skipped (the spine's recommendation); its absence is a finding for the board.

### 2.1 `owner-info-cycle` (subject: the cycle; dates: opened, return-by, reports mailed, and the entry day, which is reports mailed less 30 days)

Roles: M runs it; S, P, T are the approvers and the second person; B decides; A edits the profile and the definitions. Lessons that shaped it: `leave-room-to-correct`, `paper-cannot-require`, `form-link-needs-unit`, `test-as-an-owner`, `letters-cannot-be-recalled`, `letter-link-per-unit`, `bounces-are-silent`, `answers-need-a-policy`, `complete-only-after-writes`.

| id | step (kind) | role | needs | produces / evidence | command | clock (basis) | repeat / skip |
|---|---|---|---|---|---|---|---|
| | **A. Set up** | | | | | | |
| OI-01 | Set the cycle's dates (`person`) | A | | the dates on the run; the profile's `OWNER_INFO_CYCLE` row (a person edits the profile; jason does not) | `jason owner-info` (prints the dates) | entry day: law, 4041(b)(1); the rest: person | once / none |
| OI-02 | Dates leave room for one correction before the return-by date (`check`) | J | OI-01 | pass or fail with the gaps in days: opened to the first delivery sync, to a resend, to return-by | `jason owner-info` | proposed policy: no adopted minimum; the follow-ups use 1 day to sync and 3 to resend | on open and when dates change / a person records why not |
| OI-03 | Settle the decisions the cycle depends on: the rental-approval question, what to ask units likely not owner-occupied, co-owner envelopes (`decision`) | B | OI-01 | decision records (`data/board/decisions.json`); board items | `jason board --packet` | person (the board's); the law is silent, so the question is held | once / none; if undecided at IN-06 the occupancy follow-ups stay held |
| OI-04 | Open the cycle's campaigns, one a channel (email, mail, PayHOA), each naming form, version, and handler (`person`) | M | OI-01 | campaign rows (`data/forms/campaigns.json`); every generator refuses a form with no open campaign | `jason campaigns --open FORM --channel C --cycle-year Y --by NAME`; `--adopt` for a row the profile already runs | person | per channel / none |
| OI-05 | Update the PayHOA form in place; confirm it is live and locked (`plan`, **new kind** `payhoa-form-update`, R2) | M | OI-04 | form with question ids kept; locked in `data/payhoa/forms.json`; `payhoa_forms.live_problem` empty | `jason forms --payhoa owner-info --update` | person | once / none; `--replace` refuses a locked form |
| OI-06 | Round-trip made-up answers as the test owner (`job`, PayHOA lane) | M | OI-05 | every answer reads back | `jason forms --payhoa-test owner-info --yes` | person | once / none |
| OI-07 | Open each form link and QR target as an owner, signed out and signed in (`person`) | M | OI-05 | attestation: date, the link opened (carries `;unitId=`), lands on the form for the unit | none (jason never signs in) | person | per link / none |
| OI-08 | Build the letter and the fillable form from the template Docs (`plan`, **new kind** `google-doc`, R1) | M | OI-05 | Docs and PDFs; page count at most four | `jason packet owner-information --year YEAR --make-templates --yes`, then `--build --yes` | person (billing: a sixth billed page adds 225 cents a letter) | once / none |
| OI-09 | Plan who gets what: email, letter, or both; occupancy leads (`job`) | M queues | OI-04 | `data/owner-info/send-plan-DATE.md` (no addresses) | `jason owner-info --send-plan` | person | once, again if dates move / none |
| OI-10 | Write the email, the guide, and the letter once (`person`, child run `owner-document`) | M | OI-09 | child run done; Doc on the letterhead | inside the child: `jason broadcast data/drafts/NAME.md --to-doc --yes` | person | per document / none |
| OI-11 | Preview one owner's email, then send a test to yourself (`job`) | M | OI-10, OI-04 | preview HTML; subject names the unit; every form link carries `;unitId=`; pictures show | `jason owner-info --email-batch --message NAME.md --only me --preview OUT.html`, then `--yes` | person | once / none |
| | **B. Send** | | | | | | |
| OI-12 | Send the email batch (`plan`, **new kind** `payhoa-owner-info-email-batch`, R3, 2P) | M, 2P | OI-11, OI-07 | batch `owner-info-YEAR-email` all items sent, none `uncertain`; text kept in `data/notices/KEY/` | `jason owner-info --email-batch --message NAME.md --yes --confirmed-by NAME` | person (no statutory day to send) | per batch, resumable / none |
| OI-13 | Read the emails' delivery (`job`, child run `notice-delivery`) | M | OI-12 | child run open for key `owner-info-YEAR` | `jason notices owner-info-YEAR --sync` | proposed policy: the day after | once here, then ND-04.. / none |
| OI-14 | Wait for delivery results (`wait`) | | OI-12 | arrival: an outcome for every email, a second sync after 24 hours | | proposed policy (PayHOA fails a message with no delivery event after 24 hours) | once / none |
| OI-15 | The next day, test the emailed link as an owner again (`person`) | M | OI-14 | attestation | none | proposed policy (lesson `letters-cannot-be-recalled`) | once / none |
| OI-16 | Mail the letters, one Mailroom send per building (`plan`, **new kind** `payhoa-owner-info-mail-batch`, R3, 2P, cost shown; child runs `mailroom-letter`) | M, 2P | OI-15, OI-13 | batch `owner-info-YEAR-mail` in `data/batches.db`; each Mailroom send confirmed by a new batch in the Mailroom; letters read back as processing | `jason owner-info --mail-batch --yes --confirmed-by NAME` | person | per building / none: email first, letters after |
| | **C. Collect and record** | | | | | | |
| OI-17 | Group **IN**, repeating from the first send to the close | M, B | OI-12 | see 2.6 | see 2.6 | see 2.6 | per arrival / see 2.6 |
| | **D. Follow up and close** | | | | | | |
| OI-18 | Read what is due and who is outstanding (`check`) | J | OI-12 | the funnel (asked, answered by channel, read, confirmed, recorded, outstanding, unreachable) and the follow-up items, each with basis and the age of its source | `jason followups`; `jason campaigns --show CODE` | basis per item (4.3) | after each send, sync, and IN-01 / none |
| OI-19 | Remind the owners who have not answered (`plan`, same kind as OI-12, `--follow-up reminder`, 2P) | M, 2P | OI-18 | reminder sent to the outstanding only; the follow-up marked done by a person | `jason owner-info --email-batch --follow-up reminder --message REMINDER.md`, then `--yes` | proposed policy: 7 days before return-by (a campaign's own `remind-days` is a person's setting) | once / skipped, with the reason, when nobody is outstanding; jason never marks it done |
| OI-20 | Resend or ask for what failed (`branch`, child step `notice-delivery` ND-07) | M | OI-13 | count of members owed, from the ledger | see 2.2 | law (4041(e)); days: proposed policy | per member / none |
| OI-21 | Return-by date (`wait`) | | OI-12 | arrival: the date | | person (the association's date; the law's dates are named for what they are) | once / none |
| OI-22 | Last day to enter the answers: nothing confirmed and unrecorded, no plan open, no arrival unread (`check`, then `wait`) | J | IN, OI-21 | pass, or the gap listed as a finding for the board | `jason owner-info`; `jason responses --list` | law: 4041(b)(1) | on the entry day, daily before it / none |
| OI-23 | Close the cycle: move out the Unconfirmed Address records no owner confirmed; note what is open; close the campaigns (`person`) | M | OI-22 | PayHOA read shows none left; campaigns `closed` | `jason campaigns --close CODE --by NAME` (the PayHOA removal is a person's, or an `owner-info-tags` item) | proposed policy: 7 days after return-by (the response watch window) | once / none |
| OI-24 | The annual reports go out (`wait`, cross-family) | | OI-22 | arrival: the annual-disclosure run records the mailing | | law: the reports are 5300 and 5310 disclosures; the day is the profile's | once / none |
| OI-25 | Write the lessons and update the procedure (`person`) | A | OI-23 | lessons added with status; a fixed lesson names its guard; the SOP step names the lesson | `jason lessons --area owner-info` | person | once / none |

### 2.2 `notice-delivery` (subject: a notice key; roles: M syncs and resends, S records a posting, B takes late or unreached members, counsel reads the proof)

| id | step (kind) | role | needs | produces / evidence | command | clock (basis) | repeat / skip |
|---|---|---|---|---|---|---|---|
| ND-01 | Read the notice's requirement before it goes: recipients, method, clock with the documents' stricter period, content, evidence (`check`) | J | | the requirement recited; the batches named with the requirement's key and the date (lesson `notice-key-names-requirement`) | `jason notices REQUIREMENT --catalog` | law and documents, from the catalog row | once / none |
| ND-02 | Plan the recipients (`job`) | M queues | ND-01 | `data/notices/KEY/recipients.json` (ids and counts, no names) | `jason delivery --notice RULE --ids data/notices/KEY/recipients.json` | | once / none |
| ND-03 | Wait for the send (`wait`) | | ND-01 | arrival: a batch or a Mailroom send under the key; text as sent kept (`kept.json`) | | law or documents: the last day to send, from ND-01 | once / none |
| ND-04 | Read the delivery from PayHOA (`job`) | M | ND-03 | ledger attempts, each with one of ten outcomes | `jason notices KEY --sync`, or `--sync --subject "SUBJECT" --since DATE` for a notice sent from PayHOA's screens | proposed policy: the day after | once / none |
| ND-05 | General notice: also posted where the annual policy statement designates? (`branch` by fact, then `person` S) | S | ND-04 | a posting record with where and day, or none; a posting with no day meets no clock | `jason notices KEY --mark-general --posted "WHERE, 2099-10-02" --by NAME` | law: 4045(a)(3) | once / skip when the method is individual |
| ND-06 | Wait 24 hours; read again (`wait`, then `job`) | | ND-04 | a message with no delivery event is `unknown` | `jason notices KEY --sync` | proposed policy (vendor behavior, not a clock) | once / none |
| ND-07 | For each member owed a follow-up, plan it (`branch` by outcome, then `plan`, **new kinds** from OI-12, OI-16, and ML-04) | M, 2P | ND-06 | a resend batch whose key starts with the notice's key, so the next sync reads it (a test batch is never part of the notice) | `jason owner-info --mail-batch --only UNIT --resend --yes --confirmed-by NAME`, or `jason mailroom` | law requires the resend (4041(e)); the number of days is proposed policy: 3 after the outcome was read | per member and outcome / skipped when another delivery reached the member, or the notice was posted where designated (a failed message is then information, unless the member asked for individual delivery, 4045(b)) |
| ND-08 | Ask each member whose address failed for a working one; record it in PayHOA (`person`) | M | ND-07 | the answer recorded (`owner-info-tags` item or a person's entry) | none (no message kind exists; journey (e)) | proposed policy: 7 days after the outcome was read | per member / none |
| ND-09 | A week on, read the letters' tracking: never mailed, returned, forwarded (`wait`, then `job`) | M | ND-07 | Lob events in the ledger | `jason notices KEY --sync` | proposed policy: a week | once / none |
| ND-10 | Sync until nothing is owed (`check`) | J | ND-09 | owed is zero; the ledger is the record | `jason notices KEY` | | repeat / none |
| ND-11 | Put the proof of notice together (`check`) | J | ND-10 | each evidence item on file, to attach, or owed; the window; reached, unreached, and reached only after the last day | `jason notices KEY --proof --event DATE [--general --posted DATE] [--have text_as_sent,...]` | law and documents (the row's windows) | once / none |
| ND-12 | Members reached only after the last day, or not at all (`decision`) | B | ND-11 | a finding for the board; the usual cure is a new date and a new notice; counsel reads sufficiency | none | the Act is silent beyond delivery; the practice in [notices.md](../notices.md#when-an-owner-cannot-be-reached) is a policy for the board to consider, **proposed**, not adopted | once, only on a finding / none |
| ND-13 | Keep the text and read the record (`check`) | J | ND-11 | `jason://notice/KEY`: strength delivered, sent with follow-ups owed, sent, or file; never a file alone | `jason cite jason://notice/KEY` | | once / none |

### 2.3 `mailroom-letter` (subject: one letter; roles: M asks, 2P (T or an officer) signs where money is spent; started only by a person)

| id | step (kind) | role | needs | produces / evidence | command | clock (basis) | repeat / skip |
|---|---|---|---|---|---|---|---|
| ML-01 | Keep the PDF within the page limit (`check`) | J | | page count; price a letter in cents; four pages at most unless a person chooses otherwise | `jason mailroom --prices` | the vendor's pricing (`payhoa.pricing`), not law | once / none |
| ML-02 | Preview the recipients and the cost (`job`, PayHOA lane) | M | ML-01 | recipients by unit with the address resolved; price a letter; total in cents; PayHOA's own preview saved | `jason mailroom --pdf FILE --units UNITS` | | once, again if the PDF changes / none |
| ML-03 | Test every link and QR code as its reader would (`person`) | M | ML-02 | attestation per link (lessons `test-as-an-owner`, `form-link-needs-unit`, `letter-link-per-unit`) | none | person | per link / none |
| ML-04 | Mail it, only on a person's word (`plan`, **new kind** `payhoa-mailroom-send`, R3, 2P, cost shown, "this mails N letters; a letter cannot be recalled; type N") | M, 2P | ML-02, ML-03 | batch letters read back as processing; `data/mailroom/sent.jsonl` with letter and communication ids; with a notice, `letter.pdf` and recipient ids kept | `jason mailroom --pdf FILE --units UNITS --send --yes [--notice KEY --by NAME]` | the notice's last day to send, if there is a notice (law or documents, from ND-01) | once / none; jason never starts this step |
| ML-05 | If something is wrong, cancel at once (`wait`, with a `plan` branch, **new kind** `payhoa-mailroom-cancel`, R2) | M | ML-04 | letter id cancelled, or the window passed | `jason mailroom --cancel LETTER_ID --yes` | the window is minutes (lesson `letters-cannot-be-recalled`) | once / none |
| ML-06 | Read the batch back (`check`) | J | ML-04 | every letter `processing` or better | `jason mailroom --batch ID` | | once / none |
| ML-07 | A week on, read the tracking (`wait`, then `job`) | M | ML-06 | never mailed, returned, forwarded, handed to ND-09 when a notice key exists | `jason notices KEY --sync`, else `jason mailroom --letters KIND` and `--events COMMUNICATION` | proposed policy: a week | once / none |

### 2.4 `respond-sweep`, `respond-request`, `respond-policy`

`respond-sweep` (subject: a week, and again the day before each board meeting; roles: M).

| id | step (kind) | role | needs | produces / evidence | command | clock (basis) | repeat / skip |
|---|---|---|---|---|---|---|---|
| RS-01 | Refresh the requests (`job`, PayHOA lane) | M | | catalog age shown | `jason sync-catalog` (cadence `payhoa-catalog`, proposed) | | weekly / none |
| RS-02 | Read the open requests with their clocks; open one `respond-request` for each, by request id (`check`) | J | RS-01 | rows with kind, clock, source, due, standing; idempotent by request id | `jason respond` | per row | weekly / none |
| RS-03 | Join the emailed requests PayHOA lacks (`plan`, **new kind** `payhoa-request-create`, R2: the owner sees it) | M | RS-02 | the PayHOA request, linked | `jason request-links`, then `--create THREAD --yes` | | per thread / skipped when none |
| RS-04 | Put on the agenda what the board decides (`person`) | M | RS-02 | board items for architectural, solar, EV charger, rental, variance requests | `jason board` | | before each meeting / none |
| RS-05 | Monthly, read answers on time, by kind, for the board (`check`) | J | RS-01 | figures with counts under five shown as counts | `jason respond --all` | | monthly / none |
| RS-06 | Label new requests' kinds in the gold set; measure before changing a kind rule (`person`) | A | RS-02 | no kind's precision or recall falls | `jason respond --measure` | | per rule change / none |

`respond-request` (subject: one request, a PayHOA request or an emailed one; roles: M answers, B decides what is reserved to it, counsel advises).

| id | step (kind) | role | needs | produces / evidence | command | clock (basis) | repeat / skip |
|---|---|---|---|---|---|---|---|
| RQ-01 | Classify: kind, clock row, owner, due day (`check`) | J | | kind with `classifiedBy`; clock source (statute, documents, or policy); due; PayHOA's own due date shown beside it, never replacing it | `jason respond` | per the row (4.2) | once / none |
| RQ-02 | A kind read as `other`: decide its kind (`person`) | M | RQ-01 | the kind, with a reason | none | person | once / skipped unless `other` |
| RQ-03 | Read the clock's authority: the words first, then any reading, labeled (`check`) | J | RQ-01 | recitation of the row's authority | `jason cite AUTHORITY` | law or documents | once / none |
| RQ-04 | No rule sets a clock for this kind (`decision`) | B | RQ-03 | a finding for the board: propose a written policy (4350); a made-up due day is never shown | none | the law and the documents are silent, so a **proposed policy** is held | once / skipped unless RQ-03 found none |
| RQ-05 | Read where the answer is written: passages, library files, precedents (`job`) | M | RQ-01 | leads, each a lead and not a ruling | `jason respond --sources` | | once / none |
| RQ-06 | Draft the acknowledgment (`job`, then `plan` for an email, **new case** `acknowledgment` in kind `gmail-drafts`; child run `owner-document`) | M | RQ-01 | draft text; a date only where the law or the documents set one; a PayHOA request gets a comment, an emailed request a Gmail draft in its thread | `jason respond --draft ID`; `jason respond --draft email:ID --gmail --yes` | acknowledgment: proposed policy (`acknowledge_days`); no statute read here sets one | once / skipped when the first admin comment is already there |
| RQ-07 | Send it (`person`): a PayHOA comment (until `jason request-comment` has a gate), or the Gmail draft sent from Gmail | M | RQ-06 | the next sync shows the first admin comment or the outgoing message | `jason request-comment ID "TEXT"` | as RQ-06 | once / none |
| RQ-08 | Branch by kind (`branch` by fact) | J | RQ-02 | the path: records RQ-10..13; resale RQ-14; board RQ-15..19; staff RQ-20; executive-session kinds (payment plan, hearing request, internal dispute, ADR) link to their own families | | | once / none |
| RQ-10 | Records: open the request in the records store (`person`) | M | RQ-08 | `data/records-requests/requests.json` row: day received, unit, via, record kinds, purpose in the member's words, years; stages computed | `#/records-requests` form (`POST /api/write/records-requests/new`); no CLI verified | law: 5210(b) | once / none |
| RQ-11 | Records: decide the purpose (membership list only) and what is withheld or redacted, with the legal basis (`person`, counsel where needed) | M | RQ-10 | `purposeAdequate`, `withheld[]` with reasons, in the store; the written explanation if the member asks | `POST /api/write/records-requests/<id>` | law: 5215(d), 5225 | per record / skipped when nothing is withheld |
| RQ-12 | Records: tell the member the copying cost and wait for agreement before copying (`wait`) | M | RQ-10 | arrival: the member's agreement; `feeCents` | | law: 5205(f); whether the wait stops the 5210 clock is not in the words read, so the clock runs and both dates show (question for counsel) | once / skipped for inspection with no copies |
| RQ-13 | Records: make them available; record the day and how (`person`) | M | RQ-11, RQ-12 | `producedOn`, `inspectedOrCopies` | store write | law: 5210(b)(1), (b)(2), (b)(6) | once / none |
| RQ-14 | Resale documents: the 4525 documents and the 4528 form, fee estimate first (`person`) | M | RQ-08 | delivery day; the request's mailed-or-delivered day recorded as the anchor | none | law: 4530(a)(1) | once / none |
| RQ-15 | Board kinds: put it on the next agenda (`person`) | M | RQ-08 | board item with the question, the recited provisions, and the options, no recommendation | `jason board` | documents or statute (RQ-01) | once / none |
| RQ-16 | The board decides (`decision`) | B | RQ-15 | the decision: date, meeting, vote as taken, motion words, conditions (`data/board/decisions.json`) | `#/room`, `#/decisions` | per RQ-01; jason never approves, denies, or assigns | once / none |
| RQ-17 | Write the decision letter (`person`, child run `owner-document`) | M, the officer who recorded the vote | RQ-16 | letter at stage `approved`; an elements check | `jason letter` | law: 4765(a)(4) | once / none |
| RQ-18 | Post the decision in the PayHOA thread; record where (`person`) | M | RQ-17 | `sentRef` | none | as RQ-07 | once / none |
| RQ-19 | Reconsideration asked (`branch` by arrival) | B | RQ-18 | a new RQ-15 for kind `RECONSIDERATION`, at an open meeting | | law: 4765(a)(5); the time is the documents' or proposed policy | per request / skipped unless asked |
| RQ-20 | Staff kinds (maintenance, complaint, question): answer; maintenance is answered when the plan is told and closed when the work is done (`person`) | M | RQ-08 | first admin comment or outgoing message | `jason request-comment` or a Gmail reply | per RQ-01 | once / none |
| RQ-21 | Waiting on the member (`wait`, run `paused`) | M | RQ-06 | a pause is a person's record with a reason, ended when the member writes back; days added to the due date | none | only a POLICY clock pauses; a statute or documents clock does not unless its cited words allow (not built: `ResponseRule` has no `pauses`) | per wait / refused on a statute clock |
| RQ-22 | Close the request in PayHOA (`person`) | M | RQ-13, RQ-18, or RQ-20 | the next sync shows it closed (a done step that a store contradicts reads "changed since") | none | | once / none |

`respond-policy` (subject: a response standard or a change to it; the standard is [response-standards-design.md](../response-standards-design.md)).

| id | step (kind) | role | needs | produces / evidence | command | clock (basis) | repeat / skip |
|---|---|---|---|---|---|---|---|
| RP-01 | Print the proposal: each kind's clock with its source, statutes recited, policy clocks marked proposed (`job`) | M | | the proposal | `jason respond --standards` (**not built**); today `jason respond --all` and the rule rows | | once / none |
| RP-02 | Put it on the board's agenda with the options: adopt, adopt with changes, keep internal (`person`) | M | RP-01 | board item | `jason board` | | once / none |
| RP-03 | Is it a rule on a subject listed in 4355(a)? (`branch`, a reading for counsel) | B | RP-02 | yes: `jason rule-change`, notice first; no: a policy adopted at an open meeting | `jason rule-change` | law: 4360(a), 28 days before the change | once / none |
| RP-04 | Adopt, change, or decline (`decision`) | B | RP-03 | the vote and the motion's words | `#/room`, `#/decisions` | person (the board's) | once / none |
| RP-05 | Write the rows into the profile from the decision (`person`) | A | RP-04 | `adoption` and `adopted` on each row (fields **not built**) | a patch a person applies | | once / none |
| RP-06 | Publish only the adopted rows (`plan`, child run `owner-document`) | M | RP-05 | the `response-standards` template rendered (**not built**) | | | once / none |

### 2.5 `owner-document` (subject: a Markdown source; roles: M or S author, the letter's named approver, B where the board approves)

| id | step (kind) | role | needs | produces / evidence | command | clock (basis) | repeat / skip |
|---|---|---|---|---|---|---|---|
| OD-01 | Write it once in Markdown under `data/drafts`, pictures as `![alt](file){width=560}` (`person`) | N | | the source and its hash (lesson `one-source-per-document`) | none | person | once / none |
| OD-02 | Check the references: every `{QUOTE:key#n}` and `{CITE:key#n}` fills; a quote noted "check before sending" is read against the recorded copy (`check`) | J | OD-01 | references resolved with digests | `jason section-refs --check FILE` | | each edit / none |
| OD-03 | Where it states what a provision requires, read the provision as cited: the words in force, then the reading, labeled and whose (`check`, then `person`) | N | OD-02 | citation with its readings beside it | `jason cite EXPRESSION --cited-by --md` | law or documents | once / skipped when it states no requirement |
| OD-04 | Is it a notice the Act requires? (`branch` by fact) If so, check its elements and open `notice-delivery` (`check`) | J | OD-02 | each element present, supplied by a token, enclosed, missing, or not checkable by words; conditional elements with their condition | `jason notices REQUIREMENT --catalog`; `notice_elements.check` | law, per the requirement | once / skipped when it is not a required notice |
| OD-05 | Make its Doc on the letterhead (`plan`, **new kind** `google-doc`, R1) | N | OD-03 | Doc id; the Markdown's hash matches the hash the Doc was made from | `jason broadcast FILE.md --to-doc --yes` | | each edit / none |
| OD-06 | Approve the words (`person`; `decision` where the board must) | the letter's named approver; B | OD-05 | the letter stage `approved` with its log (`data/approvals/letters.json`); the board's approval recorded by S or P with the meeting's date | `#/approvals` (letters); no CLI verified | person; the board's own | once / none |
| OD-07 | For a page to post or attach, export the PDF (`job`) | N | OD-06 | the PDF | `jason letter --markdown FILE.md --pdf OUT.pdf --yes` | | once / skipped when no page is needed |
| OD-08 | Preview it as one recipient receives it (`person`) | N | OD-05 | attestation: subject names the unit; form links carry the unit | `jason owner-info --email-batch ... --preview OUT.html` for the owner-information email | person | per channel / none |
| OD-09 | Hand it to a delivery: email batch, broadcast, Mailroom, or posting (`branch`, child run `notice-delivery` or `mailroom-letter`) | N | OD-08 | the child run; the text kept under `data/notices/KEY/` with its sha256 | the delivery's own | | once / none |
| OD-10 | Read the kept text against the file (`check`) | J | OD-09 | unchanged, or "EDITED since it was kept: the words above are not the words sent" | `jason cite jason://notice/KEY` | | on open / none |

### 2.6 `form-campaign`, step group IN, and `form-library-review`

`form-campaign` (subject: a campaign code = form code, year, channel; the standard forms of [form-library-design.md](../form-library-design.md): state, family, and custom tiers).

| id | step (kind) | role | needs | produces / evidence | command | clock (basis) | repeat / skip |
|---|---|---|---|---|---|---|---|
| FC-01 | Is the form offered? Tier, status, recitals, handler, marker (`check`) | J | | ready, adjusted, not offered (the missing slot named), or failing | `jason form-library --check [--tier T]` | | on open / none |
| FC-02 | Stale against an amendment? (`check`; if so a child run `form-library-review`) | J | FC-01 | "stale: read the amendment" or none | `jason form-library --check`; `jason law-history` | law (the shelf's text) | on open / none |
| FC-03 | Choose the handler (`branch` by the form's authority; `person` for a form tied to no law) | M | FC-01 | a form with an authority takes the process handler its citations name (`owner-information`, `response-clock`); a custom form takes a general handler, none of which is built, so the run is `blocked` | `jason campaigns --open FORM ... --handler KEY` | person | once / none |
| FC-04 | Open the campaign (`person`) | M | FC-03 | campaign row | `jason campaigns --open FORM --channel C --cycle-year Y --by NAME [--option NAME=VALUE] [--return-by DATE]` | person | once / none |
| FC-05 | Offer the form in its channel: PayHOA form, request center, or PDF; the link carries the unit (`person`; the PayHOA form is OI-05's plan) | M | FC-04 | where it is offered; copies in `data/forms/references.json` | `jason forms --payhoa KEY --yes` | person | once / none |
| FC-06 | Collect and process the arrivals (group **IN**; handler `owner-information` goes to IN-07, handler `response-clock` opens a `respond-request` for the arrival) | M, B | FC-05 | per 2.6 IN | `jason responses --check` | per IN | per arrival / none |
| FC-07 | Read what is due and who is outstanding (`check`) | J | FC-05 | the funnel and follow-ups for this campaign | `jason campaigns --show CODE`; `jason followups --campaign CODE` | per 4.3 | repeat / none |
| FC-08 | Close the campaign (`person`) | M | FC-06 | status `closed` | `jason campaigns --close CODE --by NAME` | proposed policy: 7 days after return-by; a standing form with no return-by has no close (**not verified**) | once / none |

Step group **IN** (response intake). Included by `owner-info-cycle` (OI-17) and `form-campaign` (FC-06). Roles: M, with B for the decisions.

| id | step (kind) | role | needs | produces / evidence | command | clock (basis) | repeat / skip |
|---|---|---|---|---|---|---|---|
| IN-01 | Check for new responses on PayHOA, Gmail, scanned mail, and the Google Form; a manual channel is never checked (`job`) | M or the scheduler | | arrivals kept; each channel's last check with its age; a channel that failed says why | `jason responses --check` (cadences `responses-gmail`, `responses-payhoa`, **proposed**, adopted by a person) | | repeat / none |
| IN-02 | Read each returned form: a reading is evidence (`person`) | M | IN-01 | a reading with each field's confidence; the copy jason sent compared with the sender and the unit | `jason responses --read ID --by NAME` | proposed policy: 3 days after the arrival was kept | per arrival / `--dismiss ID --why` for a non-answer; a PayHOA or Google Form arrival is already structured |
| IN-03 | Confirm what it says; correct it; if it asks for something other than the form's answers, open a `respond-request` (`person`) | M | IN-02 | keyed answers, the same shape a PayHOA submission becomes; state `keyed` | `jason responses --confirm ID --by NAME [--set ...]` | proposed policy: 3 days after the reading | per arrival / none |
| IN-04 | Key a paper return handed in or taken by phone, naming the method (`person`) | M | | an arrival `manual:ID` | `jason responses --add-manual ... --how HOW` | | per paper return / skipped when none |
| IN-05 | Triage by the response policy: record, person, confirm, board, ignore (`check`) | J | IN-03 | findings with outcome and rule (`owner_responses.RULES`) | `jason owner-info --responses --canvas` | | per batch of answers / none |
| IN-06 | Decide what only the board decides: whether a co-owner's answer elects for the others, an occupancy answer the unit's tag does not show, a blank required answer (`decision`) | B | IN-05 | the decision; then a rule row, after which the planner classes such items | `jason board`; `#/decisions` | person (the board's); the law is silent, so each is held and never approved by a click | per question / none |
| IN-07 | Record the answers: a plan, decided item by item by a named person, applied only if nothing changed (`plan`, kind **`owner-info-tags`, built**) | M, one named person | IN-03, IN-06 | tags written; each fully recorded request completed with the board's comment emailed; arrivals marked `recorded` | `jason approvals plan owner-info-tags --by NAME`; `show`, `decide`, `submit`, `apply --yes` | law: 4041(b)(1), enter at least 30 days before the 5300 and 5310 disclosure; proposed policy: record 7 days after confirming | per plan, a plan older than 24 hours is planned again / none |
| IN-08 | Enter what only a person can: a mailing address, an email, a record in PayHOA (`person`) | M | IN-07 | the next plan finds nothing left for that unit | none | as IN-07 | per unit / none |
| IN-09 | Ask the owner where the policy says confirm (`person`) | M | IN-05 | the owner's reply, as a new arrival | none (no message kind exists) | person | per owner / none |

`form-library-review` (subject: a year; roles: A reads, B decides mid-cycle changes).

| id | step (kind) | role | needs | produces / evidence | command | clock (basis) | repeat / skip |
|---|---|---|---|---|---|---|---|
| FL-01 | List the Act's changes since each form's as-of (`job`) | A | | stale forms and citations | `jason conflicts --leads`; `jason form-library --check` | law | each January / none |
| FL-02 | Read each amendment; update the definition; bump the version, with what changed and when it takes effect (`person`) | A | FL-01 | new version; the campaign keeps the version it used | a code change | law | per form / none |
| FL-03 | A change in the law in the middle of a campaign (`decision`) | B | FL-02 | the board's decision; jason does not decide it | none | the library's open question | only on a finding / none |
| FL-04 | Find requests the law or the documents create that have no form (`job`, then `person`) | A | | candidates confirmed, held (the law is silent on a clock the form needs: proposed policy), or dropped | `jason discover-forms --seed`, `--read`, `--confirm ID --by NAME` | | yearly / none |

## 3. Branches and failure paths

| Event | What the run does |
|---|---|
| A `check` fails (dates leave no room, a form is not offered, a reference does not fill, a PDF is over its pages) | The step reads `blocked` with the failing evidence; the run stays `active`; a person fixes the cause and re-opens the check, or records why it does not apply. |
| A `job` fails | The step reads `failed` with the message; a read or sync is retried by the queue, a write never is. A sign-in failure pauses the source (`KeeperAuthRequired`, `GoogleAuthRequired`) and says so; nothing opens a browser. |
| A plan item is rejected or held | Applied items are `done`; a rejected item is recorded with its reason and the step stays open for it; a held item names its board item and is never approvable. A completion that depends on a rejected or held write stays open ("will stay open: a write it needs was rejected"). |
| A plan is old or the live state moved | The apply re-plans, refuses when any approved item's basis differs, supersedes the plan, and opens a new one; the earlier decisions show as hints. The step reads `superseded`, then the new plan's state. |
| An email batch stops part-way (rate limit, session, three failures in a row) | The batch is `paused`; an `uncertain` item is never resent blind (`jason batches --resolve ID KEY --sent` or `--not-sent`); the step stays `running` until every item is sent, failed, or resolved. |
| A mailed letter is wrong | ML-05 is open for the minutes the Mailroom allows to cancel; after that the correction is a new notice (ND-12), never a recall. |
| An arrival never comes | OI-21 and OI-22 are `wait` steps with dates; past the date the step opens a follow-up (remind, then the entry-day finding), and the run says "past the answer-by date: N outstanding". It does not mark an owner answered or unreachable. |
| An owner answered by two methods | The later answer supersedes the earlier under the cycle's rules (never over newer information); the earlier arrival stays, marked `superseded`. Outstanding counts the owner once. |
| Every delivery to an owner failed | The owner is `unreachable`, listed apart from outstanding with the follow-up the law asks (resend by first-class mail, 4041(e)); never counted outstanding and never hidden. |
| A statute clock passes with the request open | The run states it in the law's words (4.1), opens an `answer-due` follow-up, and lists the request by name for the board; executive-session kinds are counted without names. |
| A store changed under a done step (a tag removed in PayHOA, a form edited, a Doc edited after approval, a request closed elsewhere) | The step reads "changed since" with the difference, as a `changed` event; nothing is repeated and nothing is trusted blindly. A letter whose Doc changed after approval returns to `saved`. |
| A form's handler is not built, or no campaign is open | The generator refuses and says which is missing; FC-03 is `blocked`; no reference is made. |
| A request is answered outside jason (a phone call, an email jason did not see) | RS-02 shows it overdue; a person answers in the thread or records the answer; a done step is never set by a guess. |
| The entry day arrives with answers confirmed and not recorded, plans open, or arrivals unread | OI-22 fails with the three counts; the run is `blocked` on it and lists the gap as a finding for the board in the law's words (4.1). It does not write the answers itself. |
| The board has not decided the cycle's questions (OI-03) before the send | The run does not wait: the occupancy follow-ups stay held, `occupancy-vs-tag` findings stay board items, and the held writes are never approvable. When the board decides, the decision becomes a rule row and the held items re-plan. |
| The requester and the approver are the same person | The second-person step refuses: a plan's confirm by the first approver (case and spaces ignored) is refused by the server, and the step stays `needs a person` for someone else. |
| A form link is found broken after a send | OI-15 fails; the letters (OI-16) stay `blocked` and are not started; the correction is an email, and the lesson is added at OI-25 (`form-link-needs-unit`). |
| A returned form names a different owner or unit than the copy sent | IN-02 shows both and notes the difference; IN-03 is a person's, and the arrival is never attributed by a guess. |
| A request completes only partly (a write rejected, held, or for a person) | The owner's PayHOA request stays open with what is left (`requests_left`); jason completes it only once everything in it is recorded (the board's rule of 2026-10-01) and never edits or deletes an owner's submission. |
| A records request names records withheld in part | RQ-11 records `withheld[]` with the legal basis; if the member asks, the written explanation of 5215(d) is a child `owner-document`. jason never decides what is withheld. |
| The membership list is asked and no purpose is given | The step shows "no purpose stated" with 5225 beside it; a person records the member's words or that none was given; jason does not score the purpose. |
| A kind was read wrongly | RQ-02 is reopened by a person; the old kind stays in the history, the clock is recomputed from the new row, and the gold set gets a label (RS-06). |
| A statute's deemed-approval clock runs while the board has not met | RQ-15 and RQ-16 show the statute's days left in its own words; the run opens an `answer-due` follow-up; jason neither approves nor extends. |
| A step's definition changes while a run is open | The run keeps the definition version it started with; a new version applies to the next run, and the difference is shown (a change in a definition is the lowest authority and is corrected there, with the lesson). |

## 4. Clocks and their basis

### 4.1 The law, recited (from `data/authorities`; jason's consolidated text, not an official restatement; a reading follows the words and is labeled)

| Clock | Operative words | Citation | Used by |
|---|---|---|---|
| Ask each owner each year | "The association shall solicit the annual notices described in subdivision (a) of each owner and, at least 30 days before making its own required disclosure under Sections 5300 and 5310, shall enter the data into its books and records." | Civ. Code 4041(b)(1) | OI-22, IN-07 |
| What the request carries | "Notification that the member does not have to provide an email address to the association." and "A simple method for the member to inform the association in writing that the member wishes to change their preferred delivery method for receiving notices from the association." | 4041(b)(2)(A), (B) | OI-08, FC-05 |
| Individual delivery | "the association shall deliver that document in accordance with the preferred delivery method specified by the member pursuant to Section 4041." | 4040(a)(1) | ND-01, ND-07 |
| No valid method | "the association shall deliver the document by first-class mail, registered or certified mail, express mail, or overnight delivery by an express service carrier addressed to the recipient at the address last shown on the books of the association." | 4040(a)(2) | ND-07 |
| No answer | "the last mailing address provided in writing by the member or, if none, the property address shall be deemed to be the address to which notices are to be delivered." | 4041(c) | ND-07 |
| A bounced email | "If the association delivers a notice to a member’s email address and finds that the email address provided is no longer valid, the association shall resend the notice to a mailing or email address identified by the member pursuant to Section 4040." | 4041(e) | ND-07 |
| When delivery is complete | "If a document is delivered by mail, delivery is deemed to be complete on deposit into the United States mail." and "If a document is delivered by electronic means, delivery is complete at the time of transmission." | 4050(b), (c) | ND-07, ND-09 |
| General notice, individual on request | "if a member requests to receive general notices by individual delivery, all general notices to that member, given under this section, shall be delivered pursuant to Section 4040." | 4045(b) | ND-05, ND-07 |
| Records, current year | "Association records prepared during the current fiscal year, within 10 business days following the association’s receipt of the request." | 5210(b)(1) | RQ-13 |
| Records, two prior years | "Association records prepared during the previous two fiscal years, within 30 calendar days following the association’s receipt of the request." | 5210(b)(2) | RQ-13 |
| Membership list | "Membership list, within the timeframe specified in Section 8330 of the Corporations Code." | 5210(b)(6) | RQ-13 |
| Costs agreed first | "The association shall inform the member of the amount of the copying and mailing costs, and the member shall agree to pay those costs, before copying and sending the requested documents." | 5205(f) | RQ-12 |
| A denial explained | "If requested by the requesting member, an association that denies or redacts records shall provide a written explanation specifying the legal basis for withholding or redacting the requested records." | 5215(d) | RQ-11 |
| Resale documents | "Upon written request, the association shall, within 10 days of the mailing or delivery of the request, provide the owner of a separate interest, or any other recipient authorized by the owner, with a copy of all of the requested documents specified in Section 4525." | 4530(a)(1) | RQ-14 |
| A change needing approval | "The procedure shall state the maximum time for response to an application or a request for reconsideration by the board." and "A decision on a proposed change shall be in writing." | 4765(a)(1), (a)(4) | RQ-16, RQ-17 |
| An operating rule's validity | "An operating rule is valid and enforceable only if all of the following requirements are satisfied:" and "The rule is in writing." | 4350, 4350(a) | RQ-04, RP-04 |
| A rule change | "The board shall provide general notice pursuant to Section 4045 of a proposed rule change at least 28 days before making the rule change." | 4360(a) | RP-03 |

Words that answer: the 4041(b)(1) sentence sets OI-22 (reports-mailed day less 30 days); the 4041(e) sentence sets that a resend is owed and gives no number of days. A finding in the code, not a reading: the five-business-day figure in `records_requests.MEMBERSHIP_LIST_BUSINESS_DAYS`, cited there as 5210(b), is not among the words of 5210. Section 5210(b)(6) points to Corporations Code 8330, whose (a)(1) asks "five business days’ prior written demand" for inspection and whose (a)(2) says a list "shall be made available on or before the later of ten business days after the demand is received" or the date it is compiled as of. Which applies, and the label, is for counsel (see [Decisions](#11-decisions-that-are-not-this-pages)). The other kinds' statute rows (`RESPONSE_RULES`: solar, EV charger, EV meter, payment plan, request for resolution, disaster rebuild) are recited with `jason cite` and are not copied here. Business days run Monday to Friday with no holiday subtracted, so a computed day is the earliest it can fall; how a court counts a period is for counsel.

### 4.2 The documents, and the clock rows that are the profile's

The documents' clocks reach this family through `Community.response_rules()` rows (`ClockSource.DOCUMENTS`) and `notice_catalog.effective` (the documents' stricter period governs a notice's clock). 4765(a)(1) requires the documents to state the maximum response time for a change needing approval; where they do not, RQ-04 holds the question. A governing document that asks more than a statute is followed as written; one that asks less yields to the extent of the conflict (Civ. Code 4205), recorded as a `Conflict` row and never settled by the run.

### 4.3 Proposed policy (the board adopts; jason never makes a rule; every one is shown labeled "proposed")

| Number | Where | Adoption |
|---|---|---|
| Remind 7 days before the return-by date | `followups.PROPOSED_DAYS`, OI-19 | the profile has no hook to adopt a number (open decision in [followups-design.md](../followups-design.md)) |
| Resend 3 days, and ask for an address 7 days, after the outcome was read | same, ND-07, ND-08 | same |
| Read 3 days, confirm 3 days, record 7 days after an arrival was kept, read, or confirmed | same, IN-02, IN-03, IN-07 | same |
| Close 7 days after the return-by date | same, OI-23, FC-08 | same |
| The day-after sync, the 24-hour second sync, and a week on for letters | procedure `notice-delivery`, ND-04, ND-06, ND-09 | practice in the SOP |
| Acknowledge within 2 business days (records) or 3 (architectural kinds) | `ResponseRule.acknowledge_days` | no field for adoption yet |
| 45 calendar days for a reconsideration or a protected-use application | `RECONSIDERATION`, `PROTECTED_USE` rows | the row says "a proposed policy until the board adopts one" |
| What more to do for an owner who cannot be reached (five points) | [notices.md](../notices.md#when-an-owner-cannot-be-reached) | "a policy for the board to consider" |

### 4.4 A person's own

The return-by date, the reports-mailed date, a campaign's `remind-days`, a follow-up a person adds, and a pause are a person's; each is labeled person and shows who set it.

## 5. The screens

### 5.1 Which common screens the family uses

All routes are the spine's `#/work` group ([workflows-design.md §4](../workflows-design.md#4-the-web-interface-common-to-every-family)); nothing under `#/work` exists yet.

| Screen | Route | Specific to this family |
|---|---|---|
| Work list | `#/work?definition=owner-info-cycle` (and the other keys) | "Yours" holds IN-02, IN-03, RQ steps; "Waiting on a clock" holds OI-14, OI-21, ND-06, ND-09; "Board" holds OI-03, IN-06, RQ-04, RQ-16, ND-12, RP-04. |
| Run | `#/work/owner-info-cycle/2099`, `#/work/notice-delivery/KEY`, `#/work/mailroom-letter/ID`, `#/work/respond-request/ID`, `#/work/owner-document/NAME`, `#/work/form-campaign/CODE` | The step rail, panel, clock strip, links, and history, with the panels in 5.2. |
| StartRun | each definition's subject | `owner-info-cycle` asks for the three dates and shows the entry day computed; `respond-request` starts from `#/work` or from a row of `jason respond` and is idempotent by request id; `mailroom-letter` is started only by a person and says so. |
| Today and the dock | the dock's Deadlines | Follow-up items are not in the dock today (verified: `web/extra/dock.py` has none); the dock gains each open run's next clock. |

### 5.2 Family panels, loaders, and components

| Panel (on) | Reads (loader key, built unless marked) | Shows | Components |
|---|---|---|---|
| Funnel (owner-info-cycle, form-campaign) | `campaign-status` (`?code=`) | asked by channel, answered by channel (`payhoa`, `gmail`, `mail`, `forms`, `manual`), read, confirmed, recorded, outstanding, unreachable, each with its source age; a count not known is `null` with `reason`, shown as a dash | to add: `CampaignFunnel`, `ChannelMark`, `AgeStamp` (proposed in [handoff-followups.md](../console/handoff-followups.md)); built: `Stat`, `Pill` |
| Follow-ups band (owner-info-cycle, form-campaign) | `followups` (`?days=&campaign=&kind=&state=`) | the dated items in bands overdue, today, this week, later, each with basis chip, outstanding count, command | to add: `FollowUpRow`, `FollowUpBand`, `BasisChip`; built: `Command`, `DueDate`, `Findings` |
| Arrivals lane (IN) | `responses` (`?state=&channel=&unit=&request=&days=`), `response` (`?id=`, reading and acts only in the private view, logged), `outstanding-responses` | arrivals with state words new, seen, read, keyed, recorded, dismissed, superseded; the channel check strip; the owners outstanding | to add: `ArrivalRow`, `CheckedStrip`, `ScanReview` ([handoff-responses.md](../console/handoff-responses.md)); built: `DataTable`, `Doc` |
| Plan review (IN-07, OI-12, OI-16, ML-04) | `approvals` (`/api/approvals/<id>`) | the plan item by item, held and for-a-person sections, the cost, the second signature, apply behind `--allow-apply`, the result | built: `PlanReview`, `WriteRow`, `HeldNote`, `ApproveBar`, `SecondConfirm`, `ChangedBanner`, `CostLine`, `ApplyResult` |
| Writes the answers call for (IN-07) | `owner-info` (`/api/owner-info`, disk only) | the older confirm-each-write list and the apply command | built: `OwnerInfoView` with `ConfirmList` (see gap 9) |
| Notice record (notice-delivery) | `notices`, `notice` (**to add**; `notice_ledger.notices`, `notice_record.build`, `notice_delivery`) | six bands: requirement recited, text as sent, recipients, delivery (counts), proof, stage | to add: the Notices screen per [screens/notices.md](../console/screens/notices.md); built: `Recitation`, `ReadingLabel`, `Clock`, `Evidence` |
| Mailroom preview (mailroom-letter) | `mailroom` (**to add**, over `tasks.mailroom.status` and the saved preview; none exists) | the PDF, the recipients and address resolution, price a letter and total in cents, the batch read back, the tracking | built: `DocumentPreview`, `CostLine`, `Confirm` (type the count); to add: `Mailing` panel |
| Request clock (respond-request) | `member-requests` (**to add**; `jason.api.member_requests`, `acknowledgment_draft`), `records-requests` (built) | kind, clock and who set it, standing, leads, the acknowledgment draft "for a person to read and send" | built: `Clock`, `Recitation`, `ReadingLabel`, `DataTable`, `RequestForm`; the Requests screen per [screens/requests.md](../console/screens/requests.md) |
| Letter stages (owner-document) | `approvals` (letters inbox, built), `templates`, `request-letter`, `drafts` | draft, saved, requested, approved, sent; the Doc and the PDF | built: `DraftLetter`, `ApprovalsInbox`, `TemplatesView`, `DraftsView` |
| Form library (form-campaign) | `form-library` (`?tier=`) | each form's tier, status, findings, handler, campaigns | to add: `FormRegister`, `CampaignCard` ([handoff-form-library.md](../console/handoff-form-library.md)) |

Reuse the existing screens and link to them: Owner information `#/owner-info`, Approvals `#/approvals`, Records requests `#/records-requests`, Drafts `#/drafts`, Templates `#/templates`, Jobs `#/jobs`, Decisions `#/decisions`, Plan a meeting `#/agenda`. The run page links to each and shows its state. The spine's step panel is named `RunStepPanel` because `StepPanel` already names a component in `ui/src/views/DriveChooser.tsx`.

**States, for every panel.** *Loading*: `Loading`. *Empty*: "No arrivals checked yet. `jason responses --check` reads them" (never an empty table). *Missing*: the loader's `found: false` with its reason and the command that fills it ("the delivery sync has not run since 2099-10-02, so bounced notices are not shown", drawn on the band). *Stale*: each count shows its age; a source past its `stale_after` says so on the stage it feeds. *Blocked*: the step says by which step or fact. *Changed since*: the run's banner, the difference, and the step reopened. *Director*: a director reads each panel as an officer does at the same level (section 6); the server decides the level, never the page.

**Specific acts.** Every record a person makes on these screens is a `Confirm` signed by name: attest a link was tested, record a posting, record a records-request decision, confirm a reading, defer or drop a follow-up. The follow-up acts are terminal steps today (`jason followups --done ID --by NAME`); the writer is to add. Nothing on a page sends, mails, completes a request, or posts to an owner; the page shows the text to copy and the command.

### 5.3 The run pages drawn

The owner-information run (`#/work/owner-info-cycle/2099`). The step rail is the spine's; the family adds the funnel and the follow-ups band to the step panel when the current step is OI-17 or OI-18. A director sees the same page an officer sees at the same level.

```text
+--------------------------------------------------------------------------------------------------+
| Owner information 2099                          active   as of 2099-10-09 08:00   [Pause] [Note]  |
| Clocks: remind 2099-10-16 (proposed) | answers asked by 2099-10-23 (person) | enter by 2099-11-01 (law, |
|         Civ. Code 4041(b)(1)) | reports mailed 2099-12-01                                           |
+-------------------------+------------------------------------------------------------------------+
| A Set up        done    | Group IN: collect and record                       needs a person (you)  |
| B Send          done    |  Asked 90 --> Answered 47 --> Confirmed 44 --> Recorded 38               |
| C Collect       <--     |  by how asked: email 90 | 1 mailing        by how answered: PayHOA 20 ...   |
|   IN-02 read    3 old   |  Outstanding 41      Unreachable 2 (apart)      never sent a copy 10      |
|   IN-03 confirm 0       |  Checked: PayHOA 2 h ago | Gmail 2 h ago | scanned mail 2 h ago | Form --  |
|   IN-06 board   1 held  |  [Read 3 returned forms]  jason responses --list --new   A person runs this|
|   IN-07 plan    2nd     +------------------------------------------------------------------------+
| D Follow up     ready   | Linked: approval apr-example (partially approved) | campaigns OI99E, OI99M |
|   OI-19 remind  ready   |         notice owner-info-2099 | board item 1 | follow-ups 3              |
|   OI-20 resend  2 owed | History (newest first) ...                                                 |
+-------------------------+------------------------------------------------------------------------+
```

The request run (`#/work/respond-request/ID`). The clock panel is `screens/requests.md`'s "THE CLOCK" block; the rail shows the path chosen at RQ-08 and greys the others as "not applicable".

```text
| Request email:EXAMPLE1 . records . Unit 123 Main St                             due soon (6 days)  |
| Received 2099-10-05 . due 2099-10-19  [LEGAL]  Set by: the statute . owner: records                |
| [Recitation] Civ. Code 5210(b)(1) "Association records prepared during the current fiscal year ..." |
| [ReadingLabel: jason's reading] ten business days from receipt; no holiday subtracted (earliest day)|
| Rail: RQ-01 done . RQ-06 done . RQ-07 done . RQ-10 done . RQ-11 done . RQ-12 waiting (member) . RQ-13 |
| Acknowledgment: sent 2099-10-06 by J. Manager   Cost agreed: no   [Record the member's agreement]   |
```

The notice run (`#/work/notice-delivery/KEY`) is the six bands of [screens/notices.md](../console/screens/notices.md) in the step panel, with the rail beside them: requirement, text as sent, recipients, delivery, proof, stage. The Mailroom run shows the PDF (`DocumentPreview`), the recipients with their addresses resolved, and `CostLine` ("10 letters, 4 pages each, 2040 cents estimated, charged to the association"), then the `Confirm` that asks the count typed.

### 5.4 States, panel by panel

| Panel | Empty | Missing | Stale | Blocked / changed |
|---|---|---|---|---|
| Funnel | "Not opened": no campaign for the form | `null` counts as a dash with `reason` ("no emailed copy on record", "no notice ledger on disk") | each stage shows the age of its source; a check older than the channel's `stale_after` says so on the stage | a closed campaign still reads live from disk; a changed form version shows "form changed since the campaign opened" |
| Follow-ups | "Nothing due in the next 14 days as of ..." | "The delivery sync has not run since ..., so bounced notices are not shown", drawn on the band | `sourceAge` on every item | a deferred item shows its new date and reason; an item no longer derived stays in the log, not the list |
| Arrivals | "No arrivals checked yet. `jason responses --check` reads them" | a channel never checked reads "never checked"; a failed one says why (sign-in, failure) | `checkedHoursAgo` per channel | a reading of a copy that differs from the sender or unit is noted, never corrected |
| Plan review | "No approval of this kind is open. Plan one: `jason approvals plan owner-info-tags`" | the plan's live read failed: the sign-in message | a plan past `max_age_hours` is planned again before apply | "changed since review" on each item; superseded plan links to its successor |
| Notice record | "No notices in the delivery ledger" | "Text not kept" and "not synced" with their commands | the last synced standing with its time | "EDITED since it was kept" |
| Request clock | "No open requests; N answered in the last 12 months" | "no PayHOA requests on disk. Run `jason sync-catalog`" | catalog age beside the title | "open, no clock": no rule sets one; a made-up due day is never drawn |

## 6. Privacy and roles

| Data | Level | Who |
|---|---|---|
| The definitions, the clocks, the statutes recited | P0 | anyone on the roster |
| Funnel counts, follow-up items without names, ages | P0 to P1 | roster |
| Outstanding, unreachable, follow-up names, notice member rows (unit and id) | P1 and P2, names and units | M, S, P, directors, T; the Treasurer sees money kinds |
| An arrival's sender, unit, attachment names | P2 | M, S, P, directors, T |
| A reading, keyed answers, an arrival's acts | P3, the private view, opened for a stated reason and logged in `access/served.jsonl` | M, P, S, directors in the private view; not T |
| An email address, phone, mailing address | P2, masked, one field revealed, logged | M, S, P |
| A records request: the unit, kinds, and purpose in the member's words | the store (`records-requests/`) has no path rule, so a file read defaults to P2 (closed); the loader serves the row by unit, never the name; the level of the purpose is **not verified** | M, S |
| Executive-session kinds (payment plan, hearing, internal dispute, ADR) | P3 | private view |
| A notice's text as sent | P1 (the text sent to all; a member's fills are not in it) | roster |
| Plan items | P1 (names, tags); masked where a value looks like an address | M, one named person, 2P where the kind needs it |

Directors and officers have the same access to information (the board's decision of 2026-10-11): a director reads what an officer reads at the same level. By `access.SEE_RULES` the roster opens P0 and P1; the manager, president, vice president, director, and secretary open P2 and, in the private view, P3; the treasurer opens P2.

Per step, who acts and at what level it reads (a step shows at the level of what it touches):

| Steps | Acts | Reads at | Note |
|---|---|---|---|
| OI-01..OI-11, OD-01..OD-10, FC-01..FC-05 | M, A, the author | P0 to P1 | templates and documents; no owner's data except OI-09's counts |
| OI-12, OI-16, ML-04, OI-19 | M plans; T or an officer signs second | P1; recipients by unit and id | cost shown in cents; the approval store masks addresses |
| ND-02..ND-10 | M, S for ND-05 | P1 counts; member rows (unit, id) only in the private view | the ledger path `notices/*` is P1 |
| IN-02, IN-03, IN-04 | M, S, P | P3 for a reading and keyed answers (private view, logged) | the arrival list is P2 |
| IN-06, OI-03, ND-12, RQ-04, RQ-16, RP-04 | B, recorded by S or P with the meeting's date | P0 to P1 on the question; executive-session matters P3 | no click stands in for the board |
| IN-07, IN-08 | M and one named person; a high-stakes item needs a second | P1 tags; P2 masked | |
| RQ-01..RQ-09 | M | P1 kind and unit; the title may name a person, so it is P1 for M and directors and held from T except on money kinds | |
| RQ-10..RQ-13 (records) | M, S, counsel by grant | the member's purpose and the records' contents are the member's own words and the association's records; confidential records stay out (5215) | the 5215 list is the manager's decision |
| FL-01..FL-04 | A, B | P0 | |

The levels of three stores this family writes have no `PathRule`: `followups/*`, `forms/campaigns.json`, `records-requests/*`. A path no row places is P2, closed; the build assigns their level (gap 16).

A URL carries an id or a filter, never a name, an email, or an address. A run's list never carries an owner's contact details or an answer.

## 7. What exists now (checked against the repo, 2026-10-11)

| Piece | Verified |
|---|---|
| SOPs | `owner-info-cycle` (20 steps), `notice-delivery`, `mailroom-letter`, `respond`, `owner-document` in `src/jason/community/procedures.py`; `jason sop KEY` |
| Commands | `jason owner-info` (`--send-plan`, `--email-batch`, `--mail-batch`, `--resend`, `--follow-up`, `--responses`, `--canvas`, `--apply`, `--payhoa`, `--preview`), `jason responses` (`--check`, `--list`, `--read`, `--confirm`, `--seen`, `--dismiss`, `--outstanding`, `--add-manual`), `jason followups` (`--done`, `--defer`, `--drop`, `--add`), `jason campaigns` (`--show`, `--open`, `--close`, `--adopt`), `jason notices` (`--sync`, `--mark-general`, `--proof`, `--catalog`), `jason mailroom` (`--pdf`, `--units`, `--send`, `--cancel`, `--prices`, `--batch`, `--letters`, `--events`, `--months`, `--notice`), `jason respond` (`--sources`, `--draft`, `--gmail`, `--measure`, `--all`), `jason form-library` (`--check`, `--tier`), `jason discover-forms`, `jason batches`, `jason delivery`, `jason forms`, `jason packet`, `jason broadcast`, `jason letter`, `jason request-links`, `jason request-comment` |
| Not in the commands | `jason respond --standards`, `--metrics`, `--overdue`, `--log` (the response-standards design); a CLI for letter stages (the web writer `approvals` does it) |
| Approvals kinds (`src/jason/approvals/registry.py`) | three: `owner-info-tags` (R2, one person), `payhoa-attach-bills`, `gmail-drafts` (cases `proposal-request`, `hearing`, `meeting-notice` only). No kind for the email batch, the mail batch, a Mailroom send or cancel, a form update, a request comment or creation, or a Google Doc |
| Letters store | `data/approvals/letters.json`, stages draft, saved, requested, approved, sent; the board approves by a vote an officer records with the meeting's date |
| Stores | `data/forms/campaigns.json`, `data/forms/references.json`, `data/responses/inbox.json` and `acts.jsonl`, `data/followups/acts.jsonl`, `data/notices/deliveries.db`, `data/notices/KEY/kept.json`, `data/batches.db`, `data/mailroom/sent.jsonl`, `data/records-requests/requests.json`, `data/approvals/` |
| Loaders (`GET /api/<key>`) | `owner-info`, `responses`, `response`, `outstanding-responses`, `campaign-status`, `followups`, `form-library`, `records-requests`, `approvals`, `request-links`, `templates`, `request-letter`, `dock`, `jobs`. |
| Loaders not found | `notices`, `notice`, `mailroom`, `member-requests`, `cycle`, `work`, `work-run` |
| Views (`ui/src/views`) | `OwnerInfoView`, `RecordsRequestsView`, `ApprovalsView` with `PlanApprovals`, `DraftsView`, `TemplatesView`, `InboxView`, `MailTriageView`, `JobsView`. No view reads `followups`, `campaign-status`, `responses`, or `form-library` (no `ui/src` file mentions them) |
| Scheduler cadences | `responses-gmail`, `responses-payhoa` (proposed), `payhoa-catalog`, `gmail` in `jason.integrations.registry`. No cadence syncs a notice's delivery |
| Handlers | `owner-information` and `response-clock` built; five general handlers (`collect-only`, `sheet-register`, `board-item`, `payhoa-tags`, `forward-draft`) `built=False` |
| Form definitions | a module a form in `form_library/ca/` and `us/` (the count was not taken); delivery-change and secondary-address use handler `owner-information`, the rest `response-clock` |

## 8. Gaps and the build order

Gaps found (each a fact about the repo, not a wish):

1. **Approvals kinds missing for every send.** The email batch, the mail batch, a Mailroom send and cancel, a PayHOA form update, a request comment, a request creation, a Doc, and the acknowledgment draft run as commands with `--yes` and a name; only the tags have a plan. The design is in [approval-workflow.md](../console/approval-workflow.md) (`payhoa.mailroom.send`, R3, two people).
2. **`jason request-comment` has no dry run and no `--yes`** (lesson `google-writes-without-yes`): RQ-07 stays a person's step.
3. **No screen reads the follow-ups, the funnel, the arrivals, or the form library**, though their loaders are built.
4. **The notice delivery has no loader or screen** (`notices`, `notice`), and nothing schedules the sync; ND-04, ND-06, ND-09 depend on a person remembering.
5. **No Mailroom loader.** A send's preview, price, and tracking exist only in the terminal and `data/mailroom`.
6. **`respond` has no screen** (`member-requests` is specified, not built), and the records-request store (`data/records-requests`) is a second record of the same request as the PayHOA request `jason respond` reads: nothing joins them, so a records request can be overdue in one and produced in the other.
7. **The response standard is design only**: no `adoption`, `pauses`, `member_words`, metrics, or `--standards`. `acknowledge_days` is the only field.
8. **Follow-up numbers cannot be adopted**: `PROPOSED_DAYS` has no profile hook.
9. **Two ways to confirm tag writes.** `OwnerInfoView` (a confirm toggle in `data/owner-info`) and the `owner-info-tags` approval both exist; only the approval re-plans live and refuses a stale write. The run points at the approval.
10. **Per-owner cycle board (`/api/cycle`), "mine/yours" on follow-ups, the 30-day strip, and the dock's follow-ups are not built.**
11. **The membership-list clock** (5 business days, cited as 5210(b)) does not match the words of 5210(b)(6) and Corp. Code 8330 (4.1).
12. **The SOP's order puts the campaign step after the test send; `campaigns.require` refuses a copy with no open campaign.** The definition puts OI-04 first. Whether `--only me` is exempt is **not verified**.
13. **A message kind to ask a member for an address** does not exist (journey (e)); ND-08 and IN-09 are a person's steps.
14. **Only three `gmail-drafts` cases**; the acknowledgment (`jason respond --draft email:ID --gmail`) has its own path outside the approvals.
15. **No workflow engine** (`jason.workflows`, `jason workflow`): every state above is read from the stores each time, not kept.
16. **Three stores have no data level**: `followups/*`, `forms/campaigns.json`, and `records-requests/*` have no `PathRule`, so a file read defaults to P2 (closed) while their loaders serve them; the level should be set with the screens.
17. **No joined view of one owner across the family.** An owner's answer, delivery outcome, request, and letter sit in five stores; the per-owner cycle board (`/api/cycle`) that would join asked, delivered, responded, reached is design only, so "what is left for Unit 123 Main St" is read by running four commands.
18. **A cadence for the delivery sync is not registered**; the response checks are registered but proposed, so until a person adopts them the funnel's ages grow silently (they are shown, not hidden).
19. **The mail batch and the one-off Mailroom send are two paths to the same Mailroom** with different ledgers (`data/batches.db` for a batch; `data/mailroom/sent.jsonl` for a send by `jason mailroom`; whether a batch also writes the second is **not verified**); the definitions treat both as `mailroom-letter`, and the build must make the run read both.

Build order for this family: (1) the run store and fold (spine step 1), with these definitions as made-up tests; (2) the owner-information cycle end to end, since its plan kind, campaign, follow-ups, and inbox are built: read-only `Work` and `Run` over the existing loaders, then the panels in 5.2 for the funnel, follow-ups, and arrivals; (3) the approvals kinds for the email batch, the mail batch, and the Mailroom send, and the `mailroom` loader; (4) `notices` and `notice` with the sync cadence proposed; (5) `member-requests`, joining the records store to the PayHOA request, then the response standard's adoption fields; (6) `form-campaign` and the form library screen; (7) `owner-document` over the letters store.

## 9. A made-up sample run

`owner-info-cycle`, Example Village HOA, cycle 2099. Dates: opened 2099-09-15, return-by 2099-10-23, reports mailed 2099-12-01, entry day 2099-11-01 (a Sunday: send and enter a day early; how the days are counted is counsel's). Today is 2099-10-09. The email batch went out 2099-09-16 (90 copies; 10 owners were not sent a copy and get the mailed letter); the letters were mailed 2099-09-18. Sample units "123 Main St" (A. Owner) and "456 Oak Ln" (B. Owner).

| Step | State | Note |
|---|---|---|
| OI-01 dates | done | by A. Admin, 2099-08-20 |
| OI-02 room for a correction | done | return-by is 38 days after opened; sync +1, resend +3 |
| OI-03 board decisions | done | decided 2099-09-01 (rental question); co-owner envelopes: not decided, held |
| OI-04 campaigns | done | `OI99E`, `OI99M`; handler `owner-information` |
| OI-05 to OI-08 | done | form locked; link tested 2099-09-14 signed out and in |
| OI-09 to OI-11 | done | send plan 2099-09-12; test to self |
| OI-12 email batch | done | 90 sent, 0 uncertain; confirmed by J. Manager and K. Treasurer |
| OI-13 delivery read | running | child `notice-delivery/owner-info-2099`: ND-04 and ND-06 done (2099-09-17, 2099-09-18), ND-07 2 owed, ND-08 waiting on the manager |
| OI-14, OI-15 | done | |
| OI-16 mail batch | done | 10 letters, mailed 2099-09-18; child `mailroom-letter/owner-info-2099-mail` done at ML-07 (read 2099-09-25: 9 mailed, 1 returned, handed to ND-09) |
| OI-17 group IN | needs a person (M) | 47 answered: payhoa 20, gmail 18, mail 7, manual 2; read 46, confirmed 44, recorded 38; 3 arrivals unread past 3 days |
| IN-06 | needs the board | one occupancy answer the unit's tag does not show, held; board item for 2099-10-20 |
| IN-07 | waiting on the second person | plan `apr-example`: 8 of 10 writes approved, 1 held for the board, 1 for a person; the completions wait on the writes |
| OI-18 outstanding | done, repeating | outstanding 41, unreachable 2, never sent a copy 10, source ages: catalog 6 h, inbox 2 h, ledger 30 h |
| OI-19 reminder | ready | due 2099-10-16, proposed: 7 days before; 41 to remind |
| OI-20 resend | needs a person | 2 owed a resend by first-class mail (4041(e)) |
| OI-21 return-by | waiting | 2099-10-23 |
| OI-22 entry day | not started | 2099-11-01; "past" would read in the law's words |
| OI-23 to OI-25 | not started | |

Clock strip: remind 2099-10-16 (proposed); answers asked by 2099-10-23 (person); enter in the books by 2099-11-01 (law, 4041(b)(1)); reports mailed 2099-12-01. Links: approval `apr-example`, campaigns `OI99E` and `OI99M`, notice `owner-info-2099`, follow-ups 3, board item 1. Run state `active`.

Second run, `respond-request`, a records request received Monday 2099-10-05 from Unit 123 Main St, current-year records by email. RQ-01 done: kind records, clock STATUTE, due 2099-10-19 (10 business days, the earliest it can fall), owner records assignment. RQ-06 done: Gmail draft saved and sent by a person on 2099-10-06. RQ-10 done: stages `currentYear` 2099-10-19. RQ-11 done: nothing withheld. RQ-12 waiting on the member: cost 1250 cents, agreement not received; the clock runs. RQ-13 not started; standing "due soon". The member's name is not on the list; the unit is.

The history of that run, newest first (the event log the spine describes; `by` is a signed-in name or `jason`):

| At | By | Event | Detail |
|---|---|---|---|
| 2099-10-09 08:00 | jason | `check-ran` | RQ-01 again: due 2099-10-19, 6 days left, standing "due soon" |
| 2099-10-08 10:12 | J. Manager | `note` | cost estimate sent by email, 1250 cents; agreement asked |
| 2099-10-07 14:30 | J. Manager | `attested` | RQ-11: nothing withheld or redacted; no legal basis to state |
| 2099-10-06 09:05 | J. Manager | `attested` | RQ-07: Gmail draft read, edited, and sent from Gmail |
| 2099-10-05 16:20 | jason | `plan-made` | RQ-06: Gmail draft in the thread, scope `acknowledgment`, 0 cost |
| 2099-10-05 16:00 | jason | `check-ran` | RQ-01: kind records, clock statute, due 2099-10-19 |
| 2099-10-05 15:58 | J. Manager | `opened` | from `jason respond`, request `email:EXAMPLE1` |

A third run, `notice-delivery` for key `board-meeting-2099-10-20` (a general notice): ND-01 done; ND-03 done (the meeting notice sent 2099-10-06); ND-04 done; ND-05 done by S. Secretary, "clubhouse board, 2099-10-06" (a posting with a day); ND-06 skipped (posted where designated, so a failed message is information); ND-07 skipped for 1 owner whose email bounced (another delivery reached the member) and open for 1 owner who asked for individual delivery (4045(b)); ND-11 not started. Strength shown: "delivered, with the individual deliveries owed under 4045(b) listed".

## 10. Acceptance criteria

1. Each definition's steps carry a kind from the seven, a role, and a basis; every `person` step in the five SOPs appears as a `person` or `decision` step, every command as a `job` or `plan`, every check as a `check`.
2. A run of `owner-info-cycle` for a made-up cycle computes the entry day as reports mailed less 30 days and shows it with "law, Civ. Code 4041(b)(1)".
3. OI-12, OI-16, and ML-04 cannot be marked done without a plan applied or a named person's attestation; a run never starts ML-04 itself.
4. Opening a run twice makes one child run per key (idempotence by request id, notice key, campaign code, plan scope).
5. A plan whose basis changed since review reads `superseded`, and the step shows "changed since" with the difference.
6. The outstanding count excludes an owner who answered by any channel and an owner who is unreachable; the unreachable are listed apart.
7. Every proposed number renders the word "proposed" and its source; none renders as a deadline stamp, and a proposed acknowledgment date is never given to an owner.
8. A statute clock is recited from `data/authorities` with its citation before any reading, and a reading is labeled with whose it is; every quotation passes `jason verify-quotes`.
9. A pause on a `STATUTE` or `DOCUMENTS` clock is refused unless the row cites words that allow it.
10. A director reads what an officer reads at the same level on every panel in 5.2, and the owner view reads none of it.
11. No page offers approve, deny, or assign for a request, or a button that sends, mails, or posts to an owner; each shows the command or the text to copy.
12. A done step whose store changed (a tag removed, a Doc edited after approval, a request closed elsewhere) reads "changed since".
13. A mailed letter step shows the number of letters and the cost in cents, requires the count typed, and records the letter and communication ids.
14. A run is readable from disk without the server, and every state is a fold of its events.

## 11. Decisions that are not this page's

- **Child runs and step groups.** Whether a step may `need` a child run, and a definition may include a group (IN), as proposed in 0. Recommended: yes, so a Mailroom send is one run wherever it starts.
- **The membership-list clock.** Counsel reads 5210(b)(6) with Corporations Code 8330(a); the code's five business days and its "5210(b)" label then stay or change.
- **Whether a records request opened in `#/records-requests` and the same PayHOA request are one run** (gap 6). Recommended: one `respond-request`, with the store as its record.
- **The board's numbers** where the law is silent (4.3), and whether a second reminder goes after the return-by date and to whom.
- **Who is the second person** on the email batch, the mail batch, and the Mailroom send (the treasurer is recommended on money, an officer otherwise); and whether an email-only batch with no cost needs two people.
- **Whether the Mailroom send should list a notice key by default**, so the text as sent is always kept.
- **Whether a standing form with no return-by ever closes** (**not verified** in `campaigns`).
- **Not verified:** a CLI for letter stages; the `acknowledgment` draft as a `gmail-drafts` case; whether `--only me` needs an open campaign; whether `jason sop` can load a definition into the spine's `Procedure` rows without change.
