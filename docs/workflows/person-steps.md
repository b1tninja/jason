# Person steps: how a workflow enables, reminds, and guides the person

Status: **design, with phase 1 built** (2026-10-11): the `Support` record and its validators (section 4), the enable states and the claim note (section 5), the guide (section 7), and the read side of the reminders (section 6: the bands, and `jason workflow --due`). Section 9 says what is built and what is not; section 9.1 records how phase 1 was built and the calls it made. Sections 3 and 5 to 8 say, for each point, what the definitions and the Work screens already hold and what is new. The inventory of every person step is generated: [person-steps-inventory.md](person-steps-inventory.md) (`scripts/gen_person_steps.py`). The screen is [../console/screens/work-guide.md](../console/screens/work-guide.md); the brief for the design agent is [../console/design-brief-person-steps.md](../console/design-brief-person-steps.md). The model underneath is [../workflows-design.md](../workflows-design.md); the engine is [../workflows-engine.md](../workflows-engine.md).

## 1. The problem

A workflow's check, job, and plan steps are jason's: it reads, queues, and plans. Its **person steps** are a human's: an act jason cannot do (mail, a call, a link opened as an owner, a form read and confirmed, a decision in another system) and the board's decisions the secretary records. They are most of the work. When the inventory was generated there were 438 of them across 52 definitions, 329 with a command, 69 with a legal clock, and 88 that repeat per item. Today a person step is a title, one `why` sentence, a command string, a record to name, and a clock. That is enough for the person who wrote the definition. It is not enough for the manager who meets the step for the first time in March, or for a director who covers the secretary for a month.

Three promises, each a section below. For every person step the workflow must:

1. **Enable** the person: say who may do it, whether *this* person can do it *now* (their office, the data level, a second person, an integration, the record they need in hand, the terminal), and if not, who can and what is missing.
2. **Remind** the person: put the step in front of the right people at the right time, quietly, without jason sending anything on its own initiative.
3. **Guide** the person: say what to do in plain words, what to look at, the rule it rests on (recited, with the reading labeled), the exact command, what done looks like, and what to do if blocked or if the step does not apply.

## 2. The rules that run through all three

- **jason sends nothing on its own.** Every reminder is a reading that appears when a person opens a screen, runs a command, or reads the digest. No email, message, text, calendar invite, or Google Task is made by a clock. The one outward form, a reminder email *draft*, is a plan a person asks for under a control the board adopted, saved to Gmail Drafts, and sent by a person (section 6.7). This follows the standing rule that the console may save Gmail drafts and never send.
- **Quiet by default.** Nothing is shown to a person that is not theirs to do, close to its date, or past it. Reading a nudge never silences it; acting does. A legal date never snoozes.
- **A number that no law or document sets is proposed policy.** The lead time, the "open a while" threshold, and the escalation delay below are proposals with a label, adopted by the board like a control (section 6.8). Until adopted they are defaults, shown as "proposed, not the law's", never as a stamp.
- **The rule is recited, the reading is labeled.** A step that rests on a statute or a document recites the operative words from the stored text, then jason's reading follows and is marked as a reading (AGENTS.md, "Recite the rule; label the reading"). A cite the shelf cannot resolve shows "the words are not on the shelf here" and never a paraphrase.
- **Directors and officers have the same access to information.** Guidance, evidence, and nudges differ by *duty* (whose step it is), never by what a board member may read. A director reads the same step panel an officer reads at the same level.
- **Held and executive matters show general words only** outside the private view (section 8).
- **Guidance is general.** It names kinds, topics, and questions, not an association's facts and not figures that belong to a cite (the prompts-name-kinds rule). Every example in the docs is made up ("Oakview", "A. Owner", 2099 dates).
- **Authority.** A definition is jason's procedure, the lowest authority. Guidance that conflicts with a rule or the law is corrected in the definition and the lesson is recorded; it never settles an open question case by case (AGENTS.md, "Where the law is silent, write it down").

## 3. What a person step has today

Verified against `src/jason/workflows/types.py`, `defs/`, `jason.web.extra.work`, and `ui/src/components/RunStepPanel.tsx`.

