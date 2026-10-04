"""Correspondence: what a letter, notice, or handout to or from the association carries.

The ``correspondence`` kind is whatever the association sends or receives that is not a legal letter, a bill, a
statement, or a meeting record: a bank's letter about an account, the association's instructions to a buyer or to
escrow, its contact sheet and welcome packet, a newsletter or a flyer to the members, a vendor's certified record, and a
third party's guide the association passed along. The models read the same record from each (``CorrespondenceRecord``):

- the form (``Form``): a letter, a notice to the members, a handout, a certified record, a publication;
- who wrote it and to whom, as organizations and roles (``Role``), never a private person's name, and the direction;
- the subject, the date, and the signature's closing and role;
- what it refers to: the development's street addresses and their buildings, accounts by their last four digits, Civil
  Code sections, governing-document sections, dates and the deadlines it sets, and amounts in cents;
- whether it asks for a response and by when, and what it encloses or links;
- the requests the law shapes (``Request``).

The sender is the specification's counterparty when its letterhead names one (``Mystique.senders()``, read with
``jason.community.sources.resolve``); the association itself when the text speaks for it (its name in the letterhead or
footer, "the HOA", "we"); an owner only by role.

Findings are for what the law shapes, and a stated deadline:

- a response deadline the letter states (INFO);
- a member's request for association records: current-year records within 10 business days of receipt, the prior two
  fiscal years within 30 calendar days, at no more than the direct and actual cost of copying and mailing
  (CIV 5205(f), 5210(b));
- a request for internal dispute resolution: the association must take part and may not refuse to meet and confer, and
  may not charge for it (5910(c), (g); 5915(b)(2));
- a Request for Resolution: 30 days after service to accept, or it is deemed rejected, and served on a member it carries
  a copy of the ADR article (5935(a), (c));
- a notice of a disciplinary hearing: at least 10 days before, with the date, time, and place, the violation, and the
  right to attend (5855(a), (b)); a notice of decision within 14 days of the action (5855(f));
- an owner's request to meet about a payment plan: within 45 days in executive session (5665(b));
- the resale documents: within 10 days of a written request, at actual cost, estimated first, with no extra charge for
  electronic delivery (4530(a), (b));
- a letter about a reserve account the specification names: withdrawals take two signers and reserve money goes only to
  reserve components (5510), and the letter is a reserve record (5200(a)(7)).

A finding is a lead: the text cannot show when a letter was received, served, or answered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Any, ClassVar

from jason.community.document_models import DocumentModel, Finding, ModelContext, Severity, cents, dates_in, register, squash
from jason.community.sources import SourceKind, fold, resolve
from jason.community.symbols import Building, DocumentKind

from .governing_shared import ExplainsMissing, number_word
from .legal_shared import building_of, civil_code_citations, site_addresses

RECORDS_CURRENT_BUSINESS_DAYS = 10   # CIV 5210(b)(1)
RECORDS_PRIOR_DAYS = 30              # CIV 5210(b)(2)
ADR_RESPONSE_DAYS = 30               # CIV 5935(c)
HEARING_NOTICE_DAYS = 10             # CIV 5855(a)
DECISION_NOTICE_DAYS = 14            # CIV 5855(f)
PAYMENT_PLAN_MEETING_DAYS = 45       # CIV 5665(b)
RESALE_DOCUMENT_DAYS = 10            # CIV 4530(a)(1)


class Form(Enum):
    LETTER = "letter"                        # a salutation or a closing
    NOTICE = "notice"                        # an announcement or a newsletter to the members
    HANDOUT = "handout"                      # the association's instructions, checklist, contact sheet, welcome packet
    CERTIFIED_RECORD = "certified record"    # a business record with its custodian's declaration
    PUBLICATION = "publication"              # a third party's guide or manual excerpt


class Role(Enum):
    ASSOCIATION = "association"
    BOARD = "board"
    MANAGER = "manager"
    OWNER = "owner"
    MEMBERS = "members"
    BUYER = "buyer"
    SELLER = "seller"
    ESCROW = "escrow or title company"
    LENDER = "lender"
    BANK = "bank"
    INSURER = "insurer"
    VENDOR = "vendor"
    UTILITY = "utility"
    AGENCY = "government agency"
    COUNSEL = "counsel"
    ACCOUNTANT = "accountant"
    PLATFORM = "service platform"
    OTHER_ASSOCIATION = "another association"
    UNKNOWN = "unknown"


class Direction(Enum):
    INBOUND = "to the association"
    OUTBOUND = "from the association"
    OTHER = "neither"                        # a publication, or a record about the association


class Request(Enum):
    RECORDS = "association records (CIV 5205)"
    IDR = "internal dispute resolution (CIV 5910)"
    ADR = "request for resolution (CIV 5935)"
    HEARING = "notice of a disciplinary hearing (CIV 5855)"
    DECISION = "notice of a disciplinary decision (CIV 5855(f))"
    PAYMENT_PLAN = "payment plan (CIV 5665)"
    RESALE_DOCUMENTS = "resale documents (CIV 4525, 4530)"


@dataclass(frozen=True)
class Deadline:
    what: str                                # the words before the date ("will mature on")
    on: date


@dataclass(frozen=True)
class Amount:
    label: str
    cents: int


@dataclass
class CorrespondenceRecord:
    form: Form = Form.LETTER
    title: str = ""
    subject: str = ""
    dated: date | None = None
    sender: str = ""                         # an organization, or a role ("an owner"); never a private person's name
    sender_role: Role = Role.UNKNOWN
    recipient: str = ""
    recipient_role: Role = Role.UNKNOWN
    direction: Direction = Direction.OTHER
    addresses: tuple[str, ...] = ()          # the development's street addresses the text names
    buildings: tuple[Building, ...] = ()
    accounts: tuple[str, ...] = ()           # last four digits ("7476")
    statutes: tuple[str, ...] = ()           # "CIV 4525"
    document_sections: tuple[str, ...] = ()  # "CC&Rs 4.15", "Bylaws 8.5"
    dates: tuple[date, ...] = ()
    deadlines: tuple[Deadline, ...] = ()
    amounts: tuple[Amount, ...] = ()
    requests: tuple[Request, ...] = ()
    response_requested: bool = False
    respond_by: date | None = None
    enclosures: tuple[str, ...] = ()
    closing: str = ""                        # "Sincerely"
    signer_role: str = ""                    # "Customer Service", "Board of Directors", "Custodian of Records"
    adr_article_included: bool = False       # a copy of CIV 5925 and following
    hearing_on: date | None = None           # the hearing a notice sets
    hearing_elements: tuple[str, ...] = ()   # what a hearing notice states: date, time, place, violation, right to attend


_KIND_ROLE = {SourceKind.GOVERNMENT: Role.AGENCY, SourceKind.UTILITY: Role.UTILITY, SourceKind.INSURER: Role.INSURER,
              SourceKind.BANK: Role.BANK, SourceKind.VENDOR: Role.VENDOR, SourceKind.TITLE_ESCROW: Role.ESCROW,
              SourceKind.LAW_FIRM: Role.COUNSEL, SourceKind.MANAGER: Role.MANAGER, SourceKind.ACCOUNTANT: Role.ACCOUNTANT,
              SourceKind.OTHER_ASSOCIATION: Role.OTHER_ASSOCIATION, SourceKind.OWNER: Role.OWNER, SourceKind.PLATFORM: Role.PLATFORM}
_ASSOCIATION_SIDE = (Role.ASSOCIATION, Role.BOARD)

# Publishers a guide names without a letterhead the specification knows. Order matters: the first that matches wins.
_PUBLISHERS: tuple[tuple[str, Role, str], ...] = (
    ("National Flood Insurance Program (FEMA)", Role.AGENCY, r"National\s+Flood\s+Insurance\s+Program|\bNFIP\b|\bFEMA\b"),
    ("Department of Real Estate", Role.AGENCY, r"Department\s+of\s+Real\s+Estate|\bDRE\b"),
)

_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
_DATE = rf"(?:{_MONTH}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}})"
_DATE_LINE = re.compile(rf"^\s*(?:Date[d]?\s*:?\s*)?({_DATE})\s*$", re.M | re.I)
_SALUTATION = re.compile(r"^\s*Dear\s+([^\n,:]{2,80})[,:]?\s*$", re.M)
_CLOSING = re.compile(r"^\s*(Sincerely(?:\s+yours)?|Very\s+truly\s+yours|Respectfully(?:\s+submitted)?|Best\s+regards|Kind\s+regards|Regards|"
                      r"Thank\s+you),?\s*$", re.M | re.I)
_SUBJECT = re.compile(r"^\s*(?:RE|Re|Subject|SUBJECT)\s*:\s*(.{3,160}?)\s*$", re.M)
_TRIGGER = re.compile(r"(?:\bby|\bbefore|\buntil|\bthrough|no\s+later\s+than|deadline(?:\s+is)?|\bdue(?:\s+(?:on|by))?|expires?(?:\s+on)?|"
                      r"mature\s+on|matures?\s+on|\bends?|renew\s+on|maturity\s+date\s+of|on\s+or\s+before|ready\s+by|"
                      r"(?:hearing|meeting)\s+(?:on|is\s+scheduled\s+for|will\s+be\s+held\s+on))\s*:?\s*$", re.I)
_ACT = re.compile(r"respond|reply|return|submit|contact|pay|changes?|request|RSVP|decid|sign|deliver|provide|ready|register|accept|"
                  r"cure|correct", re.I)
_ACCOUNT = re.compile(r"(?:ending\s+(?:in\s+)?|account\s+(?:no\.?|number|#)\s*:?\s*[xX*.•]*|[xX*•]{2,}|\.{3})(\d{4})\b", re.I)
_SECTION = re.compile(r"(CC&Rs?|Bylaws|Declaration)\s*(?:§+|Sections?|Art(?:icle)?\.?)\s*(\d+(?:\.\d+)*(?:\s?\([a-z0-9]+\))*)|"
                      r"§+\s*(\d+\.\d+(?:\.\d+)*(?:\s?\([a-z0-9]+\))*)\s+of\s+the\s+(CC&Rs?|Bylaws|Declaration)", re.I)
_PDF = re.compile(r"([A-Z][\w .&'()-]{2,70}?\.pdf)\b")
_ENCLOSURE = re.compile(r"^\s*(?:Enclosures?|Attachments?|Encl\.?)\s*:\s*(.+)$", re.M | re.I)
_ASKS = re.compile(r"please\s+(?:respond|reply|contact|call|let\s+(?:us|the\s+\w+)\s+know|confirm|submit|return|complete|sign|provide|remit|pay|"
                   r"visit|email|notify)|(?:respond|reply)\s+(?:by|within|no\s+later)|\bRSVP\b|must\s+(?:be\s+)?(?:received|returned|submitted)|"
                   r"at\s+your\s+earliest|you\s+(?:must|need\s+to)\s+(?:respond|contact|submit|return|pay|provide)", re.I)
_REQUEST_PATTERNS: tuple[tuple[Request, str], ...] = (
    (Request.RECORDS, r"\b(?:inspect|inspection\s+of|cop(?:y|ies)\s+of)\b[^.]{0,80}\b(?:association(?:.s)?\s+)?records\b|\brecords?\s+request\b|"
                      r"Civil\s+Code\s+(?:section\s+|§\s*)?52(?:05|10)\b|Civ\.?\s*§?\s*52(?:05|10)\b"),
    (Request.IDR, r"internal\s+dispute\s+resolution|meet\s+and\s+confer|\bIDR\b"),
    (Request.ADR, r"Request\s+for\s+Resolution|alternative\s+dispute\s+resolution"),
    (Request.HEARING, r"Notice\s+of\s+(?:Board\s+)?Hearing|(?:hearing|meeting)\s+to\s+consider[^.]{0,80}(?:disciplin|violation|fine|penalt)"),
    (Request.DECISION, r"Notice\s+of\s+(?:Board\s+)?Decision|Board\s+(?:has\s+)?(?:decided|voted)\s+to\s+impose"),
    (Request.PAYMENT_PLAN, r"payment\s+plan"),
    (Request.RESALE_DOCUMENTS, r"\b4525\b|resale\s+(?:documents|disclosures?|certificate|package)|transfer\s+fee"),
)
_HEARING_ELEMENTS: tuple[tuple[str, str], ...] = (
    ("date", _DATE), ("time", r"\b\d{1,2}(?::\d\d)?\s*[ap]\.?m\.?"), ("place", r"\bZoom\b|\blocated\s+at\b|\bplace\b|\blocation\b|\bheld\s+at\b"),
    ("violation", r"violat|damage"), ("right to attend", r"right\s+to\s+attend|may\s+(?:attend|address)"),
)


# The association: its name as the specification gives it, or any "<Name> Community Association" the text prints.

def _association(context: ModelContext) -> str:
    name = str(getattr(context.community, "corporate_name", "") or "")
    return r"\s+".join(re.escape(w) for w in name.split()) if name else r"[A-Z][A-Za-z]+\s+(?:Community|Homeowners|Owners)\s+Association"


def _association_name(context: ModelContext, text: str) -> str:
    name = str(getattr(context.community, "corporate_name", "") or "")
    if name:
        return name
    hit = re.search(_association(context), text)
    return " ".join(hit.group(0).split()).upper() if hit else "the association"


def _speaks_for_association(text: str, association: str) -> bool:
    """The association's letterhead or footer, or its voice ("the HOA", "we" beside "the Association")."""
    head = "\n".join(ln for ln in text.splitlines()[:12] if ln.strip() and not ln.startswith(("#", "- ")))
    if re.search(association, head, re.I) or re.search(rf"^\s*{association}\s+-\s+\S", text, re.M | re.I):
        return True
    voice = re.search(r"\bthe\s+HOA\b|\bthe\s+Association\b|" + association, text, re.I)
    return bool(voice and re.search(r"\b(?:we|our|us)\b", text, re.I))


