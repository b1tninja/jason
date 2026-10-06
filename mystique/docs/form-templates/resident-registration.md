# Resident and vehicle registration

Status: design (2026-10-05). Key `resident-registration`; proposed marker code `RH`. It follows the standard in [form-templates.md](../../../docs/form-templates.md). The inventory row is "Resident and vehicle registration" in [standard-forms.md](../standard-forms.md) (the worked example; today a Google Form, `RESIDENT_REGISTRATION`, used September 2024 to June 2026); the general family is [docs/standard-forms.md](../../../docs/standard-forms.md) (family two: the documents make the owner ask). No law governs this form, so its `authority` is the rule, not a statute, and its handler is a general one ([arrivals-design.md](../../../docs/arrivals-design.md)).

**Offering waits on the board.** Registering residents asks, in effect, who lives in a unit, and a lessee is a resident (B-1(b)); no owner is contacted about occupancy until the board takes up `rental-approvals-4-15`. jason takes the cautious reading: this form is designed now and **not sent** until the board decides, or says it may go on while the occupancy follow-ups are held (lead 2).

## 1. Authority and what the law requires

As of: the association’s documents as jason holds them (`data/governing/owners-manual-and-rules.md`, `ccrs.md`; `data/artifacts/site-docs/governing_documents/`), read 2026-10-05. The words below are recited from jason’s copy and labeled with where they are written. A document kept as amended is consolidated from the instruments’ own words; it is not an official restatement, and the recorded and adopted documents control. **No statute on the shelf requires this form**: the Act asks the owner’s delivery preferences and occupancy once a year on the owner-information form (CIV 4041), a separate act (lead 5).

**The instrument.** The Owner’s Manual and Rules, Part B, “B-1. Registration”, adopted April 18, 2023 (`owners-manual-2023`, per [manual.md](../manual.md)), with the fine schedule it adopted the same day (Part C, “a) Fine Schedule”). B-1’s opening sentence is unlettered; its bullets are lettered here (a) to (h) in order, as the profile’s inventory letters them.

**B-1, the rule** (opening sentence):

> All members and residents, and all vehicles regularly operated by residents or located within the property, must be registered with the manager.

**B-1(a), (b), and (c), who and what:**

> Association members are those individuals owning a condominium unit at the Mystique Community Association.
>
> Residents are defined as owners and members of their families living on the premises of the Community, or lessees and members of their families living on the premises of Mystique Community Association.
>
> The Association requires written evidence of current registration for each vehicle regularly operated by a resident, or parked within the Development.

**B-1(d), the annual form and its clock, and the fine:**

> The association shall distribute a RESIDENT REGISTRATION FORM annually, which must be completed within thirty (30) days of receipt. Should there be a change of occupancy, a revised/updated form should be submitted within thirty (30) days. The association shall impose a fine for failure of an owner to maintain updated registration.

**B-1(e), what the information may be used for:**

> The information provided may be used in emergency situations, pursuing legal remedies, and providing notice to the owners of towed or impounded vehicles, in addition to assisting in the identification of persons entitled to be on the property.

**B-1(f) and (g), owners who lease** (for context; they bear on who registers):

> Owners leasing their unit(s) retain their voting right in the Association but assign the use of all common facilities of the Community to the lessee of their units(s). The lessee assumes the privileges and responsibilities of membership as hereinafter stated, but does not have a voting right the vote belongs only to the owner. Non-resident owners are not permitted to use any common area facilities when so assigned to a lessee except as a guest of a resident.
>
> The lease or rental agreement must be in writing and must be for a term of 30 days or more and be subject to the CC&RS, Bylaws, and adopted rules.

**Owner’s Manual, Part C, a) Fine Schedule** (adopted April 18, 2023): “Failure to maintain registration | $1 per day”. The Enforcement Policy Document lists the same line.

**CC&Rs 4.11, Condition of Vehicles** (the vehicle registration the evidence concerns): “Each vehicle operated or located within the Development shall maintain, and the Board shall have the authority to require written evidence of, current registration which permits the vehicle to be legally operated on public streets.”

**The Owner’s Manual’s Part C, “b) Due Process Requirements”** (what must precede a fine; the registration fine is one): “Before the Board imposes any disciplinary action for alleged violations, including monetary penalties (fines) ..., the Board must act in good faith, be reasonable, not arbitrary or capricious, and satisfy each of the following requirements: ...” (the notice of a hearing at least ten days before, the hearing, and a written decision within fifteen days).

