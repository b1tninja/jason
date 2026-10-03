"""Revision detection: the versions of one document, its sections aligned across them, and what changed in each.

A rule, a policy, or a manual is revised in place: the board edits the working Doc, a copy goes to an escrow company, a
later copy goes to a new owner. Each copy that survives (an email attachment, a library upload, a Drive revision, a
scan of the first printing) is a version. This module compares them section by section, so each section is a unit with
its own lineage.

1. **Text.** Each version's words are cleaned of what is not the document: page furniture a PDF repeats on every page
   (headers, footers, page numbers), a Doc export's comment anchors and comment texts, and its table of contents.
   ``docx_text`` renders a Word file's (or a Drive revision's docx export's) list numbers the way the file draws them,
   so "a." stays "a." and a nested "(1)" stays "(1)".
2. **Outline.** ``outline_text`` reads sections from the cleaned text: "ARTICLE n", dotted numbers ("4.15"), lettered
   rule numbers ("R-4. PARKING"), Markdown or Word headings, an all-capitals caption ("WHAT IS A RESERVE?"), and
   list labels under them ("a.", "a)", "(a)", "1.", "(i)"), nested by series and indentation. Each section's own words
   (not its subsections') are one ``Unit``.
3. **Align.** ``align`` pairs the units of two versions: the same words first (letters and digits only, so a line break
   or a quote mark is not a change), then the same label, then the same opening words (``outline_align``), then shared
   letter runs (as ``embedded_copies`` finds copies) for a section that moved or was renumbered. What is left is a split
   (one section's words now in two), a merge, an addition, or a removal.
4. **Classify.** Each pair is unchanged, reworded (with a word diff), moved, or renumbered. A reworded pair whose only
   differences are OCR's (a near letter in a word, with no number and no "shall" or "may" touched) is noise. A change
   to an amount, a number of days, a fine or fee, a number, or a "shall"/"may"/"must" is flagged (``Flag``) and is read
   first.
5. **Lineage.** ``lineages`` follows each unit through every version. A lineage's id follows the permanent-id rule
   (``addresses.pid``): the document's key, the date of the version it first appeared in, and its number there
   (``rules@2099-01-01/R-4(b)``); an unnumbered caption is known by its words (``what-is-a-reserve``).

Nothing here decides that a change was adopted: ``jason.tasks.revision_detection`` looks for the adoption on record,
and a change with none is a finding ("changed between A and B; no adoption found"). Pure: no disk, no network.
"""

from __future__ import annotations

import difflib
import io
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from functools import lru_cache
from typing import Any, Iterable, Sequence
from xml.etree import ElementTree

from jason.community.embedded_copies import stream
from jason.community.outline_align import opening_key, similarity
from jason.community.outlines import DocumentOutline, Section

SHINGLE = 12                 # letters and digits in a run compared between sections (about two words)
SAME_LABEL_MIN = 0.5         # a pair with the same label shares at least this much of its words, or it is a new rule
OPENING_MIN = 0.85           # opening words this alike pair two sections
RUNS_MIN = 0.5               # shared runs (Dice) that pair a moved or renumbered section
PART_MIN = 0.6               # share of a section's runs found inside another: a split's part, a merge's piece
VERSION_MIN = 0.3            # share of the current text's runs a copy must hold to be a version of this document
PARTIAL_BELOW = 0.5          # a version holding less than this share of the current text is an excerpt


class ChangeKind(Enum):
    UNCHANGED = "unchanged"
    REWORDED = "reworded"
    MOVED = "moved"              # the same words under another heading or out of order
    RENUMBERED = "renumbered"    # the same words under another number
    ADDED = "added"
    REMOVED = "removed"
    SPLIT = "split"              # one section's words are now in two or more
    MERGED = "merged"            # two or more sections' words are now in one


class Flag(Enum):
    """What a change touched, the most consequential first. A flagged change is read before the rest."""

    AMOUNT = "amount"            # a dollar amount
    DAYS = "days"                # a period of time (days, hours, months, years)
    FINE = "fine"                # a fine, fee, penalty, charge, or interest
    MODAL = "shall/may"          # an obligation became a permission, or the reverse, or a "not" came or went
    NUMBER = "number"            # any other number


FLAG_ORDER = list(Flag)


# ---------------------------------------------------------------------------------------------------------------------
# Text.

_QUOTES = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'", "“": '"',
                         "”": '"', "„": '"', "″": '"', "–": "-", "—": "-", "‒": "-",
                         "‐": "-", "‑": "-", " ": " ", " ": " ", " ": " ", "​": "",
                         "﻿": "", "­": "", "ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi",
                         "ﬄ": "ffl", "": "", "•": "", "●": "", "○": "", "▪": "",
                         "■": "", "➢": "", "": "", "": "", "§": "§"})
_ANCHOR = re.compile(r"\[(?:[a-z]{1,3}|\d{1,3})\]")                 # a Doc export's comment anchor: "[a]", "[ab]"
_COMMENT_LINE = re.compile(r"^\[(?:[a-z]{1,3})\]\S")                 # the comment itself, listed at the end
_PAGE_NUMBER = re.compile(r"^\s*(?:page\s+)?-?\s*\d{1,3}\s*-?(?:\s+of\s+\d{1,3})?\s*$", re.I)
_TOC_HEAD = re.compile(r"^\s*(?:#+\s*)?table\s+of\s+contents\s*$", re.I)