def _addressed_to_association(text: str, association: str) -> bool:
    hit = _SALUTATION.search(text)
    return bool(hit and re.search(rf"{association}|\bBoard\b|\bDirectors\b|\bManager\b", hit.group(1), re.I))


def _named(text: str, senders: tuple) -> Any:
    """The counterparty whose words the text repeats most, anywhere (a guide's publisher is on its last page)."""
    folded = fold(text)
    best, count = None, 0
    for known in senders:
        hits = sum(folded.count(fold(w)) for w in known.words)
        if hits > count:
            best, count = known, hits
    return best


def _senders(context: ModelContext) -> tuple:
    fn = getattr(context.community, "senders", None)
    try:
        return tuple(fn()) if callable(fn) else ()
    except Exception:  # a spec without the fact
        return ()


def _own_word(context: ModelContext) -> str:
    name = str(getattr(context.community, "corporate_name", "") or "")
    return re.escape(name.split()[0]) if name else ""


def _org_line(text: str, word: str) -> str:
    for line in text[:1500].splitlines():
        if word and fold(word) in fold(line) and len(line.strip()) <= 80:
            return " ".join(line.split()).strip(" ,.")
    return ""


def _letterhead(text: str) -> str:
    """Where a letter names its sender: above the salutation and from the closing on. A body's words ("bank statements")
    are not a sender. Without a salutation, the whole text."""
    hit = _SALUTATION.search(text)
    if not hit:
        return text
    closing = _CLOSING.search(text, hit.end())
    return text[: hit.start()] + "\n" + (text[closing.start():] if closing else text[-600:])


