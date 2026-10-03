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

Two writes, both to jason's own stores, nothing outward:

- `POST /api/board-items/<id>` with any of `status`, `owner`, `meeting`, `notes`, the board's own columns, through `tasks.board_items.set_fields` (what `jason board --set` calls). Any other field is refused with 400.
- `POST /api/canvases` (`title`, `question`, `duty`, `matter`) opens a canvas; `POST /api/canvases/<key>` changes its editable fields (`title`, `question`, `status`, `matter`, `duty`, `notes`, `links`, `checklist`, `attachments`) or, with `clip: {source, text, label, args}`, adds a clip. `GET /api/canvases` lists them and `?key=` gives one. The store is `data/canvases/<key>.json` (`tasks.canvases`, under the `canvases` store lock). An attachment is `{kind, ref, title, opts?}` with kind one of `doc`, `sheet`, `slides`, `form`, `drive`, `image`, `pdf`, `url`, `calendar` (a Google calendar id; `opts.mode`, `opts.dates`, `opts.tz`), `zoom` (a recording's share or play URL), `audio` (a path under `data/` or a URL), `map` (an address or `lat,lng`), `chart` (a published Sheets chart URL, or a Sheet id with `opts.gid` and `opts.range`), `thread` (a Gmail thread, shown as a link card: Gmail cannot be framed); `ref` is a Google file id or URL, or for an image, PDF, or audio file a path under `data/`. A frame that never loads falls back to a link card.

`GET /api/embeds` gives what a canvas embeds from the association's own accounts: the calendar id the deadlines are written to (`Community.calendar_id()`, empty until the profile sets it), the time zone, and the Zoom recordings on disk (date, topic, share and play URLs, and the files under `data/zoom/` the file route can serve). Google Tasks has no embed surface; the board items' Tasks sync is shown from jason's own record instead.

Read-only helpers for the canvas: `GET /api/file?path=` serves a photo, PDF, or text file under `data/` and nothing else (path-checked, known types only, `Content-Security-Policy: sandbox`); `GET /api/drive-files?q=` searches the Drive catalog (`data/drive/files.json`) and names the kind each file embeds as; `GET /api/photos` lists the albums under `data/photos/`; `GET /api/templates` lists the letter templates with each token sorted by who fills it (the profile, a general citation, or the run), and `?kind=&name=&V_TOKEN=value` renders the body as Markdown with those values (`templates.body_markdown`, the same text the Doc is built from), the tokens still open, and the `jason letter … --yes` command.

- `POST /api/decisions` (`meeting`, `title`, `motion`, and any of `item`, `session`, `mover`, `second`, `votes`, `outcome`, `by`, `notes`) records what the board did on one item at one meeting, replacing an earlier record for the same meeting and item; `POST /api/decisions/<id>` changes one in place. `GET /api/decisions?meeting=` lists them with each vote's tally and what the votes say on their face; the outcome is the board's word. The store is `data/board/decisions.json` (`tasks.decisions`, under the `board-decisions` store lock), and the minutes draft (`jason board --minutes`) quotes it.

- `POST /api/onboarding/<key>` records what a person did about one item of the onboarding request list (`status`, `asked_of`, `asked_on`, `chased_on`, `received_on`, `filed`, `reason`, `note`); the store is `data/onboarding/requests.json` (`tasks.onboarding`). `GET /api/onboarding` gives the active community's accounts (set or not, never a value), its facts by duty, the request list with the stores' own reading beside each item, and the gaps; `GET /api/communities` lists every profile this checkout can load with the active one's progress; `GET /api/request-letter` writes the letter from the items marked asked; `GET /api/library` (`?kind=`, `?record=`, `?period=`, `?words=`, `?confidential=1`) searches the classified library, so a received item is marked with the file jason classified rather than a typed path; `GET /api/rule-changes` lists the proposed rule changes in the specification and `?key=` gives one with its sections as current and proposed text, its bracketed choices (`V_<choice>=` fills one for the preview), the decisions to settle first, the Civil Code 4360 clock from `?notice=` to `?decision=`, and the `jason rule-change … --draft-email --yes` command. The design is [onboarding-ux.md](onboarding-ux.md).

- `POST /api/owner-info/<key>` (`by`, `confirmed`) records a person's confirmation of one planned owner-information write. `jason owner-info` saves the plan it computed (`data/payhoa/owner-info-plan.json`, `tasks.owner_info_plan`) as the read artifact of its run; `GET /api/owner-info` shows each write with its confirmation, the requests left to complete, the owners by standing, and the apply command once every write is confirmed. The apply stays `jason owner-info --apply --payhoa --yes` from a terminal.

`create_app(board_writer=None, canvas_writer=None, decision_writer=None, request_writer=None, owner_info_writer=None)` turns the writes off; `/api/health` lists `writes`.

## Views (`ui/src/views`, hash routes)

`#/communities` (the portal: every profile, the active one with its onboarding progress), `#/onboarding` (accounts, facts, the request list and its letter, gaps), `#/digest` (any tool result, generic), `#/duties` (the manager's duty anchors by cadence, each opening to its brief and the documents' passages), `#/calendar` (the recurring deadlines, overdue first), `#/money` (the monthly review: budget against actual, reconciliations, invoice questions, collections), `#/meetings` (each meeting's records and checks), `#/insurance` (the policy register against payments and mail), `#/inbox` (what is waiting on the association, from every store), `#/drafts` (emailed requests PayHOA does not have, each with the command a person runs to enter it; the page never runs it), `#/canvases` and `#/canvases/<key>` (the scratchpads: one per topic being researched or prepared for board action, with notes as Markdown with ```mermaid diagrams and photos, Google Docs, Sheets, Slides, Forms, and Drive files shown in place, photos and PDFs under `data/` served read-only, clips of what the records show, links, a checklist, and the commands that take it to the board), `#/templates` (the letter templates: fill one, see it as it would read, copy the `jason letter` command, keep the text on a canvas), `#/reserves` (each borrowing's 5515 record as a checklist), `#/title` (liens by standing, the four a person acts on first), `#/hearings` (the 5855 clocks; directors only), `#/rules` (the proposed rule changes: the board's bracketed choices, the sections current and proposed, the 4360 clock, the notice command), `#/books` (utility payments with findings, and the treasurer's reports validated against the ledger), `#/legal` (open statutory duties per matter and the deed-chain audit; directors and counsel), `#/jobs` (the queue by status with each job's log; who confirmed a write), `#/board` (kanban of board items; the board's fields editable behind a confirm), `#/records` (the Civil Code 5200 inventory and the recorded instruments), `#/ingestion` (how the library was classified, and what the recorded copies say), `#/leads` (everything unpinned, in one list), `#/status`.

## Components (`ui/src/components`)

Layout and data: `AppShell`, `Card`, `Stat`, `Badge`, `Money` (integer cents), `DataTable` (sort, filter), `Tabs`, `SearchBox`, `Kanban`, `Timeline`. Content: `Markdown` (marked + DOMPurify; a ```mermaid fence renders as a diagram, the library loaded on first use), `Embed` (a Google Doc, Sheet, Slides deck, Form, or Drive file in a frame, a photo, a PDF; the viewer must already have access to the Google file), `Command` (a command to copy, never run). The tools' shared shapes: `Pill` (a standing or status with its meaning), `Findings`, `Caveats`, `Evidence`, `DueDate`, `Clock` (a statutory timeline as stages with today's position), `RemoteView` (loading, error, the tool's own `found: false` note). Writes: `Confirm` (two clicks, the change spelled out), `ConfirmList` (a checklist with a name on each tick that gates what follows). Writes: `Confirm` (two clicks, the change spelled out). `DigestView` renders a result without knowing its shape. The map from tasks to components is [web-ui-decisions.md](web-ui-decisions.md).

## Open

Authentication (needed before any non-loopback host, and before any write beyond the board's columns), and packaging `ui/dist` inside the wheel.
