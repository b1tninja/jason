# Parking permit and guest permit request

Status: design (2026-10-05). Key `parking-permit`; proposed marker code `PK`. It follows the standard in [form-templates.md](../../../docs/form-templates.md). The inventory row is "Parking permit; guest permits" in [standard-forms.md](../standard-forms.md) (the worked example: “not a kind; no form”); the general family is [docs/standard-forms.md](../../../docs/standard-forms.md) (family two: the documents make the owner ask). No law governs this form, so its `authority` is the rule, not a statute, and its handler is a general one ([arrivals-design.md](../../../docs/arrivals-design.md)).

**Offering waits on two answers from the board:** which fee applies (the documents carry two; lead 1), and what the permit program rests on (the Manual cites a section that is about variances; lead 2). It is designed now; nothing is sent or posted.

## 1. Authority and what the law requires

As of: the association’s documents as jason holds them (`data/governing/owners-manual-and-rules.md`, `ccrs.md`; `data/artifacts/site-docs/governing_documents/`), read 2026-10-05. The words below are recited from jason’s copy and labeled with where they are written. A document kept as amended is consolidated from the instruments’ own words; it is not an official restatement, and the recorded and adopted documents control. **No statute on the shelf requires this form.**

**The instruments.**
- **Owner’s Manual and Rules, “B-12. Parking”** (also the parking rules Document, word for word the same, [manual.md](../manual.md)): adopted August 30, 2022 with “the fine schedule as amended ($15 a month parking permit)” (rule-change record `parking-fines-2022`); the Notice of Adoption was delivered by September 19, 2022. B-12’s bullets are lettered here (a) to (q) in order, as the profile’s inventory letters them: (b) the guest spaces, (o) the permit program, (p) the display of permits.
- **Owner’s Manual, Part C, “a) Fine Schedule”**, adopted April 18, 2023 (`owners-manual-2023`), and the **Enforcement Policy Document**: the two price lists, which differ (lead 1).
- **Restated Declaration**, recorded September 20, 2007, Document No. 200709200938: Section 4.11, “Vehicles and Parking”, lettered here (a) Limitations on Types of Vehicles, (b) Condition of Vehicles, (c) No Vehicle Repairs, (d) Parking of Vehicles of Residents, (e) Common Area Guest Parking Spaces, (f) No Parking Areas, (g) Parking Rules and Enforcement (with (i) Vehicle Towing and (ii) Fines). None of the three amendments touches 4.11.

**B-12(o), the permit program:**

> The board shall adopt a parking permit program to allow for long-term parking on a limited, month-to-month, basis (CC&Rs §4.20). Owners, and by proxy their residents, can apply for parking permits. The fees for the issued permits will be used to offset HOA costs associated with parking enforcement. All permits will be numbered. The parking permits may be used by the applicant or their Guest to park in any available parking space, and are non-transferable. Permits must be returned to the association when no longer needed. There shall be a replacement fee for lost or damaged permits. Upon the third request for a replacement an appearance before the Board will be required.

**B-12(p), the display:**

> Vehicles parked in the common areas, outside of garages, must display valid parking permits, except for such limited times as are necessary for deliveries, maintenance, repairs, and the loading and unloading of passengers. Any vehicle not displaying valid permits will be considered unauthorized and may be towed at the owner’s expense.

**B-12(b), the guest spaces and the guest permits:**

> The additional parking spaces, along Whimsical Lane, are designated for temporary parking of guest vehicles. No guest vehicle shall be parked in guest parking for three (3) nights or more than 72 hours during a period of seven (7) consecutive days. The movement of any vehicle for the purposes of preventing the application of this rule shall be ineffective. Each residence will be issued two (2) reusable temporary parking permits for guests.

**CC&Rs 4.11(e), Common Area Guest Parking Spaces:**

> Subject to the limitations further described in this Section, guests and invitees of Residents may park vehicles otherwise permitted by this Section within the Common Area parking spaces. No vehicle of a guest shall be parked overnight for three (3) nights or for more than 72 hours during any period of seven (7) consecutive days in any such parking space provided that the Board may, in its discretion, permit the parking of a vehicle of a guest for such longer period as it deems advisable. The movement of any vehicle for the purposes of preventing the application of this Section shall be ineffective.

