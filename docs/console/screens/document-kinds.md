# Document kinds

A new tab, `#/ingestion/kinds`, beside the library search, and a page for one kind, `#/ingestion/kinds/<kind>` · phase 3 · CLI: `jason library` (built), `jason library --score`, `jason ingest` · loader: `GET /api/library-kinds` (built: `jason.tasks.library_kinds`; `?kind=` for one kind, `?kind=unclassified` for the misses) · MCP: `library_status`, `library_search`, `records_inventory` (built); a kinds tool (to add)

## In the console

Part. `#/ingestion` shows files by classification method and by kind as two counts, and `GET /api/library` searches the classified library by `kind`, `record`, `period`, and `words` ([records-and-library.md](records-and-library.md)). Neither shows a kind with nothing in it, how a single file got its kind, or what jason read from it. This screen is that: the **shelf** of every kind jason knows, and the record of how each file was placed.

## Purpose and personas

Answer "what do we hold, what don't we, and why is this file called that?" The library is only as trustworthy as its classification, and a person can trust a classification only when they can see how it was made.

- **Manager:** finds a kind's files, sees what is unclassified, corrects a wrong kind by proposing a rule.
- **Secretary and records custodian:** reads the shelf against the records the law requires the association to keep, and sees each gap.
- **Treasurer and director:** read the financial and insurance shelves by period; read-only.
- **Counsel (later):** reads a file's kind and how it was determined before relying on it.
- **Owner (later):** sees a document's kind chip on the documents they may see; never the shelf.

## Data

| Part | Source | Level |
|---|---|---|
| Every kind, its shelf, and the Civil Code 5200 record it satisfies | `jason.community.documents.PROFILE` (kind to category and record), through `library_kinds.shelf` | P0 |
| Files per kind, per method, per period, and held back | `data/library/library.db` `documents` (`kind`, `category`, `records`, `method`, `period`, `confidential`), counted by a loader | P0 for counts; a held file adds to its count only |
| How a file was placed | the same row (`method`, `evidence`, `confidence`, `classified_at`), with the rule steps recomputed by `Community.classify_document(name, folder, path)` and the phrase rules in `jason.community.content`. A model's answer is stored as a reading with its confidence | P1 |
| A kind's one-sentence description | the kind's docstring row in the specification (to add: `Community.kind_notes()`, empty by default) | P0 |
| What jason reads from a kind | the typed readings of the document models (`jason readings`, `jason.community.kind_readers`): the fields found, with the words each came from | P1; P2 for a held file, so none |
| Where a missing kind would come from | the sources the specification names for the kind (`SyncRule`s, PayHOA folders, the sender directory): their names only, never a query | P0 |
| A first-page thumbnail | a thumbnail the server makes from disk and serves by URL (`DocRef.thumb`); none for a held file | P1 |
| A person's answer for one file | `data/library/classified-by-person.json` (built; `library.person_kinds`) | P1 |
| A proposed rule | `data/library/proposals.json` (to add): the file, the kind asked for, the reason, who, when, the files the rule would also move, and its status | P1 |

Nothing on load calls PayHOA, Google, or a model. A refresh of the classification is a person's job (`jason library`).

## Layout

```
+-------------------------------------------------------------------------------------+
| Kinds                                          jason library [copy]                  |
| 66 kinds · 58 have files · 8 empty · 10 files without a kind        [Unclassified 10]|
| Shelf [All v] Record [All v] Period [____] How placed [All v] Held [Include v]       |
+-------------------------------------------------------------------------------------+
| GOVERNING                                                                           |
| [Declaration 2 · 2099 · CIV 5200(a)(1)] [Amendment 4] [Bylaws 2] [Annexation 9]     |
| FINANCIAL                                                                           |
| [Bank statement 79 · 79 held · 2099-09] [Tax return · none · CIV 5200(a)(6)]        |
| ...                                                                                 |
+-------------------------------------------------------------------------------------+
| Library built Oct 1 from PayHOA, the Drive, and the mail. A kind is a name rule's    |
| answer unless the file says otherwise.                                               |
+-------------------------------------------------------------------------------------+
```

One kind's page:

```
+-------------------------------------------------------------------------------------+
| Bank statement · Financial                       [Open the shelf]                    |
| The bank's monthly statement of an account. Held back: every file is confidential.   |
| Satisfies CIV 5200(b), enhanced records · 79 files · newest 2099-09                  |
| By name or folder 79 · by its text 0 · by an agenda item 0 · by a model 0 · by a person 0 · no rule 0                  |
+-------------------------------------------------------------------------------------+
| Files (held)    A held file lists no name, thumbnail, or text. Counts only.          |
+-------------------------------------------------------------------------------------+
| What jason reads from this kind: statement date · account (last four) · ending balance|
+-------------------------------------------------------------------------------------+
```

A file's drawer (from a row anywhere a `Doc` appears) shows `ClassificationTrace`, then `ReadingFields`, then `KindCorrection`.

## Components

`KindShelf`, `KindTile`, `KindPage`, `KindBadge`, `ClassificationTrace`, `MethodMix`, `FacetBar`, `SampleStrip`, `ReadingFields`, `KindGap`, `KindCorrection`, `CoverageNote` (proposed, none in jason-ui or [components.md](../components.md#still-proposed); specified in [../handoff-document-kinds.md](../handoff-document-kinds.md)); `DocList` and `Doc` for files, `Findings` for the unclassified, `Caveats` for the library's age and the model's limits, `Command` for the CLI, `Confirm` for a proposal, `ReadingLabel` for a model's answer.

## Actions

| Action | Effect | How |
|---|---|---|
| Filter the shelf | `GET /api/library-kinds` with facets | a read |
| Open a kind | its page and file list | a read |
| Open a file's trace | the steps jason took and how each ended | a read; recomputed from the stored row, never a model call |
| See a file's reading | the fields found with their words | a read; none for a held file |
| Choose a kind for one file | `library.set_person_kind` (the store `jason intake` writes): the file takes that kind, method "a person's answer", with who and when. It outranks every rule | a person's act, in their name, behind `Confirm`; changes that file only |
| Propose a rule for a recurring mistake | writes a proposal and previews the rule and the files it would move | a person's act, in their name, behind `Confirm`; nothing is reclassified |
| Decide a proposal | accepts or declines; an accepted one is a rule row a person adds to the specification | the manager or a director; jason never edits the specification |
| Reclassify the library | `jason library` | shown as a command; a job later, behind `Confirm` |

jason never decides a file's kind here: a file's kind changes only by a person's answer for that file, and a rule changes only when a person adds the row to the specification and the library is reclassified.

## States

Loading; library unavailable ("The library is unavailable: nothing in `data/library`. Run `jason library --fetch`."); never classified (every tile empty, one command); no files for a kind (a gap, with its sources named); every file in a kind held back (the count and "held back", no strip); a kind with a model-placed file (that file is flagged "a reading"); no kind notes on file (the tile shows the kind's word and nothing else); phone width (shelves as lists, filters in a sheet, one thumbnail with a count); print (the shelf as a table).

## Privacy

The shelf and its counts are P0. A confidential file is counted and never named, shown, thumbnailed, read, or searched here; the count is the only thing a person without the right sees. A file's text and readings come from their own loaders at their own level. A proposal names the person who made it and is P1. An owner sees a document's kind chip only on a document they may see.

## Acceptance criteria

1. With the sample shelf, every kind is on its shelf in the fixed order, a kind with no files draws as a gap, and a kind with a required record names its citation only when the specification carries one.
2. A file placed by name, by its text, and by a model each show their method as a word, and the model's answer carries `ReadingLabel` and its confidence band.
3. A file no rule placed shows "no kind yet" in the kind's place, never a guessed kind, and the unclassified view uses the same facets.
4. A confidential file adds one to its kind's count and shows a lock; there is no name, thumbnail, text, or reading for it anywhere on the screen.
5. A person's answer for one file changes that file only, shows the method as "a person's answer" with who and when, and can be undone by choosing again; a proposed rule changes no file's kind, its preview names the rule and lists the other files it would move, and "applied" appears only once a rule row exists.
6. With the network off and no model loaded, the screen renders from the library on disk; no call is made on load.
7. Every status and method is readable without color; the shelf is navigable by keyboard in reading order; the phone and print layouts work as stated.
8. `KindBadge` renders the same in the unit manual's documents, a fact's sources, and a loss packet as in the library.
