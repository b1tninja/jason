"""Offline benchmarks for the scan pipeline: no network, no model server, nothing written outside --cache.

    python scripts/bench_offline.py ocr --pdf SCAN.pdf --reference TEXT.txt --cache D:/scratch/jason/bench
    python scripts/bench_offline.py ocr --pdf SCAN.pdf --reference TEXT.txt --cache ... \\
        --variants scanned,auto,smooth,otsu --dpi 150,200,300 --pages 1-40 --jobs 6
    python scripts/bench_offline.py blank --labels LABELS.json --cache ...
    python scripts/bench_offline.py throughput --source FOLDER --cache ... --jobs 6
    python scripts/bench_offline.py segments --gold data/library/segments-gold.json --cache ...

``ocr`` draws each page, applies each preprocessing variant (``pdf_preflight.VARIANTS``) at each resolution, reads it
with Tesseract's own tool, and scores the reading against a reference text you supply (a hand-kept copy, or a clean
export of the same document): word error rate and character error rate over the whole reading, the words wrong that the
variant added and removed against the first variant (the baseline), the pages it made better and worse, and a 95%
interval for the change in WER from resampling pages. Each page's reading is cached by file hash, variant, resolution,
and page, so a rerun only scores, and a new variant only reads its own pages.

``blank`` scores the blank-page detector against labels: ``{"FILE.pdf": {"3": "blank", "7": "marked"}}`` (1-based pages;
``blank``, ``marked``, ``content``), and prints the confusion matrix with precision and recall of ``blank``.
``throughput`` times the preflight over a folder: pages a second, and what it found. ``segments`` scores the rules
reader of the document segmentation against a gold file (``scripts/measure_segments.py``; the model readers need a
server, so they are left to that script).

The scoring is an approximation made to be repeatable, not a reference implementation: tokens are split on white space
and aligned by a banded word-level edit distance (a word added, missing, or different is one edit). Compare variants with
each other, not with a figure scored another way. The reference and the readings are the association's records or
derived from them: keep ``--cache`` in a scratch folder, and put none of its contents in a tracked file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Sequence

SAMPLES = 2000                                   # bootstrap resamples


# --- Scoring --------------------------------------------------------------------------------------------------------


def tokens(text: str) -> list[str]:
    return text.split()


BAND = 200                                       # words the alignment may drift between reference and reading


def edits(reference: Sequence[str], reading: Sequence[str], band: int = BAND
          ) -> tuple[int, list[tuple[int, int]], list[tuple[str, str]]]:
    """Edits (word-level Levenshtein, a banded alignment) to turn the reference into the reading; for each differing
    block, the reading token where it falls and its edits; and the blocks as (reference words, reading words)."""
    n, m = len(reference), len(reading)
    width = max(band, abs(n - m) + 50)
    INF = 1 << 30
    prev = {j: j for j in range(0, min(m, width) + 1)}
    steps: list[bytearray] = []                  # per reference word: the move that reached each cell of the band
    for i in range(1, n + 1):
        lo, hi = max(0, i - width), min(m, i + width)
        cur: dict[int, int] = {}
        move = bytearray(hi - lo + 1)
        ref = reference[i - 1]
        for j in range(lo, hi + 1):
            best, how = INF, 0
            if j > 0 and (j - 1) in prev:        # diagonal: a match or a substitution
                best = prev[j - 1] + (0 if ref == reading[j - 1] else 1)
                how = 1 if ref == reading[j - 1] else 2
            if j in prev and prev[j] + 1 < best:   # the reference word is missing from the reading
                best, how = prev[j] + 1, 3
            if (j - 1) in cur and cur[j - 1] + 1 < best:   # the reading has a word the reference lacks
                best, how = cur[j - 1] + 1, 4
            cur[j] = best
            move[j - lo] = how
        steps.append(move)
        prev = cur
    i, j = n, m
    ops: list[tuple[int, int, int]] = []          # (move, reference index, reading index), from the end
    while i > 0 or j > 0:
        if i == 0:
            how = 4
        else:
            lo = max(0, i - width)
            how = steps[i - 1][j - lo] if lo <= j <= min(m, i + width) else 4
        ops.append((how, i - 1, j - 1))
        if how in (1, 2):
            i, j = i - 1, j - 1
        elif how == 3:
            i -= 1
        else:
            j -= 1
    ops.reverse()
    total = 0
    where: list[tuple[int, int]] = []
    blocks: list[tuple[str, str]] = []
    run: list[tuple[int, int, int]] = []

    def close() -> None:
        nonlocal total
        if not run:
            return
        said = [reference[r] for h, r, _ in run if h in (2, 3)]
        read = [reading[c] for h, _, c in run if h in (2, 4)]
        n_edits = sum(h != 1 for h, _, _ in run)
        total += n_edits
        first = next((c for _, _, c in run if c >= 0), 0)
        where.append((min(first, max(m - 1, 0)), n_edits))
        blocks.append((" ".join(said), " ".join(read)))
        run.clear()

    for op in ops:
        if op[0] == 1:
            close()
        else:
            run.append(op)
    close()
    return total, where, blocks


def char_edits(blocks: Sequence[tuple[str, str]]) -> int:
    """Character edits inside the differing blocks of the word alignment (the matched words add none)."""
    total = 0
    for a, b in blocks:
        row = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(row[j] + 1, cur[j - 1] + 1, row[j - 1] + (ca != cb)))
            row = cur
        total += row[-1]
    return total


def per_page(where: list[tuple[int, int]], page_of: Sequence[int], pages: Sequence[int]) -> dict[int, int]:
    out = {p: 0 for p in pages}
    for j, n in where:
        if page_of:
            out[page_of[min(j, len(page_of) - 1)]] += n
    return out


def interval(deltas: list[tuple[float, float]], words: list[int], seed: int = 1) -> tuple[float, float]:
    """A 95% interval for the change in WER (points) from resampling pages: ``deltas`` are each page's (edits now, edits
    at baseline) and ``words`` its reading's tokens."""
    rnd = random.Random(seed)
    n = len(deltas)
    out = []
    for _ in range(SAMPLES):
        pick = [rnd.randrange(n) for _ in range(n)]
        w = sum(words[i] for i in pick) or 1
        out.append(100 * sum(deltas[i][0] - deltas[i][1] for i in pick) / w)
    out.sort()
    return out[int(0.025 * SAMPLES)], out[int(0.975 * SAMPLES)]