def _sender(text: str, context: ModelContext, form: Form, association: str) -> tuple[str, Role]:
    senders = _senders(context)
    own = _speaks_for_association(text, association) and not _addressed_to_association(text, association)
    own_role = Role.BOARD if re.search(r"^\s*Board\s+of\s+Directors\s*$", text[-600:], re.M) else Role.ASSOCIATION
    if own and form in (Form.NOTICE, Form.HANDOUT):
        return _association_name(context, text), own_role
    if form is Form.PUBLICATION:
        known = _named(text, senders)
        if known is not None:
            return known.name, _KIND_ROLE.get(known.kind, Role.UNKNOWN)
        for name, role, pattern in _PUBLISHERS:
            if re.search(pattern, text):
                return name, role
    known, kind, _, word = resolve("", _letterhead(text), senders, own_name=_own_word(context))
    if known is not None:
        return known.name, _KIND_ROLE.get(known.kind, Role.UNKNOWN)
    if kind is not SourceKind.UNKNOWN:
        return _org_line(text, word) or kind.value, _KIND_ROLE.get(kind, Role.UNKNOWN)
    if own:
        return _association_name(context, text), own_role
    if re.search(r"\b(?:my|our)\s+(?:unit|home|condo|property|garage|balcony)\b|\bI\s+(?:own|live|reside)\b|\bhomeowner\s+at\b", text, re.I):
        return "an owner", Role.OWNER
    return "", Role.UNKNOWN


