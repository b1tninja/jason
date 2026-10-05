"""``cite``: the association's documents and records, opened for citing and reciting, on disk.

``cite(community, data_dir)`` opens a ``Shelf``; each unit call closes over the one before it, as lawlibrary's
``Citation`` does over a code::

    shelf = cite()
    shelf.doc("Declaration").section("6.2")("a")              # Declaration Section 6.2(a)
    shelf.doc("Declaration").section("6.2")("a", "b")         # siblings
    shelf.doc("Declaration").section("6.2").through("6.4")   # a span: an outline, not concatenated words
    shelf.doc("Declaration").section("6.2(a)").as_of("2099-01-01").text   # the words in force that day
    shelf("Section 6.2(a) of the Declaration").refs.hops(2)         # what it cites, two hops out
    shelf.resolution("20990101-1"); shelf.instrument("209901010001"); shelf.minutes("2099-01-01")
    shelf.record(AssociationRecord.MINUTES)               # CIV 5200(a)(8), and where the profile keeps it
    shelf("jason://decl@2099-01-01/6.2(a)")               # an address (jason.community.addresses)

Every resolved citation carries its address (``jason://decl/6.2(a)``) and, for a section, its permanent id
(``decl@base/6.2(a)``, ``jason.tasks.permanent_ids``). A restricted book (executive-session minutes, the membership
list, election materials: CIV 5215 and 5200) is refused unless the shelf is opened with ``private=True``.

The words come from ``jason.tasks.section_refs.DiskResolver``, the one reader the ``{QUOTE:}``/``{CITE:}`` tokens and
the guide also use, so a token, ``jason cite``, and the guide give the same citation and words. The shelf is itself a
``Resolver`` (``section``, ``citation``). The reference walk follows ``data/outlines/references.json`` (``jason
outlines``) into other documents' sections and into the statutes exported to ``data/authorities``; the reverse edges
add jason's own records that name a section or a statute (Conflict rows, notice provisions and requirements, document
duties, schedule assignments, response rules, letter templates, procedures, lessons, embedded tokens and the records
of their renderings, and the 5200 record kinds), each with how the cited words stand now.

Reading only: nothing here writes to Drive, PayHOA, or the mail. A living document's versions are cached in
``data/section-refs`` as the tokens' reader caches them.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from jason.community.cite import (CAVEAT, STALE, Citing, Holder, Kind, Miss, Node, Reason, Scope, Target, Treatment,
                                  Unit, label_text, mermaid, of_reference, parse, scope_of, sentences, targets_in,
                                  tree_lines)
from jason.community.books import Book
from jason.community.outlines import DocumentOutline, normalize_number
from jason.community import scoping
from jason.community.references import ancestors
from jason.community.section_refs import TOKEN, SectionRefError, SectionText, citation_of
from jason.tasks import rule_rows
from jason.tasks.cite_scope import build_index, citing_of
from jason.tasks.section_refs import DiskResolver, is_article

MAX_NODES = 2000                   # a walk with no hop limit stops here
OUTLINE_DEPTH = 2                  # a whole document's outline lists its sections to this depth


def _reason(exc: SectionRefError) -> Reason:
    try:
        return Reason(getattr(exc, "reason", "") or "unreadable")
    except ValueError:
        return Reason.UNREADABLE


def _day(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value else None)


def _letters(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _inside(inner: str, outer: str) -> bool:
    return inner == outer or inner.startswith(outer + "(") or inner.startswith(outer + ".")


def _where(row: dict[str, Any]) -> str:
    """The citing section of a reference row: a number normalized, a heading known by its title kept as written."""
    raw = (row.get("source_section") or "").strip()
    return normalize_number(raw) if re.match(r"^(?:[A-Z]{1,2}-)?\d", raw) else raw


_NUMBER = re.compile(r"^(?:[A-Z]{1,2}-)?\d+(?:\.\d+)*(?:\s?\([A-Za-z0-9]{1,5}\))*")


def _numbers_in(field: str) -> list[str]:
    """The section numbers a record's section field gives ("8.5(c), 8.6", "12.12(a)-(c)", "15.2 (the outline's
    15.1(a))"): each piece's leading number, a run of labels expanded; a piece with no number (a heading's title, a
    description) gives none."""
    out: list[str] = []
    for piece in re.split(r"\s*(?:,|;|\band\b)\s*", field or ""):
        m = _NUMBER.match(piece.strip())
        if not m:
            continue
        number = normalize_number(m.group(0))
        out.append(number)
        run = re.match(r"\s*(?:-|–|through|to)\s*\(([a-z])\)", piece.strip()[m.end():])
        last = re.search(r"\(([a-z])\)$", number)
        if run and last and last.group(1) < run.group(1) <= "z":
            base = number[: last.start()]
            out += [f"{base}({chr(k)})" for k in range(ord(last.group(1)) + 1, ord(run.group(1)) + 1)]
    return list(dict.fromkeys(out))


def _rows_of(obj: Any, name: str) -> tuple[Any, ...]:
    """A specification's rows, whether the profile gives them as a method or a property."""
    try:
        value = getattr(obj, name, ())
        return tuple(value() if callable(value) else value)
    except Exception:
        return ()


def _key(number: str) -> tuple[float, ...]:
    from jason.community.authorities import number_key

    return number_key(number.split("(")[0])


