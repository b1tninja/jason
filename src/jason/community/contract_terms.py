"""A contract's terms as records: who must do what, by when, for how much, and how a dispute or a notice is handled.

A contract is a governing document between two parties: it states duties, deadlines, money, and procedures the same way
CC&Rs do, so it is read with the same phrase grammar (``jason.community.deontic``). What a contract adds is the parties.
Each one names itself ("Network Example Management, Inc. (hereinafter "MANAGER")", "the Association"), so a bearer is
read from the contract's own defined terms (``defined_parties``) rather than a governing document's list of people.

The reading, in order:

1. **Sections.** The numbered headings ("3.4 Log", "10. Termination", "(b)") split the text (``split_sections``).
2. **Norms.** ``deontic.read_passage`` reads each section: duties, prohibitions, permissions, rights, and conditions, each
   with its quote, deadline, recurrence, conditions, and whether it is a notice. The bearer becomes a ``Party``: the
   association's side, the counterparty, either party, or someone else.
3. **Statements.** A sentence with no "shall" can still be a term ("The term of this Agreement is one year", "This
   Agreement is governed by the laws of ..."): a sentence a key topic rule matches is kept as a ``STATEMENT``.
4. **Topics.** ``TOPIC_RULES`` rows, in order, put each term on the review checklist's shelf (docs/contracts.md): notice,
   termination, money, dispute resolution, logs and reports, records, insurance. A new kind of clause is a new row.
5. **Particulars.** Amounts in cents, a notice window's two edges, and the delivery a notice clause names.
6. **Deliverables.** A duty the counterparty bears that produces something the association can ask to see (a log, a
   report, a statement, an agenda, a certificate) or that has a clock: what the association can hold the vendor to.
7. **Findings.** Leads beside the statutes in docs/contracts.md (Civil Code 1668, 1671, 1717, 5380; Code of Civil
   Procedure 337, 1281). A finding is a lead for a person, never a determination.

A model may review the grammar's terms and add what it missed (``jason.community.term_model``): a local Ollama or Claude
on Bedrock. Nothing it says is kept unless its quote is in the text. The prompt names kinds and topics, never a section
number, a party's name, or a figure.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from dataclasses import replace as dc_replace
from enum import Enum
from typing import Any, Iterable

from jason.community.deontic import (
    Bearer, Deadline, DeadlineRelation, DocumentDuty, DutyKind, find_conditions, find_deadline, find_recurrence,
    read_passage, sentences,
)
from jason.community.document_models import Finding, Severity


class TermKind(Enum):
    DUTY = "duty"                    # must act
    PROHIBITION = "prohibition"      # must not act
    PERMISSION = "permission"        # may act
    RIGHT = "right"                  # is entitled to
    CONDITION = "condition"          # an effect that turns on an event
    STATEMENT = "statement"          # a term stated without a modal: the term, the governing law, a fee
    EXEMPTION = "exemption"          # a party is not obligated, not responsible, or a thing is excluded (``exemptions``)


_FROM_DUTY = {DutyKind.DUTY: TermKind.DUTY, DutyKind.PROHIBITION: TermKind.PROHIBITION,
              DutyKind.PERMISSION: TermKind.PERMISSION, DutyKind.RIGHT: TermKind.RIGHT,
              DutyKind.CONDITION: TermKind.CONDITION}


class Party(Enum):
    ASSOCIATION = "association"      # the association, its board, officers, or committees
    COUNTERPARTY = "counterparty"    # the manager, vendor, contractor, or firm on the other side
    EITHER = "either"                # "either party", "each Party", "the Parties"
    OTHER = "other"                  # an owner, a court, an arbitrator, a third party
    UNSTATED = "unstated"


class Topic(Enum):
    """The review checklist's shelves (docs/contracts.md, What to read in every contract)."""

    PARTIES = "parties and authority"
    TERM = "term"
    RENEWAL = "renewal"
    TERMINATION = "termination"
    BREACH = "breach and cure"
    NOTICE = "notice"
    PAYMENT = "payment"
    FEES = "fees and price"
    ESCALATION = "price changes"
    SPENDING = "spending authority"
    FUNDS = "funds and accounts"
    INDEMNITY = "indemnity"
    LIABILITY = "limits of liability"
    INSURANCE = "insurance"
    DISPUTE = "dispute resolution"
    GOVERNING_LAW = "governing law and venue"
    LIMITATIONS = "time to bring a claim"
    ATTORNEY_FEES = "attorney fees"
    ASSIGNMENT = "assignment"
    EXCLUSIVITY = "exclusivity and no-hire"
    CONFIDENTIALITY = "confidentiality"
    LOGS = "logs and rosters"
    REPORTS = "reports and statements"
    MEETINGS = "meetings"
    RECORDS = "records"
    TRANSITION = "transition at the end"
    DISCLOSURE = "disclosures and conflicts"
    AMENDMENT = "amendment and entire agreement"
    SURVIVAL = "survival"
    STATUTORY_NOTICE = "statutory notice"   # a notice the law makes the contract print (``statutory_notices``)
    SCOPE = "scope of work"


# Rule rows, in order: the first that matches a term's section caption or its words places it. Match order is part of
# the rule (a "Termination" caption with a "notice" sentence is a termination term). A miss is SCOPE, never a guess.
TOPIC_RULES: tuple[tuple[Topic, str], ...] = (
    (Topic.LIMITATIONS, r"within\s+(?:\w+\s+){0,3}\(?\d+\)?\s+(?:months?|years?)\s+(?:of|after|from)\s+the\s+time.{0,80}"
                        r"(?:knew|should\s+have\s+known)|statute\s+of\s+limitations|limitations\s+period|forfeit"),
    (Topic.DISPUTE, r"binding\s+arbitration|arbitration\s+(?:in\s+accordance|conducted|under|pursuant)|"
                    r"submit\w*\s+to\s+(?:arbitration|mediation)|by\s+mediation|mediator|dispute\s+resolution|\bJAMS\b|"
                    r"American\s+Arbitration|disputes?\s+(?:between|arising)|arbitrable"),
    (Topic.GOVERNING_LAW, r"governed\s+by|governing\s+law|construed\s+in\s+accordance\s+with.{0,40}laws?|\bvenue\b|"
                          r"jurisdiction"),
    (Topic.INDEMNITY, r"indemnif|hold\s+harmless|defend\s+(?:and\s+)?(?:hold|indemnify)"),
    (Topic.ATTORNEY_FEES, r"prevailing\s+party|attorney'?s?['’]?\s+fees\s+(?:and\s+costs\s+)?(?:incurred|to\s+the)"),
    (Topic.LIABILITY, r"limit(?:ation)?\s+of\s+liability|aggregate\s+liability|consequential|warrant(?:y|ies)|"
                      r"shall\s+not\s+be\s+(?:liable|responsible)|exclusive\s+remedy"),
    (Topic.INSURANCE, r"insur|fidelity|bond(?:ed)?\b|certificate\s+of\s+insurance|additional\s+insured"),
    (Topic.EXCLUSIVITY, r"solicit|hire\s+(?:or|any)|employ(?:ee)?s?\s+of\s+(?:the\s+)?manager|no\s+other\s+manager|"
                        r"exclusive(?:ly)?\s+engage"),
    (Topic.CONFIDENTIALITY, r"confidential|trade\s+secret|proprietary"),
    (Topic.ASSIGNMENT, r"\bassign(?:able|ment|s|ed)?\b|successors?\s+and\s+assigns"),
    (Topic.BREACH, r"breach|cure|default|non-?compliance"),
    (Topic.TERMINATION, r"terminat|resign|cancel(?:lation)?|off-?ramp|expiration\s+of\s+this"),
    (Topic.RENEWAL, r"renew"),
    (Topic.TRANSITION, r"upon\s+(?:the\s+)?(?:termination|expiration)|transition|following\s+termination|"
                       r"new\s+manag"),
    (Topic.LOGS, r"\blogs?\b|roster|register\s+of|inventory\s+of|complaints?\s+(?:or|and)\s+service\s+requests?"),
    (Topic.REPORTS, r"report|statement\s+of\s+(?:receipts|income|account)|monthly\s+statement|financial\s+statement|"
                    r"balance\s+sheet|reconcil|budget"),
    (Topic.MEETINGS, r"meeting|agenda|minutes"),
    (Topic.RECORDS, r"records|books|files|documents\s+(?:and|or)\s+records|inspection\s+(?:and|of)"),
    (Topic.FUNDS, r"bank|account|deposit|trust\s+fund|commingl|reserve|transfer\s+of\s+funds|transfers?\s+(?:of\s+funds\s+)?"
                  r"between"),
    (Topic.SPENDING, r"expenditure|disburse|obligation\s+exceeding|without\s+(?:the\s+)?prior\s+(?:written\s+)?"
                     r"(?:consent|approval)|competitive\s+bid|bids?\b"),
    (Topic.ESCALATION, r"escalat|increase|cost\s+of\s+living|consumer\s+price|employment\s+cost|then-?current|"
                       r"subject\s+to\s+change"),
    (Topic.PAYMENT, r"late\s+(?:fee|charge)|finance\s+charge|per\s+annum|payable|due\s+(?:on|by)|invoice|retainer"),
    (Topic.FEES, r"\bfees?\b|compensation|\$\s?\d|price|rate\s+of|per\s+hour|per\s+month"),
    (Topic.DISCLOSURE, r"disclos|5375|conflict\s+of\s+interest|rebate|commission|referral|affiliat"),
    (Topic.AMENDMENT, r"amend|entire\s+agreement|complete\s+agreement|supersede|modif"),
    (Topic.SURVIVAL, r"surviv"),
    (Topic.NOTICE, r"\bnotic|\bnotif"),
    (Topic.TERM, r"\bterm\b|commenc|effective\s+date"),
    (Topic.PARTIES, r"by\s+and\s+between|hereinafter|is\s+made\s+and\s+entered|authority\s+to\s+execute|duly\s+elected"),
)
_TOPIC_RE = [(t, re.compile(p, re.I)) for t, p in TOPIC_RULES]

