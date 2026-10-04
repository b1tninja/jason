# Legal, collections, and transfer documents

The `legal` group covers ten kinds: `delinquency_notice`, `recorded_lien`, `legal_correspondence`, `legal_brief`, `escrow_request`, `owner_statement`, `owner_history`, `form`, `membership_list`, and `inspection_report`. The models live in `jason.community.models.legal_*`:

| Module | Models (registration order) | Kinds |
|---|---|---|
| `legal_collections` | `pre-lien-notice`, `reimbursement-assessment-notice`, `payhoa-owner-statement`, `helsing-owner-history` | delinquency_notice, owner_statement, owner_history |
| `legal_liens` | `notice-of-delinquent-assessment`, `mechanics-lien-release-bond`, `mechanics-lien` | recorded_lien |
| `legal_letters` | `legal-letter`, `mediation-brief` | legal_correspondence, legal_brief |
| `legal_records` | `resale-document-order`, `association-form`, `membership-list` | escrow_request, form, membership_list |
| `legal_inspections` | `signal-service-fire-alarm`, `inspection-report` | inspection_report |
| `legal_shared` | none (the CIV 5650 limits, address and parcel readers, the former-section finder) | |

Owners' names and account numbers stay out of every record. A record keeps the development's street address, the unit, the building, and amounts in integer cents; a boolean (`names_owner`, `names_seller`, `names_buyer`, `carries_personal_data`) says the text names a person. The membership list record holds only counts and column names.

