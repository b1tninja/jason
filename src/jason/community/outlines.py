"""A document's outline: its sections, numbered as the document numbers them, each with its span of the text.

Other documents cite a governing document by section: "Section 7.2 of the Bylaws", "Declaration 6.5(b)",
"subsection 1.3(d)(ii), below". To follow a citation the section has to exist as a thing with that number. In the
association's Google Docs the numbers are not in the text: Docs draws them from the list a heading or paragraph belongs
to, so ``outline_from_doc`` renders them the way Docs does (each nesting level's glyph type and format) and writes the
number the way documents cite it: dotted while a level's format carries its parent ("7.2"), then in parentheses
("8.5(c)", "3.3(a)(i)"). A heading that prints its own number ("ARTICLE 4", "B-12. PARKING", "1.1 Definitions") keeps
it. A heading with no number is a section known by its title.

A ``Section`` spans from its start to the next section at its depth or shallower, so ``section_at`` finds the
innermost section around any place in the text. ``CitableDocument`` is a specification row: which Doc, what kind, and
the names other documents use for it.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from jason.community.documents import DocumentKind


@dataclass(frozen=True)
class CitableDocument:
    key: str                               # "bylaws"
    title: str
    drive_id: str                          # the Google Doc
    kind: DocumentKind
    aliases: tuple[str, ...] = ()          # names another document cites it by ("Declaration", "CC&Rs")
    amends: str = ""                       # the key of the document this one amends
    written: str = ""                      # when its text was adopted or last restated: "2007-09-17", or "2024" when the
                                           # evidence gives only the year; empty when unknown
    written_from: str = ""                 # the evidence for ``written``


@dataclass
class Section:
    number: str                            # "7.2", "8.5(c)", "3.3(a)(i)"; empty for a heading known only by its title
    title: str
    depth: int                             # 1 for an article or top heading
    start: int                             # offsets into DocumentOutline.text
    end: int = 0
    label: str = ""                        # as the document draws it ("8.5.", "c.")
    parent: str = ""

    @property
    def name(self) -> str:
        return self.number or self.title


@dataclass
class DocumentOutline:
    key: str
    title: str
    source: str = ""                       # the Drive id
    revision: str = ""                     # the Doc's revision when read
    kind: str = ""
    text: str = ""
    sections: list[Section] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)     # names other documents cite it by
    numbers: list[str] = field(default_factory=list)     # resolution numbers its headers print
    amends: str = ""                                      # the key of the document it amends
    library: str = ""                                     # the library path, for an outline read from an extract

    def section(self, number: str) -> Section | None:
        wanted = normalize_number(number)
        return next((s for s in self.sections if s.number == wanted), None)

    def section_at(self, offset: int) -> Section | None:
        inside = [s for s in self.sections if s.start <= offset < s.end]
        return max(inside, key=lambda s: (s.depth, s.start)) if inside else None

    def text_of(self, section: Section) -> str:
        return self.text[section.start:section.end]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> DocumentOutline:
        sections = [Section(**s) for s in raw.get("sections", [])]
        return cls(**{**raw, "sections": sections})


_ROMAN = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"), (10, "x"), (9, "ix"),
          (5, "v"), (4, "iv"), (1, "i")]


def _roman(n: int) -> str:
    out = ""
    for value, symbol in _ROMAN:
        while n >= value:
            out, n = out + symbol, n - value
    return out


def _glyph(n: int, kind: str) -> str:
    if kind == "UPPER_ALPHA":
        return chr(64 + n) if n <= 26 else str(n)
    if kind == "ALPHA":
        return chr(96 + n) if n <= 26 else str(n)
    if kind == "UPPER_ROMAN":
        return _roman(n).upper()
    if kind == "ROMAN":
        return _roman(n)
    return str(n)


def normalize_number(number: str) -> str:
    """A section number as documents cite it: "8.5 (c)" and "8.5.c" read as "8.5(c)"; a trailing period goes."""
    n = re.sub(r"\s+", "", number or "").rstrip(".")
    n = re.sub(r"\.([a-z]|[ivx]+)(?=$|\()", r"(\1)", n)
    return n


def _numbered(level: dict[str, Any]) -> bool:
    """A list level that numbers (decimal, alpha, roman), not a bullet glyph."""
    return bool(level.get("glyphFormat")) and "glyphSymbol" not in level


_ARTICLE = re.compile(r"^ARTICLE\s+([IVXLC]+|\d+)\b\s*[-–.:]?\s*(.*)$", re.I)
_OWN_NUMBER = re.compile(r"^((?:[A-Z]-)?\d+(?:\.\d+)*)[.)]?\s+(\S.*)$")
_TOKEN = re.compile(r"^\(?([A-Za-z]{1,4}|\d+)[.)]?$")


def _arabic(token: str) -> str:
    if token.isdigit():
        return token
    values = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
    total, prev = 0, 0
    for ch in reversed(token.lower()):
        v = values.get(ch, 0)
        total, prev = (total - v, prev) if v < prev else (total + v, v)
    return str(total)


def _paragraph_text(paragraph: dict[str, Any]) -> str:
    return "".join(e.get("textRun", {}).get("content", "") for e in paragraph.get("elements", []))


def _paragraphs(content: list[dict[str, Any]]):
    for block in content:
        if "paragraph" in block:
            yield block["paragraph"]
        elif "table" in block:
            for row in block["table"].get("tableRows", []):
                for cell in row.get("tableCells", []):
                    yield from _paragraphs(cell.get("content", []))


def outline_from_doc(doc: dict[str, Any], *, key: str, title: str = "", kind: str = "") -> DocumentOutline:
    """The outline of a Google Doc (the Docs API's document): headings and numbered list paragraphs as sections."""
    tab = ((doc.get("tabs") or [{}])[0].get("documentTab")) or doc
    lists = tab.get("lists", {})
    out = DocumentOutline(key=key, title=title or doc.get("title", ""), source=doc.get("documentId", ""),
                          revision=doc.get("revisionId", ""), kind=kind)
    counters: dict[str, list[int]] = {}
    pieces: list[str] = []
    at = 0
    anchor = ""          # the innermost section a relative number ("c.") hangs from
    anchor_depth = 0
    for p in _paragraphs(tab.get("body", {}).get("content", [])):
        raw = _paragraph_text(p)
        text = raw.strip()
        style = p.get("paragraphStyle", {}).get("namedStyleType", "")
        heading = style.startswith("HEADING_")
        label, number, relative_tokens = "", "", []
        bullet = p.get("bullet")
        if bullet:
            list_id, level = bullet["listId"], int(bullet.get("nestingLevel", 0))
            levels = lists.get(list_id, {}).get("listProperties", {}).get("nestingLevels", [])
            counts = counters.setdefault(list_id, [0] * 9)
            counts[level] += 1
            for deeper in range(level + 1, 9):
                counts[deeper] = 0
            if level < len(levels) and _numbered(levels[level]):
                fmt = levels[level]["glyphFormat"]
                label = fmt
                for k in range(level, -1, -1):
                    label = label.replace(f"%{k}", _glyph(counts[k], levels[k].get("glyphType", "")))
                # Compose the number as documents cite it: dotted while a level's format carries its parent.
                composed = _glyph(counts[0], levels[0].get("glyphType", ""))
                for k in range(1, level + 1):
                    token = _glyph(counts[k], levels[k].get("glyphType", ""))
                    fmt_k = levels[k].get("glyphFormat", "") if k < len(levels) else ""
                    composed = f"{composed}.{token}" if f"%{k - 1}" in fmt_k else f"{composed}({token})"
                first_decimal = levels[0].get("glyphType", "DECIMAL") in ("DECIMAL", "ZERO_DECIMAL", "GLYPH_TYPE_UNSPECIFIED", "")
                if first_decimal and (heading or "." in composed.split("(")[0]):
                    number = composed
                else:
                    relative_tokens = [composed]
        if not number and not relative_tokens and heading and text:
            if m := _ARTICLE.match(text):
                number = _arabic(m.group(1))
            elif m := _OWN_NUMBER.match(text):
                number = m.group(1)
        start = at
        pieces.append(raw)
        at += len(raw)
        if not text:
            continue
        if relative_tokens and (heading or anchor):
            token = relative_tokens[0]
            head, _, rest = token.partition("(")
            number = f"{anchor}({head})" + (f"({rest}" if rest else "") if anchor else token
        elif relative_tokens:
            continue                      # a numbered list in running text with no section to hang from
        if not number and not heading:
            continue
        number = normalize_number(number)
        depth = (1 + number.count(".") + number.count("(")) if number else int(style[-1]) if heading else anchor_depth + 1
        if number and out.sections and out.sections[-1].number == number and out.sections[-1].depth == depth:
            # "ARTICLE 1" then "1. DEFINITIONS": one section, the second heading its title.
            out.sections[-1].title = text
            continue
        title = text if heading else text[:90]
        parent = ""
        if number and "(" in number:
            parent = number[: number.rfind("(")]
        elif number and "." in number:
            parent = number.rsplit(".", 1)[0]
        out.sections.append(Section(number=number, title=title, depth=depth, start=start, label=label.strip(), parent=parent))
        if number and (heading or "(" not in number):
            anchor, anchor_depth = number, depth
        elif heading and not number:
            anchor_depth = depth
    out.text = "".join(pieces)
    _close(out)
    return out


def outline_from_text(text: str, *, key: str, title: str = "", kind: str = "") -> DocumentOutline:
    """An outline read from plain text (a PDF's extract): lines that start with a section number, "ARTICLE n", or
    "(a)"-style subsections under the last numbered section. Rougher than a Doc's list numbering; a miss stays a miss."""
    # OCR spreads a scan's numbers: "13 .1", "1.3( d)(i)", "6.S(b)". Close them before reading the numbers.
    text = re.sub(r"(\d)\s+\.\s*(\d)", r"\1.\2", text)
    text = re.sub(r"\(\s+([a-zA-Z0-9]{1,4})\s*\)", r"(\1)", text)
    text = re.sub(r"(\d\.)S(?=[\s(\"])", r"\g<1>5", text)
    text = re.sub(r"(\d)\"\(", r"\1(", text)
    out = DocumentOutline(key=key, title=title, kind=kind, text=text)
    base = ""            # the last dotted section ("1.3")
    letter = ""          # the last lettered subsection under it ("d"), for "(i)" and "(ii)" below it
    at = 0
    for line in text.splitlines(keepends=True):
        s = line.strip()
        if m := _ARTICLE.match(s):
            number = _arabic(m.group(1))
            out.sections.append(Section(number, m.group(2) or s, 1, at))
            base, letter = number, ""
        elif m := re.match(r"^(\d+(?:\.\d+)+)\.?\s+(\S.{0,120})", s):
            number = m.group(1)
            out.sections.append(Section(number, m.group(2), 1 + number.count("."), at, parent=number.rsplit(".", 1)[0]))
            base, letter = number, ""
        elif base and (m := re.match(r"^\(([a-z]{1,4}|\d{1,2})\)\s+(\S.{0,120})", s, re.I)):
            token = m.group(1).lower()
            roman = re.fullmatch(r"[ivx]+", token) is not None
            # "(i)" after "(h)" is the next letter; after any other letter it is the first roman subsection.
            # A roman token read before any letter ("(iv)" right under "1.3") is held as the letter; it has no successor.
            next_letter = len(letter) == 1 and len(token) == 1 and ord(token) == ord(letter) + 1
            if roman and letter and not next_letter:
                number, parent = f"{base}({letter})({token})", f"{base}({letter})"
            elif token.isdigit():
                parent = f"{base}({letter})" if letter else base
                number = f"{parent}({token})"
            else:
                number, parent, letter = f"{base}({token})", base, token
            out.sections.append(Section(number, m.group(2), 1 + number.count(".") + number.count("("), at, parent=parent))
        at += len(line)
    _close(out)
    return out


def _close(out: DocumentOutline) -> None:
    """Each section ends where the next section at its depth or shallower starts, or at the end of the text."""
    for k, s in enumerate(out.sections):
        s.end = next((t.start for t in out.sections[k + 1:] if t.depth <= s.depth), len(out.text))


def outline_lines(outline: DocumentOutline, *, max_depth: int = 9) -> list[str]:
    return [f"{'  ' * (s.depth - 1)}{s.number + ' ' if s.number else ''}{s.title}" for s in outline.sections if s.depth <= max_depth]


__all__ = ["CitableDocument", "Section", "DocumentOutline", "outline_from_doc", "outline_from_text", "outline_lines",
           "normalize_number"]
