"""What a PDF carries besides its page text: attached files, embedded images, a filled form's answers, and risks.

``jason.community.pdf_preflight`` calls this for each file. Everything is read by PyMuPDF's parser and written as bytes;
nothing is opened with another program or run:

- **Attachments.** The document's EmbeddedFiles (which holds a PDF portfolio's files too) and the FileAttachment
  annotations on pages. An email exported to PDF, or a packet with its spreadsheet attached, often carries the original
  file. Each is a child document of the PDF: its record names the parent (the PDF's sha256), the page it hangs on (None
  for the document), and its depth (1), the shape the segmentation stack uses for a nested document. A copy is saved as
  ``<sha256>.<ext>`` with an extension only from ``SAFE_EXTENSIONS`` (else ``.bin``), never under its own name, and a file
  already saved (the same sha256) is skipped. Name, size, type, and sha256 are recorded.
- **Images.** A page that is one full-page raster is a *scan* (read by ``pdf_preflight``). A smaller image is *media* of
  the page, with its box: a photograph, a plan, a signature (saved), or a *decoration* (a logo or a rule: listed, never
  read as text, never saved).
- **Form answers.** The values of an AcroForm's fields are data, not OCR.
- **Risks.** JavaScript, launch and submit actions, and open actions are flagged, never run. An encrypted file is
  reported (locked, or open but with limits on copying), never cracked.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

SAFE_EXTENSIONS = frozenset({
    "pdf", "txt", "csv", "tsv", "json", "xml", "htm", "html", "eml", "msg", "rtf", "md",
    "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp",
    "png", "jpg", "jpeg", "gif", "tif", "tiff", "bmp", "webp", "jp2", "jpx", "zip",
})
FULL_PAGE = 0.85          # an image covering this much of the page is the page: a scan
DECORATION_COVER = 0.015  # ... one covering less than this share of the page, or narrower than ...
DECORATION_PIXELS = 64    # ... this many pixels, is a logo, a rule, or a bullet
SAVE_PIXELS = 200         # a media image must be this many pixels on each side to be saved


class MediaKind(Enum):
    ATTACHMENT = "attachment"
    SCAN = "scan"                 # one full-page raster
    IMAGE = "image"               # a photograph, plan, or signature on a page
    DECORATION = "decoration"     # a logo or a rule: listed, not read


@dataclass
class Media:
    """One thing a PDF carries. ``parent`` is the PDF's sha256; ``depth`` 1 for a child of the file."""

    kind: MediaKind
    parent: str
    page: int | None              # from 0; None for the document's own attachments
    depth: int = 1
    name: str = ""                # the attachment's own name, or the image's resource name
    size: int = 0
    mime: str = ""
    sha256: str = ""
    bbox: tuple[float, float, float, float] | None = None
    width: int = 0
    height: int = 0
    dpi: int = 0                  # an image's pixels per inch as placed
    saved: str = ""               # the saved copy, relative to the media folder; empty when not saved
    note: str = ""

    def row(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d


@dataclass
class FormValue:
    page: int
    name: str
    type: str
    value: str


@dataclass
class Carried:
    media: list[Media] = field(default_factory=list)
    fields: list[FormValue] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)       # "javascript", "launch action", "submit-form action", "open action"
    locked: bool = False                                  # needs a password: nothing was read
    restrictions: tuple[str, ...] = ()                    # what an open file does not permit: "copy", "print", ...

    def row(self) -> dict[str, Any]:
        return {"media": [m.row() for m in self.media], "fields": [asdict(f) for f in self.fields], "flags": self.flags,
                "locked": self.locked, "restrictions": list(self.restrictions)}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


_BY_EXTENSION = {".csv": "text/csv", ".txt": "text/plain", ".eml": "message/rfc822", ".json": "application/json"}
_MAGIC = ((b"%PDF", "application/pdf"), (b"\x89PNG", "image/png"), (b"\xff\xd8\xff", "image/jpeg"), (b"GIF8", "image/gif"),
          (b"PK\x03\x04", "application/zip"), (b"\xd0\xcf\x11\xe0", "application/x-ole-storage"),
          (b"II*\x00", "image/tiff"), (b"MM\x00*", "image/tiff"), (b"{\\rtf", "application/rtf"))


