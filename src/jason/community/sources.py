"""Where a document comes from: the source, and what kind of source it is.

The kind of source says how to read a document. A government agency's notice can carry a legal
deadline; a utility's bill follows a tariff; an insurer or its agent writes about coverage; a bank's
statement is a record of balances; a vendor bills for work; a title company asks for the resale
documents; a law firm writes about a claim; a management company writes for its clients. The
association's own counterparties are named in the specification (``Community.senders()``): each is a
``Sender`` with its kind, a government agency's level, and the words its letterhead or name carries.
A document from a sender the specification does not name still gets a kind from the generic words
in ``KIND_WORDS`` ("Department of", "Insurance", "Bank", "Title", "LLP"); a miss stays unknown.

A document can also name another community association, as the addressee or in its body. Mail for
another association arriving at the association's box, or an agency's record naming another
association for one of the association's accounts, is worth a person's look (``other_associations``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from jason.community.base import NEVER


class SourceKind(Enum):
    GOVERNMENT = "government agency"
    UTILITY = "utility"
    INSURER = "insurer or insurance agency"
    BANK = "bank"
    VENDOR = "vendor"
    TITLE_ESCROW = "title or escrow company"
    LAW_FIRM = "law firm"
    MANAGER = "management company"             # the association's own manager
    PROPERTY_MANAGER = "owner's property manager"  # manages an owner's rented unit; an other contact, never an owner
    ACCOUNTANT = "accountant"
    OTHER_ASSOCIATION = "another community association"
    OWNER = "owner or resident"
    PLATFORM = "service platform"
    UNKNOWN = "unknown"


class Level(Enum):
    FEDERAL = "federal"
    STATE = "state"
    COUNTY = "county"
    CITY = "city"
    DISTRICT = "special district"


@dataclass(frozen=True)
class Sender:
    """One counterparty: its name, kind, a government agency's level, and the words that recognize it.

    ``words`` are matched against a document's sender field and its letterhead (the first lines), letters and
    digits only. ``payhoa_vendor`` is its name in PayHOA's vendor directory, when the association pays it.
    ``role`` says what it is to the association ("flood insurance carrier", "prior manager"). ``domains`` are the email
    domains it writes from, so its email is read beside its letters.
    """

    name: str
    kind: SourceKind
    words: tuple[str, ...]
    level: Level | None = None
    payhoa_vendor: str = ""
    role: str = ""
    domains: tuple[str, ...] = ()

    def writes_from(self, address: str) -> bool:
        """Whether an email address is at one of its domains (or a subdomain)."""
        host = address.rsplit("@", 1)[-1].strip(" >").lower()
        return any(host == d or host.endswith("." + d) for d in self.domains)


# Generic words for a sender the specification does not name, in order: the first kind whose words appear wins.
KIND_WORDS: tuple[tuple[SourceKind, Level | None, tuple[str, ...]], ...] = (
    (SourceKind.GOVERNMENT, Level.FEDERAL, ("INTERNAL REVENUE", "DEPARTMENT OF THE TREASURY", "SOCIAL SECURITY", "FEMA", "UNITED STATES")),
    (SourceKind.GOVERNMENT, Level.STATE, ("FRANCHISE TAX BOARD", "SECRETARY OF STATE", "STATE OF CALIFORNIA", "EMPLOYMENT DEVELOPMENT")),
    (SourceKind.GOVERNMENT, Level.COUNTY, ("COUNTY OF", "COUNTY TAX", "ASSESSOR", "TAX COLLECTOR", "RECORDER")),
    (SourceKind.UTILITY, None, ("DEPARTMENT OF UTILITIES", "WATER COMPANY", "UTILITY DISTRICT", "SMUD", "PG E", "WASTE MANAGEMENT")),
    (SourceKind.GOVERNMENT, Level.CITY, ("CITY OF", "FIRE DEPARTMENT", "CODE ENFORCEMENT", "POLICE DEPARTMENT")),
    (SourceKind.GOVERNMENT, Level.DISTRICT, ("SANITATION DISTRICT", "FLOOD CONTROL", "ASSESSMENT DISTRICT", "AREA FLOOD")),
    (SourceKind.TITLE_ESCROW, None, ("TITLE COMPANY", "TITLE INSURANCE", "ESCROW")),
    (SourceKind.LAW_FIRM, None, ("LAW GROUP", "LAW OFFICE", "ATTORNEYS", "ATTORNEY AT LAW", " LLP")),
    (SourceKind.INSURER, None, ("INSURANCE", "INDEMNITY", "ASSURANCE", "UNDERWRITERS", "INSURANCE EXCHANGE", "PROGRAM ADMINISTRATORS")),
    (SourceKind.BANK, None, ("BANK", "CREDIT UNION", "TRUST COMPANY")),
    (SourceKind.ACCOUNTANT, None, ("CERTIFIED PUBLIC ACCOUNTANT", " CPA")),
    (SourceKind.MANAGER, None, ("PROPERTY MANAGEMENT", "ASSOCIATION MANAGEMENT", "MANAGEMENT COMPANY")),
)

# "<Name> Community Association", "<Name> Owners Association", "<Name> Homeowners Association", "<Name> HOA".
_ASSOCIATION = re.compile(r"\b((?:[A-Z0-9][A-Za-z0-9'&.-]*\s+){1,5}(?:COMMUNITY|OWNERS|HOMEOWNERS|HOMES)\s+ASSOC(?:IATION|\.)?)", re.I)


def fold(text: str) -> str:
    """Upper-case letters and digits, one space between words: OCR's punctuation and line breaks do not matter."""
    return " " + re.sub(r"[^A-Z0-9]+", " ", text.upper()).strip() + " "


