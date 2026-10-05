"""The other names a party goes by in a contract: a dba, a short form, and a role label.

A vendor's contract rarely calls the vendor by one name. A letterhead names the trade name, the body names the company
that owns it ("Sample Holdings Inc. dba Example Home Services"), a parenthetical coins a short form ("(EHS)") that the
duties then use, and an order form sets a party's steps under a line-leading label ("CUSTOMER:", "SAMPLE CAMERAS:").
A reader that knows only the counterparty's letterhead name misses every duty written under the other names, so this
module finds them, each with the full name it stands for, for the reader to fold into one party.

``find_aliases(text)`` reads three shapes:

- a dba ("X dba Y", "X d/b/a Y", "X doing business as Y"): one party under two names. The alias is the legal name X
  and the name is the trade name Y, the one a letterhead and a signature block usually carry; ``aliases_of`` joins
  both directions, so a caller holding either name gets the other.
- a parenthetical short form right after a name ("Example Home Services (EHS)", 'Sample Co. (the "Contractor")'):
  uppercase letters 2 to 8 long, or a quoted capitalized word, and not a defined term introduced by a keyword such as
  "hereinafter" (those are the reader's definitions, read elsewhere).
- a role label: an uppercase label of one to four words alone on its line, followed by the lines that label owns.
  Only a label that names a party is kept: a role word (``ROLE_WORDS``) or the start of a name the text writes in
  mixed case. Form labels ("Re:", "Date:", "Total:") are in ``FORM_LABELS`` and never read as parties.

``role_sections(text)`` gives the lines under each role label, so a later step can give each line to its party.

A reading is a lead: jason does not decide that two names are one company in law, only that the contract uses them so.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class AliasKind(Enum):
    DBA = "dba"
    PARENTHETICAL = "parenthetical"
    ROLE_LABEL = "role label"


@dataclass(frozen=True)
class Alias:
    """``alias`` is the other name or label as written; ``name`` the full name it stands for, "" when unknown.

    ``start`` and ``end`` are the span of the alias in the text.
    """

    alias: str
    name: str
    kind: AliasKind
    start: int
    end: int


@dataclass(frozen=True)
class RoleSection:
    """One line under a role label: the label (an ``Alias`` of kind ROLE_LABEL) and the line's text and span."""

    label: Alias
    text: str
    start: int
    end: int


# How a dba is written, in the order tried. A new spelling is a new row.
DBA_MARKERS: tuple[str, ...] = (r"doing\s+business\s+as", r"d\s*/\s*b\s*/\s*a", r"dba")

# Words that introduce a defined term rather than a short form; the reader's definitions handle those.
DEFINED_TERM_KEYWORDS: tuple[str, ...] = ("hereinafter", "referred to as", "called", "known as")

# Uppercase parentheticals that are not short forms of a name.
NOT_SHORT_FORMS: tuple[str, ...] = ("AM", "PM", "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII")

# A name ending in one of these is a document, not a party: 'THIS AGREEMENT ("Agreement")'.
DOCUMENT_WORDS: tuple[str, ...] = (
    "AGREEMENT", "CONTRACT", "PROPOSAL", "ORDER", "PLAN", "ADDENDUM", "AMENDMENT", "EXHIBIT", "SCHEDULE",
    "STATEMENT", "ESTIMATE", "QUOTE", "INVOICE", "POLICY",
)

# Line labels that head a form field or a section, never a party.
FORM_LABELS: tuple[str, ...] = (
    "RE", "DATE", "PHONE", "FAX", "EMAIL", "E-MAIL", "TOTAL", "SUBTOTAL", "TAX", "AMOUNT", "PRICE", "BALANCE",
    "SUBJECT", "REFERENCE", "ATTN", "ATTENTION", "TO", "FROM", "CC", "PAGE", "NOTE", "NOTES", "ADDRESS",
    "PROPERTY", "PROJECT", "JOB", "LOCATION", "DESCRIPTION", "SCOPE", "SCOPE OF WORK", "TERMS", "EXCLUSIONS",
    "INCLUSIONS", "WARRANTY", "PAYMENT", "NOTICE", "SIGNATURE", "SIGNED", "BY", "NAME", "TITLE", "ITS",
    "ACCEPTED BY", "APPROVED BY", "BILL TO", "SHIP TO", "SOLD TO", "INVOICE", "ESTIMATE", "PROPOSAL", "QUOTE",
)

# Labels that name a party by its role.
ROLE_WORDS: tuple[str, ...] = (
    "CUSTOMER", "CLIENT", "OWNER", "CONTRACTOR", "SUBCONTRACTOR", "VENDOR", "SUPPLIER", "PROVIDER",
    "SERVICE PROVIDER", "COMPANY", "ASSOCIATION", "MANAGER", "AGENT", "CONSULTANT", "SELLER", "BUYER",
    "PURCHASER", "SUBSCRIBER", "LICENSEE", "LICENSOR", "LANDLORD", "TENANT",
)

