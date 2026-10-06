# Notice of a disputed charge, paid under protest

Status: design (2026-10-05). Key `disputed-charge`; proposed marker code `PR` (protest). It follows the standard in [form-templates.md](../form-templates.md). The inventory row is “Pay under protest” ([standard-forms.md](../standard-forms.md)), which says the notice is “a right of the owner (and a path to small claims), not a request the association grants; the notice is the evidence”, and that jason does not read it as a request kind today. The form is the owner’s record of the protest and the association’s record that it was told. The related forms are [idr-request.md](idr-request.md), [adr-request.md](adr-request.md), and [payment-plan.md](payment-plan.md).

## 1. Authority and what the law requires

As of: the shelf’s 2025 session publication of the code (`data/authorities/CIV/CIV-5650-5690.md`, `CIV-5900-5920.md`, `CIV-5925-5965.md`, read with lawlibrary, 2026-10-05). None of these sections was amended in 2025 (5658 was added by Stats. 2012, Ch. 180). jason’s copy is not an official restatement.

**CIV 5658** (the right, in full):

> (a) If a dispute exists between the owner of a separate interest and the association regarding any disputed charge or sum levied by the association, including, but not limited to, an assessment, fine, penalty, late fee, collection cost, or monetary penalty imposed as a disciplinary measure, and the amount in dispute does not exceed the jurisdictional limits of the small claims court stated in Sections 116.220 and 116.221 of the Code of Civil Procedure, the owner of the separate interest may, in addition to pursuing dispute resolution pursuant to Article 3 (commencing with Section 5925) of Chapter 10, pay under protest the disputed amount and all other amounts levied, including any fees and reasonable costs of collection, reasonable attorney’s fees, late charges, and interest, if any, pursuant to subdivision (b) of Section 5650, and commence an action in small claims court pursuant to Chapter 5.5 (commencing with Section 116.110) of Title 1 of the Code of Civil Procedure.
>
> (b) Nothing in this section shall impede an association’s ability to collect delinquent assessments as provided in this article or Article 3 (commencing with Section 5700).

**CIV 5650** (the debt and what is levied with it):

> (a) A regular or special assessment and any late charges, reasonable fees and costs of collection, reasonable attorney’s fees, if any, and interest, if any, as determined in accordance with subdivision (b), shall be a debt of the owner of the separate interest at the time the assessment or other sums are levied.
>
> (b) Regular and special assessments levied pursuant to the governing documents are delinquent 15 days after they become due, unless the declaration provides a longer time period, in which case the longer time period shall apply. If an assessment is delinquent, the association may recover all of the following: (1) Reasonable costs incurred in collecting the delinquent assessment, including reasonable attorney’s fees. (2) A late charge not exceeding 10 percent of the delinquent assessment or ten dollars ($10), whichever is greater, unless the declaration specifies a late charge in a smaller amount, in which case any late charge imposed shall not exceed the amount specified in the declaration. (3) Interest on all sums imposed in accordance with this section, including the delinquent assessments, reasonable fees and costs of collection, and reasonable attorney’s fees, at an annual interest rate not to exceed 12 percent, commencing 30 days after the assessment becomes due, unless the declaration specifies the recovery of interest at a rate of a lesser amount, in which case the lesser rate of interest shall apply.

**CIV 5655(a), (b)** (how a payment is applied; the receipt):

> (a) Any payments made by the owner of a separate interest toward a debt described in subdivision (a) of Section 5650 shall first be applied to the assessments owed, and, only after the assessments owed are paid in full shall the payments be applied to the fees and costs of collection, attorney’s fees, late charges, or interest.
>
> (b) When an owner makes a payment, the owner may request a receipt and the association shall provide it. The receipt shall indicate the date of payment and the person who received it.

**CIV 5930(c), (d)** (alternative dispute resolution is not a prerequisite here):

> (c) This section does not apply to a small claims action.
>
> (d) Except as otherwise provided by law, this section does not apply to an assessment dispute.

**CIV 5685(c)** (when the association finds the charge was wrong and a lien was recorded):

