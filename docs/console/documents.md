# Documents: one viewer for every kind

The console shows a document wherever a person needs to read the thing itself:
- a member's form answers;
- an attachment;
- a statute or a governing document;
- a Google Doc, Sheet, or Form;
- an email;
- a scanned letter.

This page specifies the one component that does it (`DocumentViewer`, opened from `EvidencePanel` and anywhere else a document is named), the server's document service behind it, and each kind of document: where its truth lives, the copy jason keeps, how it renders, how it is refreshed, and who may see it.

What is built and what is proposed are marked in each section. The evidence routes are in [approval-workflow.md](approval-workflow.md#evidence-you-can-open), the data levels in [security-and-privacy.md](security-and-privacy.md), and the accessibility duties in [components.md](components.md#accessibility).

## Rules

1. **A copy jason keeps, not a live frame.**
   - Opening a document shows jason's copy on disk, read when a person or a sync last read it.
   - The console never frames a private Google or PayHOA page:
     - PayHOA refuses to be framed (`X-Frame-Options: DENY` on every response).
     - A private Google file in a frame needs the viewer's Google cookies in a third-party frame. Safari blocks those cookies by default and Firefox partitions them. Google's sign-in page then refuses the frame, and the person sees a blank.
   - A copy also lets the server mask what must be masked before anything reaches the browser.
2. **Nothing outside is read on load.** Reading the source again is a person's act:
   - the ↻ on one document, or "Read every request again" on a plan;
   - under that person's name;
   - logged in `evidence/refreshes.jsonl`;
   - never a write to the source.

   A missing Keeper or Google sign-in fails fast and names the command that fixes it.
3. **Masked by default; unmasked by a named person, logged.** Lists and panels show contact details masked. Opening the document itself (`POST /api/evidence/view`) shows it as the source has it, because reading the document is the point. That view is named, logged in `evidence/views.jsonl` (who, when, which document, never its contents), and never automatic.
4. **Held back by level.** A confidential library file, an executive-session record, or restricted books never appear in a document list unless the person has opened the private view: the **Private view** switch in the console's header (`PrivateSwitch`), for a stated reason and 15, 30, or 60 minutes, logged in `access/private.jsonl` ([security-and-privacy.md](security-and-privacy.md#built-the-private-view), P3). While it is open, a hatched band under the header says so and closes it; a confidential document in an evidence list carries a **Confidential** chip, and its viewer says "Confidential: shown in the private view; this view is logged." A list that held something back says so, and how many: "2 held back (confidential)".
5. **The original stays one click away.**
   - Each document carries a link to its source, opened in a new tab with the person's own session: PayHOA's request page, the Doc in Google, the message in Gmail.
   - Editing happens there. The console's copy is for reading and citing.
6. **Recite; don't characterize.** A statute or governing document opens as its stored words, with its citation and the caveat that jason's copy is not an official restatement. A summary never stands in for the document.
7. **Untrusted bytes can't act.** An uploaded file, an exported HTML page, or an email body is served so that nothing in it can run with the console's privileges (see [Serving safely](#serving-safely)).

## The model

| Record | What it is | Where |
|---|---|---|
| Address | What a piece of evidence names: `payhoa:submission:N`, `CIV 4041`, `jason://decl/6.2(a)`, `board-item:ID`, `drive:ID`, `file:PATH` (a file under data/), `library:ID` (a document in `library/library.db`: its file and its extracted text, at the library's confidential flag), `gmail:MESSAGE` (proposed), `mail:ID` (proposed) | an `Evidence` row on a plan item, a canvas clip, a board item, a letter, a `DocRef` ([doc-component.md](doc-component.md)) |
| Document | One readable thing an address has: `{id, name, kind, size, readAt, note}` | `resolve(address).documents` |
| Copy | The bytes or record jason keeps, with `readAt`, `via` (what read it), and a digest | `payhoa-files/requests/N/submission.json`, `library/files/...`, `drive/copies/ID.*`, `gmail/messages/ID.json` (proposed) |
| Refresher | How one address is read again from its source, if it can be | a resolver row's `refresher` (`jason.approvals.evidence`) |
| View | One person opening one document, logged | `POST /api/evidence/view` |
| Grant | A ten-minute link to the bytes of one viewed file | `GET /api/evidence/document/<token>` |

Each kind of address is a resolver row (`EvidenceKind`), matched in order. A new kind of document is a new row with its reader, its documents, and its refresher, not a new viewer.

The renderer is chosen by the document's `kind`, never by the address:

| `kind` | Renderer | Notes |
|---|---|---|
| `submission` | the form as filled in | structured rows from the server ([PayHOA submission](#payhoa-request-submission)) |
| `form` | the blank form (proposed) | the same rows, without answers |
| `pdf` | the browser's PDF viewer in a sandboxed frame | "Open in a new tab" always beside it |
| `image` | `<img>` with Fit / Actual size | |
| `text` | serif text, or `Markdown` when it is markdown | statutes, extracts, transcripts |
| `audio` | the browser's `<audio controls>` on the view's link, with its name, its length once the player knows it, and a "Transcript" chip when a `transcript.*` sits beside it | `.m4a`, `.mp3`, `.wav`, `.ogg`: a meeting's recording. Served inline as its type with range requests, so the player seeks; the transcript opens as its own view |
| `html` | a sandboxed `srcdoc` frame (proposed) | email bodies and HTML exports, sanitized on the server |
| `table` | a read-only grid (proposed) | a Sheet's export or a register snapshot |
| `message` | headers, then the body as `text` or `html` (proposed) | Gmail |
| `file` | no preview; Download | anything outside the whitelist, and HTML, SVG, or XML uploads |

## The component

### In a panel: the Documents list (built)

- **Where:** under an evidence panel's sources, a "Documents" heading and one line: "Viewing shows the document unmasked, under your name, and is logged."
- **Each row:** the name in the serif, the kind and size ("PDF · 2.1 MB", "Form submission"), any note, and **View**. The button's accessible name is "View <name>".
- **No named person:** View is `aria-disabled` and shows "Sign in or pick your name to view it."
- **An empty list** renders nothing. A held-back count renders as one muted line (proposed).

### The viewer (built; proposed parts marked)

A modal `<dialog>` (`showModal()`), about 92vw by 90vh. Width is capped for reading: 52rem for a submission or text, 84rem for a pdf or image.

**Header, top to bottom:**
1. The document's name, an `h2` that takes focus on open.
2. Its kind, and "Read <time> (<n> days ago)" with what read it ("by jason sync-request-files").
3. The "Unmasked: shown because NAME asked; this view is logged." line in the warn tone, then the source's caveats word for word.
4. Actions:
   - **Open the original** (a new tab; built for files as "Open in a new tab");
   - **↻ Read again from <system>**, when the address has a refresher (proposed here; built in the panel);
   - **Print**;
   - **Previous / n of N / Next**;
   - **Close**.

**Behavior:**
- **Each document is its own view.** Previous and Next each make a new logged view; nothing is prefetched.
- **Closing** with Escape or Close returns focus to the button that opened the viewer. The background is inert.
- **While opening:** "Opening…" with `aria-busy`.
- **On an error:** the server's words in the error tone, inside the dialog, which stays open.
- **Printing:** prints the document alone, without the console around it.
- **Link expiry:** "The link works until <time>." under a file-backed document. After that, View again.

**Accessibility:**
- Every frame has a `title`.
- A PDF in the browser's viewer gets "Open in a new tab" for a reader who needs the browser's own tools.
- An image has its name as `alt`.
- A submission is a definition list, not a table of layout.
- Section headings are real headings inside the dialog.

## Each kind

### PayHOA request submission

**Status:** built; the rendering rules below are in progress.

**Where it comes from.**
- **Truth:** PayHOA.
- **Copy:** `payhoa-files/requests/N/submission.json` (`jason.tasks.submission_cache`), the raw `get_form_submission` answer with `readAt` and `via`. It is written whenever jason reads a submission in full: an owner-information plan's live read, `jason sync-request-files`, or the ↻.
- **Refresher:** one `get_form_submission` call.
- **Original:** for the board, PayHOA's request page `/app/requests/submission/N`; for the owner, the unit's Requests tab. Shown as a link card, never framed.

**The PayHOA form model.**
- PayHOA has seven question types: `input`, `textarea`, `file`, `checkbox`, `select`, `hr`, and `plaintext`.
- A submission's `form` carries no question list. Each answer carries its own `question` (`label`, `type`, `sortOrder`, `description` as help, `isRequired`, `options`).
- Answers are not in order; `sortOrder` is.

**How it renders**, top to bottom:
1. **Header:** the form's name, the unit, "Submitted YYYY-MM-DD", "Completed YYYY-MM-DD" when set, and the status as PayHOA names it.
2. **The form's introduction** (`form.description`), as muted text.
3. **The questions in `sortOrder`:**
   - `hr` is a **section heading**, using the form's own section titles.
   - `plaintext` is the form's own words: a muted paragraph.
   - **A choose-any question is one row.** PayHOA has no multi-select checkbox, so jason's form builder (`form_render.payhoa_questions`) writes one `checkbox` per option, labelled "N. Title: Option". The viewer joins them back:
     - **Grouping:** the form's record in `payhoa/forms.json` says which boxes belong together (fields `base.option`). The label pattern is the fallback for a form jason did not build.
     - **The answer:** the checked options in order, joined with "; " ("By mail; By email"). Unchecked options are not listed. No box checked: "None chosen".
   - **A "same as" pair is one row.** A "Same as my unit address" box plus its "or another address" input. Box checked: "Same as my unit address". Otherwise the typed text. Both given: both, with a "both given" flag.
   - **"Other":** "Other: <text>", or "Other (not specified)".
   - **A lone box** reads "Checked" / "Not checked". An attestation reads "Certified" / "Not certified".
   - **A select** shows the option's label.
   - **A file question** shows the uploads by name, each a button that opens that attachment in the viewer (a new logged view).
   - **Each question** shows its help text under it, a "required" marker in words, and "(no answer)" for a blank.
4. **What the console never shows in this view:**
   - internal notes (`notes.json`);
   - tags marked internal;
   - the assignee;
   - approvals.
   These are board and manager records, shown in the request's own screen, never in a document a member could be shown. Comments are owner-visible text; their authors' details are P2.

**Level:** P2 (contact details in the answers). Unmasked only in the logged view.

### PayHOA blank form

**Status:** proposed.

- **What it shows:** the questions as an owner sees them, before answering, so a person can read what was asked. It is rendered by the same component as a submission, with no answers.
- **Source:**
  - **for a form jason built:** its `FormTemplate`, through `questions_for` and the existing printable blank (`form_render.paper_html`). This is exact, and keeps the original grouping.
  - **for any other form:** the questions carried by any kept submission to it.
- **Original:** the owner's link `/app/forms/FORM;unitId=UNIT` and the board's `/app/form-detail/FORM`, as link cards.
- **Address:** `payhoa:form:FORM`.
- **Level:** P0, since a blank form holds no member data.

### Request attachments

**Status:** built.

- **Copy:** `payhoa-files/requests/N/<fileId>_<name>`, saved by `jason sync-request-files`.
- **How each type renders:**
  - a PDF in the PDF renderer;
  - an image (png, jpg, gif, webp) in the image renderer;
  - txt, md, or csv as text;
  - anything else, including HEIC photos, as a download.

  HEIC should get a server-made JPEG preview (proposed).
- **Id:** the file name, or `file-<hash>` when the name holds an email or a phone number.
- **Level:** P2.

### Statutes and the association's documents

**Status:** built.

- **Truth:** the statute's text exported from lawlibrary (`jason export-authorities`), and the recorded or adopted instrument for the association's documents.
- **What a citation offers:**
  - its whole section as text;
  - where `jason cite` links one, the library file (`library:<id>`), its extracted text (`library-text:<id>`), and a Drive file's copy on disk (`drive:<id>`).
- **Level and caveats:** P0, unless a library row is confidential. It always carries the caveat that jason's text is not an official restatement, and the version in force.
- **Proposed:** link the static reader (`jason cite --html`, `data/reader/`) as the original for a `jason://` address, so a person can walk to the neighbouring sections.

**The governing documents' previews** (built). The Records screen's **Governing documents** tab (`#/records`) lists each of the association's governing documents (`GET /api/governing-documents`, `jason.web.extra.governing_documents`): the declaration and its amendments (`Community.ccrs`) and the documents others cite (`Community.citable_documents`), each once, with its kind and the date it was recorded, adopted, or written, and its copies as document references (`DocRef`, [doc-component.md](doc-component.md)):
- **Recorded copy:** the recorded or adopted PDF on disk (`artifacts/site-docs/governing_documents/`, `governing/`), matched to its document by the Drive id its text extract's header names (`<name>.pdf.md`), else by name, else by recording number. A PDF no document claims is a row of its own. It is the copy that governs a recorded instrument (AGENTS.md, "Recite the version that governs").
- **Drive copy:** the Doc in Drive the specification binds, a working copy, as jason's copy (`drive:<id>`).

`DocumentPreview` shows both side by side, the recorded copy first, each labelled; a Drive file alone is `DrivePreview` as on the Templates screen. "Read every governing document from Drive" reads the Drive files on one sign-in (`refresh-many`). A row's level is the higher of its copies'; a confidential row is listed only in the private view, and the list says how many it held back.
- **A file on disk as evidence:** `file:<path under data/>` is a resolver row (`EvidenceKind.FILE`): only a place `access.PATH_RULES` names (an unplaced folder fails closed), and only a kind the viewer shows (pdf, image, text). Its source is "Recorded copy" (the file's modified time); its documents `pdf` (or `image`, `text`) and, for a PDF, `text` from its extract beside it (`<name>.pdf.md`). The level is `level_of_path`; a P3 file is held back outside the private view. No refresher: a recorded instrument does not change.
- **Page 1 as a thumbnail:** `GET /api/thumb?path=<path under data/>` (`jason.web.previews`) renders a PDF's first page with PyMuPDF, about 300 pixels wide, and keeps it as `data/thumbs/<sha256 of the path>.png`, rendered again when the PDF's modified time changes (`jason.tasks.pdf_thumbs`). It reads disk only, so a screen may load it. It is judged as `/api/file` is: 401 signed out, 404 for no PDF there, 403 for a level the person's offices do not open, each serve logged in `access/served.jsonl`; `Cache-Control: private, max-age=300`, `nosniff`, `CSP: sandbox`. `thumbs/*` is P3 by path, so a thumbnail never leaves by `/api/file`.

### Google Docs, Sheets, and Slides

**Status:** built: the copy, its refresher, freshness, restrictions, the size limit, and the `drive:<id>` evidence row (`jason.tasks.drive_copies`, `jason.approvals.evidence`), with the Templates screen's Doc column as the first screen to show them (`DrivePreview`), then the governing documents and the meeting packets (`DocumentPreview`, above). A Sheet's CSV opens as text; the `table` renderer and a CSV per sheet are proposed.

**Truth:** Drive. jason keeps Drive's metadata (`drive/files.json`), a copy when the same bytes arrived another way (`drive/holdings.json` `elsewhere`), and its own copy once a person reads a file from Drive.

**Copy:** `drive/copies/<id>.<ext>`, with `drive/copies/<id>.json` recording `{readAt, via, by, modifiedTime, mimeType, name, md5?, sizes, webViewLink, textMime?, reused?}`:
- **a Doc:** exported as PDF (to read and print), and as Markdown (`text/markdown`; plain text when Google refuses it) to search and cite: `<id>.pdf`, `<id>.md`;
- **a Sheet:** exported as PDF and its first sheet as CSV (`text/csv`): `<id>.pdf`, `<id>.csv`. A CSV per sheet is proposed;
- **Slides:** exported as PDF;
- **the thumbnail:** the file's `thumbnailLink`, read with jason's token at once (it is short-lived; only Google's hosts are asked) and kept as `<id>.png`. None when Drive gives none.

Each file is written to a temporary name and replaced, the record last, under the store lock `drive-copies`; a fresh copy removes the files an earlier one left.

**Evidence:** `drive:<id>` is a resolver row. Its sources are "Copy from Drive" (`readAt`, by, `modifiedTime`) and "Drive catalog" (the listing's `modified`, as of its `syncedAt`); its documents `pdf`, `text` (the Markdown), and `csv`, each only when on disk; its `link` the file's `webViewLink`, else the catalog's `link`, else the editor's address for its type.

**Refresher:** `files.export` (or `files.get?alt=media` for a stored file), on a person's click, with the association's OAuth: ↻ in the evidence panel, "Read from Drive" in a `DrivePreview`, or "Read every template from Drive" (`POST /api/evidence/refresh-many`, one sign-in). It goes through `/api/evidence/refresh` and its rules: signed in, P2, the person's name, and a line in `evidence/refreshes.jsonl` (system "Google Drive"). A missing Google token fails fast and names `jason drive --sync --interactive`.
- **Size:** Google's export is limited to 10 MB. A larger file is refused: "too large to export (Google exports up to 10 MB); open it in Google". Exporting a large Doc's PDF through `exportLinks` is proposed.
- **Restrictions:** jason reads `capabilities`, `copyRequiresWriterPermission`, and `downloadRestrictions` first. A file that forbids copies is refused, said, and logged; jason keeps no copy, and the console links the original.

**Freshness:** the answer compares the copy's `modifiedTime` with Drive's metadata from the last catalog sync, and says "Changed in Drive since this copy" (`changed: true`) when the catalog's is newer. It never refreshes on its own.

**Thumbnails:** `GET /api/drive/thumb/<id>` serves the kept PNG from disk (`jason.web.drive`): signed in, the file's level, logged in `access/served.jsonl`, with `Cache-Control: private, max-age=300`, `nosniff`, and `CSP: sandbox`; 404 "No preview yet" without one. The browser asks jason, never Google, so a screen may load it.

**Original:** `webViewLink` in a new tab: editing happens in Google, signed in as the person.

**Live frames:** only for a file that is published to the web or shared "Anyone with the link", if ever. When used, they follow these rules:
- a click-to-load placeholder;
- `referrerpolicy="no-referrer"`;
- `sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox"`;
- a `title`;
- `frame-src https://docs.google.com https://drive.google.com` in the console's CSP.

The `Embed` component's Google kinds move to this rule (see [Embed](#the-embed-component)).

**Level:** by the holdings row (`drive_copies.level_of`): a confidential row is P3, held back like a confidential library file (listed and opened only in the private view); a letter template's Doc is P0; a file under a Drive root's path rule is P0, as a library file is; any other is P2. `access.PATH_RULES` places `drive/copies/*` by the same rule.

### Drive PDFs and images

**Status:** built.

- **Copy order:** first the copy already held elsewhere (the holdings' `elsewhere`: a library file, an email attachment, a PayHOA attachment), named in the record as `reused` with nothing downloaded; otherwise `files.get?alt=media` into `drive/copies/` on a person's click (`<id>.pdf`, or `<id>.image.<ext>` for an image, checked by its bytes' signature).
- **Renders** as a pdf or an image.
- **Level:** by the holdings row, as above.

### Google Forms

**Status:** proposed.

**The blank form** is rendered read-only from `forms.get`, kept as `forms/<formId>/form.json`:
- `pageBreakItem` becomes a section;
- `textItem` becomes the form's own words;
- `choiceQuestion` shows its options, with "Other" and any go-to-section branching in words;
- scale, rating, date, and time questions show their format in words;
- a grid is a table with row and column headers;
- an `imageItem` is fetched once and kept, since its URL expires;
- a `videoItem` is a link, never an embed.

**The responses** are already kept as `forms/<formId>/responses.json` (P2). One response opens as a `submission`, rendered by the same component as a PayHOA submission.

**Uploaded files** in a response are Drive files (`fileUploadAnswers`), fetched like a Drive file on a person's click.

**Original:** the form's `responderUri` for an owner, and the edit link for the board, in a new tab. Most of the association's forms are restricted to its organization and would not frame anyway.

**Level:** the form is P0; a response is P2.

### Gmail messages

**Status:** proposed.

- **Truth:** Gmail. Today jason keeps headers (`gmail/correspondence.json`) and PDF attachments (`gmail/files/<message>/`), never bodies.
- **Copy:** `messages.get` with `format=full`, on a person's click, kept as `gmail/messages/<id>.json`.

**How it renders:**
1. **Headers:** From, To, Cc, Date, Subject, and the Google Groups it came through. A group-rewritten sender is read from `X-Original-From`, as the sync does.
2. **The body:**
   - The `text/plain` part when there is one.
   - Otherwise the HTML, sanitized on the server:
     - scripts, event handlers, forms, `<base>`, meta refresh, and external stylesheets are removed;
     - `cid:` images are rewritten to the message's own attachments;
     - **remote images are blocked** ("Load images", a person's act, through jason so that no cookie or referrer leaves).
   - The result renders in an `<iframe sandbox srcdoc>` with no tokens and its own CSP.
3. **Attachments:** listed as documents, each a further view.

**Original:** the thread in Gmail, in a new tab (Gmail cannot be framed).

**Level:** P1 to P2 by sender and content. Masking of an owner's address in a message body is the same server-side masking as a submission's.

### Scanned mail, Mailroom letters, drafts, minutes, transcripts

**Status:** proposed for each.

| Kind | Copy | Renders | Level |
|---|---|---|---|
| Scanned incoming mail | `mail/<id>/contents.pdf`, `text.txt` | pdf, with the text as a second document | P1–P2 |
| A Mailroom letter as mailed | `mailroom/previews/*-packet-mailed.pdf` | pdf | P1 |
| A draft | `drafts/*.md`, `.pdf` | markdown, pdf | P1 |
| Minutes, draft and approved | `board/minutes-*.md` | markdown | P1; the draft's privacy flags shown |
| A meeting transcript or summary | `zoom/meetings/<folder>/…` | text | P1; executive session P3, held back |
| A meeting's recording | `zoom/meetings/<folder>/audio.m4a` | audio (built: `file:<path>`) | P1; P3 for a call whose record shows an executive session, P2 when that cannot be read ([security-and-privacy.md](security-and-privacy.md#built-levels-a-stores-own-flag-decides)) |

Each becomes reachable through the same document service: named, logged, and level-checked. None should be served raw.

## Serving safely

**Built:**
- `GET /api/evidence/document/<token>` serves one viewed file:
  - only from its own folder;
  - only whitelisted types inline (pdf, images, text, audio as `audio/mp4`, `audio/mpeg`, `audio/wav`, or `audio/ogg`);
  - everything else, and always HTML, SVG, and XML, as an attachment;
  - with `Content-Security-Policy: sandbox; default-src 'none'; img-src 'self'; style-src 'unsafe-inline'`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`, and `Referrer-Policy: no-referrer`.
- A grant lasts ten minutes and allows range requests.
- A PDF renders in the browser's own viewer under that CSP in the desktop app's Chromium.

**Proposed:**
- **A second origin for untrusted bytes.** Serve documents from a second loopback origin (another port: same site, different origin) with `Cross-Origin-Resource-Policy: same-site`, so a file that escapes its sandbox still cannot reach the console's origin.
- **Check the PDF viewer in each browser.** Check the browser's PDF viewer under `CSP: sandbox` in Chrome, Edge, Firefox, and Safari. Where it refuses, the viewer falls back to "Open in a new tab".
- **PDF.js, if used.** If the console adopts PDF.js for an accessible text layer:
  - pin a version past the 2024 fix (CVE-2024-4367);
  - set `isEvalSupported: false`;
  - run it from the second origin.

## Gaps to close

These were found while writing this page. Each is a lead for the build order below.

| Gap | Risk | Fix |
|---|---|---|
| ~~`/api/file?path=` serves any whitelisted file under `data/`~~ **Closed** | No level check, no name, no log: a confidential library file, an executive-session transcript, or a scanned letter can be fetched by path | Done (`jason.web.access`): a signed-in roster person, the file's level by rule rows (P2 when no row places it), P3 only while the person's private view is open, and each serve logged in `access/served.jsonl` ([security-and-privacy.md](security-and-privacy.md#roles)). Embed's photos, PDFs, and audio, the meeting view's recording, and KeyDocuments' copies moved to `Doc` ([requests-and-links.md](screens/requests-and-links.md)): no view renders `/api/file` |
| ~~`/api/library?confidential=1`~~ **Closed** | Lists confidential rows to anyone on the loopback | Done: the confidential rows are held back (`heldBack: n`) unless the person's private view is open (P3); `/api/embeds?confidential=1` too |
| ~~`Embed` frames any ref~~ **Closed** | No host allowlist, no `sandbox`, no `referrerpolicy`; a private Google file frames blank for many browsers | Done: see [The Embed component](#the-embed-component) |
| ~~`MeetingStage` packet frames~~ **Closed** | A bare iframe, no fallback, no sandbox | Done: for the board and the host, a packet file on the stage is jason's copy, opened as one logged view (`POST /api/evidence/view`) and shown by `DocumentViewer` inline from its document link; with no copy, its `DocumentPreview` card (Read from Drive, Open in Google). Members (`audience=owner`, not signed in) see only a card: "The host is showing <name>; members receive the packet with the agenda". Nothing marks a packet file for members, so none is shown to them (a decision for the board). The stage never frames Google |
| Registers carry no Sheet link | A person can't reach the source | Return the spreadsheet's `webViewLink` with the snapshot |
| A file answer shows ids | "9,9" instead of names | In progress (the submission rules above) |

## The Embed component

`Embed` stays for what is meant to be framed:
- the association's public calendar;
- a published chart;
- a Zoom recording's share page;
- a map;
- remote audio and images, loaded on a click.

It changed in four ways (built; [requests-and-links.md](screens/requests-and-links.md#embed) has the kinds and hosts):
1. **A host allowlist per kind.** Anything else is a link card.
2. **Every frame gets `sandbox`** with the kind's minimum tokens, `referrerpolicy="no-referrer"`, and a `title`.
3. **Private Google files** (`doc`, `sheet`, `slides`, `form`, `drive` refs without a published URL) render as a document card that opens `DocumentViewer` on jason's copy, plus "Open in Google", instead of a frame that may be blank.
4. **Click to load.** A frame to an outside host loads on a person's click, not on page load (rule 2). A screen whose subject is a public frame passes `load="mount"` (the Calendar screen's and the owner page's calendar), as an `inline` P0 document is viewed on mount.

Photos, PDFs, and recordings under data/ render as `Doc` on `file:<path>`: a photo or a recording `inline`, a PDF as a card. A recording plays in the viewer's player from a logged view's short-lived link, never from `/api/file`.

## Build order

1. **Submission rendering** (in progress): sections, grouped choices, same-as pairs, file names, help, and required.
2. **Close the serving gaps:** `/api/file` callers to the document service; the library's confidential flag to the private view (built: the switch, the band, and the evidence's confidential documents).
3. **The viewer's header actions:** Open the original, ↻ inside the viewer, and the held-back count.
4. **Drive copies** (built, but the `table` renderer): the `drive:` resolver row with its export refresher, thumbnails, and the Doc, Sheet, and Slides renderers (pdf and markdown built; a Sheet's CSV opens as text until the `table` renderer). `DrivePreview` shows a file as jason's copy on the Templates screen. Built since: the `file:` resolver row and `GET /api/thumb?path=` for recorded copies on disk; `DocumentPreview` (a Drive file, a file on disk, or both, labelled) on the Records screen's governing documents, the agenda wizard's and the meeting view's packet files, and the meeting stage's packet cell. Drafts are next, then the `Doc` component that absorbs these ([doc-component.md](doc-component.md)).
5. **Embed's allowlist, sandbox, and document cards** (built).
6. **Google Forms:** the blank form and responses as submissions.
7. **Gmail messages:** sanitized bodies, blocked remote images, attachments.
8. **Mail scans, Mailroom letters, drafts, minutes, and transcripts** through the document service.
9. **The second origin for untrusted bytes;** a PDF viewer decision after the browser checks.
