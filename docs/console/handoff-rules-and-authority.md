# Handoff: bringing in the rules, who may make them, and which document a citation means

For the design pass on the screen where an association's rules are brought in and checked. The data exists today in files and commands and in no screen: the documents that hold rules and their parts (`jason manual`, `jason segments`, `jason outlines`), the grants of rule-making power a rule pass and a local model found (`jason rules --find --model`, `jason rules`, `jason rules --subjects`), a citation scoped to the document it means (`jason cite --in KEY`, `jason cite --scan`), and jason's own rule rows recited as data (`jason cite "owner_responses.RULES: delivery"`). Behind them: `jason.community.rule_authority`, `jason.tasks.rule_authority`, `jason.community.scoping`, `jason.tasks.cite_scope`, `jason.tasks.rule_rows`, and `jason.community.document_segments`. The design is settled in [../rule-authority.md](../rule-authority.md), [../rule-citations.md](../rule-citations.md), and [../document-segmentation.md](../document-segmentation.md). No loader serves them yet ("Where it goes" lists the ones to add), and one write is built as a command only (`jason rules --review`).

The format follows the earlier handoffs ([handoff-applicability-questions.md](handoff-applicability-questions.md); [handoff-confirmations-queue.md](handoff-confirmations-queue.md)). The words on screen follow [content/style.md](content/style.md), the patterns [content/patterns.md](content/patterns.md), and the components [components.md](components.md). Built parts it uses: `Recitation`, `ReadingLabel`, `Pill`, `Doc`, `DataTable`, `Findings`, `Caveats`, `Command`, `Confirm`, `Card`, `Tabs`, `StageSteps`, `HeldNote`, `Stat`, `QuestionCard`, `Seal`, and `RemoteView`. Most rows of the components table are an arrangement of one of them; its "Built from" column says which.

**How this page meets the other handoffs.** Each shares a component or a question with this page; each is linked where it applies and not repeated.

