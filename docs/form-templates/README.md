# Form templates: the design pages

Each page designs one form to the standard in [form-templates.md](../form-templates.md): what the law requires (quoted from the shelf), who uses it, the checklist the form must carry, the questions, the recitals, the clocks, the acknowledgment, the channels and marker, the profile slots, the handler and procedure, the edge cases, the leads for the board and counsel, and the test fixtures. The inventory of requests is [standard-forms.md](../standard-forms.md); the form system is [forms.md](../forms.md); the markers are [form-identifiers.md](../form-identifiers.md); how a returned form is recognized and handled is [arrivals-design.md](../arrivals-design.md).

A page’s file name is the form’s key. A marker code is two letters from the alphabet `0-9 A C E F H K M N P R T V X` (`NP` is the owner-information form). Before a code is made real, check this table so no two forms share one.

| Form | Key | Authority | Marker code (proposed) | Design page |
|---|---|---|---|---|
| Request to inspect or copy association records | `records-request` | CIV 5200 to 5240 | `RR` | [records-request.md](records-request.md) |
| Request for the membership list, and the opt-out of sharing it | `membership-list` | CIV 5220, 5225; CORP 8330 | `MN` | [membership-list.md](membership-list.md) |
| Request for the documents for the sale of a unit | `resale-documents` | CIV 4525 to 4530, 4575 | `RT` | [resale-documents.md](resale-documents.md) |
| Request to meet and confer (internal dispute resolution) | `idr-request` | CIV 5900 to 5920 | `MC` | [idr-request.md](idr-request.md) |
| Request for Resolution (alternative dispute resolution) | `adr-request` | CIV 5925 to 5965 | `RV` | [adr-request.md](adr-request.md) |
| Request to meet with the board about a payment plan | `payment-plan` | CIV 5660, 5665 | `PP` | [payment-plan.md](payment-plan.md) |
| Notice of a disputed charge, paid under protest | `disputed-charge` | CIV 5658 | `PR` | [disputed-charge.md](disputed-charge.md) |
| Architectural application (a change to a separate interest or the common area; a rebuild after a disaster) | `architectural-application` | CIV 4765, 4766 | `AP` | [architectural-application.md](architectural-application.md) |
| Request for reconsideration of a disapproval, at an open board meeting | `reconsideration-request` | CIV 4765(a)(5); 4766(e) | `RC` | [reconsideration-request.md](reconsideration-request.md) |
| Electric vehicle charging station or EV-dedicated meter application | `ev-charger` | CIV 4745, 4745.1 | `EV` | [ev-charger.md](ev-charger.md) |
| Solar energy system application (including a shared multifamily roof) | `solar` | CIV 714, 714.1, 4746 | `PV` | [solar.md](solar.md) |
| Protected-use application or notice (flags, signs, pets, roofs, antennas, landscaping, drought, personal agriculture, accessory dwelling units, rebuild, clotheslines) | `protected-use-application` | CIV 4705, 4706, 4710, 4715, 4720, 4725, 4735, 4736, 4750, 4751, 4752, 4753 | `PX` | [protected-use-application.md](protected-use-application.md) |
| Change my notice delivery (the “simple method” of CIV 4041(b)(2)(B)) | `delivery-change` | CIV 4041(b)(2), 4040, 4045 | `NC` | [delivery-change.md](delivery-change.md) |
| Secondary address for notices and collection notices (add or remove) | `secondary-address` | CIV 4040(b), 4041(a)(2), 5260(b), 5310(a)(2) | `NA` | [secondary-address.md](secondary-address.md) |
| Request to receive general notices by individual delivery (or to cancel it) | `individual-delivery-request` | CIV 4045(b), 5260(c), 4040 | `NV` | [individual-delivery-request.md](individual-delivery-request.md) |
| Candidate nomination and candidate statement | `candidate-nomination` | CIV 5100 to 5145 (5105, 5103, 5115, 5110) | `CN` | [candidate-nomination.md](candidate-nomination.md) |
| Request to be heard at a board meeting, written comment, and request to add an item (a courtesy form beyond the first) | `meeting-comment-request` | CIV 4925(b), 4930, 4920, 4935 | `HM` | [meeting-comment-request.md](meeting-comment-request.md) |
| Reasonable accommodation or modification request (pointer: outside the authorities shelf) | `accommodation-request` | CIV 4765(a)(3), 4760(a)(2), 4700(e), 4715; the fair-housing statutes are not on the shelf | `AM` | [accommodation-request.md](accommodation-request.md) |
| Owner information and notice delivery preferences (built; the page maps it to the standard) | `owner-info` | CIV 4041, 4040, 5260 | `NP` (built) | [owner-information.md](owner-information.md) |

