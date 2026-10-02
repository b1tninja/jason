"""A scanned or photographed paper form read with the help of its definition and layout.

A person prints the form, writes on it, and scans it or takes a photo; the page comes back shifted, scaled, a little
rotated, and noisy. The reader:

1. **aligns** each scanned page to its printed layout (``form_layout``): OCR reads the lines the page prints, each is
   matched to the same line of the blank form by its words, and an affine transform is fitted to their corners (least
   squares, the worst matches dropped and the fit made again), carrying every point of the blank form onto the scan;
2. **drops the form out**: the blank form is drawn onto the scan through that transform and taken away, leaving only
   what the person added (marks and writing), as forms readers have long done;
3. **reads the boxes**: a check box or radio button is marked when what was added inside it covers enough of it; in a
   radio group the most-marked box wins, and none when no box is marked;
4. **reads the writing**: each text field's area of what was added is read by OCR (typed or neat print), and, with a
   model, the page goes to the local vision model with the form's questions as the answer's schema (handwriting);
5. **finds the marker** (``form_refs``) a copy prints at its top right ("Ref NP27E-4RK9T-C7") and carries again as a
   bar mark at its top left (``form_marks``), naming the campaign or the copy; a hint, which nothing above depends on.

Each answer carries how it was read and a confidence. A reading is evidence for a person to confirm, never an answer
recorded on its own.
"""

from __future__ import annotations

import base64
import difflib
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jason.community.form_layout import FieldBox, FormLayout
from jason.community.forms import FormAnswers, FormTemplate, QuestionKind, option_key

DPI = 200
GROW = 7                 # pixels (odd) round the person's ink taken back from the scan before OCR: the drop-out takes a
                         # letter's foot with the writing line it sits on (form fuzzing, October 1, 2026)
MAX_RESIDUAL = 4.0       # points: an alignment whose mean error is larger (a third of a line) reads nothing; phone scans
                         # fitted 11 to 23 points off read the next question's title as an answer (form fuzzing)
MARKED = 0.07           # what was added inside a box, as a share of it, above which it reads as marked; measured on
                         # test scans aligned to under a point: marked 0.08 to 0.17, empty 0.00 to 0.05


@dataclass
class FieldReading:
    value: Any
    how: str                  # "mark", "ocr", "model"
    confidence: float         # 0 to 1


@dataclass
class ScanReading:
    source: str
    fields: dict[str, FieldReading] = field(default_factory=dict)
    reference: str = ""
    reference_how: str = ""   # "text", "bars", "text and bars", either "… (put right)", or "disagree"
    anchors: int = 0          # printed lines matched on the scan, for the alignment
    residual: float = 0.0     # the alignment's mean error, in points
    notes: list[str] = field(default_factory=list)

    def answers(self, form: FormTemplate) -> FormAnswers:
        """The reading as the form's answers: a text field's words, a check box group's chosen options, a radio
        group's option, by question."""
        out: dict[str, Any] = {}
        for q in form.questions:
            key = q.field
            if q.kind is QuestionKind.CHECKBOX:
                chosen = [o for o in q.options if (r := self.fields.get(f"{key}.{option_key(o)}")) and r.value]
                if chosen:
                    out[key] = chosen
            elif (r := self.fields.get(key)) and r.value:
                out[key] = [q.option_for(r.value)] if q.kind is QuestionKind.CHOICE else r.value
            elif q.same_as and (r := self.fields.get(q.same_as_field)) and r.value:
                out[key] = q.same_as              # the box for the usual answer, and nothing written
        return FormAnswers(form.key, out, source=self.source)


# -- images ---------------------------------------------------------------------------------------------------------------

def scan_pages(path: Path, *, dpi: int = DPI) -> list[Any]:
    """Each page of a scan (a PDF, or one image a page) as a PyMuPDF page."""
    import pymupdf

    path = Path(path)
    if path.suffix.lower() == ".pdf":
        doc = pymupdf.open(path)
    else:
        with pymupdf.open(path) as image:
            doc = pymupdf.open("pdf", image.convert_to_pdf())
    return [doc[i] for i in range(doc.page_count)]


def gray_of(page: Any, *, dpi: int = DPI, despeckle: bool = True) -> Any:
    """The page as a grey numpy image at ``dpi``, the scanner's speckle taken out (a 3-pixel median)."""
    import numpy as np
    import pymupdf
    from PIL import Image, ImageFilter

    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
    if despeckle:
        image = image.filter(ImageFilter.MedianFilter(3))
    return np.asarray(image)


