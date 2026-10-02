# Drive labels (appProperties)

jason labels the association's Drive files with what its rules found: document kind, Civil Code 5200 records, meeting dates, the latest agenda item, topics, the likely incident, and claim numbers.

## Why appProperties

The Drive Labels API needs a higher Google Workspace plan. On the association's plan it returns 403. Every plan has Drive API v3 `appProperties`, so jason stores its labels there.

## What they are

- They are private to jason's OAuth application. Another app, and the Drive UI, cannot see them.
- Each key and value together is at most 124 bytes of UTF-8. A file can carry at most 30 per application (Google, [Custom file properties](https://developers.google.com/workspace/drive/api/guides/properties)).
- `files.update` merges them. A key missing from the body is kept, and a key set to `null` is removed.
- The API can search them: `appProperties has { key='jason_kind' and value='minutes' }`. The search matches the whole value exactly.

## Schema

The rows are in `mystique/labels.py` (`LabelProperty`, from `jason.community.drive_labels`). Each row gives a key, what it holds, where the value comes from, which command writes it, and how an overlong value is trimmed:

- LIST drops whole items from the end.
- TEXT cuts at a character and adds an ellipsis.
- EXACT is never trimmed. A value too long for its key is not written.

| key | holds | from |
|---|---|---|
| `jason_kind` | document kind | `jason drive` holdings, else the agenda link |
| `jason_records` | 5200 records | holdings |
| `jason_meetings` | meeting dates, newest first | agenda labels and meeting records |
| `jason_item` | latest agenda item / sub-item | agenda labels |
| `jason_topics` | topic names | agenda links |
| `jason_incident` | first date, address or building, causes | the first likely incident |
| `jason_claims` | claim numbers | likely incidents |
| `jason_confidential` | `1` when a rule marks it confidential | holdings, executive sessions |
| `jason_labeled_at` | date jason last changed the labels | the apply run |
| `jason_hold` | reserved for a legal hold | only the legal-hold command |

jason labels only a file that appears in the association's Drive listing (`data/drive/files.json`). Google Photos albums, web pages, and links to files outside the listing are counted and skipped.

## Commands

```bash
jason drive-labels                    # dry run: counts and the exact properties per file, diffed against the cache
jason drive-labels --show FILE_ID [--live]
jason drive-labels --apply --limit 50 --yes
jason drive-labels --search jason_kind=minutes
```

- `--apply` reads each file live before writing. It sends only jason's changed keys.
- It never writes or removes a key it does not own, including `jason_hold`.
- It records what Drive returned in `data/drive/app-properties.json`.

## A label is a lead

A label is what a rule read from a file's name, path, or agenda links. It is a lead, not a classification. A person confirms it from the file.
