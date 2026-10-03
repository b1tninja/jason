"""Where the answer to a member's request is likely written: leads for the person answering, never the answer.

For each request (``responses.Handled``) it gathers:
- **passages and library documents by topic** (``intents.answer_sources``): the governing documents' passages that
  match the topic's query and the request's words, and the library's documents of the kinds that speak to the topic;
- **catalog documents by name** (``request_review.significant_words``): PayHOA library files whose names share words
  with the request, the most shared first;
- **precedents** for a complaint: the PayHOA violations on the same conduct, how the association handled it before;
- **PayHOA's own reading**: its AI analysis of the request, when PayHOA holds one, as a lead and never a kind.

Every item is a lead. A passage is ranked by word overlap and is not a ruling; a document named like the request may not
speak to it; a precedent is a pattern, not a decision. It reads disk only.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from jason.community.responses import ResponseKind
from jason.community.topics import Topic

CAVEATS = (
    "Leads, not answers: a passage is ranked by word overlap and is not a ruling; read it in its document.",
    "A document named like the request may not speak to it.",
    "A precedent shows how the association handled that conduct before; a new complaint still needs its own facts, notice, "
    "and hearing.",
    "PayHOA's AI analysis, when present, is PayHOA's reading of the request, not jason's classification.",
)
_PRECEDENT_KINDS = (ResponseKind.COMPLAINT, ResponseKind.HEARING_REQUEST)


def _catalog(data_dir: Path) -> list[tuple[str, str]]:
    """The PayHOA library's files: (name, path)."""
    path = Path(data_dir) / "payhoa.db"
    if not path.is_file():
        return []
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return [(str(n), str(p or "")) for n, p in conn.execute("SELECT file_name, path FROM documents WHERE directory = 0")]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _name_words(name: str) -> set[str]:
    from jason.tasks.request_review import significant_words

    return {w for w in significant_words(re.sub(r"\.\w{2,4}$", "", name)) if not w.isdigit()}


def common_words(catalog: list[tuple[str, str]], *, share: float = 0.02) -> set[str]:
    """Words in more than ``share`` of the library's names: the association's own name, its streets, "statement",
    "attachments". A match on them says nothing about the request."""
    from collections import Counter

    counts = Counter(w for name, _ in catalog for w in _name_words(name))
    floor = max(3, int(len(catalog) * share))
    return {w for w, n in counts.items() if n > floor}


def address_words(data_dir: Path, community: Any = None) -> set[str]:
    """The words of the association's unit addresses and of its name: a unit's street in a request matches every
    document about another unit on that street."""
    from jason.tasks.request_review import significant_words

    words = significant_words(str(getattr(community, "name", "") or ""))
    path = Path(data_dir) / "payhoa.db"
    if path.is_file():
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            for (label,) in conn.execute("SELECT label FROM units"):
                words |= significant_words(str(label or ""))
        except sqlite3.Error:
            pass
        finally:
            conn.close()
    return {w for w in words if not w.isdigit()}


def catalog_matches(text: str, catalog: list[tuple[str, str]], *, common: set[str] | None = None, limit: int = 3,
                    at_least: int = 2) -> list[dict[str, Any]]:
    """Library files whose names share at least ``at_least`` uncommon words with ``text`` (one, if the name has only
    one), the most shared first; each name once."""
    from jason.tasks.request_review import significant_words

    skip = common if common is not None else common_words(catalog)
    words = {w for w in significant_words(text) if not w.isdigit()} - skip
    found, seen = [], set()
    for name, path in catalog:
        own = _name_words(name)
        shared = words & own
        if not shared or len(shared) < min(at_least, len(own)) or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        found.append((-len(shared), name, path, sorted(shared)))
    found.sort()
    return [{"name": n, "path": p, "shared": s} for _n, n, p, s in found[:limit]]


class SourceContext:
    """What every request's leads draw on, loaded once: the violations, the library, the catalog, and a cache."""

    def __init__(self, data_dir: Path, community: Any = None) -> None:
        from jason.tasks.intents import _library, _violations

        self.data_dir = Path(data_dir)
        self.violations = _violations(self.data_dir)
        self.library = _library(self.data_dir)
        self.catalog = _catalog(self.data_dir)
        self.common = common_words(self.catalog) | address_words(self.data_dir, community)
        self.cache: dict = {}


def _words_of(request: dict[str, Any]) -> str:
    return f"{request.get('title') or ''} {str(request.get('message') or '')[:200]}".strip()


def sources_for(h: Any, community: Any, ctx: SourceContext) -> dict[str, Any]:
    """The leads for one request."""
    from jason.tasks.intents import answer_sources

    r = h.request
    text = _words_of(r)
    topics = list(r.get("topics") or [])
    if h.kind in _PRECEDENT_KINDS and not topics:
        topics = [Topic.NEIGHBORS.value]
    out: dict[str, Any] = {"topics": {}, "documents": [], "precedents": []}
    names: set[str] = set()
    for topic in topics[:2]:
        found = answer_sources(topic, text, ctx.data_dir, community, cache=ctx.cache, violations=ctx.violations,
                               library=ctx.library)
        if not found:
            continue
        out["topics"][topic] = {"passages": [{k: p[k] for k in ("file", "passage", "score", "text")}
                                             for p in found.get("passages", [])],
                                "documents": found.get("documents", [])}
        names |= {d["name"].casefold() for d in found.get("documents", [])}
        if h.kind in _PRECEDENT_KINDS:
            for v in found.get("precedents", []):
                if all(v["id"] != p["id"] for p in out["precedents"]):
                    out["precedents"].append({k: v[k] for k in ("id", "title", "reported", "status")})
    out["documents"] = [d for d in catalog_matches(text, ctx.catalog, common=ctx.common) if d["name"].casefold() not in names]
    ai = (r.get("payhoa") or {}).get("aiAnalysis")
    if ai:
        out["payhoaAnalysis"] = ai if isinstance(ai, str) else json.dumps(ai)[:400]
    return out


def source_lines(src: dict[str, Any], *, indent: str = "    ") -> list[str]:
    """The leads, a line each, labelled as leads."""
    out = []
    for topic, found in src.get("topics", {}).items():
        for p in found.get("passages", [])[:1]:
            out.append(f"{indent}lead ({topic}): {p['file']} #{p['passage']}: {p['text'][:110]}...")
        for d in found.get("documents", [])[:1]:
            out.append(f"{indent}lead ({topic}): {d['kind']} {d['name'][:70]}")
    for d in src.get("documents", []):
        out.append(f"{indent}lead (named like it): {d['path'] or d['name']}")
    for v in src.get("precedents", [])[:3]:
        out.append(f"{indent}precedent: violation {v['id']} {v['reported']} {v['title']} ({v['status']})")
    if src.get("payhoaAnalysis"):
        out.append(f"{indent}PayHOA's AI analysis (a lead, not a kind): {src['payhoaAnalysis'][:160]}")
    return out or [f"{indent}no lead found"]


__all__ = ["CAVEATS", "SourceContext", "catalog_matches", "source_lines", "sources_for"]