| Need | Field or surface that exists | What it gives | What it lacks |
|---|---|---|---|
| Plain words | `title` (always); `why` (one sentence, with the lesson or statute in its prose) | what the step is and a reason | an instruction in the imperative; the reason and the lesson are one string |
| Who | `role`, `roles` (several offices may act), `acting_roles`; `Role.ANYONE`; the run's owner | which offices; `yours` and `waitingOn` on the run JSON; "Waiting on the NAME/OFFICE" | who *holds* the office this week; a backup; an absence |
| Whether the viewer can act | `yours`, `acts` / `notOffered` per act with a sentence, `notice` (a control that binds), `ACTING_REFUSED` for an admin viewing as someone else | the act is offered or refused, with the reason | what is missing when it is not offered: an integration, a second person, the terminal, a record in hand |
| The command | `command` (one string; may carry alternatives and "then") | shown with Copy; never run by the page | an ordered list; placeholders filled from the run; which are terminal-only |
| What to look at | `evidence` (store addresses a *done* step is compared with); `check` on a SOP step | the "changed since" baseline; chips | a reader for the *before* view: the five rows, the count, the age |
| The record | `record` (what an attestation must point to); `needsRecord` | the Mark done dialog refuses without it | what *done looks like* in words |
| The rule | `clock.cite` (a law clock only); statutes named in `why` prose | a law clock recites in the clocks strip (`Recitation`, `ReadingLabel`) | a cite on a step that has no law clock; a labeled reading per step |
| The procedure and lessons | `sop` (`key#N`); `Procedure.Step` has `do`, `command`, `check`, `refs`, `lessons`, `person` | the address; the procedure step carries its own check, readings, and lessons | the panel does not read them; the inventory's SOP column shows which carry what |
| Leaving a step | `skip` (`SkipRule`), `na` (`NotApplicable`: roles, reason, record), `legal` (no skip) | the acts and who may do them | words for *when* it does not apply; what to do when blocked; who to ask |
| Dates | `clock` (`ClockDef`: slot, days, basis, cite, label, business days, per item); `DateSlot` (`late`, `timing`, `roles`, `settable`); `date-set`; `dateSlots` and `openSlots` on the run JSON | clocks computed by the fold; a slot set after the start | nothing reminds anyone that a slot is unset or that a step is late |
| Nudges | the digest (`jason attention`: LEGAL, OVERDUE, due soon, open, noted); the dock's deadlines and `mine` counts; the follow-ups (`jason followups`); `signedWaiting` on the office bands; the Work list's four groups; Today's "Your work" band (specified in [today.md](../console/screens/today.md)) | clocks and waiting counts for other systems | a line for a *workflow step*; escalation; an absence; a snooze; a person-run list |

What is built around it: the Work loaders and writer, `RunStepPanel` (why, look-at chips, command, Mark done, skip, note, na), `OfficeLens`, `StartRun` (all in `ui/src`). This page extends them; it does not replace the rule that **the run page embeds reads and links writes** ([work.md](../console/screens/work.md), "Where a step's work happens").

## 4. The guidance record

One optional record on a step, `StepDef.support: Support | None`. A step with none keeps working: every field below has a derivation from what the step already holds (the third column), so the panel is never empty and authoring is gradual. All three parts are frozen data, in the definition, like a rule row; none names an association.

```python
@dataclass(frozen=True)
class Support:
    enables: Enables = Enables()
    reminds: Reminds = Reminds()
    guides: Guides = Guides()
```

### 4.1 `Guides` (the words and the evidence)

| Field | Holds | Derived when absent | Rule |
|---|---|---|---|
| `instruction` | what to do, in one or two plain sentences, imperative, no jargon | the SOP step's `do`, else `title` | No figure that belongs to a cite; no name; no section number (the cite carries it). |
| `why` | already there (`StepDef.why`), kept to one sentence | itself | The lesson and statute move out of the prose into `lessons` and `cites`; old prose keeps working. |
| `look_at` | `tuple[LookAt]`: `LookAt(label, read, args)`; `read` names a registered **guide read** | the step's `evidence` addresses as chips, and the SOP step's `check` text as "Check before going on" | A guide read is read-only, like a `check`: `read(readers, run, step) -> Looked(count, rows[:5], refs, as_of, unavailable="")`. A read that cannot read says so; it never returns "nothing to look at". Rows are at the viewer's data level; a list row never carries a contact detail or an answer. |
| `checklist` | `tuple[Check]`: `Check(text, required=False)` | the SOP step's `check` as one unticked line | An item is one line, one thing to look at or do. A `required` item must be ticked before Mark done and the attestation records "checked: 4 of 4". Ticks are the viewer's; an unrequired tick is a browser convenience (not run state) and is never an attestation. |
| `commands` | `tuple[Cmd]`: `Cmd(text, note, terminal_only=False)` | `StepDef.command`, shown as written | Placeholders (`NAME`, `KEY`, `RUN`, `ID`) are filled from the run and the signed-in name when known, so Copy copies the filled line; one not known stays upper case and is marked "fill in". The page never runs a command. `terminal_only` says why the command cannot run anywhere else ("a mailed letter is applied only at the terminal"). |
| `lessons` | lesson keys (`jason.community.lessons`) | the SOP step's `lessons` | Validated: each key exists. Shown with its status; an open lesson in the step's area is shown as such. |
| `cites` | `tuple[Cite]`: `Cite(key, reading="")`; `key` is a shelf key (`CIV 9999(a)`) | the clock's `cite`, if a law clock | Validated like a law clock: the section resolves on the authorities shelf (a missing shelf is a skip). A cite does not make a step legal; only a law clock does. The panel recites the words in force on the run's relevant date, then the `reading` under a `ReadingLabel` ("jason's reading", or "the board reads this to mean" where the board has adopted one). No `reading` is allowed; the words alone are then shown. |
| `done_when` | what done looks like, in words | `record` as "Done when you can point to: RECORD" | A test a person can make: "every form listed as new has been read", not "the step is finished". |
| `blocked` | what to do when the step cannot be done now | a standing sentence: leave a blocked note, name what is needed and from whom | Names the thing, not a person. |
| `not_applicable` | when this step does not apply | none (shown only where `na` is declared) | Words for the `na` outcome (roles, reason, record are already there). A step with no `na` and no skip says so plainly. |
| `ask` | `tuple[Role]`: offices to ask about this step | the step's own roles, then the escalation office | Offices, never names; the panel resolves them against the roster. |

`lessons`, `cites`, and `look_at` are what lets the panel replace "see lesson x in the why prose" with a link and a recitation.

### 4.2 `Enables` (can this person do it now)

