# Record stages: rule changes and minutes

Every association record has versions, each made by an event at a stage. The shared model is `jason.community.revisions` (`Stage`, `RecordVersion`). `jason record-stages` builds the histories of two series jason already tracks:
- the operating rule changes (Civil Code 4355 to 4365);
- the board minutes (4950).

It reads disk only, writes nothing, and decides nothing. A miss stays a miss: "none on record" is not "none given".

```bash
jason record-stages                         # both series; minutes from January 1 last year
jason record-stages --rules                 # only the rule changes, with leads
jason record-stages --change example-2031   # one rule change
jason record-stages --minutes --since 2024-01-01
jason record-stages --meeting 2031-02-12    # one meeting's minutes
jason record-stages --json                  # the rows a tool would show
```

The read-only function for a tool is `jason.tasks.record_stages.histories(community, data_dir, since=..., on=...)`. Its rows never carry an executive session's minutes beyond that they exist and their date.

## A version is cited as itself

A version not in force is cited by its stage and day (`RecordVersion.label()`): `example-rules@proposed-2031-01-06`, `min/2031-01-08@draft-2031-01-12`. It is never merged into the text in force. A version in force is cited by the day it took effect: `example-rules@2031-02-12`.

## Rule changes (Civil Code 4360)

| Stage | The event | The law | Evidence jason reads |
|---|---|---|---|
| `draft` | the text as written | | a file of the rule's text dated before the decision; for a draft in the specification, its row and its board page |
| `proposed` | general notice with "the text of the proposed rule change and a description of the purpose and effect", at least 28 days before the decision | 4360(a) | the notice's file (its source, which every proposed version cites), and its delivery: the notice ledger (`rule-change-proposed-<key>`, at its strength), PayHOA's log, the Mailroom |
| `adopted` | the decision at a board meeting, after considering members' comments | 4360(b) | the minutes of the decision meeting, where they name the change |
| `distributed` | general notice of the change, not more than 15 days after it | 4360(c) | the notice of the adopted change: its file and its delivery |

Then the members' right to reverse it (4365):
- Members owning 5 percent of the separate interests may call a special vote by a written request "not ... more than 30 days after the association gives general notice of the rule change" (4365(b)).
- jason gives the last day when the notice's delivery is on record.
- With no delivery on record, it says the 30 days' end is not shown.
- 4365 does not apply to an emergency change (4365(h)), and 4360(a)'s notice is not required for one (4360(d)).

### Where the rule changes come from

**The profile's rows.** `Community.rule_change_records()` gives `RuleChangeRecord` rows (`jason.community.record_stages`): the association's own rule changes, made or proposed. A row names:
- the rule document (its key is the book of the versions);
- `files`: a pattern for the change's own files by name;
- `notices`: files that are the notice of the proposed change although their names do not say so;
- `words`: what the minutes call the change;
- `decided`: the decision meeting;
- `outcome`;
- `tasks`: a pattern for a Google Task that plans a step;
- `emergency`.

**The specification's drafts.** `Community.rule_changes()` gives the drafts `jason rule-change` builds notices from. A draft the profile's rows do not name is read as `draft` until its notice is on record.

**Leads.** These are listed for a person to read. A rule change becomes a row once confirmed.
- Files named "Notice of Proposed Rule Change" or "Notice of Adopted Rule Change" that no row claims.
- Minutes passages about rule changes on days no row names.
- Board pages (`data/board/rule-change-*.md`) with no draft in the specification.

### The evidence, by strength

A notice's evidence is read by one shared reader, `jason.tasks.notice_evidence`, which the meeting watch and the evidence finder use too ([notices.md](notices.md#how-strongly-the-record-shows-a-notice-given)). Its strengths come first:

| Strength | Meaning |
|---|---|
| delivered | the notice ledger shows every member it holds reached by a method the notice allows; or a general notice recorded as posted where the policy statement designates (4045(a)), with the 4045(b) individual deliveries |
| sent, with follow-ups owed | the ledger shows members owed a resend: a bounce (4041(e)), a returned letter, a member with no address on file; the follow-ups are listed with the clock |
| sent | it went out, but its outcomes are not synced: PayHOA's communications log, jason's sends, the Mailroom, a ledger whose attempts have no outcome yet |
| stated | the minutes say it was done |
| listed | named on an item the minutes carry; the outcome is not written |
| emailed | a copy sent from the association's mail; to whom is not read |
| file | a file written that day (the earlier of Drive's created and modified days); its delivery is not on record |
| planned | a Google Task to do it; never counted as done |

A 4360 clock is met by "delivered" on time, or by "sent" (with follow-ups owed, or not synced) on time, with what is owed in the clock's note. Of the records on time, the strongest judges the clock, then the earliest. A file never meets a clock: a file in time is "a file in time; its delivery is not on record", and a person confirms how and when it went out (`jason notices KEY --sync`, or `--mark-general` for a posting).

### The notices' addresses

When the notice ledger holds a stage's notice, the history names it:
- each clock carries the notice's address (`jason://notice/rule-change-proposed-<key>`), in its row (`notice`) and its line;
- `RuleChangeHistory.notices()` (the row's `notices`) gives each stage's notice addresses;
- a proposed version with no file for its words cites the notice's address.

The link runs both ways: `jason cite jason://notice/rule-change-proposed-<key>` names the rule change, the stage it served, its version, and its clock ([record-addresses.md](record-addresses.md#a-notice-as-a-record)).

Whether a rule is on a 4355(a) subject is for counsel. So is whether a change was one the law required with no discretion (4355(b)(4)). jason reads every change against 4360.

## Minutes (Civil Code 4950)

| Stage | The event | Evidence jason reads |
|---|---|---|
| `draft` | "minutes proposed for adoption that are marked to indicate draft status", or the minutes, available to members within 30 days (4950(a)) | the first copy on record dated on or after the meeting (a copy made ahead is a template) |
| `approved` | a later meeting's minutes record the approval | the approval item in each later meeting's minutes: the meetings it names, or "the previous meeting" |
| `corrected` | a later meeting approves them as corrected, or a corrected copy is filed | "as corrected" or "amended" in the approval item; a copy named corrected, amended, or revised |

How each history is built:
- **Copies.** Every copy of a meeting's minutes on file is listed with its earliest date: Drive, the PayHOA library, and Gmail attachments, counted by name.
- **Approved text.** The approved version cites a kept file (Drive or the library), not an email attachment. When the only copy is dated before the approval, the approved words are that copy as it now stands.
- **The 30-day clock.** It is read as `jason schedule-evidence --watch` reads it (`schedule_evidence.minutes_on_record`).
- **How an approval is read:**
  - **Stated:** the approval item's words say it passed ("approved", "M/S/P", a motion carried), or the text says the board approved the minutes.
  - **Listed:** the item only names the meeting. Minutes written on the agenda's outline often list the approval item and nothing more.
- **Approved twice.** When a meeting is named on the approval item of more than one later meeting, the first may have deferred it; the note says so.

### Executive sessions

Executive-session minutes are restricted (4935). A copy the meeting catalog marks confidential shows only that it exists and its date, in rows and in lines. A meeting held solely in executive session owes no open minutes (4950(a)). Its matters are generally noted in the next open meeting's minutes (4935(e)). The 30-day clock also leaves out confidential copies, so an executive session's minutes never count as the open minutes being available.

### The summary

For the board meetings since `--since` whose 30 days have run, the summary counts:
- a copy on record in time, late, undated, or none;
- the approval: stated, only listed, or none;
- meetings with neither a copy in time nor an approval;
- separately: executive sessions only, members' meetings, and meetings whose kind is not on record.

## Caveats

- None on record is not none given. A notice posted or mailed where jason does not look, or minutes made available that way, are not on disk. A person confirms what was done and records it (`jason schedule --done`).
- "Delivered" is the ledger's word for every member it holds; the members the plan named but no batch reached are not in the ledger. Compare the recipients plan's counts on the notice's record.
- A file's date is the day it was written by, not the day it reached the members.
- A history is read from the stores as last built: the meeting catalog (`jason meetings`), the Drive index, the library, the readings, PayHOA's communications log, and Gmail.
