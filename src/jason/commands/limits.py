"""``jason limits``: the reasonable defaults jason runs on, with the value in force and where it came from (``jason.limits``).

Read-only. A limit is changed by setting ``JASON_LIMIT_<KEY>`` in the environment, the project's ``.env``, or the user config
(``upload.max_bytes`` is ``JASON_LIMIT_UPLOAD_MAX_BYTES``), or by the profile's ``Community.limits()``.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable


def cmd_limits(args: argparse.Namespace) -> int:
    from jason import limits
    from jason.config import Settings

    try:
        settings = Settings.load()
    except Exception:  # noqa: BLE001 - the limits read without a complete .env
        settings = None
    community = None
    try:
        from jason.community import community as active

        community = active()
    except Exception:  # noqa: BLE001 - no profile: the instance and the defaults
        community = None
    rows = limits.listing(settings, community)
    if args.key:
        rows = [r for r in rows if r["key"] == args.key]
        if not rows:
            print(f"no limit {args.key}; the limits are {', '.join(l.key for l in limits.all_limits())}", file=sys.stderr)
            return 2
    if args.json:
        print(json.dumps(rows, indent=1))
        return 0
    for r in rows:
        unit = "" if r["unit"] == "switch" else f" {r['unit']}"
        rng = "" if r["minimum"] is None and r["maximum"] is None else f"; range {r['minimum']}-{r['maximum']}{unit}"
        print(f"{r['key']} = {r['value']}{unit}  [{r['source']}]{' (held to its range)' if r['clamped'] else ''}")
        print(f"    default {r['default']}{rng}; set {r['env']}")
        print(f"    {r['description']}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("limits", help="The reasonable defaults jason runs on, with the value in force and its source (read-only)")
    add_common(p)
    p.add_argument("key", nargs="?", help="one limit (none: all)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_limits)
