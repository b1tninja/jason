"""Check an answer's quotations and citations against the words jason stores.

A search tool returns passages and the client (a person, or a model) writes the answer. ``check`` reads that answer and
says, of each quotation, whether its words are jason's stored words, and of each citation, whether jason holds the
provision. It is the last step of "Recite the rule; label the reading": only stored words are quoted.

**A quotation** is the text between double quotation marks (straight or curly) or in a block quote (lines that open
with ``>``). One shorter than ``MIN_WORDS`` words is not checked (a term, a title), and single quotation marks are not
read as quotations. Each quotation gets a verdict:

- ``FOUND``: the words are in a stored text. ``exact`` is character for character; ``normalized`` is the same after
  folding (``fold``): whitespace, quote marks, a hyphen between letters (a word broken at a line's end), Markdown's
  emphasis marks, and capitalization. An ellipsis is allowed when each part is found, in order, in one passage or section.
- ``ALTERED``: no stored text has the words, and one has nearly those words. The stored words are shown beside the
  quoted ones with each difference marked ``[[so]]``.
- ``MISATTRIBUTED``: the answer attributes the quotation to one provision, and the words are stored only somewhere else.
- ``OTHER VERSION``: the answer attributes the quotation to a statute's section, and the words are those of another
  version of that section (earlier or later) than the one checked: the version in force on the day asked
  (``as_of``), or the words on the shelf now. The note says plainly which version the words are and that the one
  checked reads differently. A miss stays a miss: the answer is not clean.
- ``NOT FOUND``: no stored text has the words or nearly the words.

**A statute's version.** A quotation attributed to a statute is checked against one version of the section: with
``as_of``, the version in force on that day where the disk shows it (``law_text.version_on``; the version is named
with its digest and range), else the words on the shelf now. The other versions jason holds, on the shelf and in
the history (``jason law-history --versions``), are read only to say that a quotation is theirs.

**Where** the words were found is part of the answer: the file, its section, the passage, and its standing
(``passage_index.Standing``). Words found only in a page jason generated, or only on the reference shelf, are reported
with a warning: neither is the record or the law. A confidential file is named, and its words shown, only when the
caller asks for confidential files, by ``document_search``'s rule (a case catalog only when the sources name it).

**A citation** is read by the citation grammar already in use (``jason.community.cite.located_targets``, over
``references.extract``). A statute's section is looked up on the shelf (``law_readings.provision_text``, disk only), a
governing document's section through the same reader ``jason cite`` uses. Each is reported with its digest, with the
quotations the answer attributes to it, and, for a section the shelf holds in two versions under one number, both.

The folding is ``questions._norm``, the one ``prompts.verify`` uses through ``questions.grounded``, with the line-break
hyphen added. ``grounded`` itself is not the matcher here: it accepts a near match and words scattered close together
as grounded, which is right for a form's OCR and would pass an altered quotation.

Nothing here judges meaning. ``FOUND`` says the words are the stored words; it does not say the answer reads them
rightly, that they answer the question, or that they were in force on a given day. Reads only: the index is opened
read-only and nothing is fetched.
"""

from __future__ import annotations

import difflib
import json
import math
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Sequence

from jason.community import passage_index as pi
from jason.community.cite import Located, Target, Unit, label_text, located_targets
from jason.community.questions import _norm

MIN_WORDS = 4                 # a quotation with fewer words is not checked
NEAR = 0.75                   # the share of words a stored text must share, in order, to be called a near match
MAX_PLACES = 5                # the places listed for one quotation; the rest are counted
CONTEXT_CHARS = 120           # the stored words shown on each side of a quotation that was found
_ANCHORS = 10                 # the words a near-match search looks for before it aligns
_CANDIDATES = 40              # the passages it aligns
_REACH = 240                  # how far before a quotation a citation may introduce it

CAVEATS = (
    "This checks words, not meaning: FOUND says the quoted words are jason's stored words. It does not say the answer "
    "reads them rightly, that they answer the question, or that they were in force on a given day.",
    f"Only double quotation marks and block quotes are read as quotations, and one shorter than {MIN_WORDS} words is "
    "not checked. A paraphrase, a figure, or a date outside quotation marks is not checked at all.",
    "The stored words are jason's copies: a scan's OCR can misread, and a consolidated governing text is not an "
    "official restatement. A statute's quotation is checked against one version of the section: the version in force "
    "on the day asked (as_of), where the disk shows it, else the words on the shelf now; the other versions jason "
    "holds are read only to say that a quotation is theirs (OTHER VERSION).",
    "A quotation found only in a page (jason's own summary) or on the reference shelf is not the record or the law: "
    "quote the record or the law it points to.",
    "An attribution is read from where the citation sits: the one that introduces the quotation in its sentence, or "
    "follows it directly. Read the sentence before relying on MISATTRIBUTED.",
)


class Verdict(Enum):
    FOUND = "found"
    ALTERED = "altered"
    MISATTRIBUTED = "misattributed"
    OTHER_VERSION = "other version"      # a statute's words, of a version other than the one checked
    NOT_FOUND = "not found"


class Match(Enum):
    EXACT = "exact"                      # character for character
    NORMALIZED = "normalized"            # the same after ``fold``


# --- Folding ------------------------------------------------------------------------------------------------------------

_LETTER = r"[^\W\d_]"
_HYPHEN = re.compile(rf"(?<={_LETTER})[-\u00ad]\s*(?={_LETTER})")
_STEP = re.compile(rf"(?P<hyphen>(?<={_LETTER})[-\u00ad]\s*(?={_LETTER}))|(?P<space>[\s\u200b\u00ad\u2022\u25cb\u25cf]+)|.",
                   re.S)
_WORD = re.compile(r"[^\W_]+(?:['.][^\W_]+)*")
_QUOTE_MARKS = {"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'"}


_MARKS = {ord("*"): None, ord("`"): None}       # Markdown's emphasis and code marks: typography, not words


def fold(text: str) -> str:
    """A text as it is compared: ``questions._norm`` (whitespace runs to one space, curly quote marks to straight,
    lowercase) after Markdown's emphasis marks are dropped, and a hyphen between letters with them, so a word broken
    at a line's end reads as one word."""
    return _norm(_HYPHEN.sub("", (text or "").translate(_MARKS)))


def fold_map(text: str) -> tuple[str, list[int] | None]:
    """``fold(text)`` with, for each character of it, the offset in ``text`` it came from, so words found in the
    folded text can be shown as stored. The map is None when the two foldings disagree (never seen; guarded)."""
    out: list[str] = []
    starts: list[int] = []
    kept = [k for k, ch in enumerate(text or "") if ord(ch) not in _MARKS]
    for m in _STEP.finditer((text or "").translate(_MARKS)):
        if m.lastgroup == "hyphen":
            continue                                         # a hyphen between letters, with the line break after it
        at = kept[m.start()]
        if m.lastgroup == "space":
            if out and out[-1] != " ":
                out.append(" ")
                starts.append(at)
            continue
        piece = m.group(0)
        for ch in _QUOTE_MARKS.get(piece, piece).lower():
            out.append(ch)
            starts.append(at)
    while out and out[-1] == " ":
        out.pop()
        starts.pop()
    folded = "".join(out)
    if folded != fold(text):
        return fold(text), None
    return folded, starts


