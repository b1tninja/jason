# Photos from shared albums

Board members share Google Photos albums in agendas (`photos.app.goo.gl` links). Each album is in the member's own
account. `jason photos` takes the photos in, keeps them with their agenda labels, and can hold them in an album jason
created and in a Drive folder.

## The two APIs since March 31, 2025

| API | Can | Cannot |
| --- | --- | --- |
| **Picker** (`photospicker.googleapis.com`, scope `photospicker.mediaitems.readonly`) | Open a session whose link a person opens to pick photos (a whole album at once); list and download what was picked within 60 minutes (`=d` keeps the photo's Exif, `=dv` for a video) | Open an album by its link; list a library; keep location metadata (Google strips it) |
| **Library** (`photoslibrary.googleapis.com`, app-created data only) | Create albums, upload, add items to jason's albums with a description (50 per call), list jason's own albums and items | Read anything jason did not create; share an album; add to a person's album |

## Workflow

1. `jason photos --login --interactive` once, to consent to the Photos scopes.
2. `jason photos --pick URL` with the agenda's link. jason looks up the album's agenda labels and likely incident
   (`jason meetings --links`; a link no agenda names is saved as `unlabeled`), prints the Picker link, and waits
   (`--timeout`, default 1800 seconds, and never past the session's own limit). The person opens the link, finds the
   album, selects its photos, and presses Done. The files land in `data/photos/<slug>/` with `manifest.json`: the
   share URL, labels, incidents, and each file's id, name, time, type, MD5, and SHA-256. Picking again adds only new files.
3. `jason photos --publish SLUG [--yes]` keeps the photos in an album jason created, named by `ALBUM_NAME` in
   `mystique/photos.py` (`Mystique {date} {item}`, then the likely incident's address and claim numbers), each photo
   captioned with its agenda labels. Sharing that album is done by a person in the Google Photos app.
4. `jason photos --to-drive SLUG --drive-folder ID [--yes]` copies the photos into a folder named like the album.
   `PHOTOS_DRIVE_FOLDER` is empty until the board picks a folder.
5. `jason photos --status` lists each imported album, how many items are in jason's album, and how many are in Drive.

Without `--yes`, `--publish` and `--to-drive` only say what they would do.

## Records

These photos document association business (repairs, incidents, claims) and are association records. Until they are
copied to the association's Drive, they are held in a board member's personal Google account; the manifest's digests
tie each copy back to what was picked.
