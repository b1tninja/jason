# Design brief: the annual disclosures packet (plan, collect, freeze, check, read, and hand off)

One page of orientation for the design agent, for the packet screen specified in [handoff-annual-disclosures.md](handoff-annual-disclosures.md) (the tab **The packet** of `#/disclosures`) and for the fiscal-year run that carries it ([../workflows/money.md](../workflows/money.md), section 2.5, steps B and D). It does not repeat the handoff; it says what to read in what order, each screen and shared component to draw, which glyphs, what is the design's to decide, what can be drawn today, and a made-up community to draw against. Where the handoff and this page disagree, the handoff and the code win, and this page is corrected. The reference is [../annual-disclosures.md](../annual-disclosures.md); the packet as a document made of documents is [../document-templates.md](../document-templates.md).

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, insurer, or private fact; made-up samples only ("Oakview", "Example Rd", "Jane Example", dates in 2099). The element ids below (`CIV 9901(b)(2)`) are placeholders; the real statute is cited only where a window or a delivery rule is recited.

**Checked against the code on 2026-10-11.** `jason packet annual-disclosures` takes exactly `--year` (required), `--values`, `--make-templates`, `--build`, `--draft`, `--building N`, and `--yes` (`src/jason/commands/packet.py`); nothing else, and nothing sends. The plan reads the library and Drive indexes and the profile's `Packet` (`jason.tasks.packets.plan`, `resolve`, `values_for`; `jason.community.packets.Packet`, `Part`, `PartSource`). `--build` writes `data/packets/<packet>-<year>/` with `packet.pdf` or `building-<n>.pdf` plus a `.json` per building and `manifest.json` (bookmark per part, "Page n of N" footer). **Not built, and nothing in the code names them:** `run.json`, `collect.json`, `part-map.json`, `read-through.json`, `send-plan.json`; `--check`, `--collect`, `--give`, `--freeze`, `--qa`, `--read`, `--send-plan`, `--archive`; a module `jason.tasks.annual_packet`; every `annual-*` loader (`grep "annual-" src/jason/web/sources.py` finds none); every write under `annual/`. **Built beside it:** `jason segments --file`, `jason preflight`, `jason review annual-disclosures`, `jason notices KEY --sync`, and `jason mailroom` with `--pdf`, `--units`, `--notice KEY`, `--mail-class`, `--tracking`, `--color`, `--by`, `--send --yes`, `--cancel` (a `--notice` letter defaults to first class); the notice catalog rows `annual-budget-report` and `annual-policy-statement` (each `30 to 90` calendar days before `Anchor.FISCAL_YEAR_END`, individual delivery, secondary copies) and the rows they carry (`collection-policy-notice`, `penalty-schedule`, `dispute-resolution-summary`, `architectural-requirements`); the `owner-info-solicitation` row (answers entered 30 days before `Anchor.ANNUAL_REPORTS`); `assessment-increase` (`Anchor.DUE_DATE`, 30 to 60 days). **Views:** `ui/src` has `CalendarView` (route `disclosures`, alias `calendar`) and `OwnerDisclosures` only. No `PacketRun`, `RequirementChecklist`, `CollectList`, `SendPlanTable`, or `PacketStages` exists in `ui/src` or in the untracked `src/jason/console/ui/components`. The statutes are on this machine's shelf (`CIV-5300-5320.md`, `CIV-4000-4070.md`, `CIV-5600-5625.md`), which git ignores. **The build's own default is a guess the page must not copy:** `values_for` sets `MAILING_DATE` to today unless `values.json` names it; the design's rule is "date not on record", a question.

## A. The idea, and the rules that run through it

**The idea, in six sentences.**

1. A year's packet is a **list of parts** in the order they print, each a document with its own source, day, and standing, and beside it the **law's checklist**: each element shows the part that answers it, or a gap line exactly as it will print.
2. The run is **plan, collect, draft, freeze, generate, check, read, send plan, sent, archived**. It ends not in a send but in a PDF per variant, a map of it, and a plan a person carries out. The page reads; a person runs each command.
3. Three days are kept apart and never merged: the **as-of day** (the day the run reads the law and the stores), the **dated day** (on the cover, inside the window), and the **sent day** (read from the ledger, never typed).
4. The board adopts by vote and the secretary records it. The packet **reads** an adoption from the decision record or the minutes; it has no control that adopts, and no state says "approved". "Read by NAME" records that a person read revision N and adopts nothing.
5. A **frozen** run is not edited. A change is a new revision with a reason; the first stays, and the first's checks, reading, and any send keep pointing at it.
6. Every date carries its **basis word**: `law`, `documents`, `counterparty`, `proposed policy`, or `person`. A day jason computes from a window is the board's to adopt and never wears a stamp.

