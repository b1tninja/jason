"""The record reader: the association's books as plain pages, by their ``jason://`` addresses, on disk.

Two readers share one model of a page (``Sheet``), built from a citation the ``Shelf`` resolves
(``jason.tasks.cite``):

- the MCP resources (``jason.mcp.resources``) render a sheet as Markdown, one address at a time;
- ``jason cite --html [DIR]`` (``write``) renders every book, section, history, and version it can reach as static
  HTML in ``data/reader`` (private: ``data/`` is never checked in), with each address mapped to a relative page path,
  like lawlibrary's script-free ``/view`` pages. ``python -m http.server -d data/reader`` serves them; opening
  ``index.html`` from disk works too.

A sheet recites first: the words whole, the citation, the version in force, and the caveat. Then the address, the
permanent id, the defined terms the words use (each with its definition's address), the history, and, on the HTML
pages, what the section cites and what cites it. A record's own summary is never a page's words.

Restricted books (executive-session minutes, the membership list, election materials: CIV 5215, 5200(c)) are refused
by the shelf unless it is opened with ``private=True``; the HTML reader writes them only with ``--private``.

Reading only: nothing here writes to Drive, PayHOA, or the mail. ``write`` writes only its output folder.
"""

from __future__ import annotations

import html
import posixpath
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

from jason.community.cite import CAVEAT, Kind, Target, Unit, of_reference, scope_of

ID_CAVEAT = ("A permanent id is a pairing of words, made by a program: evidence a person can check, not a finding.")
MAX_PAGES = 20000                  # the HTML reader stops queueing pages here; a link past it is marked not written
LAW = "law:"                       # the reader's key for a statute's page ("law:CIV 4150"): statutes have no address


# --- One page --------------------------------------------------------------------------------------------------------

@dataclass
class Link:
    """A link from one page to another, by its key (an address, or ``law:`` and a statute)."""

    key: str                       # empty when the target has no address (a 5200 record kind, a heading by title)
    label: str
    note: str = ""                 # a caption, a relation, a holder
    found: bool = True
    reason: str = ""


@dataclass
class Sheet:
    """What a page shows, in the order it shows it."""

    key: str
    title: str
    kind: str
    found: bool
    reason: str = ""
    detail: str = ""
    words: str = ""                # recited whole
    in_force: str = ""             # the version in force
    note: str = ""
    caveat: str = ""
    address: str = ""
    pid: str = ""
    history: str = ""              # the section's history address
    effective: date | None = None  # the effective day of the version the words are read at (lastModified)
    terms: list[dict[str, Any]] = field(default_factory=list)
    outline: list[Link] = field(default_factory=list)
    versions: list[Link] = field(default_factory=list)
    readings: list[str] = field(default_factory=list)       # the names other readings give a section: evidence
    cites: list[Link] = field(default_factory=list)
    cited_by: list[Link] = field(default_factory=list)
    records: list[Link] = field(default_factory=list)       # jason's own records that name it (no page of their own)
    links: list[dict[str, str]] = field(default_factory=list)
    target: Target | None = None


def _number_target(t: Target, number: str) -> Target:
    return replace(t, unit=Unit.SECTION, number=number, end="", siblings=(), article=False, history=False, fragment="")


def address_of(shelf: Any, t: Target | None) -> str:
    """A target's page key: its address, or ``law:`` and the statute; empty for what has no page."""
    if t is None:
        return ""
    if t.unit is Unit.STATUTE:
        return LAW + t.id
    return shelf.address(t)


def effective_day(shelf: Any, c: Any) -> date | None:
    """The day the version a citation's words are read at took effect: an amended section's instrument; a document's
    version made effective on a day, or the one in force on a day, or now. None for the base (its day is not kept
    here), a stage, and a record."""
    from jason.community.addresses import VersionLabel
    from jason.tasks.permanent_ids import effective_dates

    t, st = c.target, c.state
    if t is None or not st.found:
        return None
    if st.kind is Kind.HISTORY:
        days = [n.get("version", "")[1:] for n in st.nodes if n.get("inForce", True) and n.get("changed")]
        try:
            return date.fromisoformat(days[-1]) if days else None
        except ValueError:
            return None
    if t.unit not in (Unit.SECTION, Unit.DOCUMENT):
        return None
    if st.kind is Kind.SECTION:        # the instrument that set its words; None while they are the base's
        dated = st.version.get("dated")
        return date.fromisoformat(dated) if st.version.get("amended") and dated else None
    label = VersionLabel(t.version) if t.version else None
    if label is not None and (label.stage is not None or label.base):
        return None
    if label is not None and label.effective is not None:
        return label.effective
    try:
        if shelf.resolver.living(t.key) is None:
            return None
        days = [d for d in effective_dates(shelf.resolver.versions(t.key)) if d is not None
                and (t.as_of is None or d <= t.as_of)]
    except Exception:
        return None
    return days[-1] if days else None


