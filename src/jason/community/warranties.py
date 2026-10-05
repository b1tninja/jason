"""Sentences that give a warranty, and what each one promises.

A contract's warranty is a duty that outlives the work: the contractor stands behind its workmanship, its materials,
or the thing it installed for a stated time. The board needs each one on a list of its own, with how long it runs and
from when, because the warranty is what it calls on when a repair fails, and its end is a date to diary. A warranty
the vendor must hand over in writing ("will provide a written warranty of five (5) years") is also a deliverable: the
board should have the paper in its files.

``warranty_of(sentence)`` reads one sentence. It tries the ``WARRANTY_RULES`` rows in order, clause by clause; the
first row that matches a clause wins. Each row names the form the warranty is written in: a verb ("warrants its
workmanship"), a promise to provide one ("will provide a written warranty"), the passive ("All work is guaranteed"),
or the bare noun with a period ("Warranty: two (2) years on labor"). It returns:

- the holder words, the subject written before the cue ("Example Roofing, Inc.", "We", "EHS"), as written. jason does
  not decide here whose they are; the contract reader maps them to a party.
- what is covered, as written ("its workmanship", "the roof"), and the kinds of cover it names (``Cover``).
- the period (``Period``: its count and unit, as printed, with ``months``), when one is stated.
- what the period runs from (``Start``), when stated.
- whether it is written, and whether it is a deliverable (a promise to provide, issue, or deliver it).

A disclaimer is not a warranty. "makes no warranties", "does not warrant", "without warranty", and "voids the
warranty" give none; ``exemptions.exemption_of`` reads those, and ``warranty_of`` returns None for them. A clause that
only uses the word gives none either: "represents and warrants that it is licensed" is a representation, "warranty
claims must be made within thirty (30) days" is a deadline for a claim, and "Payment is guaranteed" covers no work.
A miss stays a miss.

``warranties_of(sentence)`` gives every clause's warranty ("Manufacturer's warranty on materials is 25 years;
Contractor's labor warranty is 2 years" gives two); ``warranty_of`` gives the first. A noun warranty's holder is the
possessive before it ("Manufacturer's", "Our"), and what it covers is its object ("materials") or the words between the
possessive and the noun ("labor"); an exclusion after it ("does not cover damage ...") is not what it covers.

``find_warranties(text)`` reads a whole contract, one sentence at a time, and gives each warranty once. A line wrapped
mid-sentence is joined to the next before the text is split.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from jason.community.exemptions import ExemptionKind, clauses, exemption_of


class WarrantyForm(Enum):
    PROVIDES = "provides a warranty"  # "will provide a written warranty of five (5) years": a deliverable
    OFFERS = "offers a warranty"  # "offers a two (2) year warranty": a warranty, not a paper to hand over
    WARRANTS = "warrants"  # "warrants its workmanship for one (1) year"
    PASSIVE = "is warranted"  # "All work is guaranteed for one (1) year"
    NOUN = "warranty with a period"  # "Warranty: two (2) years on labor"


class Cover(Enum):
    WORKMANSHIP = "workmanship"
    LABOR = "labor"
    MATERIALS = "materials"
    EQUIPMENT = "equipment or parts"
    INSTALLATION = "installation"
    WORK = "the work"


class Unit(Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class Start(Enum):
    SUBSTANTIAL_COMPLETION = "substantial completion"
    COMPLETION = "completion"
    INSTALLATION = "installation"
    ACCEPTANCE = "acceptance"
    FINAL_PAYMENT = "final payment"
    INVOICE = "the invoice"
    SIGNING = "the contract's date"


@dataclass(frozen=True)
class Period:
    count: int
    unit: Unit
    printed: str

    @property
    def months(self) -> int | None:
        """The period in whole months: a year is 12, a day period only when it is a whole number of 30-day months
        (90 days is 3). A week period, or days that are not whole months, have none: read ``days``."""
        if self.unit is Unit.YEAR:
            return self.count * 12
        if self.unit is Unit.MONTH:
            return self.count
        if self.unit is Unit.DAY and self.count % 30 == 0:
            return self.count // 30
        return None

    @property
    def days(self) -> int | None:
        """The period in days when it is written in days or weeks; a month or a year is not a fixed number of days."""
        if self.unit is Unit.DAY:
            return self.count
        if self.unit is Unit.WEEK:
            return self.count * 7
        return None


@dataclass(frozen=True)
class Warranty:
    form: WarrantyForm
    cue: str
    holder_words: str
    covered_words: str
    covers: tuple[Cover, ...]
    period: Period | None
    start: Start | None
    written: bool
    deliverable: bool
    sentence: str

    @property
    def period_months(self) -> int | None:
        return self.period.months if self.period else None

    @property
    def deliverable_words(self) -> str:
        """The deliverable as written, from the warranty's noun through its period ("written warranty of five (5)
        years"), or "" when it is not a deliverable."""
        if not self.deliverable:
            return ""
        noun = _DELIVERABLE_NOUN.search(self.sentence)
        if not noun:
            return ""
        end = noun.end()
        if self.period:
            at = self.sentence.find(self.period.printed, noun.start())
            if at >= 0:
                end = max(end, at + len(self.period.printed))
        return " ".join(self.sentence[noun.start():end].split())


