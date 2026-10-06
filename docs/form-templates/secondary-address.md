# Secondary address for notices and collection notices

Status: design (2026-10-05). Key `secondary-address`; proposed marker code `NA`. It follows the standard in [form-templates.md](../form-templates.md). The inventory row is "Secondary address for notices and collection notices" in [standard-forms.md](../standard-forms.md). Today the secondary address is collected only inside the annual form (questions `second-email` and `second-mailing-address`, [owner-information.md](owner-information.md)); this design is the stand-alone form that can be used any day of the year and that can also remove one.

## 1. Authority and what the law requires

As of: the shelf’s 2025 session publication of the code (`data/authorities/CIV/CIV-4000-4070.md`, `CIV-5260.md`, `CIV-5300-5320.md`, `CIV-5650-5690.md`, `CIV-5700-5740.md`, read with lawlibrary, 2026-10-05). CIV 4040 is the text operative 2023-01-01; CIV 5260 is as amended by Stats. 2024, Ch. 383 (operative 2025-01-01). jason’s copy is kept from the publication; it is not an official restatement, and the official page controls.

**CIV 4040(b), the duty this form carries out:**

> (b) Upon receipt of a request by a member identifying a secondary email or mailing address for delivery of notices, pursuant to Section 5260, the association shall deliver an additional copy of both of the following to the secondary address identified in that request:
>
> (1) The documents to be delivered to the member pursuant to Article 7 (commencing with Section 5300) of Chapter 6.
>
> (2) The documents to be delivered to the member pursuant to Article 2 (commencing with Section 5650) of Chapter 8 and Section 5710.

**CIV 5260 (intro and (b)), how the request is made effective:**

> To be effective, any of the following requests shall be delivered in writing to the association, pursuant to Section 4035:
>
> (b) A request to add or remove a second email or mailing address for delivery of individual notices to the member, pursuant to Section 4040.

**CIV 4041(a)(2), the annual question:**

> (2) An alternate or secondary delivery method for receiving notices from the association, which shall include the option to receive notices at one or both of the following:
>
> (A) A mailing address.
>
> (B) A valid email address.

**CIV 4035(a), to whom the request goes:**

> (a) If a provision of this act requires that a document be delivered to an association, the document shall be delivered to the person designated in the annual policy statement, prepared pursuant to Section 5310, to receive documents on behalf of the association. If no person has been designated to receive documents, the document shall be delivered to the president or secretary of the association.

(4035(b) lists the methods: email or other electronic means “if the association has assented to that method of delivery”; personal delivery if assented, with a written receipt; first-class, registered, certified, express, or overnight mail.)

**CIV 5310(a)(2), where the association must tell members of the right:**

> (2) A statement explaining that a member may submit a request to have notices sent to up to two different specified addresses, pursuant to Section 4040.

**CIV 4041(e), what a second address is also for** (the last sentence):

> If the association delivers a notice to a member’s email address and finds that the email address provided is no longer valid, the association shall resend the notice to a mailing or email address identified by the member pursuant to Section 4040.

**The notices the second address gets copies of, by the sections 4040(b) names.** The shelf holds each in full; the operative words that deliver or serve a document on the member are:

- **Article 7 of Chapter 6** (the annual reports). CIV 5320(a): “When a report is prepared pursuant to Section 5300 or 5310, the association shall deliver one of the following documents to all members by individual delivery pursuant to Section 4040: (1) The full report. (2) A summary of the report ...”. CIV 5305, last sentence: “A copy of the review of the financial statement shall be distributed to the members within 120 days after the close of each fiscal year, by individual delivery pursuant to Section 4040.” The reports themselves are 5300 (the annual budget report, “30 to 90 days before the end of its fiscal year”) and 5310 (the annual policy statement, “Within 30 to 90 days before the end of its fiscal year”).
- **Article 2 of Chapter 8, and 5710** (the collection documents). CIV 5660 (intro): “At least 30 days prior to recording a lien upon the separate interest of the owner of record to collect a debt that is past due under Section 5650, the association shall notify the owner of record in writing by certified mail of the following: ...”. CIV 5675(e): “A copy of the recorded notice of delinquent assessment shall be mailed by certified mail to every person whose name is shown as an owner of the separate interest in the association’s records, and the notice shall be mailed no later than 10 calendar days after recordation.” CIV 5685(a): “... provide the owner of the separate interest a copy of the lien release or notice that the delinquent assessment has been satisfied.” CIV 5685(b): “... provide the owner of the separate interest with a declaration that the lien filing or recording was in error and a copy of the lien release or notice of rescission.” CIV 5710(b): “... the association shall serve a notice of default on the person named as the owner of the separate interest in the association’s records or, if that person has designated a legal representative pursuant to this subdivision, on that legal representative. Service shall be in accordance with the manner of service of summons in Article 3 (commencing with Section 415.10) of Chapter 4 of Title 5 of Part 2 of the Code of Civil Procedure. An owner may designate a legal representative in a writing that is mailed to the association in a manner that indicates that the association has received it.”
- **The payment-plan standards.** CIV 5665(a): “The association shall provide the owners the standards for payment plans, if any exists.” It sits in Article 2 of Chapter 8. Whether it is a “document to be delivered” is for counsel (lead 1).

