# Design brief: the hearing run and the law review

One page of orientation for the design agent, for two Governance screens specified in [screens/hearing-process.md](screens/hearing-process.md) (the hearing as a run, `#/work/hearing/<run id>`, with the list at `#/hearings`) and [screens/law-review.md](screens/law-review.md) (`#/law-review`). It does not repeat the specs; it says what to read in what order, what to draw, the shared pieces once, what is built and what has no view, and a made-up community to draw against. Where a spec and this page disagree, the spec and the code win, and this page is corrected. The definitions are `hearing` (h1 to h16) and `law-review` (l1 to l14) in [../workflows/board-governance.md](../workflows/board-governance.md) sections 2.4 and 2.5.

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, owner, counterparty, or private fact; made-up samples only ("Oakview", "Unit U-14", run H-7, "Example Declaration", 2099).

**Built, checked against the code on 2026-10-11.**
- **Hearing:** `#/hearings` (`HearingsView`, `App.tsx` `SCREENS`), loader `hearings` (`jason.web.sources.hearings` over `jason.mcp.county.hearings`; gate P2 in `web/gates.py`), writer `POST /api/hearings/<key>` into `hearing_decisions.record`, `jason hearing` (`--list`, `--doc`, `--create`, `--notice-on`, `--suspension`; the unit is typed as `--address`), the Gmail draft case `hearing`, the notice catalog rows `discipline-hearing` and `discipline-decision`. The view draws a table with an **address column**, `Clock` stages, `DocList`, the decision entry behind `Confirm`, and `NoticePreview`. Its key and its Confirm sentence carry the address (the privacy cases to fix). **No view and no loader:** the run page, the opaque run id, the cure record, the executive-session request, the member's reply, the penalty-schedule check, the decision-notice delivery record, the 5855(g) list. Only `owner-info-cycle` and `control-adoption` are registered definitions (`workflows/definitions_general.py`), so `#/work/hearing/H-7` and `#/work/law-review/2099` resolve to nothing today. `work.py` says executive-session handling "is not composed"; registering `hearing` before it is would put a unit in a Work row (design-gaps).
- **Law review:** `jason conflicts` (`--area`, `--open`, `--leads`, `--since`, `--document`, `--json`), `jason.tasks.conflict_leads`, MCP `document_conflicts`, `law_in_force`, `cite_document`, `citation_gaps`, `document_citations`, `jason law-history`, `jason readings --stale`; loaders `citations`, `citation-gaps`, `reference-works`, `reference-page`, drawn by `ReferenceShelfView` and `CitationGaps` (step l4 only). **No view:** no `#/law-review` route; no loaders `conflict-leads`, `conflicts`, `cite`, `record`; no dispositions store or writer; no `jason law-review` command; no `LeadList`, `LeadReader`, `ConflictRows`. A name clash to avoid: `#/leads` (`LeadsView`) is the unpinned-things screen, not these leads.
- **Built components** (`ui/src/components`): `Recitation`, `ReadingLabel`, `Clock`, `ClockStrip` (with `LawBlock`, `lawCitation`), `BasisPill`, `ChangedSince`, `RunRow`, `RunStepPanel`, `WorkflowRail`, `StartRun`, `RunHistory`, `Confirm`, `Command`, `DocList`, `Pill`, `Caveats`, `Evidence`, `HeldNote`, `DataTable`, `Glyph`. **Not in the folder:** `PartOfRunBanner` (no `run-banner` loader), `RecordTrail`, `EvidenceLinks`, `RoleLine` (specified in [design-brief-board-records.md](design-brief-board-records.md); draw them by reference), `DiffTable`.

## A. The idea, and the rules that run through it