**What the documents do not say** (so the form does not say it either): the month the form is distributed; what “receipt” is; the day the $1 a day begins; who completes the form when the owner does not live in the unit; whether a lessee must register apart from the owner; how long the registration is kept; what happens to a registration when the unit is sold.

## 2. Who uses it, and when

- **An Owner** (a member) for each unit, who completes the form for everyone who lives in the unit and every vehicle regularly operated by a resident or parked on the property. The documents say the form “must be completed within thirty (30) days of receipt” and does not say by whom; the form goes to the owner (lead 4).
- **When:** once a year, when the association distributes it (B-1(d)); and again within thirty days of a change of occupancy.
- **Who it is not for:** a member asking to rent a unit ([rental-application.md](rental-application.md), held); a guest’s vehicle (a guest permit: [parking-permit.md](parking-permit.md)); an owner answering the annual owner-information request (CIV 4041: delivery, a second address, a representative, and occupancy). **This form does not ask those, and the owner-information form does not ask for residents or vehicles.**

## 3. What the form must carry

| # | What the document says the form carries | Words | Carried by |
|---|---|---|---|
| 1 | Every member and resident of the unit | B-1 | the resident block: `res-name`, `res-relationship` |
| 2 | Each vehicle regularly operated by a resident or parked within the property | B-1 | the vehicle block |
| 3 | Written evidence of current registration for each such vehicle | B-1(c) | `veh-evidence` |
| 4 | The annual form, and the thirty days from receipt | B-1(d) | fixed text with `{DUE_DATE}` |
| 5 | A revised form within thirty days of a change of occupancy | B-1(d) | `kind`, `change-date` |
| 6 | What the information may be used for | B-1(e) | fixed text “What we use this for” |
| 7 | The fine for failure to maintain updated registration, and that a fine is imposed only after notice and a hearing | B-1(d); Part C | fixed text, as information |
| 8 | Who is asking, and for which unit | B-1 | `owner-name`, `unit-address`, `capacity` |
| 9 | That a request in other words is still a request, and where to get help | [standard 5](../../../docs/form-templates.md) | fixed text |

## 4. The questions

Kinds: text, choice, checkbox, date, address, file. One question holds one value. The resident and the vehicle blocks repeat: the paper and PDF forms print rows; the PayHOA form’s builder has no repeating group, so it carries six resident rows and six vehicle rows and a “more” box (a template change, section 11).

**The unit**

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `owner-name` | Your name | text | yes | B-1(d): the owner completes it | NAME | request.requester |
| `unit-address` | Unit address | address | yes | places the registration | ADDRESS (prefilled `UNIT_ADDRESS`) | register: unit |
| `capacity` | You are | choice: “An owner of this unit”; “A resident answering for the owner” | yes | B-1(d); “by proxy” is the parking permit’s word and the form uses it only there | TEXT | request.capacity |
| `kind` | Which form is this? | choice: “The yearly form”; “A change of occupancy: a revised form” | yes | B-1(d) | TEXT | request.kind |
| `change-date` | The date the change of occupancy happened | date | yes if a revised form | B-1(d): “within thirty (30) days” of a change | TEXT | request.change_date |

**Each resident** (a row for each person who lives in the unit, the owner included)

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `res-name` | Name | text | yes, for each row used | B-1: “All members and residents” | NAME | register: resident name |
| `res-relationship` | How is this person connected to the unit? | choice: “Owner”; “Member of the owner’s family”; “Lessee”; “Member of a lessee’s family” | yes | B-1(b): the four kinds of resident | TEXT | register: resident kind |
| `res-contact` | A phone number or an email for this person (optional) | text | no | B-1(e): “may be used in emergency situations”; not required | TEXT (a phone or an email) | register: contact, kept restricted |

**Each vehicle** (a row for each vehicle regularly operated by a resident or parked on the property)

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `veh-plate` | License plate | text | yes, for each row used | B-1: “all vehicles”; B-1(e): notice of towed vehicles | TEXT | register: plate |
| `veh-state` | State | text (two letters) | yes | identifies the plate | TEXT | register: plate state |
| `veh-desc` | Make, model, and color | text | yes | identifies the vehicle | TEXT | register: vehicle |
| `veh-resident` | Which resident operates it? | text | no | B-1: “regularly operated by residents” | NAME | register: operator |
| `veh-evidence` | The vehicle’s current registration is attached (a photo or copy of the registration card) | checkbox (one box) and a file | yes, for each row used | B-1(c): “written evidence of current registration for each vehicle” | TEXT | register: evidence on file |
| `no-vehicles` | No resident operates a vehicle that is parked on the property | checkbox (one box) | no | so a blank is not read as “forgot” | TEXT | register: none |

