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
