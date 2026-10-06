"""``jason followups``: what we do next, and when (docs/followups-design.md).

Dated actions for a person, in date order, each with its basis (law, the documents, a proposed policy, or a person's own),
the count still outstanding, the command that does it, and the age of what it was read from. jason computes and shows them;
it sends nothing, resends nothing, and completes nothing. Disk only: nothing here calls PayHOA, Google, or Gmail. Names and
units only: an address, an email, or an answer is never printed.

- No option: what is overdue, due today, and due in the next 14 days, grouped. ``--within DAYS`` changes the 14, ``--overdue``
  shows only the overdue, ``--all`` every item in every state and date (done, deferred, and dropped too), ``--campaign CODE``
  and ``--kind K`` narrow, ``--json`` prints JSON.
- ``--done ID --by NAME [--note TEXT]``: a person says it was done.
- ``--defer ID --to DATE --by NAME --why TEXT``: a person puts it off to a later day, with the reason.
- ``--drop ID --by NAME --why TEXT``: a person says it is not to be done, with the reason.
- ``--add --date DATE --text TEXT --by NAME [--campaign CODE]``: a person's own item.

Each act is kept in ``data/followups/acts.jsonl`` (who, when, what, why) and survives the next run. A refusal prints
``jason followups: <reason>`` on stderr and exits 2.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Any, Callable

ACTIONS = ("done", "defer", "drop", "add")
# An option and the actions it goes with (None: the listing). A stray one is refused rather than ignored.
MODIFIERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("campaign", "--campaign", ("list", "add")), ("kind", "--kind", ("list",)), ("within", "--within", ("list",)),
    ("overdue", "--overdue", ("list",)), ("everything", "--all", ("list",)),
    ("to", "--to", ("defer",)), ("why", "--why", ("defer", "drop")), ("note", "--note", ("done",)),
    ("on", "--date", ("add",)), ("text", "--text", ("add",)),
    ("by", "--by", ("done", "defer", "drop", "add")))
NAMES_SHOWN = 6


def _refuse(reason: str) -> int:
    print(f"jason followups: {reason}", file=sys.stderr)
    return 2


def _community() -> Any:
    from jason.community import community

    return community()


def _today() -> date:
    return date.today()


def _mask(value: Any) -> Any:
    from jason.approvals.audit import mask

    return mask(value, addresses=False)


def _print_json(body: Any) -> None:
    from jason.commands._shared import to_json

    print(to_json(body))


def _action(args: argparse.Namespace) -> str:
    return next((name for name in ACTIONS if getattr(args, name, None)), "list")


def _age(hours: float | None) -> str:
    if hours is None:
        return "age not known"
    if hours < 1:
        return f"{round(hours * 60)}m ago"
    return f"{hours:.0f}h ago" if hours < 48 else f"{hours / 24:.0f}d ago"


def _stamp(value: str) -> str:
    return value[:16].replace("T", " ") if value else "never"


def _sources(known: dict[str, Any]) -> list[str]:
    out = []
    for name, label in (("campaign", "campaign record"), ("catalog", "sent-copy catalog"), ("inbox", "response inbox"),
                        ("ledger", "notice ledger"), ("person", "a person's own items")):
        row = known[name]
        if not row["exists"]:
            out.append(f"  {label}: not on disk ({row['reason']})")
        elif name == "ledger":
            out.append(f"  {label}: synced {_stamp(row['at'])} ({_age(row['ageHours'])})")
        elif name == "inbox":
            out.append(f"  {label}: written {_stamp(row['at'])} ({_age(row['ageHours'])}); "
                       + (f"last check that succeeded {_stamp(row['lastCheck'])} ({_age(row['lastCheckAgeHours'])})"
                          if row["lastCheck"] else "no check has succeeded, so an answer that arrived is not counted"))
        else:
            out.append(f"  {label}: written {_stamp(row['at'])} ({_age(row['ageHours'])})")
    return out


def _item_lines(i: Any, known: dict[str, Any]) -> list[str]:
    from jason.tasks.followups import source_age

    head = f"  {i.due.isoformat()}  {i.kind.value:14} {i.id}  {i.what}"
    if i.state.value in ("done", "dropped", "deferred"):
        head += f"  [{i.state.value}" + (f" to {i.deferred_to.isoformat()}" if i.deferred_to else "") + (f" by {i.by}" if i.by else "") + "]"
    out = [head, f"      basis: {i.basis.value}" + (f" ({i.cite})" if i.cite else "") + (f"; {i.due_note}" if i.due_note and i.due_note not in i.cite else "")]
    if i.window_end:
        out.append(f"      window: until {i.window_end.isoformat()}")
    if i.outstanding is not None:
        shown = ", ".join(i.names[:NAMES_SHOWN]) + (f", and {len(i.names) - NAMES_SHOWN} more" if len(i.names) > NAMES_SHOWN else "")
        out.append(f"      outstanding: {i.outstanding}" + (f": {shown}" if shown else ""))
    elif i.reason:
        out.append(f"      outstanding: not known ({i.reason})")
    if i.why:
        out.append(f"      {i.state.value if i.state.value != 'upcoming' else 'note'}: {i.why}")
    if i.command:
        out.append(f"      run: {i.command}")
    out.append(f"      source: {source_age(i, known)['says']} ({_age(source_age(i, known)['ageHours'])})")
    return [_mask(line) for line in out]


def _groups(shown: list[Any]) -> list[tuple[str, list[Any]]]:
    from jason.tasks.followups import FollowUpState as S

    rows = [("Overdue", [i for i in shown if i.state is S.OVERDUE]), ("Due today", [i for i in shown if i.state is S.DUE]),
            ("Coming up", [i for i in shown if i.state is S.UPCOMING]), ("Deferred", [i for i in shown if i.state is S.DEFERRED]),
            ("Done", [i for i in shown if i.state is S.DONE]), ("Dropped", [i for i in shown if i.state is S.DROPPED])]
    return [(name, rows_) for name, rows_ in rows if rows_]


def _list(args: argparse.Namespace, data_dir: Any) -> int:
    from jason.tasks import followups as fu

    today = _today()
    within = fu.NEXT_DAYS if args.within is None else int(args.within)
    if within < 0:
        return _refuse("--within is a number of days, 0 or more")
    found = fu.items(data_dir, _community(), today=today)
    shown = fu.select(found, today=today, within=within, campaign=args.campaign or "", kind=args.kind or "", overdue=args.overdue,
                      everything=args.everything)
    known = fu.ages(data_dir, _community(), today=today)
    counts = {"overdue": sum(1 for i in shown if i.state is fu.FollowUpState.OVERDUE),
              "dueToday": sum(1 for i in shown if i.state is fu.FollowUpState.DUE),
              "coming": sum(1 for i in shown if i.state is fu.FollowUpState.UPCOMING)}
    if args.json:
        _print_json({"asOf": today.isoformat(), "within": within, "counts": counts, "total": len(found),
                     "items": [{**i.to_json(), "sourceAge": fu.source_age(i, known)} for i in shown], "ages": known,
                     "note": "disk only; jason sends, resends, and completes nothing"})
        return 0
    print(f"Follow-ups as of {today.isoformat()}: {counts['overdue']} overdue, {counts['dueToday']} due today, {counts['coming']} "
          f"coming up (the next {within} days{'; --all: every date' if args.everything else ''}). Disk only: nothing was asked of PayHOA, "
          "Google, or Gmail, and jason sends, resends, and completes nothing.")
    print("Read from:")
    print("\n".join(_sources(known)))
    if not shown:
        print()
        print(f"Nothing matches as of {today.isoformat()} ({len(found)} follow-up(s) in all; `jason followups --all` lists them).")
        return 0
    for name, rows in _groups(shown):
        print()
        print(f"{name} ({len(rows)})")
        for i in rows:
            print("\n".join(_item_lines(i, known)))
    print()
    print("A person does each one and says so: --done ID --by NAME, --defer ID --to DATE --by NAME --why TEXT, --drop ID --by NAME "
          "--why TEXT. A number marked proposed is the board's to adopt.")
    return 0


def _act_done(args: argparse.Namespace, data_dir: Any) -> int:
    from jason.tasks import followups as fu

    item = fu.done(data_dir, _community(), args.done, by=args.by or "", note=args.note or "", today=_today())
    return _acted(args, item, f"Marked {item.id} done by {item.by}: {item.what}")


def _act_defer(args: argparse.Namespace, data_dir: Any) -> int:
    from jason.commands._shared import day
    from jason.tasks import followups as fu

    try:
        to = day(args.to)
    except ValueError:
        return _refuse("--to is a day, YYYY-MM-DD")
    if to is None:
        return _refuse("--to is required with --defer: the day it comes back")
    item = fu.defer(data_dir, _community(), args.defer, to=to, by=args.by or "", why=args.why or "", today=_today())
    return _acted(args, item, f"Deferred {item.id} to {to.isoformat()} by {item.by}: {item.why}")


def _act_drop(args: argparse.Namespace, data_dir: Any) -> int:
    from jason.tasks import followups as fu

    item = fu.drop(data_dir, _community(), args.drop, by=args.by or "", why=args.why or "", today=_today())
    return _acted(args, item, f"Dropped {item.id} by {item.by}: {item.why}")


def _act_add(args: argparse.Namespace, data_dir: Any) -> int:
    from jason.commands._shared import day
    from jason.tasks import followups as fu

    try:
        due = day(args.on)
    except ValueError:
        return _refuse("--date is a day, YYYY-MM-DD")
    if due is None:
        return _refuse("--date is required with --add: the day it is due")
    item = fu.add_manual(data_dir, due=due, text=args.text or "", by=args.by or "", campaign=args.campaign or "", today=_today())
    return _acted(args, item, f"Added {item.id}, due {item.due.isoformat()}, by {args.by.strip()}: {item.what}")


def _acted(args: argparse.Namespace, item: Any, line: str) -> int:
    if args.json:
        _print_json(item.to_json())
        return 0
    print(_mask(line))
    print("Kept in data/followups/acts.jsonl. jason did nothing else: it sends, resends, and completes nothing.")
    return 0


def cmd_followups(args: argparse.Namespace) -> int:
    from jason.commands._shared import data_dir as data_of
    from jason.tasks.followups import FollowUpError

    action = _action(args)
    for dest, flag, goes in MODIFIERS:
        value = getattr(args, dest, None)
        if value is not None and value is not False and value != "" and action not in goes:
            return _refuse(f"{flag} does not go with " + (f"--{action}" if action != "list" else "the listing; it goes with an act"))
    if args.everything and args.within is not None:
        return _refuse("--all shows every date: it does not go with --within")
    if args.overdue and args.everything:
        return _refuse("--overdue and --all do not go together")
    data_dir = data_of(args)
    try:
        if action == "done":
            return _act_done(args, data_dir)
        if action == "defer":
            return _act_defer(args, data_dir)
        if action == "drop":
            return _act_drop(args, data_dir)
        if action == "add":
            return _act_add(args, data_dir)
        return _list(args, data_dir)
    except FollowUpError as exc:
        return _refuse(exc.reason)


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("followups", help="What we do next, and when: dated actions (remind, enter, resend, review) with their "
                                         "basis, the count outstanding, and the command; done, defer, or drop one (a person's act)")
    add_common(p)
    act = p.add_mutually_exclusive_group()
    act.add_argument("--done", metavar="ID", help="a person says it was done (needs --by)")
    act.add_argument("--defer", metavar="ID", help="put it off to a later day (needs --to, --by, and --why)")
    act.add_argument("--drop", metavar="ID", help="it is not to be done (needs --by and --why)")
    act.add_argument("--add", action="store_true", help="a person's own item (needs --date, --text, and --by)")
    p.add_argument("--campaign", metavar="CODE", help="only this campaign's follow-ups; with --add, the campaign it belongs to")
    p.add_argument("--kind", metavar="K", help="only this kind (remind, return-by, enter-by, reports-mailed, resend, acknowledge, "
                                               "review, decide, answer-due, close, manual)")
    p.add_argument("--within", type=int, metavar="DAYS", help="how far ahead to list (default 14)")
    p.add_argument("--overdue", action="store_true", help="only what is overdue")
    p.add_argument("--all", dest="everything", action="store_true", help="every item, in every state and on every date")
    p.add_argument("--to", metavar="DATE", help="with --defer: the day it comes back (YYYY-MM-DD)")
    p.add_argument("--date", dest="on", metavar="DATE", help="with --add: the day it is due (YYYY-MM-DD)")
    p.add_argument("--text", metavar="TEXT", help="with --add: what is to be done")
    p.add_argument("--note", metavar="TEXT", help="with --done: what was done")
    p.add_argument("--why", metavar="TEXT", help="with --defer or --drop: the reason (required)")
    p.add_argument("--by", metavar="NAME", help="who does it, for the log (every act requires it)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=lambda a: cmd_followups(a))
