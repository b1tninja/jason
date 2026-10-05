"""jason's job queue: commands to run later, one at a time per shared resource, with a record of each run.

A job is a jason command line ("gmail --sync", "outlines --model --model-doc bylaws") with the resource it uses: the
GPU (a local model), the association's Google account, the PayHOA session, a county's public index, or nothing
shared. ``jason worker`` runs the queue: one job at a time per resource, jobs on different resources side by side, each in its own process with its output
in ``data/jobs/logs/<id>.log``. The table (``data/jobs.db``) keeps every job: when it was added, by whom, each attempt,
the exit code, and the last lines it printed.

The rules the queue keeps:

- a command that writes (it carries ``--yes``) is queued only with the name of the person who confirmed it, kept with
  the job; the worker never adds ``--yes`` to anything;
- a write is never retried: a failed write waits for a person. A read or a sync is retried up to ``max_attempts``;
- a command that needs a browser (``--interactive``) cannot be queued: the worker runs without one;
- a job on the GPU waits while ``jason.local_ai.preflight`` says the model cannot be loaded (Ollama down, no GPU, or not
  enough Windows commit), and is tried again later rather than failed.

The worker does not hold the GPU lock itself (the job's own model requests take it, and holding it would block them);
one worker per community with one queue per resource, and the machine's GPU lane lock (``GPU_LANE``) across
communities, keep two GPU jobs from running at once. Scheduling is ``jason.scheduler``'s (in ``jason serve``): it
only adds a job, as ``jason jobs add -- gmail --sync`` does, and the worker runs it.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from jason.locks import Resource, ResourceBusy, account, hold


class JobStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobClass(Enum):
    """The shared resource a job uses; the worker runs one job per class at a time."""

    GPU = "gpu"
    GOOGLE = "google"
    PAYHOA = "payhoa"
    COUNTY = "county"   # a county's public index (the recorder): a long read, kept off the local lane
    LOCAL = "local"


class JobRefused(ValueError):
    """The command cannot be queued as given."""


# Which resource a command uses: by its first word, and for some by a flag. A command not listed is local.
_GPU_FLAGS = ("--model", "--extractor", "--ocr", "--reader", "--terms-model")
# Model backends that run off this machine: a job that names one is not a GPU job (it waits on the network, not the card).
_REMOTE_BACKENDS = ("bedrock", "aws")
# The flags that name the Ollama model a GPU job loads, in the order they are read.
_MODEL_NAME_FLAGS = ("--model-name", "--terms-model-name", "--model")


def _flag_value(argv: list[str], flag: str) -> str | None:
    """The value given to ``flag`` ("--model x" or "--model=x"); "" when the flag stands alone; None when absent."""
    for n, a in enumerate(argv):
        if a == flag:
            nxt = argv[n + 1] if n + 1 < len(argv) else ""
            return "" if nxt.startswith("--") else nxt
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return None


def _flag_values(argv: list[str], flag: str) -> list[str]:
    """Every value given to a repeatable ``flag`` ("--channel a --channel=b")."""
    out = []
    for n, a in enumerate(argv):
        if a == flag and n + 1 < len(argv) and not argv[n + 1].startswith("--"):
            out.append(argv[n + 1])
        elif a.startswith(flag + "="):
            out.append(a.split("=", 1)[1])
    return out


def _remote(argv: list[str]) -> bool:
    return any((_flag_value(argv, f) or "").lower() in _REMOTE_BACKENDS for f in ("--model", "--terms-model"))


def job_model(argv: list[str]) -> str:
    """The Ollama model a GPU job will load: the one its flags name, else jason's model. A backend word ("ollama") is
    not a model name. "" for a job that loads no local model."""
    if job_class(argv) is not JobClass.GPU:
        return ""
    for flag in _MODEL_NAME_FLAGS:
        value = _flag_value(argv[1:], flag)
        if value and value.lower() not in ("ollama", "local") + _REMOTE_BACKENDS:
            return value
    from jason.community.ollama_extractor import DEFAULT_MODEL

    return DEFAULT_MODEL
_CLASS_OF_COMMAND: dict[str, JobClass] = {
    "gmail": JobClass.GOOGLE, "drive": JobClass.GOOGLE, "calendar": JobClass.GOOGLE, "templates": JobClass.GOOGLE,
    "vault": JobClass.GOOGLE, "photos": JobClass.GOOGLE, "forms": JobClass.GOOGLE, "drafts": JobClass.GOOGLE,
    "labels": JobClass.GOOGLE, "drive-activity": JobClass.GOOGLE, "meetings": JobClass.GOOGLE,
    "books": JobClass.PAYHOA, "budget": JobClass.PAYHOA, "reconcile": JobClass.PAYHOA, "invoices": JobClass.PAYHOA,
    "sync-bills": JobClass.PAYHOA, "catalog": JobClass.PAYHOA, "sync-catalog": JobClass.PAYHOA,
    "sync-tax": JobClass.COUNTY, "request-links": JobClass.PAYHOA, "ledger": JobClass.PAYHOA,
    "models": JobClass.GPU, "classify": JobClass.GPU, "read-documents": JobClass.GPU,
}


def job_class(argv: list[str]) -> JobClass:
    """The resource a jason command line uses."""
    if not argv:
        return JobClass.LOCAL
    if _remote(argv[1:]):
        return JobClass.LOCAL
    if any(a in _GPU_FLAGS or a.startswith(tuple(f + "=" for f in _GPU_FLAGS)) for a in argv[1:]):
        return JobClass.GPU
    if argv[0] == "board" and any(a in ("--sheet", "--tasks", "--doc", "--agenda") for a in argv[1:]):
        return JobClass.GOOGLE
    if argv[0] == "outlines" and "--fetch" in argv[1:]:
        return JobClass.GOOGLE
    if argv[0] == "onboard" and any(a in ("--locate", "--lookup") for a in argv[1:]):
        return JobClass.COUNTY
    # The integrations' refresh commands (jason.integrations.registry), so a scheduled read takes its account's lane.
    if argv[0] == "schedule" and "--read-google" in argv[1:]:
        return JobClass.GOOGLE
    if (argv[0] == "meetings" and "--sync" in argv[1:]) or (argv[0] == "utilities" and "--payments" in argv[1:]):
        return JobClass.PAYHOA         # meetings --sync reads PayHOA's notices (and Zoom); utilities --payments, PayHOA
    if argv[0] == "responses":
        # A check of the PayHOA channel alone takes PayHOA's lane; any other check (Gmail, mailed scans, Google Forms, or
        # every channel) and a --read (an email's attachments) take Google's. Listing, confirming, and the rest read disk.
        channels = {v.lower() for v in _flag_values(argv[1:], "--channel")}
        if "--check" in argv[1:]:
            return JobClass.PAYHOA if channels == {"payhoa"} else JobClass.GOOGLE
        if "--read" in argv[1:]:
            return JobClass.GOOGLE
        return JobClass.LOCAL
    return _CLASS_OF_COMMAND.get(argv[0], JobClass.LOCAL)


@dataclass
class Job:
    id: int
    argv: list[str]
    job_class: JobClass
    status: JobStatus
    writes: bool
    confirmed_by: str
    created: str
    attempts: int = 0
    max_attempts: int = 1
    not_before: str = ""
    started: str = ""
    finished: str = ""
    pid: int = 0
    exit_code: int | None = None
    summary: str = ""
    note: str = ""

    @property
    def command(self) -> str:
        return "jason " + " ".join(self.argv)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    argv TEXT NOT NULL,
    job_class TEXT NOT NULL,
    status TEXT NOT NULL,
    writes INTEGER NOT NULL,
    confirmed_by TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 1,
    not_before TEXT NOT NULL DEFAULT '',
    started TEXT NOT NULL DEFAULT '',
    finished TEXT NOT NULL DEFAULT '',
    pid INTEGER NOT NULL DEFAULT 0,
    exit_code INTEGER,
    summary TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT ''
)
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect(data_dir: Path) -> sqlite3.Connection:
    path = Path(data_dir) / "jobs.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def _job(row: sqlite3.Row) -> Job:
    raw = dict(row)
    return Job(**{**raw, "argv": json.loads(raw["argv"]), "job_class": JobClass(raw["job_class"]),
                  "status": JobStatus(raw["status"]), "writes": bool(raw["writes"])})


def log_path(data_dir: Path, job_id: int) -> Path:
    path = Path(data_dir) / "jobs" / "logs" / f"{job_id}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def add(data_dir: Path, argv: list[str], *, confirmed_by: str = "", max_attempts: int = 3,
        job_class_override: JobClass | None = None) -> Job:
    """Queue a jason command line (without the leading "jason")."""
    argv = [a for a in argv if a != "--"]
    if not argv:
        raise JobRefused("give the jason command to run, after --")
    if argv[0] in ("worker", "jobs", "login", "serve", "daemon"):
        raise JobRefused(f"`jason {argv[0]}` is not a job")
    if "--interactive" in argv:
        raise JobRefused("a command that needs a browser (--interactive) cannot run in the worker; run it yourself")
    writes = "--yes" in argv
    if writes and not confirmed_by.strip():
        raise JobRefused("this command writes (--yes); queue it with --confirm NAME, the person who approved it")
    cls = job_class_override or job_class(argv)
    with _connect(data_dir) as conn:
        cur = conn.execute("INSERT INTO jobs (argv, job_class, status, writes, confirmed_by, created, max_attempts) VALUES (?,?,?,?,?,?,?)",
                           (json.dumps(argv), cls.value, JobStatus.QUEUED.value, int(writes), confirmed_by.strip(), _now(),
                            1 if writes else max(1, max_attempts)))
        job_id = cur.lastrowid
    return get(data_dir, int(job_id))


def get(data_dir: Path, job_id: int) -> Job:
    with _connect(data_dir) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise KeyError(job_id)
    return _job(row)


def jobs(data_dir: Path, *, every: bool = False, limit: int = 50) -> list[Job]:
    query = "SELECT * FROM jobs" + ("" if every else " WHERE status IN ('queued','running','failed')") + " ORDER BY id DESC LIMIT ?"
    with _connect(data_dir) as conn:
        return [_job(r) for r in conn.execute(query, (limit,)).fetchall()]


def cancel(data_dir: Path, job_id: int) -> Job:
    """Cancel a queued job, or retire a failed one. A running job is left to finish."""
    with _connect(data_dir) as conn:
        changed = conn.execute("UPDATE jobs SET status = ?, finished = ?, note = 'cancelled by a person' WHERE id = ? AND status IN ('queued','failed')",
                               (JobStatus.CANCELLED.value, _now(), job_id)).rowcount
    job = get(data_dir, job_id)
    if not changed:
        raise JobRefused(f"job {job_id} is {job.status.value}; only a queued or failed job can be cancelled")
    return job


def _claim(data_dir: Path, cls: JobClass, *, loaded: frozenset[str] = frozenset()) -> Job | None:
    """Take a queued job of ``cls`` that is due, marking it running: the oldest, except that on the GPU lane the
    oldest job whose model is already loaded (``loaded``, Ollama's names) goes first, so a loaded model is used
    before another is loaded in its place."""
    with _connect(data_dir) as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute("SELECT * FROM jobs WHERE status = 'queued' AND job_class = ? AND (not_before = '' OR not_before <= ?) "
                            "ORDER BY id", (cls.value, _now())).fetchall()
        row = rows[0] if rows else None
        if rows and cls is JobClass.GPU and loaded:
            row = next((r for r in rows if _loaded_as(job_model(json.loads(r["argv"])), loaded)), rows[0])
        if row is None:
            conn.execute("COMMIT")
            return None
        conn.execute("UPDATE jobs SET status = 'running', started = ?, attempts = attempts + 1, note = '' WHERE id = ?",
                     (_now(), row["id"]))
        conn.execute("COMMIT")
    return get(data_dir, row["id"])


def _loaded_as(model: str, loaded: frozenset[str]) -> bool:
    """Whether ``model`` ("qwen3.6:27b", or "qwen3.6" for its latest tag) is among Ollama's loaded names."""
    return bool(model) and any(n == model or n.split(":")[0] == model or n == model + ":latest" for n in loaded)


def loaded_models(ollama_url: str = "") -> frozenset[str]:
    """The models Ollama has loaded now; empty when it does not answer."""
    from jason.local_ai import OLLAMA_URL, _get

    try:
        return frozenset(m["name"] for m in _get(f"{ollama_url or OLLAMA_URL}/api/ps").get("models", []))
    except (OSError, ValueError):
        return frozenset()


def queued_models(data_dir: Path) -> set[str]:
    """The models the queued and running GPU jobs need."""
    with _connect(data_dir) as conn:
        rows = conn.execute("SELECT argv FROM jobs WHERE job_class = 'gpu' AND status IN ('queued','running')").fetchall()
    return {job_model(json.loads(r["argv"])) for r in rows}


def release_idle(data_dir: Path, *, loaded: frozenset[str], shared: str = "", unload: Callable[[str], Any] | None = None
                 ) -> list[str]:
    """Unload each loaded model no queued or running GPU job needs, except ``shared`` (jason's own model, which
    AnythingLLM's chat also uses at the same context, so keeping it loaded serves both). Returns what it unloaded."""
    needed = queued_models(data_dir)
    if unload is None:
        from jason.local_ai import unload as unload_model

        unload = unload_model
    out = []
    for name in sorted(loaded):
        if _loaded_as(shared, frozenset({name})) or any(_loaded_as(m, frozenset({name})) for m in needed):
            continue
        if name.startswith(("qwen3-embedding", "nomic-embed", "mxbai-embed")):
            continue                             # the embedder serves search; it is small and always wanted
        unload(name)
        out.append(name)
    return out


def _finish(data_dir: Path, job: Job, code: int, summary: str, *, retry_in: float = 0.0, note: str = "") -> None:
    retry = code != 0 and not job.writes and job.attempts < job.max_attempts
    status = JobStatus.QUEUED if retry else JobStatus.DONE if code == 0 else JobStatus.FAILED
    not_before = datetime.fromtimestamp(time.time() + retry_in, timezone.utc).isoformat(timespec="seconds") if retry else ""
    with _connect(data_dir) as conn:
        conn.execute("UPDATE jobs SET status = ?, finished = ?, exit_code = ?, summary = ?, not_before = ?, pid = 0, note = ? WHERE id = ?",
                     (status.value, _now(), code, summary, not_before, note or (f"retrying, attempt {job.attempts + 1} of {job.max_attempts}" if retry else ""),
                      job.id))


def _defer(data_dir: Path, job: Job, reason: str, seconds: float) -> None:
    """Put a claimed job back without counting the attempt (the model could not be loaded right now)."""
    until = datetime.fromtimestamp(time.time() + seconds, timezone.utc).isoformat(timespec="seconds")
    with _connect(data_dir) as conn:
        conn.execute("UPDATE jobs SET status = 'queued', attempts = attempts - 1, started = '', not_before = ?, note = ? WHERE id = ?",
                     (until, f"waiting: {reason}"[:300], job.id))


def run_job(data_dir: Path, job: Job, *, python: str = sys.executable, env_file: str | None = None,
            runner: Callable[..., int] | None = None, profile: str = "") -> tuple[int, str]:
    """Run one claimed job in its own process; returns its exit code and the last lines it printed. With ``profile``
    the process runs as that community (``JASON_PROFILE``), so one ``jason serve --all`` runs each profile's jobs as
    its own."""
    argv = list(job.argv) + (["--env", env_file] if env_file and "--env" not in job.argv else [])
    out = log_path(data_dir, job.id)
    with out.open("a", encoding="utf-8") as log:
        log.write(f"\n== attempt {job.attempts} at {_now()}: jason {' '.join(job.argv)}\n")
        log.flush()
        if runner is not None:
            code = runner(argv, log)
        else:
            # Unbuffered, so `jason jobs show` follows a long job as it prints.
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1",
                   **({"JASON_PROFILE": profile} if profile else {})}
            proc = subprocess.Popen([python, "-m", "jason.cli", *argv], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    env=env, cwd=os.getcwd())
            with _connect(data_dir) as conn:
                conn.execute("UPDATE jobs SET pid = ? WHERE id = ?", (proc.pid, job.id))
            code = proc.wait()
    tail = out.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]
    return code if isinstance(code, int) else 1, "\n".join(tail)[-1500:]