**The idea, in six sentences.**
1. A hearing is one member's path from the board's proposal to consider discipline to the written decision, in the order the statute states it, so that no requirement is skipped and each shows what is on record and who recorded it.
2. A law review asks one question of every written provision, each January and when a law takes effect mid-year: **has a later change in the law displaced any of it?** A lead is a reason to read two texts side by side, not a finding.
3. Both screens read, compute dates, and record what a person says. jason never imposes discipline, never fines, never mails a notice, and never resolves a conflict. The board decides; the secretary records the board's decisions.
4. Words before readings: the statute is recited whole from `data/authorities` (`Recitation`), the provision after it, then jason's reading under a `ReadingLabel`, then the disposition. A reading is never inline in the recited words, a heading, or a tooltip.
5. Every date says whose it is. A day jason works out is labeled exactly: "computed by jason from the statute's day-count, the earliest day" (`law` basis pill), never a stamp; a day a person states is "stated by NAME".
6. Both live in the run model: a run embeds reads and links writes ([screens/work.md](screens/work.md), "Where a step's work happens"). The run page shows the clock, the notice preview, the penalty check, and the 5855(g) list read-only; the board's decision is written on `#/decisions` and linked; a person's attestation, the cure record, the request and the reply, and a lead's disposition are the step's own register and write in place, each a `Confirm`, in the signed-in name.

**The rules** (a screen that breaks one is wrong):
- **Directors and officers have the same access to information.** No director-only view, no counts-only view among the offices that open the level; a treasurer sees what a director sees, who sees what an officer sees. A viewer whose office does not open the level gets counts and a held sentence.
- **The secretary records the board's decisions.** The hearing's decision and a conflict's outcome show as read from the decision record (motion, mover, second, votes, outcome); no control approves, imposes, adopts, resolves, votes, or sends. A mailing is a person's `jason mailroom --send --yes`, shown as a `Command`.
- **Member discipline is held.** The open record (list, agenda, Dock, minutes draft, Part-of-run banner, any export) names the matter only by its 4935 subject in the statute's words ("member discipline"), never the unit, member, violation, or the executive item's title (Civil Code 4935(e): general words). The run's id and URL are random; no key, path, or filename carries an address. The unit, matter, member, reply, and findings are P3, in the private view only, opened for a stated reason and logged. The owner view has no hearings loader.
- **Recite the version that governs,** with "jason's consolidated text, not an official restatement; the recorded or published copy governs". An earlier statute version not on disk is drawn as a miss with its `reason`, never filled with today's words. A section not on the shelf (Corporations Code 7341, the suspension notice period) is shown only as "not on the shelf" and offers no path.
- **A check is not a verdict.** The penalty check, the 5855(g) list, and a lead's route say met, open, not on record, or not yet read; they never say effective, void, compliant, violation, or conflict found. An unclear extent is never recorded as plain; where two readings remain the disposition is "for counsel", both are shown, neither applied.
- **Append only.** A correction is a later act; the cure, request, disposition, and delivery records keep their history. A cure recorded needs a second person to confirm. A digest that moved returns a lead to "Not yet read" and keeps the old act.
- **State is a word and a glyph, never colour alone.** Amounts are integer cents (draw dollars). Corrections to the statute's words are impossible: the page cannot edit a recitation.

## B. Reading order

1. [screens/hearing-process.md](screens/hearing-process.md), whole; then [screens/law-review.md](screens/law-review.md), whole.
2. [../workflows/board-governance.md](../workflows/board-governance.md) sections 2.4, 2.5, 5 (the screens), 6 (privacy), 9 (the sample), 10 (criteria 12 to 16).
3. [screens/work.md](screens/work.md) and [design-brief-work.md](design-brief-work.md) (the run page, the step panel, the embed rule); [screens/run-links.md](screens/run-links.md) (`PartOfRunBanner`, the opaque `?run=`, held matters).
4. [design-brief-board-records.md](design-brief-board-records.md) (`RecordTrail`, `EvidenceLinks`, `RoleLine`) and [design-brief-money-reviews.md](design-brief-money-reviews.md) C5 (the delinquency run: clocks strip, steps as rows, the executive-session banner). Reference these; do not redraw them.
5. [design-gaps.md](design-gaps.md) (G4, G5, the run-id and held-run items), then this page's D beside H.

## C. The screens

