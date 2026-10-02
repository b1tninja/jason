# Drive to PayHOA sync rules

The association's library lives in two places: Google Drive, where the board works, and the PayHOA library, which members and buyers see. The sync rules say which Drive files belong in which PayHOA folder. They are a plan compared by file name; nothing is uploaded until a person publishes it.

## Where the rules live

The rules are specification rows in [mystique](../mystique/README.md):

- `DriveRoot`: a root folder in the signed-in My Drive whose name already matches a PayHOA folder, and the PayHOA path it maps to. Sync from those root folders and ignore everything else at the root: the loose files beside them are working copies, mail, and duplicates, not the library.
- `SyncRule`: a Drive folder, a name glob, and the PayHOA path a matching file belongs in. A rule may cover a folder of the public site's embedded Drive folders or a signed-in root folder; the signed-in root folder is preferred when both exist.
- `LibraryFolder`: the PayHOA folder ids the paths resolve to.

## How a file is matched

- A file that matches a rule and is missing from PayHOA (compared by name to `data/payhoa-documents.json`) is `needs_publish`. That row is the sync plan.
- A Google Doc is published as `{name}.pdf`, so a Drive Doc named `ALPR Policy` maps to `Governing Documents/Policies/ALPR Policy.pdf`.
- A name that misses every glob stays skipped. The rules are name-match globs, not a folder copy.
- A glob may match more than one PayHOA subfolder (`Grant Deeds/**`); the glob does not decide which.
- PayHOA's `Email Attachments/` is a catch-all. A file that matches both it and a library folder belongs in the library folder, and nothing is synced into it from Drive.

## Excluded folders

Some Drive folders are left out on purpose: large media sets with no PayHOA counterpart (an audio book, a builder's plan set), drafts, application forms, superseded policies (`old/`), and year folders whose contents are mixed. A year folder is never synced as a whole; it stays out of the globs until a person reviews it.

Mystique's findings are in the private notes (mystique/notes/drive-sync-rules.md).
