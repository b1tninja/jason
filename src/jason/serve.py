"""``jason serve``: jason-web and the job worker in one process, for one community or every one.

The parts (docs/scheduler-daemon-design.md):
- **web**: jason-web under waitress, serving the active profile;
- **worker**: the job lanes (``jason.jobs.work``), one worker per community, each behind its own guard
  (``jobs-worker-<profile>``), so a second community's worker runs beside the first;
- **scheduler**: not built yet; ``--no-scheduler`` is accepted and does nothing.

While it runs, each community's heartbeat (``<profile data>/jobs/heartbeat.json``) is written every ``BEAT_SECONDS``
and whenever a lane takes or finishes a job: the process, the host, when it started, the last beat, which parts run, and
each lane's running job. ``jason daemon status`` reads it with no network: a beat older than ``STALE_AFTER`` is stale
(the process stopped without saying so, or hangs).

``jason daemon stop`` never kills a process. It writes a drain request (``<profile data>/jobs/drain.json``) that the
serve loop picks up: that community's lanes finish their running job and take no more, as Ctrl-C does. When every
community it serves is drained, the process ends, web included. A drain request left from before the process started is
cleared at start.

``--install-task`` prints, or with ``--yes`` registers, a Windows Task Scheduler entry that runs ``jason serve`` at
startup, restarts it on failure, and sets no execution time limit (``task_xml``).
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from xml.sax.saxutils import escape

HEARTBEAT = "heartbeat.json"
DRAIN = "drain.json"
BEAT_SECONDS = 30.0
STALE_AFTER = 90.0            # three missed beats
TASK_NAME = "jason serve"


class ServeRefused(RuntimeError):
    """The process cannot start as asked."""


class WebServer(Protocol):
    """What the serve loop needs of the web part: waitress's server (``waitress.create_server``)."""

    def run(self) -> None: ...

    def close(self) -> None: ...


Work = Callable[[str, Path, threading.Event, dict[str, Any]], Any]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def profile_names() -> list[str]:
    """Every profile this checkout can load (``jason.community.profile.profiles``), the active one first."""
    from jason.community.profile import profile_name, profiles

    active = profile_name()
    names = [row["name"] for row in profiles()]
    return [active] + [n for n in names if n != active]


def profile_data_dir(profile: str, env_file: str | None = None) -> Path:
    """A community's data folder: the active profile's as the commands read it (``config.data_dir``), any other's
    ``default_data_dir(profile)``."""
    from jason.community.profile import profile_name
    from jason.config import data_dir, default_data_dir

    return data_dir(env_file) if profile == profile_name() else default_data_dir(profile)


def heartbeat_path(data_dir: Path) -> Path:
    return Path(data_dir) / "jobs" / HEARTBEAT


def drain_path(data_dir: Path) -> Path:
    return Path(data_dir) / "jobs" / DRAIN


def _write_json(path: Path, record: dict[str, Any]) -> None:
    """Write atomically. The heartbeat thread and the lanes write the same file, so the temporary name carries the
    thread; on Windows a replace fails while a reader has the file open, so it is retried briefly."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(record, indent=1), encoding="utf-8")
    for attempt in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 19:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.05)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def read_heartbeat(data_dir: Path) -> dict[str, Any] | None:
    return _read_json(heartbeat_path(data_dir))


def write_heartbeat(data_dir: Path, record: dict[str, Any]) -> None:
    _write_json(heartbeat_path(data_dir), record)


def request_drain(data_dir: Path, *, by: str = "") -> Path:
    """Ask the serve process for this community to drain its lanes and stop. Writes a file; kills nothing."""
    path = drain_path(data_dir)
    _write_json(path, {"requested": _now(), "by": by, "pid": os.getpid(), "host": socket.gethostname()})
    return path


def drain_requested(data_dir: Path) -> dict[str, Any] | None:
    return _read_json(drain_path(data_dir))


def clear_drain(data_dir: Path) -> None:
    try:
        drain_path(data_dir).unlink()
    except OSError:
        pass


def _age(stamp: str, now: datetime) -> float | None:
    try:
        return (now - datetime.fromisoformat(stamp)).total_seconds()
    except (TypeError, ValueError):
        return None


def judge(record: dict[str, Any] | None, *, now: datetime | None = None, stale_after: float = STALE_AFTER) -> dict[str, Any]:
    """What a heartbeat says: ``state`` is ``none`` (never written), ``stopped`` (the process said it ended),
    ``stale`` (no beat for ``stale_after`` seconds: stopped without saying, or hung), or the process's own word
    (``running``, ``draining``); ``alive`` is whether a running or draining process beat recently."""
    now = now or datetime.now(timezone.utc)
    if not record:
        return {"state": "none", "alive": False, "age": None}
    age = _age(record.get("beat", ""), now)
    said = record.get("state", "running")
    if said == "stopped":
        return {**record, "state": "stopped", "alive": False, "age": age}
    if age is None or age > stale_after:
        return {**record, "state": "stale", "said": said, "alive": False, "age": age}
    return {**record, "state": said, "alive": True, "age": age}


def status(profiles: dict[str, Path], *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Each community's heartbeat, judged, with who holds its worker lock now (``jason.locks.holders``). Reads files
    and locks only; no network."""
    from jason.jobs import worker_guard
    from jason.locks import Resource, holders

    held = {h["lock"]: h for h in holders()}
    out = []
    for name, data_dir in profiles.items():
        row = judge(read_heartbeat(data_dir), now=now)
        lock = held.get(f"{Resource.STORE.value}-{worker_guard(name)}")
        out.append({**row, "profile": name, "dataDir": str(data_dir), "drain": drain_requested(data_dir),
                    "workerLock": {"pid": lock.get("pid"), "since": lock.get("since")} if lock else None})
    return out


