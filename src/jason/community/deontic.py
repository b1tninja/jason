"""What a governing document requires, forbids, and allows: its duties, prohibitions, permissions, rights, and conditions,
read from the words, each with who bears it, what sets it off, and when it is due.

A declaration, bylaws, election rules, or an owner's manual states its norms in a small set of drafting forms: "shall"
and "must" for a duty, "shall not", "may not", and "No Owner shall" for a prohibition, "may" and "shall have the power
to" for a discretionary power, "shall have the right to" and "is entitled to" for a right. The same words also state
things that are not norms at all, and those are the traps this grammar is written around:

- a definition: "'Member' shall mean an Owner", "shall be deemed", "shall be conclusively presumed";
- a statement of status: "shall be a Class A Member", "shall be appurtenant to", "Membership shall pass automatically";
- a power, not a duty: "The Board may", "shall have the power to", "shall have the absolute discretion to";
- a "may" or "shall" inside a relative or conditional clause: "as the Board may establish", "which may become a
  nuisance", "Unless the Board shall designate otherwise";
- a duty stated in the passive with its bearer left out: "Notice shall be given", or with the recipient as the subject:
  "Members shall be given notice" (the Members receive it; they do not give it);
- a negative scoped over a list, and a lead-in whose list items carry no modal of their own ("The Inspector shall:" then
  "Deliver the ballots ..."): each item inherits the lead-in's kind and bearer.

``read_passage`` reads one section's own words; ``read_outline`` reads a whole outline, carrying a lead-in into the
sections under it. Each ``DocumentDuty`` quotes the sentence it came from, names its marker, and records the bearer, the
trigger, the deadline or recurrence, and the conditions and exceptions as the words give them. It is a reading for a
person to review (``ReviewStatus``), never a rule row: ``jason duties --documents KEY`` lists them, and the measured
precision of each strategy is in docs/document-duties.md.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any, Iterable


class DutyKind(Enum):
    DUTY = "duty"                    # someone must act: shall, must, is required to, is responsible for
    PROHIBITION = "prohibition"      # someone must not act: shall not, may not, No ... shall, is prohibited
    PERMISSION = "permission"        # someone may act (a power or a privilege, not a duty): may, shall have the power to
    RIGHT = "right"                  # someone holds a right others must respect: shall have the right to, is entitled to
    CONDITION = "condition"          # an effect that turns on an event or requirement: shall be subject to, shall be effective only
    DEFINITION = "definition"        # a definition or a statement of status: no one must act


NORMS = (DutyKind.DUTY, DutyKind.PROHIBITION, DutyKind.PERMISSION, DutyKind.RIGHT, DutyKind.CONDITION)


class Bearer(Enum):
    ASSOCIATION = "association"
    BOARD = "board"                  # the board, or a director
    OFFICER = "officer"              # president, secretary, treasurer
    COMMITTEE = "committee"
    INSPECTOR = "inspector"          # the inspector of elections
    MANAGER = "manager"              # the managing agent or the association's designated agent
    OWNER = "owner"
    MEMBER = "member"
    OCCUPANT = "occupant"            # resident, tenant, lessee, guest
    CANDIDATE = "candidate"
    DECLARANT = "declarant"
    MORTGAGEE = "mortgagee"
    PERSON = "person"                # any person
    OTHER = "other"                  # a court, a public agency
    UNSTATED = "unstated"            # the words leave it out (a passive duty)


class ReviewStatus(Enum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"          # a person read the words and agrees
    CORRECTED = "corrected"          # a person changed the kind, bearer, or timing (the correction is kept beside the reading)
    REJECTED = "rejected"            # not a norm, or not this one


class DeadlineRelation(Enum):
    WITHIN = "within"                # within 30 days after the meeting; not later than 120 days after
    BEFORE = "before"                # at least 10 days before the hearing
    BETWEEN = "between"              # not less than 30 nor more than 90 days before
    BY = "by"                        # on the first day of each month; by a date
    PERIOD = "for a period"          # for a period of one year after; for the current and two prior fiscal years


@dataclass(frozen=True)
class Deadline:
    text: str                        # the words: "within thirty (30) days after receipt of such application"
    relation: DeadlineRelation
    amount: int = 0                  # 30
    unit: str = ""                   # "days", "business days", "months", "years", "hours"
    event: str = ""                  # "receipt of such application"


@dataclass(frozen=True)
class DocumentDuty:
    """One norm a document states, as the grammar or a model read it from the words.

    ``start`` and ``end`` are offsets of ``quote`` (the sentence or clause) in the outline's text; ``marker`` is the
    drafting form that made it a norm ("shall", "may not", "No ... shall", "is responsible for", or "lead-in" for a list
    item that inherits its parent's). ``set_by`` is the instrument that last set the section's words, when the document
    is kept as amended (``jason.community.living``); empty for the original text.
    """

    source: str                      # the outline key ("bylaws")
    section: str                     # the section's number, or its title when it has none
    start: int
    end: int
    quote: str
    kind: DutyKind
    bearer: Bearer
    marker: str
    marker_at: int = 0               # the marker's offset in the outline's text
    bearer_words: str = ""           # the words that named the bearer ("the Board of Directors")
    action: str = ""                 # what is to be done, as written after the marker
    trigger: str = ""                # "upon", "if", "after", "in the event" ...: what sets it off
    deadline: Deadline | None = None
    recurrence: str = ""             # the words: "annually", "at least once every three years"
    recurrence_months: int = 0       # 12, 36, 3, 1; 0 for none
    conditions: tuple[str, ...] = ()  # "unless ...", "except ...", "provided that ...", "without the prior approval of ..."
    discretionary: bool = False      # "in its sole discretion", "as it deems prudent"
    passive: bool = False            # stated in the passive: the bearer is the agent named, or implied
    inherited: bool = False          # a list item that takes its kind and bearer from the lead-in above it
    notice: bool = False             # a duty or power to give notice, deliver, mail, post, or distribute
    method: str = "grammar"          # "grammar", "model", or "hybrid"
    set_by: str = ""
    review: ReviewStatus = ReviewStatus.UNREVIEWED
    note: str = ""                   # the reviewer's note, or the model's caveat

    @property
    def id(self) -> str:
        """Stable across rereads while the words, the marker, and the kind stay the same."""
        words = " ".join(self.quote.split()).lower()
        digest = hashlib.sha1(f"{self.source}|{self.section}|{words}|{self.marker}|{self.kind.value}|{self.action[:60].lower()}"
                              .encode("utf-8")).hexdigest()[:10]
        return f"{self.source}#{self.section}:{digest}"

    @property
    def timed(self) -> bool:
        return self.deadline is not None or bool(self.recurrence_months)

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["kind"] = self.kind.value
        raw["bearer"] = self.bearer.value
        raw["review"] = self.review.value
        raw["conditions"] = list(self.conditions)
        if self.deadline is not None:
            raw["deadline"] = {**asdict(self.deadline), "relation": self.deadline.relation.value}
        raw["id"] = self.id
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> DocumentDuty:
        d = raw.get("deadline")
        deadline = Deadline(**{**d, "relation": DeadlineRelation(d["relation"])}) if d else None
        names = {f for f in cls.__dataclass_fields__}
        data = {k: v for k, v in raw.items() if k in names}
        return cls(**{**data, "kind": DutyKind(raw["kind"]), "bearer": Bearer(raw["bearer"]),
                      "review": ReviewStatus(raw.get("review", "unreviewed")), "conditions": tuple(raw.get("conditions") or ()),
                      "deadline": deadline})


# ---------------------------------------------------------------------------------------------------------------------
# Sentences


_ABBREVIATIONS = {"sec", "secs", "no", "nos", "inc", "corp", "cal", "civ", "gov", "bus", "prof", "rev", "stat", "co", "ltd",
                  "st", "ave", "e.g", "i.e", "etc", "vs", "u.s", "mr", "mrs", "ms", "dr", "jr", "seq", "art", "ch", "para",
                  "approx", "et", "cf", "p", "pp", "subd", "para", "ord", "res", "dept", "assn", "assoc"}
_BOUNDARY = re.compile(r"[.!?][\"'”’)]*\s+(?=[\"'“‘(]?[A-Z0-9(])")


def sentences(text: str) -> list[tuple[int, int]]:
    """The spans of ``text``'s sentences: split at a line break and after a full stop that ends a sentence (not one
    that ends an abbreviation such as "Sec." or "Cal.", or an initial). Blank spans are dropped."""
    spans: list[tuple[int, int]] = []
    at = 0
    for line in re.finditer(r"[^\n]+", text):
        ls, le = line.span()
        start = ls
        for m in _BOUNDARY.finditer(text, ls, le):
            word = re.search(r"([A-Za-z][A-Za-z.]*)$", text[start:m.start()])
            token = (word.group(1).lower().rstrip(".") if word else "")
            if token in _ABBREVIATIONS or (word and len(word.group(1)) == 1):
                continue
            spans.append((start, m.start() + 1))
            start = m.end()
        spans.append((start, le))
        at = le
    del at
    out = []
    for s, e in spans:
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e > s:
            out.append((s, e))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Bearers

_BEARER_PATTERNS: tuple[tuple[Bearer, str], ...] = (
    (Bearer.INSPECTOR, r"inspectors?\s+of\s+elections?|(?<!building )(?<!home )inspectors?(?!\s+of\s+the\s+unit)"),
    (Bearer.COMMITTEE, r"(?:architectural\s+(?:review\s+)?|design\s+review\s+|nominating\s+|election\s+|landscape\s+|"
                       r"defect\s+|review\s+)?committees?(?:\s+members?)?|\bARC\b"),
    (Bearer.BOARD, r"board(?:\s+of\s+directors)?|directors?"),
    (Bearer.OFFICER, r"vice[- ]president|president|secretary|treasurer|chief\s+financial\s+officer|officers?"),
    (Bearer.MANAGER, r"managing\s+agent|management\s+company|manager|management|(?:its\s+|designated\s+)agent"),
    (Bearer.ASSOCIATION, r"association|HOA"),
    (Bearer.DECLARANT, r"declarant|developer|subdivider"),
    (Bearer.MORTGAGEE, r"mortgagees?|first\s+mortgagees?|lenders?"),
    (Bearer.CANDIDATE, r"candidates?|nominees?"),
    (Bearer.OCCUPANT, r"residents?|tenants?|lessees?|renters?|occupants?|guests?|invitees?|household\s+members?|"
                      r"contract\s+purchasers?"),
    (Bearer.OWNER, r"(?:unit\s+|condominium\s+)?owners?|homeowners?"),
    (Bearer.MEMBER, r"members?(?:hip)?(?=\b)"),
    (Bearer.OTHER, r"court|city|county|arbitrator|mediator|public\s+agency"),
    (Bearer.PERSON, r"persons?|anyone|no\s+one|any\s+party"),
)
_BEARER_RE = [(b, re.compile(rf"\b(?:{p})\b", re.I)) for b, p in _BEARER_PATTERNS]
_PRONOUN = re.compile(r"^\W*(?:it|they|he|she|he\s+or\s+she|such\s+\w+)\W*$", re.I)


def find_bearer(words: str) -> tuple[Bearer, str]:
    """The first party ``words`` name (the earliest match; the longest at one place), else UNSTATED."""
    best: tuple[int, int, Bearer, str] | None = None
    for bearer, rx in _BEARER_RE:
        for m in rx.finditer(words):
            if bearer is Bearer.MEMBER and m.group(0).lower().endswith("hip"):
                continue                           # "Membership" is a status, not a party
            key = (m.start(), -(m.end() - m.start()))
            if best is None or key < (best[0], best[1]):
                best = (key[0], key[1], bearer, m.group(0))
            break
    return (best[2], best[3]) if best else (Bearer.UNSTATED, "")


# ---------------------------------------------------------------------------------------------------------------------
# Markers

_MODAL = re.compile(r"\b(shall|must|may|can|cannot|will(?=\s+be\s+required))\b", re.I)
_PHRASES: tuple[tuple[str, DutyKind], ...] = (
    (r"it\s+is\s+the\s+(?:duty|responsibility|obligation)\s+of", DutyKind.DUTY),
    (r"(?:is|are)\s+(?:hereby\s+)?(?:required|obligated)\s+to", DutyKind.DUTY),
    (r"(?:is|are)\s+(?:solely\s+)?responsible\s+(?:for|to)", DutyKind.DUTY),
    (r"(?:agrees?|covenants?)\s+to", DutyKind.DUTY),
    (r"(?:is|are)\s+due\s+and\s+payable", DutyKind.DUTY),
    (r"(?:is|are)\s+(?:strictly\s+)?prohibited|prohibited\s+from|(?:is|are)\s+not\s+(?:permitted|allowed)", DutyKind.PROHIBITION),
    (r"(?:is|are)\s+(?:hereby\s+)?(?:permitted|allowed|authorized\s+to)", DutyKind.PERMISSION),
    (r"(?:is|are)\s+entitled\s+to|ha(?:s|ve)\s+the\s+right\s+to|it\s+is\s+the\s+right\s+of", DutyKind.RIGHT),
    (r"\bright\s+of\s+(?:the|each|any|an?)\s+(?:[A-Z][\w-]*\s+){0,3}?[A-Z][\w-]*\s+to\b", DutyKind.RIGHT),
    (r"\b(?:the\s+)?(?:power\s+and\s+authority|authority\s+and\s+power|power|authority)\s+to\b", DutyKind.PERMISSION),
)
_PHRASE_RE = [(re.compile(p, re.I), k) for p, k in _PHRASES]

# Words after "shall be" that state a status or a definition rather than an act.
_STATUS_AFTER_BE = {"a", "an", "the", "one", "each", "any", "no", "such", "his", "her", "its", "their", "as", "appurtenant",
                    "located", "limited", "composed", "comprised", "vested", "known", "independent", "severable", "equal",
                    "applicable", "construed", "interpreted", "deemed", "considered", "conclusively", "presumed",
                    "entitled", "eligible", "part", "inclusive", "in", "on", "at", "for", "from", "of", "within", "under",
                    "exempt"}
_BE_DUTY_WORDS = {"in writing", "in the custody", "in compliance", "in good standing"}
_CONDITION_AFTER_BE = re.compile(r"^(?:effective|valid|binding|void|voidable|null|enforceable|in\s+effect|subject\s+to|"
                                 r"delinquent|in\s+default)\b", re.I)
_DUTY_AFTER_BE = re.compile(r"^(?:responsible|liable|obligated|required|the\s+(?:duty|responsibility|obligation)\s+of|"
                            r"due\s+and\s+payable|current)\b", re.I)
_DEFINITION_START = re.compile(r"^(?:mean|means|refer\s+to|refers\s+to|have\s+the\s+(?:same\s+)?meanings?|be\s+deemed|"
                               r"be\s+conclusively|be\s+construed|be\s+interpreted|be\s+known\s+as|be\s+defined)\b", re.I)
_STATE_VERBS = {"run", "pass", "continue", "remain", "apply", "govern", "control", "prevail", "terminate", "expire",
                "constitute", "inure", "bind", "survive", "cease", "commence", "begin", "exist", "occur", "extend", "become",
                "invalidate", "affect", "impair", "limit", "prejudice", "operate", "preclude", "supersede", "take",
                "automatically", "consist", "be"}
_IRREGULAR_PARTICIPLES = {"paid", "given", "held", "kept", "made", "sent", "done", "set", "shown", "taken", "borne", "laid",
                          "built", "brought", "sold", "put", "read", "met", "run", "won", "drawn", "chosen", "written",
                          "spent", "found", "left", "cut", "bound", "struck", "worn", "seen", "known", "begun", "thrown"}
_POSSIBILITY = {"exposed", "affected", "impacted", "subjected", "different", "inconvenienced"}
_RECIPIENT_PARTICIPLES = {"given", "provided", "sent", "mailed", "delivered", "furnished", "notified", "offered", "afforded",
                          "reimbursed", "paid", "compensated", "charged", "fined", "assessed", "served", "granted", "allowed",
                          "permitted", "denied", "told", "informed", "invited", "removed", "elected", "appointed",
                          "suspended", "disciplined", "reelected", "nominated"}
# Parties who, as the subject of a passive with one of those participles, receive the act rather than perform it.
_PERSON_BEARERS = {Bearer.OWNER, Bearer.MEMBER, Bearer.OCCUPANT, Bearer.CANDIDATE, Bearer.PERSON, Bearer.COMMITTEE,
                   Bearer.MORTGAGEE, Bearer.BOARD, Bearer.OFFICER, Bearer.INSPECTOR}
_DOCUMENT_NOUNS = re.compile(r"\b(?:notice|statement|report|ballot|agreement|application|policy|letter|budget|study|"
                             r"minutes|request|form|disclosure|sign|program|plan|summary|decision|contract|lease|"
                             r"envelope|list|agenda|packet)s?\b", re.I)
_SUBORDINATE = re.compile(r"\b(?:unless|if|until|when|whenever|whether|except\s+(?:as|that|when|where))\b[^,;:]*$", re.I)
_RELATIVE = re.compile(r"(?:\bas\s+(?:[\w'’-]+\s+){0,6}|\b(?:which|that|who|whom|whose|where|wherein|whatever|whichever|than)\s+(?:[\w'’-]+\s+){0,6})$", re.I)
_NEG_PIECE = re.compile(r"\s*(?:no|neither)\s+(?!later|less|more|fewer|sooner|longer|event\b)\w+", re.I)
_NEG_SUBJECT = re.compile(r"^\W*(?:\([a-z0-9]{1,4}\)\s*)?(?:no|neither|nothing|in\s+no\s+event|under\s+no\s+circumstances?)\b", re.I)
_LEADIN_CONDITIONS = re.compile(r"following\s+(?:conditions|events|criteria|circumstances)|if\s+all\s+of\s+the\s+following|"
                                r"first\s+to\s+occur\s+of\s+the\s+following|any\s+of\s+the\s+following\s+(?:occurs|apply)", re.I)
_DISCRETION = re.compile(r"\b(?:in|at)\s+(?:its|their|his|her|the\s+board'?s)\s+(?:sole\s+|absolute\s+|complete\s+|reasonable\s+|"
                         r"good\s+faith\s+)*discretion\b|\babsolute\s+discretion\b|\bas\s+(?:it|they|the\s+board)\s+(?:may\s+)?"
                         r"deems?\b|\bdeems?\s+(?:necessary|appropriate|prudent|advisable)\b", re.I)
_NOTICE = re.compile(r"\bnotic(?:e|es|ed)\b|\bnotif(?:y|ies|ied|ication)\b|\bmail(?:ed|ing)?\b|\bdeliver(?:ed|y)?\b|"
                     r"\bdistribut(?:e|ed|ion)\b|\bpost(?:ed|ing)?\b(?!\s+office)|\bsend\b|\bsent\b|\btransmit(?:ted)?\b|"
                     r"\bprovide\s+(?:a\s+copy|copies|written)\b|\bdisclos(?:e|ure)\b|\bdisplay(?:ed)?\b", re.I)


@dataclass(frozen=True)
class _Marker:
    start: int
    end: int
    words: str
    kind: DutyKind | None            # None: classify from the words after a modal
    modal: str = ""                  # "shall", "must", "may", "can", "cannot", "will"


def _quoted(seg: str) -> list[tuple[int, int]]:
    """Spans inside quotation marks: a modal there is words the document prescribes ("The rules ... may be found
    here"), not a norm of its own."""
    spans = [(m.start(), m.end()) for m in re.finditer(r"“[^”]{2,}”", seg)]
    straight = [m.start() for m in re.finditer(r"\"", seg)]          # paired in order: the first opens, the second closes
    spans += [(a, b) for a, b in zip(straight[0::2], straight[1::2]) if b - a > 2]
    return spans


def _markers(seg: str) -> list[_Marker]:
    quoted = _quoted(seg)
    found: list[_Marker] = [_Marker(m.start(), m.end(), m.group(0), None, m.group(1).lower()) for m in _MODAL.finditer(seg)
                            if not any(a < m.start() < b for a, b in quoted)]
    for rx, kind in _PHRASE_RE:
        for m in rx.finditer(seg):
            # "shall have the power to", "shall be responsible for": the modal before it is the marker.
            prior = seg[max(0, m.start() - 40):m.start()]
            if re.search(r"\b(?:shall|must|may|will|can)(?:\s+not)?(?:\s+(?:also|have|be|each|hereby|then|further))*"
                         r"(?:\s+(?:the|a|an|full|sole|such|all|exclusive))?\s*$", prior, re.I):
                continue
            if any(f.start <= m.start() < f.end or m.start() <= f.start < m.end() for f in found):
                continue
            found.append(_Marker(m.start(), m.end(), " ".join(m.group(0).split()), kind))
    return sorted(found, key=lambda m: m.start)


def _first_word(text: str) -> str:
    m = re.match(r"\s*([\w'’-]+)", text)
    return m.group(1).lower() if m else ""


def _participle(word: str) -> bool:
    w = word.lower()
    return w in _IRREGULAR_PARTICIPLES or (len(w) > 3 and (w.endswith("ed") or w.endswith("en"))) and w not in {"open", "even", "often", "garden", "kitchen", "between", "seven", "eleven", "children"}


def _classify(seg: str, mk: _Marker, before: str) -> tuple[DutyKind | None, bool, str]:
    """(kind or None to skip, passive, the words after the marker)."""
    after = seg[mk.end:]
    a = after.strip()
    al = a.lower()
    head = seg[:mk.start].split(";")[0]
    sentence_negative = bool(_NEG_SUBJECT.search(head)) or any(_NEG_PIECE.match(p) for p in head.split(",")[1:])
    if mk.modal == "may" and re.match(r"\s*\d", seg[mk.end:]) and seg[mk.start].isupper():
        return None, False, seg[mk.end:]                       # "May 18, 2027": the month
    if seg[mk.start:mk.end].isupper() and len(re.findall(r"[a-z]", seg)) < len(re.findall(r"[A-Z]", seg)) // 4:
        return None, False, seg[mk.end:]                       # a heading in capitals ("RESOLUTION ... MAY"), not a sentence
    if mk.kind is not None:
        words = mk.words.lower()
        if mk.kind is DutyKind.DUTY and (re.search(r"\b(?:which|that|whom)\s+(?:[\w'’-]+\s+){0,3}$", before, re.I)
                                         or re.search(r"\bwhose\b[^.;:]{0,90}$", before, re.I)):
            return None, False, a                              # "which the Association is obligated to repair": a description
        if mk.kind is DutyKind.DUTY and re.match(r"agrees?\s+to", words) and re.match(r"(?:receive|accept|be\s+bound)\b", al):
            return DutyKind.CONDITION, False, a
        if mk.kind is DutyKind.DUTY and re.search(r"\bnot\s*$", before, re.I):
            return DutyKind.DEFINITION, False, a              # "is not responsible for": a disclaimer
        return mk.kind, False, a
    modal = mk.modal
    if modal == "will":
        return DutyKind.DUTY, True, a                          # "will be required"
    # A modal inside a relative or conditional clause is part of what it modifies, not a norm of its own.
    if modal in ("may", "can") and (_RELATIVE.search(before) or re.match(r"or\s+may\s+not\b", al)):
        return None, False, a
    if modal in ("may", "can") and re.search(r"\b(?:that|whether)\s+(?:[\w'’-]+\s+){0,10}$", before, re.I):
        return None, False, a                                  # "stating that the owner ... may address the Board"
    if modal == "may" and re.search(r"\b(?:any|such|the)\s+\w+\s+(?:he\s+or\s+she|he|she|they|it|you)\s+$", before, re.I):
        return None, False, a                                  # "any service he or she may render"
    if re.search(r"\bmay\s+or\s*$", before, re.I):
        return None, False, a
    if modal == "shall" and re.search(r"\bas\s+(?:[\w'’-]+\s+){0,6}$", before, re.I):
        return None, False, a
    if sentence_negative and re.search(r"\b(?:which|that|who)\s+$", before, re.I):
        return None, False, a                                  # "No ... activity ..., which shall interfere": the prohibition's object
    if _SUBORDINATE.search(before) and not re.search(r",\s*$", before):
        return None, False, a
    negative = modal == "cannot" or bool(re.match(r"not\b", al))
    if negative and modal != "cannot":
        a = a[3:].strip()
        al = a.lower()
    no_subject = (bool(_NEG_SUBJECT.search(before)) or bool(_NEG_SUBJECT.search(before.split(":")[-1]))
                  or any(_NEG_PIECE.match(piece) for piece in before.split(",")[1:])
                  or bool(re.search(r"\bnor\s*$", before, re.I)))
    if modal == "may" and re.match(r"be\s+required\b", al) and not negative:
        return DutyKind.PERMISSION, True, a                    # "Payment may be required": the power to require it
    # Scope and terms, not acts: "shall not include", "shall only apply to", "shall hold office for one year".
    bare = re.sub(r"^(?:only|also|otherwise|thereafter|then|further|solely)\s+", "", al)
    if re.match(r"(?:include|includes|mean|apply|applies|relate|concern|cover|extend)\b", bare) and (negative or bare != al):
        return DutyKind.DEFINITION, False, a
    if re.match(r"hold\s+office\b|serve\s+(?:for\s+)?a\s+term\b", bare):
        return DutyKind.DEFINITION, False, a
    if not negative and re.match(r"be\s+(?:strictly\s+)?prohibited\b", bare):
        return DutyKind.PROHIBITION, True, a                   # "Proxies shall otherwise be prohibited"
    if not negative and re.match(r"be\s+(?:hereby\s+)?(?:authorized|empowered|permitted|allowed)\b", bare):
        return DutyKind.PERMISSION, False, a                   # "The Board shall be authorized to grant variances"
    if modal == "may" and _first_word(bare) in {"concern", "include", "cover", "address", "relate"}:
        return None, False, a                                  # "The Rules may concern ...": scope, not a power
    if bare != al and not negative:
        a, al = a[len(al) - len(bare):], bare
    if modal == "can" and not negative:
        bearer, _ = find_bearer(before)
        return (DutyKind.PERMISSION if bearer is not Bearer.UNSTATED else None), False, a
    if re.match(r"^nothing\b", before.strip(), re.I):
        return DutyKind.DEFINITION, False, a
    if _DEFINITION_START.match(al):
        return DutyKind.DEFINITION, False, a
    if negative or (no_subject and modal in ("shall", "must", "may")):
        if re.match(r"be\s+(?:required|obligated|responsible|liable)\b", al):
            return DutyKind.DEFINITION, False, a
        if re.match(r"be\s+denied\b", al):
            return DutyKind.RIGHT, True, a
        if re.match(r"be\s+considered\s+(?:[\"'“‘]|to\s+be|as|a|an)\b", al) or re.match(r"be\s+considered\s+[\"“]", al):
            return DutyKind.DEFINITION, False, a
        if _CONDITION_AFTER_BE.match(al[3:] if al.startswith("be ") else "") or re.match(r"(?:be\s+)?(?:effective|valid|binding)\b", al):
            return DutyKind.CONDITION, False, a
        if _first_word(al) in _STATE_VERBS - {"be"} and find_bearer(before)[0] is Bearer.UNSTATED:
            return DutyKind.DEFINITION, False, a
        passive = al.startswith("be ") and _participle(_first_word(al[3:]))
        return DutyKind.PROHIBITION, passive, a
    # Positive forms.
    if re.match(r"have\s+(?:the\s+|an?\s+|full\s+|sole\s+|exclusive\s+)?(?:[\w-]+\s+){0,2}?(?:right|rights|easement|option|opportunity)\b", al):
        return DutyKind.RIGHT, False, a
    if re.match(r"have\s+(?:the\s+|such\s+|full\s+|all\s+|sole\s+)?(?:[\w-]+\s+){0,2}?(?:power|powers|authority|discretion)\b", al):
        return DutyKind.PERMISSION, False, a
    if re.match(r"have\s+no\b", al):
        return DutyKind.DEFINITION, False, a
    if re.match(r"have\s+(?:the\s+)?(?:duty|obligation|responsibility)\b", al):
        return DutyKind.DUTY, False, a
    if re.match(r"have\b", al):
        return DutyKind.DEFINITION, False, a                   # "shall have an undivided interest", "shall have one vote": status
    if re.match(r"be\s+(?:treated|regarded)\s+as\b", al):
        return DutyKind.DEFINITION, False, a
    if re.match(r"be\s+entitled\b", al):
        return DutyKind.RIGHT, False, a
    if re.match(r"(?:include|contain|consist)\b", al):
        if re.search(r"\b(?:which|that)\s+$", before, re.I):
            return DutyKind.DEFINITION, False, a              # "a program which shall include the following steps"
        return (DutyKind.DUTY if _DOCUMENT_NOUNS.search(before) else DutyKind.DEFINITION), False, a
    if al.startswith("be "):
        rest = al[3:].strip()
        if _CONDITION_AFTER_BE.match(rest) or rest.startswith("subject to"):
            return DutyKind.CONDITION, False, a
        if _DUTY_AFTER_BE.match(rest) or any(rest.startswith(w) for w in _BE_DUTY_WORDS):
            return DutyKind.DUTY, False, a
        first = _first_word(rest)
        if re.match(r"^(?:permanently|promptly|immediately|automatically|also|further|duly|first|timely|jointly|"
                     r"severally|only|solely|properly|reasonably|separately|equally)\s+", rest):
            first = _first_word(re.sub(r"^\w+\s+", "", rest))
        if first in _POSSIBILITY:
            return None, False, a
        if first in _STATUS_AFTER_BE or (rest[:1].isupper() if rest else False):
            return DutyKind.DEFINITION, False, a
        if _participle(first):
            return (DutyKind.PERMISSION if modal == "may" else DutyKind.DUTY), True, a
        if a[3:4].isupper():
            return DutyKind.DEFINITION, False, a
        if modal == "may":
            return None, False, a                              # "may be obtainable", "may be necessary": a possibility
        return (DutyKind.PERMISSION if modal == "may" else DutyKind.DUTY), False, a
    if al.startswith("become effective") or al.startswith("take effect"):
        return DutyKind.CONDITION, False, a
    first = _first_word(al)
    if first in _STATE_VERBS and (modal != "may"):
        return DutyKind.DEFINITION, False, a
    if modal == "may" and first in {"occur", "result", "vary", "exist", "arise", "happen", "differ", "change", "increase",
                                    "decrease", "affect", "cause", "become", "be"}:
        return None, False, a                                  # "Foreclosure may occur": a possibility, not a power
    if modal == "may":
        return DutyKind.PERMISSION, False, a
    return DutyKind.DUTY, False, a


# ---------------------------------------------------------------------------------------------------------------------
# Timing, triggers, conditions

_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                 "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
                 "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "forty-five": 45, "fifty": 50,
                 "sixty": 60, "seventy": 70, "seventy-five": 75, "eighty": 80, "ninety": 90, "one hundred twenty": 120,
                 "one hundred and twenty": 120, "one hundred eighty": 180, "twenty-one": 21, "forty-eight": 48,
                 "seventy-two": 72, "twenty-four": 24}
