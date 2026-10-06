# Standard forms: the requests an association must accept, and how to find them in the law and the documents

Status: inventory and method (2026-10-05). It lists the requests a member makes of a common interest development that call for a standard form, says which the law makes the association accept, and gives a repeatable way to find more in the statutes, the governing documents, and the reference works. It feeds the known-forms table of [arrivals-design.md](arrivals-design.md): every form jason sends has a procedure that processes its responses, so each row here is a candidate for a form, a handler, and a procedure.

Quotations are from the statutes jason holds (`jason cite`, `authorities`), which are not official restatements. A reading is labeled as one and is never the rule.

## Three families

| Family | Why a form | Who decides it is needed |
|---|---|---|
| **Required by the law:** the association must accept, consider, and answer the request, often on a clock | A request the law makes the association take is one a form makes complete and dated, and a dated, complete request is the best evidence of the association's good faith | The statute |
| **Required by the governing documents:** the declaration, the rules, or a policy makes the owner ask first | The documents set the content, the clock, and the decision-maker; a form carries them | The documents (read against the law above them, Civil Code 4205) |
| **Offered:** nothing requires it; the association chooses to collect it | A survey, a sign-up, a registration, a contact update | The board; no authority, so the form's `authority` is `None` and its handler is chosen when it is made |

## Family one: the law makes the association take the request

Every row cites a section on the authorities shelf. "jason now" is what exists today: a request **kind** with a clock (`ResponseKind`, `jason respond`), a notice-catalog requirement, an outbound form (`FormKey`), or nothing.

| Request | Authority | What the member submits | What the association must do | jason now |
|---|---|---|---|---|
| Inspect or copy association records | CIV 5205, 5210 | a written request, naming the records (and a written designation of a representative: 5205(b)) | make the records available in the timeframes of 5210; bill only the direct and actual cost of copying and mailing (5205(f)); redact; | kind `RECORDS` with a clock; form `records`; no scan handler |
| Architectural application | CIV 4765 (4766 after a disaster) | the application the documents require | a fair, reasonable, expeditious procedure that states its maximum response time; a good-faith decision; in writing, with reasons and the reconsideration procedure; reconsideration at an open board meeting; an annual notice of the requirements (4765(c)) | kind `ARCHITECTURAL`; notice-catalog rows; design in [improvement-requests.md](improvement-requests.md); no form |
| Electric vehicle charging station | CIV 4745, 4745.1 | an application, processed as an architectural modification | decide in writing; deemed approved if not denied in writing within 60 days (unless it asked reasonably for more information) | kind `EV_CHARGER`; no form |
| Solar energy system | CIV 714, 714.1, 4746 | an application; on a shared multifamily roof, notice to each owner in the building | review within the limits; require the applicant's notice and liability insurance (4746) | kind `SOLAR`; no form |
| Low water-using landscaping, accessory dwelling unit, and the other protected uses | CIV 4735, 4751, 4750, 4753 | an application if the documents require approval for the change | the governing document's approval requirement is void where it bars the protected use; the application is still decided on a clock | partly in kind `ARCHITECTURAL`; no form |
| Payment plan | CIV 5665 | a written request to meet with the board about the debt noticed | give the standards for payment plans; meet in executive session (or by committee) within the time the section sets | kind `PAYMENT_PLAN`; no form |
| Hearing before discipline | CIV 5855 | the member's right to attend and be heard (a response, or a request to reschedule or to be heard in writing, where the documents allow) | notify the member in writing, with the date, time, place, the nature of the alleged violation, and the right to attend; hold the hearing | kind `HEARING_REQUEST`; no form |
| Internal dispute resolution | CIV 5915 | a written request to meet and confer | "The association shall not refuse a request to meet and confer"; the board designates a director; a written agreement binds when signed and ratified | kind `DISPUTE`; no form |
| Alternative dispute resolution | CIV 5925 to 5965 (5930) | a request for resolution; a party may not file an enforcement action without endeavoring to submit the dispute to ADR first (5930(a)) | the article's request-and-response procedure | kind `ADR`; no form |
| Pay under protest | CIV 5658 | the owner's written notice that a charge is disputed and paid under protest | a right of the owner (and a path to small claims), not a request the association grants; the notice is the evidence | not read as a kind |
| Secondary address for notices | CIV 4040(b), 4041(a)(2) | a secondary email or mailing address | "shall deliver an additional copy" of the notices the section names | part of the owner-information form |
| Individual delivery of general notices | CIV 4045(b) | a request to receive general notices by individual delivery | "all general notices" go to that member individually | not collected on a form |
| Annual delivery preferences and occupancy | CIV 4041 | the owner-information form (preferred and secondary delivery, representative, occupancy) | solicit yearly; enter the answers 30 days before the annual reports | built ([owner-information.md](owner-information.md)) |
| Resale documents | CIV 4525 to 4530 | an owner's (or an agent's) request for the documents, with a billing disclosure on the form 4528 sets | deliver the documents with the charges disclosed in the 4528 form | kind `RESALE`; no form |
| Run for the board; nominate | CIV 5100 to 5145 (5105, 5110) | a nomination and, if the rules ask, a candidate statement | the election rules; an inspector of elections; equal access to association media | no form |
| Speak at a meeting; be heard | CIV 4925(b) | an open-forum request (the board may set a time limit) | permit any member to speak | the meeting room's open forum |
| Reasonable accommodation (assistance animals, accessible parking, modifications) | outside the Act: federal and state fair-housing law; CIV 4765(a)(3) points to the Fair Employment and Housing Act | a request, which may be oral or written | consider it; a decision may not violate the Act | not on the authorities shelf; a question for counsel |