def sender_in(text: str, senders: Iterable[Sender], *kinds: SourceKind) -> Sender | None:
    """The counterparty a text names: the first sender of one of ``kinds``, in the directory's order, one of whose words
    the text carries (letters and digits only, so OCR's punctuation does not matter). With no kind given, any sender.
    None when the specification lists no such sender or the text names none: a miss. A general reader finds a law
    firm, a manager, a vendor, or an insurer this way, never by a name in its own pattern."""
    folded = fold(text or "")
    for sender in senders:
        if (not kinds or sender.kind in kinds) and any(fold(word) in folded for word in sender.words):
            return sender
    return None


def sender_name(text: str, community: object, *kinds: SourceKind) -> str:
    """The name, from the community's sender directory, of the counterparty of one of ``kinds`` a text names; empty on a
    miss, and for a community with no directory."""
    found = sender_in(text, getattr(community, "senders", tuple)(), *kinds)
    return found.name if found else ""


def manager_in(text: str, senders: Iterable[Sender]) -> Sender | None:
    """The management company a text names: ``sender_in`` for the kind ``MANAGER``. None when the specification lists no
    manager or the text names none: a miss."""
    return sender_in(text, senders, SourceKind.MANAGER)


def manager_name(text: str, community: object) -> str:
    """The name of the management company a text names, from the community's sender directory; empty on a miss."""
    return sender_name(text, community, SourceKind.MANAGER)


