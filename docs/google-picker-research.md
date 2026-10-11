# Choosing files and folders: the Google Picker, the Drive API, and a better library explorer

**Status: research, nothing built.** The question: "we need a better library explorer, or research if we can use the Google Picker / Drive APIs" for choosing files and folders in the records intake, the PDF splitter, the key documents, and document ingestion. This page answers it from Google's current documentation (read October 11, 2026; each claim carries its link, and anything not found in the documents read is marked **unverified**) and from what jason already does. It extends, and where it differs corrects, the picker verdict in [record-intake.md](record-intake.md#choosing-the-files-the-picker-verdict). General for any association: no profile fact is named, and every example is made up.

## The short answer

1. **Two different problems are called "explorer".** Choosing a file **in Drive** (the Picker or the Drive API) and browsing **the library** (what jason already holds: `library.db`, the ingested files, the passage index). Every consumer named above wants both: "pick a file we already have", or "bring one in from Drive". Today only the Drive half exists (`DriveChooser`), and it is the weaker of the two to improve, because the library half needs no Google setup at all.
2. **Google's Picker can be used, but it does not solve jason's central limit.** It lets the **signed-in person's own Google account** choose, so it reaches files jason's one Drive account cannot see. But under `drive.file` the access it grants is to **the app and the person's token**, not to jason's server token. The picked file is readable by the person's token, and by the server only if the bytes are handed over.
3. **The lowest-risk design that reaches the person's own files** is: the browser (or a one-time server exchange) reads the picked file with the person's own `drive.file` token and hands jason the **bytes through the upload route that already exists**, never the token. Nothing is shared, copied inside Drive, or stored.
4. **Recommendation:** (a) build the library explorer now, as a shared "From the library" source, with no Google change; (b) improve the existing server chooser (recent, shared with me, starred, full-text, filters, thumbnails through a proxy); (c) run one day-long spike on the **redirect form of the Picker** (`trigger_onepick`), which may need no script, no API key and no browser token, and fall back to the web Picker only if the spike fails; (d) keep the console free of a Google script until a person decides. The decisions are at the end.

## What the documentation says (verified)

