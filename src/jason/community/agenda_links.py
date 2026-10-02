"""The files an agenda links to, placed under the agenda item that links them.

The board's agenda Docs attach the item's papers as smart chips (a Drive file, folder, Doc, Sheet, or Slides deck, a
calendar event) and hyperlinks (a Google Photos album, the Zoom meeting, a statute, the court's case page, a vendor's
page). ``links_in_doc`` walks every tab of a Doc (child tabs too): the body, its tables, the headers and footers, and the
footnotes. Each link carries the item (the tab's level-4 heading) and sub-item (level 5) it sits under, and the section
it is in. A footnote's link takes the item where the footnote is referenced; a header's or footer's link belongs to the
whole Doc (the meeting's Zoom link, its calendar event). A link Docs splits over several text runs is one link. A link
to a heading in the same Doc is an internal cross-reference to that item (``LinkKind.INTERNAL``), and a URL typed as
plain text is a link too.

``links_in_pdf`` reads a PDF's link annotations with PyMuPDF: each link's anchor text (the words under its rectangle),
its page, and the heading above it. A heading is found by its type: a line in a larger or bold font than the page's body
text, short, and not a sentence. The largest heading size below the title is an item, and the next is a sub-item. Links
to another page of the same PDF are internal, and URLs typed in the text are found as in a Doc. ``LinkRule`` rows in the
specification name what a link points at, in order.

The item's title is a label for the file: "Insurance Renewal" on the renewal letter, "Review all open maintenance
requests" on the garage door proposal and its photos. A label is where the board used the file, not what the file is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class LinkKind(Enum):
    DRIVE_FILE = "Drive file"
    DRIVE_FOLDER = "Drive folder"
    GOOGLE_DOC = "Google Doc, Sheet, or Slides"
    PHOTOS = "Google Photos album"
    ZOOM = "Zoom meeting"
    LAW = "statute or legal reference"
    COURT = "court record"
    CALENDAR = "calendar event"
    INTERNAL = "another part of the same document"
    WEB = "web page"


class Section(Enum):
    BODY = "body"
    HEADER = "header"
    FOOTER = "footer"
    FOOTNOTE = "footnote"


@dataclass(frozen=True)
class LinkRule:
    kind: LinkKind
    pattern: str

    def matches(self, url: str) -> bool:
        return bool(re.search(self.pattern, url, re.I))


def link_kind(url: str, rules: tuple[LinkRule, ...]) -> LinkKind:
    return next((r.kind for r in rules if r.matches(url)), LinkKind.WEB)


_DRIVE_ID = re.compile(r"(?:/d/|/folders/|[?&]id=)([A-Za-z0-9_-]{20,})")


def drive_id(url: str) -> str:
    """The Drive file or folder id in a Drive, Docs, Sheets, or Slides link; empty for anything else."""
    if not re.search(r"(?:drive|docs)\.google\.com", url):
        return ""
    m = _DRIVE_ID.search(url)
    return m.group(1) if m else ""


@dataclass
class AgendaLink:
    url: str
    text: str = ""                 # the chip's title or the link's anchor text
    item: str = ""                 # the agenda item (level-4 heading) the link sits under
    subitem: str = ""              # the sub-item (level 5), when there is one
    mime: str = ""                 # a chip's MIME type
    page: int | None = None        # a PDF link's page
    kind: LinkKind = LinkKind.WEB
    target: str = ""               # the Drive id, when it is a Drive link
    section: Section = Section.BODY
    tab: str = ""                  # the Doc tab's title, when the Doc has more than one
    refers_to: str = ""            # an internal link's heading (the item it points at), or "page N"

    def label(self) -> str:
        return " / ".join(p for p in (self.item, self.subitem) if p)


_BARE_URL = re.compile(r"\bhttps?://[^\s<>\"')\]]+", re.I)


def _date_text(element: dict[str, Any]) -> str:
    props = element.get("dateElementProperties", {})
    return props.get("displayText") or (props.get("timestamp") or "")[:10]


def _text(paragraph: dict[str, Any]) -> str:
    """A paragraph's words, a chip's title in its place ("See: [Call for Candidates_Mystique.pdf] or visit ...") and a
    date chip's date ("Minutes of Mar 19, 2026")."""
    parts = []
    for e in paragraph.get("elements", []):
        if "textRun" in e:
            parts.append(e["textRun"].get("content", ""))
        elif "richLink" in e:
            parts.append(f"[{e['richLink'].get('richLinkProperties', {}).get('title', '')}]")
        elif "dateElement" in e:
            parts.append(_date_text(e["dateElement"]))
        elif "person" in e:
            parts.append(e["person"].get("personProperties", {}).get("name", ""))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _tabs(doc: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(title, documentTab) for every tab and child tab, in order; a Doc read without tabs is one tab."""
    if not doc.get("tabs"):
        return [("", doc)]
    out: list[tuple[str, dict[str, Any]]] = []

    def walk(tabs: list[dict[str, Any]]) -> None:
        for tab in tabs:
            out.append((tab.get("tabProperties", {}).get("title", ""), tab.get("documentTab") or {}))
            walk(tab.get("childTabs") or [])

    walk(doc["tabs"])
    return out


def _paragraphs(content: list[dict[str, Any]]):
    """Every paragraph in order, table cells included."""
    for block in content:
        if "table" in block:
            for row in block["table"].get("tableRows", []):
                for cell in row.get("tableCells", []):
                    yield from _paragraphs(cell.get("content", []))
        elif block.get("paragraph"):
            yield block["paragraph"]


def links_in_doc(doc: dict[str, Any], rules: tuple[LinkRule, ...] = ()) -> list[AgendaLink]:
    """Every chip and link in a Doc (all tabs; body, tables, headers, footers, footnotes), with the item and sub-item it
    sits under and its section."""
    tabs = _tabs(doc)
    headings: dict[str, str] = {}              # headingId -> the heading's text, for internal links
    for _, tab in tabs:
        for para in _paragraphs(tab.get("body", {}).get("content", [])):
            hid = para.get("paragraphStyle", {}).get("headingId")
            if hid:
                headings[hid] = _text(para)
    out: list[AgendaLink] = []
    tab_name = ""

    def emit(para: dict[str, Any], item: str, sub: str, section: Section, footnotes: dict[str, tuple[str, str]] | None) -> None:
        run: AgendaLink | None = None          # the link a run of text is still inside (Docs splits links over runs)
        plain: list[str] = []
        for el in para.get("elements", []):
            if footnotes is not None and "footnoteReference" in el:
                footnotes[el["footnoteReference"].get("footnoteId", "")] = (item, sub)
            if "richLink" in el:
                run = None
                props = el["richLink"].get("richLinkProperties", {})
                out.append(AgendaLink(props.get("uri", ""), props.get("title", ""), item, sub, props.get("mimeType", ""),
                                      section=section, tab=tab_name))
                continue
            text_run = el.get("textRun")
            if not text_run:
                run = None
                continue
            content = text_run.get("content", "")
            link = text_run.get("textStyle", {}).get("link") or {}
            url = link.get("url") or ""
            heading = link.get("headingId") or (link.get("heading") or {}).get("id") or ""
            if not url and heading:
                url = f"#heading={heading}"
            bookmark = link.get("bookmarkId") or (link.get("bookmark") or {}).get("id") or ""
            if not url and bookmark:
                url = f"#bookmark={bookmark}"
            if not url:
                run = None
                plain.append(content)
                continue
            if run is not None and run.url == url:
                run.text = (run.text + content).strip()
                continue
            run = AgendaLink(url, content.strip(), item, sub, section=section, tab=tab_name,
                             refers_to=headings.get(heading, "") if heading else "")
            out.append(run)
        for m in _BARE_URL.finditer("".join(plain)):
            url = m.group(0).rstrip(".,;:")
            out.append(AgendaLink(url, url, item, sub, section=section, tab=tab_name))

    for tab_name_, tab in tabs:
        tab_name = tab_name_ if len(tabs) > 1 else ""
        item = sub = ""
        footnotes: dict[str, tuple[str, str]] = {}
        for para in _paragraphs(tab.get("body", {}).get("content", [])):
            style = para.get("paragraphStyle", {}).get("namedStyleType", "")
            title = _text(para)
            if style.startswith("HEADING") and title:
                if style in ("HEADING_5", "HEADING_6"):  # a sub-item; a level-6 heading is the deeper sub-item
                    sub = title
                else:
                    item, sub = title, ""
            emit(para, item, sub, Section.BODY, footnotes)
        for section, key in ((Section.HEADER, "headers"), (Section.FOOTER, "footers")):
            for part in (tab.get(key) or {}).values():
                for para in _paragraphs(part.get("content", [])):
                    emit(para, "", "", section, None)
        for fid, note in (tab.get("footnotes") or {}).items():
            where = footnotes.get(fid, ("", ""))
            for para in _paragraphs(note.get("content", [])):
                emit(para, where[0], where[1], Section.FOOTNOTE, None)
    return [_finish(link, rules) for link in out if link.url]


_NUMBERING = re.compile(r"^\s*(?:[IVXLC]+|[ivxlc]+|\d+|[A-Za-z])[.)]?[\s​]*$")
_SUB_NUMBERING = re.compile(r"^\s*(?:[ivxlc]+|[a-z])[.)]\s")
_ITEM_NUMBERING = re.compile(r"^\s*(?:[IVXLC]+|\d+)[.)]\s")
_SEE = re.compile(r"^\s*(?:see|attached|link)\s*:", re.I)


def _lines(document: Any) -> list[tuple[int, float, str, float, bool, tuple[float, bool] | None]]:
    """(page, y, text, size, bold, numbering style) of each visual line; pieces set on the same line (a list number "V."
    and its heading) are one line, and the number's own size and weight are kept."""
    out: list[tuple[int, float, str, float, bool, tuple[float, bool] | None]] = []
    for n, page in enumerate(document, 1):
        pieces = []
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                if spans:
                    pieces.append((line["bbox"][1], line["bbox"][0], spans))
        pieces.sort(key=lambda p: (round(p[0]), p[1]))
        current: list[Any] = []
        for piece in pieces + [None]:
            if current and (piece is None or abs(piece[0] - current[0][0]) > 2):
                spans = [s for _, _, ss in current for s in ss]
                text = re.sub(r"[\s​]+", " ", " ".join(s["text"].strip() for s in spans)).strip()
                words = [s for s in spans if not _NUMBERING.match(s["text"])] or spans
                size = round(max(s["size"] for s in words), 1)
                bold = all(_bold(s) for s in words)
                first = spans[0]
                # The number is its own span in Google's export ("V." then the words) or the start of one span.
                numbered = (_NUMBERING.match(first["text"]) and len(spans) > 1) or _ITEM_NUMBERING.match(text) \
                    or _SUB_NUMBERING.match(text)
                numbering = (round(first["size"], 1), _bold(first)) if numbered else None
                out.append((n, current[0][0], text, size, bold, numbering))
                current = []
            if piece is not None:
                current.append(piece)
    return out


def _bold(span: dict[str, Any]) -> bool:
    return bool(span.get("flags", 0) & 16) or "bold" in span.get("font", "").lower()


def _running(lines: list[tuple[Any, ...]], pages: int) -> tuple[set[str], float, float]:
    """The page header's and footer's text (a line on at least two pages at about the same height), with the lowest
    header line and the highest footer line; nothing when the PDF has one page."""
    if pages < 2:
        return set(), -1.0, 1e9
    seen: dict[tuple[str, int], set[int]] = {}
    for n, y, text, *_ in lines:
        seen.setdefault((text, round(y / 10)), set()).add(n)
    running = {(t, band) for (t, band), ps in seen.items() if len(ps) >= 2}
    texts = {t for t, _ in running}
    ys = [y for n, y, text, *_ in lines if (text, round(y / 10)) in running]
    middle = sorted(l[1] for l in lines)[len(lines) // 2]
    header = max((y for y in ys if y < middle), default=-1.0)
    footer = min((y for y in ys if y > middle), default=1e9)
    return texts, header, footer


def _anchors(document: Any) -> set[tuple[int, str]]:
    """(page, text) of each link's anchor: a chip's title set bold on its own line is a link, not a heading."""
    out: set[tuple[int, str]] = set()
    for n, page in enumerate(document, 1):
        for link in page.get_links():
            rect = link.get("from")
            if rect is not None:
                text = re.sub(r"[\s​]+", " ", page.get_textbox(rect)).strip()
                if text:
                    out.add((n, text))
    return out


def _headings_by_type(document: Any, lines: list[tuple[Any, ...]] | None = None) -> list[tuple[int, float, str, int]]:
    """(page, y, text, level) of the lines a PDF sets as headings: larger or bold, short, not a sentence.

    The heading style used most (size and weight) is the item (level 4); a larger style is the title block (level 1);
    any other heading style is a sub-item (level 5). An agenda sets its items bold at the body size, so size alone would
    take the title for the item. A numbered line whose number is set in the item style is an item even when its words
    are a link (a chip's title), and the running header and footer are never headings."""
    lines = _lines(document) if lines is None else lines
    if not lines:
        return []
    running, _, _ = _running(lines, len(document))
    sizes: dict[float, int] = {}
    for _, _, text, size, *_ in lines:
        sizes[size] = sizes.get(size, 0) + len(text)
    body = max(sizes, key=sizes.get)            # the size most characters are set in

    def candidate(text: str, size: float, bold: bool) -> bool:
        return (size > body + 0.5 or (bold and size >= body - 0.5)) and 2 < len(text) < 110 \
            and not text.endswith((".", ",", ";")) and not _NUMBERING.match(text) and text not in running

    styles: dict[tuple[float, bool], int] = {}
    for _, _, text, size, bold, _ in lines:
        if candidate(text, size, bold):
            styles[(size, bold)] = styles.get((size, bold), 0) + 1
    if not styles:
        return []
    item = max(styles, key=lambda s: (styles[s], -s[0]))
    anchors = _anchors(document)
    # An agenda that numbers its items ("I.", "II.", or "1.") names them by the numbering: the number's style is the item
    # style, "i." and "a." number sub-items, and an unnumbered line is no item. Font sizes decide only when nothing is
    # numbered.
    numbered = [(n, y, text, numbering) for n, y, text, _, _, numbering in lines
                if numbering is not None and _ITEM_NUMBERING.match(text) and text not in running]
    if len(numbered) >= 3:
        counts: dict[Any, int] = {}
        for *_, style in numbered:
            counts[style] = counts.get(style, 0) + 1
        item_style = max(counts, key=counts.get)
        out = []
        for n, y, text, size, _, numbering in lines:
            if numbering is None or len(text) >= 110 or text in running:
                if size > item_style[0] + 0.5 and len(text) < 110 and not text.endswith((".", ",", ";")):
                    out.append((n, y, text, 1))
                continue
            if _SUB_NUMBERING.match(text):
                out.append((n, y, text, 5))
            elif _ITEM_NUMBERING.match(text) and numbering == item_style:
                out.append((n, y, text, 4))
        return out
    out = []
    for n, y, text, size, bold, numbering in lines:
        if _SEE.match(text):                   # "See: [Minutes of 10/28/25]" introduces a link; it heads nothing
            continue
        if numbering is None and any(p == n and (text == a or (len(a) > 8 and a in text and len(text) - len(a) < 12))
                                     for p, a in anchors):
            continue                           # the line is a link's own words
        if numbering is not None and _SUB_NUMBERING.match(text) and len(text) < 110:
            out.append((n, y, text, 5))         # "i." and "a." number an item's sub-items
        elif numbering == item and len(text) < 110 and text not in running:
            out.append((n, y, text, 4))
        elif candidate(text, size, bold):
            out.append((n, y, text, 4 if (size, bold) == item else 1 if size > item[0] + 0.5 else 5))
    return out


def links_in_pdf(path: Path, rules: tuple[LinkRule, ...] = ()) -> list[AgendaLink]:
    """A PDF's links (annotations, internal page links, and URLs typed in its text), each with its anchor text, page,
    and the heading above it."""
    try:
        import pymupdf

        document = pymupdf.open(path)
    except Exception:  # an unreadable PDF has no links to give
        return []
    lines = _lines(document)
    heads = _headings_by_type(document, lines)
    _, header_y, footer_y = _running(lines, len(document))
    out: list[AgendaLink] = []

    def section_at(y: float) -> Section:
        return Section.HEADER if y <= header_y + 2 else Section.FOOTER if y >= footer_y - 2 else Section.BODY

    def under(page: int, y: float) -> tuple[str, str]:
        if section_at(y) is not Section.BODY:
            return "", ""
        item = sub = ""
        for n, hy, text, level in heads:
            if (n, hy) > (page, y + 3):        # a link inside the heading's own line belongs to that heading
                break
            if level == 4:
                item, sub = text, ""
            elif level == 5:
                sub = text
        return item, sub

    for n, page in enumerate(document, 1):
        annotated: list[Any] = []
        for link in page.get_links():
            rect = link.get("from")
            anchor = page.get_textbox(rect).strip() if rect is not None else ""
            item, sub = under(n, rect.y0 if rect is not None else 0)
            if link.get("kind") == pymupdf.LINK_URI and link.get("uri"):
                out.append(AgendaLink(str(link["uri"]), re.sub(r"\s+", " ", anchor), item, sub, page=n,
                                      section=section_at(rect.y0 if rect is not None else 0)))
                annotated.append(str(link["uri"]))
            elif link.get("kind") == pymupdf.LINK_GOTO and link.get("page", -1) >= 0:
                target = link["page"] + 1
                out.append(AgendaLink(f"#page={target}", re.sub(r"\s+", " ", anchor), item, sub, page=n, refers_to=f"page {target}"))
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                text = "".join(s.get("text", "") for s in line.get("spans", []))
                for m in _BARE_URL.finditer(text):
                    url = m.group(0).rstrip(".,;:")
                    if not any(url in a or a in url for a in annotated):
                        item, sub = under(n, line["bbox"][1])
                        out.append(AgendaLink(url, url, item, sub, page=n, section=section_at(line["bbox"][1])))
    return [_finish(link, rules) for link in out]


def _finish(link: AgendaLink, rules: tuple[LinkRule, ...]) -> AgendaLink:
    link.kind = LinkKind.INTERNAL if link.url.startswith("#") else link_kind(link.url, rules)
    link.target = drive_id(link.url)
    return link


__all__ = ["AgendaLink", "LinkKind", "LinkRule", "Section", "drive_id", "link_kind", "links_in_doc", "links_in_pdf"]
