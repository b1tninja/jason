# Design brief: Rules and governing documents (the documents as amended, the rule register, a rule-change proposal, and the citation check)

One page of orientation for the design agent, for the cluster of screens specified in [screens/governing-documents.md](screens/governing-documents.md) (`#/documents`), [handoff-rule-records.md](handoff-rule-records.md), [handoff-rules-and-authority.md](handoff-rules-and-authority.md), [handoff-citations.md](handoff-citations.md), [handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md), and [handoff-document-kinds.md](handoff-document-kinds.md). It does not repeat them; it says what to read in what order, each screen to draw, what is built and what has no view, and a made-up community to draw against. Where a spec and this page disagree, the code wins and this page is corrected. The rule's design is [../rule-records.md](../rule-records.md); the workflow is [../workflows/board-governance.md](../workflows/board-governance.md) sections 2.2 (`rule-change`) and 2.7 (`owners-manual`).

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, or private fact; made-up samples only ("Oakview", "Example Declaration", 2099; every section number below marked fake is made up).

**Built, checked against the code on 2026-10-11.** *Loaders (read only, disk only):* `governing-documents` (P0), `rule-records`, `rule-record`, `rule-record-history`, `rule-record-compare`, `rule-uses`, `rule-events` (all six P0, board only, `jason.web.extra.rule_records` over `jason.tasks.rule_records`), `rule-changes` (P0; the specification's proposed changes, with `?key=` the sections, brackets, and the CIV 4360 timeline), `citations`, `citation-gaps`, `reference-works`, `reference-page` (open), `cite`, `living`, `conflicts`, `law-in-force` (P0, `jason.web.extra.rules_docs` over the `cite_document`, `living_document`, `document_conflicts`, and `law_in_force` tools; disk only, the read-through to lawlibrary held off; `cite` refuses a restricted book), `check-quotes` (P2; the text is POSTed to `/api/write/check-quotes/run` as `{text, as_of}`, never in a web address, and the GET refuses a `text`; `verify_quotes`, results only, writes nothing; a quotation found only in a confidential record is `withheld`, with no name, path, section, or words; the passage index also holds the insurance pages), `decisions` and `board-items` (P2). *Views:* `RuleChangeView` (`#/rules`), `ReferenceShelfView` (`#/reference`: `CitationGaps`, `CitedSections`, `ReferenceShelf`, `WorkReader`, `StandingPill`, `CitationChip`), `AssociationRecordsView` (`#/records`, its Governing documents tab reads `governing-documents` into `DocumentPreview`), `DecisionsView` (the next meeting's candidates only). Built parts: `Recitation`, `ReadingLabel`, `Stamp`, `Seal`, `StageSteps`, `Clock`, `DecisionBrief`, `PlanReview`, `Evidence`, `Doc`, `DataTable`, `Tabs`, `Findings`, `Caveats`, `Command`, `Confirm`, `HeldNote`. **No view:** `#/documents` is not in `SCREENS` (`App.tsx`); the six `rule-records` loaders are read by no file in `ui/src`; no `RuleRecordBook`, `RuleRecordPage`, `RecordStatus`, `RuleHistory`, `DocVersusRecord`, `ChangePage`, `ChangeFlow`, `AsOfControl`, `AsOfBanner`, `VersionLine`, `VersionTimeline`, `QuoteCheck`, `CiteBox`, or `DiffTable` exists. **No web loader at all** (the functions exist, as `jason.mcp.governance` and `jason.mcp.county` tools and `jason.api`): `rules-intake`, `rule-subjects`, `rule-citations`. (`check-quotes` takes at most 20,000 characters; the `POST /api/write/quote-checks` that records a check is not built, and is a different route from the read-only `POST /api/write/check-quotes/run`.) **Not built anywhere:** the proposal store, its event log, the comment record, `record-adoption`, the reversal intake, and the picks (`jason rule-records` writers; `rule-events` answers a proposal key with "no proposal store yet"). **Not registered:** the `rule-change` and `owners-manual` workflow definitions (only `owner-info-cycle` and `control-adoption` are), so no Work run exists for either; the "Part of run" banner exists in no code.