| Field | Holds | Derived when absent |
|---|---|---|
| `in_hand` | `tuple[str]`: what to have open before starting (a document, a login, a number to key) | none |
| `integrations` | keys of `jason.integrations` the step needs signed in (`payhoa`, `google`, `zoom`, and so on) | none; the command text is not guessed at |
| `access_note` | one sentence when the step needs more than its role says | none |
| `second_person` | whether a different person must confirm (a control or the step's kind says so) | read from `controls.effective.step_gates` |
| `terminal` | whether the step is done only at a terminal | true when every `Cmd` is terminal-only, or the kind is a terminal-only approvals kind |

The **level** a step touches (P0 to P3) is *not* declared: it is the level of the stores its `look_at` reads and its evidence addresses, as `jason.web.access` decides. The role that may act is `role` and `roles`; the level that may read is the viewer's.

### 4.3 `Reminds` (when, to whom, how loud)

| Field | Holds | Default (proposed policy; board-adoptable) |
|---|---|---|
| `lead_days` | days before the step's clock that it enters "due soon" | 14 (the schedule's two weeks) |
| `after_hours` | hours a step may sit `needs a person` before it shows as "open a while"; for a step with no clock | 168 (7 days) |
| `escalate_to` | the office that also sees the step when it is late | from the escalation table (section 6.5) |
| `escalate_after_hours` | hours past the late point before the escalation office sees it | 72; **0 for a legal clock** |
| `snoozable` | whether the holder may snooze it | true; always false for a legal step |
| `per_item` | one line for the step with a count, or one per item | one line with a count |

A step's *due date* is its `clock`; `Reminds` never carries a date of its own. A step with no clock has no "due soon" and no "late": it can only be "open a while", and the inventory lists those (code `time`) for the author to decide whether a clock exists.

### 4.4 What the validator adds

`definitions.validate` refuses: a `cite` the shelf does not resolve; a `lesson` key that does not exist; a `look_at.read` that is not registered; a `Cmd` placeholder that is not one of the known four; a `Reminds` field below its floor (`lead_days` below 0, `escalate_after_hours` above zero on a legal clock, `snoozable` on a legal step); an `escalate_to` that is not an office (`jason`, `scheduler`, `anyone` are not offices); a `required` checklist item on a step that has no `record` and no `done_when`; a `Support` on a step that is not a person, decision, or note-ended wait (a check, job, or plan has no person to guide); and, on a held definition, guidance text with an `@`, or on a `public_title` step a digit. A step may not have more than eight checklist items or three `look_at` readers (the panel is a place to act, not a report).

## 5. Enable

### 5.1 Who is the person

A role is an office; an office is held by a person the roster names. Resolution, in order:

1. **The holders** of every office in `acting_roles`, from the roster (`Community.officers()`). One person may hold two offices; two persons may hold `director`. All holders of an acting office are "the person" for nudging; the first to act completes the step.
2. **`anyone`** is any signed-in person; for nudging it means the **run's owner** (set at start: "who is the manager for this run"), never everyone.
3. **The run's owner** is also shown every step of their runs, quietly, in "Waiting on others", whoever holds the step.
4. **A claim** (section 5.4) names the one person who said they are on it. It reorders what the others see; it grants and removes nothing.
5. **A backup** (section 5.5) stands in for the nudge when the holder is away or the office is vacant.

A vacant office (the roster names no one) is a finding, not an error: the step reads "No one holds the secretary office", the escalation office sees it at once, and the board's item is proposed, not made.

### 5.2 Can this person do it now

The step panel shows one **enable state**, the first that applies, in this order. Each has fixed words (the screen spec lists them).

| # | State | When | What the person is told |
|---|---|---|---|
| 1 | `done`, `skipped`, `not applicable` | the step is over | who, when, and the record; "Reopen" where allowed |
| 2 | `held` | a held run outside the private view | the general title only; "Open the private view to see this run." |
| 3 | `viewing as` | an administrator viewing as someone else | "Viewing as NAME (admin view): go back to yourself first." |
| 4 | `paused`, `draft` | the run is paused or not yet opened | the run's reason; no clock runs |
| 5 | `not yours` | the viewer holds none of the acting offices | "Waiting on the NAME/OFFICE", who holds it, and who to ask; the step's instruction and evidence are still readable |
| 6 | `not ready` | a `needs` step is open or failed | "Waits on step N: TITLE" with a link |
| 7 | `needs an integration` | `integrations` names one that is not signed in | which one, by name, and the `jason` command or screen that connects it (names only; never a credential) |
| 8 | `needs a second person` | a gate or the kind requires a different confirmer | who may be the second (an office, from the roster); the first act is recorded as a note and the step stays open |
| 9 | `terminal only` | every command is terminal-only | the command with Copy; "A person applies this at a terminal." No Mark done button is drawn before the record exists |
| 10 | `ready` | none of the above | the Mark done control, with the record field the step asks for |

A step that is `not yours` still **shows its instruction**: a director covering for an absent officer, a counsel reading on grant, and a manager planning the week need the words even when the act is not theirs. A control the board adopted that binds the step shows "Required by a control the board adopted on DATE" (already built as `ControlStepNotice`).

### 5.3 Access and the data level

The server decides, as for every write: the signed-in person's offices against `role` and `roles`, and the data level against what the step reads. The page never hides an act the viewer's offices do not hold; it shows it, disabled, with the reason ([office-views.md](../console/screens/office-views.md), "A control the viewer's offices do not hold is shown, disabled"). A body `by` naming someone else is a 403. Directors and officers read the same panel.

### 5.4 Claiming a step

