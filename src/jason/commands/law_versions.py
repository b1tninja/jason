"""``jason law-history --versions`` and ``--add-version``: a section's earlier versions, each with its range.

jason's shelf holds one edition of each statute section, the current publication's. A review of an older letter
recites the words in force on the letter's day (AGENTS.md, "Recite the version that governs"). These two flags bring
those words onto the disk, where ``jason readings --recite CITATION --as-of DAY`` and
``jason.community.law_text.in_force`` read them:

- ``--versions`` reads each section's versions out of the session publications lawlibrary holds (its local shelf: no
  internet), and keeps every earlier one as ``data/authorities/history/<citation>/<digest>.md`` with the act that
  made it, the range it was in force, and the publications that printed it. The day the current words came into
  force goes in ``history/versions.json``. Without ``--citation`` it reads the sections the association's documents
  cite; ``--since`` adds those the Act's history says changed since; ``--shelf`` adds every section on the shelf.
- ``--add-version FILE`` keeps a version a person read from an official source the publications do not hold (a day
  before lawlibrary's first code edition, or an act a later one overwrote between two publications): the words in a
  text file, with ``--citation``, ``--source`` (the citation a reader can check), ``--by``, and the range the person
  found (``--from``, ``--until``; a day left out is not recorded).

Not a command of its own (``MODULES`` does not list it): ``cmd_law_history`` in ``jason.cli`` calls ``run``. A person
runs these; no reader does. Nothing is fetched from the internet and no words are written that lawlibrary or the
person's file did not give.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable


def add_arguments(parser: Any) -> None:
    parser.add_argument("--versions", action="store_true",
                        help="Read each section's earlier versions from the session publications lawlibrary holds and keep "
                             "them with their ranges (data/authorities/history); with no --citation, the sections the "
                             "association's documents cite, and with --since those the Act's history says changed since")
    parser.add_argument("--citation", action="append", default=[], metavar="CITATION",
                        help="With --versions or --add-version: a section (CIV-5855); may be given more than once")
    parser.add_argument("--shelf", action="store_true", help="With --versions: also every section the shelf holds")
    parser.add_argument("--add-version", metavar="FILE", default="",
                        help="Keep an earlier version a person read from an official source: a text file of its words; "
                             "needs --citation, --source, and --by")
    parser.add_argument("--source", default="", help="With --add-version: the official source, as a citation a reader can check")
    parser.add_argument("--by", default="", help="With --add-version: who read the source")
    parser.add_argument("--from", dest="start", default="", help="With --add-version: the day the words came into force (YYYY-MM-DD)")
    parser.add_argument("--until", default="", help="With --add-version: the day they ceased (YYYY-MM-DD)")
    parser.add_argument("--act", default="", help="With --add-version: the act that made the words (Stats. 2099, Ch. 1, Sec. 2)")


def _range(text: Any) -> str:
    start = text.start or ("a day not recorded" + (f" (the section's words by {text.floor})" if text.floor else ""))
    why = f" ({text.until_by})" if text.until_by else ""
    if text.until:
        until = f" until {text.until}{why}"
    elif text.current:
        until = ""
    else:
        until = f" until a day not recorded{why}"
    never = " (never in force: ended before its operative day)" if text.start and text.until and text.until <= text.start else ""
    return f"from {start}{until}{never}" + ("; in the newest publication" if text.current else "")


def run(args: argparse.Namespace, root: Path, library: Callable[[], Any]) -> int:
    """Answer ``--versions`` or ``--add-version``. ``library`` gives the lawlibrary checkout when it is needed."""
    if args.add_version:
        return _add(args, root)
    from jason.tasks.law_history import repeals, versions_wanted
    from jason.tasks.statute_fetch import prior_versions

    wanted = list(args.citation) or versions_wanted(root, since=args.since, shelf=args.shelf)
    if not wanted:
        print("nothing to read: no statute citation in data/outlines/references.json (jason outlines); say --citation, "
              "--since, or --shelf", file=sys.stderr)
        return 1
    found = prior_versions(root, wanted, library=library(), repeals=repeals(root))
    if args.json:
        print(json.dumps([{"citation": r.citation, "found": r.found, "printed": list(r.printed), "differs": r.differs,
                           "reason": r.miss.value if r.miss else "", "detail": r.detail, "files": list(r.files),
                           "versions": [{"digest": t.digest, "from": t.start, "floor": t.floor, "until": t.until,
                                         "untilBy": t.until_by, "act": t.act, "editions": list(t.editions),
                                         "newest": t.current} for t in r.versions]} for r in found], indent=1))
        return 0 if any(r.found for r in found) else 1
    done: dict[str, int] = {}
    for r in found:
        if not r.found:
            print(f"{r.citation}: not read: {r.reason_text() or r.detail}" + (f" ({r.detail})" if r.reason_text() and r.detail else ""))
            continue
        earlier = [t for t in r.versions if not t.current]
        if earlier or r.differs or args.citation:
            print(f"{r.citation}: printed in the {r.printed[0]} to {r.printed[-1]} session publications; "
                  f"{len(r.versions)} version(s)")
            for t in r.versions:
                print(f"  {t.digest[:12]}  {_range(t)}" + (f"; {t.act}" if t.act else ""))
            if r.differs:
                print("  the words on the shelf are not the newest publication's: run jason export-authorities")
        for f in r.files:
            done[f["did"]] = done.get(f["did"], 0) + 1
            if f["did"] == "refused":
                print(f"  {f['file']} holds other words than its name says; left alone for a person to look at")
    read = [r for r in found if r.found]
    print(f"{len(read)} of {len(found)} sections read; {sum(len(r.files) for r in read)} earlier versions in the history "
          f"({', '.join(f'{n} {k}' for k, n in sorted(done.items())) or 'none'}); "
          f"{sum(r.differs for r in read)} where the shelf differs from the newest publication; "
          "ranges recorded in data/authorities/history/versions.json")
    return 0 if read else 1


def _add(args: argparse.Namespace, root: Path) -> int:
    from jason.tasks.authority_digests import add_version

    if len(args.citation) != 1:
        print("--add-version needs one --citation", file=sys.stderr)
        return 2
    path = Path(args.add_version)
    if not path.is_file():
        print(f"{path}: no such file", file=sys.stderr)
        return 2
    try:
        kept, did = add_version(root, args.citation[0], path.read_text(encoding="utf-8"), source=args.source, by=args.by,
                                start=args.start, until=args.until, act=args.act)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if did == "held":
        print(f"the history already holds these words: {kept} (its header is corrected by hand)")
    else:
        print(f"kept {kept}: jason readings --recite {args.citation[0]} --as-of DAY recites it for a day in its range")
    return 0


__all__ = ["add_arguments", "run"]