**CC&Rs 4.11(d), Parking of Vehicles of Residents, and 4.11(f), No Parking Areas:**

> Residents shall park vehicles only within the garage serving the Resident’s Unit. In addition, provided that a Resident’s garage is occupied by (2) two vehicles subject to this Section, the Resident may park no more than one (1) vehicles per Residence on the public streets serving the Development.
>
> Except as specified in Section 4.11 (e), no vehicle may be parked on any portion of the Common Area. Vehicles parked within marked fire-lanes shall be subject to immediate towing in accordance with Section 4.11 (g) (i), below.

**CC&Rs 4.11(g), Parking Rules and Enforcement** (the Board’s authority to make rules):

> The Development is designed to include a total of ninety (90) parking stalls in addition to each Unit’s two (2) garage parking spaces. The ninety (90) parking stalls are expressly intended for non-Resident vehicle parking. In order to prevent or eliminate parking problems within the Development, or to further define and enforce the restrictions contained in this section, the Board shall have the authority to adopt further reasonable rules and restrictions regarding vehicles and parking within the Development as the Board may deem prudent and appropriate. The Board shall also have the power to impose sanctions for violations of provisions of the Governing Documents relating to vehicles and parking. Such authority and power shall include, without limitation:

**CC&Rs 4.20, Variances** (the section B-12(o) cites; the quotation is in [variance-request.md](variance-request.md)): “The Board shall be authorized to grant reasonable variances from the provisions of Article 4 of this Declaration upon written application from any Owner ...”. Article 4 includes 4.11.

**The fees, in the two price lists.** Owner’s Manual, Part C, a) Fine Schedule (adopted April 18, 2023): “Resident Parking Permit | $25”; “Guest Parking Permits | No Cost - 2 issued per residence”; “Lost or Damaged Permits | $25”; “Parking Violation | $50 and/or towing at owner’s expense”. The Enforcement Policy Document: “Parking Permit | $15 per month”; “Guest Parking Permits | No Cost - 2 per residence”; “Lost or Damaged Permits | $25”.

**What the documents do not say** (so the form does not say it either): a time within which a permit is issued; who issues it (the program is “adopted” by the Board; the manager administers it in practice); the number of resident permits a residence may hold; how long a month-to-month permit may run; what a permit costs (lead 1); a reason the applicant must give; what “an appearance before the Board” decides; whether the third replacement is counted by residence, by owner, or by year.

## 2. Who uses it, and when

- **An Owner, or a resident the Owner authorizes (“by proxy”)**, who wants to park a vehicle in the common area outside a garage, month to month (B-12(o)).
- **A residence** that needs its two guest permits (issued, “each residence will be issued two”), a replacement for a lost or damaged permit, or to return a permit no longer needed.
- **An Owner who wants a guest vehicle to stay longer** than the guest limit (4.11(e): the Board “may, in its discretion, permit” a longer stay).
- **When:** any time. The documents set no season.
- **Who it is not for:** a person who needs a parking space or a permit because of a disability (read as a request for a reasonable accommodation, and never refused for being on this form: [the accommodation page](../../../docs/form-templates/accommodation-request.md)); a person asking to register a vehicle (the registration form: [resident-registration.md](resident-registration.md)); an owner asking for a variance from another restriction ([variance-request.md](variance-request.md)); a person disputing a parking violation or tow (the hearing and dispute routes).

## 3. What the form must carry

| # | What the document says the form carries | Words | Carried by |
|---|---|---|---|
| 1 | The applicant is an Owner, or a resident authorized by the Owner (“by proxy”) | B-12(o) | `capacity`, `owner-ok` |
| 2 | What the permit is for: long-term parking on a limited, month-to-month basis | B-12(o) | fixed text, section 6 |
| 3 | The vehicle (permits are for vehicles in the common areas) | B-12(p) | `veh-plate`, `veh-state`, `veh-desc` |
| 4 | The vehicle is registered with the manager | B-1; B-12(o) “All permits will be numbered” | `registered` |
| 5 | A number for each permit; non-transferable | B-12(o) | fixed text; the register assigns the number |
| 6 | The fee, or “no cost” for the two guest permits | B-12(o); Part C | fixed text with `{FEE_SCHEDULE}` |
| 7 | The permit must be returned when no longer needed | B-12(o) | `request` (the “return” option); fixed text |
| 8 | A replacement fee for a lost or damaged permit, and an appearance before the Board at the third request | B-12(o) | `request`, `permit-number`, `replacement-why`; fixed text |
| 9 | A guest stays for no more than three nights or 72 hours in seven consecutive days, unless the Board permits longer | B-12(b); 4.11(e) | fixed text; the guest-extension block |
| 10 | A vehicle in the common areas outside a garage must display a valid permit, or may be towed | B-12(p) | fixed text |
| 11 | Who is asking, and for which unit | B-12(o) | `owner-name`, `unit-address`, `capacity` |
| 12 | That a request in other words is still a request, and where to get help | [standard 5](../../../docs/form-templates.md) | fixed text |

