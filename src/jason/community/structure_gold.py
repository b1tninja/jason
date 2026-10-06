"""The gold structure of a document: what a well-formatted Google Doc says its structure is.

A Doc names its headings (a paragraph style), draws its section numbers from lists, and has real page breaks, tables,
headers, and footers. A PDF of the same document has none of that: the benchmark in ``structure_fuzz`` degrades the
PDF and scores a reader that sees only the PDF against this gold (docs/structure-recovery.md).

``gold_from_doc`` reads the Docs API's document and keeps, for each paragraph, its kind, heading level, the number as the
Doc prints it (a list's rendered label, or the number its own words carry), its text and offsets, and its style facts.
``gold_from_outline`` is the weaker gold of a stored outline. ``pair_pages`` finds the page of the paired PDF where each
heading starts. ``render_pdf`` draws a gold as a PDF (a Doc's export being the paired artifact when it can be fetched):
made-up text in a test, or a stored outline's words where the export cannot be fetched.

Nothing here names an association. A gold built from a real Doc is that association's record: keep it in scratch.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from jason.community.outlines import DocumentOutline, _glyph
from jason.community.structure_numbering import fold_text, is_contents_page, split_number

HEADING_SIZES = {"TITLE": 26.0, "SUBTITLE": 15.0, "HEADING_1": 20.0, "HEADING_2": 16.0, "HEADING_3": 14.0,
                 "HEADING_4": 12.0, "HEADING_5": 11.0, "HEADING_6": 11.0, "NORMAL_TEXT": 11.0}
KINDS = ("heading", "paragraph", "list_item", "table", "page_break", "header", "footer")


@dataclass
class GoldNode:
    kind: str                       # KINDS
    text: str = ""                  # the paragraph's words as the Doc holds them, without a list's label
    level: int = 0                  # a heading's level from its named style (1 to 6); a title is 0 with ``title``
    number: str = ""                # as printed: a list's rendered label, or the number the words themselves carry
    title: str = ""                 # the words after the number
    own_number: bool = False        # the number is in ``text`` (not drawn from a list)
    title_style: bool = False       # the named style is TITLE or SUBTITLE
    list_id: str = ""
    nesting: int = -1
    start: int = 0                  # offsets into Gold.text
    end: int = 0
    size: float = 0.0
    bold: bool = False
    caps: bool = False
    indent: float = 0.0
    align: str = ""
    page: int = 0                   # the page of the paired PDF where it starts; 0 when not found
    parent: int = -1                # index of the node it hangs from (a shallower heading)

    @property
    def key(self) -> str:
        """What a heading is matched by: its words without the number, folded; the number when there are no words."""
        return fold_text(self.title or self.text) or fold_text(self.number)


@dataclass
class Gold:
    id: str
    title: str = ""
    source: str = ""                # "doc", "outline", or "made up"
    revision: str = ""
    text: str = ""
    nodes: list[GoldNode] = field(default_factory=list)
    parts: list[dict[str, Any]] = field(default_factory=list)       # {"title", "node", "page"}
    pages: int = 0
    styles: dict[str, Any] = field(default_factory=dict)             # counts of what the Doc carries

    def headings(self) -> list[GoldNode]:
        return [n for n in self.nodes if n.kind == "heading"]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Gold:
        return cls(**{**raw, "nodes": [GoldNode(**n) for n in raw.get("nodes", [])]})


def save(gold: Gold, folder: Path | str) -> Path:
    path = Path(folder) / gold.id / "gold.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(gold.to_dict(), indent=1), encoding="utf-8")
    return path


def load(folder: Path | str, doc_id: str) -> Gold:
    return Gold.from_dict(json.loads((Path(folder) / doc_id / "gold.json").read_text(encoding="utf-8")))


# --- from a Doc -----------------------------------------------------------------------------------------------------


def _runs(paragraph: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in paragraph.get("elements", []) if "textRun" in e]


def _named_defaults(tab: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for s in (tab.get("namedStyles", {}) or {}).get("styles", []):
        out[s.get("namedStyleType", "")] = s.get("textStyle", {})
    return out


def _style_of(paragraph: dict[str, Any], named: dict[str, dict[str, Any]]) -> tuple[float, bool, bool]:
    """(size, bold, small caps) over the paragraph's runs, weighted by their characters, the named style as the default."""
    style = paragraph.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
    base = named.get(style, {})
    size_w: dict[float, int] = {}
    bold_n = caps_n = total = 0
    for e in _runs(paragraph):
        content = e["textRun"].get("content", "").strip("\n")
        if not content.strip():
            continue
        ts = e["textRun"].get("textStyle", {})
        size = (ts.get("fontSize") or base.get("fontSize") or {}).get("magnitude") or HEADING_SIZES.get(style, 11.0)
        bold = ts.get("bold", base.get("bold", False))
        n = len(content)
        size_w[float(size)] = size_w.get(float(size), 0) + n
        bold_n += n if bold else 0
        caps_n += n if ts.get("smallCaps") else 0
        total += n
    if not total:
        return HEADING_SIZES.get(style, 11.0), False, False
    return max(size_w, key=size_w.get), bold_n * 2 >= total, caps_n * 2 >= total


