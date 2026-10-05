# Programs, manuals, schedules, and plans an association must adopt and carry out

**Status:** proposed design, October 5, 2026. Nothing here is built except what "What exists" names. The statutes quoted were read from the shelf that day (`jason cite`); the quotations are the Legislature's words, and every reading is labeled. This page is general: the facts of one association (its declaration's section numbers, its documents, its files) are the profile's, and the examples here are made up.

A California common interest development is obliged by the law, and by its own declaration, to **adopt** certain things and then **carry them out**: an inspection program, a maintenance manual, a fine schedule, a dispute procedure, a funding plan, election rules. Today jason knows many of the *deadlines* that follow (`obligations.py`, [schedule.md](schedule.md), [calendar.md](calendar.md)) and many of the *notices* ([notices.md](notices.md)). It does not know the **instrument itself**: that the association is obliged to have it, what it must contain, whether the association has one, whether the board adopted it, whether it is carried out, and whether a newer statute has made it stale. This page designs that, as a catalog the same shape as the notice catalog, applied to one association as a gap report.

The neighbours, linked and not repeated:
- [policy-catalog-design.md](policy-catalog-design.md): the policies jason *configures* (response standards, retention, notice delivery) and the board's adoption record for each. The catalog here is the **required** side of the same idea ("where the law is silent, write it down"); the two meet at `Instrument`, `Adoption`, and `AdoptedPolicy` (decision 1).
- [document-duties.md](document-duties.md): the duties read from the governing documents' words. A program mandate is one *shape* of a `DocumentDuty`.
- [notices.md](notices.md) and [applicability.md](applicability.md): `NoticeRequirement` and the three-valued `applies` condition. The program catalog copies both.
- [ingestion-and-review.md](ingestion-and-review.md), [collections.md](collections.md), [manager-review.md](manager-review.md): ingestion, lenses, collections, the context pack.
- [base-templates.md](base-templates.md): the base templates a profile renders.
- [pest-management.md](pest-management.md), [fire-protection.md](fire-protection.md), and the backflow and life-safety pages (named in "Instances"): programs that already exist as one-off code.
- The console design: [console/handoff-programs.md](console/handoff-programs.md).

## The idea in one line

A provision obliges the association to adopt a program; jason recites the requirement element by element, finds the document, the board's act that adopted it, and the records that it is carried out, reviews the document against the requirement, derives the duties and dates that follow, and where none exists drafts one from a base template for the board to adopt. Jason never adopts anything.

## Vocabulary

Every word is a state in code (to be `ProgramStanding` and its parts) so the console and the terminal agree. None is shown by color alone.

| Word | Means | Never means |
|---|---|---|
| **required** | a provision obliges the association to adopt or keep it, and its condition holds for the facts on hand (`applies`) | that it is missing |
| **not required** / **question** | the condition does not hold (with the deciding fact), or a fact is missing (with the question) | "nothing to do": a question is never "not required" |
| **adopted** | an act of the board (or the members) on record adopted *that document*: a resolution, a minutes motion, or the instrument's own certificate | that the document is good, or that it is in force against owners |
| **implemented** | records show the steps done on the schedule the requirement or the document states | that the program is adequate |
| **reviewed** | a review under the programs lens, as of a date, compared the document with each element of the requirement, and a person confirmed the verdicts | that jason decided anything |
| **current** | adopted, reviewed against the law in force today with no open lead, inside its own review cycle, and implementation not overdue | a legal conclusion |
| **stale** | a newer statute, an amendment of the mandating provision, or a changed document, since the last review | that the document is void |
| **default applies** | the statute supplies a procedure when the association adopts none; jason applies it and says so | a gap the board must close |
| **optional** | the provision attaches duties *if* the association adopts one ("if the Association adopts a program ..."); it does not oblige adopting | required |
| **presupposed** | a provision speaks as if the instrument exists ("pursuant to the Association's program") without saying it must; whether it must is a question | adopted |

A program also has a **lifecycle** of six stages (mandate, written program, adopting act, implementation records, owner communication, review), each with its own evidence and its own word; see "Finding what exists". A program can be written and adopted and never carried out, or carried out with no act on record.

A miss stays a miss (AGENTS.md). **"Not on file" is never "not done"**, and **"no act on record" is never "not adopted"**: each is a state with the search that was made and the question that settles it.

## What exists

| Piece | Where | What it gives this design |
|---|---|---|
| The notice catalog | `src/jason/community/notice_catalog.py`, `notices.py`, `notice_conditions.py` | the row shape to copy: key, source, `words` checked against the shelf, `applies`, `carried_by`, `also`, `caveat`, `verified` |
| Applicability | `src/jason/community/applicability.py` (`Facet`, `Fact`, `Facts`, `evaluate`, `partition`), `applicability_asks.py` | the three answers, the facts, the questions a person answers |
| Duties read from documents | `deontic.py` (`DocumentDuty`, `Bearer`, `Deadline`, `read_outline`), `tasks/document_duties.py`, `data/duties/<key>.json` | the sentences, their markers, bearers, recurrences, and list items that inherit a lead-in |
| References | `references.py` (`Reference`, `TargetKind`, `RefRelation`, `extract`, `statute_citation`), `reference_model.py` | the citation grammar, the relation verbs, the section a mention sits in |
| Document kinds | `symbols.DocumentKind`, `documents.classify_document` (`KindRule`), `content.classify_text` (`ContentRule`, `RecordRule`), `ModelClassifier` | name rules, phrase rules, a local model that never overrides them |
| Readers | `models/` (`document_models.DocumentModel`, `Finding`, `Basis`); `models/meetings.py` (minutes `Action`, `_MOTION`), `models/meetings_resolutions.py` (`ResolutionSubject`); `readings.AdoptionReader` | motions and resolutions; "adopted on" and an unsigned `DATED: ___` line |
| Recurring deadlines | `obligations.py` (`Obligation`, `Standing`), `schedule.py`, `schedule_evidence.py`, `jason deadlines` | the clock for a timed element, and the evidence that it was done |
| Standing precedents | `life_safety.py`, `elevated_inspections.py`, `jason inspections` (a Completeness lens), `pest_visits.py`, `jason pests`; and the backflow program records and watchlist, named in "Instances" | three programs already tracked as code |
| Lenses, collections, packs | `reviews.py` (`Lens`, `LensCheck`, `AS_OF`, `RECORDS`), `document_collections.py` (`Collection`), `context_pack.py` (tiers S, G, R, C, F, D), `collection_pages.py` | the review machinery |
| Conflicts and leads | `Community.conflicts()`, `jason conflicts --leads`, `jason law-history`, `law_readings.recite` | the third group of the gap report, and "the law in force on the day" |
| Adoption | `rule_changes.py` (`jason rule-change`), `record_stages.py`, `manual.AdoptionEvent`, `jason board` | the 4360 notice, the stages of a decision, the board's items |
| Base templates | `src/jason/templates/` (notices, packets, manual), `template_values.py`, `jason templates --lint` | the generation path |

## The catalog: one row per thing that must be adopted or kept

`jason.community.program_catalog.REQUIREMENTS` (proposed), the notice catalog's shape. A row is a `ProgramRequirement` whose `source` is one of four, in the order of authority (`authority_order.Tier`): the last is the lowest.

| Source | Whose | Found by | Applies |
|---|---|---|---|
| **STATUTE** | every association | `jason cite` on a section of the shelf; the row's `words` are checked against the exported text by a test, as `tests/test_notice_catalog.py` does | always (`ALWAYS`) |
| **STATUTE-CONDITIONAL** | an association for which a fact holds | the same | an `applies` condition over the facets of `applicability.py`, answered in three ways; a missing fact is a question |
| **DECLARATION** | one association, by its governing documents | the detection rule below, read from `data/duties/*.json`, confirmed by a person | the document's own scope (its conditions), as a reading |
| **CONDITION OF APPROVAL** | one development, by a public agency's approval of it (a city's conditions on a planned-development permit, a subdivision's map conditions, a recorded covenant to a public agency) | a **conditions reader** (below) over the approval document in the library, confirmed by a person | the approval's own scope (which parcels, buildings, or phases it names), as a reading |

A **condition of approval** is a source below the statute and the governing documents, and it is a different kind of mandate: the governing documents may not repeat it, and whether it **binds the association** (as against the developer who applied), and which buildings it reaches, is a question for the agency or counsel, never settled by jason. The row says so in its `caveat`, shows the agency's own words, and is a `COUNSEL_FIRST` row until a person records the answer. It supplies **floors** that a program must respect (a monthly exterior inspection, a repaint interval, a maintenance program "subject to review and approval" by an officer of the agency): the review checks the program against them and, where the condition names an approver, asks whether the approval is on file. A condition that conflicts with the declaration or the law is a `Conflict` candidate, not a pick.

A row is **not** written from memory. "A row with no recited words stays a question": a candidate whose operative words cannot be quoted from the shelf or a document is not a row; it is an open question with the search made.

### `ProgramRequirement`