## 4. The questions

Kinds: text, choice, checkbox, date, address, paragraph. One question holds one value; each `request` option opens its own block.

| Key | Question text | Kind | Required | Why | Reads as | Sets |
|---|---|---|---|---|---|---|
| `owner-name` | Your name | text | yes | B-12(o): “Owners, and by proxy their residents” | NAME | request.requester |
| `unit-address` | Unit address | address | yes | places the request | ADDRESS (prefilled `UNIT_ADDRESS`) | register: unit |
| `capacity` | You are | choice: “An owner of this unit”; “A resident applying for the owner (by proxy)” | yes | B-12(o) | TEXT | request.capacity |
| `owner-ok` | The owner knows I am applying and agrees | checkbox (one box) | yes if by proxy | B-12(o): “by proxy” | TEXT | request.owner_ok |
| `request` | What do you want? | choice: “A resident parking permit (month to month)”; “My residence’s two guest permits”; “A replacement for a lost or damaged permit”; “To return a permit I no longer need”; “To ask the Board to allow a guest vehicle to stay longer than the guest limit” | yes | B-12(o), (b); 4.11(e) | TEXT | which block applies |
| `veh-plate` | License plate of the vehicle | text | yes for a resident permit | B-12(p): a permit is for a vehicle | TEXT | register: plate |
| `veh-state` | State | text (two letters) | yes for a resident permit | identifies the plate | TEXT | register: plate state |
| `veh-desc` | Make, model, and color | text | yes for a resident permit | identifies the vehicle | TEXT | register: vehicle |
| `registered` | This vehicle is on my unit’s resident and vehicle registration | checkbox (one box) | yes for a resident permit | B-1: “all vehicles ... must be registered with the manager”; if not, the registration form first ([resident-registration.md](resident-registration.md)) | TEXT | request.registered |
| `start-month` | The first month you want it for | date (a month) | yes for a resident permit | B-12(o): “month-to-month” | TEXT | request.start_month |
| `permit-number` | The number on the permit | text | yes for a replacement or a return | B-12(o): “All permits will be numbered” | TEXT | request.permit_number |
| `replacement-why` | Was it lost or damaged? | choice: “Lost”; “Damaged” | yes for a replacement | Part C: “Lost or Damaged Permits”; B-12(o) | TEXT | request.replacement_why |
| `guest-plate` | License plate of the guest’s vehicle | text | yes for a longer guest stay | 4.11(e) | TEXT | request.guest_plate |
| `guest-desc` | Make, model, and color of the guest’s vehicle | text | no | 4.11(e) | TEXT | request.guest_vehicle |
| `guest-from` | The first night | date | yes for a longer guest stay | 4.11(e): the period | TEXT | request.guest_from |
| `guest-to` | The last night | date | yes for a longer guest stay | 4.11(e) | TEXT | request.guest_to |
| `guest-why` | Why does the guest need longer? | paragraph | no | the Board decides “in its discretion”; the form does not require a reason | TEXT | request.guest_why |
| `attestation` | I am an owner of this unit, or am authorized to apply for the owner, and what I have written is true | checkbox (one box) on PayHOA and PDF; the signature line on paper | yes | assurance ([forms.md](../../../docs/forms.md)) | TEXT | request.attested |
| (signature) | Signature and date | signature line, date | yes on paper and PDF; “signed in” online | B-12(o): the owner’s application | NAME | request.signed |

