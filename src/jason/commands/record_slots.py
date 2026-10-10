"""``jason records``: the association's record checklist, one slot for each record it must be able to put its hands on, and
what a person picked or answered for each (docs/record-intake.md).

``jason records`` (or ``--list``) prints the slots by group with their states; ``--group G`` and ``--state S`` narrow it,
``--json`` prints what the console shows. ``--slot KEY`` shows one slot: the law that requires it, what is held, what the
library read, the candidates, and the trail. ``--pins`` lists what the specification itself pins.

The writes are a person's and each is a **dry run** until ``--yes``:

- ``--pick KEY --file LINK_OR_ID --by NAME`` names a Drive file (a pasted link, or its id) or a library file
  (``library:ID``) for the slot. It copies, moves, shares, and renames nothing. ``--period`` places it in a series,
  ``--entry NUMBER`` names the instrument on a recorded-instruments slot (that pick is a key-documents link), and
  ``--resolve`` reads the file's name in Drive first (read-only; a person's sign-in is never opened unless ``--interactive``).
- ``--answer KEY --not-applicable|--none|--waiting --reason TEXT --by NAME`` records a person's word that the slot has
  no record to pick; ``--who`` says who has it. It hides nothing.
- ``--unpin KEY --by NAME`` marks a person's pin removed (``--pin ID`` when the slot has several). The file stays.

Reads disk only, except ``--pick --resolve``.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable


def _community() -> Any:
    from jason.community import community

    return community()


def cmd_records(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.commands._shared import data_dir, to_json
    from jason.tasks import record_slots as rs

    root = data_dir(args)
    community = _community()
    acts = [x for x in (args.pick, args.answer, args.unpin) if x]
    if len(acts) > 1:
        print("one act at a time: --pick, --answer, or --unpin", file=sys.stderr)
        return 2
    dry = not args.yes
    try:
        if args.pick:
            if not args.file:
                print("--pick KEY needs --file LINK_OR_ID (a Drive link or id, or library:ID)", file=sys.stderr)
                return 2
            drive = None
            if args.resolve:
                with agent_factory(args) as agent:
                    drive = agent.drive(interactive=bool(getattr(args, "interactive", False)))
                    out = rs.pick(args.pick, args.file, by=args.by or "", period=args.period or "", note=args.note or "",
                                  entry=args.entry or "", drive=drive, dry_run=dry, community=community, root=root)
            else:
                out = rs.pick(args.pick, args.file, by=args.by or "", period=args.period or "", note=args.note or "",
                              entry=args.entry or "", dry_run=dry, community=community, root=root)
            return _report(out, args, to_json)
        if args.answer:
            chosen = [k for k, on in (("notApplicable", args.not_applicable), ("none", args.none_exists), ("waiting", args.waiting)) if on]
            if len(chosen) != 1:
                print("--answer KEY needs exactly one of --not-applicable, --none, --waiting", file=sys.stderr)
                return 2
            out = rs.answer(args.answer, chosen[0], by=args.by or "", reason=args.reason or "", who=args.who or "", dry_run=dry,
                            community=community, root=root)
            return _report(out, args, to_json)
        if args.unpin:
            out = rs.unpin(args.unpin, by=args.by or "", pin=args.pin or "", note=args.note or "", dry_run=dry,
                           community=community, root=root)
            return _report(out, args, to_json)
        if args.pins:
            data = rs.pins_listing(community, root)
            if args.json:
                print(to_json(data))
                return 0
            for row in data["pins"]:
                print(row["slot"])
                for p in row["pins"]:
                    print(f"    {p['kind']:8} {p['name']}  ({p['source']})")
            return 0
        if args.slot:
            data = rs.slot_view(args.slot, community, root, private=True)
            if not data.get("found"):
                print(f"no slot {args.slot}; jason records lists them", file=sys.stderr)
                return 1
            if args.json:
                print(to_json(data))
                return 0
            _print_slot(data)
            return 0
    except KeyError as exc:
        print(f"no slot {exc.args[0] if exc.args else ''}; jason records lists them", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    data = rs.view(community, root, group=args.group or "", state=args.state or "", private=True)
    if args.json:
        print(to_json(data))
        return 0
    c = data["counts"]
    print(f"Record checklist ({data['profile']}): {c['total']} slots; "
          + ", ".join(f"{k} {v}" for k, v in c["byState"].items() if v) + (f"; {c['held']} held back" if c["held"] else ""))
    for group in data["groups"]:
        print(f"\n{group['title']}" + (f"  [{group['law']}]" if group["law"] else ""))
        for s in group["slots"]:
            extra = f"  {s['pins']} pinned" if s["pins"] else ""
            extra += "  TWO HOLDERS" if s["collision"] else ""
            extra += f"  ({s['problem']})" if s["problem"] else ""
            print(f"  {s['stateWord']:24} {s['key']}  {s['title']}{extra}")
    for note in data["notes"]:
        print(f"note: {note}")
    for caveat in data["caveats"]:
        print(f"> {caveat}")
    return 0


def _report(out: dict[str, Any], args: argparse.Namespace, to_json: Callable[[Any], str]) -> int:
    if args.json:
        print(to_json(out))
        return 0
    if out.get("dryRun"):
        would = out["would"]
        print("dry run: would write " + ", ".join(f"{k}={v}" for k, v in would.items() if v))
        print(out["note"])
        return 0
    print(f"wrote {out['written']}: {out.get('pin') or out.get('answer')} for {out['slot']}" + (" (already pinned)" if out.get("already") else ""))
    return 0


def _print_slot(d: dict[str, Any]) -> None:
    print(f"{d['key']}: {d['title']}")
    print(f"  state: {d['stateWord']}   {d['cardinality']}   group {d['group']}" + (f"   hidden by the profile: {d['hidden']}" if d["hidden"] else ""))
    print("  requires: " + (", ".join(d["requires"]) if d["requires"] else "jason's own design needs it" + (f" ({d['why']})" if d["why"] else "")))
    ans = d["existence"]["answer"]
    if ans:
        print(f"  answered: {ans['word']} by {ans['by']} on {ans['at']}: {ans['reason']}" + (f" (who: {ans['who']})" if ans["who"] else ""))
    for h in d["holders"]:
        print(f"  {h['origin']:5} {h['stateWord']:11} {h['kind']:8} {h['name']}  [{h['pin']}]" + (f" by {h['by']} {h['at']}" if h["by"] else ""))
        if h["problem"]:
            print(f"        problem: {h['problem']}")
        if h["wrongSlot"] and h["wrongSlot"]["fits"]:
            print("        it fits: " + ", ".join(f["key"] for f in h["wrongSlot"]["fits"]))
    for f in d["specificationFolders"]:
        print(f"  folder pinned by the specification: {f['folder']}")
    for c in d["collisions"]:
        print(f"  TWO HOLDERS: {c['note']}")
    if d["candidates"]:
        print(f"  {d['candidates'] and len(d['candidates'])} candidates in the library (not pinned), e.g. {d['candidates'][0]['ref']}")
    for row in d["log"]:
        print(f"  {row.get('at', '')[:10]} {row.get('by', '')}: {row.get('act', '')}")
    print(f"  {d['commands']['pick']}")


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("records", help="The record checklist: a slot for each record the association must hold, with what a person picked or answered")
    add_common(p)
    p.add_argument("--list", action="store_true", help="list the slots by group with their states (the default)")
    p.add_argument("--group", metavar="G", help="with the list: one group (governing, recorded, finance, ...)")
    p.add_argument("--state", metavar="S", help="with the list: one state (empty, picked, classified, read, problem, ...)")
    p.add_argument("--json", action="store_true", help="print JSON, as the console reads it")
    p.add_argument("--slot", metavar="KEY", help="show one slot: its law, holders, library reading, candidates, and trail")
    p.add_argument("--pins", action="store_true", help="list what the specification itself pins for each slot")
    p.add_argument("--pick", metavar="KEY", help="name a file for this slot (with --file and --by); a dry run without --yes")
    p.add_argument("--file", metavar="LINK_OR_ID", help="a Drive link or file id, or library:ID, for --pick")
    p.add_argument("--period", metavar="P", help="with --pick on a series slot: the year (2099), month (2099-06), or quarter (2099-Q2)")
    p.add_argument("--entry", metavar="NUMBER", help="with --pick on a recorded-instruments slot: the instrument's recording number")
    p.add_argument("--resolve", action="store_true", help="with --pick: read the file's name in Drive first (read-only)")
    p.add_argument("--answer", metavar="KEY", help="record a person's word on this slot (with one of the three flags, --reason, --by)")
    p.add_argument("--not-applicable", action="store_true", help="with --answer: it does not apply to this association")
    p.add_argument("--none", dest="none_exists", action="store_true", help="with --answer: the association holds none (say where you looked)")
    p.add_argument("--waiting", action="store_true", help="with --answer: someone else has it (say who with --who)")
    p.add_argument("--reason", metavar="TEXT", help="with --answer: why, or where you looked")
    p.add_argument("--who", metavar="NAME", help="with --answer --waiting: who has it")
    p.add_argument("--unpin", metavar="KEY", help="mark a person's pin on this slot removed (the file stays)")
    p.add_argument("--pin", metavar="ID", help="with --unpin: which pin, when the slot has several")
    p.add_argument("--note", metavar="TEXT", help="a few words kept with a pick or an unpin")
    p.add_argument("--by", metavar="NAME", help="the person making the write (required for every write)")
    p.add_argument("--yes", action="store_true", help="make the write; without it every write is a dry run")
    p.set_defaults(func=lambda args: cmd_records(args, agent_factory))
