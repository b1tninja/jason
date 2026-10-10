# Design sync notes

Repo-specific gotchas for syncing `ui/src/components` to Claude Design. Read before a re-sync.

- **The package is an app, not a library.** `ui/` is a Vite app; the design-system entry is a separate
  library build: `cd ui && npm run build:lib` (`vite.lib.config.ts` + `tsconfig.lib.json`) writes
  `ui/dist-lib/index.js` and the `.d.ts` tree under `ui/dist-lib/components/`. Run it before the converter;
  `--entry ./ui/dist-lib/index.js --node-modules ./ui/node_modules`, from the repo root.
- **Component CSS is global.** The components carry no CSS imports (a per-component `.css` import makes the library
  build emit a separate `style.css` the converter never ships, so designs lose those rules; `Embed`'s link-card rules
  were folded into `styles.css` for that reason); everything is `ui/src/styles.css`
  (`cfg.cssEntry`). Tokens are the `:root` custom properties in that file (`--bg`, `--panel`, `--paper`, `--ink`,
  `--muted`, `--line`, `--rule`, `--accent`, `--good`, `--warn`, `--bad`, `--r`, `--serif`, `--label`), with a dark
  variant under `prefers-color-scheme`. Fonts: `system-ui`, and Newsreader (`--serif`) through a Google Fonts `@import`
  at the top of `styles.css`, so the build reports `[FONT_REMOTE]` (informational) and nothing ships in `fonts/`;
  Georgia stands in where the font cannot load. Self-hosting it is the console's open decision 9 (docs/console/mvp.md).
- **The clerk's desk (2026-10-03).** The redesign (the project's `templates/redesign/`, REDESIGN-SPEC.md) is folded into
  `styles.css` as its last section, each `[data-skin="clerk"] X` rule written `:root X` for the same specificity, so
  no attribute is needed. Its bare `button` rule outranks component rules that strip a button's box at one class
  (`th button`, `.tabs button`, `.wizard-steps button`, `.seg button`); the section restores those explicitly, and the
  design project's own `clerk.css` still has that defect. Confirm renders its hanging label as `.confirm-label`
  (prop `label`), not `::before`.
- **Four exports share a source file.** `Loading`, `ErrorNotice`, `EmptyState` live in `States.tsx` and
  `RemoteView` in `Remote.tsx`; `cfg.componentSrcMap` pins them, otherwise they are "not src-matched".
- **Playwright.** The container's cached Chromium is build 1194 at `/opt/pw-browsers`, pinned by
  `playwright-core@1.56.1` (`/opt/node-tools`). Install that exact `playwright` version into `.ds-sync/` and run
  validate/capture with `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`. A newer playwright fails with
  "Executable doesn't exist". On the Windows checkout the cache is `%LOCALAPPDATA%\ms-playwright` (chromium-1243
  on 2026-10-03), which `playwright@1.63.0` pins; no `PLAYWRIGHT_BROWSERS_PATH` is needed there. Check the cache's
  `chromium-<build>` against `.ds-sync/node_modules/playwright-core/browsers.json` before a run.
- **Previews import from `jason-ui`.** Named exports, one per cell. `Badge` takes a single string child
  (template literal, not an array). `DueDate` takes `today` so a preview is deterministic; without it the
  distance drifts daily and the floor card rendered blank.
- **Controlled inputs need a wrapper.** `SearchBox` and `Tabs` take `value`/`active` + `onChange`; a cell wraps
  them in a small function component with `useState`, else they read as broken.
- **`Findings` with `ok={false}` and no items renders nothing** by design; never use that as a cell. `Caveats`
  returns null for an empty list, same rule.
- **Wide components.** `.kanban` is `grid-auto-columns: minmax(260px, 1fr)`, so five lanes need ~1350px: Kanban
  has `cardMode: column` and a `1400x700` viewport in `cfg.overrides`; AppShell, DecisionCard, RegisterGrid, and
  RollCall are column mode (their tables and two-column `.fields` grids overflow a grid cell). `.stats` is
  `minmax(150px, 1fr)` and clips six-figure money at ~500px; the Stat and Card previews widen the columns with
  inline grid glue (`.stat` itself has no overflow handling, a component note).
