"""Read a scanned base document again with another OCR engine, beside the reading in use, and carry the person's
transcriptions over: the evidence for a person's decision to switch.

A living document's scanned base is read once and cached (``living_docs.scan_base_text``). The people who keep it
then read the page where the OCR failed, and each reading became a transcription keyed to the OCR's exact wrong words
(``data/living/<key>/transcriptions.json``). A better engine reads the page differently, so switching the cached text
would leave most transcriptions stale. ``dry_run``:

1. reads the base again (``READINGS``: "cli" is Tesseract's own tool) into a new cache file beside the original; the
   original stays the text every build reads until a person chooses;
2. migrates each transcription (``migrate``): where the new reading already reads the person's right words it is no
   longer needed; where it has the same wrong words it is carried; where it has different wrong words at that place, a
   re-keyed transcription (the person's right words, the new wrong words) is proposed as an intake question, never
   applied; where its place cannot be found it is listed;
3. measures each reading against the working copy (``word_error``), counts the OCR questions that would disappear,
   and writes the report (``reread-<reading>.md``), the migrated set (``transcriptions.<reading>.json``), and the
   proposed questions (``reread-<reading>-asks.json``) under ``data/living/<key>/``.

``switch`` is the person's step: the migrated set becomes the active one, the old is kept as a backup, the proposed
questions join the intake queue, and ``reading.json`` names the reading every build then uses.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import shutil
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from jason.tasks import living_docs
from jason.tasks.living_docs import READINGS

CONTEXT = 3              # words of context either side when a key must be widened to occur once
MAX_GAP = 6              # a differing block longer than this, on either side, is structure, not a misread
MIN_RUN = 20             # a run between structural breaks shorter than this (reference words) is not scored
SPREAD = 6               # a re-keyed place that differs from the right words by more words than this is unplaced
ALIKE = 0.5              # a re-keyed place's words must be this alike the right words (characters), as in intake
PLACED = 0.5             # a section of the new reading this unlike the old one's words is a stray number, not it


class Fate(Enum):
    UNNECESSARY = "no longer needed"   # the new reading already reads the person's right words
    CARRIED = "carried"                # the new reading has the same wrong words there
    REKEYED = "re-keyed"               # it has different wrong words there: proposed as a question
    UNPLACED = "unplaced"              # its place in the new reading could not be found
    STALE = "stale already"            # it did not apply to the reading in use either


@dataclass
class Migrated:
    """One transcription's fate in the new reading. ``wrong`` and ``right`` key it there (carried, re-keyed);
    ``reads`` is what the new reading reads at its place."""

    row: dict
    fate: Fate
    section: str = ""
    wrong: str = ""
    right: str = ""
    reads: str = ""
    stage: str = ""
    why: str = ""

    def as_row(self) -> dict:
        """The transcription keyed to the new reading, for ``transcriptions.<reading>.json``."""
        out = {**self.row, "section": self.section, "wrong": self.wrong, "right": self.right}
        if (self.section, self.wrong) != (self.row["section"], self.row["wrong"]):
            out["carried_from"] = {"section": self.row["section"], "wrong": self.row["wrong"], "right": self.row["right"]}
        return out


# Migration.


def _tokens(body: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"\S+", body)]


_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', " ": " ", "–": "-",
                         "—": "-"})


def _fold(words: list[str]) -> list[str]:
    return [w.translate(_QUOTES) for w in words]


def _corrected(body: str, rows: list[dict]) -> tuple[str, dict[int, tuple[int, int]]]:
    """``body`` with ``rows`` applied as ``living.correct`` applies them (each row's changed core, from the end back,
    an overlapping one skipped), and each applied row's right words' span in the result, by its index in ``rows``."""
    from jason.community.living import _core

    edits = []
    for k, r in enumerate(rows):
        if body.count(r["wrong"]) != 1:
            continue
        head, core_wrong, core_right = _core(r["wrong"], r["right"])
        start = body.index(r["wrong"]) + head
        edits.append((start, start + len(core_wrong), core_right, k, head, len(r["wrong"]) - head - len(core_wrong)))
    kept, last = [], len(body) + 1
    for e in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        if e[1] > last:
            continue
        kept.append(e)
        last = e[0]
    out, pos, shift, spans = [], 0, 0, {}
    for start, end, text, k, head, tail in reversed(kept):
        out += [body[pos:start], text]
        at = start + shift
        spans[k] = (at - head, at + len(text) + tail)
        shift += len(text) - (end - start)
        pos = end
    out.append(body[pos:])
    return "".join(out), spans


def _widen(ops: list, i1: int, i2: int) -> tuple[int, int]:
    """The span [i1, i2) on side a, widened to the edges of every differing block it touches."""
    changed = True
    while changed:
        changed = False
        for tag, x1, x2, _, _ in ops:
            if tag == "equal":
                continue
            touches = (x1 < i2 and i1 < x2) or (i1 == i2 and x1 <= i1 <= x2) or (x1 == x2 and i1 < x1 < i2)
            if touches and (x1 < i1 or x2 > i2):
                i1, i2, changed = min(i1, x1), max(i2, x2), True
    return i1, i2


def _image(ops: list, i1: int, i2: int, n_b: int) -> tuple[int, int]:
    """The span on side b of a widened span [i1, i2) on side a."""
    if i1 == i2:
        for tag, x1, x2, y1, y2 in ops:
            if x1 == x2 == i1 and tag != "equal":
                return y1, y2
            if tag == "equal" and x1 <= i1 < x2:
                return y1 + (i1 - x1), y1 + (i1 - x1)
            if x1 <= i1 < x2:
                return y1, y2
        return n_b, n_b
    j1 = next((y1 + (i1 - x1) if tag == "equal" else y1 for tag, x1, x2, y1, _ in ops if x1 <= i1 < x2), n_b)
    j2 = next((y1 + (i2 - x1) if tag == "equal" else y2 for tag, x1, x2, y1, y2 in ops if x1 < i2 <= x2), n_b)
    return j1, max(j1, j2)


def _span_tokens(tokens: list[tuple[int, int, str]], s: int, e: int) -> tuple[int, int]:
    """The tokens a character span [s, e) touches; an empty span is the place before the first token after it."""
    i1 = next((k for k, t in enumerate(tokens) if t[1] > s), len(tokens))
    if e <= s:
        return i1, i1
    i2 = max((k + 1 for k, t in enumerate(tokens) if t[0] < e), default=i1)
    return i1, max(i1, i2)


def _bodies(provisions: list) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in provisions:
        out.setdefault(p.number, p.body)
    return out


@dataclass(frozen=True)
class _Place:
    number: str
    body: str
    first: bool              # the first provision with its number: the one a transcription keyed to it applies to


def _window(section: str, old_order: list[str], at: dict[str, int], new_list: list[_Place], *, limit: int = 12
            ) -> list[_Place]:
    """The new reading's provisions where an old section's words should be: from the section itself (or, when the new
    reading numbers it otherwise, the nearest earlier section both readings have) to the nearest later section both
    have. OCR that misreads a label ("1.40" for "1.10") moves a section's words, not their order. ``at`` is where each
    old section sits in the new reading."""
    here = old_order.index(section)
    if section in at:
        start = at[section]
        nxt = next((at[n] for n in old_order[here + 1:] if n in at and at[n] > start), None)
        end = nxt + 1 if nxt is not None else len(new_list)
        return new_list[start:min(end, start + limit)]
    # Numbered otherwise: the words sit before the next section both readings have, after the one before it.
    nxt = next((at[n] for n in old_order[here + 1:] if n in at), None)
    end = nxt + 1 if nxt is not None else len(new_list)
    start = next((at[n] for n in reversed(old_order[:here]) if n in at and at[n] < end - 1), 0)
    return new_list[max(start, end - limit):end]


def _section(section: str, old_body: str, window: list[_Place], group: list[tuple[int, dict]], stage: str,
             only: set[int] | None = None) -> dict[int, Migrated]:
    """The fates of one section's transcriptions (those in ``only``, else all), against the new reading's provisions in
    ``window``: the section's corrected words are aligned with the window's, and each transcription's right words
    are found there."""
    from jason.tasks.intake import _unique_span

    parts, owners, pos = [], [], 0
    for place in window:
        owners.append((pos, pos + len(place.body), place.number, place.body, place.first))
        parts.append(place.body)
        pos += len(place.body) + 1
    joined = "\n".join(parts)
    fixed, spans = _corrected(old_body, [r for _, r in group])
    ct, ot, nt = _tokens(fixed), _tokens(old_body), _tokens(joined)
    cw, ow, nw = [t[2] for t in ct], [t[2] for t in ot], [t[2] for t in nt]
    to_new = difflib.SequenceMatcher(a=cw, b=nw, autojunk=False).get_opcodes()
    to_old = difflib.SequenceMatcher(a=cw, b=ow, autojunk=False).get_opcodes()
    out = {}
    for idx, (k, r) in enumerate(group):
        if only is not None and k not in only:
            continue

        def unplaced(why: str, reads: str = "") -> Migrated:
            return Migrated(r, Fate.UNPLACED, section, reads=reads, stage=stage, why=why)   # noqa: B023

        if idx not in spans:
            out[k] = Migrated(r, Fate.STALE, section, stage=stage, why="it overlaps another transcription")
            continue
        i1, i2 = _span_tokens(ct, *spans[idx])
        for _ in range(8):                              # widen until both images are whole blocks
            w1, w2 = _widen(to_old, *_widen(to_new, i1, i2))
            if (w1, w2) == (i1, i2):
                break
            i1, i2 = w1, w2
        j1, j2 = _image(to_new, i1, i2, len(nw))
        o1, o2 = _image(to_old, i1, i2, len(ow))
        right_w, old_w = cw[i1:i2], ow[o1:o2]
        lo = nt[j1][0] if j1 < len(nt) else len(joined)
        hi = nt[j2 - 1][1] if j2 > j1 else lo
        crossed = [o for o in owners if any(o[0] <= nt[j][0] < o[1] + 1 for j in range(j1, j2))]
        if len(crossed) > 1:
            # A block at a section's edge takes in the neighbour's words: keep the part in the section that reads most
            # like the right words.
            def part(o: tuple) -> list[int]:
                return [j for j in range(j1, j2) if o[0] <= nt[j][0] < o[1] + 1]

            best = max(crossed, key=lambda o: (difflib.SequenceMatcher(None, " ".join(nw[j] for j in part(o)),
                                                                       " ".join(right_w)).ratio(), len(part(o))))
            kept = part(best)
            j1, j2 = kept[0], kept[-1] + 1
            lo, hi = nt[j1][0], nt[j2 - 1][1]
        new_w = nw[j1:j2]
        reads = " ".join(new_w)
        owner = next((o for o in owners if o[0] <= lo <= o[1]), None)
        if owner is None or hi > owner[1]:
            out[k] = unplaced("its place runs across two sections of the new reading", reads)
            continue
        base, end, number, body, first = owner
        moved = "" if number == section else f"the new reading numbers it {number or 'the preamble'}"
        if _fold(new_w) == _fold(right_w):
            out[k] = Migrated(r, Fate.UNNECESSARY, number, reads=reads, stage=stage, why=moved)
            continue
        if not first:
            out[k] = unplaced(f"the new reading has another section numbered {number or '(none)'} before this one, so "
                              "a transcription keyed to it would not reach these words", reads)
            continue
        same = _fold(new_w) == _fold(old_w)
        at = body.find(r["wrong"])
        if same and body.count(r["wrong"]) == 1 and at <= hi - base and at + len(r["wrong"]) >= lo - base:
            out[k] = Migrated(r, Fate.CARRIED, number, r["wrong"], r["right"], reads=reads, stage=stage, why=moved)
            continue
        if not same and (abs(len(new_w) - len(right_w)) > SPREAD or (not new_w and not right_w)):
            out[k] = unplaced("the new reading differs too much there to key a reading", reads)
            continue
        anchored = any(tag == "equal" and (x2 == i1 or x1 == i2) for tag, x1, x2, _, _ in to_new)
        alike = difflib.SequenceMatcher(None, " ".join(new_w).lower(), " ".join(right_w).lower()).ratio() >= ALIKE
        if not same and not (anchored and alike):
            out[k] = unplaced("the new reading's words there are not like the right words, or not anchored by words "
                              "both readings share", reads)
            continue
        local = [w for s, e, w in nt if base <= s and e <= end]
        lj1 = sum(1 for s, e, _ in nt if base <= s and e <= end and s < lo)
        lj2 = lj1 + len(new_w)
        found = _unique_span(body, new_w, local[max(0, lj1 - CONTEXT):lj1], local[lj2:lj2 + CONTEXT])
        if found is None:
            out[k] = unplaced("the new reading's words there do not occur once, even with context", reads)
            continue
        wrong, left, right_ctx = found
        right = " ".join(x for x in (left, " ".join(right_w), right_ctx) if x)
        why = "; ".join(x for x in (moved, "the same wrong words, keyed with more context" if same else "") if x)
        out[k] = Migrated(r, Fate.CARRIED if same else Fate.REKEYED, number, wrong, right, reads=reads, stage=stage,
                          why=why)
    return out


def _where(ob: dict[str, str], new_list: list[_Place]) -> dict[str, int]:
    """Where each old section sits in the new reading: the provision with its number, or, when the new reading has
    more than one (a cross-reference read as a heading), the one whose words are most like the old section's."""
    positions: dict[str, list[int]] = {}
    for n, place in enumerate(new_list):
        positions.setdefault(place.number, []).append(n)
    out = {}
    for number, old_body in ob.items():
        likeness = {n: difflib.SequenceMatcher(None, old_body[:600], new_list[n].body[:600]).ratio()
                    for n in positions.get(number, ())}
        best = max(likeness, key=likeness.__getitem__, default=None)
        if best is not None and likeness[best] >= PLACED:
            out[number] = best           # else the number is a stray (a table of contents line): look between neighbours
    return out


