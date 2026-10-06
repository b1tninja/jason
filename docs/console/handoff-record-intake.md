# Handoff: the record checklist, where a person picks the association's documents

For the design pass on the checklist of **slots** a new association fills at onboarding: one for each record the law or a governing document says it must hold, where a person **picks a Drive file or folder, pastes a link, or uploads a file**, or says **none exists**, and jason reads what was picked and says what it found. The model, the pipeline after a pick, the picker verdict, and the phases are in [../record-intake.md](../record-intake.md); this page is the console's side: the screens, the components, their states, the data, and the words. Behavior and words are settled by this page, [README.md](README.md) (principles 1 to 9), [components.md](components.md), [content/style.md](content/style.md), [content/patterns.md](content/patterns.md), and [security-and-privacy.md](security-and-privacy.md).

**What exists today.** The onboarding screens ([screens/onboarding.md](screens/onboarding.md)): the Setup tab (the stage gates, the computed checklist, the questions), **Find the association** (`DocumentLocator`), and **Key documents** (`KeyDocuments`: link, upload, unlink, and status for each recorded instrument, `POST /api/write/key-documents/<key>`). The library and its ingestion ([screens/records-and-library.md](screens/records-and-library.md), `#/ingestion`), the 5200 records page (`#/records`), and the review of what a scan holds ([handoff-intake-review.md](handoff-intake-review.md)). No screen lets a person pick a Drive file for a record that is not a recorded instrument, and none shows the whole checklist of records with a person's answer to "does one exist".

**The neighbours, and what changes in each.**

| Neighbour | What it shares | What changes there |
| --- | --- | --- |
| [screens/onboarding.md](screens/onboarding.md) (the Setup tab, `ChecklistItem`, `GateRail`) | the groups and the stage gates; an item's computed status | a new tab, **Records**, in the `#/onboarding` tab row after **Key documents**. A `ChecklistItem` that is a document gets one line: "3 of 5 slots held" with a link to the group's slots. The item's status stays jason's computed reading; a slot feeds its checks, a click never sets it |
| `KeyDocuments` (key-documents.md) | the recorded instruments, their writes | **no second writer.** On the Records tab the key-document slots render through `KeyDocuments`' own rows and write through its route; the tab's `SlotRow` for them is a summary line that opens the same row. Nothing in the key-documents screen changes |
| [handoff-held-setup-roster.md](handoff-held-setup-roster.md) (`PendingAnswer`, `PersonSteps`, `ChecklistItem`) | an answer given and waiting; a person's step | "waiting on someone else" is a slot state drawn with `PersonSteps`' row (who, the day, from a record, never a click). The held-roster's `HeldRow`/`PrivateGate` draw a confidential slot. Its decision 3 (a standing question's place) is unaffected |
| [handoff-confirmations-queue.md](handoff-confirmations-queue.md) | a classification a person confirms | a wrong-slot pick, an unconfirmed kind, and an unconfirmed split are **items in that queue** (kind "classification") as well as lines on the slot. The queue gets a fourth kind, **record reading**, with its own act; nothing is confirmed twice |
| [handoff-intake-review.md](handoff-intake-review.md) (`PreflightCard`, `SegmentTree`, `OcrReview`, `TierWord`) | what jason found in a scan | a slot's page embeds those components by link and by their summary line; it does not draw a second copy |
| [handoff-programs.md](handoff-programs.md) (`ProgramDocumentCard`, `AdoptionEvidenceRow`) | the document that adopts a program | a program's slot is the card's "pick the adopted document" act; the card's "none exists" is the slot's answer, one record |
| [handoff-storage-and-settings.md](handoff-storage-and-settings.md) | where uploads land; the machine's drives and locks | the upload folder is a `PlaceRow`; an upload with the drive short is refused with `MachineProblems`' words; a model reading holds the GPU lock and shows `ModelStack`'s state |
| [handoff-unit-records.md](handoff-unit-records.md) | a unit's documents | **not part of this checklist**: a unit's file belongs to the unit record |

## The idea in one line

Each record the association must hold is a **slot** on one checklist. For each, a person names a file, uploads one, or says in their own name that none exists; jason then reads the file and says what it found, and **a wrong pick is shown, never silently accepted**. The state of a slot is computed from those records and no control sets it, so "missing" is always an answer a person gave or an honest "nobody has spoken for this yet".

