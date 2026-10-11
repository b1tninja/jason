# Decisions

The Decisions screen, `#/decisions` (`?id=` one decision, `?meeting=` a meeting's, `?matter=` and `?outcome=` filters, `?run=` the decisions a run step asked for, `?record=KIND:ID` the form prefilled), in the Governance group · phase 2, before the specs that send a decision here are built · CLI: none today (`jason board --minutes DATE` quotes the store); `jason decisions` to add

## In the console

**Built** (checked 2026-10-11 in `ui/src/views/DecisionsView.tsx`, `src/jason/tasks/decisions.py`, `src/jason/web/sources.py`, `src/jason/web/app.py`):
- `#/decisions` (`DecisionsView`, nav roles officer and administrator) reads **only** `GET /api/agenda-plan`: the next meeting's candidates. Per matter: a `DecisionBrief` or a `BriefForm` (the question, criteria, options, facts; no recommendation), then a `DecisionCard` (motion as made, mover, second, `RollCall`, recusals, outcome in the board's word, "Recorded by" typed text, behind `Confirm`). A held executive candidate shows only `HELD_LINE`.
- It cannot show a past decision, a decision by id, or any filter. The hash is never read. `GET /api/decisions` (the `decisions` loader, P2: all, or `?meeting=`; an executive decision only in the private view, else `heldBack` and `executiveNotes`) is read by **no view**. It takes no `id`.
- `POST /api/decisions[/<id>]` (`write_decision`) records or changes one. `by` is typed text; nothing checks it against the signer or the office. `update` overwrites `motion`, `votes`, and the rest in place, and logs only an outcome change in `history`. `record` on a taken id re-records over it.
- The store has no field for the run, the step, or the matter. Its `kind` means a motion's form (`table`, `continue`, `refer`), not the matter. Outcomes are closed: `approved`, `denied`, `tabled`, `continued`, `referred` (`Outcome`).
- Readers already point here: `rule_records.links` emits `#/decisions?id=ID` routes that nothing opens; `workflows.readers.control_outcome` reads a decision by id (`approved` for adopted, `denied` for declined); `controls.effective.approved_decisions` gates a step on one.

**This spec adds** the record view (past decisions, one by id), the matter kinds, the run link, a signed writer, corrections as later entries, and a print for the minutes. The built plan layout becomes a tab. It records the board's decisions. It never decides, moves, seconds, votes, or declares a motion carried.

## Purpose and personas

The secretary records what the board did, in the board's words; every director and officer reads the same record, and the owning screens (controls, hearing, election, law review, monthly review, lien, claim) point here for the vote.

- **Secretary:** the recorder. Fills the form, links the run step, corrects an entry, prints for the minutes.
- **President, vice president, treasurer, director:** read everything the secretary reads (directors and officers have the same access to information). They do not record.
- **Manager:** reads; the minutes draft quotes these entries. Records none.
- **Counsel:** reads on grant. **Administrator:** reads; records as no one else. **Owner, reviewer:** no access.

## The law, recited

