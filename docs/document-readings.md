# Reading the documents themselves

The county index says what an instrument is and who signed it. The instrument's own text says what it does to other instruments: which declaration it amends, which annexation it rescinds, which units it annexes, which sections it changes. This page is the plan for reading that text: the concepts first, simple parsers over the extracts already on disk, what those parsers get and miss on the county's scans, and the path to the tools that fit the scans better. Survey date: 2026-09-28.

## The concepts

`jason.community.readings` names what a document can state, one record per kind of statement, and reads each with a mixin. The records are the schema whatever reads the text, a regex today or a model later.

| Concept | Record | What it states | Read by |
| --- | --- | --- | --- |
| The recorder's stamp | `Stamp` | the instrument's own number, recording date, page count, title count, fees; or that the copy was never stamped | `StampReader` |
| The title and phase | string, int | the instrument's name and the phase it is for | `TitleReader` |
| A citation | `Citation` | an earlier instrument named with its recording date, and the relation the sentence states: rescinds and supersedes, amends, annexes under, relies on, drawn on the plan or map, or a plain reference | `CitationReader` |
| Annexed property | `AnnexedProperty` | the unit range and the association and condominium common-area designations an annexation covers | `AnnexationReader` |
| The declarant | string | who made the instrument | `DeclarantReader` |
| Changed sections | strings | the sections an amendment amends, deletes, adds, or restates | `SectionReader` |

`Reader` composes them; `read_document` runs it over one extract and `read_folder` over a folder. A `DocumentReading` carries every record, a guess at the document's kind from its title, and whether the extract was readable at all (an image-only PDF yields a header line and nothing else). Two derived views feed the rest of the system: `numbers_on_disk` binds each recorded copy to its instrument number by its stamp, and `proposed_supersessions` lists every "rescinds and supersedes" statement with whether the specification already pins it. A reading is evidence, not a pin: a supersession is pinned as a `Supersession` in `mystique/annexations.py` with its source once a person has read the recital.

## What the simple parsers find

Over the governing extracts, the readers bind recorded copies to their numbers by stamp alone, including files whose names carry no number or whose old stamp OCR broke apart ("2007 1 1217"). They read the unit range and common-area designations of every annexation with a text layer, and state each rescission. The annexed ranges also check the specification: a building's first sale cannot precede the annexation that brought its units in.

What they miss, and why:

- **No text layer.** An image-only PDF extracts to a header line. Nothing textual reads it.
- **Unstamped copies.** A conformed or draft copy carries the "space above this line" box and no stamp. Its recitals still relate every instrument, but it cannot bind itself to a number.
- **OCR inside a range.** Where a digit dropped ("Units 28 through 3"), the reader leaves the end open rather than guess. The common-area designations beside the range still say which building.
- **Doubled spaces and broken lines** inside titles and stamps, handled by flattening the head before matching, which is a crutch.

Mystique's findings are in the private notes (mystique/notes/document-readings.md).

## The path to tools that fit the scans

The county's copies are poor images, and regexes over their OCR will keep missing. The records above are the fixed point: they are what any better reader must produce, and the pinned facts (the supersessions, the phase ranges, the stamp numbers of the copies on disk) are the ground truth to score it against. In order:

1. **Structured extraction by a language model over the page images.** Give the model the PDF pages, not the OCR, and ask for exactly the records above as its output schema. It reads a broken stamp and a dropped digit the way a person does. Score it on the stamped copies and the pinned rescissions before trusting it on the files nothing else reads.
2. **Retrieval over the extracts.** Embed the extracts in passages, so a question like "which instrument reserves the easement over A.C.A. 3" finds the passage across the annexations, the declaration, and the amendments. This is search, not extraction, and it serves the person reading, not the pipeline.
3. **Both together for the request list.** Extraction binds copies to numbers and states what each does; retrieval answers what a missing instrument would add. The copy-order list then asks for the instruments whose statements nothing on disk makes.

