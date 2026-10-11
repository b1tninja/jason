# Durable workflows: the tasks jason is used for, as runs a person can leave and come back to

Status: **design**. Nothing in this page is built as one engine. Its pieces are: the standard operating procedures (`jason sop`, `jason.community.procedures`), the approvals engine (plan, decide, re-plan, apply: [console/approval-workflow.md](console/approval-workflow.md)), the follow-ups and campaigns, the job queue and the scheduler, the board's items and the dock's tasks, and the journeys the console was designed from ([console/journeys.md](console/journeys.md)). This page says how those become one thing: a **workflow**, defined once for any association and run many times, whose state is on disk and whose every step is somebody's, with a web interface for each family of tasks (the per-family pages in [workflows/](workflows/README.md), written 2026-10-11).

## 1. The idea, and why now

A procedure in `jason sop` is a checklist read at a terminal: eight to twenty steps, each a sentence, a command, a check, and a flag for "a person's step". It is the right content, and it has no memory. Nobody can ask it "where is the 2027 owner-information cycle?", "what is waiting on whom?", "what did we decide on the third of October, and on what evidence?", or "pick this up again on Monday". Those answers live in a person's head, the dock's tasks, the board's items, the approvals inbox, the follow-ups, and the job queue, each a part of the same work.

A **durable workflow** is a procedure with a memory:
- **A definition** (written once, general): the steps, who does each, what must be true before it, what it produces, and the clocks that run on it.
- **A run** (many, each for a subject and a cycle): the definition's steps with their states, an append-only event log of who did what and when, and links to what each step made (an approval, a job, a follow-up, a document, a board item).
- **A web interface** that shows a run as a place a person can enter at any step, see exactly what is theirs, do it, and leave.

*Durable* means three things, each a rule: **the state is on disk, not in a session** (a restart, a day away, or another person picking up changes nothing); **every step is safe to run twice** (a re-run finds what is done and does not repeat it: the re-plan rule the approvals engine already keeps); and **nothing happens that is not in the log** (who, when, on what evidence).

## 2. What a workflow is not

- **Not an automation that acts for the board.** jason proposes; a person decides and acts (AGENTS.md). A workflow runs the *checking, reading, drafting, planning, and waiting*; every write outside jason is a plan a person approves, and every decision the law or the documents leave to the board or its members is recorded as theirs. A workflow never advances past a board decision on its own and never marks a legal clock satisfied.
- **Not a place to invent rules.** A step's clock cites the law or the documents (recited, not paraphrased) or is a **proposed policy** and says so; where the law is silent the workflow holds a question for the board (the response policy's rule, AGENTS.md "Where the law is silent, write it down").
- **Not a second source of truth.** The run points at the stores that hold the facts (PayHOA, the library, the approvals, the ledgers); it records what a person said about them. A run that disagrees with a store is shown as a difference, never silently reconciled.
- **Not a scheduler.** The scheduler reads sources on cadences a person adopted; a workflow may *wait on* a read, never cause a write on a timer.

## 3. The model

### 3.1 Definition

```text
WorkflowDefinition
  key, title, when (the trigger in words), areas
  subject        what a run is about: a cycle (a year), a meeting (a date), a unit, a request, a vendor, a document, a campaign
  roles          who may do what: the offices (manager, president, secretary, treasurer, director, administrator) and "any signed-in person"
  steps[]        see below
  clocks[]       the deadlines that run on the whole (each cited: law, documents, proposed policy, or a person's own)
  refs           the docs and procedures to read; the lessons that shaped it
```

A **step** has: `id`, `title`, `kind`, `who` (a role), `needs` (the step ids that must be done or skipped, and any facts that must hold), `produces` (what it makes: a link kind), `evidence` (what shows it is done), `command` (the terminal command, where one exists), `clock` (its own, optional), `skippable` (and who may skip, with a reason), and `repeat` (once, per unit, per owner, per period).

The seven **step kinds**:

| Kind | What it is | Who acts | Done when |
|---|---|---|---|
| `check` | jason reads stores and reports pass / fail / not enough information, with the evidence it read | jason, on open and on demand | the check passes, or a person records why it does not apply |
| `job` | a queued command (a read or a sync) | the worker | the job finished (succeeded; or failed, which stops the step and says why) |
| `plan` | an approvals plan: the writes jason would make, with evidence | a person approves item by item | the plan is applied (every approved item applied); a rejected or held item is recorded |
| `person` | an act jason cannot do (mail, a call, a vote, a visit, a decision in another system) | a named role | the person attests it, with the date and, where the step asks, the record they point to |
| `decision` | a decision reserved to the board or the members (a vote, an adoption, a policy) | the board, recorded by its secretary | the decision is recorded with its date, the meeting, the vote as taken, and the instrument |
| `wait` | until a date, a clock, an arrival (an answer, a reply, a delivery), or another step | nobody (the run is waiting) | the thing arrived, or its date passed (which may open a follow-up) |
| `branch` | a choice between paths, by a fact or by a person | jason (by fact) or a role | a path is chosen and recorded; the other path's steps are not applicable |

