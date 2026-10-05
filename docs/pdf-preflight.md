# Preflight for scanned PDFs: before OCR and ingestion

A box of scans arrives as PDFs whose pages are images, with a text layer a scanner program added, good or bad. Before OCR is spent on them, and before their text is trusted, `jason preflight FILE|FOLDER` looks at each page and file and reports what it finds. It also writes a **cleaned rendition** of the pages to read, kept in its own store, never in place of the original: the original is not rewritten, and a reading is evidence. Measured October 5, 2026.

Code: `jason.community.pdf_preflight` (the records, the checks, the cleaned rendition, the report), `jason.community.page_prep` (the image operations, numpy and Pillow only), `jason.community.pdf_media` (what a PDF carries), and `jason.commands.preflight` (the command). Tests: `tests/test_pdf_preflight.py`, which builds its PDFs from nothing.

```
jason preflight FILE|FOLDER                  the report (no change to anything)
jason preflight FOLDER --render --pdf        + cleaned page images and a clean.pdf in <data>/library/renditions/<id>/
jason preflight FILE --render --ocr          + Tesseract's reading of the rendition, with each word's box and confidence
jason preflight FILE --extract               + attachments and photographs saved by sha256 for `jason ingest`
```

## The checks

| Check | How | Where it shows |
|---|---|---|
| **Blank page** | ink after a threshold relative to the paper's own brightness, less specks, the scanner's edge shadow, and punch holes; the connected pieces of what is left; the text layer | `blank`: `content`, `blank`, or `marked` |
| **Near-blank page that matters** | a piece that may be a character (a size and a fill a scratch does not have), little ink with a text layer, a note that the page is left blank | `marked`, with the reason; kept, never dropped |
| **Orientation** | Tesseract's OSD (`--psm 0`) on the page drawn at 150 dpi; believed at confidence 5 or more | `rotation` (degrees clockwise to be upright) |
| **Skew** | a projection profile over the page's ink at trial angles | `skew` (degrees; positive when lines rise to the right) |
| **Resolution, codec, color** | the image's pixels over its placed width; its filter; its bits and a chroma test of the drawn page | `dpi`, `codec`, `colour` (bilevel, grey, colour) |
| **Placement tilt** | the angle the page's placement turns the image by | `ImageFact.tilt`: a scanner program that deskewed by placement leaves the pixels tilted |
| **JBIG2 coding** | the image dictionary's shared symbol table or quality setting | `ImageFact.risk`: symbol coding can swap a character for a look-alike (the 2013 "6 for 8" copier bug); the file does not say if it was lossless, so digits are checked against the paper when they matter |
| **Text-layer quality** | the share of the layer's words the English prior doubts (`lexicon.suspect`), with the file's own defined terms learned | `suspect_share`; a page over 3% is read again |
| **Defects** | shading (the paper's brightness range), dust (ink pixels with no inked neighbor), tilt | `uneven`, `speckle`, `skew`, and `steps`, what the cleaning would do |
| **What the PDF carries** | attached files, embedded images, form answers, actions, encryption | below |

### Blank pages

A page is **blank** only if it has no ink worth a mark (a share under 0.1%), no piece that may be a character, and no text layer (fewer than two letters or digits; one, with no character-like piece to match, is a scanner program's reading of dust). A page with a little ink or text is **marked**: a signature, a stamp, a page number or running head, a divider's title, a short text, or a note that it is left blank. Everything else is content, with a note when it has ink and no text layer. A blank page stays in the original and is left out of the rendition and the list to read; it is listed with its page number.

**Measured** on a box of 2,200 scanned pages, 354 of which had no text layer. Every page the detector could call blank has no text, so all 354 were labeled by eye from contact sheets (blank, near-blank that matters, content) before the detector's output was looked at, and 80 pages with text were labeled as well: 444 in all, 351 blank by eye.

| | Eye: blank | Eye: marked | Eye: content |
|---|---:|---:|---:|
| Detector: blank | 329 | 0 | 0 |
| Detector: marked | 22 | 7 | 0 |
| Detector: content | 0 | 6 | 80 |

Precision 329 of 329 (1.000), recall 329 of 351 (0.937), and **no page with anything on it called blank**. The 22 blank pages kept as marked were checked at the pixel level: each was dust, a hair, or the ring of a punch hole that passed for one character-like piece. The six marked pages kept as content were pleading pages and a signature page with 100 or more words of text; both are kept either way. The rules for holes, hairs, and dust were written after the first pass showed these misses (recall 0.917 before, 0.937 after), so recall is optimistic; precision and the zero were not tuned, as no rule was written to move a non-blank page. Synthetic checks (in the tests): 44 of 44 page numbers (8 to 12 point, centered, in a corner, in a head), stamps, and left-blank notes kept, clean and dirty; 37 of 40 dirty blank pages called blank. A one-digit page number at 8 point is the smallest mark found; below that, the ink cannot be told from dust at 150 dpi.

### The text layer, and when to read again

The English prior is the signal docs/ocr-correction.md measured (Spearman 0.66 on prose). On this box it separates less: on 50 pages of typed prose scored against a clean copy, the correlation of a page's suspect share with its word error rate was 0.28, and the Tesseract tool beat the scanner's text layer on 41 of the 50 pages at every share (the layer 4.95%, the tool 3.65%). So 3% (`SHARE_LIMIT`) is a place to start, not a finding: 811 of 1,829 scored pages in the box are over it. Tables, names, and addresses are doubted by an English prior, so a page of figures scores high without being badly read. The report names the pages over the limit, and the decision to read them again is a person's (`--ocr` does the work and changes nothing in the original).

## The cleaned rendition

**Flattening.** The page is drawn to an image with its annotations, form fields, and optional-content layers left off, and the scanner's text layer is not in an image. A page that is drawn in an optional-content layer keeps it (turning the layers off would take the page away), and says so.

**Cleaning** (`auto`, the default): measure each page, and fix only what is wrong with it, in this order: shading of 20 gray levels or more is **flattened** (the page divided by its own paper brightness), dust over 2% of the ink pixels is **median filtered** (3 x 3), and a tilt of 1 degree or more is **turned**. A page with none of these comes back as drawn, the same array, so the cleaning cannot harm it. The thresholds sit in the gaps the measures showed: a clean scan has 0 dust and 0 shading and a tilt of up to 0.6 degrees (its own); the defective sets had dust of 0.07 to 0.39, shading of 122, and a tilt of 1.4 to 2.2; across a sample of 200 archive pages dust reached 0.024 and shading 69 on a few.

**Variants** (`--variant`): `auto`, `scanned` (as drawn), `smooth` (blur 0.8, median 3), `flatten`, `despeckle`, `deskew` (every page), `stretch`, `clahe`, `otsu`, `sauvola`. The rendition is gray (8-bit) PNGs at 300 dpi, a 1-bit PNG only if the variant makes one; `--native` takes a scan's own raster at its true resolution instead of drawing the page.

### What was measured

The scoring is the one docs/ocr-correction.md uses: a global alignment of the reading to a hand-kept working copy, WER and CER, and a count of words made right and made wrong against the as-drawn baseline, by section ("worse" is a section with more errors than as drawn). Tesseract's tool, `eng`, one thread per page. Times are median seconds a page, 14 pages at once on a 32-thread machine.

**1. A crisp recorded scan** (56 pages; 200 dpi 1-bit source drawn at 300 dpi gray; 26,440 scored words).

| Variant | WER | CER | Words +wrong / -wrong | Sections worse | Seconds (prep + read) |
|---|---:|---:|---:|---:|---:|
| as drawn | 2.02% | 0.42% | | | 0.05 + 1.6 |
| contrast stretch | 2.02% | 0.42% | 0 / 0 | 0 | 0.15 + 1.7 |
| background flattened | 2.02% | 0.42% | 0 / 0 | 0 | 0.19 + 1.6 |
| **auto** | 2.02% | 0.42% | 0 / 0 | 0 | 0.14 + 1.6 |
| CLAHE | 2.05% | 0.42% | +29 / -21 | 22 | 0.3 + 1.6 |
| Otsu | 2.32% | 0.47% | +111 / -32 | 78 | 0.12 + 1.6 |
| Sauvola (51 px) | 2.37% | 0.49% | +143 / -45 | 105 | 1.9 + 1.7 |
| CLAHE then Sauvola | 2.37% | 0.49% | +148 / -50 | 102 | | 
| Niblack | 3.53% | 1.05% | +439 / -26 | 282 | 1.7 + 1.8 |
| median 3 | 1.87% | 0.42% | +32 / -72 | 22 | 0.17 + 1.6 |
| blur 0.8 | 1.87% | 0.41% | +25 / -64 | 16 | 0.17 + 2.1 |
| blur 0.8, median 3 (`smooth`) | **1.76%** | **0.38%** | +27 / -96 | 20 | 0.38 + 2.2 |
| deskew (any tilt over 0.15) | 2.06% | 0.41% | +48 / -38 | 32 | 0.27 + 1.6 |
| 150 / 200 / 400 / 600 dpi | 2.31 / 2.29 / 2.05 / 2.68% | | | | |

**2. The same pages with one defect each** (synthetic, applied to the 300 dpi drawing; WER as drawn, then by variant).

| Defect | As drawn | Otsu | Sauvola | CLAHE | Median 3 | Deskew | Flatten | **auto** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| shading (45% across, 25% down) | 25.79% | 25.88% | 5.76% | unreadable | 20.09% | 26.00% | 2.02% | **2.02%** |
| salt-and-pepper dust (1.5%) | 7.33% | 7.40% | 6.52% | | 1.88% | 9.82% | 7.33% | **1.88%** |
| tilt 1.7 degrees | 2.63% | 2.81% | 3.11% | 2.58% | 2.26% | 2.09% | 2.63% | **2.09%** |
| faded copy (ink 120, paper 190) | 2.08% | 2.33% | 2.26% | | 1.94% | 2.16% | 2.07% | **2.08%** |
| soft focus | 1.94% | 2.03% | 2.12% | | 1.88% | 1.94% | 1.94% | **1.94%** |
| sensor noise and blur | 1.81% | 2.00% | 8.17% | | 1.82% | 1.90% | 1.81% | **1.81%** |

For shading, Sauvola recovers most of the page and flattening all of it. For dust only the median does. Deskew helps only a tilted page, and on dust it makes things worse (it spreads each speck). `auto` took the right step on each and none on the three defects that did not need one. Where `auto` changed a page, some sections still got worse than the broken baseline (for shading, 94 of 316 sections, against 222 better): the gain is of a page that was unreadable, not of the same words.

**3. Scans from a box of archive pages** (50 pages of 300 dpi JBIG2 stencil scans that carry the same text, scored against the working copy; 27,000 scored words; the scanner's text layer 4.95%; 95% intervals from 2,000 bootstraps over pages).

| Variant | WER | Against as drawn (95% interval) | Pages better / worse |
|---|---:|---:|---:|
| as drawn (300 dpi) | 3.65% | | |
| **auto** | 3.65% | 0 | no page had a defect |
| 200 dpi, median 3 | 3.34% | -0.31 (-0.52, -0.11) | 31 / 12 |
| 200 dpi | 3.43% | -0.22 (-0.40, -0.05) | 26 / 18 |
| blur 0.8, median 3 | 3.46% | -0.19 (-0.31, -0.05) | 29 / 15 |
| median 3 | 3.55% | -0.10 (-0.26, +0.05) | 25 / 22 |
| deskew (any tilt over 0.15) | 3.57% | -0.08 (-0.15, -0.01) | 8 / 2 |
| CLAHE | 3.57% | -0.08 (-0.16, +0.01) | 23 / 16 |
| the page's own raster at 299 dpi, not drawn | 3.71% | +0.06 (-0.09, +0.23) | 18 / 23 |
| 400 dpi | 3.80% | +0.15 (+0.02, +0.31) | 19 / 23 |
| Otsu | 3.92% | +0.27 (+0.14, +0.41) | 12 / 32 |
| Sauvola | 4.04% | +0.39 (+0.23, +0.56) | 11 / 33 |
| CLAHE then Sauvola | 3.98% | +0.33 (+0.14, +0.51) | 14 / 29 |
| Niblack | 4.68% | +1.03 | 4 / 42 |
| `--psm 6` / `--psm 4` | 4.22% / 3.61% | +0.57 (+0.43, +0.72) / -0.04 | 3 / 42, 3 / 1 |

**What these say.** (a) Binarizing is worse than gray on every clean set, as Tesseract's own notes say for a recognizer that reads the gray image. (b) Smoothing a bilevel scan helps a little (the declaration 13%, the archive pages 5 to 8%), probably because a bilevel page drawn at another resolution has hard, uneven strokes, but it made 15 to 20 sections or pages worse each time, so it is `smooth`, an option, and not the default. (c) Only a defect makes cleaning matter much, and then only the matching fix does. (d) Resolution has no clear optimum: 300 and 400 dpi are level on the declaration, 200 is better on the archive pages (which are 300 dpi at source), so no resolution rule was written. (e) The page's own raster at its true resolution reads the same as drawing the page (3.71% against 3.65%, within the interval), so drawing is the default and `--native` is there to keep the real resolution. The scans in the box are placed with a small tilt that the drawing undoes, which is why the raster, undrawn, is tilted by up to a degree.

**4. The vision reader** (qwen3.5:9b through Ollama, 150 dpi, on a sample of 12 of the same archive pages; the preflight and the GPU lock held; `qwen3.6:27b` was refused for commit). The 9B model reads these pages far worse than Tesseract's tool (WER 7.8 to 9.1% against 3.65%), and the preprocessing moved it by about a point either way: gray 150 dpi 8.91%, gray 200 dpi 8.71%, flattened 8.19%, Sauvola 8.27%, CLAHE 9.11%, Otsu 7.79% (5 to 19 seconds a page). With twelve pages (about 6,500 words) these differences are inside the noise, so the literature's "gray for a vision model" was neither confirmed nor refuted here: the rendition stays gray, which is what the word layer's crops need, and a binarized copy is a variant to measure on a larger sample with the 27B.

### The default

`auto` is the default. The test the work set for a default was fewer errors with zero added harm. `auto` is the only variant that has both: it returned every clean page unchanged on the declaration, on the archive pages, and on the three synthetic defects that need no fix (so no added harm there, by construction), and it took the page from 25.79% to 2.02%, from 7.33% to 1.88%, and from 2.63% to 2.09% where the defect was present. `smooth` fixes more of a clean page on average but harms some pages, and `deskew` for every page harms the declaration, so both stay options. The harm on a defective page is the one reported above: errors move even when most go.

## What a PDF carries

`jason.community.pdf_media` reads, with PyMuPDF's parser only, and never opens or runs anything:

- **Attached files**: the document's EmbeddedFiles (which holds a PDF portfolio's files too) and each page's FileAttachment annotations. Each is a child document of the PDF with the shape the segmentation stack uses: `parent` (the PDF's sha256), `page` (None for the document), `depth` 1, `kind` `attachment`, and its name, size, MIME type, and sha256. `--extract` saves it as `<sha256>.<ext>` in `<store>/<id>/media/`, with an extension only from a list of document and image types (anything else is `.bin`), never under its own name, and skips a copy already saved. `jason ingest <that folder>` classifies and takes it in like any other document. An attachment that is a PDF is preflighted again, one level down.
- **Images**: a page that is one full-page raster is a *scan* (read as above); a smaller image is *image* media of the page, with its box and placed resolution, saved when it is at least 200 pixels on each side (a photograph, a plan, a signature); a logo, a rule, or a bullet is a *decoration*, listed and never read as text or saved. The page's own raster is read at its true resolution with `--native`.
- **Form answers**: the values of a filled AcroForm are data, not OCR.
- **Risks**: JavaScript, launch actions, submit actions, open actions, and rich media are flagged and never run.
- **Encryption**: a file that needs a password is reported and not read; a file that opens without one but forbids copying says so (and is read, as a viewer reads it).

## Prior art

Tesseract's guide asks for 300 dpi (x-heights of about 20 pixels at 10 point) and notes its own Otsu binarizer is weak on uneven paper; its LSTM recognizer reads the gray image, which is why binarizing first did not help here. OCRmyPDF's pipeline order (rotate, remove background, deskew, clean) is the order `auto` takes, and its `--skip-text`, `--redo-ocr`, and `--force-ocr` are the choices `Recommendation` names (keep, read again, read the pages with no text), with a measure of the layer's quality that OCRmyPDF does not have. unpaper's aggressive filters can move text, so none is used. The notes and links are in the research file the preflight work kept (`D:\scratch\jason\ocr-research\preprocessing.md`, private scratch) and are summarized: https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html, https://tesseract-ocr.github.io/tessdoc/ReleaseNotes.html, https://github.com/tesseract-ocr/tesseract/issues/3083, https://ocrmypdf.readthedocs.io/en/latest/advanced.html, https://arxiv.org/pdf/2008.02777.

## What remains

- **Scanner-program deskew by placement.** A page drawn from its placement is straight; its own pixels are tilted. The word layer's crops are cut from the rendition's pages, which are drawn, so they agree with the boxes in `ocr.words.json`.
- **Bleed-through and colored ink** were not measured: the box had 12 colour pages and no thin-paper show-through that Tesseract misread. A channel selection or a bleed-through removal would be tried on a set that has it.
- **Resolution by text height** (rescale so the x-height is 20 to 30 pixels) was not built: 200 dpi won on one set and lost on another, so a rule needs a set with both small and large type.
- **The tilt threshold** (1 degree) leaves the 0.2 to 0.6 degree tilts of the archive's scans alone; deskewing every page helped the archive pages (8 better, 2 worse) and hurt the declaration slightly. Measure again on more pages.
- **The text-layer limit** (3%) is a place to start. A better predictor (Tesseract's word confidence, agreement of two readings) would separate pages the layer reads well from pages it does not.
- **A page number below 8 point** cannot be told from dust at the analysis resolution.
- **A vision reader's preprocessing** was measured on twelve pages with the 9B model; a larger sample and the 27B (refused for commit) would settle it.
