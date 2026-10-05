"""Consents and releases in a contract: whose say-so an act needs, and whose claims a party gives up.

A consent clause gates an act on another party's word: "Contractor may not assign this Agreement without the consent of
the other party", "Extra work is subject to the Board's prior written approval". A review needs three things from it:
whose consent is needed, whether it must be in writing and given first, and what it is over (assignment, subcontracting,
changes, extra work, entry). A gate the association holds protects it; a gate the vendor holds on the association's own
acts is a finding.

A release runs the other way: a party gives up claims against another ("Owner releases the Association from any
liability", "Contractor waives any claim against ..."). It is read as its own record, ``Release``, because it moves risk
rather than gating an act.

``consent_of(sentence)`` reads one sentence with the ``CONSENT_RULES`` rows, in order; the first row that matches wins,
so a cue that names its holder ("without the consent of the other party") sits before a bare one ("after approval").
``holder_words`` is the holder as written, less a possessive ("our", "the Board", "Owner", "the other party"), or "" when
the words name none; who "our" is depends on how the contract defines its pronouns, which the contract reader settles, not
this module. An unmarked capitalised noun is a holder ("without Association approval"). A document or object is never one
(``OBJECT_WORDS``): "upon approval of this proposal" accepts a document and gates nothing, while "approval of the invoice
by the Board" is the Board's. A cue followed by a past-tense main verb ("with the approval of the members, the
Association adopted ...") is history, not a gate.
``over`` is the first ``OVER_RULES`` row the sentence names, or "" when it names none. ``release_of(sentence)`` reads the
``RELEASE_RULES`` rows the same way. A miss stays a miss: no cue, no record.

jason reads the words. Whether a release is enforceable (Civil Code 1542, 1668) is a reading for counsel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Consent:
    cue: str
    holder_words: str
    written: bool
    prior: bool
    over: str


@dataclass(frozen=True)
class Release:
    cue: str
    releasor_words: str
    released_words: str
    over: str


_POSS = r"(?:its|his|her|their|our|your|(?:the\s+)?[\w&.\-]+(?:\s+[\w&.\-]+){0,2}?(?:['’]s|(?<=s)['’](?!\w)))"
_NOUN = r"(?:consent|approval|authori[sz]ation|permission)"
# "prior written", "written prior", "express written", "advance": any order, at most three words.
_QUAL = r"(?:(?:prior|advance|express|expressed|written|signed|first)\s+){0,3}"
_HOLDER_END = r"(?=\s*[,.;:()]|\s+(?:and|or|which|before|prior|in|for|to|that|is|shall|will|has|being|arising|resulting|relating|related|under|from|with|by|on|due)\b|\s*$)"
# A company name keeps its suffix: "Example Roofing, Inc."
_SUFFIX = r"(?:,?\s+(?:Inc|LLC|L\.L\.C|Co|Corp|Ltd|LP|LLP)\b\.?)?"
_NAMED = rf"(?P<holder>[^,.;:()]{{1,40}}?{_SUFFIX}){_HOLDER_END}"
_POSS_HOLDER = rf"(?P<holder>{_POSS})"
_IN_WRITING = r"(?:\s+in\s+writing)?(?:\s+in\s+advance)?(?:\s+in\s+writing)?"
# A capitalised word that is not a qualifier or a cue: "Association", "Board", "Example Management".
_CAP_WORD = r"(?-i:(?!(?:Prior|Advance|Express|Expressed|Written|Signed|First|The|Such|Any|All|Its|His|Her|Their|Our|Your)\b)[A-Z][\w&\-]*)"
_BARE_HOLDER = rf"{_CAP_WORD}(?:\s+{_CAP_WORD}){{0,2}}"

# Words that name a document or an object, never a party: "approval of this proposal" accepts a document, it gates
# nothing on anyone's word. Each row is one word or phrase; a plural "s" is allowed.
OBJECT_WORDS: tuple[str, ...] = (
    "proposal", "invoice", "agreement", "contract", "plan", "drawing", "work", "change order", "estimate", "bid",
    "quote",
)
_OBJECT = re.compile(
    r"\b(?:" + "|".join(r"\s+".join(map(re.escape, w.split())) for w in OBJECT_WORDS) + r")s?$", re.IGNORECASE
)
# "approval of the invoice by the Board": the party follows the object.
_BY_HOLDER = re.compile(rf"^\s+by\s+{_NAMED}", re.IGNORECASE)
# "with the approval of the members, the Association adopted ...": history, not a gate. A past-tense main verb within
# a few words after the cue; a modal or a participle that opens a phrase ("provided", "required") is not one.
_NARRATIVE = re.compile(
    r"^\s*,\s*(?:(?!(?:shall|may|will|must|can|should|would|is|are|be)\b)[\w&.'’\-]+\s+){0,4}?"
    r"(?:was\s+|were\s+|had\s+)?"
    r"(?-i:(?!(?:provided|required|specified|stated|listed|attached|described|noted|signed|executed|need|exceed|proceed|succeed)\b)"
    r"[a-z]+ed)\b"
    # "any work performed shall ...": a participle before the main verb.
    r"(?!\s+(?:shall|may|will|must|can|should|would|is|are|was|were|by|under|without|in)\b)",
    re.IGNORECASE,
)

# Each row is a pattern; a ``holder`` group, when the cue names one, says whose consent is needed.
CONSENT_RULES: tuple[str, ...] = (
    # "without the prior written consent of the other party", "subject to the approval of the Board"
    rf"\b(?:without|subject\s+to|with|upon|after|following|requires?|requiring|obtain(?:s|ing)?|receiv(?:e|es|ing))\s+"
    rf"(?:the\s+|a\s+)?{_QUAL}{_NOUN}{_IN_WRITING}\s+of\s+{_NAMED}",
    # "without our prior written consent", "subject to the Board's approval", "with the Association's written approval"
    rf"\b(?:without|subject\s+to|with|upon|requires?|requiring|obtain(?:s|ing)?|receiv(?:e|es|ing))\s+"
    rf"{_POSS_HOLDER}\s+{_QUAL}{_NOUN}\b{_IN_WRITING}",
    # "unless approved in writing by Owner", "until consented to in advance by the Board"
    rf"\b(?:unless|until)\s+(?:first\s+|previously\s+)?(?:approved|authori[sz]ed|consented\s+to){_IN_WRITING}"
    rf"\s+(?:in\s+advance\s+)?by\s+{_NAMED}",
    # "must be approved in writing by the Association", "to be approved by client"
    rf"\b(?:must|shall|will|to)\s+(?:first\s+)?be\s+(?:first\s+|previously\s+)?(?:approved|authori[sz]ed|consented\s+to)"
    rf"{_IN_WRITING}\s+(?:in\s+advance\s+)?by\s+{_NAMED}",
    # "prior written approval of the Manager" without a leading verb
    rf"\b(?:prior|advance)\s+(?:written\s+)?{_NOUN}{_IN_WRITING}\s+of\s+{_NAMED}",
    # "the Board's prior written consent"
    rf"\b{_POSS_HOLDER}\s+(?:prior|advance)\s+(?:written\s+)?{_NOUN}\b",
    # "without Association approval", "subject to Owner approval", "with Board written consent": an unmarked capitalised
    # noun of one to three words, not a qualifier, right before the noun.
    rf"\b(?:without|subject\s+to|with|upon|after|following|requires?|requiring|obtain(?:s|ing)?|receiv(?:e|es|ing))\s+"
    rf"(?:the\s+)?(?P<holder>{_BARE_HOLDER})\s+{_QUAL}{_NOUN}\b{_IN_WRITING}",
    # "after approval", "after written authorization": the holder is unnamed.
    rf"\b(?:after|upon|following|with(?:out)?)\s+(?:{_POSS_HOLDER}\s+)?{_QUAL}(?:approval|authori[sz]ation)\b{_IN_WRITING}",
    # Bare "prior written consent".
    rf"\b(?:prior|advance)\s+written\s+{_NOUN}\b|\bwritten\s+prior\s+{_NOUN}\b",
)

_CONSENT_COMPILED = tuple(re.compile(pattern, re.IGNORECASE) for pattern in CONSENT_RULES)

# What needs the consent: the first of these the sentence names, by position.
OVER_RULES: tuple[tuple[str, str], ...] = (
    ("assignment", r"\bassign(?:s|ed|ing|ment)?\b|\btransfer\s+(?:this|the)\s+(?:agreement|contract)\b"),
    ("subcontracting", r"\bsub-?contract(?:s|ed|ing|ors?)?\b|\bdelegat\w*\b"),
    ("extra work", r"\b(?:extra|additional)\s+(?:work|repairs?|services?|visits?)\b|\bchange\s+orders?\b"),
    ("changes", r"\b(?:chang(?:e|es|ed|ing)|modif\w*|alter(?:s|ed|ing|ations?)?|amend\w*|substitut\w*)\b"),
    ("entry", r"\b(?:enter(?:s|ed|ing)?|entry|access)\b"),
)

_OVER_COMPILED = tuple((name, re.compile(pattern, re.IGNORECASE)) for name, pattern in OVER_RULES)

_RELEASE_OBJECT = (
    r"(?:(?:any|all|any\s+and\s+all|each\s+and\s+every)\s+)?(?:(?:past|present|future|further)\s+)?"
    r"(?:claims?|liabilit(?:y|ies)|responsibilit(?:y|ies)|obligations?|damages|demands|losses|rights?|causes?\s+of\s+action)"
)

# Each row is a pattern with a ``released`` group when the words name who is released.
RELEASE_RULES: tuple[str, ...] = (
    # "releases the Association from any liability"
    rf"\b(?:hereby\s+)?(?:releases?|discharges?|(?:agrees?|agree)\s+to\s+release)\s+(?:and\s+discharges?\s+)?"
    rf"(?P<released>[^,.;:()]{{1,60}}?)\s+(?:from|of)\s+(?P<obj>{_RELEASE_OBJECT})",
    # "waives all rights of subrogation against Owner"; "waiver of subrogation"
    rf"\b(?:waives?|waiver\s+of)\s+(?:(?:any|all)\s+)?(?:rights?\s+of\s+)?(?P<obj>subrogation)"
    rf"(?:[^.;]{{0,40}}?\bagainst\s+(?P<released>[^,.;:()]{{1,60}}?){_HOLDER_END})?",
    # "waives any claim against the Association"
    rf"\b(?:hereby\s+)?waives?\s+(?P<obj>{_RELEASE_OBJECT})(?:[^.;]{{0,60}}?\bagainst\s+(?P<released>[^,.;:()]{{1,60}}?){_HOLDER_END})?",
    # "shall not hold the Association liable for"
    rf"\b(?:shall|will)\s+not\s+hold\s+(?P<released>[^,.;:()]{{1,60}}?)\s+(?P<obj>liable|responsible)\b",
)

_RELEASE_COMPILED = tuple(re.compile(pattern, re.IGNORECASE) for pattern in RELEASE_RULES)

_RELEASE_OVER: tuple[tuple[str, str], ...] = (
    ("subrogation", r"subrogation"),
    ("liability", r"liab|responsib|liable|responsible"),
    ("claims", r"claim|damage|demand|loss|cause"),
    ("obligations", r"obligation"),
    ("rights", r"right"),
)

_SUBJECT = re.compile(
    r"^\s*(?:(?:\d+(?:\.\d+)*\.?|\(?[a-z0-9]{1,3}\)|[-•*])\s+)?"
    r"(?:(?:when|if|where|after|once|unless|upon|at|in|for|during|notwithstanding)\b[^,]*,\s*)?"
    r"(?P<s>.+?)\s*,?\s+(?:hereby\s+)?(?:may|shall|will|must|agrees?|releases?|discharges?|waives?)\b",
    re.IGNORECASE,
)

_LEADING_ARTICLE = re.compile(r"^(?:without|with|of|by|to|upon|on)\s+", re.IGNORECASE)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"“])")


_POSSESSIVE = re.compile(r"['’]s$|(?<=s)['’]$")  # "the Board's" and "the Members’"


def _clean(words: str) -> str:
    """The words as written, without a leading preposition or a trailing possessive: "the Board's" is "the Board"."""
    words = " ".join(words.split())
    while True:
        stripped = _LEADING_ARTICLE.sub("", words)
        if stripped == words:
            return _POSSESSIVE.sub("", words.strip(" ,"))
        words = stripped


def _over(sentence: str) -> str:
    hits = [(m.start(), i, name) for i, (name, rx) in enumerate(_OVER_COMPILED) if (m := rx.search(sentence))]
    return min(hits)[2] if hits else ""


def consent_of(sentence: str) -> Consent | None:
    """The first ``CONSENT_RULES`` row that matches the sentence, or None when it gates nothing on anyone's word."""
    for rx in _CONSENT_COMPILED:
        m = rx.search(sentence)
        if not m:
            continue
        end = m.end()
        holder = _clean(m.groupdict().get("holder") or "")
        if holder and _OBJECT.search(holder):
            # "approval of the invoice by the Board" names its party after the object; "approval of this proposal"
            # names none and accepts a document: read the rest of the sentence for another cue.
            by = _BY_HOLDER.match(sentence[end:])
            if not by:
                rest = consent_of(sentence[end:])
                return Consent(rest.cue, rest.holder_words, rest.written, rest.prior, _over(sentence)) if rest else None
            holder, end = _clean(by.group("holder")), end + by.end()
        if _NARRATIVE.match(sentence[end:]):
            return None
        cue = " ".join(sentence[m.start():end].split())
        low = cue.lower()
        written = bool(re.search(r"\b(?:written|in\s+writing|signed)\b", low))
        prior = bool(re.search(r"\b(?:prior|advance|first|previously|before)\b", low))
        return Consent(cue, holder, written, prior, _over(sentence))
    return None


