# Schedule & duties

`/schedule` · phase 2 · CLI: `jason schedule`, `jason schedule --people`

## Purpose and personas

What falls due, who does it, and whether it was done. Each occurrence of an assignment with its role, its standing, and the evidence that it was done; the duties no assignment covers; and people's own tasks read beside what jason tracks.

- **Manager:** reads what falls due across roles, and records a duty done with its evidence.
- **Secretary, Treasurer:** read their own role's list and record their own completions.
- **Director:** reads coverage: the duties nobody owns.
- **Reviewer, counsel:** no access.

## Data

| Part | Source |
|---|---|
| What falls due | `jason.api.schedule_agenda(days=60, past=30, role=...)`: `items[]` with `due`, `standing` (done, overdue, due soon, upcoming), `key`, `title`, `role`, `adoption`, `evidence`, `done` |
| Assignments | `jason.api.schedule_assignments()`: `assignments[]` with `key`, `title`, `role`, `backup`, `clock`, `covers`, `evidence`, `jason` (the command), `adoption`, `adopted`, `note` |
| Coverage | `schedule_assignments()["coverage"]`: `assigned`, `unassigned[]`, `assignedNotScheduled[]` (both should be empty) |
| People's own tasks and events | The digest's `people` section (`api.governance_digest(section="people")`), from `jason.tasks.people_tasks`: open tasks past due, tasks a rule says to close, untracked recurring items as proposed clocks. Nothing in Google is marked or closed |
| The association calendar | `association_calendar` (`jason.mcp.county`) |
| The documents' timed duties nothing tracks | The digest's `duties` section |

**Adoption.** An assignment is jason's proposal until the board adopts it (`adoption`: proposed or adopted). A proposed assignment is labeled "proposed, not adopted" wherever it shows.

## Layout

```
+------------------------------------------------------------------------------------------+
| Schedule & duties                                          Role [All v] Window [60 days v]|
| 3 overdue · 5 due soon · 22 upcoming · 14 done in the last 30 days                       |
| CLI: jason schedule [copy]                                                               |
+------------------------------------------------------------------------------------------+
| WHAT FALLS DUE                                                                           |
| Due      Duty                                Role        Adoption   Standing   Action     |
|------------------------------------------------------------------------------------------|
| Sep 30   Reconcile the operating account     treasurer   adopted    overdue    [Done]     |
| Oct 3    Notice of the Oct 7 meeting         secretary   adopted    due soon   [Done]     |
| Oct 15   Review the reserve transfers        treasurer   proposed   upcoming   [Done]     |
| Sep 15   Annual budget report                board       adopted    done: Sep 12 by       |
|                                                                      Casey Sample [evidence]|
+------------------------------------------------------------------------------------------+
| COVERAGE                                                                                 |
| 41 duties assigned · 2 nobody owns: [the insurance disclosure] [the pest notice]          |
| 1 on a clock that only a standing assignment owns                                        |
+------------------------------------------------------------------------------------------+
| PEOPLE'S OWN TASKS (read from Google; nothing is changed there)                          |
| 2 open past their due day · 1 a rule says to close · 3 recurring, untracked: proposed     |
+------------------------------------------------------------------------------------------+
| ASSIGNMENTS (41)                                                       [Show all]         |
+------------------------------------------------------------------------------------------+
```

**Record done** opens a panel in place:

```
+------------------------------------------------------------------------------------------+
| Record done: Reconcile the operating account, due Sep 30                                 |
| Done on   [ 2099-10-02 ]                                                                 |
| Evidence  [ Reconciliation for September, filed in the library        ]                 |
|           What shows it was done: the minutes' date and item, a payment, a notice proof.  |
| Done by   [ Casey Sample ]  (pre-filled with who you are acting as)                       |
|                                       [Record done as Casey Sample]   [Cancel]            |
+------------------------------------------------------------------------------------------+
```

## Components

`page-header`, `filters-bar`, `data-table`, `status-badge` (`--overdue`, `--due-soon`; "done" and "upcoming" as words), `deadline-badge` (`--legal` when the assignment covers a statute's clock), `person-chip`, `section-card`, `cli-hint`, `evidence-chip`, `states` (empty), `states` (unavailable).

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Filter by role, window | GET `role`, `days` | No | `jason schedule --role ROLE` |
| Record done | `api.record_completion(key, due, by, evidence, done_on)`: writes only `data/schedule/done.jsonl` | No approval: a signed `data/` record (`local.schedule.done`, SIGNED). Refused without a name and evidence. Logged | `jason schedule --done KEY DUE --by NAME --evidence TEXT` |
| Put on Google Calendar | Plans `google.calendar` | **Creates an approval** (phase 3, R1) | `jason schedule --calendar` |
| Put on Google Tasks | Plans `google.tasks` | **Creates an approval** (phase 3, R1) | `jason schedule --tasks` |
| Open an assignment's command | Copies `jason` (the assignment's command) | No | — |

A completion cannot be edited or removed from the console. A wrong record is corrected by a new record with a note, as the CLI does.

## States

- **No assignments:** "The profile sets no schedule. Assignments are rule rows in the profile."
- **Nothing due in the window:** "Nothing falls due in the next 60 days." The done list still shows.
- **People section unavailable:** "People's tasks are unavailable: no Google read on disk. Run `jason schedule --people`."
- **Evidence refused:** "Say what shows it was done: the minutes' date and item, a payment, or a notice proof." The panel keeps what was typed.

## Privacy

- Duties, roles, and standings are P0 or P1.
- People's own task titles can name an owner or a unit. With the private view off they are replaced by their rule's label, as the digest does with `private=True`.
- Evidence text is checked by `intake.secret_reason` before it is stored.

## Acceptance criteria

1. Items render in `schedule_agenda` order with its standing words.
2. Each proposed assignment is labeled "proposed, not adopted".
3. Record done refuses an empty name or evidence, and writes exactly one line to `data/schedule/done.jsonl` with `by`.
4. After recording, the row shows "done", the date, the person, and the evidence, without a reload losing focus.
5. Coverage shows the unassigned duties by name, and "both should be empty" when they are not.
6. With the private view off, no people's task title appears.
