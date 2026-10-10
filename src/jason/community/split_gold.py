"""A made-up gold set for the PDF splitter's suggestion pass (docs/pdf-splitter.md, 4.7), and the scores for it.

No real scan is in a tracked file: every archetype is drawn here from nothing, with the pages that truly start a document listed
beside it. ``scripts/split_fuzz.py`` and ``tests/test_split_gold.py`` use these. Pure of the association: the letterhead is "Example
Village HOA" and the street "123 Main St".

Archetypes (``ARCHETYPES``): a stack of one-page letters; documents whose pages say "Page n of N"; documents with blank separator
pages; a duplex scan (a blank back after every page); documents of different sizes with a landscape map; and image-only scans at
different resolutions. The nested case (an agreement holding a report holding an exhibit) and a file in two languages are later rows.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

VOCAB = ("garden fence parking roof paint gutter lawn sprinkler pool gate lighting elevator hallway balcony drainage "
         "insurance premium reserve budget assessment vendor contract invoice inspection permit violation hearing appeal "
         "landscape irrigation trees pavement sealing striping signage mailbox trash recycling pest termite plumbing "
         "electrical heating cooling window door lock camera access fob visitor guest vehicle storage laundry clubhouse "
         "tennis court schedule reservation deposit refund notice meeting agenda minutes motion quorum proxy ballot election "
         "director officer manager auditor counsel survey estimate warranty deadline renewal coverage claim deductible").split()
LETTER = (612, 792)
A4 = (595, 842)
LANDSCAPE = (792, 612)


@dataclass
class Gold:
    """A made-up file and the truth about it: ``starts`` are the pages (1-based) that begin a document, page 1 first."""

    name: str
    pdf: bytes
    starts: list[int]
    pages: int
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def para(seed: int, lines: int = 8, per_line: int = 12) -> list[str]:
    """Lines of text whose words come from a small vocabulary chosen by ``seed``: pages with the same seed share words (one document),
    pages with different seeds share few (two documents)."""
    import random

    rng = random.Random(seed * 7919 + 13)
    pool = rng.sample(VOCAB, 30)
    return [" ".join(rng.choice(pool) for _ in range(per_line)).capitalize() + "." for _ in range(lines)]


def _doc():
    import pymupdf

    return pymupdf.open()


def _text_page(doc: Any, lines: Sequence[tuple[str, float, float, float]], size: tuple[int, int] = LETTER) -> None:
    page = doc.new_page(width=size[0], height=size[1])
    for text, x, y, fs in lines:
        page.insert_text((x, y), text, fontsize=fs)


def _body(page_lines: list[tuple[str, float, float, float]], seed: int, lines: int = 14) -> None:
    y = 150.0
    for text in para(seed, lines):
        page_lines.append((text, 72, y, 10))
        y += 14


def letters(count: int = 8) -> Gold:
    """A stack of one-page letters from different senders, each with a letterhead, a date, and 'Dear ...'."""
    senders = ("Sample Paving Co", "Example Insurance Agency", "Sample Landscape Services", "Example Law Office", "Sample Pest Control",
               "Example Plumbing", "Sample Elevator Inc", "Example Roofing")
    doc = _doc()
    for i in range(count):
        lines = [(senders[i % len(senders)], 72, 60, 16), (f"{100 + i} Main St", 72, 78, 10), (f"March {i + 1}, 2026", 72, 120, 11),
                 ("Dear Member:", 72, 140, 11)]
        y = 170.0
        for text in para(i + 1, 5):
            lines.append((text, 72, y, 10))
            y += 14
        lines.append(("Sincerely, The Manager", 72, y + 20, 10))
        _text_page(doc, lines)
    data = doc.tobytes()
    return Gold("letters", data, list(range(1, count + 1)), count, "one-page letters from different senders, a start on every page")


def numbered(sizes: Sequence[int] = (3, 2, 4, 1, 3)) -> Gold:
    """Documents of several pages each with 'Page n of N' footers and a title opening each."""
    doc = _doc()
    starts, n = [], 0
    kinds = ("Agreement", "Report", "Policy", "Notice", "Resolution")
    for d, total in enumerate(sizes):
        starts.append(n + 1)
        for p in range(1, total + 1):
            lines: list[tuple[str, float, float, float]] = []
            if p == 1:
                lines.append((f"{kinds[d % len(kinds)].upper()} {d + 1}", 200, 90, 18))
            _body(lines, d + 1)
            lines.append((f"Page {p} of {total}", 270, 760, 9))
            _text_page(doc, lines)
            n += 1
    return Gold("numbered", doc.tobytes(), starts, n, "documents with Page n of N footers")


def blank_separated(sizes: Sequence[int] = (2, 3, 2, 3)) -> Gold:
    """Documents with a blank sheet between them (blanks are rare: separators)."""
    doc = _doc()
    starts, n = [], 0
    for d, total in enumerate(sizes):
        if d:
            doc.new_page(width=LETTER[0], height=LETTER[1])
            n += 1
        starts.append(n + 1)
        for p in range(total):
            lines: list[tuple[str, float, float, float]] = []
            _body(lines, d + 1)
            _text_page(doc, lines)
            n += 1
    return Gold("blank-separated", doc.tobytes(), starts, n, "a blank separator between documents")


def duplex(sizes: Sequence[int] = (1, 1, 1, 1, 1, 1)) -> Gold:
    """A duplex scan: a blank back after every sheet. The blanks are backs, not separators."""
    doc = _doc()
    starts, n = [], 0
    kinds = ("Notice", "Report", "Policy", "Agreement", "Resolution", "Statement")
    for d, total in enumerate(sizes):
        starts.append(n + 1)
        for p in range(total):
            lines: list[tuple[str, float, float, float]] = [(kinds[d % len(kinds)].upper(), 220, 90, 18)] if p == 0 else []
            _body(lines, d + 1)
            _text_page(doc, lines)
            doc.new_page(width=LETTER[0], height=LETTER[1])
            n += 2
    return Gold("duplex", doc.tobytes(), starts, n, "a blank back after every sheet; blanks are not separators")


def sized() -> Gold:
    """Documents of different sizes (letter, A4, a landscape map): a change of size starts a document."""
    doc = _doc()
    plan = [(LETTER, 2), (A4, 2), (LANDSCAPE, 2), (LETTER, 2)]
    starts, n = [], 0
    for d, (size, count) in enumerate(plan):
        starts.append(n + 1)
        for _ in range(count):
            lines: list[tuple[str, float, float, float]] = []
            _body(lines, d + 1)
            _text_page(doc, lines, size)
            n += 1
    return Gold("sizes", doc.tobytes(), starts, n, "a change of page size or orientation")


def _scan_image(pixels: tuple[int, int], seed: int, colour: bool = False) -> bytes:
    from PIL import Image, ImageDraw

    mode = "RGB" if colour else "L"
    img = Image.new(mode, pixels, (255, 255, 255) if colour else 255)
    draw = ImageDraw.Draw(img)
    step = max(6, pixels[1] // 60)
    for k, y in enumerate(range(step * 2, pixels[1] - step * 2, step * 2)):
        x1 = pixels[0] - step * 3 - ((k * 37 + seed * 11) % (pixels[0] // 4))
        draw.rectangle([step * 3, y, x1, y + step // 2 + 1], fill=(20, 40, 120) if colour else 0)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def mixed_dpi(plan: Sequence[tuple[int, bool, int]] = ((200, False, 3), (300, True, 3), (200, False, 2))) -> Gold:
    """Image-only scans (no text layer): runs of pages at 200 or 300 dpi, grey or colour. A change of resolution or colour is a weak
    signal; together they make a Low suggestion, which is all a scan without words can offer."""
    doc = _doc()
    starts, n = [], 0
    for dpi, colour, count in plan:
        starts.append(n + 1)
        for k in range(count):
            page = doc.new_page(width=LETTER[0], height=LETTER[1])
            px = (int(8.5 * dpi), int(11 * dpi))
            page.insert_image(page.rect, stream=_scan_image(px, n + k, colour))
            n += 1
    return Gold("mixed-dpi", doc.tobytes(), starts, n, "image-only scans; the resolution changes at each document")


ARCHETYPES: dict[str, Callable[[], Gold]] = {"letters": letters, "numbered": numbered, "blank-separated": blank_separated,
                                            "duplex": duplex, "sizes": sized, "mixed-dpi": mixed_dpi}


def gold_set(names: Sequence[str] = ()) -> list[Gold]:
    return [ARCHETYPES[n]() for n in (names or ARCHETYPES)]


# --- degrading ---------------------------------------------------------------------------------------------------------------

def strip_text(pdf: bytes, dpi: int = 150) -> bytes:
    """The same file as images only (the text layer gone): each page drawn and put back as a picture."""
    import pymupdf

    src = pymupdf.open(stream=pdf, filetype="pdf")
    out = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=pix.tobytes("png"))
    return out.tobytes()


# --- scoring -----------------------------------------------------------------------------------------------------------------

def prf(predicted: Sequence[int], gold: Sequence[int]) -> dict[str, float]:
    """Precision, recall, and F1 of the starts after page 1 (page 1 always starts a document and is not a guess)."""
    p, g = {x for x in predicted if x != 1}, {x for x in gold if x != 1}
    tp = len(p & g)
    prec = tp / len(p) if p else (1.0 if not g else 0.0)
    rec = tp / len(g) if g else 1.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3), "tp": tp, "fp": len(p - g), "fn": len(g - p)}


def taps_saved(predicted: Sequence[int], gold: Sequence[int]) -> dict[str, int]:
    """With the suggestions accepted as shown, the taps still needed (add a missed start, reject a wrong one), against marking every
    start from nothing."""
    score = prf(predicted, gold)
    without = len({x for x in gold if x != 1})
    with_ = score["fp"] + score["fn"]
    return {"withoutSuggestions": without, "withSuggestions": with_, "saved": without - with_}


def calibration(rows: Sequence[tuple[float, bool]], bands: Sequence[tuple[str, float, float]] = (("High", 0.85, 1.01), ("Medium", 0.6, 0.85),
                                                                                              ("Low", 0.0, 0.6))) -> list[dict[str, Any]]:
    """For each band, how many suggestions fell in it and what share were real starts. ``rows`` are (confidence, was a real start)."""
    out = []
    for name, lo, hi in bands:
        pick = [ok for conf, ok in rows if lo <= conf < hi]
        out.append({"band": name, "count": len(pick), "realShare": round(sum(pick) / len(pick), 3) if pick else None})
    return out