def clean(text: str) -> str:
    """Quotes, dashes, spaces, ligatures, and bullet glyphs made plain; a word broken across a line ("re-\\nquired")
    joined; a Doc export's comment anchors and the comments listed after the text dropped."""
    t = (text or "").translate(_QUOTES).replace("\r\n", "\n").replace("\r", "\n").replace("�", "'")
    lines = t.split("\n")
    # The comments a Doc's text export lists at its end ("[a]Should update for ..."): cut from the first one that
    # starts a line in the last half of the text.
    half = len(lines) // 2
    for k in range(half, len(lines)):
        if _COMMENT_LINE.match(lines[k].strip()):
            lines = lines[:k]
            break
    t = "\n".join(lines)
    t = _ANCHOR.sub("", t)
    t = re.sub(r"([a-z])-[ \t]*\n[ \t]*([a-z])", r"\1\2", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    return t


def strip_furniture(pages: Sequence[str]) -> str:
    """A PDF's pages as one text, without the lines it repeats on many pages (a header, a footer, the title in the
    margin) or a bare page number."""
    pages = [clean(p) for p in pages]
    counts: Counter[str] = Counter()
    edges: Counter[str] = Counter()
    for p in pages:
        lines = [" ".join(line.split()).lower() for line in p.split("\n") if line.strip()]
        counts.update(set(lines))
        edges.update(set(lines[:2] + lines[-2:]))
    # A line on half the pages anywhere, or at a page's top or bottom on three pages or more (a running header
    # that only one part of the document carries).
    repeated = {line for line, n in counts.items() if len(pages) >= 3 and n >= max(3, len(pages) // 2)
                and len(line) <= 120}
    running = {line for line, n in edges.items() if n >= 3 and len(line) <= 80}
    out = []
    for p in pages:
        lines = p.split("\n")
        filled = [k for k, line in enumerate(lines) if line.strip()]
        edge_at = set(filled[:2] + filled[-2:])
        keep = []
        for k, line in enumerate(lines):
            key = " ".join(line.split()).lower()
            if _PAGE_NUMBER.match(line) or key in repeated or (k in edge_at and key in running):
                continue
            keep.append(line)
        out.append("\n".join(keep))
    return "\n".join(out)


def text_hash(text: str) -> str:
    """The identity of a version's words: its letters and digits only (a re-export or a reflowed line is the same)."""
    import hashlib

    return hashlib.sha256(stream(text).encode("ascii", "ignore")).hexdigest()


# ---------------------------------------------------------------------------------------------------------------------
# Word files: the text with the list numbers the file draws.

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _roman(n: int) -> str:
    out = ""
    for value, symbol in ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"),
                          (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while n >= value:
            out, n = out + symbol, n - value
    return out


def _letters(n: int) -> str:
    out = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(97 + r) + out
    return out


def _format(n: int, fmt: str) -> str:
    if fmt == "lowerLetter":
        return _letters(n)
    if fmt == "upperLetter":
        return _letters(n).upper()
    if fmt == "lowerRoman":
        return _roman(n)
    if fmt == "upperRoman":
        return _roman(n).upper()
    if fmt in ("bullet", "none"):
        return ""
    return str(n)


def _attr(el: Any, name: str) -> str:
    return el.get(f"{_W}{name}", "") if el is not None else ""


def _levels(numbering: ElementTree.Element | None) -> tuple[dict[str, dict[int, dict[str, Any]]], dict[str, str],
                                                             dict[str, dict[int, int]]]:
    abstract: dict[str, dict[int, dict[str, Any]]] = {}
    nums: dict[str, str] = {}
    overrides: dict[str, dict[int, int]] = {}
    if numbering is None:
        return abstract, nums, overrides
    for a in numbering.findall(f"{_W}abstractNum"):
        levels = {}
        for lvl in a.findall(f"{_W}lvl"):
            ilvl = int(_attr(lvl, "ilvl") or 0)
            start = lvl.find(f"{_W}start")
            fmt = lvl.find(f"{_W}numFmt")
            text = lvl.find(f"{_W}lvlText")
            levels[ilvl] = {"start": int(_attr(start, "val") or 1), "fmt": _attr(fmt, "val") or "decimal",
                            "text": _attr(text, "val")}
        abstract[_attr(a, "abstractNumId")] = levels
    for n in numbering.findall(f"{_W}num"):
        nid = _attr(n, "numId")
        ref = n.find(f"{_W}abstractNumId")
        nums[nid] = _attr(ref, "val")
        for o in n.findall(f"{_W}lvlOverride"):
            so = o.find(f"{_W}startOverride")
            if so is not None:
                overrides.setdefault(nid, {})[int(_attr(o, "ilvl") or 0)] = int(_attr(so, "val") or 1)
    return abstract, nums, overrides


def _styles(styles: ElementTree.Element | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if styles is None:
        return out
    for s in styles.findall(f"{_W}style"):
        sid = _attr(s, "styleId")
        name = _attr(s.find(f"{_W}name"), "val").lower()
        based = _attr(s.find(f"{_W}basedOn"), "val")
        ppr = s.find(f"{_W}pPr")
        num = ppr.find(f"{_W}numPr") if ppr is not None else None
        outline = ppr.find(f"{_W}outlineLvl") if ppr is not None else None
        out[sid] = {"name": name, "based": based,
                    "numId": _attr(num.find(f"{_W}numId"), "val") if num is not None else "",
                    "ilvl": int(_attr(num.find(f"{_W}ilvl"), "val") or 0) if num is not None else 0,
                    "outline": int(_attr(outline, "val")) if outline is not None and _attr(outline, "val") else None}
    return out


def _heading_level(style: dict[str, Any] | None, styles: dict[str, dict[str, Any]]) -> int | None:
    seen = 0
    while style is not None and seen < 10:
        name = style["name"]
        if name == "title":
            return 0
        m = re.fullmatch(r"heading\s*(\d)", name)
        if m:
            return int(m.group(1))
        if style.get("outline") is not None:
            return int(style["outline"]) + 1
        style = styles.get(style.get("based") or "")
        seen += 1
    return None


def docx_suggestions(data: bytes) -> list[tuple[str, str]]:
    """A Word file's tracked changes, in order: ("insert", words) or ("delete", words). A Google Doc's export carries
    its pending suggestions this way: words proposed, not yet accepted."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        body = ElementTree.fromstring(z.read("word/document.xml"))
    out = []
    for el in body.iter():
        if el.tag == f"{_W}ins":
            words = " ".join("".join(t.text or "" for t in el.iter(f"{_W}t")).split())
            if words:
                out.append(("insert", words))
        elif el.tag == f"{_W}del":
            words = " ".join("".join(t.text or "" for t in el.iter(f"{_W}delText")).split())
            if words:
                out.append(("delete", words))
    return out


def docx_text(data: bytes, *, accept: bool = False) -> str:
    """A Word file's body as text: one line a paragraph, a list item with its label as the file draws it ("a.",
    "(1)", "1.2") and indented two spaces a level, a heading as a Markdown heading ("## R-4. PARKING"). A bulleted
    item has no label.

    Tracked changes (a Google Doc's pending suggestions) are read as the text stands: an insertion is left out and a
    deletion kept, as the Doc's own PDF prints it. ``accept`` reads them as if accepted."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
        body = ElementTree.fromstring(z.read("word/document.xml"))
        numbering = ElementTree.fromstring(z.read("word/numbering.xml")) if "word/numbering.xml" in names else None
        style_root = ElementTree.fromstring(z.read("word/styles.xml")) if "word/styles.xml" in names else None
    abstract, nums, overrides = _levels(numbering)
    styles = _styles(style_root)
    counters: dict[str, dict[int, int]] = defaultdict(dict)
    lines: list[str] = []
    deleted: set[int] = set()
    skipped_tag = f"{_W}del" if accept else f"{_W}ins"
    for d in body.iter(skipped_tag):
        deleted.update(id(x) for x in d.iter())
    kept_deletion = f"{_W}t" if accept else f"{_W}delText"
    # A table of contents is a content control whose gallery says so: its entries repeat the headings.
    for sdt in body.iter(f"{_W}sdt"):
        gallery = sdt.find(f"{_W}sdtPr/{_W}docPartObj/{_W}docPartGallery")
        if gallery is not None and "contents" in _attr(gallery, "val").lower():
            deleted.update(id(x) for x in sdt.iter())
    for p in body.iter(f"{_W}p"):
        if id(p) in deleted:
            continue
        pieces = []
        for el in p.iter():
            if id(el) in deleted:
                continue
            if el.tag in (f"{_W}t", kept_deletion) and el.text:
                pieces.append(el.text)
            elif el.tag == f"{_W}tab":
                pieces.append("\t")
            elif el.tag in (f"{_W}br", f"{_W}cr"):
                pieces.append(" ")
            elif el.tag == f"{_W}noBreakHyphen":
                pieces.append("-")
        text = " ".join("".join(pieces).split())
        ppr = p.find(f"{_W}pPr")
        style = styles.get(_attr(ppr.find(f"{_W}pStyle"), "val")) if ppr is not None else None
        num = ppr.find(f"{_W}numPr") if ppr is not None else None
        num_id, ilvl = "", 0
        if num is not None:
            num_id = _attr(num.find(f"{_W}numId"), "val")
            ilvl = int(_attr(num.find(f"{_W}ilvl"), "val") or 0)
        elif style is not None and style.get("numId"):
            num_id, ilvl = style["numId"], style["ilvl"]
        label = ""
        if num_id and num_id != "0" and nums.get(num_id) in abstract and text:
            levels = abstract[nums[num_id]]
            restart = num_id in overrides
            key = num_id if restart else nums[num_id]
            count = counters[key]
            lvl = levels.get(ilvl, {"start": 1, "fmt": "decimal", "text": f"%{ilvl + 1}."})
            start = overrides.get(num_id, {}).get(ilvl, lvl["start"])
            count[ilvl] = count.get(ilvl, start - 1) + 1
            for deeper in [k for k in count if k > ilvl]:
                del count[deeper]
            if lvl["fmt"] not in ("bullet", "none"):
                def one(m: re.Match) -> str:
                    k = int(m.group(1)) - 1
                    info = levels.get(k, {"fmt": "decimal", "start": 1})
                    return _format(count.get(k, info["start"]), info["fmt"])
                label = re.sub(r"%(\d)", one, lvl["text"])
        heading = _heading_level(style, styles)
        if not text:
            lines.append("")
        elif heading is not None:
            lines.append("#" * max(1, min(6, heading)) + " " + (f"{label} " if label else "") + text)
        else:
            lines.append("  " * ilvl + (f"{label} " if label else "") + text)
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------------------------------
# Outline.

_ARTICLE = re.compile(r"^ARTICLE\s+([IVXLC]+|\d+)\b\s*[-.:]?\s*(.*)$", re.I)
_RULE_HEAD = re.compile(r"^([A-Z]{1,3}-\d{1,3}(?:\.\d+)*)\s*[.:)-]?\s+(\S.{0,150})$")
_DOTTED = re.compile(r"^(?:Section\s+)?(\d{1,2}(?:\.\d{1,3})+)\.?\s+(\S.{0,150})$", re.I)
_MD_HEAD = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_LABEL = re.compile(r"^(?P<indent>[ \t]*)(?P<open>\()?(?P<tok>[A-Za-z]{1,4}|\d{1,2})(?P<close>[.)])(?:[ \t]+(?P<rest>\S.*))?$")
_ROMAN = re.compile(r"^(?=[ivxl]+$)x{0,3}(ix|iv|v?i{0,3})$", re.I)


def _arabic(token: str) -> str:
    if token.isdigit():
        return token
    total, prev = 0, 0
    for ch in reversed(token.upper()):
        v = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}.get(ch, 0)
        total, prev = (total - v, prev) if v < prev else (total + v, v)
    return str(total)


def slug(text: str) -> str:
    """A caption as a section path: lowercase words joined by hyphens ("what-is-my-assessment")."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:60].strip("-") or "untitled"


def _caption(line: str) -> bool:
    """An all-capitals line of two words or more, short, that is not a sentence: a caption."""
    s = line.strip()
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 6 or len(s) > 100 or len(s.split()) < 2:
        return False
    if sum(c.isdigit() for c in s) > len(s) // 10 or re.search(r"https?:|www\.|@", s, re.I):
        return False                                  # a telephone line or an address in a contact list
    if not letters[0].isupper() or sum(c.islower() for c in letters) * 8 > len(letters):
        return False                                  # "WHAT ARE THE CC&Rs?" is a caption; a sentence is not
    return not s.endswith((",", ";")) and not re.match(r"^[\"'(]", s)


class _Series(Enum):
    DIGIT = "1"
    LOWER = "a"
    UPPER = "A"
    ROMAN = "i"
    UPPER_ROMAN = "I"


def _series_of(token: str, open_series: list[tuple[_Series, str]]) -> _Series:
    """The series of a label token. "i" after an "h" is a letter; with no "h" before it, a roman numeral (a lone
    "i" with no list open is roman)."""
    if token.isdigit():
        return _Series.DIGIT
    lower = token.islower()
    if _ROMAN.match(token):
        prev = next((last for s, last in reversed(open_series) if s in ((_Series.LOWER,) if lower else (_Series.UPPER,))), "")
        single = len(token) == 1
        follows = single and prev and len(prev) == 1 and ord(token.lower()) == ord(prev.lower()) + 1
        if follows:
            return _Series.LOWER if lower else _Series.UPPER
        open_roman = any(s in ((_Series.ROMAN,) if lower else (_Series.UPPER_ROMAN,)) for s, _ in open_series)
        if not single or token.lower() == "i" or open_roman:
            return _Series.ROMAN if lower else _Series.UPPER_ROMAN
    return _Series.LOWER if lower else _Series.UPPER


def _toc_key(line: str) -> str:
    s = re.sub(r"^#+\s*", "", line.strip())
    s = re.sub(r"(?:\s*\.[.\s]+|\s+)\d{1,3}$", "", s)            # dot leaders ("..... 27", ". . . 27") and a page
    s = re.sub(r"[.\s]+$", "", s)
    return " ".join(s.lower().split())


def _drop_toc(text: str) -> str:
    """The text with its table of contents blanked: from a "Table of Contents" line, each line that the document
    repeats later (an entry is its heading again), up to the first that it does not. Blanked, not cut, so offsets
    into the text hold."""
    lines = text.split("\n")
    at = next((k for k, line in enumerate(lines[: max(40, len(lines) // 5)]) if _TOC_HEAD.match(line)), None)
    if at is None:
        return text
    keys = [_toc_key(line) for line in lines]
    # One normalized string of the lines, and where each line starts in it: an entry is found later when its words
    # appear after it (an entry wrapped over two lines is still found, each half on its own).
    joined, starts = "", []
    for key in keys:
        starts.append(len(joined))
        joined += key + " "
    end, misses = at, 0
    for k in range(at + 1, len(lines)):
        if not lines[k].strip():
            continue
        key = keys[k]
        later = starts[k + 2] if k + 2 < len(starts) else len(joined)
        if len(key) >= 3 and joined.find(key, later) >= 0:
            end, misses = k, 0
            continue
        misses += 1                     # an entry worded unlike its heading; three in a row end the contents
        if misses >= 3:
            break
    for k in range(at, end + 1):
        lines[k] = " " * len(lines[k])
    return "\n".join(lines)


@dataclass
class _Open:
    series: _Series
    indent: int
    last: str
    number: str


def outline_text(text: str, *, key: str, title: str = "", kind: str = "") -> DocumentOutline:
    """Sections read from a version's cleaned text (see the module's notes). A head starts at depth 1 (a dotted number
    deeper by its dots); a list item is one deeper than what it sits in. A run of three or more heads with no words
    between them is a table of contents and is dropped."""
    text = _drop_toc(clean(text))
    out = DocumentOutline(key=key, title=title, kind=kind, text=text)
    lines = text.split("\n")
    offsets, at = [], 0
    for line in lines:
        offsets.append(at)
        at += len(line) + 1
    head_number = ""                 # the number of the head the list sits under ("R-4", "4.15"), or a caption slug
    head_depth = 1
    stack: list[_Open] = []
    body_after: list[bool] = []      # for each section: whether any words follow it before the next section
    k = 0
    while k < len(lines):
        raw = lines[k]
        s = raw.strip()
        start = offsets[k]
        if not s or _TOC_HEAD.match(s):
            k += 1
            continue
        md = _MD_HEAD.match(s)
        head_text = md.group(2).strip() if md else s
        head_text = re.sub(r"^\*+|\*+$", "", head_text).strip()
        section: Section | None = None
        if m := _ARTICLE.match(head_text):
            section = Section(_arabic(m.group(1)), (m.group(2) or head_text).strip(), 1, start)
        elif m := _RULE_HEAD.match(head_text):
            if md or m.group(2)[:1].isupper():
                section = Section(m.group(1), m.group(2).strip(), 1, start)
        elif (m := _DOTTED.match(head_text)) and (md or m.group(2)[:1].isupper()):
            number = m.group(1)
            section = Section(number, m.group(2).strip(), 1 + number.count("."), start,
                              parent=number.rsplit(".", 1)[0])
        elif md and not _LABEL.match(head_text):
            section = Section("", head_text, 1, start)
        elif not md and _caption(s) and not _LABEL.match(s):
            section = Section("", s, 1, start)
        if section is not None:
            head_number = section.number or slug(section.title)
            head_depth = section.depth
            stack = []
            out.sections.append(section)
            body_after.append(False)
            k += 1
            continue
        lab = _LABEL.match(raw.rstrip()) or (_LABEL.match(head_text) if md else None)
        if lab is not None:
            token, rest = lab.group("tok"), (lab.group("rest") or "").strip()
            paren = bool(lab.group("open"))
            # A label alone on its line labels the words on the next line (a PDF's hanging label).
            nxt = k + 1
            if not rest:
                while nxt < len(lines) and not lines[nxt].strip():
                    nxt += 1
                rest = lines[nxt].strip() if nxt < len(lines) else ""
            first = rest[:1]
            plausible = bool(rest) and (paren or first.isupper() or first in "\"'(" or first.isdigit()
                                        or (not token.isdigit() and lab.group("close") == ")"))
            if token.isdigit() and not paren and not lab.group("rest") and not first.isupper():
                plausible = False
            if len(token) > 1 and not token.isdigit() and not _ROMAN.match(token):
                plausible = False                    # "Inc." or "etc." is a word, not a label
            if plausible:
                indent = len(lab.group("indent").expandtabs(4))
                series = _series_of(token, [(o.series, o.last) for o in stack])
                while stack and stack[-1].indent > indent:
                    stack.pop()
                at_level = next((i for i in range(len(stack) - 1, -1, -1) if stack[i].series is series), None)
                if at_level is not None:
                    del stack[at_level:]
                parent = stack[-1].number if stack else head_number
                glyph = token if series in (_Series.DIGIT,) else token
                number = f"{parent}({glyph})" if parent else f"({glyph})"
                depth = head_depth + len(stack) + 1
                stack.append(_Open(series, indent, token, number))
                label = (lab.group("open") or "") + token + lab.group("close")
                out.sections.append(Section(number, rest[:150], depth, start, label=label,
                                            parent=parent))
                body_after.append(True)
                k = (nxt + 1) if not lab.group("rest") else (k + 1)
                continue
        if body_after:
            body_after[-1] = True
        k += 1
    # A table of contents: three or more heads in a row with no words of their own and nothing between them.
    drop: set[int] = set()
    run: list[int] = []
    for i in range(len(out.sections) + 1):
        if i < len(out.sections) and out.sections[i].depth == 1 and not body_after[i]:
            run.append(i)
            continue
        if len(run) >= 3:
            drop.update(run)
        run = []
    out.sections = [s for i, s in enumerate(out.sections) if i not in drop]
    for i, s in enumerate(out.sections):
        s.end = next((t.start for t in out.sections[i + 1:] if t.depth <= s.depth), len(text))
    return out


def outline_version(text: str, *, key: str, title: str = "", ocr: bool = False) -> DocumentOutline:
    """The outline of one version, by the reader that fits its source: ``outline_text`` for a Doc, a Word file, or a
    PDF's own text; for an OCR reading, also the label grammar for scans (``outline_labels.outline_from_ocr``), which
    reads garbled labels in order. The reading that finds more numbered sections wins."""
    plain = outline_text(text, key=key, title=title)
    if not ocr:
        return plain
    try:
        from jason.community.outline_labels import outline_from_ocr

        scanned = outline_from_ocr(clean(text), key=key, title=title).outline()
    except Exception:                       # the grammar is a second reader: its failure leaves the first
        return plain
    count = lambda o: sum(1 for s in o.sections if s.number)    # noqa: E731
    return scanned if count(scanned) > count(plain) else plain


# ---------------------------------------------------------------------------------------------------------------------
# Units.

@dataclass
class Unit:
    """One section's own words in one version (its subsections' words are their own units)."""

    index: int
    number: str                  # as the version numbers it; a caption's slug when it has no number
    title: str
    words: str                   # its own words, the label dropped, whitespace collapsed
    head: str                    # the head it sits under ("R-4"), or its own number for a head
    depth: int
    stream: str = ""
    runs: frozenset[str] = frozenset()

    @property
    def opening(self) -> str:
        return opening_key(self.words)


def units(outline: DocumentOutline) -> list[Unit]:
    """Each section's own words, from its start to the next section's start, the label dropped. A number used twice
    is told apart with "~2" (the second), as the record addresses do."""
    out: list[Unit] = []
    seen: Counter[str] = Counter()
    head = ""
    for i, s in enumerate(outline.sections):
        end = outline.sections[i + 1].start if i + 1 < len(outline.sections) else len(outline.text)
        raw = outline.text[s.start:end]
        if s.label and raw.lstrip().startswith(s.label):
            raw = raw.lstrip()[len(s.label):]
        words = " ".join(raw.split())
        words = re.sub(r"^#+\s*", "", words)
        number = s.number or slug(s.title)
        if s.depth == 1 or not s.parent:
            head = number
        seen[number] += 1
        if seen[number] > 1:
            number = f"{number}~{seen[number]}"
        st = stream(words)
        runs = frozenset(st[j:j + SHINGLE] for j in range(max(1, len(st) - SHINGLE + 1))) if st else frozenset()
        out.append(Unit(len(out), number, s.title, words, head, s.depth, st, runs))
    return out


def dice(a: frozenset[str], b: frozenset[str]) -> float:
    return 2 * len(a & b) / (len(a) + len(b)) if a and b else 0.0


def contained(part: frozenset[str], whole: frozenset[str]) -> float:
    """The share of ``part``'s runs found in ``whole``."""
    return len(part & whole) / len(part) if part else 0.0


def _alike(a: Unit, b: Unit) -> float:
    """How alike two sections with the same label are: the best of their word ratio, their shared runs, and the share
    of the shorter one's words the longer one holds (a rule that grew a clause is still the same rule)."""
    wa, wb = set(a.words.lower().split()), set(b.words.lower().split())
    short = min(len(wa), len(wb))
    held = len(wa & wb) / short if short >= 4 else 0.0
    return max(_ratio(a.words, b.words), dice(a.runs, b.runs), held)


def _ratio(a: str, b: str) -> float:
    wa, wb = a.lower().split(), b.lower().split()
    if not wa or not wb:
        return 0.0
    return difflib.SequenceMatcher(None, wa, wb, autojunk=False).ratio()


# ---------------------------------------------------------------------------------------------------------------------
# Word diff and flags.

_TOKEN = re.compile(r"\S+")
_NUMBER_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
                 "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty",
                 "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "half", "once",
                 "twice", "first", "second", "third"}