_NUM = (r"(?P<num>\d+|" + "|".join(sorted((re.escape(k) for k in _NUMBER_WORDS), key=len, reverse=True)) + r")"
        r"(?:\s*\(\s*(?P<digits>\d+)\s*\))?")
_UNIT = r"(?P<unit>(?:calendar\s+|business\s+|banking\s+|fiscal\s+)?(?:days?|months?|years?|hours?|weeks?))(?:['’]s?)?"
_EVENT = r"(?P<event>[^,;.:]{3,120})"
_DEADLINES: tuple[tuple[DeadlineRelation, re.Pattern[str]], ...] = (
    (DeadlineRelation.BETWEEN, re.compile(rf"\b(?:not\s+less\s+than|no\s+less\s+than|between)\s+{_NUM}\s+(?:days?\s+)?(?:nor\s+more\s+than|and\s+not\s+more\s+than|and|to)\s+"
                                         rf"(?:\d+|\w+)(?:\s*\(\d+\))?\s+{_UNIT}\s+(?:before|prior\s+to|after)\s+{_EVENT}", re.I)),
    (DeadlineRelation.BEFORE, re.compile(rf"\b(?:at\s+least|not\s+less\s+than|no\s+less\s+than|no\s+fewer\s+than|a\s+minimum\s+of)\s+{_NUM}\s+{_UNIT}"
                                         rf"(?:\s+(?:prior|advance|written|prior\s+written))?(?:\s+notice)?\s+(?:before|prior\s+to|in\s+advance\s+of|preceding)\s+{_EVENT}", re.I)),
    (DeadlineRelation.BEFORE, re.compile(rf"\b{_NUM}\s+{_UNIT}\s*(?:prior\s+)?(?:written\s+)?notice\b", re.I)),
    (DeadlineRelation.WITHIN, re.compile(rf"\b(?:within|not\s+later\s+than|no\s+later\s+than|not\s+more\s+than|no\s+more\s+than)\s+{_NUM}\s+{_UNIT}"
                                         rf"(?:\s+(?:after|of|following|from|before|prior\s+to|after\s+the\s+date\s+of)\s+{_EVENT})?", re.I)),
    (DeadlineRelation.WITHIN, re.compile(rf"\b{_NUM}\s+{_UNIT}\s+(?:after|following|from)\s+{_EVENT}", re.I)),
    (DeadlineRelation.BEFORE, re.compile(rf"\b{_NUM}\s+{_UNIT}\s+(?:before|prior\s+to)\s+{_EVENT}", re.I)),
    (DeadlineRelation.PERIOD, re.compile(rf"\bfor\s+(?:a\s+period\s+of\s+)?{_NUM}\s+{_UNIT}(?:\s+(?:after|following|from)\s+{_EVENT})?", re.I)),
    (DeadlineRelation.PERIOD, re.compile(rf"\bfor\s+the\s+current\s+(?:fiscal\s+|calendar\s+)?year\s+and\s+(?:for\s+)?(?:the\s+|each\s+of\s+the\s+)?"
                                         rf"(?:prior|previous|preceding)\s+{_NUM}\s+{_UNIT}", re.I)),
    (DeadlineRelation.BY, re.compile(r"\b(?:on|by|before)\s+the\s+(?P<event>(?:first|last|\d+(?:st|nd|rd|th)|fifteenth|tenth)\s+day\s+of\s+[^,;.]{3,60})", re.I)),
)
_RECURRENCES: tuple[tuple[int, re.Pattern[str]], ...] = (
    (0, re.compile(r"\b(?:at\s+least\s+)?(?:once\s+)?every\s+(?P<n>\d+|two|three|four|five|six|seven|eight|nine|ten|twelve)\s*(?:\(\d+\)\s*)?(?P<u>years?|months?)\b", re.I)),
    (3, re.compile(r"\bquarterly\b|\beach\s+(?:calendar\s+|fiscal\s+)?quarter\b|\bevery\s+quarter\b", re.I)),
    (6, re.compile(r"\bsemi-?annual(?:ly)?\b|\btwice\s+(?:a|each|per)\s+year\b|\bbi-?annually\b", re.I)),
    (12, re.compile(r"\bannually\b|\bon\s+an\s+annual\s+basis\b|\beach\s+(?:calendar\s+|fiscal\s+)?year\b|\bevery\s+year\b|"
                    r"\bonce\s+(?:a|each|per)\s+year\b|\byearly\b|\bper\s+year\b|\bannual\s+(?:report|budget|review|meeting|"
                    r"statement|inspection|notice|election|audit|policy|disclosure|financial|registration|update|summary)", re.I)),
    (1, re.compile(r"\bmonthly\b|\beach\s+month\b|\bevery\s+month\b|\bper\s+month\b|\bfirst\s+day\s+of\s+each\s+month\b", re.I)),
    (24, re.compile(r"\bbiennial(?:ly)?\b", re.I)),
)
_TRIGGER = re.compile(r"\b(?P<word>upon|after|following|on\s+receipt\s+of|once(?=\s+(?:the|a|an|such|all|any|it|he|she|they)\b)|"
                      r"whenever|when|if|in\s+the\s+event\s+(?:that|of)|prior\s+to|before)\b\s+(?P<what>[^,;:]{3,140})", re.I)
