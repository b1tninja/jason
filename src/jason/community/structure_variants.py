"""Degraded copies of a PDF, each recording what was done, so a structure recovery's score can be attributed.

``make_variant`` takes the paired PDF (the Doc's export, or a drawing of the gold) and writes one variant: the clean text
layer, the text layer stripped to images at a resolution, a degradation (skew, noise, uneven shading, one global threshold,
a JBIG2-like stencil), a duplex scan with blank backs, pages out of order, a missing page, a running header changed, or the
document placed inside a larger file of other documents. ``VariantRecord.page_map`` takes a page of the source to its page
in the variant (0 where it was lost), which is what a score needs to find a heading again.

The image operations are ``page_prep``'s (numpy and Pillow); the page turned, speckled, and compressed is the way
``form_scans.simulate`` does it. Nothing here reads a real document except the PDF it is given; the filler documents of
``combined`` are made up.
"""

from __future__ import annotations

import io
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from jason.community import page_prep as prep


@dataclass(frozen=True)
class VariantSpec:
    name: str
    dpi: int = 0                       # 0: the text layer is kept; else each page is an image at this resolution
    ops: tuple[str, ...] = ()
    note: str = ""


VARIANTS: dict[str, VariantSpec] = {v.name: v for v in (
    VariantSpec("clean", 0, (), "the text-layer PDF as it is"),
    VariantSpec("image300", 300, (), "the text layer removed; each page an image at 300 dpi"),
    VariantSpec("dpi200", 200, (), "images at 200 dpi"),
    VariantSpec("dpi150", 150, (), "images at 150 dpi"),
    VariantSpec("dpi110", 110, (), "images at 110 dpi"),
    VariantSpec("skew", 200, ("skew",), "200 dpi, every page turned 1.5 degrees"),
    VariantSpec("noise", 200, ("noise",), "200 dpi, one percent of the pixels flipped"),
    VariantSpec("shade", 200, ("shade",), "200 dpi, uneven shading across the page"),
    VariantSpec("otsu", 200, ("otsu",), "200 dpi, bilevel by one global threshold"),
    VariantSpec("stencil", 150, ("stencil",), "150 dpi bilevel, each character replaced by an earlier one of nearly the same "
                                                "shape (lossy JBIG2's symbol substitution)"),
    VariantSpec("duplex", 200, ("duplex",), "200 dpi with a blank back after every page, and its show-through"),
    VariantSpec("shuffle", 200, ("shuffle",), "200 dpi, neighbouring pages swapped (a scanner that interleaves fronts and backs)"),
    VariantSpec("missing", 200, ("missing",), "200 dpi, one page from the middle left out"),
    VariantSpec("header", 0, ("header",), "the text layer with the running header changed from the middle of the file"),
    VariantSpec("combined", 0, ("combined",), "the document between other made-up documents in one larger file"),
)}


@dataclass
class VariantRecord:
    name: str
    file: str
    dpi: int
    image_only: bool
    ops: list[str]
    page_map: dict[int, int]                # a source page (1-based) -> its page in the variant, 0 when lost
    pages: int = 0
    lost: list[int] = field(default_factory=list)       # source pages left out
    added: list[int] = field(default_factory=list)      # variant pages that are not the source's (blank backs, filler)
    seed: int = 0
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["page_map"] = {str(k): v for k, v in self.page_map.items()}
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> VariantRecord:
        return cls(**{**raw, "page_map": {int(k): v for k, v in raw["page_map"].items()}})


# --- image operations -----------------------------------------------------------------------------------------------


def draw(page: Any, dpi: int) -> np.ndarray:
    import pymupdf

    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, annots=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()


def add_noise(gray: np.ndarray, share: float, rng: random.Random) -> np.ndarray:
    out = gray.copy()
    h, w = out.shape
    n = int(h * w * share)
    ys = np.array([rng.randrange(h) for _ in range(n)])
    xs = np.array([rng.randrange(w) for _ in range(n)])
    out[ys, xs] = np.where(out[ys, xs] > 128, 0, 255)
    return out


def shade(gray: np.ndarray, rng: random.Random) -> np.ndarray:
    """Paper brightness that falls off toward one corner, with a soft blotch: the shading of a page scanned under a lid."""
    h, w = gray.shape
    yy, xx = np.mgrid[0:h, 0:w]
    f = 1.0 - 0.38 * (xx / w) - 0.18 * (yy / h)
    cx, cy = rng.uniform(0.2, 0.8) * w, rng.uniform(0.2, 0.8) * h
    f -= 0.15 * np.exp(-(((xx - cx) / (0.25 * w)) ** 2 + ((yy - cy) / (0.2 * h)) ** 2))
    return np.clip(gray.astype(np.float64) * f, 0, 255).astype(np.uint8)


