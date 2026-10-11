# Monthly review

A new screen, `#/monthly-review` (`?month=2099-09`), in the Money group · phase 2 · the run page `#/work/monthly-review/2099-09` embeds it · CLI: `jason monthly-review` (to add; today `jason budget`, `jason reconcile`, `jason books`, `jason ledger`, `jason invoices`, `jason who-owes`, `jason schedule --done`)

## In the console

Everything to look at is on screen, in four tabs and a second screen. The record of the review is on none:

| Built (checked in `ui/src/App.tsx`, `ui/src/views/MoneyView.tsx`, `src/jason/web/sources.py`) | What it shows |
|---|---|
| `#/payments`, `MoneyView`, tabs Budget vs actual, Reconciliations, Invoice review, Collections | loaders `budget`, `reconciliations`, `invoices`, `collections`. [finance.md](finance.md) calls this screen `ConsolePayments`; that name is in no code searched, `MoneyView` is the built one |
| `#/books`, `BooksChecksView` | loaders `utility-payments`, `ledger-validation` |
| The dock and `#/duties` | the schedule's monthly assignment and its evidence rules over the minutes (`schedule_evidence.RULES`, keys `financial-review-*`: regular expressions over minutes text, a lead); `schedule.record_done` writes `data/schedule/done.jsonl` (who, due, done, evidence) |

**Not built.** The `monthly-review` loader; the review record (no store: who reviewed, by which path, what, what was found, the ratification); loaders for the income and expense statement (`books_report("pl")` is MCP only; `books-report` is proposed in [finance.md](finance.md)), the check register and monthly general ledger (`ledger_query`, MCP only), and the month's bank statements (the library holds them; no check pairs a statement to a month, [money.md](../../workflows/money.md) section 7). No `Freshness` component in `ui/src/components`. The `work` and `work-run` loaders do not exist. Snapshot stamps: `budget` carries `syncedAt`, `collections` `ledgerSynced`, the books `snapshotSyncedAt`; a stamp on `reconciliations` and `ledger-validation` was not found (not verified).

**This spec is the whole screen, as proposed.** It reads the built loaders and adds the review record, labeled a proposal below. jason assembles what to look at. The review is a person's act, and the screen offers no control that says a review is "complete" or "compliant".

## Purpose and personas

One month's financial review, from the six things the Civil Code names to the minutes line that records it: what was put in front of each reviewer, who reviewed it, by which path, what they found, and the ratification where the independent path needs one. Directors and officers have the same access to information (the board's decision of 2026-10-11): every director sees what the treasurer sees.

- **Treasurer:** opens the month, reads each part, records their own review and findings. Holds an office, and is named in the statute's subcommittee.
- **Director:** reads every part and records their own review. On the independent path every director records one.
- **Secretary:** the board's official record keeper. Records the ratification and the minutes link.
- **Manager:** runs the syncs (shown as commands); reads the screen. Records no review.
- **Counsel, member:** no access.

## The law, recited

