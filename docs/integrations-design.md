# Integrations and the community credential vault

Status: design (2026-10-05), not built. It turns each service jason talks to into an **integration** that an administrator configures for each community, with its credentials in a **vault** behind one interface. The secret manager behind that interface is chosen when jason is containerized and deployed; until then the vault's backend is Keeper, as it is today. Companions: [scheduler-daemon-design.md](scheduler-daemon-design.md) (how often each integration is read) and [console/handoff-instance-and-integrations.md](console/handoff-instance-and-integrations.md) (the screens and the setup dialogs). Earlier research it builds on: [credential-store-research.md](credential-store-research.md), [deployment-research.md](deployment-research.md), [install-design.md](install-design.md).

## Where it stands today

Every credential is the installation's. `.env` names a Keeper record per service (`config.py` collects every `*_record_uid` key), and one Google token file serves every command:

| Service | Credential | Where it lives today | Scope today |
|---|---|---|---|
| Keeper itself | master password, device approval, 2FA; persistent login | `~/.keeper/keeper-config.json`; ends after 30 days unused | installation |
| Google Workspace | OAuth **Desktop** client and a refresh token; Tasks, Vault, Photos each their own token | client in Keeper `google_oauth_record_uid`; tokens in `secrets/*.json` | installation |
| Console sign-in | OAuth Web client (OpenID Connect, PKCE) | Keeper records named in `data/spec/<profile>/sign_in.json` and `data/access/sign_in.json` | **per community** and per installation |
| PayHOA | username, password, a TOTP seed | Keeper `payhoa_record_uid`; org id from the profile | installation (org id per community) |
| Zoom | Server-to-Server OAuth (account id, client id, secret) | Keeper `zoom_record_uid` (`jason zoom --store-app`) | installation |
| PostScanMail | API key | Keeper `postscanmail_record_uid` (a stray `PostScan_Mail_API_Key.json` also sits, git-ignored, in the checkout: move it to Keeper and delete it) | installation |
| SMUD, the City's utility billing (i-doxs), Accela, the signed-in vendor portals | username and password (i-doxs adds security questions) | a Keeper record each | installation |
| County sources, public vendor portals, the law library, local models | none | — | installation cache, per-community stores |

Only the data folder, PayHOA's organization id, and the console's sign-in clients are per community. A second community today would share the first one's Google token, Zoom app, and portal logins.

## The model

**An integration** is a kind of connection (Google Workspace, PayHOA, Zoom, …). **A connection** is one community's configured use of it: which account, which capabilities, its credential's location in the vault, its schedule, and its state. The administrator configures connections; a community's officers see their state.

```text
Integration (in code, one per kind)          Connection (per community, data)
  key, name, scope (instance | community)      community, integration, account label
  auth method (oauth-web | s2s-oauth |         capabilities on, vault reference
    password+totp | api-key | none)            state: not set up | needs sign-in | connected | failing | paused
  capabilities → scopes / permissions          connected_by, connected_at, last_checked
  rate limits (published or polite)            schedule overrides (with who and when)
  default cadence, floor, stale_after
  setup steps (the dialog's content)
  check() — a read that proves it works
```

**Two scopes.**
- **Instance** integrations are the installation's: the vault itself, the law library, the local models, the county caches, the public vendor portals, the installation's sign-in client, and the operator's own accounts (Bedrock, the job host).
- **Community** integrations are each community's own: Google Workspace, PayHOA, Zoom, PostScanMail, the utilities, the signed-in vendor portals, the console's community sign-in client. A community's connection never reads another community's credential or data.

