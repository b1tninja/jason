"""How well ``responses.classify`` reads a request's kind, measured against a hand-labelled gold set.

The gold set is ``data/responses/kind-gold.json``. It is private, because it carries the requests' titles and the
threads' subjects. It labels each PayHOA request by its title and message, and each owner's email thread by its
subject alone, the way jason reads email. ``measure`` classifies each one as ``jason respond`` does:
- a PayHOA request by its form and its words (``classify_request``);
- an email thread by its subject, its topics, and who started it (``thread_kind``).

It reports precision and recall per kind, for each source and for both together, and lists the misses so a person can
see which rule row to change. A label is one reader's judgment, so a disagreement is a question as well as a miss.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

GOLD = Path("responses") / "kind-gold.json"


def load_gold(data_dir: Path, path: Path | None = None) -> dict[str, Any]:
    file = Path(path) if path else Path(data_dir) / GOLD
    if not file.is_file():
        raise FileNotFoundError(f"no gold set at {file}: label requests by kind first (docs/responses.md)")
    return json.loads(file.read_text(encoding="utf-8"))


def scores(pairs: list[tuple[str, str]]) -> dict[str, dict[str, Any]]:
    """Precision and recall per kind from (gold, predicted) pairs. Precision is None for a kind never predicted, and
    recall None for a kind never labelled."""
    gold, said, hit = Counter(g for g, _ in pairs), Counter(p for _, p in pairs), Counter(g for g, p in pairs if g == p)
    out = {}
    for kind in sorted(set(gold) | set(said)):
        out[kind] = {"support": gold[kind], "predicted": said[kind], "correct": hit[kind],
                     "precision": round(hit[kind] / said[kind], 3) if said[kind] else None,
                     "recall": round(hit[kind] / gold[kind], 3) if gold[kind] else None}
    return out


def predictions(data_dir: Path, community: Any, gold: dict[str, Any]) -> list[dict[str, Any]]:
    """Each labelled request with jason's kind for it and why. A request no longer in the stores is left out."""
    from jason.community.responses import rules_for
    from jason.tasks import responses as task
    from jason.tasks.request_links import load_requests
    from jason.tasks.threads import threads

    kind_rules, _ = rules_for(community)
    rows = []
    labelled = gold.get("payhoa") or {}
    for r in load_requests(Path(data_dir), community):
        label = labelled.get(str(r["id"]))
        if label:
            kind, why = task.classify_request(r, kind_rules)
            rows.append({"source": "payhoa", "id": str(r["id"]), "gold": label["kind"], "kind": kind.value, "why": why,
                         "text": r.get("title") or ""})
    labelled = gold.get("email") or {}
    if not labelled:
        return rows
    by_thread = task._messages_by_thread(Path(data_dir))
    for t in threads(Path(data_dir), community)["rows"]:
        label = labelled.get(t["threadId"])
        if label:
            kind, why = task.thread_kind(t, by_thread.get(t["threadId"], []), kind_rules)
            rows.append({"source": "email", "id": t["threadId"], "gold": label["kind"], "kind": kind.value, "why": why,
                         "text": t["subject"]})
    return rows


def measure(data_dir: Path, community: Any, path: Path | None = None) -> dict[str, Any]:
    gold = load_gold(data_dir, path)
    rows = predictions(data_dir, community, gold)
    out: dict[str, Any] = {"labelled": gold.get("labelled"), "measured": len(rows)}
    for source in ("payhoa", "email"):
        pairs = [(r["gold"], r["kind"]) for r in rows if r["source"] == source]
        out[source] = {"n": len(pairs), "accuracy": round(sum(g == p for g, p in pairs) / len(pairs), 3) if pairs else None,
                       "kinds": scores(pairs)}
    pairs = [(r["gold"], r["kind"]) for r in rows]
    out["all"] = {"n": len(pairs), "accuracy": round(sum(g == p for g, p in pairs) / len(pairs), 3) if pairs else None,
                  "kinds": scores(pairs)}
    out["misses"] = [r for r in rows if r["gold"] != r["kind"]]
    return out


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.0f}%"


def measure_lines(result: dict[str, Any], *, misses: bool = True) -> list[str]:
    out = [f"Kinds measured against the gold set labelled {result.get('labelled')}: {result['measured']} requests."]
    for source in ("payhoa", "email", "all"):
        part = result[source]
        out.append(f"\n{source}: {part['n']} labelled, {_pct(part['accuracy'])} right")
        out.append(f"  {'kind':34} {'labelled':>8} {'said':>6} {'precision':>9} {'recall':>7}")
        for kind, s in part["kinds"].items():
            out.append(f"  {kind:34} {s['support']:>8} {s['predicted']:>6} {_pct(s['precision']):>9} {_pct(s['recall']):>7}")
    if misses and result["misses"]:
        out.append("\nMisses (labelled -> said, and why):")
        for r in result["misses"]:
            out.append(f"  {r['source']} {r['id']}: {r['gold']} -> {r['kind']} ({r['why'][:50]}): {r['text'][:70]}")
    out.append("\nA label is one reader's judgment from the same text jason reads; a miss may be a question about the label.")
    return out


__all__ = ["GOLD", "load_gold", "measure", "measure_lines", "predictions", "scores"]
