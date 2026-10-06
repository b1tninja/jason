"""The scoping index of a ``Shelf``, built from the specification and the outlines on disk.

``jason.community.scoping`` is pure; this reads the shelf: the documents (their names, kinds, books, whether an outline
is on disk), the books that hold several documents, which sections each has on a given day (a document kept as amended
is read in the version in force then), and the parts of the owner's manual the profile's rows make.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.books import CANON, Book, Role
from jason.community.outlines import DocumentOutline, normalize_number
from jason.community import scoping
from jason.community.scoping import Citing, DocInfo, Index, Part, _norm_name

_SERIES_KINDS = ("resolution", "annexation", "amendment")


def _day(text: str) -> date | None:
    try:
        return date.fromisoformat((text or "")[:10]) if len(text or "") >= 10 else None
    except ValueError:
        return None


def _shape(shelf: Any, key: str, outline: DocumentOutline | None) -> list[tuple[str, int, str]]:
    """(number, depth, caption) of a document's sections: its outline's, or, for a document kept as amended with no
    outline on disk, its text as amended."""
    if outline is not None:
        # An article's caption is its title ("ARTICLE 4 MEETINGS"), with the list's own label ("4.") left off.
        return [(s.number, s.depth, s.title if re.match(r"\s*(?i:article)\b", s.title) else f"{s.label} {s.title}")
                for s in outline.sections]
    try:
        doc = shelf.resolver.document(key)[0]
    except Exception:
        return []
    return [(p.number, p.depth, p.caption or "") for p in doc.provisions if p.number]


def _info(shelf: Any, key: str, outline: DocumentOutline | None, citable: Any, living: Any = None) -> DocInfo:
    kind = (outline.kind if outline is not None else "") or getattr(getattr(citable or living, "kind", None), "value", "") or ""
    amends = (outline.amends if outline is not None else "") or getattr(citable, "amends", "") or ""
    pooled = kind not in _SERIES_KINDS and not amends and not key.startswith("resolution-")
    sections = _shape(shelf, key, outline)
    prefixes = Counter(m.group(1) for number, _, _ in sections if (m := re.match(r"^([A-Z]{1,2})-\d", number)))
    top = [caption for _, depth, caption in sections if depth == 1]
    articles = bool(top) and sum(1 for caption in top if re.match(r"\s*(?:ARTICLE|Article)\b", caption)) >= max(2, len(top) // 2)
    title = (outline.title if outline is not None else "") or getattr(citable or living, "title", "") or key
    return DocInfo(key, title, kind, shelf.books.key(key), amends, getattr(citable, "cite_as", "") or "",
                   _day(getattr(citable, "written", "")), outline is not None or living is not None, pooled, articles,
                   prefixes.most_common(1)[0][0] if prefixes else "")


def _label_free(text: str) -> str:
    return re.sub(r"^\s*\(?[A-Za-z0-9]{1,4}[.)]\s+", "", text or "")


def manual_parts(community: Any) -> tuple[Part, ...]:
    """The parts of the owner's manual the profile's rows make (``Community.owners_manual()``), each as the manual's
    section it starts at and the book it is cited by. A profile with no manual has none. This is the manual as it is
    today; document segmentation will supply the same record for any document."""
    spec = getattr(community, "owners_manual", lambda: None)()
    if spec is None:
        return ()
    out: list[Part] = []
    seen: set[tuple[str, str]] = set()
    for row in getattr(spec, "rows", ()):
        book = row.target.book
        anchor = row.at.number
        if not anchor or book == "manual" or (book, anchor) in seen:
            continue
        seen.add((book, anchor))
        title = next((c.title for c in getattr(spec, "choices", ()) if c.book == book), "") or spec.title_of(book)
        out.append(Part(spec.document, anchor, book, title if title != book else "", (), row.through.number if row.through else ""))
    return tuple(out)


# --- The parts a stored segmentation gives ---------------------------------------------------------------------------------


@dataclass
class SegmentParts:
    """What the stored segmentations gave citation scoping: the ``Part`` rows, the names they add, the documents whose
    classification parts they replace, and a line for each reading used or left out (with the reason)."""

    parts: list[Part] = field(default_factory=list)
    names: dict[str, str] = field(default_factory=dict)           # lowercase name -> the document key
    replaced: set[str] = field(default_factory=set)               # documents whose manual-classification parts are replaced
    notes: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (reading id, why)


def _fold(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def bind_outline(text: str, outlines: dict[str, DocumentOutline], *, windows: int = 20, width: int = 24) -> tuple[str, str]:
    """Which outline's document a file's text is: (key, why). Twenty short windows of the file's words, spread over it, are
    looked for in each outline's words (spacing, case, and punctuation ignored). An outline holds the file when at least
    half are found, the two texts are of like length, and no other outline comes within 0.3 of it. Else ("", why): a
    miss, never the nearest. An outline read from the file itself (``DocumentOutline.library``) is bound by its path
    instead (``segment_parts``)."""
    stream = _fold(text)
    if len(stream) < windows * width * 2:
        return "", "the file's text is too short to match to an outline"
    step = (len(stream) - width) // windows
    probes = [stream[i * step:i * step + width] for i in range(windows)]
    scored = []
    for key, o in outlines.items():
        body = _fold(o.text)
        if not body or not 0.5 <= len(body) / len(stream) <= 2.0:
            continue
        scored.append((sum(1 for q in probes if q in body) / windows, key))
    scored.sort(reverse=True)
    if not scored or scored[0][0] < 0.5:
        return "", "no outline's words are the file's"
    if len(scored) > 1 and scored[1][0] > scored[0][0] - 0.3:
        return "", f"the file's words fit more than one outline ({scored[0][1]}, {scored[1][1]})"
    return scored[0][1], f"{scored[0][0]:.0%} of the file's sampled words are the outline's"


def _bound(shelf: Any, seg: Any, row: dict[str, Any]) -> tuple[str, str]:
    outlines = shelf.outlines()
    by_path = [k for k, o in outlines.items() if o.library and o.library == row.get("path")]
    if len(by_path) == 1:
        return by_path[0], "the outline was read from this file"
    from jason.tasks import library as lib

    return bind_outline(lib.text_for(Path(shelf.data_dir), seg.id), outlines)


def _span_numbers(span: tuple[int, int] | None, outline: DocumentOutline) -> tuple[str, ...]:
    """The outline's section numbers that start inside a part's characters (``place_parts``): none where the heading is
    not in the outline's text."""
    if span is None:
        return ()
    start, end = span
    return tuple(dict.fromkeys(s.number for s in outline.sections if s.number and start <= s.start < end))