def sheet(shelf: Any, c: Any) -> Sheet:
    """The page for one citation (``shelf(expression)``)."""
    from jason.community.addresses import Address, AddressError, parse as parse_address

    st, t = c.state, c.target
    key = address_of(shelf, t) or c.expression
    out = Sheet(key, str(c), st.kind.value, st.found, st.reason.value if st.reason else "", st.detail, target=t)
    if not st.found:
        return out
    out.words = st.text or ""
    out.in_force = c.in_force if st.text else ""
    out.note = str(st.version.get("note") or "")
    if st.kind in (Kind.SECTION, Kind.RECORD, Kind.OUTLINE):
        out.caveat = CAVEAT
    elif st.kind is Kind.HISTORY:
        out.caveat = ID_CAVEAT
    out.address = c.address
    out.pid = c.pid if st.kind is Kind.SECTION else str(st.version.get("pid") or "")
    out.effective = effective_day(shelf, c)
    out.links = list(st.links)
    if t is not None and t.unit is Unit.SECTION and not t.end and not t.siblings and not t.history and out.address:
        try:
            a = parse_address(out.address)
            out.history = Address(a.key, a.section, history=True).format()
        except AddressError:
            out.history = ""
    for row in c.terms:
        out.terms.append({"term": row["term"], "key": row.get("address", ""), "citation": row.get("citation", ""),
                          "definition": row.get("definition", ""), "found": row.get("found", True)})
    for node in st.nodes:
        if "book" in node:                            # the governing documents: a set of books
            docs = ", ".join(node.get("documents") or ()) or node.get("series") or node.get("note") or ""
            out.outline.append(Link(f"jason://{node['book']}", f"{node['book']}: {node.get('title', '')}",
                                    f"{node.get('set', '')}; {docs}".strip("; ")))
        elif "version" in node and st.kind is Kind.HISTORY:
            label = node["version"]
            number = node.get("number") or ""
            addr = ""
            if number and t is not None:
                try:
                    a = parse_address(c.address)
                    addr = Address(a.key, number, version=label.lstrip("@")).format()
                except AddressError:
                    addr = ""
            flags = [x for x in ("words changed" if node.get("changed") else "",
                                 "" if node.get("inForce", True) else "not in force") if x]
            out.versions.append(Link(addr, f"{label} {number or '(not yet)'}".strip(),
                                     node.get("through", "") + (f" ({', '.join(flags)})" if flags else ""),
                                     found=bool(node.get("present", True))))
        elif node.get("number") and t is not None and t.unit in (Unit.SECTION, Unit.DOCUMENT):
            sub = _number_target(t, node["number"])
            flags = [x for x in ("amended" if node.get("amended") else "", "removed" if node.get("removed") else "",
                                 "" if node.get("found", True) else f"missing: {node.get('reason', '')}") if x]
            out.outline.append(Link(address_of(shelf, sub), node["number"],
                                    (node.get("caption") or "") + (f" ({', '.join(flags)})" if flags else ""),
                                    found=node.get("found", True) and not node.get("removed")))
        else:
            label = node.get("number") or node.get("first") or node.get("kind") or node.get("where") or ""
            note = node.get("caption") or node.get("title") or node.get("name") or node.get("location") or ""
            out.outline.append(Link("", str(label), str(note)))
    for row in st.extra.get("readings") or ():
        out.readings.append(str(row.get("says") or row))
    return out


# --- What cites what -------------------------------------------------------------------------------------------------

def _looks_numbered(where: str) -> bool:
    return bool(re.match(r"^(?:[A-Z]{1,2}-)?\d", where or ""))


