# Architectural application (`architectural-application`)

Status: design (2026-10-05). Form key `architectural-application`, marker code `AP` (proposed), authority `CIV 4765, 4766` (the annual notice is `CIV 4765(c)`). The standard it follows is [../form-templates.md](../form-templates.md); the workflow behind it (states, clocks, the proposed policies) is [../improvement-requests.md](../improvement-requests.md), and this page reuses that design and does not change it. Its siblings: [reconsideration-request.md](reconsideration-request.md) (the request after a disapproval), [ev-charger.md](ev-charger.md), [solar.md](solar.md), and [protected-use-application.md](protected-use-application.md), which are the same office running the same procedure on a statute's own terms.

Quotations are from the statutes on jason's authorities shelf (`data/authorities/CIV/`), which are not official restatements; the recorded and enacted law controls. A reading is labeled as one and is never the rule.

## 1. Authority and what the law requires

**As-of.** The shelf is the 2025 session publication of the Civil Code, exported 2026-10-04. jason holds one edition of the law, so a recital carries no `as-of` date of its own; the form's recital line says "as on jason's shelf of 2026-10-04". Section 4766 was added by Stats. 2025, Ch. 548 (SB 625); the shelf's history has no earlier edition of it. A form that recites by token cannot drift: the build fails if a cited subdivision is gone ([../form-templates.md](../form-templates.md#drift-the-recitals-are-by-token)).

**CIV 4765, the procedure for a physical change** (the whole section, quoted):

> **(a)** This section applies if the governing documents require association approval before a member may make a physical change to the member’s separate interest or to the common area. In reviewing and approving or disapproving a proposed change, the association shall satisfy the following requirements:
>
> **(1)** The association shall provide a fair, reasonable, and expeditious procedure for making its decision. The procedure shall be included in the association’s governing documents. The procedure shall provide for prompt deadlines. The procedure shall state the maximum time for response to an application or a request for reconsideration by the board.
>
> **(2)** A decision on a proposed change shall be made in good faith and may not be unreasonable, arbitrary, or capricious.
>
> **(3)** Notwithstanding a contrary provision of the governing documents, a decision on a proposed change may not violate any governing provision of law, including, but not limited to, the Fair Employment and Housing Act (Part 2.8 (commencing with Section 12900) of Division 3 of Title 2 of the Government Code), or a building code or other applicable law governing land use or public safety.
>
> **(4)** A decision on a proposed change shall be in writing. If a proposed change is disapproved, the written decision shall include both an explanation of why the proposed change is disapproved and a description of the procedure for reconsideration of the decision by the board.
>
> **(5)** If a proposed change is disapproved, the applicant is entitled to reconsideration by the board, at an open meeting of the board. This paragraph does not require reconsideration of a decision that is made by the board or a body that has the same membership as the board, at a meeting that satisfies the requirements of Article 2 (commencing with Section 4900) of Chapter 6. Reconsideration by the board does not constitute dispute resolution within the meaning of Section 5905.
>
> **(b)** Nothing in this section authorizes a physical change to the common area in a manner that is inconsistent with an association’s governing documents, unless the change is required by law.
>
> **(c)** An association shall annually provide its members with notice of any requirements for association approval of physical changes to property. The notice shall describe the types of changes that require association approval and shall include a copy of the procedure used to review and approve or disapprove a proposed change.

**CIV 4766, a substantially similar reconstruction after a disaster** (the whole section, quoted; the form carries a rebuild section, so all of it is read):

> **(a)** Any covenant, restriction, or condition contained in any deed, contract, security instrument, or other instrument, and any provision of a governing document that subjects a substantially similar reconstruction of a residential structure that was destroyed or damaged in a disaster to review by a body shall be processed and approved in accordance with this section.
>
> **(b)(1)** The body shall determine whether an application is complete or incomplete and provide written notice of this determination to the applicant no later than 30 calendar days after the body receives the application.
>
> **(b)(2)** If the body determines that an application is incomplete, the body shall simultaneously provide the applicant with a list of incomplete items and a description of how the application can be made complete.
>
> **(b)(2)(A)** After receiving a notice that the application is incomplete, an applicant may cure and address the items that are deemed incomplete by the body by resubmitting the application.
>
> **(b)(2)(B)** In the review of an application resubmitted pursuant to subparagraph (A), the body shall not require the applicant to include an item that was not identified as necessary in covenant, restriction, or condition contained in any deed, contract, security instrument, or other instrument, and any provision of a governing document in effect at the time the application was originally submitted.
>
> **(b)(2)(C)(i)** If an applicant resubmits an application pursuant to subparagraph (A), the body shall determine whether the additional application has remedied all incomplete items listed in the determination issued pursuant to this paragraph.
>
> **(b)(2)(C)(ii)** The review and determination of the resubmitted application shall be subject to the timelines and requirements specified in this subdivision.
>
> **(b)(3)** If the body does not make a timely determination as required by this subdivision, the application or resubmitted application shall be deemed to be complete for the purposes of this section.
>
> **(c)** Once an application is deemed complete, the body shall conduct any review of the proposed modification to the separate interest, including a substantially similar reconstruction of a residential structure, and do either of the following within 45 calendar days:
>
> **(c)(1)** If the body determines that the complete application is not compliant with the body’s lawfully adopted standards in effect at the time the application was first submitted, the body shall return in writing a full set of comments to the applicant with a comprehensive request for revisions.
>
> **(c)(2)** If the body determines that the complete application is compliant with the body’s lawfully adopted standards in effect at the time the application was first submitted, the body shall approve the application and notify the applicant accordingly.
>
> **(d)(1)** If a body finds that a complete application is noncompliant, the body shall provide the applicant with a list of items that are noncompliant and a description of how the application can be remedied by the applicant within the time limits specified in subdivision (b).
>
> **(d)(2)** The body shall provide the list and description authorized by paragraph (1) when it transmits its determination to the applicant as required by subdivision (b).
>
> **(d)(3)** If a body denies an application based on a determination that the application is noncompliant, the applicant may attempt to remedy the application.
>
> **(d)(4)** If an applicant submits an application pursuant to paragraph (3), the additional application is subject to the timelines of a new application as specified in subdivision (b).
>
> **(e)(1)** If an application is determined to be incomplete pursuant to subdivision (b) or determined to be noncompliant pursuant to subdivision (d), the body shall provide a process for the applicant to appeal that decision pursuant to Section 4765.
>
> **(e)(2)** The body shall provide a final written determination on the appeal no later than 60 calendar days after receipt of the applicant’s written appeal.
>
> **(f)(1)** Once a body approves an application pursuant to this section, the body shall not subject the applicant to any appeals or additional hearings.
>
> **(f)(2)** The prohibition described in paragraph (1) does not apply to the applicant’s noncompliance with the approved application.
>
> **(g)** A court shall award reasonable attorney’s fees to the applicant who prevails in an action to enforce this section.
>
> **(h)(1)** “Body” means an association, architectural review committee, or similar body.
>
> **(h)(2)** “Disaster” has the same meaning as in Section 4752.
>
> **(h)(3)** “Substantially similar reconstruction of a residential structure” has the same meaning as in Section 4752.

