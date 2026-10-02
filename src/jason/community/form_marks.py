"""The bar mark: a form's marker (``form_refs``) drawn a second time, as a row of short bars at the page's top left.

The printed marker at the top right is read by OCR, and OCR loses it below about 150 dpi. The bar mark carries the same
symbols in a form that needs no OCR, only where the ink is: each bar is one of four states, after the postal 4-state
codes (USPS's Intelligent Mail barcode; Australia Post's), a short **tracker** in the middle, an **ascender** that
also reaches up, a **descender** that also reaches down, or a **full** bar that does both. It is jason's own code and no
postal one: nothing on a page inside the envelope is for the sorting machines, and phones have no reader for it, so
nobody is invited to scan it.

- **Symbols.** Each of the marker's characters (23 values) is three bars (4 × 4 × 4 = 64 patterns), most significant
  first; the marker's own two check characters ride along, so a misread bar fails the check, and one misread character
  is put right by ``form_refs.correct``.
- **Frame.** A full bar and an ascender open the mark, a descender and a full bar close it. The two full bars at the
  ends give the middle line however the page is turned; the mark is read both ways round and kept the way its check
  holds (a page fed upside down reads too).
- **Size.** Bars 1.8 points wide every 4 points; the tracker 3.6 points tall, the full bar three times that. A copy's
  mark (12 characters) is 40 bars, 160 points; a campaign's (7) is 25, 100 points.

Like the printed marker it is a hint: the form is known by its printed lines and every answer is read from the page.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from jason.community.form_refs import ALPHABET, Marker, check, correct

WIDTH, PITCH, TRACKER = 1.8, 4.0, 3.6        # points
ORIGIN = (36.0, 16.0)                         # the mark's top-left corner on the page, points
REGION = (0.0, 0.0, 300.0, 60.0)              # where a reader looks for it: the page's top left, points


class Bar(IntEnum):
    TRACKER = 0
    ASCENDER = 1
    DESCENDER = 2
    FULL = 3


START = (Bar.FULL, Bar.ASCENDER)
STOP = (Bar.DESCENDER, Bar.FULL)


def bars(marker: Marker) -> list[Bar]:
    symbols = (marker.campaign + marker.copy + check(marker.campaign + marker.copy))
    out = list(START)
    for ch in symbols:
        v = ALPHABET.index(ch)
        out += [Bar(v // 16), Bar(v // 4 % 4), Bar(v % 4)]
    return out + list(STOP)


def size(marker: Marker) -> tuple[float, float]:
    return len(bars(marker)) * PITCH, 3 * TRACKER


def draw(page: Any, marker: Marker, *, at: tuple[float, float] = ORIGIN, gray: float = 0.0) -> None:
    """Draw ``marker``'s bars on a PyMuPDF page with their top-left corner at ``at`` (points); ``gray`` 0 is black."""
    import pymupdf

    x0, top = at
    shape = page.new_shape()
    for i, bar in enumerate(bars(marker)):
        x = x0 + i * PITCH
        y0 = top if bar & Bar.ASCENDER else top + TRACKER
        y1 = top + 3 * TRACKER if bar & Bar.DESCENDER else top + 2 * TRACKER
        shape.draw_rect(pymupdf.Rect(x, y0, x + WIDTH, y1))
    shape.finish(color=None, fill=(gray, gray, gray), width=0)
    shape.commit()


def _symbols(states: list[Bar]) -> str | None:
    if len(states) < 7 or tuple(states[:2]) != START or tuple(states[-2:]) != STOP or (len(states) - 4) % 3:
        return None
    inner = states[2:-2]
    out = ""
    for i in range(0, len(inner), 3):
        v = inner[i] * 16 + inner[i + 1] * 4 + inner[i + 2]
        if v >= len(ALPHABET):
            return None
        out += ALPHABET[v]
    return out


def decode(states: list[Bar]) -> tuple[Marker, bool] | None:
    """The marker the bar states spell, read as they are and turned round, and whether a misread character was put
    right on the way (a hint to confirm). None when neither way gives a marker."""
    from jason.community.form_refs import _as_marker

    flip = {Bar.ASCENDER: Bar.DESCENDER, Bar.DESCENDER: Bar.ASCENDER}
    turned = [flip.get(b, b) for b in reversed(states)]
    fixed: tuple[Marker, bool] | None = None
    for way in (states, turned):
        symbols = _symbols(way)
        if symbols is None:
            continue
        if (marker := _as_marker(symbols)) is not None:
            return marker, False
        if fixed is None and (put_right := correct(symbols)) and (marker := _as_marker(put_right)) is not None:
            fixed = (marker, True)
    return fixed


