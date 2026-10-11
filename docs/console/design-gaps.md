# Design gaps: which screens and flows still have no spec or brief for the design agent

Audit of 2026-10-11. Nothing here is built or drawn; this page lists what is missing and what to write next. It was made by reading the six family pages ([../workflows/README.md](../workflows/README.md) and the pages it lists), [../workflows-design.md](../workflows-design.md), every page in [screens/](screens/README.md), every `handoff-*.md`, and every `design-brief-*.md`, then checking the loaders in `src/jason/web/sources.py` (`EXTRA_LOADERS`, `default_loaders`) and the views in `ui/src` (`SCREENS` in `App.tsx`, `ui/src/views`, `ui/src/components`).

**How "built" was checked.**
- *Loader built*: the source name is a key in `EXTRA_LOADERS` or `default_loaders()`.
- *View built*: the screen is in `SCREENS`, or its source name is read by a file in `ui/src` (tests and fixtures excluded). A loader whose name appears nowhere in `ui/src` has no view.
- A cell that could not be checked says "not verified".

**Treated as covered** (the user said they are being written): the briefs `notices-and-mailroom` and `board-records` (elections, collect items, incidents) have landed and were read; `requests-and-onboarding` had not landed when this audit ran (`ls docs/console` showed no such file), so its rows say "covered, to confirm when it lands".

**Read this first (surprises).**
1. **The family pages contradict the Work spec on embedding.** [screens/work.md](screens/work.md) and [design-brief-work.md](design-brief-work.md) (C3) make a `plan` step a link ("Review in Approvals") and a `decision` step a link ("Record in Decisions"). The money and records pages say "A money step **embeds the existing screen**" ([../workflows/money.md](../workflows/money.md) section 5) and "Act in place" ([../workflows/documents-records.md](../workflows/documents-records.md) section 5), and the members and board pages list built screens as the step panels. No spec says what an embedded screen looks like inside a step, which acts may be done there, or how the run records them. This decides every family's run page (row E1).
2. **The workflows README is stale on the engine.** It says "none of the engine below is built yet" and "`jason.workflows` ... do not exist". `src/jason/workflows/` exists (`types`, `store`, `fold`, `resume`, `steps`, `definitions`, `api`; commit `fff50a3`, "Workflows engine, step 1"), and `design-brief-board-records.md` already says so. What is still absent: any registered definition (`definitions.py` says "none yet"), a `jason workflow` command, the `work` and `work-run` loaders, and any view. (Not edited here; the README should be corrected by whoever owns it.)
3. **About 35 built loaders have no view.** No file in `ui/src` reads `bill-attach`, `bill-investigation`, `life-safety`, `paint`, `paint-color`, `facts`, `unit-record`, `loss-packet`, `library-kinds`, `rule-records` (and its five siblings), `record-readings`, `responses`, `response`, `outstanding-responses`, `campaign-status`, `followups`, `form-library`, `instance-service`, `instance-integrations`, `instance-schedules`, `backflow`, `watchlist`, `report-portal`, `filing-plan`, or `document-codes`. Only components exist for the inspections and paint families (`WatchRow`, `PaletteMatrix`, and the rest). So most of the "write next" cost is a brief or a small spec, not new data.
4. **[information-architecture.md](information-architecture.md) names no `#/work`, `#/life-safety`, `#/paint`, `#/mailroom`, `#/elections`, `#/incidents`, `#/followups`, `#/responses`, `#/cycle`, `#/forms`, or `#/instance/*`** (grep, case-insensitive), though specs and briefs propose all of them. The file is modified in the working tree by another session; it needs a pass once the briefs land (row E3).
5. **`design-brief-work.md` (section H, hearing row area) uses the definition key `inspection-period`; [../workflows/property-safety-vendors.md](../workflows/property-safety-vendors.md) names it `life-safety-period`** (`grep inspection-period docs` finds only the brief). One of them is wrong.
6. **An untracked static component library, `src/jason/console/ui/`** (65 files under `components/`, `tokens.css`, `previews/`), sits beside the React components in `ui/src/components`. Its README says the contract is [components.md](components.md). How the two relate was not verified; a design agent should be told which is current.
7. **Two things the family pages call gaps have no spec at all**, and each blocks a legal clock: the monthly review's record (CIV 5500, 5501) and the delinquency steps CIV 5650 to 5720 (rows M1, M2).

