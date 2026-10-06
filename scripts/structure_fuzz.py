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
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
