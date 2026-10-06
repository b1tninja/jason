"""Scoring a structure recovery against the gold (docs/structure-recovery.md).

A recovered heading matches a gold heading when their words (number taken off, case and punctuation folded) are alike and
the page is the page the variant puts the gold heading on; each gold heading is matched once, the best pairs first.
From the matches:

- heading precision, recall, and F1, with a bootstrap interval over the headings;
- level accuracy (exact, and within one level);
- the numbering round trip (the printed number recovered exactly);
- parent and child correctness (a matched heading hangs from the match of its gold parent);
- part boundaries (the first page of each part, against the parts found);
- page numbers (the printed number of each page that prints one).

``ablation_configs`` lists the clue sets a run is repeated with (each clue left out, each alone, and the clues added in
order of cost), and ``worth`` turns the scores into what each clue is worth.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Callable, Sequence

from jason.community.structure_gold import Gold, GoldNode
from jason.community.structure_numbering import fold_number, fold_text, split_number
from jason.community.structure_pdf import CLUES, MIN_SCORE, PNode, Recovery
from jason.community.structure_variants import VariantRecord

SIMILAR_HEADING = 0.8


def _gold_key(n: GoldNode) -> str:
    return n.key


def _rec_key(n: PNode) -> str:
    parsed = split_number(n.text)
    return fold_text(parsed.rest if parsed and parsed.rest else n.text) or fold_text(n.number)


def _alike(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return 1.0 if a == b else SequenceMatcher(None, a, b).ratio()


@dataclass
class Matched:
    gold: int              # index into the gold's headings
    rec: int               # index into the recovery's nodes
    alike: float


def match_headings(gold: Gold, record: VariantRecord, rec: Recovery, *, tolerance: int = 0, alike: float = SIMILAR_HEADING,
                   scope: tuple[int, int] | None = None) -> tuple[list[Matched], list[int], list[int]]:
    """(matches, the indexes of the gold headings that can be found (their page is in the variant), the recovered nodes in
    scope). ``scope`` is the page range of the document inside a larger file (the recovered headings outside it are not
    judged)."""
    heads = gold.headings()
    findable = [i for i, h in enumerate(heads) if h.page and record.page_map.get(h.page, 0)]
    inside = [j for j, n in enumerate(rec.nodes) if scope is None or scope[0] <= n.page <= scope[1]]
    pairs = []
    for i in findable:
        g = heads[i]
        gp = record.page_map[g.page]
        gk = _gold_key(g)
        for j in inside:
            n = rec.nodes[j]
            if abs(n.page - gp) > tolerance:
                continue
            r = max(_alike(gk, _rec_key(n)), _alike(fold_text(f"{g.number} {g.title}"), fold_text(n.text)))
            if r >= alike:
                pairs.append((r, -abs(n.page - gp), i, j))
    pairs.sort(reverse=True)
    used_g: set[int] = set()
    used_r: set[int] = set()
    out = []
    for r, _, i, j in pairs:
        if i in used_g or j in used_r:
            continue
        used_g.add(i)
        used_r.add(j)
        out.append(Matched(i, j, r))
    out.sort(key=lambda m: m.gold)
    return out, findable, inside


def f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if p + r else 0.0


def bootstrap_f1(found: Sequence[int], right: Sequence[int], *, samples: int = 1000, seed: int = 1) -> tuple[float, float]:
    """A 95% interval for the F1 from resampling the gold headings (1 when found) and the recovered ones (1 when right)."""
    if not found or not right:
        return 0.0, 0.0
    rng = random.Random(seed)
    values = []
    for _ in range(samples):
        r = sum(found[rng.randrange(len(found))] for _ in range(len(found))) / len(found)
        p = sum(right[rng.randrange(len(right))] for _ in range(len(right))) / len(right)
        values.append(f1(p, r))
    values.sort()
    return values[int(0.025 * samples)], values[min(samples - 1, int(0.975 * samples))]


def score(gold: Gold, record: VariantRecord, rec: Recovery, *, labels: dict[int, str] | None = None, tolerance: int = 0,
          samples: int = 1000) -> dict[str, Any]:
    """The metrics of one recovery of one variant."""
    scope = None
    if "host_first" in record.extra:
        scope = (record.extra["host_first"], record.extra["host_last"])
    matches, findable, inside = match_headings(gold, record, rec, tolerance=tolerance, scope=scope)
    heads = gold.headings()
    n_gold, n_find, n_rec = len(heads), len(findable), len(inside)
    tp = len(matches)
    precision = tp / n_rec if n_rec else 0.0
    recall = tp / n_find if n_find else 0.0
    found = [1 if any(m.gold == i for m in matches) else 0 for i in findable]
    right = [1 if any(m.rec == j for m in matches) else 0 for j in inside]
    lo, hi = bootstrap_f1(found, right, samples=samples)
    out: dict[str, Any] = {
        "variant": record.name, "gold": n_gold, "findable": n_find, "recovered": n_rec, "matched": tp,
        "precision": precision, "recall": recall, "f1": f1(precision, recall), "f1_lo": lo, "f1_hi": hi,
        "recall_all": tp / n_gold if n_gold else 0.0,
        "bleed": len(rec.nodes) - n_rec,
        "likely": sum(1 for j in inside if rec.nodes[j].tier == "likely"),
    }
    likely_right = sum(1 for m in matches if rec.nodes[m.rec].tier == "likely")
    out["likely_precision"] = likely_right / out["likely"] if out["likely"] else 0.0
    suggested = n_rec - out["likely"]
    out["suggested_precision"] = (tp - likely_right) / suggested if suggested else 0.0
    out["likely_recall"] = likely_right / n_find if n_find else 0.0
    out["likely_f1"] = f1(out["likely_precision"], out["likely_recall"])
    # levels
    exact = near = 0
    for m in matches:
        d = abs(rec.nodes[m.rec].level - heads[m.gold].level)
        exact += d == 0
        near += d <= 1
    out["level_exact"] = exact / tp if tp else 0.0
    out["level_within1"] = near / tp if tp else 0.0
    # numbers
    numbered = [m for m in matches if heads[m.gold].number]
    same = sum(1 for m in numbered if fold_number(rec.nodes[m.rec].number) == fold_number(heads[m.gold].number))
    out["numbered"] = len(numbered)
    out["number_roundtrip"] = same / len(numbered) if numbered else 0.0
    # parents
    gold_to_rec = {heads_index(gold, m.gold): m.rec for m in matches}
    judged = ok = 0
    for m in matches:
        gnode = heads[m.gold]
        parent = gnode.parent
        rparent = rec.nodes[m.rec].parent
        if parent == -1:
            judged += 1
            ok += rparent == -1
        elif parent in gold_to_rec:
            judged += 1
            ok += gold_to_rec[parent] == rparent
    out["parent_judged"] = judged
    out["parent_correct"] = ok / judged if judged else 0.0
    # parts
    gold_parts = sorted({record.page_map.get(p["page"], 0) for p in gold.parts if p["page"]} - {0})
    rec_parts = sorted({p["page"] for p in rec.parts if scope is None or scope[0] <= p["page"] <= scope[1]})
    if gold_parts:
        hit = len(set(gold_parts) & set(rec_parts))
        pp = hit / len(rec_parts) if rec_parts else 0.0
        rr = hit / len(gold_parts)
        out["part_precision"], out["part_recall"], out["part_f1"] = pp, rr, f1(pp, rr)
    else:
        out["part_precision"] = out["part_recall"] = out["part_f1"] = None
    out["parts_gold"] = len(gold_parts)
    # page numbers
    if labels:
        judged_p = right_p = 0
        for src, want in labels.items():
            q = record.page_map.get(src, 0)
            if not q:
                continue
            judged_p += 1
            right_p += fold_number(rec.labels.get(q, "")) == fold_number(want)
        out["page_numbers"] = right_p / judged_p if judged_p else None
    else:
        out["page_numbers"] = None
    return out


def heads_index(gold: Gold, i: int) -> int:
    """The index in ``gold.nodes`` of the i-th heading (a node's ``parent`` is such an index)."""
    seen = -1
    for k, n in enumerate(gold.nodes):
        if n.kind == "heading":
            seen += 1
            if seen == i:
                return k
    return -1


# --- ablation -------------------------------------------------------------------------------------------------------


def ablation_configs(names: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """The clue sets to run: all; each clue left out; each alone (its own weight the bar, so a weak clue can fire alone);
    and the clues added in order of cost (the bar the default's, or the strongest weight when that is lower)."""
    rows = [c for c in CLUES if names is None or c.name in set(names)]
    out: list[dict[str, Any]] = [{"name": "all", "clues": [c.name for c in rows], "min_score": MIN_SCORE}]
    for c in rows:
        out.append({"name": f"without {c.name}", "clues": [x.name for x in rows if x is not c], "min_score": MIN_SCORE})
    for c in rows:
        if not c.votes:
            continue
        out.append({"name": f"only {c.name}", "clues": [c.name], "min_score": c.weight})
    by_cost = sorted((c for c in rows if c.votes), key=lambda c: (c.cost, -c.weight))
    for k in range(1, len(by_cost) + 1):
        have = by_cost[:k]
        out.append({"name": f"cost order +{by_cost[k - 1].name}", "clues": [c.name for c in have],
                    "min_score": min(MIN_SCORE, max(c.weight for c in have))})
    return out


def worth(results: dict[str, float]) -> dict[str, dict[str, float]]:
    """From F1 by configuration name ("all", "without X", "only X"): what each clue is worth. ``loss`` is F1(all) minus F1
    without the clue (what the others cannot make up for); ``alone`` is its own F1."""
    base = results.get("all", 0.0)
    out: dict[str, dict[str, float]] = {}
    for c in CLUES:
        if f"without {c.name}" in results:
            out[c.name] = {"loss": base - results[f"without {c.name}"], "alone": results.get(f"only {c.name}", 0.0)}
    return out


def mean(values: Sequence[float | None]) -> float:
    real = [v for v in values if v is not None]
    return statistics.mean(real) if real else 0.0


__all__ = ["Matched", "SIMILAR_HEADING", "ablation_configs", "bootstrap_f1", "f1", "match_headings", "score", "worth"]