def ocr_image(gray: Any, *, dpi: int = DPI) -> list[tuple[float, float, float, float, str, int, int]]:
    """Tesseract's words in a grey image, each with its box in points from the image's top left, its block, and its
    line."""
    import pymupdf
    from PIL import Image

    from jason.community.ocr import PyMuPdfTesseract

    buffer = io.BytesIO()
    Image.fromarray(gray).save(buffer, "PNG", dpi=(dpi, dpi))
    with pymupdf.open("png", buffer.getvalue()) as image:
        doc = pymupdf.open("pdf", image.convert_to_pdf())
    page = doc[0]
    textpage = page.get_textpage_ocr(dpi=dpi, language="eng", full=True, tessdata=PyMuPdfTesseract.tessdata())
    k = (gray.shape[1] * 72 / dpi) / page.rect.width if page.rect.width else 1.0     # the image page's units to points
    out = [(x0 * k, y0 * k, x1 * k, y1 * k, word, block, line)
           for x0, y0, x1, y1, word, block, line, _ in page.get_text("words", textpage=textpage)]
    doc.close()
    return out


def ocr_lines(gray: Any, *, dpi: int = DPI) -> list[tuple[str, tuple[float, float, float, float]]]:
    """The image's text lines with their boxes (points)."""
    return _lines(ocr_image(gray, dpi=dpi))


def _lines(words: list[tuple[float, float, float, float, str, int, int]]) -> list[tuple[str, tuple[float, float, float, float]]]:
    lines: dict[tuple[int, int], list[Any]] = {}
    for x0, y0, x1, y1, word, block, line in words:
        lines.setdefault((block, line), []).append((x0, y0, x1, y1, word))
    out = []
    for words in lines.values():
        words.sort(key=lambda w: w[0])
        out.append((" ".join(w[4] for w in words),
                    (min(w[0] for w in words), min(w[1] for w in words), max(w[2] for w in words), max(w[3] for w in words))))
    return out


# -- alignment ------------------------------------------------------------------------------------------------------------

def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def match_anchors(anchors: list[Any], lines: list[tuple[str, tuple[float, ...]]], *,
                  least: float = 0.8) -> list[tuple[Any, tuple[float, ...]]]:
    """Each printed line of the blank form with the scanned line that reads the same (``least`` alike or more), each
    scanned line used once."""
    scanned = [(_norm(t), box) for t, box in lines if len(_norm(t)) >= 6]
    pairs, used = [], set()
    for a in anchors:
        want = _norm(a.text)
        best, score = None, 0.0
        for n, (got, box) in enumerate(scanned):
            if n in used:
                continue
            s = difflib.SequenceMatcher(None, want, got, autojunk=False).ratio()
            if s > score:
                best, score = n, s
        if best is not None and score >= least:
            used.add(best)
            pairs.append((a, scanned[best][1]))
    return pairs


@dataclass
class Transform:
    """An affine map from the blank form's points to the scan's: ``coef`` is 3 by 2 (x, y, 1 times it)."""

    coef: Any
    residual: float

    def __call__(self, x: float, y: float) -> tuple[float, float]:
        import numpy as np

        return tuple(np.array([x, y, 1.0]) @ self.coef)


def fit_transform(pairs: list[tuple[Any, tuple[float, ...]]], *, rounds: int = 3, keep: float = 4.0) -> Transform | None:
    """The affine fitted to the matched lines' corners by least squares, refitted without the corners more than
    ``keep`` points off (a line OCR read short or long); None with fewer than three lines. On a page with few lines one
    bad line (a signature line whose underscores OCR does not read) can pull the whole fit off; then the fit is made
    again without each line in turn, and the best kept."""
    best = _fit_lines(pairs, rounds=rounds, keep=keep) if len(pairs) >= 3 else None
    if best is not None and best.residual > keep and 3 <= len(pairs) <= 8:
        for i in range(len(pairs)):
            other = _fit_lines(pairs[:i] + pairs[i + 1:], rounds=rounds, keep=keep)
            if other is not None and other.residual < best.residual:
                best = other
    return best


