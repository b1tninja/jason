# Durable workflows: the engine

The engine behind [workflows-design.md](workflows-design.md): the types, the store, the fold, the resume check, the contract of each step kind, the terminal commands, and the tests. **Step 1 is built** (the pure library, section 10); the terminal, the readers, and the screens are not. Section 6 of the design page puts it first in the build order, with no UI. It is general: it names no association, and a definition names its subject, roles, and statutes as data.

## 1. Where it lives and what it may import

- `src/jason/workflows/` (a package). `types.py` (definition, step, run, event), `store.py` (the files), `fold.py` (events to state), `resume.py` (the re-check), `steps.py` (the step kinds), `definitions.py` (the registry), `api.py` (what the loaders, the CLI, and the MCP tools call).
- It may import `jason.locks`, `jason.tasks.followups` (the clock basis), `jason.approvals` (plans), `jason.community.procedures` (the rows a definition is built over), `jason.community` (`community()`), and `jason.web.access` only for role names. **Importing it loads no profile**; a definition is resolved when asked for. It never imports a profile.
- A definition is a row, like a rule row: `Workflow(key, title, family, subject, steps, ...)`. A profile adds or overrides rows through a `Community.workflows()` method with an empty default (`()`); the general ones live in `jason.workflows.definitions`. A new decision is a new row, not a new function. Match order is part of the rule.

## 2. The types

Enums, not strings: `StepKind` (check, job, plan, person, decision, wait, branch), `StepState` (not started, ready, running, waiting, needs a person, done, skipped, blocked, failed, superseded), `RunState` (draft, active, paused, waiting, done, cancelled, failed), `EventKind` (the list in the design page, section 3.2), `ClockBasis` (law, documents, counterparty, provider, proposed policy, person; `followups.Basis` has neither `counterparty` nor `provider` yet, and `followup_basis` answers `None` for them), `Role` (the offices in `jason.web.access`, plus `administrator`, `developer`, `reviewer`, `jason`, `scheduler`, and `anyone`). JSON stores the word; the loader turns it into the symbol before a task sees it.

```python
@dataclass(frozen=True)
class StepDef:
    id: str                     # "owner-info-cycle.9", stable; a step is never renumbered, only added to
    title: str
    kind: StepKind
    role: Role                  # who may act; for a decision, who records it (the secretary)
    needs: tuple[str, ...] = ()           # step ids that must be done or skipped
    why: str = ""               # one sentence, with the lesson or statute it cites
    command: str = ""           # the terminal command, shown and copied, never run by the page
    check: Callable | None = None         # check steps: a pure read of stores -> CheckResult
    plan_kind: str = ""         # plan steps: the approvals kind key
    job: str = ""               # job steps: the job-queue name
    evidence: tuple[str, ...] = ()        # store addresses the done step must still match
    clock: ClockDef | None = None         # when it is due, and on what basis
    repeat: Repeat = Repeat.ONCE          # once, per item, per period
    skip: SkipRule | None = None          # who may skip and with what reason; None for a legal step
    group: str = ""             # a step group's prefix
    spawns: str = ""            # a child definition's key
    sop: str = ""               # the Procedure step it was built from: "owner-info-cycle#4"

@dataclass(frozen=True)
class Workflow:
    key: str; title: str; family: str; subject: str   # subject kind: "campaign", "unit", "meeting", "period"
    dates: tuple[DateSlot, ...]                       # the dates a run is started with, with checks
    steps: tuple[StepDef, ...]
    phases: tuple[Phase, ...]                         # the rail's grouping
    procedure: str = ""                               # the Procedure key it was built from
```

A definition is **checked when registered** (`validate`): every `needs` names a step; no cycle; every `plan` step names a registered kind; every `job` names a job; every `spawns` names a definition; every `law` clock cites a section that resolves on the authorities shelf (a missing shelf is a skip, as in the tests); no id repeats; a **legal step** (one with a `law` clock, or marked `legal`) has no skip rule; a step with no skip rule is unskippable, legal or not. A definition that fails does not register, and the failure names the row.

Where a definition is built over a `Procedure`, `StepDef.sop` records the step's address (`key#index`), `person=True` becomes a `person` or `decision` step, a `command` becomes a `job` or `plan`, and a `check` becomes a `check`. `jason workflow --from-sop KEY` prints the draft definition for a person to finish; the draft is never registered by itself. A procedure and its workflow must not drift: a test fails if a registered workflow's `sop` addresses a step that no longer exists.

## 3. The store

- `data/workflows/<definition>/<run-id>.jsonl`: the events, one JSON object a line, append only. A run id is opaque (`run-` and ten hex characters from the hash of the definition, the subject key, the open time, and a random salt `api.start` gives and keeps nowhere), never an address or a name: without the salt a unit or a parcel is a few hundred values to try, and the open day shows on the run.
- `data/workflows/index.json`: a rebuildable summary (`id`, `definition`, `label`, `state`, `current`, `due`, `owner`, `updated`) so the list needs no replay of every run. It is a cache: deleting it loses nothing, and `jason workflow --reindex` rebuilds it from the events.
- Every append holds `locks.hold(Resource.STORE, "workflows-<run-id>")` and writes the line with a flush and fsync; a partial last line (a crash) is dropped on read and reported as `torn`, never repaired by guessing. The index is written to a temporary file and replaced, as the approvals store does.
- **An event:** `{n, kind, step, by, at, detail, prev}`. `n` is the run's sequence number (an append whose `n` is not the last plus one is refused, which is the compare-and-swap across processes); `prev` is the first 12 hex of the sha256 of the previous line, so an edited line breaks the chain at the next line's `prev`, and `jason workflow --verify` reports the first event whose `prev` no longer matches. The last line has no successor, so the index also keeps the chain's tip and its `n`, and `--verify` compares them. `by` is a signed-in name, `jason`, or `scheduler`. A correction is a later event.
- A run's folder holds nothing else; evidence stays where it came from and is linked by address (`links`), never copied.

