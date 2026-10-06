# Solar energy system application (`solar`)

Status: design (2026-10-05); built in the form library as `ca/solar.py` (version 1, as of 2026-10-04). Form key `solar`, marker code `PV`, authority `CIV 714, 714.1, 4746`. The standard it follows is [../form-templates.md](../form-templates.md). Like the charger, it is processed "in the same manner as an application for approval of an architectural modification" (714(e)(1)), so it runs on the same procedure (`improvement-request`) and workflow as [architectural-application.md](architectural-application.md) ([../improvement-requests.md](../improvement-requests.md), reused here and not changed), with the statute's own clock and checklist. A disapproval is reconsidered on [reconsideration-request.md](reconsideration-request.md). Its sibling for the electric vehicle is [ev-charger.md](ev-charger.md).

Quotations are from the statutes on jason's authorities shelf (`data/authorities/CIV/CIV-714-714.1.md` and `CIV-4700-4753.md`), which are not official restatements. A reading is labeled as one and is never the rule.

## 1. Authority and what the law requires

**As-of.** The shelf's 2025 session publication of the Civil Code, exported 2026-10-04. CIV 714 is the 2014 amendment (Stats. 2014, Ch. 521, Sec. 2); CIV 714.1 is the 2017 amendment (Stats. 2017, Ch. 818, Sec. 1); CIV 4746 was added by Stats. 2017, Ch. 818, Sec. 3 (AB 634). The shelf's history keeps the two earlier editions of 714 (2009 to 2014 and 2014 to 2015); the current text is the shelf's. The form's recital line says "as on jason's shelf of 2026-10-04. jason's copy is not an official restatement."

**CIV 714, solar energy systems** (the whole section, quoted):

> **(a)** Any covenant, restriction, or condition contained in any deed, contract, security instrument, or other instrument affecting the transfer or sale of, or any interest in, real property, and any provision of a governing document, as defined in Section 4150 or 6552, that effectively prohibits or restricts the installation or use of a solar energy system is void and unenforceable.
>
> **(b)** This section does not apply to provisions that impose reasonable restrictions on solar energy systems. However, it is the policy of the state to promote and encourage the use of solar energy systems and to remove obstacles thereto. Accordingly, reasonable restrictions on a solar energy system are those restrictions that do not significantly increase the cost of the system or significantly decrease its efficiency or specified performance, or that allow for an alternative system of comparable cost, efficiency, and energy conservation benefits.
>
> **(c)(1)** A solar energy system shall meet applicable health and safety standards and requirements imposed by state and local permitting authorities, consistent with Section 65850.5 of the Government Code.
>
> **(c)(2)** Solar energy systems used for heating water in single family residences and solar collectors used for heating water in commercial or swimming pool applications shall be certified by an accredited listing agency as defined in the Plumbing and Mechanical Codes.
>
> **(c)(3)** A solar energy system for producing electricity shall also meet all applicable safety and performance standards established by the California Electrical Code, the Institute of Electrical and Electronics Engineers, and accredited testing laboratories such as Underwriters Laboratories and, where applicable, rules of the Public Utilities Commission regarding safety and reliability.
>
> **(d)** For the purposes of this section:
>
> **(d)(1)(A)** For solar domestic water heating systems or solar swimming pool heating systems that comply with state and federal law, “significantly” means an amount exceeding 10 percent of the cost of the system, but in no case more than one thousand dollars ($1,000), or decreasing the efficiency of the solar energy system by an amount exceeding 10 percent, as originally specified and proposed.
>
> **(d)(1)(B)** For photovoltaic systems that comply with state and federal law, “significantly” means an amount not to exceed one thousand dollars ($1,000) over the system cost as originally specified and proposed, or a decrease in system efficiency of an amount exceeding 10 percent as originally specified and proposed.
>
> **(d)(2)** “Solar energy system” has the same meaning as defined in paragraphs (1) and (2) of subdivision (a) of Section 801.5.
>
> **(e)(1)** Whenever approval is required for the installation or use of a solar energy system, the application for approval shall be processed and approved by the appropriate approving entity in the same manner as an application for approval of an architectural modification to the property, and shall not be willfully avoided or delayed.
>
> **(e)(2)** For an approving entity that is an association, as defined in Section 4080 or 6528, and that is not a public entity, both of the following shall apply:
> **(A)** The approval or denial of an application shall be in writing.
> **(B)** If an application is not denied in writing within 45 days from the date of receipt of the application, the application shall be deemed approved, unless that delay is the result of a reasonable request for additional information.
>
> **(f)** Any entity, other than a public entity, that willfully violates this section shall be liable to the applicant or other party for actual damages occasioned thereby, and shall pay a civil penalty to the applicant or other party in an amount not to exceed one thousand dollars ($1,000).
>
> **(g)** In any action to enforce compliance with this section, the prevailing party shall be awarded reasonable attorney’s fees.
>
> (Subdivision (h), on public entities and grant programs, does not apply to an association and is not recited.)

**CIV 714.1, what an association may and may not do:**

