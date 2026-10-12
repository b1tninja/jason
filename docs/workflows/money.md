# Money workflows: bills, the monthly review, delinquency, the fiscal year, insurance, and the county tax

Status: **design**. A family page of [../workflows-design.md](../workflows-design.md), written to its section 5 template. It defines the association's money as durable workflows and draws their web screens on what the console already has. Nothing here is built as a run; section 7 says, item by item, what is. The user-facing screens are in [../console/screens/finance.md](../console/screens/finance.md) and [../console/handoff-mail-and-payment-attachments.md](../console/handoff-mail-and-payment-attachments.md); this page does not repeat them.

Ground rules (AGENTS.md): jason reads, checks, drafts, and plans; a person approves, mails, pays, records, and votes. Amounts are integer cents. A law is **recited** from the stored text in `data/authorities` and a reading is labeled as one. A number that is not the law's or the governing documents' is a **proposed policy** and is marked so. Where the law is silent the run holds a **question for the board**. jason never submits an account to a collection agency, records a lien, forecloses, adopts a budget, buys insurance, or pays a tax.

## 0. How the six tasks relate

```text
fiscal-year run (long: opens in budget season, closes 120 days after the year ends; two overlap)
  |- reserve study review ......... feeds the budget's reserve line and the 5570 form
  |- budget and assessment notice . feeds the annual budget report
  |- annual disclosures packet .... carries the insurance summary (5300(b)(9)), the reserve summary, the board's statements
  |- reviewed financial statement . (5305) when it applies
  '- year close
        ^ reads (links, not copies)
insurance-renewal (per policy term, about six months)     reserve-borrowing (per borrowing, up to a year)
monthly-review (per month, about two weeks)  <-- bill-attach (per month, days)  --> payment-investigation (per payment, days to weeks)
delinquency-account (per account, weeks to years)           county-tax-cycle (per tax year, Nov to Apr)
```

| Definition | Subject | Lifetime | Opened by | Hosts or feeds |
|---|---|---|---|---|
| `fiscal-year` | a fiscal year (label "2099") | long: about 18 months, runs overlap | the manager, in budget season | hosts the reserve, budget, disclosures, and 5305 phases |
| `reserve-borrowing` | one borrowing from a reserve account | up to the one-year restoration | the treasurer, when the ledger shows a borrowing or the board puts one on an agenda | feeds `fiscal-year` (year close) |
| `insurance-renewal` | one policy's next term | about six months | the manager, when the term end is near | feeds `fiscal-year` (the summary), members' notice |
| `monthly-review` | a calendar month's books | short, recurring | the treasurer | reads `bill-attach` and `delinquency-account`; ratified at a meeting |
| `bill-attach` | a month's unapproved payments | days | the manager | feeds `monthly-review`; opens `payment-investigation` runs |
| `payment-investigation` | one PayHOA transaction | short (days), or weeks waiting on mail | `bill-attach`, or any person from an invoice finding | feeds `bill-attach` |
| `delinquency-account` | one unit's assessment account | long: weeks to years | the manager, when the ledger shows a past-due balance | feeds `monthly-review` (the receivable report) |
| `county-tax-cycle` | a tax year for the association's parcels | about five months | the treasurer | feeds `bill-attach` (the county bill source) |

**Which run is long-lived.** The `fiscal-year` run is the only one that should be opened by the calendar and stay open for a year and a half; it is a spine of phases with the other runs linked to it. `delinquency-account` is long but per account and wakes only when its clock or the board does. `payment-investigation`, `bill-attach`, and `monthly-review` are short. Every run is a place a person can leave and re-enter; the long ones lean on `wait` steps and clocks.

## 1. The tasks

| # | Task | Trigger | Subject | Definitions |
|---|---|---|---|---|
| 1 | Attach bills to PayHOA payments; investigate a payment with no bill | each month before the treasurer's review; the daily PayHOA snapshot shows unapproved payments | a month; a transaction | `bill-attach`, `payment-investigation` |
| 2 | The monthly invoice review and the treasurer's review of the operating and reserve accounts (CIV 5500, 5501) | a month ends | a month | `monthly-review` |
| 3 | Delinquent accounts and collections (CIV 5650 to 5720) | the ledger shows a past-due balance | one unit's account | `delinquency-account` |
| 4 | The budget, the reserve study and borrowings, and the annual disclosures (CIV 5300, 5305, 5310, 5320, 5550 to 5570, 5605, 5615; 5515, 5510, 5502 for a borrowing) | the fiscal year approaches its end window | a fiscal year; a borrowing | `fiscal-year`, `reserve-borrowing` |
| 5 | Insurance renewals and the 5300(b)(9) summary (CIV 5800 to 5810) | a policy's term end is within the renewal window | a policy term | `insurance-renewal` |
| 6 | The county property tax cycle | a tax year's bills issue; the monthly county sync | a tax year | `county-tax-cycle` |