@dataclass(frozen=True)
class WarrantyRule:
    """One way a warranty is written: its form, the pattern of its cue, and what the row is for."""

    form: WarrantyForm
    pattern: re.Pattern[str]
    note: str


def _rule(form: WarrantyForm, pattern: str, note: str) -> WarrantyRule:
    return WarrantyRule(form, re.compile(pattern, re.IGNORECASE), note)


_NOUN = r"(?:warrant(?:y|ies)|guarantee)"
_SPAN = r"(?:(?!\b(?:and|but|or)\b)[^.;:]){0,60}?"

WARRANTY_RULES: tuple[WarrantyRule, ...] = (
    _rule(WarrantyForm.PROVIDES,
          rf"\b(?:provide|issue|deliver|furnish|give|supply)(?:s|d)?\b{_SPAN}\b{_NOUN}\b",
          "provide/issue/deliver/furnish ... warranty"),
    _rule(WarrantyForm.OFFERS,
          rf"\b(?:offer|extend|include)(?:s|ed)?\b{_SPAN}\b{_NOUN}\b",
          "offers/extends/includes ... warranty"),
    # "guarantees to complete" is not a warranty of work.
    _rule(WarrantyForm.WARRANTS,
          r"(?:\b(?:warrants|guarantees)|\b(?:shall|will|must|hereby|also|further|does|do)\s+(?:\w+ly\s+)?"
          r"(?:warrant|guarantee))\b"
          r"(?!\s+(?:that|to|of|for|period|claims?|is|are|shall|will|on|covering)\b)",
          "warrants/guarantees (a verb, not 'that')"),
    # "warrants that all work will be free of defects for one year" is a warranty; "represents and warrants that it
    # holds all licenses" is a representation. The clause's period or cover tells them apart (see ``_read_clause``).
    _rule(WarrantyForm.WARRANTS,
          r"(?:\b(?:warrants|guarantees)|\b(?:shall|will|must|hereby|also|further|does|do)\s+(?:\w+ly\s+)?"
          r"(?:warrant|guarantee))\s+that\b",
          "warrants/guarantees that ..., with a period or a cover"),
    # A vendor's own form often writes the noun as the verb: "Example Co. warranties all work for one year".
    _rule(WarrantyForm.WARRANTS,
          r"(?<=\w)\s+warranties\s+(?=(?:all|the|its|our|their|this|each|any)\s+\w)",
          "warranties (the noun used as the verb) all work ..."),
    _rule(WarrantyForm.PASSIVE,
          r"\b(?:is|are|shall\s+be|will\s+be)\s+(?:\w+ly\s+)?(?:warranted|guaranteed)\b",
          "is/are warranted or guaranteed"),
    _rule(WarrantyForm.NOUN, rf"\b{_NOUN}\b", "warranty, with a period in the clause"),
)

