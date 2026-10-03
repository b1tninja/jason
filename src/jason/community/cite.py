"""Citations of the association's documents and records: the forms a citation is written in, and what one returns.

The model is lawlibrary's ``places.Citation``, a code closed over by each unit call. Here the book is one of the
association's documents (``Community.citable_documents()``, the living documents, an outline on disk) or one of its
records: a resolution by the number it prints, a recorded instrument by its document number, a meeting's minutes by
the meeting's day, or a Civil Code 5200 record kind. A citation narrows step by step (``doc("Declaration").section("6.2")
("a")``), names siblings (``("a", "b")``), spans (``.through("6.4")``), and closes over a date (``.as_of``). The
closure itself reads disk and lives in ``jason.tasks.cite``; this module is the pure part:

- ``parse`` reads what people and documents write ("Declaration § 6.2(a)", "Section 6.2(a) of the Declaration", "Bylaws
  Art. 6", "Rules R-3(e)", "Resolution 20990101-1", "Doc. No. 209901010001", "CIV 4920(a)", the canonical
  targets of ``jason.community.references`` such as ``decl#6.2(a)``, and ``decl#6.2(a)@2099-01-01`` for the words
  in force on a day) into a ``Target``, or a ``Miss`` with its ``Reason``. A miss is an answer, never an exception.
- ``targets_in`` reads every target a free text names (a Conflict row's provision, a response rule's authority).
- ``Node`` is one step of the reference walk, rendered as nested dicts, Markdown, or a Mermaid flowchart.
- ``Citing`` is one reverse edge: a governing document's section, or one of jason's own records, that names the target,
  with its ``scope`` (exactly, a part of it, or the whole that encloses it) and its ``treatment`` now.
- ``label_text`` splits a statute section's stored words to the subdivision a citation names.

Nothing here invents words: a recitation quotes only stored text, and says that jason's consolidated text is not an
official restatement.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from enum import Enum
from typing import Any, Iterable

from jason.community.outlines import DocumentOutline, normalize_number
from jason.community.references import CODES, TargetKind, alias_pattern, extract

CAVEAT = ("Quoted from jason's copy of the association's documents; a document kept as amended is consolidated from "
          "the instruments' own words. It is not an official restatement: the recorded and adopted documents control.")


class Kind(Enum):
    """What a citation returns (lawlibrary's handoff contract)."""

    SECTION = "section"          # one section's words
    OUTLINE = "outline"          # a document, an article, a span, or siblings: the parts, not concatenated words
    RECORD = "record"            # a resolution, an instrument, minutes, a 5200 record kind
    STATUTE = "statute"          # a statute's words on disk, or an outline of a span
    HISTORY = "history"          # a section's timeline: each version, and the numbers it went by
    MISS = "miss"


class Unit(Enum):
    """What a target names."""

    SECTION = "section"
    DOCUMENT = "document"
    STATUTE = "statute"
    RESOLUTION = "resolution"
    INSTRUMENT = "instrument"
    MINUTES = "minutes"
    RECORD = "record"
    BOOK = "book"                # an item of a series book named by an address (jason://budget/2099)


class Reason(Enum):
    """Why a citation is a miss."""

    EMPTY = "empty"                                  # nothing was asked
    UNPARSED = "unparsed"                            # not a form jason reads
    UNKNOWN_DOCUMENT = "unknown_document"            # no document by that name
    NO_OUTLINE = "no_outline"                        # a known document with no outline on disk (jason outlines)
    NOT_IN_DOCUMENT = "not_in_document"              # the document has no such section
    PARENT_ONLY = "parent_only"                      # the section is there, not the subsection
    AMBIGUOUS = "ambiguous"                          # the document numbers several sections the same
    REMOVED = "removed"                              # an amendment removed it; cite it as of an earlier day
    NOT_KEPT_AS_AMENDED = "not_kept_as_amended"      # a date asked of a document with no history
    UNREADABLE = "unreadable"                        # a source could not be read
    STATUTE_NOT_ON_DISK = "statute_not_on_disk"      # not in data/authorities: lawlibrary's cite reads it
    PRIOR_NUMBERING = "prior_numbering"              # a Davis-Stirling number from before 2014
    LABEL_NOT_FOUND = "label_not_found"              # the statute is there, not the subdivision
    EDITION_NOT_HELD = "edition_not_held"            # a statute as of a day: jason holds one edition
    NO_RESOLUTION = "no_resolution_prints_it"
    PRINTED_BY_SEVERAL = "printed_by_several"
    UNKNOWN_INSTRUMENT = "unknown_instrument"
    NO_MINUTES = "no_minutes"
    UNKNOWN_RECORD = "unknown_record"
    RESTRICTED = "restricted"                        # a book the association may withhold (CIV 5215): ask privately
    NO_VERSION = "no_such_version"                   # no version took effect that day, or no such stage on disk
    NO_BOOK_DOCUMENT = "no_book_document"            # a book the profile maps no document to


@dataclass(frozen=True)
class Miss:
    reason: Reason
    detail: str = ""
    expression: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"kind": Kind.MISS.value, "found": False, "reason": self.reason.value, "detail": self.detail,
                "expression": self.expression}


