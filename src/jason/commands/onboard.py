"""``jason onboard``: what a new association's profile needs, and what the active profile already has.

``--checklist`` checks every item of the onboarding checklist (``jason.community.onboarding``) against the active
profile and the data on disk, read-only, and prints present, partial, or missing with the evidence; ``--write`` keeps
the report under ``data/onboarding/``. ``--request SOURCE`` prints the items to ask one source for (the prior manager
by default), as the list a board or a new manager sends. ``--items`` prints the checklist itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable


def cmd_onboard(args: argparse.Namespace) -> int:
    from jason.community.onboarding import Group, Source, items, request_markdown

    try:
        group = Group(args.group) if args.group else None
    except ValueError:
        print(f"groups: {', '.join(g.value for g in Group)}", file=sys.stderr)
        return 2
    if args.request is not None:
        try:
            source = Source(args.request) if args.request else Source.PRIOR_MANAGER
        except ValueError:
            print(f"sources: {', '.join(s.value for s in Source)}", file=sys.stderr)
            return 2
        print(request_markdown(source, title=f"Requested from the {source.value}"))
        return 0
    if args.items:
        for g, rows in ((g, items(g)) for g in Group if group in (None, g)):
            print(g.title)
            for i in rows:
                mark = " [person]" if i.by_person else ""
                print(f"  {i.key}: {i.title}{mark}")
                print(f"    why: {i.why}; from: {', '.join(s.value for s in i.sources)}; fills: {i.fills}")
        return 0
    if not args.checklist:
        print("say --checklist, --items, or --request [SOURCE]", file=sys.stderr)
        return 2
    return _checklist(args, group)


def _checklist(args: argparse.Namespace, group: Any) -> int:
    from jason.community import community
    from jason.community.onboarding import Status, by_group, counts, report_dicts
    from jason.config import Settings
    from jason.tasks.onboarding import run, write_report

    settings = Settings.load(args.env)
    data_dir = settings.payhoa_catalog.parent
    the = community()
    results = run(the, data_dir, settings=settings)
    if group is not None:
        results = tuple(r for r in results if r.item.group is group)
    if args.status:
        results = tuple(r for r in results if r.status is Status(args.status))
    if args.write:
        print(f"wrote {write_report(results, data_dir, title=f'Onboarding checklist: {the.name}')}")
    if args.json:
        print(json.dumps(report_dicts(results), indent=1))
        return 0
    total = counts(results)
    print(f"{len(results)} items: {total['present']} present, {total['partial']} partial, {total['missing']} missing")
    for g, rows in by_group(results).items():
        print(g.title)
        for r in rows:
            mark = " [person]" if r.item.by_person else ""
            print(f"  {r.status.value:8} {r.item.key}: {r.item.title}{mark}")
            print(f"           {r.evidence}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("onboard", help="The onboarding checklist for a new association's profile, checked against the active one (read-only)")
    add_common(p)
    p.add_argument("--checklist", action="store_true", help="check each item: present, partial, or missing, with the evidence")
    p.add_argument("--items", action="store_true", help="print the checklist itself: each item, why, where it comes from, and what it fills")
    p.add_argument("--request", nargs="?", const="", default=None, metavar="SOURCE",
                   help="print the items to ask one source for (default: the prior manager)")
    p.add_argument("--group", help="one group, e.g. finance or insurance")
    p.add_argument("--status", choices=("present", "partial", "missing"), help="only items with this status")
    p.add_argument("--write", action="store_true", help="keep the report in data/onboarding/ (private)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_onboard)
