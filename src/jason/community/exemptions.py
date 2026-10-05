"""Sentences that say where a party's duty ends.

A contract says what a party must do (a duty), what it must not do (a prohibition), and, often in a section headed
"Limits" or "Exclusions", what it does not have to do at all. That third kind is an exemption: "We are not responsible
for any loss", "Contractor shall not be obligated to", "Exclusions: permits", "sold as is", "makes no warranty". It is
neither a duty nor a prohibition, and reading it as either is wrong both ways: "shall not be obligated to attend" does
not forbid attending, and "is not responsible for" puts nothing on the party's list of things to do. The board needs
these sentences on their own list, because they mark the gaps it must cover itself or with another vendor.

``exemption_of(sentence)`` tries the ``EXEMPTION_RULES`` rows in order; the first row that matches wins. Each row
names the kind of exemption and how its words look. The holder words are the subject written before the cue ("We",
"Manager", "The price"), as written; jason does not decide here whose they are. A plain prohibition ("shall not
disclose", "will not share") matches no row and stays a prohibition.

A list under an "Exclusions:" heading has its items on lines of their own, each a phrase with no verb.
``excluded_items(text)`` reads those items, so each one is an exemption even though the sentence alone is not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ExemptionKind(Enum):
    NOT_OBLIGATED = "not obligated"
    NOT_RESPONSIBLE = "not responsible or liable"
    EXCLUDED = "excluded from the work"
    AS_IS = "as is"
    NO_WARRANTY = "no warranty"
    LIMITED_TO = "limited to"


@dataclass(frozen=True)
class Exemption:
    kind: ExemptionKind
    cue: str
    holder_words: str


@dataclass(frozen=True)
class ExemptionRule:
    """One way an exemption is written: its kind, the pattern of its cue, and what the row is for."""

    kind: ExemptionKind
    pattern: re.Pattern[str]
    note: str


def _rule(kind: ExemptionKind, pattern: str, note: str) -> ExemptionRule:
    return ExemptionRule(kind, re.compile(pattern, re.IGNORECASE), note)


# An adverb may sit inside the cue ("is specifically not responsible", "shall not in any event be liable").
_ADV = r"(?:\w+ly\s+|in\s+any\s+event\s+|at\s+any\s+time\s+)?"

EXEMPTION_RULES: tuple[ExemptionRule, ...] = (
    _rule(ExemptionKind.NOT_OBLIGATED,
          rf"\b(?:shall|will|would)\s+{_ADV}not\s+{_ADV}be\s+{_ADV}(?:obligated|required)\s+to\b",
          "shall not be obligated/required to"),
    _rule(ExemptionKind.NOT_OBLIGATED,
          rf"\b(?:is|are|am)\s+{_ADV}not\s+{_ADV}(?:obligated|required)\s+to\b",
          "is/are not obligated/required to"),
    _rule(ExemptionKind.NOT_OBLIGATED,
          rf"\b(?:shall|will)\s+have\s+no\s+{_ADV}(?:obligation|duty|responsibility)\s+(?:to|for)\b",
          "shall have no obligation/duty to"),
    _rule(ExemptionKind.NOT_RESPONSIBLE,
          rf"\b(?:is|are|am)\s+{_ADV}not\s+{_ADV}(?:responsible|liable)\b",
          "is/are not responsible/liable for"),
    _rule(ExemptionKind.NOT_RESPONSIBLE,
          rf"\b(?:shall|will)\s+{_ADV}not\s+{_ADV}be\s+{_ADV}(?:held\s+)?(?:responsible|liable)\b",
          "shall not be responsible/liable"),
    _rule(ExemptionKind.NOT_RESPONSIBLE,
          rf"\b(?:assumes?|bears?|accepts?)\s+{_ADV}no\s+{_ADV}(?:responsibility|liability)\b",
          "assumes/bears/accepts no responsibility/liability"),
    # "excludes nothing from this warranty" excludes nothing.
    _rule(ExemptionKind.EXCLUDED, r"\bexcludes\b(?!\s+(?:nothing|none|no)\b)", "excludes"),
    _rule(ExemptionKind.EXCLUDED, rf"\b(?:is|are)\s+{_ADV}excluded\b", "is/are excluded"),
    _rule(ExemptionKind.EXCLUDED, r"\bexclusions\s*:", "exclusions:"),
    _rule(ExemptionKind.EXCLUDED, r"\b(?:does|do)\s+not\s+include\b", "does not include"),
    _rule(ExemptionKind.EXCLUDED, r"\b(?:(?:is|are)\s+)?not\s+included\b", "is not included"),
    # "such as is customary" and "as is necessary" use the words without selling anything as is.
    _rule(ExemptionKind.AS_IS,
          r"(?<!such\s)(?<!as\sfar\s)(?<!as\smuch\s)\bas[\s-]is\b(?!\s+(?:customary|necessary|required|reasonable|"
          r"practicable|possible|appropriate|the\s+case|provided|set\s+forth|stated|described))",
          "as is"),
    _rule(ExemptionKind.NO_WARRANTY, r"\bno\s+warrant(?:y|ies)\b", "no warranty"),
    _rule(ExemptionKind.NO_WARRANTY,
          r"\bmakes?\s+no\s+(?:[\w,]+\s+){0,4}?warrant(?:y|ies)\b",
          "makes no warranty"),
    # "disclaims any interest in the easement" disclaims no warranty: a warranty or liability must be in the clause.
    _rule(ExemptionKind.NO_WARRANTY,
          r"\bdisclaims?\b(?:(?!,\s+(?:and|but|or)\s)[^.;])*?\b(?:warrant(?:y|ies)|liabilit(?:y|ies))\b",
          "disclaims ... warranty or liability"),
    _rule(ExemptionKind.LIMITED_TO,
          r"\b(?:liability|warrant(?:y|ies))\b[^.;]*?\blimited\s+to\b",
          "liability ... limited to, or warranty ... limited to"),
)

# The subject is the words after the last clause break before the cue: a period, semicolon, colon, ", and", or
# "that". A plain comma is not a break, and a business suffix's period is not one either ("Example Alarm, Inc.").
_CLAUSE_BREAK = re.compile(
    r"(?:(?<!\bInc)(?<!\bCo)(?<!\bCorp)(?<!\bLtd)(?<!\bLLC)\.\s+|[;:]\s+|,\s+(?:and|but|or)\s+|\bthat\s+)",
    re.IGNORECASE)
# A leading section number or heading label is not part of the subject ("1.5 Manager", "5. LIMITS. We").
_LEADING_NUMBER = re.compile(r"^\s*(?:\(?[0-9]+(?:\.[0-9]+)*[.)]?|\(?[a-z][.)])\s+", re.IGNORECASE)


def _holder_words(before: str) -> str:
    parts = _CLAUSE_BREAK.split(before)
    words = parts[-1] if parts else ""
    words = _LEADING_NUMBER.sub("", words)
    return " ".join(words.split())


# "Sold in as-is condition" has no subject: the words before the cue open with a participle. Those words are not a
# holder, so an as-is exemption with them has none ("The equipment is sold as is" keeps "The equipment is sold").
_NO_SUBJECT_START = re.compile(
    r"^(?:sold|bought|purchased|provided|furnished|delivered|accepted|conveyed|leased|rented|installed|supplied|"
    r"transferred|taken|given|offered|\w+ed)\b",
    re.IGNORECASE)


def _as_is_holder(words: str) -> str:
    return "" if _NO_SUBJECT_START.match(words) else words


def exemption_of(sentence: str) -> Exemption | None:
    """The first ``EXEMPTION_RULES`` row the sentence matches, or None when it says no duty ends.

    A sentence may join an exemption to a duty ("X is not required to ..., but Contractor shall keep ..."); the
    exemption is returned all the same. Callers that need to know which clause it is in test ``clauses(sentence)``.
    """
    for rule in EXEMPTION_RULES:
        found = rule.pattern.search(sentence)
        if found:
            holder = _holder_words(sentence[:found.start()])
            if rule.kind is ExemptionKind.AS_IS:
                holder = _as_is_holder(holder)
            return Exemption(rule.kind, found.group(0), holder)
    return None


_CLAUSE_SPLIT = re.compile(r";\s+|,\s+(?:but|and)\s+", re.IGNORECASE)


def clauses(sentence: str) -> list[str]:
    """The sentence's clauses, split at "; ", ", but " and ", and ", so each can be tested on its own."""
    return [part.strip() for part in _CLAUSE_SPLIT.split(sentence) if part.strip()]


