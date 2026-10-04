# Schedule & duties

A band added to `#/duties` · phase 2 · CLI: `jason schedule`, `jason schedule --people`

## In the console

| Console screen | What it shows |
|---|---|
| **Duties by cadence** (`#/duties`, `ConsoleDuties`) | The manager's duty anchors (BPC 11500(d)'s services, broken into `jason.community.duties.DUTIES`) by cadence, each opening to its brief and the documents' passages |
| **Annual disclosures** (`#/disclosures`, `ConsoleDisclosures`; owner view too) | The association calendar's recurring deadlines, overdue first, each with its authority, rule, next date, and the last payment that showed it done; and the calendar jason writes to. The owner view (`OwnerDisclosures`, `calendar?view=owner`) is not the association's deadlines: it is the annual disclosures every member receives (the notice catalog's annual rows: 5300, 5305, 5310, 4041, CORP 8321, and those the policy statement carries), each with its window from the fiscal year and the day the delivery ledger shows it went out, "delivered" or "sent" only |
| **The dock** | **Deadlines** (the calendar grouped, with a screen hint and the office an assignment names as the duty's owner, or "unassigned") and **Tasks** (the action register: a person adds, owns, dates, and completes a task; completion stamps who and when). The red counts are the signed-in person's: what they or their offices may act on (`/api/dock?part=counts`) |

**What this spec adds**, as a band on `#/duties`: the **schedule** itself. The duty anchors say what the manager keeps straight; the schedule says who does each occurrence, when it falls due, and whether it was done:

1. each occurrence of an assignment with its role, standing, and evidence, and **record done**, a signed record;
2. the assignments, proposed or adopted;
3. coverage: the duties no assignment covers;
4. people's own tasks and events read beside what jason tracks.

## Purpose and personas

- **Manager:** reads what falls due across roles, and records a duty done with its evidence.
- **Secretary, Treasurer:** read their own role's list and record their own completions.
- **Director:** reads coverage: the duties nobody owns.

## Data

| Part | Source | Loader |
|---|---|---|
| What falls due | `jason.api.schedule_agenda(days=60, past=30, role=...)`: `items[]` with `due`, `standing` (done, overdue, due soon, upcoming), `key`, `title`, `role`, `adoption`, `evidence`, `done` | `schedule` (to add; `?role=`, `?days=`) |
| Assignments and coverage | `jason.api.schedule_assignments()`: `assignments[]` (`key`, `title`, `role`, `backup`, `clock`, `covers`, `evidence`, `jason`, `adoption`, `note`) and `coverage` (`assigned`, `unassigned[]`, `assignedNotScheduled[]`) | the same |
| People's own tasks and events | the digest's `people` section (`governance_digest(section="people")`, `jason.tasks.people_tasks`): open tasks past due, tasks a rule says to close, untracked recurring items as proposed clocks. Nothing in Google is marked or closed | `governance-digest` |

**Adoption.** An assignment is jason's proposal until the board adopts it. A proposed assignment is labeled "proposed, not adopted" wherever it shows.

## Layout

```
+------------------------------------------------------------------------------------------+
| THE SCHEDULE                                               Role [All v] Window [60 days v]|
| 3 overdue · 5 due soon · 22 upcoming · 14 done in the last 30 days · jason schedule [copy]|
| Due      Duty                                Role        Adoption   Standing   Action     |
| Sep 30   Reconcile the operating account     treasurer   adopted    overdue    [Done]     |
| Oct 15   Review the reserve transfers        treasurer   proposed   upcoming   [Done]     |
| Sep 15   Annual budget report                board       adopted    done: Sep 12 by       |
|                                                                      Casey Sample          |
+------------------------------------------------------------------------------------------+
| COVERAGE · 41 duties assigned · 2 nobody owns: the insurance disclosure, the pest notice  |
| PEOPLE'S OWN TASKS (read from Google; nothing is changed there) · 2 past due · 1 to close |
+------------------------------------------------------------------------------------------+
```

**Record done** opens in place:

```
| Record done: Reconcile the operating account, due Sep 30                                 |
| Done on   [ 2099-10-02 ]                                                                 |
| Evidence  [ Reconciliation for September, filed in the library        ]                 |
|           What shows it was done: the minutes' date and item, a payment, a notice proof.  |
| Done by   [ Casey Sample ]  (from "Signed in as")                                         |
|                                       [Record done as Casey Sample]   [Cancel]            |
```

## Components

`Card`, `DataTable`, `Pill` (the standing words), `DueDate`, `Evidence`, `Command`, `Confirm` (record done), `RemoteView`.

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Filter by role, window | the loader's `role`, `days` | No | `jason schedule --role ROLE` |
| Record done | `record_completion(key, due, by, evidence, done_on)`, behind `Confirm`: writes only `data/schedule/done.jsonl` | No: a signed `data/` record. Refused without a name and evidence | `jason schedule --done KEY DUE --by NAME --evidence TEXT` |
| Put on Google Calendar, on Google Tasks | shown as commands; later the `google.calendar` and `google.tasks` kinds (phase 3) | Later: an approval | `jason schedule --calendar`, `jason schedule --tasks` |

A completion is never edited or removed from the console. A wrong record is corrected by a new record with a note, as the CLI does.

## States

- **No assignments:** "The profile sets no schedule. Assignments are rule rows in the profile."
- **Nothing due in the window:** "Nothing falls due in the next 60 days." The done list still shows.
- **People's tasks unavailable:** "People's tasks are unavailable: no Google read on disk. Run `jason schedule --people`."
- **Evidence refused:** "Say what shows it was done: the minutes' date and item, a payment, or a notice proof." The form keeps what was typed.

## Privacy

- Duties, roles, and standings are P0 or P1.
- People's own task titles can name an owner or a unit; they are replaced by their rule's label, as the digest does with `private=True`.
- Evidence text is checked by `intake.secret_reason` before it is stored.
- The band is not in the owner view.

## Acceptance criteria

1. Items render in `schedule_agenda` order with its standing words; each proposed assignment is labeled "proposed, not adopted".
2. Record done refuses an empty name or evidence, and writes exactly one line to `data/schedule/done.jsonl` with `by`.
3. Coverage shows the unassigned duties by name.
4. No people's task title appears.
