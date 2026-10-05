# Handoff: the confirmations queue

For the design pass on the one list of what jason has proposed and only a person can settle: a candidate reading of the law or a governing document, a gold-record label, and a decision a lesson waits on. The data exists today, in three places and no screen: a reading whose `whose` is `JASON` is a lead (`jason readings`, [law-readings.md](../law-readings.md)); the draft gold rows for the context pack's records tier are a file whose every row says `confirmed: false` ([ingestion-and-review.md](../ingestion-and-review.md), `scripts/eval_retrieval.py`); and a lesson with `Status.DECISION` is "a person's or the board's call before anything can change" (`jason lessons --open`, `jason.community.lessons`). No loader serves them and no component renders them. Behavior and words are settled by this page, [README.md](README.md) (principles 4, 5, and 6), [components.md](components.md), [content/style.md](content/style.md), [content/patterns.md](content/patterns.md), and [approval-workflow.md](approval-workflow.md).

These components pair with what the console already has: `Recitation` and `ReadingLabel` (the words, then whose reading), `DecisionBrief` (options, never a recommendation), `Confirm` (two clicks, a name), `HeldNote` (where a board question goes), `DecisionCard` and `RollCall` (where the board's vote is recorded), `Doc` (a file a gold row or a counsel's letter names), `Pill`, `DataTable`, `Stat`, `Caveats`, `Command`, `Findings`, `Card`, `Tabs`, `DueDate`, and `RemoteView`. Build new parts only where the table says so.

