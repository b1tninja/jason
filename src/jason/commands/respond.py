"""``jason respond``: each request of the association, its kind, its clock, its owner, and whether it is on time.

``jason respond`` lists the open requests, the most urgent first, with the next step for each. ``--all`` adds the
answered ones and how many were on time, by kind. ``--kind`` narrows to one kind. It reads the stored PayHOA requests
(``jason sync-catalog`` refreshes them) and never approves, denies, or assigns a request.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Any, Callable


def _data_dir(args: argparse.Namespace):
    from jason.config import Settings

    return Settings.load(getattr(args, "env", None)).ownership_db.parent


def cmd_respond(args: argparse.Namespace) -> int:
    from jason.community import community
    from jason.community.responses import ResponseKind
    from jason.tasks import responses as task

    c, data_dir = community(), _data_dir(args)
    found = task.handle(c, data_dir)
    if not args.no_email:
        found = sorted(found + task.email_requests(c, data_dir),
                       key=lambda h: (h.closed is not None, h.due or date.max))
    if args.draft:
        wanted = [h for h in found if h.closed is None and h.acknowledged is None
                  and (args.draft == "all" or str(h.request["id"]) == args.draft)]
        if not wanted:
            print(f"no open, unacknowledged request {args.draft}", file=sys.stderr)
            return 2
        for h in wanted:
            text = task.acknowledgment(h, c)
            print(f"== #{h.request['id']} {h.kind.value}, {h.request.get('unit') or 'unit ?'}: {h.request.get('title', '')[:70]}")
            print(text)
            if str(h.request["id"]).isdigit():
                print(f"   send (a person's step): jason request-comment {h.request['id']} \"<the text above>\"")
            else:
                print(f"   an email request: reply in the thread ({h.request.get('link', '')})")
            print()
        return 0
    if args.kind:
        try:
            kind = ResponseKind(args.kind)
        except ValueError:
            print(f"kinds: {', '.join(k.value for k in ResponseKind)}", file=sys.stderr)
            return 2
        found = [h for h in found if h.kind is kind]
    if not args.all:
        shown = [h for h in found if h.open]
    else:
        shown = found
    if args.json:
        print(json.dumps([{"id": h.request["id"], "kind": h.kind.value, "standing": h.standing, "received": str(h.received),
                           "due": str(h.due), "clock": h.clock, "owner": h.rule.assignment if h.rule else "",
                           "acknowledged": str(h.acknowledged), "answered": str(h.answered)} for h in shown], indent=1))
        return 0
    s = task.summary(found)
    print("open: " + (", ".join(f"{n} {k}" for k, n in sorted(s["open"].items())) or "none"))
    if args.all:
        kinds = sorted(set(s["onTime"]) | set(s["late"]))
        print("answered within the clock: " + ("; ".join(f"{k} {s['onTime'].get(k, 0)} on time, {s['late'].get(k, 0)} late"
                                                      for k in kinds) or "none timed"))
    print("Clocks marked proposed policy are targets until the board adopts them; the handler decides nothing.")
    print("\n".join(task.lines(shown, limit=args.limit)))
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("respond", help="Each request of the association: its kind, its clock, its owner, and whether "
                                       "the answer is on time")
    add_common(p)
    p.add_argument("--all", action="store_true", help="also the answered requests, and how many were on time")
    p.add_argument("--kind", help="one kind (records request, maintenance request, ...)")
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--no-email", action="store_true", help="leave out members' requests made by email")
    p.add_argument("--draft", metavar="ID|all", help="draft the acknowledgment for an open, unacknowledged request "
                   "(or all of them), for a person to read and send")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_respond)
