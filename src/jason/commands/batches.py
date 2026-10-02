"""``jason batches``: the bulk-write batches and where each stands (``jason.batches``).

``jason batches`` lists them; ``--show ID`` gives each item's status and the latest events. A batch is run, and resumed,
by the command that made it (``jason owner-info --email-batch``). ``--retry-failed ID`` puts its failed items back to
pending after a person looked at why; ``--resolve ID KEY --sent`` (or ``--not-sent``) answers an item jason could not
verify; ``--cancel ID --yes`` skips what is left.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import Settings

    return Settings.load(args.env).payhoa_catalog.parent


def cmd_batches(args: argparse.Namespace) -> int:
    from jason import batches

    data = _data_dir(args)
    if args.cancel:
        if not args.yes:
            print(f"would skip the pending items of {args.cancel}; add --yes")
            return 0
        batches.cancel(data, args.cancel)
    if args.retry_failed:
        print(f"{batches.retry_failed(data, args.retry_failed)} failed item(s) back to pending")
    if args.resolve:
        batch_id, key = args.resolve
        if args.sent == args.not_sent:
            print("--resolve needs --sent or --not-sent", file=sys.stderr)
            return 2
        batches.resolve(data, batch_id, key, sent=args.sent)
    if args.show:
        info = batches.batch(data, args.show)
        print(batches.lines(info))
        for item in batches.items(data, args.show):
            error = f"  ({item.last_error})" if item.last_error and item.status.value != "sent" else ""
            print(f"  {item.status.value:9} {item.attempts}  {item.key:16} {item.label}{error}")
        print("latest events:")
        for e in batches.events(data, args.show, limit=args.events):
            print(f"  {e['at']}  {e['key'] or '-':16} {e['kind']}: {e['detail']}")
        return 0
    for info in batches.batches(data):
        print(batches.lines(info))
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("batches", help="Bulk-write batches: progress, failures, and resuming")
    add_common(p)
    p.add_argument("--show", metavar="ID", help="one batch's items and latest events")
    p.add_argument("--events", type=int, default=20, help="with --show: how many events (default 20)")
    p.add_argument("--retry-failed", metavar="ID", help="put a batch's failed items back to pending")
    p.add_argument("--resolve", nargs=2, metavar=("ID", "KEY"), help="answer an item jason could not verify")
    p.add_argument("--sent", action="store_true", help="with --resolve: it was sent")
    p.add_argument("--not-sent", action="store_true", help="with --resolve: it was not (back to pending)")
    p.add_argument("--cancel", metavar="ID", help="skip a batch's pending items (with --yes)")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_batches)