- **`Confirm`'s armed state is internal** and cannot render statically; its preview shows the idle button and a
  lookalike of the armed markup. `busy` only sets `disabled`, which `styles.css` does not style.
- **`RemoteView`** renders its `children` function through an inner component, so a throw while computing the
  JSX lands in `ViewBoundary`. A caught throw still appears in the review json's `pageErrs` (React logs it); the
  cell renders, so it is not a capture error.

- **Mermaid is not bundled.** `Markdown` loads it at render time from a CDN (`setMermaidUrl` overrides); bundling
  it put 5 MB into the library build and would have gone into every design. A diagram cell cannot be verified
  where the capture has no network, so the Markdown preview carries none.
- **This container has no outbound network** (the proxy refuses the CDN) and the headless Chromium shell has
  no PDF viewer: a Google preview frame, a Mermaid diagram, or a PDF cannot be verified in a capture here. The
  Embed and Markdown previews use blob URLs (an SVG photo, an HTML page) that render offline instead.
- **`data:` and `blob:` refs.** `embedUrls` passes them through (anything else is a path under data/), and
  `Markdown` allows them as image sources (DOMPurify's default strips both); the preview images rely on it.

## The console components (design handoff 2026-10-03)

- **Twenty components fetch nothing or post only on `Confirm`** (DraftLetter, ApprovalsInbox, Checklist, BoardFields,
  RequestForm, ScreenHeader, ConsoleShell, DecisionBrief, AgendaWizard, ReadinessRow, DriveAttach, MeetingStage,
  HostPanel, DockToolbar, Drawer); their previews are plain props. Who may approve in `DraftLetter`/`ApprovalsInbox`
  comes from `me` + `people` (`{name, role, approves[], canApproveBoard}`), so stage x signed-in person is the axis.
- **The dock bodies fetch `/api/dock?part=<deadlines|tasks|notes|ask>`** (DeadlineList, ActionRegister, Scratchpad,
  AskPanel, DockDrawerBody). Their previews install a module-scope `fetch` stub with the loader's shapes from
  `src/jason/web/extra/dock.py` and `today: "2026-10-03"`; a `WithFixture` wrapper sets a module-level variant the
  stub reads, so one URL serves an empty and a full cell. `found: false` renders only the loader's note.
- **Internal state is driven by a post-mount click** where no prop exists: `AgendaWizard` steps (`.wizard-steps
  button`) and `HostPanel` tabs (`[role="tab"]`). States behind typed input (a changed BoardFields, a ready
  RequestForm, Scratchpad's editor, AskPanel's Translate tab) are not cells; the UI tests cover them.
- **Sizing.** `MeetingStage` sizes by `cqw`, so each cell wraps it in a 720px div. The floating `Drawer` is
  `position: fixed` and needs a sized `transform: translateZ(0)` stand-in page or it collapses. `ConsoleShell`
  (1400x900), `AgendaWizard` (1000x1400), and `HostPanel` are column cards (`cfg.overrides`); steps 3 and 4 of the
  wizard are taller than a 700px capture, hence the tall viewport.
- **Drift to watch.** `ApprovalsInbox`'s "Sent this month" uses `new Date()` with no `today` prop, so the preview's
  October `sentOn` dates read 0 after October 2026. `AskPanel`'s "Your name" input sits outside `.dock-panel` and is
  browser-styled in the real drawer; the preview frame adds the class.
- **Fixed during this sync.** The stage's options view kept the page's `--panel` behind the brief's cards (invisible
  values on the dark stage) and `.screen-head` was defined twice; both are `styles.css` fixes, not preview ones.

## Onboarding and evidence components (re-sync 2026-10-03, evening)

- **Fetch stubs answer by URL or request body, never a module variant.** Every cell in a card mounts at once, so a
  `WithFixture` variable holds only the last cell's value. `AssociationPicker` cells each open a different county
  (`?county=`), `DocumentLocator` cells a different association (`?name=`); `EvidencePanel` routes
  `GET /api/evidence?address=` by address and `RefreshAllEvidence` routes `POST /api/evidence/refresh-all` by the body's
  `approval`. A never-settling promise holds a loading or busy state. Stubs that POST also answer `/api/session` with
  `{}` (`postJson` reads the write token from the session when the page has no `jason-token` meta).
