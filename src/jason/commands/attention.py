"""``jason attention``: what needs attention across the governance systems, most urgent first.

One section per system (``jason.tasks.attention``): the board meetings' notice and minutes clocks, the schedule,
members' requests, intake questions, conflicts, notices with follow-ups owed, the living documents, and the documents'
timed duties nothing tracks. Each line names the command that gives its detail. ``--section requests`` (repeatable) narrows; ``--limit N`` sets the lines per section;
``--json`` prints JSON; ``--private`` leaves units out (what the board packet's ``{REPORT:attention}`` prints). Reads
disk only, writes nothing, and decides nothing.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable

from jason.commands._shared import data_dir, day, to_json


def cmd_attention(args: argparse.Namespace) -> int:
    from jason.community import community
    from jason.tasks import attention

    try:
        found = attention.digest(community(), data_dir(args), on=day(args.on), limit=args.limit, past=args.past,
                                 sections=tuple(args.section or attention.SECTIONS), private=args.private)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(to_json(found.as_dict()) if args.json else "\n".join(found.lines()))
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    from jason.tasks.attention import LIMIT, PAST_DAYS, SECTIONS

    p = sub.add_parser("attention", help="What needs attention across the governance systems: clocks passed or near, "
                                         "questions open, follow-ups owed; most urgent first")
    add_common(p)
    p.add_argument("--section", action="append", choices=SECTIONS, help="one section (repeatable)")
    p.add_argument("--limit", type=int, default=LIMIT, help=f"lines per section (default {LIMIT})")
    p.add_argument("--past", type=int, default=PAST_DAYS,
                   help=f"how far back the schedule looks for what is overdue (default {PAST_DAYS} days)")
    p.add_argument("--on", help="the day to read as today (YYYY-MM-DD; default today)")
    p.add_argument("--private", action="store_true", help="leave units out, as the board packet does")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_attention)
