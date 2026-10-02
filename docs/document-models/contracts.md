# Contracts and insurance

Kinds: `insurance_policy`, `evidence_of_insurance`, `contract`, `proposal`, `lease`, `settlement`.

Modules, all in `jason.community.models`:

- `contracts_insurance`: the policy and certificate models;
- `contracts_agreements`: the contract and proposal models;
- `contracts_leases`: the lease and settlement models;
- `contracts_signing`: the shared reader for signatures and e-signature envelopes. It registers no model.

Amounts are integer cents. Dates are `date`s.

## The law

- **Insurance summary (CIV 5300(b)(9)).** The annual budget report summarizes the property, general liability, earthquake, flood, and fidelity policies. For each it gives the insurer, the type of insurance, the limit, and the deductible, if any. A copy of the declarations page may stand in for the items it prints.
- **Change notices (CIV 5810).** Members get individual notice when one of those policies lapses, or is canceled and not replaced. They also get notice of a significant change, such as a lower limit or a higher deductible. If the carrier sends a notice of nonrenewal and no replacement will be in force when coverage lapses, members are told at once.
- **Director immunity (CIV 5800(a)(4)).** A volunteer director's immunity needs general liability and D&O coverage of at least $500,000 each for 100 or fewer separate interests, and $1,000,000 each above that.
- **Owners' tort protection (CIV 5805(b)).** Owners are protected as tenants in common when general liability coverage is at least $2,000,000 for 100 or fewer separate interests, and $3,000,000 above that.
- **Crime coverage (CIV 5806).** Crime or fidelity coverage must be at least the reserves plus three months' assessments. It must also cover computer fraud and funds transfer fraud, and cover a managing agent.
- **Contracts and approvals as records (CIV 5200(a)(4), (a)(5); 5210(a)(1)).** An executed contract not otherwise privileged is an association record. So is the board's written approval of a vendor's proposal. Both are open to members for the current fiscal year and the two before it.
- **Management agreements (CIV 5375, 5380).** Before a management agreement, the prospective manager gives the board a written statement: its owners, licenses, certifications, affiliated businesses, and referral fees (5375). For an account under 5380(b), transfers out of the reserve or operating accounts need the board's prior written approval. The threshold is the lesser of $10,000 or 5% of budgeted income for 51 or more separate interests (5380(b)(6)(B)).
- **Rentals (CIV 4741(c)).** The governing documents may bar a rental of 30 days or less.
- **Builder settlements (CIV 6100(a)).** After a construction defect settlement with the builder, the association tells its members, as soon as reasonably practicable:
  - that the matter is resolved;
  - which defects it expects to correct, and when;
  - where the other defect claims stand.
- **Managing agent's statement (CIV 5375).** At most 90 days before a management agreement, the prospective manager gives the board a written statement of (a) its owners, or a corporation's directors, officers, and 10 percent shareholders; (b) the licenses they hold, with dates; (c) their certifications and designations; (d) businesses it has an interest in or incentives from; and (e) referral fees from resale-document providers.
- **Contractors (BPC 7030.5, 7159.5).** A licensee prints its license number on every bid and contract. A home improvement contract asks a down payment of at most $1,000 or 10 percent of the price, whichever is less (7159.5(a)(3)), and no payment ahead of the work done or materials delivered (7159.5(a)(5)). Whether a job for the association is a home improvement (BPC 7151.2) the text cannot settle. jason holds no copy of the BPC 7000s yet (`data/authorities/BPC` has 11000-11023 only), so these citations are from the code, unquoted.
- **NFIP co-insurance (44 CFR 61.6).** A condominium building's flood coverage is at most $250,000 a unit. The declarations print the RCBAP's co-insurance test: at a loss the building must be insured to the lesser of 80 percent of its replacement cost or that maximum.

## insurance_policy

Record `InsurancePolicy` has these fields:

- **Policy:** `carrier`, `naic`, `policy_number`, `coverage` (a `Coverage` member), `program`, `form`, `declaration` (`new`, `renewal`, or `revised`), `named_insured`.
- **Location:** `property_location` and `building`. The building comes from the specification's street ranges, or from a "BLDG n" the page prints.
- **Term:** `term_start`, `term_end`, `endorsement_effective`.
- **Coverage:** `limit` (building coverage), `contents_limit` (0 when the page prints "N/A" or "$0" beside the building coverage), `deductible`, `replacement_cost`, `units`, `flood_zone`.
- **Money:** `premium` and `charges`. The charges are the discounted premium, the reserve fund assessment, the federal policy fee, and the HFIAA surcharge.
- **Parties:** `producer` (the agency) and `agent`.
- **Printing:** `printed`.