**What the Act does not say** (so the form does not say it either): it does not say how the additional copy is delivered (by which of the 4040(a) means), whether a second address may be added by a request that reaches someone other than the 4035 designee, how many addresses a member may name, or what the association does with a copy of a notice already sent before the request arrived. No section in 5650 to 5690 names a secondary address; the tie is 4040(b)(2).

## 2. Who uses it, and when

- **A member** (an owner of a separate interest, CIV 4160) who wants the annual reports and the collection documents also sent to a second email or mailing address: a family member, an accountant, a property manager, a lender, a co-owner who lives elsewhere. Or who wants one removed.
- **When:** any day of the year; the annual solicitation asks it too (4041(a)(2)). A member in collection may use it at any time (section 7, row 5).
- **Who it is not for:** a member who wants to change the preferred method ([delivery-change.md](delivery-change.md)); a member who wants general notices individually ([individual-delivery-request.md](individual-delivery-request.md)); a member who is naming a legal representative for 4041(a)(3) or 5710(b) (the annual form’s representative section; the form says so, section 13 lead 6).

## 3. What the form must carry

| # | What the law (or the standard) says the form carries | Words | Carried by |
|---|---|---|---|
| 1 | A request identifying a secondary email or mailing address | 4040(b) | `second-email`, `second-mailing-address` |
| 2 | A request to add or to remove one, in writing | 5260(b) | `action`, `remove-which`; signature |
| 3 | Delivered to the association “pursuant to Section 4035” | 5260 | fixed text with `{DESIGNATED_PERSON}`, `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}` |
| 4 | What the second address receives copies of | 4040(b)(1), (2) | fixed text (recital) listing the sections of section 1 |
| 5 | When it takes effect | 4040(b): “Upon receipt” | fixed text, section 6 |
| 6 | The option of a mailing address, an email address, or both; an email address not required | 4041(a)(2); 4041(b)(2)(A) | `second-email`, `second-mailing-address` (each optional on its own; at least one for an add) |
| 7 | A warning that collection notices contain financial detail | standard 2 (say why a question is asked) | fixed text “Who sees these” |
| 8 | Who is asking, and for which unit | 4160, 4041 | `name`, `unit-address`, `capacity` |
| 9 | That a request in other words is still a request, and where to get help | standard 5 | fixed text |

## 4. The questions

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `name` | Your name | text | yes | 5260: a member’s request | NAME | request.requester |
| `unit-address` | Unit address | address | yes | places the member (4160); prefilled `UNIT_ADDRESS` | ADDRESS | request.unit |
| `capacity` | You are answering as | choice: “An owner of this unit”; “Someone the owner has authorized to answer” | yes | 5260; the attestation | TEXT | request.capacity |
| `action` | What do you want to do? | choice: “Add or change a second address”; “Remove a second address” | yes | 5260(b): “add or remove” | TEXT | request.action |
| `second-email` | Second email address | email | no; with `second-mailing-address`, at least one is required for an add or a change | 4040(b); 4041(a)(2)(B); never required on its own | EMAIL | additional-delivery record: email |
| `second-mailing-address` | Second mailing address | address (street; city, state, ZIP) | no; as above | 4040(b); 4041(a)(2)(A) | ADDRESS | additional-delivery record: mailing address |
| `second-name` | Name the mail should be addressed to at the second address (a person or a company) | text | no | so a copy reaches the right hands; “in care of” where it is a company | NAME | additional-delivery record: name, as the owner wrote it (no suffix) |
| `remove-which` | Which one should we stop using? (tick any) | checkbox: “My second email”; “My second mailing address” | yes if `action` is remove | 5260(b) | TEXT | the additional-delivery record: the field cleared; the record moved out when both are gone |
| `other-notices` | Also send the second address copies of the other notices the association sends me individually | checkbox (one box) | no | **not required by the Act**: 4040(b) names two groups of documents; the box is the association’s choice and is printed only if the board adopts the policy (lead 2) | TEXT | request.scope = “all individual notices” |
| `attestation` | I am an owner of this unit, or I am authorized to answer for the owner, and what I have written is true | checkbox (one box) on PayHOA and PDF; the signature line on paper | yes | assurance ([forms.md](../forms.md), “Channels and assurance”) | TEXT | request.attested |
| (signature) | Signature of owner, and date | signature line, date | yes on paper and PDF; “signed in” online | 5260: “in writing” | NAME | request.signed |