Words as stored in `data/authorities` (jason's consolidated text, not an official restatement); each is a `Recitation`, and every reading sits under a `ReadingLabel`.
- **CIV 4935(e):** "Any matter discussed in executive session shall be generally noted in the minutes of the immediately following meeting that is open to the entire membership."
- **CIV 4950(a):** "The minutes ... of any board meeting, other than an executive session, shall be available to members within 30 days of the meeting."
- **CIV 5673:** "The board shall approve the decision by a majority vote of the directors in an open meeting. The board shall record the vote in the minutes of that meeting."
- **CIV 4360(b), (c):** "A decision on a proposed rule change shall be made at a board meeting ..." "... not more than 15 days after making the rule change, the board shall deliver general notice ... of the rule change."

**Readings, labeled:** (1) The store records votes by director; "on their face the votes carry" (more ayes than noes among those voting) is a count, not the board's threshold. For a matter whose statute names a threshold, 5673's "majority vote of the directors" is not that count, so the line shows the ayes against the directors on the roster and the statute's words, and no verdict. (2) Whether a recused director counts toward a quorum is the bylaws' or counsel's (see `meetings-and-minutes.md`). (3) Procedure (what is in order, who may move, how a chair rules) is not jason's to decide: the screen has no check on it.

## Data

| Part | Source | State |
|---|---|---|
| Recorded decisions | `jason.tasks.decisions.load`; `as_dict` adds `tally`, `suggested` | Built; loader `decisions` (all or `?meeting=`). **Add** `?id=`, `?matter=`, `?outcome=`, `?run=`, `?item=`, paging |
| One decision | the same, plus `referencedBy[]` and `corrections[]` | **Add** `GET /api/decision?id=` |
| The next meeting's matters | `GET /api/agenda-plan` (`candidates`, `directors`, `decisions`, `evidenceRefs`) | Built (this is today's whole screen) |
| Directors on the roster | `board_members.current_names` (in `directors`) | Built |
| Part of run, and the steps this may answer | `GET /api/run-banner` (`banners[]`, `answers[]`) | To add ([run-links.md](run-links.md)) |
| What points at a decision | controls' act log (`decision`), the hearing row (`decisionId`), an election's `acclaimed` event, a law-review disposition, a monthly review's `ratified` act, a run step (`run`, `step`) | **Add**, one reader per store; each returns an address and a general label |
| Executive decisions | `is_executive`, `open_only`, `general_notes`; `meeting_room.private_view` (logged under `board/decisions.json`) | Built |

