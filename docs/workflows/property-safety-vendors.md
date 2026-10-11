# Workflows: the property, its safety, and its vendors

Status: **design**, October 11, 2026. A family page of [workflows-design.md](../workflows-design.md); it follows that page's template (its section 5) and its model (definition, run, the seven step kinds, the event log). Nothing here is built as one engine: `jason.workflows` does not exist (no module of that name was found in `src/jason`). What exists are the pieces each section names under "What exists now", each checked against the repo on this date; anything not checked says **not verified**. The page is general: it names no association, county, vendor, or person. Samples use "Example Village HOA", "Example Alarm Co.", "A. Owner", "123 Main St", and dates in 2099.

**Words used.** *Basis* is one of `law` (recited from `data/authorities`, whole, with its citation), `documents` (a written instrument in hand: the governing documents, a contract, a policy, or a third party's notice; the cell says which), `proposed` (a number that is neither the law's nor the documents': the board's to adopt, never stamped), and `person` (a date someone set). A step's *who* is `jason`, an office (`manager`, `president`, `secretary`, `treasurer`, `director`), `board` (a vote at a meeting, recorded by an officer), `reviewer` (the committee role proposed in [console/security-and-privacy.md](../console/security-and-privacy.md)), or `any` signed-in person. jason proposes, reads, drafts, and waits; it never sends, signs, pays, accepts a proposal, tells an insurer, or approves a request.

## 0. How these relate

