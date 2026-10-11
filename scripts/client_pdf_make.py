"""Made-up scanned PDFs for the client-side rendering measurement (docs/pdf-splitter-client-side.md).

Writes, into a scratch folder you name (never the repository, never a real archive), PDFs whose pages are one image each, in the
codecs a scanned archive uses, plus a vector-text PDF:

    ccitt100.pdf   100 pages, 1-bit, CCITT Group 4, 200 dpi A4         (a bilevel office scan)
    jpeg100.pdf    100 pages, colour, DCT (JPEG) q70, 200 dpi A4        (a colour scan)
    flate100.pdf   100 pages, 8-bit grey, Flate, 150 dpi A4             (a grey scan)
    jpx100.pdf     100 pages, colour, JPEG 2000 (JPXDecode), 150 dpi    (a scan some scanners and archivers write)
    ccitt2000.pdf  2,000 pages, CCITT Group 4                           (the page-count ceiling case)
    text500.pdf    500 pages of vector text (PyMuPDF)
    big.bin        a file of random bytes for the hashing test (size from --hash-mb)

JBIG2 is not made: no encoder (jbig2enc) is installed here and neither Pillow nor PyMuPDF writes it. Every page is generated from
the page number and a seed, so a run is repeatable. Nothing here reads any real file.

    python scripts/client_pdf_make.py SCRATCH_DIR [--hash-mb 100]
"""

from __future__ import annotations

import argparse
import io
import os
import random
import struct
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

