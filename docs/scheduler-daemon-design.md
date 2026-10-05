# jason as a service: the scheduler, the daemon, and their commands

Status: design (2026-10-05). Build steps 1 and 3 are built (`jason.jobs`, `jason.locks.account`, `jason.serve`, `jason serve`, `jason daemon`); the scheduler (step 2), incremental reads (4), and leases (5) are not. It pairs with [integrations-design.md](integrations-design.md), which says what each integration is and how often it may be read, and with [console/handoff-instance-and-integrations.md](console/handoff-instance-and-integrations.md), the screens.

## Why

Today nothing in jason runs on a timer. [jobs.md](jobs.md) tells a person to create Windows `schtasks` entries by hand: a daily `jobs add -- gmail --sync` and a `jason worker` at logon. The web app (`jason-web`) and the worker (`jason worker`) are separate processes started separately. And three things keep a second community from running beside the first:
- **The worker's guard is per machine.** `hold(Resource.STORE, "jobs-worker")` carries no profile, so one worker runs on the machine, but each worker serves one profile's `jobs.db`.
- **The service locks are per installation.** `Resource.GOOGLE` is declared and never held; `Resource.PAYHOA` is held only by `batches.py`. Neither is keyed by account or community.
- **Every credential is the installation's** (a Keeper record per `.env` key, one Google token file); see [integrations-design.md](integrations-design.md).

## The shape

One process per installation, `jason serve`, runs three parts:

| Part | What it does | Today |
|---|---|---|
| **Web** | jason-web (Flask under waitress), the console and its routes | `jason-web` |
| **Worker** | the job lanes (GPU, GOOGLE, PAYHOA, COUNTY, LOCAL), one job at a time per lane, each in its own subprocess | `jason worker` |
| **Scheduler** | wakes every 30 to 60 seconds and adds due jobs to the queue | none |

Each part can be turned off (`--no-web`, `--no-worker`, `--no-scheduler`), so the same command runs as one process on one PC or as separate containers from one image later.

**No new dependency.** jason already has a durable SQLite queue with lanes, retries, `not_before`, and per-job logs. A scheduler that only adds rows to that queue needs no library. The alternatives were weighed:
- **APScheduler 3.x** is the maintained line (4.x is still an alpha that its README says not to use in production), but its job store must never be shared between schedulers, and it would be a second queue beside jason's.
- **Huey** (SQLite, crontab periodic tasks) is the lightest full option, also a second queue.
- **RQ, Celery beat, Dramatiq** need Redis or RabbitMQ: too heavy for a single-node SQLite app.

## Schedules

A `schedules` table in each community's `jobs.db`:

| Column | Meaning |
|---|---|
| `key` | the source it refreshes (`drive`, `gmail`, `payhoa-catalog`, …), matching the Status screen's source rows |
| `argv` | the command, as the queue already stores it |
| `every` or `cron` | `15m`, `1h`, `1d`, or a five-field cron |
| `window` | the hours it may run (`07-22`), in the community's time zone |
| `enabled` | on or paused |
| `next_due`, `last_enqueued` | the scheduler's bookkeeping |
| `misfire` | after downtime: `run-once` (the default: one catch-up run, coalesced) or `skip` |
| `source` | where the cadence came from: the integration's default, an admin's change (who and when), or the board's policy |
| `confirmed_by` | required for a schedule that writes (below) |