Not asked, on purpose: why the applicant needs the permit (B-12(o) lets owners apply and requires no reason), the applicant’s income or health, the vehicle’s value or insurance, the number of vehicles in the garage (the Board may read the registration), and the unit’s occupancy.

## 5. The recitals

The form opens with these, by token, with the document and section named, then the caveat of section 1. The documents are cited as `{QUOTE:owners-manual#B-12(o)}` ([embedded-references.md](../../../docs/embedded-references.md)); the form’s record carries the instrument and date that set the words.

| Token | Section | Why it opens the form |
|---|---|---|
| `{QUOTE:owners-manual#B-12(o)}` | (o) | the permit program: who may apply, numbered, non-transferable, returned, replaced |
| `{QUOTE:owners-manual#B-12(p)}` | (p) | a valid permit must be displayed outside a garage |
| `{QUOTE:owners-manual#B-12(b)}` | (b) | the guest spaces, the limit, and the two guest permits |
| `{QUOTE:ccrs#4.11(e)}` | (e) | the Board may permit a guest a longer stay |

A plain-words note may follow each, labeled “The association’s plain-words note; the words above control.”

## 6. What the member is told

The sentence the Owner reads (`member_clock`):

> The Association’s rules (B-12) let owners, and residents they authorize, apply for a numbered parking permit for long-term parking in the common areas on a month-to-month basis. A permit may be used by the applicant or the applicant’s guest, is not transferable, and must be returned when it is no longer needed. The fee is {FEE_SCHEDULE}. Each residence is issued two reusable guest permits at no cost. A lost or damaged permit is replaced for a fee; at the third request for a replacement, you will be asked to appear before the Board. A vehicle parked in the common areas outside a garage must display a valid permit, or it may be towed at the owner’s expense. A guest may stay no more than three nights or 72 hours in seven days; the Board may allow longer, in its discretion, if you ask. We will tell you in writing the day we received your request and when your permit will be ready.

Reading (label: the association’s plain-words note, not the document): the sentence on the fee states the price list the board has confirmed (lead 1). “We will tell you ... when your permit will be ready” is the proposed policy of section 7; the documents state no time.

Who decides: the documents do not say who issues a permit. The program is one the Board “shall adopt” (B-12(o)); the manager administers it in practice. The Board decides a third replacement (“an appearance before the Board”) and a longer guest stay (4.11(e): “the Board may, in its discretion”). How to reconsider: there is no stated route. A member who disagrees asks the Board in writing, may speak at a board meeting ([meeting-comment-request.md](../../../docs/form-templates/meeting-comment-request.md)), and may ask to meet and confer (CIV 5900 to 5920).

## 7. The association’s clocks

“Counted from” is the association’s receipt, stamped on the day it arrives (mail on the day opened; email, PayHOA, and the portal on the day sent). The documents state no clock for any part of this form; every row is PROPOSED POLICY unless marked.

| # | Counted from | Number and kind of day | Who sets it | What follows if it passes |
|---|---|---|---|---|
| 1 | receipt | acknowledge within 2 business days | PROPOSED POLICY (as the response rules’ `acknowledge_days=2`) | the Owner is left without a date |
| 2 | receipt of a complete request | issue the numbered permit within 5 business days | PROPOSED POLICY | the Owner parks without a permit and may be towed (B-12(p)) |
| 3 | the permit’s first month | the permit runs month to month until it is returned; each month’s fee is billed through the Owner’s account | PROPOSED POLICY (B-12(o) says “month-to-month basis” and no end) | a permit that no one ends keeps charging |
| 4 | the end of the need | return the permit within 14 days | PROPOSED POLICY (B-12(o): “when no longer needed”) | the register shows a permit in use |
| 5 | receipt of a replacement request | issue the replacement within 5 business days, on payment of the fee; at the third request, the Owner is asked to appear before the Board | the documents for the third request; PROPOSED POLICY for the days | the third request is decided without the appearance |
| 6 | receipt of a guest-extension request | the Board answers before the guest’s first night, and at the latest within 10 business days | PROPOSED POLICY (4.11(e) states no time) | the guest parks without leave and the vehicle may be treated as unauthorized |
| 7 | receipt of a request for the two guest permits | issue them within 5 business days | PROPOSED POLICY (B-12(b): “each residence will be issued”) | the residence has no permits |
| 8 | a sale of the unit | the permits are returned at closing, and the register is closed | PROPOSED POLICY (B-12(o): “non-transferable”) | the new owner finds permits still in use |

