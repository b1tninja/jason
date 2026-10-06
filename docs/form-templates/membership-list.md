# Request for the membership list, and the opt-out of sharing it

Status: design (2026-10-05). Key `membership-list`; proposed marker code `MN`. It follows the standard in [form-templates.md](../form-templates.md). The inventory row is "Request for the membership list or to opt out of it" ([standard-forms.md](../standard-forms.md)). The records request for everything else is [records-request.md](records-request.md); a member who asks for the list on that form is routed here.

One template, one question first (`action`): ask for the list, opt out, or end an opt-out. The three share the member’s identity and the signature, so one form serves them; the questions that belong to one action are required only for that action.

## 1. Authority and what the law requires

As of: the shelf’s 2025 session publication of the code (`data/authorities/CIV/CIV-5200-5240.md`, read with lawlibrary, 2026-10-05) and the Corporations Code text on the shelf (`data/authorities/CORP/CORP-8310-8340.md`). jason’s copy is not an official restatement.

**CIV 5200(a)(9)** (what the list is):

> (9) Membership lists, including name, property address, mailing address, email address, as collected by the association in accordance with Section 4041 where applicable, but not including information for members who have opted out pursuant to Section 5220.

**CIV 5210(b)(6)** (the clock, by reference):

> (6) Membership list, within the timeframe specified in Section 8330 of the Corporations Code.

**CIV 5220** (the opt-out, in full):

> A member of the association may opt out of the sharing of that member’s name, property address, email address, and mailing address by notifying the association in writing that the member prefers to be contacted via the alternative process described in subdivision (c) of Section 8330 of the Corporations Code. This opt-out shall remain in effect until changed by the member.

**CIV 5225** (the purpose statement, in full):

> A member requesting the membership list shall state the purpose for which the list is requested which purpose shall be reasonably related to the requester’s interest as a member. If the association reasonably believes that the information in the list will be used for another purpose, it may deny the member access to the list. If the request is denied, in any subsequent action brought by the member under Section 5235, the association shall have the burden to prove that the member would have allowed use of the information for purposes unrelated to the member’s interest as a member.

**CORP 8330** (the demand, the timeframes, the alternative):

> (a) Subject to Sections 8331 and 8332, and unless the corporation provides a reasonable alternative pursuant to subdivision (c), a member may do either or both of the following as permitted by subdivision (b):
>
> (1) Inspect and copy the record of all the members’ names, addresses and voting rights, at reasonable times, upon five business days’ prior written demand upon the corporation which demand shall state the purpose for which the inspection rights are requested; or
>
> (2) Obtain from the secretary of the corporation, upon written demand and tender of a reasonable charge, a list of the names, addresses and voting rights of those members entitled to vote for the election of directors, as of the most recent record date for which it has been compiled or as of a date specified by the member subsequent to the date of demand. The demand shall state the purpose for which the list is requested. The membership list shall be made available on or before the later of ten business days after the demand is received or after the date specified therein as the date as of which the list is to be compiled.
>
> (b) The rights set forth in subdivision (a) may be exercised by:
>
> (1) Any member, for a purpose reasonably related to such person’s interest as a member. Where the corporation reasonably believes that the information will be used for another purpose, or where it provides a reasonable alternative pursuant to subdivision (c), it may deny the member access to the list. In any subsequent action brought by the member under Section 8336, the court shall enforce the rights set forth in subdivision (a) unless the corporation proves that the member will allow use of the information for purposes unrelated to the person’s interest as a member or that the alternative method offered reasonably achieves the proper purpose set forth in the demand.
>
> (c) The corporation may, within ten business days after receiving a demand under subdivision (a), deliver to the person or persons making the demand a written offer of an alternative method of achieving the purpose identified in said demand without providing access to or a copy of the membership list. An alternative method which reasonably and in a timely manner accomplishes the proper purpose set forth in a demand made under subdivision (a) shall be deemed a reasonable alternative, unless within a reasonable time after acceptance of the offer the corporation fails to do those things which it offered to do. Any rejection of the offer shall be in writing and shall indicate the reasons the alternative proposed by the corporation does not meet the proper purpose of the demand made pursuant to subdivision (a).