@dataclass
class _Folded:
    """A text with its folding, the map back, and its words (as spans of the folded text)."""

    raw: str
    folded: str
    starts: list[int] | None
    tokens: list[tuple[int, int, str]]

    @classmethod
    def of(cls, raw: str) -> _Folded:
        folded, starts = fold_map(raw)
        return cls(raw, folded, starts, [(m.start(), m.end(), m.group(0)) for m in _WORD.finditer(folded)])

    def raw_span(self, start: int, end: int) -> tuple[int, int]:
        """Where a span of the folded text sits in the stored text."""
        if self.starts is None or not self.folded:
            return start, end
        return self.starts[start], self.starts[end - 1] + 1

    def shown(self, start: int, end: int) -> str:
        if self.starts is None:
            return self.folded[start:end]
        a, b = self.raw_span(start, end)
        return " ".join(self.raw[a:b].split())

    def marked(self, first: int, last: int, flagged: set[int]) -> str:
        """The words from token ``first`` up to token ``last``, as stored, with ``[[ ]]`` around each run of flagged
        tokens."""
        if first >= last:
            return ""
        source = self.raw if self.starts is not None else self.folded
        spans = [self.raw_span(s, e) for s, e, _ in self.tokens[first:last]]
        out: list[str] = []
        at = spans[0][0]
        k = 0
        while k < len(spans):
            if first + k not in flagged:
                k += 1
                continue
            run = k
            while run + 1 < len(spans) and first + run + 1 in flagged:
                run += 1
            out.append(source[at:spans[k][0]] + "[[" + source[spans[k][0]:spans[run][1]] + "]]")
            at = spans[run][1]
            k = run + 1
        out.append(source[at:spans[-1][1]])
        return " ".join("".join(out).split())


def words(text: str) -> list[str]:
    """A text's words as they are counted and aligned."""
    return _WORD.findall(fold(text))


# --- Quotations ---------------------------------------------------------------------------------------------------------

_GAP = r"(?!\n[ \t]*\n)"
_CURLY = re.compile(rf"\u201c((?:{_GAP}[^\u201d])+)\u201d")
_STRAIGHT = re.compile(rf'"((?:{_GAP}[^"])+)"')
_BLOCK_LINE = re.compile(r"^[ \t]{0,3}>[ \t]?(.*)$")
_BYLINE = re.compile(r"^\s*(?:[\u2014\u2013]|--)\s*\S")
_ELLIPSIS = re.compile(r"\s*(?:\[\s*(?:\.{3,}|\u2026|\.\s\.\s\.)\s*\]|\.{3,}|\u2026|\.\s\.\s\.(?:\s\.)?)\s*")
_BRACKET_LETTER = re.compile(r"\[([A-Za-z])\]")


@dataclass(frozen=True)
class Quotation:
    text: str                 # the words between the marks, as the answer wrote them
    start: int                # where the quotation opens in the answer
    end: int                  # just past where it closes
    style: str                # "straight", "curly", or "block"

    @property
    def parts(self) -> tuple[str, ...]:
        """The runs of words an ellipsis separates, each without the punctuation that closes it. A bracketed capital
        ("[T]he") reads as its letter."""
        text = _BRACKET_LETTER.sub(r"\1", self.text)
        parts = [p.strip().strip(",;:.").strip() for p in _ELLIPSIS.split(text)]
        return tuple(p for p in parts if _WORD.search(fold(p)))

    @property
    def word_count(self) -> int:
        return sum(len(words(p)) for p in self.parts)


def quotations(answer: str) -> list[Quotation]:
    """Every quotation in an answer, in order: block quotes, then curly and straight double quotation marks outside
    them. A quotation does not run across a blank line. A block quote's closing byline ("-- Civil Code 5855") is not
    part of its words."""
    text = answer or ""
    found: list[Quotation] = []
    masked = list(text)

    def mask(start: int, end: int) -> None:
        for k in range(start, end):
            if masked[k] != "\n":
                masked[k] = " "

    at = 0
    block: list[tuple[int, int, str]] = []            # (line start, line end, the words after ">")

    def close() -> None:
        lines = list(block)
        block.clear()
        if not lines:
            return
        mask(lines[0][0], lines[-1][1])
        if len(lines) > 1 and _BYLINE.match(lines[-1][2]):
            lines.pop()
        while lines and not lines[-1][2].strip():
            lines.pop()
        body = "\n".join(words_ for _, _, words_ in lines).strip()
        if len(body) > 1 and body[0] in '"\u201c' and body[-1] in '"\u201d':
            body = body[1:-1]
        if body:
            found.append(Quotation(body, lines[0][0], lines[-1][1], "block"))

    for line in text.splitlines(keepends=True):
        m = _BLOCK_LINE.match(line.rstrip("\n"))
        if m:
            block.append((at, at + len(line.rstrip("\n")), m.group(1)))
        else:
            close()
        at += len(line)
    close()
    for pattern, style in ((_CURLY, "curly"), (_STRAIGHT, "straight")):
        for m in pattern.finditer("".join(masked)):
            found.append(Quotation(text[m.start(1):m.end(1)], m.start(), m.end(), style))
            mask(m.start(), m.end())
    return sorted(found, key=lambda q: q.start)


# --- Matching one text --------------------------------------------------------------------------------------------------


def _ordered(parts: Sequence[str], text: str) -> int:
    """Where the first part starts when every part is in ``text`` in order; -1 otherwise."""
    at = 0
    first = -1
    for part in parts:
        found = text.find(part, at)
        if found < 0:
            return -1
        if first < 0:
            first = found
        at = found + len(part)
    return first


def _match(parts: Sequence[str], folded_parts: Sequence[str], raw: str, folded: str) -> Match | None:
    if _ordered(folded_parts, folded) < 0:
        return None
    return Match.EXACT if _ordered(parts, raw) >= 0 else Match.NORMALIZED


@dataclass(frozen=True)
class Alignment:
    """A stored text's nearest words to a quotation."""

    ratio: float
    stored: str                              # the stored words, each difference marked [[so]]
    quoted: str                              # the quoted words, each difference marked [[so]]
    differences: tuple[tuple[str, str], ...]   # (quoted, stored) for each place they differ