A “business day” is not defined in the documents. PROPOSED POLICY: the association states the definition it uses on the form (`{BUSINESS_DAY_DEFINITION}`).

## 8. The acknowledgment text

> Reference {REFERENCE}. We received your parking request on {RECEIVED}. {ASKED_FOR}. {DECIDER} will have your permit ready by {DUE}; the number will be on it. A permit is not transferable and must be returned when you no longer need it. A vehicle parked in the common areas outside a garage must display a valid permit. To change or withdraw your request, write to {RETURN_BY_EMAIL} or {RETURN_BY_MAIL} and quote the reference.

`{ASKED_FOR}` is the option chosen: “You asked for a resident parking permit”; “You asked for your residence’s two guest permits”; “You asked for a replacement; this is the {Nth} request for a replacement for your residence”; “You asked to return permit {permit-number}”; “You asked the Board to allow a guest vehicle to stay longer; the Board will answer before {guest-from}”. `{DECIDER}` is the manager, except for a third replacement and a longer guest stay, where it is the Board.

## 9. Channels and the reference

- **Channels:** paper, fillable PDF, email, PayHOA, portal, and in person at the manager’s office for a permit’s return or replacement. The PayHOA form is the preferred channel (a signed-in answer is `SIGNED_IN` and the unit is known); a reply email from the address on file `MATCHED`; a signed paper copy `CLAIMED`. A Google Form is not offered: a permit has a number and a fee, and an unsigned-in answer would be a lead only.
- **Marker code proposed: `PK`** (parking). Letters from the alphabet `0-9 A C E F H K M N P R T V X`; the codes in use or proposed (see [the design pages’ table](../../../docs/form-templates/README.md)) include `NP`, `NC`, `NA`, `NV`, `CN`, `HM`, `AM`, `RR`, `MN`, `RT`, `MC`, `RV`, `PP`, `PR`, `AP`, `RC`, `EV`, `PV`, `PX`, and the profile’s `RN`, `VR`, `RH`; `PK` collides with none found in `docs/` or `mystique/forms.py`. A campaign is the year it was generated (`PK26P-…`).
- The reference is a hint, never what the reading depends on ([form-identifiers.md](../../../docs/form-identifiers.md)). **A permit’s number is not the reference.** The permit number is the register’s; the marker names the form and the year.

## 10. Profile slots

Filled for this association; the values that are private (contacts, the manager’s address) are in `data/spec/mystique.json`, not here.

| Slot | Filled with |
|---|---|
| `{ASSOCIATION}` | the association’s name |
| `{DECIDER}` | the manager; the Board for a third replacement and a longer guest stay |
| `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}` | the manager’s contact; the homeowner portal’s Requests section |
| `{FEE_SCHEDULE}` | **not filled**: the Manual’s Part C says $25 for a resident permit and $25 for a lost or damaged permit; the Enforcement Policy says $15 a month and $25. Empty until the board says which governs (lead 1). Guest permits: no cost, two per residence, in both |
| `{BUSINESS_DAY_DEFINITION}` | none adopted |
| `{GUEST_LIMIT}` | three nights or 72 hours in seven consecutive days (B-12(b); 4.11(e)) |

## 11. Handler and procedure

