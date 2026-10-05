"""``jason cadence``: each source's schedule in jason serve's scheduler (``jason.scheduler``; docs/scheduler-daemon-design.md).

- ``jason cadence [--community C] [--json]``: each source: its command, cadence, window, floor, where the setting came
  from, the next run, the last job's result, and a pause or why it is not scheduled. From disk only.
- ``jason cadence SOURCE --every 30m | --cron "0 2 * * *" [--window 07-22|all] --by NAME``: an administrator's change,
  adopted; refused faster than the floor its integration declares, with the reason.
- ``--restore SOURCE | --restore-all --by NAME``: back to the registry's default, adopted. A seeded default runs only
  once a person adopts it this way.
- ``--pause SOURCE --why TEXT --by NAME``; ``--resume SOURCE --by NAME`` (also clears a sign-in pause, the failures, and
  the backoff).
- ``--run-now SOURCE [--by NAME]``: add its command to the queue once, now.

Every change is recorded with who and when (the row, and ``<data>/jobs/scheduler.jsonl``). Nothing here calls a
service; the worker runs what is queued.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo


def _target(args: argparse.Namespace) -> tuple[str, Path]:
    from jason import serve
    from jason.community.profile import profile_name

    name = args.community or profile_name()
    known = serve.profile_names()
    if name not in known:
        raise SystemExit(f"jason cadence: no profile {name!r} (this checkout has: {', '.join(known)})")
    return name, serve.profile_data_dir(name, getattr(args, "env", None))


def cmd_cadence(args: argparse.Namespace) -> int:
    from jason import scheduler as sc

    name, data_dir = _target(args)
    zone_name = sc.zone_of(name)
    zone = ZoneInfo(zone_name)
    sc.seed(data_dir)
    by = (args.by or "").strip()
    try:
        if args.every or args.cron:
            if not args.source:
                raise sc.ScheduleRefused("name the source to change: jason cadence SOURCE --every SPAN --by NAME")
            row = sc.set_cadence(data_dir, args.source, every=args.every or "", cron=args.cron or "",
                                 window=args.window, by=by, zone=zone)
            print(f"{row.key}: {row.words()}, changed by {row.set_by} at {row.set_at}; adopted")
            return 0
        if args.window is not None:
            raise sc.ScheduleRefused("--window goes with --every or --cron")
        if args.restore or args.restore_all:
            rows = sc.restore(data_dir, args.restore or None, by=by, zone=zone)
            for row in rows:
                print(f"{row.key}: the default, {row.words()}; adopted by {row.set_by} at {row.set_at}")
            if not rows:
                print("nothing to restore")
            return 0
        if args.pause:
            row = sc.pause(data_dir, args.pause, why=args.why or "", by=by)
            print(f"{row.key}: paused by {row.paused_by} at {row.paused_at}: {row.paused_why}")
            return 0
        if args.resume:
            for row in sc.resume(data_dir, args.resume, by=by):
                print(f"{row.key}: resumed by {row.resumed_by} at {row.resumed_at}")
            return 0
        if args.run_now:
            job = sc.run_now(data_dir, args.run_now, by=by or sc.by_default())
            print(f"{args.run_now}: queued as job {job.id} [{job.job_class.value}]: {job.command} "
                  f"(jason jobs show {job.id})")
            return 0
        if args.source:
            raise sc.ScheduleRefused(f"what to do with {args.source}: --every or --cron (with --by), or see the list "
                                     f"(jason cadence)")
    except sc.ScheduleRefused as exc:
        print(f"jason cadence: {exc}", file=sys.stderr)
        return 2
    rows = sc.listing(data_dir, zone=zone)
    if args.json:
        print(json.dumps({"community": name, "zone": zone_name, "schedules": rows}, indent=1))
        return 0
    print(f"Schedules of {name} (times in {zone_name}; jason serve's scheduler runs the adopted ones):\n")
    print("\n".join(sc.lines(rows)))
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("cadence", help="Each source's schedule in jason serve's scheduler: list; change one (never "
                                       "faster than its floor), restore or adopt the default, pause, resume, or run "
                                       "now; recorded with who and when")
    add_common(p)
    p.add_argument("source", nargs="?", help="with --every or --cron: the source to change")
    p.add_argument("--community", metavar="C", help="the community (default the active profile)")
    p.add_argument("--json", action="store_true", help="print JSON")
    how = p.add_mutually_exclusive_group()
    how.add_argument("--every", metavar="SPAN", help="run every SPAN (10m, 2h, 1d); refused faster than the floor")
    how.add_argument("--cron", metavar="CRON", help='a five-field cron ("0 2 * * *") in the community\'s time zone')
    p.add_argument("--window", metavar="HH-HH", help="with --every or --cron: the hours it runs (07-22), or all")
    act = p.add_mutually_exclusive_group()
    act.add_argument("--restore", metavar="SOURCE", help="back to the registry's default, adopted (with --by)")
    act.add_argument("--restore-all", action="store_true", help="every source back to its default, adopted (with --by)")
    act.add_argument("--pause", metavar="SOURCE", help="pause one source (with --why and --by)")
    act.add_argument("--resume", metavar="SOURCE", help="clear a pause, its failures, and its backoff (with --by)")
    act.add_argument("--run-now", metavar="SOURCE", help="add its command to the queue once, now")
    p.add_argument("--why", default="", help="with --pause: why")
    p.add_argument("--by", default="", metavar="NAME", help="who makes the change (recorded with when)")
    p.set_defaults(func=cmd_cadence)


__all__ = ["cmd_cadence", "register"]
