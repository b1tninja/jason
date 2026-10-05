"""A file split into the documents it holds, and a document into the parts that matter on their own.

One scan is often several documents: a stack of recorded instruments, a board packet (minutes, invoices, reports), a
vendor's batch, a records book. And one document holds parts that are cited on their own: the owner's manual holds the
rules and regulations, policies, forms, and exhibits; a declaration its exhibits; a packet its minutes. This module
reads both from the pages, as readings:

- a **Segment** is a page range of the source file, with its kind, title, date, and parties, and which readers said
  it starts there (``rules`` over the page cues, ``model`` the vision model, ``embedding`` a change in what the pages
  talk about). Two readers agreeing make a boundary ``LIKELY``; one alone is only ``SUGGESTED`` (the tiers of
  ``ocr_correct.Tier``, for the same reason: independent readers are the confidence);
- a **Part** is a titled page range inside a segment, with the heading it starts at (its outline anchor, found again in
  any other text of the same document), how it was found (a bookmark, a running header, a title, an exhibit label, a
  contents page), and the book its title names where the canon says so (``books.book_named``: "Rules and Regulations"
  is ``rules``).

A segment or a part is a *reading*, never an edit: the source file is not split or rewritten, and a segment is a page
range of it, addressed ``library:ID#p3-7`` (``#seg=N`` for the N-th segment, ``#part=SLUG`` for a part;
``address``/``parse_address``). A boundary the readers do not see stays unseen: a miss is a miss.

The rule pass is a table of **cues** (``CUES``): each a signal in the page, its weight, and which way it points. A page
starts a document when the weights of the cues it shows reach ``THRESHOLD``. Adding a signal is adding a row. The cues
are the general marks of a new document, none of them one association's: a recorder's stamp, "Page 1 of N", a numbering
that restarts, a title block, a letterhead and date, an addressee, a footer or header that changes, a page size that
changes, a closing signature or notary block on the page before, a lexical break from the page before. Blank pages are
transparent (a duplex scan's blank backs are everywhere): a page is compared with the last page that has words, and a
blank page is a weak cue, never a boundary of its own. Cues that point the other way (a page that begins in the middle
of a sentence, a page number that continues, the same running header) subtract.

This module is pure: it reads no file, no model, and no profile. ``jason.tasks.segments`` reads the PDF, runs the
models, classifies each segment's kind, and keeps the store.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
from difflib import SequenceMatcher
from enum import Enum
from typing import Any

VERSION = "2026-10-05.2"        # of the cue table and the part rules: a stored reading carries it

BLANK_CHARS = 15                # a page with fewer letters and digits than this has no words (a blank back)
HEAD_LINES = 12                 # lines kept from the top of a page
TAIL_LINES = 6                  # and from the bottom
BAND = 0.11                     # the top and bottom bands where a running header and footer sit
LEAD_CHARS = 1500               # the page's opening words, for a title, a date, and the parties
THRESHOLD = 0.8                 # the score at which a page starts a document
MODEL_THRESHOLD = 0.8           # the vision model's probability at which it says "new document" (it leans to Y: 0.5 admits twice the boundaries)
SIMILAR_HEADING = 0.8           # two header or footer lines this alike are the same line (OCR reads a line a little differently each page)

# ---------------------------------------------------------------------------------------------------------------------
# The records


class Tier(Enum):
    LIKELY = "likely"           # two independent readers agree
    SUGGESTED = "suggested"     # one reader


class Reader(Enum):
    RULES = "rules"
    MODEL = "model"
    EMBEDDING = "embedding"


@dataclass(frozen=True)
class Line:
    """One line of a page: its words, where it sits (shares of the page, 0 to 1), and how it is set."""

    text: str
    top: float
    bottom: float
    x0: float = 0.0
    x1: float = 1.0
    size: float = 0.0            # the line's type size in points, as the text layer says
    bold: bool = False

    @property
    def centered(self) -> bool:
        return abs((self.x0 + self.x1) / 2 - 0.5) < 0.06 and (self.x1 - self.x0) < 0.8

    def to_dict(self) -> dict[str, Any]:
        return {"t": self.text, "top": round(self.top, 3), "bottom": round(self.bottom, 3), "x0": round(self.x0, 3),
                "x1": round(self.x1, 3), "size": round(self.size, 1), "bold": self.bold}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Line:
        return cls(raw["t"], raw["top"], raw["bottom"], raw.get("x0", 0.0), raw.get("x1", 1.0), raw.get("size", 0.0),
                   bool(raw.get("bold")))


@dataclass
class PageInfo:
    """What the rules need of one page, so they run again without the file."""

    n: int                                       # 1-based
    width: float = 0.0
    height: float = 0.0
    source: str = "text"                         # "text" (the file's text layer), "ocr", or "none"
    chars: int = 0                               # letters and digits
    words: int = 0
    ink: float | None = None                     # share of dark pixels, measured only where there are no words
    body: float = 0.0                            # the median type size
    font: str = ""
    head: list[Line] = field(default_factory=list)
    tail: list[Line] = field(default_factory=list)
    lead: str = ""                               # the opening words, flattened
    end: str = ""                                # the closing words
    terms: list[str] = field(default_factory=list)   # the page's most frequent content words
    numbered: int = 0                            # line numbers down the margin (pleading paper), dropped from the lines

    @property
    def blank(self) -> bool:
        return self.chars < BLANK_CHARS

    @property
    def header(self) -> str:
        """The running header: the top line when it sits in the top band."""
        for line in self.head[:2]:
            if line.top < BAND and not _page_number(line.text) and _alnum(line.text) >= 4:
                return line.text
        return ""

    @property
    def footer(self) -> str:
        """The running footer: the lowest line in the bottom band that is not a page number."""
        for line in reversed(self.tail):
            if line.bottom > 1 - BAND and not _page_number(line.text) and _alnum(line.text) >= 4:
                return line.text
        return ""

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["head"] = [x.to_dict() for x in self.head]
        raw["tail"] = [x.to_dict() for x in self.tail]
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PageInfo:
        fields = dict(raw)
        fields["head"] = [Line.from_dict(x) for x in raw.get("head") or ()]
        fields["tail"] = [Line.from_dict(x) for x in raw.get("tail") or ()]
        return cls(**fields)


class PartKind(Enum):
    COVER = "cover"
    CONTENTS = "contents"
    RULES = "rules"
    POLICY = "policy"
    PROCEDURE = "procedure"
    FORM = "form"
    EXHIBIT = "exhibit"
    NOTICE = "notice"
    GUIDANCE = "guidance"
    MINUTES = "minutes"
    AGENDA = "agenda"
    REPORT = "report"
    OTHER = "other"


@dataclass(frozen=True)
class Boundary:
    """A page some reader says starts a document."""

    page: int
    tier: Tier
    readers: tuple[Reader, ...]
    score: float = 0.0                           # the rule pass's sum of cue weights
    cues: tuple[str, ...] = ()                   # the cues that fired, with their weights ("title-block+1.0")
    model: float | None = None                   # the vision model's probability that the page starts a document
    embedding: float | None = None               # cosine to the page before (lower, a bigger change)

    def to_dict(self) -> dict[str, Any]:
        return {"page": self.page, "tier": self.tier.value, "readers": [r.value for r in self.readers],
                "score": round(self.score, 3), "cues": list(self.cues),
                "model": None if self.model is None else round(self.model, 3),
                "embedding": None if self.embedding is None else round(self.embedding, 3)}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Boundary:
        return cls(raw["page"], Tier(raw["tier"]), tuple(Reader(r) for r in raw["readers"]), raw.get("score", 0.0),
                   tuple(raw.get("cues") or ()), raw.get("model"), raw.get("embedding"))


@dataclass
class Segment:
    """One document in a file: pages ``start`` to ``end`` (1-based, inclusive)."""

    key: str                                     # "s1", "s2", ... in page order
    start: int
    end: int
    title: str = ""
    kind: str = ""                               # a DocumentKind value; "" when no reader names one
    kind_basis: str = ""                         # how: "name rule", "phrase rule: ...", "local model", ""
    date: str = ""                               # ISO, the first date in its opening words
    parties: tuple[str, ...] = ()
    basis: str = ""                              # how it begins: the cues, or "first page"
    tier: Tier = Tier.SUGGESTED
    readers: tuple[Reader, ...] = ()
    confidence: float = 0.0                      # 0 to 1: the readers' own, combined
    blank_after: int = 0                         # blank pages at its end (backs, separators)

    @property
    def pages(self) -> tuple[int, int]:
        return (self.start, self.end)

    @property
    def count(self) -> int:
        return self.end - self.start + 1

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["tier"] = self.tier.value
        raw["readers"] = [r.value for r in self.readers]
        raw["parties"] = list(self.parties)
        raw["confidence"] = round(self.confidence, 3)
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Segment:
        fields = dict(raw)
        fields["tier"] = Tier(raw.get("tier", "suggested"))
        fields["readers"] = tuple(Reader(r) for r in raw.get("readers") or ())
        fields["parties"] = tuple(raw.get("parties") or ())
        return cls(**fields)


@dataclass
class Part:
    """A titled page range inside a segment (or a file): the rules inside a manual, an exhibit, a form."""

    key: str                                     # a slug, unique in the file: "rules-and-regulations"
    title: str                                   # as the page prints it
    kind: PartKind
    start: int
    end: int
    anchor: str                                  # the heading line it starts at (found again in any text of the document)
    end_anchor: str = ""                         # the next part's heading ("" at the end of the segment)
    basis: str = ""                              # "bookmark", "header run", "title", "exhibit label", "contents"
    book: str = ""                               # the book the title names (``books.book_named``), else ""
    segment: str = ""                            # the segment's key
    confidence: float = 0.0
    outline: tuple[str, ...] = ()                # the outline sections it holds, when an outline was matched to it

    @property
    def pages(self) -> tuple[int, int]:
        return (self.start, self.end)

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["kind"] = self.kind.value
        raw["outline"] = list(self.outline)
        raw["confidence"] = round(self.confidence, 3)
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Part:
        fields = dict(raw)
        fields["kind"] = PartKind(raw["kind"])
        fields["outline"] = tuple(raw.get("outline") or ())
        return cls(**fields)


@dataclass
class Segmentation:
    """Everything read about one file: the page features, every boundary any reader proposed, the segments taken from
    them, and the parts. ``sha256`` is the file's; a reading of other bytes is stale."""

    id: str
    sha256: str = ""
    name: str = ""
    page_count: int = 0
    readers: dict[str, str] = field(default_factory=dict)       # reader -> its version or model
    options: dict[str, Any] = field(default_factory=dict)       # threshold and weights used
    candidates: list[Boundary] = field(default_factory=list)    # every boundary any reader proposed
    segments: list[Segment] = field(default_factory=list)
    parts: list[Part] = field(default_factory=list)
    pages: list[PageInfo] = field(default_factory=list)
    made: str = ""

    def segment(self, key: str) -> Segment | None:
        return next((s for s in self.segments if s.key == key), None)

    def part(self, key: str) -> Part | None:
        return next((p for p in self.parts if p.key == key), None)

    def parts_of(self, *, kind: PartKind | str = "", book: str = "", segment: str = "") -> list[Part]:
        """The parts of a kind, or of a book ("rules"), or in a segment."""
        kind_value = kind.value if isinstance(kind, PartKind) else kind
        return [p for p in self.parts if (not kind_value or p.kind.value == kind_value) and (not book or p.book == book)
                and (not segment or p.segment == segment)]

    def segment_at(self, page: int) -> Segment | None:
        return next((s for s in self.segments if s.start <= page <= s.end), None)

    def part_at(self, page: int) -> Part | None:
        found = [p for p in self.parts if p.start <= page <= p.end]
        return min(found, key=lambda p: p.end - p.start) if found else None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "sha256": self.sha256, "name": self.name, "pageCount": self.page_count,
                "readers": self.readers, "options": self.options, "made": self.made,
                "candidates": [b.to_dict() for b in self.candidates],
                "segments": [s.to_dict() for s in self.segments], "parts": [p.to_dict() for p in self.parts],
                "pages": [p.to_dict() for p in self.pages]}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Segmentation:
        return cls(raw["id"], raw.get("sha256", ""), raw.get("name", ""), raw.get("pageCount", 0), raw.get("readers") or {},
                   raw.get("options") or {}, [Boundary.from_dict(b) for b in raw.get("candidates") or ()],
                   [Segment.from_dict(s) for s in raw.get("segments") or ()],
                   [Part.from_dict(p) for p in raw.get("parts") or ()],
                   [PageInfo.from_dict(p) for p in raw.get("pages") or ()], raw.get("made", ""))


