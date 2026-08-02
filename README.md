# jason

HOA agent (virtual manager) for administrative tasks. Orchestrates:

- **[payhoa](../payhoa)** — PayHOA / LegFi API client
- **[smud](../smud)** — SMUD bill sync (SQLite + PDF cache)
- **[idoxs](../i-doxs)** — City of Sacramento i-doxs bill sync (SQLite + PDF cache)
- **[Keeper Commander Python SDK](https://docs.keeper.io/release-notes/developer-tools/commander-sdk/python-sdk-1.2.0)** (`keepersdk`) — vault access for credentials

## Setup

```bash
cd D:\code\jason
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e D:\code\payhoa
pip install -e D:\code\smud
pip install -e D:\code\i-doxs
pip install -e .
cp .env.example .env
# Edit .env with keeper_username and record UIDs
```

### `.env`

```
keeper_username = "you@example.com"
payhoa_record_uid = ""
smud_record_uid = "YOUR_SMUD_RECORD_UID"
idoxs_record_uid = ""
```

Optional: `keeper_password`, `keeper_config`, `payhoa_org_id`, `smud_db`, `smud_bills_dir`, `idoxs_db`, `idoxs_bills_dir`.

### Keeper login (interactive — use a real terminal)

Non-interactive jason commands **never** prompt for passwords (they would hang agents). Run login once in a terminal:

```bash
jason login
```

This updates `%USERPROFILE%\.keeper\keeper-config.json` (device tokens + stored master password for later non-interactive use). Agents and scripts then use that persistent config with no prompts.

If auth is missing, jason fails fast with `KeeperAuthRequired` and tells you to run `jason login`.

## Programmatic API

```python
from datetime import date
from jason import Jason

with Jason() as agent:
    payhoa = agent.payhoa()
    bills = agent.find_bills(amount_cents=6120, around=date(2026, 7, 1))
    water = agent.find_idoxs_bills(amount_cents=12345, around=date(2026, 6, 15))

    agent.dump_transactions("data/payhoa_txs.jsonl")
    report = agent.upload_smud_bills(dry_run=True)
    water_report = agent.upload_idoxs_bills(dry_run=True)
```

Keeper record custom/hidden fields for i-doxs security questions use a **label that appears in the question text** (e.g. `pet`, `food`, `team`); jason loads all of them and matches at login.

## CLI workflow

Analyze PayHOA filters first, then match bills:

```bash
# Live probes (server search vs client SMUD filter)
jason probe-transactions --interactive

# Intermediary dump for analysis
jason dump-transactions --out data/payhoa_txs.jsonl

# SMUD electric bills
jason upload-smud-bills --dry-run
jason upload-smud-bills

# City of Sacramento water bills (i-doxs)
# Fast list sync: Bills.aspx ACCOUNT=ALL, metadata only, skip known pages
jason sync-idoxs
jason upload-idoxs-bills --dry-run
jason upload-idoxs-bills
```

### Matching rules (SMUD and City of Sacramento)

1. Unreviewed PayHOA transactions (`reviewed=false`)
2. Utility filter:
   - **SMUD** — `transactionRule.name == "SMUD"`, or `"SMUD"` in description, or Electricity (SMUD) category
   - **City of Sacramento** — rule/description contains Sacramento utilities text, or City of Sacramento Utilities category (`1245485`)
3. Skip if transaction detail already has attachments
4. Exact amount (cents) + bill date within ±7 days in the utility cache
5. Unique match only; ambiguous / no match reported and skipped
6. PDF downloaded from the portal **only** when needed for upload

Ensure bill **metadata** is in the cache (`smud sync` / `idoxs sync` at least once). PDFs are fetched lazily by jason.