> If it is determined that an association has recorded a lien for a delinquent assessment in error, the association shall promptly reverse all late charges, fees, interest, attorney’s fees, costs of collection, costs imposed for the notice prescribed in Section 5660, and costs of recordation and release of the lien authorized under subdivision (b) of Section 5720, and pay all costs related to any related dispute resolution or alternative dispute resolution.

**CIV 5915(b)(1), (2)** (an owner who also asks to meet and confer: [idr-request.md](idr-request.md)):

> (1) The party may request the other party to meet and confer in an effort to resolve the dispute. The request shall be in writing.
>
> (2) A member of an association may refuse a request to meet and confer. The association shall not refuse a request to meet and confer.

Cited, not recited: CIV 5660(c) (the pre-lien notice says the owner is not liable for charges, interest, and costs “if it is determined the assessment was paid on time”); 5670 (the offer to meet and confer before a lien); 5690 (a failure to follow the article’s procedures); 5235 (records).

Not on the shelf (listed in the report): CCP 116.110 to 116.290 (small claims), including 116.220 and 116.221, which 5658(a) cites for the jurisdictional limit. The form states no dollar limit.

**What the law does not say** (leads in section 13): the statute requires no notice to the association at all; it says what the owner “may” do. It does not say what the association must do on a protest, how soon, or whether it must stop collecting the disputed amount, refund, or reply. It does not say what a protest must contain. It does not say whether a payment of less than “all other amounts levied” is a payment under protest.

## 2. Who uses it, and when

- **An owner** who disputes a charge or sum the association levied (an assessment, a fine, a penalty, a late fee, a collection cost, a monetary penalty imposed as a disciplinary measure, 5658(a)), where the amount in dispute is within the small-claims limit, and who is paying it anyway to keep the account clear while reserving the dispute.
- When: **at the time of payment**, or soon after. The owner pays “the disputed amount and all other amounts levied” and tells the association the payment is under protest.
- The form is offered with the pre-lien notice and in every letter that bills a charge, so an owner who disagrees finds it where the charge appears; and on request.
- Not served: an owner who wants a payment plan ([payment-plan.md](payment-plan.md)); one who wants to meet with a director ([idr-request.md](idr-request.md)); one who wants a neutral ([adr-request.md](adr-request.md)). The form carries one checkbox for the first of these, because the statute lets the owner do both (“in addition to”), and a written request to meet and confer is all 5915(b)(1) asks.

## 3. What the form must carry

The statute prescribes no content, so the checklist is the elements of 5658(a) that make a payment a payment under protest, plus what the association needs to record it.

| # | What the section supports | Words | Carried by |
|---|---|---|---|
| 1 | A dispute exists between the owner and the association about a charge or sum levied | 5658(a) “a dispute exists ... regarding any disputed charge or sum levied by the association” | `charge-kind`, `charge-description`, `why` |
| 2 | The amount in dispute (so it can be read against the small-claims limit) | 5658(a) “the amount in dispute does not exceed the jurisdictional limits of the small claims court” | `charge-amount` |
| 3 | The owner pays “the disputed amount and all other amounts levied” | 5658(a) “pay under protest the disputed amount and all other amounts levied, including any fees and reasonable costs of collection, reasonable attorney’s fees, late charges, and interest, if any” | `paid-amount`, `paid-date` |
| 4 | The payment is under protest | 5658(a) “pay under protest” | `protest` (a checkbox, required) |
| 5 | The owner may also pursue dispute resolution; the owner may commence a small claims action | 5658(a) “in addition to pursuing dispute resolution”; “commence an action in small claims court” | fixed text (recital) |
| 6 | The association’s ability to collect delinquent assessments is not impeded | 5658(b) | fixed text |
| 7 | A receipt on request, showing the date and who received the payment | 5655(b) | `receipt` |
| 8 | A request to meet and confer, in writing, if the owner wants one | 5915(b)(1) | `also-meet-confer` |
| 9 | An email only if the owner chooses email | 4041(b)(2)(A); standard 2 | `email` |
| 10 | A request in other words is still a request; help | standard 5 | fixed text |

## 4. The questions