Not asked, on purpose: why the owner wants the second address, the second person’s phone number, the second person’s relationship to the owner, or the owner’s occupancy. The form never asks the owner to name a legal representative: that is the annual form’s question (4041(a)(3)) and a separate act (5710(b)).

## 5. The recitals

| Token | Subdivisions | Why it opens the form |
|---|---|---|
| `{QUOTE:CIV 4040(b)}` | (b), (b)(1), (b)(2) | the duty and the two groups of documents |
| `{QUOTE:CIV 5260}` | (intro), (b) | the request is effective when delivered in writing to the association under 4035 |
| `{QUOTE:CIV 4041(a)(2)}` | (a)(2)(A), (B) | the choice of a mailing address, an email address, or both |
| `{QUOTE:CIV 4035(a)}` | (a) | where the request goes |
| `{QUOTE:CIV 5310(a)(2)}` | (a)(2) | the same notice the annual policy statement gives |
| `{QUOTE:CIV 4041(e)}` | (e), last sentence | the second address is also where a notice is resent after a bounce |

A plain-words note may follow each, labeled “The association’s plain-words note; the words above control.” The list of section 1 (what the second address gets copies of) is printed as a plain list with the sections named, each filled from the shelf by token (`{QUOTE:CIV 5660}` and so on) on the back of the form, so a stale word fails the build.

## 6. What the member is told

The sentence the member reads (`member_clock`):

> You may ask us in writing to send a second copy of some notices to another email address or mailing address. The law names which: the annual budget report, the annual policy statement, and the other annual reports; and the notices we send about assessments that are past due (the notice before a lien, the copy of the recorded notice, the lien release, and a notice of default). We will start sending the second copies from the day we receive your request. We will not send copies of a notice we had already sent. You can remove a second address the same way, and we stop on the day we receive that request. These notices can show what you owe, so give an address you trust. We will tell you in writing the day we received your request. Send it to {DESIGNATED_PERSON} at {RETURN_BY_MAIL} or {RETURN_BY_EMAIL}, or answer it online at {PORTAL}.

Reading (label: the association’s plain-words note, not the statute): “from the day we receive your request” reads 4040(b), “Upon receipt of a request”. “We will not send copies of a notice we had already sent” is the proposed policy of section 7, row 5; the Act is silent.

How to reconsider: there is no decision to reconsider. If a copy did not reach the second address after the date received, the member tells the contact and the association sends it (row 4). A member who disagrees may ask to meet and confer (CIV 5900 to 5920).

## 7. The association’s clocks

“Counted from” is the association’s receipt, stamped on the day it arrives (mail on the day opened; email and PayHOA on the day sent).

| # | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| 1 | receipt | acknowledge within 2 business days | PROPOSED POLICY (as `acknowledge_days=2`) | nothing in the law; the member is left without a date |
| 2 | receipt | effective: every document named in 4040(b) that the association delivers on or after the day received also goes to the second address | statute, 4040(b): “Upon receipt of a request” | the association has not delivered “an additional copy”; the delivery record is weaker, and a 5660 notice without it is for counsel |
| 3 | receipt | enter in the books within 5 business days; the handler also reads the unrecorded requests before each batch | PROPOSED POLICY | a batch goes without the copy unless the handler reads the inbox |
| 4 | the day the association finds a copy missed the second address | send within 3 business days | PROPOSED POLICY | as row 2 |
| 5 | receipt, while an account is in collection | the second address gets copies of every Article 2 or 5710 document delivered on or after the day received. A notice already sent is not sent again by right; PROPOSED POLICY: the association sends the second address a copy of the last collection notice already sent, if no lien has been recorded, as a courtesy and says so | statute for the first sentence; PROPOSED POLICY for the rest | the member is told in writing which was sent; the 5665(b) period (“within 15 days of the date of the postmark of the notice”) does not move |
| 6 | receipt of a removal | stop on the day received; a copy already sent is not recalled | statute (5260(b), 4040(b)); PROPOSED POLICY for “not recalled” | a copy goes to an address the owner removed: a delivery the owner did not want |
| 7 | receipt, from a channel below `MATCHED` | a message to the address on file within 2 business days: “we received a change to your second address; tell us if it was not you” | PROPOSED POLICY (the standard assurance rule) | an impostor’s address receives an owner’s financial notices |
| 8 | the day the preferred email bounces | resend to the second address (4041(e)); within 3 business days | statute for the resend; the days are PROPOSED POLICY | the notice has not reached the member |
| 9 | each year, 30 to 90 days before the end of the fiscal year | the policy statement carries the 5310(a)(2) statement and the 4035 designee’s name and address (5310(a)(1)) | statute, 5310(a) | the association has told no one the right exists |
| 10 | the annual solicitation | asked of every owner (4041(b)(1)) | statute | see [owner-information.md](owner-information.md) |

A “business day” is not defined on the shelf. PROPOSED POLICY: the association states the definition it uses on the form (`{BUSINESS_DAY_DEFINITION}`).

## 8. The acknowledgment text

> Reference {REFERENCE}. We received your request about your second address for notices on {RECEIVED}. From that day we will send an additional copy of the notices the law names to the address you gave. {DECIDER} records it; no one has to approve it. If you asked us to remove an address, we stopped using it on {RECEIVED}. We will enter your request in our records by {DUE}. We will write to your address on file to say we received it, so you can tell us if it was not you. To change or cancel this request, use the same form or write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.

`{DUE}` is row 3’s date. The line about the address on file is printed when the request came by a channel below `MATCHED`.

## 9. Channels and the reference

- **Channels:** paper, fillable PDF, email, PayHOA, portal. A signed-in PayHOA answer is `SIGNED_IN`; a reply email from the address on file is `MATCHED`; a signed paper copy is `CLAIMED`. A Google Form is not offered: an unsigned-in answer adds an address that receives an owner’s financial notices, and is a lead only.
- **Marker code proposed: `NA`** (notice, additional). Letters from the alphabet `0-9 A C E F H K M N P R T V X`; `NP` is the annual form, `NC` the delivery change, `NV` the individual delivery request; `NA` collides with no code found in `docs/` or `mystique/forms.py`. A standing form’s campaign is the year it was generated (`NA26M-…`, `NA26P-…`). A copy sent pre-filled (for example, after a bounce) names the copy (`NA26E-4RK9T-C7`).
- The reference is a hint, never what the reading depends on ([form-identifiers.md](../form-identifiers.md)).

## 10. Profile slots

| Slot | What it is |
|---|---|
| `{ASSOCIATION}` | the association’s name |
| `{DESIGNATED_PERSON}` | the person the annual policy statement designates (4035(a); 5310(a)(1)); else the president or secretary |
| `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}` | where the request goes; naming an email address is the association’s assent to email delivery (4035(b)(1)) |
| `{BOARD_CONTACT}` | where to write about a disagreement |
| `{BUSINESS_DAY_DEFINITION}`, `{ACK_DAYS}`, `{ENTRY_DAYS}` | as in [delivery-change.md](delivery-change.md) |
| `{ALL_INDIVIDUAL_NOTICES}` | whether the board has adopted the policy of lead 2; the `other-notices` box is printed only if so |
| the additional-delivery tag and record rules | the profile’s names for the additional-delivery record and its tag |

## 11. Handler and procedure