Two people each think the other has it. A **claim** is a note on the step, `{claim: true, by, at}` (an existing `note` event; no new event kind): "A. Manager is on it since Oct 9." It is not an assignment: it grants no standing, blocks nobody, and any holder may still act. It changes what the others see (the claimant's name on the line, the step quiet in the others' bands) and ends when the step ends, when its maker releases it, or after the "open a while" threshold passes with no act, when it reads "claimed Oct 9, still open". `jason workflow --claim RUN STEP --by NAME [--release]`.

### 5.5 Absence, vacation, and handoff

An office goes away; the steps do not wait.

- **Recording it.** The holder (or an administrator on their behalf) records `jason workflow --away --office OFFICE --from DATE --until DATE --by NAME [--cover OFFICE]`; the console has the same as a small dialog on the office view. It is an append-only log under the store lock, `data/workflows/away.jsonl`, keyed by **office**, never a reason, never a place. The log is private data, not checked in. `--away --end` ends it early.
- **Who covers.** The `--cover` office, else the profile's backup for that office (`Community.backup_for(office)`, an empty default, so a profile that names none has none), else the president for a manager's step and the vice president for the president's. The default table is a proposal for the board; the profile holds the adopted one.
- **What covering does.** Nudges for the away office's steps go to the cover, who sees them with "Covering for the treasurer until Oct 20." Section 6.5 applies from the first day.
- **What covering does not do.** It grants no authority. A role-gated act (the secretary records the board's decisions; the treasurer reviews the books) stays the role's alone: the cover sees the step, the instruction, the evidence, and "Only the secretary can record this. The secretary is away until Oct 20. Ask the president to bring it to the board." Authority passes only by the governing documents or a board decision (an acting appointment recorded as a decision, then a roster change). jason never moves it. A step whose `roles` already include the cover's office needs no handoff; they hold it.
- **The legal date during an absence.** A legal clock that falls inside an away period is a LEGAL line for the whole board from the day the absence is recorded (not the day it falls): "A legal date falls while the secretary is away."
- **Privacy.** Absence is shown as an office and two dates. No reason is asked or kept. It is visible to the board's offices and the manager (P2); a roster person with no office sees nothing.

## 6. Remind

### 6.1 Who gets nudged

The holders of the step's acting offices (or their cover while away), the run's owner for an `anyone` step, and the escalation office when the step is late (section 6.5). Nobody else. A step in a `draft` or `paused` run, a `done`, `skipped`, `not applicable`, or `superseded` step, and a step that is not yet `ready` nudge no one. A `wait` that only a person's note ends nudges its holder when its clock passes.

### 6.2 The bands

A pure function, `jason.workflows.nudge.nudges(views, definitions, roster, away, prefs, today)`, returns the nudges; nothing is stored. Each step gets at most one **band**; the first that applies:

| Band | Digest word | When | Threshold's basis |
|---|---|---|---|
| `legal` | LEGAL | a law clock on the step is due today or past | the law's date |
| `late` | OVERDUE | any other clock is past | the clock's own basis |
| `date` | needs a date | a settable date slot has no value, a clock reads from it, and the first step that reads it is `ready` | an engine fact |
| `soon` | due soon | the clock is within `lead_days` | proposed policy |
| `stale` | open | `needs a person` for longer than `after_hours`, and no clock | proposed policy |
| `quiet` | (not listed) | everything else | |

A signed plan waiting to be applied keeps its own band (`signedWaiting`, 24 hours by default; [approval-clarity.md](../console/approval-clarity.md)); it is a plan step, not a person step, and the two share the Approvals and Today surfaces.

Within a band: legal dates first, then by days to the date, then oldest. A per-item step is **one line with a count and the worst item's date**, never fourteen lines ("14 letters: 3 not done; the earliest due Oct 14").

### 6.3 The three channels

1. **In the console.** Reading, not messaging.
   - **Today**, the "Your work" band: the person's own steps by band, then "Escalated to you", then "Covering for the treasurer". The count beside a band is the digest's word, not a badge.
   - **Work**: the list's four groups, each row with the nudge word beside the due date and its basis; "needs a date" is a mark on the row.
   - **Approvals**: unchanged (plans); a step that links a plan carries the plan's strip.
   - **The office bands** ([office-views.md](../console/screens/office-views.md)): "Waiting on the treasurer", "Coming up for the treasurer", and the reading lens show the same lines for any office; a board member reading another office sees what it faces.
   - **The step panel's first line** and the rail's glyph.
   - The dock's red counts add "your steps past due" to `mine` (a count; it opens nothing).
2. **The digest.** `jason attention` gains a section (`workflows`) with the same lines, most urgent first, each with its command; the MCP `governance_digest` carries it. A person reads it when they open it.
3. **A person-run list.** `jason workflow --due [--office OFFICE] [--within DAYS] [--as-of DATE] [--json]` prints the nudges for an office (default: the viewer's) and what is `quiet` only with `--all`. It reads and writes nothing:

```
Due for the manager, as of 2099-10-20 (3 steps; 1 on a legal clock)
  LEGAL     Oakview owner information 2099 · step 22  Last day to enter the answers           due 2099-10-23 [law CIV 9999(b)]
            jason workflow --show run-3f9a0c1d22
  OVERDUE   Bill attach: Example Electric, Oct · step 4  Review the attachments                due 2099-10-14 [person]  6 days late
            jason workflow --show run-77b2e04a19
  due soon  Annual backflow test · step 3  Read the vendor's report                            due 2099-11-01 [counterparty]
Escalated to you (the president): 1
  OVERDUE   Quarterly review · step 5  Record the reviewer's notes (the treasurer, 4 days late) due 2099-10-16 [documents]
```

### 6.4 Date slots: late and timing

A date a person sets after the start (`DateSlot.late`, or a slot that is not `required`) is a clock waiting on a fact. Four readings, none of them a message:

1. **Unset.** A settable slot with no value, with a clock reading from it, becomes **needs a date** when the first step that reads it turns `ready`: "The recording day is not set. A clock needs it." It nudges the slot's `roles` (else the run's owner). The command is `jason workflow --set-date RUN SLOT=YYYY-MM-DD --record REF`.
2. **Past, not recorded.** A slot with `timing = PAST` (a day that has come: a postmark, a recording day) whose *event* date is known or implied by the slot it comes `after`, and which is still unset N days after that date, reads "The postmark was 6 days ago and is not recorded." N is `lead_days`' counterpart for the slot: proposed 3.
3. **Future, passed.** A slot with `timing = FUTURE` (a scheduled day) whose day has passed with the step that depends on it still open reads late like any clock.
4. **Corrected.** A `date-set` that corrects a value (a reason is required) re-reads every clock; a nudge computed from the old value is dropped, and the history says why.

A clock that reads from an unset slot is `undated` and is never shown as late. The inventory's "Clock" column names the slot each step hangs from.

### 6.5 Escalation without mail

Escalation is **visibility**, not a message. When a step is `late` for `escalate_after_hours` (0 for a legal clock: the day it falls), or a step's holder office is vacant, or a blocked note is left, the same step also appears for the **escalation office**: in its "Waiting on others" and "Escalated to you" lines, in the digest, and on the office band, with who holds it, how late, and the last note. Nothing is sent, and the holder's own line is unchanged.

Default escalation table (a proposal; the profile holds the board's adopted one, and an office with no row escalates to the board):

| The step is held by | Also seen by | A legal clock is seen by |
|---|---|---|
| the manager | the president | the whole board |
| the president | the vice president | the whole board |
| the vice president, the treasurer, a director | the president | the whole board |
| the secretary (records) | the president | the whole board |
| `anyone` (the run's owner) | the president | the whole board |
| a vacant office | the president | the whole board |

"The whole board" means every board office's band and the digest, as the board's items are. From there a person may *put it before the board* (a board item: a person's act, as in the control-adoption run); jason never convenes, decides, or moves a date.

### 6.6 Snooze, and what silences a nudge

| Action | Silences | Never silences |
|---|---|---|
| The holder acts (done, skip, not applicable) | the step | |
| The holder snoozes (`--snooze RUN STEP --until DATE`) | the holder's own line until the date (at most the due date, and at most 14 days) | the escalation office's line; a legal step (not snoozable); the run owner's quiet line |
| A blocked note (`--note RUN --step S --blocked --text T`) | moves the nudge to the escalation office; the holder's line stays, quiet, with the note | the step's clock |
| A claim | the others' lines (quiet) | the claimant's |
| Opening or reading the step | nothing | |
| An absence | the holder's line (it moves to the cover) | |

A snooze is a `note` event with `{snooze_until}` so the history shows who deferred what; there is no hidden personal state.

### 6.7 A reminder email draft (opt-in)

A board that wants an email in someone's drafts adopts a control, **reminder drafts**, as a control type with the other safeguards: jason suggests, the board adopts at a meeting (the secretary records it, with an effective date), and until then nothing exists. Parameters: which steps (a legal clock only, or any with a clock), the lead, and the least days between drafts for one step (proposed 7). A person asks for one: `jason workflow --remind-draft RUN STEP --by NAME` makes an approvals plan of kind `gmail-drafts`, case `step-reminder` (to add); a person marks, signs, and applies it ([approval-clarity.md](../console/approval-clarity.md)); the draft lands in Gmail Drafts; **a person sends it from Gmail**. The draft names the office, the step's general title, the date and its basis word, and a link to the run; it names no matter, no owner, no unit, and it is **refused for a held run**. No console button sends it; no clock makes it.

### 6.8 Reminder preferences, adopted like controls

The defaults in section 4.3 are rows the board adopts or changes: the lead time, the open-a-while threshold, the escalation delay, the escalation table, and the drafts control. Each is a control-like row: the decision that adopted it, an effective date, and a history ([../controls.md](../controls.md); [approval-clarity.md](../console/approval-clarity.md), section 5, for the signed-plan reminder already proposed there). A preference may only make a nudge *earlier or louder*; it can never remove a legal line, lengthen a legal clock, or let a step go unseen.

### 6.9 How often

Continuously and nowhere: the lines are computed whenever a person opens a screen or runs a command, from the stores on disk, with the day as an argument (the fold takes `today`; `--as-of` reproduces any day). There is no daily job. A reminder *draft* is at most one per step per the board's minimum days, and only when a person asks. The scheduler keeps reading sources on cadences a person adopted; it never writes a nudge.

## 7. Guide

### 7.1 What the panel shows, in order

1. **The enable state** (section 5.2) and who holds the step.
2. **Do this**: the `instruction`, then `why` in one sentence.
3. **Look at**: each `look_at` read, with its count and as-of; the evidence chips; "Open in NAME" for the owning screen at the right filter. A read that cannot read says why.
4. **The rule**: each `cite` recited whole, with the version in force on the relevant date and the caveat that jason's consolidated text is not an official restatement; then the reading, labeled. A proposed policy is shown as "proposed, not adopted".
5. **Check before you go on**: the checklist, with the required items marked.
6. **The command**: each `Cmd` with Copy, placeholders filled where known, terminal-only marked.
7. **Done when**: `done_when`, then the record the attestation must point to.
8. **If you are blocked**: `blocked`, then "Leave a blocked note", "Ask" with the offices, and "Claim".
9. **If it does not apply**: `not_applicable`, then the not-applicable act (who, reason, record) or the sentence that there is none.
10. **Learn more**: the SOP (`jason sop KEY`, the step's number), the lessons with their status, and the procedure step's readings.

On a narrow screen sections 3 to 10 are collapsible, section 2 and the act are always visible, and "Do this" never needs scrolling to find the act.

### 7.2 A worked example

A made-up guide for the step that reads the returned forms, in the owner-information cycle, on "Oakview" data (`CIV 9999(b)` is a made-up citation; a real one is checked against the shelf when the definition registers):

```python
Support(
    enables=Enables(in_hand=("the response inbox open", "this year's form, to compare"),
                    integrations=()),
    reminds=Reminds(lead_days=7, after_hours=48),
    guides=Guides(
        instruction="Read each form that has arrived, say what it answers, and confirm the reading when it is right.",
        look_at=(LookAt("Forms that arrived since the last read", read="responses-new"),
                 LookAt("Forms read and not yet confirmed", read="responses-unconfirmed")),
        checklist=(Check("Each reading matches the form on the screen", required=True),
                   Check("A form for the wrong unit is set aside, not confirmed"),
                   Check("Nothing is marked an answer until you confirm it", required=True)),
        commands=(Cmd("jason responses --list --new"),
                  Cmd("jason responses --read ID --by NAME"),
                  Cmd("jason responses --confirm ID --by NAME")),
        lessons=("returns-by-the-same-rules",),
        cites=(Cite("CIV 9999(b)", reading="jason's reading: answers are entered before the reports go out."),),
        done_when="The count of forms read and not confirmed is 0.",
        blocked="If a form cannot be read, leave a blocked note naming the form id and what is wrong with it.",
        not_applicable="",           # a required step: no not-applicable outcome
        ask=(Role.MANAGER, Role.PRESIDENT),
    ),
)
```

Rendered, under the step's title: the enable strip ("Yours: you hold the manager office. Nothing is missing."), a due line ("Due Oct 23, 2099 [documents]; due soon"), the instruction, two look-at counts, the recited rule with its labeled reading, a three-item checklist, three commands, "Done when: the count of forms read and not confirmed is 0.", and the blocked and ask lines.

### 7.3 Authoring order and archetypes

Write guidance in this order, so the steps that carry the most risk are covered first: (1) a step with a legal clock (`Exit` = `legal` in the inventory); (2) a step whose act cannot be recalled (mail, send, file); (3) a step a `WANTED` entry will turn into a check, job, or plan (write it now; the guidance moves to the new step's `look_at`); (4) the rest by family, the owner-information cycle first.

Most person steps are one of eight shapes. A shape fixes the defaults an author starts from, not a field:

| Shape | Typical guidance |
|---|---|
| Run a command and attest | `commands`, `done_when` = the output to look for, a `record` |
| Open it as the reader would (a link, a form, a letter) | `checklist` of what to see, `record` = the date and each link |
| Send or mail (cannot be recalled) | `second_person`, `terminal`, required checklist, the warning in `blocked`, no `snoozable` |
| Ask someone (a vendor, a member, counsel) | `ask`, the base template to draft from (a `template` in WANTED), `after_hours` short |
| Read and confirm | `look_at` counts, a required checklist, a reading cite |
| Enter or transcribe in another system | `in_hand`, `integrations`, `look_at` of the source, a `record` |
| File or keep | `look_at` of the plan, `done_when` = the filing read back |
| Decide and record (the board; the secretary) | the motion, the meeting, the decision record; no approve control; the next meeting date as the reminder |

### 7.4 Terminal guidance

`jason workflow --guide DEFINITION.STEP` prints the same sections as the panel, in the same order, as plain text with the commands on their own lines; `jason sop KEY` shows the procedure's steps with the workflow steps that were built from them. The terminal is where most commands are run, and a person there must not need the browser to know what to do.

## 8. Privacy

- **Directors and officers** read the same panel at the same level. A nudge differs by whose duty the step is; it never narrows or widens a board member's information. "Escalated to you" shows the step and its lateness, not more than the step's own level allows.
- **Held runs** (a hearing, a delinquent account, a records request: `Visibility.HELD`). Outside the private view, a nudge is the definition's `held_title`, the state, the office, the date, and the basis word, and nothing else: no step title unless `public_title`, no `look_at` row, no note, no claim name, no checklist, no recitation of a matter-specific clock. Inside the private view the whole panel shows, and each opening is logged under the run id (`access/served.jsonl`) as the Work screen already does. A reminder draft is refused for a held run. The digest line for a held step is "A member's hearing: a step is due", and the text filter matches the general title only.
- **Executive-session matters** (Civil Code 4935(e)) are held as the board items are: general words and state in the open record; detail only in the private view.
- **Administrator runs** (`Visibility.ADMIN`) nudge administrators only and appear in no one else's bands or counts.
- **Guidance is general** (section 2): it contains no name, no unit, no address, no figure that a cite carries, no association's fact. A test fails a definition whose guidance text matches the profile's instance terms (the same boundary the general code is held to).
- **Look-at rows** are at the viewer's data level (P0 to P3) and are counts and titles on a list; an owner's answer or contact detail is not in a nudge, a digest line, a `--due` line, a snooze note, or a claim.
- **Absence** is an office and two dates (section 5.5).
- **Contact details** are not shown in the panel. "Ask the president" names the office and the holder as the roster holds them; the directory's consent rules govern any phone number or email.

## 9. What is built, and what is new

| Piece | State |
|---|---|
| `StepDef` fields in section 3, the Work loaders and writer, `RunStepPanel` with why, evidence chips, command with Copy, Mark done, skip, not applicable, note | built |
| `DateSlot` late and timing, `date-set`, `dateSlots` and `openSlots` | built |
| The digest and its urgency words, the dock deadlines and `mine` counts, `signedWaiting` | built |
| `Support` (`Enables`, `Reminds`, `Guides`) on `StepDef`, and their validators | **built** (phase 1; 9.1) |
| Guide reads (`LookAt.read`) and their registry | **built** (`jason.workflows.guide_reads`; two reads, `responses-new` and `responses-unconfirmed`; one module per family beside the checks is still how the rest will be added) |
| `jason.workflows.nudge` (pure) and `jason workflow --due`, `--guide`, `--claim` | **built** (phase 1) |
| The `work-due` loader | not built |
| `jason workflow --snooze`, `--away`, `--remind-draft`, `--note --blocked` | not built (phase 2) |
| `Community.backup_for(office)` (empty default) | **built** (a profile may name a backup; none is read for a cover yet) |
| The `workflows` section of `jason attention` and the Today band's escalation and cover lines | not built |
| The reminder-drafts control type and the `step-reminder` case of `gmail-drafts` | not built (and not to be, until the board asks) |
| The panel's enable strip, nudge line, and guide sections | **built** ([work-guide.md](../console/screens/work-guide.md)) |
| The away dialog and banner, and the nudge marks on the lists | not built |

### 9.1 As built, phase 1 (2026-10-11)

What the code is, where it lives, and the calls the build made.

- **The record.** `Support(enables, reminds, guides)` and its parts (`LookAt`, `Check`, `Cmd`, `Cite`, `Guides`, `Enables`, `Reminds`) are frozen data in `jason.workflows.types`, and `StepDef.support` is `None` by default. A step with none behaves as it did: every field falls back as the third column of section 4.1 says (`jason.workflows.guide.spec`). `guide.from_mapping` turns JSON-like data into the symbols and refuses an unknown field by name.
- **The validators** (`guide.problems`, called by `definitions.validate`, which gained the optional `reads`, `lessons`, and `integrations` registries, each skipped when not given): a `Support` on a step that is not a person, a decision, or a wait only a note ends; guidance that carries a section number, a link, an address, a phone number, or an amount; a held definition's words with an `@`, and a `public_title` step's with a digit; a cite that is not a shelf key or `key#section`, or that the shelf says does not resolve (a missing shelf is a skip); a lesson or a guide read that does not exist; a command placeholder other than `NAME`, `KEY`, `RUN`, `ID`; an `ask` or `escalate_to` that is not an office; a `Reminds` below its floor, a snoozable legal step, a legal clock whose escalation delay is not 0; more than eight checklist items or three look-at reads; a required item with no `record` and no `done_when`; an unknown integration.
- **The nudge** (`jason.workflows.nudge`, pure, imports only the engine's types): the six bands, the proposed numbers as `Prefs` (14 days, 7 days, 72 hours, `adopted` false), the default escalation table, `claims_of`, and `run_nudges`. The days are read from the fold's clocks; "open a while" counts from the day the step's `needs` finished (or the run opened), so the same view and day give the same answer. A vacant office is escalated at once only when the roster names officers at all: an empty roster is *unknown*, never vacant.
- **A claim** is a `note` event on the step with `claim: true` (release: `claim: false`), made with `api.claim` / `jason workflow --claim RUN STEP --by NAME [--release] --yes` (without `--yes` it checks and writes nothing) and the writer's act `claim`. Only a person who may act on the step claims it, only while it is open, and only the claimant releases it. No event kind or field changed (a test folds a run with and without the note to the same states). A claim ends when the step ends, on release, or reads "still open" once the open-a-while threshold passes.
- **The composer** (`jason.tasks.step_guide`) builds the three objects for the Work page (`jason.web.extra.work_guide.attach`, called from `compose_run`) and the same words for the terminal (`jason workflow --guide RUN[:STEP]`, or `DEFINITION.STEP` for the definition's words alone, with `--for NAME` for the enable state; `--due --for NAME [--within DAYS] [--all]`). A cite is recited from the authorities shelf with the read-through held off (`statute_fetch.disabled()`); the words are whole as stored, the reading follows labeled "jason's reading", and a cite the shelf lacks says "The words of CITE are not on the shelf here." and gives the command that brings them down. Nothing else is read from outside the disk.
- **Calls the build made.** (1) The test module the brief names for the engine, `tests/test_workflows_support.py`, is the engine tests' shared fakes, so the record's tests are in `tests/test_workflows_person_support.py`. (2) The two engine modules (`guide`, `nudge`) are core and the one reads module (`guide_reads`) is edge, as `tests/test_workflows_boundaries.py` now lists. (3) A derived checklist is the procedure step's `check` as one unticked line; it is not repeated under Look at. (4) `anyone` is the run's owner for the nudge, as section 5.1 says, and the panel says "any signed-in person may do this" for it. (5) The viewer's own name is added to the holders of an office they hold, so a roster that omits a signed-in officer still reads true for them; the *ask* line uses the roster alone, so every reader is told the same names. (6) A step that is terminal-only still offers Mark done, with the record field required: the page cannot know the record exists, and the engine refuses an attestation without it. (7) The integrations' state is the last *recorded* connection (`integrations.json`, disk only); nothing is probed, and an integration nobody recorded is unknown, which does not refuse. (8) A second-person step shows "Needs a second person" for every holder, with the first act recorded as a note only where an adopted control binds it. (9) The six worked examples (`owner-info-cycle.12` and `.17`, `mailroom-letter.3`, `board-meeting.12`, `bill-attach.5`, `backflow-annual.7`) are in three families' definition files and in `definitions_general.py` (where the owner-information cycle lives).
- **Not built, by design of the phase.** Snooze, the away log and a cover, the blocked note's move of the nudge, `--remind-draft`, the `work-due` loader, the Today and Work list marks, the digest section, and reminder preferences as adopted rows. Nothing sends anything: the code imports no client (a test pins it).

## 10. The human edges of other step kinds

- **A wait only a person's note ends** (`ends_by_note`, and a wait whose reader does not exist yet): the holder is nudged when the clock passes, and the panel's act is "Note an arrival". It takes the `instruction`, `done_when`, and `ask` of a person step.
- **A branch a person answers:** the panel asks the question and records the answer; `done_when` is the question, not an outcome.
- **A plan:** decided in `#/approvals` with the stage strip ([approval-clarity.md](../console/approval-clarity.md)); the step shows the plan's state and its waiting-to-apply nudge. No `Support`.
- **A check or job:** jason's; no `Support`. The inventory's "Wanted" column lists the person steps they will replace; when a wanted read is registered the step becomes a `check` or `job` and its guidance moves to the neighbouring person step's `look_at`.

## 11. Build order

Phase 1 built steps 1 and 3, the claim of step 4, and the read side of step 2 (the bands and `--due`; the Today and Work marks and the digest section are still to do). Steps 4 (snooze, blocked note, absence and cover) and 5 are phase 2.

1. **Derive only.** The panel reads what the step already has: the SOP step's `do`, `check`, `refs`, and `lessons`; the evidence chips; `record` as "done when"; `skip`, `na`, and `ask` from the roles. No new field. This is the largest gain for the least code.
2. **`jason.workflows.nudge`** and the bands from the fields that exist (clock, slots, state); `jason workflow --due`; the Today and Work marks; the digest section. Defaults only.
3. **`Support` and its validators**; guide reads for the owner-information cycle and the legal-clock steps first.
4. **Claim, snooze, blocked note** (notes, no new event kind); then **absence** and the cover.
5. **Reminder preferences** as adopted rows; the **drafts control** last, and only if the board asks.

## 12. Tests (written with the build)

1. The inventory file equals the script's output (built: `tests/test_person_steps_inventory.py`).
2. The nudge function is pure: the same views and day give the same lines; a prefix of the events gives the earlier lines.
3. A legal clock is `legal` the day it falls, never snoozable, and escalates to the board the same day.
4. Nothing is nudged for a step that is not `ready`, a run that is paused or in draft, or a step that is over.
5. A per-item step is one line with a count.
6. An unset settable slot with a clock reading from it is `needs a date` once the reading step is ready, and the clock is `undated`, not late.
7. An absence moves the nudge to the cover, grants the cover no role, and a role-gated act by the cover is refused with the role's sentence.
8. A vacant office escalates at once and says "No one holds the OFFICE office".
9. A snooze is a `note` event, never beyond the due date or 14 days, and is refused on a legal step.
10. A held run's nudge, digest line, and `--due` line carry the general title only outside the private view.
11. A cite the shelf cannot resolve fails `validate`; the panel never paraphrases a statute.
12. Guidance on a held definition has no `@`; guidance on any definition matches no instance term.
13. The code sends nothing: the nudge module imports no client, and `--remind-draft` makes only a plan.

## 13. Decisions for the board

1. **The escalation table** (section 6.5): who also sees a late step, per office. Recommended: the president for the officers and the manager, the vice president for the president, the whole board for a legal clock.
2. **The defaults** (section 4.3): the lead (14 days), the open-a-while threshold (7 days), the escalation delay (72 hours; 0 for legal). Recommended: adopt as written, review in a year with the other standing decisions.
3. **Backups and covers** (section 5.5): the profile's table of who covers whom, and whether a cover may ever be given a role for a period (by a board decision recorded by the secretary), or only ever sees.
4. **Whether to adopt reminder drafts at all** (section 6.7). Recommended: no, until the board asks; the console and the digest are enough for a board that opens them.
5. **Whether a claim should be a note or an assignment** (section 5.4). Recommended: a note. An assignment would be a rule about who may act, and that is the board's to adopt.
6. **Whether the manager alone may snooze a non-legal step** past its due date (recommended: never past the date; a later date is a `date-set` with a reason).
7. **The command's name.** The admin asked for `jason work --due`; the command that exists is `jason workflow`, so the spec adds `--due` there. A `work` alias is cheap if wanted.
8. **Who may record an absence** for an office: the holder (recommended), or the holder and the president, or any board member.
