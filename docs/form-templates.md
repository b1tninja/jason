# Form templates for the requests an association must accept

Status: design (2026-10-05). It sets the standard every form follows and lists the forms. Each form's own design is in [form-templates/](form-templates/README.md). The inventory of requests is [standard-forms.md](standard-forms.md); how a returned form is recognized and handled is [arrivals-design.md](arrivals-design.md) and [responses-design.md](responses-design.md); the form system (definitions, rendering, reading) is [forms.md](forms.md).

## Why a form

A standard form does three things the law needs and an email cannot:

1. **It promulgates.** A rule binds because it is made known. A form that opens with the operative words of the section, then asks, shows the member the right, the content, and the clock in the same place they use it. A member who has never read the Act can still use it.
2. **It gives the request a defined shape.** The law attaches duties and clocks to a request: records within a number of days of a written request, an architectural decision within the time the procedure states, a meeting on a payment plan. A form makes the request complete, dated, and identifiable, so the clock starts on a day both sides can name.
3. **It lets the association read, not guess.** Without a form the association parses arbitrary requests: a record request buried in a complaint, an application with the tenant's name missing, a dispute with no statement of what is wanted. That is slower, error-prone, and a risk to the association, which must answer on a clock. A known structure is read by a rule, checked by a test, and handled by a registered process.

The cost of not providing a form falls on both sides: the member does not know what to say, and the association does not know what it has been asked.

## What a form is not

- **Not the only door.** A request in other words is still a request. A form makes the usual request easy; it is never a condition of being heard, and it never narrows a right the law gives. The form says so.
- **Not legal advice.** A form recites the law and asks. It does not say what the law means for this member; where a reading is offered it is labeled as one and whose it is.
- **Not a way to ask more than the law or the documents need.** Each question names why it is asked. A form that asks for what a document forbids the board to consider does not go out.

## The standard every form follows

1. **Recite, then ask.** The form opens with the operative words of its authority, quoted from the statute on disk by token (`{QUOTE:...}`; [embedded-references.md](embedded-references.md)), with the as-of date, and with the caveat that jason's text is not an official restatement. The paraphrase "in plain words" may follow the quote, labeled as the association's plain-words note, never in its place.
2. **Ask only what is needed, and say why.** Every question carries the authority or the document section that makes it necessary. A question the law bars (a rental form that asks who the tenant is, where the document says the board shall not inquire) is not on it. An email address is never required unless the request is for delivery by email (Civil Code 4041(b)(2)(A)).
3. **State the clocks to the member.** What happens next, by when, who decides, how the decision comes (in writing, with reasons where the law says so), and how to ask the board to reconsider. Where the law or the documents set the time, say whose it is; where they are silent, show the board's proposed policy as proposed.
4. **Acknowledge with a date.** Every form that is returned gets an acknowledgment that states the date received, the clock that started, and the next step. The date received is the date the clock starts unless the law says otherwise.
5. **Help is on the form.** Where to ask for another format, large print, translation, or help filling it in; that a reasonable accommodation is available; and a plain way to make the request without the form.
6. **One definition, every channel.** The same `FormTemplate` renders the mailed letter, the fillable PDF, the emailed copy, the PayHOA form, and the portal page. Each copy carries its reference ([form-identifiers.md](form-identifiers.md)). The paper form is written to be read after a scan ([form-reader.md](form-reader.md)).
7. **A reference exists only if a handler does.** No copy is made until the form names its handler and procedure ([arrivals-design.md](arrivals-design.md)); a form with no handler is not generated, and the refusal tells the administrator what is missing.
8. **Plain language.** Questions at about an eighth-grade reading level; one question, one value ([forms.md](forms.md)); a heading is the topic, never a legal term alone.
9. **Tested.** Each form has made-up answers (a fixture), a statutory checklist test, a recital-freshness test, and a scan test ([form-fuzzer.md](form-fuzzer.md)).

## Anatomy of a template

A template extends today's `FormTemplate` (`key`, `title`, `authority`, `description`, `questions`, `signature`, `dated`, `preamble`, `attestation`, `code`, `style`) with:

| Field | Holds |
|---|---|
| `authority` | the citations, canonical (`CIV 5205`), as a tuple; the process key ([arrivals-design.md](arrivals-design.md)) |
| `recitals` | the `{QUOTE:...}` tokens recited first, each with the subdivision it is |
| `required_content` | the checklist of what the law says the form or the request must carry, each item pointing at the question that carries it (the test reads this) |
| `questions` | as now, each with `why` (the authority or section) and, where it is a legal term, a plain-words help line |
| `member_clock` | the sentence the member reads: what happens, by when, who decides, how to reconsider |
| `association_clocks` | the rows the handler runs: day counted from, number and kind of day, who sets it (statute, documents, proposed policy), and what follows if it passes |
| `acknowledgment` | the receipt text, with `{RECEIVED}`, `{DUE}`, `{DECIDER}`, `{REFERENCE}` |
| `procedure`, `handler` | the SOP key and the registered handler ([arrivals-design.md](arrivals-design.md)) |
| `channels` | which of paper, fillable PDF, email, PayHOA, portal, and Google Form it is made for |
| `slots` | what the profile supplies: `{ASSOCIATION}`, `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}`, `{PORTAL}`, `{BOARD_CONTACT}`, `{FEE_SCHEDULE}`, and the clocks its documents state |

