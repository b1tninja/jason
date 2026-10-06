# Handoff: the directory and who agreed to be in it

For the design pass on the console's side of directory publication consent: which contact details of the board, officers, committee members, the manager, and vendors may appear in a document for which reader; who agreed, and since when; taking an agreement back; and what a generated document says it printed. The model, the legal readings, the record, and the phases are in [../directory-consent.md](../directory-consent.md); this page is the screens, the components, their states, the data, and the words. Behavior and words are settled by this page, [README.md](README.md) (principles 1 to 9), [components.md](components.md), [content/style.md](content/style.md), [content/patterns.md](content/patterns.md), [security-and-privacy.md](security-and-privacy.md), and [approval-workflow.md](approval-workflow.md).

**What exists today.**
- The directory block, with a publish flag on each contact field, `(not published)` and `(vacant)` lines, and an `audience` of `board` or `owners` ([../document-templates.md](../document-templates.md#5-the-directory-and-privacy), `jason document-template`).
- The people and offices screen, read only ([screens/people.md](screens/people.md)): each office, its holder, vacancy provision, terms, and the board-roster question that records a change of office.
- Roles, data levels (P2 masking is still proposed), the private view, and the reveal log ([security-and-privacy.md](security-and-privacy.md)).
- No record of who agreed, no audience beyond two, no revocation, and no screen.

**Its neighbours: linked by name, not repeated.**

| Neighbour | What it shares | What changes there |
| --- | --- | --- |
| [screens/people.md](screens/people.md) and [handoff-held-setup-roster.md](handoff-held-setup-roster.md) (`OfficeCard`, `TermRow`, `PendingAnswer`) | the seats, holders, terms, and the board-roster answer | a new **Directory** tab on `#/people`. `OfficeCard` gains one line, "Directory: 3 of 6 fields published, 2 audiences" linking the tab. Nothing there is edited; the roster stays the roster |
| the Documents studio (`handoff-documents-studio.md`, written in parallel; named here, not linked) | a document's definition, its blocks, and its part map | the studio embeds `AudiencePreview` for a directory block, and its stale list gains a "directory" cause. This page defines both; the studio owns where they sit |
| [handoff-confirmations-queue.md](handoff-confirmations-queue.md) | a person's signed act, `Confirm`, board decisions read from `data/board/decisions.json` | no new kind in that queue. A consent task is a roster task on the Directory tab and a line under "Waiting on a person" in `#/digest`; whether it joins `ConfirmationsQueue` is decision 6 |
| [handoff-record-intake.md](handoff-record-intake.md) | a kept file as evidence, `Doc`, P3 files | a consent's evidence (a kept email, a signed form) is a `Doc` in the library, picked the way a slot's file is |
| [handoff-followups.md](handoff-followups.md) | what to do next and who is outstanding | an unanswered consent request is a follow-up row, not a new list |

## The idea in one line

A detail reaches a reader only when **a record says that reader may have it**: the person's own, or the board's for the association's own contacts, each with a start day, and ended by the person's word, the seat, or a day they chose. The console shows who agreed to what for whom, takes a person's yes and no as signed records, lists the documents a withdrawn yes touched, and never prints, sends, or recalls a document.

## The components

All new except where a built one is named.

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `DirectoryRegister` | the Directory tab of People (`#/people/directory`) | `GET /api/directory` | no directory topic at all (the command that makes it, and the roster question); loading; listed by seat in the board's order; filtered by audience; a seat vacant (the provision, recited, as `OfficeCard` does); a seat held with nothing published; every field published to some audience; consents waiting (a request out); stale documents (a count linking `ReissueList`); one loader failed (the other parts listed, the failed part's note and command in its place) |
| `ConsentCounts` (a `Stat` strip) | above the register; a line in `#/digest` | `counts` | by state (in force, not yet, ended, none); by audience; requests out; documents stale for the directory; its table twin |
| `PublishMatrix` | one entry's page (`#/people/directory/<entryId>`) | `GET /api/directory/entry?id=` | a grid, fields down and audiences across, each cell a `ConsentWord`; loading; unknown id; a field the entry has no value for (the cell says "no value held": a board-only fact, never shown in an audience's preview); a role-address row (basis: the board); a cell the signed-in person may act on (a button with a name on it) and one they may not (the reason in words, no hidden button); read-only in the owner view (it has none: this screen is never in the owner view) |
| `ConsentWord` (a `Pill` preset) | each cell, the register, the history | `state` | **in force** (since a day, until a day or "until you end it"); **not yet** (from a future day); **ended** (revoked, expired, seat changed, each with its word); **none** (never given); **requested** (a request is out; no answer). Always a word; the color only repeats it |
| `ConsentRequestCard` | the entry's page, above the matrix when a request is out; the person's own view of it | `request` | drafted (the words the person will be shown, from the base template, with the purpose, the reader, the field, and the period); out (sent by whom, when; a person sends it: nothing here emails); answered (yes for some cells, no for others); overdue (the day it was due, in words); the person's own form: one checkbox a cell and a "No, not these" per row, each a word |
| `PurposeWords` | inside `ConsentRequestCard`, the `Confirm` of a give | `purpose` | the sentence the person is shown, whole, never abridged; the reader, the field, the period, and "You may say no, or change your mind at any time" as fixed words; a purpose missing (the give is off, with the reason) |
| `ConsentHistory` | the entry's page, under the matrix | `history[]` | an entry's lines in order, each: the day, the act, the field, the audience, who gave it, who recorded it, how, the evidence (`Doc`, P3), the line it ends; empty ("No consent has been recorded for this entry"); a line recorded for another person (marked, with its evidence); never an edit or delete control |
| `RevokeConfirm` (a `Confirm` preset) | a cell in force; the history | `revoke` | a cell in force (button: "End this agreement as Jane Example"); the preview of what ending it does, from the loader: documents not yet sent that become stale, documents sent that go on the reissue list, pages published; ended (the result, in place); refused (not the person, no evidence) |
| `ReissueList` | the Directory tab's band, and a document's page in the studio | `GET /api/directory/stale` | none stale ("No generated document carries a withdrawn detail."); not yet sent (regenerate: the command); sent or published (a person decides: reissue, update the page, or leave it, each recorded with a name and a day); decided; loading; a part map missing (the document predates part maps: "this document's directory fields were not recorded") |
| `AudiencePreview` | the entry's page ("What each reader sees"); the studio's directory block | `GET /api/directory/preview?audience=&on=` | one reader at a time; the directory exactly as the block would print it, with `(not published)` and `(vacant)`; values masked by the server by level and never sent unmasked; a day control (`AsOfControl`) for a future or past day; the audience chosen (`Tabs`); empty (every seat not published: the designated recipient line only) |
| `SeatConsentTask` | the Directory tab; `#/digest` | `tasks[]` | a new holder recorded (the election's result, applied), no request yet; request drafted; out; answered; a holder who left (their consents ended on a day; the list of documents) |
| `DirectoryPolicyNote` | the Directory tab's header | `policy` | none adopted ("No written directory policy. jason applies the design's defaults and the board has not adopted them."); adopted (the board item and meeting, read from the decision on record); a policy proposed and on the agenda |

Built components used as they are: `Recitation` (the statute, from disk), `ReadingLabel` (a reading, labeled and whose), `Confirm`, `Doc`, `Pill`, `DataTable`, `Stat`, `Caveats`, `Command`, `Findings`, `Card`, `Tabs`, `RemoteView`, `HeldNote`, `AsOfControl`, `RoutingTag`, `PrivateSwitch`, `MaskedField` (still proposed in [components.md](components.md#still-proposed); this page is its first user, and the matrix is where it is first needed). **Collision check against [components.md](components.md):** none of the names above is in the table or in the proposed list, and `ConsentWord` and `RevokeConfirm` are presets of `Pill` and `Confirm`, as `KeepBlank` is. `MaskedField` is not redefined.

### The words

| Word | Meaning | Where from |
| --- | --- | --- |
| in force | a record says this reader may have this detail today | `Published` |
| not yet | a record starts on a day not yet reached | `from` after the day |
| ended | revoked, expired, or the seat changed | a later `revoke`, `until`, the roster |
| none | no record: a miss | no line |
| requested | a request is out and unanswered | the request record |
| not published | what a document prints for every state but in force, the same word whatever the cause | the block |
| vacant | no one holds the seat on the record of the roster | `Community.officers()` and the terms |
| stale for the directory | a generated document printed a detail whose agreement has ended | the part map and `Published` |

"Consent" appears only as a person's act: "agreed by Jane Example", never "approved". The board's role mailbox is "published by decision of the board on Oct 7, 2099", never "consented". No control says "approve", and no cell says "declined" or "pending" in a document: those words belong to the console only.

## Data shapes

Made-up entries, people, days, and ids. A value is never in a list: the register carries `hasValue` and the field names; a value comes from `/api/directory/value` one field at a time, masked, and logged.

`GET /api/directory` (proposed; `?audience=owners`, `?state=none`):

```json
{
  "found": true, "asOf": "2099-10-05",
  "counts": {"entries": 7, "inForce": 12, "notYet": 1, "ended": 2, "none": 22, "requested": 3, "staleDocuments": 1},
  "policy": {"adopted": false, "boardItem": null, "decision": null},
  "entries": [
    {"id": "dir-0001", "kind": "officer", "role": "President", "holder": "Jane Example", "state": "held",
     "term": {"start": "2099-01-15", "endNote": "serves at the pleasure of the board"},
     "fields": [
       {"field": "name", "hasValue": true, "audiences": {"board": "in force", "owners": "in force", "site": "none", "notice": "in force", "vendor": "none"}},
       {"field": "email", "hasValue": true, "audiences": {"board": "in force", "owners": "none", "site": "none", "notice": "none", "vendor": "none"}},
       {"field": "group", "hasValue": true, "basis": "board", "audiences": {"board": "in force", "owners": "in force", "site": "in force", "notice": "in force", "vendor": "none"}}
     ],
     "request": null, "route": "#/people/directory/dir-0001"},
    {"id": "dir-0005", "kind": "officer", "role": "Secretary", "holder": null, "state": "vacant",
     "vacancy": {"source": "Bylaws 1.2", "words": "(the provision's words, recited from the stored document)"},
     "fields": [], "request": null, "route": "#/people/directory/dir-0005"},
    {"id": "dir-0007", "kind": "vendor", "role": "Landscape contractor", "holder": "Example Landscaping Inc.", "state": "held",
     "fields": [{"field": "portal", "hasValue": true, "audiences": {"owners": "none", "vendor": "in force"}}],
     "request": {"state": "out", "sentBy": "Pat Placeholder", "sentOn": "2099-09-28", "due": "2099-10-12"}, "route": "#/people/directory/dir-0007"}
  ],
  "designated": {"present": true, "source": "board decision of 2099-01-15", "note": "Printed wherever a directory is printed; not a consent field."},
  "unavailable": [],
  "caveats": ["A detail prints only where a record says its reader may have it.", "Civil Code 4035 and 5310(a)(1): the designated recipient is the board's designation; whether it may be an office in place of a named person is for counsel."]
}
```

`GET /api/directory/entry?id=dir-0001` (proposed): the entry, its matrix, its history, any request, and the commands.

```json
{
  "found": true, "id": "dir-0001", "kind": "officer", "role": "President", "holder": "Jane Example",
  "signedInIs": true, "canGive": {"name": true, "email": true, "phone": true, "address": true, "hours": true, "group": false, "portal": false},
  "why": {"group": "A role address is the board's to publish: a decision on record."},
  "optOut": {"kept": false, "note": ""},
  "matrix": {
    "email": {"audiences": {"board": {"state": "in force", "since": "2099-02-01", "until": null, "consent": "cns-0003"},
                            "owners": {"state": "none"}, "site": {"state": "none"}, "notice": {"state": "none"}, "vendor": {"state": "none"}}}
  },
  "history": [
    {"id": "cns-0003", "act": "give", "field": "email", "audience": "board", "from": "2099-02-01", "until": null,
     "basis": "person", "how": "console", "givenBy": "Jane Example", "recordedBy": "Jane Example", "recordedAt": "2099-02-01T10:12:00",
     "evidence": null, "purpose": "(the sentence the person was shown)", "revokes": null}
  ],
  "request": null,
  "commands": {"history": "jason directory --history dir-0001", "preview": "jason directory --published owners --on 2099-10-05"}
}
```

`GET /api/directory/preview?audience=owners&on=2099-10-05` (proposed): what the block prints, values masked by level.

```json
{
  "found": true, "audience": "owners", "on": "2099-10-05",
  "rows": [
    {"role": "President", "name": "Jane Example", "cells": {"email": "j•••@example.org", "phone": "not published"}, "state": "held"},
    {"role": "Secretary", "name": "(vacant)", "cells": {}, "state": "vacant"},
    {"role": "Treasurer", "name": "(not published)", "cells": {"group": "j•••@example.org", "email": "not published"}, "state": "held"}
  ],
  "designated": {"line": "(the designation, as the board recorded it)"},
  "caveats": ["Masked here as every P2 value is; the document prints the whole value for the reader it is for."]
}
```

`GET /api/directory/stale` (proposed): documents whose part map names a consent that has ended.

```json
{
  "found": true,
  "documents": [
    {"key": "owners-manual", "generated": "2099-09-20", "state": "sent", "channel": "owners",
     "fields": [{"entry": "dir-0003", "field": "phone", "audience": "owners", "consent": "cns-0009", "endedOn": "2099-10-02", "why": "revoked"}],
     "decision": null, "commands": {"regenerate": "jason document-template owners-manual --render", "decide": "jason directory --reissue-note owners-manual --by NAME"}},
    {"key": "contact-page", "generated": "2099-09-20", "state": "draft", "fields": [], "decision": null}
  ],
  "unrecorded": [{"key": "welcome-letter", "note": "generated before part maps recorded directory fields"}],
  "caveats": ["A sent or published document is a person's decision to reissue, update, or leave. jason never recalls or edits one."]
}
```

`POST /api/write/directory/consent` (proposed; behind the write guard, `X-Jason-Token`):

```json
{"entry": "dir-0001", "field": "email", "audiences": ["owners", "notice"], "from": "2099-10-06", "until": null,
 "how": "console", "by": "Jane Example", "evidence": null, "purposeShown": "(the sentence, echoed)"}
```

For a person's own field `by` is the signed-in person and `entry`'s holder: a mismatch is refused (403) unless `evidence` names a kept email or form ("A consent for another person is recorded only with their word kept: pick the email or form."). A role address needs `decision`, an id on record whose outcome is approved, read from `data/board/decisions.json` and never typed. A `purposeShown` that is not the base words for this reader, field, and period is refused (409): "The words changed since you opened this." The answer is the lines written: `{written: "directory/consents.jsonl", lines: [{"id": "cns-0010", ...}, {"id": "cns-0011", ...}], stale: []}`.

`POST /api/write/directory/revoke`: `{"consent": "cns-0010", "from": "2099-10-06", "by": "Jane Example", "reason": ""}`. The answer carries what it touched: `{written, ends: "cns-0010", effects: {"notYetSent": ["contact-page"], "sent": ["owners-manual"], "pages": []}}`. A revocation takes effect for the next document at once; the console shows `effects` and does nothing to a sent one.

`POST /api/write/directory/request` and `POST /api/write/directory/reissue-note`: a request recorded as drafted or sent (a person sends it; jason emails nothing), and a person's decision for one sent document (`{"document": "owners-manual", "decision": "reissue" | "leave" | "update-page", "by": "...", "note": ""}`).

## What the design must keep

- **A person consents, or the board decides** (principles 4 and 5). A role address is published by a decision on record, read from the decision, never typed. A person's own field is the person's yes. Nobody's yes is inferred from a seat, a silence, or an earlier directory.
- **Recite, then label** (principle 2). The statutes sit in `Recitation` as `jason cite` gives them, with the caveat; a reading ("the designated recipient is the board's designation") is a `ReadingLabel` with whose; where two readings remain ("whether an office may stand in for a named person") it says so and the board asks counsel.
- **A miss stays a miss** (principle 8). A detail with no record prints "not published", the same word whether a value exists or not; a seat with no one is "vacant" and says so with its provision; the two are never swapped. The console may show a roster person that a value exists (`hasValue`); a document and an `AudiencePreview` never do.
- **Nothing is worked out on the client.** The state of each cell, the effects of a revocation, the stale list, and the preview come from loaders. The page renders what it is given.
- **Nothing is written without a person**, and every write is a `Confirm` in a named person's name, through the write guard, with its CLI equivalent named (below). A write with no `by` is 400; while someone is signed in, `by` is that person.
- **No value in a list, a log, a URL, a part map, or a screenshot.** A URL carries an entry id, never a name ([security-and-privacy.md](security-and-privacy.md#urls)). The audit log carries ids and field names. A value is shown one field at a time, masked, and a reveal is logged.
- **Revocation is not deletion.** Ending an agreement is a new line; history is never rewritten. The console has no edit or delete control on a record.
- **The console never recalls, edits, sends, or posts.** It lists what a withdrawn yes touched; a person decides, and records the decision.
- **The board's own directory shape is the board's.** A person's consent never adds a seat or a field to a document; the studio's definition does.
- **Privacy by level** (principle 6):

  | What | Level | Shown |
  | --- | --- | --- |
  | a role label, a seat's vacancy and its provision | P0 to P1 | roster people |
  | a holder's name, a consent's state, its history, the counts | P1 | roster people |
  | an email, a phone, a mailing address, hours | P2 | masked by the server; one field revealed at a time, logged by kind; never in a list |
  | a kept email or signed form as evidence | P3 (legal and private) | the private view only, logged |
  | an opt-out record kept as a member | P3 (the membership list as a book) | the private view only; the console says only that one exists |

  The screen is board-only, never in the owner view, and nothing here is P4.
- **No color-only meaning.** Every cell is a `ConsentWord`; the matrix has a table twin; a stale document carries the word.

## Where it goes

- **Records → People and offices**: a **Directory** tab on `#/people`. Routes: `#/people/directory` (`?audience=owners|board|site|notice|vendor`, `?state=none|in-force|ended|requested`), and `#/people/directory/<entryId>`. The tab is in the row after the offices; its count of requests out and documents stale shows in the tab label.
- **`#/people`** (`OfficeCard`): one line linking the tab ([screens/people.md](screens/people.md)).
- **Documents studio** (named, not linked): `AudiencePreview` inside a directory block's panel; a "directory" cause on a stale document.
- **`#/digest`**: under "Waiting on a person", `ConsentCounts` as one line ("2 requests out, 1 document sent with a withdrawn detail"), linking the tab.
- **Onboarding** ([screens/onboarding.md](screens/onboarding.md)): a checklist item "directory consent" beside the roster, "4 of 7 seats answered", its status jason's reading and never set by a click.
- **The owner view**: none. The owner sees the document, not the record.

**CLI** (the names are free: `jason directory` is not an existing command; `jason contacts` is vendors' PayHOA contacts and is unchanged):

| Act | Command (proposed) |
| --- | --- |
| list entries and what is published | `jason directory --list [--audience A]` |
| one entry's lines in order | `jason directory --history ENTRY` |
| what an audience sees on a day | `jason directory --published AUDIENCE --on DAY` |
| agree | `jason directory --give ENTRY --field F --audience A [--audience B] --from DAY [--until DAY] --by NAME --yes` |
| the board publishes a role address | `jason directory --give ENTRY --field group --audience A --decision ID --by NAME --yes` |
| end an agreement | `jason directory --revoke CONSENT --by NAME --yes` |
| documents a withdrawn detail touches | `jason directory --stale` |
| decide a sent document | `jason directory --reissue-note DOC --decision reissue\|leave\|update-page --by NAME --yes` |
| record a request as sent | `jason directory --request ENTRY --by NAME --yes` |

**Loaders and writes to add** (named, not built; a loader wraps a function that exists, except where marked "to write"):

| Name | Function behind it | Reads | Writes |
| --- | --- | --- | --- |
| `directory` | `jason.web.extra.directory:directory` (to write) over `Community.officers()`, `Community.terms()`, `private.facts("directory")`, and `directory_consent.state` (to write) | disk only | — |
| `directory-entry` | the same, for one id; `Community.vacancy_provision`; the signed-in person and the private view (`jason.web.access`) for `canGive` | disk only | — |
| `directory-preview` | `document_templates.DirectoryBlock` through `directory_consent.published`, masked by the server by level | disk only | — |
| `directory-stale` | `directory_consent.stale` (to write) over the part maps written beside generated documents and the delivery ledger | disk only | — |
| `directory-requests` | the request records under `data/directory/` (to write) | disk only | — |
| write `directory/consent` | `jason.web.extra.directory:write_consent` (to write): appends `data/directory/consents.jsonl` under the store lock; refuses a `by` that is not the entry's holder without evidence, a role address without an approved decision, a purpose that is not the base words | — | jason's own stores only |
| write `directory/revoke` | `write_revoke` (to write): appends a `revoke` line; answers `effects` | — | the same |
| write `directory/request` | `write_request` (to write): records a request drafted or sent; sends nothing | — | the same |
| write `directory/reissue-note` | `write_reissue_note` (to write): records a person's decision for a sent document | — | the same |

jason-mcp gets no write: an assistant may read `directory`, `directory-entry`, and `directory-stale` through `jason.api` as every read tool does, with values masked; a consent is a person's act at the console or the terminal.

## Accessibility

As [components.md](components.md#accessibility), with these particulars.

- **`PublishMatrix` is a real table** (`DataTable`): a caption ("Who may see which detail of the President's entry"), row headers for fields, column headers for audiences, and each cell's `ConsentWord` as text. Cell actions are buttons with their own accessible name ("End agreement: email, owners"). No grid roles, no drag.
- **A request's form** is a `<fieldset>` for each field with a legend and a radio pair per audience ("Print it" and "Do not print it"), none checked at first, a visible label on each; an error names the cell: "Choose for the owners' documents whether your email may be printed."
- **`PurposeWords` is plain text**, read before the controls, with the period and the right to say no in the same paragraph, not behind a link.
- **`RevokeConfirm` is a `Confirm`** (two clicks, the effect spelled out): "End this agreement: records that Jane Example ended the printing of her email in documents sent to owners from Oct 6, 2099. Documents made from now on will not carry it. 1 document already sent carries it and is listed for a person to decide." The result is in `role="status"`, in place; focus stays on the cell.
- **`ReissueList`** is a table with a caption; "sent" and "draft" are words; each decision is a radio group with the document's name in its legend.
- **`AudiencePreview`** announces its audience and day when they change, in a polite live region ("Showing what owners see on Oct 5, 2099"); a masked value reads as its mask, never spelled out.
- **A stale count** carries the word beside the number, and the tab label includes it in text.
- **Nothing times out.** A request half answered stays in the form until the person leaves the page; the store holds nothing until `Confirm`.

### The phone layout (under 720 px)

- The register's rows become cards: the role and its state first ("President: held"), then the holder, then "3 of 6 details published" as words, then any request out. The audience filter collapses into a disclosure with its active choice in the summary.
- The matrix **stacks by audience**, not a horizontal scroll: a heading for each audience (Owners, Notices, Site, Vendors, Board), and under it the fields, each a row with its `ConsentWord` and its one action. Every row says its audience in text.
- The request form stacks one field at a time with its purpose above it; "Print it" and "Do not print it" are large radio rows. A person answering on a phone can answer every cell without leaving the page.
- `AudiencePreview` shows one audience at a time under a `Tabs` row that scrolls and says it does; a long address wraps inside the page.
- `ReissueList` is one card a document: its name, "sent" or "draft" in words, what it carries, then the three decisions stacked.
- "Go to" replaces the nav as `ConsoleShell` does.

## Decisions for the design

Settled by the axioms in this pass, and why:

- **No approve control anywhere.** A board decision (a role address, a policy) is a vote at a meeting on the Decisions tab; the console reads it. A person's agreement is a signed record, not an approval.
- **One record a cell, never "all".** A person who agrees for owners and notices writes two lines. A shortcut in the form writes both; the history shows both. Publishing for one reader publishes for no other.
- **Revocation is immediate for the next document and silent about the last.** It never recalls, edits, or deletes. It lists.
- **The value is never in a list.** `hasValue` tells a roster person that a detail is held; a document never tells a reader.

Still open (the board's or counsel's are in [../directory-consent.md](../directory-consent.md#8-decisions-for-the-board-and-the-design); these are the design's):

1. **Where the person answers.** The person signs in to the console and answers on their own entry, or answers a form (`ConsentRequestCard`'s own form) linked from an email without signing in, or both. A form outside sign-in needs its own identity check: decide whether the first release is console-only.
2. **How a request is sent.** The request is drafted here and a person sends it (an email from the person's own account; nothing is emailed by jason). Decide whether a draft reaches Gmail as a draft or is copied.
3. **The matrix's shortcuts.** "Same for owners and notices" is a convenience: decide whether it is one checkbox per row, or a preset the person picks.
4. **A vendor's consent.** A vendor's yes is an email kept as evidence. Decide whether a vendor contact is a roster-recorded line only, or the vendor also has a one-field form.
5. **An entry's `hasValue`.** Decide whether a roster person who is not an officer sees which details exist, or only which are published.
6. **The queue.** A consent task joins `ConfirmationsQueue` as a fourth kind, or stays on the Directory tab and `#/digest`.
7. **The stale list's reach.** It reads part maps and the delivery ledger. Decide how a document generated before part maps recorded fields is listed ("unrecorded") and whether a person may mark it checked.
8. **The tab's place.** A tab of People, or its own screen under Governance with a link from People.
9. **Counts in the nav.** Whether requests out and stale documents are counted in the tab label and the digest line, or only in the digest.
10. **A policy note.** Whether `DirectoryPolicyNote` also carries the purpose words so the board adopts them together with the directory, or only links the policy item.

## Not part of this pass

- Any send, post, recall, edit, or deletion of a document, a page, a PayHOA field, a Google Group, or a Gmail message: a person acts there, and the console says which places are "not controlled by this record".
- The board's vote on a directory policy or a role address: `#/room`, `#/decisions`, and the board loop.
- The legal reading of whether a statute reaches an association, or requires a named person (counsel; [../directory-consent.md](../directory-consent.md#2-what-the-law-says-recited-and-what-is-a-reading)).
- Changing an office, a term, or a vacancy: the roster's board-roster question.
- The member's own opt-out record and the membership list as a book.
- The Documents studio's screens and the owner's manual's screens: each owns where `AudiencePreview` and the stale cause sit.
- The owner view and the public site's own editor: the site page is a document with audience `site`.
- A confirm tool in `jason-mcp`: it stays read-only.
- The previews: the design project's authored preview for each component follows the build, as for the earlier handoffs; fixtures will be `ui/src/components/publishmatrix.test.tsx` and its siblings, from the sample data above.
