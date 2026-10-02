# jason

HOA agent (virtual manager) for administrative tasks. Orchestrates:

- **[payhoa](../payhoa)** — PayHOA / LegFi API client
- **[smud](../smud)** — SMUD bill sync (SQLite + PDF cache)
- **[idoxs](../i-doxs)** — City of Sacramento i-doxs bill sync (SQLite + PDF cache)
- **[Keeper Commander Python SDK](https://docs.keeper.io/release-notes/developer-tools/commander-sdk/python-sdk-1.2.0)** (`keepersdk`) — vault access for credentials

PayHOA HTTP lives in the payhoa package. Jason is the agent that decides when to call it.

Mystique-specific facts live in [mystique](mystique/README.md). `jason.community` is the loader and the abstract `Community` base. Tasks use that object; they do not embed association ids, building tables, or sync rules.

## Use cases

Skills for these workflows, including what not to do, are in [SKILLS.md](SKILLS.md).

### Attach utility bills to transactions

Each month the bank feed has unreviewed SMUD and City of Sacramento charges with no PDF. Jason lists those PayHOA transactions, syncs only the utility portals that have a pending match, and uploads the bill when the amount and date line up.

```bash
jason sync-bills --dry-run
jason sync-bills
```

A match must be unique. SMUD and the City are identified from the transaction text, not from the vendor list. The PDF is downloaded only when a transaction still needs one.

### Review requests against the governing documents

An owner submits a maintenance or architectural request (“the gutter is leaking”). Jason should read the request text, find the governing-document file that applies, quote that passage, leave an internal note with a recommendation, and tag the request (for example `Association Responsibility`). It should not approve, deny, or assign the request.

Today `jason review-requests` quotes the request itself and matches document file names in the catalog. `--apply-tag` writes a tag only when you pass one. Quoting a passage from the document body, and writing the recommendation into an internal note, still needs the document files themselves, not only their names.

```bash
jason sync-catalog
jason review-requests
jason review-requests --apply-tag "Association Responsibility"
```

### Monthly delinquent accounts for the collection agency

Once a month the board needs a list of accounts that are still past due, with unit, owner, and how old the balance is, to hand to the collection agency. PayHOA already has this as the Delinquent Accounts and Aging of Accounts reports. `jason who-owes` and `jason reports` pull the unpaid charges and the aging buckets (current through more than three months).

The agency portal is not connected. The realistic handoff is a dated spreadsheet or CSV from those figures, reviewed by a person, then uploaded to the agency. Jason should not submit accounts to the agency on its own.

```bash
jason reports
jason who-owes
jason who-owes-sheet
```

`jason who-owes-sheet` writes Unit, Owner, Balance, and Past due into the spreadsheet in `google_sheets_spreadsheet_id`. It refuses to run when that id is empty. The sheet is for a person to review. Jason still does not submit accounts to the agency.

### Property histories

Each unit's chain of title from the developer's first conveyance to the current owner, with the price computed from each deed's transfer tax, the base the assessor enrolled after it, the instruments recorded beside it, and an audit against the tax bills. One Markdown report per parcel under `data/reports/property-history/`, and one spreadsheet. The workflow, the bounds it relies on, and the strategies for an open parcel are in the private notes (data/spec/notes/ownership-history.md); the skill is in [SKILLS.md](SKILLS.md#write-the-property-histories).

```bash
jason property-history
jason property-history --sheet --no-browser
jason property-history --spreadsheet SPREADSHEET_ID --no-browser
```

Only the spreadsheet step needs Google. The Membership workbook is not written.

```bash
jason unit-charts --no-browser
```

`jason unit-charts` creates a second spreadsheet that charts the two unit numberings and their overlap, and every sale by date and price per building. Why unit numbers do not identify a parcel here is in the private notes (mystique/notes/unit-numbers.md).

```bash
jason sales-charts --no-browser
```

`jason sales-charts` creates the conveyance-history spreadsheet: conveyances per year stacked by process, the median and mean price per year, every sale by date with a series per process, price and tenure by building, and deed price against the enrolled base.

```bash
jason equity-charts --no-browser
```

`jason equity-charts` creates the values-and-appreciation spreadsheet, with a Unit lookup tab that fills for whichever address is picked, a Trend tab that scatters sale prices by building over time with the moving averages through them, and the market read per square foot and by bedroom count. Comps are the community's own sales; the method and its limits are in the private notes (data/spec/notes/ownership-history.md, "Views"). `--spreadsheet ID` refreshes an existing copy in place.

```bash
jason sync-characteristics
```

```bash
pip install -e ".[charts]"
jason property-history
```

`jason property-history` writes the Markdown pages: one per parcel with the chain flowchart, a tenure gantt, the home, and its value; `market.md` with Mermaid charts of the market by year and a quadrant of every unit; and, with the optional `charts` extra (matplotlib), SVG scatter charts with the moving averages under `charts/`. `--no-charts` skips the images. GitHub renders the Mermaid blocks and the images as-is; the folder is under `data/`, which git ignores, so publish a copy to read it there.

```bash
jason brief 201-1170-022-0013 --escrow
jason recent-filings --since 2026-09-01
```

`jason brief` prints one unit on one page from the stores (owner, chain, liens, solar, taxes, members, value, audit), and `--escrow` adds the lines the association can tell escrow. `jason recent-filings` lists what recorded since a date with what to do about each. Both read disk only; run the syncs first for the newest filings. The same briefs are MCP tools.

```bash
jason duties
jason duties --brief "Assessments"
```

`jason duties` writes `records.md`, the inventory of the association's records under Civil Code 5200 with the gaps, and `duties.md`, a brief per manager duty with the statute, the records, the cadence, and the passages the governing documents give for it. The same come back from the `records_inventory` and `duty_brief` tools.

```bash
jason export-authorities
jason export-authorities --list
jason anythingllm --sync
jason index-coverage
```

`jason export-authorities` writes the words of the law those briefs cite under `data/authorities/`, one page per article of the Davis-Stirling Act and one per span the duties and the lien processes name, from the lawlibrary checkout in `lawlibrary_home` (its own `.venv` runs; nothing is installed here); `--list` shows the pages and the pointers (federal law and the whole DRE publications) that must be read at their source, and `--fetch-publications` downloads the DRE publications first, so the export can cut the cited Title 10 sections out of the Commissioner's regulations. The `authorities` tool reads a section by citation. `jason anythingllm --status` checks the app itself (its models against jason's, each workspace's documents, what is wrong); `--start --yes` starts it, `--apply --yes` sets its chat model and retrieval, and `--snapshot` / `--reembed --yes` save and restore each workspace's documents ([docs/document-tools.md](docs/document-tools.md)). `jason anythingllm --sync` keeps its catalogs in AnythingLLM, each its own folder and workspace: `authorities`, `association-records`, `mail`, and `jason-pages`. A legal case with a Drive folder in `mystique/cases.py` is its own confidential catalog: `jason cases --fetch-files` downloads the folder (read-only; Google Docs as PDF, caption transcripts as text; medical and veterinary records held back unless `--include-held`) into `data/cases/<key>`, and `jason anythingllm --sync --catalog case-<key>` (or `--catalog cases`) pushes it to a workspace of its own that the shared Mystique workspace never takes. After regenerating pages, `--sync --refresh` replaces the stale copies of what Jason wrote; it never replaces the association's records. `jason index-coverage` reads every cached index document against the known processes and lists what is left to model, by pattern, with examples; `--write` saves it as `data/reports/coverage.md`. `jason mail` reads the association's PostScanMail mailbox (key in Keeper as `postscanmail_record_uid`), downloads and reads the scans, and prints what to act on: legal notices, insurance cancellations, government notices, escrow requests, and the dates the letters state ([docs/mail.md](docs/mail.md)). Google Workspace, each behind `--yes` for any write: `jason calendar` keeps the board's meetings, notice and hearing deadlines, and recurring deadlines on the calendar ([docs/calendar.md](docs/calendar.md)); `jason drive-activity --missing | --file ID | --folder ID --since DATE` reads who moved, trashed, or re-shared a file ([docs/drive-activity.md](docs/drive-activity.md)); `jason drive-labels --used` plans jason's labels on the Drive files the board used, `--apply --yes` writes them ([docs/drive-labels.md](docs/drive-labels.md)); `jason packet annual-disclosures --year 2027` plans and assembles the annual budget report and policy statement into one PDF from template Docs, PayHOA library files, and pages jason generates, with the law's required words cut from the statutes on hand ([docs/packets.md](docs/packets.md)); `jason review TASK` builds a community manager's context pack (the law, then the CC&Rs, bylaws, and rules, then the records, numbered in order of authority) and with `--run` the local model's review with every quote checked ([docs/manager-review.md](docs/manager-review.md)); `jason draft` makes Gmail drafts, never sent, `jason broadcast` checks a PayHOA member broadcast drafted on disk and previews it through PayHOA's renderer (`--preview`; `--send-sample --yes` emails only you a test copy; it never sends to members), keeps PayHOA's templates as Google Docs (`--sync-docs --yes`), and turns an edited Doc back into a body (`--from-doc`), `jason forms` handles the association's forms from one definition each: it makes the Google Forms and reads their responses, makes fillable PDFs (`--pdf`), reads and checks returned PDFs (`--read`), and matches an outside form's responses to PayHOA's current owners with proposed tag changes (`--match`), makes a definition's form in PayHOA's form builder (`--payhoa`, with `--yes`) and reads its signed-in submissions (`--payhoa-submissions`). `jason qr LINK` makes a QR code (PNG or SVG) to paste into a Doc, slide, or posted notice; jason's printed letters place one with `{QR:TOKEN}`, the link always printed beside it. `jason rentals` counts rented units against the declaration's rental cap and shows which have the board's approval on file. `jason owner-info` runs the Civil Code 4041 cycle: the deadlines, each owner's standing, and with `--apply --yes` the PayHOA tags and fields that bring the record up to date, never over newer information ([docs/owner-information.md](docs/owner-information.md)). `jason delivery` gives each current owner's notice delivery from their PayHOA tags under Civil Code 4040, with the broadcast and Mailroom lists; `--tags` sets the tag vocabulary in `mystique/tags.py` beside PayHOA's tags, `--notice KEY` gives one required notice's exact recipients and the PayHOA filters for them (`mystique/notices.py`), and `--audit` lists the tag changes that let PayHOA's own filters find everyone ([docs/drafts-and-forms.md](docs/drafts-and-forms.md)); `jason photos --pick URL` takes in the photos a person picks from a shared album, `--publish` and `--to-drive` keep them ([docs/photos.md](docs/photos.md)); `jason vault` lists Vault matters and holds. Photos and Vault each keep their own Google token. `jason zoom` syncs the association's Zoom meetings (a Server-to-Server OAuth app in Keeper as `zoom_record_uid`, custom fields `account_id` and `client_id`, the client secret in the password field; `jason zoom --store-app` creates it): transcripts, chats, AI Companion summaries, and attendance, with the schedule's meeting days that have no meeting; `jason hearing` plans a disciplinary hearing under Civil Code 5855, drafts its notice, and with `--create --yes` schedules it on Zoom ([docs/zoom.md](docs/zoom.md)). `jason insurance` reads each policy's term against the carriers' letters and PayHOA's premiums (`--policy master|umbrella|crime|d&o|workers-comp|flood-2|NUMBER` for one, `--claims` for the claims), and `jason deadlines` lists the recurring deadlines with the evidence each was done (`--within 90` for what is due soon, `--overdue`, `--name insurance`) ([docs/insurance-and-deadlines.md](docs/insurance-and-deadlines.md)); `jason sources` lists the association's counterparties by kind of source. `jason gmail --sync` reads the association's Gmail headers (read-only) and checks PostScanMail's notices against the synced mail; `jason contacts --fetch` compares PayHOA's vendor directory with who writes from each vendor ([docs/gmail.md](docs/gmail.md)). `jason copies` groups every copy of every invoice and bill across the portals, email, PayHOA, and paper, and names the best copy and the payment (`--section proposals|several|documents`, `--since 2026-01-01`, `--unexplained`, `--issuer NAME`) ([docs/copies.md](docs/copies.md)). `jason drive --sync` lists every Drive file (read-only) and shows where each association record is, which files a path rule covers, and the duplicates and versions ([docs/drive-holdings.md](docs/drive-holdings.md)). `jason permit-status --sync` signs in to the City's Accela Citizen Access (Keeper record `accela_record_uid`), reads the board's "Mystique" permit collection (`mystique/permits.py`) with its totals, and reads each open record in full (`--all` for every record): status, fees paid and due on every page of the fee tables checked against the portal's printed totals, conditions, inspections, and the review workflow; it pays no fee and schedules nothing. `jason reserves` reads the reserve study PDFs and prints next year's funding plan beside the budget and the reserve accounts ([docs/reserve-studies.md](docs/reserve-studies.md)); `--transfers` sorts the reserve accounts' movements and checks each borrowing's Civil Code 5515 record ([docs/reserve-transfers.md](docs/reserve-transfers.md)). `jason books --sync` stores PayHOA's general ledger month by month and reports it locally (`pl`, `months`, `vendors`, `cashflow`, `balances`, `receivables`, `check`, `query`). `jason ledger --fetch` reads PayHOA's saved treasurer's report runs, a balance sheet for every month end, and the chart of accounts, and checks the library's report PDFs against them ([docs/ledger-reports.md](docs/ledger-reports.md)). `jason cases` lists the association's legal matters and each statutory duty's standing (confidential). `jason google-features` checks whether the Docs API's suggested edits and anchored comments have left Developer Preview. `jason board` keeps the board's action items and drafts the next agenda and minutes from the last agenda Google Doc (`--agenda <doc id>`), and syncs a Google Sheet the board edits (`--sheet`) ([docs/board-agenda.md](docs/board-agenda.md)). `jason cost-centers` checks the annexations' two assessment cost centers against the charges, budget, and reserve studies. `jason securities` lists the developer's DRE securities by phase, the bonds, and their releases ([docs/developer-securities.md](docs/developer-securities.md)). `jason models` reads every classified library file with its kind's document model and prints the coverage; `--kind K --show` prints the readings and findings, and `--file X.pdf --kind K` reads one file on disk ([docs/document-models/README.md](docs/document-models/README.md)). `jason reconcile --fetch` reads PayHOA's bank reconciliations and prints each account's months covered, statements against the ledger, and the register items that never cleared; it changes nothing in PayHOA. `jason invoices --fetch` checks every expense payment's attachment for amount, vendor, date, reuse, and category ([docs/invoices.md](docs/invoices.md)). `jason pests` reads the pest control program from the vendor portal: every product by EPA registration number with its class, hazards, and California rules, the label limits the application record shows exceeded, rodent-station activity from the technicians' notes, visits by building, and the vendor's inspection reports; `--fetch` downloads each product's EPA and California registration, stamped label, and safety data sheet into `data/pesticides/` ([docs/pest-management.md](docs/pest-management.md)). `jason incidents` reads the repair paperwork in PayHOA, email, the library, and Drive (`--fetch` downloads the Drive folders `mystique/incidents.py` names, never the medical records) and lists the maintenance history and the insurance claims grouped into events by unit and building, with each event's work, claim or sudden cause, vendors, quoted and paid amounts, and claim numbers (`--building`, `--address`, `--work`, `--claims`, `--cause`, `--since`; [docs/incidents.md](docs/incidents.md)). `jason vendors --sync` signs in to each vendor portal in `mystique/vendors.py` with its Keeper record (`proactive_record_uid` for ProActive Pest Control) and saves the account, visits, products applied, photos, documents, and invoices checked against their tickets under `data/vendors/`; `--verify` matches the PayHOA payments to the vendor's own payment records and the attached invoices ([docs/vendor-portals.md](docs/vendor-portals.md)). `jason utilities` parses the downloaded SMUD and City bills into `data/utilities.db` and prints each account's meters and parcel, abnormal usage, and next year's cost from predicted usage at the rates in force, with a backtest, beside the budget (`--year`, `--water-increase 0.1` for a City scenario, `--account N` for one meter's history); `--payments --fetch` audits the PayHOA utility payments: the attached PDF, the bills paid, the split by budget line, and payments made twice (see [docs/utility-bills.md](docs/utility-bills.md)). `jason budget` syncs the year's budget against actual and the bank balances from PayHOA into `data/payhoa/finance-<year>.json` and prints the brief (`--offline` reads the last snapshot); `jason accounts` prints the balances. `jason library` classifies the PayHOA document library (`--fetch` downloads what is not on disk into `data/library/files`, `--model` asks a local model about files no rule placed, `--score` measures the phrase rules or the model against the name rules) and writes `data/reports/library.md`. `jason digest` is what the board should know now: what recorded, owners in default, releases owed, and the association's own liens. `jason title-watch` reads every lien joined to a unit as one standing against the title (`--attention` for what a person acts on); `jason property-history` writes the same as `liens.md`.

```bash
jason records-request --pages
```

`jason read-documents` scores a reader of the scanned instruments against the pinned facts, or with `--search` finds the passages that answer a question; `--extractor ollama` scores a local vision model over the page images through Ollama, and `--extractor claude` the hosted one, which needs `pip install -e ".[models]"` and `ANTHROPIC_API_KEY`. `jason ocr-documents` adds a text layer to image-only PDFs with an installed OCR engine, and `jason anythingllm` connects AnythingLLM Desktop to jason-mcp; the tools and their fit are in [docs/document-tools.md](docs/document-tools.md). `jason records-request` lists the recorded instruments the association's record names that no recorded copy on disk carries, with the county order form's fields, why each matters, its page count, and the copy cost at the county's fees, as Markdown and CSV under `data/reports/`. The reading of the documents themselves, and where OCR defeats it, is in [docs/document-readings.md](docs/document-readings.md).

```bash
jason sync-liens
```

`jason sync-liens` fetches the mechanic's lien filings (claims, releases, bonds, notices of action) naming the developers, the association, and every owner on a chain, so the pages can say whether each was released, bonded off, sued on, or expired unsued after ninety days. Names already searched narrowly are skipped; the run is a few hundred index calls the first time. `--all` also fetches the other lien-family filings (association, utility, judgment, tax, default, and reconveyances, which close the loans a wide name still shows open) for the wide names, which is a few thousand calls.

```bash
jason sync-solar
```

`jason sync-solar` searches the public index for every UCC filing the developer's solar lease funds recorded and caches them, so `jason property-history` can state each unit's solar standing (leased on the current owner, on a prior owner, terminated, or no filing) on its page, on `solar.md`, and on the Solar tab. Run it again before an escrow question; new filings record with each transfer.

`jason sync-characteristics` copies the assessor's residential characteristics (living area, bedrooms, baths, year built) for each unit into `data/characteristics.db`. The viewer's call is public. Run it once before `jason equity-charts`; without it the sheet still builds, with no per-square-foot figures.

### Reserve study update packet

The reserve study preparer asks each year for an update packet: the current operating budget, the current financial statements, the reserve account's bank statement, the reserve expenditures since the last report with their invoices, and bids for upcoming reserve work. The skill is [SKILLS.md](SKILLS.md#assemble-a-reserve-study-update-packet). Jason collects the files for a person to review and does not email them.

A reserve transfer is matched to the other account before it is treated as an expense. Copies go in `data/reserve-study-packet/`. Library files use the existing document download. Invoices use the existing signed attachment URL. A new report-to-PDF export is not required for this packet.

The full transaction register, with invoices, is under `data/transactions/{year}/{month}/`. Reserve components (cost center, classification, useful life, remaining life) are `Mystique.reserve_components()`, taken from the Reserve Components sheet. The comparison with the studies is in [SKILLS.md](SKILLS.md#review-transactions-against-reserve-components).

Mystique's findings are in the private notes (mystique/notes/README.md).

### Keep the document collection in sync with Google Drive

The governing documents live in PayHOA and a copy should live in a shared Google Drive folder. The first step is to export the PayHOA library and read its folders and file names. From that list we write expressions that say which Drive folder or file belongs in which PayHOA path. Jason does not copy files until those rules exist.

`jason export-documents` refreshes the flat library and writes `data/payhoa-documents.json`. Each row has `id`, `parentId`, `directory`, `fileName`, `path`, `fileSize`, `public`, and `updatedAt`.

```bash
jason export-documents
```

APIs this use case needs:

| Step | API | Status |
|------|-----|--------|
| List the PayHOA library | `GET /organizations/{orgId}/documents/flat` | Implemented. No file bytes and no `downloadUrl`. |
| List and download a Drive folder | Google Drive `files.list` / `files.get` | Signed in. The 2026-09-24 consent includes `drive.readonly`, `documents`, `spreadsheets`, and `gmail.readonly`. `agent.drive()` / `docs()` default to `interactive=False` and raise `GoogleAuthRequired` if the token is missing or lacks scopes. |
| Edit a Google Doc | Docs `documents.get` and `documents.batchUpdate` | Docs API enabled. `agent.docs().batch_update` sends the request list. A diagonal DRAFT text watermark is not one of those requests. |
| Export a Google Doc to PDF | Drive `files.export` `application/pdf` | `GoogleDrive.export_pdf`. Prints the doc as it is, watermark included. |
| Download one PayHOA document | `POST /organizations/{orgId}/documents/{id}/download` with `{}` | Implemented. The response is the file bytes. |
| Create a PayHOA document | `POST /organizations/{orgId}/documents` multipart `parentId`, `directory` `0`, `fileName`, `file` | Implemented. Replace was not in the capture. |

### Publish minutes into PayHOA

Meeting minutes stay a Google Doc, often with a diagonal DRAFT watermark. Jason can edit the Doc body with `documents.batchUpdate`, export a PDF, and upload that PDF into a PayHOA folder. Removing the watermark still happens in the Docs editor before the export.

```bash
jason publish-document --doc DOC_ID --parent PARENT_ID --out "Minutes of 7_7_26.pdf" --interactive
```

`--parent` is the PayHOA folder id. `PayhoaFolder.MEETINGS_2026` is `Meetings/2026` on the `Mystique` class. The 2026-09-24 consent already includes the Docs scope; pass `--interactive` only if the token is missing or lacks scopes.

The public site already embeds several of these folders. See [docs/mystique-site.md](docs/mystique-site.md).

Sync rules will be local expressions over these rows (for example a Drive folder mapped to a PayHOA `path`). They are not an API.

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
payhoa_record_uid = "YOUR_PAYHOA_RECORD_UID"
smud_record_uid = "YOUR_SMUD_RECORD_UID"
idoxs_record_uid = "YOUR_IDOXS_RECORD_UID"
```

Optional: `keeper_password`, `keeper_config`, `payhoa_org_id`, `smud_db`, `smud_bills_dir`, `idoxs_db`, `idoxs_bills_dir`, `google_oauth_record_uid`, `google_notebook_url`, `google_sheets_spreadsheet_id`, `anythingllm_record_uid` (a Keeper login record whose password field is the AnythingLLM API key; `jason anythingllm --store-key` creates it from a key in `.env` or `ANYTHINGLLM_API_KEY`), `lawlibrary_home` (the lawlibrary checkout, default `../lawlibrary`).

### Google Sheets setup

Jason signs in as you (Workspace SSO) and writes one spreadsheet. The OAuth client id and secret live in Keeper. The refresh token from the first browser login stays in `secrets/google-token.json`.

#### 1. Enable the Sheets API

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and select the project, or create one.
2. Open [APIs & Services → Library → Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com).
3. Click **Enable**. Confirm the project name in the header is the one you intend to use.

#### 1b. Drive API

The Drive API is enabled on the same Cloud project as Sheets. Use the Keeper record that already holds the OAuth client (`client_id`, `client_secret`). That JSON is the app identity. It is not a user login, and it does not include a scope or a refresh token. Do not create a second OAuth client or a second Keeper record.

Still required before `jason.google.GoogleDrive` can list a folder:

1. On the existing OAuth consent screen, add `drive.readonly`, `documents`, `spreadsheets`, and `gmail.readonly` if they are not there. Enabling an API does not add a scope. The downloaded client JSON does not list scopes either. Scopes are granted when a person signs in.
2. Call `agent.drive(interactive=True)` when a person is present. If `secrets/google-token.json` has no refresh token, that opens a browser on `http://127.0.0.1` for one Workspace sign-in. The Keeper client id and secret are sent with that consent. The refresh token is written to `secrets/google-token.json`. Later calls reuse it and do not open a browser unless Google rejects the token.
3. `agent.drive()` defaults to `interactive=False`. A missing or rejected token raises `GoogleAuthRequired` immediately. An unattended run does not open a browser or wait.

`GoogleDrive` lives in `jason.google` and is opened with `agent.drive()`. It reads the Keeper client fields and the refresh token. It does not belong in the PayHOA or bill-matching tasks.

New Google Sites has no content API. The published site is a Drive file (`application/vnd.google-apps.site`). Drive can read that file's metadata, move it, and change who it is shared with. Drive cannot edit the page text, layout, or embedded components. Jason uses Drive for the folders embedded on the site and for the PayHOA library, not to rewrite [mystiquecommunity.com](https://www.mystiquecommunity.com). See [docs/mystique-site.md](docs/mystique-site.md).

#### 2. Create the OAuth client

1. Open [APIs & Services → OAuth consent screen](https://console.cloud.google.com/auth/overview) (Google may label this **Google Auth platform**).
2. If the Cloud project belongs to your Workspace org, set the user type to **Internal**. That limits sign-in to people in the org and uses Workspace SSO.
3. App name: `jason`. User support email: your Workspace address.
4. Add the scopes `https://www.googleapis.com/auth/spreadsheets`, `https://www.googleapis.com/auth/documents`, `https://www.googleapis.com/auth/gmail.readonly`, and `https://www.googleapis.com/auth/drive.readonly`. Save. Enable the [Google Docs API](https://console.cloud.google.com/apis/library/docs.googleapis.com) and the [Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com) on this project the same way as Drive. Sheets is already enabled. Gmail is read-only.
5. Open [APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials).
6. **Create credentials → OAuth client ID**.
7. Application type: **Desktop app**. Name: `jason`.
8. Create, then **Download JSON**. The file looks like:

```json
{
  "installed": {
    "client_id": "...apps.googleusercontent.com",
    "project_id": "...",
    "client_secret": "...",
    "redirect_uris": ["http://localhost"]
  }
}
```

#### 3. Store the client in Keeper

1. In the Keeper vault, create a **Login** record titled `jason Google OAuth`.
2. Add custom fields with these labels exactly: `client_id`, `client_secret`. Mark `client_secret` hidden. `project_id` is optional.
3. Paste the values from the downloaded JSON. Delete the JSON file. Do not commit it and do not paste it into `.env`.
4. Copy the record UID into `.env`:

```
google_oauth_record_uid = "THE_RECORD_UID"
google_sheets_spreadsheet_id = "the id between /d/ and /edit in the sheet URL"
```

Do not run Keeper's [JSON import](https://docs.keeper.io/keeperpam/commander-cli/command-reference/import-and-export-commands/json-import) on the Google download. That command expects Keeper's record schema, not the `installed` client document. A file attachment is also a poor fit: jason already reads custom fields, and Keeper's file-attachment SDK is still limited.

The spreadsheet must be shared with the Google account you sign in as. Leave `google_sheets_spreadsheet_id` empty until that sheet exists.

`google_notebook_url` is the consumer notebook at [notebook.google.com](https://notebook.google.com/notebook/YOUR_NOTEBOOK_ID). That UUID is not a [Gemini Notebook Enterprise](https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks) id, so jason cannot query it. Enterprise notebooks use `notebook.cloud.google.com` and include a Cloud project number.

### Keeper login (interactive — use a real terminal)

Non-interactive jason commands **never** prompt for passwords (they would hang agents). Run login once in a terminal:

```bash
jason login
```

This updates `%USERPROFILE%\.keeper\keeper-config.json` (device tokens + stored master password for later non-interactive use). Agents and scripts then use that persistent config with no prompts.

If auth is missing, jason fails fast with `KeeperAuthRequired` and tells you to run `jason login`.

## Local MCP

`jason-mcp` serves the catalog already on disk. It does not call PayHOA, Google, or Keeper, and it needs no login of its own. Install the extra and run it on stdio:

```bash
pip install -e ".[mcp]"
jason-mcp
```

Claude Code picks the server up from `.mcp.json` at the repo root. That file runs `.venv\Scripts\jason-mcp.exe` relative to the repo, so the virtualenv has to be at `.venv`. Approve the project server once when Claude Code asks. No token or environment variable is required; `Settings.load()` reads `.env` only for paths.

Every tool is served by default. `jason-mcp --profile board` (or `JASON_MCP_PROFILE=board`) serves nineteen: `board_digest` first, then the lien, unit, escrow, filing, solar, duty, records, and law tools. A small local model chooses better from that list, so `jason anythingllm --write` registers the board profile with AnythingLLM; `--profile all` registers every tool.

Tools: `catalog_status`, `search_requests` (status, form name, unit, text), `search_documents` (path prefix, name), `get_request_local_export`, and `read_exported_file` for `data/payhoa-files`. The deed-chain, recorder-index, tax, and secured-roll tools are listed in [SKILLS.md](SKILLS.md#read-the-local-catalog), and the ownership workflow they support is in [SKILLS.md](SKILLS.md#publish-an-ownership-sheet).

## Programmatic API

```python
from datetime import date
from jason import Jason

with Jason() as agent:
    payhoa = agent.payhoa()
    bills = agent.find_bills(amount_cents=6120, around=date(2026, 7, 1))
    water = agent.find_idoxs_bills(amount_cents=12345, around=date(2026, 6, 15))

    agent.dump_transactions("data/payhoa_txs.jsonl")
    report = agent.sync_bills(dry_run=True)  # PayHOA-first; sync only needed portals
    smud_report = agent.upload_smud_bills(dry_run=True)
    water_report = agent.upload_idoxs_bills(dry_run=True)
```

Keeper record custom/hidden fields for i-doxs security questions use a **label that appears in the question text** (e.g. `pet`, `food`, `team`); jason loads all of them and matches at login.

## CLI workflow

PayHOA-first (preferred): inspect the unreviewed queue, sync only portals that
have pending utility txs, then attach PDFs:

```bash
jason sync-bills --dry-run
jason sync-bills
jason sync-bills --source smud
jason sync-bills --skip-sync   # attach from local cache only
```

Lower-level commands:

```bash
# Live probes (server search vs client SMUD filter)
jason probe-transactions --interactive

# Intermediary dump for analysis
jason dump-transactions --out data/payhoa_txs.jsonl

# SMUD electric bills
jason upload-smud-bills --dry-run
jason upload-smud-bills

# Units, people, violations, requests, documents
jason sync-catalog
jason sync-catalog --only units,people
jason export-documents

# Report catalog plus aging, resale, and PDF export summaries
jason reports
jason who-owes
jason violations
jason notes --unit UNIT_ID
jason communications --recipient MEMBER_ID
jason vendor-matches
jason review-requests
jason review-requests --apply-tag "Association Responsibility"
jason sync-request-files
jason sync-request-files --requests REQUEST_ID

# New utility bills from both portals into the utility store (download only; nothing goes to PayHOA)
jason fetch-bills
jason fetch-bills --source smud --account ACCOUNT
jason fetch-bills --full --no-parse

# SMUD bills, payments, and usage
jason sync-smud
jason sync-smud --account ACCOUNT --full

# City of Sacramento water bills (i-doxs)
# Fast list sync: Bills.aspx ACCOUNT=ALL, metadata only, skip pages already known
jason sync-idoxs
jason upload-idoxs-bills --dry-run
jason upload-idoxs-bills

# Attach without portal sync (both sources)
jason attach-bills
```

### Matching rules (SMUD and City of Sacramento)

1. Unreviewed PayHOA transactions (`reviewed=false`)
2. Utility filter:
   - **SMUD** — `transactionRule.name == "SMUD"`, or `"SMUD"` in description, or Electricity (SMUD) category
   - **City of Sacramento** — rule/description contains Sacramento utilities text (including truncated ACH `CITY OF SACRAMEN`), or City of Sacramento Utilities category (`1245485`)
3. Skip if transaction detail already has attachments
4. Exact amount (cents) + bill date or due date within ±7 days in the utility cache
5. Unique match only; ambiguous / no match reported and skipped
6. PDF downloaded from the portal **only** when needed for upload

`jason sync-bills` syncs portal metadata only for sources with pending txs. PDFs remain lazy.
