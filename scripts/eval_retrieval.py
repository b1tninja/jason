"""Score the passage retrievers against gold questions (data/retrieval/gold.json by default).

    python scripts/eval_retrieval.py                 # keyword, exact, dense, hybrid
    python scripts/eval_retrieval.py --rerank        # also hybrid + the LLM reranker (one chat request a question)
    python scripts/eval_retrieval.py --offline       # keyword and exact only; sends nothing to Ollama
    python scripts/eval_retrieval.py --gold data/retrieval/gold-heldout.json --fusion 60:1.0
                                                     # a held-out set, and the hybrid at another k and dense weight
    python scripts/eval_retrieval.py --gold data/retrieval/gold.json --gold data/retrieval/gold-heldout.json
                                                     # several sets: each one's table, then the pooled table

Prints recall@5 and MRR@10 per method, by kind (and by family with ``--by-family``), the misses, the embedding time,
and the vector cache's size. A gold file's ``unanswerable`` questions (an answer that spans passages, or none in the
corpus) are reported apart and never scored as misses. A dense run embeds every passage once (cached under
data/retrieval/vectors) and holds the GPU lock for each batch.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Callable, Sequence

from jason.community import retrieval
from jason.community.passages import Hit, Passage, corpus, rank

Method = Callable[[str], Sequence[Hit]]


def relevant(hit: Hit, item: dict) -> bool:
    name = str(hit.passage.path).replace("\\", "/").lower()
    text = hit.passage.text.lower()
    files = [f.lower() for f in item.get("files") or []]
    return (not files or any(f in name for f in files)) and all(t.lower() in text for t in item.get("text") or [])


def score(hits: Sequence[Hit], item: dict) -> tuple[bool, float, int]:
    ranks = [i for i, hit in enumerate(hits[:10], 1) if relevant(hit, item)]
    first = ranks[0] if ranks else 0
    return (bool(first) and first <= 5, 1.0 / first if first else 0.0, first)


def first_ranks(questions: Sequence[dict], methods: dict[str, Method]) -> tuple[dict[str, dict[str, int]], dict[str, float]]:
    """Each question's first relevant rank (0 = none in the top 10) under each method, and each method's seconds a
    question."""
    detail: dict[str, dict[str, int]] = {}
    seconds: dict[str, float] = {}
    for name, method in methods.items():
        spent = 0.0
        for q in questions:
            started = time.monotonic()
            hits = method(q["q"])
            spent += time.monotonic() - started
            detail.setdefault(q["id"], {})[name] = score(hits, q)[2]
        seconds[name] = spent / len(questions) if questions else 0.0
    return detail, seconds


def table(questions: Sequence[dict], detail: dict[str, dict[str, int]], methods: Sequence[str],
          group: str = "") -> dict[str, dict[str, dict[str, float]]]:
    """Recall@5 and MRR@10 per method, for all questions (key "all") or per value of ``group`` ("kind", "family")."""
    groups: dict[str, list[dict]] = {}
    for q in questions:
        groups.setdefault(str(q.get(group) or "-") if group else "all", []).append(q)
    out: dict[str, dict[str, dict[str, float]]] = {}
    for key, subset in sorted(groups.items()):
        out[key] = {}
        for name in methods:
            firsts = [detail[q["id"]][name] for q in subset]
            out[key][name] = {
                "n": len(subset),
                "recall@5": sum(1 for f in firsts if 0 < f <= 5) / len(subset),
                "mrr@10": sum(1.0 / f for f in firsts if f) / len(subset),
            }
    return out


def unanswerable(items: Sequence[dict], methods: dict[str, Method]) -> dict[str, dict[str, object]]:
    """For an answer that spans passages, how many of its parts each method puts in the top 10; for one with no
    answer in the corpus, the file each method ranks first (what a reader would be shown instead)."""
    out: dict[str, dict[str, object]] = {}
    for u in items:
        row: dict[str, object] = {}
        for name, method in methods.items():
            hits = tuple(method(u["q"]))[:10]
            if u.get("parts"):
                found = sum(1 for part in u["parts"] if any(relevant(h, part) for h in hits))
                row[name] = f"{found}/{len(u['parts'])}"
            else:
                row[name] = hits[0].passage.path.name if hits else "-"
        out[u["id"]] = row
    return out


def print_table(title: str, rows: dict[str, dict[str, dict[str, float]]], methods: Sequence[str]) -> None:
    width = max([len(m) for m in methods] + [8])
    print(f"\n{title}")
    print(" " * 22 + "  ".join(f"{m:>{width}}" for m in methods))
    for key, by_method in rows.items():
        n = next(iter(by_method.values()))["n"] if by_method else 0
        cells = "  ".join(f"{by_method[m]['recall@5']:.2f} / {by_method[m]['mrr@10']:.3f}".rjust(width) for m in methods)
        print(f"{key[:16]:16} {n:4}  {cells}")


def build_methods(items: tuple[Passage, ...], embedder, reranker, fusions: Sequence[tuple[int, float]]) -> dict[str, Method]:
    methods: dict[str, Method] = {
        "keyword (BM25)": lambda q: rank(q, items, k=10),
        "keyword + exact": lambda q: retrieval.keyword_exact(q, items, k=10),
    }
    if embedder:
        methods["dense"] = lambda q: retrieval.dense_rank(q, items, embedder, k=10)
        methods["hybrid (RRF)"] = lambda q: retrieval.hybrid(q, items, k=10, embedder=embedder)
        for rrf_k, weight in fusions:
            methods[f"hybrid k{rrf_k} w{weight:g}"] = (
                lambda q, rrf_k=rrf_k, weight=weight: retrieval.hybrid(q, items, k=10, embedder=embedder,
                                                                       rrf_k=rrf_k, dense_weight=weight))
    if reranker:
        methods["exact + rerank"] = lambda q: retrieval.hybrid(q, items, k=10, reranker=reranker)
    if reranker and embedder:
        methods["hybrid + rerank"] = lambda q: retrieval.hybrid(q, items, k=10, embedder=embedder, reranker=reranker)
    return methods


def parse_fusion(text: str) -> tuple[int, float]:
    k, _, weight = text.partition(":")
    return int(k), float(weight or 1.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data")
    parser.add_argument("--gold", action="append", default=[], help="a gold file; repeat for several (default: gold.json)")
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--fusion", action="append", default=[], metavar="K:W",
                        help="also run the hybrid at RRF k K and dense weight W (e.g. 60:1.0, the equal-weight fusion)")
    parser.add_argument("--by-family", action="store_true", help="also print the table by each question's family")
    parser.add_argument("--json", default="", help="write the per-question results here")
    args = parser.parse_args(argv)
    data = Path(args.data)
    paths = [Path(p) for p in args.gold] or [data / "retrieval" / "gold.json"]
    fusions = [parse_fusion(f) for f in args.fusion]

    embedder = None if args.offline else retrieval.default_embedder(data)
    reranker = retrieval.LlmReranker() if args.rerank else None
    timings: dict[str, float] = {}
    runs = []
    pooled_questions: list[dict] = []
    pooled_detail: dict[str, dict[str, int]] = {}
    names: list[str] = []
    corpora: dict[tuple[str, ...], tuple[Passage, ...]] = {}
    for path in paths:
        gold = json.loads(path.read_text(encoding="utf-8"))
        folders = tuple(gold["folders"])
        if folders not in corpora:
            corpora[folders] = corpus(*(data / f for f in folders))
        items = corpora[folders]
        questions = gold["questions"]
        for q in questions:
            if not any(relevant(Hit(p, 0), q) for p in items):
                print(f"warning: no passage in the corpus is relevant to {q['id']}", file=sys.stderr)
        print(f"\n== {path}: {len(items)} passages, {len(questions)} questions, "
              f"{len(gold.get('unanswerable') or [])} unanswerable")
        if embedder and "corpus embed s" not in timings:
            started = time.monotonic()
            embedder.embed_passages([p.text for p in items])
            timings["corpus embed s"] = round(time.monotonic() - started, 1)
            timings["passages sent"] = embedder.sent
        methods = build_methods(items, embedder, reranker, fusions)
        names = list(methods)
        detail, seconds = first_ranks(questions, methods)
        for name in methods:
            misses = [f"{q['id']}({detail[q['id']][name] or '-'})" for q in questions if not 0 < detail[q["id"]][name] <= 5]
            row = table(questions, detail, [name])["all"][name]
            print(f"{name:18} recall@5 {row['recall@5']:.2f}  MRR@10 {row['mrr@10']:.3f}  {seconds[name]:6.2f} s/q  "
                  f"misses: {', '.join(misses) or 'none'}")
        rows = table(questions, detail, names)
        kinds = table(questions, detail, names, "kind")
        print_table("recall@5 / MRR@10", {**rows, **kinds}, names)
        families = table(questions, detail, names, "family") if any(q.get("family") for q in questions) else {}
        if args.by_family and families:
            print_table("by family", families, names)
        unans = unanswerable(gold.get("unanswerable") or [], methods)
        if unans:
            print("\nunanswerable (parts found in the top 10, or the file ranked first):")
            for uid, row in unans.items():
                print(f"  {uid:28} " + "; ".join(f"{m} {v}" for m, v in row.items()))
        runs.append({"gold": str(path), "rows": rows, "kinds": kinds, "families": families, "detail": detail,
                     "seconds": seconds, "unanswerable": unans})
        prefix = path.stem + ":" if len(paths) > 1 else ""
        pooled_questions += [{**q, "id": prefix + q["id"]} for q in questions]
        pooled_detail.update({prefix + qid: ranks for qid, ranks in detail.items()})
    pooled = {}
    if len(paths) > 1:
        pooled = {**table(pooled_questions, pooled_detail, names), **table(pooled_questions, pooled_detail, names, "kind")}
        print_table(f"pooled over {len(paths)} gold files: recall@5 / MRR@10", pooled, names)
    if embedder:
        print("timings:", timings, "cache:", embedder.cache.stats() if embedder.cache else {})
    if reranker:
        took = sorted(s for s in reranker.model_seconds if s)
        if took:
            print(f"rerank: {len(took)} requests, Ollama time median {took[len(took) // 2]:.1f} s, max {took[-1]:.1f} s")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps({"runs": runs, "pooled": pooled, "timings": timings}, indent=1),
                                   encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