The last row is not on jason's shelf, so it is a pointer, not a recital. Rows with "no form" are the candidates for the first standard forms.

## Family two: the governing documents make the owner ask

The documents differ by association, so the rows are the profile's ([the profile's inventory](../mystique/docs/standard-forms.md) is the worked example). The kinds recur in most declarations:
- a rental or leasing application, and the priority list and exceptions that go with it;
- a variance request, with its own hearing procedure;
- an approval for a change to a unit or an exclusive-use area;
- an annual resident and vehicle registration;
- a parking or guest permit, a reservation of a common facility, a move-in or move-out request;
- a request to be excused or heard that the documents create.

A document may also state a clock, a fee, a hearing, or a rehearing for each. The statute above it can override a part (Civil Code 4205); the board records a conflict, never resolves one.

## Family three: offered

A survey, an interest list, a volunteer sign-up, a contact update, an RSVP. No authority; the form's handler is chosen when it is made ([arrivals-design.md](arrivals-design.md#the-handler-is-chosen-when-the-form-is-made)).

## How to find them: from the law, the documents, and the reference works

The same method serves a new association and a year's law review. It is a search with a reading step, and a person confirms every result. It adds no form by itself.

1. **Seed from the statutes.** The authorities shelf is on disk. A pass over each section's text looks for the language that creates a request: "upon request", "written request", "may request", "submit", "application", "shall approve or deny", "deemed approved", "within N days of", "shall not refuse". Each hit is a span with its citation. This needs no model, and the spans are the same for every association.
2. **Seed from the documents.** The same search over the governing documents, the rules, the policies, and the owner's manual (`passage_search`, keyword mode, no GPU): "prior written approval", "submit an application", "written request", "shall register", "permit", "hearing", "within thirty (30) days". The documents' duty reader (`document_duties`) already extracts each norm with its bearer, trigger, and deadline; a right or condition whose trigger is a request or application is a candidate.
3. **Seed from the reference works and context packs.** The reference shelf (`jason reference --cites`) and the Department's guides name the processes an association is expected to run; a section they cite that the shelf lacks is a gap to close first (`citation_gaps`).
4. **Read each span with the local model.** Under the GPU lock and after the preflight (`jason local-ai`), the model reads a span and fills one record, with the quoted words copied exactly from the span:

   | Field | |
   |---|---|
   | `who submits`, `to whom` | the member and the body (the board, a committee, the manager) |
   | `what` | the request, in the section's own words |
   | `required content` | what the section or the form must carry |
   | `clock` | each deadline: for the member, for the body, and what happens if it passes (deemed approved) |
   | `decision` | who decides, in writing, with reasons, with reconsideration |
   | `authority` | the canonical citation |
   | `quote` | the operative words, copied verbatim |

   The quote is checked against the stored text (`verify_quotes`); a quote that is not found is dropped, and the candidate with it. The model's reading is a lead: about one in five norm readings across the corpus is the wrong kind.
5. **Join across sources.** Candidates that share a subject (a statute and the document section that carries it out) are grouped: the statute gives the floor, the document gives the procedure, the owner's manual may already hold a form.
6. **A person confirms.** Each group is accepted as a known-form row, held for the board (the law is silent on a clock the form needs: a proposed policy), or dropped. A conflict between a document and a statute becomes a `Conflict` row for the board and counsel, never a guess.

`jason forms --discover` is this pass (proposed, not built): `--source statutes|documents|all`, a candidates file under `data/forms/`, and a report a person reads. The seeds in steps 1 and 2 run first and alone; the model runs only on the spans they find.

## What this does not decide

- Whether a form is the right way to take a request. A request taken on a form is still decided by the body the law or the documents name.
- A form does not make a request valid or invalid; a request in another form is still a request.
- Where the law is silent on a clock the form needs, jason proposes a policy for the board to adopt (AGENTS.md).
