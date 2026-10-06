"""An owner's manual taken apart: which words are the operating rules, which copy a higher document, which are policies
bound in, and which are guidance, so the rules can stand as their own document and the manual can be generated.

Many associations keep one document that is both a guide for owners and the board's rules. The rules bind (Civil Code
4340(a): "a regulation adopted by the board that applies generally"); the guide does not. Kept together, a guide's
edit can look like a rule change and a rule change can be lost in a guide's rewrite. This module classifies each
section of such a manual into one ``SectionKind``:

- (a) ``RULE``: an operating rule the board adopted, the words that bind;
- (b) ``COPY``: a copy or restatement of the declaration, the bylaws, or a statute, with its ``CopyState``;
- (c) ``POLICY``: a separately adopted policy bound in (the discipline policy and fine schedule, the collection policy
  and its 5730 notice, the architectural procedure and its form);
- (d) ``GUIDANCE``: contacts, how-to, explanations;
- (e) ``MIXED``: a section split at the sentence level, each piece one of the above.

The classification is rule rows, never a guess: the profile's ``ManualRow`` rows (``Community.owners_manual()``) are
matched to the manual's outline sections in order, the first match wins, and a row's ``Piece`` splits a section where a
sentence starts. The evidence is attached to every piece: the norms the deontic grammar reads in its words
(``jason.community.deontic``) and the copies the embedded-copy scan found (``data/section-refs/copies.json``). Where the
evidence disagrees with a row, or a row says its kind is open, the section is a question for a person
(``jason.community.intake.Ask``), not a guess; an answered question becomes the kind on the next run.

Every piece also gets a ``Target``: its book (``rules``, ``rules.parking``, ``disc``, ``coll``, ``arch``, or ``manual``
for guidance) and its number there. The concordance (old address to new) keeps every number the manual prints; a number
only the outline reader made up (a heading's list glyph read under the section before it) is replaced by the one the
document prints, and the old one stays as an alias, so every existing citation still resolves.

Rendering (``render``) fills a base template's tokens from the classification:

- ``{PART:slot}``: the guidance the profile puts in a slot of the base (``front``, ``welcome``, ``contacts``, ...);
- ``{INCLUDE:book}``, ``{INCLUDE:book#N}``: a whole book, or one section with its subsections; ``official`` renders
  only the rule text (guidance in a rule is left out, with a bracketed note in its place); ``optional`` renders nothing
  for a book the profile does not fill;
- ``{EXCERPTS}``: the governing documents' sections the profile quotes, each as a ``{QUOTE:key#n}``;
- ``{LAW:CIV 5730(a) quoted}``: a statute's words from disk, or the passage the subdivision prints in quotation marks;
- ``{ADOPTION_HISTORY}``: when each part was adopted or changed, from the profile's rows, the rule-change records, and
  a detector's timeline;
- the identity tokens (``{ASSOCIATION_NAME}``) and ``{RULES_TITLE}`` / ``{MANUAL_TITLE}``.

Every rendered piece is a ``Chunk`` that carries its source span, so the rendering is compared with the manual piece by
piece: identical apart from layout, or a labeled change (a copy pulled from its source, a rule read from its own
document). This module is pure; ``jason.tasks.manual`` reads the disk.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Iterable, Protocol


class ManualError(ValueError):
    """The specification and the manual do not fit: a section no row matches, a piece whose words are not there, a
    token that cannot be filled. The message lists every problem; nothing is rendered half."""


class SectionKind(Enum):
    RULE = "rule"              # (a) an operating rule the board adopted (CIV 4340(a))
    COPY = "copy"              # (b) a copy or restatement of the declaration, bylaws, or a statute
    POLICY = "policy"          # (c) a separately adopted policy bound in
    GUIDANCE = "guidance"      # (d) guidance or information
    MIXED = "mixed"            # (e) split at the sentence level
    UNCLEAR = "unclear"        # computed only: a question for a person, with a suggestion

    @property
    def letter(self) -> str:
        return {"rule": "a", "copy": "b", "policy": "c", "guidance": "d", "mixed": "e"}.get(self.value, "?")


CHOICES = (SectionKind.RULE, SectionKind.COPY, SectionKind.POLICY, SectionKind.GUIDANCE)


class CopyState(Enum):
    VERBATIM = "verbatim"      # the source's words (a punctuation slip at most)
    EDITED = "edited"          # the source's words with some changed, added, or left out
    PARAPHRASE = "paraphrase"  # restated in other words
    STALE = "stale"            # matches words the source no longer has
    UNVERIFIED = "unverified"  # the source is not on disk to compare


class AdoptionAction(Enum):
    NOTICED = "noticed"        # a proposed rule change was noticed to the members (4360(a))
    ADOPTED = "adopted"        # adopted (or amended) at a board meeting (4360(b))
    DELIVERED = "delivered"    # the notice of the change went out (4360(c))
    TABLED = "tabled"          # proposed and not decided
    LISTED = "listed"          # on an agenda, with no action recorded
    NO_ACTION = "no action"    # considered; the board chose not to act
    IN_FORCE = "in force"      # a version a dated copy shows was in force (a detector's reading)


# ---------------------------------------------------------------------------------------------------------------------
# The specification's records


@dataclass(frozen=True)
class Locator:
    """A section of the manual's outline: by its number, or by the start of its title when it has none. ``nth`` picks
    one of the sections the outline numbers alike (the second "B-12(i)")."""

    number: str = ""
    title: str = ""
    nth: int = 1

    def matches(self, number: str, title: str, nth: int) -> bool:
        if self.number:
            return number == self.number and nth == self.nth
        return bool(self.title) and not number and title.startswith(self.title) and nth == self.nth

    def text(self) -> str:
        name = self.number or self.title
        return f"{name} ({_ordinal(self.nth)})" if self.nth > 1 else name


FRONT = Locator(title="(front)")          # the words before the first section


def _ordinal(n: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")


@dataclass(frozen=True)
class Target:
    """Where a piece goes: its book (``rules``, ``rules.parking``, ``disc``, ``coll``, ``arch``, or ``manual`` for the
    guide's own words) and its number there. ``number`` set names it outright; else ``renumber`` replaces a prefix of
    the outline's number ("B-18(C)" -> "C"); else the number stays. ``slot`` is where the generated manual shows it when
    that is not the book itself: a note of guidance inside a rule renders in the ``rules`` include."""

    book: str
    number: str = ""
    renumber: tuple[str, str] = ()
    slot: str = ""

    def number_for(self, old: str) -> str:
        if self.number:
            return self.number
        if self.renumber and old.startswith(self.renumber[0]):
            return self.renumber[1] + old[len(self.renumber[0]):]
        return old

    @property
    def top(self) -> str:
        return self.book.partition(".")[0]

    @property
    def where(self) -> str:
        return self.slot or self.top


@dataclass(frozen=True)
class Piece:
    """A sentence-level split: the section's words from ``starts`` (the words that open the piece, found once in the
    section) to the next piece are of this kind and go to this target."""

    starts: str
    kind: SectionKind
    target: Target
    copies: tuple[str, ...] = ()       # what it copies: "ccrs#4.18", "CIV 5730(a)"
    state: CopyState | None = None     # only when no evidence can be read (the law is not on disk)
    note: str = ""


@dataclass(frozen=True)
class ManualRow:
    """One rule row. It matches the section at ``at``; with ``through`` every section from ``at`` to ``through``; with
    ``under`` the section and every section that starts inside its span. ``question`` marks the kind as open: the row's
    kind is the suggestion and a person answers (intake)."""

    at: Locator
    kind: SectionKind
    target: Target
    through: Locator | None = None
    under: bool = False
    copies: tuple[str, ...] = ()
    state: CopyState | None = None
    pieces: tuple[Piece, ...] = ()
    reason: str = ""
    question: str = ""


@dataclass(frozen=True)
class BookSource:
    """The document a book's words are read from when it is not the manual (a parking rules Doc kept apart)."""

    book: str
    document: str
    note: str = ""


