"""``jason schedule``: who does each duty and when, what is due, and which duties nobody owns.

``jason schedule`` lists what falls due in the next 60 days (``--days``, ``--role``), with each item's standing.
``--assignments`` lists the assignments (jason's proposals until the board adopts them). ``--coverage`` checks every
duty jason knows of (the documents' duties, the notice catalog, the recurring deadlines) against the assignments and
lists the ones nobody owns. ``--done KEY DUE --by NAME --evidence TEXT`` records that an occurrence was done.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date, timedelta
from typing import Any, Callable


def _data_dir(args: argparse.Namespace):
    from jason.config import Settings

    return Settings.load(getattr(args, "env", None)).ownership_db.parent


def cmd_schedule(args: argparse.Namespace) -> int:
    from jason.community import community
    from jason.community.schedule import Role, assignments
    from jason.tasks import schedule as task

    c, data_dir = community(), _data_dir(args)
    rows = assignments(c)
    if args.done:
        key, due = args.done
        if not any(a.key == key for a in rows):
            print(f"no assignment {key}", file=sys.stderr)
            return 2
        try:
            row = task.record_done(data_dir, key, date.fromisoformat(due),
                                   date.fromisoformat(args.on) if args.on else date.today(), args.by or "",
                                   args.evidence or "")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"recorded: {row['key']} due {row['due']} done {row['done']} by {row['by']}: {row['evidence']}")
        return 0
    if args.assignments:
        by = Counter(a.adoption.value for a in rows)
        print(f"{len(rows)} assignments: " + ", ".join(f"{n} {k}" for k, n in sorted(by.items())))
        print("\n".join(task.assignment_lines(rows)))
        return 0
    if args.coverage:
        covered, uncovered = task.coverage(c, data_dir)
        total = len(covered) + len(uncovered)
        print(f"{len(covered)} of {total} duties are assigned; {len(uncovered)} are not.")
        kinds = Counter(ref.split(":")[0] if ref.startswith(("notice:", "obligation:")) else ref.split("#")[0]
                        for ref, _ in uncovered)
        print("unassigned by source: " + ", ".join(f"{k} {n}" for k, n in kinds.most_common()))
        for ref, text in uncovered[: args.limit]:
            print(f"  - {ref}: {text}")
        if len(uncovered) > args.limit:
            print(f"  ... {len(uncovered) - args.limit} more (--limit N)")
        loose = task.unscheduled(c, data_dir)
        print()
        print(f"{len(loose)} duties on a clock are owned only by a standing assignment (assigned, not scheduled):")
        for ref, text, who in loose[: args.limit]:
            print(f"  - {ref} [{', '.join(who)}]: {text}")
        return 0
    start = date.today() - timedelta(days=args.past)
    found = task.agenda(c, data_dir, start=start, end=date.today() + timedelta(days=args.days))
    if args.role:
        try:
            role = Role(args.role)
        except ValueError:
            print(f"roles: {', '.join(r.value for r in Role)}", file=sys.stderr)
            return 2
        found = [o for o in found if o.assignment.role is role or o.assignment.backup is role]
    print(f"{len(found)} items from {start} to {date.today() + timedelta(days=args.days)}"
          " (proposed assignments until the board adopts them):")
    print("\n".join(task.lines(found)))
    events = [a for a in rows if a.trigger.value in ("event", "standing")]
    print(f"\nAlso owned, with no date of their own: {len(events)} event-driven or standing assignments "
          "(jason schedule --assignments).")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("schedule", help="Who does each duty and when: what falls due, the assignments, and the duties "
                                        "nobody owns")
    add_common(p)
    p.add_argument("--days", type=int, default=60, help="how far ahead (default 60)")
    p.add_argument("--past", type=int, default=30, help="how far back, for what is overdue (default 30)")
    p.add_argument("--role", help="one role's items (treasurer, secretary, board, ...)")
    p.add_argument("--assignments", action="store_true", help="list the assignments and their standing")
    p.add_argument("--coverage", action="store_true", help="the duties no assignment covers")
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--done", nargs=2, metavar=("KEY", "DUE"), help="record an occurrence done (with --by, --evidence)")
    p.add_argument("--on", help="with --done: the day it was done (default today)")
    p.add_argument("--by", help="with --done: who did it")
    p.add_argument("--evidence", help="with --done: what shows it (the minutes' date and item, a payment, a proof)")
    p.set_defaults(func=cmd_schedule)
