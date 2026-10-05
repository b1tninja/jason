"""Passages cut on a document's sections, not on a fixed count of words.

``passages.passages_of`` cuts an extract into 220-word windows that overlap by 40. A window ignores the document's
structure: it splits a section in two and packs the tail of one subsection with the head of the next, so a short
definition, a fee table, or a form page shares its passage with unrelated words. This module cuts on the structure:

- **The headings.** Where they come from, best first:
  - the document's outline on disk (``data/outlines/<key>.json``, the Doc as ``jason outlines`` read it), matched to the
    extract by its Drive id, its library path, or its name, and placed on the extract by aligning the two texts word by
    word (a Doc export drops the list numbers the outline keeps, so the outline gives a section its number back);
  - the section labels ``outline_labels.outline_from_ocr`` reads in the text ("ARTICLE 7", "7.4", "(c)");
  - Markdown headings ("## Insurance") and short all-capital lines ("FINE SCHEDULE"), except a line repeated on every
    page (a running header).
- **The path.** Each passage carries its section's path as a short prefix, ``Passage.heading``: the document's title,
  then the numbers and captions of the sections it sits in ("Bylaws > 7 MEETINGS > 7.2 Notice of Meetings"). The
  rankers read the prefix with the words (``Passage.ranked``); ``Passage.text`` stays the document's own words, a slice
  of the extract, so a recitation is exact.
- **The size.** A section is one passage up to ``MAX_WORDS``; a longer one splits on its paragraphs (then its lines,
  then, for a paragraph with no breaks, word windows).
- **Tables.** A Markdown table stays with its heading row: a table too long for one passage splits by rows, and each
  piece starts with the heading row.
- **No structure.** A text with no headings at all is cut into the old windows (``passages.passages_of``).
- **A minimum** (``MIN_PASSAGE_WORDS``, or ``min_words``; see the constant for what is in use and why). A passage
  with a few words ranks well, because its few words match a question, and a heading or a section's last line says
  nothing alone. With a minimum above 0, a passage under it joins a neighbour in the same file (``_join``):
  - a heading with under three words of its own joins the passage after it, and its label joins that passage's
    path (the last three, when a scan's shouted words make a run of them); the last one in a file has nothing
    after it, so its words join the passage before and its label is dropped;
  - any other short passage (a split section's last lines, a one-line definition, a list item) joins the neighbour
    it shares more of its section path with, then the shorter neighbour, then the one before;
  - the joined passage is a slice of the extract with every word in order, its path carries each section's label
    (a law page's sections are still found by their labels, ``context_pack.index_law_ranking``), and it is never
    longer than ``MAX_WORDS`` plus the minimum but for a heading's own line; a short passage with no neighbour
    that has room stays as it is, and so does a file that is one short passage;
  - a ``<<PAGE n>>`` line (a publication's text, one before each page) is a break with no label: the sections
    above it end there, it leads the passage its page starts in, and it is not counted as words. A page with
    under the minimum joins a neighbour like any short passage, so a mark is never a passage or a heading.
- **The cut before.** With a minimum of 0 the cut is the one measured on October 2, 2026: a page mark is an
  all-capital heading, a heading with no words joins the section after it and its label is dropped, and runs of
  sections under ``MIN_WORDS`` words join each other.

It is search, not extraction: a section's number in a heading is the outline's or the label reader's reading, and a
miss stays a miss.
"""

from __future__ import annotations

import bisect
import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from jason.community.passages import PASSAGE_WORDS, Passage, passages_of