@dataclass(frozen=True)
class BookChoice:
    """Why a policy is its own book or a part of ``rules``: a decision a person may revisit."""

    book: str
    title: str
    choice: str
    reason: str


@dataclass(frozen=True)
class AdoptionEvent:
    """One recorded step in a part's history. ``sections`` are the manual's numbers as its outline reads them ("B-7",
    "B-18(C)(a)" for the fine schedule's caption is not needed: "C(a)" in the new numbering is accepted too).
    ``record`` names the profile's rule-change record when there is one; ``source`` is who read it ("minutes",
    "library", "detector"); ``version`` and ``digest`` are a detector's: the dated copy and the section's words in it."""

    on: date | None
    action: AdoptionAction
    sections: tuple[str, ...]
    evidence: str
    record: str = ""
    source: str = "minutes"
    version: str = ""
    digest: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["on"] = self.on.isoformat() if self.on else None
        raw["action"] = self.action.value
        raw["sections"] = list(self.sections)
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AdoptionEvent:
        on = raw.get("on") or raw.get("date")
        return cls(date.fromisoformat(on) if on else None, AdoptionAction(raw["action"]), tuple(raw.get("sections") or ()),
                   raw.get("evidence", ""), raw.get("record", ""), raw.get("source", "detector"), raw.get("version", ""),
                   raw.get("digest", ""), raw.get("note", ""))


@dataclass(frozen=True)
class Excerpt:
    """A governing document's section the generated manual quotes by reference (``{QUOTE:ccrs#4.15}``)."""

    ref: str
    note: str = ""


@dataclass(frozen=True)
class ManualSpec:
    """A profile's manual: which outline, the rule rows, where each book's words come from, why each policy is the
    book it is, the recorded adoptions, and what the guide quotes."""

    document: str
    rows: tuple[ManualRow, ...]
    sources: tuple[BookSource, ...] = ()
    choices: tuple[BookChoice, ...] = ()
    adoptions: tuple[AdoptionEvent, ...] = ()
    excerpts: tuple[Excerpt, ...] = ()
    rules_title: str = "Rules and Regulations"
    manual_title: str = "Owner's Manual"
    book_titles: dict[str, str] = field(default_factory=dict)

    def source_of(self, book: str) -> str:
        for s in self.sources:
            if s.book == book:
                return s.document
        return ""

    def title_of(self, book: str) -> str:
        return self.book_titles.get(book) or self.book_titles.get(book.partition(".")[0]) or book


# ---------------------------------------------------------------------------------------------------------------------
# Evidence


@dataclass(frozen=True)
class CopyHit:
    """A copy the embedded-copy scan found in the manual's text (offsets into the outline's text)."""

    start: int
    end: int
    target: str                # "ccrs#4.18"
    kind: str                  # the scan's: verbatim, near-verbatim, excerpt, paraphrase
    currency: str = ""         # unamended, amended, superseded ...
    coverage: float = 0.0
    fidelity: float = 0.0

    @property
    def state(self) -> CopyState:
        if self.currency == "superseded":
            return CopyState.STALE
        if self.kind == "verbatim":
            return CopyState.VERBATIM
        if self.kind == "paraphrase":
            return CopyState.PARAPHRASE
        return CopyState.EDITED


@dataclass(frozen=True)
class Norm:
    """A norm the deontic grammar read: its kind, bearer, and offset."""

    start: int
    kind: str
    bearer: str
    quote: str


def words(text: str) -> list[str]:
    return re.sub(r"\s+", " ", text or "").strip().split(" ") if (text or "").strip() else []


