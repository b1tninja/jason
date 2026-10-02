"""What a contract's text shows about its signing: e-signature stamps, envelope certificates, and blank signature lines.

A signature drawn or pasted as an image leaves nothing in the text, so an unsigned reading is a lead, not a finding of
fact. What the text can show:

- an Adobe Acrobat Sign stamp beside the signature: ``Pat Example (Nov 8, 2022 07:40 PST)``, often followed by the
  signer's name, title, and date again;
- a DocuSign envelope: ``DocuSign Envelope ID: ...`` stamped on every page (the document went through DocuSign, not
  that it was finished), dated stamps ``1/13/2022 | 1:21 PM PST`` beside the signatures, ``DocuSigned by:`` over a
  signature image, and the Certificate of Completion (``Status: Completed``, each signer's ``Signed:`` timestamp);
- a PandaDoc Signature Certificate (``Document completed by all parties on:``, each signer's ``Signed:``);
- a vendor portal's own acceptance (``Customer signed on: ...``, a typed name beside "I have read, understood and
  accept");
- blank lines where a signature, name, or date belongs (``By:______``, ``DATED: ____``).

Nothing here registers a model; the contract, proposal, lease, and settlement models share it.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from enum import Enum

from jason.community.document_models import dates_in, squash
from jason.community.invoices import parse_date


class SignMethod(Enum):
    ADOBE_SIGN = "adobe_sign"      # Adobe Acrobat Sign stamp
    DOCUSIGN = "docusign"          # DocuSign stamp, certificate, or "DocuSigned by"
    PANDADOC = "pandadoc"          # PandaDoc signature certificate
    PORTAL = "portal"              # a vendor portal's own e-acceptance ("Customer signed on")
    TYPED = "typed"                # a name typed into an online form beside an acceptance box


class Execution(Enum):
    EXECUTED = "executed"            # a certificate says completed, or every side the form needs has signed
    SIGNED_BY_ONE = "signed_by_one"  # one party's signature shows; the form needs another
    NOT_IN_TEXT = "not_in_text"      # no signature shows in the text (an image signature would not)


@dataclass(frozen=True)
class Signature:
    name: str = ""
    signed: date | None = None
    title: str = ""
    method: SignMethod | None = None


@dataclass(frozen=True)
class Envelope:
    """An e-signature platform's certificate or stamped envelope."""

    method: SignMethod
    envelope_id: str
    completed: bool = False
    completed_on: date | None = None
    signers: tuple[Signature, ...] = ()


@dataclass(frozen=True)
class Signing:
    signatures: tuple[Signature, ...] = ()
    envelopes: tuple[Envelope, ...] = ()
    blank_lines: int = 0

    @property
    def completed(self) -> bool:
        return any(e.completed for e in self.envelopes)

    @property
    def signed_on(self) -> date | None:
        days = [s.signed for s in self.signatures if s.signed] + [e.completed_on for e in self.envelopes if e.completed_on]
        return max(days) if days else None

    def signers(self) -> int:
        """Distinct signers the text shows: named ones by name, unnamed ones by their date."""
        named = {s.name.casefold() for s in self.signatures if s.name}
        unnamed = {(s.signed, s.title) for s in self.signatures if not s.name and s.signed}
        return len(named) + (len(unnamed) if len(named) < 2 else 0)

    def execution(self, *, one_side: bool) -> Execution:
        """``one_side``: the form needs only the customer's signature (an accepted proposal, a vendor's form)."""
        if self.completed:
            return Execution.EXECUTED
        n = self.signers()
        if n >= 2 or (n == 1 and one_side):
            return Execution.EXECUTED
        return Execution.SIGNED_BY_ONE if n == 1 else Execution.NOT_IN_TEXT


_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
_NAME = r"[A-Z][A-Za-z.'\-]+(?: [A-Z][A-Za-z.'\-]+){1,3}"
ADOBE_STAMP = re.compile(rf"^[ \t]*({_NAME}) \(({_MONTH} \d{{1,2}}, \d{{4}}) \d{{1,2}}:\d{{2}}(?::\d{{2}})?(?: ?[AP]M)? ?[A-Z]{{2,4}}\)[ \t]*$",
                         re.M)