- **Handler:** `@handler("CIV 4040(b)", "CIV 5260", role=Role.FORM_RETURN, form="secondary-address", procedure="delivery-requests", channels=(PAYHOA, GMAIL, MAIL))` ([arrivals-design.md](../arrivals-design.md)). `accepts` takes an arrival with this form’s marker (`NA`) or a PayHOA form id. `read` is evidence only. `plan` lists the writes: an additional owner record on the unit, added without an invitation and tagged for additional deliveries, with the email and mailing address the owner gave, named exactly as the owner wrote the name ([owner-information.md](../owner-information.md), “Where each answer lives”); a removal clears the field, and the record is moved out when both are gone. It never touches the owner’s own record and never makes the second person an owner of the unit for any other purpose (the books treat every person on a unit as an owner: broadcasts, reminders, the membership list; `tags.NOT_OWNERS` and the additional-delivery tag keep it out of owner counts and the list).
- **A new title ends it.** A second address belongs to the member who asked. A deed after the request’s date belongs to the prior title: the old owner’s additional deliveries are not carried to the new owner ([owner-information.md](../owner-information.md), “Never over newer information”).
- **Procedure:** `delivery-requests` is proposed (see [delivery-change.md](delivery-change.md), section 11). Add to it the step for this form: **before each distribution of a 5300, 5305, 5310, or 5320 document and before each 5660, 5675(e), 5685, or 5710 notice, list the additional deliveries on the units in the batch** (`jason delivery --notice KEY --ids ids.json` already lists who receives a notice and how), **and send each additional copy as its own confirmed batch**, in the same way as the original (a mailed copy through the Mailroom; an emailed copy through the email batch). Until the procedure exists, `owner-info-cycle` (record the answers) and `notice-delivery` (deliver, read bounces, resend) are the nearest.
- **jason never:** sends a copy on its own initiative, approves or denies the request, or edits an owner’s submission (AGENTS.md, Boundaries).

## 12. Edge cases

- **Co-owners.** Each is a member; each may name a second address. A second address one co-owner names does not change the other’s. Two co-owners naming the same second address: one record per owner’s request, one delivery to that address per document where the document goes to the unit once (a document delivered “to the member” is delivered to each owner; the additional copy follows each).
- **A representative.** A person with written authority may sign for the owner. The legal representative of 4041(a)(3) is a contact; of 5710(b), the person served with a notice of default in the owner’s place. Neither is made by this form.
- **A tenant or another non-owner.** Not a member (4160). The owner may name a tenant’s address as a second address; the tenant is then the recipient of the owner’s notices, and the form says what those notices contain (section 6).
- **A lender, an attorney, a property manager, a company.** Any person may be the second address’s recipient; `second-name` is how the mail is addressed. The form does not ask who they are.
- **An address outside the United States, or a P.O. box.** Accepted; certified mail to a P.O. box and to a foreign address is for the manager to confirm before a collection notice.
- **The second address equals the first.** A no-op: the handler tells the member and records nothing.
- **A second address that bounces.** The association learns it from the bounce report ([owner-information.md](../owner-information.md), the 2027 cycle’s item 7) and tells the owner; it is not removed unless the owner asks.
- **Language and accessibility.** The statutory words stay in English; large print, another format, a person to read the form aloud or write it down, and a reasonable accommodation are offered.
- **No form used.** An email or letter that says “also send my notices to ...” is a request. The handler reads it, marks what is missing, asks once, and the date received is the day it arrived.
- **The request is really something else.** “Send my mail to my new address” is the preferred method ([delivery-change.md](delivery-change.md)); “my attorney will handle this” may be a legal representative on the annual form; “I want all your meeting notices by email” is [individual-delivery-request.md](individual-delivery-request.md).

## 13. Leads for the board and counsel

A reading is labeled as one and whose it is. A conflict between a document and the statute is noted, never resolved.