# A sentence with no "shall" is still a term when its own words match one of these topics (step 3): "will be
# automatically renewed ... unless one Party gives ... notice", "is fully assignable without consent". A form's
# description of services ("Provide new board orientation") is left to the grammar and the model.
STATEMENT_TOPICS = frozenset(t for t in Topic if t not in (Topic.SCOPE, Topic.PARTIES, Topic.LOGS, Topic.REPORTS,
                                                           Topic.MEETINGS, Topic.RECORDS))

# What a counterparty's duty produces that the association can ask to see (step 6).
DELIVERABLE_TOPICS = frozenset({Topic.LOGS, Topic.REPORTS, Topic.MEETINGS, Topic.RECORDS, Topic.INSURANCE,
                                Topic.DISCLOSURE, Topic.TRANSITION, Topic.NOTICE})

_COUNTERPARTY_WORDS = ("manager", "managing agent", "management company", "management", "contractor", "subcontractor",
                       "vendor", "company", "provider", "service provider", "consultant", "firm", "licensee", "lessor",
                       "seller", "agent", "inspector", "engineer", "attorney", "accountant", "cpa", "trustee")
_ASSOCIATION_WORDS = ("association", "hoa", "board", "board of directors", "directors", "president", "treasurer",
                      "secretary", "officer", "client", "customer", "owners association", "homeowners association")
_EITHER = re.compile(r"\b(?:either|each|both|the|any|neither)\s+part(?:y|ies)\b|\bthe\s+parties\b|\bparties\s+hereto\b",
                     re.I)
_DEFINED = re.compile(
    r"(?P<name>[A-Z][\w&.,'’\- ]{2,90}?)\s*,?\s*(?:a\s+[A-Za-z ,\-]{3,80}?)?\s*\(\s*(?:hereinafter|hereafter|herein)?\s*"
    r"(?:referred\s+to\s+(?:as\s+)?)?(?:collectively\s+)?(?:as\s+)?(?:the\s+)?[\"“”']+(?P<term>[A-Z][A-Za-z ]{1,30})[\"“”']+",
    re.S)
_COMPANY = re.compile(r"\b(?:Inc|LLC|L\.L\.C|Corp|Corporation|Company|Co|LLP|LP|Ltd|Group|Services)\b\.?", re.I)
_AMOUNT = re.compile(r"\$\s?((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d\d)?)")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?(?:%|percent\b)", re.I)
_DELIVERY = (
    ("certified mail", r"certified\s+mail|return\s+receipt"),
    ("registered mail", r"registered\s+mail"),
    ("overnight courier", r"overnight\s+(?:courier|delivery)|courier"),
    ("personal delivery", r"personal(?:ly)?\s+deliver|delivered\s+personally|personal\s+service"),
    ("mail with proof of delivery", r"proof\s+of\s+delivery"),
    ("first-class mail", r"first[- ]class\s+(?:mail|postage)|postage\s+prepaid|United\s+States\s+mail|U\.\s?S\.\s?mail"),
    ("email", r"\be-?mail\b|electronic(?:ally)?\s+(?:mail|transmission)"),
    ("fax", r"facsimile|\bfax\b"),
)
_DELIVERY_RE = [(name, re.compile(p, re.I)) for name, p in _DELIVERY]
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
          "fifteen": 15, "twenty": 20, "thirty": 30, "forty-five": 45, "sixty": 60, "ninety": 90,
          "one hundred twenty": 120, "one hundred and twenty": 120, "one hundred eighty": 180}
_N = r"(?:\d+|" + "|".join(sorted((re.escape(w) for w in _WORDS), key=len, reverse=True)) + r")(?:\s*\(\d+\))?"
_WINDOW = re.compile(rf"(?:at\s+least|not\s+less\s+than|no\s+(?:less|fewer)\s+than|a\s+minimum\s+of)\s+(?P<lo>{_N})"
                     rf"(?:\s+(?P<unit>(?:calendar\s+|business\s+)?days?|months?))?[^.;]{{0,60}}?"
                     rf"(?:(?:but|and)\s+)?(?:no|not|nor)\s+more\s+than\s+(?P<hi>{_N})", re.I)


def _number(words: str) -> int:
    words = " ".join(words.lower().split())
    m = re.search(r"\((\d+)\)", words)
    if m:
        return int(m.group(1))
    m = re.match(r"\d+", words)
    if m:
        return int(m.group(0))
    return _WORDS.get(re.sub(r"\s*\(.*$", "", words), 0)


# --- Parties ----------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class PartyTerms:
    """The words each side goes by in this contract, and the names it gives them."""

    association: tuple[str, ...] = _ASSOCIATION_WORDS
    counterparty: tuple[str, ...] = _COUNTERPARTY_WORDS
    names: dict[str, str] = field(default_factory=dict)        # defined term -> the name it stands for
    vendor_form: bool = False        # the counterparty's own form: no side is defined as the association
    roles: tuple[str, ...] = ()      # role words a side was read from, not named ("the inspection", "a responsible adult")

    def role_in(self, words: str) -> str:
        """The role word in ``words``, when a side was read from a role rather than a name; "" otherwise."""
        w = " ".join((words or "").lower().split())
        return next((r for r in self.roles if re.search(rf"(?<![\w.]){re.escape(r)}(?![\w])", w)), "")

    def party_of(self, words: str) -> Party:
        w = " ".join((words or "").lower().split())
        if not w:
            return Party.UNSTATED
        if _EITHER.search(w):
            return Party.EITHER
        # The longest matching word decides ("management company" beats "company"; "board" beats nothing).
        best: tuple[int, Party] = (0, Party.UNSTATED)
        for side, vocab in ((Party.ASSOCIATION, self.association), (Party.COUNTERPARTY, self.counterparty)):
            for v in vocab:
                if re.search(rf"(?<![\w.]){re.escape(v.lower())}(?![\w])", w) and len(v) > best[0]:
                    best = (len(v), side)
        return best[1]


_NOT_A_PARTY = frozenset({"agreement", "services", "service", "property", "project", "work", "scope", "premises",
                          "common area", "common areas", "governing documents", "effective date", "term", "fees", "log",
                          "members", "owners", "units", "president", "treasurer", "board", "exhibit", "schedule"})


def _side_of(name: str, term: str) -> Party:
    t = term.lower()
    if t in _NOT_A_PARTY:
        return Party.UNSTATED
    if re.search(r"\b(?:association|hoa|client|customer)\b", t):
        return Party.ASSOCIATION
    if any(re.search(rf"\b{re.escape(v)}\b", t) for v in _COUNTERPARTY_WORDS):
        return Party.COUNTERPARTY
    if _COMPANY.search(name) and len(term.split()) <= 3:
        return Party.COUNTERPARTY          # "Example Landscape, LLC ("Example")"
    return Party.UNSTATED


