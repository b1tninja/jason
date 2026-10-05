"""``jason rules``: who may make rules, and which subjects have rules on file.

    jason rules --find                         # read every document with the rules' reading; write data/rules/authority.json
    jason rules --find --model                 # add the local model (qwen3.5:9b, three more samples a candidate), under the GPU lock
    jason rules --find --document bylaws       # one document (repeatable)
    jason rules                                # the grants found, with their words, holders, subjects, conditions, procedure
    jason rules --all                          # the limits too (notice, vote, reversal)
    jason rules --subjects                     # each subject: authority, rules on file, and Civil Code 4355's reading
    jason rules --measure                      # precision and recall against data/rules/gold.json
    jason rules --review ID --status confirmed --note "read 2026-10-05" --by NAME

A reading is a lead for a person, never a rule row: jason proposes and the board adopts. Reading only: nothing in Drive,
PayHOA, or the mail changes (``jason.community.rule_authority``, docs/rule-authority.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import data_dir

    return data_dir(getattr(args, "env", None))


def _model(args: argparse.Namespace):
    from jason.community.rule_authority import RuleModel

    return RuleModel(model=args.model if isinstance(args.model, str) else "", lock_wait=args.wait)


def _model_name(args: argparse.Namespace) -> str:
    from jason.community.ocr_models import DEFAULT_TEXT_MODEL

    return args.model if isinstance(args.model, str) else DEFAULT_TEXT_MODEL


def cmd_rules(args: argparse.Namespace) -> int:
    from jason.community import community
    from jason.community import rule_authority as ra
    from jason.community.content import ModelUnavailable
    from jason.tasks import rule_authority as task

    data_dir = _data_dir(args)
    if args.review:
        try:
            entry = ra.review(data_dir, args.review, ra.Review(args.status), note=args.note or "", reviewer=args.by or "")
        except (KeyError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps(entry) if args.json else f"{args.review}: {entry['status']}")
        return 0

    if args.find:
        model = _model(args) if args.model is not None else None
        try:
            found = task.run(data_dir, args.document or (), community=community(), model=model, samples=args.samples,
                             again=args.again, log=lambda line: print(line, file=sys.stderr))
        except KeyError as exc:
            print(str(exc.args[0]), file=sys.stderr)
            return 2
        except ModelUnavailable as exc:
            print(f"the local model is not available: {exc}", file=sys.stderr)
            return 1
        rows = found["authorities"]
        grants = [a for a in rows if a.answer is ra.Answer.GRANT]
        print(f"{len(found['candidates'])} candidates; {len(grants)} grants and {len(rows) - len(grants)} limits"
              f" ({sum(1 for a in rows if a.tier is ra.Tier.LIKELY)} likely, {sum(1 for a in rows if a.tier is ra.Tier.SUGGESTED)} suggested, "
              f"{sum(1 for a in rows if a.tier is ra.Tier.CONFLICT)} where the readers disagree); stored in {ra.store_path(data_dir)}")
        args.find = False

    if args.measure:
        try:
            items = task.gold(data_dir)
        except OSError as exc:
            print(f"no gold set: {exc}", file=sys.stderr)
            return 2
        result = _measure(args, data_dir, items, community())
        if result is None:
            return 1
        print(json.dumps(result, indent=1) if args.json else "\n".join(_measure_lines(result)))
        return 0

    rows = ra.stored(data_dir)
    if args.subjects:
        table = task.subjects(data_dir, community(), authorities=rows)
        if args.json:
            print(json.dumps([{"subject": r.subject.value, "standing": r.standing.value, "grants": list(r.grants),
                               "rules": [f"{x.source} {x.section}" for x in r.rules], "reach": r.reading.reach.value,
                               "cites": list(r.reading.cites)} for r in table], indent=1))
        else:
            print("\n".join(task.subject_lines(table, authorities=rows)))
        return 0
    if not rows:
        print("nothing stored: run jason rules --find (add --model for the local model)", file=sys.stderr)
        return 1
    kinds = (ra.Answer.GRANT, ra.Answer.LIMITS) if args.all else (ra.Answer.GRANT,)
    shown = [a for a in rows if a.answer in kinds and (not args.tier or a.tier.value == args.tier)]
    if args.json:
        print(json.dumps([a.to_dict() for a in shown], indent=1))
    else:
        print("\n".join(task.authority_lines(shown, answers=kinds)))
    return 0


def _measure(args: argparse.Namespace, data_dir: Path, items: list[dict[str, Any]], active: Any) -> dict[str, Any] | None:
    """Read every candidate again (the rules, and the model's saved answers, or the model itself with --model) and score."""
    from jason.community import rule_authority as ra
    from jason.community.content import ModelUnavailable
    from jason.tasks import rule_authority as task

    outlines = task.outlines_of(data_dir)
    duties = task.duties_of(data_dir, outlines)
    cache = ra.load_answers(data_dir)
    model = _model(args) if args.model is not None else None
    try:
        found = ra.find(outlines, model=model, duties=duties, parts=task.rule_parts(data_dir, active, outlines), samples=args.samples,
                        cache=cache, cached_model=_model_name(args), log=lambda line: print(line, file=sys.stderr))
    except ModelUnavailable as exc:
        print(f"the local model is not available: {exc}", file=sys.stderr)
        return None
    finally:
        if model is not None:
            model.release()
            ra.save_answers(data_dir, cache)
    result = ra.measure(items, found["candidates"], found["rules"], found["model"])
    hard = [i for i in items if i.get("hard")]
    if hard:
        easy = [i for i in items if not i.get("hard")]
        result["withoutHard"] = ra.measure(easy, found["candidates"], found["rules"], found["model"])["readers"]
    return result


def _measure_lines(r: dict[str, Any]) -> list[str]:
    out = [f"{r['items']} gold items; {r['collected']} found as candidates; collector recall on grants {r['collectorRecall']}"]
    for name, c in r["readers"].items():
        out.append(f"  {name:7} precision {c['precision']:.3f}  recall {c['recall']:.3f}  f1 {c['f1']:.3f}  "
                   f"(tp {c['tp']} fp {c['fp']} fn {c['fn']} tn {c['tn']})")
    for name, c in (r.get("withoutHard") or {}).items():
        out.append(f"  {name:7} without the hard items: precision {c['precision']:.3f}  recall {c['recall']:.3f}")
    for name, d in r.get("detail", {}).items():
        out.append(f"  {name}: of {d['grantsRead']} grants read right, holder right {d['holderRight']}, subject recall {d['subjectRecall']}")
    for name, right in r.get("answerRight", {}).items():
        out.append(f"  {name}: four-way answer right {right}")
    return out


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("rules", help="Who may make rules: the provisions that give the board, the association, or a "
                                     "committee the power to adopt rules, their subjects and limits, and which "
                                     "subjects have rules on file")
    add_common(p)
    p.add_argument("--find", action="store_true", help="read the governing documents for grants and limits (the rules' reading) and store them")
    p.add_argument("--model", nargs="?", const=True, default=None, metavar="NAME",
                   help="with --find or --measure: also ask the local model (default qwen3.5:9b); needs Ollama, the GPU lock, and commit")
    p.add_argument("--samples", type=int, default=3, help="with --model: extra samples a candidate at temperature 0.3, for self-consistency (default 3)")
    p.add_argument("--wait", type=int, default=3600, help="with --model: seconds to wait for another job's GPU lock (default 3600)")
    p.add_argument("--again", action="store_true", help="with --model: ask again even where an answer is saved")
    p.add_argument("--document", action="append", metavar="KEY", help="with --find: one document (an outline key); repeatable; default every governing document")
    p.add_argument("--all", action="store_true", help="list the limits too, not only the grants")
    p.add_argument("--tier", choices=("likely", "suggested", "conflict"), help="list only this tier")
    p.add_argument("--subjects", action="store_true", help="each subject: the authority found, the rules on file, and the Civil Code 4355 reading")
    p.add_argument("--measure", action="store_true", help="precision and recall of each reader against data/rules/gold.json")
    p.add_argument("--review", metavar="ID", help="record a person's review of one reading")
    p.add_argument("--status", choices=("confirmed", "corrected", "rejected"), default="confirmed", help="with --review")
    p.add_argument("--note", help="with --review: the reviewer's note")
    p.add_argument("--by", help="with --review: the reviewer")
    p.add_argument("--json", action="store_true", help="JSON output")
    p.set_defaults(func=cmd_rules)


__all__ = ["cmd_rules", "register"]