| Field | Meaning |
|---|---|
| `key` | stable, kebab-case ("fine-schedule"); the collection is `program-<key>`, the ledger and review keys start with it |
| `title` | in words ("Schedule of monetary penalties") |
| `source` | `STATUTE`, `STATUTE_CONDITIONAL`, `DECLARATION`, or `CONDITION_OF_APPROVAL` |
| `bearers` | who the program binds: the association, each owner, or both (an owner's twin is its own element set; below) |
| `register` | whether the program rests on a **component register** (a maintenance-type program does; below) |
| `parent` | the key of the program this is a sub-program of, when it is one (below, "Overlap") |
| `authority` | citations, as the notice catalog writes them (`CIV 5850`); for a declaration row, the document key and section (`decl#9.9`) with the permanent id |
| `words` | the operative sentence, verbatim, from the shelf or the document, with its version in force |
| `shape` | `ADOPT`, `ADOPT_AND_IMPLEMENT`, `OPTIONAL`, `PRESUPPOSED` (below) |
| `instrument` | how it is adopted: the policy catalog's `Instrument` (`OPERATING_RULE`, `BOARD_POLICY`, `STATUTE_DEFAULT`, `DOCUMENTS`, `COUNSEL_FIRST`) |
| `applies` | a `Condition` for a conditional row |
| `elements` | the `RequirementElement`s, below |
| `fallback` | what the law does with none: `STATUTE_DEFAULT` (the statute's procedure applies), `NONE`, or `HOLD` for the board |
| `names` | the generic phrases documents call it ("dispute resolution procedure", "meet and confer"), used by the reference resolver; vocabulary of the law, never one association's file names |
| `kinds` | the `DocumentKind`s a document of this sort has |
| `template` | the base template's key, or "" when none exists yet |
| `carried_by` | the notice row that distributes it (`annual-policy-statement`), when one does |
| `also`, `note`, `caveat`, `verified` | as in the notice catalog; `verified=False` when the section is not on the shelf |

### `RequirementElement`

An element is one thing the requirement says a conforming instrument contains or does. It is the unit of recital and of review.

| Field | Meaning |
|---|---|
| `key`, `cite` | the element's id and its subdivision ("5105(a)(7)", "decl#9.9(a)(i)") |
| `kind` | `CONTENT` (it must state or provide for X), `STEP` (an act to do), `FREQUENCY` (how often), `PARTY` (who does or receives), `RECORD` (what is kept, and how long), `NOTICE` (what is told, to whom), `OWNER_DUTY` (a duty on owners), `ADOPTION` (how it is adopted), `LIMIT` (a bound the instrument may not cross), `CONDITION` |
| `words` | the element's words, verbatim, checked against the source |
| `bearer` | `deontic.Bearer`: association, board, officer, manager, owner, and so on |
| `cadence` | which of four kinds the words set (below): `FIXED`, `SILENT`, `EVENT`, `CONTINUOUS` |
| `every_months` | a recurrence read from the words (3 for "quarterly"); 0 when the words state none, and **"periodic" is not a number** |
| `deadline` | `deontic.Deadline` when the words give one |
| `record` | the kind of record that shows it done (a `DocumentKind`, or an `AssociationRecord`) |
| `anchors` | the phrases that point at it in a document under review: leads, never proof |
| `applies` | a condition when the element holds only sometimes |

For a statute row the elements are written by hand from the section, each with its `words`. For a declaration row they are **read**: the enumerated steps under the lead-in are already `DocumentDuty` readings with `inherited` set and a `recurrence_months` where the words give one, so the elements start as those readings and a person confirms them.

### The shape of a mandate (`Shape`)

| Shape | The words | Example (made up) |
|---|---|---|
| `ADOPT` | a duty whose head verb is adopt, establish, institute, develop, or put in place, and whose object is a program-type noun | "The Association shall adopt a handbook for the care of the roof." |
| `ADOPT_AND_IMPLEMENT` | the same with "and implement", usually with enumerated steps | "... shall adopt and implement a moisture inspection program which shall include the following steps:" |
| `OPTIONAL` | a permission or condition: "if the Association adopts X, then ..." | duties attach if adopted; adopting is the board's choice |
| `PRESUPPOSED` | a duty that acts "pursuant to the Association's X program", "under a schedule adopted by the Board", "standards ..., if any exist" | the instrument is assumed; whether it must exist is a question |

An `ADOPT` row is a gap when nothing is on file. An `OPTIONAL` row is never a gap. A `PRESUPPOSED` row is a **question for the board**, and where the law is silent it is a proposal ("Where the law is silent, write it down").

### The four cadences (`Cadence`)

The real cases showed that "how often" is not one thing. Each element says which kind its words set, and the catalog row says **which the document fixes and which the board must set**.

| Cadence | The words | The element holds | Who sets the number |
|---|---|---|---|
| `FIXED` | "not less frequently than quarterly", "semiannually", "at least once every nine years" | `every_months` | the document or statute; a floor, which the board may exceed |
| `SILENT` | "periodically", "from time to time", "as appropriate" | no number, and a question | **the board**; a policy proposal fills it, marked "proposed, not adopted"; until adopted the element has no clock |
| `EVENT` | "immediately", "promptly", "as soon as reasonably practicable", "within 15 days of the postmark" | a response clock, not a recurrence; with a number it is a `Deadline`, without one it is a question | the document if it gives a number; else the board ("immediately" is a reading for counsel; the board may propose what it means: stop the source, begin repair, record the date) |
| `CONTINUOUS` | "at all times", "shall maintain", "in a clean and proper operating condition" | a standing state, not a date | no number; shown by records of the state (a condition noted at each walk), never as an overdue date |

An `EVENT` element is an **assignment of a response**, not an `Obligation` row (an `Obligation` counts from a record's date or an interval); a `CONTINUOUS` one is verified by the fixed-cadence inspections that look at it. A silent cadence is **never** filled with a default ("periodic" does not become annual): the proposal shows a value with its source ("the studies say every 5 years", "the builder's guide says twice a year in one place and once in another") and the board chooses. Where the sources for one interval disagree, the element is an **alignment finding** (below).

### Two bearers, and the association's part toward owners

A requirement may bind the association and, in the same words, each owner ("each Owner shall adopt and implement ..."). The two are separate element sets with their own bearer and cadence. The association's own program is `bearers: association`; each owner's is an `OwnerDuty` set. The association's **part toward owners** is one of three, and the row names which the document or the board has chosen:

| Part | Means | Evidence |
|---|---|---|
| **notify** | tell owners their duty exists (the annual policy statement, a letter, the owners' manual) | the notice's proof; none on file is a finding about the association, not the owners |
| **remind** | a recurring reminder (each season) | the reminder's record |
| **enforce** | notice, hearing, and a charge under the documents' own process (never jason's act) | the enforcement record; the documents' process, not a program step |

A document that is silent on the association's part leaves it a question for the board. A board decision *not* to require owners to certify is a recorded decision, not a gap, and shows as one.

## The candidates, checked on the shelf

Each candidate the task named was read with `jason cite` (October 5, 2026). The result is a decision, not an assumption.

| Candidate | Result | What the words say (quoted from the shelf) |
|---|---|---|
| Election rules, **CIV 5105** | **Confirmed**, `STATUTE`, `ADOPT`, an operating rule | 5105(a): "An association shall adopt operating rules in accordance with the procedures prescribed by Article 5 (commencing with Section 4340) of Chapter 3, that do all of the following:" followed by seven elements, (a)(1) to (a)(7), and the disqualifications of (b) and (c) |
| Internal dispute resolution, **CIV 5905, 5910, 5915** | **Confirmed**, `STATUTE`, `ADOPT` with a `STATUTE_DEFAULT` | 5905(a): "An association shall provide a fair, reasonable, and expeditious procedure for resolving a dispute within the scope of this article." 5905(c): "If an association does not provide a fair, reasonable, and expeditious procedure ..., the procedure provided in Section 5915 applies and satisfies the requirement of subdivision (a)." 5910 lists the minimum elements ((a) to (g)); 5920 puts a description in the annual policy statement |
| Fine schedule, **CIV 5850** | **Confirmed**, `STATUTE_CONDITIONAL`, `ADOPT` | 5850(a): "If an association adopts or has adopted a policy imposing any monetary penalty ..., the board shall adopt and distribute to each member, in the annual policy statement ..., a schedule of the monetary penalties that may be assessed for those violations". Condition: the association imposes monetary penalties. Amended by Stats. 2025, Ch. 22, Sec. 3, operative 2025-06-30: a lead for any schedule adopted before |
| Architectural review procedure, **CIV 4765** | **Confirmed**, `STATUTE_CONDITIONAL`, `ADOPT` | 4765(a): "This section applies if the governing documents require association approval before a member may make a physical change"; (a)(1): "The association shall provide a fair, reasonable, and expeditious procedure for making its decision. The procedure shall be included in the association's governing documents." CIV 4150 defines governing documents to include operating rules (a reading for counsel: whether an operating rule satisfies "included in the association's governing documents") |
| Reserve funding plan, **CIV 5550, 5560** | **Confirmed**, `STATUTE_CONDITIONAL`, `ADOPT` | 5550(b)(5): the study includes "A reserve funding plan"; 5560(b): "The plan shall be adopted by the board at an open meeting before the membership of the association"; 5560(a): it "shall include a schedule of the date and amount of any change in regular or special assessments". 5550(a) conditions the study on the replacement value of the major components being "equal to or greater than one-half of the gross budget" |
| Electric vehicle charging terms, **CIV 4745(h), 4745.1(g)** | **Added**, `STATUTE_CONDITIONAL`, `ADOPT` | "... the association shall develop appropriate terms of use for the charging station." Condition: the association installs a station in the common area for all members |
| Annual policy statement, **CIV 5310** and its neighbours | **Reshaped**: not a program row. A *distribution* duty, already `notice_catalog` row `annual-policy-statement`; its items 5310(a)(6) to (10) are `PRESUPPOSED` instruments | 5310(a): "the board shall distribute an annual policy statement that provides the members with information about association policies"; (a)(7): "A statement describing the association's policies and practices in enforcing lien rights or other legal remedies"; (a)(8): "the association's discipline policy, if any"; (a)(9): "A summary of dispute resolution procedures"; (a)(10): "A summary of any requirements for association approval of a physical change" |
| Collection policy, **CIV 5310(a)(6), (7), 5730** | **Reshaped**: `PRESUPPOSED`, a question. The statute requires a *statement* of the collection policies and the 5730 notice verbatim; its words do not say the association must adopt a written collection policy | see above; 5730(a): the policy statement "shall include the following notice, in at least 12-point type" |
| Payment plan standards, **CIV 5665** | **Reshaped**: `OPTIONAL` | "The association shall provide the owners the standards for payment plans, if any exists." |
| Operating-rule subjects, **CIV 4355(a)** | **Dropped as a mandate; kept as a classifier** | 4355(a) says which rules need 4360 notice ("Sections 4360 and 4365 only apply to an operating rule that relates to one or more of the following subjects"), not that a rule must be adopted. It decides the *adoption path* of an `OPERATING_RULE` row, as a labeled reading; 4355(b)(1) excludes "A decision regarding maintenance of the common area" |
| Operating-rule validity, **CIV 4350** | **Dropped as a row; kept as the checks of the adoption act** | "An operating rule is valid and enforceable only if" it is in writing, within the board's authority, not in conflict with law or documents, adopted in good faith in substantial compliance, and reasonable |
| Records retention (5200 to 5240) | **Dropped**: no adoption words on the shelf | the shelf scan found none; retention is a policy the association may choose (the policy catalog's `records-retention`) |

**Detection on the shelf as a measure of the rule.** The detection rule below, run on the 52 Civil Code pages of the shelf, finds 17 sentences with an adoption verb or a "provide a procedure" shape, and one more by the passive shape. By hand: 7 are the rows above (5105(a), 5560(b), 5850(a), 4745(h), 4745.1(g), 4765(a)(1), 5905(a)); 5 are related disclosure or notice duties (5310(a), 5850(f), 5665, 5115(a), 5300(b)); 6 are false (a sales-tax schedule of the Board of Equalization, a presumption of mailing, a model for ballot confidentiality, a confidentiality duty, an education course, an enforcement-cost clause). Other codes of the shelf were not scanned.

A **row is added only with its words**: the table above is the first `REQUIREMENTS`. Rows are added one at a time with the section's words, a test against the shelf, and a base template or a stated gap.

## Applicability: the facets and the new facts

A conditional row's `applies` is built from `applicability.py`, never from a function. The facts the first rows need:

| Fact | Facet | Closed set | Said by |
|---|---|---|---|
| `monetary_penalties` | Subject | imposes, does not | the profile, or a person's answer with the record (the adopted discipline policy) |
| `approval_required` | Document | the governing documents require approval of physical changes, or do not | read from the documents (the duties' `committee` and `approval` readings), then a person's answer |
| `reserve_study_required` | Property | replacement value of the major components is at least half the gross budget, or below | a person's answer with the record that states it, entered like `elevated_elements`: a property fact with a record; jason does not compute it from a study it has not read |
| `ev_charging_in_common_area` | Event | installed, planned, not | the person describing the event |
| `common_interest`, `unit_count`, `state` | Property, Place | as today | the profile |

A fact the profile does not state and no one has answered is **undetermined** with its question in the queue (`applicability_asks`), exactly as `jason applies --questions` does. The row is then a *question*, not a gap.

## The records

The model extends, and does not duplicate, duties, obligations, and applicability.

| Record | Holds | Built on | Stored |
|---|---|---|---|
| `ProgramRequirement` | the catalog row | the notice catalog's shape | code (statute rows), the profile (`Community.program_requirements()`, declaration rows a person confirmed), empty by default |
| `RequirementElement` | one recited element, its bearer, recurrence, record, anchors | `DocumentDuty` fields | with its row |
| `AdoptionReading` | one `DocumentDuty` read as a mandate: shape, verb, object noun, program name as written, the steps (the duty ids it carries), the bearer | `DocumentDuty.id` | `data/programs/readings/<outline>.json`, ingestion (text only) |
| `NamedReference` | a mention of a named instrument: who mentions it, where, its name as written, its noun, whether it is conditional ("if any") or expected ("as the Board may adopt") | `references.Reference` with a new `TargetKind` | beside the reference store |
| `ProgramDocument` | a found document of this program: its digest and ids, its kind, its dates, where it was found (a file, a Drive id, or a section embedded in another document), and its `ProgramStanding` | `document_models` readings, the library | `data/programs/found.json` |
| `AdoptionEvidence` | one act: kind (`RESOLUTION`, `MINUTES_MOTION`, `CERTIFICATE`, `SELF_STATED`, `BOARD_ITEM`), its **verb class** (adopted, delegated, directed, listed, reviewed, quoted, declined), its date (and the document's own date, kept apart), the document and passage, the motion's words, the vote, who read it (grammar, model, person) | `models/meetings*.py`, `readings.AdoptionReader`, `record_stages` | with `ProgramDocument` |
| `ComponentRegister`, `ComponentRow` | for a maintenance-type program: one row per component (below) | the reserve study, the board's component list, the cost centers | with the program; read from the sources, a person confirms |
| `AlignmentFinding` | one interval or life that appears in more than one source with different values | `ComponentRow` over its sources | computed; a finding, never a pick |
| `Program` (a profile row) | the association's own program: its key, requirement keys, named members by role, its sub-programs | `ProgramRequirement` | `Community.programs()`, empty by default |
| `LogEntry` | one dated entry of an inspection log: date, inspector, areas, condition, photos, the rows it satisfies | `DocumentKind.PROGRAM_RECORD` readings | ingestion; `data/programs/readings/` |
| `ProgramReview` | the review of one document under the programs lens: an `ElementResult` per element (found at a passage, not found, unknown, for a person), the three-part decision, each finding's `Basis` | `reviews.Review`, `Finding.basis` | `data/reviews/programs/<key>/<digest>/<as-of>.json` |
| `Implementation` | per timed element, the occurrences expected in a window against the evidence | `Obligation`, `Standing`, `schedule_evidence` | computed, never stored as fixed |
| `ProposedObligation` | an `Obligation` row a timed element implies: name, authority, `every_months`, `first_due`, `applies`, evidence kinds | `obligations.Obligation` | printed and proposed; a person adds it to the profile |
| `OwnerDuty` | an element whose bearer is the owner, with the notice that tells owners and the record that shows it | `deontic.Bearer.OWNER`, `NoticeRequirement` | with its row |

**An owner's duty is part of the program.** A requirement may bind the association *and* each owner (the same steps, in each unit). The owner's half is an `OwnerDuty` element: jason lists it, names the notice that tells owners (the annual policy statement, a letter), and tracks only what the association is to do (tell them); it enforces nothing and never inspects a unit. Whether a program that reaches into a unit is an operating rule on "use of a separate interest" (CIV 4355(a)(2)) is a labeled reading, and a question for counsel.

## The component register at the core of a maintenance-type program

A manual or schedule for the upkeep of the common area is, at its core, a **register of components**: what is maintained, by whom, how often, to what life. The requirement's words ("a manual for the periodic inspection and maintenance of the Common Area") are satisfied or not by this register, so it is the program's heart and the unit of review. A `ComponentRow`:

| Field | Meaning |
|---|---|
| `component`, `quantity`, `location` | what it is, how much, and in which building or area |
| `cost_center` | the association's cost center that bears it, where the instruments set cost centers |
| `reserve` | the reserve study's component for it and its **useful life**, with the study and its date |
| `responsible` | who maintains it: the association, the owner, a public entity, a vendor (as the documents state it) |
| `interval` | the inspection interval and the maintenance interval, each with its **cadence kind** and its source |
| `assumption` | the maintenance the study's life **assumes** (the narrative that says "seal coat every 5 years"), when the study states one |
| `record` | the kind of record that shows it done (a log entry, a report, an invoice) |
| `vendor` | the contract or vendor that does it |
| `parent` | the program it belongs to if it is a sub-program's (below) |

Rows are read from the sources (the declaration's list of components, the reserve study's lines, the board's own working list, the vendor contracts), each cell carrying its source, and confirmed by a person; jason invents no component and no interval.

### Alignment is a first-class check

The same interval appeared in the real case in **four conflicting forms**: a public condition's, the reserve study's, the board's working sheet, and the owners' manual. The programs lens has an `alignment` check over the register:

- For each component, collect every stated interval or life, each with its source and date.
- Where they **differ**, the finding lists all of them side by side, labeled by source, with the authority order beside ("the condition of approval's limit is a floor; the study's life exceeds it, with no approval on file"). **jason picks none**, as the conflicts-of-fact lens picks none; the board, the agency, counsel, or the analyst resolves.
- Where a source **omits** a component another names (the study omits what the declaration lists and the board's sheet carries), the finding says so ("not in the study's list").
- Where a study states no **maintenance assumption** for a component's life, it is a question for the analyst. The reserve-study component narratives are not read today (below), so this check waits on that reader.
- `Finding.basis` is `TEXT` (each source's words), `STORE`, and `LAW` or the public condition where one is a limit.

## Overlap: one obligation per authority

A maintenance-type program touches many others (mold, pest, fire, backflow, elevated elements, the reserve study's visual inspection). The register must **not count one thing twice**:

1. **One obligation per authority.** A statute's or a document's duty is one `Obligation` row; a second program that cites the same authority points at that row, and never copies it.
2. **A task and its verifying inspection are not two rows.** "Clean the gutters twice a year" and "inspect that the gutters are clean" are one element with a task and a check; the invoice is the evidence of the task, the log entry of the check.
3. **One visit can satisfy several rows, and the log says which.** A monthly walk that also serves a quarterly check records, on the entry, the rows it satisfies (`LogEntry.satisfies`); each row counts it once.
4. **Sub-programs are rows the parent points at.** A sub-program (the pest program, the backflow test, the fire inspections, the elevated-elements inspection, a mold program) keeps its own `ProgramRequirement` and its own records; the parent lists it as a member with `parent` set and shows its standing, never restating its steps or its rows. The manual's component table cross-references, it does not duplicate.
5. A finding that shows up twice (a leak found on a walk is a mold finding and a roof finding) is **one finding with two references**, not two.

## Detection: which duties are "adopt or implement"

Input: the readings of `data/duties/*.json` (`DocumentDuty`), and the outlines' text for what the duty grammar does not read.

### The rule for an `ADOPT` shape

A `DocumentDuty` is an adoption mandate when **all** hold:

1. `kind` is `duty` (or a `condition` stated "shall be adopted by");
2. its bearer is the association, board, committee, officer, manager, or `unstated` (a passive: "shall be adopted by the Board"); an `owner` bearer is the same shape read as an **owner's** program (an `OwnerDuty`), never the association's;
3. the **head verb** of the `action` (its first verb, or the first of a coordinated pair) is adopt, implement, establish, institute, develop, formulate, promulgate, put in place; "maintain" or "prepare" counts only when the object is a program-type noun and the verb is the head;
4. within the clause the object is a **program noun** phrase: program, manual, plan, schedule, policy, procedure, protocol, checklist, guidelines, standards, rules;
5. none of the **stops** applies: "policy of insurance" and "insurance policy" (a homonym), "parliamentary procedure" (a method), "this Policy" and "the procedures set forth below" (the document speaking of itself), "established guidelines set forth in" a statute (a reference to law), a compliance duty with no adoption ("ensuring the implementation of, and compliance with, this Policy").

The enumerated steps are the duty's inherited readings (the lead-in passes its kind and bearer to the list items). Each becomes a `STEP` element, its `recurrence_months` the element's `every_months`.

### The other shapes

| Shape | Rule |
|---|---|
| `OPTIONAL` | a `permission` or `condition` reading whose trigger is "if the Association adopts", or a duty attached to "an X program that the Association may adopt" |
| `PRESUPPOSED` | a **named-instrument reference** (below) in a duty's clause: "pursuant to the Association's 'X' program", "in accordance with a schedule adopted by the Board", "guidelines adopted by the Board", "standards ..., if any exist" |
| owner's program | the `ADOPT` rule with an owner bearer |
| condition of approval | the **conditions reader** (below), over an approval document: a lettered or numbered condition whose subject is "the homeowners' association", "the owner or operator", or the applicant, with a duty marker, read as a duty with its approver ("subject to review and approval by the Planning Director") and its floors ("not less than monthly", "at least once every 8 years") |

### The conditions reader

A city's or county's conditions of approval for a development are not in the governing documents, so the duty reader of the outlines never sees them. The conditions reader reads the **approval document** (a staff report, a resolution of approval, a map's conditions) as an outline of its own, with the same grammar as `deontic.read_outline`, and adds three things the grammar lacks:

- **the subject**: "the homeowner's association", "the applicant", "the owner/operator", or a role of the agency; a condition whose subject is the applicant at the time of approval is read as **not the association's** until a person says it passed to it (it is the developer's, and whether it binds the association is the open question);
- **the approver**: the officer or body whose review or approval the condition names, kept as a field, so the review can ask whether the approval is on file;
- **the scope**: the parcels, buildings, or phases the approval names, as a fact for the row's `applies`.

A reading is a lead for a person; a condition becomes a `CONDITION_OF_APPROVAL` row only on a person's confirmation. It is **not** read for a binding effect: jason recites the agency's words and the question.

### Keeping false positives out

- The rule is **narrow on purpose**: precision first, because every hit becomes a row that a person confirms, and the confirmation queue is finite ([handoff-confirmations-queue.md](console/handoff-confirmations-queue.md)).
- A hit is a **lead for a person** (`ReviewStatus`); only a confirmed hit enters `Community.program_requirements()`. A reading never becomes a row on its own.
- **A miss stays a miss.** "Periodically", "from time to time", and "appropriate" are not frequencies: an element with no stated recurrence says so, and that is a question for the board, not a default ("periodic" never becomes "annual").
- **A quote is not an adoption, a payment is not an inspection, a last-modified date is not an inspection date.** These three false positives (above) are guards in the readers, each with a test from a real false hit.
- The stops are data (`program_detect.STOPS`), each with a test from a real false hit.
- A **gold set** (`data/programs/gold/programs.json`, private; made-up twins under `tests/fixtures`) labels positives, optional and presupposed shapes, and look-alikes before the rule is tuned, in the manner of `scripts/eval_duties.py`; the rule is reported with precision and recall by shape, and read as "about four in five" until a person has reviewed the corpus, as [document-duties.md](document-duties.md) reads the grammar.

## Finding what exists: the lifecycle, a stage at a time

Two real cases (a quarterly inspection program and a maintenance manual, each required by a declaration) showed that a program passes through **six stages, each with its own evidence, and each fails on its own**. A register that shows one blended "compliant" hides which stage is missing.

| Stage | The question | Evidence | States |
|---|---|---|---|
| 1. **Mandate** | what obliges the association, and what does it say? | the catalog row: the shelf, the declaration, or a condition of approval, recited | required · optional · presupposed · undetermined (a fact missing) · counsel first |
| 2. **Written program** | is there a document of that kind? | the resolver (below) over the library, Drive, and the outlines | not on file · on file · embedded in another document at a section · several candidates (listed; jason picks neither) · not read |
| 3. **Adopting act** | did the board adopt *that document*, by an act on record? | `AdoptionEvidence` | no act on record · act on record (kind, date, where) · stated by the document itself · unsigned draft · adopted by a document of higher authority |
| 4. **Implementation records** | is each step done, on its clock, with a dated record? | the records by element and window (the log kind, below) | each timed element's `Standing`: done, done late, no evidence, upcoming, due soon, overdue, date not on record, no store shows it; and, for a continuous or event step, "no record kind shows it" |
| 5. **Owner communication** | were owners told their part? | the notice's proof (the owners' manual, the annual statement, a letter) | not required · not on file · on file (date) · a decision not to (recorded) |
| 6. **Review** | has the program been reviewed, against the law in force, in its own cycle? | the programs lens; the minutes of the review | none · reviewed (day, by whom) · overdue · stale |

The program's overall word is computed from these: **missing** (required, no document), **drafted** (a document, no adoption evidence), **adopted** (document and act), **implemented** (and the records show the steps), **reviewed** (and a review exists as of a date), **current**, **stale**. A row with `fallback = STATUTE_DEFAULT` and no document of its own reads **default applies**, never "missing". The register shows the six stages as a strip, one word each.

### Adoption is an act, and a quotation is not one

The first real run of the revision report printed "adoption on record" for minutes that merely **quoted the section that required the program**. Naming a section is not adopting it. The rules for `AdoptionEvidence`:

1. **An adoption is a board act whose date can differ from the document's own.** A program's footer may read "adopted" on one day while the minutes record the vote on another. Both are kept, labeled ("the document says; the minutes record"), and jason picks neither as *the* date.
2. **A minutes entry counts only if its verb adopts the named instrument.** The verb is classed, each class a state of its own, from the motion's or entry's own sentence:

| Verb class | Examples of the words | Counts as |
|---|---|---|
| **adopted** | "adopted", "approved the program", "resolved to adopt", with a vote | **adoption** (a lead until a person confirms; the minutes' words recited) |
| **delegated** | "delegated a director to draft", "asked management to prepare" | a step toward adoption; **not** an adoption |
| **directed** | "we would like to direct management to ...", with no motion recorded | an intent; **not** an adoption |
| **listed** | "the manual was in the packet", an agenda attachment | **not** an adoption; evidence the board had it |
| **reviewed / discussed** | "Review Procedures" as an item | not an adoption; evidence of review |
| **quoted / cited** | the section's words repeated, or a citation of it | **not** evidence at all of adoption; it is evidence of the mandate |
| **declined** | "will not be implementing a certification program" | a recorded decision, shown as one |

3. **A vendor's proposal approved, or a contract signed, is implementation evidence**, not adoption (a program's steps may be carried out by a contract; the board's approval is a CIV 5200 record).
4. **A document that says it was adopted** is evidence of the claim, "stated by the document itself", until an act is found.
5. Where nothing matches, the state is "no act on record" with the minutes searched: how many sets, from which month to which, how many unread, **and which are not in the index at all** (a search over an index that begins in 2024 cannot find a 2022 act; the gap is named, not silent).

**An approval of a vendor's proposal is not the adoption of a program.** jason lists it apart and does not count it as adoption.

### The implementation record: the inspection log kind

A program's steps leave records of one shape: a **dated log** appended to, with an inspector, the area or component, the condition found, and photos. The kind (`DocumentKind.PROGRAM_RECORD`, subkind log) has fields a reader extracts (each its own dated entry, the inspector, the areas, the photo references) and four rules the real cases forced:

- **A reused template erases history.** A worksheet cleared and refilled loses the earlier entries; the reader notes "a template reused: earlier entries are not in this copy" and counts only the entries the file holds, never inferring the rest.
- **A copy is not a new inspection.** Two files with the same text, or a copy made on a later date, is one record; the later date is a copy date.
- **A last-modified date is not an inspection date.** A file's Drive revision date is evidence that someone saved it; it is shown as "saved on", never as "inspected on". Drive revision history is evidence jason keeps no store of; a person may read it and record it, labeled.
- **A payment is not an inspection.** A vendor's invoice for a repair or cleaning is evidence of the work, in its own row, never of an inspection; and a log with no dated entry is "undated", not "done late".

Each entry is placed to a step and a window by its own fields (the Completeness lens of `jason inspections` is the model: a reading that lacks a field is "unplaced" with the field named). One visit can satisfy several rows, and the log names which (below).

## Review: the document against the requirement, element by element

A review is one **lens** (`programs`) applied to one `ProgramDocument` (or a collection) as of a day, in the three parts of [ingestion-and-review.md](ingestion-and-review.md): findings of fact, the law, the application. Its checks, each a `LensCheck` over a reading's fields:

| Check | Asks | `Finding.basis` | Result |
|---|---|---|---|
| `elements-present` | for each element: does a passage of the document carry its anchors? | `TEXT` | **found at** a passage, **not found** (the search made), **unknown** (the document is unread), or **for a person** (an element a grammar cannot judge: "fair", "reasonable") |
| `frequency-not-longer` | does the document's stated recurrence exceed the requirement's minimum? | `TEXT`, `LAW` | a finding only when both are numbers: "document says every 6 months; the requirement says not less frequently than 3" |
| `adopted-by-act` | is there an act on record, dated on or before the document's effective date, by the body the instrument names? | `PROFILE`, `STORE` | act found, or "no act on record" with the search |
| `adoption-formalities` | for an operating rule: in writing, authority, notice under 4360 where 4355(a) reaches it | `LAW`, `STORE` | each with the section recited; whether 4355(a) reaches it is a labeled reading, and a question for counsel where unclear |
| `implemented-on-schedule` | per timed element, the standing of its derived obligation | `STORE`, `TODAY` | the same `Standing` words |
| `law-in-force` | as of the day, are the authorities the words in force, and has a lead appeared since the document's date? | `LAW` | "the words as of that day" through `law_readings.recite`; "not shown to be in force"; or a `Conflict` candidate |
| `review-overdue` | is the document's own review element (an annual review) done? | `STORE`, `TODAY` | overdue, or the date |
| `cadence-set` | for each element, which of the four cadences the document fixes; a silent one has the board's number? | `TEXT`, `PROFILE` | fixed (the number); silent (a question; a proposed value shown as not adopted); event or continuous (no clock, how it is verified) |
| `alignment` | does each component's interval or life agree across the sources? | `TEXT`, `STORE`, `LAW` | each differing value side by side with its source; an omission; no pick (above) |
| `no-double-count` | does the program restate a row a sub-program or another authority already holds? | `PROFILE`, `STORE` | the row it duplicates, and the pointer to use instead |
| `responsible-party` | does each component and step name who does it, for the association and for owners? | `TEXT` | named · not stated (a question) |
| `owner-communication` | for an owner's twin: has the association's part (notify, remind, enforce) been done or decided? | `STORE`, `PROFILE` | the notice's proof, or the recorded decision not to |
| `law-stated-in-program` | does a statement of law *inside* the program match the shelf **as of the day**? | `TEXT`, `LAW` | each cited section checked against the words in force on the program's date and today, through `law_readings.recite` and `quote_check`; "quotes the section as it stood before an amendment", "cites another code's name", or "not on the shelf" are findings of fact, none says a law was violated |
| `conditions-carried` | for a condition of approval: does the program carry each floor, and is the named approver's approval on file? | `TEXT`, `STORE` | carried · not carried (the floor and the program's value) · approval not on file |

An element's anchors **find passages; they do not decide**. "Found at section 4" is a lead; "met" is a person's confirmed verdict, kept with their name and the passage. A model may propose a verdict only with a verbatim quote that the document holds (`reference_model.find_quote`), as the duty reader does, and its answer is labeled the model's. A review decides nothing and is stored beside, not over, the reading. It is rerun when its key changes (the document's digest, the lens's version, the as-of day, the context digest).

## Deriving duties, obligations, and deadlines

Each timed element yields a **proposed** `Obligation`:

- `name`: the element's words, short; `authority`: the citation; `every_months`: the element's recurrence; `first_due`: the adoption date plus one period when the document or statute fixes none, **labeled as computed**; `applies`: the row's condition; `categories`/`payee_words`/`done_on`: the evidence kinds (an inspection report's date, a vendor's payment);
- `jason programs KEY --obligations` prints them; the **person** adds them to the profile's obligation rows (`Community.obligations()`), after which `jason deadlines` and the schedule carry them (the same path as [document-duties.md](document-duties.md): "when a person decides one should be tracked, the decision becomes an `Obligation` row ... written by a person");
- an element with no stated recurrence yields **no** row and one question: "the document says 'periodically'; the board states how often (a policy to write)";
- an `OwnerDuty` yields no association deadline except the **notice** that tells owners (a row in `notice_catalog` or the annual statement's content), and "record done" for it is the notice's proof.

## The gap report

The catalog applied to one association, in three groups and a fourth that is not a gap:

1. **Required by statute, not found or not adopted:** each `STATUTE` or `STATUTE_CONDITIONAL` row whose answer is *applies*, with its three evidences. A row that is *undetermined* is not here: it is in the questions. A row that is `default applies` is listed apart, with the default's recital.
2. **Required by the declaration, not found or not adopted:** each confirmed `DECLARATION` row, the same way. A `PRESUPPOSED` row is a question. A `CONDITION_OF_APPROVAL` row is listed here with its agency and its `COUNSEL_FIRST` caveat ("whether it binds the association is not settled"), apart from the declaration's rows, so a mandate that may not bind is never shown as one that does. Each row shows its **six stages** (the lifecycle above), so a program that is written, adopted by a minute entry, and never inspected reads as that.
3. **Adopted, but now conflicting with a newer statute:** the leads `jason conflicts --leads` lists against each adopted program's authorities, and each `Conflict` row that touches one. jason notes; the board, counsel, or an amendment resolves.
4. **Questions:** the facts missing for a conditional row, the presupposed rows, the elements for a person, the references unresolved.

`jason programs --gaps [--as-of DATE] [--json]`, and a section of `jason applies` for the facts. It serves two uses:
- **Onboarding.** A new association's adoption checklist: `onboarding` gets a group of items generated from the catalog (the policy catalog's `POLICIES` group, extended), each asking whether the association has one, finding leads, binding a found document, or proposing one ([onboarding.md](onboarding.md)).
- **The January law review.** `jason sop law-review` gains a step after `jason conflicts --leads`: run `jason programs --gaps --as-of` and read each program whose authority changed (lesson `law-outdates-provisions`).

## Base templates and the proposal path

Where a required program is missing, jason **drafts** one. It does not adopt, send, or publish it ([AGENTS.md](../AGENTS.md): "jason proposes; the board adopts").

**The draft is generated from the requirement's elements.** A base template per requirement kind (below) has front matter naming the requirement and the elements it covers; `jason templates --lint` is extended to check that **every element of the requirement has a section** in the template. The generator renders:

- the title, the authority, and the operative words, recited (`{QUOTE:key#n}` or `jason cite`), then a labeled reading if one is needed;
- the responsible party as `[BOARD CHOICE: who]` where the law names none;
- each `STEP` as a numbered item with its recurrence **recited** ("not less frequently than quarterly") and the record kept;
- the records kept, the report to the board, the annual review element, the adoption clause;
- a `[BOARD CHOICE]` field for everything the law and the declaration leave open (a frequency stated as "periodic" is exactly this). jason may show a *proposed* value from the association's history, marked "jason's proposed default, not adopted" (as the policy catalog does) and never as text.

**The path.** draft → counsel check where the row is `COUNSEL_FIRST` or the reading is unclear → board item → (if an operating rule on a 4355(a) subject) the 4360 notice, drafted with `jason rule-change`, "a reading" → the board's agenda → a vote at an open meeting, in a `DecisionBrief` that lists adopt, adopt with changes, decline (and how the duty is met otherwise), and ask counsel, **never a recommendation** → the minutes → the adoption evidence read from the minutes (or a person's signed record) → standing becomes **adopted**. A program on the maintenance of the common area is, by 4355(b)(1), outside 4360 and 4365; a program that also binds owners in their units may be a rule on "use of a separate interest"; both are labeled readings and questions for counsel, not conclusions.

### Which base templates exist, and which are needed

| Requirement | Base template today | Needed |
|---|---|---|
| Notice of the board meeting where it is voted (4920) | `src/jason/templates/notices/board-meeting-notice.md` | exists |
| Annual policy statement (5310, with 5730's notice) | `src/jason/templates/packets/annual-policy-statement.md` | exists; carries the statements, not the policies |
| Annual budget report with the reserve summary (5300) | `src/jason/templates/packets/annual-budget-report.md` | exists; the funding plan itself is not a template |
| Rules and Regulations, owner's manual | `src/jason/templates/manual/rules.md`, `owners-manual.md` | exist as extractions of adopted words, not as drafting bases |
| Proposed and adopted rule change (4360) | the generators in `rule_changes.py` (`jason rule-change`) | to move onto the base system ([base-templates.md](base-templates.md), "Rules") |
| Notice of a hearing and decision (5855) | `community.templates.BODIES`, the hearing and decision `DocumentTemplate` rows | exist (they implement the fine schedule's process, not the schedule) |
| IDR request (5915) | the `FormTemplate` for the IDR request | exists (the request, not the procedure) |
| Inspection-and-prevention program | none | **write**: `programs/inspection-program.md`, from a requirement's `STEP`, `FREQUENCY`, `RECORD` elements |
| Inspection-and-maintenance manual | none | **write**: `programs/maintenance-manual.md` |
| Fine schedule (5850) | none | **write**: `programs/penalty-schedule.md` |
| IDR procedure (5905, 5910) | none | **write**: `programs/idr-procedure.md`; the statute's default (5915) is the fallback text |
| Architectural review procedure (4765) | none | **write**: `programs/review-procedure.md` |
| Election operating rules (5105) | none | **write**: `programs/election-rules.md` |
| Reserve funding plan (5550, 5560) | none | **write**: `programs/reserve-funding-plan.md`, tables from the reserve study data |
| EV charging terms of use (4745(h)) | none | **write**: `programs/ev-terms.md` |
| Payment plan standards (5665), collection policy | none | **write**, after the board decides the questions |
| The resolution that adopts any of these | none | **write**: `programs/adopting-resolution.md` (WHEREAS recitals reciting the requirement; resolved; effective date; the minutes' reference) |

A base template names no association. A profile renders it with its identity, letterhead, and citations, and a community-specific copy is generated, never edited by hand ([base-templates.md](base-templates.md)).

## Implementation tracking

An adopted program is only half done. Each timed element has an `Obligation` (derived, then a person's) and the **evidence** the program says it leaves: an inspection report, a log, a checklist, a vendor's visit record. The Completeness lens that already serves the life-safety records (`jason inspections`) is the model: its expected documents are the periods of each obligation, its evidence a reading placed by its own fields or a person's completion, a report that lacks a date is "unplaced" with the field named, an unread file is "not read", and "not on file" is never "not done". The programs lens reuses it, element by element. A round of inspection recorded in a log, and the minutes noting the board received the report, are both evidence; neither is judged adequate.

## How pest, backflow, and life safety are instances

| Program | What exists | Where it is an instance of this design |
|---|---|---|
| Wood-destroying pests | `jason pests`, the `pest_program` tool, `pest_visits.py`, the duty "Pest control" in `duties.py`, [pest-management.md](pest-management.md) | a declaration provision that is **`OPTIONAL`** ("if the Association adopts an inspection and preventive program") with duties that attach if adopted; the vendor's visit record is the **implementation** evidence; adoption is a labeled reading (the board's approval of a vendor proposal) |
| Backflow prevention | `community/backflow.py` (`BackflowProgram`, `ProgramNotice`, `WatchEntry`), `jason backflow`, `docs/cross-connection-control.md`, an `Obligation` row | a program with a supplier's own cycle: the statute and the handbook, a local program, an `Obligation` for the test, notices as `ProgramNotice` clocks. The standing words `unknown` and `partly answered` are `Standing` words of this page |
| Life safety | `life_safety.py`, `elevated_inspections.py`, `jason inspections`, `docs/life-safety-inspections.md`, many `Obligation` rows with `applies` | the Completeness lens, per-system applicability, `Standing` incl. "date not on record" |
| A moisture or similar inspection program in a declaration | none | the worked example of an `ADOPT_AND_IMPLEMENT` declaration row with an owner's twin |
| An inspection and maintenance manual | none | an `ADOPT` declaration row with a permission to revise and no stated frequency |

Each of the three is, under a maintenance-type parent program, a **sub-program the parent points at** (`parent` on the row), never a copy of its rows ("Overlap"). A mold-type program and a maintenance-manual-type program are the two worked cases that shaped the lifecycle, the cadences, the register, and the overlap rules above; each has a profile page, and its private findings stay in the profile's notes.

The code of the three precedents is not rewritten. Each becomes an instance when its `Obligation` rows, its watchlist, or its program record is attached to a `ProgramRequirement` (the row's `obligations` and `evidence` pointers), so that the register shows it beside the others. The deep dives (a program's collection, pack recipe, and lens checks) are **instances** of the general forms below.

## The ingestion pipeline: finding mandates and referenced programs

Ingestion needs only the file; the review needs the world. The mandates are found in two passes of ingestion and **stored as readings**, and the comparison with the document is a **review under a lens**. The design follows [ingestion-and-review.md](ingestion-and-review.md) ("read once, review many times").

### (a) Duty extraction: mark the adoption shape

**Exists:** `deontic.read_outline` reads every norm of an outline, with bearer, marker, recurrence, and the inherited items of a list (`DocumentDuty.inherited`, `recurrence_months`); `tasks/document_duties.py` stores them under `data/duties/<key>.json` with reviews and an id stable across rereads; `duty_model.py` is the model reader with the quote check.

**Add:** `jason.community.program_detect` (`shape(duty, outline) -> AdoptionReading | None`), the rule above, as data (`HEAD_VERBS`, `PROGRAM_NOUNS`, `STOPS`); it reads the duties already stored, and the outline for the clause a duty sits in. It keeps the **verb**, the **object noun**, the **name as written** (the object noun phrase, "moisture inspection and prevention program"), and the **steps** (the inherited readings under the lead-in, each with its recurrence). Stored as `data/programs/readings/<outline key>.json`, keyed by duty id; a reread that leaves the duty's words alone keeps the reading and its review. It never changes `DocumentDuty` or its id.

### (b) A reference extractor for named community instruments

**Exists:** `references.extract` reads statutes, sections, whole known documents (`enforcement-policy`), resolutions, and recorded instruments, with a relation verb (`RefRelation`: acts under, is subject to, is required by, replaces).

**Add:** a `TargetKind.NAMED` and a grammar for mentions of an instrument that is not a known document:

| Pattern | Reads |
|---|---|
| a possessive and a noun: "the Association's 'X' program", "the Board's schedule" | the name as written, the noun |
| "adopted by": "a schedule adopted by the Board", "guidelines adopted by the Board", "rules duly adopted" | an instrument the document expects the board to have adopted |
| "may adopt": "such procedures as the Association may adopt" | expected, not existing |
| "if any": "standards for payment plans, if any exist" | conditional |
| "if the Association adopts" | optional |

Each mention is a **reference row**: who mentions it (the source document and section), where (the offset and the sentence), its **name as written**, its **noun**, and its **kind if known** (`DocumentKind` from the noun), plus `conditional` and `expected` flags. Names are normalized (case, determiners, the possessive, a trailing "program") and carry the `ProgramRequirement.names` synonyms (the *law's* vocabulary: "meet and confer" with "internal dispute resolution"). The same stops apply ("insurance policy"). No pattern names a vendor, a street, or an association.

### (c) Kind rules and phrase rules

**Exists:** `DocumentKind` already has `POLICY`, `OPERATING_RULES`, `ELECTION_RULES`, `RESOLUTION`, `MINUTES`, `INSPECTION_REPORT`, `ELEVATED_ELEMENT_INSPECTION`, `COMMITTEE_REPORT`, `FORM`, `TEMPLATE`; `classify_document` applies a profile's `KindRule`s (names, folders, paths) first, then `content.CONTENT_RULES` (phrases near the top), then `RECORD_RULES`, then a local model that never overrides a rule.

**Add:**
- kinds. The real cases found **no kind** for a program, manual, schedule, responsibility chart, inspection log, worksheet, equipment manual, or warranty, and "the manual" meant **five different documents** (a developer's care guide, a draft chart, the program the declaration requires, an equipment manual, the owners' manual). So kinds are named by what the document **does**, not by the word "manual": `DocumentKind.PROGRAM` (a written program, manual, plan, or schedule the association adopts), `RESPONSIBILITY_CHART` (who maintains what), `PROGRAM_RECORD` (a log, checklist, or worksheet of one round of steps, with the log subkind of the previous section), `EQUIPMENT_MANUAL`, and `WARRANTY`; plus a **developer's care guide** is `PROGRAM`-like but marked `DEVELOPER_DELIVERED`, never the association's adopted manual until an act says so. Each has a shelf in `documents.PROFILE` and, where it is one, a CIV 5200 record (decision 3). A reference that says "the manual" is resolved by **kind and role** (the one the mandate requires) and, where several fit, lists them all and picks none;
- generic `ContentRule`s whose phrases are the genre's own words, never a profile's: "this program", "the following steps", "inspection and maintenance manual", "purpose of this plan", "shall be reviewed annually", and, for the adoption act, "adopted by the board of directors on"; each needs its `min_hits` and a test from a real false hit;
- a profile's `KindRule` rows for the association's own file names (its facts), as today;
- a `RecordRule` tying a program adopted by the board to the minutes that record it (an adoption's evidence is a CIV 5200 record).

### (d) Adoption evidence

**Exists:** minutes' `Action` rows (mover, seconder, vote, the decision's words: `_MOTION`), resolutions with `ResolutionType` and `ResolutionSubject`, `readings.AdoptionReader` ("adopted on", a blank `DATED:` line as an unsigned draft), `manual.AdoptionEvent` (noticed, adopted, delivered), `record_stages`.

**Add:** a field on the minutes and resolution readers, `adopts: tuple[str, ...]`, the names of instruments a motion or resolution adopts, approves, ratifies, amends, or rescinds, read from the motion's sentence by a small grammar (verb, optional determiner, a noun phrase ending in a program noun); a `ResolutionSubject.PROGRAM`. A linking step matches each name to a reference or a `ProgramRequirement.names` by the same normalization, producing an `AdoptionEvidence` row with the quote. Each entry is given a **verb class** (adopted, delegated, directed, listed, reviewed, quoted, declined; the table above) by a small grammar over the entry's own sentence, so "delegated a director to draft", "we would like to direct management to", and "was listed in the packet" are not read as adoption, and a sentence that **only repeats the section** is read as the mandate's words and never as an act (the false "adoption on record" the revision report printed). A motion that approves a *vendor proposal or contract* is classed as implementation evidence, not adoption. The document's own stated date and the act's date are kept apart. Where nothing matches, the state is "no act on record" with the minutes searched (which months, how many sets, how many unread). A person may record an act jason did not find (`--adopted`, signed).

### (e) The resolver, and the ingestion-versus-review split

**Add:** `jason.community.program_resolver.resolve(reference, library, outlines)`: candidates by **kind** (the noun's kinds), by **name** (title, outline key, a heading inside a governing document, the Drive name), and by the passage index (`jason index --search`, hybrid, scoped to the kinds). Outcomes: **found** (one document and where), **embedded** (an instrument that is a section or exhibit of another document, found by heading; `embedded_copies.py`), **several** (all listed; picks none), **not found** (**a finding, never a guess**, with the query run and the date), **not read**. An unresolved reference is a *missing document*: it is on the gap report with the sentence that mentions it.

| Output | Layer | Stored | Rerun when |
|---|---|---|---|
| `AdoptionReading`, `NamedReference`, `AdoptionEvidence` candidates (what the words say) | **ingestion**: a function of the file's text | `data/programs/readings/`, the reference store | the outline's digest or the reader's version changes; `jason outlines --fetch`, a new library file, new minutes |
| the resolver's result (which document answers the name) | ingestion of the library, over the index | `data/programs/found.json` | a file is added or reclassified; the index is rebuilt |
| the requirement against the document, element by element | **review** under the `programs` lens | `data/reviews/programs/...` | the document's digest, the lens's version, the as-of day, or the law's text digest changes |
| the gap report, the standing words | computed from the above and the profile, the day | not stored as fixed | on read |

The pipeline is **re-run when a governing document changes** (an amendment: the outline's digest, `jason living`), **when the shelf changes** (`jason export-authorities`, a changed section's digest marks readings stale, `jason readings --stale`), and in the January law review. Findings that depend on today are keyed by the as-of day, never stored as fixed.

### (f) How to measure it

- **Hits on the association's documents.** `scripts/eval_programs.py` runs the rule over `data/duties/*.json` and the outlines and reports hits by shape; the output is private (it names provisions).
- **False positives.** Each hit is read by a person and labeled true, false (with the stop it needs), or a different shape; the figures go in a table with the rule's version.
- **A small gold set.** About thirty passages labeled before tuning: the positives (adopt, adopt and implement, with steps), the optional and presupposed shapes, and look-alikes (an insurance "policy", a parliamentary "procedure", a document speaking of itself, a statute-citing "guidelines"). Half for tuning, half held out, as in [document-duties.md](document-duties.md). A made-up twin set lives in `tests/fixtures`.
- **The resolver.** For each reference, labeled: the right document, an embedded copy, several, or none; precision of "not found" is the number that matters (a wrongly missing document is a false gap).
- **The adoption link.** For each motion that adopts a named instrument, labeled: linked right, linked wrong, missed.
- The figures and a trial row go in the trials table of [document-tools.md](document-tools.md) when a model is used.

### What the two real cases found: the ingestion gaps, and what each needs

Both cases, run by hand against a real library and Drive, hit the same gaps. Each is a task, in the order they block the rest.

| Gap | Effect | What to add |
|---|---|---|
| **No `DocumentKind` for the genre** (program, manual, schedule, responsibility chart, inspection log, worksheet, equipment manual, warranty) | nothing finds a program by kind; a log is "unclassified" | the kinds and phrase rules in (c); the `ContentRule` phrases are the genre's own words |
| **Drive Docs and Sheets unclassified and unindexed** | the program and its worksheets are invisible to search, to `verify-quotes`, and to the pack | classify Drive-native files outside a Drive root by content (`content.classify_text`), read them (text, with the sheet's tabs and cell dates), and add them to the passage index in their own catalog |
| **Minutes before a date are not in the index** | an adopting act from earlier years is unsearchable and unquotable; "no act on record" would be a false gap | index the minutes cache back to the earliest set, and report on each program "minutes searched from X to Y; not indexed before Z" |
| **References unresolved** ("the manual"; "CC&R 7.8 (a)", which names no document and so is ambiguous across two documents that both have a 7.8) | nothing links the act or the report to the section | the reference extractor of (b), with an **ambiguity state**: a section number with no document name lists every document that has it, and the minutes' own context (a "CC&R" abbreviation) is a lead, not a pick. Built as `jason.community.scoping` (`jason cite --scan FILE --in KEY --on DAY`; the miss `ambiguous_document` with its candidates, a document named earlier in the paragraph as a `leads` entry). "CC&R 7.8 (a)" itself names its document (CC&R is a name the specification gives it) and resolves; "Section 7.8" with no name and no citing document is the ambiguous one ([rule-citations.md](rule-citations.md)) |
| **Reserve-study component narratives not read** | the maintenance assumptions behind each life, and the components the study omits, are not available to the alignment check | a reserve-study reader that extracts per-component narrative: component, life, the maintenance assumed, with the page; it is a record reader (a `DocumentModel`), not a duty reader |
| **Three copies of one document not folded** (a Doc, a PDF, a Word file of the same text) | three members, three hits, three false "several candidates" | fold by text digest and near-copy (the index already folds near copies; extend the program resolver to it) |
| **A statement of law inside a program not checked** | a quoted pre-amendment statute, or one cited under another code's name, goes unseen | the `law-stated-in-program` check, over each citation in a program document, as of the program's date and today |
| **The word "manual" means five documents** | a wrong resolution | kinds by function, and the resolver's role |
| **The duty reader gives "immediately", "periodically", "at all times" no cadence** | no clock, silently | the four-cadence field on the element; `deontic` marks the cadence kind (it already reads `recurrence_months`) |
| **A minutes revision report prints "adoption on record" for a quote** | a false adoption | the verb classes of (d) |
| **A condition of approval is not outlined as a duty** | a mandate outside the declaration is missed | the conditions reader |
| **An inspection log has no date field; its only dates are Drive revisions jason keeps no store of; photos in an album jason cannot read** | an inspection is undated or invented | the log kind's rules; a store of Drive revision dates **as evidence labeled "saved on"**, read-only and per file; photos counted by link, never read |

### Screening on Drive ingestion

Reading Drive Docs into the index brings in material that must be **held back or refused before it is read**. Two real findings:

- **Privileged counsel letters** must be held back. A letter from counsel that had no document kind and no confidential flag would have entered the index and a pack. Screening classifies by **sender and content before indexing** (the sender directory's kind for counsel, and phrase rules for "privileged and confidential" and "attorney-client"), sets `confidential` and the privilege hold, and **a document whose kind is "" and whose source is unknown is held, not indexed** (a miss is held, not passed). A held document is listed with the reason, never read into a pack for a non-board audience, and never a member of a program's collection.
- **A secret scan of a Doc's text** before it is indexed or summarized. A Doc in a real Drive held credentials in plain text. The scan is `intake.secret_reason` (the same check that refuses a secret in an answer) run over every Drive Doc and Sheet on ingestion; a hit holds the file, **redacts it from every page and pack**, and raises a finding for a person ("this Doc holds what looks like a credential: rotate it"), never quoting the secret.

Both screens run **before** classification, indexing, and any model call, and are re-run when the rules change. They are ingestion, a function of the file's bytes and the sender directory.

## The programs lens, the context packs, the collections

### The lens

`reviews.PROGRAMS = Lens("programs", "Does the association have the program the law or its documents require, is it adopted by a cited act, is it carried out, and does it follow the law in force on the day?", needs_as_of=True, gathers=True)`. Its checks are the table above. A lens is a row of data (no association's facts in code): its authority scope is the requirement's `authority` and `also`; its reference material is the requirement's page (below); the facts it needs are the applicability facts and the three evidences. The as-of lens ([handoff-as-of-and-quote-check.md](console/handoff-as-of-and-quote-check.md)) supplies "the law in force on the day"; a statute amended after the document's date is a lead.

### A context pack per program

`context_pack.assemble` builds a pack for a task by tiers. The programs recipe, a `ProgramPack` row on the requirement, fills each:

| Tier | Holds for a program |
|---|---|
| **S**, the law | each statute in `authority` and `also`, **as of the day** through `law_readings.recite`; the sections it cites; a former section's words where renumbered |
| **G**, governing documents | the mandating provision with its defined terms (`RefRelation.DEFINED_IN`), the provisions that point at it (`references`), the documents that say how an instrument is adopted (the bylaws' rule-making, the operating rules' own amendment clause), and any section of the governing documents that embeds the instrument |
| **R**, records | the program's document, the adoption act (the minutes passage, the resolution), and the implementation records (reports and logs by kind, within the window) |
| **C**, the collection | the program's collection (below), labeled "records gathered for this program: neither the law nor a finding" |
| **F**, facts | the applicability verdict and its facts, the program's standing, its derived obligations' standings, the gap row, as the tools return them |
| **D**, the draft | the document under review, or the proposed draft |

The task prompt (`TaskPrompt`) names **topics and document kinds only**, never a section number or a figure (the prompts convention). `assemble` does not take a lens or a document digest yet ([ingestion-and-review.md](ingestion-and-review.md), step 3, "Open"); the programs pack is a use of it once it does, and until then a pack names the program's collection and kinds.

### A collection per program

Today a collection is code: `document_collections.collections(community)` yields one per legal case with a case file, and a `Scope` selects catalogs, kinds, and folders, never "the documents about a program". So `jason collection program-<key>` answers "no collection" for every program. Both real cases hit this, and a `Scope` cannot be the answer: the members of a program are documents the **kinds and folders do not gather** (a minutes passage that adopts it, a worksheet in a Drive folder of unrelated files, one letter to one owner).

The proposal is a profile row, `Program` (`Community.programs()`, empty by default), and `CollectionKind.PROGRAM` built from it by `document_collections.of_program(program)`. A `Program` holds the requirement keys it answers and its **named members, each with a role**:

| Role | Members |
|---|---|
| `MANDATE` | the mandating provisions and their neighbours (the declaration's sections, a condition of approval, the statutes) |
| `PROGRAM` | the written program or manual, every copy (folded: three copies of one manual are one member with three locations) |
| `ADOPTING_ACT` | the minutes, the resolution, the board item that adopt or delegate it |
| `RECORD` | the implementation records: logs, worksheets, reports, with their revision dates |
| `VENDOR_RECORD` | contracts, proposals, and reports by the step they serve (not by vendor) |
| `MAIL` | the correspondence about it |
| `OWNER_FACING` | the documents that tell owners (the owners' manual, a letter, a notice) |
| `REFERENCE` | the reserve study, the developer's deliveries, equipment manuals, warranties |
| `SUB_PROGRAM` | a sub-program's own collection, by key (listed, not merged) |

A member is a document id (or a passage: the minutes' item), never a copied text; a member's role and the `Scope` it falls under are both kept, so a program's collection can also take a `Scope` for the kinds it expects to find and report what the named list lacks. Its context lines are the requirement's recited words and elements, the found document, the adoption evidence **with its verb class**, the implementation standings, and the open questions; its label says what its material is. A privileged document is **never** a member ("Screening on Drive ingestion", above). The collection is confidential at the level of its strictest member. `jason collection program-<key>` builds the summary page under `data/collections/program-<key>/summary.md`, indexed in the collection's own catalog as a page jason wrote and never a member ([collections.md](collections.md)): its files and how each was read, what is missing, the open questions, the conflicts of fact, and the chronology (a program's life: the mandating provision's dates, the document's, the adoption, each round of the steps).

### A reference page per requirement

A generated **requirement page**, as the collection summary is: `data/programs/pages/<key>.md`, indexed with `generated` set, rebuilt and never edited, a summary that says so and points at the records it summarizes (it is never quoted as the rule). It holds the requirement recited element by element (with its version and caveat), the elements' bearers and frequencies, the standing by evidence, the derived obligations, the owners' duties, and the notices that tell owners. It serves the manager and the board, and a deep dive's findings link to it.

## Commands, loaders, and writes (proposed)

| Command | Does | Writes |
|---|---|---|
| `jason programs` | the catalog applied to the association, by source, with the standing words | nothing |
| `jason programs KEY` | one program: the requirement recited, the evidence, the review, the derived obligations, the owners' duties, the questions | nothing |
| `jason programs --gaps [--as-of DATE] [--json]` | the three groups and the questions | nothing |
| `jason programs --detect [--document KEY]` | read the stored duties, references, and minutes for mandates and names | `data/programs/readings/` (ingestion) |
| `jason programs --references [--unresolved]` | each named-instrument reference with its resolution | nothing |
| `jason programs KEY --review [--as-of DATE]` | the programs lens over the found document | `data/reviews/programs/` |
| `jason programs KEY --bind DOC --by NAME` | record that a document is the program's | `data/programs/found.json` (a person's record) |
| `jason programs KEY --adopted --minutes REF --on DATE --by NAME` | record an act jason did not find | the same; refused without a name and a record |
| `jason programs KEY --obligations` | the proposed `Obligation` rows | nothing |
| `jason programs KEY --draft` | the draft from the base template | `data/drafts/programs/<key>.md` |
| `jason programs KEY --propose --by NAME` | open a board item for the draft | the board register, through `jason board` |
| `jason collection program-KEY` | the collection's summary page | `data/collections/` |

Tools (read-only, `--profile governance` and `board`): `program_register`, `program_requirement`, `program_gaps`, `program_references`; the same functions as `jason.api`. Three of the commands above write a person's record and take `by`.

## Phases

1. **The model and the statute rows** (`programs.py`, `program_catalog.py`; the seven rows above with their words checked against the shelf; `jason programs`, read only; the new facts as questions).
2. **Detection** (`program_detect`, the named-instrument references, the resolver, `scripts/eval_programs.py`, the gold set), measured before it is relied on; the minutes' `adopts` field.
3. **Found, adopted, standing, and the gap report**; onboarding's items; the `law-review` step.
4. **The lens, the pack, the collection, the requirement page.**
5. **Base templates and the draft**, with the lint extended; the proposal flow into the board's items.
6. **Implementation tracking and derived obligations.**
7. **The console** ([console/handoff-programs.md](console/handoff-programs.md)).

## Decisions for the board and for the design

1. **One catalog or two.** The policy catalog's `PolicyTemplate`/`AdoptedPolicy` and this page's `ProgramRequirement`/`AdoptionEvidence` overlap. Decide whether `ProgramRequirement` is the required side and `PolicyTemplate` the parameter side of one record, with `AdoptedPolicy` as the adoption record shared by both, or whether they stay two. The design above assumes they converge at `Instrument` and `Adoption`.
2. **When a mandate enters the catalog.** A detected duty becomes a declaration row only on a person's confirmation. Decide who confirms (the manager, the board, counsel for a reading) and whether a declaration row is a rule row in the profile or a stored confirmation.
3. **New kinds.** `DocumentKind.PROGRAM` and `PROGRAM_RECORD`, or reuse `POLICY` and `INSPECTION_REPORT`. A new kind needs a shelf and a 5200 record.
4. **The 4355 reading.** Whether a program is an operating rule on a listed subject is a labeled reading and possibly counsel's. Decide the default the draft path takes when it is unclear: draft the 4360 notice anyway, or hold for counsel.
5. **A collection policy.** The statute requires a statement of the association's collection policies; whether it requires a *written policy* is not stated in the words read. The board decides whether to treat it as a proposal ("write it down").
6. **Owners' duties.** Whether jason may tell owners of the owner's half of a program, in the annual statement or a letter, and who writes the notice. jason enforces nothing.
7. **Frequency.** Where the document says "periodic" and the law is silent, the board states the period. Until it does the element has no clock and one question.
8. **Statute rows beyond the Civil Code.** Only the Civil Code was scanned. Decide the order of the other codes (Health and Safety, Business and Professions, Government) and the regulations.
9. **A condition of approval.** Whether the conditions of a public approval bind the association is the agency's or counsel's. Decide who asks, and whether the row is shown as a floor jason checks the program against (with the caveat) or held out of the register until answered.
10. **What an adopting act is.** Whether a minute entry that "approved the program" is an adequate adoption, or the board should adopt by resolution, is counsel's. Until then the entry is shown as an act on record, with its verb class and its date beside the document's own.
11. **The association's part toward owners.** Notify, remind, or enforce, for an owner's twin of a program: the board's decision, recorded as one (including a decision not to require certification).
12. **A store of Drive revision dates.** Whether jason keeps a read-only store of file revision dates as evidence (labeled "saved on"), and who may read it; a revision date is never an inspection date.
13. **Screening before indexing.** The rule for a document with no kind and an unknown source (held, not indexed), and who releases a held one.

## Limits

- **jason proposes; the board adopts.** No program is in force because jason drafted it. An unsigned or undated certificate is a draft.
- **Not legal advice.** A recitation informs; a reading is labeled and whose; where two readings remain, the board asks counsel.
- **A requirement yields to what is above it.** The statute, then the governing documents, then the board's rules (`authority_order.Tier`). A conflict is a `Conflict` row, never a silent override.
- **A match is a lead.** Anchors and the resolver find where to read; a person confirms.
- **Confidentiality carries over.** A review is as confidential as its document; a program that names owners' units, or counsel's advice, stays out of what is recited to others.