def compare(copy: str, source: str) -> tuple[CopyState, float, str]:
    """How a copy reads against its source's words: verbatim (a punctuation slip at most), edited, or a paraphrase, the
    ratio of the words, and the first difference in words."""
    a, b = words(source), words(copy)
    plain = lambda ws: [re.sub(r"[^\w$%]", "", w).lower() for w in ws if re.sub(r"[^\w$%]", "", w)]   # noqa: E731
    pa, pb = plain(a), plain(b)
    sm = difflib.SequenceMatcher(None, pa, pb, autojunk=False)
    ratio = sm.ratio()
    # How much of the copy is the source's words, in order: an excerpt of the source reads as edited, not paraphrase.
    contained = sum(blk.size for blk in sm.get_matching_blocks()) / max(1, len(pb))
    first = next((op for op in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if op[0] != "equal"), None)
    diff = ""
    if first:
        tag, i1, i2, j1, j2 = first
        diff = f"{tag}: {' '.join(a[i1:i2])[:80]!r} -> {' '.join(b[j1:j2])[:80]!r}"
    if ratio >= 0.999:
        return CopyState.VERBATIM, ratio, diff
    if ratio >= 0.6 or contained >= 0.6:
        return CopyState.EDITED, ratio, diff
    return CopyState.PARAPHRASE, ratio, diff


# ---------------------------------------------------------------------------------------------------------------------
# Segments: the manual's text, every character in exactly one piece


@dataclass
class Segment:
    locator: Locator
    number: str                        # the outline's number ("" for a titled section)
    title: str
    label: str                         # as the document draws it ("a.", "1.")
    depth: int
    start: int
    end: int
    kind: SectionKind
    target: Target
    new_number: str
    row: ManualRow
    piece: int = 0                     # 0 for the section's head, n for the row's n-th piece
    copies: tuple[str, ...] = ()
    declared_state: CopyState | None = None
    note: str = ""
    norms: list[Norm] = field(default_factory=list)
    hits: list[CopyHit] = field(default_factory=list)
    state: CopyState | None = None     # computed from the evidence (or declared when none can be read)
    evidence: list[str] = field(default_factory=list)
    open: str = ""                     # the question a person has not answered: its kind is a suggestion

    @property
    def old(self) -> str:
        return self.locator.text()

    @property
    def address(self) -> str:
        return f"{self.target.book}#{self.new_number}" if self.new_number else self.target.book

    @property
    def slot(self) -> str:
        return self.target.where

    @property
    def id(self) -> str:
        return f"{self.old}" + (f"/{self.piece}" if self.piece else "")


@dataclass(frozen=True)
class OutlinePlace:
    locator: Locator
    number: str
    title: str
    label: str
    depth: int
    start: int
    end: int                           # the section's own words end where the next section starts
    span_end: int                      # its span with its subsections (the outline's end)


def places(outline: Any) -> list[OutlinePlace]:
    """The outline's sections in the order of the text, each with its own words' span, and the words before the first
    section as ``FRONT``. Sections the outline numbers alike are told apart by ``nth``."""
    sections = sorted(outline.sections, key=lambda s: s.start)
    out: list[OutlinePlace] = []
    if sections and sections[0].start > 0:
        out.append(OutlinePlace(FRONT, "", FRONT.title, "", 0, 0, sections[0].start, sections[0].start))
    elif not sections and outline.text:
        out.append(OutlinePlace(FRONT, "", FRONT.title, "", 0, 0, len(outline.text), len(outline.text)))
    seen: dict[tuple[str, str], int] = {}
    for k, s in enumerate(sections):
        name = (s.number, "" if s.number else s.title)
        seen[name] = seen.get(name, 0) + 1
        loc = Locator(number=s.number, nth=seen[name]) if s.number else Locator(title=s.title, nth=seen[name])
        end = sections[k + 1].start if k + 1 < len(sections) else len(outline.text)
        out.append(OutlinePlace(loc, s.number, s.title, s.label, s.depth, s.start, end, max(s.end, end)))
    return out


def _find(places_: list[OutlinePlace], loc: Locator) -> int | None:
    for i, p in enumerate(places_):
        if p.locator == loc:
            return i
        if loc.number and p.number == loc.number and p.locator.nth == loc.nth:
            return i
        if not loc.number and loc.title and not p.number and p.title.startswith(loc.title) and p.locator.nth == loc.nth:
            return i
    return None


def _row_for(rows: Iterable[ManualRow], places_: list[OutlinePlace], i: int) -> ManualRow | None:
    p = places_[i]
    for row in rows:
        a = _find(places_, row.at)
        if a is None:
            continue
        if row.through is not None:
            b = _find(places_, row.through)
            if b is not None and a <= i <= b:
                return row
        elif row.under:
            if a == i or places_[a].start <= p.start < places_[a].span_end:
                return row
        elif a == i:
            return row
    return None


def segments(outline: Any, spec: ManualSpec) -> list[Segment]:
    """Every character of the manual's text in exactly one segment, each with its row's kind and target. Raises
    ``ManualError`` listing each section no row matches and each piece whose opening words are not in its section."""
    ps = places(outline)
    out: list[Segment] = []
    problems: list[str] = []
    for i, p in enumerate(ps):
        row = _row_for(spec.rows, ps, i)
        if row is None:
            problems.append(f"no row matches {p.locator.text()!r} ({outline.text[p.start:p.start + 50]!r})")
            continue
        own = outline.text[p.start:p.end]
        cuts: list[tuple[int, int, Piece]] = []
        for n, piece in enumerate(row.pieces, start=1):
            at = own.find(piece.starts)
            if at < 0:
                if row.under or row.through is not None:
                    continue                # a piece of a row over many sections splits the one it is in
                problems.append(f"{p.locator.text()}: piece {piece.starts[:40]!r} is not in the section")
                continue
            if own.find(piece.starts, at + 1) >= 0:
                problems.append(f"{p.locator.text()}: piece {piece.starts[:40]!r} occurs more than once")
                continue
            cuts.append((at, n, piece))
        cuts.sort(key=lambda c: c[0])
        bounds = [(0, 0, None)] + cuts
        for k, (at, n, piece) in enumerate(bounds):
            stop = bounds[k + 1][0] if k + 1 < len(bounds) else len(own)
            if stop <= at and n:
                continue
            kind = piece.kind if piece else row.kind
            target = piece.target if piece else row.target
            old_number = p.number
            new_number = target.number_for(old_number) if (target.number or target.renumber or old_number) else ""
            if not new_number and target.book == "manual":
                new_number = p.title if p.locator != FRONT else "front"      # the guide's own words, by their heading
            out.append(Segment(p.locator, p.number, p.title, p.label, p.depth, p.start + at, p.start + stop, kind, target,
                               new_number,
                               row, n, piece.copies if piece else row.copies,
                               piece.state if piece else row.state, piece.note if piece else ""))
    if problems:
        raise ManualError("; ".join(problems))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Classification


