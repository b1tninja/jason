"""An agenda's items, what each brings to the table, and the documents it points to.

``items_in_doc`` reads an agenda Doc into ``AgendaItem`` rows: each item (a level-4 heading) and sub-item (level 5) with
its notes (the paragraphs under it, a chip's title in its place) and its links. ``expected_kinds`` names the document
kinds an item brings by the specification's ``ItemRule`` rows (the treasurer's report brings reports and statements; a
claim brings the adjuster's letters and estimates). ``mentions`` finds what an item names without linking: a file name
("Proposal 6021-1.pdf") or a numbered document ("Proposal #6021-1", "estimate 000999", "claim AZ260311").

A document an item links, names, or received shortly before the meeting is related to it; the relation says which. The
item's kinds are where the board used a document, a lead for classifying it, never its classification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from jason.community.agenda_links import AgendaLink, LinkRule, links_in_doc
from jason.community.symbols import DocumentKind


@dataclass(frozen=True)
class ItemRule:
    """Title words (a regex, case-insensitive) and the document kinds an item with that title brings."""

    pattern: str
    kinds: tuple[DocumentKind, ...]

    def matches(self, title: str) -> bool:
        return bool(re.search(self.pattern, title, re.I))


def expected_kinds(title: str, rules: tuple[ItemRule, ...]) -> tuple[DocumentKind, ...]:
    """Every kind the matching rules name, in rule order, once each."""
    out: list[DocumentKind] = []
    for rule in rules:
        if rule.matches(title):
            out += [k for k in rule.kinds if k not in out]
    return tuple(out)


@dataclass
class AgendaItem:
    title: str
    subitem: str = ""
    notes: list[str] = field(default_factory=list)
    links: list[AgendaLink] = field(default_factory=list)

    @property
    def label(self) -> str:
        return " / ".join(p for p in (self.title, self.subitem) if p)

    @property
    def text(self) -> str:
        return " ".join([self.title, self.subitem, *self.notes])


def _text(paragraph: dict[str, Any]) -> str:
    parts = []
    for e in paragraph.get("elements", []):
        if "textRun" in e:
            parts.append(e["textRun"].get("content", ""))
        elif "richLink" in e:
            parts.append(f"[{e['richLink'].get('richLinkProperties', {}).get('title', '')}]")
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def items_in_doc(doc: dict[str, Any], rules: tuple[LinkRule, ...] = ()) -> list[AgendaItem]:
    """The Doc's items and sub-items in order, each with its notes and links (the header table is not an item)."""
    tab = ((doc.get("tabs") or [{}])[0].get("documentTab")) or doc
    items: list[AgendaItem] = []
    current: AgendaItem | None = None
    for block in tab.get("body", {}).get("content", []):
        para = block.get("paragraph")
        if not para:
            continue
        style = para.get("paragraphStyle", {}).get("namedStyleType", "")
        text = _text(para)
        if style.startswith("HEADING") and text:
            if style == "HEADING_5" and current is not None:
                current = AgendaItem(current.title, text)
            else:
                current = AgendaItem(text)
            items.append(current)
        elif current is not None and text:
            current.notes.append(text)
    by_label = {(i.title, i.subitem): i for i in items}
    for link in links_in_doc(doc, rules):
        item = by_label.get((link.item, link.subitem))
        if item is not None:
            item.links.append(link)
    return items


_FILE = re.compile(r"[\w&'(),+#.\- ]{3,90}?\.(?:pdf|docx?|xlsx?|pptx?|jpe?g|png|heic)\b", re.I)
_NUMBERED = re.compile(r"\b(proposal|estimate|quote|invoice|contract|claim|policy|work order|po)\s*(?:no\.?|number|#)?\s*"
                       r"([A-Z]{0,4}\d[\w-]{2,})", re.I)


def mentions(text: str) -> list[str]:
    """File names and numbered documents an item's words name ("Proposal 6021-1", "claim AZ260311")."""
    out: list[str] = []
    for m in _FILE.finditer(text):
        name = m.group(0).strip(" [](),")
        if name and name not in out:
            out.append(name)
    for m in _NUMBERED.finditer(text):
        token = m.group(2).strip(".-")
        if token not in out and not re.fullmatch(r"(19|20)\d\d", token):
            out.append(token)
    return out


__all__ = ["AgendaItem", "ItemRule", "expected_kinds", "items_in_doc", "mentions"]