- **Handler:** a **general handler** (`authority` is the rule, not a statute): `@handler("owners-manual#B-12(o)", role=Role.FORM_RETURN, form="parking-permit", procedure="parking-permits", channels=(PAYHOA, GMAIL, MAIL))` ([arrivals-design.md](../../../docs/arrivals-design.md): “append to a Google Sheet (a register)”). `accepts` takes an arrival with this form’s marker (`PK`) or a PayHOA form id. `read` is evidence only; a person confirms before anything is entered. `plan` appends a row to the **parking permit register** (a Sheet; [registers.md](../../../docs/registers.md)): the permit’s number, kind (resident, guest, replacement), unit, vehicle, date issued, date returned, the fee billed, and the count of replacements for the residence; it checks the vehicle against the registration; it counts the replacement (the third needs the Board); it drafts the acknowledgment. A fee is billed by a person, not by jason (AGENTS.md: jason writes no charge). It writes nothing outside jason.
- **Procedure:** `parking-permits` does not exist in `src/jason/community/procedures.py`; the nearest is `respond`. Add it, with steps: (1) check the vehicle is registered (or ask for the registration form); (2) number and issue the permit; (3) bill the fee as a person confirms; (4) count a replacement and put the third on the board packet; (5) put a longer-guest-stay request on the board packet and answer before the guest’s first night; (6) at each month’s end, list permits unreturned for a year; (7) at a sale, close the unit’s permits; (8) write each failure as a lesson.
- **Template changes this needs:** a `required_if` on the vehicle and permit fields by `request`; a register with auto-numbering.
- **jason never:** issues a permit, decides a longer guest stay, bills or waives a fee, tows or reports a vehicle, or imposes a fine (AGENTS.md, Boundaries).

## 12. Edge cases

- **Co-owners.** Either may apply; one permit is for one vehicle; the register counts replacements by residence.
- **A representative or a resident by proxy.** B-12(o) allows it; `owner-ok` is the owner’s agreement. A permit applied for by a lessee without the owner’s agreement is held; the owner is written to at the address on file.
- **A tenant.** B-12(o) names “their residents”, who apply by proxy. A tenant who writes directly is told the owner agrees on the form; the association does not refuse to receive it.
- **A request for accessible parking.** Read as a request for a reasonable accommodation, dated at its first mention, and never closed for being on the wrong form; see [the accommodation page](../../../docs/form-templates/accommodation-request.md).
- **A vehicle not on the registration.** The permit waits for the registration; the owner is told once; the clock for the permit runs from the day the registration arrives.
- **A guest staying longer than the limit with no request.** Not this form: a violation notice; the form’s guest-extension block is how to ask first.
- **A lost permit found.** The owner returns one of the two; the register notes the replacement and the return; the third request is still counted.
- **Language and accessibility.** The documents’ words stay in English; large print, another format, a person to read the form aloud or write it down, and a reasonable accommodation are offered.
- **No form used.** A call or an email asking for a permit is a request; the handler reads it into the form and asks once for what is missing; the date received is the day it arrived.
- **The request is really something else.** A dispute over a tow or a violation notice goes to its own route; a request for a second resident permit is this form’s resident permit option (whether the program allows more than one is lead 6).

## 13. Leads for the board and counsel

These are readings, not rules, and jason resolves none. Each should be read in full by a person before anyone acts on it.

1. **Two prices.** The Manual’s Part C (adopted April 18, 2023) lists “Resident Parking Permit | $25”; the Enforcement Policy Document lists “Parking Permit | $15 per month”; the 2022 minutes adopted the $15 a month ([manual.md](../manual.md), item 6: “Which fine schedule is adopted”). The permit’s price is the board’s to say; the form prints none until it does. Whether a permit fee belongs in a schedule of fines and monetary penalties at all (CIV 5850) is for counsel.
2. **What the program rests on.** B-12(o) says the board “shall adopt a parking permit program ... (CC&Rs §4.20)”. 4.20 is Variances; the parking provisions are 4.11 ([the profile’s inventory](../standard-forms.md), lead 6). Two readings remain: (a) the program is a rule under the Board’s authority in 4.11(g) (“the Board shall have the authority to adopt further reasonable rules and restrictions regarding vehicles and parking”), and the citation is a slip; (b) each permit is a variance from 4.11(d) under 4.20, which would need an application, a hearing within forty-five days, and fifteen days’ notice to all Members for each ([variance-request.md](variance-request.md)). The documents do not say which. A person reads the minutes of the August 30, 2022 meeting; the board asks counsel; the Manual’s citation is corrected or explained.
3. **A permit and 4.11(d), (f), (g).** 4.11(d): “Residents shall park vehicles only within the garage serving the Resident’s Unit”, and one on the public street if the garage is full; 4.11(f): “Except as specified in Section 4.11 (e), no vehicle may be parked on any portion of the Common Area”; 4.11(g): the ninety stalls “are expressly intended for non-Resident vehicle parking”. B-12(o) lets a permit be used “to park in any available parking space”. Whether a resident’s permit for a common-area space is within the Board’s rule-making authority, or needs a variance or an amendment, is the same question as lead 2 and for counsel. The Manual yields to the Declaration where they conflict (A-3).
4. **Which spaces.** B-12(b) designates “the additional parking spaces, along Whimsical Lane” for guests; B-12(o) says “any available parking space”. Whether a resident permit may use a space designated for guests is not stated.
5. **The third replacement.** B-12(o): “Upon the third request for a replacement an appearance before the Board will be required.” Not stated: whether it is counted by residence, owner, or year; what the Board decides at the appearance (a further replacement? a fee?); whether it is a hearing under the discipline procedure. It is not discipline in the Manual’s Part C list; the form says “asked to appear”, not “a hearing”.
6. **How many resident permits.** B-12(o) does not limit the number a residence may hold, or say whether a permit may be held for each vehicle.
7. **“By proxy.”** B-12(o) says “Owners, and by proxy their residents, can apply”. Not stated: whether a lessee may apply without the owner’s agreement, or whether the owner is liable for the fee. CC&Rs 4.15(j) holds an owner responsible for a tenant’s compliance.
8. **The Manual’s text has a gap where the Document has a link.** “If you need an additional parking permit, submit a  .” and “Example Permits” read as blanks in jason’s copy; the Doc’s link is the existing permit form ([manual.md](../manual.md), “The text has gaps where the Doc has chips”). A person reads the Doc and carries the link; this design replaces the form it points to only when the board adopts it.
9. **No time to issue.** The documents state none. The proposed five business days are for the board to adopt.
10. **A list of permits and privacy.** The register holds plates and residences; it is a restricted record (P3), not part of the membership list.