_AUDIENCES: tuple[tuple[Role, str, str], ...] = (
    (Role.BUYER, "the buyer", r"INSTRUCTIONS\s+FOR\s+BUYER|\bWelcome\s+to\b|new\s+owners?"),
    (Role.SELLER, "the seller", r"INSTRUCTIONS\s+FOR\s+SELLER"),
    (Role.ESCROW, "escrow", r"INSTRUCTIONS\s+(?:FOR|TO)\s+ESCROW"),
    (Role.LENDER, "the lender", r"INSTRUCTIONS\s+FOR\s+LENDER"),
)


def _recipient(text: str, context: ModelContext, form: Form, sender_role: Role, association: str, title: str) -> tuple[str, Role]:
    hit = _SALUTATION.search(text)
    if hit:
        who = hit.group(1)
        if re.search(association, who, re.I):
            return _association_name(context, text), Role.ASSOCIATION
        if re.search(r"\bBoard\b|\bDirectors\b", who, re.I):
            return "the board", Role.BOARD
        if re.search(r"\bManager\b|Management", who, re.I):
            return "the manager", Role.MANAGER
        if re.search(r"\bMembers?\b|Homeowners\b|Owners\b|Residents?\b|Neighbors?\b", who, re.I):
            return "the members", Role.MEMBERS
        if re.search(r"\bHomeowner\b|\bOwner\b", who, re.I) or (sender_role in _ASSOCIATION_SIDE + (Role.MANAGER, Role.COUNSEL)
                                                                and re.search(r"\byour\s+(?:unit|home|property|account)\b", text, re.I)):
            return "an owner", Role.OWNER
        if re.search(r"\bEscrow\b|Title", who, re.I):
            return "escrow", Role.ESCROW
        return "the addressee", Role.UNKNOWN
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith(("#", "- "))]
    head = "\n".join([title, *lines[:3]])
    for role, label, pattern in _AUDIENCES:
        if re.search(pattern, head, re.I):
            return label, role
    if form in (Form.NOTICE, Form.HANDOUT) and sender_role in _ASSOCIATION_SIDE:
        return "owners and residents", Role.MEMBERS
    if form is Form.CERTIFIED_RECORD and re.search(association, text, re.I):
        return _association_name(context, text), Role.ASSOCIATION
    return "", Role.UNKNOWN


