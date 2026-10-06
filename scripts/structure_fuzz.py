"""A benchmark for recovering a document's structure from its PDF alone (docs/structure-recovery.md).

    python scripts/structure_fuzz.py gold --id ID --doc GOOGLE_DOC_ID --cache D:/scratch/jason/structure-fuzz
    python scripts/structure_fuzz.py gold --id ID --outline KEY --data D:/code/jason/data --pdf FILE.pdf --cache ...
    python scripts/structure_fuzz.py gold --id ID --made-up dotted --cache ...
    python scripts/structure_fuzz.py variants --id ID --cache ... [--only clean,image300,dpi150]
    python scripts/structure_fuzz.py recover --id ID --cache ... [--variants ...] [--without size,caps] [--only numbering]
    python scripts/structure_fuzz.py score --id ID --cache ... [--ablate]
    python scripts/structure_fuzz.py report --id ID --cache ... [--out report.md]

``gold`` writes ``CACHE/structure/ID/gold.json`` (``structure_gold``): the Doc's headings with their levels, printed
numbers, and style facts, from the Doc itself (read-only through the Google layer, never opening a browser), or from a
stored outline, or made up. The Doc's PDF export (``source.pdf``) is the paired artifact; where it cannot be fetched
(no stored Google token), ``--pdf`` names one already on disk, else a PDF is drawn from the gold's text.
``variants`` degrades the PDF in controlled steps and records each (``structure_fuzz.VARIANTS``). ``recover`` reads each
variant with the clue rows (``structure_pdf.CLUES``), with any left out or alone. ``score`` and ``report`` compare the
recoveries with the gold. After ``gold`` nothing needs the network. The Tesseract tool reads the image-only variants.

A gold from a real Doc and everything made from it is that association's record: keep ``--cache`` in scratch, and put none
of its contents in a tracked file (counts only).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from jason.community import structure_gold as sg  # noqa: E402
from jason.community import structure_pdf as sp  # noqa: E402
from jason.community import structure_score as sc  # noqa: E402
from jason.community import structure_variants as sv  # noqa: E402


def store(args: argparse.Namespace) -> Path:
    return Path(args.cache) / "structure" / args.id


def cmd_gold(args: argparse.Namespace) -> int:
    folder = store(args)
    folder.mkdir(parents=True, exist_ok=True)
    pdf = folder / "source.pdf"
    style = sg.RenderStyle.flat() if args.style == "flat" else sg.RenderStyle.sized(toc=args.toc, bookmarks=args.bookmarks)
    if args.made_up:
        gold = sg.made_up(articles=args.articles, numbering=args.made_up)
        gold.id = args.id
        sg.render_pdf(gold, pdf, style)
        how = "made up and drawn"
    elif args.outline:
        from jason.community.outlines import DocumentOutline

        raw = json.loads((Path(args.data) / "outlines" / f"{args.outline}.json").read_text(encoding="utf-8"))
        gold = sg.gold_from_outline(DocumentOutline.from_dict(raw), doc_id=args.id)
        if args.pdf:
            pdf.write_bytes(Path(args.pdf).read_bytes())
            how = "stored outline; the PDF on disk"
        else:
            sg.render_pdf(gold, pdf, style)
            how = "stored outline; the PDF drawn from its text"
    else:
        try:
            from jason.agent import Jason

            with Jason(env_file=args.env, interactive=False) as agent:
                docs = agent.drive().docs()
                doc = docs.get(args.doc)
                gold = sg.gold_from_doc(doc, doc_id=args.id)
                try:
                    docs.export_pdf(args.doc, pdf)
                    how = "the Doc; its own PDF export"
                except Exception as exc:  # noqa: BLE001
                    print(f"the PDF export failed ({type(exc).__name__}); using --pdf or a drawn PDF", file=sys.stderr)
                    how = ""
        except Exception as exc:  # noqa: BLE001 - not authorized, offline, or no such Doc: report and stop
            print(f"cannot read the Doc non-interactively: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        if not how:
            if args.pdf:
                pdf.write_bytes(Path(args.pdf).read_bytes())
                how = "the Doc; the PDF on disk"
            else:
                sg.render_pdf(gold, pdf, style)
                how = "the Doc; a PDF drawn from its text"
    missing = sg.pair_pages(gold, pdf)
    path = sg.save(gold, Path(args.cache) / "structure")
    heads = gold.headings()
    levels = {}
    for h in heads:
        levels[h.level] = levels.get(h.level, 0) + 1
    print(f"gold {gold.id}: {len(heads)} headings by level {dict(sorted(levels.items()))}, "
          f"{sum(1 for h in heads if h.number)} numbered, {len(gold.parts)} parts, {gold.pages} pages; "
          f"{missing} headings not found in the PDF; {how}")
    print(f"wrote {path} and {pdf}")
    return 0


def cmd_variants(args: argparse.Namespace) -> int:
    folder = store(args)
    source = folder / "source.pdf"
    if not source.is_file():
        print(f"no {source}: run gold first", file=sys.stderr)
        return 1
    names = args.only.split(",") if args.only else None
    records = sv.make_all(source, folder / "variants", names, seed=args.seed)
    if names:                                           # keep the records of the variants not remade
        path = folder / "variants" / "variants.json"
        old = {r["name"]: r for r in json.loads(path.read_text(encoding="utf-8"))} if path.is_file() else {}
        for r in records:
            old[r.name] = r.to_dict()
        path.write_text(json.dumps(list(old.values()), indent=1), encoding="utf-8")
    for r in records:
        for stale in [*(folder / "ocr").glob(f"{r.name}.*_p*.json"), *(folder / "lines").glob(f"{r.name}.*.json")]:
            stale.unlink(missing_ok=True)
        print(f"{r.name:9s} {r.pages:3d} pages  {'image ' + str(r.dpi) + ' dpi' if r.image_only else 'text layer'}  {r.note}")
    return 0


def records_of(args: argparse.Namespace, names: str | None = None) -> list[sv.VariantRecord]:
    raw = json.loads((store(args) / "variants" / "variants.json").read_text(encoding="utf-8"))
    names = names or getattr(args, "variants", None)
    wanted = names.split(",") if names else None
    return [sv.VariantRecord.from_dict(r) for r in raw if wanted is None or r["name"] in wanted]


def read_lines(args: argparse.Namespace, record: sv.VariantRecord) -> dict:
    """The lines of one variant (the text layer's, or Tesseract's words for an image-only page), cached under the store."""
    import pymupdf

    folder = store(args)
    mode = args.preflight
    cached = folder / "lines" / f"{record.name}.{mode}.json"
    if cached.is_file() and not args.reread:
        return json.loads(cached.read_text(encoding="utf-8"))
    words_dir = folder / "ocr"
    words_dir.mkdir(parents=True, exist_ok=True)

    def words_of(number, page):
        from jason.community.ocr import TesseractCli, TesseractWord

        path = words_dir / f"{record.name}.{mode}_p{number}.json"
        if path.is_file():
            return [TesseractWord(*w) for w in json.loads(path.read_text(encoding="utf-8"))], record.dpi
        tool = TesseractCli(dpi=record.dpi)
        if mode == "auto":                      # the preflight's own cleaning (shading, dust, tilt) before the reading
            import tempfile

            from PIL import Image

            from jason.community.pdf_preflight import apply_variant

            from jason.community import pdf_preflight as pf

            drawn = sv.draw(page, record.dpi)
            if pf.classify_blank(pf.ink_of(drawn, record.dpi), "")[0] is pf.Blank.BLANK:
                path.write_text("[]", encoding="utf-8")        # a blank back, and its show-through, is not read
                return [], record.dpi
            gray, _ = apply_variant(drawn, "auto", record.dpi)
            with tempfile.TemporaryDirectory() as tmp:
                png = Path(tmp) / "page.png"
                Image.fromarray(gray).save(png, dpi=(record.dpi, record.dpi))
                words = tool.image_words(png, number)
        else:
            words = tool.page_words(page, number)
        words = sp.with_band(words, page, number, record.dpi)
        path.write_text(json.dumps([[w.page, w.block, w.paragraph, w.line, w.left, w.top, w.width, w.height, w.confidence,
                                      w.text] for w in words]), encoding="utf-8")
        return words, record.dpi

    with pymupdf.open(folder / "variants" / record.file) as doc:
        if record.image_only and args.jobs > 1:                  # read the pages together; the cache keeps the words
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(args.jobs) as pool:
                list(pool.map(lambda i: words_of(i + 1, doc[i]), range(doc.page_count)))
        lines, sources = sp.extract_lines(doc, words_of=words_of if record.image_only else None)
        toc = doc.get_toc(simple=True)
        pages = doc.page_count
    parts = sp.find_parts(lines, pages, toc)
    data = {"lines": [ln.to_dict() for ln in lines], "sources": sources, "toc": toc, "pages": pages, "parts": parts}
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(data), encoding="utf-8")
    return data


def run_recovery(data: dict, *, clues=None, min_score: float = sp.MIN_SCORE) -> sp.Recovery:
    lines = [sp.PLine.from_dict(d) for d in data["lines"]]
    return sp.recover(lines, data["pages"], toc=data["toc"], clues=clues, min_score=min_score, sources=data["sources"],
                      marks=data["parts"])


def cmd_recover(args: argparse.Namespace) -> int:
    folder = store(args)
    clues = None
    if args.only:
        clues = args.only.split(",")
    elif args.without:
        gone = set(args.without.split(","))
        clues = [c.name for c in sp.CLUES if c.name not in gone]
    for record in records_of(args):
        data = read_lines(args, record)
        rec = run_recovery(data, clues=clues, min_score=args.min_score)
        out = folder / "recovered" / record.name
        out.mkdir(parents=True, exist_ok=True)
        (out / "default.json").write_text(json.dumps(rec.to_dict(), indent=1), encoding="utf-8")
        likely = sum(1 for n in rec.nodes if n.tier == "likely")
        print(f"{record.name:9s} {len(rec.nodes):4d} headings ({likely} likely), {len(rec.findings)} findings, "
              f"sources {dict((s, data['sources'].count(s)) for s in set(data['sources']))}")
    return 0


def labels_of(args: argparse.Namespace) -> dict[int, str]:
    clean = next(iter(records_of(args, "clean")), None)
    return run_recovery(read_lines(args, clean)).labels if clean else {}


def score_all(args: argparse.Namespace, *, ablate: bool) -> dict:
    gold = sg.load(Path(args.cache) / "structure", args.id)
    labels = labels_of(args)
    results: dict[str, dict] = {}
    configs = sc.ablation_configs() if ablate else [{"name": "all", "clues": None, "min_score": sp.MIN_SCORE}]
    for record in records_of(args):
        data = read_lines(args, record)
        results[record.name] = {}
        for cfg in configs:
            rec = run_recovery(data, clues=cfg["clues"], min_score=cfg["min_score"])
            results[record.name][cfg["name"]] = sc.score(gold, record, rec, labels=labels, samples=args.samples)
        base = run_recovery(data)
        results[record.name]["_findings"] = {k: sum(1 for f in base.findings if f["kind"] == k)
                                             for k in sorted({f["kind"] for f in base.findings})}
        results[record.name]["_toc"] = base.toc
    path = store(args) / "scores.json"
    path.write_text(json.dumps(results, indent=1), encoding="utf-8")
    return results


def pct(v) -> str:
    return "-" if v is None else f"{100 * v:5.1f}"


def cmd_score(args: argparse.Namespace) -> int:
    results = score_all(args, ablate=args.ablate)
    print(f"{'variant':9s} {'gold':>4s} {'rec':>4s} {'P':>5s} {'R':>5s} {'F1':>5s}  95% interval  {'lvl':>5s} {'num':>5s} {'par':>5s} {'part':>5s} {'pgno':>5s}")
    for name, cfgs in results.items():
        s = cfgs["all"]
        print(f"{name:9s} {s['findable']:4d} {s['recovered']:4d} {pct(s['precision'])} {pct(s['recall'])} {pct(s['f1'])}  "
              f"[{pct(s['f1_lo'])},{pct(s['f1_hi'])}]  {pct(s['level_exact'])} {pct(s['number_roundtrip'])} "
              f"{pct(s['parent_correct'])} {pct(s['part_f1'])} {pct(s['page_numbers'])}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    results = score_all(args, ablate=True)
    lines = [f"# Structure recovery: {args.id}", "", "Counts and rates only; no words of the document.", "",
             "## By variant (all clues)", "",
             "| variant | gold | recovered | P | R | F1 | 95% | level | number | parent | parts | page no. | likely P | suggested P |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, cfgs in results.items():
        s = cfgs["all"]
        lines.append(f"| {name} | {s['findable']} | {s['recovered']} | {pct(s['precision'])} | {pct(s['recall'])} | {pct(s['f1'])} | "
                     f"{pct(s['f1_lo'])}-{pct(s['f1_hi'])} | {pct(s['level_exact'])} | {pct(s['number_roundtrip'])} | "
                     f"{pct(s['parent_correct'])} | {pct(s['part_f1'])} | {pct(s['page_numbers'])} | "
                     f"{pct(s['likely_precision'])} | {pct(s['suggested_precision'])} |")
    names = list(results)
    lines += ["", "## What each clue is worth: F1 lost when the clue is left out (percentage points)", "",
              "| clue | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for c in (c for c in sp.CLUES):
        row = [f"{100 * (results[n]['all']['f1'] - results[n][f'without {c.name}']['f1']):+.1f}" for n in names]
        lines.append(f"| {c.name} | " + " | ".join(row) + " |")
    lines += ["", "## Each clue alone: F1", "", "| clue | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for c in (c for c in sp.CLUES if c.votes):
        lines.append(f"| {c.name} | " + " | ".join(pct(results[n][f"only {c.name}"]["f1"]) for n in names) + " |")
    lines += ["", "## Clues added in order of cost: F1", "", "| added | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for cfg in sc.ablation_configs():
        if cfg["name"].startswith("cost order"):
            lines.append(f"| {cfg['name'][12:]} | " + " | ".join(pct(results[n][cfg['name']]["f1"]) for n in names) + " |")
    if "clean" in results:
        lines += ["", "## Text layer against OCR: F1 of the full reader", ""]
        base = results["clean"]["all"]["f1"]
        for n in names:
            if n != "clean":
                lines.append(f"- {n}: {pct(results[n]['all']['f1'])} ({100 * (results[n]['all']['f1'] - base):+.1f} points against the clean text layer)")
    lines += ["", "## Findings of the reader (counts)", ""]
    for n in names:
        lines.append(f"- {n}: {results[n]['_findings']}; contents {results[n]['_toc']}")
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--id", required=True, help="the benchmark's name for the document")
        sp.add_argument("--cache", default="D:/scratch/jason/structure-fuzz", help="where everything is written")

    g = sub.add_parser("gold", help="the Doc's structure and its paired PDF")
    common(g)
    g.add_argument("--doc", help="a Google Doc id (read-only)")
    g.add_argument("--outline", help="a stored outline's key (with --data)")
    g.add_argument("--data", default="data")
    g.add_argument("--pdf", help="a PDF already on disk to pair")
    g.add_argument("--made-up", choices=("dotted", "article", "rules"), help="a made-up document")
    g.add_argument("--articles", type=int, default=6)
    g.add_argument("--style", choices=("sized", "flat"), default="sized", help="how a drawn PDF sets its headings")
    g.add_argument("--toc", action="store_true", help="a drawn PDF has a contents page")
    g.add_argument("--bookmarks", action="store_true", help="a drawn PDF has bookmarks")
    g.add_argument("--env", default=None)
    g.set_defaults(fn=cmd_gold)

    v = sub.add_parser("variants", help="degraded copies of the paired PDF, each recorded")
    common(v)
    v.add_argument("--only", help="comma-separated variant names (default: all)")
    v.add_argument("--seed", type=int, default=11)
    v.set_defaults(fn=cmd_variants)

    def reading(sp_: argparse.ArgumentParser) -> None:
        common(sp_)
        sp_.add_argument("--variants", help="comma-separated variant names (default: all)")
        sp_.add_argument("--jobs", type=int, default=4, help="pages read by Tesseract at once")
        sp_.add_argument("--reread", action="store_true", help="read the lines again, not from the cache")
        sp_.add_argument("--preflight", choices=("none", "auto"), default="none",
                         help="clean each image page (the preflight's auto variant) before the OCR reads it")

    r = sub.add_parser("recover", help="read each variant's headings with the clue rows")
    reading(r)
    r.add_argument("--without", help="comma-separated clues to leave out")
    r.add_argument("--only", help="comma-separated clues to use alone")
    r.add_argument("--min-score", type=float, default=sp.MIN_SCORE)
    r.set_defaults(fn=cmd_recover)

    s_ = sub.add_parser("score", help="the recoveries against the gold")
    reading(s_)
    s_.add_argument("--ablate", action="store_true", help="also each clue left out and alone")
    s_.add_argument("--samples", type=int, default=1000, help="bootstrap resamples")
    s_.set_defaults(fn=cmd_score)

    rp = sub.add_parser("report", help="a Markdown report: by variant, by clue, text against OCR")
    reading(rp)
    rp.add_argument("--samples", type=int, default=1000)
    rp.add_argument("--out")
    rp.set_defaults(fn=cmd_report)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