_CONDITION = re.compile(r"\b(?P<word>unless|except(?:\s+as|\s+that|\s+for|\s+when|\s+where)?|provided(?:,)?\s+(?:however,?\s+)?that|"
                        r"subject\s+to|without\s+(?:the\s+)?(?:prior\s+)?(?:written\s+)?(?:consent|approval)\s+of|only\s+if|"
                        r"so\s+long\s+as|notwithstanding)\b(?P<what>[^;.]{0,140})", re.I)


def _number(m: re.Match[str]) -> int:
    if m.groupdict().get("digits"):
        return int(m.group("digits"))
    raw = (m.group("num") or "").lower()
    return int(raw) if raw.isdigit() else _NUMBER_WORDS.get(raw, 0)


def find_deadline(clause: str) -> Deadline | None:
    for relation, rx in _DEADLINES:
        m = rx.search(clause)
        if not m:
            continue
        groups = m.groupdict()
        unit = " ".join((groups.get("unit") or "").lower().split()).rstrip("'’s")
        if unit and not unit.endswith("s"):
            unit += "s"
        amount = _number(m) if groups.get("num") else 0
        return Deadline(" ".join(m.group(0).split()), relation, amount, unit, " ".join((groups.get("event") or "").split()))
    return None


def find_recurrence(clause: str) -> tuple[str, int]:
    for months, rx in _RECURRENCES:
        m = rx.search(clause)
        if not m:
            continue
        if months == 0:
            raw = m.group("n").lower()
            n = int(raw) if raw.isdigit() else _NUMBER_WORDS.get(raw, 0)
            months = n * (12 if m.group("u").lower().startswith("year") else 1)
            if not months:
                continue
        return " ".join(m.group(0).split()), months
    return "", 0


