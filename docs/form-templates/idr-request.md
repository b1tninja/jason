# Request to meet and confer (internal dispute resolution)

Status: design (2026-10-05). Key `idr-request`; proposed marker code `MC` (meet and confer). It follows the standard in [form-templates.md](../form-templates.md). The inventory row is “Internal dispute resolution” ([standard-forms.md](../standard-forms.md)); the notice catalog row is `meet-and-confer` (CIV 5915); the request kind is `ResponseKind.DISPUTE`. The form that exists today is `FormKey.IDR` (the profile’s `mystique/forms.py`); this design replaces it and records where it has drifted (section 13). The next step after this one, if it fails, is [adr-request.md](adr-request.md).

## 1. Authority and what the law requires

As of: the shelf’s 2025 session publication of the code (`data/authorities/CIV/CIV-5900-5920.md`, read with lawlibrary, 2026-10-05). None of these sections was amended in 2025 (5910 and 5915 by Stats. 2015, Ch. 303; 5910.1 by Stats. 2019, Ch. 848). jason’s copy is not an official restatement.

**CIV 5900** (what the article reaches):

> (a) This article applies to a dispute between an association and a member involving their rights, duties, or liabilities under this act, under the Nonprofit Mutual Benefit Corporation Law (Part 3 (commencing with Section 7110) of Division 2 of Title 1 of the Corporations Code), or under the governing documents of the common interest development or association.
>
> (b) This article supplements, and does not replace, Article 3 (commencing with Section 5925), relating to alternative dispute resolution as a prerequisite to an enforcement action.

**CIV 5905** (the procedure, and the default):

> (a) An association shall provide a fair, reasonable, and expeditious procedure for resolving a dispute within the scope of this article.
>
> (b) In developing a procedure pursuant to this article, an association shall make maximum, reasonable use of available local dispute resolution programs involving a neutral third party, including low-cost mediation programs such as those listed on the Internet Web sites of the Department of Consumer Affairs and the United States Department of Housing and Urban Development.
>
> (c) If an association does not provide a fair, reasonable, and expeditious procedure for resolving a dispute within the scope of this article, the procedure provided in Section 5915 applies and satisfies the requirement of subdivision (a).

**CIV 5910** (the minimum, in full):

> A fair, reasonable, and expeditious dispute resolution procedure shall, at a minimum, satisfy all of the following requirements:
>
> (a) The procedure may be invoked by either party to the dispute. A request invoking the procedure shall be in writing.
>
> (b) The procedure shall provide for prompt deadlines. The procedure shall state the maximum time for the association to act on a request invoking the procedure.
>
> (c) If the procedure is invoked by a member, the association shall participate in the procedure.
>
> (d) If the procedure is invoked by the association, the member may elect not to participate in the procedure. If the member participates but the dispute is resolved other than by agreement of the member, the member shall have a right of appeal to the board.
>
> (e) A written resolution, signed by both parties, of a dispute pursuant to the procedure that is not in conflict with the law or the governing documents binds the association and is judicially enforceable. A written agreement, signed by both parties, reached pursuant to the procedure that is not in conflict with the law or the governing documents binds the parties and is judicially enforceable.
>
> (f) The procedure shall provide a means by which the member and the association may explain their positions. The member and association may be assisted by an attorney or another person in explaining their positions at their own cost.
>
> (g) A member of the association shall not be charged a fee to participate in the process.

**CIV 5910.1** (what follows if the association does not take part):

> An association may not file a civil action regarding a dispute in which the member has requested dispute resolution unless the association has complied with Section 5910 by engaging in good faith in the internal dispute resolution procedures after a member invokes those procedures.

**CIV 5915** (the default procedure, in full):

