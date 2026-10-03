# Revision detection

Rules, policies, and manuals are revised in place. The board edits the working Doc. A copy goes to an escrow company,
and a later copy goes to a new owner. Each copy that survives is a version. `jason revisions` finds them and compares
them section by section, so each section is a unit with its own lineage. It then says what changed, when, and whether
an adoption is on record.

The pure logic is in `jason.community.revision_detection`. The readers and the report are in
`jason.tasks.revision_detection`. The command is `jason revisions`.

## Commands

```bash
jason revisions --list                  # the documents that can be compared, and when each was last built
jason revisions KEY                     # build from disk: data/revisions/KEY.json and data/reports/revisions-KEY.md
jason revisions KEY --fetch             # first read the Doc's Drive revisions and the Drive and PayHOA copies (read-only)
jason revisions KEY --versions          # the versions table
jason revisions KEY --section R-4(b)    # one section's lineage and its changes (any number it has had, or its id)
jason revisions KEY --diff v3 v7        # two versions compared directly (an id, a date, or a hash prefix)
jason revisions all --fetch             # every document
```

`KEY` is an outline key (`Community.citable_documents()`). `--fetch` reads Google and PayHOA without a browser. It
fails fast without a token (`GoogleAuthRequired`). `--ocr` reads an image-only PDF with Tesseract. A scan with its own
text layer (from the scanner's software) is read from that layer and compared as OCR.

## Where versions come from

A file is a candidate when its name names the document: its title, an alias, or a pattern in the profile's
`revision_series()` rows (`RevisionSeries`). A pattern adds an older name a copy went by, and `exclude` rules out a name
that matches but is not a copy. The other words in the name may only be version words ("draft", "revised"), dates, or
the association's own name. A parenthesized note is ignored. So "Notice of Proposed Change to the Rules" is not a copy
of the rules.

| Source | Store | The date is |
|---|---|---|
| Email attachments | `data/gmail/files.json` | when the message was sent or received |
| PayHOA library | `data/payhoa-documents.json` (files fetched to `data/revisions/payhoa/<id>/`) | the upload |
| The association's site, local Doc exports | `data/artifacts/site-docs`, `data/governing` | when jason read them (an upper bound) |
| Drive files | `data/drive/files.json` (fetched to `data/revisions/files/<id>.<ext>`) | the file's last change |
| The Doc's revisions | Drive API `revisions.list`, each exported as a Word file to `data/revisions/<key>/drive/<doc>/<rev>.docx` | when the revision was saved |

Drive merges a Doc's older edits, so the revisions are the ones it kept, not every edit. Revision exports are tightly
rate-limited (HTTP 429). `GoogleDrive.export_revision` waits and retries, and the fetch paces itself. A slimmed Word
file (its text, numbering, styles, headers, and footers; no images) is kept, so a rerun reads nothing again.

A candidate is a **version** only if it shares its words with the current text. If it holds less than
`VERSION_MIN` of the current text's letter runs, it is **excluded**: named like the document, but not this document.
One that holds less than `PARTIAL_BELOW` is an **excerpt** (partial). It is compared, but kept off the chain.

## Text and outline

- **Words.** Files with the same letters and digits are one version with many sightings. The first sighting bounds
  its date.
- **PDFs.** Page furniture is dropped. That means a line on half the pages, a short line at the top or bottom of three
  pages or more (a running header that only one part carries), and a bare page number.
- **Doc exports.** Comment anchors (`[a]`) and the comments listed at the end are dropped. A table of contents is
  blanked: from its heading, each line the document repeats later.
- **Word files.** `docx_text` draws each list label the way the file numbers it, so "a." stays "a." and a nested
  "(1)" stays "(1)". A heading becomes a Markdown heading. A table of contents control is left out.
- **Pending suggestions.** A Doc's Word export carries its unaccepted suggestions as tracked changes. `docx_text`
  reads the text as it stands, the way the Doc's own PDF prints it: a suggested insertion is left out, and a suggested
  deletion is kept. `docx_suggestions` lists them. The report shows the current Doc's suggestions, each with the first
  revision that already had it. A suggestion is a lead. It is not the text in force, and it is not a noticed
  proposal. A Markdown export applies the suggestions, so a local Markdown copy differs from the Doc by exactly them.
- **OCR.** For a scan, `outline_version` also tries the label grammar for scans (`outline_labels.outline_from_ocr`).
  It keeps whichever reading finds more numbered sections.

`outline_text` reads the following as sections:

- "ARTICLE n";
- dotted numbers ("4.15");
- lettered rule numbers ("R-4. PARKING");
- Markdown or Word headings;
- an all-capitals caption;
- the list labels under them ("a.", "a)", "(a)", "1.", "(i)"), nested by series and indentation.

Each section's own words (not its subsections') are one `Unit`. A caption with no number is known by its words
(`what-is-a-reserve`). A number used twice gets "~2", as in the record addresses.

## Alignment and classification

`align` pairs two versions' units in order of confidence:

1. The same words (letters and digits only).
2. The same label, if enough words are in common. A rule that grew a clause is still the same rule.
3. The same opening words (`outline_align.opening_key`).
4. Shared letter runs, for a section that moved or was renumbered.

What is left is a split, a merge, an addition, or a removal.

Each change gets a kind: unchanged, reworded (with a word diff), moved, renumbered, added, removed, split, or merged.

**Noise is never a change:**

- **Layout.** A word op whose removed words are found elsewhere in the new version, and whose added words are found
  elsewhere in the old one. Or an op that only adds or drops list labels. Or a section added or removed whose words
  are elsewhere.