def release_of(sentence: str) -> Release | None:
    """The first ``RELEASE_RULES`` row that matches the sentence, or None when it releases nothing."""
    for rx in _RELEASE_COMPILED:
        m = rx.search(sentence)
        if not m:
            continue
        released = m.groupdict().get("released") or ""
        subject = _SUBJECT.search(sentence[: m.start()] + " " + m.group(0))
        releasor = _clean(subject.group("s")) if subject else ""
        obj = m.group("obj").lower()
        over = next((name for name, cue in _RELEASE_OVER if re.search(cue, obj)), "")
        return Release(" ".join(m.group(0).split()), releasor, _clean(released), over)
    return None


def _sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT.split(" ".join(text.split())) if s]


def find_consents(text: str) -> tuple[Consent, ...]:
    """Each sentence's consent, in order; a sentence with none is left out."""
    return tuple(c for s in _sentences(text) if (c := consent_of(s)) is not None)


def find_releases(text: str) -> tuple[Release, ...]:
    """Each sentence's release, in order; a sentence with none is left out."""
    return tuple(r for s in _sentences(text) if (r := release_of(s)) is not None)


__all__ = [
    "CONSENT_RULES",
    "Consent",
    "OBJECT_WORDS",
    "OVER_RULES",
    "RELEASE_RULES",
    "Release",
    "consent_of",
    "find_consents",
    "find_releases",
    "release_of",
]
