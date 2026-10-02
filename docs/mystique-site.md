# The association's public site

The association's public website is a Google Site. Its pages carry the owner portal link, contacts, the governing documents, plans, reports, insurance, financials, and escrow instructions, mostly as embedded public Drive folders and files.

## Public Drive folders

Folder ids, PayHOA folder ids, and the page-to-library map are `LibraryFolder`, `KnownFile`, and `SitePageRef` on the `Mystique` class. Load them with `PayhoaFolder`, `KnownFile`, and `community.site_pages()`. The embedded folders are readable without signing in. A name match between those folders and the PayHOA library is summarized as sync rules in [drive-sync-rules.md](drive-sync-rules.md). Rules are name-match globs, not a full folder copy.

Do not treat a public embed as permission to copy a file into a new place. Several of these folders are association records. Civil Code section 5230 says records may not be sold or used for a commercial purpose.

## Drive API and the site

New Google Sites has no content API. The site is a Drive file (`mimeType` `application/vnd.google-apps.site`), not a folder of page files. The Drive API can fetch that file's metadata, move it between folders, and change its sharing permissions. It cannot change the text, layout, or components on the pages; page edits stay in the Google Sites editor.

`agent.drive()` reuses the stored refresh token. A missing token raises `GoogleAuthRequired` unless you pass `interactive=True`. `drive.readonly` covers listing and download of the embedded folders. Changing an ACL needs a broader Drive scope.

Mystique's findings are in the private notes (mystique/notes/mystique-site.md).
