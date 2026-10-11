# Design brief: the governance calendar (the meeting clocks, the schedule by role, record stages, and how a board-meeting run links to them)

One page of orientation for the design agent, for the clocks the board's year runs on. It does not repeat the specs; it says what to read in what order, each screen and component to draw, what is built and what is not, and a made-up community to draw against. The specs are [screens/meetings-and-minutes.md](screens/meetings-and-minutes.md), [screens/schedule-and-duties.md](screens/schedule-and-duties.md), the bands in [screens/today.md](screens/today.md), and the `board-meeting`, `rule-change`, `duty-schedule`, and `law-review` definitions in [../workflows/board-governance.md](../workflows/board-governance.md). Checked against the code on 2026-10-11 (the loaders in `src/jason/web/sources.py`, the views in `ui/src`, the tasks and the CLI).

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, bank, or private fact; made-up samples only.

## A. The idea, and the rules that run through it

**The idea, in six sentences.**

1. Every board meeting starts two clocks the law sets, **the notice to members** (CIV 4920) and **the minutes made available** (CIV 4950(a)), and the board's year is those clocks plus the duties the schedule assigns to a role.
2. The screens answer one question per clock: **which day does it end, whose is it, and what is on record against it?** A date is always drawn with its **basis**: `law`, `documents`, `proposed policy`, or `person`.
3. **None on record is not none given.** A notice posted, or minutes made available, where jason does not look is not on disk. An open clock stays open, in words, until a person records what was done, and then the watch counts it.
4. The schedule turns each duty into dated occurrences by role. An occurrence is **done only when a person records it, with evidence, in their name**. A duty no assignment covers is a finding, not an empty row.
5. A rule change and a set of minutes each move through **stages**, read from the files and ledgers on disk: stated, or only listed.
6. jason posts, sends, and approves nothing here. A person acts, behind a `Confirm`, and the run in Work reads these screens and links the act.

**The rules** (each is in a spec; a screen that breaks one is wrong):

- **Directors and officers have the same access to information.** There is no director-only or counts-only view; they differ in duties. The secretary is the official record keeper: the board's decisions, the postings, and the minutes' availability are recorded by the secretary or the assignment's role (the server enforces it), never by a click on a run page.
- **Open and executive session are drawn apart** (CIV 4935). Outside the private view an executive item or session shows its **general words** only, in the statute's subjects, never a title, a name, or an id. The minutes name the matter generally (4935(e)). A meeting held solely in executive session owes no open minutes.
- **Every date has a basis word.** Law and documents dates are stamps of a rule; a **proposed policy** date (the packet a week ahead, "start drafting minutes soon", the monthly read, the January law review) is labeled "proposed, not the law's" and never drawn as a stamp. Adoption is the board's: an assignment reads "proposed, not adopted" until it is adopted.
- **A statute's words are recited, then read.** `Recitation` first (from `data/authorities`: jason's consolidated text, not an official restatement), then any reading in a `ReadingLabel`. Never a paraphrase, a heading, or a tooltip in place of the words.
- **The 30 days is the law's** (4950(a)); **"start drafting soon" is a proposed policy.** Draw them as two different marks on the strip.
- **Standing is a word and a glyph, never colour alone.** The words are the engine's own; the page invents none.
- **No verb the page must not have.** The only acts are "Record a posting", "Record the minutes made available", "Record done", and "Re-check". "Post minutes", "approve minutes", "send", "adopt", and "resolve" are on no control.
- **A record is signed and appended.** It needs a name and the evidence; a refusal keeps what was typed; a correction is a later record with a note.
- **The owner view** shows only the open-session records that are posted (notice, agenda, minutes) and the annual disclosures; never a clock, a check, a schedule, or a gap.

## B. Reading order

1. [screens/meetings-and-minutes.md](screens/meetings-and-minutes.md): the watch, the checks, the stages, "The meeting room's executive session". Then [screens/schedule-and-duties.md](screens/schedule-and-duties.md).
2. [screens/today.md](screens/today.md) (the "Needs attention" and "Your work" bands).
3. This page's section D beside section H.
4. [../workflows/board-governance.md](../workflows/board-governance.md) sections 2.0 (the `decision` step), 2.1, 2.2, 2.6, 4 (the clocks and their basis), 9 (a sample run).
5. [screens/work.md](screens/work.md), "Where a step's work happens", and [design-brief-work.md](design-brief-work.md) (`ClockStrip`, `BasisPill`, `RunStepPanel`). [screens/law-review.md](screens/law-review.md) only for the January occurrence's link.
6. [design-gaps.md](design-gaps.md) rows G1, G3, G5.

