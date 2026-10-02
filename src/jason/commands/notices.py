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

``jason notices --catalog`` lists what the law requires of each kind of notice (``jason.community.notice_catalog``);
``jason notices KEY --catalog`` prints one, with the governing documents' clauses and the stricter clock.
``jason notices KEY --proof --event DATE`` prints the notice's proof-of-notice record (``tasks.notice_proof``): the
evidence its requirement calls for, what the ledger shows, the window, and who was reached only after it. A ledger
KEY names its requirement by starting with it ("board-meeting-2026-10-20"); otherwise give --requirement.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable

from jason.commands._shared import data_dir as _data_dir
from jason.commands._shared import day as _day


def notice_batches(data_dir: Path, key: str) -> list[dict[str, Any]]:
    """The notice's jason batches: ids that start with ``key``, without test batches."""
    from jason import batches

    return [b for b in batches.batches(data_dir) if str(b.get("id", "")).startswith(key) and "-test" not in str(b["id"])]


def _catalog(key: str | None) -> int:
    """The notice requirements (jason.community.notice_catalog), or one with the governing documents' clauses."""
    from jason.community import community
    from jason.community.notice_catalog import REQUIREMENTS, effective, for_ledger, provisions

    found = community()
    if not key:
        for r in REQUIREMENTS:
            clock = "; ".join(t.describe() for t in r.timing) or (f"with {r.carried_by}" if r.carried_by else "")
            kind = r.kind.value if r.kind else ", ".join(m.name.lower() for m in r.methods) or "no delivery"
            print(f"  {r.key:32} {r.statute:10} {kind:28} {clock}" + ("" if r.verified else "  [unverified]"))
        own = [p for p in provisions(found) if not p.requirement]
        if own:
            print("\nThe governing documents' own notices:")
            for p in own:
                print(f"  {p.key:32} {p.citation:28} {p.title}")
        return 0
    row = for_ledger(key)
    if row is None:
        own = next((p for p in provisions(found) if p.key == key), None)
        if own is None:
            print(f"no notice requirement or provision {key}: jason notices --catalog lists them", file=sys.stderr)
            return 2
        print(f"{own.title or own.key} [{own.citation}; {own.comparison.value}]: {own.says}")
        for t in own.timing:
            print(f"  clock: {t.describe()}")
        if own.lead:
            print(f"  lead: {own.lead}")
        return 0
    r, clocks, notes, touching = effective(row.key, found)
    print(f"{r.title} [{r.key}; {r.statute}" + (f"; also {', '.join(r.also)}" if r.also else "") + "]")
    print(f"  to: {r.recipients.value}; " + (r.kind.value if r.kind else "") +
          (f" by {', or '.join(m.value for m in r.methods)}" if r.methods else ""))
    if r.individual_on_request:
        print("  by individual delivery to a member who asked (4045(b))")
    if r.secondary_copies:
        print("  a copy to each secondary address on file (4040(b))")
    if r.carried_by:
        print(f"  carried by: {r.carried_by}")
    for t in clocks:
        print(f"  clock: {t.describe()}")
    for c in r.content:
        print(f"  content: {c}")
    for e in r.proof():
        print(f"  proof: {e.value}")
    for p in touching:
        print(f"  {p.citation} ({p.comparison.value}): {p.says}")
    for n in notes:
        print(f"  note: {n}")
    for n in (r.note, r.caveat and f"for counsel: {r.caveat}"):
        if n:
            print(f"  {n}")
    return 0


def _proof(args: argparse.Namespace, data_dir: Path) -> int:
    """One notice's proof-of-notice record, from its ledger and the dates a person gives."""
    from jason.community import community
    from jason.community.notice_catalog import effective, for_ledger, requirement
    from jason.community.notices import Evidence
    from jason.tasks import notice_ledger, notice_proof

    try:
        row = requirement(args.requirement) if args.requirement else for_ledger(args.key)
    except KeyError:
        row = None
    if row is None:
        print(f"which requirement is {args.key}? give --requirement KEY (jason notices --catalog lists them)",
              file=sys.stderr)
        return 2
    _, clocks, notes, _ = effective(row.key, community())
    have = [Evidence[h.strip().upper().replace("-", "_")] for h in (args.have or "").split(",") if h.strip()]
    found = notice_ledger.standing(notice_ledger.load(data_dir, args.key), general=args.general)
    proof = notice_proof.build(row, clocks=clocks, event=_day(args.event), sent=_day(args.sent), posted=_day(args.posted),
                               standings=found, general=args.general, have=have, ledger_key=args.key, notes=notes)
    print("\n".join(notice_proof.lines(proof)))
    return 0


def cmd_notices(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.tasks import notice_ledger

    if args.catalog:
        return _catalog(args.key)
    data_dir = _data_dir(args)
    if args.proof and args.key:
        return _proof(args, data_dir)
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
    p.add_argument("--catalog", action="store_true",
                   help="the notice requirements the law sets (no KEY: all of them; KEY: one, with the governing "
                        "documents' clauses and the stricter clock). Reads no PayHOA")
    p.add_argument("--proof", action="store_true",
                   help="the proof-of-notice record for KEY: the evidence its requirement calls for, the window, and "
                        "who was reached late, from the ledger (sync first)")
    p.add_argument("--requirement", help="with --proof: the catalog key, when KEY does not start with one")
    p.add_argument("--event", help="with --proof: the day of the meeting, hearing, due date, or other anchor")
    p.add_argument("--sent", help="with --proof: the day it was mailed or sent (default: the ledger's first attempt)")
    p.add_argument("--posted", help="with --proof --general: the day it was posted")
    p.add_argument("--have", help="with --proof: evidence on file, comma-separated (text_as_sent,mailing_declaration)")
    p.set_defaults(func=lambda a: cmd_notices(a, agent_factory))