_TIME = {"day", "days", "hour", "hours", "week", "weeks", "month", "months", "year", "years", "annually", "monthly",
         "weekly", "daily", "pm", "am", "p.m.", "a.m.", "nightly", "minutes", "calendar", "business"}
_MONEY = {"dollar", "dollars", "cents"}
_FINE = {"fine", "fines", "fined", "fee", "fees", "penalty", "penalties", "charge", "charges", "charged", "interest",
         "late", "assessment", "assessments", "cost", "costs", "deposit", "sanction", "sanctions", "tow", "towed",
         "towing"}
_MODAL = {"shall", "may", "must", "should", "will", "not", "never", "cannot", "required", "prohibited", "permitted",
          "allowed", "optional"}


def _norm_token(t: str) -> str:
    return re.sub(r"^[^\w$]+|[^\w%]+$", "", t.lower())


@dataclass(frozen=True)
class WordOp:
    op: str                      # "replace", "delete", "insert"
    before: str
    after: str
    noise: bool = False
    flags: tuple[Flag, ...] = ()
    why: str = ""                # for noise: "ocr" (a near letter), "layout" (words found elsewhere, or a label)

    def row(self) -> dict[str, Any]:
        return {"op": self.op, "before": self.before, "after": self.after, "noise": self.noise,
                "flags": [f.value for f in self.flags], "why": self.why}


