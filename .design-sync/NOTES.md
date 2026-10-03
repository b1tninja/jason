# Design sync notes

Repo-specific gotchas for syncing `ui/src/components` to Claude Design. Read before a re-sync.

- **The package is an app, not a library.** `ui/` is a Vite app; the design-system entry is a separate
  library build: `cd ui && npm run build:lib` (`vite.lib.config.ts` + `tsconfig.lib.json`) writes
  `ui/dist-lib/index.js` and the `.d.ts` tree under `ui/dist-lib/components/`. Run it before the converter;
  `--entry ./ui/dist-lib/index.js --node-modules ./ui/node_modules`, from the repo root.
- **Component CSS is global.** The components carry no CSS imports (a per-component `.css` import makes the library
  build emit a separate `style.css` the converter never ships, so designs lose those rules; `Embed`'s link-card rules
  were folded into `styles.css` for that reason); everything is `ui/src/styles.css`
  (`cfg.cssEntry`). Tokens are the `:root` custom properties in that file (`--bg`, `--panel`, `--ink`, `--muted`,
  `--line`, `--accent`, `--good`, `--warn`, `--bad`), with a dark variant under `prefers-color-scheme`. The font is
  `system-ui`: no `@font-face`, nothing to ship, no `[FONT_MISSING]`.
- **Four exports share a source file.** `Loading`, `ErrorNotice`, `EmptyState` live in `States.tsx` and
  `RemoteView` in `Remote.tsx`; `cfg.componentSrcMap` pins them, otherwise they are "not src-matched".
- **Playwright.** The container's cached Chromium is build 1194 at `/opt/pw-browsers`, pinned by
  `playwright-core@1.56.1` (`/opt/node-tools`). Install that exact `playwright` version into `.ds-sync/` and run
  validate/capture with `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`. A newer playwright fails with
  "Executable doesn't exist".
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

## Known render warns

- `[RENDER_ERRORS] RemoteView.html: TypeError: Cannot read properties of undefined (reading '0')`: the preview's
  `ChildrenThrow` cell throws on purpose to show the shape-tolerant fallback; the boundary catches it, React logs
  it, the root renders. Expected on every validate.

## Re-sync risks

- `ui/dist-lib/` is gitignored: a fresh clone must run `npm install && npm run build:lib` in `ui/` first.
- The previews use dates around 2026-10; `DueDate` cells pass `today` explicitly so they do not drift.
- Re-sync, from the repo root, after `cd ui && npm run build:lib`: re-copy the staged scripts into `.ds-sync/`,
  `npm i esbuild ts-morph @types/react playwright@1.56.1` there, fetch the project's `_ds_sync.json` to
  `.design-sync/.cache/remote-sync.json`, then
  `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node .ds-sync/resync.mjs --config .design-sync/config.json --node-modules ./ui/node_modules --entry ./ui/dist-lib/index.js --out ./ds-bundle --remote .design-sync/.cache/remote-sync.json`.
- All 48 components have authored previews in `.design-sync/previews/`; a new component ships the floor card
  until its preview is authored.
- `RollCall` and `ConfirmList` are controlled (`votes`/`onChange`, `rows`/`onToggle`): their previews wrap them in a
  `useState` component, as `Tabs` and `SearchBox` do. `DecisionCard` keeps its own state from `initial`, so its
  cells are static props. `RegisterGrid`'s board cells post to `/api/write/registers/...` only on save, so the grid
  renders without a server; the `Clock` previews pass `today` like `DueDate`.
- The conventions header (`.design-sync/conventions.md`) still names only the first 23 components; the five from
  the board loop (`Clock`, `ConfirmList`, `RollCall`, `DecisionCard`, `RegisterGrid`) are described only by their
  `.prompt.md`. Every name it does use verified against the 2026-10-03 build.
