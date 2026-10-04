"""Score the passage retrievers against gold questions (data/retrieval/gold.json by default).

    python scripts/eval_retrieval.py                 # keyword, exact, dense, hybrid
    python scripts/eval_retrieval.py --rerank        # also hybrid + the LLM reranker (one chat request a question)
    python scripts/eval_retrieval.py --offline       # keyword and exact only; sends nothing to Ollama
    python scripts/eval_retrieval.py --gold data/retrieval/gold-heldout.json --fusion 60:1.0
                                                     # a held-out set, and the hybrid at another k and dense weight
    python scripts/eval_retrieval.py --gold data/retrieval/gold.json --gold data/retrieval/gold-heldout.json
                                                     # several sets: each one's table, then the pooled table
    python scripts/eval_retrieval.py --chunking windows --no-copies --compare RUN.json --no-answer
                                                     # the old passages, against an earlier run question by question,
                                                     # and whether a score threshold flags the questions with no answer

Prints recall@5 and MRR@10 per method, by kind (and by family with ``--by-family``), the misses, the embedding time,
and the vector cache's size. A gold file's ``unanswerable`` questions (an answer that spans passages, or none in the
corpus) are reported apart and never scored as misses. A hit is relevant by its own words, never its heading, or by a
near copy folded under it (``Hit.also``); the run counts the questions credited only that way. A dense run embeds every passage once (cached under
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


def _squash(text: str) -> str:
    return " ".join(text.lower().split())


def _relevant_passage(passage: Passage, item: dict) -> bool:
    name = str(passage.path).replace("\\", "/").lower()
    text = _squash(passage.text)
    files = [f.lower() for f in item.get("files") or []]
    return (not files or any(f in name for f in files)) and all(_squash(t) in text for t in item.get("text") or [])


def relevant(hit: Hit, item: dict, *, also: bool = True) -> bool:
    """The passage's own words (spacing aside; never its heading) carry every phrase, in a named file; or, with
    ``also``, one of the near copies folded under it does (a person sees every source of a collapsed hit)."""
    if _relevant_passage(hit.passage, item):
        return True
    return also and any(_relevant_passage(p, item) for p in hit.also)


def score(hits: Sequence[Hit], item: dict) -> tuple[bool, float, int]:
    ranks = [i for i, hit in enumerate(hits[:10], 1) if relevant(hit, item)]
    first = ranks[0] if ranks else 0
    return (bool(first) and first <= 5, 1.0 / first if first else 0.0, first)


def first_ranks(questions: Sequence[dict], methods: dict[str, Method]) -> tuple[dict[str, dict[str, int]], dict[str, float]]:
    """Each question's first relevant rank (0 = none in the top 10) under each method, and each method's seconds a
    question."""
    detail: dict[str, dict[str, int]] = {}
    seconds: dict[str, float] = {}
    FIRST_STATS.clear()
    for name, method in methods.items():
        spent = 0.0
        crowded = 0
        through_also = 0
        for q in questions:
            started = time.monotonic()
            hits = tuple(method(q["q"]))
            spent += time.monotonic() - started
            first = score(hits, q)[2]
            detail.setdefault(q["id"], {})[name] = first
            if first and not relevant(hits[first - 1], q, also=False):
                through_also += 1
            cache: dict = {}
            top = hits[:10]
            crowded += sum(1 for i, h in enumerate(top)
                           if any(retrieval.near_copies(e.passage, h.passage, cache=cache) for e in top[:i]))
        seconds[name] = spent / len(questions) if questions else 0.0
        FIRST_STATS[name] = {"copies in top 10": round(crowded / len(questions), 2) if questions else 0.0,
                             "credited through also": through_also}
    return detail, seconds


FIRST_STATS: dict[str, dict[str, float]] = {}       # the last first_ranks call's crowding and "also" credits


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


def build_methods(items: tuple[Passage, ...], embedder, reranker, fusions: Sequence[tuple[int, float]],
                  copies: bool = False) -> dict[str, Method]:
    """Each retriever over ``items``; with ``copies`` every ranking folds near copies before its top 10."""
    depth = retrieval.DENSE_DEPTH

    def fold(hits: Sequence[Hit]) -> tuple[Hit, ...]:
        return retrieval.collapse(hits)[:10] if copies else tuple(hits)[:10]

    methods: dict[str, Method] = {
        "keyword (BM25)": lambda q: fold(rank(q, items, k=depth if copies else 10)),
        "keyword + exact": lambda q: retrieval.keyword_exact(q, items, k=10, copies=copies),
    }
    if embedder:
        methods["dense"] = lambda q: fold(retrieval.dense_rank(q, items, embedder, k=depth if copies else 10))
        methods["hybrid (RRF)"] = lambda q: retrieval.hybrid(q, items, k=10, embedder=embedder, copies=copies)
        for rrf_k, weight in fusions:
            methods[f"hybrid k{rrf_k} w{weight:g}"] = (
                lambda q, rrf_k=rrf_k, weight=weight: retrieval.hybrid(q, items, k=10, embedder=embedder,
                                                                       rrf_k=rrf_k, dense_weight=weight, copies=copies))
    if reranker:
        methods["exact + rerank"] = lambda q: retrieval.hybrid(q, items, k=10, reranker=reranker, copies=copies)
    if reranker and embedder:
        methods["hybrid + rerank"] = lambda q: retrieval.hybrid(q, items, k=10, embedder=embedder, reranker=reranker,
                                                                copies=copies)
    return methods


def crowding(questions: Sequence[dict], methods: dict[str, Method]) -> dict[str, float]:
    """The average number of each method's top 10 that are near copies of a passage ranked above them."""
    out: dict[str, float] = {}
    for name, method in methods.items():
        total = 0
        for q in questions:
            hits = tuple(method(q["q"]))[:10]
            cache: dict = {}
            total += sum(1 for i, h in enumerate(hits)
                         if any(retrieval.near_copies(e.passage, h.passage, cache=cache) for e in hits[:i]))
        out[name] = round(total / len(questions), 2) if questions else 0.0
    return out


