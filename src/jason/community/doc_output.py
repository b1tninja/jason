"""A document definition as a Google Doc: the requests that write it, with the Doc's real named styles.

The Markdown and HTML renderers print a document's structure as marks; a Doc keeps it as styles. This module turns an
assembled ``DocumentDefinition`` (``document_templates.assemble``) and its ``Layout`` into one list of Docs ``batchUpdate``
requests, so the Doc's outline is the document's own: the title is ``TITLE``, the line after it ``SUBTITLE``, a part or
a section ``HEADING_1``, a numbered rule ``HEADING_2``, its subdivision ``HEADING_3`` (the Markdown heading levels moved up
one), and the rest ``NORMAL_TEXT``. That structure is what a reader of the Doc, and the structure recovery that reads
published Docs, take as given: the heading a block prints is the heading the Doc has.

What it writes:

- the text of every block, with the headings' named styles, bullets, quotes, links (``[text](url)``), a ruled box for the
  status line, and a page break before the heading levels the layout names;
- a real **table** for each Markdown table (the adoption history, the directory): a marker paragraph is written in the
  text, then replaced by ``insertTable`` and its cells filled, last to first so no index moves under the next;
- a **named range** per block (its stable id), so a rule is found in the Doc by the id the record has, however the Doc is
  edited;
- the **contents**: the Docs API has no request that inserts a table-of-contents field, so the Doc has a marker where the
  contents go; ``contents_requests`` (second pass, once the headings have ids) writes the contents as links to the
  headings, and Insert > Table of contents in the Doc editor makes the field from the same headings;
- the layout's header and footer text (``header_text``, ``footer_text``), put in the Letterhead's header and footer by
  the caller.

A ``{TOKEN}`` the values do not fill is left in the text as written (a template Doc is filled when it is copied). This
module is pure: it never reads or writes Drive (``jason.tasks.document_docs`` does).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from jason.community.document_templates import Assembly, BlockResult, Layout, _tokens, shift_headings
from jason.google.docs_markdown import REPORT, DocStyle, Kind, Para, Span, _is_list, _n, inline, parse, requests

TABLE_MARKER = "[[table {}]]"
CONTENTS_MARKER = "[[contents]]"
TOKEN = re.compile(r"\{[A-Z][A-Z0-9_]*\}")
ESCAPED = re.compile(r"^\\(?=(\d+[.)]|[-*+#>])\s)")
TABLE_ROW = re.compile(r"^\|.*\|\s*$")
SEPARATOR = re.compile(r"^[|\-\s:]+$")


@dataclass
class DocPlan:
    """Everything a Doc would be given, before anything is written."""

    title: str
    requests: list[dict[str, Any]]
    paragraphs: list[str]                       # the text of each paragraph, in order (table markers included)
    tables: list[list[list[str]]]
    headings: list[tuple[str, str]]             # (named style, text), in order
    links: list[tuple[str, str]]                # (the words, the address)
    named_ranges: list[str]
    tokens: list[str]
    contents_depth: int = 0
    page_breaks: int = 0
    header: str = ""
    footer: str = ""
    text: str = ""

    @property
    def count(self) -> int:
        return len(self.requests)

    def styles(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for style, _ in self.headings:
            out[style] = out.get(style, 0) + 1
        return out


def header_text(layout: Layout, assembly: Assembly) -> str:
    return _tokens(layout.header, assembly).strip() if layout.header else ""


def footer_text(layout: Layout, assembly: Assembly) -> str:
    return _tokens(layout.footer, assembly).strip() if layout.footer else ""


def _extract_tables(markdown: str, tables: list[list[list[str]]]) -> str:
    """The block's Markdown with each table replaced by a marker line; the table's cells are added to ``tables``."""
    out: list[str] = []
    lines = markdown.split("\n")
    i = 0
    while i < len(lines):
        if TABLE_ROW.match(lines[i]):
            rows = []
            while i < len(lines) and TABLE_ROW.match(lines[i]):
                if not SEPARATOR.match(lines[i]):
                    rows.append([" ".join("".join(s.text for s in inline(c.strip())).split())
                                 for c in lines[i].strip().strip("|").split("|")])
                i += 1
            tables.append(rows)
            out.append(TABLE_MARKER.format(len(tables)))
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def _unescape(paras: list[Para]) -> None:
    """A rule line that begins like a list item was escaped for Markdown (``\\1. Words``); in a Doc it is plain text."""
    for p in paras:
        if p.kind is Kind.TEXT and p.spans and ESCAPED.match(p.spans[0].text):
            p.spans[0].text = ESCAPED.sub("", p.spans[0].text)


def build(assembly: Assembly, layout: Layout, *, style: DocStyle = REPORT, doc_end: int = 0) -> DocPlan:
    """The Doc's requests. ``doc_end`` is the end index of a Doc body that already holds text (a copy of the Letterhead):
    when given, that body is cleared first, as ``letters.body_requests`` does."""
    tables: list[list[list[str]]] = []
    paras: list[Para] = []
    owner: list[str] = []                       # the block that wrote each paragraph ("" for the layout's own)
    title_at: list[int] = []
    subtitle_at: list[int] = []
    page_from = len(paras)

    def add(markdown: str, block: BlockResult | None, *, boxed: bool = False, breaks: bool = True) -> None:
        got = parse(_extract_tables(shift_headings(markdown, layout.heading_shift), tables))
        _unescape(got)
        after_title = False                     # the paragraph that follows the title, before any heading, is the subtitle
        for p in got:
            if p.kind is Kind.HEADING and p.level == 1:
                p.kind = Kind.TEXT
                title_at.append(len(paras))
                after_title = True
            elif p.kind is Kind.HEADING:
                after_title = False
                p.level = min(p.level - 1, 6)
                if breaks and (p.level + 1) in layout.page_break_before:
                    p.page_break = True
            elif after_title:
                after_title = False
                if not subtitle_at and len(p.text) <= 120:
                    subtitle_at.append(len(paras))
            if boxed and p.kind is Kind.TEXT:
                p.boxed = True
            paras.append(p)
            owner.append(block.id if block else "")

    front = assembly.results[:layout.contents_after] if layout.contents and layout.contents_after else []
    rest = assembly.results[len(front):]
    for line in layout.cover:
        add(_tokens(line, assembly), None, breaks=False)
    if layout.title_heading:
        add(f"# {assembly.definition.title}", None, breaks=False)
    for r in front:
        if r.markdown.strip():
            add(r.markdown, r, boxed=r.kind == "status", breaks=False)
    depth = 0
    if layout.contents:
        depth = max(layout.contents_depth - 1, 1)
        paras.append(Para(Kind.TEXT, [Span("Contents", bold=True)]))
        owner.append("")
        paras.append(Para(Kind.TEXT, [Span(CONTENTS_MARKER)]))
        owner.append("")
    for r in rest:
        if r.markdown.strip():
            add(r.markdown, r, breaks=True)
    if not paras:
        paras.append(Para(Kind.TEXT, [Span("")]))
        owner.append("")

    reqs: list[dict[str, Any]] = []
    if doc_end - 1 > 1:
        reqs.append({"deleteContentRange": {"range": {"startIndex": 1, "endIndex": doc_end - 1}}})
    body = requests(paras, 1, style)

    starts, pos = [], 1
    for p in paras:
        starts.append(pos)
        pos += _n(("\t" * p.level if _is_list(p) else "") + p.text) + 1

    def span_of(i: int) -> dict[str, int]:
        return {"startIndex": starts[i], "endIndex": starts[i] + _n(("\t" * paras[i].level if _is_list(paras[i]) else "")
                                                                     + paras[i].text) + 1}

    extra: list[dict[str, Any]] = []
    for i in title_at:
        extra.append({"updateParagraphStyle": {"range": span_of(i), "paragraphStyle": {"namedStyleType": "TITLE"},
                                               "fields": "namedStyleType"}})
    for i in subtitle_at:
        extra.append({"updateParagraphStyle": {"range": span_of(i), "paragraphStyle": {"namedStyleType": "SUBTITLE"},
                                               "fields": "namedStyleType"}})
    named: list[str] = []
    first: dict[str, int] = {}
    last: dict[str, int] = {}
    for i, who in enumerate(owner):
        if who:
            first.setdefault(who, i)
            last[who] = i
    kinds = {r.id: r.kind for r in assembly.results}
    for who in first:
        if kinds.get(who) in ("prose", "status"):
            continue
        rng = {"startIndex": starts[first[who]], "endIndex": span_of(last[who])["endIndex"] - 1}
        if rng["endIndex"] > rng["startIndex"]:
            extra.append({"createNamedRange": {"name": who[:256], "range": rng}})
            named.append(who)

    # Lists are made last by ``requests`` (their leading tabs are removed, which moves the text after them); the extras
    # that name indices go before the first list, and the tables after the last, at the shifted places.
    cut = next((k for k, r in enumerate(body) if "createParagraphBullets" in r), len(body))
    reqs += body[:cut] + extra + body[cut:]
    tabs_before, removed = [], 0
    for p in paras:
        tabs_before.append(removed)
        removed += p.level if _is_list(p) else 0
    marker_of = {p.text: i for i, p in enumerate(paras) if re.fullmatch(r"\[\[table \d+\]\]", p.text)}
    for n in range(len(tables), 0, -1):
        i = marker_of.get(TABLE_MARKER.format(n))
        if i is None:
            continue
        at = starts[i] - tabs_before[i]
        rows = tables[n - 1]
        cols = max(len(r) for r in rows)
        reqs.append({"deleteContentRange": {"range": {"startIndex": at, "endIndex": at + _n(paras[i].text)}}})
        reqs.append({"insertTable": {"location": {"index": at}, "rows": len(rows), "columns": cols}})
        # A table inserted at ``at`` leaves the newline of an empty paragraph before it; the table starts one index on,
        # its rows and cells follow (row r, cell c: paragraph at start + 3 + r * (1 + 2 * cols) + 2 * c).
        start = at + 1
        for r in range(len(rows) - 1, -1, -1):
            for c in range(len(rows[r]) - 1, -1, -1):
                if rows[r][c]:
                    where = start + 3 + r * (1 + 2 * cols) + 2 * c
                    reqs.append({"insertText": {"location": {"index": where}, "text": rows[r][c]}})
                    if r == 0:                  # the head row is bold; styled as soon as it is written, before an earlier cell moves it
                        reqs.append({"updateTextStyle": {"range": {"startIndex": where, "endIndex": where + _n(rows[r][c])},
                                                         "textStyle": {"bold": True}, "fields": "bold"}})
        reqs.append({"pinTableHeaderRows": {"tableStartLocation": {"index": start}, "pinnedHeaderRowsCount": 1}})

    headings = []
    for i, p in enumerate(paras):
        if i in title_at:
            headings.append(("TITLE", p.text))
        elif i in subtitle_at:
            headings.append(("SUBTITLE", p.text))
        elif p.kind is Kind.HEADING:
            headings.append((f"HEADING_{min(p.level, 6)}", p.text))
    links = [(s.text, s.link) for p in paras for s in p.spans if s.link]
    text_lines = [p.text for p in paras if p.text not in marker_of]
    for rows in tables:
        text_lines += [c for row in rows for c in row if c]
    text = "\n".join(text_lines)
    return DocPlan(assembly.definition.title, reqs, [p.text for p in paras], tables, headings, links, named,
                   sorted(set(TOKEN.findall(text))), depth, sum(1 for p in paras if p.page_break),
                   header_text(layout, assembly), footer_text(layout, assembly), text)


# ---------------------------------------------------------------------------------------------------------------------
# After the body is written: the contents, the header and footer, and a check


def _body(doc: dict[str, Any]) -> list[dict[str, Any]]:
    tabs = doc.get("tabs")
    tab = (tabs[0].get("documentTab") or {}) if isinstance(tabs, list) and tabs else doc
    return (tab.get("body") or {}).get("content") or []


def _para_text(block: dict[str, Any]) -> str:
    return "".join((e.get("textRun") or {}).get("content", "") for e in (block.get("paragraph") or {}).get("elements", []))


def contents_requests(doc: dict[str, Any], depth: int = 2) -> list[dict[str, Any]]:
    """The contents marker replaced by one line per heading (``HEADING_1`` to ``HEADING_<depth>``), each a link to its
    heading, indented by level. Run once the Doc exists: the heading ids are the Doc's."""
    content = _body(doc)
    marker = next((b for b in content if _para_text(b).strip() == CONTENTS_MARKER), None)
    if marker is None:
        return []
    heads = []
    for b in content:
        para = b.get("paragraph") or {}
        name = (para.get("paragraphStyle") or {}).get("namedStyleType", "")
        m = re.fullmatch(r"HEADING_(\d)", name)
        hid = (para.get("paragraphStyle") or {}).get("headingId")
        if m and hid and int(m.group(1)) <= depth and _para_text(b).strip():
            heads.append((int(m.group(1)), _para_text(b).strip(), hid))
    start = int(marker["startIndex"])
    end = start + _n(CONTENTS_MARKER)
    out: list[dict[str, Any]] = [{"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}}]
    if not heads:
        return out
    lines = ["\t" * (lv - 1) + text for lv, text, _ in heads]
    out.append({"insertText": {"location": {"index": start}, "text": "\n".join(lines)}})
    pos = start
    for (lv, text, hid), line in zip(heads, lines):
        out.append({"updateTextStyle": {"range": {"startIndex": pos + lv - 1, "endIndex": pos + _n(line)},
                                        "textStyle": {"link": {"headingId": hid}}, "fields": "link"}})
        pos += _n(line) + 1
    return out


def footer_requests(doc: dict[str, Any], text: str) -> list[dict[str, Any]]:
    """The layout's footer text appended to the Doc's default footer (the Letterhead's own footer text stays)."""
    tabs = doc.get("tabs")
    tab = (tabs[0].get("documentTab") or {}) if isinstance(tabs, list) and tabs else doc
    footer_id = (tab.get("documentStyle") or {}).get("defaultFooterId")
    seg = (tab.get("footers") or {}).get(footer_id or "", {})
    if not footer_id or not text:
        return []
    content = seg.get("content") or []
    end = int(content[-1].get("endIndex", 1)) if content else 1
    if text in "".join(_para_text(b) for b in content):
        return []
    return [{"insertText": {"location": {"segmentId": footer_id, "index": max(end - 1, 0)}, "text": " · " + text}}]


def verify(doc: dict[str, Any], plan: DocPlan) -> list[str]:
    """What the written Doc lacks: each expected paragraph (a table marker excepted) that is not a paragraph of the body,
    and each heading whose named style is not the plan's."""
    content = _body(doc)
    have = [_para_text(b).rstrip("\n") for b in content if b.get("paragraph")]
    problems = []
    for text in plan.paragraphs:
        if text and not re.fullmatch(r"\[\[(table \d+|contents)\]\]", text) and text not in have:
            problems.append(f"paragraph missing: {text[:60]!r}")
    styles = [((b.get("paragraph") or {}).get("paragraphStyle") or {}).get("namedStyleType", "") for b in content
              if b.get("paragraph") and _para_text(b).strip()]
    for want, count in plan.styles().items():
        if styles.count(want) < count:
            problems.append(f"{want}: {styles.count(want)} in the Doc, {count} planned")
    return problems


__all__ = ["CONTENTS_MARKER", "DocPlan", "TABLE_MARKER", "build", "contents_requests", "footer_requests",
           "footer_text", "header_text", "verify"]
