# Information architecture

The console's navigation is jason-ui's: `ConsoleShell` with the screens in `ui/src/App.tsx` (`SCREENS`), grouped as Overview, Governance, Money, and Records. This page maps the earlier spec's screens onto that navigation, says what each spec adds to a screen that already exists, and places the screens that have no counterpart yet, with the data source each would read.

Detail lives elsewhere:
- each screen's additions, layout, and acceptance: [screens/](screens/README.md);
- every built view and its loader: [web-ui.md](../web-ui.md#views-uisrcviews-hash-routes);
- the paths a person takes across screens: [journeys.md](journeys.md);
- the words on screen: [content/style.md](content/style.md) and [content/patterns.md](content/patterns.md).

## The navigation as built

A grouped left nav; under 720 px a "Go to" select. The header carries the community's wordmark (`GET /api/theme`), "Signed in as" (a sample pick over the profile's officers, not an account), the dock toolbar, and the Board / Owner view switch. Addresses are hash routes, `#/<id>`, with `?view=owner` for the owner view, so a shared link lands on the same screen for the same audience.

The design project names each screen as a component (`ConsoleDigest`, `ConsoleApprovals`, ...). The table gives both names.

| Group | Screen (nav label) | Route | Design name | Owner view | Reads |
|---|---|---|---|---|---|
| Overview | Board digest ("Overview" for owners) | `#/digest` | `ConsoleDigest` | yes: the member digest | `/api/board-digest`; the owner view `/api/owner-digest` |
| Overview | Approvals (with the pending count) | `#/approvals` | `ConsoleApprovals` | no | `/api/approvals`; the engine's routes being added |
| Overview | Duties by cadence | `#/duties` | `ConsoleDuties` | no | `/api/duties` |
| Overview | Inbox | `#/inbox` | — | no | `/api/open-items` |
| Overview | Mail triage, Drafts, Leads, Jobs | `#/mail-triage`, `#/drafts`, `#/leads`, `#/jobs` | — | no | `/api/mail-triage`, `/api/request-links?drafts=1`, `/api/leads`, `/api/jobs` |
| Overview | Communities, Onboarding | `#/communities`, `#/onboarding` | — | no | `/api/communities`, `/api/onboarding` |
| Overview | Status | `#/status` | — | no | `/api/status`, `/api/health` (an admin only; [screens/status.md](screens/status.md)) |
| Governance | Board action items | `#/actions` (alias `board`) | `ConsoleActions` | no | `/api/board-items` |
| Governance | Decisions | `#/decisions` | `ConsoleDecisions` | no | `/api/decisions` |
| Governance | Plan a meeting | `#/agenda` | `ConsoleAgenda` | no | `/api/agenda-plan` |
| Governance | Meeting room ("Live meeting" for owners) | `#/room` | `ConsoleMeetingRoom` | yes: the stage alone | `/api/meeting-room` |
| Governance | Meetings and minutes | `#/meetings` | `ConsoleMeetings` | yes: open-session notices, agendas, minutes | `/api/meetings` |
| Governance | Next meeting, Minutes review | `#/meeting`, `#/minutes-review` | — | no | `/api/meeting`, `/api/minutes-review` |
| Governance | Annual disclosures | `#/disclosures` (alias `calendar`) | `ConsoleDisclosures` | yes: the disclosures members receive | `/api/calendar` |
| Governance | Rule changes, Hearings, Owner information | `#/rules`, `#/hearings`, `#/owner-info` | — | no | `/api/rule-changes`, `/api/hearings`, `/api/owner-info` |
| Governance | Canvases, Templates, Registers | `#/canvases`, `#/templates`, `#/registers` | — | no | `/api/canvases`, `/api/templates`, `/api/registers` |
| Money | Payments with questions | `#/payments` (alias `money`) | `ConsolePayments` | no | `/api/budget`, `/api/reconciliations`, `/api/invoices`, `/api/collections` |
| Money | Reserves and budget | `#/reserves` | `ConsoleReserves` | yes: the reserve funding summary | `/api/reserves` |
| Money | Reserve findings | `#/reserve-findings` | — | no | `/api/reserve-findings` |
| Money | Liens and delinquency | `#/liens` (alias `delinquency`) | `ConsoleLiens` | no | `/api/delinquency` |
| Money | Books checks, Title watch | `#/books`, `#/title` | — | no | `/api/utility-payments`, `/api/ledger-validation`, `/api/title-watch` |
| Records | Records (CIV 5200) | `#/records` | `ConsoleRecords` | no (an owner link lands on Records requests) | `/api/association-records`, `/api/records-inventory` |
| Records | Records requests ("Records" for owners: the request form) | `#/records-requests` | — | yes: the form and the record kinds | `/api/records-requests` |
| Records | Insurance | `#/insurance` | `ConsoleInsurance` | yes: the insurance summary | `/api/insurance` |
| Records | Insurance renewals, Legal, Document ingestion | `#/renewals`, `#/legal`, `#/ingestion` | — | no | `/api/insurance-renewals`, `/api/legal-cases`, `/api/library-status` |
| Records | Owner page | `#/owner-page` | the community profile page | yes | `/api/community-profile` |
| (header) | The dock: Deadlines, Tasks, Scratchpad, Ask | a drawer, not a route | the dock | no | `/api/dock?part=` |

