# Architecture

How the console is built. The console is two pieces that already exist, plus the approvals engine behind them:

- **jason-ui** (`ui/`): a React 18 library and single-page app (Vite, TypeScript). Its components are also the design system: the library build exposes them as `window.JasonUI` to the claude.ai design project ([.design-sync/](../../.design-sync/conventions.md)).
- **jason-web** (`src/jason/web/`): a Flask app under waitress that serves the built UI and the `/api/*` loaders over the stores on disk.
- **The approvals engine** (`src/jason/approvals/`): plans of writes outside jason, decided item by item, re-planned and fingerprinted before apply, with a hash-chained audit log. Its spec is [approval-workflow.md](approval-workflow.md). jason-web reaches it through the `/api/approvals*` routes (`jason.web.approvals`, being added), behind the write guard (`jason.web.guard`).

How to run it, the API (including [the approvals routes](../web-ui.md#approvals) and [the write guard](../web-ui.md#the-write-guard)), and every view are in [web-ui.md](../web-ui.md). What each screen decides, and the component behind each task, is in [web-ui-decisions.md](../web-ui-decisions.md). This page records the shape, what was decided and where, and what the console adds on top.

## What was decided, and where

| Decision | Where it was made | What it means here |
|---|---|---|
| A React SPA, no server rendering | [web-ui.md](../web-ui.md#why-this-shape) | A static bundle with content-hashed assets. No Node at runtime: `npm run build` once, then `jason-web` serves `ui/dist` |
| WSGI (Flask under waitress), not ASGI | [web-ui.md](../web-ui.md#why-this-shape) | jason's readers and stores are synchronous and take file locks. Waitress is pure Python and runs on Windows |
| One process, one origin | [web-ui.md](../web-ui.md#why-this-shape) | `/api/*` and the bundle on one port. No CORS, no proxy |
| Loopback by default | `jason.web.app.main` | `--host 127.0.0.1`, port 8080. Another host is a person's choice, and is out of scope until there is sign-in ([security-and-privacy.md](security-and-privacy.md)) |
| A write guard on every write | `jason.web.guard` | A Host check on the API, and on every write an Origin check and a per-process token (`X-Jason-Token`). Not a sign-in ([security-and-privacy.md](security-and-privacy.md#the-write-guard)) |
| Apply off by default | `jason-web --allow-apply` | The one write outside jason the console can make. Without the flag, `POST /api/approvals/<id>/apply` is refused and the page shows the terminal command |
| Reads are the MCP tools' | `jason.web.sources.default_loaders` | Each `GET /api/<source>` wraps a read-only `jason.mcp` tool or a task reader. Nothing on load calls PayHOA, Google, Zoom, or Keeper |
| Writes are jason's own stores | [web-ui.md](../web-ui.md#api) | Each write records a person's act (`by`) in a store under `data/`. None acts outward. A writer set to `None` in `create_app` answers 405 "writes are off", and `/api/health` lists the writes that are on |
| The console screens and the dock | the design handoff of 2026-10-03 ([web-ui-decisions.md](../web-ui-decisions.md#built-the-console-approvals-decisions-agenda-meeting-room-the-dock)) | `ConsoleShell` with four nav groups, the Board / Owner view, a sample "Signed in as" picker over the profile's officers, the dock |
| The handoff's rules | the same | Nothing is sent, posted, recorded, or filed without approval, and every write is a `Confirm` that spells out what changes. A board approval is a vote at a meeting that an officer records. Polls are member input; director votes are a roll call by name. Executive session stays out of open recordings, transcripts, and minutes. jason never recommends on a decision brief |
| The design system | `.design-sync/config.json` | jason-ui is the design system's source, as `window.JasonUI`. A component changed in `ui/src/components` is re-synced to the design project ([.design-sync/NOTES.md](../../.design-sync/NOTES.md)) |
| Approvals as a plan, then apply | `jason.approvals`, [approval-workflow.md](approval-workflow.md) | Built, with `jason approvals` in the CLI and read-only tools in `jason-mcp` |
| Approvals stored as JSON | `jason.approvals.store` | One file per approval in `data/approvals/`, with `audit.jsonl` beside it. The earlier SQLite plan is open as a decision only until a person confirms it ([mvp.md](mvp.md#open-decisions)) |

The plan this page used to describe (Starlette and uvicorn, Jinja2 templates, `jason serve` on port 8770, a token sign-in, and HTML forms posting to server-rendered pages) is withdrawn. Nothing was built from it.

## The pieces

```
ui/                                  jason-ui
  src/components/                    the library: one export per component (index.ts); also window.JasonUI
  src/views/                         one view per screen, by hash route (#/approvals, #/meetings, ...)
  src/App.tsx                        SCREENS: every screen, its nav group, and whether the owner view shows it
  src/lib/                           useApi, useHash, session (the sample sign-in), theme, format
  vite.lib.config.ts                 the library build for the design system (npm run build:lib -> ui/dist-lib)

src/jason/web/                       jason-web
  app.py                             create_app(): the routes, the write switches, the bundle
  sources.py                         default_loaders(): GET /api/<source>; the core writers
  extra/                             one module per console store: a loader and write(key, body),
                                     registered in sources.EXTRA_LOADERS / EXTRA_WRITERS

src/jason/approvals/                 the engine
  model.py  registry.py  store.py  audit.py  engine.py  kinds/owner_info.py  schemas/

src/jason/tasks/approvals.py         the letters jason drafted and their stages (data/approvals/letters.json)
src/jason/commands/approvals.py      jason approvals
src/jason/mcp/governance.py          approvals_list, approval_show (read only)
```

### How a screen reaches jason

| Need | Path |
|---|---|
| A read | `GET /api/<source>` → a loader in `sources.py` or `extra/` → a `jason.mcp` tool or a task reader. The loader returns a JSON-ready dict; a missing store is the tool's own `{found: false, note}` |
| A person's act on jason's own store | `POST /api/<store>/<key>` or `POST /api/write/<store>/<key>` with `by` → the task module's writer, under that store's lock (`jason.locks`) |
| A letter's stage | `GET /api/approvals`, `POST /api/write/approvals/<key>` → `jason.tasks.approvals` |
| An engine approval | `/api/approvals*` (`jason.web.approvals`) → `jason.approvals.engine` (`decide`, `submit`, `confirm`, `decline`, `withdraw`, `check`, `apply`). A plan is made in the terminal (`jason approvals plan KIND --by NAME`) |
| The profile | `jason.community.community()`, through `Community` methods only. The officers who may approve come from `Community.officers()` |
| The data folder | the profile's own (`jason.config.data_dir`, through `jason.mcp.county._data_dir`), never a path written into the app |

The rules a loader keeps are AGENTS.md's rules for tasks: it derives no fact of its own, it names no association, and importing jason-web loads no profile (loaders import lazily).

## The approvals engine behind jason-web

The engine is complete without the browser: `jason approvals plan`, `decide`, `submit`, `confirm`, `apply` work today. jason-web adds a door, not logic (`jason.web.approvals`, the same functions the CLI calls):

| Route | Engine call | Writes |
|---|---|---|
| `GET /api/approvals` | the letters inbox as before, with the engine's approvals beside it (`approvals`, `approvalsOpen`; `?status=`, `?kind=`) | nothing |
| `GET /api/approvals/<id>` | the approval as stored (`approval.schema.json`) | nothing |
| `GET /api/approvals/audit` | the log (`?approval=`, `?verify=1`) | nothing |
| `POST /api/approvals/<id>/check` | `engine.check`: re-plan live and compare | nothing, but it reads PayHOA live, so it is a POST behind the guard and the token header, never a link or a prefetch |
| `POST /api/approvals/<id>/decide` | `engine.decide` (`items`, `decision`, `reason`, `by`) | the approvals store and the log |
| `POST /api/approvals/<id>/submit`, `/confirm`, `/decline`, `/withdraw` | the same steps (`by`, `reason`, `role`) | the approvals store and the log |
| `POST /api/approvals/<id>/apply` | `engine.apply` (`by`, and `confirm`: the fingerprint the person reviewed) | **PayHOA**, only with `--allow-apply` |

- **Plan stays in the terminal.** A plan reads PayHOA live and is made with `jason approvals plan owner-info-tags --by NAME`. The console shows the plans that exist.
- **A live read fails fast.** `check` and `apply` sign in non-interactively. A missing Keeper session answers 503 with "run `jason login` in a terminal"; the browser never asks for a credential.
- **Apply is off by default.** Without `--allow-apply` the apply route is refused (403) with the terminal command, `jason approvals apply ID --yes --by NAME`, which the page shows instead. With it, the server says so on start ("apply is ON"), `GET /api/session` reports `applyEnabled`, and an apply must carry the token in its header and echo the fingerprint the person reviewed; a fingerprint that is not the approval's is refused (409) with nothing written. A re-plan that differs supersedes the approval and answers 409 with the new plan's id.
- **Answers in the engine's words.** A refusal is 400 with the engine's sentence; a lock held elsewhere is 409; a missing approval 404.
- **Privacy.** Anything that looks like an email address or a phone number is masked before it leaves the server.

Why apply stays behind a flag: the server has no sign-in, so a name on an apply is a pick from a list, not an authenticated person ([security-and-privacy.md](security-and-privacy.md#identity)). The terminal is where the live sessions (Keeper, Google) already are, and where the CLI's `--yes` has always been a person's act. Starting jason-web with `--allow-apply` is that same act, made once for the session.

### One inbox, two kinds of approval

`#/approvals` already lists the letters jason drafted (`jason.tasks.approvals`, `DraftLetter`, `ApprovalsInbox`). Engine approvals join the same inbox as a second kind, with the same count in the nav. How the two relate is in [approval-workflow.md](approval-workflow.md#11-letters-and-plans-one-inbox).

## Locking

jason-web is one more jason process beside the CLI, `jason-mcp`, and the worker. It uses `jason.locks` as they do:

| Work | Lock |
|---|---|
| A write to a console store | that store's lock, taken by the task module (`canvases`, `board-decisions`, `approvals`, ...) |
| A change to an engine approval | `hold(Resource.STORE, "approvals")` around each transition (`store.locked`) |
| An engine apply | `hold(Resource.STORE, "approval-<id>")`, then the kind's resource (`Resource.PAYHOA`) for the re-plan and every write |
| Local model work | never in jason-web's process. It is a `jason jobs` job (`JobClass.GPU`) whose worker runs `local_ai.preflight` first |

The letters store (`data/approvals/letters.json`) and the engine (`data/approvals/apr-*.json`, `audit.jsonl`) share the folder and the store lock key `approvals`. That is safe (each holds the lock only for one read, change, and write), but a slow apply's re-plan does not hold it.

Waitress serves requests on worker threads, so a long engine call (a plan's live read, an apply) holds one thread while it runs. The UI shows it as busy and does not retry. A plan or apply that should outlive the browser goes to `jason jobs` with the person's name (`--confirm NAME`), never with a `--yes` the person did not give.

## Testing

- **Server.** `pytest tests/test_web.py`: each loader with a missing store and with a fixture store; each write refused without `by`; the write switches off (405). The guard and the engine routes add: a write with a foreign `Host` (421), a foreign or missing `Origin`, or no token (403) refused before its handler; a decision on a held item refused (400); apply refused without `--allow-apply`; an apply whose echoed fingerprint is not the approval's refused with nothing written (409); and no GET that changes `data/approvals/`.
- **Engine.** `pytest tests/test_approvals.py`: the end-to-end plan, decide, submit, change the fake client, apply refused and superseded, re-plan, apply, audit chain verified.
- **Components.** `npm test` in `ui/` (Vitest and Testing Library). A new component ships with a test and a design-sync preview (`.design-sync/previews/<Name>.tsx`).
- **The boundary.** `tests/test_profile.py` checks that no general doc, `docs/console/` included, names a profile's facts. Samples in previews and tests use plainly fake values.
- **Accessibility.** The component tests query by role and label; a person does a keyboard pass of each new screen before it ships ([components.md](components.md#accessibility)).

## Dependencies

Nothing new. The console uses the `web` extra (Flask, waitress) and `ui/package.json` (React, marked, DOMPurify). The design-sync tooling lives outside the package.
