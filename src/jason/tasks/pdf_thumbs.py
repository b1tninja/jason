"""A thumbnail of a PDF's first page, rendered from disk and kept, for a screen that shows a recorded copy beside its row.

docs/console/documents.md ("Statutes and the association's documents"). The console shows a recorded instrument (a
governing document's recorded PDF, a packet file kept under the data folder) as a sheet of paper: page 1 rendered with
PyMuPDF to a PNG about ``WIDTH`` pixels wide. It reads the file on disk only, never Google, PayHOA, or the county, so a
screen may ask for it on load (``GET /api/thumb?path=``, ``jason.web.previews``).

**The cache.** ``data/thumbs/<sha256 of the path>.png``, the path being the PDF's place under the data folder (posix).
The PNG's modified time is set to the PDF's, so a PDF replaced or touched since is rendered again; the same PDF is read
once. Each PNG is written to a temporary name and then replaced, so a reader never sees half of one.

A PDF that cannot be opened (damaged, encrypted, no pages) has no thumbnail: ``None``, never an error.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

THUMBS = Path("thumbs")
WIDTH = 300                                    # the thumbnail's width in pixels
MAX_SCALE = 4.0                                # a tiny page is not blown up past this


def cache_path(root: Path, rel: str) -> Path:
    """Where the thumbnail of the PDF at ``rel`` (its posix path under ``root``) is kept."""
    digest = hashlib.sha256(str(rel).replace("\\", "/").encode("utf-8")).hexdigest()
    return Path(root) / THUMBS / f"{digest}.png"


def render(pdf: Path, width: int = WIDTH) -> bytes | None:
    """Page 1 of ``pdf`` as PNG bytes about ``width`` pixels wide, or None when the file cannot be rendered."""
    try:
        import pymupdf
    except ImportError:                        # PyMuPDF is a dependency; a checkout without it shows no thumbnail
        return None
    try:
        with pymupdf.open(pdf) as doc:
            if doc.needs_pass or doc.page_count < 1:
                return None
            page = doc.load_page(0)
            scale = min(MAX_SCALE, width / max(1.0, page.rect.width))
            pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
            return pix.tobytes("png")
    except Exception:  # noqa: BLE001 - a PDF PyMuPDF cannot read has no thumbnail; it is still a document
        return None


def _fresh(png: Path, mtime_ns: int) -> bool:
    try:
        return png.is_file() and png.stat().st_mtime_ns == mtime_ns
    except OSError:
        return False


def thumbnail(root: Path, rel: str, *, width: int = WIDTH) -> Path | None:
    """The kept thumbnail of the PDF at ``rel`` under ``root``, rendered now when there is none or the PDF changed
    since (its modified time differs from the PNG's); None when the file is not a PDF on disk or cannot be rendered."""
    pdf = Path(root) / rel
    try:
        stat = pdf.stat()
    except OSError:
        return None
    if pdf.suffix.lower() != ".pdf" or not pdf.is_file():
        return None
    png = cache_path(root, rel)
    if _fresh(png, stat.st_mtime_ns):
        return png
    data = render(pdf, width)
    if data is None:
        return None
    png.parent.mkdir(parents=True, exist_ok=True)
    tmp = png.with_name(f"{png.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.utime(tmp, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    os.replace(tmp, png)
    return png


__all__ = ["THUMBS", "WIDTH", "cache_path", "render", "thumbnail"]