def stencil(gray: np.ndarray, tolerance: float = 0.22) -> np.ndarray:
    """A bilevel page whose characters are drawn from a dictionary of earlier ones: each connected piece of ink is replaced by
    a first piece of the same box whose pixels differ in fewer than ``tolerance`` of the box, as a lossy JBIG2 coder does."""
    bw = prep.binarize_global(gray)
    mask = bw == 0
    out = np.full(bw.shape, 255, dtype=np.uint8)
    dictionary: dict[tuple[int, int], list[np.ndarray]] = {}
    for c in prep.components(mask):
        bm = mask[c.y0:c.y1 + 1, c.x0:c.x1 + 1]
        pool = dictionary.setdefault((c.width, c.height), [])
        use = next((p for p in pool if (p != bm).mean() < tolerance), None)
        if use is None:
            pool.append(bm)
            use = bm
        out[c.y0:c.y1 + 1, c.x0:c.x1 + 1][use] = 0
    return out


def show_through(gray: np.ndarray, rng: random.Random) -> np.ndarray:
    """The back of a sheet: white paper with the front's ink faintly through it, mirrored, and a little noise."""
    ghost = gray[:, ::-1].astype(np.float64)
    out = 255 - 0.07 * (255 - ghost)
    out += np.array([[rng.gauss(0, 1.2) for _ in range(out.shape[1] // 16 + 1)] for _ in range(out.shape[0] // 16 + 1)]
                    ).repeat(16, 0).repeat(16, 1)[:out.shape[0], :out.shape[1]]
    return np.clip(out, 0, 255).astype(np.uint8)


def _add_image(doc: Any, gray: np.ndarray, size: tuple[float, float], dpi: int) -> None:
    from PIL import Image

    page = doc.new_page(width=size[0], height=size[1])
    buf = io.BytesIO()
    bilevel = bool(np.isin(np.unique(gray), (0, 255)).all())
    image = Image.fromarray(gray)
    if bilevel:
        image.convert("1").save(buf, "PNG", dpi=(dpi, dpi))
    else:
        image.save(buf, "JPEG", quality=88, dpi=(dpi, dpi))
    page.insert_image(page.rect, stream=buf.getvalue())


# --- text variants --------------------------------------------------------------------------------------------------


def change_header(src: Any, *, from_page: int, text: str) -> str:
    """Rewrites the running header (the line in the top band most pages share) from ``from_page`` on, in place, in the
    document ``src``. Returns the header text that was replaced ("" when there is none)."""
    from collections import Counter

    from jason.community.structure_pdf import TOP_BAND, text_lines

    seen: Counter[str] = Counter()
    for i, page in enumerate(src):
        for ln in text_lines(page, i + 1):
            if ln.bottom <= TOP_BAND * ln.ph:
                seen[ln.text] += 1
    if not seen:
        return ""
    old = seen.most_common(1)[0][0]
    for i in range(from_page - 1, src.page_count):
        page = src[i]
        for rect in page.search_for(old):
            if rect.y1 <= TOP_BAND * page.rect.height:
                page.add_redact_annot(rect, fill=(1, 1, 1))
                page.apply_redactions()
                page.insert_text((rect.x0, rect.y1 - 2.5), text, fontsize=9, fontname="tiro")
    return old


def filler(kind: str, seed: int = 1) -> Any:
    """A made-up document of a page or two: a letter, an invoice, a short agreement with numbered clauses."""
    import pymupdf

    rng = random.Random(seed)
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    y = 90.0

    def line(text: str, size: float = 11.0, font: str = "tiro", x: float = 72.0, dy: float = 15.0) -> None:
        nonlocal y
        page.insert_text((x, y), text, fontsize=size, fontname=font)
        y += dy

    words = ["notice", "payment", "service", "account", "gutter", "roof", "inspection", "schedule", "visit", "estimate"]

    def prose(n: int) -> None:
        for _ in range(n):
            line(" ".join(rng.choice(words) for _ in range(11)).capitalize() + ".")

    if kind == "letter":
        line("Dear Sample Owner,", 11)
        y += 8
        prose(8)
        y += 10
        line("Sincerely,")
        line("Sample Management Co.")
    elif kind == "invoice":
        line("INVOICE", 20, "tibo", dy=30)
        line("Invoice number 0000", 11)
        line("Bill to: Sample Association")
        y += 10
        for k in range(1, 6):
            line(f"{rng.choice(words).capitalize()} {rng.choice(words)}      $ {rng.randrange(40, 400)}.00")
        line("Total due   $ 0.00", 11, "tibo")
    else:
        line("SERVICE AGREEMENT", 16, "tibo", dy=28)
        for k, title in enumerate(["Scope", "Term", "Payment", "Notices"], 1):
            line(f"{k}. {title}", 12, "tibo", dy=18)
            prose(3)
            y += 6
    return doc


# --- the variants ---------------------------------------------------------------------------------------------------


def make_variant(source: Path | str, spec: VariantSpec | str, out_dir: Path | str, *, seed: int = 11,
                 sizes: Callable[[int], tuple[float, float]] | None = None) -> VariantRecord:
    """Writes one variant of ``source`` to ``out_dir`` and returns its record."""
    import pymupdf

    spec = VARIANTS[spec] if isinstance(spec, str) else spec
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(f"{spec.name}:{seed}")
    path = out_dir / f"{spec.name}.pdf"
    src = pymupdf.open(str(source))
    n = src.page_count
    record = VariantRecord(spec.name, path.name, spec.dpi, bool(spec.dpi), list(spec.ops), {p: p for p in range(1, n + 1)},
                           seed=seed, note=spec.note)
    if not spec.dpi:
        if "header" in spec.ops:
            old = change_header(src, from_page=max(2, n // 2), text="Revised Edition Rules")
            record.extra = {"header_was": old != "", "from_page": max(2, n // 2)}
            src.save(str(path))
        elif "combined" in spec.ops:
            out = pymupdf.open()
            before = [filler("letter", seed), filler("invoice", seed)]
            after = [filler("agreement", seed)]
            offset = 0
            for d in before:
                out.insert_pdf(d)
                offset += d.page_count
            out.insert_pdf(src)
            tail = out.page_count
            for d in after:
                out.insert_pdf(d)
            record.page_map = {p: p + offset for p in range(1, n + 1)}
            record.added = [*range(1, offset + 1), *range(tail + 1, out.page_count + 1)]
            record.extra = {"host_first": offset + 1, "host_last": offset + n, "fillers": len(before) + len(after)}
            out.save(str(path))
            record.pages = out.page_count
            return record
        else:
            src.save(str(path))
        record.pages = src.page_count
        return record
    # image variants
    images: list[tuple[int, np.ndarray]] = []
    for i, page in enumerate(src):
        gray = draw(page, spec.dpi)
        if "skew" in spec.ops:
            gray = prep.rotate(gray, 1.5, fill=255)
        if "shade" in spec.ops:
            gray = shade(gray, rng)
        if "noise" in spec.ops:
            gray = add_noise(gray, 0.01, rng)
        if "otsu" in spec.ops:
            gray = prep.binarize_global(gray)
        if "stencil" in spec.ops:
            gray = stencil(gray)
        images.append((i + 1, gray))
    order = list(range(n))
    if "shuffle" in spec.ops:
        for k in range(0, n - 1, 2):
            order[k], order[k + 1] = order[k + 1], order[k]
    lost: list[int] = []
    if "missing" in spec.ops and n > 3:
        gone = n // 2
        lost = [gone + 1]
        order = [k for k in order if k != gone]
    out = pymupdf.open()
    page_map = {p: 0 for p in range(1, n + 1)}
    added: list[int] = []
    for k in order:
        number, gray = images[k]
        size = (src[k].rect.width, src[k].rect.height)
        _add_image(out, gray, size, spec.dpi)
        page_map[number] = out.page_count
        if "duplex" in spec.ops:
            _add_image(out, show_through(gray, rng), size, spec.dpi)
            added.append(out.page_count)
    record.page_map = page_map
    record.lost = lost
    record.added = added
    record.pages = out.page_count
    out.save(str(path), deflate=True)
    return record


def make_all(source: Path | str, out_dir: Path | str, names: list[str] | None = None, *, seed: int = 11) -> list[VariantRecord]:
    records = [make_variant(source, VARIANTS[n], out_dir, seed=seed) for n in (names or list(VARIANTS))]
    import json

    (Path(out_dir) / "variants.json").write_text(json.dumps([r.to_dict() for r in records], indent=1), encoding="utf-8")
    return records


__all__ = ["VARIANTS", "VariantRecord", "VariantSpec", "make_all", "make_variant"]