def _titled_in(outline: DocumentOutline, segment: Any) -> bool:
    """Whether a top-level segment's title (or label) is in the outline's words, ignoring case and spacing."""
    def squash(text: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())

    words = squash(outline.text)
    names = [n for n in (segment.title, segment.label, *segment.aliases) if n]
    return any(len(squash(n)) >= 6 and squash(n) in words for n in names)


@dataclass
class Readings:
    """The stored segmentations that may be used, each with the outline's key it is the document of, and why the others
    may not."""

    readings: list[tuple[str, Any]] = field(default_factory=list)      # (outline key, Segmentation)
    notes: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)       # (reading id, why)


def segment_readings(shelf: Any) -> Readings:
    """The stored segmentations (``data/library/segments``) that are of a file in the library, on disk, whose bytes are
    those the reading was made of (a stale one is left out, with the reason), that holds one top-level document, and that
    is the words of one outline (``bind_outline``). Each other reading is left out and says why: a miss is not a guess."""
    from jason.approvals.evidence import library_row
    from jason.tasks import segments as task

    out = Readings()
    data_dir = Path(shelf.data_dir)
    try:
        stored = sorted(task.stored(data_dir), key=lambda r: r.id)
    except Exception:  # noqa: BLE001 - an unreadable store is no readings
        return out

    def skip(seg: Any, why: str) -> None:
        out.skipped.append((seg.id, why))
        out.notes.append(f"segmentation {seg.id} not used: {why}")

    for seg in stored:
        row = library_row(data_dir, seg.id)
        if row is None:
            skip(seg, "the file is not in the library, so its bytes and its document cannot be checked")
            continue
        pdf = data_dir / "library" / "files" / str(row.get("path") or "")
        if not pdf.is_file():
            skip(seg, "the file is not on disk")
            continue
        if task.stale(seg, pdf):
            skip(seg, "stale: the file's bytes changed since it was read")
            continue
        tops = seg.top()
        key, how = _bound(shelf, seg, row)
        if len(tops) != 1:
            # A file of several documents is one outline's document only where the outline holds them all: the outline is
            # bound to the file, and every top-level document's title is in the outline's words (a policy or a form
            # bound in). Otherwise the outline may be only one of them, and a part of another would take its numbers.
            if not key:
                skip(seg, f"the file holds {len(tops)} documents, and none is known to be the outline's")
                continue
            missing = [s.title or s.label or s.key for s in tops if not _titled_in(shelf.outlines()[key], s)]
            if missing:
                skip(seg, f"the file holds {len(tops)} documents, and the outline {key} does not hold {len(missing)} of them")
                continue
            how = f"{how}; the file's {len(tops)} documents are bound into it"
        if not key:
            skip(seg, how)
            continue
        out.readings.append((key, seg))
        out.notes.append(f"segmentation {seg.id} is the document {key} ({how})")
    return out


