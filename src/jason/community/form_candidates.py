"""The records of the form-discovery pass (docs/standard-forms.md, "How to find them").

A **candidate** is a span of words in a statute or a governing document that may create a request a member makes of the
association, one a standard form could take. The discovery pass (``jason.tasks.form_discovery``) seeds candidates with
general phrase patterns, may read each with the local model, joins a statute with the document sections that carry it
out, and a person confirms, holds, or drops each. A candidate is a lead: confirming one writes only its status. It makes
no form, no procedure, and no known-form row; that is a person's next step.

Everything here is a typed record. JSON stores the words (``"statute"``, ``"new"``); the loaders turn them into symbols
before a task sees them. Nothing here names an association: the spans come from the law on the shelf and from the
documents the profile keeps.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from jason.community.responses import ClockSource


class CandidateSource(Enum):
    STATUTE = "statute"
    DOCUMENT = "document"


class CandidateStatus(Enum):
    NEW = "new"                    # seeded; nobody has looked
    CONFIRMED = "confirmed"        # a person says it is a request a form could take (nothing is made by saying so)
    HELD = "held"                  # kept for the board: the law is silent on a clock the form needs, or the reading is open
    DROPPED = "dropped"            # not a request, or the words are gone (a person's act, or a reading whose quote was not found)


class JoinBasis(Enum):
    CITATION = "citation"          # the document span cites the statute's section
    KIND = "kind"                  # both read as the same kind of request (``ResponseKind``)
    TERMS = "terms"                # the spans share the words that carry their subject


@dataclass(frozen=True)
class Clock:
    """One deadline a span states: for whom, how long, and what happens if it passes ("deemed approved")."""

    for_whom: str
    how_long: str
    if_passes: str = ""
    source: ClockSource = ClockSource.NONE        # where the clock comes from: the statute or the documents

    def to_dict(self) -> dict[str, Any]:
        return {"forWhom": self.for_whom, "howLong": self.how_long, "ifPasses": self.if_passes, "source": self.source.value}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Clock:
        return cls(str(raw.get("forWhom") or ""), str(raw.get("howLong") or ""), str(raw.get("ifPasses") or ""),
                   ClockSource(raw.get("source") or ClockSource.NONE.value))


@dataclass(frozen=True)
class Decision:
    """How the request is decided: by whom, and whether the span asks for it in writing, with reasons, and for
    reconsideration (``reconsideration`` is the span's words for it, or "")."""

    who: str = ""
    in_writing: bool = False
    reasons: bool = False
    reconsideration: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"who": self.who, "inWriting": self.in_writing, "reasons": self.reasons,
                "reconsideration": self.reconsideration}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Decision:
        return cls(str(raw.get("who") or ""), bool(raw.get("inWriting")), bool(raw.get("reasons")),
                   str(raw.get("reconsideration") or ""))


@dataclass(frozen=True)
class CandidateReading:
    """What the local model read in one span. A reading for a person to check: never the rule, and about one in five
    readings of a norm is the wrong kind. ``quote`` is the operative words, and it is kept only when it is found in the
    span word for word."""

    is_request: bool
    who_submits: str = ""
    to_whom: str = ""
    what: str = ""
    required_content: tuple[str, ...] = ()
    clocks: tuple[Clock, ...] = ()
    decision: Decision | None = None
    authority: str = ""
    quote: str = ""
    model: str = ""
    read_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"isRequest": self.is_request, "whoSubmits": self.who_submits, "toWhom": self.to_whom, "what": self.what,
                "requiredContent": list(self.required_content), "clocks": [c.to_dict() for c in self.clocks],
                "decision": self.decision.to_dict() if self.decision else None, "authority": self.authority,
                "quote": self.quote, "model": self.model, "readAt": self.read_at}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CandidateReading:
        decision = raw.get("decision")
        return cls(bool(raw.get("isRequest", True)), str(raw.get("whoSubmits") or ""), str(raw.get("toWhom") or ""),
                   str(raw.get("what") or ""), tuple(str(x) for x in raw.get("requiredContent") or ()),
                   tuple(Clock.from_dict(c) for c in raw.get("clocks") or ()),
                   Decision.from_dict(decision) if isinstance(decision, dict) else None, str(raw.get("authority") or ""),
                   str(raw.get("quote") or ""), str(raw.get("model") or ""), str(raw.get("readAt") or ""))