def align(quote: str, stored: str | _Folded) -> Alignment | None:
    """The run of ``stored`` nearest to ``quote``, word by word, with what differs. None when they share no run."""
    q = _Folded.of(quote)
    s = stored if isinstance(stored, _Folded) else _Folded.of(stored)
    a = [t for _, _, t in s.tokens]
    b = [t for _, _, t in q.tokens]
    if not a or not b:
        return None
    anchor = difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    if not anchor.size:
        return None
    slack = max(3, len(b) // 4)
    low = max(0, anchor.a - anchor.b - slack)
    high = min(len(a), anchor.a - anchor.b + len(b) + slack)
    blocks = [m for m in difflib.SequenceMatcher(None, a[low:high], b, autojunk=False).get_matching_blocks() if m.size]
    if not blocks:
        return None
    first, last = blocks[0], blocks[-1]
    start = low + max(0, first.a - first.b)
    end = min(high, low + last.a + last.size + len(b) - (last.b + last.size))
    matcher = difflib.SequenceMatcher(None, a[start:end], b, autojunk=False)
    matched = sum(m.size for m in matcher.get_matching_blocks())
    ratio = 2 * matched / (end - start + len(b))
    stored_flags: set[int] = set()
    quoted_flags: set[int] = set()
    differences: list[tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        stored_flags.update(range(start + i1, start + i2))
        quoted_flags.update(range(j1, j2))
        differences.append((q.shown(q.tokens[j1][0], q.tokens[j2 - 1][1]) if j2 > j1 else "",
                            s.shown(s.tokens[start + i1][0], s.tokens[start + i2 - 1][1]) if i2 > i1 else ""))
    return Alignment(round(ratio, 3), s.marked(start, end, stored_flags), q.marked(0, len(b), quoted_flags),
                     tuple(differences))


# --- The index's passages -----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Row:
    rel: str
    idx: int
    heading: str
    text: str
    catalog: str
    standing: str
    kind: str
    confidential: bool
    generated: bool


class _Index:
    """Every passage of the index with its text folded once, kept until the index file changes."""

    def __init__(self, data_dir: Path, rows: list[_Row]) -> None:
        self.data_dir = data_dir
        self.rows = rows
        self.folded = [fold(r.text) for r in rows]
        self.by_file: dict[str, list[int]] = {}
        for k, row in enumerate(rows):
            self.by_file.setdefault(row.rel, []).append(k)

    def exact(self, folded_parts: Sequence[str]) -> list[int]:
        """The passages that hold every part in order."""
        longest = max(folded_parts, key=len)
        return [k for k, text in enumerate(self.folded) if longest in text and _ordered(folded_parts, text) >= 0]

    def across(self, folded_parts: Sequence[str]) -> list[tuple[int, ...]]:
        """Runs of neighbouring passages of one file that hold the words between them: a quotation that crosses the
        place a file was cut (any neighbours), or an ellipsis whose parts sit in one section's passages."""
        ends: set[str] = set()
        for part in folded_parts:
            tokens = list(_WORD.finditer(part))
            if len(tokens) <= 4:
                ends.add(part)
            else:
                ends.add(part[: tokens[3].end()])
                ends.add(part[tokens[-4].start():])
        files = list(dict.fromkeys(self.rows[k].rel for k, text in enumerate(self.folded) if any(e in text for e in ends)))
        out: list[tuple[int, ...]] = []
        for rel in files[:_CANDIDATES]:
            members = self.by_file[rel]
            groups = [members] if len(folded_parts) == 1 else self._sections(members)
            for group in groups:
                if len(group) < 2:
                    continue
                joined, offsets = "", []
                for k in group:
                    offsets.append(len(joined))
                    joined += self.folded[k] + " "
                first = _ordered(folded_parts, joined)
                if first < 0:
                    continue
                last = joined.rfind(folded_parts[-1]) + len(folded_parts[-1]) if len(folded_parts) > 1 else first + len(folded_parts[0])
                run = tuple(k for k, at in zip(group, offsets) if at < last and at + len(self.folded[k]) > first)
                out.append(run or (group[0],))
        return out

    def _sections(self, members: list[int]) -> list[list[int]]:
        groups: list[list[int]] = []
        for k in members:
            if groups and self.rows[groups[-1][-1]].heading == self.rows[k].heading:
                groups[-1].append(k)
            else:
                groups.append([k])
        return groups

    def candidates(self, part: str) -> list[int]:
        """The passages most likely to hold nearly these words: those with most of the part's longest words."""
        tokens = list(dict.fromkeys(_WORD.findall(part)))
        long = [t for t in tokens if len(t) >= 5]
        anchors = sorted(long if len(long) >= 3 else tokens, key=len, reverse=True)[:_ANCHORS]
        if not anchors:
            return []
        need = max(1, math.ceil(0.6 * len(anchors)))
        scored = []
        for k, text in enumerate(self.folded):
            count = sum(1 for anchor in anchors if anchor in text)
            if count >= need:
                scored.append((-count, k))
        return [k for _, k in sorted(scored)[:_CANDIDATES]]


_MEMO: dict[str, tuple[float, _Index]] = {}


def _load(data_dir: Path) -> _Index:
    path = pi.index_path(data_dir)
    if not path.is_file():
        raise FileNotFoundError(f"no passage index at {path}: build it with jason index --build")
    key, stamp = str(path.resolve()), path.stat().st_mtime
    held = _MEMO.get(key)
    if held is not None and held[0] == stamp:
        return held[1]
    db = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        rows = [_Row(rel, idx, heading, text, catalog, standing, kind, bool(conf), bool(gen))
                for rel, idx, heading, text, catalog, standing, kind, conf, gen in db.execute(
                    "SELECT p.path, p.idx, p.heading, p.text, f.catalog, f.standing, f.kind, f.confidential, f.generated "
                    "FROM passages p JOIN files f ON f.path = p.path ORDER BY p.path, p.idx")]
    finally:
        db.close()
    index = _Index(Path(data_dir), rows)
    _MEMO.clear()
    _MEMO[key] = (stamp, index)
    return index


# --- What a check returns -----------------------------------------------------------------------------------------------

_STANDING_ORDER = {s.value: k for k, s in enumerate((pi.Standing.AUTHORITY, pi.Standing.RECORD, pi.Standing.EVIDENCE,
                                                     pi.Standing.REFERENCE, pi.Standing.PAGE))}
_STANDING_WARNING = {
    pi.Standing.PAGE.value: "found only in a page jason generated: its own summary, not the record or the law. Quote "
                            "the record or the law it points to.",
    pi.Standing.REFERENCE.value: "found only on the reference shelf: learned from, never quoted as the record or the law.",
    pi.Standing.EVIDENCE.value: "found only in a case's file: evidence gathered for one matter, neither the record nor "
                                "the law.",
}
WITHHELD = "in a confidential file: its name and words are held back unless confidential files are asked for"


@dataclass
class Place:
    """One place a quotation's words are stored."""

    standing: str
    match: Match
    catalog: str = ""
    file: str = ""                    # the file's name
    path: str = ""                    # its path under the data directory
    passages: tuple[int, ...] = ()
    section: str = ""                 # the passage's section path, or the provision's citation
    kind: str = ""
    generated: bool = False
    confidential: bool = False
    withheld: bool = False            # confidential and not asked for: only its standing is given
    citation: str = ""                # a provision read through the citation resolver
    digest: str = ""
    context: str = ""                 # the stored words around the quotation
    in_sources: bool | None = None    # among the sources the caller gave; None when none were given
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        if self.withheld:
            out: dict[str, Any] = {"confidential": True, "withheld": True, "standing": self.standing,
                                   "match": self.match.value, "note": WITHHELD}
        else:
            out = {"file": self.file, "path": self.path, "passages": list(self.passages), "section": self.section,
                   "catalog": self.catalog, "standing": self.standing, "kind": self.kind, "generated": self.generated,
                   "confidential": self.confidential, "match": self.match.value}
            if self.citation:
                out["citation"], out["digest"] = self.citation, self.digest
            if self.context:
                out["context"] = self.context
            if self.note:
                out["note"] = self.note
        if self.in_sources is not None:
            out["inSources"] = self.in_sources
        return out

    def line(self, *, match: bool = True) -> str:
        if self.withheld:
            return f"[{self.standing}] {WITHHELD}"
        where = self.citation or self.section
        passage = ("passage " if len(self.passages) == 1 else "passages ") + "-".join(
            str(n) for n in ((self.passages[0], self.passages[-1]) if len(self.passages) > 1 else self.passages))
        bits = [f"[{self.standing}]"]
        if self.path or self.file:
            bits.append(self.path or self.file)
        if where:
            bits.append(where)
        if self.passages:
            bits.append(passage)
        if self.digest:
            bits.append(f"digest {self.digest[:12]}")
        flags = [name for name, on in (("generated", self.generated), ("confidential", self.confidential),
                                       ("not in the sources given", self.in_sources is False)) if on]
        if match:
            flags.insert(0, self.match.value)
        return bits[0] + " " + ", ".join(bits[1:]) + (f" ({'; '.join(flags)})" if flags else "")


@dataclass
class QuoteCheck:
    quote: Quotation
    verdict: Verdict
    match: Match | None = None
    places: list[Place] = field(default_factory=list)
    more_places: int = 0
    attributed: list[str] = field(default_factory=list)       # the citations the answer attributes it to
    warnings: list[str] = field(default_factory=list)
    note: str = ""
    stored: str = ""                  # ALTERED: the stored words, differences marked
    quoted: str = ""                  # ALTERED: the quoted words, differences marked
    differences: list[dict[str, str]] = field(default_factory=list)
    compared_with: Place | None = None      # ALTERED: where the stored words are

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"quote": self.quote.text, "at": self.quote.start, "style": self.quote.style,
                               "verdict": self.verdict.value}
        if self.match is not None:
            out["match"] = self.match.value
        if self.attributed:
            out["attributedTo"] = list(self.attributed)
        if self.places:
            out["places"] = [p.as_dict() for p in self.places]
        if self.more_places:
            out["morePlaces"] = self.more_places
        if self.verdict is Verdict.ALTERED and (self.stored or self.quoted or self.compared_with):
            out["quoted"], out["stored"], out["differences"] = self.quoted, self.stored, self.differences
            if self.compared_with is not None:
                out["comparedWith"] = self.compared_with.as_dict()
        if self.warnings:
            out["warnings"] = list(self.warnings)
        if self.note:
            out["note"] = self.note
        return out


@dataclass
class CitationCheck:
    citation: str                     # as jason writes it: "CIV 5855(a)", "bylaws#7.2"
    kind: str                         # "statute", "section", "document", or another unit jason does not check here
    offset: int
    checked: bool = True
    found: bool = False
    digest: str = ""
    source: str = ""
    page: str = ""
    versions: list[dict[str, str]] = field(default_factory=list)      # each text the shelf holds under the number
    caveats: list[str] = field(default_factory=list)
    reason: str = ""
    quotes: list[dict[str, Any]] = field(default_factory=list)        # the quotations attributed to it
    in_force: dict[str, Any] | None = None    # a statute checked as of a day: which version, and how it is known

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"citation": self.citation, "kind": self.kind, "at": self.offset, "checked": self.checked}
        if not self.checked:
            out["note"] = self.reason
            return out
        out["found"] = self.found
        if self.kind == "statute":
            out["onShelf"] = self.found
        if self.found:
            out.update({"digest": self.digest, "source": self.source})
            if self.page:
                out["page"] = self.page
            if len(self.versions) > 1:
                out["versions"] = self.versions
        if self.in_force is not None:
            out["inForce"] = self.in_force
        elif self.reason:
            out["reason"] = self.reason
        if self.caveats:
            out["caveats"] = self.caveats
        out["quotes"] = self.quotes
        return out


