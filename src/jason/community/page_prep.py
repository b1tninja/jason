"""Image operations on one scanned page, in numpy and Pillow only: what a preflight measures and what a cleaned copy does.

The functions take and return 8-bit grayscale arrays (``uint8``, 255 white, shape rows x columns) unless they say
otherwise. Nothing here reads a PDF or runs an OCR engine; ``jason.community.pdf_preflight`` does, and chooses among
these operations with measurements (docs/pdf-preflight.md). No SciPy or OpenCV: a package the venv lacks is not needed
for any of this, and a connected-component count and a window threshold are short in numpy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# --- levels ---------------------------------------------------------------------------------------------------------


def histogram(gray: np.ndarray) -> np.ndarray:
    return np.bincount(gray.ravel(), minlength=256).astype(np.float64)


def otsu_threshold(gray: np.ndarray) -> int:
    """Otsu's global threshold: the level that best separates two classes of pixels (ink at or below it)."""
    h = histogram(gray)
    total = h.sum()
    if total == 0:
        return 128
    levels = np.arange(256, dtype=np.float64)
    w0 = np.cumsum(h)
    w1 = total - w0
    m0 = np.cumsum(h * levels)
    mt = m0[-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        between = (w0 * w1) * ((m0 / w0 - (mt - m0) / w1) ** 2)
    between = np.nan_to_num(between)
    return int(np.argmax(between))


def paper_level(gray: np.ndarray) -> int:
    """The paper's gray level: the commonest level among the brighter half of the pixels (255 for a clean page)."""
    h = histogram(gray)
    cut = int(np.searchsorted(np.cumsum(h), h.sum() / 2))
    return int(cut + np.argmax(h[cut:]))


def ink_level(gray: np.ndarray, drop: int = 70, block: int = 64) -> np.ndarray:
    """Each pixel's ink cut-off: a pixel at or below it is ink, one more than ``drop`` levels under its surroundings' paper.

    The paper is the bright end (90th percentile) of each ``block`` x ``block`` patch, smoothed, and never taken as less
    than the page's own paper level less 60: a gray page or a gradient is not ink, and a photograph's dark body still is."""
    from PIL import Image

    h, w = gray.shape
    by, bx = max(1, -(-h // block)), max(1, -(-w // block))
    padded = np.pad(gray, ((0, by * block - h), (0, bx * block - w)), mode="edge")
    blocks = padded.reshape(by, block, bx, block).transpose(0, 2, 1, 3).reshape(by, bx, -1)
    local = np.percentile(blocks, 90, axis=2).astype(np.float32)
    big = np.asarray(Image.fromarray(local, mode="F").resize((w, h), Image.Resampling.BILINEAR))
    floor = paper_level(gray) - 60
    return np.maximum(big, floor) - drop


def background(gray: np.ndarray, block: int = 48) -> np.ndarray:
    """The paper's brightness at each pixel, as float: the 90th percentile of each ``block`` x ``block`` patch (ink is
    the minority of a patch, so its bright end is paper), enlarged smoothly to the page."""
    from PIL import Image

    h, w = gray.shape
    by, bx = max(1, -(-h // block)), max(1, -(-w // block))
    padded = np.pad(gray, ((0, by * block - h), (0, bx * block - w)), mode="edge")
    blocks = padded.reshape(by, block, bx, block).transpose(0, 2, 1, 3).reshape(by, bx, -1)
    local = np.percentile(blocks, 90, axis=2).astype(np.float32)
    return np.asarray(Image.fromarray(local, mode="F").resize((w, h), Image.Resampling.BICUBIC))


def unevenness(gray: np.ndarray) -> float:
    """How unevenly the page is lit, in gray levels: the 5th to the 95th percentile of the paper's brightness over the
    page (0 for a bilevel scan; a shading or a shadow raises it)."""
    from PIL import Image

    small = np.asarray(Image.fromarray(gray).resize((max(1, gray.shape[1] // 8), max(1, gray.shape[0] // 8)), Image.Resampling.BOX))
    bg = background(small, 8)
    lo, hi = np.percentile(bg, [5, 95])
    return float(hi - lo)


def flatten(gray: np.ndarray, block: int = 48) -> np.ndarray:
    """The page divided by its own paper brightness, so a shading or a shadow no longer changes the paper's level."""
    bg = np.maximum(background(gray, block), 1.0)
    return np.clip(gray.astype(np.float32) * (255.0 / bg), 0, 255).astype(np.uint8)


def speckle(gray: np.ndarray) -> float:
    """The share of the page's ink pixels (Otsu) with no inked neighbor: near 0 for a clean scan, large for dust and
    salt-and-pepper noise."""
    ink = gray <= otsu_threshold(gray)
    total = int(ink.sum())
    if total == 0:
        return 0.0
    p = np.pad(ink, 1)
    near = np.zeros_like(ink)
    h, w = ink.shape
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            if dy == 1 and dx == 1:
                continue
            near |= p[dy:dy + h, dx:dx + w]
    return float((ink & ~near).sum()) / total


def stretch(gray: np.ndarray, low: float = 1.0, high: float = 99.0) -> np.ndarray:
    """Contrast stretch: the ``low`` percentile goes to black, the ``high`` percentile to white."""
    lo, hi = np.percentile(gray, [low, high])
    if hi - lo < 8:
        return gray
    out = (gray.astype(np.float32) - lo) * (255.0 / (hi - lo))
    return np.clip(out, 0, 255).astype(np.uint8)


def clahe(gray: np.ndarray, tiles: int = 8, clip: float = 3.0) -> np.ndarray:
    """Contrast-limited adaptive histogram equalization: each of ``tiles`` x ``tiles`` regions is equalized with its
    histogram clipped at ``clip`` times the mean bin count, and the pixels take a bilinear blend of the four nearest
    regions' maps, so no seams show."""
    h, w = gray.shape
    th, tw = -(-h // tiles), -(-w // tiles)
    padded = np.pad(gray, ((0, th * tiles - h), (0, tw * tiles - w)), mode="edge")
    blocks = padded.reshape(tiles, th, tiles, tw).transpose(0, 2, 1, 3).reshape(tiles, tiles, -1)
    luts = np.zeros((tiles, tiles, 256), dtype=np.float32)
    for i in range(tiles):
        for j in range(tiles):
            hist = np.bincount(blocks[i, j], minlength=256).astype(np.float64)
            limit = max(1.0, clip * hist.sum() / 256)
            excess = np.maximum(hist - limit, 0).sum()
            hist = np.minimum(hist, limit) + excess / 256
            cdf = np.cumsum(hist)
            luts[i, j] = 255.0 * (cdf - cdf[0]) / max(cdf[-1] - cdf[0], 1.0)
    ys = (np.arange(h) + 0.5) / th - 0.5
    xs = (np.arange(w) + 0.5) / tw - 0.5
    y0 = np.clip(np.floor(ys).astype(int), 0, tiles - 1)
    x0 = np.clip(np.floor(xs).astype(int), 0, tiles - 1)
    y1, x1 = np.clip(y0 + 1, 0, tiles - 1), np.clip(x0 + 1, 0, tiles - 1)
    fy = np.clip(ys - y0, 0, 1).astype(np.float32)[:, None]
    fx = np.clip(xs - x0, 0, 1).astype(np.float32)[None, :]
    v = gray.astype(np.intp)
    top = luts[y0[:, None], x0[None, :], v] * (1 - fx) + luts[y0[:, None], x1[None, :], v] * fx
    bottom = luts[y1[:, None], x0[None, :], v] * (1 - fx) + luts[y1[:, None], x1[None, :], v] * fx
    return np.clip(top * (1 - fy) + bottom * fy, 0, 255).astype(np.uint8)


def binarize_global(gray: np.ndarray, threshold: int | None = None) -> np.ndarray:
    """Black (0) where the page is at or below the threshold (Otsu's by default), white (255) elsewhere."""
    t = otsu_threshold(gray) if threshold is None else threshold
    return np.where(gray <= t, 0, 255).astype(np.uint8)


# --- window thresholds ----------------------------------------------------------------------------------------------


def _window_sums(a: np.ndarray, window: int) -> np.ndarray:
    """The sum of each ``window`` x ``window`` neighborhood of ``a`` (edges reflected), by an integral image."""
    pad = window // 2
    p = np.pad(a, pad, mode="reflect").astype(np.float64)
    s = np.zeros((p.shape[0] + 1, p.shape[1] + 1), dtype=np.float64)
    np.cumsum(np.cumsum(p, axis=0), axis=1, out=s[1:, 1:])
    h, w = a.shape
    k = window
    return s[k:k + h, k:k + w] - s[0:h, k:k + w] - s[k:k + h, 0:w] + s[0:h, 0:w]


def window_stats(gray: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray]:
    """Each pixel's local mean and standard deviation over a ``window`` x ``window`` neighborhood (``window`` odd)."""
    window = window | 1
    n = float(window * window)
    mean = _window_sums(gray, window) / n
    sq = _window_sums(gray.astype(np.float64) ** 2, window) / n
    return mean, np.sqrt(np.maximum(sq - mean ** 2, 0.0))


def sauvola(gray: np.ndarray, window: int = 51, k: float = 0.2, r: float = 128.0) -> np.ndarray:
    """Sauvola's adaptive threshold: ink where a pixel is below mean * (1 + k * (std / r - 1)) of its neighborhood.

    ``window`` is in pixels, about a character's height at the page's resolution (51 at 300 dpi). Black (0) is ink."""
    mean, std = window_stats(gray, window)
    t = mean * (1.0 + k * (std / r - 1.0))
    return np.where(gray <= t, 0, 255).astype(np.uint8)


def niblack(gray: np.ndarray, window: int = 51, k: float = -0.2) -> np.ndarray:
    """Niblack's adaptive threshold: ink where a pixel is below mean + k * std of its neighborhood (k negative)."""
    mean, std = window_stats(gray, window)
    return np.where(gray <= mean + k * std, 0, 255).astype(np.uint8)


# --- noise ----------------------------------------------------------------------------------------------------------


def blur(gray: np.ndarray, sigma: float = 0.8) -> np.ndarray:
    """A Gaussian blur (Pillow's), which softens the jagged edges of a bilevel scan drawn at a higher resolution."""
    from PIL import Image, ImageFilter

    return np.asarray(Image.fromarray(gray).filter(ImageFilter.GaussianBlur(sigma)))


def median(gray: np.ndarray, size: int = 3) -> np.ndarray:
    """A median filter (Pillow's), which removes isolated specks and keeps strokes at least ``size`` wide."""
    from PIL import Image, ImageFilter

    return np.asarray(Image.fromarray(gray).filter(ImageFilter.MedianFilter(size)))


@dataclass(frozen=True)
class Component:
    area: int          # ink pixels
    x0: int
    y0: int
    x1: int            # inclusive
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0 + 1

    @property
    def height(self) -> int:
        return self.y1 - self.y0 + 1


def components(mask: np.ndarray) -> list[Component]:
    """The 8-connected components of a boolean mask (True is ink), by runs and union-find.

    Cost grows with the number of runs, so a page of dense text (thousands of components) takes a few seconds; the
    preflight asks only of a page whose ink share is small."""
    h, w = mask.shape
    padded = np.zeros((h, w + 2), dtype=np.int8)
    padded[:, 1:-1] = mask
    d = np.diff(padded, axis=1)
    rows, starts = np.nonzero(d == 1)
    _, ends = np.nonzero(d == -1)               # exclusive end columns, in the same order
    n = len(starts)
    if n == 0:
        return []
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    # The run index range of each row.
    first = np.searchsorted(rows, np.arange(h + 1))
    for r in range(1, h):
        a0, a1 = first[r - 1], first[r]
        b0, b1 = first[r], first[r + 1]
        if a0 == a1 or b0 == b1:
            continue
        ps, pe = starts[a0:a1], ends[a0:a1]
        for j in range(b0, b1):
            s, e = starts[j], ends[j]
            # previous-row runs that touch [s - 1, e] (8-connectivity)
            lo = np.searchsorted(pe, s, side="left")        # pe > s - 1  <=>  pe >= s
            hi = np.searchsorted(ps, e + 1, side="left")    # ps <= e
            for i in range(lo, hi):
                ra, rb = find(a0 + int(i)), find(j)
                if ra != rb:
                    parent[rb] = ra
    roots = np.fromiter((find(i) for i in range(n)), dtype=np.int64, count=n)
    out = []
    for root in np.unique(roots):
        sel = roots == root
        out.append(Component(int((ends[sel] - starts[sel]).sum()), int(starts[sel].min()), int(rows[sel].min()),
                             int(ends[sel].max()) - 1, int(rows[sel].max())))
    return out


def remove_specks(binary: np.ndarray, *, min_side: int) -> np.ndarray:
    """A bilevel page (0 ink, 255 paper) with each connected piece of ink whose box is smaller than ``min_side`` in both
    directions made paper. Slow on dense pages (see ``components``); use ``median`` for those."""
    mask = binary == 0
    out = binary.copy()
    for c in components(mask):
        if c.width < min_side and c.height < min_side:
            out[c.y0:c.y1 + 1, c.x0:c.x1 + 1][mask[c.y0:c.y1 + 1, c.x0:c.x1 + 1]] = 255
    return out


# --- geometry -------------------------------------------------------------------------------------------------------


def estimate_skew(gray: np.ndarray, dpi: float, *, limit: float = 6.0, working_dpi: float = 100.0) -> tuple[float | None, float]:
    """The tilt of the page's text lines in degrees, positive when a line rises to the right (counter-clockwise), and
    a confidence (the sharpest row-profile's peak over the median profile's; about 1 means no preferred direction).

    The projection-profile method: the page's ink pixels are projected on rows after each trial rotation, and the
    rotation that makes the rows crispest (the largest sum of squared row counts) is the page's own. None when too
    little ink (a blank page) or no angle stands out (a photograph, a table of ruled boxes)."""
    step = max(1, int(round(dpi / working_dpi)))
    small = gray[::step, ::step] if step > 1 else gray
    # Ink is far below the paper; a bilevel page is just 0 and 255.
    cut = max(0, paper_level(small) - 80)
    ys, xs = np.nonzero(small <= cut)
    if len(ys) < 400:
        return None, 0.0
    if len(ys) > 120_000:
        keep = np.linspace(0, len(ys) - 1, 120_000).astype(np.int64)
        ys, xs = ys[keep], xs[keep]
    x = xs.astype(np.float64) - small.shape[1] / 2
    y = ys.astype(np.float64)

    def score(theta: float) -> float:
        yy = y + x * np.tan(np.radians(theta))
        bins = np.floor(yy - yy.min()).astype(np.int64)              # whole-pixel rows (half pixels double a lattice)
        counts = np.bincount(bins).astype(np.float64)
        return float((counts ** 2).sum())

    coarse = np.arange(-limit, limit + 1e-9, 0.5)
    s = np.array([score(t) for t in coarse])
    best = float(coarse[int(np.argmax(s))])
    fine = np.arange(best - 0.5, best + 0.5 + 1e-9, 0.05)
    fs = np.array([score(t) for t in fine])
    angle = float(fine[int(np.argmax(fs))])
    confidence = float(fs.max() / max(np.median(s), 1e-9))
    return (angle if confidence >= 1.1 else None), confidence


def rotate(gray: np.ndarray, angle: float, *, fill: int | None = None) -> np.ndarray:
    """Rotate counter-clockwise by ``angle`` degrees about the center, the same size, the corners filled with the paper's
    level (``fill``), by bicubic resampling."""
    from PIL import Image

    if fill is None:
        fill = paper_level(gray)
    img = Image.fromarray(gray)
    return np.asarray(img.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor=int(fill)))


def deskew(gray: np.ndarray, dpi: float) -> tuple[np.ndarray, float | None]:
    """The page turned to straighten its text lines, and the skew found (None, and the page as it was, when none)."""
    angle, _ = estimate_skew(gray, dpi)
    if angle is None or abs(angle) < 0.15:
        return gray, angle
    return rotate(gray, -angle), angle          # the lines rise by ``angle``: turn the page clockwise by it


SKEW_MIN = 1.0           # degrees: a page tilted this much or more is turned (a scan's own 0.1 to 0.6 is left)
SPECKLE_MIN = 0.02       # share of ink pixels alone: dust or noise this heavy is median filtered
UNEVEN_MIN = 20.0        # gray levels of shading across the page: flattened


@dataclass(frozen=True)
class Defects:
    skew: float | None       # degrees, positive when lines rise to the right; None when not measurable
    speckle: float
    uneven: float


def defects(gray: np.ndarray, dpi: float) -> Defects:
    """What is wrong with the page as drawn, each measured apart (docs/pdf-preflight.md for the thresholds)."""
    return Defects(estimate_skew(gray, dpi)[0], speckle(gray), unevenness(gray))


def steps_for(d: Defects) -> tuple[str, ...]:
    """The cleaning a page's defects call for, in the order it is done."""
    out = []
    if d.uneven >= UNEVEN_MIN:
        out.append("flatten")
    if d.speckle >= SPECKLE_MIN:
        out.append("median")
    if d.skew is not None and abs(d.skew) >= SKEW_MIN:
        out.append("deskew")
    return tuple(out)


def auto_clean(gray: np.ndarray, dpi: float, found: Defects | None = None) -> tuple[np.ndarray, list[str]]:
    """Fix only the defects the page has: shading flattened, dust median filtered, a tilt turned. A clean page comes back
    as it was (the same array), so the cleaning cannot harm it. Returns the page and the steps taken."""
    d = found or defects(gray, dpi)
    steps = steps_for(d)
    for step in steps:
        if step == "flatten":
            gray = flatten(gray)
        elif step == "median":
            gray = median(gray, 3)
        else:
            gray = rotate(gray, -d.skew)
    return gray, list(steps)


def upscale(gray: np.ndarray, factor: float) -> np.ndarray:
    """The page larger by ``factor`` (Lanczos), for a scan read at too low a resolution."""
    from PIL import Image

    h, w = gray.shape
    return np.asarray(Image.fromarray(gray).resize((int(round(w * factor)), int(round(h * factor))), Image.Resampling.LANCZOS))


def downscale(gray: np.ndarray, factor: float) -> np.ndarray:
    from PIL import Image

    h, w = gray.shape
    return np.asarray(Image.fromarray(gray).resize((max(1, int(round(w / factor))), max(1, int(round(h / factor)))), Image.Resampling.BOX))
