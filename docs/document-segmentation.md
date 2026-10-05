# Document segmentation

**Status:** October 5, 2026. Built: the records, the rule pass, the vision-model and embedder readers (both off by default), the part finder, the store, `jason segments`, and the measurement script. Measured on a labeled set of real scans (below). Open: [what remains](#what-remains).

Ingestion is readings ([ingestion-and-review.md](ingestion-and-review.md)). Segmentation is one more ingestion reading: it needs only the file, gives the same result for the same bytes, and judges nothing against the law or the profile. It answers two questions the rest of the pipeline kept assuming away.

1. **Which documents does this file hold?** One scan is often several documents: a stack of recorded instruments, a board packet (minutes, invoices, reports), a vendor's batch, a records binder. A file read as one document gets one kind, one date, and one set of parties, none of them right for most of its pages.
2. **Which parts does this document hold that matter on their own?** The owner's manual holds the rules and regulations, policies, forms, and exhibits. Bylaws can hold an exhibit on dispute resolution; a packet holds its minutes. A citation to "the Rules" should reach the part of the manual that is the rules, and not the guide around it.

The source file is never split or rewritten. A **segment** is a page range of it, and a **part** is a titled page range inside a segment. Both are readings kept beside the file's text, keyed by its SHA-256, and a reading of other bytes is stale.

## The records

Code: `jason.community.document_segments` (pure: it reads no file, model, or profile) and `jason.tasks.segments` (the PDF, the models, the store). The command is `jason segments` ([cli.md](cli.md)).

| Record | What it holds |
|---|---|
| `PageInfo` | One page's features: size, whether it has words, its first and last lines with their place and type size, its running header and footer, its opening and closing words, its most frequent content words. Kept in the reading, so the rules run again without the file. |
| `Boundary` | A page some reader says starts a document: the readers that said so, the rule score and the cues that made it, the model's probability, the embedder's cosine, and the tier. |
| `Segment` | Pages `start` to `end`, a title, a kind (a `DocumentKind` value, from the same chain the library uses), a date, parties, how it begins, its tier and readers, a confidence, and the blank pages at its end. |
| `Part` | A key (a slug, unique in the file), a title, a `PartKind`, pages, the **anchor** (the heading it starts at) and the **end anchor** (the next part's heading), how it was found, the book its title names (`books.book_named`), and the segment it is in. |
| `Segmentation` | The file's id and SHA-256, the readers and options used, every candidate boundary, the segments, the parts, and the pages. |

A segment's kind is classified the way the library classifies a file: the profile's name rules over the segment's title (`Community.classify_document`), then jason's phrase rules over its opening words (`content.classify_text`). A miss stays a miss: the kind is "".

### Addresses

A segment or a part is named like a library document, with a fragment ([record-addresses.md](record-addresses.md), [console/doc-component.md](console/doc-component.md)).

| Address | Names |
|---|---|
| `library:ID` | the whole file |
| `library:ID#p3-7` | pages 3 to 7 (`#p3` one page); a page range is always valid, whether or not a reading has found it |
| `library:ID#seg=s2` | the second segment of the stored reading |
| `library:ID#part=rules` | a part, by its slug |

`address`, `parse_address`, and `resolve` do the forms. A file the library does not hold is stored under `sha-` and the first sixteen hex digits of its SHA-256; when it is ingested it keeps its library id and the stored reading can be copied across. A segment or part address names pages, so it holds for any text of the same file; a part's *anchor* is what finds it again in a text with other offsets (an outline, an OCR, a Google Doc).

## The signals

The rule pass is a table, `document_segments.CUES`: each row a signal in the page, its weight, and which way it points. A page starts a document when its cues sum to `THRESHOLD` (0.8). A new signal is a new row. None of them is one association's.

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
| `exhibit-label` | -1.0 | opens with an exhibit or appendix label |

Rules that matter more than any one weight:

- **Blank pages are transparent.** A page is read against the last page with words. A duplex scan has blank backs everywhere, so where more than a quarter of the pages are blank the blank is no cue at all (`DUPLEX`); where blanks are rare, one is a separator and counts. A blank page is never a boundary, and it belongs to the segment before it.
- **Pleading paper is not numbering.** A column of line numbers down the margin is dropped from the lines, and a bare number on such a page is not a page number.
- **A running line needs a run.** A footer or header is "changed" only when the page before matched the one before it, or this page matches the next. OCR varies a running line a little, so only a plain difference counts; a likeness of 0.8 or more is the same line.
- **A page of another size is one page** unless the next keeps the size (a landscape map inside a document).

### Readers and tiers

| Reader | What it is | On by default |
|---|---|---|
| `rules` | the cue table above | yes |
| `model` | the local vision model (`qwen3.5:9b`) shown the page's thumbnail, asked "is this the first page of a new document?", scored from the probabilities of Y and N in its `top_logprobs` (as `OllamaTextCorrector.choose` scores a letter). It runs after `local_ai.preflight`, holds the GPU lock, and is unloaded after. | no: `--model` |
| `embedding` | the cosine of adjacent pages' vectors (`qwen3-embedding:8b`); a low one is the cue `embedding-change` | no: `--embed` |

Ollama returns `logprobs` with an image in the request (checked October 5, 2026), so the model's answer is a number, and the threshold is a setting. Two readers agreeing make a boundary `LIKELY`; one alone is `SUGGESTED`, the same tiers as OCR correction ([ocr-correction.md](ocr-correction.md)). `--accept` keeps any reader's boundary (`any`, the default), only those two readers share (`agree`), or the rules' alone (`rules`). Every candidate is stored with the readers that proposed it, so a later run can change what it keeps without reading again.

## The parts

A part starts at a **mark**, and the best evidence on a page wins:

| Mark | Found from |
|---|---|
| exhibit label | a line "Exhibit A", "Appendix 1", "Schedule 2", "Attachment 3" at the top of a page; two labels with different letters are two parts |
| running header | a header line that is the same on three or more pages in a row ("QUESTIONS & ANSWERS") |
| title | a line at the top of the page with a part word (`PART_RULES`: rules, policy, procedure, form or application, notice, minutes, agenda, contents, guidance) that is set big, or alone in capitals, bold, or centered; the first line of the page counts most |
| bookmark | the file's own top-level bookmarks whose title names a part (weaker than a title on the same page: a bookmark may name a section of the part) |
| contents | a "Title ..... 12" line on a contents page, kept only where the title is found on that page or the next three |
| cover | the front of a segment before its first mark, when the first page has under 100 words |
| after contents | the page after a contents part's dot leaders end |

A title that repeats on the next page is one mark; a part ends the page before the next, less its trailing blank backs; a contents part ends where its dot leaders do; a part that is the whole segment says nothing the segment does not and is left out. `Part.book` is set only where the canon knows the title: "Rules and Regulations" is `rules`; a title it does not know stays unbooked, a miss. The owner's manual's parts are the first test case ([mystique/docs/document-segments.md](../mystique/docs/document-segments.md)).

### Parts and the manual's sections

`jason manual` classifies the manual's *sections* (`SectionKind`: rule, copy, policy, guidance, mixed) from the outline, by the profile's rows. A part is the coarser, page-level cut under it: the pages of the rules, the pages of a policy bound in, the pages of a form. They agree where they overlap, and neither replaces the other. `Part.outline` is the field for the outline sections a part holds, once an outline is matched to a part's anchors; it is empty until then.

## How a citation scopes to a part

1. **By book.** `tasks.segments.parts_in_store(data_dir, book="rules")` lists the parts that name the rules, each with the stored reading it is in. A citation to "the Rules" of the manual resolves to the part, not the file.
2. **By pages.** `text_of_pages(pdf, part.start, part.end)` is the words of the part from the PDF's own layer.
3. **By anchors, in any other text of the file.** `part_span(part, text)` finds the part in an outline's text, an OCR, or a Google Doc: from its anchor heading to its end anchor, in the stream of letters and digits (spacing, punctuation, and case ignored). It returns None where the anchor is not found, and a miss is a miss. Pass the text of the segment where a heading repeats.
4. **A passage the other way.** `locate(seg, snippet, page_texts)` says which page, segment, and part another reading's passage is in, so a passage index row can be tagged and a search or citation filtered by `part`.

Reciting a rule from the manual still follows "Recite the rule; label the reading": the part says where the words are, and the recital quotes the stored words of those pages. A reading of the part's kind or book is evidence, never a pin.

## How the index and collections use it

Not built; this is the design, and the pieces above are what it calls.

- **The passage index** gets two nullable columns on a library file's rows, `segment` and `part`, set by `locate`. `document_search` and `passage_search` take them as filters, and a scoped citation passes the part's key. A confidential flag is still decided per file, never per segment.
- **A collection** (a legal case, a vendor, a meeting) can name a segment of a file by address (`library:ID#seg=s2`) instead of the whole combined file, so a board packet's minutes are a member of the meeting's collection and its invoices are members of the vendors'. A document in two collections is still ingested once.
- **Readings** (`jason models`) are per segment: a segment's kind picks the reader, and its pages are the text the reader reads. A combined file read whole gets one kind; read by segment it gets one per document.
- **Folding copies** ([programs.md](programs.md), "three copies of one document not folded"): two scans of one document fold by text digest; a segment inside two different binders folds the same way, by the digest of its pages' words.

## Measured

The gold set is a private labeled set of real scans (`data/library/segments-gold.json`; the labels are page numbers only, in no tracked file). The files are three batches of mixed documents scanned together, 41 PDFs and 2,200 pages, each with the scanner's own text layer. 31 files were labeled (some in part: a window of pages), 1,946 pages: recorded instruments and the association's governing documents with exhibits, public reports, a developer's court filings on pleading paper, fax and web-page printouts, a financial packet of one-page reports each numbered page 1, plan sets on alternate sheets, and a duplex stack with blank backs to page 145. A file's labels are the first page of each document (a page with words), ambiguous pages marked "maybe" (a prediction there counts neither way), and the parts.

**Split.** The cues and the threshold were set on the dev files (21 files, 77 labeled starts after leaving out each file's first page) and measured once on the held-out files (10 files, 79 starts) before the held-out errors were read. The held-out figures below are from that first measurement; the rules changed after it from reading the held-out errors, so a later measurement on those files is no longer held out.

{{MEASURED}}

**What the measurements say.**

{{SAYS}}

### Where a preflight step would change these figures

The measurements read each file as it is: the scanner's text layer and the page images, with blank pages as pages with no words. A preflight (blank removal, greyscale or black-and-white conversion, deskew, a cleaner OCR) would change them:

- **Blank removal** changes nothing in the rules (blank pages are already skipped), but it removes the signal where blanks are rare (`after-blank`, a separator between documents) and makes the duplex test (`DUPLEX`) unusable, since the share of blanks is read from the file. Run segmentation before blank removal, or keep the blank count.
- **A cleaner OCR** would change the cues that read words: the title cues, the page labels, the recorder's stamp, the dates. The scanner's layer misreads titles in many files (a plan sheet's title read as "CONDOJ\IIINIUJ\II PLAN"), and every such page loses a cue. The text-layer-based figures are a floor.
- **Deskew** moves lines a little and changes the header and footer test only if a skewed page puts its footer outside the bottom band.
- **The thumbnail** the model sees is the page image as scanned; a black-and-white conversion would change what it sees.

## What remains

- **The vision model's prompt** was tried in two forms (the page alone; the page and the one before). A prompt that names the genre of the file, or shows the page's first lines of text with the image, may do better, and costs the readers their independence.
- **A third reader on layout**: line widths, the margin's ink, and the share of a page that is a table or a figure are signals the text layer does not carry. A scanned page's image features (a letterhead's logo, a fax header) are only in the pixels.
- **Parts by outline.** A part's `outline` field is empty: matching an outline's sections (the manual's `ManualRow` locators) to a part's anchors is the bridge to the section-level classification.
- **The profile's words.** `PART_RULES` is a general table; a profile may need its own part words (a policy called by its own name). That is a `Community` method with an empty default, not yet added.
- **The passage index's columns** and `document_search` filters ([above](#how-the-index-and-collections-use-it)), and a read-only MCP tool over the stored readings.
- **Duplicates.** Two scans of one document, and a document in two binders, are not folded by segment yet.
- **Page order.** A scan whose pages were fed out of order (two documents interleaved) reads as many short documents.
- **Library ids.** A stored reading of a file the library did not hold is under `sha-...`; copying it to the library id on ingest is not built, and `jason ingest` does not call segmentation. Run `jason segments ID` on a combined file after ingest.