**The rules** (each is in the handoff or AGENTS.md; a screen that breaks one is wrong):

- **Directors and officers have the same access to information.** The tab is board-only (manager, an officer, an administrator); a director reads what an officer reads at the same level. Counsel reads the checklist and the clock on grant. The owner view shows nothing here.
- **The secretary records the board's decisions; the treasurer and the board adopt the budget.** The page shows who entered a statement and the adoption it reads; it records neither a vote nor an adoption.
- **Recite, then label the reading.** A statute's words come from `data/authorities` verbatim, with the citation and "jason's consolidated copy, not an official restatement"; what they are read to ask is a `ReadingLabel`. Never a paraphrase in the place of the words; never a quote from memory.
- **jason never mails, sends, or posts.** The send plan is counts, pages, a cost, and commands to copy. No button starts a batch, a send, or a cancel.
- **Counts only in a send plan.** No name, address, unit, or id; the Mailroom's own plan holds those at its own level.
- **A gap prints where it is shown.** `GapPreview` shows the sentence the draft prints, from the same function. A final build refuses while a required element is missing, waiting, or stale; the page says "final" means only that.
- **A miss stays a miss; none on record is not none given.** A missing part says what was searched; a missing ledger entry says "none on record".
- **The checklist never says "complies".** The five words are present, present but stale, missing, does not apply, waiting.
- **Every state is a word and a glyph, never colour alone;** every write is a `Confirm` that spells out what is recorded and in whose name; nothing is worked out in the browser (a day is never counted client-side).

## B. Reading order

1. [handoff-annual-disclosures.md](handoff-annual-disclosures.md), whole: "What the design must keep" and the data shapes first.
2. [../workflows/money.md](../workflows/money.md) section 2.5 (`fiscal-year`: B1 to B7 the budget and the CIV 5605 test, D1 to D14 the packet), its failure rows (`fiscal-year.win`, `B6`, `D6`, `D12`), and section 4 (the clocks and their basis words).
3. [screens/collect-items.md](screens/collect-items.md) and section C4 of [design-brief-board-records.md](design-brief-board-records.md): **the Collect tab is drawn there. Link it; do not redraw it.** Here it is a frame in the packet page.
4. [screens/notices.md](screens/notices.md) and [design-brief-notices-and-mailroom.md](design-brief-notices-and-mailroom.md) (C5 to C8: the preview, the mail options, the class a notice needs, the cost line). The send plan hands off to them.
5. [screens/work.md](screens/work.md), "Where a step's work happens", and [design-brief-work.md](design-brief-work.md): the fiscal-year run embeds the reads and links the writes.
6. [design-gaps.md](design-gaps.md) (this brief is its write-next item 5). Then this page's D beside H.

## C. The screens

The packet is the tab **The packet** at `#/disclosures/packet/<year>`; its sub-tabs (`?tab=`) are Checklist, Parts, Collect, Checks, Read-through, Send plan, and Record. The calendar of recurring deadlines stays the first tab of `#/disclosures`.

### C1. The head, always above the sub-tabs
`DayTrio` (as-of, dated, sent: each a line with its source) over `PacketStages` (ten stages; the one in work marked, "Now: collect, waiting on 4 items"; **sent** and **archived** read from logs) and a count strip (`Stat`: 27 elements, 19 present, 2 stale, 1 missing, 4 waiting, 1 does not apply, with a table twin). A `ClockStrip` of the fiscal year's end, the window, the answers date, and the dated day (C9 draws it whole). The caveat sits under it: "A clean checklist says each element has a part, current, or a visible gap. It is not a finding that the packet complies." Draw: planned; collecting; frozen; sent; "the profile defines no annual packet" with the command; no run yet; a later revision exists.

### C2. Checklist
`RequirementChecklist`: a table grouped by statement (annual policy statement, annual budget report), each group headed by its statute, window, and clock in words. A row (`RequirementRow`) opens in place: the element and its citation (`Recitation`, as of the as-of day), `RequirementWord`, the parts that answer it as `Doc` chips, `applies` as an answer word, `DeclaredRead`, `GapPreview`, and the question and where it goes (Collect item, applicability question, board item). Draw one row in each of the five states; a carried element nested under the statement that carries it; a row declared but "not found in the text" and one "found, not declared"; and the **Findings** band when the catalog and the model's table differ ("a person reviews the join once").

