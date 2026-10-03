# Meetings & minutes

`/meetings`, `/meetings/{date}` · phase 2 · CLI: `jason schedule-evidence --watch`, `jason meetings`, `jason record-stages`, `jason board`

## Purpose and personas

The clocks each board meeting starts, read forward so a late notice or late minutes shows before the day passes; each meeting's records; and the minutes draft beside the checks jason counts.

- **Secretary:** the main user. Watches each meeting's notice clock and minutes clock, records a posting, reads a minutes draft beside its checks, and fills the blanks it leaves.
- **Manager:** starts the syncs and the draft, and prepares the agenda.
- **Director:** reads the clocks the board answers for, and the stages of minutes and rule changes.
- **Treasurer, reviewer, counsel:** no access. Counsel reads a meeting's minutes through Governing documents (`jason://min/DAY`) on grant.

## Data

| Part | Source |
|---|---|
| The meeting watch | `jason.tasks.meeting_watch.watch(community, data_dir)` → `Watch.as_dict()`: `asOf`, `from`, `until`, `meetings[]` (`date`, `kind`, `basis`, `titles`, `held`, `clocks[]`, `notes`), `unrecorded[]`, `notes`, `caveats` |
| A clock | `Clock.row()`: `what` (notice or minutes), `requirement`, `authority` (CIV 4920(a), 4920(b)(2), 4950(a)), `timing`, `deadline`, `standing`, `record`, `on`, `note`, `assignment`, `due`, `strength`, `notice` (`jason://notice/KEY`) |
| Standing words | `meeting_watch.Standing`: "on record in time", "on record late", "a file in time; its delivery is not on record", "a file, written after the deadline; its delivery is not on record", "on record, undated", "none on record yet", "none on record; the deadline passed" |
| The caveats | `meeting_watch.CAVEATS`, verbatim. The first: "None on record is not none given…" |
| One meeting's records | `meeting_records(date=DAY)` and `zoom_meetings(...)` (`jason.mcp.county`): agenda, minutes copies, transcript, recording, summaries |
| The minutes draft | `data/board/minutes-draft-<date>.md` (written by `minutes_draft.draft`); its checks block `## jason's checks` |
| The checks | `minutes_draft.checks(record, text, community)`: `quorum` (`inOffice`, `present`, `unidentified`, `needed`, `standing`), `claimsQuorum`, `motions`, `confidential[]`, `kind`, `kindSaid`, `kindDiffers`, `pronouns[]`; rendered by `minutes_draft.check_lines` |
| The draft's gaps | `minutes_draft.draft(...)` returns `unsupported`, `gaps`, `unknowns` (the count of the "unknown" marker) |
| Record stages | `jason.tasks.record_stages.histories(community, data_dir)`: rule changes through 4360 (28 days, 15 days, and 4365's 30 days), and minutes with their approvals ("stated" or "listed") |
| Board items and the draft agenda | `board_items` (`jason.mcp.county`), `jason.tasks.board_items.agenda(...)` |
| Hearings | `hearings` (`jason.mcp.county`) |

## Layout: the watch

```
+------------------------------------------------------------------------------------------+
| Meetings & minutes                                                                       |
| Board meetings from Sep 3 to Dec 2, as of Oct 3: the notice each is owed and the minutes  |
| each owes. · synced Oct 3, 08:40 · jason meetings --sync [Sync]                          |
+------------------------------------------------------------------------------------------+
| Oct 7, 2099 · board meeting · from the schedule                                          |
|   Notice   by Oct 3 (4 days before, CIV 4920(a))  [LEGAL] [today]  none on record yet    |
|            Secretary, due Oct 3                  [Record a posting]                       |
|   Minutes  by Nov 6 (30 days after, CIV 4950(a))  [34 days left]   none on record yet    |
| Sep 9, 2099 · board meeting · held (Zoom record)                                         |
|   Notice   by Sep 5   on record in time: delivered (jason://notice/board-meeting-2099-09-09)|
|   Minutes  by Oct 9   [6 days left]   none on record yet   [Open the draft]               |
| * The schedule set a meeting on Aug 12 and nothing is on record near it: if it was held, |
|   its minutes are due by Sep 11.                                                         |
+------------------------------------------------------------------------------------------+
| None on record is not none given: a notice posted ... (CAVEATS, verbatim)                |
+------------------------------------------------------------------------------------------+
```

## Layout: one meeting, with its minutes draft

```
+------------------------------------------------------------------------------------------+
| Meetings & minutes > Sep 9, 2099 · board meeting                                         |
| Agenda [Document] · Recording [Record] · Transcript (open session) [Record] · Minutes: none|
+------------------------------------------------------------------------------------------+
| MINUTES DRAFT                  DRAFT until the board approves it · jason posts nothing    |
| data/board/minutes-draft-2099-09-09.md · drafted Sep 12 · checked Oct 3 [Re-check]        |
+-----------------------------------------------+------------------------------------------+
| THE DRAFT                                     | JASON'S CHECKS                           |
| # DRAFT Minutes of 9/9/99                     | Quorum: the record shows 3 of 5          |
| _Drafted by jason from the Zoom record of the |  directors on the call (Director A,      |
|  open meeting; every line is for the         |  Director B, Director C), with 0         |
|  Secretary to check._                         |  unidentified callers; a quorum is 3.    |
| ## Call to order                              |  Standing: present.                      |
| Called to order at 7:02 PM by [unknown]       | Lines naming a confidential subject: 1   |
|   ^ marked: for the Secretary                 |  "...discussed the delinquency of..."    |
| ## Business                                   |  -> read before the draft is shared       |
| ### 1. Landscaping contract                   | Lines that call a person he or she: 0    |
| - Motion: approve the bid ($4,200.00)         | Unsupported by the transcript: 1         |
|   Moved: Director A; seconded: [unknown]      |  business: approve the bid               |
|   Roll call: [unknown]                        | Blanks left for the Secretary: 5         |
+-----------------------------------------------+------------------------------------------+
| STAGES OF THESE MINUTES                                                                  |
| Draft on file Sep 12 · available to members: none on record · approved: none on record yet|
+------------------------------------------------------------------------------------------+
```

The two columns scroll together. A check that points at a line links to it, and the line carries a matching mark. Below 960 px the checks come first, above the draft.

## Components

`page-header`, `section-card`, `freshness`, `cli-hint`, `clock-row` (one per clock), `deadline-badge` (`--legal` on 4920 and 4950(a) clocks; `--passed` when the deadline passed with none on record), `status-badge`, `evidence-chip`, `job-status` (sync, draft), `diff-table` (a re-check's changes), `states` (empty), `states` (unavailable), `recitation` (the clock's authority, on demand), `reading-label` (a check is jason's count; it is labeled "jason's checks", never presented as the minutes' words).

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Sync | Reads Zoom and PayHOA's communications log, then rebuilds the meeting catalog. A read; a job | No | `jason meetings --sync` |
| Record a posting (a meeting notice) | For a general notice posted: `notice_ledger.set_general(key, posted, by)`. For the assignment that owns the clock: `api.record_completion(key, due, by, evidence)` | No approval: a signed `data/` record, logged. Needs a name and evidence ("Posted on the clubhouse board, Oct 2, 9:00") | `jason notices KEY --mark-general --posted "..." --by NAME`, or `jason schedule --done KEY DUE --by NAME --evidence TEXT` |
| Record the minutes made available | `api.record_completion(key, due, by, evidence)` for the minutes assignment | No approval: signed, logged | `jason schedule --done KEY DUE --by NAME --evidence TEXT` |
| Draft the minutes | `minutes_draft.draft(data_dir, community, day)` as a GPU job. It runs `local_ai.preflight` first and fails fast on the CPU or short of commit | No approval: it writes only `data/board/`. Logged with who started it | `jason board --minutes DAY` |
| Re-check | `minutes_draft.recheck(data_dir, community, day)`: the checks again, no model. Replaces the checks block | No | `jason board --minutes DAY --recheck` |
| Open the draft in an editor | Opens the file's folder on the machine (local only) | No | — |
| Write the agenda Doc | Plans `google.doc` (`board --agenda --doc`) | **Creates an approval** (phase 3, R1) | `jason board --agenda --doc` |
| Schedule a hearing on Zoom | Plans `zoom.hearing.create` | **Creates an approval** (phase 4, R3, two-person) | `jason hearing --create` |

**jason never posts, sends, or approves minutes.** The draft stays DRAFT until the board approves the minutes at a meeting. The board's approval reaches the console only as a record: a later meeting's minutes that state it, read by `record_stages`. "Approved" shows only when stated; an approval only listed on a later agenda shows as "listed, not stated".

## States

- **No meetings in the window:** "No board meeting in the window: the profile sets no meeting schedule, and the catalog holds none."
- **None on record yet** (deadline ahead): the clock's standing in words, with its deadline badge. Never "not given".
- **None on record; the deadline passed:** LEGAL, the badge `--passed`, and the first caveat inline: "None on record is not none given. If it was posted, record the posting."
- **A file in time, delivery not on record:** "a file in time; its delivery is not on record". A file never meets a notice clock.
- **No Zoom record for the day:** "Draft the minutes" is disabled with "No board meeting on Sep 9 in the Zoom record (`data/zoom`). Run `jason meetings --sync`."
- **No open-session transcript:** "The Sep 9 meeting has no open-session transcript to draft from."
- **Quorum not on the record, and the draft claims one:** the check reads "The draft says a quorum was present; the count does not support it. Correct the attendance, or the statement." It is shown first, with the `--soon` color.
- **Model unavailable:** the job fails fast with `local_ai.preflight`'s message and `jason local-ai` to check the stack.

## Privacy

- Executive-session material is listed by date only, outside the private view. The draft never holds it: the model is given the transcript only up to the executive break, and the executive section names only general subjects.
- Confidential lines in the open draft (the `CONFIDENTIAL` subjects of Civil Code 4935) are shown in full to the Secretary and manager, with the instruction to read each before the draft is shared. A director sees the count, and each line in the private view.
- Attendance names directors and callers as the record shows them. A caller shown only by a telephone number is shown as "unidentified caller" with the last four digits.
- Executive-session minutes in the stages band show only that they exist and their date.

## Acceptance criteria

1. The watch renders each meeting's clocks with `Standing`'s words, the deadline, and the authority, matching `Watch.as_dict()` for the fixture.
2. The caveats render verbatim, the first one above the fold.
3. No control posts, sends, publishes, or approves minutes. The words "post minutes" and "approve minutes" are not on any button.
4. Recording a posting refuses an empty name or evidence, and the watch then counts the record on the next render.
5. The checks column renders `check_lines` exactly, under the heading "jason's checks".
6. A check that names a line links to that line in the draft column.
7. Drafting refuses to start when another job holds the GPU lock, and says who holds it.
8. Executive-session material never appears with the private view off.