> **(a)** Notwithstanding Section 714, an association may impose reasonable provisions that:
> **(1)** Restrict the installation of solar energy systems in common areas to those systems approved by the association.
> **(2)** Require the owner of a separate interest to obtain the approval of the association for the installation of a solar energy system in a separate interest owned by another.
> **(3)** Provide for the maintenance, repair, or replacement of roofs or other building components.
> **(4)** Require installers of solar energy systems to indemnify or reimburse the association or its members for loss or damage caused by the installation, maintenance, or use of the solar energy system.
>
> **(b)** An association shall not:
> **(1)** Establish a general policy prohibiting the installation or use of a rooftop solar energy system for household purposes on the roof of the building in which the owner resides, or a garage or carport adjacent to the building that has been assigned to the owner for exclusive use.
> **(2)** Require approval by a vote of members owning separate interests in the common interest development, including that specified by Section 4600, for installation of a solar energy system for household purposes on the roof of the building in which the owner resides, or a garage or carport adjacent to the building that has been assigned to the owner for exclusive use.
> An action by an association that contravenes paragraph (1) or (2) shall be void and unenforceable.

**CIV 4746, a roof shared by more than one homeowner:**

> **(a)** When reviewing a request to install a solar energy system on a multifamily common area roof shared by more than one homeowner pursuant to Sections 714 and 714.1, an association shall require both of the following:
> **(1)** An applicant to notify each owner of a unit in the building on which the installation will be located of the application to install a solar energy system.
> **(2)** The owner and each successive owner to maintain a homeowner liability coverage policy at all times and provide the association with the corresponding certificate of insurance within 14 days of approval of the application and annually thereafter.
>
> **(b)** When reviewing a request to install a solar energy system on a multifamily common area roof shared by more than one homeowner pursuant to Sections 714 and 714.1, an association may impose additional reasonable provisions that:
> **(1)(A)** Require the applicant to submit a solar site survey showing the placement of the solar energy system prepared by a licensed contractor or the contractor’s registered salesperson knowledgeable in the installation of solar energy systems to determine usable solar roof area. This survey or the costs to determine useable space shall not be deemed as part of the cost of the system as used in Section 714.
> **(1)(B)** The solar site survey shall also include a determination of an equitable allocation of the usable solar roof area among all owners sharing the same roof, garage, or carport.
> **(2)** Require the owner and each successive owner of the solar energy system to be responsible for all of the following:
> **(2)(A)** Costs for damage to the common area, exclusive use common area, or separate interests resulting from the installation, maintenance, repair, removal, or replacement of the solar energy system.
> **(2)(B)** Costs for the maintenance, repair, and replacement of solar energy system until it has been removed and for the restoration of the common area, exclusive use common area, or separate interests after removal.
> **(2)(C)** Disclosing to prospective buyers the existence of any solar energy system of the owner and the related responsibilities of the owner under this section.
>
> **(d)** This section imposes additional requirements for any proposed installation of a solar energy system on a multifamily common area roof shared by more than one homeowner.
>
> **(e)** This section does not diminish the authority of an association to impose reasonable provisions pursuant to Section 714.1.

**What the law requires of this form, and what it leaves open (the association's plain-words note, not the statute's):**

- **Review limits.** The association may impose only "reasonable restrictions": those "that do not significantly increase the cost of the system or significantly decrease its efficiency or specified performance, or that allow for an alternative system of comparable cost, efficiency, and energy conservation benefits" (714(b)); "significantly" has the dollar and percentage limits of 714(d)(1). For household rooftop systems on the roof of the building the owner lives in, or an assigned adjacent garage or carport, the association may not set a general policy prohibiting them and may not require a member vote (714.1(b)(1), (2)).
- **What the association may require.** Approval of systems in common areas (714.1(a)(1)); approval where the system is on another owner's separate interest (a)(2); provisions for maintenance, repair, or replacement of roofs (a)(3); installers' indemnity (a)(4); the health, safety, and certification standards of 714(c); and, on a shared multifamily roof, what 4746 says. Nothing else is listed; whether other provisions are reasonable is a reading (section 13).
- **Time.** Written approval or denial; deemed approved if not denied in writing within 45 days from the date of receipt of the application, unless the delay is the result of a reasonable request for additional information (714(e)(2)); and the application "shall not be willfully avoided or delayed" (714(e)(1)). The text says "date of receipt of the application", not "complete application".
- **On a shared multifamily roof**, the association **shall** require the applicant to notify each owner of a unit in the building, and the owner and each successive owner to keep a homeowner liability coverage policy and give the certificate within 14 days of approval and every year after (4746(a)). It **may** require a solar site survey with an equitable allocation of usable roof area, and the owner's responsibilities of (b)(2). The form carries the "shall" items as questions and the "may" items only where the profile has adopted them.
- **What the Act leaves silent:** when the notice to owners must be given; how many days a "reasonable request for additional information" adds; whether a fee may be charged; whether a homeowner liability policy may be required off a shared roof.

## 2. Who uses it, and when

- **Who.** An owner of a separate interest who wants to install or use a solar energy system (electricity, water heating, or swimming pool heating), or a person the owner authorizes; very often the installer submits, with the owner's signature (section 12).
- **Where it applies.** The roof of the building the owner lives in; an adjacent garage or carport assigned to the owner; the owner's own separate interest elsewhere; a common area; another owner's separate interest; and a roof shared by more than one homeowner (the 4746 section is shown only for that).
- **When.** Before the installation, where the documents require approval. An owner who is not sure approval is required may still send it.
- **Not this form.** A charging station ([ev-charger.md](ev-charger.md)); another change to the unit ([architectural-application.md](architectural-application.md)); a roof replacement alone ([protected-use-application.md](protected-use-application.md), 4720).

## 3. What the form must carry

