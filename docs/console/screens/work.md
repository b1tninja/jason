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
| Hearing H-7                   Step 6: The member's reply                   by Nov 2      |
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

### Item sets, step groups, and a remedy (built)

Engine round three ([../../workflows-engine.md](../../workflows-engine.md)) gave a run item sets, step groups, and a remedy. The run page shows all three in plain words; none of it is a colour alone.

- **Step groups.** A group the definition titles (`Workflow.groups`) is a collapsible section in the rail with its title, its roll-up state as a word, and "N of M done". It is open where the fold says `expanded` (it holds the run's current step or a failed one, and the run is not finished) or where the picked step stands, and shut when it is done or not yet reached. Its toggle is a real button (`aria-expanded`; Enter and Space); a person's own click on it wins until they leave the page. A run with no declared groups draws the rail as it was. A step that counts its items shows "N of M items done" in the rail.
- **Items.** A step that repeats over a set shows an **Items** table in its panel: one row for each item (its opaque id as the row header, its state word and glyph, its own clock with its basis word, and its date with "late by 3 days", "due today", "due in 5 days", or "met"), under a roll-up line such as "3 of 12 done, 2 late" (failed and skipped items are counted in words too). A late row is marked by its words and a glyph; the row's tint only repeats them. The table scrolls sideways on a phone inside a focusable region, and folds after fifty rows ("Show all 60 items"). A set with no items says "No items have been supplied to the set requests yet. This step waits until some are." The Clocks band draws a step's per-item clocks as one card (how many, how many late, the nearest date, the basis), not one card each.
- **Supply items.** Where the viewer may (the run is a draft or going, and they opened it or hold a role a step over the set needs: the engine's own rule, `acts.supplyItems`), the panel of a step over the set has a form: the ids one to a line and an optional record. **Check the list** asks the server to make every check a real supply makes and writes nothing (the dry run), and shows the server's sentence when it refuses (an id is an opaque handle: letters, digits, and `: _ . # / -`, 64 at most, never a name or an address). Only a list that passed offers a `Confirm`, which says the count and the name it is recorded under; the act is one `note` on the run's history that holds a count and never an id. Editing the list asks the server again. Where the viewer may not, the server's sentence stands in place of the form.
- **A remedy.** The step that remedies a failed check says "This step is the remedy for the failed check above; the check stays recorded as failed." with a button to go to the check; the check says it stays recorded as failed and names the remedy step. While the remedy is open the run's current step is the remedy (the list's current step follows the fold), and the failed check is not the run's current step.
- **Held runs.** Outside the private view a held run shows a count of its items ("12 items; their ids show only in the private view") and no id, no table, no clock, and no form; supplying items to it is the 404 a missing run gets, a dry run too. Inside the private view the table and the form show, and the opening and the act are lines in `access/served.jsonl` that name the run, never an item.
- **Loader.** `work-run` adds `groups` (only when the definition has some), `run.itemSets` (the sets some step repeats over: name, label, count, step titles), `run.acts.supplyItems` (`offered`, `why`, `sets`), and on a step `perItem`, `itemAware`, `itemSet`, `itemCounts`, `remedy`, `remedyOf`; a per-item clock carries `item`. A held page has `run.itemTotal`, a count. The writer takes `{act: "supply-items", set?, items, record?, dryRun?}` (`items` a list of ids or `{id, dates}`, or text with an id to a line).

## Layout: the definitions catalog and the Start-a-run picker

`#/work/definitions` (a tab of Work, "What can be run"). A **read-only** catalog of the workflows jason has, so a person can find one to start and the board can read how a task is done.

```
+------------------------------------------------------------------------------------------+
| Work > What can be run                                              [Start a run]        |
| 41 workflows in 6 families · 2 have drifted from their procedure                         |
+------------------------------------------------------------------------------------------+
| Family: [All v]   Search: [______]   Needs: [my office v]                                |
+------------------------------------------------------------------------------------------+
| THE MEMBERS                                                                              |
| Owner information cycle   25 steps · yearly · starts with a campaign        [Start] [Read]|
|   Built from the procedure owner-info-cycle (20 steps). In step with it.                 |
| Respond to a request      14 steps · per request                            [Start] [Read]|
|   Built from the procedure respond. DRIFTED: the procedure now has 15 steps.             |
| THE MONEY                                                                                |
| ...                                                                                      |
+------------------------------------------------------------------------------------------+
```

- **A row** is a definition: its title, its family, its step count, how often it runs (once, yearly, per item), its subject kind, and the procedure it was built from. **Drift** is the engine's check (`definitions` finds a step address the procedure no longer has) shown as a word, "DRIFTED", with the sentence; the catalog never fixes it.
- **Read** opens the definition as a page: every step, its kind, its role, its clock and basis, what it needs and what it produces, and the sentence it shows a person. It reads like the family page's definition table, from the same rows, so the board can see how a task is done before it is started. A step that cites a statute recites it (`Recitation`).
- **Start** opens `StartRun` (the Start-a-run form above) with the definition chosen. A definition the viewer's office cannot start shows the role that can ("Started by the manager or the secretary") and no Start button.
- **Filters:** family, a word in the title or a step, and "my office" (the definitions that have a step for it).
- **Empty:** "No workflows are registered." **Drift:** the heading counts it and each row says it.
- **Loader:** `GET /api/work-definitions` (above). Privacy: P0; a definition holds no owner's data. An administrator's definition is listed to an administrator only.
- Definitions are jason's procedures, the lowest authority: a step that conflicts with the law or a rule is corrected in the definition and the lesson recorded. The catalog shows the definition's `lessons`, and gives no control to edit it.

## Components

Built: `StageSteps`, `Findings`, `Command`, `Confirm`, `Doc`, `DueDate`, `Freshness`, `Caveats`, `Recitation`, `ReadingLabel`, `PlanReview`, `Pill`, `Glyph`. Specified, not yet built ([../handoff-admin-components.md](../handoff-admin-components.md)): `TerminalStep`, `AgeStamp`. Built since: `ItemTable`, `SupplyItems`, and `RemedyNote` (`RunItems`), and the titled groups in `WorkflowRail`. To add: `DefinitionRow`, `DefinitionPage`, `WorkflowRail`, `RunStepPanel` (the name `StepPanel` is `DriveChooser`'s), `ClockStrip`, `BasisPill` (a `Pill` preset for the five basis words), `RunRow`, `StartRun`, and `ChangedSince`.

## Where a step's work happens

One rule settles it for every family: **the run page embeds reads and links writes.** The run never repeats a write that another screen owns, and never holds a second copy of a screen's data.

| The step needs | On the run page | Where the act happens |
|---|---|---|
| To look at something a screen already shows (a campaign funnel, the follow-ups band, an arrivals lane, a notice's six bands, a mailing's cost line, a register table) | The same component, fed by the same loader, **read only**, in the step panel's "Look at" area, cut to what the step needs (a filter, a count, the five nearest rows) | None here; a "Open in NAME" link goes to the owning screen already filtered |
| A `person` step's act with no record of its own (read the forms, check the link as an owner, post the notice) | The instruction, the evidence, and the "Mark done" `Confirm` | **In place**: the attestation is the run's own write, recorded by name with its record |
| A write another screen owns (record a decision, confirm a reading, record a posting in the ledger, confirm a deficiency) | A summary of its current state, read from that store, and a link | **On the owning screen.** When the store changes, the run's next open appends `applied` or the matching event, and the step reads done. "Mark done" is not offered for it |
| A register or tracker that **is** the step's whole job and has its own store (collect items, a deficiency's acts) | The same component, **with its writes**, drawn in the step panel; one store, one component, one `Confirm` per act recorded by name | **In the component, in place.** The run appends the matching `attested` event when the store changes (the next open does it if the request cannot), so the two never disagree |
| A `plan` step | The approval's status and its item counts, from the approvals store | `#/approvals`: decided and applied there, never in the run |
| A `decision` step | The motion and the decision record, once recorded | `#/decisions` (the secretary records it) |
| A `job` step | The job's state and result, the command with Copy | A terminal, or the job queue |

**Both ways.** A step links out to the owning screen at the right filter. An owning screen shows a one-line banner, "Part of run NAME, step N: TITLE", linking back, when its subject belongs to an open run. The banner is read from the run store and appears only to a viewer who may see the run.

**Why this rule.** The approvals engine, the decisions store, the notice ledger, and each register already enforce their own two-person rules, fingerprints, and logs. Embedding their writes in a run would duplicate that enforcement or bypass it. Reading them in place keeps the run honest: its state is read from the stores, not remembered.

## Actions

- **Mark a step done** (`attest`): only a `person` step, only by the role it names, with the evidence it asks for. A `Confirm` says what is being attested and the name it is recorded under. A step that needs a record (an invoice, a minute, a posting) refuses without it, with the sentence the definition gives.
- **Skip**: only where the definition allows, by the role it names, with a reason. A legal step has no skip: it is done, or its absence is recorded as a finding for the board.
- **Pause, resume, reopen, note, cancel**: small dialogs, each a `Confirm` recorded by name, each requiring a reason except a note.
- **Supply items** (`supply-items`): more items for an item set while the run goes, by the person who opened the run or one who holds a role a step over the set needs, checked first with a dry run, then recorded behind a `Confirm` as a note that holds a count. At a terminal: `jason workflow --supply RUN --set NAME --item ID ... --by NAME` (add `--yes` to record).
- **Start a run** (`StartRun`): a definition, its subject (with its label), the cycle's dates (checked against the definition's rule: for example, leave room for one correction before an answer-by date), and who is the manager for this run. It creates a run in `draft`; opening it starts the clocks.
- **Print the history**: a `Doc` of the run's events with their evidence addresses, for the board's record.
- A `plan` step's decision, a `job` step's run, and a `decision` step's record happen on their own screens (`#/approvals`, the job queue, `#/decisions`); the run reads the result. An administrator viewing as someone else cannot act: "Viewing as NAME (admin view): go back to yourself first."

