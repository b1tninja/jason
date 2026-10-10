# One community on a machine, many in a portal: how jason behaves in each, and where they meet

Status: design (2026-10-10); **phase 1 built (2026-10-10), see [Phase 1: what was built](#phase-1-what-was-built)**. Nothing else in this page is built unless it says so. It settles how the command line (`jason`), the MCP server (`jason-mcp`), and `jason serve` behave when they serve **one** association, how the same code behaves as a **multi-tenant portal** for many, and what the two share. It builds on [profiles.md](profiles.md) (a profile is one association), [integrations-design.md](integrations-design.md) (the vault, instance and community integrations), [scheduler-daemon-design.md](scheduler-daemon-design.md) (the daemon and its leases), [deployment-research.md](deployment-research.md) (cells, volumes, the cost of each), [onboarding-ux.md](onboarding-ux.md) (the communities screen), and the console's [security-and-privacy.md](console/security-and-privacy.md) (roles, data levels, the private view). The examples use a made-up "Example Village HOA" (`example`).

## The idea in one line

**A community is the unit of isolation. Everything that holds its facts, its secrets, or its people's words belongs to exactly one community, and nothing crosses.** The single-community install is that unit running alone; the portal is many such units behind one front door, with a thin instance layer that holds only what is not any community's.

Three words are used with one meaning each:

| Word | Means | Where it lives |
|---|---|---|
| **community** | one association at run time: its profile, its data folder, its vault prefix, its schedules, its people | the profile package plus `<data root>/<key>/` |
| **instance** | one deployment of jason: the code, the shared read-only shelves, the operator's own accounts, and the list of communities it serves | the host or the container set |
| **tool set** | a named subset of MCP tools (`board`, `governance`, `onboarding`) | `jason.mcp.server.PROFILES` (called "profile" in the MCP flags; see [MCP](#4-mcp)) |

## 1. The two shapes

### (a) A single-community install

The CLI, `jason-mcp`, and optionally `jason serve` for one association, on one machine or in one container.

- **Which community.** `JASON_COMMUNITY` (or `--community`, [below](#3-the-cli); `JASON_PROFILE` is the old name and still works) names it. The data folder is `<JASON_DATA_DIR>` for the default profile or `<JASON_DATA_DIR>/<key>/` for any other ([profiles.md](profiles.md#each-profiles-data)); `PAYHOA_CATALOG` in `.env` may move it.
- **Credentials.** In that community's vault prefix (`jason/community/<key>/...`, [integrations-design.md](integrations-design.md#the-vault)), Keeper on a PC. The machine's own settings (scratch, caches, where the data lives) are in `~/.jason/.env`.
- **People.** The person at the terminal. Their name goes on a write as `--by NAME`; the audit log records the operating-system user beside it (`os:<user>`, `via: cli`). A signed-in console adds Google accounts for the board's officers.
- **No community picker.** There is nothing to pick. A command that cannot tell which community it serves stops and says so ([3](#3-the-cli)).
- **Supported explicitly.** This is the shape jason runs in today. What is new is saying so, testing that a second profile on the same disk is never touched, and printing which community a command is acting on.

### (b) The multi-tenant portal

One deployment serving many associations.

| Who | What they are | Where they act |
|---|---|---|
| **Instance operator** | runs the deployment: health, schedules' liveness, the vault's backend, the shared shelves, creating and suspending communities. Holds no office and sees no community's content | the instance screens |
| **Community administrator** | sets up one community: its integrations, its people, its schedules' cadences. Holds no office; approves nothing | that community's Setup |
| **Board member** (officer) | holds an office (`OfficerRole`) and approves what the roster says that office approves | that community's console |
| **Manager** | a person at a management company, with a **portfolio**: the communities they serve (`data/access/managers.json` today). Acts as the manager in each, signed in to each | each community in the portfolio |
| **Owner** | a member of the association; not staff | the page for their own unit only |

A person may hold different roles in different communities (a manager in three, a director in a fourth). A role is always **a role in one community**; there is no role that spans communities except the operator's, and that one reads no content.

### What is per instance and what is per community

| Thing | Per | Why |
|---|---|---|
| The code, the base templates, the form library packs, the law shelf (authorities), the county caches, the local models | **instance** (shared, read-only to communities; [6](#6-shared-things-that-are-not-tenant-data)) | public or generic; the same for every association |
| The vault's backend and the operator's own accounts (a model provider, the job host) | **instance** | the operator's, not a community's |
| The list of communities, their state, and the instance screens | **instance** | the operator manages them; the list carries names and states, never content |
| The profile (rule rows, identity, the association's facts) | **community** | [AGENTS.md](../AGENTS.md): one association is one profile |
| Private facts (`data/spec/<key>/...`) | **community** | people, accounts, counsel |
| The data folder: stores, caches, indexes, generated pages, audit and access logs | **community** | the association's records |
| Vault records: Google client and tokens, PayHOA login, Zoom app, portal logins, the sign-in client | **community** | one community's breach stays that community's |
| Schedules, the job queue (`jobs.db`), leases, locks that name an account | **community** | [scheduler-daemon-design.md](scheduler-daemon-design.md) |
| Sign-in (the Google client, the roster, sessions) | **community** (the operator and a manager's portfolio have an instance-level door, [5](#5-the-web-portal)) | each community's Workspace decides who is in |
| The private view window and the reveal log | **community** | a reason is given to one community's board |
| Local-model context, prompts, embeddings of the community's documents | **community** | see below |
| Backups and logs | **community** (an instance log holds no content) | see below |

### What must never be shared

Each of these is **one per community**, and a defect that shares one is a defect in jason, not a setting:

- **Data**: any store, file, or generated page under a community's folder.
- **Vault records and tokens**: a path under another community's prefix is a miss, even for the operator's code path. A refresh token saved for A is never read for B.
- **Caches and indexes**: the passage index, the library's classification, the OCR and extraction caches, the ownership database, the private-facts cache (already keyed by file path and modification time, `jason.community.private`), the rendered pages.
- **Locks**: a lock that guards an account or a store carries the community (`payhoa-<key>`, `jobs-worker-<key>`; built). A lock without a community is, by construction, a wait that crosses.
- **Local-model context**: no prompt, retrieved passage, conversation, or embedding of one community's documents is put into another's request, a shared "memory", or a shared prompt cache. The model server is shared compute and holds nothing between requests; every request builds its context from one community's index. A model job holds the GPU lock and runs as one community.
- **Logs**: every line names its community; an instance log carries no content, no owner's name, no address, no amount.
- **Backups**: one snapshot set per community; a restore of A never writes into B.
- **Temp**: scratch for a job is under a folder named for its community and removed with it.

## 2. Isolation model for the portal

### The two ways to isolate

| | **Process per community** (a cell) | **One process with a community context** |
|---|---|---|
| What a request carries | nothing: the process *is* the community (`JASON_PROFILE` and the data folder are set once at start) | a `CommunityContext` threaded to every call, or a context variable set per request |
| What stays valid as written | `community()`, `data_dir()`, `Settings.load()`, `lru_cache`d readers keyed by path, the profile loader, module-level caches, `tempfile.tempdir`, file locks keyed by name | none of them without audit |
| What must change | little: add a router in front, and a guard that a process refuses a community it was not started for | every call site that reads `JASON_PROFILE` (`profile_name()` reads the environment), every module-level cache and `lru_cache` that is not keyed by community, `tempfile.tempdir` (one global), `sys.modules["jason_<key>"]` (one profile package per name, so two communities need two names), `os.environ["JASON_PROFILE"] = ...` in `jason serve`, locks and stores that default their folder |
| Failure mode | a mis-routed request reaches the wrong *process*: the gateway's bug, and the wrong process has only its own data to give | a cached profile or index served to the wrong request; a task that reads another community's index because a default argument evaluated at import; a thread-local lost across an `await` or a worker thread; a background thread (the scheduler, a job) that keeps the *previous* request's community |
| Blast radius of a crash or a stuck job | one community | all |
| Memory | one interpreter per community (a few hundred MB; the deployment research puts a cell at about $14 to $30 a month before the load balancer) | one |
| GPU, OCR, Chromium | already separate processes or subprocesses (a job is a subprocess run as its community, `jason.jobs`); the GPU lock is shared across communities either way ([8](#8-operations)) | the same |

**Where the code is today.** It is process-global by design, and says so: `community()` returns the active profile, loaded once and cached by name (`jason.community.profile`); `profile_name()` reads `JASON_PROFILE` from the environment; settings, the data folder, and the temp folder are anchored by the process's configuration; `jason serve` sets `os.environ["JASON_PROFILE"]` for the web part and runs each profile's worker and scheduler as threads, and every job as a subprocess run *as its worker's community*. Locks and the worker guard are already keyed by community. The web serves exactly one community. About two dozen `lru_cache` uses and two dozen module-level mutable containers are the audit surface for the in-process alternative.

### Recommendation

**Process per community, with a gateway.** Each community is a small set of processes over its own volume: a web process, and a worker with its scheduler (`jason serve --community KEY`, split by `--no-web` / `--no-worker` as the scheduler design already allows). A **gateway** (a reverse proxy or a small router, no jason data) maps a request's host or path to the community's web process, and an **instance app** serves the operator's screens. Reasons:

- The code's invariant today is "one process, one community." Making that the *deployment's* invariant costs a router, not a rewrite, and the isolation is the operating system's (separate users, volumes, and environment) rather than a convention in 109 modules.
- The two ways fail differently. A cell fails *closed*: the wrong process has nothing of the other community's. The shared process fails *open*: it has everything and relies on every call keeping its context.
- It matches the other decisions already made: a Cloud project, a Web client, a vault prefix, a data volume with one writer, and a lease per community.
- It does not rule out the other. If cells prove too heavy (a hundred small communities on one box), one process may later serve several, **behind the same two-community test** ([phase 7](#9-phases)); the test, not the architecture, is what protects them.

**Guards even in a cell** (defence in depth, because a cell is still one bug from a wrong volume mount):
- **A jail.** `jason.tenancy.assert_inside(path)` (to write) is called where a store, a cache, or an index opens a file; it refuses a path that is not under the process's own data folder, the shared shelves' read-only mounts, or the temp folder for this community. The profile-data test already watches this with Python's audit events ([profiles.md](profiles.md#each-profiles-data)); the jail is the same check at run time.
- **An identity check at start.** A process started for `example` refuses to open a data folder whose recorded community key (a `community.json` stamp written at creation) or whose PayHOA org id differs. Phase 5 of [profiles.md](profiles.md#making-jason-reusable-the-phases) already lists "a check that a store's recorded org id matches the profile's."
- **One community per process, stated on `/api/health`.** The gateway checks the health answer's key before sending traffic.

### How to make the rule testable

The rule: **nothing one community owns appears in another community's answer, file list, log, or lock.** It is held by three checks that fail the build:

1. **The two-community test** (`tests/test_tenancy.py`, to write). It scaffolds two communities, `alpha` and `beta`, from `tests/fixtures/spec` over one data root, with a distinct *sentinel* in every store each reads (a library file, an ownership row, a job, a private-fact name, a vault fake's secret, a scratch file). It then:
   - runs **each read entry point** for `alpha`: every CLI command marked read-only, every web loader (`GET /api/*`), every MCP tool, one job of each lane; in the **same interpreter** first `alpha`, then `beta`, then `alpha` again, so a cache that remembers the first community shows;
   - asserts, through Python's audit events, that no file under `beta`'s folder is opened or listed, and nothing is created there;
   - asserts that no `beta` sentinel appears in any output or log line, and that the outputs equal those of separate processes (order does not matter);
   - repeats the writes (`--yes`, `--by`) against a temp copy and asserts `beta`'s files are byte-identical afterward;
   - holds `alpha`'s lock and asserts `beta`'s work is not blocked, and that `alpha`'s two jobs of one account are (the keys differ by community).
   The same test runs once more with the processes separate (the cell shape) and compares.
2. **The module-state lint** (`tests/test_no_module_state.py`, to write). An AST scan of `src/jason` that fails on: a module-level mutable container filled at run time; an `lru_cache`/`cache` on a function whose key does not include the community, the data folder, or a path under it; a write to `os.environ["JASON_PROFILE"]` outside the program-start path; an assignment to `tempfile.tempdir` outside `apply_temp_dir`; a `Path("data")`; and a default argument that calls `community()` or `data_dir()`. Existing uses are a ratchet in a baseline file (as `tests/fixtures/code_boundary.json` is): a new one fails, and a cleared one must be removed from the baseline. A cache that is *meant* to be shared (the law shelf's parsed text, keyed by a content digest) is declared once in the baseline as `shared: read-only`.
3. **The boundary test's role.** `tests/test_profile.py` and `python -m jason.community.boundary` keep one association's facts *out of the shared code and docs*. In a portal that is a security property, not a style rule: the image is the same for every community, so a fact in code or a general doc is shown to every tenant. The two-community test checks the *run-time* crossing; the boundary test checks the *static* one. A new profile's facts extend the boundary check automatically (the check reads the profile).

A fourth check is in the deployment: the gateway's smoke test signs in as a person of `alpha` and asks `beta`'s host for `GET /api/session`; it must be refused, and `alpha`'s cookie must not be sent to `beta`'s origin ([5](#5-the-web-portal)).

### Migration from today's code

| Step | Change | Proves |
|---|---|---|
| now | one process, one community; `jason serve --all` runs several workers beside one web | workers and jobs already isolate by community |
| phase 1 | the tests and the lint above, on today's code | a second profile on one disk crosses nothing, in one interpreter |
| phase 3 | `jason serve --community KEY` serves *only* KEY (web, worker, scheduler); `--all` is kept for a PC and still runs one web per community | the web is community-bound; a cookie is too |
| phase 4 | a gateway and an instance app | one front door, many cells |
| phase 7 | (optional) one process, many communities | only if the two-community test passes unchanged |

`os.environ["JASON_PROFILE"] = ...` in `jason serve` is the first thing the single-process portal would have to remove; in the cell shape it is correct as written.

## 3. The CLI

The CLI is the operator's and the manager's terminal. It is **one community per command**.

### How it picks the community

In this order, first one set wins, and `jason which` prints the winner and where it came from:

1. `--community KEY` on the command (`--profile` stays as an alias where it exists, `jason serve --profile` and `jason daemon --profile`);
2. the environment, `JASON_COMMUNITY`, else `JASON_PROFILE` (the same setting; `JASON_COMMUNITY` is the new spelling, `JASON_PROFILE` keeps working);
3. the project's `.env`;
4. the **current context**, if the person set one (below), in the user config `~/.jason/.env`;
5. the only profile this machine has, if there is exactly one, *and* a line on standard error saying so. **Built with one addition:** while the compatibility shim is on (the default), several installed profiles and no choice means the built-in default profile, with the same line ([phase 1](#phase-1-what-was-built)).

**None configured, or more than one could apply.** The command stops with exit code 2 before it reads a store or opens a connection:

```text
Error: no community chosen, and this machine has 2 (example, sample).
Choose one: jason --community example ...   or   jason use example
```

A command never guesses between two. A read-only command that needs no community (`jason which`, `jason communities`, `jason --help`, `jason cite`, `jason export-authorities`: the shared shelves) still runs.

Today `DEFAULT_PROFILE` is a built-in name in `jason.community.profile`, so "nothing configured" silently means one particular association. That default is replaced by step 5 above: it is a boundary smell (a fact in code) and the one place a second install could act on the wrong community without being told.

### Contexts: switching without mixing

An operator who runs several communities from one machine switches by a **named context**, as `kubectl` does, kept in the user config:

| Command | What it does |
|---|---|
| `jason communities` | lists the communities this machine can load, the current one marked (names and data folders; no content) |
| `jason use KEY` | sets the current context: writes `JASON_COMMUNITY=KEY` in `~/.jason/.env` (a person's act; it prints the file it changed) |
| `jason use --show` / `jason which` | prints the community, its data folder, the vault prefix, the user config, and where each came from |
| `JASON_COMMUNITY=KEY jason ...` | one shell, one community, without touching the file: the safest habit for a script |

**Rules that keep the data apart:**
- **Every command that writes** prints one line first, on standard error: `community: Example Village HOA (example), data C:\...\example`. A write run through a context set days ago shows which community it will change before it does.
- **A write across a changed context is refused in a script.** `--yes` with a context taken from the user config (not the flag, the environment, or the project) asks for `--community KEY` too when standard input is not a terminal. A person at a terminal sees the line and may proceed; a script must be explicit.
- **Built in phase 1:** the write line is printed for anything given `--yes` (and for a console or MCP write). The refusal of a script's `--yes` under a saved context is **not** built (open).
- **A job** carries its community in its row and runs as that community (built).
- **`--community` is on every command** that reads a store, a connection, or a vault; one that cannot honor it says so. A command that names two communities does not exist (a comparison across communities is not a feature; [the rule](#the-idea-in-one-line)).

### A remote portal or the local disk

Three kinds of work, and the CLI treats them differently:

| Kind | Examples | Runs where | Needs |
|---|---|---|---|
| **Local read** | `jason sop`, `jason cite`, `jason lessons`, `jason conflicts`, `jason audit` over the data on disk, `jason daemon status` | on the data folder it can open, no network | the folder |
| **Live read** | `jason sync-catalog`, `jason gmail --sync`, `jason integrations check --live` | the machine that holds the community's vault access | a credential (the community's vault prefix) |
| **Write** | anything with `--yes`, `jason owner-info --apply`, `jason mailroom --send` | the same, and only with `--by` | a credential, a name, and the approval engine's rules |

**Options for a CLI that is not on the portal's host:**
- **A. Local disk only.** The CLI reads and writes a data folder it can open. An operator logs in to the portal's host (or a mounted volume) and runs the same commands against the community's volume, which is how `jason` has always worked. No new surface.
- **B. A remote CLI.** `jason --remote https://example.jason.host/...` sends the command to the portal, which runs it as the authenticated person. One more API to secure, and every command is a route.
- **C. Read-only mirror.** A community's exported snapshot on a laptop for local reads.

**Recommended: A for now, and B only as a narrow, later step** (read-only tools first, authenticated by a personal token bound to one community and one person). The reasons: nearly every command already works on a folder, B doubles the surface to secure before any community needs it, and the web console is the remote interface for people who are not operators. If B is built, `by` is the token's person and a conflicting `--by` is refused ([attribution](#attribution-and-the-approvals-one--and-two-person-rules)).

### Attribution and the approvals' one- and two-person rules

| | Single-community CLI | Portal |
|---|---|---|
| **Who `by` is** | the name given with `--by` (required on every write), recorded with the operating-system user (`os:<user>`) and `via: cli` | the signed-in person's roster name, taken from the session (a client-supplied name that differs is refused), recorded with `via: console:google` and the Google subject |
| **What it proves** | a claim, labeled as one: on a shared machine a name is not an authentication | an authentication by the community's own Workspace sign-in |
| **A name that is not on the roster** | the engine refuses an empty name and a second person equal to the first; whether it refuses an unknown name is open ([security-and-privacy.md](console/security-and-privacy.md#without-sign-in-a-named-person-not-a-login)) | refused: the roster is the check |
| **Two-person kinds** | `confirm` takes a second, distinct name; the engine refuses the submitter and the requester | the second person must be a **second signed-in session** with a different subject; a name typed into the first person's session does not count |

**How the two-person rule works when the CLI is single-user.** The engine's rule (a second, distinct person signs the same fingerprint) is a rule about *names*, and a single user can type two. jason says so in what it prints: a CLI confirmation is recorded as `cli`, with the operating-system user, and the audit log shows both names came from one machine. The options for a community that wants more:

1. **Keep the claim, label it.** (Today.) Fine for a board that sits together and enters both names; the record is honest about how.
2. **Require the console for two-person kinds.** A community setting, `two_person_via = console`, makes `jason approvals confirm` refuse and point to the console, where the second person signs in as themselves. The setting is the board's decision and is recorded like any policy ("where the law is silent, write it down").
3. **A confirmation link** emailed to the second person's address on the roster, single use, which signs the same fingerprint when opened. More machinery.

**Recommended: 1 on a PC, 2 in the portal by default** (a portal has sign-in, so a claim is no longer the best available). The kind registry records which kinds are two-person; the community setting only decides where the second signature may be given.

## 4. MCP

`jason-mcp` is a stdio server over the stores on disk; it calls no PayHOA, Google, or Keeper ([mcp.md](mcp.md)). Its **tool sets** (`board`, `governance`, `onboarding`, and all) are not communities, and the flag that picks one is called `--profile` today, which collides with the profile that *is* a community. Going forward:

- **`--tools SET`** picks the tool set (`--profile SET` and `JASON_MCP_PROFILE` keep working as aliases and are described as the tool set; `--profile` prints a deprecation message). **Built.**
- **`--community KEY`** (or `JASON_COMMUNITY`) picks the community, by the CLI's precedence above. **Built.**

### One server per community

A client that serves several communities registers **one server per community**:

```json
{ "mcpServers": {
    "jason-example-board":      { "command": "jason-mcp", "args": ["--community", "example", "--tools", "board"] },
    "jason-sample-board":       { "command": "jason-mcp", "args": ["--community", "sample",  "--tools", "board"] } } }
```

- **The server's name carries the community** (`jason-example`), and its `instructions` begin: "Community: example. This server answers for Example Village HOA only." **Built.** Every tool's result carries `community: "example"` at its top, so a pasted answer says whose it is (**not built**: phase 2).
- **No `community` argument on any tool.** A tool that took one would let a model, or a prompt hidden in a document, ask for the other community by naming it. The community is fixed when the server starts, by the person who configured the client. **Never both:** a server does not have an argument *and* a configured community, and one that does is rejected by a test (`tests/test_tenancy.py::test_no_mcp_tool_takes_a_community`, built).
- **A caller cannot cross.** There is no tool that lists, names, or opens another community. `jason://` addresses resolve inside the started community only.
- **Caveats repeat**, as they do now ("Each tool carries its caveats. Repeat them"): a confidential file is held back unless asked; a reading or a hit is evidence, not a pin; an answer that quotes is checked with `verify_quotes` first. A multi-community client adds one more, said once in the server's instructions: *the answer is for this community; do not carry a fact from one server to another's.*
- **Writes need `by`.** The three tools that write a person's record to `data/` refuse a call without `by`. On a local server `by` is a claim, labeled as in [3](#attribution-and-the-approvals-one--and-two-person-rules). On a hosted server `by` comes from the token and a conflicting value is refused.
- **What an AI client must never be able to do:** read or write outside its community; write without `by`; approve, deny, or assign (the tools decide nothing); read a secret (P4 is never served); open the private view or a confidential file without the stated reason; run a command that changes a connection.

### Hosted MCP

A hosted community serves MCP over HTTP at its own origin (`https://example.jason.host/mcp`). The bearer token is **issued to one person for one community**, carries that person's roster role and data levels (a board token never opens what the manager's role does not), and expires. The server applies the same `SEE_RULES` the console does. A personal token is revocable from the community's People screen.

### The operator's MCP

A separate server, `jason-mcp --instance`, for the operator: `instance_health` (each community's service state and heartbeat age), `instance_schedules` (cadences and next runs), `jobs_status` by community (counts, not payloads), `vault_status` (names set or not, never a value), `shelves_status` (versions of the shared shelves). It has **no tool that reads a community's content** and no community argument; it can say that `example` has a stale heartbeat, not what `example`'s library holds. The operator reaches content only by being given a role in a community, and that is logged in that community ([5](#5-the-web-portal)).

## 5. The web portal

### The URL scheme

| Option | Looks like | For | Against |
|---|---|---|---|
| **Subdomain per community** | `https://example.jason.host/#/decisions` | one origin per community: the browser keeps cookies, `localStorage`, service workers, and CSP apart for free; a community can use its own domain later; the Google redirect URI is exact per community, as each community's own Cloud project needs | wildcard DNS and certificate; local development needs a hosts entry |
| **Path prefix** | `https://jason.host/c/example/#/decisions` | one certificate; simple to host | one origin: a session cookie, `localStorage` (`jason-console-user` today), and scripts are shared across every community, so a script flaw in one reaches the others |

**Recommended: a subdomain per community**, with hash routes unchanged (`#/<screen>`, so a shared link lands on the same screen). The fallback, if a wildcard certificate is not available, is the path prefix with the isolation rebuilt by hand: a cookie named and `Path`-scoped for the community, every `localStorage` key prefixed, and a strict CSP; it is more to get wrong. One callback path (`/auth/<provider>/callback`) serves every community because the community travels in the server-side `state` ([integrations-design.md](integrations-design.md#the-vault)); with a subdomain, the callback is on the community's own origin, which is the redirect URI the community registered.

### Roles per community: the console's roles, mapped

The console's roles are today per installation: `data/access/admins.json`, `data/access/managers.json`, and the officers in the profile's private facts. In the portal:

| Today (per installation) | In the portal |
|---|---|
| **Officer** (`OfficerRole`, from `Community.officers()`) | unchanged: a community's own roster, in its private facts |
| **Manager** with a portfolio (`managers.json`) | a **portfolio** at the instance (the communities a manager serves), and a per-community **manager** row in each. The portfolio decides what the switcher offers; the community's roster decides what the person may do there |
| **Admin** (`admins.json`: jason's overall administrators, no office, the roster row only) | split in two: **instance operator** (instance screens; no community content) and **community administrator** (that community's Setup and integrations; no office; approves nothing) |
| **Owner** | no console role today; see below |

Sign-in is not a role, in either shape.

### Sign-in: the community's, and the instance's

- **A community signs in with its own Google client**, from its own Workspace, in its own Cloud project (decided; [integrations-design.md](integrations-design.md#google-workspace)). The roster is that community's. A person in two communities signs in to each, separately: **there is no single session that spans communities.** A session is bound to the community and to the account's Google subject, as the private view already is.
- **The instance has its own client** (`jason.access`) for the operator and for a management company's Workspace, as one may be added today. It signs in people for the **instance door only**: the operator's screens and a manager's switcher.
- **Moving between communities.** A manager in the portfolio opens the switcher at the instance door, which lists the communities in their portfolio (names and states only). Choosing one does a one-time, signed redirect into that community's origin, where the community's roster is checked *again* against the manager's address and a community-bound session is created. The instance door's session is never accepted by a community, and a community's session is never accepted by another. A person who is on two communities' rosters but in no portfolio signs in to each at its own address, and a personal bookmark is the switcher.
- **A person taken off one roster** is signed out of that community at their next write, as now, and nothing else changes.

### The operator's screens, and a community's own

The instance screens ([handoff-instance-and-integrations.md](console/handoff-instance-and-integrations.md)) are the operator's, served by the instance app:

| Instance (operator) | A community's own |
|---|---|
| Status of the service: each community's heartbeat, lease, lanes, next runs, recent failures | Status and Setup for that community's sources and integrations |
| Communities: each community's state, data size, last activity, integration chips; create, suspend | the community's own card, only |
| Integrations of the instance: the vault's backend, shelves, models, the instance sign-in client | Setup → Integrations: that community's connections, set up by its administrators |
| Schedules, all communities' in one table (cadence, floor, window), read-only | that community's cadences, changed by its administrator with `--by` |
| People: the operator and the portfolios | People: that community's officers, admins, managers |

The operator **sees names, states, sizes, and ages, never content**: no screen of the instance renders a document, a unit, a person's contact, or an amount. Today's `#/communities` lists every profile this checkout can load and acts on the active one; in the portal that list is the *operator's*, and a community administrator or officer sees their own community only. A hash route such as `#/communities` inside a community is that community's card.

**Support access.** The operator needs a way in when a community asks for help. Recommended: **break-glass, by the community's request**: a community administrator grants the operator a named, time-limited role in their community (a day), which appears in that community's roster and log and ends by itself. No standing access.

### The private view and the reveal log

Both stay in the community's data folder (`access/private.jsonl`, `access/served.jsonl`; [security-and-privacy.md](console/security-and-privacy.md)). The private view window is bound to the community and to the account's subject. A reveal (a proposed `MaskedField` reading of a masked P2 value) is logged there. The operator cannot open a community's private view without the grant above, and opening it as a granted role is a line in that community's log.

### An owner sees only their unit's page

An owner is not on any roster and holds no office. Today an owner cannot open a console page; the owner's view (`?view=owner`) is the manager's preview of what an owner is shown, and what an owner receives arrives through PayHOA's portal and thread. In the portal:

- **The owner's page is a different surface from the console.** It is a separate route tree in the community's origin (`/unit/...`), built from a small set of loaders that take the unit from the **session**, never from a query parameter: the server answers "your unit," and a request for another unit is a 404 the server decides, not a hidden button.
- **Sign-in for an owner** is a choice for the user (open decision): (a) none, and owners keep PayHOA's portal as the owners' system, with jason producing what PayHOA delivers; (b) a **single-use link** emailed to the address on file in PayHOA, scoped to the unit, short-lived; (c) a Google account for owners who have one, matched to the address on file. Recommended: **(a) now, (b) when the board decides it wants an owner page in jason**, since an owner sign-in is a new credential holder for the association's most personal data and the association's owner records are PayHOA's.
- **What an owner sees** is P0 and their own unit's P1/P2, nothing about any other unit, and no staff-only data level, whatever the unit's page shows.

## 6. Shared things that are not tenant data

Some data is public or generic, large, and the same for every association. It is held **once per instance**, mounted **read-only** into every community's process, and **versioned**:

| Shelf | What | Why it is shared |
|---|---|---|
| **The law shelf** (authorities) | statutes' text and versions, readings of the Act, the form library's statutes | public law; a copy per community is waste and a drift |
| **Form library packs** | the generic forms and their model readings | generic |
| **County caches** (asspy, `ASSPY_HOME`) | recorder and assessor indexes of public records | public records. A community's *questions* are not shared: which parcels it looked up is in its own log, never in the cache |
| **Local models** | model files and the model server | compute and weights; no context is retained between requests |
| **Base templates** | notices, letters, forms, packets | written once ([AGENTS.md](../AGENTS.md)) |

**Rules:**
- **Read-only to a community.** A community's process mounts the shelves read-only; a community's job never writes to one. The shelves are updated by the operator's job (`jason export-authorities`, a pack release), as an instance act, never as a side effect of a community's request.
- **Versioned.** Each shelf has a version and a content digest. A community's record of use names the version it read (a quote check already carries a digest, and `as_of` reads the version in force). An update is announced to communities as a change, with its date; a community's `as_of` readings keep their version.
- **A community overrides through its profile, never by copying.** A community's rule rows, identity, letterhead, and template variables are *applied over* a shelf's base at read time (`classify_document`'s kind rules, `DocumentTemplate`, the form library's resolve tiers). A community never has its own edited copy of a base template or a statute; a community-specific copy is *generated* from the base, as AGENTS.md already requires.
- **Nothing flows back.** A community's confidential extraction, a private fact, or a classification result does not enter a shared cache. The shared caches are keyed by public content (a statute's digest, a recording number), not by who asked.

## 7. Onboarding and lifecycle

### Creating a community

Today `jason onboard --new KEY --name NAME` writes a profile package from the general templates (a `Community` subclass with the identity, empty rule-row modules, `docs/`, an ignored `notes/`) and empty private facts in `data/spec/KEY.json`, and never overwrites ([onboarding.md](onboarding.md#starting-a-new-association)). The portal adds what a *deployment* needs around it:

| Step | Who | What | Today |
|---|---|---|---|
| 1. Create | operator | `jason community create KEY --name NAME` (the console's "Set up a new community" calls the same): the profile package, the data folder with its `community.json` identity stamp, empty private facts, an empty vault prefix `jason/community/KEY/`, a subdomain, a cell | `onboard --new` writes the profile and private facts only |
| 2. First administrator | operator, then the community | the operator names **one person** (an address at the community's Workspace); that person receives an invitation to sign in at the community's origin, and from then on adds the other administrators and officers | none |
| 3. Google | the community's administrator | creates the Cloud project in the community's own Workspace, the Internal app, the Web client, puts the client in the vault, signs in the account jason uses ([integrations-design.md](integrations-design.md#google-workspace)) | the guide in [setup.md](setup.md); built for console sign-in |
| 4. PayHOA, Zoom, utilities | the community's administrator | the community's *own* accounts into the vault (`jason integrations import ...`, or a write-only field when hosted), the PayHOA organization id, a check ([integrations-design.md](integrations-design.md#the-integrations)) | per installation until `jason vault migrate` is run |
| 5. Facts | the manager and the board | the onboarding session (`#/onboarding`): the request list, answers, gaps | built |

**Never the operator's development records.** A new community's vault holds only what its administrators put there. A development install's PayHOA login, Google client, and portal logins (the repository's `.env` record ids) are not copied into a hosted community, and a hosted community's code path has no fallback to a record id in `.env`. The vault interface rejects a path outside the community's prefix.

**A profile is code.** A community's rule rows are Python in a `Community` subclass today. The portal does not let a tenant upload Python. Options (open decision): (a) **managed profiles**: the operator reviews and deploys a profile package per community (an entry point or `JASON_PROFILE_DIR` on the community's own volume), while community administrators change only data (private facts, onboarding answers, connections, registers, cadences); (b) **data profiles**: rule rows move to data a community edits ([profiles.md](profiles.md) phases 2 to 7 point that way); (c) both. Recommended: **(a) now**, since it keeps jason's rule that a profile is reviewed, and the self-serve path waits for (b).

### Suspending

An operator or the community's administrator suspends a community: its worker and scheduler **drain** (the lanes finish their job and stop, `jason daemon stop`), its schedules are paused with the reason, the web goes to a read-only banner for administrators and officers (and the owner page says the association is not available), new sessions are refused, and the data and the vault are untouched. Resuming reverses it. The suspension, who, and why are lines in the community's log and the instance's list.

### Exporting: a community leaves

A community's administrator exports with `jason community export KEY --by NAME`:

- **The data**: the whole data folder, the private facts, the profile package, the audit chains, the access logs, and the schedules, as one archive with a manifest of files and digests, written to a place the administrator names. The archive restores into a single-community install ([1](#1-the-two-shapes)).
- **The vault records**: a community's secrets are its own. Two ways, chosen by the administrator: **(i) by reconnection**: the export lists each connection (integration, account label, capabilities, state) and no value; the community puts its own credentials into its new vault (its Google client is in its own Cloud project, its PayHOA login is its own, a refresh token is re-issued by signing in), and the old tokens are revoked at the provider on request; **(ii) an encrypted secrets bundle**, `--secrets`, encrypted to a passphrase the administrator supplies at that moment, never to a key the operator holds, and logged. Recommended: **(i) by default**, since a token should not be carried when it can be re-issued; (ii) only when the administrator asks.
- **The operator cannot export a community's secrets without the community's administrator** (the vault prefix is read through the community's connections, and the export command requires that administrator's `--by`).

### Deleting

Deletion is **two steps with a pause**: suspend, an export confirmed received, a retention period the operator states (for example thirty days), then `jason community delete KEY --yes` by the operator **and** a community administrator's confirmation. It then: revokes the community's tokens at the providers, deletes the vault prefix and its versions, removes the data volume and the community's temp and index folders, removes the community from the gateway, and records that it did so (the instance list keeps a stub: key, name, dates, no content). Backups of the community age out on the stated schedule, and the operator says when that is. What the association must keep of its own records is a duty of the association, not of jason's copy; the export is the safeguard, and the board is told to keep it (the law on those duties is read with `jason cite`, not stated here).

## 8. Operations

### The daemon: per community, or one with lanes

[scheduler-daemon-design.md](scheduler-daemon-design.md) makes `jason serve` one process with three parts (web, worker, scheduler), a lease per community, and `jason serve --all` for several. For the portal:

- **Recommended: a worker-and-scheduler process per community, and a web process per community**, as cells, from one image. The lease and the guard are already keyed by community (`jobs-worker-<key>`). A crash, a stuck job, or an auth failure that pauses a source is one community's.
- **The lanes are per community** (GPU, GOOGLE, PAYHOA, COUNTY, LOCAL); the service locks are per account (`GOOGLE:<key>`, `PAYHOA:<key>`), so two communities never wait on each other for an account.
- **One thing is shared compute: the GPU.** The GPU lock is per machine, not per community. Today it is first-come: one community's long model pass can keep the rest waiting. **Fair share**: the lock hands to the community that has waited longest since its last turn (a ticket per community, the last served time), and a job states its expected length so a long pass is split into resumable batches. A community's model job never starves because another queued first. With a hosted model (the optional Bedrock reader) the shared resource is a rate limit instead, with the same ordering.
- **One Keeper session per community per process**, opened lazily, shared by every user in the process, closed at exit or when idle, and refused for any other community ([integrations-design.md](integrations-design.md#one-keeper-session-per-community-per-process)).
- **Heavy work stays out of the web process** (OCR, Chromium captures, model calls are jobs).

`jason serve --all` stays for a PC that serves a few communities beside one another; it is the same code with the cells in one parent, and it keeps the web per community (a different port each).

### Storage and temp

- **A volume per community**, local disk, one writer (SQLite's WAL does not work over a network file system; [deployment-research.md](deployment-research.md)).
- **`JASON_TEMP_DIR`** names the drive; each community's scratch is `<temp>/<key>/`, created with the job and removed with it, and `jason storage --check` reports it per community. A short drive or commit stops model jobs for **all** communities on that machine, and says why.
- **Quotas.** A per-community data size and temp size warning (the operator's Communities screen shows size) rather than a hard stop; a hard stop on one community's quota never stops another.
- **The shared shelves** are on their own read-only volume.

### Backups

- A snapshot set **per community** (daily; the store lock is held while a database is copied, or the copy is made by SQLite's backup API), with the retention stated, kept apart from every other community's.
- **A restore writes only into the community it names** and is tested the same way as everything else ([2](#2-isolation-model-for-the-portal)): restore `alpha`, compare `beta`'s digests.
- The vault is backed up by its backend's own mechanism, per community prefix.

### Logging

Every log line, job log, and scheduler decision is JSON with `community`, `at`, `component`, and (for a request) `request_id` and the signed-in person's roster name; **never** a document's text, an owner's name, an address, an amount, or a secret (the audit log already masks emails, phones, and addresses). Logs are written under the community's folder; the instance's own log holds service events only. A shipped log carries the community key, so an operator filters by it and a community can be given only its own.

### Cost attribution

- **Model calls**: each call's tokens, model, and seconds are recorded in the community's `cost.jsonl` by the job that made it; a hosted-model call carries a community tag (a cost-allocation tag or a separate provider key per community where the provider supports it).
- **Mailroom postage**: PayHOA's Mailroom charges the association's own PayHOA account (USPS through Lob), so it is already the community's. jason records each sending's pages and the price it showed (`data/mailroom/sent.jsonl`) and the instance sums nothing from it that is not its own.
- **Compute and storage**: cells and volumes tag by community; the instance screen shows size per community.
- **The operator's invoice to a community** is a policy between the operator and the community, not a jason feature; jason only keeps the counts true.

## 9. Phases

Each phase is small, and each says what it proves.

| # | Phase | What changes | What it proves |
|---|---|---|---|
| 1 | **Single-community is explicit, and isolation is tested (built 2026-10-10; see [what was built](#phase-1-what-was-built))** | `jason which`, `jason communities`; the community choice and its refusal when none or several; `--community` on every command that reads a store (alias `--profile` kept); the `DEFAULT_PROFILE` built-in replaced by "the one installed profile"; `tests/test_tenancy.py` (the two-community test, same interpreter, then separate); the module-state lint with its baseline; the jail (`assert_inside`) at store open | a second profile on one disk crosses nothing, and no new module state can be added unnoticed |
| 2 | **Contexts and an MCP that names its community** | (`jason use`, the write line, `jason-mcp --community` and `--tools`, the server name and instructions, and the no-`community`-argument test came in phase 1); what remains: the result `community` key, and the script refusal | one operator, many communities, and a model cannot reach across |
| 3 | **A community-bound web** | `jason serve --community KEY` serves only KEY; session and cookie bound to the community; `/api/health` states the key; `/api/communities` filtered by who may see it | two web processes on two ports, one cookie jar, no session accepted by the other |
| 4 | **A gateway and the instance app** | the router (subdomain per community), the instance door and its sign-in client, the manager's switcher and the signed exchange; the roster split (operator, community administrator); instance MCP | one front door; the operator sees states and no content; a portfolio manager moves between communities with a fresh, community-bound session each time |
| 5 | **Hosted foundations** | a vault backend with a policy per community prefix; a volume per community; the identity stamp check at start; backups and restore per community; logging with the community in every line; the fair-share GPU lock; `cost.jsonl` | a restore, a lock, a vault read, and a log line each stay in their community |
| 6 | **Lifecycle** | `jason community create / suspend / export / delete`; the first-administrator invitation; the community administrator's setup screens; break-glass access | a community can be added and leave with its data and its connections, and the vault prefix is gone after |
| 7 | **(Optional) one process, many communities** | replace the process-global `JASON_PROFILE`, profile package names, `tempfile.tempdir`, and each baseline entry in the lint with a `CommunityContext` | the same two-community test, unchanged, still passes |
| 8 | **The owner's page** | the unit-scoped route tree and its sign-in, if the board wants it | an owner reaches their unit and nothing else |

Phases 1 and 2 are useful on one PC with no portal. Phases 3 to 6 are what a hosted deployment needs. Nothing in 1 to 6 changes a store's format.

## Phase 1: what was built

Single-community is the explicit, tested mode of the CLI and `jason-mcp`, and a second community on the same disk is shown to cross nothing.

**One resolver.** `jason.community.profile.resolve_community()` is pure (it reads the environment and the two `.env` files and loads no profile) and returns the name and where it came from. `profile_name()` and `community()` use it; their signatures are unchanged. Precedence, first set wins:

| # | Source | Reported as |
|---|---|---|
| 1 | the global `--community KEY` flag, before the subcommand (`jason --community KEY SUBCOMMAND ...`; it sets `JASON_COMMUNITY` and `JASON_COMMUNITY_VIA` for the process and what it starts) | `--community flag` |
| 2 | `JASON_COMMUNITY` in the environment | `JASON_COMMUNITY` |
| 3 | `JASON_PROFILE` in the environment (the old name; noted once on standard error) | `JASON_PROFILE (old name)` |
| 4 | the project's `.env`: `JASON_COMMUNITY`, then `JASON_PROFILE` | `project .env, ...` |
| 5 | the user config `~/.jason/.env` (`JASON_CONFIG`): `JASON_COMMUNITY`, then `JASON_PROFILE` | `user config, ...` |
| 6 | the shim: the only installed profile, else the built-in default unless `JASON_DEFAULT_COMMUNITY_SHIM=0` | `the only installed profile`, `built-in default` |

With nothing chosen and the shim off, `CommunityNotChosen` stops the command with exit code 2 and the message of [section 3](#3-the-cli); a data folder is never guessed either (`default_data_dir` and `private.profile_of` re-raise it). Commands that need no community (`jason use`, `jason which`, `jason communities`, `--help`) still run: building the parser no longer needs the profile.

**Commands.** `jason use` shows the community and its source. `jason use KEY` writes `JASON_COMMUNITY=KEY` to the user config (`jason.config.set_user_config_value`, which keeps every other line), prints `wrote JASON_COMMUNITY=KEY to PATH`, refuses a profile that is not installed (exit 2), and says when a nearer source still wins. `jason use --list` and `jason communities` list the installed profiles with the current one marked. `jason which` is `jason use` without a key.

**The write line.** Anything given `--yes` prints first, on standard error, `community: KEY (from SOURCE); data: PATH`. The CLI does it once in `cli.main` (`jason.tenancy.write_banner`), the console in `jason.web.guard` for every write that passes the guard, and the three MCP tools that write a person's record before they write. A write with no community chosen stops before it runs.

**MCP.** The server is named `jason-KEY` and its instructions begin `Community: KEY.`. `--tools board|governance|onboarding` picks the tool set; `--profile` and `JASON_MCP_PROFILE` stay as aliases (`--profile` prints a deprecation message); `--community KEY` picks the community. No tool takes a community (tested over `ALL_TOOLS`).

**The isolation test** (`tests/test_tenancy.py`, `tests/tenancy_support.py`). Two throwaway profiles carry a sentinel in the private facts, the PayHOA catalog, the classified library, an outline, the intake questions, a job, and a file in each folder jason writes to. Fourteen public reads (the profile, lessons, private facts, settings, the catalog search, the library, the outline, intake, jobs, the data listing, lock names, and three console loaders) run alpha, beta, alpha in one interpreter, then as separate processes. The test also checks, by Python's audit events, that serving one community opens no file of the other, that one community's lock does not block the other's, and that the harness finds a deliberate leak and names the module. **Result today: none of those reads crosses.** What phase 2 must still change is what the reads cannot show: the list `process_global` in `tests/fixtures/tenancy_state.json` (the community as a process setting, `.env` values applied to every community, the one scratch folder, the shared access folder, the shared lock folder). A read that crosses later is listed under `crosses` there with its module; a new one fails the test, and one that stops crossing must be removed.

**The module-state lint** (`jason.community.tenancy_state`, run by the same test file). It reads the syntax of `src/jason` for module-level mutable containers, `global` singletons, caches whose key holds no profile or path, writes to the settings that name the community, `Path("data")`, and default arguments that ask for the community. The ones that exist are in `tests/fixtures/tenancy_state.json` with a status (`keyed`, `shared`, `program-start`) and a one-line reason; a new one fails the test, and a cleared one must be removed (`python -m jason.community.tenancy_state --update`). None is `process-global`.

**Decided in phase 1.** (a) The compatibility shim stays: this PC's installation depends on the built-in default, so a missing choice prints one line on standard error per run and `JASON_DEFAULT_COMMUNITY_SHIM=0` turns the default off. (b) The data folder layout is unchanged: the built-in default's folder is still `<data root>/`, any other's `<data root>/<key>/` ([profiles.md](profiles.md#each-profiles-data)). (c) `jason use` is a person's command with no `--yes`: it prints exactly what it wrote. (d) The jail (`assert_inside`) is not part of phase 1. The flag is global, so every command honors it, but a subcommand's own `--community` or `--profile` (`jason cadence`, `jason vault`, `jason serve`) keeps its meaning.

## Limits per instance and per community

Capacity, cost, and safety limits (an upload's size, a job's pages, a mailing's ceiling) are layered: the code's default and bounds, the instance's value and ceiling, then the community's value inside that ceiling. Each layer is stored apart (the instance's in the user config home, a community's in its own data folder), changed only by a person with a reason, and audited. One community's limits never change another's. The design is in [instance-limits.md](instance-limits.md).

## Axioms this keeps

- **Nothing crosses a community.** The test, the lint, the jail, and the cell are four ways of holding it.
- **jason proposes; a person acts.** A write carries `by`; in the portal `by` is the signed-in person, and the two-person rule needs two sessions.
- **Facts are data, in the profile.** A community's facts are not in the image; the boundary test is what keeps a shared image from carrying one tenant's facts to another.
- **No secret in a document, a log, a URL, or the operator's screens.** The operator sees "set or not set."
- **A missing fact is a miss.** A command with no community chosen stops; it does not pick one.

## Open decisions (for the user)

1. **Process per community, or one process for all.** Recommended: per community, with a gateway; one process later only if the two-community test passes unchanged.
2. **The URL scheme.** Recommended: a subdomain per community (needs a wildcard certificate); path prefix as the fallback.
3. **The CLI's context.** `jason use` writing the user config, with the stderr line on every write; or an environment-only choice with no saved context. **Built as recommended** (both exist: the saved context, and `JASON_COMMUNITY=KEY jason ...` for one shell).
4. **A CLI against a remote portal.** Recommended: local disk only for now; a narrow, read-only remote later.
5. **Two-person kinds in the portal.** Recommended: the second signature only from a second signed-in session, as the board's recorded policy; on a PC a labeled claim.
6. **The operator's access to a community.** Recommended: no standing access; break-glass by the community's grant, time-limited and logged.
7. **A manager's portfolio.** Recommended: an instance-level list that decides what the switcher shows, with the community's own roster deciding what the manager may do there.
8. **Profiles in a portal.** Managed (the operator deploys reviewed code) now; data profiles later.
9. **The owner's page.** Whether it exists in jason, and its sign-in: none, a single-use link, or Google.
10. **Exports and secrets.** Recommended: reconnect by default; an encrypted bundle only on the administrator's request; the retention period before deletion.
11. **The fair-share rule** for the GPU, and whether a community may buy a lane of its own.
12. **Whether the default profile built into the code may stay** for the existing PC install during phase 1 (a compatibility shim with a warning) or is removed at once. **Decided in phase 1 (for the user to confirm): it stays as a shim.** A missing choice is made visible (a line on standard error each run) and `JASON_DEFAULT_COMMUNITY_SHIM=0` turns it off. When to remove it is open.

## Not part of this pass

- Code: `jason community ...`, the jail (`jason.tenancy.assert_inside`), the gateway, and the instance app are named here and not built. Phase 1's code is `jason.tenancy`, `jason.community.profile.resolve_community`, `jason.commands.use`, `jason.community.tenancy_state`, `tests/test_tenancy.py`, and `tests/test_community_choice.py`.
- The vault backend for a hosted deployment, the choice of the host, and prices ([credential-store-research.md](credential-store-research.md), [deployment-research.md](deployment-research.md)).
- A billing system between the operator and a community.
- Moving the stores off SQLite.
- Legal terms between an operator and an association (a contract, data-processing terms, retention duties): a matter for the association's counsel, not for jason.
