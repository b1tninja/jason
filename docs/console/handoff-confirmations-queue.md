# Handoff: the confirmations queue

For the design pass on the one list of what jason has proposed and only a person can settle: a candidate reading of the law or a governing document, a gold-record label, and a decision a lesson waits on. The data exists today, in three places and no screen: a reading whose `whose` is `JASON` is a lead (`jason readings`, [law-readings.md](../law-readings.md)); the draft gold rows for the context pack's records tier are a file whose every row says `confirmed: false` ([ingestion-and-review.md](../ingestion-and-review.md), `scripts/eval_retrieval.py`); and a lesson with `Status.DECISION` is "a person's or the board's call before anything can change" (`jason lessons --open`, `jason.community.lessons`). No loader serves them and no component renders them. Behavior and words are settled by this page, [README.md](README.md) (principles 4, 5, and 6), [components.md](components.md), [content/style.md](content/style.md), [content/patterns.md](content/patterns.md), and [approval-workflow.md](approval-workflow.md).

These components pair with what the console already has: `Recitation` and `ReadingLabel` (the words, then whose reading), `DecisionBrief` (options, never a recommendation), `Confirm` (two clicks, a name), `HeldNote` (where a board question goes), `Doc` (a file a gold row names), `Pill`, `DataTable`, `Stat`, `Caveats`, `Command`, `Findings`, `Card`, `Tabs`, `DueDate`, and `RemoteView`. Build new parts only where the table says so.