## The components

New parts only where this table says so; each is built from the parts in [components.md](components.md). Collisions checked against components.md and the earlier handoffs: `ChecklistItem` (the held-setup handoff) is **reused**, not redefined; the chooser is named `DriveChooser` and not `DrivePicker`, to keep it apart from **Google's Picker** and from `DriveAttach` (the agenda's attach) and `AssociationPicker`/`EntryPicker`; the slot's state word is `SlotWord`, a `Pill` preset, and is not `StandingWord` (programs) or `TierWord` (a reading's tier, reused).

| Component | Built from | Where it renders | Data | States to design |
| --- | --- | --- | --- | --- |
| `RecordChecklist` | `Tabs` (the group row), `Stat`, `DataTable`, `Caveats` | the **Records** tab of `#/onboarding` (`#/onboarding?tab=records`) | `GET /api/record-slots` | first run (all empty: the groups, the counts, "the biggest unknowns first"); loading; listed; filtered to none; Drive not connected ("jason cannot read Drive. Ask an administrator to connect it", with the command); the loader failed (the note and `jason records`); all answered ("Every slot is held or answered. Open the gates?"); a hidden slot ("hidden by the profile: reason") |
| `SlotProgress` | `Stat` strip with a table twin | above the list | `counts` | by state, by group, by law ("of the 5200 records: 9 of 15 held"); the biggest unknowns (the slots a stage gate waits on, then those a statute gives a clock); what blocks what ("the declaration's amendments wait on the declaration") |
| `SlotGroup` | `Card`, `Disclosure` | one per group | a group's slots | open or collapsed (the group holding the first closed gate opens); the count in its summary in words |
| `SlotRow` | `DataTable` row, `SlotWord`, `Doc` chip | each slot | one slot | the states in "The words"; cardinality (one, several with a count, a series with its periods as cells); confidential (name masked); a problem (its reason in words on the row); a row on a phone is a card |
| `SlotWord` (a `Pill` preset) | `Pill` | in `SlotRow`, `SlotPage`, `SlotProgress` | the slot's `state` | empty, picked, uploaded, classified, read, confirmed, not applicable, does not exist, held, waiting on someone else, problem: each a word, a glyph, a tone that only repeats it |
| `SlotPage` | `Card`, `Recitation`, `Findings`, `Command` | one slot (`#/onboarding/records/<key>`) | `GET /api/record-slot?key=` | the law first (a `Recitation` of what requires it, or a `CitationChip` where the shelf lacks it); what is held; the candidates; the acts; the log; a slot with no law named ("jason's own design needs it") |
| `ExistenceAnswer` | `QuestionCard` preset, `Confirm` | in `SlotPage` and beside an empty `SlotRow` | `existence` | not asked; "Does the association hold one?" three answers (a file, none exists, not applicable); each opens its own field (where you looked; why it does not apply; who has it and the day you asked); answered (by whom, when, the words); a `SEVERAL` slot's closing question ("Is there another?") |
| `SlotActs` | `Confirm`, `Command` | in `SlotPage` | `acts` | pick a file, pick a folder, upload, replace, unpin, the three answers: each a `Confirm` that names the slot, the file, and the person; an act the person's office may not take shows the reason in words |
| `DriveChooser` | `DataTable`, `SearchBox`, `Breadcrumb`, `Pill` | a dialog opened from `SlotActs` ("Choose from Drive") | `GET /api/drive/list?parent=&q=&drive=`; the pick is `POST /api/write/records/<key>` | see "The chooser's states" below |
| `FileSourceTabs` | `Tabs` | top of the dialog | none | **Drive** (the chooser), **Paste a link** (`PasteDriveLink`), **From this computer** (upload); a source not available is absent with its reason, never greyed |
| `PasteDriveLink` | `Field`, `Doc` | the second tab | `GET /api/drive/resolve?ref=` (server reads metadata only) | empty; resolving; resolved (the name, type, size, modified day, the owner's domain, "jason can read it"); not found or not shared with jason's account (the one line: share it with the account shown, or upload it); a link to a folder (offered as a binding); a link that is not Drive ("That is not a Drive link"); never shown a file's id in the page's URL |
| `UploadStep` | `Field` (file), `Confirm` | the third tab | the file in a `POST` (base64, as key-documents), size cap | chosen (name, size, hash first 12); too large ("larger files belong on Drive: share and pick it"); not a document ("scans and documents only"); the drive short (`MachineProblems`); written ("kept in jason's store at data/…, not sent anywhere"); a duplicate ("the same file is already filed as … "); an optional second, separate act: "Also copy to Drive folder …" |
| `FolderBinding` | `Card`, `DataTable` | in `SlotPage` and the group's header | `bindings[]` | none; bound (the folder's name, its file count, how many read, how many placed here, there, or nowhere); a file in the folder jason reads as another slot's kind (offered for that slot, never moved); the proposed sync rule (a `ProposalFlow` patch to apply, never applied here); the folder not readable |
| `PickReading` | `ReadingLabel`, `TierWord`, `Findings`, `Doc` | at the top of `SlotPage` after a pick | `reading` | pending (steps listed, each as it finishes); the four lines: **you picked X for Y; jason read it as Z (likely / suggested, by which readers); what it found; what you confirm**; agrees; **differs** (`WrongSlotNotice`); classified nothing ("jason could not tell what this is. It stays unclassified; a person says what it is"); already filed; a model reading running (holds the GPU lock) or refused ("not run: short of memory"); a failed step named, the others shown |
| `WrongSlotNotice` | `HeldNote`, `Confirm` | in `PickReading` | `reading.kind` against `slot.kinds` | "You picked this for the bylaws. jason reads it as the declaration (suggested by two readers)." with three acts: **Pin it to the declaration instead**, **Keep it here anyway** (a person's override, signed, with a reason), **Unpin**. Neither the slot nor the other is changed until a `Confirm` |
| `SplitProposal` | `SegmentTree`, `Confirm` | in `PickReading` for a combined file | `reading.segments` | proposed (each part with its pages, its kind, its slot, its tier; none pinned); partly confirmed; confirmed (each part's slot now `picked`); declined ("the file is one document"); the parts' slots already held (offered as "a newer version?", never replaces) |
| `CollisionNote` | `Findings` | in `SlotPage` | `holders[]` | one holder; **two holders** (a code pin and a data pin, or two data pins) each named with where it comes from and a "which is current" act that writes a data pin marked as superseding the profile's and offers the patch; a series cell with two |
| `PickTrail` | `AuditLog` | in `SlotPage` | `log[]` | each act (who, the day, what), including replaced and unpinned pins; the trail is never emptied |

### The words

Every state is a word the code carries, and the glyph and tone only repeat it.

| Word | Meaning | Never means |
| --- | --- | --- |
| empty | nobody has spoken for this slot | the record does not exist |
| picked / uploaded | a person named a file; jason has not read it yet | the file is the right one |
| classified | jason has a kind; **likely** (two readers agree) or **suggested** (one) | confirmed |
| read | the readers ran; what they found is listed | verified against the law |
| confirmed by NAME, DATE | a person confirmed the kind (or the split) | adopted, or complete |
| not applicable, by NAME: reason | a person says it does not apply to this association | that the law does not require it |
| does not exist, by NAME: where they looked | a person says the association holds none | that none was ever made |
| held | the file's level holds its name and text back outside the private view | missing |
| waiting on WHO, asked DATE | a person says who has it | that a request was sent (a person sends it) |
| problem: the reason | the file cannot be read, or reads as another kind | an error to dismiss |

"Approve", "accept", and "complete" appear on no control. "Done" is never a state of a slot. A series cell and a `SEVERAL` slot are **answered** only when someone says "this is all" or "none". The words about jason are "jason read it as" and "jason found", never "jason knows".

## The chooser's states

`DriveChooser` is a dialog (`role="dialog"`, labelled "Choose a file from Drive for THE SLOT") with the sources as tabs. In its Drive tab:

- **Header line, always:** "jason's Drive account (name shown) can see these files. A file it cannot see is not listed: share it with that account, or upload it." The person sees whose eyes jason has.
- **Loading:** a list skeleton, announced ("Loading the folder"). A slow folder keeps what it shows.
- **A folder opened:** a breadcrumb (My Drive, a shared drive, folders); a search box over the whole account (a name search, a POST so a name is never in a URL); a drive switch ("My Drive", each shared drive by name).
- **A row:** name, type word (Doc, PDF, folder), size, modified day, and **jason's own knowledge** where it has it: "already in the library as an amendment", "in a folder a sync rule covers", "pinned for the bylaws". Never a preview of the text.
- **Select:** a file (one, or several when the slot is `SEVERAL` or a series), or **Choose this folder** for a binding. A selected row is checked with text ("selected", not color); the footer says "2 files selected for THE SLOT" and the **Pick** button opens the `Confirm`.
- **Not authorized:** "jason cannot read Drive: it has no sign-in. Run `jason login` ..." with the command, never a field, and the dialog's other tabs still work (paste and upload do not need it for an upload; a paste needs it).
- **Scope missing:** "jason's Drive sign-in lacks the permission to list. It was granted these: (the scopes by name). Run `jason drive --login` again." The scope names are P0.
- **A file jason's token cannot read:** the row is listed if metadata shows, marked "jason cannot open this file", with why in words and the way out (share it with the account; upload).
- **A Google Doc, Sheet, or form:** "A Doc: jason keeps a Word copy; the Doc stays the original."
- **An empty folder, a shared drive jason's account is not in, a search with no match:** each its own sentence, never an empty table.
- **Rate limit or a Google error:** the error in jason's words and "nothing was picked".
- **Google's Picker, if the community turns it on** (a fallback, [../record-intake.md](../record-intake.md#the-recommendation)): the chooser's Drive tab is replaced by Google's own dialog in an iframe; **picker blocked by the browser** (a script, frame, or third-party-cookie block) shows "Google's file chooser could not open in this browser. Use jason's chooser, paste a link, or upload", and the other tabs stay. The picker's result is only a file id, handed to the same pick act. The administrator's switch, the API key, and the project number are settings on the Integrations screen ([handoff-instance-and-integrations.md](handoff-instance-and-integrations.md)), never typed here.

## Data shapes

Made-up keys, files, people, and numbers. A slot's `requires` is a citation and a title only: on the screen the words come from `jason cite` and the shelf, never from a sample.

`GET /api/record-slots` (proposed; `?group=`, `?state=`, `?law=`, `?filter=missing|confidential|waiting`):

```json
{
  "found": true, "asOf": "2099-10-05", "profile": "example",
  "driveConnected": true, "driveAccount": "jason@example.org",
  "counts": {"total": 61, "byState": {"empty": 34, "picked": 6, "classified": 5, "read": 8,
             "confirmed": 3, "notApplicable": 2, "doesNotExist": 1, "waiting": 2, "problem": 0},
             "held": 4},
  "groups": [
    {"key": "records-5200", "title": "Association records", "law": "CIV 5200",
     "opensGate": "ingest", "counts": {"total": 15, "held": 6, "answered": 2},
     "slots": [
       {"key": "records/5200/minutes", "title": "Meeting minutes", "requires": ["CIV 5200"],
        "cardinality": "series", "state": "read", "held": 5, "cells": 8,
        "periods": [{"period": "2098", "state": "confirmed"}, {"period": "2099", "state": "read"}, {"period": "2097", "state": "empty"}],
        "confidential": false, "route": "#/onboarding/records/records%2F5200%2Fminutes"}
     ]}
  ],
  "biggestUnknowns": [
    {"key": "governing/declaration", "why": "the establish gate waits on it", "blocks": ["governing/amendments"]}
  ],
  "caveats": ["A slot's state is jason's reading of records. A person's answer is theirs. Missing is not none: the association may hold it outside jason."]
}
```

`GET /api/record-slot?key=records/5200/minutes` (proposed):

```json
{
  "found": true, "key": "records/5200/minutes", "title": "Meeting minutes",
  "requires": [{"citation": "CIV 5200", "recital": {"found": true, "text": "(the words, recited from the shelf)",
                "inForce": "current words; exported 2099-10-04", "caveat": "jason's copy of the publication, not an official restatement."}}],
  "cardinality": "series", "kinds": ["minutes"], "shelf": "meeting", "confidential": false,
  "state": "read", "existence": {"possible": true, "answer": null},
  "holders": [
    {"pin": "p-3a9f", "source": "data", "kind": "drive", "name": "Minutes 2099-06.pdf", "period": "2099",
     "by": "Jane Example", "at": "2099-10-03", "level": "P1",
     "reading": {"state": "agrees", "kind": "minutes", "tier": "likely", "readers": ["rules", "phrase"],
                 "preflight": {"pages": 6, "blank": 0, "reread": 0}, "segments": null,
                 "found": ["6 pages", "motions: 4", "adjourned 7:42 pm"],
                 "standing": {"word": "draft", "evidence": "no approval found"},
                 "duties": 1, "programs": []}}
  ],
  "collisions": [],
  "bindings": [{"folder": "Minutes", "files": 31, "read": 12, "here": 9, "elsewhere": 2, "nowhere": 1}],
  "candidates": [{"ref": "library:4101", "name": "minutes-example.pdf", "why": "classified as minutes; not pinned"}],
  "acts": {"pickFile": true, "pickFolder": true, "upload": true, "answer": true, "replace": true, "unpin": true,
           "why": ""},
  "log": [{"at": "2099-10-03", "by": "Jane Example", "act": "pick", "pin": "p-3a9f"}],
  "commands": {"slot": "jason records --slot records/5200/minutes", "pick": "jason records --pick records/5200/minutes --file ID --by NAME"}
}
```

`GET /api/drive/list?parent=ID&drive=&q=` (proposed; the search `q` goes in a POST body, not the URL, so `POST /api/drive/search`):

```json
{"found": true, "account": "jason@example.org", "parent": {"name": "Records", "id": "1AbC…", "path": ["My Drive", "Records"]},
 "items": [
   {"id": "1XyZ…", "name": "Bylaws 2099.pdf", "type": "pdf", "size": 412345, "modified": "2099-09-30",
    "jason": {"inLibrary": "bylaws", "ruleCovers": true, "pinnedFor": ["governing/bylaws"]}},
   {"id": "1Qrs…", "name": "Amendments", "type": "folder", "children": null}],
 "next": null, "scopes": ["drive.readonly"], "caveats": ["jason lists what its own Drive account sees."]}
```

`POST /api/write/records/<key>` (proposed; behind the write guard, `X-Jason-Token`; the slot key is in the path, a file id in the body):

```json
{"act": "pick", "file": "1XyZ…", "by": "Jane Example", "period": "2099", "note": ""}
```

`act` is `pick`, `bind` (`folder`), `upload` (`name`, `base64`), `replace`, `unpin` (`pin`), `keep` (a wrong-slot override, with `reason`), `repin` (to another slot, `to`), `answer` (`value`: `not_applicable`, `none`, or `waiting`, with `note`, and for waiting `who`), `more` (`yes` or `no`, for a `SEVERAL` slot), `split` (`parts`: each part's slot, confirmed), or `current` (`pin`, for a collision). The answer is the record written: `{written: "spec/example/records.json", pin: "p-3a9f", reading: "queued", proposal: null | "onboarding/proposals/records-…patch"}`. A write with no `by` is 400 ("A pick names who made it."); a name that is not on the roster is 403; a file jason's token cannot read is 422 with the reason and **nothing written**; a note that `secret_reason` flags is refused and cleared.

`GET /api/drive/resolve?ref=` is a POST in practice (a link is not put in a URL): `{ref: "https://drive.google.com/file/d/…/view"}` answers `{found, kind: "file"|"folder", name, type, size, modified, ownerDomain, readable, why}`.

## What the design must keep

- **A pick is a person's signed act and nothing else moves.** It writes a pin. It never changes sharing, never writes to the file, never copies it out of Drive; an ingest of a picked file is a second act the person presses. A pin's `by` is the signed-in person ([security-and-privacy.md](security-and-privacy.md)).
- **Missing is an answer.** `empty` is "nobody has spoken for this". "None exists" and "not applicable" are different, each signed, each with words (where they looked; why it does not apply). Neither is ever filled by jason, and neither hides the slot.
- **A wrong-slot pick is surfaced.** The kind jason reads is compared with what the slot expects, and a difference is the first thing on the slot, with the three acts. A pick that jason cannot classify says so and stays unclassified (principle 8: a miss stays a miss).
- **Recite first; label the reading** (principle 2). The slot's `requires` is a `Recitation` before any reading; "jason read it as" follows with `ReadingLabel` and `TierWord` (rules / model / agree), never a bare percent. A reading by one model is a suggestion held for a person.
- **Nothing is worked out on the client.** The loader returns every state, count, what blocks what, the collisions, and what the person's office may do; the page renders them. The picker returns an id; the server resolves the rest.
- **One writer.** A key-document slot's pick is a key-documents link; the same function writes it from the CLI, the key-documents screen, and this one. A profile's code pins are shown, never edited; a change to them is a patch for a person's `git apply`.
- **The checklist is jason's reading; the board decides what is done.** A slot never marks a checklist item done and no control passes a gate.
- **No secret and no browser token.** No Google or Keeper credential is typed, shown, or stored by the console. Where Google's Picker is switched on, its browser token lives in memory for the dialog and is never written, logged, or put in a URL; the exception to "no credential in the browser" is named on the Integrations screen, in words, and is an administrator's decision.
- **Privacy by level** (principle 6):

  | What | Level | Shown |
  | --- | --- | --- |
  | a slot's title, state, law, count | P0 to P1 | the board; the checklist is never in the owner view |
  | a pinned file's name, kind, and reading | the file's own level (`access.PATH_RULES`, the library's flag) | a P3 file's name and reading **by kind only outside the private view** ("a confidential file: kind legal"); the row says "opens in the private view" |
  | the answer "does not exist" or "not applicable" and its note | P1; P3 where the slot is a restricted kind | roster people; a restricted slot by group only outside the private view |
  | the pin store | P3 (`data/spec`) | never served as a file |
  | a Drive file's id | P2 | in a POST, in the log's masked form; never in a URL, a page title, or a link text |
  | an upload's bytes | the file's level | through `/api/file` under the level rules, as any file under `data/` |

  Opening a held slot's file asks for the private view with a reason, as every restricted screen does ([handoff-held-setup-roster.md](handoff-held-setup-roster.md): `PrivateGate`).
- **The board-only route.** `#/onboarding?tab=records` and every `#/onboarding/records/<key>` are absent from the owner view; the loaders refuse `view=owner` (403). A URL carries a slot's key, never a file name or id ([security-and-privacy.md](security-and-privacy.md#urls)).
- **Nothing is mailed or sent.** "Waiting on someone else" records who and when; the request list writes the letter; a person sends it.
- **No color-only meaning.** Every state is a word, every count has a table twin, and a selected row says "selected".

## Where it goes

- **Overview → Onboarding → Records** (proposed): `#/onboarding?tab=records`; one slot `#/onboarding/records/<key>` (the key is URL-encoded, a path with slashes). Filters in the query: `?group=`, `?state=`, `?filter=missing|confidential|waiting`.
- **The Setup tab** (`ChecklistItem`): a document item shows its slots' count and links to the Records tab filtered to its group.
- **`#/records`** (the 5200 records page): each record's row gains "pick or answer" linking to its slot; the page's own holdings stay the 5200 inventory.
- **`#/digest`** under "Waiting on a person": "5 slots wait on someone else; 2 picks read as another kind" linking to the Records tab; the second also appears in the confirmations queue.
- **`#/confirmations`**: the "record reading" kind (below).
- **Programs** (`#/programs`): a program's missing adopted document links to its slot.
- **Information architecture:** one tab, one detail route, no nav entry of its own.

**Loaders and writes to add** (all proposed; a loader wraps a function that exists except where marked "to write"):

| Name | Function behind it | Reads | Writes |
| --- | --- | --- | --- |
| `record-slots` | `jason.tasks.record_slots:slots` (to write) over the `Community` interface (`records`, `developer_file`, `book_entries`, `known documents`), `key_documents.expected_entries`, `onboarding.ITEMS`, `documents.PROFILE`, and the programs catalog; states from the pins, the library's `documents` rows, the readings, and the answers | disk only | — |
| `record-slot` | the same, for one key; `law_readings.recite` for `requires`; `document_models`, `kind_analysis`, preflight and segment stores for the reading; `document_duties` for duties; `jason.web.access` for the level and `acts` | disk only | — |
| `drive-list`, `drive-search`, `drive-resolve` | `GoogleDrive.list_folder`, `list_files`, `get_file` through the server token (all exist; read-only); the library and sync rules for "what jason knows" | Drive (read), the catalog on disk | — |
| write `records` (pick, bind, answer, replace, unpin, keep, repin, more, current) | `jason.tasks.record_slots:write` (to write): appends to `data/spec/<profile>/records.json` whole under the store lock `record-slots-<profile>` after a backup; for a key-document slot, `key_documents.link` | — | jason's own stores only |
| write `records/upload` | the key-documents upload function, extended to `data/record-intake/<profile>/files/…` | — | jason's own store |
| write `records/read` | queues the pipeline for a pinned file as a job: `jason ingest` steps, preflight, segmentation, the kind's reader; a model step only when a person asked | — | the library's stores, the reading records, the job queue |
| write `records/split` | applies a confirmed split: pins each part to its slot | — | jason's own stores |
| the confirmations queue's `record reading` kind | the classification, the split, and the wrong-slot override a person confirms, through [handoff-confirmations-queue.md](handoff-confirmations-queue.md)'s write | — | its confirmation record |
| `jason records` (CLI) | the same functions | — | — |

`jason-mcp` gets **read** tools (`record_slots`, `record_slot`) over the same loaders; **no pick tool**: a pick is a person's act at the console or the terminal ([approval-workflow.md](approval-workflow.md#10-cli-and-mcp-parity)).

## Accessibility

As [components.md](components.md#accessibility), with these particulars.

- **The checklist is a real table** (`DataTable`) under each group's heading, with a caption ("Association records: 15 slots, by state") and columns slot, state, held, law, and next step, each as text; the group row is a disclosure with its count in the summary. A series slot's periods are a nested list, not a grid.
- **`SlotWord`** carries its word as text; the glyph is `aria-hidden`; the tone only repeats it.
- **`DriveChooser` is a modal dialog** (`aria-modal`, labelled by its title); focus moves to its heading and returns to the "Choose from Drive" button on close; Escape closes it and says "Nothing was picked". The sources are a tab list (arrow keys, Home and End). The file list is a **list of options in a listbox with `aria-multiselectable`** where several may be picked, or a radio group for one; each row's text is the name, type, size, and day, then jason's note. A folder opens on Enter and says "Opened Records, 12 items" in a polite region; the breadcrumb is a `nav` with `aria-current`.
- **Loading and errors** are in `role="status"` and `role="alert"` regions; a failed step of the reading names itself.
- **Pasting** has a visible label and an error that names the field; a resolved file's name is read out ("Found: Bylaws 2099.pdf, a PDF, 400 kilobytes").
- **Every act is a `Confirm`** (two clicks, the record spelled out): "Pin Bylaws 2099.pdf to the bylaws, as Jane Example. This records a pick; it moves, copies, and shares nothing." After the act, the result is in `role="status"` and focus stays on the slot.
- **A wrong-slot notice is `role="alert"`**; its three acts are a radio group with a `Confirm`; the reading's words are a `ReadingLabel` aside after the file's facts.
- **The upload field** is a labelled file input; a drag target is an addition and never the only way; no step needs a drag.
- **Targets** are at least 24 by 24 CSS pixels; shortcuts as [patterns.md](content/patterns.md#keyboard-use); nothing times out, and a half-written note stays in the field until the page closes.
- **Reduced motion:** the chooser's progress and the reading's steps do not animate.

### The phone layout (under 720 px)

- The checklist's rows are **cards**: the title first, the state as a word on the first line, the held count, then the law. Groups collapse; the filters become a disclosure with the active count in its summary.
- `SlotPage` stacks: the law's `Recitation`, then the wrong-slot notice if any (first, when there is one), the holders, `PickReading`, `ExistenceAnswer`, `SlotActs` at the foot.
- **`DriveChooser` becomes a full-screen sheet** with a sticky footer holding the count and **Pick**; the breadcrumb collapses to "Back to Records"; rows are 44 px; sources are the tab row (`ScrollRow`).
- `SplitProposal` lists its parts as cards one under another with the page range in text, never a side-by-side.
- Paste is the first tab on a phone (the person is likely to have a link in a message); upload uses the device's file chooser.
- "Go to" replaces the nav as `ConsoleShell` does.

## The journey, day 1 to day 30

As in [../record-intake.md](../record-intake.md#what-a-person-needs-from-day-1-to-day-30); the screens it walks: **day 1** the Records tab, first run (counts, the biggest unknowns); **days 1-3** a group's `FolderBinding`, the candidates, `SlotRow` by `SlotRow`; **week 1** `UploadStep`, `SplitProposal`, `ExistenceAnswer` "waiting on someone else"; **week 2** the amendments through `KeyDocuments`' rows and the second person on the Setup tab; **week 3** the programs' slots; **day 30** "Every slot is held or answered" and the gates, read by jason, open or say what they wait on. The manager's journey ([journeys.md](journeys.md)) gains "take a new association's records in": the Records tab is its first stop; the board's is "see what we do not have, and the law that says we should".

## Decisions for the design

Settled by the axioms in this pass, and why:

- **One writer for recorded instruments.** A key-document slot's pick is a key-documents link: two stores for one fact is how the two drift.
- **A wrong-slot pick is never silently accepted or silently moved.** "A miss stays a miss", "jason proposes; a person confirms".
- **Missing is two answers and a silence.** "None on record is not none given" (key-documents.md).
- **The primary chooser is jason's own, over the server token; Google's Picker is a switched-on fallback.** The console holds no credential and loads no Google script; the reasons and the unverified points (loopback origins; whether a pick extends across OAuth clients) are in [../record-intake.md](../record-intake.md#choosing-the-files-the-picker-verdict).
- **A local upload stays in jason's store.** Copying it to Drive is a second, separate, signed act.
- **A code pin and a data pin are shown together when they differ,** and neither wins silently; the profile changes only by a patch a person applies.

Still open (a person's or the design's):

1. **Google's Picker at all.** Whether the console may load Google's script and hold a browser token for the dialog (an administrator's switch, with the exception named), or jason's chooser is the only way. A person decides.
2. **Whose eyes.** jason's chooser lists what jason's one Drive account sees. Whether it should read as the signed-in person (a per-person token) is a larger change; until then, "share it with the account" is the instruction.
3. **A folder binding's reach.** Whether a bound folder's files are only candidates (the design) or may be read automatically on each sync with a proposed rule; the design proposes the rule and a person applies it.
4. **Hiding a slot a statute names.** Whether the profile may hide one with a reason (the design shows it as "hidden by the profile"), or a person's "not applicable" is the only way.
5. **The series' span.** From which period a `SERIES` slot expects cells (the association's formation, the law's retention, or a person's start). The design asks the person once per series.
6. **The slot list's size.** About 60 rows at first; whether the Records tab opens grouped by gate (what blocks what) or by law, and how "biggest unknowns first" sorts a series.
7. **Two checklists.** The Setup tab's items and the Records tab's slots overlap by design; decide whether a document item's status line on Setup is the slots' summary or only a link.
8. **A pick for a confidential kind.** Whether jason should read it at all before the private view is opened (a reading is P3), or only on the person's say; the design reads on a person's act and shows the result in the private view only.
9. **The upload cap and Drive hand-off.** The cap's size, and whether "Also copy to Drive" is offered on every upload or only where a folder is bound.
10. **Counsel.** A slot for a document counsel holds (a letter) is "waiting on someone else"; whether counsel's own copy may be a pick (the console has no access for counsel).

## Not part of this pass

- Building any of it: no code, no loader, no store, no CLI.
- Google's Picker's page and its settings on the Integrations screen: a switch named here and designed with the integrations handoff.
- Making a file public, moving a file, or filing into PayHOA: `jason publish-document` and the sync plan stay as they are.
- Applying a proposed sync rule or a profile patch: a person's `git apply`.
- Counsel acting in the console, or the owner view of any slot.
- A unit's documents (the unit record), and the owner's records request.
- The previews: the design project's authored preview for each component follows the build; fixtures will be from the sample data above.