class Edges:
    """The references both ways, indexed once: what a section's words cite (``outgoing``), and what names it (the
    governing documents' sections, and jason's own records)."""

    def __init__(self, shelf: Any):
        from jason.tasks.cite import _where

        self.shelf = shelf
        self.by_cited: dict[str, list[tuple[Target, str, str, str]]] = defaultdict(list)
        for row in shelf.rows():
            cited = of_reference(row.get("target", ""), row.get("kind", ""))
            if cited is not None:
                self.by_cited[cited.key].append((cited, row.get("source", ""), _where(row), row.get("relation", "")))
        self.mentions: dict[str, list[Any]] = defaultdict(list)
        try:
            for m in shelf.mentions():
                self.mentions[m.target.key].append(m)
        except Exception as exc:  # a record source that cannot be read leaves the documents' edges
            shelf.unread.append(f"mentions: {exc}")

    def cites(self, t: Target) -> list[Link]:
        out = []
        for cited, relation, quote, n in self.shelf.outgoing(t):
            st = self.shelf.state(cited)
            out.append(Link(address_of(self.shelf, cited), st.citation or cited.id,
                            relation + (f" x{n}" if n > 1 else ""), st.found, st.reason.value if st.reason else ""))
        return out

    def cited_by(self, t: Target) -> tuple[list[Link], list[Link]]:
        """The documents' sections that cite it, then jason's records that name it."""
        from jason.tasks.cite import _inside

        want = replace(t, as_of=None, end="", siblings=(), version="", history=False, fragment="")
        sections: dict[str, Link] = {}
        for cited, source, where, relation in self.by_cited.get(want.key, ()):
            scope = scope_of(cited, want)
            if scope is None:
                continue
            if want.unit is Unit.SECTION and source == want.key and where and _inside(where, want.number):
                continue                   # the section's own words naming itself or its parts
            src = (Target(Unit.SECTION, source, where) if _looks_numbered(where) else Target(Unit.DOCUMENT, source))
            key = address_of(self.shelf, src)
            label = f"{self.shelf.title(source)} {where}".strip()
            link = sections.setdefault(key or label, Link(key, label, f"{relation or 'cites'} ({scope.value})"))
            if relation and relation not in link.note:
                link.note += f"; {relation}"
        records: dict[tuple[str, str], Link] = {}
        for m in self.mentions.get(want.key, ()):
            scope = scope_of(m.target, want)
            if scope is None:
                continue
            records.setdefault((m.holder.value, m.key), Link("", m.key, f"{m.holder.value}: {m.title} ({scope.value})"))
        return list(sections.values()), list(records.values())


# --- The HTML reader -----------------------------------------------------------------------------------------------------

_SAFE = re.compile(r"[^A-Za-z0-9.()\-_~@,]")


def _segment(text: str) -> str:
    s = _SAFE.sub("_", text.replace(":", "_in_")) or "_"
    if s in (".", "..") or s.endswith("."):
        s += "_"
    return s


def _path_for(key: str) -> str:
    """A page's path, relative to the reader's root: ``jason://decl/4.15(a)`` -> ``decl/4.15(a).html``; a book's
    or a document's own page is its folder's ``index.html``."""
    if key.startswith(LAW):
        return "law/" + _segment(key[len(LAW):].replace(" ", "-")) + ".html"
    body = key[len("jason://"):] if key.startswith("jason://") else key
    body = body.replace("#", "/~")
    parts = [p for p in body.split("/") if p]
    if not parts:
        return "index.html"
    head, rest = parts[0], parts[1:]
    if "@" in head:
        book, _, version = head.partition("@")
        parts = [book, "@" + version, *rest]
    elif ":" in head:
        book, _, day = head.partition(":")
        parts = [book, "in-force-" + day, *rest]
    segs = [_segment(p) for p in parts]
    if len(segs) == 1 or (len(segs) == 2 and segs[1].startswith("@")):
        return "/".join(segs) + "/index.html"
    return "/".join(segs) + ".html"


@dataclass
class Report:
    out: Path
    pages: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)
    missing: dict[str, str] = field(default_factory=dict)      # a key linked to with no page, and why
    restricted: list[str] = field(default_factory=list)
    unread: list[str] = field(default_factory=list)
    capped: bool = False


