"""A preflight for scanned PDFs, before OCR and ingestion: what each page and file is, and a cleaned copy to read.

A box of scans arrives as PDFs whose pages are images, with a text layer a scanner program added, sometimes good and
sometimes not. Before spending OCR on them (and before trusting their text) the preflight looks at each page and says
what it finds:

- **Blank pages.** Ink after a light threshold, the connected pieces of it, and the text layer. A page with no ink worth
  a mark is ``BLANK``. A page with a little (a signature, a stamp, a page number, a note that it is left blank) is
  ``MARKED``: it is kept and says why, never dropped. Only a page that is both inkless and textless is blank.
- **Page facts.** Rotation (Tesseract's orientation detection), skew, the image's real resolution, color mode, and codec.
  A JBIG2 image with a shared symbol table is flagged: that format can substitute one character for a look-alike.
- **The text layer's quality.** The share of its words the English prior doubts (``jason.community.lexicon``), the
  signal that tracks the OCR's error rate (docs/ocr-correction.md), and so whether to read the page again.
- **A cleaned rendition.** The page drawn to an image with its annotations, form fields, and optional-content layers
  left off, and the scanner's text layer dropped (an image carries none), by a variant measured to help
  (docs/pdf-preflight.md). It is kept in a store beside the library, never in place of the original: the original is
  never rewritten, and a reading is evidence.

The functions read a ``pymupdf`` document. Image operations are ``jason.community.page_prep`` (numpy and Pillow).
Nothing here names an association, a vendor, or a document.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np

from jason.community import page_prep as prep
from jason.community.pdf_media import Carried, MediaKind, carried as carried_of

ANALYSIS_DPI = 150          # pages are measured at this resolution (a 300 dpi bilevel page averages down to gray)
OCR_DPI = 300               # a rendition for OCR is drawn at this resolution (docs/ocr-correction.md)
MIN_SPECK_IN = 0.035        # a piece of ink with both sides under this many inches is a speck, not a mark
EDGE_IN = 0.2               # ink within this band along the page's edge is the scanner's shadow, never a mark
HOLE_IN = (0.15, 0.8)       # a punch hole's size (inches), seen as a ring, a half ring, or a disk beside an edge
ARC_IN = 0.05               # ... a half ring is at least this tall
HOLE_MARGIN_IN = 0.9        # ... within this distance of the left or right edge
CHAR_LONG_IN = 0.06         # a piece with a side this long and a side at least CHAR_SHORT_IN may be a character
CHAR_SHORT_IN = 0.03        # (a digit at 8 point is 0.08 inch tall and 0.05 wide) unless it is
CHAR_FILL = 0.2             # a hair or a scratch, which fills less of its box than this, or is longer than
CHAR_ASPECT = 6.0           # this many times its width (a character is at most 5: a lowercase l), or is
BLOB_IN = 0.1               # a small solid blob (dust): at most this long, square, and filling more than half its box
BAND = 0.12                 # a page number or a running head lies within this share of the page's height of an edge
DENSE_INK = 0.02            # above this share of ink the page is content and its pieces are not counted
BLANK_INK = 1e-3            # a page with less core ink than this share, no character-like piece, and no text is blank
NEAR_INK = 0.006            # a page with less core ink than this share is near-blank: a mark, not content
TEXTLESS_ALNUM = 2          # a text layer with fewer letters and digits than this (or one, with no character-like
                            # piece to match) is empty: a scanner program's reading of dust
SHORT_TEXT = 60             # a page whose text layer holds fewer letters and digits than this is a short text, kept and marked
SHARE_LIMIT = 0.03          # a page whose text layer has a larger suspect share is read again (docs/pdf-preflight.md)
MIN_TOKENS = 25             # a page with fewer words has no suspect share: too few to measure
OSD_INK = 0.01              # a page needs this share of ink to be asked for its orientation
OSD_MINIMUM = 5.0           # ... and the detection this confidence to be believed
DEFAULT_VARIANT = "auto"    # measured: no change to a page without a defect, large gains on a page with one


class Blank(Enum):
    CONTENT = "content"
    BLANK = "blank"        # no ink worth a mark and no text: nothing to read
    MARKED = "marked"      # a little ink or text: kept, and why is said


class ColorMode(Enum):
    COLOUR = "colour"
    GREY = "grey"
    BILEVEL = "bilevel"


class Action(Enum):
    KEEP_TEXT = "keep the text layer"
    REREAD = "read again"                 # re-OCR the page's rendition
    OCR_MISSING = "read the pages with no text"
    NOTHING = "nothing to read"


# --- records --------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ImageFact:
    """One image drawn on a page, as the PDF declares it."""

    codec: str                 # the filter: JBIG2Decode, CCITTFaxDecode, DCTDecode, JPXDecode, FlateDecode, ...
    width: int
    height: int
    bits: int
    colorspace: str
    dpi: int                   # pixels per inch over the page's width (the image's real resolution if it fills the page)
    coverage: float            # the share of the page's area the image's box covers (1.0 when it fills it)
    risk: str = ""             # JBIG2: what the file says of its coding (a shared symbol table, or the scanner program's
                               # quality setting), since symbol coding can substitute one character for a look-alike
    tilt: float = 0.0          # the degrees the page's placement turns the image (a scanner program that deskewed it by
                               # placement leaves the pixels tilted by this much; the page, drawn, is straight)


@dataclass
class PageFacts:
    index: int                                  # from 0
    width_in: float
    height_in: float
    images: tuple[ImageFact, ...] = ()
    colour: ColorMode = ColorMode.BILEVEL
    codec: str = ""                             # the main image's
    dpi: int = 0                                # the main image's real resolution; 0 for a page with no image
    text_chars: int = 0                         # letters and digits in the text layer
    text_words: int = 0
    annotations: int = 0
    fields: int = 0
    ink: float = 0.0                            # the page's ink share before specks and edges are set aside
    core_ink: float = 0.0                       # ... and after
    pieces: int = -1                            # connected pieces of core ink; -1 when the page is too dense to count
    blank: Blank = Blank.CONTENT
    why: str = ""                               # for a MARKED page, what it holds; for a page with ink and no text, a note
    rotation: int | None = None                 # degrees to turn the page clockwise to be upright (OSD); None if unread
    rotation_confidence: float = 0.0
    skew: float | None = None                   # degrees, positive when lines rise to the right; None if no ink or no peak
    speckle: float | None = None                # share of ink pixels with no inked neighbor (dust, noise)
    uneven: float | None = None                 # gray levels of shading across the paper
    steps: tuple[str, ...] = ()                 # what the cleaning (``auto``) would do to this page
    suspect_share: float | None = None          # the text layer's share of words the English prior doubts
    tokens: int = 0
    seconds: float = 0.0

    def row(self) -> dict[str, Any]:
        d = asdict(self)
        d["blank"] = self.blank.value
        d["colour"] = self.colour.value
        return d


@dataclass
class FileFacts:
    path: str
    sha256: str
    size: int
    pages: list[PageFacts] = field(default_factory=list)
    producer: str = ""
    encrypted: bool = False
    locked: bool = False                        # needs a password that is not empty: reported, never cracked
    layers: int = 0                             # optional-content groups
    carried: Carried = field(default_factory=Carried)   # attachments, images, form answers, risks (jason.community.pdf_media)
    seconds: float = 0.0

    def count(self, kind: Blank) -> int:
        return sum(p.blank is kind for p in self.pages)

    @property
    def readable(self) -> list[PageFacts]:
        """The pages that hold something to read: every page that is not blank."""
        return [p for p in self.pages if p.blank is not Blank.BLANK]

    def share(self) -> float | None:
        """The text layer's suspect share over the pages that have text (words, not pages)."""
        t = sum(p.tokens for p in self.pages if p.suspect_share is not None)
        if not t:
            return None
        return sum(p.suspect_share * p.tokens for p in self.pages if p.suspect_share is not None) / t

    def row(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "size": self.size, "producer": self.producer,
                "encrypted": self.encrypted, "locked": self.locked, "layers": self.layers,
                "seconds": round(self.seconds, 2), "carried": self.carried.row(), "pages": [p.row() for p in self.pages]}