@dataclass(frozen=True)
class Target:
    """One thing a citation names, written the same way every time (``id``)."""

    unit: Unit
    key: str                              # a document key; a code ("CIV", "10 CCR"); a resolution or instrument
                                          # number; a meeting's day; a 5200 record kind's value
    number: str = ""                      # a section ("6.2(a)", "R-3(e)") or a statute section ("4920(a)")
    end: str = ""                         # the last section of a span
    siblings: tuple[str, ...] = ()        # whole numbers named together ("6.2(a)", "6.2(b)")
    article: bool = False                 # named as an article ("Art. 6")
    as_of: date | None = None             # "@YYYY-MM-DD": the words in force on that day
    version: str = ""                     # an address's version: "base", the day one took effect, or a stage
                                          # ("proposed-2099-01-01"); jason.community.addresses
    history: bool = False                 # an address's "/history": the timeline
    fragment: str = ""                    # an address's "#item-4"

    @property
    def id(self) -> str:
        if self.unit is Unit.SECTION:
            body = ",".join(self.siblings) if self.siblings else self.number + (f"..{self.end}" if self.end else "")
            out = f"{self.key}#{body}"
        elif self.unit is Unit.DOCUMENT:
            out = self.key
        elif self.unit is Unit.STATUTE:
            body = ",".join(self.siblings) if self.siblings else self.number + (f"-{self.end}" if self.end else "")
            out = f"{self.key} {body}"
        elif self.unit is Unit.BOOK:
            out = f"{self.key}/{self.number}" if self.number else self.key
        else:
            out = f"{self.unit.value}:{self.key}"
        out += f"@{self.as_of.isoformat()}" if self.as_of else ""
        out += f"@@{self.version}" if self.version else ""
        out += "/history" if self.history else ""
        return out + (f"#{self.fragment}" if self.fragment else "")

    @property
    def base(self) -> str:
        """A statute's section without its labels ("CIV 4920"), else the id without a date."""
        if self.unit is Unit.STATUTE:
            section = self.number.split("(", 1)[0]
            return f"{self.key} {section}"
        return replace(self, as_of=None, version="", history=False, fragment="").id

    @property
    def labels(self) -> tuple[str, ...]:
        """A statute section's subdivision labels ("4920(b)(1)" -> "b", "1")."""
        return tuple(re.findall(r"\(([^)]+)\)", self.number))


# --- The grammar --------------------------------------------------------------------------------------------------------

_LABEL = r"\(\s*[A-Za-z0-9]{1,5}\s*\)"
_DOC_NUM = rf"(?:[A-Z]{{1,2}}-\d+(?:\.\d+)*|\d+(?:\.\d+)*)(?:\s?{_LABEL})*"
_STAT_NUM = rf"\d+(?:\.\d+)*(?:\s?{_LABEL})*"
_WORD = r"(?:Sections?|Secs?\.?|§§?|Articles?|Arts?\.|Paragraphs?|Paras?\.|¶|Rules?|Subsections?|Subdivisions?)"
_SIB = rf"(?:\s*(?:,\s*(?:and|or)?|\band\b|\bor\b|&)\s*(?:{_LABEL}|{_DOC_NUM}))+"
_SPAN = rf"\s*(?:\bthrough\b|\bthru\b|\bto\b|–|—|-)\s*(?:{_WORD}\s*)?(?P<end>{_DOC_NUM})"
_CODE_ALT = "|".join(f"(?:{pattern})" for pattern, _ in CODES)
ABBREVIATIONS = frozenset({"CIV", "CORP", "HSC", "GOV", "EVID", "BPC", "CCP", "VEH", "PEN", "FAM", "PROB", "LAB", "RTC",
                           "WAT", "PRC", "COM", "INS", "FIN", "UIC", "FAC", "EDC", "ELEC", "HNC"})