@dataclass
class Report:
    quotes: list[QuoteCheck]
    citations: list[CitationCheck]
    skipped: list[str]                # quotations shorter than MIN_WORDS, not checked
    sources: dict[str, Any]           # what the caller's sources resolved to
    passages: int                     # the passages searched
    seconds: float
    include_confidential: bool = False
    as_of: date | None = None         # the day a statute's quotation was checked against the version in force

    @property
    def counts(self) -> dict[str, int]:
        out = {v.value: sum(1 for q in self.quotes if q.verdict is v) for v in Verdict}
        out["warnings"] = sum(len(q.warnings) for q in self.quotes)
        return out

    @property
    def clean(self) -> bool:
        """Every quotation checked is FOUND. Warnings (a summary, a reference) do not change it; read them."""
        return all(q.verdict is Verdict.FOUND for q in self.quotes)

    def as_dict(self) -> dict[str, Any]:
        return {"minimumWords": MIN_WORDS, "counts": self.counts, "quotes": [q.as_dict() for q in self.quotes],
                "citations": [c.as_dict() for c in self.citations], "skipped": list(self.skipped),
                **({"sources": self.sources} if self.sources else {}),
                "includeConfidential": self.include_confidential, "passagesSearched": self.passages,
                "seconds": self.seconds, "asOf": self.as_of.isoformat() if self.as_of else None, "caveats": list(CAVEATS)}

    def lines(self) -> list[str]:
        counts = self.counts
        head = (f"{len(self.quotes)} quotation(s) checked against {self.passages} passages in {self.seconds:.2f} s: "
                + ", ".join(f"{counts[v.value]} {v.value}" for v in Verdict if counts[v.value]))
        out = [head if self.quotes else f"no quotation of {MIN_WORDS} words or more to check"]
        if self.as_of is not None:
            out.append(f"as of {self.as_of.isoformat()}: a statute's quotation is checked against the version in force "
                       "that day, where the disk shows it")
        if self.skipped:
            out.append(f"{len(self.skipped)} quotation(s) shorter than {MIN_WORDS} words not checked: "
                       + "; ".join(f'"{s}"' for s in self.skipped))
        for n, q in enumerate(self.quotes, 1):
            label = q.verdict.value.upper() + (f" ({q.match.value})" if q.match and q.verdict is Verdict.FOUND else "")
            out.append("")
            out.append(f'{n}. {label}: "{_brief(q.quote.text)}"')
            if q.attributed:
                out.append(f"   attributed to {', '.join(q.attributed)}")
            if q.verdict is Verdict.ALTERED and (q.quoted or q.stored):
                out.append(f"   quoted: {q.quoted}")
                out.append(f"   stored: {q.stored}")
                if q.compared_with is not None:
                    out.append(f"   in {q.compared_with.line(match=False)}")
            for place in q.places:
                out.append(f"   in {place.line()}")
            if q.more_places:
                out.append(f"   and {q.more_places} more place(s)")
            if q.note:
                out.append(f"   note: {q.note}")
            out.extend(f"   WARNING: {w}" for w in q.warnings)
        if self.citations:
            out += ["", "citations:"]
        for c in self.citations:
            if not c.checked:
                out.append(f"- {c.citation}: not checked ({c.reason})")
                continue
            if c.found:
                state = ("on the shelf" if c.kind == "statute" else "held") + (f", digest {c.digest[:12]}" if c.digest else "")
            else:
                state = ("not on the shelf" if c.kind == "statute" else "not found") + (f" ({c.reason})" if c.reason else "")
            told = "; ".join(f"quotation {r['quote']} {_IN_WORDS[r['inItsWords']]}" for r in c.quotes)
            out.append(f"- {c.citation}: {state}" + (f"; {told}" if told else ""))
            if c.in_force is not None:
                out.append(f"    checked against {c.in_force['label']}")
            out.extend(f"    {caveat}" for caveat in c.caveats)
        out += ["", *(f"- {c}" for c in CAVEATS)]
        return out


