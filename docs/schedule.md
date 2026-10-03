# The schedule: every duty owned, and every clock set

The law, the governing documents, the notice catalog, and the recurring deadlines all impose duties. Many of them run on a clock: monthly reviews, yearly reports, deadlines counted from a meeting or a request. A duty no one owns is a duty no one does. The schedule makes sure each one is assigned, and each clock is set.

`jason sop duty-schedule` is the procedure.

## The records

`jason.community.schedule`; the profile's rows are `Community.assignments()`.

An `Assignment` has:
- **What it covers:**
  - a statute (`"CIV 5500"`);
  - a governing-document section, or a whole article or document (`"bylaws#9.6"`, `"bylaws#6"`, `"collection-policy"`);
  - a notice catalog requirement (`"notice:board-meeting"`);
  - a recurring deadline (`"obligation:<name>"`).
- **The role that owns it:** the board, an officer, the inspector of elections, the manager, counsel, jason, or the owners, with an optional backup. A role is the office. Who holds it is the board's record, kept privately.
- **When it falls due:**
  - `CADENCE`: monthly on a day, every N months, or each year on a month and day.
  - `ANCHORED`: a clock from an anchor the specification already keeps, either each board meeting (`MeetingSchedule`), the annual meeting, or the fiscal year's end (`Community.fiscal_year_end()`), so many days before or after it.
  - `EVENT`: a clock that an event starts (a records request, a hearing request, a lien payment). `handled_by` names the module that runs it.
  - `STANDING`: a continuing rule, owned but with no occurrence.
- **What shows it done:** the minutes, a payment, a jason store, or a notice proof.
- **The jason command** that does it or checks it.
- **Its adoption:**
  - `PROPOSED`: jason's proposal.
  - `ADOPTED`: the Board adopted it; `adopted` names the minutes or the resolution.
  - `DECLINED`: the note says how the duty is met instead.
  - `NOT_APPLICABLE`: the note says why.

## Commands

```bash
jason schedule                         # what falls due in the next 60 days, with each item's standing
jason schedule --role treasurer --days 120
jason schedule --assignments           # every assignment, its role, its clock, its adoption
jason schedule --coverage              # duties nobody owns, and duties on a clock that nothing schedules
jason schedule --done KEY 2026-10-20 --by NAME --evidence "minutes 2026-10-20, item 4"
```

- **An occurrence's standing:**
  - done: a completion was recorded for that day;
  - overdue;
  - due soon: within 14 days;
  - upcoming.
- **Completions** live in `data/schedule/done.jsonl`, which is private. Each names who did it and the evidence, and a completion with neither is refused.
- **The coverage check reads every duty jason knows of:**
  - the association's duties the governing documents state (`jason duties --documents`), where the bearer is the association, the board, an officer, a committee, the inspector, the manager, or unstated;
  - every notice requirement;
  - every recurring deadline.

  It reports two lists:
  - **Unowned:** no assignment covers the duty.
  - **Assigned, not scheduled:** a duty with a deadline or recurrence that only standing assignments cover.

  Both should be empty. A new document, amendment, or law usually adds to them.
- **`{REPORT:schedule}`** carries the next weeks' items and the proposed assignments into the board packet.

## Adoption

jason proposes the assignments. The Board adopts them, changes them, or declines them, usually all at once with a resolution, and amends them as offices change. Until the Board adopts an assignment, the schedule shows it as proposed. A duty whose clock comes from the law, such as the monthly financial review, is due whether or not the Board has adopted its assignment.

## On Google Calendar and Google Tasks (built October 2, 2026)

`jason.tasks.schedule_sync` puts the dated occurrences where people see them. Both are dry runs unless `--yes` is given.

```bash
jason schedule --calendar --tasks --plan-only   # the plan from disk; no Google call
jason schedule --calendar                       # read the calendar; print planned beside existing
jason schedule --tasks                          # read the role lists; print what would be created, patched, recorded
jason schedule --calendar --tasks --yes         # write both (Tasks first, so a check-off shows done on the calendar)
jason schedule --calendar --calendar-id ID --months 6 --past 30
```

- **The window.** From `--past` days back (default 30) to `--months` ahead (default 3). The days back let an occurrence done since the last run be marked done.
- **Calendar.** Each CADENCE and ANCHORED occurrence is an all-day event that does not block time, through the board calendar's own sync (`jason calendar`):
  - Its key, in `extendedProperties.private.jason`, is `schedule:<assignment>:<due day>`. A re-run patches the event; nothing is deleted, and an event without jason's key is never changed.
  - Its title is "Due: " (or "Done: " once a completion is recorded), the assignment's title, and its role in parentheses. A role is an office. No event names a person or an address. A completion's `by` stays in jason: the event says only the day it was recorded done.
  - Its description gives the owner and backup, the clock, the adoption, what shows it done, the jason command, and how to record it.
  - An occurrence the board calendar already carries on the same day is left to `jason calendar` and not added twice: the meeting itself (an assignment covering CIV 4900), its notice deadline (CIV 4920 or `notice:board-meeting`), and a recurring deadline the assignment covers (`obligation:<name>`). Those are on the calendar only when `jason calendar --yes` has run.
  - Each command reports only its own kind of keyed event as no longer planned. The board's events are `jason calendar`'s; the `schedule:` events are this command's.
