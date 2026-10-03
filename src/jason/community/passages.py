"""Search the text extracts by passage, for the question a person asks of the documents.

Which instrument reserves the easement over A.C.A. 3? Which section sets
the assessment lien threshold? The answer is a passage in one of the
extracts, and this module finds it: each extract is cut into passages of a
few hundred words, the passages are ranked by BM25 over the query's words,
and a hit says which file, where in it, and the passage. It is search, not
extraction: the passage is for the person to read, and nothing here pins a
fact. A better ranker (embeddings) can replace ``rank`` without changing
the passages or the hits.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

_WORD = re.compile(r"[a-z0-9][a-z0-9.'-]*")
_STOP = frozenset("the of and to a in for or by as is at that this with on be shall any such its from which are an all it not".split())
PASSAGE_WORDS = 220
OVERLAP_WORDS = 40


@dataclass(frozen=True)
class Passage:
    path: Path
    index: int
    start_word: int
    text: str                      # the document's own words, for display and recitation
    heading: str = ""              # the section's path ("Bylaws > 7 MEETINGS > 7.2 Notice"), read by the rankers only

    @property
    def title(self) -> str:
        return self.path.name

    @property
    def ranked(self) -> str:
        """What the rankers read: the section's path, then the words."""
        return f"{self.heading}\n{self.text}" if self.heading else self.text


@dataclass(frozen=True)
class Hit:
    passage: Passage
    score: float
    also: tuple[Passage, ...] = ()     # near copies of the passage folded under it (``retrieval.collapse``)


def passages_of(path: Path, text: str | None = None) -> tuple[Passage, ...]:
    """Cut one extract into overlapping passages of about ``PASSAGE_WORDS`` words."""
    body = text if text is not None else path.read_text(encoding="utf-8", errors="ignore")
    words = body.split()
    found: list[Passage] = []
    start = 0
    index = 0
    while start < len(words):
        chunk = words[start: start + PASSAGE_WORDS]
        found.append(Passage(path, index, start, " ".join(chunk)))
        index += 1
        if start + PASSAGE_WORDS >= len(words):
            break
        start += PASSAGE_WORDS - OVERLAP_WORDS
    return tuple(found)


def corpus(*folders: Path | str, suffixes: tuple[str, ...] = (".md", ".txt"), chunking: str = "windows",
           outlines: Path | str | None = None) -> tuple[Passage, ...]:
    """Every extract's passages under ``folders``. ``chunking`` is "windows" (``passages_of``) or "sections"
    (``passage_sections.section_passages``, which places the outlines in the folder ``outlines`` on the extracts)."""
    if chunking not in ("windows", "sections"):
        raise ValueError(f"unknown chunking {chunking!r}: windows or sections")
    index = None
    if chunking == "sections":
        from jason.community.passage_sections import OutlineIndex

        index = OutlineIndex.load(outlines)
    found: list[Passage] = []
    for folder in folders:
        root = Path(folder)
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in suffixes:
                if index is None:
                    found.extend(passages_of(path))
                else:
                    from jason.community.passage_sections import section_passages

                    found.extend(section_passages(path, outlines=index))
    return tuple(found)


def _fold(word: str) -> str:
    """A word's ranking form: trailing punctuation off ("fines." is "fines"; "5310.5" and "b-16" keep theirs inside), and
    a plain plural folded ("fines" is "fine", "policies" is "policy"; "process" and "bylaws'" stay whole words)."""
    word = word.rstrip(".'-")
    if len(word) > 4 and word.isalpha():
        if word.endswith("ies"):
            return word[:-3] + "y"
        if word.endswith("s") and not word.endswith(("ss", "us", "is")):
            return word[:-1]
    return word


def tokens(text: str) -> list[str]:
    return [folded for word in _WORD.findall(text.lower()) if word not in _STOP and (folded := _fold(word)) and folded not in _STOP]


def rank(query: str, items: tuple[Passage, ...], *, k: int = 8, k1: float = 1.5, b: float = 0.75) -> tuple[Hit, ...]:
    """BM25 over the passages' words; the top ``k`` with a positive score."""
    wanted = tokens(query)
    if not wanted or not items:
        return ()
    docs = [tokens(p.ranked) for p in items]
    n = len(docs)
    avg = sum(len(d) for d in docs) / n
    df: dict[str, int] = {}
    for d in docs:
        for term in set(d):
            df[term] = df.get(term, 0) + 1
    hits: list[Hit] = []
    for passage, d in zip(items, docs):
        if not d:
            continue
        counts: dict[str, int] = {}
        for term in d:
            counts[term] = counts.get(term, 0) + 1
        score = 0.0
        for term in wanted:
            tf = counts.get(term, 0)
            if not tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * len(d) / avg))
        if score > 0:
            hits.append(Hit(passage, round(score, 3)))
    hits.sort(key=lambda hit: (-hit.score, hit.passage.path.name, hit.passage.index))
    return tuple(hits[:k])


def search(query: str, *folders: Path | str, k: int = 8) -> tuple[Hit, ...]:
    return rank(query, corpus(*folders), k=k)
