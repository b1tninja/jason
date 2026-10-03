"""Struck-through and bold words in an image-only scan, so an amendment can be read from its recorded copy.

An amendment carries its change in type: struck words are removed, bold words added (``jason.community.living``). A
recorded copy is a scan with no text layer, and OCR keeps neither mark (it garbles struck words and draws every word in
one font). The marks survive in the pixels, so this reads them there:

- **struck**: a rule is a horizontal run of dark pixels across a text line's middle band longer than about one and a
  half line heights (no glyph is that wide). A character whose middle a rule crosses is struck.
- **bold**: stroke width, the median length of the dark runs inside a character's box. A word whose letters' mean
  stroke is well above the page's median is bold.
- **page furniture**: a line in the top or bottom margin whose words recur on another page (a running header, a
  footer with the document's name), the same line just outside the margin at its usual height, and a page number are
  dropped (``drop_furniture``), so none joins an operation's words or a sentence split across a page break.

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
MARGIN = 0.10                    # the top and bottom bands where running headers and footers sit


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
    return re.sub(r"[^a-z0-9]", "", text.lower())


# A page number: arabic (OCR may space its digits, "- 1 6 -") or roman. A footer's page number differs on every page,
# and its letters are too few for the likeness test, so it is known by its shape.
_NUMBER = r"(?:\d(?:\s?\d){0,3}|[ivxlc]{1,6})"
# Set off by dashes or tildes ("- 17 -", "-ii-", "~25 -"), or written out ("Page 3", "Page 3 of 10", "3 of 10").
_DECORATED_NUMBER = re.compile(rf"\s*(?:[-–—~]\s*{_NUMBER}\s*[-–—~]?|{_NUMBER}\s*[-–—~]|page\s*{_NUMBER}(?:\s+of\s+\d{{1,4}})?"
                               rf"|\d{{1,4}}\s+of\s+\d{{1,4}})\s*", re.I)
# A number alone: a page number only in the bottom margin, since a top line may be a section's label ("12", "iv").
_BARE_NUMBER = re.compile(rf"\s*{_NUMBER}\s*", re.I)
NEAR = 0.05                      # how far outside the margin band a running header or footer may still sit
SAME_HEIGHT = 0.02               # ... when it is at the height (a share of the page) where it sits on other pages


def page_number(line: ScanLine) -> bool:
    """Whether a margin line is a page number: "- 17 -", "-ii-", "Page 3 of 10", or a number alone at the foot."""
    text = line.text.strip()
    if _DECORATED_NUMBER.fullmatch(text):
        return True
    return line.bottom > 1 - MARGIN and bool(_BARE_NUMBER.fullmatch(text))


def drop_furniture(lines: list[ScanLine], *, alike: float = 0.7) -> list[ScanLine]:
    """Leave out the page furniture, so it never joins the words of a section split across a page break:

    - a line in the top or bottom margin whose letters recur, nearly alike, on another page (running headers and
      footers). OCR reads the same footer a little differently on each page, so the test is a likeness, not equality;
    - a line just outside the margin band (``NEAR``) that is alike to such a footer on another page and sits at its
      height there (``SAME_HEIGHT``): a page scanned a little askew puts its footer just above the band;
    - a page number in the margin (``page_number``), which differs on every page and is too short for a likeness."""
    from difflib import SequenceMatcher

    def strict(line: ScanLine) -> bool:
        return line.top < MARGIN or line.bottom > 1 - MARGIN

    def near(line: ScanLine) -> bool:
        return not strict(line) and (line.top < MARGIN + NEAR or line.bottom > 1 - MARGIN - NEAR)

    margin = [line for line in lines if strict(line)]
    numbers = [line for line in margin if page_number(line)]
    drop = {id(line) for line in numbers}
    # OCR garbles some page numbers ("iad 1 -", "~1V-"): a short margin line with a digit or a dash, at the height where
    # page numbers sit on two other pages, is one too.
    for a in margin:
        if id(a) not in drop and 0 < len(_key(a.text)) <= 5 and re.search(r"[\d\-–—~]", a.text) and len(
                {b.page for b in numbers if b.page != a.page and abs(b.top - a.top) <= SAME_HEIGHT}) >= 2:
            drop.add(id(a))
    for i, a in enumerate(margin):
        ka = _key(a.text)
        if len(ka) < 4:
            continue
        for b in margin[i + 1:]:
            if b.page != a.page and SequenceMatcher(None, ka, _key(b.text)).ratio() >= alike:
                drop.update((id(a), id(b)))
    footers = [line for line in margin if id(line) in drop and len(_key(line.text)) >= 4]
    for a in (line for line in lines if near(line)):
        ka = _key(a.text)
        if len(ka) >= 4 and any(b.page != a.page and abs(b.top - a.top) <= SAME_HEIGHT
                                and SequenceMatcher(None, ka, _key(b.text)).ratio() >= alike for b in footers):
            drop.add(id(a))
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


def page_text_lines(page: Any, page_number: int, *, dpi: int = DPI) -> list[ScanLine]:
    """OCR one page into lines with their place on the page, without measuring marks (for a whole document's text)."""
    from jason.community.ocr import PyMuPdfTesseract

    textpage = page.get_textpage_ocr(dpi=dpi, language="eng", full=True, tessdata=PyMuPdfTesseract.tessdata())
    raw = page.get_text("dict", textpage=textpage)
    height = float(page.rect.height) or 1.0
    out = []
    for block in raw["blocks"]:
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line["spans"])
            if text.strip():
                out.append(ScanLine(page_number, int(block["number"]), line["bbox"][1] / height,
                                    line["bbox"][3] / height, tuple(ScanChar(c, False, 0.0) for c in text)))
    return out


