# Records

`#/setup/records` (the checklist) and `#/setup/records/<key>` (one slot) in Setup · built · loaders `GET /api/record-slots`, `GET /api/record-slot?key=`, writer `POST /api/write/records/<slot key>`, and the Drive chooser's `POST /api/write/drive/{list,search,resolve,bound}` (`jason.web.extra.record_slots`, `jason.web.extra.drive_choose`) · design: [../handoff-record-intake.md](../handoff-record-intake.md), model and process: [../../record-intake.md](../../record-intake.md)

## In the console

One component, `RecordsView` (`ui/src/views/RecordsView.tsx`), reads the hash and draws the checklist or one slot. The console resolves a route by the whole path, then by each shorter prefix (`findScreen` in `App.tsx`), so `setup/records/<key>` lands here. The slot key is URL-encoded (`records%2F5200%2Fminutes`); a file's name or id is never in a route or a query.

| Screen | Route | Who sees it |
|---|---|---|
| **Setup > Records** | `#/setup/records` (`?state=`, `?group=` pre-filter) | officers, managers, administrators (`roles` on the screen). Never the owner view: it is not in `ownerScreens.json`, and the loaders refuse `view=owner` |
| **A slot** | `#/setup/records/<key>` | the same |

### The checklist

- **Counts.** One button for each state (empty, picked, uploaded, classified, read, confirmed, not applicable, does not exist, waiting on someone else, problem) with its count; pressing one filters the list and the button says it is pressed. The same counts are a table under "Counts as a table". Held-back and profile-hidden totals are said in words.
- **Biggest unknowns first.** The slots a gate waits on, then those a statute names, each linking to its slot, with how many other slots wait on it. First run (every slot empty) says so.
- **Groups.** One disclosure per group (the first, any filtered view, and any group with a problem open). Each is a table with a caption: slot (cardinality, hidden-by-profile reason), state (a word with a glyph; a problem's reason; a series' periods each with its own state; "two holders"), files (pins, held back, candidates), required by (citations, or "jason's own design"), and the next step. On a phone each row is a stacked card with the column names beside the values.
- Nothing is computed on the page except the filter. A state, count, and verdict arrive from the server.

### A slot

In the order a person needs it:

