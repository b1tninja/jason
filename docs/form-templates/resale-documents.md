# Request for the documents for the sale of a unit

Status: design (2026-10-05); the request is built in the library as version 1 (2026-10-05, build step 2A: `src/jason/community/form_library/ca/resale.py`, which records its departures from this page); the 4528 billing disclosure is the handler's output and is not built yet. Key `resale-documents`; proposed marker code `RT`. It follows the standard in [form-templates.md](../form-templates.md). The inventory row is "Resale documents" ([standard-forms.md](../standard-forms.md)); the notice catalog row is `resale-documents` (CIV 4530). This page covers two documents: the **request** (this form, from the owner or the owner’s agent) and the **billing disclosure** the association gives back, whose layout CIV 4528 prescribes. The second is not a form the member fills; it is a statutory form the association completes, and it is designed here because the law says what it must contain.

## 1. Authority and what the law requires

As of: the shelf’s 2025 session publication of the code (`data/authorities/CIV/CIV-4525-4545.md` and `CIV-4575-4580.md`, read with lawlibrary, 2026-10-05). Sections 4525 and 4528 were amended by Stats. 2025, Ch. 516 (SB 410), operative 2026-01-01, so the text below is in force. jason’s copy is not an official restatement; the official page controls.

**CIV 4525** (the documents):

> (a) The owner of a separate interest shall provide the following documents to a prospective purchaser of the separate interest, as soon as practicable before the transfer of title or the execution of a real property sales contract, as defined in Section 2985:
>
> (1) A copy of all governing documents. If the association is not incorporated, this shall include a statement in writing from an authorized representative of the association that the association is not incorporated.
>
> (2) If there is a restriction in the governing documents limiting the occupancy, residency, or use of a separate interest on the basis of age in a manner different from that provided in Section 51.3, a statement that the restriction is only enforceable to the extent permitted by Section 51.3 and a statement specifying the applicable provisions of Section 51.3.
>
> (3) A copy of the most recent documents distributed pursuant to Article 7 (commencing with Section 5300) of Chapter 6.
>
> (4) A true statement in writing obtained from an authorized representative of the association as to the amount of the association’s current regular and special assessments and fees, any assessments levied upon the owner’s interest in the common interest development that are unpaid on the date of the statement, and any monetary fines or penalties levied upon the owner’s interest and unpaid on the date of the statement. The statement obtained from an authorized representative shall also include true information on late charges, interest, and costs of collection which, as of the date of the statement, are or may be made a lien upon the owner’s interest in a common interest development pursuant to Article 2 (commencing with Section 5650) of Chapter 8.
>
> (5) A copy or a summary of any notice previously sent to the owner pursuant to Section 5855 that sets forth any alleged violation of the governing documents that remains unresolved at the time of the request. The notice shall not be deemed a waiver of the association’s right to enforce the governing documents against the owner or the prospective purchaser of the separate interest with respect to any violation. This paragraph shall not be construed to require an association to inspect an owner’s separate interest.
>
> (6) A copy of the initial list of defects provided to each member pursuant to Section 6000, unless the association and the builder subsequently enter into a settlement agreement or otherwise resolve the matter and the association complies with Section 6100. Disclosure of the initial list of defects pursuant to this paragraph does not waive any privilege attached to the document. The initial list of defects shall also include a statement that a final determination as to whether the list of defects is accurate and complete has not been made.
>
> (7) A copy of the latest information provided for in Section 6100.
>
> (8) Any change in the association’s current regular and special assessments and fees which have been approved by the board, but have not become due and payable as of the date disclosure is provided pursuant to this subdivision.
>
> (9) If there is a provision in the governing documents that prohibits the rental or leasing of any of the separate interests in the common interest development to a renter, lessee, or tenant, a statement describing the prohibition.
>
> (10) If requested by the prospective purchaser, a copy of the minutes of board meetings, excluding meetings held in executive session, conducted over the previous 12 months, that were approved by the board.
>
> (11) A copy of the report issued pursuant to the most recent inspection conducted pursuant to Section 5551.
>
> (b) This section does not apply to an owner that is subject to Section 11018.6 of the Business and Professions Code.

