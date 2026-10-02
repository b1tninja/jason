# Jason skills

Jason is the HOA agent. PayHOA HTTP stays in the payhoa package. These skills are the documented use cases. A skill reads local data first (`jason-mcp` or the catalog) and calls a live API only when the skill says to.

The manager’s duties and the California statutes they sit on are indexed in [docs/community-manager.md](docs/community-manager.md). That page is an index, not a quotation of the code.

## Quote a California statute

Official section text comes from the lawlibrary MCP tools (`cite_law` / `get_section` over `US-CA`, newest session) or from the pages `jason export-authorities` wrote under `data/authorities/` from that same publication, which the `authorities` tool reads by citation. Do not invent a quotation. Do not scrape leginfo when a tool returns `text`. The pages in [docs/laws](docs/laws/README.md), `records.md`, and `duties.md` are Jason's summaries; quote the statute only from the exported page or the lawlibrary `text`, and say the session. A Title 10 section the duties cite is cut from the Commissioner's regulations as DRE publishes them, once `--fetch-publications` has brought that PDF down. A federal statute and a whole DRE publication are pointers in the export's manifest: read them at the source the pointer names, or in the `authorities` catalog in AnythingLLM.

```bash
jason export-authorities            # from the lawlibrary checkout in lawlibrary_home
jason export-authorities --list
```

1. `cite_law` for the citation the task already has (`CIV 5806`, `Civ. Code § 5800(a)`, `CIV 4000-6150`, `davis-stirling`).
2. `get_section` when the code and section number are already split.
3. `outline_law` or `act_law` for a span or a named act. `mutual-benefit` is an outline only.
4. `search_span` for words inside a code and a numeric span.
5. `place` before a Sacramento ordinance question. The answer is a miss. Do not fetch a municipal host.
6. A miss with reason `outside_us_ca` and a `statute` or `regulations` field names the next corpus. United States Code is `data/codes/US.sqlite`. One CFR title is `data/codes/US/cfr/{title}.sqlite`. Fair Housing regulations are title 24 of the CFR, not California Title 24 (the building code). ADA regulations are 28 CFR. NFIP regulations are 44 CFR. Those files may be absent until loaded; absence is still a miss. Do not scrape HUD, DOJ, FEMA, leginfo, Westlaw, or ICC to fill it.

A miss has `found: false`. `ordinance_absent` means the city or county code is not in the index. Quote only `text` this interface returned. The manager page is not a source of statutory words.

Amounts are integer cents. Unattended runs use `interactive=False` and fail fast (`KeeperAuthRequired`, `GoogleAuthRequired`). Do not open a browser unless a person passed `interactive=True`.

## Attach utility bills

Each month, unreviewed SMUD and City of Sacramento charges have no PDF.

1. List those PayHOA transactions.
2. Sync only the utility portal that has a pending match.
3. Upload the bill when the amount and date line up and the match is unique.

Identify SMUD and the City from the transaction text, not from the vendor list. Download a PDF only when a transaction still needs one.

```bash
jason sync-bills --dry-run
jason sync-bills
```

## Annotate a governing document

Declarations restrict the same subjects and define the same terms. The sentences differ. Compare subjects, then read the sentences that differ.

1. Identify the instrument by the document number on the recorder's stamp. Later amendments and annexations recite the declaration's number, and the county clerk-recorder index lists it. A city uses its county recorder. Sacramento's numbers are twelve digits: the first eight are the recording date and the last four are that day's sequence. The publication date is when that copy was issued. `citation_era` says whether a recording falls before or after the January 1, 2014 Davis-Stirling renumber. An unknown date stays unknown.
2. Tag a passage with a `Provision` (maintenance, rental, insurance, and the rest of that set). That tag is the concept. It is not a quotation.
3. Leave the annotation `unread` until the instrument body is in hand. A read annotation names the instrument's own section. Do not invent that section from a file name.
4. When the body cites a statute, record that citation as `prior_statute` if it is not the current section in `Annotation.statute`. A recording in the prior era is a reason to look for an old number. It is not itself proof the text uses one.
5. An amendment annotates the same provision and names the sections it changes. Compare its recording date with the original. Read the amendment against the original for that provision. A provision the amendment does not mention stays as the original left it.
6. Do not mark a provision superseded, and do not draft a CC&R amendment, from the statute index alone. The index shows that numbering moves. The instrument shows whether this association's text still uses the old number.

## Review a request against the governing documents

An owner submits a maintenance or architectural request. Read the request, find the governing-document file that applies, quote a passage from that file, leave an internal note with a recommendation, and tag the request when asked (for example `Association Responsibility`).

Do not approve, deny, or assign the request. Do not invent a CC&R quotation from a file name. Today `review-requests` quotes the request itself and matches document names. A passage from the document body needs the file bytes.

Pull attachments, comments, and notes before reviewing:

```bash
jason sync-catalog --only requests
jason sync-request-files
jason review-requests
jason review-requests --apply-tag "Association Responsibility"
```

`sync-request-files` writes `data/payhoa-files/requests/{id}/` with the files, `comments.json`, and `notes.json`. Local search uses `search_requests` and `get_request_local_export`.

## Publish an ownership sheet

For each known parcel in the association, read the assessor's current document date. When that date and document number match the local ownership database, do not call the recorder. When they differ, fetch the grantors and grantees and remember the new date.