**What this queue is not.** It is not the approvals engine. Nothing here writes outside jason: every act is a person's record in jason's own store, signed with `by`, the way an intake answer is (approval-workflow, [section 8](approval-workflow.md#8-the-action-kind-registry): "not engine kinds"). It never routes a board question through an approve control ([section 12](approval-workflow.md#12-the-board-decides-by-vote)), and it never records the board's vote: the vote is recorded where every vote is, on the meeting's Decisions tab (`DecisionCard`, `data/board/decisions.json`), and the queue reads it from there. And `jason-mcp` gets no confirm tool: an assistant can read the queue and recite a candidate; a confirmation is a person's act at the console or in the terminal, never a tool call ([section 10](approval-workflow.md#10-cli-and-mcp-parity)).

**Its neighbour.** [handoff-applicability-questions.md](handoff-applicability-questions.md) is the other half of "what a person settles": a **fact** a record states (a count, a date, a standard, a board's choice on record) is answered in the intake queue from `#/applies`; what **words mean** is a reading, confirmed here. "Facts and readings" below says which is which, and how each links to the other.

## The idea in one line

A confirmation is **a person's act about something jason proposed**, with their name and the day: it records that act, adopts nothing, applies nothing outside jason, and never makes a rule. Three kinds of item share one list, each saying in words what it needs from a person and what the person's act does and does not do. A reading becomes the board's only by the board's vote, recorded on its Decisions tab, and counsel's only from counsel's own letter; the words of either are theirs, never jason's candidate relabeled.

## The three kinds

| Kind | What jason proposed | What a person does | What the act never does | Where the result goes | Reads and writes today |
| --- | --- | --- | --- | --- | --- |
| **Candidate reading** | A `LawReading` with `whose: jason` (`LawReading.lead`): one question of the words of one or more provisions, a proposed standing (`PLAIN`, `READING`, or `TWO_READINGS`), the canon relied on, and a note for the person | Reads the words now on disk and **puts it on the board's agenda**; records that **two readings remain** (the board asks counsel); **records counsel's reading** from counsel's letter; once the board has voted, **writes the profile row from the board's decision**; **rejects** it; or **skips** it. The acts are listed in "The acts on a reading" | Adopt anything: adoption is the board's vote, recorded on Decisions. Make a rule. Change the words. Turn jason's sentence into the board's or counsel's: their reading is the motion's words or the letter's. Apply itself to a review: a row reaches `Community.law_readings()` only as a profile change a person applies | A signed confirmation record under `data/`; a board item for the agenda; and, from the board's decision or counsel's letter, a proposal patch with the row for the profile, applied by a person with `git apply` (the pattern `onboarding_answers.propose` uses) | Reads: `jason readings`, `--recite CITATION`, `--stale`, `jason cite`. Writes: none today. Proposed: the `jason readings` acts in the table below |
| **Gold label** | A draft gold row for the records tier: a task, a question, a record kind, an audience, and the file a model drafter judged should be found, with verify phrases, with `confirmed: false` | Says **this file is the answer** (the drafter's, or one of the candidates), **none of these** (the kind holds no answer, or the only answer is held from this audience), or **not a records question** (the row leaves the set) | Change what the index ranks. Change `context_pack.RECORDS_FROM_INDEX`: that is a person's decision after the set is scored | `confirmed: true` with `by` and `at` on the row. A full set becomes the gold file the eval scores | Reads: the draft file, `jason index --search` for candidates. Scores: `python scripts/eval_retrieval.py --gold data/retrieval/gold-records.json --index`. Writes: none today. Proposed: `jason index --label ID --answer FILE\|none\|not-records --by NAME` |
| **Decision** | A lesson with `Status.DECISION`: what happened, why, and the change that waits on a call | Records who decides: a person (and records the decision), or the board (an agenda item), including the board asking counsel | Approve for the board. Ask counsel without the board. Change the lesson's row: that is code, and a person commits it | A signed decision record under `data/`; for the board, a board item through `tasks.board_items.propose` and the meeting's agenda | Reads: `jason lessons --open`, `jason sop KEY`. Writes: `jason board --set ID --status … --by NAME` for the board item's fields. Proposed: `jason lessons --decide KEY --who person\|board\|counsel --by NAME` |

The list is one list, **oldest first**: the day jason proposed it (a reading's `dated`, a gold file's `written`, a lesson's `learned`), with the age in the table's form ("3 d"). An item is never urgent on its own; a candidate reading that a review, an answer, or a fact question waits on says which, in words, and sorts no higher.

### The acts on a reading

Every act is a `Confirm` in the signed-in person's name, through the write guard (`X-Jason-Token`), and echoes the digest of each provision as the person saw it. Every act but **Re-read** is off while the reading is stale, missing, or misquoted. The CLI flags are proposed, like the route; none is built.

| Act | The words on the button (what the person signs) | Who may | What it needs | What it records | CLI (proposed) |
| --- | --- | --- | --- | --- | --- |
| Put on the board's agenda | **Put on the board's agenda as Jordan Example** | a roster person (never counsel) | the current words | the confirmation (`act: agenda`, the digests read); a board item proposed for the next agenda, carrying the question, the provisions' citations, and jason's sentence labeled as jason's | `jason readings --to-board KEY --by NAME` |
| Two readings remain | **Record that two readings remain, as Jordan Example** | a roster person (never counsel) | both readings in words: jason's and the other, the other entered by the person and labeled as theirs | the confirmation (`act: two_readings`); a board item "the board asks counsel" | `jason readings --two-readings KEY --other TEXT --by NAME` |
| Record counsel's reading | **Record counsel's reading from the letter of Sep 30, 2099, as Jane Example** | a person whose office opens P3 in the private view (the letter is P3), with the private view open | the letter, a library file (`Doc`); the passage of the letter that gives the reading, which the server finds in the letter's stored text or refuses | the confirmation (`act: counsel`); a proposal patch with `whose: counsel`, `reading` the letter's passage, `authority` the letter | `jason readings --counsel KEY --letter REF --passage TEXT --by NAME` |
| Write the board's adoption | **Write the profile row from the board's decision of Oct 7, 2099, as Sam Placeholder** | the president or the secretary (principle 5) | a decision on record for the reading's board item (`data/board/decisions.json`) whose outcome is approved; the server reads the meeting, the motion's words, and the recording officer from it, never from the form | the confirmation (`act: adopted`, the decision's id); a proposal patch with `whose: board`, `reading` the motion's words, `authority` the decision | `jason readings --adopted KEY --decision ID --by NAME` |
| Reject | **Reject as Jane Example**, with a reason | a roster person (never counsel) | a reason | the confirmation (`act: reject`); the candidate stays on record as rejected, never deleted | `jason readings --reject KEY --reason TEXT --by NAME` |
| Skip | **Skip until Nov 4 as Jane Example** | a roster person | a reason, optional | the confirmation (`act: skip`) with the day it returns | `jason readings --skip KEY --by NAME` |
| Re-read | **Record the re-read as Jane Example** | a roster person | the words now on disk, opened | the confirmation (`act: reread`) with the new digests; it carries no reading | `jason readings --reread KEY --by NAME` |

There is **no "confirm as a director's reading"**. `law_readings.Whose` holds `jason`, `board`, and `counsel`, `ReadingLabel` renders those and "two readings remain", and a director alone adopts nothing: the strongest act one person takes on a candidate is to put it before the board, named and dated.

## Facts and readings

The two queues meet, and each links to the other rather than copying it.

- **Which queue.** A question answered by reading a value off a record (a count of units, a date of inspection, an installation standard, whether the board's minutes keep acclamation available) is a fact: a `FactQuestionRow` in `#/applies`, answered in the intake queue. A question two people could answer differently from the same words (what "day" means in a notice period; whether a clause reaches a building) is a reading: a candidate here.
- **A fact that turns on a reading.** When the record that would answer a fact question is words whose meaning is open, the fact question's record field may name a reading by its key (`reading:example-day-means`). Until that reading is the board's or counsel's, the fact stays undetermined, and the question row says "waits on a reading: on the confirmations queue", linking `#/confirmations/reading/<key>`. A candidate never answers a fact.
- **A reading that facts wait on.** `CandidateReading` lists, under the question, "Questions waiting on this reading" (each fact question that names it, by id and subject, linking `#/applies?subject=…`), and the queue's "needs" column says so in words. They sort no higher.
- **A disagreement is not a reading.** A `Discrepancy` between the profile and an answer is settled by a corrected specification or a new answer ([handoff-applicability-questions.md](handoff-applicability-questions.md)), never by a confirmation here.

## The components

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `ConfirmationsQueue` | Overview → Confirmations (`#/confirmations`) | `GET /api/confirmations` | no store at all (the commands that make each kind); loading; listed, oldest first; one of the three loaders failed (the other two listed, the failed one's note and command in its place); filtered to none; stale rows marked with the word; a row facts wait on ("2 questions wait on it"); empty ("Nothing waits on a person. 3 confirmed this month.") |
| `QueueCounts` (a `Stat` strip) | above the queue; a band of `#/digest` under "Waiting on a person" | `counts` | by kind; by state; its table twin |
| `CandidateReading` | one reading, opened from the queue (`#/confirmations/reading/<key>`) | `GET /api/confirmations/reading?key=` | loading; unknown key (`found: false`, the note and `jason readings`); current (its acts on); stale (`StaleWordsBanner`, every act but Re-read off); missing (a provision not on the shelf: the command); misquoted (the quote is not in the words: acts off, the quote shown against the words); on the board's agenda (the board item and meeting); two readings (for counsel, with its board item); counsel's reading recorded (the letter, P3); adopted (`AdoptionState`); proposal written, not yet in the profile; in the profile; rejected; skipped (with the day it returns); questions waiting on it |
| `ProvisionRecital` | inside `CandidateReading`, one per provision, in the reading's order | each provision's `Recitation` with `digestRead`, `digestNow`, `state` | the words with the version in force and the caveat; the words that answer marked (`Recitation`'s `mark`, from `quote`) with a text cue as well as the highlight; two versions under one number (each labeled, the one in force today named); not shown to be in force on the day asked; stale (digest read against digest now, with where the replaced words are kept) |
| `StandingChoice` | under the recital | the reading's `standing`, `whose`, `canon`, `boardItem`, the decision on record if any; the person from "Signed in as" | the acts in "The acts on a reading", each a `Confirm` naming the person; the field each act needs opens in place (the other reading; the letter and its passage; the decision, chosen from the decisions on record for the board item, never typed); an act the person's office may not take shows the reason in words, not a hidden button; every act but Re-read off while stale, missing, or misquoted, with the reason |
| `AdoptionState` | at the top of a reading that has left "waiting"; a line in the queue | `adoption` | none ("jason's reading: a lead. Not adopted: the board has not voted."); on the agenda ("Confirmed for the board's agenda by Jordan Example, Oct 5, 2099; board item BI-2099-04, meeting of Oct 7, 2099. Not adopted."); for counsel ("Two readings remain; the board asks counsel"); counsel's ("Recorded as counsel's reading by Jane Example, from the letter of Sep 30, 2099"); adopted ("Adopted by the board at its meeting of Oct 7, 2099; recorded by Sam Placeholder, secretary"), then "proposal written", then "in the profile" |
| `StaleWordsBanner` | first in `CandidateReading` when `state` is `stale` | `provisions[].digestRead`, `digestNow`, `kept` | which provision changed, the two digests' first twelve characters, where the replaced words are kept, **Re-read** (opens both versions; `DiffTable` is still proposed, so the fallback is two `Recitation`s, the earlier labeled with its range), and that nothing can be confirmed until a person records the re-read |
| `GoldLabelRow` | one gold row, opened from the queue (`#/confirmations/gold/<id>`) | `GET /api/confirmations/gold?id=` | the question, task, kind, and audience; the drafter's file with its verify phrases, labeled "the drafter's judgment" and never pre-selected; the candidates the index returned, each a `Doc` chip with its rank and passage; a candidate held from the question's audience (a members' question cannot be answered by a file members may not see: "held from members"); a candidate the viewer may not open (P3 outside the private view: by kind only, "opens in the private view"); the three answers; confirmed; left the set ("not a records question"); the index has no candidates (the command that builds it) |
| `GoldProgress` | above the gold rows; a line in `QueueCounts` | `progress` | n of N confirmed, by task and by kind; what a full set unlocks, in words; the scoring command (`Command`); a set scored since (the run's date and the two reaches' recall and MRR, as the run printed them, side by side and in the same type) |
| `DecisionRow` | one lesson, opened from the queue (`#/confirmations/decision/<key>`) | `GET /api/confirmations/decision?key=` | loading; unknown key; what happened, why, and the change that waits (the lesson's own words); the `DecisionBrief` where one is written (question, criteria, lettered options, facts; `BRIEF_FOOTER`), else "No brief yet" with the command; `JasonAside` collapsed; `WhoDecides`; decided (by whom, when, which option); on the board's agenda (`HeldNote` form: the board item and meeting); for the board to ask counsel (the board item, marked so) |
| `WhoDecides` | inside `DecisionRow` | `decides` | undecided; a person (records the decision behind `Confirm`); the board (proposes the board item behind `Confirm`; never an approve control); the board, to ask counsel (proposes the board item with the question for counsel) |
| `JasonAside` | inside `DecisionRow` and `CandidateReading` | a lesson's `notes`; a candidate's `note` | collapsed by default, labeled "jason's note: not part of the brief, not legal advice"; opened (the text); none ("jason adds no note"); held back ("A note that names an option is not shown beside a decision. jason does not recommend."), with `jason lessons` to read it whole |

### The words

Every state is a word the code already uses, or a phrase in [content/style.md](content/style.md), and the color only repeats it.

| Word | Where from | Meaning |
| --- | --- | --- |
| waiting | the queue | no person has acted |
| current | `ReadingState.CURRENT` | every provision's words are the words it read; acts are on |
| stale | `ReadingState.STALE` | a provision's words changed since; nothing can be confirmed until re-read |
| missing | `ReadingState.MISSING` | a provision is not on the shelf |
| misquoted | `ReadingState.MISQUOTED` | the quote is not in a provision it reads |
| on the board's agenda | the confirmation record and the board item | a person put it before the board, with their name and the day; not adopted |
| two readings remain | `ReadingStanding.TWO_READINGS` | both named, neither preferred; the board asks counsel |
| counsel's reading | `Whose.COUNSEL`, from the letter | counsel's words from the stored letter, recorded by a named person |
| adopted | the board's decision on record | the board voted at a meeting; the recording officer and the motion's words |
| proposal written, in the profile | the patch, then `Community.law_readings()` | the row waits for a person's `git apply`; then it is applied |
| rejected, skipped, re-read | the confirmation record | a person's act, with a reason where one is asked |
| decided, for the board, for counsel | the decision record | who decides, and the path |
| this file, none of these, not a records question | the gold row | the three answers |

"Approve", "accept", and "apply" appear on no control here. "Confirmed" never stands alone: it is always "confirmed for the board's agenda by NAME". A reading is "jason's reading", "counsel's reading", or "the board's reading"; a decision is "recorded"; a board question is "on the board's agenda".

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
     "state": "stale", "needs": "a person reads the changed words before any other act", "waitingQuestions": ["0a0a0a0a0a"],
     "route": "#/confirmations/reading/example-day-means"},
    {"kind": "gold", "id": "q-0017", "proposed": "2099-10-01", "age": "4 d",
     "title": "Which minutes record the vote on the paint contract?",
     "task": "example-task", "recordKind": "minutes", "audience": "board",
     "state": "waiting", "needs": "this file, none of these, or not a records question", "route": "#/confirmations/gold/q-0017"},
    {"kind": "decision", "id": "example-two-stores-disagree", "proposed": "2099-10-02", "age": "3 d",
     "title": "Two stores answer the same confidentiality question by different rules",
     "areas": ["documents"], "state": "waiting", "needs": "who decides: a person, or the board", "route": "#/confirmations/decision/example-two-stores-disagree"}
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
  "waitingQuestions": [{"id": "0a0a0a0a0a", "subject": "applies:association", "route": "#/applies?subject=association"}],
  "confirmations": [],
  "adoption": null,
  "acts": {"agenda": false, "two_readings": false, "counsel": false, "adopted": false, "reject": false, "skip": false, "reread": true,
           "why": "CIV 9901's words changed since the reading read them: record the re-read first."},
  "commands": {"recite": "jason readings --recite CIV-9901", "stale": "jason readings --stale", "reread": "jason law-history --versions --citation CIV-9901"}
}
```

`acts` is the server's answer to what this person may do now (the state, the person's office, the private view); the page renders it and works nothing out. `adoption`, once there is one: `{"state": "adopted", "decision": "dec-2099-10-07-BI-2099-04", "meeting": "2099-10-07", "recordedBy": "Sam Placeholder", "office": "secretary", "motion": "(the motion's words, as recorded on the Decisions tab)", "proposal": "onboarding/proposals/reading-example-day-means.patch", "inProfile": false}`.

`POST /api/write/confirmations/reading/<key>` (proposed; behind the write guard, `X-Jason-Token`):

```json
{"act": "agenda", "by": "Jordan Example",
 "digests": {"CIV 9901": "9f8e7d6c5b4a", "bylaws#7.2": "1122334455aa"}, "reason": ""}
```

`act` is one of `agenda`, `two_readings` (then `other`: the second reading in words), `counsel` (then `letter`, a library reference, and `passage`, found in the letter's stored text or refused), `adopted` (then `decision`: the id of a decision on record for the reading's board item, outcome approved; the meeting, the motion's words, and the recording officer are read from it), `reject` (then `reason`), `skip`, or `reread`. `digests` echoes the digest of each provision as the person saw it; a digest that is not the one on disk is refused (409) and nothing is written: "The words changed since you opened this. Reload and read them again." An `adopted` act by anyone but the president or the secretary is refused (403): "The board's adoption is recorded by the president or the secretary." A `counsel` act outside the private view is refused (403) with the reason. The answer is the record written: `{written: "readings/confirmations.jsonl", boardItem: "BI-2099-04" | null, proposal: "onboarding/proposals/reading-example-day-means.patch" | null, row: {...} | null}`. A `reread` act records only that the person read the words now on disk, with their digests; it carries no reading.

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
    {"rank": 3, "held": "viewer", "kind": "treasurer_report", "level": "P3", "note": "opens in the private view; shown by kind only"}
  ],
  "candidatesFrom": {"mode": "exact", "index": "2099-10-04", "command": "jason index --search \"Which minutes record the vote on the paint contract?\" --kind minutes -k 5"},
  "confirmed": false, "confirmation": null,
  "caveats": ["The verify phrases point at the file; they are not a quotation to recite.", "sort was true on the day written and changes as files are added: it is recomputed before scoring."]
}
```

`held` is `"audience"` when the question's audience may not see the file (it cannot be the answer; "none of these" covers it) and `"viewer"` when the person at the screen may not open it now (P3 outside the private view); the two read differently.

`POST /api/write/confirmations/gold/<id>`: `{"answer": "file", "file": "library:4001", "by": "Jane Example"}`, or `{"answer": "none", ...}`, or `{"answer": "not_records", "reason": "…", ...}`. Choosing a file the person may not open is refused (403). The answer is the row as written back to the draft file, with `confirmed: true`, `confirmedBy`, and `confirmedAt`.

`GET /api/confirmations/progress` (proposed): `{total: 42, confirmed: 12, left: 30, byTask: {...}, byKind: {...}, unlocks: "A full set scores the records tier read from the index against the library reader (recall@5, MRR@10). Then a person decides context_pack.RECORDS_FROM_INDEX, and the lessons records-tier-index-cut-differs and stub-passages-cost-first-places can close.", scoreCommand: "python scripts/eval_retrieval.py --gold data/retrieval/gold-records.json --index", lastRun: null}`.

`GET /api/confirmations/decision?key=example-two-stores-disagree` (proposed): the lesson's row (`key`, `learned`, `areas`, `what`, `why`, `change`, `status`, `guards`, `docs`, `notes`, with `notes` replaced by `notesHeld: true` when they name an option), `brief` (a `DecisionBrief` body, or null), `decides` (null, or `{who: "board", counsel: false, boardItem: "BI-2099-04", meeting: "2099-10-07", by, at}`), `decision` (null, or `{option: "B", by, at, reason}`), and `commands` (`jason lessons --open`, `jason sop KEY`).

`POST /api/write/confirmations/decision/<key>`: `{"who": "person", "option": "B", "reason": "…", "by": "Jane Example"}`; `{"who": "board", "by": ...}` proposes the board item and answers its id; `{"who": "counsel", "question": "…", "by": ...}` proposes a board item whose question is for counsel (the board asks counsel). The lesson's row in `lessons.py` is unchanged by any of these: the answer carries `rowChange`, the one-line edit a person makes (`Status.DECISION` to `Status.OPEN` or `Status.FIXED`, with the guard), as a `Command`-style block to copy.

## What the design must keep

- **Recite first; label the reading** (principle 2). Each provision's `Recitation` comes before the proposed standing: the words whole, the version in force, the caveat, the digest. The standing follows as `ReadingLabel whose="jason"`, with its built basis line ("A reading, not legal advice. The recited words govern; the board decides."). A `PLAIN` candidate shows no reading sentence: the words that answer are marked in the recital. A `TWO_READINGS` candidate shows both under `whose="open"` and prefers neither.
- **A confirmation is a person's act, never an adoption.** The board's reading exists only by its vote, recorded on the meeting's Decisions tab by the president or the secretary; the queue reads that decision and never takes a vote, a meeting date, or an officer's name from a form. Until then `AdoptionState` says "Not adopted". No control says "Approve".
- **The words are whose the label says.** "The board's reading" carries the motion's words as recorded; "counsel's reading" carries the passage of counsel's stored letter. jason's candidate sentence is never relabeled as either; where the motion's words differ from jason's, the proposal shows both, jason's labeled as jason's.
- **It makes no rule and changes no code.** A row reaches the profile as a proposal patch a person applies (`git apply`), the way an onboarding answer does; a decided lesson's row is edited by a person. The screen shows the diff to apply, never applies it. Whether adopting a reading is an operating rule on a subject that needs notice to members first (Civil Code 4355(a), 4360; `jason rule-change`) is the board's question, on its board item; jason does not answer it.
- **Stale cannot be confirmed.** `status()` runs on every read. When a digest differs, `StaleWordsBanner` is first, every act but Re-read is off, and the write refuses a digest echo that is not the one on disk. A person reads the words now on disk, records the re-read, and only then acts against the new digest, which the new record carries. A board's or counsel's reading whose words changed after adoption comes back to the queue as stale.
- **Two readings go to counsel through the board; the console picks neither.** "Record that two readings remain" names both, prefers neither, and proposes a board item ("the board asks counsel"). A lesson for counsel takes the same path. Nothing here sends anything to counsel.
- **The brief never recommends, and neither does jason** (approval-workflow, section 12). `DecisionBrief` keeps `BRIEF_FOOTER`; the store refuses a body that names a recommendation. A note jason has (a lesson's `notes`, a candidate's `note`) is `JasonAside`: collapsed by default, labeled as jason's note, never inside the brief and never above the options; the loader holds back a note that names an option, by the same test the brief store applies.
- **Who decides is recorded, not assumed.** A lesson's decision is a person's or the board's. For the board, the only path is a board item and a noticed agenda ([board-items.md](screens/board-items.md), [meetings-and-minutes.md](screens/meetings-and-minutes.md)): the row says "On the board's agenda" and links the item and the meeting; the vote is recorded in `#/room` or `#/decisions`, never here.
- **A gold label is a measurement, not a pin.** Confirming a row says what the records tier should find for one question; it changes no index and no reader. `GoldProgress` says in words what a full set unlocks and names the person's decision that follows the score. The drafter's `why` is labeled the drafter's judgment, its file is never pre-selected, and the verify phrases are labeled as pointers, not a quotation.
- **Oldest first, and a miss stays a miss** (principle 8). A kind whose store is absent shows the command that makes it, in its own place in the list, and the other kinds still list. A candidate whose provision is not on the shelf says so with the command (`jason cite`), and is not confirmable.
- **Privacy by level** (principle 6):

  | What | Level | Shown |
  | --- | --- | --- |
  | a provision's words, a statute, a public governing document | P0 | always, in `Recitation` |
  | a candidate's question, jason's sentence, a board item's title | P1 | roster people; a candidate on an executive-session subject by its general subject outside the private view, as a board item is |
  | a gold row's files (the association's records) | the file's own level | a P3 file by kind only outside the private view; a file held from the question's audience marked so |
  | a lesson's words | P1, P3 where the profile's private lessons name an owner or a matter | roster people; a private lesson's names in the private view |
  | counsel's letter and the passage that gives counsel's reading | P3 (legal) | the private view only, logged; outside it, "counsel's reading, from a letter of Sep 30, 2099" and no words |
  | the board's adopted reading | P1 (the minutes' level) | roster people; an adoption in executive session by its general subject only |

  The screen is board-only, never in the owner view, and nothing here is P4.
- **No color-only meaning.** Every state above is a word; `QueueCounts` has a table twin; a stale row carries the word "stale" in its own column; the words that answer in a recital carry a text cue as well as the highlight.
- **Nothing is written without a person** (principle 4). Every act is a `Confirm` that spells out what is recorded and in whose name, behind the write guard, with its CLI equivalent named; a write with no `by` is 400; while someone is signed in, `by` is that person.

## Where it goes

- **Overview → Confirmations** (proposed), beside Approvals: route `#/confirmations`, with `?kind=` and `?state=` filters and a count in the nav (items waiting, stale ones counted apart). One item: `#/confirmations/reading/<key>`, `#/confirmations/gold/<id>`, `#/confirmations/decision/<key>`. A URL carries a key or an id, never a name ([security-and-privacy.md](security-and-privacy.md#urls)).
- **`#/digest`**, under "Waiting on a person" ([today.md](screens/today.md)): `QueueCounts` as one line ("3 readings, 30 gold labels, and 7 decisions wait on a person; 1 is stale"), linking to the queue.
- **Governing documents** (`#/documents`, [governing-documents.md](screens/governing-documents.md)): a candidate that reads the section shown appears in its READINGS band as "jason's reading (a lead; waiting for a person)", linking into the queue. A reading adopted by the board appears there as the board's, with the adoption date, once the profile row is applied; until then, as "adopted Oct 7, 2099; not yet in the profile".
- **Board action items** (`#/actions`) and **Decisions** (`#/decisions`) stay the board's. A reading or a decision put to the board arrives there as a board item; its vote is recorded on the meeting's Decisions tab (`DecisionCard`, `RollCall`); the queue row shows "On the board's agenda" until the decision is on record, then "adopted" (or the board's word: denied, tabled) with a link to the decision.
- **What applies** (`#/applies`, [handoff-applicability-questions.md](handoff-applicability-questions.md)): a fact question that waits on a reading links here, and a reading lists the questions waiting on it.
- **Approvals** (`#/approvals`) is unchanged: nothing here is an engine approval ([approvals.md](screens/approvals.md)).

**Loaders and writes to add** (all proposed; a loader wraps a function that exists, except where marked "to write"):

| Name | Function behind it | Reads | Writes |
| --- | --- | --- | --- |
| `confirmations` | `jason.web.extra.confirmations:confirmations` (to write) over `law_readings.readings` + `status` (candidates: rows with `whose: jason`), the draft gold file's rows with `confirmed: false`, and `lessons.lessons(community)` filtered to `Status.DECISION`, each with its proposed day; the intake queue's fact questions whose record names a reading | disk only | — |
| `confirmations-reading` | `law_readings.recite(citation, data_dir, readings, as_of, community=)` per provision, `law_readings.status`, `provision_text`; the reading's board item (`tasks.board_items.load`) and its decision (`data/board/decisions.json`); the person's office and private view (`jason.web.access`) for `acts` | disk only | — |
| `confirmations-gold` | the draft file's row; candidates from `passage_index.search(query, data_dir=..., scope=..., mode="exact", k=5)` (no model, no GPU lock), held files by `tasks.index_sources.library_holds`, the viewer's level by `jason.web.access` | disk only | — |
| `confirmations-progress` | the draft file's counts; the last run's JSON under `data/retrieval/runs/` where one names the gold file | disk only | — |
| `confirmations-decision` | `lessons.lesson(key)` or the community's own; the brief from `data/board/` where one is written; `tasks.board_items.load` for the item | disk only | — |
| write `confirmations/reading` | `jason.web.extra.confirmations:write_reading` (to write): appends `data/readings/confirmations.jsonl`; for `agenda` and `two_readings`, `tasks.board_items.propose` with the reading as evidence; for `counsel` and `adopted`, writes `data/onboarding/proposals/reading-<key>.patch` with the `LawReading` row for the profile (the pattern of `onboarding_answers.propose`); refuses a stale digest echo, a missing `by`, an `adopted` act without an approved decision on record or by anyone but the president or the secretary, a `counsel` passage not in the letter's text | — | jason's own stores; the profile only by a person's `git apply` |
| write `confirmations/gold` | `write_gold_label` (to write): sets `confirmed`, `confirmedBy`, `confirmedAt`, and the answer on the row, written whole under the store lock | — | `data/retrieval/gold-records.draft.json` |
| write `confirmations/decision` | `write_decision` (to write): appends `data/lessons/decisions.jsonl`; for the board (and for counsel, through the board), `tasks.board_items.propose` with the lesson as evidence, signed by the person | — | jason's own stores; the lesson's row only by a person's commit |

The candidate store is a question for the build: today a candidate lives in a person's private notes as the row it would become, and `Community.law_readings()` holds only confirmed rows. The loader needs candidates as `LawReading` rows with `whose: jason` on disk, `data/readings/candidates.json` (proposed), loaded into the record before any screen sees them, so that `status()` and `recite()` treat a candidate exactly as a reading.

## Accessibility

As [components.md](components.md#accessibility), with these particulars.

- **The queue is a real table** (`DataTable`): kind, title, proposed day, age, state, and what it needs, each a column with text; sorted "oldest first" and the sort announced; a caption ("Waiting on a person, oldest first"). Filters sit in a labelled group with a polite live region for the count ("12 of 51 items"). A row is a link to its page, in DOM order; no grid roles.
- **A recital is a `<figure>`** with `<blockquote>` and `<figcaption>` (the citation, the version in force, the caveat, the digest), as `Recitation` renders it; the reading follows as an `aside` with its label, as `ReadingLabel` renders it. A screen reader meets the words before the reading, always. The words that answer are a `<mark>` with visually hidden "the words that answer:" before and "end of the words that answer" after, and an underline as well as the highlight (1.4.1), since `<mark>` alone is not announced.
- **`StaleWordsBanner` is `role="alert"`** at the top of the page when the state is stale, missing, or misquoted, and the disabled acts each carry `aria-describedby` naming the reason. "Re-read" moves focus to the first changed provision.
- **`StandingChoice` is a `<fieldset>`** with a legend ("Your act on this reading, as Jane Example"); the acts are a radio group; the field each act needs appears in place with a visible label, and an error names the field: "Record counsel's reading needs the letter and the passage of it that gives the reading." "The board's adoption is read from its decision: choose the decision on record for board item BI-2099-04."
- **Every act is a `Confirm`** (two clicks, the record spelled out): "Put on the board's agenda: records that Jordan Example read CIV 9901 (digest 9f8e7d6c5b4a) and bylaws 7.2 (digest 1122334455aa) on Oct 5, 2099, and proposes board item BI-2099-04 for the next agenda. This adopts nothing." After the act, the result in `role="status"`, in place; focus stays on the row.
- **`DecisionBrief`'s options are lettered headings**; `JasonAside` is a `<details>` with a summary that carries its full label; `WhoDecides` is a radio group whose board choices say in text that they propose an agenda item and nothing else.
- **`GoldLabelRow`'s candidates are a list**, each a `Doc` chip (its own focus and keyboard behavior) with the rank and the passage in text; the three answers are radio buttons, none checked at first, the file choice listing the drafted file and each candidate by name.
- **Shortcuts** as [patterns.md](content/patterns.md#keyboard-use): `j`/`k` between rows, `?` lists them, single-key shortcuts off by default for anyone who asks; nothing requires a drag; every target 24 by 24 CSS pixels or spaced to pass.
- **Nothing times out.** A partly filled act (a reason typed, the other reading entered) stays in the form until the person leaves the page; the store holds nothing until `Confirm`.

### The phone layout (under 720 px)

- The queue's rows become cards: the title first, then kind and state as words on one line, then "needs" and the age. The filters collapse into a disclosure with the active count in its summary. A stale card says "stale" in words on its first line, not only in a mark.
- A reading's page stacks: `StaleWordsBanner`, the question, each `ProvisionRecital` in order (long words wrap inside the page, never sideways), the proposed standing, `JasonAside`, then `StandingChoice` at the foot, not sticky: it is one decision at the end of a reading, not a bar over a list. Each required field opens under its act. Under the question, a link "Go to the words that answer" moves focus to the marked words; the recital stays whole, never cut to an excerpt.
- On a stale reading, Re-read stacks the two versions: the words read first, labeled with their digest and range, then the words now on disk, labeled the same way; a heading for each, never side by side.
- `AdoptionState` stays above the recital in full, with its words (who, which meeting, not adopted), never shortened to a mark.
- A gold row stacks the question, the drafted file, the candidates as cards, then the three answers.
- A decision's brief uses `DecisionBrief`'s stacked form (no `columns`); `WhoDecides` follows it.
- "Go to" replaces the nav as `ConsoleShell` does; the dock's drawers still pin at 1200 px and float below.

## Decisions for the design

Settled by the axioms in this pass, and why:

- **The board's adoption is not recorded in the queue** (was decision 3). Principle 5: a board approval is a vote at a meeting, recorded by the president or the secretary, and no one clicks approve for the board. The vote is recorded once, on the Decisions tab, as every other vote is (the pattern [response-standards-design.md](../response-standards-design.md) uses for policy rows); the queue reads that decision, and its one act is to write the profile row from it.
- **No director's reading.** "jason proposes; the board adopts", and `Whose` has no director. A director's act is to put a candidate before the board.
- **A question for counsel goes through the board** (was half of decision 9). "Where two readings remain, say so. The board asks counsel" (AGENTS.md). Whether the packet also carries it stays open (below).
- **The words of a board's or counsel's reading are theirs.** "Only stored words" and "label every reading": the motion's words as recorded, or the passage of counsel's stored letter.
- **A note that recommends is not shown beside a decision.** "jason never recommends" (approval-workflow, section 12).

Still open:

1. **One list or three tabs.** The brief says one list, oldest first, so the oldest proposal is seen whatever its kind. Decide whether a kind filter is a tab row (`Tabs`) or a filter in the table, and how a stale reading reads in a list where most rows are gold labels (42 of 52 today).
2. **How much of a recital is on the row.** A row that recites every provision is long; one that hides them invites deciding without reading. Decide whether the queue row shows the question alone and the page recites, or the row shows the first provision's citation and digest state as text.
3. **The decision picker for an adoption.** The adoption act chooses among decisions on record for the reading's board item. Decide how the choice reads when there is one (shown, not a picker) and when the board tabled it and decided at a later meeting (two decisions, one approved).
4. **Skip's return.** A skipped item returns after a time or stays skipped until someone unskips it. Decide the default (the brief proposes 30 days, as a word on the row: "skipped by Jane Example; returns Nov 4"), and whether a skipped candidate still appears in the Governing documents READINGS band.
5. **Re-read as its own act.** Recording a re-read before another act is two confirms. Decide whether a stale reading's page offers the re-read and the next act as one form whose first part is the two versions, so the digest echo and the act are one record.
6. **Candidates for a gold row.** An exact search at request time is quick and needs no model; a dense search would hold the GPU lock. Decide whether the row shows exact candidates only (with the mode named), or candidates a command computed and stored beside the row with its date.
7. **Progress and the score.** Decide how `GoldProgress` shows a set scored since (the run's recall@5 and MRR@10 for the two reaches, as the run printed them) without the screen seeming to pick a reach: the choice is a person's, named as such.
8. **The decision brief's absence.** Most DECISION lessons have no written brief. Decide the state of a `DecisionRow` with none: the lesson's words alone and the command that writes a brief, or an inline brief form (question, criteria, options) a person fills before anyone decides.
9. **The packet.** A reading marked "two readings remain" and a lesson for counsel both become board items. Decide whether the packet also carries them as a line (`{REPORT:conflicts}` carries conflicts; nothing carries readings yet).
10. **The candidate store.** Candidates are written by a person today. Decide whether the console offers a form to enter a candidate (a question, provisions, a proposed standing, labeled jason's or the entrant's), or candidates come only from the terminal.
11. **A person's decision, seen by the board.** A lesson a person decides is recorded with their name and never reaches the agenda. Decide whether `#/digest` lists the month's decisions a person recorded, so the board sees what was decided outside a meeting.

## Not part of this pass

- Any write outside jason, and any engine kind: a confirmation is a signed record in jason's own store, never an approval.
- Applying a proposal patch to the profile, or editing a lesson's row: a person's `git apply` and commit.
- The board's vote on a reading or a decision: `#/room`, `#/decisions`, and the board loop.
- Sending anything to counsel, or counsel acting in the console: counsel's reading arrives as a letter a person records.
- A confirm tool in `jason-mcp`: it stays read-only, and reads the queue through the same functions.
- `DiffTable` (two versions of a provision side by side) and `CiteBox`: still proposed in [components.md](components.md#still-proposed); `StaleWordsBanner` falls back to two `Recitation`s.
- Entering a candidate reading from the console (decision 10), and converting the private candidates note into the candidate store: a person's work, as [ingestion-and-review.md](../ingestion-and-review.md) says ("jason converts none").
- The owner view: this screen is board-only at every phase.
- The previews: the design project's authored preview for each component follows the build, as for the earlier handoffs; fixtures will be `ui/src/components/confirmationsqueue.test.tsx` and its siblings, from the sample data above.
