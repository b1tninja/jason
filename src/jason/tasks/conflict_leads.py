"""Leads for the conflict register: written provisions that a later change in the law speaks to.

A provision usually stops holding because the law changed after it was written (``authority_order.Conflict``). This
reads the association's documents, as ``jason outlines`` stored them, against the Davis-Stirling Act's changes since the
2014 recodification, as ``jason law-history --export`` stored them, two ways:

- **cites**: a section of the document cites a changed section, by its current number or a former one;
- **subject**: the document's section is among the passages that best match the changed section's words (BM25 over the
  section's current text and the words the change inserted). A document need not cite a statute to be governed by it.

A change counts for a document when it became operative after the document was written (``CitableDocument.written``).
A written year alone counts changes in that same year, which may be after it, and an unknown date counts every change.
A change already on a ``Conflict`` row is marked with that row. A lead is a reason for a person to read two texts side
by side: most are not conflicts (the document may already comply, or ask more than the law's minimum), and the ones
that are become ``Conflict`` rows in the specification. The Act is the law read here; other codes are not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jason.community import succession
from jason.community.passages import Passage, rank, tokens

MIN_WORDS = 10                        # an amendment that changed fewer words is a correction, not a lead
TOP = 6                               # passages kept per change, across every document
NEAR_TOP = 0.6                        # a passage scoring under this share of the change's best is left out
QUERY_WORDS = 250
COMMON = 0.2                          # a word in more than this share of the changed sections is the Act's vocabulary
_HISTORY = re.compile(r"^\s*-\s*History:.*$|^\s*\d+(?:\.\d+)*\.\s*\((?:Added|Amended|Repealed)[^)]*\)\s*", re.M)
_SECTION_NUMBER = re.compile(r"\d{4}(?:\.\d+)*")


@dataclass(frozen=True)
class Change:
    citation: str                     # "CIV 5850"
    section: str                      # "5850"
    action: str                       # amended, added
    statute: str
    bill: str
    when: str                         # operative (or effective) date, or the edition year
    summary: str
    inserted: str                     # the words the change inserted, as the diff gives them


@dataclass(frozen=True)
class Lead:
    document: str                     # the outline's key
    title: str
    written: str
    change: Change
    route: str                        # "cites" or "subject"
    section: str                      # the document's section that speaks to it
    quote: str
    score: float = 0.0
    recorded: str = ""                # the Conflict row that already records it


def changes(data_dir: Path, *, min_words: int = MIN_WORDS) -> list[Change]:
    """The Act's changes since the 2014 recodification that changed at least ``min_words`` words (an addition always
    counts), newest last."""
    out = []
    for c in succession.changes(data_dir):
        section = str(c.get("section") or "")
        if not _SECTION_NUMBER.fullmatch(section) or int(section.split(".")[0]) < 4000:
            continue
        action = str(c.get("action") or c.get("change") or "")
        if action not in ("amended", "added", "repealed and added"):
            continue
        if succession.RECODIFIED in str(c.get("statute") or ""):
            continue
        if c.get("change") == "added":
            action = "added"             # new between editions, whatever the history note calls the act
        diff = c.get("diff") or {}
        words = sum(int(diff.get(k) or 0) for k in ("inserted", "deleted", "replaced"))
        if action == "amended" and diff and words < min_words:
            continue                     # a small edit; a change of unknown size still counts
        inserted = " ".join(str(h.get("after") or "") for h in diff.get("hunks") or [])
        out.append(Change(str(c.get("citation") or f"CIV {section}"), section, action, str(c.get("statute") or ""),
                          str(c.get("bill") or ""), str(c.get("operative") or c.get("effective") or c.get("after") or ""),
                          str(c.get("summary") or ""), inserted))
    return sorted(out, key=lambda c: (c.when, c.citation))


def after(written: str, when: str) -> bool:
    """Whether a change on ``when`` may postdate a document written on ``written`` ("2022", "2007-09-17", or "")."""
    return not written or not when or when[:len(written)] >= written


def _query(data_dir: Path, change: Change) -> str:
    from jason.tasks.export_authorities import authority_text

    text = str(authority_text(Path(data_dir), change.citation).get("text") or "")
    words = _HISTORY.sub(" ", text).split()[:QUERY_WORDS]
    return " ".join(words) + " " + change.inserted


def section_passages(outline: Any) -> list[tuple[Passage, str]]:
    """Each section's own text (up to the next section's start) as a passage, with the section's name."""
    sections = sorted(outline.sections, key=lambda s: s.start)
    out = []
    for i, s in enumerate(sections):
        end = sections[i + 1].start if i + 1 < len(sections) else len(outline.text)
        text = outline.text[s.start:end].strip()
        if len(text.split()) >= 15:
            out.append((Passage(Path(outline.key), i, 0, text), s.name))
    return out