@dataclass(frozen=True)
class Recommendation:
    action: Action
    reason: str
    pages: tuple[int, ...] = ()                 # the pages (from 0) the action covers; empty for the whole file
    variant: str = ""


# --- the page's image -----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Drawn:
    """A page drawn to gray, with what was left off."""

    gray: np.ndarray
    annotations: int = 0
    fields: int = 0
    layers_off: int = 0
    layers_kept: str = ""                       # why the layers stayed on, when they did


def _gray(pix: Any) -> np.ndarray:
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()


def _layers_off(doc: Any) -> list[dict]:
    """Turn every optional-content layer off in the open document (not the file) and return their settings."""
    import pymupdf

    configs = doc.layer_ui_configs() or []
    for c in configs:
        doc.set_layer_ui_config(c["number"], pymupdf.PDF_OC_OFF)
    return configs


def _layers_restore(doc: Any, configs: Sequence[dict]) -> None:
    import pymupdf

    for c in configs:
        doc.set_layer_ui_config(c["number"], pymupdf.PDF_OC_ON if c.get("on") else pymupdf.PDF_OC_OFF)


def draw_gray(doc: Any, index: int, dpi: float = OCR_DPI, *, flatten: bool = True) -> Drawn:
    """One page as 8-bit gray at ``dpi``. With ``flatten``, annotations and form fields are left off, and so are the
    optional-content layers unless that would take away most of the page's ink (a scan placed in a layer).

    The text layer a scanner program added is invisible text; an image has none, so a drawn page has dropped it."""
    import pymupdf

    page = doc[index]
    annots = len(list(page.annots() or []))
    fields = len(list(page.widgets() or []))
    if not flatten:
        return Drawn(_gray(page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)), annots, fields)
    gray = _gray(page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, annots=False))
    configs = doc.layer_ui_configs() or []
    if not configs:
        return Drawn(gray, annots, fields)
    saved = [dict(c) for c in configs]
    try:
        _layers_off(doc)
        bare = _gray(page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, annots=False))
    finally:
        _layers_restore(doc, saved)
    ink_default, ink_bare = (g.size - int((g > 200).sum()) for g in (gray, bare))
    if ink_default and ink_bare < 0.25 * ink_default:
        return Drawn(gray, annots, fields, 0, "the page is drawn in an optional-content layer, so the layers stay on")
    return Drawn(bare, annots, fields, len(configs))


# --- blank pages ----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Ink:
    share: float                  # all ink
    core: float                   # after specks, edge shadows, and punch holes
    pieces: int                   # connected pieces of core ink; -1 when the page is too dense to count
    chars: int                    # pieces that may be characters (a size and a fill a scratch does not have); -1 if dense
    band: bool                    # every character-like piece lies in the top or bottom band (a page number, a head)


