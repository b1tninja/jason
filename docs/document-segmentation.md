# Document segmentation

**Status:** October 5, 2026. Built: the records, the walk down the pages with a stack of open documents, the rule pass, the vision-model and embedder readers (both off by default), the part finder, the store, `jason segments`, and the measurement script. Measured on a labeled set of real scans (below). Open: [what remains](#what-remains).

Ingestion is readings ([ingestion-and-review.md](ingestion-and-review.md)). Segmentation is one more ingestion reading: it needs only the file, gives the same result for the same bytes, and judges nothing against the law or the profile. It answers two questions the rest of the pipeline kept assuming away.

1. **Which documents does this file hold, and which are inside which?** One scan is often several documents: a stack of recorded instruments, a board packet (minutes, invoices, reports), a vendor's batch, a records binder. A document can sit inside a document: an exhibit inside an instrument, a report inside a packet. A file read as one document gets one kind, one date, and one set of parties, none of them right for most of its pages.
2. **Which parts does this document hold that matter on their own?** The owner's manual holds the rules and regulations, policies, forms, and exhibits. Bylaws can hold an exhibit on dispute resolution. A citation to "the Rules" should reach the part of the manual that is the rules, and not the guide around it.

The source file is never split or rewritten. A **segment** is a page range of it, and a **part** is a titled page range inside a segment. Both are readings kept beside the file's text, keyed by its SHA-256, and a reading of other bytes is stale.

## The tree

Segments are a **tree**, not flat page ranges. Each has a parent (none at the top) and children. A page belongs to the innermost open segment. A segment's page range is absolute in the file and **includes its children's**: a packet that spans pages 1 to 40 and holds a report on pages 12 to 19 has the range 1-40 and its own pages (`runs`) 1-11 and 20-40. A document is inside another exactly when the other has pages both before and after it, or when it is an exhibit (or appendix, attachment, schedule) of it, or when the other's cover lists it.

The tree is made by walking the pages with a **stack of open documents**. Each level of the stack keeps what it expects next: its next page number (and its total, "of N"), its running header and footer, its page size and type, and the words of its last page. At each page the walk makes one of four moves:

| Move | When | Signals (and which level) |
|---|---|---|
| **continue** the top | nothing breaks | the top's page number follows, the same header and footer, the same layout; "Page n of N" not yet at N |
| **push** a new document inside the top | a first page, and the top is still open ("Page n of N" has not reached N), or an exhibit label | the first-page cues (below); an exhibit label ("Exhibit A", "Attachment 1"); numbering that restarts while the top's has stopped |
| **pop** back to an outer document | an outer document's own continuation returns | its page number resumes (the next number, the same total), with its header and footer or its words; or the inner one ends |
| **new top-level** | none of the open documents continues, and the first-page cues are there | the first-page cues |

- **Every level below the top is checked**, not only the parent: a page can close two levels at once. In the made-up test file an agreement of eight numbered pages holds a report (its own numbering and header) that holds an exhibit; the agreement resumes at its page 4, and that page closes the exhibit and the report together (`Move.closed`).
- **A pop needs more than a look.** An open level (one on the stack) resumes on its page number, its header and footer, or its words (a score of 1.6, and 0.8 more than the open document's own claim on the page). A document that closed earlier resumes only on its page number and its look together: a form printed twice looks the same both times, and numbering alone is noisy in a scan.
- **A document closed between the pages of another is inside it, even when it was first read as a sibling.** The walk first reads a new document that does not interrupt anything as a sibling; when an earlier document's next page comes back, the documents started since are re-parented under it.
- **An exhibit is always a child** of the document it follows (the nearest enclosing document that is not an exhibit), whether or not that document has pages after it; the next exhibit is its sibling. An exhibit has a `label` ("Exhibit A"), `aliases` ("Ex. A"), and the title on the line under the label.
- **A cover that lists its documents is their parent** ("Included Reports: Balance Sheet, Aging of Accounts ..."): a document of up to three pages that says it lists ("included", "enclosed", "contents", "packet") and names at least three of the documents that follow, from one of the first two, with no more than one unnamed between.
- **Blank pages are transparent.** They belong to the segment that was open, and a page is read against the last page with words.

Each move is logged (`Move`: the page, the kind, the segment it ends in, the segments it closed, the signals that decided it, the readers, the tier), except continues. `jason segments --moves` prints the log.

## The records

Code: `jason.community.document_segments` (pure: it reads no file, model, or profile) and `jason.tasks.segments` (the PDF, the models, the store). The command is `jason segments` ([cli.md](cli.md)).

| Record | What it holds |
|---|---|
| `PageInfo` | One page's features: size, whether it has words, its first and last lines with their place and type size, its running header and footer, its opening and closing words, its most frequent content words. Kept in the reading, so the rules run again without the file. |
| `Boundary` | A page some reader says breaks: the readers that said so, the rule score and the cues that made it, the model's probability, the embedder's cosine, and the tier. Whether the break is a new document or an outer one returning is the walk's to say. |
| `Move` | One move of the walk (above). |
| `Segment` | Key (`s2` is the second top-level document, `s2.1` the first inside it), pages `start` to `end` (absolute, children included), `runs` (its own pages), `parent`, `role` (document or exhibit), `label` and `aliases`, a title, a kind (a `DocumentKind` value, from the same chain the library uses), a date, parties, how it begins (`move`, `basis`), its tier and readers, a confidence, and the blank pages at its end. |
| `Part` | A key (a slug, unique in the file), a title, a `PartKind`, pages, the **anchor** (the heading it starts at) and the **end anchor** (the next part's heading), how it was found, the book its title names (`books.book_named`), aliases, and the **innermost segment** that holds its first page. |
| `Segmentation` | The file's id and SHA-256, the readers and options used, every candidate boundary, the segments (the tree, in page order), the parts, the moves, and the pages. `children_of`, `parent_of`, `ancestors_of`, `path`, `segment_at` (the innermost segment for a page), `chain_at` (the whole stack at a page). |

A segment's kind is classified the way the library classifies a file: the profile's name rules over the segment's title (`Community.classify_document`), then jason's phrase rules over its opening words (`content.classify_text`). A miss stays a miss: the kind is "".

### Addresses

A segment or a part is named like a library document, with a fragment ([record-addresses.md](record-addresses.md), [console/doc-component.md](console/doc-component.md)).

| Address | Names |
|---|---|
| `library:ID` | the whole file |
| `library:ID#p3-7` | pages 3 to 7 (`#p3` one page); a page range is always valid, whether or not a reading has found it |
| `library:ID#seg=s2` | the second top-level document of the stored reading |
| `library:ID#seg=s2/s2.1` | the first document inside it: **a nested segment shows its path**; its pages stay absolute in the file (`resolve` gives them) |
| `library:ID#part=SLUG` | a part, by its slug |

`address`, `parse_address`, `seg_path`, and `resolve` do the forms (`s2.1` alone parses too). A file the library does not hold is stored under `sha-` and the first sixteen hex digits of its SHA-256; when it is ingested it keeps its library id and the stored reading can be copied across. A segment or part address names pages, so it holds for any text of the same file; a part's *anchor* is what finds it again in a text with other offsets (an outline, an OCR, a Google Doc).

## The signals

The first-page cues are a table, `document_segments.CUES`: each row a signal in the page, its weight, and which way it points. A page breaks when its cues sum to `THRESHOLD` (0.8). A new signal is a new row. None of them is one association's.

| Cue | Weight | The page ... |
|---|---|---|
| `page-one` | +1.5 | is numbered 1 or "1 of N" |
| `one-page-document` | +1.0 | says "page 1 of 1": the next page is another document |
| `page-one-again` | +1.0 | is numbered 1 and so is the page before |
| `numbering-reset` | +1.2 | restarts its number, changes its total ("of N"), or changes the style (roman to arabic) |
| `recording-stamp` | +1.5 | opens with a recorder's request or stamp |
| `title-block` | +1.0 | opens with a title that has a document-kind word and is set bigger than the body |
| `title-caps` | +0.7 | opens with such a title, alone in capitals |
| `title-soft` | +0.35 | opens with such a title, short and bold or centered |
| `letter-head` | +0.9 | opens with a date and an addressee, or a date and a letterhead |
| `addressee` | +0.5 | opens with "To:", "Dear", "Re:" |
| `footer-change` / `header-change` | +0.8 / +0.6 | has a running footer or header that stops or starts (a first line that merely differs is not a header) |
| `size-change` | +0.9 | is another size or orientation, and the next page keeps it |
| `font-change` | +0.4 | is set in another type |
| `after-closing` | +0.4 | follows a signature, a notary's block, or a total |
| `after-blank` | +0.6 | follows a blank page, where blanks are rare |
| `lexical-break` | +0.3 | shares few words with the page before |
| `embedding-change` | +0.6 | is about something else than the page before, by the embedder |
| `mid-sentence` | -1.2 | begins in the middle of a sentence |
| `continued` | -1.2 | says "(continued)" |
| `number-continues` | -1.1 | is numbered after the page before |
| `same-title` | -0.8 | has the page before's title (a running title) |
| `same-header` / `same-footer` | -0.6 / -0.5 | has the page before's running line |
| `lexical-flow` | -0.4 | shares many words with the page before |
| `contents-page` | -1.0 | is a table of contents, or a leaf of one |
| `exhibit-label` | -1.0 | opens with an exhibit or appendix label (an exhibit is pushed by the walk, not read as a new document) |

Rules that matter more than any one weight:

- **The duplex scan.** Where more than a quarter of the pages are blank the blanks are backs, and the blank is no cue (`DUPLEX`); where blanks are rare, one is a separator and counts. A blank page is never a break.
- **Pleading paper is not numbering.** A column of line numbers down the margin is dropped from the lines, and a bare number on such a page is not a page number.
- **A running line needs a run.** A footer or header is "changed" only when the page before matched the one before it, or this page matches the next. OCR varies a running line a little, so only a plain difference counts; a likeness of 0.8 or more is the same line.
- **A page of another size is one page** unless the next keeps the size (a landscape map inside a document).

### Readers and tiers

| Reader | What it is | On by default |
|---|---|---|
| `rules` | the cue table above, and the walk | yes |
| `model` | the local vision model (`qwen3.5:9b`) shown the page's thumbnail and asked "is this the first page of a new document?", scored from the probabilities of Y and N in its `top_logprobs` (as `OllamaTextCorrector.choose` scores a letter) | no: `--model` |
| `model`, the move | for each move the walk made but a continue, the model is shown the page before and the page and asked the move as a **closed choice** against the stack: A continue the innermost open document, B a new document inside it, C a new top-level document, D, E, F back to the outer document named (the nearest first). The probabilities of the letters are its reading (`Move.model`); a move is `LIKELY` where its most probable letter is the rules' move and at least 0.5, else `SUGGESTED`. | with `--model` |
| `embedding` | the cosine of adjacent pages' vectors (`qwen3-embedding:8b`); a low one is the cue `embedding-change` | no: `--embed` |

Both model readings run after `local_ai.preflight`, hold the GPU lock, and unload the model after. Ollama returns `logprobs` with an image in the request (checked October 5, 2026), so the model's answer is a number, and the threshold is a setting. Two readers agreeing make a boundary or a move `LIKELY`; one alone is `SUGGESTED`, the same tiers as OCR correction ([ocr-correction.md](ocr-correction.md)). `--accept` keeps any reader's break (`any`, the default), only those two readers share (`agree`), or the rules' alone (`rules`).

## The parts

A part starts at a **mark**, and the best evidence on a page wins. Parts are read from a segment's **own** pages (what its children hold is theirs), and a part belongs to the innermost segment that holds its first page.

| Mark | Found from |
|---|---|
| running header | a header line that is the same on three or more pages in a row ("QUESTIONS & ANSWERS") |
| title | a line at the top of the page with a part word (`PART_RULES`: rules, policy, procedure, form or application, notice, minutes, agenda, contents, guidance) that is set big, or alone in capitals, bold, or centered; the first line of the page counts most |
| bookmark | the file's own top-level bookmarks whose title names a part (weaker than a title on the same page: a bookmark may name a section of the part) |
| contents | a "Title ..... 12" line on a contents page, kept only where the title is found on that page or the next three |
| cover | the front of a segment before its first mark, when the first page has under 100 words |
| after contents | the page after a contents part's dot leaders end |

An **exhibit is not a part**: it is a child segment (`role` exhibit), so "Exhibit A" has its own pages, its own parts, and its own tree address. A title that repeats on the next page is one mark; a part ends the page before the next, less its trailing blank backs; a contents part ends where its dot leaders do; a part that is the whole segment says nothing the segment does not and is left out. `Part.book` is set only where the canon knows the title: "Rules and Regulations" is `rules`; a title it does not know stays unbooked, a miss. The owner's manual's parts are the first test case ([mystique/docs/document-segments.md](../mystique/docs/document-segments.md)).

### Parts and the manual's sections

`jason manual` classifies the manual's *sections* (`SectionKind`: rule, copy, policy, guidance, mixed) from the outline, by the profile's rows. A part is the coarser, page-level cut under it: the pages of the rules, the pages of a policy bound in, the pages of a form. They agree where they overlap, and neither replaces the other. `Part.outline` is the field for the outline sections a part holds, once an outline is matched to a part's anchors; it is empty until then.

## How a citation scopes to a part or an exhibit

Citation scoping ([rule-citations.md](rule-citations.md)) reads `jason.community.scoping.Part` rows: `document`, `anchor`, `through`, `book`, `label`, `aliases`, and, for a row from a reading, `source` ("segments"), `path`, `numbers`, `ref`, `pages`, and `kind`. `jason cite` reads the stored readings itself (`jason.tasks.cite_scope.segment_parts`, which also decides whether a reading may be used: the file in the library, its bytes unchanged, one top-level document, one outline's words), and `jason rules` reads them through `rule_authority.parts_from_segments`. `document_segments.scoping_parts(seg, document)` is the plain mapping from a reading:

- **A part** (the rules inside a manual): `document` is the **innermost document that holds it** (a segment key, which the caller maps to its own document key with `document=`), `anchor` the heading it starts at, `through` the heading it runs up to, `book` the book its title names, `label` its title, and `aliases` the other ways the title is written ("B. Community Regulations" and "Community Regulations").
- **A nested exhibit** (a labeled child): "Exhibit A" cited inside the instrument means that child, so the child's own key is the `document`, its label ("Exhibit A") the `label`, its aliases ("Ex. A") the `aliases`, and the book its title names, where the canon names one, the `book`. **A part inside an exhibit is the exhibit's**, not the instrument's. A nested part's `book` and aliases join the index's names, so "Exhibit A" and "the Rules" scope a citation to the child or the part.

The words themselves:

1. **By book.** `tasks.segments.parts_in_store(data_dir, book="rules")` lists the parts that name the rules, each with the stored reading it is in. A citation to "the Rules" of the manual resolves to the part, not the file.
2. **By pages.** `text_of_pages(pdf, part.start, part.end)` is the words of the part from the PDF's own layer.
3. **By anchors, in any other text of the file.** `part_span(part, text)` finds the part in an outline's text, an OCR, or a Google Doc: from its anchor heading to its end anchor, in the stream of letters and digits (spacing, punctuation, and case ignored). It returns None where the anchor is not found, and a miss is a miss.
4. **A passage the other way.** `locate(seg, snippet, page_texts)` says which page, segment, and part another reading's passage is in, so a passage index row can be tagged and a search or citation filtered by `part`.

Reciting a rule from the manual still follows "Recite the rule; label the reading": the part says where the words are, and the recital quotes the stored words of those pages. A reading of the part's kind or book is evidence, never a pin.

## How the index and collections use it

Not built; this is the design, and the pieces above are what it calls.

- **The passage index** gets two nullable columns on a library file's rows, `segment` and `part`, set by `locate`. `document_search` and `passage_search` take them as filters, and a scoped citation passes the part's key. A confidential flag is still decided per file, never per segment.
- **A collection** (a legal case, a vendor, a meeting) can name a segment of a file by address (`library:ID#seg=s2/s2.1`) instead of the whole combined file, so a board packet's minutes are a member of the meeting's collection and its invoices are members of the vendors'. A document in two collections is still ingested once.
- **Readings** (`jason models`) are per segment: a segment's kind picks the reader, and its own pages (`runs`) are the text the reader reads. A combined file read whole gets one kind; read by segment it gets one per document.
- **Folding copies** ([programs.md](programs.md), "three copies of one document not folded"): two scans of one document fold by text digest; a segment inside two different binders folds the same way, by the digest of its pages' words.

## Measured

The gold set is a private labeled set of real scans (`data/library/segments-gold.json`; the labels are page numbers only, in no tracked file). The files are three batches of mixed documents scanned together (41 PDFs, 2,200 pages, each with the scanner's own text layer), the owner's manual (two copies), and two packets from the library (a treasurer's report and an annual disclosure package). 35 files were labeled, some in part. They hold recorded instruments and the association's governing documents with exhibits, public reports, a developer's court filings on pleading paper, fax and web-page printouts, a financial packet of one-page reports each numbered page 1, plan sets on alternate sheets, a duplex stack with blank backs to page 145, and two cover-led packets. A file's labels are the first page of each document (a page with words; nested documents too, exhibits not), ambiguous pages marked "maybe" (a prediction there counts neither way), each nested document with its parent and end, each page where an outer document resumes, and the parts.

**Split.** The cues and the threshold were set on the dev files and measured on the held-out files. The held-out figures were looked at: the first measurement of the flat model on 10 held-out files is reported below, and the rules (the numbering and size cues, the nesting rules) changed after the held-out errors were read, so a later measurement on those files is no longer held out. The nesting rules were written after the nesting labels were, and tuned on both splits.

Boundary figures are the first pages of documents (the first page of each file left out), exact; within one content page they are the same or a point higher. Measured October 5, 2026, model qwen3.5:9b at 72 dpi, model threshold 0.8, cue threshold 0.8.

| Split | Reader | Labeled starts | Precision | Recall | F1 |
|---|---|---|---|---|---|
| dev (21 files) | rules | 77 | 0.915 | 0.844 | 0.878 |
| dev | model alone | 77 | 0.719 | 0.896 | 0.798 |
| dev | rules and model agree | 77 | 1.000 | 0.753 | 0.859 |
| dev | either | 77 | 0.697 | 0.987 | 0.817 |
| held-out (12 files) | rules | 129 | 0.835 | 0.783 | 0.808 |
| held-out | model alone | 129 | 0.346 | 0.822 | 0.487 |
| held-out | rules and model agree | 129 | 0.888 | 0.674 | 0.767 |
| held-out | either | 129 | 0.365 | 0.930 | 0.524 |

**Nesting** (counts; the tree from the rules' breaks, within one content page):

| Split | Labeled nested documents | Found | Right parent | Right end | Extra nested | Resumes popped at the right page |
|---|---|---|---|---|---|---|
| dev (5 files) | 11 | 11 | 9 | 11 | 1 | 0 of 0 |
| held-out (8 files) | 33 | 31 | 13 | 24 | 50 | 0 of 2 |

**Parts** (the owner's manual and files with contents pages): dev 15 labeled, anchor 0.93, span within one page 0.87; held-out 10 labeled, anchor and span 1.00 (the manual's second copy, which has the same layout as the first).

**Model time:** 0.2 to 0.6 s a page for the first-page question at 72 dpi (3.3 s for a pair of pages); 2.2 s a move for the closed choice on the stack.

**What the measurements say.**

- **The rules carry the first-page question.** The vision model leans to "yes": at 0.8 it finds nearly every start and about as many false ones again on dev, and two to three times as many on the held-out files (long, uniform packets where every page has a title). Alone it is a suggestion. Where it agrees with the rules the precision is 0.89 to 1.00 and the recall falls 9 to 11 points, so agreement is the `LIKELY` tier and not a way to find more boundaries.
- **The closed choice on the stack did not work.** Asked "continue, new inside, new top-level, or back to an outer document", the model answered "new inside" for every move on the dev files, whatever the page. It adds nothing to the walk but a disagreement mark where its top letter differs, and that mark is uninformative until a prompt that works is found.
- **Exhibits and covers nest well; the real resumes are rare.** Every labeled exhibit was found with its parent on dev (9 of 11 parents right, the two wrong when a maybe-page split the parent; every end right). On held-out the labeled packets with covers are found, but the walk reads many more documents inside the large packets than were labeled (50 extra nested, nearly all inside the 156-page treasurer's report and the 213-page duplex binder, where only the first level was labeled), and the parent is right for 13 of 33. The only real file with an outer document that resumes (scanner-interleaved pages) is missed: the notice's pages sit among the order's, but the order's footer is not a page number the labels follow, so the pop is not seen. The pop is measured only by the made-up files.
- **The held-out figures are lower** than dev for every reader. The rules were tuned on dev and then changed after reading the held-out errors, so the held-out figure is a floor of what a fresh file would give only in direction, not in size.

### Where a preflight step would change these figures

The measurements read each file as it is: the scanner's text layer and the page images, with blank pages as pages with no words. A preflight (blank removal, greyscale or black-and-white conversion, deskew, a cleaner OCR) would change them:

- **Blank removal** changes nothing in the rules (blank pages are already skipped), but it removes the signal where blanks are rare (`after-blank`, a separator between documents) and makes the duplex test (`DUPLEX`) unusable, since the share of blanks is read from the file. Run segmentation before blank removal, or keep the blank count.
- **A cleaner OCR** would change the cues that read words: the title cues, the page labels (the pop and push evidence rests on them), the recorder's stamp, the dates. The scanner's layer misreads titles in many files (a plan sheet's title read as "CONDOJ\IIINIUJ\II PLAN"), and every such page loses a cue. The text-layer-based figures are a floor.
- **Deskew** moves lines a little and changes the header and footer test only if a skewed page puts its footer outside the bottom band.
- **The thumbnail** the model sees is the page image as scanned; a black-and-white conversion would change what it sees.

## What remains

- **Resume cases are rare in the archive.** Of the real files, one (a file whose pages the scanner interleaved) has an outer document that resumes. The pop is exercised by made-up files (an exhibit and a report closed by one page) and measured on that one file; a board packet with embedded minutes, or a manual with an embedded policy that the manual resumes after, would measure it better.
- **A cover is a parent only when it lists.** A document that holds another with no resume, no exhibit label, and no list of its contents is a sibling.
- **The vision model's prompts** were tried in two forms for the first-page question (the page alone; the page and the one before) and one for the move. A prompt that names the genre of the file, or shows the page's first lines of text with the image, may do better, and costs the readers their independence.
- **A third reader on layout**: line widths, the margin's ink, and the share of a page that is a table or a figure are signals the text layer does not carry.
- **Parts by outline.** A part's `outline` field is still empty. Citation scoping bridges a part to the outline's sections itself, by heading (`part_span` over the outline's text, stopping at an exhibit), as `Part.numbers`; matching the manual's `ManualRow` locators to a part's anchors is the bridge to the section-level classification.
- **One outline per file.** Citation scoping and rule authority use a reading only for a file of one top-level document that one outline is the words of (`cite_scope.bind_outline`). A stack of documents has no outline per segment to bind; reading the outlines by segment (a page range) is what would use those readings.
- **A section inside an exhibit** cannot be cited: an exhibit has no outline, so "Section 3 of Exhibit A" is a miss, never the document's own section 3.
- **The profile's words.** `PART_RULES` is a general table; a profile may need its own part words. That is a `Community` method with an empty default, not yet added.
- **The passage index's columns** and `document_search` filters ([above](#how-the-index-and-collections-use-it)), and a read-only MCP tool over the stored readings.
- **Duplicates.** Two scans of one document, and a document in two binders, are not folded by segment yet.
- **Library ids.** A stored reading of a file the library did not hold is under `sha-...`; copying it to the library id on ingest is not built, and `jason ingest` does not call segmentation. Run `jason segments ID` on a combined file after ingest.
