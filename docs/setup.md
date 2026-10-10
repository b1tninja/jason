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
- **Law library:** `lawlibrary_home`, the lawlibrary checkout (default `../lawlibrary`).

Other services keep their own Keeper records, named in `.env`:
- `postscanmail_record_uid` (the mailbox);
- `zoom_record_uid` (a Server-to-Server OAuth app; `jason zoom --store-app` now puts it at the vault path `zoom/app` instead, and no key is needed);
- `accela_record_uid` (the City's permit portal);
- one `<key>_record_uid` per vendor portal (for example `proactive_record_uid`).

Never commit `.env`, `secrets/`, HAR captures, or anything under `data/`.

## Keeper login

Non-interactive commands never prompt for a password, because they would hang an agent. Run the login once in a real terminal:

```bash
jason login
```

It updates `%USERPROFILE%\.keeper\keeper-config.json` with the device token and the stored master password, which later runs use with no prompt. When the login is missing, jason fails fast with `KeeperAuthRequired` and says to run `jason login`.

### The vault

Credentials are moving from `.env` record UIDs to vault paths, `jason/<scope>/<community or "instance">/<integration>/<name>` ([integrations-design.md](integrations-design.md#the-vault)). In Keeper, an entry is a record titled with its path, in a folder named `jason` at the top of your vault.
- `jason vault status` shows the backend, whether it answers, and which `.env` keys are still read. It never prompts.
- `jason vault migrate` shows the plan. `jason vault migrate --yes`, run in a terminal, copies each record to its path and never overwrites one. The plan and the copy also cover the Google refresh tokens (see Google Workspace below): each local `secrets/google-*token.json` goes to `google-workspace/token/<name>`, and `status` says where each would be read from.

Check the new records in Keeper, then remove the moved `*_record_uid` keys from `.env`. Until then, jason reads the `.env` record and logs the key as deprecated. Every login jason reads (PayHOA, SMUD, i-doxs, Accela, PostScanMail, Zoom, the vendor portals, the Google client, and the console's sign-in clients) tries its vault path first. `jason integrations list` and `jason onboard` count an entry at the path as set; when Keeper wants a sign-in they test `.env` alone and say so.

## Google Workspace

**Each community sets up its own Google Workspace** (its own Cloud project, OAuth client and tokens, in its own vault paths): the steps are in [google-workspace-setup.md](google-workspace-setup.md), and `jason google status` shows where a community stands. The steps below are the short form.

jason signs in as a Workspace user (SSO). The OAuth client's id and secret live in the community's vault entry (`google-workspace/oauth-client`); the installation's `.env` record `google_oauth_record_uid` is a deprecated fallback that `jason google adopt-installation-record` copies in. The refresh token from a browser sign-in is saved in the vault (`jason/community/<profile>/google-workspace/token/drive`) and nowhere else on disk. A command reads the vault first and the file second, so a worktree or any working directory with no `secrets/` folder works once `jason vault migrate --yes` has copied the token (or after the next sign-in). Google Photos, Vault, and Tasks each keep their own token (`token/photos`, `token/vault`, `token/tasks`), so adding one never asks the others to consent again. Which scopes are asked for is in `jason.google.scopes`.

### 1. The Cloud project and APIs

In the [Google Cloud Console](https://console.cloud.google.com/), select or create the project, and enable each API jason uses under **APIs & Services → Library**: Sheets, Drive, Docs, Gmail, Calendar, Drive Activity, Forms, Tasks, Photos Picker and Library, and Vault. Enabling an API does not grant a scope; scopes are granted when a person signs in.

### 2. The OAuth client

1. Open **APIs & Services → OAuth consent screen** (the Google Auth platform). For a project in the Workspace organization, set the user type to **Internal**: only people in the organization can sign in.
2. Set the app name to `jason` and the support email to a Workspace address. Add the scopes in `jason.google.scopes`.
3. Under **Credentials**, choose **Create credentials → OAuth client ID**, with the application type **Desktop app** and the name `jason`. Download the JSON.

### 3. Store the client in the vault

```bash
jason google setup --from-file client_secret_XXXX.json          # the plan; writes nothing
jason google setup --from-file client_secret_XXXX.json --yes     # a person at a terminal
```

This stores `client_id`, `client_secret` and `project_id` at `jason/community/<profile>/google-workspace/oauth-client` (create only; `--replace` overwrites), and never prints them. Delete the downloaded JSON afterwards; never commit it or paste it into `.env`. Do not use Keeper's JSON import on the Google download: it expects Keeper's record schema. An installation that still has the older `google_oauth_record_uid` in `.env` runs `jason google adopt-installation-record --yes` once.

### 4. Sign in once

```bash
jason google sign-in --name drive --interactive
```

The first call opens a browser at `http://127.0.0.1` for one sign-in and saves the refresh token to the vault alone. Any Google command with `--interactive` does the same when it has no token (`jason drive --sync --interactive`). Later runs reuse it and never open a browser. A missing or rejected token raises `GoogleAuthRequired` at once in an unattended run. A new scope (a capability added later) asks for one more consent the same way. `jason photos --login --interactive` and `jason vault --interactive` do the same for their own tokens.

New Google Sites has no content API. The published site is a Drive file, so Drive can move or share it, but not edit its pages ([mystique-site.md](mystique-site.md)). The consumer NotebookLM at notebook.google.com has no API that jason can query.

### 5. Console sign-in (jason-web)

With this step, people sign in to the console (`jason-web`) with their Google Workspace accounts. Each step a signed-in person takes then goes on the record under their own name, not a name picked from a list. Sign-in asks Google for `openid email profile` and nothing else: it only learns who the person is. jason-web never calls a Google API in the person's name.

How it works: jason-web runs OpenID Connect's authorization-code flow on the server, with PKCE, `state`, and `nonce` ([Google's OpenID Connect guide](https://developers.google.com/identity/openid-connect/openid-connect)). The browser goes to Google and comes back to `/auth/google/callback`. jason-web then trades the code for an ID token directly with Google, using the client secret. No Google script is loaded into the page, and no Google token is kept.

**Who signs in, and where it is set up.** Every file here is private, under `data/`, and never checked in.

| Level | What | File |
|---|---|---|
| A community (a profile) | Its officers, with the address each signs in with | `data/spec/<profile>/officers.json` |
| | Its own Google Sign-In: one or more clients from its own Workspace, each with the email domains it accepts | `data/spec/<profile>/sign_in.json` (`Community.sign_in`) |
| jason (the installation) | **Admins**: jason's overall administrators, across every community | `data/access/admins.json` |
| | **Managers**: each manages a portfolio of communities, and is the manager of each one in it | `data/access/managers.json` |
| | The installation's own sign-in clients, such as a management company's Workspace, for admins and managers | `data/access/sign_in.json` |

jason-web offers one button for each client: first the community's, then the installation's. If neither is set up, it uses the `.env` client, `google_signin_record_uid` or else jason's own Desktop client from step 3. Whichever client a person chooses, they must be on this community's roster: its officers, the managers whose portfolio holds it, and jason's admins. An admin holds no office, so being an admin approves nothing; what anyone may approve is still the community's roster. Each client checks its own domains.

1. **A client.** Pick one:
   - **The community's Web client (recommended).** In its Cloud project, open **Google Auth Platform → Clients → Create client**, with the type **Web application**. Under **Authorized redirect URIs**, add the exact addresses jason-web answers on, followed by `/auth/google/callback`:
     - `http://127.0.0.1:8080/auth/google/callback`
     - `http://localhost:8080/auth/google/callback`

     Plain `http` is allowed only for loopback; any other host needs `https`. Leave **Authorized JavaScript origins** empty. Download the client's JSON; newer projects may show the secret only then. Then put the client in Keeper and record it with:

     ```bash
     jason sign-in --import-client client_secret_XXXX.json --yes --delete-file
     ```

     This puts the client ID and secret in the vault at `signin/oauth-client/<key>` (a Keeper record titled with that path; it never overwrites one), and records that path in the community's `sign_in.json`. The secret goes from the file to the vault and is never printed. A row of the older form, naming a `record_uid`, still works. Without `--yes`, it says what it would do. `--for jason` records the client as the installation's instead. `--domain` restricts it to one or more domains (default: the community's email domains). `--label` names its button.
   - **Nothing to set up.** jason-web falls back to jason's own Desktop client from step 3. Google lets a Desktop client return to any loopback address and port with nothing registered. Google's guide is silent on a path after the port, but it accepted `http://127.0.0.1:8080/auth/google/callback` when this was first tried (October 2026).

   With the consent screen's user type **Internal** (step 2), only accounts in that Workspace organization can sign in with its client at all. If the Cloud project is not in the organization, the user type can only be **External**. Keep the app in **Testing** and list the people's addresses as test users (at most 100). `openid`, `email`, and `profile` are not sensitive scopes, so no verification is needed. jason-web reads Keeper without a prompt, so `jason login` must have been run once ([Keeper login](#keeper-login)). A new redirect URI can take from five minutes to a few hours to take effect.
2. **The roster.** Add each officer's Google account address to their row in `officers.json` ([Private facts](#private-facts)):

   ```json
   [{"role": "treasurer", "name": "Pat Example", "email": "treasurer@example.org"}]
   ```

   - **No address, no sign-in.** A row without `email` cannot sign in.
   - **Shared role accounts.** A role account, such as the treasurer's address, signs in as whoever holds that seat on the roster. Who holds a seat is the board's record, so update the roster when a seat changes hands.
   - **Two offices.** Where the bylaws let one person hold two offices, give the row a list: `"role": ["secretary", "treasurer"]`. Sign-in matches the person once, with both offices, and they may approve what either office approves.
   - **Admins and managers.**
     - `data/access/admins.json` takes `[{"name": "...", "email": "..."}]`.
     - `data/access/managers.json` takes `[{"name": "...", "email": "...", "communities": ["<profile>", "..."]}]`; `"*"` means every community.
     - A portfolio manager approves "the manager" in each of their communities, unless that community's own roster names a manager.
3. **Check and start it.**
   - `jason sign-in` shows the setup without writing anything: the clients, the fallback, and how many people can sign in.
   - `jason-web` offers sign-in beside the sample picker. `jason-web --require-sign-in` refuses every write until someone signs in.
   - Files and documents open from the console only for a signed-in roster person whose offices open their level ([security-and-privacy.md](console/security-and-privacy.md#roles)); without sign-in set up, none opens.
   - The **Sign in with Google** button or buttons appear at the top of the console. After sign-in, the header shows the person's name and a **Sign out** button.

   **Not production: `jason-web --dev`.** A signed-in admin gets an **Admin view** control in the header. With it, they see the console as any person on the roster or any office, to build and check role-based views. While they view as someone else, every write is refused, so no record ever carries a name its person did not sign in as. Choosing "myself" restores writes, and each switch is logged in `data/web/sign-ins.jsonl`.

**What jason-web checks before it lets anyone in:**
- the `state` it sent comes back, within ten minutes;
- the ID token's `iss` is Google, its `aud` is the chosen client, it has not expired, and it carries the `nonce` jason-web sent;
- `email_verified` is true;
- when the client names email domains, the token's `hd` claim is one of them. Google's own advice is that the `hd` parameter sent to Google is only a hint for the account chooser; the claim is what counts;
- the email matches exactly one person on the roster.

Sign-in grants what the roster grants and nothing more.

**While someone is signed in:**
- **The record uses their name.** A write's `by` must be the signed-in person's name, and an empty `by` is filled with it. Approval steps record `via: console:google` in the audit log.
- **The session has limits.** It is a signed, HttpOnly cookie that lasts twelve hours at most. Restarting jason-web signs everyone out. A person taken off the roster is signed out at their next write.
- **Sign-ins are logged.** Each sign-in, refusal, and sign-out is a line in `data/web/sign-ins.jsonl`, with the client used.

**When it goes wrong:**
- **`redirect_uri_mismatch`:** the console was opened at an address the client does not list. Add that exact address to the client. With jason's Desktop client, open the console at `http://127.0.0.1:8080`.
- **`org_internal` or "access blocked":** the account is outside the Workspace organization that owns the client.
- **"not on the roster":** the address is in none of the roster files (step 2).
- **"not an account of the Google Workspace this sign-in accepts":** the account's domain is not one of the client's domains.
- **"could not read its client":** run `jason login`. Then check that the Keeper record has the client ID (`client_id` or the login) and the secret (`client_secret` or the password).

**What is still to come.** A manager's portfolio decides where they may sign in and what they approve. But one jason-web serves one community, the active profile (`JASON_COMMUNITY`; [tenancy.md](tenancy.md)), so moving between a portfolio's communities is a separate jason-web for each. The provider kind is a closed set (`IdentityProvider`); only Google is built. The console still listens on loopback only. Serving it beyond this machine needs HTTPS and the board's written policy on who may see what ([console/security-and-privacy.md](console/security-and-privacy.md)).

### 6. jason's mailbox

jason reads mail through the Gmail API, which reads a **mailbox**. A Google Group's own archive (its "Conversation
history") has no read API: the Groups Migration API only inserts, and the Admin SDK and Cloud Identity cover members and
settings, not messages. So jason sees a group's mail only through a mailbox that is a member of the group. Set that up
once, for each new community:

1. **Give jason its own Workspace account** (recommended), e.g. `jason@<the association's domain>`. It is a paid
   license seat. A separate account keeps jason's reading and drafting apart from any person's mailbox, survives a
   change of officers or manager, and can be a member of every group without anyone's personal mail in it. If a seat is
   not affordable yet, use one shared association mailbox (the onboarding item says which), and accept that mail
   reaching only someone else's mailbox is unseen.
2. **Add that mailbox to every Google Group** the association uses (board, manager, records, architectural...), with
   **delivery set to "Each email"** (not digest, not "No email"). In the Admin console: Directory > Groups > the group >
   Members > Add members; or a group owner in groups.google.com. Do the same for each **alias** jason should see: an
   alias on a user forwards to that user's mailbox, so either put the alias on jason's account or make the alias a group
   with jason as a member.
3. **Turn on the group's archive** (Conversation history) if the board wants a record kept in Google too. It does not
   help jason read the history; only membership does, from the day it is added.
4. **Sign jason's account in** (step 4 above) so its token reads that mailbox, and record the account in the onboarding
   item `jason-mailbox` (`jason onboard`), with the groups and aliases it belongs to.
5. **The history before membership**, if the board wants it: a Google Vault export of each group (Vault's `GROUPS`
   corpus, `.mbox` with the original headers) can be imported once, matched by `Message-ID`. Vault comes only with
   editions that include it (Business Plus, Enterprise, some Education editions), needs an admin with Vault privileges,
   and its files land in Cloud Storage for download. Without Vault, there is no way to read a group's past mail.

What jason does with the mail it can read, and how it will rejoin conversations across mailboxes, is
[gmail-conversations.md](gmail-conversations.md).

## Local AI

jason's local models run on Ollama (`qwen3.6:27b` for OCR, classification, and extraction; `qwen3-embedding:8b` as the passage index's embedder, `jason index --build`). `jason local-ai` reports the stack. A model job holds jason's GPU lock and runs a preflight that fails fast on the CPU or when Windows is short of commit charge. A system-managed page file is often too small; a fixed 32 to 64 GB page file is the fix ([document-tools.md](document-tools.md)).

## Where jason writes

A rebuilt index, OCR page images, a model's files, and the county caches are large, and the system drive is often the small one. `jason storage` lists each place jason reads or writes: its path, drive, the drive's free space, and the size of what jason keeps there. `jason storage --check` exits 1 and says why when a drive is short of room (`--min-free-gb`, default 20), when scratch would land on the small drive, or when `JASON_TEMP_DIR` cannot be used.

**Name the folders once, in the user config.** Each of jason, asspy, and lawlibrary reads its own settings file from the home folder, outside `AppData`, so a terminal, an agent's shell, the worker, and a scheduled task all find the same file wherever they start (a program's `AppData` view can differ from another's, and a relative path depends on the working directory):

| Program | User config | Names | Another file |
|---|---|---|---|
| jason | `~/.jason/.env` | `JASON_TEMP_DIR`, `JASON_DATA_DIR`, `LAWLIBRARY_HOME`, and any setting a project's `.env` takes | `JASON_CONFIG` |
| asspy | `~/.asspy/.env` | `ASSPY_HOME` (county caches, tax rolls, samples) | `ASSPY_CONFIG` |
| lawlibrary | `~/.lawlibrary/.env` | `LAWLIBRARY_DATA` (the publication archive) | `LAWLIBRARY_CONFIG` |

For each setting the process environment wins, then the project's own `.env` (a checkout's, or the one `JASON_ENV` names), then the user config, then the built-in default. Write paths with forward slashes (`D:/scratch/jason/tmp`): a backslash path in double quotes is read as an escape. The tests read no user config. `jason storage` lists each file and whether it is there, and shows where each setting resolves.

```
# ~/.jason/.env
JASON_TEMP_DIR=D:/scratch/jason/tmp
LAWLIBRARY_HOME=D:/code/lawlibrary
```

A relative path in the settings (`LAWLIBRARY_HOME`, the Google token file) is taken from the jason checkout, never from the working directory.

Put scratch on a roomy drive with `JASON_TEMP_DIR`. A relative value is taken from the folder that holds the data directory. Unset, nothing changes. When it is set, each jason command, `jason-mcp`, `jason-web`, the worker and every job it starts, and the scripts in `scripts/` create the folder and point Python's `tempfile`, `TEMP`, `TMP`, `TMPDIR`, `SQLITE_TMPDIR`, and `PYTEST_DEBUG_TEMPROOT` at it, so every program jason starts (pymupdf, Tesseract, SQLite's sorts during `jason index --build`) uses it too. The tests put `tmp_path` there as well. Importing `jason` does nothing; the setting is applied when a program starts. A drive that is missing or a folder that cannot be written stops the run with a message, and jason does not fall back to the system temp folder.

What it cannot move, and what you may choose to run yourself (jason never changes a system or user setting):

- **Other programs' temp files**, and Windows itself, use the user's `TEMP` and `TMP`. To move them: `setx TEMP D:\temp` and `setx TMP D:\temp` (new programs only; make the folder first).
- **A coding agent's own scratch folder** is the agent's setting, not jason's; it is usually under the user's `TEMP`, so the `setx` lines above would move it, and a session started before them still uses the old one.
- **pip's cache**: `pip config set global.cache-dir D:\pip-cache`.
- **Folders jason reads that have their own settings**: `ASSPY_HOME` (the county index cache; default `~/.asspy`; name it in `~/.asspy/.env`), `LAWLIBRARY_DATA` (default `~/.lawlibrary/data` on Windows; name it in `~/.lawlibrary/.env`), `OLLAMA_MODELS`, `HF_HOME`, and `JASON_LOCK_DIR` (small; default `~/.jason/locks`). `jason storage` shows where each is.

None of the defaults is under `AppData`. A program launched by a packaged application (the Claude desktop app) has its `AppData\Local` writes redirected into a private per-package cache, so one person's terminal and agent could keep two folders under the same path, and two jason processes could take their locks in two lock folders and not see each other's. Data left in an old default (`%LOCALAPPDATA%\asspy`, `%LOCALAPPDATA%\lawlibrary`, `%LOCALAPPDATA%\jason\locks`) is moved by hand; `jason storage` lists any it finds.

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

**Which community a command serves.** `jason --community KEY ...` for one command, `JASON_COMMUNITY=KEY` for one shell, `jason use KEY` to save it in `~/.jason/.env`; `jason use` shows the current one and where it came from. A command that writes (anything given `--yes`) prints `community: KEY (from SOURCE); data: PATH` on standard error first. `JASON_PROFILE` is the old name of `JASON_COMMUNITY` and is still read. With no choice at all, the only installed profile (else the built-in default, while `JASON_DEFAULT_COMMUNITY_SHIM` is not `0`) is used and a line says so; setting `JASON_DEFAULT_COMMUNITY_SHIM=0` makes a missing choice among several installed profiles stop the command with exit code 2 ([tenancy.md](tenancy.md#phase-1-what-was-built)).

`JASON_DATA_DIR` (environment or `.env`) moves the data root from `data/` beside the checkout; another profile's stores are in `<root>/<profile>/`, and the private facts in `<root>/spec/` ([profiles.md](profiles.md#each-profiles-data)). The Mystique-specific research notes (`mystique/notes/`) are private too.
