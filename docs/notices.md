# Notices: what the law requires, how it is delivered, and how jason proves it

This page is the reference for every notice a California common interest development gives its members, read from the statutes on disk (`data/authorities`, `jason export-authorities`) and the governing documents' own notice clauses. It covers the vocabulary of the instruments that change a governing document, the two kinds of notice and how each is delivered, the catalog of notices with their recipients, methods, clocks, and content, what to do when an owner cannot be reached, and the evidence that proves a notice was given. It is not legal advice. Where the text is unclear, the row says so and counsel reads it first.

The records are code, so jason can act on them:

| Record | Where | What it holds |
| --- | --- | --- |
| `NoticeRequirement` | `src/jason/community/notices.py`; the rows in `src/jason/community/notice_catalog.py` | what the statute requires of one kind of notice, with a stable key |
| `Timing` | `notices.py` | one clock: at least / at most N days (or business days, or hours) before or after an anchoring event |
| `Evidence` | `notices.py` | what proves a notice was given |
| `NoticeProvision` | the profile's `notices.py` (`Community.notice_provisions()`) | a governing document's clause about a notice, compared with the statute |
| `NoticeRule` | the profile's `notices.py` (`Community.notice_rules()`) | who receives a notice the association sends, by PayHOA tags; `requirements` links it to the catalog |
| `InstrumentType` | `src/jason/community/instruments.py` | the kinds of instrument that change a governing document |
| `ProofOfNotice` | `src/jason/tasks/notice_proof.py` | one notice's evidence, window, and late or unreached members |
| `NoticeStrength` | `notices.py` | how strongly the record shows a notice given: delivered, sent with follow-ups owed, sent, or a file |
| `NoticeRecord` | `src/jason/tasks/notice_evidence.py` | one record that a notice went out (or was written), with its strength; counts only |

Commands: `jason notice-check` checks a notice or jason's base templates for each required element (below); `jason notices --catalog` lists the requirements; `jason notices --catalog --fact election=directors` sorts the rows required only for some events by the facts of one event ([below](#when-a-row-is-required)); `jason notices KEY --catalog` prints one with the documents' clauses and the stricter clock; `jason notices KEY --proof --event DATE` prints a notice's proof (below); `jason cite jason://notice/KEY` prints the notice as a record (below). The tests (`tests/test_notice_catalog.py`) check every verified row's words against the statute on disk and every pinned period against `statutory_terms`, so a change in the law fails the build instead of leaving a row stale.

## Instruments that change a governing document

The words get used loosely; each does something different to the text and takes effect differently. `jason.community.instruments.INSTRUMENTS` has a row for each.