@dataclass
class State:
    """What a target resolves to on disk."""

    kind: Kind
    found: bool
    reason: Reason | None = None
    detail: str = ""
    citation: str = ""
    title: str = ""                    # the document's or the record's title
    text: str = ""                     # stored words only
    version: dict[str, Any] = field(default_factory=dict)        # where the words came from, who set them
    nodes: list[dict[str, Any]] = field(default_factory=list)    # an outline's parts
    outline: str = ""                  # the outline whose references a walk follows from it
    numbers: tuple[str, ...] = ()      # the sections of that outline the walk follows from ("" for all)
    links: list[dict[str, str]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


# A statute the shelf misses and its read-through (jason.tasks.statute_fetch) could not bring down, by why.
_LIBRARY_MISS = {
    "not_in_library": Reason.STATUTE_NOT_IN_LIBRARY,
    "library_unavailable": Reason.LIBRARY_UNAVAILABLE,
    "worker_failed": Reason.LIBRARY_FAILED,
}


def _miss(reason: Reason, detail: str = "", citation: str = "", **extra: Any) -> State:
    return State(Kind.MISS, False, reason, detail, citation, extra=extra)


@dataclass(frozen=True)
class Mention:
    """One of jason's own records naming a target."""

    holder: Holder
    key: str
    title: str
    target: Target
    field: str = ""
    quote: str = ""                    # words the record quotes from the target, to compare with the words now
    digest: str = ""                   # a rendering's digest of the words it quoted
    as_of: date | None = None
    reading: str = ""                  # the record's own paraphrase of the provision: jason's reading, not its words
    pid: str = ""                      # the permanent id the migration stored with the record (jason cite --migrate-ids)
    numbered: str = ""                 # the reading that numbers it so ("outline": the working copy), when known


class Shelf:
    """The association's documents and records on disk, opened for citing. Also a ``Resolver``."""

    def __init__(self, community: Any = None, data_dir: Path | None = None, *, log=None, repo: Path | None = None,
                 private: bool = False):
        from jason.community.books import Books

        self.resolver = DiskResolver(data_dir, community, log=log)
        self.community = self.resolver.community
        self.data_dir = self.resolver.data_dir
        self.repo = repo
        self.private = private
        self.books = Books.of(self.community)
        self._locator: Any = None
        self._register: dict[str, list[dict[str, Any]]] | None = None
        self._checked: list[Citing] | None = None
        self._names: dict[str, str] | None = None
        self._outlines: dict[str, DocumentOutline] | None = None
        self._rows: list[dict[str, Any]] | None = None
        self._mentions: list[Mention] | None = None
        self._states: dict[str, State] = {}
        self._copies: dict[tuple[str, str], Any] = {}
        self._index: scoping.Index | None = None
        self.unread: list[str] = []    # sources of mentions that could not be read

    # --- The Resolver protocol (jason.community.section_refs): the same reader the tokens use ----------------------

    def section(self, key: str, number: str, as_of: date | None = None) -> SectionText:
        return self.resolver.section(key, number, as_of)

    def citation(self, key: str, number: str) -> str:
        return self.resolver.citation(key, number)

    # --- Opening a citation ----------------------------------------------------------------------------------------

    def index(self) -> scoping.Index:
        """The documents a citation may mean, for scoping (``jason.community.scoping``)."""
        if self._index is None:
            self._index = build_index(self)
        return self._index

    def citing(self, key: str = "", day: Any = None) -> scoping.Citing:
        """The citing context for a document key ("" for text that is not one of the documents) and the day it was
        written."""
        return citing_of(self, key, day)

    def __call__(self, expression: str, *, citing: scoping.Citing | str | None = None, day: Any = None) -> Citation:
        """The citation ``expression`` names. ``citing`` is where it is written: a document's key (or a
        ``scoping.Citing``), with ``day`` the date it was written. A number with no document named is scoped to the
        document it means from where it is written; where two documents fit, the result is a miss that names both
        (``ambiguous_document``), never a guess. ``Citation.scope`` says how a document was chosen."""
        expression = str(expression or "")
        if (row := rule_rows.parse(expression)) is not None:
            return Citation(self, Target(Unit.ROW, row[0], row[1]), expression=expression,
                            scope=scoping.Scoped(scoping.Standing.SCOPED, scoping.Form.ROW, row[0], None, (), "",
                                                 number=row[1]))
        context = citing if isinstance(citing, scoping.Citing) else self.citing(str(citing or ""), day)
        parsed = parse(expression, self.names(), self.books)
        if isinstance(parsed, Miss) and parsed.reason is Reason.UNKNOWN_DOCUMENT:
            # A common name written with other punctuation or case ("CC & R's 4.2", "BY-LAWS 7.2"): the canon.
            m = re.match(r"^(?:the\s+)?(?P<name>.+?)['’]?\s*,?\s*(?P<rest>(?:§+|Sections?|Secs?\.|Arts?\.|Articles?)?\s*"
                         r"(?:[A-Z]{1,2}-)?\d.*)$", " ".join(expression.split()), re.I)
            doc = self.books.named(m.group("name")) if m else ""
            if doc:
                retry = parse(f"{doc} {m.group('rest')}", self.names(), self.books)
                if not isinstance(retry, Miss):
                    parsed = retry
        if isinstance(parsed, Target) and parsed.unit not in (Unit.SECTION, Unit.DOCUMENT):
            return Citation(self, parsed, expression=expression)
        found = self._scoped(expression, parsed, context)
        if found is not None:
            parsed, scope = found
        else:
            scope = (scoping.Scoped(scoping.Standing.SCOPED, scoping.Form.SECTION if parsed.number else scoping.Form.DOCUMENT,
                                    parsed.key, scoping.Basis.NAMED, number=parsed.number)
                     if isinstance(parsed, Target) else None)
        if isinstance(parsed, Miss):
            return Citation(self, None, miss=parsed, expression=expression, scope=scope)
        return Citation(self, parsed, expression=expression, scope=scope)

    def _scoped(self, expression: str, parsed: Target | Miss,
                context: scoping.Citing) -> tuple[Target | Miss, scoping.Scoped] | None:
        """Scope what ``expression`` reads as: the document it means, or every document that could be, or none. None
        when it is not a citation of the association's own documents (a statute, a resolution, an address), or when it
        is read as it always was (a document named by a name that is its own)."""
        index = self.index()
        clean = scoping.clean_expression(expression)
        mention = scoping.read_expression(clean, index.scan_names, lettered=index.lettered_prefixes())
        if mention is None:
            return None
        sc = scoping.scope(mention, context, index)
        if sc.standing is scoping.Standing.UNKNOWN_DOCUMENT:
            return (parsed, sc) if isinstance(parsed, Miss) else None
        if sc.standing is scoping.Standing.NOT_ON_SHELF:
            return Miss(Reason.NO_OUTLINE, sc.note, expression), sc
        if sc.standing is scoping.Standing.AMBIGUOUS:
            return Miss(Reason.AMBIGUOUS_DOCUMENT, self._ambiguity(mention, sc), expression), sc
        if sc.standing is scoping.Standing.NO_SECTION:
            return Miss(Reason.NOT_IN_DOCUMENT, self._ambiguity(mention, sc), expression), sc
        if isinstance(parsed, Target) and parsed.key == sc.key and sc.basis is scoping.Basis.NAMED:
            if context.day and self.resolver.living(sc.key) and not parsed.as_of:
                return replace(parsed, as_of=context.day), sc
            return parsed, sc
        # Scoped to a document the written words did not name alone: read the expression for that document.
        target = parse(scoping.rewrite(clean, mention, sc.key), self.names(), self.books)
        if isinstance(target, Miss):
            return target, sc
        if context.day and not target.as_of and self.resolver.living(sc.key) and target.unit in (Unit.SECTION, Unit.DOCUMENT):
            target = replace(target, as_of=context.day)      # the words as the citing document's day had them
        return target, sc

    def _ambiguity(self, mention: scoping.Mention, sc: scoping.Scoped) -> str:
        """Each document considered, with the citation it would be and whether it has the section."""
        number = sc.number or mention.number
        rows, without = [], []
        for c in sc.candidates:
            try:
                name = self.resolver.name(c.key)
            except SectionRefError:
                name = c.key
            if c.has or sc.standing is scoping.Standing.NO_SECTION:
                cited = citation_of(name, number, article=mention.article) if number else name
                rows.append(f"{cited} ({c.key}{'' if c.has else ': has no such section'})")
            else:
                without.append(c.key)
        lead = f"; the paragraph names {', '.join(sc.leads)} (a lead, not a pick)" if sc.leads else ""
        what = "documents that could be meant: " if sc.standing is scoping.Standing.AMBIGUOUS else "documents considered: "
        lacking = f"; without it: {', '.join(without)}" if without else ""
        hint = ""
        if mention.lettered and not any(c.has for c in sc.candidates):
            letters = sorted({self.index().docs[c.key].lettered for c in sc.candidates if self.index().docs[c.key].lettered})
            hint = ("; the rules documents here number their rules " + ", ".join(f"{x}-n" for x in letters)) if letters else ""
        return f"{sc.note or 'which document is meant is not written'}; {what}" + "; ".join(rows) + lacking + lead + hint

    def doc(self, name: str) -> Citation:
        key = self.names().get(str(name or "").strip().lower(), "")
        if not key and self.books.document(str(name or "").strip()) in set(self.names().values()):
            key = self.books.document(str(name).strip())          # a book's key: decl, rules.parking
        if not key:
            key = self.books.named(str(name or ""))                # a common name, any punctuation: "CC & R's"
        if not key:
            return Citation(self, None, miss=Miss(Reason.UNKNOWN_DOCUMENT, f"no document {name!r}", str(name)),
                            expression=str(name))
        return Citation(self, Target(Unit.DOCUMENT, key), expression=str(name))

    def statute(self, expression: str) -> Citation:
        found = self(expression)
        if found.target is not None and found.target.unit is not Unit.STATUTE:
            return Citation(self, None, miss=Miss(Reason.UNPARSED, f"{expression!r} is not a statute", expression),
                            expression=expression)
        return found

    def resolution(self, number: str) -> Citation:
        return Citation(self, Target(Unit.RESOLUTION, str(number).strip()), expression=f"Resolution {number}")

    def instrument(self, number: str) -> Citation:
        return Citation(self, Target(Unit.INSTRUMENT, str(number).strip()), expression=f"Doc. No. {number}")

    def minutes(self, day: str | date) -> Citation:
        day = day.isoformat() if isinstance(day, date) else str(day).strip()
        return Citation(self, Target(Unit.MINUTES, day), expression=f"minutes {day}")

    def record(self, kind: Any) -> Citation:
        value = getattr(kind, "value", str(kind)).strip()
        return Citation(self, Target(Unit.RECORD, value), expression=f"record:{value}")

    def notice(self, key: str, *, proof: bool = False) -> Citation:
        """A notice given to members, by its delivery ledger's key (``jason://notice/KEY``); ``proof`` its proof."""
        key = str(key).strip()
        return Citation(self, Target(Unit.NOTICE, key, "proof" if proof else ""),
                        expression=f"jason://notice/{key}" + ("/proof" if proof else ""))

    # --- What the shelf holds ----------------------------------------------------------------------------------------

    def outlines(self) -> dict[str, DocumentOutline]:
        if self._outlines is None:
            from jason.tasks.outlines import load

            folder = Path(self.data_dir) / "outlines"
            self._outlines = {o.key: o for o in load(self.data_dir)} if folder.is_dir() else {}
            for key, o in self._outlines.items():
                self.resolver._outlines.setdefault(key, o)
        return self._outlines

    def names(self) -> dict[str, str]:
        """Every name a document goes by (lowercase) and every key, to its key: the outlines on disk, then the
        specification's documents (their aliases, titles, and ``cite_as``), which win."""
        if self._names is None:
            out: dict[str, str] = {}
            for o in self.outlines().values():
                out[o.key.lower()] = o.key
                for alias in o.aliases:
                    out[alias.lower()] = o.key
            for d in getattr(self.community, "living_documents", lambda: ())():
                out[d.key.lower()] = d.key
                out[d.title.lower()] = d.key
            for d in getattr(self.community, "citable_documents", lambda: ())():
                for name in (d.key, d.title, getattr(d, "cite_as", ""), *d.aliases):
                    if name:
                        out[name.lower()] = d.key
            # The canon of common names (jason.community.books.CANON), for a book the profile fills; never over a
            # name the profile's own documents use.
            from jason.community.books import CANON

            keys = set(out.values())
            for book, common in CANON.items():
                doc = self.books.document(book.value)
                if doc in keys:
                    for name in common:
                        out.setdefault(name.lower(), doc)
                    out.setdefault(book.value, doc)
            self._names = out
        return self._names

    def title(self, key: str) -> str:
        try:
            return self.resolver.name(key)
        except SectionRefError:
            return key

    def rows(self) -> list[dict[str, Any]]:
        """The references the governing documents make (``jason outlines`` writes them); read from the outlines when
        that file is not there."""
        if self._rows is None:
            from jason.tasks.outlines import load_rows, references

            rows = load_rows(self.data_dir)
            if not rows and self.outlines():
                rows = [r.to_dict() for r in references(list(self.outlines().values()))]
            self._rows = rows
        return self._rows

    # --- Addresses and permanent ids ------------------------------------------------------------------------------------

    @property
    def locator(self) -> Any:
        if self._locator is None:
            from jason.tasks.permanent_ids import Locator

            self._locator = Locator(self.resolver, self.books)
        return self._locator

    def address(self, t: Target | None) -> str:
        """The target's ``jason://`` address; empty for a statute (lawlibrary's) or a record kind."""
        from jason.community.addresses import Address

        if t is None:
            return ""
        if t.unit in (Unit.SECTION, Unit.DOCUMENT):
            body = ",".join(t.siblings) if t.siblings else (t.number + (f"..{t.end}" if t.end else ""))
            version = t.version if t.version else ""
            in_force = t.as_of if t.as_of and not version else None
            return Address(self.books.key(t.key), body, version=version, in_force=in_force, history=t.history,
                           fragment=t.fragment).format()
        series = {Unit.RESOLUTION: "res", Unit.MINUTES: "min", Unit.INSTRUMENT: "inst"}
        if t.unit in series:
            if t.unit is Unit.INSTRUMENT and not t.key.isdigit():
                return ""
            return Address(series[t.unit], item=t.key, version=t.version, fragment=t.fragment).format()
        if t.unit is Unit.BOOK:
            return Address(t.key, item=t.number, version=t.version, fragment=t.fragment).format()
        if t.unit is Unit.NOTICE:
            return Address(Book.NOTICE.value, t.number, t.key, fragment=t.fragment).format()
        return ""

    def pid(self, t: Target | None) -> str:
        """A section's permanent id, in the version it is read at; empty when no table knows it."""
        if t is None or t.unit is not Unit.SECTION or t.end or t.siblings:
            return ""
        table = self.locator.table(t.key)
        if table is None:
            return ""
        return table.permanent_id(t.number, t.as_of) or ""

    def register(self) -> dict[str, list[dict[str, Any]]]:
        if self._register is None:
            from jason.tasks.permanent_ids import load_register

            self._register = load_register(self.data_dir)
        return self._register

    # --- Resolving a target ------------------------------------------------------------------------------------------

    def state(self, t: Target) -> State:
        if t.id not in self._states:
            try:
                self._states[t.id] = self._resolve(t)
            except SectionRefError as exc:
                detail = str(exc)
                if _reason(exc) is Reason.NOT_IN_DOCUMENT and t.unit is Unit.SECTION:
                    detail += self._numbering_hint(t)
                self._states[t.id] = _miss(_reason(exc), detail)
        return self._states[t.id]

    def _numbering_hint(self, t: Target) -> str:
        """How the document does number its sections, when the number asked is not that way ("Rule 2.1" of a document
        that numbers its rules R-3(a)): so the miss says what to cite."""
        info = self.index().docs.get(t.key)
        if info is None or not info.lettered or re.match(r"[A-Z]{1,2}-", t.number):
            return ""
        return f"; {t.key} numbers its sections {info.lettered}-n (for example {info.lettered}-1)"

    def _resolve(self, t: Target) -> State:
        if t.unit is Unit.BOOK:
            return self._book(t)
        if t.unit in (Unit.SECTION, Unit.DOCUMENT) and (t.version or t.history):
            versioned = self._versioned(t)
            if versioned is not None:
                return versioned
        if t.unit is Unit.SECTION:
            if t.end:
                return self._span(t)
            if t.siblings:
                return self._siblings(t)
            return self._section(t)
        if t.unit is Unit.DOCUMENT:
            return self._document(t)
        if t.unit is Unit.ROW:
            return self._row(t)
        if t.unit is Unit.STATUTE:
            return self._statute(t)
        if t.unit is Unit.RESOLUTION:
            return self._resolution(t)
        if t.unit is Unit.INSTRUMENT:
            return self._instrument(t)
        if t.unit is Unit.MINUTES:
            return self._minutes(t)
        if t.unit is Unit.NOTICE:
            return self._notice(t)
        return self._record(t)

    def _book(self, t: Target) -> State:
        """An item of a series book named by an address: refused when the book is restricted and the shelf is not
        private; otherwise the record kind it is, the statute, and where the profile keeps it."""
        from jason.community.books import split_key

        book, _ = split_key(t.key)
        cite = f"{book.info.title if book else t.key}" + (f", {t.number}" if t.number else "")
        if book is None:
            return _miss(Reason.UNKNOWN_RECORD, f"no book {t.key!r}", cite)
        if book.restricted and not self.private:
            return _miss(Reason.RESTRICTED, f"{book.info.title} may be withheld ({book.restricted}): ask with "
                         "private=True (jason cite --private)", cite, statute=book.restricted)
        if book is Book.GOV:
            return self._governing()
        if book is Book.NOTICE and not t.number:
            return self._notices()
        if book is Book.AGENDA and t.number:
            from jason.tasks.meeting_catalog import load

            meeting = next((m for m in load(self.data_dir).get("meetings", []) if m.get("date") == t.number), None)
            rows = [r for r in (meeting or {}).get("records", []) if r.get("kind") == "agenda"]
            if rows:
                return State(Kind.RECORD, True, citation=f"agenda of the meeting of {t.number}", title=rows[0].get(
                    "name", ""), version={"statute": book.info.statute}, nodes=[
                    {"kind": r["kind"], "where": r.get("where"), "location": r.get("location")} for r in rows])
            return _miss(Reason.NO_MINUTES, "no agenda on that day in the meeting catalog (jason meetings)", cite)
        state = self._record(Target(Unit.RECORD, book.info.record.value)) if book.info.record else None
        version = {"statute": book.info.statute, "book": book.value, "item": t.number,
                   "note": "jason does not index this series by item: the record kind and where the profile keeps it"}
        if book.restricted:
            version["restricted"] = book.restricted
        law = self(book.info.statute).state if book.info.statute else None
        return State(Kind.RECORD, True, citation=cite, title=book.info.title, text=law.text if law and law.found else "",
                     version=version, nodes=state.nodes if state else [])

    def _governing(self) -> State:
        """The governing documents as a set: the Act's list (CIV 4150) with the profile's documents in each book, then
        the set the association's own documents define, and how the two differ (reported, not resolved)."""
        from jason.community.books import STATUTE_GOVERNING
        from jason.community.definitions import compare_governing

        law = self("CIV 4150").state
        def node(where: str, b: Any, note: str = "") -> dict[str, Any]:
            docs = [e.document for e in self.books.entries if e.book is b and e.role.value != "amendment"]
            row = {"set": where, "book": b.value, "title": b.info.title, "documents": docs, "note": note}
            if b.info.shape.value == "series":
                row["series"] = f"a series: jason://{b.value}/{b.info.item.replace(' ', '-').upper()}"
            elif not docs:
                row["note"] = note or "the profile maps no document to it"
            return row

        nodes = [node("statute (CIV 4150)", b) for b in STATUTE_GOVERNING]
        defined = getattr(self.community, "governing_set", lambda: None)()
        found = compare_governing(defined, STATUTE_GOVERNING)
        extra: dict[str, Any] = {"differences": {"onlyInTheDocuments": [b.value for b in found.only_profile],
                                                 "onlyInTheStatute": [b.value for b in found.only_statute],
                                                 "alsoNamed": list(found.also), "notes": found.notes}}
        if defined is not None:
            where = parse(defined.defined_at, self.names(), self.books)
            words = self.state(where).text if isinstance(where, Target) else ""
            nodes += [node(f"the documents' own term ({defined.defined_at})", b, defined.note) for b in defined.books]
            extra["definedAt"] = {"target": defined.defined_at, "address": self.address(where)
                                  if isinstance(where, Target) else "", "words": words}
        return State(Kind.OUTLINE, True, citation="the governing documents (CIV 4150)", title="the governing documents",
                     text=law.text if law.found else "", version={"statute": "CIV 4150", "source": law.version.get(
                         "source", "")}, nodes=nodes, extra=extra)

    def defined_terms(self, t: Target | None, words: str) -> list[dict[str, Any]]:
        """The terms the section's own document defines that its words use, each with the definition's words and
        address: the document's meaning governs its own words (Civil Code 1644)."""
        from jason.community.definitions import used_in

        if t is None or t.unit is not Unit.SECTION or not words:
            return []
        rows = tuple(getattr(self.community, "defined_terms", lambda: ())())
        out = []
        for term in used_in(words, rows, document=t.key):
            if term.section == t.number:
                continue
            where = Target(Unit.SECTION, term.document, normalize_number(term.section))
            st = self.state(where)
            out.append({"term": term.term, "definedAt": term.target, "address": self.address(where),
                        "citation": st.citation or term.target, "definition": st.text if st.found else "",
                        "found": st.found})
        return out

    def _versioned(self, t: Target) -> State | None:
        """A section or a document at an address's version: the base, the version made effective on a day (a miss
        when none was), a stage (a draft's words, never in force), or the section's history. None to read it as
        usual (the version is ``as_of``)."""
        from jason.community.addresses import VersionLabel
        from jason.community.revisions import Stage
        from jason.tasks.permanent_ids import effective_dates, timeline

        living = self.resolver.living(t.key)
        if t.history:
            if t.unit is not Unit.SECTION:
                return _miss(Reason.UNPARSED, "a history names a section: jason://decl/history/6.2(a)")
            found = timeline(self.locator, t.key, t.number, day=t.as_of)
            if found is None:
                return _miss(Reason.NOT_IN_DOCUMENT, f"no permanent id answers to {t.number}")
            name = self.resolver.name(t.key)
            return State(Kind.HISTORY, True, citation=citation_of(name, t.number) + ", history", title=name,
                         nodes=found["versions"], version={"pid": found["pid"], "born": found["born"],
                                                           "removed": found["removed"]},
                         extra={"readings": found["readings"]})
        label = VersionLabel(t.version)
        if label.stage is not None:
            if label.stage is not Stage.DRAFT or living is None or t.unit is not Unit.SECTION:
                return _miss(Reason.NO_VERSION, f"no {label.stage.value} version of {t.key} on disk: a stage version "
                             "is read from the record's stages (rule changes, minutes)", self.address(t))
            v = self.resolver.versions(t.key)
            ops = [op for op in v.pending if normalize_number(op.get("section", "")) == t.number]
            info = [v.instruments.get(op["instrument"]) or {} for op in ops]
            want = label.day
            ops = [(op, i) for op, i in zip(ops, info) if want is None or i.get("dated") == want.isoformat()]
            if not ops:
                return _miss(Reason.NO_VERSION, f"no draft of {t.key} sets {t.number}", self.address(t))
            op, i = ops[0]
            name = self.resolver.name(t.key)
            return State(Kind.SECTION, True, citation=f"{citation_of(name, t.number)}, as {i.get('describe') or op['instrument']} "
                         "would set it", title=name, text=op["after"],
                         version={"stage": label.stage.value, "inForce": False, "instrument": op["instrument"],
                                  "describe": i.get("describe"), "note": "a draft: not in force, and never merged into "
                                                                         "the text in force"})
        if living is None:
            if label.base or t.version == "":
                return None
            return _miss(Reason.NOT_KEPT_AS_AMENDED, f"{t.key} is not kept as amended: it has one version, @base", self.address(t))
        v = self.resolver.versions(t.key)
        days = effective_dates(v)
        if label.base:
            day = v.snapshots[0].until if len(v.snapshots) > 1 else None
            return self.state(replace(t, version="", as_of=day)) if day else self.state(replace(t, version=""))
        if label.effective is not None and label.effective not in days:
            shown = ", ".join(["base", *(d.isoformat() for d in days[1:])])
            return _miss(Reason.NO_VERSION, f"no version of {t.key} took effect on {label.effective.isoformat()}; its "
                         f"versions: {shown}", self.address(t))
        return self.state(replace(t, version=""))

    def _links(self, key: str) -> list[dict[str, str]]:
        """Where a person checks the words: the Doc an outline was read from, the library file a living document's
        base was read from, a scan in Drive. Links only; nothing is fetched."""
        out: list[dict[str, str]] = []
        living = self.resolver.living(key)
        if living is not None:
            ref = living.base
            kind = getattr(ref.kind, "value", str(ref.kind))
            if kind == "library-text":
                out.append({"what": "the base as recorded (library)", "library": ref.ref})
            else:
                out.append({"what": "the base", "url": f"https://drive.google.com/file/d/{ref.ref}/view"})
            if living.working_doc:
                out.append({"what": "the working copy kept by hand",
                            "url": f"https://docs.google.com/document/d/{living.working_doc}/edit"})
        outline = self.resolver.outline(key)
        if outline is not None and outline.source:
            out.append({"what": "the Doc as outlined", "url": f"https://docs.google.com/document/d/{outline.source}/edit"})
        if outline is not None and outline.library:
            out.append({"what": "the library file", "library": outline.library})
        return out

    def _open(self, t: Target) -> tuple[str, Any, Any]:
        r = self.resolver
        if not r.known(t.key):
            raise SectionRefError(f"no document {t.key!r}", "unknown_document")
        doc, versions = r.document(t.key, t.as_of)
        return r.name(t.key), doc, versions

    def _section(self, t: Target) -> State:
        name, doc, versions = self._open(t)
        p = self.resolver.provision(doc, t.key, t.number)
        article = t.article or is_article(p)
        cite = citation_of(name, t.number, article=article)
        if article and re.fullmatch(r"\d+", t.number):
            return self._outline_of(t, doc, [q for q in doc.provisions if q.number and _inside(q.number, t.number)],
                                    cite, versions)
        if p.removed:
            return _miss(Reason.REMOVED, f"removed by {p.set_by}" + (f" ({p.dated.isoformat()})" if p.dated else "")
                         + "; cite it as of an earlier day", cite)
        st = self.resolver.section(t.key, t.number, t.as_of)
        # "amended" and "dated" are the words recited, subsections and all, so they agree with the history; "setBy" is
        # who set the section's own words, and "parts" the subsections another instrument set.
        version = {"document": st.document, "setBy": st.set_by, "setByTitle": st.set_by_title,
                   "dated": _day(st.changed_on), "amended": st.changed, "asOf": _day(st.as_of), "source": st.source,
                   "note": st.note, "provenance": st.provenance(), "digest": st.digest, "caption": st.caption,
                   "living": versions is not None,
                   "parts": [{"section": q.number, "setByTitle": q.set_by_title, "dated": _day(q.dated)}
                             for q in st.parts]}
        return State(Kind.SECTION, True, citation=st.citation, title=doc.title, text=st.words, version=version,
                     outline=t.key, numbers=(t.number,), links=self._links(t.key))

    def _row(self, t: Target) -> State:
        """One of jason's own rule rows (or a whole table of them), recited as data and labeled as jason's."""
        r = rule_rows.recite(t.key, t.number, self.community)
        if not r.found:
            return _miss(Reason.NOT_IN_DOCUMENT if r.reason == "no_such_row" else Reason.UNKNOWN_RECORD, r.detail, r.citation)
        extra = {k: v for k, v in rule_rows.as_dict(r).items() if k in ("row", "rows", "adoption", "table")}
        return State(Kind.ROW, True, citation=r.citation, title=r.title, text=r.text,
                     version={"source": f"{r.source}, as it is written now", "note": rule_rows.LABEL}, extra=extra)

    def titled(self, t: Target) -> State | None:
        """A section named by the words of its heading ("covenants#USE"), read as the one section whose title is those
        words (an article's "ARTICLE 4" aside), or starts with them when they are several. Only when exactly one does;
        two that fit are a miss, not a pick."""
        if t.unit is not Unit.SECTION or t.end or t.siblings or not t.number or re.match(r"(?:[A-Z]{1,2}-)?\d", t.number):
            return None
        outline = self.outlines().get(t.key)
        if outline is None:
            return None
        wanted = " ".join(t.number.casefold().replace("_", " ").split())
        found = []
        for s in outline.sections:
            title = re.sub(r"^\s*(?:article\s+[ivxlc\d]+\s*[-–.:]?\s*)", "", " ".join(s.title.casefold().split()))
            # The heading itself, or its first words when they are several ("MEETINGS" alone would fit "MEETINGS OF
            # MEMBERS" and "MEETINGS OF DIRECTORS" alike: a miss, not a pick).
            if s.number and (title == wanted or (len(wanted.split()) > 1 and title.startswith(wanted + " "))):
                found.append(s)
        if len(found) != 1:
            return None
        try:
            state = self._section(replace(t, number=found[0].number, article=found[0].depth == 1))
        except SectionRefError:
            return None
        state.version = {**state.version, "titled": {"from": t.number, "to": found[0].number,
                                                     "note": f"named by its heading: {found[0].title}"}}
        return state

    def former(self, t: Target) -> State | None:
        """A section number the document no longer (or not yet) has, found by its permanent id under the number it has
        now: a former number is read as its successor, named as such. Only a citation asks this (``Citation.state``); the
        checks of what cites a section (``treat``) keep a missing number missing, so ``jason cite --stale`` still lists
        it. None when no id places it, or more than one does (a miss stays a miss)."""
        base = self.state(t)
        if base.found or base.reason not in (Reason.NOT_IN_DOCUMENT, Reason.PARENT_ONLY) or t.unit is not Unit.SECTION \
                or t.end or t.siblings or not t.number:
            return None
        try:
            found = self.locator.locate(t.key, t.number, day=t.as_of)
        except Exception as err:  # a table that cannot be built leaves the miss as it was
            self.unread.append(f"permanent ids of {t.key}: {err}")
            return None
        if found is None or found.ambiguous or found.removed or not found.number or found.number == t.number:
            return None
        try:
            state = self._section(replace(t, number=found.number))
        except SectionRefError:
            return None
        state.version = {**state.version, "renumbered": {"from": t.number, "to": found.number, "pid": found.pid,
                                                         "note": f"{t.number} is a number this document had; a permanent "
                                                                 f"id places it at {found.number} now"}}
        return state

    def _outline_of(self, t: Target, doc: Any, parts: list[Any], cite: str, versions: Any) -> State:
        nodes = [{"number": q.number, "caption": q.caption, "depth": q.depth, "setBy": q.set_by,
                  "amended": q.standing is not None, "removed": q.removed} for q in parts]
        return State(Kind.OUTLINE, True, citation=cite, title=doc.title, nodes=nodes, outline=t.key,
                     numbers=tuple(q["number"] for q in nodes) or ("",), links=self._links(t.key),
                     version={"living": versions is not None, "asOf": _day(t.as_of)})

    def _document(self, t: Target) -> State:
        name, doc, versions = self._open(t)
        parts = [p for p in doc.provisions if p.number and p.depth <= OUTLINE_DEPTH]
        state = self._outline_of(t, doc, parts, name, versions)
        state.numbers = ("",)
        if versions is not None:
            state.version["through"] = versions.at(t.as_of).through
        return state

    def _span(self, t: Target) -> State:
        name, doc, versions = self._open(t)
        numbered = [p for p in doc.provisions if p.number]
        at = {p.number: k for k, p in enumerate(numbered)}
        for n in (t.number, t.end):
            if n not in at:
                self.resolver.provision(doc, t.key, n)          # raises with the reason
        first, last = at[t.number], at[t.end]
        if last < first:
            return _miss(Reason.UNPARSED, f"{t.end} comes before {t.number}")
        stop = last + 1
        while stop < len(numbered) and _inside(numbered[stop].number, t.end):
            stop += 1
        cite = f"{name} Sections {t.number} through {t.end}"
        return self._outline_of(t, doc, numbered[first:stop], cite, versions)

    def _siblings(self, t: Target) -> State:
        name, doc, versions = self._open(t)
        nodes, missing = [], []
        for n in t.siblings:
            try:
                p = self.resolver.provision(doc, t.key, n)
                nodes.append({"number": n, "caption": p.caption, "found": not p.removed,
                              "reason": "removed" if p.removed else ""})
                if p.removed:
                    missing.append(n)
            except SectionRefError as exc:
                nodes.append({"number": n, "found": False, "reason": _reason(exc).value})
                missing.append(n)
        cite = f"{name} Sections {_series(t.siblings)}"
        state = State(Kind.OUTLINE, not missing, None if not missing else Reason.NOT_IN_DOCUMENT,
                      f"not there: {', '.join(missing)}" if missing else "", cite, doc.title, nodes=nodes,
                      outline=t.key, numbers=t.siblings, links=self._links(t.key))
        return state

    def _statute(self, t: Target) -> State:
        from jason.tasks.export_authorities import authority_pages, authority_text, on_demand_pages
        from jason.tasks.statute_fetch import caller

        cite = t.id
        pointer = {"lawlibrary": {"call": "cite", "expression": t.base if not t.end else t.id}}
        base_number = t.number.split("(", 1)[0]
        whole = re.match(r"\d+", base_number)
        dated = None
        if t.as_of is not None and not t.end and not t.siblings:
            # The words in force that day, where the disk shows which they were (an earlier version kept with its
            # range, or the current words): never another day's words in their place.
            from jason.community import law_text

            dated = law_text.in_force(t.base, self.data_dir, t.as_of)
            if dated.text is not None:
                return self._dated_statute(t, dated, pointer)
        if t.key == "CIV" and whole and 1350 <= int(whole.group(0)) <= 1378:
            return _miss(Reason.PRIOR_NUMBERING, "a Davis-Stirling number from before the 2014 renumbering: its successor "
                         f"is read with jason law-history, or lawlibrary succession.successors('CIV', '{base_number}')",
                         cite, pointer=pointer)
        if t.end:
            def span_nodes() -> list[dict[str, Any]]:
                return [{"first": p.start, "last": p.end, "title": p.title, "file": p.file, "session": p.session}
                        for p in (*authority_pages(self.data_dir), *on_demand_pages(self.data_dir)) if p.code == t.key
                        and _key(p.start) <= _key(t.end) and _key(p.end) >= _key(t.number)]

            nodes = span_nodes()
            if not nodes:
                from jason.tasks.statute_fetch import ensure

                got = ensure(self.data_dir, t.key, t.number, t.end, asked_by=caller())
                nodes = span_nodes() if got.found else []
                if not nodes:
                    why = got.miss.value if got.miss else ""
                    reason = _LIBRARY_MISS.get(why, Reason.STATUTE_NOT_ON_DISK)
                    detail = got.reason_text() if why in _LIBRARY_MISS else "no exported pages in that span"
                    return _miss(reason, detail + (f" ({got.detail})" if got.detail else ""), cite, pointer=pointer)
            return State(Kind.OUTLINE, True, citation=cite, nodes=nodes, extra={"pointer": pointer})
        if t.siblings:
            nodes = []
            for n in t.siblings:
                one = self.state(Target(Unit.STATUTE, t.key, n))
                nodes.append({"number": n, "found": one.found, "reason": one.reason.value if one.reason else ""})
            ok = all(n["found"] for n in nodes)
            return State(Kind.OUTLINE, ok, None if ok else Reason.LABEL_NOT_FOUND, "", cite, nodes=nodes)
        if t.as_of is not None:
            why = f"{dated.basis}; {dated.caveats[-1]}" if dated is not None and dated.caveats else \
                "jason holds the words of a day only for one section at a time (jason law-history --versions)"
            return _miss(Reason.EDITION_NOT_HELD, why, cite, pointer=pointer)
        got = authority_text(self.data_dir, t.base, asked_by=caller())
        if not got.get("found"):
            detail = got.get("reason", "") + (f" ({got['detail']})" if got.get("detail") else "")
            extra = {"suggest": got["suggest"]} if got.get("suggest") else {}
            return _miss(_LIBRARY_MISS.get(str(got.get("miss") or ""), Reason.STATUTE_NOT_ON_DISK), detail, cite,
                         pointer=pointer, **extra)
        words = got.get("text", "")
        version = {"source": got.get("page", ""), "session": got.get("session", ""), "heading": got.get("title", ""),
                   "official": True}
        notes: list[str] = []
        if got.get("version"):
            # Printed in two versions under the one number: which is quoted and why, in the versions' own words, or
            # that the disk does not decide and both are quoted. Never the first by position.
            notes.append(got["version"])
            version.update({k: got[k] for k in ("asOf", "decided", "digest", "undecided") if got.get(k)})
            version["decidingWords"] = list(got.get("quotes") or [])
            version["versions"] = [{k: row[k] for k in ("digest", "quoted", "label")} for row in got.get("versions") or []]
        if t.labels:
            labels = "".join(f"({x})" for x in t.labels)
            if got.get("undecided"):
                # Each version's subdivision under its own label: the first one's is never quoted for both.
                from jason.tasks.export_authorities import version_label

                parts = [(row, label_text(row.get("text", ""), t.labels)) for row in got.get("versions") or []]
                part = "\n\n".join(f"{version_label(row['label'])}\n\n{text or f'{labels} is not in this version.'}"
                                   for row, text in parts) if any(text for _, text in parts) else ""
            else:
                part = label_text(words, t.labels)
            if not part:
                return _miss(Reason.LABEL_NOT_FOUND, f"{t.base} is on disk; jason could not find "
                             f"{labels} in its words", cite, pointer=pointer)
            words = part
            version["official"] = False
            notes.append("the subdivision's words, split by jason from the exported section; the whole section "
                         "is the official text")
        if notes:
            version["note"] = "; ".join(notes)
        return State(Kind.STATUTE, True, citation=cite, title=got.get("title", ""), text=words, version=version,
                     extra={"pointer": pointer})

    def _dated_statute(self, t: Target, dated: Any, pointer: dict[str, Any]) -> State:
        """A statute's section as of a day, from ``law_text.in_force``: the words, the range they were in force, and
        how jason knows."""
        from jason.community import law_text

        held = dated.text
        words = held.words
        version = {"source": held.page or f"{law_text.HISTORY_DIR}/{law_text.slug(held.citation)}/{held.digest}.md",
                   "session": held.session, "publisher": held.source, "digest": held.digest, "official": not held.added,
                   "asOf": t.as_of.isoformat(), "inForce": dated.basis, "decided": dated.decided.value,
                   "current": held.current}
        # The section's own words that decide which version governed the day, quoted before the caveats (a caveat
        # about the other version quotes that version's own sentence itself).
        notes = [f"own words that decide it: \"{q}\"" for q in dated.quotes if not any(q in c for c in dated.caveats)]
        notes += list(dated.caveats)
        if dated.quotes:
            version["decidingWords"] = list(dated.quotes)
        if t.labels:
            part = label_text(words, t.labels)
            if not part:
                return _miss(Reason.LABEL_NOT_FOUND, f"{t.base} as of {t.as_of.isoformat()} is on disk; jason could not "
                             f"find {''.join(f'({x})' for x in t.labels)} in its words", t.id, pointer=pointer)
            words = part
            version["official"] = False
            notes.append("the subdivision's words, split by jason from the section; the whole section is the official text")
        if notes:
            version["note"] = "; ".join(notes)
        return State(Kind.STATUTE, True, citation=t.id, text=words, version=version, extra={"pointer": pointer})

    def _resolution(self, t: Target) -> State:
        claim = [o for o in self.outlines().values() if t.key in o.numbers]
        cite = f"Resolution {t.key}"
        if not claim:
            return _miss(Reason.NO_RESOLUTION, "no resolution Doc on disk prints that number (jason outlines --fetch "
                         "reads the resolutions folder)", cite)
        if len(claim) > 1:
            return _miss(Reason.PRINTED_BY_SEVERAL, "several Docs print that number: a duplicate number, or a header "
                         "copied from another resolution", cite, claimants=[o.key for o in claim])
        o = claim[0]
        draft = "draft" in (o.title + " " + o.key).lower()
        return State(Kind.RECORD, True, citation=cite, title=o.title, text=o.text, outline=o.key, numbers=("",),
                     version={"source": f"the Doc as outlined (data/outlines/{o.key}.json)", "draft": draft,
                              "note": "a draft: not adopted" if draft else ""},
                     links=self._links(o.key))

    def _governing_instruments(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        try:
            ccrs = self.community.ccrs()
            for d in getattr(ccrs, "instruments", ()):
                if getattr(d, "recorder_number", ""):
                    out[d.recorder_number] = {"title": d.title, "recorded": _day(getattr(d, "recorded", None)),
                                              "drive": getattr(d, "drive_id", "")}
        except Exception:
            pass
        for living in getattr(self.community, "living_documents", lambda: ())():
            for li in living.instruments:
                number = getattr(li.document, "recorder_number", "") or ""
                if number:
                    row = out.setdefault(number, {"title": getattr(li.document, "title", li.key),
                                                  "recorded": _day(getattr(li.document, "recorded", None))})
                    row["outline"] = li.key
                    row["amends"] = living.key
        return out

    def _instrument(self, t: Target) -> State:
        cite = f"Doc. No. {t.key}" if t.key.isdigit() else t.key
        known = self._governing_instruments().get(t.key)
        if known:
            key = known.get("outline", "")
            outline = self.resolver.outline(key) if key else None
            version = {"recorded": known.get("recorded"), "amends": known.get("amends", ""),
                       "source": f"the Doc as outlined (data/outlines/{key}.json)" if outline else ""}
            return State(Kind.RECORD, True, citation=f"{known['title']}, {cite}", title=known["title"],
                         text=outline.text if outline else "", version=version, outline=key if outline else "",
                         numbers=("",), links=self._links(key) if key else [])
        found = self._library_named(t.key)
        if found:
            path, words = found
            return State(Kind.RECORD, True, citation=cite, title=Path(path).name, text=words,
                         version={"source": f"the library's text of {path}", "note": "read by OCR if scanned"},
                         links=[{"what": "the library file", "library": path}])
        indexed = self._county(t.key)
        if indexed:
            return State(Kind.RECORD, True, citation=cite, title=indexed.get("filing", ""), version=indexed,
                         extra={"note": "in the county index cache; no text on disk (recorder_detail reads it)"})
        return _miss(Reason.UNKNOWN_INSTRUMENT, "not a governing instrument the specification names, a library file, "
                     "or in the county index cache; the board MCP's recorder_detail(number) reads the county index", cite)

    def _library_named(self, number: str) -> tuple[str, str] | None:
        db = Path(self.data_dir) / "library" / "library.db"
        if not number.isdigit() or not db.is_file():
            return None
        with sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True) as conn:
            rows = conn.execute("SELECT id, path, confidential FROM documents WHERE path LIKE ?",
                                (f"%{number}%",)).fetchall()
        for doc_id, path, secret in rows:
            text = Path(self.data_dir) / "library" / "text" / f"{doc_id}.txt"
            if not secret and text.is_file():
                return path, text.read_text(encoding="utf-8", errors="replace")
        return None

    def _county(self, number: str) -> dict[str, Any] | None:
        if not (Path(self.data_dir) / "index-cache.db").is_file():
            return None
        try:
            from jason.tasks.property_history import load_association_record

            record = load_association_record(self.community, Path(self.data_dir))
        except Exception:
            return None
        for r in getattr(record, "governing", ()):
            if r.number == number:
                return {"recorded": _day(r.recorded), "filing": r.filing, "role": r.role, "status": r.status,
                        "cites": list(r.cites)}
        return None

    def _minutes(self, t: Target) -> State:
        from jason.tasks.meeting_catalog import load

        cite = f"minutes of the meeting of {t.key}"
        catalog = load(self.data_dir)
        meeting = next((m for m in catalog.get("meetings", []) if m.get("date") == t.key), None)
        if meeting is None:
            return _miss(Reason.NO_MINUTES, "no meeting records on that day in the catalog (jason meetings)", cite)
        records = [r for r in meeting.get("records", []) if r.get("kind") in ("minutes", "draft minutes")]
        if not records:
            return _miss(Reason.NO_MINUTES, "the meeting has records, but no minutes: "
                         + ", ".join(sorted(meeting.get("has", {}))), cite)
        final = [r for r in records if r["kind"] == "minutes"]
        chosen = (final or records)[0]
        words, source = "", ""
        for r in final or records:
            if r.get("confidential"):
                continue
            words, source = self._minutes_text(r)
            if words:
                chosen = r
                break
        version = {"source": source, "draft": not final, "where": chosen.get("where"), "location": chosen.get("location"),
                   "note": "draft minutes only" if not final else ("" if words else "no text on disk for these minutes")}
        return State(Kind.RECORD, True, citation=cite, title=chosen.get("name", ""), text=words, version=version,
                     nodes=[{"kind": r["kind"], "where": r.get("where"), "location": r.get("location"),
                             "confidential": r.get("confidential", False)} for r in records])

    def _notices(self) -> State:
        """The notice book: every notice in the delivery ledger, newest first, with how strongly it shows the notice
        given (counts only)."""
        from jason.tasks.notice_evidence import ledger, recent
        from jason.tasks.schedule_evidence import Stores

        found = ledger(self.data_dir, Stores(self.data_dir, self.community).local_day)
        nodes = [{"number": key, "address": f"jason://notice/{key}", "caption": found[key].describe() if key in found
                  else "", "sent": (sent or "")[:10]} for key, sent in recent(self.data_dir)]
        law = self(Book.NOTICE.info.statute).state
        return State(Kind.RECORD, True, citation=Book.NOTICE.info.title, title=Book.NOTICE.info.title,
                     text=law.text if law.found else "", nodes=nodes,
                     version={"statute": Book.NOTICE.info.statute, "book": Book.NOTICE.value,
                              "note": "jason's own record of each notice, by its delivery ledger's key (jason notices "
                                      "KEY --sync); counts only, a member's unit only privately"})

    def _notice(self, t: Target) -> State:
        """A notice as a record (``jason.tasks.notice_record``): the requirement recited, the text sent, the fill
        records, the recipients' counts, the delivery standing, the proof, and the stage it served. ``/proof`` is the
        proof alone. Counts only unless the shelf is private."""
        from jason.tasks import notice_record as nr

        cite = f"notice {t.key}" + (", proof of notice" if t.number == "proof" else "")
        if t.number not in ("", "proof"):
            return _miss(Reason.UNPARSED, f"a notice has its record and its proof: jason://notice/{t.key} or "
                         f"jason://notice/{t.key}/proof, not {t.number!r}", cite)
        r = nr.build(t.key, shelf=self, private=self.private)
        if r is None:
            return _miss(Reason.UNKNOWN_RECORD, f"nothing under {t.key} in the delivery ledger, the batches, or "
                         "data/notices (jason notices lists the ledger; jason notices KEY --sync reads one)", cite)
        req = r.get("requirement") or {}
        title = f"{req.get('title')} ({t.key})" if req else t.key
        standing = (r.get("standing") or {}).get("describe", "nothing in the delivery ledger")
        if t.number == "proof":
            p = r.get("proof")
            if p is None:
                return _miss(Reason.UNKNOWN_RECORD, "no catalog requirement fits this key, so its proof cannot be "
                             f"built: jason notices {t.key} --proof --requirement KEY", cite)
            return State(Kind.RECORD, True, citation=cite, title=f"Proof of notice: {title}",
                         version={"requirement": p["requirement"], "complete": p["complete"],
                                  "note": "jason's record of the evidence; whether notice was sufficient is for the "
                                          "board or counsel"},
                         nodes=nr.nodes(r, proof_page=True),
                         extra={"proof": p, "sections": [("Proof of notice", nr.proof_lines(p))]})
        text = r["text"]
        version = {"source": text["source"], "requirement": req.get("key", ""), "standing": standing,
                   "note": ("the notice as sent, edited since it was kept" if text["words"] and text.get("edited")
                            else "the notice as sent" if text["words"] else
                            "jason does not have the text as sent; the record below is what it keeps")}
        if text.get("digest"):
            version["digest"] = text["digest"]
        return State(Kind.RECORD, True, citation=cite, title=title, text=text["words"], version=version,
                     nodes=nr.nodes(r), extra={"notice": r, "sections": nr.sections(r)})

    def _minutes_text(self, record: dict[str, Any]) -> tuple[str, str]:
        ref = record.get("ref") or ""
        own = Path(self.data_dir) / "meetings" / "minutes-files" / f"{ref}.txt"
        if ref and own.is_file():
            return own.read_text(encoding="utf-8", errors="replace"), f"data/meetings/minutes-files/{ref}.txt"
        db = Path(self.data_dir) / "library" / "library.db"
        if record.get("where") == "PayHOA library" and db.is_file():
            with sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True) as conn:
                row = conn.execute("SELECT id, confidential FROM documents WHERE path = ?",
                                   (record.get("location", ""),)).fetchone()
            if row and not row[1]:
                text = Path(self.data_dir) / "library" / "text" / f"{row[0]}.txt"
                if text.is_file():
                    return text.read_text(encoding="utf-8", errors="replace"), f"the library's text of {record['location']}"
        return "", ""

    def _record(self, t: Target) -> State:
        from jason.community.records import CITATION
        from jason.community.symbols import AssociationRecord

        try:
            kind = AssociationRecord(t.key)
        except ValueError:
            return _miss(Reason.UNKNOWN_RECORD, "the kinds: " + ", ".join(k.value for k in AssociationRecord),
                         f"record:{t.key}")
        statute = CITATION[kind]
        law = self(statute).state
        held: list[dict[str, Any]] = []
        c = self.community
        for row in _rows_of(c, "sync_rules"):
            if kind in getattr(row, "records", ()):
                held.append({"where": "Drive sync rule", "name": getattr(getattr(row, "id", None), "value", ""),
                             "folder": getattr(row, "drive_folder", "")})
        for row in _rows_of(c, "library_folders"):
            if kind in getattr(row, "records", ()):
                held.append({"where": "library folder", "name": getattr(row, "path", "")})
        for row in _rows_of(c, "known_files"):
            if kind in getattr(row, "records", ()):
                held.append({"where": "known file", "name": getattr(row, "name", "")})
        version = {"statute": statute, "statuteFound": law.found, "note": "" if held else
                   "the specification pins no folder or file to this kind"}
        return State(Kind.RECORD, True, citation=f"{kind.value.replace('_', ' ')} ({statute})", title=kind.value,
                     text=law.text, version={**version, **{k: v for k, v in law.version.items() if k == "source"}},
                     nodes=held)

    # --- The walk ----------------------------------------------------------------------------------------------------

    def outgoing(self, t: Target) -> list[tuple[Target, str, str, int]]:
        """What the target's words name, from the references the governing documents make: each cited target, the
        verb, the first sentence, and how many times."""
        state = self.state(t)
        if not state.outline:
            return []
        grouped: dict[str, list[Any]] = {}
        for row in self.rows():
            if row.get("source") != state.outline:
                continue
            where = _where(row)
            if "" not in state.numbers and not any(where and _inside(where, n) for n in state.numbers):
                continue
            cited = of_reference(row.get("target", ""), row.get("kind", ""))
            if cited is None or cited.id == t.id:
                continue
            entry = grouped.setdefault(cited.id, [cited, row.get("relation", "cites"), row.get("quote", ""), 0])
            entry[3] += 1
            if entry[1] == "cites" and row.get("relation", "cites") != "cites":
                entry[1] = row["relation"]
        return [tuple(v) for v in grouped.values()]

    def walk(self, t: Target, *, hops: int | None = 1, only: frozenset[Unit] | None = None,
             same: bool = False) -> Node:
        seen: set[str] = set()
        count = [0]
        root_key = t.key

        def node(target: Target, relation: str = "", quote: str = "", n: int = 1) -> Node:
            st = self.state(target)
            return Node(target.id, st.citation or target.id, target.unit.value, st.found,
                        st.reason.value if st.reason else "", relation, quote, n)

        def allowed(target: Target) -> bool:
            if same and not (target.unit in (Unit.SECTION, Unit.DOCUMENT) and target.key == root_key):
                return False
            return only is None or target.unit in only

        def expand(here: Node, target: Target, left: int | None) -> None:
            if here.id in seen:
                here.repeat = True
                return
            seen.add(here.id)
            children = [c for c in self.outgoing(target) if allowed(c[0])]
            if left is not None and left <= 0:
                here.stopped = bool(children)
                return
            for cited, relation, quote, n in children:
                child = node(cited, relation, quote, n)
                here.children.append(child)
                count[0] += 1
                if count[0] >= MAX_NODES:
                    child.stopped = True
                    continue
                expand(child, cited, None if left is None else left - 1)

        root = node(t)
        expand(root, t, hops)
        return root

    # --- What names a target -----------------------------------------------------------------------------------------

    def mentions(self) -> list[Mention]:
        """jason's own records that name a section or a statute, each read once."""
        if self._mentions is not None:
            return self._mentions
        names = self.names()
        c = self.community
        out: list[Mention] = []

        def add(holder: Holder, key: str, title: str, text: str, field: str = "", quote: str = "",
                reading: str = "") -> None:
            for t in targets_in(text, names):
                out.append(Mention(holder, key, title, t, field, quote, reading=reading,
                                   pid=pid_in(key, t.key, t.number) if t.unit is Unit.SECTION else ""))

        def guarded(what: str, read) -> None:
            try:
                read()
            except Exception as exc:  # one source that cannot be read must not hide the others
                self.unread.append(f"{what}: {exc}")

        def conflicts() -> None:
            for r in getattr(c, "conflicts", lambda: ())():
                # ``says`` paraphrases the provision: it travels as jason's reading, beside the recited words.
                add(Holder.CONFLICT, f"conflict:{r.key}", r.provision, r.provision, "provision", reading=r.says)
                add(Holder.CONFLICT, f"conflict:{r.key}", r.provision, r.authority, "authority")

        stored = self.register()

        def pid_in(record: str, document: str, number: str) -> str:
            """The permanent id the migration stored for this record's citation of ``number`` (the register)."""
            return next((r.get("pid", "") for r in stored.get(record) or ()
                         if r.get("document") == document and r.get("written") == number), "")

        def notice_clauses() -> None:
            for p in getattr(c, "notice_provisions", lambda: ())():
                for number in _numbers_in(p.section or ""):
                    out.append(Mention(Holder.NOTICE_CLAUSE, f"notice:{p.key}", p.citation,
                                       Target(Unit.SECTION, p.document, number), "section", reading=p.says,
                                       pid=pid_in(f"notice:{p.key}", p.document, number)))

        def requirements() -> None:
            from jason.community.notice_catalog import REQUIREMENTS

            for r in REQUIREMENTS:
                add(Holder.NOTICE_REQUIREMENT, f"requirement:{r.key}", r.title, r.statute, "statute")

        def duties() -> None:
            from jason.tasks.document_duties import stored

            folder = Path(self.data_dir) / "duties"
            for path in sorted(folder.glob("*.json")) if folder.is_dir() else ():
                for d in stored(self.data_dir, path.stem):
                    number = normalize_number(d.section or "")
                    if number and re.match(r"^(?:[A-Z]{1,2}-)?\d", number):
                        # A duty is read from the outline on disk: its number is the outline's.
                        out.append(Mention(Holder.DUTY, f"duty:{d.id}", d.kind.value,
                                           Target(Unit.SECTION, d.source or path.stem, number), "section", d.quote,
                                           pid=getattr(d, "pid", ""), numbered="outline"))

        def assignments() -> None:
            from jason.community.schedule import assignments as rows

            for a in rows(c):
                for cover in a.covers:
                    add(Holder.ASSIGNMENT, f"assignment:{a.key}", a.title, cover, "covers")

        def responses() -> None:
            from jason.community.responses import rules_for

            for r in rules_for(c)[1].values():
                add(Holder.RESPONSE_RULE, f"response:{r.kind.value}", r.kind.value, r.authority, "authority")

        def templates() -> None:
            for t in getattr(c, "document_templates", lambda: ())():
                add(Holder.TEMPLATE, f"template:{getattr(t.kind, 'value', t.kind)}", t.title, t.authority, "authority")

        def procedures() -> None:
            from jason.community.procedures import procedures as rows

            for p in rows(c):
                text = " ".join([p.title, p.purpose, *(s.do + " " + s.check for s in p.steps)])
                add(Holder.PROCEDURE, f"procedure:{p.key}", p.title, text, "steps")

        def lessons() -> None:
            from jason.community.lessons import lessons as rows

            for lesson in rows(c):
                add(Holder.LESSON, f"lesson:{lesson.key}", lesson.key,
                    " ".join([lesson.what, lesson.why, lesson.change]), "text")

        def record_kinds() -> None:
            from jason.community.records import CITATION

            for kind, statute in CITATION.items():
                add(Holder.RECORD_KIND, f"record:{kind.value}", kind.value, statute, "citation")

        def embedded() -> None:
            for name, text in self._token_sources():
                for m in TOKEN.finditer(text):
                    out.append(Mention(Holder.EMBEDDED, name, f"{{{m.group('verb')}:...}} in {name}",
                                       Target(Unit.SECTION, m.group("key"), normalize_number(m.group("section"))),
                                       m.group("verb")))
            for path, raw in self._renderings():
                for r in raw.get("references") or ():
                    as_of = date.fromisoformat(r["as_of"]) if r.get("as_of") else None
                    out.append(Mention(Holder.EMBEDDED, f"{path} ({raw.get('rendered', '')})",
                                       f"{r.get('verb', '')} rendered from {raw.get('source', '')}",
                                       Target(Unit.SECTION, r.get("key", ""), normalize_number(r.get("section", ""))),
                                       "rendering", digest=r.get("digest", ""), as_of=as_of))

        for what, read in (("conflicts", conflicts), ("notice provisions", notice_clauses),
                           ("notice requirements", requirements), ("duties", duties), ("assignments", assignments),
                           ("response rules", responses), ("templates", templates), ("procedures", procedures),
                           ("lessons", lessons), ("record kinds", record_kinds), ("embedded references", embedded)):
            guarded(what, read)
        self._mentions = out
        return out

    def _token_sources(self) -> Iterable[tuple[str, str]]:
        """jason's own Markdown and templates that may carry ``{QUOTE:}``/``{CITE:}`` tokens."""
        folders: list[tuple[Path, Path]] = []
        drafts = Path(self.data_dir) / "drafts"
        if drafts.is_dir():
            folders.append((drafts, Path(self.data_dir)))
        repo = self.repo
        if repo is None:
            from jason.tasks.section_refs import repo_root

            repo = repo_root()
        if repo is not None:
            folders.append((repo / "src" / "jason" / "templates", repo))
            try:
                from jason.community.profile import profile_root

                root = profile_root()
                if root is not None:
                    folders.append((root / "packet_templates", repo))
            except Exception:
                pass
        for folder, base in folders:
            for path in sorted(folder.rglob("*")) if folder.is_dir() else ():
                if path.is_file() and path.suffix in (".md", ".html") and ".rendered" not in path.name:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    if "{QUOTE:" in text or "{CITE:" in text:
                        try:
                            name = path.relative_to(base).as_posix()
                        except ValueError:
                            name = str(path)
                        yield name, text

    def _renderings(self) -> Iterable[tuple[str, dict[str, Any]]]:
        """The records ``jason section-refs --render`` writes beside each rendering (``OUT.refs.json``)."""
        for path in sorted(Path(self.data_dir).rglob("*.refs.json")):
            try:
                yield path.relative_to(self.data_dir).as_posix(), json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.unread.append(f"{path}: not a rendering record")

    def treat(self, cited: Target, *, quote: str = "", digest: str = "", as_of: date | None = None,
              holder: Holder | None = None, pid: str = "", numbered: str = "") -> tuple[Treatment, str]:
        """How the cited words stand now against the citing record. A record read from a document's outline (a duty
        read from the working copy) is compared with that outline too: a section the outline numbers and the text as
        amended does not is renumbered, not gone, and a quote the outline has is the copy's words, not stale ones.

        The permanent id finds a section again (``jason.tasks.permanent_ids``): the id the record stored (``pid``), or
        the one its number has under the reading it was read from (``numbered``), the text as amended, or another
        reading. A section found so is ``RELOCATED`` (renumbered, printed twice, or run inline), not missing."""
        if cited.unit is not Unit.SECTION or cited.end or cited.siblings:
            return Treatment.NOT_CHECKED, ""
        if not re.match(r"^(?:[A-Z]{1,2}-)?\d", cited.number):
            return Treatment.NOT_CHECKED, "named by its title, not a number"
        if holder is Holder.EMBEDDED and not digest:
            now = self.state(replace(cited, as_of=None))
            if not now.found:
                return (Treatment.REMOVED if now.reason is Reason.REMOVED else Treatment.MISSING), now.detail
            return Treatment.FILLED, "filled from the words in force each time it is rendered"
        st = self.state(replace(cited, as_of=as_of))
        copy = self._copy_words(cited)
        if (pid or not st.found) and st.reason is not Reason.REMOVED:
            moved = self._relocated(cited, st, copy, quote=quote, pid=pid, numbered=numbered, as_of=as_of)
            if moved is not None:
                return moved
        if not st.found:
            if st.reason is Reason.REMOVED:
                return Treatment.REMOVED, st.detail
            if copy is not None:
                return Treatment.RENUMBERED, (f"numbered so in the outline it was read from (data/outlines/"
                                              f"{cited.key}.json), not in the document as amended")
            return Treatment.MISSING, st.detail
        if st.kind is not Kind.SECTION:
            return Treatment.NOT_CHECKED, ""
        if digest:
            if st.version.get("digest") == digest:
                return Treatment.CURRENT, "the words rendered are the words now"
            return Treatment.WORDS_CHANGED, "the rendering quoted other words: render it again"
        if quote:
            wanted = _letters(quote)
            if wanted and wanted in _letters(st.text):
                return Treatment.CURRENT, ""
            if wanted and copy and wanted in _letters(copy):
                if st.version.get("amended"):
                    return Treatment.AMENDED, ("the quote is the outline's words; the section reads "
                                               f"{st.version.get('provenance')}")
                return Treatment.CURRENT, ("the quote is the working copy's words; the text as amended reads them "
                                           "differently (an OCR slip, or drift: jason living KEY --working)"
                                           ).replace("KEY", cited.key)
            return Treatment.WORDS_CHANGED, "the words the record quotes are not in the section now"
        if st.version.get("amended"):
            return Treatment.AMENDED, f"{st.version.get('provenance')}; the record stores no version"
        return Treatment.UNAMENDED, ""

    def _relocated(self, cited: Target, st: State, copy: str | None, *, quote: str = "", pid: str = "",
                   numbered: str = "", as_of: date | None = None) -> tuple[Treatment, str] | None:
        """The cited section found by its permanent id, or None to judge it by its number as usual (the number is
        the section's own, or no id answers to it, or more than one does and nothing tells them apart)."""
        try:
            loc = self.locator.locate(cited.key, cited.number, quote=quote, day=as_of, pid=pid, reading=numbered)
        except Exception as exc:  # a table that cannot be built leaves the record to its number
            self.unread.append(f"permanent ids of {cited.key}: {exc}")
            return None
        if loc is None:
            return None
        if st.found and loc.number == cited.number and not loc.within:
            return None
        if loc.removed:
            return Treatment.REMOVED, loc.note()
        if quote:
            if loc.quoted:
                return Treatment.RELOCATED, loc.note()
            if copy and _letters(quote) in _letters(copy):
                return Treatment.RELOCATED, (loc.note() + "; the quote is the outline's words, which the text as "
                                             "amended reads differently (an OCR slip, or drift)")
            return Treatment.WORDS_CHANGED, loc.note() + "; the words the record quotes are not in it now"
        if loc.ambiguous:
            return None
        return Treatment.RELOCATED, loc.note()

    def _copy_words(self, cited: Target) -> str | None:
        """A living document's section as its outline on disk (the working copy) reads it; None when the outline has
        no such section, or the document is not kept as amended (its outline is the text already)."""
        if not self.resolver.living(cited.key):
            return None
        outline = self.resolver.outline(cited.key)
        if outline is None:
            return None
        from jason.community.living import CurrentDocument, provisions_of

        key = ("copy", cited.key)
        doc = self._copies.get(key)
        if doc is None:
            doc = self._copies[key] = CurrentDocument(cited.key, outline.title, "", provisions_of(outline))
        if doc.provision(cited.number) is None:
            return None
        return doc.text_of(cited.number)

    def cited_by(self, t: Target) -> list[Citing]:
        want = replace(t, as_of=None, end="", siblings=())
        out: list[Citing] = []
        for row in self.rows():
            cited = of_reference(row.get("target", ""), row.get("kind", ""))
            if cited is None:
                continue
            scope = scope_of(cited, want)
            if scope is None:
                continue
            source, where = row.get("source", ""), _where(row)
            if want.unit is Unit.SECTION and source == want.key and where and _inside(where, want.number):
                continue                       # the section's own words naming itself or its parts
            treatment, note = self.treat(cited)
            out.append(Citing(Holder.DOCUMENT, f"{source}#{where}" if where else source, self.title(source),
                              cited.id, scope, "text", row.get("relation", ""), row.get("quote", ""), treatment, note))
        for m in self.mentions():
            scope = scope_of(m.target, want)
            if scope is None:
                continue
            out.append(self._citing(m, scope))
        return out

    def _citing(self, m: Mention, scope: Scope) -> Citing:
        """A mention as a reverse edge. A record that paraphrases the provision carries the paraphrase as jason's
        reading, with the section's words now beside it, so a person compares the two."""
        treatment, note = self.treat(m.target, quote=m.quote, digest=m.digest, as_of=m.as_of, holder=m.holder,
                                     pid=m.pid, numbered=m.numbered)
        words = ""
        if m.reading:
            st = self.state(replace(m.target, as_of=None))
            words = st.text if st.found and st.kind in (Kind.SECTION, Kind.STATUTE) else ""
        return Citing(m.holder, m.key, m.title, m.target.id, scope, m.field, "", m.quote, treatment, note,
                      m.reading, words)

    def stale(self) -> list[Citing]:
        """Every citing record whose cited words are gone or changed: a section missing or removed, a quote no longer
        in the words, a rendering whose words have changed. The records found again by their permanent id (renumbered,
        printed twice, run inline) are not stale; ``relocated`` lists them."""
        return [c for c in self.checked() if c.treatment in STALE]

    def relocated(self) -> list[Citing]:
        """The citing records whose section the permanent id found under another number."""
        return [c for c in self.checked() if c.treatment is Treatment.RELOCATED]

    def checked(self) -> list[Citing]:
        """Every citing record of a section, with how its cited words stand (read once)."""
        if self._checked is not None:
            return self._checked
        out = []
        for row in self.rows():
            cited = of_reference(row.get("target", ""), row.get("kind", ""))
            if cited is None or cited.unit is not Unit.SECTION:
                continue
            treatment, note = self.treat(cited)
            where = _where(row)
            out.append(Citing(Holder.DOCUMENT, f"{row['source']}#{where}" if where else row["source"],
                              self.title(row["source"]), cited.id, Scope.EXACT, "text", row.get("relation", ""),
                              row.get("quote", ""), treatment, note))
        for m in self.mentions():
            if m.target.unit is Unit.SECTION:
                out.append(self._citing(m, Scope.EXACT))
        if self._locator is not None:
            self.unread += [e for e in self._locator.errors if e not in self.unread]
        self._checked = out
        return out

    def most_cited(self, limit: int = 30) -> list[dict[str, Any]]:
        """The sections and statutes named most, across the governing documents and jason's records: where verifying
        and transcribing the words matters most."""
        counts: Counter = Counter()
        by: dict[str, Counter] = defaultdict(Counter)
        for row in self.rows():
            cited = of_reference(row.get("target", ""), row.get("kind", ""))
            if cited is not None and cited.unit in (Unit.SECTION, Unit.STATUTE):
                counts[cited.id] += 1
                by[cited.id][Holder.DOCUMENT.value] += 1
        for m in self.mentions():
            if m.target.unit in (Unit.SECTION, Unit.STATUTE):
                counts[m.target.id] += 1
                by[m.target.id][m.holder.value] += 1
        out = []
        for target_id, n in counts.most_common(limit):
            cited = of_reference(target_id)
            st = self.state(cited) if cited is not None else None
            out.append({"target": target_id, "citation": st.citation if st and st.citation else target_id,
                        "found": bool(st and st.found), "total": n, "by": dict(by[target_id])})
        return out

    def survey(self) -> dict[str, Any]:
        """Every reference the governing documents make, resolved: how many are found, and the reasons for the rest."""
        found = missed = 0
        by_unit: dict[str, Counter] = defaultdict(Counter)
        reasons: Counter = Counter()
        examples: dict[str, list[str]] = defaultdict(list)
        skipped = 0
        for row in self.rows():
            cited = of_reference(row.get("target", ""), row.get("kind", ""))
            if cited is None:
                skipped += 1
                continue
            st = self.state(cited)
            if st.found:
                found += 1
                by_unit[cited.unit.value]["found"] += 1
                continue
            missed += 1
            reason = st.reason.value if st.reason else "unknown"
            by_unit[cited.unit.value]["missed"] += 1
            reasons[reason] += 1
            if len(examples[reason]) < 5 and cited.id not in examples[reason]:
                examples[reason].append(cited.id)
        return {"references": len(self.rows()), "found": found, "missed": missed, "unfollowable": skipped,
                "byUnit": {k: dict(v) for k, v in by_unit.items()}, "reasons": dict(reasons.most_common()),
                "examples": dict(examples)}