def ink_of(gray: np.ndarray, dpi: float = ANALYSIS_DPI) -> Ink:
    """Ink after a light threshold, and the pieces of it that are marks: not specks, not the scanner's edge shadow, not
    a punch hole. A piece may be a character when it is at least ``CHAR_IN`` wide and tall and fills ``CHAR_FILL`` of its
    box (a hair or a scratch does not)."""
    mask = gray <= prep.ink_level(gray)
    share = float(mask.mean())
    if share > DENSE_INK:
        return Ink(share, share, -1, -1, False)
    h, w = mask.shape
    speck = max(2, int(round(MIN_SPECK_IN * dpi)))
    edge = max(2, int(round(EDGE_IN * dpi)))
    hole_lo, hole_hi = (v * dpi for v in HOLE_IN)
    arc_lo = ARC_IN * dpi
    margin = HOLE_MARGIN_IN * dpi
    long_side, short_side = CHAR_LONG_IN * dpi, CHAR_SHORT_IN * dpi
    band = BAND * h
    keep, chars = [], []
    inner = mask.copy()
    inner[:edge, :] = inner[-edge:, :] = False           # the edge band: the scanner's shadow, never a mark
    inner[:, :edge] = inner[:, -edge:] = False
    for c in prep.components(inner):
        if c.width < speck and c.height < speck:
            continue
        cx, cy = (c.x0 + c.x1) / 2, (c.y0 + c.y1) / 2
        if (hole_lo <= c.width <= hole_hi and arc_lo <= c.height <= hole_hi and (cx < margin or cx > w - margin)
                and band <= cy <= h - band):
            continue                                     # a punch hole: a ring, a half ring, or a disk beside an edge
        keep.append(c)
        long_, short_ = max(c.width, c.height), min(c.width, c.height)
        fill = c.area / (c.width * c.height)
        blob = long_ <= BLOB_IN * dpi and long_ <= 1.4 * short_ and fill > 0.5
        if long_ >= long_side and short_ >= short_side and fill >= CHAR_FILL and long_ <= CHAR_ASPECT * short_ and not blob:
            chars.append(c)
    core = sum(c.area for c in keep) / mask.size

    in_band = bool(chars) and all(c.y1 < band or c.y0 > h - band for c in chars)
    return Ink(share, core, len(keep), len(chars), in_band)


_LEFT_BLANK = re.compile(r"\b(?:intentionally|purposely)\b.{0,20}\bblank\b|\bblank\s+page\b|\bleft\s+blank\b", re.I | re.S)


def classify_blank(ink: Ink, text: str = "") -> tuple[Blank, str]:
    """A page's kind from its ink and its text layer.

    BLANK only when the page has no ink worth a mark (``BLANK_INK``), no piece that may be a character, and no text.
    MARKED when it has little (a signature, a stamp, a page number, a note that it is left blank, or a text layer over
    almost no ink): kept, and the reason said. CONTENT otherwise, with a note when a page has ink and no text layer."""
    alnum = sum(ch.isalnum() for ch in text)
    has_text = alnum >= TEXTLESS_ALNUM or (alnum == 1 and ink.chars > 0)
    if ink.pieces < 0:
        return Blank.CONTENT, ("" if has_text else "ink and no text layer: to be read")
    if has_text and _LEFT_BLANK.search(text):
        return Blank.MARKED, "a note that the page is left blank"
    if not has_text and ink.chars == 0 and ink.core < BLANK_INK:
        return Blank.BLANK, "no ink worth a mark and no text"
    if ink.core < NEAR_INK or (has_text and alnum < SHORT_TEXT):
        what = ("a page number or a running head" if ink.band
                else "a stamp, a signature, a divider's title, or a short text")
        return Blank.MARKED, what + ("" if has_text else ", no text layer")
    return Blank.CONTENT, ("" if has_text else "ink and no text layer: to be read")


# --- page facts -----------------------------------------------------------------------------------------------------

_BILEVEL_FILTERS = ("JBIG2Decode", "CCITTFaxDecode")


def image_facts(doc: Any, page: Any) -> tuple[ImageFact, ...]:
    """The images a page draws, as the PDF declares them (codec, size, bits, color space, and resolution)."""
    width_in = float(page.rect.width) / 72 or 1.0
    area = float(page.rect.width * page.rect.height) or 1.0
    boxes = {}
    try:
        for info in page.get_image_info(xrefs=True):
            boxes.setdefault(info.get("xref"), info)
    except Exception:  # noqa: BLE001 - a page whose images cannot be listed has none to report
        return ()
    out = []
    for image in page.get_images(full=True):
        xref, _smask, w, h, bits, space, _alt, _name, codec = image[:9]
        info = boxes.get(xref) or {}
        box = info.get("bbox")
        shown_in = (box[2] - box[0]) / 72 if box and box[2] > box[0] else width_in
        cover = 0.0
        if box:
            cover = max(0.0, min(box[2], page.rect.x1) - max(box[0], page.rect.x0)) * \
                max(0.0, min(box[3], page.rect.y1) - max(box[1], page.rect.y0)) / area
        t = info.get("transform") or (1, 0, 0, 1, 0, 0)
        out.append(ImageFact(codec or "raw", int(w), int(h), int(bits), space or "", int(round(w / shown_in)),
                             round(cover, 3), _jbig2_risk(doc, xref) if "JBIG2" in (codec or "") else "",
                             round(math.degrees(math.atan2(t[1], t[0])), 2)))
    return tuple(out)