| Kind | What it does to the text | Who adopts it | When it takes effect | Notice it needs |
| --- | --- | --- | --- | --- |
| Amendment (declaration) | sets, adds, or removes named sections | the members, by the declaration's percentage, or a majority of all members if it names none (4270(b)) | after approval, certification by the designated officer (else the president), and recording in each county (4270(a)) | the ballot carries the amendment's text (5115(g)); a court-ordered amendment is sent to members once recorded (4275(g)) |
| Amended and restated declaration | replaces the whole text; the prior declaration and its amendments are superseded | the members, as an amendment | as an amendment: on recording | as an amendment |
| Restatement only | consolidates approved amendments, no new substance | the board, only where the declaration gives it that power | as the declaration says (commonly execution by officers and recording) | none in the Act |
| Revocation | ends an instrument from a date forward | as the declaration provides ("amended or revoked") | as an amendment | as an amendment |
| Rescission | undoes an instrument as though not made, typically before it took hold (a declarant's annexation rescinded before any unit of the phase sold) | the declarant, or as the instrument says | on recording of the rescinding instrument; whether it reaches back is for counsel | none in the Act |
| Supersession | a later instrument replaces an earlier one, by its own words | whoever adopts the later instrument | when the later one takes effect | that of the later instrument |
| Repeal | removes a section or a whole rule | the adopter of that document | for a rule, on adoption after notice (4360) | a rule repeal is a rule change (4340(b)) |
| Annexation (declaration of annexation) | brings more property under the declaration; may add provisions for it | the declarant under the declaration's reserved rights, or the members for other property | on recording | none in the Act |
| Amended annexation | replaces an earlier annexation for the same phase | the declarant | on recording | none in the Act |
| Citation correction (4235) | corrects cross-references to the recodified Act | the board, by resolution; no member approval | on the resolution; a corrected declaration may be restated and recorded with it | none in the Act |
| Discriminatory covenant deletion (4225) | deletes the covenant and restates with no other change | the board must, without member approval | the restated declaration is recorded (4225(c)) | none in the Act; a request in writing starts a 30-day clock (4225(d)) |
| Rental restriction amendment (4741(f)) | deletes or restates an unlawful rental restriction, no other change | the board must, without member approval | on approval at a board meeting; whether a declaration's amendment also waits for recording is for counsel | general notice 28 days before, with text and purpose and effect (`rental-amendment-4741`) |
| Developer provisions deletion (4230) | deletes provisions only for the developer's construction and marketing | the board, with a majority of a quorum of the members | as an amendment | individual notice 30 days before, with the amendments and the meeting (`developer-amendment-4230`) |
| Rule change (4340-4370) | adopts, amends, or repeals an operating rule on a 4355(a) subject | the board | on the board's decision at a meeting after 28 days' notice; members may reverse it (4365) | `rule-change-proposed`, `rule-change-adopted`, `rule-change-reversal-results` |
| Emergency rule (4360(d)) | as a rule change | the board | at once, for at most 120 days; not readopted as an emergency rule | the adopted-change notice, with its expiry |
| Bylaw amendment | sets sections | as the bylaws provide (usually the members) | on approval; bylaws are not recorded | the ballot carries the text |

How jason represents each, and what the living-document model (`jason.community.living`, [living-documents.md](living-documents.md)) does not yet hold:

- **Section changes** (amendment, rule change, bylaw amendment, the board-required amendments) are `Instrument` operations with a `Verb` (`RESTATE`, `ADD`, `REMOVE`) and a `Standing` (`DRAFT`, `ADOPTED`, `RECORDED`). That covers the text. The standing does not say who certified the amendment or which ballot approved it, and the notices that went with it are not linked to the instrument.
- **Whole replacements** (amended and restated declaration, restatement, amended annexation, supersession) are pinned today as `governing.Supersession` rows on recorded instruments. Living reads the operations of one base document; it has no instrument that *replaces the base*, and no map from the old section numbers to the new, so provenance and annotations would not carry across a renumbering. The living model does not read the `Supersession` rows.
- **Revocation, rescission, expiry, reversal** need standings the model lacks: `REVOKED` (applied until a date), `RESCINDED` (never applies, for any `as_of`), `EXPIRED` (an emergency rule after 120 days), `REVERSED` (a rule change the members reversed, not readopted for a year, 4365(f)), and `SUPERSEDED` (with what replaced it).
- **When it takes effect** is chosen today by document kind (`effect_of`): a declaration changes on recording, anything else on adoption. Some instruments differ from their document: a 4235 citation correction to the declaration takes effect on the board's resolution; a 4741(f) amendment is approved at a board meeting. The effect belongs on the instrument kind.
- **Annexation scope**: an annexation's added provisions apply to its phase's units only; living has no per-provision scope.

## Two kinds of notice

### Individual delivery (Civil Code 4040, 4041, 4050)

When the Act requires "individual delivery" or "individual notice", the association delivers by **the member's preferred delivery method** given under 4041: a mailing address, a valid email address, or both. Without a valid method on file, it goes by first-class mail, registered or certified mail, express mail, or overnight delivery, addressed to the address last shown on the association's books (4040(a)).

- **The annual solicitation** (4041(b)): each year the association asks every owner for the preferred method, an alternate or secondary method, a legal representative, and whether the unit is owner-occupied, rented, or vacant; tells them they need not give an email; and gives a simple written way to change the preference. The answers are entered at least 30 days before the annual budget report and policy statement go out. An owner who does not answer is reached at the last mailing address they gave in writing, else the unit's address (4041(c)).
- **A valid email** is one that does not bounce or return an error after a notice is sent. When an email turns out not to be valid, the association resends the notice to a mailing or email address the member identified (4041(e)).
- **Secondary addresses** (4040(b), requested in writing under 5260): an additional copy goes to the secondary address of the documents of Article 7 of Chapter 6 (the annual budget report, the policy statement, the reviewed financial statement, and what they carry) and of Article 2 of Chapter 8 (the collection notices of 5650-5690) and 5710 (the notice of default). The catalog marks these rows `secondary_copies`.
- **The legal representative** (4041(a)(3)) is a contact for a member's extended absence, not a recipient of notices; jason keeps them apart (`tasks.notice_delivery`). A notice of default and a foreclosure decision may be served on a legal representative the owner designated (5705(d), 5710(b)).
- **The governing documents' own method**: an unrecorded provision providing a method of delivery is not the member's agreement to it (4040(c)). A bylaw or rule that says "notices go by email to members who vote electronically" does not replace the member's 4041 choice.
- **When delivery is complete**: on deposit into the United States mail; for electronic delivery, at transmission (4050). A returned letter was still delivered on deposit; its address is not good, which is a follow-up, not a failed notice.
- **Writing by email**: a requirement that information be in writing is met by an electronic record the recipient can keep; one that blocks printing or storing is not (4055).
- **Safe at Home**: a participant's substitute address is used for all association communications, and the participation is kept confidential (5216).

### General delivery (Civil Code 4045)

When the Act requires "general delivery" or "general notice", any one of these methods will do (4045(a)):

1. any method of individual delivery;
2. inclusion in a billing statement, newsletter, or other document delivered by one of these methods;
3. posting the printed document in a prominent location accessible to all members, **if the annual policy statement designates it** for general notices;
4. inclusion in the association's television programming, if it broadcasts any;
5. posting on the association's website in a prominent location accessible to all members, **if the annual policy statement designates it**.

A member who asks in writing (5260(c)) receives general notices by individual delivery (4045(b)); the policy statement describes that option. Some sections add their own "individual notice on request" (5115(a), (b)(5)); the catalog marks them `individual_on_request`.

A posting at a location the policy statement does not name is not general delivery. When there is no designated posting, a general notice is delivered only by its individual deliveries, and every member must be reached.

### The annual policy statement's designations (5310)

The policy statement carries what makes notices work: who receives documents for the association (4035), that a member may have notices sent to up to two addresses (4040), the posting location and website for general notices (4045(a)), the option to receive general notices individually (4045(b)), how to get minutes (4950(b)), the assessment and foreclosure notice (5730), lien enforcement practices, the discipline policy and penalty schedule (5850), the dispute resolution summaries (5920, 5965), the architectural approval requirements (4765), the overnight payment address (5655), and the electronic voting procedures if used (5105(i)(1)(D)). A notice that relies on posting relies on this year's statement saying where.

### Other methods the Act names

- **Certified mail**: the pre-lien notice (5660) and the copy of the recorded lien (5675(e)); registered or certified mail for the trustee's notices (2924b).
- **Personal delivery**: a hearing notice and decision (5855, or individual delivery), the termite relocation notice (4785(c)), a Request for Resolution (5935(b), among others).
- **Personal service in the manner of a summons**: the foreclosure decision to an owner who occupies the unit, and the notice of default (5705(d), 5710(b)).
- **Posting at the site**: the 48-hour pesticide notice in the common area (4777(b)(3)).
- **Within another notice**: a reserve transfer's consideration goes in the board meeting notice (5515); the 5730 notice, the penalty schedule, and the dispute resolution summaries go in the policy statement; an emergency assessment's resolution goes with the notice of assessment (5610(c)). The catalog marks these `carried_by`.

### Counting the days

- "At least N days before" an event: jason's last day is the event's date minus N (the event day not counted). "Not less than N nor more than M days before": the window runs from M days before to N days before. "Within N days after": the last day is the anchor plus N.
- Business days skip weekends. jason knows no holiday calendar, so a business-day deadline it computes is the earliest it can fall.
- Hours round up to whole days (48 hours before an application on the 10th: by the 8th).
- Mail counts on deposit and email on transmission (4050), so the day a letter is deposited is the day it went out.
- A deadline falling on a weekend or holiday, and whether "at least four days" excludes both the day of notice and the day of the meeting, are questions for counsel: the Act on disk does not define how days are counted, and the general rules on that (Code of Civil Procedure 12 and Civil Code 10) are not exported here. Until counsel reads them, send a day early.
- A clock may run from something other than receipt: resale documents are due within 10 days of the *mailing or delivery* of the request (4530), and a payment-plan meeting within 45 days of the *postmark* of the request (5665). The anchor `REQUEST_MAILED` holds those.

## The catalog

Each row is a `NoticeRequirement` in `notice_catalog.REQUIREMENTS`, keyed for linking. Recipients, method (`general` = 4045, `individual` = 4040), and the clock; the content lists, notes, and evidence are in the rows (`jason notices KEY --catalog`). Seventy-three rows; seventy-one are verified against the statute's words on disk. The two that are not say why.

### When a row is required

Fifteen rows are required only for some events. Each carries the condition as data (`NoticeRequirement.applies`, an [applicability](applicability.md) condition), written from the section's own words. The conditions are in `jason.community.notice_conditions`, each beside the words it is written from, and a test checks those words against the statute on disk.

| Rows | Required when | The words |
| --- | --- | --- |
| `board-meeting` | the board meeting is neither an emergency meeting nor held solely in executive session | 4920(a): "Except as provided in subdivision (b)" |
| `board-meeting-executive` | a nonemergency meeting held solely in executive session | 4920(b)(2) |
| `board-meeting-emergency` | an emergency meeting (the row says no notice is required) | 4920(b)(1) |
| `teleconference-meeting` | the meeting is held entirely by teleconference | 4926(a), (a)(1) |
| `nomination-procedure`, `pre-ballot-notice` | an election of directors or a recall election | 5115(a): "shall only apply to elections of directors and to recall elections"; 5115(b) |
| `acclamation-initial`, `acclamation-reminder`, `nomination-acknowledgment` | an election of directors, and the association keeps seating by acclamation available | 5103: "may, but is not required to ... if all of the following conditions have been met" |
| `electronic-ballot-notice` | an election rule allows electronic secret ballots, except in an assessment election | 5105(i), (i)(3)(A) |
| `electronic-opt-out-notice` | the election rule lets members opt out of electronic voting | 5105(i)(4) |
| `reconvened-election-meeting` | an election of directors | 5115(d)(2), (3) |
| `rule-change-proposed`, `rule-change-reversal-results` | the rule is on a subject 4355(a) lists, except an emergency rule change | 4355(a), (b); 4360(a), (d); 4365(h) |
| `rule-change-adopted` | the rule is on a subject 4355(a) lists | 4355(a), (b) |

- **Three answers.** `notice_catalog.applicable(facts)` sorts the rows:
  - **applies:** the notice is required when its event happens, on its clock;
  - **does not apply:** not required, with the fact that decided it;
  - **undetermined:** the facts do not say, with the missing fact. It is never read as "not required".
- **A row with no condition** is required whenever its event happens.
- **With no facts, nothing changes.** `jason notices --catalog` and `jason notices KEY --catalog` print as they always have. The prose `note` of each converted row stays.
- **Two kinds of fact** (`Fact.standing`):
  - **One event's facts** are said by the caller that knows the event: `--fact election=directors`.
  - **The association's standing facts** come from the profile (`Community.applicability_facts()`). Where the profile does not state one, it is a question for a person: `jason applies --questions` lists it under `applies:association`, `jason applies --file-questions` parks it in the intake queue, and the answer is read as a fact with source `answer` ([intake.md](intake.md#what-asks)). Each answer names the record that settles it.

```
jason notices --catalog --fact election=directors                    # the notices for an election of directors
jason notices --catalog --fact rule_scope=listed_subject --fact rule_change=emergency
jason notices --catalog --fact board_meeting=executive_session_only
jason notices pre-ballot-notice --catalog --fact election=recall     # one row, and each conditional element
jason notices --catalog --required                                   # every conditional row, from the facts on hand alone
```

Rows about another kind of event (a rule change, when the facts said are an election's) are set aside and named, not answered.

**The facts.** Each is a closed set whose members are the statute's own distinctions.

| Fact | Members | From | Who says it |
|---|---|---|---|
| `election` | `directors`, `recall`, `assessment`, `amendment`, `exclusive_use`, `other` | Civil Code 5100(a)(1) and (b); 5115(a) | the caller |
| `rule_scope` | `listed_subject`, `not_reached` | Civil Code 4355(a) and (b) | the caller |
| `rule_change` | `noticed`, `emergency` | Civil Code 4360(a) and (d) | the caller |
| `board_meeting` | `ordinary`, `executive_session_only`, `emergency` | Civil Code 4920(a), (b)(2), (b)(1) | the caller |
| `meeting_format` | `in_person`, `teleconference_with_location`, `entirely_by_teleconference` | Civil Code 4090, 4926(a) | the caller |
| `electronic_voting` | `none`, `opt_out`, `opt_in` | Civil Code 5105(i)(1)(C) | the profile (the election operating rules) |
| `acclamation` | `available`, `not_used` | Civil Code 5103 | the profile (the board's standing choice) |
| `director_quorum` | `none`, `at_least_20_percent`, `below_20_percent` | Civil Code 5115(b)(6) | the profile (the bylaws) |

**Acclamation is the association's choice, not a fact about its documents.** Section 5103 applies "notwithstanding ... any contrary provision in the governing documents" and says the association "may, but is not required to" seat by acclamation. Whether it keeps that available is for the board to decide once and write down ("Where the law is silent, write it down"); jason asks, and does not choose.

**Rows that keep their condition as prose.** A condition is encoded only where the section's words settle it and a closed set can carry it. These stay in `note`:

| Row | The condition | Why it is not data |
| --- | --- | --- |
| `disaster-meeting-first` | gathering in person is unsafe or impossible in a declared emergency (5450(a)); the first meeting held under the section for that emergency (5450(b)(1)) | the words are definite; two more event facts, not yet added |
| `financial-review` | gross income over $75,000 in the fiscal year, "unless the governing documents impose more stringent standards" (5305) | needs the year's gross income as a fact and a "more than" test; the documents' own standard is read first |
| `payment-plan-meeting` | the request is mailed within 15 days of the pre-lien notice's postmark (5665(b)) | a date test between two postmarks, not a closed set |
| `emergency-assessment-resolution` | an expense under 5610(c) | which of 5610's three emergencies an expense is, is a finding the board makes |
| `pesticide-unit`, `pesticide-common-area` | the association applies a pesticide "without a licensed pest control operator" (4777(b)(1)) | the words are definite; one more fact, not yet added |
| `acclamation-reminder` (its last element) | the statement is not required if the candidates already outnumber the positions (5103(b)(2)(E)) | a count on the day the reminder goes out |
| `reconvened-election-meeting` (its last element) | the 20 percent statement "unless the association's governing documents provide for a lower quorum ... if the association's governing documents require a quorum" (5115(d)(3)(C)) | two readings: see the open questions |
| the acclamation rows | "a regular election for the directors in the last three years" (5103(a)) | a condition of acclamation beside the notices, not of the notices; the words do not say the notices fall away without it |

### Meetings

| Key | Statute | To | How | Clock |
| --- | --- | --- | --- | --- |
| `board-meeting` | CIV 4920 | every member | general | at least 4 days before the meeting; with the agenda |
| `board-meeting-executive` | CIV 4920 | every member | general | at least 2 days before a meeting held only in executive session |
| `board-meeting-emergency` | CIV 4920, 4923 | every member | none required | the minutes record the emergency |
| `board-meeting-directors` | CORP 7211 | the directors | first-class mail, personal delivery, or electronic | a special meeting: 4 days by mail or 48 hours otherwise; a regular meeting fixed by the bylaws or the board needs none |
| `teleconference-meeting` | CIV 4926 | every member | in the meeting notice | technical instructions, a help contact, the individual-delivery reminder |
| `disaster-meeting-first` | CIV 5450 | every member | individual | the first teleconference meeting during a declared emergency |
| `reserve-transfer-consideration` | CIV 5515 | every member | in the board meeting notice | reasons, repayment options, whether a special assessment may be considered |
| `litigation-reserve-use` | CIV 5520 | every member | general | when the board decides to use reserves for litigation |
| `minutes-available` | CIV 4950 | every member | made available | within 30 days after the meeting |
| `member-meeting` | CORP 7511 | every member | (unverified) | the bylaws' own period governs meanwhile |

A governing document that requires a longer board-meeting notice controls; for an emergency meeting or one held only in executive session, only if it says so (4920(b)(3)).

### Elections and member votes

| Key | Statute | To | How | Clock |
| --- | --- | --- | --- | --- |
| `nomination-procedure` | CIV 5115 | every member | general (individual on request) | at least 30 days before the nomination deadline |
| `acclamation-initial` | CIV 5103 | every member | individual | at least 90 days before the nomination deadline |
| `acclamation-reminder` | CIV 5103 | every member | individual | 7 to 30 days before the nomination deadline |
| `nomination-acknowledgment` | CIV 5103 | nominator and nominee | written or electronic | within 7 business days of receiving the nomination |
| `pre-ballot-notice` | CIV 5115 | every member | general (individual on request) | at least 30 days before ballots are distributed |
| `ballots` | CIV 5115, 5105 | every member | first-class mail or delivered | at least 30 days before the voting deadline |
| `electronic-ballot-notice` | CIV 5105 | every member | individual | 30 days before the election |
| `electronic-opt-out-notice` | CIV 5105 | every member | individual | at least 30 days before the opt-out deadline |
| `reconvened-election-meeting` | CIV 5115 | every member | general | at least 15 days before the reconvened meeting |
| `election-results` | CIV 5120 | every member | general | within 15 days of the election |
| `member-vote-result-request` | CORP 8325 | the member who asks | written | for 60 days after a members' meeting, forthwith |

The election sequence runs backward from the voting deadline: ballots at least 30 days before it; the pre-ballot notice (with the candidates' names) at least 30 days before the ballots; nominations close before that notice; the call for candidates at least 30 days before the nomination deadline; and, for acclamation, the initial notice 90 days before the nomination deadline. A bylaw that closes nominations 14 days before the ballots cannot be met with the 5115(b) notice and yields to it.

### Rules and the governing documents

| Key | Statute | To | How | Clock |
| --- | --- | --- | --- | --- |
| `rule-change-proposed` | CIV 4360 | every member | general | at least 28 days before the decision; the text and its purpose and effect |
| `rule-change-adopted` | CIV 4360 | every member | general | within 15 days after the decision (an emergency rule: its text, purpose, and expiry) |
| `rule-change-reversal-results` | CIV 4365 | every member | general | within 15 days after voting closes |
| `rental-amendment-4741` | CIV 4741 | every member | general | at least 28 days before the board approves |
| `developer-amendment-4230` | CIV 4230 | every member | individual | at least 30 days before the meeting |
| `amendment-petition-hearing` | CIV 4275 | members, mortgagees, the city or county | written, as the court orders | at least 15 days before the hearing |
| `amendment-recorded-4275` | CIV 4275 | every member | individual | within a reasonable time after recording |

### Annual disclosures

| Key | Statute | To | How | Clock |
| --- | --- | --- | --- | --- |
| `owner-info-solicitation` | CIV 4041 | every member | written | answers entered at least 30 days before the annual reports |
| `annual-budget-report` | CIV 5300, 5320 | every member (+ secondary) | individual: full, or a summary | 30 to 90 days before the fiscal year ends |
| `annual-policy-statement` | CIV 5310, 5320 | every member (+ secondary) | individual: full, or a summary | 30 to 90 days before the fiscal year ends |
| `collection-policy-notice` | CIV 5730 | every member | in the policy statement, 12-point | with the policy statement |
| `penalty-schedule` | CIV 5850 | every member | in the policy statement | with the policy statement |
| `penalty-schedule-supplement` | CIV 5850 | every member | individual | a new or revised penalty (a rule change first) |
| `dispute-resolution-summary` | CIV 5965, 5920 | every member | in the policy statement | annually |
| `architectural-requirements` | CIV 4765 | every member | in the policy statement | annually |
| `financial-review` | CIV 5305 | every member (+ secondary) | individual | within 120 days after the fiscal year closes (gross income over $75,000) |
| `annual-report-8321` | CORP 8321 | every member | written | yearly notice of the right to the annual report |

### Assessments and collection

| Key | Statute | To | How | Clock |
| --- | --- | --- | --- | --- |
| `assessment-increase` | CIV 5615 | every member | individual | 30 to 60 days before the increase is due |
| `emergency-assessment-resolution` | CIV 5610 | every member | with the notice of assessment | the findings, before imposing it |
| `pre-lien-notice` | CIV 5660 | the owner of record (+ secondary) | certified mail | at least 30 days before recording a lien |
| `payment-plan-meeting` | CIV 5665 | the owner | a meeting | within 45 days of the request's postmark |
| `lien-copy` | CIV 5675 | every owner on the records (+ secondary) | certified mail | within 10 calendar days after recording |
| `lien-release` | CIV 5685 | the owner (+ secondary) | recorded, and a copy | within 21 days of payment |
| `foreclosure-decision` | CIV 5705 | the owner or legal representative | personal service (occupant) or first-class mail | after the vote, which is at least 30 days before any sale |
| `notice-of-default` | CIV 5710 | the owner or legal representative (+ secondary) | personal service | with the trustee's mailing within 10 business days of recording (2924b) |
| `notice-of-sale` | CIV 5715, 2924b | the owner | registered or certified mail | at least 20 days before the sale; states the right of redemption |
| `mechanics-lien-claim` | CIV 4620 | every member | individual | within 60 days of service of a claim of lien on the common area |

Before recording a lien the association offers meet and confer (5670) and the board decides by majority vote in an open meeting (5673). A step done wrong is started over at the association's cost (5690).

### Insurance, discipline, disputes

| Key | Statute | To | How | Clock |
| --- | --- | --- | --- | --- |
| `insurance-change` | CIV 5810 | every member | individual | as soon as reasonably practicable; immediately on a nonrenewal with no replacement |
| `discipline-hearing` | CIV 5855 | the member | personal delivery or individual | at least 10 days before the hearing |
| `discipline-decision` | CIV 5855 | the member | personal delivery or individual | within 14 days after the action (15 before June 30, 2025) |
| `religious-item-removal` | CIV 4706 | the member | individual | before door work |
| `meet-and-confer` | CIV 5915, 5910 | the other party | written | the association's procedure states its maximum time |
| `request-for-resolution` | CIV 5935 | the other parties | personal delivery, mail, fax, or other means | the recipient answers within 30 days |

### Records, sales, use, maintenance, defects, the manager

| Key | Statute | To | How | Clock |
| --- | --- | --- | --- | --- |
| `records-current-year` | CIV 5210, 5205 | the requester | available, or copies by individual delivery | within 10 business days of receipt |
| `records-prior-years` | CIV 5210 | the requester | as above | within 30 calendar days of receipt |
| `records-committee-minutes` | CIV 5210 | the requester | available | within 15 calendar days of approval |
| `records-withheld-explanation` | CIV 5215 | the requester | written | when asked |
| `membership-list-alternative` | CORP 8330 | the requester | written | within 10 business days of the demand |
| `resale-documents` | CIV 4530 | the owner or whom the owner authorizes | written or electronic | within 10 days of the mailing or delivery of the request |
| `architectural-decision` | CIV 4765 | the applicant | written | the documents' procedure sets the maximum time |
| `ev-charger-decision` | CIV 4745 | the applicant | written | deemed approved if not denied in writing within 60 days |
| `ev-meter-decision` | CIV 4745.1 | the applicant | written | the same, 60 days |
| `solar-decision` | CIV 714 | the applicant | written | deemed approved if not denied in writing within 45 days |
| `solar-building` | CIV 4746 | the building's owners | written, by the applicant | with a shared-roof application |
| `disaster-rebuild-completeness` | CIV 4766 | the applicant | written | 30 calendar days; review 45; appeal 60 |
| `pesticide-unit` | CIV 4777 | owner and tenant (and adjacent units) | individual | at least 48 hours before |
| `pesticide-common-area` | CIV 4777 | owners and tenants nearby | posted at the site, else individual | at least 48 hours before |
| `termite-relocation` | CIV 4785 | occupants and owner | personal delivery or individual | 15 to 30 days before |
| `defect-action-meeting` | CIV 6150 | every member | written | at least 30 days before suing the builder |
| `defect-settlement` | CIV 6100 | every member | written | as soon as reasonably practicable after resolution |
| `defect-list-6000` | CIV 6000 | (unverified) | | former 6000 is repealed; 4525(a)(6) still refers to its list |
| `manager-disclosure` | CIV 5375 | the board | written | at most 90 days before the management agreement |

No notice deadline was found on disk for rental approvals (4741 limits caps; a declaration may set its own procedure), accessory dwelling units (4751), or the other protected uses beyond the decisions above.

## What the governing documents add

A governing document may require more than the statute: a longer period, another method, more content. It cannot require less: the law prevails to the extent of any conflict (4205), and some sections apply notwithstanding the documents (5300(a)). Each clause is a `NoticeProvision` with a `Comparison`:

| Comparison | Meaning | What jason does |
| --- | --- | --- |
| `MORE` | a longer period, another method, more content | follows both; `combined` takes the larger "at least" and the smaller "at most" for the same clock |
| `SAME` | restates the statute | nothing more |
| `LESS` | asks less than the statute | the statute governs; the clause is a lead for the conflict register (`authority_order.Conflict`) |
| `DIFFERENT` | a method or step the statute does not name | the statute's method is used; whether the clause also satisfies it is a question |
| `RENUMBERED` | cites a former section number | read as its successor (`jason law-history`) |
| `OWN` | a notice the statute does not require | the document's own requirement, with its own clock |

Patterns to expect in documents written before 2014 or before the 2019-2025 amendments:

- **Hearing decisions in 15 days** (now 14, AB 130, June 30, 2025) and **hearing notices by first-class mail** (5855 now says personal delivery or individual delivery, which follows the member's 4041 choice).
- **Delivery methods copied from the pre-2023 4040** ("email if the member has agreed"), where individual delivery now follows the member's annual 4041 election.
- **Board meeting notice by posting "in a prominent place"** without the policy statement's designation, or by "other means reasonably designed to give notice", and without the agenda.
- **A 30-day rule-change notice** where the statute says 28: more, and followed.
- **Election timetables** keyed to the ballot mailing that cannot fit the 30-day pre-ballot notice of candidates.
- **Annual notices tied to the "pro forma budget" under former 1365**: now items of the annual policy statement.
- **Notice to "all members" of a hearing with no method named**: whether general notice satisfies it is a question for a written board policy or counsel.
- **Action without a meeting by unanimous written consent** (Corporations Code 7211), which 4910 does not allow except for an emergency meeting by email.

The profile's rows are in `mystique/notices.py`; each carries the section, a paraphrase, the comparison, and, for one that asks less or differs, the lead for the conflict register.

## When an owner cannot be reached

The ledger (`jason notices KEY --sync`, `tasks.notice_ledger.FOLLOW_UPS`) reads each attempt's outcome from PayHOA and says what is owed next:

| What happened | Delivered? | What follows | Force |
| --- | --- | --- | --- |
| Email bounced | no: the address is not valid (4041(e)) | resend by first-class mail to the address on the books or another the member identified; ask for a working email | required |
| Email with no delivery event after 24 hours, or failed | not shown | resend by mail, as for a bounce | policy |
| No email on file | no | first-class mail is the law's delivery; make sure a letter went | required |
| Letter never mailed | no | correct and send again | required |
| Letter forwarded | yes | ask the member to confirm the mailing address | policy |
| Letter returned | yes, on deposit (4050(b)) | send to the member's elected email or secondary address if any; ask for a current mailing address | policy |
| General notice posted where designated | yes, by the posting | a failed message is noted; a resend is owed only to a member who asked for individual delivery (4045(b)) | |

With no answer to the annual solicitation, the last mailing address the member gave in writing, else the unit's address, is the address (4041(c)). Beyond that the Act is silent on what more an association must do for an owner it cannot reach: it does not require skip tracing, a second method, or a certified copy for an ordinary notice. That is where the association should write down its practice and apply it the same way each time (AGENTS.md, "Where the law is silent"). A policy for the board to consider:

1. Every individual notice goes by the member's 4041 method; a bounce or a failed letter is resent the same week by the other channel on file.
2. A returned letter is resent to the unit's address when it differs, to the email on file, and to the secondary address, and the member is asked in writing for a current address.
3. Where the county roll shows a different mailing address for the owner, a copy goes there too, marked as sent to an address the owner has not confirmed.
4. For a notice with a hearing or a deadline the member can act on (a hearing, a pre-lien notice), a member not shown reached by the last day gets a new date and a new notice rather than a hearing in their absence.
5. Each step is recorded in the ledger; the proof of notice lists it.

## Proof of notice

A notice is proved by records, not by memory. `Evidence` names each kind, and `NoticeRequirement.proof()` gives the ones a row calls for from its methods:

| Evidence | Called for by |
| --- | --- |
| the notice as sent: its text, attachments, and date | every notice |
| the recipient list as of the record date, with each member's method and why | individual and general notices |
| each delivery attempt and its outcome | individual and general notices (the ledger) |
| each follow-up the ledger owed, sent and read back | individual and general notices |
| a declaration of mailing | first-class mail, certified mail, individual delivery by letter |
| the posting: where, from when to when, a dated photo or capture | general notices, site postings |
| the certified or registered mail numbers and receipts | certified and registered mail |
| a proof of service | personal service |
| a declaration of personal delivery | personal delivery |
| the recorder's number and date | a recording (a lien, its release) |
| the request on file, with the day it was received or mailed | clocks that run from a request or application |
| the date of the anchoring event | every clock |
| the agenda; the minutes | meetings, hearings, findings, emergency meetings, pesticide notices |

The link from a notice that went out to its requirement is its key. Name a notice's batches with the requirement's key and the date (`board-meeting-2026-10-20`, `pre-lien-notice-2026-11-01`); `notice_catalog.for_ledger` finds the requirement by the longest key the ledger key starts with, or `--requirement` says it. Then:

```
jason notices board-meeting-2026-10-20 --sync --subject "Board meeting" --since 2026-10-14
jason notices board-meeting-2026-10-20 --proof --event 2026-10-20 --general --posted 2026-10-15 --have text_as_sent,agenda
```

`tasks.notice_proof.build` takes the requirement, its clocks made stricter by the documents (`notice_catalog.effective`), the ledger's standings, and the dates a person gives (the event; the day mailed, sent, or posted; by default the ledger's first attempt), and returns a `ProofOfNotice`:

- each piece of evidence: on file, to attach, or owed (a resend the ledger still owes);
- the window from each clock and whether the notice went out in it;
- the members reached, not reached, and **reached only after the last day**: a bounce resent by mail after the deadline is delivered, but late. That is a finding for the board or counsel; the usual cure is a new date for the meeting or hearing and a new notice;
- the documents' clauses that changed the clock, and the row's caveat for counsel.

A clock that governs another act (the 4041 answers entered 30 days before the annual reports; a payment-plan meeting) is shown but does not judge the delivery (`Timing.delivery`).

## How strongly the record shows a notice given

Three readers judge a notice clock against the record: `jason record-stages` (a rule change's 4360 notices), the meeting watch (`jason schedule-evidence --watch` and `jason attention`: each board meeting's 4920 notice), and the evidence finder (`jason schedule-evidence`). They read the evidence in one place, `jason.tasks.notice_evidence`, from the ledger's standing (`notice_ledger.standing`) rather than from a notice's first attempt. Each record has a strength (`NoticeStrength`):

| Strength | When | Meets a clock on time? |
| --- | --- | --- |
| delivered | every member the ledger holds was reached by a method the notice allows (an email the receiving server accepted, a letter in the mail: 4050); or a general notice recorded as posted where the policy statement designates (4045(a)), with the individual deliveries owed under 4045(b) | yes |
| sent, with follow-ups owed | the ledger shows members owed a resend: a bounce (4041(e)), a returned letter not reached another way, a member with no email and no letter | yes, with the follow-ups listed |
| sent | it went out, but its outcomes are not synced: PayHOA's log, a copy from the association's mail, the Mailroom, a ledger whose attempts have no outcome yet | yes, with that said; `jason attention` asks a person to sync it near its deadline |
| file | jason has the notice's file (Drive, the library) but no record that it went out | never |

How a ledger notice is weighed (`notice_evidence.weigh`):
- A member owed a resend who has another attempt with no outcome yet (the resend itself, not synced) counts as not synced, not owed.
- A requirement whose methods the ledger cannot show (certified mail, personal service, personal delivery) is at most "sent": its receipts are the proof.
- A general notice recorded as posted (`jason notices KEY --mark-general --posted "WHERE, YYYY-MM-DD" --by NAME`) is delivered on the day the posting carries, with or without messages in the ledger. A posting recorded with no day in it is undated and meets no clock.

Of the records on time, the notice before its agenda, then the strongest, then the earliest judges the clock (`notice_evidence.choose`); with none on time, the first late send; with no send, the earliest file. A meeting's notice is read from the ledger's notices whose key carries the day, the meeting catalog's notice sent, and the catalog's notice file (Drive, dated by the day it was written), with the agenda only when no notice is on record (`notice_evidence.meeting_notices`). jason's own drafts are left out.

In `jason attention`, a board meeting's notice clock met only by a file is due soon near its deadline and a legal clock past it, and a clock met by a send whose outcomes are not synced is due soon within the schedule's two weeks of its deadline: a person syncs it (`jason notices KEY --sync`) or records the posting. A notice with follow-ups owed is in the notices section, as before.

## A notice as a record

A notice given to members is a record in the series book `notice`, keyed by its ledger key: `jason cite jason://notice/KEY` gives the requirement recited (the statute's words and the governing documents' clauses, each recited from its own text), the text sent if jason has it, the `{QUOTE:}` fill records with their version digests, the recipients plan's counts, the delivery standing, the proof, and the stage it served. `jason://notice/KEY/proof` is the proof alone. Counts only: a member's unit appears only with `jason cite --private`. The details are in [record-addresses.md](record-addresses.md#a-notice-as-a-record).

What jason keeps beside a notice, so its record is whole:
- `data/notices/KEY/` holds the text as sent (the rendered Markdown or HTML, with its `.refs.json` from `jason section-refs --render`), any PDF, and the recipients plan (`jason delivery --notice RULE --ids data/notices/KEY/recipients.json`);
- a batch that names its message (`params.message`, as the owner-information email batch now does) or its body gives the text when the folder does not;
- a key that starts with the requirement's key (`board-meeting-2099-01-14`) links the notice to its requirement and its stage; a key that does not names no requirement, and its proof needs `--requirement`.

### The text kept when it is sent

When jason sends a notice, or saves one as a draft for a person to send, it keeps the words as it rendered them in `data/notices/KEY/` (`jason.tasks.notice_text.keep`). A dry run keeps nothing.

| Sender | When it keeps | What | KEY |
| --- | --- | --- | --- |
| `jason broadcast FILE --notice KEY --yes` | with `--save-template` once the template is saved, else once the checks pass and it is handed to PayHOA's composer (jason does not send broadcasts; the state says so) | `message.html` (the body jason hands PayHOA, before PayHOA fills each member's placeholders), the subject, `message.html.refs.json`, and with `--tag`/`--member-tag` the recipients plan | given |
| `jason rule-change CHANGE --draft-email --yes` | once the Gmail draft is saved (no recipients) | `notice.txt`, the subject, and the sections it recites with their digests and the proposed version (`notice.txt.refs.json`) | `rule-change-proposed-CHANGE-NOTICEDATE`, or `--notice` |
| `jason owner-info --email-batch --yes --confirmed-by NAME` | once the batch is created, before the sends | `message.html` (before each owner's own fills), the subject, the fill records, and the owners and units it goes to | the notice its batches belong to (`owner-info-YEAR`, as `jason notices` syncs it); a test batch keeps nothing |
| `jason owner-info --mail-batch --yes --confirmed-by NAME` | once the batch is created | `letter.pdf` as mailed, the owners each building's letters go to, the marker | the same notice |
| `jason mailroom --pdf F --units U --send --yes --notice KEY` | after the Mailroom accepts it | `letter.pdf`, the unit and owner ids, the number of letters | given |

`kept.json` lists each keeping: its kind, its state (sent, or saved for a person to send, and where), when, by whom, the batch, and each file with its sha256. A kept file is never overwritten: other words under the same key are kept beside it (`message-2.html`), and the same words kept again add nothing. The recipients plan holds ids and counts, never names or addresses.

The record (`jason://notice/KEY`) reads `kept.json` first: the text, its digest, and whether each file still has it. A text edited since it was kept says so ("EDITED since it was kept: the words above are not the words sent") and does not count as the text as sent in the proof.

## What a notice must say, checked

Each requirement's `content` is jason's reading of what the section requires a notice to carry. `jason.community.notice_elements` holds a `Sign` row for each element: the subdivision it is read from and the words that show it in a notice. `check(requirement, text)` reads a rendered notice or a base template and reports each element as present (with its line and heading), supplied by a token (`{HEARING_DATE}`, filled when the notice is), said to be enclosed (the 5300(b)(9) insurance summary), missing, or not checkable by words (5310(a)(12)'s "any other information"). A conditional element (an emergency rule change's expiry, a teleconference meeting's instructions) is reported with its condition. The condition is data (`Sign.applies`, an [applicability](applicability.md) condition over the event's facts), and the words printed beside a finding are the row's `when`. The statute's own words that a notice recites ("Civil Code section 4360(a) provides: "...") are not counted as the element: quoting what the law requires does not carry it.

```
jason notice-check                                   # every base template; writes data/reports/notice-templates.md
jason notice-check discipline-hearing board-meeting  # some of them
jason notice-check --file data/drafts/NOTICE.md --requirement rule-change-proposed
jason notice-check --file data/drafts/NOTICE.md --requirement rule-change-adopted --event rule_change=noticed
```

**The event's facts.** A conditional element turns on a fact about the meeting, rule change, or election. The facts are the same closed sets that decide when a row is required ([above](#when-a-row-is-required)). The conditional elements:

| Requirement | Element | Required when |
|---|---|---|
| `rule-change-adopted` | the text, purpose and effect, and expiry date | `rule_change=emergency` (4360(c), (d)) |
| `board-meeting` | the teleconference instructions, help contact, and reminder | `meeting_format=entirely_by_teleconference` (4926(a)(1)) |
| `annual-policy-statement` | the electronic voting opt-in or opt-out procedures | `electronic_voting` is `opt_out` or `opt_in` (5105(i)(1)(D)) |
| `pre-ballot-notice` | when electronic ballots are due, and preliminary instructions | `electronic_voting` is `opt_out` or `opt_in` (5115(b)(2)) |
| `pre-ballot-notice` | the statement about a reconvened meeting at a 20 percent quorum | `director_quorum=at_least_20_percent` (5115(b)(6)(A), (B)) |
| `ballots` | the text of the proposed amendment | `election=amendment` (5115(g)(1)) |

- **Said by a person.** `--event FACT=WORD` states one, and may be repeated. The profile's own facts (`Community.applicability_facts()`) and the answered questions in the intake queue are read beside it, so an association whose election rules settle electronic voting states it once.
- **Three answers.**
  - The facts rule the element out: it does not apply, with the fact that decided it.
  - The facts call for it: it is required here, and a notice that lacks it has a gap.
  - No fact says: it is undetermined. The words are still checked, a missing element is reported "only for" its condition as before, and the fact that would settle it is named.

The bases checked (`jason.tasks.notice_templates.BASES`): the rule change notices (4360(a), (c)), the hearing notice (5855), the board meeting agenda (4920, 4926), the annual policy statement (5310), the annual budget report (5300), and the insurance change notice (5810). The pre-lien notice (5660) has no base yet, so every element is missing; its checklist is in `jason.community.models.legal_collections`. A test keeps the signs in step with the catalog: an element added to a row without a sign fails the build, and a base that drops an unconditional element fails it too.

The check reads words, not law. A notice that passes still goes to a person, and the `where` of each finding is there so the person can look.

### Where a template states the law in its own words

The same command lists each sentence where a base states the law in its own words (jason's reading), the statute's words for each subdivision it cites (the rule, recited from `data/authorities`), and the reference that would cite it (`{CITE:CIV#5855(c)}`). Headings and bare citations are listed apart. The references are proposals: a statute is not yet a target of `{QUOTE:}` or `{CITE:}`. The extension the reference tokens need: let the key be an upper-case code (`CIV`, `CORP`, `CCP`, `GOV`); resolve such a key through the exported statutes (`export_authorities.authority_text`, then `cite.label_text` for a subdivision); cite it as "Civil Code Section 5855(c)"; record the session the words were read from; and refuse `as-of` (jason holds one edition of the law). A copied governing-document passage in a template is proposed with `jason section-refs --patch`, as before ([embedded-references.md](embedded-references.md)).

## Rule changes: the words, the versions, and the order

`jason rule-change KEY` (`jason.tasks.rule_change`):

- **The current words** of each section come through the shared reader (`recite_sections`: the `Shelf` of `jason.tasks.cite`, which reads the living document kept as amended, else the outline), with the section's citation, address (`jason://coll/14`), permanent id, and the version in force. A section the shelf cannot place is read from `data/outlines` directly, and the page says so.
- **The proposed text** is a stage version of its own (`proposed_version`: `coll@proposed-2026-11-01`, `Stage.PROPOSED`), cited by its address (`jason://coll@proposed-2026-11-01/14`) and never merged into the text in force. The page's "versions cited" table lists both.
- **The member notice** follows 4360(a)'s order, whose sentence it quotes from disk: "the text of the proposed rule change", then "a description of the purpose and effect of the proposed rule change", headed as the board's own description.
- **The adoption notice** (4360(c)) recites the text as adopted: the noticed words, which the secretary replaces with the minutes' words where the board changed them.
- Both notices are checked against the catalog's required elements on the page.

### Publishing official rules extracted from a manual

`jason rule-change --from-manual` (`jason.tasks.manual_rule_change`) drafts the board's 4360 course for publishing the official rules that `jason manual --render` extracted from an owner's manual. The text of the proposed rule change is the official rules document (Enclosure A) with its concordance (Enclosure B), as the stage version `rules@proposed-DATE`. The manual's working Doc is not all adopted text, so the revision history (`jason revisions KEY`) separates it:

- **(a) adopted, or unchanged since the earliest version on disk**: everything not listed below, and any change a later adoption on record names (counted here, and listed);
- **(b) changed with no adoption found**: each passage with its earlier words and the words now in the manual, labeled. The notice proposes the words now in the manual; the board adopts them through 4360 or restores the earlier words. Part 2 is the rules; Part 3 the policies bound in the manual (a penalty schedule is an operating rule, 4355(a)(3)). "No adoption found" is a finding for a person, not proof that none happened;
- **(c) pending suggestions** in the working Doc: never accepted, not part of the text. An outline read before outlines were read without suggestions carries a suggested insertion as if accepted; the draft notice finds each one and strikes it from Enclosure A. A suggested deletion's words stand until a person accepts it.

The proposed text is the working text (`jason manual --render --current`), read in memory. The official rules `jason manual --render` writes hold the last adopted words instead: each (b) passage shows them where an adoption on record covers them, with jason's note reciting the working words, and only the note where no adopted version is on record ([owners-manual.md](owners-manual.md#the-last-adopted-words-not-the-working-ones)). The draft lists, for each (b) passage, whether its earlier words are adopted ones.

It also lists the changes it could not place in the concordance and the count of guidance-only changes. It writes `data/drafts/rule-change-official-rules-<notice date>.md` and nothing else; the purpose and effect are drafts for the board to adopt as its own description, and counsel reads the notice before it goes out.

## Open questions for counsel

- How days are counted for "at least N days before" and when a period ends on a weekend or holiday (Code of Civil Procedure 12, 12a and Civil Code 10 are not exported here).
- Whether a notice resent after its deadline (after a bounce) cures the notice, or the meeting or hearing must be reset.
- Whether "personal delivery" counts as individual delivery for a notice whose section names only 4040.
- Whether a pre-lien notice by certified mail must also go by the member's 4041 email election, and whether its 4040(b) secondary copy must be certified. The profile's collection rule sends both.
- Whether a member's opting into electronic voting is their choice of email for election notices (4040(c), 5105(i)).
- Whether a 4741(f) or 4235 amendment to the declaration takes effect before it is recorded.
- Whether a document's "notice to all members" with no method named is satisfied by general notice.
- Members' meetings: the Corporations Code's notice period (7511) is not on disk; the bylaws' period governs until it is read.
- Whether a recall election's pre-ballot notice carries the reconvened-meeting statement. Section 5115(b)(6)(A) conditions it on the documents requiring "a quorum for an election of directors", and 5115(b) reaches recall elections too. jason tests the documents' quorum only, as the words do.
- How 5115(d)(3)(C) reads: whether "if the association's governing documents require a quorum" limits the whole 20 percent statement or only "that the ballots will be counted if a quorum is reached". The quorum may also come from Corporations Code 7512 (5115(d)(2)). The element is not a condition until this is read.
- Whether 5103 reaches an election that fills seats after a recall. jason reads its notices as required for an election of directors, from "the number of board positions that will be filled at the election" (5103(b)(1)(A)).
- Whether the "recall elections" of 5115(a) and (b) are the "removal of directors" of 5100(a)(1). jason treats them as one kind of election.
- Whether the acclamation notices are still owed when the association held no regular election of directors in the last three years (5103(a)), so that acclamation is not available anyway.
