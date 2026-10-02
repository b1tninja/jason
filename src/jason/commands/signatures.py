"""``jason signatures``: who writes to the association, read from the signature block at the end of their email.

Dry by default: lists the senders a run would read and how many messages, from the headers already on disk
(``data/gmail/correspondence.json``), then the stored result. ``--fetch`` reads those messages from Gmail (read-only),
keeps only each signature's fields (an owner's or individual's only as a role and presence flags), and writes
``data/gmail/signatures.json``. No body is stored. Nothing is written to Gmail, PayHOA, or Drive.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable


def run(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import mystique
    from jason.config import Settings
    from jason.tasks.signatures import fetch, plan, report, summary_lines

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    community = mystique()
    targets = plan(data_dir, community, per_sender=args.per_sender, domains=args.domains or (), threads=args.threads or (),
                   non_owners=args.non_owners, limit=args.limit, include_automated=args.include_automated, refresh=args.refresh)
    messages = sum(len(t.messages) for t in targets)
    if args.fetch:
        if not targets:
            print("nothing to read: every selected message was read already (--refresh reads them again)")
        else:
            print(f"reading {messages} messages from {len(targets)} senders (read-only; only signature fields are kept)")
            with agent_factory(args) as agent:
                counts = fetch(agent.gmail(), data_dir, community, targets, non_owners=args.non_owners, log=print)
            print(f"read {counts}")
    result = report(data_dir, community)
    if args.json:
        out: dict[str, Any] = {"summary": result["summary"]}
        if not args.fetch:
            out["plan"] = [{"sender": t.key, "kind": t.kind, "domain": t.domain, "party": t.party, "known": t.known,
                            "messages": len(t.messages), "last": t.last[:10]} for t in targets]
        print(json.dumps(out, indent=1, default=str))
        return 0
    if not args.fetch:
        print(f"would read {messages} messages from {len(targets)} senders (dry run; --fetch reads them):")
        for t in targets:
            who = t.key if t.kind == "business" else t.party
            known = f"  [{t.known}]" if t.known else ""
            print(f"  {t.kind:8} {who[:48]:48} {len(t.messages)} message(s), latest {t.last[:10]}{known}")
        print("")
    for line in summary_lines(result):
        print(line)
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("signatures", help="Who writes to the association, from email signatures (dry unless --fetch; keeps no body)")
    add_common(p)
    p.add_argument("--fetch", action="store_true", help="read the selected messages from Gmail (read-only) and store the signature fields")
    p.add_argument("--domains", nargs="+", metavar="DOMAIN", help="only senders at these domains (or their subdomains)")
    p.add_argument("--threads", nargs="+", metavar="THREAD_ID", help="only messages in these Gmail threads")
    p.add_argument("--non-owners", action="store_true", help="skip senders the records know as owners, buyers, or board members")
    p.add_argument("--per-sender", type=int, default=2, help="latest messages per sender (default 2)")
    p.add_argument("--limit", type=int, default=40, help="messages read at most in one run (default 40)")
    p.add_argument("--include-automated", action="store_true", help="also read noreply and notification mailboxes")
    p.add_argument("--refresh", action="store_true", help="read messages already read again")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=lambda args: run(args, agent_factory))