_ABBR = "|".join(sorted(ABBREVIATIONS, key=len, reverse=True))
_STATUTE_FIRST = re.compile(rf"^(?P<code>{_CODE_ALT}|\b(?:{_ABBR})\b)\s*,?\s*(?:{_WORD}\s*)?(?P<num>{_STAT_NUM})"
                            rf"(?P<rest>.*)$", re.I)
_STATUTE_LAST = re.compile(rf"^(?:{_WORD}\s*)(?P<num>{_STAT_NUM})(?P<rest>.*?)\s*,?\s+of\s+(?:the\s+)?"
                           rf"(?P<code>{_CODE_ALT})$", re.I)
_REG = re.compile(r"^(?:Title\s+)?(?P<title>\d{1,2})\s+(?:C\.?C\.?R\.?|Cal(?:ifornia)?\.?\s*Code\s+(?:of\s+)?"
                  rf"Reg(?:ulation)?s?\.?)\s*(?:§\s*|[Ss]ections?\s*)?(?P<num>{_STAT_NUM})$", re.I)
_BARE = re.compile(rf"^(?:{_WORD}\s*)?(?P<num>\d{{4}}(?:\.\d+)?(?:\s?{_LABEL})*)$", re.I)
_RESOLUTION = re.compile(r"^(?:(?:Administrative|Special|Policy|Board)\s+)?Resolution\s*(?:No\.?\s*|Number\s*|#\s*)?"
                         r"(?P<num>[\w-]*\d[\w-]*)$", re.I)
_INSTRUMENT = re.compile(r"^(?:(?:Recorder'?s?\s+)?(?:Doc(?:ument)?\.?|Instrument)\s*(?:No\.?|Number|#)?\s*)?"
                         r"(?P<num>(?:19|20)\d{10})$|^Book\s+(?P<book>\d{1,8})\s*,?\s*Page\s+(?P<page>\d{1,5})$", re.I)
_MINUTES = re.compile(r"^(?:the\s+)?(?:(?:draft\s+)?minutes)\s*(?:of|for|from|:)?\s*(?:the\s+)?(?:\w+\s+)?"
                      r"(?:meeting\s+)?(?:of|on|held)?\s*(?P<day>\d{4}-\d{2}-\d{2})$", re.I)
_CANONICAL = re.compile(r"^(?P<key>[a-z0-9][a-z0-9.-]*)#(?P<body>\S+)$")
_PREFIXED = re.compile(r"^(?P<unit>resolution|instrument|minutes|record):(?P<key>.+)$", re.I)
_AS_OF = re.compile(r"\s*(?:@|,?\s*\bas\s+of\s+)(?P<day>\d{4}-\d{2}-\d{2})\s*$", re.I)


def _code(name: str) -> str:
    name = " ".join(name.split())
    if name.upper() in ABBREVIATIONS:
        return name.upper()
    for pattern, code in CODES:
        if re.fullmatch(pattern, name, re.I):
            return code
    return ""


def _siblings(first: str, rest: str) -> tuple[str, ...]:
    """"6.2(a)" with ", (b) and (c)" -> 6.2(a), 6.2(b), 6.2(c); a whole number stands for itself."""
    out = [first]
    base = first[: first.rfind("(")] if "(" in first else first
    for item in re.findall(rf"{_LABEL}|{_DOC_NUM}", rest):
        item = normalize_number(item)
        out.append(base + item if item.startswith("(") else item)
    return tuple(dict.fromkeys(out))


def _rest(unit: Unit, key: str, number: str, rest: str, *, article: bool, as_of: date | None,
          expression: str) -> Target | Miss:
    number = normalize_number(number)
    rest = rest.strip()
    if not rest:
        return Target(unit, key, number, article=article, as_of=as_of)
    if m := re.fullmatch(_SPAN, rest, re.I):
        return Target(unit, key, number, end=normalize_number(m.group("end")), article=article, as_of=as_of)
    if re.fullmatch(_SIB, rest, re.I):
        return Target(unit, key, number, siblings=_siblings(number, rest), article=article, as_of=as_of)
    if re.fullmatch(r"(?:,?\s*et\s+seq\.?|,?\s*(?:above|below|hereof|herein))", rest, re.I):
        return Target(unit, key, number, article=article, as_of=as_of)
    return Miss(Reason.UNPARSED, f"read {number}, then could not read {rest!r}", expression)