def _direction(sender_role: Role, recipient_role: Role) -> Direction:
    if sender_role in _ASSOCIATION_SIDE or (sender_role is Role.MANAGER and recipient_role not in _ASSOCIATION_SIDE + (Role.UNKNOWN,)):
        return Direction.OUTBOUND
    if recipient_role in _ASSOCIATION_SIDE + (Role.MANAGER,):
        return Direction.INBOUND
    return Direction.OTHER


def _title(text: str, association: str) -> str:
    footer = re.search(rf"^\s*{association}\s+-\s+(.{{3,80}}?)\s*$", text, re.M | re.I)
    if footer:
        return " ".join(footer.group(1).split())
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith(("#", "- ")) and not re.fullmatch(r"[•|_\W]+", ln.strip())]
    section = re.search(r"^\s*(Section\s+[A-Z]\.\s+[^\n]{3,60}?)\s*$", text, re.M)
    if section:
        return " ".join(section.group(1).split())
    parts: list[str] = []
    for ln in lines[:8]:
        if re.fullmatch(association, " ".join(ln.split()), re.I) or re.match(r"(?:Dear|To|From)\b", ln):
            if parts:
                break
            continue
        if len(ln) > (90 if not parts else 60) or re.search(r"\d{3}[-.)\s]\d{3}[-.\s]\d{4}|@|https?://|\$\s?\d", ln):
            break
        parts.append(ln)
        if len(" ".join(parts)) > 50:
            break
    return " ".join(" ".join(parts).split())[:120]


def _record_subject(text: str) -> str:
    """A certified record's heading ("Investigative Summary"), or its report number."""
    hit = re.search(r"^\s*((?:Investigative\s+)?Summary|[A-Z][A-Za-z ]{2,40}\s(?:Report|Summary|Record|Result|Log))\s*$", text, re.M)
    if hit:
        return " ".join(hit.group(1).split())
    hit = re.search(r"\bReport\s+(?:ID|No\.?|Number)\s*:?\s*(\S{4,60})", text, re.I)
    return f"Report {hit.group(1)}" if hit else ""


def _subject(text: str, title: str) -> str:
    hit = _SUBJECT.search(text)
    if hit:
        return " ".join(hit.group(1).split())
    hit = re.search(r"^\s*(Important\s*:\s*.{5,140}?)\s*$", text, re.M)
    if hit:
        return " ".join(hit.group(1).split())
    return title


def _dated(text: str, form: Form) -> date | None:
    hit = re.search(rf"Date\s+(?:Created|Issued|Printed)\s*:\s*({_DATE})", text, re.I)
    if hit:
        return (dates_in(hit.group(1)) or [None])[0]
    if form in (Form.LETTER, Form.CERTIFIED_RECORD):
        lines = _DATE_LINE.findall(text)
        found = [d for d in (dates_in(x) for x in lines) if d]
        if found:
            return found[0][0]
    hit = re.search(rf"(?:Updated|Revised|As\s+of|Issued)\s*:?\s*({_DATE})", text, re.I)
    return (dates_in(hit.group(1)) or [None])[0] if hit else None


def _deadlines(flat: str) -> tuple[Deadline, ...]:
    out: dict[date, Deadline] = {}
    for m in re.finditer(_DATE, flat, re.I):
        before = flat[max(0, m.start() - 90): m.start()]
        if not _TRIGGER.search(before):
            continue
        found = dates_in(m.group(0))
        if not found:
            continue
        clause = re.split(r"[.;:!?]\s|\n", before)[-1]
        what = " ".join(clause.split())[-80:].strip(" ,")
        out.setdefault(found[0], Deadline(what, found[0]))
    return tuple(sorted(out.values(), key=lambda d: d.on))


def _amounts(text: str) -> tuple[Amount, ...]:
    out: list[Amount] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        for m in re.finditer(r"\$\s?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d\d)?", line):
            value = cents(m.group(0))
            if value is None:
                continue
            label = line[: m.start()].strip(" :-–•\t")
            if not label and i:
                label = lines[i - 1].strip(" :-–•\t")
            label = " ".join(label.split())[-60:]
            if Amount(label, value) not in out:
                out.append(Amount(label, value))
    return tuple(out)


def _sections(flat: str) -> tuple[str, ...]:
    out: list[str] = []
    for m in _SECTION.finditer(flat):
        doc = (m.group(1) or m.group(4) or "").upper().replace("CC&R", "CC&Rs").replace("CC&RsS", "CC&Rs")
        doc = {"BYLAWS": "Bylaws", "DECLARATION": "Declaration"}.get(doc, doc)
        number = re.sub(r"\s", "", m.group(2) or m.group(3) or "")
        cite = f"{doc} {number}"
        if number and cite not in out:
            out.append(cite)
    return tuple(out)


