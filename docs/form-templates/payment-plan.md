# Request to meet with the board about a payment plan

Status: design (2026-10-05). Key `payment-plan`; proposed marker code `PP`. It follows the standard in [form-templates.md](../form-templates.md). The inventory row is “Payment plan” ([standard-forms.md](../standard-forms.md)); the notice catalog row is `payment-plan-meeting` (CIV 5665); the request kind is `ResponseKind.PAYMENT_PLAN` with `assignment="collections"`. The form is sent with the pre-lien notice (CIV 5660(d)), which tells the owner of the right, so the owner has it in hand within the 15 days the section allows.

## 1. Authority and what the law requires

As of: the shelf’s 2025 session publication of the code (`data/authorities/CIV/CIV-5650-5690.md` and `CIV-4900-4955.md`, read with lawlibrary, 2026-10-05). None of these sections was amended in 2025 (5660 and 5665 were added by Stats. 2012, Ch. 180). jason’s copy is not an official restatement.

**CIV 5660** (the notice the request answers; the part that matters here):

> At least 30 days prior to recording a lien upon the separate interest of the owner of record to collect a debt that is past due under Section 5650, the association shall notify the owner of record in writing by certified mail of the following: ...
>
> (d) The right to request a meeting with the board as provided in Section 5665.

The ellipsis omits subdivisions (a) to (c), (e), and (f), which are the lien description and the 14-point warning (a), the itemized statement (b), the statement about a debt that was paid on time (c), the right to meet and confer (e), and the right to alternative dispute resolution (f).

**CIV 5665** (the request, the standards, the meeting, the plan; in full):

> (a) An owner, other than an owner of any interest that is described in Section 11212 of the Business and Professions Code that is not otherwise exempt from this section pursuant to subdivision (a) of Section 11211.7 of the Business and Professions Code, may submit a written request to meet with the board to discuss a payment plan for the debt noticed pursuant to Section 5660. The association shall provide the owners the standards for payment plans, if any exists.
>
> (b) The board shall meet with the owner in executive session within 45 days of the postmark of the request, if the request is mailed within 15 days of the date of the postmark of the notice, unless there is no regularly scheduled board meeting within that period, in which case the board may designate a committee of one or more directors to meet with the owner.
>
> (c) Payment plans may incorporate any assessments that accrue during the payment plan period. Additional late fees shall not accrue during the payment plan period if the owner is in compliance with the terms of the payment plan.
>
> (d) Payment plans shall not impede an association’s ability to record a lien on the owner’s separate interest to secure payment of delinquent assessments.
>
> (e) In the event of a default on any payment plan, the association may resume its efforts to collect the delinquent assessments from the time prior to entering into the payment plan.

**CIV 4935(a), (c), (e)** (the executive session, and the minutes):

> (a) The board may adjourn to, or meet solely in, executive session to consider litigation, matters relating to the formation of contracts with third parties, member discipline, personnel matters, or to meet with a member, upon the member’s request, regarding the member’s payment of assessments, as specified in Section 5665.
>
> (c) The board shall adjourn to, or meet solely in, executive session to discuss a payment plan pursuant to Section 5665.
>
> (e) Any matter discussed in executive session shall be generally noted in the minutes of the immediately following meeting that is open to the entire membership.

**CIV 5655(a), (b)** (how a payment is applied, and the receipt):

> (a) Any payments made by the owner of a separate interest toward a debt described in subdivision (a) of Section 5650 shall first be applied to the assessments owed, and, only after the assessments owed are paid in full shall the payments be applied to the fees and costs of collection, attorney’s fees, late charges, or interest.
>
> (b) When an owner makes a payment, the owner may request a receipt and the association shall provide it. The receipt shall indicate the date of payment and the person who received it.

**CIV 5690** (what follows if the association does not follow the article’s procedures):

> An association that fails to comply with the procedures set forth in this article shall, prior to recording a lien, recommence the required notice process. Any costs associated with recommencing the notice process shall be borne by the association and not by the owner of a separate interest.

**CIV 5215(a)(5)(B)** (what the association keeps from another member who asks for records): “Records of disciplinary actions, collection activities, or payment plans of members other than the member requesting the records.”

