# Web UI

A React single-page app (`ui/`, Vite + TypeScript) served by a small WSGI app (`jason.web.app`, Flask under waitress).

## Why this shape

- **One process, one origin.** The WSGI app serves `ui/dist` and `/api/*` together. No CORS, no nginx, one command (`jason-web`).
- **WSGI (Flask), not ASGI.** Jason's readers and stores are synchronous and take file locks (`jason.locks`); nothing here streams or holds sockets. Flask is the smallest well-known WSGI framework and waitress is a pure-Python production server that runs on Windows. FastAPI (`app.frontend()`/StaticFiles) would also work; nothing in the UI depends on the choice, since it only calls `/api/*`.
- **Vite SPA, no SSR.** The UI is a read-only console for a few people. A static bundle with content-hashed assets (served `immutable`) needs no Node at runtime.
- **Read-only, loopback.** The API reads stores already on disk, as `jason-mcp` does, and has no write routes. It binds to `127.0.0.1`; `--host` is a person's choice.

## Run

```bash
pip install -e ".[web]"
cd ui && npm install && npm run build   # writes ui/dist
jason-web                               # http://127.0.0.1:8080
```

Development: `jason-web` in one terminal, `npm run dev` in `ui/` in another (Vite proxies `/api` to port 8080).
`npm test` runs the component tests; `pytest tests/test_web.py` runs the server's.

## API

`GET /api/health`, and `GET /api/<source>` for each loader in `jason.web.sources.default_loaders()`: `board-digest`, `board-items` (`?closed=1` includes closed), `association-records`, `records-inventory`, `library-status`, `document-readings`, `jobs`, `leads` (the aggregate described in [web-ui-decisions.md](web-ui-decisions.md)), `duties` (`?anchor=` for one brief with its passages), `calendar`, `meetings` (`?date=`), `insurance`, `budget` (`?year=`), `reconciliations`, `invoices` (`?all=1` includes clean payments), `collections`, `reserves`, `hearings`, `title-watch` (`?attention=1`, `?standing=`, `?apn=`), `open-items` (`?days=`), `utility-payments` (`?all=1`), `ledger-validation`, `legal-cases`, `audit-chains` (`?apn=`), and `request-links` (`?unit=`, `?drafts=1`). Each wraps a read-only `jason.mcp` tool.

A view that trips on a shape it did not expect does not take the page down: `RemoteView` catches the render error and shows the tool's raw result through `DigestView`, with the error named, so the person still sees what the tool returned. A loader that fails answers `{"error": ...}` with 4xx/5xx, which the UI shows with a Retry.

The one write: `POST /api/board-items/<id>` with any of `status`, `owner`, `meeting`, `notes`, the board's own columns, through `tasks.board_items.set_fields` (what `jason board --set` calls). Any other field is refused with 400. `create_app(board_writer=None)` turns it off; `/api/health` lists `writes`.

## Views (`ui/src/views`, hash routes)

`#/digest` (any tool result, generic), `#/duties` (the manager's duty anchors by cadence, each opening to its brief and the documents' passages), `#/calendar` (the recurring deadlines, overdue first), `#/money` (the monthly review: budget against actual, reconciliations, invoice questions, collections), `#/meetings` (each meeting's records and checks), `#/insurance` (the policy register against payments and mail), `#/inbox` (what is waiting on the association, from every store), `#/drafts` (emailed requests PayHOA does not have, each with the command a person runs to enter it; the page never runs it), `#/reserves` (each borrowing's 5515 record as a checklist), `#/title` (liens by standing, the four a person acts on first), `#/hearings` (the 5855 clocks; directors only), `#/books` (utility payments with findings, and the treasurer's reports validated against the ledger), `#/legal` (open statutory duties per matter and the deed-chain audit; directors and counsel), `#/jobs` (the queue by status with each job's log; who confirmed a write), `#/board` (kanban of board items; the board's fields editable behind a confirm), `#/records` (the Civil Code 5200 inventory and the recorded instruments), `#/ingestion` (how the library was classified, and what the recorded copies say), `#/leads` (everything unpinned, in one list), `#/status`.

## Components (`ui/src/components`)

Layout and data: `AppShell`, `Card`, `Stat`, `Badge`, `Money` (integer cents), `DataTable` (sort, filter), `Tabs`, `SearchBox`, `Kanban`, `Timeline`. The tools' shared shapes: `Pill` (a standing or status with its meaning), `Findings`, `Caveats`, `Evidence`, `DueDate`, `RemoteView` (loading, error, the tool's own `found: false` note). Writes: `Confirm` (two clicks, the change spelled out). `DigestView` renders a result without knowing its shape. The map from tasks to components is [web-ui-decisions.md](web-ui-decisions.md).

## Open

Authentication (needed before any non-loopback host, and before any write beyond the board's columns), and packaging `ui/dist` inside the wheel.