> **Status, 2026-10-11 (after the audit).** Written since: the embed rule (`screens/work.md`, "Where a step's work happens", which settles E1, E2, and G2), `screens/monthly-review.md`, `screens/delinquency-process.md`, `screens/hearing-process.md`, and `screens/law-review.md`; `README.md` of the workflows no longer says the engine is absent; the Work brief uses `life-safety-period`. Still to write from the ranked list: the annual-disclosure-packet brief, the governance-calendar brief, the property-and-units brief, and a county-tax-cycle spec (waiting on the Revenue and Taxation Code sections for the shelf).

## 1. The table

Columns: surface | family or run | spec (path) | brief (path) | loader built? | view built? | what to write | priority (H, M, L, or "-" when covered) with one reason.

Paths are under `docs/console/` unless they start with `../`. "Family pages" are `../workflows/*.md`.

### Common to every family

| Surface | Run | Spec | Brief | Loader | View | What to write | Priority |
|---|---|---|---|---|---|---|---|
| Work list, Run page, StartRun, small acts, print, definitions catalog, Your-work band | all | `screens/work.md` | `design-brief-work.md` | `work`, `work-run` not built; engine library built, no definitions registered | no (`#/work` not in `SCREENS`) | nothing; covered | - |
| E1. A built screen shown inside a step panel (compact variant, acts in place or linked out, what the step records) | all families | contradicts: `screens/work.md` links out; family pages embed | none | n/a | n/a | the embedding spec (write-next 1) | H: every family's Run page depends on the rule, and the two sources disagree |
| E2. The family step-panel gallery (which panel for which definition) | all | only in family pages section 5 | `design-brief-work.md` C3 draws the seven kinds only | n/a | n/a | fold into E1 | H (with E1) |
| E3. Routes in the information architecture | all | `information-architecture.md` lacks the routes listed above | none | n/a | n/a | an edit, not a new spec: add rows for every route a landed spec or brief proposes | M: cheap, and agents read this file to place a screen |
| The dock: each run's next clock, follow-ups | members, all | `screens/today.md`; `design-brief-work.md` C7 | same | `dock` built; run clocks and follow-ups not in it (members page 5.1) | `Dock` built; no run clock | nothing | - |

### Members (the owner-information cycle, notices, mail, requests, forms)

| Surface | Run | Spec | Brief | Loader | View | What to write | Priority |
|---|---|---|---|---|---|---|---|
| Funnel, follow-ups band, arrivals lane, scan review, cycle board, form library, campaigns | `owner-info-cycle`, `form-campaign`, `form-library-review` | `handoff-followups.md`, `handoff-responses.md`, `handoff-forms-and-arrivals.md`, `handoff-form-library.md` | `design-brief-forms.md` | `followups`, `campaign-status`, `responses`, `response`, `outstanding-responses`, `form-library` built; `cycle` (`/api/cycle`) not | no | nothing; covered | - |
| Notice record (six bands) and the proof page | `notice-delivery` | `screens/notices.md` | `design-brief-notices-and-mailroom.md` | `notices`, `notice` not built | no | nothing; covered | - |
| Mailroom list, preview, mail options, send plan | `mailroom-letter` | `screens/mailroom.md` | `design-brief-notices-and-mailroom.md` | `mailroom` not built | no | nothing; covered | - |
| Requests list and one request, request clock, acknowledgment draft | `respond-request`, `respond-sweep` | `screens/requests.md` | `requests-and-onboarding` (not landed) | `member-requests` not built; `records-requests` built | `RecordsRequestsView` built, no `#/requests` | confirm when the brief lands | - |
| Response standard: adoption, pauses, member words, metrics | `respond-policy` | `handoff-conversations-and-policies.md` | partly: `design-brief-mail-and-payments.md` lists the handoff in its reading order; depth not verified | not built (design only, members page gap 7) | no | confirm the brief draws it | L: board adopts after the screens exist |
| M0. Records request: fee cap (CIV 5205(g)) and the membership-list clock | `records-production` | none (grep of `docs/console` finds no spec of the cap; the clock reading is held for counsel) | none | `records-requests` built; `feeCents` checked only as non-negative | `RecordsRequestsView` | a short addendum to `screens/requests.md`: where a cap overrun and the held clock reading show | L: small, and the clock is held for counsel |
| Letter stages | `owner-document` | `screens/requests-and-links.md` | none needed | `approvals`, `templates`, `request-letter` built | `DraftsView`, `TemplatesView`, `ApprovalsView` built | nothing | - |