Cited, not recited: CIV 5310(a)(6), (7) (the annual policy statement carries the association’s collection policies); 5673 (the board’s decision to record a lien is made in an open meeting); 5675 (the lien); 5650(b) (the late charge and interest limits).

Not on the shelf (listed in the report): BPC 11212 and 11211.7 (the interests 5665(a) leaves out).

**What the law does not say** (leads in section 13): how a request sent other than by mail is counted; whether a lien may be recorded before the meeting; whether the association must state its standards in writing; what interest does during a plan; whether a committee of directors meets “in executive session”; what the board must decide at the meeting (the section requires a meeting, not a grant).

## 2. Who uses it, and when

- **An owner** who has received the notice before a lien (5660) and wants to discuss paying the debt in instalments. The right is for “the debt noticed pursuant to Section 5660”.
- When: **within 15 days of the postmark of the notice**, for the 45-day meeting duty to apply (5665(b)). The form goes out with the notice so that the owner has it in that time.
- Where it is offered: with the pre-lien notice (5660(d), and the enclosure), in the annual policy statement’s collection statement (5310(a)(6), (7)), and in a reminder letter.
- Not served: an owner who disputes the charge ([disputed-charge.md](disputed-charge.md)); an owner who wants to meet and confer about the debt ([idr-request.md](idr-request.md), which the association “shall not refuse” and which 5670 requires the association to offer before a lien); an owner who has been told of no debt (no 5660 notice has been sent: the association may still discuss a plan, but the 15- and 45-day clocks are not the statute’s).

## 3. What the form must carry

| # | What the law says the form or request carries | Words | Carried by |
|---|---|---|---|
| 1 | A written request to meet with the board to discuss a payment plan | 5665(a) “may submit a written request to meet with the board to discuss a payment plan” | `request` (a checkbox, required); signature |
| 2 | For the debt noticed under 5660 | 5665(a) “for the debt noticed pursuant to Section 5660” | `notice-date` (optional), the form’s fixed text naming the notice |
| 3 | The date the request is mailed, for the 15-day window and the 45-day meeting | 5665(b) “mailed within 15 days of the date of the postmark of the notice”; “within 45 days of the postmark of the request” | `date-sent` |
| 4 | The association provides the standards for payment plans, if any exist | 5665(a) “shall provide the owners the standards for payment plans, if any exists” | fixed block `{PAYMENT_PLAN_STANDARDS}` printed on or sent with the form, or the statement that none exist |
| 5 | The meeting is in executive session; a committee of directors may stand in if no regular meeting is scheduled | 5665(b); 4935(c) | fixed text |
| 6 | What a plan may contain: accruing assessments; no new late fees while the owner complies | 5665(c) | fixed text; `include-accruing` |
| 7 | A plan does not stop the association from recording a lien | 5665(d) | fixed text |
| 8 | On a default, the association may resume collection from before the plan | 5665(e) | fixed text |
| 9 | A receipt on request for each payment; the order a payment is applied | 5655(a), (b) | fixed text |
| 10 | An email only if the owner chooses email | 4041(b)(2)(A); standard 2 | `email` |
| 11 | A request in other words is still a request; help | standard 5 | fixed text |

## 4. The questions

Kinds: text, choice, checkbox, email, phone, address, paragraph, date. “Required” says when; the template needs `required_if` ([records-request.md](records-request.md), section 11).

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `name` | Your name | text | yes | the owner | NAME | request.requester |
| `unit-address` | Unit address | address | yes | the notice was addressed to the owner of record for the unit | ADDRESS (prefilled on a copy) | request.unit |
| `request` | I ask to meet with the board to discuss a payment plan for the debt in the notice the association sent me | checkbox (one box) | yes | 5665(a) | TEXT | request.plan_requested = present |
| `notice-date` | The date on the notice about unpaid assessments, if you have it | date | no | 5665(b): the 15 days run from the postmark of the notice; the association knows its own date, so this only helps match the notice | TEXT | request.notice_date |
| `date-sent` | The date you mailed or delivered this request | date | yes | 5665(b): the 45 days run from the postmark of the request | TEXT | request.sent |
| `contact-method` | How should we reach you to set the meeting? | choice: “By email”; “By phone”; “By mail” | yes | 5665(b): the board “shall meet with the owner” | TEXT | request.contact_method |
| `email` | Email address | email | only if `contact-method` is email | 4041(b)(2)(A): never otherwise | EMAIL | request.email (on the request only) |
| `phone` | Phone number | phone | only if `contact-method` is phone | as above | PHONE | request.phone (on the request only) |
| `mailing-address` | Mailing address | address | only if `contact-method` is mail | 4040(a) | ADDRESS; “Same as my unit address” box | request.mail_to |
| `proposal` | What payment plan would you like to discuss? (optional) | paragraph | no | 5665(a): the request is “to discuss a payment plan” | TEXT | request.proposal |
| `include-accruing` | I ask that the plan include the assessments that come due while it runs | checkbox (one box) | no | 5665(c): “Payment plans may incorporate any assessments that accrue during the payment plan period.” | TEXT | request.include_accruing |
| `availability` | Days and times that suit you for the meeting | paragraph | no | 5665(b): the meeting is within 45 days; the board needs the owner’s times | TEXT | request.availability |
| (signature) | Signature and date | signature line, date | yes | a written request (5665(a)) | NAME | request.signed |

