"""Readings of the law and of the governing documents, kept apart from the words they read.

The body of authorities is the words: a statute's section on the shelf (``data/authorities``,
``jason.community.law_text``), or a section of a governing document as jason keeps it
(``jason.tasks.section_refs.DiskResolver``). A **reading** is a derived record: what a person or counsel takes the
words to mean, in answer to one question. A ``LawReading`` names each provision it reads with the digest of the words
it read, so:

- it is never shown in place of the words: ``recite`` gives the provision's words first, then each reading, labeled
  as a reading and whose it is;
- it is not needed where the words are plain: the record then says ``PLAIN``, quotes the words that answer, and
  carries no reading text;
- it is stale when any provision it reads has changed (``status``): the digest no longer matches, and the reading is
  listed apart, never applied, until a person redoes or confirms it against the words now on disk;
- it gets no deference for being stored: it is checked against the text every time it is used.

The board's and counsel's readings are profile data (``Community.law_readings()``, empty by default). jason records a
reading a person gave; it never makes one up. A row whose ``whose`` is ``Whose.JASON`` is a lead for a person to
confirm or reject, and is labeled so wherever it is shown.

``status`` and ``recite`` read the disk only. A statute that is not on the shelf is a miss; nothing is fetched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from jason.community.law_text import MIN_DIGEST, normal_citation, same_digest

_HEX = re.compile(r"^[0-9a-f]+$")


class ReadingStanding(Enum):
    PLAIN = "plain"                   # the words answer the question; they are quoted, and no reading is given
    READING = "reading"               # a labeled reading: whose, and the canon or authority it rests on
    TWO_READINGS = "two_readings"     # two readings remain; the board asks counsel


class Whose(Enum):
    JASON = "jason"                   # a lead only: no person has adopted it
    BOARD = "board"
    COUNSEL = "counsel"


class Canon(Enum):
    """The rules of construction a reading may rest on, each with the statute that states it
    (docs/interpretation.md). The statutes' words are on the shelf; a canon is an aid, never an override (Civil Code
    3509)."""

    PLAIN_WORDS = "plain_words"                       # clear and explicit language governs
    WRITING_ALONE = "writing_alone"                   # intention from the writing alone, if possible
    ORDINARY_SENSE = "ordinary_sense"                 # words in their ordinary and popular sense
    GIVE_EFFECT = "give_effect"                       # the reading that gives effect over one that makes void
    EFFECT_TO_ALL = "effect_to_all"                   # nothing inserted or omitted; effect to every provision
    INTENT = "intent"                                 # the Legislature's or the parties' intention is pursued
    PARTICULAR_OVER_GENERAL = "particular_over_general"
    WHOLE_TOGETHER = "whole_together"                 # the whole together, each clause helping to interpret the other
    LAWFUL_AND_OPERATIVE = "lawful_and_operative"     # lawful, operative, definite, reasonable
    LIBERAL_CONSTRUCTION = "liberal_construction"     # a declaration, to facilitate the development's operation
    ORDER_OF_AUTHORITY = "order_of_authority"         # to the extent of any conflict, the higher authority prevails

    @property
    def citation(self) -> str:
        return _CANON_CITATIONS[self]


_CANON_CITATIONS = {
    Canon.PLAIN_WORDS: "CIV 1638",
    Canon.WRITING_ALONE: "CIV 1639",
    Canon.ORDINARY_SENSE: "CIV 1644",
    Canon.GIVE_EFFECT: "CIV 3541",
    Canon.EFFECT_TO_ALL: "CCP 1858",
    Canon.INTENT: "CCP 1859",
    Canon.PARTICULAR_OVER_GENERAL: "CCP 1859",
    Canon.WHOLE_TOGETHER: "CIV 1641",
    Canon.LAWFUL_AND_OPERATIVE: "CIV 1643",
    Canon.LIBERAL_CONSTRUCTION: "CIV 4215",
    Canon.ORDER_OF_AUTHORITY: "CIV 4205",
}


@dataclass(frozen=True)
class Provision:
    """One provision a reading reads, with the digest of the words it read.

    ``citation`` is a statute's section as the shelf writes it ("CIV 5855"; a subdivision may follow, and the digest
    is still the whole section's), or a section of a governing document as a reference names it: the document's key,
    ``#``, and the section number ("bylaws#7.2"). ``digest`` is the one ``recite`` prints for those words: the
    SHA-256 of a statute section's words (``law_text.section_digest``), or a governing section's
    ``SectionText.digest``. Its first ``MIN_DIGEST`` characters or more are enough."""

    citation: str
    digest: str

    def __post_init__(self) -> None:
        digest = self.digest.strip().lower()
        if len(digest) < MIN_DIGEST or not _HEX.match(digest):
            raise ValueError(f"{self.citation}: a provision carries the digest of the words read "
                             f"({MIN_DIGEST} or more hex characters)")
        if not self.governing and normal_citation(self.citation) is None:
            raise ValueError(f"{self.citation!r}: a provision is a code and a section (CIV 5855) or a document's "
                             "section (bylaws#7.2)")
        object.__setattr__(self, "digest", digest)

    @property
    def governing(self) -> bool:
        """A section of a governing document, not of the law."""
        return "#" in self.citation

    @property
    def base(self) -> str:
        """What is looked up: the statute's section without a subdivision, or the document's section."""
        if self.governing:
            return _governing_target(self.citation)
        return normal_citation(self.citation)[0]


def _governing_target(citation: str) -> str:
    from jason.community.outlines import normalize_number

    key, _, number = citation.partition("#")
    return f"{key.strip()}#{normalize_number(number)}"


def target_of(citation: str) -> str | None:
    """A citation as ``recite`` and ``status`` look it up: "civ-5855" is "CIV 5855", "bylaws#7.2." is "bylaws#7.2".
    None when it is neither a statute's section nor a document's section."""
    if "#" in (citation or ""):
        return _governing_target(citation)
    found = normal_citation(citation)
    return found[0] if found else None


@dataclass(frozen=True)
class LawReading:
    """One answer to one question about the words of one or more provisions.

    A ``PLAIN`` record has no reading text: the words answer the question, and ``quote`` points to the ones that do.
    A ``READING`` has the reading in a sentence and what it rests on (``canon`` or ``authority``). A ``TWO_READINGS``
    record names both in ``alternatives`` and prefers neither: the board asks counsel."""

    key: str
    provisions: tuple[Provision, ...]
    question: str                        # what was asked of the words
    standing: ReadingStanding
    whose: Whose
    dated: date
    reading: str = ""                    # the reading in a sentence; empty for PLAIN and for TWO_READINGS
    canon: Canon | None = None           # the rule of construction relied on
    authority: str = ""                  # or the authority relied on: a case, counsel's letter, a resolution
    alternatives: tuple[str, ...] = ()   # TWO_READINGS: both readings
    quote: str = ""                      # the words that answer, verbatim from a provision it reads ("..." marks an omission)
    board_item: str = ""                 # the board's action item that follows it

    def __post_init__(self) -> None:
        if not self.key or not self.question.strip():
            raise ValueError(f"{self.key or 'a reading'}: a reading has a key and the question asked of the words")
        if not self.provisions:
            raise ValueError(f"{self.key}: a reading names the provisions it reads")
        if self.standing is ReadingStanding.PLAIN:
            if self.reading or self.alternatives:
                raise ValueError(f"{self.key}: where the words are plain they are quoted; the record carries no reading")
        elif self.standing is ReadingStanding.READING:
            if not self.reading.strip() or self.alternatives:
                raise ValueError(f"{self.key}: a reading is given in a sentence, and it is one reading")
            if self.canon is None and not self.authority.strip():
                raise ValueError(f"{self.key}: a reading names the canon or authority it rests on")
        else:
            if len(self.alternatives) != 2 or not all(a.strip() for a in self.alternatives) or self.reading:
                raise ValueError(f"{self.key}: where two readings remain the record names both and prefers neither")

    @property
    def lead(self) -> bool:
        """jason's own: for a person to confirm or reject, never applied as the board's or counsel's."""
        return self.whose is Whose.JASON

    def reads(self, citation: str) -> bool:
        target = target_of(citation)
        return target is not None and any(p.base == target for p in self.provisions)


