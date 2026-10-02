"""A Google Doc's body as the HTML a mail composer writes, read from the Docs API's structure (not Drive's HTML export,
whose bold is a CSS class and whose links go through google.com/url), so the result is the same every time the Doc is.

``document_html(doc)`` (rich) keeps what PayHOA's composer can carry (``jason.community.email_html``): a title or heading
as ``h2``/``h3``/``h4``, bold, italic, underline, strikethrough, links, line breaks, nested ``ul``/``ol``, tables as
tables (a row whose every cell is bold is a header row), horizontal rules, and centered or right-aligned paragraphs; the
result is passed through ``normalize``. ``rich=False`` is the first form (a heading as a bold paragraph, a table as one
paragraph a row joined by " | "), kept because the template sync's stored hashes were taken of it. An empty paragraph is
``<p>&nbsp;</p>``, and leading and trailing empty paragraphs are dropped. Only the first tab is read; headers, footers,
and comments are not the body.
"""

from __future__ import annotations

import html
from typing import Any

ORDERED_GLYPHS = frozenset({"DECIMAL", "ZERO_DECIMAL", "UPPER_ALPHA", "ALPHA", "UPPER_ROMAN", "ROMAN"})
EMPTY = "<p>&nbsp;</p>"


def _body(doc: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    tabs = doc.get("tabs")
    if isinstance(tabs, list) and tabs:
        tab = tabs[0].get("documentTab") or {}
        return tab.get("body") or {}, tab.get("lists") or {}
    return doc.get("body") or {}, doc.get("lists") or {}


def _run_html(run: dict[str, Any], rich: bool = False) -> str:
    text = str(run.get("content") or "")
    if not text:
        return ""
    style = run.get("textStyle") or {}
    out = html.escape(text.replace("\n", ""), quote=False).replace("\u000b", "<br>")
    if not out.strip():
        return out
    link = (style.get("link") or {}).get("url")
    if style.get("underline") and not link:
        out = f"<u>{out}</u>"
    if rich and style.get("strikethrough"):
        out = f"<s>{out}</s>"
    if style.get("italic"):
        out = f"<em>{out}</em>"
    if style.get("bold"):
        out = f"<strong>{out}</strong>"
    if link:
        out = f'<a href="{html.escape(link)}">{out}</a>'
    return out


def _merge(parts: list[str]) -> str:
    """Join runs, folding ``</strong><strong>`` and the like that adjacent runs leave."""
    joined = "".join(parts)
    for tag in ("strong", "em", "u"):
        joined = joined.replace(f"</{tag}><{tag}>", "")
    return joined


def _paragraph_html(paragraph: dict[str, Any], rich: bool = False) -> str:
    parts: list[str] = []
    for element in paragraph.get("elements") or []:
        if isinstance(element.get("textRun"), dict):
            parts.append(_run_html(element["textRun"], rich))
        elif rich and "horizontalRule" in element:
            parts.append(HR)
        elif rich and isinstance(element.get("inlineObjectElement"), dict):
            # a picture keeps its place by the Doc's own id; the reader that knows which file it is swaps it in
            parts.append(f'<img src="{DOCS_OBJECT}{html.escape(str(element["inlineObjectElement"].get("inlineObjectId")))}">')
    return _merge(parts).strip()


# a web-style address, so the composer tidy (which keeps only web picture links) leaves the place for the reader
DOCS_OBJECT = "https://docs.invalid/object/"


HR = "<hr>"
# Drive imports <h2> as Heading 2 and <h3> as Heading 3, so those keep their level on the way back; a Doc's Title and
# Heading 1 become h2 (the email's subject is its title), and Heading 4 to 6 become h4.
HEADING_TAGS = {"TITLE": "h2", "SUBTITLE": "h3", "HEADING_1": "h2", "HEADING_2": "h2", "HEADING_3": "h3"}
ALIGN = {"CENTER": "center", "END": "right", "JUSTIFIED": "justify"}


def _block(paragraph: dict[str, Any], text: str) -> str:
    """A rich paragraph: its heading level and alignment, or a rule standing alone."""
    if text == HR:
        return HR
    style = paragraph.get("paragraphStyle") or {}
    named = str(style.get("namedStyleType") or "")
    tag = HEADING_TAGS.get(named) or ("h4" if named.startswith("HEADING_") else "p")
    align = ALIGN.get(str(style.get("alignment") or ""))
    attrs = f' style="text-align: {align}"' if align else ""
    return f"<{tag}{attrs}>{text}</{tag}>"


def _table_html(table: dict[str, Any]) -> str:
    rows: list[str] = []
    for row in table.get("tableRows") or []:
        cells = []
        for cell in row.get("tableCells") or []:
            texts = [_paragraph_html(c["paragraph"], True) for c in cell.get("content") or [] if isinstance(c.get("paragraph"), dict)]
            cells.append("<br>".join(t for t in texts if t))
        header = all(c.startswith("<strong>") and c.endswith("</strong>") and c.count("<strong>") == 1 for c in cells if c) and any(cells)
        tag = "th" if header else "td"
        inner = [c[len("<strong>"):-len("</strong>")] if header and c else c for c in cells]
        rows.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in inner) + "</tr>")
    return "<table>" + "".join(rows) + "</table>"