MAX_WORDS = PASSAGE_WORDS       # a section longer than this splits on its paragraphs
MIN_WORDS = 8                   # the cut before: runs of sections shorter than this join each other
# A passage with fewer words than this joins a neighbour; 0 is the cut before (see the module's notes). The index
# stores it in each file's cut signature (``cut_signature``), so changing it re-cuts every file at the next build
# (``jason index --build``), and every passage whose words or path changed is embedded again.
# Off, measured October 4, 2026 on the three gold sets over the core catalogs (docs/document-tools.md, model trials):
# 20 is the smallest minimum that leaves no passage under 20 words in a hybrid top 5 (44 slots in 39 of 190 questions
# before), and it took pooled hybrid recall@5 from 0.863 to 0.874 but MRR@10 from 0.736 to 0.728, more than the one
# question's worth allowed, as six answers that led fell to second place behind a passage a stub had sat above. Set
# 20 to trade that for no stubs; 8 and 10 cost nothing measurable and remove only the headings and crumbs.
MIN_PASSAGE_WORDS = 0
CAPTION_WORDS = 10              # a caption in the path is cut to this many words
PATH_LEVELS = 3                 # the innermost levels of the path kept in the prefix
MIN_ALIGNED = 0.5               # an outline is placed on an extract only when this share of its words align

_META = re.compile(r"^- [a-z_]+: ")
_MD_HEADING = re.compile(r"^(#{1,6})\s+(\S.*?)\s*#*\s*$")
_TABLE_RULE = re.compile(r"^\|?[\s:|-]+\|[\s:|-]*$")
_FURNITURE = re.compile(r"^(?:page\s+[\w.-]+|\d{1,4}|[ivxl]{1,6}|-\s*\d+\s*-)$", re.I)
_LABEL = re.compile(r"^\s*(?:article\s+[\divxlc]+\b[.:\s-]*|section\s+\d+(?:\.\d+)*\.?|\d+(?:\.\d+)+\.?|\(\w{1,4}\)|[A-Z]-\d+\.?)\s*", re.I)
_SENTENCE_END = re.compile(r"(?<=[a-z0-9)])\.(?:\s|$)")
_PAGE_MARK = re.compile(r"^[ \t]*<<PAGE \d+>>[ \t]*$", re.M)        # a publication's text: one before each page


def cut_signature(chunking: str = "sections", min_words: int | None = None) -> str:
    """How a file was cut, as the index stores it: "sections/min25" for the section cut with its minimum, and the
    bare name for the windows and for the cut before. A file whose stored signature differs is cut again."""
    minimum = MIN_PASSAGE_WORDS if min_words is None else min_words
    return f"{chunking}/min{minimum}" if chunking == "sections" and minimum > 0 else chunking


def _sans_marks(text: str) -> str:
    return _PAGE_MARK.sub("", text)


@dataclass(frozen=True)
class Head:
    """A heading placed on the extract: where its line starts, its number and caption, and its depth (1 the top)."""

    start: int
    number: str = ""
    caption: str = ""
    depth: int = 1
    source: str = ""                # "outline", "labels", "markdown", "caps"

    @property
    def label(self) -> str:
        """"7.4 Garage Doors"; the number once when the caption already prints it ("ARTICLE 4 - USE RESTRICTIONS")."""
        if self.number and re.search(r"(?<![\w.])" + re.escape(self.number) + r"(?![\w])", self.caption[:40]):
            return self.caption
        return " ".join(part for part in (self.number, self.caption) if part)


# --- the extract's header -------------------------------------------------------------------------------------------


def export_header(text: str) -> tuple[str, dict[str, str], int]:
    """The title, the metadata, and where the body starts, for an extract that opens with "# Title" and "- key: `value`"
    lines (the Drive exports); a text without a "# " first line has no title and its body starts at 0. A title line
    followed by no metadata is the document's own heading and stays in the body."""
    first, _, _ = text.partition("\n")
    if not first.startswith("# "):
        return "", {}, 0
    title = first[2:].strip()
    meta: dict[str, str] = {}
    at = len(first) + 1
    end = at
    for line in text[at:].splitlines(keepends=True):
        stripped = line.strip()
        if _META.match(stripped):
            key, _, value = stripped[2:].partition(": ")
            meta[key] = value.strip().strip("`")
        elif stripped:
            break
        end += len(line)
    if not meta:
        return title, {}, 0
    return title, meta, end


