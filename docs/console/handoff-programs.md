# Handoff: the programs, manuals, schedules, and plans the association must adopt and carry out

For the design pass on the components that show **what the association is obliged to adopt, whether it has it, whether the board adopted it, and whether it is carried out**, and the draft a person takes to the board where it has none. Nothing here is built: the catalog, the detection, the register, and the commands are proposed in [../programs.md](../programs.md), which settles the behavior. What exists today and feeds it: the notice catalog and its three-valued `applies` (`jason notices --catalog`, `jason applies`), the duties read from the governing documents (`jason duties --documents KEY`), the recurring deadlines with their evidence (`jason deadlines`), the life-safety completeness lens (`jason inspections`), the pest program (`jason pests`, the `pest_program` tool), the backflow program (`jason backflow`), the collection summary (`jason collection KEY`), and the conflicts and their leads (`jason conflicts --leads`).

The format follows [handoff-applicability-questions.md](handoff-applicability-questions.md) and [handoff-confirmations-queue.md](handoff-confirmations-queue.md). The words on screen follow [content/style.md](content/style.md), the patterns [content/patterns.md](content/patterns.md), and the components [components.md](components.md). The neighbours this page links to and does not repeat:
- [handoff-applicability-questions.md](handoff-applicability-questions.md): the three answers, `AnswerWord`, `VerdictRow`, the fact questions (a conditional program row reuses them);
- [handoff-confirmations-queue.md](handoff-confirmations-queue.md): a person's signed confirmation of a reading, which is how a detected mandate becomes a row;
- [handoff-collection-workspace.md](handoff-collection-workspace.md): a program's collection and its summary page;
- [handoff-context-pack-workbench.md](handoff-context-pack-workbench.md): the pack a program review runs under;
- [handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md): the day control and the law's words on a day;
- [screens/schedule-and-duties.md](screens/schedule-and-duties.md): the schedule and "record done" (a program's derived obligations appear there);
- [screens/board-items.md](screens/board-items.md): the board's items (a proposal becomes one);
- [screens/life-safety.md](screens/life-safety.md): the systems and their reports (a precedent, not a rival).

These components pair with what the console already has: `Pill`, `Recitation`, `ReadingLabel`, `DecisionBrief`, `QuestionCard`, `Confirm`, `Command`, `DataTable`, `Findings`, `Caveats`, `Card`, `Tabs`, `Doc`, `DueDate`, `Evidence`, `Clock`, `StageSteps`, `Checklist`, `Stat`, `EmptyState`, and `RemoteView`. Build new parts only where the table says so.

## The idea in one line

A provision says the association must adopt something; the console shows the requirement recited element by element, then three evidences side by side (the document, the board's act, the records that it is carried out), each as its own word, with the question that settles any that is missing. It never says "not adopted" where it means "no act on record", never says "not done" where it means "not on file", and has no approve control: the board adopts by vote, and the console shows the draft and the way to the board.

## The components

| Component | Where it renders | Data | States to design |
|---|---|---|---|
| `ProgramRegister` | `#/programs` | `programs` loader: rows by source, with the association's facts | grouped by source (statute, statute with a condition, declaration); a group with none ("Declaration: none confirmed yet. 4 detected, waiting on a person"); no catalog at all (the profile sets none); the gap summary above the groups |
| `ProgramRow` | inside `ProgramRegister` | one row: key, title, authority, answer, three evidences, overall word | required, not required (the deciding fact), question (the fact missing, linked to its `FactQuestionRow`); each of the three evidences in its own states below; **default applies**; **optional**; **presupposed** (a question, never a gap) |
| `StandingWord` (a `Pill` preset) | `ProgramRow`, the page header | the overall `ProgramStanding` | missing · drafted · adopted · implemented · reviewed · current · stale · default applies · optional · presupposed; each with its meaning in a hover card and in the row's text |
| `EvidenceTrio` | `ProgramRow`, `ProgramPage` | the three evidences | **Document:** not on file, on file, embedded in another document at a section, several candidates, not read. **Adoption:** no act on record, act on record (kind and date), stated by the document itself, unsigned draft, adopted by a document of higher authority. **Implementation:** the worst `Standing` of its timed elements with a count, or "no schedule" (no timed element), or "not due yet (adopted DATE)". Never a color alone; each is a word and a date |
| `ProgramPage` | `#/programs/<key>` | `program` loader | the bands below; a program with no document, or no applicability facts, or no elements recited |
| `ElementRecital` | `ProgramPage`, band **The requirement** | one element: `Recitation` of its words, the cite, the bearer, the recurrence, the record | statute element (recited from the shelf with its version in force); declaration element (the document's words with the section and the document's standing as amended); an element read by the grammar and not yet confirmed (labeled "read by jason, unconfirmed"); a recurrence stated ("not less frequently than quarterly: every 3 months") or **none stated** ("the words say 'periodic'; no clock; a question for the board") |
| `ProgramDocumentCard` | band **The document** | `ProgramDocument` | not on file (the search made: the kinds, the names, the date); on file (title, kind, dates, where, how read); embedded (the host document and section, a link to the passage); several candidates (each listed, "jason picks neither", the `Confirm` to bind one); not read (why, the command) |
| `AdoptionEvidenceRow` | band **Adoption** | `AdoptionEvidence` | a resolution (its number, date, vote); a minutes motion (the meeting, the item, the motion's words, mover and second, the vote); a certificate (signed or an unsigned blank date); the document's own statement; a board item's result; **a vendor proposal's approval, shown apart as implementation evidence, labeled "not an adoption"**; none, with the minutes searched (how many sets, which months, how many unread) |
| `ElementReviewTable` | band **Review** | `ProgramReview` | per element: found at a passage (link), not found (the search), unknown (document unread), for a person; a person's verdict beside it with the name and date; stale (the review's key changed: why); no review yet with the `Command` |
| `FindingRow` (built in the collection workspace) | band **Review**, below the table | a `Finding` with `basis` | the basis words (text, profile, store, today, law) in text; the three parts of a proposed decision kept apart (facts, the law recited, the application) |
| `DerivedObligations` | band **Duties and dates** | the proposed `Obligation` rows | each with its name, authority, recurrence, first due **computed** (labeled), evidence kinds; "proposed, not tracked" until a person adds it to the profile; an element with no recurrence shows its question instead of a row |
| `OwnerDutyRow` | band **Owners' part** | an `OwnerDuty` element | the owner's twin of a step (words, bearer, recurrence); the notice that tells owners (the notice row, its delivery state); "jason tracks the notice, not the owners' compliance"; no unit is named |
| `GapQuestionRow` (a `QuestionCard` preset) | `#/programs?view=gaps`, the page's Questions band, the onboarding session | one gap or question | a missing document; no act on record; a fact for the applicability condition; a presupposed row ("does the association need one? the law's words do not say"); an unresolved reference; an element for a person; each with what settles it and who may answer |
| `ReferenceRow` | band **References**; `#/programs?view=references` | `NamedReference` and its resolution | found / embedded / several / not found (**a finding, never a guess**) / not read; the sentence that mentions it, the document and section, its name as written, conditional or expected flags |
| `DetectionLead` | `#/programs?view=detected` and the confirmations queue | an `AdoptionReading` | a detected mandate: the sentence (a `Recitation` of the document's words), the shape word, the verb and object noun as read, the steps, the bearer; confirm, correct, or reject, each a signed record; a detection with an owner bearer shown as "an owner's program" |
| `ProposalFlow` | band **Proposal**, only while the row is a gap | the draft and the board path | stages as `StageSteps`: draft · counsel's reading where unclear · board item · notice (a rule on a listed subject: a reading) · the board's vote · minutes · adoption read; the stage being worked marked; each gate in words |
| `DraftPreview` | band **Proposal** | `program-draft` | the generated draft as a `Doc`, with `[BOARD CHOICE]` fields marked and counted, each recited requirement as a `Recitation`, "jason's proposed default, not adopted" on any proposed value; a draft that a base template does not yet cover ("no base template for this kind yet": the gap and the `Command`) |
| `AdoptionBrief` (a `DecisionBrief` preset) | band **Proposal**, and the agenda | the options | adopt · adopt with changes · decline, and how the duty is met otherwise · ask counsel; the facts; **no recommendation** (`BRIEF_FOOTER`); the footer says the vote is the board's, at an open meeting, in its own minutes |
| `LifecycleStrip` | `ProgramRow`, `ProgramPage` header | the six stages | mandate · written program · adopting act · implementation records · owner communication · review, one word each from the states in "The vocabulary"; a stage with no evidence is a word and its question, never blank; a stage that does not apply (no owner part) is "not required" with why; read as a list, never as a progress bar |
| `SourceTier` (a `Pill` preset) | `ProgramRow` | the row's `source` | statute · statute with a condition · declaration · **condition of approval** (the agency named; "whether it binds the association is not settled", with the `ReadingLabel`); a condition-of-approval row is grouped apart from the declaration's |
| `CadenceWord` (a `Pill` preset) | `ElementRecital`, `DerivedObligations` | an element's `cadence` | fixed ("every 3 months", the floor) · silent (**"the document sets none: the board's"**, with the proposed value labeled "proposed, not adopted" and its source) · event ("immediately": no number) · continuous ("at all times": verified by the walks, no date); an event or continuous element shows no due date and no "overdue" |
| `VerbClass` (a `Pill` preset) | `AdoptionEvidenceRow` | an act's verb class | adopted · delegated · directed · listed · reviewed · quoted (shown as **"quotes the section: not an act"**) · declined; both the act's date and the document's own date are shown, labeled, with neither chosen as the date |
| `LogEntryRow` | band **Implementation** | a `LogEntry` | dated entry (inspector, areas, condition, photo links counted not shown, the rows it satisfies); undated; "template reused: earlier entries are not in this copy"; "a copy of an earlier file"; "saved on DATE" (a Drive revision date, **never** "inspected on"); a payment shown apart as work, "not an inspection" |
| `ComponentRegisterTable` | band **Component register** (a maintenance-type program) | the `ComponentRow`s | a row per component with its cells, each cell carrying its source; a component another source lists and this one omits ("not in the study"); an unconfirmed read row labeled so; a `DataTable` with filters by building, cost center, responsible party |
| `AlignmentRow` | `ComponentRegisterTable`, band **Review** | an `AlignmentFinding` | each differing interval or life **side by side with its source and date** (as `Discrepancy`), the authority order beside them, "jason picks none"; an omission; a missing maintenance assumption (a question for the analyst) |
| `OwnerPartRow` | band **Owners' part** | the association's part toward owners | notify · remind · enforce, with the decision or its absence ("the board decided not to require certification, DATE" shown as a decision, not a gap) |
| `SubProgramRow` | band **The requirement**, the register | a parent's `parent` links | the sub-program's own standing word and a link; its steps are not restated; "counted once: one obligation per authority" |
| `MemberRoleList` | `ProgramCollectionLink`, `ProgramPage` | the program's named members | grouped by role (mandate, program, adopting act, record, vendor record, mail, owner-facing, reference, sub-program), each a document or passage with its read state; a role with no member ("no adopting act on file") is a line; a held-back document ("held: privileged, not shown") is a line with the reason and no content |
| `ScreenNotice` | the register, `ProgramPage` | the screening result | a Drive document held before indexing: privileged (by sender or phrase), no kind and unknown source, or **holding what looks like a credential** (never shown; "rotate it"); the minutes' range searched and what is not indexed ("not indexed before DATE") |
| `ProgramCollectionLink` | page header | `program-<key>` | the collection's summary page, its pack in the workbench, its files (links into the workspaces named above); not built where the collection has no files indexed |

## The vocabulary

Every state is a word from the code (`ProgramStanding`, `Shape`, `Standing`, `Answer`, `Source`), never color alone. Keep the words.

**Overall** (`ProgramStanding`; [../programs.md](../programs.md#vocabulary)):

| Word | Meaning | Shown beside it |
|---|---|---|
| missing | required, and no document is on file | the search made |
| drafted | a document is on file, no act on record | the document, and "no act on record" with the minutes searched |
| adopted | document and an act on record | the act, its date and where |
| implemented | adopted, and records show the steps on schedule | the standings |
| reviewed | a review as of a date, confirmed by a person | the day, "n of m elements found", the person |
| current | adopted, reviewed against the law in force today, inside its cycle, nothing overdue | each of the four with its date |
| stale | the law, the mandating provision, or the document changed since the last review | what changed |
| default applies | the statute's procedure applies because the association adopted none | the default's section, recited |
| optional | duties attach if adopted; adopting is the board's choice | the provision's words |
| presupposed | a provision speaks as if one exists | a question |

**The three answers** are as in [handoff-applicability-questions.md](handoff-applicability-questions.md#the-vocabulary): applies · does not apply · undetermined, the deciding or missing fact beside each. A conditional program row that is undetermined is a question, never missing.

**The shapes** (`Shape`): adopt · adopt and implement · optional · presupposed.

**The sources** (`Source`): statute · statute with a condition · declaration · condition of approval.

**The cadences** (`Cadence`): fixed · silent · event · continuous. A silent cadence is never filled with a default.

**The lifecycle's six stages**, each its own word: mandate (required · optional · presupposed · undetermined · counsel first), written program (not on file · on file · embedded · several candidates · not read), adopting act (no act on record · act on record · stated by the document itself · unsigned draft · adopted by a higher document), implementation records (the `Standing` words, or "no record kind shows it"), owner communication (not required · not on file · on file · a decision not to), review (none · reviewed · overdue · stale).

**An act's verb class**: adopted · delegated · directed · listed · reviewed · quoted · declined. Only "adopted" counts as an adoption; the others are shown for what they are.

**A log entry's states**: dated · undated · template reused · copy of an earlier file · saved on (a revision date). A payment is a row of its own: "work, not an inspection".

**An evidence's states** are in the `EvidenceTrio` row above. "No act on record" is not "not adopted", "not on file" is not "not done", and "several candidates" has no pick; each says what was searched.

**A review's element verdicts:** found at (a passage) · not found · unknown · for a person · and, by a person, **confirmed** with the name.

**Implementation:** the `obligations.Standing` words (done, done late, no evidence, upcoming, due soon, overdue, no store shows it, date not on record) unchanged.

## Data shapes

Made-up samples ("Example Village HOA", "Example Declaration 9.9", "CIV 9901"). The keys are the proposed payloads; the console reads the words as they are and derives nothing.

`GET /api/programs` (proposed; `program_catalog`, `program_detect`, `program_resolver`, over the profile and the stores):

```json
{
  "found": true, "community": "Example Village HOA", "asOf": "2026-10-05",
  "summary": {"required": 4, "notRequired": 1, "question": 2, "missing": 2, "drafted": 1, "adopted": 1, "stale": 0,
              "detected": 3, "unresolvedReferences": 2},
  "groups": [
    {"source": "statute", "rows": [
      {"key": "dispute-procedure", "title": "Procedure for resolving a dispute", "authority": ["CIV 9901"], "source": "statute", "shape": "adopt",
       "answer": {"answer": "applies", "describe": "always", "deciding": [], "missing": []},
       "standing": "default applies",
       "evidence": {"document": {"state": "not on file", "searched": "kinds: policy, operating rules; names: dispute resolution; index read 2026-10-04"},
                    "adoption": {"state": "none", "why": "default applies (CIV 9901(c))"},
                    "implementation": {"state": "no schedule"}},
       "next": "board item: adopt a procedure, or keep the statute's default", "question": ""}]},
    {"source": "statute-conditional", "rows": [
      {"key": "penalty-schedule", "title": "Schedule of monetary penalties", "authority": ["CIV 9902"], "source": "statute-conditional", "shape": "adopt",
       "answer": {"answer": "undetermined", "describe": "the association imposes monetary penalties",
                  "deciding": [], "missing": ["monetary_penalties"]},
       "standing": "presupposed", "evidence": null,
       "next": "answer the question", "question": "abdba3a040"}]},
    {"source": "condition-of-approval", "rows": [
      {"key": "coa-exterior-walk", "title": "Monthly exterior inspection", "authority": ["Example City permit PUD-0001, condition D1"], "source": "condition-of-approval", "shape": "adopt and implement",
       "caveat": "whether this condition binds the association, and which buildings it reaches, is for the agency or counsel", "standing": "presupposed",
       "answer": {"answer": "undetermined", "describe": "the approval names the applicant, not the association", "deciding": [], "missing": ["binds_association"]},
       "lifecycle": {"mandate": "counsel first", "program": "not on file", "act": "no act on record", "records": "no record kind shows it", "owners": "not required", "review": "none"}}]},
    {"source": "declaration", "rows": [
      {"key": "decl-9-9", "title": "Moisture inspection and prevention program", "authority": ["decl#9.9(a)"], "source": "declaration", "shape": "adopt and implement",
       "confirmedBy": "Jane Example", "confirmedOn": "2026-10-03",
       "answer": {"answer": "applies", "describe": "the document states no scope", "deciding": [], "missing": []},
       "standing": "drafted",
       "lifecycle": {"mandate": "required", "program": "on file", "act": "act on record", "records": "overdue", "owners": "not on file", "review": "none"},
       "evidence": {"document": {"state": "on file", "title": "Example moisture program (draft 2026)", "kind": "program", "docId": "lib:7c1e", "dates": {"written": "2026-03-02"}},
                    "adoption": {"state": "no act on record", "searched": "minutes 2025-01 to 2026-09: 19 sets, 2 not read"},
                    "implementation": {"state": "overdue", "count": 1, "of": 2}},
       "elements": 6, "ownerDuties": 6, "next": "adoption: put on the board's agenda", "question": ""}]}
  ],
  "caveats": ["A match is a lead. Not on file is not not done; no act on record is not not adopted. jason proposes and the board adopts."]
}
```

`GET /api/program?key=decl-9-9&as_of=2026-10-05` (proposed), one program's page:

```json
{
  "found": true, "key": "decl-9-9", "title": "Moisture inspection and prevention program", "asOf": "2026-10-05",
  "requirement": {
    "source": "declaration", "authority": ["decl#9.9(a)"], "permanentId": "decl@base/9.9(a)",
    "words": {"quote": "the Association shall adopt and implement a moisture inspection and prevention program which shall include the following steps:",
              "standing": "as amended; version in force 2026-10-05", "recital": "recited from the document"},
    "reading": {"label": "jason's reading", "text": "adopt and implement: both adopting and carrying out are asked", "whose": "jason", "confirmed": false},
    "elements": [
      {"key": "step-1", "kind": "step", "cite": "decl#9.9(a)(i)", "words": "Inspect the common areas not less frequently than quarterly ...", "bearer": "association",
       "everyMonths": 3, "record": "program_record", "read": "grammar", "confirmed": "Jane Example"},
      {"key": "step-2", "kind": "step", "cite": "decl#9.9(a)(iv)", "words": "Periodically inspect the irrigation ...", "bearer": "association",
       "everyMonths": 0, "cadence": "silent", "question": "the words say 'periodically': the board states how often",
       "proposed": {"everyMonths": 3, "source": "a study of the example reserve says every 3 months", "label": "proposed, not adopted"},
       "record": "program_record", "read": "grammar", "confirmed": null},
      {"key": "step-3", "kind": "step", "cite": "decl#9.9(a)(ii)", "words": "... immediately take appropriate corrective action ...", "bearer": "association",
       "everyMonths": 0, "cadence": "event", "question": "'immediately' has no number: a reading for counsel; the board may state a day count", "confirmed": null}],
    "ownerDuties": [{"key": "owner-step-1", "cite": "decl#9.9(b)(i)", "words": "Inspect the Unit not less frequently than quarterly ...", "bearer": "owner", "everyMonths": 3,
                     "notice": {"row": "annual-policy-statement", "delivery": "not sent this year"}}]
  },
  "document": {"state": "on file", "title": "Example moisture program (draft 2026)", "kind": "program", "docId": "lib:7c1e", "digest": "sha256:ab12", "read": "text layer"},
  "lifecycle": {"mandate": "required", "program": "on file", "act": "act on record", "records": "overdue", "owners": "not on file", "review": "none"},
  "adoption": [{"kind": "minutes motion", "verbClass": "adopted", "on": "2022-08-30", "documentDate": {"on": "2022-09-19", "label": "the document's own footer"},
                "quote": "approved the example program, consisting of the steps in 9.9(a)", "passage": "minutes, item 3", "labels": ["two dates, both kept"]},
               {"kind": "minutes entry", "verbClass": "quoted", "on": "2023-03-01", "counts": false, "label": "quotes the section: not an act"}],
  "notSearched": {"minutesIndexedFrom": "2024-01", "searchedFrom": "2022-01", "note": "minutes before 2024-01 are not indexed; read from the cache"},
  "leads": [{"kind": "vendor proposal approved", "meeting": "2026-02-17", "item": "4", "label": "not an adoption: implementation evidence"}],
  "members": [{"role": "mandate", "docId": "lib:decl", "title": "Example Declaration, 9.9", "read": "text layer"},
              {"role": "program", "docId": "drive:aa11", "title": "Example moisture program", "copies": 3, "read": "text layer"},
              {"role": "record", "docId": "drive:bb22", "title": "Example inspection worksheet", "read": "undated", "template": "reused"},
              {"role": "adopting act", "docId": "lib:min2022", "title": "Minutes, 2022-08-30", "read": "not indexed"},
              {"role": "adopting act", "held": true, "reason": "privileged: held, not shown"}],
  "log": [{"entry": "2022-09-12", "inspector": "Casey Sample", "areas": 14, "photos": 6, "satisfies": ["step-1"], "kind": "dated"},
          {"entry": null, "savedOn": "2024-12-02", "kind": "saved on", "label": "a revision date, not an inspection date"}],
  "register": {"rows": [{"component": "Roof drains", "quantity": 12, "location": "buildings A to D", "costCenter": "building maintenance", "reserve": {"life": 20, "study": "Example study 2025"},
                         "responsible": "association", "inspectionInterval": {"everyMonths": 6, "cadence": "fixed", "source": "study 2025"}, "assumption": "", "record": "log entry", "vendor": "",
                         "parent": null}],
               "alignment": [{"component": "Exterior paint", "values": [{"source": "the condition of approval", "interval": "at most 8 years", "kind": "floor"},
                                                                         {"source": "the study of 2024", "interval": "10 years"},
                                                                         {"source": "the board's sheet", "interval": "8 years"},
                                                                         {"source": "the owners' manual", "interval": "about 7 years"}],
                              "pick": "none"}]},
  "ownerPart": {"part": "notify", "decision": null},
  "subPrograms": [{"key": "pest-program", "standing": "adopted", "counted": "once"}],
  "review": {"asOf": "2026-10-05", "lens": "programs@3f9a", "stale": false,
             "elements": [{"key": "step-1", "result": "found at", "passage": "section 3", "basis": ["text"], "verdict": {"by": "Jane Example", "on": "2026-10-04", "word": "confirmed"}},
                          {"key": "step-2", "result": "not found", "searched": "anchors: irrigation, leaks", "basis": ["text"], "verdict": null}],
             "findings": [{"code": "frequency-not-longer", "message": "the document says every 6 months; the requirement says not less frequently than 3", "basis": ["text", "law"]}],
             "law": {"inForce": true, "recital": "recited on the day", "leads": 0}},
  "obligations": [{"name": "Common-area moisture inspection", "authority": "decl#9.9(a)(i)", "everyMonths": 3, "firstDue": {"day": "2026-12-01", "label": "computed: 3 months after the adoption date 2026-09-01"},
                   "standing": "no store shows it", "proposed": true}],
  "questions": [{"id": "9f2c01aa77", "text": "step-2: how often is 'periodically'? The board states it.", "state": "not filed"}],
  "proposal": {"stage": "draft", "draft": {"path": "data/drafts/programs/decl-9-9.md", "boardChoices": 4, "baseTemplate": "inspection-program"},
               "counsel": "the program also binds owners in their units: whether it is a rule on use of a separate interest is a question for counsel"},
  "collection": {"key": "program-decl-9-9", "files": 3, "summary": "generated 2026-10-04"},
  "caveats": ["A review decides nothing. A match is a lead. jason proposes; the board adopts."]
}
```

`GET /api/program-references?unresolved=1` (proposed):

```json
{"found": true, "references": [
  {"id": "r-31ac", "source": "decl", "section": "9.9(c)", "name": "meet and confer program", "noun": "program", "kindIfKnown": "policy",
   "conditional": false, "expected": false, "sentence": "... pursuant to the Association's ... program ...",
   "resolution": {"state": "not found", "searched": "kinds: policy, operating rules; names: dispute resolution, meet and confer; index 2026-10-04", "candidates": []}}],
 "caveats": ["Not found is a finding, not a guess."]}
```

`GET /api/program-gaps?as_of=` (proposed): the three groups and the questions, rows as in `programs`, plus `group: "statute" | "declaration" | "newer-law"`; a `newer-law` row carries the lead (the section, the change, its date) and the `Conflict` key where one exists.

A `FactValue`, a `Finding`, a `Recitation` keep their built shapes.

## What the design must keep

- **Recite first, label the reading** (principle 2). The requirement's words come from the shelf or the document through `Recitation`, with the version in force on the day and the caveat, before any row's standing. A shape, an element's recurrence, and "this program also binds owners" are readings, labeled whose ("jason's reading, unconfirmed" until a person confirms). Nothing is paraphrased as the rule.
- **Three evidences, three words.** Document, adoption, and implementation are separate, because each fails separately. Never one blended "compliant". The overall word is computed and shows its parts.
- **Not on file is not not done; no act on record is not not adopted** (principle 8). Each says what was searched, and the question that settles it.
- **A conditional row that is undetermined is a question**, not "missing" and not "not required". It links to the fact's `FactQuestionRow`.
- **A reference that cannot be resolved is a finding, never a guess.** Several candidates are all listed; jason picks none and the person binds one.
- **Six stages, six words** (`LifecycleStrip`). A program that is written and adopted but never inspected reads as that; no blended "compliant", and no progress bar.
- **A quotation is not an adoption.** An entry that only repeats the section is shown as "quotes the section: not an act". An act is shown with its verb class, and the document's date and the act's date side by side.
- **A silent cadence is the board's.** "Periodically" is never shown as a number. A proposed value is labeled "proposed, not adopted" with its source. An event or continuous element has no due date and is never "overdue".
- **A condition of approval is shown with its caveat**, in its own group, with "whether it binds the association is not settled"; it is never listed beside the declaration's rows as if it bound.
- **A saved date is not an inspection date; a payment is not an inspection; a copy is not a new inspection.** Each shown as what it is.
- **Alignment shows every value and picks none.** The sources' values for one component side by side with the authority order; no "use this one" control.
- **One obligation per authority.** A sub-program is a row the parent links; its steps are never restated.
- **A held document shows its reason and no content.** A privileged letter or a Doc that holds what looks like a credential is a line ("held: privileged"; "holds what looks like a credential: rotate it"), and the credential is never shown.
- **A match is a lead.** An element "found at" a passage is where to read, not that it is met. "Confirmed" is a person's, with the name and date.
- **A vendor's approval is not an adoption.** It is shown apart, labeled.
- **No approve control.** The console has no control that adopts a program. The vote is the board's, at an open meeting; the console shows the draft, the notice a rule on a listed subject needs (as a reading), the brief, and the `Command` to put it on the agenda. The **adoption** is read from the minutes, or a person records it with their name and the record that states it.
- **A decision brief never recommends.** `AdoptionBrief` lists options and facts; the footer is the built `BRIEF_FOOTER`.
- **Nothing is worked out on the client.** Standings, the applicability answer, the element results, the derived dates ("computed") come from the loaders. A first due day is labeled computed and never shown as the law's.
- **Owners' duties are the association's notice, not owners' compliance.** The page lists the owner's half, names the notice that tells owners, and shows nothing about any unit or owner (P0 law; no P4).
- **Every write is a `Confirm` in a named person's name** through the write guard, with its CLI equivalent shown (below). The draft write puts a file in `data/drafts` and publishes nothing.
- **Privacy by level** (principle 6). A requirement and the statutes are P0. A program's document, an adoption's minutes, and implementation records follow their documents' levels: a confidential document shows its title and state only outside the board's view, never its words. A person named in a confirmation is P1.

## Where it goes

Routes are proposed, consistent with [information-architecture.md](information-architecture.md#where-the-proposed-screens-go); none exists yet.

- **Governance → Programs** (proposed): `#/programs` (board-only, `owner: false`). Views as `Tabs`: **Register** (`ProgramRegister`), **Gaps** (the three groups and the questions), **Detected** (`DetectionLead`s waiting on a person), **References** (`ReferenceRow`s, unresolved first). Query: `?source=statute|statute-conditional|declaration`, `?as_of=YYYY-MM-DD`, `?view=`. A program: `#/programs/<key>` with bands **The requirement**, **The document**, **Adoption**, **Implementation** (the log), **Component register** (a maintenance-type program only), **Review**, **Duties and dates**, **Owners' part**, **Members**, **Questions**, **Proposal**; the `LifecycleStrip` sits in the header. The header's `Command` is `jason programs` (`--gaps`, `--as-of`).
- **The schedule and the dock's Deadlines** ([screens/schedule-and-duties.md](screens/schedule-and-duties.md)): a derived obligation a person added appears there as any obligation, with "from program KEY" linking back.
- **Board items** ([screens/board-items.md](screens/board-items.md)): a proposal becomes an item whose agenda text is the `AdoptionBrief`'s facts; the item links back to the program.
- **The confirmations queue** ([handoff-confirmations-queue.md](handoff-confirmations-queue.md)): a `DetectionLead` is a candidate reading there; confirming it adds the row.
- **The collection workspace and the pack workbench**: `ProgramCollectionLink` opens `#/collections/program-<key>` and the pack for the program.
- **The onboarding session** ([screens/onboarding.md](screens/onboarding.md)): each catalog row is an item ("does the association have one?"), rendered as `GapQuestionRow`.
- **The January law review**: the Gaps view as of the review's day, and its third group.

**Loaders to add** (names only; nothing built; each wraps a function proposed in [../programs.md](../programs.md) and derives no fact of its own):

| Loader | Route | Wraps | Notes |
|---|---|---|---|
| `programs` | `GET /api/programs?source=&as_of=` | `program_catalog.applicable`, `tasks.programs.standing` over the profile's rows, the stores | the register's shape above |
| `program` | `GET /api/program?key=&as_of=` | `tasks.programs.page`, `program_resolver`, `reviews` (the programs lens), `law_readings.recite` | the page's shape above |
| `program-gaps` | `GET /api/program-gaps?as_of=` | `tasks.programs.gaps` | three groups and the questions |
| `program-references` | `GET /api/program-references?unresolved=` | `program_resolver.resolve` over `references` | rows with their resolution |
| `program-detected` | `GET /api/program-detected` | `program_detect` readings, the duties' reviews | detected mandates and their state |
| `program-register` | `GET /api/program-register?key=` | the program's `ComponentRow`s and `AlignmentFinding`s | the component register and its alignment findings |
| `program-members` | `GET /api/program-members?key=` | `document_collections.of_program`, the screening's held list | members by role, with held-back documents as reasons |
| `program-log` | `GET /api/program-log?key=` | the log kind's `LogEntry` readings | dated, undated, reused, copy, saved on |
| `program-draft` | `GET /api/program-draft?key=` | the base template and the requirement's elements | the generated Markdown, the `[BOARD CHOICE]` count, the lint |

**Writes to add**, each a `Confirm` in the signed-in person's name, through the write guard, refused without a name:

| Write | Route | CLI equivalent | Stores |
|---|---|---|---|
| Confirm, correct, or reject a detected mandate | `POST /api/write/programs/mandate` `{id, status, by}` | `jason duties --documents KEY --review ID --status confirmed` and `jason programs --confirm ID --by NAME` | the duty's review; the profile's row on a person's apply |
| Bind a document as the program's | `POST /api/write/programs/bind` `{key, docId, by}` | `jason programs KEY --bind DOC --by NAME` | `data/programs/found.json` |
| Record an adoption act jason did not find | `POST /api/write/programs/adopted` `{key, kind, on, record, by}` | `jason programs KEY --adopted --minutes REF --on DATE --by NAME` | the same; refused without the record that states it |
| Confirm an element's verdict | `POST /api/write/programs/verdict` `{key, element, word, by}` | `jason programs KEY --verdict ELEMENT confirmed --by NAME` | the review store, beside the review |
| Generate the draft | `POST /api/write/programs/draft` `{key, by}` | `jason programs KEY --draft` | `data/drafts/programs/<key>.md` only |
| Put the draft on the board's agenda | `POST /api/write/programs/propose` `{key, by}` | `jason programs KEY --propose --by NAME` | the board register, through `jason board` |
| Answer a fact question | the built `POST /api/write/intake/<id>` | `jason intake --answer ID TEXT --by NAME` | the intake queue |

Applying a confirmed mandate to the specification (the profile's `program_requirements()`) is a terminal task by a person, as `jason intake --apply` is; the page shows it with the count and the `Command`.

## Accessibility

As [components.md](components.md#accessibility) and [content/patterns.md](content/patterns.md#accessibility-wcag-22-aa):

- **Keyboard.** `ProgramRow` opens in place as a `button` with `aria-expanded`; Escape closes it and returns focus. The register is a table with sortable column buttons; the `EvidenceTrio` is three cells, each a word. `ElementReviewTable`'s verdict is a `select` or radio group in a `fieldset` whose legend is the element's cite; the `Confirm` button follows it. `ProposalFlow` is an ordered list; the stage in progress carries `aria-current="step"`. Tabs follow the tabs pattern.
- **Screen reader.** The standing word is the accessible name of each pill, followed by its parts ("drafted: document on file; no act on record, 19 sets of minutes searched, 2 not read; implementation overdue, 1 of 2"). A recitation is a `figure` with a `blockquote` and a `figcaption` carrying the citation and version. "Computed" is read before a derived date. A `DetectionLead`'s shape word is announced with "jason's reading, unconfirmed". The recomputation after a write is a `role="status"` message ("Recorded by Jane Example. The program is now adopted."); a refused write is `role="alert"` tied by `aria-describedby`.
- **Phone layout (< 720 px).** The register's groups stack; each `ProgramRow` shows the title, the standing word, and the three evidences as three lines of text (never icons), with a disclosure for the rest. `ProgramPage`'s bands become a `select`; the `ElementReviewTable` becomes a list, one element per card, the verdict form at its end; `ProposalFlow` is a vertical list; `DraftPreview` scrolls in its own region and the `Confirm` is at the end, not sticky (2.4.11). Nothing scrolls sideways at 320 px.
- **Target size (2.5.8)**, **redundant entry (3.3.7)** (the signing name from "Signed in as"; only a second person's field starts empty), **timing (2.2.1)** (nothing times out; a half-typed verdict stays across a band change), **use of color (1.4.1)** (every state a word first; a glyph for undetermined is a question mark, for several candidates two marks, never a warning triangle).

## Decisions for the design

1. **One register or two.** The policy catalog's screen ([handoff-conversations-and-policies.md](handoff-conversations-and-policies.md)) lists policies jason configures; `#/programs` lists what the association must adopt. Decide whether one screen with a toggle serves both or two screens link to each other; the loaders differ and the words overlap (adopted, proposed, declined).
2. **The three evidences in a row.** A word each in three columns reads as a checklist; the risk is a column of "no act on record" looking like failure. Decide whether the row leads with the overall word and shows the three as one sentence, or as three small labeled values; keep the words and never a color alone.
3. **Where a detection waits.** A `DetectionLead` is a candidate reading in the confirmations queue and a tab here. Decide which is the home and which links, so a person is not asked twice.
4. **The owner's half.** Whether a program's owner-twin appears at all on the board's page, and how it reads without suggesting jason watches units ("the association tells owners; owners' compliance is not tracked").
5. **A first due day.** A "computed: 3 months after adoption" first date is a convenience; decide whether to show it, or show only "date not on record" until a person enters one, as the elevated-elements record does.
6. **The draft's weight.** A generated draft with many `[BOARD CHOICE]` fields can read as a finished policy. Decide how the preview shows how much is left to decide (a count, a progress line), and whether it may be read outside the board's view.
7. **Counsel first.** Where a row is `COUNSEL_FIRST` or a reading is unclear, decide whether `ProposalFlow` shows "ask counsel" as a stage with its own record or only a note in the brief.
8. **A program that an owner's duty twins.** Whether the two halves are one page or two (the association's program, each owner's), when the declaration states them in separate subdivisions.
9. **Newer-law rows.** The third group of the gap report reads like a conflict list. Decide how it links to `jason conflicts` and the conflicts screen without a third copy of the lead.

10. **Strip or sentence.** The `LifecycleStrip`'s six words in a row can read as a progress bar. Decide whether it is a list of labeled values, or a sentence ("written, adopted by a minute entry, not inspected, owners not told, never reviewed"); keep the words either way.
11. **Where the component register lives.** For a maintenance-type program it is the core; it could be a band of the program page or its own route (`#/programs/<key>/register`) with filters. Decide with the volume (dozens of components).
12. **Alignment's weight.** Four conflicting values for one component, with an authority order beside, is a dense row. Decide whether the register collapses an aligned component and opens a differing one by default.
13. **A held document's line.** Whether the board's view shows the title of a held privileged letter ("held: privileged") or only a count.

## Not part of this pass

- Detecting a mandate or reading a reference: the console reads the stored detections and shows them; `program_detect` and `program_resolver` are the pipeline's ([../programs.md](../programs.md)).
- Any control that adopts, approves, or declines a program: the board's vote is not a button, and no screen offers one.
- Sending a notice, a letter, or a draft to members; the 4360 notice's sending is its own flow ([screens/notices.md](screens/notices.md)).
- Applying a confirmed mandate to the profile's specification, and editing the profile or the private facts.
- Enforcing an owner's duty, inspecting a unit, or naming an owner or unit.
- Reading a program's adequacy; a review finds where the words are, and a person decides.
- An owner-facing version of any band.
- The previews: the design project's authored preview for each component follows the build; fixtures will be `ui/src/components/programregister.test.tsx` and its siblings, from the sample data above.
