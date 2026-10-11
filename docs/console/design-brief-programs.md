# Design brief: Programs (the register, one program's page, and how a program's cycle is a run in Work)

One page of orientation for the design agent, for the programs screens specified in [handoff-programs.md](handoff-programs.md) (the spec, with its proposed payloads) and settled in behavior by [../programs.md](../programs.md). It does not repeat them; it says what to read in what order, each screen and component to draw, what is built and what has no view, and a made-up community to draw against. The standing programs it draws from are the pest, backflow, and elevated-elements programs ([../workflows/property-safety-vendors.md](../workflows/property-safety-vendors.md)) and the programs a declaration may require (an inspection and prevention program, a maintenance manual); `programs.md` calls the last two the worked cases.

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, section number, or private fact; made-up samples only ("Oakview", "Example Pest Co", "Example Declaration 9.9", 2099).

**Built, checked against the code on 2026-10-11.**
- **Reads that feed a program's page today.** `jason pests` and the `pest_program` tool (`tasks/pests.py`: products by EPA number, rodent-station activity by month, label checks, visits by building, the vendor's inspection reports; MCP only); `jason backflow` with the web loaders `backflow` and `watchlist`; `jason inspections` and `jason life-safety` with the loader `life-safety`; `jason deadlines` and `calendar_rows` for elevated elements (there is no `jason elevated`); `jason applies`; `jason duties --documents KEY`; `jason conflicts --leads`; `jason schedule` and `jason schedule-evidence --record`; `jason workflow`. Views: `#/duties`, `#/work` (list, run page, definitions, start), `#/actions`, `#/decisions`, `#/approvals`, `#/controls`.
- **No view and no loader.** Nothing named `programs` exists: no `jason programs`, no `program_catalog`, `program_detect`, or `program_resolver`, no `ProgramRequirement`, `ProgramStanding`, or adoption verb class (`models/meetings.py` reads a motion's outcome, not its verb), no `DocumentKind.PROGRAM` or `PROGRAM_RECORD`, no program collection (`CollectionKind` has legal case and ad hoc only). `tasks/record_standing.programs_for` returns "the program catalog is not built" and `#/setup/records` shows that sentence as "Unavailable": the one built empty state. The pest program has no web loader (`web/sources.py` has none), `backflow` has a loader and no view, and `ui/src` has no program view or route.
- **Work.** Two definitions are registered (`owner-info-cycle`, `control-adoption`). `maintenance-program`, `backflow-annual`, `elevated-elements`, and `life-safety-period` are design only. `BasisPill`, `RunRow`, `WorkflowRail`, `RunStepPanel`, `ClockStrip`, `ChangedSince`, `StageSteps`, `Recitation`, `ReadingLabel`, `DecisionBrief`, `QuestionCard`, `ControlRow`, and `ControlStateWord` are built. `PartOfRunBanner` is not ([screens/run-links.md](screens/run-links.md)).

## A. The idea, and the rules that run through it

**The idea, in six sentences.**

1. A **program** is something the law or the governing documents say the association must adopt and carry out. The register asks of each: what does it require, did the board adopt it, is it carried out, when was it last done, when is it next due, and who does the work.
2. The requirement is **recited whole** from its source with the version in force, before anything jason says about it. A reading of it (adopt, or adopt and implement; whether it also binds owners) is labeled and says whose.
3. **Adoption is the board's recorded decision.** The secretary records it; the console has no control that adopts. A program "in force" is a **reading jason labels**, from what the minutes' verb says (adopted, delegated, directed, listed, reviewed, quoted, declined), never from a file name and never from a quotation of the section.
4. Document, adoption, and records are **three evidences, three words**, because each fails on its own. "No act on record" is not "not adopted"; "not on file" is not "not done"; each says what was searched.
5. Every date says **whose** it is (`law`, `documents`, `counterparty`, `proposed policy`, `person`); a date jason computed says "computed". Where a document says "periodically", the page shows a question, not a number.
6. A program's period (a quarterly walk, a yearly test, a nine-year inspection) is a **run in Work**. The register reads; the run does; the person acts, in their name, behind a `Confirm`.

**The rules** (each is in the spec or the code; a screen that breaks one is wrong):

- **Directors and officers have the same access to information** (decided 2026-10-11). There is no director-only or counts-only view. A level (P0 to P3) decides what a viewer sees, as on the other screens; the owner view never sees `#/programs`.
- **jason computes no legal conclusion.** No "compliant", "violation", "in force against owners", "late by law", "safe". The words are the code's: `ProgramStanding`, `Shape`, `Cadence`, `Source`, and the schedule's `Standing` words, unchanged.
- **A program is not made "current" or "adopted" by a file.** A document on file with no act is **drafted**. A vendor's approved proposal is implementation evidence, shown apart as "not an adoption". A document that says it was adopted is "stated by the document itself" until an act is found. Both dates (the act's, the document's own) are shown, labeled, and neither is chosen.
- **A condition of approval** is its own group with "whether it binds the association is not settled", never listed beside the declaration's rows as if it bound.
- **jason contacts no vendor.** It shows the vendor, the licence check, and "Ask the vendor" as a draft a person sends (a plan in Approvals or the Drafts screen). No control sends, calls, or books.
- **A silent cadence is the board's.** A proposed value is labeled "proposed, not adopted" with its source. An event or continuous element ("immediately", "at all times") has a response clock or a standing state, never an "overdue" date.
- **A saved date is not an inspection date; a payment is not an inspection; a copy is not a new inspection.** Each is shown as what it is.
- **Owners' halves:** the page lists an owner's duty, names the notice that tells owners, and shows nothing about any unit or owner.
- **A miss stays a miss.** An unresolved reference or a conditional row with a missing fact is a question with the search made, never a guess and never "missing".

## B. Reading order

1. [handoff-programs.md](handoff-programs.md): "The idea", the component table, "The vocabulary", the payloads, "What the design must keep", then its numbered decisions.
2. [journeys.md](journeys.md), journey (i): the whole adoption of a missing program as a day-by-day flow.
3. [../programs.md](../programs.md): "Vocabulary", "The four cadences", "Finding what exists" (the six stages and the verb-class table), "Overlap: one obligation per authority", "Implementation tracking".
4. [../workflows/property-safety-vendors.md](../workflows/property-safety-vendors.md): section 2.9 (`maintenance-program`), 2.3 (`backflow-annual`), 2.4 (`elevated-elements`), 4 (the clocks and their basis), 5 (the screens).
5. [screens/life-safety.md](screens/life-safety.md) and [design-brief-life-safety.md](design-brief-life-safety.md) (reference; do not redraw the systems or the deficiency register: a program links to them), [screens/schedule-and-duties.md](screens/schedule-and-duties.md) ("record done"), [screens/work.md](screens/work.md) and [screens/run-links.md](screens/run-links.md), [design-brief-work.md](design-brief-work.md), and [design-gaps.md](design-gaps.md) rows P5 and P6.
6. [screens/controls.md](screens/controls.md) and the built `ControlRow`: the nearest built register, and the one the programs register must not be confused with (decision 9).

## C. The screens

### C1. The programs register (`#/programs`, proposed; board only)

`ScreenHeader` with the gap summary (required, missing, drafted, adopted, questions, detected waiting on a person) and `Freshness` (the index and the minutes read, "minutes not indexed before 2098-01"), then `Tabs`: **Register**, **Gaps**, **Detected**, **References**. The Register groups by source in the order of authority (statute, statute with a condition, declaration, **condition of approval** apart). One row per program:

```
+----------------------------------------------------------------------------------------------------------+
| DECLARATION                                                                                               |
| Program                  Requirement (source, whole)   Adoption (from the minutes)  Last done    Next due   |
| Moisture inspection      "the Association shall adopt  drafted                      no record     none:      |
|   and prevention         and implement a moisture ..." no act on record               kind shows    no clock  |
|   [required]             Example Declaration 9.9(a)    minutes 2098-01..2099-09:    it            stated    |
|   vendor: none           [Read whole] jason's reading: 19 sets, 2 not read                                 |
|                          adopt and implement                                                              |
| Pest program             "if the Association adopts    optional                     2099-09-24    2099-10-22 |
|   [optional]             an inspection and preventive  no act on record              visit  [COUNTER-       [COUNTER- |
|   Example Pest Co        program ..." Example Decl 9.4 vendor proposal approved      PARTY]        PARTY]    |
|   licence checked 2099    [Read whole]                  2099-02-17: not an adoption                        |
| STATUTE WITH A CONDITION                                                                                  |
| Schedule of penalties    "the board shall adopt and    a question                   --            --        |
|   [question]              distribute ... a schedule"   Does the association impose  (no program)           |
|                           CIV 9902 (made up)           penalties? [Answer]                                 |
+----------------------------------------------------------------------------------------------------------+
```

- **Columns:** program (title, `StandingWord`, vendor); requirement (the cite and the words, `Read whole` opens the whole `Recitation`; never an ellipsis outside a disclosure); adoption (the word, the **verb class** of the act, its date, and what was searched); last done and next due (each a date with its `BasisPill`, and "computed" where jason counted); the vendor (name and licence check, no contact link). The row opens in place (`aria-expanded`) to the `EvidenceTrio` and the `LifecycleStrip`; the title links to C2.
- Draw: a group with none ("Declaration: none confirmed yet. 4 detected, waiting on a person"), the whole register with no catalog (the server's reason, as `programs_for` says it), a program with **several candidate documents** ("jason picks none"), a **stale** row, a **default applies** row (the statute's procedure, recited), a held document (a line with its reason and no content), and the phone layout (the row becomes a card with the three evidences as three lines).
- Filters: source, standing, "needs a person" (a question, a detection, an act to record), vendor, and the as-of day (`Clock`).

### C2. One program's page (`#/programs/<key>`, proposed)

The page reads in the order the user's question runs: **requirement → adoption → records → next due**; the rest are below.

```
+-----------------------------------------------------------------------------------------------+
| Moisture inspection and prevention program      [drafted]       Command: jason programs decl-9-9 |
| mandate required · program on file · act: no act on record · records: none shown · owners: not on file · review: none |
+-----------------------------------------------------------------------------------------------+
| THE REQUIREMENT  Example Declaration 9.9(a), as amended; version in force 2099-10-12            |
|   "the Association shall adopt and implement a moisture ... program which shall include ..."     |
|   jason's reading (unconfirmed): adopt and implement: both are asked      [Confirm as NAME]      |
|   step 1  "Inspect the common areas not less frequently than quarterly"  fixed: every 3 months   |
|   step 2  "Periodically inspect the irrigation"   silent: the document sets none; the board's   |
|           proposed 3 months from the study of 2098: proposed, not adopted                        |
|   step 3  "immediately take appropriate corrective action"  event: no number; a question          |
| ADOPTION  no act on record (19 sets read, 2 not read; minutes not indexed before 2098-01)        |
|   board item's result · 2099-08-30 · [adopted] · "approved the example program" · 4 yes, 0 no   |
|   minutes entry 2099-09-14 · [quoted] "quotes the section: not an act"                           |
|   the document's own footer says adopted 2099-09-19: both dates kept, neither chosen              |
| RECORDS  Example inspection worksheet: 1 dated entry (2099-09-12, 14 areas), 1 "saved on" (a      |
|   revision date, not an inspection)        step 1: overdue   step 2: no clock                    |
| NEXT DUE  Common-area inspection, every 3 months: first due 2099-12-12 computed from the adoption |
|   date [DOCUMENTS], proposed, not tracked     [Show the commands]                                 |
| THIS PERIOD'S RUN  none open.   [Start a run]                                                    |
+-----------------------------------------------------------------------------------------------+
```

Below: **The document** (`ProgramDocumentCard`), **Review** (`ElementReviewTable`: found at, not found, unknown, for a person; "confirmed" is a person's with the name), **Owners' part**, **Members**, **Questions**, **Proposal** (`ProposalFlow`, `DraftPreview`, `AdoptionBrief`: no recommendation). Draw the page for a program with an act on record, for one whose only act is a vendor's approval, and for a page held under the phone's band `select`. Draw the writes as `Confirm`s in the signed-in person's name (confirm a mandate, bind a document, record an adoption with the record that states it, confirm a verdict, generate the draft, put the draft on the agenda) with the CLI beside each; none adopts.

### C3. A maintenance-type program with a vendor: the pest page's Records band

The built `pest_program` shapes the band (draw from it; no loader yet). Per property: **plan** (subscription titles); **visits** by month and building; **products** by EPA registration (active ingredient, class, applications, first and last day, methods, areas, targets); **label checks** as `Findings` (an interval between treatments, a landscape use: each a question for the manager, never a violation); **rodent stations** (checked, refilled, highest activity by month); **inspection reports** with their quotes; the vendor's licence and its check ("verified 2099-03-04 on the board's page"). Beside them, apart: the proposal approved (implementation evidence, "not an adoption"), the contract, and the vacate-notice clock when a treatment needs occupants out (`law`, two edges: not less than 15 nor more than 30 days). The vendor card shows name, licence, and insurance dates, and **Ask the vendor** opens a draft a person sends. Elevated elements and backflow reuse the page: per-building rows with "date not on record" as a question, and the built `NoticeClock` and `Discrepancy` (every date side by side, no winner).

### C4. How a program's cycle is a run in Work

A program does not copy a run; it links to one. The page's **This period's run** strip is a `RunRow` for the open run of the program's current period, with the current step, who it waits on, and the next clock with its basis; the register's Next due cell links to the same. On the run page (`#/work/maintenance-program/<id>`, design only) the rail reads: standing (check) · adopt (decision, the board; the secretary records) · sync (job) · read (check) · ask (plan) · licence (person) · vacate / vacate-notice (branch, plan) · renewal (branch, opens `contract-notice-window`) · review (person). A `backflow-annual` or `elevated-elements` run is the same shape with its own clocks. Draw: the strip with a run waiting on the vendor (`counterparty`), the same program with no run and a period due within 60 days (the trigger), a run past a date, the rail with the adopt step marked "the board; the secretary records", and the "Part of run NAME, step N" banner on the program page (not built; draw from `run-links.md`). A step that completes a period writes the period's occurrence through "record done" ([screens/schedule-and-duties.md](screens/schedule-and-duties.md)); the register then moves Last done. Nothing on the run page adopts, sends, or books.

### C5. Gaps, Detected, References

Draw each tab once from the handoff (`GapQuestionRow`, `DetectionLead`, `ReferenceRow`): a detected mandate is a `Recitation` of the sentence, the shape word as "jason's reading, unconfirmed", and confirm, correct, or reject as signed records; an unresolved reference reads "not found" with the query run. The third gap group (newer law) links to `jason conflicts --leads` and the conflicts screen with no third copy of the lead.

## D. The shared components, each once

Reuse (built): `ScreenHeader`, `Card`, `Tabs`, `DataTable`, `Pill`, `Badge`, `Glyph`, `Confirm`, `Command`, `Doc`, `Recitation`, `ReadingLabel`, `Caveats`, `Freshness`, `Clock`, `DueDate`, `BasisPill`, `StageSteps`, `Findings`, `Evidence`, `Timeline`, `QuestionCard`, `DecisionBrief`, `HeldNote`, `ChangedSince`, `RunRow`, `WorkflowRail`, `ClockStrip`, `NoticeClock`, `Discrepancy`, `WatchRow`, `StandingPill`, `Stat`, `EmptyState`, `RemoteView`, `ControlStateWord` (the model for a state word). Not built, draw them from the built parts: `PartOfRunBanner`, `DeadlineCell` (specified in the life-safety brief: a `DueDate` with its basis).

| Component | What it is | Data (handoff payload names) | States |
|---|---|---|---|
| `ProgramRegister`, `ProgramRow` | C1; one row | `groups[].rows[]`: `key, title, source, shape, standing, evidence, lifecycle, next, question` | required; not required (the deciding fact); question; default applies; optional; presupposed; no catalog |
| `StandingWord` | A `Pill` preset for `ProgramStanding` | `standing` | missing, drafted, adopted, implemented, reviewed, current, stale, default applies, optional, presupposed; a meaning on focus |
| `EvidenceTrio` | document, adoption, records, each its own word | `evidence{document, adoption, implementation}` | the states of the handoff's table; never one blended word |
| `LifecycleStrip` | six stages, six words, as a list | `lifecycle` | a stage with no evidence is a word and its question; "not required" with why |
| `ElementRecital` | one element, recited, with its cadence | `requirement.elements[]` | fixed, silent, event, continuous (`CadenceWord`); read by jason, unconfirmed |
| `AdoptionEvidenceRow` and `VerbClass` | one act and the class of its verb | `adoption[]`: `kind, verbClass, on, documentDate, quote, counts` | adopted, delegated, directed, listed, reviewed, quoted ("not an act"), declined; a vendor proposal apart |
| `ProgramDocumentCard` | the document found | `document` | not on file (the search), on file, embedded, several candidates (jason picks none), not read |
| `NextDueCell` | last done and next due, each with a basis | `log[]`, `obligations[]`, `next` | dated; "computed"; "date not on record"; no clock (silent, event, continuous); upcoming, due soon, overdue, using the schedule's words |
| `VendorCard` | the vendor, its licence check, and "Ask the vendor" | the profile's vendor rows, `pest_program.license`, `jason licenses` | checked on a date; not checked; no vendor; the ask is a draft, never a send |
| `ProgramRunStrip` | the open run of the current period | a `work` row for the program's subject | none open; open; waiting (named); past a date; a child run |
| `ProposalFlow`, `DraftPreview`, `AdoptionBrief` | the path to the board | `proposal` | as the handoff: stages, `[BOARD CHOICE]` count, options without a recommendation |
| `ElementReviewTable`, `DerivedObligations`, `OwnerDutyRow`, `MemberRoleList`, `ReferenceRow`, `DetectionLead` | as the handoff | as the handoff | as the handoff |

**Fixed words** (use exactly): "no act on record", "not on file", "quotes the section: not an act", "not an adoption: implementation evidence", "jason's reading", "jason's reading, unconfirmed", "proposed, not adopted", "computed", "date not on record", "jason picks neither", "the document sets none: the board's", "held: privileged, not shown", "jason tracks the notice, not the owners' compliance". Never "compliant", "in force", "violation", "late by law", "adopted" for a file, or "not adopted" for no act.

## E. Glyphs

Use the console's: `circle-check` (an act on record, confirmed), `circle-question-mark` (a question, undetermined, not yet recorded), `clock` (a date, a clock), `triangle-alert` (overdue), `minus` (none, no clock), `lock` (held), `bug` (pest), `droplets` (backflow), `wrench` (maintenance), and the paperclip for a linked record. Propose new ones only for what none says, named for the idea: a **quoted-not-an-act** mark (a section repeated, with no motion), a **several-candidates** mark (two marks, not a warning triangle), and a **computed** mark beside a derived date. Each sits beside its word.

## F. Decisions that are the design's, in one list

1. **Three evidences in a row.** Three small labeled values, or the overall word with one sentence ("drafted: document on file; no act on record; none shown"). A column of "no act on record" must not read as failure.
2. **Where the requirement sits in a row.** The whole words in the row, or the cite with `Read whole` (recommended), the whole always one click away and never cut with an ellipsis.
3. **Last done and next due.** Two columns or one cell; and whether "computed: 3 months after adoption" is shown, or only "date not on record" until a person enters a day (the elevated-elements precedent).
4. **Group by source or by urgency.** Source (recommended: it follows the authority order and keeps a condition of approval apart) with a "needs a person" filter.
5. **Strip or sentence** for the six stages; keep the words and never a progress bar.
6. **One page template, or a template per kind.** A declaration program, a statute row, a vendor program, and a per-building cycle share one page with bands that appear only when they have content (recommended); the pest and elevated-elements pages are the stress test.
7. **The cycle's place.** A run strip on the page and a Next due link into Work (recommended), or the register shows Work's data in place.
8. **How adoption is run.** `control-adoption` is a built run. Decide whether a program's adoption is its own definition, the same run with a different subject, or only the page's `ProposalFlow` over a board item.
9. **Programs and Controls.** A control is a safeguard the board may opt into; a program is a requirement the documents set. Decide how one screen leads to the other without a second list of the same rows ([handoff-programs.md](handoff-programs.md) decision 1).
10. **Vendor contact.** Whether the card shows any contact detail (P1), or only the name, the licence, and "Ask the vendor" as a draft.
11. **The owner's half and the sub-programs**: a section on the page, or its own page; and how a sub-program (the pest, backflow, and elevated programs under a maintenance parent) is "counted once" in the parent.
12. **Print:** a one-page register for the board's packet with each adoption word and its verb class, each date and its basis.

These are not the design's: whether a minute entry is an adequate adoption or the board should adopt by resolution (counsel's), the verb classes, the cadence words, whether a program on a listed subject needs notice to members, who confirms a detected mandate, and whether a condition of approval binds the association.

## G. What can be designed now, and what waits

| Part | Now | Waits on |
|---|---|---|
| Register, program page, evidence trio, lifecycle strip, element recital, adoption rows with verb classes | Yes, from the handoff payloads and section H | `programs`, `program`, `program-gaps` loaders and the catalog, detection, and resolver (nothing built) |
| Pest page Records band | Yes, from the `pest_program` brief | A web loader over `pest_brief`; the adoption and requirement bands wait on the catalog |
| Backflow card, elevated-elements rows, system links | Yes; `backflow`, `watchlist`, `life-safety` are built | Views for them (none); `jason elevated` does not exist, so a per-building loader over `elevated_inspections.as_dict` |
| Run strip and the cycle in Work | Yes, with the built `RunRow`, `WorkflowRail`, and `BasisPill` | `maintenance-program`, `backflow-annual`, `elevated-elements` definitions (design only); `PartOfRunBanner` and the link grammar in `run-links.md` |
| Adoption read from the minutes with a verb class | Draw it | `adopts` on the minutes reader, the verb grammar, and indexing minutes before 2098 (names the gap in the page) |
| Generate the draft, `DraftPreview`, put on the agenda | Draw it | The base templates under `templates/programs/` (none exist), `jason programs --draft` and `--propose`; the board's item exists |
| "Record done" for a program's step | Yes | Nothing: `#/duties` and `jason schedule-evidence` are built; the derived obligation is a person's addition to the profile |
| Detected and References tabs | Draw them | `program_detect`, the named-reference extractor, a measured gold set |

## H. A made-up community to design against

"Oakview Condominium Association" (no real association). Today is **Oct 12, 2099**. Seven rows, each with a point to make:

| Program | Source, shape | Standing | Adoption (from the minutes) | Last done (basis) | Next due (basis) | Vendor | The point |
|---|---|---|---|---|---|---|---|
| Moisture inspection and prevention | declaration 9.9(a), adopt and implement | drafted | no act on record: 19 sets, 2 not read; one entry only quotes the section | no record shows it | none: step 2 silent, step 3 event | none | The main page; three cadences; two dates for one act |
| Pest program | declaration 9.4, optional | optional | no act on record; a vendor proposal approved 2099-02-17, apart | 2099-09-24, visit (`counterparty`) | 2099-10-22 (`counterparty`) | Example Pest Co, licence checked 2099-03-04 | A program run by contract; "not an adoption"; products, stations, label checks |
| Maintenance manual | declaration 8.2, adopt | missing | no act on record | none | none: revision cadence silent | none | Three candidate documents (a developer's care guide, a draft chart, an equipment manual): "jason picks none" |
| Backflow program | statute, comply with the local program | current | stated by the statute; no board act needed | 2098-11-12, test report (`documents`) | 2099-12-01 (`counterparty`: the supplier's notice, each start date side by side) | Example Backflow Testing | A supplier's clock; a discrepancy between sources |
| Elevated elements | statute, conditional (CIV 9903, made up), every nine years | implemented | the board's engagement 2094-03-02 | 2094-06-14, report named (`documents`) | 2103-06-14 for Bldg. 1 (`law`, computed); Bldg. 2: date not on record | Example Engineering | A per-building cycle; an unknown date is a question |
| Penalty schedule | statute, conditional (CIV 9902, made up) | question | n/a | n/a | n/a | n/a | "Does the association impose penalties?" is a question, never missing |
| Monthly exterior walk | condition of approval, Example City permit PUD-0001, D1 | presupposed | no act on record | none | none | none | Own group; "whether it binds the association is not settled"; counsel first |

Pages to draw: the moisture page (main, C2) with its elements, two acts (a board item's result 2099-08-30 and a quoted entry), a worksheet with a "saved on" entry, and the draft with 4 `[BOARD CHOICE]` fields; the same page after the secretary records the board's adoption (the word moves from drafted to adopted, the minutes' act is added beside the first, not instead of it); the pest page (C3) with Example Pest Co's visits, five products by made-up EPA number, a rodent station reading, and a label-check question; the elevated-elements page with Bldg. 1 dated and Bldg. 2 not on record; the maintenance manual with three candidates and the `Confirm` to bind one; the Work strip for the pest cycle ("Step 3 of 11: Read the portal's visits", waiting on the manager, next clock 2099-10-22 `counterparty`) and the same program on `#/work`; the register as the board's director sees it (identical to the officer's), as the manager sees it, and with no catalog ("The program catalog is not built, so no program is read").