**The return**

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `emergency` | Someone to call in an emergency, if you wish (name and phone) | text | no | B-1(e) names emergencies as a use; not required | TEXT | register: emergency contact, kept restricted |
| `attestation` | I am the owner of this unit, or I am authorized to answer for the owner, and what I have written is true | checkbox (one box) on PayHOA and PDF; the signature line on paper | yes | assurance ([forms.md](../../../docs/forms.md)) | TEXT | request.attested |
| (signature) | Signature of owner, and date | signature line, date | yes on paper and PDF; “signed in” online | the registration is the owner’s | NAME | request.signed |

**Not asked, on purpose:**
- **Anything that belongs to the owner-information form** (CIV 4041): delivery preference, a second address, a legal representative, or whether the unit is owner-occupied, rented, or vacant. The 2024 form asked them together with registration and so mixed an unverified registration with the owner’s annual written answer ([forms.md](../../../docs/forms.md), “Earlier answers”); this form does not.
- **Anything about a lease**: the lease, its term, the landlord’s terms, a background check, a credit report. B-1(h) and CC&Rs 4.15 are the rental path ([rental-application.md](rental-application.md)); the 2024 form’s uploads of leases and screening reports are not repeated, and jason never opens them.
- **Age, date of birth, a minor’s details beyond a name and the connection**, employer, income, a driver’s license number, an insurance policy, or a citizenship or immigration status.
- **A signature of a resident other than the owner.**

## 5. The recitals

The form opens with these, by token, with the document and section named, then the caveat of section 1. The documents are cited as `{QUOTE:owners-manual#B-1}` ([embedded-references.md](../../../docs/embedded-references.md)); the form’s record carries the instrument and date that set the words.

| Token | Section | Why it opens the form |
|---|---|---|
| `{QUOTE:owners-manual#B-1}` | the opening sentence and (a) to (e) | who and what must be registered; the annual form, the 30 days, the fine; what the information is used for |
| `{QUOTE:owners-manual#B-1(d)}` | (d) | the annual distribution, the 30 days, a change of occupancy, the fine |
| `{QUOTE:owners-manual#B-1(e)}` | (e) | the uses of the information |

A plain-words note may follow each, labeled “The association’s plain-words note; the words above control.”

## 6. What the member is told

The sentence the Owner reads (`member_clock`):

> The Association’s rules (B-1) say every member and resident, and every vehicle regularly used by a resident or kept on the property, must be registered with the manager. This is the yearly form; please complete it by {DUE_DATE}, which is thirty days from the day you received it. If someone moves in or out, send a new form within thirty days of the change. We use what you tell us in emergencies, to pursue legal remedies, to give notice of a towed or impounded vehicle, and to identify who is entitled to be on the property. The rules set a fine of $1 a day for failing to keep your registration up to date; a fine is imposed only after notice, a hearing, and a decision of the Board. You may ask for another format or for help filling this in. We will tell you in writing the day we received your form.

Reading (label: the association’s plain-words note and its proposed policy, not the document): “a fine is imposed only after notice, a hearing, and a decision” states Part C(b) and Civil Code 5855 as the profile’s inventory reads them (lead 1); “thirty days from the day you received it” is printed as a date so no one counts (section 7, row 2).

Who decides: nobody decides a registration; the manager records it (B-1: “registered with the manager”). The Board decides whether to impose a fine, after the hearing. How to reconsider: a member who disagrees with a fine asks at the hearing the Part C procedure gives; a member who disagrees with a record asks the manager to correct it.

## 7. The association’s clocks

“Counted from” is stated in each row. The documents count in “days”; jason counts calendar days and says so.

| # | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| 1 | the board’s choice of a month | distribute the form annually | the documents: B-1(d) “annually”; the month is PROPOSED POLICY | the association has not distributed it |
| 2 | “receipt” of the form | complete within **thirty (30) days**. **PROPOSED POLICY:** the form prints the due date, the thirtieth day after the delivery date the notice ledger shows (the mailing date for a mailed form), so no one counts | the documents (30 days); PROPOSED POLICY for what “receipt” is (lead 3) | the registration is not “updated”; a person decides whether a hearing follows |
| 3 | a change of occupancy | a revised form within **thirty (30) days** of the change | the documents: B-1(d) | as row 2 |
| 4 | receipt of a completed form | acknowledge within 2 business days | PROPOSED POLICY (as the response rules’ `acknowledge_days=2`) | the Owner is left without a date |
| 5 | receipt of a completed form | enter in the register within 5 business days | PROPOSED POLICY | the register is stale for the manager’s use |
| 6 | the due date | a reminder 10 days before, and a second notice on the due date | PROPOSED POLICY | the owner is not reminded |
| 7 | the due date | a list of units with no form goes to the board, with no fine and no letter on jason’s initiative | PROPOSED POLICY (jason lists; the board decides) | see lead 1 |
| 8 | each year | the register is read again at the next distribution; a unit’s earlier registration is shown to the owner to confirm, and is never read as this year’s | PROPOSED POLICY | a stale registration stands |

A “business day” is not defined in the documents. PROPOSED POLICY: the association states the definition it uses on the form (`{BUSINESS_DAY_DEFINITION}`).

## 8. The acknowledgment text

> Reference {REFERENCE}. We received your resident and vehicle registration for your Unit on {RECEIVED}. It lists {RESIDENT_COUNT} resident(s) and {VEHICLE_COUNT} vehicle(s). {DECIDER} records it. Your next yearly form will be sent in {NEXT_MONTH}; if someone moves in or out, send a revised form within thirty days of the change. To change this registration, use the same form or write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.

`{DECIDER}` is the manager. `{DUE}` is not used: the form is already complete.

## 9. Channels and the reference

- **Channels:** paper, fillable PDF, email, PayHOA, portal. The PayHOA form is the preferred channel (a signed-in answer is `SIGNED_IN` and the unit is known); a reply email from the address on file `MATCHED`; a signed paper copy `CLAIMED`. A Google Form is not offered: the 2024 form’s responses were unverified and had to be read as leads ([forms.md](../../../docs/forms.md)), and the registration holds residents’ and vehicles’ details that belong in a restricted store, not a shared Forms account.
- **Marker code proposed: `RH`** (residents). Letters from the alphabet `0-9 A C E F H K M N P R T V X`. `RT` (the first choice, “registration”) is taken by the resale-documents design, so this form uses `RH`; the codes in use or proposed in [the design pages’ table](../../../docs/form-templates/README.md) and this folder are `NP`, `NC`, `NA`, `NV`, `CN`, `HM`, `AM`, `RR`, `MN`, `RT`, `MC`, `RV`, `PP`, `PR`, `AP`, `RC`, `EV`, `PV`, `PX`, `RN`, `VR`, `PK`; `RH` collides with none. A campaign is the year: `RH27M-…` for the mailed blank, `RH27E-4RK9T-C7` for a pre-filled copy (the residents and vehicles on file, for the owner to confirm).
- The reference is a hint, never what the reading depends on ([form-identifiers.md](../../../docs/form-identifiers.md)).

## 10. Profile slots

Filled for this association; the values that are private (contacts, the manager’s address) are in `data/spec/mystique.json`, not here.

| Slot | Filled with |
|---|---|
| `{ASSOCIATION}` | the association’s name |
| `{DECIDER}` | the manager (“registered with the manager”, B-1) |
| `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}` | where the form goes: the manager’s contact and the homeowner portal’s Requests section |
| `{DUE_DATE}` | the thirtieth day after the delivery date (row 2) |
| `{NEXT_MONTH}` | the month the board sets for the yearly distribution |
| `{FINE_LINE}` | “Failure to maintain registration: $1 per day” (Part C a), the Enforcement Policy); and see lead 1 |
| `{BUSINESS_DAY_DEFINITION}` | none adopted |

## 11. Handler and procedure

