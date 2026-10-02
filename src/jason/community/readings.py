"""What a recorded document's own text says, read by mixins, one per kind of statement.

A scan's text extract carries statements the county index does not: the
recorder's stamp that names the instrument itself, the title, the
recitals that cite earlier instruments with a verb (rescinds, amends,
annexes, relies on), the units and common areas an annexation covers, the
declarant, the sections an amendment changes. Each mixin reads one kind of
statement; a ``DocumentReading`` composes them and says which kind of
document the text is. A reading is evidence, not a pin: what it proposes
(a supersession, an annexed range, a file's instrument number) is pinned
in the specification only after a person confirms it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"


class Relation(Enum):
    """How the reading document stands to an instrument it cites."""

    RESCINDS = "rescinds and supersedes"
    AMENDS = "amends"
    ANNEXES_UNDER = "annexes property under"
    RELIES_ON = "relies on"
    PLAN = "is drawn on the plan"
    MAP = "is drawn on the map"
    REFERENCES = "references"


@dataclass(frozen=True)
class Citation:
    """One earlier instrument the text names, with the date and title it gives and the verb around it."""

    number: str
    recorded: date | None
    title: str
    relation: Relation
    context: str


@dataclass(frozen=True)
class Stamp:
    """The recorder's stamp: the instrument's own number, date, page count, and fees."""

    number: str = ""
    recorded: date | None = None
    pages: int | None = None
    titles: int | None = None
    fees_cents: int | None = None
    unrecorded_copy: bool = False
    """True when the text carries the "space above this line" box and no stamp: a conformed or draft copy."""


@dataclass(frozen=True)
class AnnexedProperty:
    """What an annexation says it annexes: a unit range and the common-area designations."""

    first_unit: int | None = None
    last_unit: int | None = None
    association_common_areas: tuple[int, ...] = ()
    condominium_common_areas: tuple[int, ...] = ()


class StampReader:
    """Mixin. The recorder's stamp at the head of a recorded copy.

    Since 2018 the county prints ``Doc# 202003021215`` with the date, ``Pages 6``,
    and ``Titles 2``. Before that it printed ``BOOK 20071217 PAGE 1310``, which
    OCR breaks into pieces; the digits are gathered back. A copy that shows only
    the "space above this line for recorder's use" box was never stamped.
    """

    _DOC = re.compile(r"Doc#?\s*(\d{12})\b")
    _BOOK = re.compile(r"BOO[KO0!{\[\]]*\s*((?:\d[\s]*){8,10}?)\s*PAGE\s*((?:\d[\s]*){4})", re.I)
    _PAGES = re.compile(r"\bPages\s+(\d{1,3})\b")
    _TITLES = re.compile(r"\bTitles\s+(\d{1,2})\b")
    _WHEN = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\s+\d{1,2}:\d{2}")
    _OLD_WHEN = re.compile(r"\b(" + _MONTHS.upper() + r")\s+(\d{1,2}),\s*(\d{4})\b")
    _FEES = re.compile(r"\$\s?(\d{1,4})\s?[.,]\s?(\d{2})\b")
    _BOX = re.compile(r"SPACE ABOVE THIS LINE FOR RECORDER", re.I)

    def read_stamp(self, text: str) -> Stamp:
        head = text[:4000]
        number = ""
        hit = self._DOC.search(head)
        if hit:
            number = hit.group(1)
        else:
            book = self._BOOK.search(head)
            if book:
                digits = re.sub(r"\s+", "", book.group(1))
                page = re.sub(r"\s+", "", book.group(2))
                old = self._OLD_WHEN.search(head)
                if len(digits) == 8 and digits.startswith(("19", "20")):
                    number = digits + page
                elif old:
                    # OCR broke the book digits; the stamp's printed date is the book.
                    try:
                        day = datetime.strptime(f"{old.group(1)[:3].title()} {old.group(2)} {old.group(3)}", "%b %d %Y").date()
                        number = day.strftime("%Y%m%d") + page
                    except ValueError:
                        number = ""
        recorded = None
        when = self._WHEN.search(head)
        if when:
            try:
                recorded = date(int(when.group(3)), int(when.group(1)), int(when.group(2)))
            except ValueError:
                recorded = None
        elif number:
            try:
                recorded = date(int(number[:4]), int(number[4:6]), int(number[6:8]))
            except ValueError:
                recorded = None
        pages = self._PAGES.search(head)
        titles = self._TITLES.search(head)
        fees = None
        if number:
            amounts = [int(a) * 100 + int(b) for a, b in self._FEES.findall(head[:2500])]
            fees = max(amounts) if amounts else None
        return Stamp(
            number, recorded, int(pages.group(1)) if pages else None, int(titles.group(1)) if titles else None, fees,
            unrecorded_copy=not number and bool(self._BOX.search(head)),
        )


class TitleReader:
    """Mixin. The instrument's title: the uppercase block that follows the stamp or the fair-housing notice."""

    _TITLE = re.compile(
        r"\b((?:AMENDED AND RESTATED |RESTATED |FIRST |SECOND |THIRD |FOURTH )?"
        r"(?:DECLARATION OF ANNEXATION|DECLARATION OF COVENANTS|AMENDMENT TO|NOTICE OF|CONDOMINIUM PLAN|GRANT DEED|BY ?LAWS|ARTICLES OF INCORPORATION)"
        r"[A-Z0-9 ,&'()-]{0,160})",
    )
    _PHASE = re.compile(r"\bPHASE\s+(\d{1,2})\b", re.I)

    _STOP = re.compile(r"\b(?:If this document|NOTICE\b|RECITALS|This |TJH|NJF|\$)")

    def read_title(self, text: str) -> str:
        """OCR doubles spaces and breaks lines inside a title, so the head is flattened first."""
        head = " ".join(text[:5000].split())
        hit = self._TITLE.search(head)
        if not hit:
            return ""
        title = hit.group(1)
        stop = self._STOP.search(title)
        if stop:
            title = title[: stop.start()]
        return " ".join(title.split()).strip(" ,-")

    def read_phase(self, text: str) -> int | None:
        # The title alone: a recital names every phase and proves nothing about this one.
        title = self.read_title(text)
        hit = self._PHASE.search(title)
        if hit:
            return int(hit.group(1))
        if not title:
            return None
        head = " ".join(text[:5000].split())
        start = head.find(title)
        if start < 0:
            return None
        tail = self._PHASE.search(head[start + len(title): start + len(title) + 60])
        return int(tail.group(1)) if tail else None


