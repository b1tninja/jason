"""Synthetic OCR pairs for the channel: clean text rendered, degraded, read back, and aligned with what was printed.

A recognizer's confusions are learned from words it read wrongly. A working copy beside a scan gives a few hundred of them
and only for one typeface; text jason already has clean (the statutes it exported) gives as many as are wanted. Pages of
that text are set in a serif face, degraded the way a poor scan is (low resolution, blur, noise, JPEG), and read by the
Tesseract tool; the words it got wrong, aligned with the words printed, are the pairs ``ocr_channel.learn`` counts (the
idea of Guan and Greene, 2024, "Advancing Post-OCR Correction: A Comparative Study of Synthetic Data"). Nothing here
reads a scan or an association's record: the pairs are letters, and the text is public law.

Needs PyMuPDF, Pillow, and the Tesseract tool (``ocr.TesseractCli.available``).
"""

from __future__ import annotations

import difflib
import io
import os
import random
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, Sequence

from jason.community.lexicon import core
from jason.community.ocr_channel import _edit_distance

# (dpi, blur radius, JPEG quality, noise): the degradations that produced misreads like a poor scan's.
VARIANTS = ((100, 0.8, 35, 6), (85, 0.6, 50, 4), (120, 1.0, 25, 8), (75, 0.0, 70, 3), (95, 0.9, 30, 10))
WORDS_PER_PAGE = 520


def source_words(texts: Iterable[str], *, limit: int = 60000, per_text: int = 400, seed: int = 5) -> list[str]:
    """Words of the clean texts, a stretch of each, shuffled by text so the pages mix many sources."""
    rng = random.Random(seed)
    texts = list(texts)
    rng.shuffle(texts)
    out: list[str] = []
    for text in texts:
        text = re.sub(r"^---.*?---", "", text, flags=re.S)
        text = re.sub(r"[#*_`>|\[\]]", " ", text)
        out += re.findall(r"[A-Za-z][A-Za-z'.,;:()-]*", text)[:per_text]
        if len(out) >= limit:
            break
    return out


def misreads(read: Sequence[str], printed: Sequence[str]) -> list[tuple[str, str]]:
    """(as read, as printed) for each word the recognizer got wrong one for one: letters only, lowercased, a few edits
    apart. Words it ran together, split, or dropped are not letter confusions and are left out."""
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=list(read), b=list(printed), autojunk=False).get_opcodes():
        if tag != "replace" or i2 - i1 != j2 - j1 or i2 - i1 > 4:
            continue
        for a, b in zip(read[i1:i2], printed[j1:j2]):
            ra, pb = core(a).lower(), core(b).lower()
            if re.fullmatch(r"[a-z]+", ra) and re.fullmatch(r"[a-z]+", pb) and ra != pb and _edit_distance(ra, pb) <= 3:
                out.append((ra, pb))
    return out


def synthetic_pairs(texts: Iterable[str], *, pages: int = 40, variants: Sequence[tuple] = VARIANTS, seed: int = 5
                    ) -> tuple[list[tuple[str, str]], list[str]]:
    """The pairs, and every word printed (the chances to misread, for ``ocr_channel.learn``). Raises ``RuntimeError`` when
    the Tesseract tool is not installed."""
    import pymupdf
    from PIL import Image, ImageFilter

    from jason.community.ocr import PyMuPdfTesseract, TesseractCli, parse_tsv

    exe = TesseractCli.exe()
    if not exe:
        raise RuntimeError("the Tesseract tool is not installed (ocr.TesseractCli.available)")
    rng = random.Random(seed)
    words = source_words(texts, limit=pages * WORDS_PER_PAGE + 1000, seed=seed)
    chunks = [words[p * WORDS_PER_PAGE:(p + 1) * WORDS_PER_PAGE] for p in range(pages)]
    chunks = [c for c in chunks if len(c) >= 50]
    doc = pymupdf.open()
    for chunk in chunks:
        page = doc.new_page(width=612, height=792)
        page.insert_textbox(pymupdf.Rect(72, 72, 540, 720), " ".join(chunk), fontname="tiro", fontsize=11, align=3)
    env = dict(os.environ)
    tessdata = PyMuPdfTesseract.tessdata()
    if tessdata:
        env["TESSDATA_PREFIX"] = tessdata
    pairs: list[tuple[str, str]] = []
    printed: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "page.jpg"
        for dpi, blur, quality, noise in variants:
            for n, chunk in enumerate(chunks):
                pix = doc[n].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
                image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                if blur:
                    image = image.filter(ImageFilter.GaussianBlur(blur))
                if noise:
                    pixels = image.load()
                    for _ in range(pix.width * pix.height // 40):
                        x, y = rng.randrange(pix.width), rng.randrange(pix.height)
                        pixels[x, y] = max(0, min(255, pixels[x, y] + rng.randint(-noise * 8, noise * 8)))
                buffer = io.BytesIO()
                image.save(buffer, "JPEG", quality=quality)
                path.write_bytes(buffer.getvalue())
                done = subprocess.run([exe, str(path), "stdout", "-l", "eng", "--dpi", str(dpi), "tsv"],
                                      capture_output=True, env=env, check=False, timeout=120)
                read = [w.text for w in parse_tsv(done.stdout.decode("utf-8", errors="replace"), n)]
                pairs += misreads(read, chunk)
                printed += [core(w).lower() for w in chunk]
    return pairs, printed


__all__ = ["VARIANTS", "misreads", "source_words", "synthetic_pairs"]
