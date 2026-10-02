"""``jason living``: documents kept as amended, built from the base text and the amendments in effect.

``jason living`` lists them. ``jason living KEY`` builds the current text from the saved sources and writes
``data/living/KEY/current.md``; ``--fetch`` reads the Docs again first (read-only). ``--working`` compares the working
copy a person keeps by hand. ``--redline INSTRUMENT`` prints an amendment's marked words. ``--section N`` prints one
provision with its history. ``--annotations`` reads the working copy's comments (read-only) into
``data/annotations/KEY.json`` and places each on the current text. jason never edits the working copy.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Any, Callable


def _data_dir(args: argparse.Namespace):
    from jason.config import Settings

    return Settings.load(getattr(args, "env", None)).ownership_db.parent


def cmd_living(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import community
    from jason.community.living import place
    from jason.tasks import living_docs

    rows = community().living_documents()
    if not args.key:
        for ld in rows:
            print(f"{ld.key}: {ld.title}; base {ld.base_from}; {len(ld.instruments)} instruments")
        if not rows:
            print("no living documents: a LivingDocument row in the specification (Community.living_documents())")
        return 0
    ld = next((r for r in rows if r.key == args.key), None)
    if ld is None:
        print(f"no living document {args.key}: {', '.join(r.key for r in rows)}", file=sys.stderr)
        return 2
    data_dir = _data_dir(args)
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    comments = None
    if args.fetch or args.annotations:
        with agent_factory(args) as agent:
            drive = agent.drive()
            docs = drive.docs() if args.fetch else None
            built = living_docs.build(ld, data_dir, docs=docs, as_of=as_of, working=args.working or args.annotations,
                                     all_sections=args.all_sections)
            if args.annotations and ld.working_doc:
                comments = drive.list_comments(ld.working_doc)
    else:
        built = living_docs.build(ld, data_dir, as_of=as_of, working=args.working or args.all_sections,
                                  all_sections=args.all_sections)
    if args.redline:
        inst = next((i for i in built.current.applied + built.current.pending if i.key == args.redline), None)
        if inst is None:
            print(f"no instrument {args.redline}", file=sys.stderr)
            return 2
        print(inst.describe())
        for op in inst.operations:
            print(f"\n{op.section} ({op.verb.value}){' [marks lost]' if op.marks_lost else ''}:\n{op.redline()}")
        return 0
    if args.section:
        p = built.current.provision(args.section)
        if p is None:
            print(f"no section {args.section}", file=sys.stderr)
            return 2
        print(f"{p.number} {p.caption}".strip())
        print(built.current.text_of(p.number))
        print(f"\nset by {p.set_by}{f' ({p.dated})' if p.dated else ''}; history: {', '.join(p.history)}")
        return 0
    path = living_docs.write(built, data_dir)
    print("\n".join(living_docs.lines(built)))
    print(f"\nwrote {path}")
    if comments is not None:
        copy = living_docs.working_copy(ld, data_dir)
        found = living_docs.save_annotations(data_dir, ld.key, living_docs.comments_to_annotations(comments, copy))
        print(f"\n{len(found)} annotations from the working copy's comments "
              f"({living_docs.annotations_path(data_dir, ld.key)}):")
        print("\n".join(living_docs.annotation_lines(living_docs.place_annotations(built.current, copy, found))))
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("living", help="Documents kept as amended: the current text from the base and the amendments in "
                                      "effect, with provenance, drift, and annotations")
    add_common(p)
    p.add_argument("key", nargs="?", help="the document (ccrs); none lists them")
    p.add_argument("--fetch", action="store_true", help="read the Docs again first (read-only)")
    p.add_argument("--working", action="store_true", help="compare the working copy kept by hand: the amended sections")
    p.add_argument("--all-sections", action="store_true",
                   help="compare every section of the working copy (a base read by OCR differs mostly by its slips)")
    p.add_argument("--as-of", help="the text in force on this date (YYYY-MM-DD)")
    p.add_argument("--redline", metavar="INSTRUMENT", help="an amendment's words with their marks (ccrs-2nd-amendment)")
    p.add_argument("--section", help="one provision with its history (4.15(a))")
    p.add_argument("--annotations", action="store_true",
                   help="read the working copy's comments (read-only) into data/annotations and place them")
    p.set_defaults(func=lambda a: cmd_living(a, agent_factory))
