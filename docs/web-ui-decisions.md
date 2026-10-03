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

### The manager's core (`#/duties`, `#/calendar`, `#/money`, `#/meetings`, `#/insurance`)

The backbone is the duty anchors in [community-manager.md](community-manager.md): BPC 11500(d)'s four
management services (collect, report, and archive the finances and assets; carry out the board's resolutions;
carry out the governing documents; administer the contracts, insurance, and vendors), broken into the
seventeen duties `jason.community.duties.DUTIES` records. `#/duties` lays them out by cadence (monthly, annual,
every three years, continuous, on the event), each card naming what the duty keeps straight, its sections, the
tools that serve it, and its limit (what jason does not do); a card opens to `duty_brief`, the passages the
governing documents and the law notes give for the duty's questions.

The verbs with a store behind them each get a view:

- **Deadlines** (`association_calendar`): the obligations sorted overdue, no evidence, due soon, upcoming; each
  with its authority, rule, next date, the last time a payment showed it done, and its past deadlines. A payment
  is evidence, not proof.
- **Money**, the monthly review under CIV 5500: budget against actual with the categories furthest off and the
  balances; each bank account's reconciliation with its open items and their `reason` lead; the payments with
  questions (missing attachment, other vendor, possible double payment); and the delinquent accounts by
  standing with the board's `nextStep`, marked executive session.
- **Meetings** (`meeting_records`): each meeting's records on hand (agenda, notice, minutes, transcript,
  recording) and its checks (no minutes 30 days on, a recording held after the minutes, a transcript into
  executive session), with the scheduled days that have no record.
- **Insurance** (`insurance_review`): each policy's standing and term end, the next term's payments, the letters
  that print its number (a cancellation or non-renewal red), its findings, the terms as a timeline, and the
  claims the mail acknowledges.

### The next verbs (`#/inbox`, `#/reserves`, `#/title`, `#/hearings`)

- **Inbox** (`open_items`): what is waiting on the association, in one place: email threads awaiting a reply
  (with how often that sender was answered before, the nearest thing to a confidence number), PayHOA requests
  pending, deadlines due, insurance findings, letters to act on with the deadlines they state, mail not yet
  scanned, and lien notices. jason answers, pays, and files nothing.
- **Reserves** (`reserve_transfers`): a card per borrowing with the Civil Code 5515 record as four ticks (notice
  of intent on an agenda, minutes with the finding, a resolution, restored within a year), the restore-by date,
  repaid and outstanding, and the gaps red; then contributions against the budget, and the movements no
  schedule or loan explains. Whether the statute was met is the board's call.
- **Title watch** (`title_watch`): every recorded lien by standing, the four a person acts on first (in default,
  stands against the current owner, a prior owner's lien with no sale since, a release the association owes
  under 5685), with a namesake flag when the filing names a bare name. What the index shows, not a title report.
- **Hearings** (`hearings`): each planned hearing against the 5855 clocks (notice ten days ahead, delivered or
  due; the written decision within fourteen days), whether a meeting is scheduled, and its problems. Directors
  only; jason never sends the notice or decides.

### Books checks, legal, and runs (`#/books`, `#/legal`, `#/jobs`)

- **Books checks**: `utility_payments` (each SMUD or City payment against the bills it paid and the PDF attached,
  with findings for the treasurer) and `ledger_validation` (the treasurer's reports in the library matched to
  PayHOA's runs, and their printed balances against today's ledger: a report edited, misfiled, or re-run).
- **Legal**: `legal_cases` (each matter's open statutory duties, met, not met, or not shown; its events as a
  timeline) and `audit_chains` (the deed chain per parcel, each finding naming the next record to read).
  Confidential: executive session under CIV 4935(a).
- **Jobs** (`jobs_status`): the queue by status, each job's resource, attempts, and log tail, and who confirmed
  a write. The UI adds, runs, and cancels nothing; a write runs only because a person queued it with
  `--confirm NAME`.

### Canvases (`#/canvases`)

A canvas is the scratchpad for one topic a person is researching or preparing for board action: the work
before a board item. It holds the question, the person's notes (Markdown), **clips** (a row, a passage, or a
figure kept from a tool, with the tool and query it came from, so it can be re-read), links, a checklist, a duty
anchor, and a status (research, preparing, on agenda, done) with its history. The list is a kanban by status; a
canvas opens to its workspace. "To the board" shows the commands that turn it into a board item and a packet
section; the page runs neither. A clip is evidence a person kept, not a pin in the specification's sense. The
store is jason's own (`data/canvases/`), which is why the UI may write it.