class CitationReader:
    """Mixin. Earlier instruments the text cites as ``recorded on <date> as Document No. <n>``.

    The relation is read from the words before the citation: "replaced and
    rescinded", "amendment to", "annexed to the development by", "as depicted
    in the condominium plan", "final map", else a plain reference. The
    document's own stamp number is never a citation of itself.
    """

    _CITE = re.compile(
        r"(.{0,220}?)\b(?:recorded|filed|Recorded)\s+(?:on\s+)?(?:(" + _MONTHS + r")\s+(\d{1,2}),?\s+(\d{4}))?[,]?\s*as\s+(?:Document|Instrument)\s+No\.?\s*(\d{12})(?=(.{0,320}))",
        re.I | re.S,
    )

    def read_citations(self, text: str, own: str = "") -> tuple[Citation, ...]:
        found: list[Citation] = []
        seen: set[tuple[str, str]] = set()
        for before, month, day, year, number, after in self._CITE.findall(text):
            if number == own:
                continue
            context = " ".join(before.split())
            title = _cited_title(context)
            relation = _relation(context, " ".join(after.split()))
            key = (number, relation.value)
            if key in seen:
                continue
            seen.add(key)
            recorded = None
            if month and day and year:
                try:
                    recorded = datetime.strptime(f"{month[:3]} {day} {year}", "%b %d %Y").date()
                except ValueError:
                    recorded = None
            found.append(Citation(number, recorded, title, relation, context[-200:]))
        return tuple(found)


