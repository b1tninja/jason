"""QR codes read off a document: the other half of ``jason.community.qr`` (which makes them).

A report, invoice, or notice often prints a QR code that points at the real record: a vendor's online report, a payment
page, a permit, a form. The text layer never holds it, so ingestion reads it from the page image and keeps what it
decodes as metadata beside the file's text.

- ``read_codes(path)``: every QR or Micro QR code on a PDF's pages or in an image, as ``Code`` rows, one per distinct
  payload, with the first page it appeared on;
- ``Code.link`` and ``Code.host``: whether the payload is a link, and where it goes.

A decoded payload is evidence of what the paper points at, never a fact about the document, and jason does not open it:
a link is followed only by a person who has looked at where it goes. Only QR formats are read; a text-heavy page
produces false hits from one-dimensional barcodes.

Needs ``zxing-cpp`` and ``pymupdf`` for PDFs (``pip install -e ".[qr]"``); without the decoder every file reads as no
codes and ``available()`` says why.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from jason.community.qr import is_link

DPI = 150
MAX_PAGES = 40
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp")
INSTALL = 'QR codes are read with zxing-cpp: pip install -e ".[qr]"'


SECRET = re.compile(r"((?:^|[?&#])(?:pwd|passcode|password|pass|token|key|secret|sig|signature|code|auth)=)[^&#\s]*", re.I)


def redacted(text: str) -> str:
    """A payload with the values of secret-looking query parameters (a Zoom meeting's ``pwd``, a token) masked: for the
    reports and pages people read. The kept metadata holds the payload whole, under ``data/``."""
    return SECRET.sub(lambda m: m.group(1) + "***", text or "")


@dataclass(frozen=True)
class Code:
    text: str
    format: str = "QR Code"
    page: int = 1                      # 1-based; an image is page 1

    @property
    def link(self) -> bool:
        return is_link(self.text)

    @property
    def host(self) -> str:
        return (urlparse(self.text).hostname or "") if self.link and self.text.lower().startswith("http") else ""

    @property
    def portal(self) -> dict[str, str]:
        """The vendor portal the link names (``portal_links.identify``), or empty."""
        from jason.community.portal_links import identify

        found = identify(self.text) if self.link else None
        return found.as_dict() if found else {}

    @property
    def meeting(self) -> dict[str, str]:
        """The video meeting the link joins (``portal_links.identify_meeting``), or empty."""
        from jason.community.portal_links import identify_meeting

        found = identify_meeting(self.text) if self.link else None
        return found.as_dict() if found else {}

    def as_dict(self) -> dict:
        return {"text": self.text, "format": self.format, "page": self.page, "link": self.link, "host": self.host,
                "portal": self.portal, "meeting": self.meeting}


def _zxing():
    try:
        import zxingcpp
    except ImportError:
        return None
    return zxingcpp


def available() -> str:
    """"" when codes can be read, else what to install."""
    return "" if _zxing() else INSTALL


def _formats(zx):
    return [zx.BarcodeFormat.QRCode, zx.BarcodeFormat.MicroQRCode]


def _decode(zx, image, page: int) -> list[Code]:
    found = []
    for barcode in zx.read_barcodes(image, formats=_formats(zx)):
        text = (barcode.text or "").strip()
        if text:
            found.append(Code(text, str(barcode.format).rsplit(".", 1)[-1] or "QR Code", page))
    return found


def read_codes(path: Path | str, *, max_pages: int = MAX_PAGES, dpi: int = DPI) -> list[Code]:
    """The distinct QR payloads in a PDF or an image, in page order. A file that cannot be read, or a missing decoder,
    gives none."""
    zx = _zxing()
    path = Path(path)
    if zx is None or not path.is_file():
        return []
    from PIL import Image

    found: list[Code] = []
    try:
        if path.suffix.lower() == ".pdf":
            import pymupdf

            with pymupdf.open(path) as document:
                for index in range(min(document.page_count, max_pages)):
                    pixmap = document[index].get_pixmap(dpi=dpi)
                    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
                    found += _decode(zx, image, index + 1)
        elif path.suffix.lower() in IMAGE_SUFFIXES:
            with Image.open(path) as image:
                found += _decode(zx, image.convert("RGB"), 1)
    except Exception:  # noqa: BLE001 - a damaged file has no codes to read; the text reader reports the damage
        return found
    seen: set[str] = set()
    return [c for c in found if not (c.text in seen or seen.add(c.text))]


__all__ = ["Code", "available", "read_codes", "redacted"]