> (a) This section applies to an association that does not otherwise provide a fair, reasonable, and expeditious dispute resolution procedure. The procedure provided in this section is fair, reasonable, and expeditious within the meaning of this article.
>
> (b) Either party to a dispute within the scope of this article may invoke the following procedure:
>
> (1) The party may request the other party to meet and confer in an effort to resolve the dispute. The request shall be in writing.
>
> (2) A member of an association may refuse a request to meet and confer. The association shall not refuse a request to meet and confer.
>
> (3) The board shall designate a director to meet and confer.
>
> (4) The parties shall meet promptly at a mutually convenient time and place, explain their positions to each other, and confer in good faith in an effort to resolve the dispute. The parties may be assisted by an attorney or another person at their own cost when conferring.
>
> (5) A resolution of the dispute agreed to by the parties shall be memorialized in writing and signed by the parties, including the board designee on behalf of the association.
>
> (c) A written agreement reached under this section binds the parties and is judicially enforceable if it is signed by both parties and both of the following conditions are satisfied:
>
> (1) The agreement is not in conflict with law or the governing documents of the common interest development or association.
>
> (2) The agreement is either consistent with the authority granted by the board to its designee or the agreement is ratified by the board.
>
> (d) A member shall not be charged a fee to participate in the process.

**CIV 5920** (the annual description, in full):

> The annual policy statement prepared pursuant to Section 5310 shall include a description of the internal dispute resolution process provided pursuant to this article.

**CIV 5310(a)(9)** (the same, in the policy statement’s list):

> (9) A summary of dispute resolution procedures, pursuant to Sections 5920 and 5965.

**Where the form is offered besides the annual policy statement.** CIV 5660(e), the notice before a lien: the notice states “The right to dispute the assessment debt by submitting a written request for dispute resolution to the association pursuant to the association’s ‘meet and confer’ program required in Article 2 (commencing with Section 5900) of Chapter 10.” CIV 5670: “Prior to recording a lien for delinquent assessments, an association shall offer the owner and, if so requested by the owner, participate in dispute resolution pursuant to the association’s ‘meet and confer’ program required in Article 2 (commencing with Section 5900) of Chapter 10.” The form is also the document the annual policy statement points to and the document the hearing, application, and collection letters name as the way to dispute a decision.

**What the law does not say** (leads in section 13): the maximum time (5910(b) requires the *procedure* to state it; 5915 states none, only “promptly”); when the board designates; whether a director designated in one dispute may serve in another; how an association invokes the procedure against a member; what “engaging in good faith” requires beyond showing up.

## 2. Who uses it, and when

- **A member** who has a dispute with the association about rights, duties, or liabilities under the Act, the Nonprofit Mutual Benefit Corporation Law, or the governing documents (5900(a)): a fine, an architectural decision, a charge, a rule’s meaning, a records request, a failure to maintain.
- **The association** may also invoke the procedure against a member (5910(a), 5915(b)); that is a letter the association sends, generated from this template (section 6), and the member’s reply is stage 2 of the template.
- When: any time a dispute exists. Offered in the annual policy statement (5920), in the pre-lien notice (5660(e)), before a lien is recorded (5670), and in any letter that denies an application or imposes a charge, so that a member sees it where the dispute begins.
- Not served: a dispute between two members with no claim against the association (5900(a) says “between an association and a member”; the association may still offer help, reading, section 12); a request for records ([records-request.md](records-request.md)); a request for a payment plan ([payment-plan.md](payment-plan.md)); the owner’s notice that a charge is paid under protest ([disputed-charge.md](disputed-charge.md), which may ask for this too).

## 3. What the form must carry

| # | What the law says the form or request carries | Words | Carried by |
|---|---|---|---|
| 1 | The request is in writing | 5910(a); 5915(b)(1) | the form; signature |
| 2 | A request that the association meet and confer to resolve the dispute | 5915(b)(1) “request the other party to meet and confer in an effort to resolve the dispute” | fixed text heading; `dispute` |
| 3 | The association cannot refuse | 5915(b)(2) “The association shall not refuse a request to meet and confer.” | fixed text (recital) |
| 4 | The board designates a director | 5915(b)(3) | fixed text; the acknowledgment’s `{DECIDER}` |
| 5 | The meeting is prompt, at a mutually convenient time and place, and each side explains its position | 5915(b)(4); 5910(f) | `availability`, `meeting-place` |
| 6 | Either side may be assisted at its own cost | 5910(f); 5915(b)(4) | `assisted-by` |
| 7 | No fee | 5910(g); 5915(d) | fixed text |
| 8 | An agreement is in writing and signed by both, including the designee, and binds if lawful and within the designee’s authority or ratified | 5915(b)(5), (c) | fixed text |
| 9 | The maximum time for the association to act | 5910(b) | fixed text with `{IDR_MAX_DAYS}` (a profile slot; proposed in section 7) |
| 10 | If the association invoked it: the member may elect not to take part; if the member takes part and the dispute is not resolved by the member’s agreement, a right of appeal to the board | 5910(d) | stage 2 `participate`; fixed text |
| 11 | A request in other words is still a request; help | standard 5 | fixed text |