class ReadingState(Enum):
    CURRENT = "current"       # every provision's words still have the digest the reading read
    STALE = "stale"           # a provision's words changed since: not applied until redone or confirmed
    MISSING = "missing"       # a provision is not on the shelf: not applied
    MISQUOTED = "misquoted"   # the words the record points to are not in the provisions it reads: not applied


@dataclass(frozen=True)
class ProvisionStatus:
    citation: str
    state: ReadingState
    read: str                 # the digest the reading carries
    now: str = ""             # the digest of the words on disk; empty when the provision is missing
    detail: str = ""          # why it is missing, or where the replaced words are kept


@dataclass(frozen=True)
class ReadingStatus:
    key: str
    state: ReadingState
    provisions: tuple[ProvisionStatus, ...]
    detail: str = ""

    @property
    def applies(self) -> bool:
        """Only a current reading may be applied."""
        return self.state is ReadingState.CURRENT

    @property
    def changed(self) -> tuple[ProvisionStatus, ...]:
        return tuple(p for p in self.provisions if p.state is not ReadingState.CURRENT)

    def line(self) -> str:
        if self.state is ReadingState.CURRENT:
            return "current: the words it read are the words on disk"
        if self.state is ReadingState.MISQUOTED:
            return f"misquoted: {self.detail}"
        parts = []
        for p in self.changed:
            if p.state is ReadingState.MISSING:
                parts.append(f"{p.citation} is not on the shelf" + (f" ({p.detail})" if p.detail else ""))
            else:
                parts.append(f"{p.citation} changed: it read digest {p.read[:MIN_DIGEST]}, the words on disk have "
                             f"{p.now[:MIN_DIGEST]}" + (f" ({p.detail})" if p.detail else ""))
        return f"{self.state.value}: " + "; ".join(parts)