- **Post-click states** (the read-again result, the batch statuses, `OwnerNames` asking for a name) click once after
  mount, as HostPanel does; the clicked button keeps its focus ring in the capture, which is the real behavior.
- **The finder's styles live in `styles.css`.** `views/discovery.css` was folded in (its own section) because a view's
  CSS never ships: without it the picker's options ran together ("15 declaration filings2 spellings").
- **`.notice-error` is a flex row** (for ErrorNotice's message and button). A paragraph that is a notice-error spaces
  its inline words apart; `DocumentLocator`'s job line adds `.locator-job` to make it a block.
- **`.evidence-reread-all-status .notice` is inline-block**: an inline notice that wraps split into overlapping boxes.
- `EvidenceVersion` is a React context, not a component: `componentSrcMap` excludes it. `OwnerNames` is exported for
  the design library (the reveal control above the graph).
- Tall cards: `KeyDocuments` (1000x2000), `DocumentLocator` and `LocatedDocuments` (1000x1400), `BoardList` (1000x1100),
  `InstrumentGraph` (1200x1000); the graph's timeline scrolls sideways inside its box by design.

## Re-sync 2026-10-04 (afternoon): guidelines only

- All 89 components were verified by the project's anchor (0 changed, 0 new); the upload carried the README and
  `guidelines/` only (writes are always the full set, so every file was re-sent). The marks below were already in the
  project, so the note's "not yet synced" was stale.
- `guidelinesGlob` is an explicit list, so a handoff page reaches the design agent only when it is listed: added
  `handoff-unit-records`, `paint-ui-design`, `paint-design`, `unit-records-design`, and the paint, community-facts, and
  unit-record screen specs (2026-10-04). Guidelines are flattened by file name (`screens/paint.md` becomes `guidelines/paint.md`),
  so avoid two docs with the same base name.
- The project's `templates/design_handoff_community_console/` copy was gone from the final listing; the sync never
  deletes under `templates/`, so the design agent or the app removed it.
- Full render pass: 88 of 89 clean; `RemoteView` is the known intentional throw. `EvidenceEntries` and `ReadAllFromDrive`
  are floor cards (unauthored).
- Windows: `.ds-sync/node_modules/playwright` is 1.63.0 (pins chromium-1243, in `%LOCALAPPDATA%\ms-playwright`). The
  `.ds-sync` scripts are copied from the bundled skill, not committed.

- **Re-sync 2026-10-04 (night): the paint cards.** The project already held the glyph and role work (another session's
  upload carried it; the two "not yet synced" bullets below were stale). This run authored previews for `Swatch`,
  `PaletteMatrix`, `ColorDetail` and `SourcedDate` from the paint fixture's shapes (inline, since a preview imports only
  from `jason-ui`), graded all good, and added `cfg.overrides` column cards for `PaletteMatrix` (1000x1100) and
  `ColorDetail`. `PaletteMatrix`'s `scheme` is `number | null` (null = all), and its `today` is a `Date`, not a string.
  Still floor cards: `CitationChip` (`[RENDER_THIN]`, known). `[GRID_OVERFLOW] HostPanel (Sheet)` still stands: its card is
  column mode and the sheet is fixed/portal; the tool wants `single` with a `primaryStory`, which would hide the tabs, so
  it was left as a known warn. `ConsoleShell`'s preview has no role-strip cell yet.
- **A config edit asked for by another session was refused by the auto-mode classifier** (self-modification, from a peer
  message). The guidelines for `handoff-title-processes.md` and `handoff-discovery.md` are not in `guidelinesGlob`; the
  user has to approve that edit. (`handoff-contracts.md` was added by its own session after this upload.)
