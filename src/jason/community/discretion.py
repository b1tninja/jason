"""How much room a contract sentence leaves the one who acts.

A duty says what a party must do; discretion says how far a party may choose. The two read differently in a review.
"Manager may adjust the fees in its sole discretion" binds no one to anything, yet it is the sentence a board most needs
to see, because the vendor can change the price alone. "Contractor will endeavor to finish by June 1" reads like a
promise and is only a promise to try: an effort standard, a duty of means, not of result.

``discretion_of(sentence)`` reads one sentence with the ``DISCRETION_RULES`` rows, in order; the first row that matches
wins, so a narrower cue ("may, but is not obligated to") sits before a broader one ("may ... at any time"). The record
keeps the cue as written, the subject who holds the room as written, and what the room is over when the words say
(price, fees, scope, terms, termination, schedule).

``flag(d, counterparty_words)`` turns a reading into a finding code for a review: a counterparty's unfettered discretion
or one-side change over price, fees, scope, terms, or termination, and any effort standard. Discretion the association
holds is a power, not a risk, and a right either party holds is mutual, so neither is flagged.

jason reads the words. Whether a clause is enforceable as written (an implied covenant of good faith limits even
"sole discretion") is a reading for counsel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Degree(Enum):
    UNFETTERED = "unfettered"
    BOUNDED = "bounded"
    JUDGMENT = "judgment"
    APPROVAL_GATED = "approval-gated"
    ONE_SIDE_CHANGE = "one-side change"
    PERMISSION_WITHOUT_DUTY = "permission without duty"
    EFFORT = "effort standard"
    QUALITY = "quality standard"
    MUTUAL_CHANGE = "mutual change"


@dataclass(frozen=True)
class Discretion:
    degree: Degree
    cue: str
    holder_words: str
    over: str


_POSSESSIVE = r"(?:its|his|her|their|our|your|the\s+\w+['’]s|\w+['’]s)"
_CHANGE_VERBS = r"(?:terminate|suspend|increase|raise|adjust|modify|update|change|amend|revise|cancel|discontinue)"
_ANYTIME = r"(?:at\s+any\s+time|for\s+any\s+reason|for\s+no\s+reason|without\s+(?:prior\s+)?(?:notice|cause))"
_HOLDER_END = r"(?=\s*[,.;()]|\s+(?:and|or|which|before|prior|in|for|to|that)\b|\s*$)"
# A one-side change names what changes: the agreement, the service, the price, or the terms. "Contractor may terminate
# the hose at the valve" changes none of them.
_CHANGE_OBJECT = (
    r"(?:(?:this|the|these|those|its|our|their|your|his|her|such|any|all|said)\s+)?(?:[\w\-]+\s+){0,2}"
    r"(?:agreement|contract|services?|prices?|pricing|fees?|rates?|charges?|terms|schedule|scope)\b"
)
# A comma clause between "may" and its verb: "may, at any time and without notice, change".
_INTERPOSED = r"(?:,[^,.;]{1,80},\s*)?"
# "at the Manager's sole discretion": the holder when the words name one; a pronoun leaves it to the subject.
_AT_POSSESSIVE = r"at\s+(?:its|his|her|their|our|your|(?P<holder>(?:the\s+)?[\w&.\-]+['’]s))"

# Each row is (degree, pattern). A pattern may name a ``holder`` group when the cue itself says who holds the room
# ("as the Manager deems", "subject to the Board's approval"); otherwise the holder is the sentence's subject.
DISCRETION_RULES: tuple[tuple[Degree, str], ...] = (
    (Degree.PERMISSION_WITHOUT_DUTY,
     r"\bmay\s*,?\s*but\s+(?:is|are|shall|will)\s+not\s+(?:be\s+)?(?:obligated|required|bound)\s+to\b"),
    (Degree.PERMISSION_WITHOUT_DUTY, r"\bmay\s*,?\s*but\s+need\s+not\b"),
    (Degree.PERMISSION_WITHOUT_DUTY, r"\b(?:has|have|shall\s+have)\s+the\s+right\s*,?\s*but\s+not\s+the\s+obligation\b"),
    (Degree.UNFETTERED,
     rf"\b{_AT_POSSESSIVE}\s+(?:sole\s+and\s+absolute|absolute\s+and\s+sole|sole|absolute)\s+discretion\b"),
    (Degree.UNFETTERED,
     r"\b(?:sole|absolute|complete|unfettered|unrestricted|sole\s+and\s+absolute|absolute\s+and\s+sole)\s+discretion\b"),
    (Degree.UNFETTERED, rf"\bat\s+{_POSSESSIVE}\s+(?:sole\s+)?option\b"),
    (Degree.UNFETTERED, r"\breserves?\s+the\s+right\s+to\b"),
    (Degree.UNFETTERED, r"\bmay\s+elect\s+to\b"),
    (Degree.BOUNDED, rf"\b{_AT_POSSESSIVE}\s+reasonable\s+discretion\b"),
    (Degree.BOUNDED, r"\breasonable\s+discretion\b"),
    (Degree.BOUNDED, r"\bnot\s+(?:to\s+)?be\s+unreasonably\s+(?:withheld|delayed|conditioned)\b"),
    (Degree.BOUNDED, r"\bshall\s+not\s+unreasonably\s+(?:withhold|delay|condition)\b"),
    (Degree.BOUNDED, r"\bin\s+good\s+faith\b"),
    (Degree.APPROVAL_GATED,
     rf"\bsubject\s+to\s+the\s+(?:prior\s+)?(?:written\s+)?(?:approval|consent)\s+of\s+(?P<holder>[^,.;()]{{1,40}}?){_HOLDER_END}"),
    (Degree.APPROVAL_GATED,
     r"\bsubject\s+to\s+(?P<holder>(?:the\s+)?[\w&.\-]+(?:\s+[\w&.\-]+){0,3}?['’]s|its|his|her|their|our|your)"
     r"\s+(?:prior\s+)?(?:written\s+)?(?:approval|consent)\b"),
    (Degree.APPROVAL_GATED,
     r"\b(?P<holder>(?:the\s+)?[\w&.\-]+['’]s|its|his|her|their|our|your)\s+prior\s+written\s+(?:approval|consent)\b"),
    (Degree.APPROVAL_GATED,
     rf"\bprior\s+written\s+(?:approval|consent)\s+of\s+(?P<holder>[^,.;()]{{1,40}}?){_HOLDER_END}"),
    (Degree.APPROVAL_GATED, r"\bprior\s+written\s+(?:approval|consent)\b"),
    (Degree.ONE_SIDE_CHANGE,
     rf"\bmay\b\s*{_INTERPOSED}(?:\w+\s+){{0,2}}?(?P<verb>{_CHANGE_VERBS})\s+(?P<obj>{_CHANGE_OBJECT})[^.;]*?\b{_ANYTIME}"),
    (Degree.ONE_SIDE_CHANGE,
     rf"\bmay\b\s*,(?=[^,.;]*{_ANYTIME})[^,.;]{{1,80}},\s*(?:\w+\s+){{0,2}}?(?P<verb>{_CHANGE_VERBS})\s+(?P<obj>{_CHANGE_OBJECT})"),
    (Degree.ONE_SIDE_CHANGE,
     rf"\b{_ANYTIME}\b[^.;]*?\bmay\b\s*{_INTERPOSED}(?:\w+\s+){{0,2}}?(?P<verb>{_CHANGE_VERBS})\s+(?P<obj>{_CHANGE_OBJECT})"),
    (Degree.ONE_SIDE_CHANGE,
     r"\b(?P<obj>prices|pricing|rates|fees|charges|terms)\s+(?:are|is)\s+subject\s+to\s+change\s+"
     r"(?:without\s+(?:prior\s+)?notice|at\s+any\s+time)\b"),
    # The passive leaves the actor unnamed; a change made only by both parties' writing is not one side's.
    (Degree.ONE_SIDE_CHANGE,
     r"\bmay\s+be\s+(?:adjusted|increased|raised|changed|modified|revised|amended)\b(?!\s+only\b)"
     r"(?![^.;]*\b(?:mutual\w*|both\s+parties|the\s+parties|signed\s+by)\b)"),
    (Degree.JUDGMENT, rf"\bin\s+{_POSSESSIVE}\s+(?:reasonable\s+|professional\s+|sole\s+|best\s+)?(?:judgment|judgement|opinion)\b"),
    (Degree.JUDGMENT, rf"\bin\s+{_POSSESSIVE}\s+discretion\b"),
    (Degree.JUDGMENT, rf"\b{_AT_POSSESSIVE}\s+discretion\b"),
    (Degree.JUDGMENT, r"\b(?P<holder>it|he|she|they|we|you|(?:the\s+)?[\w&.\-]+)\s+deems?\b"),
    (Degree.JUDGMENT, rf"\bas\s+(?:reasonably\s+)?determined\s+by\s+(?P<holder>[^,.;()]{{1,40}}?){_HOLDER_END}"),
    (Degree.EFFORT,
     r"\b(?:use|uses|using|exercise|make)\s+(?:its|their|his|her|our|your|all)?\s*"
     r"(?:commercially\s+reasonable|reasonable|best|diligent|good[\s-]faith)\s+efforts?\b"),
    (Degree.EFFORT, r"\b(?:commercially\s+reasonable|reasonable|best|diligent)\s+efforts\b"),
    (Degree.EFFORT, r"\bendeavou?rs?\b"),
    (Degree.EFFORT, r"\b(?:will|shall|to|may)\s+attempt\s+to\b"),
    (Degree.EFFORT, r"\b(?:will\s+try|tries\s+to|try\s+to)\b"),
    # A quality standard says how well the work is done, not how hard a party must try: it is not a duty of means.
    (Degree.QUALITY, r"\b(?:good\s+and\s+)?workmanlike\b"),
    (Degree.QUALITY, r"\bindustry\s+standards?\b"),
)

_COMPILED = tuple((degree, re.compile(pattern, re.IGNORECASE)) for degree, pattern in DISCRETION_RULES)

# What the room is over: the first of these named after the cue, then anywhere in the sentence.
OVER_RULES: tuple[tuple[str, str], ...] = (
    ("termination", r"\b(?:terminat\w*|cancel\w*|suspend\w*|discontinu\w*)\b"),
    ("fees", r"\bfees?\b"),
    ("price", r"\b(?:prices?|pricing|charges?|rates?|costs?|contract\s+sum|compensation)\b"),
    ("terms", r"\b(?:terms|agreement|contract)\b"),
    ("scope", r"\b(?:scope|services|specifications)\b"),
    ("schedule", r"\b(?:schedule|dates?|hours)\b"),
)

_OVER_COMPILED = tuple((name, re.compile(pattern, re.IGNORECASE)) for name, pattern in OVER_RULES)

_SUBJECT = re.compile(
    r"^\s*(?:(?:\d+(?:\.\d+)*\.?|\(?[a-z0-9]{1,3}\)|[-•*])\s+)?"
    r"(?:(?:when|if|where|after|once|unless|upon|at|in|for|during|notwithstanding)\b[^,]*,\s*)?"
    r"(?P<s>.+?)\s*,?\s+(?:may|shall|will|must|can|reserves?|agrees?|elects?|deems?|is|are|has|have)\b",
    re.IGNORECASE,
)

_LEADING_PREPOSITION = re.compile(r"^(?:without|with|of|by|to|upon|on)\s+", re.IGNORECASE)


def _clean(words: str) -> str:
    words = " ".join(words.split())
    while True:
        stripped = _LEADING_PREPOSITION.sub("", words)
        if stripped == words:
            return words.strip(" ,")
        words = stripped


def _subject(sentence: str) -> str:
    m = _SUBJECT.search(sentence)
    return _clean(m.group("s")) if m else ""


def _first_over(text: str) -> str:
    hits = [(m.start(), i, name) for i, (name, rx) in enumerate(_OVER_COMPILED) if (m := rx.search(text))]
    return min(hits)[2] if hits else ""


def _over(sentence: str, start: int) -> str:
    for text in (sentence[start:], sentence):
        if over := _first_over(text):
            return over
    return ""


_TERMINATION_VERB = re.compile(r"(?:terminate|suspend|cancel|discontinue)", re.IGNORECASE)


def _over_of(m: re.Match[str], sentence: str) -> str:
    """What the room is over. A one-side change reads it from the verb's object, never from the verb alone: ending the
    agreement or the service is over termination; changing the price is over price."""
    groups = m.groupdict()
    obj = groups.get("obj")
    if obj is None:
        return _over(sentence, m.start())
    over = _first_over(obj)
    verb = groups.get("verb")
    if verb and _TERMINATION_VERB.fullmatch(verb) and over in ("", "terms", "scope"):
        return "termination"
    return over


def discretion_of(sentence: str) -> Discretion | None:
    """The first ``DISCRETION_RULES`` row that matches the sentence, or None when it leaves no stated room."""
    for degree, rx in _COMPILED:
        m = rx.search(sentence)
        if not m:
            continue
        holder = m.groupdict().get("holder")
        holder_words = _clean(holder) if holder else _subject(sentence)
        if _MUTUAL.search(_norm(holder_words)):
            degree = _MUTUAL_DEGREE.get(degree, degree)
        return Discretion(degree, " ".join(m.group(0).split()), holder_words, _over_of(m, sentence))
    return None


# Pronoun forms of one party, so "our" matches a counterparty given as "we".
_PRONOUN_SETS: tuple[frozenset[str], ...] = (
    frozenset({"we", "us", "our", "ours"}),
    frozenset({"you", "your", "yours"}),
    frozenset({"it", "its"}),
    frozenset({"they", "them", "their", "theirs"}),
)

_MUTUAL = re.compile(r"^(?:either|each|both|any)\s+part(?:y|ies)\b|^(?:the\s+)?parties\b", re.IGNORECASE)

_RISK_OVER = frozenset({"price", "fees", "scope", "terms", "termination"})

# A change either party may make is mutual, not one side's.
_MUTUAL_DEGREE: dict[Degree, Degree] = {Degree.ONE_SIDE_CHANGE: Degree.MUTUAL_CHANGE}


def _norm(words: str) -> str:
    words = re.sub(r"['’]s$", "", words.strip().lower())
    return re.sub(r"^the\s+", "", words)


def holds(holder_words: str, counterparty_words: tuple[str, ...]) -> bool:
    """Whether the holder's words name the counterparty or its pronoun; a mutual holder never does."""
    holder = _norm(holder_words)
    if not holder or _MUTUAL.search(holder):
        return False
    for word in counterparty_words:
        w = _norm(word)
        if not w:
            continue
        if holder == w or re.search(rf"\b{re.escape(w)}\b", holder):
            return True
        if any(holder in forms and w in forms for forms in _PRONOUN_SETS):
            return True
    return False


_holds = holds


def flag(d: Discretion, counterparty_words: tuple[str, ...]) -> str | None:
    """A finding code for a review, or None when the reading is not a risk to the association."""
    if d.degree is Degree.EFFORT:
        return "effort-standard"
    if d.degree in (Degree.QUALITY, Degree.MUTUAL_CHANGE):
        return None
    if d.over not in _RISK_OVER or not holds(d.holder_words, counterparty_words):
        return None
    if d.degree is Degree.UNFETTERED:
        return "vendor-unfettered-over-price"
    if d.degree is Degree.ONE_SIDE_CHANGE:
        return "vendor-one-side-change"
    return None


__all__ = [
    "DISCRETION_RULES",
    "Degree",
    "Discretion",
    "OVER_RULES",
    "discretion_of",
    "flag",
    "holds",
]