No `Procedure` row in `jason.community.procedures` covers any of these six (checked: its 18 keys are the owner information cycle, the board packet, mailroom, notice delivery, election, rule change, law review, intake, respond, duties, owner's manual, rule history, onboard, ingest, owner document, careful reading, and check-in). The steps below are drawn from the code, the handoffs, and the statutes, and each would become a `Procedure` row (section 8).

## 2. The definitions

Columns: **id**, **title**, **kind** (`check` `job` `plan` `person` `decision` `wait` `branch`), **role**, **needs**, **produces** (link kinds), **evidence**, **command** (terminal), **clock (basis)**, **repeat; skip**. Basis words are the spine's: `law`, `documents`, `proposed policy`, `person`. Roles: manager, treasurer, president, secretary, director, board (a `decision`, recorded by the secretary), members, any signed-in person. "Legal" steps may be skipped by nobody (spine section 7, recommended); they are done or their absence is a finding for the board.

### 2.1 `bill-attach` (task 1, the monthly pass)

When: each month before the treasurer's review. Subject: a month. Roles: manager runs it; treasurer approves attaches and reads the result.

| id | title | kind | role | needs | produces | evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|---|
| snap | Is the PayHOA snapshot fresh | check | jason | none | none | `bill-attach.snapshot.{syncedAt,ageDays,stale}` | `jason invoices --fetch` | stale after 2 days (proposed policy: the integration's default, `payhoa-transactions`) | once; skip never |
| fetch | Refresh the snapshot | job | worker | snap failed | job | job finished; new `syncedAt` | `jason invoices --fetch` (PayHOA read, fetches no write) | none | once; skipped when snap passes |
| queue | Read the queue by status | check | jason | snap | none | `bill-attach.counts`, `rows[].status` (matched, ambiguous, no match, unrouted, no source yet, not checked, already attached, no bill expected) | none (a loader) | none | once |
| srcs | Read each source that has a pending payment | job | worker | queue | job per source | each source's own stamp newer than the snapshot (`sourcesNeeded`) | `jason fetch-bills`; `jason sync-tax`; `jason vendors --sync` (a sign-in at a terminal: a `person` step) | stale-after per source in `jason cadence` (proposed policy) | per source; skipped when current |
| dry | Dry-run the attach | job | worker | srcs | `data/bills/last-dry-run.json` | `dryRun.currentWithSnapshot` true; each row `matched`/`ambiguous`/`no match` with which date matched | `jason sync-bills --dry-run` (reads PayHOA, uploads nothing) | a plan expires after 6 hours (engine: the kind's `max_age_hours`) | once |
| plan | Plan the attaches | plan | treasurer or manager | dry | approval (kind `payhoa-attach-bills`, R1, one person) | plan status; one item per matched row; applier re-reads each transaction and bill | `jason approvals plan payhoa-attach-bills --by NAME`, then `decide`, `submit`, `apply` | max age 6 hours (engine) | once; item rejected or held is recorded, not retried |
| work | Open an investigation for each row that needs one | branch | manager | queue | a `payment-investigation` run per row | rows in ambiguous, no match, unrouted, no source yet | none | none | per transaction; skipped for a row that is attached or expects no bill |
| inv | Re-read the invoice review | job | worker | plan | `invoice-review.json` | `invoices.summary` newer than the plan | `jason invoices --fetch` then `jason invoices` | none | once |
| hand | Hand the pass to the treasurer | person | manager | plan, work | note | the manager attests the counts left open and why | none | before the monthly review (person: the treasurer's day) | once; skip never |

### 2.2 `payment-investigation` (task 1, per payment)

When: a payment has no bill the sources can match, or an invoice finding names a payment already approved. Subject: a PayHOA transaction id. The outcome words are the code's (`attached-bill`, `attached-receipt-only`, `not-our-bill`, `waiting-for-mail`, `escalated`).

| id | title | kind | role | needs | produces | evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|---|
| class | Name the payee class and the rule that chose it | check | jason | none | none | `bill-investigation.routing.{payeeClass,source,byRule}` | none | none | once |
| tried | Search every store on disk by amount | check | jason | class | none | `tried[]` with each store's age; `candidates[]` (document or payment-proof) | none (a loader) | none | once, again on open |
| rule | Propose a payee row when none selected it | person | manager | class with `byRule` null | a board item (finding) | `board-items` entry | none | none | once; skip when a row selected it |
| proof | Fetch the bill or the receipt from the payee's own site | person | treasurer | tried | a file | a saved bill or receipt a person holds | none (a sign-in jason does not do) | none | once; skipped when a candidate is exact |
| keep | Keep what was saved | job | worker | proof | receipts store, bill file | `data/tax/receipts.json`, bill row | `jason county-tax --import-receipts FILE --by NAME`; `--import-bill FILE --apn A --year Y --by NAME` | none | per file |
| redry | Dry-run the source again | job | worker | keep | `last-dry-run.json` | the row now `matched` | `jason sync-bills --dry-run --source SRC` | none | once; skipped if no source owns the payee |
| attach | Attach the matched bill | plan | treasurer or manager | redry | approval (`payhoa-attach-bills`) | plan applied | `jason approvals plan payhoa-attach-bills --by NAME` | plan max age 6 hours (engine) | once |
| policy | May a payment's receipt stand in for its bill | decision | board | outcome `attached-receipt-only` | a recorded policy | board decision, date, vote, instrument | none | none (the law is silent; a held question) | once per association, not per payment; skip never |
| mail | Wait for a scan or a vendor invoice | wait | nobody | outcome `waiting-for-mail` | none | a mail item or portal file arrives that matches the amount | `jason mail`; `jason vendors --sync` | re-check at each monthly pass (proposed policy; no number is the law's) | until arrival; reopens the run |
| out | Record the outcome | person | treasurer or manager | tried | `data/bills/investigations.json` row | the writer's row: outcome, by, at, doc, note | `POST /api/write/bill-investigation/<tx>` | none | append only; later outcomes supersede |
| esc | Take it to the treasurer or the board | person | treasurer | outcome `escalated` | a board item | the item | `jason board --set` | none | once |

### 2.3 `monthly-review` (task 2)

Subject: a month. The board's duty is CIV 5500, recited in section 4. Two paths, chosen by a `branch`: the review is done at a board meeting, or independently by every director or by a subcommittee of the treasurer and at least one other director and ratified at the next meeting (CIV 5501).

| id | title | kind | role | needs | produces | evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|---|
| sync | Refresh the books | job | worker | none | snapshots | each source's stamp against its stale-after: ledger 9 days, budget 9 days, reconciliations 9 days, reports 9 days (the integration defaults, proposed policy) | `jason books --sync`; `jason budget`; `jason reconcile --fetch`; `jason ledger --fetch` | monthly (law: "on a monthly basis", CIV 5500) | per source; skipped when current |
| attach | Bills attached for the month | wait | nobody | none | link to `bill-attach` | `bill-attach` run state `done` or handed | none | none | once; skip with a reason when the board reviews without it |
| recon | Reconciliations current: operating, reserve | check | jason | sync | none | `reconciliations` per account: covered through the month, open items | `jason reconcile` | law, CIV 5500(a), (b) | per account; skip never |
| stmt | Latest bank statements on file | check | jason | none | none | the library holds a statement for each account for the month (built: the check `review-statements` pairs a statement of the month to each bank account the profile names, by the last four digits its files carry; counts only) | `jason library` | law, CIV 5500(d) | per account; skip never |
| bva | Actual against budget | check | jason | sync | none | `budget` (variance by category) | `jason budget` | law, CIV 5500(c) | once; skip never |
| ie | Income and expense statement, operating and reserve | check | jason | sync | none | `books pl` for the month; saved reports | `jason books pl`; `jason report treasurers-report period=previous-month --doc --yes` | law, CIV 5500(e) | once; skip never |
| regs | Check register, general ledger, delinquent receivable report | check | jason | sync | none | ledger report runs; `delinquency` counts | `jason books check`; `jason who-owes` | law, CIV 5500(f) | once; skip never |
| inv | Invoice findings worked | person | treasurer | attach | per finding: re-attach, re-categorize, or recover | `invoices` findings with `ok` false: none open, or each carries a reason | `jason invoices` | none | per payment; skip with a reason ("not a problem") |
| xfer | Reserve and operating transfers over the limit have prior written approval | check | jason | sync | none | transfers from `reserve_transfers`; the board's prior written approval on file (not verified: a statement model checks a limit, no run check pairs a transfer to an approval) | `jason reserves --transfers` | law, CIV 5502(a) | per transfer |
| path | Review at a meeting, or independently | branch | treasurer | recon, bva, ie, regs | chosen path | the choice, by name | none | none | once |
| rev | Review the reports | person | treasurer, directors | path | a record of who reviewed | each reviewer's name and date (no store; section 8) | none | law, CIV 5500; the day of the month is the board's (person) | per reviewer (each director, or the subcommittee) |
| rat | Ratify at the next meeting | decision | board | rev, path = independent | minutes line | minutes text: `financial-review-ratified` evidence rule | `jason schedule-evidence --watch` | law, CIV 5501: "ratified at the board meeting subsequent to the review" | once; skipped on the meeting path |
| rec | The record is filed | person | secretary | rat or rev | minutes link | the minutes record the review | none | none | once |

### 2.4 `delinquency-account` (task 3)

Subject: one unit's account (shown by unit to the treasurer and manager; a director reads what an officer reads at the same level, section 6). Steps follow CIV 5650 to 5720 and 4935. The lien and foreclosure decisions are the **board's**, never delegated (CIV 5673, 5705(c)). jason records a step the board took; it submits to no agency, records no lien, and forecloses on nothing. Standing words are `CollectionStanding`: `OWED_NO_LIEN`, `LIEN_SECURES_DEBT`, `RELEASE_DUE`, `CREDIT`.

| id | title | kind | role | needs | produces | evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|---|
| det | The ledger shows a past-due balance | check | jason | none | none | `delinquency.rows[]`: `standing`, `pastDueCents`, `ledgerSynced` | `jason sync-catalog`; `jason who-owes` | delinquent 15 days after due unless the declaration says longer (law, CIV 5650(b); documents) | per account |
| chg | Late charge and interest within the caps | check | treasurer | det | none | the ledger's charges against CIV 5650(b)(2) and (3) and the declaration (not built) | none | law, CIV 5650(b)(2), (3); documents | once |
| app | Payments applied assessments first | check | treasurer | det | none | the ledger's application order (CIV 5655(a); not built) | none | law, CIV 5655(a) | once |
| pol | The collection policy and the 5730 notice are in force | check | jason | none | none | the annual policy statement carries it (links to `fiscal-year`) | `jason packet annual-disclosures --year Y` | law, CIV 5310(a)(6), (7) | once per year |
| notice | Prepare and send the pre-lien notice by certified mail | person | manager | det, chg, app, pol | a notice record; Mailroom log | the notice ledger row `pre-lien-notice`; the Mailroom letter ids; the certified mail receipt | `jason notices`; `jason mailroom --pdf` (preview) then a person's send (certified option not verified) | law, CIV 5660 | once; skip never. No base template exists for it |
| plan | Payment plan request arrives | wait | nobody | notice | arrival | a request arrives by post or email within the notice's window | `jason responses --check`; `jason followups` | law, CIV 5665(b): 45 days, if mailed within 15 days of the notice postmark | until arrival or the window passes |
| meet | Meet the owner in executive session on a payment plan | decision | board | plan arrived | a recorded step (`payment plan offered`) | `POST /api/write/delinquency/<apn>`: decided on, vote, by | none | law, CIV 5665(b), 4935(c) | once; skip when no request |
| mc | Offer meet and confer before recording | person | manager | notice | a record (step to add) | the offer's date and the owner's reply | none | law, CIV 5670 | once; skip never |
| wait30 | Wait the 30 days | wait | nobody | notice | none | the notice's certified mail date plus 30 days has passed | `jason followups` | law, CIV 5660: "At least 30 days prior to recording a lien" | until the day; how the days are counted is counsel's |
| floor | Foreclosure floor question | check | jason | det | a finding | `floorQuestion`; assessments alone against $1,800 (the ledger's past due may include late charges: a person separates them) | none | law, CIV 5720(b), (c)(1) | per account |
| lienvote | Decide whether to record a lien | decision | board | wait30, mc | a recorded vote (the roll call is in the minutes) | the vote tally, the meeting, the minutes line | `POST /api/write/delinquency/<apn>` step `lien recorded (CIV 5673, open session roll call)` (today it also stands for the recording: section 8) | law, CIV 5673: majority vote "in an open meeting" | once; skip never. Not delegable |
| rec | Record the notice of delinquent assessment | person | president or designee | lienvote | a recorded instrument | the county index shows the filing (`jason sync-liens`; `assessment_liens`) | none | law, CIV 5675(a) to (d) | once |
| copy | Mail the recorded notice by certified mail | person | manager | rec | notice record | the ledger row `lien-copy` | `jason notices` | law, CIV 5675(e): "no later than 10 calendar days after recordation" | once; skip never |
| pay | Payment received; lien paid | branch | jason, by fact | rec | the standing `RELEASE_DUE` | ledger balance at or below zero while a lien stands | `jason sync-catalog` | none | once |
| rel | Record the release and give the owner a copy | person | manager | pay | a recorded release | the county index shows the release | none | law, CIV 5685(a): "Within 21 days of the payment" | once; skip never |
| enf | Wait 30 days after recording | wait | nobody | rec | none | the recording date plus 30 days has passed | none | law, CIV 5700(a) | until the day |
| adr | Offer meet and confer or ADR before foreclosure | person | manager | enf | a record (step to add) | the offer and the owner's choice | none | law, CIV 5705(b) | once; skip never |
| fclose | Decide whether to initiate foreclosure | decision | board | adr, floor | a recorded vote in executive session; the next open meeting's minutes name the parcel | `POST /api/write/delinquency/<apn>` step `foreclosure authorized (CIV 5720)` | none | law, CIV 5705(c), 4935(d); the vote at least 30 days before any public sale | once; skip never. Not delegable |
| alt | Small claims or another remedy | decision | board | floor under $1,800 | a recorded step | the board's decision | none | law, CIV 5720(b)(1), (3) | once |
| hand | Hand the account to an agency | person | manager | board decision | a sheet row | the agency step as the board recorded it; `jason who-owes-sheet` writes a sheet for review only | `jason who-owes-sheet` | none | the board's step; jason submits nothing |
| off | Write off | decision | board | none | a recorded step | `written off` | none | none | once |
| close | Close the account | check | jason | pay, rel or off | none | balance zero, no lien of record | `jason who-owes` | none | once |

### 2.5 `fiscal-year` (task 4)

Subject: a fiscal year. Dates the run reads: the fiscal year end, the budget meeting, the dated day, the mailing day. The window comes from the notice catalog (`Timing.window(Anchor.FISCAL_YEAR_END)`), not from a typed number. Phases: **R** reserve, **B** budget, **D** disclosures, **F** the reviewed statement, **C** close. "Collect" items are the annual packet's collection list ([../annual-disclosures.md](../annual-disclosures.md) section 5.5), not built.

| id | title | kind | role | needs | produces | evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|---|
| open | Start the run; set the dates | person | manager | none | the run | fiscal year end from the schedule; dated day chosen; room left for one correction | none (StartRun) | none | once |
| win | The window is computed and fits | check | jason | open | none | window first and last day; dated day inside; "date not on record" is a state | `jason notices --catalog` | law, CIV 5300(a), 5310(a) | once |
| R1 | The study is due | check | jason | open | none | `reserves`: latest study date, next visit and review due | `jason reserves --year Y` | law, CIV 5550(a) "At least once every three years" (applies only if the components' value reaches the statute's threshold: an applicability fact) | yearly; skip when `applies` is answered "does not apply" |
| R2 | Commission or update the study | decision | board | R1 | a recorded decision | decision record | none | none | once; skipped when not due |
| R3 | File the study | person | manager | R2 | a library file (P1) | `reserves.study` DocRef changed | `jason library` | none | once |
| R4 | Annual review of the study | decision | board | R3 or R1 | minutes line | "shall review this study, or cause it to be reviewed, annually" recorded | none | law, CIV 5550(a) | yearly; skip never |
| R5 | Adopt the reserve funding plan, with its schedule of changes | decision | board | R4 | a recorded adoption at an open meeting | decision record, meeting, vote | none | law, CIV 5560(a), (b) | per plan |
| B1 | Draft the pro forma operating budget | person | treasurer | R5 | a draft | next year's budget in PayHOA; `jason budget` | `jason budget`; `jason reserves --year Y` | documents/person: the board's date (no number is the law's) | once |
| B2 | Reserve contribution matches the plan | check | jason | B1, R5 | none | `reserve_study.checks`: "a budget off the plan"; `packet_reserve_plan` | `jason reserves --year Y` | none | once |
| B3 | Does the budget raise regular assessments | branch | jason, by fact | B1 | path | prior-year assessment against the new one (not computed anywhere found) | none | none | once |
| B4 | Test the increase against CIV 5605 | check | jason | B3 yes | a finding | 20 percent of the preceding year's regular assessment; 5 percent of budgeted gross expenses for special assessments in the aggregate | none (not built) | law, CIV 5605(a), (b) | skipped when B3 no |
| B5 | Members approve an over-limit increase | decision | members | B4 over | a recorded result | the election or meeting result | none | law, CIV 5605(b) "majority of a quorum of members" | skipped when within the limit |
| B6 | Adopt the budget | decision | board | B2, B4 | a recorded adoption | decision record; minutes | none | none: the law is silent on the day; held question. Proposed policy: adopt before the collect stage closes | once; skip never |
| B7 | Notice of the increase | person | manager | B6 | notice record | ledger row `assessment-increase` | `jason notices` | law, CIV 5615: "not less than 30 nor more than 60 days prior to the increased assessment becoming due" | once; skipped when no increase |
| D1 | Plan the packet; read gaps | job | worker | win, B6 | `plan.json` | parts found or missing, tokens open | `jason packet annual-disclosures --year Y` | none | once |
| D2 | Write the values file | job | worker | D1 | `values.json` | open tokens listed | `jason packet annual-disclosures --year Y --values` | none | once |
| D3 | Collect figures and files | person | treasurer, manager, secretary | D2 | collect items (not built) | each item: who, asked on, due by, state, value or file | none | due-by computed from the window (proposed policy) | per item; waive with a reason, never "present" |
| D4 | The insurance summary is complete | check | jason | D3, link `insurance-renewal` | none | `insurance_rows`: each policy's term in force; gaps per missing term | `jason policies --fetch` | law, CIV 5300(b)(9) | once |
| D5 | The reserve summary and the 5570 form | check | jason | R5 | none | the figures from the latest study, "based only on assets held in cash or cash equivalents" | `jason reserves --year Y` | law, CIV 5300(b)(2), 5565, 5570 | once |
| D6 | The board's statements | decision | board | B6, R5 | entered statements | each statement entered by NAME, "not yet adopted" or the meeting where adopted | none (jason never writes the board's statement) | law, CIV 5300(b)(4), (5), (6), (8) | per statement |
| D7 | Link the owner information cycle | wait | nobody | none | link | the cycle's answers entered | none | documents/law per the 4041 row | once |
| D8 | Make the templates; build a draft | plan | manager | D3, D4, D5, D6 | Docs, a draft PDF | gap pages named | `--make-templates --yes`; `--build --draft --yes` (no approvals kind is registered for it) | none | once |
| D9 | Freeze, build, check | job | worker | D8 | `run.json`, final PDF, checks | cross-part, segment, preflight, review (the freeze is not built) | `--build --yes`; `jason segments`; `jason preflight`; `jason review annual-disclosures` | none | per revision |
| D10 | Read the packet | person | named person | D9 | a reading record | "read by NAME, revision N"; adopts nothing | none | none | per revision |
| D11 | Plan the send | check | jason | D10 | none | counts, billed pages, estimate (`payhoa.pricing`) | `jason mailroom --pdf --units U --notice annual-budget-report-YEAR` | window last day, law, CIV 5300(a), 5310(a) | per variant |
| D12 | Send: email first, mail after | person | manager; treasurer second where it costs money | D11 | batches, Mailroom letters | the log (`sent.jsonl`, `jason notices KEY --sync`) | `jason mailroom --send --yes`; `jason owner-info --email-batch` style batches | law, CIV 5320(a): individual delivery of the full report or a summary; the window (above) | per channel; skip never |
| D13 | Delivery read; follow-ups | wait | nobody | D12 | follow-ups | bounces and returns, "none on record" until read | `jason notices KEY --sync`; `jason followups` | proposed policy: 24 hours (the delivery lesson) | until the window closes |
| D14 | Archive with proof | person | manager | D13 | a record in the library | sent packet, map, hashes, proof link | none | none | once |
| F1 | Does 5305 apply | branch | jason, by fact | open | path | the year's gross income against $75,000 | `jason books pl` | law, CIV 5305 | once |
| F2 | Engage a licensee | decision | board | F1 yes | a contract | recorded decision; the contract's address | none | none | once |
| F3 | Receive the review | person | treasurer | F2, year closed | a library file | the file | none | documents: the engagement's date | once |
| F4 | Distribute within 120 days | person | manager | F3 | notice record | ledger row `financial-review` | `jason notices financial-review` | law, CIV 5305: "within 120 days after the close of each fiscal year" | once; skip never when F1 yes |
| C1 | Close the run; write the lessons | person | manager | D14, F4 | lessons | `jason lessons` entries named on steps | `jason lessons --area money` (the area does not exist yet) | none | once |

### 2.6 `reserve-borrowing` (task 4)

Subject: one borrowing (key: day and transaction number, as the findings store keys it). Opened from `reserve_transfers` when it sorts a movement as a borrowing, or from an agenda that gives notice of one.

| id | title | kind | role | needs | produces | evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|---|
| spend | Is it spending for a major component, not a loan | branch | treasurer | none | path | the memo and the board's resolution | `jason reserves --transfers` | law, CIV 5510(b) | once |
| sig | Two signatures for the withdrawal | check | treasurer | none | none | the bank's record (not read by jason) | none | law, CIV 5510(a) | once; skip never |
| appr | Prior written approval over the limit | decision | board | none | written approval | approval on file | none | law, CIV 5502(a) | once; skipped under the limit |
| note | Notice of intent in a meeting notice | check | jason | none | none | `borrowings[].documents.notice`, the agenda "Notice of Intent to Borrow" | `jason reserves --transfers` | law, CIV 5515(a), 4920 | once |
| fnd | The board's written finding in the minutes | decision | board | note | `reserve-findings.json` row | `POST /api/write/reserve-findings/<key>`; minutes | none | law, CIV 5515(c) | once; skip never |
| rst | Restore the money | wait | nobody | fnd | repayment | repayment found by amount (a lead; the resolution says which loan) | `jason reserves --transfers --fetch` | law, CIV 5515(d): "within one year of the date of the initial transfer" (computed: `loan.deadline`) | until restored |
| late | A delayed restoration | decision | board | rst past its date | finding for a late restoration | same notice as a transfer, and a finding "supported by documentation" | none | law, CIV 5515(d) | only when late |
| sa | Special assessment if needed | decision | board | rst at risk | decision | decision record | none | law, CIV 5515(e), 5605 | only when needed |
| lit | Litigation use: general notice, quarterly accounting | person | manager | none | notice, accounting | the notice record | `jason notices` | law, CIV 5520 | only for litigation |

### 2.7 `insurance-renewal` (task 5)

Subject: one policy's next term. The reading is `insurance_review`; the board's decision is a closed set (`renew as quoted`, `renew with changes`, `re-bid`, `change carrier`, `let lapse`).

| id | title | kind | role | needs | produces | evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|---|
| due | The term end is near | check | jason | none | none | `insurance-renewals.policies[].daysToTermEnd`, `renewalWindow`, `standing` | `jason insurance` | 90 days before the term end (proposed policy: `WINDOW_DAYS`; the profile's schedule may set its own) | per policy |
| quote | Gather the agent's proposals | person | manager | due | files | proposals in the library or mail; Gmail headers are leads | `jason gmail --sync`; `jason mail` | none | per policy |
| min | Required limits and coverages | check | jason | quote | findings | `insurance_policies.findings`: the CIV 5800, 5805, 5806 limits | `jason policies` | law, CIV 5800(a)(4), 5805(b)(2), 5806 | per policy |
| dec | Decide the renewal | decision | board | quote, min | a recorded decision | `POST /api/write/insurance-renewals/<number>`: decision, decidedOn, by, premium, limitsChanged | none | none | once per term; skip never |
| bind | Confirm the new term is bound | person | manager | dec | declarations, premium paid or financed, policy sheet updated | `standing`: `next term paid`; new declarations in Drive | `jason policies --fetch`; `jason insurance` | none | once |
| chg | Did coverage change or lapse | branch | manager (the answer is a person's, the board's matter) | dec, bind, read | path | `memberNoticeNeeded`; the term against the term before (`ChangeKind`); the manager records the answer, and a record when it differs from the read | none | none | once |
| mem | Notice to members | person | manager | chg yes | notice record | ledger row `insurance-change` | `jason notices` | law, CIV 5810: "as soon as reasonably practicable" (no number: a held question); for a nonrenewal where replacement will not be in effect, "immediately notify" | once; skipped when no change |
| sum | Feed the summary | check | jason | bind | link into `fiscal-year` D4 | `insurance_rows` for the fiscal year | `jason packet annual-disclosures --year Y` | law, CIV 5300(b)(9) | once per fiscal year |
| read | Read whether coverage changed | check | jason | dec, bind | a suggestion for `chg`, never its answer | built: the check `insurance-changed` reads the board's recorded decision and the declarations' term against the term before; with no decision on record it passes with no suggestion and says why, so the manager answers by hand (added after `sum`; no id moved) | none | none | once |
| ovr | The answer against the read | check | jason | chg | the run's record of whether the answer agrees with the read or was given over it | built: the check `insurance-answer`; judges nothing (added after `sum`; no id moved) | none | none | once |

### 2.8 `county-tax-cycle` (task 6)

Subject: a tax year. The county tax adapter is one county's ([../adapters.md](../adapters.md); another county needs its own: [../placer.md](../placer.md)). jason pays nothing and signs in to no collector's site.

| id | title | kind | role | needs | produces | evidence | command | clock (basis) | repeat; skip |
|---|---|---|---|---|---|---|---|---|---|
| sync | Read the county's tax catalog | job | worker | none | `tax.db` rows, bill PDFs | `tax_status`; `TaxStore` stamps; stale after 35 days (proposed policy, `county-tax` cadence) | `jason sync-tax` | monthly on the 1st (proposed policy) | per parcel; skipped when current |
| stand | Read each parcel's standing | check | jason | sync | none | `tax_standing`: unpaid newest year, delinquent older years, years with no bill | `tax_account` (MCP) | none | per parcel |
| bill | Every bill has its PDF | check | jason | sync | none | the bill row has a file under `tax-bills/` | none | none | per bill |
| pdf | Save a missing bill | person | treasurer | bill missing | bill row | `jason county-tax --import-bill FILE --apn A --year Y --by NAME` | as left | none | per bill; skipped when present |
| mail | The mailed bill matches the catalog | check | jason | sync | none | `tax_bill_checks`: amounts against the stored bill | none | none | per mailed bill |
| due | Each installment's due and delinquent days | wait | nobody | stand | a follow-up | the installment dates on the calendar | `jason deadlines` | law, Revenue and Taxation Code (the text is not on the authorities shelf: cannot be recited here); jason's table is in [../insurance-and-deadlines.md](../insurance-and-deadlines.md) | per installment |
| pay | Pay the installment | person | treasurer | stand | a bank payment | the PayHOA transaction appears | none (jason pays nothing) | the delinquent day above | per installment; skip never |
| rcpt | Keep the receipt | person | treasurer | pay | `data/tax/receipts.json` | confirmation number, items in cents, last four of the tender | `jason county-tax --import-receipts FILE --by NAME` | none | per payment |
| att | Attach the bill to the payment | job, plan | worker; treasurer | rcpt, sync | approval | `county-tax` source matched one receipt, one bill, one PDF | `jason sync-bills --dry-run --source county-tax`; plan `payhoa-attach-bills` | plan max age 6 hours (engine) | per payment; a receipt that paid several bills is no match |
| cls | Close the year's installments | check | jason | att | none | balances zero per parcel | none | none | once |

## 3. Branches and failure paths

| Where | Event | What the run does | Whose move |
|---|---|---|---|
| `bill-attach.snap` | Snapshot stale or missing | `fetch` is ready; the queue shows "the snapshot is N days old" first; the run never reports a count from nothing | manager |
| `bill-attach.fetch`, `srcs` | A read fails or a source is not signed in | step `failed` with the message; the Status screen's word and fix; no retry button; `dry` stays blocked | manager, administrator |
| `bill-attach.dry` | A dry run older than the snapshot | its matches are shown as `earlier`; `plan` is blocked until a dry run is current | manager |
| `bill-attach.plan` | An item rejected or held; the plan changed since review (`changed`) | rejected item recorded, never retried; a changed plan is `superseded` and planned again; `hand` records what is left | treasurer |
| `bill-attach.plan`, apply | One upload fails | the item `failed`; the next items go on; the run is `failed` until a person resolves it | treasurer |
| `payment-investigation.class` | No payee row selects it | `rule` opens; the card says "no rule selects this payee: propose one"; a miss stays a miss | manager |
| `payment-investigation.tried` | A store is missing | that row says `not read` with its command; the others still show | manager |
| `payment-investigation.out` | `waiting-for-mail` | `mail` waits; a later sync that matches reopens the run as `reopened` ("a bill now matches"); not built | manager |
| `payment-investigation.out` | `attached-receipt-only` | the transaction stays listed in the invoice review; `policy` holds the board's question until adopted | board |
| `monthly-review.rev` | The independent path | `rat` is required at the next meeting; a review not ratified is a finding for the board | secretary |
| `monthly-review.recon` | A reconciliation not current | step `blocked` with the account; `rev` cannot be attested as complete; a person may record the review with the gap named | treasurer |
| `delinquency-account.notice` | A mailing fails or the certified receipt is missing | `wait30` does not start; the run says the notice is not proved delivered; a notice cured late starts the clock again (CIV 5690: the association recommences the required notice process at its own cost) | manager |
| `delinquency-account.lienvote` | The board declines or defers | recorded as a decision with its date; the run waits at `lienvote`; nothing advances | board |
| `delinquency-account.pay` | Payment after recording | `rel` becomes due; the run shows the 21 days; a lien still of record past it is a finding, not an error to hide | manager |
| `delinquency-account` | Balance changes under a done step | `changed`: the step reads "changed since" with the ledger's new figure; a plan the owner made is not erased | treasurer |
| `fiscal-year.win` | The window cannot be computed (fiscal year end not set) | "date not on record": a question for the manager, never a guess | manager |
| `fiscal-year.B6` | The board has not adopted by the time the collect stage needs it | an open `decision`; the run is `waiting` on the board; `D1` onward blocked; the dock shows it to the secretary | board |
| `fiscal-year.D6` | A statement not yet adopted | printed as "not yet adopted" in the draft; a final build refuses (a visible gap, never skipped) | board |
| `fiscal-year.D12` | Sent after the window closed | the run says so in the law's words and opens a follow-up; it does not hide | manager |
| `insurance-renewal.chg` | Lapse with no renewal | `mem` becomes ready at once; the run records the flag; the date is the board's reading of "as soon as reasonably practicable" | board |
| `county-tax-cycle.att` | The receipt paid several bills or names none | no match; a person decides; the investigation card opens | treasurer |
| any | A store moved under a done step | `changed`, resumed by reading the store; nothing is repeated | the step's role |

## 4. The clocks and their basis

Recited from `data/authorities/CIV/` (the stored text is jason's consolidated copy, not an official restatement). A reading is labeled; counting a period that ends on a weekend or holiday is for counsel.

| Clock | Basis | Words (stored text) | Anchor |
|---|---|---|---|
| Monthly review | law, CIV 5500 | "Unless the governing documents impose more stringent standards, the board shall do all of the following: (a) Review, on a monthly basis, a current reconciliation of the association’s operating accounts. (b) ... reserve accounts. (c) Review, on a monthly basis, the current year’s actual operating revenues and expenses compared to the current year’s budget. (d) ... the latest account statements prepared by the financial institutions ... (e) ... an income and expense statement ... (f) ... the check register, monthly general ledger, and delinquent assessment receivable reports." | each month |
| Review outside a meeting | law, CIV 5501 | "...so long as the review is ratified at the board meeting subsequent to the review and that ratification is reflected in the minutes of that meeting." | the next meeting |
| Transfers | law, CIV 5502(a) | "transfers shall not be authorized from the association’s reserve or operating accounts without prior written approval from the board of the association unless the amount of the transfer is less than" the lesser of $5,000 or 5 percent of estimated income (50 or fewer separate interests), or the lesser of $10,000 or 5 percent (51 or more) | each transfer |
| Reserve withdrawal | law, CIV 5510(a) | "The signatures of at least two persons, who shall be directors, or one officer who is not a director and one who is a director, shall be required for the withdrawal of moneys from the association’s reserve accounts." | each withdrawal |
| Borrowing | law, CIV 5515(a), (c), (d) | "if the board has provided notice of the intent to consider the transfer in a board meeting notice provided pursuant to Section 4920"; "the board shall issue a written finding, recorded in the board’s minutes"; "The transferred funds shall be restored to the reserve fund within one year of the date of the initial transfer" | the transfer |
| Reserve study | law, CIV 5550(a) | "At least once every three years, the board shall cause to be conducted a reasonably competent and diligent visual inspection ... The board shall review this study, or cause it to be reviewed, annually" | the study date |
| Funding plan | law, CIV 5560(b) | "The plan shall be adopted by the board at an open meeting before the membership of the association" | adoption |
| Increase limits | law, CIV 5605(b) | "the board may not impose a regular assessment that is more than 20 percent greater than the regular assessment for the association’s preceding fiscal year or impose special assessments which in the aggregate exceed 5 percent of the budgeted gross expenses of the association for that fiscal year without the approval of a majority of a quorum of members" | the fiscal year |
| Increase notice | law, CIV 5615 | "not less than 30 nor more than 60 days prior to the increased assessment becoming due" | the day the increase is due |
| Budget report | law, CIV 5300(a) | "an association shall distribute an annual budget report 30 to 90 days before the end of its fiscal year." | the fiscal year end |
| Policy statement | law, CIV 5310(a) | "Within 30 to 90 days before the end of its fiscal year, the board shall distribute an annual policy statement" | the fiscal year end |
| Delivery | law, CIV 5320(a) | "the association shall deliver one of the following documents to all members by individual delivery pursuant to Section 4040: (1) The full report. (2) A summary of the report ..." | the dated day |
| Reviewed statement | law, CIV 5305 | "A copy of the review of the financial statement shall be distributed to the members within 120 days after the close of each fiscal year, by individual delivery pursuant to Section 4040." (for a year of gross income above $75,000) | the year's close |
| Delinquent | law, CIV 5650(b) | "delinquent 15 days after they become due, unless the declaration provides a longer time period" | the due day |
| Pre-lien notice | law, CIV 5660 | "At least 30 days prior to recording a lien upon the separate interest of the owner of record to collect a debt that is past due under Section 5650, the association shall notify the owner of record in writing by certified mail" | the mailing |
| Payment plan meeting | law, CIV 5665(b) | "The board shall meet with the owner in executive session within 45 days of the postmark of the request, if the request is mailed within 15 days of the date of the postmark of the notice" | the request postmark |
| Lien decision | law, CIV 5673 | "the decision to record a lien for delinquent assessments shall be made only by the board and may not be delegated to an agent of the association. The board shall approve the decision by a majority vote of the directors in an open meeting." | the vote |
| Copy of the lien | law, CIV 5675(e) | "the notice shall be mailed no later than 10 calendar days after recordation" | the recording |
| Release | law, CIV 5685(a) | "Within 21 days of the payment of the sums specified in the notice of delinquent assessment, the association shall record or cause to be recorded ... a lien release or notice of rescission" | the payment |
| Enforcement | law, CIV 5700(a) | "after the expiration of 30 days following the recording of a lien created pursuant to Section 5675, the lien may be enforced" | the recording |
| Foreclosure vote | law, CIV 5705(c), 4935(d) | "The board shall approve the decision by a majority vote of the directors in an executive session."; "A board vote to approve foreclosure of a lien shall take place at least 30 days prior to any public sale." | the vote |
| Foreclosure floor | law, CIV 5720(b), (c)(1) | "less than one thousand eight hundred dollars ($1,800), not including any accelerated assessments, late charges, fees and costs of collection, attorney’s fees, or interest, may not collect that debt through judicial or nonjudicial foreclosure"; the floor does not apply to "Assessments secured by a lien that are more than 12 months delinquent." | the assessments alone |
| Insurance change | law, CIV 5810 | "as soon as reasonably practicable, provide individual notice pursuant to Section 4040 to all members if any of the policies ... have lapsed, been canceled, and are not immediately renewed, restored, or replaced, or if there is a significant change" | the lapse or change |
| Property tax installments | law, Revenue and Taxation Code | **not recited**: the text is not on the authorities shelf. Add it (`jason cite`) before any step cites a number | the bill |
| Snapshot stale after | proposed policy | 2 days; ledger, budget, reconciliations, reports 9 days; county tax 35 days (`integrations.registry` cadences) | the sync |
| Attach plan lifetime | proposed policy | 6 hours (`payhoa-attach-bills`, `max_age_hours`) | the plan |
| Date window for a match | proposed policy | plus or minus 7 days (`--date-window-days`) | the bill's date |
| Renewal window | proposed policy | 90 days before the term end (`WINDOW_DAYS`) | the term end |
| Follow-up after a send | proposed policy | read delivery again after 24 hours (the owner information lesson `bounces-are-silent`) | the send |
| The collect due-by | proposed policy | the latest day an item can arrive and leave the days the next stage needs | the dated day |

The law is silent on: the day the board adopts the budget (B6); how many days "as soon as reasonably practicable" is (CIV 5810); whether a payment's receipt may stand for its bill at the treasurer's review (`policy`). Each is a `decision` or held question, not a default.

## 5. The screens

Uses the spine's screens: **Work** (`#/work`, rows grouped Yours, Waiting on others, Waiting on a clock, Board), **Run** (`#/work/<definition>/<id>`: step rail, step panel, clock strip, links, history, changed-since), **StartRun**, and the small dialogs. Built components: `StageSteps`, `Findings`, `Command`, `Confirm`, `SecondConfirm`, `Doc`, `DueDate`, `Clock`, `NoticeClock`, `Freshness` (as `SyncBanner`'s base), `Caveats`, `Recitation`, `ReadingLabel`, `PlanReview`, `DataTable`, `Money`, `Pill`, `Stat`, `Tabs`, `RollCall`, `DecisionCard`. To add, from the spine: `WorkflowRail`, `RunStepPanel`, `ClockStrip`, `StartRun`. Spec'd by the handoffs and not built (draw them from the built parts): `PendingUtilityQueue`, `SourceSyncStrip`, `MatchPanel`, `InvestigationCard`, and the annual packet's `PacketStages`, `RequirementChecklist`, `CollectList`, `SendPlanTable`. A money step **embeds the existing screen**; it does not copy it.

| Run page | Route | Step panels use | Loaders (built) | Loaders to add |
|---|---|---|---|---|
| `bill-attach` | `#/work/bill-attach/2099-10` | `PendingUtilityQueue` (a `DataTable`) for `queue`; `SourceSyncStrip` for `srcs`; `PlanReview` for `plan`; the dry run's age as `Freshness` | `bill-attach`, `approvals`, `jobs` | none beyond `work-run` |
| `payment-investigation` | `#/work/payment-investigation/<tx>` | `InvestigationCard` for `class` and `tried`: routing, the tried stores with ages, candidates (document or payment proof), the recommendation, the five outcomes as one `Confirm` | `bill-investigation`; write `bill-investigation` | none |
| `monthly-review` | `#/work/monthly-review/2099-09` | `Findings` over `invoices`; reconciliation rows; `budget` variance; `reports` list; `SecondConfirm` is not used (a review is attested) | `budget`, `reconciliations`, `invoices`, `ledger-validation`, `collections` | `monthly-review` (one read of the five, with each snapshot's age) |
| `delinquency-account` | `#/work/delinquency-account/<apn>` | the existing `DelinquencyView` `StepPanel` (steps recorded, "Record the board's step" `Confirm`); `RollCall` on the lien vote; the clocks as `ClockStrip`; executive-session banner | `delinquency`, `collections`, `followups`; write `delinquency` | none; the step enum and clocks are code (section 7) |
| `fiscal-year` | `#/work/fiscal-year/2099` | `ClockStrip` (year end, window, dated day, answers date); the packet's `PacketStages`, `RequirementChecklist`, `CollectList`, `SendPlanTable` (all spec'd in [../console/handoff-annual-disclosures.md](../console/handoff-annual-disclosures.md), none built); the reserve and budget bands of `#/reserves` and `#/payments` | `reserves`, `reserve-findings`, `budget`, `decisions`, `board-items`, `calendar` | `annual-packet`, `annual-requirements`, `annual-parts`, `annual-collect`, `annual-checks`, `annual-send-plan`, `annual-record`, `reserve-study`, `bank-accounts`, `books-report` |
| `reserve-borrowing` | `#/work/reserve-borrowing/<key>` | the borrowing row of `#/reserve-findings` (documents notice, minutes, resolution as `Doc` chips; the finding's `Confirm`) | `reserve-findings` | none |
| `insurance-renewal` | `#/work/insurance-renewal/<policy-number-last-four>` | the policy row of `#/renewals` with the decision `Confirm`; the 5810 flag; the summary rows | `insurance-renewals`, `insurance` | `insurance-policies` |
| `county-tax-cycle` | `#/work/county-tax-cycle/2099` | a parcel table (standing, unpaid or delinquent, bill PDF as `Doc`), the receipts, the county bill source's chain as `Findings` | none for the tax store | `tax-status` (wraps `tax_status`, `tax_account`), `tax-receipts` |

**Specific to the family.**
- **Money everywhere is integer cents** rendered by `Money`; account numbers show their last four, and only to an office that opens P2.
- **Every number says how old it is**: each step panel shows the store's `syncedAt` and the stale-after beside it ("the snapshot is 4 days old; a payment made since is not listed"). A store never read is "not read" with its command, never a zero.
- **A match is a lead until a person attaches it**: the queue row says which date matched and that the bill is the only one that fits. A same-amount attachment is a lead, never the bill.
- **Recite, then read**: a statute step shows its `Recitation` (words, version in force, caveat), and the application is a `ReadingLabel`.
- **No control sends, mails, pays, records, or submits.** Every such act is a `Command` or a plan; the run records the result and who did it.

**States** for the money run pages, in each panel:

| State | The panel says |
|---|---|
| loading | "Reading the stores." with the step rail intact |
| empty | the code's own sentence: "Nothing waits on a PDF in the snapshot of DATE." Never "all caught up" |
| missing | a store absent: the band is unavailable with its command ("Bank balances are unavailable: no account snapshot on disk. Run `jason accounts`.") |
| stale | the first line of the panel: "Synced N days ago", with the integration's stale-after |
| blocked | the step that blocks it, and the fact (for example "the dry run is older than the snapshot") |
| changed since | a banner with the difference: "the ledger now shows a balance of 0; the lien is still of record" |
| waiting on a clock | the clock's words and basis; "proposed policy" is never stamped |
| waiting on the board | "Waiting on the board: lien decision. Open the decision." with `#/decisions` |

## 6. Privacy and roles

| Step group | Level | Roles that act | What others see |
|---|---|---|---|
| Bill queue, amounts, payees | P1 | manager, treasurer | roster people: counts and the queue's totals |
| Attachments, invoices, bank notices, mailed tax bills, Gmail header leads | P2 (`transactions/`, `payhoa/attachments/`, mail, Gmail) | manager, treasurer, officers | an office that does not open P2 sees the lead's kind and amount-match word, not subject, sender, or file |
| Tender last four on a county receipt | P2 and held back unless `private` | treasurer | a count |
| Reconciliations, budget, books | P1 | treasurer, manager | directors read budget against actual and reserves |
| Delinquency by unit and owner | P1 for the treasurer and manager (`personas-and-jobs.md`) | manager (records), board (decides) | executive-session subject (CIV 4935); a director reads what an officer reads at the same level |
| Payment plan meeting, foreclosure vote | executive session; the minutes name the parcel number, not the owner (CIV 5705(c)) | board, recorded by the secretary | the open minutes name the matter generally (CIV 4935(e)) |
| Reserve study | P1 (`reserve-studies/`) | treasurer, manager | owners see only the funding summary in the budget report (`reserves?view=owner`) |
| Insurance policies, claims, policy numbers | P2 (`insurance/`) | manager, treasurer | the policy number is masked in lists; claims are not in a list |
| Tax bills the association owns | P1 (`tax-bills/`) | treasurer | roster |
| The board's statements, a draft packet's figures | P1 | secretary, treasurer, manager | not delivered to members until the packet is sent |
| Gmail and mail bodies | never on a list | by explicit draft | headers only by default |

Directors and officers have the same access to information (the board's decision of 2026-10-11): a director reads what an officer reads at the same level. By `access.SEE_RULES` the roster opens P0 and P1; the manager, president, vice president, director, secretary, and treasurer open P2 and, in the private view, P3 (the treasurer since 2026-10-11).

A run's list (the Work screen) never carries an owner's name, address, contact detail, or a delinquency amount; the Work screen shows "3 delinquency runs, 1 waiting on the board". A run's export is a `Doc` with evidence addresses and the same level as its most restricted step. An admin with no office cannot open P3, and every office opens it only in the private view (`access.SEE_RULES`; the treasurer's office since 2026-10-11); the money runs open no P3.

## 7. What exists now

Verified against the repo on 2026-10-11 unless marked "not verified".

| Piece | State |
|---|---|
| Procedures | none for money (`src/jason/community/procedures.py`: 18 keys, none money). `Area` in `lessons.py` has no money area. The bill-attach build's lessons are in the handoff page only, not in `lessons.py` |
| Bill queue | `jason.tasks.bill_queue`, loader `bill-attach` (`?source=&status=`), reads the snapshot offline; `jason.tasks.bill_dry_run` keeps `data/bills/last-dry-run.json`; `PayeeClass` and `Community.payee_rules()` (`jason.community.payees`) |
| Investigation | `jason.tasks.bill_investigation`, loader and writer `bill-investigation`; outcomes in `data/bills/investigations.json` (append only) |
| Attach as an approval | `payhoa-attach-bills` in `approvals/registry.py` (R1, one person, six-hour plan); only three kinds are registered (`owner-info-tags`, `payhoa-attach-bills`, `gmail-drafts`). `sync-bills` uploads only with `--yes`; the scheduler refuses `--yes` (`scheduler.WRITES_REFUSED`) |
| County bill source | `jason.sources.county_tax`; `jason county-tax --import-receipts / --import-bill`; `data/tax/receipts.json`. The live receipts reader raises (`read_live_receipts`) |
| Invoice review | `jason invoices`, `invoice_review` MCP, loader `invoices`; shown as a tab of `#/payments`; no run, no per-finding record of what the treasurer did |
| Monthly review data | loaders `budget`, `reconciliations`, `invoices`, `collections`, `ledger-validation`, `utility-payments`; schedule evidence rules read the minutes for the review and its ratification (`schedule_evidence.RULES`). No record of who reviewed |
| Delinquency | `association_collections` (standing, `floorQuestion`, `nextStep`), loader and writer `delinquency`, `tasks/collection_steps.py` (`data/board/collection-steps.json`), screen `#/liens` (`DelinquencyView`). The notice catalog has rows `pre-lien-notice`, `payment-plan-meeting`, `lien-copy`, `notice-of-sale`; the payment plan request form exists (`form_library/ca/payment_plan.py`). The pre-lien notice has no base template (`notice_templates.py`) |
| Reserve | `jason reserves`, `reserve_study`, `reserve_transfers` (with the restoration deadline), loader `reserves`, `reserve-findings` (store `data/payhoa/reserve-findings.json`, writer), screens `#/reserves`, `#/reserve-findings` |
| Budget | `jason budget`, `budget_status`, loader `budget`; no record of an adoption beyond the decision store (`#/decisions`) |
| Annual disclosures | `jason packet annual-disclosures` has `--year`, `--values`, `--make-templates`, `--build`, `--draft`, `--building`, `--yes` only; the `annual-*` loaders, the run store, `--check`, `--collect`, `--freeze`, `--read` are not built (`commands/packet.py`). Screen `#/disclosures` is the calendar only |
| Insurance | `jason insurance`, `jason policies`, loaders `insurance`, `insurance-renewals` (writer; screen `#/renewals`), `insurance_notice` (the 5810 values), `packets.insurance_rows` (the summary; assumes the fiscal year starts January 1: `start = f"{fiscal_year}-01-01"`) |
| County tax | `jason sync-tax`, `TaxStore`, `tax_status`, `tax_account`, `tax_reassessments`; cadence `county-tax` (35 days); no console screen for the tax store |
| Scheduler | cadences exist for `payhoa-transactions` (daily), `payhoa-ledger`, `payhoa-budget`, `payhoa-reconciliations`, `payhoa-reports`, `county-tax`; no cadence for `sync-bills --dry-run` |
| Follow-ups | `FollowUpKind` has no money kind (remind, return-by, enter-by, reports-mailed, resend, acknowledge, review, decide, answer-due, close, manual); `Basis` has law, documents, proposed policy, person (reusable as the clock basis) |
| Work screens | none: no `#/work`, no `work` loader |
| Journeys | none for money in `journeys.md`; the treasurer's jobs are in `personas-and-jobs.md` |
| Not verified | whether `jason mailroom --send` can set certified mail (the pricing and the letters list know it; no flag found); whether a per-month statement is classified; the resolve stage's ambiguity after the 2026-10-10 handoff (`sources/attach.py` carries an ambiguity set, but its dry-run and live agreement was not re-run) |

## 8. Gaps and the build order

Gaps found in the build:
- **No Procedure rows, no money lesson area.** Add `Area.MONEY` and procedures `bill-attach`, `monthly-review`, `delinquency`, `fiscal-year`, `insurance-renewal`, `county-tax`; move the build's lessons into `lessons.py` (the county ACH dropped silently; a same-amount attachment taken as the bill; the work list mostly noise until payee classes). Each lesson needs its guard.
- **The bill screens are not built**: loaders and writer exist for the attach tab, queue, and investigation; there is no `ui/src` view that calls `bill-attach` or `bill-investigation`.
- **`waiting-for-mail` has no clock or reopen.** The design says a later sync that finds the bill reopens it; nothing does. A follow-up kind and a `reopened` event are needed.
- **The treasurer's review leaves no record of who reviewed.** `financial-review-*` evidence is a regular expression over minutes; the independent path (5501) has no named reviewers or ratification record in a store.
- **`collection_steps.Step` is too coarse for CIV 5650 to 5720.** Missing: meet and confer offered (5670), request to meet received (5665), copy of the recorded notice mailed (5675(e)), ADR offered (5705(b)), notice of default served (5710(b)), small claims, and the separation of the vote (5673) from the recording (the single `lien recorded` step stands for both). No clock is computed from any step: 30 days after the pre-lien notice, 45 days after a request, 10 days after recording, 21 days after payment, 30 days after recording.
- **No base template for the pre-lien notice** (every element is missing until one is written); no check of late charges or interest against CIV 5650(b); the foreclosure floor uses the ledger's past due, which can include late charges the floor excludes.
- **The delinquency loader carries no office check**: it sends owners and units to any roster person who opens it. Needs enforcing on the server by level (`access.SEE_RULES`).
- **The fiscal-year run has no store**: no `annual-*` loaders, no `--freeze`, `--collect`, `--check`, `--read`; no approvals kind for `--make-templates` or `--build` (the docs call it engine kind `google.doc`; not registered) or for a Mailroom send. No computation of the CIV 5605 limits; no typed record of a budget adoption.
- **`insurance_rows` assumes a January 1 fiscal year start.** For any other fiscal year the term in force on the first day is read on the wrong day.
- **Revenue and Taxation Code installment sections are not on the authorities shelf**, so a tax clock cannot be recited.
- **The 90-day renewal window is a code constant**, labeled proposed here but not adopted by the board.
- **`jason sync-tax` and its adapter are one county's.** Another county needs its own ([../placer.md](../placer.md)).

Build order, after the spine's engine (spine section 6, steps 1 and 2):
1. Money procedures, `Area.MONEY`, and the lessons (documents only; unblocks the engine reading `Procedure` rows).
2. **`bill-attach` and `payment-investigation`** (the spine's second family): the queue, the investigation card, the outcome, and the existing approvals kind; add the `Work` row and the attach tab.
3. **`delinquency-account`**: extend `Step`, compute the five clocks as `Basis.LAW` follow-ups, add the pre-lien base template, then the run page over `DelinquencyView`.
4. **`monthly-review`**: a review record store (who, which path, the ratification) and the one loader.
5. **`insurance-renewal`** and **`reserve-borrowing`**: both already have a board-decision store; add the clocks and the runs.
6. **`county-tax-cycle`**: put the tax code on the shelf; add the `tax-status` loader and a parcel screen.
7. **`fiscal-year`**: last; it hosts the rest and needs the `annual-*` loaders and the packet run store.

## 9. A made-up sample run

Example Village HOA, 50 separate interests. Names are plainly fake; amounts are integer cents.

**`bill-attach` for 2099-10, with one `payment-investigation`**

| Step | State | Note |
|---|---|---|
| snap | done | snapshot 2099-10-09 02:10, 1 day old |
| queue | done | 19 waiting; 26 expect no bill (hidden) |
| srcs | done | `smud` current; `idoxs` synced 2099-10-09 |
| dry | done | by Pat Example 2099-10-09 11:40, against this snapshot |
| plan | needs a person (treasurer) | 2 items: 2826 cents matched on the bill date; 6129 cents matched on the due date |
| work | needs a person (manager) | 1 investigation open: 36357 cents, class `county-tax`, no source yet |
| inv | not started | |
| hand | not started | |

`payment-investigation` for transaction 1042: class `county-tax` (rule "Example County Tax Collector ACH"); tried: tax catalog (read 2099-10-01), library, mail, Gmail headers (a notice "You sent 36357 cents": payment proof, not the bill); `proof` is waiting on the treasurer to save the receipt; outcome not recorded.

**`delinquency-account` for unit 123 Main St (A. Owner)**

| Step | State | Note |
|---|---|---|
| det | done | past due 210000 cents; no lien of the association's; ledger synced 2099-09-30 |
| notice | done | pre-lien notice sent certified 2099-08-01 |
| plan | done | no request arrived by the 15th day |
| mc | done | meet and confer offered 2099-08-01 (record to add) |
| wait30 | done | day 30 passed 2099-08-31 |
| lienvote | waiting on the board | on the 2099-10-20 agenda, open session, roll call |
| rec .. rel | not started | |
| floor | needs a person (treasurer) | assessments alone against $1,800 |

**`fiscal-year` 2099 (year end 2099-06-30, window 2099-04-01 through 2099-05-31)**

| Step | State |
|---|---|
| open, win | done |
| R1..R5 | done (study filed 2098-11-12; plan adopted 2099-01-20) |
| B1..B2 | done |
| B3..B4 | done; no increase over the limit |
| B6 | done (adopted 2099-02-17, minutes of 2099-03-17) |
| D3 | needs a person: 3 items outstanding |
| D4 | blocked: the policy has no term on file in force on the first day |
| D5 | ready |
| D6 | waiting on the board: statements not yet adopted |
| D7 | done |
| D8..D14 | not started |
| F1..F4 | not started (clock: 120 days after 2099-06-30 is 2099-10-28) |

## 10. Acceptance criteria

1. Opening `bill-attach` reads the stored snapshot and the kept dry run with no PayHOA, Google, or Keeper call; a snapshot older than its stale-after shows first; the queue lists every unapproved payment without a PDF, including unrouted and county ones, and hides "no bill expected" with its count.
2. The `plan` step's state is the approval's status; a rejected or held item is recorded; a changed plan is `superseded`.
3. `payment-investigation` writes only an outcome row in the signer's name, append only; `attached-bill` and `attached-receipt-only` name a record; no step attaches or approves.
4. `monthly-review` shows each of CIV 5500(a) to (f) with the store it was read from and that store's age; none is marked done by a click without a reviewer's name; the independent path requires the ratification step.
5. `delinquency-account` has no control that records a lien, files a notice, submits to an agency, or forecloses; the lien and foreclosure steps are `decision` steps recorded from the board's vote with a date; each clock cites its section and recites it.
6. A director reads what an officer reads at the same level on the delinquency runs, and the owner view reads none of it.
7. The `fiscal-year` run computes its window from the notice catalog; a missing fiscal year end is "date not on record"; no step says "complies" or "approved".
8. A clock past its legal day says so in the law's words and opens a follow-up; a proposed number shows "proposed" and no stamp.
9. A step done once is not repeated on reopen: an applied plan and a finished job are found by key.
10. No general doc, string, or fixture here names an association, a street, a vendor, or a person beyond the plainly fake ones.

## 11. Decisions for the user (not this page's)

- **May a step open another run** (a child `payment-investigation` from `bill-attach`, a `reserve-borrowing` from `fiscal-year`), or is a link enough? The spine says runs hold links.
- **Whether a receipt may stand in for a bill** at the treasurer's review (`policy`).
- **Whether `sync-bills --dry-run` is adopted as a scheduled read** (the engine would never schedule `--yes`).
- **The Revenue and Taxation Code sections** to put on the shelf before the tax clocks are cited.
- **Which role may record a lien's recording** (the president, a designee, or counsel), as the declaration designates (CIV 5675(d)).