DOCUSIGN_ID = re.compile(r"Docu[Ss]ign Envelope ID:\s*([0-9A-F]{8}-[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4,5}-[0-9A-F]{12})", re.I)
DOCUSIGN_DATE = re.compile(r"^[ \t]*(\d{1,2}/\d{1,2}/\d{4}) \| \d{1,2}:\d{2} [AP]M [A-Z]{2,4}[ \t]*$", re.M)
TITLE = re.compile(r"^(?:Vice President|President|Secretary|Treasurer|CEO|CFO|COO|Chief [A-Z][a-z]+ Officer|General Counsel|"
                   r"Director|Board Member|Operations Manager|General Manager|Manager|Owner|Partner|Member|Estimator|Principal)$")
_BLANK = re.compile(r"(?im)^[ \t]*(?:client\s+)?(?:signature|by|date|dated|date signed|name|title|print(?:ed)? name)[ \t]*:?[ \t]*_{4,}")
_RULE = re.compile(r"(?m)^[ \t]*_{8,}[ \t]*$")


def _near_dates(lines: list[str]) -> list[date]:
    return [d for line in lines for d in dates_in(line)]


def _adobe(text: str) -> list[Signature]:
    """Adobe Sign stamps, with the title and any unnamed co-signer (a title and a date) printed beneath them."""
    out: list[Signature] = []
    for m in ADOBE_STAMP.finditer(text):
        name, signed = m.group(1), parse_date(m.group(2))
        after = [line.strip() for line in text[m.end():].split("\n")[1:9]]
        titles: list[tuple[str, date | None]] = []
        for i, line in enumerate(after):
            if ADOBE_STAMP.match(line) or DOCUSIGN_ID.search(line) or line.startswith("Page "):
                break
            if TITLE.match(line):
                follow = _near_dates(after[i + 1: i + 3])
                titles.append((line, follow[0] if follow else None))
        title = titles[0][0] if titles else ""
        out.append(Signature(name, signed, title, SignMethod.ADOBE_SIGN))
        for extra_title, extra_date in titles[1:]:
            out.append(Signature("", extra_date, extra_title, SignMethod.ADOBE_SIGN))
    return out


def _docusign_certificates(text: str) -> list[Envelope]:
    out = []
    for block in re.split(r"Certificate Of Completion", text)[1:]:
        envelope = re.search(r"Envelope Id:\s*([0-9A-F]{32})", block, re.I)
        status = re.search(r"^Status:\s*(\w+)", block, re.M)
        lines = [line.strip() for line in block.split("In Person Signer Events")[0].split("\n")]
        signers: list[Signature] = []
        current, title = "", ""
        for i, line in enumerate(lines):
            if "@" in line and i and re.fullmatch(_NAME, lines[i - 1]):
                current, title = lines[i - 1], ""
                for follow in lines[i + 1: i + 4]:
                    if TITLE.match(follow):
                        title = follow
                        break
            m = re.match(r"Signed:\s*(\d{1,2}/\d{1,2}/\d{4})", line)
            if m and current:
                signers.append(Signature(current, parse_date(m.group(1)), title, SignMethod.DOCUSIGN))
                current = ""
        done = re.search(r"\nCompleted\s*\n\s*Security Checked\s*\n\s*(\d{1,2}/\d{1,2}/\d{4})", block)
        out.append(Envelope(SignMethod.DOCUSIGN, envelope.group(1) if envelope else "",
                            bool(status and status.group(1).lower() == "completed"),
                            parse_date(done.group(1)) if done else None, tuple(signers)))
    return out


def _pandadoc(text: str) -> list[Envelope]:
    out = []
    for block in re.split(r"Signature Certificate", text)[1:]:
        if "PandaDoc" not in block and "Reference number" not in block:
            continue
        ref = re.search(r"Reference number:\s*([A-Z0-9-]+)", block)
        done = re.search(r"completed by all parties on:\s*(\d{1,2} [A-Za-z]{3} \d{4})", block)
        lines = [line.strip() for line in block.split("\n")]
        signers: list[Signature] = []
        current = ""
        for i, line in enumerate(lines):
            if line.startswith("Email:") and i and re.fullmatch(_NAME, lines[i - 1]):
                current = lines[i - 1]
            if line == "Signed:" and current and i + 1 < len(lines):
                m = re.match(r"(\d{1,2} [A-Za-z]{3} \d{4})", lines[i + 1])
                if m:
                    signers.append(Signature(current, parse_date(m.group(1)), "", SignMethod.PANDADOC))
                    current = ""
        out.append(Envelope(SignMethod.PANDADOC, ref.group(1) if ref else "", bool(done), parse_date(done.group(1)) if done else None,
                            tuple(signers)))
    return out