_DELIVERABLE_NOUN = re.compile(rf"\b(?:written\s+)?{_NOUN}(?:\s+(?:certificate|letter|document))?\b", re.IGNORECASE)
_WRITTEN = re.compile(rf"\bwritten\s+(?:\w+\s+){{0,3}}?{_NOUN}|\b{_NOUN}\s+(?:certificate|letter|document)\b|"
                      rf"\b{_NOUN}\b[^.;]*\bin\s+writing\b", re.IGNORECASE)

# Disclaimers the exemption rows do not read: a negated verb, "without", "no guarantee", "void".
_NEGATION = re.compile(
    rf"\b(?:does|do|did|will|shall|can|cannot|could)\s*n[o']t\s+(?:\w+ly\s+)?(?:warrant|guarantee)|"
    rf"\bcannot\s+(?:warrant|guarantee)|\bnot\s+(?:be\s+)?(?:warranted|guaranteed)\b|"
    rf"\bwithout\s+(?:any\s+)?(?:\w+\s+)?{_NOUN}|\bno\s+(?:\w+\s+)?guarantees?\b|"
    rf"\bvoids?\b[^.;]*\b{_NOUN}|\b{_NOUN}\b[^.;]*\b(?:void|null|voided)\b",
    re.IGNORECASE)

_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "eighteen": 18, "twenty": 20,
    "twenty-four": 24, "thirty": 30, "thirty-six": 36, "forty-five": 45, "sixty": 60, "ninety": 90,
}
_COUNT = (r"(?:(?P<word>[a-z]+(?:-[a-z]+)?)\s*\((?P<paren>\d+)\)|(?P<digits>\d+)|(?P<bare>"
          + "|".join(sorted((re.escape(w) for w in _NUMBERS), key=len, reverse=True)) + r"))")
_PERIOD = re.compile(rf"\b{_COUNT}[\s-]*(?P<unit>years?|months?|weeks?|days?)\b", re.IGNORECASE)
_UNITS = {"year": Unit.YEAR, "month": Unit.MONTH, "week": Unit.WEEK, "day": Unit.DAY}
# A period after these words is a deadline ("claims within thirty (30) days"), not the warranty's length.
_NOT_LENGTH = re.compile(r"\b(?:within|after|before|prior\s+to|no\s+later\s+than|at\s+least|every|each)\s*$",
                         re.IGNORECASE)
# The words that join a period to the clause, removed with it when the covered words are read.
_PERIOD_LEAD = re.compile(r"(?:\b(?:for|of)\s+(?:a\s+(?:period|term)\s+of\s+)?|\b(?:a|an)\s+)$", re.IGNORECASE)


def _period(clause: str) -> tuple[Period, int, int] | None:
    for found in _PERIOD.finditer(clause):
        if _NOT_LENGTH.search(clause[:found.start()]):
            continue
        if found.group("paren"):
            count = int(found.group("paren"))
        elif found.group("digits"):
            count = int(found.group("digits"))
        else:
            count = _NUMBERS[found.group("bare").lower()]
        if count <= 0:
            continue
        unit = _UNITS[found.group("unit").lower().rstrip("s")]
        lead = _PERIOD_LEAD.search(clause[:found.start()])
        start = lead.start() if lead else found.start()
        return Period(count, unit, " ".join(found.group(0).split())), start, found.end()
    return None


@dataclass(frozen=True)
class StartRule:
    start: Start
    pattern: re.Pattern[str]


_FROM = r"\b(?:from|upon|after|following|beginning(?:\s+on)?|commencing(?:\s+on)?|starting(?:\s+on)?)\s+(?:the\s+)?(?:date\s+of\s+(?:the\s+)?)?"