class AnnexationReader:
    """Mixin. The property an annexation annexes: ``Units 48 through 57`` and the ``A.C.A.`` and ``C.C.A.`` numbers."""

    _UNITS = re.compile(r"\bUnits?\s+(\d{1,3})\s+through\s+(\d{1,3})\b", re.I)
    _ACA = re.compile(r"\b(A\.?\s?C\.?\s?A\.?|C\.?\s?C\.?\s?A\.?)\s*(\d{1,2})\b")

    def read_annexed(self, text: str) -> AnnexedProperty:
        body = text[:8000]
        units = self._UNITS.search(body)
        first = last = None
        if units:
            first, last = int(units.group(1)), int(units.group(2))
            if last < first:
                last = None  # OCR dropped a digit; the range is left open rather than wrong
        aca: list[int] = []
        cca: list[int] = []
        window = body[max(0, units.start() - 400): units.end() + 400] if units else body
        for kind, number in self._ACA.findall(window):
            target = aca if kind.replace(".", "").replace(" ", "").upper() == "ACA" else cca
            if int(number) not in target:
                target.append(int(number))
        return AnnexedProperty(first, last, tuple(aca[:1]), tuple(cca[:1]))


class DeclarantReader:
    """Mixin. Who made the instrument: ``is made by <name> ... ("Declarant")``."""

    _MADE_BY = re.compile(r"is made by\s+(.{3,160}?)\s*\(\s*[\"“]?Declarant", re.I | re.S)

    def read_declarant(self, text: str) -> str:
        hit = self._MADE_BY.search(text[:12000])
        return " ".join(hit.group(1).split()).strip(" ,") if hit else ""


class SectionReader:
    """Mixin. The sections an amendment says it changes: ``Section 4.2 is amended``, ``Article VII``."""

    _SECTION = re.compile(r"\bSection\s+(\d+(?:\.\d+)*)\b[^.]{0,80}?\b(?:is|are|shall be)\s+(?:hereby\s+)?(?:amended|deleted|added|replaced|restated)", re.I)

    def read_sections(self, text: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(self._SECTION.findall(text)))


class AdoptionReader:
    """Mixin. When a board or the members adopted the instrument, and whether the copy is signed.

    ``Adopted Aug 30, 2022``, ``adopted by the Board of Directors on ...``, and
    ``duly adopted`` name the adoption; ``effective on the date of adoption``
    says the effective date is that one. A ``DATED: ______, 2023`` line with
    the blank still in it is an unsigned draft.
    """

    _DATE = r"((?:" + _MONTHS + r")\.?\s+\d{1,2},?\s+\d{4})"
    _ADOPTED = re.compile(r"\b(?:adopted|approved)\b[^.]{0,80}?\b(?:on\s+)?" + _DATE, re.I)
    _ADOPTED_SHORT = re.compile(r"\bAdopted\s+" + _DATE, re.I)
    _EFFECTIVE = re.compile(r"\beffective\s+(?:on\s+)?(the date of adoption|(?:" + _MONTHS + r")\.?\s+\d{1,2},?\s+\d{4})", re.I)
    _UNSIGNED = re.compile(r"DATED:?\s*_{3,}", re.I)

    def read_adopted(self, text: str) -> date | None:
        for pattern in (self._ADOPTED_SHORT, self._ADOPTED):
            hit = pattern.search(text)
            if hit:
                try:
                    raw = hit.group(1).replace(".", "").replace(",", "")
                    month, day, year = raw.split()
                    return datetime.strptime(f"{month[:3]} {day} {year}", "%b %d %Y").date()
                except ValueError:
                    continue
        return None

    def read_effective(self, text: str) -> str:
        hit = self._EFFECTIVE.search(text)
        return " ".join(hit.group(1).split()) if hit else ""

    def read_unsigned(self, text: str) -> bool:
        return bool(self._UNSIGNED.search(text))


