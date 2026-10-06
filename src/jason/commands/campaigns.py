"""``jason campaigns``: the handler is chosen when a form is made (docs/arrivals-design.md, build step 1a).

A campaign is one form, one cycle, one channel (``NP27E``). A person opens it before any copy is made and chooses what
processes the answers; the record (``data/forms/campaigns.json``) keeps the form's library version, its authority, the
handler and its options, the procedure, the cycle, and who chose it. A reference exists only if a handler does:
``jason forms``, ``jason owner-info`` and the other commands that make a copy refuse a form with no open campaign.

Disk only: nothing here calls PayHOA, Google, or Gmail, and no option makes a copy or sends anything.

- No option: the campaigns (code, form, version, handler, cycle, copies sent, answers returned and recorded, status).
  A campaign the profile's response requests already run, whose row is not written yet, is listed as such.
- ``--show CODE``: one campaign.
- ``--open FORM --channel C --cycle-year Y --by NAME [--handler KEY] [--option NAME=VALUE ...] [--return-by DATE]``: a
  person's act. It writes the campaign's row and nothing else. A form with an authority takes its process handler; a form
  with none needs ``--handler`` from the general handlers.
- ``--close CODE --by NAME``: close a campaign (a person's act).
- ``--adopt``: write the rows the profile's running requests call for (the cycle that began before this record).
- ``--json``: print JSON.

A refusal prints ``jason: <reason>`` and exits 2.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Any, Callable

ACTIONS = ("show", "open", "close", "adopt")
# An option and the actions it goes with (None: the listing). A stray one is refused rather than ignored.
MODIFIERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("channel", "--channel", ("open",)), ("cycle_year", "--cycle-year", ("open",)), ("handler", "--handler", ("open",)),
    ("option", "--option", ("open",)), ("return_by", "--return-by", ("open",)), ("by", "--by", ("open", "close")))


def _refuse(reason: str) -> int:
    print(f"jason: {reason}", file=sys.stderr)
    return 2


def _print_json(body: Any) -> None:
    from jason.commands._shared import to_json

    print(to_json(body))


def _action(args: argparse.Namespace) -> str | None:
    return next((name for name in ACTIONS if getattr(args, name, None)), None)


def _row(c: Any, counts: dict[str, Any]) -> dict[str, Any]:
    return {**c.to_json(), "written": c.stored, **counts}


def _number(value: Any) -> str:
    return "-" if value is None else str(value)


def _lines(rows: list[dict[str, Any]]) -> list[str]:
    out = [f"Campaigns: {len(rows)}. Disk only: nothing was asked of PayHOA, Google, or Gmail."]
    if not rows:
        out.append("  none: a person opens one before a copy of a form is made "
                   "(jason campaigns --open FORM --channel C --cycle-year Y --by NAME).")
    for r in rows:
        due = f", return by {r['cycle']['returnBy']}" if r["cycle"]["returnBy"] else ""
        out.append(f"  {r['code']:7} {r['form']:18} v{r['version'] or '?':4} {r['handler'] or 'none':20} {r['year']} {r['channel']:7}"
                   f" sent {r['copies']}" + (f" + {r['mailings']} mailing(s)" if r["mailings"] else "")
                   + f"  returned {_number(r['returned'])}  recorded {_number(r['recorded'])}  {r['status']}{due}")
        if not r["written"]:
            out.append(f"          (not written yet: the profile's request already runs it; `jason campaigns --adopt`, or "
                       "the next send, writes the row)")
    if any(not r["written"] for r in rows):
        out.append("A row not written is read from the profile; an arrival with its reference is still recognized.")
    return out


def _show_lines(r: dict[str, Any]) -> list[str]:
    cycle = r["cycle"]
    out = [f"{r['code']}: {r['form']} v{r['version'] or '?'}" + (f", the law as of {r['asOf']}" if r["asOf"] else "")
           + f", by {r['channel']}, {r['year']}; {r['status']}",
           f"  authority: {', '.join(r['authority']) or 'none (a general form)'}",
           f"  handler: {r['handler'] or 'none'}" + (f" {r['options']}" if r["options"] else "")
           + (f"; procedure {r['procedure']} (jason sop {r['procedure']})" if r["procedure"] else "; procedure none"),
           f"  cycle: opened {cycle['opened'] or 'no date'}, return by {cycle['returnBy'] or 'no date'}",
           f"  chosen by {r['by'] or 'no one recorded'} at {r['chosenAt'] or 'no time recorded'}"
           + ("; adopted from the profile's request, not chosen in this record" if r["adopted"] else "")]
    if r["closedBy"]:
        out.append(f"  closed by {r['closedBy']} at {r['closedAt']}")
    out.append(f"  copies sent {r['copies']}" + (f", mailings {r['mailings']}" if r["mailings"] else "")
               + f"; returned {_number(r['returned'])}, recorded {_number(r['recorded'])}"
               + (f" (request {r['request']})" if r["request"] else "; no request watches this campaign"))
    if not r["written"]:
        out.append("  not written yet: `jason campaigns --adopt` writes the row")
    return out


def _gather(data_dir: Any, community: Any) -> list[dict[str, Any]]:
    from jason.tasks import campaigns

    held = campaigns.view(data_dir, community)
    stats = campaigns.counts(data_dir, community, held)
    return [_row(c, stats[c.code]) for c in sorted(held.values(), key=lambda c: (-c.year, c.code))]


def _open(args: argparse.Namespace, community: Any, data_dir: Any) -> int:
    from jason.community.forms import AnswerCycle
    from jason.tasks import campaigns

    if not args.channel:
        return _refuse("--channel is required with --open (email, mail, or payhoa)")
    if not args.cycle_year:
        return _refuse("--cycle-year is required with --open: the year the cycle is for")
    options: dict[str, str] = {}
    for item in args.option or ():
        name, sep, value = item.partition("=")
        if not sep or not name.strip():
            return _refuse(f"--option takes NAME=VALUE, not {item!r}")
        options[name.strip()] = value
    try:
        due = date.fromisoformat(args.return_by) if args.return_by else None
    except ValueError:
        return _refuse(f"--return-by is a day, YYYY-MM-DD, not {args.return_by!r}")
    cycle = AnswerCycle(year=int(args.cycle_year), opened=date.today(), return_by=due)
    row = campaigns.open_campaign(community, args.open, channel=args.channel, cycle=cycle, by=args.by or "",
                                  data_dir=data_dir, handler=args.handler, options=options)
    if args.json:
        _print_json(row.to_json())
        return 0
    print(f"opened {row.code}: {row.form} v{row.version}, handler {row.handler}, procedure {row.procedure}, by {row.by}. "
          "No copy was made: the generators now accept this form for this cycle and channel.")
    return 0


def cmd_campaigns(args: argparse.Namespace) -> int:
    from jason.commands._shared import data_dir as data_of
    from jason.community import community as active
    from jason.tasks import campaigns

    action = _action(args)
    for dest, flag, goes in MODIFIERS:
        if getattr(args, dest, None) and action not in goes:
            return _refuse(f"{flag} does not go with " + (f"--{action}" if action else "the listing; it goes with --open"))
    data_dir, community = data_of(args), active()
    try:
        if action == "open":
            return _open(args, community, data_dir)
        if action == "close":
            row = campaigns.close_campaign(data_dir, args.close, by=args.by or "")
            if args.json:
                _print_json(row.to_json())
            else:
                print(f"closed {row.code} by {row.closed_by}: no further copy is made for it.")
            return 0
        if action == "adopt":
            added = campaigns.adopt_existing(community, data_dir)
            skipped = campaigns.plan_adoption(community, data_dir)[1]
            if args.json:
                _print_json({"adopted": [c.to_json() for c in added], "skipped": skipped})
                return 0
            print(f"adopted {len(added)} campaign(s) from the profile's response requests"
                  + (": " + ", ".join(c.code for c in added) if added else "") + ".")
            for line in skipped:
                print(f"  not adopted, {line}")
            return 0
        rows = _gather(data_dir, community)
        if action == "show":
            found = next((r for r in rows if r["code"] == args.show.strip().upper()), None)
            if found is None:
                return _refuse(f"there is no campaign {args.show!r} (jason campaigns lists them)")
            if args.json:
                _print_json(found)
            else:
                print("\n".join(_show_lines(found)))
            return 0
        if args.json:
            _print_json({"campaigns": rows})
        else:
            print("\n".join(_lines(rows)))
        return 0
    except campaigns.CampaignRefusal as exc:
        return _refuse(exc.reason)


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("campaigns", help="The handler is chosen when a form is made: the campaigns (a form, a cycle, a channel), "
                                         "their handlers, and what each has sent and received; open or close one (a person's act)")
    add_common(p)
    act = p.add_mutually_exclusive_group()
    act.add_argument("--show", metavar="CODE", help="one campaign: its form and version, authority, handler, procedure, cycle, and counts")
    act.add_argument("--open", metavar="FORM", help="open a campaign for a form (needs --channel, --cycle-year, and --by); "
                                                    "writes the row only and makes no copy")
    act.add_argument("--close", metavar="CODE", help="close a campaign (needs --by)")
    act.add_argument("--adopt", action="store_true",
                     help="write the rows for the campaigns the profile's response requests already run")
    p.add_argument("--channel", metavar="C", help="with --open: email, mail, or payhoa (the marker's E, M, or P)")
    p.add_argument("--cycle-year", type=int, metavar="Y", help="with --open: the year the cycle is for")
    p.add_argument("--return-by", metavar="DATE", help="with --open: the day answers are asked by (YYYY-MM-DD)")
    p.add_argument("--handler", metavar="KEY", help="with --open: a general handler, for a form with no authority (a form with "
                                                    "an authority takes the one its authority names)")
    p.add_argument("--option", action="append", metavar="NAME=VALUE", help="with --open: a handler option (repeatable)")
    p.add_argument("--by", metavar="NAME", help="with --open or --close: who does it, for the record")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_campaigns)