### The board (meetings, rules, hearings, elections, the law)

| Surface | Run | Spec | Brief | Loader | View | What to write | Priority |
|---|---|---|---|---|---|---|---|
| G1. Meeting watch, postings, record stages on `#/meetings`; `MeetingStrip` | `board-meeting` | `screens/meetings-and-minutes.md` (watch, checks); `MeetingStrip` is in no spec | none | `meeting-watch`, `record-stages` not built; `meetings`, `meeting`, `meeting-room`, `minutes-review` built | `MeetingsView` built without the bands | a brief covering G1 and G3 (write-next 6) | M: the secretary's clocks are CLI only |
| G2. `DecisionStep` panel | every `decision` step | `design-brief-work.md` C3 (a link to Decisions) | same | `decisions` built | `DecisionsView` built | settle with E1 (read-only embed of the decision record) | M |
| G3. Schedule by role, coverage band, "record done" | `duty-schedule`, `document-duties` | `screens/schedule-and-duties.md` | none | `schedule` not built; `duties`, `calendar` built | `DutiesView` built without the bands | in the same brief as G1 | M |
| Elections | `election` | `screens/elections.md` | `design-brief-board-records.md` | no store, no loader | no | nothing; covered | - |
| G4. Hearing: stages, notice, cure record, request for executive session, penalty schedule in force on the violation day, decision notice, one decision store | `hearing` | none for the process; `screens/meetings-and-minutes.md` has only the notice documents row and a clocks line | none | `hearings` built; cure record and executive-session request have no store | `HearingsView` built (stages and decision entry only) | the hearing spec (write-next 4) | H: a member's due-process clock, and the built view lacks the steps the law adds |
| G5. Law review: leads list, conflict rows | `law-review` | none for the leads (`conflicts --leads`); `handoff-citations.md` has `CitationGaps`; `handoff-programs.md` mentions the January review | none | `conflict-leads` not built; CLI and MCP only | `ReferenceShelfView` shows gaps only | the law-review spec (write-next 8) | M: yearly (January), recite-first rule applies |
| Rule change: proposals, comment record, reversal intake (CIV 4360, 4365) | `rule-change` | `handoff-rule-records.md` | none | `rule-records` and 5 siblings built (read only); proposal store not built | `RuleChangeView` built (old); no `#/documents/rules` | a brief for the handoff, after the store exists | M: spec exists; the store is the blocker |
| Owners' manual | `owners-manual` | `handoff-rules-and-authority.md`, `handoff-documents-studio.md` | none | partly | no | nothing yet | L: last in the board build order |
| Governance digest | board | `screens/today.md`, `screens/schedule-and-duties.md` | none | `governance-digest` not built | `DigestView` built | nothing | L |

### Money

