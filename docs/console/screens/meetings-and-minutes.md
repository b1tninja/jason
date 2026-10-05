# Meetings & minutes

Bands added to `#/meetings` and `#/minutes-review` · phase 2 · CLI: `jason schedule-evidence --watch`, `jason meetings`, `jason record-stages`, `jason board`

## In the console

The Governance group already runs the board loop:

| Console screen | What it does |
|---|---|
| **Meetings and minutes** (`#/meetings`, `ConsoleMeetings`; owner view too) | Each meeting's records on hand (agenda, notice, minutes, transcript, recording) and its checks (no minutes 30 days on, a recording held after the minutes, a transcript into executive session), with scheduled days that have no record |
| **Next meeting** (`#/meeting`) | One meeting: the last days to give notice (CIV 4920: four days, two for a meeting held solely in executive session, or the governing documents' longer period, `Community.board_notice_period()`, with its source), items by session (an executive item's title only in the private view: see [Executive items on the meeting page and the plan](#executive-items-on-the-meeting-page-and-the-plan)), the agenda draft, the packet with each item's packet files as jason's copies (`DocumentPreview`) and "Read every packet file from Drive", the minutes frame, and the commands that write each Doc |
| **Plan a meeting** (`#/agenda`, `ConsoleAgenda`) | The four-step `AgendaWizard`: meeting, ready to act, order and motions (each packet file attached with its `DocumentPreview`: thumbnail, Preview, Read from Drive, Open in Google), notice. The notice lines: 4920 always; a hybrid meeting's location and director or designee (4090(b)); 4926's join instructions, help contact, individual-delivery reminder, and telephone option only for a meeting held entirely by teleconference. A line that is jason's check says so |
| **Meeting room** (`#/room`, `ConsoleMeetingRoom`) | `MeetingStage` and `HostPanel`: attendance, motions, roll calls by name, the CIV 4930 guard, executive session as the host's act; draft minutes go to Approvals for the secretary. A packet file "shown on stage" is jason's copy, opened as one logged view and shown inline for the board; with no copy, its preview card. Members (`audience=owner`) see only a card naming it ("members receive the packet with the agenda"). Never a frame of Google. The executive session is kept apart: see [The meeting room's executive session](#the-meeting-rooms-executive-session) |
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
| The checks | `minutes_draft.checks(record, text, community)`: `quorum` (`inOffice`, `present`, `unidentified`, `needed`, `standing`), `claimsQuorum`, `motions`, `confidential[]`, `executiveParticulars[]`, `executiveSources` (`plan`, `wording`, `not named`), `kind`, `kindDiffers`, `pronouns[]`; rendered as `minutes_draft.check_lines`; the draft's `unsupported`, `gaps`, `unknowns` | add to `minutes-review` |
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

## Documents

Each screen shows its documents with `Doc`, fed the loader's `DocRef`s ([doc-component.md](../doc-component.md)); never a raw `/api/file` link, a frame of Zoom or Google, or a path as text.

| Screen | Document | Reference (loader) | Variant | Level |
|---|---|---|---|---|
| Meetings and minutes (`#/meetings`) | A meeting's notice, agendas, minutes (draft and final), transcript, and recordings, by record kind, the posted copy first; shown when a person opens the meeting's **Records** | `GET /api/meetings?date=` → `docs: [{kind, docs: [DocRef]}]` (`jason.web.extra.meeting_docs.record_refs`): `library:<id>` for the PayHOA library, `drive:<id>` for Drive, `file:` for jason's drafts, its Zoom copies, and Gmail attachments | `row` (a `DocList` per kind) | the server's: a library or Drive file by its flag, `board/` P1 (executive minutes P3), `zoom/meetings/` by the Zoom index |
| | Zoom's cloud, a Gmail message, PayHOA's mailing log | none yet (no resolver): they stay badges in the table | — | — |
| Minutes review (`#/minutes-review`) | The Zoom transcript the draft was read from, beside the draft, so the Secretary checks each line against it | `transcriptDoc`: `file:zoom/meetings/<folder>/transcript.txt`, the day's board meeting in the Zoom index (`minutes_review.transcript_file`) | `inline` (viewed on mount at P1; "Show the document" first at P3) | P1 for an open meeting; P3 when the index marks it confidential, an executive session, or a hearing |
| | The filled minutes | `minutesDoc`: `file:board/minutes-<date>.md`; `minutesFile` is that path under the data folder | `chip` (the drafts table, the review's header, after a save) | P1 |
| | The draft | `draftDoc`: `file:board/minutes-draft-<date>.md`; the list's `file` is that path under the data folder | (the form and its preview show it) | P1 |
| Hearings (`#/hearings`) | The hearing notice: the Doc made from the template, then jason's draft beside the plan | `noticeRefs`: `drive:<noticeDoc.id>`, then `file:zoom/hearings/<file>` (`meeting_docs.hearing_refs`) | `card` (a `DocList`) | P3: opened only in the private view |
| Next meeting (`#/meeting`) | The meeting's Zoom recording | Zoom's share page is the original, an **Open in Zoom** link in a new tab, never a frame. The kept audio (`zoom/meetings/<folder>/audio.m4a`) is still an `Embed` of `/api/file`: `Doc` does not play audio inline yet, and the `file:` resolver serves no `.m4a` | link; audio pending | the Zoom index's |
| Decisions (`#/decisions`) | The documents a matter's evidence names, as the brief's **Sources**, under the facts a person wrote (which stay text); the same chips under the brief form while no brief is written | `GET /api/agenda-plan` → each candidate's `evidenceRefs` beside its `evidence` strings (`jason.approvals.docref.refs_from_strings`): `library:`, `drive:`, `file:`, or a citation; a `jason …` command stays a command to copy and anything else stays text | `chip` (`DecisionBrief`'s optional `sources`) | the server's |

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

## The meeting room's executive session

Civil Code 4935(e), as stored on disk: "Any matter discussed in executive session shall be generally noted in the minutes of the immediately following meeting that is open to the entire membership." The minutes members receive are those of a board meeting "other than an executive session" (4950(a)). The room keeps two records:

| Record | Holds | Level |
|---|---|---|
| `meetings/room-<date>.json` (the open record) | Everything in open session; for an executive session only: "The board adjourned to executive session at TIME to discuss SUBJECTS (Civil Code 4935(…))", and "The board met in executive session from TIME to TIME to discuss SUBJECTS (…). The board returned to open session." The executive state keeps the general note, the subjects, and each session's times | P1 |
| `meetings/room-<date>-executive.json` (the executive record) | Each session's matters (id, 4935 subject, title), and every log entry, motion, roll call, and admission made while the room is in executive session; the chair's free note | P3: the private view only |

- **The general words** are the matter's `ExecutiveSubject` in the statute's words (`EXECUTIVE_GENERAL_TERMS`: litigation; matters relating to the formation of contracts with third parties; member discipline; personnel matters; a member's payment of assessments; whether to foreclose on a lien), with the subdivisions that name it. Never the item's title or id, which can name the member or the matter.
- **A matter with no 4935 subject cannot go into executive session.** The plan carries it (`subject` on an agenda plan item), or the chair names it in the room's Zoom tab before starting; until every matter has one, "Start executive session" is not offered and the store refuses: "name the 4935 subject first".
- **Motions in executive session** are the executive record's (`x1`, `x2`, …), voted and decided there, and recorded in `board/decisions.json` with `session: "executive session"` and the matter's `subject`. The meeting page, the decisions screen, the Dock, and the minutes draft leave such a decision out and note it by its subject (`decisions.open_only`, `general_notes`); the decisions screen lists it only in the private view, counting it as held back otherwise. A motion is voted in the session it was moved in; an open motion on the floor is decided before the board adjourns. Polls and transcript suggestions wait for the open session.
- **The loader** (`GET /api/meeting-room`) answers anyone who opens the room, members included, so outside the private view its `executive` is `{shown: false, record: null, note: "Executive session: the record is kept apart (open the private view to see it)."}` and the executive item carries only `matters` (the general words) and `executiveMatters` (`ref`, `subject`, `general`, `named`). For a signed-in person whose private view is open and whose offices open P3, it adds the record and the matters' ids and titles, and logs the answer in `access/served.jsonl` under the executive file's path.
- **The host panel:** "Prepare draft minutes" builds the letter from the open log only (`minutesLetter`). While the room is in executive session, the Minutes tab shows the executive log in the private view and the held line otherwise; the Motion and Roll call tabs work on the executive record's motions, so the host opens the private view to run them.
- **The members' stage** shows the hold card for as long as the room is in executive session, with the general note only.
- **Room files written before the record was kept apart** are not rewritten: `python -m jason.tasks.meeting_room --check-executive DATE` (or `all`) counts the open entries that fall inside an executive window, never their text, for a person to decide what to do.

## Executive items on the meeting page and the plan

- **The agenda draft and the minutes frame** (`GET /api/meeting`'s `agendaMarkdown`, `minutesTemplate`; `board_items.agenda`) name an executive matter only by its 4935 subject, in the private view too: one "Adjourn to executive session" item whose lines are `meeting_agenda.executive_lines` (the agenda plan's subject; else jason's reading, flagged to confirm; else a blank).
- **The items** (`GET /api/meeting`'s `items`): an executive item's title, ask, notes, evidence, and id are listed only in the private view, logged in `access/served.jsonl` as `board/items.json`. Otherwise it is a held row: `executive-<n>`, `held`, `subject` and `general` (the plan's subject), with its priority and status; `executiveHeld` counts them and `executiveHeldNote` says so. The page records no decision on a held row.
- **The plan** (`GET /api/agenda-plan`, Plan a meeting and Decisions): an executive candidate is held the same way (logged as `meetings/plan-<date>.json`): its place on the agenda, minutes, 4935 subject, and readiness, never its title, ask, motion, packet, brief, or id; the history names it `executive-<n>`, and its `jason board --set` command is given in the private view only. A held candidate cannot be toggled, briefed, or decided until the private view is open.
- **Whole for callers that hold back themselves:** the meeting room and the plan call the loaders with `private=True` and apply the private view to their own answers.

## The meeting room on a phone

- **Under 720px** the host panel is a bottom sheet (`HostPanel sheet="auto"`): a grab handle ("Host panel" / "Hide the panel"), the tab row, then the scrolling body. It starts collapsed to the handle and the tabs; a tab tap opens it. Collapsing keeps the tab's draft (a motion's text, an unrecorded roll call).
- **The stage stays on top.** Previous and Next sit in a sticky row under it with 44px targets, above the collapsed sheet, so a director advances without opening the sheet. Each still goes through its confirm.
- **Nothing else changes:** the same tabs, confirms, executive-session hold, and private view as at desktop width.
- **Serving the console to a phone is a deployment decision, not a layout one.** jason-web binds 127.0.0.1 until sign-in and the access policy allow more ([security-and-privacy.md](../security-and-privacy.md)).

## The meeting room's rules: quorum, vote, recusal, open forum

The room counts by the profile's `BoardRule` and policies, never by jason. The loader's `rules` (`meeting_room.board_rules`) gives each with its source: the bylaws' provision, its words recited from disk (`jason cite`), or counsel's reading, labeled as a reading. A rule not on file says "not on file; ask counsel", with what the room counts meanwhile, labeled.

| Rule | From | Not on file |
|---|---|---|
| Quorum | `BoardRule.quorum()`, `source` | a majority of the directors listed, labeled a reading |
| What carries a motion | `BoardRule.vote_basis` (`VoteBasis`), `vote_source` | a majority of the directors present, labeled a reading; the decision's notes say so |
| Whether a recused director counts toward the quorum and among those present | `BoardRule.interested_in_quorum`, `interested_source` | the tally is worked both ways (`readings`); a vote the two decide differently is `held`, and the store refuses to record it |
| Two-thirds for an off-agenda emergency item | CIV 4930(d)(2) | (the statute) |
| Open forum, minutes each | `Community.open_forum_limit()` (`SpeakingLimit`), or a limit a person enters in the room (`limitBy`) | "No limit on record; the board sets it (CIV 4925(b))." No clock, no allotment, never a default |

- **A recusal is the director's disclosure,** entered by the secretary on the motion (`recused`). jason infers none. CIV 5350(b) lists the matters an interested director "shall not vote" on; a contract is 5350(a), which applies Corporations Code 7233 and 7234. 7233 is not on the authorities shelf: how it counts the director is counsel's to read.
- **The decision records it:** `decisions.Decision.recused`, never "absent" and never a no. `DecisionCard` takes it, and the minutes draft is given it.
- **A limit stored with no person behind it** (the room's earlier 3-minute default) reads as no limit on record.

## Table, continue, refer, and withdraw

Table, continue, and refer are motions the board votes on (`meeting_room.MOTION_KINDS`). Nothing disposes of an item without a vote except a withdrawal.

| Motion | `motion_draft` adds | Carried |
|---|---|---|
| Table | `kind: "table"` | Decision outcome `tabled`. The item stays on the board's list for a later motion to take it from the table |
| Continue | `kind: "continue"`, `meeting` (a later date) | Outcome `continued`. The board item's `meeting` is set to that date |
| Refer | `kind: "refer"`, `to` (a committee or person, named) | Outcome `referred`. The board item's `owner` notes the referral. jason names no one |

- **Like any motion:** two different directors present move and second, neither recused. The roll call runs under the same threshold and the same `BoardRule`. A vote that the two recusal readings decide differently is held. The open log and the minutes letter carry the motion line and the roll call. In executive session all of it goes to the executive record.
- **Against a motion on the floor:** the subsidiary motion applies to the item's pending motion (`appliesTo`) and is decided first. Only one is on the floor at a time. Carried, the pending motion's result becomes the word. Failed, the pending motion is back on the floor.
- **The decision:** `decisions.Decision.kind` with id `<date>--<item>--<kind>`, so it never replaces the main motion's decision. A failed subsidiary motion records `denied`.
- **Withdraw** (`withdraw`, `{motion}`): the mover's act before any vote is recorded. It is logged with no roll call and no decision, and the motion's result is `withdrawn`.
- **The stamp:** after the vote, the stage, the agenda list, and the Motion and Roll call tabs show the motion's word (`motionWord`): `tabled`, `continued`, `referred`, `carried`, `failed`, or `withdrawn`.

## Privacy

- Executive-session material is listed by date only. The draft never holds it: the model is given the transcript only up to the executive break, the room's open record only, and an executive decision only by its 4935 subject in general terms. An executive item on the agenda Doc goes only by its 4935 subject (the agenda plan's, else `classify_executive` on its words), never its own words; one with no subject goes as a blank for the Secretary.
- The checks count each line about the executive session that uses the agenda's own words for an executive item (`executiveParticulars`), and say how many items' subjects came from the plan, from jason's reading, or are not on record (`executiveSources`); the block never quotes them.
- Confidential lines in the open draft (Civil Code 4935 subjects) are shown in full to the Secretary and manager, with the instruction to read each before the draft is shared.
- A caller shown only by a telephone number is "unidentified caller" with the last four digits.
- The owner view shows the meetings' records as built, not the watch's assignments or the checks. Its loader (`meetings?view=owner`) sends each meeting's open-session records on file alone: the notice, the agendas, and the minutes (draft or approved) where they are posted (the PayHOA library, Drive, a PayHOA communication), never confidential. No title (a call's topic can name a hearing), no transcript, recording, chat, or summary, no executive session agenda, no jason draft, no checks or schedule gaps, and no meeting with no member record.
- The owner view's meeting room is the stage alone (`meeting-room?view=owner`): the open items, the current one, the directors present, and the motions on open items. The executive item is "Executive session" with nothing of its matters; no owner roster, log, polls, admitted names, packet, brief, or commands.

## Acceptance criteria

1. The watch renders each meeting's clocks with `Standing`'s words, the deadline, and the authority, matching `Watch.as_dict()` for the fixture; the caveats render verbatim, the first one above the fold.
2. No control posts, sends, publishes, or approves minutes. The words "post minutes" and "approve minutes" are not on any button.
3. Recording a posting refuses an empty name or evidence, and the watch counts the record on the next read.
4. The checks render `check_lines` exactly, under "jason's checks", and a check that names a line links to it.
5. Executive-session material never appears.
