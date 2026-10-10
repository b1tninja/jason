"""The splitter's page pictures (docs/pdf-splitter.md, section 3): one page of a PDF drawn at 96, 200, or 800 pixels, kept by content.

``render_page(path, page, size)`` is the one function the renderer lives behind. It prefers ``pypdfium2`` (permissive license;
``pip install -e ".[split]"``), else the PyMuPDF already in the tree, else it raises ``RendererUnavailable`` and the caller says so in
words. A renderer is imported when first asked for, never when this module is imported. Only the one page asked for is drawn: the
whole file is never decoded, and nothing here gives a browser the PDF.

The cache is ``<data>/split/thumbs/<sha256[:2]>/<sha256>/<size>/<page>.webp`` (JPEG when the imaging library lacks WebP): addressed
by the file's SHA-256, the page, and the size, so the same bytes anywhere find the same pictures, and a file's name appears nowhere.
It is bounded by the ``split.thumbnail_cache_bytes`` limit: a write that would pass the bound removes the least recently used
pictures first, never the page just drawn; a single file whose own pictures would not fit is refused in the registry's words. The
temp-drive guard (``jason.storage``) speaks first: with the drive short of room the picture is returned once and not kept. A cache
is not a record: it is rebuilt from the file and deleting it loses only speed.

Every picture has an ETag of the hash, the page, the size, and the render version (``etag``), so a browser keeps it and a changed
renderer retires it.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jason import limits, storage

SIZES = (96, 200, 800)                     # the longest side in pixels: the grid at a distance, the album, the compare pane
QUALITY = {96: 55, 200: 65, 800: 75}
SIZE_NAMES = {"tiny": 96, "small": 200, "large": 800}
RENDER_VERSION = "1"                       # bump when the drawing changes: every ETag changes with it
FOLDER = ("split", "thumbs")
NO_RENDERER = ("No page renderer is installed on this machine, so page pictures cannot be drawn. Install one with "
               "pip install -e \".[split]\" (pypdfium2) or the \"pdf\" extra (PyMuPDF), or ask your community's administrator.")


class RendererUnavailable(RuntimeError):
    """Neither pypdfium2 nor PyMuPDF can be imported."""


class PageUnreadable(ValueError):
    """A page that could not be drawn (a damaged page, an encrypted file). The others are unaffected."""


@dataclass(frozen=True)
class Rendered:
    data: bytes
    mime: str
    width: int
    height: int
    renderer: str


def renderer_name() -> str:
    """The renderer render_page would use: ``pypdfium2``, ``pymupdf``, or "" when there is none. Imports it, to be sure."""
    for name in ("pypdfium2", "pymupdf"):
        try:
            __import__(name)
            return name
        except ImportError:
            continue
    return ""


def size_of(value: Any) -> int:
    """96, 200, or 800 from a number or a name (tiny, small, large). Anything else is refused in words."""
    text = str(value).strip().lower()
    n = SIZE_NAMES.get(text)
    if n is None:
        try:
            n = int(text)
        except ValueError:
            n = 0
    if n not in SIZES:
        raise ValueError(f"a page picture is {', '.join(str(s) for s in SIZES)} pixels (tiny, small, large)")
    return n


def webp_available() -> bool:
    try:
        from PIL import features

        return bool(features.check("webp"))
    except Exception:  # noqa: BLE001
        return False


def extension() -> str:
    return "webp" if webp_available() else "jpg"


def _encode(image: Any, size: int) -> tuple[bytes, str]:
    buf = io.BytesIO()
    if webp_available():
        image.save(buf, "WEBP", quality=QUALITY[size], method=4)
        return buf.getvalue(), "image/webp"
    image.convert("RGB").save(buf, "JPEG", quality=QUALITY[size], optimize=True)
    return buf.getvalue(), "image/jpeg"


def _draw_pypdfium2(path: Path, page: int, size: int) -> Any:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        if page < 1 or page > len(pdf):
            raise PageUnreadable(f"page {page} is not in this file")
        pg = pdf[page - 1]
        try:
            w, h = pg.get_size()
            scale = size / max(w, h, 1.0)
            return pg.render(scale=scale, may_draw_forms=False).to_pil().convert("RGB")
        finally:
            pg.close()
    finally:
        pdf.close()


def _draw_pymupdf(path: Path, page: int, size: int) -> Any:
    import pymupdf
    from PIL import Image

    with pymupdf.open(str(path)) as doc:
        if doc.needs_pass:
            raise PageUnreadable("this file is protected with a password")
        if page < 1 or page > doc.page_count:
            raise PageUnreadable(f"page {page} is not in this file")
        pg = doc.load_page(page - 1)
        rect = pg.rect
        scale = size / max(rect.width, rect.height, 1.0)
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False, annots=False)
        mode = "L" if pix.n == 1 else "RGB"
        return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def render_page(path: Path | str, page: int, size: int, *, rotate: int = 0, engine: str = "") -> Rendered:
    """Page ``page`` (1-based) of the PDF at ``path`` as a picture whose longest side is ``size`` pixels. ``rotate`` turns the picture
    (degrees, clockwise) and never the PDF. ``engine`` forces ``pypdfium2`` or ``pymupdf`` (for a test). Raises ``RendererUnavailable``
    when there is none and ``PageUnreadable`` for a page that cannot be drawn."""
    size = size_of(size)
    order = [engine] if engine else ["pypdfium2", "pymupdf"]
    last: Exception | None = None
    for name in order:
        draw = _draw_pypdfium2 if name == "pypdfium2" else _draw_pymupdf
        try:
            image = draw(Path(path), int(page), size)
        except ImportError as exc:
            last = exc
            continue
        except PageUnreadable:
            raise
        except Exception as exc:  # noqa: BLE001 - one page the engine cannot draw is that page's problem
            raise PageUnreadable(f"page {page} could not be drawn ({type(exc).__name__})") from exc
        if rotate % 360:
            image = image.rotate(-(rotate % 360), expand=True)
        if max(image.size) > size:                  # a page whose size rounds up by a pixel
            image.thumbnail((size, size))
        data, mime = _encode(image, size)
        return Rendered(data, mime, image.size[0], image.size[1], name)
    raise RendererUnavailable(NO_RENDERER) from last


# --- the cache -------------------------------------------------------------------------------------------------------------

def etag(sha256: str, page: int, size: int) -> str:
    """The ETag of one picture: the hash, the page, the size, and the render version (quoted, as HTTP wants)."""
    return f'"{sha256[:16]}-{int(page)}-{int(size)}-{RENDER_VERSION}"'


def cache_root(root: Path) -> Path:
    return Path(root).joinpath(*FOLDER)


def folder_of(root: Path, sha256: str) -> Path:
    return cache_root(root) / sha256[:2] / sha256


def path_of(root: Path, sha256: str, page: int, size: int) -> Path:
    return folder_of(root, sha256) / str(size) / f"{int(page)}.{extension()}"


def _files(top: Path):
    stack = [str(top)]
    while stack:
        try:
            with os.scandir(stack.pop()) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            st = entry.stat(follow_symlinks=False)
                            yield Path(entry.path), st.st_size, st.st_mtime_ns
                    except OSError:
                        continue
        except OSError:
            continue


def usage(root: Path) -> int:
    """Bytes the cache holds now."""
    return sum(size for _, size, _ in _files(cache_root(root)))


def _evict(root: Path, need: int, keep: Path, limit_bytes: int, own: str) -> int:
    """Remove the least recently used pictures until ``need`` more bytes fit under ``limit_bytes``; the file just written is never
    removed, and other files' pictures go before this file's own. Returns the bytes freed."""
    rows = [(p, s, m) for p, s, m in _files(cache_root(root)) if p != keep and not p.name.endswith(".tmp")]
    held = sum(s for _, s, _ in rows) + need         # ``need`` is the file just written, which stays
    freed = 0
    mine = f"{os.sep}{own}{os.sep}"
    for p, s, _m in sorted(rows, key=lambda r: (mine in str(r[0]), r[2])):
        if held - freed <= limit_bytes:
            break
        try:
            p.unlink()
            freed += s
        except OSError:
            continue
    return freed


def store(root: Path, sha256: str, page: int, size: int, rendered: Rendered, *, community: Any = None) -> tuple[Path | None, str]:
    """Keep a drawn picture. Returns (its path, "") when kept, or (None, why) when the drive is short of room (the picture is then
    served once and not kept). Raises ``LimitReached`` when this picture alone cannot fit under the allowance."""
    bound = int(limits.value("split.thumbnail_cache_bytes", community=community))
    if len(rendered.data) > bound:
        raise limits.refusal("split.thumbnail_cache_bytes", len(rendered.data), bound)
    target = path_of(root, sha256, page, size)
    if target.is_file():
        return target, ""
    why = storage.room_problem(Path(root), len(rendered.data))
    if why:
        return None, why
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    tmp.write_bytes(rendered.data)
    os.replace(tmp, target)
    if usage(root) > bound:
        _evict(root, len(rendered.data), target, bound, sha256)
    return target, ""


def get(root: Path, source: Path | str, sha256: str, page: int, size: int, *, rotate: int = 0, community: Any = None) -> dict[str, Any]:
    """One picture: from the cache when it is there, else drawn now and kept. Returns ``{"data", "mime", "etag", "cached", "kept",
    "note"}``. A cached picture is touched so it is the last to go."""
    size = size_of(size)
    hit = path_of(root, sha256, page, size)
    if hit.is_file():
        try:
            os.utime(hit, None)
            data = hit.read_bytes()
            mime = "image/webp" if hit.suffix == ".webp" else "image/jpeg"
            return {"data": data, "mime": mime, "etag": etag(sha256, page, size), "cached": True, "kept": True, "note": ""}
        except OSError:
            pass
    drawn = render_page(source, page, size, rotate=rotate)
    path, why = store(root, sha256, page, size, drawn, community=community)
    return {"data": drawn.data, "mime": drawn.mime, "etag": etag(sha256, page, size), "cached": False, "kept": path is not None,
            "note": why}


def purge(root: Path, sha256: str = "") -> int:
    """Remove the pictures made for one file (or all of them). Never an original. Returns the bytes freed."""
    import shutil

    target = folder_of(root, sha256) if sha256 else cache_root(root)
    freed = usage(root) if not sha256 else sum(s for _, s, _ in _files(target))
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    return freed
