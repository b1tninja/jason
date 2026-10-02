# Drive activity

`jason drive-activity` reads the Google Drive Activity API (v2) to answer who did what to a Drive item and when: created,
edited, moved, renamed, trashed or permanently deleted, restored, or re-shared. It only reads. It never writes to Drive.

The main Google token carries `drive.activity.readonly`. The command uses the Drive client's token.

## Commands

```bash
jason drive-activity --missing                          # agenda-linked Drive items not in the association's listing
jason drive-activity --file FILE_ID [--since 2026-01-01]
jason drive-activity --folder FOLDER_ID --since 2026-01-01
jason drive-activity --missing --json
```

Each run writes `data/drive/activity-<name>.json`: `activity-agenda-missing.json`, `activity-file-<id>.json`, or
`activity-folder-<id>.json`.

## What a record holds

Each activity has its time (the timestamp, or the end of its time range), the primary action, the actors, the targets,
and the action's detail:

- move: the parents added and removed;
- rename: the old and new title;
- permission change: each permission added and removed, its role, and whether it is an "anyone with the link" grant;
- delete: `TRASH` or `PERMANENT_DELETE`.

An actor is a people id (`people/<id>`) with `isCurrentUser`, or an administrator, anonymous viewer, deleted user, or the
system. Names are not looked up; that would need the People API.

## Standing

`--missing` gives each item one standing:

- **not visible to the association account**: Drive will not show it (404 or 403), and the Activity API returns nothing.
  Most likely it is owned by a personal account and was never shared with the association. That is the answer, not an
  error. The Activity API returns an empty page, not an error, for an item the account cannot see, so Drive's own
  metadata settles it.
- **permanently deleted**: a `PERMANENT_DELETE` is on record.
- **in the trash**: Drive marks it trashed, or the last delete was not followed by a restore.
- **visible**: the account can see it; the report still lists moves, renames, and sharing changes.

## Legal holds

`jason.tasks.drive_activity.activity_for(client, ids, since, actions=CUSTODY_ACTIONS)` asks, for a set of held ids,
whether any was deleted, moved, renamed, restored, or re-shared since a date. A legal-hold watch uses it as is.