- **Glyphs through the status components (built 2026-10-04, synced).** `Pill`, `DueDate`, `Timeline`, `AuditLog`,
  `Findings`, `Caveats`, `EmptyState`, `DataTable` (a `money` kind and a `glyph` column) and `Badge` (an explicit `glyph`)
  now carry glyphs. The driver keys a component on its `.d.ts`, `.prompt.md` and preview, so it called only `HostPanel`
  changed and would NOT re-grade these although they render differently: capture them with
  `package-capture.mjs --components <list> --spot-check-components <list>` and read the sheets before uploading. The sheets
  were read 2026-10-04 and looked right; the upload waits on another session's unfinished `HostPanel`/`MeetingStage`/`Tabs`
  phone-sheet work, which would otherwise ship half-built (and `[GRID_OVERFLOW] HostPanel (Sheet)` wants a
  `cfg.overrides.HostPanel` entry).

- **Roles on `ConsoleShell` (built 2026-10-04, synced).** `ConsoleShell` takes `role`, `moves`, `landing`; a
  `ConsoleScreen` takes `roles` and `glyph`; `ScreenHeader` takes `glyph`; `DOCK_DRAWERS` carry a glyph (the pills show it).
  `DEFAULT_LANDING`, `landingScreen`, `Role`, `Move` are exported. The role class comes from the server (`roleClass` in
  `/api/session`). `ConsoleShell` and `DockToolbar` previews will need their prop sets looked at again before upload; the
  role strip is not in the shell's preview yet (add a cell with `role="officer"` and `moves`).

## Marks (built 2026-10-04, synced)

- `Glyph`, `Stamp`, `Seal`, `RoutingTag`, `RoutingTags` have authored previews; `Glyph` (the whole set, 312) and `Seal`
  (7em seals in a row) are column cards in `cfg.overrides`. The glyph bodies are static SVG from
  `ui/src/lib/glyphData.ts`, injected per glyph; nothing is fetched.
- Stamps and seals size from `--stamp-size` / `--seal-size` set on the mark, while the mark keeps its parent's font
  size, so `size="2.2em"` means the surrounding text's em (stamps.js scaled the font first, which shrank em sizes).
- The design project's `<j-stamp>`, `<j-seal>`, and glyph-layer.js are superseded by these: glyph-layer is not shipped.

## Known render warns

- `[RENDER_THIN] CitationChip.html`: no authored preview yet, so the card is the typographic floor (its name only).
  Authoring `.design-sync/previews/CitationChip.tsx` clears it.

- `[RENDER_ERRORS] RemoteView.html: TypeError: Cannot read properties of undefined (reading '0')`: the preview's
  `ChildrenThrow` cell throws on purpose to show the shape-tolerant fallback; the boundary catches it, React logs
  it, the root renders. Expected on every validate.

## Re-sync risks

- `ui/dist-lib/` is gitignored: a fresh clone must run `npm install && npm run build:lib` in `ui/` first.
- **Read the verdict before uploading.** On 2026-10-04 one driver run parsed `0 .d.ts files` (the library's type
  files were being rewritten as it read them), found 4 components, and proposed deleting every other component's
  files. Any `removed` or `deletePaths` you did not expect means the build read a half-written `ui/dist-lib/`:
  rebuild the library, re-run the driver, and upload only a verdict whose `[DTS] parsed` count and `components:`
  match the last sync. Another run the same day lost one card mid-capture the same way; a re-run was clean.
- **One sync at a time.** Several sessions sync this project from the same checkout, sharing `ds-bundle/`,
  `.ds-sync/`, and `.design-sync/.cache/remote-sync.json`. Before a run, check `ds-bundle/` and
  `.ds-sync/package-build.mjs` mtimes and the peer sessions; if another sync is mid-run, wait for it to upload, then
  fetch the fresh anchor. On 2026-10-04 (night) a guidelines-only sync waited on the paint session's; the anchor it
  then saved was that session's `ds-bundle/_ds_sync.json`, checked equal to the project's (bundleSha12, auxSha,
  scriptsSha, styleSha, hash counts). The verdict read `upload.aux` only, and the upload was the 21 aux files
  (`guidelines/**`, `README.md`) inside the full-write plan, fenced, then the anchor last.