| Neighbour | What it shares with this page | Where this page says so |
| --- | --- | --- |
| [screens/governing-documents.md](screens/governing-documents.md) | the cite box, `Recitation` of a section, the readings band, the conflicts; this screen is a route under it | "Where it goes" |
| [handoff-programs.md](handoff-programs.md) | a rule is an `OPERATING_RULE` instrument the board adopts; this page shows the **authority** side, that one the **adoption** side and the draft's way to the board. An `AuthorityLine` is the "within the authority of the board" element of an operating-rule program row | "The authority map"; "The rule-change path" |
| [handoff-confirmations-queue.md](handoff-confirmations-queue.md) | a reading by one reader is a lead, never the board's; a reading of what words *mean* is confirmed there, a *fact* about which document was written is picked here; a subject with two readings under 4355(a) goes to the board and counsel, not to a click | "The citation's choice"; decision 3 |
| [handoff-applicability-questions.md](handoff-applicability-questions.md) | a missing fact is a question a named person answers; `rule_scope` and `rule_change` are that page's event facts for the notice catalog, which this page links and does not repeat | "The rule-change path" |
| [handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md) | `?as_of=` is this screen's day; each grant's words are checked verbatim and show the verdict word | "What the design must keep" |
| `handoff-citations.md` (peer's, not yet committed) | `CitationChip` and `StandingPill` for a statute a document cites and whether the shelf holds it. A grant's limit that cites a statute uses that chip | "The authority map" |
| [screens/onboarding.md](screens/onboarding.md) | the session's ordered tasks, `QuestionCard`, and the second person on a high-stakes answer | "Bring in the rules" |
| [screens/board-items.md](screens/board-items.md) | a lead for the board's canvas becomes a board item on the agenda; the vote is recorded where every vote is | "The authority map"; "Where it goes" |

## The idea in one line

Rules are brought in **document by document, part by part, with the way each numbers its sections**, so a citation can find its words; each subject then shows **the provisions that grant the power to make rules on it, recited, beside whether a rule on it is on file**, so the board sees where authority exists and no rule has yet been written; and **where a citation could mean two documents, both are shown and a person's choice is recorded, never guessed**. Every grant is a lead read by one or two readers, each tier a word; every reading is labeled whose it is; jason proposes, the board adopts; a miss stays a miss.

## Bring in the rules (the onboarding task)

A task in the onboarding session ([screens/onboarding.md](screens/onboarding.md)), after the documents are located and their outlines are read, and before the first notice or fine rests on a rule. It is one list, in order; a step names what it needs in words, and a step is never "blocked" by color alone. The console shows the steps and runs none of them without a person.

| Step | The board is shown | Comes from | A state in words |
| --- | --- | --- | --- |
| 1. The documents that hold rules | each document that may hold a rule: the declaration, the bylaws, the articles, the operating rules, the election rules, a policy, an owner's manual, with its kind, its copies (`Doc`), and **which holds rules** ("holds rules" / "restates the declaration" / "guidance only"). The page recites the statute's test of a rule's authority first (`Recitation` of Civil Code 4350(b), from the shelf); a document the profile lists with no copy is "not on file" | `Community.governing_documents()`, `jason manual`, the documents' kinds | on file, not on file (with the command), several copies (which is read), not read |
| 2. Their parts | for an owner's manual or a scan holding several documents: each **part** as a row: its kind (rules, policy, form, exhibit, guidance, cover, contents), its pages, the heading it starts at, how it was found (running header, title, bookmark, contents), and the reader's tier; an exhibit is shown as a child document, not a part. For the manual, each *section's* kind as the code states it: a rule, a copy of the declaration or a statute, a policy bound in, guidance, mixed, **unclear** | `document_segments` (`Part`, `Segment`), `manual.SectionKind` | read; not read (the command `jason segments FILE`); a section **unclear** is a question for a person with the suggestion labeled jason's (a `QuestionCard`); no parts found ("a document that is one part says nothing more") |
| 3. How each is numbered | the numbering style each document prints, in the document's own words: lettered rules ("R-3", "R-3(e)"), dotted ("2.1"), article and section ("Article 4", "4.15"), numbered lists, or **titles only**; whether a number is printed twice (addressed by place, `R-3(i)~2`); and the **round trip**: of the numbers the outline holds, how many resolve to exactly one section when written as a citation, and each that does not, listed | `outlines_of`, `cite_scope.Index`, the outline round trip ([../rule-citations.md](../rule-citations.md#rule-documents-as-addressable-sections)) | outlined (n sections, n resolve, n listed); no outline (`jason outlines KEY`); outline stale after a fixed reader ("read it again"); titles only (addressed by words, or not at all) |
| 4. Read for grants | whether `jason rules --find` has run, when, with which readers (the rules; the rules and a local model), over which documents, and what it needs before it can: **a model reading holds the GPU lock and needs preflight** (`local_ai.preflight`), shown as the machine's state in words ([handoff-storage-and-settings.md](handoff-storage-and-settings.md)); the count of candidates, grants, limits, references | `rule_authority.run` and the stored `data/rules/authority.json` | not run (the `Command`); ran with the rules only; ran with the model too; the model reader waiting on the GPU lock (the holder named); preflight refused (the reason); stale against a changed document |
| 5. What it found, in front of a person | the leads that need a person first, each linking its band: each **conflict** tier row (the readers disagree), each subject whose standing is "rules on file, no grant found", each citation that is ambiguous or unknown, and each section the step-2 reading left unclear. Counts in text; none is a finding of fault | `by_subject`, the tiers, `cite_scope.read_text` | all four lists; one empty ("none"); "not read yet" where the step before has not run, never a zero |

**The page says what a step does not do:** it makes no rule and adopts none; it reads. A document with no outline is a miss with its command, never an empty row. A document the reader did not collect from (a resolution, an annexation) is listed as "not read for grants" with its kind.

The task's state is jason's reading, labeled, and a step that is "complete" means the reader ran on the stored words, not that the board has checked them. The word on the step is "read", never "verified".

## The components

| Component | Built from | Where it renders | Data | States to design |
| --- | --- | --- | --- | --- |
| `RulesIntake` | `StageSteps`, `Card` | the onboarding session's task; the band **Documents** of `#/documents/rules` | `GET /api/rules-intake` | the five steps above, each with its gate in words; one step's loader failing (that step shows the tool's note and command, the others stand); nothing brought in at all (the profile lists no governing documents: the setup question); all five read |
| `RuleDocumentRow` | `Doc`, `Pill`, `Findings` | step 1; the Documents band | one document: key, kind, copies, `holdsRules`, `readForGrants` | holds rules; restates the declaration; guidance only; not on file; not read; several copies |
| `PartsStrip` | `DataTable` of parts, `Pill` | step 2 | `parts[]` and `sections[]` of one document | a part (kind, pages, anchor, found by, tier); an exhibit child ("Exhibit A", its own parts); a part of unknown kind (its book not named by the canon: a miss, shown as a miss); a section's kind with its letter; unclear (a question) |
| `NumberingLine` | `Findings` | step 3 | `numbering` of one document | style in words; printed twice; titles only; outline stale; round trip n of n, with each failure listed |
| `RuleReadRun` | `Card`, `Command`, `Confirm` | step 4 | `run` | the states above; **Run the rules' reading as Jane Example** is a `Confirm` that queues the job (the rules alone, under a second); **Add the local model** is its own `Confirm` that says it holds the GPU lock and unloads the model after |
| `AuthorityMap` | a list of `AuthoritySubject` | the band **Authority** | `GET /api/rule-subjects` | by standing, filtered by tier; no read yet; a read with no grant found at all; a subject filter |
| `AuthoritySubject` | `Card`, `AuthorityStanding`, `ReachLine`, `GrantRecital`, `OnFileLine` | each subject | one `SubjectRow` | the six standings below; grants named; a general power only; guidance-only grants set apart; restrictions the documents state themselves |
| `AuthorityStanding` (a `Pill` preset) | `Pill` | `AuthoritySubject`; the intake's step 5 | `standing` | the six words in "The vocabulary" |
| `GrantRecital` | `Recitation`, `ReadingLabel`, `TierWord` | inside a subject; the Authority band's list by grant | one grant: the words, the citation, the day's version | the document's words first, whole, with the citation (`bylaws#7.8`), the version in force on the screen's day, and the caveat; then, set apart, **the readers' reading**: holder, subjects, conditions (each a quote), the procedure (a quote), labeled whose; a quote that is not verbatim is dropped and the drop noted; a condition "elsewhere in the section"; words that do not verify against the shelf (`verify_quotes` verdict) |
| `TierWord` (a `Pill` preset) | `Pill`, `ReadingLabel` | `GrantRecital`; the list | `tier`, `readers`, `consistency` | **both readers agree** (likely); **one reader: the rules** and **one reader: the model** (suggested; the model alone is a suggestion held for a person); **the readers disagree** (conflict, with which reader found it). The model's other samples show as a count ("3 of 3 other samples agree"), captioned "a filter, not a second reader", never as a percent confidence |
| `ReachLine` | `ReadingLabel` | each subject | `reach` (`listed`, `depends`, `not listed`, with `cites`) | the three words, labeled "jason's reading of Civil Code 4355(a), 4355(b)"; `depends` says two readings remain and counsel reads them |
| `OnFileLine` | `Doc`, `Recitation` | each subject | `rules[]`, `restrictions[]` | rules on file (the section and its first norm sentence); **no rule on file**; a document's own restriction (a prohibition the declaration states itself) listed beside, "a restriction the declaration states itself needs no rule"; a guidance part is never a rule on file |
| `AuthorityLead` | `HeldNote`, `Confirm`, `Command` | a subject with a grant and no rule | the subject, its grants, its `reach` | **a lead for the board's canvas**: the grant recited, the 4355 reading labeled, and the line "Where the law and the documents leave this open, the board may adopt a written policy." The act is **Put it on the board's canvas as Jane Example** (a `Confirm`; proposes a board item with the grant's words, the subject, and the reading, and no recommendation); the item is then "On the board's canvas for Oct 20" in `HeldNote`'s words |
| `GrantReview` | `Confirm`, `Findings` | each grant row | `review`, `note`, `by` | unreviewed; confirmed; corrected; rejected, each with the person, the day, and the note; a reviewed row whose words changed ("orphaned": kept, labeled); the act is **Record my review as Jane Example** with a required status and an optional note; it says "a review of what the readers found, not an adoption of anything" |
| `RuleCitations` | `DataTable`, `ScopeBasis` | the band **Citations** | `GET /api/rule-citations?text=&citing=&on=` | for one text or one document: its citations by form, each resolved, ambiguous, or missed; counts in text; none found ("A citation the grammar does not read stays unread") |
| `RuleCitationRow` | `Pill`, `Recitation`, `Doc` | each citation | one `Scoped` result | resolved (the document, its `ScopeBasis`, and the section's words recited); ambiguous across documents; ambiguous in one document (printed twice); unknown document; not on the shelf; a reprint (`alsoPrintedIn`); a lead named nearby |
| `ScopeBasis` (a `Pill` preset) | `Pill` | `RuleCitationRow` | `basis` | the eight words in "The vocabulary", each with the one line the rules page gives; and `picked`, the person's, in "The citation's choice" |
| `AmbiguousChoice` | `Card`, `Recitation` x n, `Confirm`, `Command` | an ambiguous citation's row, opened | `scope.candidates[]`, `leads`, and the pick on record | both (or all) candidates side by side: each document, **as it would be cited** ("Bylaws Section 7.8", "Declaration Section 7.8"), whether it has the section, and its words recited; the leads named nearby, labeled "a lead; it narrows nothing"; no candidate preselected; the three acts in "The citation's choice"; a pick on record (who, the day, the basis words, the digest of both); a pick **stale** because a candidate's words changed since |
| `PlaceChoice` | `AmbiguousChoice` for one document | a section a document prints twice | `candidates[]` as places (`R-3(i)`, `R-3(i)~2`) | the same, each place's words and its heading; the pick records the place cited |
| `OwnRuleRow` | `Card`, `Seal` ("jason's own row"), `Command` | the band **jason's rows**; inside any plan item or citation that rests on one | `cite_document("owner_responses.RULES: delivery")` -> `kind: row` | the row's own words, its key, the action it gives, the condition it tests (the function's name, where written, its source), where the row is written; the label verbatim; the adoption (`board-item:KEY`) or **no adoption named**; unknown table (the registered tables listed); a row the table lacks (the rows it has); an attribute with its comment and where it is written |
| `RowLabel` | `ReadingLabel` (`whose="jason"`), `Caveats` | `OwnRuleRow`, and any list that mixes the association's rules with these rows | the loader's `caveat` | "jason's own rule row, a decision kept as data: not a rule of the association. The association's rules are its governing documents; a row that rests on a board decision names the board item." The words come from the loader and are never edited on the page |
| `RuleChangeHandoff` | `ReadingLabel`, `Command`, `HeldNote`, `Doc` | the foot of an `AuthoritySubject` with `reach`; the foot of a rule's page | `reach`, `cites`, the specification's proposed changes (`jason rule-change --list`) | `listed`: "needs notice to members before adoption (Civil Code 4360)" as a reading, with the `Command`; `depends`: both readings stated, "the board asks counsel", and "the course lawful under either reading is the notice"; `not listed`: "Civil Code 4355(b) may take the change out of 4360 and 4365", a reading; a subject with no `reach` row (`other`): a miss. It builds nothing: it links `#/rules` (Rule changes, built) and `#/notices?catalog=` and shows the `Command` |

## The vocabulary

Every word is the code's, so the console and the terminal agree; no state is color alone.

**A grant's tier** (`rule_authority.Tier`, the agreement of two independent readers, never one reader's stated confidence): likely · suggested · conflict. The console says it in words that name the readers, per the pattern for a reading by a model ([handoff-confirmations-queue.md](handoff-confirmations-queue.md); [../ocr-correction.md](../ocr-correction.md)):

| Word on screen | `tier` | Means |
| --- | --- | --- |
| both readers agree | `likely` | the rules and the model read a grant (or both a limit), with the same holder |
| one reader: the rules | `suggested` | the rules alone read it (the only tier without the model) |
| one reader: the model | `suggested` | the model alone; a suggestion held for a person |
| the readers disagree | `conflict` | one reads a grant and the other reads no, a reference, or a limit; kept as a lead with the reader that found it |

**What the words read as** (`Answer`): grants the power · limits how rules are made · refers to rules adopted elsewhere · no grant. The last two are listed only on request ("All readings"). **Holder** (`Holder`): the board, the association, a committee, the members, an officer, the manager, other, **not stated** (an unstated holder agrees with a stated one). **A limit's kind** (`Condition`): consistent with the documents, consistent with the law, reasonable, notice, member vote, board vote, in writing, uniform, necessary, emergency, board approval, supplements, discretion.

**A subject's standing** (`Standing`), verbatim from `jason rules --subjects`:

| Word | Meaning | The row shows |
| --- | --- | --- |
| authority named, rules on file | a grant names the subject; a rule on it is on file | the grant, then the rule |
| authority named, no rules on file | a grant names it; no rule states a norm on it | the grant, then "no rule on file", then **the lead for the canvas** |
| general power only, rules on file | only a general power reaches it; a rule is on file | the general power (set apart: it "says nothing of this subject in particular"), then the rule |
| general power only, no rules on file | the same, with no rule | the general power, "no rule on file", the lead |
| rules on file, no grant found | a rule is on file; no grant found that reaches it | the rule, then "no grant found": **a question for the board and counsel, never an accusation**; the grant may be in the law itself or a document not read |
| neither found | nothing found | "nothing found for this subject" |

Never a "gap", "violation", "unauthorized", or "invalid". "No grant found" is not "no authority" ([../rule-authority.md](../rule-authority.md#what-it-is-and-what-it-is-not)). A subject with a grant and no rule is a lead for the board's canvas, with the same standing in the board's own register of leads.

**A subject's reading under Civil Code 4355(a)** (`Reach`): listed · depends · not listed. It is jason's reading, labeled so; it decides nothing.

**A review** (`Review`): unreviewed · confirmed · corrected · rejected, each by a named person.

**A citation's states** (`scoping.Standing`, and `found`/`reason`): resolved · ambiguous (documents) · ambiguous (twice) · unknown document · not on the shelf (`not_in_document`, `parent_only`, `no_outline`) · jason's rule row.

**A citation's basis** (`scoping.Basis`), each with its line: **named** (the citation names the document) · **self** ("this X" in the document X) · **citing** (a bare number, written in a document that has it) · **amends** (in an amendment with no such section: the document it amends) · **only** (outside the documents, and exactly one document has it: elimination, with every document considered listed) · **form** (the kind of thing cited narrows the documents) · **book** (a common name for several documents; the one that has the section, the others in `alsoInBook`) · **part** (the same rule printed in a part and in a document adopted apart, with the same words: the document adopted apart; the other a reprint). `only`, `form`, `book`, and `part` are the judgment calls and each is labeled "chosen by elimination" or "chosen by form" in text. The basis is a label on how jason found the section; what is recited is the stored words.

**Added by this page, proposed:** `picked`, a person's choice between documents that both have the section, recorded with their name and the day; it is the person's, not a basis jason computed.

## The authority map

`AuthorityMap` is the list of subjects, each an `AuthoritySubject` card in the order of the closed list (`Subject`), with the standings that need a person first. A card reads top to bottom, in this order, and never reorders:

1. **The subject** and its standing word.
2. **The provisions that grant the power**, one `GrantRecital` each. The document's words are recited first, whole, with the citation and the version in force on the screen's day (an amended document is read in that day's version, [handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md)), then the caveat ("jason's consolidated text is not an official restatement; the recorded instrument governs"). Beneath it, set apart under a `ReadingLabel` ("the readers' reading: not the document's words"), the tier word, the holder, the subjects, the conditions each with its quote, and the procedure's words. The recited words are what the document says; "the board holds it" and "its subjects" are the reader's reading and are labeled.
3. **General power**, apart and labeled: a grant of "the use, occupancy, management, and operation of the development" reaches every subject and says nothing of this one in particular, so it is listed under "General power" and never merged into the named grants.
4. **Limits that bear on it** (`related`): notice, the meeting, a reversal vote, readoption, emergency changes, each a quote with its citation, as leads linked to the grant they bear on. A limit that cites a statute shows its `CitationChip`.
5. **Rules on file**, each its section, its document, and its first norm sentence, from a rules document, an operating rule, an election rule, a policy, or a rule or policy **part**; or **no rule on file**. A guidance part's statement of the board's power is shown under "Said in guidance" and counted nowhere: "A guide's description of the board's power is not the power. Cite the document it points to."
6. **The document's own restrictions**, where the declaration states one itself.
7. **The 4355 reading** (`ReachLine`) and, below, the `RuleChangeHandoff`.
8. **The lead for the canvas**, only where the standing is "authority named, no rules on file" or "general power only, no rules on file": **Put it on the board's canvas as Jane Example**. It carries the recited grant, the subject, the reading, and a line "No rule is proposed here; the board may adopt a written policy where the law is silent". It proposes no text and no recommendation, and it never says a rule is needed. For a delegated standard ("a reasonable number, as determined by the Board"), the line is "the board's determination is the row that is missing; until written, the standard is open": that is the grant's own effect, quoted, not a duty jason imposes.

A grant is also a row by itself (the list "by grant"), with `GrantReview`, so a person can read every grant of one document in its order. A `conflict`-tier row is listed first, labeled, with the reader that found it and the other's answer.

A subject whose grant and rule disagree in the words (a rule on parking where the grant names only pets) is not a finding of fault: it is "rules on file, no grant found" if no general power reaches it, else "general power only, rules on file", and the page says which.

## The citation's choice

A rule that says "section 7.3" does not name its document. `jason cite` scopes the number from where it is written; where one document has it, the answer says why (the basis); where two documents have it and print different words, the answer is `ambiguous_document` and names both. The screen shows that state and records a person's pick.

**What `AmbiguousChoice` shows, in order:**

1. The citation as written, in its sentence, with the document it is written in and the day (`citing`, `citing_day`).
2. **Both candidates**, each a `Recitation` of its own words for that number, headed by the citation as it would be written ("Bylaws Section 7.8", "Declaration Section 7.8"), with the version on the citing day. A candidate that does not have the section is listed with "no section 7.8" and a note how it numbers ("numbers its sections R-n").
3. **Leads**, labeled: a document named near the citation ("CC&R" earlier in the paragraph) is "a lead; it narrows nothing".
4. **The three acts**, none preselected, in a `fieldset` (radio buttons, the document's name as the label):
   - **This citation means the Bylaws**, and **This citation means the Declaration** (one radio each candidate): the person records which document they read the author to mean, with an optional line "why" (a few words).
   - **It means neither, or I cannot tell**: records that no document was chosen and leaves it ambiguous, with the person's reason. It is a recorded answer, not a dismissal.
5. The `Confirm`: **Record my pick as Jane Example**, with the citation, both documents, and the pick restated above the button, and the CLI equivalent `jason cite --pick ID DOCUMENT --by NAME` (proposed). The route is proposed: `POST /api/write/rules/citation-pick` `{citation, citing, day, document, why, by}` behind the write guard.

**What a pick is.** It is the person's reading of which document the author meant, kept as data beside the citation: the citation, the text it is in, the two documents' digests, the person, the day, and the reason. It is shown as **"picked by Jane Example, Oct 5, 2099"** and `ScopeBasis` reads `picked`. It does not change what the citing text says, does not choose a document for any other citation (even the same number in the same text), and does not edit the rule: the words recited under a picked citation are the picked document's stored words. Where either document's words change after the pick, it is **stale**: the pick stays on record, is marked "the words changed since", and the citation is ambiguous again until a person records a pick again. Nothing jason computes writes a pick, and `jason cite --scan` counts a picked citation apart from a resolved one.

**What a pick never is.** It is never jason's guess, never a default ("the first document"), never the most common reading, and never "the document whose section is closer". A citation inside an adopted rule's own words keeps those words as the board adopted them: a pick beside it records the reader's understanding and does not amend the rule (decision 3).

**An ambiguous citation inside one document** (the document prints a section twice, `ambiguous`) is a `PlaceChoice`: each place with its words and its heading, the pick recorded as the place cited (`R-3(i)~2`), and the same rules.

**The other misses stay misses.** An unknown document ("Section 3 of the Master Plan") is "a document jason does not hold" and a question for a person to place the document on the shelf (the document-intake path, not a pick). A section a known document does not have is "no such section" with how the document numbers. No outline is "jason has no outline of this document yet" with `jason outlines KEY`.

## jason's own rows

A decision jason keeps as data (`owner_responses.RULES`, `owner_info.FOR_A_PERSON`, an attribute the specification holds) is **jason's, not the association's.** `OwnRuleRow` shows it where a plan item or a citation rests on one, and the band **jason's rows** lists the registered tables. Rules the screen keeps:

- **Label before words.** The row opens with `RowLabel` (the loader's caveat, verbatim), then its own words, its key, the action it gives, the condition it tests (the function's name, where it is written, its source), and where the row is written.
- **Never in the association's list.** The Authority map, the rules on file, and the citations by document never contain a row. A list that must mention both shows the rows under their own heading with the label, and a count of each, never one total.
- **The adoption is shown or its absence is.** A row that names a board item shows it (`board-item:KEY`, opened in `#/actions`); a row that names none says "no adoption named", never a guess and never "adopted". A row is jason's reading of a decision the board made; it becomes a rule row only after the board's decision ("Where the law is silent, write it down").
- **A prose rule is a miss.** A plan item that cites "the board's rule" as prose is shown as "not an address: it stays a miss until the item cites the row or the document it means".
- **Read only.** The console edits no row; a row is code a person reviews and commits.

## The rule-change path

A rule on a Civil Code 4355(a) subject needs notice to members before adoption (4360). The `RuleChangeHandoff` is the hand-off, and it builds nothing. It shows, in order:

1. The subject's `reach` as a labeled reading, with the sections it cites, after the statute's own words from the shelf (`Recitation` of 4355(a), the version on the screen's day).
2. For `depends`: both readings, named, "the board asks counsel", and "the course lawful under either reading is the notice" (AGENTS.md: "take the course that is lawful under either reading").
3. For `not listed`: "4355(b) may take the change out of 4360 and 4365", a reading; and the 4355(b)(2) caveat that a one-off decision needs no rule. Words from the shelf, not this page.
4. The `Command` `jason rule-change KEY` (the proposed changes in the specification: `jason rule-change --list`), and links to `#/rules` (Rule changes, built) for the stages and `#/notices?catalog=` for the notice's rows with the facts said (`rule_scope`, `rule_change`: [handoff-applicability-questions.md](handoff-applicability-questions.md)).
5. The words "The board decides at a meeting. This page proposes no rule and has no control that adopts one."

The 28-day notice, the draft email, and the decision meeting are `jason rule-change`'s; the member notice is a Gmail draft a person saves behind its own `Confirm` on `#/rules` ([approval-workflow.md](approval-workflow.md)). A rule that is on a listed subject and has been adopted is a program row's `OPERATING_RULE` evidence ([handoff-programs.md](handoff-programs.md)); this page does not read the adoption act.

## Data shapes

Made-up documents, people, and sections. A recited sample is a bracket placeholder; on the screen the words come from the stored section, never from this page. Keys are the shapes the code returns today where it returns them (`jason rules --json`, `jason rules --subjects --json`, `jason cite ... --json`), and proposed where marked.

`GET /api/rules-intake` (proposed; `rule_authority.outlines_of`, `manual_parts`, `segments.parts_in_store`, the stored authority file):

```json
{
  "found": true, "community": "Example Village HOA", "asOf": "2099-10-05",
  "documents": [
    {"key": "bylaws", "title": "Bylaws", "kind": "bylaws", "holdsRules": "restates", "readForGrants": true,
     "copies": [{"label": "Drive copy", "doc": {"id": "d-1", "name": "Bylaws (as amended)"}}],
     "numbering": {"style": "article and section", "example": "Article 7, 7.3", "outlined": true, "sections": 64,
                   "roundTrip": {"numbers": 64, "resolve": 64, "twice": 0, "failed": []}, "stale": false}},
    {"key": "rules-manual", "title": "Owner's manual", "kind": "owners manual", "holdsRules": "holds rules", "readForGrants": true,
     "copies": [{"label": "Recorded copy", "doc": {"id": "d-2", "name": "Owner's manual"}}],
     "numbering": {"style": "lettered rules", "example": "R-3(e)", "outlined": true, "sections": 41,
                   "roundTrip": {"numbers": 41, "resolve": 39, "twice": 2, "failed": [{"number": "R-3(i)", "why": "printed twice: cite by place R-3(i)~2"}]}, "stale": true},
     "parts": [{"key": "rules", "title": "Community Regulations", "kind": "rules", "pages": [6, 14], "anchor": "B", "foundBy": "title", "tier": "likely", "book": "rules"},
               {"key": "policy-1", "title": "Collection Policy", "kind": "policy", "pages": [15, 17], "anchor": "C", "foundBy": "running header", "tier": "suggested", "book": ""}],
     "sections": [{"number": "R-3", "kind": "rule", "letter": "a"}, {"number": "R-9", "kind": "unclear", "suggestion": "policy", "question": "q-0412"}]},
    {"key": "decl", "title": "Declaration", "kind": "declaration", "holdsRules": "restates", "readForGrants": true, "copies": [], "numbering": null}
  ],
  "run": {"state": "ran with the model too", "at": "2099-10-04", "readers": ["rules", "model"], "candidates": 82, "grants": 19, "limits": 15, "references": 18,
          "model": {"name": "example-model", "gpu": "free", "preflight": "ok"}},
  "toRead": {"conflicts": 5, "rulesNoGrant": 2, "ambiguousCitations": 3, "unclearSections": 1},
  "caveats": ["A grant is a reading, never a rule. No grant found is not no authority."]
}
```

`GET /api/rule-subjects` (proposed; `tasks.rule_authority.subjects`, `reach`), one subject with a grant, no rule, and the reading under 4355(a):

```json
{
  "found": true, "asOf": "2099-10-05", "readers": ["rules", "model"],
  "subjects": [
    {"subject": "pets", "standing": "authority named, no rules on file",
     "grants": [{"id": "ra-0007", "source": "bylaws", "section": "7.8", "citation": "bylaws#7.8", "title": "Powers of the board",
                 "answer": "yes", "holder": "board", "subjects": ["pets", "noise"], "otherSubjects": [],
                 "tier": "likely", "readers": ["rules", "model"], "consistency": "3 of 3", "part": "",
                 "recital": {"words": "[the section's words, as stored]", "operative": "[the operative words, verbatim]", "version": "in force 2099-10-05",
                             "caveat": "jason's consolidated text, not an official restatement. The recorded instrument governs.", "verified": true},
                 "conditions": [{"kind": "notice", "quote": "[verbatim]", "elsewhere": false}], "procedure": "[verbatim]",
                 "related": ["ra-0011"], "review": {"state": "unreviewed", "by": "", "on": "", "note": ""}}],
     "general": [{"id": "ra-0002", "citation": "decl#4.1", "tier": "suggested", "readers": ["rules"]}],
     "inGuidance": [{"id": "ra-0030", "citation": "rules-manual#guide.2", "part": "guidance"}],
     "rules": [], "restrictions": [],
     "reading": {"reach": "depends", "cites": ["CIV 4355(a)", "CIV 4355(b)"],
                 "note": "turns on whether the rule governs the common area or a separate interest; two readings remain"},
     "lead": {"kind": "canvas", "line": "authority named, no rule on file", "boardItem": null, "route": ""}}
  ],
  "conflicts": [{"id": "ra-0019", "citation": "bylaws#9.2", "tier": "conflict", "foundBy": "model", "otherReader": "rules said: refers"}],
  "caveats": ["A reading, never a rule row. 'No grant found' is not 'no authority': the power may be in the law, in a document not read, or in words the collector does not look for."]
}
```

`GET /api/rule-citations?text=minutes-2099-09&citing=minutes&on=2099-09-19` (proposed; `cite_scope.read_text`), one ambiguous citation and one picked:

```json
{
  "found": true, "citing": "minutes", "on": "2099-09-19",
  "counts": {"resolved": 41, "ambiguous": 1, "twice": 0, "unknown": 1, "notOnShelf": 0, "picked": 1},
  "citations": [
    {"id": "c-0007", "expression": "Section 7.3", "sentence": "[the sentence the citation is written in]", "form": "bare section",
     "found": false, "reason": "ambiguous_document",
     "scope": {"standing": "ambiguous", "form": "bare section", "number": "7.3",
               "candidates": [{"document": "bylaws", "has": true, "citedAs": "Bylaws Section 7.3",
                               "recital": {"words": "[bylaws 7.3, as stored]", "version": "in force 2099-09-19"}},
                              {"document": "decl", "has": true, "citedAs": "Declaration Section 7.3",
                               "recital": {"words": "[decl 7.3, as stored]", "version": "in force 2099-09-19"}}],
               "leads": ["decl"], "note": "more than one document has 7.3"},
     "pick": null, "choices": {"options": ["bylaws", "decl", "neither"], "preselected": null}},
    {"id": "c-0009", "expression": "R-3(e)", "found": true,
     "scope": {"standing": "scoped", "form": "bare rule", "document": "rules-manual", "basis": "form", "part": "rules.parking"},
     "pick": null},
    {"id": "c-0012", "expression": "Section 4.15", "found": false, "reason": "ambiguous_document",
     "scope": {"standing": "ambiguous", "candidates": [{"document": "bylaws", "has": true}, {"document": "decl", "has": true}]},
     "pick": {"document": "decl", "by": "Jane Example", "on": "2099-10-05", "why": "the minute is about assessments", "stale": false}}
  ],
  "caveats": ["A reading is never a recitation: what jason recites is the stored words of the section it found. A citation the grammar does not read stays unread."]
}
```

`GET /api/cite?q=owner_responses.RULES: delivery` (the `cite` loader of [screens/governing-documents.md](screens/governing-documents.md); `kind: row`):

```json
{"kind": "row", "found": true, "citation": "owner_responses.RULES: delivery", "title": "Response rule: delivery",
 "table": "owner_responses.RULES", "key": "delivery", "text": "[the row's own words]", "action": "[the action it gives]",
 "condition": {"function": "example_condition", "where": "example/module.py:12", "source": "[the function's source]"},
 "adoption": null, "adoptionNote": "no adoption named",
 "caveat": "jason's own rule row, a decision kept as data: not a rule of the association. The association's rules are its governing documents; a row that rests on a board decision names the board item."}
```

`GET /api/rule-change-handoff?subject=pets` (proposed; `reach`, `jason rule-change --list`): `{"subject": "pets", "reach": "depends", "cites": ["CIV 4355(a)"], "readings": ["a use of the common area", "a use of a separate interest"], "askCounsel": true, "changes": [], "command": "jason rule-change --list", "routes": {"changes": "#/rules", "notices": "#/notices?catalog=rule-change"}}`. The statute's own words are fetched by the `cite` loader, never held in this payload.

## What the design must keep

- **Recite the document's words first, label the reading** (principle 2). Every grant, every limit, every candidate, and every rule on file shows the document's stored words, with their citation and version, before the readers' reading, which sits under a `ReadingLabel` that names whose it is. The `Recitation` holds no reading. "The board holds it" and "its subjects" are the reader's.
- **A reading by one reader is a lead** (principle 3). The tier is stated in words naming the readers; the model's answer alone is "one reader: the model", a suggestion held for a person. No bare percent or confidence is shown; the model's other samples are a count with the caption "a filter, not a second reader".
- **jason proposes; the board adopts** (principle 5). No control on this page adopts, approves, or makes a rule. A review is a person's record about a reading; the canvas act is a proposal for the agenda. The vote is recorded where every vote is.
- **A subject with a grant and no rule is a lead, not a finding of fault.** Never "gap", "violation", "unauthorized", or "invalid"; never a red state; never "a rule is needed". It goes to the canvas as a proposal that a written policy is available where the law is silent. "Rules on file, no grant found" is a question for the board and counsel.
- **A miss stays a miss** (principle 8). No grant found, no outline, no section, an unknown document, a part whose book the canon does not name, a section with no number: each is shown as that, with its command, never an empty row and never a zero count that means "not read".
- **A missing fact is a question.** An unclear section, an unknown document, an ambiguous citation, and a subject with no reading under 4355 are questions a named person answers, not defaults.
- **Never a guess between documents** (rule-citations: "no pick between two documents that both have the section"). Both candidates shown, none preselected, no "most likely", no "first". A pick is a person's, with their name and day; it applies to that one citation and goes stale when either document's words change.
- **jason's own rows are labeled and apart.** Never counted with the association's rules, never recited as a rule, never "adopted" unless a board item is named.
- **The rule-change path is a hand-off.** It shows the reading, the `Command`, and the links; it builds no notice and drafts none.
- **Every write is a `Confirm` in a named person's name, through the write guard, with its CLI equivalent named.** The writes are four: run the reading (`jason rules --find`), review a grant (`jason rules --review ID --status S --note TEXT --by NAME`), record a citation pick (`jason cite --pick ...`, proposed), and put a subject on the board's canvas (`jason rules --to-board SUBJECT --by NAME`, proposed). Each is behind `X-Jason-Token` with `by` (400 without; 401 with no one signed in), and a refusal says "Nothing was written."
- **Nothing is worked out on the client.** The tier, the standing, the 4355 reading, the scope and its basis, the round trip, and the stale marks all come from a loader.
- **Confidential matters stay out.** The collector reads the governing documents and the board's published rules, never a resolution or counsel's letter; an executive-session or counsel's document is by kind only outside the private view. A grant a reader found in such a document is not shown. An owner's name never appears on this screen.
- **No color-only meaning.** Every word above is text; a count is text beside any bar; a conflict-tier row is marked by its word first.

**Privacy by level** (principle 6):

| What | Level | Shown |
| --- | --- | --- |
| the statutes, and the recited words of a recorded or adopted governing document | P0 | always on the board's screens |
| the readers' readings, tiers, reviews and notes, and the leads | P1 (jason's working reading) | the board's screens; **not the owner view** |
| a person's pick, review, and canvas act: who, when, why | P1 | roster people |
| the screen's counts of conflicts and subjects with no grant found | P1 | the board's screens |
| a counsel's letter, an executive-session document, a held matter | P3 | by kind only outside the private view; never collected for grants |
| a secret | P4 | never |

The screen is board-only (`owner: false`). Whether an owner view shows the rules on file with their citations, without the grants and the leads, is its own decision (decision 5).

## Where it goes

Routes are proposed, consistent with [information-architecture.md](information-architecture.md#where-the-proposed-screens-go); none exists yet.

- **Records → Governing documents → Rules and authority** (proposed): **`#/documents/rules`**, a route under `#/documents` ([screens/governing-documents.md](screens/governing-documents.md)), board-only. The Governing documents screen is where a section is recited and cited (the cite box, `Recitation`, the readings band), and every band here recites; so the rules screen is a sibling band of it, not a band on the page that shows one section. It is not `#/rules`, which is the built **Rule changes** screen (stages of a proposed change): that screen is where the hand-off ends, and this page links it. Bands in order, as `Tabs`: **Documents** (`RulesIntake`, `RuleDocumentRow`, `PartsStrip`, `NumberingLine`, `RuleReadRun`), **Authority** (`AuthorityMap`), **Citations** (`RuleCitations`), **jason's rows** (`OwnRuleRow`). Query: `?subject=` (a `Subject` word), `?tier=likely|suggested|conflict`, `?document=KEY`, `?state=` (a standing word), `?citation=ID`, `?row=TABLE:KEY` (a table and key, never a name), `?as_of=YYYY-MM-DD`. The header's `Command` is `jason rules` (`--subjects`, `--all`, `--tier`).
- **The onboarding session** ([screens/onboarding.md](screens/onboarding.md)): `RulesIntake` is a task of the session, in the order after "the outlines are read"; each of its five steps links its band in `#/documents/rules`. The unclear section and the unknown document are `next_questions`, so one answer path serves both.
- **Governing documents** (`#/documents?q=`): a section whose words are a grant shows "a grant of the power to make rules on pets (both readers agree; not reviewed)" in its readings band, linking `#/documents/rules?subject=pets`; the section's page lists the rules that cite it, each with its scope basis. The cite box takes `citing` and `citing_day` so an ambiguous answer opens `AmbiguousChoice` in place.
- **Programs** ([handoff-programs.md](handoff-programs.md)): a program row whose instrument is an operating rule takes its authority element from the stored grants and links the subject here; its `adoption-formalities` check ("within the authority of the board", 4350(b)) reads the same rows. This page owns the authority and the citations; that page owns the adoption.
- **Rule changes** (`#/rules`, built; `jason rule-change`): the end of the `RuleChangeHandoff`.
- **The board's canvases and agenda** ([screens/board-items.md](screens/board-items.md), `#/canvases`, `#/actions`, `#/agenda`): where a canvas lead lands and where the board decides.
- **The confirmations queue** ([handoff-confirmations-queue.md](handoff-confirmations-queue.md)): a question of what words *mean* (whether a rule "governs the common area") is a candidate reading there; this page sends it and does not answer it.
- **The day control** ([handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md)): `?as_of=` reads every recited document in its version of that day; the stored readings, the reviews, and the picks are the record's and do not move.

**When a loader cannot answer** (principle 8). Each band is its own `RemoteView`. No authority file on disk: the Authority band says "No rule pass has run" with `jason rules --find` and a `Confirm` to run it, and every count is "not read", never zero. No outline for a document: that document's row says so with `jason outlines KEY`. The shelf lacking a statute: the 4355 recital says "not on file" with `jason cite "CIV 4355"`, and each subject's reading still shows. A date refused: the tool's own words, and the page keeps today. The model reader unavailable (no preflight, the GPU lock held): the run is offered with the rules alone, and the card says the model did not read.

**Loaders to add** (names only; nothing built; each wraps a function that exists today and derives nothing):

| Loader | Route | Wraps | Notes |
| --- | --- | --- | --- |
| `rules-intake` | `GET /api/rules-intake` | `tasks.rule_authority.outlines_of`, `manual_parts`, `tasks.segments.parts_in_store`, `community.manual`, the stored authority file, the outline round trip | one payload per step; a failing step carries its note |
| `rule-authority` | `GET /api/rule-authority?tier=&document=&all=` | the stored `RuleAuthority` rows, `authority_lines` | the grants by document; `all` adds limits and references |
| `rule-subjects` | `GET /api/rule-subjects?subject=&state=&as_of=` | `tasks.rule_authority.subjects`, `rule_authority.by_subject`, `reach` | each subject's standing, grants, general powers, rules on file, restrictions, and the 4355 reading; the recitals through `cite_document` |
| `rule-citations` | `GET /api/rule-citations?text=&citing=&on=` | `cite_scope.read_text`, `scoping.scope` | the citations of one text with each `Scoped`, and the picks on record |
| `rule-change-handoff` | `GET /api/rule-change-handoff?subject=` | `rule_authority.reach`, the specification's proposed changes | a hand-off only; the existing `rule-changes` loader serves `#/rules` |
| `cite` (proposed on the governing-documents page) | `GET /api/cite?q=&in=&on=&as_of=` | `jason.api.cite_document` | the recitals, scope, and `kind: row` |
| `rules` (writer, **CLI built**) | `POST /api/write/rules/review` `{id, status, note, by}` | `jason rules --review` | confirmed, corrected, rejected; a review of a reading whose words changed is kept "orphaned" |
| `rules` (writer, proposed) | `POST /api/write/rules/find` `{model, by}` | `jason rules --find [--model]` as a job | rules alone; the model holds the GPU lock after preflight; the job's log is `JobStatus`'s |
| `rules` (writer, proposed) | `POST /api/write/rules/citation-pick` `{citation, citing, day, document, why, by}` | a store `data/rules/citation-picks.json` under the store lock, keyed by the citing text, the span, and both documents' digests | the pick; a pick whose digest no longer matches is stale |
| `rules` (writer, proposed) | `POST /api/write/rules/to-board` `{subject, by}` | `tasks.board_items.propose` with the grant's words and the reading as evidence | makes a board item and nothing else; CLI `jason rules --to-board SUBJECT --by NAME` |

Every writer is behind the write guard (`X-Jason-Token`, origin, fetch metadata), takes `by`, refuses a secret, and answers 401 with no one signed in.

## Accessibility

As [components.md](components.md#accessibility) and [content/patterns.md](content/patterns.md#accessibility-wcag-22-aa):

- **Keyboard.** A subject card opens by a `button` with `aria-expanded`; Escape closes it and returns focus. `AmbiguousChoice` is a `fieldset` whose legend is the citation as written; the choices are radio buttons labeled with the document's name, none checked, the two recitals before them in DOM order, and the `Confirm` disabled by `aria-disabled` until one is chosen, described by the reason. The review's status is a radio group; the note is a labeled text field. The tabs follow the tabs pattern with arrow keys. A tier word, a standing word, and a basis word are text in a `Pill`, never an icon alone.
- **Screen reader.** A `Recitation` is a `figure` with `blockquote` and `figcaption` (the citation and version). The readers' reading is a separate region labeled "the readers' reading, not the document's words". Two candidates are a list of two items, each naming its document. A `picked` citation reads "picked by Jane Example, Oct 5, 2099". The result of a recorded pick or review is `role="status"`; a refusal is `role="alert"` tied to the field by `aria-describedby`.
- **Quotations on a phone are never truncated** (see below), so no recital is read from an ellipsis.
- **Target size (2.5.8)**, **redundant entry (3.3.7)** (the name from "Signed in as"; only a second person's field starts empty), **timing (2.2.1)** (nothing times out; a half-written note stays across a band change), **use of color (1.4.1)** (every state is a word first; the glyph for a conflict is two marks, for an ambiguous citation a question mark, never a warning triangle).

### The phone layout (under 720 px)

The words that matter stay on the page.

- The tabs become a `select` whose options carry the counts in text ("Authority (5 conflicts, 2 with no grant found)", "Citations (3 ambiguous)"), so the band that needs a person is not hidden by the control.
- The intake's five steps stack as a numbered list with each step's state word in full; a step's detail opens in place.
- A subject card is one column in the order of "The authority map": the standing word with its full text, the recital in full under it (a quotation is never cut to an ellipsis), then the reading. The reading's rows wrap, never scroll sideways.
- `AmbiguousChoice` stacks its candidates one over the other, each headed by "as it would be cited"; the radio group follows; the `Confirm` is at the end of the form and not sticky (2.4.11), with the consequence in text directly above it.
- A table becomes a list: the citation, then its basis word in full, then the document.
- The rows from jason's own tables are under their own heading with the label first. Nothing scrolls sideways at 320 px.

## Decisions for the design

**Settled by the axioms in this pass.**

- **The authority map shows a grant and no rule as a lead, never a fault.** AGENTS.md ("Where the law is silent, write it down"; "jason proposes; the board adopts"). A rule is valid only if it is within the board's authority (Civil Code 4350(b)); the board's own written policy is the board's act.
- **The recited words come before any reading.** "Recite the rule; label the reading". A tier names the readers and is never a percent.
- **No guess between documents.** The rule-citations page: "No pick between two documents that both have the section." A pick is a person's, recorded, local to one citation.
- **jason's own rows are apart and labeled.** The loader's caveat, verbatim.
- **The rule-change path is a hand-off.** `jason rule-change` and `#/rules` own it.
- **The screen is a route under Governing documents, not `#/rules`.** `#/rules` is the built Rule changes screen; this page is where the grants and citations that a change rests on are read.

**Still open, and a person's to settle.**

1. **Where the weekly check lives.** `#/documents/rules` as a route under Governing documents, versus only the Documents band joining the onboarding session and the Authority band joining the board's canvas. The loaders are the same either way. Test with the manager and the secretary.
2. **Who may review a grant, and whether a second person confirms a conflict-tier grant.** `jason rules --review` takes `by` only. A grant a model alone read is a suggestion; whether a reviewer must be an officer, and whether a `conflict` row's review waits on a second person (`SecondConfirm`), is the board's call.
3. **A pick inside an adopted rule's own words.** A citation in a rule the board adopted ("see section 7.3") keeps its adopted words; a pick records the reader's understanding. Whether a pick on such a citation needs a second person, and whether it should instead go to counsel and the board as a question of what the rule means (a reading, in the confirmations queue), is the board's and counsel's. Until decided, the pick is local and labeled.
4. **Where a pick is stored.** `data/rules/citation-picks.json` (jason only), or a register the board keeps up to date ([../registers.md](../registers.md)), which AGENTS.md prefers for facts the board maintains. A pick is neither the specification nor a rule row.
5. **Whether an owner view shows rules on file with citations.** The owner may read the adopted rules; whether the console should show them by subject with their citations and no grants or leads is its own decision.
6. **The word for a general power.** "General power" is the code's term (`general_only`); the board may find a plainer label in test. The recited words must stay beside it.
7. **A gold set to show the readers' precision.** The page shows no precision or recall: the measurements are one association's private gold set and one reader's labels ([../rule-authority.md](../rule-authority.md#measurements-october-5-2026)). Whether a general sentence about how often a tier was right belongs on screen waits on a second association's set.

## Not part of this pass

- Any control that adopts, approves, or makes a rule, and the draft of a rule's text. A written policy's draft and its way to the board are the programs handoff's `ProposalFlow`.
- The member notice, its draft email, and its clock: `jason rule-change` and `#/rules`.
- Reading the adoption act of a rule ([handoff-programs.md](handoff-programs.md)).
- The collector's vocabulary, the second gold set, and the model's prompts ([../rule-authority.md](../rule-authority.md#not-done-yet)).
- Parts from segmentation replacing `parts_from_manual`: the loader reads whichever the code serves; the design shows a part either way.
- Editing the specification, a rule row, or the outlines from the console; `jason outlines`, `jason cite --migrate-ids`, and `jason intake --apply` stay terminal commands.
- An owner-facing version of any band (decision 5).
- The previews: the design project's authored preview for each component follows the build; fixtures will be `ui/src/components/authoritymap.test.tsx` and its siblings, from the sample data above.