**CIV 4528** (the billing disclosure form: its type size, and its required content). The first sentence:

> The form for billing disclosures required by Section 4530 shall be in at least 10-point type and substantially the following form:

The form, as the shelf states it (the shelf flattens a table; the words and the citations are exact, and the column order is checked against the official page when the form is built):

> CHARGES FOR DOCUMENTS PROVIDED AS REQUIRED BY SECTION 4525*
>
> The seller may, in accordance with Section 4530 of the Civil Code, provide to the prospective purchaser, at no cost, current copies of any documents specified by Section 4525 that are in the possession of the seller.
>
> A seller may request to purchase some or all of these documents, but shall not be required to purchase ALL of the documents listed on this form.
>
> Property Address
>
> Owner of Property
>
> Owner’s Mailing Address (If known or different from property address.)
>
> Provider of the Section 4525 Items:
>
> Print Name _________ Position or Title _________ Association or Agent
>
> Date Form Completed
>
> Check or Complete Applicable Column or Columns Below
>
> Columns: “Not Available (N/A), Not Applicable (N/App), or Directly Provided by Seller and confirmed in writing by Seller as a current document (DP)”; “Document”; “Civil Code Section”; “Included”; “Fee for Document”.

| Document | Civil Code Section |
|---|---|
| Articles of Incorporation or statement that not incorporated | Section 4525(a)(1) |
| CC&Rs | Section 4525(a)(1) |
| Bylaws | Section 4525(a)(1) |
| Operating Rules | Section 4525(a)(1) |
| Age restrictions, if any | Section 4525(a)(2) |
| Rental restrictions, if any | Section 4525(a)(9) |
| Annual budget report or summary, including reserve study | Sections 5300 and 4525(a)(3) |
| Assessment and reserve funding disclosure summary | Sections 5300 and 4525(a)(4) |
| Financial statement review | Sections 5305 and 4525(a)(3) |
| Assessment enforcement policy | Sections 5310 and 4525(a)(4) |
| Insurance summary | Sections 5300 and 4525(a)(3) |
| Regular assessment | Section 4525(a)(4) |
| Special assessment | Section 4525(a)(4) |
| Emergency assessment | Section 4525(a)(4) |
| Other unpaid obligations of seller | Sections 5675 and 4525(a)(4) |
| Approved changes to assessments | Sections 5300 and 4525(a)(4), (8) |
| Settlement notice regarding common area defects | Sections 4525(a)(6), (7), and 6100 |
| Preliminary list of defects | Sections 4525(a)(6), 6000, and 6100 |
| Notice(s) of violation | Sections 5855 and 4525(a)(5) |
| Required statement of fees | Section 4525 |
| Minutes of regular board meetings conducted over the previous 12 months, if requested | Section 4525(a)(10) |
| Copy of the report issued pursuant to the most recent inspection of exterior elevated elements | Sections 4525(a)(11) and 5551 |

> Total fees for these documents:
>
> * The information provided by this form may not include all fees that may be imposed before the close of escrow. Additional fees that are not related to the requirements of Section 4525 shall be charged separately.

**CIV 4530** (the request, the clock, the fee, the estimate, the form):

