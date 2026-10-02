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
- **Google:** `google_oauth_record_uid`, `google_sheets_spreadsheet_id`, `google_notebook_url`.
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

The association's private facts (account numbers, people's names and contacts, settlement figures, which units are rented) are in `data/spec/<name>.json`, which is never checked in. The specification reads them through `jason.community.private`. A checkout without them still runs, with those facts absent. The tests read made-up facts from `tests/fixtures/spec`. The Mystique-specific research notes (`mystique/notes/`) are private too.