- **A guideline only, while `ui/src` holds other sessions' unfinished work** (2026-10-05): the verdict wanted the bundle
  and styles too, which would have published that work. The plan named just the guideline, `guidelines/index.md` (the
  project's own index plus one line, so it links no guideline the project lacks), and the sentinel. The anchor was left
  as it was: it still vouches for the components, and its stale `auxSha` only makes the next sync re-upload the
  guidelines.
- The seal's word scales with the disc (no pixel floor) and sits at its centre: the 2026-10-04 capture showed long
  words clipped at the old 5em size. Check a Seal sheet's longest words (approval, confirmed) after any change to
  its CSS.
- The previews use dates around 2026-10; `DueDate` cells pass `today` explicitly so they do not drift.
- Re-sync, from the repo root, after `cd ui && npm run build:lib`: re-copy the staged scripts into `.ds-sync/`,
  `npm i esbuild ts-morph @types/react playwright@1.56.1` there, fetch the project's `_ds_sync.json` to
  `.design-sync/.cache/remote-sync.json`, then
  `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node .ds-sync/resync.mjs --config .design-sync/config.json --node-modules ./ui/node_modules --entry ./ui/dist-lib/index.js --out ./ds-bundle --remote .design-sync/.cache/remote-sync.json`.
- All 61 components have authored previews in `.design-sync/previews/`; a new component ships the floor card
  until its preview is authored. The thirteen approvals-engine components (PlanReview, WriteRow, HeldNote,
  ChangedBanner, ApproveBar, SecondConfirm, CostLine, ApplyResult, Recitation, ReadingLabel, AuditLog, QuestionCard,
  StageSteps), synced 2026-10-03, are cut from `tests/fixtures/approvals/`; their `now`/`today` props are pinned so
  the stale and clock cells do not drift. `PlanReview` is a column card at `1000x1400` (its cells are a whole plan
  and cropped at 700px); `SecondConfirm` and `StageSteps` are column cards (wide `.fields` grid; five stage tiles).
- Preview cells must differ in something visible. `SecondConfirm`'s `TwoPersonKind` differs from `Waiting` only in
  why a second person is needed, which the component does not show, so its cell has a different requester (two
  refused names). A not-in-force `Recitation` carries its own `inForce` text: spreading the in-force citation's
  `inForce` put "in force from" under "not in force".
- The 2026-10-03 re-sync re-verified all 48 earlier components: the anchor's `styleSha` and `scriptsSha` had moved
  (styles.css grew for the approvals pieces; a newer converter), so every component re-graded. Expect the same
  whenever `styles.css` changes.
- `RollCall` and `ConfirmList` are controlled (`votes`/`onChange`, `rows`/`onToggle`): their previews wrap them in a
  `useState` component, as `Tabs` and `SearchBox` do. `DecisionCard` keeps its own state from `initial`, so its
  cells are static props. `RegisterGrid`'s board cells post to `/api/write/registers/...` only on save, so the grid
  renders without a server; the `Clock` previews pass `today` like `DueDate`.
- The conventions header (`.design-sync/conventions.md`) names every component group, the approvals-engine pieces
  included; `RegisterGrid` is described only by its `.prompt.md`. Every prop name it uses was checked against the
  2026-10-03 `.d.ts` files.
- **The Doc family (2026-10-04).** `Doc`, `DocumentPreview`, and `PrivateSwitch` render wider than a grid cell
  (`[GRID_OVERFLOW]`); they are column mode in `cfg.overrides` (`Doc` at `1000x1600`). `DocList`, `EvidenceEntries`,
  `LocalPreview`, `PrivateAsk`, `PrivateBand`, and `ReadAllFromDrive` ship as floor cards: `Doc`'s and
  `PrivateSwitch`'s previews already show them. The review sheet captures every cell at a fixed width, so a
  `viewport` override does not enlarge a cell on the sheet; crop the PNG (PyMuPDF: scale the clip by
  `page.rect.height / pixmap.height`) to read a small cell.
- **A packet page on `MeetingStage`** (`PacketCopyForBoard`) was a sliver: the stage gives jason's copy `30cqw`, and
  the viewer's unscaled header and Fit toggle took it. `styles.css` now scales the viewer's header with the stage and
  hides the toggle there (`.stage-doc-copy`). A preview's sample image named `.pdf` but of kind image reads wrong;
  name a page render as a page.
- The render check marks `RemoteView` bad on every run (its throwing cell is the point); `report_validate` carries
  `bad: 1` for it.
- **Design handoffs ride the sync as guidelines (2026-10-04).** `cfg.guidelinesGlob` lists repo docs by literal path
  (`../docs/...`, package-relative from `ui/`); the build copies them flat into `guidelines/` with an `index.md`, and
  they upload under the plan's `guidelines/**`. Only general docs go there (the profile boundary test passes on
  them): never `mystique/` or anything naming the association. Their relative links point at repo paths and break
  in the project (the files are flat); the design agent finds them by name. Add a new handoff by appending its path.
