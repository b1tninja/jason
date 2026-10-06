"""A document's headings and sections read from its PDF alone: clues in order of cost, each an ablatable rule row.

A PDF has no paragraph styles, no list numbering, and no page breaks, only glyphs at places, and sometimes a text layer,
bookmarks, and a contents page. This reader gets the structure back from those clues (docs/structure-recovery.md),
and a benchmark scores it against a Google Doc's own structure (``structure_gold``, ``structure_fuzz``).

The steps:

1. **Lines.** The text layer's lines with their type size, weight, and place; for a page with no text layer, the lines
   of Tesseract's words, the size taken from the words' heights and no weight known.
2. **Furniture.** A running header or footer (a line in the band at a page's edge that repeats down the pages) and the
   page numbers are taken out and kept, not read as headings.
3. **Clues.** Each ``Clue`` row votes on lines: ``bookmark`` (the file's own outline), ``toc`` (a contents page, each
   entry checked against a heading in the body), ``size``, ``weight``, ``caps``, ``numbering`` (the grammar of
   ``structure_numbering``), ``spacing``, ``indent``, and ``sequence`` (a number that follows the one before it).
   A gap, a repeat, or a number out of order is a finding, kept as read.
4. **Tiers.** A line is a heading when its clues' weights reach ``MIN_SCORE``. It is ``likely`` when clues of two
   different families agree, and ``suggested`` when one family made it. Nothing is presented as sure.
5. **Levels.** From a bookmark's level or a contents entry's indent, else from the rank of the heading's style
   (size, then number depth, caps, and weight), the level scale anchored on the style that carries the first-depth numbers.

``outline_from_pdf`` returns the same ``DocumentOutline`` shape the other readers return. It changes no stored outline.
A model may be a labeled second reader for the ``suggested`` headings (``Recovery.unsure``); it is not called here.
Nothing here names an association.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from jason.community.outlines import DocumentOutline, Section, normalize_number
from jason.community.structure_numbering import (Number, NumberKind, SequenceCheck, contents_entries, fold_number,
                                                 fold_text, is_contents_page, split_number)

MIN_SCORE = 0.8
TOP_BAND = 0.085            # a page number alone lies in this share of the page's height from the top edge
BOTTOM_BAND = 0.915         # or below this share from the top
TOP_ZONE = 0.16             # a running header lies in this share of the page's height from the top edge
BOTTOM_ZONE = 0.86          # and a running footer below this
SHORT_CHARS = 100
SHORT_WORDS = 14
TEXT_CHARS = 25             # a page with fewer letters and digits than this in its text layer has none to read
MIN_CONFIDENCE = 35.0       # an OCR line whose words average less than this is not read
SIMILAR = 0.82              # two lines this alike (folded) are the same line


@dataclass(frozen=True)
class Clue:
    name: str
    family: str             # clues of one family are not independent of each other
    weight: float
    cost: int               # 0 free, 1 a parse, 2 a pass over the lines, 3 geometry, 4 needs the others
    note: str
    votes: bool = True      # a row that votes on lines; False for one that changes how the pages are read


CLUES: tuple[Clue, ...] = (
    Clue("bookmark", "outline", 1.2, 0, "the file's own bookmarks: title, level, page"),
    Clue("toc", "contents", 1.0, 1, "a contents page's entry, found again as a heading in the body"),
    Clue("size", "typography", 0.8, 2, "a line set larger than the body"),
    Clue("weight", "typography", 0.5, 2, "a short bold line"),
    Clue("caps", "typography", 0.5, 2, "a short line in capitals"),
    Clue("numbering", "numbering", 0.7, 2, "a line that starts with a number of the grammar"),
    Clue("spacing", "layout", 0.3, 3, "a short line with air above it"),
    Clue("indent", "layout", 0.3, 3, "a short centered line"),
    Clue("sequence", "numbering", 0.4, 4, "a number that follows the one before it in its family"),
    Clue("page_order", "order", 0.0, 1, "pages read in the order of their printed numbers when the file's order breaks them",
         votes=False),
)
BY_NAME = {c.name: c for c in CLUES}


# --- lines ----------------------------------------------------------------------------------------------------------


@dataclass
class PLine:
    page: int                       # 1-based
    text: str
    x0: float                       # points
    x1: float
    top: float
    bottom: float
    size: float                     # points; for OCR the words' height, not a font size
    bold: bool | None = None        # None: not known (OCR)
    pw: float = 612.0
    ph: float = 792.0
    source: str = "text"            # "text" or "ocr"
    conf: float = 100.0
    gap_above: float = -1.0         # in body-size units; -1 at the top of a page
    furniture: str = ""             # "header", "footer", "page number", or ""
    start: int = 0                  # offset in Recovery.text

    @property
    def words(self) -> int:
        return len(self.text.split())

    @property
    def caps(self) -> bool:
        letters = [c for c in self.text if c.isalpha()]
        return len(letters) >= 3 and sum(c.isupper() for c in letters) / len(letters) > 0.85

    @property
    def centered(self) -> bool:
        return abs((self.x0 + self.x1) / 2 - self.pw / 2) < 0.04 * self.pw and (self.x1 - self.x0) < 0.7 * self.pw

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in ("page", "text", "x0", "x1", "top", "bottom", "size", "bold", "pw", "ph",
                                              "source", "conf")}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PLine:
        return cls(**raw)


_ZERO_WIDTH = re.compile("[\\u200b\\u200c\\u200d\\ufeff\\u00ad]")


def _alnum(text: str) -> int:
    return sum(c.isalnum() for c in text)


def text_lines(page: Any, number: int) -> list[PLine]:
    """The lines of a page's text layer: each with its size (the largest span's), weight (most of its characters), and
    box. Text drawn in pieces on one baseline (a list's label and its words) is joined into one line."""
    pw, ph = float(page.rect.width), float(page.rect.height)
    raw: list[PLine] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            n = sum(len(s["text"].strip()) for s in spans)
            bold_n = sum(len(s["text"].strip()) for s in spans if s["flags"] & 16 or re.search(r"bold|black|heavy|-bd\b",
                                                                                              s["font"], re.I))
            size = max(s["size"] for s in spans)
            x0, y0, x1, y1 = line["bbox"]
            raw.append(PLine(number, _ZERO_WIDTH.sub("", "".join(s["text"] for s in line["spans"])).strip(), x0, x1, y0, y1, round(size, 2),
                             bold_n * 2 >= n, pw, ph))
    raw.sort(key=lambda ln: (round(ln.bottom), ln.x0))
    out: list[PLine] = []
    for ln in raw:
        prev = out[-1] if out else None
        if prev and abs(prev.bottom - ln.bottom) < 0.35 * max(prev.size, ln.size) and -1 <= ln.x0 - prev.x1 < 2.5 * max(prev.size, ln.size):
            prev.text = f"{prev.text} {ln.text}"
            prev.x1 = max(prev.x1, ln.x1)
            prev.top = min(prev.top, ln.top)
            prev.size = max(prev.size, ln.size)
            prev.bold = bool(prev.bold) and bool(ln.bold)
            continue
        out.append(ln)
    out.sort(key=lambda ln: (ln.top, ln.x0))
    return out


def ocr_lines(words: Sequence[Any], number: int, *, dpi: int, pw: float = 612.0, ph: float = 792.0) -> list[PLine]:
    """The lines of Tesseract's words on one page (``ocr.TesseractWord``), pixels at ``dpi`` taken to points. The size
    is the height of the line's tallest word (the second tallest of four or more), which holds an ascender and a descender."""
    k = 72.0 / dpi
    groups: dict[tuple, list[Any]] = {}
    for w in words:
        groups.setdefault((w.block, w.paragraph, w.line), []).append(w)
    out = []
    for g in groups.values():
        g = sorted(g, key=lambda w: w.left)
        heights = sorted((w.height for w in g), reverse=True)
        # The tallest word holds an ascender and a descender, so its box is the line's full extent; with four words or more the
        # second tallest is taken, so one word with a speck on it does not stand for the line.
        size = heights[1 if len(heights) >= 4 else 0] * k / 0.72
        text = " ".join(w.text for w in g)
        conf = statistics.mean(w.confidence for w in g)
        if conf < MIN_CONFIDENCE or _alnum(text) < 0.4 * len(text.replace(" ", "")):
            continue                              # the ghost of a page's other side, or dust: not a line
        out.append(PLine(number, text, min(w.left for w in g) * k, max(w.left + w.width for w in g) * k,
                         min(w.top for w in g) * k, max(w.top + w.height for w in g) * k, round(size, 2), None, pw, ph,
                         "ocr", conf))
    out.sort(key=lambda ln: (ln.top, ln.x0))
    return _join_rows(out)


def _join_rows(lines: list[PLine]) -> list[PLine]:
    """Tesseract may split a row into two lines (a label and its words, set far apart): join lines of one baseline."""
    out: list[PLine] = []
    for ln in sorted(lines, key=lambda l: (round(l.bottom / 4), l.x0)):
        prev = out[-1] if out else None
        if prev and abs(prev.bottom - ln.bottom) < 0.3 * max(prev.size, ln.size) and 0 <= ln.x0 - prev.x1 < 3 * max(prev.size, ln.size):
            prev.text = f"{prev.text} {ln.text}"
            prev.x1 = max(prev.x1, ln.x1)
            prev.size = max(prev.size, ln.size)
            continue
        out.append(ln)
    out.sort(key=lambda l: (l.top, l.x0))
    return out


WordsOf = Callable[[int, Any], Sequence[Any]]


def extract_lines(doc: Any, *, words_of: Callable[[int, Any], tuple[Sequence[Any], int]] | None = None) -> tuple[list[PLine], list[str]]:
    """Every page's lines, and per page where they came from ("text", "ocr", or "none"). ``words_of(page_number, page)``
    reads a page that has no text layer and gives (Tesseract's words, the dpi they were read at); without it such a page
    has no lines."""
    lines: list[PLine] = []
    sources = []
    for i, page in enumerate(doc):
        got = text_lines(page, i + 1)
        if sum(_alnum(l.text) for l in got) >= TEXT_CHARS:
            lines += got
            sources.append("text")
        elif words_of is not None:
            words, dpi = words_of(i + 1, page)
            got = ocr_lines(words, i + 1, dpi=dpi, pw=float(page.rect.width), ph=float(page.rect.height))
            lines += got
            sources.append("ocr" if got else "none")
        else:
            sources.append("none")
    return lines, sources


# --- furniture ------------------------------------------------------------------------------------------------------

_PAGE_NUMBER = re.compile(r"^[\s\-–—~•.|]*(?:page\s*)?(\d{1,4}|[ivxlc]{1,6})(?:\s*(?:of|/)\s*\d{1,4})?[\s\-–—~•.|]*$", re.I)


def _band(ln: PLine) -> str:
    """The zone a line sits in: "header" in the top of the page, "footer" in the bottom, else "". A running line may be set
    well down the margin (a header in 18 point type ends at a tenth of the page), so the zones are wide; only lines that
    repeat are taken out of them."""
    if ln.bottom <= TOP_ZONE * ln.ph:
        return "header"
    if ln.top >= BOTTOM_ZONE * ln.ph:
        return "footer"
    return ""


def _edge(ln: PLine) -> bool:
    """In the strip at the very edge, where a page number alone is one."""
    return ln.bottom <= TOP_BAND * ln.ph or ln.top >= BOTTOM_BAND * ln.ph


def _runs(pages: Iterable[int]) -> list[list[int]]:
    runs: list[list[int]] = []
    for p in sorted(set(pages)):
        if runs and p == runs[-1][-1] + 1:
            runs[-1].append(p)
        else:
            runs.append([p])
    return runs


def mark_furniture(lines: list[PLine], pages: int) -> dict[int, str]:
    """Marks running headers and footers and page numbers (``line.furniture``) and returns the printed page number of the
    pages that carry one. A line in a zone at a page's edge is a running line when lines like it (digits ignored,
    ``SIMILAR`` alike, about the same place) run down three pages in a row, or down a quarter of the pages; of two pages
    in a row the second is the running one (the first is a title). A page number is a line of a number alone at the edge."""
    labels: dict[int, str] = {}
    zoned = [(ln, _band(ln)) for ln in lines]
    clusters: list[dict[str, Any]] = []
    for ln, zone in zoned:
        if not zone:
            continue
        key = fold_text(re.sub(r"\d+", "", ln.text))
        if not key:
            continue
        for c in clusters:
            if c["zone"] == zone and abs(c["y"] - ln.top) <= 0.012 * ln.ph and (
                    c["key"] == key or SequenceMatcher(None, c["key"], key).ratio() >= SIMILAR):
                c["pages"].add(ln.page)
                break
        else:
            clusters.append({"zone": zone, "key": key, "y": ln.top, "pages": {ln.page}})
    need = max(3, int(0.25 * pages + 0.999))
    running: list[tuple[dict[str, Any], set[int]]] = []
    for c in clusters:
        marked: set[int] = set()
        if len(c["pages"]) >= need:
            marked = set(c["pages"])
        else:
            for run in _runs(c["pages"]):
                if len(run) >= 3:
                    marked |= set(run)
                elif len(run) == 2:
                    marked.add(run[1])
        if marked:
            running.append((c, marked))
    for ln, zone in zoned:
        if not zone:
            continue
        key = fold_text(re.sub(r"\d+", "", ln.text))
        if _edge(ln) and (m := _PAGE_NUMBER.match(ln.text.strip())):
            ln.furniture = "page number"
            labels.setdefault(ln.page, m.group(1))
            continue
        for c, marked in running:
            if (c["zone"] == zone and ln.page in marked and abs(c["y"] - ln.top) <= 0.012 * ln.ph
                    and (c["key"] == key or SequenceMatcher(None, c["key"], key).ratio() >= SIMILAR)):
                ln.furniture = zone
                if zone == "footer" and (m := re.search(r"\bpage\s*(\d{1,4})\b|(?<!\d)(\d{1,4})\s*$", ln.text, re.I)):
                    labels.setdefault(ln.page, m.group(1) or m.group(2))
                break
    return labels


def printed_order(labels: dict[int, str], pages: int) -> tuple[dict[int, float], int]:
    """A reading rank for each page: its printed number when most pages print one and the file's order breaks them (a
    scanner that interleaved sides); a page with no number keeps its place after the page before it. Returns the ranks and
    how many pages moved."""
    nums = {p: int(v) for p, v in labels.items() if v.isdigit()}
    ordered = [nums[p] for p in sorted(nums)]
    if len(nums) < 0.7 * pages or ordered == sorted(ordered) or len(set(ordered)) != len(ordered):
        return {p: float(p) for p in range(1, pages + 1)}, 0
    rank: dict[int, float] = {}
    last = 0.0
    for p in range(1, pages + 1):
        last = float(nums[p]) if p in nums else last + 0.001
        rank[p] = last
    moved = sum(1 for k, p in enumerate(sorted(rank, key=rank.get), 1) if p != k)
    return rank, moved


def body_size(lines: Iterable[PLine]) -> float:
    sizes = sorted(l.size for l in lines if not l.furniture and l.size for _ in range(max(1, _alnum(l.text) // 20)))
    return sizes[len(sizes) // 2] if sizes else 11.0


def set_gaps(lines: list[PLine], body: float) -> None:
    prev: PLine | None = None
    for ln in lines:
        if ln.furniture:
            continue
        ln.gap_above = (ln.top - prev.bottom) / body if prev is not None and prev.page == ln.page else -1.0
        prev = ln


# --- clue votes -----------------------------------------------------------------------------------------------------


@dataclass
class Candidate:
    line: PLine
    index: int                                     # position among the body lines
    votes: dict[str, str] = field(default_factory=dict)      # clue name -> its note
    number: Number | None = None
    level_hint: dict[str, int] = field(default_factory=dict)  # "bookmark", "toc" -> a level
    merged: list[PLine] = field(default_factory=list)         # a wrapped heading's later lines

    def score(self, rows: dict[str, Clue]) -> float:
        total = 0.0
        for name in self.votes:
            if name not in rows:
                continue
            w = rows[name].weight
            if name == "numbering" and self.number is not None and self.number.kind is NumberKind.PAREN:
                w = min(w, 0.3)
            total += w
        return total

    def families(self, rows: dict[str, Clue]) -> set[str]:
        return {rows[n].family for n in self.votes if n in rows}

    @property
    def text(self) -> str:
        return " ".join([self.line.text, *(m.text for m in self.merged)])


def _short(ln: PLine) -> bool:
    return len(ln.text) <= SHORT_CHARS and ln.words <= SHORT_WORDS


def _sentence(ln: PLine) -> bool:
    """A line that reads as the middle of prose: it ends in a period or a comma after several words, or it begins in
    lower case (a heading does not)."""
    first = next((c for c in ln.text if c.isalpha()), "")
    if first.islower() and not ln.text.lstrip()[:1] in "([":
        return True
    if ln.text.rstrip().endswith(":") and ln.words <= 5 and not re.match(r"^\W*(?:\d|[A-Z]\.|\()", ln.text):
        return True                      # a field's label ("NAME:") is not a heading
    return ln.words >= 4 and ln.text.rstrip().endswith((".", ",", ";"))


def vote_size(cands: list[Candidate], body: float, lines: Sequence[PLine]) -> None:
    """Lines larger than the body whose size is used by few lines: a heading's size, not a block of large type."""
    bins = Counter(round(l.size / body * 10) for l in lines if not l.furniture)
    total = sum(bins.values()) or 1
    for c in cands:
        b = round(c.line.size / body * 10)
        # An OCR height wanders with the letters a line holds (descenders, ascenders): it needs more to count.
        floor = 1.12 if c.line.source == "text" else 1.25
        if c.line.size / body >= floor and bins[b] / total <= 0.2 and _short(c.line) and not _sentence(c.line):
            c.votes["size"] = f"{c.line.size / body:.2f}x body"


def vote_weight(cands: list[Candidate], body: float, lines: Sequence[PLine]) -> None:
    for c in cands:
        ln = c.line
        if ln.bold and _short(ln) and not _sentence(ln) and ln.size / body >= 0.95:
            c.votes["weight"] = "bold"


def vote_caps(cands: list[Candidate], body: float, lines: Sequence[PLine]) -> None:
    for c in cands:
        ln = c.line
        words = [w for w in re.findall(r"[A-Za-z]+", ln.text) if len(w) > 1]
        if ln.caps and _short(ln) and not _sentence(ln) and (len(words) >= 2 or (words and len(words[0]) >= 4)):
            c.votes["caps"] = "capitals"


_NUMBERED_TITLE = re.compile(r"^[A-Z0-9\"'“(]")


def vote_numbering(cands: list[Candidate], body: float, lines: Sequence[PLine]) -> None:
    for c in cands:
        n = split_number(c.line.text)
        if n is None or not _short(c.line) or _sentence(c.line):
            continue
        if n.rest and not _NUMBERED_TITLE.match(n.rest):
            continue
        if n.kind is NumberKind.PAREN and (len(n.rest.split()) > 6 or not n.rest):
            continue
        if n.kind in (NumberKind.CAPITAL, NumberKind.ROMAN) and not n.rest:
            continue
        c.number = n
        c.votes["numbering"] = n.kind.value


def vote_spacing(cands: list[Candidate], body: float, lines: Sequence[PLine]) -> None:
    for c in cands:
        if c.line.gap_above >= 0.65 and _short(c.line) and not _sentence(c.line):
            c.votes["spacing"] = f"{c.line.gap_above:.2f} body above"


def vote_indent(cands: list[Candidate], body: float, lines: Sequence[PLine]) -> None:
    for c in cands:
        if c.line.centered and _short(c.line) and not _sentence(c.line) and c.line.words >= 1:
            c.votes["indent"] = "centered"


def vote_sequence(cands: list[Candidate], findings: list[dict[str, str]]) -> None:
    """Among the lines the numbering clue read: a number that is the successor of the one before it (or the first of its
    family) is one more clue; a gap, a repeat, or a number out of order is a finding and no clue."""
    check = SequenceCheck()
    for c in cands:
        if c.number is None or "numbering" not in c.votes:
            continue
        if c.number.kind is NumberKind.PAREN and not (c.votes.keys() - {"numbering"}):
            continue
        state = check.see(c.number)
        if state in ("next", "first"):
            c.votes["sequence"] = state
        elif state in ("gap", "repeat", "out of order"):
            f = check.findings[-1]
            findings.append({"kind": f"numbering {state}", "page": str(c.line.page), "printed": f.printed, "after": f.after})


def _norm_title(text: str) -> str:
    n = split_number(text)
    return fold_text(n.rest if n and n.rest else text)


def _like(a: str, b: str, floor: float = 0.0) -> float:
    """How alike two folded titles are, 0 to 1; 0 when the cheap bounds already put them under ``floor``."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    m = SequenceMatcher(None, a, b)
    if m.real_quick_ratio() < floor or m.quick_ratio() < floor:
        return 0.0
    return m.ratio()


def _folds(c: Candidate) -> tuple[str, str]:
    """A candidate's words folded, with and without its number, worked out once."""
    got = getattr(c, "_folds", None)
    if got is None:
        got = c._folds = (_norm_title(c.text), fold_text(c.text))
    return got


def vote_bookmarks(cands: list[Candidate], toc: Sequence[Sequence[Any]], findings: list[dict[str, str]]) -> list[tuple[int, str, int]]:
    """Votes from the file's bookmarks ([level, title, page]): the line on the bookmark's page (or the next) whose words are
    the title's. Returns the bookmarks no line was found for (they are headings the page does not show as lines)."""
    by_page: dict[int, list[Candidate]] = {}
    for c in cands:
        by_page.setdefault(c.line.page, []).append(c)
    lost = []
    for level, title, page in ((int(e[0]), str(e[1]).strip(), int(e[2])) for e in toc):
        want = _norm_title(title)
        best, best_r = None, 0.0
        for p in (page, page + 1, page - 1):
            for c in by_page.get(p, ()):
                a, b = _folds(c)
                r = max(_like(want, a, 0.85), _like(fold_text(title), b, 0.85))
                if r > best_r + (0.0 if p == page else -0.05):
                    best, best_r = c, r
        if best is not None and best_r >= 0.85:
            best.votes["bookmark"] = f"level {level}"
            best.level_hint["bookmark"] = level
        else:
            lost.append((level, title, page))
            findings.append({"kind": "bookmark with no heading found", "page": str(page), "printed": "", "after": ""})
    return lost


def vote_toc(cands: list[Candidate], page_lines: dict[int, list[PLine]], toc_pages: set[int], labels: dict[int, str],
             findings: list[dict[str, str]]) -> dict[str, int]:
    """Each entry of a contents page, found again as a line in the body. The printed page of an entry is turned into a
    PDF page through ``labels`` when the pages print numbers, and the line sought on that page and the next. An entry no
    heading answers is a finding. Returns counts: entries, verified, unverified."""
    label_page = {v.casefold(): p for p, v in labels.items()}
    body = [c for c in cands if c.line.page not in toc_pages]
    by_page: dict[int, list[Candidate]] = {}
    for c in body:
        by_page.setdefault(c.line.page, []).append(c)
    counts = {"entries": 0, "verified": 0, "unverified": 0}
    for p in sorted(toc_pages):
        lines = [l for l in page_lines.get(p, []) if not l.furniture]
        entries = contents_entries([l.text for l in lines], loose=True)
        xs = sorted({round(l.x0 / 6) for l in lines if any(l.text.startswith(t[:12]) for t, _ in entries)})
        for title, printed in entries:
            counts["entries"] += 1
            want = _norm_title(title)
            level = 1
            for l in lines:
                if l.text.startswith(title[:12]):
                    level = 1 + xs.index(round(l.x0 / 6)) if round(l.x0 / 6) in xs else 1
                    break
            expect = label_page.get(printed.casefold())
            pool: Iterable[Candidate]
            if expect is not None:
                pool = [c for q in (expect, expect + 1) for c in by_page.get(q, ())]
            else:
                pool = body
            best, best_r = None, 0.0
            full = fold_text(title)
            for c in pool:
                if not _short(c.line):
                    continue
                a, b = _folds(c)
                r = max(_like(want, a, 0.85), _like(full, b, 0.85))
                if r > best_r:
                    best, best_r = c, r
            if best is not None and best_r >= 0.85:
                best.votes["toc"] = f"entry for page {printed}"
                best.level_hint["toc"] = level
                counts["verified"] += 1
            else:
                counts["unverified"] += 1
                findings.append({"kind": "contents entry with no heading", "page": str(p), "printed": printed, "after": ""})
    return counts


# --- assembling -----------------------------------------------------------------------------------------------------


@dataclass
class PNode:
    text: str
    number: str                    # as printed
    title: str
    level: int
    page: int
    start: int
    clues: list[str]
    families: list[str]
    tier: str                      # "likely" or "suggested"
    score: float
    size: float = 0.0
    bold: bool | None = None
    caps: bool = False
    source: str = "text"
    parent: int = -1
    level_from: str = ""
    kind: str = "heading"

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class Recovery:
    nodes: list[PNode] = field(default_factory=list)
    text: str = ""
    pages: int = 0
    sources: list[str] = field(default_factory=list)          # per page: text, ocr, or none
    labels: dict[int, str] = field(default_factory=dict)      # PDF page -> its printed page number
    running: dict[int, list[str]] = field(default_factory=dict)   # PDF page -> running header and footer lines taken out
    parts: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, str]] = field(default_factory=list)
    toc: dict[str, int] = field(default_factory=dict)
    clues: tuple[str, ...] = ()
    body_size: float = 0.0

    @property
    def unsure(self) -> list[PNode]:
        """The headings one family of clues made: where a model, as a labeled second reader, may be asked."""
        return [n for n in self.nodes if n.tier == "suggested"]

    def to_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["nodes"] = [n.to_dict() for n in self.nodes]
        d["labels"] = {str(k): v for k, v in self.labels.items()}
        d["running"] = {str(k): v for k, v in self.running.items()}
        return d


VOTERS: dict[str, Callable] = {"size": vote_size, "weight": vote_weight, "caps": vote_caps, "numbering": vote_numbering,
                               "spacing": vote_spacing, "indent": vote_indent}


def _signature(c: Candidate, body: float) -> tuple:
    ln = c.line
    return (round(ln.size / body * 10) if ln.source == "text" else round(ln.size / body * 8),
            bool(ln.bold), ln.caps, ln.centered)


def assign_levels(chosen: list[Candidate], body: float) -> dict[int, tuple[int, str]]:
    """Levels by index into ``chosen``: (level, what it came from). A bookmark's level, or a contents entry's indent,
    wins; else the rank of the heading's style among the styles seen (size, then number depth, caps, weight), with the
    scale anchored on the style whose members carry first-depth numbers: larger styles above it are level 0 (a title, a
    part), the rest follow; a number with no style of its own takes its depth."""
    out: dict[int, tuple[int, str]] = {}
    sigs: dict[tuple, list[int]] = {}
    for i, c in enumerate(chosen):
        if "bookmark" in c.level_hint:
            out[i] = (c.level_hint["bookmark"], "bookmark")
        elif "toc" in c.level_hint:
            out[i] = (c.level_hint["toc"], "toc")
        if any(n in c.votes for n in ("size", "weight", "caps")):
            sigs.setdefault(_signature(c, body), []).append(i)

    def depth_of(i: int) -> float | None:
        n = chosen[i].number
        return n.depth if n is not None and n.depth else None

    def mean_depth(idx: list[int]) -> float:
        ds = [d for i in idx if (d := depth_of(i)) is not None]
        return statistics.mean(ds) if ds else 9.0

    order = sorted(sigs, key=lambda s: (-s[0], not s[3], mean_depth(sigs[s]), not s[2], not s[1]))
    rank = {s: k + 1 for k, s in enumerate(order)}
    anchor = None
    for s in order:
        first = [i for i in sigs[s] if (depth_of(i) or 9) == 1]
        if first:
            anchor = rank[s]
            break
    if anchor is None:
        anchor = 1
        # A style used once, much larger than the next, is the document's title.
        if order and len(sigs[order[0]]) == 1 and len(order) > 1 and order[0][0] >= 1.3 * order[1][0]:
            anchor = 2
    for s, idx in sigs.items():
        level = 0 if rank[s] < anchor else rank[s] - anchor + 1
        for i in idx:
            out.setdefault(i, (level, "style"))
    stack: list[tuple[int, int]] = []
    for i, c in enumerate(chosen):
        if i not in out:
            if c.number is not None and c.number.depth:
                out[i] = (c.number.depth, "number depth")
            else:
                parent_level = stack[-1][0] if stack else 0
                out[i] = (parent_level + 1, "parent")
        while stack and stack[-1][0] >= out[i][0]:
            stack.pop()
        stack.append((out[i][0], i))
    return out


def recover(lines: list[PLine], pages: int, *, toc: Sequence[Sequence[Any]] = (), clues: Iterable[str] | None = None,
            min_score: float = MIN_SCORE, sources: Sequence[str] = (), marks: Sequence[dict[str, Any]] | None = None) -> Recovery:
    """Headings and their levels from a PDF's lines. ``clues`` names the rows to use (all by default): a run with one left
    out is how a clue's worth is measured. ``toc`` is the file's bookmarks ([level, title, page])."""
    rows = {c.name: c for c in CLUES if clues is None or c.name in set(clues)}
    out = Recovery(pages=pages, sources=list(sources), clues=tuple(rows))
    out.labels = mark_furniture(lines, pages)
    for ln in lines:
        if ln.furniture:
            out.running.setdefault(ln.page, []).append(ln.text)
    body = body_size(lines)
    out.body_size = body
    rank = {p: p for p in range(1, pages + 1)}
    if "page_order" in rows:
        rank, moved = printed_order(out.labels, pages)
        if moved:
            out.findings.append({"kind": "pages out of order by their printed numbers", "page": "", "printed": str(moved), "after": ""})
    lines = sorted(lines, key=lambda l: (rank.get(l.page, l.page), l.top, l.x0))
    set_gaps(lines, body)
    body_lines = [l for l in lines if not l.furniture]
    pieces, at = [], 0
    for ln in body_lines:
        ln.start = at
        pieces.append(ln.text + "\n")
        at += len(ln.text) + 1
    out.text = "".join(pieces)
    page_lines: dict[int, list[PLine]] = {}
    for ln in lines:
        page_lines.setdefault(ln.page, []).append(ln)
    toc_pages = {p for p, ls in page_lines.items() if "toc" in rows and is_contents_page([l.text for l in ls if not l.furniture])}
    cands = [Candidate(l, i) for i, l in enumerate(body_lines) if l.page not in toc_pages or "toc" not in rows]
    for name, fn in VOTERS.items():
        if name in rows:
            fn(cands, body, body_lines)
    if "numbering" not in rows:
        for c in cands:
            c.number = split_number(c.line.text)       # the printed number is still read off a line chosen by other clues
    if "sequence" in rows and "numbering" in rows:
        vote_sequence(cands, out.findings)
    if "bookmark" in rows and toc:
        vote_bookmarks(cands, toc, out.findings)
    if "toc" in rows and toc_pages:
        out.toc = vote_toc(cands, page_lines, toc_pages, out.labels, out.findings)
    chosen = [c for c in cands if c.votes and c.score(rows) >= min_score]
    chosen = _merge_wrapped(chosen, body_lines, body)
    levels = assign_levels(chosen, body)
    stack: list[int] = []
    for i, c in enumerate(chosen):
        level, why = levels[i]
        number = c.number
        printed = number.printed if number is not None else ""
        title = number.rest if number is not None and number.rest else (c.text if number is None else "")
        fams = sorted(c.families(rows))
        node = PNode(c.text, printed, title, level, c.line.page, c.line.start, sorted(c.votes), fams,
                     "likely" if len(fams) >= 2 else "suggested", round(c.score(rows), 2), c.line.size, c.line.bold,
                     c.line.caps, c.line.source, level_from=why)
        while stack and out.nodes[stack[-1]].level >= level:
            stack.pop()
        node.parent = stack[-1] if stack else -1
        stack.append(len(out.nodes))
        out.nodes.append(node)
    out.parts = parts_of(out, chosen, find_parts(lines, pages, toc) if marks is None else marks, toc_pages)
    return out


def parts_of(rec: Recovery, chosen: list[Candidate], marks: Sequence[dict[str, Any]] = (), skip: set[int] = frozenset()) -> list[dict[str, Any]]:
    """The parts of a file bound together: the top-level headings (level 0, a title or a part's name) near the top of a page,
    then the marks of ``find_parts`` (a running header's change, a top bookmark, an exhibit label) on pages they leave bare."""
    out: dict[int, dict[str, Any]] = {}
    for node, c in zip(rec.nodes, chosen):
        if node.level == 0 and c.line.top <= 0.3 * c.line.ph and node.page not in out:
            out[node.page] = {"page": node.page, "title": node.text, "basis": "title heading"}
    for m in marks:
        if m["page"] not in skip:
            out.setdefault(m["page"], m)
    return [out[p] for p in sorted(out)]


def _merge_wrapped(chosen: list[Candidate], body_lines: list[PLine], body: float) -> list[Candidate]:
    """A heading set over two lines: the next line has the same size and weight, sits close, and is itself a candidate (or
    a short unpunctuated line of that style) - one heading."""
    out: list[Candidate] = []
    for c in chosen:
        prev = out[-1] if out else None
        ln = c.line
        if (prev and prev.line.page == ln.page and "numbering" not in c.votes and ln.gap_above >= 0
                and ln.gap_above < 0.45 and abs(prev.line.size - ln.size) <= 0.1 * body and prev.line.bold == ln.bold
                and prev.line.caps == ln.caps and (prev.merged[-1] if prev.merged else prev.line).bottom
                and prev.index + 1 + len(prev.merged) == c.index and not prev.line.text.rstrip().endswith((".", ":"))
                and not (set(c.votes) & {"bookmark", "toc"})):
            prev.merged.append(ln)
            for k, v in c.votes.items():
                prev.votes.setdefault(k, v)
            continue
        out.append(c)
    return out


# --- parts ----------------------------------------------------------------------------------------------------------


def _infos(lines: Sequence[PLine], pages: int) -> list[Any]:
    from jason.community import document_segments as ds

    by_page: dict[int, list[PLine]] = {}
    for ln in lines:
        by_page.setdefault(ln.page, []).append(ln)
    infos = []
    for n in range(1, pages + 1):
        ls = by_page.get(n, [])
        pw = ls[0].pw if ls else 612.0
        ph = ls[0].ph if ls else 792.0
        ds_lines = [ds.Line(l.text, l.top / ph, l.bottom / ph, l.x0 / pw, l.x1 / pw, l.size, bool(l.bold)) for l in ls]
        infos.append(ds.build_page(n, pw, ph, ds_lines))
    return infos


def find_parts(lines: Sequence[PLine], pages: int, toc: Sequence[Sequence[Any]] = ()) -> list[dict[str, Any]]:
    """The parts of a file bound together, where a part's name changes: the running header's runs, the titles at the top of
    a page (a running header is not one: lines marked as furniture are left out of the titles), and the file's top-level
    bookmarks (``document_segments.header_runs``, ``title_marks``, ``bookmark_marks``)."""
    from jason.community import document_segments as ds

    runs = ds.header_runs(_infos(lines, pages), 1, pages)          # the running headers themselves are the evidence here
    body = _infos([l for l in lines if not l.furniture], pages)
    marks = (runs if len(runs) > 1 else []) + ds.title_marks(body, 1, pages) + ds.bookmark_marks(toc, 1, pages)   # one run is the document's own name
    best: dict[int, Any] = {}
    for m in marks:
        if m.page not in best or m.weight > best[m.page].weight:
            best[m.page] = m
    return [{"page": p, "title": best[p].title, "basis": best[p].basis} for p in sorted(best)]


# --- the reader a caller uses ---------------------------------------------------------------------------------------


@dataclass
class PdfOutline(DocumentOutline):
    """A ``DocumentOutline`` read from a PDF, with the tier of each section beside it."""

    tiers: list[str] = field(default_factory=list)            # parallel to ``sections``
    clues: list[list[str]] = field(default_factory=list)
    pages_of: list[int] = field(default_factory=list)
    findings: list[dict[str, str]] = field(default_factory=list)
    parts: list[dict[str, Any]] = field(default_factory=list)


def to_outline(rec: Recovery, *, key: str, title: str = "", kind: str = "") -> PdfOutline:
    shift = 1 if any(n.level == 0 for n in rec.nodes) else 0
    out = PdfOutline(key=key, title=title, kind=kind, text=rec.text, findings=rec.findings, parts=rec.parts)
    for n in rec.nodes:
        number = ""
        if n.number:
            number = normalize_number(re.sub(r"^(?:article|section|rule|part|chapter)\s+", "", n.number, flags=re.I))
        out.sections.append(Section(number=number, title=(n.title or n.text)[:120], depth=n.level + shift, start=n.start,
                                    label=n.number, parent=""))
        out.tiers.append(n.tier)
        out.clues.append(n.clues)
        out.pages_of.append(n.page)
    from jason.community.outlines import _close

    _close(out)
    return out


def outline_from_pdf(path: Path | str, *, key: str = "", title: str = "", kind: str = "",
                     words_of: Callable[[int, Any], tuple[Sequence[Any], int]] | None = None,
                     clues: Iterable[str] | None = None) -> PdfOutline:
    """A PDF's outline from its own clues. ``words_of`` reads a page with no text layer (see ``extract_lines``; with
    ``ocr_words_of`` Tesseract does). It changes no stored outline."""
    import pymupdf

    with pymupdf.open(path) as doc:
        lines, sources = extract_lines(doc, words_of=words_of)
        toc = doc.get_toc(simple=True)
        rec = recover(lines, doc.page_count, toc=toc, clues=clues, sources=sources)
    return to_outline(rec, key=key or Path(path).stem, title=title, kind=kind)


def band_words(page: Any, number: int, dpi: int) -> list[Any]:
    """Words of the page's bottom band read as one block of text (``--psm 6``): a page number alone on a line is dropped by
    Tesseract's page reading, and a block reading finds it. Positions are on the full page, at ``dpi``."""
    import os
    import subprocess
    import tempfile

    import pymupdf

    from jason.community.ocr import PyMuPdfTesseract, TesseractCli, TesseractWord, parse_tsv

    exe = TesseractCli.exe()
    if not exe:
        return []
    top = (BOTTOM_BAND - 0.01) * page.rect.height
    clip = pymupdf.Rect(0, top, page.rect.width, page.rect.height)
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, clip=clip)
    env = dict(os.environ)
    tessdata = PyMuPdfTesseract.tessdata()
    if tessdata:
        env["TESSDATA_PREFIX"] = tessdata
    with tempfile.TemporaryDirectory() as tmp:
        image = Path(tmp) / "band.png"
        pix.save(str(image))
        done = subprocess.run([exe, str(image), "stdout", "-l", "eng", "--dpi", str(dpi), "--psm", "6", "tsv"],
                              capture_output=True, timeout=120, env=env, check=False)
    shift = int(round(top * dpi / 72))
    out = []
    for w in parse_tsv(done.stdout.decode("utf-8", errors="replace"), number):
        out.append(TesseractWord(w.page, 1000 + w.block, w.paragraph, w.line, w.left, w.top + shift, w.width, w.height,
                                 w.confidence, w.text))
    return out


def with_band(words: list[Any], page: Any, number: int, dpi: int) -> list[Any]:
    """Words of a page's reading with the band reading's words that the page reading lacks (by place) added."""
    have = [(w.left, w.top, w.width, w.height) for w in words]
    extra = []
    for w in band_words(page, number, dpi):
        if not any(abs(w.left - x) < w.width and abs(w.top - y) < w.height for x, y, _, _ in have):
            extra.append(w)
    return [*words, *extra]


def ocr_words_of(dpi: int = 300, language: str = "eng") -> Callable[[int, Any], tuple[Sequence[Any], int]]:
    """A ``words_of`` that reads a page with Tesseract's own tool (``ocr.TesseractCli``) at ``dpi``."""
    from jason.community.ocr import TesseractCli

    tool = TesseractCli(dpi=dpi, language=language)

    def words_of(number: int, page: Any) -> tuple[Sequence[Any], int]:
        return with_band(tool.page_words(page, number), page, number, dpi), dpi

    return words_of


__all__ = ["CLUES", "Clue", "MIN_SCORE", "PLine", "PNode", "PdfOutline", "Recovery", "extract_lines", "find_parts",
           "ocr_lines", "ocr_words_of", "outline_from_pdf", "recover", "text_lines", "to_outline"]
