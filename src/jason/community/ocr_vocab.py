"""Candidates by search of the vocabulary, scored by the OCR channel.

``ocr_correct.candidates`` makes the words an OCR misread could have been by applying edits to the word read and keeping
the ones the lexicon knows: at most one arbitrary letter edit and one confusion. A word read two or three letters wrong
at once ("condominiwn", "pcnnitted") is out of its reach, and so is anything a rule of the learned channel makes of
several letters. This module goes the other way: it finds every word of the vocabulary within a few edits of the word
read (all of them at once, in numpy), then scores each by the channel's best alignment (Brill and Moore's idea: the
probability that a recognizer reads those letters for the printed ones, with a rule for a letter group where the channel
has one and a small chance for any other edit).
"""

from __future__ import annotations

import math
import re
from typing import Iterable

from jason.community.ocr_channel import Channel

LOG_EDIT = math.log(0.001)
LOG_JUNK = math.log(0.02)


def available() -> bool:
    """Whether numpy, which the vocabulary search needs, is installed."""
    try:
        import numpy  # noqa: F401
    except ImportError:
        return False
    return True


def channel_cost(read: str, printed: str, channel: Channel | None, *, edit: float = LOG_EDIT) -> float:
    """The best log probability that ``printed`` was read as ``read``: letters kept cost nothing; a rule of the channel
    covers a group of letters at its own probability; any other letter added, dropped, or changed costs ``edit``
    (a mark that is no letter, dropped, costs the junk rate)."""
    rules: dict[tuple[int, int], dict[tuple[str, str], float]] = {}
    for a, b, v in (channel.rules if channel is not None else ()):
        rules.setdefault((len(a), len(b)), {})[(a, b)] = v
    n, m = len(read), len(printed)
    best = [[-math.inf] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            here = best[i][j]
            if here == -math.inf:
                continue
            if i < n and j < m and read[i] == printed[j]:
                best[i + 1][j + 1] = max(best[i + 1][j + 1], here)
            if i < n and j < m:
                best[i + 1][j + 1] = max(best[i + 1][j + 1], here + edit)
            if i < n:
                cost = LOG_JUNK if not read[i].isalpha() else edit
                best[i + 1][j] = max(best[i + 1][j], here + cost)
            if j < m:
                best[i][j + 1] = max(best[i][j + 1], here + edit)
            for (la, lb), table in rules.items():
                if i + la <= n and j + lb <= m:
                    v = table.get((read[i:i + la], printed[j:j + lb]))
                    if v is not None:
                        best[i + la][j + lb] = max(best[i + la][j + lb], here + v)
    return best[n][m]


class VocabIndex:
    """Words as a padded letter matrix, so every word within ``max_dist`` edits of a query is found with one pass of the
    edit-distance table over numpy columns."""

    def __init__(self, words: Iterable[str]) -> None:
        import numpy as np

        self._np = np
        self.words = sorted({w for w in words if 2 <= len(w) <= 24 and re.fullmatch(r"[a-z]+", w)})
        n = len(self.words)
        self.lengths = np.fromiter((len(w) for w in self.words), dtype=np.int16, count=n)
        self.matrix = np.zeros((n, 25), dtype=np.uint8)
        for k, w in enumerate(self.words):
            self.matrix[k, :len(w)] = np.frombuffer(w.encode("ascii"), dtype=np.uint8)

    def near(self, word: str, max_dist: int = 3) -> list[str]:
        np = self._np
        q = word.encode("ascii", "ignore")
        m = len(q)
        if not m:
            return []
        rows = np.nonzero(np.abs(self.lengths - m) <= max_dist)[0]
        if not rows.size:
            return []
        w = self.matrix[rows]
        width = int(self.lengths[rows].max())
        w = w[:, :width]
        prev = np.broadcast_to(np.arange(width + 1, dtype=np.int16), (rows.size, width + 1)).copy()
        for i in range(1, m + 1):
            cur = np.empty_like(prev)
            cur[:, 0] = i
            ch = q[i - 1]
            for j in range(1, width + 1):
                sub = prev[:, j - 1] + (w[:, j - 1] != ch)
                cur[:, j] = np.minimum(np.minimum(prev[:, j] + 1, cur[:, j - 1] + 1), sub)
            prev = cur
        dist = prev[np.arange(rows.size), self.lengths[rows]]
        return [self.words[k] for k in rows[dist <= max_dist]]


def vocabulary(lexicon) -> set[str]:
    """The words a candidate may be: those of the clean corpus, common general English, and the document's terms."""
    words = {w for w, c in lexicon.unigrams.items() if c >= lexicon.min_count}
    words.update(lexicon.terms)
    try:
        from jason.community.lexicon import _frequencies, _wordfreq

        if lexicon.english is _wordfreq:
            words.update(w for w, f in _frequencies("en").items() if f >= 1e-6)
    except ImportError:
        pass
    return {w for w in words if re.fullmatch(r"[a-z]{2,24}", w)}


def index_for(lexicon) -> VocabIndex:
    key = ("vocab-index",)
    if key not in lexicon.cache:
        lexicon.cache[key] = VocabIndex(vocabulary(lexicon))
    return lexicon.cache[key]


def search(word: str, lexicon, channel: Channel | None, *, max_dist: int = 3, keep: int = 24) -> dict[str, float]:
    """The vocabulary's words within ``max_dist`` edits of ``word`` with the channel's log probability that each was read
    as ``word``, the likeliest ``keep``; lowercase."""
    w = word.lower()
    key = ("search", w, channel.name if channel is not None else "", max_dist)
    if key in lexicon.cache:
        return lexicon.cache[key]
    scored = {c: channel_cost(w, c, channel) for c in index_for(lexicon).near(w, max_dist) if c != w}
    top = dict(sorted(scored.items(), key=lambda kv: -kv[1])[:keep])
    lexicon.cache[key] = top
    return top


__all__ = ["VocabIndex", "available", "channel_cost", "index_for", "search", "vocabulary"]