def _cited_sections(rows: list[dict[str, Any]], data_dir: Path) -> dict[str, list[tuple[str, str, str]]]:
    """Each document's statute citations as current sections: key -> [(section, document section, quote)]."""
    from jason.community.references import statute_key

    out: dict[str, list[tuple[str, str, str]]] = {}
    for r in rows:
        if r.get("kind") != "statute" or not str(r.get("target", "")).startswith("CIV "):
            continue
        base, _ = statute_key(str(r["target"]))
        number = base.split()[-1]
        current = [number]
        if r.get("prior") or (_SECTION_NUMBER.fullmatch(number) and int(number.split(".")[0]) < 4000):
            current = [t.split()[-1] for s in succession.successors(data_dir, number) for t in s.targets] or current
        for n in dict.fromkeys(current):
            out.setdefault(str(r.get("source")), []).append((n, str(r.get("source_section") or ""),
                                                             str(r.get("quote") or "")))
    return out


def _recorded(community: Any, section: str) -> str:
    from jason.community.authority_order import conflicts

    pattern = re.compile(rf"(?<![\d.]){re.escape(section)}(?![\d])")
    return next((c.key for c in conflicts(community) if pattern.search(c.authority)), "")


def leads(data_dir: Path, community: Any, *, document: str = "", since: str = "", min_words: int = MIN_WORDS
          ) -> list[Lead]:
    """Every lead, by document, then change. ``document`` narrows to one outline key; ``since`` to changes operative on
    or after a date (the year's new laws)."""
    from jason.tasks import outlines as outline_store

    specs = {d.key: d for d in community.citable_documents()}
    # Every document is ranked together (a score means something only against the others); ``document`` filters after.
    found = [o for o in outline_store.load(Path(data_dir)) if o.key in specs or o.kind == "resolution"]
    if not found:
        return []
    corpus: list[Passage] = []
    names: dict[tuple[str, int], str] = {}
    for o in found:
        for passage, name in section_passages(o):
            corpus.append(passage)
            names[(o.key, passage.index)] = name
    titles = {o.key: o.title for o in found}
    written = {o.key: getattr(specs.get(o.key), "written", "") for o in found}
    cited = _cited_sections(outline_store.load_rows(Path(data_dir)), Path(data_dir))
    items = tuple(corpus)
    found_changes = changes(Path(data_dir), min_words=min_words)
    queries = {c: tokens(_query(Path(data_dir), c)) for c in found_changes}
    # Words most of the Act uses ("separate interest", "association") say nothing about a section's subject: leave them
    # out, so the words that set it apart ("rental", "lease") decide which passage speaks to it.
    df: dict[str, int] = {}
    for words in queries.values():
        for w in set(words):
            df[w] = df.get(w, 0) + 1
    common = {w for w, n in df.items() if n > max(2, COMMON * len(queries))}
    out: list[Lead] = []
    seen: set[tuple[str, str, str]] = set()
    for change in found_changes:
        recorded = _recorded(community, change.section)
        for key in titles:
            if not after(written[key], change.when):
                continue
            for number, where, quote in cited.get(key, []):
                if number == change.section and (key, change.citation, change.when) not in seen:
                    seen.add((key, change.citation, change.when))
                    out.append(Lead(key, titles[key], written[key], change, "cites", where, quote[:240],
                                    recorded=recorded))
        hits = rank(" ".join(w for w in queries[change] if w not in common), items, k=TOP)
        if not hits:
            continue
        best = hits[0].score
        for hit in hits:
            key = str(hit.passage.path)
            if hit.score < NEAR_TOP * best or not after(written[key], change.when):
                continue
            if (key, change.citation, change.when) in seen:
                continue
            seen.add((key, change.citation, change.when))
            out.append(Lead(key, titles[key], written[key], change, "subject", names[(key, hit.passage.index)],
                            " ".join(hit.passage.text.split())[:240], hit.score, recorded))
    order = {k: i for i, k in enumerate(titles)}
    out = [l for l in out if (not document or l.document == document) and (not since or l.change.when >= since)]
    return sorted(out, key=lambda l: (order[l.document], l.change.when, l.change.citation))


def lines(found: list[Lead], community: Any = None) -> list[str]:
    """The leads as Markdown, by document: each change that may postdate it and the section that speaks to it."""
    specs = {d.key: d for d in community.citable_documents()} if community is not None else {}
    out: list[str] = []
    current = None
    for l in found:
        if l.document != current:
            current = l.document
            spec = specs.get(l.document)
            when = (f"written {l.written}" + (f" ({spec.written_from})" if spec and spec.written_from else "")
                    if l.written else "date unknown: every change since 2014 is counted")
            out += ["", f"### {l.title}", f"_{when}_", ""]
        c = l.change
        tag = f"; recorded as {l.recorded}" if l.recorded else ""
        out.append(f"- **{c.citation}** {c.action} by {c.statute}{' (' + c.bill + ')' if c.bill else ''}, "
                   f"operative {c.when or '?'} [{l.route}{tag}]. Section {l.section or '?'}: \"{l.quote}\"")
    return out[1:] if out and out[0] == "" else out


__all__ = ["Change", "Lead", "after", "changes", "leads", "lines", "section_passages"]