def _series(numbers: tuple[str, ...]) -> str:
    """"6.2(a), (b), and (c)" when they share a parent; "6.2 and 6.3" otherwise."""
    if not numbers:
        return ""
    parents = {n[: n.rfind("(")] for n in numbers if "(" in n}
    shown = list(numbers)
    if len(parents) == 1 and all("(" in n for n in numbers):
        shown = [numbers[0]] + [n[n.rfind("("):] for n in numbers[1:]]
    if len(shown) == 2:
        return f"{shown[0]} and {shown[1]}"
    return ", ".join(shown[:-1]) + f", and {shown[-1]}"


_KINDS = {"statute": Unit.STATUTE, "statutes": Unit.STATUTE, "law": Unit.STATUTE, "section": Unit.SECTION,
          "sections": Unit.SECTION, "document": Unit.DOCUMENT, "documents": Unit.DOCUMENT,
          "resolution": Unit.RESOLUTION, "resolutions": Unit.RESOLUTION, "instrument": Unit.INSTRUMENT,
          "instruments": Unit.INSTRUMENT, "recorded instrument": Unit.INSTRUMENT, "minutes": Unit.MINUTES,
          "record": Unit.RECORD}


def units(kinds: Iterable[Any]) -> frozenset[Unit]:
    """``only``'s kinds as units: a ``Unit``, a ``TargetKind``, or its word (statute, section, resolution, ...)."""
    out = set()
    for k in kinds:
        word = str(getattr(k, "value", k)).strip().lower()
        if word in _KINDS:
            out.add(_KINDS[word])
        else:
            raise ValueError(f"only: {word!r}; the kinds are statute, section, document, resolution, instrument")
    return frozenset(out)