@dataclass(frozen=True)
class FormCandidate:
    """A span that may create a request a form could take.

    ``citation`` is the canonical citation of a statute section ("CIV 5210") or a document's key and section
    ("rules 4.2"). ``quote`` is the span's own words, copied from the source (paragraphs joined by a line break), so a
    reader and a person see what the seed saw. ``seeds`` names the patterns that took it. ``known_as`` is a
    ``ResponseKind`` value or a notice-catalog key the span matches, or "" (``note`` says why). ``group`` joins a statute
    and the document sections that carry it out."""

    id: str
    source: CandidateSource
    citation: str
    quote: str
    seeds: tuple[str, ...] = ()
    reading: CandidateReading | None = None
    known_as: str = ""
    group: str = ""
    status: CandidateStatus = CandidateStatus.NEW
    note: str = ""
    known_why: str = ""            # why ``known_as`` says what it says (derived; ``note`` is a person's or the reader's)

    def with_(self, **changes: Any) -> FormCandidate:
        return replace(self, **changes)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "source": self.source.value, "citation": self.citation, "quote": self.quote,
                "seeds": list(self.seeds), "reading": self.reading.to_dict() if self.reading else None,
                "knownAs": self.known_as, "knownWhy": self.known_why, "group": self.group, "status": self.status.value,
                "note": self.note}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> FormCandidate:
        reading = raw.get("reading")
        return cls(str(raw["id"]), CandidateSource(raw["source"]), str(raw["citation"]), str(raw.get("quote") or ""),
                   tuple(str(s) for s in raw.get("seeds") or ()),
                   CandidateReading.from_dict(reading) if isinstance(reading, dict) else None,
                   str(raw.get("knownAs") or ""), str(raw.get("group") or ""),
                   CandidateStatus(raw.get("status") or CandidateStatus.NEW.value), str(raw.get("note") or ""),
                   str(raw.get("knownWhy") or ""))


@dataclass(frozen=True)
class Join:
    """Why a document span was put in a statute's group: the basis and the words of the reason."""

    statute: str                   # a candidate id
    document: str                  # a candidate id
    basis: JoinBasis
    reason: str
    strength: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"statute": self.statute, "document": self.document, "basis": self.basis.value, "reason": self.reason,
                "strength": self.strength}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Join:
        return cls(str(raw["statute"]), str(raw["document"]), JoinBasis(raw["basis"]), str(raw.get("reason") or ""),
                   float(raw.get("strength") or 0))


@dataclass
class CandidateStore:
    """What ``data/forms/candidates.json`` holds."""

    candidates: list[FormCandidate] = field(default_factory=list)
    joins: list[Join] = field(default_factory=list)
    seeded_at: str = ""

    def get(self, candidate_id: str) -> FormCandidate | None:
        return next((c for c in self.candidates if c.id == candidate_id), None)

    def to_dict(self) -> dict[str, Any]:
        return {"version": 1, "seededAt": self.seeded_at, "candidates": [c.to_dict() for c in self.candidates],
                "joins": [j.to_dict() for j in self.joins]}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CandidateStore:
        return cls([FormCandidate.from_dict(c) for c in raw.get("candidates") or ()],
                   [Join.from_dict(j) for j in raw.get("joins") or ()], str(raw.get("seededAt") or ""))


__all__ = ["CandidateReading", "CandidateSource", "CandidateStatus", "CandidateStore", "Clock", "Decision", "FormCandidate",
           "Join", "JoinBasis"]
