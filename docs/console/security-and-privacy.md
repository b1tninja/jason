# Security and privacy

The console holds the association's members' data and can write to PayHOA and Google. These are its requirements. Each one is testable, and [mvp.md](mvp.md) lists the tests.

## Where it listens

- **127.0.0.1 only.** `jason serve` binds to `127.0.0.1` and has no option for another address in phases 1 through 4. A request whose socket peer is not loopback is refused, whatever the bind says.
- **The Host header is checked.** Every request's `Host` must be exactly `127.0.0.1:<port>` or `localhost:<port>`. Anything else gets 421 Misdirected Request. This stops a DNS-rebinding page in the person's browser from reaching the console under another name.
- **No CORS.** The console sends no `Access-Control-Allow-*` headers, and refuses a preflight.
- **Headers on every response:**
  - `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'`;
  - `X-Content-Type-Options: nosniff`;
  - `Referrer-Policy: no-referrer`;
  - `Cache-Control: no-store` on every page that shows member data.

  No inline script runs. The one small script is a file the console serves itself ([architecture.md](architecture.md#stack)).
- **No outside resources.** No CDN, web font, or analytics. The console works with the network unplugged, apart from the live reads that need PayHOA or Google.

## The session token

Being on loopback is not enough: any program or browser tab on the machine can reach 127.0.0.1. The console therefore needs a secret that only the person who started it holds. This is the model Jupyter uses.

1. On start, `jason serve` makes a random token (`secrets.token_urlsafe(32)`). It keeps the token in memory and prints a sign-in link once to the terminal: `http://127.0.0.1:<port>/login#<token>`.
   - The token is in the URL **fragment**, which the browser never sends to the server or puts in a Referer.
   - The login page's script reads the fragment, POSTs it, then clears it with `history.replaceState`.
   - Without script, the login page has a field to paste the token into.
2. The POST exchanges the token for a session cookie:
   - `jc_session`, a separate random value;
   - `HttpOnly; SameSite=Strict; Path=/`;
   - `Secure` is not possible over plain-http loopback, and is omitted.

   The session expires after 12 hours, or 30 minutes idle. The start token is single-use: once exchanged, a second exchange is refused until `jason serve --rotate` or a restart.
3. `jason serve --open` opens the default browser on the link, so the person never copies it.
4. The token is never written to `data/`, to a log, or to the audit log. `jason serve --print-token` prints it again while the server runs, from the terminal that owns it.

**The launch entry** (`.claude/launch.json`) opens the console's origin with no path, so the browser lands on `/login`, which asks for the token ([architecture.md](architecture.md#launch-configuration)).

## CSRF

This follows OWASP's CSRF guidance ([cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)). The layers are:
- **A synchronizer token.** Each session has a random CSRF token, kept on the server. Every form carries it in a hidden field. Every POST, PUT, or DELETE must carry the session's token, or the request is refused (403) before the handler runs.
- **Origin and Fetch Metadata.** A state-changing request must have `Origin` equal to the console's own origin. If the browser sends `Sec-Fetch-Site`, it must be `same-origin`. A missing `Origin` on a state-changing request is refused.
- **`SameSite=Strict`** on the session cookie.
- **No state change on GET.** Every action is a POST, and a GET never writes. This includes "reveal": a reveal is a POST that returns the value and logs it.
- **The approval fingerprint is a guard of its own.** Approve, confirm, and apply each POST the fingerprint the person saw. The server refuses if it is not the current one ("the plan changed since you opened this page").

## Identity

### Phases 1 to 4: a named person, not a login

- **Acting as.** At session start, the person picks who they are acting as from the roster, and their role. The roster is a private fact, in `data/spec/<profile>.json`, read through `jason.community.private.facts`. The session carries the pair. The page header shows it, with "change".
- **The approve bar's name field** comes pre-filled with the acting name. This follows WCAG 3.3.7, which asks a site not to make a person retype what they entered earlier in the same process. The person can correct it. Submitting signs with exactly what the field holds.
- **The second person's name field starts empty.** Retyping is the point of the step, and that falls under 3.3.7's security exception. The console refuses the same name as the first signer or the requester.
- **What a name proves.** On a shared machine, a name is a claim, not an authentication. The audit log records beside it:
  - the session id;
  - the operating-system user (`getpass.getuser()`);
  - the time.

  The log does not prove who clicked. It proves which session did, at the manager's machine. The docs and the console's own help say so plainly.
- **No password field anywhere.** The console never asks for a Keeper, PayHOA, or Google credential. When a live read needs a session that is missing (`KeeperAuthRequired`, `GoogleAuthRequired`), the job fails fast with the command to run in a terminal (`jason login`). This is the non-interactive rule in AGENTS.md.

### Phase 5: board sign-in, later

Each person gets their own credential, so a name is authenticated:
- **The preferred path:** a passkey (WebAuthn) for each roster person, registered at the manager's machine and kept in `data/console/` (public keys only). A passkey is phishing-resistant, and meets WCAG 3.3.8 (accessible authentication), because nothing has to be remembered or transcribed.
- **The fallback:** a one-time link emailed to the roster person's address, through a Gmail draft a person sends. That is the only send path jason has.

**Remote access stays out of scope** until the board decides it. Serving outside 127.0.0.1 would need, at least:
- TLS;
- sign-in for each person;
- rate limits;
- the board's written policy on who may see what (a rule row, by the "where the law is silent" axiom).

Until then, a director uses the console at the manager's machine, or reads exports.

## Roles

`jason.console.identity.Role` is a closed set:

| Role | Screens | Can approve | Data levels |
|---|---|---|---|
| `manager` | All | MANAGER and BOARD_RULE kinds; first signature on TWO_PERSON kinds | P0 to P2, with P2 revealed on request. P3 in the private view |
| `director` | All but Settings → connections | First or second signature | P0 and P1. P2 on an item they are deciding. P3 executive session in the private view |
| `secretary` | Today, Meetings, Notices, Governing documents, Schedule, Records | Google Doc kinds; second signature | P0 and P1. P3 executive-session minutes in the private view |
| `treasurer` | Today, Finance, Schedule, Members (no contact) | Second signature on money kinds | P0 and P1. Account numbers by last four only |
| `reviewer` | Approvals (waiting on a second person), and their evidence | Second signature only | As the approval shows |
| `counsel` | Governing documents, conflicts, notices' requirements and proof, and granted matters | None | P0, plus the granted P3 matter files |

The role table is **data**: a `RoleGrant` row in the profile names who holds which role. It is not code. Each check is made on the server, at the route; hiding a button is not a check.

## Data levels

| Level | What | Shown | Example source |
|---|---|---|---|
| **P0** | The association's documents and the law | Always | `cite_document`, `living_document` |
| **P1** | Members' names and units, tag names, request kinds and clocks | To roles that work with members | `owner_info.ledger`, `member_requests` |
| **P2** | Contact: emails, phone numbers, mailing addresses, a unit's occupancy as an owner reported it | **Masked** (`a••••@example.com`, `123 M••• St`). Revealed by a POST, one field at a time, logged by kind | PayHOA people rows, `owner_responses.Context.answers` |
| **P3** | Restricted: executive-session minutes and material; the membership list as a book; ballots and election materials (Civil Code 5215, 5200(c)); legal matters and case files; delinquency detail beyond the unit; private facts (`data/spec`); the profile's private notes | Only in the **private view**, which is off by default. Turning it on asks for a reason, is logged, and lasts until turned off or 30 minutes idle. Restricted books follow `jason cite --private` | `reader` with `private=True`; `case_file`; `private.facts` |
| **P4** | Secrets: passwords, tokens, PINs, API keys, account and routing numbers in full, Keeper record values | **Never**: not shown, stored, logged, or asked for | — |

**Masking is the server's job.** A masked value never reaches the browser. Hiding it with CSS is not masking. The reveal endpoint returns one field, for one row, to a role allowed to see it.

**Account numbers** are shown by their last four digits, as `finance.balances` names accounts. A full number is P4, and the console has no field that holds one.

**Test accounts** (`config.test_memberships`) are labeled "test" everywhere they appear. They never count as owners.

### URLs

A URL carries an id or a filter: a unit id, a request id, a notice key, `?status=open`. It never carries a name, an email, an address, or a search for one. A search for a person is a POST, and its results page has no query string. This keeps member data out of the browser's history, out of server access logs, and out of any Referer.

### Exports

A table can be downloaded as CSV with the columns shown. P2 is masked in the export unless it was revealed. P3 is exported only in the private view. Each export is logged with its column list and row count. Like `jason owner-info --out`, an export carries names and no addresses unless addresses were asked for.

## Secrets

- **No secret is ever in the UI.** That includes values from `.env`, the Google token, Keeper, PayHOA's session, and the console's own start token after login.
- **Settings shows only whether a connection is present**, yes or no, and the command to fix it.
- **Keeper records are named by title**, never by UID or value. The intake rule answers with "the Keeper record's name".
- **Every text field that stores** (an intake answer, a rejection reason, a withdrawal reason) goes through `intake.secret_reason`. A value that looks like a secret is refused with the same message the CLI gives, and nothing is kept.
- **Error pages** show a short message and a reference to the server log. They never show a traceback, a request header, or a settings value. The server log redacts `Cookie`, `Authorization`, and form fields named like secrets.

## What the console stores

Everything is under `config.data_dir()/console/`, which is private and never checked in:

| File | Holds | Level |
|---|---|---|
| `approvals.db` | Approvals and their items | P1. Evidence links point to P2 or P3 sources; they do not copy them |
| `audit.jsonl` | The audit log | P1 at most |
| `prefs.json` | A person's console preferences (filters, density) | P0 |

Sessions and the CSRF tokens live in memory only. A restart signs everyone out.