**Fields to add to `Decision`** (empty defaults; old rows read `""`): `matter` (a closed `DecisionMatter` word, below), `run` and `step` (per run-links.md, section 4: ids in a run id's shape, both or neither; the store imports nothing from `jason.workflows`), `corrections: list[dict]` (`{at, by, why, field, was, now}`). **Finding:** `Decision.id` is `<meeting>--<item or slug of the motion>`, so an executive decision with no item id carries a slug of its motion in its id, and the id goes in URLs, banners, and `referencedBy`. An executive decision's id must be `<meeting>--executive-<n>`.

## Matters and their words

The store keeps the board's **motion outcome** (the five words). The matter's own word, and what it sets in motion, stay in the owning store and are read there (one place for each fact; the hearing spec's decision 1). The screen shows both, never two copies. Match order and the closed set are rows, not code in the view.

| Matter (`DecisionMatter`) | The motion | Store outcome | Read on the owning screen | Extra the form asks |
|---|---|---|---|---|
| `control` | adopt, decline, defer, or retire a control | `approved`, `denied`, `tabled` or `continued` | adopted (effective date), declined (ask-again date), deferred | effective date; the control key |
| `rule-change` | adopt a proposed rule (CIV 4360(b)) | `approved`, `denied`, `continued` | adopted; adoption notice due 15 days on (4360(c)) | the rule change key; emergency is the board's determination, recorded as words |
| `hearing` (executive, `member_discipline`) | findings and the board's action (CIV 5855) | `approved`, `denied`, `continued` | findings; decision notice due 14 days on (5855(f)) | the findings, in the board's words; held |
| `election` | acclaim candidates; appoint the inspector; (if moved) receive the report | `approved`, `denied` | acclaimed (the elections store holds the decision id) | candidates named on the item |
| `law-review` | amend, ask counsel, or leave a provision (a conflict row) | `approved`, `referred`, `tabled` | the disposition and the board item | the conflict key |
| `ratification` | ratify a director's or subcommittee's review (CIV 5501) | `approved`, `denied` | the month's `ratified` act, the minutes link | the month |
| `contract` | authorize a contract or a limit (a control family) | `approved`, `denied`, `tabled` | the control gate reads `approved` by id | amount (integer cents), term; held if its subject is 4935(a) |
| `lien` | record a lien (5673: open, roll call); foreclose (5705(c): executive) | `approved`, `denied` | the delinquency run's step | the parcel number, never the owner |
| `claim` | file or pursue an insurance claim | `approved`, `denied`, `tabled` | the incident record | the incident id |
| `other` | any main motion; `table`, `continue`, `refer` are the motion's `kind` | any | none | none |

A matter with a statute-named procedure adds a **required-fields check**, a list of what is missing and never a verdict: `lien` needs every director on the roster accounted for (aye, no, abstain, absent, or recused), because the vote is recorded in the minutes. A director with no row reads "not recorded", never absent.

## Layout: the record

Three tabs: **Recorded** (default when `?id`, `?meeting`, or a filter is in the hash), **For the next meeting** (today's screen, unchanged inside), and **Record one**.

```
+------------------------------------------------------------------------------------------+
| Decisions    [Recorded] [For the next meeting] [Record one]          Print a meeting [..] |
| 14 recorded · Oakview Board · 3 in executive session held back (CIV 4935(e))             |
+------------------------------------------------------------------------------------------+
| Meeting [2099-03-10 v] Matter [any v] Outcome [any v] Run [any v]   Command: jason decisions |
|------------------------------------------------------------------------------------------|
| 2099-03-10  Quiet hours for the pool        rule-change  approved   5-0   [Part of run]  |
| 2099-03-10  Landscaping contract            contract     tabled     3-2                  |
| 2099-03-10  Executive session: litigation (CIV 4935(a)), 1 matter. Open the private view. |
| 2099-02-10  Reserve transfer ratification   ratification approved  4-0-1 recused 1       |
+------------------------------------------------------------------------------------------+
```

## Layout: one decision

```
+------------------------------------------------------------------------------------------+
| Decisions > 2099-03-10--item-7                    jason://decision/2099-03-10--item-7 [copy] |
| [list-checks] Part of run Rule change: quiet hours, step 13: The board decides · Open the run |
+------------------------------------------------------------------------------------------+
| 1 THE MOTION, AS MOVED   Board meeting 2099-03-10 · open session · rule-change            |
|   "Adopt the proposed quiet-hours rule as noticed."   [quote, the board's words]          |
|   Moved: A. Director · Seconded: B. Director                                             |
| 2 THE VOTE BY NAME       A. Director aye · B. Director aye · C. Director aye              |
|   D. Director aye · E. Director recused (disclosed an interest; not absent, not a no)     |
|   4 aye · 0 no · 0 abstain · 0 absent · 1 recused.  On their face the votes carry [count] |
| 3 THE OUTCOME            approved  [Stamp: the board's word]   Recorded 2099-03-10 by the secretary |
| 4 WHAT IT SET IN MOTION  Rule change: adopted · notice due by 2099-03-25 [LEGAL 4360(c)]  |
|   Referenced by: rules?key=quiet-hours · work/rule-change/run-3f9a01c2d4 step 13           |
| 5 CORRECTIONS            none. [Add a correction]                                         |
| 6 HISTORY                recorded · linked to run, step 13 · re-opened in the minutes     |
+------------------------------------------------------------------------------------------+
| Caveat (verbatim): A recorded decision is the record of what the board decided; jason changes nothing it decided. |
+------------------------------------------------------------------------------------------+
```

## Layout: the secretary's form (Record one)

The built `DecisionCard`, with the signer's name in place of "Recorded by", a matter picker, the extra fields of the matter, and the run link. Prefilled, never preset: `?record=control:KEY`, `?record=rule-change:KEY`, `?record=hearing:RUN`, an agenda item, or an open run step.

```
| Record a decision  · from: Controls > Payment signers (the proposal, not the motion)     |
| Meeting [2099-03-10] Matter [control] Session (o) open ( ) executive (subject: ...)      |
| Motion, as made [Adopt the payment-signers control, effective 2099-04-01]  [proposal text]|
|   [x] These are the words as moved, as amended if they were (required when prefilled)      |
| Moved by [A. Director v]  Seconded by [B. Director v]                                    |
| Vote by name: A. Director (aye|no|abstain|absent) ... Recused: [ ] A. Director ...       |
| Outcome, the board's word [approved v]    Effective [2099-04-01] (matter field)          |
| This decision answers: ( ) none  (o) Control adoption: Payment signers, step 6            |
| Recording as: Jane Example, secretary (the signed-in name; not editable)    [Record]      |
```

## Components

Built: `ScreenHeader`, `Tabs`, `DataTable`, `DecisionCard`, `DecisionBrief`, `RollCall`, `Stamp`, `Pill`, `Badge`, `Confirm`, `Caveats`, `RemoteView`, `Doc`, `Evidence`, `Command`, `Recitation`, `ReadingLabel`, `HeldNote`. To add: `DecisionList` (the filters and the held line), `DecisionRecord` (the six bands), `MatterFields` (a matter's extra fields from the table above), `PartOfRunBanner` and `AnswersStep` ([run-links.md](run-links.md)), `CorrectionForm`, `PrintMeeting`. `DecisionCard`'s "Recorded by" input is removed.

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Record the decision | `record` behind `Confirm`; `by` is the signer's name; only an office-holder secretary; checks the matter's required fields; nothing outward | No: the secretary's record | `jason decisions --record ... --by NAME` (to add) |
| Link a run step | `run` and `step` on the decision; the run reads it done at its next open ([run-links.md](run-links.md) section 4); `tabled` or `continued` leaves the step open | No | `jason workflow --attest RUN STEP --by NAME --outcome WORD --record decision:ID` (built) |
| Add a correction | appends `{at, by, why, field, was, now}` to a decision with an outcome; the entry stays as recorded | No | `jason decisions ID --correct ... --why TEXT` (to add) |
| Fill an open vote | edits a decision with **no outcome yet** in place (a draft) | No | as today |
| Print for the minutes | the meeting's open decisions, one minutes line each; browser print of `?meeting=DATE&print=1` | No | `jason board --minutes DATE` (quotes the store) |
| Open the owning screen, the run, the minutes | links | No | none |

**A correction is a later entry, never an edit.** Once an outcome is set, `update` refuses `motion`, `mover`, `second`, `votes`, `recused`, and `outcome`; `correct` is the way, and the page shows the entry as recorded, then each correction beside it with who and why (for example "the board corrected the minutes on 2099-04-14"). A re-record over a taken id is refused. There is no delete, no approve, no vote, no "carried", and no recommendation field.

## States

- **No decisions on record:** "No decision is recorded yet. The secretary records one after the board acts." Not "no decision was made".
- **A meeting with none:** "Nothing recorded for 2099-03-10." The held line (below) still shows.
- **Held (executive session):** outside the private view, the meeting's line is `general_notes` words only ("The board met in executive session to discuss litigation (Civil Code 4935(a))."), with a count. A decision with no subject is counted, not described.
- **`?id=` of a held decision:** the held line, no motion, mover, vote, title, notes, or run label. In the private view (P3, logged under `board/decisions.json`) the whole record opens under a "Confidential: CIV 4935" band.
- **`?id=` unknown:** 404, "jason holds no decision under this id."
- **A run link whose run is gone or refused:** "state not read here"; the decision still shows.
- **Run step not open, or recorder not the step's role:** the picker is absent, or the writer refuses with the engine's sentence, and nothing is recorded.
- **Vote open:** no outcome; the `Stamp` is absent and the badge reads "vote open".
- **Recused director:** "recused", never absent, never a no, never inferred; an unaccounted director reads "not recorded".
- **Changed since a run read it:** "changed since" ([run-links.md](run-links.md)), shown, never silently repeated.
- **Store unreadable:** "could not read decisions.json" with the reason; the plan tab still works.

## Privacy

- Open-session decisions are P2: names of directors, motions, votes. Directors and officers see the same fields. The owner view has no `decisions` source and no tab.
- Executive-session decisions are held in every open surface: this list, the id page, the print, the minutes draft, the Dock, the banner, the run label, and `referencedBy`. They go by the 4935 subject in the statute's words, never title, motion, item id, or a slug. `hearing` and `lien` decisions are always executive and carry the parcel or the opaque run id, never an owner's name or address.
- A URL carries a decision id or a run id, never a name, an email, or an address.
- Every opening of a held decision in the private view is logged in `access/served.jsonl`.
- The print never combines an open meeting's lines with executive material. An executive print is a separate page, marked confidential, available in the private view only.

## Acceptance criteria

1. `#/decisions?id=2099-03-10--item-7` shows that decision (a past meeting's) with its six bands; `?meeting=`, `?matter=`, `?outcome=`, and `?run=` filter the record; `GET /api/decisions` serves the filters.
2. The plan tab shows what `DecisionsView` shows today, and `planmeeting.test.tsx` and `boarddocs.test.tsx` still pass.
3. The form saves in the signer's name: a body `by` naming another person is a 403; a signer without the secretary office is refused with a sentence; nothing is recorded on a refusal.
4. Every director on the roster has a vote row; a recusal is stored as `recused` and not as a vote; a `lien` decision is refused until every director is accounted for.
5. A prefilled motion is labeled "proposal", and the form will not record it until the secretary confirms "These are the words as moved".
6. With a run reference, the decision completes the step at the run's next open once; `tabled` leaves it open; the page shows the "Part of run" banner and `PartOfRunBanner` draws nothing when there is no run.
7. After an outcome is set, an edit to the motion, the votes, or the outcome is refused; a correction is appended, and the page shows both.
8. Outside the private view, no executive decision's title, motion, vote, id, run label, or note is in the HTML, a URL, the print, or `referencedBy`; only the general words and a count. An executive id has no slug of the motion.
9. The "on their face" line never reads "carries" for a `lien` decision; it shows the ayes against the directors and 5673's words.
10. No control is labeled approve, carry, declare, adopt (as a verb the screen performs), decide, or vote. The statute blocks render before any `ReadingLabel`.
11. `jason verify-quotes` passes on the recited sections. Tests use "Oakview", "A. Director", and 2099 dates, and read no real record.

## Decisions for the user

1. **The default tab.** "For the next meeting" as built, until a decision is asked for by id (recommended, so nothing regresses), or "Recorded".
2. **A new `matter` field**, or derive the matter from `referencedBy` (recommended: the field; a derived kind misreads old rows and an unlinked decision).
3. **Where a matter's own word lives.** The five outcome words in Decisions and the matter's word (adopted, declined, deferred) in the owning store (recommended), or add a `disposition` field here.
4. **Who may record.** The secretary only (recommended); or also an acting recorder the board names at the meeting, recorded as such in the entry. Without an acting-recorder rule an absent secretary leaves no one to sign.
5. **When an entry becomes a record.** At the moment an outcome is set (recommended), or at the next meeting that approves the minutes.
6. **Corrections.** Append-only entries as above (recommended), or keep in-place edits with a full history.
7. **The "on their face" line.** Replace it, for any matter whose statute names a threshold, with the count against the roster and the statute's words (recommended).
8. **An election's receiving the report.** The elections spec has no board vote for it, only a second person's confirmation; keep the matter to acclamation and the inspector's appointment (recommended) or add a vote.
9. **A deferral is a decision.** The control-adoption check treats a deferral as "nothing decided". Record a deferral here as `tabled` or `continued` with a date, or as no entry.
10. **The print.** A browser print of the open decisions (recommended), or a Doc made from a template, which is a send and goes through Approvals.
11. **The executive id fix.** Change the id for a new executive decision to `executive-<n>`; old rows are left as they are, since they are the association's records.
