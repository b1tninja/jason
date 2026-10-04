# `Doc`: one component for every document reference

A screen that names a document shows it with `Doc`, fed a `DocRef` from its loader. It never uses a raw link, an `<img>` of a file under `data/`, an iframe, or a path as text.

This page is the contract for:
- the component and its variants;
- the reference a loader returns;
- the server helpers that build that reference;
- the checklist each screen follows when it adopts them.

The behavior behind it (copies, refresh, views, levels, safe serving) is [documents.md](documents.md). `Doc` is that behavior's one face.

## The reference: `DocRef`

A loader returns references, never URLs into `data/`, absolute paths, or a document's contents:

```ts
interface DocRef {
  address: string;          // the evidence address: "payhoa:submission:1234", "drive:ID", "library:ID",
                            //   "file:board/minutes-draft-2026-10-21.md", "CIV 4920(a)", "jason://decl/6.2(a)"
  document?: string;        // one document of the address ("pdf", "text", "submission", a file id); default: its first
  name: string;             // what a person calls it, masked by the server if it held contact details
  kind: DocKind;            // "submission" | "form" | "pdf" | "image" | "text" | "table" | "html" | "message" |
                            //   "audio" | "file"
  level?: "P0" | "P1" | "P2" | "P3";
  source?: string;          // which copy: "Recorded copy", "Drive copy", "PayHOA", "Scan", "Mailroom"
  readAt?: string;          // when jason's copy was read, ISO
  size?: number;            // bytes
  thumb?: boolean;          // the server has, or can make from disk, a thumbnail
  original?: { url: string; label: string };    // "Open in Google", "Open in PayHOA", "Open in Gmail"
  refreshable?: { system: string; what: string };
  stale?: string;           // "Changed in Drive since this copy", when the server knows
}
```