| # | The form must carry | Authority | Carried by |
|---|---|---|---|
| S1 | The kind of system: electricity (photovoltaic), domestic water heating, swimming pool heating, other | 714(c)(2), (c)(3), (d)(1)(A), (d)(1)(B) (different standards and different "significantly" limits) | `system_kind` |
| S2 | Where it goes: the roof of the owner's building, an assigned adjacent garage or carport, elsewhere on the owner's separate interest, the common area, another owner's separate interest | 714.1(a)(1), (a)(2), (b)(1) | `where_installed` |
| S3 | Whether the roof is shared by more than one homeowner | 4746(a), (b) | `roof_shared` |
| S4 | The system described, so the standards can be applied | 714(b), (c) | `system_description`, `plans_attached`, `system_ownership` |
| S5 | The system's cost "as originally specified and proposed", so the limits of 714(d)(1) can be applied if the association proposes a change that adds cost | 714(d)(1)(A), (B); 4746(b)(1)(A) (the survey is not part of the cost) | `system_cost` |
| S6 | Permit and certification | 714(c)(1) to (c)(3) | `permit_status`, `permit_number`, `plans_attached` |
| S7 | **Shared roof: notice to each owner of a unit in the building** | 4746(a)(1) | `owners_notified`, `owners_notified_on`, `owners_notified_how`, `notice_copy_attached` |
| S8 | **Shared roof: the owner and each successive owner maintain a homeowner liability coverage policy and give the certificate within 14 days of approval and annually** | 4746(a)(2) | `agree_liability_policy` |
| S9 | Shared roof, where adopted: the solar site survey and the equitable allocation of usable roof area | 4746(b)(1)(A), (B) | `site_survey_attached` |
| S10 | Shared roof, where adopted: responsibility for damage, for maintenance and restoration, and disclosure to buyers | 4746(b)(2)(A), (B), (C) | `ack_damage_costs`, `ack_maintenance_costs`, `ack_disclose_buyers` |
| S11 | Where adopted: the installer's indemnity; the roof maintenance provision | 714.1(a)(4); 714.1(a)(3) | `agree_indemnity`, `ack_roof_maintenance` |
| S12 | **The 45 days and the exception** | 714(e)(2) | the panel (section 6) |
| S13 | The reasonable-restriction limits, and what the association may not do (no general prohibition, no member vote) | 714(b), (d)(1); 714.1(b) | the panel |
| S14 | Start and finish dates; signature; help | the documents; the standard | `start_date`, `finish_date`, signature, `help_needed` |

## 4. The questions

One question, one value. A question marked "when adopted" is on the copy only where the profile's documents or an adopted rule impose the provision; a provision the profile has not adopted is not asked ("never ask what the law or documents bar").