**What this queue is not.** It is not the approvals engine. Nothing here writes outside jason: every act is a person's record in jason's own store, signed with `by`, the way an intake answer is (approval-workflow, [section 8](approval-workflow.md#8-the-action-kind-registry): "not engine kinds"). It never routes a board question through an approve control ([section 12](approval-workflow.md#12-the-board-decides-by-vote)). And `jason-mcp` gets no confirm tool: an assistant can read the queue and recite a candidate; a confirmation is a person's act at the console or in the terminal, never a tool call ([section 10](approval-workflow.md#10-cli-and-mcp-parity)).

## The idea in one line

A confirmation is **a person's act about something jason proposed**, with their name and the day: it records that act, adopts nothing, applies nothing outside jason, and never makes a rule. Three kinds of item share one list, each saying in words what it needs from a person and what the person's act does and does not do.

## The three kinds

| Kind | What jason proposed | What a person does | What the act never does | Where the result goes | Reads and writes today |
| --- | --- | --- | --- | --- | --- |
| **Candidate reading** | A `LawReading` with `whose: jason` (`LawReading.lead`): one question of the words of one or more provisions, a proposed standing (`PLAIN`, `READING`, or `TWO_READINGS`), the canon relied on, and a note for the person | Confirms it as the board's reading (with the meeting that adopted it, recorded by the president or the secretary), as counsel's (naming counsel's letter), or as a director's (naming the director); marks that two readings remain, for counsel; rejects it; or skips it | Adopt anything: adoption is the board's vote. Make a rule. Change the words. Apply itself to a review: a confirmed row reaches `Community.law_readings()` only as a profile change a person applies | A signed confirmation record under `data/`, and a proposal patch with the row for the profile, applied by a person with `git apply` (the pattern `onboarding_answers.propose` uses) | Reads: `jason readings`, `--recite CITATION`, `--stale`, `jason cite`. Writes: none today. Proposed: `jason readings --confirm KEY --whose board\|counsel\|director --by NAME` |
| **Gold label** | A draft gold row for the records tier: a task, a question, a record kind, an audience, and the file a model drafter judged should be found, with verify phrases, with `confirmed: false` | Says **this file is the answer** (the drafter's, or one of the candidates), **none of these** (the kind holds no answer, or the only answer is held from this audience), or **not a records question** (the row leaves the set) | Change what the index ranks. Change `context_pack.RECORDS_FROM_INDEX`: that is a person's decision after the set is scored | `confirmed: true` with `by` and `at` on the row. A full set becomes the gold file the eval scores | Reads: the draft file, `jason index --search` for candidates. Scores: `python scripts/eval_retrieval.py --gold data/retrieval/gold-records.json --index`. Writes: none today. Proposed: `jason index --label ID --answer FILE\|none\|not-records --by NAME` |
| **Decision** | A lesson with `Status.DECISION`: what happened, why, and the change that waits on a call | Records who decides: a person (and records the decision), the board (an agenda item), or counsel (a question for counsel) | Approve for the board. Change the lesson's row: that is code, and a person commits it | A signed decision record under `data/`; for the board, a board item through `tasks.board_items.propose` and the meeting's agenda | Reads: `jason lessons --open`, `jason sop KEY`. Writes: `jason board --set ID --status … --by NAME` for the board item's fields. Proposed: `jason lessons --decide KEY --by NAME --who person\|board\|counsel` |

The list is one list, **oldest first**: the day jason proposed it (a reading's `dated`, a gold file's `written`, a lesson's `learned`), with the age in the table's form ("3 d"). An item is never urgent on its own; a candidate reading that a review or an answer waited on says which, in words, and sorts no higher.

## The components

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `ConfirmationsQueue` | Overview → Confirmations (`#/confirmations`) | `GET /api/confirmations` | no store at all (the commands that make each kind); loading; listed, oldest first; one of the three loaders failed (the other two listed, the failed one's note and command in its place); filtered to none; stale rows marked; empty ("Nothing waits on a person. 3 confirmed this month.") |
| `QueueCounts` (a `Stat` strip) | above the queue; a band of `#/digest` under "Waiting on a person" | `counts` | by kind; by state; its table twin |
| `CandidateReading` | one reading, opened from the queue (`#/confirmations/reading/<key>`) | `GET /api/confirmations/reading?key=` | current (confirmable); stale (a provision's words changed: `StaleWordsBanner`, controls off); missing (a provision not on the shelf: the command); misquoted (the quote is not in the words: controls off, the quote shown against the words); confirmed; rejected; skipped (with when it returns); two readings (for counsel, with its board item); adopted (`AdoptionState`) |
| `ProvisionRecital` | inside `CandidateReading`, one per provision, in the reading's order | each provision's `Recitation` with `digestRead`, `digestNow`, `state` | the words with the version in force and the caveat; the words that answer marked (`Recitation`'s `mark`, from `quote`); two versions under one number (each labeled, the one in force today named); not shown to be in force on the day asked; stale (digest read against digest now, with where the replaced words are kept) |
| `StandingChoice` | under the recital | the reading's `standing`, `whose`, `canon`; the person from "Signed in as" | the four acts, each a `Confirm`: confirm as the board's (a meeting date and the recording officer required), as counsel's (counsel's letter or date required), as a director's (the director named); two readings remain (both named, neither preferred); reject (a reason); skip (returns in N days, a reason optional); every control off while stale, missing, or misquoted, with the reason in words |
| `AdoptionState` | at the top of a confirmed reading; a line in the queue | `adoption` | none ("Confirmed by Jane Example as a director's reading, Oct 3, 2099. Not adopted: the board has not voted."); adopted ("Approved by the board at its meeting of Oct 7, 2099 (CIV 4910); recorded by Sam Placeholder, secretary"); counsel's (the letter's date); on the agenda (the board item and meeting, not yet voted) |
| `StaleWordsBanner` | first in `CandidateReading` when `state` is `stale` | `provisions[].digestRead`, `digestNow`, `kept` | which provision changed, the two digests' first twelve characters, where the replaced words are kept, **Re-read** (opens both versions side by side; `DiffTable` is still proposed, so the fallback is two `Recitation`s), and that nothing can be confirmed until a person records the re-read |
| `GoldLabelRow` | one gold row, opened from the queue (`#/confirmations/gold/<id>`) | `GET /api/confirmations/gold?id=` | the question, task, kind, and audience; the drafter's file with its verify phrases; the candidates the index returned, each a `Doc` chip with its rank and passage; a candidate held from a members' audience (named by kind only, "held"); the three answers; confirmed; left the set ("not a records question"); the index has no candidates (the command that builds it) |
| `GoldProgress` | above the gold rows; a line in `QueueCounts` | `progress` | n of N confirmed, by task and by kind; what a full set unlocks, in words; the scoring command (`Command`); a set scored since (the run's date and the two reaches' recall and MRR, as the run printed them) |
| `DecisionRow` | one lesson, opened from the queue (`#/confirmations/decision/<key>`) | `GET /api/confirmations/decision?key=` | what happened, why, and the change that waits (the lesson's own words); the `DecisionBrief` where one is written (question, criteria, lettered options, facts; `BRIEF_FOOTER`), else "No brief yet" with the command; `JasonAside` collapsed; `WhoDecides`; decided (by whom, when, which option); on the board's agenda (`HeldNote` form: the board item and meeting); a question for counsel (recorded, with who carries it) |
| `WhoDecides` | inside `DecisionRow` | `decides` | undecided; a person (records the decision behind `Confirm`); the board (proposes the board item behind `Confirm`; never an approve control); counsel (records the question behind `Confirm`) |
| `JasonAside` | inside `DecisionRow` and `CandidateReading` | a lesson's `notes`; a candidate's `note` | collapsed by default, labeled "jason's note: not a recommendation, not part of the brief, not legal advice"; opened (the text); none ("jason adds no note") |

### The words

Every state is a word the code already uses, and the color only repeats it.

| Word | Where from | Meaning |
| --- | --- | --- |
| waiting | the queue | no person has acted |
| current | `ReadingState.CURRENT` | every provision's words are the words it read; it can be confirmed |
| stale | `ReadingState.STALE` | a provision's words changed since; nothing can be confirmed until re-read |
| missing | `ReadingState.MISSING` | a provision is not on the shelf |
| misquoted | `ReadingState.MISQUOTED` | the quote is not in a provision it reads |
| confirmed | the confirmation record | a person recorded the act, with their name and the day |
| adopted | the board's decision on record | the board voted; a meeting and a recording officer |
| two readings | `ReadingStanding.TWO_READINGS` | both named, neither preferred; the board asks counsel |
| rejected, skipped | the confirmation record | a person's act, with a reason |
| decided, for the board, for counsel | the decision record | who decides, and the path |
| this file, none of these, not a records question | the gold row | the three answers |

"Approve", "accept", and "apply" appear on no control here. A reading is "confirmed as whose"; a decision is "recorded"; a board question is "on the board's agenda".

## Data shapes

Made-up keys, sections, people, and files. A section number here is a placeholder, and its words are left out of the sample on purpose: on the screen they come from `jason cite` and the shelf, never from a sample.

`GET /api/confirmations` (proposed; `?kind=reading|gold|decision`, `?state=`):

```json
{
  "found": true, "asOf": "2099-10-05",
  "counts": {"reading": 3, "gold": 42, "decision": 7, "stale": 1, "waiting": 51},
  "items": [
    {"kind": "reading", "id": "example-day-means", "proposed": "2099-09-28", "age": "7 d",
     "title": "Does \"day\" in the notice period mean a calendar day?",
     "provisions": ["CIV 9901", "bylaws#7.2"], "standing": "reading", "whose": "jason",
     "state": "stale", "needs": "a person reads the changed words before confirming", "route": "#/confirmations/reading/example-day-means"},
    {"kind": "gold", "id": "q-0017", "proposed": "2099-10-01", "age": "4 d",
     "title": "Which minutes record the vote on the paint contract?",
     "task": "example-task", "recordKind": "minutes", "audience": "board",
     "state": "waiting", "needs": "this file, none of these, or not a records question", "route": "#/confirmations/gold/q-0017"},
    {"kind": "decision", "id": "example-two-stores-disagree", "proposed": "2099-10-02", "age": "3 d",
     "title": "Two stores answer the same confidentiality question by different rules",
     "areas": ["documents"], "state": "waiting", "needs": "who decides: a person, the board, or counsel", "route": "#/confirmations/decision/example-two-stores-disagree"}
  ],
  "unavailable": [],
  "caveats": ["A candidate is jason's lead; no person has adopted it. A confirmation records a person's act and adopts nothing: adoption is the board's vote at a meeting."]
}
```

`GET /api/confirmations/reading?key=example-day-means` (proposed): the reading as `Recited.as_dict()` gives it, each provision recited through `recite`, and the confirmation state beside it.

```json
{
  "found": true, "key": "example-day-means",
  "question": "Does \"day\" in the notice period mean a calendar day?",
  "standing": "reading", "whose": "jason", "lead": true, "dated": "2099-09-28",
  "reading": "A day is a calendar day: the provision names no business-day count.",
  "canon": "ordinary_sense", "canonCitation": "CIV 1644", "authority": "",
  "alternatives": [], "quote": "within ten days", "boardItem": "",
  "note": "The bylaws' section and the statute's use the same word; a person checks both before confirming.",
  "state": "stale", "applies": false,
  "status": "stale: CIV 9901 changed: it read digest 0a1b2c3d4e5f, the words on disk have 9f8e7d6c5b4a (the words it read are kept: authorities/history/civ-9901/0a1b2c3d4e5f.md)",
  "provisions": [
    {"citation": "CIV 9901", "state": "stale", "digestRead": "0a1b2c3d4e5f", "digestNow": "9f8e7d6c5b4a",
     "kept": "authorities/history/civ-9901/0a1b2c3d4e5f.md",
     "recital": {"found": true, "citation": "CIV 9901", "text": "(the section's words, recited from the shelf)",
                 "inForce": "current words; exported 2099-10-04", "caveat": "jason's copy of the publication, not an official restatement."}},
    {"citation": "bylaws#7.2", "state": "current", "digestRead": "1122334455aa", "digestNow": "1122334455aa", "kept": "",
     "recital": {"found": true, "citation": "bylaws#7.2", "text": "(the section's words, as jason keeps the document)",
                 "inForce": "as amended 2097-03-12", "caveat": "Consolidated by jason from the instruments' own words; the recorded instruments control."}}
  ],
  "confirmation": null,
  "adoption": null,
  "commands": {"recite": "jason readings --recite CIV-9901", "stale": "jason readings --stale", "reread": "jason law-history --versions --citation CIV-9901"}
}
```

`POST /api/write/confirmations/reading/<key>` (proposed; behind the write guard, `X-Jason-Token`):

```json
{"act": "confirm", "whose": "director", "named": "Casey Sample", "by": "Jane Example",
 "digests": {"CIV 9901": "9f8e7d6c5b4a", "bylaws#7.2": "1122334455aa"}, "reason": ""}
```

`act` is one of `confirm`, `two_readings`, `reject`, `skip`, `reread`. `whose` is `board` (then `meeting` and `recordedBy` are required, and `recordedBy` must hold the office of president or secretary), `counsel` (then `authority` is required: the letter and its date), or `director` (then `named`). `digests` echoes the digest of each provision as the person saw it; a digest that is not the one on disk is refused (409) and nothing is written: "The words changed since you opened this. Reload and read them again." The answer is the record written: `{written: "readings/confirmations.jsonl", proposal: "onboarding/proposals/reading-example-day-means.patch", row: {...}}`. A `reread` act records only that the person read the words now on disk, with their digests; it carries no reading.

`GET /api/confirmations/gold?id=q-0017` (proposed):

```json
{
  "found": true, "id": "q-0017", "task": "example-task", "question": "Which minutes record the vote on the paint contract?",
  "recordKind": "minutes", "audience": "board", "sort": "latest",
  "drafted": {"file": {"path": "library/minutes/minutes-example.pdf", "name": "minutes-example.pdf", "sha256": "ab12…", "period": "2099-06"},
              "text": ["paint contract", "motion carried"], "why": "The drafter's judgment: the June minutes carry the vote.", "confidential": false},
  "candidates": [
    {"rank": 1, "doc": {"ref": "library:4001", "name": "minutes-example.pdf", "kind": "minutes", "level": "P1"}, "passage": "… (the passage's words) …", "isDrafted": true},
    {"rank": 2, "doc": {"ref": "library:4002", "name": "minutes-other-example.pdf", "kind": "minutes", "level": "P1"}, "passage": "…", "isDrafted": false},
    {"rank": 3, "held": true, "kind": "treasurer_report", "note": "held from a members' pack; shown by kind only"}
  ],
  "candidatesFrom": {"mode": "exact", "index": "2099-10-04", "command": "jason index --search \"Which minutes record the vote on the paint contract?\" --kind minutes -k 5"},
  "confirmed": false, "confirmation": null,
  "caveats": ["The verify phrases point at the file; they are not a quotation to recite.", "sort was true on the day written and changes as files are added: it is recomputed before scoring."]
}
```

`POST /api/write/confirmations/gold/<id>`: `{"answer": "file", "file": "library:4001", "by": "Jane Example"}`, or `{"answer": "none", ...}`, or `{"answer": "not_records", "reason": "…", ...}`. The answer is the row as written back to the draft file, with `confirmed: true`, `confirmedBy`, and `confirmedAt`.

`GET /api/confirmations/progress` (proposed): `{total: 42, confirmed: 12, left: 30, byTask: {...}, byKind: {...}, unlocks: "A full set scores the records tier read from the index against the library reader (recall@5, MRR@10). Then a person decides context_pack.RECORDS_FROM_INDEX, and the lessons records-tier-index-cut-differs and stub-passages-cost-first-places can close.", scoreCommand: "python scripts/eval_retrieval.py --gold data/retrieval/gold-records.json --index", lastRun: null}`.

`GET /api/confirmations/decision?key=example-two-stores-disagree` (proposed): the lesson's row (`key`, `learned`, `areas`, `what`, `why`, `change`, `status`, `guards`, `docs`, `notes`), `brief` (a `DecisionBrief` body, or null), `decides` (null, or `{who: "board", boardItem: "BI-2099-04", meeting: "2099-10-07", by, at}`), `decision` (null, or `{option: "B", by, at, reason}`), and `commands` (`jason lessons --open`, `jason sop KEY`).

`POST /api/write/confirmations/decision/<key>`: `{"who": "person", "option": "B", "reason": "…", "by": "Jane Example"}`; `{"who": "board", "by": ...}` proposes the board item and answers its id; `{"who": "counsel", "question": "…", "by": ...}` records the question. The lesson's row in `lessons.py` is unchanged by any of these: the answer carries `rowChange`, the one-line edit a person makes (`Status.DECISION` to `Status.OPEN` or `Status.FIXED`, with the guard), as a `Command`-style block to copy.

## What the design must keep

- **Recite first; label the reading** (principle 2). Each provision's `Recitation` comes before the proposed standing: the words whole, the version in force, the caveat, the digest. The standing follows as `ReadingLabel whose="jason"`, with its built basis line ("A reading, not legal advice. The recited words govern; the board decides."). A `PLAIN` candidate shows no reading sentence: the words that answer are marked in the recital. A `TWO_READINGS` candidate shows both under `whose="open"` and prefers neither.
- **A confirmation is a person's act, never an adoption.** The board's reading exists only by its vote: "confirm as the board's" needs the meeting's date and the officer who records it (president or secretary), as a letter's board approval does (`tasks.approvals.step(..., meeting=...)`). Without a vote, the strongest act is a director's reading, named, and `AdoptionState` says "Not adopted". No control says "Approve".
- **It makes no rule and changes no code.** A confirmed row reaches the profile as a proposal patch a person applies (`git apply`), the way an onboarding answer does; a decided lesson's row is edited by a person. The screen shows the diff to apply, never applies it.
- **Stale cannot be confirmed.** `status()` runs on every read. When a digest differs, `StaleWordsBanner` is first, every act but `reread` is off, and the write refuses a digest echo that is not the one on disk. A person reads the words now on disk, records the re-read, and only then confirms against the new digest, which the new row carries.
- **Two readings go to counsel; the console picks neither.** "Mark two readings remain" names both, prefers neither, and proposes a board item ("the board asks counsel"). It is the one act that creates a board item from a reading, and it says so.
- **The brief never recommends.** `DecisionBrief` keeps `BRIEF_FOOTER`; the store refuses a body that names a recommendation (approval-workflow, section 12). A note jason has (a lesson's `notes`, a candidate's `note`) is `JasonAside`: collapsed by default, labeled as jason's note and not a recommendation, never inside the brief and never above the options.
- **Who decides is recorded, not assumed.** A lesson's decision is the person's, the board's, or counsel's. For the board, the only path is a board item and a noticed agenda ([board-items.md](screens/board-items.md), [meetings-and-minutes.md](screens/meetings-and-minutes.md)): the row says "On the board's agenda" and links the item and the meeting; the vote is recorded in `#/room` or `#/decisions`, never here.
- **A gold label is a measurement, not a pin.** Confirming a row says what the records tier should find for one question; it changes no index and no reader. `GoldProgress` says in words what a full set unlocks and names the person's decision that follows the score. The drafter's `why` is labeled the drafter's judgment, and the verify phrases are labeled as pointers, not a quotation.
- **Oldest first, and a miss stays a miss** (principle 8). A kind whose store is absent shows the command that makes it, in its own place in the list, and the other kinds still list. A candidate whose provision is not on the shelf says so with the command (`jason cite`), and is not confirmable.
- **Privacy by level** (principle 6). A candidate's question can name a matter; a gold row names the association's files and, for a members' audience, a held file is shown by kind only; a lesson can name a unit or an owner in the profile's private lessons. The screen is board-only, never in the owner view, and a candidate on an executive-session subject is listed by its general subject outside the private view, as a board item is.
- **No color-only meaning.** Every state above is a word; `QueueCounts` has a table twin; a stale row carries the word "stale" in its own column.
- **Nothing is written without a person** (principle 4). Every act is a `Confirm` that spells out what is recorded and in whose name, behind the write guard; a write with no `by` is 400; while someone is signed in, `by` is that person.

## Where it goes

- **Overview → Confirmations** (proposed), beside Approvals: route `#/confirmations`, with `?kind=` and `?state=` filters and a count in the nav (items waiting, stale ones counted apart). One item: `#/confirmations/reading/<key>`, `#/confirmations/gold/<id>`, `#/confirmations/decision/<key>`. A URL carries a key or an id, never a name ([security-and-privacy.md](security-and-privacy.md#urls)).
- **`#/digest`**, under "Waiting on a person" ([today.md](screens/today.md)): `QueueCounts` as one line ("3 readings, 30 gold labels, and 7 decisions wait on a person; 1 is stale"), linking to the queue.
- **Governing documents** (`#/documents`, [governing-documents.md](screens/governing-documents.md)): a candidate that reads the section shown appears in its READINGS band as "jason's reading (a lead; waiting for a person)", linking into the queue. A confirmed and adopted reading appears there as the board's, with the adoption date, once the profile row is applied.
- **Decisions** (`#/decisions`) stays the board's votes. A decision routed to the board arrives there through its board item, and the queue row then shows "On the board's agenda" until the decision is on record.
- **Approvals** (`#/approvals`) is unchanged: nothing here is an engine approval ([approvals.md](screens/approvals.md)).

**Loaders and writes to add** (all proposed; a loader wraps a function that exists, except where marked "to write"):

| Name | Function behind it | Reads | Writes |
| --- | --- | --- | --- |
| `confirmations` | `jason.web.extra.confirmations:confirmations` (to write) over `law_readings.readings` + `status` (candidates: rows with `whose: jason`), the draft gold file's rows with `confirmed: false`, and `lessons.lessons(community)` filtered to `Status.DECISION`, each with its proposed day | disk only | — |
| `confirmations-reading` | `law_readings.recite(citation, data_dir, readings, as_of, community=)` per provision, `law_readings.status`, `provision_text` | disk only | — |
| `confirmations-gold` | the draft file's row; candidates from `passage_index.search(query, data_dir=..., scope=..., mode="exact", k=5)` (no model, no GPU lock), held files by `tasks.index_sources.library_holds` | disk only | — |
| `confirmations-progress` | the draft file's counts; the last run's JSON under `data/retrieval/runs/` where one names the gold file | disk only | — |
| `confirmations-decision` | `lessons.lesson(key)` or the community's own; the brief from `data/board/` where one is written; `tasks.board_items.load` for the item | disk only | — |
| write `confirmations/reading` | `jason.web.extra.confirmations:write_reading` (to write): appends `data/readings/confirmations.jsonl` and writes `data/onboarding/proposals/reading-<key>.patch` with the `LawReading` row for the profile (the pattern of `onboarding_answers.propose`); refuses a stale digest echo, a missing `by`, a board confirmation without a meeting and a recording officer | — | jason's own store; the profile only by a person's `git apply` |
| write `confirmations/gold` | `write_gold_label` (to write): sets `confirmed`, `confirmedBy`, `confirmedAt`, and the answer on the row, written whole under the store lock | — | `data/retrieval/gold-records.draft.json` |
| write `confirmations/decision` | `write_decision` (to write): appends `data/lessons/decisions.jsonl`; for the board, `tasks.board_items.propose` with the lesson as evidence, signed by the person | — | jason's own stores; the lesson's row only by a person's commit |

The candidate store is a question for the build: today a candidate lives in a person's private notes as the row it would become, and `Community.law_readings()` holds only confirmed rows. The loader needs candidates as `LawReading` rows with `whose: jason` on disk, `data/readings/candidates.json` (proposed), loaded into the record before any screen sees them, so that `status()` and `recite()` treat a candidate exactly as a reading.

## Accessibility

As [components.md](components.md#accessibility), with these particulars.

- **The queue is a real table** (`DataTable`): kind, title, proposed day, age, state, and what it needs, each a column with text; sorted "oldest first" and the sort announced; a caption ("Waiting on a person, oldest first"). Filters sit in a labelled group with a polite live region for the count ("12 of 51 items"). A row is a link to its page, in DOM order; no grid roles.
- **A recital is a `<figure>`** with `<blockquote>` and `<figcaption>` (the citation, the version in force, the caveat, the digest), as `Recitation` renders it; the reading follows as an `aside` with its label, as `ReadingLabel` renders it. A screen reader meets the words before the reading, always.
- **`StaleWordsBanner` is `role="alert"`** at the top of the page when the state is stale, missing, or misquoted, and the disabled acts each carry `aria-describedby` naming the reason. "Re-read" moves focus to the first changed provision.
- **`StandingChoice` is a `<fieldset>`** with a legend ("Your act on this reading, as Jane Example"); the whose choice is a radio group; the fields each choice requires (meeting date and officer; counsel's letter; the director's name) appear in place with visible labels, and an error names the field: "A board reading needs the meeting that adopted it and the officer who recorded it."
- **Every act is a `Confirm`** (two clicks, the record spelled out): "Record as a director's reading (Casey Sample), confirmed by Jane Example on Oct 5, 2099. This adopts nothing." After the act, the result in `role="status"`, in place; focus stays on the row.
- **`DecisionBrief`'s options are lettered headings**; `JasonAside` is a `<details>` with a summary that carries its full label; `WhoDecides` is a radio group whose board choice says in text that it proposes an agenda item and nothing else.
- **`GoldLabelRow`'s candidates are a list**, each a `Doc` chip (its own focus and keyboard behavior) with the rank and the passage in text; the three answers are radio buttons, the file choice listing the drafted file and each candidate by name.
- **Shortcuts** as [patterns.md](content/patterns.md#keyboard-use): `j`/`k` between rows, `?` lists them, single-key shortcuts off by default for anyone who asks; nothing requires a drag; every target 24 by 24 CSS pixels or spaced to pass.
- **Nothing times out.** A partly filled act (a reason typed, a meeting date entered) stays in the form until the person leaves the page; the store holds nothing until `Confirm`.

### The phone layout (under 720 px)

- The queue's rows become cards: the title first, then kind and state as words on one line, then "needs" and the age. The filters collapse into a disclosure with the active count in its summary.
- A reading's page stacks: `StaleWordsBanner`, the question, each `ProvisionRecital` in order (long words scroll inside the page, never sideways), the proposed standing, `JasonAside`, then `StandingChoice` at the foot, not sticky: it is one decision at the end of a reading, not a bar over a list. Each required field opens under its choice.
- A gold row stacks the question, the drafted file, the candidates as cards, then the three answers.
- A decision's brief uses `DecisionBrief`'s stacked form (no `columns`); `WhoDecides` follows it.
- "Go to" replaces the nav as `ConsoleShell` does; the dock's drawers still pin at 1200 px and float below.

## Decisions for the design

1. **One list or three tabs.** The brief says one list, oldest first, so the oldest proposal is seen whatever its kind. Decide whether a kind filter is a tab row (`Tabs`) or a filter in the table, and how a stale reading reads in a list where most rows are gold labels (42 of 52 today).
2. **How much of a recital is on the row.** A row that recites every provision is long; one that hides them invites deciding without reading. Decide whether the queue row shows the question alone and the page recites, or the row shows the first provision's citation and digest state as text.
3. **The board confirmation's fields.** A reading confirmed as the board's needs a meeting and a recording officer. Decide whether that act lives here at all, or only on the letters' pattern in `#/approvals` ("Record the board's approval"), with the queue showing "On the board's agenda" until it is recorded.
4. **Skip's return.** A skipped item returns after a time or stays skipped until someone unskips it. Decide the default (the brief proposes 30 days, as a word on the row: "skipped by Jane Example; returns Nov 4"), and whether a skipped candidate still appears in the Governing documents READINGS band.
5. **Re-read as its own act.** Recording a re-read before a confirm is two confirms. Decide whether a stale reading's page offers the re-read and the confirm as one form whose first part is the side-by-side words, so the digest echo and the act are one record.
6. **Candidates for a gold row.** An exact search at request time is quick and needs no model; a dense search would hold the GPU lock. Decide whether the row shows exact candidates only (with the mode named), or candidates a command computed and stored beside the row with its date.
7. **Progress and the score.** Decide how `GoldProgress` shows a set scored since (the run's recall@5 and MRR@10 for the two reaches, as the run printed them) without the screen seeming to pick a reach: the choice is a person's, named as such.
8. **The decision brief's absence.** Most DECISION lessons have no written brief. Decide the state of a `DecisionRow` with none: the lesson's words alone and the command that writes a brief, or an inline brief form (question, criteria, options) a person fills before anyone decides.
9. **Where a counsel question goes.** A reading marked "two readings remain" and a lesson sent to counsel both produce a question for counsel. Decide whether that is a board item only, or also a line in the packet (`{REPORT:conflicts}` carries conflicts; nothing carries readings yet).
10. **The candidate store.** Candidates are written by a person today. Decide whether the console offers a form to enter a candidate (a question, provisions, a proposed standing, labeled jason's or the entrant's), or candidates come only from the terminal.

## Not part of this pass

- Any write outside jason, and any engine kind: a confirmation is a signed record in jason's own store, never an approval.
- Applying a proposal patch to the profile, or editing a lesson's row: a person's `git apply` and commit.
- The board's vote on a reading or a decision: `#/room`, `#/decisions`, and the board loop.
- A confirm tool in `jason-mcp`: it stays read-only, and reads the queue through the same functions.
- `DiffTable` (two versions of a provision side by side) and `CiteBox`: still proposed in [components.md](components.md#still-proposed); `StaleWordsBanner` falls back to two `Recitation`s.
- Entering a candidate reading from the console (decision 10), and converting the private candidates note into the candidate store: a person's work, as [ingestion-and-review.md](../ingestion-and-review.md) says ("jason converts none").
- The owner view: this screen is board-only at every phase.
- The previews: the design project's authored preview for each component follows the build, as for the earlier handoffs; fixtures will be `ui/src/components/confirmationsqueue.test.tsx` and its siblings, from the sample data above.
