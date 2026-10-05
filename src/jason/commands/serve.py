"""``jason serve`` and ``jason daemon``: jason-web and the job worker in one process, its heartbeat, and its drain.

- ``jason serve [--profile P | --all] [--no-web] [--no-worker] [--no-scheduler]`` with jason-web's flags (``--host``,
  ``--port``, ``--dist``, ``--allow-apply``, ``--require-sign-in``, ``--dev``) and the worker's (``--poll``,
  ``--keep-models``). Ctrl-C drains the lanes as ``jason worker`` does. ``--no-scheduler`` is reserved for the
  scheduler to come and does nothing yet.
- ``jason serve --install-task [--yes]`` prints, or with ``--yes`` registers through ``schtasks``, the Task Scheduler
  entry that runs ``jason serve`` at startup; ``--uninstall-task [--yes]`` removes it.
- ``jason daemon status`` reads each community's heartbeat (no network); ``jason daemon stop [--profile P]`` writes a
  drain request the serve process picks up. Nothing here kills a process.

The parts and files are described in ``jason.serve`` and docs/scheduler-daemon-design.md.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


def _names(args: argparse.Namespace) -> list[str]:
    from jason import serve
    from jason.community.profile import profile_name

    if getattr(args, "all", False):
        return serve.profile_names()
    if args.profile:
        known = serve.profile_names()
        if args.profile not in known:
            raise SystemExit(f"Error: no profile {args.profile!r} (this checkout has: {', '.join(known)})")
        return [args.profile]
    return [profile_name()]


def _serve_args(args: argparse.Namespace) -> list[str]:
    """The serve flags a person gave, for the scheduled task to run the same way."""
    out: list[str] = []
    if args.all:
        out.append("--all")
    elif args.profile:
        out += ["--profile", args.profile]
    out += [flag for flag, on in (("--no-web", args.no_web), ("--no-worker", args.no_worker),
                                  ("--no-scheduler", args.no_scheduler)) if on]
    if args.host != "127.0.0.1":
        out += ["--host", args.host]
    if args.port != 8080:
        out += ["--port", str(args.port)]
    if args.dist:
        out += ["--dist", str(Path(args.dist).resolve())]
    out += [flag for flag, on in (("--allow-apply", args.allow_apply), ("--require-sign-in", args.require_sign_in),
                                  ("--keep-models", args.keep_models)) if on]
    if args.poll != 20.0:
        out += ["--poll", f"{args.poll:g}"]
    if args.env:
        out += ["--env", str(Path(args.env).resolve())]
    return out


def _task(args: argparse.Namespace, run: Callable[..., Any] = subprocess.run) -> int:
    from jason import serve

    if sys.platform != "win32":
        print("Error: --install-task and --uninstall-task use Windows Task Scheduler", file=sys.stderr)
        return 1
    name = serve.TASK_NAME + (f" {args.profile}" if args.profile and not args.all else "")
    if args.uninstall_task:
        cmd = serve.uninstall_command(name)
        if not args.yes:
            print(f"would run: {subprocess.list2cmdline(cmd)}\nadd --yes to remove the task")
            return 0
        return run(cmd).returncode
    if args.dev:
        print("Error: --dev is not production; a task that starts at boot does not take it", file=sys.stderr)
        return 1
    exe, arguments = serve.task_command(_serve_args(args))
    xml = serve.task_xml(exe, arguments, workdir=serve.checkout_root(), user=serve.task_user(), name=name)
    path = serve.task_xml_path()
    cmd = serve.install_command(path, name)
    if not args.yes:
        print(xml)
        print(f"would write the definition above to {path} (UTF-16) and run, from a terminal run as administrator "
              f"(an \"At startup\" task needs it):\n  {subprocess.list2cmdline(cmd)}\nadd --yes to create the task")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml, encoding="utf-16")
    code = run(cmd).returncode
    print(f"task {name!r} {'created' if code == 0 else 'not created (schtasks exit ' + str(code) + ')'}; definition {path}")
    return code


def cmd_serve(args: argparse.Namespace) -> int:
    from jason import serve

    if args.install_task or args.uninstall_task:
        return _task(args)
    if args.no_web and args.no_worker:
        print("Error: nothing to run: --no-web and --no-worker together", file=sys.stderr)
        return 2
    names = _names(args)
    if args.profile:
        os.environ["JASON_PROFILE"] = args.profile        # the web part and every job serve this community
    dirs = {n: serve.profile_data_dir(n, args.env) for n in names}
    web, info = None, None
    if not args.no_web:
        import waitress

        from jason.web import app as web_app

        def refuse(message: str) -> None:
            raise serve.ServeRefused(message)
        try:
            web = waitress.create_server(web_app.prepare(args, refuse), host=args.host, port=args.port)
        except (serve.ServeRefused, OSError) as exc:      # a port in use fails here, before any worker starts
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        info = {"host": args.host, "port": args.port}
        if len(names) > 1:
            print(f"jason serve: the web serves {names[0]}; the workers serve {', '.join(names)}", file=sys.stderr)

    def work(profile: str, data_dir: Path, stop: Any, lanes: dict[str, Any]) -> Any:
        from jason import jobs

        return jobs.work(data_dir, poll=args.poll, env_file=args.env, release_models=not args.keep_models,
                         profile=profile, stop=stop, current=lanes,
                         log=lambda line: print(f"[{profile}] {line}", flush=True))

    if args.no_scheduler:
        print("jason serve: --no-scheduler: the scheduler is not built yet; nothing to turn off", file=sys.stderr)
    ended = serve.run(dirs, web=web, work=None if args.no_worker else work, web_info=info,
                      log=lambda line: print(f"jason serve: {line}", flush=True))
    bad = {k: v for k, v in ended.items() if v.get("refused") or v.get("failed")}
    return 1 if bad else 0


def cmd_daemon(args: argparse.Namespace) -> int:
    from jason import serve

    names = _names(args) if args.profile else serve.profile_names()
    dirs = {n: serve.profile_data_dir(n, args.env) for n in names}
    rows = serve.status(dirs)
    if args.action == "status":
        print(json.dumps(rows, indent=1, default=str) if args.json else "\n".join(serve.status_lines(rows)))
        return 0
    # stop: a drain request for each community a serve process is running (or hangs) for; nothing is killed.
    targets = [r for r in rows if r["state"] in ("running", "draining", "stale")]
    if not targets:
        print("no jason serve is running" + (f" for {args.profile}" if args.profile else "") + "; nothing to stop")
        return 1
    by = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    for r in targets:
        path = serve.request_drain(Path(r["dataDir"]), by=by)
        note = " (its heartbeat is stale: a hung process may not read it; end it in Task Scheduler)" if r["state"] == "stale" else ""
        print(f"{r['profile']}: drain requested ({path}); its lanes finish their running jobs and stop{note}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    from jason.web.flags import add_arguments as add_web_arguments

    p = sub.add_parser("serve", help="Run jason-web and the job worker in one process, for one community or --all; "
                                     "--install-task sets it to start at boot")
    add_common(p)
    which = p.add_mutually_exclusive_group()
    which.add_argument("--profile", default="", help="the community to serve (default the active profile)")
    which.add_argument("--all", action="store_true", help="one worker per profile, each behind its own guard; the web "
                                                          "serves the active profile")
    p.add_argument("--no-web", action="store_true", help="run no web server")
    p.add_argument("--no-worker", action="store_true", help="run no worker")
    p.add_argument("--no-scheduler", action="store_true", help="reserved for the scheduler to come; does nothing yet")
    add_web_arguments(p)
    p.add_argument("--poll", type=float, default=20.0, help="seconds between the worker's looks at the queue")
    p.add_argument("--keep-models", action="store_true", help="leave models loaded after GPU jobs (as jason worker)")
    p.add_argument("--install-task", action="store_true",
                   help="print the Task Scheduler entry that runs jason serve at startup (with --yes, create it)")
    p.add_argument("--uninstall-task", action="store_true", help="print the command that removes it (with --yes, run it)")
    p.add_argument("--yes", action="store_true", help="with --install-task or --uninstall-task: do it")
    p.set_defaults(func=cmd_serve)

    d = sub.add_parser("daemon", help="jason serve's heartbeat (status) and drain request (stop); kills nothing")
    add_common(d)
    d.add_argument("action", choices=["status", "stop"])
    d.add_argument("--profile", default="", help="one community (default every profile)")
    d.add_argument("--json", action="store_true", help="with status: print JSON")
    d.set_defaults(func=cmd_daemon, all=False)


__all__ = ["cmd_daemon", "cmd_serve", "register"]