_IN_WORDS = {True: "is in its words", False: "is not in its words", "altered": "is nearly its words (altered)",
             "other version": "is in another version of it, not the one checked (other version)"}


def _brief(text: str, limit: int = 160) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


# --- Provisions: a citation's stored words ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Edition:
    """Another version of a statute's section than the one a quotation is checked against: on the shelf or in the
    history, with where it stands (earlier, later, or not said by its range) and how it is named in a verdict."""

    digest: str
    words: str
    place: str                 # "earlier", "later", or ""
    range: str                 # ``law_text.range_words``
    current: bool              # on the shelf now
    label: str                 # "an earlier version of CIV 9901 (digest ..., from ... until ...), held in the history"


@dataclass
class _Provision:
    id: str
    kind: str
    found: bool = False
    texts: list[tuple[str, str]] = field(default_factory=list)       # (digest, words), each version checked against
    source: str = ""
    page: str = ""
    standing: str = pi.Standing.AUTHORITY.value
    caveats: list[str] = field(default_factory=list)
    reason: str = ""
    labels: tuple[str, ...] = ()
    checked: bool = True
    editions: list[Edition] = field(default_factory=list)            # the other versions held: read to name, never to confirm
    in_force: dict[str, Any] | None = None                           # as of a day: which version ``texts`` is, and how known
    checked_label: str = ""                                          # "the version in force on DAY (...)" or "the words on the shelf now (...)"


def _edition(v: Any, place: str, citation: str) -> Edition:
    from jason.community.law_text import MIN_DIGEST, range_words

    what = {"earlier": "an earlier", "later": "a later"}.get(place, "another")
    where = "on the shelf now" if v.current else "held in the history"
    label = f"{what} version of {citation} (digest {v.digest[:MIN_DIGEST]}, {range_words(v)}), {where}"
    return Edition(v.digest, v.words, place, range_words(v), v.current, label)


class _Provisions:
    """The words behind each citation, read once: a statute's section from the shelf, a governing document's section
    through the citation resolver, a whole document from its outline. Disk only. With ``as_of`` a statute's section
    is the version in force that day where the disk shows it (``law_text.version_on``), and the other versions held
    are its editions."""

    def __init__(self, data_dir: Path, community: Any, as_of: date | None = None) -> None:
        self.data_dir = data_dir
        self.community = community
        self.as_of = as_of
        self._shelf: Any = None
        self._held: dict[str, _Provision] = {}

    @property
    def shelf(self) -> Any:
        if self._shelf is None:
            from jason.tasks.cite import Shelf

            self._shelf = Shelf(self.community, self.data_dir)
        return self._shelf

    def names(self) -> dict[str, str]:
        try:
            return self.shelf.names()
        except Exception:                                    # no profile documents: statutes are still read
            return {}

    def of(self, target: Target) -> list[_Provision]:
        """A target's provisions: one, or one a number for siblings named together."""
        if target.siblings and target.unit in (Unit.SECTION, Unit.STATUTE):
            return [self._one(Target(target.unit, target.key, number)) for number in target.siblings]
        return [self._one(target)]

    def _one(self, target: Target) -> _Provision:
        if target.id not in self._held:
            self._held[target.id] = self._read(target)
        return self._held[target.id]

    def _read(self, t: Target) -> _Provision:
        from jason.community.law_readings import provision_text

        if t.end or t.unit not in (Unit.STATUTE, Unit.SECTION, Unit.DOCUMENT):
            what = "a span of sections" if t.end else f"a {t.unit.value}"
            return _Provision(t.id, t.unit.value, checked=False,
                              reason=f"{what}: jason checks a statute's section and a document's section here; "
                                     "jason cite recites the rest")
        if t.unit is Unit.DOCUMENT:
            outline = self.shelf.outlines().get(t.key)
            if outline is None or not outline.text:
                return _Provision(t.id, "document", reason="jason holds no text for the document as a whole")
            return _Provision(t.id, "document", True, [("", outline.text)], outline.title,
                              standing=pi.Standing.RECORD.value)
        if t.unit is Unit.STATUTE:
            return self._statute(t)
        try:
            text = provision_text(t.base, self.data_dir, community=self.community)
        except Exception as exc:                             # a document the profile cannot open is a miss, not a crash
            return _Provision(t.id, "section", reason=str(exc))
        if not text.found:
            return _Provision(t.id, "section", reason=text.reason)
        return _Provision(t.id, "section", True, [(text.digest, text.words)], text.source,
                          standing=pi.Standing.RECORD.value, caveats=list(text.caveats))

    def _statute(self, t: Target) -> _Provision:
        """A statute's section: the version a quotation is checked against, and the other versions held as editions.
        As of a day, the version in force that day where the disk shows it; else the words on the shelf now, every
        version the shelf prints under the number."""
        from jason.community import law_text
        from jason.community.law_readings import provision_text
        from jason.community.law_text import MIN_DIGEST

        every = law_text.every_version(t.base, self.data_dir)
        today = date.today().isoformat()
        if self.as_of is not None:
            got = law_text.version_on(t.base, self.data_dir, self.as_of)
            day = self.as_of.isoformat()
            if got.found:
                places = {h.digest: h.place for h in got.held}
                editions = [_edition(v, places.get(v.digest, ""), t.base) for v in every if v.digest != got.digest]
                label = got.label()
                return _Provision(t.id, "statute", True, [(got.digest, got.words)], got.text.source, got.text.page,
                                  caveats=[c for c in got.caveats if c != law_text.NOT_RESTATEMENT], labels=t.labels,
                                  editions=editions, checked_label=label,
                                  in_force={"asOf": day, "shown": True, "decided": got.decided.value, "digest": got.digest,
                                            "from": got.start, "until": got.until, "basis": got.basis, "label": label})
            not_shown = {"asOf": day, "shown": False, "decided": got.decided.value, "digest": "", "from": "", "until": "",
                         "basis": got.basis, "label": f"the words on the shelf now; {got.reason}"}
        else:
            not_shown = None
        text = provision_text(t.base, self.data_dir, community=self.community)
        if not text.found:
            return _Provision(t.id, "statute", reason=text.reason, labels=t.labels, in_force=not_shown)
        held = law_text.law_text(t.base, self.data_dir)
        shelf = {v.digest for v in text.versions}
        # Where another version stands against the words checked: against the shelf's one version by its recorded
        # range, else by the day alone.
        against = next((v for v in every if v.current), None) if len(shelf) == 1 else None
        editions = [_edition(v, law_text.place_of(v, against, today), t.base) for v in every if v.digest not in shelf]
        digests = ", ".join(v.digest[:MIN_DIGEST] for v in text.versions)
        caveats = list(text.caveats)
        if not_shown is not None:
            caveats.insert(0, f"the disk does not show which words of {t.base} were in force on {not_shown['asOf']}: the "
                              f"quotation is checked against the words on the shelf now ({not_shown['basis']})")
        return _Provision(t.id, "statute", True, [(v.digest, v.words) for v in text.versions], text.source,
                          held.page if held else "", caveats=caveats, labels=t.labels, editions=editions,
                          in_force=not_shown, checked_label=f"the words on the shelf now (digest {digests})")


