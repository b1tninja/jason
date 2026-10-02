"""Markdown as email HTML: one source for an owner-facing message, read by the same parser that writes the Doc.

An email draft, a guide, or a notice is written once, in the Markdown of ``jason.google.docs_markdown``, and becomes:

- the email body (``render``): paragraphs, ``h2``-``h4``, numbered and bulleted lists, bold, italic, links (a bare email
  address as ``mailto:``), a picture as ``<img>`` (a local file, uploaded when the email is sent:
  ``email_html.host_images``), and a hard line break as ``<br>``. PayHOA's placeholders (``{first name}``,
  ``{unit address}``) are wrapped the way its composer wraps them, and ``{HELP:...}`` tokens are left for
  ``links.fill_help_tokens``;
- the Doc on the letterhead (``jason letter --markdown``), and its PDF to attach or post.

Because both read the same paragraphs, the email and its Doc cannot say different things. Highlights (``==note==``)
are notes to whoever edits the Doc and are dropped from the email, keeping their text.
"""

from __future__ import annotations

import html
from typing import Any

from jason.google.docs_markdown import LINE_BREAK, Kind, Para, Span, parse

HEADINGS = {1: "h2", 2: "h3"}                     # the email's subject is its title; a Doc's sections step down one


def _spans(spans: list[Span]) -> str:
    out = []
    for s in spans:
        if s.text == LINE_BREAK:
            out.append("<br>")
            continue
        text = html.escape(s.text, quote=False).replace(LINE_BREAK, "<br>")
        if s.italic:
            text = f"<em>{text}</em>"
        if s.bold:
            text = f"<strong>{text}</strong>"
        if s.link:
            text = f'<a href="{html.escape(s.link)}">{text}</a>'
        out.append(text)
    return "".join(out).replace("</strong><strong>", "").replace("</em><em>", "")


def _block(p: Para) -> str:
    style = f' style="text-align: {"center" if p.align == "CENTER" else "right"}"' if p.align in ("CENTER", "END") else ""
    if p.kind is Kind.HEADING:
        tag = HEADINGS.get(p.level, "h4")
        return f"<{tag}{style}>{_spans(p.spans)}</{tag}>"
    if p.kind is Kind.PICTURE:
        width = f' width="{p.width}"' if p.width else ""
        return f'<p{style}><img src="{html.escape(p.picture)}" alt="{html.escape(p.alt)}"{width}></p>'
    if p.kind is Kind.QUOTE:
        return f"<blockquote>{_spans(p.spans)}</blockquote>"
    if p.note:
        return f'<p style="color:#666;font-size:12px">{_spans(p.spans)}</p>'
    return f"<p{style}>{_spans(p.spans)}</p>"


def _lists(items: list[Para]) -> str:
    """A run of list paragraphs as nested ``ol``/``ul``; a note under an item joins that item."""
    out: list[str] = []
    stack: list[str] = []                          # the open list tags, one per level
    for p in items:
        if p.kind is Kind.LIST_NOTE:
            if out:
                out.append(f"<br>{_spans(p.spans)}")
            continue
        tag = "ol" if p.kind is Kind.NUMBER else "ul"
        level = min(p.level, 3)
        while len(stack) > level + 1:              # back out to this level
            out.append(f"</li></{stack.pop()}>")
        if len(stack) == level + 1 and stack[-1] != tag:
            out.append(f"</li></{stack.pop()}>")
        if len(stack) == level + 1:
            out.append("</li>")
        while len(stack) < level + 1:
            stack.append(tag)
            out.append(f"<{tag}>")
        out.append(f"<li>{_spans(p.spans)}")
    while stack:
        out.append(f"</li></{stack.pop()}>")
    return "".join(out)


def render(markdown: str | list[str]) -> str:
    """The email body for ``markdown`` (see the module docstring)."""
    from jason.tasks.template_docs import composer_html

    paras = parse(markdown)
    blocks: list[str] = []
    run: list[Para] = []
    for p in paras:
        if p.kind in (Kind.BULLET, Kind.NUMBER, Kind.LIST_NOTE):
            run.append(p)
            continue
        if run:
            blocks.append(_lists(run))
            run = []
        if p.kind is not Kind.BLANK:
            blocks.append(_block(p))
    if run:
        blocks.append(_lists(run))
    return composer_html("\n".join(blocks))


def message_html(text: str, suffix: str) -> str:
    """A message file's body as HTML: rendered from Markdown (``.md``), else as written."""
    return render(text) if suffix.lower() in (".md", ".markdown") else text


__all__ = ["message_html", "render"]