def _near(a: str, b: str) -> bool:
    """Two words OCR could confuse: a letter or two apart and of about the same length, no digits changed."""
    if re.search(r"\d", a + b) and re.sub(r"\D", "", a) != re.sub(r"\D", "", b):
        return False
    if abs(len(a) - len(b)) > 2:
        return False
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.75


def _flags(before: list[str], after: list[str], context: list[str]) -> tuple[Flag, ...]:
    changed = [_norm_token(t) for t in before + after]
    near = set(_norm_token(t) for t in context) | set(changed)
    out: set[Flag] = set()
    has_number = any(re.search(r"\d", t) or t in _NUMBER_WORDS for t in changed)
    if any("$" in t for t in before + after) or (set(changed) & _MONEY) or (has_number and ("$" in " ".join(context))):
        out.add(Flag.AMOUNT)
    if (has_number and near & _TIME) or (set(changed) & _TIME):
        out.add(Flag.DAYS)
    if (set(changed) & _FINE) or (has_number and near & _FINE):
        out.add(Flag.FINE)
    mb = Counter(t for t in (_norm_token(x) for x in before) if t in _MODAL)
    ma = Counter(t for t in (_norm_token(x) for x in after) if t in _MODAL)
    if mb != ma:
        out.add(Flag.MODAL)
    if has_number and not out & {Flag.AMOUNT, Flag.DAYS}:
        out.add(Flag.NUMBER)
    return tuple(f for f in FLAG_ORDER if f in out)