> (a) (1) Upon written request, the association shall, within 10 days of the mailing or delivery of the request, provide the owner of a separate interest, or any other recipient authorized by the owner, with a copy of all of the requested documents specified in Section 4525.
>
> (2) The documents required to be made available pursuant to this section may be maintained in electronic form, and may be posted on the association’s Internet Web site. Requesting parties shall have the option of receiving the documents by electronic transmission if the association maintains the documents in electronic form.
>
> (3) Delivery of the documents required by this section shall not be withheld for any reason nor subject to any condition except the payment of the fee authorized pursuant to subdivision (b).
>
> (b) (1) The association may collect a reasonable fee from the seller based upon the association’s actual cost for the procurement, preparation, reproduction, and delivery of the documents requested pursuant to this section. An additional fee shall not be charged for the electronic delivery in lieu of a hard copy delivery of the documents requested.
>
> (2) Upon receipt of a written request, the association shall provide, on the form described in Section 4528, a written or electronic estimate of the fees that will be assessed for providing the requested documents prior to processing the request in paragraph (1) of subdivision (a).
>
> (3) (A) A cancellation fee for documents specified in subdivision (a) shall not be collected if either of the following applies: (i) The request was canceled in writing by the same party that placed the order and work had not yet been performed on the order. (ii) The request was canceled in writing and any work that had been performed on the order was compensated.
>
> (B) The association shall refund all fees collected pursuant to paragraph (1) if the request was canceled in writing and work had not yet been performed on the order.
>
> (C) If the request was canceled in writing, the association shall refund the share of fees collected pursuant to paragraph (1) that represents the portion of the work not performed on the order.
>
> (4) Fees for any documents required by this section shall be distinguished from, separately stated, and separately billed from, all other fees, fines, or assessments billed as part of the transfer or sales transaction.
>
> (5) Any documents not expressly required by Section 4525 to be provided to a prospective purchaser by the seller shall not be included in the document disclosure required by this section. Bundling of documents required to be provided pursuant to this section with other documents relating to the transaction is prohibited.
>
> (6) A seller shall provide to the prospective purchaser, at no cost, current copies of any documents specified by Section 4525 that are in the possession of the seller.
>
> (7) The fee for each document provided to the seller for the purpose of transmission to the prospective purchaser shall be individually itemized in the statement required to be provided by the seller to the prospective purchaser.
>
> (8) It is the responsibility of the seller to compensate the association, person, or entity that provides the documents required to be provided by Section 4525 to the prospective purchaser.
>
> (c) An association may contract with any person or entity to facilitate compliance with this section on behalf of the association.
>
> (d) The association shall also provide a recipient authorized by the owner of a separate interest with a copy of the completed form specified in Section 4528 at the time the required documents are delivered. A seller may request to purchase some or all of these documents, but shall not be required to purchase all of the documents listed on the form specified in Section 4528.

**CIV 4575** (the fee limit on any other charge for a transfer):

> Except as provided in Section 4580, neither an association nor a community service organization or similar entity may impose or collect any assessment, penalty, or fee in connection with a transfer of title or any other interest except for the following: (a) An amount not to exceed the association’s actual costs to change its records. (b) An amount authorized by Section 4530.

**CIV 4540** (what follows a willful violation):

> Any person who willfully violates this article is liable to the purchaser of a separate interest that is subject to this section for actual damages occasioned thereby and, in addition, shall pay a civil penalty in an amount not to exceed five hundred dollars ($500). In an action to enforce this liability, the prevailing party shall be awarded reasonable attorney’s fees.

Cited, not recited: CIV 4535 (an owner transferring title “shall comply with applicable requirements of Sections 1133 and 1134”; those sections are not on the shelf), 4545 (title is not affected), 4580 (the exceptions to 4575 for certain organizations).

**What the law does not say** (leads in section 13): what the written request must contain (4530(a)(1) says only “Upon written request”); whether “10 days” are calendar or business days; whether the owner’s authorization of another recipient must be in writing; who may ask for the estimate; whether a refinance is a transfer; the refund time under 4530(b)(3).

## 2. Who uses it, and when

- **The owner of the separate interest (the seller)**, when the unit is to be sold or a sales contract is to be signed. The documents are the owner’s to give the buyer “as soon as practicable before the transfer of title or the execution of a real property sales contract” (4525(a)).
- **A person the owner authorizes**: an escrow officer, a real estate agent, a title company, an attorney. The statute says the association provides the documents to “the owner of a separate interest, or any other recipient authorized by the owner” (4530(a)(1)).
- When: any time the owner begins a sale. A request is the form’s clock, so the owner should be told on the form to ask early.
- Not served: a prospective purchaser without the owner’s authorization (4530(a)(1) names the owner and the owner’s authorized recipient; reading, section 13); a member who wants records for another reason ([records-request.md](records-request.md)).

## 3. What the form must carry

The request form (the owner’s side) and the 4528 billing disclosure (the association’s side) are two checklists.

**The request** (law says only “written request”; the items are the form’s design, each tied to why it is needed):

