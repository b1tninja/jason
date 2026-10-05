"""Layout marks: which of a form's options carry a mark, read from where the words sit on the page.

``checked_options`` reads options from the text alone, and leaves a blank-line option ``checked=None`` when its mark is
not on its own text line. A signed PDF often draws the marks in a separate text layer: the "X" sits on the option's
blank on the page, but the extracted text prints it lines later, after the list. Only the page layout can say which
option a mark belongs to, so this module reads the words with their boxes (PyMuPDF's ``page.get_text("words")``:
``x0, y0, x1, y1, word, block, line, wordno``).

``marks_from_words(words)`` finds:

- option lines: a blank ("______", or one already holding a mark, "__X__") or a box glyph at the start of its visual
  line, followed by a label with words. A signature block's blank ("Date: ____", "____ (print name)") is a field to
  fill, not an option.
- marks: a lone "X", "x", or check glyph (``MARK_GLYPHS``) that is not a word of a label's own text line.

Each mark is given to an option by the ``RULES`` rows, in order: first the option whose blank or box the mark overlaps,
then the option on the same baseline (centers within half a line) whose span, from just left of the blank to the
label's end, holds the mark's center. A rule that fits exactly one option decides. A mark that fits two options at the
deciding rule, or none at all, is never guessed: it is left unassigned and reported (``Unassigned``), and an option a
mark might belong to stays ``checked=None``.

An option with no mark reads ``False`` only when the page has a marks layer: at least one mark word on an option, or
beside one (``NEAR_RULES``: the option's column band, within ``NEAR_LINES`` of its line). A mark beside an option that
no ``RULES`` row gives it leaves that option ``None``. A mark far from every option (a table cell's "x", a signature
"X" at the foot of the page) is no evidence: it is reported, and alone it leaves every option ``None``. A page with no
such mark may carry its marks as drawings or an image, which the words cannot see, so its options stay ``None``. A box glyph reads as itself: a filled box is checked, an empty one is not, unless a mark overlaps it.

``marks_from_pdf(path, page_index)`` opens the PDF with pymupdf (``fitz`` on older installs) and reads one page.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from statistics import median

from jason.community.checked_options import _FORM_FIELD

LABEL_CAP = 120

MARK_GLYPHS = frozenset({"X", "x", "✓", "✔", "✗", "✘", "☓"})
_CHECKED_BOXES = frozenset({"☒", "☑"})
_EMPTY_BOXES = frozenset({"☐", "□"})
_MARK_CHARS = "".join(sorted(MARK_GLYPHS))

# A blank to mark is underscores, optionally holding one mark ("X____", "__X__", "____X"); at least three underscores.
_BLANK = re.compile(rf"^_*[{re.escape(_MARK_CHARS)}]?_*$")
_LETTERS = re.compile(r"[A-Za-z]")

# How far left of a blank a mark may sit and still be on it, and the widest gap inside one label, in line heights.
LEAD_LINES = 2.0
GAP_LINES = 4.0
# How far above or below an option's line a mark may sit and still show the page carries marks, in line heights.
NEAR_LINES = 1.0


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2

    def overlaps(self, other: Box) -> bool:
        return self.x0 < other.x1 and other.x0 < self.x1 and self.y0 < other.y1 and other.y0 < self.y1

    def union(self, other: Box) -> Box:
        return Box(min(self.x0, other.x0), min(self.y0, other.y0), max(self.x1, other.x1), max(self.y1, other.y1))


@dataclass(frozen=True)
class Word:
    box: Box
    text: str
    block: int = 0
    line: int = 0

    @classmethod
    def of(cls, t: Sequence) -> Word:
        """One PyMuPDF word tuple; block and line are optional."""
        block = int(t[5]) if len(t) > 5 else 0
        line = int(t[6]) if len(t) > 6 else 0
        return cls(Box(float(t[0]), float(t[1]), float(t[2]), float(t[3])), str(t[4]), block, line)


class OptionMarker(Enum):
    BLANK = "blank"
    MARKED_BLANK = "marked blank"  # the blank's own word holds the mark ("__X__")
    EMPTY_BOX = "empty box"
    CHECKED_BOX = "checked box"


@dataclass(frozen=True)
class LayoutOption:
    label: str
    checked: bool | None
    mark_box: Box | None
    label_box: Box
    marker: OptionMarker
    marker_box: Box


class MarkMiss(Enum):
    NO_OPTION = "no option"  # a mark beside no option: a signature "X", a stray
    AMBIGUOUS = "ambiguous"  # a mark that fits two options at the deciding rule


@dataclass(frozen=True)
class Unassigned:
    text: str
    box: Box
    miss: MarkMiss
    candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class LayoutReading:
    options: tuple[LayoutOption, ...]
    unassigned: tuple[Unassigned, ...]
    has_marks_layer: bool

    def selected(self) -> tuple[str, ...]:
        return tuple(o.label for o in self.options if o.checked is True)

    def not_selected(self) -> tuple[str, ...]:
        return tuple(o.label for o in self.options if o.checked is False)

    def unread(self) -> tuple[str, ...]:
        return tuple(o.label for o in self.options if o.checked is None)


@dataclass(frozen=True)
class _Candidate:
    """An option line before marks are given out."""

    marker: OptionMarker
    marker_box: Box
    label: str
    label_box: Box
    label_words: tuple[Word, ...]


@dataclass(frozen=True)
class MarkRule:
    """One way a mark belongs to an option; the first rule that fits any option decides."""

    name: str
    fits: Callable[[Box, _Candidate], bool]


def _line_height(c: _Candidate) -> float:
    return max(c.label_box.height, c.marker_box.height, 1.0)


def _same_baseline(mark: Box, c: _Candidate) -> bool:
    h = _line_height(c)
    if abs(mark.yc - c.label_box.yc) > h / 2:
        return False
    return c.marker_box.x0 - LEAD_LINES * h <= mark.xc <= c.label_box.x1


def _near(mark: Box, c: _Candidate) -> bool:
    """In the option's column band (from just left of the blank to the label's end) and within a line of it."""
    h = _line_height(c)
    if abs(mark.yc - c.label_box.yc) > NEAR_LINES * h:
        return False
    return c.marker_box.x0 - LEAD_LINES * h <= mark.xc <= c.label_box.x1


RULES: tuple[MarkRule, ...] = (
    MarkRule("overlaps the blank or box", lambda mark, c: mark.overlaps(c.marker_box)),
    MarkRule("on the option's baseline", _same_baseline),
)

# A mark that fits no RULES row but sits beside an option still shows the page carries marks; the options it sits
# beside stay unread. A mark far from every option (a table cell, a signature "X") is no evidence of either.
NEAR_RULES: tuple[MarkRule, ...] = (MarkRule("beside the option's line", _near),)


def _marker_of(text: str) -> OptionMarker | None:
    if text in _CHECKED_BOXES:
        return OptionMarker.CHECKED_BOX
    if text in _EMPTY_BOXES:
        return OptionMarker.EMPTY_BOX
    if _BLANK.match(text) and text.count("_") >= 3:
        return OptionMarker.MARKED_BLANK if any(ch in MARK_GLYPHS for ch in text) else OptionMarker.BLANK
    return None


def _on_line(a: Box, b: Box) -> bool:
    return abs(a.yc - b.yc) <= max(a.height, b.height, 1.0) / 2


def _candidates(words: Sequence[Word], marks: set[int]) -> list[tuple[_Candidate, int]]:
    """Each option line: a leading blank or box and the label words after it, with the marker word's index."""
    found: list[tuple[_Candidate, int]] = []
    for i, w in enumerate(words):
        marker = _marker_of(w.text)
        if marker is None:
            continue
        line = [(j, v) for j, v in enumerate(words) if j != i and j not in marks and _on_line(v.box, w.box)]
        # At the start of its line, or on a line that opens with another option ("___ A   ___ B").
        left = sorted((v for _, v in line if v.box.x1 <= w.box.x0 + 0.5), key=lambda v: v.box.x0)
        if left and _marker_of(left[0].text) is None:
            continue
        right = sorted((v for _, v in line if v.box.x0 >= w.box.x1 - 0.5), key=lambda v: v.box.x0)
        h = max(w.box.height, 1.0)
        label_words: list[Word] = []
        last = w.box.x1
        for v in right:
            if _marker_of(v.text) is not None or v.box.x0 - last > GAP_LINES * h:
                break
            label_words.append(v)
            last = v.box.x1
        if not label_words:
            continue
        label = " ".join(v.text for v in label_words).strip()
        # A field's words may end in a colon ("Name:"); the shared pattern reads them without it.
        if not _LETTERS.search(label) or _FORM_FIELD.match(label.rstrip(": \t")):
            continue
        box = label_words[0].box
        for v in label_words[1:]:
            box = box.union(v.box)
        found.append((_Candidate(marker, w.box, label[:LABEL_CAP].rstrip(), box, tuple(label_words)), i))
    return found


