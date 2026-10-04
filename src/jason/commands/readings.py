"""``jason readings``: the profile's readings of the law and the governing documents, each checked against the words.

A reading (``jason.community.law_readings.LawReading``, ``Community.law_readings()``) is what the board or counsel
takes a provision to mean. It is tied to the digest of the words it read, so it is stale when the words change.

- ``jason readings`` lists each reading with its status: current, stale (which provision changed, with the digest it
  read and the digest now), missing (a provision is not on the shelf), or misquoted.
- ``--stale`` lists only those that are not current: each is redone or confirmed by a person before it is used.
- ``--citation CIV-5855`` lists the readings of one provision (a statute's section, or ``KEY#SECTION`` for a
  governing document's).
- ``--recite CITATION`` prints the provision's words with their source and digest, and then the readings of them,
  each labeled as a reading and whose it is; the ones that no longer read these words are listed apart.
  ``--as-of YYYY-MM-DD`` sets apart a reading dated later and says when jason knows the words changed after that day.
- ``--json`` prints the same as JSON.

Reading only: nothing is written, and lawlibrary is not asked for a section that is not on disk.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable


def cmd_readings(args: argparse.Namespace) -> int:
    from jason.commands._shared import data_dir, day
    from jason.community import community as active
    from jason.community.law_readings import Recited, label, readings, recite, status, target_of

    try:
        as_of = day(args.as_of)
    except ValueError:
        print("--as-of is a date, YYYY-MM-DD", file=sys.stderr)
        return 2
    root = data_dir(args)
    community = active()
    found = readings(community)
    if args.recite:
        recital = recite(args.recite, root, found, as_of, community=community)
        if args.json:
            print(json.dumps(recital.as_dict(), indent=1))
        else:
            print("\n".join(recital.lines()))
        return 0 if recital.found else 1
    if args.citation:
        if target_of(args.citation) is None:
            print("--citation is a code and a section (CIV-5855) or a document's section (bylaws#7.2)", file=sys.stderr)
            return 2
        found = tuple(r for r in found if r.reads(args.citation))
    rows = [Recited(r, status(r, root, community=community, as_of=as_of)) for r in found]
    if args.stale:
        rows = [row for row in rows if not row.status.applies]
    if args.json:
        print(json.dumps([row.as_dict() for row in rows], indent=1))
        return 0
    if not rows:
        if args.stale and found:
            print(f"every reading is current ({len(found)} checked)")
        else:
            of = f" of {target_of(args.citation)}" if args.citation else ""
            print(f"no readings recorded{of}: the words stand alone (jason readings --recite CITATION prints them)")
        return 0
    for row in rows:
        r = row.reading
        print(f"{r.key}: {', '.join(p.citation for p in r.provisions)} [{row.status.state.value}]")
        print(f"  {label(r)}")
        if not row.status.applies:
            print(f"  not applied: {row.status.line()}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("readings", help="The board's and counsel's readings of the law and the governing documents, each "
                                        "checked against the words it read; --recite prints the words, then the readings")
    add_common(p)
    p.add_argument("--stale", action="store_true", help="only readings that are not current: the words changed, or are missing")
    p.add_argument("--citation", help="readings of one provision: a statute's section (CIV-5855) or KEY#SECTION")
    p.add_argument("--recite", metavar="CITATION", help="print the provision's words, then the readings of them")
    p.add_argument("--as-of", help="with --recite or the list: the day asked about (YYYY-MM-DD)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_readings)
