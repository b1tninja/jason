# Design brief: Life safety (the systems, and the deficiency register with its board items)

One page of orientation for the design agent, for the Life safety screen `#/life-safety` specified in [screens/life-safety.md](screens/life-safety.md). It does not repeat the spec; it says what to read in what order, each part to draw, what is built and what has no view, and a made-up community to draw against. Where the spec's layout and this page disagree, the spec's "As built (2026-10-10)" and the code win, and this page is corrected. The wider family (inspection period, deficiency, backflow) is [../workflows/property-safety-vendors.md](../workflows/property-safety-vendors.md); the earlier components for portals, notices, and the watchlist are [handoff-inspections-and-portals.md](handoff-inspections-and-portals.md).

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, insurer, or private fact; made-up samples only ("123 Main St", "Example Alarm", 2099).

**Built, checked against the code on 2026-10-11:** the loader `GET /api/life-safety[?system=KEY]` (`jason.web.extra.life_safety`, registered as `life-safety`), the writer `POST /api/write/life-safety/<deficiency id>` (acts `confirm`, `impairs`, `cleared`, `insurer-told`, `severity`, `deadline`, and `propose`), the register `jason.tasks.deficiencies` (`data/life-safety/deficiencies.json`), and `jason life-safety` (list, propose, confirm, impairs, cleared, insurer-told, severity, deadline). **No view:** `ui/src` has no life-safety view or route (`App.tsx` `SCREENS` has no `life-safety`; the only mention is a comment in `lib/inspections.ts`). The built `WatchRow`, `NoticeClock`, `ReportPortalCard`, `FilingPlan`, and `StandingPill` exist as props-only components. `DeficiencyRow` is named in the spec and does not exist. `#/actions?item=<id>` is built and opens that board item.

## A. The idea, and the rules that run through it

**The idea, in six sentences.**