_SECOND_PERSON_DEF = re.compile(r"[\"“'‘]\s*(?P<who>we|you)\s*[,\"”'’]+[^.;]{0,40}?\b(?:mean|means|refer(?:s)?\s+to|is|are)\b"
                                r"\s+(?P<what>[^.;]{3,100})", re.I)


def _second_person(head: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The words a contract written to "you" uses for each side: (association words, counterparty words).

    A definition decides ("'we,' 'us' and 'our' mean Example Alarm Co."; "'you' and 'your' mean the customer"). With
    none, a form that says "you" and "we" throughout is the counterparty's own form: "we" is the counterparty and "you"
    the association."""
    we, you = ("we", "us", "our"), ("you", "your")
    sides: dict[str, Party] = {}
    for m in _SECOND_PERSON_DEF.finditer(head):
        what = m.group("what")
        side = (Party.ASSOCIATION if re.search(r"association|\bhoa\b|customer|client|owner|subscriber", what, re.I)
                else Party.COUNTERPARTY if (_COMPANY.search(what) or re.search(r"company|contractor|vendor|provider", what, re.I))
                else None)
        if side is not None:
            sides[m.group("who").lower()] = side
    folded = head.lower()
    uses_you = len(re.findall(r"\byou(?:r)?\b", folded)) >= 5
    uses_we = len(re.findall(r"\b(?:we|our)\b", folded)) >= 3
    if not sides and not (uses_you and uses_we):
        return (), ()
    we_side = sides.get("we") or (Party.ASSOCIATION if sides.get("you") is Party.COUNTERPARTY else Party.COUNTERPARTY)
    you_side = sides.get("you") or (Party.COUNTERPARTY if we_side is Party.ASSOCIATION else Party.ASSOCIATION)
    assoc = (we if we_side is Party.ASSOCIATION else ()) + (you if you_side is Party.ASSOCIATION else ())
    counter = (we if we_side is Party.COUNTERPARTY else ()) + (you if you_side is Party.COUNTERPARTY else ())
    return assoc, counter


# Words that open many firms' names and many ordinary sentences: never taken alone as a short form of a name.
_COMMON_FIRST_WORDS = ("north", "south", "east", "west", "american", "national", "california", "pacific", "general",
                       "united", "professional", "premier", "quality", "first", "golden", "valley", "best", "advanced",
                       "allied", "central", "western", "northern", "southern", "home", "extra", "review", "bonding",
                       "construction", "security", "landscape", "landscaping", "roofing", "plumbing", "electric",
                       "insurance", "management", "services", "group", "community", "all", "year", "pro", "top")


def _initials(name: str) -> tuple[str, ...]:
    """The short forms a firm may call itself: its initials ("The Example Sprinkler Company" -> "T.E.S.C.", "TESC",
    and without "The", "E.S.C.", "ESC"), and its first distinctive word ("Example")."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'’&-]*", name) if w.lower() not in ("inc", "llc", "corp", "ltd", "co")]
    if len(words) < 2:
        return ()
    out = []
    for ws in (words, words[1:] if words[0].lower() == "the" else []):
        if len(ws) >= 2:
            letters = "".join(w[0].upper() for w in ws)
            out += [".".join(letters) + ".", letters]
    first = next((w for w in words if w.lower() not in ("the", "a", "an") and len(w) >= 4), "")
    if (first and first.lower() not in _COUNTERPARTY_WORDS + _ASSOCIATION_WORDS + _COMMON_FIRST_WORDS
            and not first.isupper()):
        out.append(first)
    return tuple(dict.fromkeys(out))


# Short forms the alias reader can return that are never a party of the contract (a licensing board, a code).
_NOT_ALIAS_WORDS = ("cslb", "dre", "bsis", "spcb", "nfpa", "ul", "ada", "osha", "cbc", "cfc", "ccr", "irs", "dir")


def _alias_words(text: str, counterparty: str) -> list[tuple[Party, str]]:
    """Each alias of the counterparty (``aliases_of`` its name) as a counterparty word, and each role label as the side
    it names: the counterparty's when the label's name is the counterparty's, the association's for a customer role
    word ("CUSTOMER", "OWNER", "CLIENT")."""
    from jason.community.party_aliases import AliasKind, aliases_of, find_aliases

    found = find_aliases(text or "")
    out: list[tuple[Party, str]] = []
    if counterparty:
        out += [(Party.COUNTERPARTY, a.lower()) for a in aliases_of(counterparty, found)]
    for a in found:
        if a.kind is not AliasKind.ROLE_LABEL:
            continue
        label = a.alias.lower()
        if counterparty and a.name and _same_name(a.name, counterparty):
            out.append((Party.COUNTERPARTY, label))
        elif re.fullmatch(r"customer|owner|client|association|hoa|purchaser|buyer|subscriber", label):
            out.append((Party.ASSOCIATION, label))
    return out


def _same_name(a: str, b: str) -> bool:
    words = lambda s: {w for w in re.findall(r"[a-z0-9]+", s.lower())  # noqa: E731
                       if w not in ("inc", "llc", "corp", "co", "company", "the", "ltd", "llp", "group", "services")}
    x, y = words(a), words(b)
    return bool(x and y and (x <= y or y <= x))


def defined_parties(text: str, *, raw: str | None = None) -> PartyTerms:
    """The parties' defined terms in the first pages ("Acme, Inc. (hereinafter "MANAGER")", "(the "Association")"), the
    second person of a form written to "you", and the short forms the counterparty uses for itself in the text."""
    head = (text or "")[:20_000]
    assoc_you, counter_we = _second_person(head)
    association, counterparty, names = list(_ASSOCIATION_WORDS + assoc_you), list(_COUNTERPARTY_WORDS + counter_we), {}
    for m in _DEFINED.finditer(head):
        term = " ".join(m.group("term").split())
        name = " ".join(m.group("name").split()).strip(" ,")
        # The name starts after the parties clause's own words ("... by and between Acme, Inc." -> "Acme, Inc."), and
        # after any sentence it was run into ("Extra Work. Owner agrees to pay Example Company").
        name = re.split(r"\b(?:by\s+and\s+between|between|and|with|pay|to)\s+(?=[A-Z])", name)[-1].strip(" ,")
        from jason.community.licenses import _clean

        name = _clean(name) or name
        side = _side_of(name, term)
        if side is Party.ASSOCIATION and term.lower() not in association:
            association.append(term.lower())
        elif side is Party.COUNTERPARTY and term.lower() not in counterparty:
            counterparty.append(term.lower())
        if side is not Party.UNSTATED:
            names[term] = name
    # In the counterparty's own form (no side defined as the association: a proposal, an estimate, a vendor's terms),
    # "Owner" is the customer it was written for, the association. A form for owners' units ("unit owner",
    # "homeowner") keeps "owner" as an owner.
    defined_association = any(_side_of(n, t) is Party.ASSOCIATION for t, n in names.items())
    unit_owners = len(re.findall(r"\b(?:unit|lot|home)\s*owners?\b|\bhomeowners?\b", head, re.I))
    if not defined_association and not assoc_you and unit_owners < 2 and "owner" not in association:
        association.append("owner")
    # The counterparty's own short forms, when the text uses them ("T.E.S.C. shall ..."), with no definition needed.
    who = _name_candidate(text or "", names)
    if who:
        for short in _initials(who):
            if short.lower() not in counterparty and re.search(rf"(?<![\w.]){re.escape(short)}(?![\w])", head):
                counterparty.append(short.lower())
    # The other names the parties go by (``party_aliases``): a dba, a parenthetical short form "(EHS)", and a role label
    # on its own line ("CUSTOMER:", "EXAMPLE CAMERAS:"). They are read from the text as laid out (``raw``), since a
    # label alone on its line is joined to the line above by unwrapping.
    for side, words in _alias_words(raw if raw is not None else text, who):
        vocab = counterparty if side is Party.COUNTERPARTY else association
        if words not in vocab and words not in _NOT_ALIAS_WORDS:
            vocab.append(words)
    # In the counterparty's own form, a sentence about its service ("the inspection will comply with ...") is the
    # counterparty's, and one about a person at the customer's premises ("a responsible adult must be present") the
    # association's: role readings, labeled as such on the term (``PartyTerms.role_in``).
    vendor_form = not defined_association and "we" not in assoc_you
    roles: tuple[str, ...] = ()
    if vendor_form:
        for word in _SERVICE_ROLES:
            if word not in counterparty:
                counterparty.append(word)
        for word in _PREMISES_ROLES:
            if word not in association:
                association.append(word)
        roles = _SERVICE_ROLES + _PREMISES_ROLES
    return PartyTerms(tuple(association), tuple(counterparty), names, vendor_form, roles)