- **Inspections and portals previews** (`DocumentCodes`, `ReportPortalCard`, `PortalReportRow`, `HoldingChips`, `FilingPlan`, `NoticeClock`, `AssemblyRegister`, `Discrepancy`, `TesterCheck`, `TextGrade`, `NotOursNotice`, `WatchRow`) draw their plainly fake data from `inspectionFixtures`, exported by `jason-ui`, so they import from the library alone. Synced 2026-10-04 (every cell graded good; the project's README carries the conventions section for them). Still unchecked: their dark-mode and 320 px layouts. `NotOursNotice` has no loader yet.

- 2026-10-05 re-sync: guidelines only (41 pages, incl. the forms, responses, follow-ups, form-library, and admin-components handoffs and design brief). Components, bundle, styles, and the anchor were not uploaded, so other sessions' unfinished ui/src work is not published; the remote anchor stays older than the local one. validate: ActionRegister render timed out (load); not investigated.

## Citation components (previews authored and graded 2026-10-10; not uploaded)

- **Ten components, all cells graded good, previews in `previews/`**: `StandingPill`, `StandingStrip`, `CitationChip`, `CitedSections`
  (its `Proposal` and `Freshness` are cells of that preview, not files), `CitationGaps`, `ReferenceShelf`, `WorkCard`, `ReferencePage`,
  `WorkReader`, `IngestCitations`. They were floor cards in the project (four threw on empty props). The design handoff is
  `docs/console/handoff-citations.md`, now in `guidelinesGlob`; the screen and its loaders are in the repo (commit 5ce32c0).
- **Overrides.** Every list and card is `cardMode: column` with its own viewport (`CitedSections`, `CitationGaps` 1100x1500,
  `ReferenceShelf` 1000x1800, `WorkCard`/`ReferencePage`/`WorkReader` 1000x900-1000, `IngestCitations` 1100x1400); the tables overflow a grid cell.
- **`WorkReader` fetches** `/api/reference-page?work=&page=`; its preview installs the same module-scope `fetch` stub as `AskPanel`, keyed by the
  exact URL the component builds (`work` is `encodeURIComponent`-ed, so the file name keeps its dot). Change the component's URL and the stub's keys change with it.
- **The standing words are the server's codes** (`ON_SHELF`, `NOT_EXPORTED`, `NOT_FOUND`, `RENUMBERED`, `REGULATION`, `OTHER_CODE`,
  `UNCHECKED`); the previews pass them as `standing`, and `lib/citations.ts` maps them to words and tones. A gap is the warn tone, never bad.
- **Known cosmetic nits (graded good, for the design pass):** the `not exported` pill wraps to two lines in the narrow Standing column of
  `CitedSections`, `CitationGaps`, and `IngestCitations`; in `CitationGaps` a second "Cited by" source wraps with its `;` separator.
- **Not uploaded.** The remote anchor is still the 2026-10-05 one; the driver ran locally with no anchor (`anchor: not_provided`, grades
  carried forward from `.cache/review`). A component and bundle upload publishes everything in `ui/src` at once, and other sessions' unfinished
  work is in that tree, so it waits (see the 2026-10-05 note). To publish: fetch the project's `_ds_sync.json` to `.cache/remote-sync.json`, run the driver
  with `--remote`, and upload the atomic way.
- **Re-sync risks.** The previews copy the shapes of `CitationRow`, `CitationsData`, `GapsData`, `ReferenceWork`, and `ReferencePageData` from
  `ui/src/lib/citations.ts`; a changed type fails the preview's compile (the card falls back to the floor), not the bundle. The page text in
  `ReferencePage` and `WorkReader` is made-up prose that quotes statute numbers only as names.

