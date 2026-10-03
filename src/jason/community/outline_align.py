"""Section numbers for an OCR reading, placed by a reference copy of the same document.

The label grammar (``outline_labels``) reads what the OCR left legible. A reference copy (a working Doc kept by hand,
or an earlier reading) knows where the rest are, but it is a copy: it may number a list the recorded text does not, or
nest a list one level too deep. ``align_to_reference`` therefore uses it only where the reading has no clear answer:

1. **Align.** The reading's sections and the reference's are aligned in order by the words that open each (a
   sequence alignment over the openings, letters and digits only, so "ofthe" meets "of the"), within the same article.
2. **Renumber the unclear.** An aligned pair with different numbers: a label the reading holds firm (read clearly and
   in order) is kept and the difference is a finding (``DISAGREES``); an unclear one (recovered from a garbled
   token, a skip, or an unusual series) takes the reference's number (``RENUMBERED``), and its subsections follow.
3. **Place the missing.** A reference section the reading lacks is looked for between its neighbours' places: a label
   token in the reading (inline, "(iv) the right to ...", or garbled at a line's start, "63) Any proposed action")
   followed by the reference's opening words. Found, it becomes a section (``ALIGNED``). Where the reading labels the
   same words differently ("(i) managing" where the copy has "(a)"), the reading's label stands and the difference is
   a finding. Words with no label token are never split: that is the copy's numbering, not the recorded text's.

Every change is a note for a person; nothing is renumbered silently, and a miss stays a miss.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, replace
from functools import lru_cache

from jason.community.outline_labels import (_AFTER, _JUNK, How, LabelNote, LabelReading, Mark, NoteKind, Series,
                                            _sub_parses, glyph, inline_title, number_parent, token_cost)
from jason.community.outlines import DocumentOutline

_KEY_LEN = 80
_INLINE_TOKEN = re.compile(r"(?:(?<=[\s;:,])|^)[(\[{][ \t]*([A-Za-z0-9|!]{1,5})[ \t]*[)\]}](?=[ \t\n])", re.M)


def opening_key(text: str) -> str:
    """A section's opening as letters and digits only, its label and an article heading's number dropped."""
    t = text.lower()
    t = re.sub(r"^\W*article\s*[0-9ivxl]+\b", "", t)
    t = re.sub(r"^\W*\d+(?:\.\d+)*\.?\s", "", t)
    return re.sub(r"[^a-z0-9]", "", t)[:_KEY_LEN]


def similarity(a: str, b: str) -> float:
    """How alike two openings are, over the shorter one's length; 0 when either is too short to say."""
    n = min(len(a), len(b))
    if n < 6:
        return 1.0 if n and a[:n] == b[:n] else 0.0
    return difflib.SequenceMatcher(None, a[:n], b[:n], autojunk=False).ratio()


def _article(number: str) -> int:
    head = re.match(r"\d+", number)
    return int(head.group(0)) if head else 0


def _last_token(number: str) -> str:
    if number.endswith(")"):
        return number[number.rfind("(") + 1:-1]
    return number.rsplit(".", 1)[-1]


