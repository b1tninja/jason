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

An officer can sign in with their Workspace account (`jason.web.signin`; set up in [setup.md, Console sign-in](../setup.md#5-console-sign-in-jason-web)):
- **The flow.** OpenID Connect's authorization-code flow runs on the server, with PKCE, `state`, and `nonce`, and asks only `openid email profile`. The ID token comes straight from Google's token endpoint, in exchange for the client secret. No Google script runs in the page, and no Google token is kept.
- **Who gets in.** An account gets in when all of these hold:
  - the token is for this client and from Google, unexpired, and carries jason-web's `nonce`;
  - the email is verified;
  - its `hd` claim is one of the association's email domains;
  - the address is exactly one officer's on the roster (`Officer.email`, a private fact).

  With an Internal consent screen, Google refuses accounts outside the Workspace organization before jason sees them.
- **What it changes.**
  - While someone is signed in, a write's `by` must be the signed-in officer's name; an empty one is filled with it.
  - Approval steps record `via: console:google`.
  - `jason-web --require-sign-in` refuses every write (401) until an officer signs in.
  - Sign-in is not a role: what a person may approve is still the roster's.
- **The session.**
  - It is Flask's signed cookie (`jason_session`, `HttpOnly; SameSite=Lax`), signed with a key made when the app starts. Lax rather than Strict, so the cookie survives the top-level return from Google.
  - It lasts twelve hours at most, and a restart signs everyone out.
  - An officer taken off the roster is signed out at their next write.
  - Sign-ins, refusals, and sign-outs are logged in `data/web/sign-ins.jsonl`.
- **What stays the same.**
  - The write guard (Host, Origin, token) still applies to every write, sign-out included.
  - Apply still needs `--allow-apply`.
  - The console still listens on loopback only.

Without sign-in set up, or with no one signed in and sign-in not required, the console behaves as before (below).

### Without sign-in: a named person, not a login

- **"Signed in as" is a sample picker** over the profile's officers (`Community.officers()`, the names from the private facts). The pick is kept in the browser's `localStorage` (`jason-console-user`), a name only. It grants nothing.
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

**Built.** The approvals routes mask anything that looks like an email address or a phone number before it leaves the server; the audit log masks email addresses before a line is written; a plan item never carries a value `intake.secret_reason` flags. The money screens mark delinquency as an executive-session subject; the legal and hearing screens are for directors and counsel by their caveats. The owner view leaves out the screens that are the board's.

**Proposed.** P2 masking for each field, with a logged reveal (`MaskedField`), and the private view for P3 (`PrivateSwitch`), both server-side. **Masking is the server's job**: a masked value never reaches the browser, and hiding it with CSS is not masking. Until these exist, a screen that would show P2 or P3 values (Members and units, a notice's member rows) is not built.

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
| `approvals/audit.jsonl` | The approvals audit log | P1 at most |
| `approvals/letters.json` | The letters jason drafted, their stages and trail | The letter's own level: a notice to members is P1; a letter to one owner names that owner |
| `board/decisions.json`, `meetings/plan-<date>.json`, `meetings/room-<date>.json` | The board's decisions, a meeting's plan, the room's record | P1; executive-session items by general nature only |
| `canvases/`, `dock/dock.json`, `registers/`, and the other console stores ([web-ui.md](../web-ui.md#api)) | A person's work and the board's columns | P1, and P3 where the subject is (a canvas on a legal matter) |

The guard's token lives in memory only; a restart makes a new one. The browser keeps the "Signed in as" name and nothing else.