def find_trigger(clause: str, deadline: Deadline | None) -> str:
    for m in _TRIGGER.finditer(clause):
        text = " ".join(m.group(0).split()).rstrip(" .")
        if deadline and text.lower() in deadline.text.lower():
            continue
        if deadline and m.start() > 0 and re.search(r"\b(?:days?|months?|years?)\s*$", clause[:m.start()], re.I):
            continue                                   # "30 days after notice": the deadline's event, not a trigger
        return text
    return ""


def find_conditions(clause: str) -> tuple[str, ...]:
    return tuple(" ".join(m.group(0).split()) for m in _CONDITION.finditer(clause))


# ---------------------------------------------------------------------------------------------------------------------
# Reading a passage


@dataclass(frozen=True)
class LeadIn:
    """A sentence that opens a list ("The Inspector of Elections shall:"): its kind and bearer pass to items with no
    modal of their own."""

    kind: DutyKind
    bearer: Bearer
    bearer_words: str = ""
    marker: str = ""


def _subject(before: str) -> str:
    """The subject of a clause: after a leading subordinate clause ("If ..., the Board shall") the words after its last
    comma; else the words from the clause's start. A leading "and" or "but" is dropped ("..., and it must")."""
    pieces = before.split(",")
    subject = before
    if len(pieces) > 1 and re.search(r"[A-Za-z]{2,}", pieces[-1]):
        subject = pieces[-1]
    elif len(pieces) > 2:
        subject = pieces[0]          # "The Board, in its discretion, shall": the words before the parenthetical
    return re.sub(r"^\s*(?:and|but|or|then|also)\s+", "", subject, flags=re.I)


