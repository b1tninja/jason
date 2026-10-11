# Delinquency process

A run page, `#/work/delinquency-account/<apn>` (one parcel), reached from `#/liens` (the list, built as `DelinquencyView`), in the Money group · phase 2 · CLI: `jason who-owes`, `jason who-owes-sheet`, `jason digest`; MCP: `association_collections`, `assessment_liens`

## In the console

`#/liens` (`DelinquencyView`, loader `delinquency`, writer `POST /api/write/delinquency/<apn>`) is built. It lists each delinquent account with its standing (`OWED_NO_LIEN`, `LIEN_SECURES_DEBT`, `RELEASE_DUE`, `CREDIT`), its past-due cents, its lien, the statute's one-line next step, and the board's latest recorded step. Opening a row shows the steps recorded and a "Record the board's step" form (`Confirm`). It carries the executive-session banner. It has no clocks, no step list under Civil Code 5650 to 5720, and no record of what the owner or the association did between the board's steps. `handoff-collection-workspace.md` is about a legal case's documents and is not this screen.

**This spec is the whole run page, as proposed.** It is the `delinquency-account` definition of [money.md](../../workflows/money.md) section 2.4, drawn as one screen. The page reads; a person acts. jason never submits an account to a collection agency (`jason who-owes-sheet` writes a sheet for review only), never mails on its own initiative, never records a lien, and never forecloses. The board decides, and the secretary records the decision.

## Purpose and personas

One unit's account from the first late day to the release or the sale: each step, who acts, its clock, and the words and section it rests on, in the order the Act sets, with what is done, what is owed, and what is not recorded anywhere.