Not asked, on purpose: the owner’s income, hardship, employment, bank, or reasons for the debt (the law asks none; the board may talk about them at the meeting); the amount of the debt (the association knows it); whether the owner is a timeshare owner (the association knows what the interest is); a deposit or a first payment (5665 sets no condition on a request).

## 5. The recitals

| Token | Subdivisions | Why it opens the form |
|---|---|---|
| `{QUOTE:CIV 5665(a)}` | (a) | the right to ask, and the standards |
| `{QUOTE:CIV 5665(b)}` | (b) | the 15 days and the 45 days, executive session, the committee |
| `{QUOTE:CIV 5665(c)}` | (c) | what a plan may include; late fees |
| `{QUOTE:CIV 5665(d)}` | (d) | the lien is not stopped |
| `{QUOTE:CIV 5665(e)}` | (e) | a default |
| `{QUOTE:CIV 4935(c)}` | (c) | executive session |
| `{QUOTE:CIV 5655(a)}` | (a) | how payments are applied |
| `{QUOTE:CIV 5655(b)}` | (b) | the receipt |

The pre-lien notice recites 5660 itself; this form recites only what the owner needs after the notice.

## 6. What the member is told

> If you want to talk about a payment plan for the debt in the notice we sent you, ask the board in writing. For the board to meet you within the time the law sets, your request must be mailed within 15 days of the date the notice was postmarked. The board will meet with you in executive session within 45 days of the postmark of your request (Civil Code 5665(b)). If no regular board meeting falls in that time, the board may name one or more directors to meet with you instead. The meeting is private; the board notes only generally in its next open minutes that it was held (Civil Code 4935(e)). Here are the association’s standards for payment plans: {PAYMENT_PLAN_STANDARDS}. A payment plan may include assessments that come due while it runs, and late fees do not add up during the plan if you keep to its terms (Civil Code 5665(c)). A plan does not stop the association from recording a lien (Civil Code 5665(d)). If you do not keep to the plan, the association may go back to collecting from where it left off (Civil Code 5665(e)). Your payments are applied first to assessments (Civil Code 5655(a)); you may ask for a receipt for any payment (Civil Code 5655(b)). The meeting is a conversation about a plan; the law does not oblige the board to agree to the plan you propose. If you do not agree with a charge, you may ask to meet and confer, or pay it under protest. If the association does not meet with you in time, tell {BOARD_CONTACT}; before it records a lien the association must follow the article’s procedures, and if it has not it must start the notice process again at its own cost (Civil Code 5690).

Reading (the association’s plain-words note; the words of the sections are above): the sentence that the law does not oblige the board to agree to a plan states that 5665(b) requires a meeting and 5665(a) a discussion, and says nothing of a grant. The last sentence points at 5690 and labels the consequence as the statute states it.

## 7. The association's clocks

| # | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| 1 | receipt | acknowledge within 2 business days, with the standards if they were not sent with the notice | PROPOSED POLICY | none in the law |
| 2 | the postmark of the notice | the owner’s window: the request is mailed within 15 days | statute: 5665(b) | the 45-day duty is not triggered by its words; the board may still meet (PROPOSED POLICY, section 13, lead 4) |
| 3 | the postmark of the request | the board meets with the owner in executive session “within 45 days” | statute: 5665(b), 4935(c) | the association has not followed a procedure of the article; before recording a lien it “shall ... recommence the required notice process” at its own cost (5690; reading, section 13, lead 2) |
| 4 | the postmark of the request | if no regular board meeting falls in the 45 days: the board “may designate a committee of one or more directors” | statute: 5665(b) | as row 3 |
| 5 | the meeting | a written plan (or a written decision not to agree) within 5 business days | PROPOSED POLICY | the owner has no record of the terms; a default cannot be shown on a plan that was never written |
| 6 | the plan’s start | no additional late fees “if the owner is in compliance with the terms” | statute: 5665(c) | a late fee charged to an owner in compliance is a charge the owner may protest ([disputed-charge.md](disputed-charge.md)) |
| 7 | a default | the association “may resume its efforts to collect the delinquent assessments from the time prior to entering into the payment plan” | statute: 5665(e) | none: the right is the association’s |
| 8 | the meeting | the matter is “generally noted in the minutes of the immediately following meeting that is open to the entire membership” | statute: 4935(e) | an omission in the minutes |
| 9 | the pre-lien notice | the lien is not recorded for at least 30 days after the notice (5660); the association also holds the lien until the owner’s meeting is held and its result is on the record | statute (the 30 days); PROPOSED POLICY (the hold) | see section 13, lead 2 |

## 8. The acknowledgment text

> Reference {REFERENCE}. We received your written request to meet with the board about a payment plan on {RECEIVED}. The request was dated {SENT}. The board will meet with you in executive session by {DUE}, which is 45 days from the postmark of your request. {DECIDER} will contact you to set a time. Our standards for payment plans are enclosed, or: the association has no written standards for payment plans. If you want to change your request, write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.

`{DUE}` is `{SENT}` plus 45 days (the postmark date if the handler can verify it; the date the request was sent otherwise). If the request is late (more than 15 days after the notice’s postmark), the acknowledgment says so, and says the association will still schedule the meeting (the proposed policy, section 13), so the owner is not left with silence.

## 9. Channels and the reference

- **Channels:** paper, fillable PDF, email, PayHOA, portal. The statute speaks of mailing and a postmark (5665(b)); the form accepts a request on any channel, with the sent date. A PayHOA request is `SIGNED_IN` and carries its own date; an email request is `MATCHED` and carries its header date; a paper request is `CLAIMED`, with its postmark read from the envelope when the mail service gives it (the Mailroom scan may not).
- **Marker code proposed: `PP`** (payment plan). No collision found. The blank is a campaign marker; it is mailed with the pre-lien notice, so the blank enclosed in a notice is pre-filled with that owner’s unit and carries a copy marker (`PP26M-4RK9T-C7`), so the return is tied to the notice that offered it.
- The reference is a hint; the form is recognized by its heading and its citation `CIV 5665`.

## 10. Profile slots

| Slot | What it is |
|---|---|
| `{ASSOCIATION}` | the association’s name |
| `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}` | where the request goes |
| `{BOARD_CONTACT}` | who sets the meeting |
| `{PAYMENT_PLAN_STANDARDS}` | the association’s written standards for payment plans, or the statement that it has none (5665(a): “if any exists”) |
| `{BOARD_MEETING_CALENDAR}` | the regular meetings, so the handler can see whether one falls within the 45 days |
| `{COMMITTEE_RULE}` | who the board names for a committee under 5665(b) |
| `{FEE_SCHEDULE}` | the late charge and interest the plan counts (5650(b)) |
| `{ACK_DAYS}` | the proposed acknowledgment days |

## 11. Handler and procedure

