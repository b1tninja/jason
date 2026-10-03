"""Which intake question to answer first: each question's ``Unblocks``, and one ``priority`` that sorts the queue.

A question is worth what its answer unblocks:

- **legal clocks** it affects: a schedule assignment or a notice requirement or provision that cites the section, or a
  fact that sets a clock (the fiscal year's end sets the annual reports' windows);
- **checklist items** it would move to present (``jason.community.onboarding``), missing ones above partial ones;
- **stage gates** it holds closed (an open question about which text is in force holds "establish");
- **books or Civil Code 5200 records** it fills;
- **sections** it touches, weighted by how often jason's records and the documents cite them (``citation_weight``);
- or only the **quality** of a text (an OCR reading, an orphaned note).

``priority`` turns that into one number, in tiers: a legal clock first, then a missing checklist item, then a stage
gate, then a heavily cited section, then a quality issue. The tiers are the weights below: a lower tier never adds up
to a higher one (each is capped below the next), so an OCR reading in a section nothing cites sinks to the bottom. An
OCR reading reaches the clock tier only when it could change what the section means (``reading_matters``): a
respacing ("ofthe") or a likely real word for a non-word does not. A book or record filled with no checklist item
behind it counts as ``RECORD``, the weight of fifty citations.

Pure records: the task (``jason.tasks.onboarding_session``) reads the citations and the checklist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

# --- Weights. Each tier's cap stays below the next tier's floor. -------------------------------------------------------

CLOCK = 100_000.0                # an answer that changes a legal clock (a notice, a schedule assignment, a statutory date)
MISSING_ITEM = 10_000.0          # each checklist item now missing that the answer would move to present
PARTIAL_ITEM = 5_000.0           # each checklist item now partial
ITEM_CAP = 9                     # items counted at most: 9 missing items stay below one clock
STAGE_GATE = 2_000.0             # the answer opens (or helps open) a stage gate
PER_CITATION = 10.0              # each weighted citation of a section the question touches
CITED_CAP = 1_900.0              # citations stay below a stage gate
RECORD = 500.0                   # a book or 5200 record the answer fills that no checklist item counts
QUALITY = 1.0                    # a question about a text's quality alone: the floor

# How much one citation counts, by what cites the section (``jason.community.cite.Holder`` values). Jason's own
# records that act on a section (a conflict, a notice, a duty, a schedule assignment) count more than a cross-reference.
HOLDER_WEIGHTS: dict[str, float] = {
    "conflict row": 4.0,
    "notice provision": 3.0,
    "notice requirement": 3.0,
    "document duty": 2.0,
    "schedule assignment": 2.0,
    "governing document": 1.0,
}
OTHER_HOLDER = 0.5               # a response rule, template, procedure, lesson, embedded copy, or record kind

# The holders whose citation makes a section part of a legal clock.
CLOCK_HOLDERS = frozenset({"notice provision", "notice requirement", "schedule assignment"})

ENCLOSING = 0.5                  # a citation of the section that encloses the one asked about ("4.15" for "4.15(a)")
ARTICLE = 0.2                    # a citation of the whole article ("4" for "4.15(a)")
INSIDE = 0.25                    # a citation of a part inside the section asked about ("4.15(a)" for "4.15"): the words
                                 # asked about are the section's own, usually its lead-in; never for a whole article

QUALITY_KINDS = frozenset({"ocr reading", "orphaned note", "section kind", "held source"})


@dataclass(frozen=True)
class Citing:
    """One record or document that cites a section: what holds it (a ``Holder`` value) and that record's key."""

    number: str
    holder: str
    key: str = ""


@dataclass(frozen=True)
class Unblocks:
    """What answering one question unblocks."""

    items: tuple[tuple[str, str], ...] = ()          # (checklist item key, its status now: missing or partial)
    gates: tuple[str, ...] = ()                      # stage values whose gate the question holds closed
    records: tuple[str, ...] = ()                    # books ("book arts") or 5200 records ("record check_register")
    clocks: tuple[str, ...] = ()                     # the clocks it affects ("notice:board-meeting", "assignment:x")
    sections: tuple[str, ...] = ()                   # the sections it touches ("ccrs#4.15(a)")
    weight: float = 0.0                              # the sections' weighted citations
    quality: bool = False                            # only a text's quality is at stake
    groups: tuple[str, ...] = ()                     # checklist groups the question belongs to (for filtering)

    def lines(self) -> list[str]:
        out = []
        if self.clocks:
            out.append("clocks: " + ", ".join(self.clocks[:4]) + (f" and {len(self.clocks) - 4} more" if len(self.clocks) > 4 else ""))
        if self.items:
            out.append("checklist: " + ", ".join(f"{k} ({s})" for k, s in self.items))
        if self.gates:
            out.append("stage: " + ", ".join(self.gates))
        if self.records:
            out.append("fills: " + ", ".join(self.records))
        if self.sections:
            out.append(f"sections: {', '.join(self.sections)} (cited weight {self.weight:g})")
        if self.quality and not out:
            out.append("quality only: no clock, item, or citation depends on it")
        return out

    def as_dict(self) -> dict[str, Any]:
        return {"items": [{"key": k, "status": s} for k, s in self.items], "gates": list(self.gates),
                "records": list(self.records), "clocks": list(self.clocks), "sections": list(self.sections),
                "citedWeight": self.weight, "qualityOnly": self.quality and not (self.clocks or self.items or self.gates
                                                                                  or self.records or self.weight)}


