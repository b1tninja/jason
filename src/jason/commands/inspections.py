"""``jason inspections``: which inspection periods of each life safety system have a report on file.

For each system the specification lists and each obligation that applies to it (``jason applies``), the periods the
obligation covers by its frequency, and for each one what is on file: an inspection-report reading placed by its own
fields (system, building, inspection date), or a completion a person recorded. A period is covered, partly on file,
not on file, or not yet due. A report that lacks a field is listed as unplaced with the field it lacks; an obligation
that does not apply is listed with the fact that decided it; an undetermined one is a question. The regulation's
record-keeping provisions are recited from the authorities shelf, or said to be missing from it
(``jason.tasks.inspections``, docs/fire-protection.md).

Read-only unless ``--write``, which saves the page (``data/reports/life-safety-records.md``) under its store lock.
``--system KEY`` shows one system, ``--as-of DATE`` asks as of another day, and ``--json`` prints the same as JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Any, Callable


def cmd_inspections(args: argparse.Namespace) -> int:
    from jason import config
    from jason.community import community
    from jason.tasks import inspections as task

    active = community()
    day = date.fromisoformat(args.as_of) if args.as_of else date.today()
    data_dir = config.data_dir(getattr(args, "env", None))
    records = task.review(data_dir, active, as_of=day)
    whole = records
    if args.system:
        one = records.of(args.system)
        if one is None:
            print("systems: " + (", ".join(s.system.key for s in records.systems) or "none listed"), file=sys.stderr)
            return 2
        records = one
    if args.write:                                   # the page is always every system, whatever is printed
        path = task.write(data_dir, whole)
        print(f"wrote {path}", file=sys.stderr)
    if args.json:
        print(json.dumps(records.as_dict(), indent=1))
        return 0
    print(f"{active.name}: life safety records on file, as of {day.isoformat()}")
    print("For each system and each obligation that applies to it: the periods, and the report or completion on file")
    print("in each. A summary, not the record.")
    print()
    for line in task.lines(records):
        print(line)
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("inspections", help="Which inspection periods of each life safety system have a report on file, "
                                           "which do not, and what could not be placed (read-only unless --write)")
    add_common(p)
    p.add_argument("--system", metavar="KEY", help="only this system (its key in the specification)")
    p.add_argument("--as-of", metavar="YYYY-MM-DD", help="the date asked for (default: today)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--write", action="store_true", help="also save the page, data/reports/life-safety-records.md")
    p.set_defaults(func=cmd_inspections)