None of that changes the layers. The concepts stay in `jason.community.readings`, the pins stay in `mystique`, and a task only applies a result.

### What is built toward that path

- **The scorecard.** `jason.community.extraction` defines an `Extractor` (anything that yields a `DocumentReading` from a file), builds the ground-truth cases from the specification and the record (for each pinned annexation file: the in-force annexation's number, the phase, the building's unit range under its numbering, the A.C.A. number, and the supersession pinned on it; for each file whose name carries a number: that number), and scores an extractor field by field. `jason read-documents` prints the regex reader's card; `extraction_scorecard` is the tool. The card is how a new reader earns trust before it is asked about the files nothing else can read.
- **Passage search.** `jason.community.passages` cuts the extracts into overlapping passages of about 220 words and ranks them by BM25 for a question; `jason read-documents --search "..."` and the `passage_search` tool return the passages with their file and place. It is search for the person, and it pins nothing. The ranker can be swapped for embeddings without changing the passages or the hits.
- **The model reader.** `jason.community.model_extractor.ClaudeExtractor` renders the PDF pages with PyMuPDF, sends the images with a prompt that names the concept records as the answer's shape, and parses the JSON into a `DocumentReading` that the same scorecard reads. It needs the `models` extra and `ANTHROPIC_API_KEY`; without either it fails fast and sends nothing. `jason read-documents --extractor claude` scores it. Nothing it reads is pinned by being read.

## Outlines and the references between documents

Governing documents cite each other and the law by section: "Section 7.2 of the Bylaws", "Declaration 6.5(b)", "Civil Code Sections 5855(d), 5910", "subsection 1.3(d)(ii), below". `jason outlines` gives every such document an outline, so a section is something with a number, and maps each reference to its target.

**Which documents.** The governing documents, policies, and rules are Google Docs; the PDFs elsewhere are exports. `mystique/outlines.py` lists each Doc (`CitableDocument`): key, kind, the Doc, the names other documents cite it by, and the document an amendment amends. It also names the resolutions folder, whose Docs are read as a whole, and the library kinds outlined from their text: the annexations, which supplement the Declaration.

**Outlines** (`jason.community.outlines`).
- **From a Google Doc.** Headings and numbered list paragraphs are sections. Docs draws their numbers from list numbering, so they are not in the text; `outline_from_doc` renders them the way Docs does and writes them the way documents cite them. A level whose format carries its parent is dotted ("7.2"); the rest are in parentheses ("8.5(c)", "3.3(a)(i)"). A heading that prints its own number ("ARTICLE 4", "B-12. PARKING") keeps it.
- **From a PDF's text** (`outline_from_text`). Lines that start with a number, "ARTICLE n", or "(a)". It closes the usual OCR gaps first ("13 .1", "1.3( d)", "6.S(b)"), and reads "(i)" as the letter after "(h)" but as roman i under any other letter.
- Each section spans to the next section at its depth or shallower, so `section_at` finds the innermost section around any place in the text.