Other forms’ rows are added by the pages’ authors, beside these and without changing them.

### Built in the library: changes to a unit and the protected uses (build step 2, part B1, 2026-10-05)

Version 1, as of 2026-10-04 (the shelf's export day), in `src/jason/community/form_library/ca/`. Each form is a State definition with its handler `response-clock` and procedure `respond` until the page's own `improvement-request` procedure is written (each definition says so in its `notes`). The questions and paragraphs the five share are `ca/improvement.py`. Each module's docstring lists where it departs from its page.

| Form | Definition | Not offered until the profile gives |
|---|---|---|
| `architectural-application` (`AP`) | `ca/architectural.py` | `PROCEDURE_CITATION`, `MAX_DAYS_APPLICATION`, `MAX_DAYS_RECONSIDERATION`, `ACK_DAYS`, `WHOSE_APPLICATION_CLOCK`, `WHOSE_RECONSIDERATION_CLOCK`, `ANNUAL_NOTICE_LINK` |
| `reconsideration-request` (`RC`) | `ca/reconsideration.py` | `PROCEDURE_CITATION`, `MAX_DAYS_RECONSIDERATION`, `WHOSE_RECONSIDERATION_CLOCK`, `TIME_LIMIT_TO_SPEAK`, `ANSWER_DELIVERY_DAYS` |
| `ev-charger` (`EV`) | `ca/ev_charger.py` | `PROCEDURE_CITATION`, `MAX_DAYS_RECONSIDERATION`, `ACK_DAYS` |
| `solar` (`PV`) | `ca/solar.py` | `PROCEDURE_CITATION`, `MAX_DAYS_RECONSIDERATION`, `ACK_DAYS` |
| `protected-use-application` (`PX`) | `ca/protected_use.py` | `PROCEDURE_CITATION`, `MAX_DAYS_APPLICATION`, `MAX_DAYS_RECONSIDERATION`, `ACK_DAYS`, `WHOSE_APPLICATION_CLOCK` |

(The standard slots, `ASSOCIATION`, `RETURN_BY_MAIL`, `RETURN_BY_EMAIL`, and `BOARD_CONTACT`, are given by the profile already.) What a profile adds with an `Add` row where its documents ask: the neighbors' acknowledgment and the fee acknowledgment (`architectural.NEIGHBOR_ACKNOWLEDGMENT`, `FEE_ACKNOWLEDGMENT`), and the solar provisions it has adopted (`solar.ADOPTABLE`). The EV form asks for neither an additional-insured endorsement nor a coverage amount (CIV 4745(f)(1)(C) changed on 2026-01-01). The protected-use form is one definition with a "which use" choice (`protected_use.USES`: each use's section, mode, and recitals); a use that is a right is a notice, never a condition of the right, and has its own acknowledgment. The response kinds `RECONSIDERATION`, `EV_METER`, `PROTECTED_USE`, and `DISASTER_REBUILD` and the notice rows `architectural-reconsideration`, `disaster-rebuild-review`, and `disaster-rebuild-appeal` are in `responses.py` and `notice_catalog.py`.

### Built in the library: the delivery, election, meeting, and accommodation forms (build step 2, part B2, 2026-10-05)

Version 1, as of 2026-10-05, in `src/jason/community/form_library/`. A form whose slots the profile has not given is not offered, and `jason form-library` names each missing slot. Each module's docstring lists where it departs from its page.