_SERVICE_ROLES = ("the inspection", "the inspections", "inspections", "the service", "the services", "the service call",
                  "the work", "all work", "the installation", "the monitoring", "the repairs", "our technician",
                  "our technicians", "the technician", "the technicians", "the crew")
_PREMISES_ROLES = ("a responsible adult", "an adult", "an authorized person", "an authorized representative",
                   "the customer's representative", "the resident", "the occupant")


_BEARER_SIDE = {Bearer.ASSOCIATION: Party.ASSOCIATION, Bearer.BOARD: Party.ASSOCIATION, Bearer.OFFICER: Party.ASSOCIATION,
                Bearer.COMMITTEE: Party.ASSOCIATION, Bearer.MANAGER: Party.COUNTERPARTY, Bearer.OWNER: Party.OTHER,
                Bearer.MEMBER: Party.OTHER, Bearer.OCCUPANT: Party.OTHER, Bearer.OTHER: Party.OTHER,
                Bearer.MORTGAGEE: Party.OTHER, Bearer.DECLARANT: Party.OTHER, Bearer.CANDIDATE: Party.OTHER,
                Bearer.INSPECTOR: Party.OTHER}


# --- Sections ---------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Section:
    number: str                      # as written: "3.4", "10", "10(b)", "ARTICLE VI", "" before the first heading
    caption: str                     # the heading's words: "Log", "Termination"
    start: int
    end: int


_HEAD = re.compile(
    r"(?m)^[ \t]*(?P<num>ARTICLE\s+[IVXLC\d]+|Article\s+[IVXLC\d]+|Section\s+\d+(?:\.\d+)*|\d{1,2}(?:\s?\.\s?\d{1,2}){0,3}\.?"
    r"|\(\s?[a-z]\s?\)|[a-z]\))(?=[ \t]+[A-Z(“\"']|[ \t]*$)[ \t]*(?P<cap>[^\n]{0,90})")


def _caption(rest: str) -> str:
    cap = re.split(r"\s[–—-]\s|[.:](?:\s|$)", rest.strip(), maxsplit=1)[0]
    words = cap.split()
    return " ".join(words[:8]) if 0 < len(words) <= 8 or rest.strip().endswith(cap) else " ".join(words[:6])


# A word that cites a section ("under Section 3.1 below", "see paragraph 7.2"): the number after it is a reference, kept.
_REFERENCE_WORDS = (r"\b(?:section|sections|paragraph|paragraphs|article|clause|exhibit|item|items|schedule|subsection|"
                    r"see|under|per|in|of|and|or|to)$")


def unwrap(text: str) -> str:
    """A PDF's text with its line wraps joined, so a sentence is one line: a line break stays before a heading, a list
    item, or a blank line, and after a line ending in a colon. A hyphen at a wrap ("manage-\\nment") is joined. The
    reading's offsets are into this text."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not out:
            out.append(stripped)
            continue
        prev = out[-1]
        # A two-column layout drops a section number into the middle of a sentence ("... including our\n3.1. yard
        # signs ..."): a number between a lowercase word and a lowercase word is the other column's, not a heading.
        column = re.match(r"^(\d{1,2}(?:\.\d{1,2})+\.?)\s+(?=[a-z])", stripped)
        if column and prev and re.search(r"[a-z,]$", prev) and not re.search(_REFERENCE_WORDS, prev.lower()):
            stripped = stripped[column.end():]
        # A role label alone on its line ("CUSTOMER:", "EXAMPLE CAMERAS:") heads the lines under it: it keeps its line.
        label = bool(re.match(r"^[A-Z][A-Z0-9&.,' -]{1,40}:$", stripped))
        breaks = (not stripped or not prev or prev.endswith(":") or label or bool(_HEAD.match(stripped))
                  or bool(re.match(r"^(?:[•●▪◦*\-]\s|o\s+(?=[A-Z])|--- page)", stripped)) or prev.startswith("--- page"))
        if breaks:
            out.append(stripped)
        elif prev.endswith("-") and not prev.endswith(" -") and stripped[:1].islower():
            out[-1] = prev[:-1] + stripped
        else:
            out[-1] = prev + " " + stripped
    joined = "\n".join(out)
    # The same column artifact inside a line ("You must maintain all risk 7.2. insurance for damage ...").
    def _drop_column_number(m: re.Match[str]) -> str:
        before = joined[max(0, m.start() - 15):m.start() + 1]
        return m.group(0) if re.search(_REFERENCE_WORDS, before.rstrip(" ,").lower()) else m.group(1) + " "

    joined = re.sub(r"([a-z,])\s+\d{1,2}(?:\.\d{1,2})+\.?\s+(?=[a-z])", _drop_column_number, joined)
    # A bullet the text layer ran into the line before it ("... deficiencies. o T.E.S.C. shall ..."): its own line.
    joined = re.sub(r"(?<=[.;:])[ \t]+[o•●▪◦][ \t]+(?=[A-Z])", "\n", joined)
    return re.sub(r"\n{3,}", "\n\n", joined).strip()


@dataclass(frozen=True)
class Prepared:
    """A document's words made ready once for every reader: unwrapped, cut into sections, and its parties read."""

    body: str                        # the unwrapped text; every reader's offsets are into this
    sections: tuple["Section", ...]
    parties: "PartyTerms"

    @property
    def numbered(self) -> int:
        """How many sections carry a number: a measure of how structured the document is."""
        return sum(1 for s in self.sections if s.number)


_PREPARED: dict[str, Prepared] = {}
_PREPARED_MAX = 64


def prepare(text: str) -> Prepared:
    """The document unwrapped, sectioned, and its parties read, computed once per text (the kind analysis and each
    kind reader ask for the same file in one ingest run). The cache keeps the last few dozen texts."""
    key = hashlib.sha1((text or "").encode("utf-8", "replace")).hexdigest()
    found = _PREPARED.get(key)
    if found is None:
        body = unwrap(text)
        found = Prepared(body, tuple(split_sections(body)), defined_parties(body, raw=text))
        if len(_PREPARED) >= _PREPARED_MAX:
            _PREPARED.pop(next(iter(_PREPARED)))
        _PREPARED[key] = found
    return found


def split_sections(text: str) -> list[Section]:
    """The text cut at its numbered headings. A lettered item takes the number above it ("10(b)"); a page header that
    repeats a number is not told apart, which a person sees as a short section."""
    text = text or ""
    found: list[tuple[int, str, str]] = []
    parent = ""
    for m in _HEAD.finditer(text):
        num = re.sub(r"\s+", " ", m.group("num")).strip().rstrip(".").replace(" .", ".").replace(". ", ".")
        if re.fullmatch(r"\d{4}", num):           # a year at the start of a line is not a heading
            continue
        if re.fullmatch(r"\(?\s?[a-z]\s?\)", num):
            letter = num.strip("() ")
            num = f"{parent}({letter})" if parent else f"({letter})"
        elif re.fullmatch(r"\d{1,2}", num) and re.match(r"(\d+)\.\d", parent) and \
                int(num) < int(re.match(r"(\d+)", parent).group(1)):
            num = f"{parent}[{num}]"           # a numbered list inside "3.7": its items, not new articles
        else:
            parent = num
        found.append((m.start(), num, _caption(m.group("cap") or "")))
    out: list[Section] = []
    if not found or found[0][0] > 0:
        out.append(Section("", "", 0, found[0][0] if found else len(text)))
    for n, (start, num, cap) in enumerate(found):
        end = found[n + 1][0] if n + 1 < len(found) else len(text)
        out.append(Section(num, cap, start, end))
    return [s for s in out if text[s.start:s.end].strip()]