_PREPOSITIONAL = re.compile(r"\b(?:before|to|from|with|against|upon|for|on\s+behalf\s+of|by)\s+(?:the|an?|any|each|its|their)?\s*"
                            r"[\w'’-]+(?:\s+of\s+[\w'’-]+)?", re.I)
_PAYMENT_SUBJECT = re.compile(r"\b(?:assessments?|installments?|dues|charges?|fees?|fines?|penalt(?:y|ies)|sums?)\b", re.I)


def _agent(after: str) -> tuple[Bearer, str]:
    m = re.search(r"\bby\s+(?:the\s+|its\s+|an?\s+|any\s+)?([^,;.]{2,60})", after[:160], re.I)
    if not m:
        return Bearer.UNSTATED, ""
    bearer, words = find_bearer(m.group(1)[:40])
    return bearer, words


def _clause_end(seg: str, at: int) -> int:
    m = re.search(r"[;]", seg[at:])
    return at + m.start() if m else len(seg)


def _notice(kind: DutyKind, subject: str, action: str) -> bool:
    """A duty or power to give notice: the act's own verb phrase delivers or posts something, or the subject is a
    notice or ballot whose contents are set. "Without notice" is not one."""
    if kind not in (DutyKind.DUTY, DutyKind.PERMISSION, DutyKind.CONDITION):
        return False
    head = " ".join(action.split()[:12])
    head = re.sub(r"\bwithout\s+(?:further\s+|prior\s+|any\s+)?notice\b", "", head, flags=re.I)
    if _NOTICE.search(head) or re.search(r"\b(?:written|electronic)\s+communication\b", head, re.I):
        return True
    return bool(re.search(r"\b(?:notice|ballot|notification)s?\b", subject, re.I)) and \
        bool(re.match(r"(?:include|contain|state|specify|set\s+forth|(?:also\s+)?be\s+(?:given|delivered|sent|mailed|posted))\b",
                      action, re.I))


