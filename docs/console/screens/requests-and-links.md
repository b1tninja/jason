# Requests and links: their documents

The documents on four built screens, and the `Embed` component they share, on `Doc` ([doc-component.md](../doc-component.md)) · phase 2

## In the console

- **Drafts** (`#/drafts`, `request-links`): each PayHOA request beside the email about it, and drafts for emailed requests PayHOA does not have.
- **Key documents** (the Onboarding screen's tab, `key-documents`): each key document with the copies jason sees and the copies people linked.
- **Canvases** (`#/canvases`, `canvases`): a person's scratchpad, with clips, links, and attachments.
- **Templates** (`#/templates`, `templates`): the letter templates and a fill form for each.

**What this spec adds:** each document these screens name is a `DocRef` from the loader, shown with `Doc`. No screen holds a link into data/, a Google link it builds itself, or a frame of a private Google file. The guard's allowlist for these screens is empty (`ui/src/components/docrefs.allowlist.json`).

## Data

| Loader | The reference | Built by |
|---|---|---|
| `request-links` (`jason.mcp.county.request_links`) | each row's `doc`: its submission, `payhoa:submission:<id>`, named by the request's title (P2) | `jason.tasks.request_links.with_refs`, on the rows shown |
| `key-documents` (`jason.tasks.key_documents.checklist`) | each copy's and each link's `doc`: a recorded copy on disk as `file:<path>` with source "Recorded copy"; a Drive pin or link as `drive:<id>`, its original "Open in Google"; an upload or a linked file as `file:key-documents/…`; a PayHOA library document by its copy under `payhoa-files/documents/` | `_copy_dict`, `_link_dict` |
| `canvases` (`?key=`) and the canvas writes | each attachment's `doc`: a Drive kind's `drive:<id>` (from the id or a private link), a photo or PDF under data/ as `file:<path>`; each clip's `doc` when its source names a document (an evidence address, `data/<path>`, `library: <path>`, a citation) | `jason.tasks.canvases.with_refs`, `refs_from_strings`' reading |
| `templates` (the listing) | each template's `doc`: its Doc, `drive:<id>` | `jason.approvals.docref.drive_ref` |

The references are built on each read and never stored: an attachment sent back with its `doc` is kept without it. A file reference no longer carries an `/api/file` URL; a Drive link keeps its Google `url` beside its `doc` for other callers.

## Documents and their variants

| Where | Variant | Why |
|---|---|---|
| Drafts, "Requests beside their email", Request column | `chip` (the request's title) | A table cell; opening shows the form the owner filled in, one logged view |
| Key documents, "Copies jason sees" and "Linked by a person" | `chip`, with the reference's original ("Open in Google") beside a Drive copy | A short list inside each entry; a recorded copy is labelled "Recorded copy", a Drive pin "Drive copy (specification pin)" |
| Canvases, a Drive file or a PDF on the canvas | `card` | A grid of attachments |
| Canvases, a photo on the canvas | `inline` | The photo is the attachment's subject; under `photos/` it is P1, so it is viewed on mount, one logged view |
| Canvases, a clip's source | `chip` when it names a document; else its words | A source such as a tool's name or a web address is not a document |
| Templates, the fill form's header | "the template Doc", the reference's `original` | The Doc column keeps its card (`DrivePreview`) |

Plain web links (a canvas's Links card, the Drafts' "Open in Gmail" links) stay links: `gmail:` references are a later step.

## Embed

`Embed` (`ui/src/components/Embed.tsx`) shows a canvas's other attachments, the Calendar screen's and the owner page's calendar, and the meeting view's recording:

| Kind | Shown as |
|---|---|
| `doc`, `sheet`, `slides`, `form`, `drive` (a private file), `chart` by a Sheet id | `Doc` card on `drive:<id>`, with "Open in Google". Never a Google frame |
| `image` under data/ | `Doc` inline on `file:<path>` |
| `pdf` under data/ | `Doc` card on `file:<path>` |
| `image` or `audio` at an https URL | Loads on a click, with no referrer |
| `image` or `audio` as `blob:` or `data:` | Shown at once: nothing outside |
| `audio` under data/ | `Doc` inline on `file:<path>` (kind `audio`): the viewer's player, from a logged view's short-lived link |
| `calendar` | A frame on `calendar.google.com` (`/calendar/embed`) |
| `chart` (published) | A frame on `docs.google.com` (`/spreadsheets/d/e/…/pubchart`) |
| A published Google file (`/d/e/…/pub`, `pubhtml`, `embed`, `viewform`) | A frame on `docs.google.com` |
| `zoom` | A frame on `zoom.us` or a subdomain (`/rec/share/`, `/rec/play/`) |
| `map` | A frame on `maps.google.com` or `www.google.com` (`/maps`) |
| `url`, a `pdf` at a URL, `thread`, and any host off its kind's list | A link card |

Every frame has `sandbox` with its kind's tokens (`EMBED_HOSTS`), `referrerpolicy="no-referrer"`, and a `title`. A frame loads on a person's click ("Load from <host>"). A screen whose subject is a public frame passes `load="mount"`: the Calendar screen and the owner page do, for the association's public calendar. A frame that never loads becomes a link card.

## States

These are `Doc`'s own states ([doc-component.md](../doc-component.md#states)): signed out, not allowed (the server's sentence), not on disk, and an error in the server's words. An `Embed` frame waiting for a click says which host it will ask. An absolute path given as an attachment is refused in words.

## Privacy

- **A request's submission is P2.** Its chip names the request by its title, masked by the server, and shows the submission only on a person's click, signed in and logged.
- **Recorded copies and the key documents' uploads are P0.** An upload the library holds as confidential is P3 (`access.PATH_RULES`).
- **Photos are P1.** A canvas's photo is viewed on mount, as the screen's subject.

## Acceptance criteria

1. Each screen's tests render its variant from a static reference, post one view on opening, and say the signed-out and not-allowed words: `ui/src/views/drafts.test.tsx`, `ui/src/components/keydocuments.test.tsx`, `ui/src/views/canvases.test.tsx`, `ui/src/views/templates.test.tsx`, and `ui/src/components/embed.test.tsx`.
2. No screen renders an `/api/file` href, an iframe of another host's private file, or an absolute path.
3. Each loader's references resolve on a made-up data folder: `tests/test_request_link_refs.py`, `tests/test_key_documents.py`, and `tests/test_web_sources.py`.