def migrate(rows: list[dict], stages: list[tuple[str, list, list]]) -> list[Migrated]:
    """Each transcription's fate in a new reading. ``stages`` are (label, the reading in use's provisions, the new
    reading's), tried in order as ``living.correct`` applies corrections: the base first, then the text after the
    amendments for those the base did not hold. A transcription neither stage holds was stale already.

    Each is looked for in its own section of the new reading first; one not placed there (the section is numbered
    otherwise, or its words moved to a neighbour) is looked for between the neighbouring sections both readings have."""
    pending = list(enumerate(rows))
    out: dict[int, Migrated] = {}
    for label, old, new in stages:
        ob = _bodies(old)
        old_order = [p.number for p in old]
        seen: set[str] = set()
        new_list = []
        for p in new:
            new_list.append(_Place(p.number, p.body, p.number not in seen))
            seen.add(p.number)
        at = _where(ob, new_list)
        here = [(k, r) for k, r in pending if r["section"] in ob and ob[r["section"]].count(r["wrong"]) == 1]
        taken = {k for k, _ in here}
        pending = [(k, r) for k, r in pending if k not in taken]
        groups: dict[str, list[tuple[int, dict]]] = {}
        for k, r in here:
            groups.setdefault(r["section"], []).append((k, r))
        for section, group in groups.items():
            found: dict[int, Migrated] = {}
            if section in at:
                found = _section(section, ob[section], [new_list[at[section]]], group, label)
            retry = {k for k, _ in group if k not in found or found[k].fate is Fate.UNPLACED}
            if retry:
                window = _window(section, old_order, at, new_list)
                again = _section(section, ob[section], window, group, label, only=retry) if window else {}
                for k in retry:
                    if k in again and (again[k].fate is not Fate.UNPLACED or k not in found):
                        found[k] = again[k]
                    elif k not in found:
                        found[k] = Migrated(dict(group)[k], Fate.UNPLACED, section, stage=label,
                                            why="no place for it in the new reading")
            out.update(found)
    for k, r in pending:
        out[k] = Migrated(r, Fate.STALE, r["section"], why="its wrong words are not once in its section")
    return [out[k] for k in range(len(rows))]