def _names_pattern(names: dict[str, str]) -> str:
    alt = sorted(names, key=len, reverse=True)
    return "|".join(re.escape(n).replace(r"\ ", r"\s+") for n in alt)


def of_address(text: str, keys: set[str], books: Any = None) -> Target | Miss:
    """A ``jason://`` address (``jason.community.addresses``) as a target. A living book's key goes to the document the
    profile maps to it (``books``: ``jason.community.books.Books``); a document's own key stands for itself. A version
    made effective on a day is kept as the target's ``version`` (the reader checks a version took effect that day) and
    read as of that day; a day in force (``:``) is ``as_of``."""
    from jason.community.addresses import AddressError, parse as parse_address
    from jason.community.books import Book

    try:
        a = parse_address(text)
    except AddressError as exc:
        return Miss(Reason.UNPARSED, str(exc), text)
    label = a.label
    as_of = a.in_force or (label.effective if label is not None else None)
    version = a.version
    if a.book is not None and a.book.info.shape.value == "group":
        return Target(Unit.BOOK, a.key, a.item or a.section, version=version, fragment=a.fragment)
    if a.series:
        book, item = a.book, a.item
        if book is Book.RES and item:
            return Target(Unit.RESOLUTION, item, version=version, fragment=a.fragment)
        if book is Book.MIN and item:
            return Target(Unit.MINUTES, item, version=version, fragment=a.fragment)
        if book is Book.INST and item:
            return Target(Unit.INSTRUMENT, item, version=version, fragment=a.fragment)
        return Target(Unit.BOOK, a.key, item, version=version, fragment=a.fragment)
    document = books.document(a.key) if books is not None else a.key
    if document not in keys:
        book = a.book
        if book is not None:
            return Miss(Reason.NO_BOOK_DOCUMENT, f"the profile maps no document to {a.key} ({book.info.title}, "
                        f"{book.info.statute or 'not in the Act'}): Community.book_entries()", text)
        return Miss(Reason.UNKNOWN_DOCUMENT, f"no book or document {a.key!r}", text)
    if not a.section:
        return Target(Unit.DOCUMENT, document, as_of=as_of, version=version, history=a.history, fragment=a.fragment)
    body = a.section
    if ".." in body:
        first, _, end = body.partition("..")
        return Target(Unit.SECTION, document, normalize_number(first), end=normalize_number(end), as_of=as_of,
                      version=version, fragment=a.fragment)
    if "," in body:
        numbers = tuple(normalize_number(n) for n in body.split(","))
        return Target(Unit.SECTION, document, numbers[0], siblings=numbers, as_of=as_of, version=version,
                      fragment=a.fragment)
    number = body if "~" in body else normalize_number(body)
    return Target(Unit.SECTION, document, number, as_of=as_of, version=version, history=a.history,
                  fragment=a.fragment)