# --- Reading -----------------------------------------------------------------------------------------------------------


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_page(job: tuple) -> tuple[int, str]:
    """One page, drawn, prepared by a variant, and read by Tesseract (a worker: top-level, so it can be spawned)."""
    pdf, index, variant, dpi, cache_file = job
    import pymupdf

    from jason.community import pdf_preflight as pf
    from jason.community.ocr import TesseractCli

    with pymupdf.open(pdf) as doc:
        drawn = pf.draw_gray(doc, index, dpi)
        gray, _ = pf.apply_variant(drawn.gray, variant, dpi)
    with tempfile.TemporaryDirectory() as tmp:
        image = Path(tmp) / "page.png"
        pf._save_png(image, gray, int(dpi))
        words = TesseractCli(dpi=int(dpi)).image_words(image, index)
    text = " ".join(w.text for w in words)
    Path(cache_file).write_text(text, encoding="utf-8")
    return index, text


def read_pages(pdf: Path, sha: str, variant: str, dpi: int, pages: Sequence[int], cache: Path, jobs: int) -> dict[int, str]:
    folder = cache / "readings" / sha[:16] / f"{variant}-{dpi}"
    folder.mkdir(parents=True, exist_ok=True)
    out: dict[int, str] = {}
    todo = []
    for p in pages:
        f = folder / f"{p}.txt"
        if f.is_file():
            out[p] = f.read_text(encoding="utf-8")
        else:
            todo.append((str(pdf), p, variant, dpi, str(f)))
    if todo:
        if jobs > 1:
            with ProcessPoolExecutor(max_workers=jobs) as pool:
                for index, text in pool.map(_read_page, todo, chunksize=2):
                    out[index] = text
        else:
            for job in todo:
                index, text = _read_page(job)
                out[index] = text
    return out


def page_range(spec: str, count: int) -> list[int]:
    """0-based pages from "1-40,45" (1-based); empty is every page."""
    if not spec:
        return list(range(count))
    pages: list[int] = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        lo, hi = int(a), int(b or a)
        pages += [p - 1 for p in range(lo, hi + 1) if 1 <= p <= count]
    return pages