**Rules for the reference:**
- **Addresses are what the evidence service resolves** ([approval-workflow.md](approval-workflow.md#evidence-you-can-open)). A new kind of document is a new resolver row, never a field a screen interprets.
- **`file:` paths are relative to the data folder** and must be placed by `access.PATH_RULES`. An unplaced folder fails closed at P2.
- **A reference never carries contents, an absolute path, or an unmasked contact.** The view (`POST /api/evidence/view`) is where contents are shown, to a named person, logged.
- **The server decides the level.** The client never infers it from a path.

**Server helpers**, in `jason.approvals.docref`, so every loader builds references the same way:
- `doc_ref(address, *, name=None, document=None) -> dict`: a light resolve. It reads only the copy's metadata, never the document.
- `file_ref(rel_path)`, `drive_ref(id)`, `library_ref(id)`, `submission_ref(n)`, `citation_ref(expr)`, and `gmail_ref(id)` once Gmail lands.
- `refs_from_strings(strings)` maps the free-text evidence strings older stores hold (`"library: …"`, `"Drive: name"`, `"data/…"`, `"jason …"`) to references. A command stays a command; an unknown string stays text, never a guess.

## The component: `Doc`

```tsx
<Doc doc={docRef} variant="chip" | "row" | "card" | "inline" />
<DocList docs={docRefs} variant="row" title="Documents" />
```

(The prop is `doc`, not `ref`, which React reserves.)

| Variant | Use | Shows | Opens |
|---|---|---|---|
| `chip` | In a sentence, a table cell, a list of evidence | Kind glyph and name; a level mark for P3 | `DocumentViewer` |
| `row` | A list of documents (a panel's Documents, a meeting's records) | 48px thumbnail or kind glyph, name, source, size or age, Preview, ↻, Original | `DocumentViewer` |
| `card` | A grid or a table's document column (Templates, governing documents, packets) | 96px paper thumbnail, name, source label, "copy from Oct 3", stale line, Preview, ↻, Original | `DocumentViewer` |
| `inline` | The document is the screen's subject (a minutes draft beside its form, a packet on the stage, a scanned letter in triage) | The document body itself, rendered by kind, with a slim header (name, source, age, ↻, Original, Open in viewer) | It is already open |

**One reference, several copies.** A screen that has both a recorded PDF and a Drive Doc passes both references. The `card` and `row` variants label them by `source` ("Recorded copy", "Drive copy"), with the governing copy first.

### States

Every variant handles each state with words, never a broken image or an empty box:

| State | Shown |
|---|---|
| Loading | The frame with "Opening…" (`aria-busy`) |
| Signed out | "Sign in with Google to open this", with the link (`signInHref`) |
| Not allowed | The server's reason: "The treasurer's office doesn't open …" |
| Needs the private view | "Confidential: open the private view to see it", with the switch's action when the person may open it |
| No copy yet | "No copy yet", with ↻ when refreshable, else the command that fills it |
| Stale | The `stale` line in the warn tone, beside the age |
| Missing | "Not on disk", with the command that fills it |
| Error | The server's sentence |

### Behavior

- **Nothing outside on load.** A thumbnail comes from jason (`/api/drive/thumb/<id>`, `/api/thumb?path=`). ↻ is a person's click, signed in, logged.
- **Opening is a view.** Preview, a chip's click, or an `inline` mount of a P2 or P3 document is one logged `POST /api/evidence/view`, never prefetched.
  - An `inline` document of P0 or P1 (a minutes draft, a statute) may load on mount, because it is the screen's subject.
  - P2 and P3 inline documents show a "Show the document" button first.
- **Original** opens the source in a new tab with the person's own session (`rel="noreferrer"`).
- **Focus.** Closing the viewer returns focus to the element that opened it.
- **No frames of outside hosts.** Never an iframe of Google, PayHOA, or Gmail. The `Embed` component keeps only what [documents.md](documents.md#the-embed-component) allows.

### Accessibility

- A chip or button's accessible name is "Open <name>", or "View <name>" in a list. Kind glyphs are `aria-hidden`, with the kind in words for screen readers.
- A thumbnail's `alt` is the document's name.
- Targets are at least 24px.
- State lines that change are announced politely.
- An `inline` document is a `region` labelled by its name.

## Adopting it on a screen

A screen moves to `Doc` in five steps:
1. **The loader** returns `DocRef`s, built with the `docref` helpers, beside or instead of the old link, path, or filename fields. It removes absolute paths and raw `/api/file` URLs.
2. **The view** replaces each link, image, iframe, or path text with `<Doc>` in the variant from the table above.
3. **Levels:** any folder the screen's documents live in has a row in `access.PATH_RULES`. A restricted folder (executive session, legal) is P3, never left to the P2 default.
4. **Tests:**
   - the variant renders from a static reference;
   - opening posts a view;
   - signed out and not allowed show their words;
   - the screen renders no `/api/file` href, no outside iframe, and no absolute path (assert it);
   - Python: the loader's references resolve (`resolve(address)` finds them).
5. **Docs:** the screen's spec in `screens/` names its documents and their variant.

## Building it

1. **Foundation**, one change, before any screen:
   - `Doc` and `DocList` with the four variants, absorbing `DrivePreview` and `DocumentPreview` (whose APIs stay as thin wrappers until their callers move);
   - `jason.approvals.docref`;
   - the `library:` and `file:` resolver rows;
   - `PATH_RULES` rows for every folder the screens below need: `mail/`, `mailroom/`, `transactions/`, `key-documents/`, `zoom/hearings/` (P3), `board/agenda*`, `board/packet*`, `notices/`, `insurance-pdfs/`, `reserve-studies/`, `cases/` (P3);
   - `Markdown` rewrites `/api/file?path=` images to `Doc` cards.
2. **Screens, in parallel**, each on its own files:

   | Group | Screens | New levels |
   |---|---|---|
   | Mail | Mail triage, the Inbox's letters, insurance notices and claims | — |
   | Meetings | Meetings and minutes, Minutes review (relative paths; the transcript `inline` beside the draft), Hearings (the notice), the meeting view's recording | `zoom/hearings/` P3 |
   | Money | Invoices, utility bills, treasurer's reports, reserve findings (fixes the empty path hint) | `transactions/` |
   | Board | Board items' evidence strings, decision briefs, Ask and Scratchpad sources | — |
   | Requests and links | PayHOA requests in Drafts and the Inbox, Key Documents, Canvases' Drive and file attachments, `Embed`'s Drive, PDF, and image kinds | `key-documents/` |
3. **Later**, each needing a new store or resolver:
   - Gmail messages (`gmail:`);
   - records produced for a records request;
   - the disclosures page;
   - legal case files (P3);
   - Mailroom letters as mailed;
   - delinquency notices sent.
