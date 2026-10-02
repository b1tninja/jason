"""A mail item as a record, and the rules that say what kind of mail it is and whether someone must act.

PostScanMail gives the sender's name, the arrival time, the folder, and (once scanned) the pages.
``MailItem.from_api`` keeps those and drops the signed links' signatures. ``classify`` reads the
sender and the scanned text against ``MAIL_RULES`` in order: the first rule whose sender words or
text phrases match names the kind. A kind carries its urgency: a legal notice, an insurance
cancellation, a government notice, or anything stating a deadline is for a person to read now.
A miss stays "other". The rules read words; they do not decide what the letter means.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class MailKind(Enum):
    LEGAL = "legal notice"
    INSURANCE_CANCELLATION = "insurance cancellation or non-renewal"
    INSURANCE = "insurance policy, renewal, or invoice"
    GOVERNMENT = "government or tax notice"
    ESCROW = "escrow or title request"
    BANK = "bank statement or notice"
    UTILITY = "utility bill"
    TAX_BILL = "property tax bill"
    LIEN_NOTICE = "preliminary notice or mechanic's lien"
    CHECK = "check or payment received"
    INVOICE = "vendor invoice or statement"
    MARKETING = "advertising"
    OTHER = "other"


class Urgency(Enum):
    ACT = "act"          # a person must read and likely respond
    REVIEW = "review"    # file it where it belongs; the board may need it
    FILE = "file"        # routine


@dataclass(frozen=True)
class MailRule:
    """Sender words (any), or text phrases (``min_hits`` of them), that name a kind.

    ``within`` limits the phrases to the letter's first characters: a summons or a cancellation notice says so in
    its title, while a policy packet repeats "notice of cancellation" and "case no" as boilerplate pages deep.
    """

    kind: MailKind
    urgency: Urgency
    senders: tuple[str, ...] = ()
    phrases: tuple[str, ...] = ()
    min_hits: int = 1
    within: int | None = None

    def matches(self, sender: str, text: str) -> list[str]:
        s = sender.casefold()
        t = (text[: self.within] if self.within else text).casefold()
        hits = [w for w in self.senders if w.casefold() in s]
        if hits:
            return hits
        found = [p for p in self.phrases if p.casefold() in t]
        return found if len(found) >= self.min_hits else []


HEADING = 1500

# Order is part of the rule: a law firm's advertisement says so and may cite a court, which no summons does, so the
# marker comes first; then a court's caption; a cancellation outranks the insurer's name.
MAIL_RULES: tuple[MailRule, ...] = (
    MailRule(MailKind.MARKETING, Urgency.FILE, phrases=("is an advertisement", "attorney advertising", "advertising material"),
             within=HEADING),
    # A compliance mailer dressed as a state requirement ("Annual Order Form", "Annual Minutes"): not from an agency.
    MailRule(MailKind.MARKETING, Urgency.REVIEW, phrases=("annual order form", "annual minutes disclosure", "corporate compliance",
                                                          "labor law poster", "certificate of good standing request"), within=HEADING),
    MailRule(MailKind.LEGAL, Urgency.ACT, phrases=("summons", "superior court of", "complaint for", "notice of lawsuit", "case number:",
                                                   "notice of default", "notice of trustee", "lis pendens", "subpoena"), within=HEADING),
    MailRule(MailKind.INSURANCE_CANCELLATION, Urgency.ACT, phrases=("notice of cancellation", "cancellation notice", "notice of non-renewal",
                                                                    "nonrenewal notice", "notice of nonrenewal", "will be cancelled",
                                                                    "intent to cancel"), within=HEADING),
    # Works of improvement (Civil Code 8000 et seq.): a recorded claim or a stop payment notice is for a person now; a
    # 20-day preliminary notice (8200) preserves a contractor's or supplier's lien rights and is settled by paying them.
    MailRule(MailKind.LIEN_NOTICE, Urgency.ACT, phrases=("claim of mechanic", "mechanics lien", "mechanic's lien", "stop payment notice",
                                                           "claim of lien (mechanic"), within=400),
    MailRule(MailKind.LIEN_NOTICE, Urgency.REVIEW, phrases=("preliminary notice", "this is not a lien", "notice to property owner"),
             within=HEADING),
    # A delinquency notice quotes the tax bill; it outranks the bill it quotes.
    MailRule(MailKind.GOVERNMENT, Urgency.ACT, phrases=("notice of delinquent", "judicial foreclosure", "tax-defaulted", "power to sell",
                                                        "notice of lien", "notice of a property lien", "notice of error in payment",
                                                        "being returned to you"), within=HEADING),
    MailRule(MailKind.TAX_BILL, Urgency.REVIEW, phrases=("property tax bill", "supplemental tax bill"), within=HEADING * 2),
    # The county's online-account letters (a PIN to verify ownership) are paperwork, not a notice to answer.
    MailRule(MailKind.GOVERNMENT, Urgency.REVIEW, phrases=("ownership verification", "opting out of paper bills"), within=HEADING * 2),
    MailRule(MailKind.GOVERNMENT, Urgency.ACT, senders=("franchise tax board", "internal revenue", "secretary of state", "superior court",
                                                          "tax collector", "department of finance", "code enforcement", "fire department",
                                                          "county of sacramento", "assessor")),
    MailRule(MailKind.LEGAL, Urgency.ACT, senders=("law group", "law office", "attorney", "llp", "law firm", "legal")),
    MailRule(MailKind.ESCROW, Urgency.ACT, senders=("title", "escrow"), phrases=("demand", "payoff", "resale", "escrow no", "estoppel"),
             min_hits=2),
    MailRule(MailKind.UTILITY, Urgency.FILE, senders=("department of utilities", "smud", "water company", "pg&e", "republic services")),
    MailRule(MailKind.BANK, Urgency.REVIEW, senders=("bank", "credit union", "chase"), phrases=("certificate of deposit", "account statement",
                                                                                              "statement period")),
    MailRule(MailKind.INSURANCE, Urgency.REVIEW, senders=("insurance", "program administrators", "indemnity", "farmers", "assurance",
                                                          "underwriters", "mcgowan"),
             phrases=("renewal", "declarations", "policy period", "premium", "certificate of insurance"), min_hits=2),
    MailRule(MailKind.CHECK, Urgency.REVIEW, phrases=("pay to the order of", "to the order of", "void after", "refund check",
                                                      "non-negotiable", "check number"), min_hits=1),
    MailRule(MailKind.INVOICE, Urgency.FILE, phrases=("invoice", "amount due", "balance due", "statement date", "remit"), min_hits=2),
    MailRule(MailKind.MARKETING, Urgency.FILE, phrases=("limited time", "special offer", "act now", "presorted", "prsrt std"), min_hits=1),
)

_DEADLINE = re.compile(
    r"(?:due|respond|response|reply|pay|payment|expires?|expiration|effective|renew(?:al)?|cancel(?:lation|led)? (?:date|on|effective)|"
    r"hearing|deadline|no later than|by)\D{0,30}?"
    r"(\d{1,2}/\d{1,2}/\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.? \d{1,2},? \d{4})",
    re.I,
)


def _date(text: str) -> date | None:
    t = text.replace(".", "").replace(",", "").strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def deadlines(text: str, *, after: date | None = None) -> list[tuple[str, date]]:
    """Dates the letter ties to an action ("due", "respond by", "effective", "expires"), on or after ``after``."""
    found: list[tuple[str, date]] = []
    for m in _DEADLINE.finditer(text):
        day = _date(m.group(1))
        if day and (after is None or day >= after):
            label = " ".join(m.group(0).split())[:60]
            if all(day != d for _l, d in found):
                found.append((label, day))
    return sorted(found, key=lambda x: x[1])


@dataclass
class MailItem:
    mail_id: str
    sender: str
    address_id: str
    received: datetime | None
    status: str
    folder: str
    assigned_to: str
    scanned: bool
    ai_summary: tuple[str, ...] = ()
    cover_url: str = field(default="", repr=False)
    pdf_url: str = field(default="", repr=False)

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> MailItem:
        meta = item.get("pdf_metadata") or {}
        received = None
        if meta.get("received_at"):
            try:
                received = datetime.fromisoformat(str(meta["received_at"]))
            except ValueError:
                received = None
        return cls(
            mail_id=str(item.get("mail_id") or ""),
            sender=str(item.get("sender_name") or "").strip(),
            address_id=str(item.get("address_id") or ""),
            received=received,
            status=str(meta.get("current_status") or ""),
            folder=str(meta.get("current_folder_name") or ""),
            assigned_to=str(meta.get("assigned_user") or ""),
            scanned=bool(item.get("pdf_content")),
            ai_summary=tuple(str(line) for line in item.get("ai_summary") or ()),
            cover_url=str(item.get("cover_image") or ""),
            pdf_url=str(item.get("pdf_content") or ""),
        )

    def record(self) -> dict[str, Any]:
        """The item as stored on disk: no signed links (they are fetched fresh when needed)."""
        return {"mailId": self.mail_id, "sender": self.sender, "addressId": self.address_id,
                "received": self.received.isoformat(sep=" ") if self.received else None, "status": self.status,
                "folder": self.folder, "assignedTo": self.assigned_to, "scanned": self.scanned, "aiSummary": list(self.ai_summary)}


@dataclass(frozen=True)
class Classified:
    kind: MailKind
    urgency: Urgency
    evidence: tuple[str, ...]
    deadlines: tuple[tuple[str, date], ...] = ()


class AddressKind(Enum):
    CURRENT = "current mailing address"
    INCOMPLETE = "current address without the box number"
    FORMER_MANAGER = "former manager's address"
    PROPERTY = "the site address, where no mail is received"
    OTHER = "another address"
    UNREAD = "addressee not read"


@dataclass(frozen=True)
class MailAddress:
    """One address a letter to the association can carry: what it is, and the words that recognize it."""

    kind: AddressKind
    label: str
    words: tuple[str, ...]
    # Words one of which must also appear for the address to be complete (the box number at a mail center).
    requires: tuple[str, ...] = ()
    zip: str = ""                   # the ZIP code a complete address carries; a different one misroutes the mail


_ADDRESSEE_NAME = re.compile(r"(?i)mystique\s+(?:community|homeowners|hoa|condo)")


def addressee_block(text: str, *, lines: int = 5) -> str:
    """The addressee: the association's name and the lines under it, from its first mention on the page.

    A letterhead names its sender first; the addressee block is the first place the association's own name
    appears with lines after it. An envelope window or a statement header reads the same way.
    """
    rows = [line.strip() for line in text.splitlines()]
    for index, line in enumerate(rows):
        if _ADDRESSEE_NAME.search(line):
            block = [r for r in rows[index: index + 1 + lines] if r]
            return " | ".join(block)
    return ""


def address_of(text: str, addresses: tuple[MailAddress, ...]) -> tuple[AddressKind, str, str]:
    """(kind, label, block): which of ``addresses`` the letter's addressee block carries."""
    block = addressee_block(text)
    if not block:
        return AddressKind.UNREAD, "", ""
    kind, label = classify_address(block, addresses)
    return kind, label, block