def display_title(path: Path, title: str = "") -> str:
    name = title or path.name
    for suffix in (".md", ".txt", ".pdf", ".docx"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()


# --- outlines on disk -----------------------------------------------------------------------------------------------


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


class OutlineIndex:
    """The outlines in a folder (``data/outlines/*.json``), found for an extract by its Drive id, its library file name,
    or a name (the outline's key, title, or an alias equal to the extract's title or file stem)."""

    def __init__(self, outlines: Iterable[dict[str, Any]] = ()) -> None:
        self.by_source: dict[str, dict[str, Any]] = {}
        self.by_file: dict[str, dict[str, Any]] = {}
        self.by_name: dict[str, dict[str, Any]] = {}
        for outline in outlines:
            if not outline.get("sections"):
                continue
            if outline.get("source"):
                self.by_source[outline["source"]] = outline
            if outline.get("library"):
                self.by_file[_norm_name(Path(outline["library"]).name)] = outline
            for name in [outline.get("key", ""), outline.get("title", ""), *(outline.get("aliases") or [])]:
                if name:
                    self.by_name.setdefault(_norm_name(name), outline)

    @classmethod
    def load(cls, folder: Path | str | None) -> "OutlineIndex":
        found: list[dict[str, Any]] = []
        root = Path(folder) if folder else None
        if root and root.is_dir():
            for path in sorted(root.glob("*.json")):
                if path.name == "references.json":
                    continue
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if isinstance(data, dict) and data.get("text") and isinstance(data.get("sections"), list):
                    found.append(data)
        return cls(found)

    def find(self, path: Path, title: str = "", meta: dict[str, str] | None = None) -> dict[str, Any] | None:
        meta = meta or {}
        if meta.get("drive_id") and meta["drive_id"] in self.by_source:
            return self.by_source[meta["drive_id"]]
        stem = path.name[:-3] if path.name.lower().endswith(".md") else path.name
        if (hit := self.by_file.get(_norm_name(stem))) is not None:
            return hit
        for name in (display_title(path, title), display_title(path)):
            if (hit := self.by_name.get(_norm_name(name))) is not None:
                return hit
        return None


# --- placing headings -----------------------------------------------------------------------------------------------

_WORD = re.compile(r"\S+")


def _words(text: str) -> tuple[list[int], list[str]]:
    starts: list[int] = []
    forms: list[str] = []
    for m in _WORD.finditer(text):
        form = re.sub(r"[^a-z0-9]", "", m.group(0).lower())
        if form:
            starts.append(m.start())
            forms.append(form)
    return starts, forms


def align_offsets(source: str, target: str, offsets: Sequence[int], *, reach: int = 12) -> tuple[list[int | None], float]:
    """Each offset in ``source`` placed in ``target`` by aligning their words (case and punctuation aside), and the
    share of ``source``'s words that aligned. An offset whose word did not align takes the next aligned word within
    ``reach`` words, or ``None``."""
    a_starts, a = _words(source)
    b_starts, b = _words(target)
    if not a or not b:
        return [None] * len(offsets), 0.0
    blocks = [blk for blk in difflib.SequenceMatcher(None, a, b).get_matching_blocks() if blk.size]
    aligned = sum(blk.size for blk in blocks) / len(a)
    block_a = [blk.a for blk in blocks]
    out: list[int | None] = []
    for offset in offsets:
        i = bisect.bisect_left(a_starts, offset)
        placed: int | None = None
        k = bisect.bisect_right(block_a, i) - 1
        if k >= 0 and blocks[k].a <= i < blocks[k].a + blocks[k].size:
            placed = b_starts[blocks[k].b + i - blocks[k].a]
        elif k + 1 < len(blocks) and blocks[k + 1].a - i <= reach:
            placed = b_starts[blocks[k + 1].b]
        out.append(placed)
    return out, aligned


def _line_start(text: str, offset: int, *, lead: int = 12) -> int:
    """The start of the line ``offset`` is on, when only a short lead ("#### ", "1.2 ", "- ") comes before it."""
    start = text.rfind("\n", 0, offset) + 1
    return start if offset - start <= lead else offset


def _caption(title: str, *, numbered: bool = False) -> str:
    """A heading's caption for the path. A numbered section's "title" is often its paragraph's opening words (a list
    item has no caption): its first sentence is the caption when that is short ("Owner" of "Owner. 'Owner' means
    ..."), else the number stands alone, so the prefix does not repeat the passage's words."""
    title = title.strip()
    if numbered:
        title = _SENTENCE_END.split(title, maxsplit=1)[0]
        if len(title.split()) > CAPTION_WORDS:
            return ""
    words = title.rstrip(".:").split()
    return " ".join(words[:CAPTION_WORDS]) + (" ..." if len(words) > CAPTION_WORDS else "")


def heads_from_outline(text: str, outline: dict[str, Any], body_start: int = 0) -> list[Head]:
    """The outline's sections placed on ``text`` (empty when too little of the outline aligns with it)."""
    sections = outline.get("sections") or []
    if not sections:
        return []
    placed, aligned = align_offsets(outline.get("text") or "", text[body_start:], [int(s.get("start") or 0) for s in sections])
    if aligned < MIN_ALIGNED:
        return []
    out: list[Head] = []
    for section, at in zip(sections, placed):
        if at is None:
            continue
        out.append(Head(_line_start(text, body_start + at), str(section.get("number") or ""),
                        _caption(str(section.get("title") or ""), numbered=bool(section.get("number"))),
                        int(section.get("depth") or 1), "outline"))
    return out


def heads_from_labels(text: str, body_start: int = 0) -> list[Head]:
    """The section labels the OCR label reader finds ("ARTICLE 7", "7.4", "(c)"). Its text is the extract normalized
    line for line, so a section is placed by its line."""
    from jason.community.outline_labels import outline_from_ocr

    body = text[body_start:]
    try:
        reading = outline_from_ocr(body, key="")
    except Exception:  # noqa: BLE001 - a reader's slip is a miss, not a failure of the search
        return []
    read_lines = reading.text.splitlines(keepends=True)
    own_lines = body.splitlines(keepends=True)
    read_starts, at = [], 0
    for line in read_lines:
        read_starts.append(at)
        at += len(line)
    own_starts, at = [], body_start
    for line in own_lines:
        own_starts.append(at)
        at += len(line)
    sections = reading.outline().sections
    if len(read_lines) == len(own_lines):
        lines_at = [bisect.bisect_right(read_starts, s.start) - 1 for s in sections]
    else:                                   # the reader moved a label between lines: place each by its words
        placed, _ = align_offsets(reading.text, body, [s.start for s in sections])
        lines_at = [bisect.bisect_right(own_starts, body_start + p) - 1 if p is not None else -1 for p in placed]
    out: list[Head] = []
    for section, i in zip(sections, lines_at):
        if i < 0:
            continue
        line = own_lines[i].strip()
        caption = section.title or _LABEL.sub("", line, count=1)
        out.append(Head(own_starts[i], section.number, _caption(caption, numbered=True), section.depth, "labels"))
    return out


def _caps(line: str) -> bool:
    s = line.strip().strip("#*_ ").strip()
    if not 3 <= len(s) <= 80 or s.startswith("|") or _FURNITURE.match(s):
        return False
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 4:
        return False
    return sum(c.isupper() for c in letters) / len(letters) >= 0.85 and len(s.split()) <= 10 and not s.endswith((",", ";"))


def heads_from_lines(text: str, body_start: int = 0, *, page_marks: bool = False) -> list[Head]:
    """Markdown headings, and short all-capital lines that are not repeated page furniture. A page mark is a break
    with no label (source "mark"): the sections above it end there, as they did when it was a heading, and it names
    nothing. With ``page_marks`` it is the all-capital heading the cut before took it for."""
    lines: list[tuple[int, str]] = []
    at = body_start
    for raw in text[body_start:].splitlines(keepends=True):
        lines.append((at, raw.rstrip("\r\n")))
        at += len(raw)
    seen: dict[str, int] = {}
    for _, line in lines:
        key = _norm_name(line)
        if key:
            seen[key] = seen.get(key, 0) + 1
    out: list[Head] = []
    for start, line in lines:
        if not page_marks and _PAGE_MARK.fullmatch(line):
            out.append(Head(start, "", "", 1, "mark"))
            continue
        if m := _MD_HEADING.match(line):
            out.append(Head(start, "", _caption(m.group(2)), len(m.group(1)), "markdown"))
        elif _caps(line) and seen.get(_norm_name(line), 0) < 3:
            out.append(Head(start, "", _caption(line), 1, "caps"))
    return out


def heads_of(path: Path, text: str, *, outlines: OutlineIndex | None = None,
             page_marks: bool = False) -> tuple[str, int, list[Head]]:
    """The document's title, where its body starts, and its headings in order (one a line; an outline's or a label's
    number wins over a bare caption on the same line)."""
    title, meta, body_start = export_header(text)
    outline = outlines.find(path, title, meta) if outlines is not None else None
    heads: list[Head] = []
    if outline is not None:
        heads = heads_from_outline(text, outline, body_start)
    if not heads:
        outline = None                      # named alike but not the same text: neither its sections nor its title
        heads = heads_from_labels(text, body_start)
    heads += heads_from_lines(text, body_start, page_marks=page_marks)
    by_line: dict[int, Head] = {}
    rank = {"mark": -1, "outline": 0, "labels": 1, "markdown": 2, "caps": 3}
    for head in heads:
        if head.start < body_start:
            continue
        held = by_line.get(head.start)
        if held is None or rank.get(head.source, 9) < rank.get(held.source, 9):
            by_line[head.start] = head
    ordered = [by_line[k] for k in sorted(by_line)]
    # "ARTICLE 1" then "DEFINITIONS" on the next line: one heading, the second line its caption.
    merged: list[Head] = []
    for head in ordered:
        prev = merged[-1] if merged else None
        if (prev is not None and prev.number and not prev.caption and not head.number and head.source in ("caps", "markdown")
                and "\n" not in text[prev.start: head.start].rstrip("\n")):
            merged[-1] = Head(prev.start, prev.number, head.caption, prev.depth, prev.source)
            continue
        merged.append(head)
    name = display_title(path, (outline or {}).get("title") or title)
    return name, body_start, merged


# --- cutting --------------------------------------------------------------------------------------------------------


@dataclass(eq=False)
class _Segment:
    start: int
    end: int
    path: tuple[str, ...]
    before: tuple[tuple[str, ...], ...] = ()       # the paths of the headings with no words joined in front of it


def _word_count(text: str) -> int:
    return len(text.split())


def _heading_only(own: str) -> bool:
    """The cut before's reading of a heading with no words of its own: its line (six words at most after its label),
    and under three words more."""
    first, _, rest = own.strip().partition("\n")
    return _word_count(rest) < 3 and _word_count(_LABEL.sub("", first, count=1)) <= 6


def _heading_lines(text: str, heads: Sequence[Head]) -> frozenset[int]:
    """Where the lines that are a heading and nothing more start: a Markdown or all-capital heading whatever its
    length, and a numbered line of six words at most after its label ("7.4 Garage Doors", "(b) the Tenant;"). A
    longer numbered line is its section's first words, and a page mark is no heading."""
    found: set[int] = set()
    for head in heads:
        if head.source in ("markdown", "caps"):
            found.add(head.start)
        elif head.source != "mark":
            end = text.find("\n", head.start)
            line = text[head.start: len(text) if end < 0 else end]
            if _word_count(_LABEL.sub("", line.strip(), count=1)) <= 6:
                found.add(head.start)
    return frozenset(found)


def _own_words(text: str, start: int, end: int, heading_lines: frozenset[int]) -> tuple[int, int]:
    """The heading lines in a slice, and its words on every other line (page marks aside)."""
    at, lines, words = start, 0, 0
    for raw in text[start:end].splitlines(keepends=True):
        if at in heading_lines:
            lines += 1
        elif not _PAGE_MARK.fullmatch(raw.strip()):
            words += _word_count(raw)
        at += len(raw)
    return lines, words


def _segments(text: str, body_start: int, heads: Sequence[Head], *,
              heading_lines: frozenset[int] | None = None) -> list[_Segment]:
    """The text between one heading and the next, each with its path (a page mark starts one with no label of its
    own, so a page's mark leads the page's words). With ``heading_lines`` it is the cut with a minimum: a heading
    with under three words of its own keeps its label when it joins the section after it, and short sections are
    joined later, passage by passage (``_join``). Without, the cut before."""
    joined = heading_lines is not None
    stack: list[Head] = []
    segments: list[_Segment] = []
    if heads and heads[0].start > body_start and text[body_start: heads[0].start].strip():
        segments.append(_Segment(body_start, heads[0].start, ()))
    for i, head in enumerate(heads):
        while stack and stack[-1].depth >= head.depth:
            stack.pop()
        stack.append(head)
        end = heads[i + 1].start if i + 1 < len(heads) else len(text)
        segments.append(_Segment(head.start, end, tuple(h.label for h in stack if h.label)))
    # A heading with no words of its own (an article's title, a run of contents lines) joins the section after it.
    merged: list[_Segment] = []
    pending: int | None = None
    held: list[tuple[str, ...]] = []
    for k, seg in enumerate(segments):
        if joined:
            bare = _own_words(text, seg.start, seg.end, heading_lines)[1] < 3
        else:
            bare = _heading_only(text[seg.start: seg.end])
        if k + 1 < len(segments) and bare:
            pending = seg.start if pending is None else pending
            held.append(seg.path)
            continue
        if pending is not None:
            seg = _Segment(pending, seg.end, seg.path, tuple(held) if joined else ())
            pending = None
            held = []
        merged.append(seg)
    if joined:
        return merged
    # Runs of tiny sections ("(a) the Owner;") join each other; the run keeps the path the members share.
    out: list[_Segment] = []
    for seg in merged:
        tiny = _word_count(text[seg.start: seg.end]) < MIN_WORDS
        if out and tiny and _word_count(text[out[-1].start: out[-1].end]) < MAX_WORDS:
            prev = out[-1]
            shared = []
            for a, b in zip(prev.path, seg.path):
                if a != b:
                    break
                shared.append(a)
            out[-1] = _Segment(prev.start, seg.end, tuple(shared))
        else:
            out.append(seg)
    return out


@dataclass
class _Unit:
    start: int
    end: int
    words: int
    header: str = ""                # a table row's heading row (with its rule line)
    has_header: bool = False        # the unit's own slice starts with that heading row


def _units(text: str, start: int, end: int) -> list[_Unit]:
    """The pieces a long section may split between: its paragraphs, and a table's rows (each knowing the table's
    heading row; the first row's slice carries it)."""
    units: list[_Unit] = []
    para: int | None = None
    table: list[tuple[int, str]] = []          # (offset, raw line) of the current table

    def close_para(upto: int) -> None:
        nonlocal para
        if para is not None and text[para:upto].strip():
            units.append(_Unit(para, upto, _word_count(text[para:upto])))
        para = None

    def close_table() -> None:
        if not table:
            return
        head = 2 if len(table) > 1 and _TABLE_RULE.match(table[1][1].strip()) else 1
        header = "\n".join(raw.strip() for _, raw in table[:head])
        first_end = table[min(head, len(table) - 1)]
        units.append(_Unit(table[0][0], first_end[0] + len(first_end[1]),
                           _word_count(text[table[0][0]: first_end[0] + len(first_end[1])]), header, True))
        for at, raw in table[head + 1:]:
            units.append(_Unit(at, at + len(raw), _word_count(raw), header))
        table.clear()

    at = start
    for raw in text[start:end].splitlines(keepends=True):
        line = raw.strip()
        if line.startswith("|"):
            close_para(at)
            table.append((at, raw))
        else:
            close_table()
            if not line:
                close_para(at)
            elif para is None:
                para = at
        at += len(raw)
    close_para(at)
    close_table()
    return units


def _windows(text: str, start: int, end: int, max_words: int) -> list[_Unit]:
    words = list(re.finditer(r"\S+", text[start:end]))
    out = []
    for i in range(0, len(words), max_words):
        chunk = words[i: i + max_words]
        out.append(_Unit(start + chunk[0].start(), start + chunk[-1].end(), len(chunk)))
    return out


def _pieces(text: str, seg: _Segment, max_words: int) -> list[tuple[int, int, str]]:
    """(start, end, heading row to put first) for each passage of a section: the section whole, or its paragraphs and
    table rows packed up to ``max_words``."""
    own = text[seg.start: seg.end]
    if _word_count(own) <= max_words:
        return [(seg.start, seg.end, "")]
    flat: list[_Unit] = []
    for unit in _units(text, seg.start, seg.end):
        if unit.words <= max_words or unit.header:
            flat.append(unit)
            continue
        at = unit.start                           # a paragraph longer than a passage: its lines, then windows
        for raw in text[unit.start: unit.end].splitlines(keepends=True):
            n = _word_count(raw)
            if n > max_words:
                flat += _windows(text, at, at + len(raw), max_words)
            elif n:
                flat.append(_Unit(at, at + len(raw), n))
            at += len(raw)
    out: list[tuple[int, int, str]] = []
    cur: list[_Unit] = []
    count = 0

    def flush() -> None:
        nonlocal cur, count
        if cur:
            lead = cur[0]
            out.append((lead.start, cur[-1].end, lead.header if lead.header and not lead.has_header else ""))
        cur, count = [], 0

    for unit in flat:
        if cur and count + unit.words > max_words:
            flush()
        if not cur and unit.header and not unit.has_header:
            count += _word_count(unit.header)
        cur.append(unit)
        count += unit.words
    flush()
    return out


@dataclass
class _Piece:
    """A passage being cut: a slice of the text, the sections it holds, and whether it is only a heading."""

    start: int
    end: int
    header: str                         # a table's heading row, put first
    segs: tuple[_Segment, ...]          # the sections in it, in order
    bare: bool = False                  # a heading with no words of its own, or only page marks
    words: int = 0                      # its words, page marks aside

    def text(self, body: str) -> str:
        words = body[self.start: self.end].strip()
        return f"{self.header}\n{words}" if self.header else words


def _heading(title: str, segs: Sequence[_Segment]) -> str:
    """The path a passage carries: the title, then each of its sections' labels (the innermost ``PATH_LEVELS`` of a
    section's path, after the last ``PATH_LEVELS`` headings with no words joined in front of it), each label once."""
    labels: list[str] = []
    for n, seg in enumerate(segs):
        shown = [label for label in seg.path if label.lower() != title.lower()][-PATH_LEVELS:]
        lead = [p[-1] for p in seg.before if p and p[-1].lower() != title.lower() and p[-1] not in shown]
        own = [*list(dict.fromkeys(lead))[-PATH_LEVELS:], *shown]
        labels += own if n == 0 else [label for label in dict.fromkeys(own) if label not in labels]
    return " > ".join([title, *labels]) if title else " > ".join(labels)


def _shared(a: _Piece, b: _Piece) -> int:
    """How much of their section path two neighbours share (``a`` before ``b``): more than any path when ``b`` goes
    on in the section ``a`` ends in, else the labels their paths start with in common."""
    last, first = a.segs[-1], b.segs[0]
    if last is first:
        return len(last.path) + 1
    start = first.before[0] if first.before else first.path
    n = 0
    for x, y in zip(last.path, start):
        if x != y:
            break
        n += 1
    return n


def _join(pieces: Sequence[_Piece], body: str, min_words: int, max_words: int) -> list[_Piece]:
    """The pieces with none under ``min_words`` that a neighbour has room for (the module's notes, "A minimum")."""
    limit = max_words + min_words
    items = list(pieces)

    def joined(a: _Piece, b: _Piece, *, labels: bool = True) -> _Piece:
        segs = tuple(dict.fromkeys((*a.segs, *b.segs))) if labels else a.segs
        piece = _Piece(a.start, b.end, a.header, segs, a.bare and b.bare)
        piece.words = _word_count(_sans_marks(piece.text(body)))
        return piece

    # First every heading goes with what follows it, so that no short passage before a heading takes the heading from
    # its own words. The last one in the run has nothing after it: its words join the passage before, which it does
    # not head, so that passage's path does not take its label.
    i = 0
    while i < len(items):
        if not items[i].bare or len(items) == 1:
            i += 1
        elif i + 1 < len(items):
            items[i: i + 2] = [joined(items[i], items[i + 1])]          # read again: a run of headings
        else:
            items[i - 1: i + 1] = [joined(items[i - 1], items[i], labels=False)]
    i = 0
    while i < len(items):
        piece = items[i]
        before = items[i - 1] if i else None
        after = items[i + 1] if i + 1 < len(items) else None
        target: _Piece | None = None
        if piece.words < min_words:
            room = [n for n in (before, after) if n is not None and n.words + piece.words <= limit]
            if len(room) == 2:
                back, forward = _shared(before, piece), _shared(piece, after)
                if forward > back or (forward == back and after.words < before.words):
                    room = [after]
            target = room[0] if room else None
        if target is None:
            i += 1
        elif target is before:
            items[i - 1: i + 1] = [joined(before, piece)]      # the piece now at i is the one that followed
        else:
            items[i: i + 2] = [joined(piece, after)]           # read again: it may still be short
    return items


def section_passages(path: Path, text: str | None = None, *, outlines: OutlineIndex | None = None,
                     max_words: int = MAX_WORDS, min_words: int | None = None,
                     skip: Callable[[str], bool] | None = None) -> tuple[Passage, ...]:
    """One extract cut on its sections (see the module's notes); the old windows when it has no headings.

    ``min_words`` is the fewest words a passage may have before it joins a neighbour (``MIN_PASSAGE_WORDS`` when not
    given; 0 is the cut before). ``skip`` names passages to leave out by their words (a page's front matter): one is
    dropped before any joining, and nothing joins across it."""
    body = text if text is not None else path.read_text(encoding="utf-8", errors="ignore")
    body = body.replace("\r\n", "\n")
    minimum = MIN_PASSAGE_WORDS if min_words is None else min_words
    joined = minimum > 0
    title, body_start, heads = heads_of(path, body, outlines=outlines, page_marks=not joined)
    if not heads:
        return tuple(Passage(p.path, p.index, p.start_word, p.text, heading=title) for p in passages_of(path, body))
    heading_lines = _heading_lines(body, heads) if joined else None
    runs: list[list[_Piece]] = [[]]                 # the pieces in order, a new run after each one left out
    for seg in _segments(body, body_start, heads, heading_lines=heading_lines):
        for start, end, table_header in _pieces(body, seg, max_words):
            if not body[start:end].strip():
                continue
            piece = _Piece(start, end, table_header, (seg,))
            words = piece.text(body)
            if skip is not None and skip(words):
                runs.append([])
                continue
            if joined:
                piece.words = _word_count(_sans_marks(words))
                lines, own = _own_words(body, start, end, heading_lines)
                piece.bare = piece.words == 0 or (lines > 0 and own < 3 and not table_header)
            runs[-1].append(piece)
    found: list[Passage] = []
    word_at = _WordIndex(body)
    for run in runs:
        for piece in (_join(run, body, minimum, max_words) if joined else run):
            found.append(Passage(path, len(found), word_at(piece.start), piece.text(body), heading=_heading(title, piece.segs)))
    return tuple(found)


class _WordIndex:
    """The number of words before an offset."""

    def __init__(self, text: str) -> None:
        self.starts = [m.start() for m in re.finditer(r"\S+", text)]

    def __call__(self, offset: int) -> int:
        return bisect.bisect_left(self.starts, offset)


__all__ = ["Head", "OutlineIndex", "align_offsets", "export_header", "heads_from_labels", "heads_from_lines",
           "heads_from_outline", "heads_of", "section_passages", "cut_signature", "MAX_WORDS", "MIN_PASSAGE_WORDS",
           "MIN_WORDS"]