## C. The screens

The calendar is not one new screen. It is **bands added to built screens** plus one composed view. Names below are the built views (`MeetingsView`, `MeetingView`, `DutiesView`, `CalendarView` for `#/disclosures`, alias `calendar`); the specs call them `Console*`.

### C1. The clocks (a band on `#/meetings`)
Per meeting, newest last, from the watch window (30 days back to 60 ahead): the date, its kind (board meeting, or executive session only), why jason knows of it ("from the schedule", "held (Zoom record)"), then two clock rows. **Notice:** last day, the rule in words and the authority (CIV 4920(a); 4920(b)(2) for an executive-only meeting; a longer documents' period shows `documents`), the standing word, the record found and its date, and the notice's address (`jason://notice/KEY`). **Minutes:** the same, for 4950(a). Under each open clock, the owner ("Secretary, due Oct 3") and the act. Below: the scheduled days with nothing on record ("if it was held, its minutes are due by ..."), and the four caveats verbatim, the first above the fold. Draw: ahead; due today; past with the first caveat inline; a file in time with no delivery on record; an executive-only meeting; the empty window.

### C2. The meeting strip (`MeetingStrip`, a header over `#/meeting` and a board-meeting run)
One meeting as a left-to-right strip: packet to directors, last day for the notice, agenda posted, the meeting, drafting starts, minutes available by, approval at the next meeting. Each mark has its date, a basis chip, and a standing word; the window between "notice by" and the meeting is drawn as a bar. No spec draws this beyond one line (board-governance section 5); it is built from `Clock`, `Pill`, `DueDate`.

### C3. The month view (composed; the design's own)
A month grid on `#/meetings` (a toggle beside the list) and in the dock's Deadlines drawer. A day shows its marks: a meeting, a notice-by day, a minutes-by day, a schedule occurrence, an annual disclosure. Each mark carries its basis chip and its standing word; a day with a legal mark says so. Tapping a day opens a list, not a popover. On a narrow screen the grid becomes an agenda list by week. It reads the watch, the schedule, and the calendar loaders; it invents no date.

### C4. Record a posting, and record the minutes made available (`Confirm`)
A dialog opened from an open clock. It shows the clock (the statute recited), asks **when and where** ("Posted on the clubhouse board, Oct 2, 9:00") and **who**, defaults the name to "Signed in as", and refuses without both: "Say what shows it was done: ...". The `Confirm` text: "Record that NAME posted the notice of the Oct 20 meeting, as stated above. This posts nothing and sends nothing." After saving, the clock reads "on record in time" or "on record late" with the person's name beside the standing, and the CLI equivalent is shown as a `Command`.

### C5. The checks beside the draft (`#/minutes-review`)
Two columns, the draft and "jason's checks" (`Findings`), checks first under 960 px. A check that names a line links to it. Order: a quorum the count does not support (shown first, with the correction), the quorum count, the motions, confidential lines, executive particulars, unsupported lines, blanks. **Re-check** reads again; no model. Every count is jason's, labeled so, never the minutes' words.

### C6. Record stages (a band on `#/meetings`)
**Minutes:** draft on file (date), available (the 30-day clock), approved (by the later minutes that state it) or "listed, not stated", corrected. **A rule change:** draft, proposed (the 4360(a) notice, 28 days), adopted (the board's decision at a meeting, 4360(b)), distributed (the adoption notice, within 15 days, 4360(c)), and the 30-day reversal window (4365(b)), each stage with its strongest record (`delivered`, `sent, with follow-ups owed`, `stated`, `listed`, `file`, `planned`) and a link to the notice. A stage with no record reads "none", a `planned` task never reads done.

### C7. The schedule by role (a band on `#/duties`)
A role filter and a window; one line of counts; a table of due day, duty, role, adoption word, standing (done, overdue, due soon, upcoming), and the act. A done row shows the record: the day, who, and the evidence as a chip. Group by role is a decision in F. A proposed assignment carries "proposed, not adopted".

### C8. Coverage and people's tasks
A band under the schedule: "41 duties assigned; 2 nobody owns", the unowned duties by name, and the duties on a clock only a standing assignment owns. An unowned duty is a finding for the board, not an empty cell. People's own tasks (read from Google) are replaced by their rule's label and are never marked or closed from here.

### C9. Record done (an attestation with evidence)
Opens in place on an occurrence: done on (a date), evidence (what shows it: the minutes' date and item, a payment, a notice proof), by (the signed-in name). `Confirm`: "Record that NAME did 'Reconcile the operating account', due Sep 30, on Oct 2, because: EVIDENCE." It writes one signed line and nothing else; a wrong record is corrected by a later one. Evidence is checked for secrets before it is stored. Contrary evidence found on disk goes to the board and records nothing.

### C10. Today's bands
"Needs attention" lines for the meetings and schedule sections (`[LEGAL] Notice of the Oct 20 meeting: 4 days left (Civil Code 4920)`), each opening the screen that owns it; "Your work" (the five nearest runs that are the viewer's move) with basis pills. Spec: [screens/today.md](screens/today.md).

### C11. How a board-meeting run in Work links to each
The run page **embeds reads and links writes** ([screens/work.md](screens/work.md)). Draw, for `board-meeting` (Oakview, section H): step m2 embeds the C1 rows for that meeting; m12 and m20 show the clock's record and a link to C4 (the record is the ledger's, so the step reads done when it arrives); m16 shows `DecisionStep` with the roll call by name and "Record in Decisions"; m18 and m19 embed the checks (C5) read only; m21 reads the stage (C6). Each owning screen shows "Part of run Board meeting Oct 20, step 12: Post and send; record the posting" linking back. A `rule-change` run's r9, r14, r16, and r17 embed the C6 rule-change rail the same way. `duty-schedule` d4 and d8 embed the C7 and C8 rows; d4 is C9.

## D. The shared components, each once

Reuse (built): `Clock` (stages with date, authority, done, who, note, evidence, and a decision diamond), `DueDate` (with `settled`), `Timeline` (provenance glyphs), `Pill`, `Findings`, `Caveats`, `Recitation`, `ReadingLabel`, `Evidence`, `Command`, `Confirm`, `Stamp`, `DataTable`, `Card`, `Tabs`, `DeadlineList`, `DecisionBrief`, `DecisionCard`, `Doc`. Not the same thing: `NoticeClock` belongs to the inspections family; `SourcedDate` has the paint family's four words, not the basis words. Specified, not built (draw from the built parts and say so): `BasisPill`, `WorkflowRail`, `ClockStrip`, `RunStepPanel` ([design-brief-work.md](design-brief-work.md)).

| Component | What it is | Data | States |
|---|---|---|---|
| `ClockRow` | One notice or minutes clock | `Clock.row()`: `what, requirement, authority, timing, deadline, standing, record, on, note, assignment, due, strength, notice` | ahead; today; past (legal); met; late; file only; undated |
| `StandingWord` | A `Pill` preset for the standing words | `Standing.value`; for a schedule, `standing` | the seven watch words; done, overdue, due soon, upcoming; `not running: no decision on record`; `does not apply`; an unknown word shown plainly |
| `MeetingStrip` | C2 | `WatchedMeeting.row()` plus the packet and drafting marks | ahead; held; executive only; emergency (no notice owed; the minutes are the evidence) |
| `MonthView` | C3 | marks from the watch, the schedule, the calendar | a month with a legal day; empty; narrow |
| `RecordForm` | The one dialog for a posting, the minutes' availability, and a done occurrence | `key, due, by, evidence, doneOn`; the clock or occurrence it answers | idle; refused (the sentence, text kept); recording; recorded; viewing as someone else (403, said so) |
| `RecordedLine` | "done Sep 12 by NAME" with its evidence | the completion row: `done, by, evidence, recorded` | present; absent; corrected by a later record |
| `ScheduleBand`, `ScheduleRow` | C7 | `items[]{due, standing, key, title, role, adoption, evidence, done}` | by role; proposed; empty window; no assignments |
| `CoverageBand` | C8 | `coverage{assigned, unassigned[], assignedNotScheduled[]}` | all covered; some unowned (named) |
| `StageRail` | C6, minutes and rule change | `stages{draft, proposed, adopted, distributed}`, `clocks[]`, `notices{}`, `outcome`, `reversal` | each strength; stated vs listed; reversed; emergency (no notice, no reversal) |
| `ChecksPanel` | C5 | `check_lines`, `quorum{inOffice, present, needed, standing}`, `claimsQuorum`, `confidential[]`, `executiveParticulars[]` | clean; a claimed quorum unsupported (first) |
| `RunEmbed`, `PartOfRun` | A read-only owning component inside a step; the banner on the owning screen | the run store | embedded; banner shown only to a viewer who may see the run |

**Fixed words** (use exactly): "None on record is not none given", "none on record yet", "none on record; the deadline passed", "a file in time; its delivery is not on record", "proposed, not adopted", "proposed, not the law's", "Record a posting", "Record the minutes made available", "Record done", "Re-check", "jason's checks", "listed, not stated", "unassigned".

## E. Glyphs

Use the glyphs the console already has. `Timeline` already carries the provenance set (proposal, badge-check, send, stamp, undo-2, lock): use it for stages (proposed, adopted, distributed, corrected, held). The standing words reuse the status glyphs (check, clock, alert triangle, question). New only where nothing says it, each named for the idea: **a meeting** (a calendar day), **a notice window** (a bracket bar), **a posting** (a pin), **minutes** (a page with lines), **a quorum** (people), **executive session** (the lock, already present), and the five **basis** glyphs from the Work brief. A diamond marks "the board decides", as `Clock` does.

## F. Decisions that are the design's, in one list

1. **Strip or month first.** Recommended: the strip on the meeting and the run; the month in the dock and as a toggle on `#/meetings`.
2. **What the clocks band folds.** All 90 days at once, or the open clocks first with met ones collapsed (recommended; a past, unmet legal clock never folds).
3. **Where the basis chip sits:** beside the date (recommended) or on the row's edge. Whichever, never colour alone.
4. **Schedule grouping:** one table with a role column and a filter (recommended) versus one tab per role.
5. **Stage rail direction** on a wide screen and on a phone (the minutes rail is 4 stages, the rule change's 4 plus a window).
6. **The `Confirm` wording** of each record, and whether the evidence shows as a `Doc` chip or text.
7. **How the packet and drafting marks differ from the law's marks** (a dashed outline, plus the words "proposed, not the law's").
8. **Print layout** of a meeting's clocks for the board's packet (`{REPORT:schedule}`).

These are not the design's: who may record a posting, the minutes' availability, or a completion (the assignment's role, enforced by the server); whether the board adopts the assignments and the proposed policies; which store a posting is written to; and whether m12 and m20 are attestations or read-and-link (the user's decisions, below).

## G. What can be designed now, and what waits

| Part | Now | Waits on |
|---|---|---|
| Records table, checks, scheduled-days-with-no-record (`#/meetings`), Next meeting, Plan, Room, Decisions, Minutes review, Rule changes, Hearings, Disclosures (`calendar`), the dock's Deadlines | Built; draw the new bands beside them | — |
| The watch (C1), the strip (C2), the month view (C3) | Yes, from `Watch.as_dict()` (the task `meeting_watch.watch` is built) | The loader `meeting-watch`: **not registered** |
| Record stages (C6) | Yes; `record_stages.histories` is built | The loader `record-stages`: **not registered** |
| Record a posting, minutes made available, record done (C4, C9) | The dialog, from the CLI's records | A web writer: **none**. `notice_ledger.set_general` and `record_completion` are CLI and MCP only |
| The checks beside the draft (C5) | Yes; `minutes_draft.checks` is built | The `minutes-review` loader does not return them yet |
| The schedule and coverage (C7, C8) | Yes; `schedule_agenda`, `schedule_assignments`, `jason schedule` are built | The loader `schedule`: **not registered**; `#/duties` shows the manager's anchors only |
| The Today bands (C10) | "Needs attention" from `attention.digest` | The loader `governance-digest`; "Your work" waits on `work`, `work-run`, and any registered definition (the engine exists, `definitions.py` registers none) |
| The run's embeds (C11) | Draw from section H | The engine's definitions and the loaders above |
| Law review (a January occurrence) | A link only | `#/law-review` and its loaders (spec only) |

## H. A made-up community to design against

"Oakview", as of **2099-10-12**. People appear as offices ("the secretary", Sam Sample; "the treasurer", Taylor Sample; "the manager", Pat Example).

| Meeting | Kind, basis | Notice (CIV 4920) | Minutes (CIV 4950(a)) | The point it makes |
|---|---|---|---|---|
| Aug 18 | scheduled, nothing on record | — | "if held, due Sep 17" | A gap, not an assertion |
| Sep 15 | board meeting, held (Zoom record) | by Sep 11, on record in time: delivered (`jason://notice/board-meeting-2099-09-15`) | by Oct 15, **3 days left**, none on record yet; draft on file Sep 29 | An open legal clock, a draft ahead of the deadline, "approved: none" |
| Oct 20 | board meeting, from the schedule | by Oct 16, **4 days left**, none on record yet, owner: the secretary | by Nov 19, upcoming | The notice window bar; the packet mark Oct 13 and Oct 19 (`proposed policy`) |
| Nov 3 | executive session only | by Nov 1 (2 days, 4920(b)(2)) | none owed | A held meeting: general words only, no title |
| Nov 17 | board meeting, from the schedule | by Nov 13 | by Dec 17 | The watch reads it as open (caveat 2) |

To draw for the Oct 20 notice: today (a legal clock "today"), then past with the first caveat inline, then met by "Posted on the clubhouse board, Oct 14, 9:00 (the secretary)". Executive session: "Adjourn to executive session: litigation" in the statute's words; the minutes' general note only.

**The schedule** (Oakview): Reconcile the operating account (treasurer, Sep 30, adopted, **overdue**); Annual budget report (board, Sep 12, adopted, done Sep 12 by Sam Sample, "the report filed in the library, Sep 12"); Review the reserve transfers (treasurer, Nov 5, **proposed**, upcoming); Law review (manager, Jan 6, 2100, `proposed policy`, link only). Coverage: 41 assigned, 2 nobody owns (the annual insurance disclosure; the roof-inspection report), 1 on a clock only a standing assignment owns.

**Rule change "quiet hours"**: draft Aug 28 (file); proposed Sep 21 (delivered, `jason://notice/rule-change-proposed-quiet-hours`, 29 days before Oct 20: 28 required, `law`); comment deadline Oct 19 (`proposed policy`); decision Oct 20 (the board decides, the secretary records); adopted notice due by Nov 4 (15 days, `law`); reversal window 30 days after the adopted notice (`law`, 4365(b)). Draw it before the decision, after (`adopted`, "approved: stated"), and an emergency change (no notice, no reversal window, expires in 120 days).

**Run links** (section C11): `board-meeting 2099-10-20`, steps m2, m12, m16, m20, m21 as in [../workflows/board-governance.md](../workflows/board-governance.md) section 9.

**Statutes to recite** (verbatim from `data/authorities`; the page also shows jason's caveat that this is consolidated text, not an official restatement):

| Citation | Words |
|---|---|
| CIV 4920(a) | "Except as provided in subdivision (b), the association shall give notice of the time and place of a board meeting at least four days before the meeting." |
| CIV 4950(a) | "The minutes, minutes proposed for adoption that are marked to indicate draft status, or a summary of the minutes, of any board meeting, other than an executive session, shall be available to members within 30 days of the meeting." |
| CIV 4935(e) | "Any matter discussed in executive session shall be generally noted in the minutes of the immediately following meeting that is open to the entire membership." |
| CIV 4360(a) | "The board shall provide general notice pursuant to Section 4045 of a proposed rule change at least 28 days before making the rule change." |

Under each recitation, the reading (if any) sits in a `ReadingLabel` with whose it is; draw one with "No reading on file" and one where two readings remain ("The board asks counsel").

Run states to draw: loading ("reading the stores on disk"), no meeting in the window ("the profile sets no meeting schedule, and the catalog holds none"), a store missing (the loader's note and its command), a stale catalog (its age and `jason meetings --sync`), an owner viewing (posted records only).