### C1. The hearings list, with the privacy handling (`#/hearings` and the Work rows)
One table of runs. Each row: the opaque label ("H-7"), a general title ("Member discipline hearing"), the state word, the hearing date, and the next clock with its basis. No unit, name, or matter. Draw three frames of one row and its run header: **private view off** (the unit, matter, member, reply, and findings read "In the private view" with a `lock`); **private view on** (a banner "Private view: on, reason: board prep, logged"; the unit id "Unit U-14" and the matter appear; never a street); and **the open record** as the minutes draft, agenda, and Dock show it: "Member discipline (Civil Code 4935)" and nothing more. Draw the empty state (the loader's "No hearings saved; plan one with `jason hearing`") and a `Part of a run on a matter held under Civil Code 4935(e)` banner on a screen the run touches. Supersedes the sample in [screens/work.md](screens/work.md) and design-brief-work H that names "the address".

```
| Hearings (3)                          Private view: off   [Open it, with a reason]            |
| H-7  Member discipline hearing   Open · hearing 2099-11-17   next: notice by 2099-11-07 [LAW]  |
| H-6  Member discipline hearing   Decision notice due 2099-12-01 [LAW]                          |
| H-5  Member discipline hearing   Closed · no discipline                                        |
```

### C2. The hearing run page (`#/work/hearing/H-7`)
Header (label, state, Private view, `jason://hearing/H-7 [copy]`, CLI, Note, Print history), a clock strip, then eight bands read like the statute. Each band shows what is on record, who recorded it, and what is missing. Draw it whole once, then the variants in H.
```
| Work > Hearing H-7 (Unit U-14: private view only)      Private view: on "board prep"   Open |
| CLOCKS  Notice by 2099-11-07 [LAW] computed by jason from the statute's day-count, the earliest day |
|         Hearing 2099-11-17 [PERSON]   Decision notice by 2099-12-01 [LAW]  (computed, not yet running) |
| 1 THE MATTER   in the board's words (P3) · violation day 2099-10-02 · set by President Dana E.        |
| 2 THE PENALTY CHECK  schedule v2099-1, distributed 2099-01-15 (annual statement) · cap $100          |
|   [Recitation CIV 5850(a),(c)] [ReadingLabel jason's] proposed $50: within the schedule and the cap  |
| 3 THE NOTICE  5 of 5 elements · delivered 2099-11-05, personal delivery, by the manager (stated)     |
|   [Recitation CIV 5855(a),(b)] [Preview the notice] Gmail draft saved · sent by a person, not jason   |
| 4 THE MEMBER  executive session requested 2099-11-06, recorded by the secretary [RecordTrail]         |
|   cure: none on record · financial commitment: none · reply: none received  [Record a cure...]        |
| 5 THE HEARING  agenda item 4 of the 2099-11-17 meeting, executive session, subject "member discipline"|
| 6 THE DECISION  the board decides; the secretary records · not yet recorded · [Record in Decisions]   |
| 7 THE DECISION NOTICE  due 2099-12-01 [LAW] · preview · delivered: not recorded · [Record delivery]   |
| 8 EFFECTIVE ONLY IF  CIV 5855(g): notice 10 days met · cure window met · exec session met · notice 14 open |
|   jason states what is on record; the board and counsel decide.   Confidential: CIV 4935.            |
```
Bands 1 to 7 follow `hearing` h1 to h16; band 8 is h15 (`RequirementsList`). A band that cannot yet be reached reads its reason, not an empty table.

### C3. Band pieces to draw closely
- **Notice clock and cure record.** The notice clock ("computed by jason from the statute's day-count, the earliest day"; the statute does not say how days are counted, so the board or counsel may count otherwise) and the delivery day as "stated by NAME", beside each other. A delivery after notice-by: "The notice was due by DATE and no delivery is recorded: the hearing must move (CIV 5855(a))" and band 5 blocked; whether a resent notice cures is left to the board or counsel. A **cure record** (`CureRecord`: none, cured, or financial commitment; day; evidence by `EvidenceLinks`; recorded by, then confirmed by a second person via `RoleLine`) that closes the run "no discipline" with the 5855(c) words recited and bands 5 to 7 skipped with the reason.
- **The member's request for executive session and reply** (`ExecRequest`): when and how received, who recorded it, what it obliges (CIV 5855(b), 4935(b) recited), and that it makes the agenda item executive; the reply as a day and a document reference, its body in the private view only.
- **Penalty-schedule check** (`PenaltyCheck`): the version in force on the violation day and its distribution record; the cap; a $150 amount with no recorded open-session finding reads "Not within CIV 5850(c); (d) asks a written finding in an open meeting" as a check; no schedule on file reads "No schedule of monetary penalties on file; jason states no penalty". Two readings of where the finding is made (5850(d)(2) open, 5855(b) executive) stay as "Two readings remain; the board asks counsel".
- **Decision notice preview** (`NoticePreview`, built): the notice as the `decision-notice` template renders it, with the address as the recipient shown only in the private view; the due day, delivery record (day, means, who), and overdue as a LEGAL step, recited.
- **The decision recorded by the secretary:** a `DecisionStep` (motion, mover, second, each director's vote by name, recusals, outcome) read from the decision record with links to `#/room` and `#/decisions`; the hearing row holds only the decision id. Draw the built entry as it is (findings, day, recorded by, `Confirm`) and the proposed link beside it. Draw "Stores disagree: changed since" as a difference, never reconciled.

### C4. The law review leads list (`#/law-review`, `?year=`)
The header counts (leads, read, conflicts proposed), the refresh dates, the `Command`, the filters (document, route, disposition, recorded already), and a `View [Leads | Conflicts]` switch.
```
| Law review 2099     Leads since [2099-01-01]  Document [all v]  View [Leads|Conflicts]            |
| Law refreshed 2099-01-04 (export) · outlines 2099-01-04 · 41 leads · 6 read · 2 conflicts proposed |
| Example Declaration  Section 7.3 (fake)  CIV 9999.1 amended, AB 9999 (fake)  subject  Not yet read |
|                      operative 2099-01-01 · 38 words added                                         |
| Example Declaration  Section 4.2 (fake)  CIV 9999.2 added                       cites    No conflict |
| Example Policy       Section 2 (fake)    CIV 9999.1 amended   recorded as C-3   subject  Conflict proposed |
| Example Rules (no written date)  CIV 9999.3 amended: every change since 2014 is counted: loose    |
```
The row's excerpt is the locator, marked "excerpt", never a recitation. Draw the empty states (no export; no change since the date; a store unreadable while the leads still show), the 200-lead MCP cap (the loader pages and never says "no more" from a capped list), and a document with no written date shown apart.

### C5. One lead (`?lead=ID`, a hash), four bands in a fixed order
**1 The law:** `Recitation` of the statute, "Before (in force 2098-12-31)" beside "Now (from 2099-01-01)", inserted words marked; where the earlier version is not on disk, "The earlier words are not on disk" with the command, nothing in its place. **2 The provision:** `Recitation` of the whole section, its written date. **3 Reading:** `ReadingLabel` jason's ("No reading on file"), then "Two readings remain" with both. **4 Disposition:** four choices (Not a conflict, A renumbering read as its successor, A Conflict row proposed, A question for counsel), a required reason, "Record as NAME" behind `Confirm`, the history newest first (`RecordTrail`), "Board item: none [Put on the board's agenda]". Below 768 px Before and Now stack, the statute first. Draw: a changed digest ("The words changed since NAME read them on 2099-01-09"; the lead returns to Not yet read), a stale reading, a refusal of an empty reason in the writer's sentence, and a director reading the same page the secretary does.

### C6. The Conflicts list (`?view=conflicts`) and a row opened
Columns: provision, yields to (since), part that yields, meanwhile, clarity (`plain`, `unclear`, `renumbered` shown as "no conflict of substance"), status (`noted`, `counsel`, `board`, `resolved` with `resolved_by`), board item. A row opens bands 1 and 2 (provision and authority recited), then `says`, `extent`, `apply` under "jason's note, not the provision". Read only: a `Conflict` row is a profile edit a person commits. Draw the caveat verbatim: "jason notes a conflict; only the board, counsel, or an amendment resolves one." No "resolve", "approve", or "adopt" control.

### C7. The run side
Draw the `PartOfRunBanner` on `#/law-review?lead=` ("Part of run Law review 2099, step 7: Read each lead beside the statute") and on the hearing detail (general words only, held); the l6 and l7 step panels embedding the leads list read only, the hearing's h7 attestation panel, and the run-links chips for `decision` and `board-item`. Reference the Work frames; do not redraw them.

## D. The shared components, each once

Reuse built parts and the three board-records pieces by reference. Specified here, to build from them:

| Component | What it is | Data | States |
|---|---|---|---|
| `HearingRunHeader` | Label, state, Private view switch with its reason | `{label, state, privateView{on, reason}}` | off; on; refused (no level) |
| `CureRecord` | Cure or commitment, evidence, who, a second confirms | `cure{state, on, evidenceRef, recordedBy, confirmedBy}` | none; cured; commitment; unconfirmed; same person refused |
| `ExecRequest` | The member's request and what it obliges | `execRequest{on, how, recordedBy}` | none; received; makes the item executive |
| `PenaltyCheck` | Schedule version, cap, finding | `penalty{kind, amountCents, scheduleVersion, distributedOn}` | within; over the cap, no finding; no schedule on file |
| `RequirementsList` | The 5855(g) list | `requirements[]{label, state, basis}` | met; open; not on record; never "effective" or "void" |
| `HearingNoticeDelivery` | Decision-notice due, delivered | `decisionNotice{dueBy, deliveredOn, by, means}` | upcoming; delivered; overdue (LEGAL, recited) |
| `LeadList` | The leads table | `Lead` and `Change` fields | the states in C4 |
| `LeadReader` | Bands 1 to 4 | statute, provision, reading, `acts[]` | before missing; changed digest; stale reading; refused write |
| `DispositionForm` | The four choices, reason, `Confirm` | `by` from the session | pick; recorded; refused; admin view |
| `ConflictRows` | The Conflicts table and its opened row | `Conflict` fields | the four statuses and three clarities |
| `PartOfRunBanner` | The one-line pointer (run-links) | `runs[]` | one; several; held; draws nothing on failure |

**Fixed words** (use exactly): "the hearing must move", "The board shall not impose discipline" (recited, not paraphrased), "No schedule of monetary penalties on file; jason states no penalty", "Not within CIV 5850(c)", "In the private view", "computed by jason from the statute's day-count, the earliest day", "Two readings remain", "jason's note, not the provision", "No reading on file", "The words changed since NAME read them on DATE", "Say what you read and why, and who is recording it.", "jason notes a conflict; only the board, counsel, or an amendment resolves one.", "Viewing as NAME (admin view): go back to yourself first". Never "approve", "impose", "send", "resolve", "adopt" on a button; never "violation found", "effective", "void", "compliant".

## E. Glyphs

Use the console's glyphs beside their words: `lock` (private view, held), `eye-off` (hidden outside the private view), `clock` (upcoming), `triangle-alert` (past a legal day, the hearing must move), `circle-check` (met, recorded), `circle-question-mark` (not on record, not yet read), `circle-dashed` (not started), `scale` (counsel reads, two readings), `history` (acts), `link` and `paperclip` (evidence, board item), `minus` (none). Propose a new one only where none says it, named for the idea: a **computed day** mark (a calendar with a small count tick: "computed by jason, the earliest day", which must never read as a stamp) and a **two readings** mark (a scale with both pans occupied).

## F. Decisions that are the design's, in one list

1. **The hearing page:** one long scroll of eight bands with a sticky band index (recommended) or the Work rail; and where the clock strip sits.
2. **The private view's presence:** a header switch with the stated reason, and how a held band reads (a sentence, never a blank).
3. **How the 5855(g) list reads** without a verdict: met, open, not on record as words and glyphs, with the statute's words recited above it.
4. **The two Recitation-and-Reading frames** on narrow screens: stacked, statute first.
5. **How inserted words show** in "Now" without a `DiffTable` (marks and a legend).
6. **Leads grouping:** by document then operative date (the loader's order, recommended) versus by statute change; and the Conflicts list as a tab or a view.
7. **The `Confirm` wording** for each act (cure, request, reply, delivery, disposition) and whether a document shows a preview in the dialog.
8. **Print:** the hearing history for the board (private view only) and the year's dispositions for the packet, every computed day labeled.

These are not the design's: who confirms a cure, whether the decision store is merged, the run id's form, where the penalty schedule lives, the 5850(d)(2) reading, who records a disposition, whether a second reader is needed, and the cadence.

## G. What can be designed now, and what waits

| Part | Now | Waits on |
|---|---|---|
| The hearings list and the three privacy frames | Yes, from the sample | The loader's masking (today it sends the address) and the opaque id |
| The run page, bands 1 to 8, the variants | Yes | The `hearing` definition (not registered), the run record `data/board/hearings.json`, and held-run handling in `work.py` |
| The decision entry and notice preview | Yes; built | One decision store (decision 1 of the spec) |
| Penalty check | Yes, with "no schedule on file" as the first state | A `Community` method for schedule versions |
| Suspension path | No | Corporations Code 7341 is not on the shelf |
| The leads list, one lead, the Conflicts list | Yes | Loaders `conflict-leads`, `conflicts`, `cite`; the dispositions store and writer |
| `PartOfRunBanner` | Yes | The `run-banner` loader |
| The law-review run page (l1 to l14) | Yes | The `law-review` definition (not registered) |

## H. A made-up community to design against

"Oakview" (no real association). Today is **2099-11-06**. Roster: Dana Example (president), Pat Example (secretary), Robin Sample (manager), Lee Sample (treasurer), Sam Example (director), Kim Example (an administrator with no office), A. Owner (the member, Unit U-14, private view only), and Example Counsel (read on grant). Ours is a fake community; statute words are placeholders for the stored text.

**Hearing H-7:** matter "Item left in a common walkway (fake)", violation day 2099-10-02, proposed penalty $50 under schedule v2099-1 (distributed 2099-01-15), hearing 2099-11-17, notice by 2099-11-07, notice delivered 2099-11-05 by personal delivery (manager's statement), executive session requested 2099-11-06 (recorded by Pat Example), no cure, no reply, agenda item 4, decision notice due 2099-12-01 once decided. Variants to draw: **late notice** delivered 2099-11-08 ("the hearing must move"); **cure recorded** 2099-11-09 (closed "no discipline", Lee Sample confirms); **over the cap** $150 with no open-session finding; **no schedule on file**; **two readings** of the 5850(d)(2) finding; **decision recorded** 2099-11-17 (d-2099-11-17: motion, Sam Example, Dana Example, votes by name, one recusal) with the notice delivered 2099-11-29 and then **overdue** on 2099-12-02; **stores disagree** (hearing row and decision store); the private view off, and Lee Sample, Sam Example, and Dana Example each reading the same fields; Kim Example with controls replaced; A. Owner refused.

**Law review 2099:** export refreshed 2099-01-04. Documents: Example Declaration (written 2090-03-12), Example Policy (2095), Example Rules (no date). Changes: CIV 9999.1 amended (AB 9999, operative 2099-01-01, 38 words added), CIV 9999.2 added (SB 8888, operative 2099-07-01), CIV 9999.3 amended (no bill known). Leads: Example Declaration Section 7.3 against 9999.1 ("An Owner may lease for not less than ninety (90) days" vs a 30-day floor in the placeholder statute, both fake), route subject, not yet read; Section 4.2 against 9999.2, cites, no conflict (read 2099-01-09 by Robin Sample); Example Policy Section 2 against 9999.1, recorded as C-3, conflict proposed; Example Rules, for counsel. Conflicts: C-3 (Example Policy 2, plain, board item BI-7) and C-4 (Example Declaration 4.2, for counsel, BI-8, meanwhile "the course lawful under either reading"). Frames: the earlier version not on disk; a stale reading; a digest changed since read; 241 leads paged past the MCP's 200; no export; a refused empty reason.
