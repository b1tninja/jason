# Information architecture

The console's navigation, and each screen's data source and actions. Every source below already exists. Most are `jason.api` functions, which are the governance MCP tools (`jason.mcp.governance`), and the board tools in `jason.mcp.county`. The rest are task functions the CLI calls. A screen calls the function and renders what it returns. It never re-derives a fact on its own.

This page names each screen's sources and actions. The detail lives elsewhere:
- each screen's layout, wireframe, and states: [screens/](screens/);
- the paths a person takes through the screens: [journeys.md](journeys.md);
- the words on screen: [content/style.md](content/style.md) and [content/patterns.md](content/patterns.md).

Rules every screen keeps:
- **Read from disk unless the user asks for live.** A screen reads the stores on disk, as `jason-mcp` does. Reading live is an explicit action that runs as a job ([architecture.md](architecture.md#long-work-jobs-and-progress)): an owner-information plan, a sync.
- **Each screen names its CLI equivalent.** Every section shows the command that gives the same detail, as `attention.Item.command` does today. A person can always check the console against the terminal.
- **Each screen shows its freshness.** It shows when the store was last synced (`catalogSynced`, `syncedAt`, `lastModified`) and the command that refreshes it.
- **A missing store is a miss.** The screen shows the section as unavailable, with the reason (`attention.Section.error`). It never shows it as empty.
- **Recite first.** Wherever words of a document or statute appear, the recitation block comes first, then jason's reading under a reading label ([components.md](components.md#text-and-data)).

## Navigation

A left rail on wide screens, and a menu button under 768 px. Its order is the manager's day:

```
Today
Approvals            (count waiting; a second count waiting on a second person)
Members & units
Requests             (count past a clock)
Notices
Meetings & minutes
Governing documents
Schedule & duties
Records & library
Finance
Onboarding           (shown while a stage gate is closed)
Settings
```

The page header carries:
- the active profile's name, from the profile and never hard-coded;
- the acting person and role;
- the private-view switch, which is off by default and logged when turned on;
- a link to the audit log.

## Addresses

| Path | Screen |
|---|---|
| `/` | Today |
| `/approvals`, `/approvals/{id}` | Approvals, and one approval |
| `/members`, `/members/units/{unit_id}` | Members & units, and one unit |
| `/requests`, `/requests/{id}` | Requests, and one request |
| `/notices`, `/notices/{key}` | Notices, and one notice: the `jason://notice/KEY` record |
| `/meetings`, `/meetings/{date}` | Meetings & minutes, and one meeting |
| `/documents`, `/r/{address}` | Governing documents, and one `jason://` address (`/r/decl/6.2(a)` is `jason://decl/6.2(a)`) |
| `/cite?q=` | The cite box: any expression `jason cite` takes |
| `/schedule` | Schedule & duties |
| `/records` | Records & library |
| `/finance` | Finance |
| `/onboarding` | Onboarding |
| `/settings` | Settings & profile |
| `/audit` | The audit log |

A query string carries only filters, never a person's name, email, or address ([security-and-privacy.md](security-and-privacy.md#urls)).

## Today

The manager's first screen: what needs a person now.

| Part | Source | Actions |
|---|---|---|
| Waiting approvals: the count, the oldest first, and each one's kind, items, held count, and age | `jason.approvals.store.pending()` (new, [approval-workflow.md](approval-workflow.md)) | Open |
| The attention digest, one section per system, most urgent first: `LEGAL`, overdue, due soon, open, noted | `api.governance_digest(limit=8)` → `attention.digest`. Its sections are meetings, requests, schedule, people, notices, living, conflicts, duties, and intake | Open each line's screen. Copy its command |
| The next questions, ranked by what each answer unblocks | `api.next_questions(limit=5)` | Answer, in Onboarding |
| Running work: jobs, batches, and who holds a lock | `jobs.jobs(data_dir)`, `batches.batches(...)`, `locks.holders()` | Open a job's log |
| Freshness: each store's last sync | Each section's `counts` and `notes`, plus the catalog's `synced` | Copy the refresh command |

Private view off: the digest is read with `private=True`, so units are left out and task titles are replaced by their rule's label.

## Approvals

The core screen ([approval-workflow.md](approval-workflow.md)).

| Part | Source | Actions |
|---|---|---|
| The queue, filtered by status, kind, and who it waits on | `jason.approvals.store.list(status=..., kind=...)` | Open. New plan, per kind, which starts the kind's planner as a job |
| One approval:<br>- the header: kind, requester, when, the plan fingerprint, the live read's time;<br>- the items as diff rows grouped by target, each with its reason, its rule recited, and its evidence chips;<br>- the "held for the board" section and the "for a person" section (never approvable);<br>- the cost summary;<br>- the second-person state;<br>- the audit timeline | `Approval` and its `PlanItem`s; the kind's `ActionKind` row; `cite_document` for each item's rule; the audit log filtered by approval id | Approve or reject each item. Approve all approvable. Submit, with a name. Second-person confirm. Re-plan. Apply. Withdraw |
| The audit log | `jason.approvals.audit.read(...)` | Filter, and verify the chain |

## Members & units

Who owns what, how notices reach each owner, and where each owner stands in the cycle.

| Part | Source | Actions |
|---|---|---|
| The owners table: unit, owner, the owner-information status (`OwnerStatus`), how notices go now, the latest answer, and the next action | `owner_info.ledger(...)` with `owner_info.summary(...)`, from the stored catalog. The command builds its rows in `commands.owner_info._rows`; the console needs that moved into `jason.tasks.owner_info` first (see [mvp.md](mvp.md#prerequisites-in-jason)) | Filter by status. Open a unit. Plan the cycle's writes, which creates an owner-information approval |
| The cycle's deadlines | `summary(...)["deadlines"]` (`AnswerCycle.deadlines`) | — |
| Delivery totals: by broadcast, by Mailroom, and what is left | `notice_delivery.plan(units, people, tags)` (`jason delivery`) | Plan the delivery tags (`delivery --audit --apply`, a phase 3 kind) |
| One unit: title, chain, liens, taxes, members, value | `unit_brief`, `ownership_record`, `party_brief` (`jason.mcp.county`) | — |
| New owners | `new_owners` | — |
| The response triage for one owner's answer: findings by outcome | `owner_responses.triage(context)` over `owner_responses.contexts(...)`, read live (a job) | None. A board finding links its board item, and a person finding is a task for a person in PayHOA |

Owners' names are P1. Emails and mailing addresses are P2: masked, and revealed on request.

## Requests

Members' requests and their clocks (`jason respond`).

| Part | Source | Actions |
|---|---|---|
| Open requests, most urgent first: kind, received, clock, due, standing, the role that owns it, and the next step | `api.member_requests(open_only=True)` → `responses.handle` | Filter by kind or standing. Open |
| Answered requests, and on-time rates by kind | `api.member_requests(open_only=False)` | — |
| One request: the thread, PayHOA's fields, the clock with its authority recited, and the leads to the answer (`--sources`) | `member_requests`, `responses.payhoa_fields`, `response_sources`, `cite_document` for the clock's statute | Draft the acknowledgment (`api.acknowledgment_draft`), shown for a person to read. Save it as a Gmail draft (a phase 3 kind, `gmail.draft.ack`) |
| Emailed requests PayHOA lacks | `request_links.request_links(data_dir, community)` | Enter one in PayHOA (a phase 3 kind, `payhoa.request.create`) |

No approve, deny, or assign control exists on this screen, ever.

## Notices

Each notice from its requirement to its proof.

| Part | Source | Actions |
|---|---|---|
| The notice catalog: what the law requires of each kind | `api.notice_requirements()` | Open |
| The notices in the ledger: each one's members reached, follow-ups owed, and last sync | `notice_ledger.notices(...)`, `notice_ledger.standing(...)`; the `notices` section of the digest | Open. Sync (a job: `jason notices KEY --sync`) |
| One notice, `jason://notice/KEY`: the requirement recited, the text as sent with its sha256 and whether it changed since, the fill records, the recipients plan, delivery by member, the follow-ups, and the proof | `notice_record.build(key)`, `api.notice_delivery(key)`, `notice_proof.build(...)`, `api.read_record("jason://notice/KEY")` | Plan a follow-up: an email bounce resent by mail is a Mailroom kind, which is phase 4 |

## Meetings & minutes

| Part | Source | Actions |
|---|---|---|
| The meeting watch: each board meeting's notice clock (4920) and minutes clock (4950(a)), and what is on record (`meeting_watch.Standing`) | `meeting_watch.watch(community, data_dir)`; the digest's `meetings` section | Open a meeting |
| One meeting: agenda, minutes copies, transcript, recording, and summaries | `meeting_records(date=...)`, `zoom_meetings` | — |
| A minutes draft with its checks: quorum, the directors on the call, gaps left for the Secretary, and confidential subjects | `data/board/minutes-draft-<date>.md`; `minutes_draft.checks(...)` and `minutes_draft.check_lines` | Re-check (`minutes_draft.recheck`). Drafting it is a GPU job |
| Record stages: rule changes through 4360 (28 days, then 15 days, then 4365's 30 days), and minutes with their approvals | `record_stages.histories(community, data_dir)` | — |
| Board action items, and the draft agenda | `board_items` (MCP), `tasks.board_items.agenda(...)` | Write the agenda Doc (a phase 3 kind, `google.doc.agenda`) |
| Hearings | `hearings` | Schedule on Zoom (a phase 4 kind, `zoom.hearing.create`) |

Executive-session material is listed by date only, outside the private view.

## Governing documents

The reader and the cite box. This is the manager's law library.

| Part | Source | Actions |
|---|---|---|
| The cite box: any expression `jason cite` takes | `api.cite_document(expression, as_of=...)` | Copy the citation. Copy the address |
| A section as a sheet: the recitation (the words whole, the citation, the version in force, the caveat), then the address, the permanent id, the defined terms, the history, what it cites, and what cites it | `reader.sheet(...)` (HTML) or `api.read_record(address)` (Markdown); `api.section_refs(expression, direction="both")` | Open a reference. Show it as of a date |
| The documents kept living, each with its rule checks, held sources, and drift | `api.living_document()`; the digest's `living` section | — |
| A section's revisions: versions, sightings, and adoptions on record | `revision_detection.history(...)`, `section_history(...)` | — |
| The owner's manual: its classification (rule, copy, policy, guidance), the concordance, and the rendered official rules with the diff | `manual.classify(...)` outputs in `data/manual/KEY/`; `data/drafts/` | — |
| Conflicts (Civil Code 4205): each row with the authority above it, the part that yields, its status, and its board item | `api.document_conflicts(leads=...)` | — |
| The documents' duties, and embedded copies | `api.document_duties(key)`, `api.embedded_copies()` | — |

Restricted books (`exec`, `members`, `ballots`) are listed by name only. A read is refused unless the private view is open. This is the `jason cite --private` rule.

## Schedule & duties

| Part | Source | Actions |
|---|---|---|
| What falls due: by role, with each item's standing (done, overdue, due soon, upcoming) | `api.schedule_agenda(days=60, role=...)` | Record done (`api.record_completion(key, due, by, evidence)`): a `data/` write signed by name, with no approval needed |
| Assignments: role, backup, clock, evidence, command | `api.schedule_assignments()` | — |
| Coverage: the duties no assignment covers | `schedule.coverage(...)` | — |
| People's own tasks and events beside what jason tracks | the digest's `people` section (`people_tasks`) | — |
| The association calendar | `association_calendar` | Put on Google Calendar (a phase 3 kind, `google.calendar.schedule`) |

## Records & library

| Part | Source | Actions |
|---|---|---|
| The library: counts by kind, and what waits for a kind | `library_status`, `library_search(kind=..., words=...)` | Search. Open text (`library_text`) |
| The Civil Code 5200 records inventory, and where each is kept | `records_inventory`, `association_records`, `record_locations` | — |
| An ingest's report: files, duplicates, proposed book, record, and folder | `data/onboarding/ingest-<day>.md`; `ingest.inventory(...)` | Park the questions. Apply: copy into the library, a `data/` write and a phase 3 kind (`local.ingest.apply`) |

A confidential file is held back unless asked for, as `library_search(include_confidential=False)` does by default.

## Finance

Read-only throughout. Amounts are integer cents, shown as dollars.

| Part | Source |
|---|---|
| Budget against actual, and the variances | `budget_status(year)` → `finance.finance_summary` |
| Bank balances, named from the specification, with account numbers by last four | `bank_accounts` |
| Reconciliations | `bank_reconciliations` |
| Reserves: the study, the funding plan, and transfers | `reserve_study`, `reserve_transfers` |
| Invoices checked against payments | `invoice_review` |
| Collections and liens | `association_collections`, `assessment_liens` |
| The general ledger's reports | `books_report(report=...)` |
| Utility costs | `utility_brief`, `utility_payments` |

The refresh is a PayHOA job (`jason budget`, `jason books`). Each panel shows its snapshot's `syncedAt`, and the note that Plaid balances are confirmed on the bank's statement.

## Onboarding

Shown in the navigation while any stage gate is closed (`onboarding.GATES`). After that, it is under Settings.

| Part | Source | Actions |
|---|---|---|
| The stage gates: start, ingest, establish, operate, adopt. Each shows open or closed, the items it waits for, and its checks | `api.onboarding_status()` → `onboarding_session.build`, `GateResult.open`, `GateResult.evidence` | — |
| Checklist progress by group | `onboarding_status()["groups"]` | Filter by group or status |
| The next questions, ranked by what each answer unblocks | `api.next_questions(limit, group, stage)` | Answer (`api.answer_intake_question(id, text, by)`). A secret is refused with `SecretRefused`'s message, and nothing is kept |
| High-stakes answers waiting for a second person | `api.intake_questions(awaiting_confirmation=True)` | Confirm (`api.onboarding_confirm(id, by)`), refused for the same name |
| Proposals: profile patches under `data/onboarding/proposals/` | the files | Read. Applying a patch stays a person's `git apply` |

## Settings & profile

| Part | Source |
|---|---|
| The active profile, its data folder, and the private-facts topics (paths only, never values) | `jason.community.community()`, `config.data_dir()`, `jason spec`'s listing |
| The roster: names and roles for "acting as" | the private facts (`private.facts(profile)`) |
| Connections: whether a Keeper session, a Google token, and a PayHOA session are present (yes or no only), and the command to fix each | `KeeperAuthRequired` and `GoogleAuthRequired` caught on a probe |
| The local model stack, and lock holders | `local_ai` report, `locks.holders()` |
| The action-kind registry, read-only: each kind's risk, approver rule, and reversibility | `jason.approvals.registry.KINDS` |
| The console's own session: token rotation, and sign-out | [security-and-privacy.md](security-and-privacy.md) |
