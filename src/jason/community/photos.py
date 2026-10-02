"""The rule that names an album jason keeps for photos a person picked, and the text each photo carries.

An album is named from the agenda item that linked the person's shared album: the prefix, the latest meeting date, the
item (and sub-item), then the likely incident's first address and its claim numbers when there is one. An album no
agenda links is named by the prefix, the unlabeled word, and the day it was picked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Google Photos caps an album title at 500 characters and a media item's description at 1000.
TITLE_LIMIT = 500
DESCRIPTION_LIMIT = 1000


@dataclass(frozen=True)
class AlbumNameRule:
    prefix: str
    unlabeled: str = "unlabeled"
    claim_word: str = "claim"

    def title(self, labels: list[dict[str, Any]], incidents: list[dict[str, Any]], *, picked: str = "") -> str:
        """``{prefix} {date} {item}[ / {subitem}][, {address}][, claim {n}, {m}]``, or the unlabeled title."""
        if not labels:
            return " ".join(p for p in (self.prefix, self.unlabeled, picked[:10]) if p)[:TITLE_LIMIT]
        first = labels[0]
        item = first.get("item") or ""
        if first.get("subitem"):
            item = f"{item} / {first['subitem']}"
        parts = [" ".join(p for p in (self.prefix, first.get("date") or "", item) if p)]
        likely = next((e for e in incidents if e.get("likely")), None)
        if likely:
            if likely.get("addresses"):
                parts.append(str(likely["addresses"][0]))
            if likely.get("claims"):
                parts.append(f"{self.claim_word} " + ", ".join(str(c) for c in likely["claims"]))
        return ", ".join(parts)[:TITLE_LIMIT]

    def description(self, labels: list[dict[str, Any]]) -> str:
        """Each agenda use of the album, newest first: ``{date} {item} / {subitem}``; the unlabeled word when none."""
        if not labels:
            return self.unlabeled
        uses = [f"{l.get('date') or ''} {l.get('item') or ''}".strip() + (f" / {l['subitem']}" if l.get("subitem") else "")
                for l in labels]
        return "; ".join(uses)[:DESCRIPTION_LIMIT]


__all__ = ["AlbumNameRule", "DESCRIPTION_LIMIT", "TITLE_LIMIT"]