def _within_days(flat: str, dated: date | None) -> date | None:
    """A response window stated as "within ten (10) days" from the letter's date."""
    hit = re.search(r"(?:respond|reply|contact|return|submit|pay)[^.]{0,80}within\s+([\w-]+(?:\s*\(\d+\))?)\s+(business\s+|calendar\s+)?days", flat, re.I)
    if not hit or dated is None:
        return None
    days = number_word(hit.group(1))
    if days is None:
        return None
    return add_business_days(dated, days) if (hit.group(2) or "").lower().startswith("business") else dated + timedelta(days=days)


def add_business_days(start: date, days: int) -> date:
    """``days`` weekdays after ``start``; holidays are not known here, so the date is the earliest the clock can run out."""
    d, left = start, days
    while left:
        d += timedelta(days=1)
        if d.weekday() < 5:
            left -= 1
    return d


def read_correspondence(text: str, context: ModelContext, form: Form) -> CorrespondenceRecord:
    association = _association(context)
    flat = squash(text)
    r = CorrespondenceRecord(form=form)
    r.title = _title(text, association)
    if form is Form.CERTIFIED_RECORD:
        r.title = _record_subject(text) or r.title
    r.subject = _subject(text, r.title)
    if form is Form.LETTER and r.subject:
        r.title = r.subject
    r.dated = _dated(text, form)
    r.sender, r.sender_role = _sender(text, context, form, association)
    r.recipient, r.recipient_role = _recipient(text, context, form, r.sender_role, association, r.title)
    r.direction = _direction(r.sender_role, r.recipient_role)
    r.addresses = site_addresses(text)
    r.buildings = tuple(dict.fromkeys(b for b in (building_of(context, a) for a in r.addresses) if b is not None))
    r.accounts = tuple(dict.fromkeys(_ACCOUNT.findall(flat)))
    r.statutes = civil_code_citations(flat)
    r.document_sections = _sections(flat)
    r.dates = tuple(dict.fromkeys(dates_in(flat)))
    r.deadlines = _deadlines(flat)
    r.amounts = _amounts(text)
    r.requests = tuple(q for q, pattern in _REQUEST_PATTERNS if re.search(pattern, flat, re.I))
    r.response_requested = bool(_ASKS.search(flat))
    acts = [d for d in r.deadlines if _ACT.search(d.what)]
    r.respond_by = _within_days(flat, r.dated) or (acts[-1].on if acts and r.response_requested else None)
    enclosed = [e.strip() for hit in _ENCLOSURE.findall(text) for e in re.split(r";|,\s(?=[A-Z])", hit) if e.strip()]
    r.enclosures = tuple(dict.fromkeys(enclosed + [" ".join(p.split()) for p in _PDF.findall(text)]))
    closing = _CLOSING.search(text)
    r.closing = " ".join(closing.group(1).split()) if closing else ""
    r.signer_role = _signer_role(text, closing)
    r.adr_article_included = bool(re.search(r"\b5925\.\s*\(|Article\s+3\.\s+Alternative\s+Dispute\s+Resolution", text))
    if Request.HEARING in r.requests:
        hit = re.search(rf"(?:hearing|meeting)[^.]{{0,80}}?\b(?:on|for)\s+(?:\w+day,?\s+)?({_DATE})", flat, re.I)
        r.hearing_on = (dates_in(hit.group(1)) or [None])[0] if hit else None
        r.hearing_elements = tuple(name for name, pattern in _HEARING_ELEMENTS if re.search(pattern, flat, re.I))
    return r


_ROLES_SIGNED = r"(Customer\s+Service|Board\s+of\s+Directors|Custodian\s+of\s+Records?|President|Secretary|Treasurer|Vice\s+President|" \
                r"Community\s+Manager|Property\s+Manager|Manager|Attorneys?\s+for\s+[^\n]{3,60}|Inspector\s+of\s+Elections)"


def _signer_role(text: str, closing: re.Match | None) -> str:
    tail = text[closing.end(): closing.end() + 300] if closing else text[-1500:]
    hit = re.search(rf"^\s*{_ROLES_SIGNED}\s*,?\s*$", tail, re.M | re.I) or re.search(rf"\b{_ROLES_SIGNED}\s*$", tail, re.M | re.I)
    return " ".join(hit.group(1).split()) if hit else ""


# Findings.

def _day(d: date) -> str:
    return f"{d:%B} {d.day}, {d.year}"


def _reserve_accounts(context: ModelContext) -> dict[str, Any]:
    fn = getattr(context.community, "bank_accounts", None)
    try:
        rows = tuple(fn()) if callable(fn) else ()
    except Exception:
        rows = ()
    return {str(getattr(a, "suffix", "")): a for a in rows}