## 4. The questions

Kinds: text, choice, checkbox, email, phone, address, paragraph, date. “Required” says when; the template needs `required_if` ([records-request.md](records-request.md), section 11).

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `name` | Your name | text | yes | the member (5900(a)) | NAME | request.requester |
| `unit-address` | Unit address | address | yes | places the member | ADDRESS (prefilled on a copy) | request.unit |
| `contact-method` | How should we reach you to set the meeting? | choice: “By email”; “By phone”; “By mail” | yes | 5915(b)(4) “mutually convenient time and place” needs a way to ask | TEXT | request.contact_method |
| `email` | Email address | email | only if `contact-method` is email | 4041(b)(2)(A): never otherwise | EMAIL | request.email (on the request only) |
| `phone` | Phone number | phone | only if `contact-method` is phone | as above | PHONE | request.phone (on the request only) |
| `mailing-address` | Mailing address | address | only if `contact-method` is mail | 4040(a) | ADDRESS; “Same as my unit address” box | request.mail_to |
| `dispute` | What is the dispute about? (a few sentences) | paragraph | yes | 5915(b)(1): the request is “in an effort to resolve the dispute”; the designee must know the dispute | TEXT | request.dispute |
| `outcome` | What would resolve it for you? | paragraph | no | 5915(b)(4): the parties “explain their positions” | TEXT | request.outcome |
| `related-notice` | Is this about something the association sent you? | choice: “A notice about unpaid assessments”; “A notice of a violation or a hearing”; “A decision on an application”; “Something else, or nothing”  | no | 5670 (the association offers it before a lien); 5910.1 | TEXT | request.related (routes to the collection or discipline record; a person confirms) |
| `availability` | Days and times that suit you | paragraph | no | 5915(b)(4) | TEXT | request.availability |
| `meeting-place` | Where you would like to meet (in person at the association’s office, by phone, or by video) | choice: “In person”; “By phone”; “By video” | no | 5915(b)(4) “time and place” | TEXT | request.meeting_mode |
| `assisted-by` | A person who will help you at the meeting (a lawyer or another person, at your cost), if any | text | no | 5910(f); 5915(b)(4) | NAME | request.assisted_by |
| (signature) | Signature and date | signature line, date | yes | 5910(a): in writing | NAME | request.signed |

Stage 2, the member’s reply when the **association** invoked the procedure (a copy pre-filled with the dispute the association states):

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `participate` | The association asks to meet and confer about the dispute described above | choice: “I will take part”; “I choose not to take part” | yes | 5910(d): “the member may elect not to participate” | TEXT | request.participation |
| `reply-contact` | How should we reach you? | as `contact-method` | if taking part | 5915(b)(4) | TEXT | as above |
| (signature) | Signature and date | signature line | yes | in writing | NAME | request.signed |

Not asked, on purpose: why the member does not want to take part; the member’s finances; whether a lawyer is retained (5910(f) allows one at the member’s cost; the member is asked only to name the helper); a phone number or an email unless the member picks it.

## 5. The recitals

| Token | Subdivisions | Why it opens the form |
|---|---|---|
| `{QUOTE:CIV 5915(b)}` | (b)(1) to (5) | the request, “shall not refuse”, the designee, the meeting, the writing |
| `{QUOTE:CIV 5915(c)}` | (c)(1), (2) | when an agreement binds |
| `{QUOTE:CIV 5915(d)}` | (d) | no fee |
| `{QUOTE:CIV 5910}` | (a), (b), (d), (f), (g) | the minimum: written request, time to act, appeal, positions, no fee |
| `{QUOTE:CIV 5910.1}` | whole | what follows if the association does not take part |
| `{QUOTE:CIV 5900(a)}` | (a) | what disputes it covers |
| `{QUOTE:CIV 5920}` | whole | the annual description; the annual policy statement carries the same words |

The form’s plain-words note, labeled as the association’s: “The association must meet with you if you ask. It cannot charge you.”

## 6. What the member is told