def status_lines(rows: list[dict[str, Any]]) -> list[str]:
    out = []
    for r in rows:
        name = r["profile"]
        if r["state"] == "none":
            out.append(f"{name}: no heartbeat (jason serve has not run for it)")
        else:
            age = f"{int(r['age'])} s ago" if r.get("age") is not None else "at an unreadable time"
            who = f"pid {r.get('pid', '?')} on {r.get('host', '?')}, started {r.get('started', '?')}"
            if r["state"] == "stale":
                out.append(f"{name}: STALE, last beat {r.get('beat', '?')} ({age}); it said {r.get('said', '?')} "
                           f"({who}); the process stopped without saying so, or hangs")
            elif r["state"] == "stopped":
                out.append(f"{name}: stopped at {r.get('beat', '?')} ({who})")
            else:
                out.append(f"{name}: {r['state']}, last beat {age} ({who})")
            web = r.get("web")
            worker = ("worker off" if not r.get("worker") else f"worker refused: {r['refused']}" if r.get("refused")
                      else f"worker failed: {r['failed']}" if r.get("failed")
                      else "worker on" if r.get("workerRunning") else "worker ended")
            parts = [f"web {web['host']}:{web['port']}" if web else "web off", worker, "scheduler not built"]
            out.append("  " + "; ".join(parts))
            if r["state"] in ("running", "draining", "stale"):
                for lane, job in (r.get("lanes") or {}).items():
                    out.append(f"  {lane:<7} " + (f"job {job['id']} since {job['since']}: {job['command']}" if job else "idle"))
        if r.get("drain"):
            out.append(f"  drain requested {r['drain'].get('requested', '?')}" + (f" by {r['drain']['by']}" if r['drain'].get("by") else ""))
        if r.get("workerLock"):
            out.append(f"  worker lock held by pid {r['workerLock']['pid']} since {r['workerLock']['since']}")
    return out


# -- the serve loop ----------------------------------------------------------------------------------------------------

@dataclass
class _Community:
    name: str
    data_dir: Path
    stop: threading.Event = field(default_factory=threading.Event)
    lanes: dict[str, Any] = field(default_factory=dict)
    thread: threading.Thread | None = None
    draining: bool = False
    refused: str = ""
    failed: str = ""

    def state(self) -> str:
        """The process's word for this community until it ends (then ``stopped``)."""
        return "draining" if (self.draining or self.stop.is_set()) else "running"

    def worker_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()


