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
from jason.community.outlines import DocumentOutline, normalize_number
from jason.community.references import ancestors
from jason.community.section_refs import TOKEN, SectionRefError, SectionText, citation_of
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


class Shelf:
    """The association's documents and records on disk, opened for citing. Also a ``Resolver``."""

    def __init__(self, community: Any = None, data_dir: Path | None = None, *, log=None, repo: Path | None = None):
        self.resolver = DiskResolver(data_dir, community, log=log)
        self.community = self.resolver.community
        self.data_dir = self.resolver.data_dir
        self.repo = repo
        self._names: dict[str, str] | None = None
        self._outlines: dict[str, DocumentOutline] | None = None
        self._rows: list[dict[str, Any]] | None = None
        self._mentions: list[Mention] | None = None
        self._states: dict[str, State] = {}
        self._copies: dict[tuple[str, str], Any] = {}
        self.unread: list[str] = []    # sources of mentions that could not be read

    # --- The Resolver protocol (jason.community.section_refs): the same reader the tokens use ----------------------

    def section(self, key: str, number: str, as_of: date | None = None) -> SectionText:
        return self.resolver.section(key, number, as_of)

    def citation(self, key: str, number: str) -> str:
        return self.resolver.citation(key, number)

    # --- Opening a citation ----------------------------------------------------------------------------------------

    def __call__(self, expression: str) -> Citation:
        parsed = parse(expression, self.names())
        if isinstance(parsed, Miss):
            return Citation(self, None, miss=parsed, expression=str(expression or ""))
        return Citation(self, parsed, expression=str(expression or ""))

    def doc(self, name: str) -> Citation:
        key = self.names().get(str(name or "").strip().lower(), "")
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

    # --- Resolving a target ------------------------------------------------------------------------------------------

    def state(self, t: Target) -> State:
        if t.id not in self._states:
            try:
                self._states[t.id] = self._resolve(t)
            except SectionRefError as exc:
                self._states[t.id] = _miss(_reason(exc), str(exc))
        return self._states[t.id]

    def _resolve(self, t: Target) -> State:
        if t.unit is Unit.SECTION:
            if t.end:
                return self._span(t)
            if t.siblings:
                return self._siblings(t)
            return self._section(t)
        if t.unit is Unit.DOCUMENT:
            return self._document(t)
        if t.unit is Unit.STATUTE:
            return self._statute(t)
        if t.unit is Unit.RESOLUTION:
            return self._resolution(t)
        if t.unit is Unit.INSTRUMENT:
            return self._instrument(t)
        if t.unit is Unit.MINUTES:
            return self._minutes(t)
        return self._record(t)

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
        version = {"document": st.document, "setBy": st.set_by, "setByTitle": st.set_by_title, "dated": _day(st.dated),
                   "amended": st.amended, "asOf": _day(st.as_of), "source": st.source, "note": st.note,
                   "provenance": st.provenance(), "digest": st.digest, "caption": st.caption,
                   "living": versions is not None}
        return State(Kind.SECTION, True, citation=st.citation, title=doc.title, text=st.words, version=version,
                     outline=t.key, numbers=(t.number,), links=self._links(t.key))

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
        from jason.tasks.export_authorities import authority_pages, authority_text

        cite = t.id
        pointer = {"lawlibrary": {"call": "cite", "expression": t.base if not t.end else t.id}}
        base_number = t.number.split("(", 1)[0]
        whole = re.match(r"\d+", base_number)
        if t.key == "CIV" and whole and 1350 <= int(whole.group(0)) <= 1378:
            return _miss(Reason.PRIOR_NUMBERING, "a Davis-Stirling number from before the 2014 renumbering: its successor "
                         f"is read with jason law-history, or lawlibrary succession.successors('CIV', '{base_number}')",
                         cite, pointer=pointer)
        if t.end:
            nodes = [{"first": p.start, "last": p.end, "title": p.title, "file": p.file, "session": p.session}
                     for p in authority_pages(self.data_dir) if p.code == t.key
                     and _key(p.start) <= _key(t.end) and _key(p.end) >= _key(t.number)]
            if not nodes:
                return _miss(Reason.STATUTE_NOT_ON_DISK, "no exported pages in that span", cite, pointer=pointer)
            return State(Kind.OUTLINE, True, citation=cite, nodes=nodes, extra={"pointer": pointer})
        if t.siblings:
            nodes = []
            for n in t.siblings:
                one = self.state(Target(Unit.STATUTE, t.key, n))
                nodes.append({"number": n, "found": one.found, "reason": one.reason.value if one.reason else ""})
            ok = all(n["found"] for n in nodes)
            return State(Kind.OUTLINE, ok, None if ok else Reason.LABEL_NOT_FOUND, "", cite, nodes=nodes)
        if t.as_of is not None:
            return _miss(Reason.EDITION_NOT_HELD, "jason holds one edition of the law (data/authorities); lawlibrary's "
                         "Citation(...).session(year) reads another", cite, pointer=pointer)
        got = authority_text(self.data_dir, t.base)
        if not got.get("found"):
            return _miss(Reason.STATUTE_NOT_ON_DISK, got.get("reason", ""), cite, pointer=pointer)
        words = got.get("text", "")
        version = {"source": got.get("page", ""), "session": got.get("session", ""), "heading": got.get("title", ""),
                   "official": True}
        if t.labels:
            part = label_text(words, t.labels)
            if not part:
                return _miss(Reason.LABEL_NOT_FOUND, f"{t.base} is on disk; jason could not find "
                             f"{''.join(f'({x})' for x in t.labels)} in its words", cite, pointer=pointer)
            words = part
            version["official"] = False
            version["note"] = ("the subdivision's words, split by jason from the exported section; the whole section "
                               "is the official text")
        return State(Kind.STATUTE, True, citation=cite, title=got.get("title", ""), text=words, version=version,
                     extra={"pointer": pointer})

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
                out.append(Mention(holder, key, title, t, field, quote, reading=reading))

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

        def notice_clauses() -> None:
            for p in getattr(c, "notice_provisions", lambda: ())():
                for number in _numbers_in(p.section or ""):
                    out.append(Mention(Holder.NOTICE_CLAUSE, f"notice:{p.key}", p.citation,
                                       Target(Unit.SECTION, p.document, number), "section", reading=p.says))

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
                        out.append(Mention(Holder.DUTY, f"duty:{d.id}", d.kind.value,
                                           Target(Unit.SECTION, d.source or path.stem, number), "section", d.quote))

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
              holder: Holder | None = None) -> tuple[Treatment, str]:
        """How the cited words stand now against the citing record. A record read from a document's outline (a duty
        read from the working copy) is compared with that outline too: a section the outline numbers and the text as
        amended does not is renumbered, not gone, and a quote the outline has is the copy's words, not stale ones."""
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
                    return Treatment.AMENDED, (f"the quote is the outline's words; {st.version.get('setByTitle')} "
                                               "set the section's words")
                return Treatment.CURRENT, ("the quote is the working copy's words; the text as amended reads them "
                                           "differently (an OCR slip, or drift: jason living KEY --working)"
                                           ).replace("KEY", cited.key)
            return Treatment.WORDS_CHANGED, "the words the record quotes are not in the section now"
        if st.version.get("amended"):
            return Treatment.AMENDED, f"set by {st.version.get('setByTitle')}; the record stores no version"
        return Treatment.UNAMENDED, ""

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
        treatment, note = self.treat(m.target, quote=m.quote, digest=m.digest, as_of=m.as_of, holder=m.holder)
        words = ""
        if m.reading:
            st = self.state(replace(m.target, as_of=None))
            words = st.text if st.found and st.kind in (Kind.SECTION, Kind.STATUTE) else ""
        return Citing(m.holder, m.key, m.title, m.target.id, scope, m.field, "", m.quote, treatment, note,
                      m.reading, words)

    def stale(self) -> list[Citing]:
        """Every citing record whose cited words are gone or changed: a section missing or removed, a quote no longer
        in the words, a rendering whose words have changed."""
        out = []
        for row in self.rows():
            cited = of_reference(row.get("target", ""), row.get("kind", ""))
            if cited is None or cited.unit is not Unit.SECTION:
                continue
            treatment, note = self.treat(cited)
            if treatment in STALE:
                where = _where(row)
                out.append(Citing(Holder.DOCUMENT, f"{row['source']}#{where}" if where else row["source"],
                                  self.title(row["source"]), cited.id, Scope.EXACT, "text", row.get("relation", ""),
                                  row.get("quote", ""), treatment, note))
        for m in self.mentions():
            treatment, _ = self.treat(m.target, quote=m.quote, digest=m.digest, as_of=m.as_of, holder=m.holder)
            if treatment in STALE:
                out.append(self._citing(m, Scope.EXACT))
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
                 depth: int | None = 1, only: frozenset[Unit] | None = None, same: bool = False):
        self.shelf = shelf
        self.target = target
        self.miss = miss
        self.expression = expression
        self.depth = depth
        self.only_units = only
        self.same_book = same

    def _copy(self, target: Target | None = None, miss: Miss | None = None, **settings: Any) -> Citation:
        base = {"depth": self.depth, "only": self.only_units, "same": self.same_book}
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
        return self.shelf.state(self.target)

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
        if st.found and st.kind in (Kind.SECTION, Kind.RECORD, Kind.OUTLINE):
            out["caveat"] = CAVEAT
        out["expression"], out["target"] = self.expression, self.id
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
        lines += [f"_{CAVEAT}_", ""]
    return "\n".join(lines)