### C3. Parts
`PacketOrder`: the parts as a nested list in the order they print, with `ContentsPreview` beside it (page numbers "after the build"; a part with a gap shows its gap line in its place). A part row: title, kind, `BasisWord`, `PartStanding`, freshness, the as-of with its rule in words, the source `Doc` chip, the hash's first twelve characters, pages in each variant, the elements it answers. A **stored** part says "attached as it is: not re-drawn"; a **passage** shows the digest read against the digest now; a **computed** part shows the inputs it read. Draw per-building variants (Building A and B differ in one part), a nested part with its gap lifted to its parent, and `PartToConfirm` (jason's proposed file and pages, labeled "jason's proposal", several candidates: "jason picks neither").

### C4. The values worksheet
`ValuesWorksheet`: what `--values` writes, read. Each token the templates carry, its value, its **layer** as a word in the order the build applies them (profile, packet, computed, statute's words, the year's file, which wins), where it prints, and its state: filled, open, a standing value not confirmed this year ("Still true for fiscal year 2099?" behind `Confirm`), changed (new value, old kept). A computed value is labeled computed: a `MAILING_DATE` that is today's date shows "computed: today; no dated day chosen" and is never presented as the dated day. Open tokens are listed first and link to the Collect item that asks for them.

### C5. Collect
Linked, not redrawn: [design-brief-board-records.md](design-brief-board-records.md) C4. In this page it is one frame, with the packet's wording (`CollectList` grouped by role; `StandingValueRow`). Draw the one thing it needs here: a **board statement** entered by the secretary, "entered by Jane Example; not yet adopted", beside "no act on record (minutes searched)", and the same once the decision record shows the adoption ("adopted at the meeting of Mar 16, 2099, recorded by the secretary"). Also the budget row: `B6 Adopt the budget` is read, never recorded; the page shows the adoption day or "no act on record".