def correspondence_findings(r: CorrespondenceRecord, context: ModelContext) -> list[Finding]:
    found: list[Finding] = []
    inbound = r.direction is Direction.INBOUND
    outbound = r.direction is Direction.OUTBOUND
    if r.respond_by:
        passed = " (past)" if r.respond_by < context.today else ""
        who = "the association" if inbound else "the recipient"
        found.append(Finding("response-deadline", f"the letter gives {who} until {_day(r.respond_by)}{passed} to act", Severity.INFO))
    if Request.RECORDS in r.requests and not outbound:
        clocks = ""
        if r.dated:
            clocks = (f" (from a request received {_day(r.dated)}: by {_day(add_business_days(r.dated, RECORDS_CURRENT_BUSINESS_DAYS))} and "
                      f"{_day(r.dated + timedelta(days=RECORDS_PRIOR_DAYS))}; the clock runs from receipt, which the text cannot show)")
        found.append(Finding("records-request", "a request for association records: the current fiscal year's within "
                             f"{RECORDS_CURRENT_BUSINESS_DAYS} business days, the prior two years' within {RECORDS_PRIOR_DAYS} calendar days"
                             f"{clocks}; the member may be billed only the direct and actual cost of copying and mailing, agreed first",
                             Severity.CHECK, "CIV 5205(f), 5210(b)"))
    if Request.IDR in r.requests:
        if outbound:
            found.append(Finding("idr-offer", "the association invokes IDR: the member may decline; a member who takes part and does not "
                                 "agree may appeal to the board; no fee may be charged", Severity.INFO, "CIV 5910(d), (g)"))
        else:
            found.append(Finding("idr-request", "a request for internal dispute resolution: the association must take part and may not "
                                 "refuse to meet and confer, the board names a director to do it, and no fee may be charged",
                                 Severity.CHECK, "CIV 5910(c), (g); 5915(b)"))
    if Request.ADR in r.requests and re.search(r"Request\s+for\s+Resolution", r.subject + " " + r.title, re.I):
        due = f" ({_day(r.dated + timedelta(days=ADR_RESPONSE_DAYS))} from the letter's date; the clock runs from service)" if r.dated else ""
        found.append(Finding("request-for-resolution", f"a Request for Resolution: the recipient has {ADR_RESPONSE_DAYS} days after service "
                             f"to accept, or it is deemed rejected{due}", Severity.CHECK, "CIV 5935(c)"))
        if outbound and r.recipient_role in (Role.OWNER, Role.MEMBERS) and not r.adr_article_included:
            found.append(Finding("adr-article-not-included", "served on a member, a Request for Resolution carries a copy of the ADR "
                                 "article (Civil Code 5925 and following); the text does not", Severity.CHECK, "CIV 5935(a)(4)"))
    if Request.HEARING in r.requests and outbound:
        if r.dated and r.hearing_on:
            lead = (r.hearing_on - r.dated).days
            severity = Severity.PROBLEM if lead < HEARING_NOTICE_DAYS else Severity.INFO
            found.append(Finding("hearing-notice-days", f"the notice is dated {lead} days before the hearing on {_day(r.hearing_on)}; the "
                                 f"member is owed at least {HEARING_NOTICE_DAYS}", severity, "CIV 5855(a)"))
        missing = [e for e, _ in _HEARING_ELEMENTS if e not in r.hearing_elements]
        if missing:
            found.append(Finding("hearing-notice-elements", f"the notice does not state {', '.join(missing)}", Severity.CHECK, "CIV 5855(b)"))
    if Request.DECISION in r.requests and outbound:
        found.append(Finding("decision-notice", f"a notice of a disciplinary decision goes to the member within {DECISION_NOTICE_DAYS} days "
                             "of the board's action; the minutes date the action", Severity.CHECK, "CIV 5855(f)"))
    if Request.PAYMENT_PLAN in r.requests and inbound and r.sender_role is Role.OWNER:
        found.append(Finding("payment-plan-meeting", f"an owner asks to meet about a payment plan: the board meets the owner in executive "
                             f"session within {PAYMENT_PLAN_MEETING_DAYS} days of the request's postmark, if it came within 15 days of the "
                             "pre-lien notice", Severity.CHECK, "CIV 5665(b)"))
    if Request.RESALE_DOCUMENTS in r.requests:
        found.append(Finding("resale-documents", f"the resale documents go out within {RESALE_DOCUMENT_DAYS} days of a written request, at "
                             "no more than the association's actual cost, estimated first on the 4528 form, with no extra charge for "
                             "electronic delivery", Severity.INFO, "CIV 4530(a), (b)"))
    known = _reserve_accounts(context)
    for suffix in r.accounts:
        account = known.get(suffix)
        purpose = str(getattr(getattr(account, "purpose", None), "value", "") or getattr(account, "purpose", "")).lower()
        if account is not None and "reserve" in purpose:
            label = getattr(account, "label", "") or "reserve account"
            found.append(Finding("reserve-account", f"about the {label} ...{suffix}: a record of the reserve account; a withdrawal takes two "
                                 "signers (two directors, or a director and an officer who is not one), reserve money goes only to "
                                 "reserve components, and moving it to operating is a borrowing", Severity.INFO,
                                 "CIV 5200(a)(7), 5510, 5515"))
        elif account is None and known and r.sender_role is Role.BANK:
            found.append(Finding("unknown-account", f"the bank's letter names account ...{suffix}, which the specification's accounts do not "
                                 "list", Severity.CHECK))
    return found


