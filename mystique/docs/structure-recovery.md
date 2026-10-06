# Structure recovery: the owner's manual (counts)

The first run of the structure-recovery benchmark ([docs/structure-recovery.md](../../docs/structure-recovery.md)) on the owner's manual Doc. Counts and rates only; the findings that name lines of the document are in `mystique/notes/structure-recovery.md` (git-ignored).

- **Gold:** the newest stored Word revision of the Doc (the Doc itself could not be read without a stored Google token), paired with the Doc's own PDF export (31 pages, 57 bookmarks). 57 styled headings (6 title-style, 4 level one, 37 level two, 4 level three, 6 level four); 27 numbered; 56 found in the PDF's text.
- **Reader, text layer, no bookmarks:** F1 70.8 (recall 91.1, precision 58.0); with the Doc's bookmarks 73.5.
- **Reader, image only, 300 to 110 dpi:** F1 57.9 to 61.4, which is 9 to 13 points under the text layer without bookmarks. Against that text layer, tilt, noise, and shading cost 14 to 17 points raw and 12 to 13 after the preflight's cleaning; a duplex scan costs 27 raw and 16 after; a JBIG2-like stencil costs 13.
- **The contents page** (35 entries, 33 found in the body) read alone gives F1 71.9 on every image variant, the best single clue once the bookmarks are gone. With it the headings called `likely` are 97 percent right (52 percent without).
- **Precision is held down by 9 lines** that print as numbered headings in capitals and that the Doc does not style as headings, and by about 20 form-field and table-cell lines. Both are the Doc's, not the reader's.
- **Numbering findings:** 1 gap, 4 out of order, 1 repeat in the numbers as printed.
- **Open:** whether the 9 lines are meant as headings; whether the Doc's parts are its title paragraphs or its bound-in documents.