def segment_parts(shelf: Any) -> SegmentParts:
    """The parts the stored segmentations give (``segment_readings``), as ``Part`` rows with ``source`` "segments". A part
    inside the document has its own section numbers (``numbers``); an exhibit, or a part inside one, has a name and a path
    and no numbers, since its sections are not an outline."""
    from jason.community.document_segments import address, place_parts

    out = SegmentParts()
    found = segment_readings(shelf)
    out.notes, out.skipped = list(found.notes), list(found.skipped)
    for key, seg in found.readings:
        outline = shelf.outlines()[key]
        before = len(out.parts)

        def nested(segment_key: str, seg: Any = seg) -> tuple[str, ...]:
            names = []
            for k in seg.path(segment_key)[1:]:
                held = seg.segment(k)
                names.append((held.label or held.title or held.key) if held else k)
            return tuple(names)

        exhibits = tuple(f"{c.label} {c.title}" for c in seg.segments if c.role == "exhibit" and c.label)
        spans = place_parts([p for p in seg.parts if not (nested(p.segment) if p.segment else ())], outline.text, exhibits,
                            seg.page_count)
        for part in seg.parts:
            way = nested(part.segment) if part.segment else ()
            numbers = _span_numbers(spans.get(part.key), outline) if not way else ()
            out.parts.append(Part(key, part.anchor, part.book, part.title, part.aliases, part.through, "segments",
                                  (*way, part.title), numbers, address(seg.id, part=part.key), part.pages, part.kind.value))
            if len((part.title or "").split()) >= 2 and part.kind.value not in ("cover", "contents"):
                for name in (part.title, *part.aliases):
                    out.names.setdefault(name.lower(), key)
            if numbers:
                out.replaced.add(key)
        for child in seg.segments:
            if child.role != "exhibit" or not child.label:
                continue
            out.parts.append(Part(key, child.label, "", child.label, child.aliases, "", "segments", nested(child.key), (),
                                  address(seg.id, segment=child.key), child.pages, "exhibit"))
            for name in (child.label, *child.aliases):
                out.names.setdefault(name.lower(), key)
        out.notes.append(f"segmentation {seg.id} gave {key} {len(out.parts) - before} parts and exhibits"
                         + ("; its sections replace the manual classification's" if key in out.replaced else ""))
    return out


