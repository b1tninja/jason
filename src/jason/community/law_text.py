"""The words of the law on the shelf, section by section, each with a digest of its words.

``jason export-authorities`` writes one page per span under ``data/authorities``; a section is the body under its
``## CITATION`` heading, split as ``context_pack.law_corpus`` splits it. A section's **words** are that body with line
endings and trailing spaces normalized, less jason's own ``- History:`` note (an annotation from the law history, not
the Legislature's words). Its **digest** is the SHA-256 of those words. The page's header (the session, the official
page, why jason holds it) is outside every section, so a new session label alone changes no digest.

The digest is what a derived record is tied to: a reading of the law (``jason.community.law_readings``) names the
digest of the words it read, and is stale when the shelf no longer holds words with that digest. When an export
replaces a section's words, the replaced words are kept under ``data/authorities/history/<citation>/<digest>.md`` and
the change is a row in ``data/authorities/changes.json`` (``jason.tasks.authority_digests`` writes both). That log is
jason's record of its own shelf; the Act's amendment history from lawlibrary is ``history/changes.json``
(``jason.community.succession``), a different file.

A page may hold one section more than once: the Legislature's publication prints two versions of some sections, each
under the same number. ``versions`` gives every one; ``law_text`` and ``section_digest`` give the first, which is the
one ``authority_text`` quotes. Nothing here says which version is in force on a day.

This module reads the disk only. It never asks lawlibrary for a section: a miss is a miss.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HISTORY_DIR = "authorities/history"
CHANGES_FILE = "authorities/changes.json"
# The fewest characters of a digest a record may carry and still be matched against the full digest.
MIN_DIGEST = 12

_NOTE = re.compile(r"^- History:\s*(.*)$")
# A code, a section number (dotted, with the letter some sections end in: "2924a"), and any subdivisions.
_CITATION = re.compile(r"^\s*(?:(\d+)[\s-]+)?([A-Za-z]{2,5})[\s-]*(?:section\s+|§\s*)?(\d+(?:\.\d+)*[a-z]?)\s*((?:\([^)]*\))*)\s*$",
                       re.IGNORECASE)
_HEX = re.compile(r"^[0-9a-f]+$")


def normal_citation(citation: str) -> tuple[str, str] | None:
    """A statute citation as the shelf's headings write it, with any subdivision apart: "civ-5855" and "CIV 5855(a)"
    give ("CIV 5855", "") and ("CIV 5855", "(a)"); "10-CCR-2792.23" gives ("10 CCR 2792.23", ""). None when the text
    is not a code and a section number."""
    m = _CITATION.match(citation or "")
    if not m:
        return None
    code = (m.group(1) + " " if m.group(1) else "") + m.group(2).upper()
    return f"{code} {m.group(3).lower()}", m.group(4) or ""


def slug(citation: str) -> str:
    """A citation as a folder name: "CIV 5855" is "CIV-5855"."""
    return re.sub(r"[^A-Za-z0-9.]+", "-", citation).strip("-")


def split_note(body: str) -> tuple[str, str]:
    """A section's body as (its words, jason's History note). The note is the ``- History:`` line the export writes
    first under the heading; everything else is the words, with line endings and trailing spaces normalized and the
    blank lines at either end dropped."""
    lines = [line.rstrip() for line in (body or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    note = ""
    if lines:
        m = _NOTE.match(lines[0])
        if m:
            note = m.group(1).strip()
            lines.pop(0)
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines), note


def section_words(body: str) -> str:
    """The words a digest is taken over (``split_note`` without the note)."""
    return split_note(body)[0]


def words_digest(body: str) -> str:
    """The SHA-256 of a section's words, as hex. Two bodies that differ only in line endings, trailing spaces, or the
    History note have the same digest."""
    return hashlib.sha256(section_words(body).encode("utf-8")).hexdigest()


def same_digest(recorded: str, now: str) -> bool:
    """Whether a digest a record carries names the words whose digest is ``now``. A record may carry the leading
    ``MIN_DIGEST`` or more characters."""
    recorded, now = (recorded or "").strip().lower(), (now or "").strip().lower()
    return len(recorded) >= MIN_DIGEST and bool(_HEX.match(recorded)) and bool(now) and now.startswith(recorded)


def split_page(text: str) -> tuple[str, list[tuple[str, str]]]:
    """A page as (its header, each section's heading and body), split where ``law_corpus`` splits it."""
    blocks = (text or "").replace("\r\n", "\n").split("\n## ")
    sections = []
    for block in blocks[1:]:
        head, _, body = block.partition("\n")
        sections.append((head.strip(), body))
    return blocks[0], sections


def source_line(header: str) -> str:
    """The page's ``- Source:`` line: who published the words, and the session."""
    for line in header.split("\n"):
        if line.startswith("- Source:"):
            return line[len("- Source:"):].strip()
    return ""


@dataclass(frozen=True)
class LawText:
    """One section's words as the shelf holds or held them."""

    citation: str               # "CIV 5855"
    words: str                  # verbatim, as hashed
    digest: str
    source: str = ""            # the page's Source line ("California Legislature, 2025 session publication, ...")
    session: str = ""
    page: str = ""              # the file under the data folder that holds or held it
    note: str = ""              # jason's History note, not part of the words
    current: bool = True        # False for words an export replaced (read from the history)
    replaced: str = ""          # the day an export replaced them, for a historical text


def page_sections(root: Path, page: Any) -> list[LawText]:
    """Each section a manifest page holds, in order. Nothing when the file is not on disk."""
    path = Path(root) / page.file
    if not path.is_file():
        return []
    header, sections = split_page(path.read_text(encoding="utf-8", errors="ignore"))
    source = source_line(header)
    out = []
    for head, body in sections:
        words, note = split_note(body)
        out.append(LawText(head, words, hashlib.sha256(words.encode("utf-8")).hexdigest(), source, page.session,
                           page.file, note))
    return out


def _pages(root: Path) -> tuple[Any, ...]:
    from jason.tasks.export_authorities import authority_pages, on_demand_pages

    return (*authority_pages(Path(root)), *on_demand_pages(Path(root)))


def shelf_sections(root: Path) -> list[LawText]:
    """Every section on the shelf: the curated pages, then the pages fetched on demand, each as its page holds it. A
    section two pages hold, or one page holds in two versions, comes back each time."""
    out: list[LawText] = []
    for page in _pages(root):
        out += page_sections(Path(root), page)
    return out


def versions(citation: str, data_dir: Path) -> list[LawText]:
    """Every text the shelf holds under a section's citation, in the shelf's order (the curated pages, then those
    fetched on demand), each digest once. Usually one; two when the publication prints two versions of the section.
    Empty when the section is not on the shelf."""
    found = normal_citation(citation)
    if found is None:
        return []
    code, _, number = found[0].rpartition(" ")
    out: list[LawText] = []
    for page in _pages(Path(data_dir)):
        if page.code != code or (page.sections and number not in page.sections):
            continue
        for text in page_sections(Path(data_dir), page):
            if text.citation == found[0] and all(text.digest != other.digest for other in out):
                out.append(text)
    return out


def history_dir(root: Path, citation: str) -> Path:
    return Path(root) / HISTORY_DIR / slug(citation)


def history_texts(citation: str, data_dir: Path) -> list[LawText]:
    """The words an export replaced for one section, oldest replacement first. Each file is read and hashed again, so
    a text is only ever returned under the digest its words have now."""
    found = normal_citation(citation)
    if found is None:
        return []
    folder = history_dir(Path(data_dir), found[0])
    if not folder.is_dir():
        return []
    out = []
    for path in folder.glob("*.md"):
        header, sections = split_page(path.read_text(encoding="utf-8", errors="ignore"))
        fields = {k.strip(): v.strip() for k, _, v in (line[2:].partition(":") for line in header.split("\n")
                                                       if line.startswith("- "))}
        for head, body in sections:
            if head != found[0]:
                continue
            words = section_words(body)
            out.append(LawText(head, words, hashlib.sha256(words.encode("utf-8")).hexdigest(), fields.get("Source", ""),
                               fields.get("Session", ""), fields.get("Page", ""), fields.get("History", ""), False,
                               fields.get("Replaced", "").split(" ", 1)[0]))
    return sorted(out, key=lambda t: (t.replaced, t.digest))


def law_text(citation: str, data_dir: Path, digest: str | None = None) -> LawText | None:
    """A section's words: the current ones (the first version, when the shelf holds two), or with ``digest`` the
    words that have it (a version on the shelf, else a text an export replaced). None when the section is not on the
    shelf, or no text held has that digest."""
    now = versions(citation, Path(data_dir))
    if digest is None:
        return now[0] if now else None
    held = next((t for t in now if same_digest(digest, t.digest)), None)
    if held is not None:
        return held
    return next((t for t in history_texts(citation, Path(data_dir)) if same_digest(digest, t.digest)), None)


def section_digest(citation: str, data_dir: Path) -> str | None:
    """The digest of a section's words as they are on disk now (the first version, when the shelf holds two), or None
    when the section is not on the shelf."""
    now = versions(citation, Path(data_dir))
    return now[0].digest if now else None


def changes(data_dir: Path, citation: str = "") -> list[dict[str, Any]]:
    """The shelf's own change log, oldest first: each time an export replaced a section's words (``citation``, the
    ``old`` and ``new`` digests, ``when``, and the old and new source lines). One section's rows with ``citation``."""
    path = Path(data_dir) / CHANGES_FILE
    if not path.is_file():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8") or "[]")
    except json.JSONDecodeError:
        return []
    if citation:
        found = normal_citation(citation)
        rows = [r for r in rows if found is not None and r.get("citation") == found[0]]
    return rows


__all__ = ["CHANGES_FILE", "HISTORY_DIR", "LawText", "MIN_DIGEST", "changes", "history_dir", "history_texts", "law_text",
           "normal_citation", "page_sections", "same_digest", "section_digest", "section_words", "shelf_sections",
           "slug", "source_line", "split_note", "split_page", "versions", "words_digest"]