## A. The idea, and the rules that run through it

**The idea, in six sentences.**

1. Two questions: **what do the association's documents and rules say, on a given day, in their own words?** and **what stage is a change to a rule at, and whose move is it?**
2. Words come first. A statute, a governing document, or a rule is shown as its stored words, whole, with the citation and the version first (`Recitation`); a reading follows, set apart and labeled with whose it is (`ReadingLabel`); the two never share a block.
3. A document is shown **as amended**: the base, each amendment that is in effect and the section it changed, and each amendment **not in effect** listed apart and never merged into the words. jason's consolidated text is not an official restatement; the recorded instruments control.
4. A rule is a **record you can read on any day** (its versions, who proposed and who recorded each, the grant it rests on, the working Doc beside it, never merged). A rule has a stage word the loader derives from its log; the client computes none.
5. **jason proposes; the board adopts.** No control here adopts, approves, votes, or fills a bracket. The vote is read from Decisions; the secretary records the board's decision and, afterward, the adoption.
6. A quotation leaves jason as stored words, marked with its verdict, or with a named person's source on the record. A clean check says "found", never "verified".

**The rules** (each is in a spec or in AGENTS.md; a screen that breaks one is wrong):

- **Directors and officers have the same access to information.** Rules, their versions, and the documents are P0 and board-only today; the drafts, reasons, flags, and checks are the board's working record (P1) and are shown identically to every director and officer. No director-only or counts-only view.
- **The secretary records the board's decisions.** The proposal page shows the motion, mover, second, each director's vote by name, recusals, and outcome **read from the decision record** (`Stamp`: carried, failed, tabled, continued). It has no control to cast, change, or imply a vote. The adoption act is the secretary's, available only after a carried decision.
- **A rule on a Civil Code 4355(a) subject needs notice before adoption** (4360). The page recites 4360(a)'s operative words from the shelf, then labels jason's reading of the subject (listed, depends, not listed); `depends` shows both readings and "the board asks counsel"; a one-off decision on a specific matter needs no rule (4355(b)(2)) and is routed to Decisions.
- **Every date is a row's.** The 28 days, the 4-day agenda notice, the 15-day notice of adoption, and the 30-day reversal window are read from a notice-catalog row or the meeting schedule and name it; the comment deadline is "proposed, not the law's". "28 days have passed" is shown only after a delivery on record.
- **Recite the version that governs, with its day.** Every screen holds one day (`?as_of=`); every recitation names it. A day the disk does not show is "not shown", never a guessed version; a former section number is read as its successor and never as a conflict.
- **A miss stays a miss.** "No grant found" is a question for the board and counsel, never "unauthorized"; "adoption not on record" is a finding for a person, not proof; "no use linked" is not "not applied". Never "violation", "invalid", "approved" (of a rule), or "pass/fail" (of a check).
- **No colour-only meaning.** Every state is a word first, with a glyph beside it.

## B. Reading order

1. [screens/governing-documents.md](screens/governing-documents.md): the cite box, the sheet, the readings band, the states. Then [handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md) ("The day control", "The recitation, its version line", "The quote check").
2. [handoff-rule-records.md](handoff-rule-records.md): "The vocabulary", "The compare", "The change flow", "The vote is read, never taken". Beside it [../rule-records.md](../rule-records.md) sections 3, 6, 8.
3. `src/jason/community/rule_records.py` (`Status`, `CompareWord`, `NOT_ON_RECORD`, `status_on`, `history`) and `src/jason/web/sources.py` `rule_changes` (the built timeline). The words in section D are the code's.
4. [handoff-rules-and-authority.md](handoff-rules-and-authority.md) for the grant a rule rests on (`GrantRecital`, `TierWord`, `ReachLine`); [handoff-citations.md](handoff-citations.md) for `StandingPill`'s seven words.
5. [../workflows/board-governance.md](../workflows/board-governance.md) 2.2, 2.7, section 4 (the clocks), and [screens/work.md](screens/work.md) for where a step's work happens; [design-brief-work.md](design-brief-work.md) for the run page. [design-gaps.md](design-gaps.md) rows "Rule change", "Governing documents", "Decisions".
6. [handoff-document-kinds.md](handoff-document-kinds.md) and [screens/records-and-library.md](screens/records-and-library.md) only for the kind chip beside a document and the library's revisions band.

