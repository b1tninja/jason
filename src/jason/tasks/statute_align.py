"""Align two versions of the Davis-Stirling Act provision by provision, and score the alignment against the gold.

Two cases:

**The recodification** (``recodification``). Former Civil Code 1350-1378 as the 2011 edition prints it against
4000-6150 as the 2013 edition prints it. The Law Revision Commission's disposition table is the gold
(``data/authorities/history/former-sections.json``, written by ``jason law-history --export``), so every variant
(structure only, lexical, embedding, the model judge) is scored on the same former units before any is trusted.

**An amendment** (``amended``). One current section as two consecutive editions print it (CIV 5855, 2023 and 2025),
old subdivisions against new ones within the section. There is no table: a unit whose words did not change is matched
by the text itself (``source="text_identity"``), the rest by the model (``source="model"``), each with its verified
quotes and a confidence. These rows are leads, never pins.

Statute text comes from lawlibrary through ``jason.sources.lawlibrary`` (``LawLibrary.editions``) and is kept under
``data/authorities/history/alignment/editions`` so a rerun does not ask again. Results are written as JSON under
``data/authorities/history/alignment`` with their run metadata.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from jason.community import statute_alignment as sa
from jason.community.succession import CHANGES_FILE, FORMER_FILE, HISTORY_DIR

ALIGN_DIR = "authorities/history/alignment"
FORMER_SPAN = ("CIV", "1350", "1378", "2011")
CURRENT_SPAN = ("CIV", "4000", "6150", "2013")
# Fifteen former sections across the Act's chapters: definitions, governing documents, operating rules, the
# association and its hearings, elections, finances, assessments, transfer disclosure, ADR, and construction defects.
SAMPLE = ("1351", "1354", "1356", "1357.130", "1360", "1363", "1363.03", "1363.810", "1365", "1365.5", "1366",
          "1367.1", "1368", "1369.520", "1375")
LEXICAL_FLOOR = 0.25
EMBEDDING_FLOOR = 0.6


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def align_dir(data_dir: Path) -> Path:
    path = Path(data_dir) / ALIGN_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------- statute text


def edition(lawlibrary: Any, data_dir: Path, span: tuple[str, str, str, str]) -> dict[str, Any]:
    """One span as one session printed it ({"sections": [{"section", "text", "path"}], "nodes": [...]}), kept on disk."""
    code, start, end, session = span
    path = align_dir(data_dir) / "editions" / f"{code}-{start}-{end}-{session}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    got = lawlibrary.editions([span])
    if not got or not got[0].found:
        return {"code": code, "start": start, "end": end, "session": session, "sections": [], "nodes": []}
    e = got[0]
    data = {"code": code, "start": start, "end": end, "session": e.session or session, "fetched": _now(),
            "sections": [{"section": s.number, "citation": s.citation, "text": s.text, "path": list(s.path), "history": s.history}
                         for s in e.sections],
            "nodes": [n.__dict__ for n in e.nodes]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return data


def units_of(data: dict[str, Any], only: Iterable[str] | None = None) -> list[sa.Unit]:
    wanted = set(only) if only is not None else None
    out: list[sa.Unit] = []
    for s in data.get("sections") or []:
        if wanted is not None and s["section"] not in wanted:
            continue
        group = (s.get("path") or [""])[-1]
        out += sa.subdivisions(s["section"], s.get("text") or "", group=group, session=str(data.get("session") or ""))
    return out


# ---------------------------------------------------------------- the recodification


def _gold_doc(data_dir: Path) -> dict[str, Any]:
    path = Path(data_dir) / HISTORY_DIR / FORMER_FILE
    if not path.is_file():
        raise FileNotFoundError(f"{path} is not on disk; run jason law-history --export")
    return json.loads(path.read_text(encoding="utf-8"))


def _vectors(embedder: Any, units: Sequence[sa.Unit]) -> dict[str, list[float]]:
    texts = [u.text[:4000] for u in units]
    return {u.id: v for u, v in zip(units, embedder.embed_passages(texts))}


def _fingerprint(cs: sa.CandidateSet, model: str) -> str:
    h = hashlib.sha256()
    h.update(model.encode())
    h.update(sa.PROMPT.encode())
    for u in (*cs.former, *cs.candidates):
        h.update(u.id.encode())
        h.update(u.text.encode())
    return h.hexdigest()[:16]


def _match(d: dict[str, Any]) -> sa.Match:
    return sa.Match(**{k: v for k, v in d.items() if k in sa.Match.__dataclass_fields__})


def recodification(data_dir: Path, lawlibrary: Any, *, sections: Sequence[str] | None = None, judge: Any = None,
                   embedder: Any = None, structure: str = "gold+outline", progress: Callable[[str], None] | None = None,
                   write: bool = True, label: str = "") -> dict[str, Any]:
    """Align the former sections (all, or ``sections``) and score every variant against the disposition table.

    ``structure`` is "gold+outline" (other sections' official rows and the headings) or "outline" (the headings and
    their text alone, as an act with no table would have). ``judge`` (``OllamaJudge``) adds the model variant; it is
    asked once per former unit, and a section already judged with the same candidates and model is read from disk."""
    say = progress or (lambda _m: None)
    gold_doc = _gold_doc(data_dir)
    former_data = edition(lawlibrary, data_dir, FORMER_SPAN)
    current_data = edition(lawlibrary, data_dir, CURRENT_SPAN)
    former_all = units_of(former_data)
    current = units_of(current_data)
    if not former_all or not current:
        raise RuntimeError("lawlibrary returned no text for one of the editions; nothing aligned")
    gold = sa.read_gold(gold_doc, former_all)
    scope = list(sections) if sections else list(dict.fromkeys(u.section for u in former_all))
    missing = [s for s in scope if not any(u.section == s for u in former_all)]
    scope = [s for s in scope if s not in missing]
    tfidf = sa.Tfidf([u.text for u in (*former_all, *current)])
    vectors: dict[str, list[float]] = {}
    embed_seconds = None
    if embedder is not None:
        started = time.monotonic()
        vectors = _vectors(embedder, [u for u in former_all if u.section in scope] + current)
        embed_seconds = round(time.monotonic() - started, 1)
    gold_pairs = sorted(gold.section_pairs) if structure.startswith("gold") else []
    cache_dir = align_dir(data_dir) / "llm-cache"
    found: dict[str, list[sa.Match]] = {v.value: [] for v in sa.Variant}   # plus the two combinations, below
    per_section: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    candidate_recall = {"unit_pairs": 0, "in_candidates": 0}
    for number in scope:
        units = [u for u in former_all if u.section == number]
        smap = sa.structure_map(former_all, current, tfidf, gold_pairs=gold_pairs, exclude_section=number)
        cs = sa.candidates(units, current, tfidf, smap, vectors=vectors or None)
        cand_sections = {c.section for c in cs.candidates}
        for f, t in gold.unit_pairs:
            if sa._section_of(f) == number:
                candidate_recall["unit_pairs"] += 1
                candidate_recall["in_candidates"] += t in cand_sections
        found["structure"] += sa.structure_matches(cs)
        found["lexical"] += sa.similarity_matches(cs, method="lexical", floor=LEXICAL_FLOOR)
        if vectors:
            found["embedding"] += sa.similarity_matches(cs, method="embedding", floor=EMBEDDING_FLOOR)
        row: dict[str, Any] = {"section": number, "units": len(units), "candidates": len(cs.candidates),
                               "origins": dict(sorted(_count(cs.origin.values()).items())),
                               "mapped_headings": {u.group: smap.targets(u.group) for u in units[:1]}}
        if judge is not None:
            key = _fingerprint(cs, getattr(judge, "model", ""))
            cached = cache_dir / f"{number}.json"
            hit = json.loads(cached.read_text(encoding="utf-8")) if cached.is_file() else None
            if hit and hit.get("fingerprint") == key:
                result = {"matches": [_match(m) for m in hit["matches"]], "dropped": hit["dropped"],
                          "requests": hit["requests"], "errors": hit.get("errors", [])}
                row["cached"] = True
            else:
                say(f"judging {number}: {len(units)} units against {len(cs.candidates)} candidates")
                started = time.monotonic()
                result = sa.judge_section(cs, judge, former_edition=f"{FORMER_SPAN[3]} edition (former Civil Code)",
                                          current_edition=f"{CURRENT_SPAN[3]} edition (Civil Code as recodified)")
                row["seconds"] = round(time.monotonic() - started, 1)
                cache_dir.mkdir(parents=True, exist_ok=True)
                cached.write_text(json.dumps({"fingerprint": key, "section": number, "judged": _now(),
                                              "seconds": row["seconds"], "matches": [m.to_dict() for m in result["matches"]],
                                              "dropped": result["dropped"], "requests": result["requests"],
                                              "errors": result["errors"]}, indent=1, ensure_ascii=False), encoding="utf-8")
            row["seconds"] = row.get("seconds") or round(sum(r["seconds"] for r in result["requests"]), 1)
            row["requests"] = len(result["requests"])
            row["errors"] = result["errors"]
            row["kept"], row["dropped"] = len(result["matches"]), len(result["dropped"])
            found["llm"] += result["matches"]
            dropped += result["dropped"]
            say(f"  {number}: {row['kept']} verified, {row['dropped']} set aside, {row['seconds']} s")
        per_section.append(row)
    if judge is not None:
        # Two readings together: the model's matches the lexical baseline also finds (a high-precision tier), and
        # either one's (a high-recall tier).
        lex = {(m.former, m.current_section) for m in found["lexical"]}
        llm = {(m.former, m.current_section) for m in found["llm"]}
        found["llm_and_lexical"] = [m for m in found["llm"] if (m.former, m.current_section) in lex]
        found["llm_or_lexical"] = found["llm"] + [m for m in found["lexical"] if (m.former, m.current_section) not in llm]
    full = set(scope) == {u.section for u in former_all}
    current_scope = [u.section for u in current] if full else []
    evaluation = {v: sa.evaluate(ms, gold, scope, current_scope=current_scope) for v, ms in found.items() if ms or v != "embedding"}
    if judge is None:
        evaluation.pop("llm", None)
    in_scope = [u for u in former_all if u.section in scope]
    best = "llm" if judge is not None else "lexical"
    timed = [r["seconds"] for r in per_section if r.get("seconds") is not None and not r.get("cached")]
    result: dict[str, Any] = {
        "kind": "recodification",
        "run": {"at": _now(), "label": label, "former": "-".join(FORMER_SPAN[1:3]) + f" ({former_data.get('session')})",
                "current": "-".join(CURRENT_SPAN[1:3]) + f" ({current_data.get('session')})", "sections": scope,
                "missing": missing, "structure": structure, "model": getattr(judge, "model", None),
                "embedder": getattr(embedder, "model", None), "embed_seconds": embed_seconds,
                "floors": {"lexical": LEXICAL_FLOOR, "embedding": EMBEDDING_FLOOR},
                "units": len(in_scope), "current_units": len(current),
                "seconds_per_section": round(sum(timed) / len(timed), 1) if timed else None,
                "requests": sum(r.get("requests", 0) for r in per_section),
                "gold_unread_parts": gold.unread_parts},
        "candidate_recall": {**candidate_recall, "recall": round(candidate_recall["in_candidates"] / candidate_recall["unit_pairs"], 3)
                             if candidate_recall["unit_pairs"] else None},
        "evaluation": evaluation,
        "sections": per_section,
        "former": sa.per_former(in_scope, found[best]),
        "current": sa.per_current([c for c in current if full or c.section in {m.current_section for m in found[best]}], found[best]),
        "dropped": dropped,
        "caveat": "A model or similarity reading is evidence, never a pin; the disposition table is the pin.",
    }
    if write:
        name = f"recodification{('-' + label) if label else ''}.json"
        (align_dir(data_dir) / name).write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        result["written"] = str(align_dir(data_dir) / name)
    return result


def _count(values: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


# ---------------------------------------------------------------- amended sections


def amendments(data_dir: Path, section: str = "") -> list[dict[str, Any]]:
    """The stored amendments to the current Act (changes.json), oldest first: (section, before, after, statute)."""
    path = Path(data_dir) / HISTORY_DIR / CHANGES_FILE
    if not path.is_file():
        return []
    rows = [c for block in json.loads(path.read_text(encoding="utf-8")).get("changes", []) for c in block.get("changes") or []]
    out = [{"section": c["section"], "before": c["before"], "after": c["after"], "statute": c.get("statute") or "",
            "summary": c.get("summary") or ""}
           for c in rows if c.get("change") == "amended" and "4000" <= str(c.get("section") or "") <= "6150"
           and sa._num(str(c.get("section"))) >= (4000.0,)]
    if section:
        out = [c for c in out if c["section"] == section]
    return out


def align_amendment(old: Sequence[sa.Unit], new: Sequence[sa.Unit], judge: Any, *, before: str, after: str) -> dict[str, Any]:
    """Old subdivisions to new within one section: identical words first (a moved letter included), the model for the
    rest against every new subdivision."""
    tfidf = sa.Tfidf([u.text for u in (*old, *new)])
    norm = lambda u: sa._fold(sa.strip_label(u.text))  # noqa: E731
    new_by_text: dict[str, list[sa.Unit]] = {}
    for u in new:
        new_by_text.setdefault(norm(u), []).append(u)
    matches: list[sa.Match] = []
    rest: list[sa.Unit] = []
    used: set[str] = set()
    for u in old:
        same = [n for n in new_by_text.get(norm(u), []) if n.id not in used]
        if same:
            used.add(same[0].id)
            matches.append(sa.Match(u.id, same[0].id, sa.Relation.CONTINUED_WITHOUT_SUBSTANTIVE_CHANGE.value, "identical",
                                    1.0, confidence="high", source="text_identity"))
        else:
            rest.append(u)
    requests: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    if rest and judge is not None:
        vecs = {u.id: tfidf.vector(u.text) for u in new}
        lexical = {f.id: {c.id: sa.cosine(tfidf.vector(f.text), vecs[c.id]) for c in new} for f in rest}
        cs = sa.CandidateSet(tuple(rest), tuple(new), lexical, {}, {c.id: "section" for c in new})
        # Old and new share the section number: the candidates are named by edition so the ids differ.
        result = sa.judge_section(cs, judge, former_edition=f"{before} edition", current_edition=f"{after} edition")
        matches += result["matches"]
        dropped, requests = result["dropped"], result["requests"]
    for m in matches:
        m.source = m.source if m.method == "identical" else "model"
    return {"matches": matches, "dropped": dropped, "requests": requests, "unjudged": [u.id for u in rest] if judge is None else []}


def amended(data_dir: Path, lawlibrary: Any, judge: Any, *, section: str = "", before: str = "", after: str = "",
            progress: Callable[[str], None] | None = None, write: bool = True) -> dict[str, Any]:
    """Each amended section (one, or every one in changes.json) old subdivisions to new; rows are leads."""
    say = progress or (lambda _m: None)
    if section and before and after:
        todo = [{"section": section, "before": before, "after": after, "statute": "", "summary": ""}]
    else:
        todo = amendments(data_dir, section)
    out_rows: list[dict[str, Any]] = []
    for c in todo:
        old_data = edition(lawlibrary, data_dir, ("CIV", "4000", "6150", c["before"]))
        new_data = edition(lawlibrary, data_dir, ("CIV", "4000", "6150", c["after"]))
        old = units_of(old_data, [c["section"]])
        new = units_of(new_data, [c["section"]])
        if not old or not new:
            out_rows.append({**c, "found": False, "reason": "no text for one edition"})
            continue
        say(f"CIV {c['section']} {c['before']} -> {c['after']}: {len(old)} old, {len(new)} new subdivisions")
        started = time.monotonic()
        res = align_amendment(old, new, judge, before=c["before"], after=c["after"])
        seconds = round(time.monotonic() - started, 1)
        ms: list[sa.Match] = res["matches"]
        old_rows = []
        for row in sa.per_former(old, ms):
            for t in row["targets"]:
                t["moved"] = sa._label_of(t["former"]) != sa._label_of(t["current"])
            old_rows.append(row)
        continued = {m.current for m in ms}
        out_rows.append({**c, "found": True, "seconds": seconds, "requests": len(res["requests"]),
                         "old": old_rows,
                         "new": [{"current": n.id, "relation": sa.Relation.NEW.value} for n in new if n.id not in continued],
                         "moves": [f"{m.former} -> {m.current}" for m in ms if sa._label_of(m.former) != sa._label_of(m.current)],
                         "changes": [{"former": m.former, "current": m.current, "change": m.change,
                                      "change_former": m.change_former, "change_current": m.change_current,
                                      "confidence": m.confidence} for m in ms if m.change],
                         "dropped": res["dropped"], "unjudged": res["unjudged"]})
    result = {"kind": "amended", "run": {"at": _now(), "model": getattr(judge, "model", None), "sections": len(out_rows)},
              "rows": out_rows,
              "caveat": "source=model rows are the local model's verified readings and source=text_identity rows are "
                        "unchanged words; both are leads, never pins. The statute text in force is the law."}
    if write:
        name = f"amended-{section}.json" if section else "amended.json"
        path = align_dir(data_dir) / name
        path.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        result["written"] = str(path)
    return result


__all__ = ["SAMPLE", "recodification", "amended", "amendments", "align_amendment", "edition", "units_of", "ALIGN_DIR"]