Kinds: text, choice, checkbox, email, phone, address, paragraph, date. “Required” says when; the template needs `required_if` ([records-request.md](records-request.md), section 11).

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `name` | Your name | text | yes | the owner (5658(a): “the owner of a separate interest”) | NAME | request.requester |
| `unit-address` | Unit address | address | yes | the account the charge is on | ADDRESS (prefilled on a copy) | request.unit |
| `charge-kind` | What kind of charge do you dispute? | choice: “An assessment”; “A fine, penalty, or monetary penalty imposed as discipline”; “A late fee”; “A collection cost or attorney’s fee”; “Interest”; “Another charge” | yes | 5658(a) lists the kinds | TEXT | request.charge_kind |
| `charge-description` | Which charge? (the date, the notice or statement it was on, what it says) | paragraph | yes | the association must find the charge on the account | TEXT | request.charge |
| `charge-amount` | The amount you dispute | text (an amount) | yes | 5658(a): the amount in dispute | TEXT | request.disputed_cents |
| `why` | Why do you dispute it? | paragraph | yes | 5658(a): “a dispute exists” | TEXT | request.why |
| `paid-amount` | The total you are paying: the disputed amount and all other amounts on your account | text (an amount) | yes | 5658(a): “the disputed amount and all other amounts levied” | TEXT | request.paid_cents |
| `paid-date` | The date you paid or will pay | date | yes | the date of payment is the date of the protest | TEXT | request.paid_on |
| `protest` | I am paying this under protest. I dispute the charge described above | checkbox (one box) | yes | 5658(a) | TEXT | request.protest = present |
| `receipt` | Send me a receipt for this payment | checkbox (one box) | no | 5655(b): “the owner may request a receipt and the association shall provide it” | TEXT | request.receipt_requested |
| `also-meet-confer` | Also: I ask to meet and confer with a director about this charge | checkbox (one box) | no | 5658(a) “in addition to pursuing dispute resolution”; 5915(b)(1) | TEXT | request.also = meet-and-confer; opens [idr-request.md](idr-request.md)’s clocks |
| `contact-method` | How should we reach you about this? | choice: “By email”; “By phone”; “By mail” | yes | the association’s reply | TEXT | request.contact_method |
| `email` | Email address | email | only if `contact-method` is email | 4041(b)(2)(A): never otherwise | EMAIL | request.email (on the request only) |
| `phone` | Phone number | phone | only if `contact-method` is phone | as above | PHONE | request.phone (on the request only) |
| `mailing-address` | Mailing address | address | only if `contact-method` is mail | 4040(a) | ADDRESS; “Same as my unit address” box | request.mail_to |
| (signature) | Signature and date | signature line, date | yes | the owner’s own statement of the protest | NAME | request.signed |

Not asked, on purpose: how the owner is paying (a card, a bank, or an account number is never written on the form: the form says so in bold; payment goes through the usual channel); whether the owner will sue (5658(a) says “may”); why the owner paid late; the owner’s income; a promise to sue or not to sue.

The Request for Resolution under 5935 is its own form ([adr-request.md](adr-request.md)): it has required content this form does not carry, so a checkbox here cannot stand for it. The form’s help line says: “To ask for alternative dispute resolution, use the Request for Resolution form.”

## 5. The recitals

| Token | Subdivisions | Why it opens the form |
|---|---|---|
| `{QUOTE:CIV 5658(a)}` | (a) | the right |
| `{QUOTE:CIV 5658(b)}` | (b) | collection is not impeded |
| `{QUOTE:CIV 5655(b)}` | (b) | the receipt |
| `{QUOTE:CIV 5655(a)}` | (a) | how a payment is applied |
| `{QUOTE:CIV 5930(c)}` | (c), (d) | ADR is not required before small claims or, except as the law provides, for an assessment dispute |

A plain-words note follows, labeled “The association’s plain-words note; the words above control”.

## 6. What the member is told

> If you dispute a charge the association has billed to you, you may pay it under protest and then bring an action in small claims court, if the amount in dispute is within that court’s limit (Civil Code 5658(a)). You pay the disputed amount and all the other amounts on your account. You may also ask to meet and confer, or ask for alternative dispute resolution, in addition to paying under protest. Paying under protest does not stop the association from collecting delinquent assessments (Civil Code 5658(b)). Your payment is applied first to assessments, then to fees and costs, attorney’s fees, late charges, and interest (Civil Code 5655(a)); if you ask, we will give you a receipt showing the date and who received the payment (Civil Code 5655(b)). We will record your protest on your account and tell the board. {DECIDER} will write to you within 30 days to say whether the association will correct the charge, look at it again, or stand by it. The association decides whether to change a charge; the law does not set a time for it to answer. The courts decide a small claims case; the association does not decide it for you. If the association has recorded a lien in error, it must promptly reverse the charges and pay the costs of dispute resolution (Civil Code 5685(c)).

