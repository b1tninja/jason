# jason documentation

One line per page, grouped by area. The project overview is [../README.md](../README.md); agent rules are [../AGENTS.md](../AGENTS.md) and [../SKILLS.md](../SKILLS.md).

The association's own findings (owners, parties, deed chains, review results) are in its profile's private notes, `mystique/notes/`, which are not checked in. A page here that says "the private notes" means that folder.

## Setup and reference

- [setup.md](setup.md): installation, `.env`, Keeper, Google OAuth.
- [profiles.md](profiles.md): one association as a profile; choosing it, what goes in it, and the plan to make jason reusable.
- [sample-profile-plan.md](sample-profile-plan.md): plan (not started) for a fictional second profile to test reusability.
- [base-templates.md](base-templates.md): plan for general base templates (letters, notices, forms, packets) rendered per profile, with the statutory catalog.
- [cli.md](cli.md): every `jason` command and its options, generated from the parser by `scripts/gen_cli_docs.py`.
- [mcp.md](mcp.md): the jason-mcp tools.
- [jobs.md](jobs.md): the job queue; `jason jobs` adds commands and `jason worker` runs them later, in order.
- [batches.md](batches.md): bulk PayHOA writes sent one at a time with a ledger, so a stopped run resumes; each notice's delivery to every member, and the follow-ups the law asks for (`jason notices`).

## PayHOA and finance

- [payhoa-reports.md](payhoa-reports.md): what PayHOA can report, how it computes it, and how jason reads it.
- [ledger-reports.md](ledger-reports.md): PayHOA's "Treasurer's Report" packet and how it validates the library's treasurer's reports.
- [invoices.md](invoices.md): the invoice model and the review of every expense payment against its attachment.
- [copies.md](copies.md): one invoice or bill held as several copies (portal, email, PayHOA, paper), the best copy, and the payment.
- [reserve-studies.md](reserve-studies.md): the reserve study model, its Civil Code 5570 disclosure, funding plan, and site visits.
- [reserve-transfers.md](reserve-transfers.md): reserve contributions, borrowing under Civil Code 5515, and the record each loan needs.
- [developer-securities.md](developer-securities.md): the developer's DRE assessment, subsidy, and completion securities by phase, bonds, and releases.

## Utility bills

- [utility-bills.md](utility-bills.md): the SMUD and City bill model, tariffs, abnormal usage, the forecast, and the PayHOA payment audit.

## Documents and library