One inspection finding fans out. The nine definitions below are linked by **child runs** (a new link kind, `run`, beside the spine's approval, job, follow-up, board item, document, and campaign).

```text
obligation period (W1 life-safety-period) ── report filed and read ──┬─ passed, nothing open ──► record kept (law: 5 years) ──► wait for the next period
                                                                      └─ open deficiency ──► W2 deficiency (one run per row)
W2 deficiency ─┬─ impairs a scheduled safeguard ──► insurer told (documents: the policy's words)
               ├─ needs a proposal ──► gmail draft (proposal request) ──► board decision ──► W5 contract-notice-window (the new agreement)
               ├─ repair above authority ──► board item ──► decision
               └─ cleared only by a linked record (invoice lines, AES 10, a later passing report)
W3 backflow-annual and W4 elevated-elements are W1's cousins: another cycle, another report, the same file/read/place/record steps.
W5 contract-notice-window: terms read ─► both edges of each notice window ─► board decision (renew, re-bid, end) ─► letter (a plan) ─► delivery proof.
W6 improvement-request: receipt ─► complete? ─► review ─► board vote ─► letter ─► work ─► verification ─► the unit's manual (and, at a loss, W8's packet).
W7 paint-cycle: catalog watch ─► board substitutes ─► reserve date ─► bids ─► award (W5) ─► record last painted.
W8 loss-claim: incident ─► history standing ─► carrier notified ─► five-question packet ─► outcome ─► member notice if coverage changes (CIV 5810).
W9 maintenance-program: portal read ─► label and licence checks ─► vendor questions ─► occupant notice if treatment needs vacating (CIV 4785) ─► renewal (W5).
```

Which clocks are the law's, which the documents', and which are proposed is in section 4; every step's clock cell carries its basis.

## 1. The tasks

| Key | Task | Subject (one run each) | Trigger |
|---|---|---|---|
| `life-safety-period` | One system's inspection, test, or maintenance for one period: schedule, report on file, deficiencies opened | system, obligation, period | an obligation is overdue, has no record, has a past period with nothing on file, or comes due within the horizon |
| `deficiency` | One deficiency a report found: confirmed, impairment, insurer, proposal, repair, cleared | a register row (`def-…`) | a reading lists an open deficiency |
| `backflow-annual` | The water supplier's annual assembly test: notice, assemblies, tester, reports, failed-test repair | program, year | the program's notice arrives, or the year's test falls due |
| `elevated-elements` | The Civil Code 5551 inspection of exterior elevated elements, per building and for the association | the association's nine-year cycle, with a row per building | the next due day (law) is within the horizon, or a building has no date on record |
| `contract-notice-window` | A vendor or management contract: terms read, both edges of each notice window, renewal decision, notice letter | a contract and its current term | a contract enters the library; the window opens; an amendment arrives |
| `improvement-request` | An owner's improvement request from application to the unit's manual (ordinary, accessibility, solar, charger, rebuild tracks) | a request (`imp-…`) | a request is received (PayHOA form, email, paper) |
| `paint-cycle` | The paint schedule against the maker's catalog, the repaint of a building group, the color request side path | a schedule, then a building group's repaint | the catalog check differs; the reserve date nears; the board asks for a repaint |
| `loss-claim` | An incident or insurance claim: history, carrier, five-question packet, outcome | an incident (a unit or the common area) | an incident is entered; a claim paper arrives |
| `maintenance-program` | A maintenance program the profile declares (pest control is the worked case) | program, period | the portal syncs; a visit or report arrives; a vendor term nears |

## 2. The definitions

Each table is one definition. Columns: `id`, step, `kind`, `who`, `needs` (step ids that must be done or skipped), what it `produces` and the evidence, the `command` (terminal; "to add" when none exists), the clock and its basis, and repeat and skip rule. A skip needs a reason, recorded by name; no legal step is skippable by anyone (spine, section 7).

**Who does what, at a glance.** The offices are the roster's; a step names the role and the server enforces it.

| Definition | Runs it | Records it | Decides it | Reads only |
|---|---|---|---|---|
| `life-safety-period` | manager | secretary (the occurrence) | board (a proposal) | director, treasurer (amounts) |
| `deficiency` | manager | manager (an office that opens P2) | board (a repair above the manager's authority) | director |
| `backflow-annual` | manager | secretary | board (the tester's engagement, if the documents require) | director |
| `elevated-elements` | manager | manager and the reserve study's preparer | board (the engagement; executive session may be used for a contract's formation) | director |
| `contract-notice-window` | manager | secretary | board (renew, re-bid, end) | treasurer, director |
| `improvement-request` | manager | manager, reviewer, the recording officer | board (the vote) | director |
| `paint-cycle` | manager | manager | board (a substitute color, an award) | any signed-in person |
| `loss-claim` | manager | manager | board (the deductible guideline) | counsel on grant |
| `maintenance-program` | manager | manager | board (adoption, renewal) | director |

**What each run links to** (`links[]`; each shown in its current state, read from its own store): `life-safety-period`: approval (`gmail-drafts`), job (`models --filed`, `vendors --reports`), follow-up, board item, library document, child runs. `deficiency`: the register row, board item, library documents (the clearing record, the insurer correspondence reference). `backflow-annual`: library documents (notices, reports), the tester snapshot. `elevated-elements`: the report, the reserve study, the building's private record. `contract-notice-window`: the reading (`data/contracts/terms/KEY.json`), the contract, the letter and its log, board item, the proof of delivery. `improvement-request`: the PayHOA request or thread address, board item, decision, letter, unit-manual entry. `paint-cycle`: the schedule Doc, the catalog copy, the reserve component, the contract. `loss-claim`: incident events, claim papers, the packet, the policy. `maintenance-program`: the vendor portal record, product registrations, notices.

### 2.1 `life-safety-period`

When: an obligation's period needs a record. Areas: documents, governing (a `life-safety` area does not exist in `jason.community.lessons.Area`; one is to add). Roles: manager runs it; secretary records; board decides a proposal. Refs: [fire-protection.md](../fire-protection.md), [life-safety-inspections.md](../life-safety-inspections.md), [console/screens/life-safety.md](../console/screens/life-safety.md), [console/handoff-inspections-and-portals.md](../console/handoff-inspections-and-portals.md). Lessons: `report-does-not-say-which-inspection`, `portal-reports-not-readings`, `inspection-record-needs-a-date`, `report-qr-points-at-the-whole-set`.

| id | step | kind | who | needs | produces; evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|
| `read` | Read the record for the period | check | jason | none | each obligation's standing (current, done late, upcoming, due soon, overdue, needs input, none on record); periods covered, partly, not on file, not yet due; reports unplaced or not read; `life-safety` loader `systems[].obligations[]` | `jason inspections`; `jason deadlines` | the obligation row's cadence (law, per row: 19 CCR 904(a)(1) for the sprinkler) | per system and period; no skip |
| `applies` | Settle which obligations reach the system | branch | jason by fact; manager answers | `read` | applies, does not apply (the deciding fact), or undetermined (the question); `questions[]` | `jason applies`; `jason applies --file-questions`; `jason intake --answer ID TEXT --by NAME` | none | per obligation; an undetermined one blocks its own path and never reads as "not required" |
| `ask` | Ask the servicer for the reports it holds and a proposal | plan | manager | `read` standing is overdue, no record, a past period not on file, or due soon | approvals kind `gmail-drafts`, case `proposal-request` (key: the system); each item with its citation; the servicer's waiting mail and the agreement on file as reminders | `jason draft --proposal-request SYSTEM --to ADDRESS --yes`; as a plan, `jason approvals plan gmail-drafts --scope …` | items due within 120 days ride along (proposed: `HORIZON_DAYS`, the program's) | per request; skip when a report answers the item (reason) |
| `send` | Read the draft in Gmail and send it | person | manager | `ask` applied | attested: day sent, the draft's reference | Gmail (jason has no send method) | none | once per request |
| `wait-reply` | Wait for the servicer's report or proposal | wait | nobody | `send` | arrival: a thread from the servicer with a report or a proposal | `jason gmail --sync` (job); `jason followups --add` sets a date | person's own date; no number in law | passing the date opens a follow-up; skip if a report arrives by another route |
| `proposal` | Accept, decline, re-bid, or defer the proposal | decision | board | `wait-reply` has a proposal | a board item (category safety) and the recorded decision; accepted starts `contract-notice-window` for the agreement | `jason board`; `#/actions`, `#/room`, `#/decisions` | none; any spending authority the documents state: not verified | per proposal; no skip |
| `entry` | Tell occupants when the inspection needs entry | person | manager | `proposal` accepted, or an agreement on file | a draft notice from a base template (to add) | to add (the screen spec points at `jason notices`: **not verified** as a template command) | the governing documents' entry clause (documents; not read here) | per building; skip when no unit is entered (reason) |
| `visit` | Wait for the booked inspection | wait | nobody | `entry` | the booked day, attested | none | person (the booked day) | none |
| `file` | File the report and what the portal holds | plan | manager | `visit` passed and a report arrived | filing plan (counts by action: file, move, copy, in drive, filed before, held); holdings | `jason gmail --file-vendor VENDOR --life-safety --yes`; `jason vendors --reports --drive --yes` | none | per report; no approvals kind covers Drive filing yet (to add) |
| `read-report` | Read the filed report into the record | job | jason | `file` | a reading: inspection date, interval, result, deficiencies, buildings | `jason models --filed` (GPU lane, after the local-ai preflight) | none | per report |
| `place` | Place what the reading could not, and record the occurrence | person | manager reads; secretary records | `read-report` | unplaced and not-read items cleared or explained; the occurrence recorded with its evidence (a State form's P, F, N/A marks are read by a person) | `jason inspections`; `jason schedule-evidence --record KEY DUE --by NAME` | none | per report |
| `authority` | Confirm the report reached the fire authority having jurisdiction | person | manager | `read-report` | attested, or the record that the servicer says it did | none | law: 19 CCR 904.2(j), the servicer's duty "at the completion" (no number) | skip when the authority takes none (reason) |
| `deficiencies` | Open a child run for each deficiency | branch | jason | `read-report` | one `deficiency` run per row; none when the report passed with nothing open | `jason life-safety --propose` | none | per row |
| `keep` | Keep the record on file | check | jason | `place` | the report in the library; its retention end | `jason inspections` (the record-keeping rule, recited) | law: 19 CCR 904.2(c), five years after the next required test or maintenance | closes the run |

### 2.2 `deficiency`

The register (`data/life-safety/deficiencies.json`) is already an append-only act log with a fold (`state_of`); the run **links to it and does not copy it** (spine rule 7). Its acts are the events: `proposed`, `confirmed`, `impairs` or `does not impair`, `insurer told`, `cleared`.

| id | step | kind | who | needs | produces; evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|
| `propose` | Propose a row from a reading | job | jason | a reading lists an open deficiency | a proposed row (id is a hash of report, location, device, comment, so a second run adds none) | `jason life-safety --propose` | none | once per row |
| `confirm` | Confirm the row against the report | person | manager | `propose` | act `confirmed`, by, at | `jason life-safety --confirm ID --by NAME` | none | no "not a deficiency" act exists (gap) |
| `impairs` | Say whether it impairs a scheduled safeguard | person | manager | `confirm` | act `impairs` or `does not impair`; a person's reading, never inferred | `jason life-safety --impairs ID --value yes` or `no --by NAME` | none | a later act corrects it |
| `route` | Follow the recorded answer | branch | jason by the recorded value | `impairs` | impairs: `tell-insurer` becomes required; otherwise it is not applicable | none | none | none |
| `tell-insurer` | Tell the insurer or agent; keep what was sent | person | manager | `route` is impairs | act `insurer told`: day and the record of what was sent (the loader raises the banner while there is none); a draft of the notice (a `gmail-drafts` case, to add) | `jason life-safety --insurer-told ID --record REF --on DATE --by NAME` | documents: the policy's protective-safeguards words (the insurance review is "not composed" in the loader: **not read**); any number of days is the policy's | once; a later act corrects |
| `estimate` | Wait for the written repair estimate | wait | nobody | `confirm` | the estimate arrives | `jason gmail --sync` | law: 19 CCR 904.2(k), "before performing any repairs" (the licensee's duty; no number) | skip when no repair is needed (reason) |
| `repair-decision` | Approve the repair | decision | board, or the manager within an authority the documents state | `estimate` | board item and decision record | `jason board` | none; the authority's limit: not verified (jason has no spending-authority row) | no skip |
| `repair` | Wait for the repair | wait | nobody | `repair-decision` | invoice (line items) and report arrive | none | law: 19 CCR 904.2(d), "immediate correction" (no number): a question for the board, and a target is proposed, not stamped | passing a target opens a follow-up |
| `clear` | Link the record that cleared it | person | manager | `repair`; the record is in the library | act `cleared`: record, kind (invoice line items, AES 10, later passing report), day; an invoice's subject line and free text are refused | `jason life-safety --cleared ID --record REF --kind KIND --on DATE --by NAME` | none | none |
| `lift` | Tell the insurer the impairment ended, if the policy says to | person | manager | `clear`, `tell-insurer` | attested; the policy's words decide (not read) | none | documents (the policy) | skippable with reason |
| `board-item` | Bring the deficiency to the board's attention | check | jason | `confirm` | **Decided (2026-10-11): every confirmed deficiency becomes a board item**, proposed for the next agenda, prioritized by its severity and any deadline a person records. The item's priority is a person's severity (urgent, high, normal) or, until one is set, jason's labeled proposal (urgent when it impairs a safeguard and no record shows the insurer was told; high when it impairs; otherwise normal; a deadline past or within 14 days raises the proposal one step). The deadline is a date a person records with who set it (insurer, authority, documents, vendor, person); jason computes no legal deadline. The item refreshes with each later act, keeps the board's own fields, and is closed by the board, never by a clear | `jason life-safety --severity ID --value urgent --by NAME`; `--deadline ID --date D --basis B --by NAME` | none (a deadline carries its own basis) | none |

### 2.3 `backflow-annual`

The program is declared by the profile (`Community.backflow_program()`); the supplier's cycle, tester, tag, report, and deadline are the supplier's. Refs: [cross-connection-control.md](../cross-connection-control.md), [console/handoff-inspections-and-portals.md](../console/handoff-inspections-and-portals.md). Lesson: `backflow-letter-goes-whole-to-the-tester`.

| id | step | kind | who | needs | produces; evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|
| `notice-in` | Record each notice with every date its days could run from | person | manager | none | the notice in the library; `ProgramNotice` clocks (dated, postmarked, scanned, failed test) | `jason backflow` | documents: the notice's own words (its days); jason picks no date | per notice |
| `assemblies` | Set the letter's assemblies beside the water account and last year's reports | check | jason | none | `assemblies[]`, `discrepancies[]`: each source in its own column, none picked | `jason backflow` | none | yearly |
| `ask-program` | Ask which date counts, or about a discrepancy | person | manager | `assemblies` or `notice-in` | a message sent by a person; the answer recorded | none | none | skip when the notice settles it |
| `tester` | Check the tester against the published lists | check | jason | none | `TesterCheck`: listed on the list dated D, under another business, not listed, or not fetched | `jason backflow --fetch-testers` (job; dated snapshot) | a list older than a year is flagged (proposed) | yearly |
| `hire` | Hire the tester and hand over the letter whole | person | manager | `tester` | attested; the letter's assembly list given | none | none | skip: none |
| `test` | Wait for the test and the filed report | wait | nobody | `hire` | each assembly's report: tag number, final result, portal receipt | none | documents: the notice's days for a passing report and for a failed one, each shown from every date it could run | on pass of the date, a follow-up |
| `receipt` | Check each report | person | manager | `test` | attested per assembly: tag, result, receipt | none | none | per assembly |
| `failed` | Any assembly failed? | branch | jason by reading | `receipt` | yes: `repair-retest`; no: skipped | none | none | none |
| `repair-retest` | Repair or replace, retest, and file again | wait | nobody | `failed` | the retest report | none | documents: the notice's days to repair, counted from each candidate date (`NoticeClock`); the handbook's duty is the public water system's (as quoted in the doc; **not on the shelf**) | until arrival |
| `file` | File the reports | plan | manager | `receipt` | filing plan as in `life-safety-period` | as there | none | per report |
| `record` | Record the occurrence and the tag numbers | person | secretary | `file` | occurrence with evidence | `jason schedule-evidence --record KEY DUE --by NAME` | law: HSC 116800 (no number); handbook "at least annually" (as quoted; **not verified** on the shelf) | yearly |
| `next` | Wait for next year | wait | nobody | `record` | next due from the obligation row | `jason deadlines` | the obligation row | opens next year's run |

### 2.4 `elevated-elements`

Refs: `src/jason/community/elevated_inspections.py` (per-building records), [life-safety-inspections.md](../life-safety-inspections.md). The inspector's name, licence, and report name are private facts (`data/spec`), P3 by source.

| id | step | kind | who | needs | produces; evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|
| `reach` | Settle which buildings the section reaches | branch | jason by fact; manager answers | none | per building: reaches (applies, does not, undetermined), the (k) and (l) answers, questions | `jason applies` | law: (l), "buildings containing three or more attached multifamily dwelling units" | per building; undetermined is a question |
| `facts` | Enter each building's facts from the record that states them | person | manager | `reach` | attached units, responsibility, elements count, permit date, certificate date, inspection date **with its report** (no date is entered without one) | the profile's private facts (a person applies them); `jason intake` | none | a fact not stated stays None |
| `due` | Count the next due day | check | jason | `facts` | `due.day`, `due.under`, standing; an unknown day is a question, never a guess | `jason deadlines`; `jason applies` | law: (b)(1) and (i) every nine years; (k) six years from the certificate for a building whose permit application was on or after the (k) date | per building |
| `engage` | Engage a licensed engineer or architect | decision | board | `due` is soon, overdue, or unknown | a board decision and a contract, which starts `contract-notice-window`; executive session is permitted for "matters relating to the formation of contracts with third parties" (CIV 4935(a)) | `jason board` | law: (b)(1), "a licensed structural or civil engineer or architect" | no skip |
| `list` | Receive the random list of locations (before the first inspection) | wait | nobody | `engage` | the list, kept for future use | none | law: (c) | first cycle only |
| `inspect` | Wait for the inspection and the written report | wait | nobody | `engage` | the report with its first-page items | none | person (the booked day); law: (i) | none |
| `read` | Enter the date of inspection from page one | person | manager | `inspect` | `inspected_on` with the report named | the profile's private facts | law: (e)(5)(A) | per building |
| `threat` | Does any element pose an immediate threat? | branch | a person reads the first-page count | `read` | yes: `preventive` becomes required | none | law: (e)(5)(F) | none |
| `preventive` | Prevent occupant access until repairs are inspected and approved | person | president or manager | `threat` yes | attested, with the day | none | law: (g)(1), "immediately" (no number) | not skippable |
| `reserve` | Incorporate the report into the reserve study | person | board; the study's preparer | `read` | the study shows it | `jason reserves` is read only; no write | law: (f), "incorporated into the study required by Section 5550" | each cycle |
| `keep` | Keep the reports for two cycles | check | jason | `read` | in the library | `jason inspections` | law: (i) | none |
| `next` | Wait for the next cycle | wait | nobody | `keep` | `due.day` nine years on | `jason deadlines` | law: (b)(1) | opens the next run |

### 2.5 `contract-notice-window`

A vendor agreement or a management agreement. Refs: [contracts.md](../contracts.md), [console/handoff-contracts.md](../console/handoff-contracts.md), `src/jason/tasks/contract_terms.py`. Lessons: `notice-window-has-two-edges`, `contract-fill-in-date-misread`, `model-invents-contract-clauses`, `name-rule-files-others-agreements`.

| id | step | kind | who | needs | produces; evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|
| `read` | Read the terms | job | jason (a model is a person's choice) | the contract is in the library | `data/contracts/terms/KEY.json`: term, renewal, each notice's window, delivery, deliverables, findings (private) | `jason contract-terms FILE`; `--library`; `--model ollama` or `bedrock` (Bedrock sends the words to AWS; a confidential file is refused unless allowed for the run) | none | again on an amendment |
| `confirm-term` | Check the term's start and end on the page | person | manager | `read` | the term's end, its source (recorded, implied, or needs input) | none | none | not skippable when the start is blank |
| `window` | Count each window back from the term's end, both edges, with the delivery | check | jason | `confirm-term` | `NoticeWindowView`: opens, closes, delivery, today; "may not count" outside either edge | to add (`jason contract-terms --window KEY`); the `contract-term` as-of check counts one edge only | documents: the contract's words (a window has two edges) | per notice clause: non-renewal, termination without cause, breach and cure |
| `owed` | Read what the counterparty owes and whether it is on file | check | jason | `read` | `OwedList`: on file, not on file, not yet due | `jason contract-terms --list` | documents | a deliverable worth tracking becomes a board item or register row, a person's choice |
| `licence` | Check the licence numbers against the board's page | person | manager | `read` | attested; the paper's number is not "valid" | `jason licenses` | person | each contract and renewal |
| `statement` | A management agreement: is the manager's written statement on file | check | jason | `read` | the statement present or missing (CIV 5375) | `jason contract-terms` finding | law: CIV 5375, "in no event more than 90 days, before entering into a management agreement" | new agreements only |
| `review` | Renew, renegotiate, re-bid, or end | decision | board | `window` has opened; lead time to reach an agenda is the board's | board item and decision; no decision before the window closes is recorded as "no action", not as renewal | `jason board` | documents: before the window closes; law: board meeting notice "at least four days" (CIV 4920(a)) | no skip |
| `choice` | Which path | branch | jason by the decision | `review` | end: `draft`; renew or re-bid: `renew` | none | none | none |
| `draft` | Draft the notice in the words, address, and delivery the clause names | plan | manager | `choice` end | a letter through the existing stages (draft, saved, requested, approved, sent); a base template `contract-notice` (to add) | `jason letter` (fills a template Doc); `#/approvals` | documents | per clause |
| `approve` | Approve the letter's words | person | the officer the letter names | `draft` | the letter's log | `#/approvals` | none | none |
| `send` | Send by the delivery the clause names; keep proof | person | manager or president | `approve` | attested: day, method, proof reference | none | documents: inside both edges | not skippable |
| `ack` | Wait for the counterparty's acknowledgment | wait | nobody | `send` | arrival in the mail | `jason gmail --sync` | person | a follow-up when it does not come |
| `renew` | Record the renewal or the new agreement | person | secretary | `choice` renew | the new contract linked; a new run | none | none | none |
| `transition` | For a change of manager: records, access, vendors | person | president | `choice` end of a management agreement | the `onboard` procedure's last two steps | `jason sop onboard` | law: CIV 5205 (records) as that procedure names it | once |

### 2.6 `improvement-request`

Refs: [improvement-requests.md](../improvement-requests.md), [console/handoff-improvement-requests.md](../console/handoff-improvement-requests.md), [console/journeys.md](../console/journeys.md) (j), forms in [form-templates/](../form-templates/architectural-application.md). The states are the doc's `RequestState`; no improvement store, loader, or `jason improvements` command exists (**not found**), so those cells say "to add".

| id | step | kind | who | needs | produces; evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|
| `receive` | Enter the request and its received day | job or person | manager | none | the request record; channel and address; received day (all clocks count from it) | `jason sync-catalog`; `jason respond`; `jason request-links --create THREAD --yes` | none | once |
| `track` | Set the track: ordinary, accessibility, solar, charger, rebuild | branch | jason by kind rule; manager when the words do not say | `receive` | the track; a miss stays a miss (the general clock and a question) | `jason respond` | none | none |
| `need` | Do the documents require approval for this change? | check | jason | `track` | applies, does not apply, or undetermined with the missing fact (rows `ChangeRule`, to add) | `jason applies` | law: CIV 4765(a), "applies if the governing documents require association approval" | an undetermined answer is a board or counsel question |
| `ack` | Acknowledge the request | person | manager | `receive` | the owner told; a PayHOA comment is posted by a person (the command writes without `--yes`) | `jason request-comment ID "…"` | proposed (acknowledgment) | once |
| `complete` | Record complete, or list what is missing | person | manager | `need` | a determination (to add); jason's list is a lead | to add (`jason improvements --determine`) | solar and charger: the deemed approval is excepted when "that delay is the result of a reasonable request for additional information"; rebuild: 30 calendar days (4766(b)(1)); ordinary: the documents' time, else proposed | a rebuild's missed day deems it complete (law) |
| `missing` | Send the list of missing items | plan | manager | `complete` false | a letter draft (base template, to add) through the letter stages; posted by a person | `#/approvals` | as `complete` | until complete |
| `wait-owner` | Wait for the owner's items | wait | nobody | `missing` | arrival in the PayHOA thread | `jason sync-request-files --requests N` | a person records a pause; only a policy clock pauses | none |
| `review` | Read against the standards and earlier decisions | person | reviewer | `complete` | a review with name and role; the reviewer's recommendation stays the reviewer's | to add; `jason respond --sources` | the review clock of the track | per request |
| `agenda` | Place it on a noticed agenda | person | manager | `review` | a board item (no recommendation); the meeting that meets the clock, computed and labeled | `jason board`; to add `jason improvements --board-item` | law: CIV 4920(a) four days | none |
| `vote` | Approve, approve with conditions, or deny | decision | board | `agenda` | the decision record: motion, roll call by name, recusal by the secretary | `#/room`, `#/decisions` | law: solar 45 days (CIV 714(e)(2)(B)); charger 60 days (CIV 4745(e)); ordinary: the documents' maximum time (4765(a)(1)), else proposed | no skip; jason never sets approved or denied |
| `letter` | Draft, approve, and deliver the decision letter | plan | manager drafts; the recording officer approves | `vote` | the letter with its required elements checked; the delivery recorded | `#/approvals` | law: 4765(a)(4) | not skippable |
| `reconsider` | A denial: reconsideration requested? | branch | the owner asks; manager enters | `letter` denied | a second decision linked to the first | `#/room` | law: 4765(a)(5); the time is the documents', else proposed | once |
| `conditions` | Record the conditions with due days | person | the recording officer | `vote` approved | `Condition` rows, each with the proof it needs | to add | the decision's own words; charger in a common area: "Within 14 days of approval, provide a certificate of insurance" (CIV 4745(f)(1)(C)) | per condition |
| `work` | Wait for the owner's start and finish | wait | nobody | `conditions` | the owner's report, entered "as reported by the owner" | to add | proposed (an approval's lifetime) | none |
| `verify` | Check the work against the approval | person | manager or reviewer | `work` | verification with its evidence; a difference shown side by side, never as a violation | to add | none | jason never inspects |
| `manual` | Link the entry in the unit's manual | person | manager, for the owner | `verify` | the entry's `approval` = the request address | `POST /api/write/unit-record/entry` (built); no CLI | none | skip when the owner declines (reason) |
| `findings` | Compute the five findings | check | jason | `manual` | approval without entry, and the others, in their fixed words | to add | none | each findings pass |

### 2.7 `paint-cycle`

Refs: [paint.md](../paint.md), [paint-design.md](../paint-design.md), [console/screens/paint.md](../console/screens/paint.md). The maker's catalog is one reader; another maker is "not checked", never guessed.

| id | step | kind | who | needs | produces; evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|
| `refresh` | Refresh the catalog copy | job | manager asks | none | the copy and its age | `jason paint --refresh` (network, a person's ask) | the copy is kept a week (code) | on demand |
| `watch` | Check each scheduled color | check | jason | none | ok, renamed, discontinued, not found, not checked, per color; `needsAPerson` | `jason paint --check` (exit 1 on a difference); `GET /api/paint` | proposed: quarterly and with the January law review ([paint-design.md](../paint-design.md)) | per schedule |
| `substitute` | Choose what substitutes for a renamed or discontinued color | decision | board | `watch` has a finding | the closest current colors listed as options, none recommended; the decision recorded; a policy proposed where none is adopted | `jason paint --match "CODE" --exterior` | none: the law and documents are silent, so a written policy is proposed (a rule on a CIV 4355(a) subject needs 28 days' notice, CIV 4360(a)) | once per finding |
| `dates` | Read next due and cost from the reserve study | check | jason | none | `reserve.next[]`; last painted is "needs input" unless a recorded event is attached | `jason paint --json` | documents (the study) | each cycle |
| `scope` | Prepare the per-building sheet for the vendor | job | manager | `substitute` settled | the sheet: surface, code, name, sheen (to add) | to add | none | per building |
| `bids` | Collect proposals and read their terms | wait | nobody | `scope` | proposals in the library, read by `contract-terms` | `jason contract-terms --library` | person | none |
| `award` | Award the work | decision | board | `bids` | the decision; the contract starts `contract-notice-window` | `jason board` | none | no skip |
| `notice` | Tell owners what to expect | person | manager | `award` | a draft notice a person sends (base template, to add); `jason notices` then reads its delivery | to add | documents (not read here) | per building |
| `record` | Record last painted by building, with the invoice | person | manager | the work is done | an incident-history improvement event on a building; a person confirms it before it is cited | `jason incidents --work improvement` | none | per building |
| `doc` | Refresh the palette Doc and page | plan | manager | `record` | the Doc (replaces edits made in it) and the page | `jason paint --to-doc --yes`; `--page` | none | no approvals kind covers a Doc write (to add) |
| `request` | Side path: an owner's color request | branch | jason | none | opens `improvement-request`; the check says on the schedule for this surface, for another, near, or not on it | to add (`--request CODE --surface S --building B`) | as `improvement-request` | per request |

### 2.8 `loss-claim`

Refs: [incidents.md](../incidents.md), [insurance-and-deadlines.md](../insurance-and-deadlines.md), [insurance-policies.md](../insurance-policies.md), [unit-records-design.md](../unit-records-design.md), [document-models/insurance-claims.md](../document-models/insurance-claims.md). jason decides neither coverage nor fault.

| id | step | kind | who | needs | produces; evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|
| `record` | Record the incident: what, where, found when | person | manager | none | an incident record (to add: today incidents are only read from paperwork) | to add | none | once |
| `history` | Read what the paperwork shows: cause, element, standing | check | jason | `record` | the event: claimed, claim candidate, under deductible, sudden with cost unknown, or none; a claim on another's policy is kept apart | `jason incidents --address "123 Main" --all`; `jason incidents --link` | the deductible is the policy's | a standing is a lead |
| `mitigate` | Stop the loss and secure the area | person | manager | `record` | attested; the vendor's papers | none | person | not skippable when water or fire is active |
| `policy` | Read which policy applies, its deductible, and its notice conditions | check | jason | `record` | policy terms recited from the pages | `jason insurance`; `insurance_policies` tool | documents: the policy; its notice-of-loss words are **not read** unless the pages are on disk | per claim |
| `notify` | Notify the carrier or agent | person | manager | `policy` | the claim number and the record of what was sent | none | documents: the policy's words (no statute for this step was found in this family) | not skippable |
| `packet` | Assemble the five-question loss packet | check | jason | `record`, a unit | each step with its provisions recited, what the record shows, and held notes ("no deductible guideline adopted") | `GET /api/loss-packet?unit=&incident=` | none | per incident |
| `confirm-step` | Confirm each of the five steps | person | manager | `packet` | a confirmation per step, with name and day | `POST /api/write/loss-packet/confirm` (built) | none | jason confirms nothing |
| `guideline` | The board's deductible guideline: adopted, or a gap | decision | board | `packet` step 5 held | a decision, or a policy proposed; a rule on a CIV 4355(a) subject needs notice (4360(a)) | `jason rule-change` | none | no skip |
| `ask-owner` | Ask the owner what the item was | plan | manager | `packet` | a draft a person sends | to add | none | per item |
| `outcome` | Wait for the carrier's outcome | wait | nobody | `notify` | a claim paper: settlement, denial, closed, or primacy | `jason insurance` | documents | follow-up when silent |
| `members?` | Did coverage lapse, reduce, or the deductible rise? | branch | jason by the renewal record | `outcome` | yes: a member notice run; the base template `insurance-change-notice` exists | `jason rule-change` is not it; `jason notices` | law: CIV 5810 | per change |
| `close` | Record the outcome and what to learn | person | manager | `outcome` | the incident's links stored; a lesson if warranted | `jason incidents --link`; `jason lessons` | none | once |

### 2.9 `maintenance-program`

The pest program is the worked case ([pest-management.md](../pest-management.md)). Another program the profile declares (a moisture or inspection program, for example) takes the same steps, with its elements as the `read` step's expected evidence ([programs.md](../programs.md), [console/handoff-programs.md](../console/handoff-programs.md); neither is built).

| id | step | kind | who | needs | produces; evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|
| `standing` | Is the program adopted? | check | jason | none | document, adoption, implementation, each in its own word; "no act on record" is not "not adopted" | to add (`jason programs`) | none | per program |
| `adopt` | Adopt it, if the documents make it optional | decision | board | `standing` is drafted or missing | the decision; a vendor proposal's approval is implementation evidence, not an adoption | `jason board` | documents (the declaration) | skip when already adopted |
| `sync` | Read the vendor's portal | job | manager starts | `adopt` | visits, products, and inspection reports on disk | `jason vendors --sync` | the scheduler reads only on a cadence a person adopted (`jason cadence`) | each period |
| `read` | Read visits, products, activity, and label limits | check | jason | `sync` | `pest_program` brief; a finding is a question (an interval between treatments, a landscape use) | `jason pests`; `jason pests --fetch` (public registers, network) | documents: the label limits as stored | each period |
| `ask` | Ask the vendor what the record cannot show | plan | manager | `read` | a draft a person sends (a `gmail-drafts` case, to add) | to add | none | when a finding stands |
| `licence` | Check the vendor's licence and insurance on the board's page | person | manager | `sync` | attested | `jason licenses` | person: before each contract and renewal | each renewal |
| `vacate` | Does treatment need occupants out? | branch | a person, from the vendor's plan | `read` | yes: `vacate-notice` | none | none | per treatment |
| `vacate-notice` | Give notice to occupants and owners | plan | manager | `vacate` | a notice draft, delivered by a person; the notice states the reason, the times, and that occupants bear their own accommodations (base template, to add); `jason notices` then reads its delivery | to add | law: CIV 4785(b), "not less than 15 days nor more than 30 days prior to the date of the temporary relocation" (two edges) | per treatment; not skippable |
| `complaint` | Route a complaint: common area or owner | person | manager | none | attested; the declaration decides who handles it | none | documents | per complaint |
| `renewal` | Renewal or re-bid | branch | jason | `read` | opens `contract-notice-window` | none | documents | each term |
| `review` | Review the year | person | board | `read` | a board item; lessons recorded | `jason lessons` | proposed (annual) | yearly |

## 3. Branches and failure paths

| Situation | The run | It never |
|---|---|---|
| A store is missing or unreadable (library, portal, catalog) | the step reads "not read" with the command; independent steps go on | reads "not on file" as "not done" |
| A report has no readable words, or only State-form marks | `place` becomes a person's step with the field named | assigns a period by file name |
| The servicer never replies | `wait-reply` passes its date, opens a follow-up, and offers `ask` to another recipient | picks a recipient or sends |
| A `gmail-drafts` plan is held or its source changes | the plan is superseded; the applier saves nothing when its hash differs | saves a stale draft |
| The proposal is declined or deferred | the deficiency stays open, the board item stays; `repair-decision` waits | closes the deficiency |
| A later report shows a deficiency passed | the `clear` step reads "changed since": a clearing record is available | clears it without a person linking the record |
| A legal clock passes (solar 45 days, charger 60) | the run says so in the statute's words, marks the step "past the law's day", and opens an urgent follow-up and a board item | marks the request approved or denied, or applies the deeming |
| A notice window's edge passes | "the window closed on DATE"; options go to the board and counsel | says a late notice counts |
| An immediate threat is reported | `preventive` is required and cannot be skipped or paused | waits for a meeting to say so |
| The term's end changes (renewal notice, amendment) | `window` reads "changed since" with both ends | keeps the old window |
| The board does not reach a decision | the `decision` step stays "on the agenda of DATE" | advances past it |
| The catalog renames a color after an award | `watch` reads "changed since" and opens `substitute` | edits the schedule |
| Two obligations share one report (a State form that does not say which inspection) | the report stays "not assigned" until a person says which; the decision whether one report may record several obligations is open (lesson `report-does-not-say-which-inspection`) | assigns a period from the form's title |
| The portal holds reports the library lacks | `file` shows the plan first, with counts; a protected portal is a person's step ("jason enters neither a password nor a code") | enters a credential or files without the plan applied |
| A tester appears on one published list under another business | `TesterCheck` says "listed under another business"; matching is on the tester's name | says "certified" |
| A test fails and the notice's days run from different dates | `NoticeClock` shows each date and its elapsed days side by side; the standing is "unknown" until every reading with an answer agrees | picks the date that counts |
| A building has no inspection date or certificate date on record | `due` reads "date not on record" and raises the question; no date is guessed | counts 2025 as the due day for a building the permit rule may reach |
| A deficiency's clearing report is dated on or before the report that found it | `clear` refuses it | accepts a record that does not post-date the finding |
| An improvement request is classified "other" | `track` is a person's step; the general clock and a question stand | invents a clock |
| A request names a provision (solar, charger) the classifier misses | the manager sets the track and the run records who did | drops the statute's clock |
| Two readings of a provision remain (for example whether a decision made at a qualifying open meeting needs a reconsideration procedure) | the run holds a question for the board and counsel, and takes the course lawful under either | settles it for the case |
| A model proposes a contract clause that is not in the text | the clause is dropped with its reason, shown as dropped | merges it quietly |
| The vendor's portal sync fails | `sync` is `failed` with the message; `read` shows the last good read and its age | repeats the sync on a timer |

## 4. The clocks and their basis

**The law's** (recited from `data/authorities`; the words are the Legislature's or the State Fire Marshal's):

| Clock | Words | Cite | Step |
|---|---|---|---|
| Exterior elevated elements, every nine years | "At least once every nine years, the board of an association of a condominium project shall cause a reasonably competent and diligent visual inspection to be conducted by a licensed structural or civil engineer or architect of a random and statistically significant sample of exterior elevated elements for which the association has maintenance or repair responsibility." | CIV 5551(b)(1) | `elevated-elements` `due`, `engage` |
| First inspection, and reports kept | "The first inspection shall be completed by January 1, 2025, and then every nine years thereafter in coordination with the reserve study inspection pursuant to Section 5550. All written reports shall be maintained for two inspection cycles as records of the association." | CIV 5551(i) | `due`, `keep` |
| A newer building | "The inspection of buildings for which a building permit application has been submitted on or after January 1, 2020, shall occur no later than six years following the issuance of a certificate of occupancy." | CIV 5551(k) | `due` |
| An immediate threat | "Upon receiving the report, the association shall take preventive measures immediately, including preventing occupant access to the exterior elevated element until repairs have been inspected and approved by the local enforcement agency." | CIV 5551(g)(1) | `preventive` |
| Sprinkler and alarm records | "Records of all testing and maintenance shall be retained on the premises by the building or system owner for a period of five years after the next required test or maintenance." | 19 CCR 904.2(c) | `keep` |
| Correction of deficiencies | "The building or system owner shall insure immediate correction of any deficiencies noted during the service." (no number: see section 8) | 19 CCR 904.2(d) | `repair` |
| The licensee's report | "It is the responsibility of the contractor, company, or licensee to provide a written report of the test and maintenance results to the building owner and the local fire authority having jurisdiction at the completion of the testing and maintenance." | 19 CCR 904.2(j) | `authority` |
| An estimate first | "An initial written estimate for the cost of repair shall be given to the customer before performing any repairs." | 19 CCR 904.2(k) | `estimate` |
| Backflow, the owner's duty | "Water users shall comply with all orders, instructions, regulations, and notices from the local health officer with respect to the installation, testing, and maintenance of backflow prevention devices." (no number) | HSC 116800 | `backflow-annual` |
| Solar | "If an application is not denied in writing within 45 days from the date of receipt of the application, the application shall be deemed approved, unless that delay is the result of a reasonable request for additional information." | CIV 714(e)(2)(B) | `improvement-request` `vote` |
| Charger | the same words with "60 days" | CIV 4745(e) | `vote` |
| Charger certificate | "Within 14 days of approval, provide a certificate of insurance" | CIV 4745(f)(1)(C) | `conditions` |
| An ordinary application | "The procedure shall state the maximum time for response to an application or a request for reconsideration by the board." (the number is the documents') | CIV 4765(a)(1) | `vote` |
| Decision in writing | "A decision on a proposed change shall be in writing. If a proposed change is disapproved, the written decision shall include both an explanation of why the proposed change is disapproved and a description of the procedure for reconsideration of the decision by the board." | CIV 4765(a)(4) | `letter` |
| Rebuild completeness | "The body shall determine whether an application is complete or incomplete and provide written notice of this determination to the applicant no later than 30 calendar days after the body receives the application." | CIV 4766(b)(1) | `complete` |
| Insurance change | "The association shall, as soon as reasonably practicable, provide individual notice pursuant to Section 4040 to all members if any of the policies described in the annual budget report pursuant to Section 5300 have lapsed, been canceled, and are not immediately renewed, restored, or replaced" (the statute continues for a nonrenewal notice) | CIV 5810 | `loss-claim` `members?` |
| Occupants out for treatment | "not less than 15 days nor more than 30 days prior to the date of the temporary relocation" | CIV 4785(b) | `vacate-notice` |
| A rule on a listed subject | "at least 28 days before making the rule change" | CIV 4360(a) | `substitute`, `guideline` |
| A board meeting's notice | "at least four days before the meeting" | CIV 4920(a) | `review`, `agenda` |
| A management agreement's statement | "in no event more than 90 days, before entering into a management agreement" | CIV 5375 | `statement` |

**The documents'** (basis `documents`; the instrument is named in the cell and is not read by this page): a contract's notice windows and delivery; the policy's protective-safeguards and notice-of-loss words; the governing documents' entry clause and the maximum response time under CIV 4765(a)(1); a supplier's notice days, each counted from every date it could run from.

**Proposed** (labeled, never stamped; the board's to adopt): the 120-day horizon that lets items coming due ride in a proposal request (`HORIZON_DAYS`); the 90-day window that flags an insurance term (`WINDOW_DAYS` in the renewals loader); a target for "immediate correction"; an acknowledgment time; an approval's lifetime; the ordinary application's times where the documents state none; the catalog check's cadence; a follow-up after a servicer's silence.

**Where the law is silent, a question for the board:** how soon a deficiency must be corrected in days; whether the insurer is told when an impairment ends; what substitutes for a discontinued color; the deductible guideline; whether a decision made at a qualifying open meeting needs a reconsideration procedure ([improvement-requests.md](../improvement-requests.md), open decision 3). The workflow holds each as a question and proposes a written policy ([AGENTS.md](../../AGENTS.md), "Where the law is silent, write it down").

## 5. The screens

Routes use the spine's **Work** group; the family adds no parallel screen. Every cell below reads a loader field; no view works out a status or a date.

### 5.1 The Work list for this family

`#/work?family=property-safety`, grouped Yours, Waiting on others, Waiting on a clock, Board. Row: the run's label, the current step, the next clock with its basis word, age. Sources (built unless marked): `life-safety` `summary` (`overdue`, `dueSoon`, `needsInput`, `noneOnRecord`, `proposedDeficiencies`, `openDeficiencies`; `impairments` and `insurerNotTold` are `null` unless the viewer opens P2); `backflow` `notices[].runsFrom[]`, `watchlist` `items[].standing`; `calendar` (elevated-element rows); `insurance-renewals` `daysToTermEnd`, `renewalWindow`, `memberNoticeNeeded`; `paint` `counts`, `needsAPerson`; `followups`; `board-items`; `approvals`; `jobs`. To add: `contracts` (`NoticeWindowView[]`), `improvement-requests`, `incidents` (a person-entered store), `work`.

### 5.2 The Run page, by definition

Step rail, step panel, clock strip, links, history, and the "changed since" banner are the spine's. The panel for each step embeds a built screen's component where one exists.

| Definition | Route | Panels (built `props`-only components unless marked) | Loader and fields |
|---|---|---|---|
| `life-safety-period` | `#/work/life-safety-period/<id>` | `read`: the system card as in [console/screens/life-safety.md](../console/screens/life-safety.md) (`StandingPill`, `Freshness`, `Findings`, `WatchRow`); `ask`: `PlanReview` and the Gmail draft preview; `file`: `ReportPortalCard`, `PortalReportRow`, `FilingPlan`, `HoldingChips` | `life-safety`; `report-portal`; `filing-plan` |
| `deficiency` | `#/work/deficiency/<id>` | the row's acts as `Timeline`; `DeficiencyRow` (to add); a banner from `banner.sentence` while an impairment has no insurer record | `life-safety` `deficiencies.rows[]` (P2) and `counts` |
| `backflow-annual` | `#/work/backflow-annual/<id>` | `NoticeClock` (every date side by side, no winner), `AssemblyRegister`, `Discrepancy`, `TesterCheck` | `backflow` `notices[]`, `assemblies[]`, `discrepancies[]`, `tester` |
| `elevated-elements` | `#/work/elevated-elements/<id>` | per-building rows: reach, `(k)` and `(l)` answers, `due`, questions; `DueDate` | `calendar` rows; a loader for `elevated_inspections.as_dict` (to add) |
| `contract-notice-window` | `#/work/contract-notice-window/<id>` | `NoticeWindow`, `TermRow`, `OwedList`, `LicenseChip`, `ContractFindings` (all to add); `DraftLetter` (built) and `ElementsCheck` (to add) for the notice | `contracts` (to add; reads `data/contracts/terms`) |
| `improvement-request` | `#/work/improvement-request/<id>` | `RequestStateStrip`, `WaitingOn`, `RequestClock`, `CompletenessList`, `ImprovementBrief`, `ConditionsTracker`, `DecisionLetterView` (all to add per the handoff); `DecisionBrief`, `RollCall`, `DraftLetter` (built) | `improvement-request` (to add) |
| `paint-cycle` | `#/work/paint-cycle/<id>` | `PaletteMatrix`, `Swatch`, `ColorDetail`, `SourcedDate` | `paint`, `paint/color?code=` |
| `loss-claim` | `#/work/loss-claim/<id>` | the five-step packet with `Recitation` per step and `held` notes; evidence chips | `loss-packet`, `unit-record`, `insurance`, `insurance-renewals` |
| `maintenance-program` | `#/work/maintenance-program/<id>` | visits, products, findings as `Findings`; the program's lifecycle (to add) | `pest_program` (MCP; no web loader found: **not verified**) |

Existing screens the runs link to, by route in `SCREENS`: `#/insurance`, `#/renewals`, `#/approvals`, `#/actions`, `#/agenda`, `#/room`, `#/decisions`, `#/duties`, `#/disclosures`, `#/reserve-findings`, `#/jobs`, `#/drafts`. Specified and not in `SCREENS`: `#/life-safety` (loader and components built, no view), `#/paint` (loader and components built, no view), `#/requests`, `#/members?unit=` (unit record), `#/contracts`, `#/programs`.

### 5.3 States every panel shows

Loading (the loader's `found` unset). Empty ("The specification lists no life safety systems"; "The association has no color schedule yet"; "No improvement requests are open"). Missing ("none on record", never "not done"; "not read"; "needs input" with the question). Stale (the catalog copy's age; a tester list older than a year; "last posted to the owner: DATE"). Blocked (by which step or fact, in words; an undetermined obligation). Changed-since (a store moved under a done step: the difference, not a silent update). Past a legal day (in the law's words).

### 5.4 Acts the screens make

Each is a `Confirm` in the signed-in person's name, with the terminal command beside it: confirm, impairs, cleared, insurer-told on a deficiency (built: `POST /api/write/life-safety/<id>`, refused while an admin views as someone else); a Gmail draft as an approval (built: `gmail-drafts`); the board's decision recorded where every vote is; a renewal decision (built: `POST /api/write/insurance-renewals/<policy>`); a loss-packet step confirmed (built). Nothing here books a vendor, accepts a proposal, tells an insurer, pays, sends, posts to PayHOA, or sets a request's status.

### 5.5 Today and the dock

The dock already counts approvals, tasks, and deadlines (`dock` loader; `Dock`). A person's open steps from this family show there with the next clock on each run and its basis word: "Tell the insurer about the open impairment (Bldg. 1, 2099-06-02; the policy's words govern)", "Notice window for the management agreement closes 2099-11-01 (documents)", "Solar request: the statute's day is 2099-11-15", "Catalog check: 1 color renamed". The run's history exports as a document for the board's record with its evidence addresses (`Doc`), including every date the clock could have run from.

### 5.6 What is specific to this family

- **Side by side, no winner.** A supplier's notice shows every date its days could run from; an assembly count that differs between sources shows each source in its own column; the paint check shows the printed name beside the catalog's. The run never settles a difference.
- **A recitation before a reading.** Each legal step shows the statute's words from section 4, then `ReadingLabel` for any reading ("the monitoring of the waterflow switch is a related supervisory service" is a reading, not the law).
- **A plan before a write.** A filing plan, a Gmail draft, a letter's words, and a Doc write each show before the one button that makes them.
- **Where the run ends.** A run ends at a record, never at an act in the world: the draft saved, the decision recorded, the proof of delivery attached, the clearing record linked.

## 6. Privacy and roles

| Step or data | Level | Who acts |
|---|---|---|
| Systems, schedule, standing, a report's building and date | P0 and P1 | manager; any signed-in roster person reads |
| A report naming units, a vendor's amount | P1 | manager, treasurer for amounts |
| Impairment, insurer told, what cleared a deficiency | P2 (may bear on a claim) | offices that open P2, never while an admin views as someone else |
| Elevated-element inspector, licence number, report name | P3 by source (`data/spec`) | private view only |
| Contract terms (they quote the contracts) | P2 (no path row; unplaced files read P2) | manager; a confidential contract held back |
| A model review by Bedrock | the words leave the machine | a named person chooses, per document |
| An improvement request and its letter | P2; a request's list never carries a contractor, cost, phone | manager, reviewer, recording officer |
| The unit's manual: a private entry | the owner's; counted, never read | the owner |
| Paint schedule and catalog | P0 | manager |
| Loss packet, claim papers | P2; a claim file's snippet is held back | manager; counsel on grant |
| Pest records, visits, products | P2 (vendors) | manager |
| Lock-box and panel codes appearing in a record | never shown | none |

Directors and officers have the same access to information (the board's decision of 2026-10-11): a director reads what an officer reads at the same level. By `jason.web.access.SEE_RULES` the roster sees P0 and P1; manager, president, vice president, director, secretary, and treasurer open P2; P3 opens only in the private view, to all of those but the treasurer. The server enforces who may act (spine, rule 4).

## 7. What exists now

Checked on October 11, 2026.

| Piece | State |
|---|---|
| SOPs | none for this family. `jason sop duty-schedule` carries one step for an overdue inspection (the proposal request); `onboard` and `ingest` carry the contract-terms and manager-change steps. The nine definitions have no `Procedure` row. |
| `jason inspections`, `jason deadlines`, `jason applies`, `jason life-safety` (list, propose, confirm, impairs, cleared, insurer-told) | built |
| `jason draft --proposal-request` and approvals kind `gmail-drafts` (cases proposal-request, hearing, meeting-notice) | built; saves a draft, never sent. Kinds in the registry: `owner-info-tags`, `payhoa-attach-bills`, `gmail-drafts` |
| Loaders in `EXTRA_LOADERS`: `life-safety`, `report-portal`, `filing-plan`, `backflow`, `watchlist`, `paint`, `paint-color`, `insurance-renewals`, `facts`, `unit-record`, `loss-packet`, `followups`, `campaign-status`, `approvals`, `dock` | built, disk only |
| Writers in `EXTRA_WRITERS`: `life-safety`, `insurance-renewals`, `unit-record`, `loss-packet` | built |
| Components, props only: `NoticeClock`, `AssemblyRegister`, `Discrepancy`, `TesterCheck`, `ReportPortalCard`, `PortalReportRow`, `FilingPlan`, `HoldingChips`, `WatchRow`, `TextGrade`, `DocumentCodes`, `PaletteMatrix`, `Swatch`, `ColorDetail`, `DecisionBrief`, `DraftLetter`, `Timeline`, `StageSteps`, `PlanReview` | built |
| Views and routes | `insurance`, `renewals`, `approvals`, `actions`, `agenda`, `room`, `decisions`, `duties`, `disclosures`, `reserve-findings`, `jobs`, `drafts` are in `SCREENS`. No view for life safety, paint, contracts, requests, unit record, or programs. |
| `jason elevated` | no command; `calendar_rows` feeds `jason deadlines` and `building_lines` feeds `jason applies` |
| `jason contract-terms`, `jason licenses` | built (`--window` is not) |
| `jason paint` (`--check`, `--match`, `--refresh`, `--to-doc`, `--page`, `--read`) | built; `--request` and `--register` are not |
| `jason incidents`, `jason insurance`, `jason pests`, `jason backflow`, `jason vendors` | built |
| `jason improvements`, `jason unit-record`, `jason programs`, `jason workflow` | not found |
| Follow-ups | kinds remind, return-by, enter-by, reports-mailed, resend, acknowledge, review, decide, answer-due, close, manual; bases law, documents, proposed policy, person. No source for an inspection, a deficiency, a notice window, or an insurance term; `add_manual` is the only way a wait gets a date. |
| Board items | `tasks.board_items.propose` exists and the category `safety` exists; a deficiency becoming an item is **not verified** |
| Base templates | `insurance-change-notice`, `flood-notice`, `board-meeting-notice`, `annual-budget-report`, `annual-policy-statement`. None for a contract notice, an entry notice, a decision letter, or an incomplete-items letter. |
| `PATH_RULES` | no rows for `life-safety/`, `contracts/`, `paint/`, `pesticides/` (unplaced reads P2, which fails closed; paint should be P0) |

## 8. Gaps and the build order

**Gaps found** (each is a finding, not a fix made here):

1. No workflow engine, and no `Procedure` for any of the nine; the definitions need their source rows first, with new `Area` values (life safety, insurance, improvements, paint, programs).
2. The deficiency register has no reject act, no estimate, repair, approval, or tag step, and no "insurer told it ended". `clear` needs a record in the library, so a report not yet filed blocks it.
3. `jason inspections` offers a proposal request, but nothing starts the board's decision, and no entry-notice template exists.
4. Drive filing (`--yes`) is a person's command, not an approvals kind; so are a palette Doc write and a PayHOA comment (`request-comment` writes without `--yes`).
5. The notice window has two edges in the terms reader (`window_days`) and one in the as-of check (`current - notice_days`); no loader or command composes `NoticeWindowView`.
6. No non-renewal or termination base template; `jason letter` fills a Doc template but none exists for this.
7. No loader for contracts, improvement requests, incidents, programs, or the pest program on the web; no views for life safety, paint, or the others.
8. An incident has no person-entered record; incidents are only read from paperwork.
9. The insurer's condition is "not composed" in the life-safety loader, so the impairment path cannot recite the policy's words.
10. No follow-up source for an inspection that went unrequested, a deficiency uncorrected, an insurance term, or a notice window.
11. `Basis` (law, documents, proposed policy, person) covers a supplier's notice only by calling it `documents`.
12. No spending-authority row, so the `repair-decision` step cannot say when the manager may act alone.
13. `fire-protection.md` attributes the owner's duty to correct deficiencies to 19 CCR 904.1(c); the text on the shelf prints it in 904.2(d). The doc should be corrected.

**Build order.**
1. `jason.workflows` (store, fold, resume), with the `Procedure` rows for `life-safety-period` and `deficiency` first (spine, section 6).
2. The `#/life-safety` view over the built loader, and `DeficiencyRow`: it makes `life-safety-period` and `deficiency` real with almost no new backend.
3. `contract-notice-window`: the `contracts` loader, `NoticeWindowView` with both edges, the base template, and the `contract-notice` approvals plan.
4. `backflow-annual` and `elevated-elements` (built readers; add the elevated loader).
5. `paint-cycle` (view over the built loader).
6. `improvement-request` (the store, loaders, and writes the handoff lists).
7. `loss-claim` (the incident record), `maintenance-program` (with the programs register).

## 9. Sample runs (made up)

**A. `life-safety-period`, "Bldg. 1 fire alarm, semiannual test, 2099 first half", for Example Village HOA**

| Step | State | Note |
|---|---|---|
| `read` | done 2099-07-02 | overdue 41 days; one report unplaced |
| `applies` | done | the system's standard is on record; one obligation undetermined, parked as a question |
| `ask` | done 2099-07-02, by M. Example | plan applied; draft saved to Example Alarm Co. |
| `send` | done 2099-07-03 | attested |
| `wait-reply` | waiting, until 2099-07-17 | a person's date; follow-up due |
| `proposal` | needs a person: board | on the agenda of 2099-07-21 |
| `entry` | not started | needs `proposal` |
| `deficiencies` | not started | child runs open after `read-report` |

**B. `deficiency`, "waterflow switch failed, Bldg. 1" (child of A)**

| Step | State | Note |
|---|---|---|
| `propose`, `confirm` | done | confirmed by M. Example, 2099-06-02 |
| `impairs` | done | impairs, by M. Example |
| `tell-insurer` | needs a person: manager | banner shown: no record the insurer was told |
| `repair-decision` | blocked | needs `estimate` |
| `clear` | not started | needs a linked record |

**C. `contract-notice-window`, "Example Management, LLC"**

| Step | State | Note |
|---|---|---|
| `read` | done | term ends 2099-12-31; non-renewal "at least 60 and no more than 120 days"; certified mail |
| `window` | done | opens 2099-09-02, closes 2099-11-01 |
| `review` | needs a person: board | on the agenda of 2099-10-15 |
| `draft` | not applicable until `choice` |  |

**D. `improvement-request`, solar, "123 Main St", received 2099-10-01**

| Step | State | Note |
|---|---|---|
| `track` | done | solar; clock set by the statute, 45 days: 2099-11-15 |
| `complete` | waiting | reasonable request for information made 2099-10-04; the clock noted as paused by a person |
| `vote` | blocked | needs `complete` |

**E. `loss-claim`, "water loss, 123 Main St", entered 2099-09-02**

| Step | State | Note |
|---|---|---|
| `record` | done | by M. Example |
| `history` | done | event: a sudden cause, cost reaches the policy's deductible, no claim on file: "claim candidate" (a lead) |
| `notify` | needs a person: manager | the policy's notice words are not read |
| `packet` | done | step 5 held: "The board has not adopted a deductible guideline" |
| `guideline` | needs a person: board | a policy proposed; a rule on a CIV 4355(a) subject needs 28 days' notice |
| `confirm-step` | 2 of 5 confirmed | by M. Example |

**F. `maintenance-program`, pest control, third quarter 2099**

| Step | State | Note |
|---|---|---|
| `standing` | done | document on file; adoption: no act on record (19 sets of minutes searched, 2 not read); implementation: current |
| `sync` | done 2099-09-28 | job succeeded |
| `read` | done | 1 question: two treatments of one building 40 days apart; the label's limit is stored |
| `vacate` | not applicable | no treatment needs occupants out |
| `licence` | needs a person: manager | before the renewal |

## 10. Acceptance criteria

1. A run of each definition can be opened with no network and no server, from the event log alone.
2. Opening a `life-safety-period` run re-evaluates `read` and records `changed` when a report newly covers a period.
3. A `deficiency` run's state equals the register's `state_of` fold; the run keeps no copy of the acts.
4. `impairs` is never set by jason; `tell-insurer` becomes required only from a person's recorded answer.
5. A deficiency cannot reach `clear` without a library record of a listed kind; free text and a subject line are refused.
6. The `ask` step's plan applied twice saves one draft; if the source changed, it saves none.
7. No step of any definition sends, signs, pays, accepts a proposal, tells an insurer, or sets a request's status.
8. A `window` shows both edges, the delivery, and today in text; a notice outside either edge reads "may not count".
9. A decision step advances only when a recorded decision exists; no skip is offered for a decision or a law's step.
10. A solar or charger run past its statute day says so in the statute's words, opens a follow-up, and marks nothing approved.
11. Every clock cell shows its basis word; a proposed number is labeled and never appears as a date to an owner.
12. The statutes in section 4 equal the words on disk (a test that greps `data/authorities` for each quoted string).
13. A page or doc for the family names no association, county, street, vendor, or person (the boundary test passes).
14. A director reads what an officer reads at the same level, and the owner view reads none of it; no impairment, insurer record, owner name, or unit appears in a run's list.
15. A `Bedrock` review is offered only to a named person, per document, and refuses a confidential file without an allowance for the run.
16. A catalog rename after an award produces `changed since` and a `substitute` step; the schedule is unchanged.
17. A child run exists for each open deficiency a report lists, and none for a report that passed with nothing open.
18. A missing store reads "not read" with its command; "none on record" never reads as "not done".
19. Every cell that says "to add" appears in the build order or is removed.
20. At 360 px each panel stacks; every state is a word; no panel scrolls sideways.

## 11. Decisions that are not this page's

- **Board:** a target for "immediate correction" (19 CCR 904.2(d)); whether the insurer is told when an impairment ends; the deductible guideline; what substitutes for a discontinued color; an acknowledgment time and an approval's lifetime for improvement requests; the ordinary application's times where the documents state none.
- **User:** whether `documents` covers a contract and a supplier's notice or `Basis` gains a fifth word; ~~whether a deficiency becomes a board item on `confirm`~~ (decided 2026-10-11: every confirmed deficiency does, prioritized by severity and deadline); whether the manager may act alone on a repair up to a limit, and where the limit lives.
- **Lessons and procedures to write when the definitions are built** (AGENTS.md, "Lessons and procedures"): a `Procedure` row for each key above, each step naming the lessons in its definition; new lessons for the gaps in section 8 that were found here (a deficiency cannot be rejected; the notice window counted on one edge in the as-of check; no board item from a deficiency; the fire-protection page's citation for the owner's duty to correct). Each stays **open** until a guard names the code or test that stops it.
- **Counsel:** whether the section on fire department inspections reaches a condominium building (HSC 13146.2 and 17921(b), as [life-safety-inspections.md](../life-safety-inspections.md) states the open question); whether an association is "the owner" of an owner-occupied unit's smoke alarm (HSC 13113.7).