START_RULES: tuple[StartRule, ...] = (
    StartRule(Start.SUBSTANTIAL_COMPLETION, re.compile(rf"{_FROM}substantial\s+completion\b", re.IGNORECASE)),
    StartRule(Start.COMPLETION, re.compile(rf"{_FROM}(?:final\s+)?completion\b|{_FROM}(?:the\s+)?work\s+is\s+"
                                           r"(?:complete|completed|finished)\b", re.IGNORECASE)),
    StartRule(Start.INSTALLATION, re.compile(rf"{_FROM}install(?:ation)?\b", re.IGNORECASE)),
    StartRule(Start.ACCEPTANCE, re.compile(rf"{_FROM}(?:final\s+)?acceptance\b", re.IGNORECASE)),
    StartRule(Start.FINAL_PAYMENT, re.compile(rf"{_FROM}(?:final|full)\s+payment\b", re.IGNORECASE)),
    StartRule(Start.INVOICE, re.compile(rf"{_FROM}(?:the\s+)?invoice\b", re.IGNORECASE)),
    StartRule(Start.SIGNING, re.compile(rf"{_FROM}(?:this|the)\s+(?:agreement|contract|proposal)\b|"
                                        rf"{_FROM}signing\b", re.IGNORECASE)),
)


def _start(clause: str) -> tuple[Start, int, int] | None:
    for rule in START_RULES:
        found = rule.pattern.search(clause)
        if found:
            return rule.start, found.start(), found.end()
    return None


@dataclass(frozen=True)
class CoverRule:
    cover: Cover
    pattern: re.Pattern[str]


COVER_RULES: tuple[CoverRule, ...] = (
    CoverRule(Cover.WORKMANSHIP, re.compile(r"\bworkmanship\b|\bworkmanlike\b", re.IGNORECASE)),
    CoverRule(Cover.LABOR, re.compile(r"\blabou?r\b", re.IGNORECASE)),
    CoverRule(Cover.MATERIALS, re.compile(r"\bmaterials?\b", re.IGNORECASE)),
    CoverRule(Cover.EQUIPMENT, re.compile(r"\bequipment\b|\bparts\b", re.IGNORECASE)),
    CoverRule(Cover.INSTALLATION, re.compile(r"\binstallation\b|\binstalled\b", re.IGNORECASE)),
    CoverRule(Cover.WORK, re.compile(r"\b(?:the|its|our|all|such)\s+work\b|\bwork\s+performed\b", re.IGNORECASE)),
)


def _covers(words: str) -> tuple[Cover, ...]:
    return tuple(rule.cover for rule in COVER_RULES if rule.pattern.search(words))


# The subject is the words after the last clause break before the cue, as in ``exemptions``.
_CLAUSE_BREAK = re.compile(
    r"(?:(?<!\bInc)(?<!\bCo)(?<!\bCorp)(?<!\bLtd)(?<!\bLLC)\.\s+|[;:]\s+|,\s+(?:and|but|or)\s+|\bthat\s+)",
    re.IGNORECASE)
_LEADING_NUMBER = re.compile(r"^\s*(?:\(?[0-9]+(?:\.[0-9]+)*[.)]?|\(?[a-z][.)])\s+", re.IGNORECASE)
_TRAILING_AUX = re.compile(r"(?:\s+(?:shall|will|must|hereby|also|further|agrees?\s+to|does|is|are|"
                           r"\w+ly))+\s*$", re.IGNORECASE)


def _holder_words(before: str) -> str:
    parts = _CLAUSE_BREAK.split(before)
    words = _LEADING_NUMBER.sub("", parts[-1] if parts else "")
    words = _TRAILING_AUX.sub("", " " + words)
    return " ".join(words.split())


_COVER_LEAD = re.compile(r"^(?:(?:on|for|covering|against\s+defects\s+in|of|in|a|an|the\s+warranty)\s+)+",
                         re.IGNORECASE)


# The passive's holder: "is warranted by Example Gates LLC", up to the next joining word.
_BY = re.compile(r"\bby\s+((?:(?!\b(?:for|from|against|upon|on|as|in|until|through)\b)[^;])+)", re.IGNORECASE)


def _clean(words: str) -> str:
    words = " ".join(words.replace(",", " ").split()).strip(" .;:-")
    return _COVER_LEAD.sub("", words).strip(" .;:-")


def _rest(clause: str, start: int, spans: list[tuple[int, int]]) -> str:
    """The clause after ``start`` with the period and start phrases taken out."""
    chars = list(clause)
    for a, b in spans:
        for i in range(max(a, start), b):
            chars[i] = " "
    return "".join(chars[start:])


