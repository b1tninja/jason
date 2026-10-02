"""``jason statute-align``: which provision of one version of the Davis-Stirling Act continues which of another.

``--sample`` or ``--sections 1363,1365`` aligns former Civil Code sections (2011 edition) with the recodified Act
(2013 edition) and, with ``--evaluate``, scores structure, lexical, embedding, and model variants against the Law
Revision Commission's disposition table. ``--amended 5855 --before 2023 --after 2025`` maps an amended section's old
subdivisions to its new ones. Results go under data/authorities/history/alignment. The model's rows are leads, never
pins; see docs/statute-alignment.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import Settings

    return Settings.load(args.env).payhoa_catalog.parent


def _lawlibrary(args: argparse.Namespace):
    from jason.config import Settings
    from jason.sources.lawlibrary import LawLibrary

    return LawLibrary(Settings.load(args.env).lawlibrary_home)


def _print_evaluation(result: dict[str, Any]) -> None:
    run = result["run"]
    print(f"{len(run['sections'])} former sections, {run['units']} units against {run['current_units']} current units "
          f"(structure: {run['structure']})")
    cr = result.get("candidate_recall") or {}
    print(f"candidate recall (table's unit pairs whose section is among the candidates): {cr.get('recall')}")
    print(f"{'variant':<10} {'sec P':>6} {'sec R':>6} {'unit P':>7} {'unit R':>7} {'relation':>9} {'chg P':>6} {'chg R':>6} {'new F1':>7}")
    for name, e in result["evaluation"].items():
        rel = e["relation"]["accuracy"]
        new = (e.get("new") or {}).get("f1")
        chg = e["relation"]["with_changes"]
        show = lambda v: "" if v is None else v  # noqa: E731
        print(f"{name:<10} {e['section']['precision']:>6} {e['section']['recall']:>6} {e['unit']['precision']:>7} "
              f"{e['unit']['recall']:>7} {show(rel):>9} {show(chg['precision']):>6} {show(chg['recall']):>6} {show(new):>7}")
    if run.get("seconds_per_section") is not None:
        print(f"model: {run['requests']} requests, {run['seconds_per_section']} s per section")


def cmd_statute_align(args: argparse.Namespace) -> int:
    from jason.tasks import statute_align as task

    data_dir = _data_dir(args)
    lawlibrary = _lawlibrary(args)
    judge = None
    if not args.no_model:
        from jason.community.statute_alignment import OllamaJudge

        judge = OllamaJudge(model=args.model or "")
    say = (lambda m: print(m, file=sys.stderr)) if not args.json else None
    try:
        if args.amended or args.all_amended:
            result = task.amended(data_dir, lawlibrary, judge, section=args.amended or "", before=args.before, after=args.after,
                                  progress=say)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
                return 0
            for row in result["rows"]:
                if not row.get("found"):
                    print(f"CIV {row['section']} {row['before']} -> {row['after']}: {row.get('reason')}")
                    continue
                print(f"CIV {row['section']} {row['before']} -> {row['after']} ({row['seconds']} s, {row['requests']} model requests)")
                for old in row["old"]:
                    targets = ", ".join(f"{t['current']}{' (moved)' if t.get('moved') else ''} [{t['relation'].replace('_', ' ')}, "
                                        f"{t['source']}, {t['confidence']}]" for t in old["targets"]) or "not continued"
                    print(f"  {old['former']} -> {targets}")
                for c in row["changes"]:
                    print(f"    change {c['former']} -> {c['current']}: {c['change']}")
                for n in row["new"]:
                    print(f"  new: {n['current']}")
            print(f"Saved {result.get('written')}")
            return 0
        from jason.tasks.statute_align import SAMPLE

        sections = [s.strip() for s in args.sections.split(",") if s.strip()] if args.sections else (list(SAMPLE) if args.sample else None)
        embedder = None
        if args.embed:
            from jason.community.retrieval import default_embedder

            embedder = default_embedder(data_dir)
        result = task.recodification(data_dir, lawlibrary, sections=sections, judge=judge, embedder=embedder,
                                     structure=args.structure, progress=say, label=args.label)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result if args.evaluate else {k: result[k] for k in ("run", "former", "current")},
                         indent=2, ensure_ascii=False, default=str))
        return 0
    if args.evaluate:
        _print_evaluation(result)
    else:
        for row in result["former"]:
            targets = ", ".join(f"{t['current']} ({t['relation'].replace('_', ' ')}{': ' + t['change'] if t['change'] else ''})"
                                for t in row["targets"])
            print(f"  {row['former']} -> {targets or 'not continued'}")
    print(f"Saved {result.get('written')}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("statute-align", help="Map provisions between two versions of the Davis-Stirling Act (former 1350-1378 "
                                             "to 4000-6150, or an amended section's subdivisions) and score it against the "
                                             "Law Revision Commission's table; readings are leads, never pins")
    add_common(p)
    p.add_argument("--sample", action="store_true", help="the fifteen-section sample across the Act's chapters")
    p.add_argument("--sections", default="", help="former sections, comma-separated (1363,1365); default with no --sample: all")
    p.add_argument("--evaluate", action="store_true", help="print precision and recall per variant against the table")
    p.add_argument("--embed", action="store_true", help="add the embedding variant (qwen3-embedding:8b, cached vectors)")
    p.add_argument("--no-model", action="store_true", help="structure and similarity only; never asks the local model")
    p.add_argument("--structure", default="gold+outline", choices=("gold+outline", "outline"),
                   help="heading correspondence from other sections' table rows and the headings, or the headings alone")
    p.add_argument("--model", default="", help="the Ollama model (default: jason's shared local model)")
    p.add_argument("--label", default="", help="a name for the result file (recodification-LABEL.json)")
    p.add_argument("--amended", default="", metavar="SECTION", help="a current section amended between two editions (5855)")
    p.add_argument("--all-amended", action="store_true", help="every amendment to 4000-6150 in changes.json")
    p.add_argument("--before", default="", help="with --amended: the earlier edition (2023)")
    p.add_argument("--after", default="", help="with --amended: the later edition (2025)")
    p.add_argument("--json", action="store_true", help="Print JSON")
    p.set_defaults(func=cmd_statute_align)
