# Board action items

`#/actions` (`ConsoleActions`, `BoardItemsView`) · built · CLI: `jason board`

## In the console

One card per matter jason's reviews found that needs a board decision, laned by the board's status. jason's columns (the ask, the authority, the summary, the evidence, the priority) are read-only; the board's four (status, owner, meeting, notes) are edited in `BoardFields` behind a `Confirm`, the same fields `jason board --set` changes. An item is a matter to decide, never the decision.

## Data

| Part | Source | Loader |
|---|---|---|
| The items | `jason.mcp.county.board_items(include_closed)` → `items[]` (`jason.tasks.board_items._encode`) | `GET /api/board-items?closed=` (`jason.web.sources.board_items`) |
| The evidence | Each item's `evidence` strings, and beside them `evidenceRefs`: the same strings mapped by `jason.approvals.docref.refs_from_strings`, one for one | the same; the board's write (`POST /api/board-items/<id>`) answers them too |

## Documents

The evidence is shown with `Doc`, fed the loader's references ([doc-component.md](../doc-component.md)); never a path as text or a raw `/api/file` link.

| Document | Reference | Variant | Level |
|---|---|---|---|
| A document an evidence string names: `library: <path>` or `library:<id>`, `Drive: <name>` (one file by that name), `data/<path>` (a placed file on disk), or a citation | `evidenceRefs[i]`, a `DocRef` (`library:`, `drive:`, `file:`, or the citation) | `chip`, under **Details and board fields** | the server's |
| A `jason …` command | `{command}` | code with **Copy**; the page never runs it | — |
| Anything else (a description, a PayHOA request list, a name that matches no file or several) | `{text}`, masked | plain text, never a guess | — |

An older server that answers no `evidenceRefs` shows the strings as chips, as before. The MCP tool `board_items` is unchanged: the references are the console's.

## Acceptance criteria

1. A string that names a document jason keeps opens it as one logged view (`POST /api/evidence/view`); nothing is viewed on load.
2. Signed out, a chip says "Sign in with Google to open this"; a view the server refuses says its reason.
3. The screen renders no `/api/file` link, no frame of an outside host, and no absolute path.
4. Each reference the loader answers resolves (`jason.approvals.evidence.resolve`), and carries the server's level (`tests/test_board_docrefs.py`).