- **Google Tasks.** One list per role, `Schedule: <role>`, in the account the Tasks token signs in to (`google-tasks-token.json`, the same token as the action register's list). A dry run creates no list.
  - Each open occurrence in the window is a task with its due day. Its notes carry jason's marker (`jason:schedule:<assignment>:<due day>`), so a re-run patches it. An occurrence recorded done completes its task.
  - **A task checked off in Google is recorded done** in `data/schedule/done.jsonl` at the next `--yes` run: done on the day Google says it was completed (in the association's time zone), `by` "Google Tasks", evidence "checked off in Google Tasks on DATE (Schedule: ROLE)". The Tasks API names neither the account nor who checked it off, so `by` cannot be a person.
  - **That is weaker evidence than the minutes.** It shows only that someone using the account marked the task, not that the duty was met. Record the real evidence as well, with `--done KEY DUE --by NAME --evidence TEXT` (both rows are kept; the schedule shows the later one).
  - A task jason no longer plans, or an open one due before the window, is reported, never deleted. A task on another role's list (the role changed) is patched where it is and reported.
- **Credentials.** A run without `--plan-only` reads Google. Without a token, a non-interactive run fails fast (`GoogleAuthRequired`). Only `--interactive` opens a browser to sign in.

## Evidence

`jason schedule-evidence` finds the evidence on disk that each occurrence was done and proposes it for a person to confirm. It never records anything on its own. `jason.tasks.schedule_evidence` does the work; the rules are `jason.community.schedule_evidence`.

```bash
jason schedule-evidence                              # the past year's occurrences that have evidence
jason schedule-evidence --since 2024-01-01 --key KEY --all          # one assignment, with the misses
jason schedule-evidence --record KEY 2026-01-20 --by NAME            # confirm one, with the evidence found
jason schedule-evidence --record KEY 2026-03-17 --by NAME --on 2026-03-20 --evidence "the person's own words"
```

- **The rules are data.** An `EvidenceRule` serves the assignments that cover one of its references, such as a statute (`CIV 5500`), a notice catalog key (`notice:board-meeting`), or a prefix (`obligation:`). Each rule names:
  - where jason looks;
  - the words it looks for, as regular expressions, and any words that must be near them;
  - how much a hit says:
    - **direct**: the record says the duty was done;
    - **supporting**: the record makes it likely, and a person reads it;
    - **against**: the record says the duty was done wrongly, such as a notice sent too late.

  jason's own rules serve the statutes and the notice catalog. A profile adds rules for the duties it covers by its own documents' sections, or for the words its minutes use (`Community.evidence_rules()`). The profile's rules are tried first.
- **Where jason looks:**
  - **The minutes' text.** jason reads the minutes of the meeting the occurrence falls on and quotes the passage. A meeting-anchored occurrence takes the meetings held in that month, or within ten days of the scheduled day. Any other occurrence takes the meetings in the rule's window. Confidential minutes are neither searched nor quoted.
  - **A report the minutes name.** This is a stored reading, such as a treasurer's report, whose name the minutes carry, with the lines of it that hold the words (for example, its bank reconciliations). If the minutes name more than one copy, jason uses the copy named most fully, which is the one the board was given.
  - **The meeting catalog.** It shows:
    - the notice to members and how many days before the meeting it went out (an emailed agenda counts only when no notice is on record);
    - the minutes on file and the earliest date any copy carries;
    - whether the meeting was held.
  - **Mailings.** PayHOA's communications log, jason's own sends, the Mailroom log, and the notice delivery ledger, inside the rule's window.
  - **The library.** A file of the kind the duty produces, for the year.
  - **Payments.** The obligation rows' payments (`jason deadlines`), for an assignment that covers a recurring deadline. Each fixed deadline that PayHOA shows paid becomes an occurrence. A late payment counts as evidence against.
- **An occurrence's standing:**
  - **proposed:** direct evidence and nothing against;
  - **partial:** supporting evidence only;
  - **contrary:** some evidence against;
  - **none:** nothing found;
  - **recorded:** a person has already recorded the occurrence done.

  A miss stays a miss. Minutes that record the review in other words are not found, and nothing found is not proof the duty was not done.
- **Recording.** `--record` calls `record_done` with the name of the person who confirms it, the evidence found (or the person's own, with `--evidence`), and the day of the evidence (or `--on`). The run's proposals are kept in `data/schedule/evidence.json`, which is private.
- **What the minutes show.** A report the minutes name shows what the board had before it, not that the board reviewed each part. To show the monthly review (Civil Code 5500), or its ratification under 5501, the minutes should say so in words: "The board reviewed the reconciliations of the operating and reserve accounts for MONTH," or "The board ratified the review of MONTH's financial documents made under Civil Code 5501."

## Not built yet

- A notice's proof-of-notice record (`jason notices KEY --proof`) as evidence for the notice assignments. The evidence finder reads the meeting catalog's notice days and the ledger's sends, not the proof's window.
- A role's holder from the board's private record, to address reminders.