# The noun's holder is a possessive before it, as written: "Manufacturer's warranty", "Our 5-year warranty". A
# lowercase noun's possessive ("the roof's warranty") names a thing, not a party, and gives none.
_POSSESSIVE = re.compile(
    r"(?P<who>(?:\b[A-Z][\w&.-]*,?\s+){0,4}\b[A-Z][\w&.-]*['’]s|\b(?i:our|your|their)\b)"
    r"\s*(?P<mid>(?:[\w-]+\s*){0,3})$")
_MID_WORD = re.compile(r"^(?:[\w-]+\s*){0,3}$")
# What follows the noun up to its verb is what it covers ("warranty on materials is 25 years"); an exclusion that
# follows ("does not cover damage") is not, and is no cover.
_EXCLUSION = re.compile(r"\b(?:does|do|shall|will|is|are)\s+not\s+(?:\w+\s+)?(?:cover|include|apply|extend)\w*\b|"
                        r"\bexclud(?:es?|ing)\b|\bexcept\b", re.IGNORECASE)
_NOUN_VERB = re.compile(r"\b(?:is|are|was|shall|will|runs?|lasts?|extends?|applies|covers|includes|does|do|"
                        r"begins?|commences?)\b", re.IGNORECASE)


def _noun_holder(before: str) -> tuple[str, str]:
    """The possessive before the noun as the holder, and the words between it and the noun ("labor")."""
    words = " ".join(_holder_words(before).split())
    found = _POSSESSIVE.search(words)
    if found and _MID_WORD.match(found.group("mid")):
        return " ".join(found.group("who").split()), " ".join(found.group("mid").split())
    return "", ""


def _noun_object(rest: str) -> str:
    """The noun's object: the words after it, up to its verb or an exclusion."""
    cut = _EXCLUSION.search(rest)
    if cut:
        rest = rest[:cut.start()]
    verb = _NOUN_VERB.search(rest)
    if verb:
        rest = rest[:verb.start()]
    return _clean(rest)


def _is_disclaimer(clause: str) -> bool:
    exemption = exemption_of(clause)
    if exemption is not None and exemption.kind is ExemptionKind.NO_WARRANTY:
        return True
    return bool(_NEGATION.search(clause))


def _read_clause(clause: str, sentence: str) -> Warranty | None:
    if _is_disclaimer(clause):
        return None
    for rule in WARRANTY_RULES:
        found = rule.pattern.search(clause)
        if not found:
            continue
        period = _period(clause)
        start = _start(clause)
        spans = [(p[1], p[2]) for p in (period,) if p] + [(s[1], s[2]) for s in (start,) if s]
        before = clause[:found.start()]
        if rule.form is WarrantyForm.PASSIVE:
            covered = _clean(_holder_words(before))
            by = _BY.search(_rest(clause, found.end(), spans))
            holder = " ".join(by.group(1).split()).strip(" .") if by else ""
        elif rule.form is WarrantyForm.NOUN:
            holder, mid = _noun_holder(_rest(clause, 0, spans)[:found.start()])
            covered = _noun_object(_rest(clause, found.end(), spans)) or _clean(mid)
        else:
            holder = _holder_words(before)
            covered = _clean(_rest(clause, found.end(), spans))
        after = _rest(clause, found.end(), spans)
        exclusion = _EXCLUSION.search(after)
        covers = _covers(covered) or _covers(after[:exclusion.start()] if exclusion else after)
        # A verb or a passive with neither a period nor a cover is a representation or a payment guarantee.
        if rule.form in (WarrantyForm.WARRANTS, WarrantyForm.PASSIVE) and not period and not covers:
            continue
        # The noun alone is a warranty only with a length.
        if rule.form is WarrantyForm.NOUN and not period:
            continue
        return Warranty(
            form=rule.form,
            cue=found.group(0),
            holder_words=holder,
            covered_words=covered,
            covers=covers,
            period=period[0] if period else None,
            start=start[0] if start else None,
            written=bool(_WRITTEN.search(clause)),
            deliverable=rule.form is WarrantyForm.PROVIDES,
            sentence=sentence,
        )
    return None