1. **What requires it.** The citations the server names (the statute's words come from `jason cite`, never typed here), the reason jason needs it, and any problem.
2. **Two holders.** A collision is an alert naming both holders and who they come from; unpinning the one that is not current settles it. Neither wins silently.
3. **What holds it.** Each pin: the name (a confidential file is "a confidential file (kind: ...)", with "opens in the private view"), who pinned it and when or "the specification", its state word, and the reading in the four lines of every pick: *you picked X for Y; jason read it as Z (likely or suggested, by which readers); what it found; what you confirm.* The verdict is agrees, differs, or unclassified. Preflight facts (pages, blank, text layer, share doubtful, what to re-read), findings, and a combined scan's proposed split (pages, kind, tier, the slots each part fits, proposed only until confirmed) are shown. A changed file is an alert with the diff of facts.
4. **Wrong-slot notice.** `role="alert"`, first on the holder: "You picked this for X. jason reads it as Y (tier). This slot expects Z. It fits: W." with **Pin it to W**, **Keep it here anyway** (a reason is required), and **Unpin**. Nothing changes until a preview is confirmed.
5. **Your answer.** The standing answer with its words and who gave it (none exists, not applicable, waiting on someone else), the "Is there another?" answer for a set that grows, and the acts to answer, say there is another or this is all, and reopen. Empty is said to be not the same as none.
6. **Choose a file.** Choose from Drive, Paste a link, Upload from this computer (all one dialog, see below), and Bind a Drive folder.
7. **Bound folders**, **files jason classified for this slot** (each with **Pin it**), the **standing block** (duties that rest on this record, recorded conflicts that cite what it requires, programs: "Unavailable" with the server's reason while the catalog is not built), the **history** (the trail, never emptied, no file name), the same acts as terminal commands, and the caveats.

### Acts

Every act is the same three steps: its fields, **Preview** (the writer's dry run, `dryRun: true`), then one confirm button spelled with the act ("Pin Policy 2099.pdf to Example policy"). Changing any field discards the preview, so what is confirmed is what was previewed. The preview names who it is recorded as (the signed-in person; with no one signed in the buttons are disabled and say why), and says nothing in Drive, PayHOA, or the county is touched. A refusal is shown as the server said it (`role="alert"`) with nothing written. After a confirm the slot reloads and a status line says what was recorded; focus goes to it.

| Act | Body (`act`) | The preview shows |
|---|---|---|
| Pick a file (from the chooser, a pasted link, or a classified candidate) | `pick`: `file`, `period` (series), `entry` (a repeating key document), `note` | what would be written |
| Read | `read`: `pin` | metadata only: the file's name, how big it is, "read as a Word copy; the Doc stays the original", whether it would be fetched or is unchanged. Confirming queues a job in the person's name; the page polls `GET /api/jobs?job=ID` and says queued, running, done, failed, or cancelled. It never reads inline |
| Keep | `keep`: `pin`, `note` (a reason, required) | the keep row |
| Repin | `repin`: `pin`, `to` (a slot jason found), `period`, `entry` | both halves of the move |
| Unpin | `unpin`: `pin`, `note` | the unpin; the file is untouched |
| More ("is there another?") | `more`: `value` yes or no | the answer |
| Reopen | `reopen`: `what` answer or more | the reopening; the earlier answer stays in the trail |
| Answer | `answer`: `value` none, not_applicable, or waiting; `note` (where you looked, or why; required for the first two), `who` (waiting) | the answer |
| Bind a folder | `bind`: `folder` | the **proposed sync rule's text**, with "Nothing is applied here." The page applies no rule |
| Upload | `upload`: `name`, `base64`, `period`, `entry`, `note`, optional `override` | size, type, hash, whether the same bytes are already pinned or pinned elsewhere, the collision if the slot holds a file. The limit (`upload.max_bytes`, from `GET /api/limits`) is shown beside the chooser; a file over it is warned about on the page, pointed to Drive, and previewed anyway so the server's words (and an administrator's once-only override, with a reason) decide. The reading is queued as a job |
| Split | `split`: `pin`, `parts` (`segment`, `slot`, `period`, `entry`); or `decline` | each part with its pages and the slot chosen, a collision as "a collision, so this part is not written", and nothing for a part left unnamed |
| Replace | `replace`: `pin`, `file` (a link) or `name` + `base64`, `period`, `entry`, `force` | **both halves**: first the new file's pin, then the old pin's unpin. A pin someone kept needs the box ticked |
| Acknowledge | `ack`: `pin` | the mark seen; it stays on the reading as history |

### The Drive chooser

`DriveChooser` is a modal dialog (`role="dialog"`, `aria-modal`, labelled "Choose a file from Drive for THE SLOT") with three sources as a tab list (arrow keys, Home, End): **Drive**, **Paste a link**, **From this computer**. Focus moves to the heading and returns to the button that opened it; Tab stays inside; Escape closes it and the page says "Nothing was picked." On a phone it is a full-screen sheet with a sticky footer holding the selection and **Pick**.

- **Drive.** Every read is a POST, so no name or id sits in a URL: `POST /api/write/drive/list` (`{parent, drive, page}`), `/search` (`{q, page}`), `/resolve` (`{ref}`). The first line says whose eyes: "jason's Drive account (ACCOUNT) can see these files. A file it cannot see is not listed: share it with that account, or upload it." A breadcrumb (`nav`, `aria-current`), shared drives, a name search, and **Show more** for the next page. Files are a radio group (one pick at a time); a folder is a button that opens it and announces "Opened NAME, N items". Each row carries jason's own knowledge (in the library as a kind, in a folder a sync rule covers, pinned for another slot) and, for a Doc, "jason keeps a Word copy; the Doc stays the original". A file jason cannot open is listed and disabled with why and the way out; a confidential file's row has no id and is disabled, saying it opens in the private view. **Choose this folder for THE SLOT** is a binding, not a pick.
- **Not connected.** The server's sentence and the command to run, in an alert; the dialog never opens a browser, and the upload tab still works.
- **Paste a link.** A link or id is looked up read-only and read out ("Found: NAME, a PDF, 391 KB, modified DAY, owned in DOMAIN."); not found, not Drive's, and not readable are each a sentence; a folder is offered as a binding. The pick sends the text the person pasted.
- **From this computer.** A labelled file input (no drag required), the limit in words, "kept in jason's store, not sent to Drive or anywhere else", then the same preview and confirm. A series asks for the period.
- **Pick.** Selecting a row and pressing **Pick** opens the same preview and confirm in the dialog. A pick records which file is meant; it moves, copies, renames, and shares nothing.

## Privacy

A slot's file name is masked by the server where its kind is confidential, and the page shows the masked text and "opens in the private view" (the private view is the console's own, not a control here). Findings of a held file are not shown. A Drive file's id is only ever in a POST body. The checklist is board only.

## Accessibility and the phone

Native `details` for groups; real tables with captions and column headers; a state is a word with a glyph, the tone only repeats it; every field is labelled and the act's heading takes focus when it opens, the preview when it appears; refusals and the wrong-slot notice are `role="alert"`; results and job progress are `role="status"`; targets are at least 24 px (44 px in the chooser's rows on a phone); reduced motion removes transitions. Under 720 px the tables become stacked cards and the dialog a full-screen sheet. Colors are the console's tokens, so dark and light follow; the styles are `ui/src/views/records.css`.

## Not built

Google's Picker (phase 2b of [record-intake.md](../../record-intake.md), a person's decision first); choosing several files in one pick (the chooser picks one at a time); the "current" act for a collision (the server answers "not built yet"); the series' span (a series shows the periods that have a pin).

## Tests

`ui/src/views/records.test.tsx`: the route and its roles (never an owner screen), the encoded slot key, the checklist (counts, filters, first run, hidden slots, the server's note), a slot (the law, the reading's lines, masking, the standing block with programs unavailable, the trail), the wrong-slot notice with a repin as a preview then a confirm recorded as the signed-in person, keep with a required reason, a refusal in the server's words, the answers and the reopening, a read that previews its size then queues and watches a job to done or failed, acknowledge, replace with both halves, a split with a collision and a decline, a binding that shows the proposed rule and applies nothing, and the chooser (POST reads with no name in a URL, folders, search, masked and unreadable rows, not connected, Escape, arrow keys, paste, upload with the limit, a series' period). Fixtures are made up and `fetch` is stubbed, as in the other screens' tests.
