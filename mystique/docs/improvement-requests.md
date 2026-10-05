# Home improvement requests: this association's provisions, forms, and gaps

The general design is [../../docs/improvement-requests.md](../../docs/improvement-requests.md): the workflow's states, the clocks, the policies proposed for a board, the records, and the owner's outputs. This page maps it to this association: which provisions apply, how requests reach jason today, what the forms hold, and where a written policy is needed. It names no owner and no private fact; owners and units are in `mystique/notes/` and `data/spec/`, which are not checked in.

The words below are recited from jason's copy of the documents (`jason cite`, read October 5, 2026), each labeled with where it is written. A document kept as amended is consolidated from the instruments' own words; it is not an official restatement, and the recorded and adopted documents control. A reading is labeled as one.

## The provisions

| Provision | Operative words, as written | What it sets | Where it enters the workflow |
|---|---|---|---|
| CC&Rs Section 5.1, "Approval by Board" | "... any proposed modifications to a Unit or Exclusive Use Common Area which are visible from the exterior of the Unit ... the Owner must submit to the Board in writing such proposed modifications to the Board, which may, in its sole discretion, approve or disapprove such proposed modifications." | The Board decides. The reach is a modification "visible from the exterior" of a Unit or an Exclusive Use Common Area | `ChangeRule` (exterior: approval required); the decider is the board |
| Owner's Manual B-18, "Architectural Control" (the Architectural Control Policy; also printed in the annual disclosures under the heading of Civil Code 4765) | "The Board of Directors is responsible to approve any exterior changes to your unit or exclusive common areas and the common areas which are visible from the exterior of the unit." "you must get approval BEFORE making any changes." "must have prior written approval from the Board of Directors." | The same reach, in the operating rules. Applications go "via the Requests section of the homeowner portal." The list of information asked for is in B-18(b) | The channel; the checklist; the annual notice (4765(c)) |
| CC&Rs Section 4.18, "Alterations to Units" | "No Unit shall be altered in any manner which would result in an increase in sound transmission, resonance or reverberations to any other Unit. Only soft-cover floors may be installed on the lower levels of Units, except for replacement of any hard coverings in kitchen, bath or other areas where such hard coverings were originally installed by Declarant." | A restriction on interior alterations. It states no approval requirement | `ChangeRule` (interior flooring: undetermined, below) |
| CC&Rs Section 7.5, "Interior Decorations" | "Except as limited by Section 4.18, above, each Owner shall have complete discretion as to furniture, furnishings, and interior decorating of the interior of his or her Unit" ... "no Owner shall do anything in or about his or her Unit that will affect the structural integrity of the building in which it is located." | Interior finishes are the owner's, limited by 4.18 and by structure | `ChangeRule` (interior finishes: not required; structure: undetermined) |
| CC&Rs Section 4.20, "Variances" | "The Board shall be authorized to grant reasonable variances from the provisions of Article 4 of this Declaration upon written application from any Owner ..." with its own hearing procedure | A route to relief from an Article 4 restriction, such as 4.18, on its own clock | The variance track (`ResponseKind.VARIANCE`, 45 days from the profile's response rules) |
| Bylaws Section 9.9(h), "Architectural Review Process" | "The Board of Directors shall distribute to the Members annually a notice of the requirements for Association approval of physical changes to property by a Member." | The annual notice, which 4765(c) also requires | `architectural-requirements`, carried by the annual policy statement |
| Bylaws Section 11.2, "Standing Committees" | "No standing committee shall have the authority to enter into contracts or otherwise act on behalf of the Association." "... shall operate under the supervision of and at the direction of the Board." | A committee may be appointed; it does not act for the association | Review: a committee reads and reports; the board decides |
| Bylaws Section 8.2(i)(ii) | "Use of a Unit, including any aesthetic or architectural standards that govern alteration of any improvements to a Unit." | An operating-rule subject, which is also Civil Code 4355(a)(2) | A standard on this subject is a rule change with 28 days' notice (4360) |
| CC&Rs Section 8.1(a)(i)(B), "Units" | "The standard fixtures and Improvements within individual Units as originally installed by Declarant and any equivalent replacements thereto" ... "excluding any Improvements or upgrades to any of the foregoing to the extent the replacement cost of any such Improvement or upgrade made after completion of the original construction of the Unit exceeds the replacement cost immediately before the installation of the Improvement or upgrade." | Where the declaration draws the insurance line: original and equivalent replacements on one side, upgrades to the extent they cost more on the other | The record's status words; the schedule; the loss packet's first step |
| CC&Rs Section 8.4, "Individual Owner's Property Insurance" | "Each Owner shall purchase and at all times maintain a policy of personal liability and property insurance insuring the Owner's Unit, any upgrades or additions to any fixtures or Improvements to the Owner's Unit, and personal property." | The owner insures upgrades and additions | The owner's schedule |
| CC&Rs Section 8.1(a)(vii), "Deductible" | "The amount of any deductible shall be paid by the Association and/or Owner pursuant to guidelines adopted by the Board." | The board's deductible guidelines, not yet adopted (`deductible-guidelines`) | The packet's fifth step |

**Readings, labeled.**

- *jason's reading: the reach.* 5.1 and B-18 reach changes visible from the exterior and exclusive-use patios, decks, and garages. 7.5 leaves interior finishes to the owner. 4.18 restricts some interior alterations and says nothing of approval. Civil Code 4765(a) applies "if the governing documents require association approval." Read together, the documents require approval for exterior changes and are silent on whether an interior alteration, such as a hard floor on a lower level or a change to plumbing, needs it. The answer for those is **undetermined**, a question for the board, not "not required." Counsel may read 4.18 and 4.20 to make a hard floor on a lower level a variance request. The board asks.
- *jason's reading: "sole discretion."* 5.1 says the Board "may, in its sole discretion, approve or disapprove." Civil Code 4765(a)(2) says a decision "may not be unreasonable, arbitrary, or capricious." Both can be obeyed: the board alone decides, and decides in good faith. This is noted, not a `Conflict` row. Counsel may read it differently.
- *jason's reading: the improvement the declaration means.* Section 1.22 defines "Improvement" as "all structures and improvements including without limitation buildings, landscaping, paving, fences, and signs." A change to a Unit's finishes is an Improvement under 8.1(a)(i)(B) when it is installed. Whether it is an Improvement that 5.1 reaches depends on the words "visible from the exterior."

## The proposed `ChangeRule` rows

These are rows a profile would hold. None is adopted. The first rows follow the words above. The last rows are the undetermined ones; each becomes a question for the board.

| Change | Answer | Decided by | Provision |
|---|---|---|---|
| A modification visible from the exterior of a Unit, including an awning | approval required | the deciding fact: visible from the exterior | CC&Rs 5.1; B-18 |
| An alteration to the exterior surfaces of a Unit or an exclusive-use patio, deck, or garage | approval required | the location | B-18 |
| A change to a common area visible from the exterior | approval required | the location | B-18 |
| Interior painting, papering, paneling, and refinishing of walls, ceilings, floors, and doors | approval not required | the location and the kind | CC&Rs 7.5 (limited by 4.18) |
| Replacing a hard covering in a kitchen, bath, or other area where one was originally installed by the Declarant | undetermined (no approval clause) | the missing fact: whether the documents require approval for interior work | CC&Rs 4.18, 7.5 |
| Putting a hard covering where the original was soft-cover, on a lower level | undetermined: a restriction with no stated approval, and a variance route | the missing fact: the track | CC&Rs 4.18, 4.20 |
| Replacing plumbing, electrical, heating and cooling, or a water heater inside a Unit | undetermined | the missing fact: whether approval is required, and whether it is an equivalent replacement | CC&Rs 7.5, 8.1(a)(i)(B) |
| Anything that may "affect the structural integrity of the building" | undetermined | the missing fact | CC&Rs 7.5 |

The third column is the three-valued reading's deciding or missing fact ([../../docs/improvement-requests.md](../../docs/improvement-requests.md#the-request-at-intake)). A change the rows do not reach stays undetermined and becomes a question.

## How a request reaches jason today

- **The PayHOA form.** "Architectural Request," one of three request forms (`mystique/requests.py`, read from the stored requests September 29, 2026). It asks for a title and a message; an attachment is optional. It has no question for the change's category, its location, the contractor, the permit, or the neighbors, so a completeness check has nothing to read. B-18 sends applicants to the Requests section of the owner portal, so the form is live. A live form gains questions only through `jason forms --payhoa KEY --update`, which keeps each question's id and answers, and is never deleted or replaced.
- **The paper and PDF application.** The Home Improvement Request Application (a form in the library and in the annual disclosures). It carries: name, date, address, phone; a proposed completion date; the type of architectural improvement (exterior doors, window coverings, sunshades, porch or balcony changes, and others) and the materials; additional comments; a neighbor acknowledgment block, with a note that acknowledgment "is required"; three general conditions of approval (comply with the governing documents; obtain governmental approvals; keep materials and debris off parking areas and the private street); the applicant's signature; and a block "to be completed by the Association" with approved, not approved, conditionally approved, comments, a board signature, and a date. Its first note asks that plans "be submitted at least thirty (30) days before activity begins" and says "No activity may begin prior to approval." That 30 days is an owner's lead time, not a time for the association to respond.
- **The kind and the clock.** The classifier reads a request on the "Architectural Request" form, or one with the words of a home improvement or permission to change, as an architectural application. The profile's one row for it is a `POLICY` clock of 30 days and an acknowledgment within two business days, "proposed policy; CIV 4765(a) requires the documents to state the maximum time, and they state none" (`mystique/responses.py`). It is proposed and not adopted.
- **The assignment.** The schedule's `architecture` assignment is the board's, with the provisions it cites and "the decision" as its evidence.
- **The manual's open questions.** `mystique/manual.py` carries two: whether B-18(b)'s list of information is part of the review procedure the documents must include or guidance, and whether the application's general conditions were adopted as operating rules or are the form's terms.

## What the form lacks beside Civil Code 4765(a)(4)

The statute asks a disapproval to be in writing with "an explanation of why the proposed change is disapproved and a description of the procedure for reconsideration of the decision by the board." The form's block for the board holds a checked word, a comments line, a signature, and a date. It has no place for the reasons against a standard, the procedure for reconsideration, or the meeting and the vote. The base `architectural-decision` letter in the general design supplies them. The profile supplies the citation for `CitationPurpose.ARCHITECTURAL_REVIEW` (not yet set in `mystique/templates.py`): the Architectural Control Policy (Owner's Manual B-18) and CC&Rs 5.1.

