# The job queue

jason's commands can run later, in order, without a person at the terminal: a nightly Gmail sync, the board Sheet and Tasks sync, a long model pass over the documents. `jason jobs` keeps the queue and `jason worker` runs it (`jason.jobs`).

## Adding a job

```bash
jason jobs add -- gmail --sync
```

Everything after `--` is the jason command, without the word "jason". The queue guesses the resource the command uses from its name and flags; `--resource` corrects a wrong guess:
- **gpu:** a local model, such as `outlines --model`, `models`, or anything with `--model`, `--extractor`, `--ocr`, or `--reader`;
- **google:** the association's Google account, such as `gmail`, `drive`, `calendar`, `templates`, `board --sheet`, or `outlines --fetch`;
- **payhoa:** the PayHOA session, such as `books`, `budget`, `reconcile`, or `invoices`;
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
- **Only one worker runs at a time.** A second one stops with "another worker is running".
- **A model job waits for the model.** Before a GPU job starts, the worker runs the same check as `jason local-ai`. If Ollama is down, has no GPU, or Windows commit is too full to load the model, the job goes back in the queue for ten minutes without using an attempt.
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

Scheduling stays with Windows. A scheduled task only adds a job; the worker, started at sign-in, runs it. Setting up the tasks is a person's step. For example, in a terminal:

```bash
schtasks /Create /SC DAILY /ST 02:00 /TN "jason gmail sync" /TR "D:\code\jason\.venv\Scripts\jason.exe jobs add -- gmail --sync"
```

```bash
schtasks /Create /SC ONLOGON /TN "jason worker" /TR "D:\code\jason\.venv\Scripts\jason.exe worker"
```

A write that should run on a schedule needs its approval recorded at the time it is scheduled (`--confirm`). Approving a whole schedule of writes is the board's decision, not jason's.