### A made-up run, on disk

```
{"n":1,"kind":"opened","by":"A. Manager","at":"2099-09-15T09:00:00Z","detail":{"definition":"owner-info-cycle","subject":"campaign:OI-2099","label":"Owner information 2099","dates":{"answers_by":"2099-10-23","in_payhoa_by":"2099-11-01"}},"prev":""}
{"n":2,"kind":"check-ran","step":"owner-info-cycle.1","by":"jason","at":"2099-09-15T09:00:02Z","detail":{"ok":true,"evidence":["spec:forms.OWNER_INFO_CYCLE@a1b2c3"]},"prev":"9f3a1c0b27de"}
{"n":3,"kind":"attested","step":"owner-info-cycle.3","by":"S. Placeholder","at":"2099-09-16T14:20:00Z","detail":{"what":"settled the board's decisions","record":"minutes:2099-09-12#4"},"prev":"5d0e44a1c9b3"}
```

## 4. The fold and the resume check

- **The fold** (`fold.py`): `state(events) -> RunView`, a pure function. It yields the run state, each step's state, the clocks, the links, and the current step. No clock reads the wall time inside the fold: `today` is an argument, so a test is deterministic and a view is reproducible. A step is `ready` when every `needs` is done or skipped and the step is not superseded; `waiting` when a `wait` or a counterparty clock holds it; `needs a person` when it is ready and its kind is person or decision; `blocked` when a `needs` is failed; a run is `waiting` when every open step is a wait.
- **Resume** (`resume.py`): `resume(run, today) -> list[Event]` is what opening a run appends, under the run's lock. It (a) re-runs each `check` step that is ready or whose evidence moved, (b) compares each done step's evidence addresses with the store now (a changed hash is a `changed` event, and the step reads "changed since" with the difference), (c) reads each `plan` step's approval status and each `job` step's job state and appends `approval-decided`, `applied`, or `job-finished` for what changed, and (d) reads the `wait` steps' arrivals. It **appends nothing when nothing changed**, so a second open is a no-op. It never marks a person's step done, never applies an approval, never sends. A `changed` event never un-does a done step on its own; a person reopens it.
- **Idempotence key:** a `job` or `plan` step is found again by `sha1(run, step, subject, item)` before another is made, in the job queue and in the approvals store (`Approval.scope`). The key is stored in the event.

## 5. The step kinds: what each one may do

