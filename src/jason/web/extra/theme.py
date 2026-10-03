"""The theme source: the active profile's brand tokens for the console and its public owner page.

``theme(args)`` reads ``Community.theme()`` and answers the CSS custom properties by scheme (``light``, ``dark``), the
public page's surface layer (``surface``, ``surfaceDark``), the wordmark, and the font stylesheet the page may load.
A profile without a theme answers ``found: false`` with empty token maps: the console then keeps jason's neutral look.
The theme is profile data; this module names no color, font, or association. It only reads; ``write`` refuses.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]

NEUTRAL_WORDMARK = "jason"


def theme(args: Args) -> dict[str, Any]:
    from jason.community import community

    c = community()
    t = c.theme()
    slug = str(c.slug or "")
    if t is None:
        return {"found": False, "slug": slug, "wordmark": NEUTRAL_WORDMARK, "light": {}, "dark": {}, "surface": {}, "surfaceDark": {},
                "fontUrl": "", "note": "the profile sets no theme; the console keeps jason's neutral look"}
    return {
        "found": True,
        "slug": slug,
        "wordmark": t.wordmark or c.name,
        "light": t.tokens("light"),
        "dark": t.tokens("dark"),
        "surface": dict(t.surface or {}),
        "surfaceDark": dict(t.surface_dark or {}),
        "fontUrl": t.font_url or "",
    }


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    raise ValueError("the theme is profile data (the profile's theme.py); it is not written from the console")