def align_to_reference(reading: LabelReading, reference: DocumentOutline, *, label: str = "the reference",
                       min_ratio: float = 0.6) -> LabelReading:
    """``reading`` with the reference's numbers where its own labels are unclear or missing (see the module's notes).
    Returns a new reading; the notes say what changed and where the two disagree."""
    text = reading.text
    marks = [replace(m) for m in sorted(reading.marks, key=lambda m: m.start)]
    notes = list(reading.notes)

    ref = sorted((s for s in reference.sections if s.number), key=lambda s: s.start)
    ref_starts = sorted(s.start for s in reference.sections)
    ref_keys = []
    for s in ref:
        end = next((x for x in ref_starts if x > s.start), len(reference.text))
        ref_keys.append(opening_key(reference.text[s.start:end]))

    def mark_keys() -> list[str]:
        out = []
        for k, m in enumerate(marks):
            end = marks[k + 1].start if k + 1 < len(marks) else len(text)
            out.append(opening_key(text[max(m.cut, m.start):end]))
        return out

    pairs = _align(marks, mark_keys(), ref, ref_keys, min_ratio)

    # Renumber the unclear; keep the firm and say where they differ.
    taken = {m.number for m in marks}
    ref_at: dict[int, int] = {}
    for mi, rj in pairs:
        m, r = marks[mi], ref[rj]
        ref_at[rj] = m.start
        if m.number == r.number:
            continue
        new_parent = number_parent(r.number)
        if m.firm or r.number in taken or (new_parent and new_parent not in taken):
            why = ("kept: read clearly and in order" if m.firm else
                   f"kept: the reading already has a {r.number}" if r.number in taken else
                   f"kept: the reading has no {new_parent}")
            notes.append(LabelNote(NoteKind.DISAGREES, m.number, f"{label} numbers these words {r.number}; {why}"))
            continue
        old = m.number
        notes.append(LabelNote(NoteKind.RENUMBERED, r.number, f'read "{m.raw or old}" as {old}; {label} numbers '
                                                                f"these words {r.number}"))
        taken.discard(old)
        for later in marks:
            if later.start >= m.start and (later.number == old or later.number.startswith(old + "(")):
                taken.discard(later.number)
                later.number = r.number + later.number[len(old):]
                taken.add(later.number)
        m.how = How.RENUMBERED
        m.label = _clean_label(r.number) + (" " if m.label.endswith(" ") else "")

    # Place what the reading lacks, between its neighbours' places.
    for rj, r in enumerate(ref):
        if rj in ref_at:
            continue
        if r.number in taken:
            continue                       # the reading has the number for other words: the drift shows it
        parent = r.parent or number_parent(r.number)
        if parent and parent not in taken:
            notes.append(LabelNote(NoteKind.ONLY_IN_REFERENCE, r.number, f"its parent {parent} is not read"))
            continue
        lo = max((ref_at[j] for j in ref_at if j < rj), default=0)
        hi = min((ref_at[j] for j in ref_at if j > rj), default=len(text))
        parent_mark = next((m for m in marks if m.number == parent), None)
        if parent_mark is not None:
            lo = max(lo, parent_mark.cut)
        if hi <= lo:
            notes.append(LabelNote(NoteKind.ONLY_IN_REFERENCE, r.number, "no room between its neighbours"))
            continue
        found = _place(text, lo, hi, r.number, ref_keys[rj], min_ratio)
        if found is None:
            notes.append(LabelNote(NoteKind.ONLY_IN_REFERENCE, r.number, "no label for its words in the reading"))
            continue
        raw = found.raw.strip()
        if found.differs:
            notes.append(LabelNote(NoteKind.DISAGREES, r.number, f'the reading labels these words "{raw}"; '
                                                                   f"{label} numbers them {r.number}; kept as read"))
            continue
        if any(m.start <= found.start < max(m.cut, m.start + 1) for m in marks):
            continue                       # inside a label already read
        line_start = text.rfind("\n", 0, found.start) + 1
        if _JUNK.fullmatch(text[line_start:found.start]):
            line_end = text.find("\n", found.cut)
            title = text[found.cut: line_end if line_end >= 0 else len(text)].strip()[:120]
        else:
            title = inline_title(text, found.cut)
        mark = Mark(r.number, found.start, found.cut, _clean_label(r.number) + (" " if found.garbled else ""),
                    title, How.ALIGNED, round(found.cost, 2), False, raw)
        marks.append(mark)
        marks.sort(key=lambda m: m.start)
        taken.add(r.number)
        ref_at[rj] = found.start
        how = "a garbled label" if found.garbled else "an inline label"
        notes.append(LabelNote(NoteKind.ALIGNED, r.number, f'"{raw}", {how}, by its words ({found.ratio:.2f})'))
    return LabelReading(text, marks, notes, reading.key, reading.title, reading.kind)


def _clean_label(number: str) -> str:
    return f"({_last_token(number)})" if number.endswith(")") else number


def _align(marks: list[Mark], keys: list[str], ref: list, ref_keys: list[str], min_ratio: float
           ) -> list[tuple[int, int]]:
    """The best order-keeping pairing of the reading's sections with the reference's, by opening words (same number
    helps), within an article of each other. A sequence alignment: gaps cost nothing, a pair scores its likeness."""
    n, m = len(marks), len(ref)
    arts = [_article(x.number) for x in marks]
    ref_arts = [_article(r.number) for r in ref]
    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    step = [[0] * (m + 1) for _ in range(n + 1)]        # 0 diagonal, 1 skip a mark, 2 skip a reference section
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best, how = score[i - 1][j], 1
            if score[i][j - 1] > best:
                best, how = score[i][j - 1], 2
            if abs(arts[i - 1] - ref_arts[j - 1]) <= 1:
                same = marks[i - 1].number == ref[j - 1].number
                ratio = similarity(keys[i - 1], ref_keys[j - 1])
                if ratio >= min_ratio or (same and ratio >= 0.35):
                    value = score[i - 1][j - 1] + ratio + (0.5 if same else 0.0)
                    if value > best:
                        best, how = value, 0
            score[i][j], step[i][j] = best, how
    pairs = []
    i, j = n, m
    while i and j:
        if step[i][j] == 0:
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif step[i][j] == 1:
            i -= 1
        else:
            j -= 1
    return pairs[::-1]


