# Handoff: the association's rules as records, and the way a change reaches them

For the design pass on the screens where the association's **rules are read as records** (the rule in force on a day, its history, the grant it rests on, how it compares with the working Doc, where it was applied) and where **a change to a rule is drafted, checked, noticed, put to the board, and recorded once adopted**. The design is settled in [../rule-records.md](../rule-records.md). What exists today: the rule records and their versions (`jason.community.rules_document`: `RuleRecord`, `RuleVersion`, `version_on`; `jason document-template --export-records`, `--records stored`), the proposed change and its member notice (`jason rule-change`, `jason.tasks.rule_change`; the built `#/rules` screen and `GET /api/rule-changes`), the adoption events (`jason.community.manual`: `AdoptionEvent`, `adoption_history`), the board items and the decisions (`#/actions`, `#/decisions`, `data/board/decisions.json`), and the grants and the 4355 reading (`jason rules`, [handoff-rules-and-authority.md](handoff-rules-and-authority.md)). **No loader serves the records or a proposal as data, no screen shows a rule's history, and every write below is proposed.**

The format follows the earlier handoffs ([handoff-applicability-questions.md](handoff-applicability-questions.md); [handoff-confirmations-queue.md](handoff-confirmations-queue.md)). The words on screen follow [content/style.md](content/style.md), the patterns [content/patterns.md](content/patterns.md), and the components [components.md](components.md). Built parts it uses: `Recitation`, `ReadingLabel`, `DecisionBrief`, `Pill`, `Doc`, `DataTable`, `Findings`, `Caveats`, `Command`, `Confirm`, `SecondConfirm`, `Stat`, `Card`, `Tabs`, `StageSteps`, `HeldNote`, `Stamp`, `Seal`, `QuestionCard`, and `RemoteView`. Most rows of the components table are an arrangement of one of them; its "Built from" column says which.

**How this page meets the other handoffs.** Each shares a component or a question with this page; each is linked where it applies and not repeated.

