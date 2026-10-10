# The PDF splitter: a person taps the first page of each document, and jason offers to guess

Status: design (2026-10-10). Nothing here is built. It joins what exists (the preflight's per-page facts, the segmentation walk, the record-intake split and its confirm, the limits registry) and adds one new surface: a page-by-page view of a large PDF where a person marks where each document starts. General for any association: no slot, vendor, folder, or id here belongs to one; samples are "Example Village HOA" and "123 Main St".

## The requirement

The user's words, kept as the requirement:

> Upload or select a PDF from a Drive, or run it as an action "Split document" on any pdf in the library. Show pages as scrollable thumbnails and let a person tap each page that is the FIRST page of a segment, so a large combined PDF (an archive consumed in a stack or pile: documents in order, all combined into big PDFs) is quickly split into multiple documents. Optionally jason or the local model SUGGESTS splits by recognizing common document shapes (first pages with a header, a date, a title, a letterhead; the run of page numbers "Page 2 of 7" restarting; blank separator pages; a change of scan DPI, size, orientation, or color; repeated headers or footers; a change of OCR language or shape), shown as suggestions the person accepts, edits, or rejects, never applied by jason on its own initiative. It needs a design that loads dynamically without being sluggish, with multiple views (an album or tiled grid, a filmstrip with a slider, vertical or horizontal scroll, a compare and zoom pane, a segment list), keyboard and touch (tap, long-press, drag a boundary, shift-click a range), and phone and tablet widths.

Three sentences carry it. **A person decides where documents start; jason only suggests.** **The hundred-page and two-thousand-page file feel the same as the ten-page file.** **The original is never touched.**

## 0. What exists, and what this adds

| Today | What it does | What the splitter takes from it |
|---|---|---|
| `jason preflight` ([pdf-preflight.md](pdf-preflight.md)) | per page: blank, marked, or content; text layer and its suspect share; DPI, codec, colour, rotation, skew; the word layer with boxes from `--ocr` | the **per-page facts** that draw placeholders and feed the suggestions. Never a second measurement |
| `jason segments` ([document-segmentation.md](document-segmentation.md)) | the cue table (`CUES`), the walk with a stack of open documents, `Segment` and `Part` records, a stored reading keyed by SHA-256, addresses `library:ID#p3-7` and `#seg=s2/s2.1` | the **suggestion engine's rule pass** (section 4) and the **nested stack** (a boundary at a level). The splitter adds no second set of cues |
| The record-intake split ([record-intake.md](record-intake.md), step 6 and the `split` act) | a proposal of parts for a scan, a person names each part's slot, a new file of just those pages (`pypdf`) with `splitFrom`, collisions reported, read-back queued under `split.auto_read` | the **apply** (section 6). The splitter is the missing front end: today a person confirms a proposal from a list, with no way to see the pages or move a boundary |
| `jason.limits` ([instance-limits.md](instance-limits.md)) | bounded, layered limits with a reason; `LimitReached` words; the temp-drive guard | three new limits (section 3.8) |
| The GPU lock and `local_ai.preflight` ([document-tools.md](document-tools.md)) | one model job at a time; a job fails fast when the machine is short | the optional model pass (section 4.4) |

The splitter is a **view and an editor over a draft**. It stores boundaries the person chose, suggestions jason made, and the facts it drew them from. It writes no PDF until the person confirms; and then it writes the same record-intake `split` act does, not a second writer.

## 1. Users, jobs, and entry points

### Who and why

| Person | Job to be done | What makes it hard today |
|---|---|---|
| **The records volunteer or secretary** with a box of scans (a prior manager's archive, a stack consumed in order and scanned into a few huge PDFs) | "Cut this 600-page file into the documents it holds, and file each one" | cutting in a PDF tool is page-number arithmetic; the pages cannot be seen at a glance; one slip puts a page in the wrong document |
| **The manager** onboarding an association | "One scan fills five slots on the record checklist" ([record-intake.md](record-intake.md)); confirm the proposal quickly, or fix it | the proposal is a list of page ranges, not pages; a wrong boundary means a rerun |
| **A board member** with a packet or a binder | "Pull the minutes out of this packet" | wants the pages, not the machinery |
| **An administrator** | set how large a file and how much cache the machine may use ([instance-limits.md](instance-limits.md)) | wants a refusal in words, not a stalled browser |

The jobs, in the order a person does them: **look** (see the pages as they were stacked); **mark** (tap each page that starts a document); **check** (read the first page of each part, and fix); **file** (say what each part is, or leave it to the slots); **leave and return** (a 600-page job takes more than one sitting, and a draft keeps).

### Entry points

All of them open the same screen on the same session; they differ only in how the file arrives.

| Entry | Where | The file | Notes |
|---|---|---|---|
| **Upload** | the splitter's "From this computer" tab, or a record slot's upload | bytes held in the upload store, subject to `upload.max_bytes` | an upload not filed anywhere is a **held upload** with a source of "splitter"; it is listed and can be dropped |
| **Pick from Drive** | the same file-source tabs as the record chooser (`DriveChooser`, `PasteDriveLink`; [console/handoff-record-intake.md](console/handoff-record-intake.md)) | fetched by id, subject to `fetch.max_bytes`, kept as a copy keyed by SHA-256 | a Drive file is never modified; the splitter reads a copy |
| **Library action: "Split document"** | on any PDF in the library (the document row's menu, the document kinds shelf, a `Doc` chip's menu) | the library file by id | the action is absent for a non-PDF and for a file over `split.max_pages` (it says so in words, not greyed) |
| **Record intake** | a combined scan in a slot's reading; the confirmations queue's "combined scan" item | the pinned file | opens with jason's **proposal as the first suggestions**; confirming files each part into its slot (section 6.4) |
| **Key documents** | a key-documents row whose picked file is a stack of instruments | the pinned file | a repeating row takes the recording number per part (`#ENTRY`), asked in the review step |
| **Command line** | `jason split FILE` (section 7) | a path or a library id | the same session, listed in the console |

A session is addressed by an id and by the file's SHA-256, so two entries to the same bytes **resume the same draft**, and a changed file (new bytes) starts a new one, with the old draft kept and marked stale.

## 2. The data model

Code to come: `jason.community.split_session` (pure records; reads no file, model, or profile), `jason.tasks.split_session` (the PDF, the store, the apply), `jason.tasks.split_thumbs` (the renderer and cache), `jason.commands.split`, `jason.web.extra.split`. Persistence is a small JSON file for the session and its draft, as the segmentation readings and record-intake readings are; no new database.

### SplitSession

| Field | Meaning |
|---|---|
| `id` | a short random id (not derived from a file name) |
| `source` | the file: `sha256`, `size`, `pages`, `kind` (`library`, `drive`, `upload`, `path`), `ref` (a library id, or a held-upload id; **never a file name**), `confidential` (copied from the library at creation, then re-read at every request) |
| `status` | `draft`, `confirmed`, `applied`, `stale` (the bytes changed), or `declined` |
| `created` / `updated` | time stamps, and `by` (the signed-in person; `jason` for a session the command line made with no person) |
| `facts` | per page: `PageFact` rows (below), copied from the preflight reading by hash so the splitter never re-measures |
| `boundaries` | the person's chosen starts: a set of `Boundary` rows (below) |
| `suggestions` | jason's proposed starts: `Suggestion` rows, never merged into `boundaries` except by a person's act |
| `segments` | derived, not stored: the ranges the boundaries make (below) |
| `history` | the undo and redo stack (below), capped |
| `examples` | the confirmed boundaries as examples for this session's later suggestions (section 4.6) |
| `applied` | after apply: the new files, their SHA-256, their slots, the apply's time and person |

### PageFact (per page, light, from the preflight)

`n` (1-based), `blank` (`content`, `blank`, `marked`), `has_text` and `words` (a count), `suspect_share`, `width` and `height` (points) and `rotation`, `dpi`, `colour` (`bilevel`, `grey`, `colour`), `codec`, `header` and `footer` (the running lines), `label` (a printed page number like "2 of 7" parsed to `(n, of)`), `title` (the top line if it looks like a title), `date` (a date in the opening lines), `lang`, and a 16-by-16 greyscale **LQIP** thumbnail (about 256 bytes) for placeholders. A page with no stored reading yet has only `n`, `width`, `height`, and a `pending` flag; the facts fill in as the preflight runs (section 3.5). Every fact has a single source in the preflight or the segmentation `PageInfo`; the splitter does not duplicate their code.

### Boundary and Suggestion

```
Boundary    page          the first page of a segment (page 1 is always a start)
            level         0 for a top-level document, 1 or more for a document inside one (the stack case)
            by, at        who set it, when
            source        "person" | "accepted" (a suggestion a person accepted; keeps the suggestion's id)
Suggestion  id, page, level
            confidence    0..1, the combined score
            tier          "likely" | "suggested"   (the same words as segmentation: two readers agree, or one)
            signals       [{signal, weight, said}]   e.g. {"page-one", 1.5, "The page is numbered 1 of 7"}
            why           one or two sentences in words, written from the signals
            reader        "rules" | "model" | "rules+model"
            state         "open" | "accepted" | "rejected" | "edited"
```

A suggestion's `why` is the explanation shown beside the page ("Page numbering restarts at 1 of 7; the page before ends a signature block"). It is built from the **signal rows**, so a new cue gets its sentence in the same row that defines it.

### Segments are ranges

A segment is `[start, end]`, with `end` the page before the next boundary at the same or a shallower level. **The first page of the file is always a boundary**; a person cannot remove it (the control says why). Each segment can carry, all optional and all **guesses until a person confirms**:

| Field | Meaning |
|---|---|
| `kind` | a `DocumentKind` from the library's classifier over the first page's title and words; empty on a miss |
| `title` | the first page's title line, or a person's text |
| `period` | for a series (a month, a year) |
| `slot` | a record-intake slot or a key-documents row, with `#ENTRY` where the row repeats |
| `confirmed` | which of these a person has set, so a guess is never shown as a fact |

The kind, title, and slot are **hints for the review step**, not part of the split. A person can split first and never name anything; filing then uses the library classification, kind then source (section 6.4).

### The nested stack

A combined archive is not always flat. An agreement holds a report that holds an exhibit; the walk in [document-segmentation.md](document-segmentation.md) calls that a stack. The splitter keeps it: every boundary has a `level`. A flat split (all level 0) is the default and what most people want. Where the segmentation reading proposes a child document, the splitter shows it as a **nested start** on the page, drawn indented in the segment list.

What apply does with a nested boundary is a choice the person makes **per nested segment**, in the review step, with the choices spelled out:

| Choice | The result |
|---|---|
| **Keep inside** (default for an exhibit) | the child stays in its parent's file; its address (`#seg=s2/s2.1`) is recorded so a citation can find it |
| **Also make a file** | a second file of the child's pages, and the parent still holds them (the parent is not made smaller) |
| **Take out** | the child becomes its own file and the parent loses its pages; the parent's runs are written as the pages before and after, in order |

"Take out" is the only choice that changes how the parent reads, so it asks for a second tap and shows the parent's page count before and after. The parent, if it is split into runs by a child that was taken out, is written as **one file with the runs joined** (pages 1-11 and 20-40), never as two.

### Undo, redo, and autosave

Every change to boundaries, levels, or labels is a **command** on a stack: `add(page)`, `remove(page)`, `move(from, to)`, `level(page, n)`, `accept(id)`, `reject(id)`, `bulk(kind, args, set)`, `label(segment, field, value)`. Undo and redo walk the stack (200 entries; older ones fold into a snapshot). A bulk act is **one** undo step. Undo works after a reload, because the stack is saved with the draft.

Autosave: the browser keeps the draft in memory and sends the command list to the server on a 1.5-second debounce and on page hide, as a `PUT` of the whole boundary set with the version it started from (`version` counter). The server answers with the new version or a **conflict** (another tab or person changed it); on conflict the page shows both and the person picks, never overwriting silently. A draft is kept `split.draft_days` (proposed default 60) after its last change, then a sweep removes the draft and its cache entries, never the original. The save is silent while it works; a failed save is a visible banner ("Not saved. Your marks are kept on this device; retry"), with the marks held in `sessionStorage` as a convenience only.

## 3. The thumbnail pipeline: hundreds to thousands of pages without sluggishness

The failure to design against: a 1,800-page, 400 MB scan opened in a browser that decodes the whole file. The design never gives the browser the whole file.

### 3.1 What runs where, and a recommendation

| Work | In the browser (pdf.js or similar) | On the server (PyMuPDF now in the tree, or pypdfium2; `pypdf` for writing) |
|---|---|---|
| Parse a 400 MB file | needs the whole file or range requests; spends the phone's memory on the page tree and fonts | one pass, once, in a process with room |
| Draw a page at 96, 200, 800 px | runs on the main thread or a worker; a scanned page is one big image to decode | the renderer extracts the page's raster directly (a scanned page is a single image) and scales it, which is cheaper than a full render |
| Reuse | each viewer repeats it | **one render per page and size, cached by hash**, shared by every viewer and every reload |
| Confidentiality and limits | the bytes of the whole file leave the server | only derived pictures of the pages asked for leave, under the access rules (section 8) |

**Recommendation: render on the server, display in the browser as plain images; use no PDF engine in the browser for the grid.** The browser gets small JPEG or WebP pictures with HTTP caching, which every phone decodes fast and cheaply. Reasons: (1) the stack-of-scans case is image-dominant, so the server's cost is a raster scale, not a layout; (2) the browser never holds the PDF, so memory on a phone is a function of the thumbnails on screen, not of the file; (3) a cache keyed by hash is shared and survives reloads; (4) the access rules and confidential masking apply in one place; (5) there is nothing to ship or update in the bundle (a PDF engine in the bundle is several megabytes and a worker).

Where a browser engine would still earn its place: the **compare and zoom pane** at high magnification on a text page, where vector sharpness matters. It is optional and loaded only when that pane opens, one page at a time, fetched through the page-extraction route in 3.6 (a one-page PDF, tens of kilobytes), not the whole file. Phase 1 skips it: the 800 px image and a "show larger" step at 1600 px serve the compare job. This keeps the first release small; the decision is open item 1 in section 9.

**Engine choice on the server.** PyMuPDF is already in the tree as the optional `pdf` extra and is fast at both text and raster. Its license is AGPL-3.0, which matters for a program an association may self-host and for any hosted offering; `pypdfium2` (Apache-2.0 / BSD) renders comparably and is the safe alternative. Recommendation: put the renderer behind one small function `render_page(pdf, n, width) -> bytes` so either engine serves, start with the one already installed, and let the license decision (open item 2) pick. `pypdf` writes the new files (as the existing split does) and is never used to render.

### 3.2 Sizes and formats

| Name | Longest side | Format | Typical bytes | Used for |
|---|---|---|---|---|
| **tiny** | 96 px | WebP (JPEG fallback), quality 55 | 1-3 KB | the grid at a distance, the filmstrip, a scrubbing slider |
| **small** | 200 px | WebP, quality 65 | 5-12 KB | the album grid, the segment list's first-page chips |
| **large** | 800 px | WebP, quality 75 | 60-150 KB | the compare pane, a single-page view, a phone's full-width card |
| **huge** (on demand) | 1600 px | WebP, quality 80 | 250-500 KB | "show larger" only; never prefetched; not cached past the session by default |

A bilevel page renders as 8-bit greyscale at these sizes (anti-aliased by the scale) so text stays readable; a colour page keeps colour. The renderer applies the page's `rotation` (what the preflight measured) **in the picture only**; the PDF is never rotated here (a rotation fix is a separate, explicit act in the review step; section 6.5). Annotations and optional layers are left off, as in the preflight's rendition.

### 3.3 The cache

A hash-addressed store under the data folder:

```
<data>/split/thumbs/<sha256[:2]>/<sha256>/<size>/<page>.webp
<data>/split/thumbs/<sha256[:2]>/<sha256>/index.json     # pages, sizes present, last used, bytes
```

- **Addressed by content.** The key is the file's SHA-256, the page, and the size; a re-upload of the same bytes finds the same pictures. The file's name appears nowhere (section 8).
- **Size bound: `split.thumbnail_cache_bytes`** (section 3.8). When a write would pass it, the cache evicts **least-recently-used files first, never one the open session is viewing, and the `huge` size first of all**; it never evicts a source file or a held upload. A single file's thumbnails larger than the bound fail the request with the registry's words (they are an error to the session, not a silent drop).
- **Temp-drive guard.** A thumbnail write goes through the same guard the upload point uses (`jason.config.apply_temp_dir`, `jason storage --check`): with the drive short of space the render still returns the picture (served once, not stored) and the page shows a "cache full" chip with the reason; it never fills the system drive. Scratch for the render uses `tempfile` on the configured temp drive, as AGENTS.md requires.
- **A cache is not a record.** It is rebuilt from the file; deleting it loses nothing. `jason split --purge` (section 7) and a retention sweep empty it.

### 3.4 Progressive and lazy loading, and the windowed grid

Only the pages near the viewport exist as elements.

- **Windowed virtualization.** The grid knows `N` pages and a fixed cell size per view, so the scroll height is computed with no measuring. It renders the **visible rows plus a buffer of two screens** above and below, recycling elements as the user scrolls. 2,000 pages are about 40 live elements in the grid, not 2,000.
- **Placeholders first.** Every cell paints at once from the **preflight facts**: the page's true aspect ratio (so the grid does not jump when pictures arrive), the 16-by-16 LQIP scaled up with a blur, and a small status glyph with a word for `blank`, `marked`, or `no text layer`. Blank pages are visible as blank before any picture loads. With no facts yet, a neutral card with the page number.
- **Request order is by distance from the viewport**, not by page order, with priority classes: *visible* (tiny or small, whichever the view uses), *near* (the buffer), *far* (prefetch only when idle). A `large` request goes out only for the page in the compare pane, plus its two neighbours on a pointer or arrow movement.
- **Scroll direction and velocity.** The loader watches the scroll offset on animation frames. Below a velocity threshold (a reading speed) it loads **in the direction of travel first** (the next rows ahead before the rows behind). Above it (a flick, a scrollbar drag, the slider), it loads **nothing but tiny**, for the rows under the viewport, and cancels the rest; the small pictures arrive when the scroll settles for 120 ms. This is what keeps a fast scroll through 2,000 pages from queueing 2,000 requests.
- **Cancel on scroll.** Each in-flight request is tied to an `AbortController`; a cell that leaves the window aborts its request. The server stops rendering a page whose connection closed before the render began (a render in progress finishes into the cache, since the next viewer will ask).
- **Batching.** A row of cells that become visible together asks for its pages in **one request** to the batch route (`GET /api/split/<id>/thumbs?pages=40-47&size=small` returns a multipart or a JSON of pictures as data URLs for the tiny size only; small and large stay individual images so the browser's cache and `loading` priorities apply). The tiny size ships as a **sprite strip** (a single image of 50 pages) so the filmstrip and slider scrub from one request per 50 pages.
- **HTTP caching.** Every picture is served with `ETag: "<sha256-prefix>-<page>-<size>-<render-version>"`, `Cache-Control: private, max-age=31536000, immutable` (the content never changes for a hash), and `304` on a conditional request. A render-version in the tag lets a changed renderer invalidate the browser's copies without touching the cache's file names. `private`, because a confidential file's pictures must never sit in a shared proxy.
- **Per-page extraction, not the whole PDF.** The browser is never given the PDF. Where a viewer needs a page as a PDF (the optional vector pane, a "download this page"), `GET /api/split/<id>/page/<n>.pdf` returns a one-page PDF built from the source with `pypdf` or the engine's page copy, and the response is cached by hash and page. HTTP range requests on the *source* are used server-side only (to read a Drive-resident file's pages without fetching everything when the provider allows it; otherwise the fetched copy is the source and `fetch.max_bytes` bounds it).
- **Memory budget on phones.** The ceiling is on **decoded pictures held at once**: at most 150 tiny, 60 small, and 3 large live at any time (about 12 MB of decoded pixels at the sizes above), plus the sprite strips. Elements outside the window drop their `src` (and the browser reclaims the bitmap); the windowing keeps the count to the budget by construction. On a device that reports `navigator.deviceMemory` of 2 GB or less, or a viewport under 480 px, the budget halves and the default view is the list with the tiny size.

### 3.5 Preparing the facts, and the first thumbnails

When a session opens:

1. **Immediately (under 100 ms):** the page count and the first page's size from the PDF's page tree (cheap, no render). The grid draws `N` aspect-ratio cells.
2. **First 40 pages, tiny and small:** rendered inline by the request that asked for them, first. This is what the person sees; the target is under one second (section 5.9).
3. **The rest, in a background job** on the document lane (`jason.jobs`, the same lane the read-back uses; one worker per file, below `models.concurrent_jobs`), in this order: the tiny sprite strips for the whole file, then the preflight facts (reusing a stored preflight reading by hash if there is one, else running the light pass: blank test, size and orientation, text layer present, page label), then the small size for pages the person has not yet scrolled to, then the rule-pass suggestions. Progress shows as a line, "Pages ready: 420 of 1,800", never a modal.
4. **A page whose facts are not ready** is drawn from step 1; its suggestions appear when its facts do.

The light pass is the only new measuring code, and it is a thin reader over `pdf_preflight`'s functions; it measures nothing the preflight cannot be asked for. Full preflight (OCR, skew, defects) is not part of opening a splitter session.

### 3.6 Routes the pipeline needs

| Route | Returns |
|---|---|
| `GET /api/split/<id>/thumb/<n>/<size>.webp` | one picture, ETag, immutable |
| `GET /api/split/<id>/sprite/<size>/<from>-<to>.webp` | a strip of tiny pictures (50 at a time) with a JSON index of offsets |
| `GET /api/split/<id>/page/<n>.pdf` | the single page as a PDF (cached) |
| `GET /api/split/<id>/facts?from=&to=` | the `PageFact` rows for a range, as JSON |

All four resolve the session id to the stored file on the server; none takes a path or a name (section 8).

### 3.7 What it costs

For 2,000 pages: tiny at 2 KB is 4 MB; small at 8 KB is 16 MB; large only for pages looked at (about 100 KB each; a careful review of 100 pages is 10 MB). The whole cache for such a file is about 20 MB, and a 400 MB scan costs the server a few minutes of background work once. The default cache bound (3.8) holds many files of this size.

### 3.8 New limits

Registered in `jason.limits.LIMITS` as full records (key, default, bounds, reason, refusal words, enforcement points), per [instance-limits.md](instance-limits.md):

| Key | Kind and unit | Default | Min - Max | Enforced at | When hit (words) |
|---|---|---|---|---|---|
| `split.thumbnail_cache_bytes` | size, bytes | 512 MB | 32 MB - 8 GB | the cache writer; with the temp-drive guard | "Page pictures are using their whole allowance ({limit}). The oldest were removed to make room; this file's pictures are loading more slowly. Ask your community's administrator to raise the allowance." |
| `split.max_pages` | count, pages | 3,000 | 50 - 10,000 | opening a session; the library action's availability | "This file has {amount} pages; the splitter opens files of up to {limit}. Nothing was changed. Split the scan into smaller files first, or ask your community's administrator to raise the limit." |
| `split.suggest_enabled` | switch | on | on or off | the suggestion engine's entry (rules and model); never the editor | "Suggestions are off for this community. You can still mark each first page yourself." |

Also proposed, smaller (open item 6): `split.draft_days` (time, default 60, 7 to 365) and a use of the existing `split.max_parts` (count) at confirm. `split.suggest_enabled` turns suggestions off, not the splitter; there is **no switch that turns the review step off**, because a switch that turns a safety check off does not exist ([instance-limits.md](instance-limits.md), switches). The model pass (4.4) has its own request flag rather than a limit: it runs only when a person asks.

## 4. The suggestion engine

The engine proposes; a person disposes. It runs **only on request** ("Suggest splits" button, or `jason split --suggest`), or automatically for the *cheap rule pass* on opening when `split.suggest_enabled` is on (the rule pass is deterministic, makes no network or model call, and its result is a list a person can ignore). The model pass never starts by itself.

### 4.1 Signals

The signals named in the requirement, mapped to the code that already reads them. The splitter adds three rows to the cue table and reuses the rest.

| Signal in the requirement | Cue row (existing: [document-segmentation.md](document-segmentation.md)) | Source of the fact | New? |
|---|---|---|---|
| a header, a date, a title, a letterhead on the first page | `title-block`, `title-caps`, `title-soft`, `letter-head`, `addressee`, `recording-stamp` | the text layer, or the OCR word layer's first lines with their size | no |
| the run of page numbers ("Page 2 of 7") restarting | `page-one`, `one-page-document`, `page-one-again`, `numbering-reset`; counter `number-continues` | `PageFact.label` | no |
| blank separator pages | `after-blank` (with the `DUPLEX` rule: where over a quarter of the pages are blank, blanks are backs, not separators) | `PageFact.blank` | no |
| a change of scan DPI, size, orientation, or colour | `size-change`; **new `dpi-change`, `colour-change`** | `width`, `height`, `rotation`, `dpi`, `colour`, `codec` | **new** |
| repeated headers or footers | `footer-change`, `header-change`; counters `same-header`, `same-footer`, `same-title` | the running lines | no |
| a change of OCR language or shape | **new `language-change`**; `lexical-break`, `embedding-change` (the embedder, off by default) | `lang`, the word layer's text, word count, layout | **new (language)** |

A new cue is a new row in `CUES` with a weight, a direction, and its sentence for `why`, never a branch in the splitter. The three new rows start with a low weight (0.3 to 0.5) because a change of scan setting alone is common mid-document (a colour insert in a black-and-white scan). They matter in combination: a scan that changes DPI *and* restarts its page numbers is a boundary almost surely, and the score adds. Their weights are set on the gold set (4.7), not by hand.

### 4.2 The pass order (cheap first)

1. **Facts.** From the preflight reading or the light pass (3.5).
2. **Rule pass.** `document_segments` scores each page's cues; a page at or over `THRESHOLD` (0.8) becomes a suggestion with the cue rows that made it as `signals`. The walk's push and pop moves give the `level`. This is the whole of the **default** engine, runs in seconds for 2,000 pages, and needs no model.
3. **Blank-run rule.** A blank separator where blanks are rare makes the next content page a suggestion (the `after-blank` row, shown with its own sentence).
4. **Model pass (optional, on request).** Only the page-one candidates and the pages the rules were unsure of (below). 4.4.
5. **Combine.** Two readers agreeing make a suggestion `likely`; one alone is `suggested` (the same tier words as segmentation, so a person learns one vocabulary).

Page-number runs and header changes need a *run* (a header is "changed" only when the page before matched the one before it): the pass reads in order, so it is sequential per file, and 2,000 pages are instant at this size.

### 4.3 Confidence and the explanation

Each signal contributes its weight; the suggestion's **confidence** is the logistic of the summed score, calibrated on the gold set so that "0.9" means about nine in ten were real starts (the calibration table is published in the measured section when built). Confidence is shown as a number and as a word band: **High** (0.85 and above), **Medium** (0.6 to 0.85), **Low** (below 0.6, and listed only when the person widens the filter). The explanation is the highest-weight signals in words, at most three:

> Page 12. Page numbering restarts at "1 of 4". The page opens with a date and a letterhead. The page before ends with a signature block.

Never colour alone; the band is a word, a glyph, and a position in the sort order.

### 4.4 The local model pass

- **When.** Only when a person asks ("Check with the local model"), on the page-one candidates the rules proposed plus the pages the rules scored between 0.4 and 0.8 (the unsure band). It is **not** run on every page: the measured model leans to "yes" and on long uniform packets is wrong more often than right (document-segmentation.md, Measured), so it is a second opinion on few pages, not a first reader.
- **How.** The existing model reader: the page's thumbnail at 72 dpi and the question "is this the first page of a new document?", scored from the probabilities of Y and N. It runs after `local_ai.preflight` (fails fast on the CPU or short of commit, with the words), holds the GPU lock, and unloads the model after. At 0.2 to 0.6 s a page, 150 candidates are about a minute and a half; the session shows progress and a **Cancel**; a cancelled pass keeps what finished.
- **What it adds.** A model score lifts the suggestion's tier to `likely` when it agrees with the rules, and adds the model's probability as a signal row ("The local model reads this as a first page, 0.91"). A page the model likes and the rules do not is added as `suggested` only, labeled "model only".
- **Never alone.** A model-only suggestion is never selected by "accept all". The lessons from segmentation stand: alone it is a suggestion.
- **What the person is told.** A line before it starts: "This reads page images with the local model on this computer. Nothing is sent anywhere. It takes about N minutes for M pages." (There is no hosted-model path in this design.)

### 4.5 Presenting suggestions

Suggestions are drawn as **ghost boundaries**: a dashed start marker on the page in every view and a row in the suggestions panel, distinct from a person's solid boundary, with the confidence band and the reason on focus or tap. The person can:

| Act | Result |
|---|---|
| **Accept** (one, or `A` on the focused page) | becomes a `Boundary` with `source: "accepted"` |
| **Edit** (move the marker to the page before or after, or change its level) | a `Boundary`, the suggestion marked `edited`, and the edit saved as an example (4.6) |
| **Reject** (`X`) | the suggestion hides and is remembered as a negative example; "Show rejected" brings it back |
| **Accept all above...** (bulk) | a threshold slider and a count ("Accept 31 suggestions at High or better"), one undo step, never including model-only ones |

Nothing in the draft is applied until the review step; a suggestion alone changes no file.

### 4.6 Learning within a session

A person's confirmed boundaries are **examples for the same archive**, used only inside the session:

- After the person has set or accepted a handful of boundaries, the engine builds a **session profile** from their first pages: the common shape of their first pages (a typical title position and size, a letterhead's lines, the running header's text, the page-number style). It rescores the *remaining* suggestions against that profile: a page that looks like the confirmed first pages rises, a page that looks like a rejected one falls. The effect is shown ("Suggestions updated from your last 8 marks") and the person may switch it off ("Use my marks to improve suggestions").
- The profile is **a small record in the session**, never shared with another session, another file, another community, or the model's training. It is deleted with the session. **Nothing cross-association, and nothing persists in a general table**; a reusable improvement to the cues comes only from a person editing the cue table in code after a measured trial.
- The mechanism is deliberately simple: a similarity of the page's fact vector (label style, header/footer text, title size, page size, language) to the mean of confirmed first pages versus the mean of non-first pages, added as one signal row ("This page looks like the first pages you marked"). No training run, no model.

### 4.7 Evaluation

Following [document-segmentation.md](document-segmentation.md) and `scripts/structure_fuzz.py`:

1. **A gold set of made-up PDFs**, checked in under `tests/fixtures/` (no real scan in a tracked file): generated by a builder in the style of the tests' PDF builders. Archetypes: a stack of one-page letters; a stack of multi-page documents with "Page n of N" footers; a stack with blank separators; a duplex scan with a blank back on every other page; documents of different sizes and a landscape map; a mixed-DPI scan; a stack with a repeated header on every page and one that changes; an agreement holding a report holding an exhibit (the nested case); a recorded-instrument stack with stamps; a file in two languages. Each comes with a label file of the true starts.
2. **A fuzz harness**, `scripts/split_fuzz.py`, in the pattern of `structure_fuzz.py` (`gold`, `variants`, `recover`, `score`, `report`): `gold` builds the made-up files and labels; `variants` degrades them in controlled steps (drop the text layer so only images remain, rasterize at 150 and 300 dpi, skew and speckle, shuffle page-number labels, insert and remove blanks, change the size of a page mid-document); `recover` runs the suggestion engine with any signal removed (`--without dpi,blank`); `score` computes precision, recall, and F1 of the starts, plus the **tap count** a person would still need (the third metric below); `report` writes a table. A real gold set (the private labeled scans) is a separate local run with counts only in the report.
3. **Metrics.** Start precision, recall, F1 at each confidence band; **calibration** (the share of High suggestions that are real); and the number that matters to the person, **taps saved**: with suggestions accepted as shown, how many boundaries remain to add, move, or reject, against tapping every first page from nothing.
4. **Pass bars before a release** (proposed, to be revised once measured): on the made-up archetypes, High suggestions at precision 0.95 or better; the rule pass alone at recall 0.80 or better on the flat archetypes; **no suggestion ever removes or moves a person's own boundary** (a property test); degrading the text layer must lower confidence, not raise it (a monotonic test).
5. **Latency tests**: the rule pass on a 2,000-page made-up file in under 5 s; the first thumbnails in under 1 s (section 5.9).

## 5. The user interface

Component names follow [console/components.md](console/components.md) conventions (tokens, not hues; every state a word; writes through `Confirm`). New components are named below with what they are built from. The screen is a full-width console route, `#/library/split/<session>`, opened full screen (the console shell collapses its side navigation to give the pages room). The screen spec for the console's design pass is a handoff page, `docs/console/handoff-pdf-splitter.md`, to be written from this design when phase 2 starts (it is not written here).

### 5.1 The frame

```
+--------------------------------------------------------------------------------+
| Split document      Example scan.pdf (use a masked label if confidential)  [?]   |
| 412 pages  |  Draft saved 10:42  |  7 segments  |  suggestions: 9 open           |
+--------------------------------------------------------------------------------+
| View: [Album][Filmstrip][Scroll][List]   Size: [-]---o---[+]   Suggest v  More v |
+------------------------------------------------------------+-------------------+
|                                                            |  Segments (7)      |
|                    (the pages)                             |  1  p1-14   Letter |
|                                                            |  2  p15-22  ...    |
|                                                            |  ...               |
|                                                            |  [Review and split]|
+------------------------------------------------------------+-------------------+
| Page 37 of 412    [slider ----------o------------------]   Go to [ 37 ]          |
+--------------------------------------------------------------------------------+
```

At 1200 px and wider the **segment rail** sits at the right. Under 1200 px it becomes a bottom sheet opened from a bar showing the count ("7 segments"). Under 720 px the view picker is a single **View** menu and the bulk actions live under **More**. The frame has one `h1` (the screen title), the file's label (masked if confidential), the counts, and the draft's save state in words.

### 5.2 Marking a first page

A **boundary marker** is drawn on a page's cell as a solid bar on its leading edge and the label "Starts segment 3"; a suggestion as a dashed bar with "Suggested start" and the band. Both exist in every view. Marking is the same everywhere:

| Input | Act |
|---|---|
| **Tap or click** a page | toggles it as the first page of a segment (add or remove its boundary) |
| **Long-press** (touch, 500 ms) or **right-click** | opens the page's menu: *Starts a segment*, *Starts a segment inside this one* (a nested start), *Remove start*, *Merge with previous*, *Show larger*, *Why was this suggested?* |
| **Drag a boundary marker** to another page | moves the boundary (a **move** command; an undoable single step) |
| **Shift-click** a page | selects the pages between the last-clicked page and this one as a range (it does not mark), and the page menu offers *Every Nth page in the selection starts a segment*, *Merge the selection into one segment*, *Mark each page in the selection as a start* |
| **Click-drag in the grid margin** (pointer) or **two-finger drag** (touch) | a marquee selection |

Selection and marking are separate (a tap marks; a shift-click selects) so a mark is never made by accident while selecting. The first page of the file always shows as a start, with a lock glyph and the tooltip "The first page always starts a segment".

### 5.3 The views

All four views share one windowed data source (section 3.4); a person's scroll position is kept when switching views (the page in view stays in view). The default is **Album** on a tablet or desktop and **List** on a phone.

**Album (tiled grid).** Pages as `small` thumbnails in a responsive grid (4 to 12 columns by width, a size slider 2x to 12x). Segments are shown as **bands**: a segment's pages sit on a tinted strip with the segment number at the start and a gap before the next; the tint is a pattern or a number as well, never color alone. This is the main view for marking: you see the stack as it was stacked.

```
 [1]------ Segment 1 (p1-14) ------------------  [15]--- Segment 2 -----
 | p1 |p2 |p3 |p4 |p5 |p6 |p7 |   | p8 |p9 | ...        |p15|p16|...
 (start)                                                 (start)
```

**Filmstrip with slider.** One large page (the current) above, and a horizontal row of `tiny` thumbnails below with the boundary markers drawn as ticks on a **scrubbing slider** whose track shows the whole file (one tick per boundary, a lighter tick per suggestion, a grey run for blanks). Dragging the slider scrubs through `tiny` pictures from the sprite strips (fast, no per-page request); releasing loads the large page. The filmstrip is the best view for a person who wants to read each first page in turn: arrow keys step; `Enter` toggles the boundary on the current page.

**Scroll (vertical or horizontal).** Pages as a continuous `large`-ish reading column (vertical) or a row (horizontal; the default when the device is in landscape on a tablet), one page wide, with the boundary toggle at the page's head. For reading page content while marking. Same window and budget; the `large` size is requested only for the page centred.

**Compare / zoom pane.** Opens beside or below any view (a split on a wide screen, a sheet on a phone): the page in focus at `large` with a **magnifier** (hover or two-finger zoom to 1600 px), and the **previous page beside it** ("Compare with the page before") so the person judges "is this the first page?" by seeing what came before. A third slot compares with the **first page of the previous segment** (do these two look like one document?). Zoom steps: fit width, 100%, 200%, with keyboard `+` and `-`.

**Segment list.** A table-twin of the whole draft, and the phone default. Each row: the segment number, page range, page count, the first page as a `small` chip, kind and title (a guess marked "guess"), the source of its start (you, accepted suggestion, or the first page), and actions (rename, merge with previous, remove start, nested level). Rows are windowed too. A suggestion appears as a row with a dashed edge and *Accept*, *Edit*, *Reject*. Selecting a row scrolls the album to it, and the reverse.

### 5.4 The segment rail

The rail is the always-on list of segments (a compact form of the segment list). Each entry: number, first page chip, "pages 15-22 (8)", a title guess, a small marker for a collision at apply (5.7). A drag handle reorders nothing (the order is the file's order; section 6.3). The rail's header shows the totals and has **Review and split** as the one primary action; it is disabled with its reason in words until there are at least two segments or the person chooses "Split into one" (see 5.7).

### 5.5 Bulk actions

| Action | What it does | Safeguard |
|---|---|---|
| **Mark every Nth page** (N from the page menu or the selection) | starts a segment every N pages across the selection or the file ("these are all two-page letters") | shows the resulting count; one undo step; pages already marked are kept, not re-marked |
| **Split on blank pages** | every content page after a blank (or run of blanks) becomes a start; the blank pages themselves are options: *drop them*, *keep with the segment before*, *keep with the segment after* | respects the duplex rule: with over a quarter of the pages blank, it asks "These blanks look like the backs of pages" and defaults to no |
| **Split at page-number restarts** | uses the label run ("1 of 7") to place starts | same as the engine's signal; no model |
| **Accept all suggestions above...** | threshold slider; High by default; the count in the button | never model-only; one undo step |
| **Reject all below...** | hides low suggestions | reversible by "Show rejected" |
| **Merge with previous** | removes this boundary (the page joins the segment before) | the page menu and `M`; one undo step |
| **Clear all my marks** | removes the person's boundaries (not the suggestions) | `Confirm`, spelled out with the count; undoable |
| **Select blank pages** | selects every blank for a bulk decision (leave, drop from the output) | the dropped pages are listed in the review step |

Each bulk act states in a line what it will do and by how many pages **before** it runs, and runs as one command.

### 5.6 Keyboard and touch

| Key | Act |
|---|---|
| Arrow keys | move focus a page (grid: also up and down by row; filmstrip: left and right) |
| `Space` or `Enter` | toggle the focused page as a segment start |
| `N` / `P` | next / previous boundary or suggestion |
| `A` / `X` | accept / reject the focused suggestion |
| `M` | merge the focused segment with the previous |
| `L` | open the page menu (the same as a long-press) |
| `Shift`+arrows | extend a selection by page; `Shift`+click selects a range |
| `Home` / `End` / `PageUp` / `PageDown` | first / last page; one screen |
| `G` | Go to page (focus the page field) |
| `V` | cycle views; `1`-`4` choose one |
| `+` / `-` | zoom in the compare pane or change the album's size |
| `Z` / `Shift`+`Z` | undo / redo (also `Ctrl`+`Z` and `Ctrl`+`Shift`+`Z`) |
| `?` | the key map |
| `Esc` | close a menu or the compare pane, clear the selection |

Touch: **tap** marks; **long-press** the menu; **drag a boundary marker** moves it (the marker has a 44 px target, with a visible handle when the page is focused); **two-finger pinch** changes the album's size or zooms the compare pane; **swipe** moves a page in the filmstrip. Touch targets are at least 44 px; the rail's bottom sheet has a drag handle and a close button as well as the swipe.

### 5.7 The review step before apply

**Review and split** opens a full-width review, not a dialog. It is the checkpoint: nothing is written until its last tap.

```
Review: 7 documents from 412 pages
  [1] pages 1-14   14 pages  "Letter"       guess: correspondence    first page [thumb]
  [2] pages 15-22   8 pages  ...
  ...
  Pages not in any file: 3 blank pages (7, 29, 155)   [ ] keep them
  Rotation fixes: 2 pages  (applied to the new files only)
  Held slots: segment 3 would fill "Annual budget report" which already holds a file  (collision)
  Duplicate files: segment 5 is identical to library file "..."  (will be skipped)
  Result: 7 new files; the original is kept untouched.
  Filing: [ ] leave in the held uploads   [x] file by the library's classification   [ ] fill record slots (choose below)
  [ Confirm as Jane Example ]      (two clicks)
```

- **Counts.** Segments, pages in and out, pages dropped (blanks the person chose to leave out) listed by number. The totals must add: pages in the new files + dropped pages = pages in the source; if they do not, the button is disabled with the arithmetic shown.
- **Per-segment first-page preview.** The first page of each segment as a `large` picture on demand (small by default), with the kind and title guesses editable inline; this is the last look at every start, in order.
- **Collisions with held record slots.** For a segment aimed at a record slot or a key-documents row, the same collision rule the record-intake split uses: a slot that already holds a file, or that an earlier segment in this split fills, is reported with what was kept, and the segment goes to the held-uploads shelf instead; never replaced silently. A series slot needs its period; a repeating row needs its recording number.
- **Duplicates.** A part identical (by hash) to a file already in the library or in this split is flagged, and defaults to "skip, point to the existing file" (section 6.6).
- **Nested choices** (section 2, "The nested stack") for each nested segment.
- **Confirm.** A `Confirm` with the change spelled out ("Split Example scan.pdf into 7 files as Jane Example; the original is kept"). On confirm the session becomes `confirmed`, then `applied` (section 6).

A single-segment result ("Split into one") is allowed when the person only wants to **drop blanks or fix rotation** and file the result; it is labeled for what it does.

### 5.8 Accessibility

- **Names and roles.** Each page cell is a button ("Page 37, content. Starts segment 3. Press Enter to remove the start."), in a grid role with row and column counts; the rail is a list; the slider is a `slider` with `aria-valuetext` ("Page 37 of 412, segment 3"). The whole screen is operable without a pointer (5.6).
- **No colour alone.** A start is a bar, a number, and the words "Starts segment N"; a suggestion is dashed and says "Suggested", with its band as a word; blank, marked, and no-text-layer are glyphs with words; the segment bands carry numbers.
- **Alt text.** A page picture has `alt` built from the facts ("Page 37; contains text; first line: ..."), never read from the image; for a confidential file the alt is the page number only.
- **Focus.** After an act the focus stays on the page it acted on; after undo, on the page it undid; opening the review moves focus to its heading; the status line is `aria-live=polite` for "Draft saved", "N suggestions found", and bulk results.
- **Motion and contrast.** No motion beyond the scroll; respects `prefers-reduced-motion` (no thumbnail fade-in); the markers meet 3:1 against the page in both themes; text 4.5:1.
- **Zoom and reflow.** At 200% zoom and 320 px the list view and the rail still work without horizontal scrolling of the page (the album scrolls as its own region).

### 5.9 Performance budget

| Measure | Budget |
|---|---|
| First visible thumbnails (the first screen, tiny and small) after the session opens, on a warm server | under **1.0 s**; with a cold 400 MB file, under 2.5 s |
| Page count and empty aspect-ratio grid | under 150 ms |
| Scroll, 2,000 pages, album, mid-range phone | **60 fps** with no long task over 50 ms; no layout shift once the page count is known |
| A fast scroll (flick or slider drag) | no more than the tiny requests for the final viewport in flight; the rest aborted within 100 ms |
| Tap to marker drawn | under 100 ms (optimistic, before the save) |
| Memory ceiling (browser tab, pictures) | **under 40 MB** decoded pictures on desktop, **under 20 MB** on a phone, regardless of page count; no whole-PDF bytes in the tab |
| Autosave | one request per 1.5 s of quiet; a payload of the boundary set only (under 20 KB for 500 boundaries) |
| Rule-pass suggestions, 2,000 pages | under 5 s after the facts are ready |
| Server memory per render | one page at a time per worker, under 150 MB |

Budgets are asserted in a browser test (section 9) with a made-up 2,000-page PDF; a regression fails the test.

### 5.10 Empty, loading, error, and offline states

| State | What the person sees |
|---|---|
| **Empty (no file yet)** | the file-source tabs (Drive, paste a link, from this computer) and a plain sentence: "Choose a PDF to split. jason shows its pages and you mark where each document starts." |
| **Opening** | the aspect-ratio grid with LQIP as soon as the page count is known; "Pages ready: 40 of 412" as a line, not a spinner over everything |
| **No text layer** | a quiet note: "This scan has no text layer. Suggestions use the page images and numbers only." and the model pass offered |
| **Too many pages** | the `split.max_pages` words; nothing opened |
| **Over the upload or fetch limit** | the registry's words at the file source, nothing stored |
| **Cannot read the PDF** (encrypted, damaged) | "This file could not be read: encrypted" with what the person can do (remove the password in the original program, or upload a copy); no draft is created |
| **A page that failed to render** | a card with the page number and "This page could not be drawn" and a *Retry*; the page can still be marked; a failure never stops the others |
| **Model unavailable** | the preflight's words (the machine is short, or the model is not running); the rule suggestions stay |
| **Offline or connection lost** | a banner: "You are offline. Your marks are kept on this device and will be saved when you are back." Already-loaded thumbnails keep showing; marking continues; the apply is disabled (it needs the server) |
| **Save conflict** | a two-column comparison of the two drafts with *Keep mine*, *Keep theirs*, *Merge boundaries* (the union); never silent |
| **Another person is editing** | a line naming them and the time of their last change; the second session is read-only until the first leaves, or both may edit with the conflict rule above (open item 7) |
| **Stale** (the file's bytes changed) | "This file changed after you started. Your marks are for the old version, kept here." The new version opens as a fresh draft |

## 6. Apply: writing the new files

### 6.1 What is written

For each confirmed segment, **a new PDF of just its pages**, built with `pypdf` from page ranges exactly as the record-intake `split` act does (`jason.tasks.record_upload.split`). The splitter does not add a second writer: it calls that function (extended where the splitter needs it, below) so collisions, locks, the store lock, the history line, and the read-back queue are the same code.

- **Page copy only.** Pages are copied with their content, images, text layer, annotations, and resources; the document's bookmarks and links that point into the segment are kept when `pypdf` can retain them and dropped when they point outside (a note in the result, "links outside this file were removed"). Form fields on the copied pages are kept as written.
- **Rotation.** A rotation the person chose in the review step is written as the page's `/Rotate` in the **new** file only. No pixel is changed, no page is flattened, no scan is re-encoded.
- **Dropped pages.** Blanks the person chose to leave out are left out of every new file and listed in the result by number.
- **Atomic.** Each file is written to a temporary name on the configured temp drive, checked (it opens; its page count is the range), and moved into place; a failure part-way leaves the files already written and **reports** which segment failed; the session stays `confirmed` and the apply can be retried for the missing ones. Nothing is deleted on failure.
- **The original.** Never modified, moved, renamed, or deleted, in Drive or in the library or the store. A Drive source is read; nothing is written to Drive unless a later, separate, explicit act copies a part there.

### 6.2 Provenance

Each new file's pin and reading record carry, as `splitFrom` does today and a little more:

```
splitFrom   {pin: <the source's pin id>, sha256: <source hash>, session: <session id>}
pages       {from: 15, to: 22, of: 412}            # the range in the source
segment     {key: "s2" | "s2/s2.1", level: 0|1, title, kind (guess|confirmed)}
confirmedBy {name, at}
```

The source's reading and pin note "split into N files" with the session id, so the original shows what came of it. The address of a part is the existing `library:ID#p15-22`, and the nested form `#seg=s2/s2.1` (record-addresses.md) keeps meaning for a child that stays inside its parent.

### 6.3 Order, naming, and filing

- **Order.** The new files are created in page order and listed in that order; the order in the original is information (a stack consumed in order), so the part number ("part 3 of 7 of the source") is stored on each file as `ordinal`.
- **Naming.** The splitter **never invents a human file name from content.** A new file has a neutral working name, "Part 3 of 7 (pages 15-22)", plus the title guess when the person accepted one. Final names, folders, and shelves come from the **library classification**: first the record's **kind** (the profile's name rules, the phrase rules, then a local model only if asked; a miss stays a miss), then the **source** (who it came from, when the sender directory knows), per the profile's filing rules ([key-documents.md](key-documents.md), the library classifier). A part whose kind is a miss is filed under *Unclassified*, with its first page shown, for a person.
- **Slots.** A segment the person assigned to a record-intake slot or a key-documents row is pinned there through the existing `split` act (`--part SEGMENT=SLOT[@PERIOD][#ENTRY]`); one the person did not assign is only filed as above. The splitter never decides that a slot is filled: the person's mapping is the confirmation ([record-intake.md](record-intake.md), "A split nobody confirmed fills nothing").
- **Held uploads.** A part that goes nowhere yet is a **held upload** in the store, listed on the Records screen, so nothing is lost and nothing is filed by guess.

### 6.4 Where the splitter lives in record intake

For a combined scan already in a slot, **"Split this scan"** opens the splitter with the proposal pre-loaded as suggestions (the tier words intact) and the proposal's slot mappings pre-filled as hints. Confirming runs the existing `split` act with the person's final parts. The confirmations queue's "combined scan" item stays until every part is confirmed or the proposal is declined; the splitter offers *Decline the proposal* as well as *Apply*. The key-documents row asks per part for the recording number where the row repeats.

### 6.5 OCR and the reading of each part

- **No re-OCR of the split.** Pages are copied with their existing text layer. A part whose pages had no text layer is **queued for the read** like any new file (the preflight, then OCR if the person's policy says so); the splitter does not run OCR inline.
- **The read-back.** Under `split.auto_read` (on by default), each new part is queued as a read-back job on the document lane in the confirming person's name; off, the result says to read each part by hand. A part that cannot be queued is listed as `notQueued`, and the split stands.
- **The segmentation reading is inherited.** The source's stored segmentation and preflight readings are keyed by the *source* SHA-256; each part gets its own reading from its own bytes. The page facts the splitter already holds (blank, label, title, date) are written into each part's reading as a **seed** so the preflight need not remeasure; if the seed disagrees with the later reading the later one wins and the difference is noted.
- **Rotation.** A rotation chosen in the review is set on the part's pages; the preflight's measured rotation is a suggestion in the review step ("Pages 7 and 90 are sideways; rotate them in the new files?"), never applied silently.

### 6.6 Dedupe by hash

- **Within the split.** Two parts whose bytes are identical (the same page range copied) cannot arise from one source, but two ranges with identical *page content* (a form printed twice) are different files and kept; the splitter does not fold by text.
- **Against the library.** Each new file's SHA-256 is checked against the library and the store. An identical file is **not written again**: the result says "already filed as ..." and points to it, and the segment's provenance is recorded on the existing file as a second `splitFrom`. The person can choose "keep a copy anyway" in the review step.
- **The source.** Splitting twice from the same source with the same boundaries produces identical bytes where `pypdf` is deterministic for the same inputs (its object ordering is; a test asserts it) and is detected as already done; the session says so rather than writing again.

## 7. API, CLI, and MCP

### 7.1 Routes

Loaders read; writes go through the console's one writer pattern (`POST /api/write/split/...`), with roles and a dry run first, as the limits and records writers do.

| Route | Kind | What |
|---|---|---|
| `GET /api/split` | read | the sessions (id, status, pages, updated, segments, suggestions open); a confidential file's label masked |
| `GET /api/split/<id>` | read | one session: source summary, boundaries, suggestions, segments, counts, version |
| `GET /api/split/<id>/facts?from=&to=` | read | page facts for a range |
| `GET /api/split/<id>/thumb/<n>/<size>.webp`, `.../sprite/...`, `.../page/<n>.pdf` | read | section 3.6 |
| `POST /api/write/split/open` | write | start or resume: `{ref: {kind: "library"\|"drive"\|"upload", id}}`; returns the session, or the limit's words |
| `PUT /api/write/split/<id>/draft` | write | the boundary set and labels with `version`; returns the new `version` or `409 conflict` with the server's copy |
| `POST /api/write/split/<id>/suggest` | write | `{model: bool}`; starts the suggestion job; returns a job id and progress by `GET /api/jobs/...` |
| `POST /api/write/split/<id>/review` | write | a dry run: the review summary (counts, collisions, duplicates, nested choices), nothing written |
| `POST /api/write/split/<id>/apply` | write | `{confirm: true, parts: [...]}` runs apply; an administrator or the confirming officer by the record-intake rules; the result lists each file written, skipped, failed |
| `POST /api/write/split/<id>/decline` | write | status `declined` |
| `DELETE /api/write/split/<id>` | write | removes a draft and its cache entries (a person with the office, a reason) |

An apply is refused with the registry's words when a limit is reached, with the reason in words when a part is stale, when the source changed, or when the machine is short of disk.

### 7.2 CLI

```
jason split FILE|ID                    open or resume a session; print its summary (dry run by default: reads only)
jason split FILE|ID --suggest [--model]    run the rule pass (and, with --model, the local-model pass); print suggestions with reasons
jason split ID --boundaries 1,15,23,40     set boundaries (a draft write; needs --by)
jason split ID --accept all|HIGH|ID,ID     accept suggestions (a draft write)
jason split ID --review                    the review summary: counts, collisions, duplicates (no write)
jason split ID --apply --yes --by NAME     write the files (the only command that writes PDFs)
jason split ID --part SEGMENT=SLOT[@PERIOD][#ENTRY] ...   assign segments to slots, as `jason records --split`
jason split ID --decline --by NAME
jason split --list                         sessions, with status
jason split --purge [ID|--all-drafts] --yes   drop drafts and their thumbnail cache (never an original)
jason split ... --json
```

Conventions follow the rest of the CLI: **dry run is the default**; `--yes` is required to write; `--by NAME` names the person for the log (a command-line draft write without `--by` is refused); the command never opens a browser; `--model` runs `local_ai.preflight` first and fails fast. The history line (`data/records/history.jsonl`) holds the session id, counts, the slots, and the pin ids, never a file name or a page's text.

### 7.3 MCP

`jason-mcp` serves the stores on disk and **writes nothing from a tool**; the splitter adds one **read-only** tool, `split_suggestions` (board and onboarding profiles): given a session id or a library id, it returns the session's status, page count, the person's boundaries, and the stored suggestions with confidence, tier, and reason. It never runs the engine, the model, or the renderer; it reads what the session saved, carries the caveat that a suggestion is evidence and not a pin, and masks a confidential file unless asked. There is no MCP tool that opens, edits, or applies a session: marking and applying are a person's, in the console or at the command line.

## 8. Safety and privacy

- **A person disposes.** A suggestion never becomes a boundary, and a boundary never becomes a file, without a person's act. There is no setting, schedule, or job that applies a split. The scheduler's `scheduled.writes_allowed` has no splitter path.
- **The original is untouched,** in the library, the store, and Drive. A Drive file is read through a copy; no write-scope call is made by the splitter.
- **Confidential files.** The session copies the library's `confidential` flag and re-reads it per request. A confidential file's **name is masked** in the list, the header, the alt text, and the history; its thumbnails and pages are served only when the signed-in person may see confidential files (the same switch `/api/library?confidential=1` honours) and the private view is open; otherwise the session opens with page numbers and the facts only and the pictures are replaced by the placeholder cards. A confidential file's pictures are `Cache-Control: private, no-store` (not `immutable`), so the browser does not keep them past the tab.
- **No names in URLs or logs.** Routes use the session id and the page number; a file's name, a Drive id's title, and a page's text never appear in a URL, a query string, an access log line, a history line, or an error message. Errors name the session and the page.
- **Thumbnails are derived copies under the same access rules.** A picture of a page is the page. It is served only through the session, which checks the signed-in person and the file's access every time; the cache path is by hash and is not served as a static folder; a removed file's pictures are removed with it. The cache lives under the data folder (never in the project, never checked in; `data/` is git-ignored).
- **Local only.** The model pass runs on the local model; no page leaves the machine; thumbnails are never sent to a hosted model. There is no hosted-model path in this design.
- **Cache purge.** `jason split --purge`, a retention sweep (`split.draft_days`), and deletion of the library file purge the cache for that hash; a **purge on demand** button sits on the session's More menu ("Remove page pictures made for this file"). Purging loses nothing but speed.
- **No cross-association learning.** The within-session examples (4.6) are deleted with the session; nothing is shared across communities or files; the cue table changes only by reviewed code.
- **Limits are not bypassed.** `upload.max_bytes`, `fetch.max_bytes`, `split.max_pages`, and the cache bound apply; the splitter's overrides, if any are added later, follow the registry's per-act override and trail.
- **Audit.** Open, apply, decline, and purge each leave a history line (who, when, counts, session id); a draft's edits are not audited line by line (they are a draft), but the **confirm** records the final boundary list.

## 9. Phases, tests, and open decisions

### 9.1 Build plan

| Phase | What | Size and result |
|---|---|---|
| **1. Backend core** | `split_session` records; the session store; the light fact pass over `pdf_preflight`; `render_page` and the hash cache with the three limits; thumb, sprite, and page routes with ETags; `jason split` (open, list, boundaries, review, apply through the existing `split` act, purge) | A person can open a file, set boundaries from the command line, and apply. Measured: first thumbnails, cache bounds |
| **2. The marking console** | the `SplitView` screen: Album and List views, windowed grid, placeholders from facts, tap and shift-click, the segment rail, autosave, undo/redo, the review step; the handoff page `docs/console/handoff-pdf-splitter.md` | The core requirement, without suggestions. A person splits a 600-page file by tapping |
| **3. More views and touch** | Filmstrip with the slider and sprite scrub, Scroll (vertical and horizontal), the compare and zoom pane, long-press and drag-a-boundary, keyboard map, the phone layout and bottom sheet | The multiple views and the phone and tablet widths |
| **4. Suggestions** | the three new cue rows; the rule pass wired to the session; ghost boundaries, accept/edit/reject, bulk acts; the optional model pass; the within-session examples; `split_suggestions` MCP tool; `scripts/split_fuzz.py` and the made-up gold set | Suggestions with reasons, measured |
| **5. Joins** | the entries from the library menu, record-intake slots, and key-documents rows; the held-uploads shelf; the confirmations-queue link; dedupe against the library; the retention sweep | Everything reaches the same screen |
| **6. Polish and the optional pane** | the optional vector compare pane (if open item 1 says yes); the accessibility audit; the performance regression test; the measured section filled in | Release |

Phases 1 and 2 deliver the user's stated job; 4 is optional and independent of 3.

### 9.2 Tests

All inputs are made up (`tests/fixtures`, builders in the style of `tests/test_pdf_preflight.py`, which builds its PDFs from nothing).

- **Records and commands:** boundary add/remove/move, level, undo/redo (including after a reload), a bulk act is one step, the first page cannot be removed, version conflict on a stale save.
- **Segments:** boundaries to ranges; a nested start; "take out" joins the parent's runs; the totals (pages in files + dropped = source pages).
- **Apply:** each file opens and has its range's page count; the original's bytes are unchanged (hash before and after); provenance fields; a collision is reported and not written; a duplicate is skipped; determinism of the output for the same boundaries; a failure part-way leaves a retryable state; read-back is queued under `split.auto_read` and is not when off; a stale source is refused.
- **Thumbnails:** a size per request; the cache key by hash; the bound evicts LRU and never the open session's pages; a short temp drive serves once without storing; ETag and `304`; a confidential file's pictures are `no-store` and withheld when not allowed; a cancelled request does not leave a partial file.
- **Limits:** each of the three keys refuses in words; a clamped stored value; `split.suggest_enabled` off leaves the editor working.
- **Suggestions:** each cue row on a made-up page; the explanation text; tier combination; no suggestion alters a person's boundary (property test); a degraded text layer lowers confidence (monotonic); the model pass runs only on request, holds the GPU lock, and respects `preflight` (with a stub model); learning within the session changes later scores and is gone with the session.
- **Boundary tests:** `python -m jason.community.boundary` and `pytest -k profile` clean; no general code or doc names an association's facts; the splitter's pure records import no profile.
- **Console (browser tests, `ui/`):** the 2,000-page made-up file keeps the live elements and decoded pictures within the budget; a fast scroll aborts requests; each view marks a boundary; keyboard-only completion of a split; a 375 px and a 768 px layout; axe checks; reduced motion.
- **Fuzz and evaluation:** `scripts/split_fuzz.py` as in 4.7, run by hand and in a nightly job; its report is the source of the measured section.

### 9.3 Open decisions, with recommendations

| # | Decision | Options | Recommendation |
|---|---|---|---|
| 1 | A PDF engine in the browser for the compare pane? | none (server images only); pdf.js for the one centred page | **None in phase 1**; add pdf.js as a lazy-loaded, one-page viewer only if testers need vector sharpness at high zoom. Revisit at phase 6 |
| 2 | Server renderer and its license | PyMuPDF (installed, AGPL-3.0); `pypdfium2` (permissive) | Put the renderer behind `render_page`; **prefer `pypdfium2` if the program may ever be offered as a service or redistributed**, otherwise PyMuPDF is fine for a self-hosted install. The user decides |
| 3 | Is a suggestion run automatic on opening? | never; the rule pass only; both | **The rule pass automatically** (cheap, deterministic, off by `split.suggest_enabled`); **the model pass never automatically** |
| 4 | Default `split.max_pages` | 1,000 / 3,000 / 10,000 | **3,000**; the virtualization handles more, but one draft of that size is already a lot of review for a person |
| 5 | Default `split.thumbnail_cache_bytes` | 256 MB / 512 MB / 2 GB | **512 MB** (about 25 files of 2,000 pages); the administrator can raise to 8 GB |
| 6 | Add `split.draft_days` and use `split.max_parts` | add / not | **Add both** as ordinary registry rows; a draft that never ends is clutter |
| 7 | Two people editing one draft | locked (read-only second) / last-writer with conflict / live merge | **Conflict on save with a visible merge** (version counter); no live collaboration in the first release |
| 8 | Nested "take out" at apply | support / keep-inside only in v1 | **Keep-inside and also-make-a-file** in v1; **take out** in a later phase after the flat path is solid, since it changes the parent |
| 9 | What the splitter does with blank pages by default | keep with the segment / drop / ask | **Ask in the review step**, defaulting to keep them with the segment before (nothing is lost), and drop only when the person says |
| 10 | Whether the splitter may write new files into Drive | no / on a separate explicit act | **No**: files go to the store and the library; a copy to Drive is the existing, separate, confirmed act |
| 11 | Thumbnail format | WebP / JPEG | **WebP with a JPEG fallback** for an old browser; the cache stores both only on a miss for a client that needs it |
| 12 | Whether the splitter replaces the record-intake proposal list | replace / join | **Join**: the proposal remains the queue item; "Split this scan" opens the splitter on it |

## 10. How this joins the documents

- [record-intake.md](record-intake.md): the splitter is the front end of step 6 (Segment) and the confirm of the `split` act; the proposal becomes suggestions; collisions are the same.
- [document-segmentation.md](document-segmentation.md): the cue table and the walk are the rule pass; three cues are added there when phase 4 lands (`dpi-change`, `colour-change`, `language-change`), with the document updated in the same change.
- [pdf-preflight.md](pdf-preflight.md): the per-page facts and, optionally, the word layer; a full preflight is not required to open a session.
- [instance-limits.md](instance-limits.md): the three new limit rows and, with them, a line in the registry table of keys.
- [key-documents.md](key-documents.md): a repeating row takes the recording number per part; the splitter pins through the same writer.
- [console/components.md](console/components.md) and [console/handoff-record-intake.md](console/handoff-record-intake.md): the file-source tabs and the confirmation components are reused; the splitter's own components (`SplitView`, `PageGrid`, `PageCell`, `BoundaryMarker`, `SegmentRail`, `ComparePane`, `SplitReview`, `SuggestionRow`) are specified in the handoff page when phase 2 starts.
- [console/security-and-privacy.md](console/security-and-privacy.md): confidential masking and the no-names-in-URLs rule.
