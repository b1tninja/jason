# Key documents

The checklist of the documents an association must be able to put its hands on: the declaration, each amendment, each annexation, the articles and bylaws, the rules, each condominium plan, the maps, each common-area deed, the notices of completion, the public reports, and the building plans. Each entry carries its recording number, its status, the copies jason sees, the copies people linked, and the locator's leads. A person links a copy, uploads one, unlinks one, or records a status; each write names its person.

Code: `jason.community.key_documents` (the list, the expansion, the status rule, the store), `jason.tasks.key_documents` (reading the profile and the stores, and the writes), `jason.web.extra.key_documents` (the console's source and write), `jason.commands.key_documents` (the CLI). The console component is `KeyDocuments` ([components](console/components.md)).

## The list is data

`KEY_DOCUMENTS` holds one row per kind of key document. A row is named by its onboarding checklist item where one exists (`jason.community.onboarding`), and says what fills it:

| Row | Fills it | Repeats |
|---|---|---|
| `declaration` | `DocumentKind.DECLARATION`; the governing roles declaration and restated declaration | no; a rescinded declaration is an entry of its own |
| `amendments` | `AMENDMENT`; amendment, restatement or amendment, covenant modification | one per instrument |
| `annexations` | `ANNEXATION`; annexation | one per instrument, and one per phase the public reports annexed with no instrument on the list |
| `articles`, `bylaws`, `operating-rules`, `election-rules` | their kinds | no |
| `condominium-plans` | `CONDOMINIUM_PLAN`; condominium plan, plan amendment | one per instrument |
| `maps` | `MAP`; subdivision map, parcel map | one per instrument |
| `common-area-deeds` | `GRANT_DEED` delivered as a common-area deed; common area deed, easement | one per instrument |
| `notices-of-completion` | notice of completion | one per instrument |
| `public-reports`, `building-plans` | `DRE_REPORT`, `PLAN_SET` | no |
| `other-recorded` | covenants, cancellations, covenant agreements, and any governing role no other row names | one per instrument |

A new kind of key document is a new row, not a branch in a task. A person may add their own entry as `other/<name>`, titled with its first link.

## Where each entry comes from

`expected_entries` reads, in this order, and never searches:

1. **The specification's declaration** (`Community.ccrs`) and its amendments: firm numbers, the sections each amendment changes, and an amendment with no number noted as not recorded (CIV 4270(a)(3)).
2. **The association's record in the index cache** (`load_association_record`): each governing record by its role, its phase, and what replaced it. A developer's filing tied to no phase is listed with a note that it may be another community's.
3. **The specification's supersessions**: the earlier instrument marked rescinded, with the reason.
4. **The public reports**: a phase they annexed with no annexation in force on the list is an expected entry.
5. **The locator's leads**: `data/onboarding/<profile>-documents-located.json` (the locator's own shape, `Location.to_dict`) and the leads the onboarding lookup saved in the private facts. A lead on a number already listed rides on that entry; a new number on a repeating row is a new entry; the association's own liens are never key documents.
6. **The copies**: each Drive pin, placed by the number its title prints, by the specification's document it is (same Drive file, or same title with or without its extension), or by the phase its title names; a pin no rule places goes to the row's `files` entry. Each recorded copy on disk whose stamp or file name carries a number on the list (the governing extracts, the PayHOA library copies, the site docs).

## Status

| Status | When |
|---|---|
| `linked` | a person linked a copy here (an active link) |
| a person's word | `missing`, `held` (on paper, say where), `located`, or `expected`, recorded with `by` and a note |
| `held` | jason sees a copy: a Drive pin, or a recorded copy on disk |
| `located` | a recording number is known (specification, index, or a locator lead), and no copy is held |
| `expected` | on the list, nothing on record yet |

`missing` is only ever a person's word, and it needs a note saying what was looked for and where: none on record is not none given. A located number is a lead, not a pin: the recorded copy is read before it is pinned in the specification.

## The store

`data/key-documents/<profile>.json`, written whole (a temporary file, then a replace) under the store lock `key-documents-<profile>` (`jason.locks`):