GUIDE_BEARERS = {"owner", "member", "occupant"}
BINDING = {"duty", "prohibition"}


@dataclass
class SectionClass:
    """One section's result: its pieces, its kind, and the question when it is open."""

    locator: Locator
    title: str
    segments: list[Segment]
    kind: SectionKind
    suggestion: SectionKind | None = None
    question: str = ""
    answered: str = ""
    evidence: list[str] = field(default_factory=list)
    ask_key: str = ""                  # what the question is keyed by: the row's anchor, shared by its sections

    @property
    def old(self) -> str:
        return self.locator.text()

    @property
    def kinds(self) -> list[SectionKind]:
        return list(dict.fromkeys(s.kind for s in self.segments if s.end > s.start and s.kind is not SectionKind.UNCLEAR))


@dataclass
class Classification:
    document: str
    revision: str
    sections: list[SectionClass]
    findings: list[str] = field(default_factory=list)

    @property
    def segments(self) -> list[Segment]:
        return [s for c in self.sections for s in c.segments]

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in self.sections:
            out[c.kind.value] = out.get(c.kind.value, 0) + 1
        return out


def attach(segs: list[Segment], norms: Iterable[Norm], hits: Iterable[CopyHit], *, law: Any = None,
           book_words: Any = None) -> None:
    """The evidence on each segment: the norms read in its words, the copies found overlapping it, and the state of a
    copy (from the scan, or from the law's words on disk; declared only when neither can be read)."""
    norms, hits = list(norms), list(hits)
    for s in segs:
        s.norms = [n for n in norms if s.start <= n.start < s.end]
        s.hits = [h for h in hits if h.start < s.end and h.end > s.start]
        for n in s.norms:
            s.evidence.append(f"norm: {n.kind}/{n.bearer}: {n.quote[:90]}")
        for h in s.hits:
            share = (min(h.end, s.end) - max(h.start, s.start)) / max(1, s.end - s.start)
            s.evidence.append(f"copy: {h.target} {h.kind} ({h.currency}; covers {share:.0%} of these words, "
                              f"fidelity {h.fidelity:.2f})")
        if s.kind is not SectionKind.COPY:
            continue
        states = {h.state for h in s.hits if not s.copies or any(h.target.startswith(c.split('#')[0] + "#") for c in s.copies)}
        if states:
            s.state = (CopyState.STALE if CopyState.STALE in states else next(iter(states)) if len(states) == 1
                       else CopyState.EDITED)
            continue
        for c in s.copies:
            if law is not None and "#" not in c:
                found = law(c, s)
                if found:
                    state, ratio, diff = compare(book_words(s) if book_words else "", found)
                    s.state = state
                    s.evidence.append(f"law: {c} on disk: {state.value} (words {ratio:.3f})" + (f"; {diff}" if diff else ""))
                    break
        if s.state is None:
            s.state = s.declared_state or CopyState.UNVERIFIED


def _check(c: SectionClass) -> str:
    """The evidence's own question about a section, when it disagrees with the row; empty when it agrees."""
    for s in c.segments:
        if s.kind is SectionKind.GUIDANCE and not s.copies:
            binding = [n for n in s.norms if n.kind in BINDING and n.bearer in GUIDE_BEARERS]
            if binding:
                return (f"The guide's words state a {binding[0].kind} for the {binding[0].bearer} "
                        f"(\"{binding[0].quote[:100]}\") and cite no source. Is it guidance restating the governing "
                        "documents (which section?), or an operating rule (Civil Code 4340(a))?")
        if s.kind is SectionKind.RULE:
            copies = [h for h in s.hits if h.kind in ("verbatim", "near-verbatim")
                      and (min(h.end, s.end) - max(h.start, s.start)) >= 0.8 * (s.end - s.start)]
            if copies:
                return (f"A row reads these words as a rule, but the scan finds them a {copies[0].kind} copy of "
                        f"{copies[0].target}. A rule of the board's own, or a copy of the declaration?")
        if s.kind is SectionKind.COPY and not s.copies and not s.hits:
            return "A row reads these words as a copy, but names no source and the scan finds none: what do they copy?"
    return ""