- **Handler:** a **general handler** (`authority` is the rule, not a statute): `@handler("owners-manual#B-1", role=Role.FORM_RETURN, form="resident-registration", procedure="resident-registration", channels=(PAYHOA, GMAIL, MAIL))` ([arrivals-design.md](../../../docs/arrivals-design.md): “append to a Google Sheet (a register)”). `accepts` takes an arrival with this form’s marker (`RT`) or a PayHOA form id. `read` is evidence only; **a person confirms before anything is entered** (as with the owner-information returns). `plan` appends the residents and vehicles to the **resident and vehicle register** (a restricted Sheet; [registers.md](../../../docs/registers.md)), opens no clock but the acknowledgment’s, and drafts the acknowledgment. The register has a row per resident and per vehicle, with the unit and the date; the contact and emergency columns are restricted.
- **What it never sets:** the occupancy tags (“Rental”, “Owner Occupied”, “Vacant”) or any delivery tag. A registration is not the owner’s annual answer ([owner-information.md](../../../docs/owner-information.md)): tags carry no dates, so a registration never changes them. Adding a lessee as a PayHOA “other contact” is a person’s confirmed write, if the board wants it.
- **Procedure:** `resident-registration` does not exist in `src/jason/community/procedures.py`; the nearest is `owner-info-cycle` (a yearly campaign) and `notice-delivery` (the send and its follow-ups). Add it, **held with the rental forms**: (1) the board sets the month and says whether it may go while the occupancy hold stands; (2) build the form from the template and test it as an owner; (3) plan the send and send in batches (email first, letters after); (4) read the returns, confirm each, and enter them in the register; (5) the reminders of row 6; (6) the list of units with no form goes to the board (row 7); (7) a change of occupancy arrives as a revised form within thirty days; (8) write each failure as a lesson.
- **Template changes this needs:** a repeating group (`repeat`) on a template, for the residents and the vehicles; a restricted-store flag on its answers (P3); a pre-filled copy from the register.
- **jason never:** fines, sends a letter to an owner about a missing registration on its own initiative, tows or reports a vehicle, or opens a lease or a screening report (AGENTS.md, Boundaries).

## 12. Edge cases

- **Co-owners.** One form for the unit; either may complete it; the date received is the first receipt.
- **A representative or a resident answering for the owner.** Accepted; `capacity` says which. The owner remains the person B-1(d) holds to the thirty days.
- **A tenant or another non-owner.** A lessee is a resident (B-1(b)) and is registered on the owner’s form. A lessee who writes to the manager is told the owner completes it; the manager may record a lessee’s vehicle at the owner’s word.
- **A unit with no resident** (vacant, or the owner lives elsewhere): the form says “no residents”, and the registration records it; `no-vehicles` likewise.
- **Language and accessibility.** The documents’ words stay in English; large print, another format, a person to read the form aloud or write it down, and a reasonable accommodation are offered.
- **A form with no marker (a photocopy) or no form.** A letter or email that lists the residents and vehicles is a registration if it carries the rest; the handler reads it into the form and asks once for what is missing.
- **A change in a vehicle’s plate or a new vehicle.** A revised form, or a one-row form; it is a change of the registration, not of occupancy; the thirty days of B-1(d) are read for occupancy only (lead 3).
- **The request is really something else.** A guest’s vehicle is a guest permit ([parking-permit.md](parking-permit.md)); a lease is the rental path; a request to change delivery or add a second address is [the change form](../../../docs/form-templates/delivery-change.md) or [the second-address form](../../../docs/form-templates/secondary-address.md). The handler routes it the same day and says which it used.

## 13. Leads for the board and counsel

These are readings, not rules, and jason resolves none. Each should be read in full by a person before anyone acts on it.