def migrated_rows(found: list[Migrated]) -> list[dict]:
    """The carried transcriptions keyed to the new reading, one per (section, wrong)."""
    seen, out = set(), []
    for m in found:
        if m.fate is Fate.CARRIED and (m.section, m.wrong) not in seen:
            seen.add((m.section, m.wrong))
            out.append(m.as_row())
    return out


def rekey_asks(key: str, reading: str, found: list[Migrated]) -> list:
    """A question for each re-keyed transcription: the person's earlier reading of the page against the new reading's
    words. Never ``likely``: the three readers (the person, the reading in use, the new reading) all differ there, and
    some earlier readings were copied from the working copy, which has slips of its own ("ownership,and")."""
    from jason.community.intake import Ask, AskKind, ask_id

    out, seen = [], set()
    for m in found:
        if m.fate is not Fate.REKEYED or (m.section, m.wrong) in seen:
            continue
        seen.add((m.section, m.wrong))
        subject = f"reread:{key}#{m.section}"
        out.append(Ask(ask_id(AskKind.OCR_READING, subject, m.wrong), AskKind.OCR_READING, subject,
                       f'Read again ({reading}), the base reads "{m.wrong}" where a person read the page as '
                       f'"{m.right}" (it corrected "{m.row["wrong"]}" in the reading in use). Which does the page say?',
                       choices=(m.right, m.wrong, "something else (type it)"), suggestion=m.right, likely=False,
                       evidence=(f'the reading in use: "{m.row["wrong"]}" in {m.row["section"]}',
                                 f'the transcription: "{m.row["right"]}" ({m.row.get("source") or "no source"})',
                                 f'the {reading} reading: "{m.reads}"' + (f" ({m.why})" if m.why else "")),
                       detail={"document": key, "section": m.section, "wrong": m.wrong, "right": m.right,
                               "reread": reading, "was": {k: m.row[k] for k in ("section", "wrong", "right")}}))
    return out


