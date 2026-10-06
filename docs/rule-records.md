# Rule records: keeping the association's rules as data, and the way a change reaches them

Status: **design** (October 2026). Nothing in this page is built except what the first table says is. It extends the rule records of [document-templates.md](document-templates.md#11-the-rules-document-the-owners-manual-template-and-the-docs-they-make) (section 11) from "the words of the rules, with versions" to "the rules, their grounds, their history, and the acts that change them". The console's design for it is [console/handoff-rule-records.md](console/handoff-rule-records.md).

This page is general. The association's own rules, subjects, grants, and board items are the profile's data. Every example here is made up.

## 1. What exists, and what this page adds

| Piece | Where | What it does today | Here |
|---|---|---|---|
| The rule record and its versions | `jason.community.rules_document` (`RuleRecord`, `RuleVersion`, `RuleBook`), `jason.tasks.rules_documents` | A stable `id`, the printed `number`, a heading, `kind` (rule or copy), `copies`, editorial `notes`, and `versions` (the words, the adoption day and board item, or `proposed`). `version_on(day)` is the newest adopted version on or before the day; a proposed version is in force on no day. Derived from the manual's classification, or kept as data in `data/rule-records/<document>.json` (`--records stored`, `--export-records`) | Reused. Fields are added (section 3); nothing is renamed |
| The Rules document, the manual, the banner | `jason document-template` | The records render as the Rules document and the owner's manual; the status line is the draft banner until an adoption event for the document is on record | Reused unchanged. A record's version in force is what they print |
| Adoption events | `jason.community.manual` (`AdoptionEvent`, `AdoptionAction`: noticed, adopted, delivered, tabled, listed, no action, in force), `adoption_history` | When each part was noticed, adopted, delivered, tabled, from the profile's rows, the rule-change records, and a detector's dated versions | Reused. The new event log (section 6.3) writes the same kinds and adds who, and a person's act |
| The proposed change | `jason.community.rule_changes` (`RuleChange`, `SectionChange`), `jason rule-change`, `jason.tasks.rule_change`, `jason.tasks.manual_rule_change` | A proposed change is **data in the specification** (`Community.rule_changes()`), or built in memory from the manual (`--from-manual`). The notice puts the proposed text first, then the purpose and effect; the dates come from the meeting schedule and the notice catalog; the member notice is a Gmail draft with no recipients that a person addresses and sends | Reused as the notice path. A **proposal** (section 6.1) becomes a `RuleChange` in memory, the way `--from-manual` already does |
| The notice catalog and its facts | `jason.community.notices` (`NoticeRequirement`, `Timing`), `jason notices --catalog --fact rule_scope=... --fact rule_change=...`, [notices.md](notices.md) | The rows that say what each rule-change notice is, to whom, by what method, by when; undetermined rows say which fact is missing | Reused. No date or period on this page is a figure to copy: the loader reads the row |
| Authority | `jason rules` ([rule-authority.md](rule-authority.md)) | Grants of rule-making power found in the governing documents, each a lead with a tier; each subject's standing; jason's reading of Civil Code 4355 for the subject (`reach`: listed, depends, not listed) | Reused. A record points at the grants it rests on (section 5) |
| Citations | `jason cite`, `jason.community.scoping`, the concordance ([rule-citations.md](rule-citations.md), [record-addresses.md](record-addresses.md)) | A citation resolves to a section, scoped to the document; every old address resolves through the concordance; a section has a permanent id | Reused. A record id is a citable address (section 4.4) |
| Conflicts | `Community.conflicts()` (`Conflict` rows), `jason conflicts`, `jason conflicts --leads` | Provisions that yield to a higher authority, with the date, how the provision is applied meanwhile, and the board item that follows | Reused. A proposal is checked against them (section 7) |
| Board items and decisions | `jason board`, `jason.tasks.board_items` (`propose`), `jason.tasks.decisions` (`data/board/decisions.json`), [console/approval-workflow.md](console/approval-workflow.md#12-the-board-decides-by-vote) | A matter for the board, laned by status; the board's vote recorded at a meeting by an officer | Reused. The change's board item is one of these; the vote is read from where it is recorded |
| Registers | [registers.md](registers.md) ("Rule changes (4360)") | A sheet row per change: proposed text link, notice deadline, decision date, adoption deadline, notice sent, comments, adopted, adopted text link | The register keeps its place for what the board keeps up to date; where the records live is decision 1 |

**New:** the record's grounds, subject, status, source, and confidentiality; the proposal as a stored draft; the event log; the checks that run before a notice; the as-of and history views; and the link from a use of a rule to the record.

## 2. The idea in one line

A rule is a **record**: its words by version, the grant it rests on, and the acts that made each version. A change to it is a **proposal** that moves through acts a named person records, from a draft with its reason, through the notice the law requires when the subject calls for one, to the board's vote and a person recording that the board adopted it. jason drafts, checks, and keeps the history; the board adopts. An adopted record is never edited: a change is a new version, and the earlier one stays addressable by day.

## 3. The rule record

`RuleRecord` as built keeps its fields. The new fields are added to the same record, so one file holds one rule's whole history. A field jason cannot fill stays empty and shows as a miss.

| Field | Meaning | Today |
|---|---|---|
| `id` | Stable, never reused; survives renumbering and rewording. The permanent id of the outline section where the document has an id table, else `book#address`; a piece of a rule is the id with `/n` | built |
| `number`, `book`, `title`, `level` | What it prints as now, and where | built (`number`, `book`, `title`, `level`) |
| `segment`, `copies` | The manual outline address, kept as an alias; what the rule restates, with its state | built |
| `kind` | `rule` (the board's own operating rule), `policy` (a policy section the board adopted), `copy` (words of the declaration, a bylaw, or a statute the rule restates), `guidance` (an explanation that is not a rule). Only a `rule` or `policy` is in the Rules document's text; a `copy` the board adopted as a rule keeps its note naming the source | built for rule and copy (`SectionKind`); policy and guidance are in the classification and are carried on the record |
| `subject` | Which `rule_authority.Subject` the rule is about, one or more, by the closed list | **new**; read from the rule's heading and norm sentences by the rule reader, then confirmed by a person; a subject the list lacks is `other` with the person's word |
| `authority` | The grants of rule-making power it rests on: grant ids from `jason rules` (`ra-0007`), each with its tier word and the citation; plus any statute the rule is made under (a citation, recited from the shelf) | **new**; none found is "no grant found", a miss and a question, never "no authority" |
| `versions` | Each: `version` id, `words`, `stage`, adoption (`on`, `boardItem`, `decision`, `recordedBy`, `recordedAt`), notice (`given`: ledger keys and days), `supersedes` (the version id replaced), `source` (section 3.2), `digest` | built (`text`, `words`, `adopted`, `board_item`, `proposed`, `note`); the rest **new** |
| `status` | `proposed`, `noticed`, `adopted`, `suspended`, `repealed`; derived, never typed (section 3.1) | **new** |
| `confidentiality` | `open` for an adopted version and its notice; `board` for a draft, a reason, and counsel's reading as the person summarized it; counsel's own letter is never held here, only named by kind and linked by reference | **new** |
| `uses` | The linked uses of the rule (section 8.3) | **new**, links only |

### 3.1 Status is derived from the events

`status` is a fold of the version and event log, so it cannot disagree with them. For one version:

| Word | Derived from |
|---|---|
| `proposed` | a draft or a submitted proposal; no notice recorded; in force on no day |
| `noticed` | a notice delivered on record (a ledger key whose delivery is read: `jason notices KEY --sync`), no decision yet |
| `adopted` | an adoption event recorded by a person, with the day, the board item, and the vote's decision id; in force from the day it says it takes effect |
| `suspended` | a suspension event on record (section 6.7), from its day until the day it ends |
| `repealed` | a repeal event on record: a version whose words are empty by adoption, or a rule change the members reversed |
| `expired` | an emergency version whose end day (from the catalog row) has passed; shown beside `repealed`, not as it |

The record's own status is its newest version's, with the version in force on a day found by `version_on(day)`. **A derived record has an imported first version** whose adoption day is not on record; it is shown as **in force, adoption not on record**, not as adopted. Jason never promotes it. A person records the adoption they find in the minutes (an event with `source: minutes` and the evidence), which is an ordinary adoption event with a past day.

### 3.2 Where each version's words come from

The words of a version are, in this order of rank, and the record says which:

1. **The adopted text:** the words in the minutes or the adopted instrument, entered by a person from the stored file, with the file's address. This is the authority for a version in force.
2. **The noticed text:** the proposed words the members were noticed of, held as the stage version (`...@proposed-DATE`). The adopted words equal them unless the board changed them; a difference is shown (section 6.5).
3. **The document's words as read:** the owner's manual's last adopted words as `jason manual` partitions them ([owners-manual.md](owners-manual.md#the-last-adopted-words-not-the-working-ones)). A passage changed with no adoption found is never the rule.

**Never a working draft.** A working Doc, a suggestion, a revision between adoptions, or a draft in the proposal store is not the rule. The record's version in force is a version whose source is 1, 2 (as adopted), or 3 with an adoption on record. A pending suggestion is never printed.

**Never filled from the declaration by reference.** A rule that restates the declaration holds its own words as the board adopted them, as a `copy`. It is not rewritten to say "see the declaration": that would itself be a rule change. Where its words and the declaration's differ, the existing copy state says so (`CopyState`) and the difference is a question for the board ([owners-manual.md](owners-manual.md#what-the-board-decides)).

## 4. How the records relate to what is already there

### 4.1 The Doc, the records, and which wins

The working Doc is a **working source**. It stays one until a person decides otherwise (decision 1). The relation is decided per document by one setting a person changes, `source`:

| `source` | The records are | The Doc is | What is shown |
|---|---|---|---|
| `doc` (default; today) | derived each run from the Doc's outline and the classification | the original | a stored file, if any, is a snapshot; a difference between it and the derivation is shown |
| `records` (a person's choice) | the original, stored in `data/rule-records/<document>.json` | generated from them (`--doc`), and a person's edit to it is "edited", never overwritten | the Doc's edit is a difference, offered as a proposal |

**Which wins.** For *what is in force*, the **adopted version of the record** wins in both modes: a Doc's words are the rule only where an adoption on record covers them. The Doc's words differ from the record's in four ways, each shown and none resolved silently:

| The comparison | Word | What the person is offered |
|---|---|---|
| Doc equals the version in force | same | nothing |
| Doc differs; an adoption on record covers the Doc's words (a later adoption than the stored version) | the record is behind | **Record the adoption** (the event was missed); the version is added with its evidence |
| Doc differs from the version in force; a proposal with those words is on file | the Doc ran ahead of the process | link the proposal; the Doc's words are labeled "a proposal, not adopted" |
| Doc differs; nothing on record covers it | changed with no adoption found | **Take the Doc's words as a proposal**, or **restore the adopted words** (an edit in the Doc by a person; jason never edits a Doc). The adopted words stay the rule meanwhile |

The diff is the two sets of words side by side (`DiffTable`, with the adopted version's citation and day, and the Doc's revision and its time), never a merged text. "A change with no adoption found" is a finding for a person, not proof that none happened. Nothing writes to the Doc; nothing makes a Doc's words a rule.

### 4.2 The outline and the classification

The classification (`jason manual --classify`) remains the reader of a Doc: it says a section is a rule, a copy, a policy, guidance, mixed, or unclear. The records are what it produces and the person confirms. `unclear` stays a question for a person (`jason intake`); a record is not created for an unclear section. A new section in the Doc with no record is "in the Doc, no record" and offered as a proposal, never added as a record with an adoption day.

### 4.3 The Rules document and the manual

Both render the **version in force on the document's as-of day** (`version_on`). A record whose status is `proposed` or `noticed` prints nothing new; a record with no version in force prints the visible gap line. Regeneration is an effect of adoption (section 6.6), never automatic: the plan says which documents change, a person runs it. The Rules document's status line (the draft banner) is a separate record, the whole document's adoption event; adopting one rule does not adopt the document.

### 4.4 Citations

A citation that names a rule resolves to **a record id**, not an outline number. The concordance already keeps every old address; the record id is the stable end of it. Consequences:

- A citation written before a renumbering still resolves; the loader shows the number as it printed then and the record's number now, and says they are one rule ("renumbered, not changed").
- A citation `as_of` a day resolves to the version in force that day (the same mechanism the statutes use: [console/handoff-as-of-and-quote-check.md](console/handoff-as-of-and-quote-check.md)). A citation inside an adopted rule's own words keeps those words.
- A proposed version has its own stage address (`...@proposed-DATE`) and is never merged into the text in force, as `jason rule-change` already does.
- A record that is repealed still resolves: it is "repealed on DAY", with its last words.

## 5. Authority: the grant a rule rests on

An operating rule is enforceable only if it is within the authority the law and the governing documents give the board ([rule-authority.md](rule-authority.md)); the statute's own words come from `jason cite`, not from this page. A record carries the grants it rests on:

- **Each grant** is a stored reading (`ra-id`) with its tier word (both readers agree, one reader, the readers disagree), the holder, the subjects, the conditions, and the grant's own words recited whole with their citation and version in force.
- **A grant is a lead, not a ruling.** A person reviews it (`jason rules --review`), and the review is the person's. A rule's record shows the review state beside the grant.
- **No grant found** is shown as that, with `jason rules --find`. It is not "no authority": the power may be in the law itself, in a document not read, or in words the collector does not look for. It is a question for the board and counsel, never an accusation.
- **A proposal on a subject with no grant** is flagged **before the notice** (section 7), as a lead, with the subject's standing from `jason rules --subjects` (general power only, no grant found, neither found). The flag is acknowledged by a person; whether it is also a stop is decision 5.

## 6. The change workflow

### 6.1 The acts, in order

A change is a **proposal**: one or more proposed versions of existing records, new records, or repeals, with one reason and one purpose and effect. It is drafted and moved by people; every act below is a person's act with `by` and a time, recorded in the event log. jason does not draft the rule's words and does not approve. It may draft a **starting text** from a Doc difference or from the person's brief, labeled "jason's draft, not the board's", which a person edits and owns.

| # | Act | Who | What it records | What it never does |
|---|---|---|---|---|
| 1 | **Start a proposal** | any roster person | the key, the records it touches (or a new one), the person, the day; the draft is stored under `proposals/` and is `board` confidential | change a record, or make a version in force |
| 2 | **Write the proposed words** | the drafter, until submitted | the proposed version's words, per record; shown against the version in force (`DiffTable`); brackets (`[choice]`) mark what the board decides and are counted | fill a bracket |
| 3 | **State the reason, and the purpose and effect** | the drafter | two separate texts: the **reason** (why a person proposes it; board-confidential, not noticed) and the **purpose and effect** (the description the notice carries: the text first, then the description of its purpose and effect, as the statute orders; read the order from the stored statute) | write the board's description; the notice labels the description the board's own once the board adopts it |
| 4 | **Say what subject it is, and read the reach** | the drafter | the subject (closed list), and jason's reading of the Civil Code 4355 reach: `listed`, `depends`, `not listed`, each with the sections it cites, **labeled jason's reading** | decide it. `depends` leaves two readings and goes to counsel through the board; the lawful course under either reading is the notice |
| 5 | **State the facts the notice catalog needs** | the drafter, or the secretary | `rule_scope` and `rule_change` (listed, noticed, emergency, not reached), as answers with `by` ([console/handoff-applicability-questions.md](console/handoff-applicability-questions.md)) | default a missing fact; a missing fact keeps the row undetermined |
| 6 | **Run the checks** | any roster person | the checks of section 7 as of the day, each a lead; each flag acknowledged by a named person with a note | block the proposal by itself (decision 5) |
| 7 | **Put it before the board** | a roster person | a board item (`jason board`, `tasks.board_items.propose`) carrying the text, the reason, the reach reading, the checks, and the clock, as evidence; and the motion's draft (the proposed words by reference, with brackets open) | recommend; carry a button that adopts |
| 8 | **Notice the members** (when the subject calls for it) | the secretary or the person who sends notices | the member notice built by `jason rule-change` from the proposal (text first, then the purpose and effect), saved as a Gmail draft; **a person addresses and sends it**; the notice's ledger key and the delivery read from `jason notices KEY --sync` | send, or mark a notice delivered from a click |
| 9 | **The board's vote** | the board, at a meeting | **read from where it is recorded**: the Decisions tab of the meeting (`data/board/decisions.json`), by the president or the secretary, with the motion's words and the roll call by name | take a vote here, or show an "approve" control |
| 10 | **Record the adoption** | the officer who records the vote | the version's adoption: the day, the board item, the decision id, the adopted words from the minutes (section 6.5), the notice ledger keys, who recorded it | adopt: the board adopted; this is the record of it. It needs a decision on record whose outcome is carried |
| 11 | **Carry it out** | people, each effect its own act | the effects of section 6.6, planned and recorded one by one | regenerate or send anything on its own |

A proposal is **withdrawn** by its drafter, or **tabled** or **not adopted** by the board's decision as read from the Decisions tab, and keeps its place in the history (a record of a decision not to act is a decision, `AdoptionAction.NO_ACTION`). A drafted version never deleted is shown as "withdrawn on DAY by NAME".

### 6.2 Which subjects need notice

A rule on a subject Civil Code 4355(a) lists needs the notice 4360 requires before the board adopts it; 4355(b) lists actions that do not. jason's reading is the `reach` of the subject (`rule_authority.reach`):

- **`listed`**: the proposal shows the notice rows for the change (`rule-change-proposed`, `rule-change-adopted`, and `rule-change-reversal-results`), the recited statute, and the clock.
- **`depends`**: both readings are stated, "the board asks counsel" goes on the board item, and the default course is the notice. A rule is not adopted before the notice on a reading counsel has not given.
- **`not listed`**: 4355(b) may take the change out of 4360 and 4365. A board item carries it; the reading is jason's, labeled, and a person records it. A one-off decision on a specific matter that is not intended to apply generally needs no rule at all (4355(b)(2)): the item is **a decision**, recorded on the Decisions tab, and it does not become a record. A decision a board will want to repeat is the case "Where the law is silent, write it down": the board is asked whether to adopt a written policy (AGENTS.md).

### 6.3 The clock and the event log

- **The 28-day clock is the catalog row's.** The loader returns the proposed-change row's `Timing`, `Method`, and recipients, the meeting schedule's next decision date that satisfies it, and each date computed with the row it came from (`rule_change.timeline`: notice, last day for notice, the agenda notice, comments due, decision, notice of adoption, the members' reversal window). A date not read from a row is not shown. A delivery is a ledger fact; "28 days have passed" is true only after a delivery on record.
- **The event log** is append-only: `data/rule-records/<document>.events.jsonl`, one line per act: `proposal`, `words`, `reason`, `reading`, `facts`, `check`, `acknowledged`, `board-item`, `notice`, `delivery`, `decision`, `adoption`, `suspension`, `repeal`, `withdrawn`, `correction`. Each line holds `by`, `at`, the record and version ids, and the evidence (a ledger key, a decision id, a file address). The record file holds the words; the log holds who did what. A correction is a new line that names the one it corrects; nothing is edited or removed.

### 6.4 Emergency and special paths

| Path | What is different | What stays |
|---|---|---|
| **Emergency rule change** (4360(d)) | `rule_change=emergency`; the catalog's emergency rows apply (the adopted-change notice with the text, the purpose and effect, and the expiry); the decision may come before notice **only where the statute allows**, which the person states as a fact with the grounds; a version carries `expires` from the row, and its status is `adopted` until it ends, then `expired` is shown beside `repealed` | the record of who adopted it and on what grounds; an emergency rule that ended is not readopted as an emergency rule (the row says so) |
| **A one-off decision** (4355(b)(2)) | no rule record is made; the item is a decision | recorded on the Decisions tab; a repeated need leads to the written-policy proposal |
| **Not a 4355(a) subject** | no 4360 notice; the board item and the vote | the same record, event log, and effects; the proposal says why the notice does not apply, and it is a labeled reading |
| **Repeal** | a proposal whose proposed version is empty by repeal; a repeal of a rule is a rule change (4340(b)) | the rule's last words stay, addressable as of any earlier day; status `repealed` from the adoption day |
| **Suspension** | the board suspends a rule for a time: an event with a day it ends; whether a suspension is itself a rule change is **a question for counsel**, and the default course is the notice | the version is not edited; the record shows "suspended from DAY to DAY" |
| **Correction of a typographical error** | a new version with a note; whether it is a rule change depends on whether it changes meaning, a reading a person labels; jason does not decide | the earlier version stays as adopted |
| **A rule that restates the declaration** | a `copy` with its own words; changing it to match the declaration may be a rule change or merely repeat the governing documents (4355(b)(5)); two readings, counsel reads | the declaration governs where it conflicts (a `Conflict` row, section 7); the rule is never filled from the declaration by reference |
| **A change after notice** | the board changes the proposed words at the meeting; the adopted words are entered from the minutes and the difference from the noticed words is shown; whether the change needs renotice is **a reading for counsel** | the noticed words are kept as the stage version |
| **Members reverse it** (4365) | the reversal window is a computed date; a reversal on record makes the version `repealed` ("reversed by the members") from its day | the record of how the vote was read |

### 6.5 Adoption, and the adopted words

The adoption act has a decision on record whose outcome is carried, the meeting, the motion's words, and the recording officer, **read from the Decisions tab, never typed**. The adopted words are what the minutes say the board adopted. They are entered as text from the stored minutes (a library file, shown), with a check that every word is in the file; where they equal the noticed words, a person confirms equal; where they differ, the difference is shown and the person's confirmation records it. `jason verify-quotes` checks the entry against the file.

### 6.6 What follows adoption

Every effect is **planned** from the record and the catalog, shown as a list, and each done by a person. A plan item is never run on its own.

| Effect | Read from | Act |
|---|---|---|
| **The record's version** is in force from its day; the previous version stays | the adoption event | none: it is derived |
| **The Rules document and the owner's manual regenerate** | `document-template` definitions that include the record | a person runs the render and, where the Docs are used, `--doc plan` then `create` (a dry run first; a person's edit to a Doc is left alone) |
| **The packet** (the annual disclosures and the policy statement) | the packet's parts that include the rule's book or subject | the next edition carries the new words; the plan says which part |
| **The members are told** | the notice catalog: `rule-change-adopted` (its recipients, method, and clock from the row) | a person sends it; the delivery is read from the ledger |
| **The annual policy statement** (5310) | the catalog rows of the policy statement and the notices it carries (the discipline policy and penalty schedule, the architectural requirements, the dispute resolution summaries), by the rule's subject | a rule on one of those subjects is listed as changing the **next** statement's contents; whether a mid-year notice is also needed is the row's `carried_by` and a question for the person |
| **A new member** | the welcome packet and the resale documents that carry the rules | the plan names them |
| **The citations** that name the rule | the concordance and the citation store | none: a citation resolves to the record id; a picked citation whose words changed is stale ([console/handoff-rules-and-authority.md](console/handoff-rules-and-authority.md#the-citations-choice)) |
| **A lesson** | `jason lessons` | where a proposal showed the process missed something, a person adds it |

### 6.7 What is archived

Nothing is deleted. A superseded version keeps its words, its adoption, its notice, and its evidence, and is addressable as of any day on which it was in force (section 8). A withdrawn or defeated proposal keeps its draft, reason, and the board's decision. The event log is the only record of who did what.

## 7. Checks before a notice

Each check is **a lead**, run as of a day, with its own words (never a bare verdict), and recorded in the log with who acknowledged it. Names of what exists and what is a gap:

| Check | Asks | Reads | Status |
|---|---|---|---|
| Authority | Does a stored grant reach the subject? Which standing: authority named, general power only, no grant found? | `rule_authority.by_subject`, the stored readings | exists; the per-proposal wrapper is new |
| The 4355 reach | Does the subject fall under 4355(a), depend on what the rule does, or not? | `rule_authority.reach` | exists |
| Conflict with the law or the governing documents | Do the proposed words and a provision of the declaration, the bylaws, or a statute both apply and differ? | `Community.conflicts()` rows for the same subject; the law-change leads (`jason conflicts --leads`); the document readings; a statute's version in force (`law_in_force`) | the rows and leads exist; **comparing proposed words to the documents is new and is a reading, tier named**, never a block |
| Duplicates the declaration | Is the proposed text the declaration's own words (a copy), or near them? | the manual's copy detection (`Segment.copies`, `CopyState`) | exists for sections; new for a proposal |
| The statutes it cites | Is each cited section the law in force on the day, or a former number? | `law_citations.resolve`, `jason law-history` | exists |
| The words it recites | Is each recited passage the stored words? | `jason verify-quotes` | exists |
| The brackets | Which choices are open? | `RuleChange.placeholders` | exists |
| The clock | Do the catalog rows and the schedule give a decision date? | `rule_change.timeline`, `jason notices --catalog` | exists |

**A flagged conflict is a `Conflict` row, a person's act.** Only the board, counsel, or an amendment resolves a conflict; jason notes it. If a proposal is flagged, the flag is on the board item; the `Conflict` row itself is a specification row a person adds in the profile and commits (the console never edits the specification). Where the flag is the only question left, the board asks counsel before adopting; "a provision yields only to the extent of any conflict" with the authority above it (Civil Code 4205), and where the extent is unclear the course lawful under either reading is taken.

## 8. As-of and audit views

### 8.1 The rule in force on a day

`version_on(day)` for one record; for a document, every record's version in force. The view always states the day and the version's address, shows the **words recited whole with the version's adoption** (day, board item, decision, notice), and the caveat that jason's text is a record of the adopted words and the recorded minutes govern. A day before the record's first version is "the disk does not show which words were in force", the same wording the statutes use; a day when a rule was suspended says so.

### 8.2 The history of one rule

Every version in order, each with: the words (diff to the one before), the adoption event, the notice and its delivery, **who proposed it** (the proposal's `by`) and **who recorded the adoption**, the board item and decision, and what it superseded. Withdrawn and defeated proposals are in it, labeled. This is the board's continuity: how one board's answer reaches the next.

### 8.3 Linking a use of a rule to the record

A **use** is something the association did that rests on a rule: a notice of a violation, a hearing, a fine, an architectural decision, a response to an owner, a board decision. A use is recorded where it already lives (the hearing, the request, the letter ledger). The rule record keeps a **link** only: `{record, version in force on the use's day, on, kind, ref, by}`. The link is made by a person or by a task that cites the rule's address as it records the use (an address `jason://rules/<id>` in the use's own record).

The view of a rule's uses shows each with the version in force that day, the outcome as recorded, and a count by outcome. It is **a list of the association's applications of its rule, not a finding**: it never says a rule was or was not applied consistently. Where a rule has no linked use the view says "no use linked" (a miss, not "never enforced"). It is how the board shows a written policy applied the same way, and how a reviewer reads it: with the rule's words, not a summary. Uses name owners; the open view shows the references only, and the board's view opens the name to the people who work with it.

### 8.4 Audit

The audit answers, from the log: who proposed, who drafted which words, who acknowledged which flag, who put it before the board, which notice was sent and when, what the vote record says, and who recorded the adoption. It is a read of the log, in order, filterable by person and act.

## 9. Commands

`jason rule-records` is free (nothing uses the name); the stored file path is `data/rule-records/` and `jason document-template --export-records` writes it. All proposed; each write takes `--by NAME` and is dry unless `--yes`. They wrap functions that exist or are small additions.

```
jason rule-records                                  # the records: id, number, title, status, version in force
jason rule-records ID [--as-of DAY]                 # one rule: the words in force that day, its adoption, its grants
jason rule-records ID --history                     # every version, who proposed, who recorded
jason rule-records ID --uses                        # linked uses, with the version in force that day
jason rule-records --compare [DOCUMENT]             # records against the working Doc, four words (section 4.1)
jason rule-records --propose KEY --records ID ... --by NAME             # start a proposal
jason rule-records --words KEY --record ID --file FILE --by NAME        # write the proposed words
jason rule-records --reason KEY --purpose FILE --effect FILE --by NAME  # the reason; the purpose and effect
jason rule-records --reach KEY --subject S --by NAME                    # subject, and the reading shown
jason rule-records --check KEY [--as-of DAY]                            # section 7, read only
jason rule-records --ack KEY --flag ID --note TEXT --by NAME           # acknowledge a flag
jason rule-records --to-board KEY --by NAME                            # a board item (tasks.board_items.propose)
jason rule-records --notice KEY ...                                    # the member notice (wraps jason rule-change)
jason rule-records --record-adoption KEY --decision ID --minutes REF --by NAME
jason rule-records --repeal ID | --suspend ID --until DAY | --withdraw KEY    # each a proposal or a recorded act
jason rule-records --effects KEY                                       # the plan of section 6.6, read only
jason rule-records --link-use ID --ref ADDRESS --on DAY --by NAME      # a use
```

`jason rule-change` stays: the proposal builds a `RuleChange` in memory and hands it to the existing notice code. `jason document-template --records stored|derived|auto` stays the switch for the renders.

## 10. What stays true

- **jason proposes; the board adopts.** There is no control that adopts a rule, approves a change, or recommends one. The board's vote is read from where it is recorded.
- **Recite, then label.** Every rule is shown as its stored words, with the citation and version, before any reading; the reach, the checks, and the authority readings are labeled jason's.
- **A miss stays a miss.** No grant found, adoption not on record, no use linked, no document read: each is shown as that, with its command.
- **Nothing in force is edited.** A change is a new version; a correction is a new log line.
- **Only stored words, and only what may be shared.** An adopted rule is open; a draft, a reason, and a conflict flag are the board's; counsel's letter is never copied here.
- **No dates from memory.** Every period and date comes from a catalog row or the meeting schedule.

## 11. Open decisions for a person

1. **Where the records live once the Doc is not the source** (the open decision of [document-templates.md](document-templates.md#9-open-decisions-for-a-person)): keep the Doc as the original with records derived (today), or records as the source and the Doc generated. Whether the board's register (a sheet) or `data/rule-records/` holds the words, and who may switch `source`. The design supports both; it needs one person to say.
2. **Who may take each act**: start and draft (any roster person?), record the adoption (the president or secretary, as the vote is), acknowledge a flag, link a use. And whether any act needs a second person (`SecondConfirm`).
3. **Whether a withdrawn draft is kept** and for how long.
4. **Suspension and correction**: whether each is a rule change. A question for counsel; the design records either.
5. **Whether a flag stops the notice** (a missing grant, a conflict, a duplicate of the declaration) or only needs a recorded acknowledgement. Recommended: acknowledgement, because jason's reading is a lead; the board decides.
6. **How `adopted` is shown for a first version whose adoption is not on record** (section 3.1): "in force, adoption not on record" and whether the board wants a list of them as a standing action item.
7. **Whether the annual policy statement is a separate record** (the statement is a document whose contents come from records), and who confirms its rule list each year.
8. **The use link's reach**: which uses are linked by the task that records them (hearings, architectural requests, responses), and which by a person.
9. **Executive session**: a draft discussed in executive session is the board's; whether the proposal view is held back from the open view until the notice, and by which flag.

## 12. Phases

- **Phase 1 (read):** `jason rule-records` (list, one rule as of a day, history), the compare against the Doc, and the use view, over the records that exist, with the new fields empty.
- **Phase 2 (the proposal):** the proposal store and event log; `--propose` through `--to-board`; the checks; the `RuleChange` built from a proposal; the notice through the existing path.
- **Phase 3 (adoption and effects):** `--record-adoption` reading the decision; the effects plan; the status fold; the use links written by the hearing and request tasks.
- **Phase 4:** `source: records` for a document, with the Doc generated; the second person where decided.

## 13. Not done

- Nothing here is built; the first table says what is.
- Comparing proposed words to the declaration is a reading, not a test, and is not measured.
- Which subjects an annual statement must carry is the catalog's; it is read, not copied.
- The reversal vote's own steps (a petition, a ballot) are not here: [notices.md](notices.md) and the election procedures.