A parcel's sale history is the list of document numbers back to the first conveyance. Start from the assessor's current document number and the grant-deed numbers already collected on the Membership workbook and in the Grant Deeds files. `SacramentoCountyRecorder.history` reads those instruments. A later deed links to an earlier one when the later deed cites that document number, or when the later grantor is the earlier grantee. Several earlier deeds can match; each one stays on the step. The assessor's deed-type token is `DocType`. `DocType.GD` is the description the parcel viewer prints for a grant deed, a corporate deed, a gift deed, and a joint-tenancy deed, and recorder filing 685 maps to that token. `DocType.QC` is a quitclaim deed, filing 689. `DocType.from_code` is the other direction. An easement token does not replace the owner. A deed of trust, filing 230, is not a `DocType` and does not transfer the fee. The trustor is the owner and the beneficiary is the lender. A reconveyance, filing 238, releases that deed of trust and does not transfer the fee. Its cross-reference is the deed of trust, so follow that number. A cited deed of trust recorded before the community existed is a different property. The next document number on the same day is someone else's instrument unless the parties are this buyer and the lender. An index cross-reference is the link between those instruments. A grant deed often has none. `instrument_kind` is fee, lien, or release. `party_roles` names the owner and the lender. `buyer_lien` is true when the deed of trust's trustor is the grant's grantee. `relate_instruments` labels the same-day neighbor and the cited document. A neighbor that cites the same number is the same lien. A reconveyance means the loan was paid and the owner stayed. A trustee's deed upon sale, filing 695, is the lien sale: the trustee conveys the fee to the buyer, often the beneficiary when nobody else bids, and the deed cites the deed of trust. Filing 694 is also a trustee's deed. The number before a developer grant is usually the notice of completion, and the next number is usually the buyer's deed of trust. A second name is kept from those rows when it is the same party; the county SearchText field does not combine with the last-name field. A notice of default, filing 531, and a notice of trustee's sale, filing 543, cite that deed of trust and do not transfer the fee. The trustor on that deed of trust is the owner who lost the property. A deed in lieu, filing 801, is the owner conveying to the lender instead. A later grant deed from that lender is the resale, not the sale. `foreclosure_deed` recognizes a trustee's deed, filing 694 or 695, and a deed in lieu, filing 801. Keep a trustee's deed when this grant cites it, or when the cited deed of trust names an owner already on the parcel. A trustee's deed to a lender, with no citation and no known trustor, stays off the parcel. `recorder_around` reads those numbers from the index. A neighbor that does not match is someone else's instrument. A name search of a grantor is not the chain. The same name is on other parcels, so those hits stay candidates until a document number ties them to this parcel. Three subdividers are pinned on the community as `developers()`. `public_reports()` is the Buildings tab: one Bureau file number for each phase, the flood building, the first conveyance, the annexation date, and the monthly assessment in cents. `catalog_reports` joins each file number to every pinned copy, and joins an annexation pin by the phase in its title. A bond-release letter stays a related file of that phase. It is the release, not the bond. The first conveyance is a deed date of that building, and it is not always the earliest deed. `opened` is the earlier day the original phase starts selling, the common-area deed. `issued` is the day the Bureau public report was issued, and a sale under that report does not record before it. `deed_in_phase` is true on or after the earliest of that issue date, `opened`, and the first conveyance. A few days before `opened` or the first conveyance still count when the day is not before the report was issued. An early developer deed can print the parent parcel (the land before the unit parcels existed) in its header and name the unit in its legal description; the unit parcels came later. `parent_parcel` says a printed number is the land, not a unit. `plan_unit` maps a unit parcel to its plan unit and `unit_parcel` maps back, for the blocks whose deeds print a parent parcel. A unit number places a deed only when the deed prints that block's parent parcel; `PlanBlock.parent_parcels` names them and `placement` requires one. Unit numbers are otherwise unreliable where a later developer numbered its buildings from scratch, so one number can name units in two buildings. A deed's legal description also names neighboring units for garages and exclusive-use areas. An address or the parcel number places a deed; a unit number on a letter is at most a candidate. Every unit's number under both numberings, and the numbers that collide, are in the private notes (mystique/notes/unit-numbers.md); `unit_parcels` lists every parcel a number can mean and `unit_number` is the MCP tool for it. `jason unit-charts` creates a spreadsheet that draws it: unit numbers against buildings under both numberings, parcels per unit number, and every sale by date and price with one series per building. The charts are Sheets charts drawn from the tabs beside them. `jason sales-charts` creates the conveyance-history spreadsheet: every deed with its process and price, conveyances per year stacked by process, median and mean price per year, every sale by date with one series per process, median first and latest price and mean years held by building, each owner's tenure, and deed price against the enrolled base. `jason equity-charts` creates the values-and-appreciation spreadsheet: a monthly market index of trailing medians, each unit's last price beside three references (recent comps by building or community, its own price carried by the index, and the assessor's value), appreciation in dollars, percent, and per year with rank and percentile, a building rollup, and a Unit lookup tab where picking an address fills the unit's figures, sales, and chart. The method is in the private notes (mystique/notes/ownership-history.md, "Views"); it is not an appraisal, and loan balances are not in the public record. `jason sync-characteristics` first copies the assessor's residential characteristics (living area, bedrooms, baths, year built) for each unit into `data/characteristics.db`, one public call per parcel; with them the sheet reads the market per square foot and by bedroom count, names each unit's plan from the specification's `FloorPlan` rows, adds a size-adjusted estimate, and draws the Trend tab: sale prices by building over time as a scatter with the community and building moving averages through it. The `unit_characteristics` tool reads the store. Do not treat a plan name as the builder's own where the specification inferred the plan; the measured area is the fact. The Markdown pages carry the same views for GitHub, with a page per building (phase, plans, every unit's standing, one gantt of all its tenures, sales by year) between the index and the parcels: Mermaid `gantt` tenure bars and a Value section on each parcel page, `market.md` with `xychart-beta` yearly series and a `quadrantChart` of the units, and matplotlib SVGs under `charts/` for the scatter-with-averages views (the `charts` extra; `--no-charts` skips them). An xychart carries the previous year's figure through a year with no sales; say so when quoting one.

**Reading the whole index cache.** The `index_survey` tool says what the cache holds and which filings fall outside every model. When a filing shows up there naming a community party, add it to the registry in `jason.community.filings` as a row with its family, sides, process, and effect, and write the lifecycle in [docs/recorded-instruments.md](docs/recorded-instruments.md); the lien tables, the association record, and the owner events pick it up from the registry. A rescission (720) or a cancelled default (616) cures a default and leaves the loan or lien open; only a tax default closes on a rescission. Do not read a cure as a release.

**Mechanic's liens.** `jason sync-liens` fetches the claims of lien, releases, bonds, and notices of action naming the developers, the association, and every owner; the association page then lists the construction-period liens against the developers, each parcel page its owners' liens, and the `mechanics_liens` tool all of them with a standing: open, in suit, action withdrawn, expired (unsued ninety days after recording, Civil Code section 8460), or closed. An expired lien is unenforceable but still of record; say both. Do not call a lien released because it expired, and do not call one live because it is of record.

