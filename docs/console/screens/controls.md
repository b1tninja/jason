# Controls

A new screen, `#/controls`, in the Governance group · phase 3 · CLI `jason controls` and the loaders `controls`, `control`, `control-notices` and writer built; the screen is not · design: [../../controls.md](../../controls.md)

## In the console

None. The nearest are `#/documents` (the governing documents and their duties), `#/actions` (the board's items), `#/decisions` (the board's recorded votes), and `#/approvals` (where a two-person kind shows who must sign). None shows a safeguard the board chose, where it came from, or what it changes.

**This spec is the whole screen, as proposed.** The loaders to add are `controls` (the suggestions and the adopted controls) and `control` (`?key=`: one control, its provision, its history), over the control catalog and the profile's adopted controls (not built; [../../controls.md](../../controls.md), section 7). The screen reads. Its one write puts a suggestion before the board as a board item. Adopting, declining, and deferring are recorded in Decisions by the secretary; this screen shows the result.

## Purpose and personas

A board wants to know which safeguards its governing documents call for, which it has chosen to add, and what each one changes. jason suggests; the board decides.

- **Every director and officer:** reads all of it (directors and officers have the same access to information). Anyone may put a suggestion before the board.
- **Secretary:** records the board's decision on a control in Decisions, and sets its effective date.
- **Manager:** sees which controls bind their work (a spending amount, a second signer) and why.
- **Treasurer, president, vice president:** see the controls on money, meetings, and contracts, as their own landing pages link them ([office-views.md](office-views.md)).
- **Counsel:** reads a provision and a suggestion on grant.
- **Owner:** never.

## Data

| Part | Source | Loader |
|---|---|---|
| The controls | Each `Control`: `key`, `type` (title, family), `scope`, `parameters`, `state`, `basis` (the provision's citation and its words, whole), `floor` (what the law or a built-in rail already requires), `reading` (jason's, labeled), `touches[]` (the kinds, steps, and sends it changes), `proposedAs` (the board item id), `decision` (the decision id, the meeting, the vote as taken), `effective`, `inForce` (the roster check), `history[]` | `GET /api/controls` (`?family=&state=`) |
| One control | the same, with the provision's section outline and the statute beside it where the floor is the law's | `GET /api/control?key=` |
| The roster check | `Community.officers()` against the control's parameters: whether the people it names exist | in the control's `inForce` and `missing[]` |
| Where a control bites | The approvals engine's effective rule for a kind, a step's gates, a send's defaults | `GET /api/control-notices?subject=` (a plan, a step, or a send) |
| Put before the board | `jason.tasks.board_items.propose` with the provision as the item's evidence | `POST /api/write/controls/<key>` with `{act: "propose"}` (the signer's name enforced) |

The provision's words are recited from the stored text of the governing document, never typed. A provision jason cannot read cleanly is shown as a question, not a suggestion.

## Layout: the list

```
+------------------------------------------------------------------------------------------+
| Controls                                                         jason suggests; the board adopts |
| 3 adopted · 2 proposed to the board · 4 suggested · 1 declined · 1 adopted, not in force  |
+------------------------------------------------------------------------------------------+
| Filter: [All families v]  [All states v]                                                 |
+------------------------------------------------------------------------------------------+
| MONEY                                                                                    |
| Payment signers            ADOPTED · in force since Nov 14      Bylaws 99.9              |
|   The treasurer and one other director above $2,500; any two directors below.            |
| Reserve withdrawals        SUGGESTED                            Bylaws 99.9                |
|   The floor is two board members. jason suggests keeping it and naming them.   [Propose] |
| Manager spending authority SUGGESTED · the documents state no limit    [Propose]         |
| CONTRACTS                                                                                |
| Contract authorization     PROPOSED TO THE BOARD · item contract-authorization           |
| REVIEWS                                                                                  |
| Monthly review             ADOPTED · takes effect Dec 1 · the roster lacks a second director |
+------------------------------------------------------------------------------------------+
```

- Groups are the control families (money, contracts, reviews, notices, meetings, onboarding). Within a group: adopted first, then proposed, suggested, deferred, declined, retired.
- Each row: the title, the state in words and a glyph, the provision's citation, a one-line summary of what it requires, and, when it is a suggestion, "Propose". The provision's citation links to the card.
- The heading counts are the loader's. "Adopted" with a future date means the board adopted it and its effective date has not come; a warning says if the roster cannot satisfy it by then. From the effective date it is "in force" and binds.

## Layout: one control