GPU_LANE = "jobs-gpu-lane"      # the machine's GPU lane (Resource.STORE), shared by every community's worker


def worker_guard(profile: str) -> str:
    """The key of a community's worker lock (``Resource.STORE``): one worker per community on this machine, and two
    communities' workers side by side. An OS byte-lock, so a crashed worker leaves it free."""
    return f"jobs-worker-{profile}"


def work(data_dir: Path, *, once: bool = False, poll: float = 20.0, env_file: str | None = None,
         preflight: Callable[..., None] | None = None, runner: Callable[..., int] | None = None,
         log: Callable[[str], None] = print, retry_in: float = 300.0, defer_for: float = 600.0,
         loaded: Callable[[], frozenset[str]] | None = None, release_models: bool = False,
         unload: Callable[[str], Any] | None = None, profile: str = "", stop: threading.Event | None = None,
         current: dict[str, Any] | None = None) -> dict[str, int]:
    """Run the queue: one thread per job class, each taking that class's jobs one at a time. With ``once``, return when
    every class has nothing due; else keep polling. Only one worker runs at a time for a community (the
    ``jobs-worker-<profile>`` lock, ``profile`` the active one by default), and each job runs as that community.

    ``stop``, set by another thread (``jason serve`` on Ctrl-C or a drain request), stops the lanes as Ctrl-C does:
    each finishes its running job and takes no more. ``current`` is filled with each lane's running job (id, command,
    since; None when idle), for the heartbeat.

    The worker holds no service lock (``Resource.PAYHOA``, ``Resource.GOOGLE``) itself: a job's own process takes it
    where it writes, and holding it here would refuse that process. One lane per resource keeps the community's jobs
    on one account apart.

    The GPU lane schedules by model: it asks which models Ollama has loaded (``loaded``), takes the oldest job whose
    model is loaded before an older one that would load another, and checks the job's own model with preflight (a
    9B job is not held back by the 27B's memory). With ``release_models``, after each GPU job it unloads the models no
    queued job needs, except jason's shared model (``release_idle``), so the next model finds the commit free."""
    from jason.config import apply_temp_dir

    apply_temp_dir(env_file)      # each job process inherits the worker's TEMP (JASON_TEMP_DIR), and applies it itself
    counts = {"done": 0, "failed": 0, "retried": 0, "deferred": 0, "released": 0}
    lock = threading.Lock()
    stop = stop if stop is not None else threading.Event()
    community = account(profile)
    lanes: dict[str, Any] = current if current is not None else {}
    lanes.update({cls.value: None for cls in JobClass})
    from jason.community.ollama_extractor import DEFAULT_MODEL

    def model_ready(model: str) -> str:
        check = preflight
        if check is None:
            from jason.local_ai import preflight as check  # type: ignore[no-redef]
        try:
            try:
                check(model or DEFAULT_MODEL)
            except TypeError:                 # a preflight that takes no model
                check()
        except Exception as exc:              # LocalAIUnavailable, or the server not answering
            return str(exc)
        return ""

    def lane(cls: JobClass) -> None:
        while not stop.is_set():
            now_loaded = (loaded or loaded_models)() if cls is JobClass.GPU else frozenset()
            job = _claim(data_dir, cls, loaded=now_loaded)
            if job is None:
                if once:
                    return
                stop.wait(poll)
                continue
            if cls is JobClass.GPU and (reason := model_ready(job_model(job.argv))):
                _defer(data_dir, job, reason, defer_for)
                with lock:
                    counts["deferred"] += 1
                log(f"job {job.id} waits: {reason}")
                if once:
                    return
                continue
            with ExitStack() as gate:
                if cls is JobClass.GPU:
                    # The card is the machine's, not the community's: one model job at a time across every community's
                    # worker. Not the GPU lock itself, which the job's own model requests take.
                    try:
                        gate.enter_context(hold(Resource.STORE, GPU_LANE, timeout=1, purpose=f"job {job.id} ({community})"))
                    except ResourceBusy as exc:
                        reason = f"another community's model job is running ({exc})"
                        _defer(data_dir, job, reason, defer_for)
                        with lock:
                            counts["deferred"] += 1
                        log(f"job {job.id} waits: {reason}")
                        if once:
                            return
                        continue
                log(f"job {job.id} [{cls.value}] starts: {job.command}")
                lanes[cls.value] = {"id": job.id, "command": job.command, "since": _now()}
                try:
                    code, summary = run_job(data_dir, job, env_file=env_file, runner=runner, profile=community)
                except Exception as exc:          # the process could not start, or the runner failed: the job fails, the lane goes on
                    code, summary = 1, f"the job could not run: {exc}"
                finally:
                    lanes[cls.value] = None
                _finish(data_dir, job, code, summary, retry_in=retry_in)
                after = get(data_dir, job.id)
                with lock:
                    key = "done" if after.status is JobStatus.DONE else "retried" if after.status is JobStatus.QUEUED else "failed"
                    counts[key] += 1
                log(f"job {job.id} {after.status.value} (exit {code})")
                if cls is JobClass.GPU and release_models:
                    try:
                        gone = release_idle(data_dir, loaded=(loaded or loaded_models)(), shared=DEFAULT_MODEL, unload=unload)
                    except Exception as exc:      # noqa: BLE001 - Ollama gone: nothing to release
                        log(f"could not release idle models: {exc}")
                        gone = []
                    if gone:
                        with lock:
                            counts["released"] += len(gone)
                        log(f"released {', '.join(gone)}: no queued job needs them")

    try:
        with hold(Resource.STORE, worker_guard(community), timeout=1, purpose=f"jason worker ({community})"):
            # Only one worker runs, so a job still marked running was left by a worker that stopped mid-job.
            with _connect(data_dir) as conn:
                stale = [_job(r) for r in conn.execute("SELECT * FROM jobs WHERE status = 'running'").fetchall()]
            for job in stale:
                _finish(data_dir, job, 1, job.summary, retry_in=0, note="the worker stopped while this job ran")
                log(f"job {job.id} was left running by a worker that stopped")
            threads =[threading.Thread(target=lane, args=(cls,), daemon=True) for cls in JobClass]
            for t in threads:
                t.start()
            try:
                while any(t.is_alive() for t in threads):
                    for t in threads:
                        t.join(timeout=1)
            except KeyboardInterrupt:
                stop.set()
                log("stopping after the running jobs finish")
                for t in threads:
                    t.join()
    except ResourceBusy as exc:
        raise JobRefused(f"another worker is running for {community} ({exc})") from exc
    return counts


def lines(items: list[Job]) -> list[str]:
    out = []
    for j in items:
        who = f"; confirmed by {j.confirmed_by}" if j.confirmed_by else ""
        out.append(f"{j.id:>4} {j.status.value:<9} [{j.job_class.value:<6}] {j.command}")
        model = job_model(j.argv) if j.job_class is JobClass.GPU else ""
        detail = f"added {j.created}{who}; attempt {j.attempts} of {j.max_attempts}" + (f"; model {model}" if model else "")
        if j.finished:
            detail += f"; finished {j.finished} (exit {j.exit_code})"
        if j.note:
            detail += f"; {j.note}"
        out.append(f"       {detail}")
    return out


__all__ = ["JobStatus", "JobClass", "JobRefused", "Job", "job_class", "add", "get", "jobs", "cancel", "work", "run_job",
           "log_path", "lines", "worker_guard"]
