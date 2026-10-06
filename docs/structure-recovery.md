# Recovering a document's structure from its PDF

A Google Doc that the association keeps well formatted is the one place where a document's structure is plain: a heading is a paragraph in a named style, a section number is drawn from a list, a page break is an element. A PDF has none of that. It has glyphs at positions, and sometimes a text layer, bookmarks, and a contents page. This page is how jason measures, and learns, how much of the Doc's structure it can recover from the PDF alone, so that it can read an unknown PDF of rules from another association.

The method is a fuzzer in the way `jason form-fuzz` is ([form-fuzzer.md](form-fuzzer.md)):
- **Gold:** the Doc says what the structure is.
- **Variants:** its PDF is degraded in controlled steps, each step recorded.
- **Recovery:** a reader that sees only the PDF writes the structure it finds.
- **Score:** the recovery is compared with the gold, by degradation and by clue.

Code: `jason.community.structure_gold`, `structure_pdf`, `structure_fuzz`; the driver is `scripts/structure_fuzz.py`. The reader a caller uses on an unknown PDF is `structure_pdf.outline_from_pdf`.

## What jason already has

| Piece | What it gives this work |
|---|---|
| `outlines.outline_from_doc` | The Doc's sections with the numbers Docs draws from a list (glyph type and format of each nesting level). It keeps headings and numbered paragraphs only: no style facts, no tables, no page breaks, no headers. The gold reader goes further and keeps them. |
| `outlines.outline_from_text` | The text-only reader: lines that start with a section number, `ARTICLE n`, a lettered rule, or `(a)` under the last numbered section. It sees no type size, no bold, no position. It is the baseline the new reader must beat on a PDF, and its grammar is the numbering clue's. |
| `outline_labels.outline_from_ocr`, `outline_align` | The numbering grammar under OCR slips, the order labels come in, and a working copy that places what the grammar could not. They work on text. |
| `document_segments` | Lines with size, bold, and place (`Line`, `PageInfo`, `build_page`), the running header and footer of a page, printed page numbers (`label_of`), the part marks (`header_runs`, `title_marks`, `contents_marks`, `bookmark_marks`), and the nested case (a document inside a file of many). The new reader uses `build_page` and `header_runs` and does not copy them. |
| `pdf_preflight`, `page_prep` | Blank pages, rotation, skew, resolution, JBIG2 risk, the cleaned rendition, and the image operations (`binarize_global`, `flatten`, `rotate`, `components`). The variants reuse the operations. |
| `ocr.TesseractCli` | Words with boxes and confidences (`image_words`). In an image-only variant the word heights and positions stand in for the font data. |
| `form_scans.simulate` | A page turned, scaled, blurred, speckled, and JPEG-compressed. The skew and noise variants call it. |
| `ocr_synth` | Text drawn, degraded, read back, and aligned with what was printed. The variants borrow its degradations. |
| `scripts/bench_offline.py` | The shape of an offline benchmark: no network, a cache folder, a bootstrap interval for a change. `structure_fuzz.py` has the same shape. |
| `jason.google` | `GoogleDocs.get` reads a Doc; `GoogleDrive.export_bytes` exports it as PDF. Both are read-only. Without a stored token the call raises `GoogleAuthRequired`; the benchmark never opens a browser. |

## The gold

`gold.json` holds the Doc's structure as nodes in reading order, with offsets into the Doc's text.

| Field | Meaning |
|---|---|
| `kind` | `heading`, `paragraph`, `list_item`, `table`, `page_break`, `header`, `footer` |
| `level` | A heading's level, from its named style (`HEADING_1` is 1, `TITLE` is 0 and a part's title) |
| `number` | The number as the Doc prints it: the list's rendered label ("8.5.", "c.", "(ii)") or the number the text itself carries ("ARTICLE 4", "B-12.") |
| `list_id`, `nesting` | The list the paragraph belongs to and its nesting level, which the Docs API gives and a PDF never does |
| `text`, `start`, `end` | The paragraph's words, without its list label, and where it sits |
| `size`, `bold`, `caps`, `indent`, `align` | The paragraph's style facts |
| `page` | The page of the paired PDF where the paragraph starts, found by reading the PDF's text layer in order |

The gold also lists the **parts** (a level-one heading that follows a page break, or a title), the running headers and footers the Doc sets, and the counts of tables and page breaks. The paired artifact is the Doc's own PDF export. Where the export cannot be fetched (no stored Google token, no network), a PDF already on disk is paired by text, or a PDF is drawn from the stored outline's text with PyMuPDF.