def classify(outline: Any, spec: ManualSpec, norms: Iterable[Norm] = (), hits: Iterable[CopyHit] = (), *,
             answers: dict[str, str] | None = None, law: Any = None) -> Classification:
    """Each section's kind, by its row and checked against the evidence. ``answers`` maps a section's old address to
    a person's answer (a kind's value): an answered question is the kind."""
    segs = segments(outline, spec)
    text = outline.text
    attach(segs, norms, hits, law=law, book_words=lambda s: text[s.start:s.end])
    answers = answers or {}
    by_place: dict[Locator, list[Segment]] = {}
    for s in segs:
        by_place.setdefault(s.locator, []).append(s)
    out: list[SectionClass] = []
    for p in places(outline):
        mine = by_place.get(p.locator, [])
        c = SectionClass(p.locator, p.title, mine, SectionKind.GUIDANCE)
        kinds = c.kinds or [mine[0].kind if mine else SectionKind.GUIDANCE]
        c.kind = kinds[0] if len(kinds) == 1 else SectionKind.MIXED
        row = mine[0].row if mine else None
        question = (row.question if row else "") or _check(c)
        if question:
            c.ask_key = row.at.text() if row is not None and row.question else c.old
            answer = answers.get(c.ask_key, "")
            chosen = next((k for k in SectionKind if k.value == answer.strip().lower()), None)
            if chosen is not None:
                c.answered = chosen.value
                c.kind = chosen
                for s in mine:
                    if s.piece == 0:
                        s.kind = chosen
            else:
                c.suggestion, c.kind, c.question = c.kind, SectionKind.UNCLEAR, question
                for s in mine:
                    s.open = question
        c.evidence = [e for s in mine for e in s.evidence]
        out.append(c)
    findings = []
    for s in segs:
        if s.kind is SectionKind.RULE and not s.norms and s.end - s.start > 0 and not _caption_only(text[s.start:s.end], s.title):
            findings.append(f"{s.id}: a rule row, and the grammar reads no norm in its words (a phrase the grammar does "
                            f"not know, or a definition): {text[s.start:s.end].strip()[:80]!r}")
    return Classification(spec.document, getattr(outline, "revision", ""), out, findings)


def _caption_only(words_: str, title: str) -> bool:
    return words_.strip() == (title or "").strip() or not words_.strip()


def asks(classification: Classification) -> list[Any]:
    """The open sections as intake questions (``AskKind.SECTION_KIND``): one per row that asks (its sections share it),
    and one per section whose evidence asks."""
    from jason.community.intake import Ask, AskKind, ask_id

    out: dict[str, Any] = {}
    for c in classification.sections:
        if c.kind is not SectionKind.UNCLEAR:
            continue
        subject = f"{classification.document}#{c.ask_key or c.old}"
        if subject in out:
            out[subject].detail["sections"].append(c.old)
            continue
        ev = tuple(c.evidence[:6])
        out[subject] = Ask(ask_id(AskKind.SECTION_KIND, subject, "manual-kind"), AskKind.SECTION_KIND, subject, c.question,
                           tuple(k.value for k in CHOICES), c.suggestion.value if c.suggestion else "", False, ev,
                           {"manual": classification.document, "sections": [c.old], "title": c.title[:90]})
    return list(out.values())


# ---------------------------------------------------------------------------------------------------------------------
# Concordance: every old address to its new one


@dataclass(frozen=True)
class Concordance:
    old: str                   # the manual's address as the outline reads it ("B-12(j)", "B-12(i) (2nd)", a title)
    piece: int
    new: str                   # "rules.parking#B-12(j)"
    kind: str
    official: bool             # in the official rules document
    status: str                # "same number", "moved", "renumbered: ...", "left out of the rules: guidance"
    words: str                 # the piece's first words


def concordance(classification: Classification, text: str) -> list[Concordance]:
    out = []
    for c in classification.sections:
        for s in c.segments:
            if s.end <= s.start:
                continue
            first = re.sub(r"\s+", " ", text[s.start:s.end]).strip()[:70]
            kind = f"unclear: {s.kind.value}?" if s.piece == 0 and c.kind is SectionKind.UNCLEAR else s.kind.value
            official = s.target.top == "rules" and s.kind in (SectionKind.RULE, SectionKind.COPY)
            if s.target.book == "manual":
                status = "left in the manual: guidance" if s.slot == "rules" else "the guide"
            elif s.number and s.new_number == s.number:
                status = "same number"
            elif s.number and s.new_number:
                status = f"renumbered: the outline's {s.number} is the reader's; the document prints {s.new_number}"
            else:
                status = "new address (a section the outline knows by its title)"
            if s.target.top != "rules" and s.target.book != "manual":
                status = f"moved to {s.target.book}; " + status
            out.append(Concordance(s.old, s.piece, s.address, kind, official, status, first))
    return out


def resolve_old(rows: Iterable[Concordance], ref: str) -> str:
    """The new address of an old reference ("B-18(C)(1)", "owners-manual#B-1(d)"); empty when nothing has it. A
    reference to a number the outline reads twice resolves to the first, as the outline's own lookup does."""
    number = (ref.split("#", 1)[1] if "#" in ref else ref).strip()
    rows = [r for r in rows if r.piece == 0]
    for wanted in (number, number.split(" (")[0]):
        for r in rows:
            if r.old == wanted:
                return r.new
        for r in rows:
            if r.old.split(" (")[0] == wanted:
                return r.new
    return ""


# ---------------------------------------------------------------------------------------------------------------------
# Rendering


TOKEN = re.compile(r"\{(?P<verb>INCLUDE|PART|LAW|EXCERPTS|ADOPTION_HISTORY)(?::(?P<arg>(?:[A-Z][A-Z0-9-]* )?[^\s{}]+))?"
                   r"(?P<flags>(?:\s+[a-z][a-z-]*)*)\s*\}")
NAME = re.compile(r"\{([A-Z][A-Z0-9_]+)\}")
EDITORIAL = "editorial"


@dataclass
class Chunk:
    """One rendered piece: its Markdown, the words it was read from, and the manual's span it stands for (none for an
    editorial note). ``label`` names a change from the manual's words, or where the words were read."""

    markdown: str
    words: str = ""
    start: int = -1
    end: int = -1
    segment: str = ""
    label: str = ""
    kind: str = ""


class Source(Protocol):
    def words(self, segment: Segment) -> tuple[str, str]: ...        # (the words, the label when read elsewhere)

    def law(self, citation: str, quoted: bool) -> tuple[str, str]: ...

    def excerpt(self, ref: str) -> str: ...

    def history(self) -> list[AdoptionEvent]: ...