class Citation:
    """A document or record, closed over by each unit call. Never raises on a miss: ``found`` and ``reason`` say."""

    def __init__(self, shelf: Shelf, target: Target | None, *, miss: Miss | None = None, expression: str = "",
                 depth: int | None = 1, only: frozenset[Unit] | None = None, same: bool = False,
                 scope: scoping.Scoped | None = None):
        self.shelf = shelf
        self.target = target
        self.miss = miss
        self.expression = expression
        self.depth = depth
        self.only_units = only
        self.same_book = same
        self.scope = scope                 # how the document was chosen (``jason.community.scoping``), when it was read

    def _copy(self, target: Target | None = None, miss: Miss | None = None, **settings: Any) -> Citation:
        base = {"depth": self.depth, "only": self.only_units, "same": self.same_book, "scope": self.scope}
        base.update(settings)
        if miss is not None:
            return Citation(self.shelf, None, miss=miss, expression=self.expression, **base)
        return Citation(self.shelf, target if target is not None else self.target, miss=self.miss,
                        expression=self.expression, **base)

    def _narrow(self, **changes: Any) -> Citation:
        if self.target is None:
            return self
        t = self.target
        if t.unit not in (Unit.SECTION, Unit.DOCUMENT, Unit.STATUTE):
            return self._copy(miss=Miss(Reason.UNPARSED, f"a {t.unit.value} has no sections", self.expression))
        unit = Unit.STATUTE if t.unit is Unit.STATUTE else Unit.SECTION
        return self._copy(replace(t, unit=unit, **changes))

    # --- Narrowing ---------------------------------------------------------------------------------------------------

    def section(self, number: Any) -> Citation:
        """A section by its whole number ("6.2", "6.2(a)", "R-3(e)"); it replaces any number named before."""
        number = re.sub(r"^(?:[Ss]ections?|§§?|[Ss]ec\.)\s*", "", str(number).strip())
        return self._narrow(number=normalize_number(number), end="", siblings=(), article=False)

    def article(self, number: Any) -> Citation:
        return self._narrow(number=normalize_number(str(number)), end="", siblings=(), article=True)

    def __call__(self, *labels: Any) -> Citation:
        """One label stacks a subdivision: ``section("6.2")("a")`` is 6.2(a). Several name siblings."""
        if not labels:
            raise TypeError("a label is required")
        if self.target is None:
            return self
        if not self.target.number:
            return self._copy(miss=Miss(Reason.UNPARSED, "name a section before its subdivision", self.expression))
        clean = [str(label).strip().strip("()") for label in labels]
        if len(clean) == 1:
            return self._narrow(number=f"{self.target.number}({clean[0]})", siblings=(), end="")
        return self._narrow(siblings=tuple(f"{self.target.number}({x})" for x in clean), end="")

    def through(self, end: Any) -> Citation:
        if self.target is None or not self.target.number:
            return self
        return self._narrow(end=normalize_number(str(end)), siblings=())

    def and_(self, *numbers: Any) -> Citation:
        """A series: this section and each further number."""
        if self.target is None or not self.target.number:
            return self
        return self._narrow(siblings=(self.target.number, *(normalize_number(str(n)) for n in numbers)), end="")

    def as_of(self, day: Any) -> Citation:
        """The words in force on ``day`` (a date or YYYY-MM-DD); None for the words now."""
        if self.target is None:
            return self
        if day in (None, ""):
            return self._copy(replace(self.target, as_of=None))
        try:
            when = day if isinstance(day, date) else date.fromisoformat(str(day))
        except ValueError:
            return self._copy(miss=Miss(Reason.UNPARSED, f"{day!r} is not a date (YYYY-MM-DD)", self.expression))
        return self._copy(replace(self.target, as_of=when))

    def hops(self, depth: int | None) -> Citation:
        """How many hops the walk follows. None follows until a target repeats."""
        return self._copy(depth=depth)

    def same(self) -> Citation:
        """Follow references only inside this document."""
        return self._copy(same=True)

    def only(self, *kinds: Any) -> Citation:
        """Follow references only to these kinds (statute, section, document, resolution, instrument)."""
        return self._copy(only=units(kinds))

    # --- Reading -----------------------------------------------------------------------------------------------------

    @property
    def state(self) -> State:
        if self.target is None:
            m = self.miss or Miss(Reason.EMPTY)
            return _miss(m.reason, m.detail)
        st = self.shelf.state(self.target)
        if not st.found and st.reason in (Reason.NOT_IN_DOCUMENT, Reason.PARENT_ONLY):
            return self.shelf.titled(self.target) or self.shelf.former(self.target) or st
        return st

    @property
    def kind(self) -> Kind:
        return self.state.kind

    @property
    def found(self) -> bool:
        return self.state.found

    @property
    def reason(self) -> Reason | None:
        return self.state.reason

    @property
    def id(self) -> str:
        return self.target.id if self.target is not None else ""

    def __str__(self) -> str:
        return self.state.citation or self.id or self.expression

    def reference(self) -> str:
        return str(self)

    def __repr__(self) -> str:
        return f"Citation({str(self)!r}, found={self.found})"

    @property
    def text(self) -> str:
        """The stored words: a section's (with its subsections') as amended or as of a day, a statute's, a record's.
        Empty for a miss and for an outline (a document, an article, a span, siblings)."""
        return self.state.text

    @property
    def version(self) -> dict[str, Any]:
        """Where the words came from and who set them."""
        return dict(self.state.version)

    @property
    def outline(self) -> list[dict[str, Any]]:
        return list(self.state.nodes)

    @property
    def history(self) -> list[dict[str, Any]]:
        """The instruments that changed this section (and its subsections), in order, with their dates; then any
        instrument not yet in force that would change it, flagged as not applied. Editorial corrections are listed as
        corrections. Empty for a document not kept as amended."""
        t = self.target
        if t is None or t.unit is not Unit.SECTION or not self.shelf.resolver.living(t.key):
            return []
        try:
            v = self.shelf.resolver.versions(t.key)
        except SectionRefError:
            return []
        numbers = t.siblings or (t.number,)
        out: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for p in v.now.provisions:
            if not p.number or not any(_inside(p.number, n) for n in numbers):
                continue
            for step in p.history:
                if step == "base":
                    continue
                key, _, verb = step.partition(": ")
                if (p.number, step) in seen:
                    continue
                seen.add((p.number, step))
                info = v.instruments.get(key) or {}
                if info:
                    out.append({"section": p.number, "instrument": key, "verb": verb, "describe": info.get("describe"),
                                "dated": info.get("dated"), "standing": info.get("standing"), "applied": True})
                else:
                    out.append({"section": p.number, "correction": step, "applied": True})
        for op in v.pending:
            n = normalize_number(op.get("section", ""))
            if any(_inside(n, x) or _inside(x, n) for x in numbers):
                info = v.instruments.get(op["instrument"]) or {}
                out.append({"section": n, "instrument": op["instrument"], "describe": info.get("describe"),
                            "dated": info.get("dated"), "standing": info.get("standing"), "applied": False,
                            "note": "not in force: its words are not in the text"})
        return out

    @property
    def subdivisions(self) -> list[str]:
        """The parts directly under this section (a document's subsections, a statute's labels)."""
        t = self.target
        if t is None or not self.found:
            return []
        if t.unit is Unit.STATUTE:
            from jason.community.cite import _style, paragraphs

            parts = paragraphs(self.text)[1 if t.labels else 0:]           # a subdivision's first paragraph is itself
            above = _style(t.labels[-1], len(t.labels) > 1) if t.labels else ""
            out: list[str] = []
            style = ""
            for p in parts:
                m = re.match(r"^\((\w{1,4})\)", p)
                if not m:
                    continue
                here = _style(m.group(1), above in ("digit", "upper"))
                style = style or here
                if here == style and m.group(1) not in out:
                    out.append(m.group(1))
            return [f"({x})" for x in out]
        try:
            doc, _ = self.shelf.resolver.document(t.key, t.as_of)
        except SectionRefError:
            return []
        number = t.number
        if not number:
            return [p.number for p in doc.provisions if p.number and p.depth == 1]
        return [p.number for p in doc.provisions if p.number and next(iter(ancestors(p.number)), "") == number]

    @property
    def terms(self) -> list[dict[str, Any]]:
        """The defined terms the recited words use, each with its definition's words and address."""
        st = self.state
        if not st.found or st.kind is not Kind.SECTION:
            return []
        return self.shelf.defined_terms(self.target, st.text)

    @property
    def address(self) -> str:
        return self.shelf.address(self.target)

    @property
    def pid(self) -> str:
        return self.shelf.pid(self.target)

    @property
    def sentences(self) -> list[str]:
        return sentences(self.text)

    def words(self) -> list[str]:
        return self.text.split()

    def containing(self, phrase: str) -> str:
        """The stored sentence that contains ``phrase``; empty on a miss."""
        needle = str(phrase or "").casefold()
        if not needle:
            return ""
        return next((s for s in self.sentences if needle in s.casefold()), "")

    @property
    def refs(self) -> Node:
        """This target as the root of the reference walk (``hops``, ``same``, ``only`` scope it)."""
        if self.target is None:
            return Node(self.expression, str(self), Kind.MISS.value, False, self.state.reason.value)
        return self.shelf.walk(self.target, hops=self.depth, only=self.only_units, same=self.same_book)

    @property
    def cited_by(self) -> list[Citing]:
        if self.target is None:
            return []
        return self.shelf.cited_by(self.target)

    @property
    def tree(self) -> dict[str, Any]:
        return self.refs.as_dict()

    @property
    def chart(self) -> str:
        return mermaid(self.refs)

    def diagram(self) -> str:
        return self.chart

    @property
    def md(self) -> str:
        return markdown(self)

    @property
    def in_force(self) -> str:
        """The version the words are: who set them and since when, or the edition of the law."""
        v = self.state.version
        if v.get("provenance"):
            dated = f", in force from {v['dated']}" if v.get("amended") and v.get("dated") else ""
            asked = f"; the words in force on {v['asOf']}" if v.get("asOf") else ""
            return f"{v['provenance']}{dated}{asked}"
        if v.get("session"):
            return f"the {v['session']} publication of the code ({v.get('source', '')})"
        return v.get("source", "")

    def as_dict(self, *, text: bool = True, refs: bool = False, cited_by: bool = False) -> dict[str, Any]:
        """The recitation first (the citation, the words whole, the version in force), then everything else. A
        paraphrase never stands in the words: a record's own summary is labeled as jason's reading."""
        st = self.state
        out: dict[str, Any] = {"kind": st.kind.value, "found": st.found, "citation": str(self)}
        if text and st.text:
            out["text"] = st.text
        elif st.text:
            out["words"] = len(st.text.split())
        if st.text and self.in_force:
            out["inForce"] = self.in_force
        if st.found and st.kind in (Kind.SECTION, Kind.RECORD, Kind.OUTLINE, Kind.ROW):
            out["caveat"] = _caveat(self.target)
        address = self.shelf.address(self.target)
        if address:
            out["address"] = address
        pid = self.shelf.pid(self.target) if st.found and st.kind is Kind.SECTION else ""
        if pid:
            out["pid"] = pid
        terms = self.terms
        if terms:
            out["terms"] = terms          # the definitions' own words, by address: recited, not read
        out["expression"], out["target"] = self.expression, self.id
        if self.scope is not None:
            out["scope"] = self.scope.as_dict()           # which document, and why: the basis, or the candidates
        if st.reason is not None:
            out["reason"] = st.reason.value
        if st.detail:
            out["detail"] = st.detail
        if st.title:
            out["title"] = st.title
        if st.version:
            out["version"] = st.version
        if st.nodes:
            out["outline"] = st.nodes
        if st.links:
            out["links"] = st.links
        if st.extra:
            out.update(st.extra)
        history = self.history
        if history:
            out["history"] = history
        if refs:
            root = self.refs
            out["refs"] = {"hops": self.depth, "tree": root.as_dict(), "nodes": root.nodes(), "edges": root.edges(),
                           "chart": mermaid(root)}
        if cited_by:
            rows = self.cited_by
            out["citedBy"] = [c.as_dict() for c in rows]
            out["citedByCount"] = dict(Counter(c.holder.value for c in rows))
            if self.shelf.unread:
                out["citedByUnread"] = list(self.shelf.unread)
        return out


