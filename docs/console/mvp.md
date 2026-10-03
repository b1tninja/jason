# The first build

The MVP is:
- `jason serve`;
- the Today screen;
- the Approvals screen, carrying one kind end to end: the owner-information cycle's PayHOA tags, and the request completions that follow them;
- `jason approvals` in the CLI, read-only approvals tools in `jason-mcp`, and the audit log.

Every criterion below is a test, or a check a person makes once. A criterion names the function it relies on.

## Prerequisites in jason

The build depends on these changes outside the console. Each comes from reading `commands/owner_info.py`, `tasks/owner_info.py`, and `tasks/owner_responses.py` as they are today.

1. **One live read, in a task.** `_answers`, `_rows`, and `_live` live in `jason.commands.owner_info`, and `owner_responses.contexts` imports `_live` from there: a task importing a command.
   - They move into `jason.tasks.owner_info` as `read_live(client, org, data_dir, community, forms, *, payhoa) -> Snapshot`, holding units, people, answers, the ledger rows, and the contexts.
   - `contexts` takes the snapshot's units and people instead of reading again.
   - One plan then reads PayHOA once. Today it reads three times: `_apply`'s read, and two `contexts` calls.
2. **A result for each item from `execute`.** `owner_info.execute` returns counts, and a failure part-way through loses which writes were made. It needs `on_item(write, ok, detail)` (or a list of results returned) so the audit can record each write.
3. **The writes not applied stay pending.** `_apply` sets `writes = []` after `execute`. With item approval, `_complete_requests` (and the adapter) must receive the writes not applied, so `to_complete` keeps those requests open.
4. **Stable ids and bases.** The adapter computes `PlanItem.id` from `Write(kind, target, value)`. It computes `basis` from the snapshot: a member's `tag_names(person)`, a unit's `tag_names(unit)`, and a submission's status and answers ([approval-workflow.md](approval-workflow.md#fingerprints)).
5. **The rule behind each write, as a citation.**
   - `plan_writes` gives `why` in words.
   - The adapter adds `rule`:
     - `CIV 4040(a)(2)` for the default delivery tag;
     - the earlier-elections rule row for an earlier written election;
     - the response policy's `delivery` row for a this-cycle answer.
   - A completion cites the board's owner-information rule row.
6. **Profile access by the current names.** `_complete_requests` calls `mystique()` and `cmd_owner_info` calls `spec_module`. The adapter uses `community()` and the profile's forms through `Community`, as AGENTS.md asks of new code.
7. **`--by` on the CLI's apply.** `jason owner-info --apply --payhoa --yes --by NAME` names the person for the audit log. Without `--by`, the operating-system user is recorded.
8. **Registering `jason serve` and `jason approvals`** in `src/jason/cli.py`: one line each.

## `jason serve`