(Subdivision (b)(2), the authorized number of members, is cited, not recited: see section 13.)

**CIV 5230(a), (c)(1)** (what the member and the association may do with the list):

> (a) The association records, and any information from them, may not be sold, used for a commercial purpose, or used for any other purpose not reasonably related to a member’s interest as a member. An association may bring an action against any person who violates this article for injunctive relief and for actual damages to the association caused by the violation.
>
> (c) (1) An association or its managing agent shall not do either of the following: (A) Sell a member’s personal information for any purpose without the consent of the member. (B) Transmit a member’s personal information to a third party without the consent of the member unless required to do so by law, including, but not limited to, Article 5 (commencing with Section 5200).

**CORP 8338(a)** (the same use limit, for a membership list):

> (a) A membership list is a corporate asset. Without consent of the board a membership list or any part thereof may not be obtained or used by any person for any purpose not reasonably related to a member’s interest as a member. Without limiting the generality of the foregoing, without the consent of the board a membership list or any part thereof may not be: (1) Used to solicit money or property unless such money or property will be used solely to solicit the vote of the members in an election to be held by their corporation. (2) Used for any purpose which the user does not reasonably and in good faith believe will benefit the corporation. (3) Used for any commercial purpose or purpose in competition with the corporation. (4) Sold to or purchased by any person.

**CIV 5216(a)** (a member in the Safe at Home program is withheld from every list; never asked on this form): see the text in [records-request.md](records-request.md), section 1. Subdivision (a)(2)(B): “Any membership list that will be shared with other members of the association.”

**CIV 5235(a), (b)** and **CIV 5240(a)**: the member’s remedy and the article’s relation to the Corporations Code are recited in [records-request.md](records-request.md), section 1. 5240(a): “the provisions of this article are intended to supersede the provisions of Sections 8330 and 8333 of the Corporations Code to the extent those sections are inconsistent.”

**What the law requires, in the three parts the form turns on** (what each says, not what it means):

- **The purpose statement.** The member “shall state the purpose for which the list is requested which purpose shall be reasonably related to the requester’s interest as a member” (5225). The Corporations Code says the demand “shall state the purpose” (8330(a)(1), (2)).
- **The list.** It is the names, addresses, and voting rights of the members entitled to vote for directors (8330(a)(2)), and in the Act’s terms the name, property address, mailing address, and email address as collected under 4041, without the members who opted out (5200(a)(9)). It is made available “on or before the later of ten business days after the demand is received or after the date specified therein” (8330(a)(2)).
- **The opt-out.** It is made “by notifying the association in writing that the member prefers to be contacted via the alternative process described in subdivision (c) of Section 8330”, and “shall remain in effect until changed by the member” (5220).

**What the law does not say** (leads in section 13): what the “alternative process” is, beyond 8330(c)’s “written offer of an alternative method of achieving the purpose”; when an opt-out takes effect; whether a denial under 5225 must be in writing, or by when; whether a member may be asked to promise how the list will be used; whether a single co-owner’s opt-out removes the unit’s addresses from the list.

## 2. Who uses it, and when

- **A member who wants the list**, for a purpose related to being a member: to ask other members to sign a petition, to run for the board, to speak to the members about a vote, to propose a recall or an amendment.
- **A member who wants to inspect the record of names and addresses** instead of receiving a list (8330(a)(1)).
- **A member who wants their own information left out** of any list the association shares, or who wants it back in.
- When: the opt-out at any time; the annual owner-information form (Civil Code 4041) offers the same choice each year, and the latest answer stands. The request when a member has a reason to contact the members.
- Who is not served: a vendor, a solicitor, or a person who is not a member; a tenant; a member who wants to send one message to everyone (the alternative process may serve them, section 11).

