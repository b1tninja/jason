# Meetings & minutes

Bands added to `#/meetings` and `#/minutes-review` · phase 2 · CLI: `jason schedule-evidence --watch`, `jason meetings`, `jason record-stages`, `jason board`

## In the console

The Governance group already runs the board loop:

| Console screen | What it does |
|---|---|
| **Meetings and minutes** (`#/meetings`, `ConsoleMeetings`; owner view too) | Each meeting's records on hand (agenda, notice, minutes, transcript, recording) and its checks (no minutes 30 days on, a recording held after the minutes, a transcript into executive session), with scheduled days that have no record |
| **Next meeting** (`#/meeting`) | One meeting: the last days to give notice (CIV 4920), items by session (executive by title only), the agenda draft, the packet, the minutes frame, and the commands that write each Doc |
| **Plan a meeting** (`#/agenda`, `ConsoleAgenda`) | The four-step `AgendaWizard`: meeting, ready to act, order and motions, notice |
| **Meeting room** (`#/room`, `ConsoleMeetingRoom`) | `MeetingStage` and `HostPanel`: attendance, motions, roll calls by name, the CIV 4930 guard, executive session as the host's act; draft minutes go to Approvals for the secretary |
| **Decisions** (`#/decisions`, `ConsoleDecisions`) | A `DecisionBrief` per matter above its `DecisionCard` |
| **Minutes review** (`#/minutes-review`) | The minutes draft's blanks as a form, the privacy flags beside their lines; a filled copy saved, the draft never edited |
| **Hearings**, **Rule changes** (`#/hearings`, `#/rules`) | The 5855 and 4360 clocks and the board's decisions on them |

**What this spec adds:**

1. **The meeting watch** on `#/meetings`: each board meeting's notice clock (4920) and minutes clock (4950(a)) read forward, in `meeting_watch.Standing`'s words, so a late notice or late minutes shows before the day passes; and the meetings the schedule set with nothing on record near them.
2. **Record a posting** and **record the minutes made available**: signed records on those clocks.
3. **jason's checks** beside the draft on `#/minutes-review`: quorum, the motions, confidential subjects, pronouns, and what the transcript does not support, with **Re-check**.
4. **Record stages** on `#/meetings`: rule changes through 4360 and 4365, and minutes with their approvals, stated or only listed.

## Purpose and personas

- **Secretary:** the main user. Watches each meeting's clocks, records a posting, reads the draft beside its checks, and fills the blanks.
- **Manager:** runs the syncs and the draft.
- **Director:** reads the clocks the board answers for, and the stages of minutes and rule changes.

## Data

| Band | Source | Loader |
|---|---|---|
| The meeting watch | `jason.tasks.meeting_watch.watch(community, data_dir)` → `Watch.as_dict()`: `asOf`, `from`, `until`, `meetings[]` (`date`, `kind`, `basis`, `titles`, `held`, `clocks[]`, `notes`), `unrecorded[]`, `notes`, `caveats` | `meeting-watch` (to add) |
| A clock | `Clock.row()`: `what` (notice or minutes), `requirement`, `authority` (CIV 4920(a), 4920(b)(2), 4950(a)), `timing`, `deadline`, `standing`, `record`, `on`, `note`, `assignment`, `due`, `notice` (`jason://notice/KEY`) | the same |
| The caveats | `meeting_watch.CAVEATS`, verbatim. The first: "None on record is not none given…" | the same |
| The checks | `minutes_draft.checks(record, text, community)`: `quorum` (`inOffice`, `present`, `unidentified`, `needed`, `standing`), `claimsQuorum`, `motions`, `confidential[]`, `kind`, `kindDiffers`, `pronouns[]`; rendered as `minutes_draft.check_lines`; the draft's `unsupported`, `gaps`, `unknowns` | add to `minutes-review` |
| Record stages | `jason.tasks.record_stages.histories(community, data_dir)` | `meeting-watch` |

## Layout: the watch

```
+------------------------------------------------------------------------------------------+
| THE CLOCKS · Sep 3 to Dec 2, as of Oct 3                 jason meetings --sync [copy]    |
| Oct 7, 2099 · board meeting · from the schedule                                          |
|   Notice   by Oct 3 (4 days before, CIV 4920(a))   [LEGAL] today   none on record yet    |
|            Secretary, due Oct 3                    [Record a posting]                     |
|   Minutes  by Nov 6 (30 days after, CIV 4950(a))   34 days left    none on record yet    |
| Sep 9, 2099 · board meeting · held (Zoom record)                                         |
|   Notice   by Sep 5   on record in time: delivered (jason://notice/board-meeting-2099-09-09)|
|   Minutes  by Oct 9   6 days left   none on record yet   [Open the draft]                 |
| * The schedule set a meeting on Aug 12 and nothing is on record near it: if it was held, |
|   its minutes are due by Sep 11.                                                         |
| None on record is not none given: a notice posted ... (CAVEATS, verbatim)                |
+------------------------------------------------------------------------------------------+
| STAGES · Sep 9 minutes: draft on file Sep 12 · available: none on record · approved: none |
+------------------------------------------------------------------------------------------+
```