Every statute below is quoted from `data/authorities/CIV`. A PROBLEM finding means the text itself falls short; a CHECK is what the text cannot show (a mailing receipt, the board's vote, a stamp).

## Coverage

Per-kind counts come from `jason models`. The pre-lien reader does not require `total_due`: a letter with no itemized statement has no total to read, and `no-itemized-statement` reports that. The `delinquency_notice` fill counts mix two models (pre-lien notices and reimbursement notices), so an empty field may simply not apply.

This association's findings are in its private notes (mystique/notes/document-models/legal.md).

## Delinquency notices

**Law.** At least 30 days before recording a lien, the association sends the owner of record, by certified mail, the notice CIV 5660 describes (quoted in `CIV-5650-5690.md`):

- its collection and lien enforcement procedures and how the amount is figured, the right to inspect records under 5205, and the foreclosure warning in capitals (5660(a));
- an itemized statement of the charges (5660(b));
- that no charges are owed if the assessment was paid on time (5660(c));
- the right to meet the board (5660(d)), where the owner may ask for a payment plan (5665);
- the right to meet and confer (5660(e)) and to ADR before foreclosure (5660(f)).

An assessment is delinquent 15 days after it is due. The late charge is at most 10 percent or $10, whichever is greater. Interest is at most 12 percent a year, starting 30 days after the due date (5650(b)). Only the board decides to record a lien, by majority vote in an open meeting, recorded in the minutes (5673). Only the board decides to foreclose a recorded lien, by majority vote in executive session, and it may not delegate that decision to an agent (5705(c), quoted in `CIV-5700-5740.md`). A lien is foreclosed only when the delinquent assessments alone, without late charges, fees, costs, and interest, reach $1,800 or are more than 12 months delinquent (5720(b)).

**Layouts.** The association's "Notice of Default and Demand for Payment", in two forms: counsel's letter, which carries the attorney's Account Transaction Report, the Statement of Rights, the enclosed collection policy, and reprints of 5660 and 5720; and the board's letter, which offers a payment plan and carries no ledger. The reader strips the reprinted statute before looking for the 5660 items, so a quotation of the law does not count as the notice saying it.

**`PreLienNotice` fields:**

- **Letter:** `notice_date`, `as_of`, `title`, `sender`, `sender_kind`, `manager`, `ledger_by`. The sender is a law firm the specification's sender directory lists when the letter's head names one and is not the board's own letterhead; `manager` and `ledger_by` (who printed the enclosed ledger) come from the same directory (`sources.sender_name`). A firm or manager it does not list is not named.
- **Unit:** `property_address`, `building`, `unit`, `names_owner`.
- **Stated terms:** `days_delinquent_stated`, `cure_days`, `foreclosure_days_after_lien`, `lien_threshold`, `collections_threshold`, `payment_plan_offered`, `board_decides_lien`, `foreclosure_by_agent` (the letter has the collection agency begin foreclosure), `certified_mail`.
- **5660 items:** `elements`, a tuple of `PreLienElement`.
- **Ledger:** `charges` (`Charge` rows: date, description, `ChargeKind`, signed amount, running balance), `total_due`, `assessments`, `late_charges`, `interest`, `payments`, `monthly_installment`.
- **Policy:** `policy_enclosed`, `policy_in_text`, `policy_effective`, `policy_late_charge_percent`, `policy_interest_percent`, `statute_reprinted`, `former_sections`.

**Checks:**

- A 5660 item missing from the letter (PROBLEM). A missing itemized statement is a CHECK, because it may have been a separate enclosure.
- A lien threatened sooner than 30 days (PROBLEM, 5660).
- Certified mail not shown (CHECK).
- The earliest lien date and the 5673 vote (INFO).
- Late charges over the 5650(b)(2) cap, or covering several installments, and interest over one month at 12 percent of the prior balance (CHECK).
- The ledger total against the stated total due (PROBLEM).
- Policy rates over the caps (PROBLEM).
- Citations of the pre-2014 Civil Code 1350-1378 numbering (CHECK).
- The collection agency said to begin foreclosure (CHECK, 5705(c)). When the letter also states no $1,800 assessments floor, only a balance, `foreclosure-floor-not-stated` (CHECK, 5720(b)).

**`ReimbursementNotice`** (the board's reimbursement assessment letter) records the date, the unit, the amount, the contractor, the invoices attached, and the CC&R sections cited. Its checks:

- No hearing notice (CHECK). A charge for common-area damage takes a 10-day hearing notice and a written decision within 14 days before it is effective (CIV 5855(a), (f), (g)). Damage to exclusive-use common area, such as a garage, counts.
- The 5725(a) limit on making the charge a lien (INFO).

This association's findings are in its private notes (mystique/notes/document-models/legal.md).

## Owner statements and owner ledgers

**`OwnerStatement`** reads PayHOA's owner statement. Its fields are `statement_date`, the association and remit-to addresses, the unit, `charges`, `duplicated_lines`, `amount_due`, `lines_total` (repeats included), `unique_total`, the stated late fee and monthly interest rates, and days from each installment's due date to its late fee and interest.

Checks:

- Repeated lines. When the amount due counts each line once, this is an INFO: the PDF's text layer is doubled. When the amount due counts both copies, it is a PROBLEM under 5650(b)(2). Otherwise it is a CHECK.
- Rates over the caps (PROBLEM).
- A late fee before day 15, or interest before day 30 (PROBLEM, 5650(b)).

**`OwnerHistory`** reads a prior manager's owner ledgers: a single account, or the whole roll of accounts. The record has `manager`, `report_date`, `account_count`, `total_balance`, `accounts_with_balance`, and `accounts_over_90_days`. Each `AccountHistory` gives:

- the unit's address, building, and unit number;
- the first and last posting and the number of entries;
- the installment, and the totals of assessments, payments, late fees, interest, and credits;
- the balance and the four aging buckets;
- counts of running-balance breaks, late fees posted before day 15, late fees over the cap or covering several installments, and high interest lines.

Checks:

- Late fees posted before the assessment is delinquent (CHECK, 5650(b)).
- Late fees over the cap. A lump may gather several months, so this is a CHECK.
- Late fees covering several installments (CHECK).
- High interest lines (CHECK).
- Aging buckets that do not add to the balance (CHECK).
- Running-balance breaks (CHECK).
- Accounts over 90 days (INFO, 5660 and 5673).

A late fee posted on the 15th for an installment due on the 1st is 14 days, one day before the assessment is delinquent under 5650(b).

This association's findings are in its private notes (mystique/notes/document-models/legal.md).

## Recorded liens

**Law.**

- **Notice of delinquent assessment.** It states the amount, a legal description, and the record owner (5675(a)). The itemized statement is recorded with it (5675(b)). It names the trustee and the trustee's address (5675(c)), and is signed by the designated person or the president (5675(d)). A copy is mailed within 10 days (5675(e)).
- **Release and foreclosure.** A release is due within 21 days of payment (5685(a)). The foreclosure floor is $1,800, or 12 months (5720(b)).
- **Mechanics lien.** Its contents are set by CIV 8416(a) (demand, owner, work, hirer, site, claimant's address, proof of service, statutory notice, verification). An action is due within 90 days or the lien expires (8460(a)).
- **Release bond.** It is 125 percent of the claim, by an admitted surety (8424(b)). Suit on the bond is due within six months of notice (8424(d)).

**Layouts.**

- A collections law firm's "Notice of Claim of Lien for Delinquent Assessments", with Exhibit A (the legal description) and Exhibit B (the itemized statement). `requested_by` is the law firm the sender directory lists (`sources.sender_name`), else the requester as the recorder's block prints it.
- A claimant's counsel's "Notice and Claim of Mechanic's Lien" for a lumber supplier. One file also carries the release of the earlier lien.
- The surety's "Bond for Release of Mechanic's Lien". The sum is written out in words, and `words_to_cents` reads it.

**`AssessmentLien` fields:**

- **Recording:** `document_number`, `recorded`, `recording_fee`, `requested_by`.
- **Association:** `association`, `association_address`, `declaration`.
- **Unit:** `property_address`, `building`, `unit`, `apn`, `legal_description`, `names_owner`.
- **Amounts:** `amount`, `as_of`, and `items` (`LienItem`: description, kind, amount, months, rate). Also `items_total`, `itemized_statement`, `delinquent_assessments`, `months_delinquent`, and the interest and late-charge rates.
- **Enforcement:** `trustee`, `trustee_address`, `elects_to_sell`.
- **Signing:** `signer_capacity`, `signed_by_agent`, `dated`, `mailing_statement`, `notarized`.

**Checks.** The PROBLEM findings, where the text falls short:

- The legal description, the itemized statement, or the trustee's address is missing, or the items disagree with the amount (5675).
- The rates are over the caps.

The CHECK findings:

- The agent's signature (5675(d)).
- The certified mailing by recording + 10 days (5675(e)).
- The pre-lien notice by recording − 30 days (5660).
- The board vote (5673).
- An APN not among the specification's parcels.
- A building that disagrees with the specification.
- A document number taken from the file name.

The INFO findings are the 5720(b) floor and the 5685 release duty.

**`MechanicsLien`** records the claimant, the amount, the work, the hirer, the prime contractor, the reputed owner (an entity only), the properties, APNs, and buildings, the statutory notice, verification, and service, and the releases in the file. Its checks:

- An 8416(a) part missing (CHECK).
- The 90-day action deadline (INFO once passed).
- The file-name number against the stamp (CHECK).

**`LienReleaseBond`** records the principal, surety, obligee, bond and lien amounts, the lien's recording date, the statute, and the date. It checks the 125 percent test (PROBLEM if under) and flags the admitted surety as a CHECK.

This association's findings are in its private notes (mystique/notes/document-models/legal.md).

## Legal correspondence and briefs

**`LegalLetter` fields:**

- **Letter:** `letter_type` (`LetterType`: settlement disclosure, IDR/ADR offer, membership update, lien resolution, trust disbursement), `letter_date`, `sender`, `sender_is_counsel`, `recipient`, `names_owner`, `property_address`, `building`, `subject`.
- **Status:** `draft`, `privileged`, `delivery`.
- **Matter:** `parties` (entities), `buildings_named`, `settlement_amount`, `amounts`.
- **Citations:** `civil_code`, `former_sections`, `ccr_sections`.
- **Dispute timing:** `response_days`, `board_decision`, `decision_notice`, `adr_article_attached`.
- **Credentials:** `prints_credentials` (never the login itself).
- **CIV 6100 items:** `defects_described`, `repair_estimate`, `other_claims_status`.

**Checks:**

- **Settlement letter.** A missing description of the defects (PROBLEM, 6100(a)(1)). A missing estimate of when (CHECK, 6100(a)(2), since 6100(b) allows a later amendment). A missing status of the other claims (PROBLEM, 6100(a)(3)).
- **IDR/ADR offer.** A response window under 30 days (CHECK, 5935(a)(3)). The ADR article not attached (CHECK, 5935(a)(4)). Days from the board's action to its written decision (5855(f), a PROBLEM over 14).
- **Any letter.** Former section numbers, drafts, printed credentials (CHECK), and privilege (INFO, 5215(a)(3)).

**`LegalBrief`** records:

- the date and the privilege, with the Evidence Code sections it cites;
- the caption, the forum and event date, the neutral's firm, and the author firm;
- the units and buildings it states, the claims basis (SB800), and the expert's total cost of repair with its date.

It checks the brief's unit count against the specification.

This association's findings are in its private notes (mystique/notes/document-models/legal.md).

## Escrow requests

**Law.**

- The association delivers the 4525 documents within 10 days of a written request (4530(a)(1)).
- It gives a fee estimate on the 4528 form first (4530(b)(2)). The fees are its actual cost, and are billed separately (4530(b)(1), (4)).
- It charges no other transfer fee beyond its records-change cost (4575).

**`EscrowRequest`** reads the resale order export: the association, the unit, the requesting company, the order type, the escrow number, the dates ordered, paid, expected, completed, and closing, the sales price, whether the buyer will occupy, whether there is a VA loan, the documents, and the fee. Buyer and seller identities become the booleans `names_seller` and `names_buyer`.

Its checks:

- Completion over 10 days (PROBLEM), or overdue with no completion (CHECK).
- No fee in the text (CHECK, 4530(b)(2)).
- No document list (INFO).
- The 4575 limit and the pending roll change (INFO).

This association's findings are in its private notes (mystique/notes/document-models/legal.md).

## Forms

**`Form`** records:

- `form_type` (`FormType`), `title`, `issuer`, `filled`, `carries_personal_data`;
- the return window, the CC&R and bylaw sections, the outside statutes (CVC 22658), and the signature lines;
- for a petition: purpose, threshold, signatures required, units listed, and building-page mismatches;
- for an architectural application: lead days, and whether it states a response time or reconsideration;
- for an assessor change of address: APNs, property address, new mailing address, effective date, and signed date;
- for a filled resident registration: the property address, from the text or else the file name, which names the unit (the handwriting rarely survives OCR).

The fill counts mix several form types, so most fields apply to one form each. A handwritten date garbled in the OCR stays empty.

Its checks:

- A completed form with a resident's data (CHECK, 5215(a)(4)).
- A petition's signatures against the threshold percentage of the specification's units, and each listed address against its building page.
- An architectural application with no maximum response time (CHECK, 4765(a)(1)) or no reconsideration procedure (CHECK, 4765(a)(4), (5)).
- An assessor filing's APNs against the specification's parcels, and its mailing address against the specification's current address.

This association's findings are in its private notes (mystique/notes/document-models/legal.md).

## Membership list

**Law.** The list holds each member's name, property address, mailing address, and email, leaving out members who opted out (5200(a)(9), 5220). A member asking for it states a purpose (5225).

**`MembershipList`** records `as_of` (the file's period, or the latest date a row carries), `rows`, and `columns` (header names only). It also records which of the four statutory fields exist, rows with an email or mailing address, rows rented, `opt_out_column`, `extra_columns`, and `distinct_properties`.

Its checks:

- The property count against the specification (CHECK).
- A statutory field missing (CHECK).
- No opt-out marker (CHECK, 5200(a)(9), 5220).
- Extra columns to strip before sharing (INFO, 5215(a)(4)).

This association's findings are in its private notes (mystique/notes/document-models/legal.md).

## Inspection reports

No Davis-Stirling section shapes these reports. The vendor's standard does (NFPA 72, NFPA 25), and jason holds no copy of it. The cadence comes from the specification's `obligations`: the fire sprinkler inspection and the backflow test are yearly. A system with no obligation gets no due date. Both models return nothing for an SB 326 balcony report, which `elevated_elements` reads.

**Layouts.** `signal-service-fire-alarm` reads the NFPA 72 report of `Signal Service` (a declared adapter, [adapters.md](../adapters.md)). `inspection-report` reads another vendor's labeled report (inspection or test date, tested by, license, pass or fail, deficiencies, next due).

**`InspectionReport` fields:**

- **Report:** `system` (`InspectedSystem`), `standard`, `inspector_firm`, `inspector_license`, `technician`, `inspection_date`.
- **Site:** `building`, `site_address`, `customer_city`, `monitoring_company` (the company block, else the supervising station the equipment table names), `accepted_by`.
- **Equipment:** `equipment` (`EquipmentTally` per type), and the device totals, tested, passed, failed, and not tested.
- **Deficiencies:** `deficiencies` (`Deficiency`: location, device, comment, status), `open_deficiencies`.
- **Outcome:** `result` (`Result`), `comments`, `next_due`.

**Checks:**

- An open deficiency or failed device (PROBLEM).
- Devices not tested (CHECK).
- No acceptance signature (CHECK).
- The vendor's customer record outside Sacramento (CHECK).
- The building against the specification (CHECK).
- The next due date from the report or the specification's cadence. It is a PROBLEM when past, and a CHECK within 60 days.

NFPA 72 sets most fire alarm tests yearly; a fire alarm row in the specification's `obligations` gives the due date.

This association's findings are in its private notes (mystique/notes/document-models/legal.md).

## What the texts cannot show

- Whether a notice went by certified mail, or when it arrived.
- Whether the board voted to record a lien (see the minutes).
- Whether a designated agent may sign.
- Whether a hearing was noticed separately.
- A stamp or signature that is an image.
- Whether a surety is admitted.
- Whether a mechanics lien claimant sued or recorded a lis pendens.
- Which 4525 documents escrow received, and the fee charged.
- Who opted out of the membership list.

Scanned pages lose digits and dates to OCR (the lien's signing date, the bond's recording stamp). The readers leave those blank rather than guess.
