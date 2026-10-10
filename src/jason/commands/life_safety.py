"""``jason life-safety``: the deficiency register (docs/console/screens/life-safety.md, "Actions").

- ``--list [--system KEY] [--json]``: each deficiency, its standing (proposed, open, cleared), and whether it impairs a
  safeguard and the insurer was told.
- ``--propose``: add a row for each open deficiency the library's inspection readings list (once; a second run adds
  nothing). A proposed row is a report's reading, not a finding.
- ``--confirm ID --by NAME``: a person accepts a proposed row.
- ``--impairs ID --value yes|no --by NAME``: whether it impairs a scheduled safeguard (a person's reading).
- ``--cleared ID --record REF --kind KIND --on DATE --by NAME``: the record that cleared it. ``REF`` is a library id; an
  invoice's subject line is not one.
- ``--insurer-told ID --record REF --on DATE --by NAME``: that a person told the insurer, and the record of what was sent.

It writes only ``data/life-safety/deficiencies.json``, append only. It contacts no insurer, vendor, or agent.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable


def _refuse(reason: str) -> int:
    print(f"jason life-safety: {reason}", file=sys.stderr)
    return 2


def cmd_life_safety(args: argparse.Namespace) -> int:
    from jason.commands._shared import data_dir
    from jason.community import community
    from jason.tasks import deficiencies as d

    root = data_dir(args)
    acts = [a for a in ("confirm", "impairs", "cleared", "insurer_told") if getattr(args, a)]
    if len(acts) > 1 or (acts and args.propose):
        return _refuse("one act at a time")
    try:
        if args.propose:
            added = d.propose(root, community())
            print(f"{len(added)} proposed; the register holds {len(d.load(root))}. A proposed row is a report's reading, "
                  "not a finding: `--confirm ID --by NAME` accepts it.")
            for line in d.lines(added):
                print(line)
            return 0
        if args.confirm:
            row = d.confirm(root, args.confirm, by=args.by)
        elif args.impairs:
            if args.value not in ("yes", "no"):
                return _refuse("--impairs ID goes with --value yes or --value no")
            row = d.set_impairs(root, args.impairs, args.value == "yes", by=args.by)
        elif args.cleared:
            row = d.clear(root, args.cleared, record=args.record, kind=args.kind, on=args.on, by=args.by)
        elif args.insurer_told:
            row = d.insurer_told(root, args.insurer_told, record=args.record, on=args.on, by=args.by)
        else:
            body = d.view(root, system=args.system or "")
            if args.json:
                print(json.dumps(body, indent=1))
                return 0
            c = body["counts"]
            print(f"{c['proposed']} proposed, {c['open']} open ({c['impairments']} impair a safeguard, "
                  f"{c['insurerNotTold']} with no record the insurer was told), {c['cleared']} cleared.")
            for line in d.lines(body["rows"]):
                print(line)
            return 0
    except ValueError as exc:
        return _refuse(str(exc))
    print("\n".join(d.lines([row])))
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    from jason.tasks.deficiencies import CLEARED_BY

    p = sub.add_parser("life-safety", help="The deficiency register: propose from the reports' readings, then a person "
                                           "confirms, says whether it impairs a safeguard, links what cleared it, and "
                                           "records that the insurer was told (append only, with who and when)")
    add_common(p)
    p.add_argument("--list", action="store_true", help="list the register (the default)")
    p.add_argument("--system", metavar="KEY", help="with --list: one system")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--propose", action="store_true", help="add a proposed row for each open deficiency in the readings")
    p.add_argument("--confirm", metavar="ID", help="accept a proposed row (with --by)")
    p.add_argument("--impairs", metavar="ID", help="whether it impairs a safeguard (with --value and --by)")
    p.add_argument("--value", choices=("yes", "no"), help="with --impairs")
    p.add_argument("--cleared", metavar="ID", help="link the record that cleared it (with --record, --kind, --on, --by)")
    p.add_argument("--insurer-told", dest="insurer_told", metavar="ID",
                   help="record that a person told the insurer (with --record, --on, --by)")
    p.add_argument("--record", metavar="REF", help="the record's id (a library id, or gmail:ID for a message)")
    p.add_argument("--kind", choices=CLEARED_BY, help="with --cleared: what kind of record cleared it")
    p.add_argument("--on", metavar="DATE", help="the day it was cleared or the insurer told (YYYY-MM-DD)")
    p.add_argument("--by", default="", metavar="NAME", help="who records this (kept with when)")
    p.set_defaults(func=cmd_life_safety)


__all__ = ["cmd_life_safety", "register"]
