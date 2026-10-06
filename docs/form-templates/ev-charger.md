# Electric vehicle charging station and EV-dedicated meter application (`ev-charger`)

Status: design (2026-10-05). Form key `ev-charger`, marker code `EV` (proposed), authority `CIV 4745, 4745.1`. The standard it follows is [../form-templates.md](../form-templates.md). It is processed "in the same manner as an application for approval of an architectural modification" (4745(e), 4745.1(e)), so it runs on the same procedure (`improvement-request`) and the same workflow as [architectural-application.md](architectural-application.md) ([../improvement-requests.md](../improvement-requests.md), reused here and not changed), with the statute's own clock and checklist in place of the ordinary ones. A disapproval is reconsidered on [reconsideration-request.md](reconsideration-request.md).

Quotations are from the statutes on jason's authorities shelf (`data/authorities/CIV/CIV-4700-4753.md`), which are not official restatements. A reading is labeled as one and is never the rule.

## 1. Authority and what the law requires

**As-of.** The shelf's 2025 session publication of the Civil Code, exported 2026-10-04. CIV 4745 was amended by Stats. 2025, Ch. 525 (SB 770), operative 2026-01-01, and the text below is the text in force. The shelf's history keeps the 2019 to 2025 text (`data/authorities/history/CIV-4745/`); the one change in substance is in (f)(1)(C), and is a drift finding in section 13. CIV 4745.1 was added by Stats. 2018, Ch. 376, Sec. 2 and is unchanged. The form's recital line says "as on jason's shelf of 2026-10-04. jason's copy is not an official restatement."

**CIV 4745, the electric vehicle charging station** (subdivisions (a) to (k), quoted):

> **(a)** Any covenant, restriction, or condition contained in any deed, contract, security instrument, or other instrument affecting the transfer or sale of any interest in a common interest development, and any provision of a governing document, as defined in Section 4150, that either effectively prohibits or unreasonably restricts the installation or use of an electric vehicle charging station within an owner’s unit or in a designated parking space, including, but not limited to, a deeded parking space, a parking space in an owner’s exclusive use common area, or a parking space that is specifically designated for use by a particular owner, or is in conflict with this section is void and unenforceable.
>
> **(b)(1)** This section does not apply to provisions that impose reasonable restrictions on electric vehicle charging stations. However, it is the policy of the state to promote, encourage, and remove obstacles to the use of electric vehicle charging stations.
>
> **(b)(2)** For purposes of this section, “reasonable restrictions” are restrictions that do not significantly increase the cost of the station or significantly decrease its efficiency or specified performance.
>
> **(c)** An electric vehicle charging station shall meet applicable health and safety standards and requirements imposed by state and local authorities, and all other applicable zoning, land use, or other ordinances, or land use permits.
>
> **(d)** For purposes of this section, “electric vehicle charging station” means a station that is designed in compliance with the California Building Standards Code and delivers electricity from a source outside an electric vehicle into one or more electric vehicles. An electric vehicle charging station may include several charge points simultaneously connecting several electric vehicles to the station and any related equipment needed to facilitate charging plug-in electric vehicles.
>
> **(e)** If approval is required for the installation or use of an electric vehicle charging station, the application for approval shall be processed and approved by the association in the same manner as an application for approval of an architectural modification to the property, and shall not be willfully avoided or delayed. The approval or denial of an application shall be in writing. If an application is not denied in writing within 60 days from the date of receipt of the application, the application shall be deemed approved, unless that delay is the result of a reasonable request for additional information.
>
> **(f)** If the electric vehicle charging station is to be placed in a common area or an exclusive use common area, as designated in the common interest development’s declaration, the following provisions apply:
>
> **(f)(1)** The owner first shall obtain approval from the association to install the electric vehicle charging station and the association shall approve the installation if the owner agrees in writing to do all of the following:
> **(A)** Comply with the association’s architectural standards for the installation of the charging station.
> **(B)** Engage a licensed contractor to install the charging station.
> **(C)** Within 14 days of approval, provide a certificate of insurance as required by paragraph (3).
> **(D)** Pay for both the costs associated with the installation of and the electricity usage associated with the charging station.
>
> **(f)(2)** The owner and each successive owner of the charging station shall be responsible for all of the following:
> **(A)** Costs for damage to the charging station, common area, exclusive use common area, or separate interests resulting from the installation, maintenance, repair, removal, or replacement of the charging station.
> **(B)** Costs for the maintenance, repair, and replacement of the charging station until it has been removed and for the restoration of the common area after removal.
> **(C)** The cost of electricity associated with the charging station.
> **(D)** Disclosing to prospective buyers the existence of any charging station of the owner and the related responsibilities of the owner under this section.
>
> **(f)(3)** The owner of the charging station, whether located within a separate unit or within the common area or exclusive use common area, shall, at all times, maintain a liability coverage policy. The owner that submitted the application to install the charging station shall provide the association with the corresponding certificate of insurance within 14 days of approval of the application. That owner and each successor owner shall provide the association with the certificate of insurance annually thereafter.
>
> **(f)(4)** A homeowner shall not be required to maintain a homeowner liability coverage policy for an existing National Electrical Manufacturers Association standard alternating current power plug.
>
> **(g)** Except as provided in subdivision (h), installation of an electric vehicle charging station for the exclusive use of an owner in a common area, that is not an exclusive use common area, shall be authorized by the association only if installation in the owner’s designated parking space is impossible or unreasonably expensive. In such cases, the association shall enter into a license agreement with the owner for the use of the space in a common area, and the owner shall comply with all of the requirements in subdivision (f).
>
> **(h)** The association or owners may install an electric vehicle charging station in the common area for the use of all members of the association and, in that case, the association shall develop appropriate terms of use for the charging station.
>
> **(i)** An association may create a new parking space where one did not previously exist to facilitate the installation of an electric vehicle charging station.
>
> **(j)** An association that willfully violates this section shall be liable to the applicant or other party for actual damages, and shall pay a civil penalty to the applicant or other party in an amount not to exceed one thousand dollars ($1,000).
>
> **(k)** In any action by a homeowner requesting to have an electric vehicle charging station installed and seeking to enforce compliance with this section, the prevailing plaintiff shall be awarded reasonable attorney’s fees.