## Base templates and the profile

The forms the law requires are **base templates**, written once in jason (`src/jason/community/form_library/`) and general: they name no association. A profile fills their slots (its name, return address, contacts, fee schedule) and gives them the clocks its documents state, so a community-specific copy is generated, not edited by hand (AGENTS.md). The forms the *documents* create (a rental application, a variance request, a registration) are base templates too, with the structure common to most declarations; a profile supplies the sections and the clocks of its own documents and may add questions its documents require.

## The forms

Grouped by what the member is asking. Each has a design page in [form-templates/](form-templates/README.md). "Required" says why the association provides it: the law makes it accept the request (L), the law prescribes what the form or the solicitation carries (P), or the documents make the member ask first (D).

| Form | Authority | Required | Handler's job |
|---|---|---|---|
| **Records** | | | |
| Request to inspect or copy association records | CIV 5200 to 5240 | L | the 5210 timeframes; cost estimate agreed before copying; the record set |
| Request for documents for the sale of a unit | CIV 4525 to 4530 | L, P (the 4528 charges form) | the required documents, the 4530 billing disclosure |
| Request for the membership list or to opt out of it | CIV 5220 | L | the list, with the opt-out noted |
| **Disputes and money** | | | |
| Request to meet and confer (internal dispute resolution) | CIV 5900 to 5920 | L ("shall not refuse") | designate a director; the written agreement |
| Request for resolution (alternative dispute resolution) | CIV 5925 to 5965 | P (the request's required content) | the response period, the next step |
| Request for a payment plan | CIV 5665 | L | the meeting within the time; the standards |
| Notice of a disputed charge | CIV 5658 | L (a right of the owner) | record the protest; the evidence |
| **Changes to a unit and protected uses** | | | |
| Architectural application | CIV 4765 | L | the procedure's maximum response time; a written decision with reasons |
| Request for reconsideration of a disapproval | CIV 4765(a)(5) | L | reconsideration at an open board meeting |
| Electric vehicle charging station application | CIV 4745, 4745.1 | L | decision in writing within 60 days or deemed approved |
| Solar energy system application | CIV 714, 714.1, 4746 | L | the notice to owners in the building; the insurance certificate |
| Protected-use application (landscaping, accessory dwelling unit, and others the documents make an owner ask about) | CIV 4735, 4751, and the other sections of CIV 4700 to 4753 | L | the same clock; a document's approval requirement is void where it bars the use |
| **Notices and delivery** | | | |
| Owner information and notice delivery preferences | CIV 4041 | P (the solicitation) | built; the cycle |
| Change my notice delivery | CIV 4041(b)(2)(B) | P ("a simple method ... in writing") | tags, the cycle |
| Secondary address for notices and collection notices | CIV 4040(b), 4041(a)(2), 5260 | L | the additional copies from the date received |
| Request for individual delivery of general notices | CIV 4045(b) | L | all general notices to that member individually |
| **Meetings and elections** | | | |
| Candidate nomination and statement | CIV 5100 to 5145 | L (the election rules provide a method) | the election; the inspector |
| Request to be heard at a meeting | CIV 4925(b) | L | the open-forum order and time limit |
| **Accommodation** | | | |
| Reasonable accommodation request | federal and state fair-housing law; CIV 4765(a)(3) points to it | L (outside the Act) | for counsel; the clock is the board's policy |
| **Required by the documents** (the profile's) | | | |
| Rental application, exception, and rehearing request | the documents' rental section; CIV 4740, 4741 | D | the documents' clocks |
| Variance request | the documents' variance section | D | the hearing, its notice, the decision |
| Resident and vehicle registration | the rules | D | the register |
| Parking or guest permit | the rules | D | the register |

Counts: 19 forms from the Act and the law around it, four from a typical declaration. One of them (owner information) is built; the others are designs.

## Order of work

1. The two forms the law's text makes most exact: the **request for resolution** (the Act says what it must contain) and the **resale documents request** (the Act prescribes the billing form). A template that must contain a checklist is the easiest to test and the most valuable to get right.
2. The **records request** and the **architectural application and reconsideration**, which the association receives most.
3. The delivery forms (change, secondary address, individual delivery), which finish the 4041 cycle.
4. The rest, and the profile's four.

## Drift: the recitals are by token

The existing records form recites "Civil Code 5205(e)" for the copying charge. The charge is in 5205(f) and (g) in the text on disk; the subdivision moved when the section was amended. A form that quotes by token cannot drift: the words and the subdivision come from the shelf when the form is built, and the build fails if a cited subdivision is gone. `jason law-history` and `jason conflicts --leads` already find the amended sections; a form lists its citations so the same check reaches it.
