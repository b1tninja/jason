# Choosing from a person's own Google Drive: the Picker, redirect form

**Status: built behind a switch (server and console), not yet tried against real Google.** It builds recommendation 3 of [google-picker-research.md](google-picker-research.md) (the redirect form of the Picker). Every Google behavior below was built from Google's documentation and tested against fakes; [what could not be verified](#what-could-not-be-verified) is listed, and [the manual test](google-workspace-setup.md#choosing-from-a-persons-own-drive-the-pickers-redirect-form) in the setup page is how a person finds out. General for any association; every example is made up.

## What it does

A signed-in board member presses **Choose from my Google Drive**. The console navigates to `GET /auth/google/pick`. jason sends the person to Google's authorization endpoint with `trigger_onepick=true` and the one scope `https://www.googleapis.com/auth/drive.file`. Google shows its Picker, in the person's own account (their private files and the shared drives they belong to). Google returns the person to `GET /auth/google/pick/callback` with `picked_file_ids` and a `code`. The **server** trades the code with the community's Web client and its secret (the same client the console's sign-in uses), reads each picked file **once, read-only**, keeps a **held copy**, drops the token, and sends the page back to where it was with `?pick=<opaque result token>`.

What it never does: write to Drive (no copy, move, rename or sharing change); ask for a refresh token (`access_type=online`); store, log, or put in the session, a URL or the page the code, the token or the client secret; log a file name or a Drive id (the HTTP client's request lines, which hold ids, are dropped while a pick is read); pin a Drive file the server cannot see again.

## Routes

| Route | Who | What |
|---|---|---|
| `GET /auth/google/pick?next=#/route&slot=records/5200/minutes&purpose=split` | signed in, an office that opens P2 (the board's level), not viewing as someone else; `pick.enabled` on | Starts a pick. `next` is a console route (`#/...`) as for sign-in; `slot` an optional slot key; `purpose` is `split` (default) or `slot`. 302 to Google. Refusals are a small page (401 not signed in, 403 no office or switch off or viewing as another, 400 bad purpose, 409 no Web client) |
| `GET /auth/google/pick/callback?state=&picked_file_ids=&code=` | the same person | Validates the state, trades the code, reads the files, saves the result, 302 to `/?pick=<token>` + `next`. A refused state is a small page (400); everything after the state is checked comes back as a result with `error` |
| `GET /api/drive-held` | a signed-in office that opens P2 | The held copies for the start page: number, size, pages, day; no name, no Drive id; a confidential copy masked |
| `POST /api/drive/pick/result` `{"token"}` | the same person, behind the write guard | The result, **read once** (removed as read, and for the person who picked): `{purpose, slot, error, report: {dryRun, counts: {held, "already held", "would hold", refused}, rows: [{outcome, reason, words, heldId, size, pages, name}]}}`. 404 when there is none, it was read, it expired, or it is another person's |

The parameters sent to Google, exactly: `client_id`, `redirect_uri` (`<console origin>/auth/google/pick/callback`), `response_type=code`, `scope=https://www.googleapis.com/auth/drive.file`, `access_type=online`, `prompt=consent`, `trigger_onepick=true`, `state`, `allow_multiple=true`, `mimetypes=application/pdf`. No `login_hint`, `hd`, folder selection, or PKCE (Google's Picker page mentions neither `state` nor PKCE; `state` is used, PKCE is left out so an unsupported parameter cannot fail the pick).

### State

The state is random (24 bytes), kept in the session and, **hashed**, in `<data>/drive-picks/states/` with the person, purpose, slot, `next` and an end time (`pick.state_minutes`, default 10). The callback needs the session's value to match the one Google returned, and then **claims** the disk record by an atomic rename, so it works once even if a session cookie is copied. A forged, repeated, expired, or another person's state is refused with nothing exchanged and nothing read.

### Result rows and their words

| `outcome` | `reason` | Said |
|---|---|---|
| `held` / `already held` | | "Read once and held. The original in Drive was not changed." / "Already held; nothing new was kept." (the same bytes are one copy) |
| `would hold` | | a dry run only (the task's `dry_run=True`): metadata read, nothing kept |
| `refused` | `folder` | a folder picked does not give its files: choose the PDFs |
| | `not_pdf` | not a PDF (a Google Doc is exported to PDF in Google first), or a PDF that is not one |
| | `too_large` | the `fetch.max_bytes` words |
| | `too_many_pages` | the `split.max_pages` words |
| | `not_readable` | downloading is off for the file, or the PDF is password-protected or damaged |
| | `no_access` | the account cannot open it (Google's text is never shown) |
| | `no_room` | the drive has no room (`storage.require_room`) |
| | `bad_id`, `duplicate` | not a Drive id; picked twice |

Every refusal ends "Nothing was kept." Before a file is kept: metadata first, then the size against `fetch.max_bytes`, then room, then the bytes (checked again against the cap), then the page count against `split.max_pages`.

## Where things are kept

`<data>/drive-picks/held/<sha256>.pdf` and `<sha256>.json` (size, pages, `picks`: `by`, `at`, `via: "picked via Picker"`, `driveIdHash` (16 hex of a SHA-256), Drive's `modified`; and `confidential`). No file name, no Drive id. `states/` and `results/` are short-lived and swept when the next is made. One line a real run in `records/history.jsonl`: `act: drive-pick`, `by`, `purpose`, counts and the held ids' first 12 characters. `python -m jason.tasks.drive_pick --purge` lists the held copies, and `--purge --yes` removes them.

## The UI (built)

The console's side is built to the contract below; the files are `ui/src/lib/pick.ts` (the start address, the one-time read of the return), `ui/src/views/PickStart.tsx` (the button), `ui/src/views/PickPanels.tsx` (the result list, a held copy opened as a draft or pinned to a slot, and the held copies), and their styles in `records.css`. Two small server pieces came with it: `GET /api/drive-held` and `heldId` on the records upload ([below](#the-two-server-pieces-the-ui-needed)). Tests: `ui/src/views/pick.test.tsx` (every state), `e2e/tests/pick.spec.ts` (the whole flow through the real routes, Google stood in for by `e2e/pick_fake.py`), and the axe scans in `e2e/tests/a11y.spec.ts` ("choosing from my own Google Drive").

1. **The button.** "Choose from my Google Drive", with the sentence that says what happens beside it ("Google will ask which files to share with jason. jason reads each file once and keeps a copy; it writes nothing to Drive and does not keep your Google sign-in.", tied to the button with `aria-describedby`). It is on the splitter's *From Drive* tab and in the records `DriveChooser` (its *Drive* tab, for the splitter's pick and for a slot). It shows only when `GET /api/session` carries `pick.enabled` true. Otherwise the same place says, calmly, "Picking from your own Drive is off for this community. Your community's administrator can turn it on in Setup, Limits (the row named `pick.enabled`)." with a link to Setup, Limits. A session with no `pick` block is treated as off.
2. **The leave.** The button navigates (`window.location.assign`) to `pick.start` with `next` set to the current hash route, `purpose` (`split` from the splitter, `slot` from a record slot) and, for a slot, `slot` (the slot key). No file id, name or token goes out.
3. **The return.** The address comes back as `/?pick=<token>#/route`. The first screen that asks (`usePickReturn`) takes the token out of the address at once (`history.replaceState`) and reads the result once with the shared write helper (`POST /api/drive/pick/result`, with the write token). A result is shared by every later mount of the screen, so React's second effect, or coming back to the screen, never reads it twice; closing the list forgets it. A result for the other purpose is ignored on this screen. The shared helper throws on a body that has an `error`, and a pick that ended in an error (Google refused, nothing picked) answers 200 with `error` set; the UI takes that body as the result, not as a failure.
4. **The rows.** An accessible list ("Files you picked") under a heading that takes the focus; one polite status line says how it went ("2 files kept." or "2 of 6 files kept. 4 files refused; each says why."). Each row: "File N: NAME", a badge (Kept, Already kept, or "Refused: a folder / not a pdf / too large / too many pages / no access / cannot be read / no room"; a glyph and words, never colour alone), the server's words as given, and for a kept row its pages and size. A refused row has no button. An error with no files ("Nothing was kept") shows the server's words whole. Other states: a 404 is "That pick is over" ("That pick was already read, or it has expired. Choose again."); a 401 asks for a sign-in and says files already read are held; any other failure is said with its message. A return that is not the one that was sent is refused by the server with a small page of its own and never reaches the console.
5. **A held row opens.** In the splitter: **Check the file** (the usual dry run, `{kind: "held", id}`, in the server's words) then **Open it for splitting**, which goes to the draft's route. For a record slot: **Pin file N** opens the usual preview-and-confirm panel (period for a series, recording number for a repeating key document, a note), which posts the slot's `upload` with `heldId`: the server hands the held copy to the upload, the browser never holds the file, and it is **not** pinned as a Drive file.
6. **Several rows.** Each kept row has its own button; the list stays until it is closed.
7. **Held copies.** The splitter's start page lists "Picked from Drive": the copies jason holds, newest first, as "Copy N", pages, size and the day picked (no name, no Drive id), each with **Check the file** and **Open it for splitting**. A confidential copy is a row that says so, with its size, pages and address held back, and no button, until the private view is open. Nothing is drawn when there are none.

### The two server pieces the UI needed

- `GET /api/drive-held` (`jason.web.extra.drive_held`, `drive_pick.listing`): the board's (P2) loader, read-only, disk only. `{found, total, copies: [{n, id, size, pages, day, confidential, held}], note}`, newest pick first, at most 20. `id` is the copy's address, used only to open it; the page never shows it. A confidential copy's `id`, `size` and `pages` are withheld unless the private view is open. Its gate is classified in `tests/fixtures/loader_gates.json`; tests are `tests/test_drive_held.py`.
- `{"act": "upload", "heldId": "<sha256>", "name": ...}` on `POST /api/write/records/<slot key>` (`jason.web.extra.record_slots._held_copy`): in place of `base64`, the server reads the held copy and gives its bytes to `record_upload.upload`, so every check, the limit, the preview, the history line and the read-back are the upload's own. Both `heldId` and `base64` is refused; an unknown or purged address is refused in words; a name without `.pdf` gets it. This is the "slot hand-off" the first version of this page listed as open decision 3; it is built as a field of the upload rather than a `kind: "held"` source for `record_upload`.

### The test launcher's stand-in for Google

`e2e/serve_e2e.py` installs `e2e/pick_fake.py` on its own app object only. It points `jason.web.pick.AUTH_URL` (in that process) at `/__e2e/google/pick`, which checks the request the way Google's documentation describes it (`trigger_onepick=true`, the one `drive.file` scope, `access_type=online`, `response_type=code`, a `state`, a redirect address ending in the callback) and answers 400 in words when something is missing, then sends the browser back to the real callback with `picked_file_ids` and a code (or `error=access_denied`, or a state that is not the one sent), by a scenario (`/__e2e/pick-scenario?name=ok|mixed|none|denied|badstate&reset=1`). The code exchange is a function that accepts only that code, and Drive is the real `GoogleDrive` client over an `httpx.MockTransport` of made-up files (two PDFs, a folder, a Google Doc, an oversized PDF, and an id nobody shared). The switch is off until a test turns `pick.enabled` on (`/__e2e/limit`). Nothing reaches Google.

### The contract the UI was built to

1. **The button.** "Choose from my Google Drive" on the splitter's *From Drive* tab and in the Records `DriveChooser`. Shown only when `GET /api/session` says it may work; until the session carries a `pick` block (`{enabled, start}`, an addition for the console's build), show it when the Integrations screen's `pick.enabled` is on. A button that is off is absent with its reason ("Choosing from your own Drive is off for this community"), as the handoff already says for a source that is off.
2. **The leave.** The button sets `window.location` to `/auth/google/pick?next=<route>&slot=<key>&purpose=<split|slot>` where `next` is the console's current hash route (`#/split`, `#/records`). A navigation, not a fetch: the Picker opens in the same tab and comes back. Keep nothing but the route and the slot key: **no file id, no name, no token**. A draft the person had open is the splitter's autosave's business; nothing in the URL carries it.
3. **The return.** On load, if the query string has `pick=<token>`, remove it from the address at once (`history.replaceState`) and `POST /api/drive/pick/result` with `{"token"}` (with the write guard's token and Origin, as every write). A 404 means it was read or expired: say "That pick is over; choose again." Never reload the token.
4. **The rows.** Draw `report.rows` in the dialog's list: name, the outcome, the `words` as given (jason's words, not rewritten), the size and pages of a held row. An `error` with no report is shown whole. A refused row shows no button.
5. **A held row opens.** In the splitter: `POST /api/write/split/new` with `{"act": "open", "ref": {"kind": "held", "id": "<heldId>"}, "by": <signed-in name>}`, which makes the usual draft (the same bytes resume the same draft). For a record slot (`purpose=slot`): a held copy is **uploaded** to the slot through the existing upload route (the slot's "uploaded from Drive by NAME on DAY"); it is **never pinned**, because the server's own account cannot see a person's private file, so a pin would break the read-back and the sync. The slot's pin route is not changed by this work, and the slot hand-off of a held id is the one piece the console must still add (see [open decisions](#open-decisions)).
6. **Several rows.** Each row has its own button; choosing one does not discard the others for the session (the result is gone once read, so the dialog keeps the rows in its own state until closed).

## Fallback if the redirect form fails

If the spike shows Google refuses `trigger_onepick` for a Web client, the documented fallback is the web Picker behind an administrator's switch: the page loads Google's scripts, the browser holds a `drive.file` token in memory, fetches the bytes itself and posts them to the existing upload route; the token never reaches the server ([google-picker-research.md](google-picker-research.md), "Analysis 3", phase 4). It is not built. The held-copy store and `kind: "held"` would not be used by it.

## What could not be verified

Nothing here was run against Google. From the documents read (October 11, 2026):

1. **Whether a Web application client may use `trigger_onepick`.** The page ([Desktop and mobile Picker](https://developers.google.com/workspace/drive/picker/guides/desktop-mobile-picker)) is written for desktop and mobile and says "select the recommended application type for your app"; it does not say a Web client is allowed or refused. This is the spike's first question.
2. **The code exchange.** The page links to the web-server guide and gives no request body. The exchange here is the web-server guide's (`grant_type=authorization_code`, `code`, `client_id`, `client_secret`, `redirect_uri`) to `https://oauth2.googleapis.com/token`. It requires the answer's `scope` (when present) to include `drive.file`.
3. **Whether the returned token reads the picked files.** The page says the app "then uses the file IDs and token with the Drive API"; it does not say whether that covers a file in a shared drive (`supportsAllDrives=true` is sent) or a file shared with the person but not owned. Test both.
4. **Whether `state` is returned.** The page lists `picked_file_ids`, `code`, `scope` and `error` and does not mention `state`. If Google drops it, every pick is refused ("did not come back as it was sent") and the flow cannot be used without another binding.
5. **`access_type=online`.** The page's sample uses `offline`; the web-server guide says `online` is the default and returns no refresh token. Whether the Picker accepts `online` was not found. If it refuses, switch to `offline` and discard the refresh token (not built).
6. **`allow_multiple`, `mimetypes`.** Named as optional on the page; their exact value syntax (comma-separated mime types, `true`) was not shown beyond `MIMETYPES`.
7. **A folder picked.** Not requested (`allow_folder_selection` is not sent), and a folder that arrives is refused. Whether a picked folder would yield its children is unknown.
8. **Loopback redirect.** The web-server guide exempts localhost URIs "including localhost IP address URIs" from HTTPS and requires the redirect URI to match a registered one exactly (scheme, case, trailing slash); it does not name `127.0.0.1` or say whether the port is part of the match. Register the exact address the console is opened at.
9. **Verification for the Web client's consent screen.** `drive.file` is documented as non-sensitive; the app is Internal. The re-prompt when a person has granted the Web client only `openid email profile` before was not documented; `prompt=consent` forces the screen.
10. **Whether `include_granted_scopes` defaults.** Not sent. The page for web-server apps describes it as opt-in.
11. **What the browser's Referer carries** to Google. The result token is never sent to Google; the redirect to `next` is on the console's own origin.
12. **A phone browser.** The page says the Picker opens in the default browser's tab; not tried.
13. **Request logging by `httpx` and `httpcore`** at INFO includes the Drive URL (and so the id). The pick drops those two loggers' lines while it reads (tested). Any other handler attached to the HTTP stack (a proxy's access log) is outside jason.

## Open decisions

1. **Retention of held copies.** They stay until purged. Recommend a sweep like the splitter's `split.draft_days`, as a registered limit; not built.
2. **Revoke the grant after the read.** Revoking the access token at `https://oauth2.googleapis.com/revoke` would end the app's `drive.file` grant to those files. Not done: an unverified side effect on the person's other picks, and the token already expires in an hour.
3. **The slot hand-off.** Built as `heldId` on the console's upload (the server hands the copy over; the browser never holds it). A `kind: "held"` source for `record_upload` itself, for the terminal, is not built.
4. **PKCE.** Left out (see above). If Google confirms it for the Picker, add it with `S256` as sign-in does.
5. **Who may pick.** The board's level (P2) and not viewing as another person. A manager with a portfolio is on the roster at that level.
6. **Revisit the switch's default** after the spike: on for a community whose Web client has the redirect address, otherwise off.
