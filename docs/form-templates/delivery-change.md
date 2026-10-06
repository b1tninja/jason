# Change my notice delivery

Status: design (2026-10-05); built in the library as version 1 (2026-10-05), `src/jason/community/form_library/ca/delivery_change.py`, marker code `NC`, handler `owner-information` with procedure `owner-info-cycle` (the `delivery-requests` procedure below is still a proposal; the module's docstring lists where it departs from this page). Key `delivery-change`. It follows the standard in [form-templates.md](../form-templates.md). The inventory row is "Change my notice delivery" in [standard-forms.md](../standard-forms.md). The model for a form that is built is [owner-information.md](owner-information.md) (the annual form this one sits beside). No form of this kind exists today.

## 1. Authority and what the law requires

As of: the shelf's 2025 session publication of the code (`data/authorities/CIV/CIV-4000-4070.md`, `CIV-5260.md`, read with lawlibrary, 2026-10-05). CIV 4040 is the text operative 2023-01-01 (Stats. 2021, Ch. 640, Sec. 2); CIV 4041 is as amended by Stats. 2022, Ch. 632 (operative 2023-01-01). jason's copy is kept from the publication; it is not an official restatement, and the official page controls.

**CIV 4041(b)(2)(B), the duty this form carries out** (the solicitation must include):

> (B) A simple method for the member to inform the association in writing that the member wishes to change their preferred delivery method for receiving notices from the association.

**CIV 4041(b)(2)(A), the companion duty, and what it means for this form:**

> (A) Notification that the member does not have to provide an email address to the association.

**CIV 4041(a)(1), what the preferred method may be:**

> (a) A member shall, on an annual basis, provide written notice to the association of all of the following:
>
> (1) The member’s preferred delivery method for receiving notices from the association, which shall include the option of receiving notices at one or both of the following:
>
> (A) A mailing address.
>
> (B) A valid email address.

**CIV 4040(a), what the association does with the member’s choice:**

> (a) (1) If a provision of this act requires an association to deliver a document by “individual delivery” or “individual notice,” the association shall deliver that document in accordance with the preferred delivery method specified by the member pursuant to Section 4041.
>
> (2) If the member has not provided a valid delivery method pursuant to Section 4041, the association shall deliver the document by first-class mail, registered or certified mail, express mail, or overnight delivery by an express service carrier addressed to the recipient at the address last shown on the books of the association.

**CIV 4041(c), when the member gives nothing:**

> (c) If a member fails to provide the notices set forth in subdivision (a), the last mailing address provided in writing by the member or, if none, the property address shall be deemed to be the address to which notices are to be delivered.

**CIV 4041(e), what “valid” means and what follows a bounce:**

> (e) For the purposes of this section, a valid email address is one that, after a notice is sent, does not result in a bounce or other error notification indicating failure of the message. If the association delivers a notice to a member’s email address and finds that the email address provided is no longer valid, the association shall resend the notice to a mailing or email address identified by the member pursuant to Section 4040.

**CIV 4055, when an electronic request is “in writing”:**

> If the association or a member receives information by electronic delivery pursuant to Section 4040, and a provision of this act requires that the information be in writing, that requirement is satisfied if the information is provided in an electronic record capable of retention by the recipient at the time of receipt. An electronic record is not capable of retention by the recipient if the sender or its information processing system inhibits the ability of the recipient to print or store the electronic record.

**CIV 4035(a) and (b), to whom a document for the association goes:**

> (a) If a provision of this act requires that a document be delivered to an association, the document shall be delivered to the person designated in the annual policy statement, prepared pursuant to Section 5310, to receive documents on behalf of the association. If no person has been designated to receive documents, the document shall be delivered to the president or secretary of the association.
>
> (b) A document delivered pursuant to this section may be delivered by any of the following methods:
>
> (1) By email, facsimile, or other electronic means, if the association has assented to that method of delivery.
>
> (2) By personal delivery, if the association has assented to that method of delivery. If the association accepts a document by personal delivery it shall provide a written receipt acknowledging delivery of the document.
>
> (3) By first-class mail, postage prepaid, registered or certified mail, express mail, or overnight delivery by an express service center.

**What the Act does not say** (so the form does not say it either): it sets no date on which a change takes effect, no time in which the association must record it, and no limit on how often a member may change. 4041(a) asks the notice “on an annual basis”; 4041(b)(2)(B) makes the change method part of that solicitation. A member may use the change form any day of the year (section 2).

**What the shelf’s CIV 5260 does and does not list.** CIV 5260 says that “to be effective, any of the following requests shall be delivered in writing to the association, pursuant to Section 4035”, and then lists seven requests: (a) membership-list information, (b) a second email or mailing address, (c) individual delivery of general notices and its cancellation, (d) the membership-list opt-out and its cancellation, (e) a full copy of a budget report or policy statement, (f) all reports in full and its cancellation, and (g) opting in or out of electronic ballots. A change of the preferred delivery method is not on that list. Reading (the association’s, labeled): 4041(b)(2)(B) requires a “simple method ... in writing”; it does not say to whom the writing goes. The form therefore tells the member the 4035 address and also accepts the change at every channel in section 9, so the member is not caught by either reading (lead 1, section 13).

## 2. Who uses it, and when

- **A member** (an owner of a separate interest, CIV 4160) who wants to change how the association delivers individual notices to them: from mail to email, from email to mail, to both, or to a different mailing or email address for the preferred method.
- **When:** any day of the year. It is the “simple method” the annual solicitation points to; the annual form and its reminders say so ([owner-information.md](owner-information.md)). It is not tied to a cycle and has no return-by date.
- **Who it is not for:**
  - A member who also wants to add or remove a second address: [secondary-address.md](secondary-address.md).
  - A member who wants every general notice (meeting notices, rule-change notices) delivered individually: [individual-delivery-request.md](individual-delivery-request.md).
  - A member answering the annual request in full (occupancy, representative): the annual form.
  - A tenant or other non-owner: not a member (section 12).

## 3. What the form must carry

`required_content` is the checklist the test reads. “Fixed text” is a block that is not a question; the test looks for its words in the rendered form.

| # | What the law (or the standard) says the form carries | Words | Carried by |
|---|---|---|---|
| 1 | A simple method to inform the association, in writing, of a change of the preferred method | 4041(b)(2)(B) | the whole form (one page, one choice); fixed text “Use this form any day of the year” |
| 2 | The member may choose a mailing address, a valid email address, or both | 4041(a)(1)(A), (B) | `delivery` |
| 3 | Notification that an email address is not required | 4041(b)(2)(A) | fixed text; `email` required only when `delivery` includes email |
| 4 | A way to give the mailing address, and what happens with none | 4041(a)(1)(A), (c) | `mailing-address`, `mailing-same`; fixed text on 4041(c) |
| 5 | Who is asking, and for which unit | 4041(a), 4160 | `name`, `unit-address`, `capacity` |
| 6 | The request is in writing and says where it goes | 4041(b)(2)(B), 4035(a), (b) | signature line or signed-in answer; fixed text with `{DESIGNATED_PERSON}`, `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}` |
| 7 | What a bounced email means and what the association does | 4041(e) | fixed text (recital) |
| 8 | The date a change takes effect, and what is not changed | PROPOSED POLICY (the law is silent) | fixed text, section 6 |
| 9 | That a request in other words is still a request, and where to get help | standard 5 | fixed text |

## 4. The questions

Kinds: text, choice, checkbox, email, address. One question holds one value. A signed-in PayHOA answer has the member and the unit already; the paper and PDF forms ask them.

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `name` | Your name | text | yes | 4041(a): the member gives the notice | NAME | request.requester |
| `unit-address` | Unit address | address | yes | places the member (4160); prefilled `UNIT_ADDRESS` on a copy sent to a member | ADDRESS | request.unit |
| `capacity` | You are answering as | choice: “An owner of this unit”; “Someone the owner has authorized to answer” | yes | 4041(a): the member’s notice; the attestation below | TEXT | request.capacity |
| `delivery` | How should the association deliver notices to you from now on? (tick one or both) | checkbox: “By mail”; “By email” | yes (at least one) | 4041(a)(1)(A), (B) | TEXT | delivery tags: email, mail (the same tags the annual form sets) |
| `mailing-same` | Mail it to my unit address | checkbox (one box) | no | 4041(a)(1)(A), (c): the unit address is the default | TEXT | delivery.mail_to = unit |
| `mailing-address` | Mailing address for notices, if it is not your unit address | address (street; city, state, ZIP) | only if `delivery` includes mail and `mailing-same` is not ticked | 4041(a)(1)(A) | ADDRESS | delivery.mail_to |
| `email` | Email address for notices | email | only if `delivery` includes email | 4041(a)(1)(B); 4041(b)(2)(A): never otherwise | EMAIL | the member’s email on the books (see section 11 on what is overwritten) |
| `keep-others` | (not a question: a printed sentence) Your second address, your representative, and your occupancy answers stay as they are unless you use another form. | fixed text | — | one question, one value; keeps the change from clearing anything else | — | — |
| `attestation` | I am an owner of this unit, or I am authorized to answer for the owner, and what I have written is true | checkbox (one box) on PayHOA and PDF; the signature line on paper | yes | the annual form’s own attestation; assurance ([forms.md](../forms.md), “Channels and assurance”) | TEXT | request.attested |
| (signature) | Signature of owner, and date | signature line, date | yes on paper and PDF; “signed in” online | 4041(b)(2)(B): “in writing” | NAME | request.signed |

Not asked, on purpose: a phone number (4041 does not ask one), why the member is changing, the unit’s occupancy, or the current email. A choice of “By email” with no email address is not an answer the association can use (lead 4); the form says so beside the box, since a paper form cannot require it.

## 5. The recitals

The form opens with these, by token, with the subdivision named, then the caveat of section 1. The statute-token form follows the sibling pages (`{QUOTE:CIV 5205(a)}`); embedded-references.md says statutes are not yet targets, so the builder reads each from `data/authorities` with the same fail-loud rule ([embedded-references.md](../embedded-references.md)).

| Token | Subdivisions | Why it opens the form |
|---|---|---|
| `{QUOTE:CIV 4041(b)(2)(B)}` | (b)(2)(B) | the right to change, in writing, in a simple way |
| `{QUOTE:CIV 4041(b)(2)(A)}` | (b)(2)(A) | no email address is required |
| `{QUOTE:CIV 4041(a)(1)}` | (a)(1)(A), (B) | the two choices |
| `{QUOTE:CIV 4041(c)}` | (c) | what happens if the member gives nothing |
| `{QUOTE:CIV 4041(e)}` | (e) | a bounced email, and the resend |
| `{QUOTE:CIV 4040(a)}` | (a)(1), (2) | the association delivers by the member’s choice, else by first-class mail |

A plain-words note may follow each, labeled “The association’s plain-words note; the words above control.” `{QUOTE:CIV 4035(a)}` is not recited at length: the form states the address it names.

## 6. What the member is told

The sentence the member reads (`member_clock`):

> Use this form any day of the year to change how we deliver your notices. You do not have to give us an email address. We will follow your change for every notice we begin to deliver on or after the day we receive it, which we will tell you in writing. A notice we had already begun to deliver stays as it was delivered. No one has to approve your change. If you chose email and a message to that address fails, we will send the notice again by mail to the address we have for you. If you do not tell us a mailing address, we use your unit address (Civil Code 4041(c)). Send this form to {DESIGNATED_PERSON} at {RETURN_BY_MAIL} or {RETURN_BY_EMAIL}, or answer it online at {PORTAL}.

Reading (label: the association’s plain-words note and its proposed policy, not the statute): the second and third sentences state the proposed policy of section 7, row 3. The sentence “No one has to approve your change” reads 4040(a)(1), which says the association “shall deliver ... in accordance with the preferred delivery method specified by the member”; the Act gives no one a power to refuse a preference.

How to reconsider: there is no decision to reconsider. If the member finds a notice was sent the old way after the date received, the member tells the contact and the association resends it the right way (row 5). A member who disagrees about delivery may ask to meet and confer (CIV 5900 to 5920).

## 7. The association’s clocks

“Counted from” is the association’s receipt, stamped on the day it arrives (mail on the day opened; email and PayHOA on the day sent). The law counts nothing for this form; every row is a proposed policy except where marked.

| # | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| 1 | receipt | acknowledge within 2 business days | PROPOSED POLICY (the same proposal the response rules carry as `acknowledge_days=2`) | nothing in the law; the member is left without a date |
| 2 | receipt | enter in the books within 5 business days | PROPOSED POLICY (4041(b)(1) sets 30 days before the annual reports for the yearly entry only) | the change is already effective (row 3), but a batch may go out the old way unless the handler reads the unrecorded changes (section 11) |
| 3 | receipt | effective for every notice the association begins to deliver on or after the day received; a notice already begun is finished as begun | PROPOSED POLICY (the law is silent; 4040(a)(1) says “the preferred delivery method specified by the member”; 4050 deems delivery complete on deposit in the mail or on transmission) | a notice sent the old way after the effective date is sent again the new way (row 5) |
| 4 | receipt | when the change comes within 30 days before the annual reports: still effective; the annual solicitation’s entry date is not moved | PROPOSED POLICY (4041(b)(1) puts the data in the books “at least 30 days before” the disclosures; it does not say a later written preference is ignored) | the member would get the annual reports the old way against their written choice |
| 5 | the day the association finds a notice went the old way | resend within 3 business days | PROPOSED POLICY | the association’s delivery record is weaker; 5300 and 5310 reports are individual-delivery documents (4040, 5320(a)) |
| 6 | the day a new email bounces | 4041(e): resend to a mailing or email address “identified by the member pursuant to Section 4040”; ask the member for a working address | statute, 4041(e) | until the member gives one, there is no “valid delivery method”, so the notice goes by first-class mail to the address last shown on the books (4040(a)(2); and 4041(c) for the address deemed) |

A “business day” is not defined on the shelf. PROPOSED POLICY: the association states the definition it uses on the form (`{BUSINESS_DAY_DEFINITION}`) and counts the day after receipt as day 1.

## 8. The acknowledgment text

> Reference {REFERENCE}. We received your request to change how we deliver your notices on {RECEIVED}. We will follow it for every notice we begin to deliver on or after {EFFECTIVE}. We will enter it in our records by {DUE}. {DECIDER} records it; no one has to approve it. If you gave an email address and we cannot deliver to it, we will write to you by mail. To change or cancel this request, use the same form or write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.

`{DUE}` is row 2’s date; `{EFFECTIVE}` is row 3’s. `{DECIDER}` names the person who records the change (the manager or the secretary), not a body that decides.

## 9. Channels and the reference

- **Channels:** paper, fillable PDF, email, PayHOA, portal. The PayHOA form is the preferred channel: a signed-in answer is `SIGNED_IN`, the strongest proof the owner asked. A reply email from the address on file is `MATCHED`; a signed paper copy is `CLAIMED` ([forms.md](../forms.md), “Channels and assurance”). A Google Form is not offered: the right belongs to a member, and an answer from no sign-in is a lead only.
- **A change to a new email address from a channel below `MATCHED`** is confirmed first with a message to the address on file (“we received a change to your delivery; tell us if it was not you”), as the standard rule already says. The change is recorded at `RECORD_AT` or above; below it, a lead.
- **Marker code proposed: `NC`** (notice change). Letters from the alphabet `0-9 A C E F H K M N P R T V X`; the owner-information form is `NP`; the records request is `RR`; the siblings of this set are `NA`, `NV`, `CN`, `HM`, `AM` (the profile’s four are in the profile pages). `NC` collides with no code found in `docs/` or `mystique/forms.py`. A standing form’s campaign is the year it was generated: `NC26M-…` for the mailed blank, `NC26P-…` for the PayHOA form.
- **A pre-filled copy** (a change form the association sends, for example after a bounce, with the current email filled in) is a copy, so its marker names the copy (`NC26E-4RK9T-C7`); a blank form is a campaign.
- The reference is a hint, never what the reading depends on ([form-identifiers.md](../form-identifiers.md)).

## 10. Profile slots

The base template is general. The profile fills:

| Slot | What it is |
|---|---|
| `{ASSOCIATION}` | the association’s name |
| `{DESIGNATED_PERSON}` | the person the annual policy statement designates to receive documents (4035(a); 5310(a)(1)), else the president or secretary |
| `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}` | where the change goes; naming an email address is the association’s assent to email delivery (4035(b)(1)) |
| `{BOARD_CONTACT}` | where to write about a disagreement |
| `{BUSINESS_DAY_DEFINITION}` | what a business day is, where the board has adopted one |
| `{ACK_DAYS}`, `{ENTRY_DAYS}` | the acknowledgment and entry days the board adopts (proposed: 2 and 5 business days) |
| the delivery tags | the profile’s names for the email and mail delivery tags (`mystique/tags.py` for the worked profile) |

## 11. Handler and procedure

- **Handler:** `@handler("CIV 4041(b)(2)(B)", role=Role.FORM_RETURN, form="delivery-change", procedure="delivery-requests", channels=(PAYHOA, GMAIL, MAIL))` ([arrivals-design.md](../arrivals-design.md)). `CIV 4041` already has the owner-information return registered under role `FORM_RETURN`; the registry allows no two handlers for one citation and role, and a lookup finds a subdivision handler before a section’s, so this one is registered under the subdivision. `accepts` takes an arrival that is this form (the marker `NC`, a PayHOA form id, a Google or title match). `read` is evidence only: the answers as a `FormAnswers`, compared with what is on the books (`owner_prefill.compare`). `plan` lists only the delivery tag writes and an email or mailing change, with each reason; it writes nothing outside jason and sets no “answered this cycle” tag, since a change is not the annual answer.
- **What it sets:** the same delivery tags the annual form sets, by the same rules ([owner-information.md](../owner-information.md), “Never over newer information”): a this-cycle or later written answer sets them; a deed after the answer’s date belongs to the prior title and changes nothing; the owner’s later profile edit stands. A choice of “By mail” only removes the email tag and does not delete the email on the owner’s profile, which is the owner’s own login; the member is told so.
- **Procedure:** `delivery-requests` does not exist in `src/jason/community/procedures.py` (keys today: owner-info-cycle, board-packet, mailroom-letter, notice-delivery, election, rule-change, law-review, document-intake, respond, duty-schedule, and others). Add it, for this form and for [secondary-address.md](secondary-address.md) and [individual-delivery-request.md](individual-delivery-request.md), with steps: (1) check for new delivery requests (`jason responses --check`); (2) stamp the receipt date and acknowledge; (3) read each return and confirm who sent it (assurance); (4) plan the writes and apply them as a person’s `--yes`; (5) **before any individual-notice batch, read the changes received and not yet recorded**, so a batch never goes the old way; (6) read bounces and resend by the other address (4041(e)); (7) write each failure as a lesson. The step in (5) is the one that keeps the change effective from receipt. Until the procedure exists, `owner-info-cycle` is the nearest (its “record the answers” step), and `notice-delivery` covers the resend.
- **jason never:** approves or denies the change, edits an owner’s submission, or sends a notice by a new method before a person confirms the return (AGENTS.md, Boundaries).

## 12. Edge cases

- **Co-owners.** Each is a member and has a delivery choice of their own; the books hold it per owner. A change signed by one co-owner is that owner’s. A form signed “for all owners” needs every name or a stated authority; PROPOSED POLICY: where two co-owners’ written changes differ, the later received governs for the notice sent to that unit’s shared address, both co-owners are told, and each keeps their own tag. For the board and counsel (lead 3).
- **A representative.** A person with a power of attorney or other written authority may sign for the owner; the form’s `capacity` and attestation say so, and the authority is attached. The legal representative the owner names on the annual form (4041(a)(3)) is a contact, never a recipient of notices, and the form does not make them one.
- **A tenant or another non-owner.** A tenant is not a member (4160). The association may answer a tenant politely and does not change the owner’s delivery on a tenant’s form. A tenant who wants copies goes through the owner, by the owner’s second address ([secondary-address.md](secondary-address.md)).
- **Language and accessibility.** The statutory words stay in English; the plain-words note may be translated. Large print, another format, a person to read the form aloud or write it down, and a reasonable accommodation are offered on the form; a request written down by the association is returned to the member for confirmation.
- **No form used.** An email or letter that says “send my notices by email” (or by mail) is a change in writing. The handler reads it into the same fields, marks what is missing (an email address, if email is chosen), and asks once. The date received is the day it arrived.
- **A telephone request.** 4041(b)(2)(B) says “in writing”. PROPOSED POLICY: a person writes it down, dates it, sends it back for the member’s confirmation, and the date received is the day the member’s confirmation arrives; a call alone does not change delivery.
- **The request is really something else.** “Stop mailing me paper” may be a change to email delivery (this form) or the paper billing statement choice (the billing system, not a notice under the Act). “Remove my email from your system” is a profile edit by the member, not a delivery change. “Send everything to my accountant” is a second address ([secondary-address.md](secondary-address.md)). The handler reads the request, routes it the same day, and tells the member which form it used.
- **An email already in the books that bounced.** The member may use this form to give a working address; a bounced address is “no longer valid” (4041(e)) and does not count as a valid method.

## 13. Leads for the board and counsel

A reading is labeled as one and whose it is. A conflict between a document and the statute is noted, never resolved.

1. **To whom a change of preferred method goes.** 5260 lists seven requests that are effective only when “delivered in writing to the association, pursuant to Section 4035”; a change of the preferred method is not among them, and 4041(b)(2)(B) says only “in writing”. The form tells the member the 4035 address and also accepts the change by every channel in section 9. Counsel confirms whether a change delivered somewhere else is effective, and the board adopts a written policy so each is treated the same way.
2. **The date a change takes effect.** The Act sets none. The proposed policy (effective for every notice begun on or after the day received) gives 4040(a)(1) its plainest reading and avoids a resend; the board may choose a later day, such as the first day after recording, in writing. A notice that is “general” and posted (4045(a)(3)) is unaffected.
3. **Co-owners with different choices.** The Act speaks of “the member’s preferred delivery method”. How it applies to two members at one unit is not stated. For counsel before the board adopts the proposed rule of section 12.
4. **“Email” with no address.** A choice of email with no valid address cannot be delivered. Reading (labeled): the prior method continues until a valid address is given, and the member is asked once (4041(e), 4041(c)). The form says so beside the box.
5. **Annual solicitation text.** The built annual form says a member may change preferences “by submitting this form again or by writing to the Association” and does not point to this short form ([owner-information.md](owner-information.md), the mapping page). Once this form is offered, the annual solicitation links to it as its “simple method”.
6. **A change that arrives inside the 30 days.** 4041(b)(1) puts the answers in the books “at least 30 days before” the annual reports. It does not say whether a later written change is honored for those reports. The proposed policy honors it. For the board.
7. **Reading 4055.** An emailed form is “in writing” only when it is “an electronic record capable of retention by the recipient”. A change by reply email, a PDF, or the PayHOA form meets that; a change typed into a chat or a text message may not. The handler asks the member to use the form in that case.

## 14. Test fixtures

Made-up answers. All use plainly fake data.

**Typical** (an owner changes from mail to email):

| Field | Answer |
|---|---|
| `name` | A. Owner |
| `unit-address` | 123 Main St, Anytown, CA 90000 |
| `capacity` | An owner of this unit |
| `delivery` | By email |
| `email` | `a.owner@example.org` |
| `attestation` | ticked; signed 2026-03-02 |

Expected: delivery tags set to email only; the mail tag removed; the owner’s profile email unchanged if it already is this address; acknowledgment with `{EFFECTIVE}` = the date received; no “answered this cycle” tag.

**Minimal** (the smallest valid return): `name`, `unit-address`, `capacity`, `delivery` = By mail, `mailing-same` ticked, signature. Expected: mail delivery to the unit address (4041(c)); no email asked; nothing else changed.

**Edge cases:**
- Email chosen, `email` blank: the return is read as incomplete; the prior method continues; one request for an address; the clock for the acknowledgment still runs from the day received (lead 4).
- Both boxes ticked, a mailing address in another state: both tags set; the mailing address recorded.
- Two co-owners return different forms the same week: both recorded per owner; each told; the unit’s shared mailing follows the later received (section 12).
- A tenant signs `capacity` = “Someone the owner has authorized” with no attached authority: held as a lead; the owner is written to at the address on file.
- A form that arrives with no marker (a photocopy): identified by its printed lines and its title; a person attaches it to its campaign.
- A change received 10 days before the annual reports: effective (row 4), the entry date unchanged.

**The statutory checklist test, in words.** (1) The rendered form contains the 4041(b)(2)(A) statement that an email address is not required. (2) The form offers mail, email, or both, and no email question is required unless email is ticked (a question with `required_if`). (3) The form carries the words “any day of the year” and no return-by date. (4) The recital block contains the exact words of 4041(b)(2)(B), 4041(b)(2)(A), 4041(a)(1), 4041(c), 4041(e), and 4040(a), each filled from the shelf, with the build failing if a cited subdivision is gone (the recital-freshness test). (5) The form asks no phone number, no reason, and no occupancy. (6) The form names the person who receives it (4035) and an email or mail address. (7) The acknowledgment carries `{RECEIVED}`, `{EFFECTIVE}`, `{DUE}`, `{DECIDER}`, and `{REFERENCE}`. (8) The same template renders the paper, the fillable PDF, the email, and the PayHOA sheet with the same questions in the same order, each carrying `NC`. (9) A made-up return of each fixture reads back to the same answers after a bad scan (`jason form-fuzz`).
