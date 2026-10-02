"""The HTML a template body is kept in: a small, email-safe set both PayHOA's composer and a Google Doc can carry.

PayHOA's composer is TinyMCE with the lists, link, autolink, image, table, and code plugins (broadcast2.har), so a body
can hold headings, bold, italic, underline, strikethrough, links, nested lists, tables, rules, and images. What a person
pastes into it from a Google Doc arrives with editor debris: ``dir="ltr"``, ``role="presentation"``, ``aria-level``,
every list item wrapped in its own ``<p>``, and a section heading's bold sometimes lost. ``normalize`` rebuilds any such
HTML (PayHOA's, a Doc's export, a hand-written draft) into one form:

- blocks: ``p``, ``h2``-``h4`` (an ``h1`` becomes ``h2``: the subject is the email's title), ``ul``/``ol``/``li``,
  ``table``/``tr``/``th``/``td``, ``blockquote``, ``hr``;
- inline: ``strong``, ``em``, ``u``, ``s``, ``a href`` (http, https, mailto), ``br``, ``img src alt``, and
  ``<span class="placeholder">{...}</span>``, the composer's placeholder;
- a span styled bold, italic, underlined, or struck through (a Doc's HTML export) becomes the tag;
- ``text-align`` on a block and ``colspan``/``rowspan`` on a cell are the only attributes kept beyond those above;
- a ``<p>`` directly inside a list item is unwrapped (two become a line break); runs of empty paragraphs become one,
  and none lead or trail.

``email_tables`` then gives each table the inline borders and padding mail clients need, since they drop stylesheets.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

BLOCKS = frozenset({"p", "h2", "h3", "h4", "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td", "blockquote", "hr"})
INLINE = frozenset({"strong", "em", "u", "s", "a", "br", "img", "span"})
VOID = frozenset({"br", "hr", "img"})
RENAME = {"b": "strong", "i": "em", "strike": "s", "del": "s", "h1": "h2", "h5": "h4", "h6": "h4", "div": "p",
          "section": "p", "article": "p", "header": "p", "footer": "p"}
DROP_WITH_CONTENT = frozenset({"script", "style", "head", "title", "meta", "link", "iframe", "object"})
SAFE_HREF = re.compile(r"^(https?:|mailto:)", re.IGNORECASE)
EMPTY = "<p>&nbsp;</p>"


@dataclass
class Node:
    tag: str                                     # "" for text
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)
    text: str = ""


def _style(attrs: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (attrs.get("style") or "").split(";"):
        key, _, value = part.partition(":")
        if key.strip():
            out[key.strip().lower()] = value.strip().lower()
    return out


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack: list[Node] = [self.root]
        self.skip = 0

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in DROP_WITH_CONTENT:
            self.skip += tag not in VOID
            return
        if self.skip:
            return
        attrs = {k.lower(): (v or "") for k, v in attrs_list}
        node = Node(tag, attrs)
        if tag in ("p", "div") or tag in BLOCKS or tag in RENAME:
            # a block opening inside an open paragraph closes it, as a browser does
            while self.stack[-1].tag in ("p", "div") and tag not in INLINE and tag not in ("b", "i", "strike", "del"):
                self.stack.pop()
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs_list)
        if tag.lower() not in VOID and self.stack[-1].tag == tag.lower():
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in DROP_WITH_CONTENT:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag in VOID:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        if not self.skip and data:
            self.stack[-1].children.append(Node("", text=data))


def _inline_wrappers(node: Node) -> list[str]:
    """The inline tags a styled span or a renamed tag stands for."""
    tag = RENAME.get(node.tag, node.tag)
    if tag in ("strong", "em", "u", "s"):
        return [tag]
    if tag != "span":
        return []
    style = _style(node.attrs)
    wraps = []
    if style.get("font-weight") in ("bold", "bolder", "600", "700", "800", "900"):
        wraps.append("strong")
    if style.get("font-style") == "italic":
        wraps.append("em")
    decoration = style.get("text-decoration", "") + " " + style.get("text-decoration-line", "")
    if "underline" in decoration:
        wraps.append("u")
    if "line-through" in decoration:
        wraps.append("s")
    return wraps


def _attrs(tag: str, node: Node) -> str:
    keep: list[tuple[str, str]] = []
    if tag == "a":
        href = node.attrs.get("href", "").strip()
        if SAFE_HREF.match(href):
            keep.append(("href", href))
    elif tag == "img":
        src = node.attrs.get("src", "").strip()
        if src.lower().startswith(("https:", "http:")):
            keep.append(("src", src))
        keep += [(k, node.attrs[k]) for k in ("alt", "width", "height") if node.attrs.get(k)]
    elif tag in ("td", "th"):
        keep += [(k, node.attrs[k]) for k in ("colspan", "rowspan") if node.attrs.get(k, "1") not in ("", "1")]
    if tag in ("p", "h2", "h3", "h4", "td", "th"):
        style = _style(node.attrs)
        kept = []
        if style.get("text-align", "") in ("center", "right", "justify"):
            kept.append(f"text-align: {style['text-align']}")
        # the letterhead's type: a font stack, its colour and size, and spacing (inline, as mail clients need)
        for key in ("font-family", "font-size", "color", "letter-spacing", "margin"):
            if style.get(key) and re.fullmatch(r"[#\w\s,'\".%()-]{1,120}", style[key]):
                kept.append(f"{key}: {style[key]}")
        if kept:
            keep.append(("style", "; ".join(kept)))
    return "".join(f' {k}="{html.escape(v)}"' for k, v in keep)


def _render(nodes: list[Node], *, in_li: bool = False) -> str:
    out: list[str] = []
    paragraphs_in_li = 0
    for node in nodes:
        if not node.tag:
            out.append(html.escape(node.text, quote=False))
            continue
        tag = RENAME.get(node.tag, node.tag)
        inner = _render(node.children, in_li=(tag == "li") or (in_li and tag not in ("ul", "ol")))
        if tag == "span" and "placeholder" in node.attrs.get("class", "").split():
            out.append(f'<span class="placeholder">{inner}</span>')
            continue
        wraps = _inline_wrappers(node)
        if wraps:
            text = inner
            for w in reversed(wraps):
                text = f"<{w}>{text}</{w}>" if text.strip() else text
            out.append(text)
            continue
        if tag in ("span", "font", "label", "small", "big", "sup", "sub", "code", "mark") or tag not in BLOCKS | INLINE:
            out.append(inner)                                # an unknown or presentational wrapper keeps its content
            continue
        if tag in VOID:
            out.append(f"<{tag}{_attrs(tag, node)}>")
            continue
        if tag == "p" and in_li:
            out.append(("<br>" if paragraphs_in_li else "") + inner.strip())
            paragraphs_in_li += 1
            continue
        if tag == "a" and not _attrs(tag, node):
            out.append(inner)
            continue
        out.append(f"<{tag}{_attrs(tag, node)}>{inner}</{tag}>")
    return "".join(out)


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t\r\n]+", " ", text)
    for tag in ("p", "h2", "h3", "h4", "li", "ul", "ol", "table", "thead", "tbody", "tr", "blockquote"):
        text = re.sub(rf"\s*<{tag}(\s[^>]*)?>", lambda m: f"\n<{tag}{m.group(1) or ''}>", text)
        text = re.sub(rf"[ ]*</{tag}>", f"</{tag}>", text)
    text = re.sub(r"(<(?:p|h2|h3|h4|li|td|th|blockquote)(?:\s[^>]*)?>)[ ]+", r"\1", text)
    text = re.sub(r"\s*<hr>", "\n<hr>", text)
    text = re.sub(r"<(p|h2|h3|h4)([^>]*)>\s*(?:&nbsp;|\xa0|\s|<br>)*</\1>", EMPTY, text)
    text = re.sub(r"(<(strong|em|u|s)>)\s*(</\2>)", "", text)
    lines = [line.rstrip() for line in text.split("\n") if line.strip()]
    collapsed: list[str] = []
    for line in lines:
        if line == EMPTY and (not collapsed or collapsed[-1] == EMPTY):
            continue
        collapsed.append(line)
    while collapsed and collapsed[-1] == EMPTY:
        collapsed.pop()
    return "\n".join(collapsed)


def normalize(text: str) -> str:
    """Any template HTML in the one form (see the module's notes)."""
    builder = _Builder()
    builder.feed(text or "")
    builder.close()
    return _tidy(_render(builder.root.children))


TABLE_STYLE = "border-collapse: collapse; margin: 8px 0"
CELL_STYLE = "border: 1px solid #c8c8c8; padding: 6px 10px; vertical-align: top; text-align: left"


def email_tables(text: str) -> str:
    """Inline borders and padding on tables and cells, which mail clients keep and stylesheets would not."""
    text = re.sub(r"<table(?![^>]*style=)", f'<table style="{TABLE_STYLE}"', text)

    def cell(m: re.Match[str]) -> str:
        tag, attrs = m.group(1), m.group(2) or ""
        if "border:" in attrs:
            return m.group(0)                        # already styled: adding twice would double it
        if "style=" in attrs:
            return re.sub(r'style="([^"]*)"', lambda s: f'style="{CELL_STYLE}; {s.group(1)}"', m.group(0), count=1)
        return f'<{tag}{attrs} style="{CELL_STYLE}">'

    return re.sub(r"<(td|th)(\s[^>]*)?>", cell, text)


@dataclass(frozen=True)
class Letterhead:
    """The association's letterhead as an email frame: a centered logo over the name, and a small centered footer.

    ``logo_url`` must be an image any mail client can load without signing in (an image link that needs a cookie, a
    referer, or a login shows as broken); empty means the frame has the name and no logo."""

    name: str
    logo_url: str = ""
    logo_width: int = 66
    logo_height: int = 96
    font: str = "Arial, sans-serif"
    footer: str = ""

    def head(self) -> list[str]:
        lines = []
        if self.logo_url:
            lines.append(f'<p style="text-align: center"><img src="{html.escape(self.logo_url)}" alt="{html.escape(self.name)}" '
                         f'width="{self.logo_width}" height="{self.logo_height}"></p>')
        lines.append(f'<h2 style="text-align: center; font-family: {self.font}; letter-spacing: 1px">{html.escape(self.name)}</h2>')
        return lines

    def foot(self) -> list[str]:
        if not self.footer:
            return []
        return ["<hr>", f'<p style="text-align: center; font-size: 12px; color: #666666">{html.escape(self.footer)}</p>']


def _text_of(line: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", line)).strip().casefold()


def strip_letterhead(body: str, letterhead: Letterhead) -> tuple[str, bool]:
    """The body without the letterhead frame, and whether it had one. The frame is found by what it says (the logo's
    address, the name, the footer's address), so a body framed by an earlier logo address is still recognized."""
    lines = normalize(body).splitlines()
    found = False
    while lines and ((letterhead.logo_url and letterhead.logo_url in html.unescape(lines[0]))
                     or (lines[0].startswith("<p") and "<img" in lines[0] and _text_of(lines[0]) == ""
                         and len(lines) > 1 and _text_of(lines[1]) == letterhead.name.casefold())
                     or _text_of(lines[0]) == letterhead.name.casefold()):
        lines.pop(0)
        found = True
    if letterhead.footer:
        while lines and (_text_of(lines[-1]) == letterhead.footer.casefold() or (found and lines[-1] == "<hr>")):
            lines.pop()
            found = True
    return "\n".join(lines), found


def with_letterhead(body: str, letterhead: Letterhead) -> str:
    """The body inside the letterhead frame (any frame it already had is replaced, not doubled)."""
    inner, _ = strip_letterhead(body, letterhead)
    return "\n".join([*letterhead.head(), inner, *letterhead.foot()])


LOCAL_IMAGE = re.compile(r'(<img\b[^>]*?\bsrc=")(?!https?:|data:|cid:)([^"]+)(")', re.I)


def local_images(text: str) -> list[str]:
    """The image files a draft names by a path of its own (not a web address), in order, once each."""
    return list(dict.fromkeys(html.unescape(m.group(2)) for m in LOCAL_IMAGE.finditer(text or "")))


def host_images(text: str, base_dir, upload) -> str:
    """``text`` with each local ``<img src="file.png">`` (a path beside ``base_dir``) uploaded once by ``upload``
    (path → the link to show it, PayHOA's ``viewUrl``) and replaced by that link. PayHOA's mailer turns an uploaded
    image's link into a lasting one when the email goes out (docs/packets.md)."""
    from pathlib import Path

    links = {}
    for name in local_images(text):
        path = Path(base_dir) / name
        if not path.is_file():
            raise FileNotFoundError(f"the message shows {name}, which is not at {path}")
        links[name] = upload(path)
    return LOCAL_IMAGE.sub(lambda m: m.group(1) + html.escape(links[html.unescape(m.group(2))]) + m.group(3), text)


def plain_text(text: str) -> str:
    """The body as the words a reader sees, one block a line: for diffs and comparisons."""
    body = re.sub(r"(?i)<br\s*/?>", "\n", text or "")
    body = re.sub(r"(?i)</(p|h\d|li|tr|blockquote)>|<hr\s*/?>", "\n", body)
    body = re.sub(r"(?i)</t[dh]>", " | ", body)
    body = re.sub(r"(?i)<li[^>]*>", "- ", body)
    body = html.unescape(re.sub(r"<[^>]+>", "", body)).replace("\xa0", " ")
    return "\n".join(line.strip(" |") for line in body.splitlines() if line.strip(" |"))


__all__ = ["Letterhead", "email_tables", "normalize", "plain_text", "strip_letterhead", "with_letterhead"]
