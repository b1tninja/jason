"""``jason preflight FILE|FOLDER``: look at scanned PDFs before they are read, and make a cleaned copy to read.

For each PDF it reports the blank pages (kept in the original, never dropped from it), near-blank pages that are marked
and kept, each page's orientation, skew, resolution, color, and codec, the quality of the scanner's text layer (the share of
its words the English prior doubts), what the file carries (attached files, images, form answers, actions that are
flagged and never run), and what to do: keep the text layer, read pages again, or read the pages that have no text.

Nothing in the original changes. ``--render`` writes the cleaned page images (and ``--pdf`` a PDF of them) to the
renditions store beside the library, ``--ocr`` reads that rendition with Tesseract's tool, and ``--extract`` saves the
attachments and the photographs to the rendition's ``media`` folder, ready for ``jason ingest``. A model is never asked.
docs/pdf-preflight.md has the checks and what was measured.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from jason.commands._shared import data_dir as _data_dir


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser(
        "preflight",
        help="Inspect scanned PDFs before OCR: blank and near-blank pages, rotation, skew, resolution, text-layer quality, "
             "attachments and images; --render writes a cleaned copy beside the library",
        description="Reports what each PDF holds and what to do with it; never changes the original. A blank page is kept "
                    "in the original and left out of the cleaned rendition; a near-blank page (a signature, a stamp, a page "
                    "number, a note that it is left blank) is marked and kept.")
    add_common(p)
    p.add_argument("source", nargs="+", help="a PDF, or a folder of PDFs")
    p.add_argument("--json", action="store_true", help="print the facts as JSON")
    p.add_argument("--no-osd", action="store_true", help="do not ask Tesseract for each page's orientation")
    p.add_argument("--no-media", action="store_true", help="do not list attachments, images, forms, and actions")
    p.add_argument("--no-text-quality", action="store_true", help="do not score the text layer (needs the corpus on disk)")
    p.add_argument("--limit", type=float, default=None, metavar="SHARE",
                   help="the suspect share over which a page is read again (default 0.03)")
    p.add_argument("--jobs", type=int, default=4, help="files read at once")
    p.add_argument("--render", action="store_true", help="write the cleaned page images to the renditions store")
    p.add_argument("--pdf", action="store_true", help="with --render: also a clean.pdf of those images")
    p.add_argument("--variant", default=None, help="the cleaning: auto (default), scanned, smooth, flatten, despeckle, "
                                                  "deskew, stretch, clahe, otsu, sauvola")
    p.add_argument("--native", action="store_true",
                   help="with --render: take a scan's own raster at its true resolution instead of drawing the page")
    p.add_argument("--ocr", action="store_true", help="with --render: read the rendition with Tesseract's tool")
    p.add_argument("--extract", action="store_true", help="save attachments and photographs to the rendition's media folder")
    p.add_argument("--store", default=None, metavar="DIR", help="the renditions store (default: <data>/library/renditions)")
    p.set_defaults(func=run)


def _lexicon(root: Path) -> Any:
    from jason.tasks.ocr_correct import lexicon_for

    lex = lexicon_for(root)
    try:
        import wordfreq  # noqa: F401
    except ImportError:
        if not lex.total:
            return None                 # no corpus and no word list: a share would doubt every word
    return lex


def run(args: argparse.Namespace) -> int:
    from jason.community import pdf_preflight as pf

    root = _data_dir(args)
    files: list[Path] = []
    for s in args.source:
        found = pf.find_pdfs(s)
        if not found:
            print(f"jason preflight: no PDF at {s}", file=sys.stderr)
            return 2
        files += found
    variant = args.variant or pf.DEFAULT_VARIANT
    if variant not in pf.VARIANTS:
        print(f"jason preflight: unknown variant {variant}; choose from {', '.join(pf.VARIANTS)}", file=sys.stderr)
        return 2
    lexicon = None if args.no_text_quality else _lexicon(root)
    results = pf.inspect_many(files, lexicon=lexicon, osd=not args.no_osd, media=not args.no_media, jobs=args.jobs)
    store = Path(args.store) if args.store else root / "library" / "renditions"
    limit = args.limit if args.limit is not None else pf.SHARE_LIMIT
    written: list[str] = []
    for facts in results:
        if facts.locked:
            continue
        if args.render or args.ocr:
            folder = pf.write_rendition(facts, store, variant=variant, pdf=args.pdf, source="native" if args.native else "drawn",
                                        jobs=args.jobs)
            written.append(f"{Path(facts.path).name}: rendition in {folder}")
            if args.ocr:
                try:
                    written.append(f"{Path(facts.path).name}: read into {pf.ocr_rendition(folder)}")
                except RuntimeError as exc:
                    written.append(f"{Path(facts.path).name}: not read: {exc}")
        if args.extract:
            written += _extract(facts, store, pf)
    if args.json:
        print(json.dumps([r.row() for r in results], indent=1))
    else:
        for facts in results:
            print("\n".join(pf.report_lines(facts, limit=limit)))
            print()
        if len(results) > 1:
            print(_totals(results, pf))
        for line in written:
            print(line)
    return 0


def _extract(facts: Any, store: Path, pf: Any) -> list[str]:
    import pymupdf

    from jason.community import pdf_media

    out = []
    with pymupdf.open(facts.path) as doc:
        if doc.needs_pass and not doc.authenticate(""):
            return out
        found, files = pdf_media.carried(doc, facts.sha256)
        folder = pf.rendition_dir(store, facts.sha256) / "media"
        paths = pdf_media.save(folder, found, files, doc)
    if paths:
        out.append(f"{Path(facts.path).name}: {len(paths)} files saved in {folder} (jason ingest {folder} takes them in)")
    return out


def _totals(results: list, pf: Any) -> str:
    pages = [p for r in results for p in r.pages]
    return (f"{len(results)} files, {len(pages)} pages: "
            f"{sum(p.blank is pf.Blank.CONTENT for p in pages)} content, "
            f"{sum(p.blank is pf.Blank.MARKED for p in pages)} marked and kept, "
            f"{sum(p.blank is pf.Blank.BLANK for p in pages)} blank")
