"""The association's books: a closed set of keys every California common interest development shares.

A book is to the association's records what a code is to the law: ``decl`` is the declaration as ``CIV`` is the Civil
Code. Each key cites the section of the Davis-Stirling Act that defines it or requires it (verified against the text in
``data/authorities``), so an address (``jason.community.addresses``) names the same kind of record in every association:

- **Living books** are amended in place and cited by section: ``decl``, ``arts``, ``bylaws``, ``rules``, ``elec``,
  ``disc``, ``coll``, ``arch``, ``plan``. A version is the text in force from a day (``decl@2023-12-06``), or a stage
  that is not in force (``rules@proposed-2026-11-01``, ``jason.community.revisions``).
- **Series books** are one record per item and cited by the item: a resolution by its number (``res/20990101-1``),
  minutes and agendas by the meeting's day, a budget or policy statement by its fiscal year, a recorded instrument by
  the county's document number.
- **Restricted books** hold what Civil Code 5200 and 5215 let the association withhold or keep from copying:
  executive-session minutes (``exec``), the membership list (``members``), and election materials (``ballots``). A read
  of one is refused unless the caller asks with ``private=True``; the refusal names the statute.
- **The governing documents as a set** (``gov``) are the Act's group (CIV 4150: "the declaration and any other
  documents, such as bylaws, operating rules, articles of incorporation, or articles of association"). A community's
  own documents may define "the Governing Documents" more broadly; that set is profile data
  (``Community.governing_set()``, ``jason.community.definitions``), and the difference is reported, never resolved.
- **The manual** (``manual``) is the one key outside the Act: an owner's guide that reprints the operating rules. It is
  not a governing document; a rule it reprints is cited in ``rules``, which control.

Names come in three layers. The **keys** are the statute's terms, the same for any association. The **canon**
(``CANON``) is the common names any profile's documents use for a book ("CC&Rs", "By-Laws", "Rules and Regulations"),
matched without regard to case or punctuation (``book_named``); it names no association. A **community's own names**
are profile data: the name its documents cite a book by (``BookEntry.cite_as``, the citation form) and the terms its
documents define (``Community.defined_terms()``).

Which of the association's documents fills which book is profile data: ``Community.book_entries()`` returns
``BookEntry`` rows (``ccrs`` -> ``decl``; a parking rules document -> a part of ``rules``). A part is a separately adopted
document inside one book (``rules.parking``): every operating rule shares one definition (4340(a)), one procedure (4360),
and one rank (4205(d)), but each adopted document numbers its own sections, so a part keeps their numbers apart. A
document no row maps is still addressed by its own key (``jason://ccrs/4.15(a)``): the document keys stay aliases.

Pure records: nothing here reads disk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from jason.community.symbols import AssociationRecord, DocumentKind


class Shape(Enum):
    LIVING = "living"        # amended in place; cited by section
    SERIES = "series"        # one record per item; cited by the item
    GROUP = "group"          # a set of books (the governing documents)


@dataclass(frozen=True)
class BookInfo:
    title: str
    statute: str                         # the section that defines or requires it, as ``jason cite`` reads it
    shape: Shape
    item: str = ""                       # what names one record of a series ("the meeting's day")
    record: AssociationRecord | None = None     # the Civil Code 5200 record kind it is
    restricted: str = ""                 # the statute that lets the association withhold it; empty when open
    kinds: tuple[DocumentKind, ...] = ()        # the document kinds that are this book unless a profile says otherwise
    note: str = ""


class Book(Enum):
    """The closed set. The value is the key an address prints."""

    DECL = "decl"
    ARTS = "arts"
    BYLAWS = "bylaws"
    RULES = "rules"
    ELEC = "elec"
    DISC = "disc"
    COLL = "coll"
    ARCH = "arch"
    PLAN = "plan"
    RES = "res"
    MIN = "min"
    AGENDA = "agenda"
    EXEC = "exec"
    BUDGET = "budget"
    APS = "aps"
    RSV = "rsv"
    INSP = "insp"
    TAX = "tax"
    FIN = "fin"
    CONTRACT = "contract"
    INST = "inst"
    MEMBERS = "members"
    BALLOTS = "ballots"
    GOV = "gov"                  # the governing documents as a set (CIV 4150)
    MANUAL = "manual"            # not a governing document: an owner's guide that reprints the rules

    @property
    def info(self) -> BookInfo:
        return INFO[self]

    @property
    def governing(self) -> bool:
        """A governing document's book (4150): its words bind. The manual's words are a guide; the rules control."""
        return self.info.record is R_GOVERNING

    @property
    def living(self) -> bool:
        return INFO[self].shape is Shape.LIVING

    @property
    def restricted(self) -> str:
        return INFO[self].restricted


_L, _S = Shape.LIVING, Shape.SERIES
R = AssociationRecord

INFO: dict[Book, BookInfo] = {
    Book.DECL: BookInfo("the declaration", "CIV 4135", _L, record=R.GOVERNING_DOCUMENTS,
                        kinds=(DocumentKind.DECLARATION,),
                        note="the document, however denominated, with what 4250 and 4255 require; an amendment takes "
                             "effect on recording (4270(a)); an annexation (a supplementary declaration) is a part of it"),
    Book.ARTS: BookInfo("the articles of incorporation", "CIV 4150", _L, record=R.GOVERNING_DOCUMENTS,
                        kinds=(DocumentKind.ARTICLES,), note="a governing document by 4150; its statement is 4280"),
    Book.BYLAWS: BookInfo("the bylaws", "CIV 4150", _L, record=R.GOVERNING_DOCUMENTS, kinds=(DocumentKind.BYLAWS,),
                          note="a governing document by 4150; they yield to the declaration and articles (4205(c))"),
    Book.RULES: BookInfo("the operating rules", "CIV 4340(a)", _L, record=R.GOVERNING_DOCUMENTS,
                         kinds=(DocumentKind.OPERATING_RULES,),
                         note="a regulation the board adopts that applies generally; a rule change is noticed (4360) "
                              "when its subject is in 4355(a); separately adopted rules are parts (rules.parking)"),
    Book.ELEC: BookInfo("the election rules", "CIV 5105(a)", _L, record=R.GOVERNING_DOCUMENTS,
                        kinds=(DocumentKind.ELECTION_RULES,),
                        note="operating rules the association must adopt for its elections; kept as their own book"),
    Book.DISC: BookInfo("the discipline policy and schedule of monetary penalties", "CIV 5850(a)", _L,
                        record=R.GOVERNING_DOCUMENTS,
                        note="the schedule goes out in the annual policy statement (5310(a)(8))"),
    Book.COLL: BookInfo("the assessment collection policy", "CIV 5310(a)(6)", _L, record=R.GOVERNING_DOCUMENTS,
                        note="the statement of collection policies 5730 requires, in the annual policy statement"),
    Book.ARCH: BookInfo("the architectural review procedure", "CIV 4765(a)(1)", _L, record=R.GOVERNING_DOCUMENTS,
                        note="the procedure for approving a physical change, included in the governing documents"),
    Book.PLAN: BookInfo("the condominium plan and maps", "CIV 4120", _L, kinds=(DocumentKind.CONDOMINIUM_PLAN,
                                                                               DocumentKind.MAP),
                        note="a plan described in 4285: a description or survey map, and a three-dimensional "
                             "description"),
    Book.RES: BookInfo("the board's resolutions", "CIV 5200(a)(8)", _S, "the resolution's number", None,
                       kinds=(DocumentKind.RESOLUTION,),
                       note="no section defines a resolution: it is the board's act at a meeting, which the minutes "
                            "record; one that applies generally may also be an operating rule (4340(a))"),
    Book.MIN: BookInfo("the minutes of meetings", "CIV 5200(a)(8)", _S, "the meeting's day", R.MINUTES,
                       kinds=(DocumentKind.MINUTES,),
                       note="a draft is available within 30 days (4950(a)); executive-session minutes are exec"),
    Book.AGENDA: BookInfo("the agendas of meetings", "CIV 5200(a)(8)", _S, "the meeting's day", R.MINUTES,
                          kinds=(DocumentKind.AGENDA,), note="the notice of a board meeting contains it (4920(d))"),
    Book.EXEC: BookInfo("the minutes of executive sessions", "CIV 4935(e)", _S, "the meeting's day", None,
                        restricted="CIV 5215(a)(5)(D)", kinds=(DocumentKind.EXECUTIVE_SESSION,),
                        note="excluded from the association records by 5200(a)(8); the matter is generally noted in "
                             "the next open meeting's minutes (4935(e))"),
    Book.BUDGET: BookInfo("the annual budget report", "CIV 5300(a)", _S, "the fiscal year", R.FINANCIAL_DISCLOSURE,
                          kinds=(DocumentKind.BUDGET,)),
    Book.APS: BookInfo("the annual policy statement", "CIV 5310(a)", _S, "the fiscal year", R.FINANCIAL_DISCLOSURE),
    Book.RSV: BookInfo("the reserve study", "CIV 5550(a)", _S, "the study's year", R.FINANCIAL_DISCLOSURE,
                       kinds=(DocumentKind.RESERVE_STUDY,)),
    Book.INSP: BookInfo("the inspector's reports on exterior elevated elements", "CIV 5200(a)(15)", _S,
                        "the report's day", R.ELEVATED_ELEMENT_REPORT, note="compiled under 5551"),
    Book.TAX: BookInfo("the tax returns", "CIV 5200(a)(6)", _S, "the tax year", R.TAX_RETURN,
                       kinds=(DocumentKind.TAX_RETURN,)),
    Book.FIN: BookInfo("the interim financial statements", "CIV 5200(a)(3)", _S, "the period", R.INTERIM_FINANCIAL,
                       kinds=(DocumentKind.FINANCIAL_STATEMENT,)),
    Book.CONTRACT: BookInfo("the executed contracts", "CIV 5200(a)(4)", _S, "the contract's name", R.EXECUTED_CONTRACT,
                            kinds=(DocumentKind.CONTRACT,)),
    Book.INST: BookInfo("the recorded instruments", "CIV 4270(a)(3)", _S, "the county's document number",
                        note="no section defines a recorded instrument; an amendment of the declaration is effective "
                             "once recorded (4270(a)(3)), so its document number is the version's evidence"),
    Book.MEMBERS: BookInfo("the membership list", "CIV 5200(a)(9)", _S, "the list's day", R.MEMBERSHIP_LIST,
                           restricted="CIV 5215(a)(4)", kinds=(DocumentKind.MEMBERSHIP_LIST,),
                           note="names and addresses: a member may opt out of sharing (5220); personal identification "
                                "information may be withheld (5215(a)(5)(C))"),
    Book.BALLOTS: BookInfo("the association election materials", "CIV 5200(c)", _S, "the election's day",
                           R.ELECTION_MATERIALS, restricted="CIV 5200(c)", kinds=(DocumentKind.BALLOT,),
                           note="signed voter envelopes may be inspected but not copied (5200(c)); in the inspector's "
                                "custody until the challenge period ends (5125)"),
    Book.GOV: BookInfo("the governing documents", "CIV 4150", Shape.GROUP, record=R.GOVERNING_DOCUMENTS,
                       note="the declaration and any other documents, such as bylaws, operating rules, and articles, "
                            "which govern the operation of the development or association: a list, not a closed set"),
    Book.MANUAL: BookInfo("the owner's manual", "", _L,
                          note="not a governing document and not in the Act: a guide for owners that reprints the "
                               "operating rules; a citation of a rule cites rules, which control"),
}
del R
R_GOVERNING = AssociationRecord.GOVERNING_DOCUMENTS

KEYS: dict[str, Book] = {b.value: b for b in Book}

# The books CIV 4150 names among the governing documents ("such as": not a closed list). Election rules are operating
# rules (5105(a)), so they are rules here too.
STATUTE_GOVERNING: tuple[Book, ...] = (Book.DECL, Book.ARTS, Book.BYLAWS, Book.RULES)

# The common names of a book, any association's (matched by ``book_named`` without case or punctuation). A profile's
# own documents may use others: those are its aliases (``CitableDocument.aliases``), not the canon.
CANON: dict[Book, tuple[str, ...]] = {
    Book.DECL: ("CC&Rs", "CC&R's", "CCRs", "CC & Rs", "Covenants, Conditions and Restrictions",
                "Declaration of Covenants, Conditions and Restrictions", "Declaration", "Restated Declaration",
                "Master Declaration"),
    Book.BYLAWS: ("Bylaws", "By-Laws", "By-laws"),
    Book.ARTS: ("Articles", "Articles of Incorporation"),
    Book.RULES: ("Rules", "Rules and Regulations", "Operating Rules", "Association Rules", "House Rules"),
    Book.ELEC: ("Election Rules", "Election and Voting Rules", "Election Procedures"),
    Book.DISC: ("Fine Schedule", "Schedule of Monetary Penalties", "Schedule of Fines", "Enforcement Policy",
                "Discipline Policy"),
    Book.COLL: ("Collection Policy", "Assessment Collection Policy", "Delinquent Assessment Policy"),
    Book.ARCH: ("Architectural Guidelines", "Architectural Review Procedure", "Architectural Standards"),
    Book.PLAN: ("Condominium Plan", "Condo Plan"),
    Book.APS: ("Annual Policy Statement",),
    Book.BUDGET: ("Annual Budget Report", "Pro Forma Budget"),
    Book.RSV: ("Reserve Study",),
    Book.GOV: ("Governing Documents",),
}


def normalize_name(text: str) -> str:
    """A name with case, spacing, and punctuation dropped: "CC & R's" and "CCRs" are one name."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower().replace("'s", "s").replace("’s", "s"))