A4 = (595.0, 842.0)                       # points


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf", "calibri.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def page_image(n: int, w: int, h: int, mode: str, seed: int = 7) -> Image.Image:
    """A made-up page: a heading, lines of words, a table rule, a little speckle. Colour pages get a coloured band and stamp."""
    rnd = random.Random(seed * 100003 + n)
    img = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(img)
    big, body = _font(max(18, h // 45)), _font(max(12, h // 80))
    d.text((w // 12, h // 14), f"Example Village HOA   Notice {n}", fill=0, font=big)
    words = "the board of directors meeting minutes budget reserve assessment owner notice account payment".split()
    y = h // 7
    while y < h - h // 8:
        line = " ".join(rnd.choice(words) for _ in range(rnd.randint(6, 12)))
        d.text((w // 12, y), line, fill=rnd.choice((0, 0, 20, 40)), font=body)
        y += h // 60
        if rnd.random() < 0.05:
            d.line((w // 12, y, w - w // 12, y), fill=0, width=2)
    for _ in range(40):
        x, yy = rnd.randrange(w), rnd.randrange(h)
        d.point((x, yy), fill=0)
    if mode == "1":
        return img.point(lambda v: 255 if v > 128 else 0).convert("1")
    if mode == "L":
        return img
    rgb = Image.merge("RGB", (img, img, img))
    dr = ImageDraw.Draw(rgb)
    dr.rectangle((w // 12, h // 5, w - w // 12, h // 5 + h // 30), fill=(200 - n % 50, 220, 255))
    dr.ellipse((w - w // 4, h - h // 5, w - w // 12, h - h // 8), outline=(180, 20, 20), width=6)
    return rgb


# --- a minimal PDF writer (one image per page) -----------------------------------------------------------------------------

class Pdf:
    def __init__(self) -> None:
        self.objs: list[bytes] = []

    def add(self, body: bytes) -> int:
        self.objs.append(body)
        return len(self.objs)            # 1-based object number

    def stream(self, d: bytes, data: bytes) -> int:
        return self.add(b"<< " + d + b" /Length " + str(len(data)).encode() + b" >>\nstream\n" + data + b"\nendstream")

    def reserve(self) -> int:
        self.objs.append(b"")
        return len(self.objs)

    def set(self, num: int, body: bytes) -> None:
        self.objs[num - 1] = body

    def write(self, path: Path, root: int) -> None:
        out = io.BytesIO()
        out.write(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
        offs = []
        for i, body in enumerate(self.objs, 1):
            offs.append(out.tell())
            out.write(f"{i} 0 obj\n".encode() + body + b"\nendobj\n")
        x = out.tell()
        out.write(f"xref\n0 {len(self.objs) + 1}\n".encode() + b"0000000000 65535 f \n")
        for o in offs:
            out.write(f"{o:010d} 00000 n \n".encode())
        out.write(f"trailer\n<< /Size {len(self.objs) + 1} /Root {root} 0 R >>\nstartxref\n{x}\n%%EOF\n".encode())
        path.write_bytes(out.getvalue())


def ccitt_bytes(img: Image.Image) -> bytes:
    """The raw CCITT Group 4 strip of a 1-bit image (one strip, so it is one valid stream)."""
    buf = io.BytesIO()
    img.save(buf, "TIFF", compression="group4", tiffinfo={278: img.height})
    buf.seek(0)
    t = Image.open(buf)
    offs, cnts = t.tag_v2[273], t.tag_v2[279]
    if not isinstance(offs, tuple):
        offs, cnts = (offs,), (cnts,)
    if len(offs) != 1:
        raise RuntimeError("the TIFF came out in more than one strip")
    raw = buf.getvalue()
    return raw[offs[0]: offs[0] + cnts[0]]


def encode(kind: str, n: int, dpi: int) -> tuple[bytes, bytes, int, int]:
    """(the image dictionary entries, the stream bytes, width, height) for page ``n``."""
    w, h = round(A4[0] / 72 * dpi), round(A4[1] / 72 * dpi)
    if kind == "ccitt":
        img = page_image(n, w, h, "1")
        # Pillow's mode "1" is 1 = white; PDF's default CCITT (BlackIs1 false) takes 0 = black, so the stream is used as it is
        data = ccitt_bytes(img)
        d = (f"/Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceGray /BitsPerComponent 1 "
             f"/Filter /CCITTFaxDecode /DecodeParms << /K -1 /Columns {w} /Rows {h} /BlackIs1 true >>").encode()
        return d, data, w, h
    if kind == "jpeg":
        img = page_image(n, w, h, "RGB")
        b = io.BytesIO(); img.save(b, "JPEG", quality=70)
        d = f"/Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode".encode()
        return d, b.getvalue(), w, h
    if kind == "flate":
        img = page_image(n, w, h, "L")
        d = f"/Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode".encode()
        return d, zlib.compress(img.tobytes(), 6), w, h
    if kind == "jpx":
        img = page_image(n, w, h, "RGB")
        b = io.BytesIO(); img.save(b, "JPEG2000", quality_mode="rates", quality_layers=[20])
        d = f"/Type /XObject /Subtype /Image /Width {w} /Height {h} /Filter /JPXDecode".encode()
        return d, b.getvalue(), w, h
    raise ValueError(kind)


def build_image_pdf(path: Path, kind: str, pages: int, dpi: int) -> None:
    pdf = Pdf()
    pages_obj = pdf.reserve()
    kids = []
    for n in range(1, pages + 1):
        d, data, w, h = encode(kind, n, dpi)
        im = pdf.stream(d, data)
        pw, ph = A4
        content = f"q {pw} 0 0 {ph} 0 0 cm /Im0 Do Q".encode()
        cs = pdf.stream(b"", content)
        pg = pdf.add(f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {pw} {ph}] /Resources << /XObject << /Im0 {im} 0 R >> >> /Contents {cs} 0 R >>".encode())
        kids.append(pg)
    pdf.set(pages_obj, f"<< /Type /Pages /Count {pages} /Kids [{' '.join(f'{k} 0 R' for k in kids)}] >>".encode())
    root = pdf.add(f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode())
    pdf.write(path, root)


def build_text_pdf(path: Path, pages: int) -> None:
    import pymupdf

    doc = pymupdf.open()
    rnd = random.Random(3)
    words = "the board of directors meeting minutes budget reserve assessment owner notice account payment".split()
    for n in range(1, pages + 1):
        pg = doc.new_page(width=A4[0], height=A4[1])
        pg.insert_text((54, 72), f"Example Village HOA   Notice {n}", fontsize=16)
        y = 110
        while y < 780:
            pg.insert_text((54, y), " ".join(rnd.choice(words) for _ in range(rnd.randint(8, 14))), fontsize=10)
            y += 14
    doc.save(str(path), garbage=1, deflate=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scratch")
    ap.add_argument("--hash-mb", type=int, default=100)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    out = Path(a.scratch)
    out.mkdir(parents=True, exist_ok=True)
    jobs = {
        "ccitt100.pdf": lambda p: build_image_pdf(p, "ccitt", 100, 200),
        "jpeg100.pdf": lambda p: build_image_pdf(p, "jpeg", 100, 200),
        "flate100.pdf": lambda p: build_image_pdf(p, "flate", 100, 150),
        "jpx100.pdf": lambda p: build_image_pdf(p, "jpx", 100, 150),
        "ccitt2000.pdf": lambda p: build_image_pdf(p, "ccitt", 2000, 200),
        "text500.pdf": lambda p: build_text_pdf(p, 500),
    }
    for name, fn in jobs.items():
        if a.only and a.only not in name:
            continue
        p = out / name
        if not p.exists():
            fn(p)
        print(f"{name}: {p.stat().st_size / 1e6:.1f} MB")
    big = out / "big.bin"
    if not big.exists() and not a.only:
        with big.open("wb") as f:
            for _ in range(a.hash_mb):
                f.write(os.urandom(1 << 20))
        print(f"big.bin: {a.hash_mb} MB")


if __name__ == "__main__":
    main()