# Abbreviations that end a company name with a period, so the period does not end the sentence.
_NAME_SUFFIXES = ("inc.", "co.", "corp.", "ltd.", "l.l.c.", "llc.", "l.p.", "lp.", "p.c.", "n.a.", "bros.")
# "and" is left out: "X and Y (the "Contractor")" is two parties, and the short form belongs to the second.
_CONNECTORS = ("of", "&", "the", "for")

_TOKEN = re.compile(r"\S+")
_PAREN = re.compile(
    r"\(\s*(?:the\s+)?(?:[\"“]([A-Z][A-Za-z]+|[A-Z]{2,8})[\"”]|([A-Z]{2,8}))\s*\)"
)
_LABEL_LINE = re.compile(r"(?m)^[ \t]*([A-Z][A-Z&'.-]*(?:[ \t]+[A-Z][A-Z&'.-]*){0,3})[ \t]*:[ \t]*$")
_SENTENCE_END = re.compile(r"[.;:!?)]\s*$")


def _capitalized(token: str) -> bool:
    return bool(re.match(r"[\"“]?[A-Z0-9]", token))


def _ends_sentence(token: str) -> bool:
    return token.endswith(".") and token.lower() not in _NAME_SUFFIXES and not re.fullmatch(r"[A-Z]\.", token)


def _tokens(text: str, lo: int, hi: int) -> list[tuple[str, int, int]]:
    return [(m.group(), lo + m.start(), lo + m.end()) for m in _TOKEN.finditer(text[lo:hi])]


def _line_bounds(text: str, pos: int) -> tuple[int, int]:
    lo = text.rfind("\n", 0, pos) + 1
    hi = text.find("\n", pos)
    return lo, len(text) if hi < 0 else hi


def _name_before(text: str, pos: int) -> tuple[str, int]:
    """The run of capitalized words that ends at ``pos`` on its line, and where it starts; ("", pos) when none."""
    lo, _ = _line_bounds(text, pos)
    run: list[tuple[str, int, int]] = []
    for tok in reversed(_tokens(text, lo, pos)):
        word = tok[0]
        if run and _ends_sentence(word):
            break
        if run and word.endswith(",") and run[-1][0].lower() in _NAME_SUFFIXES:
            run.append(tok)  # "Example, Inc."
            continue
        if word.endswith((",", ";", ":")):
            break
        if _capitalized(word) or (run and word.lower() in _CONNECTORS):
            run.append(tok)
            continue
        break
    while run and run[-1][0].lower() in _CONNECTORS:
        run.pop()
    if not run:
        return "", pos
    run.reverse()
    return text[run[0][1]:run[-1][2]].rstrip(","), run[0][1]


def _name_after(text: str, pos: int) -> tuple[str, int]:
    """The run of capitalized words that starts at ``pos`` on its line, and where it ends; ("", pos) when none."""
    _, hi = _line_bounds(text, pos)
    run: list[tuple[str, int, int]] = []
    for tok in _tokens(text, pos, hi):
        word = tok[0]
        if word.startswith("("):
            break
        if _capitalized(word) or (run and word.lower() in _CONNECTORS):
            run.append(tok)
            if _ends_sentence(word) or word.endswith(";") or (
                    word.endswith(",") and not _next_is_suffix(text, tok[2], hi)):
                break
            continue
        break
    while run and run[-1][0].lower() in _CONNECTORS:
        run.pop()
    if not run:
        return "", pos
    name = text[run[0][1]:run[-1][2]]
    if _ends_sentence(run[-1][0]) or name.endswith((",", ";")):
        name = name[:-1]
    return name, run[0][1] + len(name)


def _next_is_suffix(text: str, pos: int, hi: int) -> bool:
    nxt = _tokens(text, pos, hi)
    return bool(nxt) and nxt[0][0].lower().rstrip(",") in _NAME_SUFFIXES + ("llc", "inc", "lp")


def _initials(words: list[str]) -> str:
    return "".join(w.lstrip("\"'“")[0] for w in words if w.lower() not in _CONNECTORS and w[:1].isalnum())


def _trim_to_initials(name: str, short: str) -> str:
    """The shortest trailing run of ``name`` whose initials spell ``short``; ``name`` itself when none does."""
    words = name.split()
    for i in range(len(words) - 1, -1, -1):
        if _initials(words[i:]).upper() == short:
            return " ".join(words[i:])
    return name


def _dbas(text: str) -> list[Alias]:
    found: list[Alias] = []
    taken: list[tuple[int, int]] = []
    for marker in DBA_MARKERS:
        for m in re.finditer(rf"(?<![\w/]){marker}(?![\w/])\.?", text, re.I):
            if any(a <= m.start() < b for a, b in taken):
                continue
            legal, legal_start = _name_before(text, m.start())
            trade, _ = _name_after(text, m.end() + len(text[m.end():]) - len(text[m.end():].lstrip(" \t")))
            if not legal or not trade:
                continue
            taken.append((m.start(), m.end()))
            found.append(Alias(alias=legal, name=trade, kind=AliasKind.DBA,
                               start=legal_start, end=legal_start + len(legal)))
    return found


