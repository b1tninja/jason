"""jason serve: one worker per community, service locks per account, the parts each flag starts, the heartbeat, the
drain request, and the Task Scheduler entry (printed, never created here)."""

import random
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest

from jason import batches, jobs, serve
from jason.locks import Resource, ResourceBusy, account, hold, holders


def _until(check, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.02)
    return False


# -- step 1: the worker guard and the service locks, per community -------------------------------------------------------

def test_two_communities_run_a_worker_each_and_a_second_worker_for_one_is_refused(tmp_path):
    stop = threading.Event()
    alpha = threading.Thread(target=jobs.work, args=(tmp_path / "alpha",),
                             kwargs={"profile": "alpha", "stop": stop, "poll": 0.05, "log": lambda s: None})
    alpha.start()
    try:
        assert _until(lambda: "store-jobs-worker-alpha" in {h["lock"] for h in holders()})
        job = jobs.add(tmp_path / "beta", ["gmail", "--sync"])
        ran = []
        counts = jobs.work(tmp_path / "beta", profile="beta", once=True, log=lambda s: None,
                           runner=lambda argv, log: ran.append(argv) or 0)        # beta's worker runs beside alpha's
        assert counts["done"] == 1 and ran == [["gmail", "--sync"]] and jobs.get(tmp_path / "beta", job.id).status.value == "done"
        # The same community's second worker, in another process, is refused.
        code = subprocess.run([sys.executable, "-c", "from pathlib import Path; from jason import jobs; "
                               f"jobs.work(Path(r'{tmp_path / 'alpha2'}'), once=True, profile='alpha')"],
                              capture_output=True, text=True)
        assert code.returncode != 0 and "another worker is running for alpha" in code.stderr
    finally:
        stop.set()
        alpha.join(timeout=10)
    assert not alpha.is_alive()
    assert "store-jobs-worker-alpha" not in {h["lock"] for h in holders()}    # released when the worker ends


def test_a_job_runs_as_its_workers_community(tmp_path, monkeypatch):
    seen = {}

    class Proc:
        pid = 1

        def __init__(self, cmd, env, **kw):
            seen.update(env=env)

        def wait(self):
            return 0
    monkeypatch.setattr(jobs.subprocess, "Popen", Proc)
    job = jobs.add(tmp_path, ["gmail", "--sync"])
    jobs.run_job(tmp_path, jobs.get(tmp_path, job.id), profile="beta")
    assert seen["env"]["JASON_PROFILE"] == "beta"


def test_payhoa_locks_for_two_communities_do_not_block_each_other():
    assert account("alpha") == "alpha" and account() == "mystique"           # the active profile by default
    outcome = {}

    def other():
        try:
            with hold(Resource.PAYHOA, account("beta"), timeout=0.5):
                outcome["beta"] = "held"
            with hold(Resource.PAYHOA, account("alpha"), timeout=0.5):
                outcome["alpha"] = "held"
        except ResourceBusy as exc:
            outcome["alpha"] = f"busy: {exc}"
    with hold(Resource.PAYHOA, account("alpha"), purpose="alpha's batch"):
        t = threading.Thread(target=other)        # another thread takes its own handle: the lock is not re-entrant there
        t.start()
        t.join(timeout=10)
    assert outcome["beta"] == "held" and outcome["alpha"].startswith("busy") and "alpha's batch" in outcome["alpha"]


def test_a_batch_holds_its_communitys_payhoa_lock(tmp_path):
    batches.create(tmp_path, "b1", "test", "Test", [("k0", "item 0", {})], confirmed_by="Justin")
    seen = []

    class Handler:
        def send(self, item, checkpoint, step):
            seen.extend(h["lock"] for h in holders())
            return {"ok": True}

        def verify(self, item):
            return False
    batches.run(tmp_path, "b1", Handler(), sleep=lambda s: None, say=lambda s: None, rng=random.Random(0), profile="alpha")
    assert seen == ["payhoa-alpha"]


def test_two_communities_gpu_jobs_never_run_at_once(tmp_path):
    job = jobs.add(tmp_path, ["outlines", "--model"])
    outcome = {}

    def other():
        outcome["counts"] = jobs.work(tmp_path, profile="beta", once=True, preflight=lambda: None, loaded=frozenset,
                                      runner=lambda argv, log: 0, log=lambda s: None, defer_for=3600)
    with hold(Resource.STORE, jobs.GPU_LANE, purpose="alpha's model job"):
        t = threading.Thread(target=other)
        t.start()
        t.join(timeout=10)
    after = jobs.get(tmp_path, job.id)
    assert outcome["counts"]["deferred"] == 1 and after.status.value == "queued" and after.attempts == 0
    assert "another community's model job" in after.note