# --- Terms ------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ContractTerm:
    """One term of a contract, as the grammar or a model read it from the words."""

    source: str                      # the document's key
    section: str
    caption: str
    start: int
    end: int
    quote: str
    kind: TermKind
    party: Party
    topic: Topic
    party_words: str = ""            # the words that named the bearer
    action: str = ""
    deadline: Deadline | None = None
    window_days: tuple[int, int] | None = None     # a notice window's two edges, (shortest, longest)
    recurrence: str = ""
    recurrence_months: int = 0
    conditions: tuple[str, ...] = ()
    notice: bool = False
    delivery: tuple[str, ...] = ()   # the deliveries a notice clause names
    amounts: tuple[int, ...] = ()    # cents
    percents: tuple[float, ...] = ()
    deliverable: bool = False
    method: str = "grammar"          # "grammar", "model:<backend>", or "hybrid:<backend>"
    note: str = ""
    exemption: str = ""              # ``exemptions.ExemptionKind`` value: what the term releases
    discretion: str = ""             # ``discretion.Degree`` value: the room the term leaves its holder
    discretion_over: str = ""        # what that room is over: price, terms, termination, ...
    standards: tuple[str, ...] = ()  # the codes or standards the term brings in by reference
    warranty_months: int = 0         # the warranty's period the term gives (``warranties``), 0 for none or unstated
    consent: str = ""                # whose consent or approval the term requires (``consent``): a Party value or words

    @property
    def id(self) -> str:
        words = " ".join(self.quote.split()).lower()
        digest = hashlib.sha1(f"{self.source}|{self.section}|{words}|{self.kind.value}".encode("utf-8")).hexdigest()[:10]
        return f"{self.source}#{self.section or '-'}:{digest}"

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw.update(kind=self.kind.value, party=self.party.value, topic=self.topic.value, id=self.id,
                   conditions=list(self.conditions), delivery=list(self.delivery), amounts=list(self.amounts),
                   percents=list(self.percents), standards=list(self.standards),
                   window_days=list(self.window_days) if self.window_days else None)
        if self.deadline is not None:
            raw["deadline"] = {**asdict(self.deadline), "relation": self.deadline.relation.value}
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ContractTerm:
        d = raw.get("deadline")
        names = set(cls.__dataclass_fields__)
        data = {k: v for k, v in raw.items() if k in names}
        return cls(**{**data, "kind": TermKind(raw["kind"]), "party": Party(raw["party"]),
                      "topic": next(t for t in Topic if t.value == raw["topic"]),
                      "deadline": Deadline(**{**d, "relation": DeadlineRelation(d["relation"])}) if d else None,
                      "window_days": tuple(raw["window_days"]) if raw.get("window_days") else None,
                      "conditions": tuple(raw.get("conditions") or ()), "delivery": tuple(raw.get("delivery") or ()),
                      "amounts": tuple(raw.get("amounts") or ()), "percents": tuple(raw.get("percents") or ())})


_TOPIC_BY_VALUE = {t.value: t for t in Topic}


def topic_of(caption: str, quote: str) -> Topic:
    """A phrase rule's topic first (``topic_phrases``: "materially breaches this Agreement", a fee line, "made this ___
    day of"); else the first word rule row that matches the section's caption, then the words, skipping a topic a veto
    row says these words are not ("trees ... breach the safety height" is not breach and cure); SCOPE for a miss."""
    from jason.community.topic_phrases import topic_by_phrase, vetoed

    phrased = _TOPIC_BY_VALUE.get(topic_by_phrase(caption, quote) or "")
    if phrased is not None:
        return phrased
    for words in (caption, quote):
        for topic, rx in _TOPIC_RE:
            if words and rx.search(words) and not vetoed(topic.value, quote):
                return topic
    return Topic.SCOPE


def window_of(words: str) -> tuple[int, int] | None:
    """A notice window's shortest and longest lead, in days or months as written ("at least sixty (60) days prior, but
    no more than one hundred and twenty (120) days prior" -> (60, 120))."""
    m = _WINDOW.search(" ".join((words or "").split()))
    if not m:
        return None
    lo, hi = _number(m.group("lo")), _number(m.group("hi"))
    return (lo, hi) if 0 < lo < hi else None


def deliveries(words: str) -> tuple[str, ...]:
    return tuple(name for name, rx in _DELIVERY_RE if rx.search(words or ""))


def amounts(words: str) -> tuple[int, ...]:
    out = []
    for m in _AMOUNT.finditer(words or ""):
        whole, _, frac = m.group(1).replace(",", "").partition(".")
        out.append(int(whole) * 100 + int(frac or 0))
    return tuple(out)


def percents(words: str) -> tuple[float, ...]:
    return tuple(float(m.group(1)) for m in _PERCENT.finditer(words or ""))


_HANDS_OVER = re.compile(r"\b(?:deliver|provide|submit|furnish|send|issue|give|mail|email|file|post)s?\b[^.;]{0,60}?"
                         r"\b(?:invoices?|reports?|estimates?|certificates?|statements?|notices?|logs?|records|copies|"
                         r"proposals?|bids?|schedules?|tags?|photographs?|photos)\b", re.I)


# A fire protection document: only its duties are read against the State Fire Marshal's rules (a landscaping bid's
# "estimate before repair" is not 19 CCR 904.2(k)).
_FIRE_DOCUMENT = re.compile(r"sprinkler|fire\s+(?:alarm|pump|protection|suppression|extinguisher)|standpipe|NFPA\s*\d|"
                            r"Title\s+19|19\s+CCR|fire\s+marshal", re.I)


def is_fire_document(text: str) -> bool:
    return bool(_FIRE_DOCUMENT.search(text or ""))


def _particulars(term: ContractTerm, text: str, *, fire: bool = False) -> ContractTerm:
    """Fill the amounts, window, deliveries, and deliverable flag from the term's own words. ``fire``: the document is
    a fire protection contract, so its duties are also read against the State Fire Marshal's rules."""
    words = term.quote
    topic = term.topic
    # A record the law makes a fire protection vendor hand over (a report to the owner and the fire authority, an
    # itemized invoice, a tag; ``fire_protection``) is the vendor's deliverable, even said in the passive ("shall be
    # properly tagged"): the regulation, not the sentence, names who does it.
    from jason.community.fire_protection import deliverable_rule

    rule = (deliverable_rule(words) if fire and term.kind is TermKind.DUTY and topic is not Topic.STATUTORY_NOTICE
            else None)
    if rule is not None and term.party in (Party.COUNTERPARTY, Party.UNSTATED):
        reason = f"{rule.authority}: {rule.what}" + (" (the regulation puts it on the vendor)"
                                                      if term.party is Party.UNSTATED else "")
        term = dc_replace(term, party=Party.COUNTERPARTY, note=(term.note + "; " if term.note else "") + reason)
    else:
        rule = None
    delivery = deliveries(words) if (topic in (Topic.NOTICE, Topic.TERMINATION, Topic.BREACH, Topic.RENEWAL)
                                     or re.search(r"\bnotices?\b", words, re.I)) else ()
    window = window_of(words)
    timed = term.deadline is not None or bool(term.recurrence_months)
    # Something handed over is a deliverable whatever its topic: an itemized invoice (a fire protection vendor owes one,
    # 19 CCR 904.2(e)), a report, an estimate, a certificate, a notice.
    hands_over = bool(_HANDS_OVER.search(words))
    deliverable = rule is not None or (
        term.party is Party.COUNTERPARTY and term.kind is TermKind.DUTY
        and (topic in DELIVERABLE_TOPICS or hands_over or (timed and topic not in (Topic.PAYMENT, Topic.FEES)))
        and topic not in (Topic.INDEMNITY, Topic.LIABILITY, Topic.STATUTORY_NOTICE))
    return ContractTerm(**{**{f: getattr(term, f) for f in term.__dataclass_fields__},
                           "amounts": amounts(words), "percents": percents(words), "window_days": window,
                           "delivery": delivery, "deliverable": deliverable})


def _party(duty: DocumentDuty, parties: PartyTerms, sentence: str) -> tuple[Party, str]:
    words = duty.bearer_words or ""
    side = parties.party_of(words)
    if side is not Party.UNSTATED:
        return side, words
    mapped = _BEARER_SIDE.get(duty.bearer, Party.UNSTATED)
    if duty.bearer is Bearer.MANAGER and "manager" not in parties.counterparty:
        mapped = Party.OTHER
    if mapped is not Party.UNSTATED:
        return mapped, words
    # The grammar left it out (a subject it does not know, "Contractor shall"): the sentence's subject decides.
    at = max(0, duty.marker_at - duty.start)
    subject = sentence[:at] if at else sentence[:60]
    side = parties.party_of(subject[-80:])
    if side is Party.UNSTATED and parties.vendor_form and duty.passive and duty.kind is DutyKind.DUTY:
        # A passive duty in the counterparty's own form ("System(s) shall be inspected ...", "shall be removed") is the
        # work it is offering: a reading, labeled on the term.
        return Party.COUNTERPARTY, PASSIVE_READING
    return side, subject.strip()[-60:]