Reading (the association’s plain-words note; the statute’s words are above): the sentence that the law sets no time for the association to answer states what the shelf shows; the 30 days are the association’s proposed policy (section 7).

## 7. The association's clocks

The statute sets no clock for the association. Every row is a PROPOSED POLICY for the board unless it says statute.

| # | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| 1 | receipt | acknowledge within 2 business days | PROPOSED POLICY | none in the law |
| 2 | receipt | record the protest on the account: within 2 business days, with the date, the amount, and the charge | PROPOSED POLICY | the association cannot show it was told; the owner’s evidence is the form |
| 3 | the payment | a receipt, if asked, showing the date of payment and who received it: “shall provide it” (5655(b)); proposed: within 5 business days | statute (the duty); PROPOSED POLICY (the time) | the association has not done what 5655(b) says (“shall provide it”); what follows is for counsel |
| 4 | receipt | put the protest on the board’s next agenda, with the amounts and the charge | PROPOSED POLICY | the board does not know it has a protest |
| 5 | receipt | the association’s written answer: whether it will correct the charge, review it, or stand by it, and the routes (meet and confer, ADR, small claims): within 30 calendar days | PROPOSED POLICY | the owner has no answer; the association’s record of good faith is weaker |
| 6 | a determination that a lien was recorded in error | the lien release within 21 days (5685(b)); “promptly reverse all late charges, fees, interest...” (5685(c)) | statute | the association is liable for the costs 5685(c) names |
| 7 | the written request to meet and confer, if `also-meet-confer` is checked | as in [idr-request.md](idr-request.md), section 7 | the association’s procedure; PROPOSED POLICY | as there; the association “shall not refuse” (5915(b)(2)) |
| 8 | the owner’s payment | the owner’s time to bring a small-claims action | not on the shelf (CCP 116.110 and following; no period is stated in 5658) | for counsel |

## 8. The acknowledgment text

> Reference {REFERENCE}. We received your notice that you dispute the charge described and have paid under protest, on {RECEIVED}. We recorded the protest on your account on {RECORDED}. {DECIDER} will write to you by {DUE} to say what the association will do. Your payment is applied as Civil Code 5655(a) requires, and you will receive a receipt if you asked for one. If you also asked to meet and confer, a director will be designated and will contact you; the association does not refuse that request and there is no fee. If you want to add to your notice, write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.

`{DUE}` is the date of row 5 (`{RECEIVED}` plus 30 days); `{RECORDED}` is the date of row 2.

## 9. Channels and the reference

- **Channels:** paper, fillable PDF, email, PayHOA, portal. A PayHOA submission accompanies a PayHOA payment and is the strongest evidence (`SIGNED_IN`); the paper form goes with a check. Payment itself is never taken through the form.
- **Marker code proposed: `PR`** (protest). No collision found. The blank is a campaign marker (`PR26M-…`, `PR26P-…`).
- The reference is a hint; the form is recognized by its heading and its citation `CIV 5658`. A check with “under protest” in its memo line and no form is read as a lead (section 12).

## 10. Profile slots

| Slot | What it is |
|---|---|
| `{ASSOCIATION}` | the association’s name |
| `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}` | where the notice goes |
| `{BOARD_CONTACT}` | who answers |
| `{PAYMENT_CHANNELS}` | the ways to pay (the portal, a lockbox, a mailing address for overnight payment, which the annual policy statement carries, 5655(c)) |
| `{ANSWER_DAYS}` | the proposed 30-day answer, once adopted |
| `{ACK_DAYS}` | the proposed acknowledgment days |

## 11. Handler and procedure