_LABEL_TOKEN = re.compile(r"^[(\[]?(?:[A-Za-z]|[ivxlIVXL]{1,5}|\d{1,2}|[A-Z]-\d{1,2})[.)\]]$|^[^A-Za-z0-9]+$")
LAYOUT_CHARS = 20            # letters and digits a stretch must hold before "found elsewhere" makes it layout


def _layout_side(words: list[str], other: str) -> bool:
    """A side of an op that is layout, not wording: list labels and marks only, or a stretch long enough to be
    known found elsewhere in the other version (a caption read into the next section, a moved paragraph)."""
    if not words:
        return True
    if all(_LABEL_TOKEN.match(w) for w in words):
        return True
    s = stream(" ".join(words))
    if not other or len(s) < LAYOUT_CHARS:
        return False
    if s in other:
        return True
    # A long stretch OCR misread in a few letters: nearly all of its runs are found in the other version.
    runs = {s[j:j + SHINGLE] for j in range(len(s) - SHINGLE + 1)}
    return len(s) >= 4 * LAYOUT_CHARS and len(runs & _runs_of(other)) >= 0.85 * len(runs)


@lru_cache(maxsize=16)
def _runs_of(text: str) -> frozenset[str]:
    return frozenset(text[j:j + SHINGLE] for j in range(len(text) - SHINGLE + 1))


