"""QR codes for the links people meet on paper: a form to answer, a meeting to join, a document to read.

A QR code is a shortcut, never the only way: every code jason prints carries its link as text beside it, for a reader
without a phone camera and for anyone who wants to see where it goes before they go. The defaults keep a code readable
when printed small or photocopied: error correction M (a smudge or a fold does not lose it), a quiet zone of four
modules (the white margin scanners need), and about an inch square on the page.

- ``qr_svg`` and ``qr_png``: a code for a link, as inline SVG (for pages jason prints) or a PNG file (to paste into a
  Doc, a slide, or a poster);
- ``qr_block``: the code with its link and an optional label, as HTML for a printed page;
- ``fill_qr_tokens``: ``{QR:TOKEN}`` in a template becomes the block for the link in ``values[TOKEN]``; a token with no
  link yet prints a visible marker instead, so a draft never hides a missing link.

Only links are encoded (``https://``, ``http://``, ``mailto:``, ``tel:``). A code in an email is pointless (the reader
is already on a screen, and mail clients block inline images); email gets the link.

Needs ``segno`` (``pip install -e ".[qr]"``).
"""

from __future__ import annotations

import html
import re
from pathlib import Path

QR_TOKEN = re.compile(r"\{QR:([A-Z][A-Z0-9_]*)\}")
LINK = re.compile(r"^(?:https?://\S+|mailto:\S+|tel:\+?[\d-]+)$")
ERROR = "m"
BORDER = 4


def _segno():
    try:
        import segno
    except ImportError as exc:  # an optional extra; say what to install
        raise RuntimeError('QR codes need segno: pip install -e ".[qr]"') from exc
    return segno


def is_link(text: str) -> bool:
    return bool(LINK.match((text or "").strip()))


def _code(link: str):
    if not is_link(link):
        raise ValueError(f"not a link to encode: {link!r}")
    return _segno().make(link.strip(), error=ERROR, micro=False)


def qr_svg(link: str, *, title: str = "", dark: str = "#000000", light: str = "#ffffff") -> str:
    """The code as inline SVG that scales to its container (no fixed size; the page sets it)."""
    svg = _code(link).svg_inline(scale=1, border=BORDER, dark=dark, light=light, title=title or None, omitsize=True)
    return svg


def qr_png(link: str, path: Path | str, *, scale: int = 12) -> Path:
    """The code as a PNG file, ``scale`` pixels a module (12 makes about a 400-pixel square for a short link)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _code(link).save(str(path), kind="png", scale=scale, border=BORDER)
    return path


QR_STYLE = """<style>.qr{display:flex;gap:12pt;align-items:center;margin:8pt 0;break-inside:avoid}
.qr .code{width:1in;height:1in;flex:none}.qr .code svg{width:100%;height:100%}
.qr .text{font-size:9.5pt;line-height:1.35}.qr .link{word-break:break-all;font-family:Consolas,monospace}</style>"""


def qr_block(link: str, *, label: str = "") -> str:
    """The code beside its link (and ``label``: "Scan to answer online"), as HTML for a printed page."""
    caption = f"<strong>{html.escape(label)}</strong><br>" if label else ""
    return (f"<div class='qr'><div class='code'>{qr_svg(link, title=label or link)}</div>"
            f"<div class='text'>{caption}<span class='link'>{html.escape(link.strip())}</span></div></div>")


def fill_qr_tokens(text: str, values: dict[str, str], *, labels: dict[str, str] | None = None) -> tuple[str, list[str]]:
    """``{QR:TOKEN}`` replaced by the block for ``values[TOKEN]``, labelled from ``labels``; a token whose value is not a
    link yet becomes a visible marker. Returns the text and the tokens still without a link. The block's style is
    added once, when any code is placed."""
    labels = labels or {}
    missing: list[str] = []

    def place(m: re.Match) -> str:
        token = m.group(1)
        value = (values.get(token) or "").strip()
        if not is_link(value):
            missing.append(token)
            return f"<p><strong>[QR code: {html.escape(token)} has no link yet]</strong></p>"
        return qr_block(value, label=labels.get(token, ""))

    out = QR_TOKEN.sub(place, text)
    if out != text and "class='qr'" in out:
        out = QR_STYLE + out
    return out, missing


def qr_tokens(text: str) -> list[str]:
    """The tokens a template asks QR codes for."""
    return list(dict.fromkeys(QR_TOKEN.findall(text or "")))


__all__ = ["QR_TOKEN", "fill_qr_tokens", "is_link", "qr_block", "qr_png", "qr_svg", "qr_tokens"]