# The models, most specific first.

class _Correspondence(ExplainsMissing, DocumentModel):
    kind = DocumentKind.CORRESPONDENCE
    form: ClassVar[Form] = Form.LETTER

    def recognize(self, text: str, context: ModelContext) -> bool:
        raise NotImplementedError

    def parse(self, text: str, context: ModelContext) -> CorrespondenceRecord | None:
        if not (text or "").strip() or not self.recognize(text, context):
            return None
        return read_correspondence(text, context, self.form)

    def check(self, r: CorrespondenceRecord, context: ModelContext) -> list[Finding]:
        return correspondence_findings(r, context)

    def missing_notes(self, r: CorrespondenceRecord, context: ModelContext) -> dict[str, tuple[str, str]]:
        notes = {"sender": ("no sender is printed in the text: no letterhead, signature, or voice the models know", ""),
                 "recipient": ("no recipient is printed in the text: no salutation or audience", ""),
                 "subject": ("no subject or heading is printed in the text", "")}
        if r.dates or r.deadlines:
            shown = ", ".join(_day(d) for d in (r.dates or tuple(d.on for d in r.deadlines))[:3])
            notes["dated"] = (f"no date of issue is printed in the text; the dates it prints ({shown}) are what it refers to", "")
        else:
            notes["dated"] = ("no date of issue is printed in the text" + (f"; the file name is {context.name!r}" if context.name else ""), "")
        return notes


class CertifiedRecordModel(_Correspondence):
    name = "certified-record"
    form = Form.CERTIFIED_RECORD
    required = ("sender", "dated", "subject")

    def recognize(self, text: str, context: ModelContext) -> bool:
        return bool(re.search(r"Custodian\s+of\s+Records?", text, re.I) and re.search(r"true\s+and\s+(?:accurate|correct)", text, re.I))


class LetterModel(_Correspondence):
    name = "letter"
    form = Form.LETTER
    required = ("dated", "sender", "recipient", "subject")

    def recognize(self, text: str, context: ModelContext) -> bool:
        return bool(_SALUTATION.search(text) or (_CLOSING.search(text) and _DATE_LINE.search(text)) or
                    (_SUBJECT.search(text[:1500]) and _DATE_LINE.search(text[:1500])))


class NoticeModel(_Correspondence):
    name = "member-notice"
    form = Form.NOTICE
    required = ("dated", "sender", "recipient", "subject")

    def recognize(self, text: str, context: ModelContext) -> bool:
        head = text[:800]
        return bool(re.search(r"\bnewsletter\b|\bannounce|\bcontest\b|NOTICE\s+TO\s+(?:ALL\s+)?(?:OWNERS|RESIDENTS|MEMBERS|HOMEOWNERS)|"
                              r"Friendly\s+Reminder", head, re.I) and _speaks_for_association(text, _association(context)))


class HandoutModel(_Correspondence):
    name = "handout"
    form = Form.HANDOUT
    required = ("sender", "recipient", "subject")

    def recognize(self, text: str, context: ModelContext) -> bool:
        association = _association(context)
        titled = re.search(r"INSTRUCTIONS\s+(?:FOR|TO)\b|\bHow\s+to\b|\bObtaining\b|Check-?\s?List|Contact\s+Information|\bWelcome\b|"
                           r"Frequently\s+Asked|\bFAQ\b", f"{_title(text, association)}\n{text[:600]}", re.I)
        return bool(titled and _speaks_for_association(text, association))


class PublicationModel(_Correspondence):
    name = "publication"
    form = Form.PUBLICATION
    required = ("sender", "subject")

    def recognize(self, text: str, context: ModelContext) -> bool:
        return bool(re.search(r"\be-?book\b|\bguide\b|\bManual\b|^\s*Section\s+[A-Z]\.\s", text, re.I | re.M))


for _model in (CertifiedRecordModel(), LetterModel(), NoticeModel(), HandoutModel(), PublicationModel()):
    register(_model)

__all__ = ["Form", "Role", "Direction", "Request", "Deadline", "Amount", "CorrespondenceRecord", "CertifiedRecordModel", "LetterModel",
           "NoticeModel", "HandoutModel", "PublicationModel", "read_correspondence", "correspondence_findings", "add_business_days"]