**CIV 4745.1, the EV-dedicated time-of-use meter** (the subdivisions the form uses):

> **(a)** Any covenant, restriction, or condition contained in any deed, contract, security instrument, or other instrument affecting the transfer or sale of any interest in a common interest development, and any provision of a governing document, as defined in Section 4150, that either effectively prohibits or unreasonably restricts the installation or use of an EV-dedicated TOU meter or is in conflict with this section is void and unenforceable.
>
> **(b)(1)** This section does not apply to provisions that impose reasonable restrictions on the installation of an EV-dedicated TOU meter. However, it is the policy of the state to promote, encourage, and remove obstacles to the effective installation of EV-dedicated TOU meters.
>
> **(b)(2)** For purposes of this section, “reasonable restrictions” are restrictions based upon space, aesthetics, structural integrity, and equal access to these services for all homeowners, but an association shall attempt to find a reasonable way to accommodate the installation request, unless the association would need to incur an expense.
>
> **(c)** An EV-dedicated TOU meter shall meet applicable health and safety standards and requirements imposed by state and local authorities, and all other applicable zoning, land use, or other ordinances, or land use permits.
>
> **(d)** For purposes of this section, an “EV-dedicated TOU meter” means an electric meter supplied and installed by an electric utility, that is separate from, and in addition to, any other electric meter and is devoted exclusively to the charging of electric vehicles, and that tracks the time of use (TOU) when charging occurs. An “EV-dedicated TOU meter” includes any wiring or conduit necessary to connect the electric meter to an electric vehicle charging station, as defined in Section 4745, regardless of whether it is supplied or installed by an electric utility.
>
> **(e)** If approval is required for the installation or use of an EV-dedicated TOU meter, the application for approval shall be processed and approved by the association in the same manner as an application for approval of an architectural modification to the property, and shall not be willfully avoided or delayed. The approval or denial of an application shall be in writing. If an application is not denied in writing within 60 days from the date of receipt of the application, the application shall be deemed approved, unless that delay is the result of a reasonable request for additional information.
>
> **(f)** If the EV-dedicated TOU meter is to be placed in a common area or an exclusive use common area, as designated in the common interest development’s declaration, the following provisions apply:
>
> **(f)(1)** The owner first shall obtain approval from the association to install the EV-dedicated TOU meter and the association shall approve the installation if the owner agrees in writing to do both of the following:
> **(A)** Comply with the association’s architectural standards for the installation of the EV-dedicated TOU meter.
> **(B)** Engage the relevant electric utility to install the EV-dedicated TOU meter and, if necessary, a licensed contractor to install wiring or conduit necessary to connect the electric meter to an EV charging station.
>
> **(f)(2)** The owner and each successive owner of an EV-dedicated TOU meter shall be responsible for all of the following:
> **(A)** Costs for damage to the EV-dedicated TOU meter, common area, exclusive use common area, or separate interests resulting from the installation, maintenance, repair, removal, or replacement of the EV-dedicated TOU meter.
> **(B)** Costs for the maintenance, repair, and replacement of the EV-dedicated TOU meter until it has been removed and for the restoration of the common area after removal.
> **(C)** Disclosing to prospective buyers the existence of any EV-dedicated TOU meter of the owner and the related responsibilities of the owner under this section.
>
> **(g)** The association or owners may install an EV-dedicated TOU meter in the common area for the use of all members of the association and, in that case, the association shall develop appropriate terms of use for the EV-dedicated TOU meter.
>
> **(h)** An association that willfully violates this section shall be liable to the applicant or other party for actual damages, and shall pay a civil penalty to the applicant or other party in an amount not to exceed one thousand dollars ($1,000).
>
> **(i)** In any action by a homeowner requesting to have an EV-dedicated TOU meter installed and seeking to enforce compliance with this section, the prevailing plaintiff shall be awarded reasonable attorney’s fees.

**What the law requires of this form, and what it leaves open (the association's plain-words note, not the statute's):**

- Approval, where required, is processed "in the same manner as an application for approval of an architectural modification", and "shall not be willfully avoided or delayed" (4745(e), 4745.1(e)).
- The approval or denial is **in writing**, and an application "not denied in writing within 60 days from the date of receipt of the application" is **deemed approved**, "unless that delay is the result of a reasonable request for additional information". The time runs from the date of **receipt of the application**; the text does not say "complete application".
- For a station in a common area or an exclusive-use common area, the owner first gets approval, and the association "shall approve the installation if the owner agrees in writing to do all of the following": the four agreements of 4745(f)(1)(A) to (D). For a meter there are two (4745.1(f)(1)(A), (B)). The form carries each agreement as its own box.
- The owner and each successive owner are responsible for the things in 4745(f)(2) and (f)(3) (and, for a meter, 4745.1(f)(2)). The form lists them for the owner to read and acknowledge; they are the statute's own, not extra conditions the association adds.
- A station in a common area that is not an exclusive-use area is authorized "only if installation in the owner’s designated parking space is impossible or unreasonably expensive", by license agreement (4745(g)).
- The association may impose only **reasonable restrictions**: for a station, those "that do not significantly increase the cost of the station or significantly decrease its efficiency or specified performance" (4745(b)(2)); for a meter, those "based upon space, aesthetics, structural integrity, and equal access", with the duty to "attempt to find a reasonable way to accommodate the installation request, unless the association would need to incur an expense" (4745.1(b)(2)).
- The statute states no deadline for the association to ask for additional information, and no number of days the "reasonable request" exception adds. Those are readings and proposed policy (sections 7 and 13).

## 2. Who uses it, and when

