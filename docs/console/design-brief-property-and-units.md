# Design brief: Property and units (the paint palette, the unit record and loss packet, contracts with their notice windows, and improvement requests)

One page of orientation for the design agent, for [screens/paint.md](screens/paint.md) (`#/paint`), [screens/unit-record.md](screens/unit-record.md) (the tab on a unit's page in [screens/members-and-units.md](screens/members-and-units.md), and `#/loss-packet`), [handoff-contracts.md](handoff-contracts.md), and [handoff-improvement-requests.md](handoff-improvement-requests.md). It does not repeat the specs; it says what to read in what order, each screen to draw, the shared parts once, what is built and what has no view, and a made-up community to draw against. Where a spec and this page disagree, the code and the spec's "Checked" notes win, and this page is corrected. It reuses [design-brief-work.md](design-brief-work.md) (runs, `BasisPill`, `RunLinks`), [design-brief-life-safety.md](design-brief-life-safety.md) (the deficiency register is not redrawn), and [design-brief-board-records.md](design-brief-board-records.md) (`RecordTrail`, `EvidenceLinks`; the incident record is not redrawn: this brief only links to it). The family is [../workflows/property-safety-vendors.md](../workflows/property-safety-vendors.md) sections 2.5 to 2.9.

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, insurer, color code, or private fact; made-up samples only ("123 Main St", "Example Alarm", "A. Owner", 2099).

**Built, checked against the code on 2026-10-11.** *Loaders* (`jason.web.sources.EXTRA_LOADERS`): `paint` (`GET /api/paint`, schedules against the catalog copy on disk, plus the reserve study's painting lines), `paint-color` (`/api/paint/color?code=`), `unit-record` (`?unit=&plan=`), `loss-packet` (`?unit=&incident=&address=`), `facts`. *Writers* (`EXTRA_WRITERS`): `unit-record` (`entry`, `visibility`) and `loss-packet` (`confirm`). No paint writer and no paint job exist. *Components* (props only, in `ui/src/components`): `PaletteMatrix`, `Swatch`, `ColorDetail`, `SourcedDate` (with previews and tests), plus `Timeline`, `StageSteps`, `Clock`, `NoticeClock`, `Checklist`, `Money`, `HeldNote`, `Findings`, `Doc`, `Confirm`, `Command`. **No view:** `ui/src/App.tsx` `SCREENS` has no `paint`, `members`, `loss-packet`, `contracts`, `requests`, `incidents`, or `work`; `ui/src/views` has no file for any. **Not built at all:** a `contracts` loader and any contract component (`jason contract-terms` and `data/contracts/terms/*.json` exist; `window_days` is on a term as `(shortest, longest)`); the improvement-request store, loaders, writes, and `jason improvements`; the incident record; a color check of a chosen color (`jason paint --request` is design only; the built `--check` is the schedule against the catalog); `jason unit-record` and `jason loss-packet` commands; any registered Work definition for `paint-cycle`, `contract-notice-window`, `improvement-request`, `loss-claim`, or `maintenance-program` (the run library `jason.workflows` is built, and `LinkKind` has no paint, contract, unit, or incident kind; `doc` is the stopgap). A maintenance program has no web loader (`pest_program` is an MCP tool).

## A. The idea, and the rules that run through it

**The idea, in seven sentences.**

1. The property answers four questions a board is asked: **what color goes where and is it still the maker's color, what is in this unit and who recorded it, what must a person read when something is damaged, and when does each vendor agreement need a notice and from which day to which day.**
2. The palette is the association's record of what it approved. The maker's catalog can move under it; the page **shows the printed name beside the current one** and changes no row. A board decision on a renamed or discontinued color is the board's, recorded by the secretary.
3. A **color check** of a chosen color says one of four things: on the schedule for this surface, on it for another surface, near a scheduled color (the nearest and its difference, labeled a screen match), or not on it. It approves nothing; "near enough" is a number only the board can set.
4. A unit's record is **assumed defaults overlaid by what a person recorded**: the plan's original specification, then entries with a status the owner chose. A cell says where the record **points**, never "covered", and a difference between the declaration and the policy is an open question with an owner, never an error.
5. The loss packet is five questions in order. Each shows the provisions **recited whole**, what the record shows, and a person's confirmation with a name and a time. It never states coverage, fault, or who pays.
6. A contract's notice window has **two edges**, a basis (the contract and the term's end it counts from, both documents), and a delivery method. A notice outside either edge "may not count"; there is no winner and no verdict.
7. jason reads and drafts. It never contacts a vendor, an insurer, or an owner; never accepts a proposal, renews, or ends an agreement; never approves a color or a request. A person acts, in their own name, behind a `Confirm`.

**The rules** (each is in a spec or in the code; a screen that breaks one is wrong):

- **Directors and officers have the same access to information** (decided 2026-10-11, and `access.SEE_RULES`: manager, president, vice president, director, secretary, and treasurer all open P2; P3 only in the private view, and not for the treasurer). Draw one view for every office that opens P2. [screens/members-and-units.md](screens/members-and-units.md) and [screens/unit-record.md](screens/unit-record.md) narrow the treasurer, the secretary, and the director below that; those tables are older than the decision and are to be corrected (decision 1 below). A signed-in roster person whose office does not open P2 (an administrator with no office included) gets a `HeldNote` and counts, never a zero for a count withheld.
- **An owner never sees these screens.** `OWNER_SOURCES` has no paint, unit, packet, contract, or request loader, so the owner view answers 403. The owner's own view of their unit is a different payload and a different brief ([handoff-improvement-requests.md](handoff-improvement-requests.md), "The owner's unit view"). Do not draw an owner state here.
- **Never show contact details in a list**, and none at all on these screens: no email, phone, mailing address, or tenant. Who rents which unit and who lives where are P3 (`leases/*`, `spec/*`) and appear nowhere in this brief.
- **A reading is evidence, not a finding.** A catalog status, a coverage "points", a recited provision, and a model-read term are leads read beside the words. A finding is what a person confirmed, with their name.
- **Recite, then label.** A provision or a clause is shown whole with its citation (`Recitation`), then any reading under `ReadingLabel` with whose it is. Never type a statute's or a contract's words into a page; the loader recites from the shelf or the library.
- **Every date says whose it is.** `SourcedDate` words (recorded, implied, reported, needs input) for painting dates; a basis word (`BasisPill`: `law`, `documents`, `counterparty`, `proposed policy`, `person`) for every clock. A proposed number is never a stamp and never a date shown to an owner.
- **Append only for a person's acts.** A correction is a later act. (The loss-packet writer replaces today; see section G.)
- **State is a word and a glyph, never colour alone;** a swatch always carries its code and name in text; ink on a swatch is chosen by luminance.
- **Nothing is sent.** A question to the agent, counsel, or a vendor is a draft a person sends. An export is a file.

**The level of each field** (`access.py`; "unplaced" means no `PATH_RULES` row, which reads P2 and is closed). State the level on the field's `Evidence` chip or in the card's caption.

| Field | Level | Where it comes from |
|---|---|---|
| Palette: surface labels, codes, printed and catalog names, hex, LRV, schemes, the schedule's source and preparer | P0 | `Community.paint_schedules()`; the maker's catalog is public. The copy under `paint/` is unplaced (P2 as a file); a P0 row is a build item |
| Next due and cost (the reserve study's painting lines) | P1 | `reserve-studies/*` |
| A recorded last-painted day and building | P1 as a fact; its source (`reports/*`) is P2 | Show the day, the building, and a `DocRef`; no vendor name on this page |
| Unit identity: PayHOA unit id, address, plan, building | P1 | |
| Effective record: component, status, original specification, source | P1 (the specification P0) | `unit_record_view` |
| An entry's what, date, status | P2 | `<profile>/units/<unit>/entries.json`, unplaced |
| An entry's contractor, licence, permit, cost, serial, photos | P2, only in that unit's own tab | Never in a list across units; cost is `Money` in cents, "the owner's figure; not certified" |
| A private entry | The owner's: counted (`privateHeld`), never read, by anyone | |
| Declaration and policy "points", recited provisions | P0 for statutes and the declaration; the policy's words P2 | `insurance-pdfs/*` |
| Packet: carrier, policy number, deductible, renewal | P2 | `insurance/*` |
| Packet: incident history lines | P2 | `reports/*`; claim files' letters are held back and not counted by this loader |
| A packet confirmation (name, time, the evidence it relied on, a note) | P2 | `<profile>/units/<unit>/packets/` |
| Contracts: parties, term, windows, delivery, owed items | P2 | `contracts/` is unplaced; a confidential contract is P3 by the library flag (name only to those who may) |
| An improvement request: the owner's words, state, clock | P2; a list carries no contractor, cost, or phone | not built |

## B. Reading order

1. [screens/paint.md](screens/paint.md), then [../paint-design.md](../paint-design.md) ("What the assistant does", item 2 is the color check).
2. [screens/unit-record.md](screens/unit-record.md), then [handoff-unit-records.md](handoff-unit-records.md) (`EffectiveRecord`, `CoverageCell`, `LossPacket`).
3. [../../src/jason/tasks/paint_view.py](../../src/jason/tasks/paint_view.py) and [../../src/jason/tasks/unit_records_view.py](../../src/jason/tasks/unit_records_view.py): the real field names, and what the loaders do not send.
4. [handoff-contracts.md](handoff-contracts.md) ("The idea", `NoticeWindow`, `NoticeWindowView`), then [../workflows/property-safety-vendors.md](../workflows/property-safety-vendors.md) 2.5 and its sample C.
5. [handoff-improvement-requests.md](handoff-improvement-requests.md) (the vocabulary, `RequestStateStrip`, `RequestClock`); `RequestClock` is also drawn in [design-brief-requests-and-onboarding.md](design-brief-requests-and-onboarding.md): reuse it.
6. [screens/work.md](screens/work.md) "Where a step's work happens" (the embed rule), then sections 2.7 to 2.9 of the family page.
7. This page's section D beside section H.

## C. The screens

### C1. Paint (`#/paint`, a tab under Records)

`ScreenHeader` (title, the schedule's source as a `DocRef` chip, "prepared for the developer, 2099-01-15"), `Freshness` for the catalog copy ("from Oct 3, 9 days old; 1 color renamed, 1 discontinued, 1 not checked"), and `Command` (`jason paint`). Then four bands:

```
+---------------------------------------------------------------------------------+
| Scheme (o)1 ( )2 ( )3 ( )All          Palette: Exterior · prepared 2099-01-15    |
|               Scheme 1                 Scheme 2               Scheme 3           |
| FASCIA        [chip] SW 7008 Example Cream  ...                                  |
| STUCCO FIELD  [chip] SW 6999 Example Clay   RENAMED: printed "Example Sage",     |
|               DISCONTINUED: closest 5 ->    now "Sage Example"                    |
| ROOF          Not paint (tile)                                                   |
| Screens and printers shift color. The number on the schedule governs.            |
+---------------------------------------------------------------------------------+
| CHECK A COLOR   Number or name [______] Surface [Stucco field v] Building [3 v]  |
|  -> "Near a scheduled color: SW 7008, difference 2.9 (a screen match, not paint)."|
|  The four outcomes: on this surface / on another surface / near / not on it.     |
|  A committee decides; the governing text is recited below. [Open in Architectural]|
+---------------------------------------------------------------------------------+
| WHEN IS IT DUE      Last painted        Next due     Cost at today's prices      |
| Buildings 1, 2      2092 recorded [inv]  2100        $50,000 (reserve study)     |
| Building 3          2095 implied (2100 minus a 5-year life)   2103   $25,000     |
| Building 4          needs input: None on record yet. Add the date with its source.|
+---------------------------------------------------------------------------------+
| Interior colors as owners reported them (later). Not the association's record.   |
+---------------------------------------------------------------------------------+
```

A swatch opens `ColorDetail` in a drawer (description only on a person's click, the touch-up caveat, coordinating and similar chips, the closest current colors for a discontinued one, "used on"). A renamed color shows the printed name beside the current one; a discontinued one shows the status word and its `nearest` list with the difference number; a hand-entered color says "entered, not checked". The check is a read: it returns where the color sits and a difference, and the page has no "approve" or "matches" verdict word, only the four outcomes. **The built part:** the matrix, the swatch, the detail, and the catalog check (renamed, discontinued, not found, not checked). **Not built:** the color-check band (a loader `paint-check?code=&surface=&building=`, design only) and a scheme-per-building map (the schedule has `buildings`, but no loader says which building wears which scheme).

### C2. The unit record (a tab on `#/members?unit=<PayHOA unit id>`)

```
+---------------------------------------------------------------------------------+
| Unit 14 · 123 Main St · Plan A · Building 3        [Open the loss packet] [Add an entry]|
| Plan A is matched. 1 private entry belongs to the owner and is not read.         |
+---------------------------------------------------------------------------------+
| Component         Status             Source              Declaration  Policy      |
| Kitchen flooring  original           [plan sheet]        points: master  points: master |
| Bath flooring     upgrade            [approval][entry]   points: owner's points: owner's |
| Water heater      equiv. replacement [invoice][entry]    points: master  ask a person   |
| Refrigerator      builder option     [closing sheet]     ask a person    ask a person ?  |
| Ceiling fan       unknown            none                ask a person    ask a person   |
| Finished flooring  DIFFERS: the declaration says ... the policy says ...  -> question 1 |
+---------------------------------------------------------------------------------+
| Differences are questions, not findings. Open: finished flooring (with the agent, asked Aug 2). |
+---------------------------------------------------------------------------------+
```

A row opens its history: each entry as a `Timeline` item with what, where, replaced, date, product, the approval chip, the permit, the contractor (P2, this card only), the cost as the owner's figure, who recorded it and when, and the visibility word with its history. A `differs` cell shows both recited provisions side by side and links to the `OpenQuestion` (who it is with, asked, answered, the answer's source). With no plan matched, every status is unknown and the page says so once at the top, not per row. Rows come in the loader's order; the view sorts nothing. "Add an entry" is a `Confirm` that spells out the visibility and the name; an entry may not claim "original" or "unknown".

### C3. The loss packet (`#/loss-packet?unit=&incident=`, opened from the unit tab or an incident)

```
+---------------------------------------------------------------------------------+
| Loss packet · Unit 14 · water damage found Jun 4 · inc-2099-0003    [Export] [Print]|
| Master policy: Example Mutual, deductible $10,000, renewal 2100-03-01 · a reading |
| Unconfirmed: a person has not confirmed every step. 1 of 5 confirmed.            |
+---------------------------------------------------------------------------------+
| 1 The item   confirmed by Robin Sample, Oct 3     [recited provisions v] [records 2]|
|     Trail: Oct 3 Robin Sample (current) · Oct 9 Pat Example corrects Oct 3 (prior kept) |
| 2 Origin of cause   unconfirmed   [recited v]   [Confirm as Robin Sample]        |
| 3 An insured casualty   unconfirmed   (policy on file)                           |
| 4 Negligence   unconfirmed                                                        |
| 5 The deductible   held: The board has not adopted a deductible guideline.        |
+---------------------------------------------------------------------------------+
| History at this address: 2 lines (leads, from repair paperwork). Open: whether unit finishes ... |
+---------------------------------------------------------------------------------+
```

Each step: the question, the provisions recited whole (collapsed to a heading and citation, open on demand, never summarized), the records the person relied on (evidence addresses, required to confirm), the confirmation (name, time, a note), and its trail (`RecordTrail`, newest first, the current word marked, an earlier one dimmed and kept). A provision the shelf cannot find is a **held note naming the expression**, never a paraphrase. A step needs "shows" evidence to confirm; the refusal sentence is the writer's. No cell, heading, or export says covered, not covered, at fault, or your responsibility. A claim file's contents are never shown. The export says "unconfirmed" beside each unconfirmed step.

### C4. Contracts: the list, with the notice-window strip (`#/contracts`, proposed under Records)

```
+---------------------------------------------------------------------------------+
| Agreements   5 read · 1 window open (closes in 20 days) · 1 opens in 4 days · 1 needs input |
| Today Oct 12, 2099.   Sorted by the nearest closing edge.                          |
+---------------------------------------------------------------------------------+
| Example Management, LLC · management agreement · term ends Dec 31 (recorded)      |
|   Sep 2 [=======(today)=============] Nov 1 .......... Dec 31   documents          |
|   "A notice may be sent from Sep 2 to Nov 1, 2099, by certified mail." 20 days left|
|   2 findings (check) · e-signed both sides · read by grammar                       |
| Example Pest Control · term ends Dec 15 · window Oct 16 to Nov 15 (opens in 4 days)|
|   A notice on record Oct 3: before the window opens, so it may not count.          |
| Example Landscape Co. · term ends Nov 30 · one edge: no later than Oct 31 (19 days)|
| Example Alarm Co. · term end needs input (the start date is blank in the text)     |
| Example Paving · proposal · UNSIGNED COPY: this copy is not the signed agreement.  |
+---------------------------------------------------------------------------------+
```

A row is the strip (`NoticeWindow`, section D) plus the contract's name, kind, term end with its source word, findings count, signed state, and method; a confidential contract shows a lock and a name to those who may see it. The strip carries **both edges, today, the term's end, the delivery method, and a basis pill (`documents`)**, and a text equivalent a screen reader reads first. At 360 px the strip becomes a sentence with two `DueDate`s and the delivery. A window with one edge, a window not yet open, a window closed, and "term end needs input" are four distinct states; none shows a verdict like "late" or "valid". The contract's detail (terms, owed list, licence chips, findings) is [handoff-contracts.md](handoff-contracts.md); this brief draws only the list, the strip, and its link to a run.

### C5. The improvement request: timeline and clock (a band of `#/requests?id=`)

```
+---------------------------------------------------------------------------------+
| imp-2099-1001 · solar · 123 Main St · received Oct 1 via the owner portal         |
| [submitted Oct 1] > [incomplete Oct 4 by Robin Sample] > complete > review > board > decided |
| Waiting on the owner for a scale plan, from Oct 4.                                |
+---------------------------------------------------------------------------------+
| Clock  set by the statute · day Nov 15 (45 days from receipt) · 34 days left       |
|   [recited from the shelf: CIV 714(e)(2)(B), whole]  Reading, labeled: ...        |
|   Oct 4: a person recorded a request for more information. The statute speaks to  |
|   that delay (recited above); jason does not recompute the day or apply it.       |
|   The meeting that meets it: Oct 20; notice by Oct 16 (computed, labeled)          |
+---------------------------------------------------------------------------------+
| After the work: unit 14's manual links the approval; the unit tab shows both chips.|
+---------------------------------------------------------------------------------+
```

A second frame: an ordinary application whose clock is `proposed policy, not adopted` (a target of Oct 31 for the board; never shown to an owner as a date). The strip's current state is `aria-current="step"`; the board stage has no approve, deny, or decide control, and links the item, the agenda, and the decision. Draw the closing words (`withdrawn`, `lapsed`) and the branch (`reconsideration`) in text. The rest of the request is [design-brief-requests-and-onboarding.md](design-brief-requests-and-onboarding.md) and the handoff's tabs; this brief draws the strip, the wait line, the clock, and the manual link.

### C6. How the runs in Work link to these screens

The embed rule ([screens/work.md](screens/work.md)): **a run page embeds reads and links writes.** Draw each pair, with the "Part of run NAME, step N: TITLE" banner on the owning screen and the "Look at" embed in the step panel.

- **`paint-cycle`** (family 2.7): `watch` (a `check`) embeds the flagged rows of `PaletteMatrix` and `Findings`, read only; `substitute` (a `decision`, the board's) embeds the `nearest` list and links to Decisions, with no recommendation and a policy proposal where none is adopted; `refresh` (a `job`) and `doc` (a `plan` with no approvals kind yet) show a `Command` with Copy; `record` (a `person` step: last painted by building) attests in place; `request` is a branch that opens an `improvement-request` child run. Banner on `#/paint`: "Part of run Paint cycle, Buildings 1 and 2, step 3 of 9".
- **`maintenance-program`** (2.9, pest control the worked case): `read` embeds `Findings` of the program's brief; **there is no web loader for it**, so the panel reads "not served to the console yet" and the command (`jason pests`). `renewal` is a branch that opens a `contract-notice-window` child run, shown as one rail row; that run's `window` step embeds `NoticeWindow` read only, and the contract row on `#/contracts` carries the banner.
- **`loss-claim`** (2.8) `confirm-step` is a write another screen owns: the run shows "2 of 5 confirmed" and links to the packet, with no "Mark done". `guideline` is a `decision` step (the board's, recorded by the secretary). `notify` is a `person` step; jason contacts no insurer.
- **`contract-notice-window`** (2.5) and **`improvement-request`** (2.6): `window` and the request strip are embedded reads; the vote and the letter link to Decisions and Approvals.
- **A `RunLinks` chip** for each (a `doc` link is the stopgap kind): the schedule Doc, the packet, the contract reading, the request.

## D. The shared components, each once

Reuse (built): `ScreenHeader`, `Card`, `Tabs`, `DataTable`, `Drawer`, `Pill`, `Badge`, `Glyph`, `Confirm`, `Command`, `Doc`/`DocList`, `Recitation`, `ReadingLabel`, `Caveats`, `Freshness`, `DueDate`, `Timeline`, `StageSteps`, `Checklist`, `Findings`, `Money`, `HeldNote`, `EmptyState`, `RemoteView`, and the four paint parts. From other briefs (to build once, not redrawn): `BasisPill`, `RunLinks`, `RunStepPanel`, `RecordTrail`, `EvidenceLinks`, `RequestClock`, `RequestStateStrip`. Do not use `Stamp`: nothing here is the board's decision.

| Component | What it is | Data (real field names) | States |
|---|---|---|---|
| `PaintPage` (an adapter, then the page) | Fetches `paint`, maps loader to component shape, composes C1 | `schedules[]{title, source, sourceAddress, prepared, buildings, schemes, rows[]{label, surface, note, colors[]{scheme, code, maker, status, name, printedName, hex, lrv, exterior, families}}, counts, needsAPerson}`, `catalog{available, fetched, colors, command, note}`, `unavailable[]`, `reserve{next[]{year, description, category, costCents}, lastPainted{source}}`, `caveats` | loading; `found:false` ("The association has no color schedule yet."); catalog unavailable (the copy's age, or the command); rows with no paint |
| `ColorCheck` | The C1 check band | to add: `code, surface, building` in; `outcome` (on this surface, on another, near, not on it), `nearest{code,name,hex,distance}`, `scheduled{surface,scheme}` out | the four outcomes; no catalog; a color from another maker (entered, not checked); the board's "near enough" number not adopted (the page says so) |
| `PaintDates` | Last painted, next due, cost by building | `reserve.next[]`, `reserve.lastPainted`, a recorded event with a `DocRef` | recorded; implied (arithmetic shown); needs input (an invitation); no reserve study (`reserveNote`) |
| `EffectiveRecord` and `CoverageCell` | The C2 table | `components[]{component, kind, value, status, sources[], entries[], verified, declaration{points, words_cites[], differs}, policy{...}}`, `planMatched`, `privateHeld`, `openQuestions[]{key, title, with_whom, status, asked, answered, source}` | no plan matched; no specification for the plan; points (four words); differs (side by side, to the question); builder option; private entries held |
| `EntryCard` | One entry in a row's history | `ImprovementEntry`: `what, where, replaces, date, contractor, licence, permit, approval, cost_cents, product, model, serial, warranty, photos[], docs[], status, visibility, by, at` | shared; association; approval attached; none found; owner's figure labeled |
| `LossPacket` and `PacketStep` | The C3 packet | `steps[]{step, question, provisions[], recited[], shows[], confirmed_by, confirmed_at, state, held, open[]}`, `history[]`, `open_questions[]`, `confirmed`, `note`, `policy{carrier, number, renewal, deductibleCents}` | unconfirmed; confirmed; confirmed then corrected; held (provision missing, no policy, no guideline); no ladder (`found:false`) |
| `NoticeWindow` | The strip and its sentence | `NoticeWindowView{term, termEnd, termEndSource, opens, closes, delivery[], today, sent{day,by,doc}}` (to add) | open; not yet open; closed; one edge; term end needs input; a notice on record inside, before, or after the window |
| `ContractRow` | One agreement in the list | `ContractSummary{key, name, counterparty, method, confidential, counts, licenses[], signatures[]}` + the window | in force; proposal; unsigned copy; confidential; not read yet (a `Command`) |
| `ImprovementStrip` | C5's strip with the wait line | `state`, `history[]`, `waitingOn`, `clock{source, due, adopted}` | the states in the handoff's vocabulary; a statute clock; a proposed clock |
| `PartOfRunBanner` | "Part of run NAME, step N: TITLE" | a link from the run store, visible only to a viewer who may see the run | none; one run; two runs |

**Fixed words** (use exactly): "renamed", "discontinued", "not found", "not checked", "entered, not checked", "Screens and printers shift color. The number on the schedule governs.", "recorded / implied / reported / needs input", "None on record yet. Add the date with its source.", "points to the master policy", "points to the owner's policy", "ask a person", "Differences are questions, not findings.", "Unconfirmed: a person has not confirmed every step.", "The board has not adopted a deductible guideline.", "may not count", "UNSIGNED COPY: this copy is not the signed agreement.", "term end needs input", "A reading is evidence, not a pin.", "Viewing as NAME (admin view): go back to yourself first". Never "covered", "not covered", "at fault", "your responsibility", "approved" (for a color), "valid", "active", "late", "illegal", or "breach".

## E. Glyphs

Use the console's glyphs beside their words: `paint-bucket` (the palette, an empty schedule), `file-check` (recorded), `calculator` (implied), `user` (reported), `pencil` (needs input), `triangle-alert` (renamed, discontinued, a notice outside an edge), `circle-question-mark` (an open question, unknown), `circle-check` (confirmed), `lock` (confidential, held), `clock` (a window's days left), `minus` (none), `link` and `paperclip` (evidence), `arrow-left-right` (a difference to read, drawn calmly), `history` (the trail), `scale` (counsel reads). Propose a new glyph only where none says it, and name it for the idea: a **notice window** mark (two brackets on a line, which must never read as a progress bar), an **unsigned copy** mark (a page without a pen), a **points-to** mark (an arrow to a policy, never a shield or a check), and a **screen match** mark for a color difference (a swatch beside a chip, never a tick). The proposal mark asked for in the life-safety brief applies to jason's labeled proposals here.

## F. Decisions that are the design's, in one list

1. **Paint at 360 px:** one card per surface with a scheme chooser (recommended, as the handoff offers), a pinned label column, or one scheme at a time; and where the color check sits (a band under the matrix, recommended, or a drawer from the header).
2. **How a check result reads** without a pass or fail: the four outcomes as words, the difference number with "a screen match, not paint", and where the governing text is recited.
3. **Renamed versus discontinued on one chip:** where the printed name sits, and whether the `nearest` list is inline or in the drawer.
4. **Where the arithmetic of an implied date shows:** inline (recommended for print) or on focus.
5. **The unit tab:** the two coverage columns beside the status or below it; the wording of a `differs` cell so it neither alarms nor suggests coverage; the "unknown" note stated once.
6. **The packet:** a vertical stepper or an accordion; how whole provisions are shown without a wall of text (collapsed under a citation heading, open whole); where the trail sits; the packet as paper for an adjuster or the board (one to three pages, every unconfirmed step said so).
7. **The notice-window strip:** a band on a dated axis in the row (recommended) or only in the detail; how both edges, today, and the delivery survive 360 px and a screen reader; the order of the list.
8. **The improvement strip and clock:** whether the strip and the clock sit on one card; how a proposed clock reads to the board and is hidden from an owner.
9. **The `Confirm` wording** for each act (an entry, a visibility change, a packet step), and whether a record the person links shows a `Doc` preview inside the dialog.
10. **The "Part of run" banner and the "Look at" embed:** which rows of `PaletteMatrix` a `watch` step shows, and how a run's embedded window differs from the owning screen's.

These are not the design's: who may confirm a step (the offices that open P2; a second person is not required), the "near enough" difference for a color, what substitutes for a discontinued color, the deductible guideline, a notice window's meaning (the contract's words), a request's decision, and whether the board adopts any proposed policy.

## G. What can be designed now, and what waits

| Part | Now | Waits on |
|---|---|---|
| The palette, swatch, detail, dates (C1) | Yes: the loaders and four components are built | The view and its route; an adapter (the loader's `archived` is the component's `discontinued`, `colors` is a list not a record keyed by scheme, `source` is a string with `sourceAddress` not a `DocRef`, a not-found color has no hex) |
| Implied last-painted dates | Draw all three source words | The loader always sends `lastPainted: {source: "needs input"}`; the useful life is not read |
| The color check of a chosen color | Draw it | A loader and a `--request` command (design only); a profile `paint_policy()` for "near enough" |
| Refresh the catalog, make the Doc | Draw `Command` with Copy | No paint writer or job exists; the Doc replaces edits made in it, `Confirm` says so |
| Interior colors (`InteriorColorRegister`) | Draw the empty state and one report | The component and a register (`interior_reports()` is empty by default) |
| The unit tab and the packet (C2, C3) | Yes: both loaders and writers are built | The view; **the loaders do no viewer check** (no sign-in, no P2 test, no log of an opening, unlike `life-safety`), and the writers take `by` from the body when no one is signed in and have no admin-view refusal: a build item before a view ships |
| Plan for a unit | Draw "plan matched" | The loader takes `plan=`; no code bridges a unit to its plan (`unit_characteristics` is not wired) |
| Packet confirmations append-only | Draw the trail | `confirm_step` **replaces** a step's earlier confirmation (decision 2) |
| Packet pairs of provision and words | Draw each pair | `recited` lists only the found ones, so the words cannot be paired to `provisions` when one is missing; a loader change |
| "A claim file exists" | Draw the line | Not produced by `loss_packet_view`; `incident_history` events are strings |
| The incident behind a packet | Link only | No incident store; `incident` is a free string key ([screens/incidents.md](screens/incidents.md)) |
| Contracts and the strip | Yes, from the handoff and sample | A `contracts` loader that composes `NoticeWindowView`; the as-of check counts one edge (`current - notice_days`) while the reader has two |
| Improvement requests | Yes | The store, loaders, writes, and `jason improvements`; the base templates |
| The runs of C6 | Yes, as design | The engine's definitions for all five; a `LinkKind` for each record; a web loader for a maintenance program |

## H. A made-up community to design against

"Oakview" (no real association). Today is **Oct 12, 2099**. Roster: Robin Sample (manager), Pat Example (secretary), Lee Sample (treasurer), Sam Example (director), Dana Example (president), Kim Example (an administrator with no office, for the held state), and A. Owner (an owner; the owner view is refused these screens). Four buildings; plans A and B.

**Palette** ("Exterior Palette, prepared for the developer, 2099-01-15"; three schemes; catalog copy fetched Oct 3). Rows as printed: FASCIA (SW 7008 Example Cream, all schemes, ok), STUCCO TRIM (SW 7045 Example Slate, ok), STUCCO FIELD (scheme 1 SW 6999 Example Clay, **discontinued**, nearest SW 7041 Example Sand at 2.9; scheme 2 SW 6203 printed "Example Sage", **renamed** now "Sage Example"; scheme 3 Other-4410 Example Mist, hex typed, **entered, not checked**), ENTRY DOORS (SW 7006 Example Pearl, ok), GARAGE DOORS (SW 7048 Example Stone, ok), ROOF (tile, not paint). Dates: Buildings 1 and 2 last painted 2092 **recorded** (invoice `library:EX-INV-0042`), next due 2100, $50,000; Building 3 last painted 2095 **implied** ("2100 minus a 5-year life"), next due 2103, $25,000; Building 4 **needs input**. One interior report (SW 7008, Plan A living room, confirmed by 3 owners). Frames: all schemes; one scheme; a discontinued color's drawer; a color check for SW 7041 on STUCCO FIELD, Building 3 (near SW 6999, difference 2.9) and for a color on no schedule (not on it); no catalog copy; no schedule; Kim Example (held); a `watch` step's embed and its banner.

**Unit 14**, 123 Main St, Plan A, Building 3 (PayHOA unit id `u-0014`). Kitchen flooring original (plan sheet); bath flooring upgrade to tile (approval `imp-2098-0412`, permit, entry shared, the owner's figure $4,180, contractor "Vendor A" in the entry only); water heater equivalent replacement (invoice, entry shared); refrigerator builder option (closing sheet; open question with the agent); ceiling fan unknown; finished flooring where the declaration and the policy differ (question `oq-flooring`, with the agent, asked 2099-08-02). One private entry held. Frames: the main tab; plan not matched (all unknown, said once); no entries; an entry without a found approval (to the manager: "no approval on file for a change of this kind"; the owner's wording is the other brief's); the differs cell opened; Kim Example (held); Lee Sample (treasurer) reading the same tab as Robin.

**Loss packet** for `inc-2099-0003` (water damage in unit 14, found Jun 4): master policy Example Mutual, deductible $10,000, renewal 2100-03-01. Step 1 confirmed by Robin Sample Oct 3 (records `library:EX-DEC-01`, `drive:EX-PHOTO-9`), corrected by Pat Example Oct 9 (the earlier confirmation kept, marked); steps 2 to 4 unconfirmed; step 5 held (no guideline). History: two lines at the address (leads). Frames: unconfirmed at export; a provision the shelf lacks (held note names it); no ladder in the profile; no policy on file.

**Agreements** as in C4: Example Management, LLC (term end 2099-12-31 recorded; 60 to 120 days; certified mail; window Sep 2 to Nov 1; board item on the agenda of Oct 20), Example Pest Control (term end 2099-12-15; 30 to 60 days; window Oct 16 to Nov 15; a notice sent Oct 3 before the window), Example Landscape Co. (term end 2099-11-30; at least 30 days; closes Oct 31), Example Alarm Co. (term end needs input), Example Paving (a proposal, unsigned copy). A second frame for the strip with a notice two days after the closing edge.

**Improvement requests** as in C5: `imp-2099-1001` (solar, received Oct 1, statute day Nov 15) and `imp-2099-1002` (an ordinary application, the bathroom floor, clock `proposed policy` target Oct 31, board Oct 20, notice by Oct 16). Runs: Paint cycle for Buildings 1 and 2 (step 3 of 9, `substitute`), Pest control Q4 (step `renewal` opens a contract run), Water loss unit 14 (step `confirm-step`, 1 of 5).
