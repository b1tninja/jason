# Governing documents and property records

The `governing` group covers thirteen kinds: `declaration`, `amendment`, `annexation`, `bylaws`, `articles`, `operating_rules`, `policy`, `election_rules`, `grant_deed`, `dre_report`, `map`, `condominium_plan`, and `plan_set`. The models live in `jason.community.models.governing_*`:

| Module | Models (registration order) | Kinds |
|---|---|---|
| `governing_recorded` | `declaration`, `declaration-amendment`, `declaration-of-annexation` | declaration, amendment, annexation |
| `governing_corporate` | `articles-of-incorporation`, `bylaws` | articles, bylaws |
| `governing_rules` | `election-rules`, `operating-rules`, `board-policy` | election_rules (also tried on operating_rules and policy), operating_rules, policy (also tried on operating_rules) |
| `governing_deeds` | `grant-deed` | grant_deed |
| `governing_plans` | `dre-public-report`, `map`, `condominium-plan`, `plan-set` | dre_report, map, condominium_plan, plan_set |
| `governing_shared` | none (the stamp, citation, and execution readers, and the spec lookups) | |

The models wrap the readers jason already has instead of repeating their patterns:

- `jason.community.readings`: the stamp, the title, the citations and their verbs, the annexed units, the declarant, the amended sections, and the adoption dates.
- `jason.community.parsing`: `GrantDeedMixin`, `apn_fields`, and `unit_fields`.
- `jason.community.consideration`: the granting clause and the transfer tax.
- `jason.community.reports`: `parent_parcel`, `unit_parcels`, and the `PublicReport` rows.

`governing_shared` repairs what OCR does to the input before handing it over:

- a `Doc # 201 91 2201433` stamp whose digits came apart;
- a mangled pre-2018 `BOO!(' 2012t?302 PAGE 1601` stamp. The stamp's printed date supplies the book; otherwise the file name's number does, when its page matches and the legible digits fit;
- an `in Book 20070920 at Page 0938` citation, rewritten as the `as Document No.` form the citation reader knows;
- a `Units 28 through 3 7` range;
- the `GRANT{S) ta` and `(book) 20070920, (page) 938` slips on deeds.

Every statute below is read from `data/authorities/CIV`. A PROBLEM means the text itself falls short. A CHECK is what the text cannot show: a signature image, a notice, a vote, or a stamp OCR lost. Grantors and grantees are public record. The deed record keeps them as the text prints them, and nothing else copies them.

## Coverage

A title company's certified copy carries a handwritten certification of the recorded original; a vision reading of page 1 (`jason library --vision declaration,condominium_plan --pages 1`) reads it. Per-kind counts (files, with text, read, complete) come from `jason models`.

This association's findings are in its private notes (mystique/notes/document-models/governing.md).

## Declaration (CC&Rs)

**Law.** A declaration recorded after 1985 contains the following (CIV 4250(a)):

- a legal description;
- a statement of the development's type;
- the association's name;
- the restrictions meant as enforceable equitable servitudes.

A declaration may not cap rentals below 25 percent of the separate interests (4741(b)). The board had to delete or restate a noncompliant cap by July 1, 2022 (4741(f)). The board may correct cross-references to the repealed Davis-Stirling sections by resolution (4235(a)).

**Layout.** The Inman Thomas restated declaration: a table of contents with page numbers, footer page marks (`- 24 - 9-10-07`), recitals, and articles.

**`DeclarationRecord`** has these fields:

- `title`, `restated`, `recording` (`Recording`: number, date, pages, fees, `unrecorded_copy`, `certified_copy`, `source`), `number`, `recorded`, `declarant`, `project`;
- `phase_one_units`, `total_units`, `buildings`;
- `prior_declaration` and `prior_declaration_recorded`, from the "Prior Declaration" recital;
- `citations`, `map_reference`, `rental_cap_percent`;
- the 4250(a) flags;
- `repealed_sections`, `toc_last_page`, `last_page_seen`, `execution`.