def markdown(c: Citation) -> str:
    """A page for one citation: the words recited whole with their citation and the version in force, then what it
    cites and what cites it. A record's paraphrase appears only beside the words, labeled as jason's reading."""
    st = c.state
    lines = [f"# {c}", ""]
    if not st.found:
        lines += [f"Not found: {st.reason.value if st.reason else 'unknown'}" + (f". {st.detail}" if st.detail else ""),
                  ""]
    if st.text:
        lines += [f"> {line}" if line.strip() else ">" for line in st.text.strip().splitlines()] + [">"]
        lines += [f"> _{c}" + (f", {c.in_force}" if c.in_force else "") + "._", ""]
        if st.version.get("note"):
            lines += [f"Note: {st.version['note']}.", ""]
    address = c.address
    if address:
        lines += [f"Address: `{address}`" + (f"; permanent id `{c.pid}`" if st.found and c.pid else "") + ".", ""]
    for title, rows in st.extra.get("sections") or ():
        lines += [f"## {title}", ""] + [r if r.startswith(">") or not r else f"- {r}" for r in rows] + [""]
    terms = c.terms
    if terms:
        lines += ["## Defined terms", "", "The document defines words this section uses; its definition governs them "
                  "here (Civil Code 1644). Each is recited from its own section.", ""]
        for row in terms:
            lines += [f"**{row['term']}** ({row['citation']}, `{row['address']}`):", ""]
            if row["definition"]:
                lines += [f"> {line}" if line.strip() else ">" for line in row["definition"].strip().splitlines()]
                lines.append("")
    if st.nodes:
        lines += ["## Outline", ""]
        for n in st.nodes[:200]:
            label = n.get("number") or n.get("first", "")
            caption = n.get("caption") or n.get("title") or n.get("kind") or n.get("where") or ""
            lines.append(f"- {label} {caption}".rstrip())
        lines.append("")
    history = c.history
    if history:
        lines += ["## History", ""] + [f"- {h['section']}: {h.get('describe') or h.get('correction')}"
                                       + ("" if h.get("applied") else " (not in force; not applied)")
                                       for h in history] + [""]
    root = c.refs
    if root.children:
        lines += [f"## What it cites ({c.depth if c.depth is not None else 'all'} hops)", ""] + tree_lines(root) + [""]
        lines += ["```mermaid", mermaid(root), "```", ""]
    rows = c.cited_by
    if rows:
        lines += ["## What cites it", "", "| Who | Record | Names | Scope | Treatment |", "|---|---|---|---|---|"]
        for r in rows[:300]:
            lines.append(f"| {r.holder.value} | {r.key} | {r.target} | {r.scope.value} | {r.treatment.value} |")
        lines.append("")
        read = [r for r in rows if r.reading]
        if read:
            lines += ["## Readings beside the words", "",
                      "Each record's summary is jason's reading, not the provision; the words follow it.", ""]
            for r in read:
                lines += [f"**{r.key}** ({r.holder.value}), naming {r.target}:", "",
                          f"- jason's reading: {r.reading}", ""]
                if r.words:
                    lines += [f"> {line}" if line.strip() else ">" for line in r.words.strip().splitlines()] + [""]
    if st.found and st.kind in (Kind.SECTION, Kind.RECORD, Kind.OUTLINE):
        lines += [f"_{_caveat(c.target)}_", ""]
    return "\n".join(lines)


