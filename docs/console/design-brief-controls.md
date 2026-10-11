# Design brief: Controls (the safeguards jason suggests and the board adopts)

One page of orientation for the design agent, for the Controls screen `#/controls` specified in [screens/controls.md](screens/controls.md), on the design in [../controls.md](../controls.md). It does not repeat them; it says what to read in what order, each screen and component to draw, what is built and what has no view, and a made-up community to draw against. Where a spec and this page disagree, the spec and the code win, and this page is corrected. It reuses the vocabulary of [design-brief-work.md](design-brief-work.md) and [design-brief-board-records.md](design-brief-board-records.md) (`RecordTrail`, `EvidenceLinks`, `BasisPill`); reference those, do not redraw them.

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, bank, provision, or private fact; made-up samples only ("Oakview", "Example Bylaws, 99.9", "A. Treasurer", 2099). A dollar amount here is the board's **example number**, never a recommendation.

**Checked against the code on 2026-10-11.** **Built:** the approvals registry's `Approver.ONE_PERSON` and `TWO_PERSON` (`jason.approvals.registry`), second-person confirmation of a high-stakes onboarding answer (`POST /api/write/intake/<id>` with `{confirm: true, by}`, `SecondConfirm`, the Setup tab), board items and `jason.tasks.board_items.propose`, the decisions store and `DecisionsView`, `Community.officers()` with its `OfficerRole` words, and the components named in section D. **Not built, no view:** `Control`, `ControlType`, the catalog, the suggestion reader, the loaders (`controls`, `control`, `control-notices`), `jason controls`, the `controls` route (`App.tsx` `SCREENS` has none), the `control-adoption` definition (`jason.workflows.definitions` registers no definition; the Work screens have no view either), and the onboarding step. **Two facts to design around.** (1) The approvals engine reads only the kind's own rule: `needs_second` is true for a `TWO_PERSON` kind or any approved high-stakes item; the three registered kinds are all `ONE_PERSON`; there is no signer list, no threshold, and no "stricter of the kind's and the control's". So every "effective rule" below is to add. (2) The roster (`Community.officers()`) names who holds an office; it is not a signer list for payments.

## A. The idea, and the rules that run through it

**The idea, in six sentences.**

1. A **control** is a safeguard the board chooses to add to how the association works: two signers on a payment, a written resolution before an officer signs a contract, a review each month.
2. jason reads the governing documents and **suggests** the controls that follow from their duties and limits. It adopts nothing and **never turns one on**.
3. A suggestion is shown from the document to its effect: the provision's words whole, the floor, jason's reading (labeled), what the board adopted, what it changes, whether the roster can satisfy it, and the history.
4. The board **decides at a meeting; the secretary records it** in Decisions. This screen reads the result. Its one write puts a suggestion before the board as a board item.
5. A control **only adds**. It can require more; it can never sit below the floor the law, the documents, or a built-in two-person kind already sets. A request to go below is listed as **refused**, with the floor.
6. Where a control bites (a plan, a step, a send) the page says so in one line with a link, so a person is never blocked without a reason. The server refuses the act whatever the page shows.

**The rules** (each is in the spec; a screen that breaks one is wrong):

- **Directors and officers have the same access to information.** Every board member reads every control. The offices differ only in the acts only an officer may take (the secretary records; see [office-views.md](screens/office-views.md)). A roster person with no board office is refused with `access.may_see`'s sentence; an owner never.
- **Recite the rule, then label the reading.** The provision's words come first, whole, from the stored text (`Recitation`), then jason's reading in a `ReadingLabel` ("jason's reading, not the provision"). A provision jason cannot read cleanly is a **question** for the board or counsel, not a suggestion.
- **A suggestion never says it is in force.** In force needs all three: adopted, the effective date passed, the roster able to satisfy it.
- **Every date says whose it is.** A control's effective date is **the board's** (`person` basis), a "look again" date is the board's, a statute's is `law`, the documents' is `documents`. A date jason proposes wears `proposed policy`, never a stamp.
- **State is a word and a glyph, never colour alone.** The words are the loader's; the page invents none.
- **Offices, not people.** A control names an office ("the treasurer"). The roster check shows offices and counts (seated, vacant), never a name, email, or phone. Names appear only for an actor in a history line ("proposed by A. Secretary"), and in the decision record the card links to.
- **Acts are the signed-in person's own,** behind a `Confirm`. An administrator viewing as someone else sees "Viewing as NAME (admin view): go back to yourself first" in place of the control.
- **Nothing is hidden because of a control.** The notice never narrows what a board member may read.