def _carries(folded: str, word: str) -> bool:
    return " " + re.sub(r"[^A-Z0-9]+", " ", word.upper()).strip() + " " in folded or word.upper().replace(" ", "") in folded.replace(" ", "")


def classify_address(block: str, addresses: tuple[MailAddress, ...]) -> tuple[AddressKind, str]:
    """(kind, label) of the first address whose words the block carries; one missing its required words is incomplete."""
    # Letters and digits only: OCR prints "901 H'ST" and "PMB188".
    folded = " " + re.sub(r"[^A-Z0-9]+", " ", block.upper()) + " "
    for address in addresses:
        if any(_carries(folded, word) for word in address.words):
            if address.requires and not any(_carries(folded, word) for word in address.requires):
                return AddressKind.INCOMPLETE, address.label
            return address.kind, address.label
    return AddressKind.OTHER, ""


def care_of(block: str) -> str:
    """The party a letter is addressed in care of ("c/o", "%", "care of"), or empty."""
    m = re.search(r"(?i)(?:\bc/o\b|\bcare of\b|%)\s*([A-Za-z][A-Za-z &.,'-]{2,40})", block)
    return m.group(1).strip(" |.,") if m else ""


# Kinds whose letters stay out of shared catalogs unless a person asks: a claim or an attorney's letter, account
# statements and checks (account and routing numbers), and escrow requests (an owner's sale and personal details).
CONFIDENTIAL_KINDS = frozenset({MailKind.LEGAL, MailKind.BANK, MailKind.CHECK, MailKind.ESCROW})