Media by how it embeds: Google Docs, Sheets, Slides, Forms, Drive files, a Google Calendar, a published Sheets
chart, a map, and a Zoom recording embed by URL for a viewer already allowed to see them; photos, PDFs, and
audio under `data/` go through the read-only file route; Gmail and Google Tasks cannot be framed, so a thread
is a link card and the Tasks sync is read from jason's own record. The Google Picker (a live Drive and Photos
chooser in the browser) waits on a sign-in in the UI; until then the picker reads the Drive catalog and the
photo albums jason already keeps. County, recorder, assessor, permit, and statute pages mostly refuse framing
and are links.

What a canvas shows: the notes render as Markdown, with ```mermaid fences as diagrams and photos inline
(`![before](/api/file?path=photos/<album>/<file>.jpg)`); attachments show in place, a Google Doc, Sheet, Slides
deck, Form, or Drive file in Google's own preview frame (for a viewer already allowed to see it), a photo or PDF
under `data/` through the read-only file route. A picker searches the Drive catalog and the photo albums jason
already keeps, so a canvas is assembled from what the association has, not uploaded again.

### Templates (`#/templates`)

The UI equivalent of `jason templates` and `jason letter`. The letter templates are rows in the profile with
their bodies in `jason.community.templates.BODIES`, so the page lists each with its tokens sorted by who fills
them (the profile, a general citation, or the run) and, for one picked, a form for the run's tokens and the body
as it would read, rendered from `body_markdown`, the same text the Drive Doc is built from. The result is the
`jason letter --template … --set … --yes` command (a Drive copy, filled; a person runs it) and a "keep on a
canvas" that files the text as a clip. Packets (`jason packet`) and the Markdown drafts (`data/drafts/`) fit the
same pattern next: the parts and `values.json` as a form, the build as a command.

### Drafts for approval (`#/drafts`)

The bridge between the read-only views and the gated writes: a draft is shown next to the exact `--yes` command a
person would run, in a `Command` block that copies and never runs. The first is `request_links.drafts`, an
emailed request PayHOA does not have, with the form jason matched, the thread, and the message it would enter
(`jason request-links --create THREAD --yes`). The same pattern fits the agenda, minutes, hearing notice,
rule-change, and letter drafts, and the owner-information send plan.

## The board loop: present, decide, act

Everything above feeds one loop: a matter is researched (a canvas), becomes a board item, is noticed for a
meeting, goes to the board in a packet, is decided by a motion, is recorded in the minutes, and leads to an
action (a letter, a notice, a register entry, a payment, a filing). The UI covers the research and the items;
what the board sees and does needs its own screens.

### Built: the meeting (`#/meeting`)

One meeting as the board sees it: the date (the schedule's next unless chosen), the last days to give notice
(CIV 4920: four days; two for an executive-only meeting), the items proposed or on the agenda by session
(executive items by title only, CIV 4935), the agenda draft, the packet (background, the question, the law quoted,
what the records show now, options, a draft motion), the minutes frame the Secretary fills, and the commands
that write each as a Doc. Nothing is taken up that is not on the noticed agenda (CIV 4930).

### Built: motions and votes (the meeting's Decisions tab)

One `DecisionCard` per item proposed or on the agenda, and one for a motion not on an item: the motion as
made, mover and second (from the directors on file), a `RollCall` (aye, no, abstain, absent per director), the
tally with what the votes say on their face, and the outcome in the board's word (approved, denied, tabled; a
vote may stay open). Recording goes through a confirm that spells out the record. The store is jason's own
(`data/board/decisions.json`), one record per meeting and item, with history; the minutes draft quotes it
("Decisions the Secretary recorded at the meeting") instead of inferring votes from the transcript. jason
records the board's decision and decides nothing.

### Built: owner-information confirmations (`#/owner-info`)

`jason owner-info` now saves the plan it computed (each PayHOA tag write an owner's answer or election calls
for, the requests left to complete, the owners by standing) as the read artifact of its run. The page shows the
writes as a `ConfirmList`: a person enters their name and confirms each after reading the answer; the apply
command appears only when every write is confirmed, and it stays a terminal command. `ConfirmList` is the
component for every apply step that a person should look at row by row first.

### Built: rule changes (`#/rules`)

Each proposed change in the specification: the board's bracketed choices as a form (filled for the preview only;
jason never fills one), the decisions to settle with counsel first, the sections as current text from the outline
and proposed text, the Civil Code 4360 clock as a `Clock` (notice, last day for notice, agenda notice, comments
due, decision, adoption notice, reversal window) from a chosen notice date and decision meeting, and the command
that saves the member notice as a Gmail draft a person sends.

### Built: the hearing decision (`#/hearings`)

