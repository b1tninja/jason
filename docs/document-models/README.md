# Document models

A `DocumentKind` says what a file is. A document model says what is in it. Each model reads the text jason keeps for a file (the library's text cache, OCR included) into a typed record of the facts that kind carries. Its checks then turn the record into findings. Where a statute shapes the document, a finding cites the subdivision, for example CIV 4950 for minutes or CIV 5551 for the balcony report. A finding is a lead for a person, never a determination.

## Framework

- `jason.community.document_models` holds the pieces:
  - `DocumentModel`: set `kind` or `kinds`, `name`, and `required`, then implement `parse` and `check`; a reader whose record has findings that depend on the date lists the lens checks in `lens_checks`, and one whose record has a field from another store fills it in `enrich` (both below);
  - `Finding` and `Severity`: `info` is worth knowing; `check` means a person should look, because the text cannot show it; `problem` means the text shows a shortfall;
  - `ModelContext`, the `register`/`read` registry, and the shared text helpers.
- `jason.community.models` is the package of model modules. Each module registers its models when the package is imported, and a new module needs no entry anywhere else. A kind may have several models, most specific first: a vendor's invoice layout comes before the general invoice. A model that does not recognize a text returns `None`, and a miss stays a miss.
- `jason.tasks.document_models` runs the models:
  - `run` reads every classified library file with its kind's models and writes `data/documents/readings.json`;
  - `read_file` reads one file on disk, such as a Drive copy the library lacks;
  - `coverage` gives, per kind, the files, the files with text, the files read, and the complete readings;
  - `summary` holds back a confidential file's fields unless asked.

`jason models` runs the library, `jason models --kind minutes --show` prints the stored readings, and `jason models --file X.pdf --kind elevated_element_inspection` reads one file. The `document_models` MCP tool reads the stored readings and uses disk only.

## A reading and its reviews

This is step 2 of [ingestion-and-review.md](../ingestion-and-review.md): the review store and the first lens. A reading says what the document says. What depends on the date is a **review**, made by a lens from the reading's stored fields.

**What a consumer sees has not changed.** `DocumentModel.read` joins the lens's findings to the reading's own, as of the context's date, in the order they always had. `ModelReading.findings`, `as_dict`, and the rows in `data/documents/readings.json` show the same findings and fields as before. The new keys only say which part is which.

**The parts of a reader:**

| Step | What it may read | What it gives |
|---|---|---|
| `parse` | the text (and, for now, the specification) | the record's fields |
| `enrich` | another store | the fields named in `enriched`, filled after the parse |
| `check` | the record, the specification, other stores | the reading's own findings, and a slot for each lens check |
| a lens check | the fields it names, the as-of date, and the facts it names | findings, and fields derived as of the date |

**A lens** (`jason.community.reviews.Lens`) is a record: its key, the question it asks, whether it needs an as-of date, its checks, the kinds it applies to (from the readers that list its checks), what it reads, and its version. The version is a hash of the lens module's source and of every module that registers one of its checks.

**A lens check** is a row, registered beside the record it reviews:

```python
@AS_OF.check("lease-term", Lease, fields=("term_end",))
def lease_term(r, as_of, _facts=None) -> list[Finding]: ...
```

- **It sees only what it names.** The check is given the named fields, rebuilt from their stored (JSON) form by the record's type hints, and the date. It is given the same thing at the reading and from a stored row, so it finds the same thing either way.
- **The specification comes in as facts.** A check that needs the specification names a function `(fields, community) -> facts`. It gets the facts, never the specification. The facts have a digest, so a changed fact makes the review again.
- **It reads no store.** A check that needs another document or store is not an as-of check (below).
- **It may derive a field.** A check returns `Reviewed(findings, fields)` to fill a field as of the date. The reader's `parse` leaves that field empty.

**A slot keeps the order.** A reader lists its checks in `lens_checks`. Its `check` returns a lens check among its findings where that check's findings go, and `read` fills the slot. A check with no slot goes last. A slot the reader does not list is an error.

**A review** (`reviews.Review`) is one lens applied to one document's stored fields:

| Part | What it holds |
|---|---|
| Key | the document's id, the text's digest (`textSha`), the lens, the lens's version, and the as-of date |
| What it read | `fieldsSha` (the fields its checks name), `factsSha` (the facts they name), and `readingVersion` (the reader's version the fields came from) |
| What it found | each check's findings, each with its basis and the lens's key, and the derived fields |
| Who made it | `producedBy`: `rule` for a check function |

**A review is made again only when its key changes.** With the same key, and the same fields and facts, the stored review stands and no check runs. `jason models` hands each reading the reviews already stored for its document, text, and date.

**The store** (`jason.tasks.document_reviews`) is `data/reviews/documents/<lens>/<as-of>.json`: one lens's reviews as of one date, by document id, written under the store lock. An earlier date's file is kept. `data/reviews/<task>/` belongs to the manager-review packs.

**`jason models --as-of DATE`** makes the as-of lens's reviews again from the stored rows' fields, saves them, and prints what changed since the rows were stored: findings that appear, vanish, or are reworded, and derived fields that moved.
- It reads no document and leaves `readings.json` as it is.
- Only the lens's findings move. A reading's own findings stand as of the date the document was read.
- `document_reviews.joined_rows` gives the stored rows as they stand under the lens as of a date, for a caller that wants them.

**What a row says of the join:**

| Key | What it holds |
|---|---|
| `lens`, on a finding | the lens that made it; a reading's own finding has none |
| `lenses` | per lens: its `version`, its `asOf` date, `slots` (per check, how many of the row's other findings stand before it), and `fields` (the fields it derived) |
| `enriched` | the `fields` an enrichment may fill, and the `basis` of what it read |

`document_models.parts(row)` takes a row apart along those lines: ingestion (the parsed fields and the text-only findings), the enriched fields, each lens's part, and the findings a reader's own check still makes from elsewhere.

**The as-of lens** (`reviews.AS_OF`, key `as-of`) reads the stored fields and, for two checks, facts from the specification. Its checks:

| Check | Reader | Findings | Facts |
|---|---|---|---|
| `contract-term` | contract, nahs-roof-estimate | `term-ended`, `auto-renewal`; derives `current_term_end` | |
| `proposal-offer` | proposal, nahs-roof-estimate | `offer-open`, `offer-lapsed` | |
| `policy-term` | nfip-flood-declarations, policy-declarations | `term-ending`, `term-ended`, `term-superseded`, `next-term-issued` | the policy sheet's renewal date for the policy |
| `certificate-lines` | acord-certificate | `certificate-expired`, `lines-expired`, `lines-expiring` | |
| `lease-term` | lease | `lease-ending`, `lease-ended` | |
| `response-deadline` | the correspondence readers | `response-deadline` | |
| `minutes-as-of` | meeting-minutes | `draft-after-next-meeting`, `minutes-draft`, `minutes-due` | |
| `lien-action-deadline` | mechanics-lien | `action-deadline`, `action-deadline-passed` | |
| `report-expiry` | dre-public-report | `report-expired` | |
| `election-materials` | election-results | `keep-election-materials` | |
| `next-inspection-due` | signal-service-fire-alarm, inspection-report | `next-due` | the specification's cadence for the system |
| `next-elevated-inspection` | sb326-report | `next-inspection` | |
| `loss-run-age` | loss-run | `stale-loss-run` | |
| `resale-documents-overdue` | resale-document-order | `documents-overdue` | |
| `invoice-dated`, `invoice-due` | invoice, flood-premium-notice | `dated-in-future`, `due-date-passed` | |
| `flood-renewal-due` | flood-premium-notice | `flood-renewal-due` | |
| `tax-deadline` | tax-return | `tax-deadline` | |

**Two fields moved out of `parse`:**
- **A contract's `current_term_end`** is derived by `contract-term`. The contract reader's parse gives the same record on any day.
- **An agenda's `notice_sent` and `notice_subject`** are filled by `AgendaModel.enrich` from the communications log. The agenda reader's parse reads no store.

**Not moved: checks that need another document or store.** They are reviews of a collection, the next lens. Until then they stay in the readers' own checks and stand as of the date the document was read.
- **Date and store together:** an agenda's `no-minutes-on-file`, and whether its `posting-date-not-shown` says the log has no notice; a reserve study's `next-site-visit` and `no-current-study`.
- **Another document or store:** an agenda's `prior-minutes-not-on-file`; the minutes' `agenda-on-file`, `no-agenda-on-file`, `not-on-agenda`, and `executive-session-not-noted`; a resolution's `on-agenda`; election results' `results-in-minutes`; a bank statement's `reconciled`; a tax bill's `paid-per-county`; a treasurer's report's `ledger-changed-since`; a budget's `reserve-transfer-vs-study`; a policy page's `premium-change`, `limit-reduced`, `deductible-raised`, and `overlapping-flood-policy`; a certificate's `no-policy-file-for-term` and `flood-line-differs`; a reserve study's `superseded`; a governing document's `cites-repealed-sections`.
- **Fields still read from context at `parse`:** many readers fill a field from the specification (a client's name, a building), and the invoice reader reads the vendor directory to recognize a vendor. `jason models --basis` lists them.

## What a reading records about its own making

This is the inventory, step 1 of [ingestion-and-review.md](../ingestion-and-review.md). It changes no reader and no finding. It records where each came from.

**Each stored row** carries, beside its fields and findings:

| Key | What it holds |
|---|---|
| `textSha` | the SHA-256 of the text the reader was given |
| `asOf` | the date the reader used as today |
| `version` | the reader's version (below) |
| `fieldsBasis` | what `parse` read to fill the fields |
| `basis`, on each finding | what the call that produced the finding read; on a lens's finding, what the lens declares it reads |

A row stored before these keys has none of them. Every reader of the store treats them as optional.

**A basis** is a set from five words (`Basis`):

| Word | Meaning | How it is observed |
|---|---|---|
| `text` | the document's own text | always, once a basis is observed |
| `profile` | the specification | the reader read `context.community` |
| `store` | another store on disk | the reader read `context.data_dir` |
| `today` | the date of the reading | the reader read `context.today` |
| `law` | a statute or standard | the finding has an `authority` |

A finding whose basis is `text` alone is ingestion. Any other is a review.

**The basis is observed, not declared.** `ModelContext` counts each read of its specification, data directory, and date. `DocumentModel.read` compares the counts before and after `parse`, and before and after `check`.

**Its limits:**
- **The granularity is the call, not the finding.** `check` returns its findings together, so each finding carries everything that call read. "Review" is therefore an upper bound: a finding marked `today` came from a check that read the date, whether or not that finding used it. A finding marked `text` alone needed nothing but the record.
- **The fields have their own basis.** A text-only finding on a record whose fields were filled from the profile or a store is not ingestion yet.
- **A reader's own `read`.** When a reader overrides `read`, what it reads after the base `read` is added to every finding of that reading (`settle`).
- **What goes around the context is not seen:** a cache that an earlier call filled, or a clock a helper reads itself.
- **The file's name, period, and confidential flag are not counted.** They describe the file being read. A field read from the file's name is still not a function of the file's bytes.

**A reader's version** (`reader_version`) is the first twelve hex digits of a SHA-256 over the source of every module in the reader class's line of descent: its own module, its base readers' and mixins', and `document_models.py`. It changes when any of those files changes, and needs no constant to remember. It does not see a helper module the reader only calls into.

`jason models --basis` prints the inventory from the stored rows and reads nothing again:
- per reader and finding code: the count, how many read the text only, the basis, and the class (ingestion, lens, review, or not observed). `lens` is a review a lens made; `review` is one a reader's own check still makes;
- how many of the reviews each lens made, and how many are left in the readers;
- the readers whose fields depend on the profile, a store, or today at `parse`, the fields an enrichment fills, and the fields a lens derives.

Run `jason models` first when the rows are older than these keys.

## Questions for the local model

A document model reads with rules. A question set (`jason.community.question_sets`) asks the local model the same things in words, plus what only a reader of the words can answer. It then sets each answer beside the rule reader's field. `jason models --ask --kind minutes` runs it and writes `data/documents/questions-<kind>.json`.

**Each question** (`jason.community.questions.Question`) names:
- what it asks;
- the answer's type (yes or no, date, number, text, list);
- the law or rule it serves;
- the record field it is compared with.

**The model** (`qwen3.6:27b`, thinking off, temperature 0) answers every question as JSON under a schema: whether the document states it, the value, and a verbatim quote. Each request holds the GPU lock after the preflight, and the text never leaves the machine.

**Each answer is judged:**
- **agrees:** both readers state it, the same way;
- **differs:** both state it differently; a person looks;
- **model only:** the model found what the rules missed; a lead for a new rule;
- **rules only:** the rules found what the model missed;
- **gap:** neither finds it. On a question that serves the law, the document may lack it (no quorum stated, no vote recorded, no open forum noted);
- **ungrounded:** the quote is not in the text, so the answer does not count.

Agreement between two readers that work differently is the confidence. An answer is evidence, never the record.

**Minutes.** The minutes set taught three things, now in the questions and the judge:
- **Joined quotes.** A model joins real passages with "…", so each passage is checked, and a list's entries are each looked for in the text.
- **Silence and "no".** When neither reader finds a yes-or-no fact (no draft mark), the two agree.
- **Headings are not answers.** The heading's scheduled time, an "Open Forum" item title, and a person who only speaks answer nothing; the questions now say so.

**Decisions compared as topics.** The decisions are compared as distinct topics, not a count (`distinct_topics`, `compare_topics`): a retold decision (the same dollar amount, or most of the same words) is one topic. Informal agreements and assignments ("agreed to walk the property at night") belong under next steps, not motions.

**The minutes rule reader, corrected from these leads.** `actions_in` does not count an assignment as a decision: "agreed to walk / contact / look into / prioritize…" with no approval, vote, or motion in the sentence. It also keeps one action per decision; a retelling with the same dollar amount or most of the same words is dropped, and the telling that names a mover or a vote is kept. What still differs between the readers is mostly judgment, such as "agreed to replace the bulb" after a discussion.

**What the judge learned from bills and declarations.** Four generic changes in `jason.community.questions`:
- **Amounts.** A dollar amount is its own answer type. The model writes "$1,234.56", and the judge reads it as integer cents beside the rules' cents. A question with a `minimum` marks a stated amount under the law's floor as `short`.
- **One question, several readers.** A kind read by several readers names each reader's field: `building_limit|limit:flood_zone` means the flood reader's `limit`.
- **Labels apart from values.** A PDF's text layer often sets a label and its value on separate lines, or in the other order. A quote is grounded when all its words sit close together in the text.
- **A "no" is the gap.** When the model says "no" and the rules have nothing, neither reader found the thing asked about.

A priced list is compared as topics with each entry's amount. Two entries with the same amount are one topic only when they share a word stem, so two crime coverages with the same $25,000 limit stay two.

**Insurance policies.** The set has 19 questions. Among them: insurer, policy number, named insured, mailing address (CIV 5810), location, term, building limit, valuation, replacement cost value, deductible, and premium (CIV 5300(b)(9)). It also asks for general liability and D&O limits with the CIV 5800(a)(4) floor of $500,000, the umbrella (CIV 5805(b)), and the crime coverages (CIV 5806). A flood page prints its labels and figures in separate runs, where the rules read better than the model; the model reads the named insured's mailing address and a D&O limit a rule reader can miss.

**Proposals.** The set has 15 questions. Among them: vendor, number, date, work items, total, expiry, exclusions, license number (BPC 7030.5), insurance notices (BPC 7159(e)), warranty, payment schedule (BPC 7159.5(a)), and acceptance. A first question asks whether the document is an offer at all, since a file the proposal reader claims can be a bill.

**Invoices.** The set has 12 questions: vendor, number, date, due date, total, balance due, paid, bill-to, service location, line items, a cited proposal or work order, and a license number. Utility bills are left out. A construction invoice with no license number, or a license other than its proposals', is one to look up on the CSLB's site.

**Rule readers corrected from the question sets.**
- **Proposals.** The proposal reader turns away a bill: a first page that speaks of an invoice number, an amount or balance due, or a receipt, and never of a proposal, estimate, quote, or bid. The contractor license pattern reads "California Contractors License No. 123456-B" and "CSLB# 1234567".
- **D&O.** The D&O declarations are a filled form whose text prints the labels apart from the values. When the value after "POLICY NUMBER:" is the next label, the reader takes the numbered token the page prints twice, the largest round amount as the limit, and the next as the retention.
- **Flood mailing address.** The flood reader takes the named insured's mailing address: of the addresses the page prints, the one carrying an address the association has used, with a box line such as a "PMB" allowed between the street and the city. It then checks it against the current address, box included (CIV 5810).
- **Crime and umbrella mailing addresses.** The crime and umbrella readers take the mailing address the same way, and one check (`mailing_findings`) serves every policy reader. It compares the street, the box the specification requires (`MailAddress.requires`), and its ZIP (`MailAddress.zip`). A carrier's bill is no policy, so no policy reader checks its address.
- **Invoices.** The invoice record carries four more fields:
  - `service_address`: the first community address named;
  - `building`: that address's flood building, by the specification;
  - `reference`: the proposal, estimate, purchase order, work order, or contract billed against;
  - `license`: the contractor's license, by the proposal reader's pattern.

This association's findings are in its private notes (mystique/notes/document-models/README.md).

## Groups

| Group | Kinds | Page |
|---|---|---|
| Legally shaped reports | elevated_element_inspection (SB 326, CIV 5551) | [elevated-elements.md](elevated-elements.md) |
| Meetings | minutes, agenda, executive_session, notice, resolution, committee_report, election_results, ballot | [meetings.md](meetings.md) |
| Financial | bank_statement, treasurer_report, financial_statement, financial_review, budget, annual_disclosure, tax_bill, reserve_study | [financial.md](financial.md) |
| Contracts and insurance | insurance_policy, evidence_of_insurance, contract, proposal, lease, settlement | [contracts.md](contracts.md) |
| Legal and collections | delinquency_notice, recorded_lien, legal_correspondence, legal_brief, escrow_request, owner_statement, owner_history, form, membership_list, inspection_report | [legal.md](legal.md) |
| Governing and property | declaration, bylaws, articles, amendment, annexation, operating_rules, policy, election_rules, grant_deed, dre_report, map, condominium_plan, plan_set | [governing.md](governing.md) |
| Developer securities | security_agreement, subsidy_agreement, surety_bond, bond_release (10 CCR 2792.4, 2792.9, 2792.10) | [../developer-securities.md](../developer-securities.md) |
| Invoices and bills | invoice (with vendor layouts), utility_bill, tax_return | [invoices.md](invoices.md) |
| Roof inspections | inspection_report (RoofChecks' per-building estimate, before the general reader) | [roof-inspections.md](roof-inspections.md) |
| Insurance policies (packets) | insurance_policy: package-declarations, crime-declarations, dno-declarations, umbrella-evidence | [../insurance-policies.md](../insurance-policies.md) |
| Correspondence | correspondence (certified records, letters, member notices, handouts, publications) | [correspondence.md](correspondence.md) |
| Insurance claims | loss_run, claim_letter, claim_payment, claim_authorization, claim_estimate, police_report, manager_case_report | [insurance-claims.md](insurance-claims.md) |

## Kinds added for Drive's archive

The prior manager's archive in Drive is classified by folder (`mystique/documents.py`). That required four new kinds:

- `violation_notice`: courtesy reminders, hearing notices, and fines; confidential;
- `resale_disclosure`: resale certificates and lender questionnaires, the CIV 4525 transfer record; confidential;
- `security_report`: the patrol's daily reports;
- `audio`: the recorded readings of the CC&Rs and bylaws.

The archive's "Statement" folders hold owners' account statements (`owner_statement`, confidential). Its "Vendor Invoices" and "Financial Reports" folders hold invoices, utility bills, and the monthly financial reports.

## Coverage

`jason models` reports, per kind, the files, the files with text, the files read, and the complete readings; `scripts/eval_models.py` measures a kind without saving the readings. A file with no text (a blank template, an image, a scan too poor to read, a text layer of glyph codes that needs OCR) is not read, and a field the text itself lacks keeps a reading incomplete.

This association's findings are in its private notes (mystique/notes/document-models/README.md).
