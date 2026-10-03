# Where jason needs a person: the UI's map

A survey of the tasks where jason stops and a person decides, or where a person would be helped by a review
queue, a preview, or a dashboard. It names the tool or command behind each, the shape it returns, and the UI
component that fits. It is the plan for [web-ui.md](web-ui.md); the first four areas are built.

The rule under all of it, from [mcp.md](mcp.md): **the tools decide nothing.** A reading, a match, a gap, or a
related item is a lead, not a pin and not a finding. Every write to Google, PayHOA, Zoom, or Vault is a dry run
until a person passes `--yes`, and the job queue runs a write only with `--confirm NAME`. The UI keeps that: it
shows, it lets the board fill its own columns, and for anything else it shows the command a person would run.

## Shapes the tools share

These recur across the read-only tools, so one component serves each:

| Shape | Where it appears | Component |
|---|---|---|
| `{found: false, note\|hint}` | nearly every tool with an empty store | `RemoteView` shows the note as the empty state |
| `caveats: string[]` or `note` | digests, reviews, calendar, title watch | `Caveats`, always visible |
| `findings: string[]` with `ok`, or `gaps: string[]` | invoices, utilities, reconciliations, inventory | `Findings` |
| `{standing, meaning}` | title, collections, solar, calendar, insurance | `Pill` (word plus meaning on hover) |
| `...Cents` | everywhere | `Money` |
| `due`, `next`, `deadline`, `daysLeft`, `ageDays` | board items, calendar, hearings, threads | `DueDate` |
| `evidence[]`, `documents[]`, `path`, `link`, `how` | board items, reviews, copies | `Evidence` |
| dated steps or instruments | lifecycles, governing instruments, terms | `Timeline` |
| a status word per row | board items, jobs, batches | `Kanban` |
| anything that writes | the board's columns today | `Confirm` (two clicks, with the change spelled out) |

A confidence number is rare (the form reader's per-field `confidence`, the library's per-file score). Most
provenance is a method word (`name rule`, `phrase rule`, `model`), so a badge takes a number, a label, or a method.

## Built

### Board action items (`#/board`)

`board_items` → `BoardItem`: jason's columns (title, summary, ask, category, priority, authority, evidence,
session, due) and the board's (status, owner, meeting, notes). The view is a kanban by status with a card per
item; its details open the board's four fields. Saving goes through `Confirm` and `POST /api/board-items/<id>`,
which calls `tasks.board_items.set_fields`, the same code as `jason board --set`, and refuses any other field.
This is the UI's one write.

### Association records (`#/records`)

`records_inventory`: each Civil Code 5200 record with its citation, retention, where the specification keeps it,
how many files are there, and its gap. `association_records`: the governing instruments as a timeline and table,
the developer deliveries with what is found and missing, liens the association placed, filings against it, and
unplaced instruments.

### Document ingestion (`#/ingestion`)

`library_status`: files by classification method and by kind, the records covered, and the unclassified list.
`document_readings`: what each recorded copy's text says about itself (number, recording date, phase, pages,
unsigned or unrecorded copy), with the unreadable files listed.

### Leads (`#/leads`)

`/api/leads` gathers, in one shape (`source`, `kind`, `title`, `detail`, `next`), everything the stores show that
no person has pinned: unclassified library files, records gaps, supersessions the text states and the
specification does not pin, missing developer deliveries, and unplaced instruments. A source that cannot be
read is a note, not a crash. The caveat is on the page.

## Next, by what a person decides

**Review queues (a treasurer or manager works a list).** `invoice_review` and `utility_payments` (payments
with findings and the attachment beside them), `bank_reconciliations` (open items with a `reason` lead and an
age), `ledger_validation` (printed against ledger), `title_watch --attention` (the four standings a person acts
on), `association_collections` (grouped by standing with `nextStep`), `open_items` and `reply_needed` (an inbox).
Table with facets, expandable rows, `Findings`, `Pill`, `DueDate`.

**Compliance records (the board judges whether a statute was met).** `reserve_transfers` (a card per borrowing
with the 5515 documents ticked and `gaps` red), `association_calendar` (obligations by standing with history),
`hearings` (the 5855 clocks), `meeting_records` (checks per meeting), `insurance_review` (terms and findings).
Checklist plus `Timeline`.

**Drafts for approval (a person reads, then runs the command).** `request_links.drafts` (a proposed PayHOA
request per thread), agenda, minutes, hearing and rule-change drafts, letters from templates, Gmail drafts, the
owner-information send plan and `plan_writes`. A diff or Markdown view with the exact `--yes` command to copy;
the UI never runs it.

**Candidates and matches (a person confirms one).** `expand_deed_anchors.contested`, `compare_parties`,
`copies.candidates`, the form reader's per-field readings. Side-by-side with a confidence badge and accept or
override, writing back only where a CLI already writes.

**Runs (progress a person watches).** `jobs_status` (lanes by status, log tail, who confirmed a write) and the
batch ledger (`sent` of total, `uncertain` items a person resolves with `--resolve`). `Kanban` and a progress
bar; cancel and resolve stay CLI until the UI has a login.

## What the UI will not do

It does not approve, deny, or assign a PayHOA request; submit an account to collections; mail, email, or
broadcast; delete a form; release a hold; or run a `--yes` command. Those stay with a person at the terminal, as
[AGENTS.md](../AGENTS.md) says. The server binds to loopback and has no login, so nothing beyond the board's
columns is written until it has one.