def parse(expression: str, names: dict[str, str], books: Any = None) -> Target | Miss:
    """What ``expression`` names. ``names`` maps each name a document goes by (lowercase), and each document key, to
    its key; ``books`` (``jason.community.books.Books``) maps a book's key (``decl``) to its document, for an address
    (``jason://decl/6.2(a)``) and a canonical ``decl#6.2(a)``. A miss carries its reason: nothing here raises on what a
    person or a document wrote."""
    text = " ".join(str(expression or "").split()).strip().rstrip(".;:")
    if not text:
        return Miss(Reason.EMPTY, "name a document's section, a resolution, an instrument, minutes, or a statute",
                    str(expression or ""))
    if text.lower().startswith("jason://"):
        return of_address(text, set(names.values()), books)
    as_of = None
    if m := _AS_OF.search(text):
        try:
            as_of = date.fromisoformat(m.group("day"))
        except ValueError:
            return Miss(Reason.UNPARSED, f"{m.group('day')} is not a date (YYYY-MM-DD)", text)
        text = text[: m.start()].strip().rstrip(",")
    keys = {v for v in names.values()}
    lower = {k.lower(): v for k, v in names.items()}
    if m := _PREFIXED.match(text):
        unit = Unit(m.group("unit").lower())
        key = m.group("key").strip()
        return Target(unit, key, as_of=as_of)
    if m := _CANONICAL.match(text):
        key = m.group("key")
        if key not in keys and books is not None and books.document(key) in keys:
            key = books.document(key)                  # a book's key: decl#6.2(a)
        if key not in keys:
            return Miss(Reason.UNKNOWN_DOCUMENT, f"no document {m.group('key')!r}", text)
        body = m.group("body")
        if ".." in body:
            first, _, end = body.partition("..")
            return Target(Unit.SECTION, key, normalize_number(first), end=normalize_number(end), as_of=as_of)
        if "," in body:
            numbers = tuple(normalize_number(n) for n in body.split(","))
            return Target(Unit.SECTION, key, numbers[0], siblings=numbers, as_of=as_of)
        return Target(Unit.SECTION, key, body if "~" in body else normalize_number(body), as_of=as_of)
    if text in keys:
        return Target(Unit.DOCUMENT, text, as_of=as_of)
    if m := _RESOLUTION.match(text):
        return Target(Unit.RESOLUTION, m.group("num"), as_of=as_of)
    if m := _INSTRUMENT.match(text):
        key = m.group("num") or f"book {int(m.group('book')):08d} page {m.group('page')}"
        return Target(Unit.INSTRUMENT, key, as_of=as_of)
    if m := _MINUTES.match(text):
        return Target(Unit.MINUTES, m.group("day"), as_of=as_of)
    if m := _REG.match(text):
        return _rest(Unit.STATUTE, f"{m.group('title')} CCR", m.group("num"), "", article=False, as_of=as_of,
                     expression=text)
    for pattern in (_STATUTE_FIRST, _STATUTE_LAST):
        if (m := pattern.match(text)) and (code := _code(m.group("code"))):
            return _rest(Unit.STATUTE, code, m.group("num"), m.group("rest"), article=False, as_of=as_of,
                         expression=text)
    if lower:
        alt = _names_pattern(lower)
        first = re.match(rf"^(?:the\s+)?(?P<doc>{alt})(?:['’]s)?\s*,?\s*(?:(?P<word>{_WORD})\s*)?(?P<num>{_DOC_NUM})"
                         rf"(?P<rest>.*)$", text, re.I)
        last = re.match(rf"^(?:the\s+)?(?:(?P<word>{_WORD})\s*)?(?P<num>{_DOC_NUM})(?P<rest>.*?)\s*,?\s+(?:of|in)\s+"
                        rf"(?:the\s+|these\s+|this\s+|said\s+)?(?P<doc>{alt})$", text, re.I)
        for m in (first, last):
            if m is None:
                continue
            key = lower.get(" ".join(m.group("doc").lower().split()), "")
            if not key:
                continue
            word = (m.group("word") or "").lower()
            return _rest(Unit.SECTION, key, m.group("num"), m.group("rest"), article=word.startswith("art"),
                         as_of=as_of, expression=text)
        if m := re.fullmatch(rf"(?:the\s+)?(?P<doc>{alt})", text, re.I):
            return Target(Unit.DOCUMENT, lower[" ".join(m.group("doc").lower().split())], as_of=as_of)
    if m := _BARE.match(text):
        number = int(re.match(r"\d+", m.group("num")).group(0))
        if 1350 <= number <= 6200:
            # The references grammar's rule: a bare four-digit section in an association's writing is the Civil Code.
            return _rest(Unit.STATUTE, "CIV", m.group("num"), "", article=False, as_of=as_of, expression=text)
    if re.match(rf"^(?:{_WORD}\s*)?{_DOC_NUM}", text, re.I):
        return Miss(Reason.UNPARSED, "name the document or the code the section is in", text)
    return Miss(Reason.UNKNOWN_DOCUMENT if lower else Reason.UNPARSED, f"no document or record is named {text!r}", text)


def of_reference(target: str, kind: str = "") -> Target | None:
    """A ``jason.community.references`` target ("decl#6.2(a)", "CIV 4926(a)(3)", "resolution:20990101-1",
    "instrument:209901010001", "enforcement-policy") as a ``Target``; None for one nothing here can follow
    ("named:...")."""
    target = (target or "").strip()
    if not target or target.startswith("named:"):
        return None
    if m := _PREFIXED.match(target):
        return Target(Unit(m.group("unit").lower()), m.group("key").strip())
    if "#" in target:
        key, _, number = target.partition("#")
        if not key:
            return None
        return Target(Unit.SECTION, key, normalize_number(number))
    if kind == TargetKind.STATUTE.value or re.match(r"^(?:\d{1,2}\s+CCR|[A-Z]{2,5})\s+\d", target):
        m = re.match(r"^(?P<code>\d{1,2}\s+CCR|[A-Z]{2,5})\s+(?P<num>.+)$", target)
        if m:
            return Target(Unit.STATUTE, m.group("code"), normalize_number(m.group("num")))
        return None
    if re.fullmatch(r"[a-z0-9][a-z0-9-]*", target):
        return Target(Unit.DOCUMENT, target)
    return None