## 3. What the form must carry

| # | What the law says the form or request carries | Words | Carried by |
|---|---|---|---|
| 1 | A written request or demand | 8330(a)(1), (2) “written demand” | the form; `name`, `unit-address`, signature |
| 2 | A statement of the purpose | 5225; 8330(a) | `purpose` |
| 3 | The purpose is reasonably related to the member’s interest as a member | 5225 | fixed text above `purpose`; the signed statement |
| 4 | Inspect, or receive a list | 8330(a)(1), (2) | `how` |
| 5 | The date the list is compiled as of, if the member names one | 8330(a)(2) “as of a date specified by the member subsequent to the date of demand” | `as-of` |
| 6 | The list is without members who opted out | 5200(a)(9) | fixed text |
| 7 | A charge: reasonable, told before | 8330(a)(2) “tender of a reasonable charge”; 5205(f) | fixed text “What it costs”; stage 2 `agree-cost` |
| 8 | The member’s answer to an alternative the association offers, in writing, with reasons if rejected | 8330(c) | stage 2 `alternative-answer`, `alternative-reasons` |
| 9 | The opt-out: in writing, naming the preference for the alternative process | 5220 | `optout-statement` |
| 10 | The opt-out stays until the member changes it | 5220 | fixed text; `action` “End my opt-out” |
| 11 | The use limits | 5230(a); 8338(a) | fixed text (recital) |
| 12 | An email only if electronic delivery is asked | 4041(b)(2)(A); standard 2 | `email` |
| 13 | A request in other words is still a request; help | standard 5 | fixed text |

## 4. The questions

Kinds: text, choice, checkbox, email, phone, address, paragraph, date. “Required” says which `action` makes a question required; the template needs `required_if` (see [records-request.md](records-request.md), section 11).

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `action` | What do you want to do? | choice: “Ask for the membership list”; “Opt out: do not share my information”; “End my opt-out: share my information again” | yes | 5220, 5225; 8330(a) | TEXT | request.action |
| `name` | Your name | text | yes | identifies the member | NAME | request.requester |
| `unit-address` | Unit address | address | yes | places the member; the opt-out is recorded against the member | ADDRESS (prefilled on a copy) | request.unit |
| `for-whom` | This choice is for | choice: “Me only”; “Me and the other owners of this unit, who have each agreed” | when `action` is an opt-out or its end | 5220 speaks of “a member”; each owner is a member | TEXT | request.scope |
| `how` | You want to | choice: “Inspect and copy the record of members’ names and addresses”; “Receive a list of the names and addresses of the members entitled to vote” | when `action` asks for the list | 8330(a)(1), (2) | TEXT | request.how |
| `purpose` | What is the list for? | paragraph | when `action` asks for the list | 5225; 8330(a) | TEXT | request.purpose |
| `as-of` | List as of this date, if you want a later date than the association’s latest | date | no | 8330(a)(2) | TEXT | request.as_of |
| `delivery` | How should the list reach you? | choice: “By electronic transmission”; “On paper, by mail”; “I will collect it”; “I will inspect it” | when `how` is a list | 5205(h) (the list is an association record, 5200(a)(9)); reading in section 13 | TEXT | request.delivery |
| `email` | Email address | email | only if `delivery` is electronic | 4041(b)(2)(A) | EMAIL | request.email (on the request only) |
| `mailing-address` | Mailing address | address | only if `delivery` is mail | 4040(a) | ADDRESS | request.mail_to |
| `optout-statement` | I prefer to be contacted via the alternative process described in subdivision (c) of Section 8330 of the Corporations Code | checkbox (one box) | when `action` is “Opt out” | 5220 | TEXT | the opt-out tag (the profile’s “membership list opt-out” tag, the same one the owner-information form sets) and the request record |
| (signature) | Signature and date | signature line, date | yes | a written notice (5220); a written demand (8330) | NAME | request.signed |