# --- The caller's sources -----------------------------------------------------------------------------------------------

_SOURCE_PASSAGE = re.compile(r"^(?P<path>.+?)(?:\s*(?:#|:|,?\s+passages?\s+)(?P<n>\d+))?$", re.I)


@dataclass
class _Sources:
    given: bool = False
    rows: set[int] = field(default_factory=set)
    provisions: list[_Provision] = field(default_factory=list)
    catalogs: set[str] = field(default_factory=set)          # case catalogs the sources name
    resolved: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        if not self.given:
            return {}
        return {"resolved": self.resolved, "unresolved": self.unresolved}


def _source_items(sources: str | Sequence[Any]) -> list[Any]:
    if not isinstance(sources, str):
        return list(sources or ())
    text = sources.strip()
    if not text:
        return []
    if text[0] in "[{":
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if isinstance(data, dict):
            data = data.get("hits") or [data]
        if isinstance(data, list):
            return data
    return [item.strip() for item in re.split(r"[\n;]+", text) if item.strip()]


def _read_sources(sources: str | Sequence[Any], index: _Index, provisions: _Provisions, names: dict[str, str]) -> _Sources:
    from jason.tasks.case_files import is_case_catalog

    out = _Sources()
    items = _source_items(sources)
    out.given = bool(items)
    roots = {index.data_dir.resolve().as_posix().lower(), index.data_dir.as_posix().lower()}
    by_name: dict[str, list[str]] = {}
    for rel in index.by_file:
        by_name.setdefault(rel.rsplit("/", 1)[-1].lower(), []).append(rel)
    by_rel = {rel.lower(): rel for rel in index.by_file}

    def file_rows(text: str, passage: int | None) -> bool:
        """Mark the index's passages a path names: under the data directory, absolute, or a bare file name."""
        low = text.strip().strip('"').replace("\\", "/").lower()
        for root in roots:
            if low.startswith(root + "/"):
                low = low[len(root) + 1:]
                break
        if low in by_rel:
            rels = [by_rel[low]]
        else:
            rels = by_name.get(low, []) if "/" not in low else []
        hit = False
        for rel in rels:
            for k in index.by_file[rel]:
                if passage is None or index.rows[k].idx == passage:
                    out.rows.add(k)
                    hit = True
                    if is_case_catalog(index.rows[k].catalog):
                        out.catalogs.add(index.rows[k].catalog)
        return hit

    for item in items:
        if isinstance(item, dict):
            path = str(item.get("path") or item.get("file") or "")
            passage = item.get("passage")
            label = path + (f"#{passage}" if passage is not None else "")
            if path and file_rows(path, int(passage) if isinstance(passage, int) or str(passage or "").isdigit() else None):
                out.resolved.append(label)
            else:
                out.unresolved.append(label or json.dumps(item)[:80])
            continue
        text = str(item).strip()
        if is_case_catalog(text) and any(r.catalog == text for r in index.rows):
            out.catalogs.add(text)
            out.resolved.append(text)
            continue
        m = _SOURCE_PASSAGE.match(text)
        if m and file_rows(m.group("path"), int(m.group("n")) if m.group("n") else None):
            out.resolved.append(text)
            continue
        if file_rows(text, None):
            out.resolved.append(text)
            continue
        cited = [p for found in located_targets(text, names) for p in provisions.of(found.target)]
        if not cited:
            from jason.community.law_readings import target_of

            target = target_of(text)
            if target is not None and "#" not in target:
                code, _, number = target.rpartition(" ")
                cited = provisions.of(Target(Unit.STATUTE, code, number))
        usable = [p for p in cited if p.found]
        if usable:
            out.provisions += usable
            out.resolved.append(text)
        else:
            out.unresolved.append(text)
    return out


# --- Attribution: which citation a quotation is said to come from --------------------------------------------------------

_CLOSE = re.compile(r"^[\s>,;:.]*(?:[\u2014\u2013-]+\s*)?\(?\s*(?:(?:see|per|from|at|in|of|under|quoting|citing)\s+)?(?:the\s+)?$", re.I)
_CLAUSE = re.compile(r";|\b(?:but|while|whereas|however|although)\b", re.I)
_LEAD_IN = re.compile(r"[:,]\s*$")


def _attributions(answer: str, quotes: Sequence[Quotation], cited: Sequence[Located]) -> list[list[Located]]:
    """For each quotation, the citations the answer attributes it to: those that introduce it in its sentence (after
    the last clause break and the last quotation), a lead-in sentence that ends with a colon, or the one that follows
    it directly ("..." (Civil Code 5855))."""
    from jason.community.deontic import sentences

    spans = sentences(answer)
    ordered = sorted(cited, key=lambda c: c.offset)
    after: list[list[Located]] = []
    taken: set[int] = set()
    for q in quotes:
        mine = []
        for k, c in enumerate(ordered):
            if q.end <= c.offset <= q.end + 60 and _CLOSE.match(answer[q.end:c.offset]) and k not in taken:
                if mine and c.offset - mine[-1].offset > 40:
                    break
                mine.append(c)
                taken.add(k)
        after.append(mine)
    out: list[list[Located]] = []
    for n, q in enumerate(quotes):
        sentence = max((s for s, e in spans if s <= q.start), default=0)
        start = max(sentence, quotes[n - 1].end if n else 0, q.start - _REACH)
        lead = answer[start:q.start]
        if not lead.strip() or q.style == "block":
            # The quotation opens its line: the sentence before it introduces it when it ends with a colon or a comma.
            before = [(s, e) for s, e in spans if e <= q.start]
            if before and (q.style == "block" or _LEAD_IN.search(answer[before[-1][0]:q.start])):
                start = max(before[-1][0], quotes[n - 1].end if n else 0)
                lead = answer[start:q.start]
        breaks = [m.end() for m in _CLAUSE.finditer(lead)]
        start += breaks[-1] if breaks else 0
        before_q = [c for k, c in enumerate(ordered) if start <= c.offset < q.start and k not in taken]
        if not before_q and n and out[n - 1] and not after[n - 1] and quotes[n - 1].end >= sentence \
                and len(answer[quotes[n - 1].end:q.start]) <= 60 and not _CLAUSE.search(answer[quotes[n - 1].end:q.start]):
            before_q = list(out[n - 1])                       # 'X says "A" and "B"': B is attributed as A is
        out.append(before_q + after[n])
    return out


# --- The check ----------------------------------------------------------------------------------------------------------