## Layout: the checks beside the draft

```
+-----------------------------------------------+------------------------------------------+
| THE DRAFT (as #/minutes-review shows it)      | JASON'S CHECKS                [Re-check] |
| ## Call to order                              | Quorum: the record shows 3 of 5          |
| Called to order at 7:02 PM by [unknown]       |  directors on the call; a quorum is 3.   |
| ### 1. Landscaping contract                   |  Standing: present.                      |
| - Motion: approve the bid ($4,200.00)         | Lines naming a confidential subject: 1   |
|   Moved: Director A; seconded: [unknown]      |  -> read before the draft is shared      |
|                                               | Unsupported by the transcript: 1         |
|                                               | Blanks left for the Secretary: 5         |
+-----------------------------------------------+------------------------------------------+
```

A check that points at a line links to it. Under 960 px the checks come first, above the draft.

## Components

`Card`, `Clock` (a meeting's two clocks as stages), `Pill` (the standing words), `DueDate`, `Findings` (the checks, under the heading "jason's checks"), `Caveats` (verbatim), `Evidence`, `Command`, `Confirm` (record a posting), `Recitation` (the clock's authority, on demand), `ReadingLabel` (a check is jason's count, never the minutes' words).

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Record a posting (a meeting notice) | `notice_ledger.set_general(key, posted, by)`, or `record_completion(key, due, by, evidence)` for the assignment that owns the clock, behind `Confirm` | No: a signed `data/` record. Needs a name and the evidence ("Posted on the clubhouse board, Oct 2, 9:00") | `jason notices KEY --mark-general --posted "..." --by NAME`, or `jason schedule --done KEY DUE --by NAME --evidence TEXT` |
| Record the minutes made available | `record_completion(key, due, by, evidence)` for the minutes assignment | No: signed | `jason schedule --done KEY DUE --by NAME --evidence TEXT` |
| Re-check | `minutes_draft.recheck(data_dir, community, day)`: the checks again, no model | No | `jason board --minutes DAY --recheck` |
| Draft the minutes | shown as a command: a local-model job, under the GPU lock | No | `jason board --minutes DAY` |
| Sync | shown as a command | No | `jason meetings --sync` |

**jason never posts, sends, or approves minutes.** The draft stays DRAFT until the board approves the minutes by a vote at a meeting. That approval reaches the console only as a record: the later minutes that state it, read by `record_stages`. "Approved" shows only when stated; an approval only listed on a later agenda shows as "listed, not stated".

## States

- **No meetings in the window:** "No board meeting in the window: the profile sets no meeting schedule, and the catalog holds none."
- **None on record yet** (deadline ahead): the standing in words, with its deadline. Never "not given".
- **None on record; the deadline passed:** LEGAL, and the first caveat inline: "None on record is not none given. If it was posted, record the posting."
- **A file in time, delivery not on record:** "a file in time; its delivery is not on record". A file never meets a notice clock.
- **The draft claims a quorum the count does not support:** "The draft says a quorum was present; the count does not support it. Correct the attendance, or the statement." Shown first.

## Privacy

- Executive-session material is listed by date only. The draft never holds it: the model is given the transcript only up to the executive break.
- Confidential lines in the open draft (Civil Code 4935 subjects) are shown in full to the Secretary and manager, with the instruction to read each before the draft is shared.
- A caller shown only by a telephone number is "unidentified caller" with the last four digits.
- The owner view shows the meetings' records as built, not the watch's assignments or the checks.

## Acceptance criteria

1. The watch renders each meeting's clocks with `Standing`'s words, the deadline, and the authority, matching `Watch.as_dict()` for the fixture; the caveats render verbatim, the first one above the fold.
2. No control posts, sends, publishes, or approves minutes. The words "post minutes" and "approve minutes" are not on any button.
3. Recording a posting refuses an empty name or evidence, and the watch counts the record on the next read.
4. The checks render `check_lines` exactly, under "jason's checks", and a check that names a line links to it.
5. Executive-session material never appears.