| # | What it carries | Authority | Carried by |
|---|---|---|---|
| 1 | A written request | 4530(a)(1) | the form; signature |
| 2 | Which separate interest | 4528 header “Property Address” | `property-address` |
| 3 | The owner of the property | 4528 header “Owner of Property” | `owner-name` |
| 4 | Who is asking, and whether the owner authorized them | 4530(a)(1) “any other recipient authorized by the owner” | `requester-role`, `authorization` |
| 5 | The documents asked for: “some or all”, never forced to take all | 4528; 4530(d) | `documents` |
| 6 | The documents the seller already has and will provide directly | 4528 “Directly Provided by Seller ... (DP)”; 4530(b)(6) | `seller-provides` |
| 7 | The date the request was mailed or delivered | 4530(a)(1) “within 10 days of the mailing or delivery of the request” | `date-sent` |
| 8 | Where the estimate and the documents are to go; electronic is an option | 4530(a)(2), (b)(2) | `recipient-name`, `delivery`, `email`, `mailing-address` |
| 9 | Nothing outside 4525 is asked for or bundled | 4530(b)(5) | no “other documents” option anywhere on the form; fixed text |
| 10 | The seller is the one billed, and pays | 4530(b)(1), (8) | fixed text “What it costs” |
| 11 | Cancellation in writing | 4530(b)(3) | `action`, `cancel-reference` |
| 12 | A request in other words is still a request; help | standard 5 | fixed text |

**The billing disclosure** (CIV 4528; the layout is a `DocumentTemplate` row, not a member form; the test reads this list):

| # | Required content | Authority | Carried by |
|---|---|---|---|
| B1 | “at least 10-point type” | 4528 first sentence | the render: every run at 10 points or larger, in every output |
| B2 | “substantially the following form”: the title line “CHARGES FOR DOCUMENTS PROVIDED AS REQUIRED BY SECTION 4525*” | 4528 | the heading, with its asterisk note |
| B3 | The two sentences about the seller providing documents at no cost and not being required to buy all | 4528 | fixed text, word for word |
| B4 | Property Address; Owner of Property; Owner’s Mailing Address (if known or different) | 4528 | filled from the request and the books |
| B5 | Provider of the Section 4525 Items: Print Name, Position or Title, Association or Agent | 4528 | filled by the handler’s person |
| B6 | Date Form Completed | 4528 | filled |
| B7 | The 22 document rows, each with its Civil Code section, and a column for included, fee, and the N/A, N/App, DP choice | 4528 | the rows, in the order the section states them |
| B8 | “Total fees for these documents:” | 4528 | the sum of the itemized fees |
| B9 | The asterisk note: “The information provided by this form may not include all fees that may be imposed before the close of escrow. Additional fees that are not related to the requirements of Section 4525 shall be charged separately.” | 4528 | fixed text, word for word |
| B10 | Each fee itemized and separately stated and billed | 4530(b)(4), (7) | one fee per row; the total is not a bundle |
| B11 | The estimate goes out on this form before processing; the completed form goes with the documents | 4530(b)(2), (d) | two stages of the same document: `estimate`, `completed` |

## 4. The questions