_APN = re.compile(r"\b(\d{3})[- ]?(\d{4})[- ]?(\d{3})[- ]?(\d{4})\b")
# The label is optional: "policy N030PK2940-01" in running text names it as well as "Policy No.: N030PK2940-01" does.
_POLICY = re.compile(r"(?i)\bpolicy\s*(?:(?:no\.?|number|#)\s*[:#.]?\s*)?([A-Z]{0,6}[0-9][A-Z0-9-]{4,})")
_ESCROW = re.compile(r"(?i)\b(?:escrow|order|file)\s*(?:no\.?|number|#)\s*[:#.]?\s*([A-Z0-9][A-Z0-9-]{3,})")
_ACCOUNT = re.compile(r"(?i)\b(?:account|acct)\s*(?:no\.?|number|nbr|#)?\s*[:#.]?\s*[*xX]{2,}\s*-?(\d{4})\b")
_PERIOD = re.compile(r"(?i)(?:policy period|term)\D{0,20}(\d{1,2}/\d{1,2}/\d{2,4})\s*(?:to|-|through|thru)\s*(\d{1,2}/\d{1,2}/\d{2,4})")
_ADDRESS = re.compile(r"\b(\d{4})\s+(MACON\s+DR(?:IVE)?|ENCHANTED\s+WALK|MAGICAL\s+WALK|MESMERIZING\s+WALK|WHIMSICAL\s+L(?:N|ANE))\b", re.I)