## 14. Test fixtures

Made-up answers. All use plainly fake data.

**Typical** (an owner asks for a resident permit):

| Field | Answer |
|---|---|
| `owner-name` | A. Owner |
| `unit-address` | 123 Main St, Anytown, CA 90000 |
| `capacity` | An owner of this unit |
| `request` | A resident parking permit (month to month) |
| `veh-plate`, `veh-state` | 1ABC234, CA |
| `veh-desc` | blue sedan |
| `registered` | ticked |
| `start-month` | 2027-01 |
| `attestation` | ticked; signed 2026-12-01 (a Tuesday) |

Expected: a numbered resident permit in the register for the unit and the vehicle; acknowledgment with `{DUE}` = 2026-12-08 (five business days, counting the day after receipt as day 1, skipping the weekend, and no holiday in the span); `{FEE_SCHEDULE}` empty until the board says which governs, and the build refusing to print a price.

**Minimal** (the smallest valid return, the two guest permits): `owner-name`, `unit-address`, `capacity`, `request` = “My residence’s two guest permits”, signature.

**Edge cases:**
- A third replacement request: the register counts three for the residence; the acknowledgment says the Board will ask the owner to appear; it goes on the board packet.
- By proxy, `owner-ok` unticked: held; the owner written to.
- A vehicle with `registered` unticked: the permit waits; the registration form is offered.
- A guest extension with `guest-from` already past: read as a request; the Board is told the stay began; the acknowledgment says so.
- A request for accessible parking: read as an accommodation request on its first mention; no fee is billed on this form.
- A form with no marker (a photocopy): identified by its printed lines and title.

**The documents’ checklist test, in words.** (1) The form is the Owner’s, or a resident’s by proxy with the owner’s agreement. (2) It says the permit is month to month, numbered, non-transferable, and returned when no longer needed. (3) It says a vehicle outside a garage must display a valid permit. (4) It gives the guest limit and the Board’s power to allow longer, and says each residence is issued two guest permits at no cost. (5) It states a fee only if the board has confirmed which schedule governs; the build refuses a price while `{FEE_SCHEDULE}` is empty. (6) The recital block contains the exact words of B-12(o), (p), (b), and 4.11(e), each filled from the document, and the build fails if a section is gone. (7) The acknowledgment carries `{RECEIVED}`, `{DUE}`, `{DECIDER}`, `{REFERENCE}`. (8) The form asks no reason for the permit. (9) The same template renders paper, PDF, email, and PayHOA with the same questions in the same order, each carrying `PK`. (10) A made-up return of each fixture reads back to the same answers after a bad scan.