### C6. Checks, as findings
`QaResult`: not run; running; then four groups, each with its age and the command that runs it again. **Cross-part** (`CrossCheckRow`): two values side by side with each source (the regular assessment in the budget and in the disclosure summary; the reserve transfer and the study's plan; the insurance summary and the declarations; the recipients and the unit count); agree, differ (neither is chosen), one side not on file. **Segment** (`SegmentCompare`): the part map beside `jason segments --file` of the PDF; agree, inside, missed, contradiction; a contradiction is shown first and is a finding about the segmenter, the footer, or the splice, never about the packet; the measured recall is a caveat. **Preflight** (`PreflightCard` per attached scan, read only). **Review** (`jason review annual-disclosures`, findings only). Draw: all agree; one `differ`; one contradiction; "not run (the PDF is not built)"; a scan with a blank back that is the splice's own.

### C7. The freeze, and what changing it means
`FrozenRun` on the **Record** tab. Not frozen ("a draft's values are not kept; freeze fixes the days, the values, every part's address and hash, the templates' versions, the passages' digests, the layout, the checklist as it stood, the tool's version"); frozen (revision 1, a `Seal`, the hashes, the PDF's sha256 as the packet's identity); **superseded** (revision 2 with its reason, who, when; revision 1 stays in the ladder, dimmed and still readable, its checks and its reading marked "of revision 1"). A freeze refused while a required element is missing, waiting, or stale, unless it is a draft freeze marked so. A freeze after the dated day reads "frozen after the day it is dated". The page words what changing a frozen packet means: a new revision, its checks run again, the earlier reading becomes stale ("Read revision 1; this is revision 2"), and a revision made after a send does not recall what went out. Draw the ladder, and the refusal sentence.

### C8. Read-through
`ReadThroughList`: seven groups in the order a reader needs them (gaps and stale parts; the board's statements; each standing value; the cross-part checks; the checks' findings; each statutory part by page; the clock), each line a link to where it is. `ReadRecord` at the foot: "Record that I read revision 1 as Jane Example. This records a reading and adopts nothing." States: not read; read by NAME on DAY; stale.

### C9. Send plan and the calendar
`SendPlanTable`: one row per variant and channel: recipients (a count), billed pages per letter, the estimate (`CostLine`, "charged to the association", the pricing's date), the window's last day; the order, email first and mail after, with its reason; the commands as `Command` blocks (`jason mailroom --pdf PACKET.pdf --units U --notice annual-budget-report-2099`, the batches, `jason notices KEY --sync`); `ProofLink` to the two notices. **The mail class:** the individual delivery rule is recited (CIV 5320(a); CIV 4040(a)(2), whose words are in the notices brief, C7) and read under a `ReadingLabel`: "jason's reading, not the statute's: a packet that goes as an individual notice to a member with no valid method on record goes first class or better; the Mailroom defaults a `--notice` letter to first class, and a preview names the class." Whether a given mailing is an individual notice is for the board and counsel. A packet over four billed pages shows the sixth-page postage line and names the choice as the board's (decision 3 of the handoff).

**The dated calendar** (`PacketCalendar`, a list or a month strip with a table twin) lays the year out from the fiscal year's end and the catalog, each row a date, a plain sentence, and a `BasisPill`. Recite first: CIV 5300(a), "an association shall distribute an annual budget report 30 to 90 days before the end of its fiscal year."; CIV 5310(a), "Within 30 to 90 days before the end of its fiscal year, the board shall distribute an annual policy statement"; CIV 5320(a), "the association shall deliver one of the following documents to all members by individual delivery pursuant to Section 4040". Then the computed days (Oakview, fiscal year ending Jun 30, 2099), each from `Timing.window`, never counted in the browser: window opens Apr 1 `law`; window closes May 31 `law` (a Sunday here: "how a court counts a period ending on a weekend or holiday is for counsel"; the page moves nothing); owner-information answers entered by Apr 15 `law` (the 4041 row's days, anchored on the dated day); collect items due by Apr 20 `proposed policy`; the dated day May 15 `person`; stage days (freeze, read, send plan) `proposed policy`; the increase notice, if the budget raises the regular assessment, 30 to 60 days before the increase is due Jul 1: May 2 through Jun 1 `law` (CIV 5615); the reviewed statement 120 days after the close, Oct 28 `law`, when it applies (CIV 5305), shown as the next run's. A stricter clause is its own row: "Oakview's declaration asks the last day be May 16 `documents`, clause named; the statute's May 31 stands beside it". Draw the date not on record, a dated day outside the window, and a send after the last day in the law's words.

### C10. In the fiscal-year run
The run page's steps D1 to D14 embed these reads and link the writes ([screens/work.md](screens/work.md), "Where a step's work happens"): D1/D2 the checklist and worksheet; D3 the Collect frame; D8 and D9 the parts, the freeze, and the checks (a `job` step: the command and its result); D10 `ReadRecord` (a `person` step, the attestation is the run's own write); D11 the send plan; D12 a `person` step that shows the log's sent day and the command, "Mark done" only after the ledger shows it; D14 the archive. Draw the step panel for D3 and D9, and the banner on the packet page, "Part of run Fiscal year 2099, step D3: Collect figures and files".

## D. The shared components, each once

Built (`ui/src/components`): `Card`, `DataTable`, `Tabs`, `Pill`, `Badge`, `Glyph`, `Seal`, `Stat`, `Checklist`, `StageSteps`, `Findings`, `Caveats`, `Recitation`, `ReadingLabel`, `Doc`, `Command`, `Confirm`, `DueDate`, `Clock`, `Timeline`, `CostLine`, `Money`, `Evidence`, `EmptyState`, `RemoteView`. Specified, not built (draw from the built parts and say so): `TerminalStep`, `AgeStamp`, `BasisPill` (work.md), `CollectTracker`, `CollectItemRow`, `StateWord` (collect-items.md), `PreflightCard` and the segment tree (handoff-intake-review.md), `AsOfBanner`. New to draw: the packet components of the handoff's table, each once.

| Component | What it is | Data | States |
|---|---|---|---|
| `PacketRun`, `DayTrio`, `PacketStages` | The tab, the three days, the ten stages | `annual-packet`: `days`, `stages`, `counts`, `notices` | the handoff's list; sent and archived read from logs |
| `RequirementChecklist`, `RequirementRow`, `RequirementWord`, `DeclaredRead`, `GapPreview` | The law's checklist and the gap as printed | `annual-requirements`: `groups[].rows[]` | five words; declared and read shown together, never reconciled |
| `PacketOrder`, `PacketPartRow`, `BasisWord`, `PartStanding`, `ContentsPreview`, `PartToConfirm` | The parts in print order | `annual-parts`: `parts[]`, `contents` | stored, nested, passage, computed; variants differ |
| `ValuesWorksheet` | The merged token values and their layers | the run's `values.json` through `values_for` (layers: profile, packet, computed, statute, year's file) | filled; open; standing not confirmed; changed; computed day shown as computed |
| `QaResult`, `CrossCheckRow`, `SegmentCompare` | The checks as findings | `annual-checks` | not run; agree; differ; inside; missed; contradiction |
| `FrozenRun`, `RevisionLadder` | The freeze and its revisions | `annual-record` | not frozen; frozen; superseded; refused; frozen after the dated day |
| `ReadThroughList`, `ReadRecord` | The reader's list and the one record | `annual-read` | not read; read by NAME; stale |
| `SendPlanTable`, `ProofLink` | Counts, pages, cost, commands, the two notices | `annual-send-plan` | email and mail rows; no recipients; count differs from unit count; no send control |
| `PacketCalendar` | The dated rows with legal windows | `annual-packet.clock` and the catalog | opens, closes, stricter clause, weekend caveat, date not on record, outside the window |
| `ClockStrip`, `BasisPill` | The deadlines and their basis | `clock[]{label, date, basis, law{words, source}}` | five basis words; a legal clock recited; a proposed day never a stamp |