Kinds: text, choice, checkbox, email, phone, address, paragraph, date.

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `action` | What do you want to do? | choice: “Ask for the documents”; “Cancel a request I made” | yes | 4530(a)(1); 4530(b)(3) | TEXT | request.action |
| `requester-name` | Your name | text | yes | who asks | NAME | request.requester |
| `requester-role` | You are | choice: “The owner of the unit”; “A person the owner has authorized (agent, escrow, title, attorney)” | yes | 4530(a)(1) | TEXT | request.role |
| `owner-name` | Owner of the property | text | yes | 4528 header | NAME | request.owner |
| `property-address` | Property address (the unit) | address | yes | 4528 header; places the separate interest | ADDRESS | request.unit |
| `owner-mailing` | Owner’s mailing address, if different from the property | address | no | 4528 header “If known or different” | ADDRESS | request.owner_mail |
| `authorization` | The owner authorizes the person named above to receive the estimate and the documents | checkbox (one box) | only if `requester-role` is the authorized person | 4530(a)(1), (d) | TEXT | request.authorized = present |
| `authorization-signature` | Owner’s name, typed or signed, and date | text | only if `requester-role` is the authorized person | 4530(a)(1); reading in section 13 | NAME | request.authorized_by, with date |
| `documents` | Which documents do you ask for? (tick any) | checkbox: the 22 rows of the 4528 table, by their names | yes (at least one) | 4528; 4530(d) | TEXT | request.documents |
| `seller-provides` | Which of these do you already have as current copies and will provide directly? | checkbox: the same 22 | no | 4528 “DP”; 4530(b)(6) | TEXT | request.seller_provides |
| `date-sent` | The date you mailed or delivered this request | date | yes | 4530(a)(1): the clock counts from it | TEXT | request.sent |
| `recipient-name` | Send the estimate and the documents to (name) | text | yes | 4530(a)(1), (b)(2) | NAME | request.recipient |
| `delivery` | How should they reach that person? | choice: “By electronic transmission”; “By mail”; “I will collect them” | yes | 4530(a)(2) | TEXT | request.delivery |
| `email` | Email address | email | only if `delivery` is electronic | 4530(a)(2); 4041(b)(2)(A) | EMAIL | request.email (on the request only) |
| `mailing-address` | Mailing address | address | only if `delivery` is mail | 4040(a) | ADDRESS | request.mail_to |
| `cancel-reference` | The reference printed on the request you want to cancel | text | only if `action` is cancel | 4530(b)(3): “canceled in writing by the same party that placed the order” | TEXT | request.cancels |
| (signature) | Signature and date | signature line, date | yes | 4530(a)(1): a written request | NAME | request.signed |

Not asked, on purpose: the buyer’s name, the price, the close-of-escrow date, whether the sale is for money (none of these changes what 4525 requires); a payoff or lien-demand amount (not in 4525; a separate request); any “other documents” (4530(b)(5)); a fee, deposit, or payment before the estimate (4530(a)(3): “shall not be withheld for any reason nor subject to any condition except the payment of the fee”).

## 5. The recitals

| Token | Subdivisions | Why it opens the form |
|---|---|---|
| `{QUOTE:CIV 4525(a)}` | (a)(1) to (11) | what the owner must give the buyer |
| `{QUOTE:CIV 4530(a)}` | (a)(1) to (3) | the request, the 10 days, no conditions |
| `{QUOTE:CIV 4530(b)}` | (b)(1), (2), (4), (5), (8) | the fee, the estimate, separate billing, no bundling |
| `{QUOTE:CIV 4530(d)}` | (d) | the completed form goes with the documents |
| `{QUOTE:CIV 4528}` | the whole section | the billing disclosure form, which the association gives back |
| `{QUOTE:CIV 4575}` | the whole section | the limit on any other transfer charge |

## 6. What the member is told

> We will send you a written estimate of the fees for the documents you ask for, on the form set by Civil Code 4528, before we start the work. We will give the owner, or the person the owner authorizes, the documents you ask for within 10 days of the day the request was mailed or delivered (Civil Code 4530(a)(1)). We may not hold the documents back for any reason or condition except the fee (4530(a)(3)). The seller is billed the association’s actual cost for getting, preparing, copying, and sending the documents; there is no extra fee for receiving them electronically (4530(b)(1)). Any other charge for the transfer is limited by Civil Code 4575 and is billed separately (4530(b)(4)). You may ask for some of the documents and not all (4530(d)). You may cancel in writing: if no work has been done there is no fee and any fee paid is refunded; if work was done, you pay for what was done (4530(b)(3)). {DECIDER} handles your request. If you disagree with a fee, ask {BOARD_CONTACT} in writing; you may also ask to meet and confer (Civil Code 5900 to 5920).

The owner is also told, in the form’s plain-words note, that the owner’s duty is to give the buyer the documents “as soon as practicable before the transfer of title” (4525(a)) and to give them at no cost any current copies the owner already has (4530(b)(6)). Reading (the association’s, a plain-words note, not advice): “10 days” are counted as calendar days from the mailing or delivery date the owner writes.

## 7. The association's clocks

| # | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| 1 | receipt (and the `date-sent`) | acknowledge within 2 business days | PROPOSED POLICY | none in the law; the owner has no date |
| 2 | receipt of the written request | the estimate on the form of 4528, “prior to processing”: within 2 business days, so the 10-day clock still allows delivery | PROPOSED POLICY (the law sets no number: 4530(b)(2)) | processing may not start without it; the 10-day clock keeps running |
| 3 | the mailing or delivery of the request | the documents: “within 10 days of the mailing or delivery of the request” (read as calendar days; label: reading) | statute: 4530(a)(1) | the owner may bring an action; “Any person who willfully violates this article” is liable for actual damages and a civil penalty up to $500, and the prevailing party recovers fees (4540) |
| 4 | delivery of the documents | the completed 4528 form goes “at the time the required documents are delivered” | statute: 4530(d) | as row 3 |
| 5 | a written cancellation | refund of all fees if no work was done; of the unworked share otherwise: PROPOSED: within 10 business days | statute (the duty: 4530(b)(3)(B), (C)); PROPOSED POLICY (the time) | the association keeps money the law says it refund |
| 6 | the request | the documents are kept in electronic form where the association can (4530(a)(2)); no clock | statute | none |
| 7 | the sale | the owner’s duty to give the buyer the documents is “as soon as practicable before the transfer of title”: the owner’s, not the association’s | statute: 4525(a) | for the owner |

A request that arrives on day 8 of a sale does not change row 3. The association’s only discretion is how to meet the clock, not whether.

## 8. The acknowledgment text

> Reference {REFERENCE}. We received your request for the documents for the sale of {PROPERTY} on {RECEIVED}. We will send the estimate of fees on the form set by Civil Code 4528 first. The documents are due within 10 days of {SENT}, by {DUE}. {DECIDER} will deliver them to the owner or to the person the owner authorizes. If you want to cancel, write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.

`{SENT}` is the date the requester wrote (`date-sent`), or the postmark or delivery date the handler can verify; `{DUE}` is `{SENT}` plus 10 days.

## 9. Channels and the reference

- **Channels:** paper, fillable PDF, email, PayHOA (a signed-in owner), portal. Most requests arrive from an escrow officer or an agent, so the usual channel is email or the association’s portal, with the owner’s authorization attached; a PayHOA request is the strongest proof of who the owner is.
- **Marker code proposed: `RT`** (resale transfer). It collides with no code found. The estimate and the completed 4528 form are copies pre-filled for one request and carry a copy marker (`RT26E-…`); the blank request is a campaign marker.
- The 4528 form is not a form the member fills in; it is the association’s output, so its “reference” is the request’s, printed in the footer in at least 10-point type.

## 10. Profile slots

| Slot | What it is |
|---|---|
| `{ASSOCIATION}` | the association’s name; the “Association or Agent” line of 4528 |
| `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}` | where the request goes |
| `{BOARD_CONTACT}` | the person who answers a dispute about a fee |
| `{RESALE_PROVIDER}` | the manager, management company, or agent that provides the documents (4530(c): an association may contract with a person to comply) |
| `{FEE_SCHEDULE}` | the association’s actual-cost fee for each document (the Fee for Document column), and the transfer-record change cost (4575(a)) |
| `{ACK_DAYS}`, `{ESTIMATE_DAYS}` | the proposed policy days |

## 11. Handler and procedure

- **Handler:** `@handler("CIV 4530", "CIV 4525", "CIV 4528", role=Role.REQUEST, form="resale-documents", procedure="resale-documents")`. It accepts an arrival carrying this form (`RT`, a PayHOA form id) or classified `ResponseKind.RESALE`. `plan` opens the clock from `date-sent`; builds the 4528 estimate (the rows asked for, with the fee schedule, one fee per row, not bundled) as a draft; and at delivery builds the completed form. It writes nothing outside jason, and sends nothing. A person signs the 4525(a)(4) statement.
- **Document template:** the 4528 form is a `DocumentTemplate`-style output with `min_point_size = 10`; the test checks every run of text.
- **Procedure:** none exists. `RESPONSE_RULES` has a `RESALE` row (`assignment="records-requests"`, first step “Send the 4525 documents and the 4528 form, at actual cost.”). Add `resale-documents`: (1) stamp the date; (2) read who asks and whether the owner authorized; (3) send the estimate on the 4528 form; (4) gather the documents (the statement of assessments is a person’s, 4525(a)(4)); (5) deliver within 10 days with the completed form; (6) bill the seller separately; (7) on a cancellation, refund; (8) record each act.
- **jason never:** signs the 4525(a)(4) statement, sends the documents, or bills.