@dataclass(frozen=True)
class ProvisionText:
    """A provision's words as jason holds them, or a miss with its reason."""

    citation: str
    found: bool
    words: str = ""
    digest: str = ""
    source: str = ""                     # who published the words, or which instrument set them
    note: str = ""                       # jason's own note on the words (a statute's history line), never part of them
    caveats: tuple[str, ...] = ()
    reason: str = ""
    # The other versions of a statute's section the shelf holds under the same number, each with its own digest.
    others: tuple[ProvisionText, ...] = ()
    # For a statute asked as of a day (``law_text.in_force``): how jason knows these were the words in force that
    # day ("prior", "current", "own_words"), or "not_shown" when the disk does not show it and the words given are
    # the words on the shelf now; the basis in a sentence; and the section's own words that decide it.
    decided: str = ""
    basis: str = ""
    quotes: tuple[str, ...] = ()

    @property
    def versions(self) -> tuple[ProvisionText, ...]:
        return (self, *self.others) if self.found else ()


def provision_text(citation: str, data_dir: Path, *, community: Any = None, as_of: date | None = None) -> ProvisionText:
    """The words of a statute's section from the shelf, or of a governing document's section as jason keeps it (on
    ``as_of`` when the document is kept as amended). Reads the disk only."""
    target = target_of(citation)
    if target is None:
        return ProvisionText(citation, False, reason="say a code and a section (CIV 5855) or a document's section (bylaws#7.2)")
    if "#" in target:
        return _governing_text(target, Path(data_dir), community, as_of)
    return _statute_text(target, Path(data_dir), as_of)


