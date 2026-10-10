"""``jason reference``: the reference shelf, published guides that explain a process.

``jason reference`` lists the works and whether each is on disk. ``--fetch`` brings the missing ones into
``data/reference`` (the PDF, a note that titles it, and its text by page). ``--page WORK N`` prints one page of a work's
text, to read or cite by page. ``--cites WORK`` reads the statutes the work cites and places each against the
authorities shelf and lawlibrary, with the section numbers the shelf lacks written as a proposal (exit 1 when there are some). The shelf is a catalog of its own in AnythingLLM (``jason anythingllm --sync
--catalog reference``), apart from the authorities, the association's records, and Jason's pages.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable


def cmd_reference(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.commands._shared import data_dir, to_json
    from jason.community.reference_shelf import REFERENCE_WORKS, fetch_reference, find_work, page_text, reference_dir

    root = data_dir(args)
    if args.fetch:
        got = fetch_reference(root)
        print(f"fetched {', '.join(got)}" if got else "the reference shelf is up to date")
    if args.page:
        name, number = args.page
        work = find_work(name)
        if work is None or not number.isdigit():
            print(f"no reference work {name!r}, or {number!r} is not a page number", file=sys.stderr)
            return 2
        text = page_text(root, work, int(number))
        if not text:
            print(f"{work.title}: no text for page {number} on disk (run jason reference --fetch)", file=sys.stderr)
            return 1
        print(text)
        return 0
    if args.cites:
        return _cites(args, root, args.cites)
    rows = [{"title": w.title, "file": w.filename, "year": w.year, "author": w.author, "onDisk": (reference_dir(root) / w.filename).is_file(),
             "caveat": w.caveat} for w in REFERENCE_WORKS]
    if args.json:
        print(to_json(rows))
        return 0
    for row in rows:
        print(f"{'on disk' if row['onDisk'] else 'missing':8} {row['year']}  {row['title']}  ({row['file']})")
        print(f"         {row['author']}; {row['caveat']}")
    return 0 if all(r["onDisk"] for r in rows) else 1


def _cites(args: argparse.Namespace, root: Any, name: str) -> int:
    """The statutes a work cites, placed against the authorities shelf and, unless ``--no-law``, lawlibrary."""
    from jason.community.reference_shelf import find_work, reference_dir
    from jason.sources.lawlibrary import LawLibrary
    from jason.tasks.citation_coverage import save, survey

    from pathlib import Path

    work = find_work(name)
    text_file = reference_dir(root) / (Path(work.filename).stem + ".txt") if work else None
    if work is None or not text_file.is_file():
        print(f"no text on disk for reference work {name!r} (run jason reference --fetch)", file=sys.stderr)
        return 2
    law = None if args.no_law else (LawLibrary() if LawLibrary().available() else None)
    result = survey({work.title: text_file.read_text(encoding="utf-8")}, root, library=law, external=True)
    if result.law_checked:
        kept = save(root, work.title, result)
        print(f"kept {kept}", file=sys.stderr)
    if args.json:
        from jason.commands._shared import to_json

        print(to_json(result.as_dict()))
    else:
        print(result.markdown(f"Statutes cited by {work.title}", 1))
        for note in result.notes:
            print(f"note: {note}", file=sys.stderr)
    return 1 if result.gaps() else 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("reference", help="The reference shelf: published guides that explain a process, kept apart from the law and the record")
    add_common(p)
    p.add_argument("--fetch", action="store_true", help="download the works that are not on disk, with a note and their text")
    p.add_argument("--page", nargs=2, metavar=("WORK", "N"), help="print page N of a work's text (the file name or part of the title)")
    p.add_argument("--cites", metavar="WORK", help="the statutes a work cites and where each stands: on the authorities shelf, in lawlibrary but not exported (exit 1), not found, or renumbered")
    p.add_argument("--no-law", action="store_true", help="with --cites: do not look a statute up in lawlibrary")
    p.add_argument("--json", action="store_true", help="print the list as JSON")
    p.set_defaults(func=lambda args: cmd_reference(args, agent_factory))