## 12. Edge cases

- **Co-owners.** Either may ask. The seller is “the seller”: all owners of record; the owner who asks is treated as authorized by the others unless one objects in writing (reading, counsel).
- **A representative or agent.** `requester-role` and `authorization` carry it. A power of attorney is accepted as the owner’s writing.
- **A tenant.** Not the owner and not an authorized recipient; the request is answered as an inquiry.
- **A buyer or the buyer’s agent asking directly.** 4530(a)(1) names the owner and the owner’s authorized recipient; the buyer’s own request is a lead (section 13). The handler tells the buyer’s agent that the owner must authorize and holds nothing back from an owner’s authorized recipient for it.
- **A minor.** A minor who holds title: the sale is through a guardian or conservator; the request comes from them with their authority attached.
- **Language and accessibility.** Statutory words are English; a plain-words note may be translated. Another format, large print, and help to complete the form are offered on it.
- **A request that arrives without the form.** An escrow company’s own request letter is a written request; the handler fills the same fields, asks for what is missing once, and starts the 10 days from the mailing or delivery date it can show, not from the day the missing detail arrives (reading).
- **A request that is really something else.** A request for “the HOA documents” is this form. A request for records not in 4525 (a ledger, contracts) is a [records request](records-request.md), and cannot be bundled in (4530(b)(5)). A lender’s payoff or demand statement is not 4525’s statement of assessments, though the handler reads it as the same kind of arrival (`ResponseKind.RESALE` takes “payoff demand”); the handler routes it to a person. A refinance is not a transfer of title; lead.
- **A unit sold by a subdivider.** 4525(b): “This section does not apply to an owner that is subject to Section 11018.6 of the Business and Professions Code.” That section is on the shelf (`data/authorities/BPC/BPC-11018.6.md`); the handler checks the owner’s status with a person.

## 13. Leads for the board and counsel

Drift: none found. The notice catalog row (`resale-documents`) cites 4530’s ten days, counted from the mailing or delivery of the request (`Anchor.REQUEST_MAILED`), the estimate before processing, and the completed 4528 form, in agreement with the shelf. `standard-forms.md` says “an owner’s (or an agent’s) request ... with a billing disclosure on the form 4528 sets”; the section says the association provides the estimate “on the form described in Section 4528”.

Leads (open questions; none settled here):

1. **“10 days.”** 4530(a)(1) says “within 10 days”, where 5210(b) says “business days” or “calendar days” expressly. Reading (the association’s, proposed): calendar days, counted from the mailing or delivery of the request. Counsel confirms. The shorter reading is safer.
2. **The start of the clock.** The section counts from “the mailing or delivery of the request”, not from receipt. The association may receive the request days after it is mailed. PROPOSED POLICY: scan and stamp mail the day it is opened; use the postmark if the owner supplies it; ask for the date sent on the form.
3. **Authorization.** 4530(a)(1) says “authorized by the owner” and does not say how. Requiring the owner’s signature could be read as a “condition” that 4530(a)(3) bars; accepting any writing is the proposal here (the escrow instructions, a signed listing). Counsel reads whether to withhold anything from a third party who gives no proof of authority, a question that turns on the owner’s privacy in the account statement (4525(a)(4)).
4. **A buyer’s own request.** 4525(a) puts the duty on the owner. Whether a prospective purchaser who is not authorized may demand the documents is open; the association answers through the owner.
5. **Expedited service.** A rush fee beyond actual cost is not obviously within 4530(b)(1) (“a reasonable fee ... based upon the association’s actual cost”). Counsel reads it; none is offered here.
6. **The refund time.** 4530(b)(3) sets no day. PROPOSED POLICY in row 5.
7. **The 4528 layout.** The shelf flattens the table; the column order must be taken from the official page when the form is built, and a test compares the row names and citations. The words “substantially the following form” allow a layout change; the row names and citations are used word for word.
8. **A transfer fee other than 4530.** 4575 limits any other charge to “actual costs to change its records” and the 4530 amount. A profile’s transfer fee is checked against it (`jason conflicts --leads`); the exceptions in 4580 are for particular organizations.
9. **Documents the association does not hold** (a reserve study not yet commissioned, no list of defects): the row is marked “Not Available (N/A)” or “Not Applicable (N/App)” on the form, never left blank.
10. **The minutes row.** 4525(a)(10) says “If requested by the prospective purchaser”; the request form lets the seller tick it on the buyer’s behalf. Counsel confirms that the owner’s request on the buyer’s behalf satisfies it.
11. **The 2025 amendments** (4525, 4528; operative 2026-01-01). A table or a form written before 2026 may lack the inspector’s report row (4525(a)(11)); `jason law-history` finds it.