| key | Question (plain words) | kind | required | why (authority) | reads as | sets |
|---|---|---|---|---|---|---|
| `unit` | The address of your unit | short | yes | the separate interest | address | `ImprovementRequest.unit` |
| `owner_name` | Owner's name (each owner of record) | short | yes | the written decision (714(e)(2)(A)) | name | applicant |
| `submitted_by` | Who is sending this? The owner / a co-owner / someone the owner authorized in writing / the installer, with the owner's signature | choice | yes | proof of authority | option key | applicant role |
| `rep_authorization` | I am attaching the owner's written authorization | checkbox | when not the owner | acts for the owner | option key | authority on file |
| `contact_phone` | A phone number, if you want us to call | phone | no | convenience; never required | phone | contact (P2) |
| `decision_delivery` | How should we send the written decision? By mail to the unit / by mail to another address / by email | choice | yes | approval or denial is in writing (714(e)(2)(A)); an email is required only if you choose it (4041(b)(2)(A)) | option key | delivery route |
| `contact_email` | Your email address | email | only if `decision_delivery` is email | delivery by email | email | contact (P2) |
| `system_kind` | What kind of system? Electricity (photovoltaic) / water heating for the home / swimming pool heating / another kind / not sure | choice | yes | 714(c), (d)(1) | option key | the standards and limits that apply |
| `where_installed` | Where will it go? On the roof of the building I live in / on a garage or carport next to my building that is assigned to me / elsewhere on my own property (my yard, a patio) / in the common area / on another owner's property / not sure | choice | yes | 714.1(a)(1), (a)(2), (b)(1) | option key | placement |
| `roof_shared` | Is it on a roof that more than one homeowner shares? Yes / no / not sure | choice | yes | 4746(a): "a multifamily common area roof shared by more than one homeowner" | option key | whether the 4746 section applies |
| `system_description` | Describe the system (what it is, its size, and where on the roof or lot) | paragraph | yes | applies 714(b) and (c) | text | `description` |
| `system_ownership` | Who owns the system? I do / it is leased to me / I buy power from the owner of the system / not sure | choice | no | 4746(a)(2), (b)(2) speak of "the owner"; names who is responsible | option key | the responsible party |
| `plans_attached` | I am attaching: a layout showing placement / the equipment sheets and listings or certifications / the wiring diagram / roof attachment details (the list is the profile's checklist) | checkbox | no, and never a reason the 45 days do not run | 714(c); the profile's checklist | option keys | the checklist result (a lead) |
| `system_cost` | The cost of the system as you originally specified and proposed it (an estimate is fine) | short | no | so the limits of 714(d)(1) can be applied if the association proposes a change that adds cost; never used to approve or deny | text | the cost baseline |
| `permit_status` | The permit: have it / applied / will apply / none needed | choice | yes | 714(c)(1) | option key | permit state |
| `permit_number` | The permit number, if you have it | short | no | owner-supplied evidence | text | evidence |
| `installer_name` | The installer's name | short | no | 714.1(a)(4); 4746(b)(1)(A) | name | installer |
| `installer_license` | The installer's licence number | short | no | 4746(b)(1)(A) (a licensed contractor prepares a survey) | text | installer |
| `owners_notified` | I have notified the owner of each unit in the building of this application. | checkbox | yes when `roof_shared` is yes or not sure | 4746(a)(1) | option key | the 4746 notice evidence |
| `owners_notified_on` | On what date? | date | the same | 4746(a)(1); the evidence the association keeps (notice catalog `solar-building`) | date | notice date |
| `owners_notified_how` | How? Hand delivery / mail / email / posted at the building / other | choice | the same | the statute names no method; the evidence says which | option key | notice method |
| `notice_copy_attached` | I am attaching a copy of the notice and the list of units notified. | checkbox | no | evidence; the units' owners' names stay in the file (third parties') | option key | the evidence file |
| `agree_liability_policy` | I agree that I, and each later owner, will keep a homeowner liability coverage policy at all times and give the association the certificate of insurance within 14 days of approval and every year after. | checkbox | yes when `roof_shared` is yes or not sure | 4746(a)(2) | option key | the 14-day condition |
| `site_survey_attached` | I am attaching a solar site survey, prepared by a licensed contractor or the contractor's registered salesperson, showing the placement, with a fair allocation of usable roof area among the owners who share the roof. | checkbox | when adopted | 4746(b)(1)(A), (B) | option key | survey evidence |
| `ack_damage_costs` | I understand that I, and each later owner of the system, are responsible for costs for damage to the common area, an exclusive-use common area, or separate interests from its installation, maintenance, repair, removal, or replacement. | checkbox | when adopted | 4746(b)(2)(A) | option key | acknowledgment |
| `ack_maintenance_costs` | I understand that I, and each later owner, are responsible for the maintenance, repair, and replacement of the system until it is removed and for restoring the common area, exclusive-use common area, or separate interests after removal. | checkbox | when adopted | 4746(b)(2)(B) | option key | acknowledgment |
| `ack_disclose_buyers` | I understand that I must tell a buyer that there is a solar energy system and what the owner's responsibilities are. | checkbox | when adopted | 4746(b)(2)(C) | option key | acknowledgment (the owner's duty) |
| `agree_indemnity` | I agree that the installer will indemnify or reimburse the association or its members for loss or damage caused by the installation, maintenance, or use of the system. | checkbox | when adopted | 714.1(a)(4) | option key | indemnity condition |
| `ack_roof_maintenance` | I understand the association's provision for the maintenance, repair, or replacement of the roof ({ROOF_PROVISION}). | checkbox | when adopted | 714.1(a)(3) | option key | acknowledgment |
| `start_date` | When do you expect to start? | date | no | an approval's start time is a proposed policy (`improvement-lifetime`) | date | start |
| `finish_date` | When do you expect to finish? | date | no | the same | date | finish |
| `help_needed` | I need this form in another format, in larger print, in another language, or help filling it in | checkbox | no | the standard | option key | an accommodation lead |
| (signature) | Signature of owner, and the date | signature | yes | proof of who applied | text | signed on |

**Not asked:** neighbors' consent (the notice of 4746(a)(1) is notice, not consent); a member vote (barred for the household rooftop placements by 714.1(b)(2)); the owner's reasons for wanting solar; anything about the household's income or energy use; a coverage amount for the owner's liability policy (the statute names none); the owner's utility account.

The attestation: "I am the owner of this unit, or authorized by the owner to send this. What I have written is true to the best of my knowledge. Where I have checked a box above, I agree to it in writing."

## 5. The recitals

Opened by token, each with the subdivision and the line "as on jason's shelf of 2026-10-04" (statute targets are the proposed spelling of [../notices.md](../notices.md)):

1. `{QUOTE:CIV#714(e)(2)}` with (A), (B) (written; the 45 days; the exception)
2. `{QUOTE:CIV#714(b)}` (reasonable restrictions)
3. `{QUOTE:CIV#714(d)(1)}` with (A), (B) ("significantly")
4. `{QUOTE:CIV#714.1(a)}` with (1) to (4) (what the association may impose)
5. `{QUOTE:CIV#714.1(b)}` with (1), (2) (what it shall not do)
6. Where `roof_shared` is yes or not sure: `{QUOTE:CIV#4746(a)}` with (1), (2); and, where adopted, `{QUOTE:CIV#4746(b)}` with (1)(A), (1)(B), (2)(A), (2)(B), (2)(C)

## 6. What the member is told

> **We got it on {RECEIVED}.** We will tell you in writing that we have it within {ACK_DAYS} business days (a proposed target, not a law).
>
> **The 45 days.** The Civil Code says: "If an application is not denied in writing within 45 days from the date of receipt of the application, the application shall be deemed approved, unless that delay is the result of a reasonable request for additional information." We count from the day we **receive** your application, **{RECEIVED}**, so the forty-fifth day is **{DUE}**. The approval or the denial will be in writing.
>
> **If we need more information.** We will ask in writing, say what we need and why, and keep a copy. The law lets the delay that comes from a reasonable request count against the 45 days; it does not say how much. We aim to decide inside 45 days of the day we received your application either way.
>
> **Who decides.** {DECIDER} decides, in the same way it decides any request to change a unit: at a board meeting, on an agenda item. You do not need a vote of the members for a system on the roof of the building you live in, or on a garage or carport next to it that is assigned to you.
>
> **What we may and may not require.** We may impose only reasonable restrictions: those that do not significantly increase the cost of the system or significantly decrease its efficiency or specified performance, or that allow for an alternative system of comparable cost, efficiency, and energy conservation benefits. The law says how much is "significantly" (the dollar and percentage limits are on this form's recital). We may not set a general policy against rooftop solar for household purposes on your own building's roof or your assigned garage or carport. The system must meet the health and safety standards and the certifications the law lists, and you are responsible for the permit.
>
> **If your roof is shared with other homeowners.** The law says we "shall require" you to notify each owner of a unit in the building of your application, and to keep a homeowner liability coverage policy, and that you and each later owner give us the certificate within 14 days of approval and every year after. Please notify every owner in the building and tell us the date and how. Your notice is notice, not a request for permission; no neighbor's signature decides your application. {SURVEY_PANEL: where adopted, "Your documents also ask for a solar site survey from a licensed contractor, with a fair allocation of the usable roof among the owners who share it. The cost of the survey does not count as part of the cost of your system."}
>
> **If we deny it.** The denial is in writing and says why. You may ask the board to reconsider at an open meeting ([reconsideration form], or in your own words); the board answers within {MAX_DAYS_RECONSIDERATION} days of your request ({PROCEDURE_CITATION}).
>
> **Not the only door.** You do not have to use this form. A letter or an email that says what you want to install and where is an application, and the 45 days start the day we get it. An installer may send it for you if you sign or authorize it.
>
> **Help.** Ask {BOARD_CONTACT} for another format, larger print, another language, or help filling this in.

**What follows if the association does not act:** the application is **deemed approved** at the end of the forty-fifth day if it has not been denied in writing, unless the delay is the result of a reasonable request for additional information (714(e)(2)(B)). The handler records "deemed approved by statute on {DATE}", a person's entry, never an approval jason makes; the 14-day certificate (shared roof) is counted from the approval, which is the deemed day in that case (a reading).

## 7. The association's clocks

| Clock | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| Decision | the date of receipt of the application | 45 days | statute (714(e)(2)(B)) | deemed approved, unless the delay is the result of a reasonable request for additional information |
| A reasonable request for additional information | the day it is sent | no number in the statute; proposed: one written request, within 15 days of receipt, listing each item and why it is needed | PROPOSED POLICY (an addition to `improvement-review-time`) | the statute's exception may apply; a person records the request, the day, and the day it was answered; the handler still aims to decide inside 45 days of receipt (a reading) |
| Acknowledgment | the day received | proposed 3 business days | PROPOSED POLICY (`improvement-review-time`) | a finding for the manager |
| The applicant's notice to the owners in the building | not stated by 4746; proposed: with the application, with the evidence attached | not stated | the statute requires the notice (4746(a)(1)); PROPOSED POLICY for when (`improvement-neighbors`) | the application is not held up silently: the manager writes to ask for the evidence (a request for additional information), and the approval states the notice as a condition |
| The certificate of insurance | the day of approval | 14 days | statute (4746(a)(2)) | a finding for the manager; no remedy is stated, counsel reads it |
| The certificate, each year | the anniversary of the approval | yearly | statute (4746(a)(2)): "annually thereafter" | a finding for the manager; a recurring duty in `duty-schedule` |
| Reconsideration of a denial | as [reconsideration-request.md](reconsideration-request.md) | the documents' maximum; else proposed | documents; PROPOSED POLICY | as there |
| Meeting notice | the meeting | at least four days | statute (4920(a)) | an item not on the agenda cannot be acted on (4930(a)) |

The notice catalog already holds `solar-decision` (CIV 714, also CIV 4746; counted from `Anchor.APPLICATION_RECEIVED`, 45) and `solar-building` (CIV 4746, recipients the building's owners, the applicant's duty "which the association requires; the association keeps evidence it was given"). A `Term` row ("solar decision": `CIV` `714`, 45, with the words the section must carry) makes `tests/test_statutory_terms.py` fail the build if the statute changes ([../improvement-requests.md](../improvement-requests.md#the-clocks)). **Which meeting meets the clock:** the 45th day may fall between meetings; the handler computes the last scheduled open meeting that can be noticed in time and says so where none does; the choice is the board's.

## 8. The acknowledgment

> We received your application to install a solar energy system at {UNIT_ADDRESS} on **{RECEIVED}**. Your reference is **{REFERENCE}**.
>
> The Civil Code says an application not denied in writing within 45 days from the day it is received is deemed approved, unless the delay is the result of a reasonable request for additional information. We received it on {RECEIVED}, so the forty-fifth day is **{DUE}**. {DECIDER} decides it, at an open meeting of the board; the next meeting that can be noticed in time is {NEXT_MEETING}. We will tell you in writing.
>
> [Shared roof] Please send us the date and how you notified each owner of a unit in the building, and a copy of your notice. The law says the association shall require this notice.
>
> [If more information is needed] To decide, we need: {ITEMS_AND_WHY}. Please send it by {ASK_BY}. We are asking because {REASON}.
>
> If the board denies it, the letter will say why and how to ask the board to reconsider.
>
> This says only that we have your request and when. It is not an approval and not a denial.

## 9. Channels and the reference

- **Channels:** paper (filled by hand, scanned), the fillable PDF, an emailed copy (an installer often asks for one), the PayHOA form, the portal page. One `FormTemplate` renders each; the checkboxes are separate on every channel.
- **The marker code: `PV`** (photovoltaic). A blank form takes a **campaign** marker (`PV27M-xx`, `PV27P-xx`; `27` is the edition's year); a pre-filled emailed copy takes a copy marker (`PV27E-xxxxx-xx`).
- **Collision check.** Codes in `docs/form-templates/` on 2026-10-05: `AP`, `RC`, `EV`, `NC`, `MN`, `RR`, `RT`, `NA`, `RV`, `CN`, `MC`, `NV`; `NP` is the built owner-information form. `PV` is unused. It is made of letters of the alphabet `0-9 A C E F H K M N P R T V X`.
- **The marker is a hint.** A returned form is recognized by its printed lines and the cited authority `CIV 714`. A request in plain words ("I want to put solar panels on my roof") is still a request.

## 10. Profile slots

| Slot | What | Where |
|---|---|---|
| `{ASSOCIATION}`, `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}`, `{BOARD_CONTACT}`, `{FEE_SCHEDULE}` | standard; `{FEE_SCHEDULE}` is empty unless the documents set a fee and it may be charged here (section 13) | the profile |
| `{PROCEDURE_CITATION}`, `{MAX_DAYS_RECONSIDERATION}`, `{ACK_DAYS}` | as the architectural application | `Community.response_rules()` |
| `{SOLAR_STANDARDS_CITATION}` | the documents' section for solar installations | the profile |
| `{SOLAR_CHECKLIST}` | the items `plans_attached` offers | `Community.improvement_checklist("solar")` |
| `{SOLAR_SURVEY_REQUIRED}` | whether the profile has adopted the survey (4746(b)(1)) | the profile |
| `{SOLAR_ROOF_COSTS_ADOPTED}` | whether it has adopted the owner's responsibilities of 4746(b)(2) | the profile |
| `{INDEMNITY_ADOPTED}`, `{ROOF_PROVISION}` | whether it has adopted 714.1(a)(4) and (a)(3), and the provision's citation | the profile |
| `{BUILDINGS}` | which units share a roof (the building map), so the notice list can be offered | the profile |
| `{DECIDER}`, `{NEXT_MEETING}` | as the architectural application | the profile; `MeetingSchedule` |

**How this form relates to the owner's existing printed application.** A community's existing application (a printed form, a PayHOA request type, or a Doc) is the profile's input. The base form is built from its questions, fee, and checklist and adds what the law makes a solar form carry: the 45-day statement, the reasonable-restriction limits, the 4746 notice and liability coverage on a shared roof, and the statement that no member vote is needed. Where the existing form asks for something the law bars (a vote of the members, or a general prohibition recited as a rule), the generator lists it for a person to decide and does not carry it.

## 11. Handler and procedure

- **Handler.** `@handler("CIV 714", "CIV 714.1", "CIV 4746", role=Role.FORM_RETURN, form="solar", procedure="improvement-request", channels=(PAYHOA, GMAIL, MAIL, FORMS))`, with `accepts` (the form key; the cited authority; the words "solar", "photovoltaic", "panels"), `read` (an `ImprovementRequest` draft on the solar track, each checkbox as read), and `plan` (the 45th day, the 14-day condition, the 4746 notice evidence, none written). `ResponseKind.SOLAR` exists with a `ResponseRule` of `ClockSource.STATUTE`, `notice="solar-decision"`, `authority="CIV 714"`, and its `first_step` says "a complete application not denied in writing within 45 days is deemed approved".
- **Drift found while reading (for the author of that rule, not changed here):** the words "a complete application" are not in 714(e)(2)(B), which counts "from the date of receipt of the application" and excepts only "a reasonable request for additional information". The `first_step` should recite the statute's words ([ev-charger.md](ev-charger.md#11-handler-and-procedure) found the matching omission in the charger rule).
- **Procedure: `improvement-request`** (to be added, as set out in [architectural-application.md](architectural-application.md#11-handler-and-procedure)). The steps this track adds: (1) the clock is **45 days from receipt**; an incomplete application is listed for the owner and the clock keeps running; (2) a request for additional information is a person's record; jason never pauses the clock on its own guess, and the displayed due day carries both days; (3) at day 20 and day 40 the manager is told how many days remain and which meeting meets the clock; (4) on a shared roof, the manager checks that the applicant's notice to the building's owners is on file (`solar-building`) and lists it if not; (5) the decision is the board's vote, recorded by an officer; a denial letter carries the reasons and the reconsideration description (base template `architectural-decision`); (6) if the 45th day passes with no written denial, a person records "deemed approved by statute on {DATE}"; (7) the certificate (shared roof) is a condition at 14 days and a yearly duty in `duty-schedule`; (8) the owner's later duty to disclose the system to a buyer is the owner's summary's line, not the association's ([../improvement-requests.md](../improvement-requests.md#resale)).
- jason never approves, denies, or assigns the application; "deemed approved" is the statute's effect, and the record of it is a person's.

## 12. Edge cases

| Case | What the form and the handler do |
|---|---|
| **Co-owners** | One owner may submit for all unless the documents say otherwise; "the owner and each successive owner" under 4746(a)(2) means each owner of record is told. The decision goes to every owner of record. |
| **A representative** | Accepted with written authorization; the owner's checkbox agreements are the owner's. |
| **An installer submitting** | The common case. Received on the day it arrives; the owner's signature or authorization is asked for in writing; the 45 days run from receipt. The decision is addressed to the owner, copied to the installer the owner names. An installer's sales form that the owner has not seen is not the owner's agreement to 4746(a)(2). |
| **A tenant asking** | Not the member. The tenant is told how the owner applies. The form asks nothing about tenancy. |
| **A system owned by a third party** (a lease or a power-purchase agreement) | 714(a) speaks of the "installation or use of a solar energy system", whoever owns it; 4746's responsibilities speak of "the owner and each successive owner" of the owner and of the system. `system_ownership` names the responsible party; whether the association may require the third-party owner to sign anything is a reading for counsel. |
| **A shared roof where owners object** | The notice is notice. A neighbor's objection is not one of the grounds the statutes list; the board's decision must still be reasonable and not arbitrary (4765(a)(2), where the documents require approval). The owners' names and any comments stay in the request's file. |
| **A change the unit's insurer must see** | The form gives no coverage advice. The statute requires a homeowner liability coverage policy on a shared roof and states no amount. The owner may want to tell their own insurer of a roof installation; the association's insurance summary says "Association members should consult with their individual insurance broker or agent for appropriate additional coverage." (5300(b)(9), recited). |
| **A request that is really a variance** | A system the standards would otherwise bar is within 714(b): the question is whether the standard is a reasonable restriction. The association does not turn it into a variance request; the board decides the application, and a variance, where the documents have one, is a separate item. |
| **It arrives without the form** | A request. The manager enters it with its received day; the 45 days start; the form is sent as help. |
| **A roof that is also being replaced** | The roof work is its own change (4720 in [protected-use-application.md](protected-use-application.md), or the architectural application); the solar application is not held for it. |
| **A system that is not on the list of kinds** | `system_kind` "another kind" is read by a person against 714(d)(2), which points to a definition the shelf does not hold (CIV 801.5). |
| **Language and accessibility** | Another format, large print, translation, and help are on the form; a reasonable accommodation request is welcome with it. |
| **A director's own application** | The director is recorded as recused by the secretary; jason infers none. |

## 13. Leads for the board and counsel

Readings are labeled; conflicts are noted and never resolved.

1. **The 45 days and the exception.** As for the charger: the text counts "from the date of receipt of the application" and excepts a delay that "is the result of a reasonable request for additional information"; it states no deadline for the request, no number of days the exception adds, and no test of what is reasonable. *jason's reading:* decide inside 45 days of receipt; a specific, written, early request keeps the exception clean. The workflow page's "days paused are added to the due day" is the association's computed display, not the law; counsel reads how much time the exception buys. The rule for counting a period (CCP 12) is not on the shelf; the 45th day is computed as received day plus 45, with the written denial **delivered** by then.
2. **714(d)(1)(B), the words.** For photovoltaic systems, "significantly" is defined as "an amount not to exceed one thousand dollars ($1,000) over the system cost as originally specified and proposed, or a decrease in system efficiency of an amount exceeding 10 percent". Paragraph (A), for water and pool systems, says "an amount exceeding 10 percent of the cost of the system, but in no case more than one thousand dollars ($1,000)". Read literally, (B)'s "not to exceed" is the opposite of (A)'s "exceeding". *Two readings remain:* (i) the line is $1,000 over the cost: a restriction that adds more than $1,000 is a "significant" increase; (ii) the words say what they say. The form asks for the cost baseline and states neither reading as law; it recites (B) exactly. The board asks counsel before it relies on a dollar figure to deny or condition an application.
3. **What counts toward the cost.** 4746(b)(1)(A) says the survey, or the costs to determine usable space, "shall not be deemed as part of the cost of the system as used in Section 714". *jason's reading:* any other cost the association's requirement adds (an extra screening, a structural study, a roof reinforcement it requires) is counted in the 714(d)(1) test. Counsel reads it.
4. **What else the association may require.** 714.1(a) lists four reasonable provisions, and 4746(a), (b) lists the shared-roof ones. *jason's reading:* a requirement outside those lists (a minimum insurance amount, a recorded notice, a fee) is tested against 714(b)'s "reasonable restrictions" and is not on the statutory list; for a shared roof, 4746(e) says it "does not diminish the authority of an association to impose reasonable provisions pursuant to Section 714.1". The form asks only for what the statutes list, and for what the profile has adopted from the list. Counsel reads the rest.
5. **A homeowner liability policy off a shared roof.** 4746(a)(2) requires it on a multifamily common area roof shared by more than one homeowner. The statutes list no such requirement for an owner's own building roof, assigned garage or carport, or yard. A form that asks for it there goes beyond the list; the form does not ask for it there.
6. **Fee shifting runs both ways.** 714(g): "the prevailing party shall be awarded reasonable attorney’s fees." This differs from 4745(k) ("the prevailing plaintiff"). The association's own exposure under 714(f) is stated too: "willfully violates this section shall be liable to the applicant or other party for actual damages occasioned thereby, and shall pay a civil penalty ... not to exceed one thousand dollars ($1,000)". That is why the handler never lets the 45th day pass unseen.
7. **The notice to owners.** 4746(a)(1) says the association "shall require ... An applicant to notify each owner of a unit in the building". It does not say when, how, or what the association does with it. *Proposed policy `improvement-neighbors`, reused:* a notice is awareness and not consent; a neighbor's comment is advisory; names and signatures stay in the request's file. Whether the 45 days run while the notice is outstanding is a reading: *jason's reading* is that they run, since a request for the notice is not "a reasonable request for additional information" in the ordinary sense, and the course lawful under either reading is to decide in time and to condition the approval on the evidence. Counsel reads it.
8. **Allocation of usable roof area.** If the association adopts the survey, 4746(b)(1)(B) makes the survey determine "an equitable allocation of the usable solar roof area among all owners sharing the same roof, garage, or carport". Whose allocation binds a later owner who wants solar, and who resolves a dispute, is not stated. The board and counsel read it before the association adopts the survey.
9. **Successive owners.** 4746(a)(2) and (b)(2) speak of "each successive owner". Whether the association records anything to bind a successor, and how a buyer learns of it, is not stated; the owner's duty to tell buyers (4746(b)(2)(C)) is the owner's, and the owner's summary lists it. Counsel reads whether a recorded notice is a reasonable provision.
10. **Fee.** The Act does not mention a fee for a solar application. An architectural fee in the documents may or may not be a "reasonable restriction" under 714(b); the form carries a fee only where the documents set one and the profile says it may be charged; counsel reads it.
11. **Denial and reconsideration.** 714(e)(1) says the application is processed "in the same manner as an application for approval of an architectural modification", which *jason reads* to carry 4765's written-decision and reconsideration paragraphs where the documents require approval ([architectural-application.md](architectural-application.md#13-leads-for-the-board-and-counsel)). 714(e)(2)(A) independently requires the approval or denial in writing.
12. **No member vote.** 714.1(b)(2) bars requiring a vote for the household rooftop placements, and the section ends: "An action by an association that contravenes paragraph (1) or (2) shall be void and unenforceable." The sentence speaks of the association's action; whether it also voids a document provision that requires such a vote is a reading for counsel (714(a) separately voids a governing-document provision that "effectively prohibits or restricts the installation or use of a solar energy system"). *Noted, not resolved:* if a profile's documents carry such a requirement, `jason conflicts --leads` finds it and the board records a `Conflict` row with counsel.
13. **Statutes this page points at and the shelf does not hold:** CIV 801.5 (the definition of "solar energy system", 714(d)(2)); GOV 65850.5 (714(c)(1)); CIV 6552, 6528, 6532, 6564 (the corresponding definitions for commercial and industrial common interest developments); the Plumbing and Mechanical Codes, the California Electrical Code, and the Public Utilities Commission's rules (714(c)). They are pointers, not recitals.

## 14. Test fixtures

Made-up answers; the unit is "123 Main St"; the owner is "A. Owner".

**Typical** (photovoltaic, on the roof of the owner's own building, not shared): `unit` 123 Main St; `owner_name` A. Owner; `submitted_by` the owner; `decision_delivery` by mail to the unit; `system_kind` electricity (photovoltaic); `where_installed` on the roof of the building I live in; `roof_shared` no; `system_description` "Eight roof panels, about 3 kW, on the south slope, with an inverter in the garage."; `plans_attached` a layout showing placement; the equipment sheets and listings or certifications; `system_cost` $14,000; `permit_status` applied; `installer_name` Example Solar Inc.; `installer_license` 000000; signature A. Owner, 2026-10-12.

**Minimal** (an email, no form, from an installer): "On behalf of the owner of 123 Main St, we would like to install a roof solar system. Example Solar Inc." Expected: entered with the received day; the 45 days start; the acknowledgment states the forty-fifth day; the manager asks, in writing, for the owner's signature or authorization and the layout (a reasonable request for additional information, recorded); the checklist result lists them.

**Edge** (a shared multifamily roof, with a survey, and a third-party-owned system): `where_installed` on the roof of the building I live in; `roof_shared` yes; `system_ownership` it is leased to me; `owners_notified` checked, `owners_notified_on` 2026-10-02, `owners_notified_how` hand delivery; `notice_copy_attached` checked; `agree_liability_policy` checked; `site_survey_attached` checked (adopted in this profile); `ack_damage_costs`, `ack_maintenance_costs`, `ack_disclose_buyers` checked; `help_needed` checked (large print). Expected: the 4746 section is shown; the notice evidence is filed (`solar-building`); the 14-day certificate condition is set; the survey's allocation is listed for the board to read; the decision row `solar-decision` is shown with its 45th day and source word "statute".

**The statutory checklist test, in words.** For each profile, the generated form passes when:

1. It states that approval or denial will be in writing, that an application not denied in writing within 45 days from the date of receipt is deemed approved, and the exception for a reasonable request for additional information, each in the statute's words (714(e)(2)), and the forty-fifth day is computed from the received day.
2. It carries the reasonable-restriction standard of 714(b) and the "significantly" limits of 714(d)(1)(A) and (B) in the statute's words, and states that the association may not set a general policy against, or require a member vote for, the household rooftop placements (714.1(b)).
3. For a shared roof (`roof_shared` yes or not sure) it carries the notice to each owner of a unit in the building (4746(a)(1)) and the liability coverage and the 14-day and annual certificate (4746(a)(2)), each as its own question, and no coverage amount.
4. It carries the survey, the owner's responsibilities, the installer's indemnity, and the roof provision **only** where the profile has adopted them, each as its own question in the statute's words (4746(b); 714.1(a)(3), (a)(4)); a profile that has not adopted one never shows it.
5. It asks for no neighbor consent, no member vote, and no email address unless email is chosen.
6. It recites the tokens of section 5; each resolves against the shelf; a subdivision that has moved fails the build.
7. Every question has a `why`.
8. The marker `PV` round-trips; the scan test reads the paper form after a bad scan and does not confuse it with `EV`, `AP`, `RC`, `PX`, or `PR` (the disputed-charge form).
9. The generated form names its handler and procedure; one with no registered handler is refused.