def _docusign_anchor_values(text: str) -> list[Signature]:
    """DocuSign fills anchor tags (``\\FSSignature1\\``, ``\\FSDateSigned1\\``) and prints the values at the page's end."""
    at = text.rfind("\\FSDateSigned")
    if at < 0:
        return []
    tail = text[at:]
    stamp = DOCUSIGN_ID.search(tail)
    if not stamp:
        return []
    page = tail[stamp.end():].split("\n\n")[0]
    lines = [line.strip() for line in page.split("\n") if line.strip()]
    names = [line for line in lines if re.fullmatch(_NAME, line) and not TITLE.match(line)]
    days = _near_dates(lines)
    titles = [line for line in lines if TITLE.match(line)]
    return [Signature(names[i] if i < len(names) else "", d, titles[i] if i < len(titles) else "", SignMethod.DOCUSIGN)
            for i, d in enumerate(days)]


def read_signing(text: str) -> Signing:
    text = text or ""
    signatures = _adobe(text)
    envelopes = _docusign_certificates(text) + _pandadoc(text)
    # Every page carries the stamp and OCR varies it ("A59A", "AS59A"): one envelope per first eight characters, the
    # commonest spelling kept.
    stamped = Counter(m.group(1).upper() for m in DOCUSIGN_ID.finditer(text))
    certified = {e.envelope_id.upper()[:8] for e in envelopes}
    for envelope_id, _n in stamped.most_common():
        if envelope_id[:8] not in certified:
            certified.add(envelope_id[:8])
            envelopes.append(Envelope(SignMethod.DOCUSIGN, envelope_id))
    for e in envelopes:
        signatures += list(e.signers)
    if not any(e.signers for e in envelopes):
        stamped_days = sorted({parse_date(m.group(1)) for m in DOCUSIGN_DATE.finditer(text)} - {None})
        signatures += [Signature("", d, "", SignMethod.DOCUSIGN) for d in stamped_days]
    signatures += _docusign_anchor_values(text)
    m = re.search(r"DocuSigned by:(.{0,160})", text, re.S)
    if m:
        # The signature box's "DATE: Nov-21-2023" follows the stamp in one OCR's reading order and precedes it in
        # another's ("CLIENT SIGNATURE: | DATE: Nov-21-2023" on the line above).
        before = text[max(0, m.start() - 120):m.start()]
        dated = (re.search(rf"DATE:\s*({_MONTH})-(\d{{1,2}})-(\d{{4}})", m.group(1))
                 or re.search(rf"DATE:\s*({_MONTH})-(\d{{1,2}})-(\d{{4}})\s*$", before))
        day = parse_date(f"{dated.group(1)} {dated.group(2)}, {dated.group(3)}") if dated else (_near_dates([m.group(1)]) or [None])[0]
        signatures.append(Signature("", day, "", SignMethod.DOCUSIGN))
    m = re.search(r"Customer signed on:\s*(?:\w+day,?)?\s*(\d{1,2}/\d{1,2}/\d{4})", text)
    if m:
        signatures.append(Signature("customer", parse_date(m.group(1)), "", SignMethod.PORTAL))
    m = re.search(r"Please enter your First and Last Name here[^\S\n]+(" + _NAME + r")", text)
    if m and re.search(r"I have read, understood and accept", text, re.I):
        signatures.append(Signature(m.group(1), None, "", SignMethod.TYPED))
    # A platform's audit line under each signature ("Signed on 11/18/2025 02:36:51 UTC"); the signers stay unnamed.
    for i, m in enumerate(re.finditer(r"^Signed on (\d{1,2}/\d{1,2}/\d{4}) \d{1,2}:\d{2}(?::\d{2})? ?(?:UTC|[A-Z]{2,4})", text, re.M), 1):
        signatures.append(Signature(f"signer {i}", parse_date(m.group(1)), "", SignMethod.PORTAL))
    unique: dict[tuple, Signature] = {}
    for s in signatures:
        unique.setdefault((s.name.casefold(), s.signed, s.title if not s.name else ""), s)
    return Signing(tuple(unique.values()), tuple(envelopes), len(_BLANK.findall(text)) + len(_RULE.findall(text)))


def blank_date_after(label: str, text: str) -> bool:
    """The text leaves the date after ``label`` blank (``commencing on ______``)."""
    return bool(re.search(label + r"\s*_{4,}", squash(text), re.I))


__all__ = ["SignMethod", "Execution", "Signature", "Envelope", "Signing", "read_signing", "blank_date_after", "ADOBE_STAMP"]
