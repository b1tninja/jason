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

## Not built yet

- Google Tasks for each role's open items, and Google Calendar events for the anchored and cadence items. The board calendar (`jason calendar`) and the action register's Tasks sync are the models to follow.
- Evidence read automatically: the minutes' items, a payment's category, a notice proof. Completions are recorded by hand for now.
- A role's holder from the board's private record, to address reminders.
