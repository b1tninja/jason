# Handoff: instance administration, community integrations, and their setup dialogs

For a design pass on the screens an **administrator** uses to run jason and to connect each community's services. The behaviour is settled by [integrations-design.md](../integrations-design.md) (integrations, connections, the vault, the defaults from rate limits) and [scheduler-daemon-design.md](../scheduler-daemon-design.md) (the scheduler, the daemon, cadences). Nothing here is built; the component names are proposals the build takes from the design's results. The corrections in [handoff-reconciliation.md](handoff-reconciliation.md) and its third and fourth cuts still stand.

## Who and where

- **The administrator** is one of jason's admins (`data/access/admins.json`), signed in as themselves. They hold no office and approve nothing; they configure. Every screen here is theirs alone, refused (403) to anyone else, never in the owner view, and never while an admin views the console as someone else (`--dev`).
- **A community's officers** see their community's integrations as read-only states on Status and Setup, never the configuration.
- **Two levels:**
  - **The instance:** the installation itself. Its integrations, the vault, the service (web, worker, scheduler), the communities it serves, its administrators and managers.
  - **A community:** one profile. Its integrations, each a connection with its own account, capabilities, credential, schedule, and state.

## The screens

| Screen | Route | What it is |
|---|---|---|
| **Instance** | `#/instance` | The administrator's overview: the service's health, the vault's backend and whether it answers, each community with its integrations' states, and what needs a person. Extends today's Status screen (`#/status`, which stays the per-community view of sources) |
| **Instance → Communities** | `#/instance/communities` | Each community: its profile, its data folder's size, its integrations as a row of states, its last activity. "Set up a new community" starts onboarding (`jason onboard --new`) |
| **Instance → Integrations** | `#/instance/integrations` | The instance-wide ones: the vault, the law library, local models, county caches, public vendor portals, the installation's sign-in client, Bedrock if used |
| **Instance → Service** | `#/instance/service` | The process (`jason serve`), each community's lease and heartbeat, each job lane's current job, the next scheduled runs, recent failures, how it is started (Task Scheduler, a service wrapper, a container) |
| **Instance → Schedules** | `#/instance/schedules` | Every community's cadences in one table, with each one's default, floor, window, where it came from, and its next run |
| **Instance → People** | `#/instance/people` | The administrators and the managers with their portfolios, read-only, with the commands that change them |
| **Community → Integrations** | `#/setup/integrations` (a tab of Setup) | The community's connections as cards, each opening its setup dialog |

## The components