Stage 2 (the association’s offer of an alternative, or its estimate; pre-filled):

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `alternative-answer` | The association offers the alternative method written above | choice: “I accept the offer”; “I reject the offer” | yes | 8330(c) | TEXT | request.alternative = accepted or rejected |
| `alternative-reasons` | Why the alternative does not meet your purpose | paragraph | if rejected | 8330(c): a rejection “shall indicate the reasons” | TEXT | request.rejection_reasons |
| `agree-cost` | I agree to pay the charge shown above | choice: “I agree”; “I do not agree” | yes, if a charge is shown | 5205(f); 8330(a)(2) | TEXT | request.cost_agreed + amount |

Not asked, on purpose: the member’s email unless delivery is electronic; a phone number; whether the member is in the Safe at Home program (5216(b)); the member’s reason for opting out (5220 asks none).

## 5. The recitals

| Token | Subdivisions | Why it opens the form |
|---|---|---|
| `{QUOTE:CIV 5220}` | whole section | the opt-out and that it stays until changed |
| `{QUOTE:CIV 5225}` | whole section | the purpose, and what a denial means |
| `{QUOTE:CIV 5200(a)}` | (a)(9) | what the list holds and that it leaves out those who opted out |
| `{QUOTE:CIV 5210(b)}` | (b)(6) | the clock is by reference |
| `{QUOTE:CORP 8330}` | (a)(1), (a)(2), (b)(1), (c) | the demand, the ten business days, the alternative |
| `{QUOTE:CIV 5230(a)}` | (a) | the use limit |
| `{QUOTE:CORP 8338(a)}` | (a)(1) to (4) | the board’s consent and the uses a list may not have |

The token key `CORP 8330` follows the references grammar for a Corporations Code section; the build fails if the section or subdivision is gone from the shelf.

## 6. What the member is told

> If you ask for the membership list, tell us what it is for. The reason must be related to your interest as a member of the association. We will make the list available no later than ten business days after we receive your request (or after the date you name for the list, if later). We may, within ten business days, offer you another way to reach the members without giving you the list; you may accept it, or reject it in writing and tell us why. We may refuse to give you the list if we reasonably believe the information will be used for another purpose; if we do, we will say so in writing, and in a later court case the association carries the burden of proving that you would have used it for a purpose unrelated to being a member. The list leaves out members who have opted out. If you opt out, your name, property address, email address, and mailing address are not shared, and members who want to contact you are offered the alternative process; your choice stays in effect until you change it. {BOARD_CONTACT} decides a request the staff cannot grant; if you disagree, ask the board in writing to reconsider; you may also go to court, including small claims court (Civil Code 5235).

Reading (the association’s plain-words note): the sentence about the burden restates 5225’s last sentence.

## 7. The association's clocks

| # | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| 1 | receipt | acknowledge within 2 business days | PROPOSED POLICY (the `acknowledge_days` proposal) | no statutory consequence |
| 2 | the written demand | an inspection of the record of names and addresses at reasonable times upon five business days’ prior written demand | statute: CORP 8330(a)(1) | the member may sue (5235; CORP 8336) |
| 3 | receipt of the demand, or the date the member names for the list if later | the list: “on or before the later of ten business days after the demand is received or after the date specified therein as the date as of which the list is to be compiled” | statute: 5210(b)(6) pointing to CORP 8330(a)(2) | the member may sue; a court that finds the association unreasonably withheld access shall award the member costs and fees and may assess up to $500 for each separate written request (5235(a)) |
| 4 | receipt of the demand | the written offer of an alternative: “within ten business days after receiving a demand” | statute: CORP 8330(c) | the offer is no longer timely; the list is due (reading, counsel) |
| 5 | the offer | the member’s written rejection, with reasons: “Any rejection of the offer shall be in writing” (no time is stated); the association asks for an answer within 10 business days | PROPOSED POLICY | the offer stands as accepted for the purpose of what the association must then do; a reading, counsel |
| 6 | receipt | a denial under 5225 is in writing, with its reason, within the 10 business days of row 3 | PROPOSED POLICY (the law says the association “may deny”, 5225, and sets no time for saying so) | the association’s burden in the member’s action (5225) is harder to carry without a written reason |
| 7 | receipt of the opt-out or its end | the choice is entered in the association’s records within 2 business days and applies to every list made after the day received | PROPOSED POLICY (5220 says the opt-out “shall remain in effect until changed”; it does not say when it starts) | a list made after the day but still carrying the member’s information is a breach of the member’s choice (5230(c)(1)(B)) |
| 8 | the annual solicitation | the same choice, asked each year with the owner-information form; the latest answer by date stands | statute: CIV 4041(a) with the form; 5220 | none; the form carries the same question |
| 9 | the estimate | the member is asked to agree to a charge before the list is copied | statute: 5205(f) (reading: the list is an association record, 5200(a)(9)); 8330(a)(2) “tender of a reasonable charge” | copying waits |