# -- step 3: jason serve, its heartbeat, and jason daemon ----------------------------------------------------------------

class FakeServer:
    def __init__(self, app, host, port, on_run=None):
        self.app, self.host, self.port, self.on_run = app, host, port, on_run
        self.closed = threading.Event()
        self.ran = False

    def run(self):
        self.ran = True
        if self.on_run:
            self.on_run()
        self.closed.wait(10)

    def close(self):
        self.closed.set()


@pytest.fixture
def served(tmp_path, monkeypatch):
    """jason serve with waitress and the worker loop replaced: each fake worker records its community and asks to be
    drained, as `jason daemon stop` would, so the serve loop ends by itself."""
    from jason.web import app as web_app
    import waitress

    monkeypatch.setenv("JASON_PROFILE", "mystique")
    monkeypatch.setattr(serve, "profile_names", lambda: ["mystique", "other"])
    monkeypatch.setattr(serve, "profile_data_dir", lambda name, env=None: tmp_path / name)
    monkeypatch.setattr(web_app, "prepare", lambda a, error: "APP")
    state = SimpleNamespace(servers=[], worked=[])

    def create_server(app, host, port):
        def drain_all():
            if not state.worked:                          # --no-worker: the drain comes while the web runs
                for name in ("mystique", "other"):
                    serve.request_drain(tmp_path / name)
        server = FakeServer(app, host, port, on_run=drain_all)
        state.servers.append(server)
        return server
    monkeypatch.setattr(waitress, "create_server", create_server)

    def work(data_dir, *, profile, stop, current, **kw):
        state.worked.append(profile)
        current.update({c.value: None for c in jobs.JobClass})
        serve.request_drain(data_dir)
        stop.wait(10)
        return {}
    monkeypatch.setattr(jobs, "work", work)

    def run(*argv):
        from jason.cli import build_parser

        args = build_parser().parse_args(["serve", *argv])
        return args.func(args)
    state.run = run
    return state


def test_serve_runs_web_and_worker_by_default(served, tmp_path):
    assert served.run() == 0
    assert [(s.host, s.port, s.ran, s.closed.is_set()) for s in served.servers] == [("127.0.0.1", 8080, True, True)]
    assert served.worked == ["mystique"]
    beat = serve.read_heartbeat(tmp_path / "mystique")
    assert beat["state"] == "stopped" and beat["web"] == {"host": "127.0.0.1", "port": 8080} and beat["worker"]
    assert serve.drain_requested(tmp_path / "mystique") is None                # the honored request is cleared


def test_serve_flags_skip_parts_and_carry_jason_webs(served, tmp_path):
    assert served.run("--no-web", "--no-scheduler") == 0
    assert served.servers == [] and served.worked == ["mystique"]
    served.worked.clear()
    assert served.run("--no-worker", "--host", "0.0.0.0", "--port", "9000") == 0
    assert served.worked == [] and [(s.host, s.port) for s in served.servers] == [("0.0.0.0", 9000)]
    assert not serve.read_heartbeat(tmp_path / "mystique")["worker"]
    served.servers.clear()
    assert served.run("--all", "--no-web") == 0
    assert sorted(served.worked) == ["mystique", "other"]
    assert serve.read_heartbeat(tmp_path / "other")["state"] == "stopped"
    assert served.run("--no-web", "--no-worker") == 2
    served.worked.clear()
    assert served.run("--profile", "other", "--no-web") == 0 and served.worked == ["other"]


def test_the_heartbeat_shows_lanes_and_a_drain_request_stops_the_loop(tmp_path):
    started, ended = threading.Event(), {}
    old = tmp_path / "a" / "jobs" / "drain.json"
    serve.request_drain(tmp_path / "a")                                        # from before the process started

    def work(profile, data_dir, stop, lanes):
        lanes.update({"gpu": None, "google": {"id": 7, "command": "jason gmail --sync", "since": "2026-10-05T02:00:00+00:00"}})
        started.set()
        stop.wait(10)
        lanes["google"] = None

    loop = threading.Thread(target=lambda: ended.update(serve.run({"a": tmp_path / "a"}, work=work, beat=0.05, tick=0.02,
                                                                   log=lambda s: None)))
    loop.start()
    assert started.wait(5)
    assert _until(lambda: (serve.read_heartbeat(tmp_path / "a") or {}).get("lanes", {}).get("google"))
    row = serve.judge(serve.read_heartbeat(tmp_path / "a"))
    assert row["alive"] and row["state"] == "running" and row["workerRunning"] and loop.is_alive()
    lines = serve.status_lines([{**row, "profile": "a"}])
    assert any("job 7" in line and "gmail --sync" in line for line in lines) and any("gpu" in l and "idle" in l for l in lines)
    serve.request_drain(tmp_path / "a", by="Treasurer")                       # what `jason daemon stop` writes
    loop.join(timeout=10)
    assert not loop.is_alive() and ended == {"a": {"refused": "", "failed": ""}} and not old.exists()
    assert serve.judge(serve.read_heartbeat(tmp_path / "a"))["state"] == "stopped"


