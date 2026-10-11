# Batch archive intake: a box of scanned paper, a file at a time, with the splitter in the middle

Status: design (2026-10-11); nothing here is built. It is the workflow around [the PDF splitter](pdf-splitter.md), which cuts **one** file. This page adds the batch: a folder of scans taken as a unit of work, a triage queue, safe bulk actions, a fast lane for files that need no cutting, the steps after the cut (classify, dedupe, link, file), quality control, a data model, a command and tool surface, estimates, and a build plan. General for any association: no box, folder, person, or document here belongs to one. The examples are made up ("Box A", "Box B", "123 Main St").

## The requirement

An association inherits a physical-paper archive that was scanned in boxes. The scans are PDFs in a few top-level folders, one folder for each box. A PDF is a **stack of documents in the order they were piled**, so one file holds several documents, with no separators the scanner could use. In the example this page is sized for, there are about 270 PDFs and 6,000 pages. The median file is 4 pages, and a handful run past 140 pages. The splitter handles one file at a time and is good at it. Doing it 270 times by hand, with nothing to say which file is next, which are already done, or where each document came from, is the problem.

Four sentences carry the design.

- **A person decides; jason proposes and measures.** Every cut, every "this is one document", every filing is a person's act. Bulk actions are dry runs with a count first, then a confirm.
- **Provenance is recorded, never invented.** A person labels the box. jason records the folder it found, the file's hash, and the page range. A document's place in the pile is kept with it.
- **The median file needs a tap, not a screen.** Most of the files are short. The design puts the person's time into the few long ones and gives the short ones a lane of their own.
- **Nothing is lost on the way.** The originals are never changed. A rejected cut is superseded, never deleted. Every act is in an audit trail that names no file.

## 0. What exists, and what this adds