## C. The screens

### C1. Governing documents (`#/documents`, proposed; today the Governing documents tab of `#/records`)

The list of the association's governing documents, one row each: title, kind (`KindBadge`), the **copies** side by side (Recorded copy, Drive copy, as `DocumentPreview` draws them today: the recorded instrument first, because it governs), the **amendments** count with "N applied, N not in effect", the day the consolidated text was built, and the open findings and conflicts touching it. Above: the cite box and the one-day control (C2). Draw: a document with both copies; one with a Drive copy only ("no recorded copy on disk"); one kept only as recorded ("jason keeps this document only as recorded. It cannot give the words on a date."); a restricted book listed by name only; the empty and `found:false` states. The loader exists (`governing-documents`); the amendments, findings, and conflicts counts come from `living` and `conflicts` (built; section G).

### C2. One document as amended: a section with its history, and the as-of day

```
+--------------------------------------------------------------------------------------------+
| Example Declaration (Oakview) · Section 7.3 (fake) · Leasing           As of [ Oct 12, 2099 ] [Today]|
| Cite [ Declaration 7.3                                   ] [Cite]    jason://decl/7.3 [copy]        |
+--------------------------------------------------------------------------------------------+
| RECITED WORDS                                                                               |
| | [the section's words as stored, whole]                                                  | |
| Example Declaration, Article 7, Section 7.3 (fake), as amended Mar 12, 2094 (Amendment 1).  |
| Consolidated by jason from the instruments' own words; the recorded instruments control.    |
+--------------------------------------------------------------------------------------------+
| APPLIED  base (recorded Jan 2, 2090) · Amendment 1 (Mar 12, 2094) changed this section       |
| NOT IN EFFECT  Amendment 3: approved by members Sep 15, 2099; not recorded. Not merged.      |
| FINDINGS  words changed Jul 2098 with no adoption found [a finding, not a conclusion]       |
+--------------------------------------------------------------------------------------------+
| DEFINED TERMS (the document's definition governs)  Owner (1.20 fake) · Unit (1.31 fake)      |
| READINGS  [The board's reading, adopted Jun 10, 2098] ... [jason's reading] ...              |
| HISTORY | CITES (out) | CITED BY (in) · CONFLICTS touching this section: 1 · DUTIES: 2        |
+--------------------------------------------------------------------------------------------+
```

Fixed order: words, citation and version and caveat, then the amendments applied and not in effect, then terms, then readings, then history and references. Nothing sits between the words and their citation. The **as-of day** moves every recitation on the screen; on another day a banner says "The law and the documents on this screen are read as of DAY. Deadlines, records, and approvals stay today's." with Back to today; a day the document is kept only as recorded gives the sentence above and no words. Draw the day set before Amendment 1 (the base words, an earlier version), a day not shown, a day not yet come, a miss ("No section 7.3a. Did you mean 7.3(a)?"), and Compare two versions side by side (`DiffTable` is not built; two `Recitation`s until it is).

### C3. The rule register (a band of `#/documents/rules`, proposed; the `rule-records` loader is built)