| Surface | Run | Spec | Brief | Loader | View | What to write | Priority |
|---|---|---|---|---|---|---|---|
| Bill attach tab, investigation drawer, match panel | `bill-attach`, `payment-investigation` | `handoff-mail-and-payment-attachments.md` | `design-brief-mail-and-payments.md` | `bill-attach`, `bill-investigation` (loader and writer) built | no | nothing; covered | - |
| M1. Monthly review: the one read of budget, reconciliations, invoices, collections, ledger validation, with each snapshot's age; who reviewed, by which path (CIV 5500(a) or the independent review under 5501), the ratification | `monthly-review` | none; `screens/finance.md` has one row describing the Payments screen | none | `monthly-review` not built; the five parts are built | `MoneyView` and `BooksChecksView` built, no record of a review | the monthly-review spec (write-next 2) | H: monthly, statutory, all data built, only the record is missing |
| M2. Delinquency account: the steps CIV 5650 to 5720 add (meet and confer, request to meet, copy mailed, ADR, notice of default, small claims, vote separate from recording) and the clocks computed from them; the pre-lien notice preview | `delinquency-account` | thin: `screens/finance.md` row for `#/liens`; `handoff-reconciliation-5.md` covers only late-charge limits | none | `delinquency` and writer built; steps and clocks are code, not built (money page 7, 8) | `DelinquencyView` built with the coarse step list | the delinquency-steps spec (write-next 3) | H: lien clocks run against the owner and the association, and the built view hides them |
| Annual disclosure packet: checklist, parts, collect, checks, read-through, send plan | `fiscal-year` | `handoff-annual-disclosures.md` | partly: `design-brief-board-records.md` draws only the Collect tab | `annual-*` loaders not built | `CalendarView` only | a packet brief (write-next 5) | M: large, dated by statute, but the engine and loaders come first |
| M3. County tax cycle: parcel table (standing, unpaid or delinquent, bill PDF), receipts, the county bill source's chain | `county-tax-cycle` | none (`handoff-mail-and-payment-attachments.md` rows on county tax cover the payee class only; `screens/members-and-units.md` has a one-line taxes band per unit) | none | `tax-status`, `tax-receipts` not built (`tax_status`, `tax_account` exist) | no | a short `screens/county-tax.md` (see below, outside the top eight) | M: installments recur twice a year, but the Revenue and Taxation Code sections are not on the shelf, so no clock can be recited yet |
| M4. County records and land check (`jason county-records`, `jason land-check`) | `parcel-title`, `onboard` | none; the commands are uncommitted in the working tree | none | none | none | not verified what a console would need; decide first whether it has a screen | L |
| Reserve study, bank balances, ledger reports | `fiscal-year`, board | `screens/finance.md` (marked "to add") | none | `reserve-study`, `books-report` not built; balances: not verified | `ReservesView` built without them | brief with the packet, or leave | L |
| Reserve borrowing, insurance renewal | `reserve-borrowing`, `insurance-renewal` | `screens/finance.md`, `screens/mail.md` | none needed | `reserve-findings`, `insurance-renewals` built; `insurance-policies` not (minor) | `ReserveFindingsView`, `InsuranceRenewalsView` built | nothing | - |

### Documents and records

| Surface | Run | Spec | Brief | Loader | View | What to write | Priority |
|---|---|---|---|---|---|---|---|
| Onboarding run rail by gate, child-run rows | `onboard` | `screens/onboarding.md`, `screens/work.md` | `requests-and-onboarding` (not landed) | `onboarding-session` built | `OnboardingView` built, no rail | confirm when it lands | - |
| Record checklist, splitter, key documents, instruments | `record-slot`, `split-document`, `key-document` | `screens/records.md`, `screens/split.md` | not needed (built) | built | built | nothing | - |
| D1. Ingest report, library text, revisions | `ingest` | `screens/records-and-library.md` | none | `ingest`, `library-text`, `revisions` not built | `IngestionView` built (counts only) | brief with D3 | L: terminal path works today |
| D2. Recorder reading by number | `document-intake` D4, `key-document` K5 | none found (grep of `docs/console` for the recorder tools finds nothing; `handoff-title-processes.md` not read in full) | none | `recorder-reading` not built (MCP only) | no | a half-page in `screens/records-and-library.md` | L |
| D3. Intake review, confirmations queue, context-pack workbench, collection workspace, law as of a day and the quote check | `careful-reading`, `document-intake` | `handoff-intake-review.md`, `handoff-confirmations-queue.md`, `handoff-context-pack-workbench.md`, `handoff-collection-workspace.md`, `handoff-as-of-and-quote-check.md` | none | `record-readings`, `collections`, `legal-cases` built; others not | no | one brief over the five, when a family reaches `careful-reading` | L: last in the records build order |
| Document kinds | `ingest` | `screens/document-kinds.md`, `handoff-document-kinds.md` | none | `library-kinds` built | no | add to the D3 brief | L: loader built, cheap |
| Title and parcel processes | `parcel-title` | `handoff-title-processes.md` | none | `title-watch`, `instrument-graph` built; processes not | `TitleWatchView` built | nothing yet | L |
| Members and units, directory consent | board | `screens/members-and-units.md`, `handoff-directory-consent.md` | none | `unit-record` built; masking (P2) not | no | nothing until P2 masking exists | L |

