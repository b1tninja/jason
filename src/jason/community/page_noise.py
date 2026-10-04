"""Lines and pages in a document's text that are not its words: e-signature audit pages, page numbers, and running
headers and footers.

A contract signed through an e-signature service carries the service's audit trail after the last page (DocuSign's
"Certificate Of Completion", Adobe Acrobat Sign's "Final Audit Report", Dropbox Sign's "Audit trail"); a PDF's text
repeats its letterhead or footer on every page and prints "Page 2 of 4". A reader of terms that takes those as sentences
reads an envelope id as a clause and a footer as part of a duty.

``strip_noise(text)`` drops them and says what it dropped. It removes only whole lines and whole audit pages, never part
of a line: a footer run into the middle of a sentence is left where it is. Form feeds stay, so a page can still be
found by counting them, and the first copy of a repeated line stays, so a letterhead or a license line survives once.
Pure: no network, no store.
"""

from __future__ import annotations

import re
from typing import Any

# The heading that opens an e-signature service's audit page, and the words that confirm it is one.
_AUDIT_HEADING = re.compile(r"^\s*(?:certificate\s+of\s+completion|final\s+audit\s+report|audit\s+trail)\b", re.I)
_AUDIT_MARKERS = re.compile(r"envelope\s*id|transaction\s+id|signer\s+events|document\s+history|status:\s*(?:signed|completed)|"
                            r"certificate\s+pages|e-?signed\s+by|document\s+(?:created|emailed|viewed)\s+by|time\s+source", re.I)
# A line that is only a page number: "Page 2 of 4", "Page 3", "2 of 4", "2/4", "- 2 -".
_PAGE_NUMBER = re.compile(r"^\s*(?:page\s+\d+(?:\s*(?:of|/)\s*\d+)?|\d+\s*(?:of|/)\s*\d+|-\s*\d+\s*-)\s*\.?\s*$", re.I)
# A line that states a term is never treated as a running header, however often it repeats.
_TERM_WORDS = re.compile(r"\b(?:shall|must|will|may|agrees?|warrants?|responsible|liable)\b", re.I)

REPEAT_MIN = 3          # a line repeated at least this often (or on at least this many pages) is a running line
REPEAT_MAX_CHARS = 160  # longer lines are text, not headers
REPEAT_MIN_CHARS = 8    # shorter lines are bullets, initials, and blanks


def _audit_start(lines: list[str]) -> int | None:
    """The index of the line that opens an audit page (with the title line just above it, when there is one), or
    None. The heading counts only when audit markers follow it."""
    for i, line in enumerate(lines):
        if _AUDIT_HEADING.match(line) and _AUDIT_MARKERS.search("\n".join(lines[i:i + 40])):
            above = lines[i - 1].strip() if i else ""
            if above and len(above) < 100 and not above.endswith((".", ";", ":")):
                return i - 1
            return i
    return None


def _key(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip()).lower()


def strip_noise(text: str) -> tuple[str, list[dict[str, Any]]]:
    """``text`` without e-signature audit pages, page-number lines, and repeated running lines, and what was removed:
    each ``{"kind": "esign-audit" | "page-number" | "repeated-line", "text": <first 120 characters>, "count": n}``."""
    pages = text.split("\f")
    removed: list[dict[str, Any]] = []

    # 1. Audit pages: from the heading to the end of its page. With no form feeds the whole text is one page, and the
    # audit runs to its end (a service appends its trail after the document).
    kept_pages: list[list[str]] = []
    for page in pages:
        lines = page.split("\n")
        start = _audit_start(lines)
        if start is not None:
            cut = "\n".join(lines[start:]).strip()
            removed.append({"kind": "esign-audit", "text": cut[:120], "count": len(lines) - start})
            lines = lines[:start]
        kept_pages.append(lines)

    # 2. Page numbers, grouped by their shape ("Page # of #").
    numbers: dict[str, dict[str, Any]] = {}
    for lines in kept_pages:
        keep = []
        for line in lines:
            if _PAGE_NUMBER.match(line):
                shape = re.sub(r"\d+", "#", _key(line))
                entry = numbers.setdefault(shape, {"kind": "page-number", "text": line.strip()[:120], "count": 0})
                entry["count"] += 1
                continue
            keep.append(line)
        lines[:] = keep
    removed.extend(numbers.values())

    # 3. Running lines: the same line on several pages (or, in text with no form feeds, several times). The first copy
    # stays.
    counts: dict[str, int] = {}
    paged = len(kept_pages) > 1
    for lines in kept_pages:
        seen = set()
        for line in lines:
            key = _key(line)
            if not (REPEAT_MIN_CHARS <= len(key) <= REPEAT_MAX_CHARS) or _TERM_WORDS.search(key):
                continue
            if paged and key in seen:
                continue
            seen.add(key)
            counts[key] = counts.get(key, 0) + 1
    running = {k for k, n in counts.items() if n >= REPEAT_MIN}
    first_kept: set[str] = set()
    repeats: dict[str, dict[str, Any]] = {}
    for lines in kept_pages:
        keep = []
        for line in lines:
            key = _key(line)
            if key in running:
                if key not in first_kept:
                    first_kept.add(key)
                    keep.append(line)
                    continue
                entry = repeats.setdefault(key, {"kind": "repeated-line", "text": line.strip()[:120], "count": 0})
                entry["count"] += 1
                continue
            keep.append(line)
        lines[:] = keep
    removed.extend(repeats.values())

    return "\f".join("\n".join(lines) for lines in kept_pages), removed


__all__ = ["strip_noise", "REPEAT_MIN"]