def _ocr_slip(tag: str, wa: list[str], wb: list[str], flags: tuple[Flag, ...]) -> bool:
    """An op OCR explains: no number, amount, period, or modal touched, and either each word a near letter or two
    from its counterpart, or the two sides' letters alike (a word split or run together, "ofthe" for "of the",
    "Associa tion"), or a stray mark or two-letter fragment inserted or dropped."""
    if {Flag.AMOUNT, Flag.DAYS, Flag.MODAL, Flag.NUMBER} & set(flags):
        return False
    if tag == "replace":
        if len(wa) == len(wb) and all(_near(_norm_token(x), _norm_token(y)) for x, y in zip(wa, wb)):
            return True
        sa, sb = stream(" ".join(wa)), stream(" ".join(wb))
        return bool(sa and sb) and difflib.SequenceMatcher(None, sa, sb, autojunk=False).ratio() >= 0.85
    words = wa or wb
    return len(words) <= 2 and all(len(stream(w)) <= 2 for w in words)


def word_diff(before: str, after: str, *, ocr: bool = False, old: str = "", new: str = "") -> list[WordOp]:
    """The words that differ, each op with the flags it touches. Noise, never a change of words:

    - **layout**: an op whose removed words are found elsewhere in the new version (``new``, its letters and digits)
      and whose added words are found elsewhere in the old one (``old``), or that only adds or drops list labels;
    - **ocr** (with ``ocr``): each word a near letter or two from its counterpart, with no number and no modal changed.
    """
    a, b = _TOKEN.findall(before or ""), _TOKEN.findall(after or "")
    na, nb = [_norm_token(t) for t in a], [_norm_token(t) for t in b]
    ops: list[WordOp] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, na, nb, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        wa, wb = a[i1:i2], b[j1:j2]
        if stream(" ".join(wa)) == stream(" ".join(wb)):
            continue                                   # punctuation, case, or a word split differently
        context = a[max(0, i1 - 4):i2 + 4] + b[max(0, j1 - 4):j2 + 4]
        flags = _flags(wa, wb, context)
        why = ""
        if (old or new or all(_LABEL_TOKEN.match(w) for w in wa + wb)) and _layout_side(wa, new) \
                and _layout_side(wb, old):
            why = "layout"
        elif ocr and _ocr_slip(tag, wa, wb, flags):
            why = "ocr"
        ops.append(WordOp(tag, " ".join(wa), " ".join(wb), bool(why), () if why else flags, why))
    return ops


def words_found(words: str, other: str) -> bool:
    """Whether a whole section's words are found in another version (letters and digits): an added or removed
    section that only moved, or a caption the other version reads into the next section. A long section OCR misread
    in a few letters counts when nearly all of its runs are found."""
    s = stream(words)
    if not s or not other:
        return False
    return s in other or _layout_side(_TOKEN.findall(words), other)


def text_flags(words: str) -> tuple[Flag, ...]:
    """The flags an added or removed section's own words carry (an amount, a period, a fine), not its modals."""
    tokens = _TOKEN.findall(words or "")
    flags = set(_flags(tokens, [], tokens)) - {Flag.MODAL, Flag.NUMBER}
    return tuple(f for f in FLAG_ORDER if f in flags)


# ---------------------------------------------------------------------------------------------------------------------
# Alignment.

@dataclass
class Change:
    """What happened to one section between two versions."""

    kind: ChangeKind
    before: Unit | None
    after: Unit | None
    how: str = ""                                   # how the pair was made: words, label, opening, runs
    renumbered: bool = False
    moved: bool = False
    ops: list[WordOp] = field(default_factory=list)
    noise: bool = False                             # every difference is OCR or export noise
    flags: tuple[Flag, ...] = ()
    parts: list[Unit] = field(default_factory=list)    # a split's other parts, a merge's other pieces

    @property
    def real(self) -> bool:
        """A change to the words or the place of a section, not noise."""
        return self.kind is not ChangeKind.UNCHANGED and not self.noise

    def row(self) -> dict[str, Any]:
        def u(x: Unit | None) -> dict[str, Any] | None:
            return {"number": x.number, "title": x.title, "words": x.words} if x else None
        return {"kind": self.kind.value, "before": u(self.before), "after": u(self.after), "how": self.how,
                "renumbered": self.renumbered, "moved": self.moved, "noise": self.noise,
                "flags": [f.value for f in self.flags], "ops": [o.row() for o in self.ops],
                "parts": [p.number for p in self.parts]}


def _base(number: str) -> str:
    return number.split("~", 1)[0]


def align(a: Sequence[Unit], b: Sequence[Unit], *, ocr: bool = False) -> list[Change]:
    """Every unit of ``a`` and ``b`` in one change: paired (unchanged, reworded, moved, renumbered), split, merged,
    removed, or added. Pairs are made in order of confidence (see the module's notes); a miss stays a miss."""
    pair: dict[int, int] = {}
    how: dict[int, str] = {}
    free_b = set(range(len(b)))

    def take(i: int, j: int, why: str) -> None:
        pair[i] = j
        how[i] = why
        free_b.discard(j)

    # 1. The same words.
    by_stream: dict[str, list[int]] = defaultdict(list)
    for j, u in enumerate(b):
        if len(u.stream) >= 3:
            by_stream[u.stream].append(j)
    for i, u in enumerate(a):
        cands = [j for j in by_stream.get(u.stream, []) if j in free_b] if len(u.stream) >= 3 else []
        if cands:
            j = min(cands, key=lambda j: (_base(b[j].number) != _base(u.number), abs(j - i)))
            take(i, j, "words")
    # 2. The same label, with enough words in common.
    by_number: dict[str, list[int]] = defaultdict(list)
    for j, u in enumerate(b):
        by_number[u.number].append(j)
    for i, u in enumerate(a):
        if i in pair:
            continue
        cands = [j for j in by_number.get(u.number, []) if j in free_b]
        best = max(cands, key=lambda j: _ratio(u.words, b[j].words), default=None)
        if best is not None and _alike(u, b[best]) >= SAME_LABEL_MIN:
            take(i, best, "label")
    # 3. The same opening words.
    for i, u in enumerate(a):
        if i in pair or len(u.opening) < 12:
            continue
        cands = [(similarity(u.opening, b[j].opening), -abs(j - i), j) for j in free_b if len(b[j].opening) >= 12]
        cands = [c for c in cands if c[0] >= OPENING_MIN]
        if cands:
            take(i, max(cands)[2], "opening")
    # 4. Shared letter runs.
    scored = sorted(((dice(u.runs, b[j].runs), i, j) for i, u in enumerate(a) if i not in pair for j in free_b),
                    reverse=True)
    for score, i, j in scored:
        if score < RUNS_MIN:
            break
        if i in pair or j not in free_b:
            continue
        take(i, j, "runs")
    # 5. Splits and merges.
    changes: list[Change] = []
    split_parts: dict[int, list[int]] = defaultdict(list)
    for j in sorted(free_b):
        u = b[j]
        if len(u.runs) < 3:
            continue
        host = max(pair, key=lambda i: contained(u.runs, a[i].runs), default=None)
        if host is not None and contained(u.runs, a[host].runs) >= PART_MIN:
            split_parts[host].append(j)
    for parts in split_parts.values():
        for j in parts:
            free_b.discard(j)
    merged_into: dict[int, int] = {}
    for i, u in enumerate(a):
        if i in pair or len(u.runs) < 3:
            continue
        host = max(pair.values(), key=lambda j: contained(u.runs, b[j].runs), default=None)
        if host is not None and contained(u.runs, b[host].runs) >= PART_MIN:
            merged_into[i] = host
    # Moved: a pair out of the order the rest keep, or under another head.
    order = sorted(pair.items())
    keep = _increasing([j for _, j in order])
    in_order = {order[k][0] for k in keep}
    merged_hosts: dict[int, list[int]] = defaultdict(list)
    for i, j in merged_into.items():
        merged_hosts[j].append(i)
    old_all, new_all = "".join(u.stream for u in a), "".join(u.stream for u in b)
    for i, j in order:
        ua, ub = a[i], b[j]
        renumbered = _base(ua.number) != _base(ub.number)
        moved = i not in in_order or (_base(ua.head) != _base(ub.head) and not (renumbered and ua.depth == 1))
        parts = [b[x] for x in split_parts.get(i, [])] if i in split_parts else (
            [a[x] for x in merged_hosts.get(j, [])] if j in merged_hosts else [])
        changes.append(_pair_change(ua, ub, how[i], renumbered, moved, parts,
                                    ChangeKind.SPLIT if i in split_parts else (
                                        ChangeKind.MERGED if j in merged_hosts else None),
                                    ocr=ocr, old=old_all, new=new_all))
    for i, u in enumerate(a):
        if i not in pair and i not in merged_into:
            changes.append(Change(ChangeKind.REMOVED, u, None, noise=words_found(u.words, new_all),
                                  flags=text_flags(u.words)))
    for j in sorted(free_b):
        changes.append(Change(ChangeKind.ADDED, None, b[j], noise=words_found(b[j].words, old_all),
                              flags=text_flags(b[j].words)))
    changes.sort(key=lambda c: (c.after.index if c.after else (c.before.index if c.before else 0) + 0.5))
    return changes


