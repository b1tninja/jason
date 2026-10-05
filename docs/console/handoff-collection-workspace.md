# Handoff: the collection workspace

For the design pass on **one set of documents read together**: a legal case's file, and later a vendor's file, a system's inspection records, or a meeting's packet. The workspace shows the collection's summary, its chronology, the law its documents cite, what is missing or unread, the open questions, and the reviews kept under a lens. The data exists today, with no screen:

- `jason collection KEY [--as-of DAY] [--write] [--json]` (`jason.tasks.collection_pages`) builds the summary from the stores: what the collection is, the specification's record of the matter, the files and how each was read, what is missing or unread, "Citations of the law", the open questions, the conflicts of fact, and the chronology ([../collections.md](../collections.md#the-summary-page)).
- `jason.community.document_collections` holds the record (`Collection`: a key, a title, a kind, an index `Scope`, the context lines, the label, the confidentiality, the folder). Two kinds are built, `legal case` and `ad hoc`; a vendor's file, a meeting's packet, and a building system's records are named in the code as kinds to come.
- `jason.tasks.case_files` keeps a case's folder: `inventory` (each file and what became of it), `extract_text` (a text extract beside each PDF, with how it was read), and the files the case's rule holds back, counted and never named.
- `jason.community.chronology` and `jason.community.fact_conflicts` are the two rule-based lenses the summary is made of; `jason.community.law_citations` resolves each cited statute to the law in force on a day ("cites former X, now Y").
- `jason.community.reviews` with `jason.tasks.document_reviews` keep the lens reviews of documents (`as-of`, `records`), each finding with its `basis`; `jason.tasks.review_store` keeps the manager reviews made with a collection (`jason review TASK --collection KEY --as-of DAY`).
- The read-only MCP tools `legal_cases`, `case_file`, and `evidence` read the same stores ([../mcp.md](../mcp.md)).