## B. Reading order

1. [screens/controls.md](screens/controls.md): the whole screen, top to bottom.
2. [../controls.md](../controls.md): sections 1 (principles), 3 (what the documents suggest), 4 (lifecycle), 5 (enforcement). Do not read the association's own controls page; this brief and its sample are all a design needs.
3. This page's section D beside section H.
4. [screens/work.md](screens/work.md) and [design-brief-work.md](design-brief-work.md): the run page, the `decision` step (C6 here). [screens/board-items.md](screens/board-items.md): the item a proposal makes.
5. [screens/onboarding.md](screens/onboarding.md): the Setup tab and "Controls jason suggests" (the step C5). [screens/office-views.md](screens/office-views.md): who may act.
6. [approval-workflow.md](approval-workflow.md) and `src/jason/approvals/registry.py`: what `ONE_PERSON` and `TWO_PERSON` do today.

## C. The screens

### C1. The list (`#/controls`, Governance, beside Documents)

`ScreenHeader` with the line "jason suggests; the board adopts" and the loader's counts ("4 adopted, 2 of them not in force · 1 proposed to the board · 2 suggested · 1 deferred · 1 declined · 1 retired"). Filters: family, state. Rows grouped by **family** (money, contracts, reviews, notices, meetings, onboarding; an empty family is not drawn). Within a family: adopted, proposed, suggested, deferred, declined, retired. A **Refused** group closes the page (C2a). Each row: title, `ControlStateWord`, the provision's citation (a link to the card), one line of what it requires, "Propose" when it is a suggestion. A row's whole width is the link; "Propose" stays its own control.

```
MONEY
 Payment signers          ADOPTED · in force since Sep 20        Example Bylaws, 99.9
   The treasurer and one other director above $2,500 (example); any two directors below.
 Reserve withdrawals      SUGGESTED                              Example Bylaws, 99.9(b)   [Propose]
   The floor is two board members. jason suggests keeping that and naming which two.
 Manager spending limit   DECLINED Aug 1 · may be asked again after Feb 1, 2100 (the board's date)
 Payment countersign      RETIRED Sep 5 · replaced by Payment signers
CONTRACTS
 Contract authorization   ADOPTED · in force since Sep 20
 Contract term check      PROPOSED TO THE BOARD · item control-contract-term · next meeting Oct 24
REVIEWS
 Monthly review           ADOPTED, NOT IN FORCE · the vice president's office is vacant
NOTICES
 Delivery class           ADOPTED · takes effect Nov 14 (the board's date; not yet required)
 Recorder                 DEFERRED · look again Jan 15, 2100 (the board's date)
ONBOARDING
 Second person, other kinds  SUGGESTED                                                 [Propose]
```

Draw: the full list; the empty state ("jason has not read your governing documents. Ingest them from Onboarding." with the link); loading; the loader failed (the reason; nothing shown as adopted); a **question** row ("Example Bylaws, 99.9(c) reads two ways about who may sign for the reserve. A question for the board or counsel; no suggestion", with the words and why unclear); and a viewer who is refused.

### C2. One control (`#/controls?key=`), six bands, always in this order

A page, not a drawer. The header: breadcrumb, title, `ControlStateWord`, "Adopted Sep 5 · in force Sep 20 (the board's date)". Then, with each band a labeled region:

1. **The provision.** The citation and the words **whole** in a `Recitation`, then the floor in one sentence ("The floor: any two directors, or an officer and a director"), and beside it the statute when the floor is the law's. Sample words, all made up: *Example Bylaws, 99.9: "All checks, drafts, and orders for the payment of money shall be signed by any two directors, or by an officer and a director, unless the Board specifies another manner."*
2. **What jason suggested**, in a `ReadingLabel` ("jason's reading, not the provision"): "Name the manner the Bylaws allow: the treasurer and one other director above an amount the board sets." The suggestion is never pre-selected as the board's.
3. **What the board adopted.** The adopted parameters in the board's words, a `Stamp` "Adopted", the decision id, the meeting, the vote **as counts** ("moved, seconded, 5 to 0"), "recorded by the secretary", and **Open the decision**. Declined or deferred: the reason, the date, and the date it may be asked again, with its basis.
4. **What it changes.** One line per place it bites, each with the effective rule beside the built one ("Bill attach: two signers over $2,500; the kind's own rule is one person"; "Reserve transfers: unchanged, the floor is higher"). Each links to the approvals kind, step, or send.
5. **Can the roster satisfy it** (`RosterCheck`). "Needs: the treasurer; one other director. Seated: the treasurer, 3 directors." A shortfall says exactly who is missing by office: "The vice president's office is vacant." Offices and counts only.
6. **History** (`RecordTrail`, newest first, the current word marked): suggested by jason · proposed by A. Secretary · adopted · effective · a correction as a later row. A system row has no name ("jason, from a reading of Example Bylaws, 99.9").

A **suggestion** shows bands 1, 2, 4, 5, 6 and a **Propose to the board** `Confirm` ("Create a board item, `control-contract-term`, with this provision as its evidence, as A. Secretary. It adopts nothing and changes no rule."). Draw the card for each of the seven states, the card in the **adopted, not in force** state (two reasons: the date has not come; the roster cannot), and the card with a `ChangedBanner` (C2c).

### C2a. The refused-loosening row

A control that would go below a floor is never offered. It is listed at the foot of the list, with the floor named: "Refused: one signer for reserve withdrawals. The floor is two board members (Example Bylaws, 99.9(b), recited below). A control only adds." Its card has band 1 (the floor, whole) and a plain sentence; no Propose, no Adopt. Draw a refused row and its card.

### C2c. A provision changed since adoption

When an amendment changes the words a control rests on, the card shows a **banner above band 1**: "Amendment 2 changed Example Bylaws, 99.9 on Oct 1, 2099 (the governing documents' date). The control stays as the board adopted it. The board decides whether it still serves." with the old and new words side by side (both recited), and **Open the board item**. The built `ChangedBanner` is bound to a plan's staleness (`approval`, `recheck`, a re-plan button); draw this one from its shape, and say whether the component is generalized or a new `ControlChangedBanner` (section F).

### C3. `ControlNotice`: the line at the point of the act

One line, read-only, with the control's title as a link, shown only to a viewer who may read the control (every board member). It appears in **three places**; draw each:

- **An approvals plan** (`#/approvals`, the plan header beside the kind's facts and above `SecondConfirm`): "Two signers required: Payment signers, a control the board adopted on Sep 5. The kind's own rule is one person." On an item over the amount, a small tag "over $2,500 (example): a second signer". The plan's approver line shows the **effective** rule and where it came from.
- **A workflow step gate** (the step panel in a run, [screens/work.md](screens/work.md)): "A resolution must be on record before this step: Contract authorization, adopted Sep 5." The step reads `blocked` with the gate named until the decision is linked.
- **A Mailroom send** (the letters card in `#/approvals`; the console has no Mailroom screen, the send is `jason mailroom --send --yes`): "First class: Delivery class, a control the board adopted. Takes effect Nov 14." Draw it before and after the date: before, "Takes effect Nov 14; not yet required" (see F).

Never shown for a suggestion, a proposal, a declined, a deferred, or a retired control. A refused act says the same sentence in the server's words, naming the control. Draw the notice at 320 px.

### C4. A control the roster cannot satisfy

On the card (band 5), on the list row, and where it would bite: the act is **refused, not weakened**. "Two directors are required by Monthly review; one is seated. The act is refused. A control never falls back to fewer." Draw the refusal beside the control on the plan, and the same fact on the list.

### C5. Onboarding: "Controls jason suggests from your documents"

One optional step in the Setup session, after the governing documents are ingested and a person confirms their **duties were read** (so a misread provision is never suggested). A card per family with the list's rows, **Take these to the board** (one board item listing every suggestion with its provision) and **Not now**. Closing it records "seen", never "adopted". Never required for a gate. Draw it with `StageSteps` at the establish stage, with three families, with a question row, and after "Not now" (the line "Seen Oct 2, 2099; nothing adopted"). The second-person confirmation already there for high-stakes answers (`SecondConfirm`) is the model, and the first control family to name it is "Second person, other kinds".

### C6. The control-adoption run, in Work

One run per control ([workflows/README.md](../workflows/README.md); not registered). Draw the Work row and the run page against the seven steps: **suggest** (a `check`: jason's reader found the provision; done), **put it before the board** (a `person` step, the proposer, linking to Controls; done), **the board decides** (a `decision` step: the motion, mover, second, each director's vote by name, recusals, outcome, **read from the decision record**; no approve, vote, or adopt control), **record the decision** (the same `decision` step; "Record in Decisions" for the secretary, a link), **set the effective date** (a `person` step for the secretary; a date with the `person` basis), **check the roster can satisfy it** (a `check`; failed, `blocked`, naming the missing office), **in force** (a `wait` on the effective date, then a `check`; nothing is "turned on"). Work groups: the run sits in **The board** while step 3 is open; `blocked` runs sit in **Waiting on others**. Draw a run in each.

## D. The shared components, each once

Reuse (built, `ui/src/components`): `Card`, `Pill`, `Badge`, `Glyph`, `Seal` ("jason suggests", "jason proposes"), `Stamp` ("Adopted"), `Recitation`, `ReadingLabel`, `Caveats`, `Confirm`, `DataTable`, `Evidence`, `Doc`, `Command`, `StageSteps`, `SecondConfirm`, `HeldNote`, `Timeline`, `Tabs`, `Findings`, `Stat`, `EmptyState`, `Loading`, `ErrorNotice`, `ScreenHeader`. **Specified elsewhere, not built:** `RecordTrail`, `EvidenceLinks`, `BasisPill`, `RoleLine`, `WriteConfirm` ([design-brief-board-records.md](design-brief-board-records.md)); `RunStepPanel`, `ClockStrip` (Work). Draw them from the built parts and say so. `Stamp` has no declined or deferred word (its set is carried, failed, approved, denied, adopted, tabled, continued, referred, withdrawn, sent): use a `Pill` for those.

| Component | What it is | Data (the spec's field names) | States |
|---|---|---|---|
| `ControlRow` | One row of the list | `key, title, family, state, inForce, basis{citation}, summary, effective{date,basis}, proposedAs, missing[]` | the seven states; question; refused; adopted not in force |
| `ControlStateWord` | A `Pill` preset | `state` plus `inForce` and a `why` | suggested, proposed, adopted (in force), adopted (date ahead), adopted (roster lacks), declined, deferred, retired; an unknown word shown plainly |
| `ControlCard` | The six bands | `basis, floor, reading, parameters, decision{id,meeting,vote}, touches[], inForce, missing[], history[]` | each state; suggestion (no band 3); declined with reason; changed provision |
| `RosterCheck` | What the control needs and what is seated | `needs[]{office, count}, seated[]{office, count}, missing[]{office}` | satisfied; short; an office vacant; one person holds two offices (counts both, names none) |
| `ControlNotice` | The one line | `{title, key, adoptedOn, effective, effect}` | plan; step gate; send; in force only; not yet effective (see F) |
| `ControlProposeConfirm` | The one write | `{key}` and the signer's name taken by the server | pick; proposing; proposed; already proposed (refreshes the item); admin view |
| `RefusedRow` | A loosening refused | `{title, floor{citation, words}, why}` | one; several |
| `ControlChangedBanner` | A provision changed | `{was, now, changedOn, basis}` | one; absent |
| `OnboardingControlsStep` | C5 | the list's rows by family | offered; seen; not offered (duties not confirmed) |

**Fixed words** (use exactly): "jason suggests; the board adopts", "jason's reading, not the provision", "A control only adds", "Propose to the board", "Open in Decisions", "recorded by the secretary", "in force", "adopted, not in force", "a control the board adopted", "Viewing as NAME (admin view): go back to yourself first". Never "enabled", "turned on by jason", "activate", "violation", "compliant", "required by law" for a control, or "approve" or "vote" on this screen.

## E. Glyphs

All of these exist in the console's glyph set (`ui/src/lib/glyphData.ts`): `shield-check` (in force, and the screen), `proposal` (proposed), `circle-pause` (deferred), `circle-x` (declined), `archive` (retired), `ban` (refused), `user-x` (the roster lacks someone), `calendar-clock` (the date has not come), `clock`, `scale` (counsel reads), `signature` and `stamp` (adopted, recorded), `history` (the trail), `paperclip` and `link`, `lock` (held), `triangle-alert` (a changed provision), `circle-question-mark` (a question), `minus`. Each sits beside its word. Propose one new glyph, named for the idea: a **floor** mark (a baseline with a small arrow rising from it) for "a control only adds", used on the floor line of band 1 and on the refused row. A suggestion uses the existing `Seal` word "jason suggests", not a new mark.

## F. Decisions that are the design's, in one list

1. **Where the list sits and whether a card is a page or a drawer:** a page (`?key=`, recommended: six bands and a long recitation need room).
2. **How six bands fold on a narrow screen:** all open with a sticky band index (recommended) versus an accordion with the open question first.
3. **How the two states read apart** (settled 2026-10-11): "adopted, takes effect DATE" (the date has not come; at most a warning that the roster could not satisfy it) and "in force, the roster cannot satisfy it" (the date has come; acts it governs are refused with the reason, never relaxed): a word and a glyph each (`calendar-clock`, `user-x`), never colour alone.
4. **Whether `ControlNotice` shows a control not yet effective** ("Takes effect Nov 14; not yet required"). Recommended: yes, in the muted form, and never as required; a suggestion or a proposal never.
5. **The amendment banner:** generalize `ChangedBanner` or build `ControlChangedBanner`; and whether old and new words sit side by side or stacked.
6. **The `Confirm` wording** for "Propose to the board", and whether it previews the board item.
7. **Print:** one page of the board's adopted controls with each provision's citation, the effective date and its basis, and the roster check, for the board packet.
8. **The last step's name in the run** ("In force", a check, not "Turn on": jason turns nothing on).

These are not the design's: which families are offered first, whether a control may apply to one account, kind, or all (narrowest wins), whether an effective date is the meeting's or a later one, whether a declined suggestion may be asked again, who may propose (any board member is recommended), and where the refused loosening comes from (the spec lists it; no source row is defined yet).

## G. What can be designed now, and what waits

| Part | Now | Waits on |
|---|---|---|
| The list, the six-band card in each state, the refused row, the changed banner | Yes, from section H | `Control`/`ControlType`, the catalog, loaders `controls` and `control`, the route |
| `ControlNotice` in a plan | Yes; the plan header, `kind_facts`, and `SecondConfirm` are built | The effective-approver lookup in the approvals engine (a control may only tighten) and `GET /api/control-notices` |
| `ControlNotice` in a step and a send | Yes | The Work screens; no Mailroom screen (the notice sits on the letters card) |
| Propose to the board | Yes; `board_items.propose` is built | `POST /api/write/controls/<key>` |
| Onboarding step | Yes; the Setup tab, `StageSteps`, `SecondConfirm` are built | The suggestion reader and the "duties read" confirmation (the documents' duties are read; no signers or limits are extracted) |
| The control-adoption run | Yes, against the sample | The workflow engine's views; the definition is not registered |
| Roster check | Yes | `Community.officers()` is built; the check against a control's parameters is not |
| Adopt, decline, defer, retire | Not on this screen | They are the board's decisions, recorded in Decisions by the secretary; offer "Open in Decisions" to the secretary |

## H. A made-up community to design against

"Oakview" (no real association). Today is **Oct 12, 2099**. Roster by office: the president, the secretary (A. Secretary), the treasurer (A. Treasurer), one director (B. Director), the **vice president's office vacant**, and the manager (A. Manager). A. Owner is a member with no board office (refused). Kim Example is an administrator with no office. The governing documents are "Example Bylaws" and "Example Declaration"; sections are made up.

| Control | Family | State | The point it makes |
|---|---|---|---|
| Payment signers | money | adopted Sep 5 (decision 2099-09-05 #4, 5 to 0); in force Sep 20, the board's date; the treasurer and one other director above $2,500 (example), any two directors below | The main card; the effective rule on a bill-attach plan |
| Reserve withdrawals | money | suggested; floor two board members, Example Bylaws, 99.9(b) | A suggestion: bands 1, 2, 4, 5, 6, Propose |
| Manager spending limit | money | declined Aug 1: "the manager's limit lives in the management contract"; may be asked again after Feb 1, 2100 | Reason and date in band 3 |
| Payment countersign | money | retired Sep 5, replaced by Payment signers | History keeps it |
| Contract authorization | contracts | adopted Sep 5, in force Sep 20: a resolution on record before an officer signs | The step gate notice |
| Contract term check | contracts | proposed Oct 9 by A. Secretary, item `control-contract-term`, next meeting Oct 24 | The Work row in The board |
| Monthly review | reviews | adopted Oct 3, effective Oct 10; needs the treasurer and the vice president; the vice president's office is vacant | In force, cannot be satisfied: acts it governs are refused until the seat is filled |
| Delivery class | notices | adopted Oct 3, takes effect Nov 14 (the board's date): first class for notice letters | Adopted, not yet in force: date; the send notice before and after |
| Recorder | notices | deferred Oct 3; look again Jan 15, 2100 | Deferred, with the date |
| Second person, other kinds | onboarding | suggested | Built for onboarding answers; offered for other kinds |
| One signer for reserve withdrawals | money | **refused**; the floor is Example Bylaws, 99.9(b) | The refused row |
| Example Bylaws, 99.9(c) | money | a **question** | A provision jason cannot read cleanly |

Counts: adopted 4 (in force 2: Payment signers and Contract authorization; not in force 2: Monthly review for the roster, Delivery class for the date), proposed 1, suggested 2, declined 1, deferred 1, retired 1; one refused, one question (neither is a state). Sample plan: bill attach, 9 items, 2 over $2,500 (example) `payhoa-attach-bills`, one-person kind, effective rule two signers. Sample run: `control-adoption` for Contract term check, step 3 of 7 (the board decides), due Oct 24 `person`; a second, Monthly review, step 6 `blocked` on "the vice president's office is vacant". Sample send: a notice letter to 48 units; before Nov 14 the default is the printer's, after it first class.

Frames to draw: the list; Payment signers (the main card, all six bands); Reserve withdrawals (a suggestion with Propose and its `Confirm`); Monthly review (not in force, band 5 short); Delivery class (the date ahead); a declined card; the refused row and card; the amendment banner on Payment signers (Amendment 2, Oct 1, 2099); the three notices; the refusal on a plan when two directors are required and one is seated; the onboarding step, then "Not now"; the control-adoption run page at step 3 and at step 6; A. Owner refused; B. Director (a director) reading the same card as the secretary; an admin viewing as A. Secretary (controls replaced); the page at 320 px.
