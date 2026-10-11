# Setting up a community's Google Workspace

Each community runs jason against **its own** Google Workspace: its own Google Cloud project, its own OAuth client, and its own refresh tokens, all kept in that community's vault paths (`jason/community/<profile>/google-workspace/...`). Nothing is read from another community's paths, and the developer environment's `.env` record is only a deprecated fallback. A community's administrator does the steps below **once**; after that nobody is asked to consent again unless a token ends (see [What ends a token](#what-ends-a-token)).

Companions: [setup.md](setup.md) (Keeper and the other services), [integrations-design.md](integrations-design.md) (the vault, "Google tokens in the vault"), and the commands `jason google status|scopes|setup|adopt-installation-record|sign-in`.

## What is stored where

| What | Vault path (community `<profile>`) | Fields |
|---|---|---|
| The OAuth client | `jason/community/<profile>/google-workspace/oauth-client` | `client_id`, `client_secret`, `project_id` |
| A refresh token | `jason/community/<profile>/google-workspace/token/<name>` | `refresh_token`, `scopes` |

`<name>` is `drive` (Drive, Docs, Sheets, Gmail, Calendar, Forms and the other Drive-family scopes), `tasks`, `vault` (Google Vault) or `photos`, each its own token so granting a new API never asks the others to consent again. With a vault, a token lives there and **nowhere else on disk**. A profile may pin a different entry name for its client and the Workspace domain it expects (`Community.google_workspace()`); both are shown by `jason google status`.

The client can be downloaded from the Cloud console. **A refresh token cannot**: Google returns it once, in the exchange that follows a person's consent. That is why it is saved the moment it is given, and why `jason google sign-in` exists.

## Steps for the administrator

1. **Create or choose a Google Cloud project** in the Workspace organization at [console.cloud.google.com](https://console.cloud.google.com/). A project the community owns, not a developer's.
2. **Set the OAuth consent screen to Internal** (Google Auth Platform: Audience, user type **Internal**). Internal limits sign-in to people in the organization and its tokens are not subject to the seven-day expiry. Do **not** use External: an External app left in Testing status has refresh tokens that end after seven days, which would ask the administrator to consent again every week.
3. **Enable the APIs** the scopes need (APIs & Services, Library). `jason google scopes` lists every scope with the API it needs; today they are: Google Drive API, Google Docs API, Google Sheets API, Gmail API, Google Calendar API, Drive Activity API, Google Drive Labels API, Google Forms API, Google Tasks API, Google Vault API, Google Photos Picker API and the Photos Library API. Enabling an API grants nothing; scopes are granted when a person consents. Enable only those for features the community uses; a token for an unused name need not be created.
4. **Create a Desktop app OAuth client** (Google Auth Platform, Clients, Create client, application type **Desktop app**) and **download its JSON** (`client_secret_*.json`). Desktop is the type that returns to a loopback address with nothing registered.
5. **Store the client** (a person at a terminal, signed in to Keeper with `jason login`):
   ```bash
   jason google setup --from-file client_secret_XXXX.json          # the plan; writes nothing
   jason google setup --from-file client_secret_XXXX.json --yes
   ```
   The id and secret are never printed. The command is create only: a second run refuses unless `--replace`. Without `--from-file`, `--yes` asks for the id and secret at a hidden prompt. Then delete the downloaded file; never commit it or paste it into `.env`.
6. **Sign in once for Drive** (a person at a browser):
   ```bash
   jason google sign-in --name drive --interactive
   ```
   It lists the scopes it will ask for before the browser opens, then saves the token to the vault. If a token that covers the scopes is already held it says "already signed in" and does nothing (`--again` consents anew).
7. **Sign in for the other tokens when a feature needs them**: `--name tasks`, `--name vault`, `--name photos` (or `--name all`).
8. **Check**: `jason google status` says whether the client is the community's own, where each token is read from, and which scopes are covered or missing. Nothing it prints is a secret.

An installation that still names the developer environment's record (`google_oauth_record_uid` in `.env`) is no longer read by default: a community's client comes from its own vault path. `jason google adopt-installation-record --yes` copies the old record into the community's own path, and `GOOGLE_INSTALLATION_CLIENT=1` turns the fallback back on for an installation that has not moved yet (`jason google status` then says "this is the installation's record, not this community's").

## The 100-token limit

Google allows 100 refresh tokens per Google Account per OAuth client; past that the **oldest silently stops working**. Each consent counts. So jason signs in only when it must, and `sign-in` says so before it opens the browser. Do not sign in repeatedly to "fix" something; check `jason google status` first.

## What ends a token

A refresh token ends when: the person revokes the app; it goes six months unused; the account's password changes while Gmail scopes are in it; more than 100 are issued for the account and client; an administrator's session controls or policy require it; and, only for an **External** app left in Testing, after seven days. When one ends, the next run raises `GoogleAuthRequired` (or Google answers `invalid_grant`). **Sign in again** with `jason google sign-in --name NAME --again --interactive`. Never retry an `invalid_grant`: the token is gone.

## Persistence: a consent is never lost

The token is saved before anything else happens to it. If the vault will not take it (Keeper needs a sign-in, the network is down), it is kept in the local token file rather than lost; `jason google status` and `jason vault status` flag the file, and `jason vault migrate --yes` moves it to the vault and removes the file once the vault holds the same token. Commands read the vault first, so a git worktree or any working directory finds the token without a `secrets/` folder.

## Rotating or revoking

- **Rotate the client secret**: add a new secret in the Cloud console, `jason google setup --from-file NEW.json --replace --yes`, then delete the old secret in the console. Tokens issued to the same client id keep working; if the client id changed, sign in again.
- **Revoke a token**: the account owner removes the app at myaccount.google.com (Security, Third-party access), or the administrator in the Admin console. Then sign in again if the feature is still wanted.
- **Leave a community**: delete the community's entries under `jason/community/<profile>/google-workspace/` in Keeper and revoke the grants; nothing of it exists elsewhere.

## Choosing from a person's own Drive: the Picker's redirect form

Optional, off by default. It lets a board member choose PDFs in **their own** Google Drive (private files and the shared drives they belong to) instead of sharing them with the community's account first. How it works and what it keeps: [google-picker.md](google-picker.md). It uses the console's sign-in **Web application** client, never the Desktop client above, and asks Google for one scope only.

**What to add, and nothing else**

1. **Authorized redirect URI** on the community's Web application client (Google Auth Platform, Clients, the Web client, Authorized redirect URIs), exactly the address the console is opened at plus the path:
   - for the console on this machine at `127.0.0.1:8080`: `http://127.0.0.1:8080/auth/google/pick/callback`
   - for a hosted console: `https://console.example.org/auth/google/pick/callback`

   Google matches the whole value (scheme, case, trailing slash). Plain `http` is allowed only for a localhost address: Google's web-server guide exempts "localhost URIs (including localhost IP address URIs)" from the HTTPS rule; a hosted console needs `https`. The sign-in address (`/auth/google/callback`) stays registered beside it.
2. **Scope** on the consent screen (Google Auth Platform, Data Access): `https://www.googleapis.com/auth/drive.file`. It is non-sensitive (access only to the files a person picks) and the app is Internal, so there is nothing to verify. Do not add `drive`, `drive.readonly`, or an API key: the redirect form needs no script, API key, project number, or JavaScript origin.
3. **Turn it on** for the community: `jason limits --set pick.enabled=on --scope community --reason "..." --by "A. Person"` (or the Limits screen). It is `off` until a person does. `pick.state_minutes` (default 10) is how long a pick may stay open at Google.

Enabling the Google Picker API is **not** needed for the redirect form (it is for the web Picker, which is not built); enabling it does no harm.

### Manual test (a person runs this; nothing in jason has run it against Google)

You need: the console signed in as a board member whose email is on the roster; a Google account in the Workspace with **one PDF in its own My Drive** (not shared with the community's account) and **one PDF in a shared drive** it belongs to; and a Google Doc or a folder to try the refusals.

1. Add the redirect URI and the scope above. Start the console: `jason-web` (it prints the sign-in redirect on start; use the same host and port in step 1). Open `http://127.0.0.1:8080` and sign in with Google.
2. Turn the switch on (step 3 above). `GET /api/session` now says `"pick": {"enabled": true, ...}`.
3. Visit `http://127.0.0.1:8080/auth/google/pick?next=%23%2Fsplit&purpose=split` (or press **Choose from my Google Drive** once the console has the button). Expect Google's consent screen for the app asking for access to the specific Drive files you use with it, then Google's file Picker.
4. Pick the private PDF and the shared-drive PDF (multi-select) and confirm. Expect the browser to return to `http://127.0.0.1:8080/?pick=...#/split`.
5. Read the result once, from the browser's developer console on that page: `fetch('/api/drive/pick/result', {method:'POST', headers:{'Content-Type':'application/json','X-Jason-Token': (await (await fetch('/api/session')).json()).token}, body: JSON.stringify({token: new URLSearchParams(location.search).get('pick')})}).then(r=>r.json()).then(console.log)`. **Expected:** `counts.held` 2 (or `already held` on a repeat), each row with a 64-character `heldId`, pages, size, and "Read once and held. The original in Drive was not changed." Run it again: a 404 (read once).
6. Check on disk under the data folder: `drive-picks/held/<sha>.pdf` and `.json` for each; the JSON has `"via": "picked via Picker"`, your name, a 16-character `driveIdHash`, and no file name or Drive id. `records/history.jsonl` has one `drive-pick` line with counts. No token or code is anywhere.
7. Try the refusals: pick a Google Doc (expect `not_pdf`, "Export it as a PDF in Google"), a folder (`folder`; the Picker may not let you choose one), and a PDF over `fetch.max_bytes` (`too_large`, with the limit's words). Each ends "Nothing was kept."
8. Open a held copy: `POST /api/write/split/new` with `{"act":"open","ref":{"kind":"held","id":"<heldId>"},"by":"<your name>"}` (the console's usual write headers). Expect a draft with the PDF's pages.
9. In Drive, confirm nothing changed: the files' sharing, location, names and last-modified time are as before. In your Google account's security page (third-party apps with account access) the app appears with access to the picked files only.

**What a failure looks like**

| You see | It means |
|---|---|
| Google error `redirect_uri_mismatch` | The redirect URI in step 1 does not match the address bar (host, port, scheme, trailing slash) |
| Google error `invalid_request`, or the Picker never opens | Google does not accept `trigger_onepick` for a Web client, or one of the parameters. That is the spike's answer: stop and report the error page's text (it holds no secret). The fallback is in [google-picker.md](google-picker.md) |
| "did not come back as it was sent" on a small page | Google did not return `state`, the session was lost (a restart signs everyone out), or the pick was opened in another browser |
| "already used, or was not started here" | The callback was opened twice (Back, or a reload) |
| "took too long" | More than `pick.state_minutes` at Google |
| Result `error`: "Google would not give jason access" | The client secret in the vault is wrong, or the code was already used. Nothing was read |
| A row `no_access` for a file you picked | `drive.file` did not extend to that file (a shared-drive file, or one the Picker showed but the token cannot read): note which kind and report it |
| "Choosing from your own Google Drive is off" | `pick.enabled` is off |

**To purge the held copies**: `python -m jason.tasks.drive_pick --purge` lists them; add `--yes` to remove them. Drafts already opened from a held copy keep their own copy in the splitter's store (removed with the draft, `split.draft_days`). To end the app's access in Google: the account's security page, third-party apps, remove the app.

## The console's sign-in is separate

People sign in to the web console (`jason-web`) with a **Web application** client, a different client with registered redirect addresses; it is set up with `jason sign-in` ([setup.md](setup.md), step 5) and is not the Desktop client above. The console's connection dialogs for the Google client and tokens are a later step ([integrations-design.md](integrations-design.md), build order step 3 and 4; [console/handoff-instance-and-integrations.md](console/handoff-instance-and-integrations.md)): they call the same functions as the commands here.
