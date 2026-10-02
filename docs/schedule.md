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

## Not built yet

- Evidence read automatically: the minutes' items, a payment's category, a notice proof. Completions are recorded by hand for now.
- A role's holder from the board's private record, to address reminders.