def fit_words(printed: list[Any], scanned: list[tuple[float, float, float, float, str, int, int]], *,
              least: int = 5) -> Transform | None:
    """The affine from the words both the blank page and the scan print once (five letters or more, compared without
    case or punctuation), centre to centre: a fit that needs no whole line read right. None with fewer than ``least``."""
    from collections import Counter

    def key(text: str) -> str:
        return re.sub(r"[^a-z0-9]", "", text.casefold())

    ours = Counter(key(w.text) for w in printed)
    theirs = Counter(key(w[4]) for w in scanned)
    at = {key(w[4]): w for w in scanned if theirs[key(w[4])] == 1}
    src, dst = [], []
    for w in printed:
        k = key(w.text)
        if len(k) >= 5 and ours[k] == 1 and k in at:
            x0, y0, x1, y1 = w.rect
            s = at[k]
            src.append(((x0 + x1) / 2, (y0 + y1) / 2))
            dst.append(((s[0] + s[2]) / 2, (s[1] + s[3]) / 2))
    return fit_points(src, dst) if len(src) >= least else None


def _fit_lines(pairs: list[tuple[Any, tuple[float, ...]]], *, rounds: int, keep: float) -> Transform | None:
    import numpy as np

    if len(pairs) < 2:
        return None
    src, dst = [], []
    for a, box in pairs:
        ax0, ay0, ax1, ay1 = a.rect
        bx0, by0, bx1, by1 = box
        src += [(ax0, ay0), (ax0, ay1), (ax1, ay0), (ax1, ay1)]
        dst += [(bx0, by0), (bx0, by1), (bx1, by0), (bx1, by1)]
    src_a, dst_a = np.array(src, dtype=float), np.array(dst, dtype=float)
    mask = np.ones(len(src_a), dtype=bool)
    coef = None
    for _ in range(rounds):
        design = np.hstack([src_a[mask], np.ones((mask.sum(), 1))])
        coef, *_ = np.linalg.lstsq(design, dst_a[mask], rcond=None)
        error = np.linalg.norm(np.hstack([src_a, np.ones((len(src_a), 1))]) @ coef - dst_a, axis=1)
        new = error <= max(keep, float(np.median(error)) * 3)
        if new.sum() < 6 or (new == mask).all():
            mask = new if new.sum() >= 6 else mask
            break
        mask = new
    error = np.linalg.norm(np.hstack([src_a[mask], np.ones((mask.sum(), 1))]) @ coef - dst_a[mask], axis=1)
    return Transform(coef, float(error.mean()))


def fit_points(src: Any, dst: Any, *, rounds: int = 3, keep: float = 2.5) -> Transform | None:
    """An affine fitted to point pairs (least squares), refitted without the pairs more than ``keep`` points off."""
    import numpy as np

    src_a, dst_a = np.asarray(src, dtype=float), np.asarray(dst, dtype=float)
    if len(src_a) < 3:
        return None
    full = np.hstack([src_a, np.ones((len(src_a), 1))])
    mask = np.ones(len(src_a), dtype=bool)
    coef = None
    for _ in range(rounds):
        coef, *_ = np.linalg.lstsq(full[mask], dst_a[mask], rcond=None)
        error = np.linalg.norm(full @ coef - dst_a, axis=1)
        new = error <= max(keep, float(np.median(error)) * 3)
        if new.sum() < 3 or (new == mask).all():
            break
        mask = new
    error = np.linalg.norm(full[mask] @ coef - dst_a[mask], axis=1)
    return Transform(coef, float(error.mean()))


def refine(rough: Transform, words: list[Any], scanned: list[tuple[float, float, float, float, str, int, int]], *,
           near: float = 12.0) -> Transform:
    """The precise fit: each printed word of the blank form matched to the same word on the scan within ``near`` points
    of where the rough fit puts it (one match each), and an affine fitted to their centres. The words lie all over the
    page, so the fit holds at its edges too; the rough fit stands when too few words match."""
    found: dict[str, list[tuple[float, float]]] = {}
    for x0, y0, x1, y1, word, *_ in scanned:
        found.setdefault(_norm(word), []).append(((x0 + x1) / 2, (y0 + y1) / 2))
    src, dst, used = [], [], set()
    for w in words:
        key = _norm(w.text)
        cx, cy = (w.rect[0] + w.rect[2]) / 2, (w.rect[1] + w.rect[3]) / 2
        px, py = rough(cx, cy)
        best, distance = None, near
        for point in found.get(key, []):
            d = ((point[0] - px) ** 2 + (point[1] - py) ** 2) ** 0.5
            if d < distance and point not in used:
                best, distance = point, d
        if best is not None:
            used.add(best)
            src.append((cx, cy))
            dst.append(best)
    fine = fit_points(src, dst) if len(src) >= 12 else None
    return fine if fine is not None and fine.residual <= rough.residual else rough