_CLEAN = frozenset(glyph(series, n) for series in Series for n in range(1, 31))


@lru_cache(maxsize=4096)
def _nearest(token: str) -> str:
    """The clean label a token is closest to."""
    return token if token in _CLEAN else min(sorted(_CLEAN), key=lambda g: token_cost(token, g))


@dataclass(frozen=True)
class _Placed:
    """Where a reference section was found in the reading: ``[start, cut)`` is the label as written."""

    start: int
    cut: int
    raw: str
    cost: float            # the label as written against the reference's
    ratio: float           # how alike the words after it are to the reference's opening
    differs: bool          # the reading's own clean label is another one: it stands
    garbled: bool          # no clean label: replaced, with the words' gap


def _place(text: str, lo: int, hi: int, number: str, key: str, min_ratio: float) -> _Placed | None:
    """Where a reference section's words begin in ``text[lo:hi]`` after a label token. None when its words are not
    there after any label token."""
    if "(" not in number:
        return _place_section(text, lo, hi, number, key) if "." in number else None
    want = _last_token(number)
    need = 0.85 if len(key) < 12 else min_ratio + 0.1
    candidates: list[tuple[int, int, str]] = [(hit.start(), hit.end(), hit.group(1))
                                              for hit in _INLINE_TOKEN.finditer(text, lo, hi)]
    # A garbled label at a line's start ("63) Any proposed action").
    for line in re.finditer(r"(?m)^.*$", text[lo:hi]):
        s = line.group(0)
        p = _JUNK.match(s).end()
        candidates += [(lo + line.start() + p, lo + line.start() + end, tok) for tok, _form, end in _sub_parses(s, p)]
    best: tuple[float, _Placed] | None = None
    for start, end, tok in candidates:
        after = _AFTER.match(text, end).end()
        ratio = similarity(opening_key(text[after:after + 200]), key)
        cost = token_cost(tok, want)
        # The label the token nearly is: "(il)" is (ii), so it cannot be the copy's "(b)".
        nearest = _nearest(tok)
        garbled = token_cost(tok, nearest) > 0.3
        if not garbled and cost > 0.2 and token_cost(tok, nearest) < cost:
            cost = max(cost, 0.6)         # read as another label
        if ratio < (need if cost <= 0.5 else max(need, 0.85)):
            continue
        rank = ratio - 0.2 * min(cost, 1.0)
        if best is None or rank > best[0]:
            # A clean label is normalized in place ("{c)" as "(c)"); a garbled one is replaced with its words' gap.
            placed = _Placed(start, after if garbled else end, text[start:after], cost, ratio,
                             differs=cost > 0.5 and not garbled, garbled=garbled)
            best = (rank, placed)
    return best[1] if best else None


_SECTION_TOKEN = re.compile(r"(?m)^[^\S\n]*(\S{1,7})[ \t]+(?=\S)")


def _place_section(text: str, lo: int, hi: int, number: str, key: str) -> _Placed | None:
    """A dotted section the grammar could not read: a short token at a line's start ("#.16", "4,l6."), then the
    reference's opening words, closely. A clear number of its own ("4.18") is the reading's and stands."""
    best: _Placed | None = None
    for hit in _SECTION_TOKEN.finditer(text, lo, hi):
        tok = hit.group(1)
        ratio = similarity(opening_key(text[hit.end():hit.end() + 200]), key)
        if ratio < 0.85 or (best is not None and ratio <= best.ratio):
            continue
        clear = re.fullmatch(r"\d+\.\d+\.?", tok) is not None
        best = _Placed(hit.start(), hit.end(), text[hit.start():hit.end()], token_cost(tok.rstrip("."), number), ratio,
                       differs=clear and tok.rstrip(".") != number, garbled=True)
    return best


__all__ = ["align_to_reference", "opening_key", "similarity"]