def _statute_text(citation: str, data_dir: Path, as_of: date | None) -> ProvisionText:
    from jason.community import law_text

    held = law_text.versions(citation, data_dir)
    if as_of is not None:
        return _statute_as_of(citation, data_dir, as_of, held)
    if not held:
        earlier = law_text.history_texts(citation, data_dir)
        return ProvisionText(citation, False, reason="not on the shelf (data/authorities); jason export-authorities "
                                                     "or jason cite brings it down"
                             + (f". The history holds {len(earlier)} earlier version(s): say the day asked about (--as-of)"
                                if earlier else ""))
    found = held[0]
    caveats: list[str] = []
    if len(held) > 1:
        caveats.append(f"the shelf holds {len(held)} versions of {citation} under the one number; each is recited with "
                       "its digest, in the publication's order, which is not the order they operate in. Say the day "
                       "asked about (--as-of) and jason picks by the versions' own operative words, where they state them")
    others = tuple(ProvisionText(citation, True, t.words, t.digest, t.source, t.note) for t in held[1:])
    return ProvisionText(citation, True, found.words, found.digest, found.source, found.note, tuple(caveats), others=others)


def _statute_as_of(citation: str, data_dir: Path, as_of: date, held: list[Any]) -> ProvisionText:
    """A statute's section as of a day: the words in force that day where the disk shows which they were (an earlier
    version with its range, or the current words), else the words on the shelf now, said plainly not to be shown as
    the words of that day. Never a guess."""
    from jason.community import law_text

    day = as_of.isoformat()
    found = law_text.in_force(citation, data_dir, as_of)
    caveats = list(found.caveats)
    if found.text is not None:
        text = found.text
        source = text.source or "not recorded"
        if found.decided is law_text.Decided.PRIOR:
            now = ", ".join(t.digest[:MIN_DIGEST] for t in held)
            caveats.insert(0, "these are not the words on the shelf now" + (f" (digest {now})" if now else
                                                                          f": {citation} is no longer on the shelf"))
        return ProvisionText(citation, True, text.words, text.digest, source, text.note if text.current else "",
                             tuple(caveats), decided=found.decided.value, basis=found.basis, quotes=found.quotes)
    if not held:
        return ProvisionText(citation, False, reason=f"{found.basis}: " + "; ".join(caveats), decided=found.decided.value)
    for row in law_text.changes(data_dir, citation):
        if str(row.get("when") or "") > day:
            caveats.append(f"jason's copy of these words was replaced on {row.get('when')}, after {day}; the words "
                           f"held before are kept under digest {str(row.get('old') or '')[:MIN_DIGEST]} ({row.get('history')})")
    if len(held) > 1:
        caveats.insert(0, f"the shelf holds {len(held)} versions of {citation} under the one number; each is recited "
                          "with its digest, and their own words do not show which was in force that day")
    first = held[0]
    others = tuple(ProvisionText(citation, True, t.words, t.digest, t.source, t.note) for t in held[1:])
    return ProvisionText(citation, True, first.words, first.digest, first.source, first.note, tuple(caveats), others=others,
                         decided=found.decided.value, basis=found.basis)


def _governing_text(target: str, data_dir: Path, community: Any, as_of: date | None) -> ProvisionText:
    from jason.community.section_refs import CAVEAT, SectionRefError
    from jason.tasks.section_refs import DiskResolver

    key, _, number = target.partition("#")
    resolver = DiskResolver(data_dir, community)
    caveats = [CAVEAT]
    try:
        try:
            text = resolver.section(key, number, as_of)
        except SectionRefError as exc:
            if as_of is None or exc.reason != "not_kept_as_amended":
                raise
            text = resolver.section(key, number, None)
            caveats.append(f"{key} is not kept as amended: these are its words now, which may differ from the words "
                           f"in force on {as_of.isoformat()}")
    except SectionRefError as exc:
        return ProvisionText(target, False, reason=str(exc))
    source = text.document + (f", as set by {text.set_by_title}" if text.set_by_title and text.set_by_title != text.document else "")
    if text.dated:
        source += f" ({text.dated.isoformat()})"
    if text.note:
        caveats.append(text.note)
    return ProvisionText(target, True, text.words, text.digest, source, "", tuple(caveats))


def _quoted(quote: str, words: str) -> bool:
    """Whether ``quote`` is in ``words`` verbatim, spacing aside; "..." marks an omission between two runs."""
    flat = " ".join(words.split())
    at = 0
    for piece in re.split(r"\.\.\.|…", quote):
        piece = " ".join(piece.split())
        if not piece:
            continue
        found = flat.find(piece, at)
        if found < 0:
            return False
        at = found + len(piece)
    return True