def cite(community: Any = None, data_dir: Path | None = None, *, log=None) -> Shelf:
    """The association's documents and records, opened for citing."""
    return Shelf(community, data_dir, log=log)


def resolve(expression: str, *, as_of: str | date | None = None, text: bool = True, refs: bool = False,
            hops: int | None = 1, cited_by: bool = False, community: Any = None, data_dir: Path | None = None,
            shelf: Shelf | None = None) -> dict[str, Any]:
    """What ``expression`` names, as lawlibrary's handoff answers ``cite``: ``{kind: section|outline|record|statute|
    miss, found, reason, citation, text, ...}``. A span or a whole article is an outline, never concatenated words; a
    miss is an answer with its reason, never an exception."""
    shelf = shelf or Shelf(community, data_dir)
    c = shelf(expression)
    if as_of:
        c = c.as_of(as_of)
    c = c.hops(hops)
    try:
        return c.as_dict(text=text, refs=refs, cited_by=cited_by)
    except Exception as exc:  # a reader that fails is a miss for the agent, not a traceback
        return {"kind": Kind.MISS.value, "found": False, "reason": Reason.UNREADABLE.value, "detail": str(exc),
                "expression": expression}


__all__ = ["Citation", "MAX_NODES", "Mention", "Shelf", "State", "cite", "markdown", "resolve", "units"]
