"""``jason manual``: the owner's manual taken apart into the operating rules, copies, policies, and guidance.

``--classify`` reads the manual's outline (the Doc as ``jason outlines --fetch`` last read it), applies the profile's
rows (``Community.owners_manual()``), checks each against the deontic grammar's norms and the copy scan, and writes
``data/manual/KEY/classification.{json,md}``; ``--asks`` also puts the open questions in the intake store (``jason
intake`` answers them). ``--concordance`` writes ``concordance.{json,md}``: every old address to its new one, and every
existing citation of the manual resolved through it. ``--render`` fills the base templates
(``src/jason/templates/manual``) and writes the official rules and the generated manual to ``data/drafts/``, with the
manual's diff against the Doc's text. Reading only: nothing in Drive, PayHOA, or the mail changes.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable


def _data_dir(args: argparse.Namespace):
    from jason.config import Settings

    return Settings.load(getattr(args, "env", None)).ownership_db.parent


def cmd_manual(args: argparse.Namespace) -> int:
    from jason.community import community
    from jason.community.manual import ManualError, concordance
    from jason.tasks import manual as task

    data_dir = _data_dir(args)
    if not (args.classify or args.concordance or args.render):
        args.classify = True
    try:
        result, outline, spec = task.classify(data_dir, community())
    except ManualError as exc:
        print(f"jason manual: {exc}", file=sys.stderr)
        return 1
    if args.classify or args.concordance:
        paths = task.save_classification(data_dir, result, outline, spec, community())
        if args.classify:
            print(f"{spec.document}: {len(result.sections)} sections")
            for kind, n in sorted(task.counts_by_letter(result).items()):
                print(f"  {kind}: {n}")
            asked: set[str] = set()
            for c in result.sections:
                if c.kind.value in ("mixed", "unclear"):
                    pieces = ", ".join(f"{s.kind.value} -> {s.address}" for s in c.segments)
                    question = c.question if c.question and c.question not in asked else ""
                    asked.add(c.question)
                    print(f"  {c.kind.value}: {c.old}: {pieces}" + (f"\n    ? {question}" if question else ""))
            print(f"wrote {paths['classification_md']}")
            if args.asks:
                print(f"wrote the open questions to {task.merge_asks(data_dir, result)} (jason intake)")
        if args.concordance:
            rows = concordance(result, outline.text)
            refs = task.references(community(), rows, spec, data_dir)
            moved = [r for r in rows if r.piece == 0 and r.status.startswith(("renumbered", "moved"))]
            print(f"{len(rows)} pieces; {len(moved)} sections at a new address; {len(refs)} existing citations, "
                  f"{sum(1 for r in refs if not r['new'])} unresolved")
            for r in refs:
                if not r["new"]:
                    print(f"  UNRESOLVED {r['where']}: {r['ref']}")
            print(f"wrote {paths['concordance_md']}")
    if args.render:
        try:
            out = task.render(data_dir, community())
        except ManualError as exc:
            print(f"jason manual: {exc}", file=sys.stderr)
            return 1
        found = out["check"]
        print(f"rendered: {out['paths']['rules']} and {out['paths']['manual']}")
        print(f"the manual beside the Doc: {'every word placed' if found.covered else 'MISSING ' + '; '.join(found.missing)}"
              f"{', in order' if not found.out_of_order else ', OUT OF ORDER'}; {found.same} pieces the same, "
              f"{len(found.labeled)} labeled changes, {len(found.unlabeled)} unlabeled")
        for d in found.labeled:
            print(f"  labeled {d.segment}: {d.label} ({d.detail})")
        for d in found.unlabeled:
            print(f"  UNLABELED {d.segment}: {d.detail}")
        print(f"diff: {out['paths']['diff']}")
        return 1 if found.unlabeled or not found.covered else 0
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("manual", help="The owner's manual taken apart: which sections are the operating rules, copies, "
                                      "policies, and guidance; the official rules and the generated manual")
    add_common(p)
    p.add_argument("--classify", action="store_true", help="classify every section with its evidence (the default)")
    p.add_argument("--asks", action="store_true", help="with --classify: put the open questions in the intake store")
    p.add_argument("--concordance", action="store_true", help="every old address to its new one, and every existing "
                                                              "citation of the manual resolved")
    p.add_argument("--render", action="store_true", help="write the official rules and the generated manual to "
                                                         "data/drafts, with the diff against the Doc's text")
    p.set_defaults(func=cmd_manual)


__all__ = ["cmd_manual", "register"]
