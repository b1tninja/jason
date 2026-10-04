# jason

jason is the virtual manager of a California homeowners association. It does the reading, checking, drafting, and record-keeping work a community manager does. It reads the association's PayHOA account, Google Workspace, paper mail, Zoom meetings, utility portals, and the county's public records. It checks them against the governing documents and the Davis-Stirling Act, and drafts what the board and its Secretary act on.

It was built for its first association, a condominium community in Sacramento (the `mystique` profile). The association's facts are a specification (`mystique/`), separate from the code, so the same code can serve another community.

## What jason never does

- **It never sends, pays, approves, or deletes.** Emails are Gmail drafts, member broadcasts are previews, and payments, approvals, and request decisions are a person's. Nothing in Drive, PayHOA, or Vault is deleted.
- **It never writes without consent.** Every write to Google, PayHOA, Zoom, or Vault needs `--yes`, and without it the command shows what it would do.
- **It never decides.** A finding is a lead with its evidence. Whether a duty was met, a payment authorized, or a document privileged is the board's or counsel's to say.
- **It never prompts in the background.** An unattended run fails fast when a login is missing (`KeeperAuthRequired`, `GoogleAuthRequired`).
- **It keeps private facts private.** People's names and contacts, account numbers, and settlement figures are never checked in (`data/spec`, [docs/setup.md](docs/setup.md#private-facts)). Executive session matters stay out of open minutes and shared catalogs.

## How it is built

- **Specification** (`mystique/`): the association's facts as data. This covers the buildings and units, rule rows (document kinds, sender and link rules, agenda item rules, privilege parties), the registers, and the legal holds. A new decision is a new rule row, not new code.
- **Implementation** (`src/jason/community`, `src/jason/google`, `src/jason/...`): reusable readers, matchers, and clients. The document models read each kind of document into a typed record with findings, each citing the statute that shapes it.
- **Tasks and commands** (`src/jason/tasks`, `jason <command>`): they apply the results. Local stores under `data/` hold what jason read, so most reports run from disk.
- **Local AI:** Ollama models (OCR, classification, extraction, embeddings) on the machine's GPU, and jason's own passage index (`jason index`). A model's answer must quote the document, and it is checked against the rule reader.
- **`jason-mcp`:** serves the stores on disk to Claude Code or another MCP client ([docs/mcp.md](docs/mcp.md)).

Credentials live in Keeper. `.env` holds only record UIDs and paths. The conventions are in [AGENTS.md](AGENTS.md), and the workflows and their limits are in [SKILLS.md](SKILLS.md).

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e D:\code\asspy -e D:\code\payhoa -e D:\code\smud -e D:\code\i-doxs -e ".[dev]"
cp .env.example .env          # fill in the Keeper record UIDs
jason login                   # once, in a real terminal
pytest
```

The full setup (Keeper, the Google OAuth client and consent, the local models) is in [docs/setup.md](docs/setup.md). Every command is listed in [docs/cli.md](docs/cli.md), and every doc in [docs/README.md](docs/README.md).

## What it does

| Area | Commands | Docs |
|---|---|---|
| **Utility bills** | `sync-bills` attaches SMUD and City bills to PayHOA transactions; `utilities` covers usage, abnormal usage, next year's cost, and the payment audit | [utility-bills](docs/utility-bills.md) |
| **Finance** | `budget`, `books`, `ledger`, `reconcile`, `invoices`, `reserves` (funding plan, Civil Code 5515 borrowings), `paid-vs-approved` (each approval in the minutes followed to its payments) | [ledger-reports](docs/ledger-reports.md), [invoices](docs/invoices.md), [reserve-studies](docs/reserve-studies.md), [reserve-transfers](docs/reserve-transfers.md), [meetings](docs/meetings.md) |
| **Meetings and the board** | `board` (action items, the agenda, the minutes template, and `--minutes DATE` drafting from the Zoom record), `meetings` (the records catalog, agenda links and items), `cross-checks` (agendas against minutes), `minutes-privacy`, `rule-change` (Civil Code 4360 notices), `calendar`, `zoom`, `hearing` | [board-agenda](docs/board-agenda.md), [meetings](docs/meetings.md), [zoom](docs/zoom.md), [calendar](docs/calendar.md) |
| **Documents** | `library` (classified, with OCR and local models), `models` (typed readings and findings, `--ask` for a model's grounded answers), `drive` (where each record is held), `copies`, `export-documents`, `publish-document` | [document-models](docs/document-models/README.md), [document-tools](docs/document-tools.md), [drive-holdings](docs/drive-holdings.md), [drive-sync-rules](docs/drive-sync-rules.md), [copies](docs/copies.md) |
| **Owners and notices** | `owner-info` (the Civil Code 4041 cycle), `delivery` (who gets each notice, by 4040), `forms`, `draft` (Gmail drafts), `broadcast`, `letter`, `packet` (the annual disclosures), `rentals` | [owner-information](docs/owner-information.md), [forms](docs/forms.md), [drafts-and-forms](docs/drafts-and-forms.md), [letters](docs/letters.md), [packets](docs/packets.md) |
| **Insurance, legal, and claims** | `policies`, `insurance`, `deadlines`, `incidents` (maintenance and claims by unit and building), `cases`, `hold` (a legal hold in Vault and Drive) | [insurance-policies](docs/insurance-policies.md), [insurance-and-deadlines](docs/insurance-and-deadlines.md), [incidents](docs/incidents.md), [legal-hold](docs/legal-hold.md) |
| **Mail and counterparties** | `mail` (PostScanMail, read-only), `gmail` (headers only), `contacts`, `sources`, `vendors` (vendor portals), `pests`, `permit-status` (City permits) | [mail](docs/mail.md), [gmail](docs/gmail.md), [vendor-portals](docs/vendor-portals.md), [pest-management](docs/pest-management.md) |
| **Property and county records** | `property-history`, `brief`, `title-watch`, `recent-filings`, `sync-liens`, `sync-solar`, `records-request` | [property-histories](docs/property-histories.md), [recorded-instruments](docs/recorded-instruments.md), [document-readings](docs/document-readings.md) |
| **Records and the law** | `duties` (the Civil Code 5200 inventory and the manager's duties), `export-authorities` (the statutes' words), `review` (a manager's review with every quote checked) | [community-manager](docs/community-manager.md), [manager-review](docs/manager-review.md), [laws](docs/laws/README.md) |
| **Google Workspace** | `registers` (Sheets jason and the board keep together), `drive-activity`, `drive-labels`, `photos`, `vault` | [registers](docs/registers.md), [drive-activity](docs/drive-activity.md), [drive-labels](docs/drive-labels.md), [photos](docs/photos.md) |
| **Local AI and search** | `local-ai`, `index` (the passage index: build, status, search by scope), `ocr-documents`, `read-documents`, `index-coverage` | [document-tools](docs/document-tools.md), [rag-roadmap](docs/rag-roadmap.md) |

## Development

```bash
pytest
```

The tests never touch a live service or the association's data. They use mock HTTP transports and fakes. The private facts they need are made up, in `tests/fixtures/spec`. Temporary files go under `--basetemp` on a drive with room. Write code like the code around it: classes, enums, and records over strings; integer cents for money; a rule row for a decision ([AGENTS.md](AGENTS.md)).