_LETTERED_AFTER = r"\s*,?\s*(?:(?:Rule|Section|§)\s*)?(?P<num>[A-Z]{1,2}-\d+(?:\.\d+)*(?:\s?\([A-Za-z0-9]{1,5}\))*)"
_CANON_IN_TEXT = re.compile(r"(?<![\w#])(?P<key>[a-z0-9][a-z0-9-]*)#(?P<num>[A-Za-z0-9.()\-]+[A-Za-z0-9)])")


def targets_in(text: str, names: dict[str, str]) -> list[Target]:
    """Every document section, statute, resolution, and instrument a free text names (a Conflict row's provision, a
    rule's authority, a step of a procedure), read by the references grammar, plus the forms it leaves to us: a
    canonical ``key#n`` and a rules book's lettered number after its name ("Rules R-3(e)"). An unqualified
    "Section 6.2" names no document here and is left out."""
    text = text or ""
    if not text.strip():
        return []
    lower = {k.lower(): v for k, v in names.items()}
    keys = set(lower.values())
    out: list[Target] = []
    for ref in extract(DocumentOutline(key="", title="", text=text), lower):
        t = of_reference(ref.target, ref.kind.value)
        if t is not None and t.key:
            out.append(t)
    for m in _CANON_IN_TEXT.finditer(text):
        if m.group("key") in keys:
            out.append(Target(Unit.SECTION, m.group("key"), normalize_number(m.group("num"))))
    pattern = alias_pattern(lower)
    if pattern is not None:
        for m in pattern.finditer(text):
            after = re.match(_LETTERED_AFTER, text[m.end():m.end() + 40])
            key = lower.get(" ".join(m.group("doc").lower().split()), "")
            if after and key:
                out.append(Target(Unit.SECTION, key, normalize_number(after.group("num"))))
    return list(dict.fromkeys(out))


# --- Where a cited target sits against the one asked for ----------------------------------------------------------------

class Scope(Enum):
    EXACT = "exact"              # names it
    WITHIN = "within"            # names a part of it (6.2(a) when 6.2 was asked)
    ENCLOSING = "enclosing"      # names the whole it sits in (6.2 when 6.2(a) was asked)


def _inside(inner: str, outer: str) -> bool:
    return inner != outer and (inner.startswith(outer + "(") or inner.startswith(outer + "."))


def scope_of(cited: Target, wanted: Target) -> Scope | None:
    """How a cited target stands to the one asked for, or None when it is something else. A document named as a
    whole ("the Declaration") does not cite each of its sections, so it is not an enclosing citation of one."""
    if cited.unit is Unit.DOCUMENT or wanted.unit is Unit.DOCUMENT:
        if cited.key != wanted.key or Unit.STATUTE in (cited.unit, wanted.unit):
            return None
        if cited.unit is wanted.unit:
            return Scope.EXACT
        return Scope.WITHIN if wanted.unit is Unit.DOCUMENT else None
    if cited.unit is not wanted.unit or cited.key != wanted.key:
        return None
    if cited.unit not in (Unit.SECTION, Unit.STATUTE):
        return Scope.EXACT
    a, b = cited.number, wanted.number
    if a == b:
        return Scope.EXACT
    if _inside(a, b):
        return Scope.WITHIN
    if _inside(b, a):
        return Scope.ENCLOSING
    return None


# --- The walk and the reverse edges ------------------------------------------------------------------------------------

@dataclass
class Node:
    """One target in the reference walk, with how its parent names it."""

    id: str
    citation: str
    unit: str
    found: bool
    reason: str = ""
    relation: str = ""           # the citing verb (cites, amends, acts under, ...)
    quote: str = ""              # the sentence the parent names it in
    count: int = 1               # how many times the parent names it
    repeat: bool = False         # reached before: not followed again
    stopped: bool = False        # not followed: the hops ran out, or the walk does not enter it
    children: list[Node] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        out = {k: v for k, v in asdict(self).items() if k != "children"}
        out["children"] = [c.as_dict() for c in self.children]
        return out

    def nodes(self) -> list[dict[str, Any]]:
        """One row per target the walk reached, with the hop it was first reached on (lawlibrary's ``_walk_nodes``)."""
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def walk(node: Node, hop: int) -> None:
            if node.id not in seen:
                seen.add(node.id)
                rows.append({"id": node.id, "citation": node.citation, "unit": node.unit, "found": node.found,
                             "reason": node.reason, "hop": hop})
            for child in node.children:
                walk(child, hop + 1)

        walk(self, 0)
        return rows

    def edges(self) -> list[dict[str, Any]]:
        """Every hop as source, target, label, and found; a repeated pair is dropped (lawlibrary's ``_walk_edges``)."""
        out: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def walk(node: Node) -> None:
            for child in node.children:
                if (node.id, child.id) not in seen:
                    seen.add((node.id, child.id))
                    out.append({"source": node.id, "target": child.id, "label": child.relation or "cites",
                                "found": child.found, "count": child.count})
                walk(child)

        walk(self)
        return out