- **Handler:** `@handler("CIV 5665", role=Role.REQUEST, form="payment-plan", procedure="payment-plan")`. It accepts an arrival that is this form (`PP`) or is classified `ResponseKind.PAYMENT_PLAN` (the kind rule matches “payment plan”). `plan` finds the owner’s 5660 notice in the collection record, computes the 15-day window and the 45-day day, checks whether a regular meeting falls inside, drafts the acknowledgment, and puts “meet in executive session” or “name a committee” on the board’s agenda. It marks a request outside the window, and a request with no 5660 notice, for a person. It does not decide a plan, set terms, or record a lien. The existing `RESPONSE_RULES` row (`PAYMENT_PLAN`, `notice="payment-plan-meeting"`, `assignment="collections"`) covers the clock.
- **Procedure:** none exists. Add `payment-plan`: (1) stamp the receipt and the date sent; (2) find the notice and check the 15 days; (3) acknowledge with the standards; (4) look at the board’s calendar against the 45 days, and decide between the board and a committee; (5) hold any lien step; (6) after the meeting, the written plan and its signatures; (7) note the matter generally in the next open minutes (4935(e)); (8) track compliance and default. The collection procedure and the pre-lien procedure add the enclosure of this form to the notice as a step; no procedure key for collections exists in `src/jason/community/procedures.py`.
- **jason never:** agrees to a plan, sets its terms, or records a lien (AGENTS.md; the board decides a lien in an open meeting, 5673).

## 12. Edge cases

- **Co-owners.** Each is an “owner”; the notice goes to every owner of record, and any may ask. The plan is signed by all who are on the debt.
- **A representative.** An owner may ask a person to help; 5665 does not say whether anyone besides the owner attends the executive session. PROPOSED POLICY: the owner may bring one person, at the owner’s choice, and the board may have its manager and counsel; the board adopts it (lead 5).
- **A tenant.** Not an owner; the debt is the owner’s (5650(a)). A tenant who calls is told the association can speak only to the owner.
- **A minor.** Not asked; counsel.
- **Language and accessibility.** The statutory words are English; a plain-words note may be translated. A meeting by phone or video, an interpreter, and any reasonable accommodation are offered on the form.
- **A request that arrives without the form.** A letter or an email asking for a payment plan is a request. The handler fills the fields from it, and the clock runs from its date.
- **A request that is really something else.** “I cannot pay” by phone is not a written request; the handler writes it down, sends the form, and reminds the owner of the 15 days. A request to dispute the amount goes to [disputed-charge.md](disputed-charge.md) or [idr-request.md](idr-request.md). A request for the owner’s own ledger is [records-request.md](records-request.md). A request after a lien is recorded is not within 5665(b)’s words; the board decides whether to meet.
- **No 5660 notice has been sent.** The request is not “for the debt noticed pursuant to Section 5660”; the association may talk about a plan, and the handler records that the statutory clocks do not run.
- **A time-share owner.** 5665(a) leaves out an owner of an interest described in BPC 11212 that is not exempt under 11211.7(a); those sections are not on the shelf. The handler asks a person.

## 13. Leads for the board and counsel

Drift: none found. The notice catalog’s `payment-plan-meeting` row (45 days from the postmark of the request, if mailed within 15 days of the notice; executive session; a committee when no regular meeting falls in the period) and the `RESPONSE_RULES` `PAYMENT_PLAN` row agree with the shelf. The catalog’s executive-session note cites 4935(c), which on the shelf says “shall adjourn to, or meet solely in, executive session to discuss a payment plan pursuant to Section 5665.”

Leads (open questions; none settled here):