def status(reading: LawReading, data_dir: Path, *, community: Any = None, as_of: date | None = None) -> ReadingStatus:
    """Whether a reading still reads the words on disk: CURRENT when every provision's digest matches (a version on
    the shelf, when it holds two), STALE (naming each provision that changed, with the digest read and the digest
    now) when one does not, MISSING when a provision is not on the shelf. A reading that is not CURRENT is never
    applied."""
    from jason.community import law_text

    found: list[ProvisionStatus] = []
    texts: list[str] = []
    for p in reading.provisions:
        text = provision_text(p.base, data_dir, community=community, as_of=as_of)
        read = next((v for v in text.versions if same_digest(p.digest, v.digest)), None)
        if not text.found:
            found.append(ProvisionStatus(p.citation, ReadingState.MISSING, p.digest, detail=text.reason))
        elif read is not None:
            found.append(ProvisionStatus(p.citation, ReadingState.CURRENT, p.digest, read.digest))
            texts.append(read.words)
        else:
            kept = None if p.governing else law_text.law_text(p.base, data_dir, p.digest)
            if kept is not None and kept.current:
                # Asked as of a day: the words it read are on the shelf, and another version governed that day.
                detail = "the words it read are on the shelf, and are not the words in force on the day asked"
            else:
                detail = (f"the words it read are kept: {law_text.HISTORY_DIR}/{law_text.slug(p.base)}/{kept.digest}.md"
                          if kept is not None else "")
            found.append(ProvisionStatus(p.citation, ReadingState.STALE, p.digest, text.digest, detail))
    states = {p.state for p in found}
    if ReadingState.MISSING in states:
        return ReadingStatus(reading.key, ReadingState.MISSING, tuple(found))
    if ReadingState.STALE in states:
        return ReadingStatus(reading.key, ReadingState.STALE, tuple(found))
    if reading.quote.strip() and not any(_quoted(reading.quote, words) for words in texts):
        return ReadingStatus(reading.key, ReadingState.MISQUOTED, tuple(found),
                             "the words it quotes are not in a provision it reads")
    return ReadingStatus(reading.key, ReadingState.CURRENT, tuple(found))


def readings(community: Any = None) -> tuple[LawReading, ...]:
    """The profile's readings (``Community.law_readings()``), each key once."""
    found = tuple(getattr(community, "law_readings", lambda: ())()) if community is not None else ()
    keys = [r.key for r in found]
    twice = sorted({k for k in keys if keys.count(k) > 1})
    if twice:
        raise ValueError(f"readings with the same key: {', '.join(twice)}")
    return found


_WHOSE = {Whose.BOARD: "The board", Whose.COUNSEL: "Counsel", Whose.JASON: "jason (a lead; no person has adopted it)"}


def _basis(r: LawReading) -> str:
    parts = []
    if r.canon is not None:
        parts.append(f"{r.canon.value.replace('_', ' ')} ({r.canon.citation})")
    if r.authority:
        parts.append(r.authority)
    return "; ".join(parts)


def label(r: LawReading) -> str:
    """A reading as it is shown: whose it is, its standing, its date, and then what it says. Never the words."""
    who, day = _WHOSE[r.whose], r.dated.isoformat()
    basis = _basis(r)
    if r.standing is ReadingStanding.PLAIN:
        text = f"{who} finds the words plain ({day}): they answer \"{r.question}\""
        if r.quote:
            text += f" with \"{r.quote}\""
    elif r.standing is ReadingStanding.READING:
        text = f"{who} reads this to mean ({day}; a reading, not the words): {r.reading} Question: \"{r.question}\""
    else:
        text = (f"Two readings remain ({who}, {day}); the board asks counsel. Question: \"{r.question}\" "
                f"(1) {r.alternatives[0]} (2) {r.alternatives[1]}")
    if basis:
        text += f" Rests on: {basis}."
    if r.board_item:
        text += f" Board item {r.board_item}."
    return text


