# Design gaps: which screens and flows still have no spec or brief for the design agent

First audit 2026-10-11; refreshed the same day after the Work, Controls, and office-lens builds. This page lists what is missing and what to write next. It was made by reading the six family pages ([../workflows/README.md](../workflows/README.md) and the pages it lists), [../workflows-design.md](../workflows-design.md), every page in [screens/](screens/README.md), every `handoff-*.md`, and every `design-brief-*.md`, then checking the loaders in `src/jason/web/sources.py` (`EXTRA_LOADERS`, `_loaders`), the gates in `src/jason/web/gates.py`, the owner allowlist in `src/jason/web/extra/owner_view.py`, and the views in `ui/src` (`SCREENS` in `App.tsx`, `ui/src/views`, `ui/src/components`).

**How "built" was checked.**
- *Loader built*: the source name is a key in `EXTRA_LOADERS` or `_loaders()`.
- *View built*: the screen is in `SCREENS`, or the source's `/api/NAME` is read by a non-test file in `ui/src`. A script listed every loader key and searched `ui/src` (tests and fixtures excluded) for it; each hit that could be a common word (`facts`) was checked by hand.
- A cell that could not be checked says "not verified".

> **What changed, 2026-10-11 (since the first audit).**
> - **Built:** the workflows engine, `jason workflow`, and two registered definitions (`owner-info-cycle`, `control-adoption`; `definitions_general.py`). The Work backend (`work`, `work-run`, `work-definitions` and the `work` writer) and the Work screens (`#/work` in `SCREENS`: list, run page with rail and step panels by kind, definitions, Start a run). Controls: the catalog, suggest, effective rule, engine hook, loaders (`controls`, `control`, `control-notices`), the Controls screen (`#/controls`), `ControlNotice` on plans and workflow steps, the optional onboarding step. The office view: loader `office-view`, `OfficeLens`, and the lens on Today. The Mailroom preview record, fingerprint, and the two-person approvals kind `payhoa-mailroom-send` (terminal-only apply). Gating of every loader (`gates.py`; `tests/test_loaders_are_gated.py` and `tests/fixtures/loader_gates.json`).
> - **Written:** the briefs `notices-and-mailroom`, `board-records`, `requests-and-onboarding`, `life-safety`, `annual-disclosures`, `governance-calendar`, `property-and-units`, `money-reviews`, `platform`, `controls`, `work`; the specs `mailroom`, `elections`, `collect-items`, `incidents`, `integration-disconnect`, `monthly-review`, `delinquency-process`, `hearing-process`, `law-review`, `office-views`, `controls`, `work` (with the embed rule).
> - **Left over from the first audit, now closed:** E1, E2, G2 (embedding: `screens/work.md`, "Where a step's work happens"); M1 and M2 (specs and a brief); G4 and G5 (specs); G1, G3, M-annual, P1 to P3 (briefs); A1 (the platform brief's C5). The office-check question on `mail-triage`, `open-items`, and `delinquency` is closed: `gates.py` gates all three at P2.
> - **New gaps the builds exposed** (section "Read this first"): the run pages link to their owning screens but nothing links back, the embed is a rule with no component, `#/decisions` cannot show the decisions seven specs send people to, and the Work loader cannot hide an executive-session run.
> - **Still no spec at all:** the county tax cycle (the Revenue and Taxation Code installment sections are not on the shelf), the owner's side of the new subjects, the Decisions screen as a record, and the run-to-screen links.

## Read this first (surprises)

1. **The Work screens are built and nearly empty, and they link out blindly.**
   - Only two definitions are registered (`owner-info-cycle`, `control-adoption`). The family pages define about fifty more; until they register, `#/work` can list only those two.
   - `RunStepPanel` draws each step by kind. Its "Look at" area lists evidence addresses only; no owning component is embedded (`ui/src/components/RunStepPanel.tsx`, the `Look at` section). The embed rule in `screens/work.md` has no component yet (the briefs name `RunEmbed`, `PartOfRun`, `PartOfRunBanner`; none is in `ui/src`).
   - A `plan` step links to `#/approvals` and a `decision` step to `#/decisions`, with no id and no filter. `ApprovalsView` keeps the open plan in component state (`PlanApprovals`' `open`), not in the hash; I found no hash read in `ApprovalsView` or `DecisionsView` (grep; not verified by running them). `work.py` gives a link only `screen: "approvals"` or `"work"`.
   - The "Part of run NAME, step N" banner on an owning screen is in five briefs and `screens/work.md`, and in no code (`grep -ri "part of run" ui/src src` finds nothing). No loader answers "which open run does this subject belong to".
   - `work.py` says in its docstring that executive-session handling "is not composed: no definition marks a step executive". `screens/work.md` requires a held run to show by general words only. Registering `delinquency-account` or `hearing` before that is built would put a parcel or a unit in a Work row's label.
2. **Seven specs send a decision to `#/decisions`, and that screen cannot show it.** `DecisionsView` reads `/api/agenda-plan` (the next meeting's candidates) and posts to `/api/decisions`. The `decisions` loader (all, or `?meeting=`) is read by no view (grep). The specs that say "the secretary records it in Decisions": controls, hearing-process, elections (acclamation), law-review, monthly-review (ratification), delinquency-process (the lien vote), incidents (a claim). Past decisions, one decision by id, a decision's kind, and a decision linked to a run step have no screen and no spec. The hearing spec's "Decisions for the user 1" (one decision store) is also open.
3. **A statement in a document is stale in nine files** (listed in section 3). The worst: [../workflows/README.md](../workflows/README.md) lines 3 and 16 still say "none of the engine below is built yet" and "no definition is registered, there is no `jason workflow` command, no `work` or `work-run` loader, and no view", and [design-brief-work.md](design-brief-work.md) line 3 says "None of the engine is built". The previous status note of this page said the README no longer says so; it does.
4. **30 built loaders have no view.** The first audit counted about 35. Now without a view: `backflow`, `bill-attach`, `bill-investigation`, `campaign-status`, `document-codes`, `facts`, `filing-plan`, `followups`, `form-library`, `instance-integrations`, `instance-schedules`, `instance-service`, `library-kinds`, `life-safety`, `loss-packet`, `outstanding-responses`, `paint`, `paint-color`, `record-readings`, `report-portal`, `response`, `responses`, `rule-events`, `rule-record`, `rule-record-compare`, `rule-record-history`, `rule-records`, `rule-uses`, `unit-record`, `watchlist`. (`drive-list`, `drive-search`, `drive-resolve`, and `library-files` also show no hit, but `DriveChooser` and the splitter read them by POST; they are not gaps.) The rule-records family is six loaders with no brief; paint, the unit record, and life safety each have a brief now.
5. **`MaskedField` is specified and not built.** [components.md](components.md) and [security-and-privacy.md](security-and-privacy.md) name it (server-side P2 masking with a logged reveal); no file in `ui/src` has it. `screens/mailroom.md` says its recipient table "is not built" until it exists, and `screens/members-and-units.md` is phase 4 on it. This blocks two screens and no spec owns it.
6. **A run id in a URL may carry a parcel number.** [design-brief-money-reviews.md](design-brief-money-reviews.md) draws `#/work/delinquency-account/<apn>`. `screens/work.md` (Privacy) says a list and a URL carry "an id or a filter, never a name, an email, or an address". An APN identifies an owner through the public record, and the delinquency spec treats the account as executive-session material (CIV 4935). I did not find how `jason.workflows.api.start` forms a run id (not verified). The spec must say whether the id is opaque.
7. **The Mailroom's approvals kind is registered and its console drawing is not verified.** `payhoa-mailroom-send` is in `jason.approvals.registry`. `PlanReview` is generic; whether it shows a preview record's fingerprint, page count, and cost for this kind was not checked. `screens/mailroom.md` lists "the console drawing of the kind" as to add.
8. **`src/jason/console/ui/`** (a static component library; README, `tokens.css`, `components/`, `previews/`) is still untracked (`git status` shows `?? src/jason/console/`). How it relates to `ui/src/components` was not verified.
9. **Two files of the working tree changed under this audit** (`docs/console/information-architecture.md`, `docs/console/README.md`: three and nine lines). [information-architecture.md](information-architecture.md) now has `#/work`, `#/notices`, `#/instance`, `#/requests`, `#/hearings` and still has no `#/life-safety`, `#/paint`, `#/mailroom`, `#/elections`, `#/incidents`, `#/followups`, `#/responses`, `#/cycle`, `#/forms`, `#/monthly-review`, or `#/controls` (case-insensitive grep, one route at a time).

## 1. The table

Columns: surface | family or run | spec (path) | brief (path) | loader built? | view built? | what to write | priority (H, M, L, or "-" when covered) with one reason.

Paths are under `docs/console/` unless they start with `../`. "Family pages" are `../workflows/*.md`. A brief's depth was read at its head, its section C table, and its "what can be designed now" table (G); the interior of each was not read in full ("depth not verified").

### Common to every family

| Surface | Run | Spec | Brief | Loader | View | What to write | Priority |
|---|---|---|---|---|---|---|---|
| Work list, Run page, StartRun, small acts, print, definitions catalog | all | `screens/work.md` | `design-brief-work.md` (header stale: "none of the engine is built") | `work`, `work-run`, `work-definitions` and the `work` writer built (`EXTRA_LOADERS`, `EXTRA_WRITERS`); only 2 definitions registered | `WorkView`, `WorkRunView`, `WorkDefinitionsView`, `StartRun` built; `#/work` in `SCREENS`, roles officer, manager, administrator | nothing for the screens; register the other definitions (build work) | - |
| L1. Run links: banner on the owning screen, deep links into it, the embed frame, a held run | all families | the rule only: `screens/work.md`, "Where a step's work happens" | named in 5 briefs (`PartOfRunBanner`, `RunEmbed`); none draws the loader | no banner loader; `RunLink.screen` carries a screen name, no id | none: `RunStepPanel` "Look at" lists addresses; `#/approvals` and `#/decisions` links are unfiltered | the run-links spec (write-next 1) | H: every family's run page depends on it, and two screens already link to a page that cannot receive the link |
| E3. Routes in the information architecture | all | `information-architecture.md` lacks the routes in "Read this first" 9 | none | n/a | n/a | an edit, not a new spec | M: cheap, and agents read this file to place a screen |
| The dock, Today's "Your work" band | all | `screens/today.md`, `screens/office-views.md` | `design-brief-work.md` C7 | `dock` built (no run clock in it: `dock.py` has no run read); `office-view` built and carries a `work` band | `OfficeLens`, `OfficeToday` built (rows link to `#/work/<definition>/<id>`); `Dock` built without run clocks | nothing; the dock's run clock is a build item | - |
| Controls: catalog, one control (six bands), propose to the board, roster check, the one-line notice | all (gates on plans, steps, sends) | `screens/controls.md` (header stale: "the screen is not" built) | `design-brief-controls.md` (header stale: loaders "not built") | `controls`, `control`, `control-notices` and the `controls` writer built | `ControlsView` built, `#/controls` in `SCREENS`; `ControlNotice` in `PlanReview` and `RunStepPanel` | nothing; whether a control's notice also shows on the Mailroom send (the kind is a plan, so through `PlanReview`) is not verified | - |
| Office lens (any board member reads any office's Today) | all | `screens/office-views.md` | none needed | `office-view` built | built | nothing | - |
| Loader gates | platform | `screens/*.md` each name a level; no spec of the table itself | none needed | `gates.py`, one table | n/a | nothing | - |

### Members (the owner-information cycle, notices, mail, requests, forms)

| Surface | Run | Spec | Brief | Loader | View | What to write | Priority |
|---|---|---|---|---|---|---|---|
| Funnel, follow-ups band, arrivals lane, scan review, cycle board, form library, campaigns | `owner-info-cycle` (registered), `form-campaign`, `form-library-review` | `handoff-followups.md`, `handoff-responses.md`, `handoff-forms-and-arrivals.md`, `handoff-form-library.md` | `design-brief-forms.md` | `followups`, `campaign-status`, `responses`, `response`, `outstanding-responses`, `form-library` built; `cycle` not | no (`OwnerInfoView` is the old screen) | nothing; covered | - |
| Notice record (six bands) and the proof page | `notice-delivery` | `screens/notices.md` | `design-brief-notices-and-mailroom.md` | `notices`, `notice` not built (stores under `jason.tasks.notice_*` exist) | no | nothing; covered | - |
| Mailroom list, preview, mail options, send plan | `mailroom-letter` | `screens/mailroom.md` | `design-brief-notices-and-mailroom.md` | `mailroom` not built; the preview record, fingerprint, `--expect`, `--approval`, and the kind `payhoa-mailroom-send` are | no; recipient table also waits on `MaskedField` | nothing; covered (build the loader; see "Read this first" 5 and 7) | - |
| Requests list and one request, request clock, acknowledgment draft | `respond-request`, `respond-sweep` | `screens/requests.md` (its roles line is stale: the brief says so) | `design-brief-requests-and-onboarding.md` (landed; its sections C and G read, depth not verified) | `member-requests` not built; `records-requests` built | `RecordsRequestsView` built, no `#/requests` | nothing; covered | - |
| Response standard: adoption, pauses, member words, metrics | `respond-policy` | `handoff-conversations-and-policies.md` | the requests brief's G table draws "the rule row as built (10 fields)"; the rest "design only" | not built | no | nothing until the board adopts a standard | L |
| M0. Records request: fee cap (CIV 5205(g)) and the membership-list clock | `records-production` | none (grep of `docs/console` finds no spec of the cap; the clock reading is held for counsel) | none | `records-requests` built; `feeCents` checked against the stored 5205(g) figures (`tasks.records_fee`; an over-cap fee is refused with the statute's words) | `RecordsRequestsView` | a short addendum to `screens/requests.md` | L: small, and the clock is held for counsel |
| Letter stages | `owner-document` | `screens/requests-and-links.md` | none needed | `approvals`, `templates`, `request-letter` built | `DraftsView`, `TemplatesView`, `ApprovalsView` built | nothing | - |
| O1. What a member sees of any of this | all | none: each new spec says "the owner view is refused" (`elections`, `controls`, `mailroom`, `delinquency-process`, `hearing-process` "a member sees only their own notice"); `handoff-rule-records.md` decision 7 and `handoff-annual-disclosures.md` decision 7 ask the question and leave it open | none | `OWNER_SOURCES` lists 9 sources (`owner-digest`, `meetings`, `calendar`, `records-requests`, `reserves`, `insurance`, `meeting-room`, `community-profile`, `theme`) | `OwnerDigestView`, `OwnerPageView`, and the owner variants of five screens | the owner-view spec (write-next 4) | M: the law has the association give members notice of a proposed rule change and of an election; no spec says where a member reads either |

### The board (meetings, rules, hearings, elections, the law)

| Surface | Run | Spec | Brief | Loader | View | What to write | Priority |
|---|---|---|---|---|---|---|---|
| G1. Meeting watch, postings, record stages on `#/meetings`; `MeetingStrip` | `board-meeting` | `screens/meetings-and-minutes.md` | `design-brief-governance-calendar.md` | `meeting-watch`, `record-stages` not built; `meetings`, `meeting`, `meeting-room`, `minutes-review` built | `MeetingsView` built without the bands | nothing; covered | - |
| G3. Schedule by role, coverage band, "record done" | `duty-schedule`, `document-duties` | `screens/schedule-and-duties.md` | `design-brief-governance-calendar.md` | `schedule` not built; `duties`, `calendar` built | `DutiesView` built without the bands | nothing; covered | - |
| D-REC. Decisions as a record: past decisions, one by id, its kind, the run step it answers, executive-session decisions held | every `decision` step; control adoption, hearing findings, acclamation, law-review outcome, ratification, lien vote, claim | none: the only spec is two rows in `screens/meetings-and-minutes.md` (the sources chips; the `DecisionBrief`) | `design-brief-work.md` (a `decision` step is a link) | `decisions` built (all, or `?meeting=`; gate P2); no loader joins a decision to a run | `DecisionsView` reads `/api/agenda-plan` only; the `decisions` loader is read by no view | the Decisions spec (write-next 2) | H: seven specs send their outcome here, and the screen shows only the next meeting's candidates |
| Elections | `election` | `screens/elections.md` | `design-brief-board-records.md` (its "checked against the code" paragraph says no `work` route; stale) | no store (`ls src/jason/tasks` has no elections module), no loader | no | nothing; covered | - |
| G4. Hearing: stages, notice, cure record, request for executive session, penalty schedule in force on the violation day, decision notice, one decision store | `hearing` | `screens/hearing-process.md` | none (the governance-calendar and money briefs do not draw it) | `hearings` built; cure record and executive-session request have no store | `HearingsView` built (stages and decision entry only) | a brief with G5 (write-next 3) | H: a member's due-process clock, and the built view lacks the steps the law adds |
| G5. Law review: leads list, conflict rows | `law-review` | `screens/law-review.md` | none (the governance-calendar brief lists it as "a link only") | `conflict-leads` not built; CLI and MCP only | `ReferenceShelfView` shows gaps only | in the same brief as G4 | M: yearly (January) |
| Rule change: proposals, comment record, reversal intake (CIV 4360, 4365); the adopted rule and its history | `rule-change`, `owners-manual` | `handoff-rule-records.md`, `handoff-rules-and-authority.md`, `screens/governing-documents.md` | none | `rule-records` and its five siblings built (read only, P0); proposal store not built | `RuleChangeView` built (old); no `#/documents` or `#/documents/rules` | a brief (write-next 6) | M: six loaders and three specs, no brief |
| Governance digest | board | `screens/today.md`, `screens/schedule-and-duties.md` | none | `governance-digest` not built | `DigestView` built | nothing | L |

### Money

| Surface | Run | Spec | Brief | Loader | View | What to write | Priority |
|---|---|---|---|---|---|---|---|
| Bill attach tab, investigation drawer, match panel | `bill-attach`, `payment-investigation` | `handoff-mail-and-payment-attachments.md` | `design-brief-mail-and-payments.md` | `bill-attach`, `bill-investigation` (loader and writer) built | no | nothing; covered | - |
| M1. Monthly review: the read of budget, reconciliations, invoices, collections, ledger validation with each snapshot's age; who reviewed, by which path (CIV 5500, 5501), the ratification | `monthly-review` | `screens/monthly-review.md` | `design-brief-money-reviews.md` | `monthly-review` not built; the five parts are | `MoneyView`, `BooksChecksView` built, no record of a review | nothing; covered | - |
| M2. Delinquency account: the 22 steps of CIV 5650 to 5720 and the clocks computed from them; the pre-lien notice preview | `delinquency-account` | `screens/delinquency-process.md` | `design-brief-money-reviews.md` (C5, C6) | `delinquency` and writer built; steps and clocks are code, not loader | `DelinquencyView` built with the coarse step list | nothing; covered. Decide whether the run id carries an APN ("Read this first" 6) | - |
| Annual disclosure packet: checklist, parts, collect, checks, read-through, send plan | `fiscal-year` | `handoff-annual-disclosures.md`, `screens/collect-items.md` | `design-brief-annual-disclosures.md`; `design-brief-board-records.md` C4 (Collect tab) | `annual-*` loaders not built (none in `EXTRA_LOADERS`) | `CalendarView` only | nothing; covered | - |
| M3. County tax cycle: parcel table (standing, unpaid or delinquent, bill PDF), receipts, the county bill source's chain | `county-tax-cycle` | none | none (`design-brief-mail-and-payments.md` draws the payee class and a receipt candidate only) | `tax-status`, `tax-receipts` not built (`tax_status`, `tax_account` exist in MCP; `jason.tasks.tax_receipts` stores receipts) | no | `screens/county-tax.md` (write-next 5) | M: installments recur twice a year, and no clock can be recited |
| M4. County records and land check (`jason county-records`, `jason land-check`) | `parcel-title`, `onboard` | none; the commands are still untracked | none | none | none | decide first whether it has a screen | L |
| Reserve study, bank balances, ledger reports | `fiscal-year`, board | `screens/finance.md` (marked "to add") | none | `reserve-study`, `books-report` not built; balances: not verified | `ReservesView` built without them | brief with the packet, or leave | L |
| Reserve borrowing, insurance renewal | `reserve-borrowing`, `insurance-renewal` | `screens/finance.md`, `screens/mail.md` | none needed | `reserve-findings`, `insurance-renewals` built; `insurance-policies` not (minor) | `ReserveFindingsView`, `InsuranceRenewalsView` built | nothing | - |

### Documents and records

| Surface | Run | Spec | Brief | Loader | View | What to write | Priority |
|---|---|---|---|---|---|---|---|
| Onboarding run rail by gate, child-run rows, change of manager | `onboard` | `screens/onboarding.md`, `screens/work.md` | `design-brief-requests-and-onboarding.md` | `onboarding-session` built | `OnboardingView`, `OnboardingSetup` built, no rail; the optional controls step is built (`OnboardingControls`) | nothing; covered | - |
| Record checklist, splitter, key documents, instruments | `record-slot`, `split-document`, `key-document` | `screens/records.md`, `screens/split.md` | not needed (built) | built | built | nothing | - |
| D1. Ingest report, library text, revisions | `ingest` | `screens/records-and-library.md` | none | `ingest`, `library-text`, `revisions` not built | `IngestionView` built (counts only) | brief with D3 | L: terminal path works today |
| D2. Recorder reading by number | `document-intake` D4, `key-document` K5 | none found (grep of `docs/console` for the recorder tools finds nothing; `handoff-title-processes.md` not read in full) | none | `recorder-reading` not built (MCP only) | no | a half-page in `screens/records-and-library.md` | L |
| D3. Intake review, confirmations queue, context-pack workbench, collection workspace, law as of a day and the quote check, document kinds | `careful-reading`, `document-intake`, `ingest` | `handoff-intake-review.md`, `handoff-confirmations-queue.md`, `handoff-context-pack-workbench.md`, `handoff-collection-workspace.md`, `handoff-as-of-and-quote-check.md`, `screens/document-kinds.md` | none | `record-readings`, `library-kinds`, `collections`, `legal-cases` built; others not | no | one brief over the six (write-next 7) | L: last in the records build order, but the only big family still without a brief |
| Governing documents `#/documents` | board | `screens/governing-documents.md` | none | `governing-documents` built | no `#/documents` in `SCREENS` | brief with the rule records (write-next 6) | M |
| Title and parcel processes | `parcel-title` | `handoff-title-processes.md` | none | `title-watch`, `instrument-graph` built; processes not | `TitleWatchView` built | nothing yet | L |
| Members and units, directory consent | board | `screens/members-and-units.md`, `handoff-directory-consent.md` | none | `unit-record` built; masking not | no | nothing until `MaskedField` exists | L |

### The property, its safety, its vendors

| Surface | Run | Spec | Brief | Loader | View | What to write | Priority |
|---|---|---|---|---|---|---|---|
| Life safety page, deficiency register and card, board item | `life-safety-period`, `deficiency` | `screens/life-safety.md` | `design-brief-life-safety.md` | `life-safety` and writer built | no | nothing; covered | - |
| Backflow card, report portals, filing plan, watchlist, document codes | `backflow-annual` | `handoff-inspections-and-portals.md` | covered through the life-safety brief's reading list; depth not verified | `backflow`, `watchlist`, `report-portal`, `filing-plan`, `document-codes` built | no | confirm the brief draws the backflow card | - |
| P1. Paint | `paint-cycle` | `screens/paint.md`, `handoff-unit-records.md` | `design-brief-property-and-units.md` | `paint`, `paint-color` built | no (components only) | nothing; covered | - |
| P2. Unit record, community facts, loss packet | `loss-claim` | `screens/unit-record.md`, `screens/community-facts.md`, `handoff-unit-records.md` | `design-brief-property-and-units.md`; the incident side in `design-brief-board-records.md` | `unit-record`, `loss-packet`, `facts` and writers built | no | nothing; covered | - |
| P3. Contracts: notice window (both edges), term, owed list, license chip, findings | `contract-notice-window` | `handoff-contracts.md` | `design-brief-property-and-units.md` | `contracts` not built | no | nothing; covered | - |
| P4. Home improvement requests | `improvement-request` | `handoff-improvement-requests.md`; `screens/requests.md` | `design-brief-property-and-units.md`; `design-brief-requests-and-onboarding.md` | `improvement-request` not built | no | nothing; covered | - |
| P5. Programs register, maintenance programs, pest | `maintenance-program` | `handoff-programs.md` | none | `programs` not built; no web loader for the pest program | no | a brief (write-next 8) | L |
| P6. Elevated elements per building | `elevated-elements` | none for the panel; `handoff-programs.md` and `handoff-applicability-questions.md` mention it | none | not built (`calendar_rows` feeds the calendar) | no | a row in the programs brief | L |
| Incidents | `loss-claim` | `screens/incidents.md` | `design-brief-board-records.md` | no store (`jason.tasks.incidents` is the paperwork history, not the record) | no | nothing; covered | - |

### Mail and running jason

| Surface | Run | Spec | Brief | Loader | View | What to write | Priority |
|---|---|---|---|---|---|---|---|
| Mail triage lanes | `mail-triage` | `screens/mail.md` | none needed (built) | built; gated P2 | `MailTriageView` built | nothing | - |
| Email awaiting us, thread drawer | `email-conversation` | `handoff-mail-and-payment-attachments.md` | `design-brief-mail-and-payments.md` C4 | `open-items` built (gated P2); `email-threads` not | `InboxView` built (table) | nothing | - |
| Draft from an item (three-case start form) | `gmail-draft` | `handoff-draft-from-item.md` | `design-brief-mail-and-payments.md` lists it as spec'd, not built; depth not verified | route `POST /api/approvals/plan` exists; no screen | no | confirm the brief draws the start form | - |
| Instance overview, service, schedules, integrations, setup dialogs, vault | `integration-connect`, `service-run` | `handoff-instance-and-integrations.md`, `handoff-admin-components.md` | `design-brief-platform.md`; `design-brief-forms.md` (section C, last rows) | `instance-service`, `instance-integrations`, `instance-schedules`, `status` built; vault JSON not | `StatusView` built; the three instance loaders have no view | nothing | - |
| A1. Integration disconnect | `integration-connect` | `screens/integration-disconnect.md` | `design-brief-platform.md` C5 | not built | no | nothing; covered | - |
| A2. The machine (storage, settings) | administrator | `handoff-storage-and-settings.md` | `design-brief-platform.md` lists it in its reading order; whether it draws it: not verified | partly (`status`) | no | confirm the platform brief draws it | L |
| Check-in | `check-in` | none, by decision (workflows README decision 10) | n/a | n/a | n/a | nothing | - |

## 2. Write next (ranked, at most eight)

Each item names what the spec must contain and the document to base it on. All use the house rules in [screens/README.md](screens/README.md): recite then read, a miss stays a miss, every act is a `Confirm` signed by name with its CLI equivalent, no control approves or sends.

1. **Run links** (row L1). Write `screens/run-links.md`: the contract between a run and the screen that owns a step's subject. It must contain:
   - **The banner source.** One server-side helper that every owning loader calls to attach `run: {definition, id, step, n, title}` to a row (recommended), or one loader (`work-for?kind=&id=`), not a fetch per row from the browser. Say which owning loaders get it first (`approvals`, `decisions`, `notices`, `mailroom`, `life-safety`, `delinquency`, `hearings`). The banner appears only to a viewer who may see the run, and it carries the run's label, never a subject.
   - **The deep-link grammar.** `RunLink.screen` becomes `screen` plus `address` and a query the screen reads (`#/approvals?plan=ID`, `#/decisions?id=ID`, `#/notices?key=KEY`, `#/mailroom?preview=ID`), as `#/actions?item=` already does (`BoardItemsView.focusedItem`). One table, one row per owning screen, with what it does when the id is gone ("not found", never a blank page).
   - **The embed frame.** `RunEmbed`: the compact variant of an owning component, fed by the same loader, read only, with "Open in NAME" and the "changed since" difference (`ChangedSince`) for an embed whose store moved. Name which components embed first (the funnel, a notice's six bands, a mailing's cost line, `PaletteMatrix` rows, the review matrix, the Collect list).
   - **A held run.** What marks a step or a definition executive (CIV 4935(e)) so that `work`, `work-run`, `office-view`, and the banner show general words only. This is the missing piece in `work.py`'s `notComposed`.
   - **The run id.** Whether it may carry a parcel or unit (the delinquency brief draws an APN in the path).
   Base it on `screens/work.md` ("Where a step's work happens", Privacy, States), `design-brief-work.md` C3 and C7, the "Part of run" sentences in `design-brief-annual-disclosures.md`, `design-brief-governance-calendar.md`, `design-brief-notices-and-mailroom.md`, and `design-brief-property-and-units.md`, `src/jason/web/extra/work.py` (`_link_state`, `notComposed`), and `ui/src/components/RunStepPanel.tsx`.

2. **Decisions** (row D-REC). Write `screens/decisions.md`. It must contain:
   - the list of recorded decisions by meeting (the `decisions` loader), with a filter by kind and by the run or board item that asked for it, so "Record in Decisions" lands on a decision, not a page;
   - **decision kinds** and their outcome words, one row each: control adopted, declined, or deferred (with the effective date); hearing findings and the decision notice's due day (CIV 5855); the acclamation of candidates; the law-review outcome (amend, ask counsel, leave); the monthly review's ratification; the lien vote (open session, roll call); a claim decision;
   - the secretary's recording form, prefilled from the thing that asked (a control, a hearing, a run step), with no vote control and no recommendation;
   - how a decision links back to the run step (the id the step stores) and forward (the hearing row holds `decisionId` and nothing of the decision, the recommendation in `screens/hearing-process.md` "Decisions for the user 1");
   - executive-session decisions: held by their CIV 4935 subject (`decisions.general_notes`), shown in full only in the private view, each opening logged;
   - what happens to the built next-meeting plan layout (recommended: it becomes a tab, "For the next meeting").
   Base it on `screens/meetings-and-minutes.md` (Decisions rows), `screens/hearing-process.md` (rows on the decision store), `screens/controls.md` ("Adopt, decline, defer, retire"), `screens/elections.md` ("acclaimed" rule), `screens/law-review.md` (the record-a-decision act), `../controls.md` section 7, `src/jason/tasks/decisions.py`, the `decisions` loader in `sources.py`, and `ui/src/views/DecisionsView.tsx`.

3. **Hearing and law-review brief.** Write `design-brief-hearing-and-law-review.md` in the house brief shape (A idea and rules, B reading order, C screens, D components once, E glyphs, F decisions that are the design's, G now versus waits, H a made-up community). It must draw the hearing run page and the built `HearingsView`'s missing steps (notice, cure record, request for executive session, the penalty-schedule check against the day of the violation, the decision notice preview), the law-review lead list with the statute recited before the reading, and the three acts. It must mark the suspension-notice section (Corporations Code 7341) as not on the shelf (the CORP folder holds 7151, 7210 to 7215, 7230 to 7238, 8310 to 8340, verified). Base it on `screens/hearing-process.md`, `screens/law-review.md`, and `design-brief-money-reviews.md` as the template.

4. **The owner's side** (row O1). Write `screens/owner-view.md`. For each subject below, give the owner loader's name, its fields, what it hides, the words, and the statute it serves:
   - an adopted rule, and a proposed rule change with its comment window (CIV 4360; the `rule-records` and `rule-changes` loaders are P0 and board only);
   - an election: notice, candidates, results (CIV 5100 to 5145 are on the shelf);
   - the annual packet's contents after its sent day (decision 7 of `handoff-annual-disclosures.md`);
   - a member's own hearing notice, as delivered to them (`screens/hearing-process.md`, "The owner view has no hearings loader");
   - a member's own request (PayHOA is the portal; say what the console adds, if anything).
   Add an explicit "never here" list: Work, Controls, Mailroom, Notices, delinquency, liens, hearings of others. State the `OWNER_SOURCES` additions and the `ui/src/ownerScreens.json` rows. Base it on the module docstring of `src/jason/web/extra/owner_view.py`, `ui/src/ownerScreens.json`, `screens/elections.md`, `handoff-rule-records.md` decision 7, `docs/console/README.md` "Out of scope", and `design-brief-annual-disclosures.md`.

5. **County tax cycle** (row M3). Write `screens/county-tax.md`. It must contain:
   - the parcel table (standing, unpaid or delinquent, bill PDF, last receipt) over a `tax-status` loader that reads `jason.tasks.tax_receipts` and the MCP `tax_status`;
   - the run's steps from [../workflows/money.md](../workflows/money.md) section 2 (`county-tax-cycle`: due, pay, close), with `Basis` for each;
   - **no recited clock.** The RTC folder on the shelf holds only 2191.3 to 2191.6 and 3691 (verified), so an installment date reads "the bill's date" with basis `documents`, and "Revenue and Taxation Code: not on the shelf" in a `Recitation` empty state. The spec lists the sections to add first (`jason cite`) and says the clocks are written after they are;
   - the chain from the county bill source to a PayHOA payment and its receipt (link, do not redraw, `design-brief-mail-and-payments.md`);
   - the one-line taxes band per unit on `screens/members-and-units.md`.
   Base it on `money.md` sections 2 and 8, `handoff-mail-and-payment-attachments.md` (the payee class), `docs/adapters.md` (the receipts adapter), and `jason county-tax` in `docs/cli.md`.

6. **Rules and governing documents brief.** Write `design-brief-rules-and-documents.md`. It must cover `#/documents` (governing documents with recorded and Drive copies), the rule records (the adopted rule, its versions, the working Doc against the adopted words, its uses and acts), proposals on `#/rules/change/<key>` with the CIV 4360 timeline, and the owners' manual. Say which parts draw from built loaders (`governing-documents`, `rule-records`, `rule-record`, `rule-record-history`, `rule-record-compare`, `rule-uses`, `rule-events`, `rule-changes`) and which wait on the proposal store. Base it on `handoff-rule-records.md`, `handoff-rules-and-authority.md`, `handoff-documents-studio.md`, `screens/governing-documents.md`, and the built `RuleChangeView`.

7. **Careful-reading and records brief** (D1 to D3, M0). Write `design-brief-reading-and-records.md`. It must cover the intake review, the confirmations queue (`record-readings` is built), the context-pack workbench, the collection workspace, the law-as-of-a-day and quote check, document kinds (`library-kinds` is built), the ingest report, the recorder reading by number, and the records request's fee cap and held clock. Say which are built and which wait. Base it on the six handoffs in row D3, `screens/document-kinds.md`, `screens/records-and-library.md`, and `screens/requests.md`.

8. **Programs brief.** Write `design-brief-programs.md`: the programs register, maintenance programs, the pest program (no web loader yet), and elevated elements per building (P5, P6), with the backflow card confirmed against `design-brief-life-safety.md`. Base it on `handoff-programs.md`, `handoff-applicability-questions.md`, `handoff-inspections-and-portals.md`, and [../workflows/property-safety-vendors.md](../workflows/property-safety-vendors.md) section 5.

**Outside the top eight, in priority order:**
- the routes pass on [information-architecture.md](information-architecture.md) (E3);
- `MaskedField` as a spec of its own (server shape, reveal log, which screens use it first: Mailroom recipients, then Members);
- the dock's run clock (the dock loader has none);
- members and units, after masking;
- the machine band;
- the response standard, after the board adopts one.

**Build, not design:** register the remaining definitions (about fifty), the Mailroom loader, `member-requests`, `monthly-review`, `meeting-watch`, `record-stages`, `schedule`, `conflict-leads`, the elections, incidents, and collect stores, the banner helper (item 1), and a view for each of the 30 loaders in "Read this first" 4.

## 3. Stale statements to correct

Not edited here (this page is the only file this audit changes). The owner of each file should correct:
- [../workflows/README.md](../workflows/README.md): line 3 ("none of the engine below is built yet") and line 16 ("no definition is registered, there is no `jason workflow` command, no `work` or `work-run` loader, and no view").
- [design-brief-work.md](design-brief-work.md): line 3 ("None of the engine is built"); sections that say the loaders are "to add".
- [screens/work.md](screens/work.md): line 11 (the `work` and `work-run` loaders "to add", the run store "not built") and the same in the [screens/README.md](screens/README.md) row for `work.md`.
- [screens/controls.md](screens/controls.md): lines 3 and 9 ("the screen is not" built; loaders "not built").
- [design-brief-controls.md](design-brief-controls.md): the "Checked against the code" paragraph ("Not built, no view: `Control` ... the loaders").
- [design-brief-board-records.md](design-brief-board-records.md): "no `work` ... route" in its "Checked against the code" paragraph.
- [design-brief-requests-and-onboarding.md](design-brief-requests-and-onboarding.md): the "Work runs" row of section G ("no `work`, `work-run` loaders").
- [screens/requests.md](screens/requests.md): its roles line, which the requests brief says predates 2026-10-11.
- [screens/office-views.md](screens/office-views.md) and [screens/today.md](screens/today.md): the "Your work" band says `GET /api/work?mine=1 (to add)`; the loader exists and the office lens reads the `office-view` loader instead.

## 4. Not verified

- How fully each of the eleven briefs draws the surfaces its reading list points to. Only the heads, the section C tables, and the section G tables of `design-brief-money-reviews`, `design-brief-controls`, `design-brief-requests-and-onboarding`, `design-brief-notices-and-mailroom`, `design-brief-board-records`, `design-brief-life-safety`, `design-brief-work`, and `design-brief-platform` were read; `design-brief-annual-disclosures`, `design-brief-governance-calendar`, and `design-brief-property-and-units` were checked by grep for the run-link sentences and the surfaces named in the table.
- The relation between `src/jason/console/ui` and `ui/src/components`.
- Whether `handoff-title-processes.md` specifies a recorder reading by number (grep found no match for the tool names).
- How `jason.workflows.api.start` forms a run id (whether a parcel or unit could appear in it).
- Whether `ApprovalsView` or `DecisionsView` reads the hash in any way (grep found none; neither was run).
- Whether `PlanReview` shows the Mailroom preview's fingerprint, pages, and cost for the `payhoa-mailroom-send` kind.
- Whether the platform brief draws the machine band.
- Whether the `Dock` shows any run clock (`dock.py` reads none; the dock was not run).
- Whether `rule-changes` and the `rule-records` family, which `gates.py` leaves at P0, should be readable by any signed-in roster person (`SEE_RULES`' offices are the P2 set); the gate fixture records them as P0 with a reason, and no spec disputes it.
