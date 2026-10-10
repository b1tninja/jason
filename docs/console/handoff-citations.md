# Handoff: the statutes documents cite, and the reference shelf

For the design pass on the components that show what a document cites and whether jason holds the law it cites. The data exists today: `jason reference --cites`, the ingest report's "Statutes cited", and the MCP tools `document_citations` and `citation_gaps` ([citations.md](../citations.md#what-other-documents-cite-and-whether-the-shelf-holds-it), [reference-shelf.md](../reference-shelf.md), [mcp.md](../mcp.md)). The four loaders are built (`jason.web.extra.citations`, registered in `jason.web.sources`) and answer from disk, for the board only; no component renders them yet. Behavior and words are settled by this page, [components.md](components.md), [doc-component.md](doc-component.md), [documents.md](documents.md), and [content/style.md](content/style.md).

These components pair with what the console already has: `Doc` and `DocumentViewer` (a reference work is a document), `Recitation` and `CiteBox` (a section's words, when the shelf holds it), `Pill`, `DataTable`, `Stat`, `Caveats`, `Command`, `Findings`, `Card`, `Tabs`, and `RemoteView`. Build new parts only where the table says so.

## The idea in one line

A citation is a question: **are that section's words on the shelf, so a reading of this document can be checked against them?** Every component answers it in one of seven words, never in color alone, and never says more than the grammar read.

## The components

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `StandingPill` (a `Pill` preset) | everywhere a cited section appears | a row's `standing` | the seven words below; a row whose survey did not ask lawlibrary |
| `CitedSections` | Reference shelf → a work; Document ingestion → Statutes cited | `GET /api/citations?source=&file=` | not surveyed (the command), loading, listed (gaps first), filtered to none, one row open (its quote and page), a source with no citation, the tool's own `found: false` |
| `CitationChip` | in any sentence that names a statute: the governing-documents reader, `AskPanel` answers, a finding's text | one citation and its standing | on the shelf (opens its `Recitation`), not exported (says so, shows the proposal), not found, renumbered (with its successor), unchecked, focus and hover card |
| `CitationGaps` (with `Proposal`) | Records & library → Reference shelf, top card; the law-review procedure's step | `GET /api/citation-gaps` | no survey yet (commands), gaps listed by code, a proposal ready to copy, unchecked count with the command, a section exported since (gone from the list), no gaps |
| `StandingStrip` | above `CitedSections`; on each work card; on the ingest card | `counts` | all on the shelf, a few gaps, mostly unchecked, none cited; its table twin |
| `ReferenceShelf` and `WorkCard` | Records & library → Reference shelf | `GET /api/reference-works` | on disk or missing (the fetch command), never surveyed, surveyed (date, lawlibrary asked or not), and the work's own caveat, always open |
| `WorkReader` (a kind in `DocumentViewer`) | opened from a page chip or a work card | `GET /api/reference-page?work=&page=` | opening, a page with its text, the cited sentence marked, a page with no text layer, previous and next, the page number as PDF page and as printed |
| `IngestCitations` | Document ingestion (`#/ingestion`) and the Onboarding ingest stage | the ingest report's `citations`, `GET /api/ingest-citations` | no ingest yet, by file (a count and its gaps per file), the same list as `CitedSections`, lawlibrary not asked (`--no-law`) |
| `Successor` | inside `CitationChip` and `CitedSections` | `authorities` for a former section: `nowAt`, `successors[]` | a former Davis-Stirling number with its successor and where that came from (disposition table, Commission Comment, or a similarity candidate), more than one successor, none |

## The seven words

The words are the codes' own, with one-line meanings the pill's title carries. Keep the words; they are how a person reads the page without the color.

| Word | `standing` | Meaning | What the row offers |
| --- | --- | --- | --- |
| on the shelf | `ON_SHELF` | a page under the authorities shelf holds this section | open its `Recitation` |
| not exported | `NOT_EXPORTED` | lawlibrary holds the section and the shelf does not | the proposal to add it; "a lead for a person" |
| not found | `NOT_FOUND` | the current publication has no such section | read the sentence: the document may be wrong, or the reading |
| renumbered | `RENUMBERED` | a pre-2014 Davis-Stirling number (1350 to 1378) | its `Successor` |
| regulation | `REGULATION` | a regulation the shelf does not hold | where the Department publishes it |
| other code | `OTHER_CODE` | a code lawlibrary does not hold (a fire, building, or city code) | nothing to open |
| unchecked | `UNCHECKED` | not on the shelf, and lawlibrary was not asked | the command that asks |

`NOT_FOUND`, `NOT_EXPORTED`, and `RENUMBERED` are the gaps and sort first. A gap is a lead, not a finding: never red alone, never "error" or "invalid".

## Data shapes

Real statute numbers (they are public law) and made-up file names. These are the payloads the tools return today, key for key.

`GET /api/citations?source=ingest&file=notice` (`document_citations`):

```json
{
  "found": true, "source": "ingest", "report": "ingest-2099-10-03.json", "file": "notice",
  "lawChecked": true,
  "counts": {"ON_SHELF": 2, "NOT_EXPORTED": 1, "RENUMBERED": 1},
  "total": 4, "shown": 4,
  "sections": [
    {"citation": "GOV 66427", "standing": "NOT_EXPORTED", "meaning": "in the law, not exported", "mentions": 2,
     "citedBy": ["notice-example.pdf"], "page": "", "subdivisions": ["(b)"],
     "quote": "Under Government Code Section 66427 a notice is given."},
    {"citation": "CIV 1351", "standing": "RENUMBERED", "meaning": "a pre-2014 Davis-Stirling number", "mentions": 1,
     "citedBy": ["notice-example.pdf"], "page": "", "subdivisions": ["(k)"], "quote": "See also Civil Code Section 1351."},
    {"citation": "CIV 5650", "standing": "ON_SHELF", "meaning": "on the authorities shelf", "mentions": 1,
     "citedBy": ["notice-example.pdf"], "page": "", "subdivisions": [], "quote": "Pursuant to Civil Code Section 5650 ..."}
  ],
  "proposal": "GOV 66427",
  "notes": [],
  "caveats": ["Citations are read by a grammar: a range is read as its two ends, ..."]
}
```

`GET /api/citation-gaps` (`citation_gaps`): `{found, surveys: [{name, kind, made, lawChecked}], total, shown, gaps: [<a row above>], proposal: "BPC 11500; GOV 66427", unchecked, caveats}`. A reference work's rows carry a `page` (the first PDF page the citation is on); an ingest row has an empty one.

`GET /api/reference-works` (built): `{works: [{title, file, author, publisher, year, url, covers, caveat, topics, onDisk, pages, surveyed: "2099-10-03" | null, lawChecked, counts, command}], caveats}`. `command` is the survey command while a work has none kept, else null.

`GET /api/reference-page?work=&page=` (built): `{found, work, file, author, year, page, pages, text, noText, banner, caveat}`; `found: false` with a note for an unknown work, a page past the end, or a work not on disk (with `command`). `page` counts PDF pages; a printed number is the reader's own note, never computed. A bad `page` or `limit` is a 400.

A former section, from `authorities("CIV 1351")`: `{citation: "CIV 1351", former: true, nowAt: "CIV 4175", successors: [{...}], caveats: [...]}`.

## What the design must keep

- **A reading, a match, or a gap is a lead, not a finding** (principle 3). A citation row says what the grammar read. "Not found" is not "wrong": the sentence is shown so a person reads it.
- **The words of the law come from the shelf, never from a guide.** A reference work is explanation. On `WorkReader` a banner says so on every page ("An explanation, not the law and not the association's record"), with the work's own caveat (its age, what it predates) always visible. A section's words are only ever in a `Recitation` from the authorities shelf, with its citation and the version in force first; a `CitationChip` for a section the shelf lacks opens no text of any kind.
- **jason adds nothing to the shelf.** The proposal is a string a person copies (`BPC 11500; GOV 66427`) into the specification's authority list. There is no "Add" button, and the card says who does it: a person, in `jason.community.authorities`, with the reason.
- **The survey is dated.** Every list says when it was made and whether lawlibrary was asked ("Looked up in lawlibrary Oct 3" or "Not looked up: the shelf only"). A gap exported since is gone from the list, and the list says it was checked against the shelf as it is now.
- **A range is read as its two ends.** A caveat in words on any list ("Sections 10000-10580 are read as 10000 and 10580"), as `Caveats` renders it: verbatim, never behind a toggle.
- **Ingest rows name the association's files.** They are as private as the ingest report; they appear only where the Document ingestion screen does, and not in the owner view. A reference work's rows are public (P0).
- **Nothing here writes.** Fetching a work and running a survey are commands (`Command`: copies, never runs). No `Confirm` is needed in this pass.
- **No color-only meaning.** The seven words, a count in text beside any bar, and a table twin for `StandingStrip`.

## Where it goes

- **Records & library → Reference shelf** (a new tab beside Library and Ingest): `CitationGaps` on top, then the `WorkCard` list, then a work's `CitedSections` when one is chosen. Route `#/records/reference` and `#/records/reference/<work>`.
- **Document ingestion** (`#/ingestion`): an `IngestCitations` card after "Versions", before "Questions", in the order the report prints.
- **`CitationChip`** in the governing-documents reader's findings and in `AskPanel`'s sources, so a statute named anywhere shows whether jason holds it. It replaces nothing: a `Doc` chip is for documents, this is for statutes.
- **Onboarding's ingest stage** shows `StandingStrip` only, with a link to the ingestion screen.

## Decisions for the design

1. **Gaps first, or all?** The guide's survey is 35 gaps of 90 sections, many cited only in a legislative-history footnote. Default to the gaps, grouped by code, each with the page and sentence; decide how a long list is scanned (group by code, sort by mentions, or fold sections cited only once on the last pages).
2. **The proposal.** A code block that copies. Decide whether it is one string for all codes or one per code, and how "who adds this and where" reads without a button.
3. **The chip's weight.** A statute appears many times in a sentence-heavy screen. Decide how quiet an `ON_SHELF` chip is against a gap (a standing dot and word on focus, or always the word).
4. **`WorkReader` and the PDF.** The text layer has the page markers; the PDF has the layout. Decide whether the reader shows the text, the PDF, or both with the cited sentence marked in the text.
5. **Renumbered.** Show the successor inline (`CIV 1351 → CIV 4175`) or as a disclosure. More than one successor, and a successor that is only a similarity candidate, must read as less certain than a disposition table.
6. **Unchecked.** Most rows are unchecked until someone runs a survey with lawlibrary. Design the state of a screen that is mostly unchecked so it reads as "not asked yet", not "bad".
7. **Slow surveys.** A survey with lawlibrary takes seconds, and one over a large ingest longer. They run as commands, so the page only reads the result: design the stale state (a survey older than the shelf's last export).

## Accessibility

As [components.md](components.md#accessibility): the list is a real table (`DataTable`) with the standing as text in its own column, sorted state announced; filters in a labelled group with a polite live region for the result count ("12 of 90 sections"); a row opens a disclosure with `aria-expanded`; `CitationChip`'s card opens on focus as well as hover and closes on Escape, returning focus; `WorkReader` is a dialog like `DocumentViewer` (focus on its heading, Escape returns focus to the opener, previous and next as buttons with the page number in text); `StandingStrip`'s bar is decorative with a table twin; every state in the tables above is a word.

## Not part of this pass

- Statute-to-statute walks (a section citing another): lawlibrary's `Citation(...).refs` ([citations.md](../citations.md)), not built.
- Any write: adding an authority row, pinning a citation, resolving a gap.
- Searching the shelf's passages: the passage index's `jason index --search --standing reference` has its own screen question ([collections.md](../collections.md) and the Ask drawer).
- The previews: the design project's authored preview for each component follows the build, as for the earlier handoffs; fixtures will be `ui/src/components/citedsections.test.tsx` and its siblings, from the sample data above.