@dataclass(frozen=True)
class Recited:
    reading: LawReading
    status: ReadingStatus

    def as_dict(self) -> dict[str, Any]:
        r = self.reading
        return {"key": r.key, "standing": r.standing.value, "whose": r.whose.value, "lead": r.lead,
                "dated": r.dated.isoformat(), "question": r.question, "reading": r.reading,
                "alternatives": list(r.alternatives), "quote": r.quote,
                "canon": r.canon.value if r.canon else "", "canonCitation": r.canon.citation if r.canon else "",
                "authority": r.authority, "boardItem": r.board_item, "state": self.status.state.value,
                "applies": self.status.applies, "status": self.status.line(),
                "provisions": [{"citation": p.citation, "state": p.state.value, "read": p.read, "now": p.now,
                                "detail": p.detail} for p in self.status.provisions]}


@dataclass(frozen=True)
class Recital:
    """A provision recited: its words first, then the readings of them, each labeled; the ones that no longer read
    these words apart."""

    citation: str
    found: bool
    words: str = ""
    digest: str = ""
    source: str = ""
    note: str = ""
    reason: str = ""
    caveats: tuple[str, ...] = ()
    as_of: date | None = None
    readings: tuple[Recited, ...] = ()        # current: each may be applied, as a reading
    not_applied: tuple[Recited, ...] = ()     # stale, missing, or misquoted: listed, never applied
    later: tuple[Recited, ...] = ()           # dated after ``as_of``: not a reading on that day
    others: tuple[ProvisionText, ...] = ()    # the other versions the shelf holds under the same number
    # A statute asked as of a day: "prior", "current", or "own_words" when the disk shows these were the words in
    # force that day (``basis`` says how, ``quotes`` the section's own deciding words); "not_shown" when it does not,
    # and the words recited are the words on the shelf now.
    decided: str = ""
    basis: str = ""
    quotes: tuple[str, ...] = ()

    @property
    def in_force(self) -> bool:
        """Whether the words recited are shown to be the words in force on ``as_of``."""
        return bool(self.decided) and self.decided != "not_shown"

    @property
    def stale(self) -> tuple[Recited, ...]:
        return tuple(r for r in self.not_applied if r.status.state is ReadingState.STALE)

    def _read(self, r: Recited) -> str:
        """Which words a current reading read: the digest, for each provision of this citation."""
        mine = [p for p in r.status.provisions if target_of(p.citation) == self.citation]
        return ", ".join(f"{p.citation} digest {p.now[:MIN_DIGEST]}" for p in mine)

    def about_lines(self) -> list[str]:
        """What the words are, as the recital says it above them: their source and digest, and, asked as of a day,
        whether the disk shows them in force that day and how. Nothing for a provision that was not found."""
        if not self.found:
            return []
        out = [f"Source: {self.source}" if self.source else "Source: not recorded", f"Digest of these words: {self.digest}"]
        if self.as_of is not None:
            out.append(f"As of: {self.as_of.isoformat()}")
        if self.as_of is not None and self.decided:
            day = self.as_of.isoformat()
            if self.in_force:
                out.append(f"In force on {day}: {self.basis}")
                out += [f"Own words that decide it: \"{q}\"" for q in self.quotes]
            else:
                out.append(f"Not shown to be in force on {day}: these are the words on the shelf now; {self.basis}")
        if self.note:
            out.append(f"History (jason's note, not part of the words): {self.note}")
        return out

    def lines(self, *, stale: bool = True) -> list[str]:
        """The recital as text: the words, then the readings. ``stale=False`` leaves out what is not applied."""
        if not self.found:
            out = [f"{self.citation}: {self.reason}"]
        else:
            out = [self.citation, *self.about_lines(), "", self.words, ""]
            for n, other in enumerate(self.others, start=2):
                out += [f"{self.citation}, version {n} of {len(self.others) + 1} on the shelf",
                        f"Source: {other.source}" if other.source else "Source: not recorded",
                        f"Digest of these words: {other.digest}", "", other.words, ""]
            out += [f"Caveat: {c}" for c in self.caveats]
        return out + self.reading_lines(stale=stale)

    def reading_lines(self, *, stale: bool = True) -> list[str]:
        """The readings of the words, as the recital lists them under the words: each current one labeled with whose
        it is, its standing, and its date; then, with ``stale``, those not applied and those dated after the day
        asked, each apart. Never the words."""
        out: list[str] = []
        if self.readings:
            out.append("Readings of these words (each a reading, not the words):")
            out += [f"- [{r.reading.key}] {label(r.reading)} Reads {self._read(r)}." for r in self.readings]
        elif self.found:
            out.append("No reading of these words is stored: the words stand alone.")
        if stale and self.not_applied:
            out.append("Not applied (redone or confirmed against the words on disk before any use):")
            for r in self.not_applied:
                who = _WHOSE[r.reading.whose]
                was = (f" It read: {r.reading.reading}" if r.reading.reading
                       else f" It named two readings: (1) {r.reading.alternatives[0]} (2) {r.reading.alternatives[1]}"
                       if r.reading.alternatives else "")
                out.append(f"- [{r.reading.key}] {r.status.state.value.upper()}: {who}, {r.reading.dated.isoformat()}, on "
                           f"\"{r.reading.question}\". {r.status.line()}.{was}")
        if stale and self.later:
            out.append(f"Dated after {self.as_of.isoformat() if self.as_of else 'the day asked'} (not a reading on that day):")
            out += [f"- [{r.reading.key}] {_WHOSE[r.reading.whose]}, {r.reading.dated.isoformat()}" for r in self.later]
        return out

    def as_dict(self) -> dict[str, Any]:
        return {"citation": self.citation, "found": self.found, "words": self.words, "digest": self.digest,
                "source": self.source, "note": self.note, "reason": self.reason, "caveats": list(self.caveats),
                "asOf": self.as_of.isoformat() if self.as_of else None,
                "inForce": ({"shown": self.in_force, "decided": self.decided, "basis": self.basis,
                             "quotes": list(self.quotes)} if self.decided else None),
                "otherVersions": [{"words": o.words, "digest": o.digest, "source": o.source, "note": o.note}
                                  for o in self.others],
                "readings": [r.as_dict() for r in self.readings],
                "notApplied": [r.as_dict() for r in self.not_applied],
                "later": [r.as_dict() for r in self.later]}