PASSIVE_READING = "(passive, in the counterparty's own form)"


def _reading_note(parties: PartyTerms, words: str) -> str:
    """The label a party read from a role or the passive carries: a reading for a person to confirm, not the words."""
    if words == PASSIVE_READING:
        return "a role reading: a passive duty in the counterparty's own form is its work"
    role = parties.role_in(words)
    return f"a role reading: \"{role}\" is read as the {'counterparty' if role in _SERVICE_ROLES else 'association'}" \
        if role else ""


def read_terms(text: str, *, source: str = "", parties: PartyTerms | None = None,
               sections: Iterable[Section] | None = None) -> list[ContractTerm]:
    """Every term the grammar reads in the contract, in order. ``parties`` defaults to the contract's own definitions,
    ``sections`` to its numbered headings (``prepare`` gives both, once)."""
    text = text or ""
    parties = parties or defined_parties(text)
    fire = is_fire_document(text)
    sections = list(sections if sections is not None else split_sections(text))
    out: list[ContractTerm] = []
    lead = None
    for sec in sections:
        body = text[sec.start:sec.end]
        covered: list[tuple[int, int]] = []
        item = bool(re.search(r"\(\w\)$|\[\d+\]$", sec.number))       # a list item under the section above
        norms, opened = read_passage(body, source=source, section=sec.number, base=sec.start,
                                     lead=lead if item else None, lead_scope=item and lead is not None)
        lead = opened or (lead if item else None)
        for duty in norms:
            kind = _FROM_DUTY.get(duty.kind)
            if kind is None:
                continue
            party, words = _party(duty, parties, text[duty.start:duty.end])
            topic = topic_of(sec.caption, duty.quote)
            term = ContractTerm(
                source=source, section=sec.number, caption=sec.caption, start=duty.start, end=duty.end, quote=duty.quote,
                kind=kind, party=party, topic=topic, party_words=words, action=duty.action, deadline=duty.deadline,
                recurrence=duty.recurrence, recurrence_months=duty.recurrence_months, conditions=duty.conditions,
                notice=duty.notice or topic is Topic.NOTICE, note=_reading_note(parties, words))
            out.append(_particulars(term, text, fire=fire))
            covered.append((duty.start, duty.end))
        for s, e in sentences(body):
            s, e = sec.start + s, sec.start + e
            if any(cs < e and s < ce for cs, ce in covered):
                continue
            quote = text[s:e]
            if len(quote.split()) < 5:
                continue
            willed = _will_term(quote, parties)
            if willed is not None:
                kind, party, subject = willed
                term = ContractTerm(source=source, section=sec.number, caption=sec.caption, start=s, end=e, quote=quote,
                                    kind=kind, party=party, topic=topic_of(sec.caption, quote), party_words=subject,
                                    deadline=find_deadline(quote), conditions=find_conditions(quote),
                                    recurrence=find_recurrence(quote)[0] or "", recurrence_months=find_recurrence(quote)[1],
                                    note="; ".join(n for n in ("a \"will\" sentence read as a promise (contract reading)",
                                                               _reading_note(parties, subject)) if n))
                out.append(_particulars(term, text, fire=fire))
                continue
            topic = topic_of("", quote)          # the sentence's own words, not its caption, make it a term
            if topic not in STATEMENT_TOPICS:
                continue
            deadline = find_deadline(quote)
            recurrence, months = find_recurrence(quote)
            term = ContractTerm(source=source, section=sec.number, caption=sec.caption, start=s, end=e, quote=quote,
                                kind=TermKind.STATEMENT, party=Party.UNSTATED, topic=topic, deadline=deadline,
                                recurrence=recurrence or "", recurrence_months=months,
                                conditions=find_conditions(quote))
            out.append(_particulars(term, text, fire=fire))
    out = _role_terms(text, parties, sections, out, source=source, fire=fire)
    out = _qualify(text, parties, sections, out, source=source, fire=fire)
    # One term per quote: a compound sentence read twice ("shall maintain ... and shall make available") is one term,
    # kept with its first reading; and a document that carries the contract twice (a copy and the signed copy, or an
    # e-signature envelope) gives each term once, at its first place.
    seen: set[tuple[int, int]] = set()
    words_seen: set[str] = set()
    unique: list[ContractTerm] = []
    for t in out:
        words = " ".join(re.sub(r"[^\w\s]", " ", t.quote.lower()).split())
        if (t.start, t.end) in seen or (len(words) > 20 and words in words_seen):
            continue
        seen.add((t.start, t.end))
        words_seen.add(words)
        unique.append(t)
    return unique


# A line under a role label that opens with these is not an order to the label's party ("If permits are required,
# ...", "Your sales representative will ..."): it is read by its own words.
_NOT_IMPERATIVE = frozenset(
    "if when where while after before once unless until the a an your our their its his her this that these those all "
    "each every any some no we you it they there here step note notes fees fee total annual monthly".split())
ROLE_READING = "the line sits under the party's role label (contract reading)"


def _role_terms(text: str, parties: PartyTerms, sections: list[Section], out: list[ContractTerm], *, source: str,
                fire: bool) -> list[ContractTerm]:
    """The lines under a role label ("CUSTOMER:", "EXAMPLE CAMERAS:"; ``party_aliases.role_sections``) belong to the
    label's party: a term read there with no party takes the label's, and an order with no subject ("Provide access
    to each location.") is the label party's duty. A label that names neither party changes nothing."""
    from jason.community.party_aliases import role_sections

    found = list(out)
    for rs in role_sections(text):
        side = parties.party_of(rs.label.alias)
        if side not in (Party.ASSOCIATION, Party.COUNTERPARTY):
            continue
        for s, e in sentences(rs.text):
            s, e = rs.start + s, rs.start + e
            quote = text[s:e].strip()
            if not quote.endswith((".", "!", ";")) or len(quote.split()) < 3:
                continue
            hits = [i for i, t in enumerate(found) if t.start < e and s < t.end]
            if hits:
                for i in hits:
                    if found[i].party is Party.UNSTATED:
                        found[i] = dc_replace(found[i], party=side, party_words=rs.label.alias,
                                           note="; ".join(n for n in (found[i].note, ROLE_READING) if n))
                continue
            first = re.match(r"[A-Za-z]+", quote)
            if not first or not quote[0].isupper() or first.group().lower() in _NOT_IMPERATIVE:
                continue
            if re.search(r"\b(?:will|shall|must|may|is|are)\b", quote.split(",")[0], re.I):
                continue                    # a sentence with its own verb and subject, not an order
            sec = next((x for x in sections if x.start <= s < x.end), None)
            term = ContractTerm(source=source, section=sec.number if sec else "", caption=sec.caption if sec else "",
                                start=s, end=s + len(quote), quote=quote, kind=TermKind.DUTY, party=side,
                                topic=topic_of(sec.caption if sec else "", quote), party_words=rs.label.alias,
                                action=first.group().lower(), deadline=find_deadline(quote),
                                conditions=find_conditions(quote), note=ROLE_READING)
            found.append(_particulars(term, text, fire=fire))
    return sorted(found, key=lambda t: (t.start, t.end))


# A clause that binds after the exemption's clause ("..., but Contractor shall keep the site clean"): the sentence
# is a duty with an exemption beside it, not an exemption.
_BINDS = re.compile(r"\b(?:shall|must|will|agrees?\s+to)\b(?!\s+not\b)", re.I)
EXEMPTION_READING = "a release from a duty, read by its words (contract reading)"