class DocumentKindGuess(Enum):
    ANNEXATION = "annexation"
    DECLARATION = "declaration"
    AMENDMENT = "amendment"
    CONDOMINIUM_PLAN = "condominium plan"
    DEED = "deed"
    BYLAWS = "bylaws"
    ARTICLES = "articles"
    NOTICE = "notice"
    OTHER = "other"


@dataclass(frozen=True)
class DocumentReading:
    """Everything the mixins read from one text, and the kind the title implies."""

    path: Path
    kind: DocumentKindGuess
    title: str
    stamp: Stamp
    phase: int | None
    citations: tuple[Citation, ...]
    annexed: AnnexedProperty
    declarant: str
    sections: tuple[str, ...]
    text_length: int
    adopted: date | None = None
    effective: str = ""
    unsigned: bool = False

    @property
    def number(self) -> str:
        return self.stamp.number

    @property
    def supersedes(self) -> tuple[Citation, ...]:
        return tuple(c for c in self.citations if c.relation is Relation.RESCINDS)

    @property
    def amends(self) -> tuple[Citation, ...]:
        return tuple(c for c in self.citations if c.relation is Relation.AMENDS)

    @property
    def readable(self) -> bool:
        """False for an image-only extract, which holds only the file's header line."""
        return self.text_length > 400


class Reader(StampReader, TitleReader, CitationReader, AnnexationReader, DeclarantReader, SectionReader, AdoptionReader):
    """The composed reader. ``read`` runs every mixin over one text."""

    def read(self, text: str, path: Path | str = "") -> DocumentReading:
        stamp = self.read_stamp(text)
        title = self.read_title(text)
        return DocumentReading(
            Path(path), _kind(title, text), title, stamp, self.read_phase(text),
            self.read_citations(text, own=stamp.number), self.read_annexed(text), self.read_declarant(text),
            self.read_sections(text), len(text), self.read_adopted(text), self.read_effective(text), self.read_unsigned(text),
        )


def read_document(path: Path | str) -> DocumentReading:
    """Read one text extract on disk."""
    target = Path(path)
    return Reader().read(target.read_text(encoding="utf-8", errors="ignore"), target)


def read_folder(*folders: Path | str, suffixes: tuple[str, ...] = (".md", ".txt")) -> tuple[DocumentReading, ...]:
    """Read every text extract under the folders, in name order."""
    found: list[DocumentReading] = []
    for folder in folders:
        root = Path(folder)
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in suffixes:
                found.append(read_document(path))
    return tuple(found)


@dataclass(frozen=True)
class Proposal:
    """A supersession the readings state, to be pinned in the specification or already pinned."""

    number: str
    superseded_by: str
    phase: int | None
    source: str
    pinned: bool


def proposed_supersessions(readings: tuple[DocumentReading, ...], pinned: tuple = ()) -> tuple[Proposal, ...]:
    """Every "rescinds and supersedes" statement, with whether the specification already pins it."""
    known = {(fact.number, fact.superseded_by) for fact in pinned}
    found: list[Proposal] = []
    seen: set[tuple[str, str]] = set()
    for reading in readings:
        if not reading.number:
            continue
        for cite in reading.supersedes:
            key = (cite.number, reading.number)
            if key in seen:
                continue
            seen.add(key)
            found.append(Proposal(cite.number, reading.number, reading.phase, f"{reading.title or reading.path.name} ({reading.number})", key in known))
    return tuple(found)


def numbers_on_disk(readings: tuple[DocumentReading, ...]) -> dict[str, Path]:
    """Instrument number to the recorded copy on disk, by the stamp the copy carries."""
    return {reading.number: reading.path for reading in readings if reading.number}