def test_a_heartbeat_with_no_recent_beat_is_stale():
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    beat = {"state": "running", "beat": (now - timedelta(seconds=200)).isoformat(), "pid": 1, "host": "h"}
    assert serve.judge(beat, now=now)["state"] == "stale" and not serve.judge(beat, now=now)["alive"]
    assert serve.judge({**beat, "beat": (now - timedelta(seconds=10)).isoformat()}, now=now)["alive"]
    assert serve.judge(None)["state"] == "none"


def test_daemon_status_and_stop(tmp_path, monkeypatch, capsys):
    from jason.cli import build_parser

    monkeypatch.setattr(serve, "profile_names", lambda: ["mystique", "other"])
    monkeypatch.setattr(serve, "profile_data_dir", lambda name, env=None: tmp_path / name)

    def jason(*argv):
        args = build_parser().parse_args(list(argv))
        return args.func(args)
    assert jason("daemon", "stop") == 1 and "nothing to stop" in capsys.readouterr().out
    assert serve.drain_requested(tmp_path / "mystique") is None               # nothing written when nothing runs
    started = threading.Event()

    def work(profile, data_dir, stop, lanes):
        started.set()
        stop.wait(10)
    loop = threading.Thread(target=serve.run, args=({"mystique": tmp_path / "mystique", "other": tmp_path / "other"},),
                            kwargs={"work": work, "tick": 0.02, "log": lambda s: None})
    loop.start()
    assert started.wait(5) and _until(lambda: serve.read_heartbeat(tmp_path / "other"))
    assert jason("daemon", "status") == 0
    out = capsys.readouterr().out
    assert "mystique: running" in out and "other: running" in out and "worker on" in out
    assert jason("daemon", "stop", "--profile", "other") == 0
    assert _until(lambda: serve.read_heartbeat(tmp_path / "other")["workerRunning"] is False)
    assert loop.is_alive()                                                     # mystique still runs
    assert jason("daemon", "stop") == 0
    loop.join(timeout=10)
    assert not loop.is_alive()
    jason("daemon", "status", "--json")
    assert '"state": "stopped"' in capsys.readouterr().out


@pytest.mark.skipif(sys.platform != "win32", reason="Task Scheduler is Windows only")
def test_install_task_prints_without_yes_and_runs_schtasks_only_with_it(tmp_path, monkeypatch, capsys):
    from jason.cli import build_parser
    from jason.commands.serve import _task

    calls = []

    def run(cmd):
        calls.append(cmd)
        return SimpleNamespace(returncode=0)
    args = build_parser().parse_args(["serve", "--install-task", "--all", "--port", "9000", "--no-scheduler"])
    assert _task(args, run=run) == 0 and calls == []
    out = capsys.readouterr().out
    xml = out[:out.index("</Task>") + len("</Task>")]
    root = ElementTree.fromstring(xml.encode("utf-16"))
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    assert root.find("t:Triggers/t:BootTrigger", ns) is not None
    assert root.findtext("t:Settings/t:ExecutionTimeLimit", namespaces=ns) == "PT0S"
    assert root.findtext("t:Settings/t:RestartOnFailure/t:Count", namespaces=ns) == "999"
    assert root.findtext("t:Actions/t:Exec/t:Arguments", namespaces=ns).endswith("serve --all --no-scheduler --port 9000")
    assert 'schtasks /Create /TN "jason serve" /XML' in out and "add --yes" in out
    monkeypatch.setattr(serve, "task_xml_path", lambda: tmp_path / "task.xml")
    assert _task(build_parser().parse_args(["serve", "--install-task", "--yes"]), run=run) == 0
    assert calls == [["schtasks", "/Create", "/TN", "jason serve", "/XML", str(tmp_path / "task.xml"), "/F"]]
    assert (tmp_path / "task.xml").read_bytes()[:2] == b"\xff\xfe"           # UTF-16, as schtasks reads it
    calls.clear()
    assert _task(build_parser().parse_args(["serve", "--uninstall-task", "--profile", "other"]), run=run) == 0
    assert calls == [] and 'schtasks /Delete /TN "jason serve other" /F' in capsys.readouterr().out
    assert _task(build_parser().parse_args(["serve", "--install-task", "--dev"]), run=run) == 1