def _caveat(t: Target | None) -> str:
    """The caveat a found citation carries: a notice's (jason's record of it), else the documents' (CAVEAT)."""
    if t is not None and t.unit is Unit.NOTICE:
        from jason.tasks.notice_record import CAVEAT as NOTICE_CAVEAT

        return NOTICE_CAVEAT
    if t is not None and t.unit is Unit.ROW:
        return rule_rows.LABEL
    return CAVEAT


def cite(community: Any = None, data_dir: Path | None = None, *, log=None, private: bool = False) -> Shelf:
    """The association's documents and records, opened for citing. ``private`` opens the restricted books (CIV 5215)."""
    return Shelf(community, data_dir, log=log, private=private)


def resolve(expression: str, *, as_of: str | date | None = None, text: bool = True, refs: bool = False,
            hops: int | None = 1, cited_by: bool = False, community: Any = None, data_dir: Path | None = None,
            shelf: Shelf | None = None, private: bool = False, citing: str | None = None,
            citing_day: str | date | None = None) -> dict[str, Any]:
    """What ``expression`` names, as lawlibrary's handoff answers ``cite``: ``{kind: section|outline|record|statute|
    history|miss, found, reason, citation, text, address, pid, ...}``. A span or a whole article is an outline, never
    concatenated words; a miss is an answer with its reason, never an exception. ``expression`` may be an address
    (``jason://decl/6.2(a)``) or one of jason's own rule rows (``owner_responses.RULES: delivery``); a restricted book
    is read only with ``private``. ``citing`` is the document the expression is written in (a key), ``citing_day`` the
    day it was written: a citation with no document named is scoped from them (``scope`` in the answer says how, or
    names every document that fits)."""
    shelf = shelf or Shelf(community, data_dir, private=private)
    c = shelf(expression, citing=citing, day=citing_day)
    if as_of:
        c = c.as_of(as_of)
    c = c.hops(hops)
    try:
        return c.as_dict(text=text, refs=refs, cited_by=cited_by)
    except Exception as exc:  # a reader that fails is a miss for the agent, not a traceback
        return {"kind": Kind.MISS.value, "found": False, "reason": Reason.UNREADABLE.value, "detail": str(exc),
                "expression": expression}


__all__ = ["Citation", "MAX_NODES", "Mention", "Shelf", "State", "cite", "markdown", "resolve", "units"]