> The association cannot refuse your request to meet and confer. It will not charge you a fee. The board will designate a director to meet with you promptly, at a time and place that suits you both, to hear your side and explain the association’s. Either of you may bring a lawyer or another person to help, at your own cost. If you reach an agreement, it will be written down and signed by you and the director; it binds you both if it is lawful and within the authority the board gave the director, or the board ratifies it. We will act on your request within {IDR_MAX_DAYS}. If the meeting does not resolve the dispute, you may ask the board to look at it again, ask to use alternative dispute resolution (Civil Code 5925 to 5965), or go to court, including small claims court when the amount is within its limit. If the association starts the process with you, you may choose not to take part; if you do take part and the dispute is not settled by your agreement, you may appeal to the board.

Reading (the association’s plain-words note; the statute’s words are above): the last sentence on appeal restates 5910(d), which gives the right only when the association invoked the procedure; for a member-invoked request the statutes give no appeal, so the paragraph names the other routes.

## 7. The association's clocks

| # | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| 1 | receipt | acknowledge within 2 business days | PROPOSED POLICY | none in the law |
| 2 | receipt | the association’s maximum time to act on a request invoking the procedure: `{IDR_MAX_DAYS}`; proposed: 30 calendar days to the meeting, unless both agree to later in writing | the association’s procedure (documents or board policy) where it has one: 5910(b) “shall state the maximum time”; otherwise 5915 (“promptly”) and this PROPOSED POLICY | if the association has no procedure that meets 5910, 5915 applies (5905(c)); a member whose request is ignored may go on to ADR and court, and the association “may not file a civil action regarding a dispute in which the member has requested dispute resolution” unless it has engaged in good faith (5910.1) |
| 3 | receipt | the board designates a director: within 5 business days; PROPOSED POLICY (5915(b)(3) says “The board shall designate a director”, no time) | PROPOSED POLICY | the meeting cannot be set; row 2 keeps running |
| 4 | the designation | the director contacts the member to set the meeting within 3 business days | PROPOSED POLICY | as row 3 |
| 5 | the meeting | a resolution is “memorialized in writing and signed by the parties, including the board designee” (5915(b)(5)); no time is stated; PROPOSED: the director’s written summary within 5 business days | statute (the duty); PROPOSED POLICY (the time) | no binding agreement |
| 6 | the signed agreement | the board ratifies at its next meeting unless it is “consistent with the authority granted by the board to its designee” (5915(c)(2)) | statute; PROPOSED POLICY for “next meeting” | the agreement binds only if the second condition is met |
| 7 | the annual statement | the policy statement carries the description (5920; 5310(a)(9)) 30 to 90 days before the fiscal year’s end (5310(a)) | statute | a statement without it fails 5310(a) |
| 8 | the pre-lien notice | the offer of meet and confer before a lien is recorded (5670), and the notice’s own statement (5660(e)) | statute | the notice process is recommenced at the association’s cost (5690) (reading: 5670 is in the article 5690 names; counsel) |

## 8. The acknowledgment text

> Reference {REFERENCE}. We received your written request to meet and confer about a dispute on {RECEIVED}. The association does not refuse a request to meet and confer, and there is no fee. The board will designate a director, {DECIDER}, to meet you. The meeting is to be held by {DUE}, unless you and the association agree in writing to a later date. {DECIDER} will contact you at the way you chose to set a time and place. If you want to change your request, write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.

## 9. Channels and the reference

- **Channels:** paper, fillable PDF, email, PayHOA, portal. A PayHOA request is a signed-in answer (`SIGNED_IN`); an emailed request from the address on file is `MATCHED`; paper is `CLAIMED`. A dispute is a request whose identity matters less than its date, since the association “shall not refuse” a member’s request; an unmatched sender is asked to confirm membership, but the request is not dropped.
- **Marker code proposed: `MC`** (meet and confer). No collision found. Campaign marker for the blank (`MC26M-…`, `MC26P-…`); a copy marker for the stage 2 reply to an association-invoked request.
- The letters that offer this form (the annual policy statement, the pre-lien notice, the hearing letter) carry the form’s PayHOA link and print its QR code with its address ([forms.md](../forms.md), “A QR code for a link”).

## 10. Profile slots