A `DataTable`, one row per rule, in print order: number and title, **status** (`RecordStatus`), the version's adoption day and source (`RecordSource`), subjects, the grant's standing word, **Compare** word, an open-proposal marker ("1 proposal open", linking C5), a use count (a count of linked uses, "no use linked" at 0). Filters: status, subject, compare word, `?as_of=`. Counts in text beside any bar. Draw: a rule with every column filled; one "in force, adoption not on record" (the loader's own string, never shown as "adopted") whose compare word is "changed with no adoption found"; one with a proposal open; one repealed (last words, the day); one suspended (to a day); "no rule records yet" with `jason document-template --export-records`; derived-not-stored (a note); a document whose classification failed (its note; the rest stand). Under 720 px each row is a card: number, title, status word, then the compare word.

### C4. One rule as a record (`#/documents/rules/record/<id>?as_of=`, proposed)

Tabs: **Words** (the version the loader places on the day, recited whole, then `RecordSource`'s line and the caveat "jason's text of an adopted rule. The minutes and the recorded instrument govern."), **History** (every version newest first with a word diff to the one before, its adoption day and decision, who proposed and who recorded it, a gap before the first version, a withdrawn or defeated proposal labeled), **Grounds** (the grant recited whole, then the readers' tier word under a `ReadingLabel`; "no grant found" as a question), **Compare** (the adopted words and the working Doc's words side by side, never merged, the compare word, and the acts the word allows), **Uses**, **Audit**. The Compare tab has no act that makes the Doc the rule and none that edits it.

### C5. A rule-change proposal (`#/rules/change/<key>`, proposed; today `#/rules` opens a specification row)

```
+--------------------------------------------------------------------------------------------+
| Quiet hours on weekends (fake) · amends R-12 · drafted by Jane Example · board working paper  |
| [Drafting ✓] [Reason ✓] [Reach ✓] [Checked: 1 flag] [Before the board] [Noticed] [Decided] [Adoption] |
+--------------------------------------------------------------------------------------------+
| THE PROPOSED TEXT (first; CIV 4360(a)): R-12 now | proposed, diff · 1 choice left: [start time]   |
| PURPOSE AND EFFECT (labeled: the board's own description once adopted; jason's draft until then) |
| REACH  jason's reading of Civil Code 4355: listed. Recited: [4355(a) words from the shelf]       |
| NOTICE CLOCK  notice by Oct 14 · agenda notice by Nov 13 (CIV 4920) · comments due Nov 16        |
|   (proposed, not the law's) · decision Nov 17 · notice of adoption by Dec 2 · reversal window     |
|   30 days after that notice (CIV 4365) — each date names its row; "draft saved, no recipients"    |
| BOARD  item BI-2099-12 · motion draft (brackets open) · THE VOTE, READ: not yet decided           |
|   "The board decides at a meeting. The vote is recorded on the Decisions tab by the president or  |
|   the secretary."   After a carried decision only: [Record the adoption as Pat Example]            |
+--------------------------------------------------------------------------------------------+
```

Order is the statute's: the **text first**, then the purpose and effect (two texts, never one; the reason is board confidential and never noticed). The recitation of 4360(a) is from the shelf; the built `RuleChangeView` paraphrases it and puts the purpose card above the sections, so redraw both. Draw each stage's gate in words ("needs: the facts the notice catalog asks"), the stages that do not apply ("not needed: jason's reading of Civil Code 4355"), the endings (withdrawn, tabled, not adopted), a delivery late or only a file (the clock is not met; the decision moves; "blocked"), words changed at the meeting (the adopted words entered from the minutes differ from the noticed words: a reading for counsel, not decided), an emergency path, and a repeal. The proposal's whole page is a `HeldNote` outside the board's view (draft, reason, flags).

### C6. The citation and quote-check panel (`#/documents/check?as_of=`, proposed; `QuoteCheck` also under an answer in `AskPanel` and a draft)

The text first, each quotation marked in place with its verdict chip, then one verdict row per quotation, then the citations, then the caveats ("This checks words, not meaning"). Verdicts, in capitals as the command prints them: FOUND (exact or normalized), ALTERED (`QuoteDiff`: quoted and stored on two lines, differences also listed in text), MISATTRIBUTED, OTHER VERSION (which version, which was checked, a small `VersionTimeline`), NOT FOUND, and short ones listed "not checked". A citation row shows `StandingPill` (seven words: on the shelf, not exported, not found, renumbered, regulation, other code, unchecked) and, for a former number, the successor. `GiveGate`: clean leaves the control with "Quotations checked as of DAY: 3 found"; not clean replaces the control with the list and **Give it as written, as NAME** (a `Confirm` asking "Where these words are from"). Draw the not-yet-checked, checking, clean, not clean, changed-since-the-check, and no-passage-index states.

### C7. Where these link to the Work run

The `rule-change` run (steps r0 to r20) and the `owners-manual` run (o1 to o11) are designed in board-governance 2.2 and 2.7 and **not registered**. Draw from the sample: the run page's rail with the proposal page's step panels embedded read only ("Look at"), "Part of run Rule change: quiet hours, step 13 of 21" on the proposal page, the `decision` step as a link ("Record in Decisions") that lands on a decision (the Decisions record is a gap), a `person` step "Record the adoption" that opens C5's act, and a rule record page that says "A proposal is open: run Rule change R-12" with a link. The owners-manual decision o9 ("does the extraction need the 4360 notice?") is a board decision whose two readings are shown and whose lawful course either way is the notice.

## D. The shared components, each once

Reuse (built): the list in the "Built" paragraph. Specified, not built (draw from built parts and say so): those marked *new*. Proposed names follow the handoffs.

| Component | What it is | Data | States |
|---|---|---|---|
| `Recitation` (built) | The words whole, citation, version, caveat | `cite_document`: `found, citation, text, inForce, history, caveat` | in force; not shown (new caption "Not shown to be in force on DAY"); a miss with its reason; an outline, never joined words |
| `ReadingLabel` (built) | A reading, labeled | `whose`: jason, board (with the adoption day), counsel, open | jason's; the board's; two readings remain (both, "the board asks counsel") |
| `AsOfControl`, `AsOfBanner` *new* | The screen's one day | `asOf`, `today` | today; another day; a day not yet come; refused (the tool's words) |
| `AmendmentList` *new* (from `living_document`) | What amended what | `applied[], notInEffect[], held, findings[], amended[]{section,setBy,dated}, section{words,setBy,dated,history,removed}` | applied; not in effect (apart, "not merged"); a change with no adoption found; none |
| `RecordStatus` *new* (a `Pill`) | A rule's stage | `status`, `statusWord`, `adoptionOnRecord` | the seven words below, each with its day |
| `RuleRecordBook`, `RuleRecordPage` *new* | C3 and C4 | `rule-records`, `rule-record`, `-history`, `-compare`, `-uses`, `-events` | section C |
| `RuleHistory`, `DocVersusRecord` *new* | Versions with diffs; the two sets of words | `versions[]{stage,words,diffTo,adopted,proposedBy,recordedBy}`, `compare{word,adopted,doc}` | one version; a gap before the first; withdrawn; the Doc has a pending suggestion (not counted) |
| `ChangeFlow`, `ChangePage` *new* | The proposal's stages and tabs | `GET /api/rule-proposal` (proposed; no store) | section C5 |
| `NoticeClockLine` *new* | A date and the row it came from | `clock{source,noticeBy,decision,...,delivery}` | not sent; draft saved, no recipients; sent, delivery not read; delivered to n of n; after the deadline; no schedule ("needs the meeting schedule") |
| `VoteOnRecord` (`Stamp`, built) | The vote, read | the decision record | not yet decided; carried; failed; tabled; continued; no decisions file |
| `QuoteCheck`, `QuoteMark`, `QuoteDiff`, `GiveGate` *new* | C6 | `verify_quotes` report | section C6 |
| `StandingPill`, `CitationChip`, `CitedSections` (built) | A statute's standing on the shelf | `citations`, `citation-gaps` | the seven words |

**The code's words** (use exactly). A rule's status: **proposed · noticed · adopted · in force, adoption not on record · suspended · repealed · expired**. A version's source: the adopted text · the noticed text · the document's words as read, adoption on record · imported, adoption not on record · proposed words, not adopted. Compare: **same · the record is behind · the Doc ran ahead · changed with no adoption found**. A grant's tier: both readers agree · one reader: the rules · one reader: the model · the readers disagree. Reach: listed · depends · not listed. A check: not run · run, nothing found · found. A rule that has an adopted version and an open proposal shows **adopted** with the open-proposal marker; **proposed** and **noticed** are a rule's status only while no version is adopted. "in force, adoption not on record" is the loader's own string, drawn as sent; the page writes no other "in force" of a rule. "distributed" is not a code word: a notice's delivery ("delivered to n of n") is the ledger's. Fixed phrases: "jason's text of an adopted rule. The minutes and the recorded instrument govern.", "Consolidated by jason from the instruments' own words; the recorded instruments control.", "No adoption found is a finding for a person, not proof that none happened.", "A pending suggestion is not accepted and is not a rule.", "proposed, not the law's", "Record in Decisions", "Viewing as NAME (admin view): go back to yourself first".

## E. Glyphs

Use the console's: `scale` (authority, a grant), `scroll-text` and `file-text` (the words), `book-marked` (a governing document), `history` (versions), `gavel` and `rollcall` (the vote, read), `notice` (the member notice), `proposal` and `held-proposed` (a draft), `stamp` (adopted), `calendar-clock` and `clock` (a clock), `link` and `paperclip` (a use, a reference), `circle-question-mark` (a miss, a question for counsel), `triangle-alert` (a finding, a change with no adoption found), `circle-check` (found, done), `lock` (held), `for-secretary`. New, named for the idea: an **amendment not in effect** mark (a page with a dashed edge, beside "not in effect"); a **quotation verdict** set for FOUND, ALTERED, OTHER VERSION, NOT FOUND (a quote mark with a check, a swap, a clock, a slash; the verdict word always beside it); a **working Doc against the record** pair mark for the Compare tab. Each sits beside its word.

## F. Decisions that are the design's, in one list

1. **Where it lives:** `#/documents` with rules and authority as a sibling route under it and proposals at `#/rules/change/<key>` (the handoffs' proposal), or one route that holds all (decision 1 of the rule-records handoff). The loaders are the same.
2. **The page for a section:** the three-column history/cites/cited-by below the readings (recommended on wide screens) or tabs; and whether the whole section opens beside a subdivision's split by default.
3. **The as-of control:** one day per screen in the address (recommended) or a pinned working-session day.
4. **The register's density:** whether the compare word and the use count share a column, and whether four compare words are too many for one filter.
5. **How "adoption not on record" reads in a table of forty:** a word plus a mark, and whether the book lists them as one action item for the board.
6. **The proposal rail:** a left rail (recommended, matches Work) or a stage strip on top, and how the stages that do not apply fold.
7. **Timeline scale for versions:** a time axis with open ends faded to "not recorded", equal steps, or the table only.
8. **Confirm wording** for each act (the handoff's drafts), and whether a record the person links shows a `Doc` preview in the dialog.
9. **The quote check's trigger and the "checking" state**, and where a verdict chip sits in dense text.
10. **Print:** the rule as a record for the board's packet (words, adoption, notice, version of the day) and the proposal for the notice.

These are not the design's: who may draft, acknowledge a flag, put a change before the board, or record the adoption; whether a flag stops the notice; whether `source: records` is offered; whether the owner view shows an adopted rule and its notice; and a comment-deadline policy.

## G. What can be designed now, and what waits

| Part | Now | Waits on |
|---|---|---|
| Governing documents list with both copies | Yes; `governing-documents` is built | A route and view for `#/documents` (today only a tab of `#/records`) |
| One document as amended, a section, the as-of day | Yes, from section H | The views; `AsOfControl`; `DiffTable` (the loaders `cite`, `living`, `conflicts`, `law-in-force` are built) |
| Rule register, one rule, its history, its grounds, Compare, Uses, Audit | Yes; the six loaders are built | The views; `GrantRecital` needs `rule-subjects`; Uses links only hearings and open-session decisions that cite `jason://rules/<id>` |
| Rule-change proposal page | The read half, yes (the specification's row, its brackets, the timeline) | The proposal store, event log, comment record, `rule-proposal`, `-checks`, `-effects`, the writers, and `record-adoption` (rule-records phases 2 to 4) |
| The vote, read; the adoption act | Draw `VoteOnRecord` from `decisions` | The Decisions record screen (design-gaps D-REC); `record-adoption` |
| Citations and quote check | `StandingPill`, `CitedSections`, `CitationGaps` built; draw `QuoteCheck` from the sample | The `QuoteCheck` view, `POST /api/write/quote-checks` (the record of a check), the passage index (the `check-quotes` loader is built) |
| The Work run | The run page and its panels | The `rule-change` and `owners-manual` definitions; the "Part of run" banner and run-link grammar (design-gaps L1) |
| Hearings, elections, jason's own rows, picks between documents | Out of this brief | Their own briefs; `rules-intake`, `rule-citations`, the pick store |

## H. A made-up community to design against

"Oakview HOA" (no real association). Today is **Oct 12, 2099**. Roster: Robin Sample (manager), Pat Example (secretary), Lee Sample (director), Jane Example (drafter). Documents: Example Declaration (base recorded Jan 2, 2090; Amendment 1 applied Mar 12, 2094; Amendment 2 applied Jun 1, 2097; **Amendment 3 approved by members Sep 15, 2099, not recorded: not in effect**), Example Bylaws, Rules and Regulations. Sections are **fake**: Declaration 7.3 Leasing, 1.20 Owner, 1.31 Unit; the statute for the quote check is **CIV 9901 (fake)**, two versions (fifteen days to Jun 30, 2095; fourteen after). The recited words on screen are stored words; a bracket stands for them here.

| Rule | Status shown | Version and source | Compare | Grounds | Why it is in the sample |
|---|---|---|---|---|---|
| R-12 Quiet hours | adopted Apr 14, 2098 | v2, the adopted text (BI-2098-07, minutes) | same | both readers agree (bylaws 7.8, fake) | The ordinary record; "1 proposal open" (rc-0007) |
| R-3 Trash containers | in force, adoption not on record | v1, imported | changed with no adoption found (Doc changed Mar to May 2099) | rules on file, no grant found | The finding and the question for counsel |
| R-15 Pool guest limit (a new rule) | noticed | v1 proposed words, noticed Sep 20, 2099, delivered to 118 of 120; decision Oct 20; no version adopted | n/a: "no version in force on this day" (shown as the record's gap) | authority named, no rules on file | A noticed proposal with a delivery gap, and the one case where the status is "noticed" |
| R-5 Signs | repealed Nov 2, 2098 | last words kept | same | one reader: the model | A repeal; last words and the day |
| R-9 Gate hours | suspended to Nov 30, 2099 | v3 | the Doc ran ahead | general power only | A suspension; a question whether it is a rule change (counsel) |

**The proposal to draw** (all dates sample): rc-0007 "Quiet hours on weekends (fake)" against R-12, drafted by Jane Example Sep 30; reason and purpose written; reach listed (CIV 4355(a), jason's reading); checked, 1 flag (a possible overlap with Declaration 9.2, fake) unacknowledged and 1 open bracket ("[start time]"); notice draft saved with no recipients; notice by Oct 14; agenda notice by Nov 13 (CIV 4920); comments due Nov 16 (proposed policy); decision Nov 17; notice of adoption by Dec 2 (CIV 4360(c)); reversal window 30 days after that notice (CIV 4365). Board item BI-2099-12, status proposed; vote not yet decided.

**Panels to draw:** C2 for Declaration 7.3 on Oct 12, 2099 and on Jan 1, 2094 (before Amendment 1); the main proposal page with the flag open; the same after the decision is carried (the adoption act appears for Pat Example, not for Lee Sample, who reads the same page without the act); the same where the delivery is late (blocked clock); the Compare tab for R-3 and for R-9; the quote-check text "The notice is given fourteen days before the hearing" (OTHER VERSION: the later fourteen-day words quoted, the fifteen-day version checked as of Jun 1, 2095), one ALTERED, one NOT FOUND, one FOUND; a former number (CIV 9803(g), fake) read as CIV 9901; and the empty states: no rule records yet, no proposal store ("no proposals yet"), no outline.