### The property, its safety, its vendors

| Surface | Run | Spec | Brief | Loader | View | What to write | Priority |
|---|---|---|---|---|---|---|---|
| Life safety page, deficiency register and card, board item | `life-safety-period`, `deficiency` | `screens/life-safety.md` | `design-brief-life-safety.md` | `life-safety` and writer built | no | nothing; covered | - |
| Backflow card, report portals, filing plan, watchlist, document codes | `backflow-annual` | `handoff-inspections-and-portals.md` (sections of `#/life-safety`) | covered through the life-safety brief's reading list; depth not verified | `backflow`, `watchlist`, `report-portal`, `filing-plan`, `document-codes` built | no | confirm the brief draws the backflow card | - |
| P1. Paint | `paint-cycle` | `screens/paint.md`, `handoff-unit-records.md` | none | `paint`, `paint-color` built | no (components only) | a brief (write-next 7) | M: loader and components built, so it is the cheapest to draw |
| P2. Unit record, community facts, loss packet | `loss-claim` | `screens/unit-record.md`, `screens/community-facts.md`, `handoff-unit-records.md` | partly: the board-records brief covers an incident's paperwork and loss-packet section only | `unit-record`, `loss-packet`, `facts` and writers built | no | same brief as P1 | M |
| P3. Contracts: notice window (both edges), term, owed list, license chip, findings | `contract-notice-window` | `handoff-contracts.md` | none | `contracts` not built | no | a brief (write-next 7) | M: a legal-clock surface with a full handoff and no brief |
| P4. Home improvement requests | `improvement-request` | `handoff-improvement-requests.md`; `screens/requests.md` | `requests-and-onboarding` (not landed; the screens README makes it a band of `#/requests`) | `improvement-request` not built | no | confirm when it lands | - |
| P5. Programs register, maintenance programs, pest | `maintenance-program` | `handoff-programs.md` | none | `programs` not built; no web loader for the pest program | no | brief after P1 to P3 | L |
| P6. Elevated elements per building | `elevated-elements` | none for the panel; `handoff-programs.md` and `handoff-applicability-questions.md` mention it | none | not built (`calendar_rows` feeds the calendar) | no | a row in the programs brief | L |
| Incidents | `loss-claim` | `screens/incidents.md` | `design-brief-board-records.md` | no store | no | nothing; covered | - |

### Mail and running jason

| Surface | Run | Spec | Brief | Loader | View | What to write | Priority |
|---|---|---|---|---|---|---|---|
| Mail triage lanes | `mail-triage` | `screens/mail.md` | none needed (built) | built | `MailTriageView` built | nothing (office check on the loader is a code gap) | - |
| Email awaiting us, thread drawer | `email-conversation` | `handoff-mail-and-payment-attachments.md` | `design-brief-mail-and-payments.md` C4 | `open-items` built; `email-threads` not | `InboxView` built (table) | nothing | - |
| Draft from an item (three-case start form) | `gmail-draft` | `handoff-draft-from-item.md` | `design-brief-mail-and-payments.md` lists it as spec'd, not built; depth not verified | route `POST /api/approvals/plan` exists; no screen | no | confirm the brief draws the start form | - |
| Instance overview, service, schedules, integrations, setup dialogs, vault | `integration-connect`, `service-run` | `handoff-instance-and-integrations.md`, `handoff-admin-components.md` | `design-brief-forms.md` (section C, last rows) | `instance-service`, `instance-integrations`, `instance-schedules`, `status` built; vault JSON not | `StatusView` built; the three instance loaders have no view | nothing | - |
| A1. Integration disconnect | `integration-connect` | `screens/integration-disconnect.md` | none: `design-brief-forms.md` mentions "disconnect" once and `design-brief-work.md` not at all | not built | no | one section appended to the forms brief | L: administrator only, and the connect flow comes first |
| A2. The machine (storage, settings) | administrator | `handoff-storage-and-settings.md` | none | partly (`status`) | no | none yet | L |
| Check-in | `check-in` | none, by decision ("the console never starts check-in runs", workflows README decision 10) | n/a | n/a | n/a | nothing | - |