### 3.2 Run, step state, and events

A **run**: `id`, `definition`, `subject` (with its label), `opened` (by whom, when), `dates` (the cycle's dates that steps read), `state`, `steps[]` (each with its state), `links[]`, and the **event log**.

- **Run state:** `draft` (being set up; no clock runs), `active`, `paused` (a person's pause, with a reason), `waiting` (every open step is a wait), `done`, `cancelled` (with a reason), `failed` (a step failed and nobody has resolved it).
- **Step state:** `not started`, `ready` (its `needs` hold), `running` (a job), `waiting` (why, until when), `needs a person` (who), `done`, `skipped` (by whom, why), `blocked` (by which step or fact), `failed` (the message), `superseded` (a re-plan replaced it).
- **Events** (append only; the run's state is a fold of them): `opened`, `step-ready`, `check-ran` (result, evidence), `job-queued`, `job-finished`, `plan-made`, `approval-decided`, `applied`, `attested` (who, what, the record), `decided` (the board's), `waited`, `arrived`, `skipped`, `paused`, `resumed`, `reopened` (a done step opened again by a later fact), `changed` (a store moved under a done step), `note`, `cancelled`. Each carries `by` (a signed-in name or `jason`/`scheduler`), `at`, and `detail`. A correction is a later event, never an edit.

### 3.3 Rules that make it durable

1. **Persistence.** `data/workflows/<definition>/<run-id>.jsonl` (the events) and an index; written under the store lock (`jason.locks`); an atomic append. A run is always readable without the server (disk only).
2. **Resume.** Opening a run re-evaluates its `check` steps and compares every done step's evidence with the store it came from; a difference is a `changed` event and the step reads "changed since" with the difference. Nothing is repeated that is done; nothing done is trusted blindly.
3. **Idempotence.** A `job` or `plan` step finds its earlier job or plan by a key (the run, the step, the subject) before it makes another.
4. **Who can act.** A step names a role; the server enforces it (the signed-in office, as the console already does). The run page shows a person *their* steps first, and others' steps as "waiting on the treasurer".
5. **Clocks have a basis.** Every deadline on a run is `law` (cited and recited from the stored text), `documents`, `counterparty` (a date another party stated, such as a vendor's quote or a notice from a fire authority; labeled, and not the law's), `proposed policy` (labeled, never a stamp), or `person`; a proposed number is the board's to adopt. A run past a legal clock says so in the law's words and opens a follow-up; it does not hide.
6. **Privacy follows the data.** A step reads and shows at the level of what it touches (P0 to P3, `jason.web.access`); a director sees counts and states where the requests area does; a run's list never carries an owner's contact details or an answer.
7. **Links, not copies.** A step links to its approval, job, follow-up, board item, dock task, document (`Doc`), or campaign by id; the run page shows their current state, read from them.

### 3.3a Child runs and step groups

Six of the seven family pages asked for the same two things, so they are part of the model:
- **A child run.** A step may *spawn* a run of another definition (an owner-information run spawns a notice-delivery run and a Mailroom run per batch; an inspection finding spawns a deficiency run, which may spawn a proposal request, a board item, and an insurer notice; onboarding spawns one ingest run per folder and one intake run per document). The parent step is `waiting` until the child is `done` or `cancelled`; the parent shows the child's state and links to it; a child never advances the parent past a decision. A run has at most one parent. Recommended; the engine records the link as a `run` link kind.
- **A step group.** A definition may include a *named group of steps* that other definitions reuse (response intake is shared by the owner-information cycle and every form campaign). A group is expanded into the run's steps at start, with its own prefix; it is a definition-time convenience, not a run.
- **A clock basis `counterparty`** is added to the four (law, documents, proposed policy, person); `followups.Basis` gains it with the engine.

### 3.4 How today's pieces become steps

| Today | In a workflow |
|---|---|
| A `Procedure` and its `Step`s (`person` flag, `command`, `check`, `refs`, `lessons`) | the definition; `person: True` becomes a `person` or `decision` step, a command a `job` or `plan`, a `check` a `check` step |
| An approvals plan (`jason approvals`, the Approvals inbox) | a `plan` step: the step's state is the plan's status |
| A follow-up (`jason followups`: remind, resend, ask, read, confirm, record, close) | a `wait` step's open edge, or a `person` step with a date |
| A campaign and its funnel | a run's subject (the owner-information cycle is one run with one campaign) |
| A job in the queue | a `job` step |
| A board item (planning layer) and the board's vote | a `decision` step |
| A dock task | a `person` step surfaced on the person's dock |
| A journey in [console/journeys.md](console/journeys.md) | the run's story: its screens are the interface below |

## 4. The web interface, common to every family

Routes are proposed, consistent with [console/information-architecture.md](console/information-architecture.md): a **Work** group (the run list and the run page) and a link from each existing screen to the runs it belongs to. Components are the built ones (`StageSteps`, `Findings`, `Command`, `Confirm`, `Doc`, `DueDate`, `Freshness`, `Caveats`, `Recitation`, `ReadingLabel`, `PlanReview`) plus the ones named below.

1. **Work** (`#/work`): every open run, grouped by whose move it is ("Yours", "Waiting on others", "Waiting on a clock", "Board"), each row: the run's label, the current step, its due date and basis, and its age. A director sees counts and states. Filters: definition, role, due soon.
2. **Run** (`#/work/<definition>/<id>`): the **step rail** (`WorkflowRail`: every step with its state as a word and a glyph, grouped by phase, the current step marked), the **step panel** (`RunStepPanel`; `StepPanel` is already `DriveChooser`'s): what to do, why, the evidence to look at, the command as a `Command`, and the act as a `Confirm` or a `TerminalStep`), the **clocks strip** (`ClockStrip`: each deadline with its basis), the **links** (what the run made, each in its current state), the **history** (the event log, newest first, with who and when), and the **changed-since** banner when a store moved.
3. **Start a run** (`StartRun`): the definition's subject, its dates (checked: leave room for one correction before an answer-by date), and the roles (who is the manager for this run). It creates a run in `draft`; opening it starts the clocks.
4. **Skip, pause, reopen, note** are small dialogs, each a `Confirm` recorded by name and each requiring a reason.
5. **The Today / dock** shows the person's open steps and the next clock on each of their runs.
6. **Print and export**: a run's history as a document for the board's record (a `Doc`), with its evidence addresses.

The interface never sends, files, or mails anything: a step that does is a plan the person approves or a command they run, and the run records the result.

## 5. The per-family pages

Each family page in [workflows/](workflows/README.md) is written to one template, so they can be compared and built in any order:

1. **The tasks** it covers, each with its trigger and its subject.
2. **For each task a definition table:** step id, title, kind, role, needs, produces, evidence, command, clock and its basis, repeat, skip rule.
3. **Branches and failure paths:** what happens when a check fails, an arrival never comes, a plan is rejected or held, a store changes under a done step.
4. **The clocks and their basis:** the law (cited from `data/authorities`, recited whole, never paraphrased), the documents, proposed policy (labeled), or a person's own.
5. **The screens:** which of §4's screens it uses, what is specific to the family (a campaign funnel, a meeting packet, a ledger), its loaders (built or to add), and its components (built or to add).
6. **Privacy and roles:** per step, the level and the role; what a director sees.
7. **What exists now:** the SOP key, the commands, loaders, stores, approvals kinds, and screens that already do part of it, each verified against the repo.
8. **Gaps and the build order** for that family.
9. **A made-up sample run** (a table of steps and states on plainly fake data) the design agent can draw.
10. **Acceptance criteria** a test could check.

## 6. What to build, in order

1. **The run store and the fold** (`jason.workflows`): a definition type that reads the existing `Procedure` rows and adds the step kinds, the run store, the event log, the state fold, and the resume check. Pure and tested on made-up definitions. No UI.
2. **`jason workflow`** (list, start, show, do, attest, skip, pause): the terminal first, as every write is, with `--by`.
3. **One family end to end**, chosen for how much already exists: the owner-information cycle (its approvals kind, campaign, follow-ups, and responses are built), then the bill attach (its queue, investigation, outcome, and approvals kind are built).
4. **The loaders** (`work`, `work-run`) and the writer for the small acts, then the **Work** and **Run** screens over them.
5. **The other families**, each a set of definitions plus the one or two screens specific to it.

## 7. Decisions that are not this page's

- **Which role may skip** a legal step (recommended: none; a legal step is done, or its absence is recorded as a finding for the board).
- **Whether a run may have two owners** (a manager who changes mid-run).
- **How long a done run is kept visible** (recommended: a year, then the history stays on disk and out of the list).
- **Whether the board approves a definition** (a workflow is jason's procedure, the lowest authority; a step that conflicts with the law or a rule is corrected in the definition, and the lesson is recorded).