def tesseract_text_lines(pdf: Path, *, dpi: int = DPI) -> list[ScanLine]:
    """A scanned PDF's lines as Tesseract's own tool reads them (``ocr.TesseractCli``): its word spacing, which
    PyMuPDF's page OCR loses ("ofthe"). A Tesseract paragraph is a block."""
    import pymupdf

    from jason.community.ocr import TesseractCli

    cli = TesseractCli(dpi=dpi)
    out = []
    with pymupdf.open(str(pdf)) as doc:
        for n in range(doc.page_count):
            page = doc[n]
            height = float(page.rect.height) * dpi / 72 or 1.0
            lines: dict[tuple[int, int, int], list] = {}
            for w in cli.page_words(page, n):
                lines.setdefault((w.block, w.paragraph, w.line), []).append(w)
            for (block, paragraph, _), words in lines.items():
                text = " ".join(w.text for w in words)
                out.append(ScanLine(n, block * 1000 + paragraph, min(w.top for w in words) / height,
                                    max(w.top + w.height for w in words) / height,
                                    tuple(ScanChar(c, False, 0.0) for c in text)))
    return out


def scan_lines(pdf: Path, *, dpi: int = DPI, engine: str = "auto") -> list[ScanLine]:
    """A scanned document's lines by OCR, each with its page, block, and height on the page, its furniture still in:
    what ``lines_text`` makes a text of. ``engine``: "tesseract-cli" (the tool's own words; the default when the tool
    is installed), "pymupdf" (PyMuPDF's page OCR, which runs narrow-spaced words together), or "auto"."""
    import pymupdf

    from jason.community.ocr import TesseractCli

    if engine == "tesseract-cli" or (engine == "auto" and TesseractCli.available()):
        return tesseract_text_lines(pdf, dpi=dpi)
    with pymupdf.open(str(pdf)) as doc:
        return [line for n in range(doc.page_count) for line in page_text_lines(doc[n], n, dpi=dpi)]


def lines_text(lines: list[ScanLine]) -> str:
    """OCR lines as text, without the page furniture (``drop_furniture``): each OCR block a paragraph, so a section
    number starts its own line as an outline expects."""
    out: list[str] = []
    last = None
    for line in drop_furniture(lines):
        if (line.page, line.block) != last and out:
            out.append("\n")
        elif out:
            out.append(" ")
        out.append(line.text.strip())
        last = (line.page, line.block)
    return "".join(out)


def scan_text(pdf: Path, *, dpi: int = DPI, engine: str = "auto") -> str:
    """A scanned document's text by OCR, page by page, without its page furniture (``scan_lines``, ``lines_text``)."""
    return lines_text(scan_lines(pdf, dpi=dpi, engine=engine))


def lines_to_rows(lines: list[ScanLine]) -> list[dict[str, Any]]:
    """OCR text lines as JSON rows (their words and place; a text line has no marks), to keep beside a reading."""
    return [{"page": line.page, "block": line.block, "top": round(line.top, 5), "bottom": round(line.bottom, 5),
             "text": line.text} for line in lines]


def lines_from_rows(rows: list[dict[str, Any]]) -> list[ScanLine]:
    return [ScanLine(int(r["page"]), int(r["block"]), float(r["top"]), float(r["bottom"]),
                     tuple(ScanChar(c, False, 0.0) for c in str(r["text"]))) for r in rows]


def same_words(text: str, lines: list[ScanLine]) -> str:
    """Why ``lines`` are not the OCR that made ``text`` (empty when they are): their text (``lines_text``) must be
    ``text``'s words less words of lines the furniture pass now drops. A reading made by an older furniture pass keeps
    some furniture; any other difference is a different OCR, whose words a person's transcriptions were not keyed to."""
    from collections import Counter
    from difflib import SequenceMatcher

    kept = {id(line) for line in drop_furniture(lines)}
    spare = Counter(w for line in lines if id(line) not in kept for w in line.text.split())
    old, new = text.split(), lines_text(lines).split()
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        where = " ".join(old[max(0, i1 - 4): i2 + 4])
        if tag != "delete":
            return f'the words differ near "{where}": "{" ".join(old[i1:i2])}" -> "{" ".join(new[j1:j2])}"'
        for w in old[i1:i2]:
            if spare[w] <= 0:
                return f'"{w}" near "{where}" is not on a line the furniture pass drops'
            spare[w] -= 1
    return ""


def operations_from_scan(pdf: Path, *, pages: tuple[int, ...] = ()):
    from dataclasses import replace

    from jason.community.living import read_operations

    return tuple(replace(op, struck_by_ocr=True) for op in read_operations(scan_paragraphs(pdf, pages=pages), styled=True))


__all__ = ["ScanChar", "ScanLine", "drop_furniture", "lines_from_rows", "lines_text", "lines_to_rows",
           "operations_from_scan", "page_lines", "page_number", "page_text_lines", "same_words", "scan_lines",
           "scan_paragraphs", "scan_text", "tesseract_text_lines", "styled_paragraphs"]