- [drive-sync-rules.md](drive-sync-rules.md): which Drive files belong in which PayHOA folder, compared by name; nothing uploads until a person publishes.
- [drive-holdings.md](drive-holdings.md): where each association record is in Drive: path rules, copies by content, duplicates, versions.
- [drive-labels.md](drive-labels.md): jason's labels on Drive files as private `appProperties`.
- [drive-activity.md](drive-activity.md): who created, moved, renamed, trashed, or re-shared a Drive item, read from the Drive Activity API.
- [document-readings.md](document-readings.md): reading the instruments' own text into concept records, and what OCR defeats.
- [intake.md](intake.md): taking documents in: the questions jason parks for a person (classification, OCR readings, an amendment's silent changes, drift), and answers kept as records.
- [living-documents.md](living-documents.md): each governing document as amended, section by section, with the instrument that set its words; corrections and annotations kept apart.
- [document-duties.md](document-duties.md): the duties, prohibitions, permissions, rights, and conditions the governing documents state, read by a phrase grammar and a local model, measured, and reviewed by a person.
- [document-tools.md](document-tools.md): the open-source tools for the scans (Ollama, AnythingLLM, OCR engines) and how each joins jason.
- [letters.md](letters.md): the letter templates in Drive, their `{VARIABLE}` tokens, and filling a copy.
- [packets.md](packets.md): several documents (the annual disclosures) assembled into one PDF.
- [mystique-site.md](mystique-site.md): the association's public Google Site, its embedded Drive folders, and the page-to-library map.
- [photos.md](photos.md): photos taken in from shared Google Photos albums, kept in jason's album and in Drive.
- [registers.md](registers.md): running records kept as Google Sheets (action items, hold notices, approvals, rule changes).

### Document models

- [document-models/README.md](document-models/README.md): the framework; a typed record and findings per document kind, and the coverage.
- [document-models/contracts.md](document-models/contracts.md): insurance policies, certificates, contracts, proposals, leases, and settlements.
- [document-models/correspondence.md](document-models/correspondence.md): letters that are not legal, bills, statements, or meeting records.
- [document-models/elevated-elements.md](document-models/elevated-elements.md): the SB 326 exterior elevated elements report (Civil Code 5551).
- [document-models/financial.md](document-models/financial.md): bank statements, treasurer's reports, budgets, the CPA review, tax bills, and reserve studies.
- [document-models/governing.md](document-models/governing.md): declarations, amendments, annexations, bylaws, rules, deeds, DRE reports, maps, and plans.
- [document-models/insurance-claims.md](document-models/insurance-claims.md): insurance claim papers, all confidential.
- [document-models/invoices.md](document-models/invoices.md): invoices, utility bills, and tax returns.
- [document-models/legal.md](document-models/legal.md): delinquency notices, liens, legal letters, escrow requests, and other transfer documents.
- [document-models/meetings.md](document-models/meetings.md): minutes, agendas, resolutions, and elections.
- [document-models/roof-inspections.md](document-models/roof-inspections.md): what governs the roofs, the roof inspection reader, and the leak calls by building.
- [rag-roadmap.md](rag-roadmap.md): document models, kinds, and retrieval contexts; what exists and what is next.

## Meetings, board, and minutes

- [board-agenda.md](board-agenda.md): the board's action items, the meeting schedule, and drafting the next agenda and minutes.
- [meetings.md](meetings.md): the meeting records catalog across Zoom, Drive, and PayHOA, and its checks.
- [calendar.md](calendar.md): meetings, notice and hearing deadlines, and recurring deadlines on Google Calendar.
- [zoom.md](zoom.md): the Zoom meeting history and disciplinary hearings under Civil Code 5855.

## Owners, notices, and forms

- [owner-information.md](owner-information.md): the owner information cycle (Civil Code 4040, 4041) from law to delivery.
- [drafts-and-forms.md](drafts-and-forms.md): Gmail drafts (never sent) and the request forms in Google Forms.
- [forms.md](forms.md): the paper forms reference: what jason makes, sends, and reads back.
- [form-reader.md](form-reader.md): reading returned forms (PayHOA, typed PDF, paper) and their markers.
- [form-identifiers.md](form-identifiers.md): the campaign and copy markers on what jason sends; a marker is a hint.
- [form-design.md](form-design.md): the form layout that guards against poor data entry (`jason form-lab`).
- [form-fuzzer.md](form-fuzzer.md): testing the paper form and its reader with made-up answers and bad scans.

## Law, legal, insurance, and claims

- [community-manager.md](community-manager.md): the manager's duties and the statutes they sit on.
- [notices.md](notices.md): every notice the law requires (recipients, method, clock, content), the instruments that change a governing document, unreachable owners, and the proof of notice.
- [manager-review.md](manager-review.md): how jason reviews a task: the base prompt, the task prompts, and the context pack.
- [law-history.md](law-history.md): the Davis-Stirling Act's former sections, their successors, and every change since 2011.
- [statute-alignment.md](statute-alignment.md): which provision continues which between two versions of the Act.
- [legal-hold.md](legal-hold.md): legal holds: the register, Vault, `jason_hold` labels, and custody checks.
- [insurance-policies.md](insurance-policies.md): each insurance policy term by term from its declarations, beside the policy sheet.
- [insurance-and-deadlines.md](insurance-and-deadlines.md): each policy's term against its letters and premiums, and recurring deadlines with their evidence.
- [incidents.md](incidents.md): the maintenance history and insurance claims by unit and building.
- [laws/README.md](laws/README.md): the laws that govern a California common interest development; the obligation index.
- [laws/obligations.md](laws/obligations.md): what the association must do under the Civil Code.
- [laws/records.md](laws/records.md): association records and annual reports (Civil Code 5200-5240, 5300-5320).
- [laws/reserves.md](laws/reserves.md): reserve studies and reserve funds, with the recent amendments.
- [laws/bpc.md](laws/bpc.md): the duties of a common interest development manager (Business and Professions Code 11500-11506).
- [laws/assist.md](laws/assist.md): what jason can assist with, duty by duty.

## Mail, email, Zoom, and vendors

- [mail.md](mail.md): the PostScanMail mailbox: the read-only API, the sync, and the sort into what to act on.
- [gmail.md](gmail.md): the association's Gmail as a source, headers only, and vendor contacts against PayHOA.
- [vendor-portals.md](vendor-portals.md): vendor customer portals (ProActive on FieldPortals), the invoice check, and the PayHOA verification.
- [pest-management.md](pest-management.md): who is responsible for pests, what the vendor must do, and how jason reads the vendor's record.

## Property records and county

- [property-histories.md](property-histories.md): each unit's chain of title, deed prices, assessed bases, and the audit against the tax bills.
- [recorded-instruments.md](recorded-instruments.md): every filing in the county's public index other than conveyances, and the lifecycle each opens or closes.