## Clocks and the meeting schedule

- No statute sets a time for an ordinary application, and the documents set none. Solar (45 days), charger (60 days), and a disaster rebuild (30, 45, and 60 calendar days) have statutory clocks, already in the response rules and notice catalog (the rebuild's `Term` rows are proposed). A variance under 4.20 has its own, in the documents.
- The board meets the third Tuesday of every month in practice, and the resolution's regular months are January, April, July, and October (`mystique/banking.py`). Third Tuesdays of consecutive months are 28 or 35 days apart. An application that is complete the day after a meeting can be decided at the next, 28 or 35 days later, with the notice four days before (Civil Code 4920(a)). A 30-day policy clock is met only when the gap is 28 days and the review is done before the notice; a 45-day clock is met by either gap. This is computed from the schedule, labeled so, for the board's brief on `improvement-review-time`. It is not a recommendation.

## Where a written policy is needed

For each policy the general design proposes, what this association's documents already say:

| Policy key | What the documents say | The gap |
|---|---|---|
| `improvement-review-time` | Nothing for an ordinary application. 4.20 times a variance | a maximum time for response and for reconsideration (4765(a)(1)) |
| `improvement-approval-needed` | Exterior changes need approval (5.1, B-18). Interior finishes are the owner's (7.5), limited by 4.18 | which interior changes need approval; the notice's list of types (4765(c)) |
| `improvement-application-contents` | B-18(b) lists what to send; the form lists its fields; open manual question | whether the list is a requirement; contents by category; copies; electronic submission |
| `improvement-delegation` | The Board decides (5.1). A committee does not act for the association (11.2) | what the manager may determine; whether any category may be pre-approved |
| `improvement-conditions` | Three general conditions on the form; open manual question | whether they are operating rules; the standard list; due days and proof |
| `improvement-lifetime` | A proposed completion date on the form | how long an approval lasts; an extension |
| `improvement-verification` | Nothing | what shows the work matches the approval; who verifies |
| `improvement-reconsideration` | Nothing for architecture | how to ask, by when, the meeting |
| `improvement-neighbors` | The form says acknowledgment "is required" | who is affected; what an acknowledgment means; where a neighbor's name is kept |
| `improvement-records` | Nothing | retention; a copy to the owner; inspection by another member |
| `improvement-unapproved-work` | B-18(d) and (e) say an alteration without prior written approval is removed at the owner's cost and may be fined by the day | a first step that is a question; the route to a hearing. The `per-day-fines` and `hearing-procedure` conflicts are open (below) |
| `improvement-statements` | Nothing | whether the association gives a copy of an owner's own approvals, and at what fee |

**The open conflicts that touch an unapproved-work lead.** The `per-day-fines` row (B-18(e) and the fine schedule against Civil Code 5850(c) and 5865) is with counsel, and its applied rule meanwhile is "Accrue no per-day fine until counsel advises." The `hearing-procedure` row says the enforcement policy's steps are followed with the statute's (5855). Neither is settled here: a "records show work" lead goes to the board as a question, and any later enforcement is the enforcement policy's process, on its own record.

**Adoption.** A rule on 4355(a)(2) or (a)(6) is a rule change with 28 days' notice (`jason rule-change`). The `rule_changes()` rows are where each proposed policy is tracked once the board takes it up. Until the board adopts a row it is proposed, measured internally, and never published to owners as a promise.

## The unit record and the insurance line

- The declaration draws the line at "originally installed by Declarant and any equivalent replacements," and excludes upgrades "to the extent the replacement cost ... exceeds the replacement cost immediately before the installation." That is a difference in cost, so the owner's figure for what a replaced item would have cost to replace in kind is the field that would let a record show it. Whether to ask for it is a question for the insurance agent and counsel, with `unit-finishes-and-equipment` and `builder-options` ([unit-records-profile.md](unit-records-profile.md)). The schedule an owner makes recites the declaration's lines (8.1(a)(i)(B), 8.4) beside it and the statute's own statement from Civil Code 5300(b)(9) in the annual insurance summary. It gives no coverage advice.
- The owner's entry names the original component from the plan's specification. The specifications by plan are not yet on file (`original_specs()` is empty), so every component of every plan reads unknown until the developer's papers are read.

## What is not decided here

The policies above; whether the Board delegates; how 4.18 and 4.20 apply to a hard floor; whether a request and its decision are association records a member may inspect; whether an entry an owner shared may start a lead; and the deductible guidelines. Each is a board or counsel question in the general design's open decisions.
