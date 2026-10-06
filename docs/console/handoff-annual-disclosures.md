# Handoff: the annual disclosure packet

For the design pass on the screen that plans, checks, assembles, and hands off one year's annual disclosure packet: **what the law asks of it against what the definition includes, with every gap visible; the run that collects what only people have, freezes it, and makes the PDF; the checks on the PDF; and the send plan a person carries out.** Behavior, the model, and the words are settled in [../annual-disclosures.md](../annual-disclosures.md), which builds on [../document-templates.md](../document-templates.md) (the packet as a document made of embedded documents) and [../packets.md](../packets.md) (the splice that exists today).

**What exists today.** The packet is built from the terminal: `jason packet annual-disclosures --year N` plans (parts found or missing, tokens open, gaps), `--values` writes the year's values file, `--make-templates --yes` makes the template Docs, `--build --draft --yes` assembles one PDF per building with a bookmark per part and a manifest. The console has the calendar of recurring deadlines at `#/disclosures` (the board view) and `OwnerDisclosures` (the owner view: the annual disclosures every member receives, each with its window and the day the ledger shows it went out), and the Notices screen's one-notice record ([screens/notices.md](screens/notices.md), proposed whole). Nothing shows the packet itself, what the law asks of it, or what is missing.

**What this is not.**
- It is **not the approvals engine.** The build writes Docs and a PDF through the existing `packet --build --yes` (engine kind `google.doc`, R1, one person, [approval-workflow.md](approval-workflow.md)); the send is the Mailroom's own kind, run by a person from the terminal. Every write on this screen is a signed record in jason's own store, the way an intake answer is.
- It has **no approve control.** The board adopts the budget, the policies, and its statements by vote, recorded on the Decisions tab ([approval-workflow.md](approval-workflow.md#12-the-board-decides-by-vote)); this screen reads those adoptions and never records one. "Read by NAME" records that a person read a revision; it adopts nothing.
- It **never sends.** The page ends in files and a plan; the send is a command a person copies and runs (AGENTS.md, Boundaries).
- `jason-mcp` gets no write tool for it: an assistant can read the checklist, the parts, and the plan through the same functions.

**Neighbours, linked and not repeated:**
- [handoff-applicability-questions.md](handoff-applicability-questions.md): the three answers (applies, does not apply, undetermined) and the signed answer to a fact question; an element that does not apply is that answer, recorded there.
- [handoff-confirmations-queue.md](handoff-confirmations-queue.md): a person's confirmation of what jason proposed; a proposed source for a part is the fourth kind this design asks it to hold (decision 1).
- [handoff-programs.md](handoff-programs.md): the register of what the association must adopt. A policy part of the packet is a program's document; its `StandingWord` is that page's, and the packet reads it (the part is *adopted*, *drafted*, or *stale* by the program's evidence).
- [handoff-followups.md](handoff-followups.md): the campaign funnel for the owner-information request; the packet's own owner-information chain links there.
- [handoff-intake-review.md](handoff-intake-review.md): `PreflightCard` and the segment tree, used read-only on the built PDF and its attached scans.
- [handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md): `AsOfBanner`, and the law's words as of a day; the packet's passages are recited under it.
- [screens/notices.md](screens/notices.md), [screens/schedule-and-duties.md](screens/schedule-and-duties.md): where this screen sits ("Where it sits").

These components pair with what the console already has: `Recitation`, `ReadingLabel`, `QuestionCard`, `Confirm`, `Command`, `DataTable`, `Findings`, `Caveats`, `Card`, `Tabs`, `Doc`, `Embed`, `Pill`, `Stat`, `Checklist`, `StageSteps`, `DueDate`, `Clock`, `Evidence`, `CostLine`, `Money`, `Timeline`, `EmptyState`, and `RemoteView`. Build new parts only where the table says so.

## The idea in one line

A packet is a list of parts, each a document with its own source, day, and standing; beside the list is the law's checklist, each element showing the part that answers it or a gap line **exactly as it will print**; and a run that ends not in a send but in a PDF, a map of it, and a plan a person carries out.

## Where it sits

| Where | What | Why there |
|---|---|---|
| **Annual disclosures** (`#/disclosures`, the board view) | A new tab, **The packet**, at `#/disclosures/packet` (`/<year>`). The calendar's recurring deadlines stay the first tab | The disclosures members receive are already here ([schedule-and-duties.md](screens/schedule-and-duties.md)); the packet is how they are made. The calendar stays the association's deadlines; the packet's own clock is computed from the catalog and shown on the tab, not copied into the calendar |
| **Notices** (`#/notices?key=annual-budget-report-2099`) | Unchanged: the record of one notice from requirement to proof | The packet's send and its proof are those two notices' (`annual-budget-report-2099`, `annual-policy-statement-2099`: one packet, one text, two rows). This screen links to each; it does not show a second copy of the ledger. The notice's band 2, "The text as sent", is the packet PDF and its map |
| **Schedule and duties** (`#/duties`, the dock's Tasks) | A collection item whose role has an assignment appears in the role's list as an occurrence, with the same key | One place records it (this tab); the schedule shows it and its evidence points here. "Record done" there is not offered for a collection item: the value or the file is what completes it |
| **Applicability questions** (`#/applies`) | A fact an element turns on is asked there, and the element says "waiting on a person's answer" with the link | One queue for facts |
| **Confirmations** (`#/confirmations`) | A proposed source for a part (decision 1) | The same act as the others: a person confirms what jason proposed |
| **Board action items** (`#/actions`) | A gap only the board can settle (adopt the budget, adopt or re-adopt a policy, make a statement) arrives as a board item, with its meeting | The board decides by vote |
| **Owner view** (`OwnerDisclosures`) | **Nothing new at first** (decision 7) | The member's view stays what members receive and when |

## The components

| Component | Where it renders | Data | States to design |
|---|---|---|---|
| `PacketRun` | `#/disclosures/packet` (`/<year>`); the tab's page | `GET /api/annual-packet?year=` | the profile defines no annual packet (the command to see packets); no run yet for the year (the plan command, and the year's clock so a person can start); loading; planned; collecting; frozen; generated; read; send plan ready; sent (read from the logs); archived; a later revision exists ("revision 2 supersedes this one"); the catalog or a model table unavailable (the note and command, the rest still shown) |
| `DayTrio` (a `Card` over `AsOfBanner`) | the head of `PacketRun` | `days` | the **as-of day** (the day the run reads the law and the stores as of), the **dated day** (on the cover, inside the window), the **sent day** (from the ledger, never typed); each its own line with its source; the as-of day not yet frozen ("not frozen: today"); a freeze after the dated day ("frozen after the day it is dated"); a dated day outside the window ("outside the window the notice's row gives"); no dated day chosen ("date not on record": a question, never a guess) |
| `PacketStages` (a `StageSteps` preset) | under the head | `stages` | plan · collect · draft · freeze · generate · check · read · send plan · sent · archived, each a word and what it waits on; the stage being worked marked `aria-current="step"`; **sent** and **archived** are read from the logs ("a person sent it; the Mailroom's log shows 214 letters"), never marked by a click; a frozen run's earlier stages are shown as frozen with the revision |
| `RequirementChecklist` | the **Checklist** tab | `GET /api/annual-requirements?year=&state=` | grouped by requirement (the catalog's row, its statute, its window); the counts in a `Stat` strip (present, stale, missing, waiting, does not apply) with a table twin; filtered to one state; filtered to none ("Nothing is in that state."); the sources disagree (a **Findings** band: the model's table and the catalog differ on an item; a person reviews the join once); the profile has no packet; every element present ("Every element has a part, current. That is not a finding that the packet complies.") |
| `RequirementRow` | inside `RequirementChecklist` | one element | the element and its citation (opens a `Recitation` of the statute's words, as of the as-of day); `RequirementWord`; the part or parts that answer it as `Doc` chips; `applies` as `AnswerWord`; `DeclaredRead`; `GapPreview` for missing and waiting; the question and where it goes; a carried element nested under the statement that carries it |
| `RequirementWord` (a `Pill` preset) | `RequirementRow`, `PartRow`, the head | `state` | **present** · **present but stale** · **missing** · **does not apply** · **waiting**; each with its meaning in a hover card and in the row's text (never color alone) |
| `DeclaredRead` | `RequirementRow` | `declared`, `read` | declared by the definition (the part) beside what the output's text shows (the item found, or not found by the reader); agree; **declared, not found in the text**; **found, not declared**; **declared, not read** (a part with no text layer: "a person reads the page"); never resolved by the page; the pattern that found it is named, since a miss is the reader's |
| `GapPreview` | `RequirementRow`; the **Gaps** list | `gap` | the sentence as it will print, in a boxed block with a label ("As printed in a draft: on its own page, in the contents, and in the part map. A final build refuses while this stands."); missing; waiting (who was asked, when); stale (what changed, with the old and the new as two `Recitation`s for a statute's passage); no gap (nothing prints) |
| `PacketOrder` | the **Parts** tab | `GET /api/annual-parts?year=` | the parts as a **tree** in the order they print: nested generated parts expand; each `PacketPartRow`; the contents page as it will print beside it (`ContentsPreview`); per-variant differences (a part that differs between variants says which); no parts (the definition is empty) |
| `PacketPartRow` | `PacketOrder` | one part | id path, title, kind (nested definition, stored file, form, passage, computed), `BasisWord`, `PartStanding`, `RequirementWord` for freshness, the as-of with its rule in words, the source as a `Doc` chip, the hash's first twelve characters, pages (first to last, in each variant) and the page choice, the elements it answers as chips; a **stored** part says "attached as it is: not re-drawn"; a **nested** part shows its own gaps lifted; a **passage** shows the digest read against the digest now; a **computed** part shows the inputs it read |
| `BasisWord` (a `Pill` preset) | `PacketPartRow` | `basis` | statute · governing document · board's choice · convenience; the checklist's "included, no element names it" band lists the last two |
| `PartStanding` (a `Pill` preset) | `PacketPartRow` | `standing` | adopted (the adoption day, the minutes or decision) · draft · recorded · issued (the period) · computed · statute · unknown; "stale" is a separate word from `RequirementWord`, shown beside |
| `ContentsPreview` | `PacketOrder` | `contents` | the contents page and the bookmark tree as they will be, from the part map; page numbers "after the build" until a build gives them; a part with a gap shows its gap line in its place |
| `CollectList` | the **Collect** tab | `GET /api/annual-collect?year=` | by who it is asked of (a role, from the schedule's assignments, labeled "proposed" where the board has not adopted it); each `CollectItemRow`; none to collect; all received; an item late for the window ("must arrive by Apr 20 to leave the days the next stage needs") |
| `CollectItemRow` | `CollectList` | one item | what it is and the elements it answers, who it is asked of, asked on, due by (`DueDate`, computed and labeled), state (not asked · asked · received, awaiting a person's confirmation · confirmed · waived by NAME, with the reason), the value or the file (a `Doc`), who entered it and from what source; a board statement entered is labeled "entered by NAME; not yet adopted" or "adopted at the meeting of DATE (recorded by NAME)"; the entry form behind `Confirm` |
| `StandingValueRow` | `CollectList` | a standing value | the value, its layer, when it was last confirmed, and "Still true for fiscal year 2099?" behind `Confirm`; never confirmed this year (the row is stale until it is); changed (a new value entered, with the old kept) |
| `PartToConfirm` (a `QuestionCard` preset) | `PacketRun`'s **Confirm** band; the confirmations queue if decision 1 says so | `confirm[]` | jason's proposed source and pages for a part (the newest matching file, the pages its rule kept), labeled "jason's proposal"; the file as a `Doc`; several candidates ("jason picks neither"); the person confirms this file and these pages, or names another; a part whose source changed after it was confirmed |
| `ClockStrip` | the head, and the **Send plan** tab | `clock` | the fiscal year's end; the window's first and last day (from the catalog's row, recited as the row's clock in words with its citation); the owner-information answers date; the dated day inside it; stricter clocks from the governing documents with the clause that makes them, labeled; "How a court counts a period ending on a weekend or holiday is for counsel" |
| `FrozenRun` (a `Card`) | the **Record** tab | `GET /api/annual-record?year=` | not frozen; frozen (the days, the revision, how many values and parts, every part's address and hash, the base templates' versions, the passages' digests, the layout, the checklist as it stood, the tool's version); superseded by a revision (the reason, who, when); `RevisionLine` for each |
| `QaResult` | the **Checks** tab | `GET /api/annual-checks?year=` | not run; running; cross-part checks as `CrossCheckRow`s; the segment check as `SegmentCompare`; each attached scan's `PreflightCard`; the footer-band findings; the review's findings (`Findings`); each check's age and the command that runs it again |
| `CrossCheckRow` | `QaResult` | one relation | the two values side by side with the source of each (the assessment in the budget and in the disclosure summary; the reserve transfer and the study's plan; the insurance summary and the declarations; the unit count and the recipients); agree; differ (neither is chosen); one side not on file |
| `SegmentCompare` | `QaResult` | `segments` | the part map beside `jason segments` of the PDF; each part as **agree**, **inside** (an exhibit inside an attached file), **missed** (with the cues the page has), or **contradiction** (a finding about the segmenter, the footer, or the splice, shown first); "not run (the PDF is not built)"; the segmenter's measured recall in a caveat |
| `ReadThroughList` | the **Read-through** tab | `GET /api/annual-read?year=` | the seven groups in the order a reader needs them (gaps and stale parts; the board's statements; each standing value; the cross-part checks; the checks' findings; each statutory part by page; the clock); each line a link to where it is; `ReadRecord` at the foot |
| `ReadRecord` (a `Confirm` preset) | the foot of `ReadThroughList` | `read` | not read; read by NAME on DAY, revision N; **stale**: the packet changed after it was read ("Read revision 1; this is revision 2"); the words say it records a reading and adopts nothing |
| `SendPlanTable` | the **Send plan** tab | `GET /api/annual-send-plan?year=` | one row per variant and channel: the recipients' count (counts only), the pages billed per letter, the estimate (`CostLine`, "charged to the association", the pricing's date), the window's last day; the order (email first, mail after, with the lesson it comes from); the commands as `Command` blocks (the dry run, the batches, the sync); **no send control**; a variant with no recipients; a count that differs from the unit count in the packet (a finding); a packet longer than a letter carries (the board's choice named: decision 3) |
| `ProofLink` | the **Send plan** and **Record** tabs | `proof` | the two notices (`annual-budget-report-2099`, `annual-policy-statement-2099`): each as a link to `#/notices?key=` with its standing word from the ledger ("delivered", "sent", "file", "none on record"); never a second ledger |

### The words

Every state is a word the code uses, or one defined in [../annual-disclosures.md](../annual-disclosures.md), and the color only repeats it.

| Word | Meaning |
|---|---|
| present | a part answers the element, its source is on file, it is current, it has the standing the element needs, no token in it is open. **Not** "compliant" |
| present but stale | a part answers it but fails its as-of rule: the term in force is not on file, the policy's version in force is not the one in the part, the statute's words changed since the passage was cut, or a standing value was not confirmed this run |
| missing | no part answers it, or its source is not on file for the year. "Not on file is not not done": the row says what was searched |
| does not apply | the row's condition is answered *does not apply* by a recorded fact, with who and when; the row stays |
| waiting | a value or a decision only a person can give has not arrived, or the part waits on an event (the adoption, a renewal); the row says who and what |
| declared, read | the definition says a part answers it, and the output's text shows it |
| declared, not found in the text | the part is declared, and the reader did not find the item: a miss of the reader's pattern, or the part's words |
| found, not declared | the reader found an item no part declares |
| declared, not read | a part with no text layer; a person reads it |
| adopted · draft · recorded · issued · computed · statute · unknown | a part's standing: what its source says it is |
| statute · governing document · board's choice · convenience | a part's basis |
| agree · inside · missed · contradiction | the segment check's four results |
| not frozen · frozen · superseded | the run's record |
| read by NAME on DAY | a person read revision N; adopts nothing |
| sent | read from the Mailroom's log or the batches: never marked by a click |

"Approve", "approved", "compliant", "complete", and "sufficient" appear on no control and in no state here. "Final" is a build's name for "the checks passed and no required element is missing, waiting, or stale", and the page says so beside it. A requirement's `applies` words are `AnswerWord`'s. A reading of what the words mean is a `ReadingLabel`: "jason's reading", never the statute's.

## Data shapes

Made-up: "Example Village HOA", "CIV 9901", "Building A", people "Jane Example". Section numbers are placeholders and their words are left out of the samples: on the screen the words come from `jason cite` and the shelf, never from a sample. The window's days are those the catalog row carries.

`GET /api/annual-packet?year=2099` (proposed):

```json
{
  "found": true, "community": "Example Village HOA", "year": 2099, "packet": "annual-disclosures",
  "title": "Annual Budget Report and Annual Policy Statement", "revision": 1,
  "days": {"asOf": "2099-03-02", "asOfFrozen": false, "dated": "2099-05-15", "datedWhy": "chosen by Jane Example, 2099-02-20",
           "sent": null, "fiscalYearEnd": "2099-06-30",
           "window": {"first": "2099-04-01", "last": "2099-05-31", "requirement": "annual-budget-report", "inside": true}},
  "stages": [
    {"key": "plan", "state": "done", "at": "2099-02-20"}, {"key": "collect", "state": "now", "waitingOn": "4 items"},
    {"key": "draft", "state": "later"}, {"key": "freeze", "state": "later"}, {"key": "generate", "state": "later"},
    {"key": "check", "state": "later"}, {"key": "read", "state": "later"}, {"key": "sendPlan", "state": "later"},
    {"key": "sent", "state": "later", "from": "the Mailroom's log and the batches"}, {"key": "archived", "state": "later"}],
  "counts": {"elements": 27, "present": 19, "stale": 2, "missing": 1, "waiting": 4, "doesNotApply": 1, "findings": 2},
  "notices": ["annual-budget-report-2099", "annual-policy-statement-2099"],
  "unavailable": [],
  "caveats": ["A clean checklist says each element has a part, current, or a visible gap. It is not a finding that the packet complies.",
              "How a court counts a period ending on a weekend or holiday is for counsel."]
}
```

`GET /api/annual-requirements?year=2099&state=missing` (proposed): `rows` grouped by requirement; the same row for every state.

```json
{
  "found": true, "year": 2099, "asOf": "2099-03-02",
  "sourceFindings": [
    {"kind": "table-differs", "text": "The policy statement's item table has 11 entries; the module says items (1) through (12); the catalog's content list names an electronic voting item, if used.",
     "needs": "a person reviews the join once", "command": "jason packet annual-disclosures --year 2099 --check --state missing"}],
  "groups": [
    {"requirement": "annual-policy-statement", "title": "Annual policy statement", "statute": "CIV 9902",
     "clock": "30 to 90 days before the end of the fiscal year", "rows": [
      {"id": "CIV 9902(a)(3)", "element": "the designated posting location for general notices, if any",
       "applies": {"answer": "applies", "turnsOn": []},
       "state": "waiting", "parts": ["policy-statement"], "why": "the posting location is a standing value not confirmed for 2099",
       "declared": {"part": "policy-statement"}, "read": {"found": null, "why": "the output is not built"},
       "gap": "[Waiting: Example item. Required by CIV 9902(a)(3): the posting location has not been confirmed for fiscal year 2099. Asked of the manager on 2099-02-20.]",
       "question": {"goesTo": "collect", "id": "c-07"}}]},
    {"requirement": "annual-budget-report", "title": "Annual budget report", "statute": "CIV 9901",
     "rows": [
      {"id": "CIV 9901(b)(2)", "element": "the example reserve summary",
       "applies": {"answer": "applies"}, "state": "missing", "parts": [], "why": "no part declares it, and the library has no file at the path searched",
       "searched": "library path 'Example Folder/2099/Example Reserve Summary*'; index read 2099-03-01",
       "gap": "[Missing: Example reserve summary. Required by CIV 9901(b)(2): not on file for fiscal year 2099. Searched: library path 'Example Folder/2099/Example Reserve Summary*', index read 2099-03-01.]",
       "question": {"goesTo": "collect", "id": "c-02"}}]}
  ]
}
```

`GET /api/annual-parts?year=2099` (proposed): the part map as a tree, the same document `part-map.json` holds.

```json
{
  "found": true, "year": 2099, "variants": ["Building A", "Building B"],
  "parts": [
    {"id": "cover", "title": "Cover", "kind": "definition", "basis": "convenience", "standing": "computed", "freshness": "current",
     "asOf": "2099-03-02", "rule": "fiscal-year", "answers": [], "pages": null, "gap": false},
    {"id": "budget-report", "title": "Annual Budget Report", "kind": "definition", "basis": "statute", "standing": "draft",
     "freshness": "current", "asOf": "2099-03-02", "rule": "fiscal-year", "answers": ["annual-budget-report"],
     "children": [
       {"id": "budget-report/insurance-summary", "title": "Insurance summary", "kind": "definition", "basis": "statute",
        "standing": "computed", "freshness": "stale", "rule": "term-in-force",
        "why": "the term covering 2098-07-01 is not on file; the newest is the term before",
        "inputs": ["policy records read 2099-03-01"], "answers": ["CIV 9901(b)(9)"], "gap": true}]},
    {"id": "declarations", "title": "Master policy declarations", "kind": "stored", "basis": "statute", "standing": "issued",
     "freshness": "current", "asOf": "2098-07-01", "rule": "term-in-force",
     "source": {"doc": {"ref": "library:4001", "name": "declarations-example.pdf", "level": "P2"}, "sha256": "9e2f4b7c1d0a5e33…",
                "pages": "3-5", "pageCount": 3, "rule": "keep: the policy period and limits headings"},
     "answers": ["CIV 9901(b)(9)"], "textLayer": true, "pages": {"Building A": [14, 16], "Building B": [14, 16]}, "gap": false},
    {"id": "fha-statement", "title": "FHA statement", "kind": "definition", "basis": "statute", "standing": "statute",
     "freshness": "current", "rule": "statute-digest", "digestRead": "1122334455aa", "digestNow": "1122334455aa",
     "ownSheet": true, "answers": ["CIV 9901(b)(10)"], "pages": {"Building A": [19, 20]}}],
  "contents": [{"title": "Annual Budget Report", "page": 2, "children": [{"title": "Insurance summary", "page": 6}]}]
}
```

`GET /api/annual-collect?year=2099` (proposed):

```json
{
  "found": true, "year": 2099,
  "items": [
    {"id": "c-02", "what": "the example reserve summary pages", "answers": ["CIV 9901(b)(2)", "CIV 9901(b)(3)"],
     "from": {"role": "treasurer", "assignment": "proposed, not adopted"}, "askedOn": "2099-02-20", "dueBy": "2099-04-20",
     "dueWhy": "the last day it can arrive and leave the days the next stages need", "state": "asked",
     "value": null, "file": null, "enteredBy": null, "source": null},
    {"id": "c-05", "what": "the board's statement on example matters", "answers": ["CIV 9901(b)(4)"],
     "from": {"role": "secretary", "assignment": "adopted 2099-01-10"}, "state": "received",
     "value": "(the words as entered)", "enteredBy": "Jane Example", "enteredOn": "2099-03-01",
     "boardLabel": "entered by Jane Example; not yet adopted", "adoption": null}],
  "standing": [
    {"key": "POSTING_LOCATION", "layer": "profile", "value": "(the posting location)", "lastConfirmed": "2098-03-10",
     "confirmedThisYear": false, "stillTrueAsk": "Still true for fiscal year 2099?"}],
  "confirm": [
    {"part": "declarations", "proposal": {"doc": {"ref": "library:4001", "name": "declarations-example.pdf"}, "pages": "3-5",
      "why": "the newest file whose path matches; the pages whose text names the policy period and limits"},
     "candidates": 1, "state": "waiting"}]
}
```

`GET /api/annual-checks?year=2099` (proposed): `{crossChecks: [{id, what, left: {value, source}, right: {value, source}, state: "agree|differ|one side not on file"}], segments: {run: "2099-03-04", file: "building-a.pdf", rows: [{part, expectedPage, found: "agree|inside|missed|contradiction", cues: []}], recall: "dev 0.84, held-out 0.78"}, preflight: [{part, report: PreflightCard}], footerBand: [{page, ink: true}], review: {task: "annual-disclosures", findings: []}, ranAt}`.

`GET /api/annual-send-plan?year=2099` (proposed):

```json
{
  "found": true, "year": 2099, "frozen": false, "revision": 1,
  "clock": {"fiscalYearEnd": "2099-06-30", "window": {"first": "2099-04-01", "last": "2099-05-31"}, "dated": "2099-05-15",
            "answersEnteredBy": "2099-04-15", "stricter": []},
  "rows": [
    {"variant": "Building A", "channel": "email", "recipients": 31, "pagesBilled": null, "estimateCents": null,
     "file": "building-a.pdf", "sha256": "9e2f4b7c1d0a5e33…"},
    {"variant": "Building A", "channel": "mail", "recipients": 17, "pagesBilled": 41, "estimateCents": 30960,
     "priceSource": "payhoa.pricing, 2098-10-01", "estimated": true, "chargedTo": "the association"},
    {"variant": "Building A", "channel": "secondary copies", "recipients": 3}],
  "order": "email first, mail after: a letter cannot be recalled after minutes; an email can be corrected (the owner-information cycle's lesson)",
  "commands": ["jason mailroom --pdf --units A --notice annual-budget-report-2099", "jason notices annual-budget-report-2099 --sync"],
  "findings": ["The recipient total (51) differs from the unit count in the packet (50): a person reads the delivery plan."],
  "proof": [{"notice": "annual-budget-report-2099", "standing": "none on record", "route": "#/notices?key=annual-budget-report-2099"}]
}
```

`GET /api/annual-record?year=2099` (proposed): `{found, frozen: {at, by, asOf, dated, revision, values: 41, parts: [{id, address, sha256, pages}], templates: [{key, version, hash}], passages: [{citation, digest}], layout, tool}, pdf: {file, sha256, pages}, checklist: {...counts}, revisions: [{n, reason, by, at}], read: {by, on, revision} | null, archived: {record, by, at} | null}`.

**Writes** are `POST /api/write/annual/...` behind the write guard (`X-Jason-Token`); each takes `by`:

| Write | Body | Records |
|---|---|---|
| `annual/collect/<id>` | `{"by": "Jane Example", "value": "…" \| "file": "library:4002", "source": "…"}` | the item received, with who, when, and the source and the file's digest |
| `annual/collect/<id>/waive` | `{"by": "...", "reason": "…"}` | a waiver with a reason: the element then reads *waiting* until a person gives it, or *does not apply* through the applicability answer; a waiver is never *present* |
| `annual/standing/<key>` | `{"by": "...", "stillTrue": true}` or `{"value": "…"}` | the reconfirmation, or a new value with the old kept |
| `annual/part/<id>` | `{"by": "...", "file": "library:4001", "pages": "3-5"}` | the confirmed source and pages; the digest of the file as the person saw it |
| `annual/freeze` | `{"by": "...", "asOf": "2099-03-02", "dated": "2099-05-15"}` | `run.json` (the days, the values, every part's address and digest, the checklist as it stood); refused while a required element is missing, waiting, or stale unless `draft: true`, which freezes a draft marked so |
| `annual/read` | `{"by": "...", "revision": 1}` | the reading, refused for a revision that is not the current one |
| `annual/archive` | `{"by": "..."}` | after the sent day shows in the ledger: the sent packet, its map and hashes, the plan, and the link to the notice's proof, filed as the association record the profile pins; refused with no sent day on record |

## What the design must keep

- **Recite first; label the reading** (principle 2). A statute's words in a row are a `Recitation` (words, version in force on the as-of day, caveat, digest). A part's passage is that same recital. What the words are read to ask is a `ReadingLabel` ("jason's reading").
- **A gap is shown where it prints.** The sentence in `GapPreview` is the sentence the draft prints, from the same function; the page never words a gap its own way.
- **A miss stays a miss; none on record is not none given.** A missing part says what was searched; a missing ledger entry says "none on record", with the pairing sentence at least once on the page ([content/style.md](content/style.md)).
- **jason proposes; a person acts.** A proposed source is `PartToConfirm`; a board statement is entered by a person and shown as theirs; a standing value is asked again; nothing is chosen by the page. jason never writes a board's statement.
- **The board adopts by vote.** An adopted budget, policy, or statement shows its adoption read from the decision record or the minutes; where there is none, "no act on record" with the minutes searched. The page has no control that adopts, and never says "approved" for a click.
- **No mailing.** The send plan is a table and commands to copy. No button on the page starts a send, a batch, or a cancel; the page reads the logs afterward.
- **The checklist never says "complies".** It says each element has a part, current, or a visible gap, and its caveat says that is not a finding of compliance.
- **Declared and read are shown together and never reconciled by the page.** A disagreement is a finding with both sides.
- **A frozen run is not edited.** A change is a revision with a reason; the first stays.
- **Only stored words.** A statute's words come from the shelf; a governing document's from the stored file; the member-facing summary's words are `{QUOTE}` passages.
- **Privacy by level** (principle 6):

  | What | Level | Shown |
  |---|---|---|
  | The checklist's requirement, citation, and the statute's words | P0 | always |
  | The part tree, titles, kinds, bases, standings, the contents | P1 | roster people |
  | A stored part's file | the file's own level | a P2 or P3 source (a confidential report, an insurer's file with a policy number) by kind and title only outside the level that opens it; the page opens at the level of its most restricted source |
  | Values entered, the board's statements as entered, the budget's figures before they are delivered | P1 | roster people; a draft's values never leave the console's own machine until the packet is sent |
  | A statement not yet adopted | P1 | labeled "not yet adopted" |
  | The send plan's counts, the pages, the cost | P1 | counts only: no name, address, unit, or id appears; the Mailroom's own plan holds the ids at its own level |
  | The segment check, the preflight, the footer findings | P1 | roster people; a scan's text opens at the scan's level |
  | The read-through record | P1 | roster people |
  | The sent packet after the sent day | P0 for members (they hold it) | a member sees only its part titles and what each answers, once decision 7 says so |

  The tab is board-only (the manager, an officer, an administrator). Counsel sees the checklist and the clock on grant. The owner view shows nothing here at first.
- **No color-only meaning.** Every state above is a word; `RequirementChecklist` has a table twin; a stale row carries "stale" in its own column; a gap carries its sentence.
- **Nothing is written without a person** (principle 4). Every write is a `Confirm` that spells out what is recorded and in whose name, behind the write guard, with its CLI equivalent named; a write with no `by` is 400; while someone is signed in, `by` is that person.
- **Nothing is worked out on the client.** The loader returns the states, the windows, the dates, the counts, and the estimates; the page renders them. A day is never counted in the browser.

## Where it goes

- **Annual disclosures → The packet**: route `#/disclosures/packet`, with `/<year>`; the page's tabs are Checklist, Parts, Collect, Checks, Read-through, Send plan, and Record (`?tab=`). A row opens in place: `?element=` for a `RequirementRow`, `?part=` for a `PacketPartRow`. A URL carries a year, a key, or an id, never a name ([security-and-privacy.md](security-and-privacy.md#urls)). A count in the nav item for the Annual disclosures screen ("3 waiting") joins the existing screen's count.
- **`#/digest`**, under "Waiting on a person" ([today.md](screens/today.md)): one line from the loader ("The 2099 packet has 4 elements waiting and 1 missing; the window opens Apr 1"), linking to the Checklist tab.
- **`#/notices`**: the two notices' record, unchanged, linked from `ProofLink`.

**Loaders and writes to add** (all proposed; a loader wraps a function that exists, except where marked "to write"):

| Name | Function behind it | Reads | Writes |
|---|---|---|---|
| `annual-packet` | `jason.tasks.annual_packet:run_header` (to write) over `community.packet(...)`, the run store, `notice_catalog.requirement`, `Timing.window`, `schedule` | disk only | — |
| `annual-requirements` | `jason.community.annual_packet:checklist` (to write, pure) over the `Packet`, `notice_catalog.REQUIREMENTS` (annual rows and `carried_by`), `financial_annual.BUDGET_REPORT_ITEMS` and `POLICY_STATEMENT_ITEMS`, `notice_catalog.applicable`, the parts' as-of rules, and, once built, `AnnualReportModel.parse` of the output's text | disk only | — |
| `annual-parts` | `jason.tasks.packets.plan` and `resolve` over the profile's packet; the definition builder (phase 2 of [document-templates.md](../document-templates.md)); `part-map.json` | disk only | — |
| `annual-collect` | the run's `collect.json` and `values.json`; `jason.tasks.packets.values_for`; `schedule_assignments` for roles | disk only | — |
| `annual-checks` | `jason.community.annual_packet:cross_checks` (to write), the stored segmentation (`tasks.segments`), the stored preflight report, the review's stored findings | disk only (the checks run by their commands, never on a request) | — |
| `annual-send-plan` | `tasks.notice_delivery` (counts), `Timing.window`, `payhoa.pricing`, the mailroom's `sent.jsonl` | disk only (the owners' tags from the stored catalog) | — |
| `annual-record` | `run.json`, `manifest.json`, `read-through.json`, the notice ledger | disk only | — |
| write `annual/collect`, `annual/collect/waive`, `annual/standing`, `annual/part`, `annual/freeze`, `annual/read`, `annual/archive` | `jason.web.extra.annual:write_*` (to write) over the run store under the store lock | — | the run's own files under `data/packets/<packet>-<year>/`, jason's own store; a Doc or a PDF only by the build's own command |

**The commands** (flags on `jason packet`, each free in `src/jason/commands/packet.py` today; the build stays `--build`):

| Console | CLI |
|---|---|
| The Checklist tab | `jason packet annual-disclosures --year 2099 --check [--state missing\|waiting\|stale]` |
| The Parts tab, and the draft's plan | `jason packet annual-disclosures --year 2099` (exists), `--values` (exists) |
| Collect, give a value or a file | `--collect` (list), `--give ID --value TEXT` or `--file ADDRESS --source TEXT --by NAME` |
| Reconfirm a standing value | `--standing KEY --still-true --by NAME` |
| Confirm a proposed source | `--confirm-part ID --file ADDRESS --pages 3-5 --by NAME` |
| Freeze | `--freeze --asof DAY --dated DAY --by NAME` |
| Build a draft or the final | `--build [--draft] --yes` (exists) |
| The checks | `--qa` (the cross-part checks, `jason segments --file`, `jason preflight`, the footer band; the review: `jason review annual-disclosures`) |
| The read-through record | `--read --revision N --by NAME` |
| The send plan | `--send-plan` (prints; sends nothing) |
| The archive | `--archive --by NAME` (refused with no sent day in the ledger) |

## Accessibility

As [components.md](components.md#accessibility), with these particulars.

- **The checklist is a real table** (`DataTable`): element, citation, state, part, as-of, and what it needs, each a column with text; a caption ("The 2099 packet's requirements, by statement"); groups are `<tbody>` sections with a row-header; sort and the sort announced; filters in a labelled group with a polite live region ("5 of 27 elements"). A row is a disclosure (a button with `aria-expanded`) that opens its recital, its parts, `DeclaredRead`, and `GapPreview`; no grid roles.
- **The part tree is a tree only where it nests.** Part rows are a nested list (`ul`) with each level labelled; a `button` expands a nested part; no `role="treegrid"`. The contents page beside it is a list of links with page numbers in text.
- **`GapPreview` is a `<blockquote>` with a heading** ("As printed"), so a screen reader hears it as the sentence the page quotes, and its label says whether it prints in a draft or a final.
- **`RequirementWord` and `PartStanding` are text** with the meaning in an `aria-describedby`; the five states are never distinguished by color or icon alone.
- **`DeclaredRead` is a two-column description list** with a visible label for each side; a disagreement is announced in the row's status text.
- **Every write is a `Confirm`**: "Give the reserve summary as Jane Example: records that Jane Example gave file declarations-example.pdf (digest 9e2f4b7c1d0a, pages 3 to 5) for 'the example reserve summary' on Mar 2, 2099. This adopts nothing." The result in `role="status"`, in place; focus stays on the row.
- **The clock strip is a description list**, each day a `<time datetime>` with a text reading ("May 31, 2099: the last day in the window"); the window's range is "from Apr 1 through May 31", never a dash ([content/style.md](content/style.md)).
- **The send plan has no send control**, so there is nothing to mis-tap; each `Command` has a visible copy button and a text label.
- **A long recital** (a statute's passage) wraps inside the page, never sideways; "Go to the words that answer" moves focus to the marked words.
- **Nothing times out.** A half-typed value or reason stays until the person leaves the page; the store holds nothing until `Confirm`.
- **Shortcuts** as [patterns.md](content/patterns.md#keyboard-use): `j`/`k` between rows, `?` lists them; targets are 24 by 24 CSS pixels or spaced.

### The phone layout (under 720 px)

- The tabs become a "Go to" select inside the page; the head stacks: the three days as three lines, then the stages as a list (the one being worked first, "Now: collect, waiting on 4 items"), never a progress bar.
- The checklist's rows become cards: the element first, then the state word and its part on one line, then the gap sentence in full. The counts are a list of five lines with the twin table beneath. A stale card says "stale" in words on its first line.
- A part is a card: title, basis and standing words, source chip, pages; a nested part expands under it, indented one step only.
- `GapPreview` is the full width of the card and never truncated.
- A collect item is a card with the entry form below it, the field and its label stacked, `Confirm` at the foot.
- `SegmentCompare` stacks: the part map's list, then the segmenter's, each part a pair of lines (what the map says; what the segmenter found), never two columns.
- The send plan's rows are cards with the count, the estimate, and the window's last day as a list.
- `ReadRecord` is at the foot of the read-through list, not sticky.
- "Go to" replaces the nav as `ConsoleShell` does; the dock's drawers still pin at 1200 px and float below.

## Decisions for the design

Settled by the axioms, and why:

- **The page never sends and never adopts.** AGENTS.md (Boundaries; "jason proposes; the board adopts"). The send is a command a person copies; the adoption is a vote, read.
- **The checklist is read, not typed.** The catalog rows and the model tables are the source; the join between them is the one small table a person reviews.
- **A gap prints.** "A required part that is missing or stale is a visible gap. Never silently skipped" ([../document-templates.md](../document-templates.md)). A final build refuses; a draft names each gap.
- **No claim of compliance.** The words are `present`, `stale`, `missing`, `waiting`, `does not apply`; the caveat says so on the page.
- **A frozen run is not edited.** A revision, with its reason.

Still open:

1. **Where the packet's questions go.** The confirmations queue holds three kinds. Decide whether it takes a fourth, a *packet part to confirm* (jason's proposed source and pages, a person confirms), or the packet's own page holds them. The design as written works either way: `PartToConfirm` is one component. If the queue takes it, `#/confirmations?kind=packet` is the filter, and the queue's header says four kinds.
2. **One tab or its own screen.** The design puts the packet as a tab of `#/disclosures`. The alternative is a screen of its own in Governance beside Notices. A tab keeps the calendar and the packet together; a screen gives the packet room.
3. **The summary route or the full report to each member** (CIV 5320). The packet's size, the Mailroom's cost, and a variant for a member who asked for the full report turn on it. Decide how `SendPlanTable` shows the two routes side by side without choosing: the same rows under each, the cost of each, and the board's choice named as the board's.
4. **Where the board's statements are entered.** Entered here by a person, labeled "not yet adopted", or only read from the minutes' adopted text. The first is faster and risks a statement the board has not seen; the second leaves the packet waiting for the minutes.
5. **How "waiting" and "late for the window" differ.** A collection item has a due-by day computed from the window; decide whether an item past it is a state of its own ("late for the window") or the same *waiting* with the date in red text. The design uses a word beside the date, never a color.
6. **A standing value's confirmation.** Decide whether a value confirmed last year and unchanged is asked each run (the design) or carries a longer cycle.
7. **The owner view.** Whether members see, after the sent day, the packet's contents (part titles and what each answers), as a page of their own. It adds a column to `OwnerDisclosures` and no run data.
8. **The schedule's occurrence.** Whether a collection item shows in the schedule as its own occurrence (the design) or only as a link from the duty it belongs to.
9. **The read-through's shape.** Whether the reader records one "read by" for the whole packet (the design) or one per statutory part.
10. **The footer.** The merged PDF's "Page n of N" on every page may read as continuous numbering to the segmenter. Decide, after the first measurement, whether the packet-wide footer stays, moves to the gutter, or is replaced by a footer per part (a decision on the packet's look, not the checks').
11. **The 4041 request inside the screen.** Whether the owner-information request's own clock and campaign appear as a strip on this tab (the design: a strip that links to [handoff-followups.md](handoff-followups.md)) or only on its own screen.

## Phased plan

Smallest first; each phase is reviewable and stops.

1. **The checklist and the gap view.** `annual-packet` (header, clock, counts) and `annual-requirements`; `RequirementChecklist`, `RequirementRow`, `RequirementWord`, `GapPreview`, `DayTrio` read-only, `ClockStrip`; `jason packet annual-disclosures --check`. No write, no generation change, nothing built that was not built.
2. **Generation.** `annual-parts` and `annual-record`; `PacketOrder`, `PacketPartRow`, `ContentsPreview`, `FrozenRun`; the definition builder, contents, nested bookmarks, the part map with pages; the freeze write.
3. **Collection.** `annual-collect`; `CollectList`, `CollectItemRow`, `StandingValueRow`, `PartToConfirm`; the writes `annual/collect`, `annual/standing`, `annual/part`.
4. **The checks.** `annual-checks`; `QaResult`, `CrossCheckRow`, `SegmentCompare`, the preflight cards, `ReadThroughList`, `ReadRecord`; `annual/read`.
5. **Delivery.** `annual-send-plan`; `SendPlanTable`, `ProofLink`; `annual/archive`; the digest line.

## Not part of this pass

- Any send, batch, cancel, or posting: the screen has none, and the plan is commands to copy.
- Recording the board's vote, adopting a budget or a policy, or making a statement for the board.
- Building the packet from the console: `--build --yes` stays a terminal command until a person decides it is an engine plan (engine kind `google.doc`, R1, [approval-workflow.md](approval-workflow.md)).
- The owner view of the packet (decision 7).
- Editing a part's words, a stored file, or a base template from this screen.
- The reviewed financial statement's own run (CIV 5305): the same screen shape, a second definition with one attached file, after the packet's.
- A `jason-mcp` write tool.
- The previews: the design project's authored preview for each component follows the build, as for the earlier handoffs; fixtures will be `ui/src/components/requirementchecklist.test.tsx` and its siblings, from the sample data above.
