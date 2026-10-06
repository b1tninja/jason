# Request to receive general notices by individual delivery

Status: design (2026-10-05); built in the library as version 1 (2026-10-05), `src/jason/community/form_library/ca/individual_delivery.py`, marker code `NV`, handler `response-clock` with procedure `respond` (the `delivery-requests` procedure is still a proposal; the module's docstring lists where it departs from this page). Key `individual-delivery-request`. It follows the standard in [form-templates.md](../form-templates.md). The inventory row is "Request for individual delivery of general notices" in [standard-forms.md](../standard-forms.md). Today this request is not collected on any form ([standard-forms.md](../standard-forms.md), family one); the annual policy statement is where the option must be described.

## 1. Authority and what the law requires

As of: the shelf’s 2025 session publication of the code (`data/authorities/CIV/CIV-4000-4070.md`, `CIV-4075-4190.md`, `CIV-5260.md`, `CIV-5300-5320.md`, `CIV-4900-4955.md`, read with lawlibrary, 2026-10-05). CIV 4045 is as amended by Stats. 2021, Ch. 640 (operative 2022-01-01); CIV 5260 as amended by Stats. 2024, Ch. 383 (operative 2025-01-01). jason’s copy is kept from the publication; it is not an official restatement, and the official page controls.

**CIV 4045(b), the right this form carries out:**

> (b) Notwithstanding subdivision (a), if a member requests to receive general notices by individual delivery, all general notices to that member, given under this section, shall be delivered pursuant to Section 4040. The option provided in this subdivision shall be described in the annual policy statement prepared pursuant to Section 5310.

**CIV 4045(a), what a general notice is and how it is otherwise given** (intro and (1)):

> (a) If a provision of this act requires “general delivery” or “general notice,” the document shall be provided by one or more of the following methods:
>
> (1) Any method provided for delivery of an individual notice pursuant to Section 4040.

(4045(a)(2) to (5) add: inclusion in a billing statement, newsletter, or other document delivered by a method of the section; posting the printed document in a prominent location designated in the annual policy statement; inclusion in association television programming; and posting on the association’s internet website in a prominent location, if designated in the annual policy statement.)

**CIV 4148 and 4153, the two definitions:**

> “General notice” means the delivery of a document pursuant to Section 4045.
>
> “Individual notice” means the delivery of a document pursuant to Section 4040.

**CIV 4040(a), what “pursuant to Section 4040” means for this member:**

> (a) (1) If a provision of this act requires an association to deliver a document by “individual delivery” or “individual notice,” the association shall deliver that document in accordance with the preferred delivery method specified by the member pursuant to Section 4041.
>
> (2) If the member has not provided a valid delivery method pursuant to Section 4041, the association shall deliver the document by first-class mail, registered or certified mail, express mail, or overnight delivery by an express service carrier addressed to the recipient at the address last shown on the books of the association.

**CIV 5260(c), how the request is made effective, and its cancellation:**

> To be effective, any of the following requests shall be delivered in writing to the association, pursuant to Section 4035:
>
> (c) A request for individual delivery of general notices to the member, pursuant to subdivision (b) of Section 4045, or a request to cancel a prior request for individual delivery of general notices.

**CIV 5310(a)(4), where the association must tell members of the right:**

> (4) Notice of a member’s option to receive general notices by individual delivery, pursuant to subdivision (b) of Section 4045.

**Three more places the Act says a member may ask:**

- CIV 4926(a)(1)(C) (a meeting held entirely by teleconference): the notice of each such meeting includes “A reminder that a member may request individual delivery of meeting notices, with instructions on how to do so.” CIV 5450(b)(2)(C) says the same for a meeting held under the emergency-powers article. The “instructions” are this form.
- CIV 5115(a) (elections of directors and recalls): “An association shall provide general notice of the procedure and deadline for submitting a nomination at least 30 days before any deadline for submitting a nomination. Individual notice shall be delivered pursuant to Section 4040 if individual notice is requested by a member.” And CIV 5115(b)(5): “Individual notice of the above paragraphs shall be delivered pursuant to Section 4040 if individual notice is requested by a member.”
- CIV 4920(c) (a board meeting): “Notice of a board meeting shall be given by general delivery pursuant to Section 4045.” 4920(d): “Notice of a board meeting shall contain the agenda for the meeting.”

**Which notices are “general notices”.** The Act does not list them in one place. The sections on the shelf that say “general notice” or “general delivery” include 4360(a) and (c) (a proposed rule change, and a rule change made), 4365(g) (the result of a member vote to reverse a rule change), 4741(f) (an amendment that removes a restricted rental covenant), 4920(c) (a board meeting), 5115(a), (b), and (d)(3) (election notices), and 5120(b) (“Within 15 days of the election, the board shall give general notice pursuant to Section 4045 of the tabulated results of the election”). The notice catalog (`jason notices --catalog`) is the list jason keeps, and the form’s “what this covers” block is read from it (section 5), not written by hand.

**What the Act does not say** (so the form does not say it either): when the request takes effect; whether it lasts until cancelled or lapses; whether a fee may be charged; what happens to a notice already begun. It does not make the posting or website method unnecessary: a general notice may still be given by the 4045(a) means, and the member’s individual delivery is the additional way, by the member’s choice.

## 2. Who uses it, and when

- **A member** (an owner of a separate interest, CIV 4160) who wants every general notice delivered to them by the method they chose for individual notices, instead of only by posting, a newsletter, or the website.
- **When:** any day of the year. The annual policy statement describes the option (4045(b), 5310(a)(4)); the annual form and the meeting notices point to it ([owner-information.md](owner-information.md); 4926 and 5450 reminders).
- **Who it is not for:** a member who wants to change the preferred method ([delivery-change.md](delivery-change.md)), add a second address ([secondary-address.md](secondary-address.md)), or get a copy of the minutes (CIV 4950(a): “distributed to any member upon request and upon reimbursement of the association’s costs”, a different right and clock).

## 3. What the form must carry

| # | What the law (or the standard) says the form carries | Words | Carried by |
|---|---|---|---|
| 1 | A request to receive general notices by individual delivery | 4045(b) | `request` |
| 2 | In writing, to the association, under 4035 | 5260(c), 4035 | signature or signed-in answer; fixed text with `{DESIGNATED_PERSON}`, `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}` |
| 3 | The request covers “all general notices” to the member | 4045(b) | fixed text “What this covers” (read from the notice catalog) |
| 4 | They are delivered by the member’s preferred method, else first-class mail to the address on the books | 4040(a)(1), (2) | fixed text, with the member’s current method printed beside it (not asked) |
| 5 | A request to cancel a prior request | 5260(c) | `request` option 2 |
| 6 | The annual policy statement describes the option | 4045(b), 5310(a)(4) | fixed text “Where we tell you about this”; not a question |
| 7 | The instructions a teleconference meeting notice promises | 4926(a)(1)(C); 5450(b)(2)(C) | the form itself, and its address and page, are what those notices point to |
| 8 | Who is asking, and for which unit | 4160 | `name`, `unit-address`, `capacity` |
| 9 | That a request in other words is still a request, and where to get help | standard 5 | fixed text |

## 4. The questions

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `name` | Your name | text | yes | 5260(c): a member’s request | NAME | request.requester |
| `unit-address` | Unit address | address | yes | places the member (4160); prefilled `UNIT_ADDRESS` | ADDRESS | request.unit |
| `capacity` | You are answering as | choice: “An owner of this unit”; “Someone the owner has authorized to answer” | yes | 5260; the attestation | TEXT | request.capacity |
| `request` | What do you want? | choice: “Deliver every general notice to me by the delivery method I chose”; “Cancel my earlier request” | yes | 4045(b); 5260(c) | TEXT | the member’s individual-general-notices flag, on or off (a member tag, proposed, created when first written; and a register row) |
| `attestation` | I am an owner of this unit, or I am authorized to answer for the owner, and what I have written is true | checkbox (one box) on PayHOA and PDF; the signature line on paper | yes | assurance ([forms.md](../forms.md), “Channels and assurance”) | TEXT | request.attested |
| (signature) | Signature of owner, and date | signature line, date | yes on paper and PDF; “signed in” online | 5260: “in writing” | NAME | request.signed |

Not asked, on purpose: where to send the notices (4045(b) fixes it: the delivery method the member chose), a reason, a phone number, an email address (never required, 4041(b)(2)(A); the member’s method is on the books), and the unit’s occupancy. The form prints the member’s method beside the question, from the books, so the member can see what “your method” means; if the member has none, the form says first-class mail goes to the address on the books (4040(a)(2)) and points to [delivery-change.md](delivery-change.md).

## 5. The recitals

| Token | Subdivisions | Why it opens the form |
|---|---|---|
| `{QUOTE:CIV 4045(b)}` | (b) | the right, and that it covers all general notices |
| `{QUOTE:CIV 4045(a)}` | (a) intro, (a)(1) | what a general notice is; the other ways it is given |
| `{QUOTE:CIV 4040(a)}` | (a)(1), (2) | what the member’s choice is |
| `{QUOTE:CIV 5260}` | (intro), (c) | the request is in writing to the association under 4035 |
| `{QUOTE:CIV 5310(a)(4)}` | (a)(4) | the annual statement describes the option |
| `{QUOTE:CIV 4920(c)}` | (c), (d) | meeting notices are general, and carry the agenda |

“What this covers”: a plain list of the general notices, each with its section, read from the notice catalog with the general-delivery rows only. A plain-words note may follow each recital, labeled “The association’s plain-words note; the words above control.”

## 6. What the member is told

The sentence the member reads (`member_clock`):

> Most notices to all members, such as notices of board meetings with their agendas, proposed rule changes, and election notices, may be posted or put on our website. If you ask, we will also deliver every one of them to you the way you chose to receive notices: by mail, by email, or both. If you have not chosen, we use first-class mail to the address on our books. We will start with every general notice we begin to deliver on or after the day we receive your request, and we will tell you in writing the day we received it. A notice we had already begun to deliver is not sent again. Your request stays until you cancel it with this form or you no longer own your unit. We charge nothing for it. Send it to {DESIGNATED_PERSON} at {RETURN_BY_MAIL} or {RETURN_BY_EMAIL}, or answer it online at {PORTAL}.

Reading (label: the association’s plain-words note and its proposed policy, not the statute): “from the day we receive”, “not sent again”, “stays until you cancel”, and “we charge nothing” are the proposed policy of section 7, rows 2, 4, 5. The Act is silent on each.

How to reconsider: there is no decision to reconsider. A member who finds a general notice was not delivered to them after the date received tells the contact; the association sends it. A member who disagrees may ask to meet and confer (CIV 5900 to 5920).

## 7. The association’s clocks

“Counted from” is the association’s receipt, stamped on the day it arrives (mail on the day opened; email and PayHOA on the day sent).

| # | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| 1 | receipt | acknowledge within 2 business days | PROPOSED POLICY (as `acknowledge_days=2`) | nothing in the law; the member is left without a date |
| 2 | receipt | effective for every general notice the association begins to deliver on or after the day received | PROPOSED POLICY (4045(b) does not say; “if a member requests” is read as from the request) | a notice goes by posting only to a member who asked |
| 3 | receipt | enter in the books within 5 business days; the handler reads unrecorded requests before each general-notice batch | PROPOSED POLICY | a batch goes without the member |
| 4 | the day a notice was begun | a notice begun before receipt is not resent; for a board meeting notice, the four days of 4920(a) (two days for a meeting held solely in executive session, 4920(b)(2); none for an emergency meeting, 4920(b)(1)) are not shortened for a late request | statute for the meeting-notice periods; PROPOSED POLICY for the rest | the Act’s notice periods are the association’s, whatever the request |
| 5 | receipt of a cancellation | stop on the day received; the flag is removed | statute (5260(c)); PROPOSED POLICY for the day | a member who cancelled keeps receiving individual copies |
| 6 | a transfer of title | the request ends with the member’s ownership; the new owner is a new member and is asked in the annual solicitation and the policy statement | PROPOSED POLICY (the Act is silent) | a new owner is delivered individual copies they did not ask for |
| 7 | each year, 30 to 90 days before the end of the fiscal year | the policy statement carries the 5310(a)(4) notice and the 4045(a)(3) and (a)(5) locations | statute, 5310(a) | the association has told no one the right exists |
| 8 | the day a general notice is begun | individual delivery to every member on the list, in the same batch process as any individual notice ([notices.md](../notices.md) for the delivery and its follow-ups) | statute, 4045(b) and 4040 | a notice is not “delivered pursuant to Section 4040” |

A “business day” is not defined on the shelf. PROPOSED POLICY: the association states the definition it uses on the form (`{BUSINESS_DAY_DEFINITION}`).

## 8. The acknowledgment text

> Reference {REFERENCE}. We received your request about general notices on {RECEIVED}. {DECIDER} records it; no one has to approve it. From {RECEIVED}, every general notice we begin to deliver will also be delivered to you by the way you chose to receive notices (shown on your record as: {CURRENT_METHOD}). To cancel this request, use the same form or write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference. We will enter your request in our records by {DUE}.

`{CURRENT_METHOD}` is the member’s preferred method on the books at the day received (“first-class mail to the address on our books” if there is none). For a cancellation the second and third sentences are replaced by “We stopped sending you general notices individually on {RECEIVED}.”

## 9. Channels and the reference

- **Channels:** paper, fillable PDF, email, PayHOA, portal. A signed-in PayHOA answer is `SIGNED_IN`; a reply email from the address on file is `MATCHED`; a signed paper copy is `CLAIMED`. A Google Form is not offered: the right belongs to a member, and an unsigned-in answer is a lead only.
- **Marker code proposed: `NV`** (notice, individual deliVery: the alphabet has no `I`, and `NI`, `NG`, and `NL` are outside it). Letters from the alphabet `0-9 A C E F H K M N P R T V X`; `NP` is the annual form, `NC` the delivery change, `NA` the second address; `NV` collides with no code found in `docs/` or `mystique/forms.py`. A standing form’s campaign is the year it was generated (`NV26M-…`, `NV26P-…`).
- The reference is a hint, never what the reading depends on ([form-identifiers.md](../form-identifiers.md)).

## 10. Profile slots

| Slot | What it is |
|---|---|
| `{ASSOCIATION}` | the association’s name |
| `{DESIGNATED_PERSON}` | the person the annual policy statement designates (4035(a); 5310(a)(1)); else the president or secretary |
| `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}` | where the request goes; naming an email address is the association’s assent to email delivery (4035(b)(1)) |
| `{BOARD_CONTACT}` | where to write about a disagreement |
| `{GENERAL_NOTICE_LOCATION}`, `{WEBSITE_LOCATION}` | the places the annual policy statement designates for general notices (4045(a)(3), (a)(5); 5310(a)(3)) |
| `{BUSINESS_DAY_DEFINITION}`, `{ACK_DAYS}`, `{ENTRY_DAYS}` | as in [delivery-change.md](delivery-change.md) |
| the general-notice tag | the profile’s name for the member tag the flag sets (proposed; created when first written) |

## 11. Handler and procedure

- **Handler:** `@handler("CIV 4045(b)", "CIV 5260", role=Role.FORM_RETURN, form="individual-delivery-request", procedure="delivery-requests", channels=(PAYHOA, GMAIL, MAIL))` ([arrivals-design.md](../arrivals-design.md)). `accepts` takes an arrival with this form’s marker (`NV`) or a PayHOA form id. `read` is evidence only. `plan` sets or clears the member’s individual-general-notices flag and a register row (who, unit, date received, on or off), nothing else; a register is the durable record because no tag has a date ([registers.md](../registers.md)).
- **What the flag does:** `jason delivery --notice KEY --ids ids.json` lists who receives a notice and how ([owner-information.md](../owner-information.md)). Each general-notice requirement in the notice catalog gains a recipient rule: the members whose flag is on, delivered by their method. A meeting notice, a rule-change notice, and an election notice then go as two batches: the general method (post or website) and the individual copies.
- **Procedure:** `delivery-requests` is proposed (see [delivery-change.md](delivery-change.md), section 11). Add the step for this form: **before each general notice, list the members with the flag on and deliver the notice to each by their method** (`jason notices REQUIREMENT --catalog` gives the requirement, the clock, and the recipients; the notice’s key and date name its batches, as `notice-delivery` already asks). `notice-delivery` and `election` are the nearest procedures today; `election` gains one line: the 5115 notices go individually to every member with the flag on.
- **Template change this needs:** a recipient rule in the notice catalog for “members who asked for individual delivery of general notices”, which the notice rows for 4920, 4360, 4365, 4741(f), 5115, and 5120 share.
- **jason never:** sends a notice on its own initiative, approves or denies the request, or edits an owner’s submission (AGENTS.md, Boundaries).

## 12. Edge cases

- **Co-owners.** Each is a member; the request is the member’s. One co-owner’s request covers only that owner’s notices; the other co-owner is not changed.
- **A representative.** A person with written authority may sign for the owner; the legal representative of 4041(a)(3) is a contact and does not make this request.
- **A tenant or another non-owner.** Not a member (4160). The association may send a tenant notices as a courtesy and says so; a tenant’s request is a courtesy request only. The owner may ask for individual delivery and share the notices.
- **A member with no valid delivery method.** 4040(a)(2): first-class mail to the address last shown on the books. Every general notice is then mailed to that member; the form says so, and the cost is the association’s (the Act sets no fee). For counsel if the board thinks otherwise (lead 3).
- **Language and accessibility.** The statutory words stay in English; large print, another format, a person to read the form aloud or write it down, and a reasonable accommodation are offered.
- **No form used.** An email or letter that says “send me all board notices” is a request. The handler reads it, asks once for what is missing, and the date received is the day it arrived.
- **The request is really something else.** “Send me the minutes” (4950(a), on request and reimbursement), “send me the agenda” (the agenda is part of the notice, 4920(d), so it is covered), “add me to the newsletter” (a courtesy list, not this form), “stop all email” (a delivery change). The handler routes it the same day and says which form it used.

## 13. Leads for the board and counsel

A reading is labeled as one and whose it is. A conflict between a document and the statute is noted, never resolved.

1. **Which notices are general.** 4045(b) says “all general notices to that member, given under this section”. The Act has no list; the catalog is jason’s reading of each section. A notice the catalog does not mark general is for a person to read. Counsel confirms the catalog’s general rows before the form’s “what this covers” list is printed.
2. **Late requests.** The Act sets no cut-off. A request received after a meeting notice went does not make the association resend it (the proposed policy); a request received before it does not extend the period (4920(a)). For the board.
3. **Cost of individual mail.** A member with no email who asks for individual delivery receives every general notice by first-class mail (4040(a)(2)). The Act sets no fee. Whether a charge could be reasonable is for counsel; the form states none.
4. **Does the request last?** The Act does not say. The proposal (until cancelled or title passes) keeps the right simple; the alternative (renewed each year with the 4041 solicitation) is a policy the board could adopt and say so in the annual statement.
5. **The annual policy statement.** 4045(b) and 5310(a)(4) require the statement to describe the option. Whether the current statement does is a check to run (`jason cite`; `jason notices --catalog`). The form does not satisfy 5310.
6. **The teleconference reminder.** 4926(a)(1)(C) and 5450(b)(2)(C) require “instructions on how to do so”. The meeting-notice template carries this form’s address and page; adding the instructions is a change to that template, not to this form.
7. **Executive session and emergency meetings.** 4920(b)(1) says no notice is required for an emergency meeting, and (b)(2) sets two days for a meeting held solely in executive session. Whether the individual copy of a general notice is owed in those cases is for counsel; the form promises “every general notice we begin to deliver”.
8. **Reading 5260(c) with 4045(b).** The first speaks of a request “to the member”; the second of “general notices to that member”. They read together to one right. No inconsistency is read here.

## 14. Test fixtures

Made-up answers. All use plainly fake data.

**Typical** (an owner asks for every general notice by email, and email is already their method):

| Field | Answer |
|---|---|
| `name` | A. Owner |
| `unit-address` | 123 Main St, Anytown, CA 90000 |
| `capacity` | An owner of this unit |
| `request` | Deliver every general notice to me by the delivery method I chose |
| `attestation` | ticked; signed 2026-03-02 |

Expected: the flag set on; a register row; acknowledgment with `{CURRENT_METHOD}` = by email; the next meeting notice goes to the member by email as well as to its posting.

**Minimal** (the smallest valid return): `name`, `unit-address`, `capacity`, `request`, signature.

**Edge cases:**
- A member whose books show no delivery method: acknowledgment says first-class mail to the address on the books; points to the change form.
- A cancellation: the flag cleared on the day received; “we stopped” acknowledgment.
- A request signed by a tenant: held as a lead; the owner is written to.
- A request received the day after a meeting notice went: effective for the next notice; the earlier notice is not resent.
- A request by an owner whose unit then transfers: the flag ends at the deed; the new owner has none.
- A photocopy with no marker: identified by printed lines; a person attaches it to its campaign.

**The statutory checklist test, in words.** (1) The recital block contains the exact words of 4045(b), 4045(a) (intro and (1)), 4040(a), 5260’s introduction and (c), 5310(a)(4), and 4920(c), each filled from the shelf, with the build failing if a cited subdivision is gone. (2) The form says the request covers “all general notices”. (3) The form offers a cancellation. (4) The form names the 4035 designee and an address. (5) The form prints the member’s method from the books and does not ask for an address or an email. (6) “What this covers” is read from the notice catalog’s general-delivery rows, and each row has a section the shelf holds. (7) The form asks no reason, no phone, no occupancy. (8) The acknowledgment carries `{RECEIVED}`, `{DUE}`, `{DECIDER}`, `{REFERENCE}`. (9) The same template renders paper, PDF, email, and PayHOA with the same questions in the same order, each carrying `NV`. (10) A made-up return of each fixture reads back to the same answers after a bad scan.