1. **Which Article 2 and 5710 documents are “to be delivered to the member”.** The sections of 5650 to 5690 and 5710 that deliver or serve a document on the owner are 5660, 5675(e), 5685(a) and (b), and 5710(b); 5665(a) provides “standards for payment plans” and 5658 states a right, not a delivery. 5710(b) is service in the manner of a summons on “the person named as the owner ... or, if that person has designated a legal representative ..., on that legal representative”. Whether an additional copy of a notice of default goes to a secondary address, and how, is for counsel. The form lists only the four the text plainly delivers and says “the notices the law names”.
2. **“Individual notices” beyond the two groups.** 5260(b) speaks of a second address “for delivery of individual notices to the member”; 4040(b) names two groups. Reading (the association’s, labeled): the Act requires copies of the two groups; copies of the other individual notices (a rule-change vote, an assessment increase, a discipline hearing notice) are a choice. PROPOSED POLICY: the board decides in writing whether to copy them, and the `other-notices` box is printed only if it does.
3. **How the additional copy is delivered.** 4040(b) says “deliver an additional copy” and not by which means. The 5660 notice must go to the owner “by certified mail”; 5675(e) copy “by certified mail”. PROPOSED POLICY: the copy to a mailing address goes by the same means as the original; the copy to an email address goes by email, and the certified mailing to the owner is unchanged. Counsel confirms whether an email copy suffices.
4. **“Up to two different specified addresses”.** 5310(a)(2) says a member may ask to have notices sent “to up to two different specified addresses”. 4040(b) says “a secondary email or mailing address”; 4041(a)(2) says “one or both” of a mailing address and an email. Reading: a member may name one second email and one second mailing address; whether “two” counts the preferred address is for counsel. The form follows 4041(a)(2) (each of the two, both optional).
5. **To whom the request goes.** 5260 requires delivery “to the association, pursuant to Section 4035”: to the designated person, or the president or secretary, by email only “if the association has assented”. A request sent to an address the association has not named as assented may not be “effective”. The form names the address; the handler treats any receipt by the manager as receipt by the association (PROPOSED POLICY) and counsel confirms.
6. **A legal representative is a different act.** 5710(b): an owner “may designate a legal representative in a writing that is mailed to the association in a manner that indicates that the association has received it”. The annual form’s representative question (4041(a)(3)) is not that writing. Whether the association tells an owner facing a notice of default about 5710(b) is for the board; this form does not.
7. **Misuse.** A second address receives an owner’s financial notices; a request from an address that is not on file, or a signature not matched, could add a stranger’s address. Row 7 (the message to the address on file) is the proposed protection, and the standard assurance rule applies. For the board.
8. **Does the annual policy statement say it?** 5310(a)(2) requires the statement; whether the current policy statement carries it, and the 4035 designee, is a check to run (`jason notices --catalog`; `jason cite`). The form’s existence does not satisfy 5310.

## 14. Test fixtures

Made-up answers. All use plainly fake data.

**Typical** (an owner adds an accountant’s email and mailing address):

| Field | Answer |
|---|---|
| `name` | A. Owner |
| `unit-address` | 123 Main St, Anytown, CA 90000 |
| `capacity` | An owner of this unit |
| `action` | Add or change a second address |
| `second-email` | `accountant@example.org` |
| `second-mailing-address` | 9 Example Way, Anytown, CA 90000 |
| `second-name` | B. Accountant, CPA |
| `attestation` | ticked; signed 2026-03-02 |

Expected: an additional-delivery record on the unit with both addresses, named exactly “B. Accountant, CPA”; copies from the date received; a message to the address on file if the channel was below `MATCHED`.

**Minimal** (the smallest valid return): `name`, `unit-address`, `capacity`, `action` = add, `second-email` only, signature.

**Edge cases:**
- `action` = add with both address fields blank: incomplete; one request for an address.
- `action` = remove, `remove-which` = second email: the email cleared; the mailing address stays; the record is not moved.
- `action` = remove, both ticked: the record moved out.
- The second address equals the first: no change; told so.
- A request received the day after a 5660 notice went: effective for later documents; the courtesy copy (row 5) goes if the board adopts it; the 15-day period does not move.
- A request from a tenant of the unit (not the owner): held as a lead; the owner is written to at the address on file.
- A removal received after a lien was recorded: effective; the recorded notice’s copy (5675(e)) already mailed is not recalled.

**The statutory checklist test, in words.** (1) The recital block contains the exact words of 4040(b), 5260’s introduction and (b), 4041(a)(2), 4035(a), 5310(a)(2), and 4041(e), each filled from the shelf; the build fails if a cited subdivision is gone. (2) The form offers an email address, a mailing address, or both, and requires neither on its own. (3) The form offers add and remove. (4) The form names the 4035 designee and an address. (5) The form lists the notices the second address receives copies of, each by section, and the list is read from the shelf. (6) The form asks no relationship, no phone, no reason, and does not ask for a legal representative. (7) The form carries a sentence that collection notices can show what is owed. (8) The `other-notices` box appears only when the profile’s `{ALL_INDIVIDUAL_NOTICES}` is set. (9) The acknowledgment carries `{RECEIVED}`, `{DUE}`, `{DECIDER}`, and `{REFERENCE}`. (10) The same template renders paper, PDF, email, and PayHOA with the same questions in the same order, each carrying `NA`. (11) A made-up return of each fixture reads back to the same answers after a bad scan.