# Measurement against the working copy.


def _label(number: str) -> str:
    """A section's label as the page prints it: a list item's own letter ("(iv)"), a heading's number ("4.11")."""
    return re.findall(r"\([^)]*\)$", number)[0] if number.endswith(")") else number


def page_tokens(provisions: list) -> tuple[list[str], list[str]]:
    """The words of ``provisions`` as a page prints them (label, caption, words), and the section each belongs to."""
    words, owner = [], []
    for p in provisions:
        if getattr(p, "removed", False):
            continue
        toks = " ".join(x for x in (_label(p.number), p.caption, p.body) if x).translate(_QUOTES).split()
        words += toks
        owner += [p.number] * len(toks)
    return words, owner


def _lev(a: list | str, b: list | str) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


@dataclass
class Score:
    words: int = 0                    # reference words scored
    edits: int = 0
    chars: int = 0
    char_edits: int = 0
    differences: list[tuple[str, str, str]] = field(default_factory=list)   # (section, reading, working copy)

    @property
    def wer(self) -> float:
        return self.edits / self.words if self.words else 0.0

    @property
    def cer(self) -> float:
        return self.char_edits / self.chars if self.chars else 0.0


def word_error(hyp: list[str], ref: list[str], owner: list[str], skip: set[str]) -> Score:
    """Word and character error of ``hyp`` against the working copy's words ``ref``, from one alignment of the whole
    text. A differing block of more than ``MAX_GAP`` words on either side (a caption, the table of contents, page
    furniture) or one touching a section in ``skip`` (set by an amendment) breaks the text into runs; runs of fewer
    than ``MIN_RUN`` reference words are not scored."""
    score = Score()
    run: list[tuple[str, list[str], list[str]]] = []
    run_words = 0

    def flush() -> None:
        nonlocal run, run_words
        if run_words >= MIN_RUN:
            for section, a, b in run:
                score.words += len(b)
                score.chars += len(" ".join(b)) + (1 if b else 0)
                if a != b:
                    score.edits += _lev(a, b)
                    score.char_edits += _lev(" ".join(a), " ".join(b))
                    score.differences.append((section, " ".join(a), " ".join(b)))
        run, run_words = [], 0

    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=hyp, b=ref, autojunk=False).get_opcodes():
        bad = any(owner[k] in skip for k in range(j1, j2))
        if bad or (tag != "equal" and (i2 - i1 > MAX_GAP or j2 - j1 > MAX_GAP)):
            flush()
            continue
        section = owner[j1] if j2 > j1 else (owner[j1 - 1] if j1 else "")
        run.append((section, hyp[i1:i2], ref[j1:j2]))
        run_words += j2 - j1
    flush()
    return score


def difference_kind(reading: str, copy: str) -> str:
    """spacing (the same characters), case or punctuation (the same letters and digits), or words."""
    if reading.replace(" ", "") == copy.replace(" ", ""):
        return "spacing"
    fold = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())     # noqa: E731
    return "case or punctuation" if fold(reading) == fold(copy) else "words"


# The dry run and the switch.


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _corrections(rows: list[dict]) -> tuple:
    from jason.community.living import Correction, CorrectionKind

    return tuple(Correction(r["section"], r["wrong"], r["right"], CorrectionKind(r.get("kind", "transcribed")),
                            source=r.get("source", ""), note=r.get("note", "")) for r in rows)


