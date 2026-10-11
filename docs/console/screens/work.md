# Work

A new group, **Work**, with two screens: `#/work` (the runs that are open) and `#/work/<definition>/<id>` (one run) · phase 2, after the run store · CLI: `jason workflow` (to add) · model: [../../workflows-design.md](../../workflows-design.md), families: [../../workflows/README.md](../../workflows/README.md)

The design brief for the design agent is [../design-brief-work.md](../design-brief-work.md).

## In the console

None. The nearest are Today and the dock (a person's own tasks and deadlines), `#/approvals` (one kind of step: a plan awaiting a decision), `#/actions` (the board's items), and `#/followups` (dated actions). None follows a task from its start to its end across those parts. A run reads them and shows the result in one line of sight.

**This spec is the whole screen, as proposed.** The loaders to add are `work` (the open runs) and `work-run` (`?definition=&id=`: one run), over the run store `jason.workflows` (not built; [../../workflows-design.md](../../workflows-design.md) section 6, step 1). It reads, and writes only the small acts below, in the signed-in person's name. It never sends, files, or mails anything: a step that does is a plan a person approves in `#/approvals`, or a command a person runs.

## Purpose and personas

A task that takes days or months (an owner-information cycle, a bill's attachment, a hearing, an annual inspection) is a run of steps with dates. The person who opens the console should see whose move it is, what is due, and why, and should be able to leave and come back without losing the place.

- **Manager:** most of the runs; the steps of every family that are done at a terminal or in PayHOA.
- **Secretary:** the board's record keeper; records the board's decisions, postings, and minutes; follows meeting and notice runs.
- **Treasurer:** the money family's reviews and ratifications.
- **President, vice president, director:** the board's steps; a director reads what an officer reads at the same level (directors and officers have the same access to information; they differ in duties).
- **Administrator:** starts and repairs runs; never decides on the board's or a person's behalf.
- **Counsel:** reads a run's evidence on grant. No step.
- **Owner:** never sees this screen.

## Data

| Part | Source | Loader |
|---|---|---|
| The open runs | `jason.workflows.runs(data_dir, state=open)`: `id`, `definition`, `label`, `subject`, `state`, `current` (step id and title), `owner`, `due` (date, basis), `age`, `waitingOn` | `GET /api/work` (`?definition=&role=&due=&state=`) |
| One run | `jason.workflows.show(data_dir, definition, id)`: the run, its `steps[]` (state, role, evidence, links), `clocks[]`, `links[]`, `events[]` | `GET /api/work-run?definition=&id=` |
| Definitions | `jason.workflows.definitions()`: key, title, family, subject kind, dates asked | `GET /api/work-definitions` |
| The small acts | `attest`, `skip`, `pause`, `resume`, `reopen`, `note`, `cancel`, `start`; a `plan` step's approval and a `job` step's job are read from the approvals engine and the job queue | `POST /api/write/work/<definition>/<id>` with `{act, step?, reason?, ...}` (signer's name enforced; a `by` in the body naming someone else is a 403) |
| The linked records | each link's current state, read from its own store: an approval, a job, a follow-up, a board item, a dock task, a document, a campaign | the same loaders as those screens |

A run's list never carries an owner's contact details or an answer. A link is an id; the page reads the current state behind it, never a copy.

## Layout: the list

```
+------------------------------------------------------------------------------------------+
| Work                                                           [Start a run]             |
| 14 open runs · 3 are yours · 2 are due this week · 1 is past a legal date                |
+------------------------------------------------------------------------------------------+
| Filter: [All definitions v] [Whose move v] [Due soon]                                    |
+------------------------------------------------------------------------------------------+
| YOURS                                                                                    |
| Owner information 2099        Step 9 of 25: Read the returned forms       due Oct 23     |
|   run 2099-10                  [your move: manager]                       [LEGAL] CIV... |
| Bill attach: A. Utility, Oct  Step 4 of 7: Approve the attachments       due Oct 14     |
|                                [your move: treasurer]                     [PERSON]       |
| WAITING ON OTHERS                                                                        |
| Hearing: 123 Main St          Step 6: The member's reply                   by Nov 2      |
|                                [waiting on: the member]                   [DOCUMENTS]    |
| WAITING ON A CLOCK                                                                       |
| Annual backflow test          Step 3: The vendor's report                  Dec 1         |
|                                [waiting: counterparty]                    [COUNTERPARTY] |
| THE BOARD                                                                                |
| Rule change: quiet hours      Step 13: The board decides                   Nov 14        |
|                                [the board; the secretary records]         [LEGAL]        |
+------------------------------------------------------------------------------------------+
```

- Groups: **Yours** (the signed-in person's office holds the current step), **Waiting on others** (a named other office, the owner, a vendor, an authority), **Waiting on a clock** (a `wait` step with a date), **The board** (a `decision` step). A run appears once, in the group of its most pressing open step.
- Within a group: the nearest due date first, a legal date before any other, a run with no date last.
- Each row is a link to the run. The due date is `DueDate` with its **basis word** beside it (`LEGAL`, `DOCUMENTS`, `COUNTERPARTY`, `PROPOSED`, `PERSON`); a proposed number is never shown as a stamp.
- The heading counts are the loader's; "past a legal date" is the law's own date, recited on the run page, not computed here.

## Layout: one run

Six bands. The rail and the step panel are the page; the others read from them.

```
+------------------------------------------------------------------------------------------+
| Work > Owner information 2099                      Opened Oct 1 by the manager · active  |
| Pause · Note · Print the history · Cancel                                                |
+------------------------------------------------------------------------------------------+
| CHANGED SINCE (only when a store moved under a done step)                                |
| Step 5 was done on Oct 3. The kept form now has 2 more questions than when it was done.  |
+------------------------------------------------------------------------------------------+
| THE RAIL                    | THE STEP                                                   |
| Prepare                     | 9  Read the returned forms                                 |
|  done    1 Check the data   | needs a person: the manager                                |
|  done    2 Draft the notice | Why: an owner's answer counts only once a person confirms  |
| Send                        |   the reading (jason's reading, not the owner's word).     |
|  done    5 Send             | Look at: 4 forms arrived since Oct 7 (the response inbox)  |
| Collect                     | Command  jason responses --list --state new   [Copy]       |
|  >>      9 Read the forms   | When the forms are read, say so:  [Mark done...]           |
|  ready  10 Apply the tags   | Skip is not offered: this step is required by the law.     |
|  waiting 11 Answers by      | Clock: answer-by Oct 23 (documents). Law: CIV 4041 below. |
| Close                       |                                                            |
|  not started 14 ...         |                                                            |
+------------------------------------------------------------------------------------------+
| CLOCKS                                                                                   |
| Answers by Oct 23 [DOCUMENTS]   In PayHOA by Nov 1 [DOCUMENTS]   Resend by ... [LEGAL]   |
| "In the words of CIV 4041(e): ..." (Recitation, with its source)                         |
+------------------------------------------------------------------------------------------+
| LINKS                                                                                    |
| Campaign OI-2099 (46 of 48 reached)  Approval 31 (applied)  Follow-ups: 2 owed          |
| Child run: Notice delivery (done)   Child run: Mailroom batch 1 (waiting)                |
+------------------------------------------------------------------------------------------+
| HISTORY                                                                                  |
| Oct 9 08:12  The manager attested step 9 "read". Oct 8 ... jason: check-ran ...          |
+------------------------------------------------------------------------------------------+
```

- **The rail** (`WorkflowRail`): every step, its state as a word and a glyph (never colour alone), grouped by the definition's phases, the current step marked. A step group (response intake) shows under its own prefix. A child run is one row linking to that run.
- **The step panel** (`RunStepPanel`): the step's title; its state and who it waits on; **why** (the definition's reason, with the lesson or the statute it cites); **look at** (the evidence, as `Doc` chips and counts, at the level the viewer may see); **the command** as a `Command` with Copy (the page never runs it) or a `TerminalStep`; **the act** as a `Confirm`. For a `plan` step the panel shows the plan's status and links to `#/approvals` for the decision; for a `decision` step it shows the motion, mover, second, vote, and outcome, read from the decision record, with no approve or vote control.
- **The clocks strip** (`ClockStrip`): each deadline on the run with its basis. A `law` clock recites the statute's operative words from the stored text (`Recitation`), then jason's reading in a `ReadingLabel`. A run past a legal clock says so in the law's words and links the follow-up it opened.
- **Links**: what the run made, each in its current state.
- **History**: the event log, newest first, with who and when. A correction is a later entry, never an edit.
- **Changed since**: the resume check's differences, shown before anything else on the page.

## Components

Built: `StageSteps`, `Findings`, `Command`, `TerminalStep`, `Confirm`, `Doc`, `DueDate`, `Freshness`, `Caveats`, `Recitation`, `ReadingLabel`, `PlanReview`, `Pill`, `Glyph`, `AgeStamp`. To add: `WorkflowRail`, `RunStepPanel` (the name `StepPanel` is `DriveChooser`'s), `ClockStrip`, `BasisPill` (a `Pill` preset for the five basis words), `RunRow`, `StartRun`, and `ChangedSince`.

## Actions

- **Mark a step done** (`attest`): only a `person` step, only by the role it names, with the evidence it asks for. A `Confirm` says what is being attested and the name it is recorded under. A step that needs a record (an invoice, a minute, a posting) refuses without it, with the sentence the definition gives.
- **Skip**: only where the definition allows, by the role it names, with a reason. A legal step has no skip: it is done, or its absence is recorded as a finding for the board.
- **Pause, resume, reopen, note, cancel**: small dialogs, each a `Confirm` recorded by name, each requiring a reason except a note.
- **Start a run** (`StartRun`): a definition, its subject (with its label), the cycle's dates (checked against the definition's rule: for example, leave room for one correction before an answer-by date), and who is the manager for this run. It creates a run in `draft`; opening it starts the clocks.
- **Print the history**: a `Doc` of the run's events with their evidence addresses, for the board's record.
- A `plan` step's decision, a `job` step's run, and a `decision` step's record happen on their own screens (`#/approvals`, the job queue, `#/decisions`); the run reads the result. An administrator viewing as someone else cannot act: "Viewing as NAME (admin view): go back to yourself first."

## States

- **No open runs:** "No runs are open. Start one from [Start a run]."
- **Loading:** a skeleton and "reading the runs on disk".
- **A run whose store cannot be read:** the step shows "could not read the store" with the loader's reason; the run is not marked failed.
- **A run held:** an executive-session matter (CIV 4935(e)) appears by its general words and its state only; the run page shows no details outside the private view, and each opening is logged (`access/served.jsonl`), as the board items are.
- **Paused:** a banner with the reason, who, and when; no clock is hidden.
- **Failed:** the failing step's message and the person who may resolve it; nothing is retried by a click.
- **Changed since:** a banner above the rail; the affected step reads "changed since" with the difference.

## Privacy

- Directors and officers have the same access to information. A step reads and shows at the level of what it touches (P0 to P3, `jason.web.access`); a viewer who may see P2 sees the names and units a step touches, and the private view (P3) opens an owner's answer for the offices that open it, each opening logged.
- A run's list and a URL carry an id or a filter, never a name, an email, or an address.
- The owner view never reads `work` or `work-run` (`OWNER_SOURCES` does not list them).
- Counsel reads a run's evidence on grant, not its list.

## Acceptance criteria

1. `GET /api/work` signed out is a 401; for a viewer whose offices do not open P1 it is refused with the sentence `access.may_see` gives; the owner view is refused.
2. Each open run appears once, in the group of its most pressing open step, ordered legal dates first.
3. Every deadline shows a basis word; a `law` clock renders its statute words in a `Recitation` before any `ReadingLabel`; no proposed number renders as a stamp.
4. A step the viewer's office does not hold shows "waiting on NAME/OFFICE" and no act.
5. A `person` step cannot be marked done without its required evidence; a legal step offers no skip.
6. A `decision` step offers no approve, vote, or adopt control; it shows the decision record once the secretary has recorded it.
7. A body `by` naming someone else is a 403; an admin viewing as someone else cannot act.
8. A `plan` step's status is the approval's; a `job` step's is the job's; neither is repeated on a second open of the run (idempotence).
9. A store that moved under a done step shows the `ChangedSince` banner and a `changed` event; nothing done is silently repeated.
10. A director reads the same run page an officer reads at the same level; the page shows no owner's contact details or answer in a list.
11. The page renders no `/api/file` link, no absolute path, and no frame of an outside host.