A stored outline (`data/outlines/KEY.json`) is a weaker gold: its headings, depths, and numbers, but no style facts and no page breaks.

## The degradation ladder

Each variant is a PDF plus a record of what was done (`variants.json`), so a score is attributed to a step.

| Variant | What is done |
|---|---|
| `clean` | The text-layer PDF as exported or drawn |
| `image300` | The text layer removed; each page is a 300 dpi image. Structure must come from OCR |
| `dpi200`, `dpi150`, `dpi110` | The same at lower resolution |
| `skew` | A 1.5 degree turn |
| `noise` | One percent of the pixels flipped |
| `shade` | Uneven shading across the page |
| `otsu` | Bilevel by one global threshold |
| `stencil` | Bilevel, then each character replaced by an earlier one of nearly the same shape: the way lossy JBIG2 substitutes a look-alike |
| `duplex` | A blank back after every page, with the faint show-through of a scanner |
| `shuffle` | Pages out of order (neighbours swapped, as a scanner that interleaves fronts and backs does) |
| `missing` | One page left out |
| `header` | The running header changed from the middle of the file |
| `combined` | The document placed inside a larger file between other made-up documents (the nested case) |

The record carries the dpi, the page map (gold page to variant page), the pages added or lost, and the seed.

## The clues

The reader reads cheap clues first; each is a row in `structure_pdf.CLUES` with a family, a weight, and a cost, so a run can leave any one out.

| Clue | Family | Needs | Reads |
|---|---|---|---|
| `bookmark` | outline | the file's own bookmarks | titles and levels |
| `toc` | contents | a contents page | each entry, verified against a heading in the body |
| `size` | typography | text layer or OCR heights | lines larger than the body, level by rank of size |
| `weight` | typography | text layer | short bold lines |
| `caps` | typography | any | short lines in capitals |
| `numbering` | numbering | any | the grammar: `1.`, `1.1`, `A.`, `B-12`, `(a)`, `Article`, `Section`, roman numerals |
| `spacing` | layout | line positions | a short line with air above and below |
| `indent` | layout | line positions | a centered or outdented short line |
| `sequence` | numbering | numbers read | a number that follows the one before it; a gap, a repeat, or a number out of order is a **finding**, kept as read |

Before the clues run, the running header and footer (a line in the top or bottom band that repeats down the pages) and the page numbers are taken out and kept: they are structure of their own (the page number, the part's name) and noise for the headings.

For an image-only variant the line's size is the height of its words in Tesseract's output, its place is the word boxes', and bold is not known, so `weight` has no vote.

**Tiers.** A heading is `likely` when two clues of different families agree, and `suggested` when one family made it. The reader never presents a heading that one family alone made as sure. A heading's level comes from the strongest evidence for it: a bookmark's level, a contents entry's indent, the depth of its number, or the rank of its type size.

**The model reader.** A local model may be a labeled second reader for headings the rules are unsure about (the page crop, a closed choice), behind `local_ai.preflight` and the GPU lock. It is off by default and the benchmark does not need it.

## The metrics

All of them are per variant, per clue set, and with a bootstrap interval where noted.
- **Heading precision, recall, and F1.** A recovered heading matches a gold heading when their texts (number removed, case and punctuation folded) are alike enough and the page is the same, allowing for the variant's page map. Each gold heading is matched once. The interval is a bootstrap over the headings.
- **Level accuracy.** Of the matched headings, how many have the gold's level; and within one level.
- **Numbering round trip.** Of the matched headings that print a number, how many have the number recovered exactly (case, punctuation, and spacing folded).
- **Parent and child.** Of the matched headings, how many have the gold's parent (the nearest heading of a shallower level).
- **Part boundaries.** The first page of each gold part against the parts found.
- **Page numbers.** Of the pages that print a number, how many the reader reads.
- **Ablation.** F1 with each clue left out, and with only that clue (with the numbering and sequence clues that the others need for a level); the difference is what the clue is worth.
- **OCR against text.** The gap between a clue set's F1 on the clean text-layer PDF and on the image-only one.

## Privacy

- The code and this page carry no heading, number, name, or Doc id of any association. Examples are made up.
- A gold file from a real Doc, its variants, and the readings are the association's records. They live under the folder `--cache` names (scratch, never the system drive) and are never tracked. The tracked docs carry counts only.
- A tracked test builds its own PDFs from invented text.

## Using the result

`outline_from_pdf(path)` returns the same `DocumentOutline` the other readers return, with the tier of each section beside it. It changes no stored outline: a caller chooses to use it. The findings (a gap in the numbering, a contents entry with no heading, a repeat) come back with it, for a person.