def tree_lines(node: Node, *, depth: int = 0) -> list[str]:
    mark = "" if node.found else f" [missing: {node.reason}]"
    verb = f"{node.relation} " if depth and node.relation and node.relation != "cites" else ""
    times = f" x{node.count}" if node.count > 1 else ""
    tail = " (repeat)" if node.repeat else ""
    out = [f"{'  ' * depth}- {verb}{node.citation}{times}{mark}{tail}"]
    for child in node.children:
        out += tree_lines(child, depth=depth + 1)
    return out


def _mermaid_id(text: str) -> str:
    return "n_" + re.sub(r"[^A-Za-z0-9_]", "_", text)


def mermaid(node: Node) -> str:
    """The walk as a Mermaid flowchart: a missing target is dashed, a statute is round."""
    lines = ["flowchart LR"]
    declared: set[str] = set()

    def declare(n: Node) -> None:
        ident = _mermaid_id(n.id)
        if ident in declared:
            return
        declared.add(ident)
        label = n.citation.replace('"', "'")[:60]
        shape = f'(("{label}"))' if n.unit == Unit.STATUTE.value else f'["{label}"]'
        lines.append(f"  {ident}{shape}")
        if not n.found:
            lines.append(f"  class {ident} missing")

    edges: set[tuple[str, str]] = set()

    def walk(n: Node) -> None:
        declare(n)
        for child in n.children:
            declare(child)
            pair = (_mermaid_id(n.id), _mermaid_id(child.id))
            if pair not in edges:
                edges.add(pair)
                label = child.relation if child.relation and child.relation != "cites" else ""
                label = (label + (f" x{child.count}" if child.count > 1 else "")).strip()
                arrow = f" -->|{label}| " if label else " --> "
                lines.append(f"  {pair[0]}{arrow}{pair[1]}")
            walk(child)

    walk(node)
    lines.append("  classDef missing stroke-dasharray: 5 5")
    return "\n".join(lines)


class Holder(Enum):
    """What names a target: a governing document's section, or one of jason's own records."""

    DOCUMENT = "governing document"
    CONFLICT = "conflict row"
    NOTICE_CLAUSE = "notice provision"
    NOTICE_REQUIREMENT = "notice requirement"
    DUTY = "document duty"
    ASSIGNMENT = "schedule assignment"
    RESPONSE_RULE = "response rule"
    TEMPLATE = "letter template"
    PROCEDURE = "procedure"
    LESSON = "lesson"
    EMBEDDED = "embedded reference"
    RECORD_KIND = "association record kind"


class Treatment(Enum):
    """How the cited words stand now against what the citing record names (a citator's "noting up")."""

    CURRENT = "current"                                  # the words the record quotes are still there
    UNAMENDED = "unamended"                              # no amendment has set the section's words
    AMENDED = "amended"                                  # an amendment set them; the record stores no version
    WORDS_CHANGED = "words changed since read"           # the record quotes words no longer there
    REMOVED = "removed"
    RENUMBERED = "numbered differently"                  # the outline it was read from has the number; the text as
                                                         # amended does not, and no permanent id finds it
    RELOCATED = "renumbered, found by its permanent id"  # numbered otherwise in the text as amended (or printed twice,
                                                         # or run inline): the permanent id finds the section
    MISSING = "missing"                                  # the document has no such section
    FILLED = "filled when rendered"                      # an embedded token: always the words in force
    NOT_CHECKED = "not checked"                          # a statute or a record: nothing to compare

STALE = frozenset({Treatment.WORDS_CHANGED, Treatment.REMOVED, Treatment.RENUMBERED, Treatment.MISSING})