```json
{"version": 1, "profile": "example", "entries": {
  "amendments/202001170712": {
    "links": [{"id": "l-1a2b3c4d", "kind": "upload", "ref": "key-documents/example/files/<sha16>/First Amendment.pdf",
               "name": "First Amendment.pdf", "sha256": "...", "size": 123456, "by": "Jane Example",
               "at": "2026-10-03T18:00:00+00:00", "note": "", "unlinked": null}],
    "status": {"value": "held", "by": "Jane Example", "at": "...", "note": "the binder in the office"},
    "log": [{"at": "...", "by": "Jane Example", "action": "link", "link": "l-1a2b3c4d", "note": ""}]
  }}}
```

- **Link** a copy: a file under `data/` (its path and sha256 are kept), a Drive file (an id, or any Drive or Docs link; the name comes from the Drive catalog on disk when it holds the id), or a PayHOA library document (its number; the name and the local copy come from the catalog on disk). The same copy linked again is one link.
- **Upload**: a file a person chose is copied to `data/key-documents/<profile>/files/<first 16 of its sha256>/<its original name>` and linked. The same file twice is one copy; a different file with the same name lands in another folder; nothing is ever overwritten. Documents and scans only (`.pdf`, images, `.tif`, `.txt`, `.md`, `.doc`, `.docx`), at most 25 MB (`MAX_UPLOAD_BYTES`); a larger file goes on Drive and is linked there.
- **Unlink** marks the link removed with who and when. The file is never deleted.
- **Status** records a person's word, as above. `linked` comes only from a link.

Every write needs `by`, refuses "jason", and checks the key: a row's key, `<row>/<number or name>`, or `other/<name>`.

## Commands

```bash
jason key-documents                                    # the checklist
jason key-documents --json                             # the rows the console shows
jason key-documents --markdown > key-documents.md      # a page
jason key-documents --link amendments/202001170712 --drive https://drive.google.com/file/d/ID/view --by "Jane Example"
jason key-documents --link bylaws --file "governing/Bylaws.pdf" --by "Jane Example"     # a file under data/
jason key-documents --link maps --payhoa 1076784 --by "Jane Example"
jason key-documents --upload declaration --file "C:/Users/me/Downloads/CC&Rs recorded.pdf" --by "Jane Example"
jason key-documents --unlink bylaws --link-id l-1a2b3c4d --by "Jane Example" --note "the draft, not the recorded copy"
jason key-documents --status maps --set missing --note "asked the prior manager and the city" --by "Jane Example"
```

## The console

`GET /api/key-documents` is the checklist. `POST /api/write/key-documents/<key>` takes one action, behind the write guard (Host, Origin, token) and, when sign-in is on, in the signed-in person's name:

| Body | Does |
|---|---|
| `{"action": "link", "kind": "file" \| "drive" \| "payhoa", "ref": "...", "by": "..."}` | links an existing copy |
| `{"action": "upload", "name": "Map.pdf", "base64": "...", "by": "..."}` | the browser's file, at most 25 MB decoded |
| `{"action": "upload-ref", "path": "C:/...", "by": "..."}` | a file the server can read, under the same limit and suffixes |
| `{"action": "unlink", "link": "l-...", "by": "..."}` | marks the link removed |
| `{"action": "status", "value": "missing", "note": "...", "by": "..."}` | a person's word |

The base64 body was chosen over a multipart upload so the write goes through the same JSON route, guard, and sign-in hook as every other store write; 25 MB covers a recorded declaration's scan, and anything larger belongs on Drive. A link to a file opens through `/api/file` when its type is one that route serves.

`KeyDocuments` (`ui/src/components/KeyDocuments.tsx`) takes `data` (the payload), `by` (the signed-in name; without it the component asks for a name), `onChanged` (reload after a write), and `post` (for tests). Each write is a `Confirm` that names the copy, the entry, and the person; a refusal is an alert that says nothing was written.

## Caveats

- A located recording number is a lead, not a pin.
- None on record is not none given.
- Held means jason sees a copy; whether it is the complete recorded copy is for a person to read.
- Unlinking removes the link, never the file.
