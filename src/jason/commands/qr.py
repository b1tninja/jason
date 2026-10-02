"""``jason qr LINK``: a QR code for a link, to paste into a Doc, a slide, a poster, or a posted meeting notice.

``jason qr https://... --out data/qr/meeting.png`` writes a PNG (``--scale`` pixels a module) or, for an ``.svg`` path,
an SVG; without ``--out`` it writes ``data/qr/<the link's host and path>.png``. jason's own printed letters place codes
themselves with ``{QR:TOKEN}`` (``jason.community.qr``). Print the link beside the code: not everyone can scan one.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Callable


def cmd_qr(args: argparse.Namespace) -> int:
    from jason.community.qr import is_link, qr_png, qr_svg
    from jason.config import Settings

    if not is_link(args.link):
        print(f"not a link: {args.link} (give https://..., mailto:..., or tel:...)", file=sys.stderr)
        return 2
    if args.out:
        out = Path(args.out)
    else:
        name = re.sub(r"[^a-z0-9]+", "-", re.sub(r"^\w+:/*", "", args.link.casefold())).strip("-")[:60] or "qr"
        out = Settings.load(args.env).payhoa_catalog.parent / "qr" / f"{name}.png"
    if out.suffix.lower() == ".svg":
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(qr_svg(args.link), encoding="utf-8")
    else:
        qr_png(args.link, out, scale=args.scale)
    print(f"{out}  (print the link beside it: {args.link})")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("qr", help="A QR code for a link (PNG or SVG), to paste into a Doc, slide, or posted notice")
    add_common(p)
    p.add_argument("link", help="the link: https://..., mailto:..., or tel:...")
    p.add_argument("--out", help="the file to write (.png or .svg; default data/qr/<link>.png)")
    p.add_argument("--scale", type=int, default=12, help="PNG pixels a module (default 12)")
    p.set_defaults(func=cmd_qr)