**Checks:**

- The specification pins the prior declaration this one rescinds (CHECK).
- The specification's number differs from the stamp (CHECK).
- The rental cap is under 25 percent (CHECK, 4741(b), (f)). A later amendment may restate it.
- A 4250(a) element is not found (CHECK).
- The text cites a former section (INFO, 4235(a)).
- The extract stops before its contents' last page (CHECK).

This association's findings are in its private notes (mystique/notes/document-models/governing.md).

## Amendments

**Law.** An amendment is effective once three things have happened (CIV 4270(a)):

- the members approve it by the declaration's percentage (a)(1);
- an officer certifies that approval in an acknowledged writing (a)(2);
- it is recorded (a)(3).

The board alone may amend in these cases, each with its own procedure:

- to delete a discriminatory covenant (4225(b));
- to delete developer provisions: 30 days' notice and a majority of a quorum (4230(c), (d));
- to correct cross-references, recorded with the resolution (4235);
- to fix a rental restriction (4741(f)): by July 1, 2022, with 28 days' general notice of the text, purpose, and effect, decided at a board meeting.

An extension of the term may not exceed the initial term or 20 years (4265(c)).

**Layouts.**

- A declarant's amendment with an electronic stamp (`Doc# … Fees $101.00`).
- An association's board amendment on counsel's form, with a blank recorder's box and `DATED: ____, 2023`.

**`AmendmentRecord`** has these fields:

- `title`, `ordinal`, `recording`, `number`, `recorded`, `maker`;
- `approval` (`Approval`: members, declarant, board-rental, board-covenant, board-developer, board-cross-reference, court) and `authorities` (the statutes and declaration sections cited);
- `declaration_number`, `prior_amendments`, `annexations_cited`;
- `sections` and `subsections` (`4.15`, `4.15(a)`);
- `effective_on_recording`, `certified`, `extends_term`, `witness_ordinal`, `draft_year`, `citations`, `execution`.

**Checks:**

- No county stamp (CHECK, 4270(a)(3)).
- The date or signature lines are blank (CHECK).
- The title's ordinal differs from the one the signature clause adopts (PROBLEM).
- The approval is not stated (CHECK).
- A members' amendment has no officer's certificate (CHECK, 4270(a)(2)).
- A board rental amendment is dated after July 1, 2022 (CHECK), and its 28-day notice is not shown (CHECK, 4741(f)).
- The amendment deletes developer provisions (CHECK, 4230) or corrects cross-references (INFO, 4235(b)).
- The amendment extends the term (INFO, 4265).
- It amends a declaration other than the one the specification pins (CHECK).
- The specification does not list it (INFO).

This association's findings are in its private notes (mystique/notes/document-models/governing.md).

## Declarations of annexation

**Layouts.**

- John Laing's 2007 instrument with the old `BOOK 20071217 PAGE 1310` stamp.
- Watt's 2019-2021 instruments with electronic stamps, some copies OCR'd from a scan with border marks.

**`AnnexationRecord`** has these fields:

- `title`, `amended_restated`, `phase`, `recording`, `number`, `recorded`, `declarant`;
- `first_unit`, `last_unit`, `association_common_areas`, `condominium_common_areas`, `units`;
- `declaration_number`, `plan_number`, `map_reference`, `rescinds`, `citations`, `execution`.

**Checks:**

- The file name and the stamp give different numbers (CHECK).
- The name omits, or wrongly claims, "amended" (CHECK).
- The recorded date or unit count differs from the phase's row in `mystique/reports.py` (CHECK).
- The instrument rescinds one that `mystique/annexations.py` does not pin (CHECK).
- The specification records it as rescinded (INFO).
- It annexes under a declaration other than the one pinned (CHECK).
- No notary's acknowledgment appears in the text (CHECK).

