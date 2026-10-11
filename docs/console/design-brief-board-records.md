# Design brief: the board's records (elections, collect items, incidents)

One page of orientation for the design agent, for three screens that share one pattern: [screens/elections.md](screens/elections.md) (`#/elections`), [screens/collect-items.md](screens/collect-items.md) (the tracker inside a run step, and the packet's Collect tab), and [screens/incidents.md](screens/incidents.md) (`#/incidents`). It does not repeat the specs; it says what to read in what order, what to draw, the shared pieces once, what is built and what has no view, and a made-up community to draw against. Where a spec and this page disagree, the spec and the code win, and this page is corrected. Reuses the vocabulary of [design-brief-work.md](design-brief-work.md) and the deficiency register in [design-brief-life-safety.md](design-brief-life-safety.md).

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, insurer, or private fact; made-up samples only ("123 Main St", "Example Alarm", "A. Candidate", 2099).

**Checked against the code on 2026-10-11.** No view exists for any of the three: `ui/src/App.tsx` has no `elections`, `incidents`, `work`, or `life-safety` route, and `ui/src/views` has no file for them. Nothing of their own stores exists: no `data/elections/`, `data/incidents/`, `collect.json`, no `jason elections` command, no `jason://election/` or `jason://incident/` address, no `jason.tasks.incident_records` or collect module. No `election`, `loss-claim`, or `fiscal-year` definition is registered. **Built and behind them:** the run library (`jason.workflows`: types, append-only store, fold, resume, per-item steps with `Repeat.PER_ITEM`; `LinkKind` has no `incident`, a `doc` link is the stopgap); the notice catalog and `ElectionKind`; `data/authorities/CIV/CIV-5100-5145.md` and `CIV-5200-5240.md` (present on this machine, ignored by git); `jason.tasks.decisions`; `jason.tasks.deficiencies` with its writer `POST /api/write/life-safety/<id>` and `jason life-safety`; `incident_history`, `jason incidents --link`, and the loss-packet loader and its one write. **Built components** (`ui/src/components`): `Card`, `DataTable`, `Pill`, `Badge`, `Glyph`, `Seal`, `Confirm`, `ConfirmList`, `SecondConfirm`, `Command`, `Doc`, `DueDate`, `Clock`, `Timeline`, `Recitation`, `ReadingLabel`, `Caveats`, `Evidence`, `EvidenceEntries`, `HeldNote`, `Stat`, `Tabs`, `Findings`, `QuestionCard`. **Not in the folder:** `TerminalStep`, `AgeStamp`, `BasisPill`, `PriorityPill`, `DeficiencyRow` (specified only). A name clash to avoid: `ui/src/views/RecordTrail.tsx` is the record-intake acts file (`SlotWord`, `ActPanel`); the shared table below is `RecordTrail` in `components/`, so build it as `components/RecordTrail.tsx` and import it by path (or rename it).

## A. The idea, and the rules that run through it

**The idea, in six sentences.**

1. A person **records what happened or what was received**, in their own name, and the record only grows: a correction is a later act, nothing is edited or deleted.
2. Each screen **reads and never decides**. The inspector reports and the board decides (elections); a person gives and another confirms (collect items); a person says what they saw and the carrier and counsel say the rest (incidents). jason sends, counts, files, and asks no one.
3. **Nothing is assumed present.** A thing not received is waiting. A waiver always carries a reason and never reads as "present", "done", or "n/a" alone.
4. **Evidence is linked by address** (`library:4002`, `jason://notice/KEY`, a decision id, a report's digest), never copied, and a record that is P2 or P3 is shown by kind and title only outside the level that opens it.
5. A **run points at the record; the record does not hide in the run.** The run holds steps and links; the record holds the facts (decision 1 of the elections spec).
6. Every date says **whose** it is, and every statute is recited before any reading of it.

**The rules** (each is in a spec; a screen that breaks one is wrong):

- **Directors and officers have the same access to information.** There is no director-only or counts-only view among the offices that open the level; a viewer whose office does not open it gets counts and a `held` sentence (`HeldNote`), with a dash and its reason for a count withheld, never a zero.
- **The secretary records the board's decisions.** A vote, a motion, or an acclamation shows as read from the decision record (motion, mover, second, outcome); no control casts, changes, or adopts one.
- **The election console records only what the independent inspector of elections reports.** jason runs no election, counts no ballot, shows no individual ballot, no envelope, no list of who returned one, no running tally before the count. The inspector is outside the console and never signs in. No button reads count, tabulate, declare, certify, approve, adopt, or vote.
- **A candidate may not record or confirm their own election.** This is a **proposed policy for the board**, not a rule: draw it with the `proposed policy` basis word and the sentence "Proposed for the board's adoption. Until adopted, the screen refuses it as a precaution, and says so." The refusal is the writer's own sentence beside the control.
- **A statute is recited whole, from `data/authorities`, before any reading** (`Recitation`, then `ReadingLabel` with whose reading). When the shelf is absent the block reads "recited from the shelf", the section, and the export command; no quote is written from memory. Where the law is unclear (several points in the elections spec, decision 11) the page says "counsel reads this" and shows both readings or neither.
- **A record is a person's word, not a finding.** An incident's cause, an item's value, and a nominee's status are what someone recorded, with their name; none is jason's conclusion about cause, cover, fault, or who won.
- **A proposed number is never a stamp.** A day jason computes (a collect item's due day, a retention end, a retention policy) wears `PROPOSED`; a legal day wears `LAW`, with the statute recited beside it. "Past due 3 days" is a word beside a date, not a state.
- **Acts are the signed-in person's own,** behind a `Confirm` that says what will be recorded and under what name. An administrator viewing as someone else sees "Viewing as NAME (admin view): go back to yourself first" in place of each control.
- **State is a word and a glyph, never colour alone.** The words are the folded ones (list in D), never invented.
- **A free-text field refuses an email address or a phone number,** and names no resident, voter, or medical detail.

## B. Reading order

1. The three specs, in this order: [incidents.md](screens/incidents.md) (smallest), [collect-items.md](screens/collect-items.md), [elections.md](screens/elections.md) (largest, most rules).
2. [../workflows/board-governance.md](../workflows/board-governance.md) section 2.3 (steps e1 to e18) and its failure table; [../workflows/money.md](../workflows/money.md) section 2.5 (step D3); [../workflows/property-safety-vendors.md](../workflows/property-safety-vendors.md) section 2.8 (`loss-claim`, step `record`) and 2.2 (the deficiency steps).
3. [screens/work.md](screens/work.md) and [design-brief-work.md](design-brief-work.md): the run page, the step panel, and `BasisPill`, `RunLinks`, `Confirm`. These screens are linked from a run; do not redraw it.
4. [design-brief-life-safety.md](design-brief-life-safety.md) sections C3, D, and F: the deficiency card, its acts table, `ActTrail`, `PriorityPill`, `DeadlineCell`. The three records are the same shape.
5. This page's section D beside section H.
6. [handoff-annual-disclosures.md](handoff-annual-disclosures.md) (`CollectList`, `CollectItemRow`, `StandingValueRow`) for the packet tab's wording.

## C. The screens

### C1. Elections list (`#/elections`)
`ScreenHeader` with the summary ("2 elections on record, 1 in progress, 1 closed, materials kept until a date"). One row an election: label, kind and seats, the next date with its basis, the inspector (set or not), and where the materials are (`CustodyLine`). Draw: a directors election mid-run, a member vote closed with its report filed, the empty state ("No elections on record. The inspector's reports of past elections are in the library; open one to record the next." Never "no election was held"), and a "term ended; election due" arrival from People.

### C2. One election (`?id=`), seven bands in the order the work runs
Header: label, kind, `jason://election/ID [copy]`, opened by, CLI. Then: **1 Rules and standing facts** (version in force; each fact with its record; "undetermined" shown as undetermined, never "no"; the 90-day check passes or blocks); **2 Dates** (`ElectionTimeline`: each date with the notice day it forces and its basis word; a passed day reads PASSED in the law's words and opens a follow-up); **3 The inspector** (`InspectorCard`: outside the console; the independence statement as a `Doc`; "whether the inspector is independent is not jason's call"); **4 Nominations** (`NominationRow` per nominee: received, acknowledged, qualified with basis; a member vote swaps this for **The measure**: the text sent with the ballot and the threshold in the documents' and the law's words); **5 Notices** (catalog key, last day, delivery counts, a link, "Plan in Approvals"); **6 Voting and the count**; **7 Seats and materials**. Close with the caveat verbatim in `Caveats`.

Band 6 is the band to get right. Before the count it is a deliberate, labeled blank: dates, and "Nothing is shown before the count: no ballot, no running tally, no list of who has returned one." (a locked panel, not an empty table that invites a number). After the report: `ReportEvidence` (the inspector's report as a `Doc` with its digest and day received) beside the results as `TypedCount`s, each labeled "Typed from the inspector's report; jason has not counted or checked it", **unconfirmed** until a second, different person confirms. A measure shows the inspector's reported outcome and the threshold in words; jason shows no "carried". Draw: the report edited since filed ("EDITED since filed"), the report not in hand ("waiting on the inspector's report"; no seat recorded from a name alone), and no quorum (the reconvened-meeting notice row opens; materials stay with the inspector).

### C3. The election's acts
Open, record rules, record the inspector, set the dates (refused inside 90 days of the count, and for a passed notice day), record a nomination / acknowledgment / qualification (a disqualification needs a basis and the appeal route), link a notice, record the report, record an acclamation (only when an approved decision names each qualified candidate: a link to Decisions, no vote control), record the seats (hands to the existing two-person onboarding confirm), record the materials transferred, move, reconvene, cancel, note. Each is a `Confirm` with the writer's refusal beside the field.

### C4. Collect items (inside a run step: `#/work/<definition>/<id>?step=ID`, and the packet's `?tab=collect`)
`CollectTracker` heads: counts by state, the outer edge (a `LAW` window close) and the items' due day (`PROPOSED`). Rows grouped by the person asked, then by due day, a legal edge before a proposed one, an item with no day last. A row: what, the provision it answers, asked of (role: "proposed, not adopted" or "adopted DAY"), when and how, due by, `StateWord`, and the controls that state allows. Row states: not asked, asked, received (awaiting a person), confirmed, waived; draw one each, plus a statement entered but "not yet adopted", a file changed since confirmed (old and new digest), and a due day "date not on record". Expanding a row opens its `RecordTrail`. The same component sits in the run's step panel (a `person` step of the run, per item) and the packet tab (with the packet's wording); draw it once and show both frames.

### C5. Incidents list and record (`#/incidents`, `?id=`)
List: counts, filters (state, building, cause, "has no run"), a row per record with the found day, the place, what and the person's cause word, `ActiveBanner` if active, and its links. One record: the header (`jason://incident/ID`, recorded by, state, age); **1 What, where, when** (the person's words; amendments listed beneath, not overwritten); **2 What the paperwork shows** (read from repair paperwork, not from this record; a lead, with a link picker); **3 Links** (the `loss-claim` run and its step, the loss packet, the deficiency register row, a board item); **4 History** (`RecordTrail`). Draw: active water (the banner, "The run's mitigate step cannot be skipped", not "stopped"), a withdrawn record (dimmed, the reason, never removed), no paperwork report ("run `jason incidents` first"), a place that matches no unit ("no unit matches"), and a linked deficiency now cleared. A viewer whose office does not open P2 sees counts only.

### C6. The run side
A run links to each record as a `RunLinks` chip (kind, id, state, label). Draw the chip for an election (`election` run step e5), an item set (a collect step "3 of 6 confirmed"), and an incident (`loss-claim` step `record`). The run step that needs a record refuses without it, in the definition's sentence (design-brief-work, section A).

## D. The shared components, each once

Reuse (built): the list in the opening paragraph. Everything below is to build from them; do not draw a screen-only copy of a shared piece.

| Component | What it is | Data | States |
|---|---|---|---|
| `RecordTrail` | The record's acts as a table (the deficiency card's trail, generalized): who, when, the act word, what it said, its evidence | `acts[]{act, by, at, day?, detail, evidence[], corrects?}`; `state` folded by the loader | one act; many; a correction as a later row marked "corrects NAME's entry of DAY", the earlier value kept and dimmed (not struck); the **current** word on each question marked; a system act ("jason, listed from the plan") |
| `EvidenceLinks` | A strip of address chips for what backs a row | `evidence[]{kind, title, address, sha256?, level, state}` | in the library; with a digest (first twelve characters); **EDITED since filed**; **not on file**; **not in the library**; a P2 or P3 file shown by kind and title only; never a path or a `/api/file` link |
| `RoleLine` | Who is asked, who recorded, who confirmed, and why a control is missing | `{askedOf{role, adoption}, recordedBy, confirmedBy, viewer{name, viewingAs, onCandidateList}}` | role "proposed, not adopted"; recorded and confirmed by the same person (shown, and refused where a second is required); "Viewing as NAME..." replacing the controls; "A candidate on this list may not record or confirm this (proposed policy)"; "Waiting on the NAME/OFFICE" |
| `TypedCount` | A number typed by a person from a document, with its source | `{value, label, source{doc, sha256}, typedBy, at, confirmedBy?}` | typed, unconfirmed; confirmed by a second person; source edited; source missing (reads unconfirmed); never styled as a computed result |
| `BasisPill` | The five clock bases (shared with Work) | `law, documents, counterparty, proposed policy, person` | five words with glyphs; `proposed policy` never looks like `law` |
| `StateWord` | A `Pill` preset per closed set | elections: `draft`, `in progress`, `report filed`, `results confirmed`, `closed`, `cancelled`; items: `not asked`, `asked`, `received`, `confirmed`, `waived`; incidents: `open`, `closed`, `withdrawn` | a word and a glyph; an unknown word shown plainly |
| `ProposedPolicyNote` | The labeled box for a policy the board has not adopted | `{text, basis: "proposed policy", adopted?}` | proposed; adopted (names the decision); refusing an act under it |
| `RecordHeader` | Id, copyable `jason://` address, recorded by, state, age | `{id, address, by, at, state}` | open; closed; withdrawn; cancelled |
| `WriteConfirm` | The `Confirm` for an act, with the writer's refusal beside the field | `{act, fields, says, refused?}` | pick; recording; recorded; refused (the sentence); admin view; "the act is recorded; the run was not written: WHY" (the tracker or record stands) |

Screen-specific (each once): elections: `ElectionTimeline` (dates, each with the notice day it forces and its basis; built from `Clock` stages), `InspectorCard` (no controls for the inspector's work), `NominationRow`, `ReportEvidence` (a `Doc` plus digest plus day received), `CustodyLine` (who holds the materials, until when, both retention readings). Collect: `CollectTracker`, `CollectItemRow`, `GiveForm` (a value, cents, a date, a statement, or a library file, with its **source** required), `WaiveForm` (reason required), and `StandingValueRow` from the handoff. Incidents: `IncidentForm`, `IncidentRow`, `IncidentLinks`, `EventLinkPicker`, `ActiveBanner`.

**Fixed words** (use exactly): "waived by NAME on DAY: REASON", "the element reads waiting", "Typed from the inspector's report; jason has not counted or checked it", "Nothing is shown before the count", "unconfirmed", "EDITED since filed", "report not on file", "proposed policy", "PASSED", "a person linked these; it is not a finding about cause or fault", "A record is a person's word. It is not a finding about cause, cover, or fault.", "Entering an item records what a person says; it adopts nothing and sends nothing.", "jason records what the inspector reports. It runs no election, counts no ballot, and decides nothing; the board decides.", "Viewing as NAME (admin view): go back to yourself first". Never "count", "tabulate", "declare", "certify", "approve", "adopt", "vote" on an election control; never "present" for a waiver; never "violation", "at fault", or "covered".

## E. Glyphs

Use the console's glyphs, each beside its word: `circle-check` (confirmed), `badge-check` (confirmed by a second person), `clock` (waiting, upcoming), `triangle-alert` (past due, PASSED, active), `octagon-alert` (EDITED, blocked, refused), `circle-dashed` (not asked, report not on file), `circle-question-mark` (undetermined, not yet recorded), `lock` (held, before the count), `eye-off` (never shown), `paperclip` and `link` (evidence, links), `history` (the acts), `minus` (none), `scale` (counsel reads). Propose a new glyph only where none says it, and name it for the idea: a **waived** mark (a circle with a bar, which must never be read as a check), a **typed from a report** mark (a document with a quotation tick, which must never read as verified), and the **proposal** mark already asked for in the life-safety brief.

## F. Decisions that are the design's, in one list

1. **`RecordTrail` order:** newest first (Work's history, the incident spec) or oldest first (the deficiency trail). One order for all three; recommended newest first with the current word marked.
2. **How "the latest word wins" shows** without strikethrough: a "current" word, the replaced value dimmed, "corrected by NAME" on the row.
3. **The election page:** one long scroll of seven bands with a sticky band index (recommended) or tabs; and how band 6 draws "nothing before the count" so it reads as a rule, not a bug.
4. **How the candidate refusal reads:** beside the control, in the `ProposedPolicyNote` words, as a precaution of the screen and not a finding about the person.
5. **The collect row:** a table row that expands (recommended) or a drawer; and how one component serves the run's step panel and the packet tab.
6. **The `Confirm` wording** for each act (drafts in the specs), and whether a library file shows a `Doc` preview in the dialog.
7. **Narrow screens:** rows become cards (state word, what, date); the election bands stack; the acts table keeps who and when.
8. **Print:** the election record for the minutes (dates, notices, the report's digest, the typed results as unconfirmed or confirmed, custody) and the collect list for the packet, every proposed day labeled.

These are not the design's: who may record or confirm (the offices that open the level), whether the board adopts the candidate policy, the retention rule, who qualifies a nominee or selects the inspector, whether "late" is a state, and the questions the specs list for counsel.

## G. What can be designed now, and what waits

| Part | Now | Waits on |
|---|---|---|
| The three lists and the incident record | Yes, from the sample | The stores (`data/incidents/records.json`, `data/elections/<id>.jsonl`, `collect.json`), their loaders, and the views |
| The election's seven bands | Yes | `jason.elections` (`runs`, `show`), the `election` definition (build step 8 of board-governance), a small generalization of `workflows/store.py` |
| Recited statutes | Yes; the shelf holds CIV 5100-5145 and 5200-5240 here | A build with no shelf reads "recited from the shelf"; draw that state too |
| The recall kind | Draw the kind only | The recall's own Corporations Code section is not on the shelf |
| Collect tracker in a run step | Yes | Items are fixed at the run's `opened` event, so a late item needs a child run or an `items-added` event (collect-items decision 1) |
| The packet's Collect tab | Yes | `GET /api/annual-collect`, the annual packet module |
| The incident's paperwork section and loss packet | Yes; both are built reads | Event ids (links are day + address + claim numbers); a loss-packet confirmation write that appends rather than replaces |
| A run's link chips | Yes | `LinkKind` has no `incident`, `election`, or `collect`; the `doc` link is the stopgap |
| Writes | Draw the `Confirm`s | The signed writers (`POST /api/write/...`) for each store |

## H. A made-up community to design against

"Hillcrest" (no real association). Roster: Pat Example (secretary), Robin Sample (manager), Lee Sample (treasurer), Sam Example (a director, and a candidate), Dana Example (president), Kim Example (an administrator with no office), A. Owner (an owner, no access).

**Election "Directors 2099"** (as of 2099-03-10; two seats; kind `directors`): rules of 2097-06-01 in force; electronic ballots opt-out, quorum required, acclamation not available (a board decision of 2098-09-15); Independent Inspector Co. selected Dec 1 by the board, one inspector, independence statement on file; call for candidates by Jan 28 `LAW`; nominations close Feb 27 `PERSON`; pre-ballot notice by Mar 2 `LAW`; ballots out Apr 1 `PERSON`; delivered by Apr 4 `LAW`; voting deadline May 4; count May 5; results notice by May 20 `LAW`; retention to at least May 5, 2100 `LAW`. Nominations: A. Candidate (received Feb 3, acknowledged Feb 5), B. Candidate, C. Candidate, all qualified; B. Candidate is the director Sam Example (draw the refusal when he opens "Confirm the results"). Notices: nomination-procedure delivered Jan 20 in time; pre-ballot delivered Mar 1, 48 of 48 reached; ballots owed. After the report (draw as a second frame, as of 2099-05-06): A. Candidate 21, B. Candidate 17, C. Candidate 9, ballots 48, `inspector-report-2099.pdf` sha256 `4b1c...9e0a`, results unconfirmed until Lee Sample confirms. A second election, "Member vote: amendment" (closed, report filed Oct 5, 2098, materials with the inspector), to draw the measure band with no nominations.

**Collect items** (run `2099-fy`, step D3, as of 2099-04-23; outer edge May 31 `LAW`; items due Apr 20 `PROPOSED`):

| Item | Answers | Asked of | State | Point it makes |
|---|---|---|---|---|
| Example reserve summary pages | CIV 9901(b)(2) | A. Treasurer (role proposed, not adopted), Feb 20 by email | asked, past due 3 days | The late word; no "late" state |
| Example insurance terms | CIV 9901(b)(9) | A. Manager, in person | received, awaiting a person; file `declarations-example.pdf` `9e2f4b7c1d0a` | Digest, source, Confirm by another person |
| Example board statement | CIV 9901(b)(4) | A. Secretary, in meeting | confirmed; "entered by A. Secretary; not yet adopted" | A statement adopted nowhere on record |
| Example posting place | CIV 9902(a)(3) | A. Manager | waived Mar 2: "does not apply this year (see the applicability answer)" | A waiver with a reason; the element reads waiting |
| Example mailing day | none yet | not asked | not asked | The first control: "Record who was asked" |
| Example statement kept from last year | CIV 9901(b)(1) | A. Secretary | received, then "changed since confirmed" (the file's digest differs) | A confirmed item that moved |

Also a second run, "Example run", with three items (the tracker works for any definition).

**Incidents** (as of 2099-03-11): `inc-2099-0007`, recorded by Robin Sample Mar 2 09:14: "Water on the ceiling of the hallway, stain spreading", cause (their word) plumbing leak or overflow, 123 Main St, Building 4, unit interior, found Mar 2, happened unknown, active yes, injury flag no, one photo. Links: run `work/loss-claim/2099-03-a` (step 4 of 11), loss packet (5 steps, 2 confirmed), deficiency `def-3f9a` (open, a person linked it). Paperwork: 2 events at 123 Main St; earlier, Jan 2098 plumbing leak, claimed; standing "sudden, cost unknown" (a lead). `inc-2099-0004` (Feb 11, common area gate, vehicle collision, no links) and one withdrawn record with its reason. Frames: the active banner; Sam Example reading the same record as Robin; Kim Example (counts only: "5 records, 3 open"); A. Owner refused; no paperwork report; an amendment (cause changed, reason given, earlier value kept).