def _pair_change(ua: Unit, ub: Unit, how: str, renumbered: bool, moved: bool, parts: list[Unit],
                 structural: ChangeKind | None, *, ocr: bool, old: str, new: str) -> Change:
    """One paired section's change: split or merged (``structural``), else reworded when a word changed that is not
    noise, else moved, renumbered, or unchanged."""
    ops = [] if ua.stream == ub.stream else word_diff(ua.words, ub.words, ocr=ocr, old=old, new=new)
    reworded = any(not o.noise for o in ops)
    if structural is not None:
        kind = structural
    elif reworded:
        kind = ChangeKind.REWORDED
    elif moved:
        kind = ChangeKind.MOVED
    elif renumbered:
        kind = ChangeKind.RENUMBERED
    else:
        kind = ChangeKind.UNCHANGED
    noise = bool(ops) and not reworded and kind is ChangeKind.UNCHANGED
    flags = tuple(f for f in FLAG_ORDER if any(f in o.flags for o in ops if not o.noise))
    return Change(kind, ua, ub, how, renumbered, moved, ops, noise, flags, parts)


def _increasing(seq: list[int]) -> list[int]:
    """The positions of a longest increasing subsequence of ``seq``."""
    if not seq:
        return []
    tails: list[int] = []
    tails_at: list[int] = []
    prev = [-1] * len(seq)
    import bisect

    for k, x in enumerate(seq):
        pos = bisect.bisect_left(tails, x)
        if pos == len(tails):
            tails.append(x)
            tails_at.append(k)
        else:
            tails[pos] = x
            tails_at[pos] = k
        prev[k] = tails_at[pos - 1] if pos else -1
    out, k = [], tails_at[-1]
    while k != -1:
        out.append(k)
        k = prev[k]
    return out[::-1]


def coverage(part: Iterable[Unit], whole: Iterable[Unit]) -> float:
    """The share of ``whole``'s runs that ``part`` holds."""
    pr = frozenset().union(*(u.runs for u in part)) if part else frozenset()
    wr = frozenset().union(*(u.runs for u in whole)) if whole else frozenset()
    return contained(wr, pr)


# ---------------------------------------------------------------------------------------------------------------------
# Lineage.

@dataclass
class Step:
    """One section of one lineage in one version."""

    version: int                 # the version's position in the chain
    unit: Unit
    change: Change | None        # how it came to be (None in the first version)


@dataclass
class Lineage:
    id: str                      # the permanent id: key@version-date/number
    first: int                   # the version it first appeared in
    steps: list[Step] = field(default_factory=list)
    ended: int | None = None     # the version it was removed in (or merged away)
    split_from: str = ""         # the lineage a split took it from
    merged_into: str = ""        # the lineage a merge put it in

    @property
    def last(self) -> Unit:
        return self.steps[-1].unit

    def unit_at(self, version: int) -> Unit | None:
        found = None
        for s in self.steps:
            if s.version <= version:
                found = s.unit
        if self.ended is not None and version >= self.ended:
            return None
        return found if self.steps and self.steps[0].version <= version else None


def permanent_id(key: str, version_label: str, number: str) -> str:
    """``key@label/number``; read through ``addresses.pid`` when it is there, so the two always agree."""
    try:
        from jason.community.addresses import pid

        return pid(key, version_label, number)
    except Exception:                       # the address module is not built, or the number is not an address path
        return f"{key}@{version_label or 'base'}/{number}"


def lineages(key: str, version_labels: Sequence[str], chain_units: Sequence[Sequence[Unit]],
             steps: Sequence[Sequence[Change]]) -> list[Lineage]:
    """Each unit followed through the chain: ``steps[k]`` aligns version k with version k + 1."""
    out: list[Lineage] = []
    by_unit: dict[tuple[int, int], Lineage] = {}
    for u in chain_units[0] if chain_units else ():
        lin = Lineage(permanent_id(key, version_labels[0], u.number), 0, [Step(0, u, None)])
        out.append(lin)
        by_unit[(0, u.index)] = lin
    for k, changes in enumerate(steps):
        nxt = k + 1
        for c in changes:
            if c.before is not None and c.after is not None:
                lin = by_unit.get((k, c.before.index))
                if lin is None:
                    continue
                lin.steps.append(Step(nxt, c.after, c))
                by_unit[(nxt, c.after.index)] = lin
                if c.kind is ChangeKind.SPLIT:
                    for p in c.parts:
                        new = Lineage(permanent_id(key, version_labels[nxt], p.number), nxt,
                                      [Step(nxt, p, Change(ChangeKind.SPLIT, c.before, p, "runs"))],
                                      split_from=lin.id)
                        out.append(new)
                        by_unit[(nxt, p.index)] = new
                if c.kind is ChangeKind.MERGED:
                    for p in c.parts:
                        gone = by_unit.get((k, p.index))
                        if gone is not None:
                            gone.ended = nxt
                            gone.merged_into = lin.id
            elif c.before is not None:
                lin = by_unit.get((k, c.before.index))
                if lin is not None:
                    lin.ended = nxt
            elif c.after is not None and (nxt, c.after.index) not in by_unit:
                new = Lineage(permanent_id(key, version_labels[nxt], c.after.number), nxt, [Step(nxt, c.after, c)])
                out.append(new)
                by_unit[(nxt, c.after.index)] = new
    return out


