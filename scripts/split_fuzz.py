"""A benchmark for the PDF splitter's suggestion pass (docs/pdf-splitter.md, 4.7). A skeleton in the pattern of structure_fuzz.py.

    python scripts/split_fuzz.py gold --cache D:/scratch/jason/split-fuzz [--only letters,numbered]
    python scripts/split_fuzz.py variants --cache ... [--only numbered]
    python scripts/split_fuzz.py recover --cache ... [--variants clean,image150] [--without size-change,dpi-change]
    python scripts/split_fuzz.py score --cache ...
    python scripts/split_fuzz.py report --cache ... [--out report.md]

``gold`` draws the made-up archetypes (``jason.community.split_gold``) with the pages that truly start a document, into
``CACHE/split/NAME/``. ``variants`` degrades each in controlled steps (the text layer gone so only images remain, at 150 dpi).
``recover`` runs the suggestion pass on every variant, with any signal left out (``--without``). ``score`` computes the start
precision, recall and F1 at Medium-or-better and at every band, the taps a person would still need against marking every start,
and a calibration table (the share of each band that were real starts). ``report`` writes them as a table.

Everything here is made up: no real scan is read, and none is put in a tracked file. A private labeled set is a separate local run
that keeps counts only. Still to build (docs/pdf-splitter.md, 4.7): more degradations (skew and speckle, shuffled page-number labels,
inserted blanks, a mid-document size change), the nested archetype, the two-language file, and the model pass's ablation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from jason.community import split_gold as sg  # noqa: E402
from jason.community import split_suggest as ss  # noqa: E402
from jason.tasks import split_session as sess  # noqa: E402

VARIANTS = {"clean": lambda pdf: pdf, "image150": lambda pdf: sg.strip_text(pdf, 150)}


def folder(args: argparse.Namespace, name: str = "") -> Path:
    return Path(args.cache) / "split" / name if name else Path(args.cache) / "split"


def names(args: argparse.Namespace) -> list[str]:
    base = folder(args)
    found = sorted(p.name for p in base.iterdir() if (p / "gold.json").is_file()) if base.is_dir() else []
    only = [n for n in (getattr(args, "only", "") or "").split(",") if n]
    return [n for n in found if not only or n in only]


def cmd_gold(args: argparse.Namespace) -> int:
    only = [n for n in (args.only or "").split(",") if n] or list(sg.ARCHETYPES)
    for name in only:
        gold = sg.ARCHETYPES[name]()
        out = folder(args, name)
        out.mkdir(parents=True, exist_ok=True)
        (out / "clean.pdf").write_bytes(gold.pdf)
        (out / "gold.json").write_text(json.dumps({"name": name, "starts": gold.starts, "pages": gold.pages, "note": gold.note}, indent=1),
                                       encoding="utf-8")
        print(f"gold {name}: {gold.pages} pages, {len(gold.starts)} starts")
    return 0


def cmd_variants(args: argparse.Namespace) -> int:
    for name in names(args):
        out = folder(args, name)
        base = (out / "clean.pdf").read_bytes()
        for key, make in VARIANTS.items():
            if key != "clean":
                (out / f"{key}.pdf").write_bytes(make(base))
        print(f"variants {name}: {', '.join(VARIANTS)}")
    return 0


def cmd_recover(args: argparse.Namespace) -> int:
    without = [w for w in (args.without or "").split(",") if w]
    wanted = [v for v in (args.variants or "").split(",") if v] or list(VARIANTS)
    for name in names(args):
        out = folder(args, name)
        for key in wanted:
            pdf = out / f"{key}.pdf"
            if not pdf.is_file():
                continue
            facts, infos = sess.scan(pdf, lqip=False)
            found = ss.suggest(facts, infos, without=without)
            tag = f"{key}" + (f"-without-{'-'.join(without)}" if without else "")
            (out / f"recover-{tag}.json").write_text(json.dumps({"variant": key, "without": without,
                                                                "suggestions": [s.to_dict() for s in found]}, indent=1), encoding="utf-8")
            print(f"recover {name}/{tag}: {len(found)} suggestions")
    return 0


def scores(args: argparse.Namespace) -> list[dict]:
    rows = []
    for name in names(args):
        out = folder(args, name)
        gold = json.loads((out / "gold.json").read_text(encoding="utf-8"))
        for path in sorted(out.glob("recover-*.json")):
            got = json.loads(path.read_text(encoding="utf-8"))
            sug = got["suggestions"]
            medium = [s["page"] for s in sug if s["confidence"] >= 0.6]
            every = [s["page"] for s in sug]
            rows.append({"archetype": name, "variant": path.stem.removeprefix("recover-"), "pages": gold["pages"], "starts": len(gold["starts"]),
                         "mediumPlus": sg.prf(medium, gold["starts"]), "allBands": sg.prf(every, gold["starts"]),
                         "taps": sg.taps_saved(medium, gold["starts"]),
                         "calibration": [(s["confidence"], s["page"] in gold["starts"]) for s in sug]})
    return rows


def cmd_score(args: argparse.Namespace) -> int:
    for r in scores(args):
        m, a = r["mediumPlus"], r["allBands"]
        print(f"{r['archetype']:<16} {r['variant']:<28} medium+ P {m['precision']:.2f} R {m['recall']:.2f} F1 {m['f1']:.2f} | "
              f"all P {a['precision']:.2f} R {a['recall']:.2f} | taps {r['taps']['withSuggestions']} of {r['taps']['withoutSuggestions']}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    rows = scores(args)
    lines = ["# The splitter's suggestions on the made-up gold set", "",
             "| archetype | variant | starts | precision (medium+) | recall (medium+) | F1 | recall (all bands) | taps left |",
             "|---|---|---|---|---|---|---|---|"]
    pooled: list[tuple[float, bool]] = []
    for r in rows:
        m = r["mediumPlus"]
        lines.append(f"| {r['archetype']} | {r['variant']} | {r['starts']} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} | "
                     f"{r['allBands']['recall']:.2f} | {r['taps']['withSuggestions']} of {r['taps']['withoutSuggestions']} |")
        pooled += [tuple(x) for x in r["calibration"]]
    lines += ["", "## Calibration", "", "| band | suggestions | real starts |", "|---|---|---|"]
    for row in sg.calibration(pooled):
        share = "-" if row["realShare"] is None else f"{row['realShare']:.2f}"
        lines.append(f"| {row['band']} | {row['count']} | {share} |")
    lines += ["", "A made-up set: the table shows the pass works on its own examples, not how it fares on a real archive."]
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    for name, fn in (("gold", cmd_gold), ("variants", cmd_variants), ("recover", cmd_recover), ("score", cmd_score), ("report", cmd_report)):
        s = sub.add_parser(name)
        s.add_argument("--cache", required=True)
        s.add_argument("--only", default="")
        if name == "recover":
            s.add_argument("--variants", default="")
            s.add_argument("--without", default="")
        if name == "report":
            s.add_argument("--out", default="")
        s.set_defaults(func=fn)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