- **Who.** An owner of a separate interest who wants to install an electric vehicle charging station, or an EV-dedicated time-of-use meter, or both, where the governing documents require approval; or an authorized representative. Tenants and non-owners ask the owner (section 12).
- **Where it applies.** Within the owner's unit; in a deeded or otherwise designated parking space; in an exclusive-use common area; in a common area that is not exclusive use, if the owner's own space will not do (4745(g)); and for a station for all members (4745(h)). The checklist of agreements is required only where the statute attaches it: a common area or an exclusive-use common area (4745(f), 4745.1(f)).
- **When.** Before the work. An owner who is not sure approval is required may still send the form; the association answers whether approval is required, in writing.
- **Not this form.** A solar energy system ([solar.md](solar.md)); other changes to a unit ([architectural-application.md](architectural-application.md)); a request for a charging station for use by all members that the association itself would build (a board item, not an owner's application).

## 3. What the form must carry

| # | The form must carry | Authority | Carried by |
|---|---|---|---|
| E1 | What is to be installed: a station, a meter, or both | 4745(a); 4745.1(a) | `what_installing` |
| E2 | Where: in the unit, in a deeded or designated space, in an exclusive-use common area, in a common area that is not exclusive use, or a station for all members | 4745(a), (f), (g), (h) | `where_placed`, `space_description` |
| E3 | If a common area that is not exclusive use: why the owner's own space will not do | 4745(g) | `why_not_own_space`, `why_not_own_space_detail` |
| E4 | The station or meter described, so the architectural standards and the health and safety standards can be applied | 4745(c); 4745.1(c); the standards the owner agrees to under (f)(1)(A) | `station_description`, `plans_attached`, `power_source`, `utility_name` |
| E5 | **Agreement 1:** comply with the association's architectural standards for the installation | 4745(f)(1)(A) | `agree_standards` |
| E6 | **Agreement 2:** engage a licensed contractor | 4745(f)(1)(B) | `agree_licensed_contractor`; `contractor_name`, `contractor_license` (to follow) |
| E7 | **Agreement 3:** within 14 days of approval, provide a certificate of insurance as required by paragraph (3) | 4745(f)(1)(C), (f)(3) | `agree_certificate_14_days` |
| E8 | **Agreement 4:** pay for the installation and the electricity usage | 4745(f)(1)(D) | `agree_pay_costs` |
| E9 | The responsibilities of the owner and each successive owner: (A) damage costs; (B) maintenance, repair, replacement, and restoration after removal; (C) the cost of electricity; (D) disclosure to prospective buyers | 4745(f)(2)(A) to (D) | `ack_damage_costs`, `ack_maintenance_restoration`, `ack_electricity`, `ack_disclose_buyers` |
| E10 | The liability coverage policy, kept at all times; the certificate yearly; and that an existing standard plug needs no homeowner policy | 4745(f)(3), (f)(4) | the panel; `plug_only` |
| E11 | **Meter agreement 1:** comply with the association's architectural standards for the meter | 4745.1(f)(1)(A) | `meter_agree_standards` |
| E12 | **Meter agreement 2:** engage the relevant electric utility, and if necessary a licensed contractor for wiring or conduit | 4745.1(f)(1)(B) | `meter_agree_utility_contractor` |
| E13 | The meter owner's responsibilities: (A) damage costs; (B) maintenance and restoration; (C) disclosure to buyers | 4745.1(f)(2)(A) to (C) | `meter_ack_damage`, `meter_ack_maintenance`, `meter_ack_disclose` |
| E14 | The 60-day rule: decision in writing, deemed approved if not denied in writing, the exception for a reasonable request for information | 4745(e); 4745.1(e) | the panel (section 6) |
| E15 | The reasonable-restriction standard, so the owner sees what the association may and may not require | 4745(b); 4745.1(b) | the panel |
| E16 | The license agreement, where the space is in a common area that is not exclusive use | 4745(g) | the panel; `why_not_own_space` |
| E17 | Start and finish dates; signature and date; help | the documents; the standard | `start_date`, `finish_date`, signature, `help_needed` |

The agreements E5 to E8 (and E11, E12) are the statute's list "in writing": the signed form is the owner's written agreement, as is any email in which the owner agrees to each by name. A box the owner leaves unchecked on a placement the statute covers is a question to the owner, not a denial: the statute says the association "shall approve ... if the owner agrees in writing".

**Not asked (the law or the documents do not need it):** the vehicle, or whether the owner has one; the cost of the station; that the association be named an additional insured, or a policy limit (the 2026 text of (f)(1)(C) lists neither: section 13); a neighbor's consent or acknowledgment; the owner's reasons for wanting a charger.

## 4. The questions

One question, one value. "Shown when" lists where a question is on the copy.

| key | Question (plain words) | kind | required | why (authority) | reads as | sets |
|---|---|---|---|---|---|---|
| `unit` | The address of your unit | short | yes | the separate interest (4745(a)); places the return | address | `ImprovementRequest.unit` |
| `owner_name` | Owner's name (each owner of record) | short | yes | the written decision (4745(e)) | name | applicant |
| `submitted_by` | Who is sending this? The owner / a co-owner / someone the owner authorized in writing / a contractor, with the owner's signature | choice | yes | proof of authority | option key | applicant role |
| `rep_authorization` | I am attaching the owner's written authorization | checkbox | when not the owner | a representative acts for the owner | option key | authority on file |
| `contact_phone` | A phone number, if you want us to call | phone | no | convenience; never required | phone | contact (P2) |
| `decision_delivery` | How should we send the written decision? By mail to the unit / by mail to another address / by email | choice | yes | the approval or denial is in writing (4745(e)); an email is required only if you choose it (4041(b)(2)(A)) | option key | delivery route |
| `contact_email` | Your email address | email | only if `decision_delivery` is email | delivery by email | email | contact (P2) |
| `what_installing` | What do you want to install? A charging station / an EV-dedicated time-of-use meter / both / not sure | choice | yes | 4745(a); 4745.1(a); sets which agreements and which notice row (`ev-charger-decision`, `ev-meter-decision`) apply | option key | track (charger, meter, or both) |
| `where_placed` | Where will it go? Inside my unit / in my deeded parking space / in a parking space designated for my use / in my exclusive-use common area / in a common area that is not exclusive use / a station for all members / not sure | choice | yes | 4745(a), (f), (g), (h) | option key | placement; whether the agreements are required |
| `space_description` | Which space, or which part of the unit? (a space number or a short description) | short | when `where_placed` names a space or an area | identifies the location | text | location |
| `why_not_own_space` | Installing at your own parking space is: impossible / unreasonably expensive / neither / not sure | choice | when `where_placed` is a common area that is not exclusive use | 4745(g): authorized "only if installation in the owner’s designated parking space is impossible or unreasonably expensive" | option key | the (g) finding input |
| `why_not_own_space_detail` | Please tell us why (a quote or a note is welcome, never required) | paragraph | no | helps the board; the statute states no proof | text | the brief's facts |
| `station_description` | Describe what you will install (make and model, how many charge points, the wiring route) | paragraph | yes for a station | 4745(c), (d); applies the association's standards (agreement E5) | text | `description` |
| `plans_attached` | I am attaching: a sketch of where it goes / the product sheet / the wiring or conduit route (the list is the profile's checklist) | checkbox | no, and never a reason the 60 days do not run | the profile's checklist; applying (c) | option keys | the checklist result (a lead) |
| `power_source` | Where will the electricity come from? My unit's panel / my own meter / a common-area meter / a new EV-dedicated meter / not sure | choice | no | agreement E8 and E9(C) (who pays for the electricity) | option key | cost allocation |
| `utility_name` | Which electric utility will install the meter? | short | for a meter | 4745.1(f)(1)(B) | text | the utility |
| `contractor_name` | The licensed contractor's name, if you know it now | short | no (due before work starts, as a condition of the approval) | 4745(f)(1)(B) | name | contractor |
| `contractor_license` | The contractor's licence number, if you know it now | short | no (the same) | 4745(f)(1)(B) | text | contractor |
| `agree_standards` | I agree to comply with the association's architectural standards for the installation of the charging station. | checkbox | yes where the placement is a common area or exclusive-use common area | 4745(f)(1)(A) | option key | agreement 1 |
| `agree_licensed_contractor` | I agree to engage a licensed contractor to install the charging station. | checkbox | the same | 4745(f)(1)(B) | option key | agreement 2 |
| `agree_certificate_14_days` | I agree that, within 14 days of approval, I will give the association a certificate of insurance as required by 4745(f)(3). | checkbox | the same | 4745(f)(1)(C), (f)(3) | option key | agreement 3; sets the 14-day condition |
| `agree_pay_costs` | I agree to pay for both the costs associated with the installation of, and the electricity usage associated with, the charging station. | checkbox | the same | 4745(f)(1)(D) | option key | agreement 4 |
| `plug_only` | This is only an existing standard (NEMA) alternating-current power plug. Yes / no | choice | no | 4745(f)(4): no homeowner liability policy is required for it | option key | insurance condition off |
| `ack_damage_costs` | I understand that I, and each later owner of the station, are responsible for costs for damage to the station, the common area, an exclusive-use common area, or separate interests from its installation, maintenance, repair, removal, or replacement. | checkbox | no | 4745(f)(2)(A); the statute's own responsibility, not an extra condition | option key | acknowledgment |
| `ack_maintenance_restoration` | I understand that I, and each later owner, are responsible for the maintenance, repair, and replacement of the station until it is removed and for restoring the common area afterwards. | checkbox | no | 4745(f)(2)(B) | option key | acknowledgment |
| `ack_electricity` | I understand that I, and each later owner, are responsible for the cost of the electricity. | checkbox | no | 4745(f)(2)(C) | option key | acknowledgment |
| `ack_disclose_buyers` | I understand that I must tell a buyer that there is a charging station and what the owner's responsibilities under this section are. | checkbox | no | 4745(f)(2)(D) | option key | acknowledgment (the owner's duty, not the association's) |
| `meter_agree_standards` | I agree to comply with the association's architectural standards for the installation of the meter. | checkbox | yes for a meter in a common area or exclusive-use common area | 4745.1(f)(1)(A) | option key | meter agreement 1 |
| `meter_agree_utility_contractor` | I agree to engage the relevant electric utility to install the meter and, if necessary, a licensed contractor to install wiring or conduit to connect it to a charging station. | checkbox | the same | 4745.1(f)(1)(B) | option key | meter agreement 2 |
| `meter_ack_damage` | I understand that I, and each later owner of the meter, are responsible for costs for damage to the meter, the common area, an exclusive-use common area, or separate interests. | checkbox | no | 4745.1(f)(2)(A) | option key | acknowledgment |
| `meter_ack_maintenance` | I understand that I, and each later owner, are responsible for the maintenance, repair, and replacement of the meter until it is removed and for restoring the common area afterwards. | checkbox | no | 4745.1(f)(2)(B) | option key | acknowledgment |
| `meter_ack_disclose` | I understand that I must tell a buyer that there is an EV-dedicated meter and what the owner's responsibilities are. | checkbox | no | 4745.1(f)(2)(C) | option key | acknowledgment |
| `start_date` | When do you expect to start? | date | no | an approval's start time is a proposed policy (`improvement-lifetime`) | date | start |
| `finish_date` | When do you expect to finish? | date | no | the same | date | finish |
| `help_needed` | I need this form in another format, in larger print, in another language, or help filling it in | checkbox | no | the standard | option key | an accommodation lead |
| (signature) | Signature of owner, and the date | signature | yes | the owner's written agreement (4745(f)(1)) | text | signed on |

The agreement boxes are shown and required only for the placements the statute attaches them to; for a placement inside the unit, in a deeded space, or in a designated space that is the owner's separate interest, they are shown as information ("These apply if the station is in a common area or exclusive-use common area") and not required (the reading in section 13 on 4745(f)(3)). The attestation: "I am the owner of this unit, or authorized by the owner to send this. What I have written is true to the best of my knowledge. Where I have checked a box above, I agree to it in writing."

## 5. The recitals

Opened by token, each with the subdivision and the line "as on jason's shelf of 2026-10-04" (statute targets are the proposed spelling of [../notices.md](../notices.md)):

1. `{QUOTE:CIV#4745(e)}` (the 60 days and the exception)
2. `{QUOTE:CIV#4745(f)(1)}` (the owner agrees in writing to the four)
3. `{QUOTE:CIV#4745(f)(1)(A)}`, `{QUOTE:CIV#4745(f)(1)(B)}`, `{QUOTE:CIV#4745(f)(1)(C)}`, `{QUOTE:CIV#4745(f)(1)(D)}`
4. `{QUOTE:CIV#4745(f)(2)}` with (A) to (D); `{QUOTE:CIV#4745(f)(3)}`; `{QUOTE:CIV#4745(f)(4)}`
5. `{QUOTE:CIV#4745(b)(2)}` (reasonable restrictions)
6. Where the placement is a common area that is not exclusive use: `{QUOTE:CIV#4745(g)}`
7. For a meter: `{QUOTE:CIV#4745.1(e)}`, `{QUOTE:CIV#4745.1(f)(1)}` with (A), (B), `{QUOTE:CIV#4745.1(f)(2)}`, `{QUOTE:CIV#4745.1(b)(2)}`

The paragraph tokens are listed so nothing depends on whether a subdivision token renders its paragraphs.

## 6. What the member is told

> **We got it on {RECEIVED}.** We will tell you in writing that we have it within {ACK_DAYS} business days (a proposed target, not a law).
>
> **The sixty days.** The Civil Code says: "If an application is not denied in writing within 60 days from the date of receipt of the application, the application shall be deemed approved, unless that delay is the result of a reasonable request for additional information." We count from the day we **receive** your application, **{RECEIVED}**, so the sixtieth day is **{DUE}**. The approval or the denial will be in writing.
>
> **If we need more information.** If we ask you for more information, we will do it in writing, say exactly what we need and why, and keep a copy. The law lets the delay that comes from a reasonable request count against the 60 days; it does not say how much. We aim to decide inside 60 days of the day we received your application either way.
>
> **Who decides.** {DECIDER} decides, in the same way it decides any request to change a unit: at a board meeting, on an agenda item. The next meeting that can be noticed in time is {NEXT_MEETING}.
>
> **What the law says we must approve.** If your station is to go in a common area or an exclusive-use common area, the association "shall approve the installation if the owner agrees in writing to do all of the following": the four things listed on this form, each with its own box. If you check them all and sign, you have given the written agreement the statute asks for. You may agree in other words, too.
>
> **What the law says you are responsible for.** You, and each later owner of the station, are responsible for the costs and the duties listed on this form (4745(f)(2)), and you must keep a liability coverage policy at all times and give us the certificate within 14 days of approval and every year after (4745(f)(3)). A buyer must be told that the station is there. These are the law's, not ours.
>
> **What we may and may not require.** We may impose "reasonable restrictions": restrictions "that do not significantly increase the cost of the station or significantly decrease its efficiency or specified performance". The station must meet the health and safety standards and the permits the law requires (4745(c)); you are responsible for the permit.
>
> **If your station goes in a common area that is not your exclusive-use area.** The law lets us authorize that "only if installation in the owner’s designated parking space is impossible or unreasonably expensive", and then we sign a license agreement with you for the space. Tell us on the form why your own space will not do.
>
> **If we deny it.** The denial is in writing and says why. You may ask the board to reconsider at an open meeting ([reconsideration form], or in your own words); the board answers within {MAX_DAYS_RECONSIDERATION} days of your request ({PROCEDURE_CITATION}). A denial does not end your rights under the section.
>
> **Not the only door.** You do not have to use this form. A letter or an email that says what you want to install, where, and that you agree to the four things is an application, and the 60 days start the day we get it.
>
> **Help.** Ask {BOARD_CONTACT} for another format, larger print, another language, or help filling this in.

**What follows if the association does not act:** the application is **deemed approved** at the end of the sixtieth day if it has not been denied in writing, unless the delay is the result of a reasonable request for additional information (4745(e)). The handler records "deemed approved by statute on {DATE}", a person's entry, never an approval jason makes. The owner's 14 days to give the certificate are counted from the approval, which is the deemed day in that case (a reading, section 13).

## 7. The association's clocks

| Clock | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| Decision: station | the date of receipt of the application | 60 days | statute (4745(e)) | deemed approved, unless the delay is the result of a reasonable request for additional information |
| Decision: meter | the date of receipt of the application | 60 days | statute (4745.1(e)) | the same |
| A reasonable request for additional information | the day it is sent | no number in the statute; proposed: one written request, within 15 days of receipt, listing each item and why it is needed | PROPOSED POLICY (an addition to `improvement-review-time`) | the statute's exception may apply; a person records the request, who sent it, the day, and the day it was answered; the handler still aims to decide inside 60 days of receipt (a reading) |
| Acknowledgment | the day received | proposed 3 business days | PROPOSED POLICY (`improvement-review-time`) | a finding for the manager |
| The certificate of insurance | the day of approval | 14 days | statute (4745(f)(1)(C), (f)(3)) | a finding for the manager; the statute states no remedy, counsel reads it |
| The certificate, each year | the anniversary of the approval | yearly | statute (4745(f)(3)): "annually thereafter" | a finding for the manager; the year is a recurring duty in `duty-schedule` |
| The license agreement, for a common area that is not exclusive use | the approval | proposed 30 calendar days to sign | PROPOSED POLICY | the approval's conditions are not met; the work does not start |
| Contractor name and licence | before work starts | a condition of the approval | the decision's own words | a finding for the manager |
| Reconsideration of a denial | as [reconsideration-request.md](reconsideration-request.md) | the documents' maximum; else proposed | documents; PROPOSED POLICY | as there |
| Meeting notice | the meeting | at least four days | statute (4920(a)) | an item not on the agenda cannot be acted on (4930(a)) |

The notice catalog already holds the two statute rows: `ev-charger-decision` (CIV 4745; counted from `Anchor.APPLICATION_RECEIVED`, 60) and `ev-meter-decision` (CIV 4745.1, 60). A `Term` row for each ("charger decision", "meter decision"; the section, the value, the words the section carries) makes `tests/test_statutory_terms.py` fail the build if the statute changes ([../improvement-requests.md](../improvement-requests.md#the-clocks)). **Which meeting meets the clock:** the 60th day may fall between meetings; the handler computes the last scheduled open meeting that can be noticed in time (`MeetingSchedule`, `Community.board_notice_period()`), and where none falls in time it says so, and the choice (a special meeting, or a request for more information) is the board's.

## 8. The acknowledgment

> We received your application to install {WHAT_INSTALLING} at {UNIT_ADDRESS} on **{RECEIVED}**. Your reference is **{REFERENCE}**.
>
> The Civil Code says an application not denied in writing within 60 days from the day it is received is deemed approved, unless the delay is the result of a reasonable request for additional information. We received it on {RECEIVED}, so the sixtieth day is **{DUE}**. {DECIDER} decides it, at an open meeting of the board; the next meeting that can be noticed in time is {NEXT_MEETING}. We will tell you in writing.
>
> [If more information is needed] To decide, we need: {ITEMS_AND_WHY}. Please send it by {ASK_BY}. We are asking because {REASON}.
>
> If the board denies it, the letter will say why and how to ask the board to reconsider.
>
> This says only that we have your request and when. It is not an approval and not a denial.

## 9. Channels and the reference

- **Channels:** paper (filled by hand, scanned), the fillable PDF, an emailed copy, the PayHOA form (a request type the profile may already have), the portal page. One `FormTemplate` renders each, with the agreements as separate boxes on every one.
- **The marker code: `EV`.** A blank form is the same for every owner: a **campaign** marker (`EV27M-xx` paper, `EV27P-xx` PayHOA; `27` is the edition's year). A pre-filled emailed copy takes a copy marker (`EV27E-xxxxx-xx`). The edition's year changes when the recited law changes; 4745 changed on 2026-01-01, so a copy printed before that is a prior edition and is still recognized and read against its own edition.
- **Collision check.** Codes in `docs/form-templates/` on 2026-10-05: `AP`, `RC`, `NC`, `MN`, `RR`, `RT`, `NA`; `NP` is the built owner-information form. `EV` is unused. It is made of letters of the alphabet `0-9 A C E F H K M N P R T V X`.
- **The marker is a hint.** A returned form is recognized by its printed lines and the cited authority `CIV 4745`. A request in plain words ("I want to put in a charger") is still a request.

## 10. Profile slots

| Slot | What | Where |
|---|---|---|
| `{ASSOCIATION}`, `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}`, `{BOARD_CONTACT}`, `{FEE_SCHEDULE}` | standard; `{FEE_SCHEDULE}` is empty unless the documents set a fee for architectural modifications and it may be charged here (section 13) | the profile |
| `{PROCEDURE_CITATION}`, `{MAX_DAYS_RECONSIDERATION}`, `{ACK_DAYS}` | as the architectural application | `Community.response_rules()` |
| `{EV_STANDARDS_CITATION}` | the association's architectural standards for a charging station (the standards the owner agrees to comply with); empty means "the architectural standards" generally | the profile |
| `{EV_CHECKLIST}` | the items `plans_attached` offers | `Community.improvement_checklist("ev-charger")` |
| `{PARKING_SPACES}` | which spaces are separate-interest, designated, exclusive-use common area, or common area | the profile (the declaration's designations) |
| `{LICENSE_AGREEMENT}` | the license agreement form for a common area that is not exclusive use (4745(g)) | the profile |
| `{DECIDER}`, `{NEXT_MEETING}` | as the architectural application | the profile; `MeetingSchedule` |

**How this form relates to the owner's existing printed application.** A community's existing application (a printed form, a request type in PayHOA, or a Doc) is the profile's input. The profile points at it for its fee, its checklist, and its standards for a charging station. The base form adds what the law makes the form carry that an ordinary application lacks: the 60-day statement, the four agreements each with a box, the responsibilities, the (g) question, and the meter's two agreements. Where the existing form asks for something the 2026 statute no longer lists (an additional-insured endorsement, an amount of coverage), the generator lists it for a person to decide and does not carry it as the statutory agreement.

## 11. Handler and procedure

- **Handler.** `@handler("CIV 4745", "CIV 4745.1", role=Role.FORM_RETURN, form="ev-charger", procedure="improvement-request", channels=(PAYHOA, GMAIL, MAIL, FORMS))`, with `accepts` (the form key; the cited authority; the words "charging station" or "EV meter"), `read` (an `ImprovementRequest` draft on the charger track, with each agreement box as read), and `plan` (the 60-day day, the 14-day condition, and the license agreement, none written). `ResponseKind.EV_CHARGER` exists with a `ResponseRule` of `ClockSource.STATUTE`, `notice="ev-charger-decision"`, `authority="CIV 4745"`; its `KindRule` words cover "charging station" and "EV charger", not "TOU meter". Proposed: add `ResponseKind.EV_METER` (or extend the words), with a rule on `ev-meter-decision` and `CIV 4745.1`.
- **Procedure: `improvement-request`** (to be added, as set out in [architectural-application.md](architectural-application.md#11-handler-and-procedure)). The steps this track adds: (1) the clock is **60 days from receipt**, not from "complete"; an incomplete application is listed for the owner and the clock keeps running; (2) a request for additional information is a person's record (what, why, who sent it, the day, the day answered); jason never pauses the clock on its own guess, and the displayed due day carries both days; (3) at day 30 and day 50 the manager is told how many days remain and which meeting meets the clock; (4) the decision is the board's vote, recorded by an officer; a denial letter carries the reasons and the reconsideration description (base template `architectural-decision`); (5) if the 60th day passes with no written denial, a person records "deemed approved by statute on {DATE}" and the 14-day certificate condition starts; (6) the certificate, 14 days after approval and each year after, is a condition and a recurring duty (`duty-schedule`); (7) the license agreement, for 4745(g), is a condition. Name the lessons on the steps they change.
- **Drift found while reading (for the procedure's author, not changed here):** the `ResponseRule` for the charger kind reads "an application not denied in writing within 60 days is deemed approved" and omits the statute's exception; the solar rule says "a complete application not denied ... within 45 days", and the statute does not say "complete" ([solar.md](solar.md)). The `first_step` texts should recite the exception and not add "complete".
- jason never approves, denies, or assigns the application; "deemed approved" is the statute's effect, and the record of it is a person's.

## 12. Edge cases

| Case | What the form and the handler do |
|---|---|
| **Co-owners** | One owner may submit for all unless the documents say otherwise; the agreement is "the owner’s", and each owner of record is told of the responsibilities of "each successive owner". The decision goes to every owner of record. |
| **A representative** | Accepted with written authorization. The written agreements are the owner's: a representative's check marks are the owner's only if the owner signed or authorized them. |
| **A tenant asking** | The statute speaks of the owner's unit and parking space and of "the owner". A tenant's request is answered with how the owner applies; whether a tenant who is a person with a disability asks for an accommodation is a separate request with its own form. The form asks nothing about tenancy. |
| **A contractor submitting for an owner** | Received. The owner's signature is the written agreement; the manager asks for it in writing (a reasonable request for additional information, recorded). The 60 days run from receipt either way. |
| **A change the unit's insurer must see** | The form gives no coverage advice. The statute requires the owner's liability coverage policy and the certificate; it does not name an amount or an additional insured. The panel does not either. |
| **A request that is really a variance** | A charger the standards would otherwise bar is within 4745(b): the question is whether the standard is a reasonable restriction. The association does not turn it into a variance request; the board decides the application, and a variance, where the documents have one, is a separate item. |
| **It arrives without the form** | A request. The manager enters it with its received day; the 60 days start; the form is sent as help; the four agreements are asked for in writing. |
| **Several chargers, or a shared station** | One application per owner's station. A station for all members (4745(h)) is a board item with terms of use, not an owner's application; an owner proposing one is told so, and the proposal is entered as a request to the board. |
| **A new parking space** | 4745(i): "An association may create a new parking space where one did not previously exist to facilitate the installation of an electric vehicle charging station." It is the board's choice; an owner may ask. |
| **An owner who sells** | Each successive owner is responsible for the station's costs, and a seller discloses it to a buyer (4745(f)(2)(D)); the owner's own summary lists it. The association adds nothing to the 4525 package for it ([../improvement-requests.md](../improvement-requests.md#resale)). |
| **Language and accessibility** | Another format, large print, translation, and help are on the form; a reasonable accommodation request is welcome with it. |
| **A director's own application** | The director is recorded as recused by the secretary; jason infers none. |

## 13. Leads for the board and counsel

Readings are labeled; conflicts are noted and never resolved.

1. **A change in the text in 2026 (drift).** *Fact:* until 2026-01-01, 4745(f)(1)(C) read: "Within 14 days of approval, provide a certificate of insurance that names the association as an additional insured under the owner’s insurance policy in the amount set forth in paragraph (3)." (the shelf's 2019 to 2025 edition). Since SB 770 it reads: "Within 14 days of approval, provide a certificate of insurance as required by paragraph (3)." The additional-insured and amount words are gone, and paragraph (3) states no amount. *jason's reading:* the statutory agreement is the certificate "as required by paragraph (3)", which is a liability coverage policy kept at all times with an annual certificate. A form, a letter, or a profile that still asks for an additional-insured endorsement or a coverage amount as the statutory agreement is built on the old text. Whether the association may ask for either as a reasonable restriction under 4745(b) (a restriction that does not "significantly increase the cost of the station or significantly decrease its efficiency or specified performance") is a second reading for counsel; until then the form does not ask for them, and a profile that does is told which words changed.
2. **Does (f) reach a placement inside the unit?** 4745(f) begins "If the electric vehicle charging station is to be placed in a common area or an exclusive use common area ... the following provisions apply", while (f)(3) says "whether located within a separate unit or within the common area or exclusive use common area". Two readings: (f) as a whole applies only to the common-area placements; or (f)(3)'s own words extend the liability policy to a unit placement. *Course lawful under either:* the form shows the agreements as information, not as a requirement, for an in-unit placement, and the owner is not refused for leaving them unchecked; counsel reads it.
3. **The 60 days and the exception.** The text counts "from the date of receipt of the application" and excepts a delay "the result of a reasonable request for additional information". It does not say when the request must be made, how many days it adds, or what makes it reasonable. *jason's reading:* the course that is lawful under any reading is to decide inside 60 days of receipt; a request for more information that is specific, written, and made early keeps the exception clean. The workflow page's "days paused are added to the due day" ([../improvement-requests.md](../improvement-requests.md#the-clocks)) is the association's computed display, not the law; counsel reads how much time the exception buys. The shelf does not hold the rule for counting a period (CCP 12 is not on the shelf), so the sixtieth day is computed as received day plus 60, with the written denial **delivered** by then.
4. **When is "approval"?** The 14-day certificate runs "from approval" (4745(f)(1)(C), (f)(3)). If the application is deemed approved on the 61st day, is that the date? *jason's reading:* yes, the deemed day; a person records it. Counsel reads it.
5. **A fee.** The Act does not mention a fee for a charging station application. An architectural fee in the documents may or may not be a "reasonable restriction" within 4745(b)(2) (it "significantly increase[s] the cost of the station" is a question of degree). The form carries a fee only where the documents set one and the profile says it may be charged; counsel reads it. Cost to the owner of the association's own review (an engineer, for example) is the same question.
6. **Denial and reconsideration.** 4745(e) says the application is processed "in the same manner as an application for approval of an architectural modification", which *jason reads* to carry 4765's written-decision and reconsideration paragraphs where the documents require approval ([architectural-application.md](architectural-application.md#13-leads-for-the-board-and-counsel)). The exposure is stated in the statute: "An association that willfully violates this section shall be liable to the applicant or other party for actual damages, and shall pay a civil penalty ... not to exceed one thousand dollars ($1,000)" (4745(j)), and the prevailing plaintiff "shall be awarded reasonable attorney’s fees" (4745(k)). The same words are in 4745.1(h) and (i). That is why the handler never lets the 60th day pass unseen.
7. **The meter.** 4745.1(b)(2) bars restrictions beyond space, aesthetics, structural integrity, and equal access, and asks the association to "attempt to find a reasonable way to accommodate the installation request, unless the association would need to incur an expense". Whether an association must incur no expense at all is the text; the form asks nothing about it.
8. **License agreement, (g).** The statute says the association "shall enter into a license agreement with the owner". The terms are the board's and counsel's; this page does not draft them. Whether an association may charge a fee for the license is for counsel.
9. **A station for all members, (h).** "The association shall develop appropriate terms of use" is a rule on subject 4355(a)(1) (use of the common area), and a rule on it needs general notice at least 28 days before the board makes it (4360(a)).
10. **Conflict notes.** Where a document requires something the statute lists as no longer required (the additional insured), the document and the statute may conflict "to the extent of" it (4205(a)): *noted, not resolved.* `jason conflicts --leads` lists the change in the Act since the document was written.
11. **Statutes this page points at and the shelf does not hold:** the California Building Standards Code (4745(d)), the zoning and land-use ordinances and permits of 4745(c), and the local agency's own rules. They are pointers, not recitals.

## 14. Test fixtures

Made-up answers; the unit is "123 Main St"; the owner is "A. Owner".

**Typical** (a station in the owner's exclusive-use parking area): `unit` 123 Main St; `owner_name` A. Owner; `submitted_by` the owner; `decision_delivery` by mail to the unit; `what_installing` a charging station; `where_placed` in my exclusive-use common area; `space_description` carport space 7; `station_description` "One wall-mounted charger, one charge point, wired from the unit's panel by a licensed electrician."; `plans_attached` a sketch of where it goes; the product sheet; `power_source` my unit's panel; `agree_standards`, `agree_licensed_contractor`, `agree_certificate_14_days`, `agree_pay_costs` all checked; `ack_damage_costs`, `ack_maintenance_restoration`, `ack_electricity`, `ack_disclose_buyers` checked; `contractor_name` Example Electric Inc. (licence 000000 to follow); signature A. Owner, 2026-10-12.

**Minimal** (an email, no form): "I would like to install an EV charger in my garage at 123 Main St. I agree to follow your standards, use a licensed contractor, send the insurance certificate within 14 days of approval, and pay for the installation and the electricity. A. Owner." Expected: entered with the received day; all four agreements read as given in writing (the email is a written agreement); the 60 days start the day received; the acknowledgment draft states the sixtieth day.

**Edge** (a common area that is not exclusive use, with a request for more information): `where_placed` in a common area that is not exclusive use; `why_not_own_space` unreasonably expensive; `why_not_own_space_detail` "My assigned space is on the far side of the building; the conduit run is long."; `what_installing` both; `power_source` a new EV-dedicated meter; `utility_name` Example Power; `meter_agree_standards` and `meter_agree_utility_contractor` checked; the four station agreements checked; `plug_only` no; `help_needed` checked. Expected: the (g) recital is shown; the license agreement is a condition; the handler records a written request for the site plan on day 12 (a person's record, "waiting on the owner for a site plan, from day 12"); the sixtieth day is computed with both days kept ("60 days from receipt: day {DUE}; the request of day 12 may add days: a reading"); the meter's decision row `ev-meter-decision` is shown beside the station's.

**The statutory checklist test, in words.** For each profile, the generated form passes when:

1. It states that approval or denial will be in writing, that an application not denied in writing within 60 days from the date of receipt is deemed approved, and the exception for a reasonable request for additional information, each in the statute's words (4745(e), 4745.1(e)), and the sixtieth day is computed from the received day.
2. For the common-area and exclusive-use-common-area placements it carries the four agreements of 4745(f)(1)(A) to (D) as four separate boxes in the statute's words, and the two of 4745.1(f)(1)(A), (B) for a meter; none is merged with another; none adds a condition the statute does not list (no additional insured, no coverage amount, no neighbor consent).
3. It carries the responsibilities of 4745(f)(2)(A) to (D) and 4745.1(f)(2)(A) to (C) each as its own acknowledgment, and states the (f)(3) liability policy, the 14-day and annual certificate, and the (f)(4) plug exception.
4. It carries the (g) question and the license-agreement statement for the common area that is not exclusive use, and the (h) statement for a shared station.
5. It states the reasonable-restriction standard in the statute's words (4745(b)(2); 4745.1(b)(2)).
6. It recites the tokens of section 5; each resolves against the shelf; a subdivision that has moved fails the build; a change in the shelf's text of 4745 (as in 2026) is found by `jason law-history` and the form's edition is bumped.
7. It asks for no email address unless email is chosen, and nothing about the vehicle, the cost, or a neighbor.
8. The marker `EV` round-trips; the scan test reads the paper form after a bad scan and does not confuse it with `AP`, `RC`, or `PV`.
9. The generated form names its handler and procedure; one with no registered handler is refused.