# --- Suites ------------------------------------------------------------------------------------------------------------


def suite_ocr(args: argparse.Namespace) -> int:
    import pymupdf

    from jason.community import pdf_preflight as pf
    from jason.community.ocr import TesseractCli

    if not TesseractCli.available():
        print("Tesseract's command-line tool is not installed (or TESSERACT_EXE is not set).", file=sys.stderr)
        return 2
    pdf = Path(args.pdf)
    reference = tokens(Path(args.reference).read_text(encoding="utf-8", errors="replace"))
    reference_text = " ".join(reference)
    with pymupdf.open(pdf) as doc:
        pages = page_range(args.pages, doc.page_count)
    sha = sha256_of(pdf)
    variants = [v for v in args.variants.split(",") if v]
    unknown = [v for v in variants if v not in pf.VARIANTS]
    if unknown:
        print(f"unknown variants: {', '.join(unknown)}; known: {', '.join(pf.VARIANTS)}", file=sys.stderr)
        return 2
    dpis = [int(d) for d in args.dpi.split(",") if d]
    runs = [(v, d) for d in dpis for v in variants]
    base = runs[0]
    results: dict[tuple[str, int], dict[str, Any]] = {}
    for variant, dpi in runs:
        t0 = time.time()
        readings = read_pages(pdf, sha, variant, dpi, pages, Path(args.cache), args.jobs)
        page_of: list[int] = []
        toks: list[str] = []
        for p in pages:
            t = tokens(readings.get(p, ""))
            toks += t
            page_of += [p] * len(t)
        total, where, blocks = edits(reference, toks)
        results[(variant, dpi)] = {
            "tokens": toks, "page_of": page_of, "edits": total, "where": where, "blocks": blocks,
            "wer": 100 * total / max(len(reference), 1),
            "cer": 100 * char_edits(blocks) / max(len(reference_text), 1),
            "seconds": time.time() - t0, "page_words": Counter(page_of)}
    baseline = results[base]
    base_pages = per_page(baseline["where"], baseline["page_of"], pages)
    rows = []
    for key, r in results.items():
        mine = per_page(r["where"], r["page_of"], pages)
        better = sum(mine[p] < base_pages[p] for p in pages)
        worse = sum(mine[p] > base_pages[p] for p in pages)
        base_wrong = Counter(b for _, b in baseline["blocks"])
        now_wrong = Counter(b for _, b in r["blocks"])
        added = sum((now_wrong - base_wrong).values())
        removed = sum((base_wrong - now_wrong).values())
        row = {"variant": key[0], "dpi": key[1], "wer": round(r["wer"], 2), "cer": round(r["cer"], 2),
               "added": added, "removed": removed, "pages_better": better, "pages_worse": worse,
               "seconds": round(r["seconds"], 1)}
        if key != base:
            lo, hi = interval([(mine[p], base_pages[p]) for p in pages], [r["page_words"][p] for p in pages])
            row["delta"] = round(r["wer"] - baseline["wer"], 2)
            row["ci95"] = [round(lo, 2), round(hi, 2)]
        rows.append(row)
    if args.json:
        print(json.dumps({"reference_words": len(reference), "pages": len(pages), "baseline": f"{base[0]}@{base[1]}",
                          "rows": rows}, indent=1))
        return 0
    print(f"{len(pages)} pages, {len(reference)} reference words, baseline {base[0]} at {base[1]} dpi")
    print(f"{'variant':<11}{'dpi':>5}{'WER%':>8}{'CER%':>7}{'delta':>8}{'95% interval':>16}{'+wrong':>8}{'-wrong':>8}"
          f"{'better':>8}{'worse':>7}{'sec':>7}")
    for r in rows:
        d = f"{r['delta']:+.2f}" if "delta" in r else ""
        ci = f"({r['ci95'][0]:+.2f},{r['ci95'][1]:+.2f})" if "ci95" in r else ""
        print(f"{r['variant']:<11}{r['dpi']:>5}{r['wer']:>8.2f}{r['cer']:>7.2f}{d:>8}{ci:>16}{r['added']:>8}"
              f"{r['removed']:>8}{r['pages_better']:>8}{r['pages_worse']:>7}{r['seconds']:>7.1f}")
    return 0