**Fixed words** (use exactly): "present", "present but stale", "missing", "does not apply", "waiting", "declared, not found in the text", "found, not declared", "declared, not read", "frozen", "superseded by revision N", "read by NAME on DAY", "not yet adopted", "no act on record", "date not on record", "none on record", "jason's proposal", "jason's reading, not the statute's", "as printed in a draft", "No control here sends, mails, or posts". Never "approved", "compliant", "complete", or "sufficient" on a control or in a state; "final" only with its meaning beside it.

## E. Glyphs

Use the console's (`circle-check` present and confirmed, `triangle-alert` stale and a contradiction, `octagon-alert` refused, `circle-dashed` missing and not asked, `clock` waiting, `lock` frozen and held, `paperclip` and `link` the parts and evidence, `history` the revisions, `scale` a legal basis, `circle-question-mark` date not on record, `minus` does not apply, `eye-off` withheld). New, named for the idea: a **sheet with a dashed outline** (a gap that prints), a **locked sheet with a revision tick** (a frozen revision, after the notices brief's "locked sheet"), and an **eye** for "read by NAME", which must never look like a check, a stamp, or an approval. Each sits beside its word.

## F. Decisions that are the design's, in one list

1. **Tab order and weight.** The head always visible with the sub-tabs below (recommended), or a left rail of stages. The checklist is first; the Record tab last.
2. **Checklist grouping:** by statement with a state filter (recommended), or flat by state.
3. **How a gap reads:** the boxed block that prints, with its label, on its own line in the row; how many to show collapsed.
4. **How the freeze reads as immutable** without a padlock cliché: a seal, the hashes, a ladder; and how revision 1 stays visible after revision 2.
5. **The calendar's shape:** a list (recommended), a month strip, or a line from the window's first day to its last with the dated day marked; and where the weekend caveat sits.
6. **How the three days read** so the dated day and the sent day are never taken for one.
7. **The Confirm's wording** for each write, and whether a library file shows a `Doc` preview in the dialog.
8. **Narrow screens (under 720 px):** the tabs become a "Go to" select; rows become cards; a gap is full width and never truncated; `SegmentCompare` stacks as pairs of lines; the send plan's rows are cards.
9. **Print:** the read-through list and the send plan, for the board's record, every proposed day labeled.

These are not the design's: the handoff's eleven open decisions (where part questions go, one tab or its own screen, the summary route or the full report, where statements are entered, the owner view, the footer), whether the board adopts a day, the budget, a policy, or a statement, who is asked for a figure, and what the law means on a weekend.

## G. What can be designed now, and what waits

