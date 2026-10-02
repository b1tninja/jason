"""``jason form-lab``: which form layout comes back readable (``jason.tasks.form_lab``).

``--sample`` draws the current layout (and ``--layout`` JSON) blank and filled, as PNGs. ``--evaluate`` scores a layout on
the battery. ``--search`` runs the coordinate descent from the current form's style and writes each evaluation to
``data/forms/lab/search-<date>.jsonl`` and the best layout to ``best.json``. ``--benchmark MODEL ...`` runs Tesseract,
the hints, and each local vision model on the same battery for the current and the best layout. Nothing is sent; the
answers are made up.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import Settings

    return Settings.load(args.env).payhoa_catalog.parent


def cmd_form_lab(args: argparse.Namespace) -> int:
    from jason.tasks import form_lab as fl

    out = _data_dir(args) / "forms" / "lab"
    out.mkdir(parents=True, exist_ok=True)
    layout = fl.Layout.from_json(json.loads(args.layout)) if args.layout else fl.CURRENT
    best_file = out / "best.json"
    trials = fl.battery(args.trials, args.seed)
    costs = None
    if args.priced:
        from payhoa.pricing import PRICING

        costs = fl.Costs(page_cents=PRICING.page, misread_cents=args.misread_cents, returned=args.returned)
        print(f"priced: {PRICING.page}c a page ({costs.point_cents * 100:.2f}c per 100 points of height), "
              f"{args.misread_cents:.0f}c a misread answer, {args.returned:.0%} returned on paper")
    if args.sample:
        layouts = [fl.CURRENT, layout]
        if best_file.is_file():
            layouts.append(fl.Layout.from_json(json.loads(best_file.read_text(encoding="utf-8"))["layout"]))
        for lay in dict.fromkeys(layouts):
            for path in fl.sample(lay, out / "samples", responder=args.responder):
                print(path)
    if args.evaluate:
        ev = fl.evaluate(layout, trials, costs=costs)
        print(json.dumps({"objective": round(ev.objective, 4), "cents": ev.cents and round(ev.cents, 1),
                          **{k: v for k, v in ev.__dict__.items() if k not in ("layout", "costs")}}, indent=1))
    if args.search:
        log = out / f"search-{date.today().isoformat()}.jsonl"
        best, history = fl.search(trials, start=layout, passes=args.passes, log=log, costs=costs,
                                  say=lambda s: print(s.encode("ascii", "replace").decode(), flush=True))
        ev = next(e for e in history if e.layout == best)
        best_file.write_text(json.dumps({"layout": best.as_json(), "objective": ev.objective, "trials": args.trials,
                                         "seed": args.seed, "evaluations": len(history)}, indent=1), encoding="utf-8")
        print(f"best: {fl._short(best)} (objective {ev.objective:.3f}); {len(history)} layouts in {log}")
    if args.benchmark:
        layouts = [fl.CURRENT]
        if best_file.is_file():
            layouts.append(fl.Layout.from_json(json.loads(best_file.read_text(encoding="utf-8"))["layout"]))
        if args.layout:
            layouts.append(layout)
        if args.styles:                               # each kind of answer space, the rest as today
            layouts += [fl.Layout(style=s) for s in fl.FieldStyle if s is not fl.FieldStyle.RULE]
            layouts.append(fl.Layout(phone_style=fl.FieldStyle.CHAR_BOXES))
        layouts = list(dict.fromkeys(layouts))
        rows = fl.benchmark(layouts, trials, args.benchmark, say=lambda s: print(s, flush=True))
        path = out / f"benchmark-{date.today().isoformat()}.json"
        path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        for r in rows:
            print(f"{r['layout'][:50]:50} {r['reader']:28} {r.get('text', r.get('error', ''))}")
        print(path)
    if args.prompts:
        result = fl.prompt_trial(trials, args.prompts, layout=layout, say=lambda s: print(s, flush=True))
        path = out / f"prompts-{date.today().isoformat()}.json"
        path.write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(path)
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("form-lab", help="Find the form layout that comes back most readable (made-up answers)")
    add_common(p)
    p.add_argument("--layout", help="a layout as JSON (default: the current form's style)")
    p.add_argument("--trials", type=int, default=12, help="trials in the battery (default 12)")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--sample", action="store_true", help="draw the layouts blank and filled, as PNGs")
    p.add_argument("--responder", default="hurried print", help="who fills the sample in")
    p.add_argument("--evaluate", action="store_true", help="score the layout on the battery")
    p.add_argument("--search", action="store_true", help="coordinate descent from the layout")
    p.add_argument("--passes", type=int, default=3)
    p.add_argument("--priced", action="store_true",
                   help="price a layout's height at the Mailroom's cost a page (payhoa.pricing) against "
                        "the follow-ups its misreads cost, instead of a fixed space penalty")
    p.add_argument("--misread-cents", type=float, default=150.0,
                   help="with --priced: a person's follow-up for one answer read wrong, in cents (default 150)")
    p.add_argument("--returned", type=float, default=0.5,
                   help="with --priced: the share of mailed letters that come back on paper (default 0.5)")
    p.add_argument("--benchmark", nargs="+", metavar="MODEL", help="readers on the battery: these Ollama vision models")
    p.add_argument("--styles", action="store_true", help="with --benchmark: every kind of answer space too")
    p.add_argument("--prompts", nargs="+", metavar="MODEL",
                   help="does telling these models the form's rules (and what was sent) help, or make them report it?")
    p.set_defaults(func=cmd_form_lab)
