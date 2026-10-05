# People and offices

`#/people`, in Records · built · board only · loader `GET /api/people` (`jason.web.extra.people`)

## In the console

Built, read-only. It answers [handoff-reconciliation-3.md](../handoff-reconciliation-3.md#people-and-offices): each office, who holds it, what it approves, and whether the person can sign in. There is no edit control: no change of role, no added person, no term set from the browser.

## Data

`GET /api/people` answers only a signed-in person on the roster (401 otherwise). The owner view refuses it: it is not in `OWNER_SOURCES`, and `ui/src/ownerScreens.json` does not list it.

| Part | Source |
|---|---|
| `offices[]`: president, vice president, secretary, treasurer, each with `holders` (`name`, `approves`, `recordsBoard`, `canSignIn`) | `Community.officers()`; `Officer.approves`; `Officer.can_approve("the board")`; the sign-in roster (`jason.web.signin`) |
| A vacant office: `vacancy` ("No one holds the office of OFFICE."), `provision` (`source`, `words`) or `provisionNote` | `Community.vacancy_provision(office)` (None: "not on file") |
| `offices[].duties`: each with `owners`, `assigned`, `routing`, `backup` | `Community.assignments()` as the dock reads them (`dock._duty_owners`); a vacant office's duties are unassigned |
| `directors`: directors with no office; `seats` with its source | `Community.board()` |
| `management`: the profile's manager and the portfolio managers, with `portfolio` | `jason.access.officers_with_managers` |
| `admins[]`: "Not an office; approves nothing.", with any office the person also holds | `jason.access.admins` |
| `people[]`: one row a person, offices joined | all of the above |
| `terms`: `rows[]` (`person`, `seat`, `office`, `start`, `endNote`, `source`, `provision`, `status`), else "Terms: not on file."; `question`, the election-status question and its commands | `Community.terms()` (`Term`, the private facts' terms topic) |
| `change`: the onboarding item `board-roster`, its `question` (id, words, form), and the commands that answer, confirm, and apply it | `jason.community.onboarding`, `jason.community.roster` |

## Rules

- **A person may hold two offices.** The answer is grouped by office and by person, never one `role` a person.
- **A vacant office routes nothing.** It shows "No one holds the office of OFFICE." and the governing documents' vacancy provision, recited, when the profile keeps it. No office takes another's work by default; its duties are unassigned.
- **The administrator is not an office** and approves nothing. Management is not an office of the board; it approves what `Officer.approves` says.
- **A change of office is the board's act, recorded in the minutes.** Then the board-roster question records it (`OFFICE; PERSON (or vacant); YYYY-MM-DD; MINUTES`), a second person confirms, and `jason onboard --apply` appends it to the officers topic. The screen shows the question and the commands.
- **Terms.** Directors' terms (the members elect them, for the term the bylaws set) and officers' terms (the board elects them, as the bylaws say) differ. Each is a private fact with its election record (the minutes or the inspector's report) and the provision that sets it, recorded by the election-status question. An officer with no end on record serves "at the pleasure of the board". "term ended; election due" shows only when the recorded end is past; jason computes no other date.

## Privacy

- Names are P1: anyone on the roster sees them.
- Email addresses are P2: masked (`[email]`) unless the person's private view is open and their offices open P2. Then the answer is logged in `access/served.jsonl` (`address: api/people`).

## Acceptance criteria

1. No sign-in: 401. The owner view: 403.
2. One person in two offices appears under both, and once by person.
3. A vacant office says so, cites its provision or says it is not on file, and its duties are unassigned.
4. An admin is listed as no office.
5. No control edits anything (`ui/src/views/people.test.tsx`, `tests/test_web_people.py`).
6. Terms on file show with their sources, and an ended one as due; the change section names the board-roster question (`tests/test_roster.py`).
