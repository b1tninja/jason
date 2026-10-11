# Durable workflows: the engine

The engine behind [workflows-design.md](workflows-design.md): the types, the store, the fold, the resume check, the contract of each step kind, the terminal commands, and the tests. **Step 1 is built** (the pure library, section 10); the terminal, the readers, and the screens are not. Section 6 of the design page puts it first in the build order, with no UI. It is general: it names no association, and a definition names its subject, roles, and statutes as data.

## 1. Where it lives and what it may import

- `src/jason/workflows/` (a package). `types.py` (definition, step, run, event), `store.py` (the files), `fold.py` (events to state), `resume.py` (the re-check), `steps.py` (the step kinds), `definitions.py` (the registry), `api.py` (what the loaders, the CLI, and the MCP tools call).
- It may import `jason.locks`, `jason.tasks.followups` (the clock basis), `jason.approvals` (plans), `jason.community.procedures` (the rows a definition is built over), `jason.community` (`community()`), and `jason.web.access` only for role names. **Importing it loads no profile**; a definition is resolved when asked for. It never imports a profile.
- A definition is a row, like a rule row: `Workflow(key, title, family, subject, steps, ...)`. A profile adds or overrides rows through a `Community.workflows()` method with an empty default (`()`); the general ones live in `jason.workflows.definitions`. A new decision is a new row, not a new function. Match order is part of the rule.

## 2. The types

Enums, not strings: `StepKind` (check, job, plan, person, decision, wait, branch), `StepState` (not started, ready, running, waiting, needs a person, done, skipped, blocked, failed, superseded), `RunState` (draft, active, paused, waiting, done, cancelled, failed), `EventKind` (the list in the design page, section 3.2), `ClockBasis` (law, documents, counterparty, proposed policy, person; `followups.Basis` gains `counterparty`), `Role` (the offices in `jason.web.access`, plus `jason` and `scheduler`). JSON stores the word; the loader turns it into the symbol before a task sees it.

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

- `data/workflows/<definition>/<run-id>.jsonl`: the events, one JSON object a line, append only. A run id is opaque (`run-` and ten hex characters from the hash of the definition, the subject key, and the open time), never an address or a name.
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
jason workflow --pause RUN --reason TEXT --by NAME   |   --resume RUN  |   --reopen RUN STEP --reason TEXT  |   --note RUN --text TEXT
jason workflow --cancel RUN --reason TEXT --by NAME --yes
jason workflow --verify RUN | --reindex | --from-sop KEY
```

**Added when it was built (2026-10-11):** `--attest` also takes `--outcome`, `--motion` (a decision step), and `--choice` (a branch step), and `--what`; `--arrived RUN STEP` ends a `wait` step; `--item` (repeatable) sets a run's items at `--start` or names the item on a per-item step; `--expect N` refuses if the run's last `n` has moved; `--as-of DATE` fixes the clocks for a repeatable view; `--step` goes with `--note`. `--resume RUN --by` lifts a person's pause; `--open` is the resume check. `--cancel` always needs `--yes`. `--verify` exits 1 when the chain is broken. Roles come from the community's officers and the administrators; with no officers named, a role-gated act is refused with the reason. The default readers do not yet reach the approvals engine or the job queue, so `--open` runs the check steps and leaves a `plan` or `job` step waiting.

Every write needs `--by`; `--cancel` and `--start`/`--open` of a run with a legal clock need `--yes`. Non-interactive: it never opens a browser. A command that would change a run reads it first and refuses on a changed `n` (two persons at once). The same functions are `jason.api.workflow_*` and the MCP tools `workflows` and `workflow_run` (read only, on the board profile), each with its caveats.

## 8. Loaders and writers (the web layer)

`work`, `work-run`, `work-definitions` (read) and `POST /api/write/work/<definition>/<id>` for the small acts, as [console/screens/work.md](console/screens/work.md) lists them; they call `jason.workflows.api` and add only the sign-in and the level gate. The Work and Run screens are built after `jason workflow` works.

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
- **Open:** per-step item sets for `PER_ITEM` (one list per run today); a `second` role on a step for the "2P" steps; a recorded `campaign` or `notice_key` on the run (derived today from the dates); children `owner-document` and `notice-delivery` are not defined, so `spawns` is empty.

## 11. Decisions for you

- **One file per run or one folder per definition** (recommended above: a file per run, a folder per definition).
- **The hash chain** is cheap and makes an edited record visible; it is not a signature. Keep it, or drop it as more than a local store needs?
- **Who may `--cancel`** a run with a legal clock (recommended: the secretary or the manager, with a reason, and the cancelled run stays listed for the board).
- **Whether the index is a cache only** (recommended) or the list's source.
