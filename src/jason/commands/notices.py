"""``jason notices``: each notice's delivery to every member, what became of it, and the follow-ups the law asks for.

``jason notices`` lists the notices in the ledger. ``jason notices KEY --sync`` reads the notice's batches (every jason
batch whose id starts with KEY, test batches left out) and each attempt's outcome from PayHOA. Emails come from
the communications log, where SendGrid's bounces and PayHOA's failures land; letters from the Mailroom with Lob's
events. ``jason notices KEY`` prints each member's standing and the follow-ups owed (``notice_ledger.FOLLOW_UPS``):
- a bounce is resent by mail (Civil Code 4041(e));
- a letter that never mailed is sent again;
- a returned letter's member is asked for an address.

A follow-up is sent through the commands that guard each send; their batches, named with the same KEY, are read in
on the next --sync. Read-only in PayHOA.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import Settings

    return Settings.load(getattr(args, "env", None)).ownership_db.parent


def notice_batches(data_dir: Path, key: str) -> list[dict[str, Any]]:
    """The notice's jason batches: ids that start with ``key``, without test batches."""
    from jason import batches

    return [b for b in batches.batches(data_dir) if str(b.get("id", "")).startswith(key) and "-test" not in str(b["id"])]


def cmd_notices(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.tasks import notice_ledger

    data_dir = _data_dir(args)
    if not args.key:
        rows = notice_ledger.notices(data_dir)
        if not rows:
            print("no notices in the ledger: jason notices KEY --sync reads one (KEY: its batches' prefix, e.g. "
                  "owner-info-2027)")
        for key, n, synced in rows:
            print(f"{key}: {n} attempts; synced {synced[:16]}")
        return 0
    if args.sync:
        found = notice_batches(data_dir, args.key)
        if not found and not args.subject:
            print(f"no batches start with {args.key}: jason batches lists them (or give --subject for a notice sent "
                  "from PayHOA's screens)", file=sys.stderr)
            return 2
        since = args.since or (min(str(b.get("created") or "") for b in found)[:10] if found else "")
        if not since:
            print("--since DATE is needed with --subject alone", file=sys.stderr)
            return 2
        with agent_factory(args) as agent:
            counts = notice_ledger.sync(agent.payhoa(), agent.org_id, data_dir, args.key, [b["id"] for b in found],
                                        since=since, subject=args.subject or "")
        print(f"{args.key}: read {', '.join(b['id'] for b in found)} since {since}")
        print("  " + "; ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    standing = notice_ledger.standing(notice_ledger.load(data_dir, args.key), general=args.general)
    if args.json:
        print(notice_ledger.as_json(standing))
        return 0
    print("\n".join(notice_ledger.lines(standing)))
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("notices", help="Each notice's delivery to every member, bounces and returns, and the follow-ups the law asks for")
    add_common(p)
    p.add_argument("key", nargs="?", help="the notice: its batches' id prefix (owner-info-2027)")
    p.add_argument("--sync", action="store_true", help="read the notice's batches and their outcomes from PayHOA (read-only)")
    p.add_argument("--subject", help="with --sync: also every message in PayHOA's log whose subject contains this "
                   "(a notice sent from PayHOA's screens: a meeting notice, a broadcast)")
    p.add_argument("--since", help="with --sync: the day the notice went out (default: its first batch's)")
    p.add_argument("--general", action="store_true",
                   help="a general notice (Civil Code 4045: a meeting notice) that was also posted where the annual policy "
                        "statement designates, so the posting delivered it: a failed message is noted, a resend is owed "
                        "only to a member who asked for individual delivery (4045(b)), and a bounce still asks for a "
                        "working email. Not posted: leave this off, since the messages were the delivery")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=lambda a: cmd_notices(a, agent_factory))
