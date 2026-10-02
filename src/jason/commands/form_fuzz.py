"""``jason form-fuzz``: the paper form and its reader tested with made-up answers (``jason.tasks.form_fuzz``).

``jason form-fuzz`` checks the generated form (``--lint`` alone stops there), then runs ``--cases`` cases: answers
made up in each style, typed, handwritten, cursive, or pre-filled and sent back, scanned at each profile, read raw and
with the reading hints, and scored. The report goes to ``data/forms/fuzz/<form>/report-<date>.md``; failing cases join
the corpus, and ``--replay`` runs the corpus again. Nothing is sent and no owner's information is used.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import Settings

    return Settings.load(args.env).payhoa_catalog.parent


def cmd_form_fuzz(args: argparse.Namespace) -> int:
    import tempfile

    from jason.community.form_layout import read_layout
    from jason.community.forms import FormKey
    from jason.community.spec import spec_module
    from jason.tasks import form_fuzz as fz

    data = _data_dir(args)
    forms = spec_module("forms")
    form = next(f for f in vars(forms).values() if getattr(f, "key", None) == FormKey(args.form) and hasattr(f, "questions"))
    blank = Path(args.pdf) if args.pdf else data / "packets" / "owner-information-2027" / "owner-info-fillable.pdf"
    if not blank.is_file():
        print(f"no fillable form at {blank}: build it with jason packet owner-information --build --yes", file=sys.stderr)
        return 2
    layout = read_layout(blank, form)
    findings = fz.lint(blank, layout, form)
    packet = blank.with_name("packet.pdf")
    if packet.is_file() and packet != blank:
        findings += [fz.Finding(f.kind, f"letter, {f.where}", f.detail) for f in fz.lint(packet, layout, form)
                     if f.kind in ("token left unfilled", "marker place not clear", "inside the print margin")]
    print(f"lint: {len(findings)} finding(s)")
    for f in findings:
        print(f"  {f.kind} ({f.where}): {f.detail}")
    if args.lint:
        return 0
    if args.replay:
        todo = fz.load_corpus(data, form)
        if not todo:
            print("the corpus is empty")
            return 0
    else:
        todo = fz.cases(args.seed, args.cases, fills=[fz.Fill(x) for x in args.fills.split(",")],
                        styles=[fz.Style(x) for x in args.styles.split(",")], profiles=args.profiles.split(","))
    model = None
    if args.model:                                    # the local vision model reads the text fields too
        from jason.community.form_reader import VisionReader
        from jason.local_ai import LocalAIUnavailable, preflight

        try:
            preflight(args.model)
        except LocalAIUnavailable as exc:
            print(exc, file=sys.stderr)
            return 2
        model = VisionReader(args.model, timeout=240)
    results = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        for n, case in enumerate(todo, 1):
            r = fz.run_case(case, form, blank, layout, Path(tmp), model=model)
            results.append(r)
            state = r.error or (f"{r.share:.0%} raw, {r.share_hinted:.0%} hinted, marker {r.marker_how or 'none'}"
                                if r.aligned else "could not align")
            line = f"[{n}/{len(todo)}] {case.label()}: {state}"
            print(line.encode("ascii", "replace").decode(), flush=True)         # the console may not print accents
    if args.model:
        from jason.local_ai import unload

        unload(args.model)
    today = date.today().isoformat()
    out = Path(args.out) if args.out else fz.corpus_path(data, form).with_name(f"report-{today}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(fz.report(results, findings, form=form, seed=args.seed, today=today), encoding="utf-8")
    failed = [r.case for r in results if r.failed]
    if failed and not args.replay:
        print(f"{len(failed)} failing case(s) kept in {fz.save_corpus(data, form, failed)}")
    print(f"report: {out}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    from jason.tasks.form_fuzz import PROFILES

    p = sub.add_parser("form-fuzz", help="Test the paper form and its reader with made-up answers and bad scans")
    add_common(p)
    p.add_argument("--form", default="owner-info", help="the form's key (default owner-info)")
    p.add_argument("--pdf", help="the fillable PDF (default: the owner information packet's)")
    p.add_argument("--cases", type=int, default=24, help="how many cases (default 24)")
    p.add_argument("--seed", type=int, default=1, help="the seed the cases are drawn from (default 1)")
    p.add_argument("--fills", default="typed,hand,cursive,prefilled,edited", help="typed, hand, cursive, prefilled, edited")
    p.add_argument("--styles", default="plain,long,lookalike,punctuation,accents,caps", help="styles of made-up answer")
    p.add_argument("--profiles", default=",".join([*PROFILES, "random"]), help="scan profiles, and random")
    p.add_argument("--lint", action="store_true", help="only check the generated form")
    p.add_argument("--replay", action="store_true", help="run the corpus of failing cases again")
    p.add_argument("--out", help="where the report goes")
    p.add_argument("--model", help="read the text fields with this local vision model too (Ollama)")
    p.set_defaults(func=cmd_form_fuzz)