| Slot | What it is |
|---|---|
| `{ASSOCIATION}` | the association’s name |
| `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}` | where the request goes |
| `{BOARD_CONTACT}` | who designates the director and handles reconsideration |
| `{IDR_MAX_DAYS}` | the maximum time the association’s procedure states (5910(b)); the board adopts it |
| `{IDR_PROCEDURE}` | the association’s own procedure, if its documents have one, or a statement that it uses 5915 |
| `{IDR_DESIGNEE_RULE}` | how the board designates (a standing designee, a rotating director, or one per dispute) |
| `{MEDIATION_PROGRAM}` | a local low-cost mediation program the association uses (5905(b)) |

## 11. Handler and procedure

- **Handler:** `@handler("CIV 5915", "CIV 5910", role=Role.REQUEST, form="idr-request", procedure="meet-and-confer")`. It accepts an arrival that is this form (`MC`, a PayHOA form id) or is classified `ResponseKind.DISPUTE`. `plan` opens the clocks of rows 2 to 6, drafts the acknowledgment, puts “designate a director” on the next board agenda, and records which notice the dispute relates to (so that a pending lien is held until the offer is made, 5670). `RESPONSE_RULES` has no `DISPUTE` row today, only the notice-catalog entry; add one (`source=POLICY` until the board adopts `{IDR_MAX_DAYS}`; `assignment="disputes"`). jason does not designate the director, schedule the meeting, sign the agreement, or decide the dispute (AGENTS.md).
- **Procedure:** none exists. Add `meet-and-confer`: (1) stamp receipt; (2) read the request and the related notice; hold any lien step until the offer is made; (3) put the designation on the next board agenda; (4) acknowledge; (5) set the meeting; (6) the director’s written summary and signatures; (7) ratification; (8) record the outcome, and a lesson for a clock missed. The annual policy statement’s 5920 description and 5965 summary are steps of the procedure that makes the statement; no such procedure key exists in `src/jason/community/procedures.py` at this date, so add the step when it does.
- **Template changes this needs:** `required_if`; a `stage` and a `direction` (member-invoked, association-invoked) on a template, so the association’s letter is generated from the same base.

## 12. Edge cases

- **Co-owners.** Either may invoke; the request names one owner and may say “and my co-owner”; the agreement is signed by those who are parties.
- **A representative.** A member may be assisted by another person (5910(f)); a person who invokes for the member needs the member’s writing, as in [records-request.md](records-request.md).
- **A tenant or non-owner.** Not a member; 5900(a) speaks of a member. The request is answered as an inquiry, and a tenant who is a party to a lease dispute is told what the association can and cannot do.
- **A minor.** Not asked; counsel.
- **Language and accessibility.** Statutory words are English; a plain-words note may be translated. A meeting may be held in person, by phone, or by video (`meeting-place`), with an interpreter or any reasonable accommodation the member asks for; the form says so.
- **A request that arrives without the form.** A letter or email saying “I want to meet and confer” is a request (5910(a), “in writing”). The handler fills the form’s fields and sends the acknowledgment; the clock runs from receipt.
- **A request that is really something else.** A complaint about a neighbor is not a dispute “between an association and a member” and is handled by the complaint process; the association may still offer a neutral (5905(b)) as a courtesy (reading). A request for a hearing before discipline is under 5855 and its own notice. A request for the association’s records is [records-request.md](records-request.md). A request to pay under protest is [disputed-charge.md](disputed-charge.md). A demand letter from a lawyer is a legal notice for the board and counsel, and may also be a Request for Resolution ([adr-request.md](adr-request.md)).
- **The association invokes it.** The template’s association-to-member letter states the dispute, the right to decline (5910(d)), the right of appeal to the board if the member takes part (5910(d)), no fee (5910(g)), and the maximum time; the board approves the letter before it is sent.

## 13. Leads for the board and counsel

**Drift findings (the existing form).** The `IDR` form (`mystique/forms.py`) asks `Email address` as a required question; standard 2 and CIV 4041(b)(2)(A) do not allow an email to be required unless the member asks for email. It says “A board member will contact you to set a meeting”; 5915(b)(3) says “The board shall designate a director”; the form’s sentence names no one and promises no time. It lacks the statement that the association “shall not refuse” (5915(b)(2)), that there is no fee (5910(g), 5915(d)), the written agreement and ratification (5915(b)(5), (c)), the assistance of another person (5910(f)), and the maximum time (5910(b)). Its `authority` string cites 5910 and 5915 only, and not 5900 or 5905. None of these makes the form unlawful; each is a gap this design closes.

