"""Score AnythingLLM's vector search against the same gold questions as scripts/eval_retrieval.py.

    python scripts/eval_anythingllm.py --workspace SLUG                  # one workspace, both gold files
    python scripts/eval_anythingllm.py --workspace association-records --workspace insurance
                                                                         # each workspace, and their union by score
    python scripts/eval_anythingllm.py --json data/retrieval/runs/DATE-anythingllm.json

A hit is relevant by the same rule as eval_retrieval: every phrase in the chunk's own words (the
``<document_metadata>`` header AnythingLLM prepends is cut off first), in a file whose title carries one of the
question's file names. ``folded`` counts a chunk whose text repeats one ranked above it once, as eval_retrieval's
near-copy fold does. Each request embeds the question on the shared Ollama, so the run holds the GPU lock.
It only reads: no document, workspace, or setting changes.

jason no longer runs AnythingLLM (its own passage index replaced it; docs/applicability.md), so this script keeps the
measurement repeatable on its own: it calls the app's API directly, with the key from ``--key`` or
``ANYTHINGLLM_API_KEY``, and needs nothing of jason but the GPU lock.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

API = "http://localhost:3001/api/v1"
HEADER = re.compile(r"^\s*<document_metadata>.*?</document_metadata>\s*", re.S)


def _squash(text: str) -> str:
    return " ".join(text.lower().split())


def relevant(chunk: dict, item: dict) -> bool:
    title = str((chunk.get("metadata") or {}).get("title") or "").lower()
    text = _squash(HEADER.sub("", str(chunk.get("text") or "")))
    files = [f.lower() for f in item.get("files") or []]
    return (not files or any(f in title for f in files)) and all(_squash(t) in text for t in item.get("text") or [])


def fold(chunks: list[dict]) -> list[dict]:
    """Drop a chunk whose body repeats one already kept (the same passage from another copy of the file)."""
    seen: set[str] = set()
    out = []
    for c in chunks:
        body = _squash(HEADER.sub("", str(c.get("text") or "")))[:400]
        if body in seen:
            continue
        seen.add(body)
        out.append(c)
    return out


def first_rank(chunks: list[dict], item: dict) -> int:
    return next((i for i, c in enumerate(chunks[:10], 1) if relevant(c, item)), 0)


def vector_search(key: str, slug: str, query: str, depth: int, api: str = API) -> list[dict]:
    body = json.dumps({"query": query, "topN": depth, "scoreThreshold": 0}).encode("utf-8")
    request = Request(f"{api}/workspace/{slug}/vector-search", data=body, method="POST",
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"})
    with urlopen(request, timeout=300) as response:
        return json.loads(response.read().decode("utf-8") or "{}").get("results") or []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data")
    parser.add_argument("--gold", action="append", default=[])
    parser.add_argument("--workspace", action="append", default=[], help="a workspace slug; repeat")
    parser.add_argument("--key", default="", help="the app's API key (default: ANYTHINGLLM_API_KEY)")
    parser.add_argument("--api", default=API)
    parser.add_argument("--depth", type=int, default=30, help="chunks asked of each workspace before folding")
    parser.add_argument("--json", default="")
    args = parser.parse_args(argv)
    data = Path(args.data)
    golds = [Path(p) for p in args.gold] or [data / "retrieval" / "gold.json", data / "retrieval" / "gold-heldout.json"]

    import os

    from jason.locks import Resource, hold

    key = args.key or os.environ.get("ANYTHINGLLM_API_KEY", "")
    spaces = [s for s in args.workspace if s]
    if not spaces or not key:
        print("name a workspace with --workspace and give the key (--key or ANYTHINGLLM_API_KEY)", file=sys.stderr)
        return 2
    methods = [*spaces, *(["union"] if len(spaces) > 1 else [])]
    result: dict = {"workspaces": spaces, "runs": []}
    with hold(Resource.GPU, purpose="eval AnythingLLM vector search"):
        for path in golds:
            gold = json.loads(path.read_text(encoding="utf-8"))
            questions = gold["questions"]
            detail: dict[str, dict[str, int]] = {}
            seconds = {m: 0.0 for m in methods}
            for q in questions:
                pooled: list[dict] = []
                for slug in spaces:
                    started = time.monotonic()
                    found = vector_search(key, slug, q["q"], args.depth, api=args.api)
                    seconds[slug] += time.monotonic() - started
                    pooled += found
                    detail.setdefault(q["id"], {})[slug] = first_rank(found, q)
                    detail[q["id"]][slug + " folded"] = first_rank(fold(found), q)
                if len(spaces) > 1:
                    merged = sorted(pooled, key=lambda c: -float(c.get("score") or 0))
                    detail[q["id"]]["union"] = first_rank(merged, q)
                    detail[q["id"]]["union folded"] = first_rank(fold(merged), q)
            rows = {}
            for name in sorted({m for d in detail.values() for m in d}):
                firsts = [detail[q["id"]][name] for q in questions]
                rows[name] = {"n": len(questions),
                              "recall@5": round(sum(1 for f in firsts if 0 < f <= 5) / len(questions), 3),
                              "mrr@10": round(sum(1.0 / f for f in firsts if f) / len(questions), 3)}
            print(f"\n== {path}: {len(questions)} questions")
            for name, row in rows.items():
                misses = [q["id"] for q in questions if not 0 < detail[q["id"]][name] <= 5]
                print(f"{name:34} recall@5 {row['recall@5']:.2f}  MRR@10 {row['mrr@10']:.3f}  misses {len(misses)}")
            for m in spaces:
                print(f"  {m}: {seconds[m] / len(questions):.2f} s/q")
            result["runs"].append({"gold": str(path), "rows": rows, "detail": detail,
                                   "seconds": {m: s / len(questions) for m, s in seconds.items()}})
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(result, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
