# Today

Bands added to `#/digest` · phase 2 · CLI: `jason attention`

## In the console

The console's first screen is **Board digest** (`#/digest`, `ConsoleDigest`; "Overview" in the owner view). It renders `board_digest` (`GET /api/board-digest`) through `DigestView`. Beside it:
- the dock's **Deadlines** drawer gives what falls due, grouped, with a screen hint (`/api/dock?part=deadlines`);
- **Inbox** (`#/inbox`, `open_items`) gives what is waiting on the association across the stores;
- **Jobs** (`#/jobs`) gives the queue and who confirmed each write;
- the nav's **Approvals** count gives the letters waiting on an approver.

**What this spec adds** to `#/digest`, as bands above the board digest, board view only:

1. **Waiting on a person**: the letters awaiting approval and the engine approvals waiting on a decision, a submission, or a second signature.
2. **Needs attention**: the governance digest (`attention.digest`), one section per system, most urgent first. The board digest is the board's tools' summary; the governance digest is jason's clocks (meetings, requests, schedule, people, notices, living documents, conflicts, duties, intake).
3. **Next questions**, while an onboarding gate is closed or an open question carries a clock.
4. **Who holds a lock**, beside the link to `#/jobs`.

## Purpose and personas

One question: what needs a person now? The approvals waiting, the clocks running, and the questions whose answers unblock the most, in one place, most urgent first.

- **Manager:** the daily start. Opens approvals, follows each digest line to its screen, runs the syncs.
- **Director, Secretary, Treasurer:** the same digest, narrowed by role (once roles exist) to the sections they answer for.
- **Reviewer:** "Waiting on you as second person".

## Data

| Band | Source | Loader |
|---|---|---|
| Waiting on a person | Letters: `pending` and the `requested` group. Engine: `approvals` with `status` in planned, in review, approved, partially approved, and whether each needs a second signature | `GET /api/approvals` (existing) |
| Needs attention | `jason.api.governance_digest(limit=8, private=True)` → `attention.digest(...).as_dict()`: `totals` by urgency, `unavailable`, and `sections[]` (`key`, `title`, `command`, `available`, `error`, `summary`, `counts`, `notes`, `items[]` with `urgency`, `text`, `due`, `command`, `more`), and the `caveat` | `governance-digest` (to add; `?section=`) |
| Next questions | `jason.api.next_questions(limit=5)`: `questions[]` with `id`, `kind`, `question`, `priority`, `unblocks`, `highStakes` | `next-questions` (to add) |
| Lock holders | `jason.locks.holders()` | add to `/api/health` |

**Section order** is the digest's own (`Digest.ordered`): sections with something urgent first, quiet ones next, unavailable ones last. Within a section, `Item.key`: urgency, then a statute's clock before the documents' before a policy's, then the due day.

## Layout

```
+--------------------------------------------------------------------------------------------+
| Board digest                                                          Records as of Oct 3 |
| 1 on a legal clock · 3 overdue · 4 due soon · 6 waiting on a person · 2 noted              |
+--------------------------------------------------------------------------------------------+
| WAITING ON A PERSON                                                                        |
|  Owner information: PayHOA tags   plan · in review · 10 changes · 2 held for the board  > |
|  Notice of the Oct 7 meeting      letter · awaiting the secretary                        > |
+--------------------------------------------------------------------------------------------+
| NEEDS ATTENTION                                                                            |
| Meetings · jason schedule-evidence --watch [copy]                                          |
|  [LEGAL] Notice of the Oct 7 meeting: 4 days left (Civil Code 4920)                     > |
|  [due soon] Minutes of Sep 9 due Oct 9: none on record yet                              > |
| Requests · jason respond [copy]                                                            |
|  [OVERDUE] Request 1042, architectural: 6 days late                                     > |
| Intake · unavailable: no intake queue on disk. Run jason intake --scan.                    |
+--------------------------------------------------------------------------------------------+
| NEXT QUESTIONS                                                                             |
|  Which version of the declaration is in force?   unblocks: 2 clocks, 1 gate            >  |
+--------------------------------------------------------------------------------------------+
| (the board digest, as today)                                                               |
| Read from the stores on disk. jason decides nothing: a clock is computed... (the caveat)   |
+--------------------------------------------------------------------------------------------+
```

Under 720 px the bands stack full width and the totals line wraps.

## Components

`ScreenHeader` (the totals line as its summary), `Card` per band, `Pill` for the urgency words (LEGAL, OVERDUE, due soon, open, noted), `DueDate`, `Command`, `RemoteView` (a section unavailable shows its `error` and command), `QuestionCard` (compact), `Caveats` for the digest's caveat.

## Actions

| Control | Does | Approval? |
|---|---|---|
| A waiting row | Opens it in `#/approvals` | No |
| A digest line | Opens the screen that owns it; where none exists yet, shows the line's command to copy | No |
| Copy command | Copies the section's or line's `command` | No |
| A next question | Opens it in `#/onboarding` | No |

The bands have no write of their own. A sync is a command (`jason sync-catalog`, `jason notices KEY --sync`, `jason meetings --sync`), shown, never run.

## States

- **First run, nothing on disk:** every digest section is unavailable. One panel instead: "jason has no stores for this profile yet. Start with Onboarding." with a link.
- **A section unavailable:** it sits last, with "Unavailable:" and its error. The rest stands.
- **A section with nothing owed:** "Nothing needs attention." with its summary line.
- **Nothing waiting:** "Nothing is waiting on a person." The band stays, so its absence is never mistaken for a failure to load.

## Privacy

- The digest is read with `private=True`: units are left out of request lines, and people's task titles are replaced by their rule's label. A line never names an owner.
- Waiting rows show counts and kinds, never names.
- The owner view shows none of these bands.

## Acceptance criteria

1. With fixture stores, the digest's sections render in `Digest.ordered` order and lines in `Item.key` order, and the totals line matches `Digest.totals()` with the urgency words as labels.
2. A missing store renders its section as unavailable, last, with its error and command. No other section is affected.
3. No rendered line contains a fixture unit label or an owner's name.
4. Waiting on a person counts letters and plans apart, and the counts match `/api/approvals`.
5. The loaders make no call to PayHOA, Google, or Zoom: a test with those clients patched to raise passes.
6. The digest's caveat is shown verbatim.
