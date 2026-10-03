# Architecture

How the console is built: the stack, the modules, how pages reach jason, locking and long work, launching, and testing. The approvals engine (`jason.approvals`) is specified in [approval-workflow.md](approval-workflow.md) and built separately. The console is one of its three doors.

## Stack

**The choice:**
- Starlette, served by uvicorn;
- HTML rendered on the server, with Jinja2 templates;
- plain HTML forms that work with no script;
- a few small scripts, served by the console itself, that enhance the forms;
- no JavaScript build step, no framework, no CDN.

**Why it fits the repo:**
- **Starlette and uvicorn are already installed.** They come in with `mcp`. The console adds no web framework the project does not already carry.
- **The work is reads of Python functions.** Every screen is a call to `jason.api` or a task function that returns a dict or dataclasses, rendered once. A server-rendered page is the shortest path from that dict to the screen. A single-page app would need a JSON API for every screen, plus a client-side copy of the data model, the masking, and the role checks. Those checks must stay on the server ([security-and-privacy.md](security-and-privacy.md#data-levels)).
- **Forms are the approval model.**
  - Approving is a form post: the selected items, a name, the fingerprint, and the CSRF token.
  - It works with no script, which is also the accessible baseline.
  - The UI library already builds on this: its write-row checkboxes join the approve bar's form with `form="approve-form"`.
  - Scripts add "select all", the live count, the same-name check before sending, and toasts. They never decide anything.
- **No build step means nothing to break between Python releases.** The repo has no Node toolchain, and a manager's machine should not need one. The CSS and JS in `src/jason/console/ui/` are served as written.
- **Local-first holds.** Every asset ships in the package, and the Content-Security-Policy is `'self'` only.

**Templates: Jinja2, as an optional extra.** Jinja2 is not installed today. It is the one new dependency the console should take, for two reasons:
- **autoescaping by default.** Owners' names, request text, and document words are rendered into HTML, so an unescaped value is the console's most likely injection bug. Jinja2 makes escaping the default and raw HTML the explicit exception (`|safe`, used only on HTML jason rendered itself, such as `reader.Sheet`).
- **one macro per component.** The UI library's components (`ui/components/*.html`) are reference markup with their states and variants in comments, and they become macros one for one. Starlette's `Jinja2Templates` loads them.

The alternative, recorded as an open decision in [mvp.md](mvp.md#open-decisions), is a small `jason.console.html` builder: an escaping `Html` string type plus functions for each component, with no dependency. It is workable, but it re-implements autoescaping and makes the markup harder to compare with the library's reference files.

**Progress for long work:**
- **With script:** a small poller (`static/console.js`) fetches `GET /jobs/{id}` as JSON every two seconds, and announces the result through a `role="status"` region (WCAG 4.1.3).
- **Without script:** the job page carries a "Refresh" link.

No WebSocket and no server-sent events: polling a local server costs nothing, and survives a laptop's sleep.

## Module layout

```
src/jason/approvals/            the engine (built separately; approval-workflow.md is its spec)
  model.py                      Approval, PlanItem, Decision, ApprovalStatus, ItemClass, Result, Signature
  registry.py                   ActionKind rows (KINDS)
  fingerprint.py                item ids, bases, plan fingerprints
  store.py                      data/console/approvals.db
  audit.py                      data/console/audit.jsonl: append, read, verify
  kinds/owner_info.py           plan(scope, client) and apply(approval, client): the owner-information adapters
  cli.py                        jason approvals
  schemas/                      JSON Schemas of the records

src/jason/console/
  __init__.py                   create_app() re-exported
  app.py                        create_app(*, data_dir=None, token=None, community=None) -> Starlette
  serve.py                      jason serve: the subcommand (register, cmd_serve)
  security.py                   host guard, login and session, CSRF, the security headers
  identity.py                   Role, Actor, the roster (private facts), permits(actor, action)
  privacy.py                    Level, mask(value, kind), reveal (logged)
  render.py                     the Jinja environment: filters (cents to dollars, dates in the association's
                                time zone, data levels), globals (the profile's name, the acting person)
  runner.py                     long work: one job at a time per resource, progress, results
  pages/
    today.py  approvals.py  members.py  requests.py  notices.py  meetings.py
    documents.py  schedule.py  records.py  finance.py  onboarding.py  settings.py  audit.py
  templates/                    base.html and one folder per page; components imported as macros from ui/
  ui/                           the component library (tokens.css, base.css, components/*), served at /static/ui/
  static/console.js             login fragment, the job poller, the progressive enhancements
```

Rules the layout keeps:

- **A page module only reads and renders.** It calls `jason.api`, a `jason.mcp.*` function, a task function, or `jason.approvals`, and passes the result to a template. It derives no fact itself. When a page needs a fact jason does not yet return, the fact is added to the task (or to `Community`, with an empty default) first. That is the AGENTS.md rule for tasks, applied to pages.
- **No association in the console's code.** The profile's name, roster, letterhead, and rules come from `jason.community.community()` and the private facts. Nothing in `src/jason/console/` names an association, a street, a vendor, or a person. The UI library's sample markup uses plainly fake values.
- **Importing the console loads no profile.** `create_app()` resolves the profile when it is called, not at import time.
- **Each page module exposes `routes() -> list[Route]`.** `app.py` mounts them. The pages hold no state between requests apart from the session.
- **Handlers are plain `def`, not `async def`.** jason's functions block: they read files and call PayHOA. Starlette runs a sync endpoint in its thread pool, so a slow read never stalls the event loop. Live reads go through `runner.py`, never in the request itself.

### How a page calls jason

| Need | Call |
|---|---|
| The data folder | `jason.config.data_dir()`: the profile's own, as the CLI reads it. Never a path written into the console |
| The profile | `jason.community.community()` |
| A governance read | `jason.api.<tool>(...)`, which returns a JSON-ready dict |
| A board read | `jason.mcp.county.<tool>(...)` (`budget_status`, `board_items`, `unit_brief`, ...) |
| A record page | `jason.api.read_record(address)`, or `jason.tasks.reader.sheet(...)` for the HTML sheet |
| A live read or write | `jason.agent.Jason(interactive=False)`, inside a `runner` job. A missing Keeper or Google session raises `KeeperAuthRequired` or `GoogleAuthRequired`, and the job fails fast with "run `jason login` in a terminal" |
| A plan, decision, or apply | `jason.approvals.<function>(...)` |
| A signed `data/` write | `api.answer_intake_question`, `api.onboarding_confirm`, `api.record_completion`. They take their own locks and require `by` |

## Locking

The console is one more jason process beside the CLI, the MCP server, and the worker. It uses `jason.locks` exactly as they do:

| Work | Lock |
|---|---|
| A change to the approvals store | `hold(Resource.STORE, "approvals", timeout=30, purpose=...)` around each transition. SQLite runs in WAL mode, so reads need no lock |
| A plan's live read | `hold(Resource.PAYHOA, "plan-<kind>", timeout=5)`. On `ResourceBusy`, the job fails with who holds the lock (`locks.holders()`): "PayHOA is busy: batch owner-info-… is sending" |
| An apply | The kind's `resource` lock for the whole re-plan and write (`hold(Resource.PAYHOA, "approval-<id>")`), as `jason.batches.run` holds `batch-<id>` |
| A Google write | `hold(Resource.GOOGLE, ...)`, where the task already takes it |
| Local model work | Never in the console's process. It is queued to `jason.jobs` (`JobClass.GPU`), whose worker runs `local_ai.preflight` first |

A store jason writes whole (JSON) can be read while it is half-written. A page that gets a decode error reads it once more, then shows the section as unavailable. It never shows a partial read as data.

## Long work: jobs and progress

`runner.py` is a small in-process queue for work started from the console:
- one worker thread per resource class: `payhoa`, `google`, `local`;
- each job records its kind, who started it, its state (queued, running, done, failed), its last lines of progress, and its result. The result is the new approval's id, or an error with the command to fix it;
- jobs live in memory, and their outcome lands in the approvals store and the audit log. A restart loses only the progress text.

**Hand-off to the job queue.** For work that should outlive the console, or must run on the GPU, the console adds a job to `jason.jobs` instead, with the acting person as `confirmed_by`. That is the queue's own rule: a write is queued only with the name of the person who confirmed it. Examples:
- `jobs.add(data_dir, ["approvals", "apply", ID, "--by", NAME], confirmed_by=NAME)`;
- `["owner-info", "--email-batch", ...]`, from phase 4.

The worker never adds `--yes`, and never retries a write. The console shows queued jobs from `jobs.jobs(data_dir)`, with each one's log (`jobs.log_path`).

**Batches stay batches.** An approved email or mail batch (phase 4) is created through `jason.batches.create(..., confirmed_by=...)` and run by the command that owns it. The console shows `batches.items` and `batches.events`, and offers `--retry-failed`, `--resolve`, and `--cancel` as their own approvals.

## `jason serve`

```
jason serve [--port 8770] [--open] [--rotate] [--print-token]
```

- It binds 127.0.0.1 only. There is no `--host` option ([security-and-privacy.md](security-and-privacy.md#where-it-listens)).
- It prints the sign-in link (the token in the fragment) once. `--open` opens the default browser on it.
- It refuses to start if the port is taken, and says which process holds it.
- It runs uvicorn in the foreground with one worker process; the console's runner threads live in that process. Ctrl-C stops it, and a running apply finishes its current item first.
- It is registered from `src/jason/commands/serve.py` (or `jason.console.serve.register`). `src/jason/cli.py` needs one line to add it, which is part of the build, not this spec.

## Launch configuration

The entry to add to `.claude/launch.json`, beside the existing preview entry:

```json
{
  "name": "jason-console",
  "runtimeExecutable": "D:\\code\\jason\\.venv\\Scripts\\python.exe",
  "runtimeArgs": ["-m", "jason", "serve", "--port", "8770"],
  "port": 8770
}
```

- Port 8770 keeps clear of the owner-information preview server's 8765.
- The preview pane opens the origin, `http://127.0.0.1:8770`. The console shows `/login`, which asks for the token `jason serve` printed in the server's output (`preview_logs`).
- The entry carries no token, because a launch file can be committed.

## Testing

Tests run under `pytest`, with the made-up private facts in `tests/fixtures/spec`, which `conftest.py` sets through `JASON_SPEC_DIR`. They give the same results on any checkout.

- **Pages.** `starlette.testclient.TestClient(create_app(data_dir=tmp_path, token="t"))`. TestClient needs `httpx`, which is installed with `mcp`. A fixture logs in (`POST /login` with the token) and carries the session cookie and CSRF token. Each page has a test that it:
  - renders with a missing store (shows "unavailable", not a 500);
  - renders with a fixture store;
  - shows no P2 value unmasked.
- **Security.** These requests are refused:
  - a `Host` other than loopback (421);
  - a POST without the CSRF token, or with a foreign `Origin`, or with `Sec-Fetch-Site: cross-site` (403);
  - a second login with a used token;
  - every route without a session (redirect to `/login`, or 401 for JSON).

  A test walks every route and asserts that GET never changes the approvals store or the audit log.
- **The approval flow, end to end, with no network.** It uses a fake PayHOA client like the one in `tests/test_owner_info.py` (`update_member_tags`, `add_unit_tag`, `set_submission_complete`, `add_submission_comment`, `list_units`, `iter_people`, and the form submissions):
  1. plan;
  2. decide some items, with a rejection reason;
  3. submit with a name;
  4. change the fake's state for one approved member;
  5. apply, and assert `superseded`, no client write, and a new approval;
  6. plan again, approve, and apply;
  7. assert exactly the approved calls were made, and that the request completion was blocked where a write was rejected;
  8. verify the audit chain.
- **Second person.** The same name is refused (casefold and trimmed). A re-plan clears both signatures.
- **Accessibility, in tests.** Every page's HTML is parsed and checked for:
  - one `<h1>`;
  - a `<main>` landmark;
  - a label on every form control;
  - no positive `tabindex`;
  - `<th scope>` on table headers;
  - `aria-live` or `role="status"` on the regions that change.

  Contrast is checked once, in the token file's own test: the tokens.css header states its ratios.
- **The boundary.** `tests/test_profile.py` already checks that general docs name no profile fact. A console test asserts that `src/jason/console/` names none either. It reuses `jason.community.boundary` terms, as the docs check does.

## Dependencies

What the console would add. **pyproject is not edited here**; this is the list for the build.

| Package | Why | Where |
|---|---|---|
| `starlette>=0.40` | The app. Already installed through `mcp`, but not declared | a new `console` extra |
| `uvicorn>=0.30` | The server. Already installed through `mcp` | `console` |
| `python-multipart>=0.0.9` | Starlette's form parsing (`await request.form()`). Already installed through `mcp` | `console` |
| `jinja2>=3.1` | Templates with autoescaping (pulls in `markupsafe`). **New** | `console` (an open decision: [mvp.md](mvp.md#open-decisions)) |
| `httpx>=0.27` | `TestClient`. Already installed through `mcp` | `dev` |

The extra:

```toml
console = [
    "starlette>=0.40",
    "uvicorn>=0.30",
    "python-multipart>=0.0.9",
    "jinja2>=3.1",
]
```

There are no new dependencies in phases 1 through 4 beyond this. Phase 5's passkeys would add a WebAuthn library (`webauthn`), decided then.