| Kind | jason does | A person does | Done when | Never |
|---|---|---|---|---|
| `check` | reads stores, returns `CheckResult(ok, evidence, message)` | nothing | the check passes now | write anything; a check that cannot read is `failed` with the reason, not `ok` |
| `job` | queues the named job (the queue holds the GPU and the store locks), reads its result | runs the terminal command if the job is not queued by the engine | the job finished and its result matches the step's evidence | run unqueued, or a model job without `local_ai.preflight` |
| `plan` | asks `approvals.engine.plan(kind, scope)` for a plan, links it | decides, submits, and applies it in `#/approvals` (two persons where the kind says so) | the approval is applied (or withdrawn with a reason, which the definition says is a skip or a failure) | decide, submit, or apply an approval; a `plan` step is never done by the run's owner clicking on the run page |
| `person` | shows the instruction, the evidence to look at, and the command | attests, in their own name, with the record the step asks for | an `attested` event by the role with its record | attest for someone; mark done without the required record |
| `decision` | shows the motion and links the decision | the secretary records the board's decision in the decisions store | a decision with a final outcome is on record for the motion | vote, adopt, or approve; owning the run gives no standing to record (the role alone does, so a person who is both owner and secretary records as the secretary) |
| `wait` | folds arrivals and the clock | nothing (an arrival, a date, or a person's `arrived` note ends it) | the arrival is on record, or the clock passed and the definition says what then | hide an overdue clock: a past `law` clock opens a follow-up and says so in the law's words |
| `branch` | evaluates a fact the definition names against the stores, or reads a person's answer | answers, when the fact is a person's | the fact is read; the unchosen path's steps become `skipped` by `jason` with the reason | pick a path from a guess |

Boundaries the engine adds to the ones in AGENTS.md: **it contains no code that sends mail, files a document, writes to PayHOA or Google, or decides**; every such act is a `plan` step (the approvals engine), a `job` the person queues, or a command they run. A definition cannot name a function that writes to an outside system; `validate` allows only registered approvals kinds and registered jobs.

## 6. Roles and access

- A step's `role` is checked on the server against the signed-in person's offices, as the console does for every write; the engine takes `by` as an argument and the web layer supplies it from the sign-in (a `by` in a body naming someone else is a 403). The engine itself trusts no caller: `attest(run, step, by=..., role_of=...)` refuses a `by` whose offices do not include the step's role.
- Directors and officers have the same access to information (they differ in duties): the engine's reads are gated by the level of what a step touches (`access.Level`), never by office alone. A list or an event never carries an owner's contact details or an answer; an event's `detail` holds addresses and counts.
- An executive-session matter (CIV 4935(e)) is held as the board items are: the list shows its general words and state, and the detail opens only in the private view, each opening logged.

## 7. The terminal: `jason workflow`

```
jason workflow --list [--definition KEY] [--state open|all] [--json]
jason workflow --definitions [--family F]
jason workflow --start KEY --subject S --label L --date NAME=YYYY-MM-DD ... --by NAME     (a draft)
jason workflow --open RUN --by NAME            (starts the clocks; runs resume)
jason workflow --show RUN [--events]
jason workflow --attest RUN STEP --record REF --by NAME
jason workflow --skip RUN STEP --reason TEXT --by NAME
jason workflow --na RUN STEP --reason TEXT --record REF --by NAME     (not applicable: not a skip)
jason workflow --set-date RUN SLOT=YYYY-MM-DD --record REF [--reason TEXT] --by NAME
jason workflow --pause RUN --reason TEXT --by NAME   |   --resume RUN  |   --reopen RUN STEP --reason TEXT  |   --note RUN --text TEXT
jason workflow --cancel RUN --reason TEXT --by NAME --yes
jason workflow --verify RUN | --reindex | --from-sop KEY
jason workflow --guide RUN[:STEP] [--for NAME]   |   --due --for NAME [--within DAYS] [--all]   |   --claim RUN STEP --by NAME [--release] [--yes]   (built, phase 1 of person-steps)
```

**Added when it was built (2026-10-11):** `--attest` also takes `--outcome`, `--motion` (a decision step), and `--choice` (a branch step), and `--what`; `--arrived RUN STEP` ends a `wait` step; `--item` (repeatable) sets a run's items at `--start` or names the item on a per-item step; `--expect N` refuses if the run's last `n` has moved; `--as-of DATE` fixes the clocks for a repeatable view; `--step` goes with `--note`. `--resume RUN --by` lifts a person's pause; `--open` is the resume check. `--cancel` always needs `--yes`. `--verify` exits 1 when the chain is broken. Roles come from the community's officers and the administrators; with no officers named, a role-gated act is refused with the reason. The default readers do not yet reach the approvals engine or the job queue, so `--open` runs the check steps and leaves a `plan` or `job` step waiting.

Every write needs `--by`; `--cancel` and `--start`/`--open` of a run with a legal clock need `--yes`. Non-interactive: it never opens a browser. A command that would change a run reads it first and refuses on a changed `n` (two persons at once). The same functions are `jason.api.workflow_*` and the MCP tools `workflows` and `workflow_run` (read only, on the board profile), each with its caveats.

## 8. Loaders and writers (the web layer)

`work`, `work-run`, `work-definitions` (read) and `POST /api/write/work/<definition>/<id>` for the small acts, as [console/screens/work.md](console/screens/work.md) lists them; they call `jason.workflows.api` and add only the sign-in and the level gate. The Work and Run screens are built after `jason workflow` works.

**As built (the backend, `jason.web.extra.work`; `tests/test_web_work.py`).** All three loaders and the writer are for the offices that open P2 (the manager and every board office) and for an administrator (who then reads the `ADMIN` definitions alone), and none is an owner source. A run is listed once, in the group of its most pressing open step (`yours`, `others`, `clock`, `board`; a decision step is always `board`, with `mine` set for the office that records it), legal dates first; a list row carries the run's label, step, role, date and basis, never a subject, an item, or a name. `work-run` folds the stored events and then a **dry resume** (what opening the run would append, from the stores now), so a GET writes nothing and `pending` says what the next open records; writing is the `open` act or `jason workflow --open`. The writer maps each act onto one `api` function with the signer's account as `by` and the roles of their offices (403 for a role refusal or a `by` naming someone else, 400 for a rule, 409 for a run that moved on since `expect`); it does not take a `decision` or a `plan` step's attestation (those belong to Decisions and Approvals), and `start` accepts `dryRun` to check the dates. Executive-session handling is by definition, not by step (held definitions, below). Not composed: a step marked executive inside an open run, a counterparty on a wait, the decision's mover, second, and vote, a definition's cadence and who may start it, and the follow-up a past legal date should open.

## 9. Tests (written with the engine)

1. **The fold is pure:** the same events and `today` give the same view; replaying a prefix gives the earlier view.
2. **Durability:** kill the process between two appends (a torn last line): the run reads, reports `torn`, and appends cleanly after it.
3. **Compare-and-swap:** two processes appending at once: one wins and the other gets a refusal naming the changed `n`.
4. **Resume appends nothing when nothing changed;** a changed store appends one `changed` event and does not un-do the step.
5. **Idempotence:** opening a run twice makes one job and one plan.
6. **Roles:** a `person` step refuses an attester without the role; a `decision` step refuses the run's owner; a body `by` for someone else is refused by the web layer.
7. **Boundaries:** `validate` rejects a definition naming an unregistered approvals kind, a job, a missing step, a cycle, a legal step with a skip rule, or a `law` clock whose section does not resolve; the import test shows importing `jason.workflows` loads no profile; a source test shows no module in the package imports a sending, filing, or writing client.
8. **The hash chain:** an edited line is reported by `--verify` with its `n`.
9. **Procedure drift:** every registered definition's `sop` addresses exist.
10. **The first family end to end** on made-up data: the owner-information run, from `--start` to the last step, with a fake approvals plan and a fake job, in a temporary data folder.

## 10. As built (step 1, 2026-10-11)

The pure library is in `src/jason/workflows/` with 65 tests (`tests/test_workflows_*.py`). Differences from, and additions to, the sections above:
- `StepDef` also has `record` (what an attestation must point to), `legal`, `elapsed` (a wait's clock ends it, or only flags it overdue), `on_withdrawn` (fail or skip), and `choices` (a branch's paths); `Workflow` has `clocks` for the whole run's deadlines.
- `EventKind.SPAWNED` records a child run. A draft run is `opened` with `detail.draft`; `open_run` appends `resumed` with `activated`. Resume appends `waited` once, when a wait begins, and never writes `step-ready` (the fold derives readiness). A branch's unchosen path reads skipped by `jason` in the fold, with no event; the branch check returns its choice in `CheckResult.choice`.
- A `superseded` step does not satisfy a `needs`: the replacement must be a step the later steps also need.
- Past `law` clocks are reported (`RunView.past_law`); opening the follow-up is the caller's write, not the engine's.
- `Role` is a string enum in `types.py`; every holder in `jason.web.access.SEE_RULES` is a value (a test pins it), and it adds `administrator`, `jason`, `scheduler`, and `anyone`.
- `definitions.extra(provider, **checks)` is the hook for a profile's rows; `Community.workflows()`, a `Readers` backed by the approvals engine and job queue, a job-name registry, and the overdue-law follow-up are not built.
- SOP addresses are `key#N` counted from 1, as `jason sop` numbers them. `--start` and `--open` both need `--yes` when the run has a legal clock.
- Cancel is the secretary or the manager with a reason and `yes` (`CANCEL_ROLES`, one constant).

### Step 3 (2026-10-11): store-backed readers and the first definition

- `jason.workflows.readers.StoreReaders` reads the approvals store, the job queue's database, the response inbox, the follow-ups, and the notice ledger, and writes nothing (a test pins the data folder byte-identical after every call). `jason.workflows.definitions_general.register_general()` registers the general definitions; `jason workflow` calls it, never an import. The first is `owner-info-cycle` (27 steps: the table's 25 plus the board decision and the tags plan under group IN), with its date slots asked at start and one law clock, the entry day (30 days before the reports are mailed, `CIV 4041(b)(1)`).
- **A reader adopts; it does not make.** Planning an approval or queueing a job reads the live system, so the reader links the newest plan of the step's kind made since the run opened, or a queued job it recorded, and a person plans or queues. This replaces section 4's "a `job` or `plan` step finds its earlier job or plan by a key before it makes another" for plans.
- **Edge modules.** `readers` and `definitions_general` import the approvals store, the job queue, and read functions of the tasks; the boundary test gives them an allow-list of read-only stores. The core modules still import none.
- **The second definition, `control-adoption` (2026-10-11):** one run per control (subject `control:KEY`, family `board`, no date asked at start, no procedure, no statute: the effective date is the board's, a `person` basis). Eight steps: suggest (a check), put it before the board (a person, `anyone`), the board decides (a decision, the secretary), record the outcome (a branch: `adopted` or `declined`; a declined control skips the rest and the run is done), set the effective date (the secretary), check the roster (warns, blocks nothing), in force (a wait the date and the check end; role `jason`, so no person turns it on), and the yearly review (a wait the secretary notes, or the board's retiring the control, ends). Its five reads (`control-suggested`, `control-outcome`, `control-roster`, `control-in-force`, `control-retired`) are in `readers.CHECKS`, read the controls' act log (`jason.controls.store`) and the decisions store, and write nothing; the edge allow-list gains `jason.controls` and `jason.tasks.decisions`. A deferral leaves the decision step open (a tabled or continued decision is not final). No command records the board's outcome on the control yet (`jason controls` has no adopt, decline, or defer): the secretary uses `jason.controls.store.record`.
- **Open:** (per-step item sets are built: see engine round three below); a `second` role on a step for the "2P" steps; a recorded `campaign` or `notice_key` on the run (derived today from the dates); children `owner-document` and `notice-delivery` are not defined, so `spawns` is empty.

