"""Codes and standards a contract brings in by reference.

A vendor's contract often says less than it binds: "inspected in strict accordance with NFPA 25" makes the whole of
that standard the scope of work, and "installed per the manufacturer's instructions" makes the maker's sheet the
measure of a good installation. The words that matter are then the standard's, not the contract's, so the board needs
to know which standards a contract names and whether it incorporates them or only mentions them.

``find_standards(text)`` reads every standard named in the text with the ``STANDARD_ROWS`` rows, in order; the first
row that claims a span wins, so a longer name ("California Code of Regulations, Title 19") is a row before a shorter
one. Each ``Standard`` keeps its name as written, its family, and the cue that brings it in: a phrase such as "in
accordance with" or "to meet the minimum requirements of" before it in the same sentence (the ``CUE_ROWS``). A
standard joined to a cued one ("NFPA 25 (as amended by Title 19)") shares that cue. A standard with no cue is only
mentioned, and its cue is empty.

"per" and "follow" are cues only when the standard follows them with nothing but filler words between ("per the
current NFPA 25"); "per month" and "per visit" bring nothing in. Such a short cue reaches only a standard that carries
a number ("NFPA 25", "UL 300"), a code row (Title 19 or 24, the CBC, the CFC), or the manufacturer's instructions, so an
acronym used as an adjective ("$40 per ADA ramp") is not brought in.

A cue in a negated clause ("not in accordance with", "shall not be obligated to ... in accordance with") brings nothing
in. A bare "Title 19" is the California Code of Regulations only with CCR, regulations, or fire context near it in the
sentence, and "Title 19 of the Municipal Code" (or City or County Code) is never a state title (the
``_TITLE_CONTEXT_ROWS``). An edition printed before the name ("the 2019 edition of NFPA 72") is kept in the name as
"NFPA 72 (2019)".

``label`` gives a standard's short form for a report ("NFPA 25 (2013 California Edition)", "Title 19"), and
``describe`` joins the labels of several, once each. jason reads which standards a contract names; it does not read
the standards, and whether an edition is the one in force is a question for the authority having jurisdiction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Family(str, Enum):
    """The kind of code or standard; the value is the short key a ``Standard`` carries."""

    NFPA = "nfpa"
    TITLE_19 = "title-19"
    TITLE_24 = "title-24"
    CBC = "cbc"
    CFC = "cfc"
    UL = "ul"
    ADA = "ada"
    OSHA = "osha"
    MANUFACTURER = "manufacturer"
    LOCAL_CODE = "local-code"


@dataclass(frozen=True)
class StandardRow:
    family: Family
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class CueRow:
    """A phrase that brings a standard in. ``reach`` is how many characters may sit between it and the standard;
    ``filler_only`` cues ("per") allow only filler words between, so "per month" never reaches a later standard."""

    pattern: re.Pattern[str]
    reach: int = 80
    filler_only: bool = False


@dataclass(frozen=True)
class Standard:
    name: str
    family: str
    cue: str
    start: int
    end: int


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


_NFPA = (r"(?:\b(?P<pre>(?:19|20)\d{2})\s+edition\s+of\s+(?:the\s+)?)?"
         r"\bNFPA[\s-]*(?:No\.?\s*|#\s*)?(?P<number>\d{1,4}[A-Z]?)\b"
         r"(?:[\s,]*\(?(?P<year>(?:19|20)\d{2})\)?(?!\d))?"
         r"(?:\s*(?P<edition>California|National)?\s*Edition\b)?")
_CCR = r"(?:CCR|California\s+Code\s+of\s+Regulations)"

# Acronyms are matched in capitals only ((?-i:...)), so "ada" or "ul" inside a word or in lower case is not a name.
STANDARD_ROWS: tuple[StandardRow, ...] = (
    StandardRow(Family.NFPA, _rx(_NFPA)),
    StandardRow(Family.TITLE_19, _rx(rf"\b{_CCR},?\s*Title\s*19\b|\bTitle\s*19(?:,?\s*{_CCR})?\b|\b19\s*CCR\b")),
    StandardRow(Family.TITLE_24, _rx(rf"\b{_CCR},?\s*Title\s*24\b|\bTitle\s*24(?:,?\s*{_CCR})?\b|\b24\s*CCR\b"
                                     r"|\bCalifornia\s+Building\s+Standards\s+Code\b")),
    StandardRow(Family.CBC, _rx(r"\bCalifornia\s+Building\s+Code\b|(?-i:\bCBC\b)")),
    StandardRow(Family.CFC, _rx(r"\bCalifornia\s+Fire\s+Code\b|(?-i:\bCFC\b)")),
    StandardRow(Family.UL, _rx(r"(?-i:\bUL)[\s-]*(?:#\s*)?\d{2,4}[A-Z]?\b|(?-i:\bUL)[\s-]+(?:listed|classified|certified)\b"
                               r"|\bUnderwriters\s+Laboratories\b")),
    StandardRow(Family.ADA, _rx(r"(?-i:\bADA\b)|\bAmericans\s+with\s+Disabilities\s+Act\b")),
    StandardRow(Family.OSHA, _rx(r"(?-i:\b(?:Cal/)?OSHA\b)")),
    StandardRow(Family.MANUFACTURER, _rx(r"\bmanufacturer(?:['’]s|s['’]|s)?\s+(?:(?:written|published|current)\s+)?"
                                         r"(?:installation\s+)?(?:instructions|specifications|recommendations|guidelines)\b")),
    StandardRow(Family.LOCAL_CODE, _rx(r"\b(?:all\s+)?(?:applicable\s+)?local\s+(?:building\s+|fire\s+)?"
                                       r"(?:codes?|ordinances?)(?:\s+and\s+ordinances)?\b")),
)

@dataclass(frozen=True)
class _TitleContextRow:
    """A bare code title ("Title 19", no CCR in the match) is a state title only when ``context`` is found near it in
    the same sentence (``None``: always), and never when ``reject`` follows it."""

    family: Family
    context: re.Pattern[str] | None
    reject: re.Pattern[str]


_LOCAL_TITLE = _rx(r"^\s*,?\s*of\s+the\s+(?:[\w.-]+\s+){0,3}?(?:Municipal|City|County)\s+Code\b")
_TITLE_CONTEXT_ROWS: tuple[_TitleContextRow, ...] = (
    _TitleContextRow(Family.TITLE_19,
                     _rx(rf"{_CCR}|\bregulations?\b|\bfire\b|\bState\s+Fire\s+Marshal\b|\bNFPA\b"), _LOCAL_TITLE),
    _TitleContextRow(Family.TITLE_24, None, _LOCAL_TITLE),
)
_CCR_IN = _rx(_CCR)
_TITLE_REACH = 80

# Families a short (``filler_only``) cue may reach; UL only with a number.
_SHORT_CUE_FAMILIES = frozenset({Family.NFPA, Family.UL, Family.TITLE_19, Family.TITLE_24, Family.CBC, Family.CFC,
                                 Family.MANUFACTURER})

CUE_ROWS: tuple[CueRow, ...] = (
    CueRow(_rx(r"\bin\s+(?:strict\s+|full\s+)?accordance\s+with\b")),
    CueRow(_rx(r"\b(?:to\s+)?meet(?:s|ing)?\s+(?:all\s+)?(?:of\s+)?(?:the\s+)?(?:minimum\s+)?requirements\s+of\b")),
    CueRow(_rx(r"\bas\s+required\s+by\b")),
    CueRow(_rx(r"\bpursuant\s+to\b")),
    CueRow(_rx(r"\b(?:compl(?:y|ies|ying)\s+with|in\s+compliance\s+with)\b")),
    CueRow(_rx(r"\bconform(?:s|ing)?\s+(?:to|with)\b")),
    CueRow(_rx(r"\bas\s+defined\s+(?:by|in)\b")),
    CueRow(_rx(r"\bper\b"), reach=40, filler_only=True),
    CueRow(_rx(r"\bfollows?\b"), reach=40, filler_only=True),
)

_FILLER = _rx(r"^(?:\s*(?:the|all|any|applicable|current|latest|most|recent|edition|of|and|its)\b)*[\s,]*$")
# Text that may join a standard to a cued one before it and share that cue.
_JOIN = _rx(r"^[\s,(]*(?:(?:as\s+amended\s+by|and/or|and|or|including|together\s+with)\b)?[\s,(]*$")
# A sentence ends at . ! ? ; before a space (not after a short abbreviation), or at a bullet on its own line.
_BREAK = re.compile(r"(?<!\bNo)(?<!\bInc)(?<!\b[A-Z])[.!?;](?=\s|$)|\n\s*(?:o|•|-|\*)\s*\n")


# Where a clause starts: a sentence break, a comma or colon, or a word that opens a new clause.
_CLAUSE = re.compile(_BREAK.pattern + r"|[,:]|(?i:\b(?:but|however|provided|unless|except)\b"
                     r"|\band\s+(?:shall|will|must)\b)")
_NEGATION = _rx(r"\b(?:not|never|neither|nor)\b|n['’]t\b")
_NEGATION_REACH = 120


def _negated(text: str, cue_start: int) -> bool:
    """Whether a negation sits in the clause before the cue that starts at ``cue_start``."""
    before = text[max(0, cue_start - _NEGATION_REACH):cue_start]
    starts = [m.end() for m in _CLAUSE.finditer(before)]
    return bool(_NEGATION.search(before[starts[-1] if starts else 0:]))


def _short_cue_reaches(family: Family | None, name: str) -> bool:
    """Whether a short cue ("per", "follow") may bring in a standard of ``family`` named ``name``."""
    if family not in _SHORT_CUE_FAMILIES:
        return False
    return family != Family.UL or bool(re.search(r"\d", name))


def _sentence_around(text: str, start: int, end: int) -> str:
    """The text of the same sentence within ``_TITLE_REACH`` characters either side of ``start``..``end``."""
    before = text[max(0, start - _TITLE_REACH):start]
    breaks = [m.end() for m in _BREAK.finditer(before)]
    after = text[end:end + _TITLE_REACH]
    stop = _BREAK.search(after)
    return before[breaks[-1] if breaks else 0:] + " " + (after[:stop.start()] if stop else after)


def _title_holds(text: str, start: int, end: int, family: Family) -> bool:
    """Whether a code title matched at ``start``..``end`` is the state title its row names."""
    for row in _TITLE_CONTEXT_ROWS:
        if row.family != family:
            continue
        if row.reject.match(text[end:end + _TITLE_REACH]):
            return False
        if row.context is None or _CCR_IN.search(text[start:end]):
            return True
        return bool(row.context.search(_sentence_around(text, start, end)))
    return True


def _cue_before(text: str, start: int, family: Family | None = None, name: str = "") -> str:
    """The nearest cue in the same sentence that reaches the standard starting at ``start``, else ''. A cue in a
    negated clause reaches nothing, and a short cue reaches only the families in ``_SHORT_CUE_FAMILIES``."""
    best: tuple[int, str] | None = None
    for row in CUE_ROWS:
        window_start = max(0, start - row.reach - 60)
        for m in row.pattern.finditer(text, window_start, start):
            gap = text[m.end():start]
            if len(gap) > row.reach or _BREAK.search(gap):
                continue
            if row.filler_only and not (_FILLER.match(gap) and _short_cue_reaches(family, name)):
                continue
            if _negated(text, m.start()):
                continue
            if best is None or m.end() > best[0]:
                best = (m.end(), " ".join(m.group(0).split()))
    return best[1] if best else ""


def find_standards(text: str) -> list[Standard]:
    """Every code or standard named in ``text``, in order, each with the cue that brings it in ('' if none)."""
    claimed: list[tuple[int, int, Family, str]] = []
    for row in STANDARD_ROWS:
        for m in row.pattern.finditer(text):
            if any(m.start() < e and s < m.end() for s, e, _, _ in claimed):
                continue
            if not _title_holds(text, m.start(), m.end(), row.family):
                continue
            name = " ".join(m.group(0).split())
            if row.family == Family.NFPA and m.group("pre"):
                name = f"NFPA {m['number'].upper()} ({m['pre']})"
            claimed.append((m.start(), m.end(), row.family, name))
    claimed.sort()
    out: list[Standard] = []
    for start, end, family, name in claimed:
        cue = _cue_before(text, start, family, name)
        if not cue and out and out[-1].cue and _JOIN.match(text[out[-1].end:start]):
            cue = out[-1].cue
        out.append(Standard(name, family.value, cue, start, end))
    return out


def incorporated(text: str) -> list[Standard]:
    """The standards ``text`` brings in by reference: those with a cue."""
    return [s for s in find_standards(text) if s.cue]


def incorporates(sentence: str) -> bool:
    """Whether a cue in ``sentence`` brings in a standard named after it in the same sentence."""
    return bool(incorporated(sentence))


def label(standard: Standard) -> str:
    """A standard's short form: "NFPA 25 (2013 California Edition)", "Title 19"; others as written."""
    if standard.family == Family.NFPA.value:
        m = _rx(_NFPA).match(standard.name)
        if m:
            edition = " ".join(p for p in (m["year"], (m["edition"] or "").title()) if p)
            if re.search(r"edition\s*$", standard.name, re.IGNORECASE):
                edition = f"{edition} Edition".strip()
            return f"NFPA {m['number'].upper()}" + (f" ({edition})" if edition else "")
    if standard.family == Family.TITLE_19.value:
        return "Title 19"
    if standard.family == Family.TITLE_24.value and "title" in standard.name.lower():
        return "Title 24"
    return standard.name


def describe(standards: list[Standard]) -> str:
    """The labels of ``standards``, once each in order, joined with commas."""
    return ", ".join(dict.fromkeys(label(s) for s in standards))


__all__ = ["Family", "StandardRow", "CueRow", "Standard", "STANDARD_ROWS", "CUE_ROWS", "find_standards",
           "incorporated", "incorporates", "label", "describe"]