## 8. The acknowledgment text

> Reference {REFERENCE}. We received your {REQUEST_KIND} on {RECEIVED}. If you asked for the membership list, we will make it available, or offer you another way to reach the members, by {DUE}. {DECIDER} handles your request. The membership list leaves out members who have opted out. If you opted out, we recorded your choice on {RECORDED}; it stays in effect until you change it.

`{REQUEST_KIND}` is one of “request for the membership list”, “request to opt out of the membership list”, “request to end your opt-out”. `{DUE}` is the date of row 3 or row 4, whichever applies; for an opt-out the sentence about `{DUE}` is left out and `{RECORDED}` is the date of row 7.

## 9. Channels and the reference

- **Channels:** paper, fillable PDF, email, PayHOA. A request for the list is made by a member, so a signed-in PayHOA answer (`SIGNED_IN`) or a reply email from the address on file (`MATCHED`) is the strongest; a signed paper copy is `CLAIMED`. The opt-out is recorded on the strongest channel at or above `RECORD_AT`; a return below `MATCHED` is first told to the address on file (“we received this change; tell us if it wasn’t you”), since an opt-out changes what others may learn.
- **Marker code proposed: `MN`** (membership). Distinct from `NP` (owner information). Campaign marker for a standing form (`MN26M-…`), copy marker for the stage 2 reply.
- The annual owner-information form carries the same opt-out as a choice; both set the same tag, and the one with the later date stands.

## 10. Profile slots

| Slot | What it is |
|---|---|
| `{ASSOCIATION}` | the association’s name |
| `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}`, `{BOARD_CONTACT}` | where it goes, and who decides |
| `{ALTERNATIVE_METHOD}` | the board’s adopted alternative process for 8330(c): for example, the association forwards the member’s message to the members, without giving the list (a board policy, section 13) |
| `{LIST_RECORD_DATE}` | the most recent date for which the list has been compiled (8330(a)(2)) |
| `{FEE_SCHEDULE}` | the reasonable charge for a list, as the board adopts it |
| `{ACK_DAYS}` | the proposed acknowledgment days |

## 11. Handler and procedure

- **Handler:** `@handler("CIV 5220", "CIV 5225", "CORP 8330", role=Role.REQUEST, form="membership-list", procedure="membership-list")`. For `action` = opt-out or its end, the same handler plans the tag write (the profile’s opt-out tag), a plan, not a write: a person confirms (`--yes`), as for the owner-information answers (`owner_info.plan_writes`). For `action` = list, it opens the clocks of rows 3 to 6 and drafts the acknowledgment; it **prepares** the list with opt-outs removed (`jason.web.extra.records_requests` already says the list is prepared that way and “does not hand the list to anyone; a person produces it”). It never decides whether a purpose is related to membership: that is a person’s, with counsel.
- **Procedure:** none exists for it. `respond` covers the clock. Add `membership-list`: (1) stamp the receipt; (2) a request for the list: read the purpose, and put “related, offer the list”, “related, offer the alternative”, or “not related, deny with reason” before the board’s designee within 5 business days; (3) prepare the list without opt-outs and without any Safe at Home participant (5216(a)); (4) send within the clock, or the written alternative within ten business days; (5) an opt-out: record the choice, tag it, confirm; (6) record each act.
- **Template changes this needs:** `required_if`; a `stage` for the reply.
- **jason never:** hands over the list, denies a request, or decides a purpose (AGENTS.md).

