"""Defined terms: what a governing document says its own words mean, and where.

A declaration or bylaws usually opens with a definitions article: '"Rules" shall mean the rules and regulations ...'.
A word a document defines takes the document's meaning wherever that document uses it, not its ordinary one (Civil Code
1644: words are taken in their ordinary sense unless used in a technical sense, or a special meaning is given them).
So reciting a provision that uses a defined term carries the term's definition beside it, by its address, as an edge:
the words of the definition, never a paraphrase.

- ``read`` is a small general reader: a provision whose words open with one or more quoted terms followed by "shall
  mean", "means", "shall refer to", or "shall have the meaning" defines them. A person checks what it finds; the
  profile keeps the result as ``DefinedTerm`` rows (``Community.defined_terms()``), so a reading slip never becomes a
  definition by itself.
- ``used_in`` finds the defined terms a text uses, as written (a capitalized term, matched whole), longest first so
  "Member in Good Standing" is not also "Member".
- ``GoverningSet`` is what a document says "the Governing Documents" are (a profile row), kept apart from the statute's
  list (CIV 4150, ``jason.community.books.STATUTE_GOVERNING``); ``compare_governing`` reports how the two differ and
  resolves nothing.

Pure: the rows come from the profile and the text from the readers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

_QUOTED = r"[\"“]([A-Z][^\"“”]{0,60}?)[,.]?[\"”]"
_LEAD = re.compile(rf"^\W*(?:(?:The\s+)?(?:terms?|words?|phrases?)\s+)?(?P<terms>{_QUOTED}(?:\s*(?:,|or|and|,\s*and|,\s*or)?"
                   rf"\s*{_QUOTED})*)\s*(?:\([^)]{{0,80}}\)\s*)?(?:,\s*)?(?:as\s+used\s+in\s+[^,]{{1,60}},\s*)?"
                   r"(?:shall\s+mean|means|shall\s+refer\s+to|refers\s+to|shall\s+have\s+the\s+(?:same\s+)?meaning|"
                   r"has\s+the\s+(?:same\s+)?meaning|shall\s+include|includes)\b")


@dataclass(frozen=True)
class Definition:
    """A definition the reader found: the terms, the section, and its words as read."""

    terms: tuple[str, ...]
    section: str
    words: str


@dataclass(frozen=True)
class DefinedTerm:
    """A term a document defines, and the section that defines it (a profile row)."""

    term: str                        # as the document writes it ("Governing Documents")
    document: str                    # the document key ("bylaws")
    section: str                     # the section that defines it ("2.4")
    note: str = ""

    @property
    def target(self) -> str:
        return f"{self.document}#{self.section}"


@dataclass(frozen=True)
class GoverningSet:
    """What a document says "the Governing Documents" are: the books it names, and anything else it names in words
    ("the policies and resolutions duly adopted by the Board"), with the section that says so."""

    defined_at: str                  # "decl#1.21": the defining section, by book or document key
    books: tuple[Any, ...]           # jason.community.books.Book members the definition names
    also: tuple[str, ...] = ()       # what it names that is not a book ("the policies duly adopted by the Board")
    note: str = ""


def read(provisions: Iterable[Any]) -> list[Definition]:
    """The definitions in a document's provisions (anything with ``number``, ``caption``, ``body``)."""
    out = []
    for p in provisions:
        body = " ".join((getattr(p, "body", "") or "").split())
        if not getattr(p, "number", "") or not body:
            continue
        m = _LEAD.match(body)
        if not m:
            continue
        terms = tuple(dict.fromkeys(t.strip().rstrip(",.") for t in re.findall(_QUOTED, m.group("terms"))))
        if terms:
            out.append(Definition(terms, p.number, body))
    return out


def rows(definitions: Iterable[Definition], document: str) -> list[DefinedTerm]:
    """The reader's findings as rows, one per term, for a person to check and keep in the profile."""
    return [DefinedTerm(t, document, d.section) for d in definitions for t in d.terms]


def used_in(text: str, terms: Sequence[DefinedTerm], *, document: str = "") -> list[DefinedTerm]:
    """The defined terms ``text`` uses, as written and whole, longest first; with ``document``, only that document's
    terms and those of documents with no term of the same name in it."""
    text = text or ""
    mine = [t for t in terms if not document or t.document == document]
    taken: list[tuple[int, int]] = []
    found: list[DefinedTerm] = []
    for t in sorted(mine, key=lambda t: len(t.term), reverse=True):
        for m in re.finditer(rf"(?<![\w-]){re.escape(t.term)}(?![\w-])", text):
            if any(a <= m.start() < b for a, b in taken):
                continue
            taken.append(m.span())
            if t not in found:
                found.append(t)
    return found


@dataclass
class Comparison:
    statute: tuple[Any, ...]                       # the books 4150 names
    profile: tuple[Any, ...]                       # the books the document's definition names
    only_profile: tuple[Any, ...] = ()
    only_statute: tuple[Any, ...] = ()
    also: tuple[str, ...] = ()
    notes: list[str] = field(default_factory=list)


def compare_governing(defined: GoverningSet | None, statute: Sequence[Any]) -> Comparison:
    """How the document's "Governing Documents" differ from the statute's list. 4150's list is not exhaustive ("such
    as"), so a book only the document names is a difference to read, not a conflict; one only the statute names is a
    book the document's own term leaves out."""
    if defined is None:
        return Comparison(tuple(statute), (), notes=["the profile records no definition of the Governing Documents"])
    profile = tuple(defined.books)
    out = Comparison(tuple(statute), profile, tuple(b for b in profile if b not in statute),
                     tuple(b for b in statute if b not in profile), tuple(defined.also))
    out.notes.append("CIV 4150 names its documents \"such as\": a list, not a closed set. The document's own term "
                     "governs where the document uses it (Civil Code 1644); the law's term governs the law. The "
                     "difference is reported, not resolved.")
    return out


__all__ = ["Comparison", "DefinedTerm", "Definition", "GoverningSet", "compare_governing", "read", "rows", "used_in"]
