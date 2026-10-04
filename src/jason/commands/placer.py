"""``jason placer-history PARCEL``: one Placer parcel's recorded history, and its document processes as DAGs.

``jason placer-history "687 Example Ln"`` (an address, a twelve-digit APN, or a document number) walks the parcel's
deeds back through the county recorder's public index (read only, through the cache) and writes, under
``data/reports/placer/<apn>/``, the parcel page ``<apn>.md`` and its bundle ``<apn>.json``. ``--processes`` adds
``processes.md``: the chain of title, tenures, closings, loan lifecycles, REO resales, and probate as Mermaid DAGs
(``jason.tasks.process_report``). ``--render <apn>.json`` redraws ``processes.md`` from a saved bundle without
calling the county.

Owners are shown by role unless ``--names`` (P1: the people who work with them); the files stay under ``data/`` and
are never committed. Each join is a reading of the index, a lead, not a pin.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable


def _out_dir(args: argparse.Namespace, stem: str) -> Path:
    if args.out:
        return Path(args.out)
    from jason.config import Settings

    return Settings.load(args.env).payhoa_catalog.parent / "reports" / "placer" / stem


def _processes(bundle: dict, out: Path, *, address: str, names: bool) -> Path:
    from jason.tasks.process_report import process_markdown

    page = out / ("processes-names.md" if names else "processes.md")
    page.write_text(process_markdown(bundle, address=address, names=names), encoding="utf-8")
    return page


def cmd_placer_history(args: argparse.Namespace) -> int:
    if args.render:
        source = Path(args.render)
        if not source.is_file():
            print(f"no bundle at {source}", file=sys.stderr)
            return 2
        bundle = json.loads(source.read_text(encoding="utf-8"))
        print(_processes(bundle, Path(args.out) if args.out else source.parent, address=args.address or "", names=args.names))
        return 0
    if not args.parcel:
        print("give a parcel (an address, a twelve-digit APN, or a document number), or --render BUNDLE.json", file=sys.stderr)
        return 2
    from jason.community.placer.assessor import PlacerCountyAssessor
    from jason.tasks.placer_history import placer_parcel_report

    assessor = PlacerCountyAssessor()
    digits = "".join(ch for ch in args.parcel if ch.isdigit())
    stem = digits if len(digits) == 12 else ""
    address = args.address or ""
    if not stem:
        # The assessor's search answers an empty list on a failed request as well as on no match: ask twice.
        hits = assessor.search(args.parcel, kind="idaddress") or assessor.search(args.parcel, kind="idaddress")
        if not hits:
            print(f"the Placer assessor has no parcel for {args.parcel!r}", file=sys.stderr)
            return 1
        stem = hits[0].apn
        address = address or getattr(hits[0], "address", "") or args.parcel
    out = _out_dir(args, stem)
    report = placer_parcel_report(stem, out, assessor=assessor, pause=args.pause)
    if report is None:
        print(f"no recorded history found for {args.parcel}", file=sys.stderr)
        return 1
    for path in report.paths:
        print(path)
    if args.processes:
        print(_processes(report.bundle.as_dict(), out, address=address, names=args.names))
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("placer-history", help="A Placer parcel's recorded history; --processes draws its document processes as DAGs")
    add_common(p)
    p.add_argument("parcel", nargs="?", help="an address, a twelve-digit APN, or a document number")
    p.add_argument("--processes", action="store_true", help="also write processes.md: Mermaid DAGs of the chain, closings, loans, and liens")
    p.add_argument("--render", metavar="BUNDLE", help="redraw processes.md from a saved <apn>.json, without calling the county")
    p.add_argument("--names", action="store_true", help="show owners by name (P1) in processes-names.md; default: by role")
    p.add_argument("--address", help="the address for the page title (default: the assessor's)")
    p.add_argument("--out", help="the folder to write (default data/reports/placer/<apn>)")
    p.add_argument("--pause", type=float, default=1.0, help="seconds between index searches (default 1)")
    p.set_defaults(func=cmd_placer_history)