def sniff_mime(name: str, data: bytes) -> str:
    """A type from the bytes' first signature, else from the name's extension; empty when neither says."""
    ext = Path(name).suffix.lower()
    if ext in _BY_EXTENSION:
        return _BY_EXTENSION[ext]
    for sig, mime in _MAGIC:
        if data.startswith(sig):
            if mime == "application/zip":                       # Office files are zips
                guess = mimetypes.guess_type(name)[0] or ""
                return guess if "officedocument" in guess or "opendocument" in guess else mime
            return mime
    return mimetypes.guess_type(name)[0] or ""


def safe_name(sha: str, name: str) -> str:
    """The saved file's name: the sha256, with the original extension only if it is a document or image type."""
    ext = Path(name).suffix.lower().lstrip(".")
    return f"{sha}.{ext}" if ext in SAFE_EXTENSIONS else f"{sha}.bin"


# --- attachments ----------------------------------------------------------------------------------------------------


def attachments(doc: Any, parent: str) -> list[tuple[Media, bytes]]:
    """Every attached file: the EmbeddedFiles tree, then each page's FileAttachment annotations. Bytes are returned with
    the record so the caller can save them; nothing is opened or run."""
    out: list[tuple[Media, bytes]] = []
    try:
        names = list(doc.embfile_names())
    except Exception:  # noqa: BLE001 - a file whose name tree is damaged has none to list
        names = []
    for n in names:
        try:
            info = doc.embfile_info(n)
            data = bytes(doc.embfile_get(n))
        except Exception:  # noqa: BLE001
            continue
        name = info.get("filename") or info.get("ufilename") or n
        out.append((Media(MediaKind.ATTACHMENT, parent, None, 1, name, len(data), sniff_mime(name, data),
                          sha256_bytes(data), note=(info.get("desc") or "")[:200]), data))
    for page in doc:
        try:
            annots = list(page.annots() or [])
        except Exception:  # noqa: BLE001
            continue
        for annot in annots:
            if annot.type[0] != 17:                              # PDF_ANNOT_FILE_ATTACHMENT
                continue
            try:
                info = annot.file_info
                data = bytes(annot.get_file())
            except Exception:  # noqa: BLE001
                continue
            name = info.get("filename") or info.get("name") or "attachment"
            r = annot.rect
            out.append((Media(MediaKind.ATTACHMENT, parent, page.number, 1, name, len(data), sniff_mime(name, data),
                              sha256_bytes(data), (r.x0, r.y0, r.x1, r.y1), note=(info.get("description") or "")[:200]), data))
    return out


# --- images ---------------------------------------------------------------------------------------------------------


def images(doc: Any, parent: str) -> list[Media]:
    """Each page's images as media records: the full-page raster (a scan), photographs and plans, and decorations.
    No bytes are read here."""
    out = []
    for page in doc:
        area = float(page.rect.width * page.rect.height) or 1.0
        width_in = float(page.rect.width) / 72 or 1.0
        try:
            infos = page.get_image_info(xrefs=True)
            names = {i[0]: i[7] for i in page.get_images(full=True)}
        except Exception:  # noqa: BLE001
            continue
        for info in infos:
            x0, y0, x1, y1 = info["bbox"]
            w, h = int(info["width"]), int(info["height"])
            cover = min(1.0, (x1 - x0) * (y1 - y0) / area)
            shown_in = (x1 - x0) / 72 if x1 > x0 else width_in
            if cover >= FULL_PAGE:
                kind = MediaKind.SCAN
            elif cover < DECORATION_COVER or min(w, h) < DECORATION_PIXELS:
                kind = MediaKind.DECORATION
            else:
                kind = MediaKind.IMAGE
            out.append(Media(kind, parent, page.number, 1, names.get(info.get("xref"), ""), 0, "",
                             "", (x0, y0, x1, y1), w, h, int(round(w / shown_in)), note=f"xref {info.get('xref')}"))
    return out


def image_bytes(doc: Any, xref: int) -> tuple[bytes, str]:
    """An embedded image's own bytes and extension (PyMuPDF's ``extract_image``): the encoded data as stored, not a
    re-rendering."""
    got = doc.extract_image(xref)
    return (bytes(got["image"]), got["ext"]) if got else (b"", "")