def _is_heading(line: str, s: Segment) -> bool:
    line = line.strip()
    if not line or line != (s.title or "").strip() or line.endswith((".", ":", ";", ",")):
        return False
    return not s.label or line.isupper()           # a list item that is all title ("c. Legal action") is no heading


def segment_markdown(s: Segment, text: str) -> str:
    """A segment's words as Markdown: a caption as a heading, a list item with the label the document draws, every
    other line its own paragraph. The words themselves are not changed."""
    lines = [ln.rstrip() for ln in (text or "").split("\n")]
    out: list[str] = []
    first = True
    for ln in lines:
        if not ln.strip():
            continue
        if first and s.piece == 0 and _is_heading(ln, s):
            level = 2 if s.label in PART_LABELS or s.locator == FRONT else 3 if s.depth <= 2 else 4
            out.append(f"{'#' * level} {(s.label + ' ') if s.label and s.label not in ln else ''}{ln.strip()}")
        elif first and s.piece == 0 and s.label:
            out.append(f"**{s.label}** {ln.strip()}")
        else:
            out.append(_escape(ln.strip()))
        first = False
    return "\n\n".join(out)


PART_LABELS = ("A.", "B.", "C.", "D.", "E.")


def _escape(line: str) -> str:
    """A line that Markdown would read as a list or heading is escaped; its words stay."""
    if re.match(r"^(\d+[.)]|[-*+#>])\s", line):
        return "\\" + line
    return line


def _slot_segments(classification: Classification, slot: str, number: str = "") -> list[Segment]:
    segs = [s for s in classification.segments if s.slot == slot and s.end > s.start]
    if number:
        inside = [s for s in segs if s.new_number == number or s.new_number.startswith(number + "(")
                  or (s.new_number.startswith(number) and s.new_number[len(number):len(number) + 1] in (".", "-"))]
        segs = inside
    return segs


def _include(classification: Classification, source: Source, spec: ManualSpec, book: str, number: str,
             official: bool, text: str, passages: Iterable[Passage] = (), current: bool = False) -> list[Chunk]:
    chunks: list[Chunk] = []
    segs = _slot_segments(classification, book, number)
    # The (b) passages, in the official rules only: shown in place of the working words they cover (or after them,
    # with ``current``), and a removed passage after the piece it follows.
    first: dict[str, list[Passage]] = {}
    last: dict[str, list[Passage]] = {}
    after: dict[str, list[Passage]] = {}
    covered: set[str] = set()
    loose: list[Passage] = []
    if official and book == "rules":
        ids = {s.id for s in segs}
        for p in passages:
            if p.top != "rules":
                continue
            mine = [i for i in p.segments if i in ids]
            if mine:
                first.setdefault(mine[0], []).append(p)
                last.setdefault(mine[-1], []).append(p)
                covered.update(mine)
            elif p.follows in ids:
                after.setdefault(p.follows, []).append(p)
            elif not number and not p.segments and not p.follows:
                loose.append(p)
    for s in segs:
        rule_text = s.kind in (SectionKind.RULE, SectionKind.COPY) and s.target.top == "rules"
        if official and book == "rules" and not rule_text:
            first_words = re.sub(r"\s+", " ", text[s.start:s.end]).strip()
            what = {"guidance": "Guidance", "policy": "A policy"}.get(s.kind.value, s.kind.value.title())
            chunks.append(Chunk(f"_[{what} left in the {spec.manual_title}: “{first_words[:60]}…” "
                                f"({s.old}{'/' + str(s.piece) if s.piece else ''}).]_", kind=EDITORIAL,
                                label="left out of the official rules", segment=s.id))
            for p in after.get(s.id, ()):
                chunks += _passage_chunks(p, current=current)
            continue
        if s.id in covered and not current:
            for p in first.get(s.id, ()):
                chunks += _passage_chunks(p, current=False)
            for p in after.get(s.id, ()):
                chunks += _passage_chunks(p, current=False)
            continue
        got, label = source.words(s)
        chunks.append(Chunk(segment_markdown(s, got), got, s.start, s.end, s.id, label, s.kind.value))
        if official and s.kind is SectionKind.COPY and s.copies:
            cite = getattr(source, "cite", lambda ref: ref)
            note = f"_[Restates {', '.join(cite(c) for c in s.copies)} ({s.state.value if s.state else 'unverified'}).]_"
            if len(chunks) > 1 and chunks[-2].kind == EDITORIAL and chunks[-2].markdown == note:
                chunks.pop(-2)                      # one note after a run of pieces that copy the same source
            chunks.append(Chunk(note, kind=EDITORIAL, label="a copy kept in the rules", segment=s.id))
        if official and s.open:
            note = "_[An open question: whether these words are a rule is for the board (jason intake). Kept as written.]_"
            if len(chunks) > 1 and chunks[-2].kind == EDITORIAL and chunks[-2].markdown == note:
                chunks.pop(-2)
            chunks.append(Chunk(note, kind=EDITORIAL, label="an open question", segment=s.id))
        if current:
            for p in last.get(s.id, ()):
                chunks += _passage_chunks(p, current=True)
        for p in after.get(s.id, ()):
            chunks += _passage_chunks(p, current=current)
    for p in loose:
        chunks += _passage_chunks(p, current=current)
    return chunks