def _caption(sent: str, more: bool) -> bool:
    """A section's own caption line ("Transfer to Public Agency."), when more words follow it."""
    s = sent.strip()
    if not more or len(s) > 90 or _MODAL.search(s):
        return False
    words = re.findall(r"[A-Za-z][\w'’-]*", s)
    caps = sum(1 for w in words if w[0].isupper() or w.lower() in {"of", "and", "the", "to", "for", "in", "on", "a", "or", "by"})
    return bool(words) and caps == len(words)


def _title_line(text: str, s: int, e: int) -> bool:
    """The passage's first line is its heading ("Directors May Not be Delinquent."): every word capitalized but the
    small ones, a line of its own, and words follow it."""
    sent = text[s:e].strip()
    if not text[e:].strip() or (e < len(text) and text[e] != "\n") or len(sent) > 90:
        return False
    words = re.findall(r"[A-Za-z][\w'’-]*", sent)
    small = {"of", "and", "the", "to", "for", "in", "on", "a", "an", "or", "by", "be", "not", "with", "at", "is"}
    return bool(words) and all(w[0].isupper() or w.lower() in small for w in words) and \
        sum(1 for w in words if w[0].isupper()) >= max(1, len(words) // 2)


def _own_bearer(sent: str) -> tuple[Bearer, str]:
    """The bearer a list item names as its own subject ("The Association provides ..."), else UNSTATED."""
    m = re.match(r"\s*(?:the|each|every|any|all|an?)\s+((?:[\w'’-]+\s+){0,3}[\w'’-]+)", sent, re.I)
    return find_bearer(m.group(1)) if m else (Bearer.UNSTATED, "")


def read_passage(text: str, *, source: str = "", section: str = "", base: int = 0, lead: LeadIn | None = None,
                 lead_scope: bool = False) -> tuple[list[DocumentDuty], LeadIn | None]:
    """The norms in one section's own words, and the lead-in its last sentence opens for the sections under it.

    ``lead`` is the parent's lead-in; with ``lead_scope`` (the passage is a list item under it) the first sentence after
    the caption, when no sentence of the passage has a marker of its own, is an item of that kind and bearer. Within a
    passage, lines after a sentence ending in a colon ("the Association may:") are items of that sentence's kind until
    a line with a marker of its own. Offsets are ``base`` plus the offset in ``text``.
    """
    out: list[DocumentDuty] = []
    spans = sentences(text)
    opened: LeadIn | None = None
    inner: LeadIn | None = None                   # a lead-in opened inside this passage
    last_bearer: tuple[Bearer, str] = (Bearer.UNSTATED, "")

    def inherit(s: int, e: int, li: LeadIn) -> DocumentDuty:
        sent = text[s:e]
        bearer, words = _own_bearer(sent)
        if bearer is Bearer.UNSTATED:
            bearer, words = li.bearer, li.bearer_words
        deadline = find_deadline(sent)
        recurrence, months = find_recurrence(sent)
        return DocumentDuty(
            source=source, section=section, start=base + s, end=base + e, quote=sent, kind=li.kind, bearer=bearer,
            marker="lead-in", marker_at=base + s, bearer_words=words, action=" ".join(sent.split())[:240],
            trigger=find_trigger(sent, deadline), deadline=deadline, recurrence=recurrence, recurrence_months=months,
            conditions=find_conditions(sent), discretionary=bool(_DISCRETION.search(sent)), inherited=True,
            notice=_notice(li.kind, "", sent))

    for index, (s, e) in enumerate(spans):
        sent = text[s:e]
        if re.match(r"\W*whereas\b", sent, re.I):
            continue                                   # a recital gives reasons; the resolution's words follow "RESOLVED"
        found = [] if index == 0 and _title_line(text, s, e) else _markers(sent)
        norms: list[DocumentDuty] = []
        prev_marker = -1
        for k, mk in enumerate(found):
            before_all = sent[:mk.start]
            seg_start = sent.rfind(";", 0, mk.start) + 1
            before = sent[seg_start:mk.start]
            kind, passive, after = _classify(sent, mk, before)
            if kind is None:
                continue
            next_start = next((f.start for f in found[k + 1:] if f.start > mk.end), len(sent))
            clause_end = min(_clause_end(sent, mk.end), next_start)
            # The clause: from the sentence's start (the first norm) or the last comma or semicolon after the norm before.
            if prev_marker < 0:
                clause_start = seg_start
            else:
                ands = [prev_marker + m.end() - 1 for m in re.finditer(r"\band\b", sent[prev_marker:mk.start])]
                cut = max([sent.rfind(",", prev_marker, mk.start), sent.rfind(";", prev_marker, mk.start), *ands])
                clause_start = cut + 1 if cut >= 0 else prev_marker
            clause = sent[clause_start:max(clause_end, mk.end)]
            # Who: the subject, the agent of a passive, or the bearer of the clause before ("...; may sign all checks").
            subj = _subject(before)
            if mk.kind is DutyKind.RIGHT and mk.words.lower().startswith("right of"):
                bearer, words = find_bearer(mk.words)
            elif mk.kind is not None and re.match(r"it\s+is\s+the", mk.words, re.I):
                bearer, words = find_bearer(after[:60])
            elif passive:
                bearer, words = find_bearer(_PREPOSITIONAL.sub(" ", subj))
            else:
                bearer, words = find_bearer(subj)
            m_resp = re.match(r"(?:at\s+all\s+times\s+)?be\s+(?:the\s+(?:duty|responsibility|obligation)|in\s+the\s+custody)\s+of\s+"
                              r"([^,;.]{2,60})", after, re.I)
            if m_resp:
                bearer, words = find_bearer(m_resp.group(1))
            if passive and kind is not DutyKind.RIGHT:
                agent, agent_words = _agent(after)
                first = _first_word(after[3:]) if after.lower().startswith("be ") else ""
                if agent is not Bearer.UNSTATED:
                    bearer, words = agent, agent_words
                elif bearer in _PERSON_BEARERS and first in _RECIPIENT_PARTICIPLES:
                    bearer, words = Bearer.UNSTATED, ""      # "Members shall be given notice": the Members receive it
                elif bearer is Bearer.UNSTATED and first == "paid" and _PAYMENT_SUBJECT.search(subj):
                    bearer, words = Bearer.OWNER, ""         # assessments are paid by the owners
            if bearer is Bearer.UNSTATED and kind is DutyKind.DUTY and re.match(r"(?:be\s+)?due\s+and\s+payable", after, re.I) \
                    and _PAYMENT_SUBJECT.search(subj + " " + mk.words):
                bearer, words = Bearer.OWNER, ""
            if bearer is Bearer.UNSTATED and mk.kind is DutyKind.DUTY and "due and payable" in mk.words.lower():
                bearer, words = Bearer.OWNER, ""
            if bearer is Bearer.UNSTATED and (_PRONOUN.match(subj or "") or not re.search(r"[A-Za-z]", subj)):
                if norms:
                    bearer, words = norms[-1].bearer, norms[-1].bearer_words
                elif last_bearer[0] is not Bearer.UNSTATED and _PRONOUN.match(subj or ""):
                    bearer, words = last_bearer
                elif lead is not None and lead_scope:
                    bearer, words = lead.bearer, lead.bearer_words
            # Timing: the words after the marker first ("shall be paid in monthly installments"), then the clause's
            # preface ("Within thirty days after receipt, the Board shall"); a coordinated duty ("... annually and shall
            # consider and implement adjustments") shares the timing of the one before it.
            tail = sent[mk.end:max(clause_end, mk.end)]
            deadline = find_deadline(tail) or find_deadline(clause)
            recurrence, months = find_recurrence(tail)
            if not months:
                recurrence, months = find_recurrence(clause)
            if norms and re.search(r"\band\s*$", sent[max(prev_marker, 0):mk.start], re.I) and norms[-1].bearer is bearer:
                deadline = deadline or norms[-1].deadline
                if not months:
                    recurrence, months = norms[-1].recurrence, norms[-1].recurrence_months
            negated = bool(re.match(r"\s*not\b", sent[mk.end:], re.I))
            action = " ".join(after[:max(clause_end - mk.end, 0) or 200].split())[:240]
            item = DocumentDuty(
                source=source, section=section, start=base + s, end=base + e, quote=sent, kind=kind, bearer=bearer,
                marker=" ".join(mk.words.split()).lower() if mk.kind is not None else
                ("no ... " + mk.modal if kind is DutyKind.PROHIBITION and not negated and mk.modal != "cannot"
                 else mk.modal + (" not" if negated else "")),
                marker_at=base + s + mk.start, bearer_words=" ".join(words.split()),
                action=action, trigger=find_trigger(clause, deadline), deadline=deadline, recurrence=recurrence,
                recurrence_months=months, conditions=find_conditions(clause), discretionary=bool(_DISCRETION.search(clause)),
                passive=passive, notice=_notice(kind, subj, after),
            )
            del before_all
            norms.append(item)
            prev_marker = mk.end
            if bearer is not Bearer.UNSTATED:
                last_bearer = (bearer, words)
        if not norms and inner is not None and _is_list_item(sent):
            if not found:
                norms.append(inherit(s, e, inner))
        elif norms:
            inner = None
        out.extend(norms)
        # A sentence that ends with a colon, or breaks off unfinished, opens a list for what follows.
        ends_open = sent.rstrip().endswith(":") or (index == len(spans) - 1 and not re.search(r"[.!?\"'”)]\s*$", sent))
        own = [n for n in norms if not n.inherited]
        if ends_open:
            real = [n for n in own if n.kind is not DutyKind.DEFINITION] or own
            if real or found:
                opened = _lead_from(sent, real, last_bearer)
                inner = opened if not sent.rstrip().endswith(":") or index + 1 < len(spans) else None
                if not sent.rstrip().endswith(":") or index + 1 < len(spans):
                    inner = opened
            else:
                inner = None
                opened = None
        elif own:
            opened = None
    # A list item under a parent's lead-in: when no sentence here has a marker of its own, its first sentence after the
    # caption is an item of the lead-in's kind.
    # A first sentence that starts in lower case continues the parent's unfinished sentence, whatever follows it.
    if lead is not None and lead_scope:
        for index, (s, e) in enumerate(spans):
            sent = text[s:e]
            if _caption(sent, index + 1 < len(spans)):
                continue
            mine = [n for n in out if not n.inherited and base + s <= n.marker_at < base + e]
            continues = bool(re.match(r"[\W\d]*[a-z]", sent))
            if not mine and (continues or not any(not n.inherited for n in out)):
                out.insert(0, inherit(s, e, lead))
            break
    return out, opened


def _is_list_item(sent: str) -> bool:
    """A line under a colon that reads as an item of the list: a phrase of three words or more ending as a list item
    ends ("Perform the maintenance or repairs."), not a table's cell ("$40 or warning", "1st Violation")."""
    s = sent.strip()
    return (len(s) < 400 and len(s.split()) >= 3 and bool(re.search(r"(?:[.;]|\b(?:and|or))\s*$", s))
            and not re.match(r"[\W\d]*\$|(?:the|if|this|these|all|any|each|no)\b", s, re.I))




def _lead_from(sent: str, norms: list[DocumentDuty], last_bearer: tuple[Bearer, str]) -> LeadIn:
    if _LEADIN_CONDITIONS.search(sent):
        kind = DutyKind.CONDITION
    elif norms:
        kind = norms[0].kind
        if kind in (DutyKind.DEFINITION, DutyKind.CONDITION) and re.search(r"\b(?:power|authority)\b", sent, re.I):
            kind = DutyKind.PERMISSION
        elif kind is DutyKind.DEFINITION and re.search(r"\bright", sent, re.I):
            kind = DutyKind.RIGHT
    else:
        kind = DutyKind.PERMISSION if re.search(r"\b(?:power|authority)\b", sent, re.I) else DutyKind.DUTY
    first = norms[0] if norms else None
    bearer, words = (first.bearer, first.bearer_words) if first and first.bearer is not Bearer.UNSTATED else last_bearer
    return LeadIn(kind, bearer, words, first.marker if first else "")


def _descends(child: str, parent: str) -> bool:
    return bool(parent) and child != parent and (child.startswith(parent + "(") or child.startswith(parent + "."))


def read_outline(outline: Any, *, passages: Iterable[Any] | None = None) -> list[DocumentDuty]:
    """Every norm in ``outline`` (a ``DocumentOutline``), section by section, each list item under a lead-in taking the
    lead-in's kind and bearer. ``passages`` are ``reference_model.Passage`` rows; by default every section's own words."""
    from jason.community.reference_model import passages as passages_of

    rows = list(passages) if passages is not None else passages_of(outline, max_chars=1_000_000, min_chars=1)
    leads: list[tuple[str, LeadIn]] = []          # (section, its lead-in), innermost last
    out: list[DocumentDuty] = []
    for p in rows:
        leads = [(sec, li) for sec, li in leads if _descends(p.section, sec)]
        parent = leads[-1][1] if leads else None
        found, opened = read_passage(p.text, source=outline.key, section=p.section, base=p.start, lead=parent,
                                     lead_scope=parent is not None)
        out.extend(found)
        if opened is not None and p.section:
            leads.append((p.section, opened))
    return out


def norms_only(items: Iterable[DocumentDuty]) -> list[DocumentDuty]:
    return [i for i in items if i.kind in NORMS]


__all__ = ["DutyKind", "NORMS", "Bearer", "ReviewStatus", "DeadlineRelation", "Deadline", "DocumentDuty", "LeadIn",
           "sentences", "find_bearer", "find_deadline", "find_recurrence", "find_trigger", "find_conditions",
           "read_passage", "read_outline", "norms_only", "replace", "field"]
