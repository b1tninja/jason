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

## The console's sign-in is separate

People sign in to the web console (`jason-web`) with a **Web application** client, a different client with registered redirect addresses; it is set up with `jason sign-in` ([setup.md](setup.md), step 5) and is not the Desktop client above. The console's connection dialogs for the Google client and tokens are a later step ([integrations-design.md](integrations-design.md), build order step 3 and 4; [console/handoff-instance-and-integrations.md](console/handoff-instance-and-integrations.md)): they call the same functions as the commands here.