def place(box: FieldBox, to_scan: Transform) -> tuple[float, float, float, float]:
    xs, ys = zip(*(to_scan(x, y) for x in (box.rect[0], box.rect[2]) for y in (box.rect[1], box.rect[3])))
    return min(xs), min(ys), max(xs), max(ys)


# -- dropping the form out ------------------------------------------------------------------------------------------------

def added(scan: Any, blank: Any, to_scan: Transform, *, dpi: int = DPI, spread: int = 5) -> Any:
    """What the person added: the scan's ink where the blank form, drawn onto the scan and widened by ``spread``
    pixels (to allow for the alignment's error and the scanner's blur), has none. A boolean image of the scan's size."""
    import numpy as np
    from PIL import Image, ImageFilter

    k = dpi / 72
    c = to_scan.coef                         # scan = [x y 1] @ c, in points; invert it, in pixels
    forward = np.array([[c[0, 0], c[1, 0], c[2, 0] * k], [c[0, 1], c[1, 1], c[2, 1] * k], [0, 0, 1]])
    inverse = np.linalg.inv(forward)
    image = Image.fromarray(blank).transform((scan.shape[1], scan.shape[0]), Image.AFFINE,
                                             data=tuple(inverse[:2].ravel()), resample=Image.BILINEAR, fillcolor=255)
    printed = np.asarray(image.filter(ImageFilter.MinFilter(spread))) < 160
    return (scan < 128) & ~printed


def mark_level(extra: Any, rect: tuple[float, float, float, float], *, dpi: int = DPI, reach: float = 1.5,
               step: float = 0.5, inset: float = 0.3) -> float:
    """The share of a box's middle the person's marks cover, at its best within ``reach`` points of where the
    alignment put it (the drop-out took the box's outline away, so looking about finds the mark, not the box). The middle
    is the box less ``inset`` of its size on each side: an X, a check, or a filled dot crosses it, while what is left of
    an outline drawn a little differently (a filled PDF redraws its empty radio buttons) does not."""
    w, h = rect[2] - rect[0], rect[3] - rect[1]
    k = dpi / 72
    # the box and the reach round it, without what is left of its outline: straight bars a few pixels thick running
    # most of the box's width or height (a pen's X, check, or dot crosses the box; an outline's leftovers do not)
    ox, oy = int(round((rect[0] - reach) * k)), int(round((rect[1] - reach) * k))
    area = _without_bars(extra[max(oy, 0):max(int(round((rect[3] + reach) * k)), 0),
                               max(ox, 0):max(int(round((rect[2] + reach) * k)), 0)], int(0.35 * w * k), int(0.35 * h * k))
    ox, oy = max(ox, 0), max(oy, 0)
    rect = (rect[0] + w * inset, rect[1] + h * inset, rect[2] - w * inset, rect[3] - h * inset)
    best = 0.0
    n = int(reach / step)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            a, b, c, d = (int(round(v * k)) for v in (rect[0] + i * step, rect[1] + j * step, rect[2] + i * step,
                                                       rect[3] + j * step))
            region = area[max(b - oy, 0):max(d - oy, 0), max(a - ox, 0):max(c - ox, 0)]
            if region.size:
                best = max(best, float(region.mean()))
    return best


def _without_bars(region: Any, long_x: int, long_y: int, *, thick: int = 3) -> Any:
    """``region`` (a boolean image) without straight bars: a run of at least ``long_x`` pixels along a row, in a band of
    at most ``thick`` such rows (and the same down the columns). A filled dot is many such rows thick and stays."""
    import numpy as np

    out = region.copy()
    for img, long_ in ((out, long_x), (out.T, long_y)):
        if long_ < 2 or img.size == 0:
            continue
        rows = []
        for r in range(img.shape[0]):
            line = np.concatenate([[False], img[r], [False]]).astype(np.int8)
            edges = np.flatnonzero(np.diff(line))
            runs = [(s, e) for s, e in zip(edges[::2], edges[1::2]) if e - s >= long_]
            rows.append(runs)
        r = 0
        while r < len(rows):
            if not rows[r]:
                r += 1
                continue
            band = r
            while band < len(rows) and rows[band]:
                band += 1
            if band - r <= thick:
                for q in range(r, band):
                    for s, e in rows[q]:
                        img[q, s:e] = False
            r = band
    return out