def recite(citation: str, data_dir: Path, readings: Iterable[LawReading] = (), as_of: date | None = None, *,
           community: Any = None) -> Recital:
    """A provision's words, verbatim from the shelf with their digest and source, and then each reading that reads
    it: the current ones labeled with whose they are, their standing, and their date; the stale ones apart, as stale.

    With ``as_of``, a reading dated later is set apart too, and a statute's words are the words in force on that day
    where the disk shows which they were (``law_text.in_force``): an earlier version from the history with the range
    it was in force and its source, the current words where a record places them in force by then, or, of two
    versions printed under one number, the one their own operative words pick, quoted. Where the disk does not show
    it, the words on the shelf now are recited and said plainly not to be shown as the words of that day
    (``Recital.in_force`` is false), with what is missing and what would bring it. Never a guess.

    This is what a review or an answer calls: the words come first, whatever is stored."""
    target = target_of(citation) or citation
    text = provision_text(citation, Path(data_dir), community=community, as_of=as_of)
    current: list[Recited] = []
    set_aside: list[Recited] = []
    later: list[Recited] = []
    for r in readings:
        if not r.reads(target):
            continue
        row = Recited(r, status(r, Path(data_dir), community=community, as_of=as_of))
        if as_of is not None and r.dated > as_of:
            later.append(row)
        elif row.status.applies:
            current.append(row)
        else:
            set_aside.append(row)
    return Recital(target, text.found, text.words, text.digest, text.source, text.note, text.reason, text.caveats, as_of,
                   tuple(current), tuple(set_aside), tuple(later), text.others, text.decided, text.basis, text.quotes)


__all__ = ["Canon", "LawReading", "Provision", "ProvisionStatus", "ProvisionText", "ReadingStanding", "ReadingState",
           "ReadingStatus", "Recital", "Recited", "Whose", "label", "provision_text", "readings", "recite", "status",
           "target_of"]
