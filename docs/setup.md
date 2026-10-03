# Setup

jason runs on Windows from a checkout at `D:\code\jason`, beside its sibling packages (`D:\code\payhoa`, `D:\code\smud`, `D:\code\i-doxs`). Credentials live in Keeper; `.env` holds only record UIDs and paths.

## Install

```bash
cd D:\code\jason
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e D:\code\payhoa
pip install -e D:\code\smud
pip install -e D:\code\i-doxs
pip install -e ".[dev]"
cp .env.example .env
```

Optional extras:
- `pip install -e ".[mcp]"`: the local catalog server, `jason-mcp` ([mcp.md](mcp.md)).
- `pip install -e ".[charts]"`: SVG charts in the Markdown reports (matplotlib).
- `pip install -e ".[models]"`: the hosted model reader for scanned instruments (needs `ANTHROPIC_API_KEY`).

## `.env`

```
keeper_username = "you@example.com"
payhoa_record_uid = "YOUR_PAYHOA_RECORD_UID"
smud_record_uid = "YOUR_SMUD_RECORD_UID"
idoxs_record_uid = "YOUR_IDOXS_RECORD_UID"
```

Optional settings:
- **Keeper:** `keeper_password`, `keeper_config`.
- **PayHOA:** `payhoa_org_id`.
- **Bill stores:** `smud_db`, `smud_bills_dir`, `idoxs_db`, `idoxs_bills_dir`.
- **Google:** `google_oauth_record_uid`, `google_sheets_spreadsheet_id`, `google_notebook_url`, and, optionally, `google_signin_record_uid` for a separate console sign-in client ([step 5](#5-console-sign-in-jason-web)).
- **AnythingLLM:** `anythingllm_record_uid`, a Keeper login record whose password field is the AnythingLLM API key. `jason anythingllm --store-key` creates it from a key in `.env` or `ANYTHINGLLM_API_KEY`.
- **Law library:** `lawlibrary_home`, the lawlibrary checkout (default `../lawlibrary`).

Other services keep their own Keeper records, named in `.env`:
- `postscanmail_record_uid` (the mailbox);
- `zoom_record_uid` (a Server-to-Server OAuth app; `jason zoom --store-app` creates it);
- `accela_record_uid` (the City's permit portal);
- one `<key>_record_uid` per vendor portal (for example `proactive_record_uid`).

Never commit `.env`, `secrets/`, HAR captures, or anything under `data/`.

## Keeper login

Non-interactive commands never prompt for a password, because they would hang an agent. Run the login once in a real terminal:

```bash
jason login
```

It updates `%USERPROFILE%\.keeper\keeper-config.json` with the device token and the stored master password, which later runs use with no prompt. When the login is missing, jason fails fast with `KeeperAuthRequired` and says to run `jason login`.

## Google Workspace

jason signs in as a Workspace user (SSO). The OAuth client's id and secret live in a Keeper record. The refresh token from the first browser sign-in is kept in `secrets/google-token.json`. Google Photos, Vault, and Tasks each keep their own token beside it, so adding one never asks the others to consent again. Which scopes are asked for is in `jason.google.scopes`.

### 1. The Cloud project and APIs

In the [Google Cloud Console](https://console.cloud.google.com/), select or create the project, and enable each API jason uses under **APIs & Services → Library**: Sheets, Drive, Docs, Gmail, Calendar, Drive Activity, Forms, Tasks, Photos Picker and Library, and Vault. Enabling an API does not grant a scope; scopes are granted when a person signs in.

### 2. The OAuth client

1. Open **APIs & Services → OAuth consent screen** (the Google Auth platform). For a project in the Workspace organization, set the user type to **Internal**: only people in the organization can sign in.
2. Set the app name to `jason` and the support email to a Workspace address. Add the scopes in `jason.google.scopes`.
3. Under **Credentials**, choose **Create credentials → OAuth client ID**, with the application type **Desktop app** and the name `jason`. Download the JSON.

### 3. Store the client in Keeper

1. Create a **Login** record titled `jason Google OAuth`. Add custom fields labeled exactly `client_id` and `client_secret` (hidden), and paste the values. Delete the downloaded JSON; never commit it or paste it into `.env`.
2. Put the record UID in `.env` as `google_oauth_record_uid`.

Do not use Keeper's JSON import on the Google download: it expects Keeper's record schema.

### 4. Sign in once

Run any Google command once with `--interactive`, for example:

```bash
jason drive --sync --interactive
```

The first call with `--interactive` opens a browser at `http://127.0.0.1` for one sign-in and writes the refresh token. Later runs reuse it and never open a browser. A missing or rejected token raises `GoogleAuthRequired` at once in an unattended run. A new scope (a capability added later) asks for one more consent the same way. `jason photos --login --interactive` and `jason vault --interactive` do the same for their own tokens.

New Google Sites has no content API. The published site is a Drive file, so Drive can move or share it, but not edit its pages ([mystique-site.md](mystique-site.md)). The consumer NotebookLM at notebook.google.com has no API that jason can query.

### 5. Console sign-in (jason-web)

With this step, officers can sign in to the console (`jason-web`) with their Workspace accounts. Each step a signed-in officer takes then goes on the record under that officer's own name, not a name picked from a list. Sign-in asks Google for `openid email profile` and nothing else: it only learns who the person is. jason-web never calls a Google API in the person's name.

How it works: jason-web runs OpenID Connect's authorization-code flow on the server, with PKCE, `state`, and `nonce` ([Google's OpenID Connect guide](https://developers.google.com/identity/openid-connect/openid-connect)). The browser goes to Google and comes back to `/auth/google/callback`. jason-web then trades the code for an ID token directly with Google, using the client secret. No Google script is loaded into the page, and no Google token is kept.

1. **The client: nothing to do.** jason-web signs people in with jason's own Desktop client, the Keeper record from step 3 (`google_oauth_record_uid`). Google lets a Desktop client return to any loopback address and port with nothing registered in the console ([Google's loopback guide](https://developers.google.com/identity/protocols/oauth2/native-app#redirect-uri_loopback)), and jason-web listens on loopback. The consent screen from step 2 applies too: with the user type **Internal**, only accounts in the association's Workspace organization can sign in at all. jason-web reads the Keeper record without a prompt, so `jason login` must have been run once ([Keeper login](#keeper-login)).
2. **The roster.** Add each officer's Google account address to their row in the private officers file (`data/spec/officers.json`, or `data/spec/<profile>/officers.json`; [Private facts](#private-facts)). Use the address they sign in with:

   ```json
   [{"role": "treasurer", "name": "Pat Example", "email": "treasurer@example.org"}]
   ```

   A row without `email` cannot sign in. A shared role account (such as the treasurer's address) signs in as whoever holds that seat on the roster. Who holds a seat is the board's record, so update the roster when a seat changes hands.
3. **Start it.** Run `jason-web` to offer sign-in beside the sample picker, or `jason-web --require-sign-in` to refuse every write until an officer signs in. jason-web says at startup which client it signs in with. **Sign in with Google** appears at the top of the console. After sign-in, the header shows the officer's name and a **Sign out** button.

**Optional: a Web application client.** You need one only to serve the console on a name other than loopback, which needs HTTPS and is out of scope for now (below). You also need one if Google ever refuses the Desktop client's return address with `redirect_uri_mismatch`. Google's guide names `http://127.0.0.1:port` for Desktop clients and is silent on a path after the port, but Google accepted `http://127.0.0.1:8080/auth/google/callback` from jason's Desktop client when this was first tried (October 2026).
1. In the Cloud console, open **Google Auth Platform → Clients → Create client**, with the type **Web application** and the name `jason console`.
2. Under **Authorized redirect URIs**, add the exact addresses jason-web answers on, followed by `/auth/google/callback`. For example:
   - `http://127.0.0.1:8080/auth/google/callback`
   - `http://localhost:8080/auth/google/callback`

   Plain `http` is allowed only for loopback; any other host needs `https`. Leave **Authorized JavaScript origins** empty.
3. Copy the client ID and secret straight into a new Keeper Login record titled `jason Google sign-in`, with custom fields `client_id` and `client_secret` (hidden). Newer projects may show the secret only once.
4. Put the record's UID in `.env` as `google_signin_record_uid`. When it is set, it takes the place of the Desktop client.

A new redirect URI can take from five minutes to a few hours to take effect.

If the Cloud project is not in the Workspace organization, its user type can only be **External**. Keep the app in **Testing** and list the officers' addresses as test users (at most 100). `openid`, `email`, and `profile` are not sensitive scopes, so no verification is needed either way.

**What jason-web checks before it lets anyone in:**
- the `state` it sent comes back, within ten minutes;
- the ID token's `iss` is Google, its `aud` is this client, it has not expired, and it carries the `nonce` jason-web sent;
- `email_verified` is true;
- when the profile names the association's email domains (`Community.email_domains`), the token's `hd` claim is one of them. Google's own advice is that the `hd` parameter sent to Google is only a hint for the account chooser; the claim is what counts;
- the email matches exactly one officer on the roster.

Sign-in grants what the roster grants and nothing more: what a person may approve is still `Officer.approves`.

**While an officer is signed in:**
- **The record uses their name.** A write's `by` must be the signed-in officer's name, and an empty `by` is filled with it. Approval steps record `via: console:google` in the audit log.
- **The session has limits.** It is a signed, HttpOnly cookie that lasts twelve hours at most. Restarting jason-web signs everyone out. An officer taken off the roster is signed out at their next write.
- **Sign-ins are logged.** Each sign-in, refusal, and sign-out is a line in `data/web/sign-ins.jsonl`.

**When it goes wrong:**
- **`redirect_uri_mismatch`.**
  - With the Desktop client: open the console at `http://127.0.0.1:8080` rather than `localhost`. If Google still refuses, set up the Web client above.
  - With the Web client: the console was opened at an address the client does not list. Add that exact address.
- **`org_internal` or "access blocked":** the account is outside the Workspace organization.
- **"not an officer's account":** the address is not on the roster (step 2).
- **"not an account of the association's Google Workspace":** the account's domain is not one of `Community.email_domains`.
- **"could not read its client":** run `jason login`, and check that the Keeper record has `client_id` and `client_secret`.

The console still listens on loopback only. Serving it beyond this machine needs HTTPS and the board's written policy on who may see what ([console/security-and-privacy.md](console/security-and-privacy.md)).

## Local AI

jason's local models run on Ollama (`qwen3.6:27b` for OCR, classification, and extraction; `qwen3-embedding:8b` as the embedder), shared with AnythingLLM Desktop. `jason local-ai` reports the stack. A model job holds jason's GPU lock and runs a preflight that fails fast on the CPU or when Windows is short of commit charge. A system-managed page file is often too small; a fixed 32 to 64 GB page file is the fix ([document-tools.md](document-tools.md)).

## Using jason from Python

```python
from datetime import date
from jason import Jason

with Jason() as agent:
    payhoa = agent.payhoa()
    bills = agent.find_bills(amount_cents=6120, around=date(2026, 7, 1))
    report = agent.sync_bills(dry_run=True)
    drive = agent.drive()            # interactive=False: fails fast without a token
```

A Keeper record for the City's i-doxs portal answers its security questions from custom fields whose labels appear in the question text (for example `pet`, `food`, `team`).

## Private facts

The association's private facts (account numbers, people's names and contacts, settlement figures, which units are rented) are each profile's own, under `data/spec/`, which is never checked in: `data/spec/<profile>.json` holds onboarding's answers, and `data/spec/<profile>/<topic>.json` one file per topic (`bank_accounts`, `utility_accounts`, `cases`, `holds`, `senders`). The specification reads them through `jason.community.private`. A checkout without them still runs, with those facts absent. The default profile's topics kept at the older `data/spec/<topic>.json` are still read for it alone; `jason spec` shows where each is read from, and `jason spec --migrate` (a dry run unless `--yes`) copies them into `data/spec/<profile>/` after a backup. The tests read made-up facts from `tests/fixtures/spec/<profile>/`.

`JASON_DATA_DIR` (environment or `.env`) moves the data root from `data/` beside the checkout; another profile's stores are in `<root>/<profile>/`, and the private facts in `<root>/spec/` ([profiles.md](profiles.md#each-profiles-data)). The Mystique-specific research notes (`mystique/notes/`) are private too.