In the owner view every read carries `view=owner`, and the server answers it from the owner loaders alone (`jason.web.extra.owner_view`): a screen marked "yes" is sent only what a member is entitled to, and any other source is refused (403). `ui/src/ownerScreens.json` names the sources each owner screen reads; [security-and-privacy.md](security-and-privacy.md#roles) has the rule.

## The spec's screens, mapped

| Spec screen | In the console | What the spec adds | Spec |
|---|---|---|---|
| Today | `#/digest`, with the dock's Deadlines and `#/inbox` | The governance digest's sections (`attention.digest`) beside the board digest; the approvals waiting on a person; the next questions; running work | [today.md](screens/today.md) |
| Approvals | `#/approvals` (letters, built) | The engine's plans: review by item, held and for-a-person sections, decide and sign, second person, re-plan check, apply behind the flag, audit | [approvals.md](screens/approvals.md) |
| Meetings & minutes | `#/meetings`, `#/meeting`, `#/agenda`, `#/room`, `#/minutes-review`, `#/decisions`, `#/hearings` | The meeting watch's clocks (4920 notice, 4950(a) minutes) read forward, recording a posting, the minutes draft's checks beside the draft, and the record stages | [meetings-and-minutes.md](screens/meetings-and-minutes.md) |
| Schedule & duties | `#/duties`, `#/disclosures`, the dock's Deadlines and Tasks | The schedule's occurrences by role with "record done", the assignments, coverage, and people's own tasks | [schedule-and-duties.md](screens/schedule-and-duties.md) |
| Records & library | `#/records`, `#/ingestion`, `#/leads`, `#/records-requests` | Library search, an ingest's report and its apply, and a document's revisions | [records-and-library.md](screens/records-and-library.md) |
| Finance | `#/payments`, `#/reserves`, `#/liens`, `#/books`, `#/title` | Bank balances by last four, the reserve study, and the ledger's reports | [finance.md](screens/finance.md) |
| Requests | partly: `#/inbox` (requests pending), `#/drafts` (emailed requests PayHOA lacks), `#/records-requests` (records requests) | Every member request with its clock and standing (`jason respond`), one request's page, and the acknowledgment draft | [requests.md](screens/requests.md) |
| Onboarding | partly: `#/communities`, `#/onboarding` (accounts, facts, the request list, gaps) | The onboarding session: stage gates, the next questions ranked by what each unblocks, signed answers, and the second person on a high-stakes answer | [onboarding.md](screens/onboarding.md) |
| Members & units | none (`#/owner-info` holds the cycle's planned writes only) | Proposed whole | [members-and-units.md](screens/members-and-units.md) |
| Notices | none | Proposed whole | [notices.md](screens/notices.md) |
| Governing documents | none | Proposed whole: the reader and the cite box | [governing-documents.md](screens/governing-documents.md) |
| Settings & profile | `#/status` (sources and writes), `#/communities` | The connections (yes or no only), the action-kind registry read-only, lock holders | below |

### Where the proposed screens go

A new screen is a row in `SCREENS` and a loader in `jason.web.sources` (or a module in `jason.web.extra`). Each loader wraps a function that exists today; none derives a fact of its own.

| Screen | Group, route | Loader to add | Wraps |
|---|---|---|---|
| Requests | Overview, `#/requests` | `member-requests` (`?open=1`, `?id=`) | `jason.api.member_requests`, `response_sources`, `acknowledgment_draft` |
| Members and units | Governance, `#/members` (`?unit=` a PayHOA unit id only) | `members`, `unit` | `owner_info.ledger` and `summary` from the stored catalog; `party_brief`, `unit_brief`, `parcel_liens`, `new_owners` |
| Notices | Governance, `#/notices` (`?key=`) | `notices`, `notice` | `notice_ledger.notices`, `notice_record.build`, `jason.api.notice_requirements`, `notice_delivery` |
| Governing documents | Records, `#/documents` (`?q=`, `?address=`) | `cite`, `record` | `jason.api.cite_document`, `read_record`, `section_refs`, `living_document`, `document_conflicts` |
| What applies | Governance, `#/applies` (`?subject=association\|system:<key>\|building:<key>`, `?as_of=`, `?fact=FACT=WORD`) | `applies`, `applies-questions`, `notice-catalog`; writes through the built `intake` writer and a proposed `applies` writer (file the questions) | `jason.tasks.applicability_asks.evaluate`, `applicability_asks.questions`/`standing`, `elevated_inspections.records`, `notice_catalog.applicable`/`about`, `jason.api.answer_intake_question`, `onboarding_confirm` |
| Confirmations | Overview, `#/confirmations` (`?kind=`, `?state=`; `/reading/<key>`, `/gold/<id>`, `/decision/<key>`) | `confirmations`, `confirmations-reading`, `confirmations-gold`, `confirmations-progress`, `confirmations-decision`; writes `confirmations/reading`, `confirmations/gold`, `confirmations/decision` (each takes `by`) | `law_readings.readings`, `status`, `recite`, `provision_text`; the draft gold rows and `passage_index.search(mode="exact")`; `lessons.lessons` filtered to `Status.DECISION`, `tasks.board_items.propose` |
| Context-pack workbench | Records, `#/workbench` (`/compare`, `/reviews`) | the loaders [handoff-context-pack-workbench.md](handoff-context-pack-workbench.md#where-it-goes) names | `passage_index.search`, `context_pack.assemble`, `jason.api` `document_search`, `verify_quotes`, the review store |
| Collection workspace | Records, `#/collections` (`/<key>`) | the loaders [handoff-collection-workspace.md](handoff-collection-workspace.md#where-it-goes) names | `document_collections`, `collection_pages.summarize`, `law_citations`, `case_files`, `fact_conflicts`, the review store |
| Law as of a day, the quote check | shared components; `#/documents/check` | the loaders [handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md#where-it-goes) names | `law_text.version_on`, `jason.api.law_in_force`, `quote_check.check`, `law_citations.resolve` |
| The machine | Administration, `#/instance/machine` (a band beside `#/status`) | the loaders [handoff-storage-and-settings.md](handoff-storage-and-settings.md#where-it-goes) names | `storage.report`, `config.user_config_path`, `locks.holders`, `local_ai`, `jason index --status` |
| Onboarding session | a band of `#/onboarding` | `onboarding-session`, `next-questions` | `jason.api.onboarding_status`, `next_questions`, `intake_questions`; writes through `answer_intake_question` and `onboarding_confirm` (both take `by`) |
| The governance digest | a band of `#/digest` | `governance-digest` (`?section=`) | `jason.api.governance_digest` |
| The meeting watch | a band of `#/meetings` | `meeting-watch` | `meeting_watch.watch`, `record_stages.histories` |
| The schedule | a band of `#/duties` | `schedule` (`?role=`, `?days=`) | `jason.api.schedule_agenda`, `schedule_assignments` |

The owner view shows none of these at first. An owner-facing version of any of them is its own decision ([mvp.md](mvp.md#open-decisions)).

### Settings

There is no Settings screen. `#/status` lists the sources and the writes that are on, and should add: whether apply is on, whether a Keeper session and a Google token are present (yes or no, never a value, with the command that fixes each), the lock holders (`locks.holders()`), and the action kinds read-only (`jason.approvals.registry.kinds()`: each one's risk, approver rule, and reversibility).

## Rules every screen keeps

- **Read from disk.** A screen renders the stores on disk, as `jason-mcp` does. Nothing on load calls PayHOA, Google, Zoom, or Keeper. A live read (a plan, a sync) is an action a person takes, and it fails fast when a session is missing.
- **Each screen names its command.** A `Command` gives the CLI that prints the same detail, so a person can always check the console against the terminal.
- **Each section shows its freshness** when its loader gives one ("synced Oct 3, 06:00"), with the command that refreshes it. A loader that does not give one yet is a gap to fix in the loader, not a date to invent.
- **A missing store is a miss.** The tool's own `found: false` note, with the command that fills it, through `RemoteView`. Never an empty table.
- **Recite first.** Wherever a rule's words appear, the `Recitation` comes first, then any reading under a `ReadingLabel`.
- **Nothing goes out from the page.** A write outside jason is either an engine approval (apply behind the flag) or a `Command` a person runs. A write to jason's own store is a person's act, with `by`, behind a `Confirm`.
- **The board decides at a meeting.** A question for the board goes to its agenda (`#/agenda`) and is decided by a vote recorded in `#/room` or `#/decisions`. No screen has an approve control for the board.
- **A URL carries an id or a filter**, never a name, an email, or an address ([security-and-privacy.md](security-and-privacy.md#urls)).
