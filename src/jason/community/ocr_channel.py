"""The OCR channel: what a recognizer reads for what was printed, learned from aligned text instead of listed by hand.

``ocr_correct.CONFUSIONS`` is a hand list of glyph confusions, each as likely as the next ("rn" for "m", "li" for "h"). A
recognizer's real confusions are many more, they are not equally likely, and some are two glyphs for one ("tJ" for a
wide "U"), which a one-character edit cannot reach. ``learn`` counts them from words read wrongly and the words they
should have been (a recognizer's reading aligned with a person's transcription, or with text rendered from a clean
corpus and read back), and gives each rule the chance a recognizer reads those letters for what was printed:

    P(read "rn" | printed "m") = times "m" was read "rn" / times "m" was printed

``Channel.reads`` applies the rules to a word, for ``ocr_correct.candidates``. Nothing here names a document, a
vendor, or a word: the table is letters. docs/ocr-correction.md has the measurements.
"""

from __future__ import annotations

import difflib
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Channel:
    """Rules (as read, as printed, log probability): lowercase letters and the marks a recognizer confuses with them."""

    name: str
    rules: tuple[tuple[str, str, float], ...] = ()

    def reads(self, word: str) -> Iterable[tuple[str, float]]:
        """Every string one rule away from ``word``, taken as printed, with the rule's log probability."""
        for read, printed, logp in self.rules:
            start = word.find(read)
            while start >= 0:
                yield word[:start] + printed + word[start + len(read):], logp
                start = word.find(read, start + 1)

    def merged(self, other: "Channel", name: str = "") -> "Channel":
        """The rules of both; where a pair is in both, the likelier."""
        best: dict[tuple[str, str], float] = {}
        for read, printed, logp in (*self.rules, *other.rules):
            best[(read, printed)] = max(logp, best.get((read, printed), -math.inf))
        return Channel(name or f"{self.name}+{other.name}", tuple((r, p, v) for (r, p), v in best.items()))

    def to_dict(self) -> dict:
        return {"name": self.name, "rules": [[r, p, round(v, 6)] for r, p, v in self.rules]}

    @classmethod
    def from_dict(cls, data: dict) -> "Channel":
        return cls(str(data.get("name") or "channel"),
                   tuple((str(r), str(p), float(v)) for r, p, v in data.get("rules") or ()))

    def table(self, top: int = 15) -> list[tuple[str, str, float]]:
        """The likeliest rules, as (as read, as printed, probability)."""
        return [(r, p, math.exp(v)) for r, p, v in sorted(self.rules, key=lambda x: -x[2])[:top]]


def char_spans(read: str, printed: str) -> list[tuple[str, str]]:
    """The places a read word differs from the printed one, as (as read, as printed) letter groups: one minimal edit
    path, adjacent edits merged ("tjnit" / "unit" gives ("tj", "u")), a pure insertion or deletion widened by one
    neighbouring letter so every rule has letters on both sides."""
    n, m = len(read), len(printed)
    cost = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        cost[i][0] = i
    for j in range(m + 1):
        cost[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost[i][j] = min(cost[i - 1][j] + 1, cost[i][j - 1] + 1, cost[i - 1][j - 1] + (read[i - 1] != printed[j - 1]))
    ops: list[tuple[str, int, int]] = []              # (kind, read index, printed index), kind in "=sdi"
    i, j = n, m
    while i or j:
        if i and j and cost[i][j] == cost[i - 1][j - 1] + (read[i - 1] != printed[j - 1]):
            ops.append(("=" if read[i - 1] == printed[j - 1] else "s", i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i and cost[i][j] == cost[i - 1][j] + 1:
            ops.append(("d", i - 1, j))
            i -= 1
        else:
            ops.append(("i", i, j - 1))
            j -= 1
    ops.reverse()
    # Walk again, collecting runs of edits between matches.
    runs: list[list[tuple[str, int, int]]] = []
    current: list[tuple[str, int, int]] = []
    for op in ops:
        if op[0] == "=":
            if current:
                runs.append(current)
            current = []
        else:
            current.append(op)
    if current:
        runs.append(current)
    spans = []
    for run in runs:
        r0 = min(k for _, k, _ in run)
        r1 = max(k + 1 if kind in "sd" else k for kind, k, _ in run)
        p0 = min(k for _, _, k in run)
        p1 = max(k + 1 if kind in "si" else k for kind, _, k in run)
        a, b = read[r0:r1], printed[p0:p1]
        if not a or not b:                            # widen by the letter on the left, else on the right
            if r0 > 0 and p0 > 0:
                a, b = read[r0 - 1:r1], printed[p0 - 1:p1]
            elif r1 < n and p1 < m:
                a, b = read[r0:r1 + 1], printed[p0:p1 + 1]
        if a and b and a != b:
            spans.append((a, b))
    return spans


_WORD = re.compile(r"[a-z]+")


def aligned_pairs(read_tokens: Sequence[str], printed_tokens: Sequence[str], *, max_edits: int = 3
                  ) -> list[tuple[str, str]]:
    """(as read, as printed) for each word read wrongly: one-for-one replaced words of two aligned token lists that are
    plain letters (edges stripped), a few edits apart."""
    from jason.community.lexicon import core

    def letters(token: str) -> str:
        c = core(token).lower()
        return c if _WORD.fullmatch(c) else ""

    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=list(read_tokens), b=list(printed_tokens), autojunk=False).get_opcodes():
        if tag != "replace" or i2 - i1 != j2 - j1 or i2 - i1 > 4:
            continue
        for a, b in zip(read_tokens[i1:i2], printed_tokens[j1:j2]):
            ra, pb = letters(a), letters(b)
            if ra and pb and ra != pb and _edit_distance(ra, pb) <= max_edits:
                out.append((ra, pb))
    return out


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def learn(pairs: Iterable[tuple[str, str]], printed: Iterable[str], *, min_count: int = 2, max_chars: int = 3,
          floor: float = 1e-4, name: str = "learned") -> Channel:
    """The channel counted from (as read, as printed) word pairs. ``printed`` is every word of the printed text the
    pairs came from (right ones too), so a rule's probability is per chance to misread, not per word: a letter printed
    often and misread seldom is a weak rule."""
    counts: Counter = Counter()
    for read, right in pairs:
        for a, b in char_spans(read, right):
            if len(a) <= max_chars and len(b) <= max_chars:
                counts[(a, b)] += 1
    words = [w.lower() for w in printed]
    chances: Counter = Counter()
    wanted = {b for _, b in counts}
    for w in words:
        for b in wanted:
            if b in w:
                chances[b] += w.count(b)
    rules = []
    for (a, b), c in counts.items():
        if c >= min_count:
            p = c / (chances.get(b, 0) + c)
            rules.append((a, b, math.log(max(p, floor))))
    return Channel(name, tuple(sorted(rules, key=lambda r: -r[2])))


__all__ = ["Channel", "aligned_pairs", "char_spans", "learn"]
