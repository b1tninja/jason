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

This association's findings are in its private notes (mystique/notes/document-readings.md).

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

### Section numbers from a scan's OCR

A recorded copy's OCR garbles many labels, and `outline_from_text` reads only clean ones. Its misses come in a few kinds:
- a dropped dot ("41 Residential Use" for 4.1);
- a letter or a wrong digit for a digit ("ARTICLES EASEMENTS" for Article 9, "3.2" between 5.1 and 5.3);
- a bracket for a parenthesis ("{c)", "(b}");
- a glyph run into its parenthesis ("Gj)", "Q)");
- an empty or half label ("()", "( Rehearing");
- a misread roman numeral ("(it)", "(11)", "(ili)");
- stray marks before the label ("“ (a)", "| (b)");
- a table of contents whose dot leaders OCR broke up, or that another engine lays out in columns: bare "ARTICLE 2" lines and rows of numbers ("2.1 2.2 2.3");
- a wrong digit in a clear-looking number ("1.40" between 1.9 and 1.11);
- a heading run into the line before it ("ARTICLE 3 COMMON AREA 3.1 Ownership of Common Area. (a) Association Common Area. ...");
- a section number read on the line above its caption ("6.13 (ii) By Recording a lien ...", with "Foreclosure of Liens." alone below);
- subsections listed inline ("Rules (i) limiting ..., (ii) limiting ...").

Two steps recover them. Each keeps what it did as a note, and a miss stays a miss.

**The label grammar** (`jason.community.outline_labels.outline_from_ocr`) reads each line's start against the few labels the order allows next. It never reads a token as just any label.
- **The grammar.** It reads "ARTICLE n", "A.n" sections, and four subsection series: (a), (i), (A), (1). A letter comes under a section, a roman numeral under a letter, and a capital under a roman numeral. Another series is allowed at a cost.
- **The confusions.** A token's distance to each expected label is a weighted edit distance:
  - i, l, 1, I, |, ! and t are near, and so are o, 0, O and s, 5, S;
  - a dropped or doubled stroke in a roman numeral, a missing dot, or a missing parenthesis costs a little;
  - an unrelated glyph costs a whole substitution. That is accepted only with a caption after the label. For a section number, the next clear label must also agree: "9.4" before "9.2" is 9.1.
- **The order.** Labels increase. A skipped label is a gap, noted, and a clear later number stands (an excerpt that starts at 4.15). A clear label that goes backwards is a cross-reference at a line's start, read as text.
- **Front matter.** A row of numbers alone is a table of contents and read as text. When a captioned article heading starts the order again from a lower number ("ARTICLE 1 DEFINITIONS" after bare headings up to "ARTICLE 16") and what was read so far carries almost no words of its own, that was a table of contents: it is dropped, with a note, and the body is read from there.
- **Run-in and displaced headings.** An article heading's line is searched for its first section and that section's "(a)" run into it. A section number read above its subsection line, with its caption alone a line or two below, is moved back before its caption.
- **Inline labels.** A line label whose predecessors were not read ("(iii)" with no (i) or (ii)) looks for them mid-line in its parent's words. It splits them out, then reads the rest of that series on its line. An inline enumeration nothing points to stays words.
- **A hanging caption.** A short Title Case line just before a label line with no caption of its own is that label's caption, when the label's siblings carry captions.
- **Firm and unclear.** Each label (`Mark`) records how it was read: clear, recovered, or inline. It is firm when it was read cleanly and in order.

The outline's text writes each label cleanly ("Gj)" as "(j)", "41" as "4.1").

**Alignment to a reference** (`jason.community.outline_align.align_to_reference`) uses a copy of the same document, such as the working Doc or an earlier reading. The copy is evidence, not authority: it may number a list the recorded text runs inline, or nest a list a level too deep. It is used only where the reading has no clear answer:
1. **Align.** The two outlines' sections are aligned in order, within an article of each other, by the words that open them. The comparison uses letters and digits only, so "ofthe" meets "of the".
2. **Renumber the unclear.** A firm label the copy numbers otherwise is kept, and the difference is a finding (`DISAGREES`). An unclear one takes the copy's number (`RENUMBERED`), and its subsections follow. An example is "(1)" read as an unusual numeric series where the copy has (b).
3. **Place the missing.** A section only the copy has is looked for between its neighbours' places, after a label token in the reading that its words follow. The token may be inline ("(iv) the right to ...") or garbled at a line's start ("63) Any proposed action"). If found, it becomes a section (`ALIGNED`). Where the reading's own clean label differs ("(i) managing" where the copy has "(a)"), the reading's label stands and the difference is a finding. Words with no label token are never split.

