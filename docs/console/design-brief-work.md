# Design brief: Work (the runs list, the run page, and starting a run)

One page of orientation for the design agent, for the durable-workflow screens specified in [screens/work.md](screens/work.md). It does not repeat the spec; it says what to read in what order, each screen and component to draw, what can be drawn today, and a made-up community to draw against. The model behind the screens is [../workflows-design.md](../workflows-design.md); the engine is [../workflows-engine.md](../workflows-engine.md). **None of the engine is built**, so every screen below is drawn from the sample in section H.

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, bank, or private fact; made-up samples only ("123 Main St", "Example County", "Example Alarm").

## A. The idea, and the rules that run through it

**The idea, in six sentences.**

1. A task that takes days or months (a yearly owner request, a bill's attachment, a hearing, an inspection) is a **run**: steps in an order, with dates, that a person can leave and come back to.
2. The Work list answers one question: **whose move is it, and what is due?** A run shows once, in the group of its most pressing open step.
3. The run page answers: **where are we, what is next, who does it, why, and what is the evidence?** The step rail is the page; the rest reads from it.
4. A step is one of seven kinds. The page draws what each kind needs a person to do, and never offers a control a kind must not have: a decision has no approve, vote, or adopt; a plan's decision is made in the approvals screen.
5. Every date says **whose** it is: the law's, the documents', a counterparty's, jason's proposal, or a person's. A proposed number is never drawn as a stamp.
6. The page reads; the person acts, in their name, behind a `Confirm`. jason sends, files, and mails nothing from here.

**The rules** (each is in the spec; a screen that breaks one is wrong):

- **Directors and officers have the same access to information.** There is no director-only or counts-only view. A step shows what a viewer's level allows (P0 to P3), and a list never carries an owner's contact details or an answer.
- **State is a word and a glyph, never colour alone.** The state word is the engine's own (`not started`, `ready`, `running`, `waiting`, `needs a person`, `done`, `skipped`, `blocked`, `failed`, `superseded`); the page never invents one.
- **A legal date is recited.** The statute's operative words come first (`Recitation`), jason's reading follows in a `ReadingLabel`, labeled as a reading. A run past a legal date says so in the law's words.
- **A step that needs a record refuses without it,** in the definition's sentence, not a generic error.
- **Changed since is shown first.** When a store moved under a done step, the banner is above the rail, and the step reads "changed since" with the difference; nothing done is silently repeated.
- **Skipping is a decision with a reason.** A legal step offers no skip.
- **The secretary records the board's decisions.** A decision step shows the motion, mover, second, each director's vote by name, recusals, and outcome, read from the decision record; it has no control to cast or change them.
- **An executive-session matter is held:** by its general words and state only, with no details outside the private view.

## B. Reading order

1. [screens/work.md](screens/work.md): the whole screen, top to bottom.
2. This page's section D (the components) beside section H (the sample).
3. [../workflows-design.md](../workflows-design.md) sections 3.1, 3.2, and 4 for the step kinds, the states, the events, and the clock bases.
4. One family page for flavour: [../workflows/members-cycles.md](../workflows/members-cycles.md) (the owner-information run, the most that is built) and [../workflows/board-governance.md](../workflows/board-governance.md) (decisions and meetings).
5. [handoff-admin-components.md](handoff-admin-components.md) for `Command` and `TerminalStep`; [approval-workflow.md](approval-workflow.md) for what a `plan` step links to.

## C. The screens

### C1. Work (`#/work`)

The list of open runs in four groups: **Yours**, **Waiting on others**, **Waiting on a clock**, **The board**. Each row: the run's label, the current step's title and position ("Step 9 of 25"), who it waits on, the due date with its basis pill, and its age. Heading counts: open runs, yours, due this week, past a legal date. Filters: definition, whose move, due soon. Draw the empty state, the loading state, and a group with fifteen rows (collapsed after five, with the count). A row's whole width is the link.

### C2. Run (`#/work/<definition>/<id>`)

Two columns on a wide screen: the **rail** (left) and the **step** (right). Above them: the title row (label, state, opened by and when; Pause, Note, Print the history, Cancel), and the **Changed since** banner when there is one. Below: the **clocks strip**, the **links**, and the **history**. The rail groups steps by phase, marks the current step, shows a step group under its own prefix, and shows a child run as one row that links to it. On a narrow screen the rail becomes a collapsed "Step 9 of 25: Read the returned forms" header that opens the list. Draw the step panel for each of the seven kinds (C3).

### C3. The step panel, by kind

| Kind | The panel shows | The person's control |
|---|---|---|
| `check` | the question, the result (passed or failed now), the evidence, when it ran | none; "Run again" is a read |
| `job` | the job's state and result, the command (Copy), when it ran | none; a person runs the command at a terminal, and the job's result arrives |
| `plan` | the approval's status and its items (counts), a link to `#/approvals` | "Review in Approvals"; the decision is made there |
| `person` | the instruction, why, the evidence to look at, the command, the record it needs | "Mark done" (`Confirm`), asks for the record |
| `decision` | the motion's words and the decision record | none; "Record in Decisions" for the secretary, a link |
| `wait` | what it waits for, the date and its basis, what arrived | "Note an arrival" where the definition allows a person's note |
| `branch` | the fact it reads and the path chosen, or the question for a person | "Answer" (`Confirm`) where the fact is a person's |

**Where the work happens** (spec: [screens/work.md](screens/work.md), "Where a step's work happens"): the panel embeds reads (the same components as the owning screens, read only) and links writes; only a `person` step's attestation is written in place. Draw an embedded funnel in a step's "Look at" area and the "Part of run NAME, step N" banner on an owning screen.

A step that is not the viewer's shows "Waiting on the treasurer" and no act. A step `blocked` names the step or fact it waits on. A step `failed` shows the message and who may resolve it; nothing retries by a click.

### C4. Start a run

A form: the definition (by family), its subject (with a label), the cycle's dates, who is the manager for this run. Each date is **checked** against the definition's rule ("leave room for one correction before the answer-by date"), with the sentence shown beside the field. Creating it makes a `draft`; opening it starts the clocks. Draw a date that fails its check and one that passes.

### C5. The small acts

Skip, pause, resume, reopen, note, and cancel are dialogs. Each is a `Confirm` that says what will be recorded and under what name. Each asks for a reason except a note. "Viewing as NAME (admin view): go back to yourself first" replaces the control for an administrator acting as someone else. Cancel names every open step and every child run it will leave.

### C6. Print the history

A `Doc` of the run's events with their evidence addresses, for the board's record; draw the print layout (a letterhead-free page, the label, the events newest last).

### C7. What can be run (the catalog) and Your work on Today

- **The catalog** (`#/work/definitions`): a read-only list of the workflows by family, each with its step count, its cadence, the procedure it came from, a DRIFTED word when the procedure lost a step, and [Start] / [Read]. [Read] opens a definition as a page that reads like a table of steps, kinds, roles, and clocks. Draw a family with eight rows, a drifted row, and a row the viewer's office cannot start (the role that can is named, no button). Spec: [screens/work.md](screens/work.md), "The definitions catalog".
- **Your work on Today** (`#/digest`): a band of the five nearest runs that are the viewer's move, each with its current step and its due date and basis pill, and "All your runs (14 open)". Spec: [screens/today.md](screens/today.md).

## D. The shared components, each once

Reuse (built): `StageSteps`, `Findings`, `Command`, `Confirm`, `Doc`, `DueDate`, `Freshness`, `Caveats`, `Recitation`, `ReadingLabel`, `PlanReview`, `Pill`, `Glyph`, `DataTable`, `Tabs`, `Card`. Specified, not built (draw them from the built parts and say so): `TerminalStep`, `AgeStamp`.

| Component | What it is | Data | States |
|---|---|---|---|
| `RunRow` | One row of the list | `id, definition, label, state, current{id,title,n,of}, waitingOn, due{date,basis}, age` | yours; waiting on someone (named); waiting on a clock; the board's; past a legal date; paused; failed |
| `WorkflowRail` | The step rail | `steps[]{id,title,kind,state,role,phase,group,child}` | every step state; the current step marked; a child-run row; a group under its prefix |
| `RunStepPanel` | The step (name: `StepPanel` is `DriveChooser`'s) | `step{...}, evidence[], links[], command, needs{record}` | the seven kinds (C3); each state; changed since |
| `ClockStrip` | The deadlines | `clocks[]{label,date,basis,law{words,source},past}` | upcoming; due today; past; a legal clock recited |
| `BasisPill` | A `Pill` preset | one of `law`, `documents`, `counterparty`, `proposed policy`, `person` | five words, each with a glyph; unknown word shown plainly |
| `ChangedSince` | The banner | `changed[]{step,was,now,at}` | one; several; none (absent) |
| `RunLinks` | What the run made | `links[]{kind,id,state,label}` | an approval, a job, a follow-up, a board item, a dock task, a document, a campaign, a child run |
| `RunHistory` | The event log | `events[]{n,kind,step,by,at,detail}` | newest first; a correction as a later entry; a torn-log warning |
| `DefinitionRow`, `DefinitionPage` | The catalog row and the definition read as a page | `key, title, family, steps[], cadence, procedure, drift{ok, why}, startedBy` | in step; drifted; not startable by the viewer |
| `StartRun` | The form of C4 | `definition{dates[]{name,rule}}` | valid; a date that fails its check; refused (the sentence) |

**Fixed words** (use exactly): "Yours", "Waiting on others", "Waiting on a clock", "The board", "needs a person", "changed since", "a legal date", "proposed, not the law's", "Waiting on the NAME/OFFICE", "Record in Decisions", "Review in Approvals", "Viewing as NAME (admin view): go back to yourself first".

## E. Glyphs

Use the glyphs the console already has. A new one only for what none can say: a *state* glyph set for the ten step states (not started: an empty circle; ready: a filled circle; running: a spinner that stops under reduced motion; waiting: a clock; needs a person: a person; done: a check; skipped: a slashed circle; blocked: a lock; failed: an alert triangle; superseded: a struck line), and one for each basis word. Name each for the idea.

## F. Decisions that are the design's, in one list

1. **Rail left or timeline top** on a wide screen. The rail is recommended: long runs (25 to 45 steps) need the whole list in view.
2. **How a long rail folds:** the done phases collapsed to one line each (recommended), with the current phase open.
3. **Where the clocks strip sits:** under the rail and step (recommended) or pinned at the top when any clock is legal.
4. **How the Work list groups on a narrow screen:** one list with group headings (recommended) versus tabs.
5. **How a child run shows:** one row in the rail that links to the child, plus its state in the links band.
6. **The Confirm's wording** for each act, and whether a record that points to a document shows a `Doc` preview in the dialog.
7. **Print layout** of the history.

These are not the design's: who may skip a step, whether the board approves a definition, and how long a done run stays on the list (the spine's section 7).

## G. What can be designed now, and what waits

| Part | Now | Waits on |
|---|---|---|
| Work list, run page, rail, step panel (all seven kinds), clocks, links, history | Yes, from section H | The engine (`jason.workflows`) and the loaders for real data |
| Start a run, the small acts, print | Yes | The writer `POST /api/write/work/...` |
| A `plan` step's panel | Yes; it links to the built approvals screen | — |
| A `decision` step's panel | Yes; it reads the built decisions record | — |
| Family-specific surfaces (a campaign funnel, a meeting packet, a ledger) | Their own built screens, linked | The family pages' own screen gaps |

## H. A made-up community to design against

"Oakview" has these open runs (dates are plainly made up; the loaders will send ISO dates).

| Run | Definition | Current step | Group | Due and basis | The point it makes |
|---|---|---|---|---|---|
| Owner information 2099 | `owner-info-cycle` | 9 of 25, read the returned forms (manager) | Yours | Oct 23, `documents` | The long run; a child notice-delivery run done and a Mailroom run waiting |
| Bill attach: Example Electric, Oct | `bill-attach` | 4 of 7, approve the attachments (treasurer) | Yours | Oct 14, `person` | A `plan` step |
| Hearing H-7 | `hearing` | 6, the member's reply | Waiting on others | Nov 2, `documents` | A wait on an owner; no name beyond the address |
| Annual backflow test | `backflow-annual` | 3, the vendor's report | Waiting on a clock | Dec 1, `counterparty` | A date the vendor stated |
| Rule change: quiet hours | `rule-change` | 13, the board decides | The board | Nov 14, `law` | A `decision` step; the secretary records |
| Election 2099 | `election` | 4, appoint the inspector | The board | Oct 2, `law`, **past** | A run past a legal date |
| Annual inspection: fire alarm | `life-safety-period` | 5, a deficiency run is open | Waiting on others | Nov 30, `documents` | A parent waiting on a child run |

Run states to draw: `draft` (being set up; no clock runs), `active`, `paused` (with a reason), `waiting`, `done`, `cancelled` (with a reason), `failed`.

Step panels to draw for the owner-information run: step 3 (`decision`, done), step 5 (`plan`, applied), step 9 (`person`, needs a person, four forms arrived since Oct 7), step 11 (`wait`, answers by Oct 23), and step 5 with a **changed since** banner ("the kept form now has 2 more questions than when it was done").

A clocks strip to draw: answers by Oct 23 (`documents`), in PayHOA by Nov 1 (`documents`), resend by a legal date (`law`, with a recitation block: the statute's words with a placeholder citation and a labeled reading).