def _is_heading(paragraph: dict[str, Any]) -> bool:
    named = str((paragraph.get("paragraphStyle") or {}).get("namedStyleType") or "")
    return named == "TITLE" or named.startswith("HEADING_")


def _list_tag(lists: dict[str, Any], list_id: str, level: int) -> str:
    levels = (((lists.get(list_id) or {}).get("listProperties") or {}).get("nestingLevels") or [])
    glyph = str((levels[level] if level < len(levels) else {}).get("glyphType") or "")
    return "ol" if glyph in ORDERED_GLYPHS else "ul"


def _render_list(items: list[tuple[int, str]], lists: dict[str, Any], list_id: str, level: int, i: int) -> tuple[str, int]:
    """Render items[i:] that sit at ``level`` or deeper as one list; return the HTML and the next index."""
    tag = _list_tag(lists, list_id, level)
    lines = [f"<{tag}>"]
    while i < len(items) and items[i][0] >= level:
        if items[i][0] > level:                       # a deeper item with no parent at this level
            inner, i = _render_list(items, lists, list_id, level + 1, i)
            lines.append(f"<li>{inner}</li>")
            continue
        text = items[i][1]
        i += 1
        if i < len(items) and items[i][0] > level:
            inner, i = _render_list(items, lists, list_id, level + 1, i)
            lines.append(f"<li>{text}\n{inner}</li>")
        else:
            lines.append(f"<li>{text}</li>")
    lines.append(f"</{tag}>")
    return "\n".join(lines), i


def document_html(doc: dict[str, Any], *, rich: bool = True) -> str:
    body, lists = _body(doc)
    out: list[str] = []
    pending: list[tuple[int, str]] = []              # the current list's items: (nesting level, html)
    pending_id = ""

    def flush() -> None:
        nonlocal pending, pending_id
        if pending:
            out.append(_render_list(pending, lists, pending_id, 0, 0)[0])
        pending, pending_id = [], ""

    for block in body.get("content") or []:
        paragraph = block.get("paragraph")
        table = block.get("table")
        if isinstance(paragraph, dict):
            text = _paragraph_html(paragraph, rich)
            bullet = paragraph.get("bullet")
            if isinstance(bullet, dict):
                list_id = str(bullet.get("listId") or "")
                if pending and list_id != pending_id:
                    flush()
                pending_id = list_id
                pending.append((int(bullet.get("nestingLevel") or 0), text))
                continue
            flush()
            if not text:
                out.append(EMPTY)
            elif rich:
                out.append(_block(paragraph, text))
            elif _is_heading(paragraph) and not text.startswith("<strong>"):
                out.append(f"<p><strong>{text}</strong></p>")
            else:
                out.append(f"<p>{text}</p>")
        elif isinstance(table, dict):
            flush()
            if rich:
                out.append(_table_html(table))
                continue
            for row in table.get("tableRows") or []:
                cells = []
                for cell in row.get("tableCells") or []:
                    texts = [_paragraph_html(c["paragraph"]) for c in cell.get("content") or [] if isinstance(c.get("paragraph"), dict)]
                    cells.append(" ".join(t for t in texts if t))
                if any(cells):
                    out.append("<p>" + " | ".join(cells) + "</p>")
    flush()
    while out and out[-1] == EMPTY:
        out.pop()
    while out and out[0] == EMPTY:
        out.pop(0)
    if rich:
        from jason.community.email_html import normalize

        return normalize("\n".join(out))
    return "\n".join(out)


__all__ = ["document_html"]
