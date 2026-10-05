"""Who signed a contract, for which side, with what title, and when: the contract's signature block.

A board asks of every contract on file whether its copy is signed, and by whom. The answer is in the signature block,
which a PDF's text layer gives in a few recurring shapes:

- labelled fields: "By: ____  Name: ____  Title: ____  Date: ____", "ACCEPTED BY: ____", "Name & Title: ____",
  "Its: ____", "Company: ____", "Customer signature ____ Date ____", "Signed for the Contractor: ____", and a
  parenthetical under the blank that names the field or the party ("____ (signature) ____ (print name)",
  "____ (Owner or Agent)");
- a party named on the line before the "By:" line, or as a role label on the same line ("MANAGER: Sample Co.  By:"),
  and a bare title on the line after it ("President");
- an e-signature stamp ("Pat Example (Apr 16, 2026 23:11 PDT)"), which a signing service writes over the form; its
  text lands after the form's blank fields, followed by the values typed into them (a date, the printed name, the
  title). The stamp fills the nearest unsigned form block before it (``STAMP_REACH`` lines at most);
- a signing service's audit trail or certificate ("Final Audit Report", "Certificate Of Completion"): read only for its
  signer and signing date ("e-signed by ... Signature Date:", "Signer Events ... Signature Adoption ... Signed:"),
  and kept only for a signer no block above already names. Its other lines ("By: <sender>") are never fields.

``signature_blocks(text)`` gives one ``SignatureBlock`` per signing side, in the order of the text. A blank field
("______") is unsigned: the block is kept with ``signed`` False and ``signer`` "" (or the printed name, when only the
name was filled), so a reader can say the copy is unsigned. Dates come back ISO (YYYY-MM-DD) or "".

A reading is a lead. jason reads which words sit in which field; whether a person had authority to sign for a side,
or whether an audit trail's signature binds, is a reading for the board and counsel. A letter's closing
("Sincerely, ... Estimator") is not a signature block and is not read here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class BlockKind(Enum):
    FORM = "form"  # labelled fields on the page, filled or blank
    E_SIGNATURE = "e-signature"  # a stamp with no form block to fill
    AUDIT = "audit trail"  # a signing service's record of the signature


class Field(Enum):
    SIGN = "signature"
    NAME = "name"
    TITLE = "title"
    NAME_TITLE = "name and title"
    DATE = "date"
    PARTY = "party"


@dataclass(frozen=True)
class SignatureBlock:
    """One signing side.

    ``party_words`` are the words that name the side as written ("Example Community Association", "Owner",
    "Contractor"), "" when the block names none. ``signer`` is the signer's (or printed) name, "" when blank.
    ``signed`` is True only when the signature field holds a mark, an e-signature stamp, or an audit record.
    ``start`` and ``end`` span the block in the text.
    """

    party_words: str
    signer: str
    title: str
    date: str
    signed: bool
    start: int
    end: int
    kind: BlockKind = BlockKind.FORM


@dataclass(frozen=True)
class Label:
    """A field label: the pattern and the field it opens.

    ``line_start`` labels count only at the start of a line, after an optional party or role label ("CONTRACTOR",
    "Customer", "Example Roofing, Inc.,"), or after another field on the same line; mid-sentence they are prose.
    """

    pattern: str
    field: Field
    line_start: bool = False


# Order matters where two labels could start at the same place: the longer label first.
LABELS: tuple[Label, ...] = (
    Label(r"name\s*(?:&|and)\s*title\s*:", Field.NAME_TITLE),
    Label(r"(?:docu)?signed\s+for\s+(?P<for>[A-Za-z][A-Za-z .'&-]{1,40}?)\s*:", Field.SIGN),
    Label(r"docusigned\s+by\s*:", Field.SIGN),
    Label(r"(?:accepted|approved|agreed)(?:\s+(?:and\s+(?:agreed|accepted)|by))?\s*:", Field.SIGN),
    Label(r"(?:(?P<who>[A-Za-z]+(?:'s)?)\s+)?signature\s*(?::|(?=_{3}))", Field.SIGN),
    Label(r"signed\s*:", Field.SIGN),
    Label(r"by\s*(?::|(?=_{3}))", Field.SIGN, line_start=True),
    Label(r"(?:print(?:ed)?\s+)?name\s*:", Field.NAME),
    Label(r"(?:title|its)\s*:", Field.TITLE),
    Label(r"date(?:d)?\s*(?::|(?=_{3}))", Field.DATE),
    Label(r"(?:company|entity|firm)\s*:", Field.PARTY),
)

_LABEL_RE = re.compile(
    r"(?<![A-Za-z])(?:" + "|".join(f"(?P<l{i}>{lab.pattern})" for i, lab in enumerate(LABELS)) + ")",
    re.IGNORECASE,
)
# "Example Home Services, by ____": the party, then ", by" before a blank.
_COMMA_BY = re.compile(r"^(?P<party>[A-Z][^:_\n]{1,60}?),\s+by\s*:?\s*(?=_{3})")
# "MANAGER: Sample Co.  By: ____": an uppercase role label that opens a line holding a signature field.
_ROLE = re.compile(r"^(?P<role>[A-Z][A-Z&' -]{1,30}[A-Z]):\s*(?P<name>[^_\n]*?)\s*(?=\b(?i:by|signed|signature)\b)")
_BLANK = re.compile(r"_{3,}")

# Words right before "by" that name who made, sent, or checked the paper, not who signed it: "Prepared By: ...",
# "Submitted by: ...", "Approved as to form by: ...". A "By:" after any of them is not a signature field.
BY_NOT_SIGNING: tuple[str, ...] = (
    r"prepared",
    r"submitted",
    r"inspected",
    r"sold",
    r"quoted",
    r"estimated",
    r"reviewed",
    r"approved\s+as\s+to\s+form",
    r"sent",
    r"installed",
)
_BY_DENIED = re.compile(r"(?<![A-Za-z])(?:" + "|".join(BY_NOT_SIGNING) + r")\s*$", re.IGNORECASE)
# A party or role label before a line-start label: up to six words, the first capitalized ("CONTRACTOR",
# "Customer", "For the Association").
_PARTY_WORD = r"(?:[A-Z][\w'&.,-]*|the|for|of|and)"
_BY_PARTY = re.compile(rf"\s*[A-Z][\w'&.,-]*(?:\s+{_PARTY_WORD}){{0,5}}\s*:?\s*")
_PAREN =re.compile(r"\(([^()]{1,40})\)")

# Words in a parenthetical under a blank that name the field rather than the party.
PAREN_FIELDS: tuple[tuple[str, Field], ...] = (
    (r"(?:authorized\s+)?signature", Field.SIGN),
    (r"(?:print(?:ed)?\s+)?name", Field.NAME),
    (r"title", Field.TITLE),
    (r"date", Field.DATE),
)

AUDIT_HEADERS = re.compile(r"^\s*(?:final audit report|certificate of completion|audit trail)\b", re.IGNORECASE | re.M)
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_NAME = r"[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,4}"
_MONTH_DATE = r"[A-Z][a-z]{2,8}\.?\s+\d{1,2},\s*\d{4}"
_STAMP = re.compile(
    rf"^\s*(?P<name>{_NAME})\s*\((?P<date>{_MONTH_DATE})"
    r"(?:[ ,]+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?(?:\s*[A-Z]{2,5})?)?\)\s*$"
)
# On a line of its own, a stamp must carry its time ("23:11 PDT"), so "Annual Meeting (Apr 16, 2026)" is no stamp.
_STAMP_LINE = re.compile(
    rf"^\s*(?P<name>{_NAME})\s*\((?P<date>{_MONTH_DATE})"
    r"[ ,]+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?(?:\s*[A-Z]{2,5})?\)\s*$"
)
_ADOBE = re.compile(rf"e-signed by\s+(?P<name>{_NAME})\s*\([^)\n]*\)\s*\n?.{{0,80}}?Signature Date:\s*(?P<date>\S+)",
                    re.IGNORECASE | re.DOTALL)
_DOCUSIGN = re.compile(rf"Signature\s+Timestamp\s+(?P<name>{_NAME}?)\s+Signature Adoption:.{{0,300}}?"
                       r"Signed:\s*(?P<date>\d{1,2}/\d{1,2}/\d{2,4})", re.IGNORECASE | re.DOTALL)
_COMPANY_END = re.compile(r"\b(?:inc|co|corp|ltd|llc|lp|llp|pc)\.?$", re.IGNORECASE)

STAMP_REACH = 15
"""How many lines after an unsigned form block an e-signature stamp may sit and still fill it."""


def iso_date(written: str) -> str:
    """A written date as YYYY-MM-DD: "04/16/2026", "4/16/26", "2026-04-16", "Apr 16, 2026", "16 April 2026"; else ""."""
    s = written.strip().strip(",.")
    if m := re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})\b", s):
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
    elif m := re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\b", s):
        mo, d, y = int(m[1]), int(m[2]), int(m[3])
        y += 2000 if y < 100 else 0
    elif m := re.match(r"^([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b", s):
        mo, d, y = _month(m[1]), int(m[2]), int(m[3])
    elif m := re.match(r"^(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b", s):
        d, mo, y = int(m[1]), _month(m[2]), int(m[3])
    else:
        return ""
    if not (1 <= mo <= 12 and 1 <= d <= 31 and 1900 <= y <= 2200):
        return ""
    return f"{y:04d}-{mo:02d}-{d:02d}"


def _month(word: str) -> int:
    w = word[:3].lower()
    return _MONTHS.index(w) + 1 if w in _MONTHS else 0


@dataclass(frozen=True)
class _Found:
    field: Field
    value: str  # the text written in the field, blanks removed; "" when blank
    after: str  # text after the blank: a parenthetical or a trailing title
    party: str  # party words carried by the label itself ("Signed for the X", "Customer signature")
    raw: str  # the field's text as written, blanks included
    start: int
    end: int


@dataclass
class _Draft:
    party: str = ""
    signer: str = ""
    name: str = ""
    title: str = ""
    date: str = ""
    signed: bool = False
    start: int = 0
    end: int = 0
    first_line: int = 0
    last_line: int = 0
    kind: BlockKind = BlockKind.FORM

    def block(self) -> SignatureBlock:
        return SignatureBlock(self.party, self.name or self.signer, self.title, self.date, self.signed,
                              self.start, self.end, self.kind)


def _clean_party(words: str) -> str:
    words = re.sub(r"^\s*the\s+", "", words.strip(), flags=re.IGNORECASE)
    words = re.sub(r"'s$", "", words).strip(" ,:")
    return words if _COMPANY_END.search(words) else words.rstrip(".")


def _split_value(raw: str) -> tuple[str, str]:
    """The filled text before any blank, and the text after the last blank."""
    if not _BLANK.search(raw):
        return raw.strip(), ""
    parts = _BLANK.split(raw)
    return parts[0].strip(), parts[-1].strip()


def _label(m: re.Match) -> Label:
    return LABELS[next(int(k[1:]) for k, v in m.groupdict().items() if v is not None and re.fullmatch(r"l\d+", k))]


def _starts_line(line: str, lead: int, m: re.Match, after_field: bool, party_lead: bool) -> bool:
    """Whether a ``line_start`` label sits where a signature field opens: at the start of the line, after a party or
    role label, or after another field; never after a ``BY_NOT_SIGNING`` word ("Prepared By:")."""
    before = line[:m.start()]
    if _BY_DENIED.search(before):
        return False
    if after_field or party_lead:
        return True
    prefix = line[lead:m.start()]
    return not prefix.strip() or bool(_BY_PARTY.fullmatch(prefix))


def _fields(line: str, offset: int) -> list[_Found]:
    found: list[_Found] = []
    lead = 0
    party_lead = ""
    if m := _COMMA_BY.match(line):
        party_lead = m["party"]
    elif (m := _ROLE.match(line)) and not _LABEL_RE.match(line):
        party_lead = m["name"].strip() or m["role"].title()
        lead = m.end()
    matches: list[tuple[re.Match, Label]] = []
    for m in _LABEL_RE.finditer(line, lead):
        label = _label(m)
        if label.line_start:
            if not _starts_line(line, lead, m, bool(matches), bool(party_lead)):
                continue
            if not matches and not party_lead:
                # "CONTRACTOR By: ____": the party or role label before the field names the side.
                party_lead = line[lead:m.start()].strip(" :,")
        matches.append((m, label))
    for i, (m, label) in enumerate(matches):
        end = matches[i + 1][0].start() if i + 1 < len(matches) else len(line)
        raw = line[m.end():end]
        value, after = _split_value(raw)
        groups = m.groupdict()
        party = groups.get("for") or groups.get("who") or ""
        if party.lower() in {"authorized", "your", "my", "his", "her", "their", "its"}:
            party = ""
        if i == 0 and party_lead and label.field is Field.SIGN:
            party = party or party_lead
        found.append(_Found(label.field, value, after, _clean_party(party), raw, offset + m.start(), offset + end))
    if party_lead and not found:
        return []
    if m := _COMMA_BY.match(line):
        if not any(f.field is Field.SIGN for f in found):
            raw = line[m.end():]
            value, after = _split_value(raw)
            found.insert(0, _Found(Field.SIGN, value, after, _clean_party(m["party"]), raw, offset, offset + len(line)))
    return found


def _paren_field(words: str) -> Field | None:
    for pattern, field in PAREN_FIELDS:
        if re.fullmatch(pattern, words.strip(), re.IGNORECASE):
            return field
    return None


_PAREN_PAIR = re.compile(r"([^()]*)\(([^()]{1,40})\)")


def _paren_layout(draft: _Draft, raw: str) -> bool:
    """The layout that names each field under its blank: "____ (signature) ____ (print name) ____ (date)".

    Each parenthetical names the field (or the party) of the text before it. False when no parenthetical names a field.
    """
    pairs = _PAREN_PAIR.findall(raw)
    if not any(_paren_field(words) for _, words in pairs):
        return False
    for written, words in pairs:
        value = _BLANK.sub(" ", written).strip()
        field = _paren_field(words)
        if field is None:
            if not draft.party:
                draft.party = _clean_party(words)
        elif field is Field.SIGN and value:
            draft.signer, draft.signed = re.sub(r"^/s/\s*", "", value), True
        elif field is Field.NAME and value:
            draft.name = value
        elif field is Field.TITLE and value:
            draft.title = value
        elif field is Field.DATE and value:
            draft.date = iso_date(value) or draft.date
    return True


def _apply(draft: _Draft, f: _Found) -> None:
    value = f.value
    if f.field is Field.SIGN:
        if f.party and not draft.party:
            draft.party = f.party
        if _paren_layout(draft, f.raw):
            return
        if value:
            if s := _STAMP.match(value):
                draft.signer, draft.date = s["name"], draft.date or iso_date(s["date"])
            else:
                draft.signer = re.sub(r"^/s/\s*", "", value).strip()
            draft.signed = True
        for words in _PAREN.findall(f.after):
            if _paren_field(words) is None and not draft.party:
                draft.party = _clean_party(words)
        rest = _PAREN.sub("", f.after).strip()
        if rest and not draft.title and _is_title(rest):
            draft.title = rest
    elif f.field is Field.NAME and value:
        draft.name = value
    elif f.field is Field.TITLE and value:
        draft.title = value
    elif f.field is Field.NAME_TITLE and value:
        name, _, title = value.partition(",")
        draft.name, draft.title = name.strip(), draft.title or title.strip()
    elif f.field is Field.DATE and value:
        draft.date = iso_date(value) or draft.date
    elif f.field is Field.PARTY and value and not draft.party:
        draft.party = _clean_party(value)


def _is_title(line: str) -> bool:
    words = line.split()
    return (0 < len(words) <= 4 and line[0].isupper() and not re.search(r"[\d_:@]", line)
            and not line.rstrip().endswith("."))


def _is_party_line(line: str) -> bool:
    s = line.strip()
    if not s or not s[0].isupper() or re.search(r"[_:@]", s) or len(s.split()) > 8:
        return False
    return not s.endswith(".") or bool(_COMPANY_END.search(s))


def _lines(text: str) -> list[tuple[int, str]]:
    out, pos = [], 0
    for line in text.split("\n"):
        out.append((pos, line))
        pos += len(line) + 1
    return out


def _form_blocks(lines: list[tuple[int, str]], stop: int) -> list[_Draft]:
    drafts: list[_Draft] = []
    current: _Draft | None = None
    pending: list[_Found] = []
    for n, (offset, line) in enumerate(lines):
        if offset >= stop:
            break
        if not line.strip():
            current, pending = None, []
            continue
        found = _fields(line, offset)
        if not found:
            # A bare title on the line right after the signature line; the signer's name printed again under the
            # signature is not the title, and the title may follow it.
            s = line.strip()
            if current is not None and n == current.last_line + 1 and not current.title and _is_title(s) \
                    and not _STAMP_LINE.match(line):
                if s.lower() not in {current.signer.lower(), current.name.lower()} - {""}:
                    current.title = s
                current.end, current.last_line = offset + len(line), n
            current, pending = (current if current is not None and current.last_line == n else None), []
            continue
        for f in found:
            if f.field is Field.SIGN:
                current = _Draft(start=f.start, end=f.end, first_line=n, last_line=n)
                if pending:
                    current.start = pending[0].start
                    for p in pending:
                        _apply(current, p)
                    pending = []
                elif not f.party and n > 0 and line.lstrip().lower().startswith(("by", "signature")) \
                        and _is_party_line(lines[n - 1][1]):
                    current.party = _clean_party(lines[n - 1][1])
                    current.start = lines[n - 1][0]
                _apply(current, f)
                drafts.append(current)
            elif current is not None:
                _apply(current, f)
                current.end, current.last_line = f.end, n
            else:
                pending.append(f)
    return drafts


def _stamps(lines: list[tuple[int, str]], stop: int, drafts: list[_Draft]) -> list[_Draft]:
    """E-signature stamps: each fills the nearest unsigned form block before it, else stands as its own block."""
    out: list[_Draft] = []
    for n, (offset, line) in enumerate(lines):
        if offset >= stop:
            break
        s = _STAMP_LINE.match(line)
        if not s or any(d.first_line <= n <= d.last_line for d in drafts):
            continue
        name, date, title, end, last = s["name"], iso_date(s["date"]), "", offset + len(line), n
        # The values typed into the form follow the stamp: a date, the printed name, then the title.
        k, saw_name = n + 1, False
        while k < len(lines) and k <= n + 3 and lines[k][0] < stop:
            nxt = lines[k][1].strip()
            if iso_date(nxt) and len(nxt.split()) <= 4:
                date = date or iso_date(nxt)
            elif nxt == name:
                saw_name = True
            elif saw_name and _is_title(nxt):
                title = nxt
                end, last = lines[k][0] + len(lines[k][1]), k
                break
            else:
                break
            end, last = lines[k][0] + len(lines[k][1]), k
            k += 1
        target = None
        for d in reversed(drafts):
            if d.first_line > n:
                continue
            if not d.signed and not d.signer and n - d.last_line <= STAMP_REACH:
                target = d
            break
        if target is None:
            target = _Draft(start=offset, first_line=n, kind=BlockKind.E_SIGNATURE)
            out.append(target)
        target.signer, target.signed = name, True
        target.date = target.date or date
        target.title = target.title or title
        target.end, target.last_line = end, last
    return out


def _audit(text: str, stop: int, known: set[str]) -> list[_Draft]:
    out: list[_Draft] = []
    for pattern in (_ADOBE, _DOCUSIGN):
        for m in pattern.finditer(text, stop):
            name = m["name"].strip()
            if name.lower() in known:
                continue
            known.add(name.lower())
            out.append(_Draft(signer=name, date=iso_date(m["date"]), signed=True, start=m.start(), end=m.end(),
                              kind=BlockKind.AUDIT))
    return out


def signature_blocks(text: str) -> list[SignatureBlock]:
    """Each signing side's block in ``text``, in the order of the text; [] when the text has none."""
    header = AUDIT_HEADERS.search(text)
    stop = header.start() if header else len(text)
    lines = _lines(text)
    drafts = _form_blocks(lines, stop)
    drafts += _stamps(lines, stop, drafts)
    known = {d.signer.lower() for d in drafts if d.signer} | {d.name.lower() for d in drafts if d.name}
    drafts += _audit(text, stop, known)
    return [d.block() for d in sorted(drafts, key=lambda d: d.start)]


def signed_by(blocks: list[SignatureBlock]) -> tuple[SignatureBlock, ...]:
    """The blocks that hold a signature."""
    return tuple(b for b in blocks if b.signed)


__all__ = [
    "AUDIT_HEADERS",
    "BlockKind",
    "Field",
    "LABELS",
    "Label",
    "PAREN_FIELDS",
    "STAMP_REACH",
    "SignatureBlock",
    "iso_date",
    "signature_blocks",
    "signed_by",
]