# ---------------------------------------------------------------------------------------------------------------------
# Addresses: a segment or part of a stored file, in the form ``library:ID#...``


@dataclass(frozen=True)
class Address:
    id: str
    start: int = 0
    end: int = 0
    segment: str = ""
    part: str = ""

    def __str__(self) -> str:
        return address(self.id, pages=(self.start, self.end) if self.start else None, segment=self.segment, part=self.part)


def address(doc_id: str, *, pages: tuple[int, int] | None = None, segment: str = "", part: str = "") -> str:
    """``library:ID`` whole, ``library:ID#p3-7`` (``#p3`` one page), ``library:ID#seg=s2``, ``library:ID#part=SLUG``."""
    base = f"library:{doc_id}"
    if part:
        return f"{base}#part={part}"
    if segment:
        return f"{base}#seg={segment}"
    if pages and pages[0]:
        a, b = pages
        return f"{base}#p{a}" if a == b else f"{base}#p{a}-{b}"
    return base


_ADDRESS = re.compile(r"^library:(?P<id>[A-Za-z0-9_-]{1,64})(?:#(?:p(?P<a>\d+)(?:-(?P<b>\d+))?|seg=(?P<seg>[A-Za-z0-9]+)"
                      r"|part=(?P<part>[a-z0-9-]+)))?$")


def parse_address(text: str) -> Address | None:
    m = _ADDRESS.match((text or "").strip())
    if not m:
        return None
    a = int(m["a"]) if m["a"] else 0
    b = int(m["b"]) if m["b"] else a
    return Address(m["id"], a, max(a, b), m["seg"] or "", m["part"] or "")


