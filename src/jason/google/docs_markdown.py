r"""Markdown into a Google Doc: the board's drafts (agenda, packet) and the letter bodies, written in the house style.

A small Markdown: headings (``#`` to ``######``), paragraphs, bullets (``-`` or ``*``) and numbered items (``1.``) nested
by indent, block quotes (``>``), and inline ``**bold**``, ``_italic_`` or ``*italic*``, ``[links](url)``, and
``==highlight==`` for a note to whoever edits the Doc; a bare ``https://`` address is linked. A line that is only
``\pagebreak`` starts the next paragraph on a new page. Lines between ``\keep`` and ``\endkeep`` stay on one page: each
paragraph but the last keeps with the next, and none splits its own lines (a form's question with its help and lines).
An indented line under a list item continues it: it sits in the
item's indent with no number, as the secretary's "See:" lines do. A line that is none of these (a table row) is written
as text.

``requests`` turns paragraphs into one Docs ``batchUpdate``: insert the text at an index, give every paragraph its named
style and spacing, clear the text style the insertion point would lend it, apply the heading and inline styles, then
make the lists. Docs reads a list item's nesting from its leading tabs and removes them, so the lists are made last and
from the end of the text back, which keeps the earlier indices valid. The insertion point must be the start of an empty
paragraph (the body of a fresh copy, or a placeholder whose text was deleted): the last line takes that paragraph's
newline.

The Docs API cannot change a Doc's named styles, so the house look (dark bold headings, a rule under a section heading,
quoted law set in) is applied to each paragraph as it is written. ``DocStyle`` holds it; ``LETTER``, ``REPORT``, and
``AGENDA`` are the three in use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any


class Kind(Enum):
    TEXT = "text"
    HEADING = "heading"
    BULLET = "bullet"
    NUMBER = "number"
    LIST_NOTE = "list note"         # an indented line under a list item: set in the item's indent, without a number
    QUOTE = "quote"
    BLANK = "blank"
    PICTURE = "picture"             # ``![alt](file){width=600}``: a marker line the picture replaces (``picture_requests``)


@dataclass
class Span:
    text: str
    bold: bool = False
    italic: bool = False
    link: str = ""
    highlight: bool = False


@dataclass
class Para:
    kind: Kind
    spans: list[Span] = field(default_factory=list)
    level: int = 0                  # a heading's level (1-6), or a list item's nesting (0-2)
    align: str = ""                 # "CENTER" or "END"; empty keeps the start
    boxed: bool = False             # a ruled box around consecutive boxed paragraphs
    note: bool = False              # small grey text: a statement the law asks for, set apart from the business
    size: float = 0                 # a text size of its own (a title)
    keep_with_next: bool = False
    keep_lines: bool = False        # its own lines stay on one page (inside a ``\keep`` group)
    page_break: bool = False        # start on a new page (a ``\pagebreak`` line before it)
    picture: str = ""               # a picture's file, its alt text, and its width in pixels (0: as Docs sizes it)
    alt: str = ""
    width: int = 0

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)


@dataclass(frozen=True)
class DocStyle:
    text_below: float = 6
    list_below: float = 3
    first_above: float = 0          # space above the first paragraph (a letter's date under the letterhead)
    heading_sizes: tuple[float, ...] = (18, 14, 12, 11, 11, 11)
    heading_above: tuple[float, ...] = (6, 18, 12, 10, 8, 8)
    ruled_levels: tuple[int, ...] = (2,)
    ink: tuple[float, float, float] = (0.13, 0.13, 0.13)
    grey: tuple[float, float, float] = (0.35, 0.35, 0.35)
    note_size: float = 9
    quote_size: float = 10
    bullet_preset: str = "BULLET_DISC_CIRCLE_SQUARE"
    number_preset: str = "NUMBERED_DECIMAL_ALPHA_ROMAN"
    write_above: float = 0          # a form's writing line (a paragraph of underscores): room above it to write in
    write_ink: tuple[float, float, float] | None = None   # and its line's colour (pale, so a scan keeps less of it)


LETTER = DocStyle(text_below=0, first_above=14, heading_above=(6, 14, 12, 10, 8, 8))
REPORT = DocStyle()
# The secretary's agendas number the items I, II, III with sub-items under them; the business lines sit close together.
AGENDA = DocStyle(text_below=4, list_below=4, number_preset="NUMBERED_UPPERROMAN_UPPERALPHA_DECIMAL")

HIGHLIGHT = (1.0, 0.95, 0.6)

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST = re.compile(r"^(\s*)([-*]|\d+[.)])\s+(.*)$")
_QUOTE = re.compile(r"^>\s?(.*)$")
# A horizontal rule is dashes or asterisks; a line of underscores is kept, as a form's blank to sign or fill in.
_RULE = re.compile(r"^\s*(?:-{3,}|\*{3,})\s*$")
_WRITING = re.compile(r"^_{8,}$")               # a paragraph that is only a writing line
_BLANK = re.compile(r"_{8,}")                   # a blank to write on, alone or after a label ("Signature ____")
_INLINE = re.compile(
    r"\*\*(?P<b>.+?)\*\*"
    r"|==(?P<h>.+?)=="
    r"|\[(?P<lt>[^\]]+)\]\((?P<lu>[^)\s]+)\)"
    r"|(?<![\w*])\*(?P<i1>[^*\s](?:[^*]*?[^*\s])?)\*(?![\w*])"
    r"|(?<![\w_])_(?P<i2>[^_\s](?:[^_]*?[^_\s])?)_(?![\w_])"
    r"|`(?P<c>[^`]+)`"
    r"|(?P<url>https?://[^\s)\]]+[^\s)\].,;:])"
    r"|(?<![\w.+-])(?P<mail>[\w.+-]+@[\w-]+(?:\.[\w-]+)+)"
)
# a picture on a line of its own: ![alt](file) or ![alt](file){width=600}
_PICTURE = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<file>[^)\s]+)\)(?:\{width=(?P<width>\d+)\})?$")
PICTURE_MARKER = "[[picture {}]]"
LINE_BREAK = "\u000b"                       # a new line inside a paragraph: Docs' own soft break; ``<br>`` in an email
_PICTURE_MARKER = re.compile(r"\[\[picture ([^\]]+)\]\]")
PT_PER_PX = 0.75


def inline(text: str) -> list[Span]:
    """``text`` as spans, its inline marks read and removed. An unmatched mark stays as written."""
    spans: list[Span] = []
    at = 0
    for m in _INLINE.finditer(text):
        if m.start() > at:
            spans.append(Span(text[at:m.start()]))
        if m.group("b") is not None:
            spans += [replace(s, bold=True) for s in inline(m.group("b"))]
        elif m.group("h") is not None:
            spans += [replace(s, highlight=True) for s in inline(m.group("h"))]
        elif m.group("lt") is not None:
            spans += [replace(s, link=m.group("lu")) for s in inline(m.group("lt"))]
        elif m.group("i1") is not None or m.group("i2") is not None:
            spans += [replace(s, italic=True) for s in inline(m.group("i1") or m.group("i2"))]
        elif m.group("url") is not None:
            spans.append(Span(m.group("url"), link=m.group("url")))
        elif m.group("mail") is not None:
            spans.append(Span(m.group("mail"), link=f"mailto:{m.group('mail')}"))
        else:
            spans.append(Span(m.group("c")))
        at = m.end()
    if at < len(text):
        spans.append(Span(text[at:]))
    return spans


def parse(markdown: str | list[str], *, keep_blank: bool = False) -> list[Para]:
    """Markdown lines as paragraphs. A blank line only separates, unless ``keep_blank`` (a letter's spacing lines)."""
    lines = markdown.splitlines() if isinstance(markdown, str) else [line for chunk in markdown for line in chunk.splitlines() or [""]]
    out: list[Para] = []
    new_page = False
    group: int | None = None                # where the open ``\keep`` group starts in ``out``
    join = False                            # the last line ended in a hard break: this one continues its paragraph
    for raw in lines:
        line = raw.rstrip()
        joined, join = join, bool(line.strip()) and (raw.endswith("  ") or line.endswith("\\"))
        if join and line.endswith("\\"):
            line = line[:-1].rstrip()
        if joined and line.strip() and out and out[-1].kind in (Kind.TEXT, Kind.BULLET, Kind.NUMBER, Kind.QUOTE):
            out[-1].spans += [Span(LINE_BREAK)] + inline(line.strip())
            continue
        if line.strip() == r"\pagebreak":
            new_page = True
            continue
        if line.strip() == r"\keep":
            group = len(out)
            continue
        if line.strip() == r"\endkeep":
            kept = out[group:] if group is not None else []
            for para in kept:
                para.keep_lines = True
            for para in kept[:-1]:
                para.keep_with_next = True
            group = None
            continue
        if not line.strip() and " " not in raw:      # a no-break space alone is a deliberate empty line
            if keep_blank:
                out.append(Para(Kind.BLANK))
            continue
        if _RULE.match(line):
            continue
        count = len(out)
        if m := _PICTURE.match(line.strip()):
            out.append(Para(Kind.PICTURE, [Span(PICTURE_MARKER.format(m.group("file")))], align="CENTER",
                            picture=m.group("file"), alt=m.group("alt"), width=int(m.group("width") or 0)))
        elif m := _HEADING.match(line):
            out.append(Para(Kind.HEADING, inline(m.group(2)), level=len(m.group(1))))
        elif m := _LIST.match(line):
            indent = len(m.group(1).expandtabs(4))
            kind = Kind.NUMBER if m.group(2)[0].isdigit() else Kind.BULLET
            out.append(Para(kind, inline(m.group(3)), level=min((indent + 1) // 3, 2)))
        elif out and _is_list(out[-1]) and len(line) - len(line.lstrip()) >= 2:
            indent = len(line[:len(line) - len(line.lstrip())].expandtabs(4))
            out.append(Para(Kind.LIST_NOTE, inline(line.strip()), level=max(min((indent + 1) // 3, 2) - 1, 0)))
        elif m := _QUOTE.match(line):
            out.append(Para(Kind.QUOTE, inline(m.group(1))))
        else:
            out.append(Para(Kind.TEXT, inline(line.strip())))
        if new_page and len(out) > count:
            out[-1].page_break, new_page = True, False
    return out


def _n(text: str) -> int:
    """Length in the Docs API's units (UTF-16 code units)."""
    return len(text.encode("utf-16-le")) // 2


def _pt(value: float) -> dict[str, Any]:
    return {"magnitude": value, "unit": "PT"}


def _rgb(color: tuple[float, float, float]) -> dict[str, Any]:
    return {"color": {"rgbColor": dict(zip(("red", "green", "blue"), color))}}


def _border(color: tuple[float, float, float], width: float, padding: float) -> dict[str, Any]:
    return {"color": _rgb(color), "width": _pt(width), "padding": _pt(padding), "dashStyle": "SOLID"}


def _is_list(p: Para) -> bool:
    return p.kind in (Kind.BULLET, Kind.NUMBER, Kind.LIST_NOTE)


def requests(paras: list[Para], at: int, style: DocStyle = REPORT, *, segment_id: str = "") -> list[dict[str, Any]]:
    """Docs requests that write ``paras`` at index ``at`` (the start of an empty paragraph) in ``style``."""
    if not paras:
        return []

    def rng(start: int, end: int) -> dict[str, Any]:
        out = {"startIndex": start, "endIndex": end}
        if segment_id:
            out["segmentId"] = segment_id
        return out

    lines, starts = [], []
    pos = at
    for p in paras:
        line = ("\t" * p.level if _is_list(p) else "") + p.text
        starts.append(pos)
        lines.append(line)
        pos += _n(line) + 1
    end = pos - 1                                   # the last line's newline is the placeholder paragraph's own
    location = {"index": at, **({"segmentId": segment_id} if segment_id else {})}
    out: list[dict[str, Any]] = [{"insertText": {"location": location, "text": "\n".join(lines)}}]
    # Inserted text joins the list of the paragraph it lands in (a rewritten Doc's last paragraph may be a list item);
    # take every inserted paragraph out of any list first, and make this text's own lists at the end.
    out.append({"deleteParagraphBullets": {"range": rng(at, end + 1)}})

    base = {"namedStyleType": "NORMAL_TEXT", "spaceAbove": _pt(0), "spaceBelow": _pt(style.text_below), "indentStart": _pt(0),
            "indentFirstLine": _pt(0), "keepWithNext": False, "alignment": "START", "pageBreakBefore": False}
    out.append({"updateParagraphStyle": {"range": rng(at, end + 1), "paragraphStyle": base, "fields": ",".join(base)}})
    out.append({"updateTextStyle": {"range": rng(at, end), "textStyle": {},
                                    "fields": "bold,italic,underline,link,foregroundColor,backgroundColor,fontSize"}})
    boxed = [i for i, p in enumerate(paras) if p.boxed]
    for i, p in enumerate(paras):
        start, stop = starts[i], starts[i] + _n(lines[i])
        para: dict[str, Any] = {}
        text: dict[str, Any] = {}
        if p.kind is Kind.HEADING:
            k = min(p.level, 6) - 1
            para = {"namedStyleType": f"HEADING_{k + 1}", "spaceAbove": _pt(style.heading_above[k]), "spaceBelow": _pt(4),
                    "keepWithNext": True}
            if p.level in style.ruled_levels:
                para["borderBottom"] = _border((0.75, 0.75, 0.75), 0.75, 2)
            text = {"bold": True, "fontSize": _pt(style.heading_sizes[k]), "foregroundColor": _rgb(style.ink)}
        elif _is_list(p):
            para = {"spaceBelow": _pt(style.list_below)}
        elif p.kind is Kind.QUOTE:
            para = {"indentStart": _pt(18), "indentFirstLine": _pt(18), "borderLeft": _border((0.8, 0.8, 0.8), 1.5, 8)}
            text = {"fontSize": _pt(style.quote_size), "foregroundColor": _rgb(style.grey)}
        if p.note:
            text = {"fontSize": _pt(style.note_size), "foregroundColor": _rgb(style.grey)}
        blanks = list(_BLANK.finditer(p.text)) if (style.write_above or style.write_ink) else []
        if blanks:                                      # a writing line, or a line to sign and date on
            # Docs adds the paragraph above's space below to this one's space above; the room to write in is the two
            # together, so it comes to ``write_above`` exactly, and a line under a line is one writing line's pitch
            prev = paras[i - 1] if i else None
            prev_below = 0.0 if prev is None or _WRITING.match(prev.text) else (
                4.0 if prev.kind is Kind.HEADING else style.list_below if _is_list(prev) else style.text_below)
            para = {**para, "spaceAbove": _pt(max(0.0, style.write_above - prev_below))}
            if _WRITING.match(p.text):
                para["spaceBelow"] = _pt(0)
                if style.write_ink:
                    text = {**text, "foregroundColor": _rgb(style.write_ink)}
            elif style.write_ink:                       # only its blanks are pale; the label keeps its ink
                for m in blanks:
                    blank_at = start + _n(p.text[:m.start()])
                    out.append({"updateTextStyle": {"range": rng(blank_at, blank_at + _n(m.group(0))),
                                                    "textStyle": {"foregroundColor": _rgb(style.write_ink)},
                                                    "fields": "foregroundColor"}})
        if p.size:
            text = {**text, "fontSize": _pt(p.size)}
        if p.align:
            para["alignment"] = p.align
        if p.keep_with_next:
            para["keepWithNext"] = True
        if p.keep_lines:
            para["keepLinesTogether"] = True
        if p.page_break:
            para["pageBreakBefore"] = True
        if i == 0 and style.first_above:
            para["spaceAbove"] = _pt(style.first_above)
        if p.boxed:
            line = _border((0.2, 0.2, 0.2), 1, 6)
            para.update(borderLeft=line, borderRight=line, borderTop=line, borderBottom=line, indentStart=_pt(72), indentFirstLine=_pt(72),
                        indentEnd=_pt(72), spaceBelow=_pt(0))
            if i == boxed[-1]:
                para["spaceBelow"] = _pt(10)
        if para:
            out.append({"updateParagraphStyle": {"range": rng(start, stop + 1), "paragraphStyle": para, "fields": ",".join(para)}})
        if text and stop > start:
            out.append({"updateTextStyle": {"range": rng(start, stop), "textStyle": text, "fields": ",".join(text)}})
        at_span = start + (p.level if _is_list(p) else 0)
        for s in p.spans:
            width = _n(s.text)
            marks: dict[str, Any] = {}
            if s.bold:
                marks["bold"] = True
            if s.italic:
                marks["italic"] = True
            if s.link:
                marks["link"] = {"url": s.link}
            if s.highlight:
                marks["backgroundColor"] = _rgb(HIGHLIGHT)
            if marks and width:
                out.append({"updateTextStyle": {"range": rng(at_span, at_span + width), "textStyle": marks, "fields": ",".join(marks)}})
            at_span += width

    runs: list[tuple[int, int]] = []                # (first, last) paragraph of each list
    for i, p in enumerate(paras):
        if _is_list(p) and runs and runs[-1][1] == i - 1:
            runs[-1] = (runs[-1][0], i)
        elif _is_list(p):
            runs.append((i, i))
    for first, last in reversed(runs):
        items = [paras[j] for j in range(first, last + 1) if paras[j].kind is not Kind.LIST_NOTE]
        top = next((q for q in items if q.level == 0), items[0] if items else paras[first])
        preset = style.number_preset if top.kind is Kind.NUMBER else style.bullet_preset
        out.append({"createParagraphBullets": {"range": rng(starts[first], starts[last] + _n(lines[last])), "bulletPreset": preset}})
        # Making the list removed the run's leading tabs; a note's bullet comes off at its shifted place, and Docs keeps
        # its indent.
        removed = 0
        for j in range(first, last + 1):
            if paras[j].kind is Kind.LIST_NOTE:
                start = starts[j] - removed
                note = rng(start, start + _n(paras[j].text))
                indent = _pt(36 * (paras[j].level + 1))       # where the item's text starts at that nesting
                out.append({"deleteParagraphBullets": {"range": note}})
                out.append({"updateParagraphStyle": {"range": note, "paragraphStyle": {"indentStart": indent, "indentFirstLine": indent},
                                                     "fields": "indentStart,indentFirstLine"}})
            removed += paras[j].level
    return out


def _elements(doc: dict[str, Any]):
    tab = ((doc.get("tabs") or [{}])[0].get("documentTab")) or doc

    def walk(content: list[dict[str, Any]]):
        for block in content or []:
            for element in (block.get("paragraph") or {}).get("elements") or []:
                yield element
            for row in (block.get("table") or {}).get("tableRows") or []:
                for cell in row.get("tableCells") or []:
                    yield from walk(cell.get("content") or [])

    yield from walk(tab.get("body", {}).get("content", []))


def picture_markers(doc: dict[str, Any]) -> list[tuple[str, int, int]]:
    """Each picture marker (``PICTURE_MARKER``) in the Doc: its file and its range, in the Docs API's units.

    Pictures go in after the text: Drive's HTML import drops them, and the text requests cannot carry them. A marker
    holds the place; ``picture_requests`` swaps each for its picture."""
    found = []
    for element in _elements(doc):
        run, start = element.get("textRun") or {}, element.get("startIndex")
        text = str(run.get("content") or "")
        if start is None:
            continue
        for m in _PICTURE_MARKER.finditer(text):
            begin = start + _n(text[:m.start()])
            found.append((m.group(1), begin, begin + _n(m.group(0))))
    return found


def picture_requests(markers: list[tuple[str, int, int]], links: dict[str, str],
                     widths: dict[str, int]) -> list[dict[str, Any]]:
    """Replace each marker with its picture fetched from ``links`` (a link the Docs API can read; Docs keeps its own
    copy), at ``widths`` pixels when given; last first, so the earlier indexes still hold."""
    out: list[dict[str, Any]] = []
    for name, start, end in sorted(markers, key=lambda x: -x[1]):
        image: dict[str, Any] = {"uri": links[name], "location": {"index": start}}
        if widths.get(name):
            image["objectSize"] = {"width": _pt(widths[name] * PT_PER_PX)}
        out += [{"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}}, {"insertInlineImage": image}]
    return out


def picture_ids(doc: dict[str, Any]) -> list[str]:
    """The Doc's pictures in reading order, by object id."""
    return [str(e["inlineObjectElement"].get("inlineObjectId")) for e in _elements(doc)
            if isinstance(e.get("inlineObjectElement"), dict)]


def markdown_requests(markdown: str | list[str], at: int, style: DocStyle = REPORT, *, segment_id: str = "") -> list[dict[str, Any]]:
    return requests(parse(markdown), at, style, segment_id=segment_id)


def body_start_and_end(doc: dict[str, Any]) -> tuple[int, int]:
    """The body's first index and the end of its last paragraph's newline."""
    tab = ((doc.get("tabs") or [{}])[0].get("documentTab")) or doc
    content = tab.get("body", {}).get("content", [])
    return 1, int(content[-1].get("endIndex", 1)) if content else 1


def find_paragraph(doc: dict[str, Any], text: str) -> tuple[int, int] | None:
    """The (start, end) of the first body paragraph whose text is exactly ``text``, its newline excluded."""
    tab = ((doc.get("tabs") or [{}])[0].get("documentTab")) or doc
    for block in tab.get("body", {}).get("content", []):
        para = block.get("paragraph")
        if para and "".join(e.get("textRun", {}).get("content", "") for e in para.get("elements", [])).rstrip("\n") == text:
            return int(block["startIndex"]), int(block["endIndex"]) - 1
    return None


__all__ = ["Kind", "Span", "Para", "DocStyle", "LETTER", "REPORT", "AGENDA", "PICTURE_MARKER", "inline", "parse",
           "requests", "markdown_requests", "body_start_and_end", "find_paragraph", "picture_ids", "picture_markers",
           "picture_requests"]
