# Handoff: reviewing what jason found when it took a scan in

For the design pass on the screen where a person reviews what jason found in a scanned or bulk file before it is trusted: its **preflight** (which pages are blank, which to read again, what is left alone), its **segments** (which documents the file holds, and which are inside which), its **OCR readings** (the words jason doubts, and what the page itself says), and what the **extraction** pulled out (attachments and photographs). The data exists today in four commands and their stores, and no screen: `jason preflight FILE|FOLDER` ([pdf-preflight.md](../pdf-preflight.md)), `jason segments ID` ([document-segmentation.md](../document-segmentation.md)), `jason intake` and its OCR suggestions, with `jason intake --library-ocr` for the worst-read list ([ocr-correction.md](../ocr-correction.md)), and `jason preflight --extract`. No loader serves them and no component renders them. Behavior and words are settled by this page, [README.md](README.md) (principles 2, 3, 4, 6, and 8), [components.md](components.md), [content/style.md](content/style.md), [content/patterns.md](content/patterns.md), and [security-and-privacy.md](security-and-privacy.md).

These components pair with what the console already has: `Doc` and `DocumentViewer` ([doc-component.md](doc-component.md), [documents.md](documents.md)) for the file and its pages, `ReadingLabel` (whose reading it is), `Pill`, `DataTable`, `Stat`, `Card`, `Tabs`, `Confirm`, `Command`, `Caveats`, `Findings`, `QuestionCard` (the intake queue's row, which an OCR reading already is), `Timeline`, `RemoteView`, `HeldNote`, and `Seal`. Build new parts only where the table says so.

**What this screen is not.** It is not ingestion: `#/ingestion` says which kind a file is and which record it covers ([screens/records-and-library.md](screens/records-and-library.md)), and the kind's own pass is [handoff-document-kinds.md](handoff-document-kinds.md). It is not the confirmations queue ([handoff-confirmations-queue.md](handoff-confirmations-queue.md)): that holds what jason *proposed about the law or its own tests* (candidate readings, gold labels, lessons waiting on a decision); this holds what jason *read from a file*. It is not the context-pack workbench ([handoff-context-pack-workbench.md](handoff-context-pack-workbench.md)), which searches passages that a reading already made. And it changes no file: **the original is never rewritten, split, or cleaned in place**, the cleaned rendition lives in its own store, a segment is a page range and never a new file, and an OCR suggestion is held beside the text and never written into it. A person's act here is a signed record in jason's own store, laid over a reading, never over the original.

**Its neighbours, by what each answers.** A *fact* a record states is the intake queue's (`#/applies`). A *kind* of document is `#/ingestion`. A *reading of the law* is `#/confirmations`. A *page, a document boundary, or a word* of one scan is here.

## The idea in one line

Every reading jason makes of a scan is **evidence beside the file, never a change to it**, and this screen shows each one with the page it rests on, the readers that made it, and a tier in words, so that a person can answer it, in their own name, in the order that spends their time best.

## What exists today

| Reading | Command | Store | What a person can do with it today |
|---|---|---|---|
| Preflight: per page `content`, `marked`, or `blank`; rotation; skew; dpi; codec; color; suspect share of the text layer; defects (`uneven`, `speckle`, `skew`) and the `steps` cleaning would take; a cleaned rendition; attachments, images, form answers, risks, encryption | `jason preflight FILE\|FOLDER` (`--render`, `--pdf`, `--ocr`, `--extract`, `--limit`) | the report (printed or `--json`); renditions under `<data>/library/renditions/<id>/`; media saved by sha256 in `<id>/media/` | Read it. `--render` and `--extract` write only to the renditions store. Nothing records a person's judgment of a page |
| Segments: a tree of nested documents, each with its page range, `runs`, parent, role, kind, tier, readers, and the `Move` that opened it with its signals; parts with anchors | `jason segments ID` (`--write`, `--moves`, `--model`, `--embed`, `--accept`, `--show`, `--list`) | `data/library/segments/ID.json`, keyed by the file's SHA-256 | Read it and store it. No command confirms, splits, merges, re-parents, or names anything: **proposed** below |
| OCR readings: suggestions with the reading, the method, the evidence, the guard, and the tier (`likely`, `suggested`, `conflict`); each doubted word's crop and box | `jason intake --scan` (`--model`, `--vision`, `--vision-route`, `--ocr-options`); `jason intake --kind ocr-reading`, `--likely`; `--library-ocr` | intake questions; `data/living/<key>/ocr-suggestions.json` for a reading one reader made; `data/library/text/<id>.ocr-suggestions.json` beside a library text; `<scan>.words.json` and `ocr.words.json` for the boxes | `jason intake --answer ID TEXT --by NAME`; `--accept-likely --by NAME` answers every open likely reading; `--apply` turns answers into the records the next run uses |
| Extraction: attachments (each a child of the PDF: `parent` sha256, `depth` 1, `kind` `attachment`), photographs and plans at least 200 px a side, decorations (listed, never saved), form answers | `jason preflight FILE --extract`, then `jason ingest <media folder>` | `<store>/<id>/media/<sha256>.<ext>` | Take them in with `jason ingest`. The parent link is in the report, not on any screen |
| The worst-read files, by the share of words the English prior doubts | `jason intake --library-ocr [--library-kind KIND]` | the sidecar files above | Read the list in the terminal |

The OCR answers already have a built writer: `POST /api/write/intake/<id>` queues `answer_intake_question` with `by` ([information-architecture.md](information-architecture.md)). This screen uses it for OCR readings and adds writers only for the three things the CLI cannot yet record: a person's keep of a blank page, a person's act on a segment, and a person's act on a part.

## The components

| Component | Where it renders | Data | States to design |
|---|---|---|---|
| `IntakeReview` | the screen: Records, `#/intake` (the worst-read list) and `#/intake/<fileId>` (one file); `ScreenHeader` with the file's name, its `Doc` chip, and the `Command` for each reading | `GET /api/intake-review` and `GET /api/intake-review/file?id=` | no store at all (the commands that make each reading); loading; a file with only some readings (the rest as "not read: jason preflight FILE", never an empty band); a file held back (confidential, outside the private view: the counts only); the file's bytes changed since the readings were made (`ReadingStale`); empty ("No scan has been read yet.") |
| `ReadFileList` | `#/intake`; the "Where to spend a person's time" band | `files[]` (the suspect share, pages over the limit, open readings by tier, blank pages, segments found) | listed worst-read first with the sort announced; sorted by another column (open likely readings, pages to read again); filtered by kind; a file whose OCR text has no sidecar yet ("not scored: `jason intake --library-ocr`"); a file held back; the share's limit named as a place to start, not a finding |
| `ReadingShare` (a `Stat` preset) | in `ReadFileList` and at the head of one file | `suspectShare`, `limit`, `pagesOver`, `pages` | "6.1% of words doubted; 14 of 200 pages over 3%"; its table twin; the limit shown with "a place to start" and the measured reason beside it ([pdf-preflight.md](../pdf-preflight.md#the-text-layer-and-when-to-read-again)); a page of figures or names scores high without being badly read, and the card says so where the page's words are mostly numbers |
| `PreflightCard` | one file's Pages tab, first | `preflight` | loading; read (the strip, the plan, the pages to read again); not read (the command); the PDF needs a password (reported, not read); opens without one but forbids copying ("read as a viewer reads it"); a risk found (JavaScript, a launch or submit action: listed, never run); original untouched (always stated); a rendition exists (its date and variant) or does not (the command) |
| `PageStrip` | inside `PreflightCard`; also under the segment tree | `pages[]` as runs | a strip of page cells, each with its number and a word and mark (`content`, `marked`, `blank`); runs collapse ("pages 12 to 40: content, 29 pages") and open; the page being viewed marked "viewing"; a page a person kept marked "kept by Jane Example"; a page over the limit marked "read again"; a page with no text layer marked as such; a key under the strip in the same words |
| `PageMark` | one cell of the strip and one row of the page list | a page's `blank`, `reason`, `rotation`, `skew`, `dpi`, `suspectShare`, `defects` | content; marked (the reason: signature, stamp, page number, running head, divider's title, short text, left blank); blank; kept (a person's keep over a blank); read again (over the limit); rotated or skewed (the degrees); a low dpi |
| `PreflightPlan` | inside `PreflightCard` | `plan` | the steps jason would take, each with the measure that decided it and the threshold ("flatten the shading: 122 gray levels, over 20"; "median filter the dust: 0.07 of ink pixels, over 0.02"; "turn 1.7 degrees, over 1"); a page with no measured defect "comes back as drawn"; the blank pages "left out of the rendition, kept in the original"; the variant named (`auto`), the others listed as options and never chosen here |
| `KeepBlank` (a `Confirm` preset) | on a blank page's row | one page | off until the page is open in the viewer; "Keep page 7 in the rendition, as Jane Example"; kept (the person, the day, a reason); undo is its own `Confirm` ("Let page 7 be left out again"); never offered on a page with ink and no text where the person has not looked |
| `RereadList` | `PreflightCard` | `reread[]` | the pages over the limit, with each page's share and a note where its words are mostly figures; a `Command` for `jason preflight FILE --render --ocr`; the model-free route first, the vision route after, each with its cost in words; the decision to read again is a person's, so the list has no "do it" button |
| `SegmentTree` | one file's Documents tab | `segmentation` | loading; not segmented (`jason segments ID --write`); stored and current; stale (the file's SHA-256 is not the reading's; the tree shown as read and labeled "of other bytes"); a flat file (one segment: "jason found one document"); a deep tree (collapsed below depth 2, each node with a count); a person's overlay applied ("as read" and "as decided" views, switchable, never merged without saying); a reading with `--model` and one without (the readers named) |
| `SegmentRow` | inside `SegmentTree`, one per segment | `Segment` | the key (`s2.1`), the title or "untitled", the kind or "no kind" (a miss stays a miss), the page range and its own pages (`runs`), the level in words ("inside s2"), the role (document or exhibit, with its label), the date and parties where read, the move that opened it, the tier word, the readers; open (its signals); confirmed, split, merged, re-parented, or named by a person (who and when); a boundary the walk re-parented ("read first as a sibling, then placed inside s2 when its page 4 returned") |
| `MoveBadge` (a `Pill` preset) | `SegmentRow` and `PageBelongs` | `Move.kind` | `new top-level`, `push` (a new document inside), `pop` (back to an outer one, with the segments it closed), `continue` (not logged, so not shown); each with its words, never an arrow alone |
| `SignalList` | inside an open `SegmentRow` and `BoundaryRow` | `Move.signals`, `Boundary.cues`, `Boundary.model`, `Boundary.embedding` | the cues that made the break with their weights ("page-one +1.5", "numbering-reset +1.2", "continued -1.2"), the rule score against the 0.8 threshold, the model's probability where it read, the embedder's cosine where it read; the closed-choice reading of the move labeled "uninformative on the measured files" until a prompt that works is found ([document-segmentation.md](../document-segmentation.md#measured)) |
| `TierWord` (a `Pill` preset) | `SegmentRow`, `BoundaryRow`, `OcrSuggestionCard` | `tier` | `likely` (two readers agree), `suggested` (one reader), `conflict` (readers disagree, each a choice), `confirmed by NAME` (a person), `rejected by NAME`; always the readers beside it, never a bare confidence |
| `BoundaryRow` | the Documents tab's second list: every candidate boundary, including those the walk did not take | `boundaries[]` | a boundary the rules and the model both found (likely), one only the rules found, one only the model found (suggested, with the note that the model leans to yes), one a person split or confirmed; a boundary the walk read as a continue; the page's thumbnail beside it |
| `SegmentActions` | under an open `SegmentRow` and `BoundaryRow` | `acts` | the five acts in "The acts on a segment", each a `Confirm` naming the person; an act the file's state does not allow shows the reason in words, never a hidden button; every act off while the reading is stale |
| `PartRow` | beneath its segment | `Part` | the title, the `PartKind`, the pages, the mark that found it (running header, title, bookmark, contents, cover, after contents), the anchor and end anchor as the words on the page, the book its title names or "no book" (a miss), the innermost segment that holds it; named by a person; an exhibit shown as a child segment, never as a part |
| `SegmentBreadcrumb` | above the page in the viewer | `chainAt(page)` | the path from the file to the innermost segment ("sha-0a1b… / s2 Report / s2.1 Exhibit A"), each a link that selects that segment; the part, where one holds the page, after it; a page in no segment (a gap, "not in any document jason found"); a blank page (transparent: it belongs to the segment that was open, said in words) |
| `PageViewer` | right of the tree (below it on a phone) | `GET /api/intake-review/page?id=&page=` | the page image (the rendition's, or the original's when none exists; labeled which), its number and the file's page count, `SegmentBreadcrumb`, `PageMark`, its text layer in a `<details>`, previous and next; loading; the page's image held ("opens in the private view" for a P3 file); no image on disk (the command); "original" and "cleaned" toggled, never overlaid |
| `PageBelongs` | in `PageViewer` | `stack` | the stack-aware answer to "which segment does this page belong to": the innermost open segment and every level below the top that is open at this page, outermost first, each with its own pages (`runs`) and whether this page is one of them ("page 9 is s2's own; s2.1 is open here, its pages 7 to 11") and, for a pop, the segments the page closed; never a single label that hides the nesting |
| `OcrReview` | one file's Readings tab; also the page viewer's side panel | `ocr` | loading; none yet (`jason intake --scan`); open readings grouped by page; answered; held (a reading one reader made, kept in `ocr-suggestions.json`, not a question); a reading whose crop has no image (the command); the readers that ran named, the ones that did not ("vision: not run") named too |
| `OcrSuggestionCard` | `OcrReview`, one per reading | `Suggestion` | see "The OCR card" below: the crop beside the reading, the readings labeled by reader, the tier, the guard, the three answers |
| `CropBeside` | inside `OcrSuggestionCard` | `crop`, `box`, `line` | the page's crop at a size a person can read, with the word's box on the line and the line's words in text beside it; the crop's alt text is the OCR's reading, the reading is also text; a crop with no image on disk ("the crop is cut from the rendition: `jason preflight FILE --render --ocr`"); a crop of a P3 file held until the private view is open |
| `ReadingPair` | inside `OcrSuggestionCard` | `readings[]` | each reading with its reader's label (**text rules**, **page crop (vision model)**, **a person's working copy**), the OCR's own reading first and labeled "as read"; where two readers differ, both shown and neither preselected; where they agree, one line "the text rules and the page crop agree" |
| `OcrAnswer` | inside `OcrSuggestionCard` | the three answers | accept (a reading chosen from those shown, or the person's own typed), reject (keep as read), **I can't tell** (leave it open, noted); each through `Confirm` in a named person's name; none checked at first |
| `BulkLikely` | above `OcrReview` | `bulk` | the count of open likely readings that change no number and no operative word, by page range; "Look at a sample" first (five opened); a `Confirm` that names the count and the person; the readings it would not take (a number changed, an operative word, a reading one reader made) counted and listed, never swept in; done (the count answered) |
| `ExtractionFound` | one file's Found inside tab | `extraction` | loading; not extracted (`jason preflight FILE --extract`); attachments, photographs, and decorations as three lists; risks; form answers; each row's parent link; each taken in (a library id) or not yet (the command); an attachment that is a PDF, preflighted again, one level down |
| `ExtractedItemRow` | inside `ExtractionFound` | an item | the name as the PDF gave it (text, never a path), the kind (`attachment`, `image`, `decoration`), size, MIME type, sha256 (first 12), the page it was on or "the document", `parent` as a link to the file, `depth`, whether saved and under what name (`<sha256>.<ext>`, never its own name), whether `jason ingest` took it in, and its library address if so; a decoration "listed, never read or saved"; a risk "flagged, never run" |

### The words

Every state is a word the code uses, and the color or glyph only repeats it. A page is never told apart by color alone: each cell carries its number and its word.

| Word | Where from | Meaning |
|---|---|---|
| content, marked, blank | `PageFact.blank` | a page with ink worth a mark and text, a page with a little (a signature, a stamp, a page number, a head, a divider's title, a short text, a note that it is left blank), a page with none. A marked page is kept, never dropped |
| kept | a person's keep | a person says a blank page stays in the rendition; the original always has every page |
| read again | the suspect share over `--limit` | the page's text layer has more doubted words than the limit; a place to start, a person decides |
| left alone | `plan` | no measured defect, so the page "comes back as drawn" |
| as read, as decided | the stored reading, and a person's overlay | the machine's tree and the tree after a person's acts; both stay |
| new top-level, push, pop | `Move.kind` | a new document; a new document inside the open one; the outer document returning |
| likely, suggested, conflict | `Tier` | two independent readers agree (and the guard passes); one reader; readers disagree |
| confirmed by NAME, rejected by NAME | the overlay | a person's act, with the day |
| text rules, page crop, working copy | the reader | which reader made a reading |
| held | the loader | a confidential file or page not shown outside the private view |
| of other bytes | the SHA-256 | the reading was made of a file that is not this one |

"Fixed", "corrected", "accepted" alone, and "approved" appear on no control. An OCR reading is "accepted as Jane Example's transcription" (kind `TRANSCRIBED`, `living.Correction`); the original text is unchanged either way. A tier is never a percentage.

## The preflight card

```
sha-0a1b2c3d4e5f6a7b · scan-box-example.pdf · 200 pages · read Oct 5, 2099             jason preflight scan-box-example.pdf [copy]
Original: untouched, as scanned. Cleaned rendition: in the renditions store, variant auto, Oct 5, 2099 (not a replacement).

Pages    1 ■C ... 40 ■C   41 ▢B   42 ◪M   43 ■C ... 118 ■C   119 ▢B ▢B   120 ... 200 ■C       key: C content · M marked · B blank
Viewing page 42: marked. A page number, 8 point, in the lower corner. Kept; never dropped.

What would be done, and why
  Left alone      178 pages: no measured defect (shading 0, dust 0, tilt under 1 degree)
  Flatten shading  2 pages (88, 89): 122 gray levels of range, over 20
  Median filter    1 page (141): dust 0.07 of ink pixels, over 0.02
  Turn             1 page (156): 1.7 degrees, over 1 degree
  Left out of the rendition, kept in the original: 3 blank pages (41, 119, 120)        [Keep page 41 ...]

Pages to read again (text layer over 3%: a place to start)     14 of 200    jason preflight scan-box-example.pdf --render --ocr [copy]
  Page 63: 9.2% doubted. Mostly figures: an English word list doubts figures and names without their being badly read.

Carries: 2 attachments, 3 photographs, 11 decorations (listed, never read) · risks: none · encrypted: no
```

The card is one `Card`. `PageStrip` is first, so the person sees the whole file before any list. A blank page's row has `KeepBlank`; a marked page has no control (it is already kept). `PreflightPlan` says what *would* be done, in the future tense, until a person has run `--render`; afterward it says what *was* done and the rendition's date. The cleaned rendition is shown as a toggle on the page in the viewer, original first.

**The page strip, in text.** A cell is a `<li>` in an ordered list with the text "Page 42, marked" (visually the number and a one-letter mark with a distinct outline shape for each word), reachable by arrow keys as a composite widget, and a run is a disclosure whose summary says "Pages 43 to 118, content, 76 pages". A person never has to find a color.

## The segment tree

```
sha-0a1b2c3d4e5f6a7b · 3 documents at the top, 4 inside them · stored Oct 5, 2099 · readers: rules, model        as read | as decided

s1  Agreement (example)                  pages 1-8          document · push none · likely (rules, model agree)
s2  Board packet (example)               pages 9-120        document · new top-level · likely
    s2.1  Treasurer's report             pages 12-19        inside s2 · push · suggested (rules only)
          part: Balance sheet            page 14
    s2.2  Exhibit A  Schedule            pages 40-44        inside s2 · exhibit of s2 · likely
s3  Letter (example)                     pages 121-124      document · new top-level · suggested (model only)

Viewing page 14                                          Breadcrumb: file / s2 Board packet / s2.1 Treasurer's report / part Balance sheet
Which segment does page 14 belong to? Its own pages: s2.1 (pages 12-19). Also open here: s2 (its own pages 9-11 and 20-120).
```

Each row is one `SegmentRow`: the title is a heading of the level its depth gives, the range reads "pages 9 to 120 (its own: 9 to 11, 20 to 120)", and the move that opened it reads in words ("a new document inside s2, because its page 1 appeared while s2's 'Page n of N' had not reached N"). The level is a word and a number ("level 2, inside s2"), and the indent only repeats it. A page range is absolute in the file and includes the children's; a segment's own pages are the `runs`. A segment is named like a library document with a fragment (`library:ID#seg=s2/s2.1`), and the row copies that address on request; a part is `library:ID#part=SLUG` ([document-segmentation.md](../document-segmentation.md#addresses)).

**The page viewer's breadcrumb and `PageBelongs`.** The breadcrumb answers "where am I"; `PageBelongs` answers "which of the open documents does this page continue". They are not the same: a page in a report that sits inside a packet belongs to the report, and the packet is also open around it. The stack at a page (`chain_at`) is shown outermost first with each level's own pages, so that nesting is read as nesting. A pop is shown as an event: "page 20 closed s2.1 and returned to s2 (its page number resumed, with its header)".

### The acts on a segment

Every act is a `Confirm` in the signed-in person's name, through the write guard (`X-Jason-Token`), and echoes the file's SHA-256 and the reading's digest as the person saw them; a mismatch is refused (409) and nothing is written. None changes the file or the stored reading: each is a row of a person's overlay, `data/library/segments/ID.decisions.jsonl` (proposed), applied over the reading for "as decided". **No command records any of these today; every CLI flag below is proposed**, in the style of `jason intake --answer ... --by`.

| Act | The words on the button (what the person signs) | What it needs | What it records | What it never does | CLI (proposed) |
|---|---|---|---|---|---|
| Confirm a boundary | **Confirm that a document begins at page 41, as Jane Example** | the page open in the viewer | the boundary a person read at page 41, on top of the readers' tier: "confirmed by Jane Example" beside "likely" or "suggested", never replacing it | Change the readers or their tier. Split the file | `jason segments ID --confirm-boundary 41 --by NAME` |
| Split here | **Start a new document at page 41, as Jane Example** | the page; whether it is a new top-level document or inside the open one (a choice, no default) | a boundary no reader found, labeled "added by a person"; the tree below it is re-walked from the person's decision | Split the PDF; pages stay in one file | `jason segments ID --split 41 --inside s2 --by NAME` (or `--top`) |
| Merge | **Merge s2.2 into s2, as Jane Example** | the two segments, adjacent in page order, or a child and its parent | a merge row: "this boundary is not one"; the page range of the survivor | Delete the segment's record: the reading keeps it, the overlay hides it | `jason segments ID --merge s2.2 --into s2 --by NAME` |
| Re-parent | **Place s3 inside s2, as Jane Example** (or "Move s3 to the top level") | the segment and its new parent, the choices being the open documents at its first page and no cycle | a parent change; a segment's pages stay absolute | Reorder pages | `jason segments ID --reparent s3 --under s2 --by NAME` |
| Name a part | **Name pages 14 to 15 "Balance sheet", as Jane Example** | a title, the pages, and the segment that holds the first page | a part row labeled "named by a person", its anchor taken from the words on the page or "no anchor" | Claim a `book` the canon does not name: a title it does not know stays unbooked | `jason segments ID --part "Balance sheet" --pages 14-15 --by NAME` |

Also off, and why: every act is off while the reading is stale ("the file is not the one read: `jason segments ID --again`"). A person's overlay is itself evidence, not a pin: a later `jason segments ID --again` leaves it in place and shows where the new reading disagrees with it, as a `Discrepancy`, never resolving it.

## The OCR card

```
Page 17 · line 12 of the page                                      Tier: likely · text rules and page crop agree · guard passes
┌──────────────────────────────────────────────────────────────┐
│ [crop: the line, 4x]  ... the integrity ot Lhe tJnit and the roof ...           (the word's box marked)  │
└──────────────────────────────────────────────────────────────┘
The line as read:  the integrity ot Lhe tJnit and the roof
  As read ........................ tJnit
  Text rules ..................... Unit       (the language model: likelier by itself; the rules)
  Page crop (vision model) ....... Unit
  The working copy ............... not on record

  Changes no number and no operative word.            ( ) Accept "Unit"   ( ) Reject (keep as read)   ( ) I can't tell
  [ Accept as Jane Example ]  records this as Jane Example's transcription of page 17; the scan's text is unchanged.
  jason intake --answer ID "Unit" --by "Jane Example" [copy]
```

- **The crop is beside the reading.** The page's own words are the evidence; the OCR text and the models are readers of it. The person reads the crop and chooses. Where the crop is not on disk, the card says so and gives the command; it never answers from the text alone and calls it seen.
- **The readers are labeled.** "Text rules" (layout and lexicon: one reader), "page crop" (the vision model, a second reader), and "working copy" (a person's hand transcription) are separate, per [the readers](../ocr-correction.md#the-readers). The OCR's own reading is "as read", first. A reading one reader made is a **suggestion** and says "one reader"; two independent readers that agree, with the guard passing, are **likely**; readers that disagree are a **conflict** with each reading shown and none chosen. No percentage appears.
- **The guard is a sentence.** "This changes a number" or "This changes an operative word (shall to may)" or "This adds or drops a word" or "Changes no number and no operative word", from `ocr_correct.guard`. A guarded change is never in the bulk and always opens its crop first.
- **Nothing is applied.** Accepting records a person's transcription (kind `TRANSCRIBED`) that the next run uses (`jason intake --apply`); the stored text is unchanged, and the card says so. A reading is evidence, and a person's answer is a reading too, labeled as theirs.
- **I can't tell** is an answer: it leaves the reading open with the person's note ("the crop is cut off"; "need the original page"), is counted apart from rejected, and never counts as accepted. It keeps the card in the list.
- **A conflict** shows each reading with its reader and no default; the person chooses one, types their own, or "I can't tell".
- **Bulk, only for what a bulk can carry.** `BulkLikely` accepts the open readings that are `likely` *and* change no number and no operative word *and* add or drop no word, on the pages shown, after the person has opened a sample of five. It names the count, the person, and the pages ("Accept 212 likely readings on pages 1 to 60 that change no number or operative word, as Jane Example"). It is the screen's form of `jason intake --accept-likely --by NAME`, narrowed to the file (proposed: `--subject`). A reading the model alone made, a guarded change, or a conflict is never in it, and the screen lists what was left out and why.

## Worst-read files

```
Where to spend a person's time                            jason intake --library-ocr [copy]       sorted: worst-read first
File                              Kind         Doubted words   Pages over 3%   Open: likely · suggested · conflict   Blank   Segments
scan-box-example-a.pdf            (no kind)    6.1%            14 of 200       212 · 31 · 4                          3       7
scan-box-example-b.pdf            minutes      3.4%            6 of 40         40 · 5 · 0                            0       1
```

The list is `DataTable` with a caption ("Files read by OCR, worst-read first"), the sort announced, and a row that is a link to the file. The doubted share is the English prior's, and the column header says so ("Doubted words, by an English word list"); the card repeats that tables, names, and addresses are doubted without being badly read, and that on the measured box the share separated badly-read pages less than it did on prose, so it orders a person's time and judges no file. A file's "open" counts are by tier in separate columns, so a person sees where the likely, quick ones are. A file with no scored sidecar is listed last as "not scored", with the command. Nothing here sorts a confidential file in without its counts only.

## What the extraction found

```
Found inside scan-box-example-a.pdf               jason preflight scan-box-example-a.pdf --extract [copy]
Attachments (2)
  contract-example.pdf     application/pdf   84 KB   sha256 3f9a2b…   on page 12   parent: this file (depth 1)   saved as 3f9a2b….pdf   in the library: not yet   jason ingest <folder> [copy]
  letter-example.docx      application/vnd…  12 KB   sha256 9c01de…   the document parent: this file (depth 1)   saved as 9c01de….bin   in the library: library:4101
Photographs and plans (3)   page 31, 44, 44 ... each at least 200 px a side, saved by sha256
Decorations (11)            listed, never read as text or saved
Risks: none.  Form answers: none (a filled form's values are data, not OCR).
```

An attachment is a **document of its own with a parent link**: its row says `parent`, links back to the file and the page it came from, and, once `jason ingest` has taken it in, links to its own library address. It is never shown as part of the parent's text, and its kind is the library's classification, not the screen's. A PDF attachment is preflighted again, one level down, and appears as a nested row with its own card. The saved name is the sha256 and a type from a short list, never the name inside the PDF; the name inside the PDF is shown as text only.

## Data shapes

Made-up files, pages, and words. A section number is a placeholder, and a quotation from any document is a placeholder in the sample: on the screen a page's words come from the stored text layer and the crop from the page image, never from a sample.

`GET /api/intake-review` (proposed; `?kind=`, `?sort=share|likely|pages`):

```json
{
  "found": true, "asOf": "2099-10-05",
  "files": [
    {"id": "sha-0a1b2c3d4e5f6a7b", "name": "scan-box-example-a.pdf", "kind": "", "level": "P1", "held": false,
     "pages": 200, "suspectShare": 0.061, "limit": 0.03, "pagesOver": 14,
     "open": {"likely": 212, "suggested": 31, "conflict": 4}, "blank": 3, "segments": 7,
     "readings": {"preflight": "2099-10-05", "segments": "2099-10-05", "ocr": "2099-10-05", "extract": "2099-10-05"},
     "route": "#/intake/sha-0a1b2c3d4e5f6a7b"},
    {"id": "sha-1122334455667788", "held": true, "kind": "legal", "level": "P3",
     "note": "held: confidential; opens in the private view", "counts": {"pages": 40}}
  ],
  "unavailable": [],
  "caveats": ["The share of doubted words is an English word list's. Figures, names, and addresses are doubted without being badly read. It orders a person's time; it does not judge a file."]
}
```

`GET /api/intake-review/file?id=sha-0a1b2c3d4e5f6a7b` (proposed): the four readings and the file's state.

```json
{
  "found": true, "id": "sha-0a1b2c3d4e5f6a7b", "name": "scan-box-example-a.pdf", "doc": {"address": "library:sha-0a1b2c3d4e5f6a7b", "kind": "pdf", "level": "P1"},
  "sha256": "0a1b2c3d4e5f6a7b…", "stale": false, "original": "untouched",
  "preflight": {
    "read": "2099-10-05", "pages": 200, "suspectLimit": 0.03,
    "strip": [{"from": 1, "to": 40, "word": "content"}, {"from": 41, "to": 41, "word": "blank"}, {"from": 42, "to": 42, "word": "marked", "reason": "a page number"}],
    "pages_detail": [{"page": 41, "word": "blank", "rotation": 0, "skew": 0.2, "dpi": 300, "codec": "jbig2", "colour": "bilevel", "suspectShare": null, "keptBy": null, "defects": [], "riskNote": "jbig2 symbol coding can swap look-alike characters: check digits against the paper"}],
    "plan": {"variant": "auto", "steps": [
      {"step": "flatten", "pages": [88, 89], "measure": "shading", "value": 122, "threshold": 20},
      {"step": "median", "pages": [141], "measure": "dust", "value": 0.07, "threshold": 0.02},
      {"step": "turn", "pages": [156], "measure": "tilt", "value": 1.7, "threshold": 1.0}],
      "leftAlone": 178, "leftOut": [41, 119, 120]},
    "reread": [{"page": 63, "suspectShare": 0.092, "mostlyFigures": true}],
    "rendition": {"exists": true, "variant": "auto", "made": "2099-10-05", "path": null},
    "carries": {"attachments": 2, "images": 3, "decorations": 11, "risks": [], "encrypted": false, "forbidsCopying": false},
    "commands": {"report": "jason preflight scan-box-example-a.pdf", "render": "jason preflight scan-box-example-a.pdf --render --ocr"}
  },
  "segmentation": {
    "stored": "2099-10-05", "readers": ["rules", "model"], "accept": "any", "sha256": "0a1b2c3d4e5f6a7b…", "overlay": {"by": ["Jane Example"], "acts": 2},
    "segments": [
      {"key": "s2", "start": 9, "end": 120, "runs": [[9, 11], [20, 120]], "parent": null, "role": "document", "label": "", "title": "Board packet (example)", "kind": "", "date": "", "parties": [],
       "move": "new", "basis": "page-one, title-block", "tier": "likely", "readers": ["rules", "model"], "decided": null, "address": "library:sha-0a1b2c3d4e5f6a7b#seg=s2"},
      {"key": "s2.1", "start": 12, "end": 19, "runs": [[12, 19]], "parent": "s2", "role": "document", "title": "Treasurer's report (example)", "kind": "treasurer_report",
       "move": "push", "basis": "page-one while s2's 'Page n of N' had not reached N", "tier": "suggested", "readers": ["rules"], "decided": null}
    ],
    "parts": [{"key": "balance-sheet", "title": "Balance sheet", "kind": "form", "pages": [14, 15], "anchor": "BALANCE SHEET", "endAnchor": "", "found": "title", "book": "", "segment": "s2.1", "namedBy": null}],
    "boundaries": [{"page": 41, "readers": ["rules"], "score": 1.9, "cues": [{"cue": "page-one", "weight": 1.5}, {"cue": "after-blank", "weight": 0.6}, {"cue": "continued", "weight": -0.2}], "model": null, "embedding": null, "tier": "suggested", "taken": true}],
    "moves": [{"page": 20, "kind": "pop", "ends": "s2", "closed": ["s2.1"], "signals": ["page number resumed", "same footer"], "tier": "likely"}],
    "stackAt": {"page": 14, "chain": [{"key": "s2", "ownPages": [[9, 11], [20, 120]], "open": true}, {"key": "s2.1", "ownPages": [[12, 19]], "open": true, "thisPage": true}]},
    "commands": {"show": "jason segments sha-0a1b2c3d4e5f6a7b --show sha-0a1b2c3d4e5f6a7b --moves", "again": "jason segments sha-0a1b2c3d4e5f6a7b --again --write"}
  },
  "ocr": {"read": "2099-10-05", "readers": {"textRules": true, "model": true, "vision": true}, "open": {"likely": 212, "suggested": 31, "conflict": 4}, "bulk": {"count": 198, "pages": "1-60", "left": [{"why": "changes a number", "count": 9}, {"why": "one reader", "count": 31}]}},
  "extraction": {"done": "2099-10-05", "items": []},
  "acts": {"keepBlank": true, "boundary": true, "split": true, "merge": true, "reparent": true, "part": true, "ocr": true, "why": ""},
  "caveats": ["The original is never changed. A reading is evidence, a tier is a count of readers, and a person's act is a record laid over it."]
}
```

`acts` is the server's answer to what this person may do now (the file's state, the person's office, the private view); the screen renders it and works nothing out. `stale` is true when the stored readings are of other bytes, and then every act but "read again" is off.

`GET /api/intake-review/page?id=…&page=14` (proposed): the page for the viewer, and what the stack says about it.

```json
{
  "found": true, "id": "sha-0a1b2c3d4e5f6a7b", "page": 14, "pages": 200,
  "image": {"which": "rendition", "url": "/api/thumb?…", "original": true, "cleaned": true, "held": false},
  "mark": {"word": "content", "reason": ""}, "textLayer": "(the page's stored words, plain text)", "suspectShare": 0.012,
  "breadcrumb": [{"key": "", "label": "file", "address": "library:sha-0a1b2c3d4e5f6a7b"}, {"key": "s2", "label": "Board packet (example)"}, {"key": "s2.1", "label": "Treasurer's report (example)"}, {"key": "part:balance-sheet", "label": "Balance sheet"}],
  "stack": [{"key": "s2", "ownPages": [[9, 11], [20, 120]], "thisPage": false}, {"key": "s2.1", "ownPages": [[12, 19]], "thisPage": true}],
  "closedHere": [],
  "readings": [{"id": "q-ocr-0412", "line": 12}]
}
```

`GET /api/intake-review/ocr?id=…&page=17` (proposed): one page's suggestions.

```json
{
  "found": true, "page": 17,
  "suggestions": [
    {"id": "q-ocr-0412", "question": "intake question id", "line": 12, "as_read": "tJnit", "tier": "likely", "agreement": ["text rules", "page crop"],
     "readings": [{"reader": "text rules", "text": "Unit", "basis": "language model and a learned confusion"},
                  {"reader": "page crop", "text": "Unit", "basis": "the vision model read the word's crop"},
                  {"reader": "working copy", "text": null, "basis": "not on record"}],
     "guard": {"changesNumber": false, "changesOperativeWord": false, "addsOrDropsWord": false, "sentence": "Changes no number and no operative word."},
     "crop": {"url": "/api/thumb?…", "box": [412, 880, 76, 28], "line": "the integrity ot Lhe tJnit and the roof", "held": false},
     "answer": null, "bulkEligible": true, "held": false},
    {"id": "q-ocr-0413", "line": 31, "as_read": "shail", "tier": "suggested", "agreement": [], "readings": [{"reader": "text rules", "text": "shall"}],
     "guard": {"changesNumber": false, "changesOperativeWord": true, "addsOrDropsWord": false, "sentence": "Changes an operative word."}, "answer": null, "bulkEligible": false}
  ],
  "commands": {"likely": "jason intake --kind ocr-reading --likely", "answer": "jason intake --answer ID TEXT --by NAME"}
}
```

`POST /api/write/intake/<id>` (built): `{"answer": "Unit", "by": "Jane Example"}`. "I can't tell" is the same writer with `{"answer": "undecided", "note": "the crop is cut off", "by": …}` (proposed: the intake store holds an answer today, not a noted deferral). `POST /api/write/intake-review/bulk` (proposed): `{"file": "sha-…", "pages": "1-60", "sample": ["q-ocr-0412", …], "by": "Jane Example"}`; the server answers with the count written and the ones it left out and why.

`POST /api/write/intake-review/keep/<fileId>` (proposed): `{"page": 41, "reason": "", "by": "Jane Example", "sha256": "0a1b…"}`; writes `data/library/renditions/<id>/decisions.jsonl`; the rendition is rebuilt only when a person runs `jason preflight FILE --render`.

`POST /api/write/intake-review/segment/<fileId>` (proposed): `{"act": "split", "page": 41, "inside": "s2", "by": "Jane Example", "sha256": "0a1b…", "digest": "…"}`; `act` is `confirm`, `split`, `merge`, `reparent`, or `part` (then `title`, `pages`). A digest or SHA-256 that is not the one on disk is refused (409): "The file or its reading changed since you opened this. Read it again." A write with no `by` is 400. The answer is the row appended and the tree "as decided".

## What the design must keep

- **The original is never changed** (AGENTS.md; [pdf-preflight.md](../pdf-preflight.md)). No control splits, cleans, or rewrites a file. A split is a page range in a record, a clean is a rendition in its own store, an accepted word is a transcription kept beside the text. The card says "Original: untouched" in words on every file, and a rendition is always labeled as one.
- **A reading is evidence, a tier is a count of readers** (principles 2 and 3). A tier is `likely`, `suggested`, or `conflict`, with the readers named; never a percentage, never "accuracy". The vision model leans to "yes" on a first page, and a one-reader boundary says so ([document-segmentation.md](../document-segmentation.md#measured)). A person's confirmation sits beside the tier and replaces nothing.
- **A person's act is a person's.** A confirmation, a split, a merge, a re-parent, a name, and an answer are each a `Confirm` in a named person's name, with the CLI equivalent named (proposed where the CLI has none). jason never takes one on its own initiative, and no act is "approved" for the board. A person's overlay is laid over the reading and both stay; the screen says which view it shows.
- **Nothing is worked out on the client.** Which pages are blank, over the limit, or marked; the tree; the stack at a page; a boundary's score; the tier; the guard's sentence; whether a reading is bulk-eligible; what a person may do now: each is a loader's field. The client sorts nothing in a way the server did not name, and counts nothing it was not sent.
- **Pages are never told apart by color.** Each page cell, each tier, and each move carries a word.
- **A reading of other bytes is stale.** The loader compares the file's SHA-256 with the reading's; the screen says "of other bytes", shows the reading as read, and turns every act off but "read again".
- **A miss stays a miss.** A segment with no kind says "no kind"; a part with no book says "no book"; a page in no segment says so; a missing reading shows its command in place, and the other readings still show.
- **The model's choices are labeled and bounded** ([ocr-correction.md](../ocr-correction.md#the-guard-and-the-tiers)). A reading by the vision model alone is a suggestion; the screen shows only readings the guard let through (`usable_reading`) as readings, and counts the rest. A model's reading that would change a number or an operative word waits for the page, and the crop is opened first.
- **Bulk is for the quiet kind only.** A likely reading that changes no number, no operative word, and no word count, after a sample is opened. Anything guarded, one-reader, or in conflict is answered one at a time.
- **Confidential files are held back** (principle 6; [screens/records-and-library.md](screens/records-and-library.md)). A confidential file appears as counts only, outside the private view; its page images, crops, text layer, and titles do not load, and the file's name may name a person, so it is shown to the board view only. Opening a P2 or P3 page or crop is one logged view, as `Doc` does ([doc-component.md](doc-component.md#behavior)), and is never prefetched.

  | What | Level | Shown |
  | --- | --- | --- |
  | a file's counts: pages, blank pages, share of doubted words, open readings by tier | the file's own level | roster people; a P3 file's counts, with "held" |
  | a page image, a crop, a text layer, a segment's title and parties, an extracted item's name | the file's own level | the file's level decides; a P3 file only in the private view, logged |
  | a person's act (their name, the page or reading, the day) | P1 | roster people; for a P3 file, the private view |
  | the commands | P0 | always |

  The screen is board-only, never in the owner view, and nothing here is P4. A URL carries a file id (`sha-…` or a library id) and a page number, never a file's name ([security-and-privacy.md](security-and-privacy.md#urls)).
- **Nothing is sent or run without a person.** The commands that read again (`--render --ocr`, `--model`, `--vision`) hold the GPU lock and preflight; the screen shows them as `Command`s a person runs, or queues as a job a person starts (open decision 5), never on load.
- **No color-only meaning.** Each state above is a word; every figure strip has a table twin; a focus ring is visible on every cell.

## Where it goes

- **Records → Intake review** (proposed), beside Document ingestion: route `#/intake` (the worst-read list), `#/intake/<fileId>` with tabs Pages, Documents, Readings, Found inside (`?tab=`, `?page=`). `#/ingestion` gains a link from each file row ("Review the scan"), and a count in the nav (open likely readings; blank pages are not counted). The Documents tab and the Readings tab each carry the page viewer.
- **`#/digest`**, under "Waiting on a person" ([screens/today.md](screens/today.md)): one line ("212 likely and 35 other OCR readings, and 2 unreviewed documents in 3 scans, wait on a person"), linking in.
- **Governing documents** (`#/documents`): a part that names the rules or a policy links to its segment as "the Rules, pages 14 to 40 of the scan" with the `library:ID#part=SLUG` address.
- **The confirmations queue** (`#/confirmations`) stays apart ([handoff-confirmations-queue.md](handoff-confirmations-queue.md)); a reading that turns on a section jason read from a scan links here, and this screen links there when a boundary's meaning is the law's.
- **The workbench** ([handoff-context-pack-workbench.md](handoff-context-pack-workbench.md)): a passage's `segment` and `part` filters, once the index carries them (`document_search`), are the same addresses.

**Loaders and writes to add** (all proposed; a loader wraps a function that exists, except where marked "to write"):

| Name | Function behind it | Reads | Writes |
|---|---|---|---|
| `intake-review` | `jason.web.extra.intake_review:review` (to write) over the sidecars `jason intake --library-ocr` writes, `data/library/segments/`, the renditions store, and the intake questions of kind `ocr reading` | disk only | — |
| `intake-review-file` | `pdf_preflight` (the stored report; `--json`), `document_segments` (`Segmentation`, `chain_at`, `scoping_parts`), `tasks.segments` (the store), `tasks.ocr_correct` and `tasks.intake.ocr_reading_asks`, `pdf_media` | disk only | — |
| `intake-review-page` | the renditions store's page images; `Segmentation.segment_at`, `chain_at`; the library text; levels by `jason.web.access` and `library_holds` | disk only | — |
| `intake-review-ocr` | the page's intake questions; `ocr.words.json` boxes; the crop cut from the rendition's page (a thumbnail route, never a path); the guard by `ocr_correct.guard` | disk only | — |
| write `intake` (built) | `answer_intake_question`, `onboarding_confirm` | — | the intake answer, with `by` |
| write `intake-review/bulk` | `write_bulk` (to write): checks each id is `likely`, guard-clean, and in the shown pages, then calls the intake writer; refuses a guarded reading | — | the intake store |
| write `intake-review/keep` | `write_keep` (to write): appends the person's keep to the renditions store's decisions | — | `data/library/renditions/<id>/decisions.jsonl` |
| write `intake-review/segment` | `write_segment_act` (to write): appends the person's act to the segmentation's overlay; refuses a stale SHA-256, a cycle in a re-parent, a missing `by` | — | `data/library/segments/ID.decisions.jsonl` |

A segment's reading is keyed by SHA-256 and the library id the file may take on ingest; a reading stored under `sha-…` is shown under that id until the library id is known (the stored reading is not yet copied across on ingest, per [what remains](../document-segmentation.md#what-remains)).

## Accessibility

As [components.md](components.md#accessibility), with these particulars.

- **The page strip is a list** of buttons in reading order, each named "Page 42, marked, a page number" (the word first, then the reason), with a visible number and a mark of its own shape for each word; arrow keys move along it, `Home` and `End` jump, and a run is a disclosure that says how many pages it holds. The strip's table twin is the page list below it.
- **The segment tree is a nested list** (`ul` within `li`), not a bare tree role: each row's heading carries its level, the range is text, and the level is stated ("level 2, inside s2"). A row opens with a disclosure whose summary is the move and the tier in words. Expand and collapse by `Enter`; `j`/`k` between rows as [patterns.md](content/patterns.md#keyboard-use) says.
- **The page viewer** is a `region` labeled by the file's name and the page; the breadcrumb is a `nav` with `aria-current="page"` on the last item; the page image's alt text is the page's number and mark ("Page 14 of 200, content"), the text layer is a `<details>`; previous and next are buttons with the page number in their names; moving to another page announces "Page 15 of 200, in s2.1" politely.
- **`PageBelongs` is a list** read outermost first, with each level's own pages; a pop is a sentence.
- **An OCR card is a `<fieldset>`** with a legend naming the page and line; the crop is an image whose alt is the OCR's reading *and* the reading is text beside it; the readings are a description list (reader, reading); the three answers are a radio group with none checked; the tier is a word in a `Pill`, not a color. The line's words are text so a screen reader reads the sentence, and the doubted word is marked with `<mark>` plus a visually hidden "the word in doubt:" and an underline (1.4.1).
- **Every act is a `Confirm`** (two clicks, the record spelled out): "Start a new document at page 41: records that Jane Example read page 41 on Oct 5, 2099 and added a boundary there to the segments of this file. The file is not split." After the act, the result in `role="status"`, in place; focus stays on the row. An error names the field: "Choose whether the new document is at the top or inside s2."
- **A refusal that stops the work is `role="alert"`:** the stale file, the changed digest, a bulk that included a guarded reading.
- **`ReadFileList` is a real table** (`DataTable`) with a caption, each tier its own column, a sort announced politely, a polite live region for the filter count, and a row that is a link; no grid roles.
- **Shortcuts** (single-key, off by default for anyone who asks): `n` and `p` for the next and previous page, `a`, `r`, and `t` to choose accept, reject, and "I can't tell" on the open card, never a drag. Every target 24 by 24 CSS pixels or spaced to pass; nothing needs a drag. A crop is zoomable by buttons (no gesture needed), and a page zooms to 200% without a horizontal scroll of the controls (1.4.4, 1.4.10).
- **Nothing times out.** A partly written note ("I can't tell", a typed reading) stays until the person leaves; the store holds nothing until `Confirm`.

### The phone layout (under 720 px)

- The file's page is one column with `Tabs` as a `Go to` select: Pages, Documents, Readings, Found inside. `PreflightCard` stacks: the strip as runs only (a person opens a run to see cells, each still a 44 px target), then "what would be done" as a list, then "pages to read again" as cards; `KeepBlank` sits on the page's own card.
- **The segment tree is an outline** with the level said in words ("inside s2") and the indent capped at two steps; deeper levels fold under "N more inside"; a node's page range is on its own line. The viewer is below the tree, not beside it: a segment's row has "View page 9", which opens the viewer in a full-screen sheet (a bottom sheet with a grab handle, as `HostPanel` does) with `SegmentBreadcrumb` first, the page, `PageBelongs`, then previous and next; closing it returns focus to the row.
- **An OCR card stacks:** the page's line and the tier first (as words on one line), the crop with its zoom buttons, the line in text, the readings one per line with their reader labels, the guard's sentence, then the three answers and `Confirm`. `BulkLikely` is a card above the list with its sample and count, never sticky.
- **The worst-read list** becomes cards: the file's name, its doubted share and pages over the limit as words on one line, then the open counts by tier, then the blank and segment counts; sorted worst-read first, the sort named.
- **A held file** is a card with the word "held" first and no thumbnail.
- "Go to" replaces the nav as `ConsoleShell` does; the dock's drawers still pin at 1200 px and float below.

## Decisions for the design

Settled by the axioms in this pass, and why:

- **An act is laid over a reading, never into it.** The original and the stored reading are evidence; a person's act is another record ("a reading is evidence"). The screen shows "as read" and "as decided", and a later reading of the same bytes never erases the overlay.
- **No bulk past a likely, guard-clean reading.** A number or an operative word is the line the guard draws ([ocr-correction.md](../ocr-correction.md#the-guard-and-the-tiers)), and the screen draws it in the same place.
- **A blank page is kept only by a person's word.** The detector's precision is high on the measured box and its recall is not total; a person can keep a page, and the screen never drops one from the original.
- **Preflight comes before segmentation and OCR** ([pdf-preflight.md](../pdf-preflight.md), [document-segmentation.md](../document-segmentation.md#where-a-preflight-step-would-change-these-figures)). The card says when blank removal would change a segmentation's evidence (the duplex test and `after-blank`), and the Documents tab says which count of blanks its reading used.
- **The model's tier is a count of readers.** A bare confidence appears nowhere (the pattern the confirmations queue uses for its labels).

Still open:

1. **Where "read again" runs.** A re-read holds the GPU lock and takes minutes. Decide whether the screen only shows the command, or queues it as a job a named person starts (`#/jobs`), with the preflight and the lock checked first.
2. **One overlay or two.** The segment acts and the OCR answers are stored in two places (the segmentation's overlay, the intake store). Decide whether a file has one decisions record, so "everything a person did to this scan" is one list, or two stays.
3. **A split with no page cue.** A person may add a boundary no reader found. Decide whether it needs a reason, and how it reads in the tree when a later `--again` finds no signal there ("added by a person; the readers found none").
4. **Merge and a child's pages.** Merging a child into its parent changes the parent's `runs`. Decide whether a merge is allowed across a sibling in page order, and what the screen says when it is not.
5. **The sample before a bulk.** Five opened readings is a proposal. Decide the sample's size and whether it is chosen by the server (a spread of pages) or by the person.
6. **A confirmation's effect on the index.** A confirmed segment would set the `segment` and `part` columns of the passage index ([document-segmentation.md](../document-segmentation.md#how-the-index-and-collections-use-it), not built). Decide whether an unconfirmed segment is indexed at all, and how a person's confirmation is shown beside a hit in the workbench.
7. **Original or cleaned on first view.** The brief says the original first. Decide whether the person's last choice is remembered per file (a per-viewer convenience, in browser storage only) and what an OCR crop is cut from when the two differ (the rendition's, as the word boxes are).
8. **Where an unsegmented, unrendered file begins.** A file with none of the four readings is listed with its commands. Decide whether the screen offers a single "read this scan" job that runs them in the order preflight, segments, OCR.
9. **A vision reading on a number.** The crop route never reads a number; a person's own typed reading can. Decide whether a typed reading that changes a number asks for a second person (as a high-stakes intake answer does).
10. **A part's name.** `PART_RULES` is a general table and a profile may need its own words. Decide whether a person's name for a part feeds the profile's rows as a proposal, or stays this file's.

## Not part of this pass

- Running a model, preflight, or segmentation from the page: the commands are shown, and a job is open decision 1.
- Editing a file's text, cleaning a file in place, or splitting a PDF: nothing here does.
- The passage index's `segment` and `part` columns and a read-only MCP tool over stored readings ([document-segmentation.md](../document-segmentation.md#what-remains)); the console is ready for them.
- The kind a file or a segment is, and the correction of one: [handoff-document-kinds.md](handoff-document-kinds.md).
- Folding two scans of one document, and a document in two binders (not built).
- A jason-mcp confirm tool: it stays read-only and can read the same readings through the same functions.
- The owner view: this screen is board-only at every phase.
- `DiffTable` for two readings of one page: still proposed ([components.md](components.md#still-proposed)); two `Recitation`-style blocks stack until it exists.
- The previews: the design project's authored preview for each component follows the build, as for the earlier handoffs; fixtures will be `ui/src/components/intakereview.test.tsx` and its siblings, from the sample data above.