**Rules:**
- **One run at a time.** A schedule whose last job is still queued or running is not added again (coalesce).
- **Reads only, by default.** A schedule that writes (a command with `--yes`) needs `confirmed_by`, a person's name, exactly as `jobs add --confirm NAME` does today; whether the board allows any scheduled write is its decision ([jobs.md](jobs.md)).
- **Defaults from the integration.** Each integration declares a default cadence and a `stale_after` (about two to three times the cadence); see [integrations-design.md](integrations-design.md#defaults-from-rate-limits). That `stale_after` is what the Status screen has been missing: today no source declares one, so Status shows ages only (lesson `sources-declare-no-freshness`).
- **An admin changes a cadence; jason never tightens one past the integration's floor.** A schedule faster than the floor the integration declares (from its published or polite rate) is refused with the reason.
- **Paused on sign-in failure.** A job that fails with `KeeperAuthRequired`, `GoogleAuthRequired`, a 401, or an auth 403 pauses its integration's schedules and turns its Status row to "not signed in"; they resume when a person signs in again. Nothing retries a sign-in failure on a timer.

## Backoff, one helper for every client

- **Retry on** 429; 403 with `rateLimitExceeded`, `userRateLimitExceeded`, or `usageLimits`; 500, 502, 503, 504; and transport errors.
- **Wait** for `Retry-After` when it is sent, read as seconds or an HTTP date (RFC 9110), and also as an ISO 8601 time, which Zoom sends on a daily limit. Otherwise `min(2^n + random(0..1 s), 32 to 64 s)`, Google's published formula, for at most about seven tries.
- **Then park the job** with `not_before`, which the queue already supports.
- **Never retry** another 4xx, or a write without verifying it (as `batches.py` already does).
- **Stop the lane** on an auth failure (above).

The existing pacers stay: Gmail's (15 down to 1 request a second), Drive's revision export backoff, and `batches.Pace` for PayHOA writes (which already reads PayHOA's `x-ratelimit-remaining`).

## One writer per community: leases

- **The process guard is keyed by profile:** `jobs-worker-<profile>`, the existing OS byte-lock, so a crash releases it.
- **A lease row** in that profile's `jobs.db` (`holder`, `pid`, `host`, `expires_at`, a fencing token that only rises) is taken with `BEGIN IMMEDIATE`, renewed every 30 seconds, and expires after two minutes. A holder that paused past its expiry cannot write stale results.
- **The service locks are keyed by account:** `GOOGLE:<community>` and `PAYHOA:<community>`, so two communities' jobs never wait on each other and one community's jobs never run two at a time against its account.
- **Local disk only.** SQLite's WAL mode does not work over a network file system; a hosted deployment gives each community's data a local volume (one writer per volume), as [deployment-research.md](deployment-research.md) already says.

## Running it

| Where | How | Notes |
|---|---|---|
| **This PC (now)** | Task Scheduler, "At startup", running `jason serve`, restart on failure | Nothing to install; it is what [jobs.md](jobs.md) already uses. A hung process is not detected; `jason daemon status` and the Status screen show the heartbeat. Disable the 72-hour execution limit for a long-lived task. |
| **This PC, supervised** | WinSW or Servy as a Windows service (optional) | WinSW's stable line is v2.12 (2023); Servy is newer and actively released (2026) but one maintainer. NSSM is unmaintained since 2017 and pywin32 services are fiddly with virtual environments. |
| **A container (later)** | one process per container: `jason serve --no-worker --no-scheduler` for web, `jason serve --no-web` for worker and scheduler, from one image, over one volume; `--init` reaps children | No cron in the container (it loses the environment, logs off stdout). |

**Keeper's 30-day logout.** Keeper's persistent login ends after 30 days without use. A daemon that is idle that long needs `jason login` again at a terminal. Status warns at day 25.

## The commands

`jason schedule` and `jason sources` are taken (duties, counterparties), so:

| Command | What it does |
|---|---|
| `jason serve [--profile P \| --all] [--no-web] [--no-worker] [--no-scheduler] [--host] [--port]` | runs the three parts, one lease per profile; `jason-web`'s flags carry over |
| `jason serve --install-task [--yes]` | prints, or with `--yes` creates, the Task Scheduler entry; `--uninstall-task` removes it |
| `jason daemon status` | the process, each profile's lease and heartbeat, each lane's current job, the next five due schedules |
| `jason daemon stop [--profile P]` | marks the lease to drain: lanes finish their current job and stop, as Ctrl-C does today |
| `jason cadence list [--profile P]` | each schedule: its source, cadence, window, next run, last job, and where the cadence came from |
| `jason cadence set KEY --every 15m \| --cron "0 2 * * *" [--window 07-22] --by NAME` | changes one, logged; refused faster than the integration's floor |
| `jason cadence pause KEY` / `resume KEY` | |
| `jason cadence run KEY` | adds it to the queue now |
| `jason cadence defaults [--yes]` | shows, or with `--yes` writes, the integration defaults for every connected integration |

Logs: `data/<profile>/jobs/logs/<id>.log` (exists), `data/<profile>/serve.log` (rotating), and the scheduler's decisions as JSON lines. Health: `GET /api/health` (no sign-in: alive, lease age, lane heartbeats) and the Status screen (next run per source).

## Build order

1. **Built.** Key the worker guard and the service locks by profile and account. This alone lets a second community run.
   - The guard is `jobs-worker-<profile>`; each job runs as its worker's community (`JASON_PROFILE`).
   - `PAYHOA` is held as `payhoa-<profile>` (`locks.account()`) by a batch run and an approval's apply (also `GOOGLE` for a Google kind); a batch no longer has a lock of its own, so two batches of one community no longer run at once.
   - Model jobs stay one at a time across communities (the `jobs-gpu-lane` lock); a GPU job that finds it taken waits without spending an attempt.
   - `GOOGLE` is still held by no Google sync. Candidates, not yet added: `gmail --sync`, `drive --sync`, `templates`, `board --sheet`/`--tasks`, `forms`, `calendar`, and the Vault holds; each holds it only where it writes, since the worker's lane already keeps one community's Google jobs apart.
2. `schedules` and the scheduler thread inside `jason worker`, with `jason cadence`.
3. **Built, without the scheduler.** `jason serve` (web and worker in one process; `--no-scheduler` is accepted and does nothing yet) and `--install-task`.
   - The heartbeat is `<profile data>/jobs/heartbeat.json`, written every 30 seconds and when a lane takes or finishes a job; `jason daemon status` calls one older than 90 seconds stale.
   - `jason daemon stop` writes `<profile data>/jobs/drain.json`; the process drains that community and ends when every community it serves is drained. A request from before the process started is cleared at start.
   - The task is "At startup" (a minute after boot), runs as the person with no password stored (S4U), restarts every minute on failure, and has no time limit. Creating it needs a terminal run as administrator. Task Scheduler restarts a task that fails; a process that hangs is not restarted, only shown stale.
   - The web serves the active profile; `--all` runs every profile's worker beside it.
4. Incremental Google reads: Drive `changes.list` from a saved start page token, Gmail `history.list` from the stored `historyId` (2 units a call against 6,000 a minute per user), Calendar `syncToken`. Today Drive re-lists every file and Gmail reads by `newer_than:`.
5. Leases with fencing tokens, for when the data moves to a container volume.

## Open decisions

1. Whether the board allows any scheduled write.
2. The default cadences ([integrations-design.md](integrations-design.md#defaults-from-rate-limits)), which also set each source's `stale_after`.
3. Task Scheduler or a service wrapper on this PC.
4. Incremental Google reads now, or full listings at a lower cadence until later.

## Sources

Fetched 2026-10-05: Google's Drive, Gmail, Sheets, Docs, Calendar, Tasks, and Vault limits pages (the per-minute quota units since May 1, 2026; Gmail 6,000 units a minute per user, `history.list` 2 units; Drive `files.list` 100 units); Drive changes and push guides; Zoom's rate limits; RFC 6585 and RFC 9110 on 429 and `Retry-After`; SQLite's transaction and WAL pages; APScheduler 3.11 and 4.0a6, Huey 3.4, RQ, Celery beat, Dramatiq; WinSW, Servy, NSSM, pywin32 releases; Docker's multi-service guidance. The repository: `jobs.py`, `locks.py`, `batches.py`, `google/gmail.py`, `google/drive.py`, `zoom/client.py`, `web/app.py`, `web/extra/status.py`.
