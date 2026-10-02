"""`jason drive-labels`: jason's labels on the association's Drive files, stored as appProperties.

With no flags it is a dry run: the plan's counts and the exact properties that would be set, diffed against the cache
``data/drive/app-properties.json``. ``--show FILE_ID`` puts one file's plan beside its appProperties (``--live`` reads
them from Drive). ``--apply --yes`` writes; without ``--yes`` ``--apply`` lists what it would write and sends nothing.
``--search key=value`` finds files by one property. Non-interactive runs fail fast when the Google token is missing.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    parser = sub.add_parser(
        "drive-labels",
        help="Label the association's Drive files with jason's appProperties (dry run unless --apply --yes)",
    )
    add_common(parser)
    parser.add_argument("--show", metavar="FILE_ID", help="One file's planned labels beside its current appProperties")
    parser.add_argument("--live", action="store_true", help="With --show, read the current appProperties from Drive")
    parser.add_argument("--apply", action="store_true", help="Write the labels (needs --yes; otherwise a dry run)")
    parser.add_argument("--yes", action="store_true", help="Confirm the writes to Drive")
    parser.add_argument("--used", action="store_true",
                        help="Only files an agenda item or a meeting record used (the recommended first apply)")
    parser.add_argument("--limit", type=int, default=0, help="Files to write (with --apply) or list (dry run)")
    parser.add_argument("--search", metavar="KEY=VALUE", help="Files whose appProperty KEY equals VALUE exactly")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    parser.set_defaults(func=lambda args: run(args, agent_factory))


def run(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import mystique
    from jason.config import Settings
    from jason.tasks import drive_labels as task

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.search:
        key, sep, value = args.search.partition("=")
        if not sep or not key.strip():
            print("--search takes KEY=VALUE, e.g. jason_kind=minutes")
            return 2
        with agent_factory(args) as agent:
            hits = task.search(agent.drive(), key.strip(), value.strip())
        if args.json:
            print(json.dumps(hits, indent=2))
        else:
            for h in hits:
                print(f"{h.get('id')}  {h.get('name')}")
            print(f"{len(hits)} files with {key.strip()}={value.strip()!r}")
        return 0

    community = mystique()
    rows = task.schema(community)
    plan = task.plan(data_dir, community)
    if args.used:
        # Only the files the board used: linked by an agenda item or a meeting's own record (not the audio book, not
        # every file the Drive rules classify).
        used = {task.Origin.AGENDA_LINK, task.Origin.MEETING_RECORD}
        plan["files"] = [f for f in plan["files"] if used & set(f["origins"])]
        plan["counts"]["files"] = len(plan["files"])
    cache = task.load_cache(data_dir)

    if args.show:
        current = cache.get(args.show, {})
        if args.live:
            from jason.google.drive_properties import get_app_properties

            with agent_factory(args) as agent:
                current = get_app_properties(agent.drive(), args.show)
        print(json.dumps({**task.show(plan, args.show, current, rows), "currentFrom": "Drive" if args.live else "cache"},
                         indent=2))
        return 0

    waiting = task.pending(plan, cache, rows)
    if args.apply and args.yes:
        with agent_factory(args) as agent:
            result = task.apply(agent.drive(), plan, yes=True, data_dir=data_dir, rows=rows, limit=args.limit, log=print)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"written {result['written']}, unchanged {result['unchanged']}, failed {len(result['failed'])}; "
                  f"cache {result.get('cache')}")
        return 1 if result["failed"] else 0

    if args.json:
        print(json.dumps({**plan, "pending": waiting[: args.limit or None]}, indent=2))
    else:
        print("\n".join(task.summary_lines(plan, waiting, limit=args.limit or 10)))
        if args.apply:
            print("\nnothing written: --apply needs --yes")
    return 0


__all__ = ["register", "run"]
