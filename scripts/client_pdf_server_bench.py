"""The server side of the client-rendering comparison (docs/pdf-splitter-client-side.md): the same made-up PDFs, drawn the way
``jason.tasks.split_thumbs`` draws them (PyMuPDF, or pypdfium2 when installed), at 96 / 200 / 800 px, encoded as WebP, plus a cut
of a page range with pypdf, a SHA-256 of the file, and the pixel difference to a browser picture saved by client_pdf_bench.mjs.

    python scripts/client_pdf_server_bench.py PDF_DIR [--pictures OUT_DIR]

Reads only the made-up files in PDF_DIR. Prints one JSON object.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import statistics
import time
from pathlib import Path

from PIL import Image

SIZES = (96, 200, 800)


def draw(path: Path, n: int, size: int, engine: str) -> Image.Image:
    from jason.tasks import split_thumbs as t

    fn = t._draw_pymupdf if engine == "pymupdf" else t._draw_pypdfium2
    return fn(path, n, size)


def timed(path: Path, pages: list[int], size: int, engine: str) -> dict:
    from jason.tasks import split_thumbs as t

    ms, enc, nbytes = [], [], []
    for n in pages:
        t0 = time.perf_counter()
        img = draw(path, n, size, engine)
        t1 = time.perf_counter()
        data, _mime = t._encode(img, size)
        t2 = time.perf_counter()
        ms.append((t1 - t0) * 1000), enc.append((t2 - t1) * 1000), nbytes.append(len(data))
    return {"renderMed": round(statistics.median(ms), 1), "encodeMed": round(statistics.median(enc), 1),
            "perPage": round(statistics.median(ms) + statistics.median(enc), 1), "bytesMean": round(statistics.mean(nbytes))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_dir")
    ap.add_argument("--pictures", default="")
    ap.add_argument("--engine", default="pymupdf")
    a = ap.parse_args()
    d = Path(a.pdf_dir)
    out: dict = {"engine": a.engine, "runs": {}}
    for name in ("ccitt100", "jpeg100", "flate100", "jpx100", "text500", "ccitt2000"):
        p = d / f"{name}.pdf"
        if not p.exists():
            continue
        pages = list(range(1, 31)) if name != "ccitt2000" else [1, 500, 1000, 1500, 2000]
        t0 = time.perf_counter()
        import pymupdf
        with pymupdf.open(str(p)) as doc:
            npages = doc.page_count
        topen = (time.perf_counter() - t0) * 1000
        out["runs"][name] = {"pages": npages, "openMs": round(topen, 1), **{str(s): timed(p, pages, s, a.engine) for s in SIZES}}
        if a.pictures:
            pic = Path(a.pictures)
            for s in (200, 800):
                b = pic / f"{name}-p1-{s}.png"
                if b.exists():
                    mine = draw(p, 1, s, a.engine).convert("L")
                    theirs = Image.open(b).convert("L")
                    if theirs.size != mine.size:
                        theirs = theirs.resize(mine.size)
                    diff = [abs(x - y) for x, y in zip(mine.getdata(), theirs.getdata())]
                    ink = lambda im: sum(1 for v in im.getdata() if v < 200) / (im.size[0] * im.size[1])
                    out["runs"][name][f"vsBrowser{s}"] = {"meanAbsDiff": round(statistics.mean(diff), 2), "inkServer": round(ink(mine), 4),
                                                          "inkBrowser": round(ink(theirs), 4), "sizeServer": mine.size}
    big = d / "big.bin"
    if big.exists():
        t0 = time.perf_counter()
        h = hashlib.sha256()
        with big.open("rb") as f:
            while chunk := f.read(1 << 20):
                h.update(chunk)
        ms = (time.perf_counter() - t0) * 1000
        out["hash"] = {"mb": round(big.stat().st_size / 1e6), "ms": round(ms), "hex": h.hexdigest()}
    cut = d / "ccitt2000.pdf"
    if cut.exists():
        from pypdf import PdfReader, PdfWriter

        t0 = time.perf_counter()
        r = PdfReader(str(cut))
        w = PdfWriter()
        for i in range(999, 1010):
            w.add_page(r.pages[i])
        buf = io.BytesIO()
        w.write(buf)
        out["pypdfCut11of2000"] = {"ms": round((time.perf_counter() - t0) * 1000), "bytes": len(buf.getvalue())}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