def resolve(seg: Segmentation, addr: Address | str) -> tuple[int, int] | None:
    """The page range an address names in ``seg``; None when it names a segment or part the reading has not found."""
    if isinstance(addr, str):
        addr = parse_address(addr)
    if addr is None or addr.id != seg.id:
        return None
    if addr.part:
        p = seg.part(addr.part)
        return p.pages if p else None
    if addr.segment:
        s = seg.segment(addr.segment)
        return s.pages if s else None
    if addr.start:
        return (addr.start, addr.end) if addr.end <= max(seg.page_count, addr.end) else None
    return (1, seg.page_count) if seg.page_count else None


def slug(text: str, taken: Iterable[str] = ()) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48].strip("-") or "part"
    used = set(taken)
    out, n = base, 1
    while out in used:
        n += 1
        out = f"{base}-{n}"
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Reading a page's lines into its features


_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{3,}")
_STOP = frozenset("""this that with from have shall which will their there been were also such each other than then these
those when where into upon under more most only same any all and for are not the its has had was may must can per""".split())


def _alnum(text: str) -> int:
    return sum(c.isalnum() for c in text)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _page_number(text: str) -> bool:
    return bool(_LABEL_ONLY.fullmatch(text.strip()))


_LINE_NUMBER = re.compile(r"\d{1,2}")
_NUM = r"(?:\d{1,4}|[ivxlc]{1,6})"
_LABEL_ONLY = re.compile(rf"[-–—~•.\s]*(?:page\s*)?{_NUM}(?:\s*(?:of|/)\s*\d{{1,4}})?[-–—~•.\s]*", re.I)