def run(profiles: dict[str, Path], *, web: WebServer | None = None, work: Work | None = None,
        web_info: dict[str, Any] | None = None, beat: float = BEAT_SECONDS, tick: float = 0.5,
        log: Callable[[str], None] = print, stop: threading.Event | None = None) -> dict[str, Any]:
    """Run the parts until every community is drained, Ctrl-C, ``stop``, or no part is left running.

    ``profiles`` maps each community to its data folder; ``web`` is the bound web server (it serves the active
    profile), None for ``--no-web``; ``work(profile, data_dir, stop, lanes)`` runs one community's worker until its
    ``stop`` is set, None for ``--no-worker``. Returns, per community, how it ended."""
    if web is None and work is None:
        raise ServeRefused("nothing to run: --no-web and --no-worker together")
    stop = stop or threading.Event()
    started = _now()
    host, pid = socket.gethostname(), os.getpid()
    parts = {p: _Community(p, Path(d)) for p, d in profiles.items()}
    for c in parts.values():
        clear_drain(c.data_dir)                     # a request from before this process started is not for it

    def worker(c: _Community) -> None:
        from jason.jobs import JobRefused

        try:
            work(c.name, c.data_dir, c.stop, c.lanes)  # type: ignore[misc]
        except JobRefused as exc:
            c.refused = str(exc)
            log(f"[{c.name}] worker refused: {exc}")
        except Exception as exc:  # noqa: BLE001 - one community's worker failing leaves the others running
            c.failed = f"{type(exc).__name__}: {exc}"
            log(f"[{c.name}] worker failed: {c.failed}")

    web_error: list[str] = []

    def serve_web() -> None:
        try:
            web.run()  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            web_error.append(f"{type(exc).__name__}: {exc}")
            log(f"web failed: {web_error[-1]}")

    def record(c: _Community) -> dict[str, Any]:
        return {"profile": c.name, "pid": pid, "host": host, "started": started, "state": c.state(),
                "web": web_info if web is not None else None, "worker": work is not None,
                "workerRunning": c.worker_running(), "scheduler": False, "lanes": dict(c.lanes),
                "refused": c.refused, "failed": c.failed}

    def beat_all(force: bool, last: dict[str, str]) -> None:
        for c in parts.values():
            rec = record(c)
            key = json.dumps(rec, sort_keys=True, default=str)
            if force or key != last.get(c.name):
                write_heartbeat(c.data_dir, {**rec, "beat": _now()})
                last[c.name] = key

    web_thread = threading.Thread(target=serve_web, name="jason-web", daemon=True) if web is not None else None
    if work is not None:
        for c in parts.values():
            c.thread = threading.Thread(target=worker, args=(c,), name=f"jason-worker-{c.name}", daemon=True)
            c.thread.start()
    if web_thread is not None:
        web_thread.start()
        log(f"web on http://{(web_info or {}).get('host', '?')}:{(web_info or {}).get('port', '?')}")
    last: dict[str, str] = {}
    beat_all(True, last)
    next_beat = time.monotonic() + beat
    try:
        while not stop.is_set():
            for c in parts.values():
                if not c.draining and drain_requested(c.data_dir) is not None:
                    c.draining = True
                    c.stop.set()
                    log(f"[{c.name}] drain requested: the lanes finish their running jobs and stop")
            workers_alive = any(c.thread is not None and c.thread.is_alive() for c in parts.values())
            web_alive = web_thread is not None and web_thread.is_alive()
            if all(c.draining for c in parts.values()) and not workers_alive:
                log("every community is drained")
                break
            if not workers_alive and not web_alive:
                break
            now = time.monotonic()
            beat_all(now >= next_beat, last)
            if now >= next_beat:
                next_beat = now + beat
            time.sleep(tick)
    except KeyboardInterrupt:
        log("stopping after the running jobs finish")
    finally:
        for c in parts.values():
            c.stop.set()
        for c in parts.values():
            while c.thread is not None and c.thread.is_alive():
                try:
                    c.thread.join(timeout=1)
                except KeyboardInterrupt:
                    log("still waiting for the running jobs (each job's own process got the Ctrl-C too)")
                beat_all(False, last)
        if web is not None:
            try:
                web.close()
            except Exception:  # noqa: BLE001 - closing a server that already stopped
                pass
        for c in parts.values():
            c.draining = True
            write_heartbeat(c.data_dir, {**record(c), "state": "stopped", "beat": _now()})
            clear_drain(c.data_dir)
    return {c.name: {"refused": c.refused, "failed": c.failed} for c in parts.values()} | (
        {"web": {"failed": web_error[-1]}} if web_error else {})


# -- the Task Scheduler entry ------------------------------------------------------------------------------------------

def checkout_root() -> Path:
    return Path(__file__).resolve().parents[2]


def task_command(serve_args: list[str]) -> tuple[str, str]:
    """The program and arguments the task runs: the venv's ``jason.exe`` beside this Python, else ``python -m
    jason.cli``."""
    exe = Path(sys.executable).with_name("jason.exe")
    if exe.is_file():
        return str(exe), subprocess.list2cmdline(["serve", *serve_args])
    return sys.executable, subprocess.list2cmdline(["-m", "jason.cli", "serve", *serve_args])


def task_user() -> str:
    domain, user = os.environ.get("USERDOMAIN", ""), os.environ.get("USERNAME", "")
    return f"{domain}\\{user}" if domain and user else user


def task_xml(command: str, arguments: str, *, workdir: Path, user: str, name: str = TASK_NAME) -> str:
    """The Task Scheduler definition: at startup (a minute after boot), as ``user`` whether signed in or not with no
    password stored (S4U), restart every minute on failure (999 times), no execution time limit (PT0S; the default is
    72 hours), one instance, on battery too."""
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>{escape(user)}</Author>
    <Description>{escape(name)}: jason-web and the job worker (docs/scheduler-daemon-design.md). Stop it with `jason daemon stop`.</Description>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT1M</Delay>
    </BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(user)}</UserId>
      <LogonType>S4U</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>999</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(command)}</Command>
      <Arguments>{escape(arguments)}</Arguments>
      <WorkingDirectory>{escape(str(workdir))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def task_xml_path() -> Path:
    """Where ``--install-task --yes`` writes the definition it registers: beside the user config (``~/.jason``)."""
    from jason.config import user_config_path

    return user_config_path().parent / "jason-serve-task.xml"


def install_command(xml_path: Path, name: str = TASK_NAME) -> list[str]:
    return ["schtasks", "/Create", "/TN", name, "/XML", str(xml_path), "/F"]


def uninstall_command(name: str = TASK_NAME) -> list[str]:
    return ["schtasks", "/Delete", "/TN", name, "/F"]


__all__ = ["BEAT_SECONDS", "STALE_AFTER", "TASK_NAME", "ServeRefused", "WebServer", "checkout_root", "clear_drain",
           "drain_requested", "heartbeat_path", "install_command", "judge", "profile_data_dir", "profile_names",
           "read_heartbeat", "request_drain", "run", "status", "status_lines", "task_command", "task_user", "task_xml",
           "task_xml_path", "uninstall_command", "write_heartbeat"]