def _cited_title(context: str) -> str:
    """The instrument name the sentence gives before "recorded": the last capitalized run."""
    hit = re.search(r"((?:[A-Z][A-Za-z&',.-]*\s+(?:(?:and|of|for|to)\s+)*){2,}[A-Z][A-Za-z&',.-]*(?:,\s*Phase\s+\d+)?)\s*(?:,|which|that)?\s*$", context)
    if hit:
        return " ".join(hit.group(1).split()).strip(" ,")
    words = context.split()
    return " ".join(words[-8:])


def _relation(context: str, after: str = "") -> Relation:
    """The verb before the citation decides; a rescission stated just after it (the "Prior Declaration" recital) counts too."""
    lower = context.lower()
    tail = after.lower()[:320]
    if "rescind" in lower or "supersed" in lower or "replaced" in lower:
        return Relation.RESCINDS
    # Only the "Prior Declaration" recital, which names the rescinded instrument first and rescinds it after;
    # "replaced and rescinded the previous instrument" in a tail belongs to the citation that follows it.
    if "prior declaration" in tail and ("rescind" in tail or "supersed" in tail):
        return Relation.RESCINDS
    if "amendment to" in lower or "amended by" in lower or "amends" in lower:
        return Relation.AMENDS
    if "annexed to" in lower or "annexation" in lower:
        return Relation.ANNEXES_UNDER
    if "condominium plan" in lower:
        return Relation.PLAN
    if "final map" in lower or "book" in lower and "maps" in lower:
        return Relation.MAP
    if "with respect to" in lower or "pursuant to" in lower or "subject to" in lower:
        return Relation.RELIES_ON
    return Relation.REFERENCES


def _kind(title: str, text: str) -> DocumentKindGuess:
    upper = " ".join((title or text[:3000]).split()).upper()
    if title and "ANNEXATION" in upper:
        return DocumentKindGuess.ANNEXATION
    if "AMENDMENT TO" in upper:
        return DocumentKindGuess.AMENDMENT
    if "DECLARATION OF COVENANTS" in upper:
        return DocumentKindGuess.DECLARATION
    if "DECLARATION OF ANNEXATION" in upper:
        return DocumentKindGuess.ANNEXATION
    if "CONDOMINIUM PLAN" in upper:
        return DocumentKindGuess.CONDOMINIUM_PLAN
    if "GRANT DEED" in upper or "QUITCLAIM" in upper:
        return DocumentKindGuess.DEED
    if "BYLAWS" in upper or "BY LAWS" in upper or "BY-LAWS" in upper:
        return DocumentKindGuess.BYLAWS
    if "ARTICLES OF INCORPORATION" in upper:
        return DocumentKindGuess.ARTICLES
    if "NOTICE OF" in upper:
        return DocumentKindGuess.NOTICE
    return DocumentKindGuess.OTHER


def reading_dict(reading: DocumentReading) -> dict[str, Any]:
    return {
        "path": str(reading.path), "kind": reading.kind.value, "title": reading.title, "readable": reading.readable,
        "number": reading.number, "recorded": reading.stamp.recorded.isoformat() if reading.stamp.recorded else "",
        "pages": reading.stamp.pages, "titles": reading.stamp.titles, "feesCents": reading.stamp.fees_cents,
        "unrecordedCopy": reading.stamp.unrecorded_copy, "phase": reading.phase, "declarant": reading.declarant,
        "annexed": {"firstUnit": reading.annexed.first_unit, "lastUnit": reading.annexed.last_unit,
                    "associationCommonAreas": list(reading.annexed.association_common_areas),
                    "condominiumCommonAreas": list(reading.annexed.condominium_common_areas)},
        "citations": [{"number": c.number, "recorded": c.recorded.isoformat() if c.recorded else "", "title": c.title, "relation": c.relation.value} for c in reading.citations],
        "sections": list(reading.sections),
        "adopted": reading.adopted.isoformat() if reading.adopted else "",
        "effective": reading.effective,
        "unsigned": reading.unsigned,
    }


_unused = field  # the dataclass field import stays for readers who extend the records
