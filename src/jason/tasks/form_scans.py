"""Test scans of a filled form, and the form reader scored against what was filled in.

``simulate`` turns a filled fillable PDF into what a home scanner or a phone gives back: the fields flattened onto the
page, each page rendered as an image, turned a little, scaled and shifted, speckled, and saved as an image-only PDF (no
text layer). ``score`` reads it back with ``form_reader.read_scan`` and compares each field with the values filled in.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jason.community.forms import FormTemplate, QuestionKind, option_key


def simulate(filled_pdf: Path, out: Path, *, dpi: int = 150, angle: float = 1.2, scale: float = 0.97,
             shift: tuple[int, int] = (18, -12), noise: float = 0.01, seed: int = 7, blur: float = 0.0, jpeg: int = 0,
             gamma: float = 1.0) -> Path:
    """A scan of ``filled_pdf``: flattened, rendered at ``dpi``, turned ``angle`` degrees (180 more for a page fed upside
    down), scaled and shifted, with ``noise`` (a share of pixels flipped), ``blur`` (a Gaussian radius in pixels),
    ``gamma`` (above 1 lighter, below darker: a faint or a dark copy), and JPEG at quality ``jpeg`` (0 for none),
    written to ``out`` as an image-only PDF."""
    import io
    import tempfile

    import pymupdf
    from PIL import Image, ImageFilter

    from jason.community.pdf_fields import flatten

    rng = random.Random(seed)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        flat = flatten(filled_pdf, Path(tmp) / "flat.pdf")
        images = []
        with pymupdf.open(flat) as doc:
            for page in doc:
                pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
                image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
                w, h = image.size
                image = image.resize((int(w * scale), int(h * scale)))
                canvas = Image.new("L", (w, h), 255)
                canvas.paste(image, ((w - image.width) // 2 + shift[0], (h - image.height) // 2 + shift[1]))
                canvas = canvas.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
                if blur:
                    canvas = canvas.filter(ImageFilter.GaussianBlur(blur))
                if gamma != 1.0:
                    canvas = canvas.point(lambda v: int(255 * (v / 255) ** (1 / gamma)))
                pixels = canvas.load()
                for _ in range(int(w * h * noise)):
                    x, y = rng.randrange(w), rng.randrange(h)
                    pixels[x, y] = 0 if pixels[x, y] > 128 else 255
                if jpeg:
                    buffer = io.BytesIO()
                    canvas.save(buffer, "JPEG", quality=jpeg)
                    canvas = Image.open(buffer).convert("L")
                images.append(canvas.convert("RGB"))
        images[0].save(out, "PDF", resolution=dpi, save_all=True, append_images=images[1:])
    return out


@dataclass
class Score:
    right: list[str] = field(default_factory=list)
    wrong: list[tuple[str, Any, Any]] = field(default_factory=list)       # (field, filled, read)

    @property
    def share(self) -> float:
        total = len(self.right) + len(self.wrong)
        return len(self.right) / total if total else 0.0


def _same(a: Any, b: Any) -> bool:
    import re

    def norm(v: Any) -> str:
        return re.sub(r"[^a-z0-9@]+", " ", str(v or "").casefold()).strip()

    return norm(a) == norm(b)


def score(filled: dict[str, Any], reading: Any, form: FormTemplate) -> Score:
    """Each field filled in against what the reader read, by field name; a box left empty counts too."""
    out = Score()
    for q in form.questions:
        if q.kind is QuestionKind.CHECKBOX:
            for o in q.options:
                name = f"{q.field}.{option_key(o)}"
                want, got = bool(filled.get(name)), bool((reading.fields.get(name) or _Empty).value)
                (out.right.append(name) if want == got else out.wrong.append((name, want, got)))
            continue
        want = filled.get(q.field) or ""
        got = (reading.fields.get(q.field) or _Empty).value or ""
        if q.kind is QuestionKind.CHOICE:
            want = option_key(want) if want else ""
        if _same(want, got):
            out.right.append(q.field)
        else:
            out.wrong.append((q.field, want, got))
    return out


class _Empty:
    value = None


__all__ = ["Score", "score", "simulate"]