# --- forms, actions, encryption -------------------------------------------------------------------------------------

_ACTIONS = (("javascript", re.compile(r"/JavaScript\b|/JS\b")), ("launch action", re.compile(r"/Launch\b")),
            ("submit-form action", re.compile(r"/SubmitForm\b")), ("open action", re.compile(r"/OpenAction\b")),
            ("rich media", re.compile(r"/RichMedia\b|/Movie\b|/Sound\b|/3D\b")))


def form_values(doc: Any) -> list[FormValue]:
    """The answers on a filled AcroForm: its fields' names, types, and values. They are data, not OCR."""
    out = []
    for page in doc:
        try:
            widgets = list(page.widgets() or [])
        except Exception:  # noqa: BLE001
            continue
        for w in widgets:
            value = w.field_value
            if value in (None, "", "Off"):
                continue
            out.append(FormValue(page.number, w.field_name or "", w.field_type_string, str(value)))
    return out


def risks(doc: Any) -> list[str]:
    """Actions in the file that a viewer might run, read from the objects' dictionaries and never run."""
    found: set[str] = set()
    try:
        total = doc.xref_length()
    except Exception:  # noqa: BLE001
        return []
    for xref in range(1, total):
        try:
            obj = doc.xref_object(xref, compressed=False)
        except Exception:  # noqa: BLE001
            continue
        if obj.startswith("<<") or obj.lstrip().startswith("<<"):
            for label, pattern in _ACTIONS:
                if label not in found and pattern.search(obj):
                    found.add(label)
    return sorted(found)


def restrictions(doc: Any) -> tuple[str, ...]:
    """What an open, encrypted file does not permit (PyMuPDF's permission bits); empty for a file with no limits."""
    import pymupdf

    if not (doc.is_encrypted or (doc.metadata or {}).get("encryption")):
        return ()
    perms = doc.permissions
    out = []
    for label, bit in (("print", pymupdf.PDF_PERM_PRINT), ("modify", pymupdf.PDF_PERM_MODIFY), ("copy", pymupdf.PDF_PERM_COPY),
                       ("annotate", pymupdf.PDF_PERM_ANNOTATE)):
        if not perms & bit:
            out.append(label)
    return tuple(out)


def carried(doc: Any, parent: str) -> tuple[Carried, list[tuple[Media, bytes]]]:
    """Everything the PDF carries, and the attachments' bytes (for ``save``)."""
    found = Carried(restrictions=restrictions(doc))
    files = attachments(doc, parent)
    found.media = [m for m, _ in files] + images(doc, parent)
    found.fields = form_values(doc)
    found.flags = risks(doc)
    return found, files


def save(folder: Path, found: Carried, files: list[tuple[Media, bytes]], doc: Any, *, photos: bool = True) -> list[Path]:
    """Write the attachments, and the photographs and plans, under ``folder`` as ``<sha256>.<ext>`` (never under their own
    names, with an extension only from ``SAFE_EXTENSIONS``), skipping a file already saved. Returns the paths written."""
    folder.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    seen = {p.name.split(".")[0] for p in folder.iterdir() if p.is_file()}
    for media, data in files:
        target = safe_name(media.sha256, media.name)
        if media.sha256 in seen:
            media.note = (media.note + " duplicate").strip()
            media.saved = target
            continue
        (folder / target).write_bytes(data)
        media.saved = target
        seen.add(media.sha256)
        written.append(folder / target)
    if photos:
        for media in found.media:
            if media.kind is not MediaKind.IMAGE or min(media.width, media.height) < SAVE_PIXELS:
                continue
            m = re.search(r"xref (\d+)", media.note)
            if not m:
                continue
            data, ext = image_bytes(doc, int(m.group(1)))
            if not data:
                continue
            media.size, media.sha256 = len(data), sha256_bytes(data)
            media.mime = mimetypes.guess_type(f"x.{ext}")[0] or ""
            target = safe_name(media.sha256, f"x.{ext}")
            media.saved = target
            if media.sha256 in seen:
                media.note += " duplicate"
                continue
            (folder / target).write_bytes(data)
            seen.add(media.sha256)
            written.append(folder / target)
    (folder / "media.json").write_text(json.dumps(found.row(), indent=1), encoding="utf-8")
    return written