def _qualify(text: str, parties: PartyTerms, sections: list[Section], out: list[ContractTerm], *, source: str,
             fire: bool) -> list[ContractTerm]:
    """Each term's qualifiers, read by their rows: an exemption ("Manager shall not be obligated to ...", "We are not
    responsible for ...") is its own kind, not a prohibition; the room a term leaves its holder (``discretion``); and
    the codes it brings in by reference (``incorporated_standards``). A sentence the grammar left unread that releases
    a party or gives one room is read as a term too, so the reading carries every exemption and discretion."""
    from jason.community.discretion import discretion_of
    from jason.community.exemptions import clauses, exemption_of
    from jason.community.consent import consent_of
    from jason.community.incorporated_standards import incorporated, label
    from jason.community.warranties import warranties_of

    def qualified(t: ContractTerm) -> ContractTerm:
        changes: dict[str, Any] = {}
        ex = exemption_of(t.quote)
        if ex is not None:
            parts = clauses(t.quote)
            rest = [c for c in parts if exemption_of(c) is None]
            if not any(_BINDS.search(c) for c in rest):
                changes.update(kind=TermKind.EXEMPTION, exemption=ex.kind.value,
                               note="; ".join(n for n in (t.note, EXEMPTION_READING) if n))
                if t.party is Party.UNSTATED and ex.holder_words:
                    changes["party"] = parties.party_of(ex.holder_words)
                    changes["party_words"] = ex.holder_words
        room = discretion_of(t.quote)
        if room is not None:
            changes.update(discretion=room.degree.value, discretion_over=room.over)
            if t.party is Party.UNSTATED and room.holder_words and "party" not in changes:
                who = parties.party_of(room.holder_words)
                if re.match(r"(?:either|each|both|any)\s+part(?:y|ies)|(?:the\s+)?parties\b", room.holder_words, re.I):
                    who = Party.EITHER
                changes.update(party=who, party_words=room.holder_words)
        found = incorporated(t.quote)
        if found:
            changes["standards"] = tuple(dict.fromkeys(label(s) for s in found))
        # A warranty the term gives: its period, and a written warranty promised is a deliverable ("EHS will provide a
        # written warranty of five (5) years").
        given = [w for w in warranties_of(t.quote) if w.period_months or w.deliverable]
        if given and t.kind is not TermKind.EXEMPTION:
            changes["warranty_months"] = next((w.period_months for w in given if w.period_months), 0)
            if any(w.deliverable for w in given) and t.party is Party.COUNTERPARTY:
                changes["deliverable"] = True
        gate = consent_of(t.quote)
        if gate is not None:
            who = parties.party_of(gate.holder_words) if gate.holder_words else Party.UNSTATED
            changes["consent"] = who.value if who is not Party.UNSTATED else gate.holder_words
        return dc_replace(t, **changes) if changes else t

    terms = [qualified(t) for t in out]
    for sec in sections:
        for s, e in sentences(text[sec.start:sec.end]):
            s, e = sec.start + s, sec.start + e
            if any(t.start < e and s < t.end for t in terms):
                continue
            quote = text[s:e]
            if len(quote.split()) < 4:
                continue
            ex, room = exemption_of(quote), discretion_of(quote)
            if ex is None and room is None:
                continue
            kind = TermKind.PERMISSION if re.search(r"\bmay\b", quote, re.I) else TermKind.STATEMENT
            term = ContractTerm(source=source, section=sec.number, caption=sec.caption, start=s, end=e, quote=quote,
                                kind=kind, party=Party.UNSTATED, topic=topic_of(sec.caption, quote),
                                deadline=find_deadline(quote), conditions=find_conditions(quote))
            terms.append(qualified(_particulars(term, text, fire=fire)))
    return sorted(terms, key=lambda t: (t.start, t.end))


# The subject runs to "will" without a sentence's end; a company suffix's period ("Example Holdings Inc. dba ...") is
# not one.
_WILL = re.compile(r"^(?P<subj>(?:[^.;:]|(?<=\bInc|\bLtd|\bLLC)\.|(?<=\bCo)\.|(?<=\bCorp)\.){1,160}?)\s+will\s+(?P<neg>not\s+)?(?!be\s+required\b)(?P<verb>[a-z]+)", re.I)
_NOT_A_PROMISE = re.compile(r"^(?:be|have\s+been|likely|probably|result|cause|occur|vary)\b", re.I)


def _will_term(sentence: str, parties: PartyTerms) -> tuple[TermKind, Party, str] | None:
    """A contract's "will" sentence as a promise: "<party> will deliver ..." is a duty, "<party> will not ..." a
    prohibition, when the subject is one of the parties ("Contractor", "we", "the Association", a firm's short name).
    A subject that is not a party ("This proposal will expire", "Prices will vary") makes no promise. Governing documents
    keep the grammar's rule ("will be required" only)."""
    # A sentence that opens its section carries the section's number ("1.1 Manager will ..."): the number is not the subject.
    words = re.sub(r"^(?:\d{1,2}(?:\.\d{1,2})*\.?|\(?[a-z]\)|[A-Z]\.)\s+", "", " ".join(sentence.split()))
    m = _WILL.match(words)
    if not m:
        return None
    if m.group("verb").lower() == "be":
        # "will be pressure washed", "will be removed": in the counterparty's own form, the work it offers, when no party
        # is the subject ("All surfaces to be painted will be pressure washed"). Elsewhere a "will be" states, not promises.
        after = words[m.end():].split()
        subj = re.split(r",\s*", m.group("subj"))[-1]
        # The subject is no party ("Debris will be removed"), or the counterparty's service ("All inspections will be
        # performed"). A party as the subject ("Contractor will be paid") is the one acted on, not a promisor.
        service = parties.role_in(subj) in _SERVICE_ROLES
        if (parties.vendor_form and after and re.match(r"^\w+(?:ed|en)$", after[0], re.I)
                and (service or parties.party_of(subj) is Party.UNSTATED)):
            return (TermKind.PROHIBITION if m.group("neg") else TermKind.DUTY), Party.COUNTERPARTY, PASSIVE_READING
        return None
    if _NOT_A_PROMISE.match(m.group("verb")):
        return None
    subject = m.group("subj")
    # The subject is the last clause before "will" ("Upon request, Contractor will ...", "If ..., we will ..."); a
    # comma between the subject and its verb ("Manager, will deliver ...") leaves the clause before it.
    clauses = [c for c in re.split(r",\s*", subject) if c.strip()]
    subject = clauses[-1] if clauses else subject
    party = parties.party_of(subject)
    if party not in (Party.ASSOCIATION, Party.COUNTERPARTY, Party.EITHER):
        return None
    return (TermKind.PROHIBITION if m.group("neg") else TermKind.DUTY), party, subject.strip()


# A name that is a service the contract names, not its party: an arbitration or mediation provider, a bond's surety.
_NOT_COUNTERPARTY = re.compile(r"dispute\s+resolution|arbitration|mediation|\bJAMS\b|surety|fidelity|association|\bHOA\b|"
                               r"benefit|non-?profit|mutual|california\s+corporation", re.I)
_SERVICE_BEFORE = re.compile(r"(?:conducted|administered|provided|issued|underwritten)\s+by\s*$|(?:arbitration|mediation)\b[^.]{0,40}$",
                             re.I)
# A form's labeled blank ("Manager and Branch: Example, LLC", "Contractor: Example, Inc."): the label, its colon, then
# the name on the same or the next line.
_LABELED = re.compile(r"\b(?:Manager(?:\s+and\s+Branch)?|Contractor|Vendor|Consultant|Provider|Company\s+Name)\s*:\s*\n?\s*"
                      r"([A-Z][\w&.,'’\- ]{1,70}?\b(?:Inc|LLC|L\.L\.C|Corp|Corporation|Company|LLP|Ltd)\b\.?)")


def _name_candidate(text: str, names: dict[str, str]) -> str:
    """The counterparty's name, best evidence first:

    1. the holder of a license the document prints (a license is the firm's identity; ``jason.community.licenses``);
    2. a defined party's company name ("Example, Inc. (hereinafter "MANAGER")");
    3. a form's labeled blank ("Contractor: Example, Inc.");
    4. the letterhead: the first business name in the opening, skipping the association, a customer named after "Bill
       To" or "c/o", form words ("Initial", "President"), and a service the contract names (an arbitration provider).
    """
    from jason.community.licenses import Board, _names, find_licenses

    text = text or ""
    holders = [m.holder for m in find_licenses(text[:40_000]) if m.holder
               and m.board not in (Board.NOTARY, Board.CERTIFICATION) and not _NOT_COUNTERPARTY.search(m.holder)]
    if holders:
        return max(set(holders), key=holders.count)
    for name in names.values():
        if _COMPANY.search(name) and not _NOT_COUNTERPARTY.search(name):
            return name
    label = _LABELED.search(text[:20_000])
    if label and not _NOT_COUNTERPARTY.search(label.group(1)):
        return label.group(1).strip()
    for m, name in _names(text, 0, min(len(text), 20_000)):
        if _NOT_COUNTERPARTY.search(name) or _SERVICE_BEFORE.search(text[max(0, m.start() - 60):m.start()]):
            continue
        return name
    from jason.community.licenses import letterhead_line

    return letterhead_line(text[:3000])


