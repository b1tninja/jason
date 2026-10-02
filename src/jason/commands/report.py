"""``jason report``: the reports a document can name (``{REPORT:key setting=value}``), each a document of its own.

``jason report --list`` shows each report, when it last ran, and its Doc. ``jason report KEY [setting=value ...]`` runs
one now and saves it (``data/reports/live``); ``--all`` runs every report the board's items name. ``--doc --yes`` also
rewrites the report's own Google Doc on the letterhead (My Drive/Meetings/Reports, private) and, for a PayHOA packet
run, files the run's own PDF there. ``--catalog`` lists PayHOA's packet runs as catalogued (``report_runs``): a document
includes a run already built, never a new one (``jason.tasks.live_reports``).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from typing import Any, Callable


def _data_dir(args: argparse.Namespace):
    from jason.config import Settings

    return Settings.load(getattr(args, "env", None)).ownership_db.parent


def _reports_folder(drive: Any, home: Any) -> str:
    return drive.child_folder(home.meetings, "Reports") or drive.create_folder("Reports", home.meetings)


def named_reports(data_dir) -> list[tuple[str, dict[str, str]]]:
    """The reports (with their settings) the board's open items name in their notes."""
    from jason.tasks.board_items import load
    from jason.tasks.live_reports import references, stem

    seen: dict[str, tuple[str, dict[str, str]]] = {}
    for item in load(data_dir):
        for key, params in references(item.notes or ""):
            seen.setdefault(stem(key, params), (key, params))
    return list(seen.values())


def _next_meeting() -> date:
    from jason.community import mystique

    return mystique().meeting_schedule().next_meeting(date.today(), monthly=True)


def _catalog(data_dir) -> int:
    from jason.tasks.report_runs import indexed_at, load, month_name

    runs = load(data_dir)
    if not runs:
        print("no packet runs catalogued: jason report treasurers-report reads them from PayHOA")
        return 0
    print(f"PayHOA packet runs, catalogued {indexed_at(data_dir)[:16]}:")
    for r in runs:
        where = ("Drive" if r.get("driveId") else "library copy" if r.get("library") else
                 "downloaded" if r.get("pdf") else "in PayHOA")
        print(f"  {r['packet']:26} {month_name(r['period']) if r['period'] else '?':15} run {r['completedAt'][:10]}  "
              f"{r['pages'] or '?':>3} pages  {where}" + (f"  ({'; '.join(r['notes'])})" if r.get("notes") else ""))
    return 0


def cmd_report(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import mystique
    from jason.tasks import live_reports

    data_dir = _data_dir(args)
    if args.catalog:
        return _catalog(data_dir)
    if args.list or not (args.key or args.all):
        now = datetime.now()
        named = {k for k, _ in named_reports(data_dir)}
        for key, report in sorted(live_reports.REPORTS.items()):
            snap = live_reports.snapshot(key, data_dir)
            age = snap.age_days(now) if snap else None
            when = ("resolved from the catalog when a document is built" if report.offline else
                    "never run" if age is None else f"ran {snap.ran_at[:16].replace('T', ' ')} ({age:.1f} days ago)")
            flags = [w for w, on in (("named in the board's items", key in named),
                                     (f"stale (over {live_reports.STALE_DAYS} days)",
                                      not report.offline and age is not None and age > live_reports.STALE_DAYS),
                                     (f"last refresh failed: {snap.error}" if snap and snap.error else "", bool(snap and snap.error)))
                     if on and w]
            print(f"{key}: {report.title}; {when}" + (f"; {'; '.join(flags)}" if flags else "")
                  + (f"\n  {snap.url}" if snap and snap.doc_id else ""))
        return 0
    try:
        settings = dict(s.split("=", 1) for s in args.settings)
    except ValueError:
        print("settings are written setting=value (period=previous-month)", file=sys.stderr)
        return 2
    targets = named_reports(data_dir) if args.all else [(args.key, settings)]
    unknown = [k for k, _ in targets if k not in live_reports.REPORTS]
    if unknown:
        print(f"no report named {', '.join(unknown)}; the reports are {', '.join(sorted(live_reports.REPORTS))}",
              file=sys.stderr)
        return 2
    if args.doc and not args.yes:
        print("--doc rewrites each report's own Google Doc and files a packet run's PDF (private, My Drive/Meetings/"
              "Reports); add --yes", file=sys.stderr)
        return 2
    community = mystique()
    context = {"on": date.fromisoformat(args.date) if args.date else _next_meeting()}
    failed = 0
    for key, params in targets:
        snap = live_reports.refresh(key, data_dir, community, params, context=context)
        label = live_reports.command_for(live_reports.REPORTS[key], params).removeprefix("jason report ")
        if snap.error:
            failed += 1
            print(f"{label}: could not run ({snap.error}); kept the run of {snap.ran_at or 'never'}")
        else:
            print(f"{label}: ran {snap.ran_at}")
            for row in snap.rows[:3]:
                print(f"  {row}")
    if args.doc:
        from jason.community.spec import spec_module

        from jason.community.profile import load_profile

        home, head = load_profile().drive_home(), load_profile().letterhead()
        with agent_factory(args) as agent:
            drive = agent.drive()
            folder = _reports_folder(drive, home)
            for key, params in targets:
                report = live_reports.REPORTS[key]
                if report.attach is not None:
                    report.attach(agent.payhoa(), drive, data_dir, params, context, folder)
                    live_reports.refresh(key, data_dir, community, params, context=context)   # now with the Drive link
                snap = live_reports.publish(key, data_dir, drive, folder_id=folder, letterhead_id=head.doc_id,
                                            footer=head.footer, params=params)
                print(f"{key}: {snap.url}")
    return 1 if failed else 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("report", help="Run a report a document names ({REPORT:key}) and keep it as its own document")
    add_common(p)
    p.add_argument("key", nargs="?", help="the report to run now (see --list)")
    p.add_argument("settings", nargs="*", metavar="SETTING=VALUE",
                   help="the report's settings, as a document names them (period=previous-month, period=2026-09)")
    p.add_argument("--list", action="store_true", help="each report, when it last ran, and its Doc (the default)")
    p.add_argument("--catalog", action="store_true", help="PayHOA's packet runs as catalogued (no PayHOA call)")
    p.add_argument("--all", action="store_true", help="run every report the board's items name")
    p.add_argument("--date", help="the document's date for relative periods (default: the next board meeting)")
    p.add_argument("--doc", action="store_true",
                   help="also rewrite each report's own Google Doc, and file a packet run's PDF, in Drive (--yes)")
    p.add_argument("--yes", action="store_true", help="confirm --doc")
    p.set_defaults(func=lambda a: cmd_report(a, agent_factory))