def build_page(n: int, width: float, height: float, lines: Sequence[Line], *, source: str = "text", font: str = "",
               ink: float | None = None) -> PageInfo:
    """A page's features from its lines in reading order."""
    lines = [ln for ln in lines if ln.text.strip()]
    margin = [ln for ln in lines if ln.x1 < 0.2 and _LINE_NUMBER.fullmatch(ln.text.strip())]
    numbered = len(margin) if len(margin) >= 8 else 0     # pleading paper: a column of 1 to 28 down the margin
    if numbered:
        lines = [ln for ln in lines if ln not in margin]
    text = " ".join(ln.text.strip() for ln in lines)
    sizes = sorted(ln.size for ln in lines for _ in range(max(1, _alnum(ln.text) // 20)) if ln.size)
    body = sizes[len(sizes) // 2] if sizes else 0.0
    counts = Counter(w.lower() for w in _WORD.findall(text) if w.lower() not in _STOP)
    return PageInfo(n, round(width, 1), round(height, 1), source if lines else "none", _alnum(text), len(text.split()),
                    ink, round(body, 1), font, list(lines[:HEAD_LINES]), list(lines[-TAIL_LINES:]),
                    re.sub(r"\s+", " ", text)[:LEAD_CHARS], re.sub(r"\s+", " ", text)[-300:],
                    [w for w, _ in counts.most_common(60)], numbered)


# ---------------------------------------------------------------------------------------------------------------------
# Cues

# What documents call themselves, in any association: a title with one of these words, set apart, opens a document. A
# part's own words (an exhibit, the rules, a form) are PART_RULES below; they open parts, not documents.
DOC_TITLE = re.compile(
    r"\b(agreement|amendment|declaration|bylaws|by-laws|articles of|certificate|resolution|minutes|agenda|invoice|statement|"
    r"report|policy|notice|bond|deed|contract|proposal|estimate|proxy|ballot|budget|permit|application|affidavit|"
    r"memorandum|memo|order|summons|complaint|opinion|receipt|letter|lease|license|authorization|consent|petition|bid|quote|"
    r"disclosures?|summary|form|(?:superior|district|bankruptcy|supreme|municipal|appellate) court|court of appeal)\b", re.I)
TITLE_WORDS = DOC_TITLE

_RECORDING = re.compile(
    r"recording requested|when recorded|space above this line for recorder|recorder'?s? use|"
    r"\bdoc(?:ument)?\s*(?:#|no\.?|number)\s*\d{6,}", re.I)
_DATE = re.compile(
    r"\b(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}|"
    r"\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?\s+day\s+of\s+[A-Za-z]+,?\s+\d{4})", re.I)
_ADDRESSEE = re.compile(r"^\s*(dear\b|to\s*:|attn\b|attention\s*:|re\s*:|subject\s*:|from\s*:|bill to|sold to|prepared for|"
                        r"memo(?:randum)?\b)", re.I)
_CLOSING = re.compile(
    r"in witness whereof|notary public|acknowledged before me|subscribed and sworn|sincerely|respectfully|very truly|"
    r"authorized signature|signature of|^\s*by\s*:|end of (?:document|report|statement)|"
    r"remainder of (?:this )?page|intentionally left blank|total (?:due|amount)|amount due|balance due|"
    r"state of california,?\s+county of|i declare under penalty", re.I)
_CONTINUED = re.compile(r"\(\s*cont(?:inued|'d|\.)?\s*\)|\bcontinued\b\s*$", re.I)
_LABELS = (
    re.compile(r"\bpage\s*(\d{1,4})\s*of\s*(\d{1,4})\b", re.I),
    re.compile(r"^\s*(\d{1,4})\s+of\s+(\d{1,4})\s*$", re.I),
    re.compile(r"^[-–—~•\s]*(?:page\s*)?(\d{1,4})\s*[-–—~•]?\s*$", re.I),
    re.compile(r"\bpage\s*(\d{1,4})\b", re.I),
)
_ROMAN = re.compile(r"^[-–—~•\s]*([ivxl]{1,6})\s*[-–—~•]?\s*$", re.I)


@dataclass(frozen=True)
class Label:
    n: int                      # the printed page number
    total: int = 0              # "of N", when printed
    roman: bool = False


def label_of(page: PageInfo) -> Label | None:
    """The page number printed in the footer or header ("Page 3 of 9", "- 4 -", "iii"), else None."""
    for line in [*reversed(page.tail), *page.head[:3]]:
        text = line.text.strip()
        if len(text) > 40:
            continue
        for pat in _LABELS:
            m = pat.search(text)
            if m:
                # A bare number is a page number only in the margins, and only a small one; on pleading paper the
                # numbers down the margin are line numbers, not page numbers.
                if pat is _LABELS[2] and (page.numbered or not (line.bottom > 1 - BAND or line.top < BAND)):
                    continue
                n = int(m[1])
                if n > 600:
                    continue
                return Label(n, int(m[2]) if pat.groups > 1 and m.lastindex and m.lastindex >= 2 else 0)
        m = _ROMAN.match(text)
        if m and not page.numbered and (line.bottom > 1 - BAND or line.top < BAND):
            return Label(_roman(m[1]), 0, True)
    return None


def _roman(token: str) -> int:
    vals = {"i": 1, "v": 5, "x": 10, "l": 50}
    out, prev = 0, 0
    for ch in reversed(token.lower()):
        v = vals.get(ch, 0)
        out += -v if v < prev else v
        prev = max(prev, v)
    return out


def _top_lines(page: PageInfo, count: int = 10, depth: float = 0.45) -> list[Line]:
    return [ln for ln in page.head[:count] if ln.top < depth]


def _title_score(ln: Line, body: float, words: re.Pattern[str]) -> float:
    """How far a line reads as a title: set bigger than the body (0.9, 1.0 in capitals), alone in capitals (0.7), or bold
    or centered and short (0.4). A sentence is no title: long lines, and lines that end as a sentence does, are not."""
    text = ln.text.strip()
    letters = re.sub(r"[^A-Za-z]", "", text)
    count = len(text.split())
    if len(letters) < 4 or count > 12 or not words.search(text):
        return 0.0
    caps = letters.isupper()
    if ln.size and ln.size >= body * 1.25:
        return 1.0 if caps else 0.9
    if caps:
        return 0.7
    if (ln.bold or ln.centered) and count <= 8 and text[:1].isupper() and not text.endswith((".", ",", ";")):
        return 0.4
    return 0.0


def title_line(page: PageInfo, words: re.Pattern[str] | None = None) -> tuple[Line, float] | None:
    """The line that names the document (or, with ``words``, the part) the page opens with, and how sure
    (``_title_score``). The first of the best-scoring lines wins."""
    best: tuple[Line, float] | None = None
    body = page.body or 10.0
    for ln in _top_lines(page):
        score = _title_score(ln, body, words or DOC_TITLE)
        if score and (best is None or score > best[1]):
            best = (ln, score)
    return best


@dataclass(frozen=True)
class Cue:
    """A signal that a page starts a document (positive weight) or continues one (negative)."""

    key: str
    weight: float
    says: str                  # what the signal means, for the report


CUES: dict[str, Cue] = {c.key: c for c in (
    Cue("page-one", 1.5, "the page is numbered 1, or '1 of N'"),
    Cue("one-page-document", 1.0, "the page says it is page 1 of 1: a document of one page, and the next page is another"),
    Cue("page-one-again", 1.0, "the page is numbered 1 and so is the page before: a 1 cannot follow a 1"),
    Cue("numbering-reset", 1.2, "the page number restarts, or the total ('of N') changes"),
    Cue("recording-stamp", 1.5, "a recorder's stamp or request opens the page"),
    Cue("title-block", 1.0, "a title with a document-kind word, set bigger than the body, opens the page"),
    Cue("title-caps", 0.7, "a title with a document-kind word alone in capitals opens the page"),
    Cue("title-soft", 0.35, "a short bold or centered line with a document-kind word opens the page"),
    Cue("letter-head", 0.9, "a date and an addressee, or a date and a letterhead, open the page"),
    Cue("addressee", 0.5, "an addressee line ('To:', 'Dear', 'Re:') opens the page"),
    Cue("footer-change", 0.8, "a running footer stops or starts: it is not the page before's"),
    Cue("header-change", 0.6, "a running header stops or starts: it is not the page before's"),
    Cue("size-change", 0.9, "the page is not the size or orientation of the page before"),
    Cue("font-change", 0.4, "the type is not the page before's"),
    Cue("after-closing", 0.4, "the page before ends in a signature, a notary's block, or a total"),
    Cue("after-blank", 0.6, "a blank page comes before (counted only where blanks are rare: a duplex scan has them everywhere)"),
    Cue("lexical-break", 0.3, "few of the words of the page before come back"),
    Cue("embedding-change", 0.6, "the page talks of something else than the page before (the embedder's change point)"),
    Cue("mid-sentence", -1.2, "the page begins in the middle of a sentence"),
    Cue("continued", -1.2, "the page says it is a continuation ('(continued)')"),
    Cue("number-continues", -1.1, "the page number follows the page before's"),
    Cue("same-title", -0.8, "the title is the page before's: a running title, not a new document"),
    Cue("same-footer", -0.5, "the running footer is the page before's"),
    Cue("same-header", -0.6, "the running header is the page before's"),
    Cue("lexical-flow", -0.4, "many of the words of the page before come back"),
    Cue("contents-page", -1.0, "the page is a table of contents, or a leaf of one: front matter of the document before"),
    Cue("exhibit-label", -1.0, "the page opens with an exhibit or appendix label: a part of the document before"),
)}


def _ratio(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    return SequenceMatcher(None, na, nb).ratio() if na and nb else 0.0


def _same(a: str, b: str) -> bool:
    return _ratio(a, b) >= SIMILAR_HEADING


def _differs(a: str, b: str) -> bool:
    """Two lines that are not the same line read two ways: OCR varies a running line a little, so only a plain difference
    counts."""
    return bool(_norm(a) and _norm(b)) and _ratio(a, b) < 0.5


def _overlap(a: PageInfo, b: PageInfo) -> float:
    sa, sb = set(a.terms), set(b.terms)
    if not sa or not sb:
        return -1.0
    return len(sa & sb) / math.sqrt(len(sa) * len(sb))


def _sentence_open(page: PageInfo) -> bool:
    """The page begins mid-sentence: its first word, of three letters or more, is lowercase (a one or two letter glyph
    at the top is a speck the OCR read, and a list label "(a)" opens a clause, not a sentence)."""
    m = re.match(r"\W*([A-Za-z]+)", page.lead)
    return bool(m and len(m.group(1)) >= 3 and m.group(1).islower())


def _resized(a: PageInfo, b: PageInfo) -> bool:
    return bool(a.width and b.width) and (abs(a.width - b.width) / b.width > 0.05 or abs(a.height - b.height) / max(b.height, 1) > 0.05)


def _running(get: Callable[[PageInfo], str], prev2: PageInfo | None, prev: PageInfo, page: PageInfo,
             nxt: PageInfo | None) -> str:
    """"same" when a running line (header or footer) is the page before's; "change" when it differs and one of the two is
    a running line (the page before's matched the one before it, or this page's matches the next); else "" (a first line
    that differs is not a header)."""
    a, b = get(prev), get(page)
    if not (a and b):
        return ""
    if _same(a, b):
        return "same"
    if _differs(a, b) and ((prev2 is not None and _same(get(prev2), a)) or (nxt is not None and _same(get(nxt), b))):
        return "change"
    return ""


def page_cues(prev: PageInfo | None, page: PageInfo, *, embedding: float | None = None,
              weights: dict[str, float] | None = None, prev2: PageInfo | None = None,
              nxt: PageInfo | None = None) -> list[tuple[str, float, str]]:
    """The cues a page shows, as (key, weight, evidence), given the last page with words before it (None for the file's
    first), the one before that, and the next. ``embedding`` is the cosine to the page before, when an embedder read both."""
    w = {**{k: c.weight for k, c in CUES.items()}, **(weights or {})}
    out: list[tuple[str, float, str]] = []

    def fire(key: str, evidence: str = "") -> None:
        if w.get(key):
            out.append((key, w[key], evidence))

    here = label_of(page)
    before = label_of(prev) if prev else None
    if here and not here.roman and here.n == 1:
        fire("page-one", f"page {here.n}" + (f" of {here.total}" if here.total else ""))
        if here.total == 1:
            fire("one-page-document", "page 1 of 1")
        if before and not before.roman and before.n == 1:
            fire("page-one-again", "1 then 1")
    if prev and here and before and not (here.n == 1 and not here.roman):
        if here.roman == before.roman:
            if here.n < before.n:
                fire("numbering-reset", f"{before.n} then {here.n}")
            elif here.total and before.total and here.total != before.total:
                fire("numbering-reset", f"of {before.total} then of {here.total}")
            elif here.n == before.n + 1 and (here.total == before.total):
                fire("number-continues", f"{before.n} then {here.n}")
    elif prev and here and before and here.n == 1 and not here.roman and before.roman:
        fire("numbering-reset", "numbering changes style")
    stamp = _RECORDING.search(" ".join(ln.text for ln in _top_lines(page, 6, 0.4)))
    if stamp:
        fire("recording-stamp", stamp.group(0))
    title = title_line(page)
    if title:
        key = "title-block" if title[1] >= 0.9 else "title-caps" if title[1] >= 0.7 else "title-soft"
        fire(key, title[0].text.strip()[:60])
        if prev is not None and title[1] >= 0.7:
            before_title = title_line(prev)
            if before_title and _same(before_title[0].text, title[0].text):
                fire("same-title", title[0].text.strip()[:40])
    top = " | ".join(ln.text for ln in _top_lines(page, 8, 0.4))
    has_date = bool(_DATE.search(top))
    if has_date and (any(_ADDRESSEE.match(ln.text) for ln in _top_lines(page, 10, 0.5))
                     or re.search(r"@|\(\d{3}\)|\d{3}[-. ]\d{3}[-. ]\d{4}|\b(?:suite|ste|p\.?o\.? box)\b", top, re.I)):
        fire("letter-head", _DATE.search(top).group(0))
    elif any(_ADDRESSEE.match(ln.text) for ln in _top_lines(page, 8, 0.4)):
        fire("addressee", next(ln.text for ln in _top_lines(page, 8, 0.4) if _ADDRESSEE.match(ln.text))[:40])
    if _sentence_open(page):
        fire("mid-sentence")
    opening = " ".join(ln.text for ln in _top_lines(page, 3, 0.4))
    if prev is not None:
        if re.search(r"table of contents|^\W*contents", opening, re.I) or (_leader_page(page) and _leader_page(prev)):
            fire("contents-page")
        if any(_EXHIBIT_LINE.match(re.sub(r"\s+", " ", ln.text).strip()) for ln in _top_lines(page, 3, 0.4)):
            fire("exhibit-label")
    if any(_CONTINUED.search(ln.text) for ln in _top_lines(page, 6, 0.3)):
        fire("continued")
    if prev is not None:
        if _resized(prev, page) and (nxt is None or _resized(prev, nxt)):
            # A page of another size starts a document only if the next page keeps that size: a landscape map in
            # the middle of a document is one page, and the next goes back.
            fire("size-change", f"{prev.width:.0f}x{prev.height:.0f} then {page.width:.0f}x{page.height:.0f}")
        if page.font and prev.font and page.font != prev.font and abs((page.body or 0) - (prev.body or 0)) >= 1.5:
            fire("font-change", f"{prev.font} {prev.body} then {page.font} {page.body}")
        footer = _running(lambda p: p.footer, prev2, prev, page, nxt)
        if footer:
            fire("same-footer" if footer == "same" else "footer-change", page.footer[:40])
        header = _running(lambda p: p.header, prev2, prev, page, nxt)
        if header:
            fire("same-header" if header == "same" else "header-change", page.header[:40])
        closing = _CLOSING.search(" ".join(ln.text for ln in prev.tail[-4:])) or _CLOSING.search(prev.end[-160:])
        if closing:
            fire("after-closing", closing.group(0))
        share = _overlap(prev, page)
        if 0 <= share < 0.12:
            fire("lexical-break", f"{share:.2f}")
        elif share >= 0.45:
            fire("lexical-flow", f"{share:.2f}")
        if embedding is not None and embedding_break(embedding):
            fire("embedding-change", f"{embedding:.2f}")
    return out


EMBED_BREAK = 0.55
DUPLEX = 0.25                   # more blank pages than this share and the blanks are backs, not separators


def embedding_break(cosine: float) -> bool:
    """Whether two adjacent pages' cosine is low enough to count as a change of subject. The embedder's cosines for
    adjacent pages of one document run high; ``EMBED_BREAK`` was set on the dev set (docs/document-segmentation.md)."""
    return cosine < EMBED_BREAK


def score_pages(pages: Sequence[PageInfo], *, embeddings: dict[int, float] | None = None,
                weights: dict[str, float] | None = None) -> dict[int, tuple[float, list[tuple[str, float, str]]]]:
    """The rule pass: each page's score and cues. Blank pages are skipped: a page is read against the last page with
    words, and the first page with words is always a start. A blank page before is a cue only where blanks are rare."""
    out: dict[int, tuple[float, list[tuple[str, float, str]]]] = {}
    live = [p for p in pages if not p.blank]
    duplex = bool(pages) and (len(pages) - len(live)) / len(pages) > DUPLEX
    blank_weight = 0.0 if duplex else (weights or {}).get("after-blank", CUES["after-blank"].weight)
    for i, page in enumerate(live):
        prev = live[i - 1] if i else None
        prev2 = live[i - 2] if i > 1 else None
        nxt = live[i + 1] if i + 1 < len(live) else None
        last_blank = prev is not None and page.n - prev.n > 1
        fired = page_cues(prev, page, embedding=(embeddings or {}).get(page.n), weights=weights, prev2=prev2, nxt=nxt)
        if prev is not None and last_blank and blank_weight:
            fired.append(("after-blank", blank_weight, ""))
        score = 10.0 if prev is None else sum(wt for _, wt, _ in fired)
        out[page.n] = (score, fired)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# The readers, combined


def decide(pages: Sequence[PageInfo], *, rule_scores: dict[int, tuple[float, list[tuple[str, float, str]]]],
           model: dict[int, float] | None = None, embeddings: dict[int, float] | None = None,
           threshold: float = THRESHOLD, model_threshold: float = MODEL_THRESHOLD,
           accept: str = "any") -> list[Boundary]:
    """Every page some reader says starts a document, with the readers that agree.

    ``accept``: "any" keeps a boundary one reader proposes (tier ``SUGGESTED``) as well as two that agree (``LIKELY``);
    "agree" keeps only boundaries two readers share (the model, or the embedder, must confirm the rules); "rules" keeps
    the rule pass's alone. With no model and no embedder every boundary is the rule pass's alone."""
    out: list[Boundary] = []
    first = next((p.n for p in pages if not p.blank), 1)
    for page in pages:
        if page.blank:
            continue
        n = page.n
        score, fired = rule_scores.get(n, (0.0, []))
        readers: list[Reader] = []
        if n == first or score >= threshold:
            readers.append(Reader.RULES)
        p_model = (model or {}).get(n)
        if p_model is not None and p_model >= model_threshold and n != first:
            readers.append(Reader.MODEL)
        cos = (embeddings or {}).get(n)
        if cos is not None and embedding_break(cos) and n != first:
            readers.append(Reader.EMBEDDING)
        if n == first and not readers:
            readers.append(Reader.RULES)
        if not readers:
            continue
        # The embedder's break is itself one of the rules' cues; it is a reader of its own only when asked for apart.
        independent = {r for r in readers if r is not Reader.EMBEDDING or Reader.RULES not in readers}
        tier = Tier.LIKELY if len(independent) >= 2 or n == first else Tier.SUGGESTED
        if accept == "agree" and tier is not Tier.LIKELY:
            continue
        if accept == "rules" and Reader.RULES not in readers:
            continue
        out.append(Boundary(n, tier, tuple(readers), score, tuple(f"{k}{wt:+.1f}" for k, wt, _ in fired), p_model, cos))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Titles, dates, and parties


_MONTHS = {m: i + 1 for i, m in enumerate("january february march april may june july august september october november december".split())}


def read_date(text: str) -> str:
    """The first date in ``text`` as ISO ("October 4, 2026", "10/4/2026", "4th day of October, 2026"), or ""."""
    for m in _DATE.finditer(text or ""):
        raw = m.group(0)
        got = re.match(r"([A-Za-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", raw)
        if got and got[1][:3].lower() in {k[:3] for k in _MONTHS}:
            month = next(v for k, v in _MONTHS.items() if k[:3] == got[1][:3].lower())
            return _iso(int(got[3]), month, int(got[2]))
        got = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", raw)
        if got:
            year = int(got[3]) + (2000 if int(got[3]) < 70 and len(got[3]) == 2 else 1900 if len(got[3]) == 2 else 0)
            return _iso(year, int(got[1]), int(got[2]))
        got = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
        if got:
            return _iso(int(got[1]), int(got[2]), int(got[3]))
        got = re.match(r"(\d{1,2})(?:st|nd|rd|th)?\s+day\s+of\s+([A-Za-z]+),?\s+(\d{4})", raw, re.I)
        if got and got[2].lower() in _MONTHS:
            return _iso(int(got[3]), _MONTHS[got[2].lower()], int(got[1]))
    return ""


def _iso(year: int, month: int, day: int) -> str:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


_PARTIES = (
    re.compile(r"\bby and between\s+(?P<a>.{3,120}?)\s+(?:and|&)\s+(?P<b>.{3,120}?)(?:[,.;(]|\s+(?:a|an|the)\s)", re.I),
    re.compile(r"\bbetween\s+(?P<a>.{3,100}?)\s+(?:and|&)\s+(?P<b>.{3,100}?)(?:[,.;(]|\s+(?:a|an|the)\s)", re.I),
)
_LABELED = re.compile(r"\b(?i:from|to|bill to|sold to|prepared for|prepared by|attention|attn|vendor|payee)\s*:\s*([A-Z][^:|]{2,60}?)(?=\s{2,}|\s\||\s[A-Z][a-z]+:|$)")


def read_parties(text: str) -> tuple[str, ...]:
    """The parties the opening words name: "by and between X and Y", or labeled lines ("From:", "Bill To:"). A reading
    from patterns, with the OCR's slips, never a fact; a miss is empty."""
    flat = re.sub(r"\s+", " ", text or "")[:900]
    for pat in _PARTIES:
        m = pat.search(flat)
        if m:
            return tuple(re.sub(r"\s+", " ", m[g]).strip(" ,.;") for g in ("a", "b"))
    found = [m[1].strip(" ,.;") for m in _LABELED.finditer(flat)]
    return tuple(dict.fromkeys(found))[:3]


def read_title(page: PageInfo) -> str:
    """What the page's opening names the document: the title line, else the first line with a title word, else the first
    line of any length (the top band's running header aside)."""
    found = title_line(page)
    if found:
        return re.sub(r"\s+", " ", found[0].text).strip(" .:-")
    for ln in _top_lines(page, 8, 0.5):
        if TITLE_WORDS.search(ln.text) and len(ln.text) <= 90:
            return re.sub(r"\s+", " ", ln.text).strip(" .:-")
    for ln in page.head[:6]:
        if _alnum(ln.text) >= 6 and not _page_number(ln.text):
            return re.sub(r"\s+", " ", ln.text).strip(" .:-")[:90]
    return ""


# ---------------------------------------------------------------------------------------------------------------------
# Segments


def segments_from(pages: Sequence[PageInfo], boundaries: Sequence[Boundary], *, classify: Callable[[str, str], tuple[str, str]]
                  | None = None, text_of: Callable[[int, int], str] | None = None) -> list[Segment]:
    """The pages cut at the boundaries. A blank page belongs to the segment before it. ``classify(title, text)`` gives
    (kind, basis) and ``text_of(start, end)`` the segment's opening text; both optional."""
    by_n = {p.n: p for p in pages}
    starts = sorted(b.page for b in boundaries)
    if not starts:
        return []
    out: list[Segment] = []
    for i, start in enumerate(starts):
        end = (starts[i + 1] - 1) if i + 1 < len(starts) else (pages[-1].n if pages else start)
        page = by_n.get(start)
        b = next(b for b in boundaries if b.page == start)
        trailing = 0
        for n in range(end, start, -1):
            if by_n.get(n) and by_n[n].blank:
                trailing += 1
            else:
                break
        seg = Segment(f"s{i + 1}", start, end, basis="first page" if i == 0 else " ".join(b.cues) or "reader",
                      tier=b.tier, readers=b.readers, blank_after=trailing,
                      confidence=_confidence(b))
        if page is not None:
            seg.title = read_title(page)
            seg.date = read_date(page.lead)
            seg.parties = read_parties(page.lead)
            opening = text_of(start, min(end, start + 1)) if text_of else page.lead
            if classify is not None:
                seg.kind, seg.kind_basis = classify(seg.title, opening or page.lead)
        out.append(seg)
    return out


def _confidence(b: Boundary) -> float:
    """0 to 1 from what the readers said: the rule score over its threshold, the model's probability, agreement."""
    parts: list[float] = []
    if Reader.RULES in b.readers:
        parts.append(min(1.0, 0.5 + 0.25 * (b.score - THRESHOLD) + 0.25) if b.score < 10 else 1.0)
    if b.model is not None:
        parts.append(b.model)
    if b.embedding is not None and Reader.EMBEDDING in b.readers:
        parts.append(max(0.0, 1.0 - b.embedding))
    if not parts:
        return 0.0
    base = sum(parts) / len(parts)
    return min(1.0, base + (0.1 if b.tier is Tier.LIKELY and len(b.readers) > 1 else 0.0))


# ---------------------------------------------------------------------------------------------------------------------
# Parts

# What a part's title says it is, in the order tried. General words of governing documents and their attachments.
PART_RULES: tuple[tuple[PartKind, re.Pattern[str]], ...] = (
    (PartKind.EXHIBIT, re.compile(r"^\W*(?:exhibit|appendix|attachment|annex|schedule|addendum|enclosure)\b\s*[\"'“]?\s*[A-Z0-9]{1,4}\b", re.I)),
    (PartKind.CONTENTS, re.compile(r"\b(?:table of contents|contents|index)\b", re.I)),
    (PartKind.MINUTES, re.compile(r"\bminutes\b", re.I)),
    (PartKind.AGENDA, re.compile(r"\bagenda\b", re.I)),
    (PartKind.FORM, re.compile(r"\b(?:application|request form|request for|worksheet|form of|permit application|registration form|"
                               r"checklist|ballot|proxy)\b", re.I)),
    (PartKind.RULES, re.compile(r"\b(?:rules and regulations|rules & regulations|house rules|operating rules|election rules|"
                                r"rules|regulations)\b", re.I)),
    (PartKind.POLICY, re.compile(r"\b(?:polic(?:y|ies)|resolution)\b", re.I)),
    (PartKind.PROCEDURE, re.compile(r"\b(?:procedures?|guidelines|process)\b", re.I)),
    (PartKind.NOTICE, re.compile(r"\bnotice\b", re.I)),
    (PartKind.GUIDANCE, re.compile(r"\b(?:questions (?:and|&) answers|faq|frequently asked|guide|handbook|welcome|"
                                   r"contact information|information)\b", re.I)),
)


PART_WORDS = re.compile("|".join(f"(?:{pat.pattern})" for _, pat in PART_RULES), re.I)


def part_kind(title: str) -> PartKind | None:
    for kind, pat in PART_RULES:
        if pat.search(title):
            return kind
    return None


@dataclass(frozen=True)
class Mark:
    """A place a part may start: a bookmark, a running header run, a title, an exhibit label, a contents entry."""

    page: int
    title: str
    basis: str
    level: int = 1
    weight: float = 1.0


BASIS_WEIGHT = {"bookmark": 0.6, "exhibit label": 0.9, "title": 0.7, "header run": 0.8, "contents": 0.6, "cover": 0.6,
                "after contents": 0.6}


def header_runs(pages: Sequence[PageInfo], lo: int, hi: int) -> list[Mark]:
    """Marks where a running header begins a run that differs from the run before it ("QUESTIONS & ANSWERS" on pages
    4 to 9 and "CONTACT INFORMATION" on 10 to 12). A run of fewer than three pages is a title's work, not a running header's."""
    runs: list[tuple[int, int, str]] = []
    for page in pages:
        if not (lo <= page.n <= hi) or page.blank:
            continue
        head = page.header
        if runs and head and _same(head, runs[-1][2]):
            runs[-1] = (runs[-1][0], page.n, runs[-1][2])
        else:
            runs.append((page.n, page.n, head))
    # A running header that names no kind of part (the association's name on every page) is weak evidence.
    return [Mark(a, text, "header run", weight=1.0 if part_kind(text) else 0.45) for a, b, text in runs if text and b - a >= 2]


_EXHIBIT_LINE = re.compile(r"^\W*(?:exhibit|appendix|attachment|annex|schedule|addendum)\s*[\"'“]?\s*[A-Z0-9]{1,4}\b", re.I)


def title_marks(pages: Sequence[PageInfo], lo: int, hi: int) -> list[Mark]:
    """Marks at pages that open with a part's title: a line in the top of the page with a part word that is set big, or
    alone in capitals, bold, or centered; an exhibit label wherever it opens the page."""
    out: list[Mark] = []
    for page in pages:
        if not (lo <= page.n <= hi) or page.blank:
            continue
        first = [ln for ln in page.head[:6] if ln.top < 0.4]
        done = False
        for ln in first[:4]:
            text = re.sub(r"\s+", " ", ln.text).strip()
            if _EXHIBIT_LINE.match(text) and len(text) <= 60:
                out.append(Mark(page.n, text, "exhibit label"))
                done = True
                break
        if done:
            continue
        found = title_line(page, PART_WORDS)
        if found and part_kind(found[0].text) is not None:
            first_line = any(found[0] is ln for ln in page.head[:2])      # the first line of the page is the page's title
            out.append(Mark(page.n, re.sub(r"\s+", " ", found[0].text).strip(" .:-"), "title",
                            weight=found[1] + (0.6 if first_line else 0.0)))
    return out


_CONTENTS_LINE = re.compile(r"^(?P<title>[A-Za-z][^\d]{3,80}?)\s*(?:\.{2,}|\s{2,}|\s)\s*(?P<page>\d{1,3})\s*$")


def contents_marks(pages: Sequence[PageInfo], lo: int, hi: int, text_of: Callable[[int], list[str]] | None = None) -> list[Mark]:
    """Marks from a contents page: lines "Title ..... 12", kept only where the title is found on that page (a contents
    page's numbers are the document's own, so an offset is allowed: the first title found on pages p to p + 3).
    ``text_of(page)`` gives a page's lines (the stored head and tail otherwise)."""
    out: list[Mark] = []
    by_n = {p.n: p for p in pages}

    def lines_of(n: int) -> list[str]:
        if text_of:
            return text_of(n)
        page = by_n.get(n)
        return [ln.text for ln in (page.head + page.tail)] if page else []

    for page in pages:
        if not (lo <= page.n <= min(hi, lo + 6)):
            continue
        head_text = " ".join(ln.text for ln in page.head[:3]).lower()
        if "contents" not in head_text:
            continue
        for text in lines_of(page.n):
            m = _CONTENTS_LINE.match(text.strip())
            if not m or part_kind(m["title"]) is None:
                continue
            want, offset = int(m["page"]), None
            for n in range(want, want + 4):
                if lo <= n <= hi and any(_same(m["title"], ln) or _norm(m["title"]) in _norm(ln) for ln in lines_of(n)[:8]):
                    offset = n - want
                    break
            if offset is not None:
                out.append(Mark(want + offset, m["title"].strip(" ."), "contents"))
    return out


def bookmark_marks(toc: Sequence[Sequence[Any]], lo: int, hi: int, *, max_level: int = 1) -> list[Mark]:
    """Marks from the file's own bookmarks ([level, title, page] as PyMuPDF's ``get_toc``): those whose title names a part."""
    out: list[Mark] = []
    for entry in toc:
        level, title, page = int(entry[0]), str(entry[1]).strip().replace("​", ""), int(entry[2])
        if level <= max_level and lo <= page <= hi and part_kind(title) is not None:
            out.append(Mark(page, title, "bookmark", level))
    return out


def _same_title(a: str, b: str) -> bool:
    """The same heading read twice. Exhibit labels differ by their letter ("Exhibit A", "Exhibit B"), which a likeness
    would not see."""
    if _EXHIBIT_LINE.match(a) or _EXHIBIT_LINE.match(b):
        return _norm(a) == _norm(b)
    return _same(a, b)


COVER_WORDS = 100               # a first page with fewer words than this, before the first mark, is a cover
LEADERS = re.compile(r"(?:\.\s?){4,}")


def _leader_page(page: PageInfo | None) -> bool:
    """A contents page: dot leaders between titles and numbers on several lines."""
    return page is not None and len(LEADERS.findall(page.lead)) >= 3


def _score(m: Mark) -> float:
    """How far a mark is to be trusted: its basis, its own weight, and a bonus where the title names a kind of part."""
    return BASIS_WEIGHT.get(m.basis, 0.5) * m.weight + (0.3 if part_kind(m.title) is not None else 0.0)


def find_parts(pages: Sequence[PageInfo], segments: Sequence[Segment], *, toc: Sequence[Sequence[Any]] = (),
               text_of: Callable[[int], list[str]] | None = None, min_pages: int = 1) -> list[Part]:
    """The parts of each segment: marks from the bookmarks, running header runs, titles, exhibit labels, and a contents
    page, merged (one per page; the best evidence wins; a title that repeats on the next page is one mark), then each
    part runs to the page before the next. The front of a segment before its first mark is a cover. A contents part ends
    where its dot leaders end, and the text after it is the document's main text. One part that is the whole segment says
    nothing the segment does not, and is left out."""
    parts: list[Part] = []
    taken: list[str] = []
    by_n = {p.n: p for p in pages}
    for seg in segments:
        lo, hi = seg.start, seg.end
        marks = [*bookmark_marks(toc, lo, hi), *header_runs(pages, lo, hi), *title_marks(pages, lo, hi),
                 *contents_marks(pages, lo, hi, text_of)]
        best: dict[int, Mark] = {}
        for m in marks:
            cur = best.get(m.page)
            if cur is None or _score(m) > _score(cur):
                best[m.page] = m
        front = by_n.get(lo)
        if front is not None and not front.blank and front.words < COVER_WORDS:
            best.pop(lo, None)                            # a front page of few words is a cover, whatever its bookmarks say
        picked: list[Mark] = []
        for n in sorted(best):
            m = best[n]
            if picked and _same_title(m.title, picked[-1].title):
                continue                                  # the same title again: a continuation, not a new part
            picked.append(m)
        if not picked:
            continue
        first = by_n.get(lo)
        if picked and picked[0].page > lo and first is not None and not first.blank and first.words < COVER_WORDS:
            picked.insert(0, Mark(lo, read_title(first) or "front matter", "cover", weight=0.8))
        # A contents part ends where its leaders end; what follows, up to the next mark, is the main text.
        out: list[Mark] = []
        for i, m in enumerate(picked):
            out.append(m)
            if part_kind(m.title) is PartKind.CONTENTS or m.basis == "contents":
                nxt = picked[i + 1].page if i + 1 < len(picked) else hi + 1
                n = m.page
                while n + 1 < nxt and (_leader_page(by_n.get(n + 1)) or by_n.get(n + 1) is not None and by_n[n + 1].blank):
                    n += 1
                if _leader_page(by_n.get(m.page)) and nxt - (n + 1) > 3 and by_n.get(n + 1) is not None:
                    out.append(Mark(n + 1, read_title(by_n[n + 1]) or "main text", "after contents", weight=0.6))
        picked = sorted(out, key=lambda x: x.page)
        if len(picked) == 1 and picked[0].page == lo:
            continue
        for i, m in enumerate(picked):
            end = (picked[i + 1].page - 1) if i + 1 < len(picked) else hi
            while end > m.page and by_n.get(end) is not None and by_n[end].blank:
                end -= 1                                  # a blank back is not part of the part
            if end - m.page + 1 < min_pages:
                continue
            kind = part_kind(m.title) or (PartKind.COVER if m.basis == "cover" else PartKind.OTHER)
            if m.basis == "cover":
                kind = PartKind.COVER
            key = slug(m.title, taken)
            taken.append(key)
            parts.append(Part(key, m.title, kind, m.page, end, anchor=m.title,
                              end_anchor=picked[i + 1].title if i + 1 < len(picked) else "", basis=m.basis,
                              book=_book_of(m.title, kind), segment=seg.key,
                              confidence=round(min(1.0, _score(m)), 3) if by_n.get(m.page) else 0.3))
    return parts


def _book_of(title: str, kind: PartKind) -> str:
    """The book the title names where the canon knows it ("Rules and Regulations" is ``rules``); a rule-like part with
    no canon name stays unbooked: a miss is a miss."""
    try:
        from jason.community.books import book_named
    except Exception:  # pragma: no cover
        return ""
    candidates = [title, re.sub(r"^\W*[A-Z0-9]{1,3}[.)]\s*", "", title), re.sub(r"\b(?:the|an?|of)\b", "", title, flags=re.I)]
    for cand in candidates:
        book = book_named(cand.strip())
        if book is not None:
            return book.value
    return ""


# ---------------------------------------------------------------------------------------------------------------------
# Scoping a citation to a part


def _stream(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def part_span(part: Part, text: str) -> tuple[int, int] | None:
    """The part's characters in ``text`` (any text of the same document: the PDF's layer, an outline's, an OCR): from
    its anchor heading to its end anchor, found in the stream of letters and digits (spaces, punctuation, and case
    ignored). None where the anchor is not found: a miss, never a guess. A heading found more than once is taken at the
    first place after the previous part's, so pass the text of the segment, not the whole file, where headings repeat."""
    stream = _stream(text)
    if not stream:
        return None
    a = _stream(part.anchor)
    if len(a) < 4:
        return None
    start = stream.find(a)
    if start < 0:
        return None
    end = len(stream)
    if part.end_anchor and len(_stream(part.end_anchor)) >= 4:
        j = stream.find(_stream(part.end_anchor), start + len(a))
        if j >= 0:
            end = j
    # Map stream offsets back to offsets in ``text``.
    where = [i for i, ch in enumerate(text.lower()) if ch.isalnum() and ch in "abcdefghijklmnopqrstuvwxyz0123456789"]
    if end > len(where) or start >= len(where):
        return None
    return where[start], (where[end - 1] + 1 if end > start else where[start])


def page_of(seg: Segmentation, snippet: str, texts: Sequence[str]) -> int | None:
    """The 1-based page whose text (``texts[n-1]``) holds ``snippet``'s first twelve words, else None. For scoping a
    passage of some other reading of the file to a part."""
    words = _stream(" ".join(snippet.split()[:12]))
    if len(words) < 20:
        return None
    for n, text in enumerate(texts, start=1):
        if words in _stream(text):
            return n
    return None


def locate(seg: Segmentation, snippet: str, texts: Sequence[str]) -> tuple[int | None, str, str]:
    """Where a passage of some other reading of the file sits in this one: (page, segment key, part key), each "" or None
    when the snippet's words are not found on any page. For tagging the passage index's rows with their segment and part,
    so a search or a citation can be scoped to one."""
    page = page_of(seg, snippet, texts)
    if page is None:
        return None, "", ""
    s, p = seg.segment_at(page), seg.part_at(page)
    return page, s.key if s else "", p.key if p else ""


def in_part(part: Part, page: int | None) -> bool:
    return page is not None and part.start <= page <= part.end


__all__ = ["Address", "BAND", "Boundary", "CUES", "Cue", "Line", "Mark", "PageInfo", "Part", "PartKind", "Reader",
           "Segment", "Segmentation", "THRESHOLD", "Tier", "VERSION", "address", "build_page", "decide", "find_parts",
           "in_part", "label_of", "locate", "page_cues", "page_of", "parse_address", "part_kind", "part_span", "read_date",
           "read_parties", "read_title", "resolve", "score_pages", "segments_from", "slug", "title_line"]
