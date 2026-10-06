# Request to inspect or copy association records

Status: design (2026-10-05); built in the library as version 2 (2026-10-05, build step 2A: `src/jason/community/form_library/ca/records.py`, which keeps the old fields and records its departures from this page). Key `records-request`; proposed marker code `RR`. It follows the standard in [form-templates.md](../form-templates.md). The inventory row is "Records" in [standard-forms.md](../standard-forms.md). The form that exists today is `FormKey.RECORDS` (the profile's `mystique/forms.py`); this design replaces it and records where it has drifted (section 13).

## 1. Authority and what the law requires

As of: the shelf's 2025 session publication of the code (`data/authorities/CIV/CIV-5200-5240.md`, read with lawlibrary, 2026-10-05). Sections 5200 and 5210 were amended by Stats. 2025, Ch. 516 (SB 410), operative 2026-01-01, so the text below is the text in force. jason's copy is kept from the publication; it is not an official restatement, and the official page controls.

**CIV 5200, the definitions** (the record sets the form offers):

> For the purposes of this article, the following definitions shall apply:
>
> (a) “Association records” means all of the following:
>
> (1) Any financial document required to be provided to a member in Article 7 (commencing with Section 5300) or in Sections 5565 and 5810.
>
> (2) Any financial document or statement required to be provided in Article 2 (commencing with Section 4525) of Chapter 4.
>
> (3) Interim financial statements, periodic or as compiled, containing any of the following: (A) Balance sheet. (B) Income and expense statement. (C) Budget comparison. (D) General ledger. A “general ledger” is a report that shows all transactions that occurred in an association account over a specified period of time. The records described in this paragraph shall be prepared in accordance with an accrual or modified accrual basis of accounting.
>
> (4) Executed contracts not otherwise privileged under law.
>
> (5) Written board approval of vendor or contractor proposals or invoices.
>
> (6) State and federal tax returns.
>
> (7) Reserve account balances and records of payments made from reserve accounts.
>
> (8) Agendas and minutes of meetings of the members, the board, and any committees appointed by the board pursuant to Section 7212 of the Corporations Code; excluding, however, minutes and other information from executive sessions of the board as described in Article 2 (commencing with Section 4900).
>
> (9) Membership lists, including name, property address, mailing address, email address, as collected by the association in accordance with Section 4041 where applicable, but not including information for members who have opted out pursuant to Section 5220.
>
> (10) Check registers.
>
> (11) The governing documents.
>
> (12) An accounting prepared pursuant to subdivision (b) of Section 5520.
>
> (13) An “enhanced association record” as defined in subdivision (b).
>
> (14) “Association election materials” as defined in subdivision (c).
>
> (15) All inspector’s reports compiled pursuant to Section 5551.
>
> (b) “Enhanced association records” means invoices, receipts, and canceled checks for payments made by the association, purchase orders approved by the association, bank account statements for bank accounts in which assessments are deposited or withdrawn, credit card statements for credit cards issued in the name of the association, statements for services rendered, and reimbursement requests submitted to the association.
>
> (c) “Association election materials” means returned ballots, signed voter envelopes, the voter list of names, parcel numbers, and voters to whom ballots were to be sent, proxies, the candidate registration list, and the tally sheet of votes cast by electronic secret ballot. Signed voter envelopes may be inspected but may not be copied. An association shall maintain association election materials for one year after the date of the election.

**CIV 5205, the request, the representative, the place, the cost, the format:**

> (a) The association shall make available association records for the time periods and within the timeframes provided in Section 5210 for inspection and copying by a member of the association, or the member’s designated representative.
>
> (b) A member of the association may designate another person to inspect and copy the specified association records on the member’s behalf. The member shall make this designation in writing.
>
> (c) The association shall make the specified association records available for inspection and copying in the association’s business office within the common interest development.
>
> (d) If the association does not have a business office within the development, the association shall make the specified association records available for inspection and copying at a place agreed to by the requesting member and the association.
>
> (e) If the association and the requesting member cannot agree upon a place for inspection and copying pursuant to subdivision (d) or if the requesting member submits a written request directly to the association for copies of specifically identified records, the association may satisfy the requirement to make the association records available for inspection and copying by delivering copies of the specifically identified records to the member by individual delivery pursuant to Section 4040 within the timeframes set forth in subdivision (b) of Section 5210.
>
> (f) The association may bill the requesting member for the direct and actual cost of copying and mailing requested documents. The association shall inform the member of the amount of the copying and mailing costs, and the member shall agree to pay those costs, before copying and sending the requested documents.
>
> (g) In addition to the direct and actual costs of copying and mailing, the association may bill the requesting member an amount not in excess of ten dollars ($10) per hour, and not to exceed two hundred dollars ($200) total per written request, for the time actually and reasonably involved in redacting an enhanced association record. If the enhanced association record includes a reimbursement request, the person submitting the reimbursement request shall be solely responsible for removing all personal identification information from the request. The association shall inform the member of the estimated costs, and the member shall agree to pay those costs, before retrieving the requested documents.
>
> (h) Requesting parties shall have the option of receiving specifically identified records by electronic transmission or machine-readable storage media as long as those records can be transmitted in a redacted format that does not allow the records to be altered. The cost of duplication shall be limited to the direct cost of producing the copy of a record in that electronic format. The association may deliver specifically identified records by electronic transmission or machine-readable storage media as long as those records can be transmitted in a redacted format that prevents the records from being altered.

**CIV 5210, the periods and the timeframes:**

> (a) Association records are subject to member inspection for the following time periods:
>
> (1) For the current fiscal year and for each of the previous two fiscal years.
>
> (2) Notwithstanding paragraph (1), minutes of member and board meetings are subject to inspection permanently. If a committee has decisionmaking authority, minutes of the meetings of that committee shall be made available commencing January 1, 2007, and shall thereafter be permanently subject to inspection.
>
> (3) Notwithstanding paragraph (1), all inspector’s reports compiled pursuant to Section 5551 shall be subject to inspection for the time period required by subdivision (i) of Section 5551.
>
> (b) When a member properly requests access to association records, access to the requested records shall be granted within the following time periods:
>
> (1) Association records prepared during the current fiscal year, within 10 business days following the association’s receipt of the request.
>
> (2) Association records prepared during the previous two fiscal years, within 30 calendar days following the association’s receipt of the request.
>
> (3) Any record or statement available pursuant to Article 2 (commencing with Section 4525) of Chapter 4, Article 7 (commencing with Section 5300), Section 5565, or Section 5810, within the timeframe specified therein.
>
> (4) Minutes of member and board meetings, within the timeframe specified in subdivision (a) of Section 4950.
>
> (5) Minutes of meetings of committees with decisionmaking authority for meetings commencing on or after January 1, 2007, within 15 calendar days following approval.
>
> (6) Membership list, within the timeframe specified in Section 8330 of the Corporations Code.
>
> (c) There shall be no liability pursuant to this article for an association that fails to retain records for the periods specified in subdivision (a) that were created prior to January 1, 2006.

**CIV 5215, withholding and redacting:**

> (a) Except as provided in subdivision (b), the association may withhold or redact information from the association records if any of the following are true:
>
> (1) The release of the information is reasonably likely to lead to identity theft. ...
>
> (2) The release of the information is reasonably likely to lead to fraud in connection with the association.
>
> (3) The information is privileged under law. Examples include documents subject to attorney-client privilege or relating to litigation in which the association is or may become involved, and confidential settlement agreements.
>
> (4) The release of the information is reasonably likely to compromise the privacy of an individual member of the association.
>
> (5) The information contains any of the following: (A) Records of goods or services provided a la carte to individual members of the association for which the association received monetary consideration other than assessments. (B) Records of disciplinary actions, collection activities, or payment plans of members other than the member requesting the records. (C) Any person’s personal identification information, including, without limitation, social security number, tax identification number, driver’s license number, credit card account numbers, bank account number, and bank routing number. (D) Minutes and other information from executive sessions of the board as described in Article 2 (commencing with Section 4900), except for executed contracts not otherwise privileged. Privileged contracts shall not include contracts for maintenance, management, or legal services. (E) Personnel records other than the payroll records required to be provided under subdivision (b). (F) Interior architectural plans, including security features, for individual homes.
>
> (b) Except as provided by the attorney-client privilege, the association may not withhold or redact information concerning the compensation paid to employees, vendors, or contractors. Compensation information for individual employees shall be set forth by job classification or title, not by the employee’s name, social security number, or other personal information.
>
> (d) If requested by the requesting member, an association that denies or redacts records shall provide a written explanation specifying the legal basis for withholding or redacting the requested records.

(The ellipsis in 5215(a)(1) omits its definition of “identity theft” and its examples; subdivision (c), on liability for a failure to withhold, is cited, not recited.)

**CIV 5216(a)** (a member in the Safe at Home program; recited by the association only on request, never asked on this form):

> Notwithstanding any other law, upon request of a member of an association who is an active participant in the Safe at Home program, the association shall do both of the following: (1) Accept and use the address designated by the Secretary of State as the Safe at Home participant’s substitute address under the Safe at Home program for all association communications. (2) Withhold or redact information that would reveal the name, community property address, or email address of the Safe at Home participant from both of the following: (A) All resident community membership lists, including mailbox bank listings, resident directories, electronic keypads, unit property numbers, and internet web portal accounts. (B) Any membership list that will be shared with other members of the association.

**CIV 5230(a)** (what the member may do with what the records show):

> The association records, and any information from them, may not be sold, used for a commercial purpose, or used for any other purpose not reasonably related to a member’s interest as a member. An association may bring an action against any person who violates this article for injunctive relief and for actual damages to the association caused by the violation.

**CIV 5235(a), (b)** (what follows if the association does not act):

> (a) A member may bring an action to enforce that member’s right to inspect and copy the association records. If a court finds that the association unreasonably withheld access to the association records, the court shall award the member reasonable costs and expenses, including reasonable attorney’s fees, and may assess a civil penalty of up to five hundred dollars ($500) for the denial of each separate written request.
>
> (b) A cause of action under this section may be brought in small claims court if the amount of the demand does not exceed the jurisdiction of that court.

**CIV 5240(a), (b), (d)** (how the article sits with the Corporations Code, and who it does not reach):

> (a) As applied to an association and its members, the provisions of this article are intended to supersede the provisions of Sections 8330 and 8333 of the Corporations Code to the extent those sections are inconsistent.
>
> (b) Except as provided in subdivision (a), members of the association shall have access to association records, including accounting books and records and membership lists, in accordance with Article 3 (commencing with Section 8330) of Chapter 13 of Part 3 of Division 2 of Title 1 of the Corporations Code.
>
> (d) This article shall not apply to any common interest development in which separate interests are being offered for sale by a subdivider under the authority of a public report issued by the Bureau of Real Estate so long as the subdivider or all subdividers offering those separate interests for sale, or any employees of those subdividers or any other person who receives direct or indirect compensation from any of those subdividers, comprise a majority of the directors. Notwithstanding the foregoing, this article shall apply to that common interest development no later than 10 years after the close of escrow for the first sale of a separate interest to a member of the general public pursuant to the public report issued for the first phase of the development.

Other sections this form cites and does not recite: CIV 5220 and 5225 (the membership list: [membership-list.md](membership-list.md)); CIV 4950(a) (the minutes' timeframe, quoted in section 7); CIV 5551(i) (the inspector's reports' period); CIV 4040 and 4041 (individual delivery; an email is never required, 4041(b)(2)(A)); CIV 4525 to 4530 ([resale-documents.md](resale-documents.md)). CORP 8333 (accounting books and records open "upon the written demand ... of any member at any reasonable time, for a purpose reasonably related to such person’s interests as a member") is on the shelf; 5240(b) points to it, and this design does not ask a purpose for records other than the membership list, because 5205 asks none.

**What the law does not say** (found by reading the shelf; each is a lead in section 13):

- It does not define "properly requests" (5210(b)).
- It does not define "business day" anywhere in 5200 to 5240 or elsewhere on the shelf's CIV files.
- It does not say whether a request must be written to start the clocks, except for a designation (5205(b), "in writing") and a request for copies sent "directly" to the association (5205(e), "written request").
- It sets no time for the cost estimate, only that it comes before copying (5205(f)) or before retrieving (5205(g)).
- It sets no time for the written explanation of a withholding, only that it is given "if requested" (5215(d)).

## 2. Who uses it, and when

- **A member** (an owner of a separate interest) who wants to look at, or have copies of, the association's records.
- **A person the member designates in writing** (5205(b)): a relative, an accountant, an attorney, a buyer's agent, a tenant the owner authorizes. The designation is part of the form so the request and the authority arrive together.
- When: at any time. The right is a standing right (5210(a) sets the periods). The form is the usual way, never the only way ([form-templates.md](../form-templates.md), "What a form is not"): a request in an email or a letter is a request.
- Who is not served by this form: a buyer or an escrow agent (the sale documents are [resale-documents.md](resale-documents.md)); a member asking only for the membership list ([membership-list.md](membership-list.md), which asks the purpose 5225 requires); a member asking for a copy of the minutes alone (4950(a): the form accepts it, and the minutes clock is the shorter one).

## 3. What the form must carry

`required_content` is the checklist the test reads. "Fixed text" is a block of the form that is not a question; the test looks for its words in the rendered form.

| # | What the law says the form or request carries | Words | Carried by |
|---|---|---|---|
| 1 | The request names the records | 5205(a) "make available association records"; 5205(e) "specifically identified records" | `record-sets`, `specific-records` |
| 2 | The time periods the records cover | 5210(a), (b) | `period`, `period-from`, `period-to` |
| 3 | Inspect, copy, or both | 5205(a), (c), (d), (e) | `how`, `inspect-times` |
| 4 | A designation of a representative is in writing, by the member | 5205(b) "The member shall make this designation in writing." | `capacity`, `member-name`, `designation`, `designation-signature` |
| 5 | The member is told, before copying, the amount of the copying and mailing cost, and agrees to it | 5205(f) | fixed text "What it costs"; stage 2 `agree-copying` |
| 6 | For an enhanced association record: the estimated redaction cost, told and agreed before the documents are retrieved; at most $10 an hour and $200 a request | 5205(g) | fixed text "What it costs"; stage 2 `agree-redaction` |
| 7 | The option of electronic transmission or machine-readable storage media | 5205(h) | `delivery` |
| 8 | An email address only if the member asks for delivery by email | 4041(b)(2)(A); standard 2 | `email` (required only when `delivery` is electronic) |
| 9 | The clocks the association works to | 5210(b) | fixed text "When you will hear from us" (section 6) |
| 10 | What may be withheld, and the right to a written explanation on request | 5215(a), (d) | fixed text "What may be held back"; `explanation` |
| 11 | Where inspection happens | 5205(c), (d) | fixed text with `{BUSINESS_OFFICE}`; `inspect-times` |
| 12 | The use limit on what the records show | 5230(a) | fixed text (recital), no question |
| 13 | The member's remedy if the association does not act | 5235(a), (b) | fixed text (recital), no question |
| 14 | A statement that a request in other words is still a request, and where to get help | standard 5 | fixed text |

## 4. The questions

Kinds: text, choice, checkbox, email, phone, address, paragraph, date. One question holds one value. Stage 1 is the request; stage 2 is the agreement to the estimate (section 9: it goes out pre-filled with the amounts, as a copy). The "required" column says when a question is required; the form template needs a `required_if` rule for the conditional ones (section 11), since `FormQuestion.required` is a plain flag today.

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `name` | Your name | text | yes | 5205(a): a member, or the member’s designated representative | NAME | request.requester |
| `unit-address` | Unit address | address | yes | places the requester as a member (5205(a)) | ADDRESS (prefilled `UNIT_ADDRESS` on a copy sent to a member) | request.unit |
| `capacity` | You are asking as | choice: “A member (owner) of the association”; “A person the member has designated in writing” | yes | 5205(a), (b) | TEXT | request.capacity |
| `member-name` | Name of the member you ask for | text | only if `capacity` is the representative | 5205(b) | NAME | request.member |
| `designation` | The member designates the person named above to inspect and copy the records described below on the member’s behalf | checkbox (one box) | only if `capacity` is the representative | 5205(b) | TEXT | request.designation = present |
| `designation-signature` | Member’s signature (typed or written) and date | text | only if `capacity` is the representative | 5205(b): “in writing” | NAME | request.designation_signed, with date |
| `record-sets` | Which records do you want? (tick any) | checkbox: the sets of 5200(a), in plain words, and “Other records” | yes | 5200(a), (b), (c) | TEXT | request.sets (each set is an `AssociationRecord`) |
| `specific-records` | Describe the records as exactly as you can (what, which dates, which vendor or meeting) | paragraph | yes | 5205(e): copies go by delivery only for “specifically identified records” | TEXT | request.description |
| `period` | What time does it cover? (tick any) | checkbox: “This fiscal year”; “Last fiscal year”; “The fiscal year before last”; “Minutes of member or board meetings, any date”; “Minutes of a committee with decisionmaking authority”; “Inspector’s reports” | yes | 5210(a), (b) | TEXT | request.periods (each sets a clock, section 7) |
| `period-from` | From (date), if you know it | date | no | narrows the search; 5210(b) places a record by when it was prepared | TEXT | request.from |
| `period-to` | To (date), if you know it | date | no | as above | TEXT | request.to |
| `how` | What do you want to do? | choice: “Inspect the records”; “Receive copies”; “Inspect, then receive copies” | yes | 5205(a), (c), (d), (e) | TEXT | request.how |
| `inspect-times` | Days and times that suit you to inspect | paragraph | no | 5205(c), (d): the place and time are agreed where there is no business office | TEXT | request.inspect_times |
| `delivery` | If you want copies, how should they reach you? | choice: “By electronic transmission”; “By mail”; “On machine-readable storage media (a USB drive or disc)”; “I will collect them at the place records are inspected” | when `how` includes copies | 5205(e) (individual delivery), 5205(h) | TEXT | request.delivery |
| `email` | Email address for the electronic copies | email | only if `delivery` is electronic | 5205(h); 4041(b)(2)(A): never otherwise | EMAIL | request.email (kept on the request only; never written to a tag) |
| `mailing-address` | Mailing address for the copies | address | only if `delivery` is mail or storage media | 5205(e), 4040(a) | ADDRESS; “Same as my unit address” box | request.mail_to |
| `cost-ceiling` | Do not copy or send anything that costs more than this without asking me first | text (an amount) | no | 5205(f): the member may limit what is agreed | TEXT | request.ceiling_cents |
| `explanation` | If you keep back or black out anything, send me the legal reason in writing | checkbox (one box) | no | 5215(d): “If requested by the requesting member” | TEXT | request.explanation_requested |
| (signature) | Signature and date | signature line, date | yes on paper and PDF; “signed in” online | proves who asked; stage 1 | NAME | request.signed |

Stage 2 (the estimate copy, pre-filled with the amounts; a signed-in PayHOA reply or a signed return):

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `agree-copying` | I agree to pay the direct and actual cost of copying and mailing shown above | choice: “I agree”; “I do not agree” | yes | 5205(f): “the member shall agree to pay those costs, before copying and sending” | TEXT | request.copy_agreed + the amount and date |
| `agree-redaction` | I agree to pay the estimated redaction charge shown above | choice: “I agree”; “I do not agree”; “No redaction charge is shown” | yes | 5205(g): agreement “before retrieving the requested documents” | TEXT | request.redaction_agreed + amount and date |
| (signature) | Signature and date | signature line | yes | stage 2 | NAME | request.agreement_signed |

Not asked, on purpose: why the member wants the records (5205 asks no purpose; asking one would be asking more than the law needs), the member's phone number, the unit's occupancy, or whether the member is in the Safe at Home program (5216(b): the association keeps participation confidential, so a field for it on a form many people see is not made).

## 5. The recitals

The form opens with these, by token, with the subdivisions named, then the caveat of section 1.

| Token | Subdivisions | Why it opens the form |
|---|---|---|
| `{QUOTE:CIV 5205(a)}` | (a) | the right, and that it reaches the member’s representative |
| `{QUOTE:CIV 5205(b)}` | (b) | the written designation |
| `{QUOTE:CIV 5205(f)}` | (f) | the estimate and the member’s agreement before copying |
| `{QUOTE:CIV 5205(g)}` | (g) | the redaction charge for enhanced records and its caps |
| `{QUOTE:CIV 5205(h)}` | (h) | electronic transmission or storage media |
| `{QUOTE:CIV 5210(a)}` | (a)(1), (2), (3) | the periods |
| `{QUOTE:CIV 5210(b)}` | (b)(1) to (6) | the timeframes |
| `{QUOTE:CIV 5215(a)}` | (a)(1) to (5) | what may be held back |
| `{QUOTE:CIV 5215(d)}` | (d) | the written explanation |
| `{QUOTE:CIV 5230(a)}` | (a) | the limit on use |
| `{QUOTE:CIV 5235(a)}` | (a), (b) | what the member may do if the association does not act |

A plain-words note may follow each, labeled “The association’s plain-words note; the words above control.” `{QUOTE:CIV 5200(a)}` is not recited at length: the `record-sets` options carry its paragraphs, and the page links to the section.

## 6. What the member is told

The sentence the member reads (`member_clock`):

> We will make records of this fiscal year available within 10 business days after we receive your request, and records of the two years before within 30 calendar days. Minutes, committee minutes, the membership list, and the documents named in Civil Code 4525 to 4530, 5300, 5565, and 5810 have the times the law sets for them, shown on the back of this form. Before we copy or send anything, we will tell you the cost and ask you to agree to it in writing; if you want to see the records instead, there is no copy cost. We may hold back or black out some information the law lets us protect; if you ask, we will tell you in writing the legal reason. The person at {RECORDS_CONTACT} decides what is within your request. If you disagree, ask the board in writing to reconsider; you may also ask to meet and confer (Civil Code 5900 to 5920), and you may go to court, including small claims court if the amount is within its limit (Civil Code 5235). If we do not act in time, you may bring an action, and a court that finds we unreasonably withheld access shall award you your reasonable costs and attorney’s fees and may assess a civil penalty of up to $500 for each separate written request.

Reading (label: the association’s plain-words note, not the statute): the last sentence restates 5235(a).

## 7. The association's clocks

“Counted from” is the association’s receipt of the request, stamped on the day it arrives (mail on the day opened; email and PayHOA on the day sent). The law counts from receipt in 5210(b); where it counts from something else the row says so.

| # | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| 1 | receipt | acknowledge within 2 business days | PROPOSED POLICY (the same proposal `RESPONSE_RULES` carries as `acknowledge_days=2`) | nothing in the law; the member is left without a date and the board's good-faith record is weaker |
| 2 | receipt | records prepared during the current fiscal year: within 10 business days | statute: 5210(b)(1) | the member may sue (5235(a)); a court that finds the records were unreasonably withheld shall award costs and fees and may assess a civil penalty up to $500 for the denial of each separate written request |
| 3 | receipt | records prepared during the previous two fiscal years: within 30 calendar days | statute: 5210(b)(2) | as row 2 |
| 4 | receipt | a record or statement under Article 2 of Chapter 4, Article 7 of Chapter 6, Section 5565, or Section 5810: “within the timeframe specified therein” | statute: 5210(b)(3), then the section named | as row 2; the handler reads the number from that section |
| 5 | the meeting | minutes of a board meeting other than an executive session: “available to members within 30 days of the meeting”, and “distributed to any member upon request and upon reimbursement of the association’s costs” | statute: 5210(b)(4), CIV 4950(a) | as row 2 |
| 6 | the committee’s approval of the minutes | 15 calendar days following approval (committee with decisionmaking authority, meetings commencing on or after January 1, 2007) | statute: 5210(b)(5) | as row 2 |
| 7 | receipt (the demand) | membership list: “on or before the later of ten business days after the demand is received or after the date specified therein as the date as of which the list is to be compiled”; the written offer of an alternative: “within ten business days after receiving a demand” | statute: 5210(b)(6) pointing to CORP 8330(a)(2) and (c) | see [membership-list.md](membership-list.md) |
| 8 | receipt | the cost estimate: within 3 business days, so that the member can agree and the 10-business-day or 30-day clock can still be met | PROPOSED POLICY (the law says only “before copying and sending”, 5205(f), and “before retrieving”, 5205(g)) | copying cannot start; the statutory clock is not paused by the law’s text (section 13, lead 3) |
| 9 | the estimate | the member is asked to answer within 15 calendar days; if the member does not agree, the request is kept open for inspection and closed for copies; a reminder at day 10 | PROPOSED POLICY | the request is closed as to copies, and reopens when the member asks again; nothing is billed |
| 10 | the day records are produced, or the 10th business day, whichever is first | the written explanation of a withholding or redaction, when the member asked | PROPOSED POLICY (the law sets no time: 5215(d)) | the member may sue; the association has no written basis on the record |
| 11 | the election | election materials are kept for one year | statute: 5200(c) | a ballot set not kept is a records failure (5235(a)) |
| 12 | creation of the record | records are kept for the current and the two previous fiscal years (minutes permanently) | statute: 5210(a); no liability for records created before January 1, 2006 (5210(c)) | see 5235(a) |

A “business day” is not defined on the shelf. PROPOSED POLICY: the association states the definition it uses on the form (`{BUSINESS_DAY_DEFINITION}`) and counts the day after receipt as day 1.

## 8. The acknowledgment text

> Reference {REFERENCE}. We received your request to inspect or copy association records on {RECEIVED}. The time the law sets for the records you asked for ends on {DUE}. {DECIDER} will tell you the cost of any copies before anything is copied or sent, and will ask you to agree to it in writing. If you asked for the membership list, a separate letter follows. If you want to change or add to your request, write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.

`{DUE}` is the earliest due date among the request’s clocks (rows 2 to 7); the handler lists the others beside it.

## 9. Channels and the reference

- **Channels:** paper, fillable PDF, email, PayHOA, portal. The paper and fillable PDF are the standard form; the PayHOA form is the preferred channel (a signed-in answer is `SIGNED_IN`, the strongest proof that a member asked, see [forms.md](../forms.md), “Channels and assurance”); a reply email from the address on file is `MATCHED`; a signed paper copy is `CLAIMED`. A Google Form is not offered: the right belongs to a member, and an unsigned-in answer would be a lead only.
- **Marker code proposed: `RR`** (records request). Letters from the alphabet `0-9 A C E F H K M N P R T V X`; the owner-information form is `NP`; `RR` collides with no code found in `docs/` or `mystique/forms.py`. A standing form’s campaign is the year it was generated (`RR26M-…` for the mailed blank, `RR26P-…` for the PayHOA form).
- **Stage 2 is a copy:** the estimate goes to one member, pre-filled with the amounts, so its marker names the copy (`RR26E-4RK9T-C7`), and the return is compared field by field with what was sent. The campaign marker alone would not say which request the agreement answers.
- The reference is a hint, never what the reading depends on ([form-identifiers.md](../form-identifiers.md)).

## 10. Profile slots

The base template is general. The profile fills:

| Slot | What it is |
|---|---|
| `{ASSOCIATION}` | the association’s name |
| `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}` | where the request goes |
| `{RECORDS_CONTACT}` | the person or office that handles a records request, and `{BOARD_CONTACT}` for a reconsideration |
| `{BUSINESS_OFFICE}` | the business office within the development, or a statement that there is none, so that a place is agreed (5205(c), (d)) |
| `{FISCAL_YEAR_START}` | the first day of the fiscal year, so “this fiscal year” and “the two before” can be placed |
| `{FEE_SCHEDULE}` | the direct and actual cost of a copy and of mailing; the redaction rate, never above $10 an hour or $200 a request (5205(g)) |
| `{BUSINESS_DAY_DEFINITION}` | what a business day is, where the board has adopted one |
| `{ACK_DAYS}` | the acknowledgment days the board adopts (proposed: 2 business days) |
| `{ESTIMATE_DAYS}`, `{AGREEMENT_DAYS}` | the proposed policy days of rows 8 and 9 once adopted |

## 11. Handler and procedure

- **Handler:** `@handler("CIV 5205", "CIV 5210", "CIV 5215", role=Role.REQUEST, form="records-request", procedure="records-request", channels=(PAYHOA, GMAIL, MAIL))` ([arrivals-design.md](../arrivals-design.md)). The class `RecordsRequests` already named there. `accepts` takes an arrival that is this form (the marker `RR`, a PayHOA form id) or is classified `ResponseKind.RECORDS` with a citation. `read` is evidence only: the answers as a `FormAnswers`, with the record sets mapped to their clocks. `plan` opens the clocks of section 7 (as schedule occurrences), drafts the acknowledgment (`acknowledgment_draft`), and, when `how` includes copies, drafts the stage 2 estimate for a person to fill in. It writes nothing outside jason, sends nothing, and never decides what is withheld.
- **Procedure:** none exists. The `respond` procedure covers the clock and the answer, and `RESPONSE_RULES` has a `RECORDS` row with `assignment="records-requests"`. Add a procedure `records-request`, with steps: (1) stamp the receipt date and open the clocks; (2) acknowledge; (3) gather the records by set and period; (4) read 5215 for each record and note what is held back and why; (5) estimate the cost, send stage 2, wait for the agreement; (6) deliver by the chosen means and record the date; (7) close, and put a denied or partly denied request on the next agenda; a lesson for each failure.
- **Template changes this needs:** a `required_if` on a `FormQuestion` (so the email is required only for an electronic delivery, and the representative’s questions only for a representative); a `stage` on a template (the estimate copy); a pre-filled amount line type.
- **jason never:** approves or denies the request, decides what is withheld, copies a record to the member, or bills (AGENTS.md, Boundaries).

## 12. Edge cases

- **Co-owners.** Each is a member. Any one may ask; one request is one clock; the copies go to the requester, not to the unit. Two co-owners asking on one form is one request with two names.
- **A representative.** The designation is the member’s, in writing (5205(b)). A power of attorney is a writing, and the form accepts it attached in place of the signature line. A representative who gives no designation is told, once, that the clock starts when the written designation arrives (reading, section 13, lead 4).
- **A tenant or a non-owner.** A tenant is not a member. The association may answer a tenant, but 5205 does not require it; a tenant with the owner’s written designation is a representative. A buyer in escrow asks through [resale-documents.md](resale-documents.md).
- **A minor.** A minor who holds title is a member; the law is silent on who may sign. The form takes the parent or guardian as the representative, with the guardian’s writing (reading, counsel).
- **Language and accessibility.** The statutory words stay in English; the plain-words note may be translated. Large print, another format, a person to read the form aloud or write it down, and a reasonable accommodation are offered on the form; a request written down by the association is returned to the member for confirmation.
- **A request that arrives without the form.** It is a request. The handler reads it into the same fields, marks what is missing, and asks for it once; the clock runs from receipt, not from the day the missing detail arrives, unless the request is too vague to identify any record (reading, lead 1).
- **A request that is really something else.** A request for the membership list goes to [membership-list.md](membership-list.md) the same day. A request for the sale documents goes to [resale-documents.md](resale-documents.md). A request for payoff or the owner’s own account balance is a records request for the member’s own ledger and a different kind of statement (CIV 4525(a)(4) is the sale statement): the handler reads it, then answers or routes it. A request to be told why a charge is owed is not a records request; a request for the notice or the ledger behind it is.
- **A member in the Safe at Home program.** The association keeps participation confidential (5216(b)) and withholds the name, address, and email from every list that would be shared (5216(a)(2)). The handler reads the profile’s private register, never a form answer.
- **A member who asks for records a person at the manager’s office holds.** They are the association’s records; the association answers. A manager’s portal may be the usual channel, and the association’s clock still runs.

## 13. Leads for the board and counsel

A reading is labeled as one and whose it is. A conflict between a document and the statute is noted, never resolved.

**Drift finding (the existing form).** The `RECORDS` form (`mystique/forms.py`) says in its description that “The association may charge the direct cost of copying and redaction (Civil Code 5205(e))”. In the text on disk, 5205(e) is the individual-delivery provision (“the association may satisfy the requirement ... by delivering copies of the specifically identified records to the member by individual delivery”). The charge for copying and mailing is 5205(f), and the redaction charge (time at not more than $10 an hour, not more than $200 a request) is 5205(g), and only for an enhanced association record. The form also says “direct cost of copying and redaction”, where 5205(f) says “direct and actual cost of copying and mailing” and 5205(g) allows a time charge for redaction only of enhanced association records. The notice catalog’s rows (`records-current-year`) cite (e), (f), and (g) correctly. The existing form also lacks the written designation of a representative (5205(b)), the agreement to the cost before copying (5205(f), (g)), the 5215(d) request, and the periods; it asks an email address as required, which standard 2 does not allow. This design replaces the whole form and recites by token, so the subdivision comes from the shelf when the form is built and the build fails if it is gone.

Leads (each is a question the law leaves open; none is settled here):

1. **“Properly requests” (5210(b)).** The words are not defined. Reading (the association’s, proposed): a request is proper when it identifies the records by set and period well enough to find them, comes from a member or a designated representative, and reaches the association; a form is never required. Counsel confirms; the board adopts a written policy so each request is treated the same way.
2. **“Business day” and how it is counted.** Not defined on the shelf. PROPOSED POLICY in section 7. The board adopts it.
3. **Does the clock stop while the member decides on the cost?** 5205(f) says copying waits for the member’s agreement; 5210(b) counts from receipt. Reading A: the access clock runs from receipt; inspection is always available within it, and copies follow the agreement. Reading B: the time to produce copies is extended by the days the member takes to agree. The law does not say. The proposal in section 7 meets the shorter reading (estimate in 3 business days) and leaves the question for counsel.
4. **Written requests.** 5205(b) and 5205(e) say “writing”; 5210(b) does not. Whether an oral request starts a clock is open. PROPOSED POLICY: write it down, date it, send it back for confirmation; counsel reads whether the clock runs from the oral request.
5. **Redaction of a record that is not an enhanced record.** 5205(g) allows an hourly charge for redacting “an enhanced association record”. Whether time spent redacting another record may be billed is open; this design charges none.
6. **A member’s purpose.** The records article asks a purpose only for the membership list (5225). Corporations Code 8333 asks a purpose for accounting books and records; 5240(a) says 5200 to 5240 supersede 8330 and 8333 “to the extent those sections are inconsistent”. Whether 5240(b) gives the association a ground to ask a purpose for other records is a question for counsel; this design asks none.
7. **A developer-controlled association.** 5240(d) says the article does not apply while a subdivider’s people are a majority of the directors (with a ten-year outer limit). Add a `Community` method for the association’s control status (empty default) so the handler can say so; none is added here.
8. **The 2025 amendments** (5200, 5210; operative 2026-01-01). Any form or template written before 2026 may carry the earlier text of 5200(a) and 5210. `jason law-history` and `jason conflicts --leads` find the change; the token build catches it for this form.
9. **The cost schedule.** Whether the association’s per-page and mailing charges are the “direct and actual” cost is for the board and the manager’s books; the schedule is adopted by the board, and the form only shows it.

## 14. Test fixtures

Made-up answers. All use plainly fake data.

**Typical** (a member asks for copies of last year’s contracts by email):

| Field | Answer |
|---|---|
| `name` | A. Owner |
| `unit-address` | 123 Main St, Anytown, CA 90000 |
| `capacity` | A member (owner) of the association |
| `record-sets` | Executed contracts; Check registers |
| `specific-records` | The landscape and roofing contracts signed last year, and the check register for last year |
| `period` | Last fiscal year |
| `how` | Receive copies |
| `delivery` | By electronic transmission |
| `email` | a.owner@example.test |
| `explanation` | checked |
| signature, date | A. Owner, 2026-10-05 |

Expected: `check()` returns no problems; clocks opened: the previous-two-years row (30 calendar days, from the receipt date); the cost estimate is drafted; the acknowledgment carries `{DUE}` = receipt + 30 calendar days.

**Minimal** (a member inspects this year’s minutes):

| Field | Answer |
|---|---|
| `name` | A. Owner |
| `unit-address` | 123 Main St |
| `capacity` | A member (owner) of the association |
| `record-sets` | Agendas and minutes |
| `specific-records` | Board minutes since January |
| `period` | Minutes of member or board meetings, any date |
| `how` | Inspect the records |
| signature | A. Owner |

Expected: no email, no mailing address, no delivery asked and none required; clocks: minutes (4950(a)); no estimate (inspection costs nothing).

**Edge** (a representative asks for enhanced records, with a redaction charge, a member in the Safe at Home program on the unit’s account, and a prior-year record):

| Field | Answer |
|---|---|
| `name` | B. Agent |
| `unit-address` | 456 Elm St |
| `capacity` | A person the member has designated in writing |
| `member-name` | C. Owner |
| `designation` | checked |
| `designation-signature` | C. Owner, 2026-10-01 |
| `record-sets` | Enhanced association records |
| `specific-records` | Invoices and canceled checks for the pool repair |
| `period` | This fiscal year; Last fiscal year |
| `how` | Inspect, then receive copies |
| `delivery` | By mail |
| `mailing-address` | 456 Elm St (the box “Same as my unit address” checked) |
| `cost-ceiling` | $40 |

Expected: two clocks (10 business days for the current year’s invoices; 30 calendar days for last year’s); the estimate shows a copying and mailing cost and a redaction charge no higher than $10 an hour and $200 for the request; the handler redacts the Safe at Home participant’s name and address; the copies wait for stage 2.

**The statutory checklist test, in words.** For each row of the section 3 table: (a) the template’s `required_content` names the row’s authority and the key of the question or fixed block that carries it; (b) a question with that key exists, or the fixed block’s words are in the rendered form, in every channel (paper, PDF, PayHOA sheet); (c) a required question is required exactly when the table says; (d) the form carries no required email, no field for why the member wants the records, and no field for Safe at Home participation; (e) every recital token in section 5 resolves against `data/authorities/CIV/CIV-5200-5240.md`, and the subdivision named exists there (the recital-freshness test; a changed or removed subdivision fails the build); (f) 5205(f) and (g) both appear in the estimate stage’s text, and the redaction cap in the text equals $10 an hour and $200 a request as the section states; (g) the clocks in section 7, rows 2 and 3, equal 10 business days and 30 calendar days as 5210(b)(1), (2) state. The scan test reads a made-up filled copy at several resolutions and expects the same answers, and the marker `RR` reads back or is repaired to the one sent marker ([form-fuzzer.md](../form-fuzzer.md)).
