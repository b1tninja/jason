# Developing the MCP server locally: one process for every session

Research and a proposal (October 4, 2026). Nothing here is built yet.

## The problem

`.mcp.json` names `jason` and `hardly` as **stdio** servers. A stdio server is a child process of the client, so every
Claude Code session and every Cursor window starts its own copy of each. On Windows each copy is two processes (the
venv's launcher `jason-mcp.exe` or `python.exe`, and the Python it starts).

On October 4, 2026 there were 9 Claude Code sessions and 3 Cursor windows:
- 18 `jason-mcp` processes (about 1.0 GB), 24 `hardly` (about 1.0 GB), 14 `mcp_server` (0.4 GB), and 6 `jason.mcp`
  (0.25 GB).
- Every one still had a live parent, so none was an orphan: the count is sessions × servers × 2.
- They were a small part of the commit in use: about 2.7 GB of 56 GB, against 14.6 GB for the Claude sessions themselves.

A code change does not reach them until each session restarts its server.

Docker would give one server, but every change then means a rebuild or a restart. A container could bind-mount the
source and reload instead, but on Windows file-change events often do not cross into a WSL2 container from an NTFS
folder, so the reloader has to poll.

## What the clients and the SDK support

- **Claude Code** speaks stdio, HTTP (streamable HTTP; `"type": "http"` or `"streamable-http"` in `.mcp.json`), SSE
  (deprecated), and WebSocket.
  - It retries a server that dropped, with exponential backoff, up to five attempts. `/mcp reconnect` reconnects by hand.
  - In an interactive session it acts on a server's `list_changed` notification, fetching the new tool list without a
    reconnect.
  - Each session holds its own connection; a server on a URL is one process however many sessions use it.
- **The MCP Python SDK here (2.2.0)** names the server `MCPServer` (FastMCP's new name).
  - `run(transport="streamable-http")` and `streamable_http_app(...)` serve the same server over HTTP: a Starlette app
    with `stateless_http`, `json_response`, `session_idle_timeout`, `max_sessions`, and `host` (127.0.0.1 by default).
  - A sync tool runs in a worker thread (`anyio.to_thread`), so one process can serve several sessions at once.
  - `uvicorn` 0.53, `starlette`, and `watchfiles` are already installed.
- **jason's locks** (`jason.locks`) are file locks on Windows (`msvcrt.locking`), which hold between threads of one
  process as well as between processes. That is a reading of the code to test, not a measurement.

## The options

1. **One local HTTP daemon that reloads itself. Recommended for development.**
   - `jason-mcp --http` serves on `127.0.0.1` (no network exposure). `--reload` runs it under uvicorn's reloader,
     watching `src/jason`: an edit restarts the one process in a second or two.
   - `.mcp.json` names `{"type": "http", "url": "http://127.0.0.1:PORT/mcp"}`, so every session and window shares it.
   - Each profile (board, governance, onboarding) is its own path in the same process (`/mcp`, `/mcp/board`, ...).
   - A tool's changed body takes effect on the next call after the reload. A new or renamed tool appears when the
     client starts a new session against the restarted server. Under the spec, a request with an unknown session
     id gets a 404, and the client starts a new session; `/mcp reconnect jason` does it by hand.
   - Costs:
     - one process serves everyone, so a crash or a stuck tool affects every session;
     - Claude Desktop's chat app takes stdio servers in its config, so it needs a bridge (option 2) or stays on stdio;
     - the daemon has to be started (by hand, by `jason worker`'s logon task, or by a scheduled task at logon).
2. **A thin stdio shim in front of the daemon.**
   - Clients that only speak stdio run a small forwarder instead of jason: `mcp-proxy` (sparfenyuk, MIT) bridges stdio
     to streamable HTTP. It is still one process per session, but tens of megabytes with none of jason's imports.
   - It also keeps stdio's habit of starting with the session.
3. **Hot reload inside a stdio server.**
   - A wrapper stays attached to the client and restarts the real server, or re-imports its tool modules, on a file
     change, then sends `tools/list_changed`. Examples: `mcp-reloader` and `mcpmon` ("nodemon for MCP").
   - It fixes the restart-to-see-a-change loop, not the number of processes.
4. **Slimmer stdio servers.**
   - Import heavy modules inside the tools that use them, so an idle copy costs less.
   - Worth doing anyway, but it keeps one copy per session.
5. **Docker with the source bind-mounted and a polling reloader.**
   - This is close to the deployed shape (docs/deployment-research.md) without a rebuild per change.
   - It is the right test before deploying, not the everyday loop.

The model is already handled this way: Ollama is one local daemon that every jason process, and AnythingLLM, reaches
over HTTP (docs/jobs.md). Option 1 gives the MCP server the same shape.

## Proposal

1. Add `--http [--port N] [--reload]` to `jason-mcp`:
   - the SDK's `streamable_http_app` under uvicorn, bound to 127.0.0.1;
   - one Starlette app mounting each profile at its own path;
   - `--reload` as uvicorn's reloader over `src/jason`, using an app factory.
2. Keep stdio as the default, so a fresh checkout works with no daemon.
   - A developer's `~/.claude.json` (local scope) points `jason` at the URL; `.mcp.json` stays stdio for everyone else.
3. Start the daemon at logon beside the worker, and show it in `jason local-ai` with the other daemons (up or down,
   port, sessions served).
4. Test first:
   - two sessions calling tools at once;
   - a tool that takes the GPU or a store lock from two sessions;
   - a reload while a call runs;
   - a new tool appearing after a reload, without restarting Claude Code.

## Sources

- [Claude Code: connect Claude Code to tools via MCP](https://code.claude.com/docs/en/mcp)
- [.mcp.json configuration reference](https://thepromptshelf.dev/blog/mcp-json-configuration-reference-2026/)
- [FastMCP transport options (stateless_http, json_response)](https://gofastmcp.com/python-sdk/fastmcp-server-mixins-transport)
- [mcp-proxy (sparfenyuk)](https://glama.ai/mcp/servers/sparfenyuk/mcp-proxy)
- [mcp-reloader](https://glama.ai/mcp/servers/@mizchi/mcp-reloader) and [mcpmon](https://pypi.org/project/mcpmon/)
- The installed SDK's signatures (`MCPServer.run`, `streamable_http_app`), read on this machine
