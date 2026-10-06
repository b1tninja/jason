# Request for reconsideration (`reconsideration-request`)

Status: design (2026-10-05); built in the form library as `ca/reconsideration.py` (version 1, as of 2026-10-04). Form key `reconsideration-request`, marker code `RC`, authority `CIV 4765(a)(5)` (and `CIV 4766(e)` for a rebuild appeal). The standard it follows is [../form-templates.md](../form-templates.md). It is the second half of [architectural-application.md](architectural-application.md): the same office, the same procedure (`improvement-request`), the same workflow ([../improvement-requests.md](../improvement-requests.md), reused here and not changed). The charger, solar, and protected-use forms ([ev-charger.md](ev-charger.md), [solar.md](solar.md), [protected-use-application.md](protected-use-application.md)) send a disapproved applicant here too.

Quotations are from the statutes on jason's authorities shelf (`data/authorities/CIV/`), which are not official restatements. A reading is labeled as one and is never the rule.

## 1. Authority and what the law requires

**As-of.** The shelf's 2025 session publication of the Civil Code, exported 2026-10-04 (jason holds one edition of the law). The form's recital line says "as on jason's shelf of 2026-10-04. jason's copy is not an official restatement."

**CIV 4765, the paragraphs that make the entitlement:**

> **(a)(1)** The association shall provide a fair, reasonable, and expeditious procedure for making its decision. The procedure shall be included in the association’s governing documents. The procedure shall provide for prompt deadlines. The procedure shall state the maximum time for response to an application or a request for reconsideration by the board.
>
> **(a)(4)** A decision on a proposed change shall be in writing. If a proposed change is disapproved, the written decision shall include both an explanation of why the proposed change is disapproved and a description of the procedure for reconsideration of the decision by the board.
>
> **(a)(5)** If a proposed change is disapproved, the applicant is entitled to reconsideration by the board, at an open meeting of the board. This paragraph does not require reconsideration of a decision that is made by the board or a body that has the same membership as the board, at a meeting that satisfies the requirements of Article 2 (commencing with Section 4900) of Chapter 6. Reconsideration by the board does not constitute dispute resolution within the meaning of Section 5905.
>
> **(a)(2)** A decision on a proposed change shall be made in good faith and may not be unreasonable, arbitrary, or capricious.

(Paragraph (a)(2) applies to the reconsideration decision too: it is "a decision on a proposed change".)

