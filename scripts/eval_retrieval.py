"""Score the passage retrievers against the gold questions in data/retrieval/gold.json.

    python scripts/eval_retrieval.py                 # keyword, exact, dense, hybrid
    python scripts/eval_retrieval.py --rerank        # also hybrid + the LLM reranker (one chat request a question)
    python scripts/eval_retrieval.py --offline       # keyword and exact only; sends nothing to Ollama

Prints recall@5 and MRR@10 per method, the misses, the embedding time, and the vector cache's size. A dense run
embeds every passage once (cached under data/retrieval/vectors) and holds the GPU lock for each batch.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from jason.community import retrieval
from jason.community.passages import Hit, corpus, rank


def relevant(hit: Hit, item: dict) -> bool:
    name = str(hit.passage.path).replace("\\", "/").lower()
    text = hit.passage.text.lower()
    files = [f.lower() for f in item.get("files") or []]
    return (not files or any(f in name for f in files)) and all(t.lower() in text for t in item.get("text") or [])


def score(hits: tuple[Hit, ...], item: dict) -> tuple[bool, float, int]:
    ranks = [i for i, hit in enumerate(hits[:10], 1) if relevant(hit, item)]
    first = ranks[0] if ranks else 0
    return (bool(first) and first <= 5, 1.0 / first if first else 0.0, first)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data")
    parser.add_argument("--gold", default="")
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--json", default="", help="write the per-question results here")
    args = parser.parse_args(argv)
    data = Path(args.data)
    gold = json.loads(Path(args.gold or data / "retrieval" / "gold.json").read_text(encoding="utf-8"))
    items = corpus(*(data / f for f in gold["folders"]))
    questions = gold["questions"]
    for q in questions:
        if not any(relevant(Hit(p, 0), q) for p in items):
            print(f"warning: no passage in the corpus is relevant to {q['id']}", file=sys.stderr)
    print(f"{len(items)} passages, {len(questions)} questions")

    embedder = None if args.offline else retrieval.default_embedder(data)
    timings: dict[str, float] = {}
    if embedder:
        started = time.monotonic()
        embedder.embed_passages([p.text for p in items])
        timings["corpus embed s"] = round(time.monotonic() - started, 1)
        timings["passages sent"] = embedder.sent
    reranker = retrieval.LlmReranker() if args.rerank else None

    methods = {
        "keyword (BM25)": lambda q: rank(q, items, k=10),
        "keyword + exact": lambda q: retrieval.keyword_exact(q, items, k=10),
    }
    if embedder:
        methods["dense"] = lambda q: retrieval.dense_rank(q, items, embedder, k=10)
        methods["hybrid (RRF)"] = lambda q: retrieval.hybrid(q, items, k=10, embedder=embedder)
    if reranker:
        methods["exact + rerank"] = lambda q: retrieval.hybrid(q, items, k=10, reranker=reranker)
    if reranker and embedder:
        methods["hybrid + rerank"] = lambda q: retrieval.hybrid(q, items, k=10, embedder=embedder, reranker=reranker)

    rows = []
    detail: dict[str, dict] = {}
    for name, method in methods.items():
        found = mrr = 0.0
        spent = 0.0
        misses = []
        for q in questions:
            started = time.monotonic()
            hits = method(q["q"])
            spent += time.monotonic() - started
            hit5, rr, first = score(hits, q)
            found += hit5
            mrr += rr
            detail.setdefault(q["id"], {})[name] = first
            if not hit5:
                misses.append(f"{q['id']}({first or '-'})")
        n = len(questions)
        rows.append((name, found / n, mrr / n, spent / n))
        print(f"{name:18} recall@5 {found / n:.2f}  MRR@10 {mrr / n:.3f}  {spent / n:6.2f} s/q  misses: {', '.join(misses) or 'none'}")
    for kind in ("exact", "paraphrase"):
        subset = [q for q in questions if q.get("kind") == kind]
        if subset:
            parts = []
            for name in methods:
                r5 = sum(1 for q in subset if 0 < detail[q["id"]][name] <= 5) / len(subset)
                parts.append(f"{name} {r5:.2f}")
            print(f"  {kind} ({len(subset)}): " + "; ".join(parts))
    if embedder:
        print("timings:", timings, "cache:", embedder.cache.stats() if embedder.cache else {})
    if reranker:
        took = sorted(s for s in reranker.model_seconds if s)
        if took:
            print(f"rerank: {len(took)} requests, Ollama time median {took[len(took) // 2]:.1f} s, max {took[-1]:.1f} s")
    if args.json:
        Path(args.json).write_text(json.dumps({"rows": rows, "detail": detail, "timings": timings}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
