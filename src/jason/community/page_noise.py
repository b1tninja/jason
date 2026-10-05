"""Lines and pages in a document's text that are not its words: e-signature audit pages, page numbers, and running
headers and footers.

A contract signed through an e-signature service carries the service's audit trail after the last page (DocuSign's
"Certificate Of Completion", Adobe Acrobat Sign's "Final Audit Report", Dropbox Sign's "Audit trail"); a PDF's text
repeats its letterhead or footer on every page and prints "Page 2 of 4". A reader of terms that takes those as sentences
reads an envelope id as a clause and a footer as part of a duty.

``strip_noise(text)`` drops them and says what it dropped. It removes whole lines and whole audit pages, and part of a
line only for a ``FORM_FOOTERS`` row: a form's running footer that carries both a page count and the form's own stamp
(its version or revision date), as "Page 3 of 22 Version 3.33 XY, Revised 1/1/2022". PDF text extraction often runs
such a footer into the middle of a sentence; the pair of a page count and a form stamp is never a contract's words, so
it is cut wherever it sits, with every repeat. A bare page number or a lone "Version 2" or "revised on 1/1/2022" inside
a line is left where it is. Form feeds stay, so a page can still be found by counting them, and the first copy of a
repeated line stays, so a letterhead or a license line survives once. Pure: no network, no store.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# The heading that opens an e-signature service's audit page, and the words that confirm it is one.
_AUDIT_HEADING = re.compile(r"^\s*(?:certificate\s+of\s+completion|final\s+audit\s+report|audit\s+trail)\b", re.I)
_AUDIT_MARKERS = re.compile(r"envelope\s*id|transaction\s+id|signer\s+events|document\s+history|status:\s*(?:signed|completed)|"
                            r"certificate\s+pages|e-?signed\s+by|document\s+(?:created|emailed|viewed)\s+by|time\s+source", re.I)
# A line that is only a page number: "Page 2 of 4", "Page 3", "2 of 4", "2/4", "- 2 -".
_PAGE_NUMBER = re.compile(r"^\s*(?:page\s+\d+(?:\s*(?:of|/)\s*\d+)?|\d+\s*(?:of|/)\s*\d+|-\s*\d+\s*-)\s*\.?\s*$", re.I)


@dataclass(frozen=True)
class FormFooter:
    """One shape of a form's running footer, cut wherever it sits (a whole line or inside one)."""

    name: str
    pattern: re.Pattern[str]
    note: str


_PAGE_COUNT = r"page\s+\d+\s+of\s+\d+"
# A form's stamp: its version ("Version 3.33", "Ver. 2", "Rev. 4") with an optional short form code, and/or the date
# it was revised ("Revised 1/1/2022", "Rev. 01/2022").
# A form code is two to four capitals not followed by a lowercase word: "A contractor shall" opens a sentence.
_FORM_CODE = r"(?:\s+(?-i:[A-Z]{2,4})\b(?!\s+(?-i:[a-z])))"
_FORM_VERSION = rf"(?:version|ver\.)\s*\d+(?:\.\d+)*{_FORM_CODE}?"
_FORM_REVISED = r"(?:revised|rev\.)\s+\d{1,2}/(?:\d{1,2}/)?\d{2,4}\b"
# "Rev. 3" alone is also a drawing's or a plan's revision, cited in a sentence: it is a stamp only with its form code.
_FORM_REV = rf"rev\.\s*\d+(?:\.\d+)*{_FORM_CODE}"
_FORM_STAMP = rf"(?:(?:{_FORM_VERSION}|{_FORM_REV})(?:\s*,?\s*{_FORM_REVISED})?|{_FORM_REVISED})"
_JOIN = r"\s*[,|\u2013-]?\s*"

# Both rows need a page count AND a form stamp: either alone also occurs in a contract's own words.
FORM_FOOTERS: tuple[FormFooter, ...] = (
    FormFooter("page-then-stamp",
               re.compile(rf"\b{_PAGE_COUNT}{_JOIN}{_FORM_STAMP}", re.I),
               "Page 3 of 22 Version 3.33 XY, Revised 1/1/2022"),
    FormFooter("stamp-then-page",
               re.compile(rf"\b{_FORM_STAMP}{_JOIN}{_PAGE_COUNT}\b", re.I),
               "Rev. 2 XY, Revised 1/1/2022 Page 3 of 22"),
)

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


def _cut_footers(line: str, found: dict[str, dict[str, Any]]) -> str | None:
    """``line`` without the ``FORM_FOOTERS`` it carries, each counted in ``found``; None when nothing else was on it."""
    cut = False
    for row in FORM_FOOTERS:
        def drop(m: re.Match[str], row: FormFooter = row) -> str:
            shape = re.sub(r"\d+", "#", _key(m.group(0)))
            entry = found.setdefault(shape, {"kind": "form-footer", "text": m.group(0).strip()[:120], "count": 0,
                                             "row": row.name})
            entry["count"] += 1
            return "\x00"
        line, n = row.pattern.subn(drop, line)
        cut = cut or bool(n)
    if not cut:
        return line
    # Where a footer sat between two words, one space joins them; at either end of the line, nothing.
    gap = r"[ \t]*\x00(?:[ \t]*\x00)*[ \t]*"
    line = re.sub(rf"{gap}$", "", re.sub(rf"^(\s*){gap}", r"\1", line))
    line = re.sub(gap, " ", line)
    return line if line.strip() else None


def strip_noise(text: str) -> tuple[str, list[dict[str, Any]]]:
    """``text`` without e-signature audit pages, page-number lines, and repeated running lines, and what was removed:
    each ``{"kind": "esign-audit" | "form-footer" | "page-number" | "repeated-line", "text": <first 120 characters>,
    "count": n}`` (a form footer also names its ``FORM_FOOTERS`` row)."""
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

    # 2. Form footers, cut wherever they sit, then page numbers; each grouped by its shape ("Page # of #").
    numbers: dict[str, dict[str, Any]] = {}
    for lines in kept_pages:
        keep = []
        for line in lines:
            line = _cut_footers(line, numbers)
            if line is None:
                continue
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


__all__ = ["strip_noise", "FormFooter", "FORM_FOOTERS", "REPEAT_MIN"]