## 12. Edge cases

- **Co-owners.** Each owner is a member. `for-whom` lets one owner speak for all only if each has agreed; otherwise the answer is that owner’s own. A list request from one co-owner is one request.
- **A representative.** A member may designate another person to “inspect and copy ... on the member’s behalf” (5205(b)), in writing; the purpose is the member’s purpose. The form takes the member’s designation as in [records-request.md](records-request.md). An opt-out made by a representative is accepted only with the member’s writing.
- **A tenant or non-owner.** Not a member; 5220 and 5225 speak of a member. The request is answered as an inquiry.
- **A minor.** Not asked; the same reading as in [records-request.md](records-request.md), section 12.
- **Language and accessibility.** The statutory words are English; a plain-words note may be translated; another format, large print, help to complete it, and an accommodation are offered on the form.
- **No form.** A letter saying “I opt out” is a notice “in writing”; the handler records it and sends the form’s opt-out statement back for the member to confirm (the preference for the alternative process in 5220’s words). A letter asking for “the list of owners” is a request for the list without a purpose: the association asks for the purpose once; the clock runs from receipt (reading, lead 4).
- **A member who has opted out asks for the list.** The law does not say whether such a member receives the list, or whether it carries their own entry. 5200(a)(9) leaves out “members who have opted out”, and the entry is the member’s own. PROPOSED POLICY: the member receives the list on the same terms as any member, without their own entry unless they ask for it. The board adopts it; counsel reads it.
- **A member in the Safe at Home program.** The association uses the substitute address and withholds the name, address, and email from any list shared with members (5216(a)). The handler reads the profile’s private register, never a form.
- **A request that is really something else.** A request for “all records” goes to [records-request.md](records-request.md). A request for a resident directory is a membership list request. A vendor or a candidate asks the same way a member does; a candidate who is a member states a purpose like any other (reading, counsel).

## 13. Leads for the board and counsel

**Drift check.** The owner-information form’s membership-list question (`membership-list` in `mystique/forms.py`) offers “Opt me out of sharing my name and addresses (Civil Code §5220)” with the help “requests to contact you go through the Association instead”. 5220 lists “name, property address, email address, and mailing address” and names the preference “to be contacted via the alternative process described in subdivision (c) of Section 8330”. Reading (the association’s): the plain-words help carries the same meaning; the form does not carry the statute’s words, which this template’s `optout-statement` does. Not a conflict; the question’s wording follows this template once it is built from it.

Leads (open questions; none is settled here):