Layouts:

- `nfip-flood-declarations`: Philadelphia Indemnity's NFIP Residential Condominium Building Association Policy declarations (manageflood), in their new, renewal, and revised forms. The text layer prints the labels apart from their values. The reader keys each value to the label it always sits beside: the building coverage is the first whole-dollar amount after "COVERAGE", and the total is the amount printed under "FEDERAL POLICY FEE:", or "ANNUAL SUBTOTAL:" on a revised page. The premium parts check that reading.
- `policy-declarations`: any other declarations page with "Policy Number", "Policy Period", and "Named Insured" labels. The master, umbrella, crime, and D&O declarations are not in the library, so no real file uses this reader yet.

Checks:

| Code | Severity | When | Authority |
|---|---|---|---|
| `term-superseded` | info | The term ended, and the policy sheet carries a later term for the number, or for the building's flood policy | |
| `term-ended` | check | The term ended and the sheet shows no later term | CIV 5810 |
| `term-ending` | check | The term ends within 60 days | CIV 5810 |
| `next-term-issued` | info | The page runs past the sheet's term in force | |
| `insured-not-association` | problem | The named insured is not the association | |
| `number-not-on-sheet` | check | The number is on neither the current nor the prior list | |
| `building-mismatch` | check | The sheet puts the number on another building | |
| `overlapping-flood-policy` | check | Another flood file in the library covers the same building for an overlapping term | |
| `limit-reduced`, `deductible-raised` | check | Against the same building's previous term in the library | CIV 5810 |
| `premium-change` | info | Against the previous term | |
| `premium-parts` | check | The itemized parts do not add to the total | |
| `coverage-to-value` | info | Building coverage as a share of the replacement cost, and whether it is the NFIP maximum for the units | 44 CFR 61.6 |
| `coverage-below-coinsurance` | check | Building coverage under the lesser of 80% of replacement cost and $250,000 a unit | 44 CFR 61.6 |
| `summary-items-present`, `summary-item-missing` | info, check | Whether the page gives the insurer, type, and limit (and a deductible where it prints one) | CIV 5300(b)(9) |

## evidence_of_insurance

Record `EvidenceOfInsurance` has these fields:

- **Certificate:** `forms` (ACORD 25, 24, 27, 28, and 101), `issued`, `producer`, `certificate_number`.
- **Insurers:** `insurers`, each with its letter, name, and NAIC number.
- **Insured:** `insured`.
- **Coverage:** `lines`, each a `CoverageLine` with the insurer letter, `coverage`, the wording, `policy_number`, `effective`, `expiration`, `limit`, `aggregate`, `deductible`, the flood `building`, and every amount printed.
- **Text:** `description`, `remarks` (the ACORD 101 page), `holder`, `units`.

Layout `acord-certificate`:

- The reader drops the form's printed labels and reads the values in order.
- Each row starts at its insurer letter. A run of letters is a block of rows whose numbers, dates, deductibles, and limits follow column by column; that is how LaBarre/Oksnee prints the property, crime, and D&O lines.
- An unnamed row's type comes from its amounts: general liability prints six, auto one, and umbrella two limits and a retention.
- Rows that name their type ("Property", "Crime/Fidelity Bond", "Employee Dishonesty", "Directors & Officers Liability") use the name.
- The remarks' "Commercial Flood" lines become flood lines with their building.
- It also reads the older Farmers/Russo certificate: no NAIC numbers, with "Limit:" and "Deductible:" labels, and an ACORD 24.

Checks:

| Code | Severity | When | Authority |
|---|---|---|---|
| `certificate-expired`, `lines-expired` | check | Every policy, or some, expired before today | |
| `lines-expiring` | info | A policy expires within 60 days | CIV 5810 |
| `holder-is-association` | info | The holder is the association's own board | |
| `insured-not-association` | problem | The insured is not the association | |
| `number-not-on-sheet` | check | A number on neither the current nor the prior list | |
| `prior-number-for-current-term` | check | The certificate prints a number the sheet lists as an earlier term's, for the term in force | |
| `line-kind-mismatch` | check | The sheet's kind for the number differs from the certificate's line | |
| `no-policy-file-for-term`, `flood-line-differs` | check | A flood line against the library's declarations for that number and term | |
| `volunteer-immunity-coverage` | info, check | General liability and D&O against the director immunity minimum | CIV 5800(a)(4) |
| `owner-tort-coverage` | info, check | General liability plus umbrella against the owners' minimum | CIV 5805(b) |
| `crime-coverage` | check | The crime limit, whether computer and funds transfer fraud are named, and whether the managing agent is named | CIV 5806 |
| `unit-count` | check | The description's unit count against the specification | |
| `summary-items-present`, `summary-item-missing` | info, check | As for policies | CIV 5300(b)(9) |