| Point | What Google's page says | Link |
|---|---|---|
| What it is | A "File Open" dialog for Drive; the app gets file metadata (id, name, mime type, url, size, last edited, parent) back; the user must be signed in | [Picker overview](https://developers.google.com/workspace/drive/picker/guides/overview), [reference](https://developers.google.com/workspace/drive/picker/reference/picker) |
| Web setup | Load `https://apis.google.com/js/api.js` (then `gapi.load('picker', ...)`) and `https://accounts.google.com/gsi/client`; an OAuth access token passed with `setOAuthToken` "with views that access private user data"; `setDeveloperKey` (API key); `setAppId` = the Cloud **project number**, "to allow the app to access the user's files"; a **Web application** OAuth client with **authorized JavaScript origins** | [Web guide](https://developers.google.com/workspace/drive/picker/guides/web-picker), [sample](https://developers.google.com/workspace/drive/picker/guides/web-picker-sample) |
| Same project | The client id and the app id "must come from the same project" | [sample](https://developers.google.com/workspace/drive/picker/guides/web-picker-sample) |
| API key | Website restrictions must include the app's origin **and** `https://docs.google.com/*` (the picker renders in an iframe hosted there; without it, "API developer key is invalid"); API restrictions: Picker API (plus Drive API if the app calls Drive); enable both APIs in the project. The sample's restriction example uses `http://localhost/*` | web guide and sample |
| Views and features | `DocsView` has `setIncludeFolders`, `setSelectFolderEnabled`, `setEnableDrives`, `setMode`, `setOwnedByMe`, `setStarred`, `setParent`, `setFileIds`; the builder has `enableFeature` with `MULTISELECT_ENABLED`, `NAV_HIDDEN`, `SUPPORT_DRIVES`, `MINE_ONLY`, `SIMPLE_UPLOAD_ENABLED`; `setSelectableMimeTypes`, `setMaxItems`, `setOrigin`, `setLocale`. A response has `action` (`PICKED`, `CANCEL`, `ERROR`) and `docs` (`id`, `name`, `mimeType`, `url`, `sizeBytes`, `lastEditedUtc`, `parentId`, `serviceId`). Nothing is marked deprecated | [reference](https://developers.google.com/workspace/drive/picker/reference/picker) |
| Shared drives | `DocsView.setEnableDrives` "shows shared drives and the files they contain" and **only** shared drives (not combined with `setOwnedByMe`, which gives no results; it overrides `setParent`/`setFileIds`; `setStarred` is ignored). Direct Drive API calls need `supportsAllDrives=true` | [setEnableDrives](https://developers.google.com/workspace/drive/picker/reference/picker.docsview.setenabledrives), [shared drive support](https://developers.google.com/workspace/drive/api/guides/enable-shareddrives) |
| Scopes | Web apps can use `drive.file` or `drive.readonly`; the web guide says to get the token for its views with `drive.file`, and, for scopes other than `drive` or `drive.readonly`, to use `DocsView.setMode(LIST)` because "the user hasn't granted access to thumbnails" | web guide, overview |
| What `drive.file` is | **Non-sensitive**; access only to files the user opens with, or shares with, the app, "while using the Google Picker API or the app's file picker"; `drive`, `drive.readonly`, `drive.metadata.readonly` are **restricted** (verification for public apps; a security assessment if restricted data is stored on servers). Google's advice: "use non-sensitive scopes as they grant per-file access" | [Choose Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth) |
| Picker does not manage files | It "doesn't allow users to organize, move, or copy files" | web guide |
| Token client | Google Identity Services `initTokenClient` + `requestAccessToken` from a user gesture; the token is short-lived; **no refresh token**; nothing stored by the OS or browser; a closed popup never calls back; more scopes can be requested later (incremental) | [token model](https://developers.google.com/identity/oauth2/web/guides/use-token-model) |
| Redirect form (desktop and mobile) | The authorization endpoint with `trigger_onepick=true`, `prompt=consent`, scope `drive.file` **only**, `response_type=code`; the redirect returns `picked_file_ids` (comma-separated) and a `code` to exchange for a token; the app then calls Drive with the ids and that token. It opens "within a new tab in the user's default browser", and the page says a picker "can no longer be displayed within an embedded webview". Optional `allow_multiple`, `mimetypes`, `file_ids`, `allow_folder_selection`. A separate client id per platform | [Desktop and mobile](https://developers.google.com/workspace/drive/picker/guides/desktop-mobile-picker), [overview](https://developers.google.com/workspace/drive/picker/guides/overview) |
| Web component | `@googleworkspace/drive-picker-element` (and a React wrapper): `<drive-picker client-id app-id ...>` with `<drive-picker-docs-view>`; emits `picker-picked`, `picker-canceled`, `picker-error`; the CDN build loads the Picker and API client libraries itself. The README seen was version 0.5.1 (pre-1.0) | [web component](https://developers.google.com/workspace/drive/picker/guides/web-component) |
| Origins and HTTPS | "OAuth 2.0 clients for web apps must use redirect URIs and JavaScript origins that are compliant with Google's validation rules, including using the HTTPS scheme"; and the web-server page exempts **localhost** from the HTTPS rule for **redirect URIs** | [OAuth policies](https://developers.google.com/identity/protocols/oauth2/policies), [web server flow](https://developers.google.com/identity/protocols/oauth2/web-server) |
| `files.list` | `q` supports `name`, `fullText`, `mimeType`, `modifiedTime`, `viewedByMeTime`, `sharedWithMe`, `starred`, `trashed`, `parents`, `owners` | [search terms](https://developers.google.com/workspace/drive/api/guides/ref-search-terms) |
| File fields | `thumbnailLink` is short-lived ("on the order of hours"), needs a credentialed request, and "isn't meant for direct use in web apps because of CORS" (use a proxy); `md5Checksum` only for binary content; `size`, `modifiedTime`, `lastModifyingUser`, `webViewLink`, `shortcutDetails`, `iconLink` exist; **no page count** and no PDF field | [files resource](https://developers.google.com/workspace/drive/api/reference/rest/v3/files) |

## What was not found (unverified)

- **Whether a pick extends from one OAuth client to another** (a browser token under the Web client, a server token under the Desktop client). Google's pages say the access is the **app's**; none says how "app" is bounded. A community forum thread reports that `drive.file` access follows the client id, which fits; it is not Google's documentation. Treat as: **not across clients**, until a test says otherwise.
- **Self-hosting the Picker's scripts.** Google's guides show only Google-hosted scripts and say nothing for or against self-hosting. The dialog itself is an iframe on `docs.google.com`, so it cannot be self-hosted in any case. No Google page read states a Terms-of-Service ban or a permission.
- **Content Security Policy for the Picker.** Google's identity pages give CSP for the Identity Services library (`script-src https://accounts.google.com/gsi/client`, `frame-src https://accounts.google.com/gsi/`, `connect-src` likewise). The Picker pages give none. A page that loads the Picker will need at least `script-src apis.google.com` and `frame-src docs.google.com`; the full list is to be found by trying with a report-only policy.
- **Quotas for the Picker**: none documented in the pages read. Drive API quotas were not read; a handful of people choosing files is far below any.
- **Mobile browsers for the web Picker.** The documentation's mobile guidance is for native apps. A phone browser opening the web Picker's iframe was not documented; test it.
- **`http://127.0.0.1` or `http://localhost` as an authorized JavaScript origin.** The policy page demands HTTPS for origins and addresses localhost only for redirect URIs (and the API-key restriction example uses `http://localhost`). Whether the token client accepts a loopback origin, and whether it accepts `127.0.0.1` as well as `localhost`, was not found. The console listens on `127.0.0.1`.
- **A folder picked under `drive.file`: whether its children become readable.** Not found. Do not assume it.
- **`drive.file` with shared-drive files.** Not found.
- **Whether a Web application client may use the `trigger_onepick` redirect form.** The page is written for desktop and mobile apps and says a multi-platform app needs a client id per platform. A Web client with a registered redirect address is what jason-web already has; whether Google accepts it here is the spike.
- **An Internal app and restricted scopes.** jason's own design ([integrations-design.md](integrations-design.md#google-workspace), [google-workspace-setup.md](google-workspace-setup.md)) rests on Internal apps needing no verification; the Drive scopes page read here speaks of "public" apps. Consistent, but Google's Internal-app wording was not re-read here.

## How jason holds Google today

- One refresh token per community, for the **community's own account**, from a **Desktop** client, in the community's vault ([google-workspace-setup.md](google-workspace-setup.md)). Its scopes include `drive` (full), granted by the board so a person's move can be filed (`jason.google.scopes`).
- Console sign-in is a separate **Web application** client asking only `openid email profile` (`jason.web.signin`); its **authorized JavaScript origins are left empty** ([setup.md](setup.md)); the console holds no credential and loads no Google script ([console/security-and-privacy.md](console/security-and-privacy.md)).
- The chooser's backend (`jason.tasks.drive_choose`) lists, searches and resolves through that server token, read-only, and says "jason's Drive account sees these". Its open limit is the handoff's decision 2 ([console/handoff-record-intake.md](console/handoff-record-intake.md#decisions-for-the-design)): the chooser shows the **account's** files, not the signed-in person's.
- The rules a design here must keep (record-intake, "What jason must not do"): never change a file's sharing; never write to, move or rename a file as part of a pick; never copy a file out of Drive except at a person's signed act; **never keep a browser token on disk, in a URL, or in a log**; a file's name or id is in a POST body, never a URL. AGENTS.md adds that no secret reaches the page, and that non-interactive runs fail fast rather than open a browser.

## Analysis 1: which account reads a picked file

With the web Picker the person's browser holds a `drive.file` token for the **Web client**. A pick grants that app access to those files. Three facts follow:

- The server's token is the **Desktop client's, for the community account, with `drive`**. It can read any file **that account** can see. It does not need the pick for a file in the community's Drive or a shared drive the account belongs to; the pick only names it.
- For a file in the **person's own private Drive**, the community account cannot see it, and the Desktop token has nothing to do with the pick (different client; per-client access is the unverified-but-likely reading above).
- So a picked private file becomes readable by jason in only one of four ways:

| How | What happens | Verdict |
|---|---|---|
| **Share** | The person shares the file with the community account in Drive | Works today with any chooser; jason must not do it (it changes sharing); the chooser says "share it with the account shown". Leaves a standing grant the person may forget |
| **Copy into the community's Drive** | The person's token copies the file into a community folder | A write to Drive; jason does not copy inside Drive; needs a wider scope. **Rejected** |
| **Server reads with the person's token** | The browser sends its access token to the server once, with the picked id; the server calls `files.get`/`alt=media` and discards the token | Works, but a bearer token crosses into the server's memory and logs; breaks "no credential in the browser or in transit". Acceptable only in the redirect form below, where the **server itself** receives the code and the token never touches the page |
| **Browser reads, hands over bytes** | The browser fetches the file with its token (Drive API supports browser calls) and posts the bytes to the existing upload route (way D). A Google Doc is exported as a Word copy first, as jason already does | **Preferred for the web Picker.** The token stays in browser memory; the server never sees it; the file arrives as an upload at a person's signed act |

Provenance is the same in each case and should be recorded the same way: the Drive file id, `modifiedTime`, `md5Checksum` (binary files) or the export's hash, the picker's `sizeBytes`, the person who picked (`by`), the day. A pick the server cannot re-read later is a **copy** (a held upload keyed by hash), and the slot says "uploaded from Drive by NAME on DAY", not "pinned to a Drive file", because a pin to a private file the server cannot see breaks the read-back, the sync and `jason ingest`.

**Privacy and audit, by design**

| | Server chooser (today) | Web Picker, bytes handed over | Redirect Picker, server exchanges the code |
|---|---|---|---|
| Whose Drive is shown | The community account's | The person's own (and shared drives they belong to) | The person's own |
| Whose account Google's audit log shows reading the file | The community account (every pick looks the same) | The **person** (their token read it) | The person |
| Who sees the person's other files | Nobody new; jason lists only what the account sees | Google's dialog does; jason receives only what was picked | Same |
| Token exposure | None in the browser | In browser memory for the dialog; short-lived; no refresh token | The server holds an access token for one request and drops it |
| Scope granted | Already held (`drive`) | `drive.file` only (non-sensitive) | `drive.file` only |
| jason's own "who picked what" | `by` + slot + file id in the act's history line (no file name) | Same, plus the hash of the bytes | Same |
| What jason must add | Nothing | Script, key, app id, origin, consent for a second token | Redirect route, code exchange, no script |

The Google audit trail is the one real gain: today every read looks like the community account; with a person's own token, Drive's log names the person. jason's own act log already names the person either way.

## Analysis 2: the server-token chooser

**For it:** built; works on loopback and on a hosted console; no key, no script, no origin, no second token; read-only; shows what jason knows of each file (in the library, covered by a sync rule, pinned for a slot), which no Google dialog can; the same listing serves folder binding for sync rules, which the **community account** must be able to list anyway (a sync rule runs as that account, so a folder only the person can see cannot become a rule, whatever picker chose it).

**Against it:** it is jason's dialog to build and keep up (tree, search, list, phone sheet); it shows only the account's Drive; every pick of a private file needs a manual share first; Google's audit log cannot tell the people apart.

**Handoff open decision 2** ("whose eyes"): reading as the signed-in person means a per-person Drive token. This research says a per-person token is **already what the Picker gives, narrowed to the picked files**, so decision 2 need not become a second, wide per-person `drive` consent for every console user. Recommend answering it: "the chooser lists the community's Drive and says so; a person's own files come in through the Picker's narrow grant (or a share, or an upload)."

**Cheap improvements to the chooser with no Google change** (all in the Drive API pages above): a "Recent" lane (`orderBy` modified time, or `viewedByMeTime` for the account); "Shared with me" (`sharedWithMe = true`) and "Starred" lanes; full-text search (`fullText contains`) beside name search; filters on type (`mimeType`), date (`modifiedTime`), owner; sort; and thumbnails through a **server proxy** (`thumbnailLink` needs credentials and is not for direct web use). None adds a scope. A page count is not a Drive field: it comes from fetching and preflighting the file, not from the listing.

## Analysis 3: the hybrid

The proposal: the Picker for a person's own files, the token held in browser memory only, never stored by jason; and either the bytes or the token passed to the server; the server chooser for the community's Drive.

- **Passing the token once per request is not acceptable as the default.** AGENTS.md does not use the words "never store a token", but its boundaries and [console/security-and-privacy.md](console/security-and-privacy.md) put no Google credential in the page or a URL or a log, and record-intake bars a browser token on disk, in a URL or a log. A bearer token in a POST body is exposed to request logging, error reports and any proxy. If a design must send a token, it is the redirect form, where the **server** gets the code from Google directly.
- **Handing over bytes is acceptable.** The token never leaves the page; the server sees an upload, which the key-documents and splitter routes already accept (`upload.max_bytes`, 100 MB by default; a larger file stays in Drive, where a share is the route).
- **The two choosers merge in one dialog** as sources of the existing `FileSourceTabs`: *Community Drive* (the server chooser), *My Drive* (the Picker, if the community enabled it), *The library*, *Paste a link*, *From this computer*. A source that is off is absent with its reason, as the handoff already says.
- **Folders:** the Picker can choose a folder (`setSelectFolderEnabled`, `setIncludeFolders`), but a folder only binds or ingests if the community account can list it. So *My Drive* offers files; folders stay with the community chooser. If a person's folder must be ingested, they share the folder, or choose its files.
- **Ingestion** of a folder (`jason ingest <Drive folder>`) stays a server act on the community Drive. The Picker is not a bulk tool: it returns the ids picked, one dialog at a time (the web sample reads only the first document; multiselect is available but the callback must walk `docs`).

### The redirect form: a spike worth a day

The desktop and mobile guide describes a flow with **no page script, no API key, no app id, no authorized JavaScript origin, and no browser token**: the console navigates to Google's authorization endpoint with `trigger_onepick=true`, `scope=drive.file`, `response_type=code`, and the Web client's registered redirect address (jason-web already has one, with loopback allowed for redirect URIs); the Picker opens in a tab; the redirect returns `picked_file_ids` and a `code`; **jason's server** exchanges the code (it holds the Web client's secret in the vault), reads each picked file once, hands the bytes to the same signed pick act, and drops the token. This keeps every jason rule, needs no change to what the console loads, and gives Drive's audit log the person. What is unknown, and is the spike: does a **Web application** client accept `trigger_onepick`; does a picked folder yield its children; do shared-drive files work; and how it behaves on a phone (the page says the Picker opens in the default browser's tab, so a tab round trip, not a dialog, and the console must survive the navigation: state in the URL's slot key, never a file id).

## Analysis 4: a better library explorer

"The library" is what jason already holds and has read: `data/library/library.db` (`documents`: id, source, path, name, kind, category, records, method, period, confidential, evidence, confidence, classified_at, sha256; `ingested` adds origin, dates, book, version), the passage index ([document-tools.md](document-tools.md)), the preflight and segment readings, and the key documents' links. The existing screens show it as counts (`IngestionView`) or a reference shelf; there is no screen for "find the file I mean and look at it". The same explorer serves four consumers as a **source tab, "From the library"**, so none of them needs Drive:

| Consumer | Uses the explorer to |
|---|---|
| Records intake | pick a file already held for a slot, with its kind shown against the slot's ([record-intake.md](record-intake.md)) |
| PDF splitter | open any PDF in the library for splitting ([pdf-splitter.md](pdf-splitter.md): "the library action"), and see which parts are already filed |
| Key documents | link an existing copy ([key-documents.md](key-documents.md): link a file under `data/`) |
| Document ingestion | see what a Drive or folder ingest would duplicate, by hash, before it runs |

**What it needs, by field**

| Wanted | Where it comes from today | Gap |
|---|---|---|
| Search by words | passage index (`document_search`) and the name | none; passages, not answers |
| Filter by kind, category, source, record, book, confidence tier, period | `documents` / `ingested` columns | none (a loader returns the facets with counts) |
| Date | `period`, `dates`, `classified_at` | a single "document date" is a reading; show which |
| Pages | preflight facts (cached by hash) | a library-wide column needs a cached count per sha256 |
| Has a text layer / suspect text | preflight; `.vision.txt` layers | likewise a cached flag, with its reader |
| Confidential | `confidential` | already masked outside the private view; the explorer must keep that rule |
| Grouping | kind, period, record, book, source folder | views only |
| Preview | `/api/file` for PDFs and images; the splitter's page pictures ([pdf-splitter-client-side.md](pdf-splitter-client-side.md)) | first-page thumbnails cached by hash |
| Duplicates, versions | sha256; ingest's version finder | a "same file as" chip |

**Shape:** one loader (`library-explorer`) returning rows, facet counts and a page token; one component built from `DataTable`, `SearchBox`, `Pill`, plus a preview pane; a phone sheet like the chooser's. The logic (what a facet means, what a kind is) stays on the server; the page renders. A "pick" returns a library id into the same pick act, so the explorer adds no write of its own.

## Setup the Picker would add (per community, if enabled)

All of it is in the community's own Cloud project; none is shared between communities.

1. **Enable the Google Picker API** (the Drive API is already on).
2. **Create an API key**, restricted to the Picker API (and the Drive API if the browser calls Drive), with website restrictions for the console's origin **and** `https://docs.google.com/*`.
3. **Note the project number** (the Picker's app id).
4. **Authorized JavaScript origins** on the community's Web client (empty today): the console's origin. Hosted (https) is clear; a loopback origin is **unverified**.
5. **Consent screen scopes:** add `drive.file`, a non-sensitive scope; it needs no verification, and the app is Internal besides. The server's Desktop client is untouched, so existing tokens are not asked to consent again (a new token for the Web client holds only what it requests).
6. **Settings in jason** (the Integrations screen's, as the handoff already plans): an administrator's switch, the API key and the project number, kept in the vault, not typed into the picker page.
7. The redirect form needs only steps 1 and 5, plus a registered redirect address for the pick's callback, and a server route.

## Phases

| Phase | What | Cost | Needs from the user |
|---|---|---|---|
| 1 | The library explorer as a source tab, with the facets, search and preview (no Google) | a few days; a page-count cache is the one new store | decisions 1 and 2 |
| 2 | Chooser improvements: recent, shared with me, starred, full text, filters, thumbnail proxy | 2 to 3 days | none |
| 3 | The redirect-form spike in one community's project: Web client, `trigger_onepick`, a real file in a private Drive and one in a shared drive, a picked folder | a day to test; two days to build the route if it works | decision 3; a test Drive account |
| 4 | If the spike fails, the web Picker: script in the console behind the administrator's switch, bytes fetched in the browser and posted to the upload route | 3 to 5 days; the origin and CSP questions come first | decisions 3 and 4 |
| 5 | Retire "share it with the account" wherever the Picker or the upload covers the case | small | none |

## Decisions, with recommendations

1. **Which comes first, the library explorer or the Picker?** Recommend the library explorer. It serves all four consumers with no Google change, and it makes a Drive pick the rarer path.
2. **Handoff decision 2 (whose eyes).** Recommend: the server chooser stays the community's Drive and says so; a per-person wide token is not built; a person's own files come in through the Picker's narrow grant, a share, or an upload.
3. **May the console ever load a Google script or take a browser token?** Recommend no for now: try the redirect form first, because it needs neither. Only if it fails, and an administrator switches it on, the web Picker with the exception named on the Integrations screen.
4. **Token to the server or bytes to the server?** Recommend bytes (browser fetch and upload) for the web Picker, and the server-side code exchange for the redirect form. Never a token in a request body.
5. **A pick of a private file: pin or copy?** Recommend a held copy by hash with its Drive provenance recorded, never a pin the server cannot read.
6. **Web component or direct API** if the web Picker is built. Recommend direct use of the documented API with `@types/google.picker`, about sixty lines, over a pre-1.0 package that fetches its own scripts from a CDN; revisit when the component is stable.
7. **What to configure first (the user):** one test community project with the Web client's redirect address for the spike, a Drive account that has a private file and a shared-drive file, and, only for phase 4, the API key and project number.

## Related

[record-intake.md](record-intake.md) (the picker verdict this page extends), [console/handoff-record-intake.md](console/handoff-record-intake.md) (`DriveChooser`, `FileSourceTabs`, the decisions), [google-workspace-setup.md](google-workspace-setup.md), [integrations-design.md](integrations-design.md), [console/security-and-privacy.md](console/security-and-privacy.md), [key-documents.md](key-documents.md), [pdf-splitter.md](pdf-splitter.md), [pdf-splitter-client-side.md](pdf-splitter-client-side.md), [document-tools.md](document-tools.md).