def _jbig2_risk(doc: Any, xref: int) -> str:
    """What a JBIG2 image's dictionary says of how it was coded: a shared symbol table (``JBIG2Globals``) or a quality
    setting the scanner program left (``JB2Quality``). Either may mean symbol coding; the file does not say whether it
    was lossless, so a person reads a page's digits against the paper when they matter."""
    try:
        parms = doc.xref_get_key(xref, "DecodeParms")[1] or ""
    except Exception:  # noqa: BLE001
        return ""
    notes = []
    if "JBIG2Globals" in parms:
        notes.append("shared symbol table")
    m = re.search(r"JB2Quality\s+(\d+)\s+0\s+R", parms)
    if m:
        try:
            notes.append(f"scanner quality setting {doc.xref_object(int(m.group(1))).strip()}")
        except Exception:  # noqa: BLE001
            notes.append("scanner quality setting")
    elif "JB2Quality" in parms:
        notes.append("scanner quality setting")
    return ", ".join(notes)


def _main_image(images: Sequence[ImageFact]) -> ImageFact | None:
    """The image that carries the page: the sharpest of those covering at least half of it, else the largest."""
    wide = [i for i in images if i.coverage >= 0.5]
    if wide:
        return max(wide, key=lambda i: (i.dpi, i.coverage))
    return max(images, key=lambda i: i.coverage, default=None)


def color_mode(doc: Any, page: Any, images: Sequence[ImageFact]) -> ColorMode:
    """Bilevel when every image is 1 bit; color when the page drawn in RGB has color in it (a color image whose pixels
    are all gray is gray); gray otherwise."""
    import pymupdf

    if images and all(i.bits == 1 for i in images):
        return ColorMode.BILEVEL
    grayish = all(i.colorspace in ("DeviceGray", "") for i in images) and bool(images)
    if grayish:
        return ColorMode.GREY
    pix = page.get_pixmap(dpi=40, colorspace=pymupdf.csRGB, annots=False)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).astype(np.int16)
    chroma = a.max(axis=2) - a.min(axis=2)
    return ColorMode.COLOUR if float((chroma > 24).mean()) > 0.002 else ColorMode.GREY


def orientation(gray: np.ndarray, dpi: float = ANALYSIS_DPI, *, minimum: float = OSD_MINIMUM) -> tuple[int | None, float]:
    """Tesseract's orientation and script detection (``--psm 0``): the degrees to turn the page clockwise to be upright
    (0, 90, 180, 270) and its confidence; None when the tool is missing, there is too little text, or it is not sure
    (confidence under ``minimum``, 5: on forms, tables, and noisy type it called upright pages upside down at 1.5 to 4,
    where prose is 10 and up, and a page said to be upside down is one a person turns before OCR)."""
    import os
    import subprocess
    import tempfile

    from PIL import Image

    from jason.community.ocr import PyMuPdfTesseract, TesseractCli

    exe = TesseractCli.exe()
    if not exe:
        return None, 0.0
    env = dict(os.environ)
    tessdata = PyMuPdfTesseract.tessdata()
    if tessdata:
        env["TESSDATA_PREFIX"] = tessdata
    env["OMP_THREAD_LIMIT"] = "1"
    fd, name = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        Image.fromarray(gray).save(name, dpi=(int(dpi), int(dpi)))
        done = subprocess.run([exe, name, "stdout", "--psm", "0", "-l", "osd", "--dpi", str(int(dpi))],
                              capture_output=True, timeout=120, env=env, check=False)
    except (OSError, subprocess.SubprocessError):
        return None, 0.0
    finally:
        try:
            os.remove(name)
        except OSError:
            pass
    out = done.stdout.decode("utf-8", errors="replace")
    rot = re.search(r"Rotate:\s*(\d+)", out)
    conf = re.search(r"Orientation confidence:\s*([\d.]+)", out)
    if not rot or not conf or float(conf.group(1)) < minimum:
        return None, float(conf.group(1)) if conf else 0.0
    return int(rot.group(1)), float(conf.group(1))


def text_quality(texts: Sequence[str], lexicon: Any) -> list[tuple[float | None, int]]:
    """Each text layer's share of words the English prior doubts, with its word count: the signal that tracks an OCR's
    error rate (docs/ocr-correction.md). The language model also learns the file's own defined terms and names, so a
    document's proper nouns are not doubts. A page with fewer than ``MIN_TOKENS`` words has no share (None)."""
    from jason.community.lexicon import document_terms

    lex = lexicon.with_terms(document_terms("\n".join(texts), lexicon))
    out = []
    for text in texts:
        tokens = text.split()
        if len(tokens) < MIN_TOKENS:
            out.append((None, len(tokens)))
            continue
        out.append((sum(lex.suspect(t) for t in tokens) / len(tokens), len(tokens)))
    return out