_CANON_INDEX: dict[str, Book] = {normalize_name(n): b for b, names in CANON.items() for n in names}


def book_named(name: str) -> Book | None:
    """The book a common name means ("CC&R's" -> decl, "By-Laws" -> bylaws), or a key ("decl"); None otherwise."""
    if name in KEYS:
        return KEYS[name]
    return _CANON_INDEX.get(normalize_name(name))


class Role(Enum):
    """What a document is to its book."""

    TEXT = "text"                # the book's text (or a part's)
    AMENDMENT = "amendment"      # an instrument that amends it: a version, not a part
    SUPPLEMENT = "supplement"    # a supplementary declaration (an annexation): a part


@dataclass(frozen=True)
class BookEntry:
    """One profile document in a book. ``part`` names a separately adopted document inside the book ("parking" for
    ``rules.parking``); empty for the book's main text."""

    document: str                # the document key (an outline or living document key)
    book: Book
    part: str = ""
    role: Role = Role.TEXT
    note: str = ""               # why it goes here (a decision a person may revisit)
    cite_as: str = ""            # the name the community's documents cite the book by ("CC&Rs"): the citation form
                                 # when the document's own row gives none

    @property
    def key(self) -> str:
        """The address key: ``rules`` or ``rules.parking``."""
        return f"{self.book.value}.{self.part}" if self.part else self.book.value


