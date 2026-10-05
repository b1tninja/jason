# Screen specs

One page per screen of the earlier spec, now read against the console that exists. Where a console screen already does the job, the spec says which, and keeps only what it adds. Where none does, the spec is the whole screen, with the loader it would read. The navigation and the routes come from [information-architecture.md](../information-architecture.md); the approval model from [approval-workflow.md](../approval-workflow.md); roles and data levels from [security-and-privacy.md](../security-and-privacy.md); the words from [content/style.md](../content/style.md) and [content/patterns.md](../content/patterns.md).

| Spec | In the console | Status | Phase |
|---|---|---|---|
| [today.md](today.md) | `#/digest` (`ConsoleDigest`), the dock, `#/inbox` | Adds bands to a built screen | 2 |
| [approvals.md](approvals.md) | `#/approvals` (`ConsoleApprovals`): letters built | Adds the engine's plan review (being built) | 1 |
| [meetings-and-minutes.md](meetings-and-minutes.md) | `#/meetings`, `#/meeting`, `#/agenda`, `#/room`, `#/minutes-review`, `#/decisions`, `#/hearings` | Adds the meeting watch, postings, the draft's checks, and record stages | 2 |
| [schedule-and-duties.md](schedule-and-duties.md) | `#/duties` (`ConsoleDuties`), `#/disclosures` (`ConsoleDisclosures`), the dock | Adds the schedule by role, "record done", and coverage | 2 |
| [records-and-library.md](records-and-library.md) | `#/records` (`ConsoleRecords`), `#/ingestion`, `#/leads`, `#/records-requests` | Adds library search, an ingest's report and apply, and revisions | 2 |
| [finance.md](finance.md) | `#/payments` (`ConsolePayments`), `#/reserves` (`ConsoleReserves`), `#/liens` (`ConsoleLiens`), `#/books`, `#/title` | Adds bank balances, the reserve study, and the ledger's reports | 2 |
| [requests.md](requests.md) | partly `#/inbox`, `#/drafts`, `#/records-requests` | A new screen, `#/requests` | 2 |
| [onboarding.md](onboarding.md) | partly `#/communities`, `#/onboarding` | A new band of `#/onboarding`: the session | 2 |
| [paint.md](paint.md) | none | Proposed whole, `#/paint` | 3 |
| [life-safety.md](life-safety.md) | none (its parts are in the dock, `#/actions`, `#/insurance`) | Proposed whole, `#/life-safety` | 3 |
| [community-facts.md](community-facts.md) | none | Proposed whole, `#/facts` | 3 |
| [document-kinds.md](document-kinds.md) | part (`#/ingestion` counts kinds and methods) | Proposed whole, `#/ingestion/kinds` | 3 |
| [unit-record.md](unit-record.md) | none | Proposed whole, a tab of `#/members` and `#/loss-packet` | 4 |
| [members-and-units.md](members-and-units.md) | none | Proposed whole, `#/members` | 4 (needs P2 masking) |
| [notices.md](notices.md) | none | Proposed whole, `#/notices` | 2 |
| [governing-documents.md](governing-documents.md) | none | Proposed whole, `#/documents` | 2 |
| [mail.md](mail.md) | `#/mail-triage`, `#/inbox`'s letters and requests, `#/insurance`, `#/renewals` | Their documents on `Doc` (built) | 2 |
| [board-items.md](board-items.md) | `#/actions` (`ConsoleActions`) | Its evidence on `Doc` (built) | 2 |
| [requests-and-links.md](requests-and-links.md) | `#/drafts`, the key documents tab, `#/canvases`, `#/templates`, and `Embed` | Their documents on `Doc` (built) | 2 |
| [people.md](people.md) | `#/people` (`PeopleView`) | Built, read-only: offices, holders, vacancies, sign-in | 2 |
| [status.md](status.md) | `#/status` (`StatusView`) | Built, read-only, administrator only: sources, sign-ins, gates, failures | 2 |
| What applies (proposed; [../handoff-applicability-questions.md](../handoff-applicability-questions.md)) | none (its parts are in the dock's Deadlines, [life-safety.md](life-safety.md), [notices.md](notices.md), and the onboarding session) | Proposed whole, `#/applies` | 3 |
| Confirmations (proposed; [../handoff-confirmations-queue.md](../handoff-confirmations-queue.md)) | none (its parts are in `jason readings`, `jason lessons --open`, and the draft gold file) | Proposed whole, `#/confirmations` | 2 |
| Context-pack workbench (proposed; [../handoff-context-pack-workbench.md](../handoff-context-pack-workbench.md)) | none (its parts are `jason index --search`, the MCP `document_search`, and `jason review`) | Proposed whole, `#/workbench` | 3 |
| Collection workspace (proposed; [../handoff-collection-workspace.md](../handoff-collection-workspace.md)) | none (its parts are `jason collection`, `jason review --collection`, and the `legal_cases` and `case_file` tools) | Proposed whole, `#/collections` | 3 |
| Law as of a day and the quote check (proposed; [../handoff-as-of-and-quote-check.md](../handoff-as-of-and-quote-check.md)) | none (its parts are `jason cite`, `jason verify-quotes --as-of`, and the `law_in_force` tool) | Components shared across screens, and `#/documents/check` | 2 |
| The machine (proposed; [../handoff-storage-and-settings.md](../handoff-storage-and-settings.md)) | extends [status.md](status.md) (`#/status`) | Proposed band, `#/instance/machine` | 2 |
| Programs (proposed; [../handoff-programs.md](../handoff-programs.md)) | none (its parts are `jason duties --documents`, `jason deadlines`, `jason inspections`, `jason pests`, `jason backflow`, `jason collection`) | Proposed whole, `#/programs` | 3 |

Screens built with no spec here: the meeting room, decisions, and agenda (from the design handoff), insurance and renewals (`ConsoleInsurance`; their documents are in [mail.md](mail.md)), canvases and templates (their documents are in [requests-and-links.md](requests-and-links.md)), registers, legal, and the community profile page ([web-ui.md](../../web-ui.md#views-uisrcviews-hash-routes)).

The journeys that cross these screens are in [journeys.md](../journeys.md).

## How each spec is laid out

1. **In the console.** The screen that exists, and what this spec adds to it; or "none".
2. **Purpose and personas.**
3. **Data.** The exact function or MCP tool behind each part, and the jason-web loader that serves it (existing, or to add). A screen renders what the loader returns. It never works a fact out on its own.
4. **Layout.** An ASCII wireframe at desktop width, and what changes under 720 px (where `ConsoleShell`'s nav becomes a select).
5. **Components.** jason-ui names ([components.md](../components.md)).
6. **Actions.** Each control, what it calls, and whether it creates an approval. Every action names its CLI equivalent.
7. **States**, **Privacy**, and **Acceptance criteria.**

## Rules every screen keeps

These come from the principles in [README.md](../README.md#principles). They are not repeated in each spec.

- **Recite, then read.** Wherever a rule's words appear, `Recitation` comes first: the words whole, the citation, the version in force, and the caveat. Any reading follows in a `ReadingLabel`. Nothing else sits between them.
- **jason proposes, a person decides, the board votes.** No control on any screen approves, denies, or assigns a member's request; sends to a collection agency; deletes a PayHOA form; edits an owner's submission; mails anything on jason's own initiative; or approves for the board.
- **Nothing is written without a named person.** A write outside jason is an engine approval, applied from the browser only with `--allow-apply`, or a `Command` a person runs. A write to jason's own store carries `by` (from "Signed in as", editable) behind a `Confirm`.
- **A miss stays a miss.** Three states, kept apart in words:
  - **Empty:** the store was read and holds nothing. "No open requests."
  - **Unavailable:** the store could not be read. The tool's own note and the command that fills it. "Requests are unavailable: no PayHOA catalog on disk. Run `jason sync-catalog`."
  - **None on record:** the store was read, and the thing jason looks for is not in it. Not proof it did not happen. "None on record. A notice posted where jason does not look is not on disk."
- **Every section shows its freshness and its command** where the loader gives a sync time: when its store was last synced, and a `Command` that refreshes it.
- **Reads are from disk; live reads are a person's action.** A screen never calls PayHOA, Google, or Zoom on load. A live read (a check, a sync) is a button behind the write guard, or a command.
- **The owner view.** A new screen starts board-only (`owner: false` in `SCREENS`). An owner version is its own decision, and it needs an owner loader (`OWNER_SOURCES` in `jason.web.extra.owner_view`) and its sources in `ui/src/ownerScreens.json`: in the owner view the server answers no other source.
- **Restricted material.** Until the private view exists ([security-and-privacy.md](../security-and-privacy.md#data-levels)), a screen that would show P2 or P3 values lists the item by name or date only, with the command that shows it in a terminal.

## Roles, in short

Today there are no roles in the console, only the Board / Owner view and the officers in "Signed in as" ([security-and-privacy.md](../security-and-privacy.md#roles)). The specs' privacy sections use the proposed roles, so that the loaders can enforce them once sign-in exists:

| Short | Role | Typical person |
|---|---|---|
| **M** | manager | The person who runs the association day to day |
| **D** | director | A director, the president included |
| **S** | secretary | The Secretary |
| **T** | treasurer | The Treasurer |
| **R** | reviewer | A second person on an approval |
| **C** | counsel | The association's attorney, read only, on grant |

## Shared states

| State | What the person sees | Component |
|---|---|---|
| Loading | "Reading the store…" | `Loading` (in `RemoteView`) |
| The tool's own miss | The tool's `found: false` note, with its command | `RemoteView` |
| A loader failed | What failed and a Retry | `ErrorNotice` |
| Empty | One sentence that says what was read and that it holds nothing, then the next useful step | `EmptyState` |
| A shape the view did not expect | The tool's raw result, with the error named | `ViewBoundary` |
| A live read running | Busy, with what it is reading | the button's own busy state |
| A refused write | What did not happen, why, and what to do; nothing partial hidden | inline `.notice-error`, `role="alert"` |

## Shared acceptance criteria

These apply to every screen, and each screen's own list adds to them.

1. No button, link, or form on any screen carries the words approve, deny, or assign next to a member's request, or collection agency, delete form, or edit submission; and none approves for the board. A component test renders each screen with fixture data and checks.
2. Each section shows its freshness and a `Command` where its loader gives a sync time, or says why it has none.
3. A store that is missing renders the tool's note with a command, never an empty table.
4. No P2 value reaches the browser unrevealed: a test greps each loader's answer for the fixture's emails and addresses.
5. No P3 value reaches the browser outside the private view.
6. No P4 value is ever rendered. The fixtures hold a fake token, and a test greps for it.
7. No route or query string carries a name, an email, or an address.
8. Every screen passes a keyboard-only walk that reaches every control with its focus visible and not hidden under a sticky bar, and an automated WCAG 2.2 AA check with no serious or critical finding.
9. Every text in the general screens names no association, person, street, or vendor of a real profile. Examples are plainly fake. `tests/test_profile.py`'s boundary check covers `docs/console/`.
