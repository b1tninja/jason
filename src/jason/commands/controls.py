"""``jason controls``: the safeguards a board opts into, and the ones jason suggests (docs/controls.md).

- ``--list [--family F] [--state S] [--json]``: every control, by family, with its state in words; read.
- ``--show KEY [--json]``: one control from the provision to its history: the provision whole, the floor, jason's reading
  (labeled as jason's), what it changes, the roster check, and the history; read.
- ``--roster-check KEY``: what the control needs, what is seated, and what is missing, by office and count (no names); read.
- ``--suggest [--document KEY ...] [--duties-read] [--record --by NAME] [--json]``: read the governing documents' sections
  as stored and print the controls they suggest, each with the provision's words whole, the floor (read only where one count
  is certain), jason's proposal and its reading; a weak match is a question, not a suggestion. It runs only once the duties
  are read (``Community.duties_read()``, or ``--duties-read`` from a person who has read and confirmed them). ``--record
  --by NAME`` appends the suggestions to the act log as suggested acts by jason; it adopts nothing.
- ``--propose KEY --by NAME``: put a suggested control before the board: a board item with the provision as its evidence, and
  the control becomes proposed. That is all a person may do with a suggestion here.

This command never adopts, declines, defers, or retires a control. Those are the board's decisions, recorded by the secretary
at a meeting (``jason.controls.store.record`` with the decision id); a control is in force only from the effective date the
board names, and only when the roster can satisfy it. A write needs ``--by``.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Any, Callable

WRITES = ("propose",)
ACTS = ("list", "show", "roster_check", "suggest", "propose")


def _refuse(reason: str) -> int:
    print(f"jason controls: {reason}", file=sys.stderr)
    return 2


def _print_json(body: Any) -> None:
    from jason.commands._shared import to_json

    print(to_json(body))


def _day(args: argparse.Namespace) -> date | None:
    from jason.commands._shared import day

    return day(getattr(args, "as_of", None))


def cmd_controls(args: argparse.Namespace) -> int:
    from jason.commands._shared import data_dir
    from jason.community import community
    from jason.controls.types import ControlRefused

    chosen = [a for a in ACTS if getattr(args, a, None)]
    if len(chosen) > 1:
        return _refuse("one act at a time")
    act = chosen[0] if chosen else "list"
    if act in WRITES and not (args.by or "").strip():
        return _refuse(f"--{act.replace('_', '-')} names the person who asks for it: add --by NAME")
    if getattr(args, "record", False) and act != "suggest":
        return _refuse("--record goes with --suggest")
    root = data_dir(args)
    try:
        home = community()
        if act == "list":
            return _list(args, home, root)
        if act == "show":
            return _show(args, home, root)
        if act == "roster_check":
            return _roster(args, home, root)
        if act == "suggest":
            return _suggest(args, home, root)
        return _propose(args, home, root)
    except KeyError as exc:
        return _refuse(f"no control {exc.args[0] if exc.args else ''}".strip())
    except (ControlRefused, ValueError) as exc:
        return _refuse(str(exc))


# --- reads ---------------------------------------------------------------------------------------------------------------

def _list(args: argparse.Namespace, home: Any, root: Any) -> int:
    from jason.controls import view

    body = view.compose(home, root, family=args.family or "", state=args.state or "", today=_day(args))
    if args.json:
        _print_json(body)
        return 0
    print(f"{view.LABEL}. {body['counts']['total']} control(s): {body['heading']}.")
    if body["empty"]:
        print(body["empty"])
    for g in body["families"]:
        print(f"\n{g['title'].upper()}")
        for r in g["controls"]:
            cite = r["basis"]["citation"] or "no provision cited"
            print(f"  {r['key']}: {r['title']} [{r['stateWord']}] ({cite})")
            print(f"      {r['summary']}")
        for q in g["questions"]:
            print(f"  QUESTION {q['citation']}: {q['title']} (not a suggestion; {q['whyQuestion']})")
    return 0


def _show(args: argparse.Namespace, home: Any, root: Any) -> int:
    from jason.controls import view

    body = view.one(home, root, args.show, today=_day(args))
    if args.json:
        _print_json(body)
        return 0 if body["found"] else 2
    if not body["found"]:
        return _refuse(body["note"])
    c = body["control"]
    print(f"{c['title']} ({c['key']}): {c['stateWord']}")
    print(f"\n1 THE PROVISION: {c['basis']['citation'] or 'none cited'}")
    print(f'  "{c["basis"]["words"]}"' if c["basis"]["words"] else "  (cited, not quoted)")
    print("  " + (c["floor"]["note"] or f"The floor the provision sets: {c['floor']['provision']}"))
    if c["floor"]["catalog"]:
        print(f"  The catalog's floor: {c['floor']['catalog']}")
    if c["changed"]:
        print(f"  CHANGED since the control was recorded: now reads \"{c['changed']['now']}\"")
    if c["reading"]:
        print(f"\n2 WHAT JASON SUGGESTED\n  {c['reading']}")
    if c["decision"] or c["state"] in ("adopted", "declined", "deferred", "retired"):
        print(f"\n3 WHAT THE BOARD DECIDED\n  {c['summary']}; decision {(c['decision'] or {}).get('id', 'not named')}"
              + (f"; effective {c['effective']}" if c["effective"] else ""))
    print("\n4 WHAT IT CHANGES")
    for t in c["touches"]:
        print("  " + _touch(t))
    print(f"\n5 CAN THE ROSTER SATISFY IT\n  {_roster_line(c['roster'])}")
    print("\n6 HISTORY")
    for h in c["history"]:
        print(f"  {h['at'][:10]} {h['act']} by {h['by']}: {h['why']}" + (f" (decision {h['decision']})" if h.get("decision") else ""))
    return 0


def _touch(t: dict[str, Any]) -> str:
    if t.get("key"):
        return (f"{t['kind']} {t['key']}: the kind's own rule is {t['builtin']}; the control asks {t['with']}"
                + ("" if t["changes"] else " (unchanged)"))
    return f"{t['kind']} {t.get('what', '')}" + (f": {t['note']}" if t.get("note") else "")


def _roster_line(r: dict[str, Any]) -> str:
    if not r["read"]:
        return "the roster could not be read, so the check was not made"
    needs = "; ".join(f"{n['count']} {n['office']}" for n in r["needs"]) or "nothing named"
    seated = ", ".join(f"{s['count']} {s['office']}" for s in r["seated"]) or "no one"
    return f"needs {needs}. Seated: {seated}." + (f" Missing: {r['lacks']}." if r["lacks"] else " The roster can satisfy it.")


def _roster(args: argparse.Namespace, home: Any, root: Any) -> int:
    from jason.controls import view

    body = view.one(home, root, args.roster_check, today=_day(args))
    if not body["found"]:
        return _refuse(body["note"])
    check = body["control"]["roster"]
    if args.json:
        _print_json(check)
    else:
        print(_roster_line(check))
    return 0


# --- the reader ------------------------------------------------------------------------------------------------------------

def _suggest(args: argparse.Namespace, home: Any, root: Any) -> int:
    from jason.controls import suggest as reader

    confirmed = bool(getattr(args, "duties_read", False) or home.duties_read())
    documents = reader.ShelfDocuments(home, root, args.document or ())
    found = reader.suggest(home, documents, duties_read=confirmed, data_dir=root)
    recorded = None
    if args.record and not found.reason:
        if not (args.by or "").strip():
            return _refuse("--record names the person who asks for it: add --by NAME")
        recorded = reader.record(found, by=args.by, data_dir=root, community=home)
    if args.json:
        _print_json({"reason": found.reason, "known": found.known, "unread": found.unread, "ready": confirmed,
                     "suggestions": [s.as_dict() for s in found.suggested], "questions": [s.as_dict() for s in found.questions],
                     "recorded": list(recorded.recorded) if recorded else None})
        return 0
    if found.reason:
        print(f"jason suggests nothing: {found.reason}. Confirm them, then run this again (--duties-read, from a person "
              "who has read them).")
        return 0
    print(f"{len(found.suggested)} suggestion(s), {len(found.questions)} question(s) for the board or counsel"
          + (f"; {found.known} section(s) already have a control recorded from the same words" if found.known else "")
          + ". jason suggests; the board adopts. Nothing here is adopted.")
    for s in found.suggested:
        print(f"\nSUGGESTION {s.key or '(new)'}: {s.type.title} <- {s.basis.citation}"
              + (" [the provision's words changed since the control was recorded; the control stays as the board left it]"
                 if s.changed else ""))
        print(f'  The provision, whole: "{s.basis.words}"')
        print(f"  {s.floor_note}")
        print(f"  {s.reading}")
    for s in found.questions:
        print(f"\nQUESTION (not a suggestion): {s.type.title} <- {s.basis.citation}")
        print(f'  The provision, whole: "{s.basis.words}"')
        print(f"  {s.reading}")
    for line in found.unread:
        print(f"  not read: {line}")
    if recorded:
        print(f"\nRecorded {len(recorded.recorded)} suggested act(s) by jason at the request of {args.by}"
              + (f"; skipped {len(recorded.skipped)}" if recorded.skipped else "")
              + f"; kept {recorded.questions} question(s) and {recorded.changed} changed provision(s) for the screen.")
    else:
        print("\n--record --by NAME appends these to the act log as suggested acts. jason adopts nothing.")
    return 0


# --- the one write -----------------------------------------------------------------------------------------------------------

def _propose(args: argparse.Namespace, home: Any, root: Any) -> int:
    from jason.controls.propose import propose

    out = propose(args.propose, by=args.by, data_dir=root, community=home)
    if args.json:
        _print_json(out)
        return 0
    print(f"{'Refreshed' if out['refreshed'] else 'Proposed'} {out['key']}: board item {out['item']}, "
          f"{out['board']['added']} added, {out['board']['updated']} refreshed; the control is {out['state']}, by {out['by']}. "
          "It is not adopted: the board decides at a meeting, and the secretary records the decision.")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    from jason.controls.view import FAMILIES, STATES

    summary = ("The safeguards the board opts into, and the ones jason suggests from the governing documents: list, show, "
               "suggest (and record), and put one before the board. jason suggests; the board adopts. This never adopts, "
               "declines, defers, or retires a control: those are the board's decisions, recorded by the secretary")
    p = sub.add_parser("controls", help=summary, description=summary)
    add_common(p)
    p.add_argument("--list", action="store_true", help="list the controls (the default)")
    p.add_argument("--family", choices=FAMILIES, help="with --list: one family")
    p.add_argument("--state", choices=STATES, help="with --list: one state")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--show", metavar="KEY", help="one control, from its provision to its history")
    p.add_argument("--roster-check", dest="roster_check", metavar="KEY",
                   help="what the control needs, what is seated, and what is missing, by office")
    p.add_argument("--suggest", action="store_true",
                   help="read the governing documents and print the controls they suggest (after the duties are read)")
    p.add_argument("--document", action="append", metavar="KEY", help="with --suggest: read only this document (repeatable)")
    p.add_argument("--duties-read", dest="duties_read", action="store_true",
                   help="with --suggest: a person confirms the documents' duties were read and are right")
    p.add_argument("--record", action="store_true",
                   help="with --suggest and --by: append the suggestions to the act log as suggested acts by jason")
    p.add_argument("--propose", metavar="KEY",
                   help="put a suggested control before the board as a board item (with --by); it adopts nothing")
    p.add_argument("--by", default="", metavar="NAME", help="who asks for the write (kept with when)")
    p.add_argument("--as-of", dest="as_of", metavar="DATE", help="read as of this day (YYYY-MM-DD); default today")
    p.set_defaults(func=cmd_controls)


__all__ = ["cmd_controls", "register"]