1. **“Shall impose a fine.”** B-1(d): “The association shall impose a fine for failure of an owner to maintain updated registration.” A fine is valid only under a schedule distributed to members (CIV 5850(a)) and after the hearing CIV 5855 provides; the profile’s `hearing-procedure` row notes that the policy’s steps differ from the statute’s. The fine schedule’s “$1 per day” is a per-day fine; the `per-day-fines` row records that whether a fine accruing by the day survives the statute’s cap is unsettled and that the course meanwhile is to accrue no per-day fine until counsel advises (board item `enforcement-policy-ab130`). The rule is the board’s to apply, not the manager’s; this form says a fine follows notice and a hearing and promises none.
2. **The occupancy hold.** The form asks who lives in the unit; an owner contacted about it is an owner contacted about occupancy. The board takes up `rental-approvals-4-15` first, or says registration may proceed. Until then it is designed, not sent.
3. **“Receipt.”** B-1(d) counts thirty days from receipt of a form the association distributes. The documents do not say what receipt is for a mailed or emailed form. CIV 4050 deems delivery of an Act document complete on deposit in the mail or on transmission; the registration form is not an Act document, so this is a reading only. The proposal prints the date. For counsel if a fine is ever contested.
4. **Who completes it.** The form goes to owners; B-1 says “All members and residents ... must be registered”. A lessee’s duty is not stated apart from the owner’s; CC&Rs 4.15(j) makes the owner “strictly responsible and liable to the Association for ... each tenant’s compliance”. Reading (labeled): the owner completes it for everyone.
5. **Two lists.** The annual owner-information request (CIV 4041) and this registration both touch who occupies a unit; they have different purposes, authors, and clocks. Keeping them apart (no shared tags, no shared form) avoids a registration being read as the owner’s written answer.
6. **The 2024 responses.** The Google Form’s responses are unverified; they remain leads for an owner to confirm, and their uploads (leases, background checks, credit checks) are not read ([forms.md](../../../docs/forms.md), “Leases”).
7. **What the data is used for, and who sees it.** B-1(e) lists four uses. A list of residents and vehicles is a restricted record (P3): it is not part of the membership list and is not shown to members. Whether any of it is an association record a member may inspect (CIV 5200 to 5240) is for counsel.
8. **A vehicle registration.** B-1(c) asks “written evidence of current registration for each vehicle”; CC&Rs 4.11 lets the Board require it. The form asks a copy; whether a photograph of a registration card (which carries an address) is the right evidence is for the board.
9. **Adoption.** B-1 and the fine schedule were adopted April 18, 2023 (`owners-manual-2023`); whether the Part C schedule or the Enforcement Policy Document’s controls is open ([manual.md](../manual.md), item 6). The registration line is the same in both.

## 14. Test fixtures

Made-up answers. All use plainly fake data.

**Typical** (a yearly form for a unit with two residents and one vehicle):

| Field | Answer |
|---|---|
| `owner-name` | A. Owner |
| `unit-address` | 123 Main St, Anytown, CA 90000 |
| `capacity` | An owner of this unit |
| `kind` | The yearly form |
| `res-name` (row 1) | A. Owner |
| `res-relationship` (row 1) | Owner |
| `res-name` (row 2) | B. Owner |
| `res-relationship` (row 2) | Member of the owner’s family |
| `veh-plate`, `veh-state` | 1ABC234, CA |
| `veh-desc` | blue sedan |
| `veh-evidence` | ticked; file attached |
| `attestation` | ticked; signed 2026-11-02 |

Expected: two resident rows and one vehicle row in the register; acknowledgment counts 2 and 1; no tag written.

**Minimal** (the smallest valid return): `owner-name`, `unit-address`, `capacity`, `kind`, one resident (`res-name`, `res-relationship`), `no-vehicles` ticked, signature.

**Edge cases:**
- A revised form with `change-date` 2026-11-10 and a new lessee: the lessee row added; the earlier registration kept as history; no occupancy tag written.
- A vehicle row with `veh-evidence` unticked: incomplete; one request for the evidence; the row is entered and marked “evidence missing”.
- `res-relationship` = “Lessee” and no other lease fact: accepted; nothing about the lease is asked.
- A unit with no residents: a form with `no residents` ticked; the register records it.
- A form returned after the due date: recorded with its date; listed to the board (row 7); no fine.
- A form with no marker (a photocopy): identified by its printed lines and title.

**The documents’ checklist test, in words.** (1) The form asks every member and resident of the unit and every vehicle, and written evidence of current registration for each vehicle. (2) It prints the thirty days as a date and the revised-form clock. (3) It states B-1(e)’s four uses and says a fine follows notice and a hearing. (4) It asks nothing of the 4041 answers (delivery, a second address, a representative, occupancy) and nothing about a lease, a background check, or a credit report. (5) Its answers are in a restricted store and set no occupancy or delivery tag. (6) The recital block contains the exact words of B-1 and B-1(d) and (e), each filled from the document, and the build fails if a section is gone. (7) The acknowledgment carries `{RECEIVED}`, `{DECIDER}`, `{REFERENCE}` and the counts. (8) The form is not generated while the hold stands: the generator refuses it and says “held: rental-approvals-4-15”. (9) The same template renders paper, PDF, email, and PayHOA with the same questions in the same order, each carrying `RH`. (10) A made-up return of each fixture reads back to the same answers after a bad scan.