## States

- **No open runs:** "No runs are open. Start one from [Start a run]."
- **Loading:** a skeleton and "reading the runs on disk".
- **A run whose store cannot be read:** the step shows "could not read the store" with the loader's reason; the run is not marked failed.
- **A run held:** a run of a held definition (a hearing, a delinquent account, a records request: CIV 4935(e)) appears outside the private view by the definition's general words ("A member's hearing"), its state, its group, and its date with the basis word; the row says "Open the private view to see this run." and the run page shows only that, with no steps, links, evidence, or history. Inside the private view the whole run shows, and each opening is logged (`access/served.jsonl`), as the board items are.
- **Paused:** a banner with the reason, who, and when; no clock is hidden.
- **Failed:** the failing step's message and the person who may resolve it; nothing is retried by a click.
- **Changed since:** a banner above the rail; the affected step reads "changed since" with the difference.

## Privacy

- Directors and officers have the same access to information. A step reads and shows at the level of what it touches (P0 to P3, `jason.web.access`); a viewer who may see P2 sees the names and units a step touches, and the private view (P3) opens an owner's answer for the offices that open it, each opening logged.
- A run's list and a URL carry an id or a filter, never a name, an email, or an address. A run's id is random (a salt `api.start` gives and keeps nowhere), so it cannot be recovered by trying the association's units or parcels.
- **Held runs** (`Visibility.HELD`; `jason.web.extra.work_scope`). Outside the private view a held run is its `held_title`, its state, its group, whose move it is by office, the date and its basis word (no clock label, no citation), and its id as an opaque handle. The text filter matches only the general title. The run page is `held_page`: the run's shape with nothing in it. An act on a held run is the 404 a missing run gets; starting one is a 403, a dry run too. In the private view (open, for an office that opens P3 in it) the run shows whole and each list, page, act, and start that shows it is a line in `access/served.jsonl`, under the run id; a log that cannot be written serves nothing. Directors and officers have the same access; `SEE_RULES` is unchanged. A step's title shows on a held run outside the private view only where its definition sets `public_title`.
- **Administrator runs** (`Visibility.ADMIN`: `integration-connect`, `service-run`, `check-in`). Only an administrator sees the definition in the catalog or its runs in the list, its counts, or the office views; for anyone else a read is the 404 a missing run gets and a start is the refusal an unknown definition gets. An administrator who holds no office reaches the three loaders for these alone. `check-in` is a terminal procedure (`console_start` false): the catalog lists it with the sentence and the console never starts it.
- The catalog (`work-definitions`) otherwise shows a held definition and its steps to every office that opens P2 (it is jason's procedure, not a run); its `startable` is false outside the private view, with `startableWhy`.
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
12. The catalog lists every registered definition once, with its family, step count, and procedure; a definition whose procedure lost a step is marked DRIFTED with the sentence, and the heading counts them.
13. "Start" is offered only for a definition the viewer's office may start; otherwise the row names the role that can.
14. The catalog has no control that edits a definition.
15. A step over an item set lists every item with its state and its own clock in words, and a roll-up line counts the done and the late; a late item is never marked by colour alone.
16. A titled step group is a collapsible section, open where it holds the current or a failed step; a person can open and shut it from the keyboard.
17. Items are supplied only after a dry run passes, in the signed-in name, as one note that holds a count; a name or an address in an id is refused in the engine's words, with or without the dry run.
18. A held run outside the private view shows a count of its items and no id; supplying to it is a 404.
19. The step that remedies a failed check says the check stays recorded as failed.