def build_index(shelf: Any) -> Index:
    """The ``Index`` of a ``Shelf``'s documents."""
    community = shelf.community
    outlines = shelf.outlines()
    citable = {d.key: d for d in getattr(community, "citable_documents", lambda: ())()}
    living = {d.key: d for d in getattr(community, "living_documents", lambda: ())()}
    docs: dict[str, DocInfo] = {}
    for key in dict.fromkeys([*outlines, *citable, *living]):
        docs[key] = _info(shelf, key, outlines.get(key), citable.get(key), living.get(key))
    names = shelf.names()
    # The names that are words a person writes, not an address key ("decl", "coll"): the scanner reads only these.
    natural: set[str] = set()
    for key, o in outlines.items():
        natural.update(a.lower() for a in (o.title, *o.aliases) if a)
    for d in citable.values():
        natural.update(a.lower() for a in (d.title, d.cite_as, *d.aliases) if a)
    natural.update(n.lower() for _, common in CANON.items() for n in common)
    groups: dict[str, tuple[str, ...]] = {}
    for book, common in CANON.items():
        members = tuple(dict.fromkeys(e.document for e in shelf.books.entries if e.book is book and e.role is Role.TEXT
                                      and e.document in docs))
        if len(members) > 1:
            for name in common:
                groups[_norm_name(name)] = members
    index = Index(docs, names, groups)
    index.scan_names = {n: k for n, k in names.items() if n in natural}
    index.address_keys = frozenset(docs) | frozenset(b.value for b in Book if b.living)
    cache: dict[tuple[str, date | None], Any] = {}

    def doc(key: str, day: date | None) -> Any:
        if (key, day) not in cache:
            try:
                cache[(key, day)] = shelf.resolver.document(key, day if shelf.resolver.living(key) is not None else None)[0]
            except Exception:
                cache[(key, day)] = None
        return cache[(key, day)]

    def has(key: str, number: str, day: date | None) -> bool:
        number = normalize_number(number)
        current = doc(key, day)
        if current is not None:
            p = current.provision(number)
            return p is not None and not p.removed
        return False

    def words(key: str, number: str) -> str:
        outline = outlines.get(key)
        section = outline.section(number) if outline is not None else None
        if section is not None:
            return _label_free(outline.text_of(section))
        current = doc(key, None)
        return _label_free(current.text_of(number)) if current is not None else ""

    index.has, index.words = has, words
    manual = manual_parts(community)
    found = segment_parts(shelf) if getattr(shelf, "segments", True) else SegmentParts()
    index.parts = tuple(p for p in manual if p.document not in found.replaced) + tuple(found.parts)
    for name, key in found.names.items():
        if _norm_name(name) not in index.names and _norm_name(name) not in index.groups:
            index.scan_names.setdefault(name, key)
    index.segment_notes = tuple(found.notes)
    return index


def status_of(found: bool, reason: str) -> str:
    """What a citation came to, in the words the inventory counts by: resolved, ambiguous (several documents fit),
    unknown document (no document is named or none fits), or not on the shelf (a document that is known has no such
    section, or no outline)."""
    if found:
        return "resolved"
    if reason == "ambiguous_document":
        return "ambiguous document"
    if reason in ("ambiguous", "printed_by_several"):
        return "ambiguous (a number the document prints twice)"
    if reason in ("unparsed", "unknown_document", "empty"):
        return "unknown document"
    return "not on the shelf"


def read_text(shelf: Any, text: str, *, citing: str = "", day: date | str | None = None) -> list[dict[str, Any]]:
    """Every citation of an association document in ``text`` and what each comes to (``jason cite --scan``): the words
    as written, its form, where it is (``offset``), whether it resolved, to which document, and how that document was
    chosen (``basis``) or which documents fit (``candidates``). ``citing`` is the document the text is (a key), ``day``
    the day it was written. A heading of the document's own is not a citation."""
    from jason.tasks import rule_rows

    index = shelf.index()
    context = shelf.citing(citing, day)
    outline = shelf.outlines().get(citing) if citing else None
    heads = {s.start for s in outline.sections} if outline is not None and outline.text == text else set()
    rows = []
    for m in scoping.scan(text, index.scan_names, lettered=index.lettered_prefixes(), rows=rule_rows.table_names(),
                          keys=index.address_keys):
        if any(h <= m.start <= h + 4 for h in heads):
            continue
        c = shelf(m.expression, citing=context)
        st = c.state
        scope = c.scope
        rows.append({"offset": m.start, "text": m.text, "form": m.form.value, "named": m.named, "found": st.found,
                     "reason": st.reason.value if st.reason else "", "document": c.target.key if c.target else "",
                     "citation": st.citation, "status": status_of(st.found, st.reason.value if st.reason else ""),
                     "basis": scope.basis.value if scope is not None and scope.basis is not None else "",
                     "path": list(scope.path) if scope is not None else [],
                     "candidates": [x.key for x in scope.candidates if x.has] if scope is not None and not st.found else [],
                     "detail": st.detail if not st.found else ""})
    return rows


def tally(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Rows by form, each counted by status."""
    out: dict[str, Counter] = {}
    for r in rows:
        out.setdefault(f"{r['form']} ({'named' if r['named'] else 'bare'})", Counter())[r["status"]] += 1
    return {k: dict(v) for k, v in sorted(out.items())}


def citing_of(shelf: Any, key: str = "", day: date | str | None = None) -> Citing:
    """The citing context for a document key ("" for text that is not one of the documents) and the day it was written."""
    when = day if isinstance(day, date) or day is None else _day(str(day))
    if not key:
        return Citing(day=when)
    o = shelf.outlines().get(key)
    return Citing(key, (o.kind if o is not None else ""), when, (o.amends if o is not None else ""), o.title if o is not None else "")
