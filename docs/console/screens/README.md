# Screen specs

One page per screen of the console. Each one turns a row of [information-architecture.md](../information-architecture.md) into something a person can build and test. The navigation order, the paths, and the data sources come from that page. The approval model comes from [approval-workflow.md](../approval-workflow.md). Roles and data levels come from [security-and-privacy.md](../security-and-privacy.md). Wording comes from [content/style.md](../content/style.md), and the interaction patterns from [content/patterns.md](../content/patterns.md).

| Screen | Path | Phase | Spec |
|---|---|---|---|
| Today | `/` | 1 | [today.md](today.md) |
| Approvals | `/approvals`, `/approvals/{id}` | 1 | [approvals.md](approvals.md) |
| Members & units | `/members`, `/members/units/{unit_id}` | 1 (table), 2 (unit) | [members-and-units.md](members-and-units.md) |
| Requests | `/requests`, `/requests/{id}` | 2 | [requests.md](requests.md) |
| Notices | `/notices`, `/notices/{key}` | 2 | [notices.md](notices.md) |
| Meetings & minutes | `/meetings`, `/meetings/{date}` | 2 | [meetings-and-minutes.md](meetings-and-minutes.md) |
| Governing documents | `/documents`, `/r/{address}`, `/cite?q=` | 2 | [governing-documents.md](governing-documents.md) |
| Schedule & duties | `/schedule` | 2 | [schedule-and-duties.md](schedule-and-duties.md) |
| Records & library | `/records` | 2 | [records-and-library.md](records-and-library.md) |
| Onboarding | `/onboarding` | 2 | [onboarding.md](onboarding.md) |
| Finance | `/finance` | 2 | [finance.md](finance.md) |

The journeys that cross these screens are in [journeys.md](../journeys.md).

## How each spec is laid out

Every spec has the same sections, in this order:

1. **Purpose and personas.** The one job the screen does, and who does it there.
2. **Data.** The exact function, MCP tool, or `jason://` address behind each part. A screen calls these and renders what they return. It never works a fact out on its own.
3. **Layout.** An ASCII wireframe at desktop width (1280 px), and what changes below 768 px.
4. **Components.** Names from the component library (`src/jason/console/ui/components/`, described in [components.md](../components.md)).
5. **Actions.** Each control, what it calls, and whether it creates an approval. Every action names its CLI equivalent.
6. **States.** Loading, empty, unavailable, and error.
7. **Privacy.** What each role sees, and what is masked.
8. **Acceptance criteria.** Testable statements. A screen ships when each one passes.

## Rules every screen keeps