Leads (open questions; none settled here):

1. **The maximum time.** 5910(b) requires the *procedure* to state it; 5915, the default, says “promptly”. Does an association that adopted nothing, and uses 5915, fail 5910(b)? 5915(a) says its procedure “is fair, reasonable, and expeditious within the meaning of this article”, so a reading is that the default satisfies the article without a number. PROPOSED POLICY in section 7 adds one so the clock is never open. Counsel reads it; the board adopts it.
2. **The designation.** Whether a standing designee satisfies “The board shall designate a director” for each dispute, or the board must act each time. The board adopts a written policy (`{IDR_DESIGNEE_RULE}`) and records each designation.
3. **A conflict of interest.** A director who is a party, a witness, or a neighbor in the dispute: the law is silent. PROPOSED POLICY: such a director does not serve as the designee. The board adopts.
4. **Good faith.** 5910.1 bars a civil action “unless the association has complied with Section 5910 by engaging in good faith”. What the record of good faith is: the acknowledgment, the designation, the meeting, the summary. The handler keeps each with its date.
5. **A request that is not a “dispute”.** Whether a request for a hearing or a reconsideration is a 5900 dispute: a reading for counsel.
6. **The lien path.** 5670 makes the offer a step before a lien; 5690 requires the notice to be recommenced if the article’s procedures are not followed. Reading (the association’s): the offer to meet and confer is such a procedure. Counsel confirms before a lien is recorded after a request.
7. **The annual statement.** 5920 and 5310(a)(9) require a “description” or “summary” in the annual policy statement. Whether the association’s statement carries it is a check in the policy statement’s procedure, not this form.
8. **A document’s own procedure.** If the governing documents state a procedure that falls short of 5910, 5905(c) says 5915 applies. Record it as a `Conflict` row, never resolved here.

## 14. Test fixtures

**Typical** (a member disputes a fine):

| Field | Answer |
|---|---|
| `name` | A. Owner |
| `unit-address` | 123 Main St |
| `contact-method` | By email |
| `email` | a.owner@example.test |
| `dispute` | I was fined for a parking violation I believe did not occur on the date shown |
| `outcome` | Withdraw the fine |
| `related-notice` | A notice of a violation or a hearing |
| `availability` | Weekday evenings |
| `meeting-place` | By video |
| signature | A. Owner, 2026-10-05 |

Expected: no problems; clocks 2 to 6 opened; the acknowledgment shows `{DUE}` = receipt + 30 calendar days; the related notice is linked for a person to confirm.

**Minimal:**

| Field | Answer |
|---|---|
| `name` | A. Owner |
| `unit-address` | 123 Main St |
| `contact-method` | By phone |
| `phone` | (555) 010-0100 |
| `dispute` | The landscaping near my unit is not being maintained |
| signature | A. Owner |

Expected: no email asked or required; no `outcome`, no `availability`.

**Edge** (an owner who has just received a pre-lien notice; a lawyer assists; the board’s only regular meeting is far off):

| Field | Answer |
|---|---|
| `name` | B. Owner |
| `unit-address` | 456 Elm St |
| `contact-method` | By mail |
| `mailing-address` | 456 Elm St (the box “Same as my unit address” checked) |
| `dispute` | I dispute the late charges on my account |
| `related-notice` | A notice about unpaid assessments |
| `assisted-by` | D. Lawyer |
| signature | B. Owner |

Expected: the handler records the request against the collection record and holds any lien step until the offer is made (5670); the designation is on the next agenda or taken by written consent if the documents allow it; the clock does not wait for the next regular meeting.

**The statutory checklist test, in words.** (a) Each row of the section 3 table names its authority and the key or block that carries it; (b) the recital text contains “The association shall not refuse a request to meet and confer.” exactly as 5915(b)(2) reads on the shelf; (c) the form says there is no fee and cites 5910(g) and 5915(d); (d) no required email, and `email` is required exactly when `contact-method` is email; (e) the form says the request is in writing and carries a signature; (f) stage 2 offers both choices of 5910(d) and states the appeal; (g) `{IDR_MAX_DAYS}` is filled before the form is generated, or the generation refuses and names the missing slot (standard 7); (h) the recital tokens resolve against the shelf and name existing subdivisions. The scan and marker tests are as in [records-request.md](records-request.md).