def resolve(sender: str, text: str, senders: tuple[Sender, ...], *, own_name: str = "",
            wide: int = 1200) -> tuple[Sender | None, SourceKind, Level | None, str]:
    """(named sender or None, kind, level, the words that decided) for a document's sender field and letterhead.

    The sender field is tried first, then the letterhead (the first 400 characters, without the association's own
    name, which is the addressee there). A named sender outranks the generic words there. Last, a named sender's
    words anywhere in the first ``wide`` characters: a form's payer block ("JPMORGAN CHASE BANK" on a 1099) or an
    invoice's "COMPANY:" line sits below the addressee. ``own_name`` is a pattern for that name
    (``Community.name_pattern``); without one, no line is taken for the addressee.
    """
    own = rf"(?i)(?:{own_name})[^\n]*" if own_name else NEVER
    head = re.sub(own, " ", text[:400])
    below = re.sub(own, " ", text[:wide])

    def named(places: tuple[str, ...]) -> tuple[Sender, str] | None:
        for place in places:
            folded = fold(place) if place else ""
            for known in senders:
                for word in known.words:
                    if folded and fold(word) in folded:
                        return known, word
        return None

    hit = named((sender, head))
    if hit:
        return hit[0], hit[0].kind, hit[0].level, hit[1]
    for place in (sender, head):
        if not place:
            continue
        folded = fold(place)
        for kind, level, words in KIND_WORDS:
            for word in words:
                if fold(word) in folded:
                    return None, kind, level, word.strip()
    hit = named((below,))
    if hit:
        return hit[0], hit[0].kind, hit[0].level, hit[1]
    return None, SourceKind.UNKNOWN, None, ""


_CONNECTORS = {"at", "of", "the", "de", "la", "del", "on"}
_NOT_A_NAME = {"THE", "YOUR", "THIS", "OUR", "AN", "A", "HOMEOWNERS", "OWNERS", "COMMUNITY", "EACH", "ANY", "FACILITY", "NAME"}


def _name_before(tokens: list[str]) -> list[str]:
    """The capitalized run that ends at the suffix: "Bk i University District" keeps "University District"."""
    kept: list[str] = []
    for token in reversed(tokens):
        word = token.strip(",.;:")
        if word.lower() in _CONNECTORS and kept:
            kept.insert(0, word)
            continue
        if len(word) >= 3 and word[0].isupper() and re.fullmatch(r"[A-Za-z][A-Za-z'&-]*", word) and word.upper() not in ("NAME", "FACILITY"):
            kept.insert(0, word)
            continue
        # A phase number ends a name ("Longmeadow Village 2"); a number anywhere else is not part of it.
        if not kept and re.fullmatch(r"\d{1,2}", word):
            kept.insert(0, word)
            continue
        break
    while kept and (kept[0].lower() in _CONNECTORS or kept[0].lower() in ("dear", "re", "attn", "from", "to", "for")):
        kept.pop(0)
    return kept


def other_associations(text: str, *, own_name: str = "") -> tuple[str, ...]:
    """Names of other community associations a document mentions (its addressee, a c/o line, or its body).

    Only the capitalized name directly before "Association" counts, the association's own name is dropped by
    ``own_name``, its pattern with OCR's spellings (``Community.name_pattern``), a bare "the Homeowners Association" is
    not a name, and "Assoc" and "Association" are one name.
    """
    own = re.compile(rf"(?i){own_name or NEVER}")
    found: list[str] = []
    keys: set[str] = set()
    for match in _ASSOCIATION.finditer(text):
        words = match.group(1).split()
        suffix_at = next(i for i, w in enumerate(words) if w.upper().rstrip(".") in ("COMMUNITY", "OWNERS", "HOMEOWNERS", "HOMES"))
        core = _name_before(words[:suffix_at])
        if not core or all(w.upper() in _NOT_A_NAME for w in core):
            continue
        suffix = re.sub(r"(?i)\bassoc(?:iation|\.)?$", "Association", " ".join(words[suffix_at:]))
        name = " ".join(core + [suffix])
        if own.search(fold(name).replace(" ", "")):
            continue
        key = fold(name).replace(" ", "")
        if key not in keys:
            keys.add(key)
            found.append(name)
    # OCR debris before a name ("Renee Ble University District ...") leaves a longer copy of a name already found.
    squeezed = {n: fold(n).replace(" ", "") for n in found}
    return tuple(n for n in found if not any(o != n and squeezed[n].endswith(squeezed[o]) for o in found))


__all__ = ["SourceKind", "Level", "Sender", "KIND_WORDS", "resolve", "other_associations", "fold", "sender_in", "sender_name",
           "manager_in", "manager_name"]