def inspect_page(doc: Any, index: int, *, osd: bool = True) -> tuple[PageFacts, str]:
    """One page's facts and its text layer (kept apart: the text is a reading, and is scored at the file's level)."""
    t0 = time.perf_counter()
    page = doc[index]
    images = image_facts(doc, page)
    main = _main_image(images)
    text = page.get_text()
    facts = PageFacts(index, round(page.rect.width / 72, 2), round(page.rect.height / 72, 2), images,
                      colour=ColorMode.GREY, codec=main.codec if main else "", dpi=main.dpi if main else 0,
                      text_chars=sum(ch.isalnum() for ch in text), text_words=len(text.split()),
                      annotations=len(list(page.annots() or [])), fields=len(list(page.widgets() or [])))
    facts.colour = color_mode(doc, page, images)
    drawn = draw_gray(doc, index, ANALYSIS_DPI)
    ink = ink_of(drawn.gray, ANALYSIS_DPI)
    facts.ink, facts.core_ink, facts.pieces = ink.share, ink.core, ink.pieces
    facts.blank, facts.why = classify_blank(ink, text)
    if facts.blank is not Blank.BLANK:
        if osd and ink.share >= OSD_INK:
            facts.rotation, facts.rotation_confidence = orientation(drawn.gray, ANALYSIS_DPI)
        # the defects the cleaning acts on, measured where they were calibrated (a page drawn at the OCR resolution)
        full = draw_gray(doc, index, OCR_DPI).gray
        found = prep.defects(full, OCR_DPI)
        facts.skew = round(found.skew, 2) if found.skew is not None else None
        facts.speckle, facts.uneven = round(found.speckle, 4), round(found.uneven, 1)
        facts.steps = prep.steps_for(found)
    facts.seconds = time.perf_counter() - t0
    return facts, text


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_pdf(path: Path | str, *, lexicon: Any = None, osd: bool = True, media: bool = True,
                progress: Callable[[int, int], None] | None = None) -> FileFacts:
    """A PDF's facts, page by page. With a ``lexicon`` (``jason.community.lexicon.Lexicon``) each page's text layer is
    scored by the English prior. With ``media`` the attachments, images, form answers, and risks are listed
    (``jason.community.pdf_media``). The file is only read; a file that needs a password is reported and not read."""
    import pymupdf

    path = Path(path)
    t0 = time.perf_counter()
    facts = FileFacts(str(path), sha256_of(path), path.stat().st_size)
    with pymupdf.open(path) as doc:
        facts.encrypted = bool(doc.is_encrypted or (doc.metadata or {}).get("encryption"))
        if doc.needs_pass and not doc.authenticate(""):      # the empty password is how a viewer opens an owner-locked file
            facts.locked = True
            facts.carried.locked = True
            return facts
        facts.producer = (doc.metadata or {}).get("producer") or ""
        facts.layers = len(doc.layer_ui_configs() or [])
        if media:
            facts.carried, _ = carried_of(doc, facts.sha256)
        texts = []
        for i in range(doc.page_count):
            page_facts, text = inspect_page(doc, i, osd=osd)
            facts.pages.append(page_facts)
            texts.append(text)
            if progress:
                progress(i + 1, doc.page_count)
    if lexicon is not None:
        for page_facts, (share, tokens) in zip(facts.pages, text_quality(texts, lexicon)):
            page_facts.suspect_share, page_facts.tokens = share, tokens
    facts.seconds = time.perf_counter() - t0
    return facts


def _inspect_task(args: tuple) -> FileFacts:
    path, lexicon, osd, media = args
    return inspect_pdf(path, lexicon=lexicon, osd=osd, media=media)


def inspect_many(paths: Sequence[Path | str], *, lexicon: Any = None, osd: bool = True, media: bool = True, jobs: int = 1,
                 progress: Callable[[str], None] | None = None) -> list[FileFacts]:
    """Several PDFs, one file to a process when ``jobs`` is more than 1 (each file's pages are read in order)."""
    tasks = [(str(p), lexicon, osd, media) for p in paths]
    if jobs <= 1 or len(tasks) <= 1:
        out = []
        for t in tasks:
            out.append(_inspect_task(t))
            if progress:
                progress(t[0])
        return out
    from concurrent.futures import ProcessPoolExecutor

    out = []
    with ProcessPoolExecutor(min(jobs, len(tasks))) as pool:
        for facts in pool.map(_inspect_task, tasks):
            out.append(facts)
            if progress:
                progress(facts.path)
    return out


def find_pdfs(source: Path | str) -> list[Path]:
    """A PDF, or the PDFs under a folder, in name order."""
    source = Path(source)
    if source.is_file():
        return [source]
    return sorted(p for p in source.rglob("*") if p.suffix.lower() == ".pdf" and p.is_file())


# --- what to do -----------------------------------------------------------------------------------------------------


def recommend(facts: FileFacts, *, limit: float = SHARE_LIMIT) -> list[Recommendation]:
    """What to do with the file's pages: keep a text layer that reads as English, read again (from the cleaned
    rendition) a page whose text layer the English prior doubts more than ``limit`` of, read for the first time a page
    with ink and no text, and leave a blank page unread. A blank page stays in the file; the original is not changed."""
    keep, again, missing, blank = [], [], [], []
    for p in facts.pages:
        if p.blank is Blank.BLANK:
            blank.append(p.index)
        elif p.text_chars < TEXTLESS_ALNUM and (p.blank is Blank.CONTENT or p.core_ink >= BLANK_INK):
            missing.append(p.index)
        elif p.suspect_share is not None and p.suspect_share > limit:
            again.append(p.index)
        else:
            keep.append(p.index)
    out = []
    if keep:
        out.append(Recommendation(Action.KEEP_TEXT, "the text layer reads as English" if any(
            p.suspect_share is not None for p in facts.pages) else "no language model was given to judge it", tuple(keep)))
    if again:
        out.append(Recommendation(Action.REREAD, f"the text layer's suspect share is over {limit:.0%}", tuple(again),
                                  DEFAULT_VARIANT))
    if missing:
        out.append(Recommendation(Action.OCR_MISSING, "ink and no text layer", tuple(missing), DEFAULT_VARIANT))
    if blank and not (keep or again or missing):
        out.append(Recommendation(Action.NOTHING, "every page is blank", tuple(blank)))
    return out