**Solar leases.** `jason sync-solar` pulls every UCC filing the developer program's lease funds recorded into the index cache; the property history then states each unit's solar standing on its page, on `solar.md`, on the Solar tab, and through the `solar_status` tool. The model and its bounds are in [docs/recorded-instruments.md](docs/recorded-instruments.md#solar-leases-and-the-fixture-filings). Do not tell escrow a unit's panels were purchased because no filing was found; say no filing was found. Do not send a lease question to the company now trading as SunPower; the leases went to SunStrong Management. Do not read a filing shared by an owner's several units as a lease on each.

`held_units` is a bulk deed that names the parcels of one building a developer still held. Those are the parcels that developer sold. A parcel of that building missing from that deed had already been conveyed by the earlier developer, and a later deed of that parcel is a resale. `still_held` answers which of those a parcel is. A buyer who closed on `opened` has a notice of completion as the preceding number and the buyer's deed of trust as the next number. `phase_on` is the phase whose first conveyance is the latest one a developer grant can belong to. A street that already names a flood building uses that building, including a later sale after the next phase has opened. `parcel_block` is the parcel segment of the assessor number. One phase is one block. `phases_for_blocks` gives that block the phase of the flood building on it, including an address the flood range does not name. Each pinned developer is indexed under several spellings, including the recorder's misspellings (the developers are `developers()` in the specification). A deed from any of them is that developer's conveyance. Searching that developer as the grantor lists the homes they sold. `forward_hits` keeps a sale when the person being resolved is the grantee, so resolving a buyer against a developer hits that developer's deed to the buyer. The other buyers are other parcels. A hit is the possible root to load with the later deed. It is not stored until that chain reaches one developer and has no gap. `IndexCache` stores every document a search returns, its cross-references, and the filing code and description. Inferences are written back onto that row with `note` and `set_apn`. `instrument_kind` also classifies a notice of completion, a substitution of trustee, a death affidavit, an assignment, and an easement. Those, and a fee that only restates the same owner into a trust, do not advance a buyer walk. An association or another community deed is not a unit sale. `backfill_empty_kinds` refreshes blank-kind rows one document at a time. `cache_community_names` searches the association's indexed names with no date floor and labels association, phase, and other association parties. `cache_known_parties` searches each known owner once by full indexed name without fanning out. `builder_leaf` starts on the developer side inside a date window: leaf 1 is the developer grant, leaf 2 is each buyer next deed across every sale before any branch goes farther. Same-day neighbors of a known recording are cached too. `descend` uses those builder leaves first, then one current leaf. A lender is not searched. A party matches when the same words identify both names, so an extra given name or a missing junior is a different person. The developer side stops after the sale and one resale, so other subdivisions are not walked through every later buyer. `chain_ready` is the store test: one developer grant, no gap, and one prior on each later deed. A meet is not stored until that test passes. `solved_numbers` is every document on a chain that already reached one developer with no gap. `forward_sales` and `forward_hits` leave those numbers out when they are passed as `exclude`. The chain still keeps an earlier deed that conveyed the land to that developer when its number is known. A lender, a land investor, or another builder that conveyed the land between those developers is not a developer. A step with no document number connecting it stays a gap. The recorder matches a last name from the front of the indexed name, so a search for the project word finds the declaration and the phase annexations, and it does not find a developer whose name starts with another word. Notices of completion are searched under each pinned developer. The association's deeds are searched under `index_association()`, which covers ASSN, ASSOCIATION, and ASSOC. Those three spellings hand off to each other. A person's surname and given name hand off when the index drops an initial or a third name. The same words in either order are one person, so a deed indexed under `FIRSTSURNAME SECONDSURNAME` hands off to a later deed indexed under `SECONDSURNAME GIVENNAME`. A company that keeps an extra word does not. `nearby_numbers` is the same-day sequence just before a developer deed, which is where the notice of completion sits. `closing_numbers` is that preceding number and the following one. A developer's notice of completion is the preceding number. A developer's partial reconveyance, or the buyer's deed of trust, is the following number. A later developer deed that cites the first number is the same conveyance, and the secured roll keeps the first number. `document_stamp` is that roll number: the recording date plus the page. A name search wider than the limit is not followed; `NARROW_FILINGS` searches that name again as a grant deed, a quitclaim, a UCC financing statement, and a UCC termination. `name_candidates` sets the assessor's owner beside the recorder's parties for that parcel. A one-letter token is a candidate for the one longer word that starts with it, and a vowel-stripped token is a candidate for the full word, so `FMLY` is a candidate for `FAMILY`. `OwnerName` compares equal, and the deed chain hands off, when those candidates account for every remaining word and the names already share another word. A candidate alone is not a match. `OwnerName` is not hashed. `merge_candidates` counts how many owners showed the same pair. `OwnershipStore.remember_history` keeps the document numbers in `data/ownership.db`. Those numbers are what pick the tax bills for each sale. `document_numbers` reads the stamps out of Grant Deed filenames and sheet cells. `find_deeds`, `granted_by`, and `granted_to` select conveyances by party. A shorter name matches the index form that continues it, so `EXAMPLE COMMUNITIES` matches `EXAMPLE COMMUNITIES LLC`. `paths` walks backward from one document number and keeps each branch. `community.deed_numbers()` is the pinned set, read from those Grant Deed filenames. If `data/ownership.db` is gone, call `history` with `deed_numbers()`. `gaps` are the deeds that still do not reach an earlier document and are not a developer grant. A cited number that is not in the chain is an unknown, as is a parcel whose chain has no documents. The history report lists both so the next search has a grantor or a document number. `classify_deeds` splits a search into rows already pinned and candidates. A candidate is not a pin. A reconveyance process names the filings that complete that one step. A developer closing expects the notice of completion and the buyer's deed of trust, and a run of deeds into the same buyer sits between the grant and that lien. A blanket release expects a partial reconveyance that cites the builder's deed of trust. A foreclosure is complete when the trustee's deed cites the deed of trust, and the grantee is not searched. An REO resale is complete when the grant cites that trustee's deed. A resale is complete when it cites the prior deed. A restatement into the same owner's trust does not continue. A re-recording is the same grant recorded again within `TWIN_DAYS` with the same parties, to correct the first instrument; the first recording is the conveyance, `earlier_twin` finds it, and `twins` pairs them across a search. An excluded transfer is a grant between family or affiliates, read from a shared surname or leading company word by `family_transfer`; it continues to the grantor's own deed and does not reassess. Each process says whether it `reassesses`. `jason.community.calendar` reads the tax bills against those flags: a reassessing deed lands on the bill for the next January 1, a rise in the year the building was finished is construction, a rise under the factored base from the last sale is a Proposition 8 restoration, a small rise over it is an improvement, a rise well over it with no deed is a sale the chain lacks, a sale below the base is a decline, and a year most parcels rose in with no deed is a market restoration. `audit_chains` runs those checks and the phase, developer, order, and price checks on every stored chain; a finding names the record to read next.

The secured roll is a separate catalog (`data/secured.db`), joined to a parcel on the APN. The county updates that roll once a year. When the assessor's document date is newer than the roll's recording date, the property has sold and the roll's owner and mailing address are the previous owner's. Do not treat that row as current title.

`jason sync-tax` writes each bill into `data/tax.db`, including the assessed value, the ad valorem levies, and the direct charges. The print PDF for each bill is saved under `data/tax-bills/{parcel}/`. The ad valorem lines are a rate times the net assessed value. The countywide line is 1% of that value. Direct charges are the dollar amounts printed on the bill. They are not a percent of the sale price. They are also not the same amount every year: each district sets its own. `tax_split` separates the value-based tax from the direct charges. `direct_levies` lines those charges up by code, and `follows_reassessment` reports whether a charge scaled in a year the enrolled value rose by more than the 2% factor. The bill is printed once a year, and a newer assessor document date means it can still name the previous owner.

Write the rows into a new Google spreadsheet. Do not update the Membership workbook (`KnownFile.MEMBERSHIP`). Account, email, board role, and rented stay on that workbook.

Do the county work in this order.

1. `jason sync-tax` fills `data/tax.db` and saves each bill PDF under `data/tax-bills/{parcel}/`.
2. `jason county-report --local` reads that catalog and the ownership database. It prints how many rows each tab has. It does not call Google.
3. `jason county-report --interactive` reads the assessor, reads the pinned grant-deed numbers from the recorder, stores that chain, and publishes one spreadsheet. `--no-browser` skips opening it.

The spreadsheet tabs are Ownership, Deed history, Association taxes, Sale prices, and Taxes due. Ownership is the assessor's current instrument. Deed history is the pinned grant-deed chain, and a gap is a pinned deed that still does not reach an earlier document. Association taxes are the common-area bills. Sale prices on the spreadsheet are the enrolled value in the latest year that value rose by more than 2%, with the current document number when ownership has that parcel. That enrolled value is the county base-year figure. The consideration is the amount the deed's documentary transfer tax was computed on: fifty-five cents per five hundred dollars, and on these City of Sacramento deeds a city tax of two dollars and seventy-five cents per one thousand dollars. `deed_price` reads those two amounts. When they agree, that dollar is the price. When the deed says the tax is not payable, there is no price. The enrolled figure is not that price. Taxes due calls the newest year's unpaid balance due, and an unpaid older year delinquent. The Membership workbook is left as it is.

```bash
jason sync-tax
jason county-report --local
jason county-report --interactive
jason county-report --interactive --no-browser
jason ownership-sheet
jason ownership-sheet --no-browser
```

The command opens the new spreadsheet with the standard-library `webbrowser` module when that module imports. `--no-browser` skips the launch.

## Answer a title, lien, or escrow question about a unit

A board member asks what is on a unit, an escrow officer asks what the association knows before a sale, or someone hands Jason a document number. Everything comes from the stores; nothing is searched unless the syncs are stale.

1. `unit_brief(apn)` first. It is the unit on one page: owner and instrument, the chain and last price, the open liens while the owner held it, the solar standing, taxes, the membership check, owner events, audit findings, the home, and the value figures, with the caveats attached. `jason brief APN` prints it as Markdown.
2. For a sale, `escrow_brief(apn)` or `jason brief APN --escrow`. Its `tellEscrow` lines are what the association can say: whether its own assessment lien stands, any default or sale notice of record, a mechanic's lien and whether it expired, other open liens, the solar lease standing, taxes, and a death on title. It does not state a demand amount; PayHOA holds the ledger.
3. For the whole community, or for "what needs a person", `title_watch(attention=True)` or `jason title-watch --attention`: each lien joined to a unit, read against the title as one standing (in default, a default gone quiet, stands, a prior owner's lien with no sale since, a release the association owes under Civil Code 5685, presumed paid at a sale, lapsed, expired, runs with the land). `standing="RELEASE_DUE"` is the association's own duty list. The same rows are `liens.md` in the property-history pages, and every lien row in the two briefs carries its `standing`.
4. For a document number, `lifecycle_of(number)`: which chain, lifecycle, or record it sits in, the whole lifecycle with its status, and the statute it runs under. For a code or a name, `explain_filing("389")` or `explain_filing("release of mechanics lien")`.
5. To read the instrument itself, `read_deed` for a scan on disk, else `recorder_detail`.
6. When the newest filing may be missing, run `jason sync-solar`, `jason sync-liens`, and the ownership refresh, then ask again.

Say the bounds the brief carries. A lien indexes a person, not a parcel. Each lien row carries `nameMatch`; when `namesakeRisk` is set, the filing drops a middle name the deed carries (a lien on the owner's surname and given name alone that a release later shows was a namesake's), and escrow's line says to confirm it is this owner. The solar program's lessor and a loan recorded at a closing tie a filing to the unit on their own. A prior owner's loan with no reconveyance in the cache is presumed paid at the sale that ended their tenure, and the brief lists it apart from the current owner's liens. An expired mechanic's lien is unenforceable and still of record, and so is a lapsed judgment or tax lien past its statutory life. A rescission cures a default and releases nothing. No solar filing is not proof of purchase. The value figures are comps, not an appraisal. Do not approve, deny, or assign anything, and do not promise escrow what the ledger has not confirmed.

## Read a recorded document's text, and order the copies the records lack

A recorded instrument's own text relates it to others: the declaration it amends, the annexation it rescinds, the units it annexes. `read_document(path)` reads one extract on disk into the concept records (stamp, title and phase, citations with their relation, annexed property, declarant, changed sections); `document_readings()` reads every governing extract and lists the supersessions the texts state with whether the specification pins each. A reading is evidence: a rescission it states is pinned in `mystique/annexations.py` as a `Supersession` with its source only after a person reads the recital. OCR garbles stamps and ranges, and an image-only PDF reads as nothing; [docs/document-readings.md](docs/document-readings.md) says what the parsers miss and the path to model-based extraction over the page images.

```bash
jason read-documents
jason read-documents --search "easement reserved over A.C.A. 3"
jason read-documents --extractor claude
jason records-request --pages
```

`read-documents` scores a reader against the pinned facts: the regex parsers by default; `--extractor ollama` the local vision model over the page images through Ollama (qwen3.5:9b unless `--model` names another local vision model; no key, nothing leaves the machine, a minute or two a document); `--extractor claude` the hosted model, which needs the `models` extra and `ANTHROPIC_API_KEY` and otherwise sends nothing. `--search` finds the passages that answer a question, for the person to read. The `extraction_scorecard`, `read_scan`, and `passage_search` tools do the same. A model's reading is evidence like the parsers'; the scorecard says what to trust, and nothing is pinned by being read.

The open-source tools around this, what is installed, and how each joins are in [docs/document-tools.md](docs/document-tools.md): `jason ocr-documents` writes a text layer beside each image-only PDF with whichever OCR engine is available (Docling with RapidOCR, PyMuPDF with Tesseract, or the text AnythingLLM's collector already extracted at upload, read from its storage folder) and says so when none is; `jason read-scans` reads each image-only governing PDF with the local vision model and keeps the readings under `data/readings/`; the records request then lists an instrument such a reading covers at priority 4 with the file named, and a person verifies the stamp on the image before dropping the order. `jason anythingllm` prints the entry that registers jason-mcp as agent tools in AnythingLLM Desktop (`--write` installs it) and `--ask` puts a question to its workspace through the `anythingllm_query` tool, which needs `ANYTHINGLLM_API_KEY` from the app's API Keys page. Do not read the app's database for a key, do not pull a model or install PyTorch as a side effect, and do not pin what a model answered.

`records-request` writes `data/reports/records-request.md` and `.csv`: the instruments the association's record names with no recorded copy on disk, each with the order form's fields (document number, book and page, title, recording date), why the association wants it, the page count (marked when estimated; `--pages` reads it from the index), plain or certified, and the cost at the county's fees. The `records_request` tool returns the same rows. Confirm the fees and the form against the county's page before sending; Jason does not send the order.

## Answer a records or duty question

Someone asks what the association must keep, where a kind of record lives, or what a duty requires and where the governing documents speak to it.

```bash
jason duties
jason duties --brief "Assessments"
```

`jason duties` writes `records.md`, the Civil Code 5200 inventory (each kind with its citation, meaning, retention, the PayHOA folder or Drive rule or known file that holds it, how many files the catalog has there, and the gap when nothing is pinned or nothing is on hand, plus the governing copies with their recorded status and whether a copy is an unsigned draft), and `duties.md`, one brief per duty anchor from [docs/community-manager.md](docs/community-manager.md) with the statute, the artifact, the records, the cadence, what Jason produces, the limit, and the passages the governing documents and the law notes give for the duty's questions. The `records_inventory` and `duty_brief` tools return the same. A gap is a place to look, not a finding that the record does not exist; a passage is the document's own words for the person to read; and a brief decides nothing about whether a duty is met.

For a question a retriever answers better, `jason anythingllm --sync` keeps three catalogs in AnythingLLM, each its own folder and workspace: `authorities` (the statute pages lawlibrary exported and the DRE publications), `association-records` (the governing documents, annexations, policies, resolutions, and public reports), and `jason-pages` (the generated pages and these instructions). The shared association workspace holds all three. Ask the catalog that holds the answer: a question of law goes to `authorities` (`anythingllm_query(question, catalog="authorities")`, or `jason anythingllm --catalog authorities --ask "..."`), because in the shared workspace the long public reports crowd out the sections. Each source comes back with its catalog and shelf; a source from `jason-pages` is a summary and is not quoted as the law or as the record. The duty briefs already quote the exported statute for each duty's own sections, and fall back to the law notes only before an export.

## Classify the document library and find a record

Someone asks where the 2025 minutes are, whether the association holds its tax returns, or what a file in Email Attachments is. The library is the PayHOA document catalog, classified.

```bash
jason sync-catalog
jason library --fetch        # download what is not on disk, read it, classify it
jason library                # reclassify from the cached text
jason library --model        # also ask the local model about files no rule placed
jason library --score        # how the phrase rules agree with the name rules
```

The chain keeps each file's method. The specification's name and folder rules (`mystique/documents.py`) go first. Then come the title and body phrase rules over the file's own words; an extract's header is dropped so the file name cannot leak in. Last, a local model with every kind defined, which answers from the closed list and never overrides a rule. Refinement rules then add a 5200 record the kind alone does not give: the board's written approval of a vendor's proposal in the minutes (a)(5), reserve balances in a treasurer's report (a)(7), a check register (a)(10), a balcony inspection (a)(15). The bank accounts are facts in `mystique/banking.py` (operating, reserve, and a reserve CD); the reserve accounts' statements and letters are reserve records.

The same file filed twice (a meeting's minutes and its copy in Email Attachments) is one file: search and the inventory merge copies by their SHA-256 and keep every record their folders give. `library_search(kind, record, period, words)` finds files, newest first; `library_status()` is the coverage; `library_text(id)` is a file's words. Confidential files (bank statements, owner histories and statements, delinquency files, executive sessions, escrow requests, the member list, the Confidential folder) are classified like any other and held back unless asked for, and they never go to AnythingLLM. `jason duties` counts each 5200 record from the library, with the newest file. A template or a photo is classified so it can be set aside; it is not a record. A phrase or model answer is evidence about a file, not a pin: when it matters, open the file.

## Review what recorded this month

Once a month, or before a meeting, list what the county recorded that touches the community.

```bash
jason sync-solar
jason sync-liens
jason digest --days 30
jason recent-filings --since 2026-09-01
```

`board_digest(days=30)` (or `jason digest`) is the start: what recorded, owners in default with the newest notice's date, releases the association owes, prior owners' liens with no sale since, how many liens stand on current owners, the association's own open liens with other associations' liens set apart, and the solar standings. Each list is capped, and `more` names the tool with the rest. It decides nothing; an owner in default to another association is not the board's matter.

`recent_filings(since)` returns every transfer, lien step, owner event, association lien, and governing instrument on or after that date, each with an action: a new owner goes to the membership record and the escrow file; a step on the association's own lien goes to collections; an owner's notice of default is watched for a trustee's deed, which changes the member; a death on title goes to the membership record; a governing instrument is filed under Civil Code 5200. `assessment_liens()` is the collections view of the association's own liens, unit by unit, under sections 5650 to 5720. The monthly delinquent handoff below stays the handoff; Jason does not submit an account to an agency or start a foreclosure.

## Write the property histories

One Markdown report per parcel and one spreadsheet, from the stores on disk. Nothing is searched. The report is the chain of title read against everything else: each deed's process (developer closing, resale, foreclosure, REO resale, excluded transfer, re-recording, restatement), the price computed from its transfer tax, the base the next bill enrolled, how the deed was placed on the parcel (the parcel number or plan unit on the scan, a citation, or a name handoff), the instruments a process expects beside it (notice of completion, buyer's lien, partial reconveyance, trustee's deed), the tax calendar, the audit findings, and a Mermaid diagram colored by process. An open parcel lists the instruments a pass already placed on it that no chain reaches. A sale with no readable price shows the enrolled base as a stand-in, marked as such, and a "Why unpriced" column names the cause. The ten common-area parcels get a report too: the association deed the assessor lists, back through the land deeds, with no developer or member checks.

```bash
jason property-history
jason property-history --sheet --no-browser
jason property-history --spreadsheet SPREADSHEET_ID --no-browser
```

The Markdown goes to `data/reports/property-history/` with a `README.md` index. `--sheet` creates a new spreadsheet with the tabs Parcels, Deed chain, Related documents, Sale prices, Tax calendar, Audit, Open items, plus the county tabs Assessor current, Community deeds, Association taxes, and Taxes due; headers are frozen and bold and columns sized. `--spreadsheet` refreshes that spreadsheet in place, padding shorter tabs so nothing stale survives. Only the spreadsheet step needs Google. The Membership workbook is never written; a member's account, email, board role, and rented flag stay there.

Two files beside the stores carry what a person supplied. `data/deed-prices.csv` holds transfer-tax figures read off a scan whose text layer garbled the line; it wins over the extract. `data/parcel-notes.csv` holds facts about a parcel that no record states, each with a date and a source, and the report prints them. A death record the assessor lists as the current instrument (type DETH) is shown as one and moves no title; the trust or the surviving owner continues. Each report also lists the liens, defaults, loans, and releases that name an owner, paired into lifecycles by `jason.community.filings`, and marked by whether each opened while that owner held the unit. The association's own record, in `association.md` and the Governing records and Liens and notices tabs, ties the recorded governing instruments to the Title 10 section 2792.23 deliveries phase by phase and lists the assessment liens the association placed, the utility liens and the tax-default notice recorded against it, and its request for notice. The catalog of filings is [docs/recorded-instruments.md](docs/recorded-instruments.md). `load_parcel_histories` assembles the model, `build_parcel_history` is the pure builder, `parcel_markdown` and `mermaid_conveyances` render it, and `property_tabs` lays out the tabs. `scan_index` reads every deed extract on disk and `placement` says whether a scan places an instrument on a parcel, contradicts it, or only matches its address.

## Provide a membership list or a mailing

Two different jobs share the same names.

An association mailing is the association writing to its own members. One envelope per destination. Every grantee at that address goes in the name block. Nobody is marked first or primary. The envelope template’s `First_Owner_Full_Name` field is the wrong shape. Use a name block and a mailing address. When the assessor has no mailing address, use the situs address. The secured roll's mailing address is the county tax-bill address for that APN. It can name the previous owner when the roll is older than the current deed. A second address for one owner comes from the Membership roster, not from the deed.

A member’s request to inspect or copy the membership list is an association-records request. Civil Code § 5200(a)(9) names that list. Section 5225 requires the member to state a purpose reasonably related to membership. Section 5220 opt-outs stay off the list until the member changes them. Section 5260 says a change to list information is in writing. Section 5230 says the association does not sell a member’s personal information. Section 5216 keeps Safe at Home participation confidential and uses the Secretary of State substitute address. Deadlines and the place of inspection are in [docs/laws/records.md](docs/laws/records.md).

The ownership sheet is recorded title. It is not the membership list. Grantees on a deed can be a trust, a company, or a prior owner. The Membership workbook is the list the association keeps. Jason prepares either document. Jason does not decide that a member’s purpose is good enough, and Jason does not hand the list out.

## Answer a budget or balance question

A board member asks how the year is tracking against the budget, which categories are over, or what is in the reserve accounts.

```bash
jason budget                 # sync from PayHOA, then print the brief
jason budget --offline       # print the last snapshot without calling PayHOA
jason accounts
```

`jason budget` stores one snapshot per year in `data/payhoa/finance-<year>.json`. It holds the budget against actual for the full year and year to date, each month's income and expense, the category distributions for both ranges, the bank and deposit accounts, and collection progress. `budget_status()` and `bank_accounts()` read it without calling PayHOA, and `board_digest` carries its headline. A category gap is year to date, so the actual meets the budget for the same months. A parent category's "Total for" row stands for its own line. The accounts are named from `mystique/banking.py`, including an account PayHOA lists by name with no last four. The balances are Plaid's, as PayHOA last refreshed them, and can lag the bank; the statement in the library is the record. The payhoa client can also edit a budget month (`update_budget_item`) and copy a past year into a draft (`create_budget_draft_from_historical`). Jason does neither on its own: changing the budget is the board's decision, taken in an open meeting.

## Answer a pest control or pesticide question

A resident or board member asks what was sprayed, whether it is safe for children, pets, bees, or the creek, who handles a pest, or whether the vendor follows the rules.

```bash
jason pests --fetch     # each product's EPA and California registration, stamped label, and safety data sheet
jason pests             # products, label checks, rodent stations, visits by building, inspection reports
```

Start with who is responsible. The declaration says who pays for the wood-destroying pest program and common-area repairs, and the rules say who handles pest control inside a unit (the association's are in mystique/notes/pest-management.md).

Name a product by its EPA registration number, and quote the safety data sheet and the label, never memory. The label governs use. The SDS gives the hazards and first aid. For an exposure, give Poison Control (1-800-222-1222) and the agricultural commissioner (1-87-PESTLINE).

A label check marked as a finding is what the vendor's own record shows. A question is something the record cannot settle. Do not tell a resident a product is "safe". Say what the label and SDS say, and who to call. Jason never directs an application or changes the contract. See [docs/pest-management.md](docs/pest-management.md).

## Answer an insurance question from the policies

A board member, owner, or lender asks what the association's insurance covers, its limits, deductibles, carriers, or when a policy renews.

```bash
jason policies --fetch                      # read the sheet, fetch each policy's papers, read the declarations
jason policies --policy master              # one policy's terms, documents, and findings
jason anythingllm --ask "..." --catalog insurance   # the policies' own words
```

Answer from the declarations and forms, not from the sheet or memory; the sheet can lag a renewal. Quote the limit, deductible, and term the declarations print, and say which document. A finding is a lead for the board and agent, not a coverage opinion; coverage of a particular loss is the carrier's answer. See [docs/insurance-policies.md](docs/insurance-policies.md).

## Trace the maintenance history and claims by unit and building

A board member asks what has happened at a unit or a building: the work done, the leaks and collisions, the claims, and what they cost.

```bash
jason incidents --fetch                    # download the Drive paperwork mystique/incidents.py names, then read everything
jason incidents --building 8               # one building's history (--all adds routine upkeep and inspections)
jason incidents --address "1234 Example Way" # one unit's history
jason incidents --claims --private         # the events with an insurance claim, with their snippets
jason incidents --work maintenance         # the maintenance history
jason incidents --link                    # search Drive, Gmail (headers), the ledger, the minutes, and the mail for each event's documents
```

An event is the rules' reading of the paperwork: proposals, invoices, change orders, reports, and claim letters, grouped by unit, cause, and date. Its work is the maintenance history; whether it was more than upkeep is read only from a claim on file. "Sudden, no claim" names a leak, break, or collision no claim was filed for; whether a peril was covered is the insurer's answer, not Jason's. Read the documents before citing one. A claim or loss file is confidential: give its date, place, cause, amounts, and claim number, not its contents, unless a board member asks. Never read or quote the medical or veterinary records, which the fetch never downloads. Who pays for interior damage is the declaration's and the board's call (the declaration's section on consequential damage), not the history's. See [docs/incidents.md](docs/incidents.md).

## Read a vendor portal and verify its bills

A board member asks what the pest control company did, what it applied, what it billed, or whether the payments and attached invoices are right.

```bash
jason vendors --sync       # sign in with the Keeper record (proactive_record_uid); download what is new
jason vendors --verify     # PayHOA payments against the vendor's own payments and invoices
```

The portal is the vendor's record. The visits, products, and EPA numbers are what the technician entered. A portal payment that PayHOA lacks may be an owner's own payment or a payment from another account. An attachment that is not the invoice the vendor applied the payment to is a finding, not proof of a wrong payment. An owner's property can sit on the association's master account; say so when its tickets appear. Do not pay, re-attach, or recategorize anything. The treasurer does that. See [docs/vendor-portals.md](docs/vendor-portals.md).

## Read the utility bills, forecast them, and audit their payments

A board member asks what the utilities will cost next year, whether a meter shows a leak or a short, or whether past utility payments carry the right bill and split.

```bash
jason utilities                         # parse new bills; accounts, anomalies, next year's forecast against the budget
jason utilities --water-increase 0.1    # the same, with a 10% City water scenario from July 2027 (not an adopted rate)
jason utilities --account ACCOUNT --service water_irrigation
jason utilities --payments --fetch      # audit every SMUD and City payment in PayHOA
```

Say what the bills say. A meter, size, service address, or parcel comes from the bills. The purpose of an account comes from `mystique/utilities.py`. An anomaly is a reason to look at a meter, not a finding of a leak. A catch-up read after bills with no usage is an unread meter. A forecast names its scenario, and SMUD's 2028 prices are provisional. In the payment audit, "paid twice" is confirmed by the next bill's credit. A payment without that credit is reported as a question, not a double payment. Do not split, recategorize, or re-attach a PayHOA transaction. The treasurer does that from the audit's expected split. See [docs/utility-bills.md](docs/utility-bills.md).

## Check the mail

A board member asks what came in the mail, whether a renewal or a notice arrived, or what is due soon.

```bash
jason mail                   # sync PostScanMail, then what arrived in 30 days: act on, review, dates
jason mail --offline --days 90
jason mail --item 6182234    # one letter's text
```

Name the sender, the arrival date, and the kind. Quote a letter only from its scanned text (`mail_item`). The sort reads words: a legal notice or cancellation is for a person to read now, and a listed date is where the letter puts one, not a ruling on the deadline. A policy number the letters print is a reading until a person pins it on the building. The mail catalog in AnythingLLM leaves out credential letters and, unless asked, confidential kinds. Do not ask PostScanMail to scan, forward, shred, or discard. See [docs/mail.md](docs/mail.md).

## Look up a past meeting

A board member asks what was said or decided at a meeting, who attended, or which meetings have no record.

```bash
jason zoom                        # sync the Zoom account, then every meeting with its next steps and the schedule's gaps
jason zoom --offline --kind board
jason zoom --meeting 2026-09-15   # one meeting's AI summary, speakers, attendees, and transcript
```

Name the meeting by date and topic. Quote only from the transcript (`zoom_meeting`), and say that speech recognition misreads names and numbers. The AI Companion summary is not the minutes: it records no roll call, motion, or vote, so do not report a decision from it as adopted. A board meeting's recording can run into the executive session; an executive session's or a hearing's text is held back unless a director asks. A gap on the schedule is a reason to look, not proof no meeting was held. See [docs/zoom.md](docs/zoom.md).

## Find a meeting's records

A board member asks for a meeting's minutes, whether minutes exist, or what recordings are kept.

```bash
jason meetings                  # every meeting with its agendas, minutes, transcripts, summaries, and recordings, and the checks
jason meetings --date 2026-07-07
```

Say where each record is (Zoom's cloud, jason's copy, Drive, the PayHOA library). "No minutes found" means not found in those places. A kept recording is a finding against the Decorum Rules, but may be under a litigation hold: never suggest deleting it. Do not quote a transcript that runs into an executive session unless a director asks. See [docs/meetings.md](docs/meetings.md).

## Schedule a disciplinary hearing

The board decides to hear a violation or a charge for common-area damage.

```bash
jason hearing --address "1234 Example Way" --violation "the board's words"   # dates and a notice draft; changes nothing
jason hearing --address "1234 Example Way" --violation "..." --date 2026-10-20 --time "6:30 pm" --create --yes
jason hearing --address "1234 Example Way" --violation "..." --doc --owner "Name" --matter "Trash Cans" --yes   # the notice as a Doc
jason letter --template decision-notice --name "Notice of Decision - 1234 Example Way" --set DECISION="..." --yes
jason hearing --list
```

The violation is the board's statement, never jason's. The notice must reach the member at least 10 days before the hearing (Civil Code 5855(a)), and the draft carries what 5855(b) requires. Leave the owner's name to the secretary. Schedule on Zoom only when a person asks with `--create --yes`. jason never sends the notice, never decides the discipline, and never writes the decision; the decision is due in writing within 14 days (5855(f)). A Doc made from a template lists its unfilled `{TOKENS}`; say which are left. See [docs/zoom.md](docs/zoom.md) and [docs/letters.md](docs/letters.md).

## Keep the board's action items and prepare the next meeting

A board member asks what the board needs to decide, wants the next agenda drafted, or wants a board packet.

```bash
jason board                                  # the open action items
jason board --set cost-centers-not-kept --status proposed --owner Treasurer
jason board --agenda <last agenda Doc id> --previous 2026-09-15 --tech-contact "Name, (916) 555-0100, help@example.org"
jason board --packet                         # the board packet for the next meeting (data/board/packet-<date>.md)
jason board --sheet <sheet id>               # read the board's edits from its Sheet, then write the list back
```

An action item is a matter the records show the board must decide; never state the decision. The agenda draft starts from last month's Google Doc (read-only) the way the secretary copies it: it keeps the standing items and the decorum rules, adds what an all-Zoom meeting's notice needs (CIV 4926(a)(1): technical instructions, a help contact's telephone and email, the individual-delivery reminder) and the roll-call rule (4926(a)(3)), gives the notice deadline (4920), and puts litigation and collections items in executive session (4935). In November it warns that a meeting where ballots are counted cannot be held entirely on Zoom (4926(b)).

The board packet researches each open-session item in depth: background, the question, the statute text quoted from `data/authorities`, the facts re-read live from the review that found the item, the evidence, options, a draft motion, any notice of its own, and deadlines. Executive session items are listed by title only. To go deeper on one item, read its evidence commands and documents (the MCP tools `cost_centers`, `reserve_transfers`, `developer_securities`, `document_models`, `library_text`, `authorities`) and add what they show under the item; quote documents only from their text, and mark a reading as a reading. Nothing is written to Google Drive without the board's approval: copying last month's Doc and inserting items (as suggested edits, `write_mode="SUGGEST"`, a Developer Preview feature) are actions a person approves first. See [docs/board-agenda.md](docs/board-agenda.md).

## Plan the reserve contribution from the study

A board member asks what to budget for reserves next year, what the study expects to spend, or when the next study is due.

```bash
jason reserves               # next year's plan beside the budget and the reserve accounts
jason reserves --year 2028
```

Quote the study's own figures and name the study (fiscal year, preparer, date). The contribution per unit uses the association's unit count from the specification. A study that counts otherwise is flagged. Percent funded is the statute's formula, not a target. A planned expenditure is the study's schedule, not a purchase. The board adopts the funding plan in the budget. See [docs/reserve-studies.md](docs/reserve-studies.md).

## Review payments against their invoices

A treasurer asks whether past payments carry the right invoice and category, or whether anything was paid twice.

```bash
jason invoices --fetch                 # read all transactions and attachments, then review
jason invoices --payee "Pro Active"    # one payee's findings
```

Report findings as questions for the treasurer. The same file on two payments of the same amount is "possibly paid twice" until the bank shows two debits. A returned payment is not a payment. A reserve reimbursement carrying the operating invoice is not a duplicate. A scan is unchecked, not wrong. Do not re-attach, re-categorize, or ask a vendor for a refund. See [docs/invoices.md](docs/invoices.md).

## Monthly delinquent handoff

Once a month, list accounts that are still past due, with unit, owner, balance, and past due, for a person to hand to the collection agency.

Do not submit accounts to the agency portal. The sheet is the handoff.

```bash
jason reports
jason who-owes
jason who-owes-sheet
```

`who-owes-sheet` writes Unit, Owner, Balance, and Past due into `google_sheets_spreadsheet_id`. It refuses to run when that id is empty.

Before the handoff, read the ledger beside the recorded liens: `association_collections()` (and the collections section of `jason digest`). Each account gets one standing. **Release due** is a paid account whose lien is still of record; Civil Code 5685(a) gives the association 21 days from payment to record the release, so it goes to the board first. **Lien secures debt** carries the section 5720 question: under $1,800 of assessments, fees and interest excluded, foreclosure is barred unless more than 12 months delinquent. The ledger's past-due figure can include fees, so the answer is the board's. **Owed, no lien** carries the steps a lien would need: the certified pre-lien notice 30 days ahead (5660) and the board's open-meeting vote in the minutes (5673). Jason records nothing, sends nothing to an agency, and starts no foreclosure.

## Assemble a reserve study update packet

The reserve study preparer asks each year for an update packet. "Since our last report" starts the day after the last report the preparer delivered.

Jason gathers the items for a person to review. Jason does not email the packet. Copies of the files go in `data/reserve-study-packet/`.

1. **Current operating budget.** The year's pro forma budget in the library (`Financials/<year>/`).
2. **Current financial statements.** The latest complete treasurer's report under `Confidential/Complete Financial Statements/<year>/`: balance sheet, budget performance, budget vs actual, profit vs loss, general ledger, and the bank reconciliations for the operating account and the reserve account. The redacted copy under `Financials/<year>/` leaves those figures out.
3. **Reserve account bank statement.** The latest statement of the reserve account named in `mystique/banking.py`. It may be newer in `Email Attachments/` than in the confidential statements folder.
4. **Reserve expenditures since the last report, with invoices.** Select the reserve bank account, not a category: a reserve expense category may hold only part of the reserve work. A reserve line is sometimes only a transfer that reimburses the operating account. That split is awkward. Always find the matching transaction, and do it whenever the reserve line has no PDF.

Match a reserve transfer this way:

- The same bank `transaction#` on the other account is the other half of the transfer. Those pairs have no invoice.
- A reserve description `Online Transfer to CHK ...` (the operating account's last four) is reserve cash sent to operating to cover a payment operating already made. The expenditure is the operating charge of the same amount. That charge can be weeks earlier. Its payee, date, and PDF are the ones to send. The PDF on the reserve transfer is a copy of that invoice. When a reimbursement has no operating-side transfer row in PayHOA, the match is the vendor charge, by amount and by the shared PDF.
- A reserve line with no PDF still gets a match. A transfer from operating with no PDF can be the funding for a reserve payment the same day that has the invoice. Count that payment once.

Leave these off the expenditure list. They moved cash, or they are the analyst's own bill: the monthly transfers in from operating (the reserve contribution), a transfer to a reserve CD, a service charge and the transfer that put it back, and the preparer's own invoice.

5. **Bids or estimates for upcoming reserve work.** A proposal for work already invoiced is the bid for a finished job. Owner maintenance requests that mention estimates are not a board bid file.

This association's findings are in its private notes (mystique/notes/SKILLS.md).

Library PDFs download with `PayhoaClient.download_document` (`POST /organizations/{orgId}/documents/{id}/download`). Many library files download as one zip with `PayhoaClient.bulk_download_documents` (`POST /organizations/{orgId}/documents/bulk-download`, body `{"documents": [id, ...]}`). Transaction invoices download with `download_signed_url` from the attachment `url` on `GET /organizations/{orgId}/transactions/{id}`. Those calls already exist. This packet does not need a new report-to-PDF export. `GET /reports/config` still has no render call. The budget and the treasurer's report are the rendered PDFs, already stored in the library.

The latest update may arrive by email and not be in the PayHOA library; the library may hold only the last full study. Keep both PDFs in `data/reserve-studies/`.

## Review transactions against reserve components

Every PayHOA transaction is exported under `data/transactions/{year}/{month}/`. `transactions.json` has the date, amount in cents, description, memo, category, and bank account. Invoices sit in that month's `invoices/` folder. An attachment that has a name and no download URL, on the list or on the transaction detail, cannot be fetched; say so rather than treat the payment as unattached.

A reserve line that is a transfer still gets matched to the operating charge before anyone treats it as a reserve expense. Category `Reserve Expenses` is not the test. The component list is.

Civil Code section 4177(a) is the money the board has set aside for future repair or replacement of major components the association must maintain. Section 5510(b) limits spending those funds to repair, restoration, replacement, or maintenance of those components, and to litigation about that work. Section 5550(b) is why the analyst asks: the annual review resets remaining useful life and the contribution. A component enters the study when its remaining life is under 30 years. Section 5550(c) includes gas, water, and electrical lines to the extent section 4775 makes the association responsible for them. The reserve-study guide is `docs/laws/reserves.md`. It covers SB 900, AB 2114, and SB 410.

The practical test, used by reserve-study firms and consistent with that statute, has two questions. Is the work on a component already in the study? Does the work make that component new again, or only keep it running? Replacement of a component, or of a real part of one, is a reserve expense, and the analyst should shorten or split the remaining life. A failed part, a cleaning, a test, a bulb, or a monthly contract stays operating. Tell the analyst anyway when the invoice touches a component they are tracking, so they do not reset a life that did not reset. Small repairs stay operating even when the component is in the study. There is no statutory dollar cutoff. A dollar floor in the association's own spending policy does not define an expenditure as one invoice. Related replacements of one component can be one expenditure; a different component stays on its own line. A partial replacement (some of a line's fixtures) is reimbursed without resetting the rest of the line. See `docs/laws/reserves.md`.

`Mystique.reserve_components()` is the working list from the Reserve Components sheet (`KnownFile.RESERVE_COMPONENTS`). Each row has a cost center (`common`, `p1_p2`, `p3_p8`), a classification (`ComponentMajor`), replacement cost in cents, useful life, and remaining life. A row with an empty Major cell on the sheet takes its classification from the component (backflow rows are `ComponentMajor.BACKFLOW`). A row can have a useful life and no cost.

That sheet is behind the studies. The studies do not use those cost centers or item codes. They use one component list, and they can differ from the sheet in a component's life, grouping, and cost. The latest update is the study to use for remaining life. The sheet is the list that still carries cost center.

This association's findings are in its private notes (mystique/notes/SKILLS.md).

## Sync the document library with Drive

Governing documents live in PayHOA. A copy lives in named Google Drive folders, including the folders embedded on the association's website (`Community.site`). The rules are `SyncRule` objects on the `Mystique` class in [mystique](mystique/README.md). The narrative is [docs/drive-sync-rules.md](docs/drive-sync-rules.md).

`jason document-sync` writes `data/sync-plan/plan.json` and `report.md`. Counts are by rule. `needs_publish` and `would_create` are the action lists. It does not upload.

| Result | Meaning |
|--------|---------|
| `matched` | The same file name is already at the library path. |
| `would_create` | The name exists in PayHOA, often only under Email Attachments. Prefer the library path. |
| `needs_publish` | The file matches a rule and PayHOA does not have it. A Google Doc publishes as `{name}.pdf`. Example: Drive `ALPR Policy` → `Governing Documents/Policies/ALPR Policy.pdf`. |
| skipped | The name misses the glob, or the folder is excluded (Audio Book, John Laing, Proposed, Applications, Policies/old, Watt, Insurance 2021–2023, Confidential, Email Attachments, loose My Drive root). |

```bash
jason export-documents
jason document-sync
```

Name-match is not “upload everything in the folder.” `needs_publish` is the list to review before `create_document`. Replacing an existing PayHOA file was not captured. Do not sync the site file **Portal**; Drive cannot edit Google Sites page text.

## Publish a Google Doc as a PayHOA PDF

Minutes and policies often stay a Google Doc, sometimes with a diagonal DRAFT watermark. Edit the body with `documents.batchUpdate`. Export with `GoogleDocs.export_pdf` (Drive `files.export`, `application/pdf`). Upload the PDF into a PayHOA folder.

The Docs API cannot remove a text watermark. Remove it in the Docs editor before export, or the PDF includes it. `drive.readonly` cannot save that PDF back into Drive. A local file is only needed when PayHOA must receive the bytes.

```bash
jason publish-document --doc DOC_ID --parent PARENT_ID --out "Name.pdf"
```

`--parent` is the PayHOA folder id from `export-documents`; the folders jason uses are `PayhoaFolder` members on the `Mystique` class.

## Read the local catalog

`jason-mcp` answers from `data/payhoa.db`, `data/payhoa-files`, `data/ownership.db`, `data/index-cache.db`, `data/tax.db`, and deed extracts on disk. It does not log into PayHOA, Google, or Keeper. Only the `recorder_*` and `tax_search` tools reach the county's public index, and those need no login either. `.mcp.json` at the repo root registers it for Claude Code as a stdio server.

```bash
pip install -e ".[mcp]"
jason-mcp
```

`search_requests` filters by status, form name, unit, and text. `search_documents` filters by path prefix and file name. Use those before a live list call. `county_status`, `ownership_record`, `search_ownership`, and `pinned_chain` read the local chain. `compare_parties` is the chain's name equality. `read_deed` is the consideration on an extract already saved; it reads the `.pdf.md` text beside the scan, never the scan. `expand_deed_anchors` starts from the pinned deeds, the developer grants, and the stored unit chains with their priors, places a deed only when it joins that set without touching two parcels, and returns the solved parcels plus the candidates still loose. A parcel it leaves open has no stored deed that reaches a developer. `tax_reassessments` lists the bill years a parcel's enrolled value left the 2% track, and `audit_chains` checks every stored chain against recording order, the phase window, the developer that sold that phase, the tax calendar, and the deed price; a finding names the record to read next. The strategies for closing an open parcel, the bounds, and the assertions are in the private notes (mystique/notes/ownership-history.md). `recorder_search` queries the Sacramento public index by document number or party. A wide name comes back only as a grant deed, a quitclaim, or a UCC filing. `recorder_detail` reads one instrument's APN and the document numbers it cites. `recorder_priors` lists earlier grant deeds on which that party is the grantee. A hit is not a pin. Keep it when the detail APN is the parcel being searched. `tax_status` and `tax_account` read `data/tax.db`. `tax_search` queries the public tax index by parcel or address and does not download bills or write the catalog. `secured_status`, `secured_parcel`, and `secured_search` read `data/secured.db`. `secured_roll` reads `secured_roll_public.xlsx` for one APN or for the community parcels. Amounts are integer cents. The roll owner can be a year behind a sale.

## Refine a Gmail draft

A person asks for a change to a letter jason drafted: a date, a sentence, a tone, a recipient. Edit the saved draft in place; do not save a new one.

1. Find it: `jason draft --list` (id, recipients, subject), or the draft id the register or task recorded (a legal hold's notices are in `data/holds/<key>/register.json`).
2. Read it as it stands: `jason draft --show ID`. The person may have edited it in Gmail since jason saved it; their text is the text to change.
3. Change it: `jason draft --edit ID --replace "OLD" "NEW"` (repeatable), `--subject`, `--body-file`, or `--to`. The dry run prints a diff. Show the diff to the person, then run the same command with `--yes`.
4. When the draft came from a template or a specification row (a hold notice, a hearing notice), change the row or the wording at its source too, so the next draft carries the refinement. Re-running `jason hold --notices --yes` updates the hold's drafts in place.

The update keeps the draft's id, thread, and the recipients a person typed in Gmail. An OLD that is not found stops the edit with nothing changed. A draft with an attachment is refused; edit it in Gmail. jason never sends or deletes a draft: a draft gone from Gmail was sent or discarded there, and a redraft then creates a new one.

## Read a returned owner information form

An owner sends back the owner information form: a PayHOA form submission, the emailed PDF typed into, a reply email, or paper scanned or photographed. The map of the whole form is [docs/forms.md](docs/forms.md).

1. Know the form from its own printed lines (`form_reader.identify_form`), never from its marker.
2. Read it:
   - A typed PDF: `fillable.read_answers`.
   - A scan: `form_reader.read_scan`, with `VisionReader` for handwriting. On this machine the 27B model usually can't load; see the model trials in [docs/document-tools.md](docs/document-tools.md).
   - Then the reading hints (`form_hints.apply`), with what that copy printed made fresh from PayHOA.
3. Judge where it came from (`community/assurance.assess`): signed in, matched to the email on file, holding the owner's reference, claimed, or a lead. Below matched, the change is told to the address on file before it is relied on.
4. Find the copy it answers, as a hint: the marker (`form_references.lookup`), its bar mark, the Gmail thread, or the unit address the owner wrote. A mailed letter names only its campaign.
5. Compare it with what was on file (`owner_prefill.compare`): unchanged, changed, added, or cleared.
6. Show a person each change with how it was read and its assurance. The tag writes are `jason owner-info` with `--yes`, after they confirm.

Do not tell the vision model what the copy was sent with, or add format rules to its prompt: told the old answers, a model can report them instead of the owner's changes. Compare after reading, in code.

Do not record a reading on its own. Do not let a marker decide which owner a return belongs to: a marker repaired by its checks or matched to the nearest sent one says so, and a person confirms it. Do not keep an owner's address or email outside PayHOA. Do not trust the hints over a real change: a reading that differs from what was sent in anything but OCR's look-alikes is the owner's change.

## Test the form, its layout, and its reader

Before changing the form's design, the reader, or the hints, or before trying a new model, measure.

```bash
jason form-fuzz --lint                         # the built form: tokens, the marker's places, margins, sizes
jason form-fuzz --replay                       # the cases that failed before
jason form-fuzz --cases 60 --seed 1            # a fresh run; compare with the last report
jason form-lab --sample                        # the layouts, blank and filled, as PNGs
jason form-lab --search                        # coordinate descent over the layout (about 15 s a layout)
jason form-lab --benchmark glm-ocr:latest qwen3.5:9b --styles
pytest tests/test_form_reader.py tests/test_form_marks.py tests/test_form_lab.py
```

Reports and corpora are under `data/forms/fuzz/` and `data/forms/lab/`. The answers are made up (the `example` domains), so run neither tool on owner records. A model run preflights, holds the GPU lock, and unloads the model when done. Add a row to the model trials after trying a model. The responder model in `form_lab` is an assumption, stated so it can be argued with; tune it against real filled copies, not against the numbers it produces. Change `owner_prefill.normalize` only before copies are sent, since sent copies' fingerprints are hashes of it. See [docs/form-fuzzer.md](docs/form-fuzzer.md) and [docs/form-design.md](docs/form-design.md).
