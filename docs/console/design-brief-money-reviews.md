# Design brief: the board's money oversight (the monthly review and the delinquency process)

One page of orientation for the design agent, for two screens: the monthly review ([screens/monthly-review.md](screens/monthly-review.md), `#/monthly-review`, embedded by the run `monthly-review`) and the delinquency account ([screens/delinquency-process.md](screens/delinquency-process.md), `#/work/delinquency-account/<apn>`, reached from `#/liens`). It does not repeat the specs; it says what to read in what order, what to draw, what is built, and a made-up community to draw against. The definitions are in [../workflows/money.md](../workflows/money.md) (2.3 `monthly-review`, 2.4 `delinquency-account`, 4 the clocks). Where a spec and the code disagree, the code wins and this page names the difference (section G).

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, bank, or private fact; made-up samples only ("Oakview", "A. Owner", "123 Main St", "Example Bank", dates in 2099).

## A. The idea, and the rules that run through it

**The idea, in six sentences.**

1. The Civil Code names six things the board reviews each month; the monthly review screen puts each in front of every reviewer **with its source and age**, and records **who reviewed what, by which path**. It never says the review is complete or compliant.
2. There are three recorded paths, not two: the board as a board at a meeting (5500), every director independently (5501), or the treasurer and at least one other director (5501). The two independent paths need a **ratification** at the next meeting, entered by the secretary, whose words are quoted from the stored minutes.
3. A delinquent account is a **run of 22 steps** in the order the Act sets (5650 to 5720), each with who acts, its clock, the clock's basis, and the statute's words recited before jason's reading.
4. The page shows the **board's steps apart from the manager's**. The vote to record a lien (5673, open meeting, roll call) and the recording (5675) are two steps; the foreclosure vote (5705(c)) is in executive session.
5. Every computed date reads **"computed by jason from the statute's day-count, the earliest day"** and starts from a day a person recorded; with no anchor it reads "not started". Counting a period that ends on a weekend or holiday is counsel's.
6. The page reads; a person acts, in their name, behind a `Confirm`. Nothing here mails, records a lien, submits to a collection agency, or forecloses.

**The rules** (a screen that breaks one is wrong):

- **Directors and officers have the same access to information.** There is no director-only or counts-only view of the same data. Counts-only applies to the Work list and the portfolio band, because a list is not the record; opening an account shows a director what it shows an officer.
- **The secretary records the board's decisions** (the ratification, the lien vote, the foreclosure vote). The page shows motion, vote, and outcome read from the record; it has no control that casts or changes a vote.
- **Statutes are recited verbatim** from `data/authorities` (`CIV-5500-5502.md`, `CIV-5650-5690.md`, `CIV-5700-5740.md`) in a `Recitation`, whole, with "jason's consolidated copy, not an official restatement"; the reading follows in a `ReadingLabel`. A section not on the shelf (Civil Code 2934a, CCP 415.10, CCP 116.110 to 116.810, Business and Professions Code 11211.7) reads "Not on the shelf: SECTION. `jason cite` fetches it", never words from memory.
- **Executive-session matters name the parcel, not the owner,** in anything that reaches open minutes (4935(e), 5705(c)); a step's note is checked with `minutes_privacy`. The owner's name appears only in the private view.
- **Amounts are integer cents through `Money`; a bank account shows its last four only** (`··0001`).
- **Every number says how old it is,** and a proposed number ("stale after 9 days") is labeled **proposed policy** and wears no stamp. State is a word and a glyph, never colour alone.
- **A control only tightens.** Where a board-adopted control changes who signs or the review cadence, the page shows a `ControlNotice` (section C7); the server enforces it, not the button.

## B. Reading order