@dataclass(frozen=True)
class LetterFacts:
    """What a letter's own text names, read by pattern: the handles that join it to the association's other records.

    ``parcels`` are 14-digit assessor numbers; ``addresses`` are street addresses on Mystique's streets; the rest are
    the numbers a renewal, an escrow demand, or a statement is filed under. A pattern reading is evidence, not a pin.
    """

    parcels: tuple[str, ...] = ()
    addresses: tuple[str, ...] = ()
    policies: tuple[str, ...] = ()
    policy_periods: tuple[tuple[str, str], ...] = ()
    escrows: tuple[str, ...] = ()
    accounts: tuple[str, ...] = ()

    def record(self) -> dict[str, Any]:
        return {"parcels": list(self.parcels), "addresses": list(self.addresses), "policies": list(self.policies),
                "policyPeriods": [list(p) for p in self.policy_periods], "escrows": list(self.escrows), "accounts": list(self.accounts)}


def _unique(values) -> tuple[str, ...]:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return tuple(seen)


def letter_facts(text: str) -> LetterFacts:
    """The parcel numbers, addresses, policy numbers and periods, escrow numbers, and account endings a letter prints."""
    street = {"DRIVE": "DR", "LANE": "LN"}
    addresses = []
    for number, name in _ADDRESS.findall(text):
        words = name.upper().split()
        words[-1] = street.get(words[-1], words[-1])
        addresses.append(f"{number} {' '.join(words)}")
    periods = []
    for start, end in _PERIOD.findall(text):
        a, b = _date(start), _date(end)
        if a and b and a < b:
            periods.append((a.isoformat(), b.isoformat()))
    return LetterFacts(
        parcels=_unique("".join(m) for m in _APN.findall(text)),
        addresses=_unique(addresses),
        policies=_unique(p.upper().strip("-.") for p in _POLICY.findall(text)),
        policy_periods=tuple(dict.fromkeys(periods)),
        escrows=_unique(e.upper().strip("-") for e in _ESCROW.findall(text) if any(c.isdigit() for c in e)),
        accounts=_unique(_ACCOUNT.findall(text)),
    )


def classify(sender: str, text: str, *, received: date | None = None, rules: tuple[MailRule, ...] = MAIL_RULES) -> Classified:
    """The first rule the sender or the text matches; a stated deadline after arrival raises routine mail to review."""
    due = tuple(deadlines(text, after=received))
    # PostScanMail often leaves the sender blank; the letterhead at the top of the scan names it then.
    who = sender or text[:300]
    for rule in rules:
        hits = rule.matches(who, text)
        if hits:
            urgency = rule.urgency
            if due and urgency is Urgency.FILE and rule.kind not in (MailKind.MARKETING, MailKind.UTILITY):
                urgency = Urgency.REVIEW
            return Classified(rule.kind, urgency, tuple(hits), due)
    return Classified(MailKind.OTHER, Urgency.REVIEW if due else Urgency.FILE, (), due)


__all__ = ["MailKind", "Urgency", "MailRule", "MAIL_RULES", "MailItem", "Classified", "classify", "deadlines",
           "LetterFacts", "letter_facts", "CONFIDENTIAL_KINDS", "AddressKind", "MailAddress", "addressee_block", "address_of", "care_of"]
