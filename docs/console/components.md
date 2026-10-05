# Components

The console draws every screen from **jason-ui** (`ui/src/components`, exported from `index.ts`). The same components are the design system: the library build exposes them as `window.JasonUI` to the claude.ai design project, with one authored preview each in `.design-sync/previews/` ([conventions](../../.design-sync/conventions.md), [notes](../../.design-sync/NOTES.md)). [web-ui.md](../web-ui.md#components-uisrccomponents) lists them as built.

This page maps what the console needs onto them. Where the earlier spec named a component of the static prototype library (`src/jason/console/ui/`, the `jc-` names), the table gives the jason-ui component that does the job. Components marked **being added** are being written now for the engine's approvals screen; the names are that work's to settle, and this page follows them.

**Conventions** (jason-ui's, from the conventions header):
- **Tokens, not hues.** `--bg`, `--panel`, `--ink`, `--muted`, `--line`, `--accent`, `--good`, `--warn`, `--bad`, with a dark variant under `prefers-color-scheme`, and the brand tokens the profile's theme adds (`--brand-font`, `--hero`, ...). The prototype's `held` role has no jason-ui token yet; `HeldNote` should add one (`--held`) rather than borrow `--warn`, since held is not late.
- **A small class vocabulary**, global in `styles.css`: `.stack`, `.row`, `.wrap`, `.grid-2`, `.muted`, `.num`, `.chip`, `.notice`, `.notice-warn`, `.notice-error`. Components carry no CSS imports.
- **Every state is a word.** `Pill` takes the word and its meaning; a color only repeats it.
- **Writes go through `Confirm`** (two clicks, the change spelled out) or `ConfirmList` (a name on each tick). Nothing writes on a single click.
- **Samples are plainly fake:** "Example Village HOA", "Owner A", "Jane Example", "123 Main St".

## Layout and frame

| The console needs | jason-ui | Notes |
|---|---|---|
| The frame: wordmark, legal name, sign-in pick, dock, Board / Owner view, grouped nav, a "Go to" select under 720 px | `ConsoleShell` | Replaces the prototype's `app-shell` and `nav`. Nav counts come from the screen list (`count`); the approvals count is the letters waiting on the signed-in person's approval (the dock's counts), or the inbox's pending count with nobody signed in. **Roles (October 4, 2026):** `role` (`officer`, `manager`, `administrator`, `owner`; the server derives it from the person's offices as `GET /api/session`'s `roleClass`, `jason.web.signin.role_class`) filters a screen that declares `roles` (the manager does not see Decisions); `moves` is the role strip above the role's landing screen (`landingScreen`, `DEFAULT_LANDING`: officer to the digest, manager to the duties, administrator to Approvals), built from the dock's counts (`lib/roles.ts`); a nav item, a dock pill, and `ScreenHeader` take a `glyph` |
| The page header | `ScreenHeader` (`title`, `summary`, `actions`) | Replaces `page-header`. One `h1` per screen |
| A titled section | `Card` (`title`, `actions`) | Replaces `section-card`. Its freshness line and command go inside it (below) |
| Bands of one screen | `Tabs` (controlled) | |
| A plain frame without the console | `AppShell` | Older views; new screens use `ConsoleShell` |
| The dock | `DockToolbar`, `Drawer`, `DockDrawerBody`, and the drawers `DeadlineList`, `ActionRegister`, `Scratchpad`, `AskPanel` | Built. Deadlines, tasks, notes, and Ask, floating or pinned at 1200 px |

## Status and time

| The console needs | jason-ui | Notes |
|---|---|---|
| A status or standing word | `Pill` (`word`, `meaning`) | Replaces `status-badge`. Approval statuses, item results, and clock standings are words from the code (`ApprovalStatus`, `Result`, `meeting_watch.Standing`) |
| A category or a count | `Badge` | |
| A deadline: time left or past, with the date | `DueDate` (`iso`, `today`) | Replaces `deadline-badge`. A statute's clock is marked by its citation beside it, not by a color of its own |
| A statutory clock as stages | `Clock` (stages with `who`, `note`, `evidence`, `decision`) | Replaces `clock-row`. Used for 4360, 5210, 5515, 5855 |
| Onboarding's stage gates in order | `StageSteps` (**being added**) | Replaces `stage-stepper`: each stage with its gate in words ("Gate open", or what it waits on), the stage being worked marked `aria-current="step"`. A gate is jason's reading; the board decides what is done |
| Dated events | `Timeline` | |
| Required contents, ready or missing | `Checklist`; `ConfirmList` when a person must tick | |
| Who did it | the name in text, from the record | The prototype's `person-chip` is not carried over. `DraftLetter`'s log and `AuditLog` name each person; jason is named "jason" and never as a signer |

## Approval

The letters' approvals are built (`DraftLetter`, `ApprovalsInbox`). The engine's plan review is **being added**.

| The console needs | jason-ui | Notes |
|---|---|---|
| The inbox: everything waiting on a person, by stage | `ApprovalsInbox`; `PlanApprovals` (a view, **being added**) beside it | Built for letters. The engine's plans are listed beside them on the same screen ([approval-workflow.md](approval-workflow.md#11-letters-and-plans-one-inbox)) |
| A drafted letter through its stages | `DraftLetter` | Built: draft, saved, awaiting approval, approved, sent; each step a `Confirm` in a person's name; the approved stage shows a `Command`, never a send button. A board approval names the meeting |
| One engine approval, whole | `PlanReview` (**being added**), listed by the `PlanApprovals` view inside `ApprovalsView` | Header (kind, status, requested by, read time, fingerprint's first 12 hex, clock, reversibility), the approvable items grouped by target, then the sections that are never approvable, the cost, the decisions, and the audit |
| One plan item | `WriteRow` (**being added**) | Replaces `write-row`: the change as before → after with its sign in words, why, the rule (opening its `Recitation`), the evidence, and the decision. A held, for-a-person, or confirm-with-owner item has no control at all |
| What an item rests on | `Evidence` | Takes strings today. The engine's evidence is `{label, address}`; `WriteRow` renders the label with the address as the chip, or `Evidence` grows an object form |
| Held for the board | `HeldNote` (**being added**) | Replaces `held-banner`: how many, why, the board item, and that approving the rest never approves a held item. It says the item goes to the board's agenda, never that someone may approve it here |
| Changed since review | `ChangedBanner` (**being added**) | Superseded, changed since review (a `check` that differs, or an apply refused), or read longer ago than the kind allows: what changed, the new approval, and the terminal command to plan again. A change blocks `ApproveBar`; a plan that is only old keeps its decisions, since apply re-plans first |
| Deciding and signing | `ApproveBar` (**being added**) | Replaces `approve-bar`: decide the selected items (approve, or reject and hold with a reason), then sign with the tally, the cost, and the name (pre-filled from "Signed in as", never "jason"): "Approve 5 of 8 changes as Jane Example". Each write goes through `Confirm` |
| The second person | `SecondConfirm` (**being added**) | Replaces `confirm-panel`: the rule in words, who signed first, a name field that starts empty, refused for the same name |
| A two-click write | `Confirm` | Built. Every write outside the engine uses it |
| What it costs | `CostLine` (**being added**), with `Money` | Replaces `cost-summary`: integer cents as dollars, "estimated", who is charged, the price source. "No cost" is stated, never blank |
| What an apply did | `ApplyResult` (**being added**) | Replaces `result-panel`: applied, failed, uncertain, blocked, not applied, and changed, each listed; failures open. With apply off, it shows the `Command` to run instead |
| A command to run | `Command` | Built: copies, never runs. Replaces `cli-hint` |
| The audit | `AuditLog` (**being added**) | Replaces `audit-timeline`: an approval's events in order, with "chain verified" or "chain broken at line N" from `audit.verify` |

## Text and data

| The console needs | jason-ui | Notes |
|---|---|---|
| A rule's words, recited whole | `Recitation` (**being added**) | The words, the citation, the version in force, the caveat. A reading never goes inside it |
| A reading, labeled with whose | `ReadingLabel` (**being added**) | jason's, the board's (with its adoption date), or counsel's; "two readings remain" when open |
| Findings a person reads | `Findings` | |
| A tool's caveats, always visible | `Caveats` | Rendered verbatim, never behind a toggle |
| Dense rows | `DataTable` (sort, filter, row selection, `date` column kind) | Replaces `data-table` and the prototype's `filters-bar`; `SearchBox` for a search field |
| A register with the board's columns | `RegisterGrid` | |
| Money | `Money` (integer cents) | |
| A figure | `Stat` | |
| Markdown, with Mermaid | `Markdown` | |
| A Doc, Sheet, PDF, or photo | `Embed` | |
| A ranked question with its answer form | `QuestionCard` (**being added**) | Replaces `queue-item`: what it unblocks, the question, jason's suggestion labeled as jason's, the evidence, the answer with "by", and the second-person state for a high-stakes answer |
| Choosing the association from the county's directory | `AssociationPicker` (`counties`, `defaultCounty`, `onPick`, `onClear`, `picked`, `limit`, `debounceMs`) | A county and a search box that is a WAI-ARIA combobox over a listbox (`GET /api/associations`): each row's name, kind and standing badges, the years it recorded, and its evidence in words ("386 assessment liens · 15 declaration filings"); the chosen row's spellings behind a disclosure. Choosing only emits `{key, name, county, row}`; it writes nothing. A county with no directory shows the `Command` that builds it. "A directory row is a lead, not a pin." ([screens/onboarding.md](screens/onboarding.md#finding-the-association-and-its-documents)) |
| An association's recorded documents, located | `DocumentLocator` (`county`, `name`, `me`, `pollMs`, `questionHref`); its parts `LocatedDocuments` (`location`, `questionHref`, `actions`), `BoardList` (`location`), `TieBadge` (`doc`) | `GET /api/documents-located`: grouped by checklist item, each with the board's question, "a second person confirms" on the declaration and amendments, and a table of number, date, filing, the tie as a word badge (a strong tie, or "the builder's filing", which "may be another community's"), how it was found, and business parties only; then not located with each ask, the notes, and the caveats. Missing shows the note, the command, and "Locate documents", which queues a read job as a named person behind `Confirm` (`POST /api/write/documents-located/locate`), then reads again every few seconds while the job is queued or running. Writes off (405) shows the command. The board's list is the same data as a printable checklist (hold a copy, order a copy) that records no mark. The answers go through the onboarding questions, never a second form |
| The key documents and their copies | `KeyDocuments` (`data`, `by`, `onChanged`, `post`) | `GET /api/key-documents`: each expected document (declaration, amendments, annexations, bylaws, condominium plans, maps, common-area deeds, …) with its recording number, a status word (expected, located, held, linked, missing), the copies held and the links a person made, and the locator's suggestion labeled a lead, not a pin. Link, upload, unlink, and status each go through a `Confirm` naming the person (`POST /api/write/key-documents/<key>`); unlink never deletes a file. A refusal shows as an alert saying nothing was written ([key-documents.md](../key-documents.md)) |
| The recorded instruments as a graph | `InstrumentGraph` (`data`, `initial`) | `GET /api/instrument-graph`: an SVG timeline (parcels, a column per recording year, parties) with a keyboard-usable node list beside it; an edge's provenance (the rule, the store, lead or firm) shows on focus in a status region; family filters; the cycles left out; the Mermaid diagram on request. The shared view never shows a private person ([instrument-graph.md](../instrument-graph.md)) |
| Loading, error, empty, and the tool's own `found: false` | `RemoteView`, `Loading`, `ErrorNotice`, `EmptyState` | Replaces `states`. "Unavailable" is the tool's note with its command; never an empty table |
| A view that throws on a shape it did not expect | `ViewBoundary` (in `RemoteView`) | Shows the raw result, so a person still sees what the tool returned |
| A result message | inline `.notice` with `role="status"` or `role="alert"` | The prototype's `toast` is not carried over: results stay where the action was taken ([patterns.md](content/patterns.md#notifications)) |

## Meetings and decisions

Built from the design handoff; listed here so the screen specs can name them.

| Component | Job |
|---|---|
| `DecisionBrief` | The question, the criteria, lettered options, and the facts. Never a recommendation (`BRIEF_FOOTER`) |
| `DecisionCard` | The board's decision on one item: motion, mover and second, the roll call, the outcome in the board's word |
| `RollCall` | Each director's vote by name, with `present`, `recused`, `threshold`, and the rules on file (`interested`, `quorum`, `basis`). A recused row reads "recused", never "absent". With the recusal rule not on file, the tally is worked both ways and a vote the readings decide differently is "held" ("not on file; ask counsel") |
| `AgendaWizard`, `ReadinessRow`, `DriveAttach` | Planning a meeting: items, order, motions, packet, notice. jason reports computed checks only |
| `MeetingStage`, `HostPanel` | The meeting room: the stage, attendance, motions, votes, the CIV 4930 guard, executive session as the host's act. `HostPanel sheet` (`true`, or `"auto"` under 720px) is a bottom sheet: a grab handle, the tab row always shown, the body scrolling; collapsed, the body is hidden but kept mounted, and a tab tap opens it. `open` and `onOpenChange` control it; without `open` it starts collapsed |
| `BoardFields` | The board's columns on a board item, old → new behind a confirm |
| `RequestForm` | An owner's records request, with the 5210 clock it starts |

## Marks: glyphs, stamps, seals, routing tags

Ported from the design handoff's glyph sheet ([handoff-reconciliation.md](handoff-reconciliation.md#the-visual-system), items 26–27). glyph-layer.js is not shipped: a screen puts a mark where it means one. The vocabularies are `ui/src/lib/marks.ts`; the glyph data is generated into `ui/src/lib/glyphData.ts` (Lucide 1.51.0 subset, ISC, and jason's own).

| Component | Props | Job |
|---|---|---|
| `Glyph` | `name` (a `GlyphName`), `size` (CSS length or px; 16 inline, 20 nav, 24 headers, 32 empty states), `label`, `stroke` | One meaning per glyph (`GLYPH_META`), beside its word. Decorative (`aria-hidden`) unless `label` names a glyph that stands alone. An unknown name renders nothing and logs once |
| `Stamp` | `word`, `by`, `date`, `sentRef`, `size`, `tilt` (0 in a table) | What a **person** decided, in its own word: carried, failed, approved, denied, adopted, tabled, continued, referred, withdrawn, sent (`STAMP_WORDS`). `sent` renders only with `sentRef`, the record of the sending, never from a click. A word outside the set keeps its word in the neutral tone; a seal's word, `draft`, `confidential`, and `recorded` render nothing |
| `Seal` | `word`, `detail`, `instrument`, `date`, `size`, `tone="ink"`, `inline` | What **jason** did, and whether a person still has to act (open, done, unresolved, not jason's): proposes, suggests, needs approval, waiting on, read, drafted, reminded, filed, not confirmed, not sure, ask a person, will not send (`SEAL_WORDS`). A county filing is `read` with its `instrument` number, never "recorded". `filed` is a seal |
| `RoutingTag`, `RoutingTags` | `owner` / `owners`: `{role, name?, adoption?}` as the server resolved it (a dock deadline's `owners` row, an `Officer`) | Whose desk a thing is on, by the office's role value; "unassigned" when nothing resolved. Never read out of a thing's words. An assignment not adopted reads "(proposed)" |

Stamps and seals never share a word, a key or a word of a label (`marks.test.tsx`). Draft is the *drafted* seal; confidential is the P3 chip, a level and not a decision.

## Still proposed

Not in jason-ui and not being added now. Each waits on a decision in [mvp.md](mvp.md#open-decisions) or on its screen.

| Component | Job | Waits on |
|---|---|---|
| `MaskedField` | A contact value masked by the server, with a logged reveal of one field | The data levels and roles ([security-and-privacy.md](security-and-privacy.md#data-levels)) |
| `PrivateSwitch` | Opening restricted material for a stated reason, logged | The same |
| `Freshness` | When a section's store was last synced, and the command that refreshes it | Each loader returning its sync time. `ConsoleShell`'s `recordsAsOf` covers the page; a section line is the gap |
| `JobStatus` | A plan or sync running as a job, its log tail, and its result | Whether engine plans run in the request or as jobs ([architecture.md](architecture.md#locking)) |
| `CiteBox` | Any expression `jason cite` takes, answered as a `Recitation` | The governing-documents reader ([screens/governing-documents.md](screens/governing-documents.md)) |
| `DiffTable` | Before and after for a text: a section's versions, a notice's text against what was kept | The same, and the notices screen |
| `AnswerWord` (a `Pill` preset), `VerdictRow`, `SourcedFact`, `StandingFacts`, `FactQuestionRow` (a `QuestionCard` preset), `EventFactsPicker`, `CatalogGroups`, `BuildingInspectionRow`, `DueUnder` | What applies: the three-valued answer with its deciding or missing fact, the question a person answers, the event facts, and the per-building 5551 record | [handoff-applicability-questions.md](handoff-applicability-questions.md): the `#/applies` decisions |
| `ConfirmationsQueue`, `QueueCounts`, `CandidateReading`, `ProvisionRecital`, `StandingChoice`, `AdoptionState`, `StaleWordsBanner`, `GoldLabelRow`, `GoldProgress`, `DecisionRow`, `WhoDecides`, `JasonAside` | The confirmations queue: a person's signed confirmation of a reading, a gold label, or a decision, adopting nothing | [handoff-confirmations-queue.md](handoff-confirmations-queue.md): the `#/confirmations` decisions |
| `IndexLine`, `IndexSearchBar`, `SliceControls`, `SearchScopeLine`, `PassageStanding` (a `Pill` preset), `HitCard`, `PackBuilder`, `PackView`, `PackSource`, `HeldBack`, `PackGaps`, `PackBudget`, `ModelGate`, `ReviewRun`, `ReviewAnswer`, `QuotationCheck`, `KeptReviews`, `PackCompare` | The context-pack workbench | [handoff-context-pack-workbench.md](handoff-context-pack-workbench.md): its decisions |
| `CollectionList`, `WorkspaceHeader`, `CollectionStateBanner`, `SummaryBand` (a `Card` preset), `MatterRecord`, `GapLine`, `FileInventory`, `ReadState` (a `Pill` preset), `ChronologyLanes`, `StatementRow`, `FactConflictCard`, `CitationRow`, `FormerAndNow`, `ReviewList`, `ReviewRecord`, `FindingRow`, `LensCompare`, `OpenQuestionRow`, `RaiseQuestion` and `ExtractTextAction` (`Confirm` presets) | The collection workspace | [handoff-collection-workspace.md](handoff-collection-workspace.md): its decisions |
| `AsOfControl`, `AsOfBanner`, `VersionLine`, `NotShownNotice`, `VersionTimeline`, `SubdivisionWords`, `TermOnDay`, `FormerSectionRow`, `QuoteCheck`, `QuoteMark`, `QuoteVerdictRow`, `QuoteDiff` (a `DiffTable` preset), `CitationCheckRow`, `GiveGate` | The law as of a day, and the quote check | [handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md): its decisions |
| `MachineProblems`, `DriveRoom`, `PlaceRow`, `TempLine`, `ConfigFiles`, `SettingChain`, `SettingChange`, `LeftBehind`, `LockTable`, `ModelStack`, `PreflightLine`, `CommitHeadroom`, `IndexHealth` | The machine jason runs on | [handoff-storage-and-settings.md](handoff-storage-and-settings.md): its decisions |

## Accessibility

The console meets WCAG 2.2 AA ([W3C](https://www.w3.org/TR/WCAG22/)). jason-ui is a React app: there is no no-script baseline, so each component carries these duties itself.

- **Keyboard (2.1.1, 2.4.3, 2.4.7).** Every action is a native `button`, `a`, or form field, in DOM order. No `tabindex` above 0. The focus ring is visible on every focusable element, and table regions that scroll are focusable and labeled.
- **Focus not obscured (2.4.11).** `ApproveBar` is sticky; the page reserves its height (`scroll-padding-bottom`) so a focused row is never under it.
- **Target size (2.5.8).** Row checkboxes and decision buttons are at least 24 by 24 CSS pixels, or spaced to pass.
- **Dragging (2.5.7).** Nothing needs a drag. `Kanban` lays out cards without moving them, and `AgendaWizard` orders items with buttons. A new component keeps it that way.
- **Contrast (1.4.3, 1.4.11).** Text 4.5:1 and component edges 3:1 against `--bg` and `--panel`, in both schemes and under a profile's brand tokens. The prototype measured its pairs ([its README](../../src/jason/console/ui/README.md)); jason-ui's tokens need the same table.
- **Use of color (1.4.1).** Every state is a word first.
- **Reflow (1.4.10).** At 320 CSS px the page does not scroll sideways; `ConsoleShell` turns the nav into a select under 720 px, and wide tables scroll inside their own region.
- **Status messages (4.1.3).** The approve bar's count, an apply's progress, and a result use `role="status"`; a refusal that stops the work uses `role="alert"`.
- **Labels and errors (1.3.1, 3.3.1 to 3.3.3).** Every control has a visible label. An error names the field and how to fix it: "That is the name that approved it. A second person confirms."
- **Redundant entry (3.3.7).** The approver's name comes from "Signed in as". Only the second person's field starts empty, under the criterion's security exception.
- **Timing (2.2.1).** Nothing times out. Decisions save as they are made (`in_review`), so a person can leave and come back.
- **Consistent help (3.2.6).** Each screen's command (`Command`) sits in the same place under its header.