- [ ] `jason serve` starts uvicorn on `127.0.0.1:8770`, and `--port` changes the port. There is no option to bind another address.
- [ ] It prints the sign-in link once, with the token in the URL fragment. `--open` opens the browser on it. `--print-token` prints it again while running. `--rotate` makes a new token and ends every session.
- [ ] A request with a `Host` other than `127.0.0.1:<port>` or `localhost:<port>` gets 421. A non-loopback peer is refused.
- [ ] Every route but `/login` and `/static/` redirects to `/login` without a session, or returns 401 for JSON.
- [ ] `POST /login` with the token sets `jc_session` (`HttpOnly; SameSite=Strict`). A second exchange of the same token is refused.
- [ ] Every POST without the session's CSRF token, with a foreign `Origin`, or with `Sec-Fetch-Site: cross-site` gets 403 before its handler runs.
- [ ] No GET changes `approvals.db`, `audit.jsonl`, or any store. A test walks every route to check.
- [ ] Every response carries the CSP and the other headers in [security-and-privacy.md](security-and-privacy.md#where-it-listens). Pages with member data carry `Cache-Control: no-store`.
- [ ] After sign-in, the person picks who they are acting as, and their role, from the roster (the private facts). The header shows it.
- [ ] The `jason-console` entry in `.claude/launch.json` starts it ([architecture.md](architecture.md#launch-configuration)).

## Today

- [ ] It renders `api.governance_digest(limit=8, private=True)`, one section per system, most urgent first. Each line has its urgency badge (`LEGAL` as a legal deadline badge), its text, its due date, and its command.
- [ ] A section whose store is missing is shown as unavailable, with its `error`. The page still renders.
- [ ] It shows the waiting approvals: the count, the oldest first, and those waiting on a second person apart.
- [ ] It shows the top five of `api.next_questions()`, each linking to Onboarding to answer.
- [ ] It shows running work (`runner` jobs, `jobs.jobs`, `batches.batches`, `locks.holders()`), and each store's freshness with its refresh command.
- [ ] With the private view off, no unit or owner name appears in the digest. This is the `private=True` rendering.

## Approvals: the owner-information kind, end to end

### Plan

- [ ] On Approvals, "Plan: owner information (PayHOA)" starts a `runner` job on the `payhoa` class. It holds `Resource.PAYHOA` for the read, and reads PayHOA live once (prerequisite 1).
- [ ] Without a Keeper session, the job fails fast with "run `jason login` in a terminal". The browser never shows a credential field.
- [ ] The job stores one `Approval` of kind `payhoa.owner-info.tags`, with:
  - `requested_by` the acting person, `requested_via: "console"`, `read_at`, and `fingerprint`;
  - `scope: {"payhoa": true, "cycle": <the cycle's year>}`;
  - **approvable** items, one per `Write` from `plan_writes`, each with id, basis, why, rule, and evidence (the ledger row, and the PayHOA submission for an answer);
  - **held for the board** items: the unit occupancy writes `_apply` holds today (a `triage` finding with `Outcome.BOARD` and rule `occupancy-vs-tag`), each with its `Finding.text` and `board_item`;
  - **for a person** items: each `to_complete(...).left` entry that names a person's entry (`FOR_A_PERSON`, `PERSON_FIELDS`), and each `Outcome.PERSON` finding;
  - **confirm with the owner** items, from each `Outcome.CONFIRM` finding;
  - **completion** items (`payhoa.owner-info.complete`, approver `BOARD_RULE`). There is one for each pending request whose `left` would be empty once its writes apply. Each has `depends_on` set to those writes, and the comment text (`OWNER_INFO_COMPLETED_COMMENT`, read through the profile) shown in full, because it is emailed to the owner;
  - **informational** items: each pending request that stays open, with its `left`.
- [ ] No item targets a test membership (`config.test_memberships`). Their count is shown as "test accounts left out: N".
- [ ] A newer plan of the same kind and scope supersedes any open one.

### Review

- [ ] `/approvals/{id}` shows the header: kind, status badge, planned by jason, requested by, the read time, the fingerprint's first 12 hex, and the cycle's nearest deadline (`summary(...)["deadlines"]`).
- [ ] Items are grouped by owner (member and unit). Each row shows the change, before and after, why, the rule as a short citation opening its recitation (`api.cite_document`), and the evidence chips.
- [ ] Held items are in a "Held for the board" section with the held banner. Items for a person and items to confirm with the owner are in their own sections. **None has a checkbox**, and no request or form field can approve one: the server refuses an item that is not `APPROVABLE`.
- [ ] Owners' names are shown (P1). Emails and mailing addresses in the evidence are masked (P2), and a reveal is logged by field kind.
- [ ] The cost summary says "No charge: PayHOA tag changes and request status".

### Decide and submit

- [ ] Each approvable item can be approved, rejected (reason required), or held for the board (reason required). "Approve all approvable" sets each one, and each is logged as its own decision.
- [ ] Decisions save as they are made. The approval moves to `in review`, and leaving and returning keeps them.
- [ ] A completion item whose writes are not all approved shows "will stay open". It cannot be approved: its approval is refused with the writes it waits on.
- [ ] Submit posts the name (pre-filled with the acting person), the fingerprint, and the CSRF token. The result is `approved` if every approvable item is approved, else `partially approved`. With none approved, it is `withdrawn` ("nothing approved").
- [ ] A person's hold proposes a board item through `tasks.board_items.propose`, signed with the name. The approval links it.

### Re-plan and fingerprint check

- [ ] "Apply" runs a `runner` job holding `Resource.PAYHOA` for `approval-<id>`. It re-reads live and re-plans with the same scope.
- [ ] If any approved item is missing, has a different basis, or is now held: **nothing is written**. The approval becomes `superseded`. A new approval is made from the re-plan, showing the earlier decisions as hints but not counting them. The page shows the changed-since-review banner, with both fingerprints and the changed items.
- [ ] Items new in the re-plan do not block an apply. They are listed as "new since review, not included".
- [ ] The test: change one approved member's tags in the fake client between submit and apply. The apply refuses, writes nothing, and the audit has `apply.refused` with that item.

### Apply

- [ ] Only approved items are written, through the adapter calling `owner_info.execute` (with prerequisite 2) for tags, and `owner_info.complete` for completions.
- [ ] Each write logs `item.applying` before its request and `item.applied` or `item.failed` after it. A write with no answer back is `uncertain`.
- [ ] A completion is applied only when every write it depends on is `applied`, and `to_complete` (with the writes not applied as pending) leaves it nothing. Otherwise it is `blocked`, and its request stays open.
- [ ] The approval ends `applied` (every approved item applied) or `failed` (each failure with its error). A failed write is never retried automatically.
- [ ] The result panel replaces the approve bar, with the counts and lists (`role="status"`).

### Audit

- [ ] `data/console/audit.jsonl` has one line for each event in [approval-workflow.md](approval-workflow.md#9-the-audit-log), each with `prev` and `hash`.
- [ ] `jason approvals audit --verify` passes on an untouched log, and names the first broken line after a hand edit.
- [ ] No line holds an email, a mailing address, an account number, or a token. A test scans the log after the end-to-end run for `@` and long digit runs.
- [ ] The approval page's audit timeline shows its events in order.

### Parity

- [ ] `jason approvals`, `show`, `decide`, `submit`, `apply`, and `audit` work on the same records the console made, and the reverse holds too. A plan made in the CLI can be approved in the console.
- [ ] `jason-mcp --profile governance` lists `approvals_list`, `approval_show`, and `approval_audit`. No MCP tool decides, submits, confirms, or applies.
- [ ] `jason owner-info --apply --payhoa --yes [--by NAME]` still works as today, and now writes the same audit lines with `via: "cli"`.

## Non-functional

- [ ] All MVP pages pass the HTML accessibility checks in [architecture.md](architecture.md#testing). A person does a keyboard-only pass of plan, review, submit, and apply, and a screen-reader pass of the approval page.
- [ ] Nothing in `src/jason/console/` or `src/jason/approvals/` names an association fact. The boundary test covers both folders.
- [ ] The test suite runs with no network, no Keeper, and no Google token.
- [ ] The pages render with the network unplugged, apart from the plan and apply jobs, which fail fast and say so.

## Moving the CLI's `--yes` paths onto approvals

The CLI keeps working at every step. Each step is a change to one kind at a time, made when its planner and applier exist.

| Step | What changes | `--yes` then means |
|---|---|---|
| **1. Audit everything** (MVP) | Every `--yes` path writes `approval.applied`-style lines to the audit log, with `via: "cli"`, the person from `--by` or `--confirmed-by`, else the operating-system user, and a fingerprint of what it wrote. Paths not yet in the registry log at least the kind (the command) and the counts | What it means today, now on the record |
| **2. Plan and apply through the engine** (each kind in phase 3) | The kind's planner and applier exist. `jason <command> --yes --by NAME` becomes sugar: plan, approve every approvable item as NAME, submit, apply, in one run, with the same re-plan check. `--by` becomes required for R2 kinds | "I approve all of this plan", recorded as an approval |
| **3. Two people where the registry says so** (phase 4) | A 2P kind refuses a bare `--yes`. The command takes `--approval ID` instead, and applies only an approval with both signatures. Examples: `jason mailroom --send --approval ID`, `jason owner-info --email-batch --approval ID` | Not accepted for 2P kinds |
| **4. Jobs carry the approval** | `jason jobs add --confirm NAME -- approvals apply ID --by NAME`. The worker runs approvals by id, never a bare `--yes` | — |
| **5. Retire bare `--yes` for R2 and R3** | `--yes` stays for R0 and R1 (local and private) with `--by`. R2 and R3 go through an approval, from the console or the CLI | R0 and R1 only |

The survey's ungated writes are treated first in step 1, given a dry run and a registry row:
- `board --sheet`;
- `board --create-sheet`;
- `board --tasks`;
- `property-history --sheet`.

## Open decisions

For the person deciding the build:

1. **Templates.** Add `jinja2` (autoescaping, macros match the UI library) as the one new dependency, or build a small escaping HTML builder with none ([architecture.md](architecture.md#stack))? Recommended: Jinja2.
2. **A change at apply.** Refuse the whole apply when any approved item changed, as specified, or apply the unchanged items and re-plan only the rest? Recommended: refuse the whole apply. A person reviewed a picture, not a list of independent lines.
3. **Which kinds need two people.** As proposed: Mailroom sends, email and mail batches, publishing a Google Form, Vault holds, scheduling a hearing, switching a document's reading, and a PayHOA form update that changes an answered question. Should completing an owner-information request, which emails the owner the board's comment, be one person (as proposed, under the board's rule) or two?
4. **The roster and roles.** Who holds which role, and is that a board decision to record as a rule row? Until sign-in, is a self-asserted name at the manager's machine acceptable for first signatures?
5. **Plan age.** Is 24 hours the right `max_age` before a plan must be read again, for every kind, or shorter for sends?
6. **A person's hold.** Should "hold for the board" propose a board item automatically (as specified), or only note it for the manager to add?
7. **MCP.** Should the approvals tools stay read-only, as specified, so an assistant can explain a plan but never act on one?
8. **The audit log.** Is a hash-chained local file enough, or should each day's last hash also go somewhere a person keeps apart from this machine, such as the board's records?
9. **Port.** 8770, or another free port.
10. **Remote access.** Out of scope until the board adopts a written policy on who may see what. Confirm that it stays out.