- **Handler:** `@handler("CIV 5658", role=Role.REQUEST, form="disputed-charge", procedure="disputed-charge")`. It accepts an arrival that is this form (`PR`) or a letter or memo that says the owner pays “under protest”. `plan` records the protest against the account (a plan for a person to enter; jason writes no ledger entry), drafts the acknowledgment, opens clocks 2 to 5, adds a board item, and, when `also-meet-confer` is checked, opens the clocks of [idr-request.md](idr-request.md). It never refunds or reverses a charge, never decides the dispute, and never advises the owner to sue.
- **Kind:** there is no response kind for it. `ResponseKind` has `PAYMENT_PLAN`, `DISPUTE`, and `ADR`, but not a protest, and `KIND_RULES` has no row for “under protest”; a letter that says so is read as `OTHER` or `DISPUTE`. Add a kind and a `KindRule` for it, with a `ResponseRule` whose `source` is `POLICY` until the board adopts clocks 2 to 5.
- **Procedure:** none exists. Add `disputed-charge`: (1) stamp the receipt; (2) record the protest and the payment; (3) acknowledge; (4) give the receipt if asked; (5) read the charge against the governing documents and the books with the manager; (6) put it on the next agenda; (7) the board’s answer, in writing; (8) correct the charge or stand by it, and record why. If a lien is involved, the procedure sends the matter to the collections step before anything is recorded.
- **jason never:** reverses a charge, sends a refund, or records or releases a lien (AGENTS.md).

## 12. Edge cases

- **Co-owners.** Each owner is “the owner of a separate interest”. One owner’s notice is a notice for the account. The reply goes to the one who wrote, and the handler tells the others if the account is joint.
- **A representative.** An owner may have someone pay and write; the protest is the owner’s statement, so the owner’s signature or writing is asked for, and a power of attorney is accepted.
- **A tenant.** The charge is the owner’s debt (5650(a)); a tenant who pays for the owner is told the owner must make the protest.
- **A minor.** Not asked; counsel.
- **Language and accessibility.** The statutory words are English; a plain-words note may be translated; another format, large print, and help in completing the form are offered on it.
- **A request that arrives without the form.** A check marked “under protest” in its memo line, or a letter saying so, is a lead, not a protest the association can ignore: the handler records the payment and the words, sends the form to the owner for the details (the charge, the amount, why), and does not treat the missing form as no protest. The date of the payment is the date of the protest.
- **A payment of less than everything.** 5658(a) speaks of paying “the disputed amount and all other amounts levied”. A smaller payment marked “protest” is applied by 5655(a), and the owner is told that the association’s collection continues on what is unpaid (5658(b)); the form says so.
- **A request that is really something else.** A request for the account’s ledger is [records-request.md](records-request.md). A request to pay in instalments is [payment-plan.md](payment-plan.md). A request to meet with a director is [idr-request.md](idr-request.md). A request to be heard on a fine is a request for a hearing under 5855, and its own notice.
- **A charge on which a lien has been recorded.** The handler sends the matter to the board and counsel at once; 5685 governs a lien recorded in error.
- **A disciplinary monetary penalty.** 5658(a) names it; the handler links the protest to the hearing record (5855), and does not decide the discipline.

## 13. Leads for the board and counsel

Drift: none found. The inventory row (`standard-forms.md`) says the notice is “the evidence” and that jason reads no kind for it; this design adds one in a suggestion, section 11. The notice catalog has no row for the protest, since the statute requires no notice; a row may be added with `delivers=False` if the board wants the clocks of section 7 tracked as occurrences.

Leads (open questions; none settled here):

