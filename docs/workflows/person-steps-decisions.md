# Person steps: the board's decisions that block phase 2

Status: **open, for the board to answer** (drafted 2026-10-11). This page is the decision list that [person-steps.md](person-steps.md) section 13 points at, written so a board member can read one decision at a time and answer it. Phase 1 of person steps is built ([person-steps.md](person-steps.md) section 9.1): the guidance record, the bands, `jason workflow --due`, `--guide`, and the claim. Phase 2 (snooze, the blocked note, absence and cover, the Today and Work marks, the digest section, reminder preferences as adopted rows) waits on the seven answers below. Until an answer is recorded, the code default holds and is shown as *proposed, not the law's*.

jason proposes and never decides. Every recommendation here is **proposed, not the law's**: a number or a table that no statute and no governing document sets. Where a statute bears on a decision it is recited below from the stored text, then jason's reading follows, labeled as a reading. A section that is not on the authorities shelf is not cited. jason's consolidated text is not an official restatement of the law. The screen these decisions shape is [../console/screens/work-guide.md](../console/screens/work-guide.md); how an adopted answer becomes a row is in [../controls.md](../controls.md).

## The seven, at a glance

| # | The question | Proposed (not the law's) | If the board does not answer |
|---|---|---|---|
| 1 | [Who else sees a late step, for each office?](#1-the-escalation-table) | The president for the officers and the manager; the vice president for the president; the whole board for a legal clock. Visibility only. | The code default table is shown, labeled proposed. |
| 2 | [What are the lead, the open-a-while threshold, and the escalation delay?](#2-the-defaults) | 14 days, 7 days, 72 hours (0 for a legal clock); review in a year. | The same numbers hold, labeled proposed, never as a stamp. |
| 3 | [Who covers whom during an absence, and may a cover ever hold a role?](#3-backups-and-covers) | A cover only sees. A role changes only by a board decision the secretary records. | No cover is named; only the proposed pairs are shown, labeled. |
| 4 | [Do reminder email drafts exist at all?](#4-reminder-email-drafts) | No, not until the board asks. | They do not exist. Nothing to build. |
| 5 | [Is a claim a note or an assignment?](#5-a-claim-a-note-or-an-assignment) | A note (as built). | A note. |
| 6 | [May anyone snooze past a due date, and may the manager do so for a step that is not on a legal clock?](#6-snooze) | No one snoozes past a due date; a later date is a recorded date change with a reason. | Snooze is not built; nothing is silenced. |
| 7 | [Who may record an absence, and what is the command called?](#7-who-records-an-absence-and-the-commands-name) | The holder, or the secretary on the holder's behalf, logged; `jason workflow --due` as built, a `work` alias if wanted. | No absence can be recorded; the command stays as built. |

Numbers 4, 5 and the command in 7 are answered "no change" in the proposal, so the board can take them in one motion. Numbers 1 to 3 and 6 to 7 change what people see and are worth a short discussion.

This page numbers seven where section 13 of the person-steps page lists eight: the snooze question (its item 6) now states its options, and the absence question (its item 8) and the command's name (its item 7) are one decision, 7.

## What stays true whatever the board chooses

Each decision repeats the lines that touch it. None of these is open.

- **jason sends nothing on its own.** A reminder is a reading on a screen, in a digest, or at a command. No email, message, text, calendar invite, or Google Task is made by a clock.
- **A legal clock is never snoozable,** never delayed before it escalates, and never removed by a preference.
- **Directors and officers have the same access to information.** A nudge or an escalation differs by whose duty a step is, never by what a board member may read.
- **A held step shows its general title only** outside the private view: the state, the office, the date and its basis word, and nothing else.
- **The secretary records the board's decisions;** jason records what the secretary gives it and decides nothing.
- **A cover or an escalation office gains no authority.** It sees, reads, and asks.

## 1. The escalation table

**The question.** When a step is late, which other office also sees it, for each office that can hold a step?

**Why it matters.** A step left undone is usually a step nobody else saw. Escalation is how a late step reaches a second pair of eyes without anyone being messaged. Too little, and a late legal date is seen by one person; too much, and every board member's screen is full of other offices' lines and the legal ones are hard to find.

**Options.**

| Option | What it does | What it costs |
|---|---|---|
| A. The proposed table | A step held by the manager, the treasurer, the secretary, a director, the vice president, or `anyone` also shows for the president once it is late. A step held by the president also shows for the vice president. A step on a legal clock shows for the whole board the day it falls. A vacant office is escalated at once. | The president sees every late officer and manager step; a busy president has the longest list. |
| B. The whole board sees every late step | Every late step appears in every board office's band. | The most noise; the legal lines no longer stand out from the rest. |
| C. One person only, legal clocks included | Every late step, legal or not, appears for the president only. | A legal date is seen by one person, which fails exactly when that person is away. |
| D. No escalation | Each step shows only for its holder and the run's owner. | A late step is seen by no one else. |

**Proposed, not the law's: option A.** The table is in [person-steps.md](person-steps.md) section 6.5. The board may name a different office for any row; an office with no row escalates to the board.

**What stays true.** Escalation is **visibility only:** the step also appears on another office's screen and in the digest, and **nothing is sent to anyone**. The holder's own line does not change. A legal clock escalates with a delay of 0 whatever the table says. A held step is escalated with its general title only.

**The law and the documents.** Escalation widens what a board office sees and never narrows what a director may read. The statute on a director's right of inspection:

> Every director shall have the absolute right at any reasonable time to inspect and copy all books, records and documents of every kind and to inspect the physical properties of the corporation of which such person is a director.

(Corporations Code 8334.) jason's reading: a nudge that names a director as its holder or its escalation office is a convenience about whose duty a step is, and it neither grants nor takes away the right above. Matters in a closed session are noted in general words:

> Any matter discussed in executive session shall be generally noted in the minutes of the immediately following meeting that is open to the entire membership.

(Civil Code 4935(e).) jason's reading: an escalated line for a held step carries general words, as the board's items do, outside the private view.

**How the answer is recorded.** The board decides at a meeting and the secretary records the decision (`jason board`, `decisions.json`). It becomes an adopted **preference row** like the apply preferences ([../controls.md](../controls.md) section 5, [../console/approval-clarity.md](../console/approval-clarity.md) section 5.1): the decision that adopted it, an effective date the board names, and a history. The board's table is the row's parameter. Until adopted, the **code default** applies (`jason.workflows.nudge.ESCALATION`), shown as *proposed, not the law's*.

**What code changes follow.** The escalation table becomes a preference type beside `PREFERENCES` in `jason.controls.catalog`; `nudge.escalation_office` reads the adopted row first and the code default second; the Today "Escalated to you" lines, the office bands, and the digest section (phase 2) are built to read it. Option A changes no code. Options B, C, and D change the table only.

## 2. The defaults

**The question.** What are the three numbers that no law sets: how many days before a clock a step shows as due soon, how long a step with no clock may sit before it shows as open a while, and how long a late step waits before its escalation office also sees it?

**Why it matters.** These numbers decide when a step starts to show and when a second office sees it. Too short, and everything is always flagged; too long, and a flag arrives after the date.

**Options.**

| Option | What it does | What it costs |
|---|---|---|
| A. Adopt as proposed | Lead 14 days (the schedule's two weeks). Open a while after 7 days (168 hours). Escalation delay 72 hours; 0 for a legal clock. Reviewed in a year with the board's other standing decisions. | The numbers are a guess until a year of use shows what suits this board. |
| B. Adopt different numbers | The board names each number. The least are 0 days of lead and 0 hours of delay. A legal clock keeps a delay of 0 whatever is named. | The board has to choose each number without the experience to set it. |
| C. Different numbers by family | The money and the board's steps one way, the members' cycles another. | More to read and to explain; the same lateness reads differently in two places. |
| D. Do not adopt | The proposed numbers keep working, labeled *proposed, not the law's*, and the board is not asked again unless it chooses. | The label never goes away. |

**Proposed, not the law's: option A,** reviewed in a year.

**A note on direction.** [person-steps.md](person-steps.md) section 6.8 says a preference may only make a nudge earlier or louder. Read plainly, that would bar a number later than the proposal even for a step that is not legal (a lead of 7 days). The point of the sentence is that a preference can never remove a legal line or lengthen a legal clock. If the board wants a later number for a step that is not legal, say so, and the sentence is relaxed to that.

**What stays true.** A legal clock is never delayed or removed. The numbers change **when** a line appears and never **whether** a legal line appears. Nothing is sent.

**The law and the documents.** None bears. No statute and no governing document found for this decision sets a lead time, a threshold, or an escalation delay. The board's setting is its own choice, in writing, and jason applies it the same way every time. Whether such a setting is an operating rule turns on this definition:

> "Operating rule" means a regulation adopted by the board that applies generally to the management and operation of the common interest development or the conduct of the business and affairs of the association.

(Civil Code 4340(a).) jason's reading: these settings control how jason shows the board's own steps to the board and the manager. They are not a regulation of members or of the development, so jason treats them as the board's internal procedure and not an operating rule. That is one reading; the words "the conduct of the business and affairs of the association" can be read more widely, and where two readings remain the board asks counsel. Nothing in the proposal turns on it: the board adopts it in writing at a meeting either way.

**How the answer is recorded.** The secretary records the board's decision. It becomes an adopted **preference row** (three numbers, each with its decision, effective date, and history), adopted as `jason controls` adopts the apply preferences (`--adopt KEY --meeting DATE --decision ID --effective DATE --param NAME=VALUE --yes`). Until then the **code default** is `jason.workflows.nudge.DEFAULTS` (`adopted` is false).

**What code changes follow.** A reminder-numbers preference type in the catalog; `nudge` reads the adopted row first (it already takes the numbers as `Prefs`); the validator refuses a number below its floor and a nonzero delay on a legal clock; the panel stops saying *proposed, not the law's* beside a number once it is adopted and says "adopted DATE" instead.

## 3. Backups and covers

**The question.** When an office is away, which office sees its steps, and may a cover ever be given the role for a period?

**Why it matters.** An absence is when steps are most likely to be missed. A cover who can see the step and ask about it helps. A cover who can also act changes who has authority, and authority is the board's to give.

**Options.**

| Option | What it does | What it costs |
|---|---|---|
| A. A cover only sees (proposed) | For each office the board names one cover. During a recorded absence the cover sees the absent office's steps with the instruction, the evidence, and the sentence that only the office itself can act, and who to ask. A role-gated act (the secretary records the board's decisions) stays the role's alone. Authority passes only by the governing documents or a board decision the secretary records, followed by a roster change. | If the secretary is away, the board's decisions wait, or the board makes an acting appointment by decision. |
| B. A cover may hold a role for a period | The board's decision names the office, the cover, and the dates; the cover may then act as the role. | jason would have to end the cover's authority when the period ends, and a missed end leaves authority where nobody meant it. The governing documents' rules about who may hold an office decide whether it is allowed at all, and jason has not read them for this. |
| C. No covers named | An absent office's steps go to its escalation office from the first day, as a vacancy's do. | No one is asked to look out for them; a cover is a person, and an escalation office is a table row. |

**Proposed, not the law's: option A.** The proposed pairs are the president for the manager and the vice president for the president. The board names a cover for each of the other offices (the vice president, the treasurer, the secretary, a director) or leaves it to option C's rule for that office.

**What stays true.** A cover **sees and asks;** it gains no authority. The secretary records the board's decisions, and a cover for the secretary does not. A legal clock that falls inside a recorded absence shows for the whole board from the day the absence is recorded. Absence is recorded as an office and two dates, never a reason. Directors and officers read the same information at the same level.

**The law and the documents.** On who holds an office and how it changes:

> Any number of offices may be held by the same person unless the articles or bylaws provide otherwise.

(Corporations Code 7213(a).)

> Except as otherwise provided by the articles or bylaws, officers shall be chosen by the board and serve at the pleasure of the board, subject to the rights, if any, of an officer under any contract of employment.

(Corporations Code 7213(b).) jason's reading: a person holds an office because the board chose them, and the board may choose a different person. A cover who acts as an office is a choice of the board and not of jason, which is why option A leaves the change to a board decision and a roster update. The bylaws may provide otherwise, and jason has not read them for this decision. Where the governing documents speak to an acting officer, the board follows them and asks counsel if they leave it open.

**How the answer is recorded.** Two parts. The table of covers is a fact of the association's profile (`Community.backup_for(office)`, an empty default, so a profile that names none has none); the secretary records the board's decision and a person updates the profile's table with the decision's id and date. Whether a cover may ever hold a role is a decision only: option A needs no row, and a board that chooses option B records each acting appointment as its own decision before the roster changes. Until adopted, the step panel shows the **code default** pairs (`jason.tasks.step_guide.BACKUPS`) labeled as proposed.

**What code changes follow.** `Community.backup_for` exists and the step panel's ask line shows its answer; no nudge reads it yet. Phase 2 makes the nudge function route an away office's lines to the cover (`jason workflow --away`, the away log, the banner on the office view), and refuses a role-gated act by a cover with the role's sentence. Option B would add a dated acting-appointment record and a check that expires it. It is not proposed.

## 4. Reminder email drafts

**The question.** Should jason be able to prepare an email reminder as a draft in Gmail for a person to send?

**Why it matters.** The console, the digest, and the command already show what is due, to anyone who opens them. A reminder email goes to a person's inbox without their opening anything, and it is a message that leaves the association's systems. It is also the one outward form a reminder takes, so it needs the board's control.

**Options.**

| Option | What it does | What it costs |
|---|---|---|
| A. Do not adopt (proposed) | Reminder drafts do not exist. Nothing is built. The board may ask later. | A person who never opens the console or the digest is not reminded by it. |
| B. Adopt for legal clocks only | A person asks for a draft for a step on a legal clock, at the lead the board sets and no more often than the days between drafts it sets (proposed 7). | One control type and one plan case to build and keep, and a draft a person has to send. |
| C. Adopt for any step with a clock | The same, for any step with a clock. | More drafts, more to approve and send, and a longer list of messages that leave the association. |

**Proposed, not the law's: option A,** until the board asks.

**What stays true if it is adopted.** jason **sends nothing.** A person asks for a draft (`jason workflow --remind-draft RUN STEP --by NAME`). That makes a plan of the Gmail drafts kind. A person **marks** it, **signs** it, and **applies** it ([../console/approval-clarity.md](../console/approval-clarity.md)); the draft lands in Gmail Drafts; **a person sends it from Gmail.** The draft names the office, the step's general title, the date and its basis word, and a link to the run. It names no matter, owner, or unit, and it is refused for a held run. No console button sends it and no clock makes it.

**The law and the documents.** None found that bears; nothing is cited.

**How the answer is recorded.** The secretary records the decision. If the answer is yes, it becomes an adopted **control** of a new type, reminder drafts (which steps, the lead, the days between drafts), with an effective date and a history, adopted as any control is ([../controls.md](../controls.md)). If the answer is no, the decision is recorded as declined, and jason does not ask again without a reason or a date the board names. The default with no decision is that the drafts do not exist.

**What code changes follow.** On a yes: the control type, a `step-reminder` case in the Gmail drafts kind, and `jason workflow --remind-draft`. On a no: none.

## 5. A claim: a note or an assignment

**The question.** When a person says they are on a step, does that only tell the others, or does it give the step to that person?

**Why it matters.** Two people each think the other has it. A claim solves that. But an assignment is a statement about who has a duty, and who has a duty is the board's to say.

**Options.**

| Option | What it does | What it costs |
|---|---|---|
| A. A note (as built, proposed) | A claim is a note on the step: the person's name and the date. It reorders what the others see and grants and removes nothing. Any holder can still act. It ends when the step ends, when it is released, or reads as still open once the threshold passes. | Nothing stops two people from acting; the first to act completes the step. |
| B. An assignment | A claim makes one person responsible and may stop the others from acting. The board adopts who may assign, whether others may act on an assigned step, and how an assignment ends. | A new rule about duties, new ways to be stuck (an assignee who is away), and a reason to record every assignment as a decision. |
| C. No claim | The button is removed. | The problem the claim solves returns. |

**Proposed, not the law's: option A,** as built.

**What stays true.** A claim sends nothing and gives no authority. It is a note with a name and a time, as every note is. jason does not assign member requests (a standing project boundary), and it assigns nothing here either; under option B a person would assign, and the board would adopt the rule that lets them.

**The law and the documents.** On duties:

> any other officers with any titles and duties as shall be stated in the bylaws or determined by the board

(Corporations Code 7213(a), the end of the first sentence.) jason's reading: an officer's duties are stated in the bylaws or determined by the board, so a rule that makes a step one person's duty is the board's to adopt and not a convenience of jason's. That is why option B is a board decision and option A is not.

**How the answer is recorded.** The secretary records the decision. Option A needs no row: the **code default** (a claim is a note) is what is built, and the decision is recorded as made. Option B would be an adopted rule row with an effective date, adopted as the board adopts any rule that governs who acts.

**What code changes follow.** Option A: none. Option C: remove the claim button and the `claim` act. Option B: a new act and rule, designed after the board answers.

## 6. Snooze

**The question.** May anyone snooze a step past its due date, and may the manager, alone, snooze a step that is not on a legal clock past its date?

**Why it matters.** A holder who cannot do a step today sometimes wants it out of their way for a few days. A snooze that ends before the due date helps. A snooze that outlasts the date makes a late step look quiet, which is the failure the nudge exists to prevent.

**Options.**

| Option | What it does | What it costs |
|---|---|---|
| A. No snooze past a due date (proposed) | A holder snoozes their own line for at most until the due date and at most 14 days. A step that cannot be done by its date gets a new date through a recorded date change with a reason, where its date is one a person may set (`jason workflow --set-date`); that re-reads every clock and shows in the history. | A step that cannot be done by its date takes a date change and a reason, not a quiet day. |
| B. The manager alone may, for a step that is not legal | The manager may snooze a step that is not on a legal clock for up to 14 days past its date, with a one-line note. The escalation office's line is unchanged. | A late step reads quiet on the manager's own screen, and a second set of rules to explain. |
| C. Any holder may, for a step that is not legal | The same as B for every holder. | The same, for every office. |
| D. No snooze at all | The snooze act is removed. | A holder who wants a step out of the way for a day cannot. |

**Proposed, not the law's: option A.**

**What stays true.** A legal clock **cannot be snoozed** by anyone: the act is refused with the sentence that a legal date cannot be snoozed. A snooze never silences the escalation office's line or the run owner's quiet line. A snooze is a note with a name and a time, so the history shows who deferred what. Nothing is sent.

**The law and the documents.** None found that bears; nothing is cited. The rule that a legal date never snoozes is jason's own, and the law's date is whatever the step's clock cites.

**How the answer is recorded.** The secretary records the decision. Option A is the **code default** (the snooze act is bounded by the due date and 14 days), so it needs no row. Options B and C are adopted **preference rows** with a number of days and who may use them, with an effective date; option D removes the act.

**What code changes follow.** Phase 2 adds the snooze act and the `note` with `snooze_until`, with the refusals (legal, past the due date, past 14 days). Option B or C relaxes the second refusal for a step that is not legal and reads the row. Option D adds nothing.

## 7. Who records an absence, and the command's name

**The question.** Who may record that an office is away, and what is the person-run command called?

**Why it matters.** An absence moves an office's nudges to its cover and shows a legal date inside it to the whole board. If anyone can record one, anyone can quiet an office, so who records it matters. The command's name matters only to the people who type it.

**Options for who records.**

| Option | What it does | What it costs |
|---|---|---|
| A. The holder, or the secretary on the holder's behalf (proposed) | The person who holds the office records their own absence. The secretary, who keeps the board's records, may record it for them, logged with both names. | If the secretary is the one away, the holder records it, or another board office does under option B or C. |
| B. The holder and the president | The president may also record it. | A second person may quiet an office the holder did not mean to. |
| C. Any board member | Any board member may record one. | Anyone on the board can move an office's nudges. |
| D. The holder only | No one records on another's behalf. | An absence that was not recorded before the holder left is not recorded. |

**Proposed, not the law's: option A.**

**The command.** The screen spec asks for `jason work --due`. The command that exists is `jason workflow`, and `--due` is there. A person types `jason workflow --due`. A shorter `work` alias costs one line and changes nothing else; it is not proposed unless the board or the manager wants it.

**What stays true.** An absence is recorded as an **office and two dates, never a reason and never a place,** and is visible to the board's offices and the manager. A cover gains no authority. The log is append-only and private, with the name of the person who recorded each line and when. Nothing is sent.

**The law and the documents.** None found that bears; nothing is cited.

**How the answer is recorded.** The secretary records the decision. Option A is the **code default** (who may write the away log), so a decision for A needs no row; B, C, or D adopts a **preference row** for who may record, with an effective date. The command's name is not a board matter; it is the manager's choice and a change to the command line only.

**What code changes follow.** Phase 2 adds `jason workflow --away` and `--away --end`, the log under the store lock, and the console dialog and banner, each checking the recorder against this decision. The earlier design said an administrator may record on the holder's behalf; option A replaces the administrator with the secretary. A `work` alias is one entry in the command table.

## How to answer

Answers go to the secretary, who records the board's decision (`jason board`, `decisions.json`). jason records what the secretary gives it and decides nothing, so a decision is whatever the board's record says it is.

- **Answer by number and option,** for example `1: A; 2: A; 3: A, the vice president covering the treasurer; 4: A; 5: A; 6: A; 7: A, no alias`. Where the proposal is no change, saying so in one motion is a complete answer.
- **Name an effective date** for any answer that changes a setting (1, 2, 6, 7, and a table in 3). The setting binds from that date. An answer with no date is recorded as made and applies from the date the secretary records.
- **A number is the board's to change.** Say a different number and it is recorded as the board's number, with the decision's id. A question that the law or the governing documents leave open is for the board to put to counsel; jason does not settle it.
- **A decision left unanswered** keeps the code default, shown as *proposed, not the law's*, and does not block any step from being done. Only the phase 2 features that need an answer wait.
- **Review.** An adopted answer is reviewed each year with the board's other standing decisions.