def no_answer_features(questions: Sequence[dict], items: tuple[Passage, ...], embedder) -> dict[str, dict[str, float]]:
    """Each question's best dense cosine and best BM25 score (and BM25 over the question's word count)."""
    from jason.community.passages import tokens

    out: dict[str, dict[str, float]] = {}
    for q in questions:
        row: dict[str, float] = {}
        top = rank(q["q"], items, k=1)
        row["bm25"] = float(top[0].score) if top else 0.0
        row["bm25/word"] = row["bm25"] / max(1, len(tokens(q["q"])))
        if embedder:
            dense = retrieval.dense_rank(q["q"], items, embedder, k=1)
            row["cosine"] = float(dense[0].score) if dense else 0.0
        out[q["id"]] = row
    return out


def separation(answerable: dict[str, dict[str, float]], absent: dict[str, dict[str, float]]) -> dict[str, dict]:
    """For each feature, the threshold that best flags the questions with no answer (score below it), with that flag's
    precision and recall over all the questions given, and the ranges of the two groups."""
    out: dict[str, dict] = {}
    features = sorted({f for row in list(answerable.values()) + list(absent.values()) for f in row})
    for feature in features:
        pos = sorted(row[feature] for row in absent.values() if feature in row)
        neg = sorted(row[feature] for row in answerable.values() if feature in row)
        if not pos or not neg:
            continue
        best = None
        for cut in sorted(set(pos + neg)):
            limit = cut + 1e-9                        # flag a question whose best score is at or below ``cut``
            tp = sum(1 for v in pos if v < limit)
            fp = sum(1 for v in neg if v < limit)
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / len(pos)
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            if best is None or f1 > best["f1"]:
                best = {"threshold": round(limit, 4), "precision": round(precision, 3), "recall": round(recall, 3),
                        "f1": round(f1, 3), "flagged answerable": fp}
        out[feature] = {**(best or {}), "absent": [round(v, 4) for v in pos],
                        "answerable min / median": [round(neg[0], 4), round(neg[len(neg) // 2], 4)]}
    return out


def compare(before: dict, after: dict, questions_by_gold: dict[str, list[dict]]) -> dict[str, dict]:
    """Question by question, against an earlier run's JSON: for each gold file and method in both, the questions won
    (into the top 5 or up the ranks) and lost, and the families whose recall moved."""
    out: dict[str, dict] = {}
    old_runs = {Path(r["gold"]).name: r for r in before.get("runs", [])}
    for run in after.get("runs", []):
        gold = Path(run["gold"]).name
        old = old_runs.get(gold)
        if not old:
            continue
        questions = {q["id"]: q for q in questions_by_gold.get(gold, [])}
        for method in sorted({m for ranks in run["detail"].values() for m in ranks}):
            won, lost, up, down = [], [], [], []
            families: dict[str, int] = {}
            for qid, ranks in run["detail"].items():
                if method not in ranks or method not in old["detail"].get(qid, {}):
                    continue
                a, b = old["detail"][qid][method], ranks[method]
                in_a, in_b = 0 < a <= 5, 0 < b <= 5
                fam = str(questions.get(qid, {}).get("family") or questions.get(qid, {}).get("kind") or "-")
                if in_b and not in_a:
                    won.append(f"{qid}({a or '-'}>{b})")
                    families[fam] = families.get(fam, 0) + 1
                elif in_a and not in_b:
                    lost.append(f"{qid}({a}>{b or '-'})")
                    families[fam] = families.get(fam, 0) - 1
                elif a != b and (b and (not a or b < a)):
                    up.append(f"{qid}({a or '-'}>{b})")
                elif a != b:
                    down.append(f"{qid}({a or '-'}>{b or '-'})")
            out[f"{gold} / {method}"] = {"won": won, "lost": lost, "rank up": up, "rank down": down,
                                         "families moved": {f: n for f, n in sorted(families.items()) if n}}
    return out


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
    parser.add_argument("--chunking", choices=("windows", "sections"), default=retrieval.CHUNKING,
                        help=f"cut passages as fixed windows or on the documents' sections (default {retrieval.CHUNKING})")
    parser.add_argument("--copies", action=argparse.BooleanOptionalAction, default=retrieval.COLLAPSE_COPIES,
                        help="fold near copies before each method's top 10 (default: retrieval.COLLAPSE_COPIES)")
    parser.add_argument("--compare", default="", help="an earlier run's --json: list the questions won and lost")
    parser.add_argument("--no-answer", action="store_true",
                        help="measure whether a threshold on the best score separates the questions with no answer")
    parser.add_argument("--index", action="store_true",
                        help="rank the passage index's passages under the gold folders (jason index --build) "
                             "instead of cutting the folders; vectors come from the index")
    parser.add_argument("--index-all", action="store_true",
                        help="rank every passage in the index (all catalogs), the harder corpus")
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
    questions_by_gold: dict[str, list[dict]] = {}
    for path in paths:
        gold = json.loads(path.read_text(encoding="utf-8"))
        folders = tuple(gold["folders"])
        if folders not in corpora:
            started = time.monotonic()
            if args.index or args.index_all:
                from jason.community import passage_index

                scope = passage_index.Scope() if args.index_all else passage_index.Scope(folders=folders)
                loaded = passage_index.load(data, scope, vectors=embedder is not None)
                corpora[folders] = loaded.passages
                if embedder is not None and not isinstance(embedder, passage_index.StoredEmbedder):
                    embedder = passage_index.StoredEmbedder(loaded.vectors, embedder)
            else:
                corpora[folders] = corpus(*(data / f for f in folders), chunking=args.chunking, outlines=data / "outlines")
            timings["corpus cut s"] = round(time.monotonic() - started, 1)
        items = corpora[folders]
        questions = gold["questions"]
        for q in questions:
            if not any(relevant(Hit(p, 0), q) for p in items):
                print(f"warning: no passage in the corpus is relevant to {q['id']}", file=sys.stderr)
        print(f"\n== {path}: {len(items)} passages, {len(questions)} questions, "
              f"{len(gold.get('unanswerable') or [])} unanswerable")
        if embedder and "corpus embed s" not in timings:
            started = time.monotonic()
            embedder.embed_passages([p.ranked for p in items])
            timings["corpus embed s"] = round(time.monotonic() - started, 1)
            timings["passages sent"] = getattr(embedder, "sent", getattr(embedder, "live", 0))
        methods = build_methods(items, embedder, reranker, fusions, copies=args.copies)
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
        stats = {name: dict(row) for name, row in FIRST_STATS.items()}
        print("near copies in the top 10 (average), and questions credited only through a folded copy:")
        for name, row in stats.items():
            print(f"  {name:18} {row['copies in top 10']:5.2f}  {row['credited through also']}")
        absent_items = [u for u in gold.get("unanswerable") or [] if u.get("reason") == "absent"]
        noanswer = {}
        if args.no_answer and absent_items:
            answerable = no_answer_features(questions, items, embedder)
            absent = no_answer_features(absent_items, items, embedder)
            noanswer = {"separation": separation(answerable, absent), "absent": absent,
                        "answerable": answerable}
            print("\nno answer in the corpus: the best threshold on each feature (flag below it)")
            for feature, row in noanswer["separation"].items():
                print(f"  {feature:10} {json.dumps(row)}")
        runs.append({"gold": str(path), "rows": rows, "kinds": kinds, "families": families, "detail": detail,
                     "seconds": seconds, "unanswerable": unans, "stats": stats, "no_answer": noanswer,
                     "settings": {"chunking": args.chunking, "copies": args.copies, "passages": len(items)}})
        questions_by_gold[path.name] = questions
        prefix = path.stem + ":" if len(paths) > 1 else ""
        pooled_questions += [{**q, "id": prefix + q["id"]} for q in questions]
        pooled_detail.update({prefix + qid: ranks for qid, ranks in detail.items()})
    pooled = {}
    if len(paths) > 1:
        pooled = {**table(pooled_questions, pooled_detail, names), **table(pooled_questions, pooled_detail, names, "kind")}
        print_table(f"pooled over {len(paths)} gold files: recall@5 / MRR@10", pooled, names)
    if embedder:
        cache = getattr(embedder, "cache", None)
        print("timings:", timings, "cache:", cache.stats() if cache else {})
    if reranker:
        took = sorted(s for s in reranker.model_seconds if s)
        if took:
            print(f"rerank: {len(took)} requests, Ollama time median {took[len(took) // 2]:.1f} s, max {took[-1]:.1f} s")
    result = {"runs": runs, "pooled": pooled, "timings": timings}
    if embedder and getattr(embedder, "cache", None):
        result["cache"] = embedder.cache.stats()
    if args.compare:
        before = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        result["compare"] = {"against": args.compare, "by method": compare(before, result, questions_by_gold)}
        print(f"\nagainst {args.compare}:")
        for key, row in result["compare"]["by method"].items():
            print(f"  {key}: won {len(row['won'])}, lost {len(row['lost'])}; families {row['families moved'] or '-'}")
            for label in ("won", "lost"):
                if row[label]:
                    print(f"    {label}: {', '.join(row[label])}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(result, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