Recited at design time from the stored text (`data/authorities/CIV/CIV-5500-5502.md`: Stats. 2018, Ch. 396, operative 2019-01-01; jason's consolidated copy, not an official restatement). Both sections are on the shelf. The page shows them in `Recitation`, whole, and rereads the file at build time; a section missing from the shelf then reads "recited from the shelf at build time: not on the shelf".

> **CIV 5500.** "Unless the governing documents impose more stringent standards, the board shall do all of the following: (a) Review, on a monthly basis, a current reconciliation of the association’s operating accounts. (b) Review, on a monthly basis, a current reconciliation of the association’s reserve accounts. (c) Review, on a monthly basis, the current year’s actual operating revenues and expenses compared to the current year’s budget. (d) Review, on a monthly basis, the latest account statements prepared by the financial institutions where the association has its operating and reserve accounts. (e) Review, on a monthly basis, an income and expense statement for the association’s operating and reserve accounts. (f) Review, on a monthly basis, the check register, monthly general ledger, and delinquent assessment receivable reports."

> **CIV 5501.** "The review requirements of Section 5500 may be met when every individual member of the board, or a subcommittee of the board consisting of the treasurer and at least one other board member, reviews the documents and statements described in Section 5500 independent of a board meeting, so long as the review is ratified at the board meeting subsequent to the review and that ratification is reflected in the minutes of that meeting."

**Structure, verified.** 5500 has six numbered duties and no other path. 5501 is one sentence with no subdivisions: it names two groups of reviewers (every individual member of the board, or the treasurer and at least one other board member) and one condition (ratified at the next meeting, reflected in the minutes). So the screen has **three** recorded paths, not two: the board's review as the board (5500), the independent review by every director (5501), and the independent review by a subcommittee (5501).

**Readings, each labeled (`ReadingLabel`, "jason's reading, not the statute"):**
- 5500 does not say the board reviews at a meeting. The screen reads "the board's review" as one the minutes record, and asks for the meeting day. A reading, for the board and counsel.
- 5501 "the board meeting subsequent to the review": the screen shows the next meeting on the calendar after the review day and states no day count. Whether a later meeting still counts, and how to count a meeting that is cancelled, is for counsel.
- 5500 "current": the screen shows how far each reconciliation reaches and the age of each snapshot, and says nothing about whether it is "current". That is the reviewer's judgment.
- 5500 "more stringent standards": the governing documents may ask more (the screen shows a band if the profile supplies one, below). Where they ask less, the statute governs; jason notes a conflict and resolves none (`jason conflicts`).

## Data

| Part | Cite | Source today | Loader |
|---|---|---|---|
| Operating reconciliation | 5500(a) | `bank_reconciliations`: months reconciled, gaps, latest statement ending, register balance, open items with age, ledger mismatches | `reconciliations` (built; one account card per account, purpose from the specification) |
| Reserve reconciliation | 5500(b) | same | same |
| Actual against budget | 5500(c) | `budget_status`: year to date and full year, the categories furthest from budget | `budget` (built; `syncedAt`) |
| Bank statements | 5500(d) | the library's statement for each account for the month; Plaid balances beside, labeled "can lag the bank" | none; `library` search; month pairing not verified. Proposed: a row per account with the statement's `Doc` chip, or "none filed for 2099-09" |
| Income and expense statement | 5500(e) | `books_report("pl")` for the month, operating and reserve; saved treasurer's reports validated by `ledger_validation` | `books-report` (to add), `ledger-validation` (built) |
| Check register, general ledger, delinquent assessment receivable | 5500(f) | `ledger_query` and `books_report("check")` for the month; `books_report("receivables")` (totals and counts, no names); `association_collections` for standing | `ledger-query` (to add), `books-report` (to add), `collections` (built) |
| Beside the six, not part of them | 5502(a) | transfers needing prior written approval: `reserve_transfers` | `reserves` (built). Shown as a link, never as a seventh duty |
| Invoice findings | none | `invoice_review`: payments with questions | `invoices` (built). A worked list for the treasurer, not a statutory item |

**The `monthly-review` loader (to add), one read of the above.** `GET /api/monthly-review?month=2099-09` returns `parts[]` (key `recon-operating`, `recon-reserve`, `budget`, `statements`, `income-expense`, `registers`), each with `cite`, `source`, `syncedAt`, `ageDays`, `staleAfterDays` (the integration default, 9 days; proposed policy, not the law's), `state` (`read`, `stale`, `missing`), `digest` (sha256 of what was read), `figures` (integer cents and counts only), and `command`; then `record` (the folded state of the store below), `meetings` (the days on the calendar after the month's end), and `roster` (directors and officers by name and office, from `people`). It reads disk only.

## Proposal: the review record (not built)

A store `data/finance/monthly-reviews.json`, **append only**, in the shape of `jason.tasks.deficiencies` (rows with `acts[]`, the state folded from the acts, the latest word on each question winning; every act holds the store's lock via `jason.locks` and asks for `by`). A row's id is `review-2099-09` (the month under review, not a hash: there is one row a month). A correction is a later act that names the act it corrects; nothing is edited or deleted.

| Act | Carries | Rule |
|---|---|---|
| `opened` | `by`, `at`, month | once; the monthly assignment or a person opens it |
| `snapshot` | per part: `syncedAt`, `digest`, `figures` | taken when a reviewer first opens the month and again if a store changed. Fixes what was in front of the reviewer after a later sync overwrites the stores |
| `path` | `meeting`, `every-director`, or `subcommittee`; for a subcommittee the members named; `by` | the latest word wins; the roster comparison is shown as a fact, never as a verdict |
| `reviewed` | `by` (the reviewer, signed in), `on`, `parts[]` (the keys the reviewer says they read), `snapshotAt`, `note` | each reviewer signs their own. A reviewer who read only some parts says so. For a meeting, `on` is the meeting day and `minutes` points to it |
| `found` | `part`, `text`, `by`, `held` | a finding is a person's words. `held` marks one about an owner's account: executive session (CIV 4935), P3, counts only elsewhere |
| `answered` | the finding, `text`, `by`, optional board item id | a later word on a finding; closes nothing the board owns |
| `ratified` | `meeting` (day), `minutes` (`jason://min/DAY`), `minutesState` (`draft` or `adopted`), `by` (the secretary), `at` | the independent paths only. Records that the secretary entered it; the minutes' words are quoted from the stored minutes, never typed here |
| `correction` | `of` (act id), `text`, `by` | the original stays |
| `scheduled` | the `schedule.record_done` row id | a person records the occurrence done on the schedule from here; the review's id is the evidence |

Refusals, word for word: "Name who reviewed." / "Say which parts you read." / "Only the secretary records the ratification." (if the board decides it so, below).

## Layout

```
+------------------------------------------------------------------------------------------+
| Monthly review > 2099-09                          jason monthly-review --month 2099-09 [copy]|
| Reviewed by 2 (A. Treasurer, B. Director) · path: every director · ratification: not recorded |
+------------------------------------------------------------------------------------------+
| THE LAW   [Recitation] CIV 5500 (a) to (f), whole · CIV 5501, whole · caveat       [open] |
| [ReadingLabel: jason's reading, not the statute] ... (the four readings above)           |
+------------------------------------------------------------------------------------------+
| 1 WHAT TO LOOK AT                         read through the month's end, 2099-09-30        |
| Part                 Cite    Snapshot (age)        Figures                   Reviewed by |
| Operating reconcil.  5500(a) Oct 5 04:30 (6 d)     through Sep · 3 open items  A.T.   B.D. |
| Reserve reconcil.    5500(b) Oct 5 04:30 (6 d)     through Aug · 1 gap [STALE]  A.T.   -   |
| Actual vs budget     5500(c) Oct 5 04:15 (6 d)     net YTD -$12,040.00         A.T.   B.D. |
| Bank statements      5500(d) none filed for 2099-09 (Example Bank operating)     -     -   |
| Income and expense   5500(e) Oct 5 04:00 (6 d)     [open the statement]        A.T.   B.D. |
| Register, ledger, receivable 5500(f) 2099-10-05    past due $2,100.00 · 3 accts  A.T.  -   |
| Each row: [Open the tab it comes from] · command. Beside: transfers (5502) · invoice findings 4 |
+------------------------------------------------------------------------------------------+
| 2 PATH AND REVIEWERS                                                                     |
| (o) The board, at a meeting   ( ) Every director, independently   ( ) Treasurer + others  |
| Directors on the roster: A. Treasurer (treasurer) reviewed Oct 9 · B. Director reviewed   |
| Oct 10 · C. Secretary (secretary): no review recorded.    [Record my review]             |
+------------------------------------------------------------------------------------------+
| 3 FINDINGS                                                                               |
| Reconciliation, reserve: "Example Bank statement of Aug not filed" · A. Treasurer, Oct 9  |
|   answered Oct 10 by B. Director: "asked the manager to file it"          [Add a finding] |
| Held findings: 1 (executive session; shown to those who open the private view)           |
+------------------------------------------------------------------------------------------+
| 4 RATIFICATION (the independent paths only)                                              |
| Next meeting on the calendar after the review: 2099-10-20 · not yet held                  |
| Recorded by C. Secretary: ... · Minutes: jason://min/2099-10-20 (draft) [Doc chip]        |
| The minutes' words, quoted from the stored minutes: "..." [Quote, not a reading]          |
+------------------------------------------------------------------------------------------+
| 5 HISTORY  every act with who and when, corrections shown beside what they correct        |
| A review record is a person's act. jason assembled what to look at... (CAVEATS, verbatim) |
+------------------------------------------------------------------------------------------+
```

When the profile supplies a stricter standard (a `Community` method with an empty default, `stricter_review()`, to add), a band beside band 1 recites the governing document's words with a `Conflict` note if it asks less than the statute. Without one, the band is absent, not empty.

## Components

Built: `ScreenHeader`, `Tabs`, `DataTable`, `Card`, `Money` (every amount integer cents), `Stat`, `Pill`, `Findings`, `Recitation`, `ReadingLabel`, `Doc`, `DueDate`, `Clock`, `Evidence`, `Checklist`, `Confirm`, `ConfirmList`, `ChangedBanner`, `HeldNote`, `PrivateSwitch`, `Caveats`, `Command`, `RemoteView`. To add: `Freshness` (a store's stamp and its stale-after, [components.md](../components.md)), `ReviewMatrix` (parts down, reviewers across, a tick each, never a "done" row), `PathChoice`. The matrix ticks are facts a person signed, never computed.

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Record my review | `reviewed` act under `Confirm` ("Record that I, A. Treasurer, reviewed these parts on 2099-10-09"), one tick per part, the snapshot taken | No: a signed record | `jason monthly-review --month M --review --parts a,b,c --by NAME` |
| Choose the path | `path` act | No | `--path meeting\|every-director\|subcommittee [--members NAMES]` |
| Add a finding / answer one | `found`, `answered`; "Held" marks it executive session | No | `--finding PART --text ... [--held]` |
| Put a finding on the board's agenda | proposes a board item (`board_items.propose`), as the deficiency register does | No: the board decides | `jason board --set` |
| Record the ratification | `ratified` act, secretary | No | `--ratify --meeting DAY --by NAME` |
| Correct an act | `correction` | No | `--correct ID --text ...` |
| Record done on the schedule | `schedule.record_done` with the review id as evidence | No | `jason schedule --done KEY ...` |
| Sync a store | shown as a command; reads PayHOA | No | `jason budget`, `jason reconcile --fetch`, `jason books --sync`, `jason ledger --fetch` |

No control sends a letter, pays, files, or posts. jason computes no legal conclusion: no row says "complies", "met", or "invalid".

## States

- **Loading:** "Reading the stores." with the six rows drawn.
- **A store missing:** the row is unavailable with its command ("No reconciliations on disk. Run `jason reconcile --fetch`."); the others still show; a reviewer may sign a part only after the row has read.
- **Stale:** the row's first line: "Synced 11 days ago; stale after 9 (proposed policy)".
- **Changed since reviewed:** `ChangedBanner`: "The budget differs from the one A. Treasurer reviewed (read Oct 5, now Oct 12)." Nothing is voided; a person reviews again.
- **No review recorded:** "No review is recorded for 2099-09." Never "overdue" in the law's voice; the schedule's own standing shows beside it.
- **Independent path, a director with no review:** "C. Secretary has no review recorded." A fact beside the statute's words, not a finding that the path failed.
- **No meeting after the review:** "No later meeting is on the calendar. Add one to the schedule." After a meeting passes with no ratification: "The meeting of 2099-10-20 has passed. No ratification is recorded." and a board item may be proposed; whether the review still counts is for counsel.
- **Minutes still a draft:** `minutesState` draft, labeled so; adopted when the minutes record is adopted.
- **Held finding / outside the private view:** counts only ("1 held finding").
- **Not on the shelf:** "recited from the shelf at build time: not on the shelf".

## Privacy

- The record is P1: names of directors and officers, dates, parts, and figures in integer cents. Account numbers by their last four digits only (`··0001`); never a full number.
- Delinquency is an executive-session subject (CIV 4935). Band `registers` shows totals and counts from `books_report("receivables")` (no names). Unit rows (`collections`) open only to an office that opens them, as `#/liens` does; the unit and owner never enter the record. A held finding is P3.
- Directors and officers read the same bands. Known gap: `access.SEE_RULES` gives the treasurer P2 and no private view, while the director and secretary open P3 in the private view; it is inconsistent with the 2026-10-11 decision (below). The `collections` loader has no server-side office check ([money.md](../../workflows/money.md) section 8).
- The roster of reviewers is by office and name; the record shows who reviewed, never what a member owes.

## Acceptance criteria

1. Opening a month reads only stored snapshots; no PayHOA, Google, or Keeper call.
2. CIV 5500 and 5501 render whole in `Recitation` before any `ReadingLabel`; each reading is labeled; no word of the statute is typed in the component.
3. The six parts cite (a) to (f) and each shows its store, snapshot age, and stale-after; a missing store shows its command and does not hide the others.
4. No part is marked reviewed without a signed-in name; a reviewer ticks only the parts they say they read.
5. The path control offers three paths; the independent paths show the ratification band, and the meeting path does not.
6. The ratification is recordable only by the office the board names (secretary proposed), and shows the minutes link and `minutesState`; the minutes' words come from the stored minutes.
7. No text computes compliance. A past meeting with no ratification says only what is recorded.
8. Every act is appended with who and when; a correction leaves the original visible.
9. With the private view off, no unit, owner, or held finding text appears in the HTML.
10. Every amount is integer cents through `Money`; fake data only (`A. Treasurer`, `Example Bank`, 2099 dates).

## Decisions for the user

1. **The ratification actor.** The secretary only (recommended: the board's official record keeper), or any officer? And is a ratification recorded from the draft minutes, with `minutesState` updating when adopted, or only once adopted?
2. **A director who cannot sign in.** Each director records their own review (recommended: it is a person's act), or the secretary may record one "reported by" with the label? Neither is a legal conclusion.
3. **Keep figures or digests in the snapshot.** Digest plus headline cents and counts (recommended, so a later sync does not erase what the reviewer saw), or digest only?
4. **Receivables band.** Totals and counts only on this screen (recommended), with unit rows left to `#/liens`, or by unit here for the offices that open them?
5. **Access consistency.** Bring the treasurer's `SEE_RULES` row in line with the director's and secretary's (private-view P3), per the 2026-10-11 decision, before held findings ship?
6. **Does the profile supply a stricter standard** (`stricter_review()`)? Add the empty-default method now, or leave the band out until a profile needs it?
7. **The record's month.** One row per calendar month under review (proposed), or per review sitting (a month may have two)?
8. **Embedding (settled 2026-10-11).** The run page embeds this screen's reads and links its writes ([work.md](work.md), "Where a step's work happens"): the review matrix shows read only in the step panel, and the review, the path, and the ratification are recorded here, or by the secretary in Decisions.
9. **Bank statements.** Build a statement-to-month check (not built; the library holds the files), or leave 5500(d) as "none filed" and a person's tick?
