# Mail (PostScanMail)

The association's paper mail goes to a PostScanMail virtual mailbox. PostScanMail receives each piece, photographs the envelope, and scans the contents when asked or by rule. Renewals, cancellations, legal notices, government letters, and escrow requests arrive this way, so jason reads the mailbox.

## Access

PostScanMail's account API authenticates with one header, `x-api-key`. The key is in Keeper, in a login record whose password field holds it. `.env` names that record as `postscanmail_record_uid`. The key file downloaded from PostScanMail's console, `PostScan_Mail_API_Key.json`, and the Postman collection are ignored by git. The collection's `api_key` variable holds a different key from the one in Keeper. Delete the key file once Keeper holds the key, and revoke the collection's key in the console if it is still live.

`jason.postscanmail.PostScanMail` makes only reads:

- `GET /items?sort_order=desc&page=N` returns 20 items a page, newest first. The live API wraps the page in `{"status": 1, "data": {...}}`.
- Each item's cover image and scanned PDF are signed links. The signature is the credential, so the API key is not sent with them.

The API also offers open, discard, shred, and rescan requests for groups of items, their cancellations, and switches for the account's automatic rules (auto scan, auto shred, auto discard, auto AI summary). Those change or destroy the association's mail, and some are billed. The client does not implement them.

The HAR captured on September 29, 2026 holds only the public site's analytics requests, so the Postman collection is the source for the calls.

## The sync

`jason mail` pages through the mailbox. It stops at a page it already has, unless `--full` is given. For each item it:

- keeps the record in `data/mail/items.json`: sender, arrival, status, folder, assignee, whether it was scanned, and PostScanMail's AI summary lines. The signed links are not kept.
- downloads the scan to `data/mail/<mail id>/contents.pdf`. An unscanned item keeps its envelope, `cover.jpg`.
- reads the PDF's text layer, or OCRs it with Tesseract when there is none, into `text.txt`.

## The sort

`MAIL_RULES` in `jason.postscanmail.models` sorts each item by its sender and the letter's words. The first matching rule wins. PostScanMail leaves the sender blank on most items, so the letterhead, the scan's first 300 characters, stands in for it.

| Kind | Urgency | Matched by |
|---|---|---|
| Advertising | file | "is an advertisement" or "attorney advertising" in the heading. It comes first, since a law firm's advertisement may cite a court |
| Legal notice | act | "summons", "superior court of", "notice of default", "lis pendens", "subpoena" in the heading, or a law firm or attorney as sender |
| Insurance cancellation or non-renewal | act | "notice of cancellation", "notice of non-renewal", "will be cancelled" in the heading |
| Property tax bill | review | "property tax bill" near the top |
| Government or tax notice | act, or review for the county's online-account PIN letters | Franchise Tax Board, IRS, Secretary of State, tax collector, code enforcement, the fire department |
| Escrow or title request | act | a title or escrow sender |
| Utility bill | file | the City's utilities department, SMUD, a water company |
| Bank statement or notice | review | a bank as sender, or "certificate of deposit" or "account statement" |
| Insurance policy, renewal, or invoice | review | an insurer or agency, or two of "renewal", "declarations", "policy period", "premium" |
| Check or payment received | review | "pay to the order of", "void after", "refund check" |
| Vendor invoice or statement | file | two of "invoice", "amount due", "balance due", "remit" |

"In the heading" means the letter's first 1,500 characters. An insurance packet repeats "notice of cancellation" and "case no" as boilerplate pages deep, so those phrases are held to the heading; otherwise an insurance packet sorts as a legal notice or a cancellation.

A date the letter places next to "due", "respond", "effective", "expires", "renewal", or "hearing" is listed as a deadline when it falls on or after the day the letter arrived. A routine item that states such a date is raised to review. A miss stays "other".

The sort reads words. It does not decide what a letter means, and a stated date is not necessarily the real deadline. Read the letter.

## Credentials in the mail

Some letters carry a credential. The county's ownership-verification letters print a PIN for the parcel's online tax account. OCR scatters the PIN's value across the page, so a redaction cannot be trusted. Any letter whose text names a PIN, passcode, temporary password, or access code has its text withheld from `jason mail --item` and the `mail_item` tool. The PDF on disk is unchanged.

## Facts each letter prints

`letter_facts` reads the handles that join a letter to the association's other records: 14-digit parcel numbers, street addresses on the association's streets, insurance policy numbers, escrow and order numbers, and masked account endings. The sync joins them to the specification: a parcel number that is one of the association's parcels, and an address that falls in one of its buildings.

`policy_readings` gathers the insurance policy numbers the letters print, the building their letters place, the latest letter, and the latest stated date, so the mail shows the flood program's history policy by policy. A reading is evidence, not a pin: a building's policy goes on `BuildingRange.policy_number` only after a person confirms it. A policy number that also appears on another building's letter is not placed.

This association's findings are in its private notes (mystique/notes/mail.md).

## Checks against jason's records

`jason mail --checks` (and the `mail_checks` MCP tool) reads each kind of letter against a store jason already keeps:

- **Addresses.** The addressee block (the lines after the association's name) is checked against `Mystique.mail_addresses()` in `mystique/mail.py`. The addresses of record are:
  - **The PostScanMail box.** The mail center holds many boxes, and the box (PMB) number routes a letter to the association's. An address without it is flagged as *incomplete*, even when the letter arrived.
  - **The site address.** It is the common-area parcel and the service address on the utility accounts, and no mail is received there. A letter a sender addresses there never arrives, so the box cannot show it.
  - **The prior managers' offices.** A letter still addressed in care of a prior manager is flagged.

  The mailing address a counterparty has on file is therefore also read from its own bills. `account_addresses` reads the mailing block on each utility account's latest bill: the block after the association's name that is not the "Location:" or premise line.
- **Escrow requests.** Each with the 10 days Civil Code 4530(a)(1) allows from the mailing or delivery of the request, counted from the day PostScanMail received it.
- **Tax bills and delinquency notices.** Each county bill and notice matched to the bill `jason sync-tax` stored, by the bill number it prints (a notice prints a short form of the stored bill's number, without the century and a zero) or by its total or an installment, with whether the stored bill is paid now.
- **Bank statements.** Each statement's date, account ending, and ending balance.
- **Checks.** The amounts a check prints against PayHOA deposits of that amount within 45 days, with the category each deposit was booked to.
- **Preliminary notices and lien claims.** Each 20-day preliminary notice (Civil Code 8200) or mechanic's lien claim, with the claimant named from the form's CLAIMANT block, against PayHOA payments to the claimant from 120 days before the notice to a year after. Whether a claim was recorded is the `mechanics_liens` tool's question.

The checks also go into `data/reports/mail.md`, so the jason-pages catalog carries them as a summary. This association's findings are in its private notes (mystique/notes/mail.md).

## Sources

Who a letter comes from, and what kind of source that is, decides how to read it. A government agency's notice can carry a legal deadline; a utility's bill follows a tariff; an insurer writes about coverage; a bank's statement is a record of balances; a vendor bills for work; a title company asks for resale documents; a manager writes for its clients.

- **The directory.** `Mystique.senders()` (`mystique/senders.py`) is a `Sender` row per counterparty: its name, `SourceKind`, a government agency's `Level` (federal, state, county, city, special district), the words its letterhead or bank line carries, its PayHOA vendor name, and its role. A new counterparty is a new row.
- **Resolving.** `jason.community.sources.resolve` tries the sender field, then the letterhead (the first 400 characters, with the association's own name removed, since that is the addressee), then the generic words in `KIND_WORDS` ("County of", "Insurance", "LLP"), then a named sender's words anywhere in the first 1,200 characters (a 1099's payer block, an invoice's "COMPANY:" line). A preliminary notice's sender is the claimant its form names. A miss stays unknown. A known source sorts a letter the words left as "other" (a utility's letter is a utility letter).
- **Other associations.** `other_associations` reads the names of other community associations a letter mentions. A letter that names one and never names this association is that association's mail (`misdirected`), often an owner statement from another association a prior manager also manages. It never gets a letter page. A notice about the association's own account that names another association is a record under another name, for a person to correct with the sender.
- **Owners.** The association's own assessment statement mailed back with a payment is an owner's account; it never gets a letter page (Civil Code 5215).
- **The report.** `jason sources` (and the `counterparties` MCP tool) lists each named sender by kind, with its letters by kind and its PayHOA payments (money out only; a wire or deposit in is not a payment), the PayHOA vendors the directory does not name, the letterheads no rule names, and the other associations.

## Letter pages

The sync writes `data/mail/<mail id>/letter.md` for each shareable letter: a heading with the date, sender, kind, and mail id; the sort, stated dates, and facts; PostScanMail's summary; and the scanned text. A letter page is correspondence: the sender's words as scanned, not the association's record and not an authority.

- A letter carrying a PIN or access code never gets a page, nor does another association's mail or an owner's own account. Attorney letters, bank statements, checks, and escrow requests are confidential kinds.
- The letters are the passage index's `mail` catalog (`jason index --build`; `jason.tasks.index_sources.MailSource`). The index reads a letter's page, or its scanned text (`text.txt`) when it has no page, and decides each letter by `MAIL_RULES`:
  - never indexed: a letter carrying a PIN or access code (read from its text, whatever the stored sort says), another association's mail, and an owner's own account;
  - confidential (searched only when asked): a letter the sort left unknown, the confidential kinds, and a letter that names a member.

  `jason index --plan` lists the counts. `mail_brief` and `mail_item` still read the sort, and `data/reports/mail.md` is the year's brief as a page. Retrieval over OCR'd letters favors boilerplate, so a question about renewals is better answered from the brief than from the letters.
- Until October 4, 2026 the pages were AnythingLLM's `mail` catalog (`jason anythingllm --sync --catalog mail`); that command was removed with the app.

## Reading it

- `jason mail` syncs and prints the last 30 days: what to act on, what to review, upcoming dates, and unscanned items. `--offline` reads the disk, `--days N` widens the window, and `--item <mail id>` prints one letter's text.
- The `mail_brief` MCP tool gives the same brief, narrowed by `kind` or `urgency`. `mail_item` gives one letter's record and text.
- Asking PostScanMail to scan, forward, shred, or discard mail is a person's decision.