1. **The alternative process.** 5220 points at 8330(c): “a written offer of an alternative method of achieving the purpose ... without providing access to or a copy of the membership list.” The statutes do not say what the association offers a member who wants to contact someone who opted out. The board adopts the method as a written policy (`{ALTERNATIVE_METHOD}`) and records each use. Counsel reads whether it must be offered within the ten business days for every request or only for those that reach an opted-out member.
2. **When the opt-out takes effect.** PROPOSED POLICY in row 7. The board adopts it.
3. **An undertaking.** Whether the association may ask a requester to sign a promise not to misuse the list (5230(a); 8338(a)), or deny a list for want of one, is a question for counsel. This design recites the use limits and does not require a promise.
4. **Written denial and the burden.** 5225 puts the burden on the association in a later action. A denial with a written reason is the board’s best record; the law does not require it. PROPOSED POLICY, row 6.
5. **The charge.** 8330(a)(2) says “a reasonable charge”; 5205(f) says “the direct and actual cost of copying and mailing”; 5240(a) says the article supersedes 8330 and 8333 “to the extent those sections are inconsistent”. Reading (the association’s, proposed): the charge is the direct and actual cost, agreed to beforehand, for both. Counsel confirms.
6. **Voting rights.** 8330(a)(2) speaks of the names, addresses and voting rights of the members entitled to vote; 5200(a)(9) of name, property address, mailing address, and email address. The list’s columns are the profile’s; how voting rights are shown is for the board.
7. **Co-owners.** If one owner of a unit opts out and the other does not, whether the unit’s property and mailing addresses leave the list is open: the address is “that member’s” property address (5220) and also the other member’s. PROPOSED POLICY: the unit’s addresses are withheld if either opts out, until counsel reads it. The board adopts.
8. **The voter list.** 5200(c) lists “the voter list of names, parcel numbers, and voters to whom ballots were to be sent” among association election materials a member may inspect. Whether an opt-out under 5220 reaches the voter list for an election is for counsel.
9. **An authorized number of members.** CORP 8330(b)(2) and 8331 give a group of members a route with a short time for the corporation to go to court (8331(b): a petition within 10 business days). A demand by a group is for counsel on the day it arrives.
10. **A developer-controlled association.** 5240(d): see [records-request.md](records-request.md), lead 7.

## 14. Test fixtures

**Typical** (a member asks for the list to circulate a petition):

| Field | Answer |
|---|---|
| `action` | Ask for the membership list |
| `name` | A. Owner |
| `unit-address` | 123 Main St |
| `how` | Receive a list of the names and addresses of the members entitled to vote |
| `purpose` | To ask members to sign a petition to put a rule change on the agenda |
| `delivery` | By electronic transmission |
| `email` | a.owner@example.test |
| signature | A. Owner, 2026-10-05 |

Expected: no problems; clock row 3 = receipt + 10 business days; the list is prepared without opted-out members and without any Safe at Home participant.

**Minimal** (an opt-out):

| Field | Answer |
|---|---|
| `action` | Opt out: do not share my information |
| `name` | A. Owner |
| `unit-address` | 123 Main St |
| `for-whom` | Me only |
| `optout-statement` | checked |
| signature | A. Owner |

Expected: no email, no purpose asked or required; a plan to tag the member and a confirmation sent to the address on file if the channel is below `MATCHED`.

**Edge** (a co-owner asks for the list without a purpose; the other co-owner has opted out; a representative signs the demand):

| Field | Answer |
|---|---|
| `action` | Ask for the membership list |
| `name` | B. Agent |
| `unit-address` | 456 Elm St |
| `how` | Inspect and copy the record of members’ names and addresses |
| `purpose` | (blank) |
| `delivery` | I will inspect it |
| signature | B. Agent |

Expected: `check()` reports `purpose: required, left blank`; the handler does not reject the request but asks for the purpose once (the clock runs from receipt, lead 4 of this page); the handler flags that the representative’s written designation is missing ([records-request.md](records-request.md)); the list for any later request omits the opted-out co-owner and, by the proposed policy, the unit’s addresses.

**The statutory checklist test, in words.** (a) Every row of the section 3 table names its authority and the key of the question or fixed block that carries it; (b) each question exists, or the fixed block’s words are in the rendered form, in every channel; (c) `purpose` is required exactly when `action` asks for the list; `email` exactly when delivery is electronic; `optout-statement` exactly for an opt-out; (d) the opt-out statement’s words equal “prefers to be contacted via the alternative process described in subdivision (c) of Section 8330 of the Corporations Code” as 5220 reads on the shelf; (e) the form carries no required email, no reason-for-opting-out question, and no Safe at Home question; (f) every recital token resolves against the shelf (CIV 5200-5240; CORP 8330, 8338) and names a subdivision that exists; (g) the clock rows 3 and 4 say ten business days as 8330(a)(2) and (c) state. The scan test and the marker test are as in [records-request.md](records-request.md).