def _is_caps(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 3 and sum(c.isupper() for c in letters) / len(letters) > 0.85


def gold_from_doc(doc: dict[str, Any], *, doc_id: str = "") -> Gold:
    """The gold structure of a Google Doc (the Docs API's document, first tab)."""
    tab = ((doc.get("tabs") or [{}])[0].get("documentTab")) or doc
    lists = tab.get("lists", {})
    named = _named_defaults(tab)
    gold = Gold(id=doc_id or doc.get("documentId", ""), title=doc.get("title", ""), source="doc",
                revision=doc.get("revisionId", ""))
    counters: dict[str, list[int]] = {}
    pieces: list[str] = []
    at = 0
    stack: list[int] = []                     # indexes of the headings the next one may hang from

    def paragraph_node(p: dict[str, Any]) -> GoldNode | None:
        nonlocal at
        raw = "".join(e.get("textRun", {}).get("content", "") for e in p.get("elements", []))
        text = raw.strip()
        start = at
        pieces.append(raw)
        at += len(raw)
        for e in p.get("elements", []):
            if "pageBreak" in e:
                gold.nodes.append(GoldNode("page_break", start=start, end=at))
        if p.get("paragraphStyle", {}).get("pageBreakBefore") and text:
            gold.nodes.append(GoldNode("page_break", start=start, end=start))
        if not text:
            return None
        ps = p.get("paragraphStyle", {})
        style = ps.get("namedStyleType", "NORMAL_TEXT")
        size, bold, small = _style_of(p, named)
        node = GoldNode("paragraph", text=text, start=start, end=at, size=size, bold=bold, caps=small or _is_caps(text),
                        indent=float((ps.get("indentStart") or {}).get("magnitude", 0.0)),
                        align=ps.get("alignment", "START"))
        heading = style.startswith("HEADING_")
        if style in ("TITLE", "SUBTITLE"):
            node.title_style = True
        bullet = p.get("bullet")
        label = ""
        if bullet:
            list_id, level = bullet["listId"], int(bullet.get("nestingLevel", 0))
            node.list_id, node.nesting = list_id, level
            levels = lists.get(list_id, {}).get("listProperties", {}).get("nestingLevels", [])
            counts = counters.setdefault(list_id, [0] * 9)
            counts[level] += 1
            for deeper in range(level + 1, 9):
                counts[deeper] = 0
            if level < len(levels) and levels[level].get("glyphFormat") and "glyphSymbol" not in levels[level]:
                label = levels[level]["glyphFormat"]
                for k in range(level, -1, -1):
                    label = label.replace(f"%{k}", _glyph(counts[k], levels[k].get("glyphType", "")))
                label = label.strip()
        if heading or node.title_style:
            node.kind = "heading"
            node.level = int(style[-1]) if heading else 0
        elif bullet:
            node.kind = "list_item"
        if label:
            node.number, node.title = label, text
        elif node.kind == "heading" and (m := split_number(text)):
            node.number, node.title, node.own_number = m.printed, m.rest or "", True
        else:
            node.title = text
        return node

    def walk(content: list[dict[str, Any]]) -> None:
        nonlocal at
        for block in content:
            if "paragraph" in block:
                node = paragraph_node(block["paragraph"])
                if node is not None:
                    if node.kind == "heading":
                        while stack and gold.nodes[stack[-1]].level >= node.level:
                            stack.pop()
                        node.parent = stack[-1] if stack else -1
                        stack.append(len(gold.nodes))
                    gold.nodes.append(node)
            elif "table" in block:
                cells = []
                for row in block["table"].get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        for sub in cell.get("content", []):
                            if "paragraph" in sub:
                                cells.append("".join(e.get("textRun", {}).get("content", "")
                                                     for e in sub["paragraph"].get("elements", [])).strip())
                joined = "\t".join(cells)
                start = at
                pieces.append(joined + "\n")
                at += len(joined) + 1
                gold.nodes.append(GoldNode("table", text=joined[:200], start=start, end=at))

    walk(tab.get("body", {}).get("content", []))
    for kind, group in (("header", "headers"), ("footer", "footers")):
        for _, part in (tab.get(group) or {}).items():
            words = " ".join("".join(e.get("textRun", {}).get("content", "") for e in b["paragraph"].get("elements", []))
                             for b in part.get("content", []) if "paragraph" in b).strip()
            if words:
                gold.nodes.append(GoldNode(kind, text=words, start=-1, end=-1))
    gold.text = "".join(pieces)
    _finish(gold)
    return gold


# --- from a stored outline ------------------------------------------------------------------------------------------


def gold_from_outline(outline: DocumentOutline, *, doc_id: str = "") -> Gold:
    """A weaker gold from a stored outline: its sections as headings (a section numbered "(a)" or deeper in parentheses
    is a list item), their depths, printed numbers, and offsets. It carries no style facts and no page breaks."""
    gold = Gold(id=doc_id or outline.key, title=outline.title, source="outline", revision=outline.revision,
                text=outline.text)
    stack: list[int] = []
    for s in outline.sections:
        item = "(" in s.number
        node = GoldNode("list_item" if item else "heading", text=s.title, level=0 if item else s.depth,
                        number=s.label or s.number, title=s.title, start=s.start, end=s.end)
        if s.label and s.title.startswith(s.label):
            node.title = s.title[len(s.label):].strip()
        if not item:
            while stack and gold.nodes[stack[-1]].level >= node.level:
                stack.pop()
            node.parent = stack[-1] if stack else -1
            stack.append(len(gold.nodes))
        gold.nodes.append(node)
    _finish(gold)
    return gold


def _finish(gold: Gold) -> None:
    counts: dict[str, int] = {}
    for n in gold.nodes:
        counts[n.kind] = counts.get(n.kind, 0) + 1
    counts["lists"] = len({n.list_id for n in gold.nodes if n.list_id})
    gold.styles = counts
    # A part is a document bound in: a title-style heading, or where none is used, a top heading after a page break.
    top = min((n.level for n in gold.nodes if n.kind == "heading" and n.level), default=0)
    titled = any(n.kind == "heading" and n.title_style for n in gold.nodes)
    parts = []
    after_break = True
    for i, n in enumerate(gold.nodes):
        if n.kind == "page_break":
            after_break = True
        elif n.kind == "heading" and (n.title_style or (not titled and n.level == top and after_break
                                                        and gold.styles.get("page_break"))):
            parts.append({"title": n.text, "node": i, "page": 0})
            after_break = False
        elif n.kind in ("heading", "paragraph", "list_item"):
            after_break = False
    gold.parts = parts


# --- pairing with the PDF -------------------------------------------------------------------------------------------


def pdf_lines(path: Path | str) -> list[list[str]]:
    """The text-layer lines of each page of a PDF, in reading order."""
    import pymupdf

    out = []
    with pymupdf.open(path) as doc:
        for page in doc:
            lines = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    t = "".join(s["text"] for s in line["spans"]).strip()
                    if t:
                        lines.append(t)
            out.append(lines)
    return out


def pair_pages(gold: Gold, pdf: Path | str, *, lines: list[list[str]] | None = None) -> int:
    """Sets each heading's, part's, and page break's ``page`` from the PDF's text layer, reading both in order. Returns
    the number of headings not found (their page stays 0). A heading is found where a line, or two lines run together,
    equals its words (with its number or without)."""
    pages = lines if lines is not None else pdf_lines(pdf)
    gold.pages = len(pages)
    skip = {p for p, ls in enumerate(pages) if is_contents_page(ls)}          # a contents page lists headings it does not hold
    flat = [(p + 1, fold_text(t)) for p, ls in enumerate(pages) if p not in skip for t in ls]
    cursor, missing = 0, 0
    page_now = 1
    for node in gold.nodes:
        if node.kind == "page_break":
            continue
        if node.kind not in ("heading", "list_item"):
            continue
        want = fold_text(((node.number + " ") if node.number else "") + (node.title or node.text))
        want2 = fold_text(node.title or node.text)
        found = -1
        # The line that prints the number and the words together is the heading; the words alone may be a label elsewhere.
        for forms, window in (((want,), 400 if node.number else 0), ((want, want2), len(flat))):
            for k in range(cursor, min(len(flat), cursor + window)):
                cand = flat[k][1]
                nxt = (cand + " " + flat[k + 1][1]) if k + 1 < len(flat) else cand
                if cand in forms or nxt in forms or (len(want2) > 12 and cand.startswith(want2)):
                    found = k
                    break
            if found >= 0:
                break
        if found < 0:
            if node.kind == "heading":
                missing += 1
            continue
        node.page = flat[found][0]
        page_now = node.page
        cursor = found + 1
    for part in gold.parts:
        part["page"] = gold.nodes[part["node"]].page
    return missing


# --- drawing a gold as a PDF ----------------------------------------------------------------------------------------


@dataclass
class RenderStyle:
    """How ``render_pdf`` sets a document: the type size and weight of each heading level, and what else it prints."""

    body: float = 11.0
    sizes: dict[int, float] = field(default_factory=lambda: {0: 24.0, 1: 18.0, 2: 14.0, 3: 12.0, 4: 11.0})
    bold_levels: tuple[int, ...] = (0, 1, 2, 3)
    caps_levels: tuple[int, ...] = ()
    indent_per_level: float = 0.0
    before: float = 14.0
    after: float = 5.0
    header: str = "Sample Association Rules"       # a running header on every page after the first
    page_numbers: bool = True
    toc: bool = False
    bookmarks: bool = False
    part_breaks: bool = True                        # a part starts a new page

    @classmethod
    def sized(cls, **kw: Any) -> RenderStyle:
        return cls(**kw)

    @classmethod
    def flat(cls, **kw: Any) -> RenderStyle:
        """Every heading the size of the body: level one in capitals, level two in bold, the rest told by number alone."""
        base = dict(sizes={0: 11.0, 1: 11.0, 2: 11.0, 3: 11.0, 4: 11.0}, bold_levels=(2,), caps_levels=(0, 1), before=9.0,
                    after=3.0)
        base.update(kw)
        return cls(**base)


def render_pdf(gold: Gold, path: Path | str, style: RenderStyle | None = None) -> Path:
    """The gold set in a PDF (Times, letter paper), headings by ``style``; fills ``node.page`` as it goes. A list item
    prints its number as a hanging label. Needs PyMuPDF."""
    import pymupdf

    style = style or RenderStyle()
    roman = pymupdf.Font("tiro")
    bold = pymupdf.Font("tibo")
    width, height = 612.0, 792.0
    left, right, top, bottom = 72.0, 540.0, 80.0, 720.0
    doc = pymupdf.open()
    state = {"page": None, "y": top, "n": 0}

    def new_page() -> Any:
        state["page"] = doc.new_page(width=width, height=height)
        state["n"] += 1
        state["y"] = top
        pg = state["page"]
        if style.header and state["n"] > 1:
            pg.insert_text((left, 42), style.header, fontsize=9, fontname="tiro")
        if style.page_numbers:
            pg.insert_text((width / 2 - 6, 756), str(state["n"] + (1 if style.toc else 0)), fontsize=9, fontname="tiro")
        return pg

    def wrap(text: str, font: Any, size: float, avail: float) -> list[str]:
        words, lines, cur = text.split(), [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if font.text_length(trial, fontsize=size) <= avail or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        return lines + ([cur] if cur else [])

    def put(text: str, size: float, is_bold: bool, *, before: float, after: float, indent: float = 0.0,
            label: str = "", centered: bool = False) -> int:
        font = bold if is_bold else roman
        lines = wrap(text, font, size, right - left - indent)
        need = before + len(lines) * size * 1.25 + after
        if state["page"] is None or state["y"] + need > bottom:
            new_page()
        state["y"] += before if state["y"] > top else 0
        first_page = state["n"]
        for k, line in enumerate(lines):
            if state["y"] + size * 1.25 > bottom:
                new_page()
            x = left + indent
            if centered:
                x = (width - font.text_length(line, fontsize=size)) / 2
            if k == 0 and label:
                state["page"].insert_text((x, state["y"] + size), label, fontsize=size,
                                          fontname="tibo" if is_bold else "tiro")
                x += font.text_length(label + " ", fontsize=size)
            if k > 0 and label:
                x = left + indent + font.text_length(label + " ", fontsize=size)
            state["page"].insert_text((x, state["y"] + size), line, fontsize=size, fontname="tibo" if is_bold else "tiro")
            state["y"] += size * 1.25
        state["y"] += after
        return first_page

    toc_entries: list[tuple[GoldNode, str]] = []
    # Pass 0 reserves nothing: the contents page, when asked for, is inserted in front once the pages are known.
    new_page()
    for i, node in enumerate(gold.nodes):
        if node.kind == "page_break":
            continue
        if node.kind in ("header", "footer", "table"):
            if node.kind == "table":
                node.page = put(node.text.replace("\t", "   "), style.body, False, before=6, after=6)
            continue
        if node.kind == "heading":
            lvl = node.level
            if style.part_breaks and (lvl == 0 or any(p["node"] == i for p in gold.parts)) and state["y"] > top + 40:
                new_page()
            size = style.sizes.get(lvl, style.body)
            words = node.text if node.own_number or not node.number else node.title
            shown = words.upper() if lvl in style.caps_levels else words
            label = node.number if not node.own_number else ""
            if label and lvl in style.caps_levels:
                label = label.upper()
            node.page = put(shown, size, lvl in style.bold_levels, before=style.before, after=style.after,
                            indent=style.indent_per_level * max(0, lvl - 1), label=label, centered=lvl == 0)
            toc_entries.append((node, shown))
        else:
            label = node.number if node.kind == "list_item" and node.number else ""
            node.page = put(node.title or node.text, style.body, False, before=2, after=4, indent=18.0 if label else 0.0,
                            label=label)
    gold.pages = doc.page_count
    if style.toc and toc_entries:
        doc.insert_page(0, width=width, height=height)
        pg = doc[0]
        pg.insert_text((left, 100), "TABLE OF CONTENTS", fontsize=14, fontname="tibo")
        y = 130.0
        for node, shown in toc_entries:
            if node.level > 2 or node.level == 0 or y > 700:          # a title is not in a Doc's contents
                continue
            printed = (node.number + " " if node.number and not node.own_number else "") + shown
            x0 = left + 14 * max(0, node.level - 1)
            num = str(node.page + 1)
            span = right - x0 - roman.text_length(printed[:70] + "  " + num, fontsize=10)
            dots = "." * max(3, int(span / roman.text_length(".", fontsize=10)))
            pg.insert_text((x0, y), f"{printed[:70]} {dots} {num}", fontsize=10, fontname="tiro")
            y += 14
        for node, _ in toc_entries:
            node.page += 1
        for part in gold.parts:
            part["page"] = gold.nodes[part["node"]].page
        gold.pages += 1
    else:
        for part in gold.parts:
            part["page"] = gold.nodes[part["node"]].page
    if style.bookmarks:
        doc.set_toc([[n.level, s[:80], n.page] for n, s in toc_entries if n.page and n.level])
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    doc.close()
    return path


def made_up(*, articles: int = 4, sections: int = 3, seed: int = 3, numbering: str = "dotted", parts: int = 2) -> Gold:
    """A made-up document with known headings and numbering: articles of sections of lettered items, with a body of
    invented sentences. ``numbering`` is "dotted" ("1.", "1.1"), "article" ("ARTICLE 1", "1.1"), or "rules" ("R-1.")."""
    import random

    rng = random.Random(seed)
    nouns = ["gate", "fence", "notice", "meeting", "vote", "fee", "permit", "garden", "vehicle", "fixture", "record",
             "repair", "access", "schedule"]
    verbs = ["shall be kept", "must be filed", "is posted", "will be reviewed", "may be amended", "is due"]

    def sentence() -> str:
        return f"The {rng.choice(nouns)} {rng.choice(verbs)} by the {rng.choice(nouns)} " \
               f"before the {rng.choice(nouns)} is {rng.choice(['closed', 'opened', 'recorded', 'paid'])}."

    def para(n: int = 3) -> str:
        return " ".join(sentence() for _ in range(n))

    subjects = ["Parking", "Noise", "Pets", "Landscaping", "Trash", "Signs", "Leases", "Fines", "Meetings", "Records", "Insurance",
                "Gates", "Pools", "Storage", "Fences", "Lighting"]
    gold = Gold(id=f"made-up-{numbering}-{seed}", title="Sample Rules", source="made up")
    per_part = max(1, articles // max(1, parts))
    s = 0
    for a in range(1, articles + 1):
        if parts and (a - 1) % per_part == 0 and (a - 1) // per_part < parts:
            gold.nodes.append(GoldNode("page_break"))
            gold.nodes.append(GoldNode("heading", text=f"PART {['ONE', 'TWO', 'THREE'][(a - 1) // per_part]}",
                                       level=0, title_style=True, title=f"PART {['ONE', 'TWO', 'THREE'][(a - 1) // per_part]}"))
        name = subjects[s % len(subjects)]
        s += 1
        if numbering == "rules":
            gold.nodes.append(GoldNode("heading", text=name.upper(), level=1, number=f"R-{a}.", title=name.upper()))
        elif numbering == "article":
            t = f"ARTICLE {a} {name.upper()}"
            gold.nodes.append(GoldNode("heading", text=t, level=1, number=f"ARTICLE {a}", title=name.upper(), own_number=True))
        else:
            gold.nodes.append(GoldNode("heading", text=name, level=1, number=f"{a}.", title=name))
        gold.nodes.append(GoldNode("paragraph", text=para(2), title=para(2)))
        for b in range(1, sections + 1):
            name2 = subjects[s % len(subjects)]
            s += 1
            gold.nodes.append(GoldNode("heading", text=name2, level=2,
                                       number=f"{a}.{b}" if numbering != "rules" else f"R-{a}.{b}", title=name2))
            gold.nodes.append(GoldNode("paragraph", text=para(5), title=para(5)))
            for c in "ab":
                gold.nodes.append(GoldNode("list_item", text=sentence(), title=sentence(), number=f"({c})"))
    for n in gold.nodes:
        if n.kind == "paragraph" and not n.title:
            n.title = n.text
    # parents
    stack: list[int] = []
    for i, n in enumerate(gold.nodes):
        if n.kind == "heading":
            while stack and gold.nodes[stack[-1]].level >= n.level:
                stack.pop()
            n.parent = stack[-1] if stack else -1
            stack.append(i)
    _finish(gold)
    return gold


__all__ = ["Gold", "GoldNode", "RenderStyle", "docx_to_doc", "gold_from_docx", "gold_from_doc", "gold_from_outline", "load", "made_up", "pair_pages",
           "pdf_lines", "render_pdf", "save"]


# --- from a Word file -----------------------------------------------------------------------------------------------

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_NUMFMT = {"decimal": "DECIMAL", "lowerLetter": "ALPHA", "upperLetter": "UPPER_ALPHA", "lowerRoman": "ROMAN",
           "upperRoman": "UPPER_ROMAN", "decimalZero": "ZERO_DECIMAL"}


def docx_to_doc(path: Path | str) -> dict[str, Any]:
    """A Word file (a Doc's ``.docx`` export, or a revision Drive kept) as a document shaped like the Docs API's, so
    ``gold_from_doc`` reads it: paragraph styles by name, list numbering by the file's numbering part, page breaks, tables,
    headers, and footers. Offline: nothing is fetched."""
    import xml.etree.ElementTree as ET
    import zipfile

    def val(el: Any, tag: str, attr: str = "val") -> str | None:
        child = el.find(f"{_W}{tag}") if el is not None else None
        return child.get(f"{_W}{attr}") if child is not None else None

    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        root = ET.fromstring(z.read("word/document.xml"))
        styles = ET.fromstring(z.read("word/styles.xml")) if "word/styles.xml" in names else None
        numbering = ET.fromstring(z.read("word/numbering.xml")) if "word/numbering.xml" in names else None
        parts = {n: ET.fromstring(z.read(n)) for n in sorted(names) if re.fullmatch(r"word/(header|footer)\d+\.xml", n)}

    style_named: dict[str, str] = {}
    style_num: dict[str, tuple[str, int]] = {}
    style_text: dict[str, dict[str, Any]] = {}
    if styles is not None:
        for st in styles.iter(f"{_W}style"):
            sid = st.get(f"{_W}styleId", "")
            name = (val(st, "name") or "").lower()
            mapped = {"title": "TITLE", "subtitle": "SUBTITLE"}.get(name)
            if mapped is None and (m := re.fullmatch(r"heading (\d)", name)):
                mapped = f"HEADING_{m.group(1)}"
            style_named[sid] = mapped or "NORMAL_TEXT"
            ppr, rpr = st.find(f"{_W}pPr"), st.find(f"{_W}rPr")
            num = ppr.find(f"{_W}numPr") if ppr is not None else None
            if num is not None and val(num, "numId") not in (None, "0"):
                style_num[sid] = (val(num, "numId") or "", int(val(num, "ilvl") or 0))
            ts: dict[str, Any] = {}
            if rpr is not None:
                if rpr.find(f"{_W}b") is not None and val(rpr, "b") not in ("0", "false"):
                    ts["bold"] = True
                if (sz := val(rpr, "sz")):
                    ts["fontSize"] = {"magnitude": int(sz) / 2}
            style_text[sid] = ts

    lists: dict[str, Any] = {}
    if numbering is not None:
        abstract: dict[str, list[dict[str, Any]]] = {}
        for an in numbering.iter(f"{_W}abstractNum"):
            levels = []
            for lv in sorted(an.findall(f"{_W}lvl"), key=lambda e: int(e.get(f"{_W}ilvl", 0))):
                fmt = val(lv, "numFmt") or "decimal"
                text = val(lv, "lvlText") or ""
                level: dict[str, Any] = {"glyphType": _NUMFMT.get(fmt, "DECIMAL")}
                if fmt == "bullet" or not text:
                    level["glyphSymbol"] = text or "-"
                else:
                    level["glyphFormat"] = re.sub(r"%(\d)", lambda m: f"%{int(m.group(1)) - 1}", text)
                levels.append(level)
            abstract[an.get(f"{_W}abstractNumId", "")] = levels
        for num in numbering.iter(f"{_W}num"):
            ref = val(num, "abstractNumId")
            if ref in abstract:
                lists[num.get(f"{_W}numId", "")] = {"listProperties": {"nestingLevels": abstract[ref]}}

    def run_text(r: Any) -> str:
        return "".join((t.text or "") for t in r.iter(f"{_W}t")) + ("\t" if r.find(f"{_W}tab") is not None else "")

    def paragraph(p: Any) -> dict[str, Any]:
        ppr = p.find(f"{_W}pPr")
        sid = val(ppr, "pStyle") or ""
        named = style_named.get(sid, "NORMAL_TEXT")
        elements: list[dict[str, Any]] = []
        for r in p.iter(f"{_W}r"):
            br = r.find(f"{_W}br")
            if br is not None and br.get(f"{_W}type") == "page":
                elements.append({"pageBreak": {}})
            text = run_text(r)
            if not text:
                continue
            rpr = r.find(f"{_W}rPr")
            ts = dict(style_text.get(sid, {}))
            if rpr is not None:
                if rpr.find(f"{_W}b") is not None:
                    ts["bold"] = val(rpr, "b") not in ("0", "false")
                if (sz := val(rpr, "sz")):
                    ts["fontSize"] = {"magnitude": int(sz) / 2}
                if rpr.find(f"{_W}smallCaps") is not None:
                    ts["smallCaps"] = True
            elements.append({"textRun": {"content": text, "textStyle": ts}})
        if elements and "textRun" in elements[-1]:
            elements[-1]["textRun"]["content"] += "\n"
        else:
            elements.append({"textRun": {"content": "\n", "textStyle": {}}})
        pstyle: dict[str, Any] = {"namedStyleType": named}
        if (jc := val(ppr, "jc")):
            pstyle["alignment"] = {"center": "CENTER", "right": "END", "both": "JUSTIFIED"}.get(jc, "START")
        ind = ppr.find(f"{_W}ind") if ppr is not None else None
        if ind is not None and (left := ind.get(f"{_W}left") or ind.get(f"{_W}start")):
            pstyle["indentStart"] = {"magnitude": int(left) / 20}
        if ppr is not None and ppr.find(f"{_W}pageBreakBefore") is not None and val(ppr, "pageBreakBefore") not in ("0", "false"):
            pstyle["pageBreakBefore"] = True
        out: dict[str, Any] = {"paragraphStyle": pstyle, "elements": elements}
        num = ppr.find(f"{_W}numPr") if ppr is not None else None
        pair = None
        if num is not None:
            pair = (val(num, "numId") or "", int(val(num, "ilvl") or 0))
        elif sid in style_num:
            pair = style_num[sid]
        if pair and pair[0] not in ("", "0") and pair[0] in lists:
            out["bullet"] = {"listId": pair[0], "nestingLevel": pair[1]}
        return {"paragraph": out}

    def plain(part: Any) -> list[dict[str, Any]]:
        return [paragraph(p) for p in part.iter(f"{_W}p")]

    content: list[dict[str, Any]] = []
    body = root.find(f"{_W}body")
    for child in body:
        if child.tag == f"{_W}p":
            content.append(paragraph(child))
        elif child.tag == f"{_W}tbl":
            cells = [{"content": plain(tc)} for tr in child.iter(f"{_W}tr") for tc in tr.findall(f"{_W}tc")]
            content.append({"table": {"tableRows": [{"tableCells": cells}]}})
    doc: dict[str, Any] = {"documentId": Path(path).stem, "title": Path(path).stem, "body": {"content": content},
                           "lists": lists, "headers": {}, "footers": {}}
    for name, part in parts.items():
        group = "headers" if "header" in name else "footers"
        doc[group][name] = {"content": plain(part)}
    return doc


def gold_from_docx(path: Path | str, *, doc_id: str = "") -> Gold:
    """The gold structure of a Word file: a Doc's ``.docx`` export, which keeps its styles, list numbering, page breaks,
    tables, headers, and footers (``docx_to_doc``)."""
    gold = gold_from_doc(docx_to_doc(path), doc_id=doc_id or Path(path).stem)
    gold.source = "docx"
    return gold