**Rules every integration keeps:**
- **No secret in the console.** The console never displays, logs, or stores a secret, and never puts one in a manifest, report, response, or URL (AGENTS.md Boundaries). On this PC a secret reaches the vault through a terminal command (a hidden prompt, or a provider's file moved into Keeper and deleted) or the provider's own consent screen. When hosted, a write-only field may pass a value over HTTPS straight to the vault's put, never returned and logged only as "set, by whom, when" ([the handoff](console/handoff-instance-and-integrations.md#secrets-in-the-console)). The console holds the vault reference and shows "set" or "not set".
- **The narrowest scope that does the job,** listed before consent, read-only first. A write capability (Gmail drafts, Docs edits, Zoom meeting creation) is a separate capability turned on separately.
- **A connection counts as connected only after a read succeeds** (`check()`): listing one Drive file, reading the PayHOA organization, listing one Zoom meeting. Who connected it and when are recorded.
- **Revoking and rotating are as visible as connecting.** Disconnecting removes the vault entry, revokes the provider's token where the provider allows it, pauses the schedules, and records who did it.
- **Sign-in failures stop, they do not retry.** A 401, an auth 403, `GoogleAuthRequired`, or `KeeperAuthRequired` turns the connection to "needs sign-in" and pauses its schedules ([scheduler-daemon-design.md](scheduler-daemon-design.md)).

## The vault

One interface, the `SecretStore` of the earlier research, with every secret named by a path:

```text
jason/<scope>/<community or "instance">/<integration>/<name>
   e.g. jason/community/oakview/google-workspace/oauth-client
        jason/community/oakview/google-workspace/token/<account>
        jason/community/oakview/payhoa/login
        jason/instance/instance/signin/oauth-client
```

| Operation | Meaning |
|---|---|
| `get(path)` | the secret, or a miss |
| `put(path, value, if_version=None)` | writes; with `if_version` it is check-and-set, needed because a provider may return a new refresh token on every refresh (Zoom's user OAuth always does) |
| `delete(path)` | removes it (and its versions where the backend keeps them) |
| `list(prefix)` | names only, never values |
| `describe(path)` | set or not, version, last changed, by whom where the backend records it |

**Token rules** (Google's own guidance and RFC 9700):
- Refresh tokens are encrypted at rest, kept off the browser, and never logged.
- A new refresh token is saved before the access token it came with is used, under the version check or the store lock.
- The web flow is the authorization-code flow with PKCE even for a confidential client, a one-time `state` bound to the server session **and the community**, and a `nonce` for OpenID Connect. One callback path (`/auth/<provider>/callback`) serves every community; the community travels in the server-side `state`, never in the URL.
- jason notices the ways a Google token dies: unused for six months; a Gmail-scoped token after the user changes their password; the 101st token for one user on one client (the oldest is dropped silently); seven days for any app left in "Testing" that asks for more than `openid email profile`. Each becomes "needs sign-in", never a silent gap.
- A community that leaves has its tokens revoked and its vault prefix deleted.

### Backends, by tier

| Tier | Backend | How jason authenticates to it | Notes |
|---|---|---|---|
| **This PC (now)** | **Keeper**, as today (Commander via `keepersdk`), records named by vault path | the Windows user's Keeper login (`jason login`; 30-day idle logout) | No change of backend now. The change is that paths replace `.env` keys. Tests use Moto (Apache 2.0) in Docker or an in-memory fake. |
| This PC, alternative | OS keyring (Windows Credential Manager, DPAPI) | the Windows user | Least to run; one user, one machine. |
| **One VM, a few communities** | **SSM Parameter Store SecureString**, a path per community (free standard tier; a KMS key per community about $1 a month) | an **EC2** instance role, so no stored secret | Lightsail has no instance role (only an IAM user's keys on the box), so the self-host VM is EC2, or the store is OpenBao. |
| One VM, off AWS | **OpenBao** 2.7 (MPL), a namespace per community (since 2.3), per-namespace sealing (2.6), static-key auto-unseal (2.4) | AppRole with a response-wrapped, single-use SecretID | More to run; the unseal key must come from outside the VM or be entered by hand. |
| **Hosted, many communities** | **AWS Secrets Manager**, one JSON secret per community, IAM by path and tag (ABAC); a KMS key per community for any that ask | the ECS task role | About $0.40 a community a month plus calls. |

Rejected or not now: Vault Community (BSL license, no namespaces without Enterprise); Doppler (self-host only in Enterprise); 1Password service accounts (vault access fixed at creation, a 50,000-a-day account-wide request cap on Business); Keeper Secrets Manager as the hosted store (billed per Keeper Business user, IP lockdown in place of IAM). **Keeper Secrets Manager** remains a good self-host backend for an installation that already pays for Keeper Business: a non-human client from a one-time token, with no master password and no device approval, which would end the 30-day logout for a daemon.

**What changes now, with no new secret manager:** the vault interface with a Keeper backend; vault paths per community in place of `.env` keys (`.env` keeps only the vault's own login); the Google token and every portal login looked up per community; `jason vault migrate` to copy today's records under the new paths. The backend swap is deployment work.

## The integrations

| Integration | Scope | Auth | Capabilities (each a separate switch) | Setup the administrator does |
|---|---|---|---|---|
| **Google Workspace** | community | OAuth **Web application** client in the community's own Workspace, consent screen **Internal**; one token per account jason uses (its mailbox, or a named officer's) | read Drive, Docs, Sheets; read Gmail; read Calendar; draft in Gmail; edit Docs and Sheets; Forms; Tasks; Vault (separate token); Photos (separate token) | the Cloud project, the APIs, the consent screen and branding, the Web client and its redirect URI, the client into the vault, the first sign-in, jason's mailbox in the groups ([below](#google-workspace)) |
| Console sign-in | community and instance | OAuth Web client, OpenID Connect (`openid email profile`) | sign-in only | a Web client (may be the same Cloud project as above) |
| **PayHOA** | community | username, password, TOTP seed, in one vault entry | read the catalog, ledger, budget, reconciliations, reports, meetings; bulk writes (owner information, broadcasts) as a separate switch | the vault entry, the organization id, a check |
| **Zoom** | community | Server-to-Server OAuth app in the community's Zoom account (account id, client id, secret); one-hour tokens, no refresh token | read meetings, recordings, summaries, participants; create meetings (hearings) | the Marketplace app, its scopes, the three values into the vault ([below](#zoom)) |
| PostScanMail | community | API key | read the scanned mail | the key into the vault |
| Utilities (SMUD, the City's billing) | community | username and password (i-doxs adds security questions) | read bills and usage | the vault entry |
| Vendor portals, signed in | community | username and password, one per portal | read invoices and visits | the vault entry, named by the profile's portal row |
| Vendor portals, public; county sources; the law library; local models | instance | none | read | nothing to connect; jason checks they answer |

### Google Workspace

**Recommended: each community's own Cloud project, an Internal app with a Web client.** Google needs no verification for an Internal app, shows no unverified warning, and sets no 100-user cap; restricted scopes in an Internal app get no further review. One community's breach stays that community's. It is what `jason sign-in --import-client` already does for console sign-in. It costs the community's administrator about 30 minutes with the guide.

The alternatives, for later:
- **One jason-owned External app, verified.** The best experience (the admin only consents), but `drive`, `drive.readonly`, `gmail.readonly`, and `gmail.compose` are restricted scopes, so it needs Google's verification and a **CASA security assessment every year** (about $540 at Tier 2, up to $4,500 at Tier 3, by third-party pricing), and one breach exposes every community. Worth it only at scale.
- **Admin-trusted**: each Workspace admin marks jason's unverified client as Trusted. Google lists this as a case where verification is not needed; whether it holds for many unrelated organizations is not verified, and it does not cover consumer Gmail.
- **A service account with domain-wide delegation.** Google advises against it: it can impersonate any user, super-admins included. Only for a narrow admin task (Groups membership), and then keyless.
- **A Gmail-only community** (no Workspace) cannot use Internal. It uses an External app published "In production" and unverified: the warning screen, fewer than 100 users. Never "Testing" for Drive or Gmail: those tokens die in seven days.

**The setup guide becomes the dialog.** The steps in [setup.md](setup.md#google-workspace) are the dialog's content, changed in four places:
1. **The client is a Web application**, not a Desktop app: a hosted jason cannot receive a Desktop client's loopback redirect. Its authorized redirect URI is `https://<jason's host>/auth/google/callback` (and `http://127.0.0.1:8080/auth/google/callback` on this PC).
2. **The client goes into the vault under the community's path** (`jason integrations import google-workspace client_secret.json --yes --delete-file`), never into `.env`.
3. **The first sign-in happens in the browser,** from the dialog, with the account jason uses (its mailbox, or the signed-in officer's), and its token is stored under that account's path.
4. **The scopes come from the capabilities switched on,** read-only first; turning a write capability on asks for one more consent.

The steps, in order, with what jason can check after each:

| Step | The administrator, in Google's console | jason checks |
|---|---|---|
| 1. The project | Create a Cloud project inside the community's Workspace organization | — |
| 2. The APIs | Enable each API for the capabilities switched on (Drive, Docs, Sheets, Gmail, Calendar, Drive Activity, Forms, Tasks, Photos Picker and Library, Vault) | at sign-in, a call to each; a disabled API names itself |
| 3. Branding | Google Auth Platform → Branding: app name `jason` (or the community's choice), a support email at the community's domain, the logo optional | — |
| 4. Audience | User type **Internal** | the token's `hd` matches the community's domain |
| 5. Data access | Add the scopes the capabilities need (the dialog lists them, read-only first) | the granted scopes against the asked |
| 6. The client | Clients → Create client → **Web application**; the redirect URI the dialog shows; no JavaScript origins; download the JSON (newer projects show the secret only then) | — |
| 7. Into the vault | `jason integrations import google-workspace <file> --community C --yes --delete-file` (or the dialog's upload, which never displays the secret) | the vault entry is set |
| 8. Sign in | "Sign in with Google" in the dialog, as the account jason will read with | a Drive list and a Gmail profile read succeed |
| 9. jason's mailbox | the account in every group with "Each email" delivery ([setup.md](setup.md#6-jasons-mailbox)) | the groups the mailbox belongs to |

A redirect URI can take from five minutes to a few hours to take effect; the dialog says so when a sign-in fails with `redirect_uri_mismatch`.

### Zoom

**A Server-to-Server OAuth app in each community's Zoom account**, as today ([zoom.md](zoom.md#setup)). It cannot be published, needs no Marketplace review, and keeps no refresh token: jason stores the account id, client id, and secret, and asks for a one-hour token when it needs one. A published general app would need Marketplace review and a rotating 90-day refresh token per account; not for now.

| Step | The administrator, in Zoom's App Marketplace | jason checks |
|---|---|---|
| 1. The app | Develop → Build app → **Server-to-Server OAuth**, by the account owner or an admin with the permission | — |
| 2. Scopes | The `:admin` granular scopes for the capabilities on: list meetings, past meetings and instances, participants; list recordings and the recording content; meeting summaries; write meeting only for hearings. Zoom renames scopes, so the dialog lists them by purpose | a token's scopes against the asked |
| 3. Activate | Activate the app | — |
| 4. Into the vault | account id, client id, client secret, through `jason integrations import zoom --community C` (prompts for the secret at the terminal, never echoed) or the dialog's secure entry | a token is issued and one meeting is listed |

Participants and AI summaries need a paid plan; the check says which capabilities the plan allows.

### PayHOA

No public API and no published limit: jason uses PayHOA's own web endpoints with a member's sign-in. The vault entry holds the username, password, and TOTP seed; the organization id comes from the profile. The check signs in and reads the organization's name. Bulk writes keep their own pace (`batches.Pace`, which reads PayHOA's `x-ratelimit-remaining`) and their person's `--yes`.

## Defaults from rate limits

Each integration declares its limits, a default cadence, a **floor** (the fastest an administrator may set), and `stale_after` (about two to three times the cadence, which finally gives the Status screen its threshold). Published figures were read on 2026-10-05; Google moved Drive and Gmail to per-minute quota units on May 1, 2026.

| Source | Published limit | Default cadence | Floor | Stale after |
|---|---|---|---|---|
| Gmail (`history.list`, 2 units) | 6,000 units a minute per user; 1,200,000 per project | every 10 min, 07:00–22:00; hourly overnight | 2 min | 1 h |
| Drive (`changes.list` from a saved token; a full list costs 100 units) | 325,000 units a minute per user; 1,000,000 per project | every 15 min by day, hourly overnight; a full reconcile weekly | 5 min | 2 h |
| Calendar (`syncToken`) | 600 requests a minute per user; 10,000 per project | every 30 min | 5 min | 3 h |
| Sheets (the board's register) | 60 reads and 60 writes a minute per user | hourly, and after a write | 15 min | 1 d |
| Tasks | 50,000 a day per project | hourly | 15 min | 1 d |
| Docs | 300 reads, 60 writes a minute per user | on demand | — | — |
| Vault | 20 exports in progress per organization | on demand | — | — |
| Zoom (meetings, recordings, summaries) | by plan: Pro 30/20/10 requests a second for light/medium/heavy, 10 a minute resource-intensive, 30,000 a day for heavy | daily at 03:00, and two hours after each scheduled board meeting | 1 h | 2 d |
| PayHOA catalog, transactions, requests | none published | nightly 02:00 | 6 h | 2 d |
| PayHOA ledger, budget, reconciliations, reports | none published | weekly, and the 5th of each month | 1 d | 9 d |
| Utilities, vendor portals | none published | weekly, and near each bill date | 1 d | 9 d |
| County tax, secured roll | none published | monthly; daily during the installment windows | 1 d | 35 d |

**An undocumented service is read politely:** one request at a time, about a second apart with jitter, a descriptive user agent, `Retry-After` honored, backoff on 429 and 5xx up to 32 to 64 seconds. These are defaults for the board or the administrator to adopt; a community can read less often, never faster than the floor.

## Commands

| Command | What it does |
|---|---|
| `jason integrations list [--community C \| --instance]` | each integration: connected or not, account, capabilities, last check, schedule, never a value |
| `jason integrations check KEY [--community C]` | runs the integration's check |
| `jason integrations import KEY FILE --community C [--yes] [--delete-file]` | moves a provider's credential file into the vault under the community's path; prints nothing secret |
| `jason integrations connect KEY --community C [--interactive]` | runs the sign-in (a browser for OAuth; a hidden prompt for a password) |
| `jason integrations disconnect KEY --community C --yes --by NAME` | revokes, deletes the vault entry, pauses the schedules, logs it |
| `jason vault status` | the backend, whether it answers, the paths per community (names only) |
| `jason vault migrate [--yes]` | copies today's `.env`-named Keeper records under the new vault paths for the active community; `.env` then keeps only the vault's own login |

## Build order

1. The `Integration` registry in code and `Connection` rows in each community's data (`data/<profile>/integrations.json`), read by the Status screen.
2. The `SecretStore` interface with the Keeper backend, vault paths, and `jason vault migrate`. Per-community lookups for Google, Zoom, PayHOA, and the portals.
3. Google Workspace as a Web client per community, with the browser sign-in from the console and tokens by account.
4. The console's dialogs ([handoff](console/handoff-instance-and-integrations.md)), each over `jason integrations`.
5. Later, with containerization: the backend swap (SSM or Secrets Manager; OpenBao off AWS).

## Open decisions

1. Accept a Cloud project per community (recommended), or budget for one verified jason app and its yearly CASA?
2. Support Gmail-only communities (unverified External app, a warning screen, under 100 users)?
3. The self-host VM: EC2 with an instance role (needed for SSM), or OpenBao?
4. Keeper: the dev backend only, or the self-host backend through Keeper Secrets Manager (which ends the 30-day logout for a daemon)?
5. Ask Google whether admin-trusted clients cover a service used by many organizations?
6. The default cadences above.

## Sources

Read 2026-10-05: Google's "When is verification not needed", restricted-scope verification, unverified apps, Using OAuth 2.0 (seven-day Testing tokens, the 100-token limit, expiry), OAuth best practices, Authorize unverified third-party apps, Marketplace consent configuration, service-account best practices; Google's Drive, Gmail, Sheets, Docs, Calendar, Tasks, Vault limits; AWS Secrets Manager, KMS, and Parameter Store pricing and tiers, and AWS's SaaS isolation with ABAC; AWS re:Post on Lightsail credentials; OpenBao's namespaces, releases, and static seal; Vault editions and the AppRole pattern; Infisical pricing and machine identities; Keeper Secrets Manager, its one-time token and Python SDK; 1Password service accounts and limits; Doppler pricing; Zoom S2S OAuth, OAuth, distribution, and rate limits; RFC 9700, RFC 6585, RFC 9110; CASA pricing (third party). Not verified: Infisical's self-hosted audit limits, KSM and 1Password per-seat prices, each scope's restricted class against Google's list, the admin-trusted exemption across organizations, OpenBao's static seal on native Windows.
