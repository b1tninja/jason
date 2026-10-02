"""Struck-through and bold words in an image-only scan, so an amendment can be read from its recorded copy.

An amendment carries its change in type: struck words are removed, bold words added (``jason.community.living``). A
recorded copy is a scan with no text layer, and OCR keeps neither mark (it garbles struck words and draws every word in
one font). The marks survive in the pixels, so this reads them there:

- **struck**: a rule is a horizontal run of dark pixels across a text line's middle band longer than about one and a
  half line heights (no glyph is that wide). A character whose middle a rule crosses is struck.
- **bold**: stroke width, the median length of the dark runs inside a character's box. A word whose letters' mean
  stroke is well above the page's median is bold.
- **page furniture**: a line in the top or bottom margin whose words recur on another page (a running header, a
  footer with the document's name) is dropped, so it never joins an operation's words.

The result is ``StyledRun`` paragraphs for ``living.read_operations``. OCR still misreads some letters; a slip in the
operative words is a ``Correction`` row, and a second reading (the draft Doc) compares the words.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jason.community.living import StyledRun

DPI = 300
RULE_LINE_HEIGHTS = 1.5          # a rule is longer than this many line heights
BOLD_RATIO = 1.3                 # a word is bold when its mean stroke is this much over the page's median
MARGIN = 0.07                    # the top and bottom bands where running headers and footers sit


@dataclass(frozen=True)
class ScanChar:
    c: str
    struck: bool
    stroke: float


@dataclass(frozen=True)
class ScanLine:
    page: int
    block: int
    top: float                   # the line's top and bottom as shares of the page height
    bottom: float
    chars: tuple[ScanChar, ...]

    @property
    def text(self) -> str:
        return "".join(c.c for c in self.chars)


def _runs(row: Any) -> list[tuple[int, int]]:
    """(start, end) of each run of True in a boolean row."""
    import numpy as np

    padded = np.concatenate(([False], row, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return list(zip(edges[::2], edges[1::2]))


def page_lines(page: Any, page_number: int, *, dpi: int = DPI) -> list[ScanLine]:
    """OCR one page (Tesseract through PyMuPDF) and measure each character's marks in its pixels."""
    import numpy as np
    import pymupdf

    from jason.community.ocr import PyMuPdfTesseract

    scale = dpi / 72
    textpage = page.get_textpage_ocr(dpi=dpi, language="eng", full=True, tessdata=PyMuPdfTesseract.tessdata())
    raw = page.get_text("rawdict", textpage=textpage)
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    dark = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width) < 120
    height = float(page.rect.height) or 1.0
    out = []
    for block in raw["blocks"]:
        for line in block.get("lines", []):
            chars = [c for s in line["spans"] for c in s["chars"]]
            if not chars:
                continue
            x0, y0, x1, y1 = (int(round(v * scale)) for v in line["bbox"])
            h = max(1, y1 - y0)
            rules = [(x0 + a, x0 + b) for y in range(y0 + int(h * 0.3), y0 + int(h * 0.8))
                     for a, b in _runs(dark[y, x0:x1]) if b - a > RULE_LINE_HEIGHTS * h]
            measured = []
            for c in chars:
                cx0, cy0, cx1, cy1 = (int(round(v * scale)) for v in c["bbox"])
                mid = (cx0 + cx1) / 2
                box = dark[cy0 + int((cy1 - cy0) * 0.35): cy1 - int((cy1 - cy0) * 0.2), cx0:cx1]
                widths = [b - a for row in box for a, b in _runs(row)]
                stroke = float(np.median(widths)) if widths and c["c"].strip() else 0.0
                measured.append(ScanChar(c["c"], any(a <= mid <= b for a, b in rules), stroke))
            out.append(ScanLine(page_number, int(block["number"]), line["bbox"][1] / height, line["bbox"][3] / height,
                                tuple(measured)))
    return out


def _key(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def drop_furniture(lines: list[ScanLine], *, alike: float = 0.8) -> list[ScanLine]:
    """Leave out lines in the top or bottom margin whose letters recur, nearly alike, on another page: running headers
    and footers. OCR reads the same footer a little differently on each page, so the test is a likeness, not equality."""
    from difflib import SequenceMatcher

    margin = [line for line in lines if line.top < MARGIN or line.bottom > 1 - MARGIN]
    drop = set()
    for i, a in enumerate(margin):
        ka = _key(a.text)
        if len(ka) < 6:
            continue
        for b in margin[i + 1:]:
            if b.page != a.page and SequenceMatcher(None, ka, _key(b.text)).ratio() >= alike:
                drop.update((id(a), id(b)))
    return [line for line in lines if id(line) not in drop]


def styled_paragraphs(lines: list[ScanLine]) -> list[list[StyledRun]]:
    """The lines as ``StyledRun`` paragraphs (an OCR block is a paragraph), bold judged word by word."""
    from statistics import mean, median

    strokes = [c.stroke for line in lines for c in line.chars if c.stroke and not c.struck]
    plain = median(strokes) if strokes else 0.0
    paragraphs: list[list[StyledRun]] = []
    last: tuple[int, int] | None = None
    for line in lines:
        if (line.page, line.block) != last:
            paragraphs.append([])
            last = (line.page, line.block)
        word: list[ScanChar] = []
        for c in [*line.chars, ScanChar(" ", False, 0.0)]:
            if c.c.strip():
                word.append(c)
                continue
            if word:
                letters = [w.stroke for w in word if w.c.isalnum()]
                bold = bool(letters) and plain > 0 and mean(letters) > plain * BOLD_RATIO
                paragraphs[-1] += [StyledRun(w.c, struck=w.struck, bold=bold and not w.struck) for w in word]
            paragraphs[-1].append(StyledRun(" "))
            word = []
    return paragraphs


def scan_paragraphs(pdf: Path, *, pages: tuple[int, ...] = (), dpi: int = DPI) -> list[list[StyledRun]]:
    """A scanned PDF's paragraphs with their marks. ``pages`` (0-based) narrows the pages read; all by default."""
    import pymupdf

    doc = pymupdf.open(str(pdf))
    wanted = pages or tuple(range(doc.page_count))
    lines = [line for n in wanted for line in page_lines(doc[n], n, dpi=dpi)]
    return styled_paragraphs(drop_furniture(lines))


def operations_from_scan(pdf: Path, *, pages: tuple[int, ...] = ()):
    from dataclasses import replace

    from jason.community.living import read_operations

    return tuple(replace(op, struck_by_ocr=True) for op in read_operations(scan_paragraphs(pdf, pages=pages), styled=True))


__all__ = ["ScanChar", "ScanLine", "drop_furniture", "operations_from_scan", "page_lines", "scan_paragraphs",
           "styled_paragraphs"]