**References** (`jason.community.references`). A citation grammar, with each reference tied to the section it sits in, the verb around it (replaces, amends, acts under, is subject to, overrides, takes a definition from, is required by, or cites), and its sentence:
- **Statutes** in any code: lists and subdivisions ("5850(c), (d)"), the code before or after the number ("Corporation Code, Section 7110", "602(k) Penal Code"), and regulations ("10 CCR 2792.23"). A bare four-digit section from 1350 to 6200 is the Civil Code. A pre-2014 Davis-Stirling number (1350 to 1378) is marked as prior numbering.
- **Sections** of the document itself or another, by name before or after ("Declaration Section 6.5(b)", "Section 6.5(d) and Section 6.6(c) of the Declaration", "these Bylaws"). An unqualified section in an amendment or an annexation is the Declaration's, unless the document's own outline has it or its parent (an annexation's own "1.3(d)(ii)").
- **Other:** documents named without a section, resolutions by number, and recorded instruments.

**Checks.** Each reference is resolved against what jason holds:
- a section against the target's outline: found, parent only, or missing;
- a statute against the exported law in `data/authorities`;
- a resolution number against the numbers the resolution Docs print, whether in a header or as the Doc's title.

The findings are leads for a person: a cited section a document lacks, a resolution number printed by several Docs, and statutes cited by their pre-2014 numbers.

**Output.**
- `data/outlines/<key>.json`: each outline, with its text and Drive revision.
- `data/outlines/references.json`: every reference with its status.
- `data/reports/references.md`: the documents, a Mermaid diagram of which cites which, the findings, and the most cited targets.
- `data/outlines/<key>.md`: each document's outline, with each section's references out and what cites it.
- `data/reports/references.html` (`jason.tasks.outline_viewer`): one offline page to explore them. It has the document list, each document's section tree, and each section's text, trimmed to 1,500 characters. It shows what a section cites, with the relation and the status, and marks every status other than found or law on disk. It shows what cites the section, with the quote. It has a graph of which documents cite which and the codes they cite, the findings linked to their sections, and a search over sections and targets ("4926", "7.2"). The data is embedded as JSON, and the page loads nothing from the network.

**Commands.**
- `jason outlines --fetch`: read the Docs and the library's text again (read-only). Without it, the stored outlines are used.
- `--doc bylaws`: one document's outline.
- `--section bylaws#7.2`: a section's text, what it cites, and what cites it.
- `--cites "CIV 4926"`: every document that cites a target, including its subdivisions.

A missing page in a scan looks like a missing section; a person tells a drafting gap from a scan's gap.

Mystique's findings are in the private notes (mystique/notes/document-readings.md).

A missed reference stays missed: the grammar reads what is written the way associations write it, and a model reading one section at a time can add the prose references ("the rules adopted by the Board") later.

`jason outlines --model` is that model. It reads one section's own words at a time (`--model-doc owners-manual` or `--model-doc bylaws#7.2`, repeatable; `--model-limit`, 20 by default) with the shared local model, after `preflight`, under the GPU lock, and only through Ollama on this machine. The prompt lists every outlined document by key with its title and the names other documents use for it, the grammar's naming rules, and a few worked examples, and the answer is held to a JSON schema: the kind of target, the target, a short quote, and the relation. A proposal is kept only when its quote is in the section, compared without regard to case, spacing, or the style of quotation marks and dashes; anything else is dropped and counted. A kept target is named the grammar's way (an alias becomes its key, "the Davis-Stirling Act" is CIV 4000, a name on no list stays `named:` with its words), and one the grammar already found in the same section is not new. What is new goes to `data/outlines/model/references.json`, marked `method: model` with the words the model quoted, never into the grammar's `references.json`: it is a lead a person reads. A section read before with the same words is skipped unless `--model-again`.

## Ordering the copies the records lack

`jason records-request` writes `data/reports/records-request.md` and `.csv`: every instrument the association's record names (the governing instruments, the association's own liens and releases, the liens and notices against it, the construction-period claims) with no recorded copy on disk, with what the county's order form asks for and what the copy costs. A copy on disk is one whose stamp names the instrument, whose file name prints the number, or that a Drive pin names. Each row carries the document number, the book and page (for a twelve-digit number, the first eight digits and the last four), the recording date, the title the index prints, what the instrument is, why the association wants it, the page count (from the stamp, the cached detail, or an estimate marked with an asterisk; `--pages` reads counts from the index now), plain or certified, and the cost at the county's fees: a plain copy $8.00 for the first page and $1.00 for each further page, a certified copy $9.00 and $1.00, as the county's page read on 2026-09-28. The declaration and its amendments are asked certified; a rescinded instrument is asked plain for the file. The order form, the mailing address, the fax, and the phone are on the page. The `records_request` tool returns the same rows.