| Today | What it does | What the batch takes from it |
|---|---|---|
| The splitter ([pdf-splitter.md](pdf-splitter.md)) | one file: pages as thumbnails, a person marks each first page, jason suggests, a review, then an apply that writes new files | the **editor** for the files that need cutting; `SplitSession`, the facts cache by hash, the rule pass, flags, `review`, `apply`, filing (`held`, `library`, `slots`), the OCR queue, and the limits `split.*`. The batch adds no second editor and no second writer |
| Record intake ([record-intake.md](record-intake.md)) | a checklist of slots; a pick; the read-back; the confirmed `split` act that pins each part to a slot with `splitFrom` | the **slots**, the collision rules, and the pin's provenance block. A part filled into a slot goes through its one writer |
| `jason ingest` and `jason library` ([document-tools.md](document-tools.md), [ingestion-and-review.md](ingestion-and-review.md)) | a folder, zip, or Drive folder into the library: inventory, dedupe by hash, read, classify, propose a folder | the **classification chain** for each part (name rules, phrase rules, the local model only when asked; a miss stays a miss) and the library rows. The batch hands parts to this intake and does not classify by itself |
| Key documents ([key-documents.md](key-documents.md)) | one entry per recorded instrument, a link, an upload | the link for a part that is a recorded instrument (the recording number is asked per part) |
| Segmentation and preflight ([document-segmentation.md](document-segmentation.md), [pdf-preflight.md](pdf-preflight.md)) | the cue table, the walk; the per-page facts | the **measurements** and the **suggestion count** for every file, computed once, by hash |
| The job queue ([jobs.md](jobs.md)) | lanes by resource; one worker per community; a write runs only with `--confirm NAME` | how the batch runs its measuring, its OCR, and its model pass without anyone waiting |
| The vendor attachment filing ([drive-sync-rules.md](drive-sync-rules.md) for the library's Drive side; `jason.tasks.vendor_files` for the rule shape) | a kind-then-source rule list, a plan first, no duplicates by content, a link back to the source in the file's properties | the **shape of the Drive filing plan** (section 5.4) |
| `jason.limits` ([instance-limits.md](instance-limits.md)) | bounded, layered limits with a reason | the new `archive.*` limits (section 7.6) |

What is new: the **batch** and its **box** and **item** records with a state machine; the **provenance** each resulting document carries; the **triage** screen; the **fast lane** and its contact sheet; the **batch actions**; the **verify** pass and the audit trail; and the way the splitter shows where it is in a box.

## 1. The unit of work, and provenance

### 1.1 What a unit is

| Unit | What it is | When a person picks it |
|---|---|---|
| **Box** | one top-level folder of scans, the physical box it came from. The default unit | almost always. A box is the natural stopping point and the natural thing to label |
| **Folder** | any subfolder, or a chosen list of files from a folder | a box scanned in several sessions with several folders; a re-scan of a few files |
| **Scan session** | files scanned together, as the scanner's output folder or the modified-time span groups them | when the folders do not follow the boxes. A person groups files into a box by hand, and the grouping is a recorded act |
| **Batch** | one run of work over one or more boxes: the unit of progress, resume, limits, and audit | always. A batch holds the boxes a person chose for this stretch of work |

A **batch** is the working unit and a **box** is the provenance unit. One batch can hold Box A and Box B; the resulting documents carry the box, not the batch.

### 1.2 What is recorded, and by whom

Nothing about where a document came from is guessed. Each fact has an author.

| Fact | Kept as | Who or what makes it |
|---|---|---|
| The box's **label** ("Box A") | `label` on the box | a **person** types it, with their name and the day. It is the only name for the box that appears on a document. If nobody labels a box, the screens say "unlabeled folder" and the library shows the folder as found |
| The **folder as found** | `folder_recorded` (the path or Drive folder name at the time of the scan) | jason, read-only. It is a fact about the scan, kept as found, and shown only in the private view |
| The file's **identity** | `sha256`, `size`, `pages` | jason, from the bytes |
| The file's **position** in the box | `position` and `order_basis` | jason sorts by the stated basis (`name`, `modified`, or `person`). The doc says which. **A person confirms that the order is the order of the pile** (one yes for the box, "The files in Box A are in pile order, by name"). Until they do, the position is "listed 14th by name", not "the 14th in the pile" |
| A document's **page range** in its file | `pages {from, to, of}` | the cut a person confirmed in the splitter |
| A document's **place among the parts** | `ordinal` ("part 3 of 7") | the splitter, from the confirmed boundaries |

### 1.3 How provenance appears downstream

A document made by an archive split carries one **origin record**. It is a private fact (`data/`, never checked in). A history line, a log, a URL, or an error message names the item id and the counts, never the folder or the file name.

```
origin
  batch         <batch id>
  box           {id, label, labeledBy, labeledAt}          # label is the person's words
  folder        <the folder as found>                      # private view only
  item          <item id>   source {sha256, pages: 412, name_recorded}     # name private view only
  position      {file: 14, of: 52, basis: "name", pileOrder: true|false}
  pages         {from: 15, to: 22, of: 412}
  ordinal       {part: 3, of: 7}
  confirmedBy   {name, at}
  supersedes    <part id>                                  # only on a re-split (section 6.3)
```

| Where | How the origin appears |
|---|---|
| **The library** (`library.db`, the library explorer) | a new source word `archive` for the filter chips (beside `payhoa`, `drive`, `gmail`, `ingest`). A row says "Box A, file 14, pages 15-22" in its detail, and the explorer's filters take a box. The `origin` is a block on the document's row, not a change to its kind or folder. A confidential file is masked as everywhere else |
| **Record slots** | the pin carries the origin beside `splitFrom` (record intake already writes `splitFrom`, `pages`, `segment`, `confirmedBy`, `ordinal`). A slot's holder row reads "from Box A, file 14, pages 15-22". A part filled into a slot is still pinned only by a person's confirm |
| **The Drive filing plan** (section 5.4) | each planned upload keeps the origin in the file's properties (`archiveBatch`, `archiveItem`, `archiveSha256`, `archivePages`, `archiveBox`) and its description ("Box A, file 14, pages 15-22"), the way a vendor attachment keeps its message. The label is the person's word; the folder as found is not written to Drive |
| **A packet or a citation** | the address of a part stays `library:ID#p15-22`; the origin is what a reader follows from it to the pile |
| **A search result** | `library_search` can say "from Box A" for a hit and take `box` as a filter. Nothing about the box changes how a document is classified |

**Never invented.** A box label with no person's name on it is refused. A "position in the pile" without the box's pile-order confirmation says what it is ("listed 14th by name"). A document whose source cannot be found any more (a file deleted from the folder) keeps its origin with `sourceGone: true`.

## 2. The triage screen

Triage is the screen a person lives in. It answers four questions at a glance: what is in this box, what is done, what is next, and where do I stop for the day.

### 2.1 The queue

One table, one row for every file in the chosen box or folder. It reads from the batch store and the facts cache; opening it measures nothing.

| Column | What it shows | Source |
|---|---|---|
| `#` | the position by the stated order | the item |
| File | "Item 14" and, in the private view, the file name; a confidential file is masked | the item |
| Pages | count | the PDF's page tree |
| Size | bytes in words ("3.1 MB") | the file |
| Text | `text` (a layer), `partly`, `none` (image only), with the suspect share in the detail | the facts |
| Preflight | up to three chips: **blank** pages (n), **sideways** (n), **quality** (low dpi, skew, mixed sizes) | the light fact pass; the full preflight is queued, never required |
| Expect | "1 document" or "about 5 starts", with the band of the highest suggestion | the rule pass summary, by hash (section 3.1) |
| Status | one of the six words below | the state machine |
| Next | the one act the row offers ("Accept as one", "Open", "Apply", "File") | the state |

**Status words**, the ones a person reads, each mapped from the internal states (section 7.2):

| Word | Means |
|---|---|
| **new** | in the folder, not looked at by a person |
| **in progress** | a draft exists, or the file is open |
| **split** | a person confirmed the cut (or accepted it as one document); the new files may or may not be written yet |
| **filed** | the parts are in the library, a slot, or held, as the person chose |
| **needs a person** | something stopped the file, with the reason in words (unreadable, encrypted, over the page limit, a collision, a rejected cut, a question) |
| **skipped** | a person set it aside, with a reason (a duplicate, a blank run, "not for us") and their name. A skipped file is shown, counted, and can be reopened |

### 2.2 Sort, filter, and search

Sort by position (the default), pages, size, status, expected starts, and flags. Filters: status; **short** (1-3 pages), **long** (over `archive.long_file_pages`, default 40); no text layer; has blank pages; has sideways pages; has a High suggestion; duplicate of another item; edited by someone else. A chip shows how many files match each filter given the others, as the library explorer does. Searching by a file name works only in the private view and is a POST, never a web address. Filters are a view, not a state: they never change an item.

### 2.3 The "next file" flow

The aim is that a person never decides what to do next.

- **Next** is computed: the first file in the queue's order whose status is `new` or `in progress` for the person, skipping files another person has open. A person can switch the order to "shortest first", "longest first", or "needs a person first".
- Opening a file opens the splitter on its session at `#/setup/split/<session>?batch=<id>&item=<n>`. The splitter's toolbar shows the batch strip (section 8).
- **Done, next** (the splitter's `D`) confirms the review as it stands, marks the item `split`, and opens the next file. A file with an unresolved flag stays on the review until the person deals with it or marks it **needs a person** with a note.
- Returning to triage puts the cursor on the file just left.

### 2.4 Keyboard throughput

Triage is operable without a pointer. Keys do not collide with the splitter's (its map is in [pdf-splitter.md](pdf-splitter.md), 5.6).

| Key | In triage |
|---|---|
| `J` / `K` or arrows | next / previous row |
| `Enter` | open the row's file in the splitter |
| `1` | **accept as one document** (a short, unflagged file; section 4) |
| `S` | skip, then asks for the reason in one line |
| `H` | needs a person, then asks for the note |
| `X` or `Space` | select the row; `Shift` and arrows extend; `Ctrl+A` selects what the filter shows |
| `B` | open the **batch actions** menu on the selection (section 3) |
| `F` | the fast lane for the selection or the filter (section 4) |
| `/` | focus the filter box |
| `?` | the key map |

In the splitter, two keys are added: `]` and `[` for the next and previous file, and `D` for done, next. `[`, `]` and `D` are free in the splitter's map.

### 2.5 Progress and resume

A **progress bar for the box** counts files, not pages, and also shows the pages beside it, because the work is in the pages:

```
Box A   [########------------]  41 of 96 files  ·  1,180 of 2,950 pages  ·  about 2 h 10 min left
         split 38 · filed 3 · in progress 1 · needs a person 4 · skipped 2 · new 48
```

The time left is an estimate from this person's pace so far (a moving average of seconds per page and per file), shown as a range, and absent for the first five files. Resuming tomorrow is automatic: opening the batch lands on **Continue where you stopped** (the last item, with its draft, undo stack, and scroll position, which the splitter already keeps), and the screen says what changed since: "Measuring finished for 62 files overnight. 3 files changed on disk." Nothing to restart; nothing re-measured; a draft is kept `split.draft_days` after its last change.

## 3. Batch actions: safe by construction

Every batch action has the same shape. **jason proposes, a dry run says what it would do and how many, and a person confirms.** None of them cuts, files, or writes a document by itself.

| Action | What it does | Writes | The dry run says | Confirm |
|---|---|---|---|---|
| **Measure all** | runs the light fact pass for every file: page count, text layer, blank, sideways, size, the 16 by 16 pictures | the facts cache by hash (no document) | "62 files to measure (3,100 pages); 0 already measured; about 12 min; local lane" | `--yes --by`; no signature needed, since it only reads |
| **Run the rule pass for all** | the suggestion pass on every measured file, so triage shows the expected starts | suggestions in the draft, no boundary | "58 files; 41 expect no extra starts; 17 expect 1 to 30 starts" | same |
| **Queue OCR for chosen files** | one local-lane job for each chosen image-only file | the OCR text beside the library's text, by hash | "12 files, 940 pages with no text, 9 already read, queue at most `archive.ocr_queue_max`" | `--yes --by`; the count is typed back for more than 25 files |
| **Run the model pass for chosen files** | the page-one question on the unsure pages, on the local model | model suggestions marked "model only" | "6 files, 140 candidate pages, about 90 s each, the GPU lock held; preflight first" | `--yes --by` |
| **Accept as one document** | marks the chosen short, unflagged files as one document each (section 4) | the item's confirmed plan: one segment | "37 files, 61 pages; 0 with flags; first pages shown" | `--yes --by`, typed count above 50 |
| **Apply the splits** a person confirmed | writes the new files for every item whose cut was confirmed | the new files (the splitter's one writer) | per item: parts, pages, collisions, duplicates, rotations; totals; "0 collisions, 3 duplicates skipped" | `--yes --by`, and the typed count |
| **File the parts** as held, library, or slots | hands the new files to the chosen destination (section 5) | held store, library rows, or pins | the splitter's own `filing` counts, per part | `--yes --by` |
| **Reopen** | puts a `split` or `filed` item back in progress, with its draft | the state | "this item's files stay; a re-split supersedes them" | `--by` |

**What a batch action never does.**

- Cut a file nobody confirmed. There is no setting, schedule, or job that applies a split ([pdf-splitter.md](pdf-splitter.md), 8).
- Change an original, in the folder, in Drive, or in the library.
- Accept a suggestion on a person's behalf. "Accept all above" stays in the splitter and works on one file. A batch never reaches into a draft to accept.
- Skip the typed count. Past a threshold (`archive.confirm_count`, default 25 items or 500 pages), the dry run's count is typed back, because a bulk act that a tired person clicks through is the failure to design against.
- Run on a stale item. An item whose file changed on disk is `stale` and left out of every batch action with the reason.

**Atomic per item, not per batch.** An apply over 40 items writes each item's parts one item at a time, each by the splitter's own atomic write. A failure leaves the items done and reports the one that failed; the batch action can be run again, and it finds the finished items already done by hash (section 7.3). Nothing is rolled back, and nothing is deleted.

## 4. Files that need no splitting: the fast lane

The median file is 4 pages. A file of 1 to 3 pages is almost always one document, and spending a screen on it costs more than the decision is worth. The fast lane exists so a short file is one tap, and a screenful of them is one tap too.

### 4.1 What qualifies

A file qualifies for the fast lane when **all** of these hold. The rule is a row in a table, so it can be tuned and tested.

| Test | Default |
|---|---|
| pages | at most `archive.fast_lane_max_pages` (3) |
| the rule pass | no suggestion at Medium or better inside the file |
| flags | no page-number restart, no size change, no blank page between content pages, no sideways page left unresolved |
| readable | the PDF opens, has no password, and each page draws |

A second tier, **"looks like one document"**, takes a longer file (4 to `archive.likely_one_max_pages`, default 12) when the evidence is consistent: the printed page labels run "1 of N" to "N of N" with N equal to the page count, or the running header repeats on every page and the rule pass finds no start. It is offered, not assumed, and it is shown with a stronger check (4.3).

### 4.2 Accept as one document, in one tap

In triage, `1` on a qualifying row, or the **Accept as one** button on the row, makes the file one segment. It is the same record the splitter would make (a single segment from page 1 to the last page, `confirmed` by the person), so the file passes through apply, filing, and classification exactly like a cut file. It differs in one thing: **a one-segment file whose pages are unchanged needs no new file.** Apply in that case does not copy the pages; it records the original file as the document, with its origin ("Box A, file 14, all 3 pages"), and files **the original bytes** (the same hash). That also means no duplicate bytes are created for a file that was already one document.

### 4.3 The contact sheet

For many short files, a tap per file is still slow. The fast lane's screen is a **contact sheet**: the first page of each qualifying file as a `small` picture, 12 to a screen on a desktop and 4 on a phone, in the queue's order.

```
Fast lane · Box A · 37 short files · 3 screens                       [Accept the rest of this screen: 12]
+--------+ +--------+ +--------+ +--------+       Each card: first page, "Item 14 · 2 pages"
| page 1 | | page 1 | | page 1 | | page 1 |       and a small last-page picture on hover or focus.
| 2 pp   | | 3 pp   | | 1 p    | | 3 pp   |       A card has three acts: [Needs a look] [Skip] [Fix sideways].
| Item 14| | Item 15| | Item 16| | Item 17|       A card the person leaves alone is accepted
+--------+ +--------+ +--------+ +--------+       when they press "Accept the rest".
```

- **Accept the rest of this screen** is a bulk act with its count in the button. A card marked "needs a look" is left out and goes to the splitter's queue. Arrow keys move between cards, `Enter` opens the card in the splitter, `N` marks needs a look, and `A` accepts the rest.
- The sheet shows the **first and last page** of each file (hover or focus on a pointer screen; a second picture in the card on a larger screen). A boundary hidden inside a 3-page file shows up as a last page that looks like a new document's first page.
- The sheet is itself a flag-checked view: a card shows its flag chips, and a flagged card is not accepted by "accept the rest".
- Accepting a screen is one undo step per screen.

### 4.4 What the fast lane risks, and the guard

A short file might hold two documents. The guards are the tests above (no suggestion, no restart), the last-page picture, and the **spot check** (section 6.2), which samples accepted-as-one files on purpose. If a spot check finds a hidden boundary, the lane's tests are tightened (a lesson is recorded and the rule row changes), and the other accepted files are re-sampled.

## 5. After the split: classify, dedupe, link, file

Nothing in this section is new machinery for cutting. It is the sequence the parts go through, with one rule: **a plan first, a person confirms the writes.**

### 5.1 Classification

Each new part goes through the library's intake (`filing: library`), which calls `classify_document` in the order AGENTS.md sets: the profile's name rules, then the PayHOA-folder and library-path rules, then the phrase rules on the first pages, then a local model **only when a person asked**. **A miss stays a miss.** A part's working name is neutral ("Box A, file 14, part 3 of 7 (pages 15-22)"); the splitter never invents a title from content. The file name of the *source* is not a classification hint unless the profile's name rules say so.

- The model pass for classification is a batch action (section 3), runs on the local lane with the GPU lock and `local_ai.preflight`, and answers from the closed list of kinds. An answer under the confidence floor is dropped.
- A part's **kind** is a guess until a person confirms it (the library's reading is evidence, not a pin).
- The shelf and the Civil Code 5200 record come from `documents.PROFILE` for the kind, as for any document.

### 5.2 Dedupe

| Check | Against | Result |
|---|---|---|
| **Exact** (SHA-256 of the part) | the library, the intake store, the pinned files, and the other parts of this batch | not written again; "already filed as ..." with the existing file; the new origin is added to the existing file as a second origin (the same file in two boxes is worth knowing) |
| **Near** (the page word-hash or 16 by 16 mean-hash set) | other parts across the **whole batch** and the library | flagged, with the two first pages side by side and the overlap share ("14 of 15 pages repeat"). A person chooses: keep both, keep one and point to it, or mark as a version. jason does not fold by similarity |
| **Same bytes, two items** | other items of the batch | the second item is `duplicate` of the first and is never split twice (section 7.3) |

The near-duplicate index across files is new: a small table of page hashes by item (`data/archive/pagehash.db`; about 32 bytes a page, so 6,000 pages is under 1 MB). Within one file the splitter already flags near-duplicate segments; the batch extends the same test across files, because a pile often holds a document and its copy.

### 5.3 Linking to record slots and key documents

The kind and the text suggest where a part belongs, and jason **offers** it:

- A part read as a kind that fills a record slot is offered to that slot ("reads as the minutes of a board meeting; the slot for minutes by period holds none for that period"). A person pins it; a slot that already holds a file is a collision, and the part goes to held. A series slot takes the period; a repeating key document takes its recording number.
- A part read as a recorded instrument is offered to the key documents' list for the link, with the recording number asked.
- A part that fits no slot is filed by kind and source in the library, and the slots it could have satisfied are listed in the batch report.
- **A pick is never made by the batch.** The offers are a queue (section 5.5). They are the confirmations queue's "record reading" kind in its existing form.

### 5.4 The filing plan to Drive

Whether the parts reach Drive at all is a decision (section 10, D3). If yes, it follows the rules the vendor attachment filing already keeps, and a plan comes first.

1. **Kind first, then source.** The profile's filing rules (`FilingRule.condition`, kind then named sender or kind of source) give each part its folder path from the filing root. The *source* here is the counterparty the sender directory knows from the first page (`sources.sender_in`), never a name typed into the batch. A part whose kind is a miss goes to an **Unclassified** folder for the box, so the pile is still findable. A document no rule takes goes to the fallback.
2. **A plan, not a write.** `jason archive --file-plan BATCH` writes a plan: for each part, the destination folder (made if needed), the file name, the reason (the rule's condition and the facts, as `Verdict.explain()` gives them), the origin properties, and the dedupe verdict. The plan is a file under `data/archive/plans/`; it changes nothing in Drive.
3. **No duplicates.** A part is not planned for upload when Drive already holds the same content: the same MD5 in the destination or the Drive sync listing, or a file jason filed before, found by `appProperties` (`archiveSha256`). The same content twice in the batch is planned once, from the earliest.
4. **A person confirms the writes.** Applying the plan is a write outside jason's own store, so it follows the pattern of the approvals engine: a plan a person marks, signs, and applies, with a second signature where the board has adopted one for that kind. `jason archive --file-apply PLAN --yes --by NAME`. A broad Drive scope is granted for filing a file a person asks to move; nothing is shared, renamed, or deleted, and the original scan file is not touched.
5. **The link back.** Each upload carries the origin in `appProperties` and its description, so Drive shows where it came from. Each filing is logged in `data/archive/filings.jsonl` with the item and part ids and the Drive file id, never a file name.

### 5.5 The board's review of unclassified parts

A part with no kind, a kind below the floor, or two readers that disagree, lands in the **Unclassified review**, a queue grouped for speed.

- **Grouped by look.** Parts are clustered by the first page's header and layout (the same measures the within-session suggestion profile uses), so ten minutes of one letterhead are ten cards in one group, and a kind chosen for the group applies to the selected cards.
- **Grouped by box and sequence.** The screen can group by box and file order, because a neighbour in the pile often shares a kind.
- A card shows the first page (`small`, `large` on a click), the page count, the origin, and the library's best guess with its tier word.
- The acts: **confirm the kind** (a person's answer, kept as the library keeps it), **set a different kind**, **hold** (leave in Unclassified with a note), **send to counsel** (a board item), **it is a duplicate**. A confirmed kind is a person's answer, and the document is then filed by the plan.
- **Repeated confirmations propose a rule.** When a person assigns the same kind to a group of parts that share a phrase, the batch **proposes** a phrase rule row (a patch for a person to apply to the profile or to the general phrase table), with the examples. It writes nothing. "A new decision is a new rule row."

## 6. Quality control

### 6.1 The verify pass

`Verify this document` is a short screen for one part, to check a cut against the paper:

```
Verify · Item 14 · part 3 of 7 (pages 15-22, 8 pages)
 [the page before: last page of part 2]   [first page of this part]   [last page of this part]   [first page of the next part]
 Checks:   page count 8      printed labels "1 of 8" ... "8 of 8"   (agree)
           first page looks like a first page (title block, date)   (agree)
           last page ends with a signature block                     (agree)
           the next part's first page looks like a first page        (agree)
 [ Correct ]  [ Wrong start ]  [ Wrong end ]  [ Two documents ]  [ Not a document ]
```

The cheap automatic checks, shown beside the pictures, are **evidence for the person**, not a verdict: the printed page labels against the page count; whether the first page has the cues of a first page (a title block, a date, a letterhead, a "page 1" label); whether the page before this part looks like an ending (a signature block, "page N of N"); whether the next part's first page looks like a start. A part whose checks all agree is an easy tap. A part where they disagree is raised first.

### 6.2 Spot checks

- **A seeded random sample** of the confirmed parts in each box, at `archive.spot_check_share` (default 10 percent, never below 5), plus these always: every part from a file accepted as one document in the "looks like one" tier; every part that is more than `archive.long_part_pages` (default 40); every part adjacent to a page a person moved or whose suggestion they rejected; every part on a file where the person's pace was unusually fast (a signal, not a judgment); and every part a verify check disagrees with.
- The sample is deterministic from the batch id (so a person returning tomorrow sees the same sample), and lists its size and why each part is in it.
- A box cannot be marked **done** until its sample is checked or the person records, with their name, why a part was left unchecked. The spot-check share cannot be set to zero (a safety check has no off switch; [instance-limits.md](instance-limits.md) keeps that rule).
- **The result is a rate.** "31 checked, 29 correct, 2 wrong start." A box with a wrong-start rate over `archive.recheck_rate` (default 10 percent) is flagged: "Check more of this box", and the sample widens for it.

### 6.3 Rejects and re-splits

A verify result of wrong start, wrong end, two documents, or not a document is a **reject**. It never deletes a file.

1. The part is marked `rejected` with the reason and the person's name.
2. Its item reopens in the splitter at the rejected range, with the rejected boundary marked and the note shown. The rest of the item's confirmed cut stays.
3. The person re-marks and confirms. Apply writes the **new** parts; each has `supersedes` pointing at the old part.
4. The old part stays in the library and the held store marked `superseded` (hidden by default, shown with "Show superseded"), because something may have cited it. If it was pinned to a slot, the slot shows "the pin was superseded; confirm the new part". The old file's address keeps resolving.
5. A part whose supersession is not yet reviewed appears in the batch's attention list, not in the queue as new.

### 6.4 The audit trail

`data/archive/audit.jsonl` is append-only. Each line is one act: the batch, the box, the item and part ids, the act (`label`, `scan`, `measure`, `suggest`, `accept-one`, `confirm`, `apply`, `file`, `verify`, `reject`, `reopen`, `skip`, `needs-person`, `bulk`), who, when, the counts, and for a bulk act the dry run's numbers and whether the count was typed. **It names no file, folder, or page text.** A person can reconstruct how a given document came to exist: who labeled the box, who confirmed the cut, who applied it, who verified it. `jason archive --audit ITEM` prints that chain. It is the board's evidence that the archive was handled consistently.

## 7. The data model, the surface, and the machinery

Code to come, in the splitter's layout: `jason.community.archive_batch` (pure records and the state machine; reads no file, profile, or service), `jason.tasks.archive_batch` (the store, the scan, the jobs), `jason.tasks.archive_filing` (the Drive plan), `jason.commands.archive`, `jason.web.extra.archive`, and `jason.mcp.archive`.

### 7.1 Records

```
ArchiveBatch   id (random)  label (a person's)  created, by  status: open | paused | done | closed
               roots [ {kind: "drive"|"path", ref, label} ]    # ref opaque; never in a URL
               version (optimistic)  limits (the values in force at creation)
ArchiveBox     id  batch  label (a person's; empty = unlabeled)  labeledBy, labeledAt
               folder_recorded (private)  order_basis: name|modified|person  pile_order: yes|no|unknown (confirmed by, at)
               counts {files, pages, by_state}  sample (the spot-check ids)  status: open | checked | done
ArchiveItem    id  box  sha256  size  pages  position  name_recorded (private)
               state (7.2)  reason  session (split session id)  parts [part ids]
               facts {text, blank, sideways, quality, expect_starts, band}  flags
               duplicate_of  supersedes  seen {first, last}  by, at   version
ArchivePart    id  item  pages {from, to}  ordinal  sha256  kind (guess|confirmed)  filed {where, id}
               verify {state: unchecked|ok|wrong, by, at}  superseded_by
```

The store is `data/archive/archive.db` (SQLite, write-ahead log), because a box of 270 items is written to by a job and a person at once. Each row has a `version`, and every write is one transaction that checks it, so a stale write is a conflict, not a silent overwrite. The batch-wide acts (scan, apply, file) take the store lock `archive-<profile>` for their length. A draft's boundaries still live in the splitter's session file; the item points at the session by id.

### 7.2 The item state machine

```
              scan
   (folder) -------> new --measure--> measured --rule pass--> ready ----open----> in_progress
                       |                  |                     |  \                |   |
                  unreadable         no text/OCR              accept-as-one       confirm  needs_person
                       v                  v                     v                    v        |
                 needs_person        ocr_queued  ------->   accepted_whole -----> confirmed <-+
                                                                                       |
                                                                                  apply (dry run, then yes)
                                                                                       v
   skipped <--(person)-- any open state                                             split
   duplicate <--(same sha as another item)                                             |  classify, dedupe
   stale <--(bytes changed on disk)                                                    v
   gone <--(file removed from folder)                                               filed ---verify---> verified
                                                                       rejected <-- (verify: wrong)  --> in_progress (re-split)
```

| From | To | Caused by | Guard |
|---|---|---|---|
| (found) | `new` | `scan` | a PDF that opens; otherwise `needs_person` with the reason |
| `new` | `measured` | `measure` job | facts cached by hash |
| `measured` | `ready` | `rule pass` job | `split.suggest_enabled`; otherwise `ready` without suggestions |
| `ready`, `new` | `accepted_whole` | person: accept as one | qualifies for a lane (section 4) |
| `ready`, `measured` | `in_progress` | person opens the file | a session is created or resumed |
| `in_progress` | `confirmed` | person: Done, next | the review's totals add; flags dealt with |
| `confirmed`, `accepted_whole` | `split` | apply | dry run first, confirm; atomic per item |
| `split` | `filed` | file the parts | destination chosen; collisions held |
| `filed` | `verified` | verify | a person's check |
| `filed`, `verified` | `rejected`, then `in_progress` | verify: wrong | the old part kept, `superseded` on re-apply |
| any open | `skipped` | person | a reason and their name |
| any | `stale` | the scan sees different bytes | never split; the new bytes are a new item |
| any | `needs_person` | a job or a guard | reason in words; cleared by a person |

The six **status words** of section 2.1 are a projection: `new` (new, measured, ready), `in progress` (in_progress, confirmed, accepted_whole, ocr_queued), `split` (split), `filed` (filed, verified), `needs a person` (needs_person, rejected, stale, gone), `skipped` (skipped, duplicate). A stricter word is shown in the detail.

### 7.3 Resumable and idempotent by file hash

- **The item's identity is the file's SHA-256.** A scan of the folder matches by hash: the same bytes at a new path are the same item (the path is updated); the same bytes in two boxes are one item with a second place, flagged as a duplicate for a person; **different bytes at a path that held another file** is `stale` for the old item (kept, with its work) and a new item for the new bytes.
- **Every job is safe to run twice.** Measuring and the rule pass read the facts cache by hash and do nothing for a file already measured. OCR skips a file whose text is already read for that hash. Apply on an item whose confirmed boundaries already produced these exact parts (determinism of the splitter) finds each part's bytes already present and reports "already done".
- **Resume is the same code as start.** `jason archive --resume BATCH` re-scans, queues what is missing, and prints the same triage a fresh batch would. A crash leaves a job marked running; the next worker records it stopped and queues a read again (jobs.md). A write fails and waits for a person.
- **Nothing is deleted by a re-scan.** A file removed from the folder becomes `gone` (kept, with its work and origin); a person decides.

### 7.4 Commands

Dry run by default; `--yes` writes; `--by NAME` is required for any act that is a person's. Conventions follow `jason split`, `jason records`, and `jason ingest`.

```
jason archive --open SOURCE --box LABEL --by NAME           dry run: what a scan finds (files, pages, bytes, what is already known)
jason archive --open SOURCE --box LABEL --by NAME --yes    create the batch and box; scan; queue measuring
jason archive                                              the batches and their progress
jason archive BATCH                                        the triage table (--status, --box, --filter, --sort, --json)
jason archive BATCH --confirm-order BOX --basis name --by NAME --yes   the pile-order confirmation
jason archive BATCH --measure [--items ...]                dry run; --yes --by queues jobs
jason archive BATCH --suggest [--model] [--items ...]      dry run; --yes --by queues jobs
jason archive BATCH --ocr --items ... [--yes --by]
jason archive BATCH --accept-one --items ... [--yes --by]  the fast lane's act, with its dry run
jason archive BATCH --apply [--items ...] [--filing held|library|slots] [--yes --by --expect COUNT]
jason archive BATCH --file-plan                            write the Drive plan (reads only)
jason archive --file-apply PLAN --yes --by NAME
jason archive BATCH --verify [--sample | --items ...]      the sample, and the checks (reads only)
jason archive BATCH --reject PART --reason TEXT --by NAME  start a re-split
jason archive BATCH --skip ITEM --reason TEXT --by NAME
jason archive BATCH --audit [ITEM] [--json]
jason archive --resume BATCH
jason archive --report BATCH                               counts, pace, the sample's rate, unclassified, collisions
```

`--expect COUNT` is the typed count: the command refuses when the dry run's count is different, so a script cannot apply a different set than a person saw. A command that writes can be queued as a job only with `--confirm NAME` (jobs.md), and the worker never adds `--yes`.

### 7.5 API and MCP

| Route or tool | Kind | What |
|---|---|---|
| `GET /api/archive-batches` | read | the batches with counts; box labels are the person's words |
| `GET /api/archive-batch?id=` | read | one batch: the boxes, the counts, the pace, the sample, the limits |
| `GET /api/archive-items?batch=&box=&state=&sort=&page=` | read | the triage rows, 50 a time with a `next` token. A file name appears in the private view only. No name in a web address: a name filter is a POST |
| `GET /api/archive-item?id=` | read | one item with its facts, flags, parts, origin, and audit lines |
| `GET /api/archive-fast?batch=&box=` | read | the fast lane's cards (qualifying items and their picture ids) |
| `GET /api/archive-review?batch=` | read | the unclassified review's groups |
| `POST /api/write/archive/<batch or new>` | write | `act`: `open`, `label`, `confirm-order`, `measure`, `suggest`, `ocr`, `accept-one`, `apply`, `file`, `file-plan`, `file-apply`, `verify`, `reject`, `skip`, `needs-person`, `reopen`, `resume`. Each takes `dryRun`; a write needs `confirm: true`, the signed-in person as `by`, and the typed `expect` count over the threshold |
| MCP `archive_status`, `archive_item` | read-only, board profile | the batch's counts and the item's state, with the caveat that a count is progress and not a finding, a reading is evidence and not a pin, and a confidential item is masked unless asked. No MCP tool opens, measures, accepts, applies, or files |

Pictures are the splitter's (`/api/split/thumb`), reached through the item's session. The fast lane and the verify screen ask for the first and last page of each part by the session and page, never by a name.

**Loaders and their gates.** Every new loader is listed in `tests/fixtures/loader_gates.json` or `tests/test_loaders_are_gated.py` fails. The proposal:

| Loader | Gate | Why |
|---|---|---|
| `archive-batches`, `archive-batch`, `archive-items`, `archive-item`, `archive-fast`, `archive-review` | `p2` | the box labels, the folder names, the page counts, and the pile are the association's private record; the owner view is refused with 403 |

The write routes go through the write guard (`by` required; never `jason`), the owner view refused, and the history line holds the batch, item and part ids and counts only.

### 7.6 Limits (`jason.limits`)

Registered as full records (key, default, bounds, reason, refusal words, enforcement points). A switch that turns a safety check off does not exist.

| Key | Kind | Default | Range | Enforced at |
|---|---|---|---|---|
| `archive.max_items` | count | 500 | 10 to 5,000 | opening or rescanning a batch: the queue's size |
| `archive.max_pages` | count | 20,000 | 500 to 100,000 | the same: pages across the batch |
| `archive.measure_concurrency` | count | 2 | 1 to 8 | the measuring jobs running at once on the local lane |
| `archive.ocr_queue_max` | count | 100 | 1 to 1,000 | OCR jobs queued by one batch action (above `split.ocr_queue_max`, which still bounds each apply) |
| `archive.model_pass_max` | count | 25 | 1 to 200 | files in one model-pass request (the GPU lock serializes the rest) |
| `archive.fast_lane_max_pages` | count | 3 | 1 to 10 | which files qualify for the fast lane |
| `archive.likely_one_max_pages` | count | 12 | 4 to 40 | the "looks like one document" tier |
| `archive.long_file_pages`, `archive.long_part_pages` | count | 40 | 10 to 500 | the "long" filter; the spot check's always-sample |
| `archive.confirm_count` | count | 25 items | 5 to 500 | the typed-count threshold for a bulk write |
| `archive.spot_check_share` | percent | 10 | 5 to 100 | the share of parts sampled; **cannot be set to zero** |
| `archive.recheck_rate` | percent | 10 | 1 to 50 | the wrong-start rate that widens a box's sample |

`split.max_pages`, `split.max_parts`, `split.thumbnail_cache_bytes`, `fetch.max_bytes`, and `upload.max_bytes` still apply to each file. `archive.max_pages` caps a batch's queue, not a single file. A refusal is told in words, with the limit and the amount, as in [instance-limits.md](instance-limits.md).

### 7.7 Jobs and lanes

| Work | Lane | Guard |
|---|---|---|
| Folder scan, hashing, the page-tree reading | the Drive read is `google`; a path scan is `local` | read-only; a Drive file's bytes are fetched once, to the splitter's copy, under `fetch.max_bytes` |
| Measure, the rule pass, the near-duplicate hashing | `local` (CPU) | `archive.measure_concurrency`; no model, no GPU lock |
| OCR of image-only pages | `local` | `tasks.library_ocr` engines (Docling with RapidOCR, Tesseract); idempotent by hash; at most `archive.ocr_queue_max` |
| The model pass (page one questions, or classification) | `gpu` | `local_ai.preflight` first and fails fast on the CPU or short of commit; the GPU lock for each request; the model unloaded after |
| Apply, filing | a person's command (in the console, a job in their name) | `--yes --by`; the store lock; the temp-drive guard |
| The Drive filing apply | `google` | the signed plan; never retried automatically |

One worker per community. Overnight work is queued by day: measuring first, then the rule pass, then OCR, then the model pass, so a person starting in the morning sees triage fully populated and can start with the box's longest file.

### 7.8 Temp drive, locks, confidential masking

- **Temp-drive guard.** A fetch to the splitter's copy, a thumbnail write, a plan file, OCR scratch, and a part's write all go through the configured temp drive (`jason.config.apply_temp_dir`, `storage.require_room`, `tempfile`). With the drive short, the job fails fast with the words and the queue pauses; **the batch never fills the system drive**, and `jason storage --check` is shown on the batch screen when it matters. A batch `--open` dry run reports the bytes it would copy and the room there is.
- **Store locks.** The batch store's batch-wide acts take `archive-<profile>`; the splitter's draft writes keep their own. A store jason reads, changes, and writes back (`records.json`, the library, the intake store) is written under its lock by its own writer, not by the batch.
- **Confidential masking.** A confidential file (a restricted kind, or one the person marks) is shown as "a confidential file (kind: legal)" with no name, no picture, and no text outside the private view, and its pictures are `private, no-store`. The same holds for the contact sheet (a placeholder card with the page count), the verify screen, the unclassified review, and the audit trail (ids only). A box can be marked **confidential** by a person, which masks every item in it. A confidential part is never sent to a remote model; there is no remote model path here.
- **No names in URLs, logs, or errors**: batch, box, item, and part ids and page numbers only.

## 8. How the splitter embeds, and the Setup > Archive screen

### 8.1 The batch in the splitter

When the splitter opens with `?batch=&item=`, the toolbar gains a **batch strip**, one line, above the pages, and a few acts. Nothing in the splitter's own map changes.

```
 Split document   Item 14 of 96 · Box A · 412 pages · Draft saved · 7 segments · suggestions: 9 open
+-------------------------------------------------------------------------------------------------+
| ‹ Prev file [   Box A  41 of 96 files · 1,180 of 2,950 pages  ####-----   ] Next file ›  Done, next |
| Draft v  View v  Mark v  Pages v  Help v   Size ---o--   Undo Redo [Segments 7] [Compare] ... [Review and split] |
+-------------------------------------------------------------------------------------------------+
```

- **‹ Prev file / Next file ›** (`[` / `]`): move to the neighbouring item in the queue's order without closing the work. The draft saves first; a conflict is shown, never overwritten.
- **Done, next** (`D`): confirms the review as it stands, marks the item `split`, and opens the next. It is disabled with its reason while a flag is unresolved ("2 pages are sideways and not decided").
- **Needs a person** and **Skip** are in the **Draft** menu with their note box, so a file that cannot be finished is set aside in two taps and the pile moves on.
- The strip's progress bar is the triage bar; clicking it returns to triage with the cursor on this file.
- On a phone the strip collapses to "Item 14 · 41 of 96" with the same acts in the bottom bar's **Pages** menu, and **Done, next** is the bottom bar's primary button.
- The review step is unchanged (the checkpoint), with one added line: the filing choice defaults to the batch's choice (set once per box), and the confirm text names the item ("Confirm the cut of Item 14 as Jane Example").
- If confirm and apply are one act in the splitter today, the batch needs them separated (confirm records the signed plan, `split`; apply writes). The splitter's status `confirmed` already exists; whether the act is separable is open item D1.

### 8.2 Setup > Archive: the batch list

Desktop:

```
Setup · Archive                                                       [ New batch ]   [ Help ]
+-----------------------------------------------------------------------------------------------+
| Batch                  Boxes   Files   Pages   Progress                       Status           |
| Spring pile            A, B     270    6,000   [#######-----------]  38%      open · continue  |
|   Box A  (labeled by Jane Example, Oct 5)   96 files   2,950 pp   41 split · 3 filed · 4 need a person |
|   Box B  (unlabeled)                       174 files  3,050 pp   not started                   |
+-----------------------------------------------------------------------------------------------+
| Storage: temp drive has room for this batch (est. 1.1 GB).       Queue: measuring 62 of 270      |
| [ Continue where you stopped: Box A, file 41 ]   [ Fast lane: 37 files ]   [ Review unclassified: 12 ] |
| [ Spot check: 14 of 31 done ]   [ Report ]                                                      |
+-----------------------------------------------------------------------------------------------+
```

Phone (one column, the same acts):

```
Archive
Spring pile · open
[###########-------] 38%
Box A · 96 files
  41 split · 3 filed · 4 need a person
[ Continue: file 41 ]
[ Fast lane (37) ]
[ Triage ]
[ Unclassified (12) ]
[ Spot check 14 of 31 ]
Box B · unlabeled   [ Label box ]
Queue: measuring 62 of 270
```

New batch: choose a root (a Drive folder through the existing chooser, or a root from this community's archive roots, which are private facts, never typed in general code; the console takes no server path), pick the boxes (each folder is one), type each label, and read the **dry run** (files, pages, bytes, what is already known, the room on the temp drive). Create runs the scan and queues measuring.

### 8.3 The triage table, desktop and phone

```
Box A · 96 files · sort: position v   filter: [All v] [short] [long] [no text] [blank] [sideways] [dup]   [ / search ]
 #   File      Pages  Size   Text   Preflight         Expect          Status        Next
 14  Item 14     3   0.4MB  text   -                 1 document      new           Accept as one
 15  Item 15    28   3.1MB  none   blank 2, sideways 1  about 5 starts  in progress   Open
 16  Item 16   412  94MB   partly quality: mixed dpi  about 31 starts  needs a person Open
 [ Batch actions on 3 selected v ]    1 of 96 selected · J/K move · Enter open · 1 accept as one · ? keys
```

On a phone a row is a card (position, pages, expect, status, and the one act), the filters are a sheet, and a long press selects.

## 9. Estimates, throughput, and what to automate first

### 9.1 What the box probably looks like

The counts given (about 270 files, 6,000 pages, median 4 pages, a handful over 140) fit this rough shape. **These are assumptions to be replaced by the first measurement (phase 1).** The average is 22 pages a file, pulled up by the long files; most of the files are short and most of the pages are in a few long files.

| Band | Files | Pages | Share of files | Share of pages | Lane |
|---|---:|---:|---:|---:|---|
| 1-3 pages | 105 | 230 | 39% | 4% | fast lane, contact sheet |
| 4-10 pages | 70 | 450 | 26% | 7% | "looks like one" tier, then the splitter |
| 11-40 pages | 55 | 1,300 | 20% | 21% | the splitter, suggestions accepted |
| 41-140 pages | 34 | 3,000 | 13% | 49% | the splitter, the suggestion pass and bulk marks |
| over 140 pages | 6 | 1,100 | 2% | 18% | the splitter, several sittings |
| **Total** | **270** | **6,080** | | | |

The documents inside are unknown; at about 3 pages a document the pile is roughly 2,000 documents.

### 9.2 Throughput targets (to be measured)

| Measure | Target | Notes |
|---|---|---|
| Fast lane, contact sheet | 2 seconds a file, 25 seconds a screen of 12 | plus the exceptions: about 10% of cards need a look at 40 seconds each |
| Short file in the splitter | 30 to 45 seconds a file | open, check, Done, next |
| Splitter on a long file with suggestions | 1.5 seconds a page (a tap and a look at each start; the pages between are not looked at) | the splitter's own tap count is the measure, "taps saved" ([pdf-splitter.md](pdf-splitter.md), 4.7) |
| The same without suggestions | 3 seconds a page | the floor; also the pessimistic case |
| Verify | 6 to 10 seconds a part | the first and last pages side by side |
| Unclassified review | 5 to 8 seconds a part in a group | after grouping by look |
| Dead time between files | under 1 second | because measuring is done before the person sits down |

### 9.3 How long, by the targets

| Work | Files and pages | Time at target | Pessimistic (3 s/page; no group wins) |
|---|---|---:|---:|
| Fast lane (band 1) | 105 files | 12 min | 25 min |
| Short files (band 2) | 70 files | 25 min | 50 min |
| Medium files (band 3) | 55 files, 1,300 pp | 50 min | 90 min |
| Long files (band 4) | 34 files, 3,000 pp | 95 min | 180 min |
| Very long files (band 5) | 6 files, 1,100 pp | 35 min | 70 min |
| **Marking and cutting** | | **about 3 h 40 min** | **about 7 h** |
| Spot checks and verify (sample about 220 of 2,000 parts, plus flagged) | | 40 min | 75 min |
| Unclassified review (a quarter, about 500 parts) | | 50 min | 110 min |
| Filing plan review and apply | | 20 min | 40 min |
| **Person time, all steps** | | **about 5.5 h** | **about 11 h** |

So **four sessions of about two hours**, plus a short pilot session on the smallest box, finish the 6,000 pages at target; the pessimistic case is six sessions. The comparison that matters is the hand method (a PDF tool and page-number arithmetic, naming each file): at about 15 to 20 seconds a page that is 25 to 33 hours, and no provenance. The machine's time is separate and unattended: measuring and the rule pass at 0.1 to 0.3 s a page (10 to 30 minutes for 6,000 pages), OCR of the image-only pages at roughly 2 to 5 s a page (3 to 8 hours overnight if every page needs it), and the model pass on a few hundred candidate pages (about 10 minutes). These numbers come from the splitter's measurements and the library's; they are **estimates** until the pilot box is timed.

### 9.4 What to automate first

By the arithmetic, the person's time splits two ways, and the two want different automation.

- **By pages** (the long files, 67 percent of the pages): the person's time is the taps and the looks at each start. The saving comes from having measuring, the rule pass, and OCR **finished before they sit down**, a **next-file flow with no dead time**, and the suggestions the splitter already has. This is the biggest saving per hour of build.
- **By files** (the short files, 65 percent of the count): the person's time is the per-file overhead, opening, deciding, closing. The saving comes from the **fast lane and the contact sheet**, which turn 175 files into about 15 screens.
- Then the steps after the cut, which scale with documents, not pages: grouping the unclassified by look, and the verify pass's cheap automatic checks.

Build order by saving, then: (1) the batch store, scan, and batch measuring and rule pass; (2) triage and the next-file flow in the splitter; (3) the fast lane and contact sheet; (4) batch apply and library filing; (5) verify, spot check, and the audit trail; (6) OCR and the model pass in batch, near-duplicate across files; (7) the unclassified review's grouping and the Drive plan.

### 9.5 Phased build plan, with go/no-go checks

Every phase ends on a pilot with **one small box taken end to end**, because the estimates above are unmeasured.

| Phase | Builds | Go/no-go check before the next |
|---|---|---|
| **1. Provenance and inventory** | the batch, box, and item records and the store; `jason archive --open`, the scan, the hash identity, the pile-order confirmation; batch measuring and the rule pass on the local lane; the read-only triage table (console and CLI) | The scan of the whole folder takes under 10 minutes; a second scan changes nothing; no original is touched (hash before and after); the real distribution replaces section 9.1's assumption and the estimate is redone. **No-go** if measuring 6,000 pages takes more than an hour (the fact pass needs work first) |
| **2. Triage and the next-file flow** | the status words, filters, keyboard map, the progress bar and resume; the splitter's batch strip, **Done, next**, previous and next; the `confirmed` separation (D1) | A person clears a 20-file box using only the keyboard; the dead time between files is under 1 second at the 95th percentile; resume the next day lands on the right file. **No-go** if marking is not faster than the splitter alone by at least a third on the pilot |
| **3. The fast lane and contact sheet** | qualify rules, accept as one (no new file for a whole-file document), the contact sheet, the "looks like one" tier | On the pilot box, accepted-as-one files are checked against the paper by a person: **no hidden boundary** in a sample of 40, or the rules are tightened and the sample redone. Seconds a file within the target |
| **4. Batch apply and filing** | the dry run and typed count; apply over many items; filing held, library, slots; classification through the library intake; exact dedupe; origin on the library row and the slot pin | Apply of a 30-item batch is idempotent when run twice; a forced failure part-way leaves a retryable state; the origin shows in the library and the slot; originals unchanged. **No-go** if any bulk act could run without its dry run |
| **5. Quality control** | verify, the spot check sample and the box's done gate, rejects and re-split with `supersedes`, the audit trail | A seeded wrong cut is caught by the sample on a made-up box in 9 of 10 trials; a reject never deletes; `--audit` reconstructs a part's history with no file name in it |
| **6. OCR, the model pass, near-duplicate across files** | batch OCR and model-pass actions with limits; the page-hash index; the cross-file duplicate flags | OCR and the model pass run unattended overnight within the GPU lock and the temp-drive guard; no commit-charge failure; the duplicate flags on a made-up set have no false fold |
| **7. The unclassified review and the Drive plan** | grouping by look; proposed rule rows; the Drive filing plan with no-duplicates and the origin properties; the signed apply | A plan shows every destination and reason and writes nothing; applying it twice uploads nothing the second time; the board's review clears the pilot box's unclassified parts at under 10 seconds a part in a group |

Tests are made-up, as the splitter's are: a generated "box" of PDFs built from nothing (a stack of one-page letters, numbered documents, blank separators, a 140-page file, a copy of a file in a second box, an image-only file, an encrypted file, a file changed between scans), with labeled starts. The boundary tests (`python -m jason.community.boundary`, `pytest -k profile`) and the loader gate test run in every phase.

## 10. Risks and open decisions

### 10.1 Risks

| Risk | Why it matters | Guard |
|---|---|---|
| A short file holds two documents | the fast lane files it as one, silently | the tests in 4.1, the last-page picture, the spot check, the lane's rule tightened on a finding |
| A tired person clicks through bulk confirms | a wrong accept scales | the dry run's count typed back, a threshold limit, one undo step a screen, the audit trail |
| The file order is not the pile order | "position" would be a false fact | the order is a stated basis, confirmed by a person for the box, else labeled "listed Nth by name" |
| Hidden estimate error | the sessions are unmeasured | the pilot box is timed, the estimate redone in phase 1 |
| OCR time and the GPU | hours of unattended work contend with the model | lanes by resource, preflight, the GPU lock, queue by day; OCR does not use the GPU lock |
| The temp drive fills | a 6,000-page batch writes copies, thumbnails, and OCR scratch | the guard at every write, a dry run that reports bytes and room, the cache bound |
| Duplicate bytes and near duplicates | a pile holds a document and its copy; the library fills with twins | exact dedupe by hash, near-duplicate flags that a person resolves, a second origin on the one file |
| Confidential content in the pile | the pile is not sorted by confidentiality | masking by kind and by box, `no-store` pictures, board only, no remote model |
| A rule changed mid-batch | the lane's rules or the cue table change while a box is half done | each item records the rule version it was measured under; a change re-measures by hash and shows the difference, never silently |
| The Drive filing writes outside jason | a mistake is in the association's Drive | a plan first, the dedupe, a signed apply, no rename or delete, the original scan untouched |
| Scope creep into a records project | the archive tempts reading content into facts | this page stops at filing; reading a document's duties or conflicts is the existing `jason records` and `jason duties`, on a person's pick |

### 10.2 Decisions needed

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Are **confirm** and **apply** separate acts in the splitter? | confirm = apply today; separate them so "Done, next" signs the plan and a box-wide apply writes | **Separate them.** A person confirms each file as they go, and applies the whole box after a dry run with a count. The `confirmed` status already exists |
| D2 | Is a box the batch's provenance unit and a person's label the only name? | box label by a person; or take the folder name as the label | **A person's label.** The folder as found is recorded and shown only in the private view; an unlabeled box is shown as unlabeled |
| D3 | Do the parts go to **Drive** at all, or only the library and slots? | library only; library plus a Drive filing plan | **Library first (phases 1 to 6); the Drive plan as phase 7.** The library is jason's own store; Drive is a write outside it. Decide after the pilot |
| D4 | Who may apply and file? | any board member with an office; an administrator; the two-person plan | **A signed-in office holder for the library and slots; the approvals plan (marked, signed, applied) for the Drive filing**, with a second signature if the board adopts one |
| D5 | Is a file accepted as one document kept as the **original bytes** or copied? | keep the original (the same hash); copy as a new part | **Keep the original** and record the origin on it; no new bytes for a file already one document |
| D6 | The fast-lane threshold | 2, 3, 5 pages; with or without the "looks like one" tier | **3 pages and the tier to 12**, both limits, tuned on the pilot's result |
| D7 | The spot-check share | 5, 10, 20 percent | **10 percent with the always-sample list**, widened for a box over the recheck rate; never zero |
| D8 | Where the archive's roots are named | typed in the console; the profile's private facts | **The profile's private facts** (`Community.archive_roots()`, an empty default; `data/spec/<profile>/archive.json`), so a general doc and the code name none |
| D9 | The model pass in a batch | never; on request per file; on request per box | **On request**, limited by `archive.model_pass_max`, never automatic, never alone (a model-only suggestion is not selected by a bulk accept) |
| D10 | A near-duplicate across files | flag only; fold automatically | **Flag only.** jason does not fold by similarity |
| D11 | Whether a single pass of sixteen-by-sixteen hashes is enough for the near-duplicate index | the picture hash; the word hash when there is a text layer | **Both, as the splitter's flags do**: words where there is a text layer, the picture otherwise |
| D12 | The renderer license | PyMuPDF (AGPL-3.0); `pypdfium2` | unchanged from the splitter (its open decision 2); the batch makes no new claim |

### 10.3 Lessons and procedure to add when this is built

None are added by this design (it changes no code). When the phases land, record in `src/jason/community/lessons.py` (true of any association) any miss found in the pilots: a fast-lane file that hid a boundary, an estimate that was off, a bulk act that needed its typed count. Add a procedure `archive-intake` to `jason.community.procedures` naming the steps in section 9.5 and the lessons by key, so that `jason sop archive-intake` prints it. Update `docs/README.md`, `docs/cli.md` (regenerated from the parser), `docs/mcp.md` (the tool count, and the board's count in AGENTS.md), `docs/console/README.md`, [pdf-splitter.md](pdf-splitter.md) (the batch strip in 5.11 and the entry point in section 1), and [record-intake.md](record-intake.md) (the origin on a pin) in the same change as the code.

## 11. How this joins the other documents

- [pdf-splitter.md](pdf-splitter.md): the batch opens a splitter session for each file that needs cutting, adds the batch strip and **Done, next** to its toolbar, and calls its `review` and `apply`. It adds no second editor, writer, or renderer.
- [record-intake.md](record-intake.md): a part filled into a slot goes through the one writer, with the origin on the pin; the unclassified review is the confirmations queue's record-reading kind in a batch form.
- [document-tools.md](document-tools.md) and [ingestion-and-review.md](ingestion-and-review.md): classification is the library's chain; the batch calls it and does not copy it.
- [key-documents.md](key-documents.md): a recorded instrument found in the pile links through the key documents' one writer, with the recording number asked.
- [document-segmentation.md](document-segmentation.md) and [pdf-preflight.md](pdf-preflight.md): the facts and the rule pass the triage table summarizes.
- [google-picker.md](google-picker.md): a person's own Drive folder can be chosen through the Picker's redirect form where a community has set it up; otherwise the console's chooser over the server token (the roots in D8) is the way to a Drive box. The batch reads Drive only.
- [pdf-splitter-client-side.md](pdf-splitter-client-side.md): a file chosen on this computer is drawn by the browser; a batch's files are the server's to draw, as a library or Drive file is.
- [jobs.md](jobs.md) and [instance-limits.md](instance-limits.md): the lanes and the `archive.*` rows.
- [drive-sync-rules.md](drive-sync-rules.md): the library's Drive side; the archive filing plan keeps its "plan first, nothing uploaded until a person publishes it" stance.
- [console/security-and-privacy.md](console/security-and-privacy.md): masking, levels, and no names in URLs.