@dataclass(frozen=True)
class Passage:
    """(b) A passage of the manual whose words changed in the working copy with no adoption found in the board's
    records (the revision history, ``jason revisions``; separated by ``jason.tasks.manual_rule_change``).

    ``earlier`` is the passage's words before the change ("" when the passage is new) and ``working`` its words now (""
    when it was removed). ``basis`` names the adoption on record those earlier words carry ("2022-08-30 (a record)");
    empty when no adopted version of the passage is on record, so its adopted words are not known. ``segments`` are the
    rendered pieces the working words are; a passage with no working words is shown after ``follows``. A passage with
    neither is shown at the end of its book."""

    address: str
    number: str                        # the manual's number as its outline reads it
    kind: str                          # reworded, added, removed, split, merged
    from_on: str
    to_on: str
    earlier: str
    working: str
    basis: str = ""
    segments: tuple[str, ...] = ()
    follows: str = ""
    book_title: str = ""

    @property
    def known(self) -> bool:
        return bool(self.basis)

    @property
    def top(self) -> str:
        return self.address.split("#", 1)[0].partition(".")[0]


PASSAGE_LABEL = "jason's note, not rule text"


def _q(words: str) -> str:
    return "“" + " ".join((words or "").split()) + "”"


def passage_note(p: Passage, *, current: bool = False) -> str:
    """jason's bracketed note on a (b) passage. With ``current`` the working words are printed and the note recites
    the last adopted words; otherwise the last adopted words are printed (when known) and the note recites the working
    words. Where no adopted version is on record the note says so and names the earlier words only as a version's."""
    verb = {"added": "Added", "split": "Added (split from another passage)", "removed": "Removed",
            "merged": "Removed (merged into another passage)"}.get(p.kind, "Changed")
    if not p.segments and p.number:
        verb += f" (the manual's {p.number})"
    said = [f"{verb} between {p.from_on} and {p.to_on}; no adoption found."]
    if p.known and not current:
        if not p.earlier:
            said.append(f"The last adopted version has no such passage (adopted {p.basis}), so none is printed as a "
                        "rule.")
        else:
            said.append(f"The words printed are the last adopted (adopted {p.basis}).")
        said.append(f"The working text reads: {_q(p.working)}" if p.working else "The working text leaves them out.")
    elif p.known:
        said.append(f"The last adopted words (adopted {p.basis}) read: {_q(p.earlier)}" if p.earlier else
                    f"The last adopted version has no such passage (adopted {p.basis}).")
        if not p.working:
            said.append("The working text leaves them out.")
    else:
        said.append("No adopted version of this passage is on record, so its adopted words are not known"
                    + ("." if current else " and none are printed as a rule."))
        said.append(f"The version of {p.from_on} reads: {_q(p.earlier)}" if p.earlier else
                    f"The version of {p.from_on} has no such passage.")
        if not current:
            said.append(f"The working text reads: {_q(p.working)}" if p.working else "The working text leaves it out.")
        elif not p.working:
            said.append("The working text leaves it out.")
    return f"_[{PASSAGE_LABEL}: " + " ".join(said) + "]_"


def _passage_chunks(p: Passage, *, current: bool) -> list[Chunk]:
    """The passage in the official rules: the last adopted words (when known and not ``current``), then the note."""
    out = []
    if not current and p.known and p.earlier:
        out.append(Chunk(_escape(" ".join(p.earlier.split())), p.earlier, kind="adopted",
                         label="the last adopted words (b)", segment=p.address))
    out.append(Chunk(passage_note(p, current=current), kind=EDITORIAL, label="changed with no adoption found",
                     segment=p.address))
    return out


def _history_lines(spec: ManualSpec, events: list[AdoptionEvent], rows: list[Concordance],
                   passages: Iterable[Passage] = (), *, current: bool = False) -> list[str]:
    if not events:
        lines = ["_No adoption is recorded yet: the minutes and the library have none for these parts._"]
    else:
        lines = ["| Date | Action | Parts | Evidence |", "|---|---|---|---|"]
        for e in sorted(events, key=lambda e: (e.on or date.max, e.action.value)):
            parts = []
            for sec in e.sections:
                new = resolve_old(rows, sec) or next((r.new for r in rows if r.new.endswith("#" + sec)), sec)
                parts.append(new.split("#", 1)[1] if new.startswith("rules#") else new)
            lines.append(f"| {e.on.isoformat() if e.on else '(undated)'} | {e.action.value} | {', '.join(parts)} | "
                         f"{e.evidence}{' (' + e.record + ')' if e.record else ''}{'; ' + e.note if e.note else ''} |")
    passages = sorted(passages, key=lambda p: (p.top != "rules", p.address, p.to_on))
    if passages:
        shown = ("the working words are printed and jason's note recites the last adopted words" if current else
                 "the last adopted words are printed where they are known, and jason's note recites the working words")
        lines += ["", f"_Changed with no adoption found (jason's finding from the revision history, not a record of "
                      f"the board; \"no adoption found\" is not proof that none happened). In the {spec.rules_title}, "
                      f"{shown}._", "",
                  "| Passage | Changed | The last adopted words |", "|---|---|---|"]
        for p in passages:
            where = p.book_title or spec.title_of(p.address.split("#", 1)[0])
            number = p.address.split("#", 1)[1] if "#" in p.address else p.number
            lines.append(f"| {where} {number} | {p.kind}, {p.from_on} to {p.to_on} | "
                         f"{'adopted ' + p.basis if p.known else 'not known: no adopted version on record'} |")
    return lines


