"""`jason minutes-privacy`: open minutes that name a member in an executive-session matter, and corrected copies."""

from __future__ import annotations

import argparse
from typing import Any, Callable


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    parser = sub.add_parser("minutes-privacy",
                            help="Find open minutes naming a member in a delinquency, payment plan, or discipline (CIV 4935); --correct writes a copy")
    add_common(parser)
    parser.add_argument("--correct", action="store_true", help="Write a corrected copy of each, for the Secretary (originals unchanged)")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from jason.config import Settings
    from jason.tasks.minutes_privacy import correct, scan

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    result = scan(data_dir)
    print(f"{result['minutes']} minutes read; {len(result['withNames'])} name a member in an executive-session matter")
    for m in result["withNames"]:
        print(f"- {m['date']} {m['name']}: {len(m['hits'])} passage(s)")
        for h in m["hits"]:
            print(f"    \"{h['passage'][:110]}\"")
        if args.correct:
            print(f"    corrected copy: {correct(data_dir, m['id'])}")
    return 0