**CIV 4752, the words 4766(h) points to** (subdivisions (a) and (c) quoted; the form's rebuild section asks for the facts these words turn on):

> **(a)** Any covenant, restriction, or condition contained in any deed, contract, security instrument, or other instrument, and any provision of a governing document shall be void and unenforceable to the extent that it prohibits, or includes conditions that have the effect of prohibiting, a substantially similar reconstruction of a residential structure that was destroyed or damaged in a disaster.
>
> **(c)(1)** “Disaster” means any of the following: **(A)** A state of disaster or emergency declared by the federal government. **(B)** A state of emergency proclaimed by the Governor pursuant to Section 8625 of the Government Code. **(C)** A local emergency proclaimed by a local governing body or official pursuant to Section 8630 of the Government Code.
>
> **(c)(2)** “Objective design standard” means a standard that involves no personal or subjective judgment and is uniformly verifiable by reference to an external and uniform benchmark or criterion available and knowable by both the applicant and the association before submittal.
>
> **(c)(3)** “Substantially similar reconstruction of a residential structure” means a proposal that rebuilds a residential structure on a separate interest located in a common interest development that complies with all of the following: **(A)(i)** The local building code. **(ii)** For purposes of this subparagraph, a proposal shall be considered to be in compliance with the local building code if the building permit is deemed approved by the local agency with appropriate jurisdiction. **(B)** The interior livable square footage of the rebuilt residential structure will not exceed 110 percent of the square footage that existed when the structure was damaged or destroyed. **(C)** The exterior footprint of the rebuilt residential structure will meet either of the following: **(i)** The rebuilt residential structure will be constructed in the same location and to the same exterior dimensions as the structure that was damaged or destroyed. **(ii)** The setbacks for the rebuilt residential structure will be at least four feet from the side and rear lot lines. **(D)** The height of the rebuilt residential structure will not exceed 110 percent of the height that existed when the residential structure was damaged or destroyed, or 100 percent of the height allowed by the governing documents of the association in effect at the time the proposal was submitted, whichever is greater. **(E)** Any objective design standard in effect at the time the original residential structure was destroyed or damaged in a disaster, provided that the standard does not unreasonably increase the cost to construct, effectively prohibit the construction of, or extinguish the ability to otherwise rebuild, a substantially similar residential structure.

**CIV 4760, a member's own modifications** (two subdivisions the form meets):

> **(a)(2)(D)** Any member who intends to modify a separate interest pursuant to this paragraph shall submit plans and specifications to the association for review to determine whether the modifications will comply with the provisions of this paragraph. The association shall not deny approval of the proposed modifications under this paragraph without good cause.
>
> **(b)** Any change in the exterior appearance of a separate interest shall be in accordance with the governing documents and applicable provisions of law.

(Paragraph (a)(2) begins: "Modify the member’s separate interest, at the member’s expense, to facilitate access for persons who are blind, visually handicapped, deaf, or physically disabled, or to alter conditions which could be hazardous to these persons.", and its conditions (A) to (C) are on the shelf; the whole subdivision (a) begins "Subject to the governing documents and applicable law, a member may do the following:".)

**What the law requires of this form, and of the procedure behind it (the association's plain-words note, not the statute's):**

- The procedure is in the governing documents, with prompt deadlines, and **states the maximum time for response to an application and the maximum time for response to a request for reconsideration** (4765(a)(1)). The form states both, taken from the procedure, so that the annual notice, the procedure, and the form never differ.
- The decision is in writing; a disapproval carries why and a description of the reconsideration procedure (4765(a)(4)).
- A disapproved applicant may ask the board to reconsider, at an open meeting (4765(a)(5)); the request form is [reconsideration-request.md](reconsideration-request.md).
- The members get an annual notice of the types of change that need approval, with a copy of the procedure (4765(c)). This form and that notice share one source: the profile's change rows and its procedure row.
- A rebuild after a disaster runs on 4766's clocks, not the ordinary ones.

**What the law leaves silent, so the board's written policy fills it** (each is a proposed policy in [../improvement-requests.md](../improvement-requests.md#where-the-documents-are-silent-policies-proposed-for-the-board), not a rule): a period for an ordinary application where the documents state none; what silence means for an ordinary application (4765 states no deemed approval); the contents of an application; a fee; neighbor acknowledgment; how long an approval lasts. 4765 applies only where the governing documents require approval (4765(a), opening words); a change they do not require approval for is outside it.

## 2. Who uses it, and when

- **Who.** An owner of a separate interest, or a person the owner authorizes in writing, who wants to make a physical change to the separate interest or to the common area (including an exclusive-use area) and whose governing documents require approval first. A co-owner may submit; the rules for several owners are in section 12.
- **When.** Before the work starts. Also when an owner is not sure the change needs approval: the form lets the owner say so, and the association answers the question in writing (it is not "approved" and it is not "denied": it is "approval required", "approval not required", or "undetermined", [../applicability.md](../applicability.md)).
- **Three tracks on one form.** The ordinary application, the accessibility modification (4760(a)(2): plans and specifications are submitted for review, and denial needs good cause), and the rebuild after a declared disaster (4766). The member chooses by two questions (`accessibility`, `disaster_rebuild`); the handler sets the track and may correct it.
- **Not this form.** A charging station or an EV-dedicated meter ([ev-charger.md](ev-charger.md)); a solar energy system ([solar.md](solar.md)); a use the law protects ([protected-use-application.md](protected-use-application.md)); a rental application, a variance request, a repair request, a complaint (the profile's own forms, or the maintenance and complaint paths). A request that is really a variance is read in section 12.

## 3. What the form must carry

Each item names the question that carries it. The checklist test (section 14) reads this table.

| # | The form must carry | Authority | Carried by |
|---|---|---|---|
| C1 | The change, said so it can be decided: what, where, and whether it is the separate interest or the common area | 4765(a), opening words; 4765(a)(2) (a decision needs something to decide) | `change_category`, `change_what`, `change_where`, `change_location_detail` |
| C2 | The owner and the unit, and who is submitting | 4765(a)(4) (a written decision goes to someone); 4041(a)(3) (a legal representative) | `unit`, `owner_name`, `submitted_by`, `rep_authorization` |
| C3 | Plans and specifications | 4760(a)(2)(D) for the accessibility track; the documents' checklist, else the proposed `improvement-application-contents` | `plans_attached` |
| C4 | Contractor, licence, insurance | the documents; proposed `improvement-application-contents` | `owner_doing_work`, `contractor_name`, `contractor_license`, `contractor_insurance` |
| C5 | Permit, where the change needs one | 4765(a)(3) (a decision may not violate "a building code or other applicable law governing land use or public safety") | `permit_needed`, `permit_number` |
| C6 | Start and completion dates | proposed `improvement-lifetime` | `start_date`, `finish_date` |
| C7 | The fee, only if the documents set one | the documents; the form shows what they set and invents none | `fee_ack` |
| C8 | **The maximum time for response to an application** | 4765(a)(1), last sentence | not a question: the "What happens next" panel (section 6), filled from `{MAX_DAYS_APPLICATION}` |
| C9 | **The maximum time for response to a request for reconsideration** | 4765(a)(1), last sentence | the same panel, from `{MAX_DAYS_RECONSIDERATION}` |
| C10 | That the decision will be in writing, with reasons if disapproved and a description of the reconsideration procedure | 4765(a)(4) | the same panel |
| C11 | That a disapproved applicant may ask the board to reconsider at an open meeting, and how | 4765(a)(5) | the same panel; the form [reconsideration-request.md](reconsideration-request.md) |
| C12 | The rebuild section, its clocks, the list of incomplete items, the appeal, and the end of appeals once approved | 4766(b), (c), (d), (e), (f) | `disaster_rebuild` and the `rebuild_*` questions; the rebuild panel (section 6) |
| C13 | The accessibility track | 4760(a)(2)(D) | `accessibility` |
| C14 | Neighbor acknowledgment: **optional**, and present only where the documents require it | none in the Act; see section 13 | `neighbor_ack` (shown only when `{NEIGHBOR_ACK_SOURCE}` is set) |
| C15 | The owner's signature (and a representative's authorization) and the date | the documents; proof of who applied | signature line, `rep_authorization` |
| C16 | Help, another format, and that a request in other words is still a request | the standard (help is on the form; not the only door) | `help_needed`; the help panel |
| C17 | A pointer to the annual notice and its copy of the procedure | 4765(c) | the footer link `{ANNUAL_NOTICE_LINK}` |

## 4. The questions

One question, one value. "Shown when" says when the question is on a copy; a question the documents do not support is not asked ("never ask what the law or documents bar"). `Required` is for the form to be complete as a form; a missing item the documents make necessary is a person's finding of "incomplete", not the form's. The plain-words help for a legal term is in the form; it is not repeated here.

| key | Question (plain words) | kind | required | why (authority) | reads as | sets |
|---|---|---|---|---|---|---|
| `unit` | The address of your unit | short | yes | the separate interest it is for (4765(a)); places a mailed return | address (prefilled `UNIT_ADDRESS` on an emailed copy) | `ImprovementRequest.unit` |
| `owner_name` | Owner's name (each owner of record) | short | yes | the written decision (4765(a)(4)) goes to the owner | name | the applicant record |
| `submitted_by` | Who is sending this? The owner / a co-owner / someone the owner has authorized in writing / a contractor, with the owner's signature | choice | yes | proof of authority; no clock turns on it | option key | applicant role |
| `rep_authorization` | I am attaching the owner's written authorization | checkbox | when `submitted_by` is not the owner | a representative acts for the owner (4041(a)(3) names the owner's legal representative) | option key | the authority on file |
| `contact_phone` | A phone number, if you want us to call | phone | no | convenience only; never required | phone | contact (P2) |
| `decision_delivery` | How should we send you the written decision? By mail to the unit / by mail to another address / by email | choice | yes | the decision is in writing (4765(a)(4)); an email address is required only if you choose email (4041(b)(2)(A)) | option key | delivery route |
| `contact_email` | Your email address | email | only if `decision_delivery` is email | delivery by email | email | contact (P2) |
| `change_category` | What kind of change is it? (a list from the association's rows) / something else / not sure | choice | yes | 4765(c) (the annual notice names the types needing approval); the profile's `change_rules()` | option key | the category and the track |
| `change_what` | What do you want to do? Describe it in your own words | paragraph | yes | a decision needs the thing decided (4765(a)(2)); it is the application's text | text | `ImprovementRequest.description` |
| `change_where` | Where? Inside my unit / outside my unit (a wall, roof, door, window, yard) / in my exclusive-use area / in the common area / not sure | choice | yes | 4765(a) names "the member’s separate interest or ... the common area" | option key | `location` |
| `change_location_detail` | Which part? (for example "rear patio, east wall") | short | no | helps find the part; the plan shows it exactly | text | `location` detail |
| `replaces` | What does it replace, if anything? | short | no | the unit's record links an approval to what it changes ([../unit-records-design.md](../unit-records-design.md)) | text | `components` |
| `like_for_like` | In your words, is it the same as what is there / different from what is there / new | choice | no | the owner's own word, shown as the owner's and never as the association's finding | option key | `owners_word` |
| `plans_attached` | I am attaching: drawings to scale / a description of materials and colors / photos of the area / product sheets (the list is the profile's checklist for the category) | checkbox | yes for the items the checklist marks needed | 4760(a)(2)(D) (plans and specifications); the documents' checklist | option keys | the checklist result (a lead) |
| `owner_doing_work` | I am doing the work myself | checkbox | no | tells us there is no contractor to ask about | option key | work provider |
| `contractor_name` | Contractor's name | short | when the documents require it and `owner_doing_work` is not checked | the documents; proposed `improvement-application-contents` | name | contractor |
| `contractor_license` | The contractor's licence number | short | same | the documents; a licensed contractor where the work needs one | text | contractor |
| `contractor_insurance` | I am attaching the contractor's certificate of insurance | checkbox | same | the documents | option key | condition proof |
| `permit_needed` | Does the work need a city or county permit? Yes / no / not sure | choice | yes | 4765(a)(3) (a building code or land-use or safety law) | option key | permit state |
| `permit_number` | The permit number, if you have it | short | no | owner-supplied evidence; jason holds no owner's permit | text | evidence |
| `start_date` | When do you expect to start? | date | yes | proposed `improvement-lifetime` (an approval's start and finish times) | date | start |
| `finish_date` | When do you expect to finish? | date | yes | the same | date | finish |
| `accessibility` | This change is to make my home easier or safer for a person who is blind, visually handicapped, deaf, or physically disabled | checkbox | no | 4760(a)(2) and (a)(2)(D); we do not ask who or what the condition is | option key | track (accessibility) |
| `disaster_rebuild` | Is this to rebuild a home that was destroyed or damaged in a disaster? Yes / no / not sure | choice | yes | 4766(a); 4752(c)(1) | option key | track (rebuild) |
| `disaster_declared_by` | Who declared the disaster? The federal government / the Governor / a local government / not sure | choice | no | 4752(c)(1)(A) to (C) | option key | rebuild facts |
| `rebuild_old_sqft` | Interior living area before the disaster, in square feet | short | no | 4752(c)(3)(B) | text | rebuild facts |
| `rebuild_new_sqft` | Interior living area as rebuilt | short | no | 4752(c)(3)(B) (110 percent) | text | rebuild facts |
| `rebuild_height` | Height before and as rebuilt | short | no | 4752(c)(3)(D) | text | rebuild facts |
| `rebuild_footprint` | The footprint is the same place and size / the setbacks are at least four feet from the side and rear lot lines / neither or not sure | choice | no | 4752(c)(3)(C)(i), (ii) | option key | rebuild facts |
| `rebuild_permit` | The building permit: deemed approved / applied for / not yet applied | choice | no | 4752(c)(3)(A)(ii) | option key | rebuild facts |
| `neighbor_ack` | Neighbors who may be affected have been told: attached / not attached / does not apply | choice | no, and never a condition | only where `{NEIGHBOR_ACK_SOURCE}` names the documents' section; proposed `improvement-neighbors` | option key | neighbor file (third parties', P2) |
| `fee_ack` | I have paid, or will pay, the review fee of `{FEE_SCHEDULE}` | checkbox | only where the documents set a fee for the category | the documents; none invented | option key | fee state |
| `help_needed` | I need this form in another format, in larger print, in another language, or help filling it in | checkbox | no | the standard (help on the form) | option key | an accommodation lead |
| (signature) | Signature of owner, and the date | signature | yes | proof of the application; the documents | text | signed on |

The rebuild questions are asked only if `disaster_rebuild` is yes or not sure, and they are **optional**: the 4766 clocks run for any application the member says is a rebuild (the handler takes the conservative course, section 12), and no rebuild fact is required to start them. A rebuild application's checklist is the documents' items in effect on the day it was submitted (4766(b)(2)(B)); `plans_attached` for that track lists only those.

**The attestation** (above the signature): "I am the owner of this unit, or I am authorized by the owner to send this. What I have written is true to the best of my knowledge. I understand that an approval by the association is an approval under its procedure, and does not say that the change is safe, meets the building code, is insured, or is worth what it costs." The last sentence is the base template's statement of what an approval is, which the board adopts with the template ([../improvement-requests.md](../improvement-requests.md#the-board-stage)).

## 5. The recitals

The form opens with these, in order, each by token, with the subdivision it is and the line "as on jason's shelf of 2026-10-04. jason's copy is not an official restatement." Statute targets are not yet resolved by `{QUOTE:}` (notices.md proposes the extension: an upper-case code key, the exported statutes, refusing `as-of`), so the tokens below are the proposed spelling; until the extension is built the build fills them from `export_authorities.authority_text`.

1. `{QUOTE:CIV#4765(a)(1)}` (procedure; maximum time)
2. `{QUOTE:CIV#4765(a)(4)}` (decision in writing; reasons; reconsideration described)
3. `{QUOTE:CIV#4765(a)(5)}` (reconsideration at an open meeting)
4. `{QUOTE:CIV#4765(c)}` (the annual notice)
5. Where the rebuild section is shown: `{QUOTE:CIV#4766(b)(1)}`, `{QUOTE:CIV#4766(b)(2)}`, `{QUOTE:CIV#4766(b)(3)}`, `{QUOTE:CIV#4766(c)}`, `{QUOTE:CIV#4766(e)(2)}`, `{QUOTE:CIV#4766(f)(1)}`
6. Where `accessibility` is checked, in the acknowledgment: `{QUOTE:CIV#4760(a)(2)(D)}`

The paragraph tokens are listed so nothing depends on whether a subdivision token renders its paragraphs. Each recital is followed, if at all, by "In plain words (the association's note, not the law's): ...", never in its place.

## 6. What the member is told

The panel "What happens next" is on every copy (`member_clock`). The numbers come from the profile's response row; each is followed by whose it is. The words in braces are slots.

> **We got it on {RECEIVED}.** We will tell you in writing that we have it within {ACK_DAYS} business days (a proposed target of the board, not a law).
>
> **Who decides.** {DECIDER} decides. An application is decided by the board at a meeting, on an agenda item, in open session; the members' agenda names the unit and the kind of change in general words, and not your name or your plans.
>
> **When.** Your procedure says we answer within **{MAX_DAYS_APPLICATION} days** of the day we receive your application ({PROCEDURE_CITATION}). {WHOSE_APPLICATION_CLOCK}. If your application is missing something we need, we tell you in writing what it is and how to supply it, and we count again from what you send.
>
> **The decision is in writing.** If we approve it, the letter says so and lists any conditions with the day each is due. If we disapprove it, the letter says **why**, and it **describes how to ask the board to reconsider**.
>
> **If you disagree.** You may ask the board to reconsider a disapproval at an open board meeting ([reconsideration form], or in your own words). The board answers within **{MAX_DAYS_RECONSIDERATION} days** of your request ({PROCEDURE_CITATION}). {WHOSE_RECONSIDERATION_CLOCK}.
>
> **If we do not answer in time.** The Civil Code does not say that silence approves a change of this kind. Your procedure says: {SILENCE_RULE}. If it says nothing, write to {BOARD_CONTACT}; the board will put your application on its next agenda and tell you the date.
>
> **Approval is not the whole story.** An approval says the change was allowed under the association's procedure. It does not say the change is safe, meets the building code, is insured, or is worth what it costs. You may want to tell your own insurer of a larger change. The association's insurance summary says: "Association members should consult with their individual insurance broker or agent for appropriate additional coverage." (Civil Code 5300(b)(9), recited).
>
> **A neighbor's name.** {NEIGHBOR_PANEL: where the documents require acknowledgment, "Your documents ask for it. It is a courtesy so your neighbors know; it is not their consent, and no one's signature decides your application."}
>
> **Not the only door.** You do not have to use this form. A letter or an email that says what you want to change and where is an application, and our time starts the day we get it.
>
> **Help.** Ask {BOARD_CONTACT} for this form in another format, in large print, or in another language, or for help filling it in. A request for a reasonable accommodation is welcome with it or on its own; it has its own form.

**The rebuild panel** (shown when `disaster_rebuild` is yes or not sure; the numbers are the statute's, and the association's, and are the same for every association):

> **If you are rebuilding after a declared disaster.** Within **30 calendar days** of the day we receive your application we tell you in writing whether it is complete or incomplete. If it is incomplete, the same letter lists the incomplete items and says how to make it complete, and you may resubmit it. If we do not tell you in time, **your application is treated as complete** (Civil Code 4766(b)(3)). Once it is complete we have **45 calendar days** to approve it or to send you, in writing, a full set of comments with a comprehensive request for revisions and a list of what is not compliant and how to fix it. If we find the application incomplete or not compliant you may appeal, and we give you a final written determination within **60 calendar days** of your written appeal. **Once we approve it, we may not subject you to any appeals or additional hearings**, except for not complying with what was approved. This is the law's rule for a rebuild; your reading of it is yours, and a lawyer can help you with it.

The last sentence is the standard's disclaimer. The panel recites 4766 first (section 5) and this note follows, labeled as the association's.

**What follows if the association does not act:** for a rebuild, the application is deemed **complete** if no timely determination is made (4766(b)(3)); 4766 states no deemed approval ([../improvement-requests.md](../improvement-requests.md#tracks)). For an ordinary application the Act states nothing; the member is told the procedure's rule or the proposed one (section 7, and the leads in section 13).

## 7. The association's clocks

Each row has a source word: **statute**, **documents**, or **PROPOSED POLICY** (the law and the documents are silent; a target until the board adopts it, `ClockSource.POLICY`). Proposed numbers are examples for the board to replace; a board that picks a slower time for an ordinary application writes down why ([../improvement-requests.md](../improvement-requests.md#where-the-documents-are-silent-policies-proposed-for-the-board)). A pause (`PauseReason.waiting_on_member`) applies only to a policy clock, only for the reasons its row lists, and is a person's record.

| Clock | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| Acknowledgment | the day received (the association's time zone) | proposed 3 business days | PROPOSED POLICY (`improvement-review-time`) | a finding for the manager; no legal effect |
| Completeness, ordinary track | the day received | proposed 15 calendar days | documents, else PROPOSED POLICY (`improvement-review-time`) | proposed: the application stands as complete on the next day (a policy the board may or may not adopt; the Act states it only for the rebuild track) |
| Decision, ordinary track | the day complete | the documents' maximum; else proposed 45 calendar days | documents (4765(a)(1) requires them to state it); PROPOSED POLICY where they state none | a finding for the board; the member is told in the "If we do not answer" paragraph. 4765 states no deemed approval |
| Notice of the board meeting that decides it | the meeting | at least four days before | statute (4920(a); general delivery, 4920(c); the notice contains the agenda, 4920(d)) | the board may not discuss or act on an item not on the agenda, except as 4930(b) to (e) allow (4930(a)) |
| Reconsideration: the member's request | the date of the written decision | proposed 30 calendar days | PROPOSED POLICY (`improvement-reconsideration`); the Act states no period for the request | a later request is accepted as a new application or at the board's discretion; counsel reads this ([reconsideration-request.md](reconsideration-request.md)) |
| Reconsideration: the board's answer | the day the request is received | the documents' maximum; else proposed: the first open meeting that can be noticed, and no later than 45 calendar days | documents (4765(a)(1)); PROPOSED POLICY where silent | a finding for the board; a special meeting is the board's choice |
| Rebuild: completeness | the day received | 30 calendar days | statute (4766(b)(1)) | deemed complete (4766(b)(3)) |
| Rebuild: resubmission | the day the resubmission is received | 30 calendar days, the same | statute (4766(b)(2)(C)(ii)) | deemed complete |
| Rebuild: review | the day the application is complete (determined or deemed) | 45 calendar days | statute (4766(c)) | no deemed approval is stated; a court "shall award reasonable attorney’s fees to the applicant who prevails" (4766(g)); counsel |
| Rebuild: appeal | the day the written appeal is received | 60 calendar days | statute (4766(e)(2)) | the same |
| The annual notice | each year | once a year | statute (4765(c)); carried by the annual policy statement | the notice catalog's `architectural-requirements` row: `jason notices` shows it open |
| Approval's lifetime: start by, finish by | the decision's date | proposed: start within a number of months, finish within a number, one extension | PROPOSED POLICY (`improvement-lifetime`) | the approval lapses; a new application is made |
| A condition's due day | the decision | the decision's own words | the board's decision | a finding for the manager: "Condition 2, due Oct 20: none on record" |

The catalog's `architectural-decision` row counts from `Anchor.APPLICATION_RECEIVED` with the words "within the maximum time the procedure states" and no number; the form's `{MAX_DAYS_APPLICATION}` is that number. The workflow design adds the anchors for "complete", "reconsideration requested", and "appeal received" ([../improvement-requests.md](../improvement-requests.md#the-clocks)); the rebuild rows need them, and the `Term` rows for 30, 45, and 60 days that the same page proposes.

## 8. The acknowledgment

Sent by the manager (a draft a person reads and sends; jason sends nothing), within the acknowledgment time. By the channel the application came in: a comment on the PayHOA request, a reply in the email thread, a letter.

> We received your request to change {UNIT_ADDRESS} on **{RECEIVED}**. Your reference is **{REFERENCE}**; please write it on anything you send us about this request.
>
> Under {PROCEDURE_CITATION}, we answer within {MAX_DAYS_APPLICATION} days of the day we received it, which is **{DUE}**. {DECIDER} decides it, at an open meeting of the board; the next meeting that can be noticed in time is {NEXT_MEETING}. We will tell you in writing what the decision is. If it is a disapproval, the letter will say why and how to ask the board to reconsider (the board answers a request within {MAX_DAYS_RECONSIDERATION} days).
>
> If we need anything else from you, we will write to say exactly what it is and how to send it. Nothing here is a decision.
>
> [Rebuild only] Because you told us this is a rebuild after a disaster, we will tell you whether your application is complete or incomplete by **{COMPLETE_DUE}**, 30 calendar days after we received it.
>
> This acknowledgment says only that we have your request and when. It is not an approval.

`{DUE}` is the due day of the decision clock, computed by the handler with its source word shown beside it ("documents" or "proposed policy, not adopted"). The acknowledgment is stored with the request and is the evidence of the day the clock started.

## 9. Channels and the reference

- **Channels:** paper (printed, filled by hand, and scanned: the form is written to be read after a scan, [../form-reader.md](../form-reader.md)); the fillable PDF; an emailed copy; the PayHOA form (an `Architectural Request` form already exists in some PayHOA accounts and is the profile's: section 10); the portal page when the portal exists. One `FormTemplate` renders every one; the paper copy and the PayHOA copy carry the same questions and the same recitals ([../forms.md](../forms.md)). A live PayHOA form that a letter, QR code, or email links to is never deleted; it gains questions through `jason forms --payhoa KEY --update` ([../forms.md](../forms.md#changing-the-payhoa-form)).
- **The marker code: `AP`** (architectural application). A blank form is the same for every owner, so the marker is a **campaign** marker (`AP27M-xx` paper, `AP27P-xx` PayHOA, where `27` is the edition's year and `xx` are the two check characters `form_refs.make` computes). A pre-filled emailed copy (the unit address filled in) takes a copy marker (`AP27E-xxxxx-xx`) because copies differ ([../form-identifiers.md](../form-identifiers.md#rules-for-a-new-marker)). The edition's year changes when the recited law, a clock, or a question changes, so an old copy is still recognized and read against its own edition.
- **Collision check.** Codes in use or proposed on 2026-10-05: `NP` (owner information, built, in the profile's forms), and, from the sibling pages already in `docs/form-templates/`, `NC` (delivery-change), `MN` (membership-list), and `RR` (records-request). `RR` is therefore not used for the reconsideration request; this page's siblings propose `RC` (reconsideration-request), `EV` (ev-charger), `PV` (solar), and `PX` (protected-use-application; `PR`, its first proposal, is the disputed-charge form's). All are two letters of the alphabet `0-9 A C E F H K M N P R T V X`, and no two are equal. The README of this folder is the register: a code is claimed there before it is used.
- **The marker is a hint.** The form is recognized by its printed lines and title and by the cited authority `CIV 4765` ([../arrivals-design.md](../arrivals-design.md)); a missing marker changes nothing but the copy. A request with no marker, or in no form, is still a request (section 12).
- **Arrival.** A returned form is cataloged, identified, and routed to the handler in section 11 by its `authority`, `CIV 4765`.

## 10. Profile slots

A community-specific copy is generated from this base, never edited by hand (AGENTS.md). The profile supplies:

| Slot | What | Where it comes from |
|---|---|---|
| `{ASSOCIATION}`, `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}`, `{BOARD_CONTACT}` | the standard slots | the profile |
| `{FEE_SCHEDULE}` | the fee the documents set, by category; empty means no fee and no `fee_ack` question | the profile's fee rows |
| `{PROCEDURE_CITATION}` | the section of the documents that holds the procedure | the `architectural-review` citation purpose |
| `{MAX_DAYS_APPLICATION}`, `{MAX_DAYS_RECONSIDERATION}`, `{ACK_DAYS}` | the numbers, each with its source word | `Community.response_rules()` for `ResponseKind.ARCHITECTURAL` (`ClockSource.DOCUMENTS` or `POLICY`) |
| `{WHOSE_APPLICATION_CLOCK}`, `{WHOSE_RECONSIDERATION_CLOCK}` | "That time is set by {section}" or "That time is a target the board proposed and has not adopted" | the same row |
| `{SILENCE_RULE}` | what the documents say if the association does not answer in time; empty if nothing | the profile's documents |
| `{CHANGE_CATEGORIES}` | the list for `change_category`, each with approval required / not required / undetermined | `Community.change_rules()` |
| `{CHECKLIST_BY_CATEGORY}` | the items `plans_attached` offers, per category | `Community.improvement_checklist(category)` |
| `{NEIGHBOR_ACK_SOURCE}` | the documents' section that asks for neighbor acknowledgment; empty means the question is not asked | the profile |
| `{SIGNERS}` | whether one owner or every owner signs | the documents; the default in section 12 |
| `{DECIDER}` | the body that decides (the board; a committee only recommends unless the documents let it decide) | the profile |
| `{NEXT_MEETING}` | the last scheduled open meeting that can be noticed in time | `MeetingSchedule` and `Community.board_notice_period()` |
| `{ANNUAL_NOTICE_LINK}` | the annual notice and its copy of the procedure | the notice ledger |

**How this form relates to the owner's existing printed application.** A community's existing application form (a printed form, a PayHOA request form, or a Doc) is **the profile's input**, not something this base replaces. The profile points at it: its questions, its checklist, its fee, and its clock. The base form is built from the profile's answers and the law, so the generated copy keeps what the documents ask and adds what the law requires of the form that the existing one may lack (the maximum times, the written-decision and reconsideration statements, the rebuild section, and the help panel). Where the existing form asks for something this page lists as not asked (a question the law bars, or one the documents do not support), the generator lists it for a person to decide; it does not drop it silently. A live form already linked from a letter, a QR code, or an email is changed in place and never replaced. The existing form's name still classifies an incoming request (`KindRule` rows on the form's name), so returns on the old form keep arriving as architectural applications.

## 11. Handler and procedure

- **Handler.** A registered form-return handler for `CIV 4765`: `@handler("CIV 4765", role=Role.FORM_RETURN, form="architectural-application", procedure="improvement-request", channels=(PAYHOA, GMAIL, MAIL, FORMS))`, with `accepts` (the form key or the cited authority), `read` (an `ImprovementRequest` draft, evidence and never an answer), and `plan` (the clocks and the checklist result, no write). A second registration `@handler("CIV 4766", role=Role.REQUEST, procedure="improvement-request")` takes a rebuild arriving in words with no form. The generators refuse a marker for this form until both are registered ([../arrivals-design.md](../arrivals-design.md#the-handler-is-chosen-when-the-form-is-made)).
- **Procedure key: `improvement-request`.** It does not exist in `src/jason/community/procedures.py`; the existing `respond` procedure answers requests on their clocks but has no application workflow. Add it with the steps of [../improvement-requests.md](../improvement-requests.md#the-workflow-as-states): (1) receive and enter the request, set its received day, and acknowledge (a draft a person sends); (2) ask whether the documents require approval, with the `ChangeRule` rows (undetermined is a question for the board, never "not required"); (3) read the checklist and sign a determination of complete or incomplete (a person's word; jason lists what is present and missing, a lead); (4) review: a person's record; (5) put it on a noticed agenda (`jason board`); (6) after the board's recorded vote, render the decision letter from the base template `architectural-decision`, checked by `notice_elements`, and a person sends it and records where and when; (7) a written request for reconsideration moves it to "reconsideration" ([reconsideration-request.md](reconsideration-request.md)); (8) conditions, work, verification, and the link to the unit's record; (9) each January, the annual notice (`architectural-requirements`) and the review of this form's recitals (`jason sop law-review`). Name the lessons on the steps they change.
- **`respond` gains one step:** "an architectural, charger, solar, or protected-use request is entered as an `ImprovementRequest` and run by `improvement-request`; the weekly pass reads only its due day."
- **`ResponseKind` additions proposed:** `RECONSIDERATION`, `EV_METER`, `PROTECTED_USE`, `DISASTER_REBUILD`. `ARCHITECTURAL` exists (`responses.py`) with a `KindRule` on the form name `Architectural Request`; `RESPONSE_RULES` has no row for it (a profile supplies it), which is why `{MAX_DAYS_APPLICATION}` comes from the profile.
- **jason never** approves, denies, or assigns the request. "Decided" exists only when a board decision record exists, recorded by an officer ([../improvement-requests.md](../improvement-requests.md#rules-the-states-keep)).

## 12. Edge cases

| Case | What the form and the handler do |
|---|---|
| **Co-owners** | One owner may submit for all unless `{SIGNERS}` says every owner signs. The decision is addressed to every owner of record. If co-owners disagree about the change, the association records what it received and decides on the application; it does not decide between owners. |
| **A representative** (an agent, a person with power of attorney) | The form accepts a representative who attaches the owner's written authorization (`rep_authorization`). The decision goes to the owner, with a copy to the representative the owner named; PayHOA's legal-representative record under 4041(a)(3) is a hint, not the authorization. Without it the submission is still received and the clock starts for the acknowledgment; the missing authorization is listed as an incomplete item by a person. |
| **A tenant asking** | A tenant is not the member. The tenant's request is answered with how the owner applies, and the form is not asked for the tenant's name or lease terms (nothing in this form asks whether a unit is rented). Where the documents let a resident ask for a minor change, the profile says so and the owner's signature is replaced by the documents' rule. |
| **A contractor submitting for an owner** | A contractor may send the form with the owner's signature or authorization. A submission without either is received, the acknowledgment says so, and the manager lists "owner's signature" as the missing item; the decision is never addressed to a contractor alone. A counsel lead asks whether a missing signature is an incomplete item on the rebuild track (4766(b)(2)(B) limits the items to those the documents identified). |
| **A change the unit's insurer must see** | The form carries no coverage advice. The panel repeats the statute's insurance sentence (section 6) and no more. The association's decision says only that the change was allowed; it does not say what the owner's insurer covers. A change touching structure or a component the association insures is named in the reviewer's notes, not decided by the form. |
| **A request that is really a variance** | An application that asks to be excused from a standard rather than to meet it ("I know the rule says X; I want Y") is still an application and its clock runs from the day received. The manager notes it and puts it before the board as a decision on a proposed change; where the documents provide a variance procedure and its own hearing, the profile's variance form is offered beside it, never instead. Whether the 4765 clocks or the documents' variance clocks govern is a question for counsel (section 13). |
| **It arrives without the form** | It is a request. The manager enters it with its received day; the form is sent as help, not as a condition; "incomplete" is judged only against the checklist in force on the received day. A PayHOA general request, an email, or a letter all count. |
| **Language and accessibility** | The form is written at about an eighth-grade level. Another format, large print, translation, and help filling it in are on the form (`help_needed`). The paper form is readable on a scan. A reasonable accommodation request is welcome with it or alone and has its own form ([../standard-forms.md](../standard-forms.md)); 4765(a)(3) names the Fair Employment and Housing Act, which the shelf does not hold, so it is a pointer. |
| **A change inside the unit only** | It may be outside 4765 entirely ([../improvement-requests.md](../improvement-requests.md#open-decisions)). The answer is "approval not required" or "undetermined" with the missing fact, never a denial. |
| **A rebuild that may not qualify** | The member says rebuild; the application may not meet 4752(c)(3). The handler runs the 4766 clocks while it asks counsel whether the application is a "substantially similar reconstruction": the course lawful under either reading. |
| **A resubmission or an amendment** | A rebuild resubmission is judged against the items listed, within the 30-day clock again (4766(b)(2)(C)). For an ordinary application a material change to the plans is a new received day for the changed part, a proposed policy, recorded with both days. |
| **An owner who is a director** | Recorded as recused by the secretary on the director's disclosure; jason infers none ([../improvement-requests.md](../improvement-requests.md#the-board-stage)). |
| **Work already begun** | The form does not ask. A finding of work without an approval goes through the `improvement-unapproved-work` policy: the first step is a question to the owner, never a notice. |
| **Two changes in one letter** | One application per change if they go to different deciders or tracks; otherwise one, each change listed. The form allows one `change_what`; the manager splits. |

## 13. Leads for the board and counsel

Each is a reading, labeled, or an open question. Where a conflict could exist it is **noted, not resolved**: only the board, counsel, or an amendment resolves one, and a `Conflict` row is made only where both provisions cannot be obeyed.

1. **No maximum time.** *jason's reading (a), reused:* 4765(a)(1) requires the procedure to state a maximum time. Where the documents state none, the statute is unmet by the documents, not silent. The board's route is a written rule on subject 4355(a)(6) ("Any procedures for reviewing and approving or disapproving a proposed physical change to a member’s separate interest or to the common area."), adopted with general notice at least 28 days before the board makes the rule change (4360(a)). The proposed numbers in section 7 become the documents' or the board's only by that route. Until then the form says "proposed, not adopted".
2. **Silence.** 4765 states no deemed approval for an ordinary application. Three courses are the board's, not jason's: the Act's silence stands; a written rule that an application not decided within the maximum time is treated as approved; a written rule that it goes to the next agenda automatically. A written rule on this is an operating rule within 4350 (in writing, within the board's authority, not in conflict with governing law, adopted in good faith, reasonable) and a subject within 4355(a)(6). Counsel reads whether a rule can make silence an approval.
3. **Reconsideration of a decision the board itself made.** *jason's reading (b):* 4765(a)(4) asks the written disapproval to describe the reconsideration procedure, while (a)(5) says reconsideration is not required of a decision made by the board "at a meeting that satisfies the requirements of Article 2". Read to give each effect, the letter describes the procedure the association has, which may be a written request for the board to reconsider at its next open meeting. Whether a decision made at a qualifying meeting needs any procedure is a second reading. Two readings remain; the board asks counsel. This form offers reconsideration either way.
4. **The 4766 text is dense.** Four readings to put to counsel: (i) 4766(c) starts its 45 days "Once an application is deemed complete": whether that includes an application the body has determined complete, or only one deemed complete by default; the form runs 45 days from complete either way. (ii) 4766(d)(1) says the list and description say how the application "can be remedied by the applicant within the time limits specified in subdivision (b)", and (d)(2) says they are provided "when it transmits its determination ... as required by subdivision (b)": subdivision (b) states times for the body, not the applicant. (iii) 4766(h)(1) makes a committee a "body": a committee's determination is the association's for these clocks. (iv) 4766(b)(2)(B) bars requiring an item "not identified as necessary" in the documents "in effect at the time the application was originally submitted": the rebuild checklist is frozen on the received day and the form's rebuild fact questions are optional. 4766(g) makes attorney's fees mandatory for a prevailing applicant, which is why the form takes the conservative course.
5. **Does "no appeals after approval" reach an ordinary approval?** 4766(f)(1) is stated for a rebuild. For an ordinary approval the Act says nothing. *Proposed policy `improvement-finality` (new; not in the workflow page):* an approval, once given, is not reopened on another member's request, except for noncompliance with the approval or a material misstatement in the application; the board decides whether to adopt it, and counsel reads what the documents allow. Until adopted the form says nothing about it.
6. **Neighbor acknowledgment.** The Act does not mention it. 4765(a)(2) bars a decision that is "unreasonable, arbitrary, or capricious", and 4765(a)(3) bars one that violates "any governing provision of law". A neighbor's refusal to sign is not a standard in the Act. *jason's reading:* a law may not make the acknowledgment a condition where the statute lists what the applicant must agree to (4745(f)(1), 4746(a), 714.1) or limits what the body may require (4766(b)(2)(B)); for an ordinary application, whether the documents may make it a condition is for counsel. The form therefore shows it only where the documents require it, labels it a courtesy, says it is awareness and not consent (proposed `improvement-neighbors`), and never makes an unsigned line a reason for "incomplete" without a person's reading. Whether the acknowledgment stays on the application is an open decision (workflow page, decision 10).
7. **Fee.** The documents set it. Whether an association may charge a fee for an application the law requires it to process on a clock is not stated in the Act; the form shows only what the documents set. For the charger, solar, and rebuild tracks the lead is in those pages and in counsel's hands; a fee for a rebuild application is not mentioned in 4766 at all.
8. **Accessibility modifications.** 4760(a)(2)(D): "The association shall not deny approval of the proposed modifications under this paragraph without good cause." That is a standard, and it is not a clock. The form asks for the purpose of the change and not for who or what the condition is. Whether a request for a ramp is an accessibility modification or an architectural change is a person's reading; the track can be corrected.
9. **The form is not a governing document.** 4765(a)(1) says the procedure "shall be included in the association’s governing documents". If a printed application states times different from the documents', the documents govern (4205(a) and (d) put the law above the documents and the declaration above the operating rules; the form is below all of them). The generator therefore reads the numbers from the documents and refuses a form whose numbers differ from the procedure row (a test, section 14). The form is "Issuance of a document that merely repeats existing law or the governing documents" within 4355(b)(5) only so far as it repeats; a proposed policy on it is a rule.
10. **Open board decisions that remain** ([../improvement-requests.md](../improvement-requests.md#open-decisions)): which changes the documents require approval for; the maximum times and the route; whether a board's own decision needs a reconsideration procedure at all; delegation and pre-approved categories; whether a request and its plans are association records a member may inspect; whether an owner's shared entry may start a lead; and the form's neighbor acknowledgment.
11. **Statutes this page points at and the shelf does not hold:** Government Code 12900 and following (the Fair Employment and Housing Act), Government Code 8625 and 8630 (the disaster declarations), and the local building code. They are pointers, not recitals.
12. **Day counting.** The Act's periods say "calendar days" only in 4766; the others say "days". The shelf does not hold the Code of Civil Procedure's rule for counting a period (CCP 12 is not on the shelf), so a due day is computed as received day plus the number, delivery of the written decision by that day, and counsel confirms the counting.
13. **Where the documents say "sole discretion".** *jason's reading (c), reused:* the board alone decides, and decides in good faith and not arbitrarily (4765(a)(2)); both can be obeyed, so it is not a `Conflict` row. Counsel may read it differently.

## 14. Test fixtures

Made-up answers; the unit is "123 Main St"; the owner is "A. Owner". Fixtures live with the others under `tests/fixtures/` when the form is built; none is a real person's.

**Typical.**

| key | answer |
|---|---|
| `unit` | 123 Main St |
| `owner_name` | A. Owner |
| `submitted_by` | the owner |
| `decision_delivery` | by mail to the unit |
| `change_category` | replace a rear patio door |
| `change_what` | Replace the rear sliding patio door with a new sliding door of the same size and the same color frame. |
| `change_where` | outside my unit |
| `change_location_detail` | rear patio, east wall |
| `replaces` | the existing patio door |
| `like_for_like` | the same as what is there |
| `plans_attached` | drawings to scale; product sheets |
| `contractor_name` / `contractor_license` | Example Doors Inc. / 000000 |
| `contractor_insurance` | attached |
| `permit_needed` | no |
| `start_date` / `finish_date` | 2026-11-15 / 2026-11-20 |
| `accessibility` / `disaster_rebuild` | unchecked / no |
| signature / date | A. Owner / 2026-10-12 |

**Minimal** (a letter in the owner's own words with no form): `unit` 123 Main St, and the text "I would like to repaint my front door a darker green. A. Owner." No other answers. The handler enters it with the day received; the acknowledgment goes out; the checklist result lists the items the documents' checklist would need (a color sample, the product); the determination is a person's.

**Edge** (rebuild with co-owners and a representative): `unit` 123 Main St; `owner_name` A. Owner and B. Owner; `submitted_by` an authorized representative with `rep_authorization` attached; `disaster_rebuild` yes; `disaster_declared_by` a local government; `rebuild_old_sqft` 1,800; `rebuild_new_sqft` 1,900; `rebuild_height` the same; `rebuild_footprint` the same place and size; `rebuild_permit` applied for; `decision_delivery` by email with `contact_email` owner@example.com; `help_needed` checked (large print). Expected: the rebuild panel is shown; the 30-calendar-day completeness clock starts on the received day; the 45-day and 60-day clocks are computed and shown; the checklist is the documents' items as of the received day; the large-print copy is queued; the decision is addressed to both owners and copied to the representative.

**The statutory checklist test, in words.** For each profile, the generated form passes when all of these hold:

1. It states a maximum time for response to an application and a maximum time for response to a request for reconsideration, each with its source word, and each equal to the profile's procedure row; the build fails with the missing row named if either is absent (4765(a)(1)).
2. It says the decision will be in writing; that a disapproval will carry an explanation and a description of the reconsideration procedure; and that the applicant may ask the board to reconsider at an open meeting (4765(a)(4), (a)(5)). The decision template's required elements (`architectural-decision`, checked by `notice_elements`) contain both parts.
3. It carries the rebuild section with the 30, 45, and 60 calendar-day periods, the list-of-incomplete-items promise, the appeal, and the end of appeals once approved (4766(b), (c), (d), (e), (f)); it does not require a rebuild fact to start the clocks.
4. It recites the tokens of section 5; each resolves against the shelf; a subdivision that has moved fails the build (the recital-freshness test).
5. Every question has a `why`; none asks a person's disability, a tenant's name, or an email address unless delivery by email is chosen; `neighbor_ack` is absent when `{NEIGHBOR_ACK_SOURCE}` is empty and never required when present; `fee_ack` is absent when `{FEE_SCHEDULE}` is empty.
6. It carries the help panel and the sentence that a request in other words is still a request.
7. It carries a pointer to the annual notice (4765(c)); the annual-notice requirement stays open in `jason notices` until the notice is sent.
8. The marker `AP` round-trips (`form_refs.make` and `parse`), and `jason form-fuzz --lint` finds the marker's two places clear on every page.
9. The scan test: made-up returns of the paper form, scanned badly ([../form-fuzzer.md](../form-fuzzer.md)), are recognized (campaign `AP`) and read with the answers above; none is recognized as another form.
10. The generated form names its handler and procedure; a form with no registered handler is refused, and the refusal says what is missing.