## 2. Write next (ranked, at most eight)

Each item names what the spec must contain and the document to base it on. All use the house rules in [screens/README.md](screens/README.md): recite then read, a miss stays a miss, every act is a `Confirm` signed by name with its CLI equivalent, no control approves or sends.

1. **Embedded step panels** (rows E1, E2, G2). Write `screens/run-embeds.md`, or a section of `screens/work.md` that supersedes its link-out rule. It must contain:
   - the rule for when a built screen embeds in a step versus links out, with one answer per step kind;
   - the compact variant of each embedded screen, named (`PlanReview`, `DelinquencyView`'s step panel, `RecordsView`'s slot, the decision record, `OwnerInfoView`, `MeetingsView` bands);
   - which acts may be done in place and how the run records them (an `attested` event pointing at the store row);
   - how "changed since" shows inside an embed;
   - a table of every definition's step panels.
   Base it on section 5 of each family page ([money](../workflows/money.md), [documents-records](../workflows/documents-records.md), [members-cycles](../workflows/members-cycles.md), [board-governance](../workflows/board-governance.md), [property-safety-vendors](../workflows/property-safety-vendors.md), [mail-and-platform](../workflows/mail-and-platform.md)), `screens/work.md` ("Layout: one run"), and `design-brief-work.md` C3. Resolve by recommending one rule and listing the exceptions; the design agent cannot draw a Run page until this is settled.

2. **Monthly review** (M1). Write `screens/monthly-review.md`. It must contain:
   - the run page (`monthly-review`) and its record: reviewer by name, the path (CIV 5500(a) review, or the independent review of 5501), the date, the ratification meeting, and a link to the minutes' words;
   - the `monthly-review` loader's shape (one read of `budget`, `reconciliations`, `invoices`, `collections`, `ledger-validation`, each with its snapshot age);
   - the states from the money page (stale, missing, changed since, waiting on the board);
   - the statutes recited whole;
   - the privacy level (delinquency is executive-session material, CIV 4935).
   Base it on [money.md](../workflows/money.md) section 2 (`monthly-review`) and section 8 (gap "The treasurer's review leaves no record of who reviewed"), `screens/finance.md`, and the `payhoa-attach-bills` row of `approval-workflow.md`.