- **OCR.** Each word a near letter or two from its counterpart, with no number and no modal changed.

**Flags, read first:**

- an amount;
- a period (days, hours, months);
- a fine, fee, charge, or interest;
- shall/may (an obligation became a permission, or a "not" came or went);
- any other number.

## Lineage and the chain

The **chain** is the Doc's revisions in order, after the versions older than the Doc. With no revisions fetched, it is
every version in date order.

A copy whose words match a revision, up to export differences, is a **copy** of it. Its dates and sightings join the
revision. The match counts the copy's words as a bag against each revision's. The revision that differs least wins,
and a tie goes to the latest one saved on or before the copy's date. It is a match if it differs by no more than
`MATCH_SHARE` (1%) of the words, and at least `MATCH_WORDS` (40). Two files read the same way (two PDFs, two Word
files) have no export noise between them, so for those any wording difference is an edit, and they are not merged.
What a copy differs by is kept as its residual: file chips, a header the PDF prints in the text, or an edit Drive did
not keep. A copy that matches no revision is a **side** version. It is compared to its nearest version and reported
apart.

A candidate named by the document's own title that shares almost none of its words, and is older, is **rewritten**:
an earlier text the current one replaced wholesale. It is listed and not aligned. A candidate named only by a
profile pattern that shares nothing is excluded. A copy whose words are nearly all in an earlier copy, which holds
much more, is an **excerpt** (`EXCERPT_HELD`, `EXCERPT_HOLDS`), for example a scan of some pages.

`jason revisions all` compares the profile's series rows. A declaration and its amendments are separate instruments,
and the living documents read them. `jason revisions ccrs` still runs on request.

`lineages` follows each unit through the chain. A lineage's id follows the permanent-id rule (`addresses.pid`): the
document's key, the date of the version it first appeared in, and its number there (`rules@2099-01-01/R-4(b)`).

- A split part is a new lineage that names the one it came from.
- A merged piece ends with the lineage it went into.

The date in the id is the first version's date as the evidence gives it. For a Doc revision, that is when it was
saved. For a copy, it is the earliest sighting. It is not proof of the effective date.

**Milestones** are the chain's versions that someone outside the Doc saw (an email, an upload, the site, a Drive
copy), plus the first and the last. The report compares consecutive milestones, so a draft made and undone between two
of them is not a change. Each change says when its later words were **first saved** (the first chain version that has
them).

## Adoption on record

For each change, the window runs from the earlier milestone's date to `ADOPTION_AFTER` (120) days after the later one.
A Doc is often edited before the board adopts the text. Two sources are searched:

- the profile's rule-change rows (`Community.rule_change_records()`) for the document, decided in the window. A row
  whose title, words, or file pattern names the section's head (`R-4`) **names this section**;
- the minutes in the window (`schedule_evidence.Stores.minutes`) that name the section's head, or the document, near an
  adoption word.

A change with no adoption naming the section is a **finding**: "changed between A and B; no adoption found". An
adoption of the same document in the window that does not name the section is listed only as a possibility. jason
never decides that a change was adopted.

Each lineage's timeline is a list of `revisions.RecordVersion`:

- `ADOPTED` (with the decided day as `effective`) when an adoption names the section;
- `DISTRIBUTED` when the version was sent or published;
- otherwise `DRAFT`.

## Dates

A version keeps every date with what it is and where it came from.

- **Existed by.** A sighting, the PDF's own creation date, or a full date in a file's name ("991120" read as
  YYMMDD or MMDDYY when only one reading is a date). Each is an upper bound: the words existed by then.
- **Claims.** "EFFECTIVE: ...", "Revised ...", or a bare year in a name. These are read as written, as a lower bound
  at best, since a later copy keeps printing an old effective date.

Older versions are ordered by the latest date they claim, then by when they existed.

## Surfaces

- `jason revisions` (above).
- `jason.tasks.revision_detection.history(data_dir, key)` and `section_history(data_dir, key, number)` read the stored
  result, read-only, for the governance MCP. Repeat their caveats:
  - "no adoption found" is a finding, not proof that none happened;
  - a Drive revision is a saved draft of the working Doc, not an adopted text.
- The report, `data/reports/revisions-<key>.md`, is private because it quotes the association's documents. It lists
  the versions, then each change between milestones with its words before and after, quoted, the adoption evidence or
  the finding, then the sections only moved or renumbered, then the copies that match no revision.

## The manual's adoption history

`jason manual` takes the owner's manual apart. When it keeps a store for the document (`data/manual/<key>/`),
`jason revisions` also writes the detector's rows to that store's `history.json`
(`jason.tasks.manual.history_path`). The rows are `AdoptionEvent.to_dict()` rows with `source` "detector". Each row is
one of:

- an "in force" row for each milestone someone outside the Doc saw (sent or published);
- an "in force" row for each section change that copy shows.

A section is named by its new address where the concordance resolves it (`manual.resolve_old` over the Doc outline's
numbering, matched by opening words). Otherwise it keeps its outline number. A number that only moved with its words
is the concordance's, not a change, so it is not written. Rows from other sources are kept, and the detector's own
rows are replaced on each run.

## Limits

- A `.doc` (Word 97) file has no reader. Save it as `.docx` or PDF to compare it.
- Labels read from a PDF and labels drawn from a Word file can disagree where a list's style changed. Alignment does
  not depend on labels, but a lineage's id uses the number its first version printed.
- A section's head is the nearest numbered or captioned head above it. A caption a PDF prints but a Doc does not
  (a running title) can split a section in one source and not the other. Layout noise absorbs most of it, and a side
  version's residual changes show the rest.