def suite_blank(args: argparse.Namespace) -> int:
    import pymupdf

    from jason.community import pdf_preflight as pf

    labels: dict[str, dict[str, str]] = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    base = Path(args.labels).parent
    kinds = ("blank", "marked", "content")
    matrix: dict[tuple[str, str], int] = Counter()
    harmed: list[str] = []
    for name, pages in labels.items():
        path = Path(name) if Path(name).is_absolute() else base / name
        with pymupdf.open(path) as doc:
            for number, eye in pages.items():
                facts, _ = pf.inspect_page(doc, int(number) - 1, osd=False)
                got = facts.blank.value
                matrix[(got, eye)] += 1
                if got == "blank" and eye != "blank":
                    harmed.append(f"{Path(name).name} p{number}")
    print(f"{'detector \\ eye':<16}" + "".join(f"{k:>9}" for k in kinds))
    for got in kinds:
        print(f"{got:<16}" + "".join(f"{matrix[(got, k)]:>9}" for k in kinds))
    called = sum(matrix[("blank", k)] for k in kinds)
    truth = sum(matrix[(g, "blank")] for g in kinds)
    right = matrix[("blank", "blank")]
    print(f"blank: precision {right}/{called}" + (f" = {right / called:.3f}" if called else "")
          + f", recall {right}/{truth}" + (f" = {right / truth:.3f}" if truth else ""))
    print(f"pages with a mark called blank: {len(harmed)}" + (": " + ", ".join(harmed[:20]) if harmed else ""))
    return 1 if harmed else 0


def suite_throughput(args: argparse.Namespace) -> int:
    from jason.community import pdf_preflight as pf

    paths = pf.find_pdfs(args.source)
    if args.limit:
        paths = paths[:args.limit]
    t0 = time.time()
    facts = pf.inspect_many(paths, jobs=args.jobs, osd=not args.no_osd, media=False)
    seconds = time.time() - t0
    pages = sum(len(f.pages) for f in facts)
    kinds = Counter(p.blank.value for f in facts for p in f.pages)
    print(f"{len(facts)} files, {pages} pages in {seconds:.1f} s: {pages / max(seconds, 1e-9):.1f} pages a second "
          f"({args.jobs} jobs, OSD {'off' if args.no_osd else 'on'})")
    print("pages: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
    return 0


def suite_segments(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import measure_segments

    argv = ["--gold", args.gold, "--cache", str(Path(args.cache) / "segments"), "--variants", "rules"]
    if args.split != "all":
        argv += ["--split", args.split]
    return measure_segments.main(argv)


def main(argv: list[str] | None = None) -> int:
    from jason.config import apply_temp_dir_or_exit

    apply_temp_dir_or_exit()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", required=True, help="a scratch folder (never under AppData or the working directory)")
    sub = ap.add_subparsers(dest="suite", required=True)
    o = sub.add_parser("ocr", help="preprocessing variants and resolutions, scored against a reference text")
    o.add_argument("--pdf", required=True)
    o.add_argument("--reference", required=True, help="the document's text, as a file")
    o.add_argument("--variants", default="scanned,auto,smooth,otsu", help="the first is the baseline")
    o.add_argument("--dpi", default="300", help="resolutions to draw at, a list: 150,200,300")
    o.add_argument("--pages", default="", help="1-based pages, e.g. 1-40,45 (every page when empty)")
    o.add_argument("--jobs", type=int, default=4)
    o.add_argument("--json", action="store_true")
    o.set_defaults(run=suite_ocr)
    b = sub.add_parser("blank", help="the blank-page detector against labels")
    b.add_argument("--labels", required=True)
    b.set_defaults(run=suite_blank)
    t = sub.add_parser("throughput", help="preflight speed over a folder")
    t.add_argument("--source", required=True)
    t.add_argument("--jobs", type=int, default=4)
    t.add_argument("--limit", type=int, default=0)
    t.add_argument("--no-osd", action="store_true")
    t.set_defaults(run=suite_throughput)
    s = sub.add_parser("segments", help="the segmentation rules against a gold file")
    s.add_argument("--gold", required=True)
    s.add_argument("--split", default="all", choices=["all", "dev", "held-out"])
    s.set_defaults(run=suite_segments)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    Path(args.cache).mkdir(parents=True, exist_ok=True)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