1. **The statute asks for no notice.** 5658(a) says what the owner “may” do. Whether a payment is “under protest” if no notice reaches the association is a question for counsel. The form’s purpose is evidence: the association records the protest and the owner has a dated copy.
2. **“All other amounts levied.”** The owner who pays only the undisputed part, or part of the debt, is not obviously within 5658(a). PROPOSED POLICY: the association records such a payment as a payment marked “protest”, applies it under 5655(a), and tells the owner what 5658(a) says; whether it is a payment under protest is for counsel.
3. **What the association does about a protested charge.** The law sets no duty. PROPOSED POLICY (the board adopts): row 4 and row 5 above, a written answer in 30 days, and a rule that the association does not add fees to the disputed amount for the protest itself. Where the association agrees the charge was wrong, it corrects it and the board records why; 5685(c) is the statute’s model for a lien recorded in error.
4. **A consistent practice.** A protest the association handles the same way each time is the board’s record of good faith (AGENTS.md, “Where the law is silent, write it down”). The page’s rows 1 to 5 are the proposal.
5. **The jurisdictional limit.** The limit is in CCP 116.220 and 116.221, not on the shelf. Until it is, the handler does not say whether an amount is within it; it flags an amount in dispute above `{SMALL_CLAIMS_LIMIT}` (a profile slot once the sections are on the shelf) for counsel.
6. **Interest and late fees while a charge is disputed.** Whether they continue to run on the disputed part is not answered by 5658; 5650(b) allows them on a delinquent assessment. The owner has paid everything, so the question is whether they are refunded if the owner wins; for counsel.
7. **A protest against a fine.** 5855 requires a hearing before a monetary penalty is imposed. A protest of a fine the board never heard may mean the notice step was missed; the handler links the protest to the hearing record for the board.
8. **ADR is not required.** 5930(c), (d) exclude a small-claims action and, except as the law provides, an assessment dispute from the prerequisite. A request for resolution is still available (5658(a): “in addition to”), and 5660(f) and 5705(b) provide ADR before foreclosure.
9. **Payment channels.** The form never carries a card or bank number; a payment is made through the association’s ordinary means.

## 14. Test fixtures

**Typical** (an owner disputes a late fee, by email, and asks for a receipt):

| Field | Answer |
|---|---|
| `name` | A. Owner |
| `unit-address` | 123 Main St |
| `charge-kind` | A late fee |
| `charge-description` | The late fee on the October statement |
| `charge-amount` | $25.00 |
| `why` | I paid on the 10th and have a receipt dated the 10th |
| `paid-amount` | $325.00 |
| `paid-date` | 2026-10-05 |
| `protest` | checked |
| `receipt` | checked |
| `contact-method` | By email |
| `email` | a.owner@example.test |
| signature | A. Owner, 2026-10-05 |

Expected: no problems; clocks 2 to 5 opened; `{DUE}` = receipt + 30 calendar days; a board item; no refund.

**Minimal:**

| Field | Answer |
|---|---|
| `name` | A. Owner |
| `unit-address` | 123 Main St |
| `charge-kind` | An assessment |
| `charge-description` | The special assessment of 2026 |
| `charge-amount` | $500.00 |
| `why` | The notice was not sent as the documents require |
| `paid-amount` | $1,250.00 |
| `paid-date` | 2026-10-05 |
| `protest` | checked |
| `contact-method` | By mail |
| `mailing-address` | 123 Main St |
| signature | A. Owner |

Expected: no email; no receipt requested; no meeting requested.

**Edge** (a payment by check marked “under protest”, with no form; a lien already recorded; a co-owner; the amount above the limit):

| Field | Answer |
|---|---|
| a check | the memo line says “under protest”, the amount is a partial payment, no form attached |
| (later) `name` | B. Owner |
| `charge-kind` | A collection cost or attorney’s fee |
| `charge-amount` | $9,000.00 |
| `also-meet-confer` | checked |

Expected: the handler records a protest lead on the day of the check, sends the form, and applies the check by 5655(a); it flags the amount (above `{SMALL_CLAIMS_LIMIT}` when set) and the recorded lien for the board and counsel; `also-meet-confer` opens the meet-and-confer clocks.

**The statutory checklist test, in words.** (a) Each row of section 3 names its authority and its carrier; (b) `protest` exists, is required, and its words include “under protest” as 5658(a) writes it; (c) the recital of 5658(a) contains the words “pay under protest the disputed amount and all other amounts levied” and 5658(b) contains “Nothing in this section shall impede an association’s ability to collect delinquent assessments”; (d) `paid-amount` is required and its text says “all other amounts”; (e) no question asks for a card, bank, or account number, an income, or a promise to sue; (f) `email` is required exactly when `contact-method` is email; (g) the form says in bold that no account number is to be written on it; (h) every recital token resolves against the shelf and names an existing subdivision; (i) the clocks in section 7 are all labeled PROPOSED POLICY except row 6 (statute), so the test fails if one is presented as the law’s. The scan and marker tests are as in [records-request.md](records-request.md).
