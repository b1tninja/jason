# Design sync notes

Repo-specific gotchas for syncing `ui/src/components` to Claude Design. Read before a re-sync.

- **The package is an app, not a library.** `ui/` is a Vite app; the design-system entry is a separate
  library build: `cd ui && npm run build:lib` (`vite.lib.config.ts` + `tsconfig.lib.json`) writes
  `ui/dist-lib/index.js` and the `.d.ts` tree under `ui/dist-lib/components/`. Run it before the converter;
  `--entry ./ui/dist-lib/index.js --node-modules ./ui/node_modules`, from the repo root.
- **Component CSS is global.** The components carry no CSS imports; everything is `ui/src/styles.css`
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
  has `cardMode: column` and a `1400x700` viewport in `cfg.overrides`; AppShell is column mode. `.stats` is
  `minmax(150px, 1fr)` and clips six-figure money at ~500px; the Stat and Card previews widen the columns with
  inline grid glue (`.stat` itself has no overflow handling, a component note).
- **`Confirm`'s armed state is internal** and cannot render statically; its preview shows the idle button and a
  lookalike of the armed markup. `busy` only sets `disabled`, which `styles.css` does not style.
- **`RemoteView`** renders its `children` function through an inner component, so a throw while computing the
  JSX lands in `ViewBoundary`. A caught throw still appears in the review json's `pageErrs` (React logs it); the
  cell renders, so it is not a capture error.

## Known render warns

- `[RENDER_ERRORS] RemoteView.html: TypeError: Cannot read properties of undefined (reading '0')`: the preview's
  `ChildrenThrow` cell throws on purpose to show the shape-tolerant fallback; the boundary catches it, React logs
  it, the root renders. Expected on every validate.

## Re-sync risks

- `ui/dist-lib/` is gitignored: a fresh clone must run `npm install && npm run build:lib` in `ui/` first.
- The previews use dates around 2026-10; `DueDate` cells pass `today` explicitly so they do not drift.
