"""jason's job queue: commands to run later, one at a time per shared resource, with a record of each run.

A job is a jason command line ("gmail --sync", "outlines --model --model-doc bylaws") with the resource it uses: the
GPU (a local model), the association's Google account, the PayHOA session, or nothing shared. ``jason worker`` runs the
queue: one job at a time per resource, jobs on different resources side by side, each in its own process with its output
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
one worker with one queue per resource keeps two GPU jobs from running at once. Scheduling stays with Windows: a
scheduled task only adds a job (``jason jobs add -- gmail --sync``), and the worker runs it.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from jason.locks import Resource, ResourceBusy, hold


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
    LOCAL = "local"


class JobRefused(ValueError):
    """The command cannot be queued as given."""


# Which resource a command uses: by its first word, and for some by a flag. A command not listed is local.
_GPU_FLAGS = ("--model", "--extractor", "--ocr", "--reader")
_CLASS_OF_COMMAND: dict[str, JobClass] = {
    "gmail": JobClass.GOOGLE, "drive": JobClass.GOOGLE, "calendar": JobClass.GOOGLE, "templates": JobClass.GOOGLE,
    "vault": JobClass.GOOGLE, "photos": JobClass.GOOGLE, "forms": JobClass.GOOGLE, "drafts": JobClass.GOOGLE,
    "labels": JobClass.GOOGLE, "drive-activity": JobClass.GOOGLE, "meetings": JobClass.GOOGLE,
    "books": JobClass.PAYHOA, "budget": JobClass.PAYHOA, "reconcile": JobClass.PAYHOA, "invoices": JobClass.PAYHOA,
    "sync-bills": JobClass.PAYHOA, "catalog": JobClass.PAYHOA, "request-links": JobClass.PAYHOA, "ledger": JobClass.PAYHOA,
    "models": JobClass.GPU, "classify": JobClass.GPU, "read-documents": JobClass.GPU,
}


def job_class(argv: list[str]) -> JobClass:
    """The resource a jason command line uses."""
    if not argv:
        return JobClass.LOCAL
    if any(a in _GPU_FLAGS or a.startswith(tuple(f + "=" for f in _GPU_FLAGS)) for a in argv[1:]):
        return JobClass.GPU
    if argv[0] == "board" and any(a in ("--sheet", "--tasks", "--doc", "--agenda") for a in argv[1:]):
        return JobClass.GOOGLE
    if argv[0] == "outlines" and "--fetch" in argv[1:]:
        return JobClass.GOOGLE
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
    if argv[0] in ("worker", "jobs", "login"):
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


def _claim(data_dir: Path, cls: JobClass) -> Job | None:
    """Take the oldest queued job of ``cls`` that is due, marking it running."""
    with _connect(data_dir) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM jobs WHERE status = 'queued' AND job_class = ? AND (not_before = '' OR not_before <= ?) "
                           "ORDER BY id LIMIT 1", (cls.value, _now())).fetchone()
        if row is None:
            conn.execute("COMMIT")
            return None
        conn.execute("UPDATE jobs SET status = 'running', started = ?, attempts = attempts + 1, note = '' WHERE id = ?",
                     (_now(), row["id"]))
        conn.execute("COMMIT")
    return get(data_dir, row["id"])


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
            runner: Callable[..., int] | None = None) -> tuple[int, str]:
    """Run one claimed job in its own process; returns its exit code and the last lines it printed."""
    argv = list(job.argv) + (["--env", env_file] if env_file and "--env" not in job.argv else [])
    out = log_path(data_dir, job.id)
    with out.open("a", encoding="utf-8") as log:
        log.write(f"\n== attempt {job.attempts} at {_now()}: jason {' '.join(job.argv)}\n")
        log.flush()
        if runner is not None:
            code = runner(argv, log)
        else:
            # Unbuffered, so `jason jobs show` follows a long job as it prints.
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
            proc = subprocess.Popen([python, "-m", "jason.cli", *argv], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    env=env, cwd=os.getcwd())
            with _connect(data_dir) as conn:
                conn.execute("UPDATE jobs SET pid = ? WHERE id = ?", (proc.pid, job.id))
            code = proc.wait()
    tail = out.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]
    return code if isinstance(code, int) else 1, "\n".join(tail)[-1500:]


def work(data_dir: Path, *, once: bool = False, poll: float = 20.0, env_file: str | None = None,
         preflight: Callable[[], None] | None = None, runner: Callable[..., int] | None = None,
         log: Callable[[str], None] = print, retry_in: float = 300.0, defer_for: float = 600.0) -> dict[str, int]:
    """Run the queue: one thread per job class, each taking that class's jobs one at a time. With ``once``, return when
    every class has nothing due; else keep polling. Only one worker runs at a time (the jobs-worker lock)."""
    counts = {"done": 0, "failed": 0, "retried": 0, "deferred": 0}
    lock = threading.Lock()
    stop = threading.Event()

    def model_ready() -> str:
        if preflight is not None:
            try:
                preflight()
            except Exception as exc:          # LocalAIUnavailable, or the server not answering
                return str(exc)
            return ""
        from jason.local_ai import LocalAIUnavailable
        from jason.local_ai import preflight as check

        try:
            check()
        except LocalAIUnavailable as exc:
            return str(exc)
        return ""

    def lane(cls: JobClass) -> None:
        while not stop.is_set():
            job = _claim(data_dir, cls)
            if job is None:
                if once:
                    return
                stop.wait(poll)
                continue
            if cls is JobClass.GPU and (reason := model_ready()):
                _defer(data_dir, job, reason, defer_for)
                with lock:
                    counts["deferred"] += 1
                log(f"job {job.id} waits: {reason}")
                if once:
                    return
                continue
            log(f"job {job.id} [{cls.value}] starts: {job.command}")
            try:
                code, summary = run_job(data_dir, job, env_file=env_file, runner=runner)
            except Exception as exc:          # the process could not start, or the runner failed: the job fails, the lane goes on
                code, summary = 1, f"the job could not run: {exc}"
            _finish(data_dir, job, code, summary, retry_in=retry_in)
            after = get(data_dir, job.id)
            with lock:
                key = "done" if after.status is JobStatus.DONE else "retried" if after.status is JobStatus.QUEUED else "failed"
                counts[key] += 1
            log(f"job {job.id} {after.status.value} (exit {code})")

    try:
        with hold(Resource.STORE, "jobs-worker", timeout=1, purpose="jason worker"):
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
        raise JobRefused(f"another worker is running ({exc})") from exc
    return counts


def lines(items: list[Job]) -> list[str]:
    out = []
    for j in items:
        who = f"; confirmed by {j.confirmed_by}" if j.confirmed_by else ""
        out.append(f"{j.id:>4} {j.status.value:<9} [{j.job_class.value:<6}] {j.command}")
        detail = f"added {j.created}{who}; attempt {j.attempts} of {j.max_attempts}"
        if j.finished:
            detail += f"; finished {j.finished} (exit {j.exit_code})"
        if j.note:
            detail += f"; {j.note}"
        out.append(f"       {detail}")
    return out


__all__ = ["JobStatus", "JobClass", "JobRefused", "Job", "job_class", "add", "get", "jobs", "cancel", "work", "run_job",
           "log_path", "lines"]
