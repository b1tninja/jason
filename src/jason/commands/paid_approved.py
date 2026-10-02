"""`jason paid-vs-approved`: each approval in the minutes followed to its payments, and large payments no approval explains."""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    parser = sub.add_parser("paid-vs-approved", help="What the minutes approved against what PayHOA paid (disk only)")
    add_common(parser)
    parser.add_argument("--limit", type=int, default=12, help="Lines per section")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from jason.config import Settings
    from jason.tasks.paid_vs_approved import build, summary_lines

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    result = build(data_dir)
    print(json.dumps(result, indent=2, default=str) if args.json else "\n".join(summary_lines(result, limit=args.limit)))
    return 0
