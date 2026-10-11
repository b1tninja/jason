# Collect items

A tracker used inside a run, not a route of its own: the step panel of a per-item collect step at `#/work/<definition>/<id>?step=ID` (the `?item=` opens one), and the Collect tab of a packet at `#/disclosures/packet/<year>?tab=collect` · phase 2, after the run store and the packet's run files · CLI: `jason packet annual-disclosures --year Y --collect` (to add)

## In the console

None. The nearest are `#/duties` (a role's tasks and deadlines), `#/followups` (dated actions on a campaign), and the Work screens ([work.md](work.md)), whose step panel shows a `person` step as one line. None keeps a list of things asked of people, each with its own date, state, and what came back.

**This spec is the whole tracker, as proposed.** It is general: any run with a step that gathers inputs from people uses it. The first user is `fiscal-year` step D3 "Collect figures and files" ([../../workflows/money.md](../../workflows/money.md), section 2.5), whose list is the annual packet's collection list ([../../annual-disclosures.md](../../annual-disclosures.md), 5.5). The packet tab's `CollectList` and `CollectItemRow` ([../handoff-annual-disclosures.md](../handoff-annual-disclosures.md)) are this tracker with the packet's wording.

**What is built.** The run library `jason.workflows` (types, store, fold, resume check, step-kind contracts) is built and has per-item steps: a step with `repeat=PER_ITEM` carries item states, and an act on it must name the item. Packet planning and `--values` exist (`jason packet annual-disclosures --year Y [--values]`, `jason.tasks.packets.values_for`). `schedule_assignments` (a role's proposed or adopted tasks) and `jason followups --add` exist.

**What is to add.** Everything else: the item store (`collect.json`; neither `jason.tasks.annual_packet` nor a collect-items module exists), the `--collect`, `--give`, `--file`, `--waive` flags, the loader `annual-collect` and a general `collect-items` (`?run=`), the writes, the components, and a `jason workflow` command and Work loaders. **A gap in the library:** a run's items are fixed in its `opened` event (`fold.py` reads `detail.items` there only), so an item found after the run opens cannot be added. Decision 1.

## Purpose and personas

A run that needs a figure, a file, or a statement from a person keeps one line for each: who was asked, when, by what day, what came back, and who confirmed it. Nothing is assumed present. An item that is not received is waiting; an item that is waived is waived, with a reason, and is never counted as present.

- **Manager:** makes the list from the plan, records who was asked, enters what arrives, and sends the asking by their own means (jason sends nothing).
- **Treasurer:** gives the figures; confirms what the manager enters.
- **Secretary:** enters the board's statements as the board adopted them; records the meeting.
- **Director, president, vice president:** read the whole list; a director reads what an officer reads at the same level; confirm where the item names their office.
- **Administrator:** repairs the list; decides nothing on a person's behalf.
- **Counsel:** reads the list and its history on grant. No act.
- **Owner, reviewer:** no access.

## Data

| Part | Source |
|---|---|
| The items of a run | `jason.tasks.collect_items.items(data_dir, run)` (to add): each item's acts, folded, the latest word on each question winning |
| The packet's list | `GET /api/annual-collect?year=` (proposed in the handoff): `items[]`, `standing[]`, `confirm[]`; this tracker takes `items[]` |
| The run and its step | `jason.workflows.api.show`: the step's `items` (each with its state), `clocks`, `links` |
| Who it is asked of | `schedule_assignments`: a role, with `assignment: adopted DAY` or `proposed, not adopted` |
| The window and outer edge | `Timing.window(Anchor.FISCAL_YEAR_END)` through the notice catalog; the statute's words by `Recitation` |
| A file received | a library address (`library:4002`) read as a `Doc`; the digest is the file's sha256, taken when it was attached |
| A board statement's adoption | read from the decision record or the minutes, never typed |
| Reminders | `jason.tasks.followups` rows, linked by id |

**An item** (store `collect.json` in the run's folder, append only, under the store lock `jason.locks`):

```json
{"id": "c-02", "what": "Example reserve summary pages", "kind": "file", "answers": ["CIV 9901(b)(2)"],
 "from": {"role": "treasurer", "assignment": "proposed, not adopted"},
 "acts": [
  {"act": "listed", "by": "jason", "at": "2099-02-20T09:00:00+00:00"},
  {"act": "asked", "by": "A. Manager", "at": "2099-02-20T09:10:00+00:00", "whom": "A. Treasurer", "how": "email", "note": ""},
  {"act": "due", "by": "jason", "day": "2099-04-20", "basis": "proposed policy", "why": "the last day it can arrive and leave the days the next stage needs"},
  {"act": "given", "by": "A. Manager", "at": "2099-03-01T10:00:00+00:00", "file": "library:4002", "sha256": "9e2f4b7c1d0a...", "source": "the study summary, pages 3 to 5"}],
 "state": "received"}
```

`kind` is a closed set: `value` (text), `amount` (integer cents, shown as `$61.20`), `date`, `file`, `statement` (the board's words), `standing` (a value kept from last year, asked "still true?"). `state` is folded, never stored by hand: `not asked`, `asked`, `received`, `confirmed`, `waived`. A correction is a later `given` act; the earlier value stays in the history.

## Layout

```
+------------------------------------------------------------------------------------------+
| Collect: figures and files                  fiscal year 2099 · run 2099-fy · step D3     |
| 6 items · 2 not asked · 1 asked · 1 received, awaiting a person · 1 confirmed · 1 waived |
| Outer edge: window closes May 31, 2099 [LAW]   Items due by Apr 20 [PROPOSED]            |
+------------------------------------------------------------------------------------------+
| Filter: [All states v] [Asked of v]                                   [List the items]   |
+------------------------------------------------------------------------------------------+
| Item                       Asked of · on · how       Due by            State             |
|------------------------------------------------------------------------------------------|
| Example reserve summary    A. Treasurer              Apr 20            ASKED             |
|  CIV 9901(b)(2) (3)        Feb 20 · email            [PROPOSED]        asked 28 days ago |
|                            role proposed, not adopted                  [Record it] [Waive]|
| Example insurance terms    A. Manager                Apr 20 [PROPOSED] RECEIVED          |
|  CIV 9901(b)(9)            Feb 20 · in person        past due 3 days   awaiting a person |
|                            file: declarations-example.pdf  9e2f4b7c1d0a  by A. Manager   |
|                            source: the policy's declarations page   [Confirm] [Correct]  |
| Example board statement    A. Secretary              Apr 20 [PROPOSED] CONFIRMED         |
|  CIV 9901(b)(4)            Feb 20 · in meeting       entered by A. Secretary; not yet    |
|                            adopted (no act on record; minutes searched)                  |
| Example posting place      A. Manager                -                 WAIVED            |
|  CIV 9902(a)(3)            waived by A. Manager, Mar 2: "does not apply this year (see   |
|                            the applicability answer)". The element reads waiting.        |
| Example mailing day        (not asked)               Apr 20 [PROPOSED] NOT ASKED         |
|                            [Record who was asked]                                        |
+------------------------------------------------------------------------------------------+
| Row opened: HISTORY  listed Feb 20 jason · asked Feb 20 A. Manager · due Apr 20 (policy) |
|  · given Mar 1 A. Manager (value kept, replaced by the next line) · given Mar 4 ...      |
+------------------------------------------------------------------------------------------+
| Entering an item records what a person says; it adopts nothing and sends nothing.        |
+------------------------------------------------------------------------------------------+
```

- Grouped by the person asked, then by due day, a legal edge before a proposed one, an item with no day last. A state is a word and a `Glyph`, never colour alone. A table twin carries every column.
- **Due by** is a `DueDate` with its **clock basis word** beside it: `LAW`, `DOCUMENTS`, `COUNTERPARTY` (a day the other party stated), `PROPOSED` (jason's computed day, the board's to adopt, never a stamp), `PERSON` (a day someone set). The page words the item's day as "the last day it can arrive and leave the days the next stage needs" and never as a legal deadline.
- "Past due 3 days" is a word beside the date, not a seventh state (decision 2). It counts from a day the loader sends; the page counts nothing.
- A waived item never renders as present, done, or "n/a" alone: it reads "waived by NAME on DAY: REASON", and the line for the element it answers says what the element reads now (waiting, or does not apply through its applicability answer).

## Components

Built (checked in `ui/src/components`): `DataTable`, `Card`, `Pill`, `Glyph`, `DueDate`, `Doc`, `Confirm`, `ConfirmList`, `Command`, `Seal`, `Recitation`, `ReadingLabel`, `Timeline`, `Findings`, `Caveats`, `Stat`. Proposed elsewhere and not in the folder: `TerminalStep`, `AgeStamp`. To add: `CollectTracker` (the list, the filters, the heads), `CollectItemRow`, `StateWord` (a `Pill` preset for the five states), `BasisWord` (the five clock bases; shared with `BasisPill` in [work.md](work.md)), `GiveForm` (the entry behind `Confirm`), `WaiveForm`. `StandingValueRow` for a `standing` item is in the handoff.

## Actions

Every write is a `Confirm` that spells out what is recorded and in whose name, behind the write guard, and names its CLI. A body `by` naming someone else is a 403; an admin viewing as someone else cannot act. A write with no `by` is a 400.

| Control | Does | CLI (to add) |
|---|---|---|
| List the items | Makes the list from the plan's waiting elements; adds none twice (the id comes from the element and the part) | `--collect` (prints), `--collect --make --yes` |
| Record who was asked | `asked`: whom, on what day, how (a word: email, in person, call, letter, form). Records that a person asked; jason asks no one | `--ask ID --whom NAME --how WORD --by NAME` |
| Set or change the due day | `due`: a day and its basis. Below a legal edge or outside the window, refused with the sentence | `--due ID --day D --basis WORD --by NAME` |
| Record it (`given`) | A value, an amount in cents, a date, a statement, or a library file; with its **source** (required) and the file's digest | `--give ID --value TEXT --source TEXT --by NAME`, `--file ADDRESS` |
| Confirm | A person reads what was entered and says it is the thing asked for. Confirmation by a person other than the enterer is the proposal (decision 3) | `--confirm ID --by NAME` |
| Waive | `waived` with a reason (required). Never "present". A legal element's waiver is also recorded as a finding for the board | `--waive ID --reason TEXT --by NAME` |
| Reopen | A later act: a confirmed or waived item is asked again, with a reason; the history stays | `--reopen ID --reason TEXT --by NAME` |
| Remind me | A follow-up row linked to the item (`jason followups --add`); a command to copy, not a send | `jason followups --add --date D --text TEXT --by NAME` |

Confirming or waiving an item also appends an `attested` event for that step and item to the run, in the same request: the tracker is written first, then the event, and the answer carries `run: {ok: false, why}` if the event fails (the deficiency register's rule). The run's per-item step is done when every item is confirmed or waived.

## States

- **No run, or no list yet:** "No items are listed for this run. `--collect --make` lists them from the plan."
- **Nothing to collect:** "The plan found no element waiting on a value or a file."
- **All confirmed or waived:** "Every item is confirmed or waived. A waiver is not a finding that the element is present."
- **A date not on record** (no fiscal year end, no dated day): the due day reads "date not on record", a question, never a guess.
- **Role not adopted:** "Asked of the treasurer (proposed, not adopted by the board)."
- **Late for the window:** the word "past due N days" beside the date, with the sentence "must arrive by Apr 20 to leave the days the next stage needs".
- **A store moved under a confirmed item** (the file changed): the item reads "changed since confirmed", with the old and new digest; the resume check opens a `changed` event.
- **A board statement:** "entered by NAME; not yet adopted", or "adopted at the meeting of DAY (recorded by NAME)" read from the decision record. The page has no control that adopts.
- **Loading, store unreadable:** a skeleton; "could not read collect.json" with the loader's reason; the run is not marked failed.

## Privacy

- The list is P1 (roster people): item names, roles, days, and states. A value entered is P1 and labeled draft until the packet is sent. A file keeps its own level: a P2 or P3 file shows by kind and title only outside the level that opens it, and the tracker never displays its text.
- Directors and officers have the same access to information; a director reads what an officer reads at the same level.
- A free-text field (a source, a reason) refuses an email address or a phone number, as the deficiency register masks them. A person's name appears as the one who asked, entered, or confirmed.
- A URL carries a run id, a step id, and an item id, never a name. No `/api/file` link, no absolute path.
- Owner view and reviewers: refused.

## Decisions for the user

1. **Items added after the run opens.** The library fixes items in `opened`. Either D3 becomes a child run opened after D2 (its items known then), or the library gains an `items-added` event. Recommended: the child run, with no engine change.
2. **"Late" as a state or a word.** Recommended: a word beside the date (the handoff's decision 5).
3. **Who confirms.** A different person from the enterer, or the enterer may. Recommended: different, as proposed policy for any figure that goes into a disclosure, and labeled so.
4. **A file arrives how.** Attach a file already in the library only (recommended), or accept an upload here. Upload belongs to record intake.
5. **Where the store lives.** The packet's own `data/packets/<packet>-<year>/collect.json`, with the general tracker reading any run's `collect.json` (recommended), or one store for all runs.
6. **The secretary's part.** Whether a board statement is entered by the secretary only, or any officer.

## Acceptance criteria

1. Listing twice adds no item; an item's id is stable.
2. Every date shows a basis word; a proposed day never renders as a stamp or as the law's.
3. A waiver without a reason, a `given` without a source, and a due day outside the window are refused with a sentence, and nothing is written.
4. A waived item is never counted as present anywhere on the page or in the packet's checklist; the element it answers reads waiting or does not apply.
5. Confirming and waiving write the tracker and the run's event; if the event fails the answer says so and the tracker stands.
6. A correction keeps the earlier value in the history.
7. A body `by` naming someone else is a 403; an admin viewing as someone else cannot act; a write with no `by` is a 400.
8. A director sees the same list an officer sees; the owner view and a reviewer are refused.
9. A file's digest is shown (first twelve characters); a file changed since confirmation shows "changed since confirmed".
10. The page sends, mails, files, and asks no one. Reminders are commands or follow-up rows a person adds.
11. The tracker works for a second definition with no change to its code (a made-up "Example run" with three items).