## contract

Record `Contract` has these fields:

- **Document:** `title`, `form` (agreement, vendor form, engagement letter, or accepted proposal), `dated`, `scope`, `license`, `units`.
- **Parties:** `vendor`, `vendor_role` (from the specification's counterparty directory), `client`.
- **Signing:** `commencement_blank`, `signed_on`, `execution` (executed, signed by one, or not in the text), `signatures`, `envelopes`, `certified`, `blank_signature_lines`.
- **Term:** `term_months`, `auto_renews`, `renewal_months`, `notice_days`, `term_end`, and `current_term_end`, which counts the automatic renewals up to today.
- **Money:** `prices`, each with a label, amount, and period: one time, visit, month, year, hour, unit ("Price per unit to replace ..."), or percent. Also `items`, `total`, `authorized`, `validity_days`.
- **Management terms:** `spending_limit`, `unlimited_transfers`, and `manager_statement`: the CIV 5375 items (`StatementItem`) a statement inside the agreement gives, read from that statement alone by the `STATEMENT_RULES` rows.

The vendor is the specification's counterparty (`Mystique.senders()`) whose words appear first. A name in an address block or an email address does not count ("TO: RealManage", "Association c/o ..."). A vendor the directory lacks is read from the letterhead: the "Company" label, a company suffix, the parties clause, or the website.

The title is an upper-case heading on one line (a logo's stray letter on the line above does not join it). The first 8,000 characters are searched first, then the whole text, since Jensen's specifications addendum comes before its agreement. A heading about the agreement ("PARTIES TO THE AGREEMENT", "SERVICES INCLUDED IN YOUR AGREEMENT") is not a title; a heading the parties clause follows is preferred; a one-word heading takes the upper-case line above it (Signal Service's "COMMERCIAL LEASE ... INSPECTION AGREEMENT"). Else a mixed-case title line ("Proposal", "Bid"). Newman's engagement letter has no title.

The license is a CSLB number, or another board's number with its letters (Pro Active's structural pest control "PR" license).

Layouts:

- `nahs-roof-estimate`: North American Home Services' per-building roof estimates, DocuSigned, with the payment authorization page. It is also registered for `proposal`. The building subtotals must add to the authorized amount.
- `contract`: every other contract, read with rule rows (`PRICE_RULES`, `PERCENT_RULES`, `TERM_RULES`, `NOTICE_RULES`, `SCOPE_RULES`). A new layout is a new row. The rows cover:
  - Bravo Security's service agreement (Adobe Sign);
  - Signal Service's alarm monitoring lease: two DocuSign envelopes with certificates of completion, a 36-month term renewing for two years, and 30 days' notice;
  - Flock's order form: DocuSign anchor tags, 24 months renewing for 24;
  - The Helsing Group's management agreement;
  - Jensen's master landscape agreement;
  - Berding & Weil's contingency fee agreement;
  - Pro Active Pest Control's portal-signed service agreement;
  - North American Home Services' click-accepted inspection agreement;
  - Newman CPA's engagement letter;
  - CalPro's proposal, and All Year Pressure Washing's quote, both accepted with Adobe Sign;
  - Top Garden's bid.

Checks:

| Code | Severity | When | Authority |
|---|---|---|---|
| `association-record` | info | Executed | CIV 5200(a)(4), 5210(a)(1) |
| `unsigned-in-text`, `partly-signed` | check | No signature, or one side only, shows in the text | CIV 5200(a)(4), 5210(a)(1) |
| `no-signing-certificate` | info | A DocuSign envelope without its certificate of completion in the file | |
| `commencement-blank` | check | "commencing on ____" or "made this ____ day" | |
| `client-not-association` | check | The client named is not the association | |
| `term-ended` | info | A fixed term has ended | |
| `auto-renewal` | check within 60 days, else info | The date non-renewal notice is due | |
| `month-to-month` | info | Month to month, with the notice needed to end it | |
| `counterparty-ended` | info | The specification lists the counterparty as a prior manager, so renewal terms no longer run | |
| `authorized-differs` | problem | The items do not add to the authorized amount | |
| `accepted-after-validity` | info | Signed after the offer's window | |
| `service-lines-differ` | check | The monthly service lines do not add to the monthly totals | |
| `unit-count` | check | A unit count in the document differs from the specification | |
| `manager-disclosure` | check | A management agreement with no statement in it | CIV 5375 |
| `manager-statement` | info | The agreement carries the managing agent's statement; the items it gives | CIV 5375 |
| `manager-statement-incomplete` | check | The statement leaves out an item, named by subdivision | CIV 5375(a)-(e) |
| `license-not-printed` | check | Construction work (`CONTRACTOR_WORK` rows, not an inspection or a service) with no license number in the text | BPC 7030.5 |
| `transfers-without-approval` | check | The manager may move funds "without regard to dollar amount" | CIV 5380(b)(6)(B) |
| `spending-limit` | info | The manager's unapproved-expenditure limit | |
| `may-be-privileged` | info | A fee agreement with counsel | CIV 5200(a)(4) |

## proposal

Record `Proposal` has these fields:

- **Offer:** `vendor`, `number`, `prepared_for`, `proposal_date`, `valid_until`, `validity_days`, `scope`.
- **Money:** `items`, `options` (alternative prices), `payment_schedule`, `total`, and `price` (the total, or the lowest option).
- **Acceptance:** `accepted_on`, `execution`, `signatures`.
- **Other:** `license`, `units`.

Layouts:

- `nahs-roof-estimate`;
- `proposal`, which reads:
  - All Year Pressure Washing's quote table;
  - J.B. Bostick's proposal with its PandaDoc signature certificate. Each item's title is the short line before its long description;
  - Good Life Construction's JobTread proposal: issue and expiry dates, and a payment schedule;
  - Pro Elections' letter with two prices ("TOTAL COST if ...");
  - California Builder Services' option pricing ("OPTION 1: ... FEE:"), in a PayHOA attachment.

Checks:

| Code | Severity | When | Authority |
|---|---|---|---|
| `accepted` | check | Accepted: keep the board's written approval with it | CIV 5200(a)(5) |
| `accepted-after-validity` | info | Accepted after the offer's limit | |
| `offer-open`, `offer-lapsed`, `no-acceptance` | info | No acceptance shows | |
| `items-differ-from-total` | check | The priced lines do not add to the total; some may be options | |
| `schedule-differs-from-total` | problem | The payment schedule does not add to the total | |
| `unit-count` | check | Against the specification | |
| `license-not-printed` | check | As for contracts | BPC 7030.5 |
| `down-payment-over-limit` | check | The schedule's deposit is over the lesser of $1,000 or 10 percent of the price | BPC 7159.5(a)(3) |
| `payment-ahead-of-work` | check | A schedule line billed before the work ("Mobilization", "at signing") besides the down payment | BPC 7159.5(a)(5) |

## lease

Record `Lease` has these fields:

- **Parties and place:** `agent`, `premises`, `building`, `dated`.
- **Term:** `term_start`, `term_end`, `month_to_month`.
- **Money:** `rent`, `adjusted_rent`, `deposit`, `deposit_waived`.
- **Signing:** `residents` (a count; no names are kept), `execution`, `signers`, `signed_on`.

Model `lease` reads Belong, Inc.'s lease (Belong signs as the owner's agent, and each e-signature leaves a "Signed on" line) and leases with the same clauses.

Checks:

| Code | Severity | When | Authority |
|---|---|---|---|
| `short-term-rental` | check | A term of 30 days or less | CIV 4741(c) |
| `lease-ended`, `lease-ending` | info | The term has ended, or ends within 60 days | |
| `premises-not-placed` | check | The address is not in a building of the specification | |
| `rent-adjusted` | info | An addendum changes the rent | |
| `unsigned-in-text` | check | No signature shows | |

## settlement

Record `Settlement` has these fields:

- **Agreement:** `title`, `parties` (role and name), `dispute`, `dispute_began`, `exhibits`.
- **Payment:** `payment`, `payment_due_days`, `payee`.
- **Terms:** `builder_claim`, `waives_1542`.
- **Signing:** `execution`, `signatures`, `signed_on`, `blank_signature_lines`.

Model `settlement`. Checks:

| Code | Severity | When | Authority |
|---|---|---|---|
| `unsigned-in-text` | check | The signature page is blank in the text | CIV 5200(a)(4) |
| `member-disclosure` | check | A builder defect settlement | CIV 6100(a) |
| `waives-1542` | info | A Civil Code 1542 waiver | |
| `settlement-payment` | info | The amount, due date, and payee | |

This association's findings are in its private notes (mystique/notes/document-models/contracts.md).

## What the text cannot show

- A signature drawn or pasted as an image.
- Whether the board approved a contract or proposal. That is in minutes or a resolution.
- Whether a management statement under CIV 5375 was delivered.
- The reserve balance and assessments that CIV 5806 compares with the crime limit.
- A policy's own declarations, when they are not in the library.
- A certificate's limits are the producer's summary, not the policy.
- Whether a job for the association is a home improvement contract (BPC 7151.2), and whether a license the text omits is current.