| Neighbour | What it shares with this page | Where this page says so |
| --- | --- | --- |
| [handoff-rules-and-authority.md](handoff-rules-and-authority.md) | the route family `#/documents/rules` (this page adds a band to it); `GrantRecital`, `TierWord`, `AuthorityStanding`, and `ReachLine` are reused unchanged as a record's grounds; its `RuleChangeHandoff` ends at a link, and **this page is where that link goes** (`#/rules/change/new?subject=`), so its "builds nothing" stays true of that component | "Where it goes"; decision 1 |
| [screens/board-items.md](screens/board-items.md) and [approval-workflow.md](approval-workflow.md#12-the-board-decides-by-vote) | a proposal reaches the board as a board item in `#/actions`; the vote is recorded on the Decisions tab by an officer; **no control here approves** | "The vote is read, never taken" |
| [handoff-confirmations-queue.md](handoff-confirmations-queue.md) | a question of what words *mean* (whether a rule governs the common area, whether a correction changes meaning) is a reading confirmed there; a **fact** the notice catalog needs is answered in the applicability queue | "The reach and the facts" |
| [handoff-applicability-questions.md](handoff-applicability-questions.md) | `rule_scope` and `rule_change` are that page's event facts; a proposal asks them in place and shows the rows they decide (`EventFactsPicker`, `CatalogGroups`) | "The reach and the facts" |
| [handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md) | `AsOfControl` and `AsOfBanner` hold the day; `VersionLine` and `VersionTimeline` are the shape of a rule's versions; `QuoteCheck` checks the adopted words entered from the minutes | "The rule on a day, and its history" |
| [handoff-programs.md](handoff-programs.md) | an operating rule is the program catalog's `OPERATING_RULE` instrument; its `ProposalFlow` is the same shape as this page's `ChangeFlow` for a program's draft, which names its adoption step; this page owns the rule's record, that page the program's adoption row | "The change flow" |
| [handoff-collection-workspace.md](handoff-collection-workspace.md) and [screens/meetings-and-minutes.md](screens/meetings-and-minutes.md) | a hearing or an architectural decision is a *use* of a rule and links to the record | "Where a rule was applied" |
| [screens/notices.md](screens/notices.md) | the notice rows, the delivery ledger, and the clock; the member notice is a Gmail draft a person sends | "The notice and its clock" |
| `handoff-citations.md` (peer's, not yet committed) | `CitationChip` for a statute a rule or a check cites | "The checks" |

## The idea in one line

A rule is **a record you can read on any day**: its words as the board adopted them, the grant they rest on, every version with who proposed it and who recorded its adoption, the working Doc beside it with its differences shown and never merged, and the places the association applied it. A change is **a proposal that moves through acts a named person records**, from a draft with its reason, through the notice the law requires when the subject calls for one and the board's vote, to a person recording that the board adopted it; **jason drafts, checks, and keeps the history, and the board adopts**. Nothing is edited once adopted; a miss stays a miss.

## The components

| Component | Built from | Where it renders | Data | States to design |
| --- | --- | --- | --- | --- |
| `RuleRecordBook` | `DataTable`, `Stat` | the band **Records** of `#/documents/rules` | `GET /api/rule-records` | no records stored and none derivable (the command: `jason document-template --export-records` or `jason manual --classify`); derived (not stored: a note says so); stored; filtered to none; one document's classification failed (that document's note and command; the rest stand); counts by status in text beside any bar |
| `RuleRecordRow` | `Pill`, `Doc` | each row of the book | one record, summary | number, heading, `RecordStatus`, the version in force today with its adoption day, subjects, grant standing word, an open proposal marker ("1 proposal open"), a use count; a rule with no version in force today ("no version in force on this day": a visible line, the record's gap) |
| `RecordStatus` (a `Pill` preset) | `Pill` | rows and pages | `status`, `adoptionOnRecord` | **proposed** · **noticed** · **adopted** · **in force, adoption not on record** · **suspended** · **repealed** · **expired**; always the word, with the day it began; never color alone; "in force, adoption not on record" is never shown as "adopted" |
| `RuleRecordPage` | `Tabs`, `Card` | `#/documents/rules/record/<id>` | `GET /api/rule-record?id=&as_of=` | tabs: **Words** (the version in force, recited whole), **History**, **Grounds**, **Compare**, **Uses**, **Audit**; unknown id (the note and the list); id renumbered (the old address resolves: "renumbered, not changed", both numbers); repealed (last words, the day); a proposal pending (a link, and "not in force") |
| `RecordSource` | `ReadingLabel` | under the words | `source` | which of the three sources the words are from, in words: **the adopted text** (the minutes' file, linked as a `Doc`) · **the noticed text** · **the document's words as read, adoption on record** · **imported, adoption not on record**. A working draft is never a source and the line says so on a record that has one. The caveat is the loader's: "jason's text of an adopted rule. The minutes and the recorded instrument govern." |
| `RuleHistory` | `VersionTimeline` preset, `DiffTable` | the History tab | `GET /api/rule-record-history?id=` | every version in order, newest first, each: the words and a diff to the one before, the adoption (day, board item, decision, meeting), the notice (ledger keys and delivery days), **who proposed it** and **who recorded the adoption**, what it superseded; a version in force on the screen's day marked in words; a withdrawn or defeated proposal listed, labeled ("withdrawn Oct 9, 2099 by Sam Placeholder"; "not adopted: the board's decision of Nov 17, 2099"); a gap before the first version ("the record does not show which words were in force before Mar 1, 2090") |
| `RecordGrounds` | `GrantRecital`, `TierWord`, `ReachLine`, `OnFileLine` | the Grounds tab; a proposal's checks | `authority[]` of the record | each grant the rule rests on: its words recited whole with citation and version, then under a `ReadingLabel` the tier word, holder, subjects, the reviewer; **no grant found** (a miss with `jason rules --find`; "a question for the board and counsel, never an accusation"); a general power only (set apart); a grant in guidance (set apart, counted nowhere); a review state; a statute the rule is made under (a `CitationChip` once built, else the cite) |
| `CompareWord` (a `Pill` preset) | `Pill` | `DocVersusRecord`; the book's filter | `compare` | **same** · **the record is behind** · **the Doc ran ahead** · **changed with no adoption found** |
| `DocVersusRecord` | `Discrepancy` preset, `DiffTable` | the Compare tab; the book's "differs" filter | `GET /api/rule-record-compare?id=` | the two sets of words **side by side**, never merged: the adopted version (citation, day) and the working Doc's words (the revision and its time); the word; the acts the word allows, each a `Confirm` below; Doc not read or no outline (the command); the Doc holds a **pending suggestion** (never counted: "not accepted, not a rule"); source is `records` and the Doc is "edited" (left alone) or in "conflict" (nothing written) |
| `ChangeList` | `DataTable`, `Pill` | `#/rules` (the built Rule changes screen) | `GET /api/rule-changes` (built) plus `GET /api/rule-proposals` | each change by source: **in the specification** (built rows, read only) and **proposal by NAME** (a person's draft); the stage in words; the next date and its row; a draft the viewer wrote ("yours"); filtered; empty ("No proposed changes. 3 adopted this year.") |
| `ChangeFlow` | `StageSteps` preset | the top of a proposal; `#/rules/change/<key>` | `stage`, `stages[]` | **drafting** · **reason and purpose written** · **subject and reach read** · **checked** · **before the board** · **noticed** (a delivery on record) · **decided** (read from the Decisions tab) · **adoption recorded** · **carried out**; each with the person and the day, its gate in words ("needs: the facts the notice catalog asks"); a stage that does not apply (`not listed`: no notice) shown as "not needed: jason's reading of Civil Code 4355" with its sections, never skipped silently; **withdrawn**, **tabled**, **not adopted** end it |
| `ChangePage` | `Card`, `Tabs` | `#/rules/change/<key>` | `GET /api/rule-proposal?key=` | tabs: **Words**, **Reason and effect**, **Reach**, **Checks**, **Board**, **Notice**, **Effects**, **Audit**; unknown key; the viewer is not the drafter (read only, with the drafter's name); the draft is `board` confidential (a `HeldNote`: not shown in the open view) |
| `ChangeDraftForm` | `Confirm`, `DiffTable`, `Command` | the Words tab | `proposed[]` | for each record: the version in force beside the proposed words (diff), the brackets counted and listed ("2 choices left for the board"); a new rule (no version in force), a repeal (empty words by repeal), a split or merge; **Save my draft as Jane Example** is a `Confirm` that spells out "This saves a draft. It changes no rule." Disabled for a record with a proposal already open on the same rule ("open in proposal X": two proposals on one rule need a person to say which first); a draft started from a Doc difference is marked "started from the Doc's words" |
| `PurposeEffectFields` | `Doc` | the Reason and effect tab | `reason`, `purpose`, `effect` | **two** texts, never one: the **reason** (board confidential, never noticed) and the **purpose and effect** (the description the notice carries). The notice's own order is shown: the proposed text first, then the description, as the statute orders it (a `Recitation` of the sentence from the shelf, with the version in force). The description is labeled "the board's own description once adopted; jason's draft until then" |
| `ReachGate` | `ReachLine`, `EventFactsPicker`, `HeldNote`, `Command` | the Reach tab | `subject`, `reach`, `facts`, `rows` | the subject (closed list, `other` with the person's word); jason's reading of Civil Code 4355 as a labeled reading (listed, depends, not listed, with the sections it cites); `depends` states **both readings**, "the board asks counsel", and "the course lawful under either reading is the notice"; `not listed` states "Civil Code 4355(b) may take the change out of 4360 and 4365" as a reading, and that a **one-off decision on a specific matter needs no rule** (a link: record it as a decision, not a rule); the two facts (`rule_scope`, `rule_change`) answered in place with `by`, the catalog rows they decide, and the rows still undetermined ("needs: rule_scope"); a missing fact is a question, never a default |
| `ProposalChecks` | `Findings`, `CheckRow` | the Checks tab | `GET /api/rule-proposal-checks?key=&as_of=` | authority; reach; conflict with the law or a governing document; duplicates the declaration; statutes cited (the law in force on the day); recited words verified; open brackets; the clock; each a **lead** in words with its reader labeled (rules, model, agree) and its own recital; **not run** vs **run, nothing found** vs **found** (a miss and a clean read are different words); a check that cannot run (no outline, no shelf) shows its command |
| `CheckRow` | `Pill`, `ReadingLabel`, `Recitation` | `ProposalChecks` | one check | the question in words; the words recited first (the provision), then the reading; the standing (found / nothing found / not run); the flag state: **unacknowledged** · **acknowledged by NAME on DAY: "note"**; the conflict row says "a lead for a `Conflict` row; only the board, counsel, or an amendment resolves a conflict" |
| `FlagAck` (a `Confirm` preset) | `Confirm` | each flagged `CheckRow` | `flag`, `note`, `by` | **Record that I have read this flag, as Jane Example**, with a required note; says "This records that a person read it. It does not resolve it." No second person unless decision 2 says so |
| `NoticeClockLine` | `DueUnder`, `SourcedDate`, `Command` | the Notice tab; the Board tab | `clock` | each date **from the row it came from** (the proposed-change row's timing and method; the meeting schedule's decision dates that satisfy it), shown with the row key as a source: notice by, agenda notice by, comments due, decision, notice of adoption by, members' reversal window; **no date from a row not read** (a missing schedule: "needs the meeting schedule", with the command); the delivery state read from the ledger: **not sent** · **draft saved, no recipients** · **sent, delivery not read** · **delivered to n of n** · **after the deadline**; "28 days have passed" only after a delivery on record |
| `NoticeDraft` | `Doc`, `Command`, `Confirm` | the Notice tab | `notice` | the member notice as `jason rule-change` builds it from the proposal: the text, then the purpose and effect; the elements check from `jason notice-check` ("the text, the purpose and effect, the comment deadline: each present"); **Save the draft as Jane Example** (Gmail draft, no recipients; "a person addresses and sends it"); the draft's saved key; the console never sends |
| `BoardLink` | `HeldNote`, `Stamp` | the Board tab | `boardItem`, `decision` | the board item (its status, owner, meeting) as a link to `#/actions`; **Put it before the board as Jane Example** (a `Confirm`; it proposes a board item carrying the text, the reason, the reach reading, the checks, and the clock as evidence; it recommends nothing); the motion draft (`MotionDraft`: the proposed words by reference, brackets open, edited by a person, mover and second recorded by the secretary); then **the vote, read** |
| `VoteOnRecord` | `Stamp`, `RollCall` view | the Board tab | `decision` (read from `data/board/decisions.json`) | **not yet decided** · **carried** · **failed** · **tabled** · **continued**, with the meeting, the motion's words, the roll call by name, the recording officer; read only; there is **no control that takes or approves a vote** on this page; the text "The board decides at a meeting. The vote is recorded on the Decisions tab by the president or the secretary." |
| `AdoptionRecord` | `Confirm`, `QuoteCheck`, `DiffTable` | the Board tab, after a carried decision | `adoption` | **Record the adoption as Sam Placeholder** (an officer who records votes); the decision, the meeting, the motion's words, the recording officer **read from the record, not typed**; the **adopted words** entered from the minutes (a library file, shown beside the entry) with the verbatim check ("every word is in the file"); the diff to the noticed words ("equal" or "the board changed these words at the meeting": a reading for counsel on whether it needs another notice, not decided here); the notice's ledger keys; refused without a carried decision, without the minutes, or on a failed check; "This records that the board adopted it. It does not adopt it." |
| `EffectsPlan` | `DataTable`, `Command` | the Effects tab | `GET /api/rule-proposal-effects?key=` | the list of section 6.6 of the design: the version in force (derived: nothing to do); the Rules document and the manual (a plan: "will change"; `jason document-template ...` as a `Command`; "a person runs it"); the packet parts; the notice of adoption (its row, recipients, method, and clock); the annual policy statement's next edition (which part by subject; "whether a mid-year notice is also needed is the row's, and a question for the person"); citations (nothing to do: they resolve to the record id); each item **to do** · **done by NAME on DAY** · **not needed (why)**; nothing runs from this tab |
| `EffectRow` | `Pill`, `Command` | `EffectsPlan` | one effect | the effect, what it reads, the act, and the person's record ("Recorded as done by Jane Example") |
| `RuleUseList` | `DataTable`, `Stat` | the Uses tab | `GET /api/rule-uses?id=` | each linked use: its kind (notice, hearing, request, response, decision), the day, **the version in force that day** (with a link), the outcome as the use's own record states it, a link to the use (`Doc` or board screen); counts by outcome in text; **no use linked** (a miss, "not a finding that the rule was not applied"); a use whose day falls where no version was in force (shown, labeled); the open view shows references and no names |
| `RuleUseRow` | `Pill`, `Doc` | `RuleUseList` | one use | the line above; a use linked to a version that is superseded shows it as the version of its day, never rewritten to the current one |
| `ChangeAudit` | `DataTable` | the Audit tab; `RuleRecordPage`'s Audit tab | `GET /api/rule-events?key=|id=` | the event log in order: act, person, time, the record and version, the evidence; filter by person and act; a **correction** is a line that names the line it corrects (the original stays); empty log for a derived record ("nothing recorded since jason first read it") |

**One component across handoffs.** `Discrepancy` is the shared component for two stored readings that disagree (the inspections handoff, `FactConflictCard`); `DocVersusRecord` is that component with the four words above. `StageSteps` is the programs handoff's shape for a draft's way to the board; `ChangeFlow` shares it. `VersionTimeline` and `VersionLine` stay the as-of handoff's, and `RuleHistory` is a preset, not a second timeline. `MotionDraft` is the improvement handoff's. None of these is redefined here.

## The vocabulary

Every word is the code's or the design's, so the console and the terminal agree; no state is color alone.

**A record's status** (`RecordStatus`): proposed · noticed · adopted · in force, adoption not on record · suspended · repealed · expired. Derived from the log by the loader; the client never computes it.

**A source of the words** (`RecordSource`): the adopted text · the noticed text · the document's words as read, adoption on record · imported, adoption not on record. A working draft is never one of them.

**A compare word** (`CompareWord`): same · the record is behind · the Doc ran ahead · changed with no adoption found.

**A change's stage** (`ChangeFlow`): drafting · reason and purpose written · subject and reach read · checked · before the board · noticed · decided · adoption recorded · carried out; and its endings: withdrawn · tabled · not adopted.

**A check's standing** (`CheckRow`): not run · run, nothing found · found. A flag: unacknowledged · acknowledged. Never "pass" or "fail".

**A reach** (`Reach`, jason's reading of Civil Code 4355): listed · depends · not listed. It decides nothing.

**An effect's state** (`EffectRow`): to do · done by NAME · not needed (why).

**Never** "approved", "rejected", "valid", "invalid", "violation", "unauthorized", "enforceable", "consistent" or "inconsistent" (of a rule's use), or "overdue" of a date jason did not read from a row. A proposal's board decision is **carried** or **failed**, the words a person recorded.

## The rule on a day, and its history

`?as_of=YYYY-MM-DD` on the record's route, held by `AsOfControl`, reads the version in force that day. On today the control says "As of today, Oct 5, 2099". On another day `AsOfBanner` says "The rules on this screen are read as of Mar 1, 2099. Deadlines and proposals stay today's." The Words tab recites the version's words whole with its adoption (day, board item, decision, notice), then the loader's caveat. A day before the first version shows the same words the statutes use ("the record does not show which words were in force on this day"). A day when the rule was suspended is shown as that, with the suspension's dates. The History tab ignores the day except to mark the version in force on it.

**A citation resolves to the record.** The cite box takes an address of a rule (`jason://rules/rules#R-12`, or an old number); the answer is the record, "renumbered, not changed" where the number moved, and, with `as_of`, the version of that day. A citation inside an adopted rule's own words keeps those words.

## The compare, and which wins

The Compare tab answers one question: do the working Doc's words equal the adopted words? The rule is the adopted version in either source mode. The tab shows the two sets side by side with the word and the acts the word allows:

| Word | The acts offered (each a `Confirm` in a named person's name) | What each records |
| --- | --- | --- |
| same | none | nothing |
| the record is behind | **Record the adoption found in the minutes as Jane Example** (opens `AdoptionRecord` in its past-day form: the day, the evidence file, the adopted words checked against it) | an adoption event with `source: minutes` |
| the Doc ran ahead | **Link the proposal** (a proposal with those words is on file) | a link; nothing in force changes |
| changed with no adoption found | **Take the Doc's words as a proposal as Jane Example**; **Leave it as a note for the board** (a board item "changed with no adoption found") | a draft proposal started from the Doc's words; or a board item |

There is **no act that makes the Doc's words the rule** and **none that edits the Doc**; to restore the adopted words a person edits the Doc in Docs, and the tab says so. Where the document's `source` is `records`, the Doc is generated from the records, and an edit to it is shown as "edited" with the same acts.

## The change flow

The screen follows the flow of [../rule-records.md](../rule-records.md#61-the-acts-in-order) in this order, each stage a tab of `ChangePage` and a step of `ChangeFlow`. Each act is a `Confirm` in a named person's name, through the write guard; the words on its button say what the person signs.

| Act | The words on the button | What it records |
| --- | --- | --- |
| Start a proposal | **Start a proposal as Jane Example** | the key, the records touched, the person, the day |
| Save the words | **Save my draft as Jane Example** | the proposed version per record |
| Save the reason and the purpose and effect | **Save the reason and the description as Jane Example** | the two texts |
| Say the subject and the facts | **Record the subject and the facts as Jane Example** | the subject, `rule_scope`, `rule_change`, each with `by` |
| Acknowledge a flag | **Record that I have read this flag, as Jane Example** | the note |
| Put it before the board | **Put it before the board as Jane Example** | a board item with the evidence |
| Save the notice draft | **Save the draft as Jane Example** | a Gmail draft with no recipients; the saved key |
| Record the adoption | **Record the adoption as Sam Placeholder** | the adoption event |
| Record an effect done | **Record this as done by Jane Example** | the effect's state |
| Withdraw | **Withdraw this proposal as Jane Example**, with a reason | the draft is kept, labeled withdrawn |
| Repeal, or suspend | **Propose a repeal as Jane Example**; **Propose a suspension** | a proposal whose version is empty by repeal, or an event with the day it ends; whether a suspension is a rule change is a question for counsel shown on the page |

**Emergency and one-off.** An emergency rule change shows the catalog's emergency rows, the grounds the person states as a fact, and, once adopted, the expiry from the row; "an emergency rule that ended is not readopted as an emergency rule" is the row's. A **one-off decision on a specific matter** is not a rule: the Reach tab says so and links to the board item as a decision. **A rule that duplicates the declaration** is a `copy`: the page shows the declaration's words beside it and the copy's state; "the rule's words are not replaced by a reference to the declaration; changing them is a rule change, or merely repeats the governing documents: two readings, counsel reads" ([../rule-records.md](../rule-records.md#64-emergency-and-special-paths)).

### The reach and the facts

The Reach tab is the page where a **fact** and a **reading** meet and stay apart. The two catalog facts are answered here, with `by`, and decide which notice rows apply. The reach is jason's reading, shown after the statute's own words from the shelf (`Recitation`, never typed here). Where two readings remain, the page offers **Put "the board asks counsel" on the board's item as Jane Example**, and counsel's reading is recorded in the confirmations queue, not here.

### The vote is read, never taken

The Board tab shows the board item, the motion's draft, and then the vote **read from the Decisions tab**. There is no approve, vote, or adopt control anywhere on `#/rules/change/<key>`. A proposal whose decision is **carried** unlocks `AdoptionRecord`, for an officer who records votes; **failed**, **tabled**, and **continued** show their stamp and end or park the flow as the decision says.

## Where a rule was applied

The Uses tab lists the places the association applied the rule, each linked to its own record, with the version in force that day. It is **a list, not a finding**: it states "the same version applied" or "a later version applied" and counts outcomes as recorded, and it never says a rule was applied consistently or not. "No use linked" is shown as that. A use is linked by the task that records it (a hearing, an architectural decision, a response) citing the rule's address, or by a person (`jason rule-records --link-use`); the link records who.

## Data shapes

Made-up documents, people, rules, and dates. A recited sample is a bracketed placeholder; on the screen the words come from the stored version, never from this page. Keys are proposed; they follow the existing store shape (`RuleRecord.to_dict`) where one exists.

`GET /api/rule-records?document=rules-and-regulations&status=&subject=&as_of=2099-10-05` (proposed; `rules_documents.prepare`, `RuleBook`):

```json
{
  "found": true, "asOf": "2099-10-05", "community": "Example Village HOA", "document": "rules-and-regulations",
  "source": "derived from the classification", "stored": false,
  "counts": {"records": 41, "adopted": 33, "adoptionNotOnRecord": 6, "proposed": 1, "noticed": 1, "suspended": 0, "repealed": 0, "noGrantFound": 4, "differsFromDoc": 3},
  "records": [
    {"id": "rules#R-12", "number": "R-12", "title": "Quiet hours", "kind": "rule", "subjects": ["noise"],
     "status": "adopted", "adoptionOnRecord": true, "inForce": {"version": "v2", "adopted": "2098-04-14", "boardItem": "BI-2098-07"},
     "grounds": {"standing": "authority named, rules on file", "grants": ["ra-0007"]},
     "openProposals": [], "uses": 3, "compare": "same"},
    {"id": "rules#R-3", "number": "R-3", "title": "Trash containers", "kind": "rule", "subjects": ["trash"],
     "status": "adopted", "adoptionOnRecord": false, "inForce": {"version": "v1", "adopted": null, "boardItem": ""},
     "grounds": {"standing": "rules on file, no grant found", "grants": []},
     "openProposals": ["rc-0004"], "uses": 0, "compare": "changed with no adoption found"}
  ],
  "notes": ["Derived from the classification: no record is stored. jason document-template --export-records keeps them as data."],
  "caveats": ["A record is jason's text of an adopted rule. The minutes and the recorded instrument govern."]
}
```

`GET /api/rule-record?id=rules%23R-12&as_of=2099-10-05` (proposed; `RuleRecord.version_on`):

```json
{
  "found": true, "id": "rules#R-12", "asOf": "2099-10-05", "number": "R-12", "numberThen": "R-12", "renumbered": false,
  "title": "Quiet hours", "kind": "rule", "subjects": ["noise"], "confidentiality": "open", "status": "adopted",
  "version": {"id": "v2", "words": "[the adopted words, as stored]", "digest": "5b1e0c4a9d27…", "stage": "adopted",
              "adopted": "2098-04-14", "effective": "2098-04-14", "boardItem": "BI-2098-07", "decision": "dec-2098-0414-3",
              "recordedBy": "Sam Placeholder", "recordedAt": "2098-04-15T09:12:00",
              "notice": [{"key": "rule-change-proposed-quiet-2098-03-10", "delivered": "2098-03-10", "to": "every member"}],
              "supersedes": "v1", "source": {"kind": "adopted text", "file": {"id": "lib-882", "name": "Minutes, Apr 14, 2098"}}},
  "grounds": [{"id": "ra-0007", "citation": "bylaws#7.8", "tier": "likely", "readers": ["rules", "model"], "review": "confirmed by Jane Example",
               "recital": {"words": "[the grant's words, as stored]", "version": "in force 2099-10-05", "verified": true}}],
  "reach": {"reach": "listed", "cites": ["CIV 4355(a)(1)"], "note": "use of the common area"},
  "copies": [], "openProposals": [],
  "compare": {"word": "same", "doc": {"revision": "r-0412", "read": "2099-10-04T18:20:00"}},
  "uses": {"count": 3},
  "caveats": ["jason's text of an adopted rule. The minutes and the recorded instrument govern."]
}
```

`GET /api/rule-record-history?id=rules%23R-12` (proposed), a proposed, a withdrawn, and an adopted version in order:

```json
{
  "found": true, "id": "rules#R-12",
  "versions": [
    {"id": "v3", "stage": "proposed", "proposal": "rc-0007", "words": "[the proposed words]", "diffTo": "v2",
     "proposedBy": "Jane Example", "proposedAt": "2099-09-30", "notice": [], "adopted": null},
    {"id": "v2", "stage": "adopted", "words": "[the adopted words]", "diffTo": "v1", "adopted": "2098-04-14",
     "boardItem": "BI-2098-07", "decision": "dec-2098-0414-3", "proposedBy": "Sam Placeholder", "recordedBy": "Sam Placeholder",
     "notice": [{"key": "rule-change-proposed-quiet-2098-03-10", "delivered": "2098-03-10"}], "supersedes": "v1"},
    {"id": "v1", "stage": "adopted", "words": "[the first words]", "adopted": null, "adoptionOnRecord": false,
     "source": {"kind": "imported, adoption not on record"}}
  ],
  "ended": [{"proposal": "rc-0003", "end": "withdrawn", "by": "Jane Example", "on": "2099-02-02", "reason": "folded into rc-0007"}],
  "gaps": [{"before": "v1", "note": "the record does not show which words were in force before the first version"}]
}
```

`GET /api/rule-record-compare?id=rules%23R-3` (proposed; `RuleBook` against `manual_rule_change.partition`):

```json
{
  "found": true, "id": "rules#R-3", "word": "changed with no adoption found",
  "adopted": {"version": "v1", "words": "[the last adopted words]", "citation": "rules#R-3", "adopted": null},
  "doc": {"revision": "r-0412", "words": "[the working Doc's words]", "changedBetween": ["2099-03-01", "2099-05-12"],
          "pendingSuggestions": 1, "suggestionNote": "A pending suggestion is not accepted and is not a rule."},
  "acts": ["take-as-proposal", "board-note"],
  "caveat": "No adoption found is a finding for a person, not proof that none happened."
}
```

`GET /api/rule-proposals` and `GET /api/rule-proposal?key=rc-0007` (proposed):

```json
{
  "found": true, "key": "rc-0007", "title": "Quiet hours on weekends", "source": "proposal", "by": "Jane Example", "confidentiality": "board",
  "stage": "checked", "stages": [
    {"key": "drafting", "state": "done", "by": "Jane Example", "on": "2099-09-30"},
    {"key": "reason", "state": "done", "by": "Jane Example", "on": "2099-09-30"},
    {"key": "reach", "state": "done", "by": "Jane Example", "on": "2099-10-01"},
    {"key": "checked", "state": "current", "needs": "1 flag to acknowledge"},
    {"key": "board", "state": "waiting"}, {"key": "noticed", "state": "waiting"},
    {"key": "decided", "state": "waiting"}, {"key": "adoption", "state": "waiting"}, {"key": "effects", "state": "waiting"}
  ],
  "proposed": [{"record": "rules#R-12", "against": "v2", "words": "[the proposed words]", "diff": "[server-built diff]",
                "brackets": ["[weekend start time]"], "stageAddress": "rules#R-12@proposed-2099-09-30"}],
  "reason": "[the reason, as written]", "purpose": "[the purpose]", "effect": "[the effect]",
  "subject": "noise", "reach": {"reach": "listed", "cites": ["CIV 4355(a)(1)"], "label": "jason's reading of Civil Code 4355"},
  "facts": [{"fact": "rule_scope", "answer": "listed_subject", "by": "Jane Example", "on": "2099-10-01"},
            {"fact": "rule_change", "answer": "noticed", "by": "Jane Example", "on": "2099-10-01"}],
  "rows": [{"key": "rule-change-proposed", "state": "required"}, {"key": "rule-change-adopted", "state": "required"},
           {"key": "rule-change-reversal-results", "state": "required"}],
  "clock": {"source": "rule-change-proposed", "note": "sample dates: the loader reads the row and the meeting schedule",
            "noticeBy": "2099-10-20", "decision": "2099-11-17", "adoptionNoticeBy": "2099-12-02", "reversalBy": "2099-12-17",
            "delivery": {"state": "draft saved, no recipients", "key": "rule-change-proposed-quiet-2099-10-20"}},
  "board": {"item": "BI-2099-12", "status": "proposed", "meeting": "2099-11-17", "decision": null},
  "adoption": null, "effects": [],
  "caveats": ["A draft is the board's working paper. It changes no rule."]
}
```

`GET /api/rule-proposal-checks?key=rc-0007&as_of=2099-10-05` (proposed; each check's reader and recital):

```json
{
  "found": true, "key": "rc-0007", "asOf": "2099-10-05",
  "checks": [
    {"id": "authority", "standing": "run, nothing found", "result": "authority named, rules on file", "grants": ["ra-0007"], "reader": "rules", "flag": null},
    {"id": "conflict", "standing": "found", "reader": "model", "tier": "suggested",
     "recital": {"provision": "decl#9.2", "words": "[the declaration's words, as stored]", "version": "in force 2099-10-05"},
     "reading": "[jason's reading of how the two provisions bear on each other]",
     "flag": {"id": "f-1", "state": "unacknowledged"}, "lead": "a lead for a Conflict row; only the board, counsel, or an amendment resolves a conflict"},
    {"id": "duplicates", "standing": "run, nothing found", "reader": "rules", "flag": null},
    {"id": "statutes", "standing": "not run", "needs": "the shelf lacks the statute the text cites", "command": "jason cite \"CIV 9901\""},
    {"id": "quotes", "standing": "run, nothing found", "flag": null},
    {"id": "brackets", "standing": "found", "open": ["[weekend start time]"], "flag": {"id": "f-2", "state": "acknowledged", "by": "Jane Example", "note": "the board chooses"}},
    {"id": "clock", "standing": "run, nothing found", "source": "rule-change-proposed"}
  ]
}
```

`GET /api/rule-proposal-effects?key=rc-0007` (proposed; `document_template` definitions, the packet registry, the catalog):

```json
{
  "found": true, "key": "rc-0007", "ifAdoptedOn": "2099-11-17",
  "effects": [
    {"id": "version", "what": "rules#R-12 v3 is in force from the day it says", "state": "derived"},
    {"id": "rules-document", "what": "The Rules document changes at rules#R-12", "state": "to do", "command": "jason document-template rules-and-regulations"},
    {"id": "manual", "what": "The owner's manual changes where it includes the rule", "state": "to do", "command": "jason document-template owners-manual"},
    {"id": "notice-adopted", "what": "The notice of adoption", "row": "rule-change-adopted", "state": "to do", "by": "[from the row's timing]"},
    {"id": "policy-statement", "what": "The next annual policy statement carries the subject: noise", "row": "annual-policy-statement", "state": "to do", "note": "whether a mid-year notice is also needed is the row's and a question for the person"},
    {"id": "citations", "what": "Citations resolve to the record id", "state": "not needed", "why": "citations resolve to the record"}
  ]
}
```

`GET /api/rule-uses?id=rules%23R-12` (proposed) and `GET /api/rule-events?key=rc-0007` (proposed):

```json
{
  "found": true, "id": "rules#R-12", "count": 3,
  "byOutcome": [{"outcome": "reminder sent", "n": 2}, {"outcome": "hearing held", "n": 1}],
  "uses": [{"kind": "notice", "on": "2099-02-11", "version": "v2", "outcome": "reminder sent", "ref": {"doc": {"id": "ledger-0212", "name": "Notice, Feb 11, 2099"}}},
           {"kind": "hearing", "on": "2099-04-06", "version": "v2", "outcome": "hearing held", "ref": {"route": "#/hearings?id=h-2099-04"}}],
  "note": "A list of the association's uses of the rule, not a finding. 'No use linked' is shown as that.",
  "events": [{"act": "proposal", "by": "Jane Example", "at": "2099-09-30T10:02:00", "record": "rules#R-12", "version": "v3"},
             {"act": "acknowledged", "by": "Jane Example", "at": "2099-10-02T08:30:00", "flag": "f-2", "note": "the board chooses"}]
}
```

**The writes** (each `POST /api/write/rule-records/...`, behind the write guard with `by`; the body is the fields in the act's row above, and each echoes the digest of the words the person saw): `propose` `{records, subject, by}`; `words` `{key, record, words, by}`; `reason` `{key, reason, purpose, effect, by}`; `reach` `{key, subject, facts, by}`; `ack` `{key, flag, note, by}`; `to-board` `{key, by}`; `notice-draft` `{key, noticeDate, by}`; `record-adoption` `{key, decision, minutes, words, by}`; `effect-done` `{key, effect, by}`; `withdraw` `{key, reason, by}`; `repeal`, `suspend` `{record, until, by}`; `take-doc-words` `{record, by}`; `link-use` `{record, ref, on, by}`.

## What the design must keep

- **jason proposes; the board adopts** (principle 5). No control adopts, approves, or votes. The vote is read from the Decisions tab. The adoption act records what the board did, only after a carried decision on record, in an officer's name.
- **Recite, then label** (principle 2). A rule, a grant, a conflicting provision, and the statute for a notice are shown as their stored words with citation and version, before any reading. A reading (the reach, a conflict, a duplicate, a check) sits under a `ReadingLabel` that names whose it is.
- **A reading is a lead** (principle 3). A flag is acknowledged, not resolved; a check says "found", "nothing found", or "not run", never pass or fail; a conflict says only the board, counsel, or an amendment resolves it.
- **A miss stays a miss** (principle 8). No grant found, adoption not on record, no use linked, no document read, a gap before the first version, a missing meeting schedule: each is that, with its command, never an empty row and never a count that means "not read".
- **Nothing in force is edited.** An adopted version is never changed; a correction is a new log line; the previous version stays addressable by day.
- **The Doc is a working source**, never the rule. Its words appear beside the adopted words, never merged, and nothing here edits it.
- **No date or period from memory.** Every date and period is read from a catalog row or the meeting schedule and shows the row. "Noticed" and "28 days have passed" are true only after a delivery on record.
- **A draft is the board's.** The reason, the drafts, the flags, and counsel's reading as a person summarized it are `board` confidential; the open view shows an adopted version, its notice, and nothing else.
- **A use is a list, not a finding.** The Uses tab never says a rule was or was not applied consistently.
- **Every write is a `Confirm` in a named person's name, through the write guard, with its CLI equivalent named** (below). Each says what it changes and what it does not. A refusal says "Nothing was written."
- **Nothing is worked out on the client.** The status, the compare word, the diff, the clock's dates, the checks, the effects, and the version in force on a day all come from a loader.
- **No color-only meaning.** Every state is a word first.

**Privacy by level** (principle 6):

| What | Level | Shown |
| --- | --- | --- |
| an adopted rule's words, its adoption, its notice, its history | P0 | the open view and the board's screens |
| a draft, a reason, the checks, a flag and its acknowledgment, the log of who drafted | P1 (the board's working record) | roster people; **not the owner view** |
| a use's reference | P1 | roster people; the open view lists the reference without a name |
| an owner's name on a use (a hearing, a request) | P2 or P3 by the use's own level | the people who work with it, through the use's own screen; never copied into the rule's record |
| counsel's letter | P3 | by kind only; never copied; the record links the file and names its kind |
| a draft discussed in executive session | P3 | by general nature only outside the private view |

The records screens are board-only (`owner: false`), except that an owner view may show the adopted rule and its notice (decision 7).

## Where it goes

Routes are proposed, consistent with [information-architecture.md](information-architecture.md#where-the-proposed-screens-go); none exists yet.

- **Records → Governing documents → Rules and authority**, fifth band **Records** (`RuleRecordBook`): `#/documents/rules?band=records`. Query: `?document=KEY`, `?status=`, `?subject=`, `?compare=` (a `CompareWord`), `?as_of=YYYY-MM-DD`. A record's page: **`#/documents/rules/record/<id>`** (the id is URL-encoded), tabs Words, History, Grounds, Compare, Uses, Audit, with `?as_of=`. The header's `Command` is `jason rule-records`. This is a band of the existing route because the Authority band already recites the grants a record rests on and `RecordGrounds` reuses it; the alternative, a route of its own, is decision 1.
- **Governance → Rule changes** (`#/rules`, built): `ChangeList` extends it with a **proposal** source beside the specification's rows (labeled); a proposal's page is **`#/rules/change/<key>`** (`ChangePage`); **`#/rules/change/new?subject=&grant=`** starts one, and is where `RuleChangeHandoff` and `AuthorityLead` (the Authority band) link. The built page for a specification row (`/api/rule-changes?key=`) is unchanged. A specification row and a proposal are both shown as a `RuleChange` when the notice is built.
- **The board's items and decisions** (`#/actions`, `#/agenda`, `#/decisions`, `#/room`): the proposal's board item is an ordinary one; the vote is recorded where every vote is. Neither duplicates this page; each links back to `#/rules/change/<key>`.
- **Governing documents** (`#/documents?q=`): a section that is a rule shows "this rule's record: version in force, adopted Apr 14, 2098; 3 uses" and links its record; a citation resolves to the record id.
- **The programs register** ([handoff-programs.md](handoff-programs.md)): an operating-rule program row links the record's page for its adoption evidence.
- **The Rules document and the manual** (`jason document-template`): their render uses the version in force; the Effects tab links them.
- **Onboarding** ([screens/onboarding.md](screens/onboarding.md)): a task "keep the rules as records" after the rules are brought in ([handoff-rules-and-authority.md](handoff-rules-and-authority.md)): export the records, confirm each unclear section, list the records whose adoption is not on record.
- **The dock's Deadlines and the digest**: a proposal's computed dates (notice by, decision, notice of adoption) appear as deadlines with their row as the source; an adoption not recorded within the row's window after a carried decision is a deadline "to record" in the secretary's list.
- **MCP** (read only, proposed): `rule_records` and `rule_record` in the governance profile, with the same caveats; no write tool.

**When a loader cannot answer** (principle 8). Each tab is its own `RemoteView`. No records stored and no outline: "No rule records yet" with `jason document-template --export-records`. No decisions file: the Board tab says the vote cannot be read and links `#/decisions`, where it is recorded. No meeting schedule: the clock says what it needs. A proposal's checks that cannot run say so with the command.

**Loaders to add** (names only; nothing built; each wraps a function that exists or a small addition and derives nothing on the client):

| Loader | Route | Wraps | Notes |
| --- | --- | --- | --- |
| `rule-records` | `GET /api/rule-records?document=&status=&subject=&as_of=` | `tasks.rules_documents.prepare`, `RuleBook`, `version_on`, the stored file or the derivation | the book with counts; the status fold; the grants' standing |
| `rule-record` | `GET /api/rule-record?id=&as_of=` | `RuleRecord`, `rule_authority`, the concordance (`permanent_ids`) | one record; the version in force on the day; the old address resolved |
| `rule-record-history` | `GET /api/rule-record-history?id=` | the stored versions and the event log | with the ended proposals |
| `rule-record-compare` | `GET /api/rule-record-compare?id=&document=` | `RuleBook` against `manual_rule_change.partition`, `jason revisions` | the four words; the pending suggestions counted apart |
| `rule-proposals` | `GET /api/rule-proposals?stage=&by=` | the proposal store | the viewer's drafts marked |
| `rule-proposal` | `GET /api/rule-proposal?key=` | the proposal, `rule_change.timeline`, the notice catalog and ledger, `tasks.decisions`, `tasks.board_items` | one proposal; the stage fold; the clock from the rows |
| `rule-proposal-checks` | `GET /api/rule-proposal-checks?key=&as_of=` | `rule_authority.by_subject`, `reach`, `conflicts`, `law_citations.resolve`, `quote_check`, the manual's copy detection | read only; each check's standing |
| `rule-proposal-effects` | `GET /api/rule-proposal-effects?key=` | `document_templates` definitions, the packet registry, the catalog, `procedures` | read only |
| `rule-uses` | `GET /api/rule-uses?id=` | the use links, each use's own record | outcome as the use records it |
| `rule-events` | `GET /api/rule-events?key=|id=` | the event log | filterable |
| `rule-records` (writers) | `POST /api/write/rule-records/<act>` as above | `jason rule-records` | each behind `X-Jason-Token` with `by` (400 without; 401 with no one signed in); `record-adoption` refuses without a carried decision, the minutes, and a passing quote check |

**CLI equivalents** (proposed; section 9 of the design): `jason rule-records --propose`, `--words`, `--reason`, `--reach`, `--ack`, `--to-board`, `--notice` (wraps `jason rule-change KEY --draft-email --yes --by NAME`), `--record-adoption`, `--effects`, `--link-use`, `--repeal`, `--suspend`, `--withdraw`, `--compare`; `jason rule-records ID --as-of DAY --history --uses`. The name is free: no command uses `rule-records`, and `data/rule-records/` is the stored-file folder `jason document-template --export-records` writes. Read-only MCP tools `rule_records` and `rule_record` are free.

## Accessibility

As [components.md](components.md#accessibility) and [content/patterns.md](content/patterns.md#accessibility-wcag-22-aa):

- **Keyboard.** Tabs follow the tabs pattern with arrow keys; a record row opens by a `button` with `aria-expanded`. `DocVersusRecord` is two regions in DOM order (the adopted words, then the Doc's), each labeled, followed by the word and the acts; the `Confirm`s are native buttons. The diff is a list of changes with text markers ("removed:", "added:"), never color alone.
- **Screen reader.** A `Recitation` is a `figure` with `blockquote` and `figcaption` (citation and version). `RecordStatus` is text. A `ChangeFlow` is an ordered list; the current step is `aria-current="step"` and each step's state is a word. A flag's acknowledgment is `role="status"`; a refusal is `role="alert"` tied to the field.
- **Forms.** The draft's words are a labeled text area; the count of open brackets is announced as the person types ("2 choices left for the board"), as a polite status and not on every key. A half-written draft stays across a tab change (timing, 2.2.1); an unsaved draft says so.
- **Redundant entry (3.3.7)** the name comes from "Signed in as"; the second-person field, where decision 2 asks for one, starts empty. **Target size (2.5.8).** **Use of color (1.4.1):** every state is a word.
- **Dates** are written in full ("Nov 17, 2099") with the row that gave them; a countdown is a word and not a ring.

### The phone layout (under 720 px)

- The tabs of `RuleRecordPage` and `ChangePage` become a `select` whose options carry the state in words ("Checks (1 flag to acknowledge)", "Board (carried, adoption not recorded)").
- `ChangeFlow` is a numbered list, one step a line, the state word in full; a step's detail opens in place.
- A record's words are shown in full, never cut to an ellipsis; the diff is stacked, "before" over "after", each labeled.
- `DocVersusRecord` stacks the adopted words over the Doc's, each headed by what it is; the acts follow, not sticky.
- A table becomes a list: the record's number and heading, then its status word and the version in force, then the grant standing. Nothing scrolls sideways at 320 px.

## Decisions for the design

**Settled by the axioms in this pass.**

- **No control adopts or approves; the vote is read.** AGENTS.md ("jason proposes; the board adopts"); [approval-workflow.md](approval-workflow.md#12-the-board-decides-by-vote).
- **The Doc is a working source; the adopted version of the record is the rule.** Their words are shown side by side and never merged.
- **A flag is a lead, acknowledged by a person.** A conflict row is a profile row a person adds; the console edits no specification.
- **A decision brief never recommends.** The board item carries the facts and the clock, and the two readings where two remain.
- **A one-off decision is not a rule.** The page says so and routes it to a decision.
- **No dates from memory.** Every date is a row's.

**Still open, and a person's to settle.**

1. **Where it lives.** A fifth band **Records** on `#/documents/rules` and the proposals on `#/rules` (the proposal here), versus one route of its own (`#/rule-records`) that holds both, versus the proposals joining the board's canvas only. The loaders are the same. Test with the secretary, who records the adoptions, and the president.
2. **Who may take each act**, and whether any needs a second person (`SecondConfirm`): draft, acknowledge a flag, put it before the board, record the adoption, link a use. The design assumes any roster person may draft and an officer who records votes records the adoption.
3. **Whether a flag stops the notice.** The design makes it an acknowledgement; whether a missing grant or a conflict must be acknowledged by an officer, or by counsel, before **Save the notice draft** is enabled is the board's.
4. **Whether `source: records` is offered at all** in this pass, or only the compare (decision 1 of [../rule-records.md](../rule-records.md#11-open-decisions-for-a-person)). Without it the screens are read-only on the records and write only proposals and events.
5. **How an adopted version with no adoption on record is shown** ("in force, adoption not on record") and whether the book lists them as an action item for the board.
6. **Whether a withdrawn draft is shown to a person other than its drafter**, and for how long it is kept.
7. **Whether the owner view shows an adopted rule, its notice, and its history** (decision 5 of [handoff-rules-and-authority.md](handoff-rules-and-authority.md#decisions-for-the-design) is the same question for the authority screen).
8. **The word for the "Doc ran ahead" state**, and whether four compare words are too many for the book's filter. Test in review.
9. **A use's link written by the task that records it**, which tasks first (hearings and architectural decisions), and how a person links one the tasks missed.
10. **Whether the annual policy statement** is itself shown as a record whose rule list is confirmed each year.

## A phased build plan

1. **Read the records.** `rule-records`, `rule-record`, `rule-record-history` over what exists (`RuleBook`, the stored file or the derivation), the **Records** band and the record page with Words, History (derived versions only), Grounds, and the as-of day; `RecordStatus`, `RecordSource`, `RuleHistory`, `RecordGrounds`. No write. This needs the status fold and the new fields empty, and it makes no change to a rule.
2. **Compare.** `rule-record-compare`; `DocVersusRecord` and `CompareWord`; the two acts "Take the Doc's words as a proposal" and "Record the adoption found in the minutes" (the second waits for phase 4's `AdoptionRecord`).
3. **Proposals.** The proposal store and event log; `rule-proposals`, `rule-proposal`, `rule-proposal-checks`; `ChangeList`, `ChangePage`, `ChangeFlow`, `ChangeDraftForm`, `PurposeEffectFields`, `ReachGate`, `ProposalChecks`, `FlagAck`; the writes through `ack`; the board item. Reuses `jason rule-change` for the notice.
4. **Notice, vote, adoption.** `NoticeClockLine`, `NoticeDraft`, `BoardLink`, `VoteOnRecord`, `AdoptionRecord`; `record-adoption` and its refusals.
5. **Effects and uses.** `EffectsPlan`, `RuleUseList`, `ChangeAudit`; the use links from hearings and architectural decisions.
6. **Records as the source** (decision 4), if the board chooses.

Each phase is a gate: the screen of the phase before is used for a real change before the next is built, and a lesson is added where the process missed something.

## Not part of this pass

- Any control that adopts, approves, votes on, or recommends a rule or a change, and the writing of a rule's words by jason (a starting text from a Doc difference is labeled and a person's to edit).
- The reversal vote's own steps (a petition, a ballot), and the election machinery: [screens/notices.md](screens/notices.md) and the election screens.
- Sending the notice: the member notice is a Gmail draft a person sends.
- Editing the working Doc, the specification, a `Conflict` row, or the classification from the console; those are a person's edits in Docs or in the profile.
- Whether a suspension or a correction is a rule change (a question for counsel, recorded either way).
- The annual policy statement's own assembly ([handoff-programs.md](handoff-programs.md); `jason packet`).
- An owner-facing version beyond decision 7.
- The previews: the design project's authored preview for each component follows the build; fixtures will be `ui/src/components/rulerecords.test.tsx` and its siblings, from the sample data above.