### Engine round two (2026-10-11): limits 1, 2, 3, 4 and the basis and roles of 8

`tests/test_workflows_engine_v2.py` (34 tests, with a golden log written before the round that folds identically). Nothing here changes a definition that does not use it; every old log folds as it did.
- **Several roles on a step (limit 1).** `StepDef.roles` lists further roles beside `role`; `role` stays the primary, the one a list shows. A person holding any of them may `attest`, `arrived`, `skip` (a skip rule with no roles of its own takes all of them), and `reopen`. `StepDef.acting_roles` is the primary first, then the others, each once. `validate` refuses a `roles` entry that is not a `Role`, a repeat, and the primary repeated; a decision or person step is checked over every role. A refusal for one role reads as before ("does not hold the manager role that X needs"); for several, "does not hold a role that X needs (manager or treasurer)". The run JSON and `StepView` carry `roles`; `StepAsk.step_roles` carries them to a gate, and `jason.controls.effective.step_gates(..., step_roles=)` counts a second person across all of them. No existing definition was widened.
- **Not applicable (limit 2).** `StepDef.na = NotApplicable(roles, reason_required, record_required)`. The act `na` (`api.not_applicable`, `jason workflow --na RUN STEP --reason --record --by`, the writer act `na`) is recorded by a person holding one of `na.roles` (none: the step's roles), with a reason and a record, as a `not-applicable` event. The step is **done, not skipped**: `StepView.na` is true, its state is `done`, its reason reads "recorded as not applicable by NAME: reason", it satisfies a `needs`, and the history sentence is the same. A legal step may carry `na` though `validate` still refuses a skip rule on it, and a skip of it is still refused. The step's clock is kept and reads **"not applicable, recorded"** (neither `satisfied` nor dropped), so it is not past and opens no follow-up. A branch has no `na` (its path is chosen). `reopen` takes it back. The same gates apply as to a skip: `_gated` asks the control gate with act `na`, a second-person gate makes the first a `first_of_two` note (`api.pending_first(events, step, "na")`), and the run page's per-step `controls` list a step that has `na` or a skip.
- **Dates after the start (limit 3).** `DateSlot.late` (not asked at the start, so `check_dates` does not require it), `DateSlot.timing` (`DateTiming.ANY`, `PAST` for a day that has come, `FUTURE` for one that has not), and `DateSlot.roles` (none: any named person). A slot is **settable** when it is `late` or not `required`. The act `date-set` (`api.set_date(run, slot, day, by, record=, reason=)`, `--set-date RUN SLOT=YYYY-MM-DD --record --by`, the writer act `set-date` with `{slot, day, record, reason?}`) is refused for a slot the definition lacks, a slot fixed at the start, a day that is not `YYYY-MM-DD`, a day that breaks the slot's own timing, and a day out of order with the slot it comes `after` or a slot that comes after it; it always needs a record. A slot that already has a day (from the start or an earlier `date-set`) is a **correction** and needs a reason. Append-only: the fold takes the latest `date-set` per slot, recomputes every clock from the dates as they stand, and ignores a `date-set` for a slot the definition lacks. The run JSON (`api.view_dict` and `work-run`) gives `dateSlots` (value, who set it, how many times, settable, correction) and `openSlots`, and `acts.setDate` says which the viewer may set. A run that is done or cancelled takes none.
- **A step that waits on its child runs (limit 4).** `StepDef.waits_on_child` (needs `spawns`; `validate` says so). The fold keeps the children spawned from each step (`StepView.children`, in order; `api.spawned` may be called once for each, and a repeat of one child is refused). With the flag, the step is **not done until its own act is on record and every child spawned from it is `done` or `cancelled`**: with any child unfinished it reads `waiting` ("child run X is running", or "1 of 2 child runs finished; waiting on ..."), so a person cannot attest it until they finish; a branch records its choice, then waits when a child is spawned, and its path's steps open when the branch is done (the unchosen path reads skipped as soon as the choice is made). A step done before any child is spawned is done (nothing to wait for), and waits again if one is spawned. A reopen keeps the children. A step **without** the flag is unchanged: the last child decides, a branch never waits.
- **Basis and roles (limit 8, part).** `ClockBasis.PROVIDER` ("provider", labeled PROVIDER, handled as `counterparty` is: no `followups.Basis` yet). `Role.DEVELOPER` and `Role.REVIEWER` are roles but not offices: the boundary test pins them with `administrator`, `jason`, `scheduler`, and `anyone` as the roles `SEE_RULES` does not name, and nothing in the board's roster holds them (a roster passed as `roles_of` does). Business-day offsets are still calendar days only.
- **Still open from the list below at the end of round two:** 5 (per-item steps), 6 (step groups), 7 (a `wait` ended only by a person's note), business-day offsets, 9 (checks, jobs, kinds), and conditional or per-item spawning. Round three (next section) builds 5, 6, 7, business days, and the remedy; 9 and per-item spawning stay open.

### Engine round three (2026-10-11): a remedy, item sets, step groups, business days, a wait only a note ends

`tests/test_workflows_engine_v3.py` (the cases, the golden log of round two folding as it did, and seeded property tests of the fold). **No event kind and no event field changed**; an old log folds as it did (a test pins the round-two golden log), and the file format, the hash chain, and the compare-and-swap are untouched. Every new field has the default that means "as before", so no registered definition changed. `definitions.validate` refuses the combinations that cannot hold (a remedy that is not a check the step needs, per-item rules on a step that does not repeat, a per-item path over a different set, a note wait that names a check or lets a date end it, a group declared twice).

- **A remedy (the failed check that blocks its dependents).** `StepDef.remedy_of = "<check step id>"`, on a step that `needs` that check. A failed check still blocks every dependent, **except** the step named as its remedy: that step is not blocked by the failure and opens as soon as its other needs hold. The check **stays recorded as failed** (its state, its `check-ran` events, and its message are unchanged), so the log never says it passed. While the remedy step is open (ready, running, waiting, or needs a person), the failed check does not make the run `failed` and is not the run's current step (the remedy is); `StepView.remedy` on the check names the remedy step. Once the remedy is done and the check still fails, the run reads `failed` again, the dependents of the remedy are open, the other dependents of the check stay blocked, and a resume re-reads the check (it re-runs a failed check as before) and the held-back steps open when it passes. A remedy blocked by another need stays blocked: only the named check is excused. Only a `check` step is remedied.
- **Item sets (limit 5).** `StepDef.item_set` names the set of items a step repeats over (`""` is the run's own items, as before). `StepDef.item_needs` lists steps in `needs` that are read **item by item**: an item waits only for its own item of them, not for every item. Items are **supplied while the run goes**: `api.supply_items(data, run, set, items, by, roles_of=, record=)` (`steps.supply_items_act`) appends a `note` event with no step whose detail has `items_supplied: {set, items}` and a `text` (a use of the existing `note` kind, as `first_of_two` is; the fold reads it and nothing else does). An item is an opaque id (letters, digits, and `: _ . # / -`, at most 64 characters: no space and no `@`, so a name or an address cannot ride in one), once in a set, in the order given; up to 500 at a call; supplied by the run's owner or a person who may act on a step over the set, while the run is a draft or going. An entry may be `{id, dates}`: slot dates (declared slots, `YYYY-MM-DD`, with a `record`) that the item's own clocks read before the run's; a later supply of the same id corrects them (the latest wins, both events stay). The set `""` is the run's items from the start plus anything supplied to it; a step that names no set behaves exactly as before.
  - **Roll-up.** A step that names a set or per-item needs (`StepDef.item_aware`) reads as its **most pressing item**: failed, needs a person, ready, running, waiting, blocked, not started (`fold.SEVERITY`); done when every item is finished (skipped when none was done). `StepView.items` lists every item's state (even for one item), `StepView.item_counts` counts them by state, and the reason reads "N of M items done; ..." with the pressing item's reason. A step that does not name a set keeps the old roll-up (the first unfinished item speaks) and the old quirk of listing no items for a set of one.
  - **No items yet.** An item-aware step whose set is empty is `waiting` ("no items in the set X yet") and refuses an act that names an item. It can be skipped or recorded as not applicable (if the definition allows) to move past an empty set.
  - **Per-item branches.** A `branch` that names a set takes one choice **for each item**; the steps on the other path are `skipped` **for that item only** ("not on the path P chosen at B for item X"). Its path steps must repeat over the same set (`validate`). A branch with no set keeps the one global choice.
  - **A clock for each item.** `ClockDef.per_item` on a step that repeats gives one `ClockView` per item (key `step[item]`, `ClockView.item` the item, `step` the step), from the item's dates before the run's, satisfied or "not applicable, recorded" by that item's own state. A step with no items yet keeps the one step clock. `past_law` and the list's due date read the per-item keys like any other.
  - **Built after the round (2026-10-11): the terminal command and the Work screens.** `jason workflow --supply RUN --set NAME --item ID [--item ID ...] --by NAME [--item-date ID SLOT=YYYY-MM-DD --record REF] [--yes]` (`api.supply_items`; the person must be on the roster; without `--yes` it makes every check and prints what would be recorded, `api.supply_items(..., dry_run=True)`, and writes nothing). The Work loaders pass `groups`, `run.itemSets`, each step's `perItem`, `itemAware`, `itemSet`, `itemCounts`, `remedy`, and `remedyOf`, and each per-item clock's `item`; the writer has the act `supply-items`; the run page draws the item table with its roll-up, the groups, the remedy, and a Supply items form (`docs/console/screens/work.md`, "Item sets, step groups, and a remedy").
- **Not built here.** Removing an item from a set (an item is skipped, not removed: append-only); per-item spawning (a child run for each item); a way to give a set's items from a file (`--item` repeats; there is no `--items-file`); item rows in the list and the Today band (a row names the run, never an item).
- **Step groups (limit 6).** `StepDef.group` names a group and `Workflow.groups = (StepGroup(key, title), ...)` titles them (a group no row declares is titled by its key; once a definition declares any, every step's group must be among them). The fold gives `RunView.groups`, one `GroupView` per group in the order the steps first name it: its steps, a roll-up state (the same rule as items), how many are finished, `expanded` (the group holds the run's current step or a failed one, and the run is not finished) or collapsed (done, or not yet reached), and the current step in it. **A group is a reading, not a step**: no event is added, and nothing is expanded into the run's steps at start (the design page said "expanded at start"; the definitions already write a group's steps out, so the engine folds them rather than expanding them). The steps are what they were. `api.view_dict` carries `groups` only when there are some. *Built after the round:* the run page draws each titled group as a collapsible section in the rail (open where `expanded`, shut otherwise; a person's click wins), with its roll-up state and "N of M done".
- **Business days (limit 8, the rest).** `ClockDef.business_days` counts `days` in business days: Monday to Friday, less a calendar of holidays (`fold.add_business_days`; the starting day is not counted, `0` is the day itself, a negative count goes back). **The fold reads no calendar**: `fold.state(..., holidays=)` takes it, and when none is given it takes the `holidays` of the `children` mapping it is handed, which is what `resume.children_of(events, readers)` returns (a dict that carries `readers.holidays()`), so every existing caller, the dry resume included, gets the readers' calendar without a change. `Readers.holidays()` returns an empty set by default (weekends only: a business-day deadline is then the earliest it can fall, as `jason.tasks.followups` says of its own); a reader that knows the community's holidays overrides it, and a calendar that cannot be read is an empty one. **No holiday is in the engine's code.** The community's calendar is `Community.holidays()` (days as `YYYY-MM-DD`; an empty default, so weekends only), read by `StoreReaders.holidays`; no profile sets one yet.
- **A wait only a note ends (limit 7).** `StepDef.ends_by_note` on a `wait` step with no check and `elapsed` left at `overdue`: no reader's arrival and no date ends it (resume does not ask the readers for an arrival, and the fold ignores an `arrived` event written under `jason` or `scheduler`). A person holding one of the step's roles ends it with `arrived`, and **must say what arrived** (the note, `--what`), which is stored as the event's `what`; the step reads "for the manager to record a note that it arrived (due DATE)" while it waits, and an overdue clock is still reported, never hidden. An ordinary wait keeps its old act (no words needed).
- **The dry resume** reads the new features with `resume.pending` as before: it enumerates per-item checks for every item supplied, skips the arrival read for a note wait, and a second open appends nothing (tests).
- **Property tests of the fold** (seed-parametrised, no library): the fold is deterministic over random logs of every event kind (valid and not); a log read back from JSON folds the same whatever the order of the child mapping or the form of the calendar; a prefix gives the earlier view and item sets only grow, in order; supplying what is already there changes nothing but the count; the states do not depend on the day; a failed check with its remedy open never leaves the run failed or current; the roll-up is order-free and a failure always shows; and business-day arithmetic is consistent (landing on a business day, counting in two goes, back again).

### All families written as code (2026-10-11)

`jason.workflows.defs` holds one pure-data module per family (`members`, `board`, `money`, `records`, `property`, `platform`); `register_general` registers the general two and every builder in them (46 in all). Rules every module follows: it imports only `jason.workflows.types` (and `named_check`), names only registered plan kinds, jobs and checks, and turns every other check, job or plan of the page into a `person` step whose `why` says what it becomes and whose `WANTED` entry names it (about 250 reads, jobs, kinds and cases across the families). A definition the Work backend must treat with care carries a `Workflow.visibility` (see "Held and administrator runs" below): `hearing`, `delinquency-account`, and `records-production` are `HELD` (member discipline, a parcel and balance, restricted kinds), and `integration-connect`, `service-run`, and `check-in` are `ADMIN`. All are in `BUILDERS` (the 46 became 52).

**Engine limits found by writing them all** (each is a build item):
1. **One role per step.** *Built (engine round two): `StepDef.roles`.* The definitions still name one role each; widening them to the pages' "treasurer or manager" is a definition change.
2. **A law clock makes a step legal and a legal step cannot be skipped,** but many pages skip a step "when not applicable". *Built: `StepDef.na` and the `na` act.* The definitions still use a branch path or put the statute in `why`; moving them to `na` is a definition change.
3. **Dates are fixed at start.** *Built: `DateSlot.late` and the `date-set` act.* The definitions still ask for the dates they ask for.
4. **A branch does not wait for a spawned child,** and a step with `spawns` ends when the last child ends. *Built for a step that opts in: `StepDef.waits_on_child`.* Per-item and conditional spawning still cannot be expressed (**not built**).
5. **Per-item steps** take one item list fixed at start and wait on every item of the previous step; per-item branches and per-item `needs` are needed (letters, requests, links). *Built (round three): `StepDef.item_set` and `item_needs`, items supplied while the run goes, a per-item branch and clock, and a roll-up; then `jason workflow --supply`, the `supply-items` act on the Work writer, and the run page's item table, roll-up, and Supply items form.* The definitions still use the run's own items; moving them to named sets is a definition change.
6. **Step groups are not expanded** (`StepDef.group` is unused); groups were collapsed by hand. *Built (round three) as a reading: `Workflow.groups` and `RunView.groups`, expanded and collapsed in the fold and the readers; the Work run page draws them as collapsible rail sections.* No definition declares titles yet.
7. **A `wait` with no named check ends only by a person's note.** *Built (round three): `StepDef.ends_by_note`.* The definitions still use an ordinary wait.
8. **`ClockBasis` lacks `provider`;** `Role` lacks a developer value and a reviewer; business-day offsets are calendar days only. *Built: `ClockBasis.PROVIDER`, `Role.DEVELOPER`, `Role.REVIEWER`; and business-day offsets (round three: `ClockDef.business_days` against a calendar the readers supply).* The community's holiday calendar itself is `Community.holidays()` (empty by default), read by `StoreReaders.holidays`.
9. **No check or job fits** without the reads in `WANTED`: the next engine work is a set of read-only checks (the `CHECKS` registry), the job names, and a handful of approvals kinds and `gmail-drafts` cases.

### Person-step guidance, phase 1 (2026-10-11)

`StepDef.support: Support | None` (enable, remind, guide; [workflows/person-steps.md](workflows/person-steps.md), section 4) is optional frozen data, and a step with none behaves as it did: **no event kind and no event field changed**, and the fold is untouched. Three modules join the package (`tests/test_workflows_boundaries.py` lists them): `guide` (core: the derivation of a step's words from what it holds, the `Support` validator, `from_mapping`), `nudge` (core, pure: the bands, the proposed numbers, the default escalation table, `claims_of`), and `guide_reads` (edge: the registry of read-only look-at reads and the two response-inbox reads). `definitions.validate` and `register` take the optional registries `reads`, `lessons`, and `integrations` (each skipped when not given; `register_general` gives the first two). A **claim** is a `note` event on the step with a `claim` key (`steps.claim_act`, `api.claim`, the writer's act `claim`, `jason workflow --claim`): not an assignment, ended by the step's ending, a release by its maker, or a reopen. `jason workflow` gains `--guide RUN[:STEP]` (or `DEFINITION.STEP`), `--due --for NAME [--within DAYS] [--all]`, and `--claim RUN STEP [--release]`; the Work page's step rows gain `enable`, `nudge`, and `guide` (person steps only; a held run outside the private view carries none), composed by `jason.tasks.step_guide`. Six steps in four families carry a `Support` as worked examples; the rest fall back. Not built: snooze, the away log and cover, the blocked note, `--remind-draft`, the `work-due` loader, the digest section, and the list marks.

### Jobs and kinds still wanted

<!-- wanted:begin (generated by python -m jason.workflows.jobs.wanted --write; do not edit by hand) -->

Generated from each family's `WANTED` against what is registered (`jason.workflows.jobs.wanted`; `tests/test_workflows_wanted.py` fails when this list drifts). A job is a **descriptor** of an existing jason command: a person runs the command, and the engine only recognizes the queued job by its words and reads how it ended. `jobs.READY` names the families whose descriptors are registered in `readers.JOBS`; all six are in it now, so each family's `WANTED` lists only the jobs with no single command (a registered job's step stays a person's: the Work page shows the command with Copy, and the engine only recognizes the job when a person queues it). No approvals kind is added here: that is the board's call, so the kinds are only listed.

| Family | Jobs wanted | Registered | Descriptor written, family not ready | No single command | Neither descriptor nor reason | Plan kinds and cases wanted (unmet) |
|---|---|---|---|---|---|---|
| members | 2 | 0 | 0 | 2 | 0 | 6 |
| board | 1 | 0 | 0 | 1 | 0 | 8 |
| money | 4 | 0 | 0 | 4 | 0 | 1 |
| records | 7 | 0 | 0 | 7 | 0 | 2 |
| property | 0 | 0 | 0 | 0 | 0 | 6 |
| platform | 0 | 0 | 0 | 0 | 0 | 2 |

**Registered job families (`jobs.READY`):** `board`, `members`, `money`, `platform`, `property`, `records`. A registered job leaves its family's `WANTED`, so a ready family's wanted jobs are only those it has not described.

**No single existing command to point at:**

- members: `respond-standards` -- its command is not built (`jason respond --standards`)
- members: `letter-pdf-export` -- it writes (`--yes`): a plan step's act, not a job a worker runs
- board: `duties-score` -- a script (`scripts/eval_duties.py`), not a jason command
- money: `bill-sources-read` -- three commands (`fetch-bills`, `sync-tax`, `vendors --sync`): a job names one command
- money: `tax-documents-keep` -- a signed append (`--by NAME`): a person's act, not a queued read
- money: `books-sync` -- four commands (`books`, `budget`, `reconcile`, `ledger`): a job names one command
- money: `packet-build` -- it writes Docs (`--yes`): a plan step's act, not a job a worker runs
- records: `citations-scan` -- three commands (`segments`, `cite --scan`, `cite EXPR`): a job names one command
- records: `library-drive-sync` -- two commands (`library`, `drive`): a job names one command
- records: `parcel-gap-lookup` -- no command yet
- records: `parcel-report` -- the same command as `parcel-history` (`instrument-graph --parcel`); no word tells the two apart in the queue
- records: `recorder-reading` -- an MCP tool (`recorder_search`, `recorder_detail`), not a jason command
- records: `record-read` -- it writes (`--yes --by NAME`): a plan step's act, not a job a worker runs
- records: `split-read-back` -- it writes (`--yes --by NAME`): a plan step's act, not a job a worker runs

**Plan kinds and cases still wanted (the board's call; none is registered by this work):**

- members: `payhoa-owner-info-mail-batch`, `payhoa-mailroom-cancel`, `payhoa-request-create`, `gmail-drafts/acknowledgment`, `google-doc`, `payhoa-form-update`
- board: `google.doc`, `google.calendar+google.tasks`, `zoom.hearing.create`, `local.section-refs.apply`, `gmail-drafts/rule-change-proposed`, `gmail-drafts/rule-change-adopted`, `gmail-drafts/election-notice`, `gmail-drafts/decision-notice`
- money: `annual-packet-docs`
- records: `local.ingest.apply`, `local.living.reread`
- property: `gmail-drafts/insurer-notice`, `gmail-drafts/vendor-question`, `gmail-drafts/owner-request`, `drive-filing`, `payhoa-comment`, `doc-write`
- platform: `payhoa-requests-from-email`, `gmail-thread-reply`

<!-- wanted:end -->

### Held and administrator runs (2026-10-11)

`Workflow.visibility` is a `Visibility`: `BOARD` (the default: every office that opens P2), `ADMIN`, or `HELD`. Two more fields go with it: `held_title` (the general words a held run shows outside the private view, such as "A member's hearing"; one line, at most 80 characters, no digit or `@`, and only a held definition has one) and `console_start` (False for a terminal procedure the console never starts; `check-in`). A step may set `public_title` when its title names no matter, so a held run may show it outside the private view. `definitions.validate` refuses a held definition with no title, a title on any other, and a `public_title` on a step of any other.

`jason.web.extra.work_scope` decides, and the Work loaders, the writer, and the office view ask it:

- **HELD.** Outside the private view a run is its `held_title`, its state, its group, whose move it is by office, the date and its basis word (no clock label, no citation), and the run id as an opaque handle (`held` is true). `work-run` answers a page with nothing in it but that. The text filter matches only the general title, so searching for a street finds nothing. Inside the private view (`access.private_window()` open, for an office that opens P3 in it) the whole run, and each list, page, act, and start that shows one is a line in `access/served.jsonl` (P3, with the private view's id and reason, under the run id); a log that cannot be written serves nothing (503). Outside the private view an act on a held run is the 404 a missing run gets, and starting one is a 403 (a dry run too).
- **ADMIN.** Only an administrator (`Viewer.admin`) sees the definition in the catalog, its runs in the list or its counts, reads a run, acts on one, or starts one. For anyone else a read is the 404 a missing run gets, a start is the 400 an unknown definition gets, and no sentence names it. An administrator who holds no office reaches the three Work loaders for these alone; one who also holds an office sees both.
- **`console_start` false.** Listed (to an administrator) with `startable` false and the sentence, never started by the console; `jason workflow` starts it.
- **The run id.** `api.start` gives every run a random salt, so no id is derived from a subject; a run started before this change keeps its id.

## 11. Decisions for you

- **One file per run or one folder per definition** (recommended above: a file per run, a folder per definition).
- **The hash chain** is cheap and makes an edited record visible; it is not a signature. Keep it, or drop it as more than a local store needs?
- **Who may `--cancel`** a run with a legal clock (recommended: the secretary or the manager, with a reason, and the cancelled run stays listed for the board).
- **Whether the index is a cache only** (recommended) or the list's source.