def mark_notices(terms: list[ContractTerm], text: str) -> tuple[list[ContractTerm], list[tuple[Any, int, int]]]:
    """Terms inside a notice the law makes the contract print (``statutory_notices``: the mechanics lien warning, the
    CSLB information, the right to cancel) go on the statutory notice topic. They are the Legislature's words, not
    either party's promise, so none is a duty or a deliverable. ``text`` is the text the terms' offsets are into.
    Returns the terms and the notices found."""
    from jason.community.statutory_notices import find_notices

    notices = find_notices(text)
    out = []
    for t in terms:
        inside = next((n for n, s, e in notices if s <= t.start < e), None)
        if inside is None:
            out.append(t)
            continue
        out.append(dc_replace(t, topic=Topic.STATUTORY_NOTICE, kind=TermKind.STATEMENT, deliverable=False,
                              note=(t.note + "; " if t.note else "") + f"{inside.title} ({inside.authority})"))
    return out, notices


def counterparty_name(text: str, parties: PartyTerms) -> str:
    """The counterparty's name as the contract prints it (``_name_candidate``); "" when none shows."""
    return _name_candidate(text, dict(parties.names))


# --- Findings ---------------------------------------------------------------------------------------------------------

def _q(term: ContractTerm, n: int = 160) -> str:
    q = " ".join(term.quote.split())
    return q if len(q) <= n else q[: n - 3].rstrip() + "..."


def _where(term: ContractTerm) -> str:
    return f"section {term.section}" if term.section else "the opening"


def findings(terms: Iterable[ContractTerm]) -> list[Finding]:
    """Leads a person reads beside the statutes (docs/contracts.md). None of them decides anything."""
    terms = list(terms)
    out: list[Finding] = []
    by_topic: dict[Topic, list[ContractTerm]] = {}
    for t in terms:
        by_topic.setdefault(t.topic, []).append(t)

    for t in terms:
        if t.window_days:
            lo, hi = t.window_days
            out.append(Finding("notice-window", f"{_where(t)}: a notice window with two edges, at least {lo} and no more "
                               f"than {hi} before the event; a notice outside either edge may not count: \"{_q(t)}\"",
                               Severity.CHECK))
    notices = [t for t in terms if t.delivery and t.topic in (Topic.NOTICE, Topic.TERMINATION, Topic.BREACH,
                                                               Topic.RENEWAL)]
    for t in notices:
        out.append(Finding("notice-delivery", f"{_where(t)}: names the delivery {', '.join(t.delivery)}: \"{_q(t)}\"",
                           Severity.INFO))
    if not by_topic.get(Topic.DISPUTE):
        out.append(Finding("no-dispute-clause", "no mediation or arbitration clause was read: a dispute goes to court",
                           Severity.INFO))
    for t in by_topic.get(Topic.DISPUTE, []):
        if re.search(r"binding\s+arbitration|decided\s+by\s+(?:binding\s+)?arbitration|submit\w*\s+to\s+arbitration|"
                     r"settled\s+.{0,60}arbitration", t.quote, re.I):
            out.append(Finding("arbitration", f"{_where(t)}: an agreement to arbitrate: \"{_q(t)}\"", Severity.INFO,
                               "CCP 1281"))
            break
    for t in terms:
        # A change the counterparty may make alone: to the price, fees, or scope at its sole discretion, or to those,
        # the terms, or the term itself at will ("may terminate ... with or without cause"). Its sole discretion over
        # how it ends or limits something ("at our option ... repairing or replacing") is a remedy, not a change.
        if t.party is Party.COUNTERPARTY and (
                (t.discretion == "unfettered" and t.discretion_over in ("price", "fees", "scope"))
                or (t.discretion == "one-side change"
                    and t.discretion_over in ("price", "fees", "scope", "terms", "termination"))):
            out.append(Finding("vendor-one-side-change" if t.discretion == "one-side change" else "vendor-unfettered",
                               f"{_where(t)}: the counterparty may " + ("end the agreement" if t.discretion_over ==
                                                                        "termination" else f"change the {t.discretion_over}")
                               + f" on its own: \"{_q(t)}\"",
                               Severity.CHECK))
        elif t.discretion == "effort standard":
            out.append(Finding("effort-standard", f"{_where(t)}: an effort, not a result, is promised: \"{_q(t)}\"",
                               Severity.INFO))
        if t.kind is TermKind.EXEMPTION and t.party is Party.COUNTERPARTY:
            out.append(Finding("counterparty-exemption", f"{_where(t)}: the counterparty is released ({t.exemption}): "
                               f"\"{_q(t)}\"", Severity.INFO))
    standards = list(dict.fromkeys(x for t in terms for x in t.standards))
    if standards:
        out.append(Finding("incorporates-standard", f"brings in by reference: {', '.join(standards)}; the work is "
                           "measured against them, so the edition named matters", Severity.INFO))
    for t in by_topic.get(Topic.LIMITATIONS, []):
        out.append(Finding("shortened-limitations", f"{_where(t)}: sets its own time to bring a claim: \"{_q(t)}\"; "
                           "whether it shortens the statute's four years is a question for counsel", Severity.CHECK,
                           "CCP 337"))
    for t in by_topic.get(Topic.ATTORNEY_FEES, [])[:1]:
        out.append(Finding("fee-shifting", f"{_where(t)}: attorney fees go to a party; the statute makes the clause run "
                           f"both ways: \"{_q(t)}\"", Severity.INFO, "CIV 1717"))
    ind = by_topic.get(Topic.INDEMNITY, [])
    givers = {t.party for t in ind if t.kind in (TermKind.DUTY, TermKind.STATEMENT)}
    if Party.ASSOCIATION in givers and Party.COUNTERPARTY not in givers:
        out.append(Finding("one-way-indemnity", "only the association indemnifies in the terms read; the counterparty "
                           "gives none", Severity.CHECK))
    for t in by_topic.get(Topic.LIABILITY, []):
        if t.amounts or re.search(r"shall\s+not\s+exceed|aggregate\s+liability|exclusive\s+remedy", t.quote, re.I):
            out.append(Finding("liability-cap", f"{_where(t)}: caps or limits what the counterparty owes: \"{_q(t)}\"",
                               Severity.CHECK, "CIV 1668"))
            break
    for t in terms:
        if re.search(r"liquidated\s+damages", t.quote, re.I):
            out.append(Finding("liquidated-damages", f"{_where(t)}: a sum fixed in advance: \"{_q(t)}\"", Severity.CHECK,
                               "CIV 1671"))
        if t.topic in (Topic.FUNDS, Topic.SPENDING) and re.search(r"without\s+regard\s+to\s+(?:the\s+)?(?:dollar\s+)?amount|"
                                                                    r"transfers?\b[^.]{0,80}\bas\s+needed", t.quote, re.I):
            out.append(Finding("transfers-without-limit", f"{_where(t)}: moves funds between the association's accounts "
                               f"with no limit: \"{_q(t)}\"", Severity.CHECK, "CIV 5380(b)(6)"))
        if re.search(r"subject\s+to\s+change\s+from\s+time\s+to\s+time\s+by|then-?current|at\s+(?:management|manager)'?s?"
                     r"\s+discretion|as\s+amended\)", t.quote, re.I) and t.topic in (Topic.ESCALATION, Topic.FEES,
                                                                                      Topic.PAYMENT, Topic.AMENDMENT,
                                                                                      Topic.SCOPE, Topic.SPENDING):
            out.append(Finding("one-side-may-change", f"{_where(t)}: the counterparty may change the terms or prices "
                               f"without the board signing: \"{_q(t)}\"", Severity.CHECK))
    seen: set[tuple[str, str]] = set()
    unique: list[Finding] = []
    for f in out:
        key = (f.code, f.message)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def deliverables(terms: Iterable[ContractTerm]) -> list[ContractTerm]:
    return [t for t in terms if t.deliverable]


__all__ = ["TermKind", "Party", "Topic", "TOPIC_RULES", "PartyTerms", "Section", "ContractTerm", "defined_parties",
           "split_sections", "read_terms", "topic_of", "window_of", "deliveries", "amounts", "percents", "findings",
           "deliverables"]