def check(answer: str, data_dir: Path | str, *, sources: str | Sequence[Any] = "", include_confidential: bool = False,
          community: Any = None, as_of: date | None = None) -> Report:
    """Check every quotation and citation in ``answer`` against jason's stored words.

    ``sources`` are the hits the answer was written from, if the caller has them: file paths with passage numbers
    ("governing/ccrs.md#3"; one a line or separated by ";"), citations ("CIV 5855"), or ``document_search``'s hits as
    JSON. A quotation found outside them is flagged. ``include_confidential`` names confidential files and shows their
    words; a case catalog's only when the sources name it. ``as_of`` checks a quotation attributed to a statute
    against the version in force on that day, where the disk shows it; a quotation of another version is
    ``OTHER_VERSION``, named. Without a day a statute's words are the words on the shelf now, and the history is read
    only to name a quotation of an earlier version. Documents are checked as before either way. Raises
    ``FileNotFoundError`` without an index."""
    from jason.tasks.case_files import is_case_catalog

    started = time.monotonic()
    data_dir = Path(data_dir)
    answer = (answer or "").replace("\r\n", "\n").replace("\r", "\n")
    index = _load(data_dir)
    if community is None:
        from jason.community import community as active

        community = active()
    provisions = _Provisions(data_dir, community, as_of)
    names = provisions.names()
    given = _read_sources(sources, index, provisions, names)

    def withheld(row: _Row) -> bool:
        if not row.confidential:
            return False
        if not include_confidential:
            return True
        return is_case_catalog(row.catalog) and row.catalog not in given.catalogs

    every = quotations(answer)
    checked = [q for q in every if q.word_count >= MIN_WORDS]
    skipped = [_brief(q.text, 80) for q in every if q.word_count < MIN_WORDS]
    # A citation inside a quotation ("pursuant to Section 4040") is part of the quoted words, not the answer's own.
    cited = [c for c in located_targets(answer, names) if not any(q.start <= c.offset < q.end for q in every)]
    attributed = _attributions(answer, checked, cited)

    def row_place(k: int, match: Match, part: str = "", run: tuple[int, ...] = ()) -> Place:
        row = index.rows[k]
        place = Place(row.standing, match, row.catalog, row.rel.rsplit("/", 1)[-1], row.rel,
                      tuple(index.rows[j].idx for j in run) or (row.idx,), row.heading, row.kind, row.generated,
                      row.confidential, withheld(row), in_sources=(any(j in given.rows for j in (run or (k,)))
                                                                   if given.given else None))
        if run:
            place.note = "the quotation runs across neighbouring passages of the file"
        elif part and not place.withheld:
            place.context = _context(row.text, part)
        return place

    def provision_place(p: _Provision, digest: str, match: Match, in_sources: bool | None) -> Place:
        return Place(p.standing, match, "authorities" if p.kind == "statute" else "", Path(p.page).name if p.page else "",
                     p.page, (), p.id, citation=p.id, digest=digest, in_sources=in_sources)

    def in_provision(p: _Provision, parts: Sequence[str], folded_parts: Sequence[str]) -> list[tuple[str, Match]]:
        """The versions of a provision that hold the words, each with how it matched."""
        hits = []
        for digest, text in p.texts:
            match = _match(parts, folded_parts, text, fold(text))
            if match is not None:
                hits.append((digest, match))
        return hits

    def near(parts: Sequence[str], texts: Iterable[tuple[Any, str | _Folded]]) -> tuple[Any, list[Alignment]] | None:
        """The text nearest to the quotation's parts: for each part its alignment, when every part is at least a near
        match in it."""
        best: tuple[float, Any, list[Alignment]] | None = None
        for key, text in texts:
            folded = text if isinstance(text, _Folded) else _Folded.of(text)
            found = [align(part, folded) for part in parts]
            if any(a is None or a.ratio < NEAR for a in found):
                continue
            score = min(a.ratio for a in found)
            if best is None or score > best[0]:
                best = (score, key, found)
        return (best[1], best[2]) if best else None

    def versions(held: Iterable[_Provision]) -> list[tuple[tuple[_Provision, str], str]]:
        """Each text of each provision, keyed by the provision and that text's digest."""
        return [((p, digest), text) for p in held for digest, text in p.texts]

    results: list[QuoteCheck] = []
    told: dict[str, list[dict[str, Any]]] = {}             # citation id -> the quotations attributed to it
    for n, quote in enumerate(checked):
        parts = quote.parts
        folded_parts = [fold(p) for p in parts]
        claimed = [p for c in attributed[n] for p in provisions.of(c.target)]
        claimed = list({p.id: p for p in claimed}.values())
        resolved = [p for p in claimed if p.found]
        # A whole document named beside a quotation can confirm it and never accuses: jason's copy of the document
        # is one copy, and the index may hold the words in another.
        strict = [p for p in resolved if p.kind != "document"]
        result = QuoteCheck(quote, Verdict.NOT_FOUND, attributed=[p.id for p in claimed])
        places: list[Place] = []

        # 1. In the provision the answer attributes it to.
        confirmed = False
        other: list[tuple[_Provision, Edition, Match]] = []     # a statute's words of another version than the one checked
        for p in resolved:
            hits = in_provision(p, parts, folded_parts)
            told.setdefault(p.id, []).append({"quote": n + 1, "inItsWords": bool(hits)})
            for digest, match in hits:
                confirmed = True
                place = provision_place(p, digest, match, True if given.given and p in given.provisions else
                                        (None if not given.given else False))
                if p.in_force is not None and p.in_force["shown"]:
                    place.note = f"matches {p.checked_label}"
                places.append(place)
            if not hits:
                for edition in p.editions:
                    match = _match(parts, folded_parts, edition.words, fold(edition.words))
                    if match is not None:
                        other.append((p, edition, match))
                        told[p.id][-1]["inItsWords"] = "other version"
                        break
            if hits and len(p.texts) > 1:
                held = ", ".join(d[:12] for d, _ in hits)
                result.warnings.append(f"the shelf holds {len(p.texts)} versions of {p.id} under the one number; the "
                                       f"words are in the version(s) with digest {held}. jason does not say which is "
                                       "in force on a given day.")
            if hits and p.labels:
                inside = any(_ordered(folded_parts, fold(label_text(text, p.labels))) >= 0 for _, text in p.texts)
                if not inside:
                    result.warnings.append(f"the words are in {p.id.split('(')[0]}, outside "
                                           f"{''.join(f'({x})' for x in p.labels)} as jason splits the section")
        for p in claimed:
            if not p.found:
                told.setdefault(p.id, [])
                why = p.reason or "not checked"
                result.warnings.append(f"attributed to {p.id}, which jason could not open ({why}): the attribution "
                                       "was not checked")

        # 2. In the sources' provisions and in the index.
        for p in given.provisions:
            if p in resolved:
                continue
            for digest, match in in_provision(p, parts, folded_parts):
                places.append(provision_place(p, digest, match, True))
        rows = index.exact(folded_parts)
        for k in rows:
            match = Match.EXACT if _ordered(parts, index.rows[k].text) >= 0 else Match.NORMALIZED
            places.append(row_place(k, match, folded_parts[0]))
        if not rows:
            for run in index.across(folded_parts):
                places.append(row_place(run[0], Match.NORMALIZED, run=run))

        if other and not confirmed:
            # The words are the statute's, of a version other than the one checked: said plainly, and not clean.
            p, edition, match = other[0]
            result.verdict, result.match = Verdict.OTHER_VERSION, match
            result.compared_with = provision_place(p, edition.digest, match, None)
            result.compared_with.note = edition.label
            result.note = f"the words you quote are {edition.label}; the version checked, {p.checked_label}, reads differently"
            if places:
                places.sort(key=lambda pl: (pl.withheld, not pl.citation, pl.in_sources is False,
                                            _STANDING_ORDER.get(pl.standing, 9), pl.match is not Match.EXACT, pl.path))
                result.places, result.more_places = places[:MAX_PLACES], max(0, len(places) - MAX_PLACES)
                result.warnings.append("the words as quoted are also stored in the place(s) listed; none is the version "
                                       "checked")
            results.append(result)
            continue

        if places:
            places.sort(key=lambda p: (p.withheld, not p.citation, p.in_sources is False,
                                       _STANDING_ORDER.get(p.standing, 9), p.match is not Match.EXACT, p.path))
            result.places, result.more_places = places[:MAX_PLACES], max(0, len(places) - MAX_PLACES)
            result.match = Match.EXACT if any(p.match is Match.EXACT for p in places) else Match.NORMALIZED
            close = near(parts, versions(strict)) if strict and not confirmed else None
            if confirmed or not strict:
                result.verdict = Verdict.FOUND
                if resolved and not confirmed:
                    result.warnings.append(f"attributed to {', '.join(p.id for p in resolved)} as a whole; jason's copy "
                                           "of it does not hold these words: see where they are stored")
            elif close is not None:
                # The answer names a provision whose own words are nearly these: it misquotes that provision, though
                # the words as quoted are stored elsewhere.
                p, digest = close[0]
                _altered(result, close[1], provision_place(p, digest, Match.NORMALIZED, None))
                _note(result, f"{p.id} has nearly these words, not these; the words as quoted are stored in the "
                              "place(s) listed")
                told[p.id][-1]["inItsWords"] = "altered"
            else:
                result.verdict = Verdict.MISATTRIBUTED
                result.note = (f"attributed to {', '.join(p.id for p in strict)}, whose words do not hold it; the "
                               "words are stored in the place(s) listed")
            _standing_warnings(result, places, given)
            results.append(result)
            continue

        # 3. Nearly the words: the attributed provision first, then the sources, then the open index, then the rest.
        close = near(parts, versions(strict))
        if close is not None:
            p, digest = close[0]
            _altered(result, close[1], provision_place(p, digest, Match.NORMALIZED, None))
            told[p.id][-1]["inItsWords"] = "altered"
            results.append(result)
            continue
        close = near(parts, versions(given.provisions))
        if close is not None:
            p, digest = close[0]
            _altered(result, close[1], provision_place(p, digest, Match.NORMALIZED, True))
            results.append(result)
            continue
        candidates = list(dict.fromkeys(k for part in folded_parts for k in index.candidates(part)))
        candidates.sort(key=lambda k: (withheld(index.rows[k]), k not in given.rows))
        open_rows = [k for k in candidates if not withheld(index.rows[k])]
        close = near(parts, [(k, index.rows[k].text) for k in open_rows])
        if close is not None:
            _altered(result, close[1], row_place(close[0], Match.NORMALIZED))
            if strict:
                _note(result, f"attributed to {', '.join(p.id for p in strict)}, whose words hold no near match")
            results.append(result)
            continue
        close = near(parts, [(k, index.rows[k].text) for k in candidates if withheld(index.rows[k])])
        if close is not None:
            result.verdict = Verdict.ALTERED
            result.compared_with = row_place(close[0], Match.NORMALIZED)
            result.note = "a near match is in a confidential file; the stored words are held back unless asked for"
            results.append(result)
            continue

        # 4. An ellipsis whose parts are stored apart is a splice, not a quotation of one place.
        if len(parts) > 1:
            apart = [index.exact([fp]) for fp in folded_parts]
            if all(apart):
                result.verdict = Verdict.ALTERED
                result.places = [row_place(found[0], Match.NORMALIZED, fp) for found, fp in zip(apart, folded_parts)]
                result.note = ("each part is stored, but the parts are not in order within one passage or section: the "
                               "quotation joins separate places")
                results.append(result)
                continue
            have = sum(1 for found in apart if found)
            if have:
                result.note = f"{have} of its {len(parts)} parts are stored; the others are not"
        results.append(result)

    citations = _citations(cited, provisions, told)
    return Report(results, citations, skipped, given.as_dict(), len(index.rows), round(time.monotonic() - started, 3),
                  include_confidential, as_of)