# "guarantees the pricing in this agreement for one year" holds a price, not the work: a price lock, not a warranty.
_PRICE_LOCK = re.compile(r"\b(?:guarantee[sd]?|warrant(?:s|ed)?|lock(?:s|ed)?)\s+(?:in\s+)?(?:the\s+|its\s+|our\s+|this\s+|"
                         r"these\s+)?(?:pric(?:e|es|ing)|rates?|fees?|quote|charges?)\b|"
                         r"\b(?:pric(?:e|es|ing)|rates?|fees?)\s+(?:is|are)\s+guaranteed\b", re.IGNORECASE)


def warranties_of(sentence: str) -> tuple[Warranty, ...]:
    """Every warranty the sentence gives, one per clause, in order; () when it gives none.

    The sentence is read clause by clause, so "warrants its workmanship for one (1) year, but makes no warranty as to
    materials" gives the workmanship warranty and drops the disclaimer, and "Manufacturer's warranty on materials is
    25 years; Contractor's labor warranty is 2 years" gives both.
    """
    sentence = " ".join(sentence.split())
    found: list[Warranty] = []
    for clause in clauses(sentence) or [sentence]:
        if _PRICE_LOCK.search(clause):
            continue
        warranty = _read_clause(clause, sentence)
        if warranty is not None:
            found.append(warranty)
    return tuple(found)


def warranty_of(sentence: str) -> Warranty | None:
    """The sentence's first warranty, or None when it gives none (a disclaimer, a representation, a deadline)."""
    found = warranties_of(sentence)
    return found[0] if found else None


_SENTENCE_END = re.compile(r"(?<!\bInc)(?<!\bCo)(?<!\bCorp)(?<!\bLtd)(?<!\bNo)(?<!\bLic)(?<=[.!?])\s+(?=[A-Z0-9\"(])")
# A line that ends a sentence or a heading, and a line that opens a list item, are never joined.
_LINE_CLOSED = re.compile(r"[.!?:;][\"')\]”’]*$")
_LIST_START = re.compile(r"^(?:[-*•]|o\s|\(?[0-9]+[.)]\s|\(?[a-z][.)]\s)", re.IGNORECASE)
# A line ending in a comma or a joining word runs on to the next ("for a period of" / "two (2) years").
_RUNS_ON = re.compile(r"(?:,|\b(?:and|or|of|the|a|an|to|for|from|with|by|in|on|at|as|that|which|its|their))$",
                      re.IGNORECASE)


def _continues(line: str, following: str) -> bool:
    """Whether ``following`` is the same sentence wrapped onto the next line."""
    if _LINE_CLOSED.search(line) or _LIST_START.match(following):
        return False
    return following[0].islower() or bool(_RUNS_ON.search(line)) or bool(re.match(r"\(\d", following))


def sentences(text: str) -> list[str]:
    """The text's sentences: a blank line or a line of its own ends one, and so does a period before a capital.
    A line wrapped mid-sentence (no closing punctuation, and the next line goes on in lowercase or after a joining
    word) is joined to the next with a space."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            lines.append("")
        elif lines and lines[-1] and _continues(lines[-1], line):
            lines[-1] = f"{lines[-1]} {line}"
        else:
            lines.append(line)
    out: list[str] = []
    for line in lines:
        if line:
            out.extend(part.strip() for part in _SENTENCE_END.split(line) if part.strip())
    return out


def find_warranties(text: str) -> tuple[Warranty, ...]:
    """Every warranty in the text, in order, each sentence once (a contract printed twice gives each once)."""
    seen: set[str] = set()
    found: list[Warranty] = []
    for sentence in sentences(text):
        key = " ".join(sentence.lower().split())
        if key in seen:
            continue
        seen.add(key)
        found.extend(warranties_of(sentence))
    return tuple(found)


__all__ = ["WarrantyForm", "Cover", "Unit", "Start", "Period", "Warranty", "WarrantyRule", "WARRANTY_RULES",
           "StartRule", "START_RULES", "CoverRule", "COVER_RULES", "warranty_of", "warranties_of", "find_warranties",
           "sentences"]