def _seeds(shelf: Any, private: bool) -> tuple[list[str], dict[str, tuple[str, str]], list[str]]:
    """The pages to start from: every book, each part, and each numbered section of a living book's document (with
    its neighbours, for previous and next); and the restricted books left out."""
    from jason.community.books import Book

    seeds: list[str] = []
    order: dict[str, tuple[str, str]] = {}
    held: list[str] = []
    keys = set(shelf.names().values())
    living_keys: list[str] = []
    for b in Book:
        if b.restricted and not private:
            held.append(b.value)
            continue
        seeds.append(f"jason://{b.value}")
        if b.living and shelf.books.document(b.value) in keys:
            living_keys.append(b.value)
    for e in shelf.books.entries:
        if e.part and e.role.value != "amendment" and e.key not in living_keys:
            seeds.append(f"jason://{e.key}")
            living_keys.append(e.key)
    for k in living_keys:
        doc = shelf.books.document(k)
        try:
            current, _ = shelf.resolver.document(doc)
        except Exception as exc:
            shelf.unread.append(f"{k}: {exc}")
            continue
        numbers: list[str] = []
        seen: dict[str, int] = {}
        for p in current.provisions:
            if not p.number:
                continue
            seen[p.number] = seen.get(p.number, 0) + 1
            numbers.append(p.number if seen[p.number] == 1 else f"{p.number}~{seen[p.number]}")
        addrs = [f"jason://{k}/{n}" for n in numbers]
        for i, a in enumerate(addrs):
            order[a] = (addrs[i - 1] if i else "", addrs[i + 1] if i + 1 < len(addrs) else "")
        seeds += addrs
    return seeds, order, held


def collect(shelf: Any, *, private: bool = False, limit: int = MAX_PAGES) -> tuple[dict[str, Sheet], Report,
                                                                                    dict[str, tuple[str, str]]]:
    """Every page the reader can reach from the books, breadth first: each page's links queue their targets, so a
    link resolves to a page or is reported missing with its reason."""
    from jason.community.addresses import parse as parse_address, AddressError

    report = Report(Path("."))
    seeds, order, held = _seeds(shelf, private)
    report.restricted = held
    edges = Edges(shelf)
    pages: dict[str, Sheet] = {}
    queued: set[str] = set(seeds)
    queue: deque[str] = deque(seeds)
    while queue:
        key = queue.popleft()
        expression = key[len(LAW):] if key.startswith(LAW) else key
        c = shelf(expression)
        try:
            s = sheet(shelf, c)
        except Exception as exc:  # one page that cannot be read is a miss, not the end of the reader
            report.missing[key] = f"unreadable: {exc}"
            continue
        if not s.found:
            report.missing[key] = s.reason + (f": {s.detail}" if s.detail else "")
            continue
        s.key = key
        t = c.target
        current = t is not None and not t.version and t.as_of is None and not t.history
        if current and t.unit is Unit.SECTION and not t.end and not t.siblings:
            s.cites = edges.cites(t)
            s.cited_by, s.records = edges.cited_by(t)
        elif current and t.unit is Unit.STATUTE and not t.end and not t.siblings:
            s.cited_by, s.records = edges.cited_by(t)
        elif current and t.unit in (Unit.RESOLUTION, Unit.INSTRUMENT, Unit.MINUTES):
            s.cites = edges.cites(t)
        pages[key] = s
        links = [s.history] + [x["key"] for x in s.terms] + [x.key for x in (*s.outline, *s.versions, *s.cites,
                                                                               *s.cited_by)]
        for nxt in links:
            if not nxt or nxt in queued:
                continue
            if nxt.startswith("jason://"):
                try:
                    book = parse_address(nxt).book
                except AddressError:
                    book = None
                if book is not None and book.restricted and not private:
                    queued.add(nxt)
                    report.missing[nxt] = f"restricted ({book.restricted}): written only with --private"
                    continue
            if len(queued) >= limit:
                report.capped = True
                report.missing.setdefault(nxt, f"not written: the reader stops at {limit} pages")
                continue
            queued.add(nxt)
            queue.append(nxt)
    report.unread = list(dict.fromkeys(shelf.unread))
    return pages, report, order


_CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6862;--rule:#dedad2;--link:#1f5fa8;--quote:#f1eee7;--miss:#a33a2a}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#e8e6e1;--muted:#a19d95;--rule:#3a3835;--link:#8fb8ea;
--quote:#22211f;--miss:#e08a7a}}
body{background:var(--bg);color:var(--fg);font:16px/1.55 Georgia,serif;max-width:46rem;margin:0 auto;padding:1rem}
a{color:var(--link)}nav,footer,.meta,.note{color:var(--muted);font-size:.9rem}
blockquote{background:var(--quote);margin:1rem 0;padding:.75rem 1rem;white-space:pre-wrap;border-left:3px solid
var(--rule)}code{font-size:.9em}.missing{color:var(--miss);border-bottom:1px dotted var(--miss)}
h2{font-size:1.05rem;margin-top:1.75rem;border-bottom:1px solid var(--rule)}ul{padding-left:1.2rem}
.prevnext{display:flex;justify-content:space-between;gap:1rem}
"""


def _e(text: Any) -> str:
    return html.escape(str(text or ""))


class _Writer:
    def __init__(self, pages: dict[str, Sheet], report: Report, order: dict[str, tuple[str, str]], when: str):
        self.pages, self.report, self.order, self.when = pages, report, order, when
        self.paths: dict[str, str] = {}
        taken: set[str] = set()
        for key in pages:
            path = _path_for(key)
            n = 1
            while path.lower() in taken:          # a case-insensitive disk: B-2 and b-2 apart
                n += 1
                stem, dot, ext = path.rpartition(".")
                path = f"{stem}~{n}.{ext}" if dot else f"{path}~{n}"
            taken.add(path.lower())
            self.paths[key] = path

    def href(self, here: str, key: str) -> str:
        rel = posixpath.relpath(self.paths[key], posixpath.dirname(here) or ".")
        return quote(rel, safe="/()~@,-._")

    def link(self, here: str, key: str, label: str) -> str:
        if key and key in self.paths:
            return f'<a href="{self.href(here, key)}">{_e(label)}</a>'
        if not key:
            return _e(label)
        why = self.report.missing.get(key, "not written")
        return f'<span class="missing" title="{_e(why)}">{_e(label)}</span> <span class="note">({_e(why)})</span>'

    def page(self, key: str) -> str:
        s = self.pages[key]
        here = self.paths[key]
        body: list[str] = []
        crumbs = [self.link(here, "jason://", "Books")] if "jason://" in self.paths else []
        if s.address:
            head = s.address[len("jason://"):].split("/")[0]
            book_key = "jason://" + re.split(r"[@:]", head)[0]
            if book_key != key and book_key in self.paths:
                crumbs.append(self.link(here, book_key, self.pages[book_key].title))
        body.append(f"<nav>{' / '.join(crumbs)}</nav>" if crumbs else "")
        body.append(f"<h1>{_e(s.title)}</h1>")
        if s.words:
            body.append(f"<blockquote>{_e(s.words.strip())}</blockquote>")
            body.append(f"<p class=\"meta\"><em>{_e(s.title)}" + (f", {_e(s.in_force)}" if s.in_force else "")
                        + ".</em></p>")
        if s.note:
            body.append(f'<p class="note">Note: {_e(s.note)}</p>')
        if s.caveat:
            body.append(f'<p class="note"><em>{_e(s.caveat)}</em></p>')
        meta = []
        if s.address:
            meta.append(f"Address <code>{_e(s.address)}</code>")
        if s.pid:
            meta.append(f"permanent id <code>{_e(s.pid)}</code>")
        if s.effective:
            meta.append(f"{'words last changed' if s.kind == 'history' else 'in force from'} "
                        f"{s.effective.isoformat()}")
        if s.history:
            meta.append(self.link(here, s.history, "history"))
        if meta:
            body.append(f'<p class="meta">{"; ".join(meta)}</p>')
        if s.terms:
            body.append("<h2>Defined terms</h2><p class=\"note\">The document defines words this section uses; its "
                        "definition governs them here (Civil Code 1644). Each is recited from its own section.</p>")
            for row in s.terms:
                body.append(f"<p><strong>{_e(row['term'])}</strong>: {self.link(here, row['key'], row['citation'])}"
                            "</p>")
                if row["definition"]:
                    body.append(f"<blockquote>{_e(row['definition'].strip())}</blockquote>")
        sections = (("Outline", s.outline), ("Versions", s.versions), ("What it cites", s.cites),
                    ("What cites it", s.cited_by), ("jason's records that name it", s.records))
        for title, rows in sections:
            if not rows:
                continue
            body.append(f"<h2>{_e(title)}</h2><ul>")
            for r in rows:
                if r.key:
                    item = self.link(here, r.key, r.label)      # a page, or marked missing with why
                elif r.found:
                    item = _e(r.label)                          # no address: a record of jason's, a heading
                else:
                    item = f'<span class="missing">{_e(r.label)}</span>'
                lost = not r.found and r.reason and r.key not in self.paths and r.key not in self.report.missing
                body.append(f"<li>{item}" + (f" <span class=\"note\">{_e(r.note)}</span>" if r.note else "")
                            + (f" <span class=\"note\">(missing: {_e(r.reason)})</span>" if lost else "") + "</li>")
            body.append("</ul>")
        if s.readings:
            body.append("<h2>Other readings' numbers</h2><ul>" + "".join(f"<li>{_e(r)}</li>" for r in s.readings)
                        + "</ul>")
        if s.links:
            body.append("<h2>Where to check the words</h2><ul>")
            for row in s.links:
                where = row.get("url") or row.get("library", "")
                body.append(f"<li>{_e(row.get('what', ''))}: " + (f'<a href="{_e(where)}">{_e(where)}</a>'
                            if where.startswith("https://") else f"<code>{_e(where)}</code>") + "</li>")
            body.append("</ul>")
        series = [k for k in self.pages if k != key and k.startswith(key.rstrip("/") + "/") and s.kind == "record"]
        if series:
            body.append("<h2>Items in this reader</h2><ul>" + "".join(
                f"<li>{self.link(here, k, self.pages[k].title)}</li>" for k in sorted(series)) + "</ul>")
        prev, nxt = self.order.get(key, ("", ""))
        if prev or nxt:
            body.append('<p class="prevnext"><span>' + (self.link(here, prev, "previous: " + prev.rsplit("/", 1)[-1])
                        if prev else "") + "</span><span>" + (self.link(here, nxt, "next: " + nxt.rsplit("/", 1)[-1])
                                                            if nxt else "") + "</span></p>")
        return self._wrap(s.title, "\n".join(x for x in body if x))

    def index(self) -> str:
        from jason.community.books import Book

        here = "index.html"
        rows = []
        for b in Book:
            key = f"jason://{b.value}"
            flag = f" <span class=\"note\">restricted ({_e(b.restricted)})</span>" if b.restricted else ""
            label = f"{b.value}: {b.info.title}"
            item = self.link(here, key, label) if key in self.paths else (
                f"{_e(label)} <span class=\"note\">(not written: "
                f"{_e(self.report.missing.get(key) or ('restricted: --private writes it' if b.restricted else 'no page'))}"
                ")</span>")
            parts = [k for k in self.paths if k.startswith(f"{key}.") and "/" not in k[len("jason://"):]]
            sub = "".join(f"<li>{self.link(here, k, self.pages[k].title + ' (' + k[len('jason://'):] + ')')}</li>"
                          for k in sorted(parts))
            rows.append(f"<li>{item} <span class=\"note\">{_e(b.info.statute or 'not in the Act')}; "
                        f"{_e(b.info.shape.value)}</span>{flag}" + (f"<ul>{sub}</ul>" if sub else "") + "</li>")
        body = ("<h1>The association's books</h1><p class=\"note\">Written by <code>jason cite --html</code> on "
                f"{_e(self.when)} from the stores on disk. Private: the pages quote the association's records; keep "
                f"them in data/. {_e(CAVEAT)}</p><ul>" + "".join(rows) + "</ul>")
        return self._wrap("The association's books", body)

    def _wrap(self, title: str, body: str) -> str:
        return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                f"<title>{_e(title)}</title><style>{_CSS}</style></head><body>\n{body}\n<footer><p>jason record reader"
                f"; {_e(self.when)}</p></footer></body></html>\n")


def write(shelf: Any, out: Path, *, private: bool = False, limit: int = MAX_PAGES) -> Report:
    """Write the reader's pages under ``out`` (``data/reader``): ``index.html``, a page per book, part, section,
    history, version, and each record or statute a page links to. Restricted books only when ``private``."""
    pages, report, order = collect(shelf, private=private, limit=limit)
    report.out = Path(out)
    pages["jason://"] = Sheet("jason://", "The association's books", "index", True)
    w = _Writer(pages, report, order, date.today().isoformat())
    w.paths["jason://"] = "index.html"
    for key, path in w.paths.items():
        target = report.out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(w.index() if key == "jason://" else w.page(key), encoding="utf-8")
        kind = pages[key].kind
        report.by_kind[kind] = report.by_kind.get(kind, 0) + 1
    report.pages = len(w.paths)
    return report


def links_in(page: str) -> list[str]:
    """The relative hrefs a written page links to (for checking the reader's closure)."""
    return [h for h in re.findall(r'href="([^"]+)"', page) if not re.match(r"^[a-z]+:", h)]


__all__ = ["Edges", "LAW", "Link", "MAX_PAGES", "Report", "Sheet", "address_of", "collect", "effective_day",
           "links_in", "sheet", "write"]
