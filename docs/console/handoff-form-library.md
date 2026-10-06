# Handoff: the form a member sees, the place to find one, and the library an administrator keeps

For a design pass on three things that come from [form-templates.md](../form-templates.md) and [form-library-design.md](../form-library-design.md): the **form itself** (one anatomy for paper, the fillable PDF, the emailed copy, PayHOA's form, and the portal page), the **member's request center** (where an owner finds the right form and follows what they sent), and the **form library** (where an administrator sees which forms are built in, adjusted, not offered, or stale). It sits beside [handoff-responses.md](handoff-responses.md) (one returned form, read for a person) and [handoff-forms-and-arrivals.md](handoff-forms-and-arrivals.md) (arrivals, the cycle board, the forms register). Read [handoff-reconciliation.md](handoff-reconciliation.md) and its third and fourth cuts first. The component names are proposals; the data shapes follow the designs and the build corrects this page.

## The idea in six sentences

A form is how a member exercises a right in a way the association can answer on time. It opens with the law's own words, so a member who has never read the Act sees what they are entitled to; it asks only what is needed and says why; and it tells them what happens next, by when, who decides, and how to ask again. The same design serves a sheet of paper, a PDF, and a web page, so a member never meets a different form for a different channel. A member can always make the request without the form, and the form says so. The administrator's screen shows which forms jason provides for every community under the law, which this community adjusted, and which are waiting on something. Nothing here decides a request or tells a member what the law means for them.

## Who sees what

| Viewer | Sees |
|---|---|
| An owner (the owner view) | the request center and the forms; their own requests and their status; never another member's, never the library |
| A manager, the Secretary | the forms and the library read-only; every request on `#/requests` ([screens/requests.md](screens/requests.md)) |
| An administrator | the library with its checks and the commands that change it |
| A director | the library read-only |

## 1. The form page

One anatomy, every channel. Top to bottom:

```text
+--------------------------------------------------------------------------------+
|  {ASSOCIATION}                                       Request to inspect records |
|  Form version 2 · the law as of the 2025 publication                              |
+--------------------------------------------------------------------------------+
|  WHAT THE LAW SAYS                                                      Civil Code §5205, §5210 |
|  "The association shall make available association records ..."  (quoted, exact) |
|  "In plain words" (the association's note, labeled)                                |
+--------------------------------------------------------------------------------+
|  WHAT HAPPENS NEXT                                                                |
|  We will write to you by [date the clock names] ...                               |
|  Who decides · How you can ask us to reconsider · What if we do not answer        |
+--------------------------------------------------------------------------------+
|  YOUR REQUEST                                                                     |
|  1. Your name                                                                     |
|  2. The records you want        why we ask: the law asks you to identify them (§5205(e)) |
|  3. ... (each question: the label, a line of help, a "why we ask")                |
+--------------------------------------------------------------------------------+
|  You do not have to use this form. You may write to us in your own words.         |
|  Need another format, large print, a translation, or help filling this in? [how]   |
+--------------------------------------------------------------------------------+
|  Signature ______________  Date ________        Ref NP27E-… (small, top right)   |
+--------------------------------------------------------------------------------+
```

- **The recital block** (`RecitalBlock`): the quoted words with their citation and the as-of; "In plain words" follows, in a quieter face and labeled the association's. Never the other way round. The block is short: the operative sentence or two, with a link or a QR code to the full section. Where the section is long, the form quotes the part that answers the member's question and names the rest.
- **What happens next** (`MemberClockPanel`): written as a promise in plain words, with the dates filled when the form is returned (the acknowledgment). It is the same panel on every form: when we reply, who decides, how to ask again, what the member can do if we do not act (for example "deemed approved"). Where the clock is the board's proposed policy (the law is silent), it says so: "proposed by the board; the board has not yet adopted it".
- **Each question** (`QuestionWithWhy`): a label in plain words, one line of help, and a small "why we ask" naming the authority or the document section. An optional question says "optional" and says what happens if it is left blank. A question that asks for something sensitive (a diagnosis is never asked) says why and how it is kept.
- **The right to use other words** and **the help line** (`HelpFooter`): always present, above the signature, never in a footer a printer cuts off.
- **The reference** (`Ref NP27E-…`) top right and as a bar mark top left, as today ([form-identifiers.md](../form-identifiers.md)); the layout rules for print are [form-design.md](../form-design.md): a proportional face, 22 pt writing rooms, no combs.
- **Length:** a form fits on one sheet when the law allows, never more than four billed pages ([the Mailroom's limit](../mailroom.md)).

**Per channel,** the same content with the channel's own affordances:
- **Paper and the fillable PDF:** one question per line; the recital and the clocks above the first question; the acknowledgment slip a tear-off or a second page, never a footnote.
- **PayHOA's form:** question help under 255 characters, so the recital is a heading text block and "why we ask" is the help; the clocks are in the form's description. Where PayHOA cannot show a block, the form's first question is a read-only text and a link to the full page.
- **The portal or web page:** the same panels in the same order; the recital is expandable but open by default; a progress note ("3 of 7") only on forms longer than a screen.
- **The emailed copy:** the recital and clocks in the message, the form attached, the reference in the subject.

**States:** blank, filled, with an error (a required question empty; an address that does not read as an address, said in words, never red alone), submitted (the receipt), and "your request is already on file" (a duplicate within a window).

### `AcknowledgmentReceipt`

What the member gets back, and what the association keeps:

```text
We received your request on Oct 5, 2026.   Reference NP27E-4RK9T-C7
What we will do:   Make the records available by Oct 19 (10 business days, Civil Code §5210)
Who decides:       The manager, for the board
If we do not:      You may write to the board, or ask to meet and confer (Civil Code §5915)
Questions:         [contact]
```

It states the date received (which starts the clock), the due date computed from the clock, and the next step. One component for every form; the words change, the shape does not.

## 2. The member's request center

An owner-view screen, `#/requests`, that answers "what do I do to …?" rather than "which form is it?".

```text
+--------------------------------------------------------------------------------+
| Ask the association                                                              |
| [ Search: "records", "rent", "change a window" ]                                 |
+--------------------------------------------------------------------------------+
| Records and money                                                                 |
|   Look at or copy the association's records           [ Open the form ]          |
|   Ask for a payment plan                                [ Open the form ]          |
|   Dispute a charge                                      [ Open the form ]          |
| My home                                                                           |
|   Change something on my home (architectural approval)  [ Open the form ]          |
|   Install an EV charger or solar panels                 [ Open the form ]          |
|   Ask for a reasonable accommodation                    [ Open the form ]          |
| How you hear from us                                                              |
|   Change how I get notices · Add a second address                                  |
| Disputes                                                                          |
|   Ask to meet and confer · Ask for resolution                                      |
| Selling my unit                                                                   |
|   Ask for the documents for a sale                                                 |
+--------------------------------------------------------------------------------+
| My requests                                                                       |
|   Records · sent Oct 5 · we reply by Oct 19                       [ Received ]    |
+--------------------------------------------------------------------------------+
```

- **Grouped by need, in the member's words.** The group names and links are the community's own list (the library supplies the forms; the community orders and names the groups). A form the community has not made ("not offered") is not shown, and "Don't see what you need? Write to us" is always the last line.
- **Each entry** (`FormPicker`) names the right, the form, and how long it usually takes ("we reply by 10 business days"), and opens the form in the channel the community chose (PayHOA, the portal, or a PDF).
- **My requests** (`RequestTracker`): each request the owner sent, with the date received, the clock, who has it, and the standing words already used (`answered on time`, `due soon`, `open`, [screens/requests.md](screens/requests.md)); never the board's notes, never the other side's reasoning; a decision appears when the association sends it. Read-only; there is no "withdraw" until the board decides what it means.
- **The owner view's allowlist:** the center, the forms, and the member's own requests only (`ui/src/ownerScreens.json`, the server's allowlist); nothing here is a board or manager screen.

## 3. The form library (the administrator's)

A table of the forms jason provides for this community, by tier.

| Column | |
|---|---|
| Form | its title and key |
| Tier | **State** (the law's, built in), **Family** (a structure the documents fill), **Custom** (the community's own) |
| Authority | the citation, a link to the words |
| Version and as-of | `v2 · the 2025 publication`; **stale** when a section it cites has been amended since |
| Status | ready; adjusted (what); not offered (the missing slot, in words); failing (what) |
| Handler and procedure | links |
| Campaigns | the cycles that used it, with the version each used |

```text
+--------------------------------------------------------------------------------------+
| Forms provided for this community             Law: United States, California            |
| 19 built in · 3 adjusted · 2 not offered · 1 failing        checked Oct 5, 4:30 PM      |
+--------------------------------------------------------------------------------------+
| STATE   Request to inspect records          CIV 5205, 5210      v2  ready, adjusted     |
|           adjusted: a stricter clock (the documents' section), a question added         |
| FAMILY  Rental application                  the documents' §…    v1  not offered        |
|           missing: which section creates it · the board's decision                      |
| STATE   Request for resolution              CIV 5925–5965        v1  failing            |
|           a required item is not carried: "notice that the other party must respond"    |
+--------------------------------------------------------------------------------------+
```

- **Adjusted** opens a diff: the built-in form on the left, this community's on the right, each change labeled with who set it and why (a document's section, a community choice). An adjustment that would remove a required item is shown as **refused**, with the finding.
- **Stale** reads "A section this form cites was amended on [date]. Read the amendment before the next campaign." with the citation and the amendment's words (`Recitation`); never silent, never auto-fixed.
- **The checks** (`CheckFinding`): the seven in [form-library-design.md](../form-library-design.md#what-the-library-checks), each a plain sentence: what, which form, which item, and the one step.
- **Read-only** for everyone but the administrator, whose changes are commands until console writes exist (`TerminalStep`).
- **No "publish" button:** a form is made for a campaign when a person chooses to, not when it is edited.

## Components

| Component | On | Job |
|---|---|---|
| `FormPage`, `RecitalBlock`, `MemberClockPanel`, `QuestionWithWhy`, `HelpFooter` | every form, every channel | The anatomy |
| `AcknowledgmentReceipt` | the confirmation | The date received, the clock, the next step |
| `FormPicker`, `RequestTracker` | the request center | "What do I do to …?" and "where is my request?" |
| `LibraryRow`, `TierBadge`, `VersionStamp`, `StaleNote`, `AdjustmentDiff`, `CheckFinding` | the library | A form's tier, version, status, changes, and findings |

Reuse what is built: `Tabs`, `RegisterGrid`, `Recitation`, `Seal` (`read`), `Pill`, `Command`/`TerminalStep`, `Evidence`, `Glyph`, `Caveats`, `AgeStamp`. No `Stamp`: a form is not a decision.

## Words

| Say | Not |
|---|---|
| What the law says / In plain words | Legal notice / Summary |
| What happens next | Process, workflow |
| Why we ask | Required field |
| You do not have to use this form | Optional |
| We received your request on | Submitted |
| Not offered (because …) | Disabled, unavailable |
| Stale: read the amendment | Outdated, error |

## What must not change

- The law's words come first and exact; the plain-words note is labeled and follows.
- A question the law or a document bars is never on a form; a question never asks for a diagnosis or a tenant's identity where the documents say the board shall not consider it.
- Every form says the member may use other words, and where to get help or another format.
- The acknowledgment states the date received, and that date starts the clock.
- A form is not a decision, and no screen decides a request or tells a member what the law means for them.
- The owner view shows an owner their own requests only; the library is never in it.
- Confidence and attention are never color alone; every form is readable at large print.

## Decisions that are the design's

1. How much of the recital shows by default on a phone, and how the full section is reached from paper (a short link, or a QR code the Mailroom's page budget allows).
2. Whether "What happens next" sits above the questions (the proposal: the member should know the clock before committing) or beside them on a wide screen.
3. How the request center groups forms when a community has many custom forms.
4. Whether the library is its own page or a tab of Forms (`#/forms`), and how a diff reads on a narrow screen.
5. The glyphs for a form's three tiers (one meaning per glyph).
6. How a member who prefers paper reaches "My requests" (a reference lookup on the receipt).

## Open (the build's or a person's)

- The console routes (proposed): `GET /api/forms` and `/api/forms/<key>` (the resolved library for the viewer), `GET /api/my-requests` (the owner's own, read from the member requests' clocks), the library's check as `GET /api/form-library`.
- Which of the form's channels the community offers is the board's decision; the library lists what exists.
- The request center's groups and names are the community's; the first list is the board's to confirm.