def _runs(columns: Any, least: int) -> list[tuple[int, int]]:
    """Runs of consecutive columns with at least ``least`` dark pixels: the bars."""
    out, start = [], None
    for x, n in enumerate(list(columns) + [0]):
        if n >= least and start is None:
            start = x
        elif n < least and start is not None:
            out.append((start, x))
            start = None
    return out


def read_states(dark: Any, dpi: float) -> list[list[Bar]]:
    """The rows of bars in a dark-pixel mask (True is ink), each row as bar states. Bars are found as runs of dark
    columns of a bar's width; a row is a run of bars at the bar pitch. The middle line comes from the two full bars at
    its ends, so a turned page reads too."""
    import numpy as np

    k = dpi / 72
    columns = dark.sum(axis=0)
    found = [(a, b) for a, b in _runs(columns, max(2, int(TRACKER * k * 0.5)))
             if 0.4 * WIDTH * k <= b - a <= 2.2 * WIDTH * k]
    groups: list[list[tuple[int, int]]] = []
    for run in found:
        if groups and abs((run[0] + run[1]) / 2 - (groups[-1][-1][0] + groups[-1][-1][1]) / 2 - PITCH * k) <= 0.35 * PITCH * k:
            groups[-1].append(run)
        else:
            groups.append([run])
    rows = []
    for group in groups:
        if len(group) < 7:
            continue
        extents = []
        for a, b in group:
            ys = np.nonzero(dark[:, a:b].any(axis=1))[0]
            # the bar's own rows: the longest stretch of ink in its columns, so a speck above or below is not the bar
            best, start = (0, 0), ys[0]
            for prev, cur in zip(ys, list(ys[1:]) + [ys[-1] + 10**6]):
                if cur - prev > 2:
                    if prev - start > best[1] - best[0]:
                        best = (start, prev)
                    start = cur
            extents.append(((a + b) / 2, best[0], best[1]))
        (xa, ta, ba), (xb, tb, bb) = extents[0], extents[-1]
        half = ((ba - ta) + (bb - tb)) / 4                           # half a full bar
        if half <= 0:
            continue
        slope = ((ta + ba) / 2 - (tb + bb) / 2) / (xa - xb) if xb != xa else 0.0
        states = []
        for x, top, bottom in extents:
            middle = (ta + ba) / 2 + slope * (x - xa)
            up = (middle - top) > half * 2 / 3                       # past the tracker's top (a third of the full bar)
            down = (bottom - middle) > half * 2 / 3
            states.append(Bar(int(up) * Bar.ASCENDER + int(down) * Bar.DESCENDER))
        rows.append(states)
    return rows


def read(gray: Any, dpi: float, *, region: tuple[float, float, float, float] | None = REGION) -> list[tuple[Marker, bool]]:
    """The bar marks in a page image (a grayscale array at ``dpi``), searched in ``region`` (points; None for the whole
    page) and at the page's other end too (fed upside down), each with whether it needed a character put right."""
    import numpy as np
    from PIL import Image, ImageFilter

    k = dpi / 72
    h, w = gray.shape
    places = [gray]
    if region is not None:
        x0, y0, x1, y1 = (int(v * k) for v in region)
        places = [gray[y0:y1, x0:x1], gray[h - y1:h - y0, w - x1:w - x0]]
    out: list[tuple[Marker, bool]] = []
    for part in places:
        if not part.size:
            continue
        clean = np.asarray(Image.fromarray(np.ascontiguousarray(part)).filter(ImageFilter.MedianFilter(3)))
        # plain ink first, then lighter cuts for a faint copy, then the region's own split; the check keeps any wrong one
        for cut in dict.fromkeys((128, 160, 190, _otsu(clean))):
            for states in read_states(clean < cut, dpi):
                found = decode(states)
                if found and all(found[0] != m for m, _ in out):
                    out.append(found)
    return out


def _otsu(image: Any) -> int:
    """The gray level that best splits ``image`` into ink and paper (Otsu's method), so a light mark or a dark scan
    reads too."""
    import numpy as np

    hist = np.bincount(image.ravel(), minlength=256).astype(float)
    levels = np.arange(256)
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    s0 = np.cumsum(hist * levels)
    m0 = np.divide(s0, w0, out=np.zeros(256), where=w0 > 0)
    m1 = np.divide(s0[-1] - s0, w1, out=np.zeros(256), where=w1 > 0)
    return int(np.argmax(w0 * w1 * (m0 - m1) ** 2)) + 1


__all__ = ["Bar", "ORIGIN", "REGION", "bars", "decode", "draw", "read", "read_states", "size"]
