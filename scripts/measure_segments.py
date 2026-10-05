"""Score document segmentation against hand-labeled files (a private gold JSON under data/library/).

    python scripts/measure_segments.py --gold data/library/segments-gold.json --cache D:/scratch/jason/segments/measure
    python scripts/measure_segments.py ... --split held-out -v          # one split, with each missed and extra boundary
    python scripts/measure_segments.py ... --model qwen3.5:9b           # ask the vision model for each page not cached
    python scripts/measure_segments.py ... --variants rules,model,agree,union
    python scripts/measure_segments.py ... --set title-block=1.2 --threshold 1.0   # try a different weight

The gold file is ``{"files": [{"path", "split", "boundaries", "maybe", "window", "parts"}]}``: the pages that start a
document (1-based, a page with words), ambiguous pages (a prediction there counts neither way), a window of pages that
were labeled, and the parts ``{title, start, end}``. ``--cache`` is required: the pages read from each PDF and each
model reading are kept there (a scratch folder, never under AppData or the working directory), so a rerun only scores.
A model request holds the GPU lock and runs ``jason.local_ai.preflight`` first; ``--unload`` releases the model after.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from jason.community.document_segments import VERSION, PageInfo
from jason.tasks import segments as task


def _key(path: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in path)[-90:]


def main(argv: list[str] | None = None) -> int:
    from jason.config import apply_temp_dir_or_exit

    apply_temp_dir_or_exit()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--cache", required=True, help="a scratch folder for the pages read and the model's readings")
    ap.add_argument("--split", default="all", choices=["all", "dev", "held-out"])
    ap.add_argument("--variants", default="rules")
    ap.add_argument("--model", default="", help="the vision model to ask where a page's reading is not cached")
    ap.add_argument("--pair", action="store_true", help="show the model the page before as well")
    ap.add_argument("--dpi", type=int, default=72)
    ap.add_argument("--threshold", type=float, default=task.THRESHOLD)
    ap.add_argument("--model-threshold", type=float, default=task.MODEL_THRESHOLD)
    ap.add_argument("--set", action="append", default=[], help="a cue weight, key=value; repeatable")
    ap.add_argument("--embed", action="store_true", help="read the embedder's cosines (qwen3-embedding) where not cached")
    ap.add_argument("--moves", action="store_true", help="also ask the model each move as a closed choice (needs --model)")
    ap.add_argument("--only", action="append", default=[], help="score only files whose path holds this text; repeatable")
    ap.add_argument("--refresh", action="store_true", help="read the pages again")
    ap.add_argument("--unload", action="store_true", help="unload the model when done")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    cache = Path(args.cache)
    (cache / "pages").mkdir(parents=True, exist_ok=True)
    (cache / "model").mkdir(parents=True, exist_ok=True)
    files = task.gold_pages(Path(args.gold))
    if args.only:
        files = [f for f in files if any(o in f["path"] for o in args.only)]
    weights = {k: float(v) for k, v in (item.split("=", 1) for item in args.set)}
    mode = f"{'pair' if args.pair else 'single'}-{args.dpi}"
    variants = [v for v in args.variants.split(",") if v]

    def pages_for(f):
        target = cache / "pages" / (_key(f["path"]) + ".json")
        if target.is_file() and not args.refresh:
            raw = json.loads(target.read_text(encoding="utf-8"))
            if raw.get("version") == VERSION:
                return [PageInfo.from_dict(p) for p in raw["pages"]], raw["toc"]
        pages, toc = task.read_pages(Path(f["path"]))
        target.write_text(json.dumps({"version": VERSION, "toc": toc, "pages": [p.to_dict() for p in pages]}), encoding="utf-8")
        return pages, toc

    reader = None
    if args.model:
        from jason.local_ai import preflight

        preflight(args.model)
        reader = task.OllamaPageReader(model=args.model, dpi=args.dpi, pair=args.pair)

    seconds = {"pages": 0, "n": 0}

    def model_for(f):
        target = cache / "model" / (_key(f["path"]) + f".{(args.model or 'none').replace(':', '-')}.{mode}.json")
        if target.is_file():
            return {int(k): v for k, v in json.loads(target.read_text(encoding="utf-8")).items()}
        if reader is None:
            return None
        pages, _ = pages_for(f)
        started = time.monotonic()
        got = task.read_model(Path(f["path"]), pages, reader)
        seconds["pages"] += time.monotonic() - started
        seconds["n"] += len([p for p in pages if not p.blank]) - 1
        target.write_text(json.dumps(got), encoding="utf-8")
        return got

    embedder = None
    (cache / "embed").mkdir(parents=True, exist_ok=True)

    def embeddings_for(f):
        target = cache / "embed" / (_key(f["path"]) + ".json")
        if target.is_file():
            return {int(k): v for k, v in json.loads(target.read_text(encoding="utf-8")).items()}
        if not args.embed:
            return None
        nonlocal embedder
        if embedder is None:
            from jason.community.retrieval import OllamaEmbedder

            embedder = OllamaEmbedder()
        pages, _ = pages_for(f)
        got = task.read_embeddings(pages, embedder)
        target.write_text(json.dumps(got), encoding="utf-8")
        return got

    result = task.evaluate(files, pages_for, embeddings_for=embeddings_for if any(v in variants for v in ("embed", "rules+embed", "all3")) else None, variants=variants, model_for=model_for if ("model" in variants or "agree" in variants
                                                                                      or "union" in variants) else None,
                           split=args.split, threshold=args.threshold, model_threshold=args.model_threshold,
                           weights=weights or None)
    if args.moves and reader is not None:
        total: dict[str, int] = {}
        for f in task.gold_pages(Path(args.gold)):
            if args.split != "all" and f.get("split") != args.split or f.get("boundaries") is None:
                continue
            if args.only and not any(o in f["path"] for o in args.only):
                continue
            pages, _ = pages_for(f)
            target = cache / "model" / (_key(f["path"]) + f".{args.model.replace(':', '-')}.moves-{args.dpi}.json")
            if target.is_file():
                probs = {int(k): v for k, v in json.loads(target.read_text(encoding="utf-8")).items()}
            else:
                segs, moves = task.variant_tree(pages, "rules")
                started = time.monotonic()
                probs = task.read_moves(Path(f["path"]), pages, segs, moves, reader)
                seconds["moves"] = seconds.get("moves", 0.0) + time.monotonic() - started
                seconds["movesn"] = seconds.get("movesn", 0) + len(probs)
                target.write_text(json.dumps(probs), encoding="utf-8")
            for k, v in task.evaluate_moves(f, pages, probs).items():
                total[k] = total.get(k, 0) + v
        if total:
            print(f"moves ({args.split}): {total['moves']} rule moves, {total['labeled']} at labeled pages; rules right "
                  f"{total['rules_right']}; model asked {total['asked']}, right {total['model_right']}; model and rules name the "
                  f"same move {total['agree']} times, right {total['agree_right']}")
            if seconds.get("movesn"):
                print(f"closed choice: {seconds['moves'] / seconds['movesn']:.2f} s a move over {seconds['movesn']} moves")
    if args.unload and args.model:
        from jason.local_ai import unload

        unload(args.model)
    if args.json:
        print(json.dumps(result, indent=1, default=list))
        return 0
    print(f"split {args.split}; threshold {args.threshold}; model threshold {args.model_threshold}; cue version {VERSION}")
    for v, row in result["variants"].items():
        e, n = row["exact"], row["near"]
        print(f"{v:6s} {row['files']:2d} files, {e['gold']} labeled starts (first pages left out): exact P {e['precision']:.3f} "
              f"R {e['recall']:.3f} F1 {e['f1']:.3f} | within one page P {n['precision']:.3f} R {n['recall']:.3f} F1 {n['f1']:.3f}"
              f"  (predicted {e['predicted']})")
    if seconds["n"]:
        print(f"model: {seconds['pages'] / seconds['n']:.2f} s a page over {seconds['n']} pages")
    for v, n in result.get("nesting", {}).items():
        print(f"nesting {v}: {n['gold']} labeled nested documents in {n['files']} files: found {n['found']}, right parent "
              f"{n['parent']}, right end {n['end']}, {n['extra']} extra nested; resumes {n['popped']} of {n['resumes']} popped "
              f"at the right page, {n['pops_extra']} other pops")
    p = result.get("parts")
    if p:
        print(f"parts: {p['gold']} labeled in {p['files']} files; anchor exact {p['anchor_exact']:.3f}, within one page "
              f"{p['anchor_near']:.3f}; span within one page {p['span_near']:.3f}; {p['extra']} found parts match none")
    if args.verbose:
        for row in result["files"]:
            if row["variant"] == variants[0]:
                print(f"  {Path(row['path']).parent.name}/{Path(row['path']).name}: missed {row['missed']} extra {row['extra']}")
        for r in (p or {}).get("rows", []):
            print(f"  parts {Path(r['path']).parent.name}/{Path(r['path']).name}: found {r['found']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