def _is_label_text(mark: Word, words: Sequence[Word], marks: set[int]) -> bool:
    """A mark glyph printed inside a label's own text line ("2 x 4 lumber") is a word, not a mark."""
    for j, v in enumerate(words):
        if j in marks or v is mark or _marker_of(v.text) is not None:
            continue
        if (v.block, v.line) == (mark.block, mark.line) and _on_line(v.box, mark.box) and v.box.x1 <= mark.box.x0 + 0.5:
            return True
    return False


def marks_from_words(words: Iterable[Sequence]) -> LayoutReading:
    """Read one page's PyMuPDF word tuples: its option lines and which carry a mark.

    Note: a mark is given to an option only when exactly one option fits it at the first ``RULES`` row any option
    fits; otherwise it comes back in ``unassigned`` and the options it might belong to stay ``checked=None``.
    """
    ws = [Word.of(t) for t in words]
    glyphs = {i for i, w in enumerate(ws) if w.text in MARK_GLYPHS}
    marks = {i for i in glyphs if not _is_label_text(ws[i], ws, glyphs)}
    candidates = _candidates(ws, marks)
    # A word that heads an option line is a marker, never also a mark.
    marks -= {i for _, i in candidates}
    cands = [c for c, _ in candidates]

    given: dict[int, Box] = {}
    doubtful: set[int] = set()
    unassigned: list[Unassigned] = []
    has_layer = False  # a mark on or beside an option; a mark far from every option says nothing
    for i in sorted(marks, key=lambda k: (ws[k].box.y0, ws[k].box.x0)):
        mark = ws[i]
        fitting: list[int] = []
        for rule in RULES:
            fitting = [k for k, c in enumerate(cands) if rule.fits(mark.box, c)]
            if fitting:
                break
        if len(fitting) == 1:
            k = fitting[0]
            given[k] = given[k].union(mark.box) if k in given else mark.box
            has_layer = True
        elif fitting:
            doubtful.update(fitting)
            has_layer = True
            unassigned.append(
                Unassigned(mark.text, mark.box, MarkMiss.AMBIGUOUS, tuple(cands[k].label for k in fitting)))
        else:
            near = [k for k, c in enumerate(cands) if any(rule.fits(mark.box, c) for rule in NEAR_RULES)]
            if near:
                doubtful.update(near)
                has_layer = True
            unassigned.append(Unassigned(mark.text, mark.box, MarkMiss.NO_OPTION))

    options: list[LayoutOption] = []
    for k, c in enumerate(cands):
        mark_box = given.get(k)
        if mark_box is not None or c.marker in (OptionMarker.MARKED_BLANK, OptionMarker.CHECKED_BOX):
            checked: bool | None = True
            if mark_box is None and c.marker is OptionMarker.MARKED_BLANK:
                mark_box = c.marker_box
        elif k in doubtful:
            checked = None
        elif c.marker is OptionMarker.EMPTY_BOX or has_layer:
            checked = False
        else:
            checked = None
        options.append(LayoutOption(c.label, checked, mark_box, c.label_box, c.marker, c.marker_box))
    options.sort(key=lambda o: (o.marker_box.y0, o.marker_box.x0))
    return LayoutReading(tuple(options), tuple(unassigned), has_layer)


def _open(path: str | Path):
    try:
        import pymupdf
    except ImportError:  # older installs name the module fitz
        import fitz as pymupdf
    return pymupdf.open(str(path))


def marks_from_pdf(path: str | Path, page_index: int) -> LayoutReading:
    """Read page ``page_index`` (0-based) of the PDF at ``path`` with ``marks_from_words``."""
    doc = _open(path)
    try:
        words = doc[page_index].get_text("words")
    finally:
        doc.close()
    return marks_from_words(words)


__all__ = [
    "GAP_LINES",
    "LABEL_CAP",
    "LEAD_LINES",
    "MARK_GLYPHS",
    "NEAR_LINES",
    "NEAR_RULES",
    "RULES",
    "Box",
    "LayoutOption",
    "LayoutReading",
    "MarkMiss",
    "MarkRule",
    "OptionMarker",
    "Unassigned",
    "Word",
    "marks_from_pdf",
    "marks_from_words",
]