1. [screens/monthly-review.md](screens/monthly-review.md), whole: "The law, recited" and "Proposal: the review record" first.
2. [screens/delinquency-process.md](screens/delinquency-process.md), whole: the 22-row table is the page.
3. This page's D beside H. Then [screens/work.md](screens/work.md), "Where a step's work happens" (reads embed, writes link out) and [design-brief-work.md](design-brief-work.md) for the run page, the rail, and `ClockStrip`.
4. [screens/finance.md](screens/finance.md) for the bands these screens sit beside; [../controls.md](../controls.md) and [screens/controls.md](screens/controls.md) for `ControlNotice`.
5. References, not to be redrawn: [design-brief-mail-and-payments.md](design-brief-mail-and-payments.md) (bill attach feeds the review's "attachments" step and the invoice findings; link it); [design-brief-annual-disclosures.md](design-brief-annual-disclosures.md) (the `fiscal-year` run; the policy statement that carries the 5730 notice is step 4 of the delinquency run; its `ClockStrip` and weekend caveat are the model here).

## C. The screens

### C1. Monthly review (`#/monthly-review?month=2099-09`)
Five bands in the spec's order, under a header that carries one line: "Reviewed by 2 (A. Treasurer, B. Director) · path: every director · ratification: not recorded" and the command to copy. Band 0, **the law**: `Recitation` of 5500 (a) to (f) and 5501, whole, then four labeled readings (the board's review is one the minutes record; "subsequent" shows the next meeting and no day count; "current" is the reviewer's judgment; "more stringent standards"). A stricter-standard band appears beside band 1 only when the profile supplies one; absent, not empty.

### C2. The review matrix (band 1, "What to look at")
`ReviewMatrix`: **six duties down** (operating reconciliation 5500(a), reserve reconciliation (b), actual against budget (c), bank statements (d), income and expense statement (e), register, ledger, and receivable (f)), and across: the **source** (store and loader), the **age** (`Freshness`: snapshot, age, stale-after, state `read | stale | missing`), the **figures** (cents and counts only), the **state**, and one **column per reviewer** (a tick is a fact a person signed with the parts they say they read; never computed, never a "done" row). Beside the six, as links and never a seventh row: transfers (5502), invoice findings. Each row has "Open the tab it comes from" and its sync command. Draw: all read; one stale ("Synced 11 days ago; stale after 9 (proposed policy)"); one missing with its command while the others still show; a part changed since a reviewer read it (`ChangedBanner`, nothing voided); bank statements "none filed for 2099-09".

### C3. Path, reviewers, and the ratification line (bands 2 and 4)
`PathChoice`: three radios, the latest word wins; for the subcommittee the members are named. Below, the roster of directors and officers with each one's review date or "no review recorded", a fact beside the statute's words and never a verdict. **The ratification line** (independent paths only; absent on the meeting path): "Next meeting on the calendar after the review: 2099-10-20 · not yet held"; "Recorded by C. Secretary"; the minutes link with `minutesState` (draft or adopted); the minutes' words as a **Quote, not a reading**. Draw: no meeting on the calendar ("Add one to the schedule"); the meeting passed with no ratification ("The meeting of 2099-10-20 has passed. No ratification is recorded." plus "Put on the board's agenda"; whether the review still counts is for counsel); ratified from draft minutes; ratified from adopted minutes. Refusals in the spec's words ("Name who reviewed." "Say which parts you read." "Only the secretary records the ratification.").

### C4. Findings and history (bands 3 and 5)
Findings by part, each a person's words with a later answer; **held** findings (about an owner's account) as "1 held finding" outside the private view. History: every act with who and when; a correction beside what it corrects, the original never removed. The caveats close the page, verbatim from the loader.

### C5. The delinquency account page, as a run (`#/work/delinquency-account/<apn>`)
Eight bands in order. Header: breadcrumb "Liens and delinquency > Parcel 000-000-000-0000 (123 Main St)", run state, and the **executive-session banner** (CIV 4935) with the ledger's age. Then:

- **Clocks** (`ClockStrip`): pre-lien notice mailed, earliest recording (+30 days), request window (15 days), plan meeting (45 days), copy due (10 days), enforcement (30 days), release due (21 days), redemption (90 days). Each: the date, a `BasisPill` (`law` and the section), the label "computed by jason from the statute's day-count, the earliest day", and the state (`not started`, `upcoming`, `passed`). A clock past its day says so in the statute's words and shows the follow-up it opened.
- **The account**: standing word (`OWED_NO_LIEN`, `LIEN_SECURES_DEBT`, `RELEASE_DUE`, `CREDIT`), past due, lien and status; "Charges vs caps: not checked (no check built)".
- **The steps**: the 22 rows grouped Notice | Plan | Lien | Release | Foreclosure, each with state, **who acts (the manager's steps and the board's steps drawn apart)**, the clock, and a row that opens its `Recitation` then a `ReadingLabel`. Then: the board's record, the lien in the county index, the floor (assessments alone against $1,800 or 12 months), the owner's requests and offers ("none stored"), routes not taken (small claims, agency sheet, write-off), the documents.

### C6. The five bits that need their own drawing
- **The pre-lien notice** (step 5, 5660): the checklist of its elements; "no base template" as the empty state; the **mail class** drawn as a fact, not a choice: "certified mail" is the law's floor (a control may add tracking or a second person; it cannot lower it); the Mailroom preview command (`jason mailroom --pdf --units U`); and the **certified receipt**: postmark day, receipt "not on file". With no receipt the 30-day clock reads "not started: the notice is not proved delivered (5660)", and a notice cured late starts it again (5690). Sending is a person's `jason mailroom --send --yes`, shown as a `Command`.
- **The payment plan record** (steps 6, 7): the request's postmark against the 15-day window, the 45-day meeting window, the board's meeting in executive session (4935(c)), the plan's terms (what the standards slot holds), and the owner's reply. States: none arrived; arrived inside 15 days; arrived after ("5665(b) sets the 45 days for a request mailed within 15"; the board's choice is a recorded decision). Readings labeled: a plan does not stop a lien (5665(d)).
- **The lien, the vote, and the recording split** (steps 10, 11, 12): three rows. The **vote** (open meeting, majority of directors, `RollCall`, minutes line naming the parcel); the **recording** (the president or designee; the county index shows number and day); the **copy mailed** (10 calendar days after recording, certified). Today the built store has one step for the vote and the recording; draw it as two and say so.
- **The floor and routes not taken** (steps 9, 20, 22): the floor as a labeled reading; "Handed to a collection agency" as a **sheet for review** (`jason who-owes-sheet`), never a submit.
- **Release** (step 13): paid, lien of record, 21 days; a lien still of record past it is a finding, shown, not hidden.

### C7. Where a control appears (`ControlNotice`)
One line at the point of the act, read-only, naming the control and linking to its card ([screens/controls.md](screens/controls.md)): on the **path** choice or the reviewer roster ("Review cadence: the board adopted a treasurer-led subcommittee on Oct 3"); on the **ratification** actor ("Recorder: the secretary records, by a control adopted Oct 3"); on the bill-attach **plan** that feeds the review ("Two signers required"); on the pre-lien notice's **send** ("Required by a control the board adopted: a second person confirms"). Draw also "adopted, not in force: the roster lacks a second director" on the path choice. The notice never hides a control and the page never offers to turn one on.

### C8. The portfolio view (counts only)
A band on `#/liens` and the Work screen's money rows: "7 delinquent accounts: Notice 3 · Plan 1 · Lien 2 · Release 0 · Foreclosure 0 · Not yet started 1" with "1 waiting on the board" and "1 past a legal date". **Counts by stage only**: no name, address, parcel, or amount. A count opens `#/liens` filtered, and the table there is the one the built view already draws. Also the monthly review's receivable row (part (f)) uses the same counts (`books_report("receivables")`, no names).

## D. The shared components, each once

Built in `ui/src/components`: `Card`, `DataTable`, `Tabs`, `Money`, `Stat`, `Pill`, `Badge`, `Glyph`, `Findings`, `Recitation`, `ReadingLabel`, `Doc`, `DueDate`, `Clock`, `NoticeClock`, `Evidence`, `Checklist`, `Confirm`, `ConfirmList`, `SecondConfirm`, `ChangedBanner`, `HeldNote`, `PrivateSwitch`, `Caveats`, `Command`, `RemoteView`, `RollCall`, `DecisionCard`, `StageSteps`, `Stamp`, `Seal`. **Not built; draw from the built parts and say so:** `Freshness`, `ReviewMatrix`, `PathChoice`, `RunStepPanel`, `WorkflowRail`, `ClockStrip`, `BasisPill`, `ControlNotice`, `ControlRow`.

| Component | What it is | Data | States |
|---|---|---|---|
| `ReviewMatrix` | Six duties by reviewer | `parts[]{key,cite,source,syncedAt,ageDays,staleAfterDays,state,figures,command}`, `record`, `roster[]{name,office}` | read; stale; missing; changed since reviewed; no review recorded |
| `Freshness` | A store's stamp and its stale-after | `syncedAt, ageDays, staleAfterDays` | fresh; stale (the first line of the part); missing with its command |
| `PathChoice` | The three paths and the members | `path`, `members[]` | meeting; every director; subcommittee; adopted-not-in-force |
| `RatificationLine` | Next meeting, who entered it, minutes link, the quote | `meetings[]`, `ratified{meeting,minutes,minutesState,by,at}` | not yet held; none on calendar; passed unratified; draft; adopted |
| `ReviewFinding` | A finding and its answers | `found`, `answered`, `held` | open; answered; held (a count outside the private view) |
| `ClockStrip` + `BasisPill` | Deadlines with basis | `clocks[]{label,date,basis,law{words,source},state,anchor}` | not started; upcoming; passed (recited); a counting caveat |
| `DelinquencySteps` | The 22 rows in five groups | `steps[]{n,title,who,clock,words,state,record}` | done; waiting on a person; waiting on the board; waiting on a clock; not recorded |
| `PreLienNotice` | Elements, class, receipt | `elements[]`, `mailClass`, `tracking`, `receipt{postmark,onFile}` | no template; mailed, no receipt; mailed with receipt; cured late |
| `PaymentPlanRecord` | Request, windows, meeting, terms | `request{postmark}`, `windows`, `plan` | none; inside 15 days; after; plan in force; default |
| `LienSplit` | Vote, recording, copy mailed | `vote{meeting,tally}`, `recorded{number,day}`, `copy{day}` | each row alone; all three |
| `PortfolioCounts` | Accounts by stage | `stages{notice,plan,lien,release,foreclosure,notStarted}`, `waitingOnBoard`, `pastLegalDay` | counts; zero ("No delinquent accounts in the ledger of DATE"); ledger missing |
| `ControlNotice` | The "required by a control" line | `control{key,title,adopted}`, `inForce`, `missing[]` | in force; adopted not in force; absent when no control applies |

**Fixed words** (use exactly): "computed by jason from the statute's day-count, the earliest day", "jason's reading, not the statute", "proposed policy", "No review is recorded for 2099-09", "has no review recorded", "No ratification is recorded", "not started", "not proved delivered", "Waiting on the board", "Not on the shelf", "Executive session matter (CIV 4935)", "Record the board's step", "Viewing as NAME (admin view): go back to yourself first". Never "complies", "met", "invalid", "overdue" in the law's voice, "approved", or "complete" on a review.

## E. Glyphs

Use the console's (`circle-check` done, `clock` waiting on a clock, `scale` a legal basis, `triangle-alert` stale or past a legal day, `circle-dashed` not recorded, `lock` held, `paperclip` a document). New, named for the idea: an **eye** for "reviewed by NAME" that never looks like a check or a stamp (as in the annual brief); a **gavel-free ballot** for the board's step (a hand on a ballot box) to tell the board's rows from the manager's; a **postmarked envelope** for a mailing with a receipt, and the same envelope with a dashed outline for "receipt not on file". Each sits beside its word.

## F. Decisions that are the design's, in one list

1. **Matrix orientation:** duties down, reviewers across (recommended), or one card per reviewer. On a narrow screen the matrix becomes one card per duty with its ticks.
2. **How the three paths read** so a subcommittee is never taken for a board-at-a-meeting review, and the ratification line is visibly absent, not empty, on the meeting path.
3. **Rail or bands for the 22 steps:** the run's rail grouped in five (recommended) with the spec's bands beneath, or bands only. The done groups collapse to one line.
4. **Where the clocks sit:** pinned under the header (recommended: a clock past its day must not be below the fold) or under the steps.
5. **How the board's steps and the manager's differ** without colour: a glyph, a column, and a group label.
6. **How a recitation opens in a row** (in place, or a side panel), and how many rows may be open at once.
7. **The portfolio band's shape:** a single stage bar with counts (recommended; a table twin) or five stat tiles.
8. **The Confirm wording** for each act, and where a `ControlNotice` sits relative to the button (above it, recommended).
9. **Print layout** of a month's review record and of the account's step history, for the board's record, every proposed or computed day labeled.

These are not the design's: who records the ratification, what a day count is on a weekend, whether a late ratification counts, the standards a payment plan must meet, and whether any step may be skipped (a legal step offers no skip).

## G. What can be designed now, and what waits

Verified against the code on 2026-10-11 (`ui/src`, `src/jason/web/sources.py`).

| Part | Built | No view, no store, or waits |
|---|---|---|
| `#/payments` (`MoneyView`, tabs Budget vs actual, Reconciliations, Invoice review, Collections) over loaders `budget`, `reconciliations`, `invoices`, `collections` | Yes; read only. Its code comment calls it "the monthly review"; it records no review | A matrix, a path, a reviewer, a ratification: **no `monthly-review` loader, no store** (`data/finance/monthly-reviews.json` is a proposal), no write |
| `#/books` (`BooksChecksView`: Utility payments, Ledger validation) | Yes | Income and expense, check register, and ledger loaders (`books-report`, `ledger-query`) are MCP only; no statement-to-month check for 5500(d) |
| `#/liens` (`DelinquencyView`) over `delinquency`, writer `POST /api/write/delinquency/<apn>` | Yes: table, standing, next step, 7 recordable steps behind `Confirm`, roll-call reminder, executive-session banner | The 22-step page, the clocks, the acts between the board's steps (notice mailed, request, offers, copy, release): **no store**. The built `Step` has one value for the lien vote and recording. The `delinquency` loader is P2 (`jason.web.gates`, 2026-10-11) |
| The Collections tab of `#/payments` | Yes, and it lists unit address and past due, to the offices that open P2 (`collections` is gated like `delinquency`, 2026-10-11) | The portfolio band is the counts-only alternative |
| Bill attach and investigation | Loaders and writer built | **No view reads `bill-attach` or `bill-investigation`** (grep of `ui/src`); drawn in the mail-and-payments brief |
| Pre-lien notice | Notice catalog rows and checklist; payment plan form | No base template. Mailroom takes `--mail-class` (standard, first-class) and `--tracking` (certified, registered); certified is untried on a live send |
| Recitations | Statutes on the shelf for 5500 to 5502, 5650 to 5690, 5700 to 5740 | Civil Code 2934a, CCP 415.10, 116.110 to 116.810, B&P 11211.7: not on the shelf |
| `Freshness`, `ClockStrip`, `BasisPill`, `RunStepPanel`, `WorkflowRail` | **None exists in `ui/src/components`** (specs call `Freshness` built) | The run engine library exists (`src/jason/workflows`); no definition is registered and the `work`, `work-run` loaders do not |
| Controls | Nothing in `src` or `ui/src` | Catalog, record, effective-approver lookup, `controls` loader, `ControlNotice`: all design only |

Draw now, from section H: C1 to C4 (the matrix and its states), C5 and C6, C8, and C7 against an assumed control. The writes (review, path, ratify, the acts between steps) are drawn as `Confirm`s against writers that do not exist.

Differences to fix in the specs, found while verifying: `finance.md` calls the screen `ConsolePayments` (the code is `MoneyView`); `money.md` 2.3 says two paths (the spec says three); `money.md` lists `Freshness` as built; the stale-after is 9 days in the review spec and 7 in `finance.md`.

## H. A made-up community to design against

"Oakview HOA": 50 units, fiscal year ending Jun 30, 2099. Board: A. Treasurer (treasurer), B. Director (director), C. Secretary (secretary), D. President (president); Pat Example (manager). Accounts: Example Bank operating `··0004`, Example Bank reserve `··0011`. Today is Oct 11, 2099.

**Monthly review, 2099-09.** Path "every director". Snapshots read Oct 5 (6 days old; stale after 9, proposed policy), except reserve reconciliation reached through Aug (1 gap, stale) and bank statements (none filed for 2099-09). Figures: net YTD -$12,040.00; past due $2,100.00 across 3 accounts; 4 invoice findings. A. Treasurer reviewed all six on Oct 9; B. Director reviewed four on Oct 10 (not statements, not receivable); C. Secretary no review recorded; D. President no review recorded. One finding: "Example Bank statement of Aug not filed" (A. Treasurer, Oct 9), answered Oct 10 by B. Director. One held finding. Next meeting 2099-10-20, not yet held; frames: ratified from draft minutes; meeting passed unratified; path "meeting" (no ratification band); path "subcommittee" (A. Treasurer, B. Director); budget changed since A. Treasurer read it; a control (review cadence) adopted Oct 3, in force and not in force.

**Delinquency, parcel 000-000-000-0000 (123 Main St, A. Owner, private view only).** Past due $2,100.00; assessments alone not separated. Pre-lien notice mailed 2099-08-01 by Pat Example, certified, receipt not on file; computed earliest recording 2099-08-31; request window closed 2099-08-16, none arrived; meet and confer offered 2099-08-01 (no record stored). Vote to record lien waiting on the board, 2099-10-20 agenda, open meeting, roll call; recording, copy, enforcement, release not started. Frames: receipt on file; a request postmarked day 20 (after the 15-day window); plan in force then default; vote 3-0 on 2099-10-20 with the minutes line naming only the parcel; lien recorded 2099-10-25, copy due 2099-11-04, enforcement from 2099-11-24; paid after recording with release due in 21 days and a lien still of record at day 25 (a finding); under the floor ("foreclosure is barred (5720(b))"); foreclosure vote in executive session, the next open minutes naming the parcel; a section not on the shelf; no ledger. **Portfolio:** 7 accounts: Notice 3, Plan 1, Lien 2, Release 0, Foreclosure 0, Not started 1; 1 waiting on the board; 1 past a legal day.

**Viewers:** D. President and B. Director read the same pages; Kim Example (an administrator with no office) sees counts and commands; A. Owner is refused; "Viewing as C. Secretary (admin view): go back to yourself first" replaces each control.

## Decisions for the user (not the design's)

1. **Ratification actor:** the secretary only (recommended), or any officer; from draft minutes (with the state updating) or only once adopted.
2. **A director who cannot sign in:** each records their own review (recommended), or the secretary records one "reported by".
3. **Snapshot in the review record:** digest plus headline cents and counts (recommended), or digest only.
4. **Collections tab and receivables:** counts only on the review (recommended), and the office check on the `delinquency` and `collections` loaders (built: P2, `jason.web.gates`).
5. **Split the lien step** into the vote and the recording, and migrate the existing rows (they stand for both).
6. **A store for the acts between the board's steps** (the clocks have no anchor without it), and a pre-lien notice base template with who adopts its wording.
7. **A written counting policy** for a period ending on a weekend or holiday, proposed to the board (Civil Code 4350), each use recorded.
8. **Whether the profile supplies a stricter review standard** (`stricter_review()`), and whether the monthly review is its own route (the spec) or a fifth tab of `#/payments`.