| Form | Definition | Handler, procedure | Not offered until the profile gives |
|---|---|---|---|
| `delivery-change` (`NC`) | `ca/delivery_change.py` | `owner-information`, `owner-info-cycle` | `DESIGNATED_PERSON` |
| `secondary-address` (`NA`) | `ca/secondary_address.py` | `owner-information`, `owner-info-cycle` | `DESIGNATED_PERSON` |
| `individual-delivery-request` (`NV`) | `ca/individual_delivery.py` | `response-clock`, `respond` | `DESIGNATED_PERSON`, `GENERAL_NOTICE_LOCATION` |
| `candidate-nomination` (`CN`) | `ca/candidate_nomination.py` | `response-clock`, `respond` | `NOMINATION_DEADLINE`, `NOMINATION_RETURN`, `INSPECTOR` |
| `meeting-comment-request` (`HM`) | `ca/meeting_comment.py` | `response-clock`, `respond` | `TIME_LIMIT`, `AGENDA_NOTICE_PLACE` |
| `accommodation-request` (`AM`), jurisdiction `US` | `us/accommodation.py` | `response-clock`, `respond` | `COUNSEL` |

The accommodation definition recites only what the shelf holds and says in its notes that the fair-housing statutes are not on the shelf. Each page's dedicated procedure (`delivery-requests`, `accommodation-request`, a step in `election` and in `board-packet`) is still a proposal; the definitions name `owner-info-cycle` or `respond` until it is written.

### Built in the library: records, disputes, and money (build step 2, part A, 2026-10-05)

In `src/jason/community/form_library/ca/`, as of 2026-10-05 (the shelf's 2025 session publication). Each is a State definition with the handler `response-clock` and the procedure `respond` until the page's own procedure is written (named below). The paragraphs and question builders the seven share are `ca/common.py`. Each module's docstring holds its version notes (what was kept, added, or removed) and where it departs from its page. A form whose slot the profile has not given is not offered, and `jason form-library` names the slot.

| Form | Definition | Version | Page's proposed procedure | Not offered until the profile gives |
|---|---|---|---|---|
| `records-request` (`RR`) | `ca/records.py` | 2 (from 1) | `records-request` | nothing more than the standard slots |
| `idr-request` (`MC`) | `ca/idr.py` | 2 (from 1) | `meet-and-confer` | nothing more than the standard slots |
| `adr-request` (`RV`) | `ca/adr.py` | 1 | `request-for-resolution` | nothing more than the standard slots |
| `resale-documents` (`RT`) | `ca/resale.py` | 1 | `resale-documents` | `FEE_SCHEDULE` |
| `membership-list` (`MN`) | `ca/membership_list.py` | 1 | `membership-list` | nothing more than the standard slots |
| `payment-plan` (`PP`) | `ca/payment_plan.py` | 1 | `payment-plan` | `PAYMENT_PLAN_STANDARDS` |
| `disputed-charge` (`PR`) | `ca/disputed_charge.py` | 1 | `disputed-charge` | nothing more than the standard slots |

Departures from the pages, shared by all seven: a question the page makes required in one case only (an email for electronic delivery, a representative's designation) is not required, because `FormQuestion.required` is a plain flag, and its help line says when it is needed (the pages' `required_if` is a template change still to come); the second stage of a page (the estimate copy, the response, the reply) needs a `stage` and a `direction` on the template and is a deferred required item; the recitals are checked against the shelf but not yet printed from it, so the sentences the law requires word for word (the Request for Resolution's notice, the 4528 billing form's sentences, the opt-out statement) are written into each form's text and tested against the page's words. The 10-point type rule of the billing disclosure (CIV 4528) is a rendering requirement, since `FormStyle` holds no smallest point size. The page slots a form does not require (for example `{RECORDS_CONTACT}`, `{BUSINESS_OFFICE}`, `{IDR_MAX_DAYS}`) are not slots of version 1 or 2: the form states the law's rule, and a time the board has not adopted is printed as proposed.
