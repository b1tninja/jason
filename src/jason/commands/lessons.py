"""``jason lessons``: what went wrong, what changed, and what is still open (``jason.community.lessons``).

``jason lessons`` lists every lesson, jason's general ones and the community's own; ``--area mailroom`` narrows to one
area; ``--open`` leaves out the fixed ones. A command that acts in an area shows that area's open lessons in its dry
run, and ``{REPORT:lessons area=owner-info}`` carries them into the board packet.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable


def cmd_lessons(args: argparse.Namespace) -> int:
    from dataclasses import asdict

    from jason.community import mystique
    from jason.community.lessons import Area, Status, lessons

    try:
        area = Area(args.area) if args.area else None
    except ValueError:
        print(f"areas: {', '.join(a.value for a in Area)}", file=sys.stderr)
        return 2
    found = [l for l in lessons(mystique()) if (area is None or l.applies_to(area))
             and (not args.open or l.status is not Status.FIXED)]
    if args.json:
        print(json.dumps([{**asdict(l), "learned": l.learned.isoformat(), "areas": [a.value for a in l.areas],
                           "status": l.status.value} for l in found], indent=1))
        return 0
    for status in (Status.DECISION, Status.OPEN, Status.FIXED):
        group = [l for l in found if l.status is status]
        if not group:
            continue
        print(f"{status.value.upper()} ({len(group)})")
        for l in group:
            print(f"  {l.key} [{', '.join(a.value for a in l.areas)}; {l.learned.isoformat()}]")
            print(f"    what: {l.what}")
            print(f"    why: {l.why}")
            print(f"    change: {l.change}")
            for g in l.guards:
                print(f"    guard: {g}")
            for n in l.notes:
                print(f"    note: {n}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("lessons", help="What went wrong, what changed, and what is still open")
    add_common(p)
    p.add_argument("--area", help="one area: " + ", ".join(a.value for a in _areas()))
    p.add_argument("--open", action="store_true", help="only lessons still to act on (open or awaiting a decision)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_lessons)
    register_sop(sub, add_common)
    register_conflicts(sub, add_common)


def _areas() -> tuple:
    from jason.community.lessons import Area

    return tuple(Area)


def cmd_conflicts(args: argparse.Namespace) -> int:
    """Each written provision a higher authority displaces: what still governs, what yields, and who is acting."""
    from dataclasses import asdict

    from jason.community import community
    from jason.community.authority_order import conflict_lines, conflicts
    from jason.community.lessons import Area

    try:
        area = Area(args.area) if args.area else None
    except ValueError:
        print(f"areas: {', '.join(a.value for a in Area)}", file=sys.stderr)
        return 2
    if args.leads:
        from jason.commands._shared import data_dir as _data_dir
        from jason.tasks import conflict_leads

        data_dir = _data_dir(args)
        found_leads = conflict_leads.leads(data_dir, community(), document=args.document or "",
                                           since=args.since or "")
        if args.json:
            print(json.dumps([{**asdict(l), "change": asdict(l.change)} for l in found_leads], indent=1))
            return 0
        if not found_leads:
            print("no leads: jason outlines and jason law-history --export write what this reads")
            return 0
        print(f"{len(found_leads)} leads: a change in the Act that may postdate a document, and the section that speaks "
              "to it. A lead is for a person to read beside the statute; one that is a conflict becomes a Conflict row.")
        print("\n".join(conflict_leads.lines(found_leads, community())))
        return 0
    found = conflicts(community(), area, open_only=args.open)
    if args.json:
        print(json.dumps([{**asdict(c), "tier": c.tier.label, "authority_tier": c.authority_tier.label,
                           "since": c.since.isoformat() if c.since else None, "clarity": c.clarity.value,
                           "status": c.status.value, "areas": [a.value for a in c.areas]} for c in found], indent=1))
        return 0
    if not found:
        print("no conflicts recorded" + (f" in {area.value}" if area else "") + ": a provision a higher authority "
              "displaces is a Conflict row in the specification (Community.conflicts())")
        return 0
    print("Follow each provision as written, except the part that yields; that part follows the higher authority.")
    print("\n".join(conflict_lines(found)))
    return 0


def register_conflicts(sub: Any, add_common: Callable[[Any], None]) -> None:
    p = sub.add_parser("conflicts", help="Written provisions a higher authority displaces: what still governs and what "
                                         "yields (Civil Code 4205)")
    add_common(p)
    p.add_argument("--area", help="one area: " + ", ".join(a.value for a in _areas()))
    p.add_argument("--open", action="store_true", help="leave out the resolved ones")
    p.add_argument("--leads", action="store_true",
                   help="find candidates: each change in the Davis-Stirling Act since 2014 that may postdate a document, "
                        "with the section that cites it or speaks to its subject (reads the stored outlines and law history)")
    p.add_argument("--document", help="with --leads: one document's outline key (bylaws, enforcement-policy)")
    p.add_argument("--since", help="with --leads: only changes operative on or after this date (2026-01-01: this year's laws)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_conflicts)


def cmd_sop(args: argparse.Namespace) -> int:
    from jason.community import mystique
    from jason.community.procedures import find, lines, procedures

    community = mystique()
    if not args.key:
        for proc in procedures(community):
            print(f"{proc.key}: {proc.title} ({len(proc.steps)} steps). {proc.when}")
        return 0
    proc = find(args.key, community)
    if proc is None:
        print(f"no procedure {args.key}: {', '.join(p.key for p in procedures(community))}", file=sys.stderr)
        return 2
    print("\n".join(lines(proc, community)))
    return 0


def register_sop(sub: Any, add_common: Callable[[Any], None]) -> None:
    p = sub.add_parser("sop", help="Standard operating procedures: a task's steps, commands, checks, and reading")
    add_common(p)
    p.add_argument("key", nargs="?", help="the procedure to print (none: list them)")
    p.set_defaults(func=cmd_sop)
