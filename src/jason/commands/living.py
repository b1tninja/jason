"""``jason living``: documents kept as amended, built from the base text and the amendments in effect.

``jason living`` lists them. ``jason living KEY`` builds the current text from the saved sources and writes
``data/living/KEY/current.md``; ``--fetch`` reads the Docs again first (read-only). ``--working`` compares the working
copy a person keeps by hand. ``--redline INSTRUMENT`` prints an amendment's marked words. ``--section N`` prints one
provision with its history. ``--annotations`` reads the working copy's comments (read-only) into
``data/annotations/KEY.json`` and places each on the current text. jason never edits the working copy.
``--reread cli`` reads a scanned base again beside the reading in use and writes the evidence for switching
(``tasks.ocr_reread``); ``--use-reread cli --yes --by NAME`` is the person's switch.
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
    if args.reread or args.use_reread:
        return _reread(args, ld, data_dir)
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    comments = None
    if args.fetch or args.annotations:
        with agent_factory(args) as agent:
            drive = agent.drive()
            docs = drive.docs() if args.fetch else None
            built = living_docs.build(ld, data_dir, docs=docs, drive=drive if args.fetch else None, as_of=as_of, working=args.working or args.annotations,
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
    if ld.base.kind.value == "scan" and living_docs.chosen_reading(data_dir, ld.key):
        print(f"(the base is read by the {living_docs.chosen_reading(data_dir, ld.key)} reading: "
              f"{living_docs.reading_choice_path(data_dir, ld.key)})")
    print(f"\nwrote {path}")
    if comments is not None:
        copy = living_docs.working_copy(ld, data_dir)
        found = living_docs.save_annotations(data_dir, ld.key, living_docs.comments_to_annotations(comments, copy))
        print(f"\n{len(found)} annotations from the working copy's comments "
              f"({living_docs.annotations_path(data_dir, ld.key)}):")
        print("\n".join(living_docs.annotation_lines(living_docs.place_annotations(built.current, copy, found))))
    return 0


def _reread(args: argparse.Namespace, ld: Any, data_dir: Any) -> int:
    """``--reread NAME``: read the scanned base again beside the reading in use, migrate the transcriptions, and write
    the evidence (a dry run). ``--use-reread NAME --yes --by NAME``: the person's switch."""
    from jason.tasks import ocr_reread

    try:
        if args.reread:
            r = ocr_reread.dry_run(ld, data_dir, args.reread, lexicon=not args.no_lexicon, numbering=args.numbering)
            print("\n".join(ocr_reread.lines(r)))
            print(f"\nwrote {ocr_reread.paths(data_dir, ld.key, args.reread)['report']}")
            print(f"to switch (a person's decision): jason living {ld.key} --use-reread {args.reread} --yes --by NAME")
            return 0
        if not args.yes:
            print(f"would switch {ld.key} to the {args.use_reread} reading: the migrated transcriptions become the set in "
                  f"use (the old kept as a backup) and the proposed questions join the intake queue. Read "
                  f"{ocr_reread.paths(data_dir, ld.key, args.use_reread)['report']} first; --yes --by NAME switches.")
            return 0
        print("\n".join(ocr_reread.switch(ld, data_dir, args.use_reread, args.by or "")))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


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
    readings = ("cli", "pymupdf")                     # living_docs.READINGS, without importing it at startup
    p.add_argument("--reread", choices=readings, metavar="READING",
                   help="read a scanned base again (cli: Tesseract's tool) beside the reading in use; migrate the "
                        "transcriptions and write the comparison (a dry run: nothing in use changes)")
    p.add_argument("--no-lexicon", action="store_true", help="with --reread: count questions without the text rules")
    p.add_argument("--numbering", choices=("text", "labels", "aligned"),
                   help="with --reread: how both readings get their section numbers (default: as builds number them); "
                        "a switch needs a dry run numbered as the builds are")
    p.add_argument("--use-reread", choices=readings, metavar="READING",
                   help="switch to a re-read (a person's decision; needs --yes --by NAME and a dry run first)")
    p.add_argument("--yes", action="store_true", help="with --use-reread: switch")
    p.add_argument("--by", help="with --use-reread: the person who chose it")
    p.set_defaults(func=lambda a: cmd_living(a, agent_factory))
