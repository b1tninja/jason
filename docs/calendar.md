# Board calendar

`jason calendar` puts the board's meetings, notice deadlines, hearings, and recurring deadlines on Google Calendar. It reads what jason already has on disk and the specification. It is a dry run unless `--yes` is given.

## What is planned

| Event | From | When |
|---|---|---|
| Board meeting | the schedule (`meeting_schedule`), monthly in practice | the schedule's hour, 90 minutes, in the association's time zone |
| Notice and agenda due | each meeting | all day, four days before (CIV 4920(a); two for a meeting held solely in executive session, 4920(b)(2)), or the governing documents' longer period with its source (`Community.board_notice_period()`, 4920(b)(3)) |
| Board hearing | `data/zoom/hearings.json` (`jason hearing`) | the hearing's start, the hearing policy's length |
| Hearing notice due | the saved hearing | all day, on its `noticeBy` (CIV 5855(a); Corp 7341(c) to suspend) |
| Hearing decision due | the saved hearing | all day, on its `decisionByIfHeld` (CIV 5855(f)) |
| Deadline | `jason.tasks.deadlines.calendar` (taxes, filings, insurance terms, the reserve study) | all day, on its next date in the window |

- A meeting in a regular month of Administrative Resolution 20230130-1 is titled a regular meeting; the other months' are special meetings under it. The titles are `CALENDAR_POLICY` in `mystique/board_calendar.py`.
- The location is the Zoom link the saved agendas carry for the meeting ID of the last board meeting in `data/zoom/meetings.json`; without one it is the schedule's place.
- A hearing's title is "Board hearing". No event names the owner, the address, or the violation (CIV 4935). Its key is a digest of the address and start.
- All-day events do not block time.

## How the calendar is changed

Each event jason makes carries a key in `extendedProperties.private.jason` (`board-meeting:2026-10-20`, `deadline:<name>:<date>`). A run lists the calendar's events in the window and sets them beside the plan:

- **Create.** A planned key the calendar lacks.
- **Update.** A keyed event whose title, description, location, or times differ. Times are compared as instants.
- **Covered.** A board meeting whose day already has an event jason did not make with the policy's words ("board of directors", "board meeting"): the board's Zoom invitation. No second event is added.
- **Extra.** A keyed event of the board's kinds that jason no longer plans. It is reported, never deleted.
- **Another run's.** A keyed `schedule:` event belongs to `jason schedule --calendar` ([schedule.md](schedule.md)), which puts each dated duty on the same calendar. Each command counts the other's events and leaves them alone. The schedule does not add a second event for a meeting, its notice deadline, or a recurring deadline this calendar already carries on the same day.
- **Others.** Every event without a key is listed and never changed.

Writes send no invitations or updates (`sendUpdates=none`). There is no delete.

## Commands

```bash
jason calendar --plan-only                 # the plan from disk; no Google call
jason calendar                             # read the primary calendar; print planned beside existing
jason calendar --calendar ID --months 6
jason calendar --yes                       # create the missing events and patch the changed ones
jason calendar --list-calendars            # needs calendar.readonly as well as calendar.events
```

The main Google token's `calendar.events` scope reads and writes events. A non-interactive run without a token fails fast (`GoogleAuthRequired`).
