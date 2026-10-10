# Configurable limits: what an operator and an administrator may change, and what they may not

Status: design (2026-10-10), **phases 1 and 2 built** (the registry and resolver, the write path and the trail: `src/jason/limits.py`, `jason limits`; [the decisions taken](#decisions-taken-in-phases-1-and-2) are at the end). Phase 3 is built for the first three keys (`upload.max_bytes`, `fetch.max_bytes`, `split.auto_read`), the temp-drive guard stands at the upload point, and the **backend** of phases 4 and 5 is built: the two console sources and the one console writer (`jason.web.extra.limits_view`), the read-only MCP tool `limits`, and the per-act override. The console **screens** are built (`ui/src/views/LimitsView.tsx`; [screens/limits.md](console/screens/limits.md)); the retention sweeper (6), and the portal's per-community view (7) are not built; [what was taken](#decisions-taken-in-phases-3-to-5-backend) is below. It settles how jason's limits (an upload's size, a job's pages, a mailing's ceiling) are named, layered, stored, changed, shown, enforced, and audited, for one association on one machine and for many in a portal. It builds on [tenancy.md](tenancy.md) (a community is the unit of isolation; the instance is what is not any community's), [setup.md](setup.md) (the machine's settings and the user config), [record-intake.md](record-intake.md) (the first limits: an upload's size and the automatic read of a split), [integrations-design.md](integrations-design.md) (the vault and the rate floors), [scheduler-daemon-design.md](scheduler-daemon-design.md) (lanes, the worker, cadences and their floors), and the console's [instance and integrations handoff](console/handoff-instance-and-integrations.md) and [security-and-privacy.md](console/security-and-privacy.md). Examples use made-up keys and a made-up "Example Village HOA" (`example`).

**What was built first.** (Now grown into phases 1 and 2; see the status line.) A sibling change added `jason.limits`: a registry of limit records (key, default, minimum, maximum, unit, description), `effective(settings)` returning a value and its source (`default`, `env`, `instance`, `community`), the first two limits (`upload.max_bytes`, default 100 MB; `split.auto_read`, default on), and a read-only `jason limits`. This page is the design that registry grows into. Where the two differ, the registry's code wins until this page's phase 1 lands, and the difference is recorded here.

## The idea in one line

**A limit is a number or a switch with a reason, a floor, and a ceiling; the code sets the default and the outer bounds, the operator narrows them for an installation, a community's administrator narrows them again for itself, and a person with a reason may go past a limit once, never past its ceiling.** Every layer can tighten. A layer can loosen only inside the bounds the layer above it left open. Nothing a person changes can switch a safety limit off.

## 1. What a limit is

A **limit** is a named, bounded setting that decides how much of a resource jason may use for one act, in one place, in one period. It is not a rule of the association (that is a rule row in the profile), not a policy the board adopts (that is a written policy), and not a secret (that is the vault). It is the operator's and the administrator's dial for **capacity, cost, and safety**.

### The record

Each limit is one row in the registry in code (`jason.limits.LIMITS`), the same way a cadence or an integration is a row, never a function with a number inside it:

| Field | Meaning |
|---|---|
| `key` | dotted, stable, lower case: `upload.max_bytes`. A key is never reused for a different meaning; a renamed limit keeps its old key as an alias |
| `kind` | one of the kinds below; decides how the value is typed, compared, and shown |
| `unit` | `bytes`, `count`, `per_hour`, `seconds`, `days`, `cents`, `switch` |
| `default` | what the code uses when nothing else is set |
| `minimum`, `maximum` | the **hard bounds**: the lowest and highest value any layer may set. Code, reviewed. A value outside them is refused at the point it is set and clamped (with a log line) if it is read from a file |
| `direction` | `either`, or `lower_only` (a limit that may be tightened below its default but never raised above it; the safety limits below) |
| `scopes` | which layers may set it: `instance`, `community`, both, or neither (a limit that only the code sets) |
| `override` | whether a person may pass it once, with a reason, and by how much (below) |
| `why` | one plain sentence: why the limit exists |
| `when_hit` | the wording a person sees at the refusal, and what they can do |
| `applies_to` | the enforcement points that read it (documentation only; a test checks each is real) |
| `restart` | `none`, `next_job`, or `next_start`: when a change takes effect |

A limit with no `why` and no `when_hit` does not load.

### The kinds

| Kind | Unit | Examples (illustrative keys) | A bound that matters |
|---|---|---|---|
| **size** | bytes | `upload.max_bytes` (default 100 MB), `export.max_bytes`, `fetch.max_bytes` (one download from a provider), `packet.max_pages` (as a count) | the web server's own request ceiling and the data volume's free space bound it; the maximum is never above what the host can hold |
| **count** | count | `ocr.pages_per_job`, `split.max_parts`, `batch.max_items` (one confirm or one apply), `jobs.queue_depth` (queued jobs per community) | a count that guards a write (`batch.max_items`) has a low maximum |
| **rate** | per hour | `drive.reads_per_hour`, `gmail.reads_per_hour`, `county.requests_per_hour`, `web.requests_per_minute` (per signed-in person) | never above the provider's published or polite rate; the same floors [the scheduler](scheduler-daemon-design.md) uses for cadences. A rate limit and a cadence floor are one number, kept in one place |
| **time** | seconds, days | `vault.session_idle_seconds`, `session.idle_minutes`, `job.timeout_seconds`, `retention.fetched_copies_days`, `retention.temp_days` | a retention has a **minimum** (what a duty to keep requires is read with `jason cite`, not stated here) as well as a maximum; a timeout has a maximum so a stuck job ends |
| **concurrency** | count | `models.concurrent_jobs`, `lane.<name>.concurrent`, `ocr.concurrent_jobs` | the GPU lock is one per machine ([6](#6-enforcement-and-how-a-refusal-is-told)); a concurrency limit narrows the queue, never the lock |
| **switch** | on/off | `split.auto_read`, `models.hosted_allowed`, `upload.allow_scans`, `scheduled.writes_allowed` | a switch that turns a **safety check** off does not exist; a switch only turns a convenience or a cost on or off ([7](#7-safety)) |
| **cost** | cents | `models.hosted_budget_cents_per_month`, `mailroom.max_cents_per_send`, `mailroom.max_letters_per_send`, `mailroom.max_pages_per_letter` | a spend ceiling is `lower_only`: it can be tightened by either layer and raised only by the code's reviewed maximum |

Two groups are called out because they must not behave like the rest:

- **Safety ceilings** (`lower_only`, and the instance may not raise them either): anything that spends the association's money or reaches its members without a person reading it first. The mailroom's per-send cost, letters, and pages are the example: the registry's default is the most jason will ever send in one act; an administrator may set it lower, never higher, and a person who needs more sends in more than one act, each with its own `--send --yes`. A limit that protects a person outside the community (a recipient, a member) is a safety ceiling.
- **Provider floors** (a rate limit, a cadence): the default is the polite rate and is also the maximum. A layer may slow jason down and may not speed it up.

### What is not a limit

A rule of the association (a quorum, a fine, a notice period) is the profile's. A deadline in law is the law's. A secret, a path, an account, and an address are not limits. A permission (who may do a thing) is the roster's. A limit never decides whether something is allowed in principle; it decides **how much, how fast, or how long**.

## 2. Layers and precedence

Four layers, from the most general to the most particular. A value is found by walking from the top (the code) down and keeping the last layer that sets it **and is allowed to**.

| # | Layer | Set by | Lives | Reach |
|---|---|---|---|---|
| 0 | **Code default** | the code, reviewed | `jason.limits.LIMITS` | every installation, every community |
| 1 | **Environment** | the person who starts the process | `JASON_LIMIT_<KEY>` in the process environment, the project's `.env`, or the user config | one process; a bring-up and test convenience, reported as `env` |
| 2 | **Instance** | the **instance operator** | the instance limits file ([3](#3-where-each-layer-is-stored)) | every community on this installation, as a **ceiling** and as a default |
| 3 | **Community** | the **community's administrator** | the community's data folder | that community, inside the instance's bounds |
| 4 | **One act** | a **person**, with a reason | the act's own record | one upload, one run, one send |

The resolver, in order:

1. Start with the code's `default`.
2. If the instance sets a value, it becomes the **instance value**, and it also sets the instance's **ceiling** for the key (the instance may set a separate `ceiling`; if it sets only a value, the value is both). It is clamped to `[minimum, maximum]`.
3. If the community sets a value **and the key allows the community scope**, it is used, clamped to `[minimum, min(maximum, instance ceiling)]`. A community value above the instance ceiling is not used and is reported as `clamped by instance` (it is never silently honored, and never silently discarded).
4. For a `lower_only` limit, steps 2 and 3 are clamped above by the **default** as well as by the ceiling.
5. The environment layer, when set, sits where the instance layer sits (it is the operator's own process) and is reported as `env`. It cannot exceed the maximum, and in a portal it is read only in the instance's process, never in a community's.
6. A per-act override (layer 4) is never stored as a setting. It is read at the enforcement point from the act ([the override](#the-per-act-override)).

`effective()` returns, for each key: `value`, `source` (`default`, `env`, `instance`, `community`), `minimum`, `maximum`, `ceiling` (the highest this community may set: min of maximum and the instance's), `clamped` (a note, when a stored value was not used as written), and `set` (who, when, why, of the layer that won). **Source** answers "why is it this number?" in one word, and the console shows it in words ([4](#4-the-console)).

### Rules that keep the layers honest

- **Tighten freely, loosen within bounds.** Any layer may set a value that is more restrictive than the layer above it. A layer may set a value more permissive than the layer above only if the layer above's ceiling allows it. For a `lower_only` limit, "more permissive" is never allowed.
- **The instance's ceiling binds communities, not itself.** The operator may move an instance value up to the code's `maximum` at any time (by a recorded change). A community cannot.
- **Each community is read on its own.** One community's value never changes another's effective value (the same rule as everything in [tenancy.md](tenancy.md)). The resolver takes the community from the process or the request context, never from an argument a caller supplies.
- **A missing or damaged file is a miss.** A layer whose file is absent, unreadable, or not valid is skipped, a line is logged, and `jason limits` says so. It never makes the limit unbounded and never crashes a job.
- **An unknown key in a file is kept and reported**, not dropped (a file written by a newer jason is not destroyed by an older one).
- **A value is typed and checked on read as well as on write.** A file that was edited by hand to a value outside the bounds is clamped and reported; the audit trail shows no change was made through jason.

### The per-act override

Some limits may be passed **once**, by a person, with a reason, because a legitimate act is occasionally larger than the usual one (a very large combined scan; a mailing to the whole membership). The override is the weakest layer and the most visible.

- Only a limit whose `override` allows it, and only up to the limit's `override_max` (a number at most the hard `maximum`, and never above a safety ceiling).
- Offered where the refusal is told ([6](#6-enforcement-and-how-a-refusal-is-told)): "This file is 140 MB; the limit is 100 MB. A person may allow this one file up to 250 MB, with a reason."
- Needs a person with the **community administrator** role (or higher) to confirm; not an officer by that office alone, and never jason on its own initiative. The reason is required text, not a choice.
- It applies to **that act only**. The act's record carries it: `limit_override: {key, limit, allowed, by, reason, at}`. It is not a setting and cannot be copied to the next act.
- Recorded in the same audit trail as a change of setting, with kind `override`.
- A rate limit and a switch have no per-act override. A safety ceiling has none.

## 3. Where each layer is stored

**Never in the profile's checked-in code. Never a secret. Never in the vault.** A limit is configuration, not a fact about the association and not a credential.

| Layer | File | Why there |
|---|---|---|
| Code default and bounds | `src/jason/limits.py` (the registry) | reviewed, the same for every association; a default is not an association's fact |
| Environment | `JASON_LIMIT_UPLOAD_MAX_BYTES=...` | the way every other machine setting is read (`config._env_value`), so the user config applies; this layer is for bring-up and tests |
| Instance | `~/.jason/limits.json` (`JASON_LIMITS_FILE` moves it; the user config home, beside `~/.jason/.env`) | the installation's, outside every community's data folder and outside the repository, found the same way by a terminal, the worker, and a scheduled task (`config._anchored`; never relative to the working directory) |
| Community | `<community data folder>/limits.json` (`data/<key>/limits.json`, or `data/limits.json` for the built-in default folder, by the same rule as every store; [profiles.md](profiles.md#each-profiles-data)) | the community's own record, with its backups and its export; a restore of this community restores its limits and no other's |
| Audit | `<scope's folder>/limits-log.jsonl` (instance: `~/.jason/limits-log.jsonl`; community: `<data folder>/limits-log.jsonl`) | append only, beside the file it describes ([the trail](#the-audit-trail)) |

### Formats

One file per layer, JSON, written whole with a temporary file and a rename, under the store lock (`jason.locks`), so a reader never sees half a file.

```json
{
  "version": 1,
  "limits": {
    "upload.max_bytes":        { "value": 52428800, "ceiling": 209715200,
                                 "by": "A. Operator", "at": "2026-10-10T16:02:11Z",
                                 "reason": "The host's disk is small" },
    "split.auto_read":         { "value": false }
  }
}
```

The community's file has the same shape without `ceiling` (a community does not set a ceiling for anyone). `value` is typed by the key's unit (integers in the unit's base: bytes, cents, seconds; booleans for switches). `by`, `at`, and `reason` are written by the change command, not typed by hand; a file with a value and no `by` is read, shown as "set by hand", and the audit trail has no matching line. The file holds **the current value and who last set it**; the trail holds the history.

Rules for the files:
- **No secret and no personal data** may be written to a limits file. The registry has no key whose value is a name, an address, or a credential.
- **The community file belongs to the community's volume.** An instance change never edits it; the instance's ceiling is applied when the value is read.
- **Every write goes through one function** (`jason.limits.set_limit`), which checks the key, the layer's right to set it, the bounds, the ceiling, and the role, and writes the file and the trail together. A hand edit is allowed (it is a file) and is clamped on read.
- **A shared host with several processes** reads the files on each job start and at most once a minute in a long-lived process, so a change takes effect on its `restart` ([1](#the-record)) without a restart of the service. A cached value is keyed by the community and the file's modification time, as private facts are.

### The audit trail

Every change, in either layer, is one line in the layer's `limits-log.jsonl`, appended in the same locked write as the file. It records:

| Field | Meaning |
|---|---|
| `at` | when (UTC) |
| `kind` | `set`, `reset`, `override`, `clamped` (a read found a value outside the bounds), `refused` (a change that was refused and why) |
| `scope` | `instance` or `community` (and the community key in the instance's trail for a community-targeted act, never the community's values) |
| `key` | the limit's key |
| `from`, `to` | the previous and new values, typed and with their unit (`from_source`, the layer the value came from before) |
| `reason` | the person's text, required for `set`, `reset`, and `override` |
| `by` | the name given with `--by`, or the signed-in person's roster name in the console |
| `via` | `cli`, `console:google`, `mcp` |
| `who` | for the console, the signed-in account's subject (a Google subject, as the access log already records it); for the CLI, the operating-system user, labeled as a claim ([tenancy.md](tenancy.md#attribution-and-the-approvals-one--and-two-person-rules)) |
| `role` | the role the person acted in (`instance operator`, `community administrator`) |
| `dry_run` | never true in the log; a dry run writes nothing |

**No file names, no paths, no document text, no owner or unit.** An override line names the kind of act ("an upload", "a mailing") and the numbers, never the thing that was uploaded or the people mailed. The reason is the person's own text and is shown back to them with the warning that it is kept; a form that asks for it says not to put names in it. The trail is kept with the layer's other logs and follows their backup. The instance's trail holds the operator's changes and the fact that a community was changed (the key, the limit, the numbers); it never holds a community's reasons for an override.

`jason limits --log` reads a trail (the community's own, or the instance's); a person sees only the trail they may.

## 4. The console

Two screens, one component family. Both are **read by their role and written only by the role the layer names** ([7](#7-safety)). They extend the Instance and Setup screens of the [instance handoff](console/handoff-instance-and-integrations.md) and add no new level of navigation.

| Screen | Route | Who | What it sets |
|---|---|---|---|
| **Instance → Limits** | `#/instance/limits` | the instance operator (one of jason's administrators as themselves; 403 to anyone else and while viewing as someone else; never the owner view) | the instance layer: a default and a ceiling for every community |
| **Community → Limits** | `#/setup/limits` (a tab of Setup) | the community's administrator; officers and managers read it | the community layer, inside the instance's ceiling |

### The table

One row per limit, grouped by kind (Size, Counts, Rates, Time, Switches, Cost), each group collapsible and the groups that have a changed value open. Columns:

| Column | Shows |
|---|---|
| **Limit** | a plain name ("Largest file you can upload") and, small, the key (`upload.max_bytes`) so a command line matches |
| **In effect** | the value in words with its unit ("100 MB", "6 files at once", "off") |
| **Where it comes from** | one word with a glyph: **built in**, **this machine's setting** (env), **the operator**, **this community**; a `clamped` note when a stored value was not used as written ("set to 500 MB here; the operator's limit is 200 MB") |
| **Allowed range** | the minimum, the highest this layer may set (the ceiling), and the built-in default ("1 MB to 200 MB; built in 100 MB") |
| **Last changed** | who and when, from the layer's trail ("A. Operator, Oct 10, 2026"), with the reason on expand |
| **Edit** | opens the editor (a read-only row shows why it is read-only: "set by the operator", "only the code sets this") |

An instance row for a key adds a **community column group** (read-only, names and values, no content): how many communities use the instance value and which have set a lower one. A community's row shows nothing of any other community.

Each row expands to two lines the person can always read:

- **Why this limit exists.** The registry's `why`: "Large uploads fill the disk and make the reading of a scan very slow. The limit keeps one file from using the machine for an hour."
- **What happens when it is reached.** The registry's `when_hit`: "The file is not saved. You are told its size and the limit, and may split it, or ask an administrator to allow this one file up to 250 MB with a reason."

### The editor: dry run first, then confirm

Editing is a two-step act, as every write in the console ([approval-workflow.md](console/approval-workflow.md) and the `Confirm` mark):

1. **Change.** A typed field for the value in the unit's own words (a size takes "50 MB"; a switch is a switch; a time takes "30 minutes"), with the allowed range beside it and a required **Reason** field.
2. **Preview (a dry run).** The same call as the command line with no `--yes`. It shows, in words:
   - the change: "Largest file you can upload: 100 MB (built in) to 50 MB (this community)";
   - **what it affects**: for a size or count, how many things on disk are already above the new value and what happens to them (nothing: a limit applies to new acts and never deletes or hides what exists); for a rate, the next cadence run it would slow; for a retention, **what would be removed and when**, as a count and a size, never a name;
   - **what it cannot do**: "The operator's limit of 200 MB still applies" or "This is the lowest allowed";
   - who will be recorded: the signed-in person's name and role.
3. **Confirm.** One button, labeled with the change ("Set the limit to 50 MB"), not "OK". It records the change and the line in the trail and shows the new row with a "Changed just now" mark. **Cancel** leaves nothing written.

**Reset to default** is a row action with the same preview ("Back to the operator's 200 MB" or "back to built in 100 MB"), a reason, and a confirm. It removes the layer's value; it never sets the built-in value as if the layer chose it.

A retention that would delete anything is **never confirmed in the same screen that sets it** without the delete preview and a typed confirmation (the word "remove"), and the deletion itself is a separate, logged job ([retention](#retention-is-the-limit-that-can-delete)).

### Words the person reads

The wording is the registry's; the screens add none of their own. Every refusal and every explanation:
- names the limit **in plain words**, the number, and the unit, never a key or an id ("This file is 140 MB; the largest allowed here is 100 MB.");
- says **what was not done** ("The file was not saved.") and **what the person can do** (split, ask for an override, wait, or ask the administrator or the operator), in that order;
- names **who can change it** in words ("Your community's administrator can raise this to 200 MB, the operator's limit.");
- carries no file name, no unit number, no owner, no path, and no id; if the person needs to find the act, the screen they are on is the context.

Examples:

| Limit | When hit |
|---|---|
| `upload.max_bytes` | "This file is 140 MB. The largest file you can add here is 100 MB. Nothing was saved. You can split the scan into smaller files, or ask your community's administrator to allow this one file." |
| `ocr.pages_per_job` | "This scan has 320 pages and one reading handles at most 200. The first 200 pages were not started. You can split the scan, or a community administrator can allow this one scan up to 300 pages." |
| `mailroom.max_letters_per_send` | "This sending would mail 214 letters; one sending is limited to 150. Nothing was sent. Send the first 150, then the rest as a second sending, each confirmed by a person." (No override.) |
| `drive.reads_per_hour` | "jason has read as much from Drive as it may this hour. The reading will continue at 14:00. Nothing was lost." |
| `models.concurrent_jobs` | "A reading is already running for this community. This one is waiting its turn and will start by itself; it is number 2." |

The Status screen of a community shows a limit that is **currently holding something back** (a rate limit that is delaying a read, a queue at its depth) as a state, with the same words, so a person is not left wondering why it is slow.

### Accessibility and layout

Follows the console's contracts ([components.md](console/components.md)): every state is a word and a glyph, never color alone; the editor is keyboard-complete; the range and the effect are read by a screen reader in the order above.

## 5. The command line and MCP

### `jason limits`

Read-only without a change flag. One community per command, chosen as every command is ([tenancy.md](tenancy.md#3-the-cli)).

| Command | What it does |
|---|---|
| `jason limits` | the table for the chosen community: key, value with unit, source, the range, last change |
| `jason limits KEY` | one limit: its value and source, every layer's value, the bounds, the ceiling, `why`, `when_hit`, and the last five lines of its trail |
| `jason limits --scope instance` | the instance layer's table (values, ceilings, who set them); needs no community |
| `jason limits --json` | the same as data, for the console's loaders and scripts |
| `jason limits --log [--key KEY] [--scope S]` | the trail |
| `jason limits --set KEY=VALUE [--ceiling VALUE] --scope instance\|community --reason TEXT --by NAME` | a **dry run**: prints exactly what would change and what it affects, and writes nothing |
| `jason limits --set ... --yes` | applies it |
| `jason limits --reset KEY --scope S --reason TEXT --by NAME [--yes]` | removes the layer's value, with the same dry run |

Rules:
- `--set` without `--yes` is always a dry run, and says so on its first line. `--yes` is the same call with the write.
- `--reason` and `--by` are required with `--set` and `--reset`; a missing one stops the command before anything is read (exit 2). `--by` is a claim on a terminal, labeled as one in the trail.
- A command with `--scope community` prints the write line first (`community: example (from ...); data: ...`), as every write does, and runs against that community only. `--scope instance` prints `instance: PATH` instead and never opens a community's folder.
- A value is parsed in the unit's words (`50MB`, `30m`, `on`); a value outside the bounds, above the ceiling, on a `lower_only` limit above its default, or on a key the scope may not set, stops with the reason and the nearest allowed value. Exit code 1 for a refused value, 2 for a usage error.
- `--set` takes more than one `KEY=VALUE` and applies them in **one** write with **one** reason (so a related pair is not left half changed); the dry run lists each.
- The command works with no network, no vault, and no model; it reads and writes the two files and their trails.
- It is a person's command. A scheduled task, a job, and the MCP server never call `--set`.

### MCP

One read-only tool in the `board` and `governance` tool sets and the operator's server: `limits` (no arguments but an optional `key`). It returns the effective table for the **server's community** with each value, its source, its range, and its `why` and `when_hit`, and the caveat "These are the limits in force; they are changed by a person, in the console or with `jason limits --set`." It takes **no community argument** (the rule in [tenancy.md](tenancy.md#4-mcp)) and serves no secret and no trail's reasons. The instance server (`jason-mcp --instance`) serves the instance layer with the same shape. **No MCP tool changes a limit**, and none proposes a value as a setting; a model that thinks a limit is too low says so in words, and a person decides.

## 6. Enforcement and how a refusal is told

### Where a limit is enforced

Every limit names its enforcement points in `applies_to`, and each is **one call** to the registry, never a comparison against a number in the caller:

```python
limit = limits.check("upload.max_bytes", size, act=act)   # raises LimitReached with .words
```

`LimitReached` carries the limit's key, the number, the limit, the layer that set it, and the registry's `when_hit` already filled in. The caller renders `.words` and does nothing else: no caller rewords a refusal, and none compares a value to a constant. A **lint** (`tests/test_limits_used.py`) fails on a number in a limit's range that appears as a bare literal where a registry key exists, on a registry key that no `applies_to` point reads, and on a read of a key that is not in the registry.

| Point | Limits it reads |
|---|---|
| the web upload handler (before the body is stored; the length header first, then the stream's count) | `upload.max_bytes`, `upload.allow_scans`, `web.requests_per_minute` |
| the record-intake split and read steps | `split.auto_read`, `split.max_parts`, `ocr.pages_per_job` |
| the job queue and the worker | `jobs.queue_depth`, `job.timeout_seconds`, `lane.<name>.concurrent`, `models.concurrent_jobs` |
| the Google, PayHOA, and county readers | `drive.reads_per_hour`, `gmail.reads_per_hour`, `county.requests_per_hour` (shared with the cadence floor) |
| the vault session | `vault.session_idle_seconds` |
| the mailroom's plan and its send | `mailroom.max_cents_per_send`, `mailroom.max_letters_per_send`, `mailroom.max_pages_per_letter` (checked on the **preview** and again on `--send`) |
| the temp and fetched-copy sweeper | `retention.fetched_copies_days`, `retention.temp_days` |
| the hosted-model reader | `models.hosted_allowed`, `models.hosted_budget_cents_per_month` |

**Check early, check again late.** A limit is checked at the earliest point that has the number (the upload's declared length) and again where the number is true (the stored count), because the first can be wrong. A refusal leaves nothing half-done: an upload over its limit is not stored, a batch over its count does nothing, and the act says so.

### Four ways a limit behaves

| Behavior | Which kinds | The person sees |
|---|---|---|
| **Refuse** | size, count, cost, a switch off | the words; nothing was done |
| **Wait** | rate, concurrency, queue | "will start by itself"; the position or the time; nothing is lost; a rate limit slows, it never drops a read |
| **End** | time (a job timeout, an idle session) | "ended after 30 minutes"; what was done and what was not; the job may be run again |
| **Remove** | retention | only by the sweeper, only what is past its age, as a logged job, with a count; see below |

### Retention is the limit that can delete

A retention limit decides when jason removes a **copy it made** (a fetched file, scratch, a rebuilt index), never the association's record. The sweeper:
- removes only files under the folders the registry names for it (`temp`, `fetched`), checked by the jail (`jason.tenancy.assert_inside`, [tenancy.md](tenancy.md#2-isolation-model-for-the-portal)), so a mis-set age can never reach a store, a pin, an upload's bytes, or a source document;
- never deletes what a pin, a key document, or an open job still reads;
- logs a count and a size, never a name;
- has a **minimum** age in the registry (a copy is not removed within a day of being made, so a running job never loses its input), which no layer can lower.
Raising a retention (keeping copies longer) is free. Lowering one asks for the delete preview in [the editor](#the-editor-dry-run-first-then-confirm).

### How limits meet the local-model GPU lock and the temp-drive guard

- **The GPU lock is not a limit and a limit cannot hold it.** The lock (one per machine, [tenancy.md](tenancy.md#8-operations)) orders model jobs; `models.concurrent_jobs` bounds how many **may be queued or running for one community** so one community cannot fill the queue, and `ocr.pages_per_job` bounds one job's length so the lock is released and a resumable batch is made. A limit is checked **before** the lock is requested, so a refused job never waits for the lock and a waiting job never holds a limit's slot idle. A raised concurrency never lets two jobs hold the GPU lock; it lets two be *queued*.
- **The preflight comes first.** `jason.local_ai.preflight` (GPU, commit charge) still runs before a model job and fails fast on the CPU or short of commit. A limit never overrides it: a model job is allowed only if **both** the limit and the preflight allow it, and the refusal names the one that stopped it ("the machine is short of memory right now" is the preflight's, in its own words, not a limit's).
- **The temp-drive guard also comes first.** `jason storage --check` and the guard on `JASON_TEMP_DIR` stop a job when a drive is short of room; a size limit set high (an upload of 2 GB) does not make room that is not there. The upload point checks the **guard's free space against the declared size** as well as the limit, and refuses with the guard's words if the drive cannot take it. A limit's maximum is chosen at registry time to fit a typical host, and the instance's Limits screen shows the host's free space beside any size limit.
- **A limit can only make jason do less than the guards allow.** It is never a way around one.
- **Per community.** In a portal the guards are per machine and the limits per community: a community's limit narrows its own share; one community's raised limit cannot take another's room (a community's total share of the volume is a quota in [tenancy.md](tenancy.md#storage-and-temp), not a limit that could be raised through this page).

## 7. Safety

### Who may change what

| Layer | Who | How | What the person must have |
|---|---|---|---|
| Instance | the **instance operator**: one of jason's administrators as themselves (`data/access/admins.json`; in a portal, the instance role) | Instance → Limits; `jason limits --scope instance --set ... --yes` | a name, a reason; on the console, a signed-in session |
| Community | the **community administrator** (a role with no office, as in the [handoff](console/handoff-instance-and-integrations.md#who-and-where)); an officer, a manager, or an owner is read-only unless the roster also makes them an administrator | Setup → Limits; `jason limits --scope community --set ... --yes` | a name, a reason; on the console, a signed-in session |
| One act | the community administrator, at the refusal | the override ([2](#the-per-act-override)) | a reason |

- **No limit is changed on an officer's authority alone, and none on a manager's.** A manager serving several communities holds no limit rights unless the community makes them an administrator there. A manager in a portfolio does not set limits across it.
- **A community's administrator cannot raise a limit past the instance's ceiling**, and the instance's operator cannot raise one past the code's maximum. Each of those is checked in `set_limit`, not in the screen.
- **A person does not set a limit that affects only another person's act** (there is no per-person limit in this design).
- **In the portal, the operator sees values, sources, and the trail's numbers and never a community's reasons for an override** or any content.

### Changes are proposals to a person, never jason's own initiative

- jason **never changes a limit by itself**: not when it is hit often, not when a disk is full, not when a job fails. It may **propose**: a repeated refusal produces a finding for the administrator ("In the last 30 days, 9 uploads were over the limit of 100 MB; the largest was 140 MB. The administrator may raise the limit up to the operator's 200 MB, or leave it.") shown on the Limits screen and in the board's digest as an item. The finding is data (counts, sizes), not a button.
- A model never proposes a value as a setting, and no MCP tool writes.
- A scheduled task never calls `--set`.
- A raised limit **has a cost and a reason**; the dry run says what it costs (disk, time, money) in words.

### Bounds that cannot be disabled

- **Every limit has a `maximum` and a `minimum`.** There is no "no limit", no `0` that means unlimited, no `null`, no negative, and no value that the parser reads as unbounded (`inf`, a very large string). A switch is the only kind with two values, and a switch is never the way to disable a safety check.
- **Safety ceilings are `lower_only`.** The instance may not raise a mailroom ceiling above the code's.
- **Floors are floors.** A rate or a cadence cannot be faster than the provider's published or polite rate; this page and the scheduler's cadence floor are one number.
- **The minimums protect the work.** A timeout cannot be so short that no job could finish; a retention cannot be so short that a running job loses its input; a queue depth cannot be zero while jobs are queued.
- **Changing the registry's bounds is a code change**, reviewed, with a lesson if it follows an incident; it is never a setting.
- **A limit never turns off the audit trail,** the write line, a confirmation, a two-person rule, the jail, the identity check, the store lock, the preflight, or the temp guard. There is no limit key for any of them, and a test fails if one is added.

### Honest failure

- A limits file that cannot be read gives the **built-in value and the stricter of any layer that can be read**, never the more permissive; the screen says the file could not be read and where.
- A change that cannot be written is not applied; the screen says so and the old value stays.
- A change whose trail line cannot be written is not applied (the file and the line are one write).
- If the clock is wrong or the file is from the future, the trail records what it read and the screen says so.

## 8. Phases, tests, open decisions

### Phases

Each phase is small, and each says what it proves.

| # | Phase | What changes | What it proves |
|---|---|---|---|
| 1 | **The registry and the resolver** (the sibling change plus) | `LIMITS` rows with the full record ([1](#the-record)); `effective()` with the instance and community files read, the ceiling, the bounds, and `lower_only`; the files' format and the atomic write; `limits.check` and `LimitReached`; `jason limits [KEY] [--json]` and `--scope instance` | the layers resolve in the right order; a bad file is a miss; a community cannot exceed the ceiling; two communities in one process read their own values |
| 2 | **The write path and the trail** | `set_limit` and `reset_limit` as the one writer; `limits-log.jsonl`; `jason limits --set/--reset/--log` with the dry run, the write line, `--reason`, `--by`; the roles for the CLI as a claim | a change is a dry run until `--yes`; the trail has who, from, to, reason; nothing is written on a refusal |
| 3 | **Enforcement points** | the upload handler, the intake split, the job queue and lanes, the readers' rates, the vault idle time, and the mailroom's ceilings read the registry through `limits.check`; the lint that finds a bare number and an unread key; the words for each refusal | every first limit is enforced from the registry and nothing else; a refusal is in words with no id and no file name |
| 4 | **The console** | `#/instance/limits` and `#/setup/limits` (the table, the editor with dry run and confirm, reset, the explanations, the effect preview), the 401/403 rules, the signed-in person in `by`/`who`, the findings for repeated refusals | an administrator changes a limit and sees why it is what it is; an officer sees it and cannot change it |
| 5 | **Per-act overrides** | the override at the refusal, the reason, the act's record, the trail line, the `override_max` | one large act goes through once and leaves a visible record; the next one is refused again |
| 6 | **Retention and the sweeper** | the retention keys, the sweeper as a job under the jail, the delete preview and typed confirmation, the minimum age | a lowered age removes only copies, with a count, and never a store |
| 7 | **Portal** | the instance's ceiling applied to every community's cell; the instance screen's per-community columns; the file read per process; the operator's MCP | the same two-community test, with different limits, passes in cells and in one process |

Phases 1 to 3 are useful on one PC with no portal. A new limit after phase 3 is one row and the call at its enforcement point.

### The test plan

1. **Resolver** (`tests/test_limits.py`): each layer alone; each pair in precedence; the ceiling clamps a community; `lower_only` cannot rise above its default at any layer; a value below `minimum` or above `maximum` is refused on write and clamped on read; a missing, empty, truncated, and invalid file are each a miss with a line; an unknown key is kept; `effective()` reports the right `source` and `clamped` in each case; the unit parser (`50MB`, `30m`, `on`) and its refusals; no way to express "unlimited".
2. **Isolation** (`tests/test_limits_tenancy.py`, on the two-community harness of `tests/test_tenancy.py`): `alpha` and `beta` in **one interpreter**, alpha then beta then alpha, with different community values for the same key and different instance ceilings; each reads its own, a change to alpha's file changes nothing in beta's read, beta's file is byte-identical after any alpha write, no audit event opens the other's `limits.json` or trail, the cached value is keyed by community and modification time, and the same assertions hold across separate processes. A **sentinel** reason in alpha's trail never appears in beta's output, the instance's trail, or the instance console loader. The module-state lint (`tests/fixtures/tenancy_state.json`) gets no new unkeyed state.
3. **Writes**: a dry run writes nothing (a file hash before and after); `--yes` writes the file and the trail line together or neither (a failure injected between them); `--reason` and `--by` are required; a community administrator cannot set a key the registry gives only to the instance; the role checks in the console loader (401 with no sign-in; 403 for an officer, a manager, an owner, and while viewing as someone else; the operator is refused on a community's override reasons).
4. **Enforcement**: a table-driven test over the registry that, for each key, builds the smallest act over its limit and checks the refusal's words (no key, no id, no path, no file name; the number, the unit, the next step), and that nothing was stored; a test that a key with no `applies_to` or an `applies_to` that no code reads fails; the lint for bare numbers.
5. **Guards**: a size limit above the temp drive's free space is refused with the guard's words; a model job over its concurrency is refused before the GPU lock is requested (assert the lock is not taken); the preflight's refusal and a limit's refusal read differently; a raised concurrency does not allow two holders of the lock.
6. **Safety**: a test that no registry key names a safety control (the write line, the confirmation, the jail, the preflight); a test that every key has a finite `minimum` and `maximum` and a `why` and a `when_hit`; a mailroom ceiling cannot be raised above the default at the instance or community layer or by an override; the sweeper never touches a path outside its folders, nor a file a pin reads, nor a file younger than the minimum age.
7. **Words** (`tests/test_limits_words.py`): every `why` and `when_hit` passes the console's content rules ([content/style.md](console/content/style.md)): plain language, no id, no key, and a next step.
8. **Boundary**: `python -m jason.community.boundary` and the docs boundary test stay clean; the registry holds no association's fact (a default is a number for any association).

### Open decisions (for the user)

1. **Where the instance file lives in a portal.** `~/.jason/limits.json` is right for a PC and for a cell that has a home folder; a cell with a read-only image wants it from a mounted instance config volume or from the environment. Recommended: the same file name, found by `JASON_LIMITS_FILE`, so a deployment mounts it.
2. **Whether an environment layer exists in a portal at all.** Recommended: yes for the instance's own process, never read inside a community's cell for a key the community may set, so an environment variable cannot be a back door around a community's own choice or the instance's ceiling.
3. **Who the community administrator is for the CLI.** On a PC the person at the terminal gives a name and the trail calls it a claim; in a portal only a signed-in administrator may set a community limit. Recommended: as in [tenancy.md](tenancy.md#attribution-and-the-approvals-one--and-two-person-rules), a claim on a PC, an authentication in the portal; no extra approval for a limit.
4. **Whether a lowered limit needs a second person.** Recommended: no (a tightening is safe); a **raised** safety-adjacent limit (the hosted-model budget, a retention lowered) is a candidate for the two-person rule in the portal. For the user.
5. **The first set of keys and their numbers.** This page names kinds and illustrative keys; each default, minimum, and maximum is the registry's, chosen with the operator's host in mind. Recommended: ship the first two and add one row at a time as each enforcement point is wired (phase 3).
6. **Overrides: reason only, or reason and a second person.** Recommended: reason only, the community administrator, in the trail; a mailing has no override at all.
7. **Whether a cost limit also counts money spent elsewhere** (a provider's own invoice). Recommended: no; a cost limit counts only what jason itself records (`cost.jsonl`, the sending log), and says so.
8. **How a limit is announced.** When the operator lowers a ceiling under a community's value, the community's administrator is told on the Limits screen and in the next digest, not by mail. Recommended: that, with the change in the community's trail as an instance act.
9. **Whether a limit's findings feed the board's digest** or stay on the Limits screen. Recommended: the screen, plus one digest line for a repeated refusal.
10. **Retention duties.** What the association must keep is read with `jason cite` and decided by the board and counsel; the registry's `retention.*` minimums are a safety floor for running jobs, not a statement of that duty. For the board.

## Decisions taken in phases 1 and 2

The open decisions above were answered with their **recommended** answers; the code adds these choices where the page was silent.

| # | Decision | Taken |
|---|---|---|
| 1 | Instance file in a portal | `~/.jason/limits.json`, beside the user config (so `JASON_CONFIG` moves both in tests); `JASON_LIMITS_FILE` moves it alone. The trail sits beside the file (`limits-log.jsonl`) |
| 2 | Environment layer | read as the operator's own: `JASON_LIMIT_<KEY>` in the process is `env`; the same name in the project's `.env` or the user config stays `instance` (as it was before this change). Neither sets a ceiling; only the instance file does. In a portal a community's cell would not read the environment for a key the community may set: not built (phase 7) |
| 3 | Community administrator on the CLI | a claim: `--by` is recorded as given, with `who: claim: <operating-system user>`; no extra approval |
| 4 | Second person for a raised limit | no |
| 5 | The first keys | the two that exist (`upload.max_bytes`, `split.auto_read`), each now a full record |
| 6 | Overrides | built in phase 5 (backend), see [phases 3 to 5](#decisions-taken-in-phases-3-to-5-backend) |
| 7 | Cost limits | not built |

Choices the page left open:

- **Order of layers.** Default, then the profile's `Community.limits()` (still `community`), `.env`/user config, process environment, the instance file, the community file. The last that sets a value wins, so the community file is the final word inside the instance's ceiling. The profile's `Community.limits()` is held to the same ceiling.
- **The ceiling.** An instance entry with only a `value` is also the ceiling (as written above), so a community can then only go lower; to leave communities room, the operator sets `--ceiling`. For a switch the instance's value is the ceiling: an instance `off` keeps the switch off for every community.
- **What "stricter" means when a file cannot be read.** The code's default is the baseline. The value is the stricter (smaller number, or switch off) of the default and the values that could be read; an unreadable instance file means no ceiling above the default. So an unreadable file never loosens anything, and never tightens below what a readable layer chose. An empty file counts as unreadable; a missing file is no layer and no note. A file with a value that does not parse for one key is unreadable for that key.
- **`effective()` fields.** `value`, `source`, `clamped` (a bool), `note` (the clamp or the unreadable file, in words), `minimum`, `maximum`, `ceiling`, `set` (by, at, reason of a file's winning entry), `layers`, `unreadable`. Clamping is on read as well as on write.
- **Writes.** `set_limits` and `reset_limits` take the store lock for the file, stage the new file beside it, append the trail line, then rename the file into place; a failure before the rename leaves the old file and no line. A file that cannot be read is never written over. A reset logs `to: null`. The trail line carries `at, kind, scope, key, from, from_source, to, unit, reason, by, via, who, role` (and `ceiling`); no file name or path. The `clamped` and `refused` trail kinds are built (phases 3 to 5, below); the instance trail's line for a community-targeted act (the portal's) is not.
- **Refusal text.** `LimitReached` (a `ValueError`, so existing handlers still catch it) carries `key, amount, limit, source, words`. `when_hit` is a template with `{amount}` (rounded up), `{limit}`, `{ceiling}`. Callers whose cap is the smaller of two readings use `limits.refusal(key, amount, cap)`; a plain comparison uses `limits.check`. The upload refusal no longer names the file.
- **Not yet** (at the end of phase 2; see the next section for what has since been built). The console screens, the web server's request ceiling, the other enforcement points.

The lint (`tests/test_limits_used.py`) finds a bare copy of a size limit's default or maximum, a registered key that nothing reads, and a read of an unregistered key. Two literals of the same size that are other limits not yet rows (a stored-file copy and a read-back fetch) are listed there with their reason, and the test fails when one is no longer needed.

## Decisions taken in phases 3 to 5 (backend)

What the backend of the console, the MCP tool, the override, and the guard settled where the page was silent.

| # | Decision | Taken |
|---|---|---|
| 1 | `fetch.max_bytes` | A registered size limit (default 100 MB, 1 MB to 500 MB, no override), read through `limits.check` at `tasks.drive_copies.export` and `tasks.record_readback._problem`. `DOWNLOAD_LIMIT` and `MAX_FETCH` and the lint's exemptions are gone; the refusal is the registry's words |
| 2 | Temp-drive guard | `jason.storage.require_room` runs at the upload point (`record_upload.upload`, before any limit or override is read, and again in `_keep` for a split's parts): the data drive must keep 256 MB free after the file, and the temp drive must hold the file. It refuses in words naming the drive (never a path) with "A limit never makes room that is not there." A drive that cannot be read is not a reason to refuse. An override cannot get past it, and no override line is written when the guard refuses |
| 3 | The two loaders | `GET /api/limits` (Setup > Limits): any signed-in officer, manager, or administrator reads; a person with no office is refused (403) and the owner view is refused (the source is in no owner list). `GET /api/instance-limits` (Instance > Limits): `status.require_admin` (401 with no sign-in, 403 for anyone else and while viewing as someone else). Each row: effective value in words, source in words, range, ceiling, last change (the layer's trail), why, when hit, clamped and its note, and whether this person may change it (with the reason when not). The instance screen reads the instance file and its own trail only: never a community's values or reasons |
| 4 | The writer | `POST /api/write/limits/<scope>` (`instance` or `community`): `set` or `reset`, a required reason, **a dry run unless `dryRun` is `false`**, the signed-in roster person as `by` (a different name is refused), `who` the account subject, `via` `console:google`. The community layer is the community administrator's; the instance layer is the instance operator's. Today both are the roster's administrator (an admin in `data/access/admins.json`, signed in as themselves, who is on every community's roster), so one person can hold both roles and acts in the role the layer names. An officer, a manager, an owner, and an admin viewing as someone else are refused (403). `set_limits` and `reset_limits` take `role` and refuse a role that is not the layer's, so the check is not only in the screen |
| 5 | Refusals | A refused change is a 400 with the limit named in words, "Nothing was changed.", and "The nearest allowed value is X." (`LimitRefused.describe`). A change meant to be applied that is refused leaves one `refused` line (the attempted value, the reason given, the refusal); a dry run leaves none |
| 6 | The override | `limits.Override` (key, allowed, reason, by, role, via, what) carried as `check(..., act=)`. Honoured only where the row has `override`, up to `override_max`, with a reason, a name, and the role of a community administrator or instance operator; otherwise `LimitRefused` with the nearest allowed value. It is never written to a limits file. A real run writes one `override` line to the **community's** trail (the amount, the allowed value, the reason, the kind of act in words); a dry run (`record=False`) writes none, and if the line cannot be written the override is not allowed |
| 7 | Where overrides are wired | Only `upload.max_bytes` has a row that allows one (once-only maximum 250 MB), and only for a record slot that is not a key document (the key documents' store re-checks the limit itself, so it takes none). `record_upload.upload(override=)`; `jason records --upload KEY --file PATH --override upload.max_bytes=200MB --reason TEXT --by NAME` (a dry run without `--yes`); the console's `upload` act on `POST /api/write/records/<slot>` takes `"override": {"allowed", "reason"}` and only the signed-in administrator may send it. The pin keeps `limit_override` (key, limit, allowed, by, reason, at) as the act's record. The mailroom has none, as designed |
| 8 | `clamped` | `limits.check` notes a stored value that was held to its range once per setting (the same raw value is not written twice in a row) in the trail of the layer that supplied it (`community`, else `instance`). The read does not depend on the write |
| 9 | MCP | `limits(key="")` in the board and governance sets and `jason.api.limits`: the server's community only, no community argument, no trail, no reasons, no path, no write tool anywhere. The instance server (`jason-mcp --instance`) does not exist yet, so the instance layer is not served over MCP |
| 10 | The PDF splitter's limits | Five rows, each read at one point: `split.thumbnail_cache_bytes` (512 MB, 32 MB to 8 GB; `tasks.split_thumbs.store`), `split.max_pages` (3,000, 50 to 10,000; `tasks.split_session.open_session`, before anything is kept), `split.max_parts` (500, 2 to 2,000; `review`), `split.suggest_enabled` (on; `suggest`, and the rule pass at opening), and `split.draft_days` (60, 7 to 365; the sweep). None has a per-act override. See [pdf-splitter.md](pdf-splitter.md), section 9.4 |

Not built: the console screens, the findings for repeated refusals, the retention keys and the sweeper, the portal's per-community column group, the instance trail's line for a community-targeted act, and the other enforcement points (`ocr.pages_per_job`, rates, the mailroom's ceilings).

## Axioms this keeps

- **A limit is a row, not a number in a function.** A new limit is a new row and one call; the caller never compares against a constant.
- **Facts are data.** A default is a number for any association; nothing here names one.
- **Nothing crosses a community.** Each community's limits, trail, and reasons are its own; the operator sees numbers, not content.
- **jason proposes; a person acts.** A limit changes only by a person, with a reason, and is recorded; jason may point out that one is often hit.
- **No secret in a limit.** A limits file and a trail hold numbers, names of people who acted, and their reasons, nothing else.
- **A missing fact is a miss.** A file that cannot be read gives the stricter value, never the looser.
- **Recite the rule; label the reading.** A refusal says the limit, the number, and who can change it; it does not characterize.

## Not part of this pass

- Code beyond the sibling change's registry; the console screens; the sweeper.
- Quotas on the data volume as a whole (a per-community size warning in [tenancy.md](tenancy.md#storage-and-temp)); they are the operator's, not a limit a community sets.
- Billing between an operator and a community.
- The numbers of the first limits beyond the two already chosen.
