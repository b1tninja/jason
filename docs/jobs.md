# The job queue

jason's commands can run later, in order, without a person at the terminal: a nightly Gmail sync, the board Sheet and Tasks sync, a long model pass over the documents. `jason jobs` keeps the queue and `jason worker` runs it (`jason.jobs`).

## Adding a job

```bash
jason jobs add -- gmail --sync
```

Everything after `--` is the jason command, without the word "jason". The queue guesses the resource the command uses from its name and flags; `--resource` corrects a wrong guess:
- **gpu:** a local model, such as `outlines --model`, `models`, or anything with `--model`, `--extractor`, `--ocr`,
  `--reader`, or `--terms-model`. A command that names a model off this machine (`--model bedrock`,
  `--terms-model bedrock`) is local: it waits on the network, not the card;
- **google:** the association's Google account, such as `gmail`, `drive`, `calendar`, `templates`, `board --sheet`, `schedule --read-google`, or `outlines --fetch`;
- **payhoa:** the PayHOA session, such as `books`, `budget`, `reconcile`, `invoices`, `sync-catalog`, `meetings --sync`, or `utilities --payments`;
- **county:** a county's public index, such as `onboard --locate`, `onboard --lookup`, or `sync-tax` (the console's "locate" button queues the first). A locate runs dozens of searches, so it keeps its own lane and never holds up the local jobs;
- **local:** everything else.

**Rules the queue keeps:**
- **A command that writes** (it carries `--yes`) is queued only with `--confirm NAME`, the person who approved it. The job keeps that name and time. The worker never adds `--yes` to anything.
- **A write runs once.** A failed write waits for a person. A read or sync is retried up to `--max-attempts` times (three by default), five minutes apart.
- **A command that needs a browser** (`--interactive`) cannot be queued; the worker runs without one.
- `worker`, `jobs`, and `login` are not jobs.

## Running the queue

```bash
jason worker --once
```

- **One lane per resource.** The worker runs one job at a time per resource, and jobs on different resources side by side. Two model jobs never run together, but a Gmail sync can run during a model pass.
- **Each job is its own process,** with its output in `data/jobs/logs/<id>.log`.
- **`--once`** stops when nothing is due; without it the worker keeps polling (`--poll`, 20 seconds).
- **One worker per community.** Its guard is `jobs-worker-<profile>` (an OS lock, freed by a crash). A second worker for the same community stops with "another worker is running"; another community's worker runs beside it. Each job runs as its worker's community (`JASON_PROFILE`).
- **The GPU is the machine's.** Model jobs never run two at a time across communities: a GPU job that finds another community's model job running waits ten minutes without using an attempt.
- **The service locks are per community.** `Resource.PAYHOA` and `Resource.GOOGLE` are keyed by the community (`locks.account()`, lock `payhoa-<profile>`). The worker holds neither; a job's own process takes the lock where it writes (a PayHOA batch, an approval's apply).
- **A model job waits for its own model.** Each GPU job's model is the one its flags name (`--model-name`,
  `--terms-model-name`, `--model NAME`), else jason's model (`jason jobs` shows it). Before the job starts, the worker
  runs the same check as `jason local-ai` for that model: a 9B job is not held back by the 27B's memory. If Ollama is
  down, has no GPU, or Windows commit is too full to load the model, the job goes back in the queue for ten minutes
  without using an attempt. A model already loaded needs no new commit.
- **A loaded model is used first.** The GPU lane asks Ollama what is loaded and takes the oldest job whose model is
  loaded before an older job that would load another. Jobs for the same model run back to back.
- **One model serves jason and AnythingLLM.** jason's model callers ask for `qwen3.6:27b` with a 65,536-token context,
  and AnythingLLM's chat asks for the same (`jason local-ai` shows both). Ollama reloads a model whose context
  differs, so a caller that changes either reloads it for everyone; OCR's own context is the known exception.
- **Idle models are released.** After each GPU job, the worker unloads every model no queued or running job needs.
  It keeps jason's shared model (AnythingLLM uses it too) and the embedder, so the next model finds the commit free.
  `--keep-models` turns this off.
- **The worker holds no GPU lock itself.** Each model request in the job takes the lock (`jason.locks`), and the lanes keep two model jobs apart.
- **A worker that stopped mid-job** leaves the job marked running. The next worker finds it and records it as stopped: a read is queued again, and a write fails and waits for a person.

## Looking at the queue

- `jason jobs`: queued, running, and failed jobs; `--all` for every job.
- `jason jobs show ID`: one job, with the end of its log (`--tail`).
- `jason jobs cancel ID`: cancels a queued job, or retires a failed one. A running job is left to finish.
- The read-only MCP tool `jobs_status` gives the same.

The table is `data/jobs.db` (SQLite). It records, for each job:
- the command and the resource it uses;
- its status and attempts;
- who confirmed a write;
- the start and finish times and the exit code;
- the last lines the job printed.

## Scheduling

**Running the worker at boot:** `jason serve` runs jason-web and the worker in one process (`--profile P` or `--all`, `--no-web`, `--no-worker`). `jason serve --install-task` prints the Task Scheduler entry that starts it at boot (restart on failure, no time limit); with `--yes`, from a terminal run as administrator, it creates it. `jason daemon status` reads each community's heartbeat (`<data>/jobs/heartbeat.json`); `jason daemon stop` asks the process to drain and stop. See [scheduler-daemon-design.md](scheduler-daemon-design.md).

**Scheduling the jobs:** `jason serve`'s scheduler (`jason.scheduler`) adds each source's refresh to the queue on its cadence, as an ordinary job; the worker runs it.
- **The schedules** are a `schedules` table in the community's `jobs.db`, one row per source the integrations registry declares (`jason integrations list` shows them), seeded with the registry's default cadence, window, and floor.
- **A person adopts each one first:** `jason cadence --restore SOURCE --by NAME` (or `--restore-all`) adopts the default; `jason cadence SOURCE --every 30m --by NAME` (or `--cron "0 2 * * *"`, `--window 07-22`) adopts a change, refused faster than the floor. `jason cadence` lists them; `--pause SOURCE --why TEXT --by NAME`, `--resume`, and `--run-now` do what they say. Each change keeps who and when.
- **One at a time:** a source whose job (or a person's job for the same command) is queued or running is not added again; a run missed while jason was down is one catch-up run.
- **Failures back off** (five minutes, or the floor, doubled each time, to a day; longer when the job printed a `Retry-After`). A sign-in failure pauses the integration's sources until a person signs in (`jason integrations check KEY --live`) or runs `jason cadence --resume`; nothing retries it on a timer.
- **The scheduler never schedules a write** (a command with `--yes`). Approving a schedule of writes is the board's decision, not jason's; until then a write is queued by a person with `--confirm`.
- `jason serve --no-scheduler` turns it off. The decisions are logged in `<data>/jobs/scheduler.jsonl`; `jason daemon status` shows the next five runs.

The older `schtasks` entries are replaced: `jason serve --install-task` replaces `schtasks /Create /SC ONLOGON /TN "jason worker" ...` (remove it so the two do not race for the worker's guard), and the scheduler replaces a daily `jobs add` task such as "jason gmail sync" (remove it once its source is adopted).
