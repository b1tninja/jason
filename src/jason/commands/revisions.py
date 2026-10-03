"""``jason revisions``: a document's versions, its sections followed across them, and what changed when (read-only)."""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    parser = sub.add_parser(
        "revisions",
        help="Find a document's versions (email, PayHOA, the site, Drive files and revisions) and say what changed "
             "in each section, and whether an adoption is on record (read-only)",
        description="Collects every version of one document jason outlines (an outline key such as the rules or a "
                    "policy), compares them section by section, and writes data/revisions/KEY.json and the report "
                    "data/reports/revisions-KEY.md. --fetch first reads the Doc's Drive revisions and the Drive and "
                    "PayHOA files named like it (read-only; fails fast without a token). Never writes to Drive or "
                    "PayHOA.",
    )
    add_common(parser)
    parser.add_argument("document", nargs="?", default="", help="the document's outline key; 'all' for every one")
    parser.add_argument("--list", action="store_true", help="list the documents that can be compared")
    parser.add_argument("--fetch", action="store_true",
                        help="read the Doc's Drive revisions and the Drive and PayHOA files named like it first")
    parser.add_argument("--no-payhoa", action="store_true", help="with --fetch, skip PayHOA")
    parser.add_argument("--ocr", action="store_true", help="read an image-only PDF with Tesseract")
    parser.add_argument("--versions", action="store_true", help="print the versions table")
    parser.add_argument("--section", metavar="N", help="one section's lineage and changes (a number or a lineage id)")
    parser.add_argument("--diff", nargs=2, metavar=("A", "B"),
                        help="compare two versions directly: an id (v3), a date (the version current on it), or a hash")
    parser.add_argument("--stored", action="store_true", help="print the stored history; do not rebuild it")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.set_defaults(func=lambda args: run(args, agent_factory))


def run(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import community
    from jason.config import Settings
    from jason.tasks import revision_detection as rd

    settings = Settings.load(args.env)
    data_dir = settings.payhoa_catalog.parent
    spec = community()
    if args.list or not args.document:
        for key in rd.keys(spec):
            stored = rd.load(data_dir, key)
            tail = f"  ({stored['counts'].get('versions', 0)} versions, built {stored['built']})" if stored else ""
            print(f"{key}{tail}")
        return 0
    wanted = rd.keys(spec, series_only=True) if args.document == "all" else [args.document]
    if args.fetch:
        with agent_factory(args) as agent:
            drive = agent.drive(interactive=getattr(args, "interactive", False))
            payhoa = None
            if not args.no_payhoa:
                try:
                    payhoa = agent.payhoa()
                except Exception as exc:                  # no session: Drive's copies still count
                    print(f"PayHOA not read: {exc}")
            for key in wanted:
                got = rd.fetch_drive(drive, spec, data_dir, key)
                print(f"{key}: Drive: {got['revisions']} revisions, {got['exported']} exported, {got['files']} files"
                      + (f"; {len(got['errors'])} errors" if got["errors"] else ""))
                for e in got["errors"][:5]:
                    print(f"  {e}")
                if payhoa is not None:
                    got = rd.fetch_payhoa(payhoa, agent.org_id, spec, data_dir, key, log=lambda s: None)
                    print(f"{key}: PayHOA: {got['files']} files" + (f"; {len(got['errors'])} errors" if got["errors"] else ""))
    if args.diff:
        got = rd.diff(spec, data_dir, wanted[0], args.diff[0], args.diff[1], ocr=args.ocr)
        if args.json:
            print(json.dumps(got, indent=1, ensure_ascii=False))
            return 0
        print(f"{got['from']['id']} ({got['from']['on']}) -> {got['to']['id']} ({got['to']['on']}): "
              f"{len(got['changes'])} changes")
        for c in got["changes"]:
            num = (c.get("after") or c.get("before") or {}).get("number", "")
            print(f"  {num}: {c['kind']}" + (f" [{', '.join(c['flags'])}]" if c["flags"] else ""))
            for o in c["ops"]:
                if not o["noise"]:
                    print(f"      {o['op']}: \"{o['before'][:100]}\" -> \"{o['after'][:100]}\"")
        return 0
    for key in wanted:
        if args.stored:
            result = rd.history(data_dir, key)
        else:
            result = rd.build(spec, data_dir, key, ocr=args.ocr, log=print)
            out, page = rd.write(data_dir, result)
            print(f"wrote {out} and {page}")
            history = rd.manual_history(data_dir, result)
            if history is not None:
                print(f"wrote the detector's rows to {history} (jason manual reads them)")
        if args.section:
            got = rd.section_history(data_dir, key, args.section)
            if args.json:
                print(json.dumps(got, indent=1, ensure_ascii=False))
                continue
            for lin in got.get("lineages") or []:
                print(f"{lin['id']}: numbers {' -> '.join(lin['numbers'])}; now {lin['current'] or '(gone)'}")
                for t in lin["timeline"]:
                    print(f"    {t['label']:28} {t['stage']:11} {t['note']}  [{t['event']}]")
            for c in got.get("changes") or []:
                print(f"  {c['fromOn']} -> {c['toOn']}: {c['kind']} {c['flags']}")
                print(f"      before: {c['before'][:300]}")
                print(f"      after:  {c['after'][:300]}")
            continue
        if args.json:
            print(json.dumps(result, indent=1, ensure_ascii=False))
        else:
            print("\n".join(rd.lines(result, versions=args.versions)))
    return 0


__all__ = ["register", "run"]