def _rows(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def build_numbering(living: Any = None) -> str:
    """How ``living_docs.build`` numbers ``living``'s base read from text by default (``living_docs.
    default_numbering``: by the working copy where there is one, else by the label grammar)."""
    return living_docs.default_numbering(living)


def _build(living: Any, data_dir: Path, numbering: str, **kw: Any) -> Any:
    import inspect

    if "numbering" in inspect.signature(living_docs.build).parameters:
        kw["numbering"] = numbering
    return living_docs.build(living, data_dir, **kw)


def base_provisions(living: Any, text: str, data_dir: Path | None = None, numbering: str = "text") -> list:
    """A base text's provisions before any amendment, numbered as ``living_docs.build`` numbers a scanned base."""
    from jason.community.living import provisions_of
    from jason.community.outlines import outline_from_text

    prepared = living_docs.prepare_extract(text)
    if numbering == "text":
        return provisions_of(outline_from_text(prepared, key=living.key, title=living.title, kind=living.kind.value))
    outline, _ = living_docs.numbered_outline(living, prepared, Path(data_dir or "."), aligned=numbering == "aligned")
    return provisions_of(outline)


def _vocabulary(data_dir: Path) -> Counter:
    from jason.tasks.intake import vocabulary

    texts = [json.loads(p.read_text(encoding="utf-8")).get("text", "")
             for p in (Path(data_dir) / "outlines").glob("*.json") if p.name != "references.json"]
    return vocabulary(texts)


def _questions(key: str, built: Any, copy: Any, vocab: Counter, data_dir: Path, lexicon: bool) -> tuple[list, int]:
    """The OCR questions ``jason intake --scan`` would ask of a build (the text rules as the second reader when
    ``lexicon``), and how many one-reader suggestions it would hold."""
    from jason.tasks.intake import ocr_reading_asks

    lex = None
    if lexicon:
        from jason.tasks.ocr_correct import lexicon_for

        lex = lexicon_for(data_dir, " ".join(p.body for p in built.current.provisions), exclude=(key,))
    held: list = []
    asks = ocr_reading_asks(key, built.current, copy, vocab, lexicon=lex, held=held)
    return asks, len(held)


def _ask_key(a: Any) -> tuple[str, str, str]:
    """An OCR question by its section and the words it would change, less the context around them."""
    from jason.community.living import _core

    _, wrong, right = _core(" ".join(a.detail.get("wrong", "").split()), " ".join((a.suggestion or "").split()))
    return a.detail.get("section", ""), wrong.strip(), right.strip()


@dataclass
class Reread:
    key: str
    reading: str
    original: str                              # the reading in use ("" the original)
    files: dict[str, str]
    scores: list[tuple[str, Score]]
    found: list[Migrated]
    profile: list[Migrated]                    # the specification's corrections, migrated the same way
    asks: list                                 # the proposed re-keyed questions
    questions: dict[str, Any]
    sections: dict[str, Any]
    transcriptions_sha: str
    built: str = field(default_factory=lambda: date.today().isoformat())

    def counts(self) -> Counter:
        return Counter(m.fate.value for m in self.found)


def dry_run(living: Any, data_dir: Path, reading: str = "cli", *, lexicon: bool = True, drive: Any = None,
            numbering: str | None = None) -> Reread:
    """Read the base again with ``reading``, migrate the transcriptions, measure, and write the evidence (never the
    transcriptions in use, the intake queue, or the cached text). ``numbering`` is how both readings get their section
    numbers (``living_docs.build``'s option; None is its default): transcriptions are keyed by section, so both
    readings, and the builds after a switch, must be numbered alike."""
    from jason.community import intake
    from jason.community.living import SourceKind

    if living.base.kind is not SourceKind.SCAN:
        raise ValueError(f"{living.key}: its base is not a scan; there is nothing to read again")
    if reading not in READINGS:
        raise ValueError(f"no reading {reading!r}: {', '.join(READINGS)}")
    key, data_dir = living.key, Path(data_dir)
    folder = living_docs.living_dir(data_dir, key)
    cache = folder / "sources"
    in_use = living_docs.chosen_reading(data_dir, key)
    if reading == in_use:
        raise ValueError(f"{key} already reads its base by the {reading} reading")
    old_text = living_docs.scan_base_text(living.base, cache, drive, reading=in_use)
    new_text = living_docs.scan_base_text(living.base, cache, drive, reading=reading)
    pdf = cache / f"{living.base.ref}.pdf"
    digest = _sha(pdf)
    active = living_docs.transcriptions_path(data_dir, key)
    rows = _rows(active)

    # Builds: each reading as read, and with its transcriptions.
    numbering = numbering or build_numbering(living)
    old_raw = _build(living, data_dir, numbering, reading=in_use, transcribed=())
    new_raw = _build(living, data_dir, numbering, reading=reading, transcribed=())
    old_base = base_provisions(living, old_text, data_dir, numbering)
    new_base = base_provisions(living, new_text, data_dir, numbering)
    stages = [("base", old_base, new_base),
              ("amended", old_raw.current.provisions, new_raw.current.provisions)]
    found = migrate(rows, stages)
    profile = migrate([{"section": c.section, "wrong": c.wrong, "right": c.right, "kind": c.kind.value,
                        "source": c.source, "note": c.note} for c in living.corrections], stages)
    carried = migrated_rows(found)
    asks = rekey_asks(key, reading, found)
    accepted = carried + [{"section": a.detail["section"], "wrong": a.detail["wrong"], "right": a.suggestion,
                           "kind": "transcribed"} for a in asks]
    old = _build(living, data_dir, numbering, reading=in_use)
    new = _build(living, data_dir, numbering, reading=reading, transcribed=_corrections(carried))
    new_if = _build(living, data_dir, numbering, reading=reading, transcribed=_corrections(accepted))

    copy = living_docs.working_copy(living, data_dir)
    scores: list[tuple[str, Score]] = []
    if copy is not None:
        from jason.community.living import provisions_of

        ref, owner = page_tokens(provisions_of(copy))
        skip = {p.number for b in (old, new) for p in b.current.provisions if p.standing is not None}
        name = "the original reading" if not in_use else f"the {in_use} reading"
        for label, b in ((f"{name}, as read", old_raw), (f"{name}, with its {len(rows)} transcriptions", old),
                         (f"the {reading} reading, as read", new_raw),
                         (f"the {reading} reading, with the {len(carried)} carried", new),
                         (f"the {reading} reading, if every re-keyed question is accepted as suggested", new_if)):
            scores.append((label, word_error(page_tokens(b.current.provisions)[0], ref, owner, skip)))

    # The OCR questions: the open ones in the queue that a scan of the new reading would no longer ask.
    vocab = _vocabulary(data_dir)
    old_asks, old_held = _questions(key, old, copy, vocab, data_dir, lexicon)
    new_asks, new_held = _questions(key, new, copy, vocab, data_dir, lexicon)
    queue = [a for a in intake.load(data_dir) if a.kind is intake.AskKind.OCR_READING and a.subject.startswith(f"{key}#")]
    open_now = [a for a in queue if a.status is intake.AskStatus.OPEN]
    # A question is the same one when its id is (the same wrong words), or when its section and its changed core are
    # (a scan widens the wrong words with context until they occur once, and context differs between readings).
    new_keys = {_ask_key(a) for a in new_asks} | {a.id for a in new_asks}
    known = {a.id for a in queue} | {_ask_key(a) for a in queue}
    bodies = {p.number: " ".join(p.body.split()) for p in new.current.provisions}
    gone = [a for a in open_now if a.id not in new_keys and _ask_key(a) not in new_keys]
    renumbered = [a for a in gone if a.detail.get("section", "") not in bodies]
    words_gone = [a for a in gone if a not in renumbered
                  and " ".join(a.detail.get("wrong", "").split()) not in bodies[a.detail["section"]]]
    reads_suggestion = [a for a in words_gone if " ".join(a.suggestion.split())
                        and " ".join(a.suggestion.split()) in bodies[a.detail["section"]]]
    fresh = [a for a in new_asks if a.id not in known and _ask_key(a) not in known]
    questions = {"open": len(open_now), "disappear": len(gone), "disappear_words_gone": len(words_gone),
                 "disappear_reads_suggestion": len(reads_suggestion), "disappear_renumbered": len(renumbered),
                 "still_asked": len(open_now) - len(gone), "asked_of_original": len(old_asks),
                 "asked_of_new": len(new_asks), "new": len(fresh), "new_likely": sum(a.likely for a in fresh),
                 "held_original": old_held, "held_new": new_held, "rekeyed_asks": len(asks), "lexicon": lexicon}
    old_n = [p.number for p in old_base if p.number]
    new_n = [p.number for p in new_base if p.number]
    sections = {"original": len(old_n), "new": len(new_n), "numbering": numbering,
                "only_original": list(dict.fromkeys(n for n in old_n if n not in set(new_n))),
                "only_new": list(dict.fromkeys(n for n in new_n if n not in set(old_n)))}
    digest16 = digest[:16]
    files = {"original": living_docs.base_text_path(living.base, cache, digest16, in_use).name,
             "new": living_docs.base_text_path(living.base, cache, digest16, reading).name}
    out = Reread(key, reading, in_use, files, scores, found, profile, asks, questions, sections, _sha(active))
    write(out, data_dir, carried)
    return out


def paths(data_dir: Path, key: str, reading: str) -> dict[str, Path]:
    folder = living_docs.living_dir(data_dir, key)
    return {"report": folder / f"reread-{reading}.md", "detail": folder / f"reread-{reading}.json",
            "transcriptions": folder / f"transcriptions.{reading}.json", "asks": folder / f"reread-{reading}-asks.json"}


def write(r: Reread, data_dir: Path, carried: list[dict]) -> dict[str, Path]:
    p = paths(data_dir, r.key, r.reading)
    p["report"].parent.mkdir(parents=True, exist_ok=True)
    p["transcriptions"].write_text(json.dumps(carried, indent=1), encoding="utf-8")
    p["asks"].write_text(json.dumps([{**asdict(a), "kind": a.kind.value, "status": a.status.value} for a in r.asks],
                                    indent=1), encoding="utf-8")
    p["detail"].write_text(json.dumps({
        "key": r.key, "reading": r.reading, "in_use": r.original, "built": r.built, "files": r.files,
        "transcriptions_sha256": r.transcriptions_sha, "counts": dict(r.counts()), "questions": r.questions,
        "sections": r.sections,
        "scores": [{"reading": label, "wer": s.wer, "cer": s.cer, "words": s.words, "edits": s.edits}
                   for label, s in r.scores],
        "transcriptions": [{"fate": m.fate.value, "stage": m.stage, "was": {k: m.row[k] for k in ("section", "wrong", "right")},
                            "section": m.section, "wrong": m.wrong, "right": m.right, "reads": m.reads, "why": m.why}
                           for m in r.found],
        "profile_corrections": [{"fate": m.fate.value, "was": {k: m.row[k] for k in ("section", "wrong", "right")},
                                 "reads": m.reads, "why": m.why} for m in r.profile],
    }, indent=1), encoding="utf-8")
    p["report"].write_text("\n".join(markdown(r)) + "\n", encoding="utf-8")
    return p


def markdown(r: Reread) -> list[str]:
    counts = r.counts()
    q = r.questions
    name = "the original reading" if not r.original else f"the {r.original} reading"
    out = [f"# Reading the base again: {r.key}, {r.reading}", "",
           f"{r.built}. The reading in use is {name} (`sources/{r.files['original']}`); the {r.reading} reading is "
           f"cached beside it (`sources/{r.files['new']}`). Nothing in use changed: the builds still read {name} and "
           f"`transcriptions.json`. This is the evidence for a person's decision to switch.", ""]
    if r.scores:
        out += ["## Word error against the working copy", "",
                "One alignment of the whole text against the working copy; sections an amendment set, and differing "
                f"blocks of more than {MAX_GAP} words (captions, the table of contents, page furniture), are left out. "
                "The working copy has slips of its own, so no reading reaches zero.", "",
                "| Reading | WER | CER | Words scored |", "|---|---:|---:|---:|"]
        out += [f"| {label} | {s.wer:.2%} | {s.cer:.2%} | {s.words:,} |" for label, s in r.scores]
        out.append("")
    total = len(r.found)
    out += ["## The transcriptions", "",
            f"{total} transcriptions keyed to {name}:", "", "| Fate | Count | Meaning |", "|---|---:|---|"]
    meaning = {Fate.UNNECESSARY: f"the {r.reading} reading already reads the person's right words",
               Fate.CARRIED: "the same wrong words: carried to the new set",
               Fate.REKEYED: "different wrong words at that place: proposed as a question, never applied",
               Fate.UNPLACED: "its place could not be found: listed below for a person",
               Fate.STALE: f"it did not apply to {name} either"}
    out += [f"| {f.value} | {counts.get(f.value, 0)} | {meaning[f]} |" for f in Fate]
    moved = [m for m in r.found if m.fate is Fate.CARRIED and m.section != m.row["section"]]
    out += ["", f"The migrated set (`transcriptions.{r.reading}.json`) holds the carried ones, one per place"
            + (f"; {len(moved)} of them under the section number the {r.reading} reading gives their words "
               f"({', '.join(sorted({m.row['section'] + ' as ' + m.section for m in moved}))})" if moved else "")
            + f". The {q['rekeyed_asks']} proposed questions are in `reread-{r.reading}-asks.json`; none is likely "
            "(the person, the reading in use, and the new reading all differ there), and they join the intake queue "
            "only when a person switches.", ""]
    if r.profile:
        pc = Counter(m.fate.value for m in r.profile)
        out += [f"The specification's {len(r.profile)} corrections: " + ", ".join(f"{v} {k}" for k, v in pc.items())
                + ". A carried or re-keyed one is a person's edit to the profile's row.", ""]
    out += ["## The OCR questions", "",
            f"- Open in the intake queue now: {q['open']}.",
            f"- Would disappear on the next `jason intake --scan` after a switch: {q['disappear']}. In "
            f"{q['disappear_words_gone']} the {r.reading} reading no longer has the words in question "
            f"({q['disappear_reads_suggestion']} of them read as the suggestion; the rest are junk it does not read, "
            f"or read another way); {q['disappear_renumbered']} are in a section it numbers otherwise (they may come "
            "back under the new number); in the rest the words are still there but no longer differ from the working "
            "copy enough to ask, or the scan words the difference otherwise.",
            f"- Still asked: {q['still_asked']}.",
            f"- A scan would ask {q['asked_of_original']} of {name} now and {q['asked_of_new']} of the {r.reading} "
            f"reading with the carried transcriptions; {q['new']} of those are new ({q['new_likely']} likely)."
            + ("" if q["lexicon"] else " (Without the text rules as a second reader.)"),
            f"- One-reader suggestions held for the record: {q['held_original']} against {q['held_new']}.", "",
            "## Sections", "",
            f"Numbered by \"{r.sections.get('numbering', 'text')}\" (`living_docs.build`'s `numbering`), the outline "
            f"reads {r.sections['original']} numbered sections in {name} and {r.sections['new']} in the "
            f"{r.reading} reading."]
    if r.sections["only_original"]:
        out.append(f"Only in {name}: {', '.join(r.sections['only_original'][:40])}.")
    if r.sections["only_new"]:
        out.append(f"Only in the {r.reading} reading: {', '.join(r.sections['only_new'][:40])}.")
    if r.sections["new"] < 0.8 * r.sections["original"]:
        out += ["", f"**This numbering reads far fewer sections in the {r.reading} reading.** Its labels need the "
                "numbering's attention before a switch; the fates above follow from it."]
    out += ["", "A transcription is keyed by section number. Where a reading misreads a label (a section numbered "
            "otherwise, a cross-reference read as a heading), a carried transcription follows the number that reading "
            "gives, and one behind a second section of the same number cannot be keyed. Both readings here are numbered "
            "the same way, as the builds number them; a change of numbering moves sections again, so run this again "
            "after one.", ""]
    carried_score = next((s for label, s in r.scores if "carried" in label), None)
    if carried_score is not None:
        kinds = Counter(difference_kind(a, b) for _, a, b in carried_score.differences)
        common = Counter(f'"{a}" / "{b}"' for _, a, b in carried_score.differences).most_common(25)
        out += ["## Remaining differences", "",
                f"The {r.reading} reading with the carried transcriptions differs from the working copy in "
                f"{len(carried_score.differences)} places: " + ", ".join(f"{v} {k}" for k, v in kinds.most_common())
                + ". Some are the working copy's own slips.", "", "| The reading / the working copy | Times |",
                "|---|---:|"]
        out += [f"| {pair.replace('|', '/')} | {n} |" for pair, n in common]
        out.append("")
    rekeyed = [m for m in r.found if m.fate is Fate.REKEYED]
    if rekeyed:
        out += ["## Re-keyed (first 40)", "", "| Section | Was | Now reads | Right |", "|---|---|---|---|"]
        out += [f"| {m.section} | {_cell(m.row['wrong'])} | {_cell(m.wrong)} | {_cell(m.right)} |" for m in rekeyed[:40]]
        out.append("")
    unplaced = [m for m in r.found if m.fate in (Fate.UNPLACED, Fate.STALE)]
    if unplaced:
        out += ["## Unplaced and stale", "", "| Section | Wrong | Right | Fate | Why |", "|---|---|---|---|---|"]
        out += [f"| {m.row['section']} | {_cell(m.row['wrong'])} | {_cell(m.row['right'])} | {m.fate.value} | "
                f"{_cell(m.why)} |" for m in unplaced[:60]]
        out.append("")
    out += ["## To switch", "", "A person's decision. It keeps every file:", "", "```bash",
            f"jason living {r.key} --use-reread {r.reading} --yes --by NAME", "```", "",
            f"- `transcriptions.{r.reading}.json` becomes `transcriptions.json`; the set in use is kept as "
            f"`transcriptions.{r.original or 'original'}.backup.json`.",
            "- The proposed questions join the intake queue (`jason intake --subject reread:`).",
            f"- `reading.json` names the {r.reading} reading; every build reads it from then on.",
            "- The next `jason intake --scan` marks the open questions keyed to the old words stale.",
            "- The switch refuses if `transcriptions.json` changed since this report: run it again first."]
    return out


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")


def lines(r: Reread) -> list[str]:
    """The report's numbers for the terminal."""
    counts, q = r.counts(), r.questions
    out = [f"{r.key}: read again by the {r.reading} reading (sources/{r.files['new']}); the reading in use is unchanged."]
    out += [f"  {label}: WER {s.wer:.2%}, CER {s.cer:.2%} over {s.words:,} words" for label, s in r.scores]
    out.append(f"Transcriptions ({len(r.found)}): " + ", ".join(f"{counts.get(f.value, 0)} {f.value}" for f in Fate))
    out.append(f"Re-keyed questions proposed: {q['rekeyed_asks']} (for a person; none likely).")
    out.append(f"OCR questions open now: {q['open']}; {q['disappear']} would disappear ({q['disappear_words_gone']} whose "
               f"words the new reading no longer has, {q['disappear_reads_suggestion']} of them read as suggested; "
               f"{q['disappear_renumbered']} in a section numbered otherwise), {q['still_asked']} "
               f"still asked; {q['new']} new ({q['new_likely']} likely).")
    out.append(f"Sections (numbered by {r.sections.get('numbering', 'text')}): {r.sections['original']} in the reading "
               f"in use, {r.sections['new']} in the {r.reading} reading"
               + (": far fewer, so the numbering needs attention before a switch." if r.sections["new"]
                  < 0.8 * r.sections["original"] else "."))
    return out


def switch(living: Any, data_dir: Path, reading: str, by: str) -> list[str]:
    """Make ``reading`` the one every build reads: the migrated transcriptions become the active set (the old is kept
    as a backup), the proposed re-keyed questions join the intake queue, and ``reading.json`` records who chose it.
    Refuses unless the dry run's files are there and the transcriptions in use have not changed since."""
    from jason.community import intake
    from jason.community.intake import Ask, AskKind, AskStatus

    if not by:
        raise ValueError("a switch names the person who chose it (--by NAME)")
    key, data_dir = living.key, Path(data_dir)
    p = paths(data_dir, key, reading)
    if not p["detail"].is_file() or not p["transcriptions"].is_file():
        raise ValueError(f"no dry run for the {reading} reading: jason living {key} --reread {reading}")
    detail = json.loads(p["detail"].read_text(encoding="utf-8"))
    active = living_docs.transcriptions_path(data_dir, key)
    if detail.get("transcriptions_sha256", "") != _sha(active):
        raise ValueError(f"transcriptions.json changed since the dry run: jason living {key} --reread {reading} again")
    in_use = living_docs.chosen_reading(data_dir, key)
    if in_use != detail.get("in_use", ""):
        raise ValueError(f"the reading in use changed since the dry run: jason living {key} --reread {reading} again")
    numbered = detail.get("sections", {}).get("numbering", "text")
    if numbered != build_numbering(living):
        raise ValueError(f"the dry run numbered sections by {numbered!r}, and builds number them by "
                         f"{build_numbering(living)!r}: the migrated transcriptions are keyed to the wrong sections. Run "
                         f"jason living {key} --reread {reading} --numbering {build_numbering(living)} again")
    cache = living_docs.living_dir(data_dir, key) / "sources"
    if not (cache / detail["files"]["new"]).is_file():
        raise ValueError(f"the {reading} reading's text is gone: jason living {key} --reread {reading} again")
    backup = active.with_name(f"transcriptions.{in_use or 'original'}.backup.json")
    if backup.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        backup = active.with_name(f"transcriptions.{in_use or 'original'}.backup.{stamp}.json")
    out = []
    if active.is_file():
        shutil.copy2(active, backup)
        out.append(f"kept the transcriptions in use as {backup.name}")
    shutil.copy2(p["transcriptions"], active)
    out.append(f"transcriptions.json is now the migrated set ({len(_rows(active))} rows)")
    proposed = [Ask(r["id"], AskKind(r["kind"]), r["subject"], r["question"], tuple(r.get("choices") or ()),
                    r.get("suggestion", ""), bool(r.get("likely")), tuple(r.get("evidence") or ()),
                    dict(r.get("detail") or {}), AskStatus(r.get("status", "open"))) for r in _rows(p["asks"])]
    if proposed:
        intake.save(data_dir, intake.merge(intake.load(data_dir), proposed))
        out.append(f"{len(proposed)} re-keyed questions joined the intake queue (jason intake --subject reread:)")
    choice = living_docs.reading_choice_path(data_dir, key)
    choice.write_text(json.dumps({"reading": reading, "by": by,
                                  "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                  "previous": in_use, "backup": backup.name, "file": detail["files"]["new"]},
                                 indent=1), encoding="utf-8")
    out.append(f"{choice.name}: every build of {key} now reads the {reading} reading (chosen by {by})")
    out.append("next: jason living " + key + " --working, then jason intake --scan (stales the questions keyed to the "
               "old words)")
    return out


__all__ = ["Fate", "Migrated", "Reread", "Score", "base_provisions", "difference_kind", "dry_run", "lines", "markdown",
           "migrate", "migrated_rows", "page_tokens", "paths", "rekey_asks", "switch", "word_error"]
