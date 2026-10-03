# Records & library

Bands added to `#/records` and `#/ingestion` · phase 2 · CLI: `jason library`, `jason ingest`, `jason revisions`

## In the console

The Records group already shows the records' standing:

| Console screen | What it shows | Loaders |
|---|---|---|
| **Records (CIV 5200)** (`#/records`, `ConsoleRecords`; owner view too) | Each 5200 record with its citation, retention, where the specification keeps it, how many files are there, and its gap; the governing instruments as a timeline; the developer deliveries found and missing; liens the association placed; filings against it | `association-records`, `records-inventory` |
| **Document ingestion** (`#/ingestion`) | Files by classification method and by kind, the records covered, the unclassified list; what each recorded copy says about itself | `library-status`, `document-readings` |
| **Leads** (`#/leads`) | Everything unpinned, in one list: unclassified files, records gaps, supersessions the specification does not pin, missing deliveries | `leads` |
| **Records requests** (`#/records-requests`) | Member requests for records with their 5210 clocks and the board's decisions | `records-requests` |

`GET /api/library` (`?kind=`, `?record=`, `?period=`, `?words=`, `?confidential=1`) already searches the classified library; the onboarding screen uses it to mark a received item.

**What this spec adds:**

1. **Library search** on `#/ingestion`: the search as a screen of its own, with a file's text.
2. **An ingest's report** on `#/ingestion`: what a run over a box of documents found, its questions, and the copy into the library.
3. **Revisions** on `#/records`: how a document changed from version to version, each change tied to an adoption on record or flagged with none found.

## Purpose and personas

- **Manager:** searches the library, runs an ingest, answers its questions. Reads a document's versions.
- **Secretary:** reads the minutes and rules versions.
- **Director:** reads a document's revisions before a rule change.
- **Treasurer:** searches financial records.

## Data

| Band | Source | Loader |
|---|---|---|
| Search | `library_search(kind=..., record=..., period=..., words=..., include_confidential=False)` | `library` (existing) |
| A file's text | `library_text(doc_id, include_confidential=False)` | `library-text` (to add) |
| An ingest | `data/onboarding/ingest-<day>.json` (`jason.tasks.ingest.write_report`): files, duplicates, versions, proposed book, record, and folder, the questions, and the checklist items and gates that moved | `ingest` (to add) |
| A document's revisions | `jason.tasks.revision_detection.history(data_dir, key)` (stored): versions with their sightings and dates, the chain, and changes by section, each tied to an adoption on record or flagged; `section_history(data_dir, key, number)` for one section; `revision_detection.keys(community)` for what can be compared | `revisions` (to add; `?key=`, `?section=`) |

## Layout

```
+------------------------------------------------------------------------------------------+
| LIBRARY · 1,204 files · 38 wait for a kind               jason library --fetch [copy]     |
| Kind [All v]  Record [All v]  Period [____]  Words [______________]  [Search]             |
| Name                                 Kind               Period     Record        Open     |
| 2099-09 Operating statement.pdf      bank statement     2099-09    financial     [Text]   |
| (confidential) 1 file held back                                                          |
+------------------------------------------------------------------------------------------+
| INGEST · last run Sep 30, from "Prior manager box.zip"                                   |
| 212 files · 14 duplicates · 9 versions of known documents · 31 questions                 |
| Ready to file: 160 · need a kind: 22 · need a folder: 9                                  |
| jason ingest SOURCE --park [copy]      jason ingest SOURCE --apply [copy]                 |
+------------------------------------------------------------------------------------------+
| REVISIONS · Rules and regulations                                                        |
| v1 Jan 2097 (base, adopted) -> v2 Jun 2098 (adopted Jun 10, 2098; minutes) -> v3 Feb 2099 |
| Section R-6: words changed between v2 and v3 with no adoption found [compare]            |
+------------------------------------------------------------------------------------------+
```

## Components

`Card`, `Tabs`, `DataTable`, `SearchBox`, `Timeline` (a document's versions), `Findings` (a change with no adoption found), `Evidence`, `Pill`, `Command`, `QuestionCard` (an ingest's questions, answered on `#/onboarding`), `RemoteView`. A side-by-side compare waits on `DiffTable` ([components.md](../components.md#still-proposed)).

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Search | `GET /api/library` with the filters | No | `jason library` |
| Open text | `library-text` for one file | No | — |
| Park the questions, copy into the library | shown as commands. Copying into the library becomes the `local.ingest.apply` kind (phase 3) | Later: an approval, one person, R0 | `jason ingest SOURCE --park`, `jason ingest SOURCE --apply` |
| Fetch versions | shown as a command (reads Drive and PayHOA) | No | `jason revisions KEY --fetch` |
| Compare two versions | `revision_detection.diff(...)` | No | `jason revisions KEY --diff A B` |

**A new version of a recited document is reported, never applied.** The ingest band lists it with "a new version: read it beside the current text. jason does not change the words it recites." Changing which words are in force is `local.living.reread`, a two-person kind.

## States

- **No library:** "The library is unavailable: nothing in `data/library`. Run `jason library --fetch`."
- **No ingest yet:** "No ingest has run. Start one with `jason ingest SOURCE`."
- **A file no rule placed:** "Needs a kind", with the evidence. A model's answer below the confidence floor is a question, never a filing.
- **A change with no adoption found:** "Words changed between v2 and v3 with no adoption found in the board's records." Labeled a finding, with: "This does not say the change was invalid. It says jason found no record of its adoption. Ask the Secretary."

## Privacy

- File names can name owners. Search results show names to the board view only.
- A confidential file is held back and counted (`include_confidential=False`, the default). Showing it is a deliberate request (`?confidential=1`), and, once the private view exists, opened there and logged.
- Restricted 5200 records (the membership list, executive-session minutes, ballots) are listed by kind only.
- Search words can name a person. The screen's route never carries them; the loader takes them as a query today, so a POST form of the search is the safer shape ([security-and-privacy.md](../security-and-privacy.md#urls)).

## Acceptance criteria

1. No search words appear in the screen's route.
2. A confidential file is counted and held back unless asked for.
3. A new version of a recited document is listed as reported, with no control that applies it.
4. A change with no adoption found is labeled a finding with the note above, never "invalid" or "unauthorized".