A hearing opens to its 5855 clock (notice delivered by, the hearing, the written decision due) and a card where the
board's findings and discipline are entered once, in its words, with the day decided and who recorded it, behind
a confirm; the decision is written onto the hearing's own row, and the notice deadline follows from it. The
decision notice then previews from the decision-notice template with the hearing's facts filled, naming any
token still open, with the `jason letter` command that fills a Drive copy for a person to deliver.

### Built: the rest of the inventory, one store each

Each records what a person decided beside the facts the read-only tools show, in jason's own store, and acts
outward on nothing: **registers** (`#/registers`: a local snapshot of each register, the board's columns edited
by kind and logged, pushed to the Sheet by the next sync); **delinquency steps** (`#/delinquency`: release,
payment plan, pre-lien notice, lien by roll call in open session, handoff, foreclosure authorized, written off,
each with its date, vote, and recorder, beside the standing and `nextStep`); **minutes review**
(`#/minutes-review`: the draft's blanks as a form, the privacy flags beside their lines, a filled copy saved and
the draft never edited); **insurance renewals** (`#/renewals`: renew, renew with changes, re-bid, change carrier,
or let lapse, with whether a CIV 5810 member notice is needed); **reserve findings** (`#/reserve-findings`: the
board's 5515 finding per borrowing, at the borrowing or for a late restoration, flagged where the record lacks
one); **records requests** (`#/records-requests`: each member request with its 5210 clock, whether the stated
purpose is adequate for the membership list, what is withheld and why, and when it was produced); **mail
triage** (`#/mail-triage`: scan, forward, shred, discard, or keep, recorded per letter for the person at the mail
service).

The pattern for all of them is already on the page: the facts from the read-only tools, the decision's text
entered once by a person, a preview from the same template the Doc is built from, and the command that writes.
A decision is recorded where jason already keeps it (the board's columns, a register, the minutes); the UI adds
no second place for it.

### Built: the console (`#/approvals`, `#/decisions`, `#/agenda`, `#/meeting-room`, the dock)

The design handoff of 2026-10-03 rebuilt as components and stores (`docs/web-ui.md`). What a person decides on each:

- **Approvals.** A person saves a draft jason wrote, asks the named approver, and approves in their own name; the board's approval is a vote at a meeting (CIV 4910) that the president or secretary records with the meeting date. The approved stage shows the terminal command (`jason letter … --yes`, `jason mailroom --send --yes`); a person runs it and then records where the send was logged. jason drafts and records; it sends nothing and moves no letter on its own. "Signed in as" is a sample picker over the profile's officers, not an account.
- **Plan a meeting.** A person chooses which items to include, their kind, order, minutes, motion, and packet; jason reports only computed checks (motion drafted, documents attached, executive matter marked, notice still possible) and a one-line suggestion. Putting an item on the noticed agenda and writing the Doc stay `jason board` commands; the notice is a letter drafted in Approvals; `jason zoom --create-board-meeting --date … --yes` schedules the meeting on the account, and the page fills the notice's join link and dial-in from it.
- **Decisions.** A person writes the brief (question, criteria, options, facts) and records the board's decision; jason never recommends an option, and the store refuses a body that names one.
- **Meeting room.** The chair runs the meeting and the board decides; jason records. A person records attendance, puts a motion on the floor (two different present directors, a quorum from the profile's board rule), enters each director's vote by name, and records the result: a majority of directors present, or two-thirds under CIV 4930(d)(2); a recused director counts toward the quorum and not the vote. A topic not on the agenda is logged only under one of the five CIV 4930 paths. Executive session, polls (member input only), and admissions are logged as the host's acts in Zoom; jason admits, mutes, records, and ends nothing. Draft minutes go to Approvals for the secretary.
- **Dock.** A person adds, owns, dates, and completes register tasks (completion stamps who and when). Ask answers only from sourced material and otherwise routes the question to a person as a task. A translation is a person's draft marked needs review until a fluent reviewer approves it in Approvals; the English notice controls. Scratchpad notes are working notes, not association records.
- **Board fields and owner requests.** `BoardFields` saves the board's columns behind a confirm that lists old → new, appended to the item's history. `RequestForm` records an owner's records request (CIV 5205) and shows the 5210 clock the association now owes; a person answers it.
- **Theme and the owner page** are read-only; nothing on them is decided. The brand lives in the profile (`Community.theme()`).

## Next, by what a person decides

**Drafts.** The agenda and minutes drafts (`data/board/*.md`), hearing and meeting-notice Gmail drafts, letters
from templates, the owner-information send plan and `plan_writes`, each with its command.

**Review queues.** `reply_needed` on its own with its basis, `vendor_portal`, `document_copies` candidates.

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