Six of these are defined, with their data and every state, in [handoff-admin-components.md](handoff-admin-components.md): `ServiceStatus`, `VaultStatus`, `IntegrationCard`, `ConnectionChip`, `CapabilityList`, `CadenceTable`. **There, not here:** where the two pages differ, that page wins, and the rows below keep only what this page added. The rest (`CommunityRow`, `ConnectDialog`, `StepCheck`, `RedirectUri`, `SecretDrop`, `FileDrop`, `DisconnectConfirm`) are defined here, and `PersonSteps` in [handoff-held-setup-roster.md](handoff-held-setup-roster.md#personsteps) (its single step is the `TerminalStep` of the admin page).

| Component | Where | States to design |
|---|---|---|
| `ServiceStatus` (defined in the admin page) | Instance, Service | running (since, by Task Scheduler / a service / a container); a lane busy (its job, elapsed); a stale heartbeat (the process may be hung); stopped; a community's lease held by another host |
| `VaultStatus` (defined in the admin page) | Instance, Integrations | the backend (Keeper on this PC; later SSM, Secrets Manager, OpenBao) and whether it answers; "Keeper needs a sign-in at the terminal" with `jason login`; Keeper's 30-day logout coming (day 25 on); paths per community (names only, never a value) |
| `CommunityRow` | Communities | each community with its integration chips; one needing a sign-in; one never set up; one whose data folder is on another host |
| `IntegrationCard` (defined in the admin page) | Community → Integrations, Instance → Integrations | not set up; needs sign-in (who must, and the step); connected (account, capabilities, last check, next read); failing (the error's plain words and the fix); paused (by whom, why); a capability off |
| `ConnectionChip` (defined in the admin page) | Communities, Status, Setup | the five states as a word and a glyph: not set up, needs sign-in, connected, failing, paused |
| `ConnectDialog` | from an `IntegrationCard` | a stepper over the integration's setup steps (below): each step's instructions, what the administrator does in the provider's console, and what jason then checks; resumable; shows which step failed and why |
| `StepCheck` | inside `ConnectDialog` | not yet; checking; passed (what jason read, with a `read` seal); failed (the provider's error in plain words, the likely cause, the step to revisit); cannot check (a step only the administrator can confirm) |
| `CapabilityList` (defined in the admin page) | `ConnectDialog`, `IntegrationCard` | each capability a switch, read-only ones first, write ones marked "writes"; the scopes or permissions each asks for, in the provider's own names; turning a write on asks for one more consent; a capability the plan doesn't allow (Zoom participants without a paid plan) |
| `RedirectUri` | Google and sign-in dialogs | the exact address to paste, copyable; the loopback form on this PC and the HTTPS form when hosted; "can take from five minutes to a few hours to take effect" |
| `SecretDrop` | `ConnectDialog` | a **write-only** entry that passes a value straight to the vault and never shows it again (below); "set" with when and by whom; "replace"; unavailable on this PC (the terminal command instead) |
| `FileDrop` | Google, sign-in dialogs | a provider's credential file (Google's client JSON) going straight into the vault; the file is not kept and its contents never shown |
| `CadenceTable` (defined in the admin page, with `ScheduleRow` and `CadenceEditor`) | Schedules, `IntegrationCard` | each source's cadence, window, default, floor, source (the integration's default, an admin's change, the board's policy), next run, last result; a change below the floor refused with the reason; paused; a scheduled write marked and showing who confirmed it |
| `DisconnectConfirm` | `IntegrationCard` | what disconnecting does (revoke the provider's token, delete the vault entry, pause the schedules), typed confirmation, recorded by name |
| `PersonSteps` | dialogs, Service | the steps only a person takes, in order, each with who and the command ([handoff-held-setup-roster.md](handoff-held-setup-roster.md)) |

Use the built marks: `Seal` for what jason checked, `Stamp` never (connecting is not a decision), `Glyph` beside every state word, `Command` for every terminal step, `Confirm` for every write.

## Secrets in the console

The rule: **the console never displays, logs, or stores a secret.** Two ways a secret gets into the vault:
- **On this PC (Keeper backend):** the dialog shows the terminal command (`jason integrations import`, `jason integrations connect`), which prompts with hidden input or moves the downloaded file into Keeper and deletes it. The dialog then checks.
- **Hosted (a later backend):** `SecretDrop` and `FileDrop` are write-only: the value goes over HTTPS from the field straight to the vault's put, is never returned, never written to a log or the audit trail (only "set, by whom, when"), and the field clears. They are offered only when the backend accepts writes from the service and the console is served over HTTPS.

Never a password field that reveals, never a "copy secret" button, never a secret in a URL, a toast, or an error message.

## The setup dialogs

Each dialog's steps are the integration's own (`setup steps` in the registry), from the guides already written. A step names where in the provider's console to go, what to set, and what jason checks afterwards. Screenshots of the provider's console go out of date; the dialog names the menu path in words and links to the provider's page.

### Google Workspace

From [setup.md](../setup.md#google-workspace), changed to a **Web application** client per community (a hosted jason cannot receive a Desktop client's loopback redirect):

| Step | The administrator does | jason checks |
|---|---|---|
| 1. Project | Google Cloud Console → create a project **inside the community's Workspace organization** | — |
| 2. APIs | APIs & Services → Library: enable the APIs for the capabilities switched on (Drive, Docs, Sheets, Gmail, Calendar, Drive Activity, Forms, Tasks, Photos Picker and Library, Vault). "Enabling an API grants nothing; scopes are granted at sign-in." | at sign-in, a call to each; a disabled API names itself |
| 3. Branding | Google Auth Platform → Branding: the app name (`jason`, or the community's choice), a support email at the community's domain; logo optional | — |
| 4. Audience | User type **Internal** (only the organization's accounts can sign in; no Google verification needed) | the token's domain is the community's |
| 5. Data access | Add the scopes the `CapabilityList` shows, read-only first | granted scopes against those asked |
| 6. The client | Clients → Create client → **Web application**; paste the `RedirectUri`; leave JavaScript origins empty; download the JSON (newer projects show the secret only then) | — |
| 7. Into the vault | `FileDrop` hosted, or `jason integrations import google-workspace <file> --community C --yes --delete-file` on this PC | the vault entry is set |
| 8. Sign in | "Sign in with Google" as the account jason reads with: its own mailbox (recommended), or the signed-in officer | a Drive list and the Gmail profile read |
| 9. jason's mailbox | Add the account to every Google Group with "Each email" delivery; aliases as groups ([setup.md](../setup.md#6-jasons-mailbox)) | the groups the mailbox is in |

**Errors in plain words**, from setup.md's troubleshooting: `redirect_uri_mismatch` (the address the console was opened at is not on the client; or the new URI hasn't taken effect yet); `org_internal` / "access blocked" (an account outside the organization); a disabled API (which one, and the Library link); the 7-day expiry of a "Testing" app (never use Testing for Drive or Gmail).

**A Gmail-only community** (no Workspace) is not supported (decided 2026-10-05): step 1 says a community needs Google Workspace, and the dialog stops there for a consumer account. **The alternatives** (one verified jason app; admin-trusted; domain-wide delegation) are not offered in the dialog: a Cloud project per community is decided (2026-10-05).

### Console sign-in

The same project may carry it: a second Web client, scopes `openid email profile` only, the `RedirectUri` for `/auth/google/callback`, the domains it accepts, the button's label. Then the roster (who may sign in), shown as the People screen's read-only list with the board-roster question.

### Zoom

From [zoom.md](../zoom.md#setup):

| Step | The administrator does | jason checks |
|---|---|---|
| 1. The app | App Marketplace → Develop → Build app → **Server-to-Server OAuth**, by the account owner or an admin with the permission | — |
| 2. Scopes | The `:admin` granular scopes for the capabilities on, listed by purpose (Zoom renames scopes): meetings, past meetings and instances, participants; recordings and their content; meeting summaries; write meeting only for hearings | the token's scopes |
| 3. Activate | Activate the app | — |
| 4. Into the vault | account id, client id, client secret: `SecretDrop` hosted, or `jason integrations import zoom --community C` on this PC | a token is issued; one meeting is listed |

The check says which capabilities the plan allows (participants and AI summaries need a paid plan).

### PayHOA

| Step | The administrator does | jason checks |
|---|---|---|
| 1. A sign-in | A PayHOA member account jason signs in with (who it is matters: what it can see is what jason can read) | — |
| 2. Into the vault | username, password, and the authenticator's setup key (TOTP seed) | — |
| 3. The organization | the organization id from the profile, confirmed | jason signs in and reads the organization's name |
| 4. Writes | bulk writes (owner information, broadcasts) stay off unless switched on, and each still needs a person's `--yes` | — |

### The others

PostScanMail (an API key), the utilities (a username and password; the City's billing adds security questions), and each signed-in vendor portal (a login per portal, named by the profile's portal row) each get a short dialog: the entry into the vault, then a read.

## Schedules

`CadenceTable` rows come from each integration's defaults ([integrations-design.md](../integrations-design.md#defaults-from-rate-limits)):
- the default, the floor (the fastest allowed, from the published or polite rate), and `stale after` (which the Status screen uses);
- an administrator's change records who and when, and is refused below the floor;
- "Restore defaults" per row and per community;
- a schedule that writes is marked, shows who confirmed it, and exists only if the board allows scheduled writes;
- a connection that needs a sign-in shows its schedules paused, with the reason.

## The service

`ServiceStatus` shows `jason daemon status`: the process and how it was started, each community's lease (holder, heartbeat age), each lane's job, the next five runs, and the last failures, with `jason serve --install-task` and `jason daemon stop` as commands. Nothing on the screen starts or stops the service; that is a terminal step.

## As built (checked against the code, 2026-10-05)

This page's first line ("Nothing here is built") is out of date. The parts behind it are built and [handoff-admin-components.md](handoff-admin-components.md) gives each one's real data, its states, and the corrections; this page keeps the screens, the setup dialogs, and "Secrets in the console".

| This page's screen | What exists | What does not |
|---|---|---|
| Instance (`#/instance`) | the Status screen (`#/status`, built, admin only) with its sources and standing; `jason daemon status --json` for the service | the overview itself; the three routes below are built (`instance-service`, `instance-integrations`, `instance-schedules`) |
| Communities (`#/instance/communities`) | `#/communities` lists the profiles (`communities` loader) | each community's integration row of chips, data folder size, last activity |
| Integrations (instance and community) | `jason integrations list [--instance] --json`; `GET /api/instance-integrations[?scope=instance][&vault=1]` | the cards |
| Service | `jason daemon status --json` (`jason.serve.status`), `jason serve --install-task`, `jason daemon stop`; `GET /api/instance-service` | `ServiceStatus` |
| Schedules | `jason cadence --json`, with `--every`, `--cron`, `--window`, `--pause`, `--resume`, `--restore`, `--run-now`; `GET /api/instance-schedules` | no write from the console |
| People | `#/people` (offices, terms, jason's admins, the managers with portfolios), read-only | the Instance route (the same list under another nav group) |
| The setup dialogs | each integration's `setup_steps` in the registry (`Step`: `title`, `admin_does`, `jason_checks`; 37 across the integrations) | `ConnectDialog`, `StepCheck`, `RedirectUri`, `SecretDrop`, `FileDrop`, `DisconnectConfirm`; the steps are not in `integrations list --json` |

### The three routes (built 2026-10-10; `jason.web.extra.instance`)

- **Keys, not paths.** The loaders are `instance-service`, `instance-integrations`, and `instance-schedules` (`GET /api/<key>`), not `/api/instance/*`.
- **Who.** One of jason's admins as themselves (401 with no sign-in, 403 for anyone else and while viewing as someone else); never the owner view; read only.
- **Disk only.** Heartbeat files and locks, the connections' stored rows, the stores' own stamps, and the schedules table opened read-only. No Google, PayHOA, Keeper, or network, and nothing written. A community whose scheduler has not run is `seeded: false` with the command that seeds it (`jason cadence`); the loader never seeds.
- **Service** is each community's judged heartbeat: `none`, `running`, `draining`, `stale` (older than `staleAfterSeconds`, 90, the beat every 30), `stopped`; `alive`; the worker lock; a drain request; the lanes; the next runs.
- **Integrations** are `jason integrations list --json`'s rows: names, states, the vault *path*, whether a credential is set, never a value. The vault is asked only with `?vault=1` (names only, non-interactive); without it a credential held only in the vault reads "not set" and `vault.asked` says the vault was not asked.
- **Schedules** are `jason cadence --json`'s rows for every community: cadence, window, floor, default, where the setting came from, adoption, and next run.

### Where this page's text differed from the code (the code wins)

- **The commands in "Secrets in the console".** `jason integrations import` and `jason integrations connect` do not exist: `jason integrations` has `list` and `check` only. Two registry steps (Google Workspace's and Zoom's "Into the vault") still name `jason integrations import`. Credentials reach the vault today by `.env` record uids read through Keeper and moved by `jason vault migrate --yes` (a plan without `--yes`). The `SecretDrop` and `FileDrop` rules stand; their terminal alternative does not exist yet.
- **The service's lease and heartbeat** (`ServiceStatus`): one heartbeat file per community and a worker lock (`workerLock`: pid and since); "a community's lease held by another host" is `refused` ("another worker holds this community") and the lock's holder.
- **The five connection states** are `not set up`, `needs sign-in`, `connected`, `failing`, `paused`, exactly (`ConnectionState`). A setting that is only named in `.env` counts as "set" and a vault path as "set" when the vault answers; a credential set and never read is `not set up`.
- **Google's nine steps, Zoom's four, PayHOA's four** are in the registry in those counts. The registry's words are the source for each step's text; this page's tables are the summary.

## What must not change

- No secret displayed, logged, stored, or put in a URL by the console.
- An integration counts as connected only after jason's read succeeds.
- Disconnecting revokes and deletes; it is as visible as connecting, recorded by name.
- A sign-in failure pauses, never retries on a timer.
- No cadence faster than the integration's floor.
- Administrators configure; they approve nothing on a community's behalf.
- The design project may use the association's real details; what comes back into the repo is general.

## Decisions that are the design's

1. Whether Instance is its own nav group or Status grows into it.
2. How `ConnectDialog` resumes: from the step that failed, or from the start with completed steps collapsed.
3. How a long provider-console step (Google's nine) stays readable: one step per page, or a checklist with expanding steps.
4. How the five connection states read at a glance in a community row.

## Open (the build's or a person's)

- The secret manager behind the vault when hosted, and the self-host VM ([integrations-design.md](../integrations-design.md#open-decisions)).
- Whether the board allows scheduled writes.
- The default cadences.