def fill_token(token: str, verb: str, arg: str, flags: set[str], classification: Classification, spec: ManualSpec,
               source: Source, text: str, rows: list[Concordance], passages: list[Passage],
               current: bool = False) -> list[Chunk]:
    """The chunks one template token stands for. ``render`` calls it for each token, and a document template's blocks
    (``jason.community.document_templates``) call it for the same words, so the two cannot differ. A token that cannot
    be filled raises ``ManualError``."""
    made: list[Chunk] = []
    if verb == "PART":
        made = _include(classification, source, spec, arg, "", False, text)
        if not made and "optional" not in flags:
            raise ManualError(f"{token}: the profile puts nothing in the slot {arg!r}")
    elif verb == "INCLUDE":
        book, _, number = arg.partition("#")
        made = _include(classification, source, spec, book, number, "official" in flags, text, passages, current)
        if not made and "optional" not in flags:
            raise ManualError(f"{token}: the profile maps nothing to {arg!r}")
        if made and "official" in flags and book == "rules":
            firsts: dict[str, int] = {}
            for s in classification.segments:
                if s.target.top not in ("rules", "manual"):
                    firsts.setdefault(s.target.top, s.start)
            for other in sorted(firsts, key=firsts.__getitem__):
                made.append(Chunk(f"_[{spec.title_of(other)}: published as its own document ({other}); "
                                  "see the concordance.]_", kind=EDITORIAL, label="a part published apart"))
    elif verb == "LAW":
        got, label = source.law(arg, "quoted" in flags)
        made = [Chunk(got.strip(), got, kind="law", label=label)]
    elif verb == "EXCERPTS":
        made = [Chunk(source.excerpt(e.ref), kind="excerpt", label=f"quoted from {e.ref}") for e in spec.excerpts]
    elif verb == "ADOPTION_HISTORY":
        made = [Chunk("\n".join(_history_lines(spec, source.history(), rows, passages, current=current)),
                      kind=EDITORIAL, label="adoption history")]
    return made


def render(template: str, classification: Classification, spec: ManualSpec, source: Source, text: str, *,
           values: dict[str, str] | None = None, passages: Iterable[Passage] = (),
           current: bool = False) -> tuple[str, list[Chunk]]:
    """The template with its tokens filled. Returns the Markdown and the chunks. A token that cannot be filled raises
    ``ManualError`` (a book the profile does not fill renders nothing only when the token says ``optional``).

    ``passages`` are the (b) passages: ``{INCLUDE:rules official}`` prints each one's last adopted words in place of its
    working words, with jason's note (``current``: the working words, with the note reciting the adopted ones), and
    ``{ADOPTION_HISTORY}`` lists them."""
    passages = list(passages)
    values = dict(values or {})
    values.setdefault("RULES_TITLE", spec.rules_title)
    values.setdefault("MANUAL_TITLE", spec.manual_title)
    rows = concordance(classification, text)
    chunks: list[Chunk] = []
    problems: list[str] = []
    pieces: list[str] = []
    at = 0
    body = re.sub(r"^<!--.*?-->\s*", "", template, flags=re.S)       # the base's header comment is not printed
    for m in TOKEN.finditer(body):
        lead = body[at:m.start()]
        pieces.append(NAME.sub(lambda n: values.get(n.group(1), n.group(0)), lead))
        if lead.strip():
            chunks.append(Chunk(NAME.sub(lambda n: values.get(n.group(1), n.group(0)), lead).strip(), kind=EDITORIAL,
                                label="the template's own words"))
        at = m.end()
        verb, arg, flags = m.group("verb"), m.group("arg") or "", set((m.group("flags") or "").split())
        try:
            made = fill_token(m.group(0), verb, arg, flags, classification, spec, source, text, rows, passages, current)
        except ManualError as exc:
            problems.append(str(exc))
            continue
        chunks.extend(made)
        pieces.append("\n\n".join(c.markdown for c in made if c.markdown))
    tail = body[at:]
    pieces.append(NAME.sub(lambda n: values.get(n.group(1), n.group(0)), tail))
    if problems:
        raise ManualError("; ".join(problems))
    out = "".join(pieces)
    out = re.sub(r"\n{3,}", "\n\n", out).strip() + "\n"
    return out, chunks


# ---------------------------------------------------------------------------------------------------------------------
# The rendering beside the manual


@dataclass
class Difference:
    segment: str
    label: str
    detail: str


@dataclass
class RenderCheck:
    covered: bool                      # every word of the manual is in one rendered chunk, in order
    missing: list[str]                 # spans of the manual no chunk renders
    out_of_order: list[str]
    same: int                          # chunks whose words are the manual's
    labeled: list[Difference]          # chunks whose words differ, with the reason
    unlabeled: list[Difference]        # chunks whose words differ with no reason: a defect


def check(chunks: list[Chunk], text: str) -> RenderCheck:
    """The rendering beside the manual's text, chunk by chunk: words equal apart from layout (spacing, the Markdown
    added), or a labeled difference."""
    placed = [c for c in chunks if c.start >= 0]
    covered_spans = sorted((c.start, c.end) for c in placed)
    missing, at = [], 0
    for s, e in covered_spans:
        if s > at and text[at:s].strip():
            missing.append(f"{at}-{s}: {text[at:s].strip()[:60]!r}")
        at = max(at, e)
    if at < len(text) and text[at:].strip():
        missing.append(f"{at}-{len(text)}: {text[at:].strip()[:60]!r}")
    order = [c.start for c in placed]
    out_of_order = [placed[i].segment for i in range(1, len(order)) if order[i] < order[i - 1]]
    same, labeled, unlabeled = 0, [], []
    for c in placed:
        if words(c.words) == words(text[c.start:c.end]):
            same += 1
            continue
        _, ratio, diff = compare(c.words, text[c.start:c.end])
        d = Difference(c.segment, c.label, f"words {ratio:.3f}; {diff}")
        (labeled if c.label else unlabeled).append(d)
    return RenderCheck(not missing, missing, out_of_order, same, labeled, unlabeled)


__all__ = ["AdoptionAction", "AdoptionEvent", "BookChoice", "BookSource", "CHOICES", "Chunk", "Classification",
           "Concordance", "CopyHit", "CopyState", "Difference", "Excerpt", "FRONT", "Locator", "ManualError", "ManualRow",
           "ManualSpec", "Norm", "PASSAGE_LABEL", "Passage", "Piece", "RenderCheck", "SectionClass", "SectionKind",
           "Segment", "Source", "Target", "asks", "attach", "check", "classify", "compare", "concordance",
           "fill_token",
           "passage_note", "places", "render", "resolve_old",
           "segment_markdown", "segments", "words"]
