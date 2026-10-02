# Document models

A `DocumentKind` says what a file is. A document model says what is in it. Each model reads the text jason keeps for a file (the library's text cache, OCR included) into a typed record of the facts that kind carries. Its checks then turn the record into findings. Where a statute shapes the document, a finding cites the subdivision, for example CIV 4950 for minutes or CIV 5551 for the balcony report. A finding is a lead for a person, never a determination.

## Framework

- `jason.community.document_models` holds the pieces:
  - `DocumentModel`: set `kind` or `kinds`, `name`, and `required`, then implement `parse` and `check`;
  - `Finding` and `Severity`: `info` is worth knowing; `check` means a person should look, because the text cannot show it; `problem` means the text shows a shortfall;
  - `ModelContext`, the `register`/`read` registry, and the shared text helpers.
- `jason.community.models` is the package of model modules. Each module registers its models when the package is imported, and a new module needs no entry anywhere else. A kind may have several models, most specific first: a vendor's invoice layout comes before the general invoice. A model that does not recognize a text returns `None`, and a miss stays a miss.
- `jason.tasks.document_models` runs the models:
  - `run` reads every classified library file with its kind's models and writes `data/documents/readings.json`;
  - `read_file` reads one file on disk, such as a Drive copy the library lacks;
  - `coverage` gives, per kind, the files, the files with text, the files read, and the complete readings;
  - `summary` holds back a confidential file's fields unless asked.

`jason models` runs the library, `jason models --kind minutes --show` prints the stored readings, and `jason models --file X.pdf --kind elevated_element_inspection` reads one file. The `document_models` MCP tool reads the stored readings and uses disk only.

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
