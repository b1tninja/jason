"""``jason respond``: each request of the association, its kind, its clock, its owner, and whether it is on time.

``jason respond`` lists the open requests, the most urgent first, with the next step for each and what PayHOA's own
fields hold. ``--all`` adds the answered ones and how many were on time, by kind. ``--kind`` narrows to one kind.
``--sources`` adds the leads to where each answer is written. ``--draft ID`` drafts the acknowledgment; with
``--gmail`` an email request's acknowledgment becomes a Gmail draft in its thread (dry run unless ``--yes``; never
sent). ``--measure`` scores the kinds against the hand-labelled gold set. It reads the stored PayHOA requests (``jason
sync-catalog`` refreshes them) and never approves, denies, or assigns a request.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace):
    from jason.config import Settings

    return Settings.load(getattr(args, "env", None)).ownership_db.parent


def _day(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _row(h: Any, sources: dict[str, Any] | None) -> dict[str, Any]:
    row = {"id": h.request["id"], "kind": h.kind.value, "standing": h.standing, "received": _day(h.received),
           "due": _day(h.due), "clock": h.clock, "owner": h.rule.assignment if h.rule else "",
           "acknowledged": _day(h.acknowledged), "answered": _day(h.answered), "classifiedBy": h.why,
           "payhoaDue": _day(h.payhoa_due), "payhoaTags": (h.request.get("payhoa") or {}).get("tags") or [],
           "hints": list(h.hints)}
    if sources is not None:
        row["sources"] = sources.get(str(h.request["id"]), {})
    return row


def _drafts(args: argparse.Namespace, found: list[Any], c: Any, data_dir: Path,
            agent_factory: Callable[[Any], Any] | None) -> int:
    from jason.tasks import responses as task

    wanted = [h for h in found if h.closed is None and h.acknowledged is None
              and (args.draft == "all" or str(h.request["id"]) == args.draft)]
    if not wanted:
        print(f"no open, unacknowledged request {args.draft}", file=sys.stderr)
        return 2
    if args.gmail:
        wanted = [h for h in wanted if h.request.get("threadId")]
        if not wanted:
            print("--gmail drafts replies to email requests only; answer a PayHOA request with jason request-comment",
                  file=sys.stderr)
            return 2
    made = task.drafted(data_dir)
    to = tuple(args.to or ())
    plans = []
    for h in wanted:
        text = task.acknowledgment(h, c)
        print(f"== #{h.request['id']} {h.kind.value}, {h.request.get('unit') or 'unit ?'}: {h.request.get('title', '')[:70]}")
        if args.gmail:
            plan = task.reply_plan(h, c)
            before = made.get(str(h.request["id"]))
            print(f"   Gmail draft in the thread {plan['threadId']} ({plan['link']})")
            recipient = ", ".join(to) if to else "the writer of the thread's last message in, read when the draft is made"
            print(f"   To: {recipient}")
            print(f"   Subject: {plan['subject']}")
            if before:
                print(f"   already drafted: Gmail draft {before['draftId']} on {before['at'][:10]}; not drafted again")
            else:
                plans.append(plan)
        print(text)
        if not args.gmail:
            if str(h.request["id"]).isdigit():
                print(f"   send (a person's step): jason request-comment {h.request['id']} \"<the text above>\"")
            else:
                print(f"   an email request: reply in the thread ({h.request.get('link', '')}), or "
                      f"jason respond --draft {h.request['id']} --gmail")
        print()
    if not args.gmail:
        return 0
    if not args.yes:
        print(f"Dry run: add --yes to save {len(plans)} acknowledgment(s) as Gmail drafts in their threads. A draft is "
              "never sent; a person reads it in Gmail and sends it there.")
        return 0
    if agent_factory is None or not plans:
        return 0
    from jason.google.gmail_drafts import GmailDrafts

    with agent_factory(args) as agent:
        drive = agent.drive()
        gmail, drafts = drive.gmail(), GmailDrafts.on(drive)
        for plan in plans:
            made_now = task.make_reply(plan, gmail, drafts, data_dir, to=to)
            print(f"Gmail draft {made_now['draftId']} saved in thread {made_now['threadId']}"
                  f"{'' if made_now['threaded'] else ' (the message it answers has no Message-ID: check its thread)'}"
                  f"{'' if made_now['to'] else '; no recipient found: add one in Gmail'}. Review and send it from Gmail.")
    return 0


def cmd_respond(args: argparse.Namespace, agent_factory: Callable[[Any], Any] | None = None) -> int:
    from jason.community import community
    from jason.community.responses import ResponseKind
    from jason.tasks import responses as task

    c, data_dir = community(), _data_dir(args)
    if getattr(args, "measure", None):
        from jason.tasks.request_kinds import measure, measure_lines

        gold = None if args.measure == "default" else Path(args.measure)
        try:
            result = measure(data_dir, c, gold)
        except FileNotFoundError as exc:
            print(exc, file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps({k: v for k, v in result.items() if k != "misses"} | {"misses": len(result["misses"])}, indent=1))
        else:
            print("\n".join(measure_lines(result)))
        return 0
    found = task.handle(c, data_dir)
    if not args.no_email:
        found = sorted(found + task.email_requests(c, data_dir),
                       key=lambda h: (h.closed is not None, h.due or date.max))
    if args.draft:
        return _drafts(args, found, c, data_dir, agent_factory)
    if args.gmail or args.yes:
        print("--gmail and --yes go with --draft ID", file=sys.stderr)
        return 2
    if args.kind:
        try:
            kind = ResponseKind(args.kind)
        except ValueError:
            print(f"kinds: {', '.join(k.value for k in ResponseKind)}", file=sys.stderr)
            return 2
        found = [h for h in found if h.kind is kind]
    shown = found if args.all else [h for h in found if h.open]
    sources = None
    if args.sources:
        from jason.tasks.response_sources import SourceContext, sources_for

        ctx = SourceContext(data_dir, c)
        sources = {str(h.request["id"]): sources_for(h, c, ctx) for h in shown[:args.limit]}
    if args.json:
        print(json.dumps([_row(h, sources) for h in shown], indent=1))
        return 0
    s = task.summary(found)
    print("open: " + (", ".join(f"{n} {k}" for k, n in sorted(s["open"].items())) or "none"))
    if args.all:
        kinds = sorted(set(s["onTime"]) | set(s["late"]))
        print("answered within the clock: " + ("; ".join(f"{k} {s['onTime'].get(k, 0)} on time, {s['late'].get(k, 0)} late"
                                                      for k in kinds) or "none timed"))
    print("Clocks marked proposed policy are targets until the board adopts them; the handler decides nothing.")
    print("\n".join(task.lines(shown, limit=args.limit, sources=sources)))
    if sources is not None:
        from jason.tasks.response_sources import CAVEATS

        print("\n" + "\n".join(f"* {c_}" for c_ in CAVEATS))
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("respond", help="Each request of the association: its kind, its clock, its owner, and whether "
                                       "the answer is on time")
    add_common(p)
    p.add_argument("--all", action="store_true", help="also the answered requests, and how many were on time")
    p.add_argument("--kind", help="one kind (records request, maintenance request, ...)")
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--no-email", action="store_true", help="leave out members' requests made by email")
    p.add_argument("--sources", action="store_true", help="add the leads to where each answer is written: governing "
                   "document passages, library documents, and precedent violations for a complaint")
    p.add_argument("--draft", metavar="ID|all", help="draft the acknowledgment for an open, unacknowledged request "
                   "(or all of them), for a person to read and send")
    p.add_argument("--gmail", action="store_true", help="with --draft: an email request's acknowledgment as a Gmail "
                   "draft reply in its thread (dry run unless --yes; never sent)")
    p.add_argument("--to", action="append", metavar="ADDRESS", help="with --gmail: the recipient, instead of the "
                   "writer of the thread's last message")
    p.add_argument("--yes", action="store_true", help="with --draft --gmail: save the Gmail drafts (default: dry run)")
    p.add_argument("--measure", nargs="?", const="default", metavar="GOLD",
                   help="score the kinds against the hand-labelled gold set (data/responses/kind-gold.json)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=lambda a: cmd_respond(a, agent_factory))
