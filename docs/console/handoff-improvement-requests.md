# Handoff: home improvement requests, the board stage, the owner's unit, and what the unit's record serves

For the design pass on the components that carry **a home improvement request from receipt to the unit's manual**, **the board stage it passes through**, **the owner's view of their unit**, and **two outputs and one view the record serves**: the owner's resale summary, the owner's insurance schedule, and the association's original-or-upgraded view at a loss. The behavior, the law, the policies proposed for the board, and the records are settled in [../improvement-requests.md](../improvement-requests.md). The unit's manual, effective record, and loss packet are in [../unit-records-design.md](../unit-records-design.md) and [../unit-records-backend.md](../unit-records-backend.md); the earlier handoff for them is [handoff-unit-records.md](handoff-unit-records.md). This page is what the design needs: the components, their states, sample data, what the design must keep, the delivery decision for the owner's view, and the decisions it is asked to make.

**What exists today.** `jason respond` reads each PayHOA request and email as a kind (`architectural application`, `solar application`, `EV charger application`, and others) with a clock and a next step. The board loop is built: board items (`#/actions`), the agenda wizard (`#/agenda`), the meeting room's motions and roll call (`#/room`), recorded decisions (`#/decisions`), and letters through their stages (`#/approvals`). The unit's record has three reads and three writes built (`/api/facts`, `/api/unit-record`, `/api/loss-packet`; an entry, its visibility, a packet step's confirmation). **No screen shows a request as an improvement, and no loader joins a request to a unit's manual.** The requests screen ([screens/requests.md](screens/requests.md)), the members-and-units page ([screens/members-and-units.md](screens/members-and-units.md)), and the unit record ([screens/unit-record.md](screens/unit-record.md)) are specified and not built. The console is loopback-only on the manager's machine ([security-and-privacy.md](security-and-privacy.md)): **it is not an owner portal.**

The words on screen follow [content/style.md](content/style.md), the patterns [content/patterns.md](content/patterns.md), and the components [components.md](components.md). Neighbours this page links to and does not repeat: [screens/board-items.md](screens/board-items.md), [screens/meetings-and-minutes.md](screens/meetings-and-minutes.md) (the agenda, the room, the roll call), [approval-workflow.md](approval-workflow.md#12-the-board-decides-by-vote) (the board decides by vote), [screens/community-facts.md](screens/community-facts.md) (the facts an owner reads), [handoff-applicability-questions.md](handoff-applicability-questions.md) (the three-valued answer used for "does it need approval"), and [handoff-confirmations-queue.md](handoff-confirmations-queue.md) (a person's signed confirmation that adopts nothing).

## The idea in one line

A request is a record with a state, each state names the person who moves it and the clock that runs in it, the board decides by a vote a person records, and when the work is done the unit's manual links to the approval; the owner sees their own requests and their own manual, the association sees what it has itself been given, and nothing says a change is safe, lawful, insured, or worth what it cost.

## Four surfaces

| | Surface | Audience | Where it lives | Real now |
|---|---|---|---|---|
| (a) | The review and the board stage | manager, committee, directors, secretary | a band of `#/requests?id=`, then the existing board screens | specified; the board screens it composes with are built |
| (b) | The owner's unit view | the owner | a document and the PayHOA request thread now; the console's owner view as the manager's preview; an owner-facing surface later | the document and the thread, by hand |
| (c) | The owner's resale summary and insurance schedule | the owner, who chooses what to share | outputs of (b) | not built |
| (d) | The original-or-upgraded view at a loss | manager, directors, counsel | the loss packet's first step and the unit record's tab | the packet is built; the improvement evidence is not |

## What is real now: delivery of the owner's view

The console serves 127.0.0.1 only, and Sign in with Google admits the roster's Workspace accounts, not owners. An owner cannot open a console page. The design therefore decides the delivery, and says what is real.

| Channel | Real now? | What jason does today | What it cannot do | Used for |
|---|---|---|---|---|
| The console's owner view (`?view=owner`) | Yes, on the manager's machine only | Serves the owner loaders' allowlisted fields; every read carries `view=owner` | An owner cannot reach it; there is no owner sign-in | The **preview** a manager checks before anything is delivered, and a screen at the desk |
| PayHOA's owner portal | Yes: it is the owners' portal | The architectural request form (a title, a message, an optional file); the owner sees their own submissions, status, and comments. jason reads submissions, edits a live form in place (`jason forms --payhoa KEY --update`), posts a comment (ungated today: `request-comment`), attaches a file to a request, and uploads a library document | Render a page of jason's components; hold a per-unit document shelf (not captured); set a status that says approved or denied (a person's act); mark a request complete (a person's act, but the owner-information exception) | The **request thread**: the state in words, the next step, the decision letter attached. Community-level documents: the procedure, the FAQ, the forms |
| A generated per-unit packet | Yes: one Markdown source becomes a letterhead Doc and a PDF (`jason letter --markdown FILE --pdf OUT`, [../base-templates.md](../base-templates.md)) | Renders it from a base template for the profile; a person delivers it (a comment's attachment, a Gmail draft, handed over). A mailed copy is a person's `jason mailroom --send --yes`, four billed pages at most | Stay current (it is dated); take an entry from the owner | **The unit view as a document**: "Your unit, as of Oct 5" |
| An owner-held folder | The fallback in the unit-records design | Nothing: the owner controls it | The association cannot read a private entry in it | The private manual, until a surface exists |
| An owner-facing surface | No | Nothing | Needs owner sign-in, TLS, rate limits, and the board's written policy on who may see what | Later. The same payload and components |

**The decision this page makes.**

1. **One payload.** `GET /api/unit-home?unit=ID&audience=owner` returns the owner's unit as data. The same payload feeds three renderers: the console's owner-view page (the manager's preview, real), a base template `unit-home` that renders it to a Doc and a PDF (real, delivered by a person), and the later owner-facing page. Nothing is worked out in a renderer.
2. **The request channel stays PayHOA.** The owner's request, its status, and the decision letter live in the PayHOA thread, which is where owners look. jason prepares the thread's text (state, next step) for a person to post and attaches the letter. It sets no status.
3. **The manual's private half waits.** An entry an owner made from a request submitted to the association is the association's record and is shared by that act (the form says so). A private entry exists only where the owner holds the manual. Until an owner-facing surface exists, a file a person generates for an owner holds only shared and association entries, and says how many private ones were left out (a count, never a title).
4. **Not this pass:** the owner-facing surface, owner sign-in, mirroring jason's states into PayHOA's statuses.

## The components

Existing jason-ui parts are reused where named: `StageSteps`, `Clock`, `DueDate`, `Pill`, `Checklist`, `ConfirmList`, `Confirm`, `Command`, `Recitation`, `ReadingLabel`, `DecisionBrief`, `DecisionCard`, `RollCall`, `DraftLetter`, `Doc` and `DocList`, `Timeline`, `DataTable`, `Findings`, `Caveats`, `HeldNote`, `Money`, `Stat`, `Tabs`, `EmptyState`, `RemoteView`, and, from the unit-records handoff, `EffectiveRecord`, `CoverageCell`, `FactList`, `UnitManual`, `ImprovementForm`, `LossPacket`, `SourcedDate`, `OpenQuestion`. `AnswerWord` and `QuestionCard` are the applicability handoff's. New parts only where a table says so.

### (a) The review and the board stage

| Component | Where it renders | Data | States to design |
|---|---|---|---|
| `RequestPipeline` (a `DataTable` preset) | `#/requests?kind=architectural`, and the request band's header | `requests[]` | counts above the table by state and standing; rows by clock then received day; a row with the track, the state word, the waiting-on line; empty ("No improvement requests are open. 6 decided in the last 12 months."); a request with no clock ("open, no clock") |
| `RequestStateStrip` (a `StageSteps` preset) | the request page's top | `state`, `history[]` | the states in order, the current one `aria-current="step"`; incomplete and reconsideration shown as a branch in words; withdrawn and lapsed as a closing word; each step with who moved it and when |
| `WaitingOn` | under the strip, in every list row | `waitingOn` | "Waiting on the owner for a scale plan, from Oct 3"; "On the board's agenda for Oct 20"; "Waiting on the secretary to record the vote"; "Waiting on no one: a person has not moved it" (the stale case) |
| `RequestClock` (a `Clock` and `DueDate` preset) | the request page, under the strip | `clock` | the source word (set by the statute, set by the governing documents, **proposed policy, not adopted**, no clock on record), the recited provision on demand, the due day with `DueDate`, days paused with the reason and who recorded it, and **the meeting that meets it** ("The last scheduled meeting on or before the due day is Oct 20; its notice goes out by Oct 16 (4920)", labeled computed); "No scheduled meeting falls before the due day"; a business-day clock says weekends are skipped and holidays are not |
| `NeedAnswer` (an `AnswerWord` preset) | the request header and `#/applies`-style rows | `need` | approval required (the row and its provision); approval not required (the deciding row); **undetermined** (the missing fact, and the question to the board or counsel, linked); never "not required" for a miss |
| `CompletenessList` (a `Checklist` preset) and `DetermineConfirm` (a `Confirm` preset) | the Application tab | `checklist[]`, `determination` | each item present, missing, or **for a person** (a fact only a person can read from an attachment); a profile with no checklist ("The specification lists no application contents"); the determination as a person's signed act, and jason's list labeled "jason's reading of the form; a person decides"; deemed complete by the statute (rebuild track) |
| `ReviewerNote` and `ReviewForm` | the Review tab | `reviews[]` | a person's note with name, role, date; blank; saving; saved; a recommendation shown as the reviewer's, never jason's; no review yet |
| `StandardsRecital` (`Recitation` list) | the Review and Board tabs | `standards[]` | each provision whole with its citation and version in force, then the board's adopted standards (each with its adoption date), then any reading labeled with whose it is; a provision not on file ("not on file; ask counsel"); a standard proposed and not adopted, labeled |
| `SimilarDecisions` | the Review tab | `precedents[]` | each earlier request's change in general words, outcome, meeting, and conditions; none found ("none on record is not none decided"); "A precedent shows past handling, not this matter's facts" |
| `ImprovementBrief` (a `DecisionBrief` preset) | the Board tab; `#/agenda`'s item; `#/actions`'s card under Details | `brief` | the question, the criteria (the recited standards and 4765's three), lettered options (approve; approve with conditions; deny, each reason tied to a standard; continue; refer; table), the facts; never a recommendation (the store refuses a body that names one); the reviewer's recommendation shown beside it as the reviewer's |
| `ConditionsPicker` | the brief's option "approve with conditions" | `conditions[]` | the standard list by name, a free line, each with a due day and what proves it; none chosen; a condition the profile has not adopted, labeled |
| `MotionDraft` | the Board tab and `#/room`'s motion field | `motion` | the text rendered from the base template; edited by a person; recorded by the secretary (mover and second); a request with no board item yet ("Place it on the agenda first") |
| `BoardStageLinks` | the Board tab | `board` | the board item (`#/actions`), the agenda (`#/agenda`), the meeting's notice (4920), the decision (`#/decisions`), each a link with its state word. **No approve, deny, or decide control anywhere on this tab** |
| `DecisionLetterView` (a `DraftLetter` preset) and `ElementsCheck` (a `Checklist` preset) | the Decision tab | `letter`, `elements[]` | the letter through its stages, approved for its words by the officer who recorded the vote with the meeting's date; each required element present or missing (the decision, the request, the meeting and vote, the conditions, the reasons and the standard, the reconsideration procedure, what an approval is and is not); a denial missing its reasons or its procedure blocks "approved" for the words; the delivery record (`sentRef`) or "not sent yet" |
| `ConditionsTracker` | the Work tab | `conditions[]` | open, met (who, when, the evidence), waived by a later decision; due soon; past due with "none on record" |
| `WorkRecord` and `VerifyConfirm` | the Work tab | `completion` | started and finished as the owner said, entered by a named person "as reported by the owner"; verified by a named person with the evidence (a permit's final, photographs, a visit) and the day; a difference between the approval and what was done shown side by side and never as a violation |
| `ReconcileRow` (a `Findings` row) | the unit's tab, the request page, and the board digest as a count | `findings[]` | the five kinds in "The vocabulary", each with its fixed words, its evidence chips, and who sees it; closed; seen |

### (b) The owner's unit view

The owner sees their own unit and nothing else. These components work **without `ConsoleShell`**, at phone width, on a plain page with the community's brand ([handoff-unit-records.md](handoff-unit-records.md#where-it-lives-in-the-console)).

| Component | Where it renders | Data | States to design |
|---|---|---|---|
| `UnitHome` | the owner's page; the packet's cover | `unit-home` | the four bands in order: Your requests, Your unit's manual, Your unit's documents, About your community; "as of Oct 5" with how the file was made; nothing on record for the unit (an invitation, not an error) |
| `MyRequestCard` | Your requests | `requests[]` | one card per request: the owner's words for the change, the state word, the next step, the clock in words, the link to the request in PayHOA (a link the profile supplies), the decision letter as a `Doc` once sent |
| `OwnerStateWord` (a `Pill` preset) | each card | `ownerState` | the owner's words in "The vocabulary" below; never color alone |
| `NextStepLine` | each card | `next` | what happens next and who does it, in one sentence; for a proposed clock, no date ("No time limit is adopted for this kind of request"); for an incomplete one, the items and how to send them |
| `OwnerTimeline` (a `Timeline` preset) | a card's details | `history[]` | received, determined, on the agenda, decided, letter sent, work started, work finished, confirmed, recorded; each with its day; only what is on record |
| `ApprovedNotRecorded` | Your unit's manual, above the entries | `prompts[]` | "Approved Oct 20. Add what was done to your manual." with the approval as a chip; shown to the owner only |
| `ImprovementCard` | the manual | `entries[]` | the entry: what and where, what it replaced, date, product and model, contractor, permit, the owner's figure labeled "paid by the owner; not certified" (`Money`, integer cents), photographs, the approval chip, the visibility word; an entry whose approval is not on file shows "No approval on file for a change of this kind: [the provision]. If one was given, link it." (the owner's gap, never shown to the board) |
| `ShareChoice` | each entry | `visibility` | a radio group: **private to you**, **shared with the association**, **made by the association**; under the choice, in words, what the other side can then do, and, for sharing, "If this change needed approval and none is on file, the association will see that. Sharing may make it an association record." A change is a `Confirm` in the owner's name; the manual stays an offer ("Nothing is required of an owner") |
| `ManualEmpty` | the manual | none | "Start your unit's manual" with what it is for and how to begin; the common case |
| `UnitDocuments` (a `DocList`) | Your unit's documents | `docs[]` | the plan's sheets and original specifications (community facts for the plan, with "documented", "reported", or "assumed"); the unit's decision letters; manuals and warranties for the plan; empty; a document the owner may not open |
| `ApprovalNeedTable` | About your community | `needs[]` | which changes need approval, in plain words with the provision recited under each: required, not required, **undetermined** ("Ask the board before you start"); the profile's `ChangeRule` rows as the owner reads them; none stated |
| `HowToApply` | About your community | `apply` | how to apply (the channel), what an application holds (the checklist), how long a decision takes and **where that time comes from** (statute, documents, or "no time limit is adopted"), how to ask for reconsideration; the annual 4765(c) notice's contents, not paraphrased |
| `CommunityResources` | About your community | `facts[]`, `documents[]`, `contacts[]` | the facts view of [screens/community-facts.md](screens/community-facts.md) (paint colors, touch-up paint, the FAQ), the governing documents and the rules that apply to changes (each a `Doc`), the contacts and the how-tos; a fact assumed, shown as an assumption and "your unit may differ" |

### (c) The owner's resale summary and insurance schedule

Outputs the owner chooses to share. The owner (or, until there is a surface, a person at the owner's request) builds each; the association stores neither.

| Component | Where it renders | Data | States to design |
|---|---|---|---|
| `OutputBuilder` | the manual's header: **Make a summary for a buyer**, **Make a schedule for an insurer** | `output` | four steps in order (purpose, entries, fields, preview), each a step the person can go back to; never auto-sent; a file at the end |
| `EntryPicker` | step 2 | `entries[]` | each entry a labeled checkbox with its date and what; nothing pre-checked; "N private entries are not included" where a person (not the owner) builds it; "Entries without an approval for a change that needed one: 2" shown before the preview, to the owner, with the link to add it |
| `FieldPicker` | step 3 | `fields[]` | the contractor, the cost (the owner's figure), the photographs, each included or left out; the defaults are out |
| `ResaleSummaryPreview` | step 4, the print layout | `summary` | the header ("Prepared by the owner ... The association certifies nothing about it"), one line per entry, the approval references and letter copies as `Doc`s, the footer with the date and the count; a reminder row for a statutory owner duty (a charger's disclosure to buyers), recited with its citation; no entries chosen |
| `InsuranceSchedulePreview` and `ScheduleTable` | step 4, the print layout | `schedule` | a real table with a caption, header cells, and a total row: the date, what and where, what it replaced, product and model, contractor, permit and approval references, the owner's figure, photographs listed; the total "the owner's figures, added up; not an appraisal, not a replacement cost"; the plan's original specification beside a row where one is on file; the 5300(b)(9) statement recited, and where the governing documents draw the line between what the association and the owner insure, that line recited by the profile |
| `ExportLog` | the manual's footer | `exports[]` | each file made: when, by whom, which purpose, how many entries; never the contents; none yet |

### (d) The original-or-upgraded view at a loss

| Component | Where it renders | Data | States to design |
|---|---|---|---|
| `OriginalOrUpgradedRow` (an `EffectiveRecord` row preset) | the unit record's tab; the loss packet's first step | `components[]` with `changes[]` | the component, its status word, the original specification and its source, and beside the two coverage columns the **change evidence**: the approval and its day, the entry and its day, the permit, the invoice; no specification for the plan (every row unknown, stated once at the top); builder option with its open question |
| `ChangeEvidence` | inside the row | `changes[]` | chips: approval (the request), entry (shared), permit, invoice; each a `Doc` or an address with its level; an entry not shared is not listed |
| `ApprovalOnFile` | inside the row | `approvals[]` | "An approval is on file for this component, Oct 20, 2025. No entry is shared." with the question for the owner as a **draft** a person sends; the approval says a change was allowed, not that it was finished |
| `OwnerKnowledgeNote` | above the packet | `ownerKnows` | the packet was opened for this unit "with the owner's knowledge", by whom and when; private entries counted and not read; the packet never contacts the owner |

## The vocabulary

Every state is a word from the code or the workflow's enum, so the console, the terminal, and the letters agree. No state is color alone.

**The request's states, for the association** (`RequestState`): draft, submitted, incomplete, complete, under review, for the board, decided, reconsideration, work started, work finished, verified, recorded, withdrawn, lapsed. "Decided" is followed by the board's own word (approved, denied, tabled, continued, referred) from the decision record, and by "with conditions" where the approval carries them.

**The same states, in the owner's words.** The owner never sees an internal word that sounds like a ruling before a ruling exists.

| State | The owner sees | The next step line |
|---|---|---|
| submitted | Received | "The association received your request on Oct 1. A person checks that it is complete." |
| incomplete | Needs more from you | "Send: a scale plan. Reply on your request in the owner portal." |
| complete | Complete | "Your request is complete. A reviewer reads it next." |
| under review | Under review | The clock in its own words: "Decision due by Nov 14 (set by the governing documents)", or "No time limit is adopted for this kind of request." A proposed policy's day is not shown |
| for the board | On the board's agenda | "The board takes it up at its meeting on Oct 20." Or "The board takes it up at a meeting; the date is not set." |
| decided, approved | Approved by the board at its meeting of Oct 20 | "The decision letter was sent Oct 22 in the owner portal." Or "The decision letter is being prepared." Shown only when a decision record exists |
| decided, approved with conditions | Approved with conditions | The conditions, each with its due day |
| decided, denied | Denied | "The letter explains why and how to ask the board to reconsider." |
| reconsideration | Reconsideration asked | "The board takes it up at its next open meeting." |
| work started, work finished | Work started, Work finished | "A person confirms the work against the approval." |
| verified | Confirmed | "Confirmed against the approval on Nov 3 by Pat Example." |
| recorded | In your manual | the link to the entry |
| withdrawn, lapsed | Withdrawn, Approval ended | "A new request is needed to start the work." |

**A clock's source** (`ClockSource`): set by the statute, set by the governing documents, **proposed policy, not adopted**, no clock on record. A statute's clock shows its citation; a proposed policy's shows "a target until the board adopts it" and is **never** published to an owner as a date.

**The answer to "does it need approval"** (`applicability.Answer`): approval required, approval not required, **undetermined**. Undetermined is never styled as "not required", is never grouped with it, and names the missing fact and the question.

**The reconciliation's findings** (the words are fixed so they say no more than the record shows):

| Finding | Words | Who sees it |
|---|---|---|
| Approval, no entry | "Approved [date]. No entry shared with the association." | the owner (a prompt); the manager as a count |
| Entry, no approval | "Recorded [date]. No approval on file for a change of this kind: [provision]. If one was given, link it." | the owner only |
| Records show work, no approval | "The records show [what, where, source]. No approval is on file for it. jason does not know whether one was needed or given: a person reads the record." | the board, as a board item |
| Entry differs from the approval | "The approval says [A]. The entry says [B]." Both, side by side | the owner; the manager |
| Condition open, not verified, lapsed | the line, with the day and "none on record" | the manager |

**Never on screen**: "covered", "not covered", "at fault", "your responsibility", "violation" (for a finding), "illegal", "unapproved" (as a charge), "approved by jason", or any word that says jason decided, in a cell, a heading, a chip, a letter, or an export.

## Data shapes

Made-up samples: "Example Village HOA", "123 Main St", "Owner A", "Jane Example", "Pat Example". A statute's or a document's words are never typed in a payload: a provision carries its citation and the loader recites it from the shelf at render (`recited` is empty here to show that). Amounts are integer cents.

`GET /api/improvement-requests?unit=14` (proposed; the manager's list):

```json
{
  "found": true, "community": "Example Village HOA", "asOf": "2026-10-05",
  "summary": {"open": 4, "byState": {"under review": 2, "for the board": 1, "work started": 1}, "overdue": 0, "decidedLast12Months": 6},
  "requests": [
    {"id": "imp-20261001-a1b2", "unit": "14", "kind": "architectural application", "track": "ordinary",
     "received": "2026-10-01", "channel": "payhoa", "source": "payhoa:submission:90017",
     "ownersWords": "Replace the bathroom floor with tile",
     "state": "under review",
     "waitingOn": {"who": "the reviewer", "what": "the plans", "since": "2026-10-03"},
     "need": {"answer": "undetermined", "missing": ["whether the documents require approval for a floor inside the unit"],
              "question": "q-4c1d90", "provision": "[the row's provision address]"},
     "clock": {"source": "proposed policy", "adopted": false, "days": 30, "pausedDays": 0, "due": "2026-10-31",
               "standing": "open", "meetingThatMeetsIt": {"date": "2026-10-20", "noticeBy": "2026-10-16", "label": "computed"}},
     "level": "P2"}
  ],
  "caveats": ["A proposed clock is a target until the board adopts it. A completeness list is jason's reading of the form; a person decides."]
}
```

`GET /api/improvement-request?id=imp-20261001-a1b2` (proposed; one request, abridged):

```json
{
  "found": true, "id": "imp-20261001-a1b2", "unit": "14", "address": "123 Main St", "state": "for the board",
  "history": [{"state": "submitted", "on": "2026-10-01", "by": "channel"},
              {"state": "complete", "on": "2026-10-03", "by": "Jane Example"},
              {"state": "under review", "on": "2026-10-03", "by": "Jane Example"},
              {"state": "for the board", "on": "2026-10-06", "by": "Jane Example"}],
  "checklist": [{"item": "Drawings to scale", "status": "present", "doc": "drive:1AbCdEf"},
                {"item": "Contractor's licence", "status": "for a person", "doc": "payhoa:file:7731"},
                {"item": "Permit, where one is needed", "status": "missing"}],
  "determination": {"complete": true, "missing": [], "by": "Jane Example", "at": "2026-10-03T16:20:00Z", "deemed": false},
  "reviews": [{"by": "Pat Example", "role": "committee", "at": "2026-10-05", "note": "The plans match the application.", "recommendation": "a person's, labeled"}],
  "standards": [{"citation": "CIV 4765(a)(2)", "recited": null}, {"citation": "[document address]", "recited": null, "adopted": "2024-04-16"}],
  "precedents": [{"id": "imp-20250611-c3d4", "change": "Replace window coverings", "outcome": "approved", "meeting": "2025-06-17", "conditions": 1}],
  "board": {"item": "improvement-imp-20261001-a1b2", "itemStatus": "on agenda", "meeting": "2026-10-20", "noticeBy": "2026-10-16",
            "decision": null, "motionDraft": "Move to approve the request of the owner of 123 Main St, received Oct 1, 2026, ..."},
  "letter": null,
  "conditions": [], "completion": null, "entries": [],
  "commands": {"propose": "jason improvements --board-item imp-20261001-a1b2 --by NAME"}
}
```

`GET /api/unit-home?unit=14&audience=owner` (proposed; the owner's own unit; every field is an allowlist):

```json
{
  "found": true, "community": "Example Village HOA", "unit": "14", "address": "123 Main St", "plan": "A", "asOf": "2026-10-05",
  "requests": [
    {"id": "imp-20261001-a1b2", "ownersWords": "Replace the bathroom floor with tile",
     "ownerState": "On the board's agenda", "next": "The board takes it up at its meeting on Oct 20.",
     "clock": {"words": "No time limit is adopted for this kind of request.", "source": "none"},
     "history": [{"on": "2026-10-01", "what": "Received"}, {"on": "2026-10-03", "what": "Complete"}],
     "thread": {"label": "Your request in the owner portal", "href": "[a link the profile supplies]"},
     "letter": null}
  ],
  "manual": {
    "entries": [{"id": "e-5f2a", "what": "Water heater", "where": "Utility closet", "replaces": "Water heater",
                 "date": "2024-03", "status": "equivalent replacement", "statusBy": "the owner's word",
                 "costCents": 118000, "costNote": "paid by the owner; not certified",
                 "approval": null, "needsApproval": {"answer": "applies", "provision": "[the row's provision address]"},
                 "visibility": "private"}],
    "prompts": [{"request": "imp-20250611-c3d4", "text": "Approved Jun 17, 2025. Add what was done to your manual."}],
    "privateHeldForOthers": 0
  },
  "documents": [{"kind": "plan sheet", "name": "Plan A, sheet 3", "ref": "library:1044", "status": "documented"}],
  "community": {
    "needs": [{"change": "Changes visible from the outside", "answer": "applies", "provision": "[address]"},
              {"change": "Interior paint", "answer": "does not apply", "provision": "[address]"},
              {"change": "A floor inside the unit", "answer": "undetermined", "ask": "Ask the board before you start"}],
    "apply": {"channel": "the owner portal's Architectural Request form", "checklist": ["Drawings to scale", "Contractor's licence"],
              "timeWords": "No time limit is adopted for this kind of request.", "reconsideration": "[the procedure, once adopted]"},
    "facts": [{"id": "touch-up-paint", "statement": "...", "status": "documented"}],
    "contacts": [{"role": "Manager", "how": "[a link or number the profile supplies]"}]
  },
  "caveats": ["An approval says a change was allowed. It does not say the change is safe, lawful, insured, or worth what it cost."]
}
```

`GET /api/improvement-schedule?unit=14&purpose=insurance&entries=e-5f2a,e-7b90&fields=cost,contractor` (proposed; a logged read that returns a file link):

```json
{
  "found": true, "purpose": "insurance", "unit": "14", "asOf": "2026-10-05", "by": "Owner A",
  "header": "Prepared by the owner of this unit from the owner's own records. The association certifies nothing about it.",
  "rows": [{"date": "2024-03", "what": "Water heater", "where": "Utility closet", "replaces": "Water heater",
            "product": "[maker, model]", "contractor": "Vendor A", "permit": "[number]", "approval": null,
            "ownersFigureCents": 118000, "original": "Water heater (plan A specification, source on file)"}],
  "totalOwnersFiguresCents": 118000, "totalNote": "the owner's figures, added up; not an appraisal, not a replacement cost",
  "statement": {"citation": "CIV 5300(b)(9)", "recited": null},
  "privateNotIncluded": 1, "withoutApproval": 1,
  "file": {"kind": "pdf", "href": "[a ten-minute link]"},
  "logged": {"columns": ["date", "what", "cost"], "rows": 1}
}
```

`GET /api/loss-packet?unit=14&incident=inc-1` gains, in step 1 (proposed):

```json
{"components": [
  {"component": "Bathroom floor", "status": "upgrade", "specification": "Vinyl (plan A, source on file)",
   "declaration": {"points": "owner's policy"}, "policy": {"points": "owner's policy"},
   "changes": [{"kind": "approval", "id": "imp-20250611-c3d4", "on": "2025-06-17", "words": "An approval is on file for this component."},
               {"kind": "entry", "id": "e-91ab", "on": "2025-08", "shared": true}],
   "ask": "No invoice is shared. Draft a question to the owner (a person sends it)."}],
 "ownerKnows": {"by": "Jane Example", "on": "2026-10-05"}, "privateHeld": 1}
```

## What the design must keep

- **jason never approves, denies, or assigns.** No control on any screen here is labeled approve, deny, decide, or assign for a request. The board's decision is a vote at a meeting, recorded by an officer; the Board tab links the item, the agenda, and the decision. The only controls are a person's records (a determination, a review, a placement on the agenda proposed for the board, a condition met, a delivery recorded, a verification), each a `Confirm`.
- **A brief never recommends.** A reviewer's recommendation is the reviewer's, with a name, beside the brief and never inside it.
- **Recite, then label.** A provision is recited whole with its citation and version in force before any reading; each reading says whose it is. A statute's words are never typed on a screen from this page.
- **A proposed policy is not a rule.** A proposed clock or condition is labeled "proposed policy, not adopted" wherever it shows, ranked after a statute's or the documents', and never shown to an owner as a date.
- **A miss stays a miss.** "Does it need approval" has three answers. Undetermined is a question, never "not required." "None on record is not none given."
- **The owner's manual is the owner's.** A private entry is counted and never read by anyone else. Contractor, cost, phone, and neighbors' names never appear in a list across units. A cost is the owner's figure, labeled "paid by the owner; not certified."
- **An approval states that a change was allowed.** Not that it is safe, lawful, insured, equivalent to what it replaced, or worth what it cost. The words appear in the letter and beside every approval chip.
- **An entry's status is the owner's word.** The association states none. The owner's own description on the application is shown as the owner's.
- **A finding is a lead.** The five findings use their fixed words. A finding about an entry without an approval goes to the owner only. A "records show work" lead goes to the board as a board item, never as a notice or an accusation; a reconciliation finding is not part of the resale documents.
- **Resale and insurance outputs are the owner's.** The association stores neither, adds nothing to the 4525 documents, and gives no coverage advice. Each output carries its header and footer, and the statute's own words where it recites one.
- **The owner view is a view of the owner's unit.** It is not a permission, and it is not reachable by an owner.
- **Executive session stays out.** A possible-violation lead on a discipline matter is held and shown by its general subject, as any executive item.
- **Nothing is sent.** Exports are files. A message to an owner is a draft a person sends. A letter is sent by a person, who records where. A PayHOA comment is not posted from the console until it has a gate; the page shows the text to copy.
- **Words on screen** follow [content/style.md](content/style.md): sentence case, verbs first, no "successfully," no "please," an empty state that invites ("Start your unit's manual").

## Where it goes

Routes are proposed, consistent with [information-architecture.md](information-architecture.md#where-the-proposed-screens-go); none exists yet.

- **Overview → Requests**: `#/requests?kind=architectural` is the pipeline; `#/requests?id=ID` is the request, as `Tabs`: **Application** (the request, the checklist, the determination, the clock), **Review** (reviewers' notes, the standards recited, similar decisions), **Board** (the brief, the motion draft, the links), **Decision** (the letter, its elements, the delivery), **Work** (conditions, start, finish, verification), **Record** (the entry link, the findings). The header's `Command` is `jason improvements --request ID`.
- **The unit's page**: `#/members?unit=ID` gains an **Improvements** tab ([screens/unit-record.md](screens/unit-record.md)): the unit's requests, its manual with the findings, and the schedule and summary for an owner who asks. The loss packet's first step takes the change evidence.
- **The board loop is not changed.** The item is a card in `#/actions`; the agenda wizard lists it; the room shows the motion draft; `#/decisions` shows the `DecisionCard`; `#/approvals` holds the letter. Each links back to the request.
- **The owner's unit**: the console's owner view is `#/unit?view=owner&unit=ID` (a preview, on the manager's machine). The same payload renders `unit-home` to a Doc and a PDF through `jason letter --markdown`.
- **The board digest** gets a count (open requests by standing; leads open), never a unit's contents.

**Loaders to add** (names only; nothing built; each wraps what exists or what the records page adds):

| Loader | Route | Wraps | Notes |
|---|---|---|---|
| `improvement-requests` | `GET /api/improvement-requests?unit=&state=&kind=` | `jason.api.member_requests` (the kind and clock), the `improvements/` store | The pipeline; a P2 field is masked outside the request page |
| `improvement-request` | `GET /api/improvement-request?id=` | the store, `Community.change_rules()` through `applicability.evaluate`, `improvement_checklist`, `response_sources`, `decisions`, `notice_elements` | One request; the clock and the meeting that meets it are computed in the loader |
| `improvement-policies` | `GET /api/improvement-policies` | `Community.improvement_policies()`, the standards proposal | Each policy row: proposed or adopted, with its adoption |
| `unit-home` | `GET /api/unit-home?unit=&audience=owner` | the above for the unit, `unit_record_view(owner=True)`, `facts_view`, the profile's documents | The owner's allowlist; `audience=manager` returns the shared view |
| `improvement-schedule` | `GET /api/improvement-schedule?unit=&purpose=&entries=&fields=` | `unit_records_view._entries`, the profile's specification | A logged read that returns a file; `purpose` is `insurance` or `resale` |
| `improvement-findings` | `GET /api/improvement-findings?unit=` | the reconciliation | Counts for the board; lines for the owner and manager as the table says |
| `loss-packet` (extended) | `GET /api/loss-packet?unit=&incident=` | `assemble` plus the unit's approvals and shared entries | Step 1 gains `changes[]` |

**Writes to add** (each a `Confirm` in the signed-in person's name, through the write guard, with the token and `by`; each answers 401 with no one signed in and refuses a secret):

| Write | Route | Confirm button | CLI equivalent (to add) | Notes |
|---|---|---|---|---|
| Record a determination | `POST /api/write/improvement/determination` `{id, complete, missing[]}` | **Record it complete as Jane Example** / **Record the incomplete list as Jane Example** | `jason improvements --determine ID --complete \| --incomplete ITEM... --by NAME` | A letter of the list is its own draft |
| Record a pause, or its end | `POST /api/write/improvement/pause` `{id, reason, from, to?}` | **Record the wait as Jane Example** | `jason improvements --pause ID --reason waiting_on_member --by NAME` | Only a policy clock pauses |
| Record a review | `POST /api/write/improvement/review` `{id, note, role}` | **Save the review as Pat Example** | `jason improvements --review ID --by NAME` | The note is the person's |
| Place on the agenda | `POST /api/write/improvement/board-item` `{id}` | **Propose it for the agenda as Jane Example** | `jason improvements --board-item ID --by NAME` | Makes a board item (`tasks.board_items.propose`); the board sets the agenda |
| Record conditions | `POST /api/write/improvement/conditions` `{id, decision, conditions[]}` | **Record the conditions as Sam Placeholder** | `jason improvements --conditions ID --by NAME` | After the vote, by the recording officer |
| Draft the decision letter | `POST /api/write/improvement/letter` `{id}` | **Draft the letter as Jane Example** | `jason improvements --letter ID --draft --by NAME` | A draft in the letters' store; its approval is the existing stage, by the officer with the meeting's date |
| Record a delivery | `POST /api/write/improvement/delivered` `{id, via, sentRef, on}` | **Record where it was sent as Jane Example** | `jason improvements --delivered ID --via VIA --ref REF --by NAME` | Never a send |
| Record work as reported | `POST /api/write/improvement/work` `{id, started?, finished?}` | **Record the owner's report as Jane Example** | `jason improvements --work ID --started DAY --by NAME` | "as reported by the owner" |
| Verify | `POST /api/write/improvement/verify` `{id, evidence[]}` | **Record the check as Pat Example** | `jason improvements --verify ID --evidence ADDRESS --by NAME` | The evidence is named |
| Link an entry | `POST /api/write/unit-record/entry` (built) with `request` | the existing entry's button | `jason unit-record --add ... --by NAME` | The entry's `approval` is `improvement:<id>` |
| Change an entry's visibility | `POST /api/write/unit-record/visibility` (built) | **Share this entry with the association as Owner A** | `jason unit-record --visibility ...` | The consequence is shown first |
| Close or mark a finding seen | `POST /api/write/improvement/finding` `{id, state}` | **Mark seen as Jane Example** | `jason improvements --finding ID --seen --by NAME` | Changes nothing else |

Not from the console: a PayHOA comment, a file attached to a request, a Mailroom send, a request status. They are engine kinds proposed in [approval-workflow.md](approval-workflow.md#8-the-action-kind-registry) (`payhoa.request.comment`, `payhoa.request.attach`) and wait for a registry row. Until then the page shows the text and the command.

## Accessibility

As [components.md](components.md#accessibility) and [content/patterns.md](content/patterns.md#accessibility-wcag-22-aa):

- **Keyboard.** The state strip is an ordered list; each step is text, the current one `aria-current="step"`. Tabs follow the tabs pattern with arrow keys, and each tab is reachable by its `?id=` and a hash. Every action is a native `button`. A `Confirm` restates what will change and by whom.
- **Screen reader.** Every state word is the accessible name of its pill, followed by the waiting-on line. A clock's source word is read with its due day ("due Oct 31, a proposed policy, not adopted"). The recitation is a `figure` with `blockquote` and `figcaption` (citation and version). A checklist is a list of items each with its status in words. A finding reads its fixed words. The "meeting that meets the clock" is a labeled line, not a tooltip.
- **Tables.** `ScheduleTable` and `RequestPipeline` are real tables with captions ("Open improvement requests, most urgent first"; "Improvements for Unit 14, with the owner's figures"), `th scope` headers, a total row marked `scope="row"`, and numbers right-aligned in tabular figures. A table that scrolls sideways does so inside its own labeled, focusable region.
- **Forms.** `ShareChoice` is a `fieldset` with a legend, radio buttons whose labels are the words, and the consequence tied to the group by `aria-describedby`. The determination's missing items are a group of labeled checkboxes. An error names the field and how to fix it; a half-typed review stays across a tab change.
- **Print.** The summary, the schedule, the decision letter, and the unit packet have print layouts: black on white, the header and footer repeated, no sticky bars, links written out. Color and icon repeat words and never replace them.
- **Target size (2.5.8)** 24 by 24 CSS px at least, or spaced, for every chip, radio, and checkbox; **redundant entry (3.3.7)**: the person's name comes from "Signed in as" (or, for an owner, from the sign-in); a determination's missing items are not asked again when a letter is drafted. **Timing (2.2.1)**: nothing times out. **Reflow (1.4.10)**: nothing scrolls sideways at 320 px. **Status messages (4.1.3)**: a recorded step announces itself in `role="status"`; a refusal that stops the work is `role="alert"`, in jason's words, with "Nothing was written." **Motion**: the reduced-motion setting is respected.
- **Photo upload (owner)** works from a phone camera and from a file, has a text alternative field, and a failure keeps what was typed.

## Phone layout (under 720 px)

The owner's unit is the phone's first screen. At 360 px it is one column, in the order an owner needs it, with each band a disclosure after the first.

```
+--------------------------------------+
| Example Village HOA                  |
| Unit 14 · 123 Main St · Plan A       |
| As of Oct 5                          |
+--------------------------------------+
| YOUR REQUESTS (1)                    |
| Replace the bathroom floor           |
| [On the board's agenda]              |
| The board takes it up Oct 20.        |
| No time limit is adopted for this    |
| kind of request.                     |
| [Open it in the owner portal]        |
| [Details v]                          |
+--------------------------------------+
| YOUR UNIT'S MANUAL (2) v             |
| Approved Jun 17, 2025. Add what was  |
| done to your manual.   [Add]         |
| Water heater · 2024 · private        |
| [Make a summary for a buyer]         |
| [Make a schedule for an insurer]     |
+--------------------------------------+
| YOUR UNIT'S DOCUMENTS v              |
| ABOUT YOUR COMMUNITY v               |
+--------------------------------------+
```

- The requests come first. A card's state word, its next step, and its clock are text, not a tooltip. The link to the request is a full-width button.
- `OutputBuilder`'s four steps are four screens with Back and Next at the foot, not sticky (2.4.11). The preview is the print layout in one column; the schedule's table becomes a list of cards, each row's labels written beside its values, and the total below.
- The manager's pages (the pipeline, the request tabs) collapse as the other handoffs do: `Tabs` become a `select`, the pipeline a list of name, state word, and due day, the board stage's links stacked. A phone is not where a board decides; the room's bottom sheet is as built.
- A photo is taken from the phone and added to an entry with its text alternative.

## Decisions for the design

1. **Where the improvement pipeline lives.** A filter and a band on `#/requests` (proposed here), or its own item under Governance. The loaders are the same.
2. **What an owner sees of a proposed clock.** This page shows none. The alternative shows "the board's target is Oct 31, not yet adopted." Decide whether an unadopted number ever helps an owner or only sets an expectation the association has not promised.
3. **Whether the unit view is a page, a packet, or both for the owner.** This page makes the document real now and the page later. Decide the cadence: on request, with the annual policy statement, or at each decision.
4. **The reviewer's recommendation beside a brief that never recommends.** Where it sits (a labeled aside, a tab) so a director reads it as a person's view and not as the system's.
5. **The conditions picker.** A standard list plus a free line, or the standard list alone. A free line is flexible and harder to track.
6. **The share consequence.** The wording that tells an owner what sharing may do ("the association will see that ... may become an association record") without alarming them or discouraging a manual. Test it with an owner.
7. **How "records show work, no approval" reads to the board.** A board item with its fixed words, or a count in the digest and a list on the unit's tab only. The board's own digest never lists a unit's contents.
8. **Whether the schedule's total is shown at all.** It is the owner's figures added up and labeled so; some will read it as a value. Decide whether the total is a default, an option, or left out.
9. **The first sentence of a decision letter's footer.** The statement of what an approval is and is not: the board adopts the words with the template, and the design should show them whole so the board sees them.
10. **Pre-approved categories.** If the board adopts a written rule that pre-approves a category with conditions, how the pipeline shows a request decided under it, with no individual vote, and where it is recorded.
11. **The phone, and the photo.** Photo first, then the form, or the form with an add-photo step; and how the approval is found and attached on a phone, and the gap shown when none is found.
12. **Owner-facing chrome.** The standalone page's header, language, and brand tokens, shared with the paint and community-facts pages, since several communities may use the same components under their own names.

## Not part of this pass

- The backend: the store, the loaders, the writes, the base templates (`improvement-motion`, `architectural-decision`, `unit-home`, the incomplete notice), and the profile's rows. The first build uses the sample data above as fixtures.
- The owner-facing surface, owner sign-in, and any hosting beyond loopback.
- Mirroring jason's states into PayHOA's custom statuses. A status is a person's act in PayHOA.
- Posting a comment, attaching a file, or setting a status from the console; a Mailroom send.
- An inspection by jason, a lookup of an owner's permit, or a check of a contractor's licence.
- Any statement of what a policy covers beyond what is recited from it, and any valuation.
- Deciding the policies proposed for the board ([../improvement-requests.md](../improvement-requests.md#where-the-documents-are-silent-policies-proposed-for-the-board)).
- The previews: the design project's authored preview for each component follows the build; fixtures will be a `*.test.tsx` beside each component, from the sample data above.