def between(lin: Lineage, a: int, b: int, *, ocr: bool = False, old: str = "", new: str = "") -> Change | None:
    """The lineage's change from version ``a`` to version ``b`` (any versions between them skipped), or None when it
    is in neither. ``old`` and ``new`` are the two versions' letters and digits, for telling layout from wording."""
    ua, ub = lin.unit_at(a), lin.unit_at(b)
    if ua is None and ub is None:
        return None
    if ua is None:
        kind = ChangeKind.SPLIT if lin.split_from and lin.first > a else ChangeKind.ADDED
        return Change(kind, None, ub, noise=words_found(ub.words, old) if ub else False,
                      flags=text_flags(ub.words) if ub else ())
    if ub is None:
        kind = ChangeKind.MERGED if lin.merged_into else ChangeKind.REMOVED
        return Change(kind, ua, None, noise=words_found(ua.words, new), flags=text_flags(ua.words))
    renumbered = _base(ua.number) != _base(ub.number)
    moved = any(s.change is not None and s.change.moved for s in lin.steps if a < s.version <= b)
    return _pair_change(ua, ub, "lineage", renumbered, moved, [], None, ocr=ocr, old=old, new=new)


# ---------------------------------------------------------------------------------------------------------------------
# Dates a version's words or its file name print.

_MONTHS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                           "september", "october", "november", "december"])}
_MONTH_RE = r"(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\.?"
_PRINTED = re.compile(
    r"\b(revised|adopted|effective|amended|approved|updated|restated|rev\.?)\b[^.\n]{0,40}?"
    rf"(?:{_MONTH_RE}\s+(\d{{1,2}}),?\s+(\d{{4}})|(\d{{1,2}})/(\d{{1,2}})/(\d{{2,4}})|{_MONTH_RE}\s+(\d{{4}}))", re.I)


def _month(name: str) -> int:
    n = name.lower().rstrip(".")
    return next((v for k, v in _MONTHS.items() if k.startswith(n[:3])), 0)


def printed_dates(text: str) -> list[tuple[date, str]]:
    """Dates the words print with what they say happened ("Revised March 1, 2099", "Adopted 3/1/99"): a claim the
    document makes about itself, read as written."""
    out: list[tuple[date, str]] = []
    for m in _PRINTED.finditer(text or ""):
        try:
            if m.group(2):
                d = date(int(m.group(4)), _month(m.group(2)), int(m.group(3)))
            elif m.group(5):
                y = int(m.group(7))
                d = date(y + 2000 if y < 100 else y, int(m.group(5)), int(m.group(6)))
            else:
                d = date(int(m.group(9)), _month(m.group(8)), 1)
        except (ValueError, TypeError):
            continue
        phrase = " ".join(m.group(0).split())
        if (d, phrase) not in out:
            out.append((d, phrase))
    return out


def name_dates(name: str) -> list[date]:
    """Dates a file name prints: "2099-11-20", "2099.1.04", or six digits read as YYMMDD or MMDDYY when only one
    reading is a date ("991120", "022699"). An ambiguous six digits gives nothing."""
    out: list[date] = []
    for m in re.finditer(r"(?<!\d)(\d{4})[-._](\d{1,2})[-._](\d{1,2})(?!\d)", name):
        try:
            out.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            pass
    for m in re.finditer(r"(?<![\d.])(\d{6})(?!\d|\.\d)", name):
        s = m.group(1)
        readings = []
        for y, mo, d in ((s[0:2], s[2:4], s[4:6]), (s[4:6], s[0:2], s[2:4])):
            try:
                readings.append(date(2000 + int(y), int(mo), int(d)))
            except ValueError:
                pass
        if len(readings) == 1:
            out.append(readings[0])
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Which files are a version of a document.

VERSION_WORDS = {"draft", "final", "revised", "rev", "adopted", "proposed", "copy", "clean", "redline", "signed",
                 "current", "updated", "version", "v", "the", "of", "and", "a", "new", "old", "amended", "restated",
                 "pdf", "docx", "doc", "md"}


@dataclass(frozen=True)
class RevisionSeries:
    """A document whose versions jason compares, as the profile names it: its key (an outline key), and patterns for
    file names that hold a version beyond its title and aliases (a first printing's own name). ``exclude`` names
    files that match but are not a version. Every candidate must also share its words with the current text."""

    key: str
    names: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    note: str = ""


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower().replace("'", "").replace("’", ""))


def name_matches(name: str, phrases: Iterable[str], *, extra: Iterable[str] = (), exclude: Iterable[str] = (),
                 allowed: Iterable[str] = ()) -> bool:
    """Whether a file's name names a version of a document: it holds one of the document's names (its title or an
    alias), and its other words are version words ("draft", "revised"), dates, or ``allowed`` (the association's own
    name). A parenthesized note in a name ("(scanned copy)") is not read. ``extra`` patterns match on their own;
    ``exclude`` patterns rule a name out."""
    if any(re.search(p, name, re.I) for p in exclude):
        return False
    if any(re.search(p, name, re.I) for p in extra):
        return True
    bare = re.sub(r"\([^)]*\)", " ", name)
    bare = re.sub(r"\.(pdf|docx?|md|txt)$", "", bare.strip(), flags=re.I)
    words = _words(bare)
    okay = VERSION_WORDS | {w for a in allowed for w in _words(a)}
    for phrase in phrases:
        pw = _words(phrase)
        if not pw:
            continue
        joined, target = " ".join(words), " ".join(pw)
        if f" {target} " not in f" {joined} ":
            continue
        rest = list(words)
        for w in pw:
            if w in rest:
                rest.remove(w)
        if all(w in okay or w in pw for w in rest):
            return True
    return False


__all__ = ["ChangeKind", "Change", "Flag", "Lineage", "RevisionSeries", "Step", "Unit", "WordOp", "align", "between",
           "clean", "contained", "coverage", "dice", "docx_text", "lineages", "name_dates", "name_matches",
           "outline_text", "permanent_id", "printed_dates", "slug", "strip_furniture", "text_flags", "text_hash",
           "units", "word_diff", "VERSION_MIN", "PARTIAL_BELOW"]
