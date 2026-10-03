# Records & library

`/records` · phase 2 · CLI: `jason library`, `jason ingest`, `jason revisions`, `jason records-request`

## Purpose and personas

The association's records: what the library holds and of what kind, which Civil Code 5200 records are kept and where, what an ingest of a box of documents found, and how a document changed from version to version, with the adoption on record or its absence.

- **Manager:** searches the library, runs an ingest, answers its questions, and applies it. Reads a document's versions.
- **Secretary:** checks that each 5200 record has a home, and reads the minutes and rules versions.
- **Director:** reads a document's revisions before a rule change.
- **Treasurer:** searches financial records.
- **Reviewer, counsel:** no access. Counsel receives records through a granted matter.

## Data

| Part | Source |
|---|---|
| The library | `library_status` (`jason.mcp.county`): counts by kind, what waits for a kind |
| Search | `library_search(kind=..., record=..., period=..., words=..., include_confidential=False)` |
| A file's text | `library_text(doc_id, include_confidential=False)` |
| The 5200 records | `records_inventory`, `association_records`, `record_locations` (`jason.mcp.county`): each record kind, its statute, and where the profile pins it. A pin is the record; an empty group is a missing document; a folder with no pin is unclassified |
| An ingest | `data/onboarding/ingest-<day>.md` and `.json` (`jason.tasks.ingest.write_report`): files, duplicates, versions, proposed book, record, and folder, the questions, and the checklist items and gates that moved. `ingest.gate(data_dir)` for the onboarding stage |
| A document's revisions | `jason.tasks.revision_detection.history(data_dir, key)` (stored): versions with their sightings and dates, the chain, milestones, and changes by section, each tied to an adoption on record or flagged with none found. `section_history(data_dir, key, number)` for one section |
| Documents that can be compared | `revision_detection.keys(community)` (`jason revisions --list`) |

## Layout

```
+------------------------------------------------------------------------------------------+
| Records & library                                                                        |
| [Library] [5200 records] [Ingest] [Revisions]                       (tabs, one per band)  |
+------------------------------------------------------------------------------------------+
| LIBRARY · 1,204 files · 38 wait for a kind · synced Oct 2 · jason library --fetch [copy]   |
| Kind [All v]  Record [All v]  Period [____]  Words [______________]  [Search]             |
| Name                                 Kind               Period     Record        Open     |
| 2099-09 Operating statement.pdf      bank statement     2099-09    financial     [Text]   |
| Minutes 2099-08-12.pdf               minutes            2099-08    minutes       [Text]   |
| (confidential) 1 file held back                                    [Ask to show]          |
+------------------------------------------------------------------------------------------+
| 5200 RECORDS                                                                             |
| Record                       Statute         Kept in                          Standing   |
| Minutes of the board         CIV 5200        Library: Board/Minutes           pinned     |
| Membership list              CIV 5200        (restricted)                     pinned     |
| Reserve study                CIV 5200        none pinned · 3 classified files  MAP ask   |
+------------------------------------------------------------------------------------------+
| INGEST · last run Sep 30, from "Prior manager box.zip"                     [New ingest]  |
| 212 files · 14 duplicates · 9 versions of known documents · 31 questions (parked: no)    |
| Ready to file: 160 · need a kind: 22 · need a folder: 9                                  |
| Moved: checklist "Insurance policies" missing -> present; gate "ingest" open -> closed   |
|                                     [Park the questions]   [Plan: copy into the library] |
+------------------------------------------------------------------------------------------+
| REVISIONS · Rules and regulations                                         [Fetch versions]|
| v1 Jan 2097 (base, adopted) -> v2 Jun 2098 (adopted Jun 10, 2098; minutes) -> v3 Feb 2099 |
| Section R-6: words changed between v2 and v3 with no adoption found [finding] [compare]  |
+------------------------------------------------------------------------------------------+
```

The 5200 table's statute column shows the citation the record kind carries (`AssociationRecord`), never one typed into the page.

## Components

`page-header`, tabs (proposed: `tabs`, built as links with `aria-current`, so each band has its own URL fragment), `data-table`, `filters-bar`, `section-card`, `freshness`, `cli-hint`, `evidence-chip` (`--confidential` for a held-back file), `status-badge`, `diff-table`, `queue-item` (an ingest's questions), `job-status` (ingest, fetch), `states` (empty), `states` (unavailable).

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Search | POST (words can name a person). Results without a query string | No | `jason library` / `library_search` |
| Open text | `library_text(doc_id)` | No | — |
| Ask to show (confidential) | Re-reads with `include_confidential=True` for this file, logged | No; logged as `reveal` | — |
| New ingest | `ingest.run(community, data_dir, sources)` as a job: inventory, read, classify, find versions, propose. Writes only its report and staging under `data/onboarding/` | No (R0, staging only). Logged with who started it | `jason ingest SOURCE` |
| Park the questions | Parks the ingest's questions in the intake queue | No approval: a `data/` write, logged with the acting name | `jason ingest SOURCE --park` |
| Plan: copy into the library | Plans `local.ingest.apply`: copies the ready files into `data/library/files` and records them in `library.db` | **Creates an approval** (phase 3, R0, one person). Nothing goes to Drive or PayHOA | `jason ingest SOURCE --apply` |
| Fetch versions | `revision_detection.fetch_drive` / `fetch_payhoa`, then `build`, as a job. Reads Drive and PayHOA; writes the stored history | No | `jason revisions KEY --fetch` |
| Compare two versions | `revision_detection.diff(...)` in a `diff-table` | No | `jason revisions KEY --diff A B` |
| Answer a MAP question (a record with no folder) | Opens the question on `/onboarding#q-{id}` | No | — |

**A new version of a living or citable document is reported, never applied.** The ingest band lists it with "a new version: read it beside the current text. jason does not change the words it recites." Changing which words are in force is `local.living.reread`, a two-person kind.

## States

- **No library:** "The library is unavailable: nothing in `data/library`. Run `jason library --fetch`."
- **No ingest yet:** "No ingest has run. Start one with a folder, a zip, or a Drive folder."
- **Ingest job running:** the job panel with its stage: inventory, read, classify, versions, report.
- **A file no rule placed:** "Needs a kind" with the evidence. A model's answer below the confidence floor is a question, never a filing.
- **No revisions stored:** "No version history for this document. Fetch versions reads Drive and PayHOA."
- **A change with no adoption found:** "Words changed between v2 and v3 with no adoption found in the board's records." Labeled a finding, with the note: "This does not say the change was invalid. It says jason found no record of its adoption. Ask the Secretary."

## Privacy

- File names can name owners. Library rows show names to the manager, director, and secretary; to the treasurer only for financial kinds.
- A confidential file (`library_search(include_confidential=False)`, the default) is held back and counted, and shown on request, logged.
- Restricted 5200 records (the membership list, executive-session minutes, ballots) are listed by kind only, and open only in the private view.
- An ingest report names its files and is P1; its private copy stays in `data/onboarding/`.

## Acceptance criteria

1. Search is a POST, and no search words appear in any URL.
2. A confidential file is counted and held back until "Ask to show", which logs a reveal.
3. A new ingest writes nothing outside `data/onboarding/`, and "Plan: copy into the library" creates a `local.ingest.apply` approval.
4. A new version of a recited document is listed as reported and has no control that applies it.
5. A change with no adoption found is labeled a finding with the note above, never "invalid" or "unauthorized".
6. A 5200 record kind with no pinned folder shows its MAP question link.