def specks_out(region: Any, *, tallest: int = 4, longest: int = 14, smallest: int = 6) -> Any:
    """``region`` (a boolean image) without its slivers and dust: each connected piece no taller than ``tallest`` pixels
    and at least ``longest`` long (what is left of a printed rule; a hyphen is shorter), or smaller than ``smallest``
    pixels (the scanner's dust; a comma or period is larger)."""
    import numpy as np

    keep = region.copy()
    seen = np.zeros_like(region, dtype=bool)
    h, w = region.shape
    for y0, x0 in zip(*np.nonzero(region)):
        if seen[y0, x0]:
            continue
        stack, piece = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            piece.append((y, x))
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and region[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        ys, xs = [y for y, _ in piece], [x for _, x in piece]
        flat = max(ys) - min(ys) + 1 <= tallest and max(xs) - min(xs) + 1 >= longest
        if flat or len(piece) < smallest:
            for y, x in piece:
                keep[y, x] = False
    return keep


def read_area(extra: Any, rect: tuple[float, float, float, float], *, dpi: int = DPI, above: float = 6.0,
              below: float = 3.0, printed: list[tuple[float, float, float, float]] = (), gray: Any = None,
              pitch: float = 0.0) -> str:
    """The words the person wrote in a field's area, read by OCR on what they added there alone. ``printed`` are the
    form's own words placed on the scan (points): what the drop-out left of them (a label's fringe in a soft scan) is
    taken out first, so a question's title is never read as its answer."""
    import numpy as np

    k = dpi / 72
    a, b, c, d = (max(int(round(v * k)), 0) for v in (rect[0] - 6, rect[1] - above, rect[2] + 6, rect[3] + below))
    region = extra[b:d, a:c].copy()
    for x0, y0, x1, y1 in printed:
        pa, pb, pc, pd = (int(round(v * k)) for v in (x0 - 2.5, y0 - 2.5, x1 + 2.5, y1 + 2.5))
        if pc > a and pa < c and pd > b and pb < d:
            region[max(pb - b, 0):max(pd - b, 0), max(pa - a, 0):max(pc - a, 0)] = False
    if region.size == 0 or region.mean() < 0.002 or min(region.shape) < 4:
        return ""
    rows = region.mean(axis=1) > 0.25                  # a piece of the printed writing line the drop-out left: a row
    for _ in range(2):                                 # with ink across a quarter of the field, and two rows either side
        rows = rows | np.roll(rows, 1) | np.roll(rows, -1)
    region[rows, :] = False
    region = specks_out(region)
    image = np.full((region.shape[0] + 40, region.shape[1] + 40), 255, dtype=np.uint8)   # a margin helps Tesseract
    if gray is not None:
        # the scan's own grey where the person's ink is (and a pixel round it): a soft scan keeps its letters' edges,
        # which a black-and-white mask loses
        from PIL import Image, ImageFilter

        near = np.asarray(Image.fromarray(region.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(GROW))) > 0
        image[20:20 + region.shape[0], 20:20 + region.shape[1]] = np.where(near, gray[b:d, a:c], 255)
    else:
        image[20:20 + region.shape[0], 20:20 + region.shape[1]][region] = 0
    words = ocr_image(image, dpi=dpi)
    words.sort(key=lambda w: (w[5], w[6], w[0]))
    top = 20 / k + above + 1.0                     # a point inside the field's top and bottom (points, in the image): a
    bottom = 20 / k + above + (rect[3] - rect[1]) + 1.0   # word centred outside, or a sliver under 4.5 points tall, is
    kept = [w for w in words                       # what the drop-out left of a question's title, not the answer
            if any(ch.isalnum() or ch in "@.-" for ch in w[4]) and top <= (w[1] + w[3]) / 2 <= bottom
            and w[3] - w[1] >= 4.5]
    if not pitch:
        return " ".join(w[4] for w in kept if any(ch.isalnum() for ch in w[4])).strip()
    # one character a box: letters in neighbouring boxes are one word; a box left empty, or a new row, is a space
    kept.sort(key=lambda w: (round((w[1] + w[3]) / 2 / (pitch * 0.9)), w[0]))
    out, last, row = "", None, None
    for w in kept:
        here = round((w[1] + w[3]) / 2 / (pitch * 0.9))
        if last is not None:
            out += " " if here != row or w[0] - last >= pitch * 1.2 else ""
        out, last, row = out + w[4], w[2], here
    return out.strip()


def read_cells(extra: Any, gray: Any, cells: list[tuple[float, float, float, float]], *, dpi: int = DPI) -> str:
    """An answer written one character a box, read the way the boxes ask: each box's ink cut out and set side by side
    as an ordinary word (an empty box between letters a space, the empty boxes after the answer nothing), and the
    line read by OCR. The boxes tell the reader where each letter is, which OCR cannot tell on its own (NIST found
    separately spaced boxes read best when the reader cut along them)."""
    import numpy as np

    k = dpi / 72
    glyphs: list[Any] = []
    height = 0
    for x0, y0, x1, y1 in cells:
        a, b, c, d = (max(int(round(v * k)), 0) for v in (x0 + 1, y0 - 2, x1 - 1, y1 + 2))
        ink = specks_out(extra[b:d, a:c].copy()) if d > b and c > a else None
        if ink is None or ink.sum() < 6:
            glyphs.append(None)
            continue
        rows, cols = np.nonzero(ink)
        r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
        piece = np.where(ink[r0:r1, c0:c1], gray[b + r0:b + r1, a + c0:a + c1], 255).astype(np.uint8)
        glyphs.append((piece, r0, r1))
        height = max(height, d - b)
    while glyphs and glyphs[-1] is None:
        glyphs.pop()
    if not any(glyphs):
        return ""
    gap, space = max(2, int(height * 0.08)), max(6, int(height * 0.45))
    width = sum((g[0].shape[1] + gap) if g else space for g in glyphs) + 40
    line = np.full((height + 40, width), 255, dtype=np.uint8)
    x = 20
    for g in glyphs:
        if g is None:
            x += space
            continue
        piece, r0, _ = g
        line[20 + r0:20 + r0 + piece.shape[0], x:x + piece.shape[1]] = np.minimum(
            line[20 + r0:20 + r0 + piece.shape[0], x:x + piece.shape[1]], piece)
        x += piece.shape[1] + gap
    words = ocr_image(line, dpi=dpi)
    words.sort(key=lambda w: w[0])
    return " ".join(w[4] for w in words if any(ch.isalnum() or ch in "@.-" for ch in w[4])).strip()


# -- the page and the scan -------------------------------------------------------------------------------------------------

def read_page(page: Any, blank_page: Any, layout: FormLayout, page_index: int, *, dpi: int = DPI,
              ocr_text: bool = True) -> tuple[dict[str, FieldReading], int, float, str]:
    """One scanned page read against the layout's page and the blank form's page: the fields, the lines matched, the
    alignment's mean error (points), and the page's OCR text (for the reference)."""
    fields, anchors = layout.on_page(page_index)
    scan = gray_of(page, dpi=dpi)
    printed_words = layout.words_on(page_index)
    tried = []
    for turned in (False, True):                 # a page fed upside down is read turned round
        if turned:
            scan = scan[::-1, ::-1].copy()
        words = ocr_image(scan, dpi=dpi)
        lines = _lines(words)
        pairs = match_anchors(anchors, lines)
        to_scan = fit_transform(pairs)
        text = "\n".join(t for t, _ in lines)
        tried.append((scan, words, text))
        if to_scan is not None:
            to_scan = refine(to_scan, printed_words, words)
            if to_scan.residual <= MAX_RESIDUAL:
                break
    if to_scan is None or to_scan.residual > MAX_RESIDUAL:
        # a page with few printed lines (a signature page) may not align by its lines: by its words instead
        for scan, words, text in tried:
            by_words = fit_words(printed_words, words)
            if by_words is not None:
                to_scan = refine(by_words, printed_words, words)
                if to_scan.residual <= MAX_RESIDUAL:
                    break
    if to_scan is None:
        return {}, len(pairs), 0.0, text
    if to_scan.residual > MAX_RESIDUAL:          # the fit puts the fields in the wrong places: read nothing from them
        return {}, len(pairs), to_scan.residual, text
    extra = added(scan, gray_of(blank_page, dpi=dpi, despeckle=False), to_scan, dpi=dpi)
    printed = [place(FieldBox("", "text", page_index, tuple(w[:4])), to_scan) for w in blank_page.get_text("words")
               if any(ch.isalnum() for ch in w[4])]                 # the writing lines are underscores: not words
    out: dict[str, FieldReading] = {}
    radios: dict[str, list[tuple[float, str]]] = {}
    for box in fields:
        rect = place(box, to_scan)
        if box.kind == "checkbox":
            level = mark_level(extra, rect, dpi=dpi)
            out[box.name] = FieldReading(level >= MARKED, "mark", min(1.0, abs(level - MARKED) / MARKED))
        elif box.kind == "radio":
            radios.setdefault(box.name, []).append((mark_level(extra, rect, dpi=dpi), box.option))
        elif ocr_text:
            if layout.cells.get(box.name):               # one character a box: read along the boxes
                value = read_cells(extra, scan, [place(FieldBox(box.name, "text", page_index, c), to_scan)
                                                 for c in layout.cells[box.name]], dpi=dpi)
            else:
                value = read_area(extra, rect, dpi=dpi, printed=printed, gray=scan,
                                  pitch=layout.pitches.get(box.name, 0.0))
            out[box.name] = FieldReading(value, "ocr", 0.6 if value else 0.3)
    for name, levels in radios.items():
        levels.sort(reverse=True)
        best, option = levels[0]
        second = levels[1][0] if len(levels) > 1 else 0.0
        marked = best >= MARKED and best - second >= 0.04          # and clearly more than the next box
        out[name] = FieldReading(option if marked else "", "mark", min(1.0, (best - second) / MARKED) if marked else 0.5)
    return out, len(pairs), to_scan.residual, text


def identify_form(page: Any, layouts: list[FormLayout], *, dpi: int = DPI, least: int = 4) -> tuple[FormLayout | None, int, int]:
    """Which form, and which of its pages, a scanned page is: the layout page whose printed lines the scan matches most
    (at least ``least``). Read from the form's own text, never from a marker, so a page with no marker, or a marker
    smudged past reading, is still recognised. Returns the layout, its page index, and the lines matched."""
    lines = ocr_lines(gray_of(page, dpi=dpi), dpi=dpi)
    best: tuple[FormLayout | None, int, int] = (None, -1, 0)
    for layout in layouts:
        for index in range(len(layout.pages)):
            found = len(match_anchors(layout.on_page(index)[1], lines))
            if found > best[2]:
                best = (layout, index, found)
    return best if best[2] >= least else (None, -1, best[2])


def find_marker(page: Any, text: str, *, dpi: int = DPI) -> tuple[str, str]:
    """The page's marker and how it was read: the printed marker in the page's OCR ``text`` and the bar mark
    (``form_marks``), each kept only when its check holds. Two readings that agree confirm each other; a reading with one
    character put right (``form_refs.correct``) is used only when nothing reads whole, and says so. ("", "") when the
    page carries none that reads; ("", "disagree") when the two name different markers."""
    from jason.community import form_marks
    from jason.community.form_refs import parse, repaired

    printed = parse(text)
    barred = form_marks.read(gray_of(page, dpi=dpi), dpi)
    whole = [m for m, fixed in barred if not fixed]
    if printed and whole:
        return (printed[0].text, "text and bars") if printed[0] in whole else ("", "disagree")
    if printed:
        return printed[0].text, "text"
    if whole:
        return whole[0].text, "bars"
    fixed = repaired(text)
    if fixed:
        return fixed[0].text, "text (put right)"
    if barred:
        return barred[0][0].text, "bars (put right)"
    return "", ""


def read_scan(path: Path, form: FormTemplate, layout: FormLayout, *, dpi: int = DPI, model: Any = None) -> ScanReading:
    """A scanned return read against its form: each page aligned to the layout's page in order, the blank form dropped
    out, its boxes and writing read; with ``model`` (``VisionReader``) its text fields by the local vision model too
    (the model's words are kept where OCR read none or was unsure)."""
    import pymupdf

    reading = ScanReading(str(path))
    pages = scan_pages(Path(path), dpi=dpi)
    errors = []
    with pymupdf.open(layout.source) as blank:
        for index, page in enumerate(pages[:len(layout.pages)]):
            number = layout.page_numbers[index] if index < len(layout.page_numbers) else index
            fields, found, residual, text = read_page(page, blank[number], layout, index, dpi=dpi)
            reading.anchors += found
            if not fields:
                reading.notes.append(f"page {index + 1}: could not align ({found} printed lines matched)")
            else:
                errors.append(residual)
            reading.fields.update(fields)
            if not reading.reference:                                     # a hint: nothing above depends on it
                reading.reference, reading.reference_how = find_marker(page, text, dpi=dpi)
                if reading.reference_how == "disagree":
                    reading.notes.append(f"page {index + 1}: the printed marker and the bar mark name different copies")
                    reading.reference = ""
            if model is not None:
                names = [f.name for f in layout.on_page(index)[0] if f.kind == "text"]
                for name, value in model.read(page, form, names, dpi=dpi).items():
                    ocr = reading.fields.get(name)
                    if value and (ocr is None or not ocr.value or ocr.confidence < 0.7):
                        reading.fields[name] = FieldReading(value, "model", 0.75)
    reading.residual = sum(errors) / len(errors) if errors else 0.0
    _join_lines(reading)
    return reading


def _join_lines(reading: ScanReading) -> None:
    """An answer written on several lines is read a line a field ("mailing-address", "mailing-address#2"): joined
    back into the question's field, a line each, before the hints and the answers read it."""
    from jason.community.pdf_fields import LINE, join_lines

    by_base: dict[str, list[FieldReading]] = {}
    for name in [n for n in reading.fields if LINE in n]:
        by_base.setdefault(name.partition(LINE)[0], []).append(reading.fields[name])
    if not by_base:
        return
    joined = join_lines({n: (r.value or "") for n, r in reading.fields.items() if n.partition(LINE)[0] in by_base})
    for base, extras in by_base.items():
        first = reading.fields.get(base)
        read = [r for r in [first, *extras] if r is not None and r.value]
        for name in [n for n in reading.fields if n.startswith(base + LINE)]:
            del reading.fields[name]
        if read:
            reading.fields[base] = FieldReading(joined.get(base, ""), read[0].how, min(r.confidence for r in read))


# -- the local vision model, for handwriting ----------------------------------------------------------------------------

class VisionReader:
    """The page and the form's questions to the local vision model; its answer is held to a JSON schema of the text
    fields asked for. Uses the scan reader's settings (qwen3.6:27b, thinking off, temperature 0).

    The prompt is plain on purpose: it never carries what a copy was sent with, nor format rules. Told the pre-filled
    answers, glm-ocr reported the old value for 13 of 24 answers the owner had changed; the rules changed nothing
    (``jason form-lab --prompts``, docs/form-design.md). The comparison with what was sent is ``form_hints`` and
    ``owner_prefill.compare``, after the reading, where every repair is marked."""

    def __init__(self, model: str = "", *, base_url: str = "", timeout: int = 600) -> None:
        from jason.community.ollama_extractor import DEFAULT_MODEL, OLLAMA_URL

        self.model, self.base_url, self.timeout = model or DEFAULT_MODEL, base_url or OLLAMA_URL, timeout

    def read(self, page: Any, form: FormTemplate, names: list[str], *, dpi: int = DPI) -> dict[str, str]:
        from jason.community.ollama_extractor import _post

        if not names:
            return {}
        questions = {q.field: q for q in form.questions}
        listing = "\n".join(f"- {n}: {questions[n].title if n in questions else n}" for n in names)
        prompt = ("This is a scanned page of a paper form someone filled in by hand. For each field below, write exactly "
                  "what the person wrote on its lines (an empty string when nothing is written). Do not copy the "
                  "printed questions or help text; transcribe only the handwriting or typing.\n" + listing)
        schema = {"type": "object", "properties": {n: {"type": "string"} for n in names}, "required": names}
        image = base64.b64encode(page.get_pixmap(dpi=min(dpi, 150)).tobytes("png")).decode("ascii")
        answer = _post(f"{self.base_url}/api/chat", {
            "model": self.model, "stream": False, "think": False, "format": schema,
            "options": {"temperature": 0}, "messages": [{"role": "user", "content": prompt, "images": [image]}],
        }, self.timeout)
        try:
            return {k: str(v).strip() for k, v in json.loads((answer.get("message") or {}).get("content") or "{}").items()}
        except (ValueError, AttributeError):
            return {}


__all__ = ["FieldReading", "MARKED", "ScanReading", "Transform", "VisionReader", "added", "fit_points", "identify_form",
           "fit_transform", "refine", "specks_out",
           "gray_of", "mark_level", "match_anchors", "ocr_image", "ocr_lines", "read_area", "read_page", "read_scan",
           "scan_pages"]
