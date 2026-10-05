# Reading a collection: the chronology, the conflicts of fact, and the summary page

Two helpers for a careful reading of a set of documents, and one page that gathers them. Each helper is a general lens ([ingestion-and-review.md](ingestion-and-review.md), "A lens"): it works on any slice of the passage index, and it names no association.

- **Chronology:** what happened, in what order, according to which document.
- **Conflicts of fact:** where two documents give different values for what looks like the same fact.
- **The summary page:** for a named collection, one generated page: its files and how each was read, what is missing, the open questions, the conflicts, and the chronology ([The summary page](#the-summary-page)).

All are rule-based: no model and no network. They state findings of fact only, and only as the law's practice allows them to be stated ([ingestion-and-review.md](ingestion-and-review.md), "Three questions"):
- A finding rests on the record, and each is tied to its source: the file, the passage, the word position, and the document's own words.
- Two records that disagree are both kept. jason picks neither.
- What a document says is quoted. Nothing here finds that the thing happened, reads the law, or applies it.

## The scope

A lens takes a `passage_index.Scope` and a title. The scope is the collection's members: catalogs, standings, kinds, folders, and whether the files held back unless asked are included ([applicability.md](applicability.md)). The title names the page.

| Flag | What it does |
|---|---|
| `--catalog NAME` | only this index catalog (repeat). A legal case's catalog, `case-<key>`, opens its own held files, as the document search does. |
| `--standing`, `--kind K`, `--folder F` | only that standing, document kind, or data folder (repeat) |
| `--confidential` | include the files held back unless asked. It never opens a case catalog that is not named. |
| `--title` | the collection's title; default, the scope's own words |
| `--json` | the result as JSON |
| `--write` | save the generated page under `data/collections/<slug>/`. Without it nothing is written. |

`jason index --status` lists the catalogs.

A collection's own generated pages (`data/collections/`) are left out of every such scope. A lens reads documents, never a page a lens wrote.

## The chronology

`jason chronology --catalog NAME [--kind K] [--folder F] [--from DATE] [--to DATE] [--confidential] [--json] [--write]`
(`jason.community.chronology`).

Every dated statement in the scope is an event:

| Part | What it holds |
|---|---|
| The date | read by the existing date readers (`document_models.dates_in`, `invoices.parse_date`), with the words it was written in |
| The quote | the sentence, or the smallest group of clauses, that carries the date, in the document's own words |
| The place | the file, its context line, the section, the passage, and the word and character position |
| The document | its catalog, standing, kind, and whether it is held back unless asked |
| The kind of date | the role and the rule that gave it (below) |
| Also in | the other places that carry a near copy of the statement |

Events sort by date, then by standing: the law, the association's record, a matter's evidence, a reference work, a page jason wrote.

### What kind of date it is

| Role | What it is | Rule |
|---|---|---|
| `document` | the document's own date | at the file's head: a line that is only a date (`date-line`), or a line labeled Date, Sent, Hearing Date, Meeting Date, and the like (`label-line`, `label-above`) |
| `heading` | a date in a short line at the head | `head-line`. Often the document's own date, and not taken for it: a notice's scheduled time reads the same. |
| `name` | a date only the file's name prints | `file-name`: a year, a month, and a day, as a recording's stamp gives them. It is the name's, never the document's words. |
| `embedded` | a message header's date further in | a "Sent:" or "Date:" line inside the document: a quoted message, an attached form |
| `about` | a date the text speaks about | `sentence`; a form's field with its label (`label-line`, `label-above`); a table's cell with the lines around it (`date-cell`) |

- **A range** ("from 1/1/2099 through 12/31/2099") is one event with its last day.
- **"On or about"** is marked.
- **A month with no day** ("March 2099") is the first of the month, marked as a month.
- **The document's own date** is carried on each of its other events, so a line can read "the letter dated ... says".
- **A long statement** is cut around its date, and the cut is marked with an ellipsis.

### Copies

Near copies of a statement on the same day fold into one event, and the other places are listed with it (`retrieval.near_copies`). A short statement (a date line, a form's field) folds only when the passages around it are the same nearly letter for letter. Two letters dated the same day stay two events, and so do two reports filled in on one form.

### The specification's record

Where the specification already holds a chronology for the collection, it is passed in as `recorded`. For a legal case's catalog, `jason chronology` passes the case's events (`LegalCase.events`). They are shown as their own source, "the specification's record", after the documents' statements. They are never merged with a document's statement: a recorded event is the specification's entry, confirmed by a person, and not a quote from a file.

## The conflicts of fact

`jason fact-conflicts`, with the same scope flags (`jason.community.fact_conflicts`).

A conflict lists each value with every document that gives it, each with its quote and its place. It names the rule that found it. There is no score, and the order of the sides means nothing.

| Rule | What it finds |
|---|---|
| `stored-field` | Two documents of one kind, about the same thing, whose stored readings (`data/documents/readings.json`, from `jason models`) give different values for one field. |
| `identifier-amount` | Two documents each have one statement that names the same labeled identifier ("Invoice 1042"), carries exactly one dollar amount, and labels it with the same word ("total"). The amounts differ. |
| `identifier-date` | The same, for exactly one date after the same word ("dated", "recorded", "due"). |
| `dated-statement-amount` | Two documents carry the same sentence about the same date, word for word but for its one amount. The amounts differ. |

### The stored-field rows

`fact_conflicts.FIELD_RULES` says, for a kind, when two readings are about the same thing and what is then compared. The rows name document kinds and the readers' field names, never an association's facts.

- **`same`:** the fields that must all be present and equal: the thing and its period. A missing one is a miss, not a match.
- **`compare`:** dates, amounts, counts, numbers, and the parties' names. A field one reading lacks is not compared. Two spellings of one name are one value.
- **`show`:** fields printed beside each statement to tell the documents apart (a draft flag, the day a report was generated). They are never compared.
- **Several rows a kind.** A policy is the same policy by its number and term. Two policies are about the same thing by what they cover, the building, and the term, so a second policy number for one building and term is found too. One difference found by two rows is listed once.
- **A kind with no row is not compared,** and the report lists it.

A reading belongs to the scope when its file is in it. An index row under the library's text folder is named by its library id (`fact_conflicts.library_id`), and the reading is matched through the library's fold of a document's copies.

A stored field is the reader's reading, not the document's words. Its quote is the first place the text prints the value. When the text does not print it in a form the rule knows (a count, a yes or no), the statement says so and carries no quote.

### Why the text rules are narrow

A false conflict wastes a careful reader's time, so the rules prefer missing one to inventing one.
- A statement with two amounts, two identifiers, or no labeling word is left out.
- `dated-statement-amount` takes only a sentence. A form's line or a table's row is the same words in every copy of the form, about a different parcel or month each time.
- A sentence addressed to "you" is left out: a form letter says the same words to each recipient.

## The summary page

`jason collection KEY [--write] [--json]` (`jason.tasks.collection_pages`). `KEY` is a collection's key or its catalog (`case-24cv000123`); `jason collection` alone lists the collections. Naming a legal case opens its confidential files, as the other commands do.

A collection is a named set of documents with what holds for all of them (`jason.community.document_collections`; [manager-review.md](manager-review.md), "Collections"). Its summary is one page, generated from the stores:

| Section | What it holds | Read from |
|---|---|---|
| What this collection is | its title, kind, and key, and what its material is | the `Collection` record |
| The specification's record of the matter | for a legal case: its forum, role, and status, then its events, then its duties | the `LegalCase` record, and nothing else |
| Sources: the collection's files | each file with its kind, its standing, how its words were read, the pages no reader gave words for, and its dated statements | the passage index; a case's manifest and extracts (`case_files.inventory`) |
| What is missing or unread | files with no text and why, text the index does not hold, image pages unread, files an OCR engine read, files with no dated statement, mentions of a month and a day with no year, what the conflict rules could not compare | the same, by rule |
| Open questions | the facts the stores leave undetermined | below |
| Conflicts of fact | every side with its source | `fact_conflicts` |
| Chronology: what the documents say | the documents' own dates, apart from the dates at a head, in a header, or in a file's name, apart from the dates they speak about | `chronology` |

- **Every statement names its source:** the file and the passage. Nothing on the page finds that an event happened. It says only that a document says so.
- **The specification's entries stay in their own section.** They are confirmed by a person and are not quotes from a file, so they are never merged into the chronology.
- **A held-back file is counted and never named.** Neither is an extract of one.
- **The open questions** are found by rule, and jason answers none:
  - a duty the specification's record does not show either way;
  - an event the specification records on a day for which no statement was read in the files;
  - each conflict of fact;
  - a file whose own date was not read at its head;
  - a date a document gives as "on or about".

**Where it is kept.** `--write` saves `data/collections/<key>/summary.md` under the store lock. Without it nothing is written. The page is written whole each time and never edited: the same stores give the same bytes, apart from the line that carries the date.

**How it is found.** `jason index --build` indexes each collection's pages in the collection's own catalog (`case-<key>` for a legal case), with the standing `page`, the generated flag, and the collection's confidentiality (`collection_pages.PagesSource`). A search that names the catalog returns the summary as a page hit, which every tool labels a summary and never the rule. A search that does not name a case's catalog never sees it.

**It is companion material, never a member.** A collection's scope leaves `data/collections/` out (`Scope.not_folders`). So:
- no lens reads the page back as a document, and a summary made after the page is indexed is the same page;
- the collection's count of files is its documents;
- a context pack never ranks the page with the evidence ([manager-review.md](manager-review.md), "Collections").

## The generated pages

`jason chronology --write` and `jason fact-conflicts --write` save `data/collections/<slug>/chronology.md` or `conflicts.md`, under the store lock. `jason collection KEY --write` saves `data/collections/<key>/summary.md`. Each page opens with:
- **Generated:** by jason, on a date, by rule, from the documents listed under Sources.
- **Standing:** a summary, not the record.
- **Confidential:** yes when any source is held back unless asked, or when the page carries the record of a confidential matter. Such a page is for directors and counsel.
- **Scope:** the scope in a line.

A page is derived. Deleting it loses nothing the command cannot make again. It is quoted to no one in place of the documents it lists.

## Measured

Read-only, on one association's index, October 4, 2026.

| Scope | Result |
|---|---|
| The open library files | about 1,230 dated statements from 169 of 205 files; about 460 near copies folded; about 330 mentions of a month and a day with no year not placed |
| A case catalog of caption transcripts | no full date in the words; the only events were the dates the file names print |
| The open library readings | 203 stored readings, 5 subjects compared, 1 conflict. Read, it was real: two policy numbers for one building and one term. |
| The library with its held files | 29 stored-field conflicts in 8 subjects, not read. By their shown fields, 5 subjects are one report generated on two days. |
| The text rules, every catalog | no conflict. Before `dated-statement-amount` took only sentences it reported one, and it was false: one bill's stub, printed for ten parcels. |
| A legal case's summary page | one page of 8 sections in under a second: 137 dated statements from 18 of its 20 files with text, no conflict, and no stored reading to compare. Made twice, the page was the same. Not yet read by a person against the files. |

So the stored-field rule has one conflict read and found real, and the text rules have none read on real documents. Their precision is tested on made-up text only (`tests/test_chronology.py`).

## Caveats

- **An event is a statement, not a finding.** Read the document, and weigh it against the others.
- **A date the readers cannot read is not there:** a date with no year, a date spelled out in words. The page counts the mentions of a month and a day with no year.
- **OCR can misread a date or a figure.** Check the quote against the file.
- **A two-digit year** the readers place more than twenty years ahead is read a century back ("1/2/98").
- **A date in a file's name** can be a day off: a recording's stamp can be in another time zone.
- **A difference is not always an error.** A later document can replace an earlier one (an endorsement, a revised report), and two documents can speak of different things under one number.
- **No conflict listed is not a finding that the documents agree.**
- **A passage cut from a file with no headings** has lost its line breaks in the index. The lenses read them back from the file. Where the file has changed since the build, a date line there is read as a sentence.
- **Confidentiality carries over.** A page is as confidential as its strictest source.
- **A file with no text gave the summary nothing.** The page lists it as not read. It does not say the file is silent.
- **An open question is found by rule.** A question the rules do not look for is not listed, and "none was found" is not a finding that nothing is open.

## Not built

- A summary page for an ad hoc scope. `jason collection` takes a named collection, and the only named collections are the legal cases with a case file. `jason chronology` and `jason fact-conflicts` still take scope flags.
- The pages `jason chronology --write` and `jason fact-conflicts --write` save are not indexed. Only a named collection's folder is.
- Stored reviews keyed by the lens version and the documents' digests. A page is made again each time.
- A conflict between a document and a store (the ledger, the policy sheet). That is the "Money" lens.
- A date with no year placed by its document's own date.