def _note(result: QuoteCheck, text: str) -> None:
    result.note = "; ".join(part for part in (result.note, text) if part)


def _altered(result: QuoteCheck, found: Sequence[Alignment], place: Place) -> None:
    result.verdict = Verdict.ALTERED
    result.match = None
    result.compared_with = place
    if place.withheld:
        return
    result.quoted = " ... ".join(a.quoted for a in found)
    result.stored = " ... ".join(a.stored for a in found)
    result.differences = [{"quoted": quoted, "stored": stored} for a in found for quoted, stored in a.differences]
    if not result.differences:
        result.note = ("the words are the same; the punctuation differs" if len(found) == 1 else
                       "the words are the same; the punctuation or the order of the parts differs")


def _standing_warnings(result: QuoteCheck, places: Sequence[Place], given: _Sources) -> None:
    best = min(_STANDING_ORDER.get(p.standing, 9) for p in places)
    standing = next(s for s, k in _STANDING_ORDER.items() if k == best)
    if standing in _STANDING_WARNING:
        result.warnings.append(_STANDING_WARNING[standing])
    elif all(p.generated for p in places):
        result.warnings.append(_STANDING_WARNING[pi.Standing.PAGE.value])
    if all(p.withheld for p in places):
        result.warnings.append("found only " + WITHHELD)
    elif all(p.confidential for p in places):
        result.warnings.append("found only in a confidential file: for directors and counsel, never an owner, the "
                               "newsletter, or an open meeting")
    if given.given and not any(p.in_sources for p in places):
        result.warnings.append("found, but not in the sources given: the answer quotes words from outside them")


def _context(text: str, folded_part: str) -> str:
    """The stored words around a quotation, as stored."""
    stored = _Folded.of(text)
    at = stored.folded.find(folded_part)
    if at < 0 or stored.starts is None:
        return ""
    start, end = stored.raw_span(at, at + len(folded_part))
    low, high = max(0, start - CONTEXT_CHARS), min(len(text), end + CONTEXT_CHARS)
    return ("... " if low else "") + " ".join(text[low:high].split()) + (" ..." if high < len(text) else "")


def _citations(cited: Sequence[Located], provisions: _Provisions, told: dict[str, list[dict[str, Any]]]) -> list[CitationCheck]:
    """One row a provision the answer cites, in the answer's order. A whole document is listed only when a quotation
    is attributed to it."""
    out: dict[str, CitationCheck] = {}
    for found in sorted(cited, key=lambda c: c.offset):
        for p in provisions.of(found.target):
            if p.id in out or (p.kind == "document" and p.id not in told):
                continue
            row = CitationCheck(p.id, p.kind, found.offset, p.checked, p.found, source=p.source, page=p.page,
                                caveats=list(p.caveats), reason=p.reason, quotes=told.get(p.id, []), in_force=p.in_force)
            if p.found and p.kind != "document":
                row.digest = p.texts[0][0]
                row.versions = [{"digest": digest} for digest, _ in p.texts]
            if found.prior:
                row.caveats.append("a Davis-Stirling number from before the 2014 renumbering: not the law in force. "
                                   "jason law-history gives its successor.")
            out[p.id] = row
    return list(out.values())


__all__ = ["Alignment", "CAVEATS", "CitationCheck", "Edition", "MIN_WORDS", "Match", "NEAR", "Place", "QuoteCheck",
           "Quotation", "Report", "Verdict", "WITHHELD", "align", "check", "fold", "fold_map", "quotations", "words"]
