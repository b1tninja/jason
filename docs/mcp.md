# jason-mcp

`jason-mcp` is a stdio MCP server over the stores already on disk: the PayHOA catalog (`data/payhoa.db`, `data/payhoa-files`), the deed chain (`data/ownership.db`, deed extracts), and the files the other `jason` commands saved. It does **not** call PayHOA, Google, or Keeper. A few tools read a public source (the Sacramento recorder's index, the public tax index) or a local service (Ollama, AnythingLLM); each says so below.

The tool list is `ALL_TOOLS` in `src/jason/mcp/server.py`. The tools live in `server.py` (the PayHOA catalog), `county.py` (deeds, liens, reviews, mail, meetings, documents, law), `index.py` (the recorder's index), and `rolls.py` (tax bills and the secured roll).

## Running it

```bash
pip install -e ".[mcp]"
jason-mcp                         # stdio; every tool
jason-mcp --profile board         # the board set
jason-mcp --profile governance    # the governance systems
```

- `.mcp.json` at the project root registers `jason` as `.venv\Scripts\jason-mcp.exe` for Claude Code.
- The server runs from `JASON_CWD` when a client sets it, else the folder that holds `.env`. The stores are addressed as `data/...` from there.
- **Profiles.** With no profile (or `all`) every tool is served: 121 today. `--profile governance` serves the fourteen governance tools below. `--profile board` (or `JASON_MCP_PROFILE=board`) serves thirty-eight: the digest, the briefs, the budget, utility, vendor, pest, incident, insurance policy, reserve, reserve transfer, invoice, and reconciliation reviews, the mail, the Zoom meetings, the meeting records, and hearings, insurance, deadlines, open items, and party briefs, the lien and solar standings, the duties, and the law. The list is `PROFILES["board"]` in `server.py`. An unknown profile stops the server.
- **AnythingLLM.** `jason anythingllm --write` registers jason-mcp in AnythingLLM Desktop's `anythingllm_mcp_servers.json` with the board profile; `--profile all` registers every tool. A small local model chooses better from the board set.

## Rules for a client

- `board_digest` is the entry point for what the board should know now.
- Each tool carries its caveats. Repeat them.
- A confidential file, an executive session's or hearing's text, and a claim's snippet are held back unless asked.
- A reading, a match, or a related item is evidence or a lead, not a pin and not a finding. A recorder hit is not a pin.
- The tools decide nothing. Whether a statute was met, a peril covered, or a duty done is a person's to say.
- Amounts are integer cents.

Tools marked **(board)** are in the board profile.

## PayHOA catalog

| Tool | What it reads, and the caveat |
| --- | --- |
| `catalog_status` | Row counts in `data/payhoa.db` for the configured organization. |
| `search_requests` | PayHOA requests in the catalog by status, form name, unit, or text. |
| `search_documents` | PayHOA library documents in the catalog by path prefix or name. |
| `get_request_local_export` | One request's comments, notes, and attachment names as `jason sync-request-files` saved them. |
| `read_exported_file` | One file from a request's export. It rejects a path outside that folder. |

## Units, title, and liens

| Tool | What it reads, and the caveat |
| --- | --- |
| `unit_brief` **(board)** | One unit on a page: title and chain, open liens while owning here, solar standing, taxes, members. Repeat its caveats. |
| `escrow_brief` **(board)** | What the association can tell escrow before a sale of the unit. Repeat its caveats. |
| `title_watch` **(board)** | Every unit's liens as one standing each against the title; `attention=True` for what a person acts on. A presumption is not a release, and another association's lien is never on the unit. |
| `assessment_liens` **(board)** | The association's own assessment liens, unit by unit. Repeat its caveats. A lien row's `namesakeRisk` means the filing dropped the deed's middle name; say so. |
| `association_collections` **(board)** | The PayHOA ledger beside the association's own liens (release due, lien secures debt, owed with no lien, credit). It records nothing and sends nothing. |
| `parcel_liens` | Every lien, default, loan, or release lifecycle naming an owner of a parcel. A lien indexes a person, not a parcel; `where` says whether it opened while that owner held this unit, is the association's own lien, or belongs to another time or property. |
| `mechanics_liens` | Every mechanic's lien lifecycle with its standing. An expired lien is unenforceable but still of record. |
| `solar_status` **(board)** | Each unit's solar lease standing from the cached UCC filings. No filing is not proof of purchase. |
| `unit_characteristics` **(board)** | The assessor's stored residential characteristics (living area, bedrooms, baths, year built) and the plan each unit matches. |
| `unit_number` | Every parcel a unit number can mean. Numbers 21 to 32 name two parcels each (`ambiguous`); a unit number places a deed only on a 2007 deed that prints the block's parent parcel. |
| `new_owners` | Recent conveyances with the buyer's questions. |

## Deeds and the ownership chain

| Tool | What it reads, and the caveat |
| --- | --- |
| `county_status` | How much chain material is on disk: ownership rows, pinned deeds, unit parcels with no current deed, extracts. |
| `ownership_record` | The assessor's current deed for one parcel, from the ownership store. |
| `search_ownership` | Current deeds whose grantor or grantee compares equal to a name, by the chain's spelling rules. |
| `compare_parties` | Whether two party strings are one owner, and the abbreviation candidates. |
| `pinned_chain` | The pinned community deeds, newest first, with gaps and cited unknowns. |
| `read_deed` | Consideration and granting clause from a deed extract on disk. The price is integer cents from the documentary transfer tax. The recorder is not called. |
| `audit_chains` | Every stored unit chain, or one, checked against the other records. A finding names the record to read next; it is not a verdict. |
| `expand_deed_anchors` | Grows the local deeds out from the pinned chain. A solved parcel drops out, and `remaining` is the candidate pool. |
| `list_developers` | The subdividers pinned on the community, and each index spelling. |
| `list_public_reports` | Each DRE public report file, its phase, and the pinned copies and annexations. A related file is not the report. |

## County records and the index

| Tool | What it reads, and the caveat |
| --- | --- |
| `recorder_search` | Searches the Sacramento public index by document number or party name. A hit is not a pin. |
| `recorder_detail` | One instrument from the public index: APN, parties, and the numbers it cites. A hit is not a pin. |
| `recorder_around` | The subject, the same-day numbers beside it, and the documents it cites. A same-day number whose parties do not match is someone else's instrument. A hit is not a pin. |
| `recorder_descend` | Walks out from a deed and from the developer, one step at a time. A meet is not a pin and is not stored. |
| `recorder_priors` | Grant deeds before a date on which a name is the grantee. A hit is not a pin. |
| `recent_filings` **(board)** | What recorded on or after a date that touches a unit or an owner while owning here. Repeat its caveats. |
| `lifecycle_of` **(board)** | Where a recorded document number sits in the stores. Repeat its caveats. |
| `explain_filing` **(board)** | What a county filing code or name is: its family, sides, and the lifecycle it opens. |
| `association_records` | The association's record in the index cache: governing instruments, liens it placed, and liens and notices against it. Nothing is searched; run the community name searches first. |
| `index_survey` | Counts the cache by family, process, and filing and lists the filings no class reads. A new filing there is a new rule row in `filings.py`, not a special case in a task. |
| `index_coverage` | The cached index against the processes, and what is left to model. |
| `records_request` **(board)** | The recorded instruments the association's record lacks, with the order form's fields and the copy cost. |
| `tax_status` | How many tax accounts and bills are stored. |
| `tax_account` | The stored tax account for one parcel, newest bill first. |
| `tax_reassessments` | Each bill year the enrolled value rose by more than the 2% factor. The enrolled value is the county's base-year figure, not the deed consideration, and a jump can be a Proposition 8 restoration. It does not call the tax collector. |
| `tax_search` | Queries the public tax index by parcel or address. It does not download bill pages. |
| `secured_status` | How many secured-roll rows are stored, and where the bulk workbook is. |
| `secured_parcel` | One stored secured-roll row. The owner can be a year behind a sale. |
| `secured_search` | Stored secured-roll rows whose owner contains a text. |
| `secured_roll` | The bulk secured workbook for one parcel or for the community. |
| `permits` | The City's permit collection as `jason permit-status --sync` saved it (`data/accela`): each open record's status, fees, conditions, and review marks. A fee line's date is the invoice date, and the collection's fees paid include the developer's building permits. |

## Utilities

`utility_brief` **(board)**, `utility_accounts`, `utility_usage`, and `utility_payments` **(board)** read the parsed SMUD and City bills (`data/utilities.db`) and the last payment audit.

| Tool | What it reads, and the caveat |
| --- | --- |
| `utility_brief` | The bills, abnormal usage, and next year's cost beside the budget line. Abnormal usage is a reason to look, not a finding. |
| `utility_accounts` | Each account's meters and parcel as the bills state them. |
| `utility_usage` | One account's usage bill by bill, and usage per day. |
| `utility_payments` | Each PayHOA payment's bills, attachment, and split by budget line. jason changes nothing in PayHOA. |

## Finance, ledger, and reserves

| Tool | What it reads, and the caveat |
| --- | --- |
| `budget_status` **(board)** | The finance snapshot `jason budget` took from PayHOA: budget against actual, year to date and full year. |
| `bank_accounts` **(board)** | The bank balances from the same snapshot, named from `mystique/banking.py`. The balances are Plaid's and can lag the bank. |
| `books_report` | The books `jason books --sync` stored from PayHOA's general ledger (`data/payhoa/ledger.db`): profit and loss, categories by month, vendors, cash flow, balances, receivables without names, and a check against PayHOA's budget against actual and its Profit vs Loss by Month. |
| `ledger_query` | Entries in the same ledger by filter. It leaves the units' own accounts out. |
| `ledger_validation` | The last `jason ledger` check of the library's treasurer's reports against PayHOA's "Treasurer's Report" packet: copies that are a run as generated (by SHA-256), copies under the wrong month, accounts the ledger no longer carries, balances it now reports differently. The printed report is the record of what the board was told. |
| `bank_reconciliations` **(board)** | PayHOA's bank reconciliations as `jason reconcile --fetch` stored them: months covered, statement against ledger (a difference the items in transit explain is marked), items that never cleared with their age, transfers open on both sides, and why each may not have cleared. Clearing or voiding an item is the treasurer's. |
| `invoice_review` **(board)** | The last `jason invoices` review of every expense payment against its attachments (amount, vendor, date, reuse, category) with the per-vendor reader scorecard. It changes nothing in PayHOA. |
| `document_copies` | The last `jason copies` run: every invoice and bill as one document with each copy held (issuer's portal, email, PayHOA attachment, paper scan), the rule that joined it, the best copy by `mystique/copies.py`, and the payment. Every copy stays where it is. |
| `reserve_study` **(board)** | The reserve study PDFs on disk: the latest plan for a year beside the budget's transfer line and the reserve accounts, each study's Civil Code 5570 disclosure, and when the next site visit is due. The figures are the preparer's. |
| `reserve_transfers` **(board)** | Every movement on the reserve accounts from the stored ledger, and each borrowing's Civil Code 5515 record (notice of intent, minutes, resolution, restoring contributions within a year). A repayment is matched by amount, and whether the statute was met is the board's to say. |
| `cost_centers` | The annexations' two assessment cost centers (the Phases 1 and 2 Property, A.C.A. 3 and 8; the Annexed Property) beside the DRE reports' cost center budgets, the assessments charged in each, the budget's lines, and the reserve studies' funding plans. Restoring them is the board's, with counsel. |
| `developer_securities` | The developer's DRE securities saved from Drive (`data/developer-security`) by phase: agreements by type, bonds, and the releases that name them. A bond with no release on file may have been released without a copy reaching Drive, and OCR can misread amounts. |

## Vendors, insurance, incidents, and claims

| Tool | What it reads, and the caveat |
| --- | --- |
| `vendor_portal` **(board)** | A vendor's customer portal as `jason vendors --sync` saved it under `data/vendors/<key>` (for a pest control vendor on FieldPortals: properties, plans, visits with products and EPA numbers, photos, documents, invoices checked against tickets) and, after `--verify`, each PayHOA payment against the portal and the invoice. jason signs in with the Keeper record `<key>_record_uid`, only reads the portal, and never pays. |
| `pest_program` **(board)** | The same record as a pest control program: each product by EPA number with label, safety data sheet, and California rules once `jason pests --fetch` has run, rodent station activity, visits by building, and inspection reports ([pest-management.md](pest-management.md)). The declaration decides who pays, and jason directs no application. |
| `vendor_contacts` | Each PayHOA vendor's contact beside the people who write from its domains in Gmail (headers only), with what a person should update, and PostScanMail's Gmail notices against the synced mail. jason reads no message body, sends no email, and changes nothing in PayHOA. |
| `insurance_policies` **(board)** | The last `jason policies` run: each policy term by term from its declarations, beside the policy sheet and the specification, with findings (the sheet out of step, a renewed term not on file, a mailing address not the association's, the Civil Code 5800/5805/5806 limits, protective safeguards). The policies' own words are the AnythingLLM `insurance` catalog ([insurance-policies.md](insurance-policies.md)). |
| `insurance_review` **(board)** | Each policy on the sheet against the carriers' letters and the premiums PayHOA paid: term in force, renewal notices, premiums by term (a flood payment placed on the building whose renewal bill prints it), and claims. |
| `association_calendar` **(board)** | The recurring deadlines (taxes, filings, inspections, insurance terms, the reserve study) with the PayHOA evidence each was done, and past deadlines done late. A payment is evidence, not proof. |
| `incident_history` **(board)** | The last `jason incidents` run: maintenance history and insurance claims from the repair paperwork, grouped into events on units and buildings, each with its work, its standing against the $10,000 deductible, causes, elements, vendors, amounts, and claim numbers ([incidents.md](incidents.md)). An event is a rule's reading, not a finding; whether a peril was covered is the insurer's answer; a claim's snippet is held back unless asked; medical records are never read. |
| `legal_cases` | The association's legal matters from `mystique/cases.py`: forum, number, role, status, businesses (private persons by role only), counsel, insurer claims, events, money, each statutory duty's standing, and a settlement's released items priced from the claimant's cost of repair. Confidential, for directors and counsel. A cost of repair marked for mediation (Evidence Code 1119) stays out of members' notices. |

## Meetings, minutes, and hearings

| Tool | What it reads, and the caveat |
| --- | --- |
| `zoom_meetings` **(board)** | The Zoom meetings as `jason zoom` synced them (`data/zoom`): each occurrence's kind by `mystique/zoom.py`'s topic rules (or a board meeting by the schedule's day), who joined, and the schedule's meeting days with no meeting. |
| `zoom_meeting` | One meeting: transcript as speaker turns, the AI Companion summary, and its next steps. The AI summary is not the minutes (no roll call, motion, or vote). An executive session's or hearing's text, or a transcript that mentions one, is held back unless asked. |
| `meeting_records` **(board)** | The last `jason meetings` catalog: every meeting's agendas, notices, minutes, transcripts, AI summaries, chats, attendance, and recordings across Zoom, jason's copy, Drive, the PayHOA library, and drafts, with each meeting's checks (minutes 30 days on, CIV 4950; a recording kept after the minutes against the Decorum Rules; a transcript that runs into executive session). It deletes nothing, and a kept recording may be under a litigation hold. With `date` it adds what the agenda links under each item; with `file` it gives every meeting and item that linked a file, a lead for filing it, not a classification. |
| `hearings` **(board)** | The disciplinary hearings `jason hearing` planned under Civil Code 5855 (notice 10 days before, decision in writing within 14 days) and where each stands. jason creates a Zoom meeting only with `jason hearing --create --yes`, never keeps the host's start link, and never sends the notice or decides the discipline. |
| `board_items` | The board's running list of action items, with the board's own status, owner, meeting, and notes. An item is a matter to decide, never the decision. |

## Mail, email, and counterparties

| Tool | What it reads, and the caveat |
| --- | --- |
| `mail_brief` **(board)** | The paper mail as `jason mail` synced it from PostScanMail (`data/mail`), sorted into legal notices, insurance letters, government notices, escrow requests, bank statements, bills, and checks, with the dates the letters tie to an action. jason only reads the mailbox and never asks PostScanMail to scan, forward, shred, or discard. |
| `mail_item` | One letter's sender, sort, and scanned text. Same rule as `mail_brief`. |
| `mail_checks` | The mail against jason's other records: old addresses, escrow clocks under Civil Code 4530, tax bills and delinquency notices against the stored bills, bank statement balances, checks against deposits. |
| `counterparties` | Who the association hears from and pays, by kind of source, the other associations the mail names, and the letterheads no rule names. The directory is `mystique/senders.py`. |
| `email_threads` | The Gmail as threads of work (headers only, from `jason gmail --sync`): status, age, parties (never an owner's address), and related payments, letters, invoices, Drive files, requests, and violations. A related item is a lead, not proof. jason sends no email. Repeat the caveats. |
| `thread_topics` | What the association hears about by topic (`mystique/topics.py`), and the FAQ candidates. |
| `email_intents` | What each thread asks, from its subject, and for a complaint, question, or information request, where the answer is likely written (governing-document passages, library documents, PayHOA violations as precedents). It decides nothing. |
| `reply_needed` | Which email the association answers, learned from its own replies, and the open threads that likely need a response, each with the history it was judged by. |
| `request_links` | Each PayHOA request joined to PayHOA's notices and the owner's threads about its unit, with reasons, and a draft for each emailed request PayHOA lacks (form from `mystique/requests.py`). Read-only; a draft is entered only by a person with `jason request-links --create THREAD --yes`. |
| `open_items` **(board)** | What is waiting on the association: threads awaiting us, pending requests, deadlines, insurance findings, unscanned mail, letters to act on, unpaid lien notices. |
| `party_brief` **(board)** | One unit (by address) or one counterparty (by name, vendor, or domain) across every store: a unit's owners by deed, PayHOA standing, requests, violations, threads, letters, and the unit brief; a counterparty's payments by year, invoices, threads, letters, contacts, and Drive files saved from its email. |
| `case_file` | One matter across the stores by the words that name it. It decides nothing. |

## Documents, library, and models

| Tool | What it reads, and the caveat |
| --- | --- |
| `library_search` **(board)** | The classified document library (`jason library`). Each row keeps its method (name rule, phrase rule, local model). A confidential file is held back unless asked. |
| `library_status` | How the library is classified, by method and kind. Same rules. |
| `library_text` | One library file's cached text. A confidential file's text is held back unless asked. |
| `record_locations` | The last `jason drive` run: every Drive file placed by the Drive roots and classified (kind, Civil Code 5200 records, confidential), every other place its content is held, duplicates and versions, and folders no path rule covers. jason moves, renames, and deletes nothing in Drive. |
| `document_models` | The stored document-model readings (`jason models`): per kind, files read and completed, and each file's typed record and findings. A finding cites the statute when the law shapes the document; a confidential file's fields are held back unless asked; a reading is evidence, not a pin. |
| `document_references` | The outlines and references `jason outlines` stored (`data/outlines`): numbered sections, one section's text with what it cites and what cites it, every statute, section, or resolution reference, and findings. References are read by a citation grammar, a finding is a lead for a person, and a scanned annexation's outline can miss subsections. |
| `read_document` | One recorded copy's text into the concept records (stamp, citations with relation, annexed property). A reading is evidence. |
| `document_readings` | Every governing and annexation extract read at once, with the supersessions the texts state. A supersession is pinned in `mystique/annexations.py` only after a person reads it. |
| `passage_search` **(board)** | Ranks the extracts' passages for a question. |
| `extraction_scorecard` | Scores a reader (regex, the local vision model through Ollama, or the hosted model) against the pinned facts. |
| `read_scan` | Reads one image-only PDF with the local vision model through Ollama. |
| `jobs_status` | The job queue (`jason jobs`, run by `jason worker`; [jobs.md](jobs.md)): each job's command, resource, status, attempts, who confirmed a write, and the end of its log. It adds, runs, and cancels nothing. |

The local readers never leave the machine. The hosted reader fails fast without its key and sends nothing.

## Law, records, and duties

| Tool | What it reads, and the caveat |
| --- | --- |
| `authorities` **(board)** | The statute pages `jason export-authorities` wrote from lawlibrary: the words of the law (`records.md` and `duties.md` are summaries). Given a former Davis-Stirling section (Civil Code 1350-1378) it returns where the 2014 recodification put it; given a current one it adds the changes since 2011, both from `jason law-history --export` ([law-history.md](law-history.md)). Each successor row names its source (the Law Revision Commission's disposition table, its Comment, or a similarity candidate); the statute text in force is the law. |
| `records_inventory` **(board)** | The Civil Code 5200 inventory with its gaps. It does not decide that a record exists. |
| `duty_brief` **(board)** | One manager duty mapped to its statute, records, cadence, and the documents' passages. It does not decide that a duty is met. |
| `manager_context` **(board)** | A professional community manager's context pack for a task (`jason review`; [manager-review.md](manager-review.md)): the base prompt (the order of authority under Civil Code 4205, the method, the privacy rules), the task's prompt from `mystique/prompts.py`, and the sources numbered in order of authority. Work from it, cite by id, and quote; it decides nothing. |

## AnythingLLM

| Tool | What it reads, and the caveat |
| --- | --- |
| `anythingllm_query` | Asks AnythingLLM by catalog (`authorities`, `association-records`, `mail`, `jason-pages`, or a legal case's `case-<key>`) or the shared association workspace, and labels each source with its catalog. A `jason-pages` source is a summary. |
| `anythingllm_status` | AnythingLLM itself: its chat and embedding settings against jason's, each workspace's embedded documents and retrieval, and what is wrong with the command that fixes it. Starting it, applying settings, and re-embedding are `jason anythingllm` commands with `--yes`. |

Each legal case with a `drive_folder` in `mystique/cases.py` is its own catalog (`jason cases --fetch-files`, then `jason anythingllm --sync --catalog case-<key>`). It is confidential, never in the shared workspace, synced only when named, titled with its case number, and never moved into or out of another catalog. It leaves out the medical and veterinary records the case holds back unless a person passes `--include-held`. AnythingLLM fails fast without its key and sends nothing.

## Governance

The living documents, conflicts, intake questions, the schedule, members' requests, the notice catalog and delivery, and the documents' duties. These are `--profile governance` (`jason.mcp.governance`).

| Tool | What it reads, and the caveat |
| --- | --- |
| `living_document` | A governing document as amended: the instruments applied and not in effect, the findings, and the rule rows' checks. With `section`, also that section's words, who set them, and its history. `as_of` gives the text in force on a date. Built from the saved sources. Not an official restatement; the recorded instruments control. |
| `document_conflicts` | Provisions a higher authority displaces (4205), each with what still governs and what yields. `leads` adds the Act's changes since each document was written. A lead is something to read, not a conflict. |
| `intake_questions` | The questions parked while taking documents in, with evidence, choices, and the suggestion. `likely` means two independent readers agree. |
| `answer_intake_question` | **Writes** a person's answer to `data/intake/asks.json`; `by` is required. `jason intake --apply` turns answers into records. |
| `schedule_agenda` | What falls due, by role, with each item's standing. Assignments are proposals until the board adopts them. |
| `schedule_assignments` | Every assignment (role, clock, evidence, adoption) and the coverage check: duties nobody owns, and duties on a clock nothing schedules. |
| `record_completion` | **Writes** that an occurrence was done to `data/schedule/done.jsonl`; `by` and `evidence` are required. |
| `member_requests` | Each member's request (PayHOA and the owners' email): its kind, its clock (statute, documents, or proposed policy), due day, owner, and standing, with the next step. `sources` adds leads to where each answer is written (passages, library files, precedent violations); each is a lead, not a ruling. Email kinds come from subjects. Never approves, denies, or assigns. |
| `request_kinds_measure` | How well requests' kinds are read: precision and recall per kind against the private hand-labelled gold set; `misses` lists each wrong reading with its rule. The rules were tuned on that set, so the scores are an upper bound. |
| `acknowledgment_draft` | A first comment for an open request, for a person to send: a PayHOA comment, or for an email request `jason respond --draft ID --gmail` (a Gmail draft in its thread). It promises a date only where the law or the documents set one, and sends nothing. |
| `notice_requirements` | The notice catalog: every requirement, or one in full (methods, clock, content, the proof it needs, what the documents add). |
| `notice_delivery` | One notice's delivery to every member from the ledger: reached, bounced, skipped, and the follow-ups the law asks for. Sync first. |
| `document_duties` | The norms a document states, each with its section, quote, bearer, and timing. A reading is a lead; about one in five is the wrong kind. |
| `governance_digest` | Start here: what needs attention across these systems, most urgent first (a passed statutory or documents' clock, then overdue, due soon, open, noted). Each section is capped, names the tool for the rest, and is reported unavailable rather than failing when its store is missing ([attention.md](attention.md)). Decides nothing. |

**From Python.** The same functions are `jason.api` (`from jason import api; api.member_requests()`). They return JSON-ready dicts. The other tools import from `jason.mcp.county`, `jason.mcp.index`, and `jason.mcp.rolls`.

## Board

| Tool | What it reads, and the caveat |
| --- | --- |
| `board_digest` **(board)** | Start here for what the board should know now: what recorded since a date, owners in default, releases the association owes, prior owners' liens with no sale since, the association's own open liens (and other associations' liens that are not ours), and the solar standings. Each list is capped, with the tool that gives the rest in `more`. Run the syncs first for the newest filings. It decides nothing. |

The other board-profile tools are marked **(board)** in the sections above.
