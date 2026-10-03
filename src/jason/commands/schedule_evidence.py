"""``jason schedule-evidence``: evidence on disk that a scheduled duty was done, for a person to confirm.

``jason schedule-evidence`` lists, for each occurrence of each assignment from ``--since`` (default a year ago) to
``--until`` (default today), what jason found that shows it done: the minutes' passage, the notice and how early it
went, the minutes on file, a mailing, a payment. Nothing is recorded. ``--record KEY DUE --by NAME`` records one
occurrence a person has read and confirms (``schedule.record_done``), with the evidence found unless ``--evidence``
gives the person's own; ``--on`` sets the day it was done (default the evidence's date).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from typing import Any, Callable


def _data_dir(args: argparse.Namespace):
    from jason.config import Settings

    return Settings.load(getattr(args, "env", None)).ownership_db.parent


def cmd_schedule_evidence(args: argparse.Namespace) -> int:
    from jason.community import community
    from jason.tasks import schedule_evidence as task

    c, data_dir = community(), _data_dir(args)
    try:
        start = date.fromisoformat(args.since) if args.since else date.today() - timedelta(days=365)
        end = date.fromisoformat(args.until) if args.until else date.today()
    except ValueError as exc:
        print(f"a date is YYYY-MM-DD: {exc}", file=sys.stderr)
        return 2
    if args.record:
        key, due_text = args.record
        if not args.by:
            print("--record needs --by NAME: who read the evidence and confirms it", file=sys.stderr)
            return 2
        try:
            due = date.fromisoformat(due_text)
            on = date.fromisoformat(args.on) if args.on else None
        except ValueError as exc:
            print(f"a date is YYYY-MM-DD: {exc}", file=sys.stderr)
            return 2
        found = task.find(task.propose(c, data_dir, start=due, end=due, keys=[key]), key, due)
        if found is None:
            print(f"no occurrence of {key} falls due on {due} (jason schedule --assignments)", file=sys.stderr)
            return 2
        if found.done:
            print(f"already recorded: {key} due {due} done {found.done['done']} by {found.done['by']}", file=sys.stderr)
            return 2
        try:
            row = task.record(data_dir, found, args.by, on=on, evidence=args.evidence or "")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"recorded: {row['key']} due {row['due']} done {row['done']} by {row['by']}: {row['evidence']}")
        return 0
    proposals = task.propose(c, data_dir, start=start, end=end, keys=args.key or ())
    path = task.write(data_dir, proposals, start=start, end=end)
    if args.json:
        print(json.dumps({"summary": task.summary(proposals), "proposals": [p.row() for p in proposals]}, indent=1))
        return 0
    counts = task.summary(proposals)
    print(f"Evidence for {len(proposals)} occurrences from {start} to {end} (proposals; nothing is recorded):")
    for key, n in counts.items():
        print(f"  {key}: {n['occurrences']} due; {n['recorded']} recorded, {n['proposed']} proposed, "
              f"{n['partial']} partial, {n['contrary']} contrary, {n['none']} with none")
    loose = [k for k in task.unserved(c) if not args.key or k in args.key]
    if loose:
        print(f"  no evidence rule yet: {', '.join(loose)}")
    print()
    print("\n".join(task.lines(proposals, show_none=args.all)))
    print()
    print(f"Kept in {path}. Record one a person confirms: jason schedule-evidence --record KEY DUE --by NAME")
    for caveat in task.CAVEATS:
        print(f"* {caveat}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("schedule-evidence", help="Evidence on disk that each scheduled duty was done, proposed for a "
                                                 "person to confirm and record")
    add_common(p)
    p.add_argument("--since", help="from this day (YYYY-MM-DD; default a year ago)")
    p.add_argument("--until", help="to this day (YYYY-MM-DD; default today)")
    p.add_argument("--key", action="append", help="one assignment's occurrences (repeatable)")
    p.add_argument("--all", action="store_true", help="also list the occurrences with no evidence")
    p.add_argument("--json", action="store_true", help="the proposals as JSON")
    p.add_argument("--record", nargs=2, metavar=("KEY", "DUE"),
                   help="record one occurrence a person confirms (with --by; --evidence to give your own)")
    p.add_argument("--by", help="with --record: who read the evidence and confirms it")
    p.add_argument("--on", help="with --record: the day it was done (default the evidence's date)")
    p.add_argument("--evidence", help="with --record: the evidence in the person's own words")
    p.set_defaults(func=cmd_schedule_evidence)