# --- the cleaned rendition ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Variant:
    """A named preprocessing: operations in order on the page drawn at ``OCR_DPI`` (docs/pdf-preflight.md)."""

    name: str
    steps: tuple[tuple, ...]
    note: str


VARIANTS: dict[str, Variant] = {v.name: v for v in (
    Variant("scanned", (), "the page as drawn, in gray: the baseline every other variant is measured against"),
    Variant("auto", (("auto",),), "only what the page needs: shading flattened, dust median filtered, a tilt over 1 degree "
                                  "turned; a page with none of these is returned as drawn"),
    Variant("smooth", (("blur", 0.8), ("median", 3)), "a light blur and a 3x3 median on every page; fewer errors on the "
                                                    "bilevel scans measured, but not on every page"),
    Variant("flatten", (("flatten",),), "the page divided by its own paper brightness"),
    Variant("despeckle", (("median", 3),), "a 3x3 median"),
    Variant("deskew", (("deskew",),), "every page turned to straighten its lines, whatever the tilt"),
    Variant("stretch", (("stretch",),), "a contrast stretch (the 1st and 99th percentile to black and white)"),
    Variant("clahe", (("clahe",),), "contrast-limited adaptive histogram equalization"),
    Variant("otsu", (("otsu",),), "bilevel by one global threshold: measured worse than gray for Tesseract"),
    Variant("sauvola", (("sauvola",),), "bilevel by a local (Sauvola) threshold: measured worse than gray unless the paper "
                                        "is unevenly lit"),
)}


def apply_variant(gray: np.ndarray, variant: str | Variant, dpi: float = OCR_DPI) -> tuple[np.ndarray, list[str]]:
    """A drawn page after a variant's operations, and the names of the steps that changed it."""
    v = VARIANTS[variant] if isinstance(variant, str) else variant
    done: list[str] = []
    for op, *args in v.steps:
        if op == "auto":
            gray, taken = prep.auto_clean(gray, dpi)
            done += taken
            continue
        if op == "flatten":
            gray = prep.flatten(gray)
        elif op == "median":
            gray = prep.median(gray, *(args or (3,)))
        elif op == "blur":
            gray = prep.blur(gray, *(args or (0.8,)))
        elif op == "stretch":
            gray = prep.stretch(gray)
        elif op == "clahe":
            gray = prep.clahe(gray)
        elif op == "otsu":
            gray = prep.binarize_global(gray)
        elif op == "sauvola":
            gray = prep.sauvola(gray, int(51 * dpi / 300) | 1)
        elif op == "deskew":
            gray, angle = prep.deskew(gray, dpi)
            if angle is None or abs(angle) < 0.15:
                continue
        else:
            raise ValueError(f"unknown operation {op}")
        done.append(op)
    return gray, done


@dataclass(frozen=True)
class Clean:
    gray: np.ndarray
    dpi: int
    steps: tuple[str, ...]
    drawn: Drawn


def native_gray(doc: Any, index: int) -> tuple[np.ndarray, float] | None:
    """The page's one full-page image at its own resolution, not drawn: its pixels (ink dark) and the pixels per inch it
    is placed at. None unless the page is a single raster covering it (a scan) that PyMuPDF can decode."""
    import pymupdf

    page = doc[index]
    try:
        infos = page.get_image_info(xrefs=True)
    except Exception:  # noqa: BLE001
        return None
    area = float(page.rect.width * page.rect.height) or 1.0
    big = [i for i in infos if (i["bbox"][2] - i["bbox"][0]) * (i["bbox"][3] - i["bbox"][1]) / area >= 0.85]
    if len(big) != 1 or len(infos) != 1:
        return None
    info = big[0]
    try:
        pix = pymupdf.Pixmap(doc, info["xref"])
        a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, 0].copy()
    except Exception:  # noqa: BLE001
        return None
    if a.mean() < 128:                                  # a stencil mask (ink 255) or a negative: ink must be dark
        a = 255 - a
    t = info["transform"]
    return a, info["width"] / (math.hypot(t[0], t[1]) / 72 or 1.0)


def render_clean(doc: Any, index: int, variant: str = DEFAULT_VARIANT, *, dpi: int = OCR_DPI, source: str = "drawn") -> Clean:
    """One page as a cleaned image for OCR: drawn at ``dpi`` (annotations, form fields, and optional-content layers left
    off; the scanner's text layer is not in an image), or with ``source="native"`` taken from the page's own raster at its
    real resolution when it is a scan, and then put through ``variant``. A vision model is given the same image."""
    drawn = draw_gray(doc, index, dpi)
    gray, at = drawn.gray, dpi
    if source == "native":
        n = native_gray(doc, index)
        if n is not None:
            gray, at = n[0], int(round(n[1]))
    out, steps = apply_variant(gray, variant, at)
    return Clean(out, at, tuple(steps), drawn)


def _save_png(path: Path, gray: np.ndarray, dpi: int) -> None:
    from PIL import Image

    img = Image.fromarray(gray)
    if len(np.unique(gray[::5, ::5])) <= 2:             # bilevel: a 1-bit PNG
        img = img.convert("1")
    img.save(path, dpi=(dpi, dpi), optimize=False)


def rendition_dir(store: Path | str, sha256: str) -> Path:
    """Where a file's rendition lives in the store: one folder per original, named by the first sixteen characters of its
    sha256. The original is not in it and is never touched."""
    return Path(store) / sha256[:16]