**In the living documents.** `living_docs.build(numbering=...)` chooses how a base read from text is numbered:
- `"text"` is `outline_from_text`;
- `"labels"` is the grammar;
- `"aligned"` is the grammar, then the working copy.

Unless a caller says otherwise, a document with a working copy is numbered `"aligned"` (the board approved the working copy as the numbering reference) and one without is numbered `"labels"` (`living_docs.default_numbering`). The re-read's dry run numbers both readings the same way, so its migrated transcriptions are keyed as the builds key them. The notes go to `Built.numbering` and to `report.json` under `numbering`.

**A trial on a recorded declaration.** It compared every section with the board's working copy:
- **The grammar alone** cut the sections in one outline only by about two fifths. No section that had matched began to differ. The table of contents no longer passes as sections, so the corrections it had made stale applied.
- **With alignment**, they fell to about a third. What remains is mostly the copy's own numbering: lists it enumerates with letters where the recorded text has roman numerals, a list nested a level too deep, a renumbered run of subsections, and a section an amendment added. Those are findings for a person, not OCR.
- **The words.** The amended sections and the rule checks were unchanged. More sections are now compared word by word, and their differences are the OCR's word slips.
- **One side effect.** A correction keyed to a section whose inline subsections alignment splits out early ("7.3(b)" holding words now in "7.3(b)(iii)") goes stale. It is re-keyed to the subsection.
- **A second engine's reading.** The Tesseract command-line tool's reading of the same scan lays its table of contents out in columns. Before the front-matter and run-in rules, the grammar read about three fifths as many sections in it as in the first reading, and the articles collapsed under the table's last heading. After them, both readings come within a few sections of each other, by the grammar alone and with alignment, and the re-read's dry run leaves no transcription unplaced.

**A layout model?** Recognising headings and list items with a model such as granite-docling or PaddleOCR-VL (see [document-tools.md](document-tools.md), "Not tried yet") would add little to the numbering. After the grammar and alignment, a handful of labels remain garbled beyond reading. A trial is worth its download only if it is scored as a whole-page OCR on the word differences, with label recovery (`outline_from_ocr` over its text) as a second score.

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

This association's findings are in its private notes (mystique/notes/document-readings.md).

A missed reference stays missed: the grammar reads what is written the way associations write it, and a model reading one section at a time can add the prose references ("the rules adopted by the Board") later.

`jason outlines --model` is that model. It reads one section's own words at a time (`--model-doc owners-manual` or `--model-doc bylaws#7.2`, repeatable; `--model-limit`, 20 by default) with the shared local model, after `preflight`, under the GPU lock, and only through Ollama on this machine. The prompt lists every outlined document by key with its title and the names other documents use for it, the grammar's naming rules, and a few worked examples, and the answer is held to a JSON schema: the kind of target, the target, a short quote, and the relation. A proposal is kept only when its quote is in the section, compared without regard to case, spacing, or the style of quotation marks and dashes; anything else is dropped and counted. A kept target is named the grammar's way (an alias becomes its key, "the Davis-Stirling Act" is CIV 4000, a name on no list stays `named:` with its words), and one the grammar already found in the same section is not new. What is new goes to `data/outlines/model/references.json`, marked `method: model` with the words the model quoted, never into the grammar's `references.json`: it is a lead a person reads. A section read before with the same words is skipped unless `--model-again`.

## Ordering the copies the records lack

`jason records-request` writes `data/reports/records-request.md` and `.csv`: every instrument the association's record names (the governing instruments, the association's own liens and releases, the liens and notices against it, the construction-period claims) with no recorded copy on disk, with what the county's order form asks for and what the copy costs. A copy on disk is one whose stamp names the instrument, whose file name prints the number, or that a Drive pin names. Each row carries the document number, the book and page (for a twelve-digit number, the first eight digits and the last four), the recording date, the title the index prints, what the instrument is, why the association wants it, the page count (from the stamp, the cached detail, or an estimate marked with an asterisk; `--pages` reads counts from the index now), plain or certified, and the cost at the county's fees: a plain copy $8.00 for the first page and $1.00 for each further page, a certified copy $9.00 and $1.00, as the county's page read on 2026-09-28. The declaration and its amendments are asked certified; a rescinded instrument is asked plain for the file. The order form, the mailing address, the fax, and the phone are on the page. The `records_request` tool returns the same rows.