def priority(u: Unblocks) -> float:
    """One number that sorts the queue, highest first.

    - ``CLOCK`` when the answer affects a legal clock;
    - plus ``MISSING_ITEM`` for each missing checklist item and ``PARTIAL_ITEM`` for each partial one (``ITEM_CAP`` at
      most);
    - plus ``STAGE_GATE`` when it holds a stage gate closed;
    - plus ``PER_CITATION`` for each weighted citation of its sections, up to ``CITED_CAP``;
    - plus ``RECORD`` when it fills a book or record no item counts;
    - and ``QUALITY`` as the floor every question has.

    Each tier's cap stays below the next tier's single step, so the order is: a legal clock, a missing item, a partial
    item, a stage gate, a cited section, a record, then quality alone."""
    score = QUALITY
    if u.clocks:
        score += CLOCK
    missing = sum(1 for _, s in u.items if s == "missing")
    partial = sum(1 for _, s in u.items if s != "missing")
    counted = min(missing, ITEM_CAP)
    score += counted * MISSING_ITEM + min(partial, ITEM_CAP - counted) * PARTIAL_ITEM
    if u.gates:
        score += STAGE_GATE
    score += min(u.weight * PER_CITATION, CITED_CAP)
    if u.records and not u.items:
        score += RECORD
    return score


def relation(asked: str, cited: str) -> float:
    """How much a citation of section ``cited`` bears on section ``asked`` of the same document: 1 for the same section,
    ``ENCLOSING`` for a section that encloses it, ``ARTICLE`` for its whole article, ``INSIDE`` for a part inside it
    (0 when ``asked`` is a whole article: its own words are a heading or a lead-in), 0 otherwise."""
    if not asked or not cited:
        return 0.0
    if asked == cited:
        return 1.0
    if _inside(cited, asked):
        return 0.0 if _article(asked) else INSIDE
    if _inside(asked, cited):
        return ARTICLE if _article(cited) else ENCLOSING
    return 0.0


def _article(number: str) -> bool:
    return not any(c in number for c in ".(")


def _inside(inner: str, outer: str) -> bool:
    return inner.startswith(outer) and len(inner) > len(outer) and inner[len(outer)] in ".("


def section_weight(number: str, citing: Iterable[Citing]) -> tuple[float, tuple[str, ...]]:
    """The weighted citations of a section, and the clocks among them: a record that cites the section itself or a
    section enclosing it (never only its article, nor only a part inside it)."""
    weight = 0.0
    clocks: list[str] = []
    for c in citing:
        r = relation(number, c.number)
        if not r:
            continue
        weight += r * HOLDER_WEIGHTS.get(c.holder, OTHER_HOLDER)
        if c.holder in CLOCK_HOLDERS and r >= ENCLOSING and c.key and c.key not in clocks:
            clocks.append(c.key)
    return round(weight, 2), tuple(clocks)


def reading_matters(detail: dict[str, Any], likely: bool) -> bool:
    """Whether an OCR reading could change what a section means, so a clock that cites the section waits on it: not
    when the two readings differ only in spacing, case, or punctuation ("ofthe", "of the"; "or", "OR"), nor when a
    likely reading puts real words for non-words with no digit at stake; yes when a digit differs, or the readings are
    words a person must choose between. (A guard the text rules set, a number or operative word, always matters.)"""
    if detail.get("guard"):
        return True
    wrong, right = str(detail.get("wrong") or ""), str(detail.get("right") or "")
    if re.sub(r"[^a-z0-9]", "", wrong.casefold()) == re.sub(r"[^a-z0-9]", "", right.casefold()):
        return False
    if re.findall(r"\d+", wrong) != re.findall(r"\d+", right):
        return True
    return not likely


def subject_section(subject: str) -> tuple[str, str]:
    """``("ccrs", "4.15(a)")`` from ``ccrs#4.15(a)``; a subject with no section gives an empty number."""
    if "#" not in subject or subject.startswith(("library:", "fact:", "book:", "record:", "map:")):
        return "", ""
    document, _, number = subject.partition("#")
    return document, number


@dataclass
class Ranked:
    ask: Any
    unblocks: Unblocks
    score: float = field(default=0.0)


def rank(asks: Iterable[Any], unblocks: dict[str, Unblocks]) -> list[Ranked]:
    """The open questions, highest priority first; ties keep a stable order by kind and subject."""
    out = [Ranked(a, unblocks.get(a.id, Unblocks()), 0.0) for a in asks]
    for r in out:
        r.score = priority(r.unblocks)
    out.sort(key=lambda r: (-r.score, getattr(r.ask.kind, "value", ""), r.ask.subject, r.ask.id))
    return out


__all__ = ["ARTICLE", "CITED_CAP", "CLOCK", "CLOCK_HOLDERS", "Citing", "ENCLOSING", "HOLDER_WEIGHTS", "INSIDE",
           "ITEM_CAP", "MISSING_ITEM", "OTHER_HOLDER", "PARTIAL_ITEM", "PER_CITATION", "QUALITY", "QUALITY_KINDS",
           "RECORD", "Ranked", "STAGE_GATE", "Unblocks", "priority", "rank", "reading_matters", "relation",
           "section_weight", "subject_section"]
