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

`GET /api/health`, and `GET /api/<source>` for each loader in `jason.web.app.default_loaders()` (today `board-digest`, the `board_digest` tool). A loader that fails answers `{"error": ...}` with 4xx/5xx, which the UI shows with a Retry. Add a source by adding a loader; it reads the association only through `Community`.

## Components (`ui/src/components`)

`AppShell`, `Card`, `Stat`, `Badge`, `Money` (integer cents), `DataTable` (sort, filter), `Tabs`, `SearchBox`, and `Loading`/`ErrorNotice`/`EmptyState`. `DigestView` renders a tool result without knowing its shape: scalars become stats, row lists become tables, and keys ending in `Cents` show as dollars. Build a purpose-made view when a result needs more than that.

## Open

Authentication (needed before any non-loopback host), routing (tabs are local state), and packaging `ui/dist` inside the wheel.