3. **Delinquency steps and clocks** (M2). Write `screens/liens.md` (or extend `screens/finance.md`). It must contain:
   - the full step list under CIV 5650 to 5720 (the seven missing steps are in the money page's gap list), each with its recited statute;
   - the five clocks computed from them, each labeled by basis (`Basis.LAW`);
   - the board's vote shown apart from the recording;
   - the pre-lien notice preview (no base template exists; say so in the empty state);
   - the executive-session banner and the missing office check on the loader.
   Base it on [money.md](../workflows/money.md) section 2.4 and section 8, the built `DelinquencyView`, `jason.tasks.collection_steps`, and `handoff-reconciliation-5.md` (late-charge limits, CIV 5650(b)).

4. **Hearing** (G4). Write `screens/hearings.md`. It must contain:
   - the run's stages (notice by, hearing, decision by) with their statutory basis, the member's right to be heard, and the request for executive session;
   - the cure record (CIV 5855(c)) and the penalty-schedule check (5850(c)) against the schedule in force on the violation's day;
   - the decision-notice preview and the single decision store (the hearing row links the decision id; the id is opaque, never an address);
   - the private-view rule (P3), and the empty and missing states ("no hearings saved; plan one with `jason hearing`").
   It must mark the suspension-notice section (Corporations Code 7341) as not on the shelf. Base it on [board-governance.md](../workflows/board-governance.md) sections 2.4, 5, and 8, `screens/meetings-and-minutes.md`, and the built `HearingsView`.

5. **Annual disclosure packet brief** (fiscal-year). Write `design-brief-annual-packet.md` in the house brief shape (A idea and rules, B reading order, C screens, D components once, E glyphs, F decisions, G now versus waits, H a made-up community). It must cover the packet's stages, requirement checklist, parts, collect list, checks, read-through, and send plan, tied to the fiscal-year run's clocks strip. Base it on `handoff-annual-disclosures.md`, [money.md](../workflows/money.md) section 5 (`fiscal-year` row), and `design-brief-board-records.md` C4 (which already draws the Collect tab, so link it).

6. **Governance calendar brief** (G1, G3, G2). Write `design-brief-governance-calendar.md`. It must cover the meeting watch band, postings, record stages, `MeetingStrip`, the schedule by role, `CoverageBand`, "record a posting", and "record done" on `#/meetings` and `#/duties`. Base it on `screens/meetings-and-minutes.md`, `screens/schedule-and-duties.md`, and [board-governance.md](../workflows/board-governance.md) section 5 ("What is specific to the family"). Say which parts draw from built loaders (`meetings`, `duties`, `calendar`) and which wait on `meeting-watch`, `record-stages`, `schedule`.

7. **Property and units brief** (P1, P2, P3). Write `design-brief-property-and-units.md`. It must cover:
   - `#/paint`;
   - the unit record, community facts, and loss packet (`#/members?unit=`, `#/facts`, `#/loss-packet`);
   - the contract notice window with both edges side by side, no winner.
   Paint and unit-record are first because their loaders are built. Base it on `screens/paint.md`, `screens/unit-record.md`, `screens/community-facts.md`, `handoff-unit-records.md`, `handoff-contracts.md`, and [property-safety-vendors.md](../workflows/property-safety-vendors.md) section 5.

8. **Law review** (G5). Write `screens/law-review.md`. It must contain:
   - the `LeadList`: each change in the Act since a document was written, with the citing section, the statute recited first (`Recitation`), then the reading under `ReadingLabel`;
   - the acts "Record no conflict", "Record a conflict row to add to the profile", "Put on the board's agenda";
   - the `conflict-leads` loader's shape, and the `Conflict` row display (plain versus a question for counsel).
   Base it on [board-governance.md](../workflows/board-governance.md) section 2.5 and the `LeadList` line of section 5, `handoff-citations.md` (`CitationGaps`), the "January law review" note in `handoff-programs.md`, and AGENTS.md "Follow what is written".

**Outside the top eight, in priority order:** the county tax cycle (M3: a parcel table over a `tax-status` loader; recite no clock until the Revenue and Taxation Code sections are on the shelf); the routes pass on [information-architecture.md](information-architecture.md) (E3); the rule-change proposals brief once the store exists; the careful-reading brief (D3 plus document kinds); integration disconnect (append to the forms brief); the machine; programs and elevated elements.

## 3. Not verified

- Whether `design-brief-forms.md` and `design-brief-mail-and-payments.md` fully draw the surfaces their reading lists point to (the response-standard screens, the draft start form): only their section C tables were read.
- The contents of the `requests-and-onboarding` brief, which had not landed.
- The relation between `src/jason/console/ui` and `ui/src/components`.
- Whether `handoff-title-processes.md` specifies a recorder reading by number (grep found no match for the tool names; the file was not read in full).
- Whether the `Dock` and `DigestView` already show any run clock (the workflows pages say not; no `work` loader exists to feed them).
- Whether any loader in "built" carries an office check; the family pages say several do not (`mail-triage`, `open-items`, `delinquency`).