1. The screen answers "are our fire protection systems inspected, tested, and in working order, and can we prove it?" The register answers its sharpest half: **what was found, what a person has said about it, and where the board stands.**
2. A report's open deficiency is **proposed** by jason once, from the report's reading. It is a finding only when a person **confirms** it.
3. **Every confirmed deficiency becomes a board item**, proposed for the next agenda ("Decide the repair, the vendor, and the date"), and every later act refreshes that same item. Any deficiency is worth the board's attention (decided 2026-10-11).
4. The item is **prioritized by severity and deadline**, both a person's words. Until a person sets a severity, the priority is **jason's proposal**, labeled so. It is not a legal standard, and jason computes no legal deadline.
5. A deficiency is **cleared only by a linked record** (an invoice's line items, an AES 10, a later passing report), never by a subject line or free text. jason never contacts an insurer: "insurer told" records what a person did.
6. The page reads; a person acts, in their own name, behind a `Confirm`. The board decides; the secretary records the decision in Decisions. This screen has no approve, vote, adopt, or send.

**The rules** (each is in the spec or the register's code; a screen that breaks one is wrong):

- **Directors and officers have the same access to information** (decided 2026-10-11). The impairment and the sentence "no record shows the insurer was told" show to every director, as to every officer. There is no director-only or counts-only view. The offices that open P2 (manager, president, vice president, director, secretary, treasurer) read the whole register. A signed-in roster person whose office does not open P2 gets the proposed, open, and cleared counts and a `held` sentence; `impairments`, `insurerNotTold`, and `urgent` are `null` and drawn as a dash with the reason, never a zero.
- **Nothing is inferred.** "Impairs a scheduled safeguard" is `null` until a person says; the page then says "not yet recorded". The banner is raised only from what a person recorded.
- **Proposed is labeled proposed.** A priority jason proposes carries "priority proposed" and "jason's proposal, not a legal standard". A person's severity carries "set by NAME on DATE". A deadline always shows its **basis word** (`insurer`, `authority`, `documents`, `vendor`, `person`) and who recorded it. A deadline never raises a person's severity.
- **Append only.** A correction is a later act; nothing is edited or unsaid. The latest word on each question wins, and the older acts stay in the trail.
- **Acts are the signed-in person's own.** An administrator viewing as someone else sees "Viewing as NAME (admin view): go back to yourself first" in place of each control (403). The server takes the name; the page sends none.
- **State is a word and a glyph, never colour alone.** A status or priority is a word first.
- **No code or lock-box number is ever shown,** and a unit number follows the spec's privacy section. A row's location, device, and comment arrive masked.
- **A reading is labeled.** A statute or the policy's words are recited whole (`Recitation`) before any reading (`ReadingLabel`).

## B. Reading order

1. [screens/life-safety.md](screens/life-safety.md): "As built (2026-10-10)" first, then Layout, Actions, States, Privacy.
2. [../../src/jason/tasks/deficiencies.py](../../src/jason/tasks/deficiencies.py): the acts, `proposed_priority`, `board_item_of`, and `view` (the sort and the counts).
3. This page's section D beside section H (the sample).
4. [screens/board-items.md](screens/board-items.md) for the board's side of the item (its four columns, executive items).
5. [../workflows/property-safety-vendors.md](../workflows/property-safety-vendors.md) section 2.2 (the deficiency steps) and [handoff-inspections-and-portals.md](handoff-inspections-and-portals.md) for the built `WatchRow` and portal parts.
6. [components.md](components.md) for what to reuse.

## C. The screens

### C1. The page frame (`#/life-safety`)

`ScreenHeader` with the summary line (systems, overdue, open deficiencies, how many impair a safeguard), `Freshness` for the deadlines and reports, and the banners (C3) directly under it. Then a `SystemCard` per listed system (schedule, reports, owes us), as the spec's Layout draws them, then the **Deficiency register** (C2), then the vendors table. The spec's per-system schedule is not this brief's subject: draw it from the spec and the built `StandingPill` and `WatchRow`.

### C2. The deficiency register (a section of the page)

```
+------------------------------------------------------------------------------------------------+
| Deficiencies   1 proposed · 3 open · 1 cleared      sorted: open first, priority, deadline      |
|  [ ] Show cleared (1)     System [All v]   Command: jason life-safety --list                      |
+------------------------------------------------------------------------------------------------+
| Priority            Finding                         System / Bldg   Deadline (basis)   Board item |
| urgent  proposed    Waterflow switch, failed        Alarm / 1       2099-10-05 insurer  proposed   |
|                     found 2099-09-19                                7 days past          [Open]   |
| high    proposed    Smoke detector, hall, low batt. Alarm / 3       2099-10-20 vendor   on agenda  |
| normal  Robin S.    Pressure gauge, riser           Sprinkler / 2   2099-10-01 authority proposed  |
| —       proposed    Exit light, stairwell           Alarm / 4       —                   none yet   |
| cleared             Horn/strobe, Bldg. 1 corridor   Alarm / 1       cleared 2099-08-02            |
+------------------------------------------------------------------------------------------------+
```

One `DataTable`, one row per register row, in the **loader's order** (`deficiencies.rows`: open first, then priority urgent, high, normal, then deadline ascending with none last, then date found); the view never re-sorts by its own idea, and a column sort is a read. Columns: **Priority** (`PriorityPill`, section D: the word, and `proposed` or "set by NAME"); **Finding** (location, device, comment as masked, and the report's name and day, a `DocRef` chip); **System and building** ("a system not placed" when `system` is empty); **Deadline** (`DeadlineCell`); **Board item** (`BoardItemLink`: its status word, a link to `#/actions?item=life-safety-<id>`). A proposed row has no priority yet and no board item: it shows "proposed from a report's reading, not a finding" and a **Confirm** control. Cleared rows are hidden behind a toggle that keeps the count. Selecting a row opens the card (C3). Under 720 px, rows become cards: priority word, finding, deadline, status.

### C3. The deficiency card (a drawer over the register; a full page at `#/life-safety?deficiency=<id>`)

```
+----------------------------------------------------------------------------------+
| Waterflow switch, failed · Alarm / Bldg. 1 · found 2099-09-19   [report chip]      |
| open · confirmed by Robin Sample 2099-09-21                                       |
+----------------------------------------------------------------------------------+
| ! A person recorded an impairment on a scheduled safeguard, and no record shows   |
|   the insurer was told.                                                          |
+----------------------------------------------------------------------------------+
| Priority   urgent (priority proposed). jason's proposal, not a legal standard:   |
|   it impairs a safeguard and no record shows the insurer was told. A severity a   |
|   person records replaces it.                              [Record a severity]    |
| Deadline   2099-10-05 · set by insurer · recorded by Robin Sample · 7 days past   |
|   (a date a person recorded; jason computes no legal deadline)  [Record a deadline]|
| Impairs a safeguard   yes, Robin Sample 2099-09-22 · [Change]                      |
| Insurer told   no record · [Record that the insurer was told]                      |
| Cleared by   not cleared · [Record what cleared it]                                |
+----------------------------------------------------------------------------------+
| Board item   life-safety-def-… · proposed for the next agenda · [Open in Actions]  |
|   "Decide the repair, the vendor, and the date". Status, owner, meeting, notes are |
|   the board's; the secretary records the board's decision in Decisions.            |
+----------------------------------------------------------------------------------+
| Trail (oldest first): proposed 09-20 jason · confirmed 09-21 · impairs 09-22 ...   |
+----------------------------------------------------------------------------------+
```

Each row of the middle block is a **field with its source** and its act. Each act is a `Confirm` that spells out what will be recorded and under what name; the list is the five acts below. Every act on a confirmed row also refreshes the board item; the result shows "Board item refreshed" or, when the answer's `boardItem` is `{ok: false, why}`, "The act is recorded; the board item was not written: WHY" (the act stands).

| Act | Fields (as the writer takes them) | The `Confirm` says | Refused when |
|---|---|---|---|
| Confirm | none | "Confirm this deficiency as NAME. It becomes a board item proposed for the next agenda." | already confirmed (no-op) |
| Impairs | yes or no | "Record NAME's reading: this does / does not impair a scheduled safeguard." | not confirmed |
| Insurer told | the record's id (a library id or `gmail:ID`, not words), the day (not in the future) | "Record that NAME says the insurer was told on DATE, per RECORD. jason contacts no insurer and sends nothing." | not confirmed; words for an id |
| Cleared | the record's id (must be in the library), its kind (`invoice line items`, `AES 10`, `later passing report`, `other record`), the day | "Record that RECORD cleared this on DATE. This closes nothing on the board." | not confirmed; id not in the library; a "passing report" that is not passing or not later; a subject line |
| Severity | urgent, high, or normal | "Record NAME's severity: HIGH. It replaces jason's proposed priority." | not confirmed |
| Deadline | the date, the basis word, the record (optional) | "Record a deadline of DATE, set by BASIS, as NAME. jason computes no legal deadline." | not confirmed; more than a year past; malformed |

Show the refusal in the writer's own sentence, beside the field. A past deadline within a year is accepted and shown as overdue.

### C4. The banners (under the page header, above the register)

- **Impairment, insurer not told** (from `banner`, raised from what a person recorded): the loader's sentence, verbatim, and the ids it names as links to their cards. Beside it, "Open the board item". `[Recite the condition]` waits (section G). Every director sees it.
- **Overdue deadlines** (from `summary.overdueDeadlines`): "N deadlines a person recorded have passed", each with its basis word, in the register's order. The loader sends a count and the rows, not a sentence; the wording is the design's (section F). It says "recorded", never "legal".
- **Held** (a viewer who does not open P2): the loader's `held` sentence, the three counts, and no rows.

### C5. The board item the register makes

A small preview in the card and the `#/actions` link: the item's title ("Life safety deficiency: DEVICE (SYSTEM)"), category safety, priority with its label, `due` from the deadline, the summary that says what each person recorded, and, once cleared, "cleared by RECORD on DATE. jason closes nothing: the board closes this item." Draw the card's two states: the item written, and the item not written (the failure above). Executive items are not involved: a deficiency item is not executive.

## D. The shared components, each once

Reuse (built, in `ui/src/components`): `ScreenHeader`, `Card`, `Tabs`, `DataTable`, `Drawer`, `Pill`, `Badge`, `Glyph`, `Seal` (jason's "proposes"), `Confirm`, `Command`, `Doc` and `DocRef`, `Recitation`, `ReadingLabel`, `Caveats`, `Freshness`, `DueDate`, `Timeline`, `Findings`, `Stat`, `HeldNote`, `ChangedBanner`, `RoutingTag`, `StandingPill`, `WatchRow`, `EmptyState`, `RemoteView`. Do not use `Stamp`: nothing here is a decision of the board.

| Component | What it is | Data (the real field names) | States |
|---|---|---|---|
| `DeficiencyRegister` | The C2 table with its toggle and counts | `deficiencies{found, counts{proposed, open, cleared, impairments, insurerNotTold, urgent, overdueDeadlines}, rows[], detail, held, command, caveats}` | loading; `found:false` with `note`; empty ("No deficiency on record. A report not yet read is not seen."); held (counts, a dash for the null ones); a filter that matches nothing |
| `DeficiencyRow` | One row (the spec's name; to build) | a row: `id, system, buildings, report{id,name,day,where}, location, device, comment, standing, severity, deadline, deadlineBy, priority{value,proposed,why}, boardItem{id,status}, impairs, insurerNotTold` | proposed; open; open and impairing; open with insurer told; cleared; deadline past |
| `DeficiencyCard` | The C3 drawer | the row plus `acts[]`, `confirmed`, `impairsBy`, `insurerTold{record,on,by,inLibrary}`, `cleared{record,kind,on,by}`, `severityBy`, `deadlineBy{date,basis,record,by}` | each standing; viewing as someone else (controls replaced); an act refused (the sentence); an act recorded with the item written or not |
| `PriorityPill` | A `Pill` preset | `priority.value` (urgent, high, normal) and `priority.proposed`, `priority.why`, `severityBy` | proposed (shows "priority proposed", `why` on focus and in the card in full); a person's ("set by NAME"); none (proposed row, a dash) |
| `DeadlineCell` | `DueDate` plus the basis | `deadline`, `deadlineBy.basis`, `.by`, `.record` | none ("no deadline recorded"); upcoming; due within jason's window (shown as a fact about the date, not a legal one); past (overdue by N days, from the loader's day, not the view's); each of the five basis words |
| `ImpairmentBanner` | The C4 banner | `banner{ids[], sentence}`, `summary.impairments`, `.insurerNotTold` | one; several (ids as links); absent; held (not drawn) |
| `ActForms` | The six acts as `Confirm` forms | the writer's fields (C3 table) | pick; asks for a record (insurer told, cleared, a deadline's optional one); recording; recorded; refused; admin view |
| `BoardItemLink` | The item's status and the `#/actions?item=` link | `boardItem{id,status}` (the board's words: open, proposed, on agenda, in progress, deferred, closed) | none yet (proposed row); written; not written (the failure); closed by the board while the deficiency stays open |
| `ActTrail` | A `Timeline` preset: who, when, which act, in order | `acts[]` (`proposed` has no name: "jason, from a report's reading") | one act; many; a correction shown as a later entry |

**Fixed words** (use exactly): "priority proposed", "jason's proposal, not a legal standard", "set by NAME", "a person recorded", "no record shows the insurer was told", "insurer told: no record", "not yet recorded", "proposed from a report's reading, not a finding", "cleared by RECORD on DATE", "jason closes nothing: the board closes this item", "Viewing as NAME (admin view): go back to yourself first", "Open in Actions". Never "past due by law", "late", "violation", "compliant", or "safe".

## E. Glyphs

Use the console's glyphs: `triangle-alert` (impairment, overdue, urgent), `circle-question-mark` (not yet recorded), `clock` (due within the window), `circle-check` (confirmed, cleared), `minus` (no deadline, none), `lock` (held), and the paperclip or link glyph for a linked record. Propose a new one only where none says it, and name it for the idea: an **insurer-silent** mark (an impairment with no record that the insurer was told), and a **proposal** mark that separates jason's priority from a person's (a `Seal`-style word may do it; the design decides). Each glyph sits beside its word.

## F. Decisions that are the design's, in one list

1. **Where the register sits:** a section of `#/life-safety` below the systems (recommended: one page answers the question) or a tab beside Schedule and Reports; and the per-system tab (`?system=KEY`) filters the same table.
2. **The overdue-deadlines banner wording**, since the loader sends a count, not a sentence. It must say a person recorded the date, and name the basis, not claim a legal deadline.
3. **How proposed versus person's priority reads in a table of twelve** without colour: a word plus a mark, and whether a proposed `urgent` outranks a person's `normal` visually (the sort is the loader's and does).
4. **Where the board item shows:** a column, a line in the card, both (recommended), and whether the card previews the item's summary.
5. **The `Confirm` wording** for each act (C3 gives drafts), and whether a record the person links shows a `Doc` preview inside the dialog.
6. **How the card orders its fields:** the open questions first (impairs, insurer told) or the priority first.
7. **The empty and held states'** wording, and how a dash for a `null` count is explained.
8. **Print:** a one-page register for the board packet (deficiencies, priority, deadline and basis, board item), with every proposed priority labeled.

These are not the design's: who may confirm or clear (the offices that open P2), whether the board adopts the proposal rule below, what a deadline's basis word means, and whether a clearing record is enough.

## G. What can be designed now, and what waits

| Part | Now | Waits on |
|---|---|---|
| Register table, card, the six acts, the banners, the trail | Yes, from the loader and writer | The view itself (`ui/src`): build `DeficiencyRow` and the page |
| The board item's link and preview | Yes (`#/actions?item=` is built) | Nothing; the page does not list the items yet (`notComposed`, `boardItems`) |
| Per-system deficiency counts on a `SystemCard` | Draw them | The loader sends page-wide counts only; the view may group `rows` by `system` or the loader adds counts (a build item) |
| "Recite the condition" (the policy's protective-safeguards words) | Draw it disabled, with `jason insurance` | The insurer's condition is not composed (`notComposed`, `insurer`) |
| Vendors table (licences, amounts) | From the spec | Not composed (`vendors`; P1 amounts) |
| A "not a deficiency" act, an estimate, a repair step, "insurer told it ended" | No | None exists in the register (the family page, gap 2); the deficiency run (Work) is design only |
| A written priority policy | The labeled proposal | The board adopting one (below) |

**A policy to propose, not decide here.** The law and the documents are silent on how soon a deficiency must be corrected and in what order the board takes them. jason's proposal (urgent if it impairs a safeguard and no record shows the insurer was told; high if it impairs one; a deadline past or within 14 days raises it a step) is a default, labeled so. The board may adopt a written priority policy; until then no screen calls it a rule.

## H. A made-up community to design against

"Ridgeview" (no real association). Today is **Oct 12, 2099**. Systems: Fire alarm and monitoring (vendor Example Alarm), Sprinklers (buildings 1 to 4). Roster: Robin Sample (manager), Pat Example (secretary), Lee Sample (director), and A. Owner (a member whose office does not open P2, for the held state). The register:

| Id | Finding | System / Bldg | Standing | Impairs | Insurer told | Severity | Deadline (basis) | Priority shown | Board item |
|---|---|---|---|---|---|---|---|---|---|
| `def-a1b2c3d4e5` | Waterflow switch failed, found 2099-09-19 | Alarm / 1 | open | yes (Robin, 09-22) | no record | none | 2099-10-05 `insurer` (7 days past) | urgent, **proposed** | proposed |
| `def-b2c3d4e5f6` | Smoke detector, hall, low battery | Alarm / 3 | open | not yet recorded | n/a | none | 2099-10-20 `vendor` (8 days) | high, **proposed** (normal raised a step by the near deadline) | on agenda |
| `def-c3d4e5f6a7` | Pressure gauge, riser, unreadable | Sprinkler / 2 | open | no (Robin, 10-02) | n/a | normal, set by Robin 10-03 | 2099-10-01 `authority` (11 days past) | normal, **a person's** (a past deadline never raises it) | proposed |
| `def-d4e5f6a7b8` | Exit light, stairwell | Alarm / 4 | proposed | not yet recorded | n/a | none | none | none yet | none yet |
| `def-e5f6a7b8c9` | Horn/strobe, corridor | Alarm / 1 | cleared 2099-08-02 | yes | told 2099-07-20 (record `gmail:EX01`) | high | 2099-08-15 `documents` | cleared | in progress, the board's |

Summary: `counts` proposed 1, open 3, cleared 1, impairments 1, insurerNotTold 1, urgent 1, overdueDeadlines 2. Banner ids: `def-a1b2c3d4e5`. Cleared by: invoice line items, library record `drive-EX-INV-0042`.

Card states to draw: `def-a1b2c3d4e5` with the banner and the acts open (the main card); the same after **Insurer told** is recorded (the banner clears, `priority.why` becomes "it impairs a safeguard", the proposal falls to high, the board item refreshes); `def-c3d4e5f6a7` (a person's word beside a past deadline); `def-d4e5f6a7b8` unconfirmed (one control, **Confirm**); an act refused (a subject line given for a clearing record; a deadline 14 months past); the board item not written; Lee Sample (a director) reading the same impairment and banner as Robin; A. Owner's held view; an admin viewing as Pat Example (controls replaced); the page with no deficiencies and with the register unreadable (`found:false`).