def _render_task(args: tuple) -> tuple[int, str, int, tuple[str, ...]]:
    path, index, variant, dpi, source, folder = args
    import pymupdf

    with pymupdf.open(path) as doc:
        c = render_clean(doc, index, variant, dpi=dpi, source=source)
    name = f"page-{index + 1:04d}.png"
    _save_png(Path(folder) / name, c.gray, c.dpi)
    return index, name, c.dpi, c.steps


def write_rendition(facts: FileFacts, store: Path | str, *, variant: str = DEFAULT_VARIANT, pdf: bool = False,
                    pages: Sequence[int] | None = None, dpi: int = OCR_DPI, source: str = "drawn", jobs: int = 1) -> Path:
    """Write the cleaned pages of a file to its folder in ``store``: ``page-NNNN.png`` for each page that is not blank
    (``pages`` narrows them), ``rendition.json`` (the variant, the steps each page needed, and the blank pages left out),
    and with ``pdf`` a ``clean.pdf`` of those images (no text layer; an image has none). Blank pages stay in the original and
    are listed, never dropped from it. Returns the folder."""
    import pymupdf

    folder = rendition_dir(store, facts.sha256)
    folder.mkdir(parents=True, exist_ok=True)
    want = [p.index for p in facts.pages if p.blank is not Blank.BLANK and (pages is None or p.index in pages)]
    tasks = [(facts.path, i, variant, dpi, source, str(folder)) for i in want]
    if jobs > 1 and len(tasks) > 1:
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor(min(jobs, len(tasks))) as pool:
            done = list(pool.map(_render_task, tasks))
    else:
        done = [_render_task(t) for t in tasks]
    record = {"source": {"sha256": facts.sha256, "size": facts.size, "pages": len(facts.pages)}, "variant": variant,
              "dpi": dpi, "native": source == "native",
              "pages": {str(i): {"file": name, "dpi": at, "steps": list(steps)} for i, name, at, steps in done},
              "blank": [p.index for p in facts.pages if p.blank is Blank.BLANK],
              "marked": {str(p.index): p.why for p in facts.pages if p.blank is Blank.MARKED}}
    if pdf and done:
        with pymupdf.open() as out, pymupdf.open(facts.path) as src:
            for i, name, at, _ in sorted(done):
                rect = src[i].rect
                page = out.new_page(width=rect.width, height=rect.height)
                page.insert_image(rect, filename=str(folder / name))
            out.save(folder / "clean.pdf", garbage=3, deflate=True)
        record["pdf"] = "clean.pdf"
    (folder / "rendition.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    return folder


def ocr_rendition(folder: Path | str, *, language: str = "eng") -> Path:
    """Read a rendition's pages with Tesseract's tool (``ocr.TesseractCli``, the engine measured best) and write
    ``ocr.txt`` (the pages' text, in the shape ``TesseractCli.text_of`` gives), ``ocr.pages.json`` (each page's text by its
    index in the original), and ``ocr.words.json`` (every word with its box and Tesseract's confidence) beside them. The original's own text layer is not changed. Raises ``RuntimeError`` when the
    tool is not installed."""
    from jason.community.ocr import TesseractCli

    folder = Path(folder)
    if not TesseractCli.available():
        raise RuntimeError("Tesseract is not installed (see docs/document-tools.md)")
    record = json.loads((folder / "rendition.json").read_text(encoding="utf-8"))
    by_page: dict[str, str] = {}
    words = []
    for key in sorted(record["pages"], key=int):
        info = record["pages"][key]
        cli = TesseractCli(dpi=int(info["dpi"]), language=language)
        w = cli.image_words(folder / info["file"], int(key))
        words += w
        by_page[key] = TesseractCli.words_text(w)
    (folder / "ocr.txt").write_text(TesseractCli.words_text(words), encoding="utf-8")
    (folder / "ocr.pages.json").write_text(json.dumps(by_page, indent=1), encoding="utf-8")
    # Each word with its box (pixels of the rendition's page image) and Tesseract's confidence, 0 to 100: a second detector
    # for the word layer (docs/ocr-correction.md), and the page image it can crop from is the rendition's own.
    (folder / "ocr.words.json").write_text(json.dumps(
        [{"page": w.page, "block": w.block, "paragraph": w.paragraph, "line": w.line, "left": w.left, "top": w.top,
          "width": w.width, "height": w.height, "conf": w.confidence, "text": w.text} for w in words]), encoding="utf-8")
    return folder / "ocr.txt"


# --- the report -----------------------------------------------------------------------------------------------------


def ranges(pages: Iterable[int]) -> str:
    """Page indexes (from 0) as the pages a person counts (from 1), with runs joined: 1-3, 7, 9-10."""
    nums = sorted(p + 1 for p in pages)
    out: list[str] = []
    start = prev = None
    for n in nums:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(f"{start}-{prev}" if prev != start else str(start))
            start = prev = n
    if start is not None:
        out.append(f"{start}-{prev}" if prev != start else str(start))
    return ", ".join(out)


def _median(values: Sequence[float]) -> float:
    v = sorted(values)
    return v[len(v) // 2] if v else 0.0


def report_lines(facts: FileFacts, *, limit: float = SHARE_LIMIT) -> list[str]:
    """A file's preflight as plain lines: what it holds, what is wrong, and what to do. A blank page is said to be kept in
    the original; nothing here changes it."""
    name = Path(facts.path).name
    out = [f"{name}  ({facts.size / 1e6:.1f} MB, sha256 {facts.sha256[:12]}, {len(facts.pages)} pages"
           + (f", made by {facts.producer}" if facts.producer else "") + ")"]
    if facts.locked:
        return out + ["  locked: it needs a password, so nothing was read (it is not cracked)"]
    if facts.encrypted:
        out.append("  encrypted"
                   + (f"; opening it without a password, it does not permit {', '.join(facts.carried.restrictions)}"
                      if facts.carried.restrictions else ""))
    pages = facts.pages
    blank = [p.index for p in pages if p.blank is Blank.BLANK]
    marked = [p for p in pages if p.blank is Blank.MARKED]
    out.append(f"  pages: {facts.count(Blank.CONTENT)} content, {len(marked)} marked and kept, {len(blank)} blank"
               + (f" (page {ranges(blank)}: kept in the original, left out of the rendition)" if blank else ""))
    by: dict[str, list[int]] = {}
    for p in marked:
        by.setdefault(p.why, []).append(p.index)
    for why, idx in by.items():
        out.append(f"    kept, near blank: page {ranges(idx)}: {why}")
    codecs: dict[str, int] = {}
    colours: dict[str, int] = {}
    for p in pages:
        codecs[p.codec or "no image"] = codecs.get(p.codec or "no image", 0) + 1
        colours[p.colour.value] = colours.get(p.colour.value, 0) + 1
    dpis = [p.dpi for p in pages if p.dpi]
    out.append("  images: " + ", ".join(f"{n} {c}" for c, n in codecs.items())
               + (f"; {min(dpis)} to {max(dpis)} dpi as placed" if dpis else "")
               + "; " + ", ".join(f"{n} {c}" for c, n in colours.items()))
    low = [p.index for p in pages if p.dpi and p.dpi < 200 and p.blank is not Blank.BLANK]
    if low:
        out.append(f"    low resolution (under 200 dpi): page {ranges(low)}; drawn at {OCR_DPI} dpi for OCR")
    risky = sorted({i.risk for p in pages for i in p.images if i.risk})
    if risky:
        n = sum(1 for p in pages if any(i.risk for i in p.images))
        out.append(f"  JBIG2 coding: {n} pages carry {', '.join(risky)}. Symbol coding can swap a character for a "
                   "look-alike; the file does not say it was lossless. Check digits against the paper when they matter.")
    tilts = [p.index for p in pages if p.images and abs(p.images[0].tilt) >= 0.3]
    if tilts:
        out.append(f"  placed tilted: {len(tilts)} pages are drawn straight by the scanner program's placement "
                   "(the pixels themselves are tilted)")
    nonblank = [p for p in pages if p.blank is not Blank.BLANK]
    read = [p for p in nonblank if p.rotation is not None]
    turned = [p.index for p in read if p.rotation]
    out.append("  orientation: " + (f"page {ranges(turned)} to be turned (Tesseract OSD, confidence 5 or more)" if turned
                                    else f"upright where read ({len(read)} of {len(nonblank)} pages read confidently)"))
    skews = [p.skew for p in nonblank if p.skew is not None]
    if skews:
        big = [p.index for p in nonblank if p.skew is not None and abs(p.skew) >= prep.SKEW_MIN]
        out.append(f"  skew: median {_median([abs(s) for s in skews]):.2f} degrees"
                   + (f"; page {ranges(big)} at {prep.SKEW_MIN:g} degrees or more" if big
                      else f"; none at {prep.SKEW_MIN:g} degrees or more"))
    cleaned = [p for p in nonblank if p.steps]
    if cleaned:
        by2: dict[str, list[int]] = {}
        for p in cleaned:
            by2.setdefault("+".join(p.steps), []).append(p.index)
        out.append("  cleaning the rendition applies (every other page is left as drawn): "
                   + "; ".join(f"{k} on page {ranges(v)}" for k, v in by2.items()))
    shares = [p for p in nonblank if p.suspect_share is not None]
    if shares:
        wsum = sum(p.tokens for p in shares)
        mean = sum(p.suspect_share * p.tokens for p in shares) / wsum
        over = [p.index for p in shares if p.suspect_share > limit]
        out.append(f"  text layer: {len(shares)} pages scored; {mean:.1%} of words doubted by the English prior"
                   f" (median page {_median([p.suspect_share for p in shares]):.1%}); "
                   + (f"page {ranges(over)} over {limit:.0%}" if over else f"none over {limit:.0%}"))
    notext = [p.index for p in nonblank if p.text_chars < TEXTLESS_ALNUM]
    if notext:
        out.append(f"  no text layer: page {ranges(notext)}")
    c = facts.carried
    kinds: dict[str, int] = {}
    for m in c.media:
        kinds[m.kind.value] = kinds.get(m.kind.value, 0) + 1
    extra = [f"{n} {k}" for k, n in kinds.items() if k != "scan"]
    if extra or c.fields or c.flags:
        out.append("  carries: " + ", ".join(extra + ([f"{len(c.fields)} filled form fields"] if c.fields else [])
                                             + ([f"flags: {', '.join(c.flags)} (never run)"] if c.flags else [])))
    if facts.layers:
        out.append(f"  optional-content layers: {facts.layers} (turned off in the rendition unless the page is drawn in one)")
    for r in recommend(facts, limit=limit):
        where = f" (page {ranges(r.pages)})" if r.pages else ""
        out.append(f"  -> {r.action.value}{where}: {r.reason}" + (f"; variant {r.variant}" if r.variant else ""))
    return out