def _parentheticals(text: str) -> list[Alias]:
    found: list[Alias] = []
    for m in _PAREN.finditer(text):
        short = m.group(1) or m.group(2)
        if short in NOT_SHORT_FORMS:
            continue
        before = text[max(0, m.start() - 40):m.start()].lower()
        if any(k in before.split("\n")[-1] for k in DEFINED_TERM_KEYWORDS):
            continue
        name, _ = _name_before(text, m.start())
        if not name or name.split()[-1].upper() in DOCUMENT_WORDS:
            continue
        if short.isupper():
            name = _trim_to_initials(name, short)
        start = m.start(1) if m.group(1) else m.start(2)
        found.append(Alias(alias=short, name=name, kind=AliasKind.PARENTHETICAL, start=start, end=start + len(short)))
    return found


def _label_name(text: str, label: str) -> str:
    """The full name a role label stands for: a form line "Label: Name", else the longest mixed-case name it starts."""
    form = re.search(rf"(?mi)^[ \t]*{re.escape(label)}[ \t]*:[ \t]*(\S.*)$", text)
    if form:
        name, _ = _name_after(text, form.start(1))
        if name:
            return name
    words = label.split()
    best = ""
    pattern = r"\b" + r"\s+".join(re.escape(w) for w in words) + r"\b"
    for m in re.finditer(pattern, text, re.I):
        if m.group().isupper():
            continue  # the label itself, or a letterhead in capitals
        name, _ = _name_after(text, m.start())
        if name.lower().startswith(label.lower()) and len(name) > len(best):
            best = name
    return best


def _is_party_label(text: str, label: str) -> bool:
    if label in FORM_LABELS:
        return False
    if label in ROLE_WORDS:
        return True
    pattern = r"\b" + r"\s+".join(re.escape(w) for w in label.split()) + r"\b"
    return any(not m.group().isupper() for m in re.finditer(pattern, text, re.I))


def _role_labels(text: str) -> list[Alias]:
    found: list[Alias] = []
    names: dict[str, str] = {}
    for m in _LABEL_LINE.finditer(text):
        label = re.sub(r"\s+", " ", m.group(1))
        if not _is_party_label(text, label):
            continue
        if label not in names:
            names[label] = _label_name(text, label)
        found.append(Alias(alias=label, name=names[label], kind=AliasKind.ROLE_LABEL, start=m.start(1), end=m.end(1)))
    return found


def find_aliases(text: str) -> list[Alias]:
    """Every dba, parenthetical short form, and role label in ``text``, in the order they appear."""
    return sorted(_dbas(text) + _parentheticals(text) + _role_labels(text), key=lambda a: (a.start, a.end))


def aliases_of(name: str, aliases: list[Alias]) -> list[str]:
    """Every other name the party called ``name`` goes by, following aliases both ways (case-insensitive)."""
    group = {name.lower()}
    changed = True
    while changed:
        changed = False
        for a in aliases:
            if not a.name:
                continue
            pair = {a.alias.lower(), a.name.lower()}
            if pair & group and not pair <= group:
                group |= pair
                changed = True
    out: list[str] = []
    for a in aliases:
        for n in (a.alias, a.name):
            if n and n.lower() in group and n.lower() != name.lower() and n not in out:
                out.append(n)
    return out


def role_sections(text: str) -> list[RoleSection]:
    """The lines under each role label, up to the next label, a blank line, or a line that is not a sentence."""
    out: list[RoleSection] = []
    labels = [a for a in find_aliases(text) if a.kind is AliasKind.ROLE_LABEL]
    for i, label in enumerate(labels):
        stop = labels[i + 1].start if i + 1 < len(labels) else len(text)
        pos = text.find("\n", label.end)
        while 0 <= pos < stop:
            lo = pos + 1
            hi = text.find("\n", lo)
            hi = len(text) if hi < 0 else hi
            line = text[lo:hi].strip()
            if not line or lo >= stop or not _SENTENCE_END.search(line):
                break
            offset = lo + text[lo:hi].index(line)
            out.append(RoleSection(label=label, text=line, start=offset, end=offset + len(line)))
            pos = hi
    return out


__all__ = [
    "AliasKind",
    "Alias",
    "RoleSection",
    "DBA_MARKERS",
    "DEFINED_TERM_KEYWORDS",
    "NOT_SHORT_FORMS",
    "DOCUMENT_WORDS",
    "FORM_LABELS",
    "ROLE_WORDS",
    "find_aliases",
    "aliases_of",
    "role_sections",
]