- **Manager:** sends the pre-lien notice (a person, by Mailroom), offers meet and confer, mails the copy, records the release. Reads every clock.
- **Treasurer:** reads the ledger, checks the charges against the caps, separates assessments from late charges for the floor.
- **Secretary:** records the board's votes and the minutes line that names the parcel.
- **President, vice president, directors:** read what an officer reads at the same level (the board's decision of 2026-10-11); vote at the meeting.
- **Counsel:** reads the recited words and the open questions, on grant.
- **Reviewer, owner view:** no access. The owner view reads none of it.

## Data

| Part | Source | State |
|---|---|---|
| The account: standing, balance, past due, lien number, recorded day, lien status, `lienDays`, `floorQuestion`, `nextStep`, `ledgerSynced` | loader `delinquency` over `association_collections` (`community/collections.py`, ledger `data/payhoa.db`, liens from the county index) | Built |
| The association's liens by unit, with each lien's lifecycle | MCP `assessment_liens` (`community/briefs.assessment_liens`); the filings come from `jason sync-liens` (mechanic's liens by default; `--all` adds the association's) | Built, no `jason liens` command and no console loader |
| The board's recorded steps | `tasks/collection_steps.py`, `data/board/collection-steps.json`: seven steps (`release recorded`, `payment plan offered`, `pre-lien notice sent`, `lien recorded`, `handed to collection agency`, `foreclosure authorized`, `written off`), each with `decidedOn`, `by`, `vote` (`ayes-noes`), `note`, history | Built, too coarse (below) |
| The notice catalog rows | `notice_catalog`: `pre-lien-notice` (5660), `payment-plan-meeting` (5665), `lien-copy` (5675), `lien-release` (5685), `foreclosure-decision` (5705), `notice-of-default` (5710), `notice-of-sale` (5715); each has `Anchor`, `window(anchor_day)`, its recited `words` | Built; `window()` counts whole days from the anchor, business days skip weekends, and no holiday calendar is known |
| The pre-lien notice's checklist | `notice_elements.SIGNS["pre-lien-notice"]` and `models/legal_collections.py` | Built. **No base template** (`notice_templates.py`: "no base template") |
| The payment plan request form | `form_library/ca/payment_plan.py`; generating it needs the association's plan standards or a statement that none exist (`{PAYMENT_PLAN_STANDARDS}`) | Built; the standards slot may be empty |
| The ledger's charges by kind (assessment, late charge, interest, fee) | `who-owes` gives unpaid charges tied to units; `ledger_query` omits the units' receivable accounts | **Not built as a check.** Nothing compares charges to 5650(b)(2) and (3), or to 5655(a)'s order |
| The cure, the payment plan, the pre-lien notice (mailed day, certified receipt), the meet-and-confer offer, the ADR offer, the owner's reply | none | **No store.** A step recorded by the board is not a mailing, an offer, or a plan |
| The Mailroom log | `data/mailroom/sent.jsonl` (letters, communication ids); `jason mailroom --pdf` previews. `jason mailroom --mail-class first-class --tracking certified` sets certified mail (first class only; $10.00 more a letter; added 2026-10-11, tested against PayHOA's own Mail Options rules, not yet used on a live send) | Built; certified untried live |
| The minutes | the vote line and the parcel-number rule, `tasks/minutes_privacy.py` (flags an owner's name beside a delinquency word) | Built; no link from a step to the minutes line |
| Office check | `access.SEE_RULES` | **Not on the `delinquency` loader**: it answers any roster person |

**The statute's text** is read from `data/authorities/CIV/CIV-5650-5690.md` and `CIV-5700-5740.md` (jason's consolidated copy, not an official restatement; the recorded instrument or the official page governs). Sections 5650, 5655, 5658, 5660, 5665, 5670, 5673, 5675, 5680, 5685, 5690, 5700, 5705, 5710, 5715, 5720, 5725, 5730, 4935, 5205, 5900, 5925 are on the shelf. **Not on the shelf, so not recited:** Civil Code 2934a (substituted trustee); Code of Civil Procedure 415.10 and the following (manner of service of summons, named in 5705(d) and 5710(b)); Code of Civil Procedure 116.110, 116.220, 116.221, 116.810 (small claims, named in 5658 and 5720(b)(1)); Business and Professions Code 11211.7 and 11212 (time-share exemptions in 5665(a)). The page says "not on the shelf" beside each, with the fetch command `jason cite`.

### The steps, in order

Every date is **computed by jason from the statute's day-count, the earliest day**, from a date a person recorded. How a period ending on a weekend or holiday is counted is for counsel. Every clock row recites; the right column is the reading, labeled.

| # | Step | Who acts | Clock and basis | Words (recited from the shelf) |
|---|---|---|---|---|
| 1 | Assessment becomes delinquent | nobody; the ledger shows it | Delinquent 15 days after due (law, 5650(b)); interest may run 30 days after due | "delinquent 15 days after they become due, unless the declaration provides a longer time period, in which case the longer time period shall apply" |
| 2 | Late charge and interest within the caps | treasurer checks | Law, 5650(b)(2), (3); the declaration may set less | "A late charge not exceeding 10 percent of the delinquent assessment or ten dollars ($10), whichever is greater"; "at an annual interest rate not to exceed 12 percent, commencing 30 days after the assessment becomes due" |
| 3 | Payments applied assessments first | treasurer checks | Law, 5655(a) | "shall first be applied to the assessments owed, and, only after the assessments owed are paid in full shall the payments be applied to the fees and costs of collection, attorney's fees, late charges, or interest" |
| 4 | Policy statement carries the 5730 notice | jason checks | Yearly (5310, 5730) | "The annual policy statement, prepared pursuant to Section 5310, shall include the following notice, in at least 12-point type" |
| 5 | Pre-lien notice by certified mail | manager, by Mailroom (a person sends) | At least 30 days before recording (law, 5660) | "At least 30 days prior to recording a lien ... the association shall notify the owner of record in writing by certified mail" |
| 6 | Payment plan request (owner) | owner asks; manager logs | Request mailed within 15 days of the notice's postmark (law, 5665(b)) | "if the request is mailed within 15 days of the date of the postmark of the notice" |
| 7 | Meet with the owner on a plan | board, executive session | Within 45 days of the request's postmark (5665(b); 4935(c)) | "The board shall meet with the owner in executive session within 45 days of the postmark of the request ... unless there is no regularly scheduled board meeting within that period, in which case the board may designate a committee of one or more directors" |
| 8 | Offer meet and confer | manager | Before recording (law, 5670) | "Prior to recording a lien for delinquent assessments, an association shall offer the owner and, if so requested by the owner, participate in dispute resolution" |
| 9 | Floor question | treasurer | 5720(b), (c)(1) | "less than one thousand eight hundred dollars ($1,800), not including any accelerated assessments, late charges, fees and costs of collection, attorney's fees, or interest, may not collect that debt through judicial or nonjudicial foreclosure"; "more than 12 months delinquent" |
| 10 | Vote to record a lien | board, open meeting, roll call | Not delegable (5673) | "shall be made only by the board and may not be delegated to an agent of the association. The board shall approve the decision by a majority vote of the directors in an open meeting. The board shall record the vote in the minutes of that meeting." |
| 11 | Record the notice of delinquent assessment | president or the person designated | Earliest recording is notice postmark plus 30 days (computed) | 5675(a) to (d): the notice states the amount, a legal description, the owner's name, and the trustee for nonjudicial sale; signed by the designated person or the president |
| 12 | Mail the recorded notice, certified | manager | No later than 10 calendar days after recording (5675(e)) | "the notice shall be mailed no later than 10 calendar days after recordation" |
| 13 | Payment; record the release; copy to owner | manager | Within 21 days of payment (5685(a)); a lien recorded in error, 21 calendar days (5685(b)) | "Within 21 days of the payment of the sums specified in the notice of delinquent assessment, the association shall record or cause to be recorded ... a lien release or notice of rescission" |
| 14 | Enforcement may begin | nobody; a wait | After 30 days following recording (5700(a)) | "after the expiration of 30 days following the recording of a lien created pursuant to Section 5675, the lien may be enforced in any manner permitted by law" |
| 15 | Offer meet and confer or ADR before foreclosure | manager | Before initiating (5705(b)); the owner chooses; no binding arbitration for a judicial foreclosure | "the association shall offer the owner and, if so requested by the owner, participate in dispute resolution" |
| 16 | Vote to initiate foreclosure | board, executive session | Not delegable; vote at least 30 days before any public sale (5705(c); 4935(d)) | "The board shall approve the decision by a majority vote of the directors in an executive session. The board shall record the vote in the minutes of the next meeting of the board open to all members ... by the parcel number of the property, rather than the name of the owner or owners." |
| 17 | Notify the owner of the decision | board's agent | Occupying owner: personal service; other: first-class mail (5705(d)) | "notice by personal service in accordance with the manner of service of summons" (the manner is not on the shelf) |
| 18 | Notice of default; trustee's sale | trustee, with the association | 5710(b); 5715(b): sale notice states the right of redemption | "shall serve a notice of default on the person named as the owner" |
| 19 | Redemption | owner | Ends 90 days after the sale (5715(b), computed) | "The redemption period ... ends 90 days after the sale." |
| 20 | Small claims or another remedy | board decides | Under the floor (5720(b)(1), (3)) | "a civil action in small claims court"; "Any other manner provided by law, except for judicial or nonjudicial foreclosure" |
| 21 | A step done wrong | manager | Before recording (5690) | "shall, prior to recording a lien, recommence the required notice process. Any costs ... shall be borne by the association" |
| 22 | Handed to a collection agency; written off | board decides; a person | None in this Act | jason submits nothing; `who-owes-sheet` writes a sheet |

Readings (each labeled "jason's reading, not the statute"): a payment plan does not stop a lien (5665(d)) and stops added late fees while the owner complies (5665(c)); a default lets collection resume "from the time prior to entering into the payment plan" (5665(e)). A recorded vote is the board's step 10; the recording is step 11. The built store has one step, `lien recorded`, for both.

## Layout

One account, eight bands in order, so the page reads as the Act does. The Work screen's row for it carries no name, address, or amount: "3 delinquency runs, 1 waiting on the board".

```
+------------------------------------------------------------------------------------------+
| Liens and delinquency > Parcel 000-000-000-0000 (123 Main St)         [copy] Run: open   |
| EXECUTIVE SESSION MATTER (CIV 4935). jason shows; a person acts. Ledger synced 2099-09-30 |
+------------------------------------------------------------------------------------------+
| CLOCKS  (computed by jason from the statute's day-count, the earliest day; counsel counts |
|          a period that ends on a weekend or holiday)                                      |
| Pre-lien notice mailed 2099-08-01 ... earliest recording 2099-08-31   [LAW 5660]  passed  |
| Request window closes 2099-08-16 (none arrived)            [LAW 5665(b)]          passed  |
| Lien recorded -  | copy due -  | enforcement -  | release due -        [LAW]  not started  |
+------------------------------------------------------------------------------------------+
| 1 THE ACCOUNT   OWED_NO_LIEN · past due $2,100.00 · assessments alone: not separated      |
|   Charges vs caps: not checked (no check built) · Order of application: not checked       |
+------------------------------------------------------------------------------------------+
| 2 THE STEPS   (22 rows above, grouped: Notice | Plan | Lien | Release | Foreclosure)      |
|  done      Pre-lien notice by certified mail   Aug 1 by Pat Example  receipt: not on file |
|  done      Meet and confer offered             Aug 1                  (no record stored)  |
|  waiting   Vote to record a lien   board, open meeting, roll call  [Record the board's step]|
|  later     Record notice of delinquent assessment                                         |
|  [Recitation] each row opens its statute words, then [ReadingLabel] jason's reading       |
+------------------------------------------------------------------------------------------+
| 3 THE BOARD'S RECORD  vote 3-0 on 2099-10-20 · minutes line: Parcel 000-000-000-0000      |
|   Open minutes name the parcel, not the owner. [Record the board's step]                  |
+------------------------------------------------------------------------------------------+
| 4 THE LIEN IN THE COUNTY INDEX   number, recorded day, status, release  [Read the index]  |
| 5 THE FLOOR  assessments alone against $1,800 or 12 months · jason's reading, labeled      |
| 6 OWNER'S REQUESTS AND OFFERS   plan request, meet and confer, ADR: none stored           |
| 7 ROUTES NOT TAKEN   small claims · agency sheet (jason submits nothing) · write-off       |
| 8 THE DOCUMENTS  pre-lien notice: no base template · Mailroom log · recorded instruments    |
+------------------------------------------------------------------------------------------+
| Caveats (verbatim from the loader) and: jason's text is not an official restatement.      |
+------------------------------------------------------------------------------------------+
```

## Components

Built: `ScreenHeader`, `Card`, `DataTable`, `Money`, `Pill`, `Badge`, `StageSteps`, `Clock`, `NoticeClock`, `DueDate`, `Recitation`, `ReadingLabel`, `Findings`, `Caveats`, `Command`, `Confirm`, `SecondConfirm`, `RollCall`, `DecisionCard`, `Evidence`, `Doc`, `RemoteView`. To add from the work spine: `RunStepPanel`, `ClockStrip` (each deadline with its basis; a law clock recites then reads; a proposed number shows "proposed" and no stamp). The step rail groups the 22 rows into five and shows `done`, `waiting on a person`, `waiting on the board`, `waiting on a clock`, `not recorded`. No state is conveyed by color alone. The vote and the recording are two rows, never one.

## Actions

| Control | Does | Approval? | CLI or command |
|---|---|---|---|
| Record the board's step | `record_step`: step, `decidedOn`, `by`, `vote` as `ayes-noes`, note. Appends; edits and deletes nothing. The lien step shows the roll-call reminder first | No: a signed record, behind `Confirm` | `POST /api/write/delinquency/<apn>` |
| Record an act (to add): notice mailed with postmark and certified receipt; request received with postmark; meet and confer offered; ADR offered; copy mailed; release recorded | New store (below). Each takes a day, who, and a reference; none sends anything | No: a signed record | none yet |
| Preview the pre-lien notice | Shown as the Mailroom preview command; the notice has no base template | No | `jason mailroom --pdf` with `--units` |
| Send the notice, mail the copy | Not a console action. A person sends from the Mailroom with `--send --yes` | Outside the console | `jason mailroom --send --yes` |
| Read the county index | Shown as a command | No | `jason sync-liens` (`--all` for the association's filings) |
| Write the review sheet | Shown as a command; a sheet for review, nothing submitted | No | `jason who-owes-sheet` |
| Open the minutes line | `jason://min/DAY` | No | none (the record link only) |

There is no control that records a lien, files a notice, submits to an agency, forecloses, or starts a trustee's sale. A clock past its legal day says so in the law's words and opens a follow-up (`Basis.LAW`); the owner is never contacted from this page.

## States

- **No ledger:** "No PayHOA catalog at data/payhoa.db. `jason sync-catalog` reads it." (the loader's own note).
- **Ledger stale:** the sync age beside the figure; the clocks still show, marked "from a ledger N days old".
- **Notice not proved delivered** (no certified receipt stored): the 30-day clock is not started; the run says so, naming 5660, and a notice cured late starts it again (5690: the association recommences the notice process at its own cost).
- **Request after the 15th day:** "Mailed after 15 days of the notice's postmark. 5665(b) sets the 45 days for a request mailed within 15." The board's choice is recorded as a decision, not decided here.
- **Under the floor:** "Under $1,800 in assessments alone and not 12 months delinquent: foreclosure is barred (5720(b))." The ledger's past due may include late charges the floor leaves out; a person separates them.
- **Paid, lien of record:** `RELEASE_DUE`; the 21 days from the payment day; a lien still of record past it is a finding, shown, not hidden.
- **Balance changed under a done step:** "changed since", with the ledger's new figure; a plan the owner made is not erased.
- **Board declined or deferred:** recorded as a decision with its date; the run waits at the vote.
- **A section not on the shelf:** "Not on the shelf: Code of Civil Procedure 415.10. `jason cite` fetches it." No words are written from memory.
- **No office check:** until the loader enforces `access.SEE_RULES`, the screen is not offered to a roster-only person.

## Privacy

- Executive-session subject (CIV 4935): P1, the treasurer and manager by unit; directors and officers the same level as officers, the same information. The owner view reads none of it. The Work list carries counts only.
- The page names the parcel and the address; the owner's name appears only in the private view. Minutes and exports name the parcel, not the owner (5705(c)); the open minutes note the matter generally (4935(e)). A step's `note` is checked with `minutes_privacy`.
- The county index, the recorded notice, and the county's lien filings are public records; the ledger, the plan, and the owner's replies are not.
- jason shows the clocks and records; it does not advise the owner, and what a payment plan means for one owner is for counsel.

## Acceptance criteria

1. The run renders the 22 rows in order, each with who acts, its clock, its basis, and its recited words before any `ReadingLabel`.
2. Every computed date reads "computed by jason from the statute's day-count, the earliest day", from a recorded anchor day; with no anchor it reads "not started".
3. The vote to record (5673) and the recording (5675) are two steps; the vote is by roll call in an open meeting, the foreclosure vote (5705(c)) in executive session, and the minutes line names the parcel.
4. No control records a lien, sends a notice, submits to an agency, or forecloses; `who-owes-sheet` and the Mailroom are shown as commands.
5. Sections not on the shelf are named as such; no sentence is written from memory.
6. A clock past its day says so in the statute's words, opens a follow-up, and does not hide.
7. With the private view off, no owner's name appears. The Work list shows no amount or name.
8. A director sees what an officer sees at the same level; the owner view receives 403.
9. The built record steps still work and their history is kept; a step is never edited.

## Decisions for the user

- **A store for the acts between the board's steps** (notice mailed with postmark and receipt, request received, meet and confer offered, ADR offered, copy mailed, release recorded, a payment plan with its terms). Without it the clocks have no anchor. `collection_steps.Step` is too coarse.
- **Split `lien recorded` into a vote and a recording**, and migrate the existing rows (they stand for both).
- **A pre-lien notice base template** from `notice_elements.SIGNS` (the foreclosure warning in 14-point boldface or capitals), the itemized statement, and the payment plan form. Who adopts the wording: the board, with counsel.
- **Late-charge and interest check against the caps and the declaration's lesser figure**, and the order of application; it needs the ledger's charges by kind.
- **Certified mail:** `jason mailroom` now takes `--tracking certified` (with `--mail-class first-class`); a person confirms it on the first live use that PayHOA records it, and that the certified receipt can be stored.
- **Whether a late-charge-excluded figure for the floor** can be taken from PayHOA, or stays a person's separation.
- **A written counting policy**: the shelf's text does not say how "at least 30 days", "within 21 days", or "30 days following" is counted when it ends on a weekend or holiday. jason computes the earliest day and labels it; counsel reads the rest. Propose a policy for the board to adopt (Civil Code 4350), and record each use.
- **The office check on the `delinquency` loader** before this page is exposed.