**CIV 4766, the appeal for a rebuild after a disaster** (the paragraphs this form carries; the whole section is quoted in [architectural-application.md](architectural-application.md#1-authority-and-what-the-law-requires)):

> **(e)(1)** If an application is determined to be incomplete pursuant to subdivision (b) or determined to be noncompliant pursuant to subdivision (d), the body shall provide a process for the applicant to appeal that decision pursuant to Section 4765.
>
> **(e)(2)** The body shall provide a final written determination on the appeal no later than 60 calendar days after receipt of the applicant’s written appeal.
>
> **(f)(1)** Once a body approves an application pursuant to this section, the body shall not subject the applicant to any appeals or additional hearings.
>
> **(f)(2)** The prohibition described in paragraph (1) does not apply to the applicant’s noncompliance with the approved application.

**CIV 4900 to 4955, the open meeting the reconsideration is held at** (only the subdivisions the form uses):

> **4910(a)** The board shall not take action on any item of business outside of a board meeting.
>
> **4920(a)** Except as provided in subdivision (b), the association shall give notice of the time and place of a board meeting at least four days before the meeting.
>
> **4920(c)** Notice of a board meeting shall be given by general delivery pursuant to Section 4045.
>
> **4920(d)** Notice of a board meeting shall contain the agenda for the meeting.
>
> **4925(a)** Any member may attend board meetings, except when the board adjourns to, or meets solely in, executive session. As specified in subdivision (b) of Section 4090, a member of the association shall be entitled to attend a teleconference meeting or the portion of a teleconference meeting that is open to members, and that meeting or portion of the meeting shall be audible to the members in a location specified in the notice of the meeting.
>
> **4925(b)** The board shall permit any member to speak at any meeting of the association or the board, except for meetings of the board held in executive session. A reasonable time limit for all members of the association to speak to the board or before a meeting of the association shall be established by the board.
>
> **4930(a)** Except as described in subdivisions (b) to (e), inclusive, the board may not discuss or take action on any item at a nonemergency meeting unless the item was placed on the agenda included in the notice that was distributed pursuant to subdivision (a) of Section 4920. This subdivision does not prohibit a member or resident who is not a director from speaking on issues not on the agenda.
>
> **4930(d)(3)** The item appeared on an agenda that was distributed pursuant to subdivision (a) of Section 4920 for a prior meeting of the board that occurred not more than 30 calendar days before the date that action is taken on the item and, at the prior meeting, action on the item was continued to the meeting at which the action is taken.
>
> **4935(a)** The board may adjourn to, or meet solely in, executive session to consider litigation, matters relating to the formation of contracts with third parties, member discipline, personnel matters, or to meet with a member, upon the member’s request, regarding the member’s payment of assessments, as specified in Section 5665.
>
> **4950(a)** The minutes, minutes proposed for adoption that are marked to indicate draft status, or a summary of the minutes, of any board meeting, other than an executive session, shall be available to members within 30 days of the meeting. The minutes, proposed minutes, or summary minutes shall be distributed to any member upon request and upon reimbursement of the association’s costs for making that distribution.

**What the law requires of this form and of the procedure behind it (the association's plain-words note, not the statute's):**

- A disapproved applicant is entitled to reconsideration by the board, at an open meeting. The entitlement does not depend on a reason or on new information (4765(a)(5)). The form therefore never makes a stated ground a condition.
- The procedure states the maximum time the board has to respond to a request for reconsideration (4765(a)(1)). The form states it.
- The board acts only at a meeting, on an item that was on the agenda in the notice (4910(a), 4930(a)); the notice goes out at least four days before and contains the agenda (4920(a), (d)). An application is not a subject 4935(a) lists, so it is heard in open session ([../improvement-requests.md](../improvement-requests.md#the-board-stage)).
- The member may attend and may speak, subject to a reasonable time limit the board sets (4925(a), (b)).
- For a rebuild, the process and the 60-calendar-day final written determination are the statute's (4766(e)); once approved, there are no further appeals or hearings (4766(f)).

**What the law leaves silent:** the time the applicant has to ask; whether a request may follow an approval with conditions; whether the ordinary application has an appeal from an "incomplete" finding; whether a second reconsideration is available; the time to deliver the written answer after the vote. Each is a proposed policy in section 7, labeled.

## 2. Who uses it, and when

- **Who.** An applicant whose proposed change was disapproved, or the owner's authorized representative. The applicant is the person the application named; any co-owner of record may ask (section 12).
- **When.** After the written decision. The decision letter (the base template `architectural-decision`, which carries the reconsideration description 4765(a)(4) asks for) encloses this form or links to it, with the original reference filled in.
- **Also, as proposed policies and for a rebuild:** an approval whose conditions the applicant asks the board to look at again; and, for a rebuild, an incomplete or noncompliant finding the applicant appeals (4766(e)(1)); the form's `decision_kind` question sets which.
- **Not this form.** A new application with changed plans (`request_kind` offers it and routes it to [architectural-application.md](architectural-application.md), where the clocks start again). A request to meet and confer about a dispute (the internal dispute resolution form; 4765(a)(5) says reconsideration "does not constitute dispute resolution within the meaning of Section 5905", so the two are separate). A reasonable accommodation request (its own form). A complaint about how a decision was reached (a question for the board and counsel).

## 3. What the form must carry

| # | The form must carry | Authority | Carried by |
|---|---|---|---|
| R1 | Which decision is to be reconsidered: the unit, the decision's date, and the reference | 4765(a)(5) ("a proposed change is disapproved") | `unit`, `decision_date`, `reference` |
| R2 | Who is asking, and authority if not the owner | the applicant's entitlement (4765(a)(5)); 4041(a)(3) | `owner_name`, `submitted_by`, `rep_authorization` |
| R3 | What kind of decision it was (disapproved; approved with conditions; for a rebuild, incomplete or noncompliant) | 4765(a)(5); 4766(e)(1) | `decision_kind` |
| R4 | That the board will reconsider at an open meeting, and which | 4765(a)(5); 4920 | the panel (section 6); `{NEXT_MEETING}` |
| R5 | **The board's maximum response time**, the procedure's | 4765(a)(1) | not a question: the panel, from `{MAX_DAYS_RECONSIDERATION}` |
| R6 | What the applicant would like looked at again: optional | none; helps preparation; never a condition | `what_to_look_at` |
| R7 | New or changed plans: optional; and the choice to make it a new application | 4766(d)(3), (d)(4) for a rebuild; the documents | `new_material`, `request_kind` |
| R8 | That the meeting is open; the right to attend and to speak; the time limit; the agenda link | 4925(a), (b); 4920(d) | the panel; `attend_how`, `meeting_help` |
| R9 | The written answer: delivery route | 4765(a)(4) | `decision_delivery`, `contact_email` |
| R10 | For a rebuild: the written appeal, the 60 calendar days, no appeals once approved | 4766(e), (f) | `decision_kind` (rebuild choices); the rebuild panel |
| R11 | Signature and date; help; "not the only door" | the standard | signature line; `help_needed`; help panel |

## 4. The questions

| key | Question (plain words) | kind | required | why (authority) | reads as | sets |
|---|---|---|---|---|---|---|
| `unit` | The address of your unit | short | yes | places the decision (prefilled on an enclosed copy) | address | the request it follows |
| `reference` | The reference on your decision letter or on the form you sent | short | no | ties it to the application; the unit and date are enough without it | text | the original `ImprovementRequest` |
| `owner_name` | Owner's name (each owner of record) | short | yes | the applicant's identity | name | applicant |
| `submitted_by` | Who is sending this? The owner / a co-owner / someone the owner authorized in writing | choice | yes | authority to ask | option key | applicant role |
| `rep_authorization` | I am attaching the owner's written authorization | checkbox | when not the owner | a representative acts for the owner | option key | authority on file |
| `decision_date` | The date on the letter that disapproved it | date | yes | which decision; counts the proposed request window | date | the decision it follows |
| `decision_kind` | What did the letter say? My change was disapproved / My change was approved, with conditions I ask the board to look at again / My rebuild application was found incomplete / My rebuild application was found not compliant / I am not sure | choice | yes | 4765(a)(5), "if a proposed change is disapproved"; 4766(e)(1) | option key | the track and the clock (ordinary or rebuild appeal) |
| `request_kind` | What do you want? Please reconsider the same application / I changed my plans; please treat this as a new application | choice | yes | 4766(d)(3), (d)(4); the documents; changes the clock | option key | reconsideration or a new application |
| `what_to_look_at` | What would you like the board to look at again? (You do not need to give a reason.) | paragraph | no | helps the board prepare; 4765(a)(5) makes reconsideration an entitlement | text | the brief's facts (the applicant's words) |
| `new_material` | I am attaching new or changed plans or information | checkbox | no | the board may weigh it; for a rebuild a resubmission has its own clock (4766(d)(3), (d)(4)) | option key | attachments |
| `attend_how` | How do you plan to take part? In person / by phone or video / I would rather not attend / not sure | choice | no | the right to attend and speak (4925(a), (b)); a teleconference notice carries the instructions (4926) | option key | the meeting plan |
| `meeting_help` | I need help to take part (an accessible room, a phone line, an interpreter) | checkbox | no | the standard (help on the form) | option key | an accommodation lead |
| `decision_delivery` | How should we send the written answer? By mail to the unit / by mail to another address / by email | choice | yes | the decision is in writing (4765(a)(4)); an email is required only if you choose it (4041(b)(2)(A)) | option key | delivery route |
| `contact_email` | Your email address | email | only if `decision_delivery` is email | delivery by email | email | contact (P2) |
| `help_needed` | I need this form in another format, in larger print, in another language, or help filling it in | checkbox | no | the standard | option key | an accommodation lead |
| (signature) | Signature of owner (or authorized representative), and the date | signature | yes | proof of who asked | text | signed on |

The form asks nothing about the reason for the disapproval, a person's health, or a tenant; the association has the decision. The attestation reads: "I am the owner of this unit, or I am authorized by the owner to send this. What I have written is true to the best of my knowledge. I understand the board will consider this at an open meeting that members may attend."

## 5. The recitals

Opened by token, with the subdivision it is and the line "as on jason's shelf of 2026-10-04" (statute targets are the proposed spelling of [../notices.md](../notices.md), until the extension is built):

1. `{QUOTE:CIV#4765(a)(5)}`
2. `{QUOTE:CIV#4765(a)(1)}` (the last two sentences carry the maximum time)
3. `{QUOTE:CIV#4765(a)(4)}`
4. `{QUOTE:CIV#4925(b)}` (the right to speak)
5. `{QUOTE:CIV#4920(a)}` (the four days' notice)
6. For `decision_kind` of a rebuild kind: `{QUOTE:CIV#4766(e)(1)}`, `{QUOTE:CIV#4766(e)(2)}`, `{QUOTE:CIV#4766(f)(1)}`

## 6. What the member is told

> **You asked on {RECEIVED}.**
>
> **What you are asking for.** You are asking the board to look again at its decision on the change at {UNIT_ADDRESS}. The Civil Code says that if a change is disapproved, the applicant is entitled to ask the board to reconsider, at an open meeting. You do not need a new reason to ask.
>
> **Who decides and where.** {DECIDER} decides, at a board meeting that is open to members. The next meeting that can be noticed in time is **{NEXT_MEETING}**, at {MEETING_PLACE}{TELECONFERENCE_HELP}. The agenda is on the notice of the meeting, which is given at least four days before the meeting; the agenda item names your unit and the kind of change in general words, and not your name. {AGENDA_LINK}
>
> **You may come and you may speak.** Any member may attend, and the board permits any member to speak, within a reasonable time limit it sets ({TIME_LIMIT_TO_SPEAK} per speaker). The meeting is open, so what is said about your change is said where other members can hear it. If you would rather not attend, say so on the form; the board will still decide.
>
> **How long the board has.** Your procedure says the board answers a request for reconsideration within **{MAX_DAYS_RECONSIDERATION} days** of the day it receives the request ({PROCEDURE_CITATION}). {WHOSE_RECONSIDERATION_CLOCK}.
>
> **The answer.** The board's answer is in writing, and we send it within {ANSWER_DELIVERY_DAYS} days of the vote (a proposed target). If the board again disapproves, the letter says why. It also says whether any further step is available under our procedure, and it does not use up your other rights, such as asking to meet and confer about a dispute.
>
> **If we do not act in time.** The Civil Code does not say what follows if the board does not act on a request for reconsideration in time. Your procedure says: {SILENCE_RULE}. If it says nothing, write to {BOARD_CONTACT}; the item goes on the next agenda.
>
> **Not the only door.** You do not have to use this form. A letter or an email that says "please reconsider the decision on {UNIT_ADDRESS}" is a request, and our time starts the day we get it.
>
> **Help.** Ask {BOARD_CONTACT} for another format, larger print, another language, help filling this in, or help taking part in the meeting.

**The rebuild panel** (shown for the rebuild kinds): "If your application to rebuild after a declared disaster was found incomplete or not compliant, you may appeal. We give you a final written determination within **60 calendar days** of your written appeal (Civil Code 4766(e)(2)); this form is your written appeal. Once an application is approved, the board may not subject you to any appeals or additional hearings, except for not complying with what was approved (4766(f)). A new application that fixes what we found is treated as a new application with its own timelines, and is made on the architectural application (4766(d)(3), (d)(4)). Your reading of these rules is yours; a lawyer can help you with it."

**What follows if the association does not act:** for an ordinary request, the Act states nothing (section 7). For a rebuild the Act states no deemed result either; 4766(g) says "A court shall award reasonable attorney’s fees to the applicant who prevails in an action to enforce this section."

## 7. The association's clocks

| Clock | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| Acknowledgment | the day the request is received | proposed 3 business days | PROPOSED POLICY (`improvement-review-time`) | a finding for the manager |
| The applicant's window to ask | the date of the written decision | proposed 30 calendar days | PROPOSED POLICY (`improvement-reconsideration`); the Act states none | a later request is taken at the board's discretion, or as a new application; counsel reads whether a window narrows the entitlement (section 13) |
| The board's response to a request | the day the request is received | the documents' maximum (4765(a)(1) requires them to state it); else proposed: the first open meeting that can be noticed, and no later than 45 calendar days | documents; PROPOSED POLICY where silent (`improvement-reconsideration`) | a finding for the board; a special meeting is the board's choice; no statutory consequence stated for an ordinary request |
| Notice of the meeting that hears it | the meeting | at least four days before; general delivery; the agenda in the notice | statute (4920(a), (c), (d)) | the board may not discuss or act on an item not on the agenda, except as 4930(b) to (e) allow (4930(a)) |
| A continued item | the first meeting | the next meeting not more than 30 calendar days later | statute (4930(d)(3)) | beyond 30 calendar days it needs a new agenda item |
| Rebuild appeal: final written determination | the day the written appeal is received | 60 calendar days | statute (4766(e)(2)) | no deemed result is stated; fees under 4766(g); counsel |
| The written answer delivered | the vote | proposed 7 calendar days | PROPOSED POLICY (`improvement-reconsideration`) | a finding for the manager |
| Minutes available to members | the meeting | 30 days | statute (4950(a)) | the minutes are late; `jason notices` shows it |

"Which meeting meets the clock" is computed from `MeetingSchedule` and `Community.board_notice_period()`: the last scheduled open meeting on or before the due day, and the day its notice must go out. Where none falls in time, the item says so ("No scheduled meeting falls before the due day: a special meeting, or the policy's pause") and the choice is the board's ([../improvement-requests.md](../improvement-requests.md#the-clocks)). The notice catalog has an `architectural-decision` row and no row for the reconsideration answer or for the rebuild's 45-day review and 60-day appeal; the rows to add are in section 11.

## 8. The acknowledgment

> We received your request to reconsider the decision of {DECISION_DATE} on {UNIT_ADDRESS} on **{RECEIVED}**. Your reference is **{REFERENCE}**.
>
> {DECIDER} will consider it at an open board meeting. The next meeting that can be noticed in time is **{NEXT_MEETING}**; the agenda is posted with the notice of that meeting ({AGENDA_LINK}). You may attend and speak. Under {PROCEDURE_CITATION} the board answers within {MAX_DAYS_RECONSIDERATION} days, which is **{DUE}**. We will send you the answer in writing.
>
> If you told us you need help to take part, we will contact you about it before the meeting.
>
> [Rebuild only] Because this is an appeal of a rebuild determination, the final written determination is due within 60 calendar days of today, **{DUE}**.
>
> This says only that we have your request and when. It is not a decision.

## 9. Channels and the reference

- **Channels:** an enclosure with the decision letter (the usual way: a copy with the unit, the decision date, and the original reference filled in), the fillable PDF, an emailed copy, the PayHOA form, the portal page; and plain words in any channel.
- **The marker code: `RC`** (reconsideration). The enclosed copy differs for each applicant (it carries the request it follows), so an emailed or individually printed enclosure takes a **copy marker** (`RC27E-xxxxx-xx`). A blank copy (the PayHOA form, a form picked up or downloaded) takes the campaign marker (`RC27M-xx`, `RC27P-xx`), and the applicant writes the unit and the decision's date. The copy marker names the unit it was made for; the reference of the original application is kept beside it, not inside it.
- **Collision check.** Codes in `docs/form-templates/` on 2026-10-05: `RR` (records-request), `NC` (delivery-change), `MN` (membership-list), `AP` (architectural-application); `NP` is the built owner-information form. `RC` is unused. All are letters of the alphabet `0-9 A C E F H K M N P R T V X`.
- **The marker is a hint.** A reply in the decision letter's email thread is recognized by the subject's reference or by the cited authority `CIV 4765(a)(5)`; a missing marker changes only the copy.

## 10. Profile slots

| Slot | What | Where |
|---|---|---|
| `{ASSOCIATION}`, `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}`, `{BOARD_CONTACT}` | standard | the profile |
| `{PROCEDURE_CITATION}` | the section of the documents with the reconsideration procedure | the `architectural-review` citation purpose |
| `{MAX_DAYS_RECONSIDERATION}`, `{WHOSE_RECONSIDERATION_CLOCK}`, `{SILENCE_RULE}` | the number with its source word, and what the documents say if the board does not act | `Community.response_rules()` for `ResponseKind.RECONSIDERATION` (`ClockSource.DOCUMENTS` or `POLICY`) |
| `{RECON_REQUEST_DAYS}` | the window to ask, if the documents or an adopted policy state one; empty means none is stated | the profile |
| `{ANSWER_DELIVERY_DAYS}` | days from the vote to the written answer | the profile (proposed policy) |
| `{DECIDER}`, `{NEXT_MEETING}`, `{MEETING_PLACE}`, `{AGENDA_LINK}` | the board; the computed meeting; its place; the link to the notice and agenda | the profile; `MeetingSchedule`; the notice ledger |
| `{TELECONFERENCE_HELP}` | where the meeting is entirely by teleconference, the 4926(a)(1) instructions and the help contact | the profile |
| `{TIME_LIMIT_TO_SPEAK}` | the board's reasonable time limit for speakers (4925(b)) | the profile |

**How this form relates to the owner's existing printed application.** A community's printed application often has a line or a paragraph that says how to ask the board to reconsider. That wording is the profile's input: it names the procedure, the board's time, and where to send the request. The base form is generated from that input and the law, so the member sees the community's own steps in the law's frame (the entitlement, the open meeting, the maximum time, and the help panel). Where the printed wording differs from the documents' procedure, the documents govern (4205), and the generator lists the difference for a person.

## 11. Handler and procedure

- **Handler.** `@handler("CIV 4765(a)(5)", role=Role.REQUEST, form="reconsideration-request", procedure="improvement-request", channels=(PAYHOA, GMAIL, MAIL, FORMS))`, and `@handler("CIV 4766(e)", role=Role.REQUEST, procedure="improvement-request")` for the rebuild appeal. A reply to a decision letter that says "please reconsider" with no form is routed to the same handler by its subject reference or cited section.
- **Procedure: `improvement-request`** (it does not exist yet; its steps are in [architectural-application.md](architectural-application.md#11-handler-and-procedure)). The step to add is **"Reconsideration"**: (1) enter the request against the original, set its received day, and acknowledge (a draft a person sends); (2) read the decision's date against the window the profile states; a late request is not refused, it is a question for the board; (3) compute the meeting that meets the clock; (4) make the board item with the unit and kind of change in general words; it goes in open session (4935(a) does not list an application); (5) the decision brief: the question, the recited standards, the lettered options (affirm; reverse; approve with conditions; continue to a named meeting within 30 calendar days; refer), the facts, with the applicant's words shown as the applicant's; (6) the board's vote is recorded by an officer as a second `Decision`, linked to the first (`<date>--<item>--reconsider`); (7) a person sends the written answer and records where and when. The step names the lessons it comes from once there are any.
- **Notice catalog rows to add** (`src/jason/community/notice_catalog.py`; this page proposes, it changes nothing): `architectural-reconsideration` (CIV 4765, applicant, written, counted from `Anchor.RECONSIDERATION_REQUESTED`, "within the maximum time the procedure states"; elements: the decision, if disapproved why); `disaster-rebuild-review` (CIV 4766(c), 45 calendar days from `Anchor.APPLICATION_COMPLETE`); `disaster-rebuild-appeal` (CIV 4766(e)(2), 60 calendar days from `Anchor.APPEAL_RECEIVED`). The anchors are the three the workflow page adds.
- **`ResponseKind.RECONSIDERATION`** (proposed) with a `KindRule` on the form's name and on the words "reconsider" and "reconsideration" beside a prior decision, and a `ResponseRule` of `ClockSource.DOCUMENTS` or `POLICY`; its `first_step`: "Put it on the next open meeting that can be noticed."
- jason never decides the request, never sets a status that says approved or denied, and never sends the answer.

## 12. Edge cases

| Case | What the form and the handler do |
|---|---|
| **Co-owners** | Any owner of record may ask; the answer goes to every owner of record. If the owners disagree, the association records the request it received. |
| **A representative** | Accepted with the owner's written authorization; the answer goes to the owner, with a copy to the representative the owner named. Without the authorization the request is received and the manager asks for it; the board is not made to wait for it to be late. |
| **A tenant asking** | A tenant is not the applicant. The answer says how the owner may ask. The form does not ask about tenancy. |
| **A contractor submitting** | Received; the owner is asked to confirm in writing; the answer goes to the owner, never to a contractor alone. |
| **A change the insurer must see** | The form gives no coverage advice. The decision letter's statement of what an approval is and is not (the base template) carries over. |
| **A request that is really a variance** | If the documents have a variance procedure, the profile's variance form is offered beside this one, never instead; the reconsideration is heard on its own item, and the board may take the variance as a separate item. |
| **It arrives without the form** | A letter, an email, or a PayHOA message saying "please reconsider" is a request; its received day is the day it arrives. |
| **Language and accessibility** | Another format, large print, translation, help filling it in, and help taking part in the meeting are on the form; a teleconference notice carries instructions (4926(a)(1)); a reasonable accommodation request is welcome with it. |
| **A late request** | Not refused by jason. The window is a proposed policy; the board decides whether to hear it, or to treat it as a new application. |
| **A second request after reconsideration** | The Act speaks of "reconsideration" and states no second. The final letter says what the association's procedure offers; the board decides whether to hear a second request on new material, which is a new application. |
| **The board's own decision at a qualifying meeting** | 4765(a)(5) says reconsideration is not required in that case; the form offers it anyway (section 13, reading (b)). |
| **An applicant who is a director** | Recorded as recused by the secretary on the director's disclosure; jason infers none. |
| **The applicant wants it private** | The meeting is open and 4935(a) does not list an application. The panel says so before the applicant relies on privacy. A possible violation is a discipline matter on its own path (5855), not here. |
| **The board wants more information** | It may continue the item to a named meeting not more than 30 calendar days later (4930(d)(3)); the written answer then follows the later vote; the maximum time still runs unless the board adopts a written pause. |

## 13. Leads for the board and counsel

1. **The applicant's window.** *jason's reading:* 4765(a)(5) makes reconsideration an entitlement on disapproval and states no deadline to ask; 4765(a)(1) requires the procedure to state a maximum time for the **board's** response. A deadline for the applicant is the board's policy. Whether a short window narrows an entitlement the statute states without one is a question for counsel; a window at least as long as the proposed 30 calendar days, with late requests heard at the board's discretion, is the cautious course. A rule on this subject is a procedure on subject 4355(a)(6) and needs general notice at least 28 days before the board makes the rule change (4360(a)).
2. **Reading (b), reused.** 4765(a)(4) asks the disapproval to describe the reconsideration procedure, and (a)(5) says reconsideration is not required of a decision the board itself made "at a meeting that satisfies the requirements of Article 2". Two readings remain: that the letter describes the procedure the association has (which may be a request at the next open meeting), or that a decision made at a qualifying meeting needs none. The form offers reconsideration either way; the board asks counsel.
3. **"A body that has the same membership as the board."** A committee with different membership that decides an application is not within that sentence, so reconsideration by the board is owed; a committee with the board's membership meeting under Article 2 is within it. The form does not read which a decision was; the profile's deciders row says.
4. **Approved with conditions.** The statute speaks of a disapproval. Whether an applicant may ask the board to reconsider a condition is a policy choice (proposed: yes). Counsel reads whether a condition so heavy that it defeats the change is a disapproval.
5. **An incomplete finding on an ordinary application.** 4766(e)(1) gives an appeal from an incomplete determination for a rebuild. The Act gives none for an ordinary application; the proposed policy offers one (the same process). The board adopts it or not.
6. **What the second decision must say.** 4765(a)(4) requires a description of the reconsideration procedure "if a proposed change is disapproved", and the reconsideration decision is a decision on a proposed change. Whether the description is required again after reconsideration, and whether a second reconsideration is available, are two readings; the proposed letter says what the association's procedure offers next and that other rights are not used up. Counsel reads it.
7. **Open meeting and privacy.** The discussion is in open session and the minutes are available to members within 30 days (4950(a)). The agenda and the open packet name the unit and the kind of change in general words; the applicant's phone number, contractor, and plans stay in the directors' packet ([../improvement-requests.md](../improvement-requests.md#privacy-and-visibility)). Whether a member inspecting minutes sees the applicant's identity is for counsel. A member who is denied a right under the Act's open-meeting article may sue within one year (4955(a)).
8. **4766(d)(1) and (e) together.** The text speaks of remedying within "the time limits specified in subdivision (b)", which are times for the body. A rebuild applicant may either appeal under (e) or submit a new application under (d)(3) and (d)(4); the form lets the applicant choose (`request_kind`). Counsel reads which clocks run while both are open.
9. **Conflict notes (not resolved).** Where the documents state a reconsideration time that is longer than the board can meet on a four-day-notice schedule, or none, the gap is a board matter, not a `Conflict` row; where the documents bar reconsideration of a board decision and the board still offers it, no provision is disobeyed.
10. **Statutes this page points at and the shelf does not hold:** Government Code 12900 and following (the Fair Employment and Housing Act, named in 4765(a)(3)). Civil Code 4090(b), which 4925(a) points to for teleconference meetings, is on the shelf and is a pointer here, not a recital.

## 14. Test fixtures

Made-up answers; the unit is "123 Main St"; the owner is "A. Owner".

**Typical** (ordinary, disapproved): `unit` 123 Main St; `reference` AP27M-xx (the original); `owner_name` A. Owner; `submitted_by` the owner; `decision_date` 2026-10-03; `decision_kind` my change was disapproved; `request_kind` please reconsider the same application; `what_to_look_at` "The board said the new fence is too tall; I would like it to look at a lower fence."; `attend_how` by phone or video; `decision_delivery` by mail to the unit; signature A. Owner, 2026-10-10.

**Minimal** (no form): an email "Please reconsider the decision of Oct 3 on 123 Main St. A. Owner." Expected: entered with the received day; the acknowledgment draft states the meeting that meets the clock and the maximum time; the checklist lists nothing as incomplete (every item other than the decision's identity is optional).

**Edge** (rebuild appeal by a representative): `unit` 123 Main St; `submitted_by` an authorized representative with `rep_authorization`; `decision_kind` my rebuild application was found incomplete; `request_kind` please reconsider the same application; `new_material` checked; `meeting_help` checked; `help_needed` checked (large print); `decision_delivery` by email with `contact_email` owner@example.com. Expected: the rebuild panel is shown; the 60-calendar-day final written determination is computed from the received day and shown with its source word "statute"; the answer is addressed to the owner with a copy to the representative; the help items are queued; the item is the board's, in open session.

**The statutory checklist test, in words.** The generated form passes when:

1. It recites `4765(a)(5)` and states the entitlement without making a reason or new material a condition.
2. It states the board's maximum response time to a request for reconsideration, with its source word, equal to the profile's procedure row (4765(a)(1)); a profile with none is refused with the missing row named.
3. It says the board hears it at an open meeting, gives the next meeting that can be noticed in time (four days, 4920(a)), says the notice carries the agenda, and says the member may attend and speak within a reasonable time limit (4925(a), (b)).
4. It says the answer is in writing and states what the answer will say if the board again disapproves.
5. For the rebuild kinds it carries the 60 calendar days (4766(e)(2)), the written-appeal statement, and the end of appeals once approved (4766(f)).
6. No question asks for an email address unless email is chosen as the delivery route, for a person's health, or for a tenant.
7. Every question has a `why`; the recitals resolve against the shelf and fail the build when a subdivision moves.
8. The marker `RC` round-trips; the scan test reads the enclosed copy after a bad scan and never confuses it with `RR`, `AP`, or another form.
9. The generated form names its handler and procedure; one with no registered handler is refused.