```
+------------------------------------------------------------------------------------------+
| Controls > Payment signers                                  Adopted Oct 3 · in force Nov 14 |
+------------------------------------------------------------------------------------------+
| 1 THE PROVISION                                                                          |
| Bylaws 99.9  [Recitation: the words, whole]                                              |
| The floor: any two directors, or an officer and a director. The board may specify another manner. |
+------------------------------------------------------------------------------------------+
| 2 WHAT JASON SUGGESTED  [ReadingLabel: jason's reading, not the provision]                |
| Name the manner: the treasurer and one other director above an amount the board sets.    |
+------------------------------------------------------------------------------------------+
| 3 WHAT THE BOARD ADOPTED                                                                  |
| The treasurer and one other director above $2,500; any two directors below it.           |
| Decision 2099-10-03 #4 · moved, seconded, 5 to 0 · recorded by the secretary [Open]      |
+------------------------------------------------------------------------------------------+
| 4 WHAT IT CHANGES                                                                        |
| Payment plans (payhoa-attach-bills): second signer rule is now stricter than the kind's. |
| Reserve transfers: unchanged (the floor is higher).                                      |
+------------------------------------------------------------------------------------------+
| 5 CAN THE ROSTER SATISFY IT                                                              |
| Needs the treasurer and one other director: both seated.                                 |
+------------------------------------------------------------------------------------------+
| 6 HISTORY                                                                                |
| Oct 1 suggested by jason · Oct 2 proposed by A. Secretary · Oct 3 adopted · Nov 14 in force |
+------------------------------------------------------------------------------------------+
```

Six bands, always in this order, so the card reads from the document to its effect. A suggestion has bands 1, 2, 4, 5, and 6 and a "Propose to the board" button. A declined or deferred control shows its reason and date in band 3.

## The "required by a control" line (`ControlNotice`)

Wherever a control changes what a person must do, the screen says so, with a link: a plan ("Two signers required: a control the board adopted on Oct 3"), a workflow step ("A resolution must be on record before this step"), a send ("First class: a control the board adopted"). It is a one-line component shown at the point of the act. It is read-only, never hides a control, and names the control by title. It appears only to a viewer who may read the control (every board member). The server refuses the act whatever the page shows.

## Onboarding: "Controls jason suggests from your documents"

One step in the onboarding session ([onboarding.md](onboarding.md)), after the governing documents are ingested and their duties read: a card per family with the same rows as the list, "Take these to the board" (creates one board item that lists every suggestion with its provision) and "Not now". The step is never required; closing it records that the suggestions were seen, not that anything was adopted.

## Components

Built: `Card`, `Pill`, `Glyph`, `Recitation`, `ReadingLabel`, `Caveats`, `Confirm`, `DataTable`, `Evidence`, `Stamp`. To add: `ControlRow`, `ControlCard` (the six bands), `ControlStateWord` (a `Pill` preset for the six states), `ControlNotice`, and `RosterCheck` (what the control needs and what is seated).

## Actions

- **Propose to the board** (a `Confirm` that names the provision and says a board item will be created): creates or refreshes the board item and records who proposed it. It writes nothing else.
- **Open the decision, the board item, the provision, the approvals kind** are links.
- **Adopt, decline, defer, retire** are not here: they are the board's decisions, recorded in Decisions by the secretary; this screen reads them. "Open in Decisions" is offered to the secretary with the control prefilled.
- jason turns nothing on. A control is in force only from its effective date and only when the roster can satisfy it.

## States

- **No suggestions yet** (the governing documents are not ingested): "jason has not read your governing documents. Ingest them from Onboarding." with the link.
- **A provision jason cannot read cleanly:** the row is a question for the board or counsel, not a suggestion, with the provision's words and why it is unclear.
- **Adopted, effective date not yet reached,** and the roster cannot satisfy it: band 5 warns who is missing. **In force and the roster cannot satisfy it** (a seat fell vacant): acts that need it are refused with the reason, and the page says so at the top.
- **A provision changed since the control was adopted** (an amendment): a `ChangedBanner` on the card; the control stays as adopted and is flagged for the board.
- **A control that would go below a floor** is never shown as a suggestion; it is listed as refused, with the floor.
- **Loader fails:** the page says so with the reason; nothing is shown as adopted that is not.

## Privacy

- Directors and officers have the same access to information. The controls are the association's own rules (P1 for the titles and states; the provision's words are P0 where the document is). A control that names a person by office names the office, not the person.
- The roster check shows offices and counts, never a person's contact details.
- The owner view never reads `controls` (`OWNER_SOURCES` does not list it).

## Acceptance criteria

1. `GET /api/controls` signed out is a 401; a roster person without a board office is refused with `access.may_see`'s sentence; the owner view is refused.
2. A suggestion renders the provision's words from the stored text in a `Recitation` before jason's reading, and the reading is labeled "jason's reading, not the provision".
3. A suggestion never says it is in force. Only an adopted control whose effective date has passed shows "in force"; if the roster cannot satisfy it, the page says so and the acts it governs are refused, never relaxed.
4. "Propose to the board" creates a board item with the provision as evidence, in the signer's name, and changes no control's state to adopted.
5. A control that would loosen a floor is not offered; it is listed as refused with the floor named.
6. The "required by a control" line appears at the point of the act, links to the card, and the server refuses the same act with the control named.
7. An amendment that changes an adopted control's provision shows the `ChangedBanner` and does not change the control.
8. A declined suggestion shows its reason and the date it may be asked again.
9. No page, URL, or response carries a person's name, email, or address for an office a control names.

## Decisions for the user

1. **Where the page lives:** Governance beside Documents (recommended), or Setup.
2. **Who may propose:** any board member (recommended) or the secretary and president.
3. **Whether a suggestion appears before the documents' duties are confirmed by a person** (recommended: only after "duties read" is confirmed, so a misread provision is never suggested).
4. **Whether a refused loosening is listed** (recommended: yes, so the board sees why).
