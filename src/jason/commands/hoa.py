"""``jason hoa-reports`` and ``jason land-sync``: every owners' association on a county's map, and keeping it current.

``jason land-sync`` brings the county's land store (``asspy.land``, beside the index cache) up to date: the map's
plans and maps, the parcels transferred since the last sync (``--full`` reads every parcel and finds retired ones),
the recorder rows of the common-area parcels' deeds, and the watch's filings since its last read (association,
utility, and tax liens, defaults, annexations, declarations, plans, maps). It prints what changed. It only reads.

``jason hoa-reports`` writes a page for every association the land ties to it, under
``data/reports/hoa/<county>/``: its formation, parcels, turnover, recordings, changes, and maps (``map.svg``,
``footprint.kml``, ``footprint.geojson``; ``--map-books`` the assessor's map pages as PDFs). ``--deeds`` reads every
parcel's last deed from the recorder; owners are named only with ``--names`` (P1). Pages are never committed.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Callable


def _reports_root(args: argparse.Namespace) -> Path:
    if args.out:
        return Path(args.out)
    from jason.config import Settings

    return Settings.load(args.env).payhoa_catalog.parent / "reports" / "hoa"


def cmd_hoa_reports(args: argparse.Namespace) -> int:
    from jason.tasks.hoa_reports import build_reports

    pages = build_reports(args.county, _reports_root(args), only=args.only or (), limit=args.limit, shapes=not args.no_shapes,
                          names=args.names, map_books=args.map_books, deeds=args.deeds,
                          progress=(lambda line: print(line, flush=True)) if args.verbose else None, tied_only=args.tied_only)
    if not pages:
        print("no association is tied to land yet: run `jason land-sync --full` first", file=sys.stderr)
        return 1
    print(f"{len(pages)} pages under {pages[0].path.parent.parent}")
    return 0


def cmd_land_sync(args: argparse.Namespace) -> int:
    from asspy import County
    from asspy.land import common_land_uses, read_deeds, record_owners, sync_divisions, sync_land_uses, sync_parcels, watch_filings

    county = County(args.county)
    gis = getattr(county.assessor, "gis", None)
    if gis is None:
        print(f"{county.name} has no map service in asspy yet", file=sys.stderr)
        return 2
    changes: Counter = Counter()
    with county.land() as land:
        for event in sync_divisions(gis, land):
            changes[event.kind] += 1
        for event in sync_parcels(gis, land, full=args.full):
            changes[event.kind] += 1
        sync_land_uses(gis, land)
        common = common_land_uses(land)
        marks = ",".join("?" * len(common))
        numbers = [p["document_number"] for p in land.parcels(where=f"land_use IN ({marks}) AND status = 'ACTIVE'", args=common)]
        # The plans' and maps' own rows: who recorded each and what its title cites (once; then only new ones).
        numbers += [d["number"] for d in land.divisions() if d["number"]]
        read_deeds(county.recorder, land, numbers)
        # The associations those deeds name join the directory, as recordings under their names.
        with county.associations() as directory:
            changes["association found by a deed"] += record_owners(land, directory)
        if not args.no_watch:
            after = date.fromisoformat(args.since) if args.since else None
            for event in watch_filings(county.recorder, land, after=after):
                changes[event.kind] += 1
    if not changes:
        print("no changes")
    for kind, count in changes.most_common():
        print(f"{count:6}  {kind}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("hoa-reports", help="A page for every owners' association on the county's map: parcels, maps, documents, changes")
    add_common(p)
    p.add_argument("--county", default="sacramento", help="the county (default sacramento)")
    p.add_argument("--only", nargs="*", help="only associations whose names hold these words")
    p.add_argument("--limit", type=int, default=0, help="at most this many pages")
    p.add_argument("--tied-only", action="store_true", help="only associations whose land is tied (by deed, plan, or name)")
    p.add_argument("--no-shapes", action="store_true", help="do not read shapes from the county's map (no map.svg or KML)")
    p.add_argument("--map-books", action="store_true", help="download the assessor's map book pages as PDFs")
    p.add_argument("--deeds", action="store_true", help="read every parcel's last deed from the recorder (slow; cached)")
    p.add_argument("--names", action="store_true", help="name owners from their deeds (P1; needs --deeds); default: none")
    p.add_argument("--out", help="the folder to write (default data/reports/hoa)")
    p.add_argument("--verbose", action="store_true", help="print a line per page")
    p.set_defaults(func=cmd_hoa_reports)

    q = sub.add_parser("land-sync", help="Bring the county's land store current: plans, maps, parcels, deeds, and the recorder watch")
    add_common(q)
    q.add_argument("--county", default="sacramento", help="the county (default sacramento)")
    q.add_argument("--full", action="store_true", help="read every parcel (about a minute), finding retired ones")
    q.add_argument("--no-watch", action="store_true", help="skip the recorder watch")
    q.add_argument("--since", help="read the watch from this day (YYYY-MM-DD) instead of its last read")
    q.set_defaults(func=cmd_land_sync)
