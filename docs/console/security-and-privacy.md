# Security and privacy

The console (jason-ui served by jason-web) holds the association's members' data, writes jason's own stores, and, with one flag, writes PayHOA through an approved plan. These are its requirements: what is built, and what is still proposed. Each is testable.

## Where it listens

- **127.0.0.1 by default.** `jason-web` binds `127.0.0.1:8080`. `--host` is a person's choice, and the guard then accepts that name too. Serving beyond the machine is out of scope until there is sign-in for each person and a written policy on who may see what (below).
- **No CORS.** jason-web sends no `Access-Control-Allow-*` headers. The UI and the API share one origin.
- **No credential in the browser.** jason-web never asks for a Keeper, PayHOA, or Google credential. A live read that needs a session that is missing (`KeeperAuthRequired`, `GoogleAuthRequired`) fails fast with "run `jason login` in a terminal" (503). This is the non-interactive rule in AGENTS.md.
- **Files under `data/` only.** `GET /api/file` serves a photo, PDF, audio, or text file under `data/`, path-checked, known types only, with `Content-Security-Policy: sandbox`.

## The write guard

Loopback is not a boundary: any browser tab or program on the machine can reach 127.0.0.1. `jason.web.guard` puts three layers in front of every write (OWASP's [CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)):

| Layer | Rule | Refused with |
|---|---|---|
| **Host** | Every `/api/*` request and every write names a loopback host (`127.0.0.1`, `localhost`, `::1`) or the `--host` a person passed. This stops a DNS-rebinding page from reaching the API under its own name | 421 |
| **Origin** | A write (POST, PUT, PATCH, DELETE) carries `Origin` equal to the server's own host. A missing or `null` Origin is refused, and so is `Sec-Fetch-Site` other than `same-origin` | 403 |
| **Token** | A random token made when the app starts, held in memory only, never written to `data/` or a log. The page reads it from `<meta name="jason-token">` in `index.html` or `GET /api/session` and sends it as `X-Jason-Token`. Every response also sets it as an `HttpOnly; SameSite=Strict` cookie, so the older pages keep writing jason's own stores. A write outside jason (an approval's `check` or `apply`) takes the header only | 403 |

**What the guard is not.** The token is not a sign-in: a program on the machine can read `/api/session` as the page does. It is a second, independent layer against a web page in the person's browser, which the Origin check already refuses.

**No state change on GET.** Every write is a POST. An approval's `check` reads PayHOA live, so it is a POST too: a link, a prefetch, or another site's `<img>` never sets it off.

**The write switches.** `create_app` turns each group of writes off (`board_writer=None`, `extra_writes=False`, `approvals_writes=False`); a write that is off answers "writes are off". `/api/health` lists the writes that are on, and `/api/session` says whether apply and live checks are on.

## Apply: off unless a person turns it on

`POST /api/approvals/<id>/apply` is the one route that writes outside jason. It is refused unless the person who starts the server passes `--allow-apply`:

- **Off (the default).** The route is refused with the command a person runs instead: `jason approvals apply ID --yes --by NAME`. The page shows that command, as every other outward write in the console does.
- **On.** The server prints "apply is ON" when it starts. An apply carries the token in its header (the cookie alone is not enough), names its person (`by`), and echoes the fingerprint that person reviewed (`confirm`); a fingerprint that is not the approval's is refused, with nothing written. The engine then re-reads live and refuses again if anything changed since review ([approval-workflow.md](approval-workflow.md#6-re-plan-before-apply)).

Why a flag and not a role: unless sign-in is required (`--require-sign-in`), a name on an apply may be a pick from a list. Starting the server with `--allow-apply` is a person's act at the terminal, like the CLI's `--yes`, made once for the session.

## Identity

### Built: Sign in with Google