This association's findings are in its private notes (mystique/notes/document-models/governing.md).

## Common areas and cost centers

A condominium project's documents can divide the common area in two: an **association common area** (A.C.A.) the association owns in fee, and a **condominium common area** (C.C.A.) the owners hold in undivided shares. The condominium plan's legend defines both, the declaration defines what each includes, and each annexation annexes an A.C.A. with its C.C.A. and units. The specification holds the association's common areas (`mystique/parcels.py`, `ASSOCIATION_COMMON_AREAS`: number, parcel, building, phase, units, builder, cost center).

An annexation can also split the regular assessment into a general component and **cost centers**, each "allocated and assessed equally among the Units within" it and carrying the upkeep of its own buildings. The specification holds those rules (`COST_CENTERS`). This association's reference is in its private notes (mystique/notes/document-models/governing.md).

**What the models read:**

| Model | Fields |
|---|---|
| Annexation | `association_common_areas`, `condominium_common_areas`, `undivided_interest`, `assessments_commence`, `cost_centers`, `cost_center_clause`, `assessment_components`, `phases_1_2_acas`, `annexed_center_expenses`, `phases_1_2_center_text`, `allocated_equally`, `defect_period_expired` |
| Declaration | `aca_owned_in_fee`, `aca_includes_structure`, `lot_a_is_aca`, `cca_elevations`, `cca_share_text` (kept as printed, because OCR garbles its fractions) |
| Condominium plan | `legend_defines_common_areas`, `aca_plan_sheet`, `condominium_common_areas` |

**Checks against the specification:**
- an ACA's phase, units, or cost center differing;
- the Phases 1 and 2 ACAs the clause names;
- the CCA share against the phase's units;
- `cost-center-clause-missing`, when the extract lacks 1.3(d);
- `phases-1-2-clause-skipped`, when 1.3(a)(ii) cites 1.3(d)(ii) but the text goes from (i) straight to (iii);
- `phases-1-2-clause-missing`, when 1.3(d)(ii) is absent for another reason, such as missing pages.

The clause heading is matched without requiring every word, since a recorded text can drop one.

`jason cost-centers` (MCP `cost_centers`) sets the rule beside the records: the monthly assessments charged in each cost center, the budgets' lines, the reserve studies' funding plans, and the cost center budgets the DRE public reports gave buyers (the public report model extracts `cost_center_assessment_cents`, `cost_center_reserve_cents`, `built_out_reserve_cents`, and `adopted_assessment_cents`). Restoring cost centers is for the board, with counsel.

This association's findings are in its private notes (mystique/notes/document-models/governing.md).

## Bylaws and articles

**Law.** The articles identify the association as formed to manage a common interest development under the Davis-Stirling Act. They state its office, or the development's front and cross streets, and its managing agent (CIV 4280(a)(1)-(3)). The statement of information carries the same identification (4280(b)). A seat is elected at the end of its term and at least every four years (5100(a)(2)), by secret ballot (5100(a)(1)).