Why the layers are kept apart (ingestion and review; facts, law, application; the administrative law judge's proposed decision) is settled in [../ingestion-and-review.md](../ingestion-and-review.md#three-questions-as-the-law-separates-them). The console has `#/legal` (open statutory duties per matter) and `#/ingestion` (how the library was classified), and nothing that shows a collection.

The format follows [handoff-applicability-questions.md](handoff-applicability-questions.md) and [handoff-confirmations-queue.md](handoff-confirmations-queue.md). The neighbours this page links to and does not repeat: [documents.md](documents.md) (one viewer for every document, its copies and levels), [doc-component.md](doc-component.md) (`Doc` and the `DocRef` a loader returns, with every state a reference can be in), [screens/records-and-library.md](screens/records-and-library.md) (library search, an ingest, a document's revisions), and [screens/board-items.md](screens/board-items.md) (the board's items, held executive rows, and their evidence). Written in the same wave, named here and not linked: `handoff-context-pack-workbench.md` (a pack and a review under it), `handoff-as-of-and-quote-check.md` (the day control, the version in force, quote verdicts, former sections), and, from another session, `handoff-citations.md` (`CitationChip`, `Successor`, `StandingPill`).

These components pair with what the console already has: `Recitation` and `ReadingLabel`, `Doc` and `DocList`, `Pill`, `DataTable`, `Card`, `Tabs`, `Timeline`, `Findings`, `Caveats`, `Command`, `Confirm`, `Stat`, `EmptyState`, `RemoteView`, and the built private view. They reuse `Discrepancy` as [handoff-applicability-questions.md](handoff-applicability-questions.md#the-components) proposes it. Build new parts only where the table says so.

## The idea in one line

A collection is **a scope and a context**: whatever the index holds under its scope today, read together, with every statement tied to the file and passage it rests on, every gap named with the command that fills it, every disagreement shown with both sources and neither picked, every citation resolved to the law of the day asked with both versions recited where held, and every open question left for a person, who may take it to the board's agenda; the workspace edits no document and decides nothing.

## The components

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `CollectionList` | Records → Collections (`#/collections`) | `GET /api/collections` | none set (the specification sets no case with a case file: the note and `jason cases`); no passage index (the command); listed, each with kind, files and passages held, level; a held row outside the private view (kind and level only, no title or key); a proposed kind not built |
| `WorkspaceHeader` | top of `#/collections/<key>` | the loader's `header` | kind, key, title; who may see it in words; the data level; the as-of day (the day control) or "the shelf now"; last built (the index, the folder's fetch, the newest extract, the page on disk), each with its date or "never"; the `Command`; the state banner under it |
| `CollectionStateBanner` | first under the header | `states[]` | not built; stale (what changed, since when, the command); partial (files with no text, pages unread, may misread); held back by the collection's rule (a count); confidential (outside the private view); executive-session material; several at once, in that order |
| `SummaryBand` (a `Card` preset) | each band of the Summary tab | one section of the summary with `readFrom` and its `gaps` | the band's content; "Read from:" its stores in words; its gaps, each a `GapLine`; nothing found ("None was found by rule." with the caveat that it is not a finding); the store missing (the note and command) |
| `MatterRecord` | the Summary tab's context band | `context`, `recorded[]`, `duties[]` | a legal case's record (forum, role, status; its events; its duties with each standing in words); an ad hoc collection's lines ("given with the collection; none is a quote from a file"); no record ("The specification records no event for the matter.") |
| `GapLine` | inside each band; all of them in What is missing | one `missing[]` row | each gap key below, with its count and the command that fills it; a held-back count that names nothing |
| `FileInventory` | the Files tab | `files[]`, `heldBack` | the read-state words below; a file known only to the index; a file the index does not hold; held back (one line, a count); folder not fetched; no files |
| `ReadState` (a `Pill` preset) | a file row; a statement's place; a conflict side | a file's `state`, `howRead`, `pagesUnread`, `mayMisread` | each word in "Read state" below, the "how" beside it in text |
| `ChronologyLanes` | the Chronology tab | `chronology.events[]`, `chronology.recorded[]` | the documents' own dates; dates at a head, in a header, or in a file's name; dates the documents speak about; the specification's record in a lane of its own; a range; "on or about"; a month with no day; near copies folded ("also in"); none read in a group; a filter by date span |
| `StatementRow` | inside `ChronologyLanes` | one `Event` with its `doc` | the date as written beside the date read; the role and rule in words; the document's words as a quote (cut marked by an ellipsis); the place as a `Doc` chip with passage and word; the document's own date beside an "about" date; held back (named by kind only) |
| `FactConflictCard` | the Chronology tab under a statement it touches; the Summary's conflicts band | one `FactConflict` | two sides; three or more sides; a side given by several documents; a stored field with no quote ("the text does not print it in a form the rule knows"); the `show` fields that tell the documents apart; a side from a held-back file; its open question and where it went |
| `CitationRow` | the Citations tab | one `citations[]` use | each resolution word below; cited by (each document and passage as a `Doc` chip); the sentence it sits in; the `Recitation`s it opens; the gap it raises |
| `FormerAndNow` | inside a former `CitationRow` | `former`, `formerAsOf`, `words[]` | both held (two `Recitation`s side by side); the former's words not held (the successor only, and the gap); several successors; the day asked before the renumbering (one `Recitation`, "the words then in force"); not shown to be in force on the day |
| `ReviewList` | the Reviews tab | `GET /api/collection-reviews` | manager reviews kept with this collection (task, as-of, digest, sources, answer verified or not, or pack only); lens reviews of its member documents by lens and day; none kept (the commands); none possible (no member has a stored reading); a confidential review outside the private view |
| `ReviewRecord` | one review opened | `GET /api/collection-review` | a manager review's sources by tier with each law source's in-force line and its readings' states, its gaps, its runs; a lens review's findings by check, each a `FindingRow`; reused (stood from the store) or made again; the lens's version |
| `FindingRow` | inside `ReviewRecord` and `LensCompare` | one `Finding` | its severity word, message, authority (a `CitationChip`), lens and check, and its basis in words; a finding from the text alone (labeled "ingestion: from the text alone") |
| `LensCompare` | two reviews of one document side by side | `GET /api/collection-compare` | two lenses on one day; one lens on two days; two manager reviews of one question on two days; only in A, only in B, in both; a review missing on one side (the command that makes it) |
| `OpenQuestionRow` | the Questions tab; the Summary's questions band | one `openQuestions[]` row | each question rule below; already raised (the board item and its status); raised to counsel (the item, its ask); none ("None was found by rule.") |
| `RaiseQuestion` (a `Confirm` preset) | under an `OpenQuestionRow` | the question, the person from "Signed in as" | for the board's agenda; for counsel, through the board; refused (no one signed in; a question already raised; writes off: the `Command`) |
| `ExtractTextAction` (a `Confirm` preset) | the Files tab's header; a file row in "not read yet" or "partly read" | the case's key, the files it would read | queue the local read; queue the vision read (GPU lane, preflight first); a job already queued or running (`JobStatus`); writes off (the `Command`) |

## The vocabulary

Every state is a word from the code, so the console and the terminal agree, and no state is conveyed by color alone.

**Read state** (`case_files.FileState` with the extract's `ReadMethod`; the loader sends the word):

| Word | From | What the row shows beside it |
| --- | --- | --- |
| read as fetched | `text` | a transcript or a text file, read as it is |
| read: text layer | `extracted`, `text layer` | the PDF's own words |
| read: text layer, scanned pages by OCR | `extracted`, `text layer` with scanned pages read | "N of M pages read by OCR: ENGINE, which may misread" |
| read by OCR, may misread | `extracted`, `ocr` | the engine; "check a quote against the file" |
| read by a vision model, may misread | `extracted`, `vision` | the model; the same line |
| read: the file's own words | `extracted`, `document` | a Word file or a table |
| partly read | an extract with `unreadPages` | "N of M pages are images no reader gave words for" |
| not read yet | `no extract` | "no text extract yet", with `ExtractTextAction` |
| unreadable | `unreadable` | the reader's reason ("image-only; no OCR engine is installed") |
| not taken | `listed` | what it is ("a shortcut to a file kept elsewhere", "a .m4a file the fetch does not take") |
| not on disk | `not on disk` | "listed to fetch and not on disk", with the fetch command |
| fetch failed | `failed` | the fetch's error |
| held back | the case's `held_back` rule | one line, a count; never a row, a name, or an extract |

**The kind of date** (`chronology.DateRole`, in `ROLE_WORDS`' own words): the document's own date; a date in a line at the document's head (often its own date; a scheduled time reads the same); a message header's date inside the document; a date in the file's name, not in its words; a date the text speaks about. "On or about", "a month with no day", and "a range" are marks beside the date.

**How a citation resolved** (`law_citations.Resolution`, with the summary page's labels):

| Word | `resolution` | Shown |
| --- | --- | --- |
| on the shelf | `current` | the digest, the source, and how the day is known; the words open in a `Recitation`, not repeated on the row |
| former number | `former` | "cites former X, now Y", the table's source and succession, the act and its operative day; `FormerAndNow` |
| the number then in force | `then_current` | the day asked is before the renumbering; the words of that day, where held |
| open | `unresolved` | "an open finding, and no successor is guessed"; it is also an open question |
| not on the shelf | `not_held` | what brings it down (`jason cite`) |

**A conflict's rule** (`fact_conflicts.Rule`, with `RULE_WORDS` verbatim on the card): stored-field, identifier-amount, identifier-date, dated-statement-amount.

**A finding's basis** (`document_models.Basis`): text, profile, store, today, law, each written out ("from the text and today's date"). Text alone is ingestion; anything more is a review. **Severity:** info, check, problem.

**A duty's standing** (`document_collections.duty_line`): "The record shows it met.", "The record shows it not met.", "The record does not show it either way.", "It does not apply: the statute's condition has not arisen."

**The collection's states:** not built, stale, partial, held back, confidential, executive session (below). **Who said it:** "a document says", "the specification's record", "jason's summary of the collection: a summary, not the record" (`SUMMARY_LABEL`), "a person's question". Never "found", "established", or "confirmed" for a document's statement.

## The header

`WorkspaceHeader` answers five questions before anything else:

1. **What it is.** The title, the kind word (`legal case`, `ad hoc`), the key, and the label in the code's words ("evidence gathered for this matter: neither the record nor the law").
2. **Who may see it.** In words, from the server: "Confidential: for directors and counsel. Shown in your private view." For an open collection: "Open to the roster." The data level beside it as text (P3, P1).
3. **The day.** The as-of day the citations and reviews were read against, from the day control (`?as_of=`), or "the shelf now (no day asked)". Changing it reads again; it writes nothing.
4. **Last built.** Each store the workspace reads, with its own date: the passage index's build of the collection's catalog, the folder's fetch (`fetchedAt`), the newest extract (`readAt`), and the summary page on disk ("Generated: by jason on …"), or "never". Never one invented date for all.
5. **The command.** `jason collection KEY --as-of DAY`, copyable.

## The summary as bands

The Summary tab is the page's sections as bands, in the page's order, each a `SummaryBand` with its source and its gaps. The loader computes it from the stores on each read (it reads only, in under a second on a case of twenty files); the page on disk is shown as a line in the header and is never the band's source.

| Band | Read from | Its gaps (the `missing[]` keys it shows) |
| --- | --- | --- |
| What this collection is | the `Collection` record | — |
| The specification's record of the matter (`MatterRecord`) | the `LegalCase` record, and nothing else | — ; a recorded event with no statement on its day is an open question |
| Sources: the collection's files | the passage index; the case's manifest and extracts | `not-fetched`, `no-text`, `not-indexed`, `pages-unread`, `may-misread`, `held-back` |
| What is missing or unread | all of the above, by rule | every key, in the page's fixed order |
| Citations of the law | `law_citations`, as of the day | `law-not-held`, `former-words-not-held`, `then-words-not-held` |
| Open questions | by rule | — |
| Conflicts of fact | `fact_conflicts` | `no-stored-reading`, `kinds-not-compared` |
| Chronology: what the documents say | `chronology` | `no-dated-statement`, `no-year` |

The counts (`counts`) sit in a `Stat` strip under the header with their table twin: files, with text, indexed, held back, pages unread, dated statements, conflicts, citations by resolution, gaps, open questions. A band's empty state is the code's own sentence: "Nothing is recorded as missing or unread. That is not a finding that the collection is complete." "No conflict was found by the rules. That is not a finding that the documents agree."

`MatterRecord` is labeled in the code's words: the specification's record, "confirmed by a person", "None is a quote from a file of the collection, and none is merged with what the documents say below." It never shares a lane, a list, or a sort with the documents' statements.

## The chronology, and two documents that disagree

`ChronologyLanes` shows three groups of the documents' statements (their own dates; dates at a head, in a header, or in a file's name; dates they speak about) and, apart, a lane for the specification's record. Each `StatementRow` reads as the code's `says()`: the document, then what it says, then its words. "letter-example.pdf, dated 2099-03-02 at its head, says: '…'", never "On 2099-03-02 the board …". The date as written ("3/2/99") is shown beside the date read, so a misread is visible. Each statement's place is a `Doc` chip (the file, passage, word) that opens the file as one logged view; "also in" lists the near copies as chips.

**A disagreement is two recited sources side by side** (`FactConflictCard`, built on `Discrepancy`). For each side: the value, then each document that gives it, with its `ReadState`, its place, the `show` fields that tell the documents apart (a draft flag, a printed date), and its words as a quote; a stored field's side says "Read from: the reader's stored reading" and, where the text does not print the value, says so and carries no quote. The rule's words (`RULE_WORDS`) head the card. The sides are equal columns; the card says "the order of the sides means nothing", and the loader's order is stable from run to run so it cannot read as a ranking. There is no "use this value", no "mark as resolved", and no note field: a conflict leaves the card only when the documents change. Its next step is its open question ("Which value holds for …? jason picks neither."), which a person may raise.

The caveats are under the lanes, verbatim (`chronology.CAVEATS`, `fact_conflicts.CAVEATS`): an event is a statement, not a finding; OCR can misread a date; no conflict listed is not a finding that the documents agree.

## The citations band

One `CitationRow` a cited statute, in the loader's order: open, former number, the number then in force, not on the shelf, on the shelf. Each row:

- **The resolution word**, then the note in the code's words ("cites former CIV 9803(g), now CIV 9901 (disposition table and commission comment: continued; renumbered to CIV 9900 to CIV 9999 by Stats. 2097, Ch. 1, operative 2098-01-01)").
- **Cited by**: each document and passage as a `Doc` chip, and the sentence the citation sits in, quoted as the document's words (a few, as the loader gives them).
- **Both recited, where held** (`FormerAndNow`). Left: the former section's own words, labeled "as last in force, to 2097-12-31" with its digest and source. Right: the successor's words "in force on 2099-10-05", or "NOT SHOWN to be in force on 2099-10-05 (the words on the shelf now)". Each is a `Recitation` fed from the loader's `words`, never from the page. A former section's words are never labeled as the law of the day asked.
- **Not held** says which and what brings it down; it is the gap's line, with the command (`jason law-history --add-version` for a former section's words, `jason cite` for a section not on the shelf).
- **Open** is an open question, linked to its `OpenQuestionRow`.

A current citation's words are not repeated on the row; its `CitationChip` opens the `Recitation`. A successor is the table's reading of the Commission's documents, labeled so; any reading of the words is a `ReadingLabel`, and the row carries none of its own. The as-of mechanics (the day control, the version in force, quote checks) are `handoff-as-of-and-quote-check.md`'s.

## The files

`FileInventory` is a `DataTable`: the file (a `Doc` chip), its kind, its standing, its `ReadState` with how, pages unread, and dated statements. A file the index holds that the folder does not account for is its own row; a file whose text the index does not hold says so. The held-back files are one line under the table: "Held back by the collection's rule: 2 files, not fetched or read. None is named on this page."

A person's acts on a file, and nothing more:

| Act | Does | Write? | CLI |
| --- | --- | --- | --- |
| Open | the file, or its text extract, through `Doc` as one logged view (`POST /api/evidence/view`; `file:cases/<key>/files/…`, P3) | no | — |
| Extract text | queues `cases --extract-text --case KEY` as a job on the local lane, behind `Confirm`: **Queue the text read of 3 files as Jane Example** | jason's own store (extracts and the manifest) | `jason cases --extract-text --case KEY` |
| Read scanned pages with the vision model | the same with `--vision`, on the GPU lane; the preflight runs first and fails fast | the same | `jason cases --extract-text --vision --case KEY` |
| Fetch the folder | a read of Drive: shown as the `Command`, or queued on the google lane (decision 3) | the same | `jason cases --fetch-files --case KEY` |
| Index the new text | queues `index --build` | the passage index | `jason index --build` |
| Write the summary page | `collection_pages.write` under the store lock, behind `Confirm`: **Write the summary page as Jane Example** | `data/collections/<key>/summary.md` | `jason collection KEY --write` |

The workspace **never edits a document**: no rename, re-kind, move, delete, or edit of a file or an extract. An extract is made again from its file, never corrected by hand; a correction belongs in the store it came from (the page's caveat, verbatim). Including a held-back file is a terminal step a person takes (`--include-held`), and its copy is never extracted or indexed; the workspace offers no control for it.

## Reviews under a lens

The Reviews tab lists what was kept, and opens one. Two kinds sit in one list, told apart in words:

- **Manager reviews made with this collection** (`review_store.history`, filtered by collection): the task, the as-of day (and whether a person named it), the digest's first sixteen characters, the number of sources and law sources, how many law sources were not shown in force, and the answer: "verified: 6 quotes found, 0 not found", "NOT verified", or "pack only". Opened, `ReviewRecord` lists the sources by tier with each law source's in-force line and its readings' states (current, stale, missing, misquoted), the pack's gaps, and each run. The pack itself is `handoff-context-pack-workbench.md`'s.
- **Lens reviews of the member documents** (`document_reviews.load` by lens and day, matched to the members by library id): the `as-of` and `records` lenses. Opened, `ReviewRecord` lists the findings by check, each a `FindingRow` with its basis in words, its severity, its authority, and whether the review stood from the store or was made again. A legal case's files have no stored reading (the document readers read the library), so the tab says "No member has a stored reading, so no lens has reviewed one" (the gap `no-stored-reading`), never an empty table.

**Facts, law, application.** A review is a proposed decision in three parts ([../ingestion-and-review.md](../ingestion-and-review.md#a-review)). The store does not yet keep a review's answer in three parts, so the design shows what is kept: findings grouped by basis by the loader, the law sources recited with their in-force line, and no application sentence of its own. The three-part form is decision 6.

**Compare two lenses** (`LensCompare`): two reviews of one document, side by side, with the key of each (lens, version, day, the digests of the fields and facts read). Findings are matched by check and code on the server: in both, only in A, only in B. The same shape compares one lens on two days ("a change is visible as a difference between two reviews") and two manager reviews of one question on two days (their sources and in-force lines). Nothing is merged and neither side is preferred. A review missing on one side shows the command that makes it (`jason models --as-of DAY --lens records`; `jason review TASK --collection KEY --as-of DAY`), and running either is a job behind `Confirm`, never on load.

## Open questions, and where they go

`OpenQuestionRow` shows a question in the code's words, with the rule that found it and the sources it names as `Doc` chips:

| Rule | The question asks |
| --- | --- |
| `duty-unshown` | whether a duty the specification records was met; the record does not show it either way |
| `recorded-unread` | which file records an event the specification records, since no statement of that day was read |
| `conflict` | which value holds, where two documents disagree |
| `former-unplaced` | what section, if any, now holds what a former number held |
| `no-own-date` | the date of a file whose head gave none (a heading or the file name is shown, and not taken for it) |
| `on-or-about` | on what day, where a document says "on or about" |

jason answers none. **A person may raise one** (`RaiseQuestion`), and it then goes the one way a question reaches the board: a board item through `tasks.board_items.propose`, signed. Two choices, each a `Confirm` in the signed-in person's name:

- **For the board's agenda**: "Propose this as a board item as Jane Example. The board decides at a meeting; this records only the question." The item's category follows the collection (legal for a case), its session follows `agenda_session` (an item on litigation goes to executive session), its evidence names the collection and the question's sources, and its ask is "decide".
- **For counsel, through the board**: the same item with the ask "decide whether to direct counsel to answer the question below". jason and the manager are not counsel; the console sends nothing to counsel. Drafting a letter from the item afterward is [handoff-draft-from-item.md](handoff-draft-from-item.md)'s.

After the act the row shows "Raised by Jane Example on Oct 5, 2099: board item BI-2099-07, proposed", and the item's status from then on is the board's, as [screens/board-items.md](screens/board-items.md) shows it. A question raised twice is refused with the first item named. No control answers, dismisses, or closes a question.

## States, and privacy by level

| State | When | The banner says | The way out |
| --- | --- | --- | --- |
| not built | no passage index; the folder never fetched; the case has no catalog yet | "Not built: the passage index holds nothing under this collection's scope." | the commands in order: fetch, extract, `jason index --build` |
| stale | a member file changed after its extract was read or the index cut it; the page on disk is older than the stores it lists | what changed, since when, and which files ("2 files changed since the index was built on Oct 3") | the command that reads it again; the bands still show, each marked with its build date |
| partial | files with no text, pages unread, files read by OCR or a vision model | the counts, in the gaps' words | `ExtractTextAction`; the vision read |
| held back | the case's rule holds files back | "2 files held back by the collection's rule: not fetched, not read, and not named. No count above includes them." | none in the console |
| confidential | the collection is P3 (every legal case's is) and the private view is closed | "Confidential: for directors and counsel. Open the private view to see it." | the built private view, for a stated reason, logged |
| executive session | a member is executive-session material (a meeting packet's executive item or minutes) | in an open collection, the member is counted and named by its Civil Code 4935 subject in general words, as a held board item is | the private view |

**Privacy by level** (principle 6; [security-and-privacy.md](security-and-privacy.md#data-levels)):

- **A collection is as confidential as its strictest member and its matter** (`Collection.confidential`; `cases/*` is P3). A legal case's collection is P3 whatever the board has disclosed of the case. The server decides the level; the client never infers it.
- **Outside the private view**, a P3 collection is a held row: its kind and level, "a legal matter (confidential)", and no title, key, file name, count of statements, or question. The route of a held row carries an opaque id, as an executive board item's does (decision 1). Inside, every answer is logged in `access/served.jsonl` with the view's id and reason, and a file opens as a logged view.
- **Who may open it**: those whose offices open P3 in the private view (manager, president, vice president, director, secretary). The treasurer alone and an admin with no office are refused with the reason. Counsel's grant of a matter's file is not built ([security-and-privacy.md](security-and-privacy.md#roles)).
- **What is shared.** Nothing leaves the workspace in this pass: no export, no copy to a canvas, no packet line, no email. The summary is "quoted to no one in place of the documents it lists". A confidential collection reaches only a board task's pack; for any other audience the pack holds nothing from it and says so in its gaps ("the collection is confidential; this task's audience is all members"). Executive-session material stays out of open recordings, transcripts, minutes, and the members' packet. The owner view shows no part of this screen.
- **Private facts** (a settlement figure, counsel's direct contact, a person's medical record) never reach a band: they are not in the stores the summary reads, and the held-back rule keeps the records it names off disk.

## Data shapes

Made-up samples only: "Example Village HOA", "Example v. Example Commons", case "24CV000123", files of plainly fake names, sections "CIV 9901" and "CIV 9803(g)", "Jane Example". Words of a statute are placeholders: on screen they come from the shelf through the loader, never from a sample. The keys of `summary` are `Summary.as_dict()`'s, key for key; keys marked "proposed" are the loader's additions.

`GET /api/collections` (proposed; `document_collections.collections` with `passage_index.count`, the shape of `jason review --collections`):

```json
{
  "found": true, "community": "Example Village HOA",
  "collections": [
    {"key": "24cv000123", "title": "Example v. Example Commons", "kind": "legal case", "confidential": true,
     "level": "P3", "files": 8, "passages": 212, "indexed": true, "route": "#/collections/24cv000123"},
    {"held": true, "ref": "held-1", "kind": "legal case", "level": "P3", "label": "a legal matter (confidential)"}
  ],
  "heldBack": 1,
  "heldNote": "1 collection is confidential: open the private view to see it.",
  "command": "jason review --collections"
}
```

`GET /api/collection?key=24cv000123&as_of=2099-10-05` (proposed; `collection_pages.summarize(community, data_dir, collection, as_of=).as_dict()`, with `header`, `states`, `doc` on each file and place, and `openQuestions` as rows):

```json
{
  "found": true,
  "header": {"key": "24cv000123", "title": "Example v. Example Commons", "kind": "legal case",
             "label": "evidence gathered for this matter: neither the record nor the law",
             "level": "P3", "seeWho": "Confidential: for directors and counsel. Shown in your private view.",
             "asOf": "2099-10-05",
             "built": {"index": "2099-10-03T06:00:00Z", "fetched": "2099-10-02T21:14:09Z",
                       "extracted": "2099-10-02T21:20:41Z", "page": "2099-09-30"},
             "command": "jason collection 24cv000123 --as-of 2099-10-05"},
  "states": [{"state": "stale", "text": "2 files changed since the index was built on Oct 3.", "command": "jason index --build"},
             {"state": "partial", "text": "1 file has no text; 3 of 12 pages of one file are images no reader gave words for."},
             {"state": "held back", "text": "2 files held back by the collection's rule: not fetched, not read, and not named."}],
  "summary": {
    "key": "24cv000123", "title": "Example v. Example Commons", "kind": "legal case",
    "generatedBy": "jason (rule-based; no model)", "standing": "a summary, not the record", "confidential": true,
    "scope": "catalogs case-24cv000123; confidential in case-24cv000123; not under collections",
    "label": "evidence gathered for this matter: neither the record nor the law", "asOf": "2099-10-05",
    "counts": {"files": 9, "filesWithText": 8, "filesIndexed": 8, "filesByHowRead": {"not read": 1, "text layer": 5, "OCR: example-ocr": 1, "text, as it was fetched": 2},
               "heldBack": 2, "pagesUnread": 3, "datedStatements": 41, "statementsByRole": {"document": 6, "heading": 2, "name": 2, "embedded": 3, "about": 28},
               "nearCopiesFolded": 4, "recordedEvents": 3, "duties": 1, "conflicts": 1, "citations": 3,
               "citationsByResolution": {"current": 1, "former": 1, "unresolved": 1}, "missing": 5, "openQuestions": 4},
    "context": {"title": "the specification's record of the matter",
                "lines": ["Matter: Example v. Example Commons", "Forum: superior court", "The association's role: defendant", "Status: open"]},
    "files": [
      {"file": "complaint.pdf", "kind": "", "standing": "evidence", "howRead": "text layer", "hasText": true, "indexed": true,
       "datedStatements": 9, "pages": 14, "pagesUnread": 0, "mayMisread": false, "confidential": true,
       "state": "extracted", "readWord": "read: text layer", "doc": {"address": "file:cases/24cv000123/files/complaint.pdf", "name": "complaint.pdf", "kind": "pdf", "level": "P3"}},
      {"file": "exhibit-b-photos.pdf", "kind": "", "standing": "evidence", "howRead": "text layer, scanned pages by OCR: example-ocr", "hasText": true, "indexed": true,
       "datedStatements": 1, "pages": 12, "pagesUnread": 3, "mayMisread": true, "confidential": true,
       "state": "extracted", "readWord": "partly read", "doc": {"address": "file:cases/24cv000123/files/exhibit-b-photos.pdf", "name": "exhibit-b-photos.pdf", "kind": "pdf", "level": "P3"}},
      {"file": "scan-0007.pdf", "kind": "", "standing": null, "howRead": "not read: image-only; no OCR engine is installed", "hasText": false, "indexed": false,
       "datedStatements": 0, "pages": 0, "pagesUnread": 0, "mayMisread": false, "confidential": false,
       "state": "unreadable", "readWord": "unreadable", "doc": {"address": "file:cases/24cv000123/files/scan-0007.pdf", "name": "scan-0007.pdf", "kind": "pdf", "level": "P3"}}
    ],
    "heldBack": 2,
    "missing": [
      {"key": "no-text", "count": 1, "text": "No text for 1 file (image-only; no OCR engine is installed): scan-0007.pdf."},
      {"key": "pages-unread", "count": 3, "text": "exhibit-b-photos.pdf: 3 of 12 pages are images no reader gave words for (photographs, or scans to read with a vision model)."},
      {"key": "held-back", "count": 2, "text": "Held back by the collection's rule: 2 files, not fetched, not read, and not named here. No count above includes them."},
      {"key": "no-stored-reading", "count": 1, "text": "No document reader's stored reading belongs to the collection's files, so the stored-field rule compared nothing. Only the text rules looked for conflicts."},
      {"key": "former-words-not-held", "count": 1, "text": "Cited by a former number whose own words jason does not hold, so only the successor is recited: CIV 9803(g). …"}
    ],
    "citations": [
      {"cited": "CIV 9810", "base": "CIV 9810", "subdivisions": "", "resolution": "unresolved", "asOf": "2099-10-05",
       "renumbered": "renumbered to CIV 9900 to CIV 9999 by Stats. 2097, Ch. 1, operative 2098-01-01", "successors": [],
       "succession": "not continued", "source": "", "open": true,
       "note": "cites former CIV 9810; the table says not continued: an open finding, and no successor is guessed",
       "former": null, "formerAsOf": null, "words": [],
       "citedBy": [{"document": "letter-from-counsel.pdf", "passage": 3}], "quotes": ["(the sentence the citation sits in, as the document gives it)"]},
      {"cited": "CIV 9803(g)", "base": "CIV 9803", "subdivisions": "(g)", "resolution": "former", "asOf": "2099-10-05",
       "renumbered": "renumbered to CIV 9900 to CIV 9999 by Stats. 2097, Ch. 1, operative 2098-01-01",
       "successors": ["CIV 9901"], "succession": "continued", "source": "disposition table and commission comment", "open": false,
       "note": "cites former CIV 9803(g), now CIV 9901 (disposition table and commission comment: continued; renumbered to CIV 9900 to CIV 9999 by Stats. 2097, Ch. 1, operative 2098-01-01); its own words not held; CIV 9901 recited",
       "former": {"citation": "CIV 9803", "found": false, "digest": "", "source": "", "decided": "", "basis": "", "reason": "no version of that day on disk", "words": ""},
       "formerAsOf": "2097-12-31",
       "words": [{"citation": "CIV 9901", "found": true, "digest": "9f8e7d6c5b4a3210", "source": "authorities/CIV/CIV-9900-9999.md",
                  "decided": "current", "basis": "the 2098 publication", "reason": "", "words": "(the section's words, recited from the shelf)"}],
       "citedBy": [{"document": "complaint.pdf", "passage": 2}, {"document": "answer.pdf", "passage": 5}], "quotes": ["…"]}
    ],
    "openQuestions": [
      {"id": "q-3f2a1c", "rule": "conflict", "text": "Which value holds for Invoice 1042: total? The documents give 2 values (conflict 1 below), and jason picks neither.",
       "sources": ["file:cases/24cv000123/files/invoice-1042.pdf", "file:cases/24cv000123/files/demand-letter.pdf"], "raised": null},
      {"id": "q-9b7e44", "rule": "recorded-unread", "text": "The specification records \"Mediation held\" on 2099-05-14 (it names its record as: counsel's letter). No statement dated that day was read in the collection's files. Which file records it, and can its date be read?",
       "sources": [], "raised": {"by": "Jane Example", "at": "2099-10-05", "to": "board", "item": "BI-2099-07", "status": "proposed"}}
    ],
    "conflicts": {"counts": {"conflicts": 1, "byRule": {"identifier-amount": 1}, "storedReadings": 0, "subjectsCompared": 0, "kindsNotCompared": []},
                  "conflicts": [{"rule": "identifier-amount", "ruleSays": "two documents each state one amount, under the same word, for the same labeled identifier, and the amounts differ",
                                 "subject": "Invoice 1042", "what": "total", "confidential": true,
                                 "sides": [{"value": "$1,250.00", "statements": [{"value": "$1,250.00", "quote": "Invoice 1042 … total $1,250.00", "basis": "the document's words", "file": "invoice-1042.pdf", "passage": 1, "word": 40, "standing": "evidence", "doc": {"address": "file:cases/24cv000123/files/invoice-1042.pdf", "name": "invoice-1042.pdf", "kind": "pdf", "level": "P3"}}]},
                                           {"value": "$1,520.00", "statements": [{"value": "$1,520.00", "quote": "… Invoice 1042, a total of $1,520.00 …", "basis": "the document's words", "file": "demand-letter.pdf", "passage": 2, "word": 118, "standing": "evidence", "doc": {"address": "file:cases/24cv000123/files/demand-letter.pdf", "name": "demand-letter.pdf", "kind": "pdf", "level": "P3"}}]}]}]},
    "chronology": {"counts": {"events": 41, "files": 8, "filesWithEvents": 7, "from": "2098-11-02", "to": "2099-09-20", "folded": 4, "recorded": 3, "datesWithNoYear": 6},
                   "events": [{"date": "2099-03-02", "end": null, "written": "March 2, 2099", "precision": "day", "approximate": false,
                               "role": "document", "rule": "label-line", "label": "Hearing Date", "quote": "Hearing Date: March 2, 2099",
                               "cutBefore": false, "cutAfter": false, "documentDate": "2099-03-02",
                               "file": "notice-of-hearing.pdf", "context": "notice-of-hearing.pdf: text layer", "section": "", "passage": 0, "word": 12,
                               "catalog": "case-24cv000123", "standing": "evidence", "kind": "", "confidential": true, "generated": false,
                               "doc": {"address": "file:cases/24cv000123/files/notice-of-hearing.pdf", "name": "notice-of-hearing.pdf", "kind": "pdf", "level": "P3"}, "alsoIn": []}],
                   "recorded": [{"date": "2099-05-14", "step": "Mediation held", "recordedIn": "counsel's letter", "source": "the specification's record"}]},
    "caveats": ["This page is a summary jason generated from the stores. It is never quoted in place of the documents it lists: quote the document, from the file.", "…"]
  }
}
```

The loader drops each `path` the summary carries (an absolute path on disk) and gives the `doc` reference in its place; `tests/test_loader_paths.py` holds it.

`GET /api/collection-reviews?key=24cv000123` (proposed; `review_store.history` per task, filtered by collection; `document_reviews.load` for the members' library ids):

```json
{
  "found": true, "key": "24cv000123", "confidential": true,
  "manager": [{"task": "example-task", "asOf": "2099-03-01", "asOfNamed": true, "written": "2099-10-04", "digest": "0a1b2c3d4e5f6a7b",
               "sources": 14, "law": 3, "notShown": 1, "readings": 0, "runs": 1, "model": "example-model",
               "grounded": 5, "ungrounded": 1, "verified": false, "confidential": true}],
  "lens": [],
  "lensNote": "No member has a stored reading, so no lens has reviewed one.",
  "commands": {"manager": "jason review example-task --collection 24cv000123 --as-of 2099-03-01", "history": "jason review example-task --history"}
}
```

`GET /api/collection-compare?doc=library:4001&a=as-of@2099-10-05&b=records@2099-10-05` (proposed; two `Review` records of an ad hoc vendor collection's invoice, matched by check and code on the server):

```json
{
  "found": true, "document": {"address": "library:4001", "name": "invoice-1042.pdf", "kind": "invoice", "level": "P1"},
  "a": {"lens": "as-of", "lensVersion": "1a2b3c4d5e6f", "asOf": "2099-10-05", "fieldsSha": "aa11bb22cc33dd44", "factsSha": "", "reused": true},
  "b": {"lens": "records", "lensVersion": "6f5e4d3c2b1a", "asOf": "2099-10-05", "fieldsSha": "aa11bb22cc33dd44", "factsSha": "ee55ff6677889900", "reused": false},
  "onlyA": [{"code": "example-due-passed", "message": "The due date of 2099-09-30 has passed as of 2099-10-05.", "severity": "check", "authority": "", "basis": ["text", "today"], "lens": "as-of", "check": "example-due"}],
  "onlyB": [{"code": "example-not-in-ledger", "message": "No ledger row matches this invoice's number and total.", "severity": "check", "authority": "", "basis": ["text", "store"], "lens": "records", "check": "example-ledger"}],
  "both": [],
  "caveats": ["A review is a lead for a person, like the reading it rests on."]
}
```

**Writes** (proposed, behind the write guard, `X-Jason-Token`; a write with no `by` is 400; while someone is signed in, `by` is that person; with writes off, the page shows the command):

- `POST /api/write/collections/<key>/extract` `{by, vision: false}` → `{job, command, existing}` (a job already queued or running is answered, not doubled).
- `POST /api/write/collections/<key>/summary` `{by, asOf}` → `{written: "collections/24cv000123/summary.md", generated: "2099-10-05"}`.
- `POST /api/write/collections/<key>/question/<id>` `{to: "board" | "counsel", by}` → `{item: "BI-2099-07", status: "proposed", session: "executive session"}`; a question already raised is 409 with its item.
- `POST /api/write/collections/<key>/review` `{task, asOf, by}` → `{job, command}` (a pack with no model run; a model run is its own job on the GPU lane).

## What the design must keep

- **A statement, never a finding** (principle 3). Every chronology line names the document and quotes it. Nothing on the screen says an event happened, a fact is true, or a duty was met beyond what the specification's record says, in its words.
- **The specification's record stays apart.** `MatterRecord` and the recorded lane are labeled the specification's, confirmed by a person, and never merged, interleaved, or sorted with the documents' statements.
- **Two sources that disagree are both shown, side by side, and neither is picked.** No "use this value", no "resolve", no default side, no order that reads as a rank. The way forward is a question a person raises, or a document that changes.
- **Recite first; label the reading** (principle 2). Former and successor are both recited where held, each with its day, digest, and caveat; a former section's words are never shown as the law of the day asked. A successor is the table's reading, labeled; the console adds no reading.
- **Every gap is named, with its command** (principle 8). A file with no text is "not read", never "silent". "None was found by rule" is said with "that is not a finding". A store not built shows its command, never an empty band.
- **The workspace edits no document.** Its writes are jason's own derived stores (an extract, the summary page, a review pack, a board item), each a `Confirm` in a named person's name with its CLI equivalent, and a job where it reads with a model or the network.
- **A question reaches the board only as a board item** (principle 5). Raising it records the question; the board decides at a meeting; a question for counsel is the board's to direct. No control answers, approves, or closes a question here, and a review's findings are never an approval.
- **Privacy by level** (principle 6). The server sends the level and holds back what the person may not see. Held-back files are a count, never a name; a confidential collection is a held row outside the private view; executive-session material is named by its general subject only. Nothing is shared from the workspace in this pass.
- **Nothing is worked out on the client.** The read words, the gaps, the questions, the stale lines, the compare's three groups, and the levels all come from a loader.
- **No color-only meaning.** Every state is a word; the counts have a table twin; a conflict is two columns of text, not a red mark.

## Where it goes

Routes are proposed, consistent with [information-architecture.md](information-architecture.md#where-the-proposed-screens-go); none exists yet.

- **Records → Collections** (proposed): `#/collections` lists them; `#/collections/<key>` is one workspace, board-only (`owner: false`), with `Tabs`: **Summary**, **Chronology**, **Citations**, **Files**, **Reviews**, **Questions**. Query: `?tab=`, `?as_of=YYYY-MM-DD`, `?from=`/`?to=` for the chronology, `?doc=&a=&b=` for a compare. A route carries a key or an opaque id, never a name or a search ([security-and-privacy.md](security-and-privacy.md#urls)).
- **`#/legal`**: each matter with a case file links to its workspace (in the private view).
- **`#/actions`**: a board item raised from a question names the collection in its evidence as `collection:<key>` (a new resolver row for `Doc`, at the collection's level), so its chip opens the workspace on the Questions tab.
- **`#/ingestion`** ([screens/records-and-library.md](screens/records-and-library.md)): an ad hoc collection a person names from the library's filters opens the same workspace once `jason collection` takes an ad hoc scope (not built).
- **The dock's Ask**: an answer about a matter cites the workspace's sources as `Doc` chips; the summary is never cited as the record.

**Loaders and writes to add** (each wraps a function that exists, except where marked "to write"; each reads disk only):

| Name | Function behind it | Notes |
| --- | --- | --- |
| `collections` | `document_collections.collections(community)`, `passage_index.count(data_dir, scope)` | held rows outside the private view (opaque `ref`), as `board_items` holds executive rows |
| `collection` | `collection_pages.summarize(community, data_dir, collection, as_of=)` → `Summary.as_dict()`; `case_files.inventory` for each file's `state`; `jason.approvals.docref.file_ref` for each file and place | to write: `header.built` (the index's build, the manifest's `fetchedAt`, the newest `readAt`, the page's "Generated" line), `states[]`, `openQuestions` as `{id, rule, text, sources, raised}` (the rule keyed by `Summary.questions`), and the stale check (an extract's `sha256` against its file; the index's build against a text file's change) |
| `collection-reviews` | `review_store.history(data_dir, task, include_confidential=)` over the tasks, filtered by `collection`; `document_reviews.load(data_dir, lens, as_of)` matched through `fact_conflicts.library_id` | confidential records only in the private view |
| `collection-review` | the kept record (`review_path`) or one `Review` (`document_reviews.load`) | findings grouped by basis on the server |
| `collection-compare` | two `Review` records, or two kept manager records | to write: the match by check and code |
| write `collections/<key>/extract` | `jason.jobs.add(data_dir, ["cases", "--extract-text", "--case", key] (+ `--vision`), confirmed_by=by)` | the local lane, or the GPU lane with `--vision` |
| write `collections/<key>/summary` | `collection_pages.write(data_dir, summary)` under the store lock | `jason collection KEY --write` |
| write `collections/<key>/question/<id>` | to write: a `BoardItem` from the question (category from the kind, ask "decide" or the counsel ask, evidence `collection:<key>` and the sources) through `tasks.board_items.propose`, signed with `by`; a record of the raise in `data/collections/<key>/raised.jsonl` | proposed CLI: `jason collection KEY --raise ID --to board\|counsel --by NAME` |
| write `collections/<key>/review` | `jason.jobs.add(data_dir, ["review", task, "--collection", key, "--as-of", day], confirmed_by=by)` | `jason review TASK --collection KEY --as-of DAY` |

`access.PATH_RULES` needs a row for `collections/*` at the collection's own level (P3 for a case), decided by the store's flag rather than left to the P2 default; and a `collection:` resolver row for `Doc`.

## Accessibility

As [components.md](components.md#accessibility) and [content/patterns.md](content/patterns.md#accessibility-wcag-22-aa):

- **Structure.** One `h1` (the title, or "A legal matter (confidential)" for a held row); each band an `h2`. The tabs follow the tabs pattern with arrow keys, and each tab is reachable by its `?tab=` link. The counts strip has a table twin.
- **Tables.** `FileInventory` is a real table with a caption ("The collection's files, and how each was read"); the read state is a column of text. Wide tables scroll inside their own labeled, focusable region.
- **Quotes and recitals.** A document's words in a `StatementRow` or a conflict side are a `blockquote` with the file and place in its `cite` text, so a screen reader hears whose words they are before the words. A `Recitation` is a `figure` with `blockquote` and `figcaption` (the citation, the version in force, the caveat); in `FormerAndNow` the two figures are a list of two items, each labeled with its day.
- **A conflict** is a list of sides, each a group named "Value $1,250.00, given by 1 document", with no visual order a screen reader must infer; "the order of the sides means nothing" is text in the card.
- **Writes.** `RaiseQuestion` and `ExtractTextAction` are `Confirm`s: the button says the act, the count, and the name ("Queue the text read of 3 files as Jane Example"); the result is a `role="status"` message in place; a refusal is `role="alert"` beside the control, saying nothing was written.
- **Status and time.** A job's progress is polite; the private view's countdown is the built band's. Nothing times out.
- **Target size (2.5.8)**, **redundant entry (3.3.7)** (the name from "Signed in as"), and **use of color (1.4.1)** as the components page says.

### The phone layout (under 720 px)

- The tabs become a `select`. The header stacks: the title, the kind and level words, the day, then "Last built" behind a disclosure; the `Command` copies.
- Each `SummaryBand` is a full-width card; its gaps follow its content.
- The chronology is one column: the date, the role in words, the document chip, then the quote. The specification's lane comes after the documents' groups under its own heading, never interleaved.
- A `FactConflictCard`'s sides stack, each headed by its value; the "order means nothing" line stays above them.
- `FormerAndNow` stacks the former recital above the successor's, each with its day in its heading.
- `FileInventory` rows become cards: the name, the read word, then pages unread and statements.
- `LensCompare` becomes three sections (only in A, only in B, in both); `RaiseQuestion` and `ExtractTextAction` are full width at the foot of their card, not sticky (2.4.11). Nothing scrolls sideways at 320 px.

## Decisions for the design

1. **A held collection's route.** A case's key is often its court number. Decide whether the key may appear in a route and in browser history, or whether every P3 collection's route is an opaque id the server maps, as an executive board item's `executive-<n>` is.
2. **The page on disk.** The workspace computes the summary live; the page on disk is what packs and the index carry. Decide whether the header only dates the page, or also shows "the page on disk differs from the stores" (a server compare that ignores the date line), with **Write the summary page** beside it.
3. **Fetching from the console.** `jason cases --fetch-files` reads Drive. Decide whether the Files tab queues it as a job on the google lane behind `Confirm`, or shows the `Command` only.
4. **The vision read.** It holds the GPU lock and may misread. Decide whether it is offered beside the local read, or only on a file in "partly read", one file at a time.
5. **Raising a question to counsel.** Decide whether "for counsel" is a board item with the counsel ask, or a separate counsel question kept with the collection that the board's packet carries (the confirmations queue's decision 9 asks the same).
6. **Facts, law, application.** Kept reviews do not store their answer in three parts yet. Decide whether `ReviewRecord` shows the three parts now, grouping findings by basis (text as fact; law; profile, store, or today as application), or shows findings by basis words only until the store keeps the parts.
7. **Which day.** The workspace has one as-of day for citations and reviews. Decide whether a review kept as of another day is shown with its own day in its row (and the compare offers "as of the workspace's day"), or the list filters to the workspace's day.
8. **The chronology's weight.** A case gave 41 statements, most "about" dates. Decide whether the "about" group folds by default with its count, keeping the documents' own dates and the specification's lane open.
9. **The proposed kinds.** A vendor's file, a meeting packet, and a system's records are not built as kinds. Decide whether the list shows them as "not built" rows naming the commands that serve them today (`jason inspections` for a system's records), or omits them until each is a `CollectionKind`.

## Not part of this pass

- Any edit to a document, an extract, the specification, or the specification's record of a matter; correcting a case's events or duties is a person's change to the profile.
- Answering, dismissing, or closing an open question, and any board decision: the board decides at a meeting, recorded in `#/room` or `#/decisions`.
- Sharing: exports, a packet line, a copy to a canvas, an email to counsel, or any owner-facing view.
- Including a held-back file (`--include-held`), which stays a terminal step and is never extracted or indexed.
- A summary for an ad hoc scope, stored reviews keyed by a collection's own lens, and the lenses not built (duties, parties, money, against the law, against the governing documents) ([../collections.md](../collections.md#not-built)).
- The context pack itself and a review under it (`handoff-context-pack-workbench.md`); the day control and quote verdicts (`handoff-as-of-and-quote-check.md`).
- Counsel's grant of a matter's file as a role ([security-and-privacy.md](security-and-privacy.md#roles)).
- The previews: the design project's authored preview for each component follows the build; fixtures will be `ui/src/components/collectionworkspace.test.tsx` and its siblings, from the sample data above.
