import pytest

from jason import jobs
from jason.jobs import JobClass, JobRefused, JobStatus


def test_job_classes():
    assert jobs.job_class(["gmail", "--sync"]) is JobClass.GOOGLE
    assert jobs.job_class(["outlines", "--model", "--model-doc", "bylaws"]) is JobClass.GPU
    assert jobs.job_class(["outlines", "--fetch"]) is JobClass.GOOGLE
    assert jobs.job_class(["board", "--sheet", "--tasks"]) is JobClass.GOOGLE
    assert jobs.job_class(["books", "--sync"]) is JobClass.PAYHOA
    assert jobs.job_class(["local-ai", "--check"]) is JobClass.LOCAL


def test_the_queue_refuses_unconfirmed_writes_browsers_and_itself(tmp_path):
    with pytest.raises(JobRefused, match="--confirm"):
        jobs.add(tmp_path, ["board", "--packet", "--doc", "--yes"])
    with pytest.raises(JobRefused, match="browser"):
        jobs.add(tmp_path, ["gmail", "--sync", "--interactive"])
    with pytest.raises(JobRefused, match="not a job"):
        jobs.add(tmp_path, ["worker"])
    write = jobs.add(tmp_path, ["--", "board", "--packet", "--doc", "--yes"], confirmed_by="Treasurer", max_attempts=5)
    assert write.writes and write.max_attempts == 1 and write.confirmed_by == "Treasurer" and write.argv[0] == "board"


def _runner(codes):
    """A fake process: each command's exit codes in order (lanes run in parallel, so by command, not by call)."""
    calls = []

    def run(argv, log):
        calls.append(argv)
        log.write(f"ran {' '.join(argv)}\n")
        return codes[argv[0]].pop(0)
    return run, calls


def test_a_read_is_retried_and_a_write_is_not(tmp_path):
    read = jobs.add(tmp_path, ["gmail", "--sync"], max_attempts=2)
    write = jobs.add(tmp_path, ["templates", "--rewrite", "agenda", "--yes"], confirmed_by="Secretary")
    run, calls = _runner({"gmail": [1, 0], "templates": [1]})
    counts = jobs.work(tmp_path, once=True, runner=run, retry_in=3600, log=lambda s: None)
    assert jobs.get(tmp_path, write.id).status is JobStatus.FAILED            # a write waits for a person
    after = jobs.get(tmp_path, read.id)
    assert after.status is JobStatus.QUEUED and after.attempts == 1 and "retrying" in after.note
    assert counts["failed"] == 1 and counts["retried"] == 1
    import sqlite3

    with sqlite3.connect(tmp_path / "jobs.db") as conn:                       # make the retry due now
        conn.execute("UPDATE jobs SET not_before = '' WHERE id = ?", (read.id,))
    jobs.work(tmp_path, once=True, runner=run, retry_in=0, log=lambda s: None)
    done = jobs.get(tmp_path, read.id)
    assert done.status is JobStatus.DONE and done.attempts == 2 and "ran gmail --sync" in done.summary
    assert jobs.cancel(tmp_path, write.id).status is JobStatus.CANCELLED
    with pytest.raises(JobRefused, match="only a queued or failed"):
        jobs.cancel(tmp_path, read.id)


def test_a_gpu_job_waits_while_the_model_cannot_load(tmp_path):
    job = jobs.add(tmp_path, ["outlines", "--model"])
    run, calls = _runner({"outlines": [0]})

    def not_ready():
        raise RuntimeError("Windows commit is nearly full")
    counts = jobs.work(tmp_path, once=True, runner=run, preflight=not_ready, defer_for=0, log=lambda s: None)
    waiting = jobs.get(tmp_path, job.id)
    assert counts["deferred"] == 1 and not calls
    assert waiting.status is JobStatus.QUEUED and waiting.attempts == 0 and "commit" in waiting.note
    jobs.work(tmp_path, once=True, runner=run, preflight=lambda: None, log=lambda s: None)
    assert jobs.get(tmp_path, job.id).status is JobStatus.DONE and calls == [["outlines", "--model"]]


def test_a_job_whose_runner_fails_or_whose_worker_stopped_is_not_left_running(tmp_path):
    import sqlite3

    def broken(argv, log):
        raise OSError("could not start")
    write = jobs.add(tmp_path, ["templates", "--rewrite", "agenda", "--yes"], confirmed_by="Secretary")
    jobs.work(tmp_path, once=True, runner=broken, log=lambda s: None)
    assert jobs.get(tmp_path, write.id).status is JobStatus.FAILED and "could not run" in jobs.get(tmp_path, write.id).summary
    read = jobs.add(tmp_path, ["gmail", "--sync"])
    with sqlite3.connect(tmp_path / "jobs.db") as conn:                       # a worker died mid-job
        conn.execute("UPDATE jobs SET status = 'running', attempts = 1 WHERE id = ?", (read.id,))
    run, _ = _runner({"gmail": [0]})
    jobs.work(tmp_path, once=True, runner=run, log=lambda s: None, retry_in=0)
    assert jobs.get(tmp_path, read.id).status is JobStatus.DONE


def test_the_mcp_tool_reads_the_queue(tmp_path):
    from jason.mcp.county import jobs_status

    assert jobs_status(data_dir=tmp_path)["found"] is False
    job = jobs.add(tmp_path, ["gmail", "--sync"])
    jobs.log_path(tmp_path, job.id).write_text("line one\nline two\n", encoding="utf-8")
    listed = jobs_status(data_dir=tmp_path)
    assert listed["jobs"][0]["command"] == "jason gmail --sync" and listed["byStatus"] == {"queued": 1}
    one = jobs_status(job=job.id, data_dir=tmp_path)
    assert one["job"]["resource"] == "google" and one["log"][-1] == "line two"


def test_only_one_worker_runs(tmp_path):
    from jason.locks import Resource, hold

    with hold(Resource.STORE, "jobs-worker"):
        import subprocess
        import sys

        # Another process, not this one: the lock is re-entrant within a process.
        code = subprocess.run([sys.executable, "-c", "from pathlib import Path; from jason import jobs; "
                               f"jobs.work(Path(r'{tmp_path}'), once=True)"], capture_output=True, text=True)
        assert code.returncode != 0 and "another worker is running" in code.stderr