@dataclass(frozen=True)
class Citing:
    """One reverse edge: who names the target, how, and how the cited words stand now."""

    holder: Holder
    key: str                     # the citing record ("conflict:<key>", "bylaws#7.2", a file)
    title: str
    target: str                  # the id it names
    scope: Scope
    field: str = ""              # the record's field that names it
    relation: str = ""
    quote: str = ""              # words the citing record quotes (a document's sentence, a duty's clause)
    treatment: Treatment = Treatment.NOT_CHECKED
    note: str = ""
    reading: str = ""            # jason's own paraphrase in the record (a Conflict row's ``says``): a reading, never
                                 # the words
    words: str = ""              # beside a reading, the cited section's words now, to compare

    def as_dict(self) -> dict[str, Any]:
        out = {"holder": self.holder.value, "key": self.key, "title": self.title, "target": self.target,
               "scope": self.scope.value, "field": self.field, "relation": self.relation, "quote": self.quote,
               "treatment": self.treatment.value, "note": self.note}
        if self.reading:
            out["recitedWords"] = self.words
            out["jasonsReading"] = self.reading
        return out


# --- Statute subdivisions ------------------------------------------------------------------------------------------------

_ROMAN = re.compile(r"^(?:i{1,3}|iv|vi{0,3}|ix|x{1,3}|xi{1,3}|xiv|xv)$")
_ROMAN_VALUES = {"i": 1, "v": 5, "x": 10}


def _style(label: str, roman: bool = False) -> str:
    if label.isdigit():
        return "digit"
    if label.isupper():
        return "upper"
    return "roman" if roman and _ROMAN.match(label) else "lower"


def _value(label: str, style: str) -> int:
    """A label's place in its series: (c) is 3, (12) is 12, (iv) is 4, (aa) follows (z)."""
    if style == "digit":
        return int(label)
    if style == "roman":
        total, prev = 0, 0
        for ch in reversed(label):
            v = _ROMAN_VALUES.get(ch, 0)
            total, prev = (total - v, prev) if v < prev else (total + v, v)
        return total
    letters = label.lower()
    return (len(letters) - 1) * 26 + ord(letters[-1]) - 96


def paragraphs(text: str) -> list[str]:
    """Paragraphs at blank lines, and a label that opens a line ("(b) (1) If ...") splits one."""
    out: list[str] = []
    for block in re.split(r"\n[ \t\r\f\v]*\n", text or ""):
        block = " ".join(block.split())
        if not block:
            continue
        # "(b) (1) If a board meeting ..." opens (b) and its (1) together: keep them as two paragraphs.
        m = re.match(r"^(\([A-Za-z0-9]{1,4}\))\s+(\([A-Za-z0-9]{1,4}\)\s.*)$", block)
        if m:
            out += [m.group(1), m.group(2)]
        else:
            out.append(block)
    return out


def label_text(text: str, labels: Iterable[str]) -> str:
    """The words of the subdivision ``labels`` names ("b", "1" for (b)(1)) inside a section's stored text: each label
    opens at a paragraph that starts with it and runs to the next paragraph that starts with one of the next three
    labels of its series (one or two may be repealed), so a deeper "(i)" does not end an "(a)". A lowercase label
    under a number or a capital is roman. An empty string when a label is not found. jason splits the official
    section; the section itself is the source."""
    current = paragraphs(text)
    above = ""
    for label in labels:
        label = str(label).strip("() ")
        roman = above in ("digit", "upper")
        style = _style(label, roman)
        start = next((k for k, p in enumerate(current) if p.startswith(f"({label})")), None)
        if start is None:
            return ""
        value = _value(label, style)
        end = len(current)
        for k in range(start + 1, len(current)):
            m = re.match(r"^\(([A-Za-z0-9]{1,4})\)", current[k])
            if not m or _style(m.group(1), roman) != style:
                continue
            if 0 < _value(m.group(1), style) - value <= 3:
                end = k
                break
        current = current[start:end]
        above = style
    return "\n\n".join(current)


def sentences(text: str) -> list[str]:
    """The text's sentences, by the duty reader's splitter (``jason.community.deontic.sentences``)."""
    from jason.community.deontic import sentences as spans

    return [text[s:e] for s, e in spans(text or "")]


__all__ = ["ABBREVIATIONS", "CAVEAT", "Citing", "Holder", "Kind", "Miss", "Node", "Reason", "STALE", "Scope", "Target",
           "Treatment", "Unit", "label_text", "mermaid", "of_address", "of_reference", "paragraphs", "parse", "scope_of",
           "sentences", "targets_in", "tree_lines"]
