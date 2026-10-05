# Document segments in the association's records

General design, signals, and measurements: [../../docs/document-segmentation.md](../../docs/document-segmentation.md). This page is what is particular to this association. No owner's name, address, or private figure is here; what the combined files hold is in `mystique/notes/document-segments.md`, which git ignores.

## The owner's manual's parts

The manual is one PDF made of parts that were adopted at different times and belong to different books ([manual.md](manual.md)). The segmentation finds each by page, without reading the outline:

| Part | Found from | Book |
|---|---|---|
| cover, contents | the front page of few words; the "table of contents" title | none |
| questions and answers, contact information | a running header on three or more pages | none (guidance, not a governing document) |
| the rules | the first line of its first page ("Rules") | `rules`, from the canon |
| the assessment collection policy, the annual notice, the election rules, the home improvement application | a title in capitals with a part word | none: the canon names no collection or election book, so `Community.book_entries` is what ties them to `coll` and `elec` |

The part's pages and the manual task's classification of the outline's sections agree where they overlap: the pages of the rules part hold the sections that `jason manual` classifies as rules, copies of the declaration, and guidance in rules; the policy pages hold the policy sections. A part never changes a section's classification; the profile's rows still decide it.

Where the PDF has bookmarks they name some parts and not others, so the bookmark is one mark among several, and the page's own title wins where both are at the same page.

## The scanned archive

The association's older records were scanned in three batches into 41 PDFs, 2,200 pages, named "Untitled N" with a scanner text layer. They are combined files: recorded instruments and the governing documents with their exhibits, the developer's reports, court filings on pleading paper, early management packages of one-page reports, plan sets, and duplex stacks with blank backs. They are the real test of segmentation. The labeled boundaries and parts are kept privately at `data/library/segments-gold.json` (page numbers only, git ignored); the tests use made-up PDFs.

To read one: `jason segments --file "D:\hoa_archive\<batch>\Untitled N.pdf"` (a dry run), and `--write` to store the reading under `data/library/segments/`. A file already in the library is read by its id: `jason segments ID`.

## Open for the board and the manager

- Which of the archive's files are the association's records under Civil Code 5200 (the developer's delivery), which are other parties' court papers the association holds, and which should be filed under a different folder. Segmentation says where each document starts; it does not decide what the association keeps.
- Whether a combined file is split in the library (a segment becoming its own library file) or stays one file with segments addressed by pages. Segments are page ranges today and the file is never changed; splitting would be a filing decision.
