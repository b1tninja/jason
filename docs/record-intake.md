# Record intake: a checklist where a person picks the association's documents

A design (nothing here is built) for one checklist of **slots**, one for each record an association must be able to put its hands on, where a person **picks a file from Google Drive, pastes its link, or uploads one from the computer** for each, and jason reads what was picked and says what it found. The user's idea, in a line: onboarding gets a repository and checklist in which, for each required document, a person goes in and uploads or selects a Drive document.

The console's side (screens, components, states, the phone layout) is [console/handoff-record-intake.md](console/handoff-record-intake.md). This page is the model and the process, general for any association: no slot, folder, vendor, or id here belongs to one.

## What exists today, and what this joins

Four things already do part of the work. This design **adds no second store of what they hold** and says, below, which one owns what.

| Today | What it does | What the slot checklist takes from it |
|---|---|---|
| The onboarding checklist ([onboarding.md](onboarding.md)) | Items with checks (`Method`, `Kinds`, `Record`, `InBook`, `Store`, `Private`, `Fact`), computed present, partial, or missing; five stage gates | The slot list's **groups** and the **stage gates**. A slot's state feeds an item's checks; the checklist stays jason's computed reading |
| The key documents ([key-documents.md](key-documents.md)) | One entry per recorded instrument; a person **links** a copy (a file under `data/`, a Drive file by id or link, a PayHOA document), uploads one, unlinks one, or records a status; `data/key-documents/<profile>.json` | The write path for every slot whose record is a **recorded instrument** (declaration, each amendment, annexations, maps, plans, deeds). A pick for such a slot **is** a key-documents link; no second store |
| The association's records ([key-documents.md](key-documents.md), `jason records-request`, the 5200 inventory `records_inventory.inventory`) | The Civil Code 5200 records, each held by a pinned Drive sync rule, library folder, or known file; an empty group is a missing document | The slots for the 5200 records. The profile's **code pins** (`AssociationRecord`, `DeveloperDelivery`, `DocumentPin`, `LibraryFolder.records`) are one source of a slot's holder |
| Ingest ([onboarding.md](onboarding.md#ingest), `jason ingest`) | Reads a folder, a zip, or a Drive folder URL; classifies; files into the library; parks questions | The **pipeline after a pick**. A pick is a one-file (or one-folder) ingest whose source a person named |

What is new: the **slot** as a first-class row (its law, cardinality, and states); the person's **pick** as a signed act (a file or folder named for a slot, or the answer that none exists); a **chooser** for Drive; and the **reading back** to the person ("you picked X for Y; jason read it as Z"). The neighbours the screen shares ground with are in the console handoff.

## The slot

A slot is a row in jason's code, written once for every association, drawn from what jason already knows it needs. It is not typed into the console and not copied from a profile.

| Field | What it says |
|---|---|
| `key` | stable and general (`governing/declaration`, `records/5200/minutes`, `delivery/map`). A key never names an association. It is what a pin, a URL, and a command carry |
| `title` | plain words a board member knows ("The recorded declaration") |
| `requires` | the law or document that requires the record, **by citation only** (a code section, a regulation, a governing document's role); the words are recited from disk where the screen shows them (`jason cite`), never typed here |
| `group` | the checklist group it sits in (the onboarding groups, so the two never disagree) |
| `cardinality` | `ONE`, `SEVERAL` (a set that grows: amendments, annexations, policies), or `SERIES` (one for each year or period: minutes, budgets, financial statements, reserve studies) |
| `kinds` | the `DocumentKind`s a file in this slot is expected to classify as, with the shelf (`DocumentCategory`) and the 5200 record (`documents.PROFILE`) |
| `confidential` | whether the record is held back (a restricted kind), so its file's name is masked outside the private view |
| `existence` | whether "none exists" is a possible honest answer (an association may truly hold no developer's plan set), and what a person must say to give it |
| `after` | which pipeline steps apply to a file picked here, and which program or duty it can satisfy |
| `source` | where the slot comes from: the 5200 inventory, the developer deliveries, the key documents list, the document kinds, the programs catalog, or the profile's added slots |

### Where the list comes from

The slot list is **assembled by a loader from code**, never typed:

| Source | Slots it gives |
|---|---|
| `AssociationRecord` and `records.py` (Civil Code 5200) | one for each record kind; the citation comes from the same table |
| `DeveloperDelivery` (10 CCR 2792.23 and the public report) | the map, the plan, the common-area deed, the public report, the plan set |
| `key_documents.KEY_DOCUMENTS` | the governing documents, each amendment and annexation as an instrument with its recording data (the entry's recording number is part of the slot) |
| `onboarding.ITEMS` | the items a person supplies, so a slot exists for every `fills` that is a document |
| `programs` (the adoption catalog, [programs.md](programs.md)) | one slot for each program the documents mandate: the adopted document, then the implementation record |
| `documents.PROFILE` | the kinds with no slot of their own (insurance policy and certificate, contract, permit, condition-of-approval document, reserve study, budget, financial statement, minutes, agenda): a `SEVERAL` or `SERIES` slot for each |
| the unit records ([console/screens/unit-record.md](console/screens/unit-record.md)) | **not slots**: a unit's documents are the unit record's, filed by unit, never in the association's checklist |

A profile **adds or hides** slots as data: a `SlotRule` row in the profile (`Community.record_slots()`, an empty default, so another profile gets none and misses none): add a slot the association needs (a local permit condition), or hide one that cannot apply, with the reason. Hiding is a signed answer too (below). A profile that hides a slot a statute names shows it as "hidden by the profile: reason", never as absent.

### Cardinality and the series

A `SERIES` slot has one cell for each period the association has existed (or since the oldest record the law requires it to keep), and each cell has its own state, so "minutes for 2025" can be empty while 2024 is held. A `SEVERAL` slot has the instruments found so far, and a final row: "Is there another? Yes, add one / No, this is all", a person's answer, signed. A `SEVERAL` slot is complete only when someone says it is.

## The states

A slot's state is **computed from records** (a pin, an answer, a file's reading), never set by a click. The words:

| State | Means | From |
|---|---|---|
| empty | nothing picked, no answer | no pin, no answer |
| picked | a person named a Drive file or folder for the slot | the pin |
| uploaded | a person put a local file in for the slot | the pin (kind `upload`) |
| classified | jason ran the classifier and has a kind | the library's `documents` row |
| read | jason's readers ran (preflight, segmentation, OCR, the kind's reader) | the reading records |
| confirmed | a person confirmed the kind, or the split | the confirmation record |
| not applicable | a person said the record does not apply, with their name and the reason | the answer |
| does not exist | a person said the association has none, after looking, with where they looked | the answer |
| held | the file is confidential: held back outside the private view | the kind or the library flag |
| waiting on someone else | a person said who has it (the prior manager, the county, counsel) and when it was asked | the answer, with `by` and the day |
| problem | the pick cannot be read, or classified as another kind than the slot's | the readers |

**Missing is an answer, never silent.** `empty` is the state of a slot nobody has spoken for. `does not exist` and `not applicable` are different answers a person gives with their name, and each needs words: what was looked for and where ([key-documents.md](key-documents.md): "none on record is not none given"). jason never fills either, and a checklist item is never "done" because a slot is "empty" for long. The record that a slot does not exist is itself a record: it can be the thing the board wants to show a buyer or an auditor.

`confirmed` and the others are never one word standing alone: "confirmed by Jane Example, Oct 5, 2099".

## The pick: one slot, one person's act

A pick is a **person's signed act** with the slot's key, what was named (a Drive file id, a Drive folder id, an upload's hash), the person (`by`), and the day. It records an intention and **copies nothing**: the file stays where it is.

| Act | What it names | What it writes | What it does not do |
|---|---|---|---|
| Pick a file for a slot | a Drive file id (or link, or a local upload) | a pin on the slot | move, copy, share, rename, or write the file |
| Pick a folder for a slot | a Drive folder id | a **folder binding**: files in it are read as candidates for the slot, and (when the slot is a 5200 record) a proposed Drive sync rule | file anything; the folder's contents are candidates, never pins |
| Upload a local file | a file the person chose | the bytes under `data/` (below), a pin of kind `upload` | send the file anywhere |
| Replace | the new file for a slot that has one | a new pin; the old pin is marked replaced, never deleted | delete the old file |
| Not applicable | the slot, a reason | an answer | hide the slot: it stays on the list as "not applicable by Jane Example" |
| Does not exist | the slot, where the person looked | an answer | claim the record was never required |
| Waiting on someone | the slot, who, the day asked | an answer | send a request (a person sends it; the request list writes the letter) |
| Unpin | a pin | the pin is marked unpinned with who and when | delete the file |

A pick **never** makes a Drive file public, never changes its sharing, never writes to it, and never copies it out of Drive without the person's act (an ingest of a picked file is that act: the person pressed it, and the pin says so).

### Where an upload lands

A file from the computer lands in **jason's own store, not in Drive**, the way key-documents uploads already do: `data/key-documents/<profile>/files/<first 16 of sha256>/<name>` for a slot of that store, and `data/record-intake/<profile>/files/<first 16 of sha256>/<name>` for the others. Why: jason's Drive access is read-only by default for a sync (and the board's grant of the broad scope is for filing a file a person asks to move); a local upload that quietly became a Drive file would be a write the person did not name; the library already ingests from `data/`. The same file twice is one copy; a different file with the same name goes in another folder; nothing is overwritten; documents and scans only; a size cap as key-documents has. A person who wants the upload **also in Drive** asks for it as a second act ("Copy to Drive folder X", a `Confirm`, using the existing `upload_bytes`): a separate write in a named person's name, never part of the pick.

### Where a pin is stored

A pin is a **private fact**: it names a file and a person, and a file's name can be a record's subject.

| What | Where | Checked in |
|---|---|---|
| Pins, folder bindings, answers (not applicable, does not exist, waiting) for the slots key-documents does not own | `data/spec/<profile>/records.json`, written whole under a store lock, signed rows with `by` and `at`; a backup first, as the intake answers do | no |
| Pins for a recorded instrument's slot | `data/key-documents/<profile>.json` (the link), unchanged | no |
| The profile's own code pins (`AssociationRecord`, `DocumentPin`, `LibraryFolder.records`, `KnownFile`, `SyncRule`) | the profile's modules | yes (it is the association's specification) |
| An upload's bytes | `data/record-intake/<profile>/files/…` | no |

**Which wins.** A code pin is the specification's; a data pin is a person's. The rule, so a conflict is shown and never settled silently:
- both name the **same** file: one holder, the data pin adds who and when;
- they name **different** files for a `ONE` slot: neither wins. The slot shows "two holders" with both named; the person is asked which is current. A person's choice is a data pin marked `supersedes: code`, and the screen offers a **proposal to change the profile** (a patch, as `jason onboard --apply` writes, for `git apply`), never an edit of the profile. Until a person applies it, the slot's reading uses the data pin and says the profile still pins the other file;
- a `SEVERAL` or `SERIES` slot **unions** them, each row naming where it came from.

jason never edits the profile.

## What happens after a pick

Every step is a labeled reader with a tier, and the output is what the person sees. None of them runs without the person's pick; none of them changes a pin.

| Step | What it does | Tier (the console's `TierWord`) |
|---|---|---|
| 1. Fetch | Reads the file's metadata (name, type, size, modified time, the owner's domain) and its bytes through jason's own Drive token, read-only. A Google Doc comes as a Word file (the exported copy is what jason keeps; the Doc stays the original: a Drive Doc is the original of an agenda or a template). Fails fast with the reason when the token cannot read it | a fact (the file's own metadata) |
| 2. Ingest | `jason ingest`'s steps for one file: inventory (hash; a hash the library already holds is "already filed"), extract, classify. Dry run first: nothing is filed until a person applies | |
| 3. Classify | `classify_document`'s chain, in order: a person's earlier answer, the profile's kind rules (by name, PayHOA folder, library path), the phrase rules, then the local model (only when a person asked: it runs preflight and holds the GPU lock). **A miss stays a miss** | rules / model; `likely` (two readers agree) or `suggested` (one) |
| 4. Compare with the slot | The classified kind against the slot's expected kinds. Agrees: "read as an amendment, as the slot expects". Differs: **a wrong-slot pick is shown, never silently accepted** ("you picked this for the bylaws; jason reads it as the declaration"), with the slot it fits and "pin it there instead", "keep it here anyway" (a person's override, signed), or "unpin" | |
| 5. Preflight | Blank pages, text-layer quality, and what to read again ([pdf-preflight.md](pdf-preflight.md)); the cleaned rendition never replaces the original | measured |
| 6. Segment | A combined scan is split into documents and parts ([document-segmentation.md](document-segmentation.md)). **A pick of one PDF can fill several slots**: a split proposal is shown ("pages 1-34 read as the declaration; 35-41 as the first amendment; 42-60 as the bylaws"), and each part's slot is pinned only when a person confirms the split. A split nobody confirmed fills nothing | rules / model, `suggested` until confirmed |
| 7. Read | The kind's reader (`document_models`): its typed record and the fields found; OCR readings where the page was scanned, with the word layer's corrections shown as readings ([ocr-correction.md](ocr-correction.md)), never overwriting the original text | likely / suggested |
| 8. Standing | Whether the document is a draft, adopted, or recorded, and the **adoption evidence** (minutes, a resolution, a recording stamp) found, or "none found" ([programs.md](programs.md): "adoption is an act, and a quotation is not one"). A governing document's standing is a reading, with a second person's confirmation where the checklist says so | a reading, `suggested` |
| 9. Duties | `document-duties`: what the document says must be done, by whom, and when; each becomes an obligation proposal, never an assignment | a reading |
| 10. Conflicts and authority | The conflicts leads against the law in force and the rule authority ([rule-authority.md](rule-authority.md)); a lead is read beside the statute before it becomes a row | a lead |
| 11. Programs | Which program in the adoption catalog this file adopts or implements, element by element, or "no program found" | a reading |

What the person sees is the same four lines for every pick: **you picked X for Y; jason read it as Z (likely, or suggested, and by which readers); here is what it found; here is what you confirm.** A reading by a model alone is a suggestion held for a person, as everywhere ([console/handoff-intake-review.md](console/handoff-intake-review.md): `TierWord`).

## Choosing the files: the picker verdict

The question: how does a person select Drive files in the console? Four ways, checked against Google's documentation (fetched October 5, 2026) and against what jason already is.

### What jason already is

- jason's Drive reads use **one OAuth token held on the server** (`secrets/google-token.json`, from the Desktop client), and the scopes it asks for already include **`drive`** (granted by the board on September 29, 2026, so a person's move can be filed), `drive.readonly`, and `drive.file` (`jason.google.scopes`). The sync, the catalog, the copies, and `jason ingest <Drive folder URL>` read through it.
- The console is **loopback-only** (`127.0.0.1:8080`) and puts **no credential in the browser**. No Google script is loaded into the page today (console sign-in is the server's OpenID Connect flow, "no Google script is loaded into the page"). The documented exceptions to "no outside resource" are three, each on first use, and none is a Google script ([console/security-and-privacy.md](console/security-and-privacy.md#outside-resources)).
- Each community has its **own Cloud project, an Internal app, and a Web client** (decided October 5, 2026: [integrations-design.md](integrations-design.md#google-workspace)). The Web client's **authorized JavaScript origins are left empty today** ([setup.md](setup.md#5-console-sign-in-jason-web)).

### The four ways

| Way | What it is | Needs | Reads with | Verdict |
|---|---|---|---|---|
| **A. jason's own chooser** | A dialog in the console that lists Drive through the **server** (`files.list`, `files.get`): My Drive, shared drives, search by name, folders to open, the file's name, type, size, and modified time. A person selects one or more. | nothing new: the existing token; no key, no app id, no origin, no script | jason's server token (`drive`) | **Primary** (phase 2) |
| **B. Paste a link or id** | The person copies a Drive link (or the id) and pastes it; jason resolves it (`files.get`, read-only) and shows the name before the pick is recorded. Any Drive or Docs link form is accepted, as key-documents already does | nothing new | the server token | **Primary for phase 1**, and always available |
| **C. The Google Picker** | Google's own "File Open" dialog, a script (`apis.google.com/js/api.js` with the picker module, and `accounts.google.com/gsi/client` for a browser access token) in the page | an API key (website-restricted to allow `docs.google.com`, since the picker renders in an iframe there); the Cloud **project number** (`setAppId`); a Web client with **authorized JavaScript origins** for the console's origin; an access token **in the browser** (`setOAuthToken`) | a picked file's id; then jason's server token | **Fallback**, if a community wants Google's own chooser or a narrower scope |
| **D. Upload from the computer** | A file chooser in the browser; the bytes go to jason's store | nothing | jason's own store | Always available (phase 3) |

### What the documentation says, and what follows

- **The picker needs a browser access token.** Google's web guide: an app "must send an OAuth 2.0 access token with views that access private user data" (`setOAuthToken`), and it needs an API key (`setDeveloperKey`) and the project number (`setAppId`), with the OAuth client's **authorized JavaScript origins** configured in the Cloud console. ([Integrate the Google Picker into web apps](https://developers.google.com/workspace/drive/picker/guides/web-picker); [the web sample](https://developers.google.com/workspace/drive/picker/guides/web-picker-sample); [the reference](https://developers.google.com/workspace/drive/picker/reference/picker).) jason's rule is that the console holds **no credential**, and its server-held token is a Desktop client's. So the picker needs a **second, browser-side token**, obtained through Google Identity Services with the community's Web client, and a Google script in a page that today loads none. That is an exception to "no credential in the browser" and to the outside-resource list, and it is a person's decision, not a default.
- **`drive.file` is per app.** Google's scope page describes it as access to files "that you open with an app or that the user shares with an app while using the Google Picker API", and recommends it as the narrowest scope; `drive` and `drive.readonly` are **restricted** scopes ([Choose Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)). The documentation fetched **does not say** that a pick made with one OAuth client's browser token extends to a different client's server token. The access is the app's (the OAuth client or project) that the person picked with. So **a pick in the browser under the Web client does not, on that evidence, let the server's Desktop-client token read the file.** jason would have to read the picked file with a token of the same client (a Web-client token the server obtained through the authorization-code flow), and that has not been tried. Treat as unproven until a test with a real file says otherwise.
- **This matters little to jason today**, because jason's server token already holds `drive` and can read any file the person can. The picker's value to jason is Google's familiar dialog and its handling of shared drives and search, not access. The picker does not need to grant access, only to **name a file**; a name would do (the id).
- **Folders and shared drives.** The picker's reference lists `setIncludeFolders` and `setSelectFolderEnabled` for folder selection, the `MULTISELECT_ENABLED` feature, and `SUPPORT_DRIVES` for shared drives; its response gives an `action` (`PICKED`, `CANCEL`, `ERROR`) and `docs` (each with an `id`, and a name and type). The picker "doesn't allow users to organize, move, or copy files" (the web guide). All of that is **also doable through way A** with the Drive API (`supportsAllDrives`, `includeItemsFromAllDrives`, `q` on `mimeType`/`parents`).
- **Loopback origins: not verified.** The setup guide's redirect rule for loopback is verified in practice (a Desktop client and loopback redirect addresses). Google's OAuth policy page fetched says Web-client origins "must use the HTTPS scheme" and does not address `http://127.0.0.1` or `localhost` for **JavaScript origins**. Whether the picker's token flow accepts `http://127.0.0.1:8080` as an origin is **unknown**; the test is one try in the community's Cloud project (add the origin, request a token), and it is the first thing phase 2b would check. A hosted console (https) has no such question.
- **Restricted-scope review.** The community's app is **Internal**, so restricted scopes need no Google verification ([integrations-design.md](integrations-design.md#google-workspace)); this holds for either path.

### The recommendation

- **Primary: way B in phase 1, way A in phase 2.** The console's own chooser over the server token. It works on loopback today, adds no script, no key, no browser token, no origin, no project number, and no new scope; it reads only, and can show jason's classification of what is listed (a file already in the library, a file in a folder a sync rule covers, a file pinned elsewhere). Its cost: jason builds the dialog (a tree, a search, a list), which Google's picker gives free.
- **Fallback: way C, the Google Picker,** behind an administrator's switch, **only** if (a) a community will not grant jason a broad scope and wants `drive.file` alone, or (b) the people choosing find jason's dialog worse than Google's. It needs the exception above and the loopback-origin check, and its pick would **name** a file the server then reads with a token that can (so the scope question above must be answered first). Its result is only ever **an id** into the same pick act.
- **Always: way D** for paper someone scanned, and for a file nobody put in Drive.

### What jason must not do (any way)

- never make a file public, change a file's sharing, or add a person to it;
- never write to, rename, move, or trash a picked file as part of a pick (a move is a separate, signed act the board has authorized for filing, and is not a pick);
- never copy a file out of Drive (an ingest) except at a person's act, signed, naming the slot;
- never keep a browser token on disk, in a URL, or in a log; never put a file's name or id in a URL ([console/security-and-privacy.md](console/security-and-privacy.md#urls)): a slot's key is in the URL, the file's id is in a POST;
- never list a folder the person's own Drive access could not list (the server token is the **signed-in person's** where possible; today it is jason's one account, so the dialog lists what **jason's account** sees and says so: "jason's Drive account sees these").

The last point is a real limit: jason reads Drive as one account, so the chooser shows that account's files, not the signed-in person's. A person who wants to pick a file jason's account cannot see must first **share it with that account** in Drive (one line the chooser shows beside "not found"), or upload it (way D). That is also what a Drive pick of a private file requires with any picker, since the server must read it.

## The acts in the console, and their commands

Each is a `Confirm` in a named person's name through the write guard; nothing is applied outside jason. The command names below are **proposed**; `jason records` is a free name (the parser has `records-request`, `record-stages`, `key-documents`, `intake`, `onboard`, `ingest`, `library`, `drive`; `intake` is the question queue, a different thing from this).

| Act | Command (proposed) | Built today |
|---|---|---|
| List the slots and their states | `jason records [--group G] [--state S] [--json]` | the checklist's items: `jason onboard --checklist`; the 5200 inventory; `jason key-documents` |
| One slot, with its candidates and its pins | `jason records --slot KEY` | no |
| Pick a file | `jason records --pick KEY --file ID_OR_LINK --by NAME` | for a recorded instrument: `jason key-documents --link ENTRY --drive LINK --by NAME` already does it |
| Pick a folder | `jason records --bind KEY --folder ID_OR_LINK --by NAME` | no (a sync rule is a profile row) |
| Upload | `jason records --upload KEY --file PATH --by NAME` | for a key document: `jason key-documents --upload ENTRY --file PATH` |
| Replace | `jason records --pick KEY --file ID --replace --by NAME` | no |
| Not applicable, does not exist, waiting | `jason records --answer KEY --not-applicable\|--none\|--waiting WHO --note TEXT --by NAME` | for a key document: `jason key-documents --status ENTRY --set missing --note TEXT` |
| Unpin | `jason records --unpin KEY --pin ID --by NAME` | for a key document: `--unlink` |
| Read what was picked | `jason records --read KEY` (the pipeline's steps, dry run) | `jason ingest` over a Drive URL; `jason drive --record R` |
| Confirm a kind or a split | the confirmations queue's act, not a new command | [console/handoff-confirmations-queue.md](console/handoff-confirmations-queue.md) |

Where a built command already does the job (`jason key-documents`), `jason records --pick` for that slot **calls the same function**; there is one writer. The profile's code pins can be listed with `jason records --pins`.

## What a person needs, from day 1 to day 30

1. **Day 1.** An administrator has connected Drive ([onboarding.md](onboarding.md#connecting-integrations-todo)); the checklist is almost all empty. The first screen shows the groups, the count of slots, and "the biggest unknowns first": the slots a stage gate waits on, then the slots a statute names with a clock.
2. **Day 1-3.** The board's secretary, who holds a Drive folder, **binds the folder** to the groups it holds (one act, many candidates). jason lists what is in it, classifies, and offers each file to the slot it fits: a person confirms or moves each. Files the person already knows are **picked** one at a time; the rest are left.
3. **Week 1.** A box of scans is uploaded; segmentation proposes splits; a person confirms. A prior manager is asked for the rest: the slots go to "waiting on someone else" with who and the day, and the request list writes the letter.
4. **Week 2.** The association's amendments are picked as instruments with their recording numbers (the declaration's graph and the locator's leads shown beside). The second person confirms which text is in force.
5. **Week 3.** Policies and programs: for each program the catalog says the association must adopt, a person picks the adopted document or says none exists; the gap report writes itself from the "none exists" answers.
6. **Day 30.** What is left is only answered: each slot is held, or `not applicable`, or `does not exist`, or `waiting` with a name. The board has a list of what it does not have, with the law that says it should, to act on. The gates can open.

## Privacy

- A slot's **file name is masked** where its kind is confidential: the level follows the file's kind and the library's flags (`access.PATH_RULES`, the library's `confidential`); outside the private view the slot says "a confidential file is pinned (kind: legal)" and no name, and its bytes are never served ([console/security-and-privacy.md](console/security-and-privacy.md#data-levels)). A slot whose **existence** is the secret (a settlement) is shown by its group only.
- The pin file is P3 (`data/spec/` is P3). The checklist screen shows slots, states, and counts to the board; a file's name to those who may open the file.
- The checklist is **board-only**. An owner never sees a slot; an owner's view of the records the association holds is the records page and the records request.
- A name or text that looks like a secret is refused by `intake.secret_reason` in a note, as everywhere.

## What stays a person's

Choosing the file; saying a record does not exist or does not apply; confirming a kind, a split, or a standing; applying a proposal to the profile; copying a file to Drive; sending a request for a missing record. jason proposes and reads; it never decides that a record is complete or that an association has no obligation.

## Phases

| Phase | What | What it proves | Effort |
|---|---|---|---|
| 1 | The checklist read-only from jason's catalog (the loader `record-slots`), the states computed from records already on disk, **paste-a-link pin** and the three answers (not applicable, does not exist, waiting), `jason records` | that the slot list is right, that people will answer "none exists", and that the key-documents writer serves every slot | about a week: a loader, a store, a screen, no new Google |
| 2 | **jason's chooser** (way A) over the server token; folder binding; the reading back after a pick (steps 1-4) | that the chooser works without a script and a person reaches a file in a shared drive | about a week and a half: a Drive listing route, a dialog |
| 2b | **The Google Picker** (way C), if wanted | the loopback-origin question and the cross-client scope question | a day to test, a few for the page, a person's decision first |
| 3 | **Upload** and the whole pipeline (steps 5-11): segmentation proposals, standing, duties, programs, conflicts | that a pick of one scan fills several slots, and the board gets a gap list | two weeks, mostly wiring existing readers |

## Open decisions

See the list in [console/handoff-record-intake.md](console/handoff-record-intake.md#decisions-for-the-design); the ones that are a person's call before a build: whether the console may carry the Google Picker's script and a browser token (way C); whether a pick of a folder may propose a sync rule (it proposes, a person applies); where an upload lives when a community wants it in Drive; and whether the profile's `SlotRule` may hide a slot a statute names.
