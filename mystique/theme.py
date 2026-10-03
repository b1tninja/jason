"""The association's brand for the console and its public owner page: one ``Theme`` row.

The console reads it through ``Community.theme()`` and ``GET /api/theme`` and applies it on ``[data-community="mystique"]``:
jason's data views take the brand layer only (accent, the text on it, the brand font); the public owner page opts into
the surface layer with ``data-reach="full"``. The values are the design handoff's ``themes/mystique.css`` (October 3,
2026). Dark-scheme overrides carry the same keys; the accent is lighter there, so the text on it is near-black.
"""

from __future__ import annotations

from jason.community.base import Theme

THEME: Theme | None = Theme(
    wordmark="Mystique",
    accent="#5b3f8f",
    on_accent="#fff",
    accent_2="#e0b973",
    on_accent_2="#2a2038",
    brand_font='"Gloock", Georgia, "Times New Roman", serif',
    brand_weight=400,
    brand_case="uppercase",
    brand_tracking=".2em",
    hero="#2a2038",
    hero_ink="#f4eff7",
    hero_muted="#c9bfd4",
    hero_line="#4a3d5c",
    font_url="https://fonts.googleapis.com/css2?family=Gloock&display=swap",
    dark={"accent": "#bba3ee", "on_accent": "#1e1726", "hero": "#251d31", "hero_muted": "#c3b8cf", "hero_line": "#43375a"},
    # The public page's surface: a warm paper, rounder cards (14px) and hero (22px), pill buttons.
    surface={"bg": "#f6f3ee", "panel": "#fffdfa", "ink": "#211a2a", "muted": "#655c70", "line": "#e5dee2",
             "good": "#2c7a4c", "warn": "#8f5f00", "bad": "#ad3326", "radius": "14px", "radius-lg": "22px"},
    surface_dark={"bg": "#15111b", "panel": "#1e1926", "ink": "#eee8f2", "muted": "#a79db3", "line": "#322a3c",
                  "good": "#6fd09a", "warn": "#e6b955", "bad": "#ff8f84"},
)
"""The brand. ``None`` would give the console jason's neutral look."""
