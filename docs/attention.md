# What needs attention

`jason attention` reads the stores the governance commands keep and says, in one place, what needs a person: clocks passed or near, questions open, follow-ups owed. It is the same digest as the MCP tool `governance_digest` (`jason.api.governance_digest()`) and the board packet's `{REPORT:attention}`. The code is `jason.tasks.attention`.

```bash
jason attention                       # every section, eight lines each
jason attention --section requests    # one section (repeatable)
jason attention --section meetings    # the board meetings' notice and minutes clocks
jason attention --limit 20 --json     # more lines, as JSON
jason attention --private             # units left out, as the packet prints it
jason attention --on 2026-11-01       # read a given day as today
```

## The sections

| Section | Reads | What it lists | Detail |
| --- | --- | --- | --- |
| The board meetings' clocks | the meeting schedule, `data/meetings/catalog.json`, the Zoom index, `data/schedule/done.jsonl` | each board meeting's notice to members (Civil Code 4920) and minutes (4950(a)) against the record: a deadline passed with none on record or a record dated past it, a deadline within two weeks with none on record yet, minutes on file undated past their deadline, a scheduled day behind with nothing on record. The counts carry every meeting watched. | `jason schedule-evidence --watch` |
| The schedule | the assignments, `data/schedule/done.jsonl`, the duties store | each occurrence overdue (the last 30 days, `--past`) or due within two weeks, by role; the duties nobody owns | `jason schedule --role ROLE`, `--coverage` |
| Members' requests | the stored PayHOA requests and the owners' email threads | each unanswered request past or near its clock, or past its acknowledgment day; a statute's clock first | `jason respond --kind KIND` |
| Intake questions | `data/intake/asks.json` | open questions by kind (what an amendment changed first, OCR slips last), the likely ones apart, answers not yet applied | `jason intake --kind KIND`, `--likely`, `--apply` |
| Conflicts | the specification's conflict rows | open conflicts: with counsel, on the board's register, then noted with no one acting | `jason conflicts --open` |
| Notices | `data/notices/deliveries.db` | every notice in the ledger with a follow-up owed: a resend the law requires, one the association's policy asks, an address to ask for | `jason notices KEY` |
| Living documents | each one's last build, `data/living/KEY/report.json` | a rule row the current text no longer bears out, a source held, the working copy's drift, the findings, a build over 30 days old, a document never built | `jason living KEY` |
| Timed duties | `data/duties/*.json` | the association's duties with a deadline or recurrence that no recurring deadline, calendar event, notice rule, or assignment carries; owners' duties as a count | `jason duties --documents KEY --timed --untracked` |

Every line names the command that gives its detail; each section names its MCP tool.

## Urgency

Each line has one urgency, and the digest orders by it, then by what sets the clock (a statute, then the governing documents, then a policy), then by the day due:

1. **LEGAL**: a clock the law or the governing documents set has passed (a records request past its statutory days, a duty the bylaws set left overdue, a meeting's notice day passed with none on record, minutes dated past their 30 days), or the law requires a delivery again (an emailed notice that bounced is resent by mail).
2. **OVERDUE**: past a clock a policy sets, adopted or proposed. Requests past a proposed policy's clock by more than 90 days are summed on one line: most were settled outside the record and need answering or closing where they were made.
3. **due soon**: within the schedule's two weeks or a request's five days; a failed rule check on a living document.
4. **open**: waiting on a person, with no clock.
5. **noted**: for the record.

Sections are ordered by their most urgent line. The packet's report prints five lines a section (`{REPORT:attention limit=8}` sets it; `section=requests` narrows it).

## Robust by section

Each section is read on its own. One whose store is missing or broken is reported as unavailable with the reason (`Unavailable: ...` under the totals, `"unavailable"` in JSON), and the rest of the digest stands. Requests made by email and the schedule's coverage check are optional parts: when they cannot be read, the section says so in a note and keeps the rest.

## What it does not do

- It reads disk only. Sync each system first for the latest (`jason notices KEY --sync`, `jason living KEY --fetch`, the PayHOA request sync).
- It writes nothing. Opening the notice ledger never creates it, and a missing duties store stays missing.
- It decides nothing. A clock is computed; a conflict is noted; a follow-up is a person's send through the command that guards it; an assignment is a proposal until the board adopts it. A schedule item done but not recorded shows as overdue until someone records it (`jason schedule --done`).
- A meeting's clock with none on record is not proof none was given: a posting is not on disk. Once a person confirms one, `jason schedule --done KEY DUE --by NAME --evidence TEXT` records it and the meetings section counts it. The meetings section reads the catalog as last built (`jason meetings --sync` reads Zoom and PayHOA's log and rebuilds it), and leaves the schedule section the assignments it reads, so a meeting's notice is not listed twice ([schedule.md](schedule.md), The watch).
- A notice is read as individually delivered. A general notice that was also posted owes fewer resends: `jason notices KEY --general` says which.