**`ArticlesRecord`** has these fields: `name`, `corporation_type`, `filed` (the Secretary of State's endorsement), `signed`, `entity_number`, `agent_for_service`, the three 4280 flags, `front_street`, `cross_street`, `declaration_referenced`, `amendment_vote`.

**`BylawsRecord`** has these fields:

- `title`, `version` (the drafter's footer), `adopted`, `certificate_of_adoption`;
- the board: `directors_initial`, `directors_min`, `directors_max`, `term_years`, `staggered_terms`, `term_limit`, `board_quorum`;
- the members: `member_quorum`, `cumulative_voting`, `annual_meeting`;
- elections: `secret_ballot`, `inspectors_of_election`, `nominations`, `proxies`;
- `repealed_sections`, page coverage, and `sections`.

**Checks:**

- A 4280 statement is missing (CHECK). Before 2014, a filing under former 1363.5 is deemed to comply (4280(c)).
- The name differs from the specification's corporate name (CHECK).
- A term runs longer than four years (PROBLEM, 5100(a)(2)).
- No adoption certificate in the text (CHECK).
- No secret-ballot provision (INFO).
- Repealed sections are cited (INFO).
- The extract is partial (CHECK).

An extract can stop short of the PDF it came from, so `jason library` takes a PDF's own text layer when it is longer than the extract.

This association's findings are in its private notes (mystique/notes/document-models/governing.md).

## Operating rules, policies, and election rules

**Law.**

- **What a rule is.** An operating rule is a board regulation of general application (4340(a)). It is valid only if it is written, within the board's authority, consistent with the governing documents, adopted in good faith, and reasonable (4350).
- **How a rule is changed.** These subjects bring in the rule-change procedure (4355(a)):
  - use of the common area or of a separate interest;
  - discipline and fines;
  - payment plans;
  - dispute resolution;
  - architectural review;
  - elections.

  For those, the board gives 28 days' general notice of the text and purpose, decides at a board meeting, and gives general notice within 15 days after (4360(a)-(c)).
- **Fines.** A penalty schedule goes out with the annual policy statement (5850(a), 5310(a)(8)). A penalty may not exceed $100 per violation unless it is a health or safety violation found so at an open meeting (5850(c), (d)).
- **Collection policy.** The collection policy belongs in the annual policy statement (5310(a)(6), (7); 5730). Interest on a delinquent assessment may start only 30 days after it is due (5650(b)). A copy of a record costs the actual cost of copying (5205(f)). A resale document's fee is limited to the cost of preparing it (4530(b)).
- **Hearings (5855, as amended 2025).**
  - The member gets notice 10 days before the hearing, and a right to cure the violation before it.
  - The member may ask for internal dispute resolution after the hearing.
  - The board decides in executive session on request, and gives written notice of the decision within 14 days.
- **Voting.** A member may not be denied a ballot, including for nonpayment (5105(h)(1)).
- **Election rules.** They must do what 5105(a)(1)-(7) and (h) list. The disqualifications follow 5105(c)-(f).

**Layouts.**

- **The Owner's Manual & Rules.** It compiles the Q&A, rules `B-1` to `B-18` under "EFFECTIVE: SEPTEMBER 15, 2022", the fine schedule, the collection policy, and the 5730 notice.
- **Policies.** Each is a one- to five-page statement with a title line (collection, enforcement, ethics). The enforcement policy's fine schedule puts label and amount on separate lines.
- **Election rules.** Counsel's form, with a secretary's certificate.

**Records.**

- **`OperatingRulesRecord`**: `title`, `adoption` (`Adoption`: adopted, effective, effective text, blank adoption line, blank signature), `effective`, `authority` (the declaration section), `rules` (`RuleSection` code and title), `subjects` (`RuleSubject`, the 4355(a) subjects), `fines` (`FineRow`: label, value, amount, maximum, per day, penalty or fee), `notice_described`, `reversal_described`, `includes`, `included_effective` (an effective date the compilation prints for an included policy), `hearing` (the hearing procedure: notice days, decision days, cure, IDR after, executive session on request), `repealed_sections`.
- **`PolicyRecord`**: `title`, `subject` (`PolicySubject`), `adoption`, `adopted`, `effective`, `supersedes_prior`, `subjects`, `fines`, `declaration_sections`, `repealed_sections`, `hearing`, and `collection` (interest start, late charge, copy and resale fees, IDR fee).
- **`BylawsRecord`** (above) also carries `rule_notice_days`, `rule_reversal_vote`, `suspends_voting_for_default`, `hearing`, and `certificate_page`.
- **`ElectionRulesRecord`**: `title`, `adoption`, `adopted`, `certificate`, `certificate_year`, `elements`, and `missing_elements` (`ElectionElement`, one per 5105 subdivision). It also records:
  - voting methods: `electronic_voting`, `acclamation`, `cumulative_voting`;
  - nominations: `write_ins_allowed`, `floor_nominations_allowed`;
  - candidate rules: `disqualifies_delinquent`, `directors_must_be_current`, `excludes_fines`, `idr_before_disqualifying`, `one_year_membership`;
  - `retention`.

**The 5105 elements.**

| Element | Subdivision |
|---|---|
| Media access | (a)(1) |
| Meeting space | (a)(2) |
| Qualifications, nominations | (a)(3) |
| Voting power, proxies, voting period (a stated deadline counts) | (a)(4) |
| Inspector selection | (a)(5) |
| Inspector's helpers | (a)(6) |
| Candidate and voter lists | (a)(7) |
| No member denied a ballot | (h)(1) |
| Power of attorney | (h)(2), (3) |
| Ballot and rules delivered 30 days ahead | (h)(4) |
| No amendment within 90 days | (h)(4)(B)(iii) |

**Checks:**

- **The rule-change procedure.** For a rule on a 4355(a) subject (CHECK).
- **Fines.**
  - The penalty schedule goes in the annual policy statement (INFO).
  - A penalty over $100 (CHECK, 5850(c)); for a safety violation, INFO under 5850(d).
- **Adoption.**
  - No adoption date (CHECK, 4360(b)). The message says "no adoption date is printed in the text", gives the reason, and adds a lead from the library: an effective date the compilation prints (`effective-date-in-compilation`), or minutes that record the adoption.
  - A blank adoption line (CHECK).
  - "Effective on the date of adoption" with no date (CHECK).
  - A rule-change notice shorter than 28 days in the bylaws (`rule-notice-short`, CHECK, 4360(a)).
- **Policy statement.** The collection or discipline policy belongs in the annual policy statement (INFO). `in-annual-policy-statement` (INFO) names the annual disclosure on file that carries it.
- **Hearings (5855).**
  - `decision-notice-days`: a written decision allowed more than 14 days (PROBLEM).
  - `no-cure-before-hearing` and `no-idr-after-hearing` (CHECK).
  - `no-executive-session-on-request` (CHECK).
- **Collection terms.**
  - `interest-starts-early`: interest before 30 days (PROBLEM, 5650(b)).
  - `records-copy-fee`: a flat fee per document rather than the actual cost (CHECK, 5205(f)).
  - `resale-document-fee` (CHECK, 4530(b)).
- **Voting.** `vote-suspension-for-default`: bylaws that let the board suspend voting for nonpayment (CHECK, 5105(h)(1)).
- **Scope.** The ethics policy's disciplinary action is against directors, so no 4355(a) subject applies and it draws no rule-change finding.
- **Election rules.**
  - An element not found (CHECK, citing its subdivision).
  - A blank certificate (CHECK).
  - The rules disqualify a delinquent nominee but do not hold directors to the same rule (PROBLEM, 5105(c)(1), (f)).
  - Fines are not excluded (CHECK, 5105(d)).
  - No IDR before disqualifying (CHECK, 5105(e)).
  - Floor nominations are allowed with electronic ballots (PROBLEM, 5105(i)(1)(F)).
  - The 30-day delivery of the ballot and rules (INFO).

This association's findings are in its private notes (mystique/notes/document-models/governing.md).

## Grant deeds

**Layouts:**

- Title companies' grant deed forms (Placer, First American, Fidelity, Stewart, Chicago, Old Republic): electronic `Doc#` stamps, the `APN/Parcel ID(s)` line, "The documentary transfer tax is $… and City Tax is $…".
- John Laing's 2007-2008 developer deeds, with `A.P.N.` parent parcels.
- Old `BOOK/PAGE` stamps.
- The common-area deeds of each phase, exempt.
- A trustee's deed upon sale.
- Title companies' unrecorded copies sent to the association with their sale notice.
- Title companies' certified copies: no county stamp, but a certification of the recorded original, often handwritten ("CERTIFIED TO BE A TRUE COPY / RECORDED 6/19/2019 / BOOK 2019 0619 PAGE 681", "recorded on 11/7/08 ... Instrument No.: 2008-1337", "Series # 20100910/1231").
- A receiver's deed that defines its parties (`... ("Grantor"), does hereby grant to ... ("Grantee")`), and its re-recording.

**Where the number comes from.** `number_source` says which of these gave `number`, in this order:

1. `stamp` or `spaced`: the county's `Doc#` or `BOOK/PAGE` stamp (`stamp and name` when an old stamp was completed from the file name, as before).
2. `certification`: the title company's certification, whole. Its recording date supplies the book when it prints only the year and page.
3. `certification and name`: the certification's date (or its year and page) agrees with the file name's number, and its legible digits fit the name's page in order. A vision reading misreads handwriting (`2013-0920-8576` for page 856), so the name completes it.
4. `name`: the text has neither; the file name's number (`GD 201905071257.pdf`) and the date it carries. This is a CHECK (`number-from-name`).

When the certification disagrees with the name (a different day, or a page whose digits do not fit), the name's number stands, the certification's reading is kept in `certification_differs`, and the finding `certification-differs` asks a person to look; the county index settles which is right. A certified copy often carries no county stamp at all.

**The vision layer.** `jason.tasks.library.text_for` puts a vision model's reading of the first pages ahead of the older text, which repeats those pages. `layers` splits the two where the older text repeats one of the reading's opening lines (or its `# name` header). The stamp, the parcel numbers, the unit, and the transfer taxes come from the reading when it has them. This matters because `deed_price` takes the last city tax it sees, and because an OCR slip in the older layer (`2014170-004-0000`) would otherwise count as a second parcel. The granting clause and the date are taken first-found, which is the reading.

**`GrantDeedRecord`** has these fields:

- `deed_type`, `recording`, `number`, `number_source`, `certification_differs`, `recorded`, `requested_by`;
- `apns`, `apn`, `unit`, `building`, `grantor`, `grantee`;
- `county_tax_cents`, `city_tax_cents`, `exempt`, `exemption`, `consideration_cents`, `dated`;
- `declaration_cited`, `plan_cited`, `parent_parcel`, `common_area`, `sale_notice`;
- `corrects` and `corrects_recorded` for a re-recorded deed;
- for a trustee's deed, `unpaid_debt_cents` and `amount_paid_cents`.

Other readings:

- **Consideration.** When the county tax is a $0.55 step and the city tax, to the cent, computes a price that the county step rounds up to, that price is the consideration. For example, $694.41 is $252,513, and 506 steps is $278.30. `deed_price` compares the two only at the county's whole step.
- **Exempt deeds.** "R&T 11911" handwritten in an exempt deed's tax blank reads as `$ 119.11`; it is taken as exempt, not as a tax.
- **Parcel numbers.** A developer's multi-unit deed lists ranges (`201-1170-022-0001 through 201-1170-022-0008`). These are expanded within one assessor's parcel, and an `APN:` list past the head is read. OCR's `I` for 1 and `·` for a hyphen are repaired inside the numbers only.
- **The deed's date.** It is `Dated: 10/25/07`, `Dated: January 21st 2008`, or First American's continuation header `continued Date: 01/05/2012`. A trust's "Dated 17 January 2006" in the vesting is not the deed's date.
- **Citations.** The words nearest before a cited number decide whether it is the plan or the declaration. When the plan's own number did not read, the CC&Rs' `Book 20070920, Page 938` that follows `("Plan"), and in the Restated Declaration` is no longer taken as the plan. A garbled plan number is taken only when, after mapping OCR's letter-for-digit slips, it begins with the recording date printed before it. The declaration fallback reads "covenants ... recorded ... as instrument number 20070920, page 938" from the text, not from the specification.

**Checks:**

- The copy has no county stamp, or shows only the blank recorder's box (CHECK), when neither a certification nor the file name gives the number.
- The number is the file name's alone (`number-from-name`, CHECK), or the certification disagrees with the name (`certification-differs`, CHECK).
- The file name and the stamp give different numbers (CHECK).
- The deed is recorded before its own date (`recorded-before-dated`, CHECK): one is misread, or the deed misprints its year.
- A re-recorded deed (`re-recorded`, INFO).
- **Parcel numbers:**
  - A parent parcel (INFO).
  - A parcel number on the association's map page that the current roll no longer carries (INFO).
  - A parcel number off the map page (CHECK).
  - A unit and parcel number that fit none of the specification's numberings (CHECK). A unit number alone never places a deed.
- **Transfer tax:**
  - A county tax that is not a multiple of $0.55 per $500 (CHECK).
  - County and city taxes that compute different considerations (CHECK).
- The title company's sale notice is attached (INFO).

This association's findings are in its private notes (mystique/notes/document-models/governing.md).

## Public reports, condominium plans, maps, plan sets

**`PublicReportRecord`** has these fields:

- `file_number` and `base_file_number`, joined to the specification by the latter;
- `report_type` (preliminary, conditional, final, amended), `subdivider`, `subdivision`;
- `issued`, `amended`, `expires`;
- `phase`, `total_phases`, `total_units`;
- `first_unit`, `last_unit`, `units`, `building`, `common_area`;
- `built_out_assessment_cents` and `phase_assessment_cents`;
- the reserve contributions of each: `built_out_reserve_cents` and `phase_reserve_cents`, from "Of these amounts, the monthly contributions toward long-term reserves ... are $15.25 and $18.20, respectively";
- the cost center's: `cost_center_assessment_cents`, `cost_center_phase_assessment_cents`, `cost_center_reserve_cents`, and `cost_center_phase_reserve_cents`. The sentence after "Cost Center built-out budget" is the cost center's.

The last phase (8) states only the built-out budget, so its phase fields stay empty.

The Bureau prints the header two ways: on single lines, or in two columns whose dates fall on separate lines. The preliminary report uses the RE 603C box form.

Its checks compare the report with its `mystique/reports.py` row: the phase, the unit count, the building, and the issue date. An expired report is INFO: it is a historical record of what buyers were told.

**`CondominiumPlanRecord`** has these fields: `title`, `recording`, `number`, `recorded`, `buildings`, `unit_ranges`, `units`, `association_common_areas`, `sheets`, `divides_plan` (the earlier plan whose units it further divides), `map_reference`, `surveyor_statement`, `no_deeds_of_trust`.

**`MapRecord`** has these fields: `title`, `map_kind` (final map, parcel map, assessor's parcel map, improvement plans, fire insurance map report), `subdivision_number`, `map_reference`, `dated`, `sheets`, `apns`, `instruments`, `surveyor_statement`, `owner_consent`, `dedications`. A pre-filing print with a blank book and page is INFO; later instruments give the map's recorded citation.

**`PlanSetRecord`** has these fields: `title`, `plan_kind` (record of decision, staff report, application, drawings), `file_number`, `related_files`, `project_address`, `apns`, `dated`, `units`, `buildings`, `acres`, `decision`.

This association's findings are in its private notes (mystique/notes/document-models/governing.md).

## What the texts cannot show

- A signature or a notary's seal that is only an image.
- A notice given, a vote taken, or a meeting held. The 4360, 4741(f), and 4270(a)(2) findings stay CHECK.
- Whether a rule or policy was adopted, when its text carries no signed adoption.
- Pages past what an extract reaches, such as a certificate or an amendment article late in a long document.
- The recorded copy of an amendment the library holds only as a draft.
- The county stamp on a title company's copy: a number may come from the file name alone (`number-from-name`), and a handwritten certification may disagree with it.