def entries_of(community: Any) -> tuple[BookEntry, ...]:
    try:
        return tuple(getattr(community, "book_entries", lambda: ())())
    except Exception:
        return ()


def split_key(key: str) -> tuple[Book | None, str]:
    """``rules.parking`` -> (Book.RULES, "parking"); a key outside the set -> (None, the key)."""
    head, _, part = (key or "").partition(".")
    book = KEYS.get(head)
    return (book, part) if book is not None else (None, key)


class Books:
    """The profile's mapping, read both ways: an address key to its document, and a document to its address key."""

    def __init__(self, entries: Iterable[BookEntry]):
        self.entries = tuple(entries)
        self._by_key: dict[str, str] = {}
        self._by_doc: dict[str, BookEntry] = {}
        for e in self.entries:
            self._by_doc.setdefault(e.document, e)
            if e.role is not Role.AMENDMENT:
                self._by_key.setdefault(e.key, e.document)

    @classmethod
    def of(cls, community: Any) -> Books:
        return cls(entries_of(community))

    def document(self, key: str) -> str:
        """The document an address key names (``decl`` -> ``ccrs``); a key no row maps stands for itself (an alias:
        the document's own key)."""
        return self._by_key.get(key, key)

    def entry(self, document: str) -> BookEntry | None:
        return self._by_doc.get(document)

    def key(self, document: str) -> str:
        """The address key for a document (``ccrs`` -> ``decl``); its own key when no row maps it, and the amended
        book's key for an amendment."""
        e = self._by_doc.get(document)
        return e.key if e is not None else document

    def book(self, key_or_document: str) -> Book | None:
        """The book an address key or a document key belongs to."""
        book, _ = split_key(key_or_document)
        if book is not None:
            return book
        e = self._by_doc.get(key_or_document)
        return e.book if e is not None else None

    def restricted(self, key_or_document: str) -> str:
        book = self.book(key_or_document)
        return book.restricted if book is not None else ""

    def cite_as(self, document: str) -> str:
        e = self._by_doc.get(document)
        return e.cite_as if e is not None else ""

    def named(self, name: str) -> str:
        """The document a common name means for this profile ("CC&R's" -> the declaration's document); empty when the
        name is not in the canon or no document fills its book."""
        book = book_named(name)
        if book is None:
            return ""
        doc = self.document(book.value)
        return doc if doc != book.value or doc in self._by_doc else ""

    def governing(self) -> tuple[BookEntry, ...]:
        """The profile's documents in the books CIV 4150 names."""
        return tuple(e for e in self.entries if e.book in STATUTE_GOVERNING and e.role is not Role.AMENDMENT)

    def amendments(self, key: str) -> tuple[BookEntry, ...]:
        return tuple(e for e in self.entries if e.role is Role.AMENDMENT and e.key == key)

    def table(self) -> list[dict[str, Any]]:
        """Each book with its statute and the profile's documents in it."""
        out = []
        for b in Book:
            docs = [{"document": e.document, "key": e.key, "role": e.role.value, "note": e.note}
                    for e in self.entries if e.book is b]
            out.append({"key": b.value, "title": b.info.title, "statute": b.info.statute, "shape": b.info.shape.value,
                        "item": b.info.item, "restricted": b.info.restricted, "documents": docs})
        return out


def default_book(kind: DocumentKind | str | None) -> Book | None:
    """The book a document kind is unless a profile says otherwise; None for a kind the statute leaves open (a
    policy: discipline, collection, or a rule, by what it does)."""
    try:
        kind = DocumentKind(kind) if kind else None
    except ValueError:
        return None
    for b in Book:
        if kind in b.info.kinds:
            return b
    if kind is DocumentKind.ANNEXATION or kind is DocumentKind.AMENDMENT:
        return Book.DECL
    return None


__all__ = ["Book", "BookEntry", "BookInfo", "Books", "CANON", "INFO", "KEYS", "Role", "STATUTE_GOVERNING", "Shape",
           "book_named", "default_book", "entries_of", "normalize_name", "split_key"]