A person on the roster can sign in with their Google Workspace account (`jason.web.signin`; set up in [setup.md, Console sign-in](../setup.md#5-console-sign-in-jason-web)):
- **The flow.** OpenID Connect's authorization-code flow runs on the server, with PKCE, `state`, and `nonce`, and asks only `openid email profile`. The ID token comes straight from Google's token endpoint, in exchange for the client secret. No Google script runs in the page, and no Google token is kept.
- **The clients.** A community sets up its own Google Sign-In: one or more clients from its own Workspace (`Community.sign_in`, a private fact). The installation may add its own (`jason.access`), such as a management company's Workspace for admins and managers. The console shows one button for each. `jason sign-in --import-client` puts a downloaded client in Keeper and records it; the secret is never printed.
- **The roster.** It joins the two levels:
  - **the community's officers** (`Officer.email`, a private fact);
  - **managers** (`data/access/managers.json`). A manager whose portfolio holds this community is its manager;
  - **jason's admins** (`data/access/admins.json`). They are the overall administrators, and hold no office, so being an admin approves nothing.
- **Who gets in.** An account gets in when all of these hold:
  - the token is for the chosen client and from Google, unexpired, and carries jason-web's `nonce`;
  - the email is verified;
  - its `hd` claim is one of that client's domains;
  - the address is exactly one person's on the roster.

  With an Internal consent screen, Google refuses accounts outside the client's Workspace organization before jason sees them.
- **What it changes.**
  - While someone is signed in, a write's `by` must be the signed-in person's name; an empty one is filled with it.
  - Approval steps record `via: console:google`.
  - `jason-web --require-sign-in` refuses every write (401) until someone signs in.
  - Sign-in is not a role: what a person may approve is still the roster's.
- **The session.**
  - It is Flask's signed cookie (`jason_session`, `HttpOnly; SameSite=Lax`), signed with a key made when the app starts. Lax rather than Strict, so the cookie survives the top-level return from Google.
  - It lasts twelve hours at most, and a restart signs everyone out.
  - A person taken off the roster is signed out at their next write.
  - Sign-ins, refusals, and sign-outs are logged in `data/web/sign-ins.jsonl`, each with the client used.
- **What stays the same.**
  - The write guard (Host, Origin, token) still applies to every write, sign-out included.
  - Apply still needs `--allow-apply`.
  - The console still listens on loopback only.

**Two offices, one person.** A person who holds two offices is two roster rows with one name. Sign-in matches them once, with the offices joined. The letters' approval check and the console's people list read every office the person holds, and a portfolio manager too.

**Admin view (`--dev`, not production).** A signed-in admin may view the console as any person on the roster, or as an office with no person (`POST /auth/act-as`, a guarded write). This is for building and checking role-based views. While they view as someone else:
- every write is refused (403), so no record ever carries a name its person did not sign in as;
- the switch and its return are logged.

Without `--dev`, being an admin gives no view-as.

**A portfolio in one console: not yet.** One jason-web serves one community (the active profile). A manager with several communities runs a jason-web for each until jason serves more than one profile at once ([mvp.md](mvp.md#open-decisions), decision 14).

Without sign-in set up, or with no one signed in and sign-in not required, the console behaves as before (below), except that no file or document opens (Roles, file and document access).

### Without sign-in: a named person, not a login

- **"Signed in as" is a sample picker** over the profile's officers (`Community.officers()`, the names from the private facts). The pick is kept in the browser's `localStorage` (`jason-console-user`), a name only. It grants nothing.
- **A picked name opens nothing.** Files, documents, and the evidence's live reads need a Google sign-in (Roles, below).
- **The server checks what it can.** A letter's approval is refused unless `by` is an officer whose `approves` names the letter's approver; for the board, the president or the secretary, with the meeting's date (`tasks.approvals`). Every write requires `by`.
- **An engine approval checks names against each other, not against the officers.** The engine refuses an empty name, and refuses a second person who is the first signer or the requester (casefold, trimmed). It does not yet refuse a name that is not an officer; whether the console's door should is an open decision ([mvp.md](mvp.md#open-decisions)).
- **The second person's name starts empty** in `SecondConfirm`. Retyping is the point of that step, which falls under WCAG 3.3.7's security exception. The first signer's name is pre-filled from "Signed in as".
- **What a name proves.** On a shared machine, a name is a claim, not an authentication. The audit log records the operating-system user beside each name (`os_user`), and `via: "console"` or `"cli"`. The log does not prove who clicked. The console's caveats say so plainly.

### Later: beyond Google sign-in

- **Google sign-in authenticates a person through their Workspace account.** It is as strong as that account's own sign-in, including the organization's two-step verification, if its admin requires it.
- **A passkey (WebAuthn) remains an option** for an officer without a Workspace account. It would be registered at the manager's machine, with public keys only under `data/`.
- **Until the board decides that sign-in is required** (`--require-sign-in` as the norm):
  - apply stays behind `--allow-apply`;
  - the second-person rule guards against mistakes, not a determined person;
  - serving beyond loopback stays out of scope.

**Remote access** would need, at least: TLS, sign-in for each person, rate limits, and the board's written policy on who may see what (a rule row, by the "where the law is silent" axiom).

## Roles

**Built.** The roster is `Community.officers()`: each `Officer` has an `OfficerRole` (president, vice president, secretary, treasurer, director, manager) and `approves` (what that person may approve on their own, such as "the treasurer" or "a fluent reviewer"). "The board" is never a person's approval: it is a vote at a meeting that the president or the secretary records (`Officer.can_approve`).

**The Board / Owner view is a view, not a permission.** The owner view (`?view=owner`) shows the read-only screens an owner would see, with a banner. Anyone at the machine can switch back. It decides what a screen shows, never who may see it.

**Built: file and document access.** Opening a file or a document from the console needs a signed-in roster person, and their offices' data levels (`jason.web.access`, enforced on the server):

| Who | Opens | In the private view, for a stated reason |
|---|---|---|
| anyone on the roster (an officer, a manager, an admin) | P0, P1 | — |
| manager, president, vice president, director, secretary | P2 | P3 |
| treasurer | P2 | — |

- **The rows.** They are `SEE_RULES`, one an office. A person holding several offices gets the union. An admin with no office or manager role holds only the roster row: no P2, no P3. P4 is never served.
- **Viewing as.** An admin viewing the console as someone (`--dev`) is judged as that someone; the log names both.
- **What a file is.** `level_of_path` places a path under `data/` by rule rows, first match, and by the stores' own flags: a library file by library.db's `confidential` (any copy with the same digest counts), a Zoom meeting's files by the index's `confidential` or its kind (executive session, hearing), any path the Drive holdings mark confidential. `spec/`, `cases/`, `legal/`, and `access/` are P3; a request's files, form responses, Gmail files, mail scans, and Mailroom are P2; photos, drafts, and minutes P1; the law, the reader, the site's documents, the governing documents, and PayHOA's documents P0. **A path no row places is P2**: closed, never open.
- **The routes.**
  - `GET /api/file` answers 401 with no one signed in, and 401 when sign-in is not set up on this jason-web: fail closed. It answers 403 with the reason when the level is not the person's. P3 opens only while the person's private view is open (below), and the line it logs carries the view's id and reason.
  - A fetch gets JSON with `signIn`; a page load gets a small page with the sentence and "Sign in with Google".
  - `GET /api/library?confidential=1` (and `/api/embeds?confidential=1`) holds the confidential rows back unless the person's private view is open, with `heldBack: n`.
  - The evidence routes (`POST /api/evidence/view`, `/refresh`, `/refresh-all`, and a view's link) take the name from the sign-in, never the body. A view's link is bound to the sign-in that opened it.
- **Each serve is logged** in `access/served.jsonl` (below), before the bytes go out.

**Proposed.** Screen-level access by role, enforced on the server at each loader and write (hiding a button is not a check):

| Role | Screens | Can sign | Data levels |
|---|---|---|---|
| manager | All | First signature; one-person kinds | P0 to P2, with P2 revealed on request. P3 in the private view |
| director (president, vice president included) | All but connections | First or second signature | P0 and P1. P2 on an item they are deciding. P3 executive session in the private view |
| secretary | Overview, Governance, Records | Second signature; records the board's vote | P0 and P1. P3 executive-session minutes in the private view |
| treasurer | Overview, Money | Second signature on money kinds | P0 and P1. Account numbers by last four only |
| reviewer | Approvals waiting on a second person, and their evidence | Second signature only | As the approval shows |
| counsel | Governing documents, conflicts, notices' requirements and proof, granted matters | None | P0, plus granted P3 matter files |

`OfficerRole` has no reviewer or counsel. Whether they become officer roles, or a separate grant in the profile, is open ([mvp.md](mvp.md#open-decisions)).

## Data levels

| Level | What | Shown | Example source |
|---|---|---|---|
| **P0** | The association's documents and the law | Always | `cite_document`, `living_document` |
| **P1** | Members' names and units, tag names, request kinds and clocks | To the people who work with members | `owner_info.ledger`, `member_requests` |
| **P2** | Contact: emails, phone numbers, mailing addresses, a unit's occupancy as an owner reported it | **Masked** by the server (`a••••@example.com`); revealed one field at a time, logged by kind | PayHOA people rows, `owner_responses.Context.answers` |
| **P3** | Restricted: executive-session minutes and material; the membership list as a book; ballots and election materials (Civil Code 5215, 5200(c)); legal matters and case files; delinquency detail beyond the unit; private facts (`data/spec`) | Only in the **private view**, off by default, opened for a stated reason and logged. Restricted books follow `jason cite --private` | `reader` with `private=True`; `case_file`; `private.facts` |
| **P4** | Secrets: passwords, tokens, PINs, API keys, account and routing numbers in full, Keeper record values | **Never**: not shown, stored, logged, or asked for | — |

**Built.** The approvals routes mask anything that looks like an email address or a phone number before it leaves the server, except one document a named person asks to see from an evidence panel, which is shown unmasked and logged (`evidence/views.jsonl`, below); the audit log masks email addresses before a line is written; a plan item never carries a value `intake.secret_reason` flags. The money screens mark delinquency as an executive-session subject; the legal and hearing screens are for directors and counsel by their caveats. The owner view leaves out the screens that are the board's.

### Built: the private view

P3 is shown only in a person's **private view**: a time-limited, logged window they open for themselves (`jason.web.access`; the console's `PrivateSwitch`).

- **Who may open it.** A signed-in person whose offices open P3 in the private view (`SEE_RULES`: manager, president, vice president, director, secretary). The treasurer alone, and an admin with no office, are refused with the reason, and the switch shows disabled with that reason beside it. It is refused while an admin views the console as someone else, and 401 with no one signed in.
- **Opening it.** The **Private view: off** switch in the header asks "Why" (required, a short phrase such as "executive session prep", 120 characters at most, never an owner's personal details) and "For 15 / 30 / 60 minutes" (30 by default), then confirms "Open the private view as NAME for 30 minutes". It is `POST /api/private` with `{reason, minutes}`, behind the write guard and the token header. An empty reason, a long one, or one that looks like a secret (`intake.secret_reason`) is refused (400) and nothing is kept; contact details in a reason are masked before it is logged.
- **What it is.** `{id, by, sub, reason, opened, until}` in the signed session cookie; the id is `secrets.token_hex(4)`. It is bound to the account's Google `sub`, so another sign-in in the same browser never inherits it. While an admin views as someone else it is not open for that view.
- **Closing it.** "Close private view" (`DELETE /api/private`), signing out, a new sign-in, or its time running out: the next request finds it expired. Opening, closing, and expiry are each a line in `access/private.jsonl`.
- **What the page reads.** `GET /api/session` carries `private: {open, until, reason, id, mayOpen, why, minutes, default}`: whether it is open, until when and why, and whether this person may open it, with the reason when not. The `sub` it is bound to never leaves the server.
- **On screen.** While it is open, a hatched band in the warning tone runs under the header, in words: "Private view — restricted material is shown — for REASON — until 21:15 (12 min left)", with "Close private view". It is a labelled region; focus goes to its heading when it opens; the countdown is not announced, but a polite line says when five minutes are left and when it closes. Opening, closing, and expiry reload the page, so every screen fetches again under the new view. The owner view never shows the switch or the band.
- **What it opens.** A P3 file from `/api/file`; the held-back rows of `/api/library?confidential=1` and `/api/embeds?confidential=1`; in an evidence panel, a citation's confidential documents (each listed with `level: "P3"`, a **Confidential** chip, and in its viewer "Confidential: shown in the private view; this view is logged."), a restricted book's words (`jason cite --private`), and an executive-session board item's summary and notes. A document link opened in the private view stops working when it closes.
- **The log.** Every line `access/served.jsonl` writes while the view is open carries `private: true`, its `privateId`, and its reason. There is no per-request `private=1&reason=` any more: the window is the one way.

**Proposed.** P2 masking for each field, with a logged reveal (`MaskedField`), server-side. **Masking is the server's job**: a masked value never reaches the browser, and hiding it with CSS is not masking. Until it exists, a screen that would show P2 values (Members and units, a notice's member rows) is not built.

**Account numbers** show their last four digits, as `finance.balances` names accounts. A full number is P4.

**Test accounts** (`config.test_memberships`) are labeled "test" wherever they appear, and never count as owners.

### URLs

A URL carries an id or a filter: a screen, a unit id, a request id, a notice key, a date, `?view=owner`. It never carries a name, an email, an address, or a search for one. A search for a person is a POST. This keeps member data out of browser history, any server log, and any Referer.

### Exports (proposed)

A table downloaded as CSV has the columns shown. P2 is masked unless revealed; P3 only in the private view. Each export is logged with its column list and row count.

## Outside resources

The earlier spec required no CDN, web font, or remote frame. jason-ui made three exceptions, each on first use:
- `Markdown` loads Mermaid from a CDN the first time a page has a diagram (`setMermaidUrl` overrides it);
- `GET /api/theme` may give the profile's font stylesheet URL;
- `Embed` frames Google Docs, Sheets, Slides, Forms, Drive, Calendar, and a Zoom recording, for a viewer already allowed to see them.

None of them sends member data: they load a library, a font, or a file the viewer's own Google session opens. A Content-Security-Policy for the bundle would name exactly these origins and nothing else. Whether to self-host Mermaid and the font is open ([mvp.md](mvp.md#open-decisions)).

## Secrets

- **No secret is ever in the UI.** That includes values from `.env`, the Google token, Keeper, PayHOA's session, and the guard's token (which the page holds only in memory and the cookie).
- **Status shows only whether a connection is present**, yes or no, and the command that fixes it.
- **Keeper records are named by title**, never by UID or value.
- **Every text field that stores** (a reason, an answer, a note) goes through `intake.secret_reason` where the task already checks it. A value that looks like a secret is refused with the CLI's message, and nothing is kept.
- **Errors** say what did not happen and what to do, in jason's words. They never show a traceback, a request header, or a setting.

## What the console stores

Everything is under the profile's data folder (`jason.config.data_dir`), private and never checked in:

| Path | Holds | Level |
|---|---|---|
| `approvals/apr-*.json` | Engine approvals and their items | P1. Evidence points to P2 or P3 sources; it does not copy them |
| `approvals/apr-*.evidence.json` | The plan's snapshot of each record it read live: a request's status and answers as read ([approval-workflow.md](approval-workflow.md#evidence-you-can-open)) | P2, as the PayHOA catalog is. Contact details and answers flagged P2 are masked by the server before they leave it (`jason.approvals.evidence`) |
| `approvals/audit.jsonl` | The approvals audit log | P1 at most |
| `evidence/refreshes.jsonl` | One line for each live re-read of a piece of evidence: when, who, which address, the system, and whether it worked | P1; never the answers |
| `drive/copies/` | jason's copies of Drive files, exported on a person's click ([documents.md](documents.md#google-docs-sheets-and-slides), `jason.tasks.drive_copies`): `<id>.pdf`, a Doc's `<id>.md`, a Sheet's `<id>.csv`, a stored image's `<id>.image.<ext>`, the thumbnail `<id>.png`, and the record `<id>.json` (`readAt`, `via`, `by`, `modifiedTime`, `mimeType`, `name`). A file that forbids copies, or one over Google's 10 MB export limit, is never kept | The file's level by the Drive holdings (`drive_copies.level_of`): P3 when confidential, listed and opened only in the private view; P0 a letter template or a file under a Drive root's path rule; else P2. Served only through the evidence's documents (a logged view) and `GET /api/drive/thumb/<id>` (signed in, the level, logged) |
| `thumbs/` | Page 1 of a PDF under data/, rendered by `GET /api/thumb?path=` (`jason.tasks.pdf_thumbs`) and kept as `<sha256 of the path>.png`, rendered again when the PDF changes ([documents.md](documents.md#statutes-and-the-associations-documents)) | P3 by path, so `/api/file` never serves one; `/api/thumb` serves it at the PDF's own level (signed in, the level, logged under the PDF's path) |
| `evidence/views.jsonl` | One line for each document a person opened unmasked from an evidence panel (`POST /api/evidence/view`): `at`, `by`, `address`, `document`, `kind`. The view itself shows the submission or file whole, contact details included, to the signed-in person only (the body's name is never used, and the link is bound to that sign-in); it is never automatic, sits behind the write guard and the token header, and is refused while an admin views as someone else. A file is served by a ten-minute link held in memory (`GET /api/evidence/document/<token>`), path-checked, `nosniff`, `no-store`, sandboxed, and an HTML, SVG, or XML file only as an attachment ([approval-workflow.md](approval-workflow.md#evidence-you-can-open)) | P1; never the contents |
| `access/served.jsonl` | One line for each file `/api/file` served, each document opened unmasked from an evidence panel, and each confidential listing shown (`jason.web.access`): `at`, `by` (who signed in), `as` (whom an admin viewed as), `path` or `address`, `level`, `private`, and while the private view is open its `privateId` and stated `reason`. Written before the bytes go out; a log that cannot be written serves nothing | P1; never the contents |
| `access/private.jsonl` | One line each time a private view is opened, closed, or expires: `at`, `event` (`opened`, `closed`, `expired`), `id`, `by` (who signed in), the stated `reason`, `minutes` on opening, and on a closing `why` when it was not the person's click ("signed out", "signed in again", "another sign-in", "opened again"). Opening is refused when the line cannot be written | P1; the reason is a short phrase, contact details masked, never a secret |
| `approvals/letters.json` | The letters jason drafted, their stages and trail | The letter's own level: a notice to members is P1; a letter to one owner names that owner |
| `board/decisions.json`, `meetings/plan-<date>.json`, `meetings/room-<date>.json` | The board's decisions, a meeting's plan, the room's record | P1; executive-session items by general nature only |
| `console/reveals.jsonl` | Each time a person showed owners' names on the instrument graph: when, who, the scope, the parcel or unit, how many persons were named; never the names | P1 at most |
| `onboarding/<profile>-documents-located.json` (and `.md`), `key-documents/<profile>.json` and `key-documents/<profile>/files/` | The documents located for the association with each instrument's private persons and index side, the key documents and their copies | P1: owners' names, shown to the people who work with them and masked on the graph until a person asks |
| `canvases/`, `dock/dock.json`, `registers/`, and the other console stores ([web-ui.md](../web-ui.md#api)) | A person's work and the board's columns | P1, and P3 where the subject is (a canvas on a legal matter) |

The guard's token lives in memory only; a restart makes a new one. The browser keeps the "Signed in as" name and nothing else.