## 14. Test fixtures

**Typical** (an escrow officer asks for the full set by email, for a seller):

| Field | Answer |
|---|---|
| `action` | Ask for the documents |
| `requester-name` | E. Escrow |
| `requester-role` | A person the owner has authorized |
| `owner-name` | A. Owner |
| `property-address` | 123 Main St, Anytown, CA 90000 |
| `authorization` | checked |
| `authorization-signature` | A. Owner, 2026-10-01 |
| `documents` | all 22 |
| `date-sent` | 2026-10-05 |
| `recipient-name` | E. Escrow |
| `delivery` | By electronic transmission |
| `email` | e.escrow@example.test |
| signature | E. Escrow, 2026-10-05 |

Expected: no problems; `{DUE}` = 2026-10-15; the estimate lists 22 rows with one fee each; the total is the sum.

**Minimal** (the owner asks for governing documents only, and will provide the rest directly):

| Field | Answer |
|---|---|
| `action` | Ask for the documents |
| `requester-name` | A. Owner |
| `requester-role` | The owner of the unit |
| `owner-name` | A. Owner |
| `property-address` | 123 Main St |
| `documents` | Articles of Incorporation or statement that not incorporated; CC&Rs; Bylaws; Operating Rules |
| `date-sent` | 2026-10-05 |
| `recipient-name` | A. Owner |
| `delivery` | I will collect them |
| signature | A. Owner |

Expected: no email, no mailing address required; the estimate lists four rows; the other rows are not billed (the seller “shall not be required to purchase ALL of the documents listed on this form”, 4528).

**Edge** (a request mailed days before it arrives; an agent with no authorization; one document requested that 4525 does not name):

| Field | Answer |
|---|---|
| `action` | Ask for the documents |
| `requester-name` | B. Agent |
| `requester-role` | A person the owner has authorized |
| `owner-name` | C. Owner |
| `property-address` | 456 Elm St |
| `documents` | Regular assessment; Special assessment; Notice(s) of violation |
| `date-sent` | 2026-09-28 (received 2026-10-03) |
| `authorization` | (blank) |
| `delivery` | By mail |
| `mailing-address` | 1 Agent Way, Anytown |
| signature | B. Agent |

Expected: `check()` reports `authorization: required, left blank` and `authorization-signature: required, left blank`; the handler asks once and does not refuse the owner; the clock counts from 2026-09-28 (`{DUE}` = 2026-10-08, already within 5 days of receipt, so the handler marks the request urgent); a free-text “and the pool maintenance contract” in a covering letter is not on the form, and the handler routes it to a records request, never into the 4528 list (4530(b)(5)).

**The statutory checklist test, in words.** (a) Each row of the request table (1 to 12) and the billing table (B1 to B11) names its authority and the key or the block that carries it; (b) the `documents` question offers exactly the 22 rows of the 4528 table, by the names the section gives, and no “other” option; (c) the rendered 4528 estimate carries each fixed sentence of the section word for word (B3, B9) and its title (B2); (d) every text run in the 4528 output is at least 10 points in every medium; (e) each row’s Civil Code citation equals the section’s; (f) `email` is required exactly when delivery is electronic; (g) the clock in row 3 equals 10 days as 4530(a)(1) states and counts from `date-sent`; (h) the recital tokens resolve against the shelf and name existing subdivisions; (i) the form has no question about the buyer, the price, or a fee paid. The scan and marker tests are as in [records-request.md](records-request.md).