These come from the principles in [README.md](../README.md#principles). They are not repeated in each spec.

- **Recite, then read.** Wherever a rule's words appear, the `recitation` block comes first: the words whole, the citation, the version in force, and the caveat. jason's reading follows in a `reading-label` block. Nothing else may sit between them.
- **jason proposes, a person decides.** No control on any screen approves, denies, or assigns a member's request; sends to a collection agency; deletes a PayHOA form; edits an owner's submission; or mails anything on jason's own initiative. A test checks each screen's HTML for these verbs on buttons ([acceptance criteria](#shared-acceptance-criteria)).
- **Nothing is written without a named person.** A write outside `data/` goes through an approval. A `data/` record a person signs (an intake answer, a confirmation, a completion) carries `by`, pre-filled with the acting person and editable.
- **A miss stays a miss.** Three states are kept apart, in words:
  - **Empty:** the store was read and holds nothing. "No open requests."
  - **Unavailable:** the store could not be read. The reason and the command that fills it. "Requests are unavailable: no PayHOA catalog on disk. Run `jason sync-catalog`."
  - **None on record:** the store was read, and the thing jason looks for is not in it. This is not proof it did not happen. "None on record. A notice posted where jason does not look is not on disk."
- **Every section shows its freshness and its command.** A `freshness` line under each section's heading: when its store was last synced, and the command that refreshes it. A `cli-hint` beside it gives the command that prints the same detail.
- **Reads are from disk; live reads are jobs.** A page renders from the stores on disk and never calls PayHOA, Google, or Zoom on load. A live read (a sync, a plan) is a job with a `job-status` ([architecture.md](../architecture.md)).
- **Private view.** P3 material shows only while the private view is on (the page header's switch). Off, a restricted item is listed by name or date only, with "Restricted: open the private view to read it."

## Roles, in short

The six roles of `jason.console.identity.Role` ([security-and-privacy.md](../security-and-privacy.md#roles)):

| Short | Role | Typical person |
|---|---|---|
| **M** | `manager` | The person who runs the association day to day |
| **D** | `director` | A director, the president included |
| **S** | `secretary` | The Secretary |
| **T** | `treasurer` | The Treasurer |
| **R** | `reviewer` | A second person on an approval |
| **C** | `counsel` | The association's attorney, read only, on grant |

A role that cannot open a screen gets a 403 page: "This screen is not open to the treasurer role. Ask the manager if you need it." The navigation leaves the screen out for that role.

## Shared states

| State | What the person sees | Component |
|---|---|---|
| Loading a page | Nothing special: pages are rendered on the server from disk, and should arrive in under a second. A section that reads a large store renders its heading at once and its body when ready, with "Reading the store…" in a `role="status"` region | `section-card` |
| Running a job | The job's name, who started it, when, its lock, and its last log lines. A link to the full log. A **Stop** button only where the job can stop safely (a read) | `job-status` |
| Empty | One sentence that says what was read and that it holds nothing, then the next useful step | `states` (empty) |
| Unavailable | "Unavailable:", the reason as `attention.Section.error` gives it, and the command that fills the store | `states` (unavailable) |
| Error on an action | What did not happen, why, and what to do. Nothing partial is hidden ([style.md](../content/style.md#errors)) | `states` (error) |
| Refused by role | 403, with the role named | page |

## Components this set uses

Named in [components.md](../components.md), which is the contract:
- Layout: `app-shell`, `nav`, `page-header`.
- Status and identity: `status-badge`, `deadline-badge`, `stage-stepper`, `person-chip`, `held-banner`.
- Approval: `approval-card`, `write-row`, `evidence-chip` (with `--rule`), `changed-banner`, `approve-bar`, `confirm-panel`, `cost-summary`, `result-panel`.
- Text and data: `recitation`, `reading-label` (and `.jc-decision` for a person's decision), `data-table`, `filters-bar`, `states` (empty, unavailable, error, sign-in needed, busy), `toast` (no timer).
- Activity: `audit-timeline`, `queue-item`.
- Also needed: `masked-field`, `private-switch`, `job-status`, `freshness`.

Proposed here, and not yet in components.md. Each is named so it can be settled there:

| Name | What it is |
|---|---|
| `section-card` | A titled section of a screen, with its `freshness` line, its `cli-hint`, and its body |
| `cli-hint` | The CLI command that gives the same detail, with a copy button |
| `clock-row` | One legal or policy clock: what, the authority recited on demand, the deadline badge, and what is on record |
| `cite-box` | The cite field: any expression `jason cite` takes, with the result as a recitation |
| `diff-table` | Before and after for a text (a section's versions, a notice's text against what was kept) |
| `tabs` | Bands of one screen as links with `aria-current`, each band with its own fragment (Records & library) |

## Shared acceptance criteria

These apply to every screen, and each screen's own list adds to them.

1. No button, link, or form on any screen carries the words approve, deny, or assign next to a member's request, or collection agency, delete form, or edit submission. A test renders each screen with fixture data and checks.
2. Each section shows a `freshness` line and a `cli-hint`, or says why it has none.
3. A store that is missing renders `states` (unavailable) with a command, never `states` (empty).
4. No P2 value reaches the HTML unrevealed. A test greps each rendered page for the fixture's emails and addresses.
5. No P3 value reaches the HTML with the private view off.
6. No P4 value is ever rendered. The fixtures hold a fake token, and a test greps for it.
7. No query string carries a name, an email, or an address.
8. Every page passes an automated WCAG 2.2 AA check (axe-core or the equivalent) with no serious or critical finding, and a keyboard-only walk reaches every control with its focus visible and not hidden under a sticky bar.
9. Every text in the general screens names no association, person, street, or vendor of a real profile. Examples are plainly fake. `tests/test_profile.py`'s boundary check covers `docs/console/`.
