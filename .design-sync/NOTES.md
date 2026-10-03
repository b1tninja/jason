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
  (template literal, not an array). `DueDate` takes `today` so a preview is deterministic.

## Known render warns

(none recorded yet)

## Re-sync risks

- `ui/dist-lib/` is gitignored: a fresh clone must run `npm install && npm run build:lib` in `ui/` first.
- The previews use dates around 2026-10; `DueDate` cells pass `today` explicitly so they do not drift.