| Part | Now | Waits on |
|---|---|---|
| Head, stages, checklist, `GapPreview`, `ClockStrip`, `PacketCalendar` | Yes, from H | The loaders `annual-packet` and `annual-requirements`, and `jason.community.annual_packet:checklist` (to write) |
| Parts, contents, per-variant pages | Yes | `annual-parts`; the definition builder and a part map with pages (today `manifest.json` per building has the bookmarks) |
| Values worksheet | Yes, from `values_for`'s layers | A loader over `values.json`; the "no dated day" state needs the run store, since the build defaults `MAILING_DATE` to today |
| Collect frame | Yes (drawn in the board-records brief) | `collect.json`, `annual-collect`, the writes; items are fixed when a run opens (collect-items decision 1) |
| Checks | Yes | `annual-checks`; the cross-part checks (to write); `jason segments --file` and `jason preflight` exist and are read only |
| Freeze, record, revisions | Yes, drawn | `run.json`, `--freeze`, the revision writes: none exist |
| Read-through and `ReadRecord` | Yes | `read-through.json`, `annual/read` |
| Send plan | Yes, from H; commands are built | `annual-send-plan` over `notice_delivery` counts, `payhoa.pricing`, `sent.jsonl`; the two-person send kind is not registered |
| The CIV 5605 increase test (a finding in the budget stage) | A frame only | Nothing computes it yet (money.md B4 "not built"); the insurance summary assumes a January 1 year start (`insurance_rows`), so a different fiscal year reads the term in force on the wrong day |
| Run embeds (C10) | Yes | The workflow engine's loaders `work`, `work-run`; no `fiscal-year` definition is registered |

## H. A made-up community to design against

"Oakview HOA": 50 units in Building A and Building B on Example Rd, fiscal year ending Jun 30, 2099, run `2099-fy`, packet `annual-disclosures`, notices `annual-budget-report-2099` and `annual-policy-statement-2099`. People: Jane Example (manager), A. Treasurer, A. Secretary, Sam Example (a director), Kim Example (an administrator with no office), A. Owner (no access). As of Mar 2, 2099; window Apr 1 through May 31; dated day May 15 (chosen by Jane Example Feb 20); collect items due Apr 20 (`proposed policy`); answers entered by Apr 15.

**The checklist** (27 elements: 19 present, 2 stale, 1 missing, 4 waiting, 1 does not apply; findings 2):

| Element | State | The point it makes |
|---|---|---|
| `CIV 9901(b)(1)` the pro forma budget | present, standing `draft`, "not yet adopted: no act on record (minutes searched)" | A part that exists but is not adopted |
| `CIV 9901(b)(2)` the reserve summary pages | missing; "Searched: library path 'Example Folder/2099/Example Reserve Summary*', index read Mar 1" | A gap that prints; a miss is the search's |
| `CIV 9901(b)(9)` the insurance summary | present but stale: the term covering Jul 1, 2098 is not on file; newest is the term before | The as-of rule |
| `CIV 9902(a)(3)` the posting location | waiting: a standing value not confirmed for 2099 | A standing value |
| `CIV 9902(a)(7)` the electronic voting item | does not apply, by the recorded answer of Jane Example | A row that stays |
| `CIV 9901(b)(10)` the FHA statement | present, passage digest `1122334455aa` equals the digest now | A passage part |

**Parts** (print order): Cover; Annual Budget Report (nested: budget, reserve summary, insurance summary, FHA statement on its own sheet, Charges For Documents form, disclosure summary); Master policy declarations (stored, `declarations-example.pdf`, `9e2f4b7c1d0a`, pages 3 to 5, P2, shown by kind and title outside the level that opens it); Annual Policy Statement (nested). Building A and Building B differ in the FHA statement.

**Checks:** regular assessment $412.00 in the budget, $418.00 in the disclosure summary (`differ`, neither chosen); recipients 51 against 50 units in the packet (a send-plan finding); the segment check: 6 agree, 1 inside (declarations within the insurer's longer file), 1 missed (cues listed), and in a second frame one **contradiction** at a part boundary; a scan with a sideways page.

**Send plan:** Building A email 31, mail 17 (41 billed pages, 30,960 cents, `payhoa.pricing` of Oct 1, 2098), secondary copies 3; Building B email 28, mail 22. A second frame: the packet over a letter's four pages, with the board's choice named as the board's. **Calendar frames:** as of Mar 2 with a dated day; no dated day chosen; a dated day of Jun 5 outside the window; the declaration's stricter last day of May 16; a send plan read after the last day. **Frozen frames:** not frozen; frozen Apr 24 as revision 1 with 41 values and 12 parts; revision 2 on May 2 for "the budget summary corrected" with revision 1's reading marked stale; frozen after the dated day. **Viewers:** Jane Example and Sam Example read the same page; Kim Example (an administrator with no office) sees the counts and the commands, not the P2 titles; A. Owner is refused; "Viewing as Jane Example (admin view): go back to yourself first" replacing each control.
