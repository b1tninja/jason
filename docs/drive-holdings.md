# Where the records are in Drive

`jason drive --sync` lists every file the signed-in account can see in Google Drive (read-only) and saves the list to `data/drive/files.json`. Each file keeps its id, name, folder path, type, size, MD5, modified time, and owner.

A file whose folder the account can't see is labelled by where it sits:

- `My Drive/` for a file in the account's own My Drive root;
- `Shared with me (owner)/` for a file shared from a folder the account can't open;
- `Shared drive/` for a file on a shared drive.

`jason drive` (and the `record_locations` MCP tool) then read the list the way the PayHOA library is read. The result is `data/drive/holdings.json`.

## Path rules

A Drive root in the specification (`DriveRoot` in `mystique/anchors.py`) says which Drive folder matches which PayHOA library folder. A file under a root takes that folder's library path plus its own subpath. So `My Drive/Meetings/2025/Minutes of 7_15_25.pdf` is read as `Meetings/2025/Minutes of 7_15_25.pdf`.

The library's name and path rules (`classify_document`, the `LibraryFolder` records, the bank account suffixes) then give the file's kind, its Civil Code 5200 records, and whether it is confidential. A file under no root has no path rule; its kind comes from its name alone.

`DriveRoot` only places files. Publishing from Drive to PayHOA is a separate set of rules (`SyncRule`, [drive-sync-rules.md](drive-sync-rules.md)).

## Copies by content

Every file on disk the association holds outside Drive gets an MD5:

- the PayHOA library's files;
- the PayHOA payment attachments;
- the email attachments;
- the scanned mail.

The hashes are cached in `data/drive/md5-cache.json`. A Drive file with the same MD5 lists each of those places. A Google Doc, Sheet, or Slide has no MD5 in Drive, so it is matched by name only.

The report lists:

- **each record's holdings**: files in Drive, how many are under a path rule, how many are also in the PayHOA library, and the paths outside any rule;
- **the same content in several Drive folders**;
- **the same name with different content**, which are versions or different documents that share a name;
- **library files not in Drive**;
- **the Drive folders no path rule covers**, with the kinds their file names suggest.

## What it found

This association's findings are in its private notes (mystique/notes/drive-holdings.md).

A duplicate, a version, or a new path rule is for a person to decide. Jason moves, renames, and deletes nothing.