1. **Channels other than mail.** 5665(b) counts from “the postmark of the request”. A request sent by email or PayHOA has no postmark. Reading (the association’s, proposed): the date it is sent, as shown by the system, stands in for the postmark. Counsel confirms. The shorter date is used.
2. **The lien and the meeting.** 5660 requires 30 days’ notice before a lien; 5665(b) allows 45 days from the postmark of the request to hold the meeting, which can end after the 30 days; 5665(d) says a plan “shall not impede an association’s ability to record a lien”. The sections do not say a lien waits for the meeting. PROPOSED POLICY: no lien is recorded until the meeting is held, or the 45 days have passed, whichever is first, with the board’s decision on the record (5673). A lien recorded without the meeting may be a failure to follow “the procedures set forth in this article”, which 5690 answers by requiring the notice process to start again at the association’s cost; whether 5665(b) is such a procedure is a reading for counsel.
3. **Written standards.** 5665(a) says the association shall provide standards “if any exists”. The law does not require the association to have any. The axiom of jason is to write down what the law leaves open (AGENTS.md): the board is invited to adopt written standards (a proposed skeleton follows), so the plans are handled the same way each time, which is the board’s best answer to a claim of selective treatment. PROPOSED standards skeleton for the board to adopt, change, or reject: the term of a plan (a maximum number of months); the instalment as a share of the debt; assessments that come due during the plan are paid as they come due, or are folded into the instalment (5665(c)); late fees do not accrue while the owner complies (5665(c), statute); the owner’s default and the association’s right to resume (5665(e), statute); a written plan signed by the owner and a director; an inspection of the plan’s status each quarter. None of these is adopted by this page.
4. **A late request.** A request mailed more than 15 days after the notice is outside 5665(b)’s words. PROPOSED POLICY: the board treats it the same way, and meets within the same 45 days where it can; it records that the request was late. The board adopts it, since a consistent practice is the board’s record of good faith.
5. **Who attends.** 5665(b) says “The board shall meet with the owner in executive session”. Who else may attend (a spouse, a lawyer, an advisor) is open. PROPOSED POLICY, above. Counsel reads it.
6. **Interest during a plan.** 5665(c) says “Additional late fees shall not accrue during the payment plan period if the owner is in compliance with the terms of the payment plan.” It says nothing of interest (5650(b)(3) allows interest at not more than 12 percent). Whether interest continues to run is open; reading for counsel. The plan’s written terms should say.
7. **A committee.** 5665(b) lets the board designate “a committee of one or more directors”. Whether such a meeting is “in executive session” (4935(c)) and how it is minuted is for counsel.
8. **What the board must decide.** The section requires a meeting, and a plan “may” be made. A board that refuses a plan has met its duty under 5665(b); the owner’s other routes are meet and confer (5670 requires the association to offer it before a lien) and alternative dispute resolution (5660(f)).
9. **Privacy.** The meeting, the plan, and the records are held back from other members’ requests (5215(a)(5)(B)); the minutes note the matter generally (4935(e)).

## 14. Test fixtures

**Typical** (an owner asks 8 days after the notice, by email):

| Field | Answer |
|---|---|
| `name` | A. Owner |
| `unit-address` | 123 Main St |
| `request` | checked |
| `notice-date` | 2026-09-20 |
| `date-sent` | 2026-09-28 |
| `contact-method` | By email |
| `email` | a.owner@example.test |
| `proposal` | Twelve monthly payments |
| `include-accruing` | checked |
| `availability` | Evenings |
| signature | A. Owner, 2026-09-28 |

Expected: no problems; the request is inside the window; `{DUE}` = 2026-11-12 (45 days from 2026-09-28); the board’s agenda gets “meet in executive session”; the standards are in the acknowledgment.

**Minimal:**

| Field | Answer |
|---|---|
| `name` | A. Owner |
| `unit-address` | 123 Main St |
| `request` | checked |
| `date-sent` | 2026-09-28 |
| `contact-method` | By mail |
| `mailing-address` | 123 Main St |
| signature | A. Owner |

Expected: no email, no proposal, no times; the handler asks nothing more.

**Edge** (a late request, with no regular board meeting in the 45 days, from co-owners):

| Field | Answer |
|---|---|
| `name` | B. Owner and C. Owner |
| `unit-address` | 456 Elm St |
| `request` | checked |
| `notice-date` | 2026-08-30 |
| `date-sent` | 2026-09-22 |
| `contact-method` | By phone |
| `phone` | (555) 010-0100 |
| signature | B. Owner, C. Owner |

Expected: the request is 23 days after the notice, so outside the 15 days; the handler marks it for a person and, under the proposed policy, schedules the meeting anyway; because the board’s calendar has no regular meeting in the 45 days, the handler proposes a committee of one or more directors (5665(b)); the acknowledgment says the request was late and that the association will still meet.

**The statutory checklist test, in words.** (a) Each row of section 3 names its authority and its carrier; (b) the `request` question exists, is required, and its words say the owner asks to meet with the board about a payment plan for the debt in the notice; (c) the form cannot be generated unless `{PAYMENT_PLAN_STANDARDS}` is filled, either with the standards or with the statement that none exist (standard 7); (d) the rendered form recites 5665(b)’s “within 45 days of the postmark of the request” and “within 15 days of the date of the postmark of the notice” exactly; (e) the clock for the meeting equals 45 days and the window equals 15 days as the section states; (f) `email` is required exactly when `contact-method` is email; (g) no question asks the owner’s income, hardship, or the reason for the debt; (h) every recital token resolves against the shelf and names an existing subdivision. The scan and marker tests are as in [records-request.md](records-request.md).