def is_exemption(sentence: str) -> bool:
    return exemption_of(sentence) is not None


_EXCLUSIONS_HEADING = re.compile(r"^\s*(?:work\s+)?(?:exclusions|not\s+included|excluded)\s*:?\s*$", re.IGNORECASE)
_LIST_ITEM = re.compile(r"^\s*(?:[0-9]+[.)]|\(?[a-z][.)]|[-*•o])\s+(?P<item>\S.*?)\s*$", re.IGNORECASE)


# Another heading ends a list: a line that ends in a colon, or a short line in capitals ("PAYMENT TERMS").
_HEADING = re.compile(r"^\s*(?:[^.]{1,60}:|[A-Z][A-Z0-9 &/,'-]{2,60})\s*$")


def excluded_items(text: str) -> tuple[str, ...]:
    """The items listed on their own lines under a heading such as "Exclusions:", in order.

    A bulleted or numbered list ends at the first line that is not an item, so the paragraph after it is not read as
    excluded. A list of plain lines takes one item a line and ends at a blank line or another heading.
    """
    items: list[str] = []
    under = False
    style = ""  # "", "bullet", or "plain": set by the first item under the heading
    for line in text.splitlines():
        if _EXCLUSIONS_HEADING.match(line):
            under, style = True, ""
            continue
        if not under:
            continue
        if not line.strip():
            if style == "plain":
                under = False
            continue
        item = _LIST_ITEM.match(line)
        if item and style in ("", "bullet"):
            style = "bullet"
            items.append(item.group("item"))
        elif style == "" and not _HEADING.match(line):
            style = "plain"
            items.append(line.strip())
        elif style == "plain" and not _HEADING.match(line):
            items.append(line.strip())
        else:
            under = False
    return tuple(items)


__all__ = ["ExemptionKind", "Exemption", "ExemptionRule", "EXEMPTION_RULES", "exemption_of", "is_exemption",
           "clauses", "excluded_items"]
