"""Who an email is from, read from the signature block at its end.

An owner writes "Thanks, Jane" from a personal address and her phone; a property manager signs with a title, a company,
an office line, and a DRE license; an escrow officer's mail ends in a wire-fraud warning. The signature says what kind
of party wrote, and jason's Gmail store (headers only) cannot.

Two pure steps, no network and no store:

- ``split_signature(text)`` cuts the quoted reply chain ("On ... wrote:", "-----Original Message-----", an Outlook
  "From: ... Sent:" header, ``>`` lines), then finds where the signature starts: a ``--`` delimiter, the last sign-off
  ("Best regards", "Thanks,", "Sincerely", "Respectfully"), a "Sent from my iPhone" line, or a confidentiality
  disclaimer, else a trailing block of short lines that carries a phone, a website, or a license. HTML is turned into
  text first; Gmail's ``gmail_signature`` and ``gmail_quote`` marks are kept as a delimiter and a cut.
- ``parse_signature(block)`` reads the block's structured fields only: a name, a title, a company, whether a phone and a
  street address are present (the number is kept only for a labeled business line on a professional's signature),
  the website, license numbers (DRE, CalBRE, CSLB, NMLS, State Bar, insurance, escrow), social and scheduling links (by
  kind), a business disclaimer, and the mobile marker. Then a role (``SignatureRole``) with a confidence and the cues
  that fired.

The role is a guess for a person to confirm: a named sender in ``mystique/senders.py`` outranks it, and an owner who
writes from work reads as a business. A miss stays unknown.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field
from enum import Enum
from html.parser import HTMLParser

from jason.community.sources import SourceKind

# Consumer mailbox providers: a sender here is likely an individual, but not always (a realtor on gmail.com).
CONSUMER_DOMAINS = frozenset((
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "rocketmail.com", "icloud.com", "me.com", "mac.com",
    "hotmail.com", "outlook.com", "live.com", "msn.com", "aol.com", "comcast.net", "att.net", "sbcglobal.net",
    "verizon.net", "cox.net", "charter.net", "frontier.com", "proton.me", "protonmail.com", "mail.com", "gmx.com",
))


class SignatureRole(Enum):
    PROPERTY_MANAGER = "property manager"            # manages an owner's rented unit
    ASSOCIATION_MANAGER = "association manager"      # manages an association (the association's own, or another's)
    REALTOR = "realtor"
    TITLE_ESCROW = "title or escrow"
    ATTORNEY = "attorney"
    INSURER = "insurer or agent"
    LENDER = "lender"
    VENDOR = "vendor or contractor"
    GOVERNMENT = "government"
    BUSINESS = "business, role unclear"
    INDIVIDUAL = "individual"
    UNKNOWN = "unknown"

    @property
    def source_kind(self) -> SourceKind | None:
        """The directory's kind for this role; None for a realtor or an unclear business (no ``SourceKind`` row)."""
        return _SOURCE_KIND.get(self)

    @property
    def professional(self) -> bool:
        return self not in (SignatureRole.INDIVIDUAL, SignatureRole.UNKNOWN)


R = SignatureRole
_SOURCE_KIND = {
    R.PROPERTY_MANAGER: SourceKind.PROPERTY_MANAGER, R.ASSOCIATION_MANAGER: SourceKind.MANAGER,
    R.TITLE_ESCROW: SourceKind.TITLE_ESCROW, R.ATTORNEY: SourceKind.LAW_FIRM, R.INSURER: SourceKind.INSURER,
    R.LENDER: SourceKind.BANK, R.VENDOR: SourceKind.VENDOR, R.GOVERNMENT: SourceKind.GOVERNMENT, R.INDIVIDUAL: SourceKind.OWNER,
}


class LicenseKind(Enum):
    DRE = "California DRE"
    CALBRE = "CalBRE (former DRE)"
    CSLB = "CSLB contractor"
    NMLS = "NMLS"
    BAR = "State Bar"
    INSURANCE = "insurance"
    ESCROW = "escrow"


@dataclass(frozen=True)
class License:
    kind: LicenseKind
    number: str


@dataclass(frozen=True)
class Phone:
    """A labeled business line ("office", "main", "direct", "fax", "toll-free"); a mobile or unlabeled number is never kept."""

    label: str
    number: str


@dataclass(frozen=True)
class Signature:
    name: str = ""
    title: str = ""
    company: str = ""
    has_phone: bool = False
    business_phones: tuple[Phone, ...] = ()
    website: str = ""
    licenses: tuple[License, ...] = ()
    has_address: bool = False
    links: tuple[str, ...] = ()          # kinds only: "linkedin", "calendly", ...
    disclaimer: bool = False
    mobile: bool = False                 # "Sent from my iPhone"
    role: SignatureRole = SignatureRole.UNKNOWN
    confidence: float = 0.0
    reasons: tuple[str, ...] = ()

    @property
    def fields(self) -> int:
        """How much the block said: the count of fields found (to keep the fullest of a sender's signatures)."""
        return sum(bool(v) for v in (self.name, self.title, self.company, self.has_phone, self.website, self.licenses,
                                     self.has_address, self.links, self.disclaimer))

    def to_dict(self, *, private: bool = False) -> dict:
        """The fields as JSON. ``private`` (an owner or another individual) keeps only the role, its confidence, the kinds
        of cue that fired, and the presence flags: no name, title, company, number, website, or link."""
        out = {"role": self.role.value, "confidence": self.confidence, "hasPhone": self.has_phone,
               "hasAddress": self.has_address, "disclaimer": self.disclaimer, "mobile": self.mobile}
        if private:
            out["reasons"] = sorted({r.split(":", 1)[0] for r in self.reasons})
            return out
        out.update({"name": self.name, "title": self.title, "company": self.company, "website": self.website,
                    "businessPhones": [{"label": p.label, "number": p.number} for p in self.business_phones],
                    "licenses": [{"kind": lic.kind.value, "number": lic.number} for lic in self.licenses],
                    "links": list(self.links), "reasons": list(self.reasons)})
        return out


# --- HTML to text -------------------------------------------------------------------------------------------------

QUOTE_MARK = "-----Original Message-----"
SIGNATURE_MARK = "-- "
_BLOCK_TAGS = {"p", "div", "br", "tr", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "blockquote", "ul", "ol"}


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.href: list[str] = []
        self.quoted = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.quoted:
            return
        a = {k: v or "" for k, v in attrs}
        if tag in ("style", "script", "head", "title"):
            self.skip += 1
            return
        marks = f"{a.get('class', '')} {a.get('id', '')}"
        if tag == "blockquote" or re.search(r"gmail_quote|divRplyFwdMsg|appendonsend|yahoo_quoted|moz-cite-prefix|OutlookMessageHeader", marks):
            self.out.append(f"\n{QUOTE_MARK}\n")
            self.quoted = True                  # everything after the reply's own text is the quoted chain
            return
        if "gmail_signature" in marks:
            self.out.append(f"\n{SIGNATURE_MARK}\n")
        if tag in _BLOCK_TAGS:
            self.out.append("\n")
        if tag == "a":
            self.href.append(a.get("href", ""))
        if tag == "img" and a.get("alt"):
            self.out.append(f" {a['alt']} ")

    def handle_endtag(self, tag: str) -> None:
        if self.quoted:
            return
        if tag in ("style", "script", "head", "title"):
            self.skip = max(0, self.skip - 1)
            return
        if tag == "a" and self.href:
            href = self.href.pop()
            if href.startswith(("http://", "https://", "tel:")):
                self.out.append(f" <{href}> ")
        if tag in _BLOCK_TAGS:
            self.out.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip and not self.quoted:
            self.out.append(data)


def html_to_text(markup: str) -> str:
    """Visible text of an HTML body, a line per block; links keep their target; the quoted chain is cut at its mark."""
    parser = _Text()
    parser.feed(markup or "")
    parser.close()
    text = _html.unescape("".join(parser.out))
    text = re.sub(r"[ \t ]+", " ", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", "\n".join(line.strip() for line in text.split("\n"))).strip()


def _looks_html(text: str) -> bool:
    return bool(re.search(r"(?i)<(?:html|body|div|p|br|table|span)\b[^>]*>", text or ""))


# --- split --------------------------------------------------------------------------------------------------------

_QUOTE = (
    re.compile(r"(?m)^[ \t]*On\b[^\n]{0,250}(?:\n[^\n]{0,250}){0,2}?\bwrote:[ \t]*$"),
    re.compile(r"(?mi)^[ \t]*-{2,}\s*Original Message\s*-{2,}"),
    re.compile(r"(?mi)^[ \t]*-{2,}\s*Forwarded message\s*-{2,}"),
    re.compile(r"(?mi)^[ \t]*Begin forwarded message:"),
    re.compile(r"(?mi)^[ \t]*\*?From:\*?[ \t].+\n(?:.*\n){0,3}?[ \t]*\*?(?:Sent|Date):\*?[ \t]"),
    re.compile(r"(?m)^[ \t]*_{10,}[ \t]*$"),
    re.compile(r"(?m)^[ \t]*>"),
)
# Footers a mailing list or a shared inbox appends after the writer's own text.
_FOOTER = (
    re.compile(r"(?mi)^[ \t]*Received via \S+ shared inbox"),
    re.compile(r"(?mi)^[ \t]*You received this message because you are subscribed to the Google Groups?"),
    re.compile(r"(?mi)^[ \t]*To unsubscribe from this group"),
)
_SIGNOFF = re.compile(
    r"(?i)^(?:best(?: regards| wishes)?|kind(?:est)? regards|warm(?:est)? regards|regards|respectfully(?: yours| submitted)?|"
    r"sincerely(?: yours)?|yours (?:truly|sincerely)|thanks?(?: you)?(?: so much| again| very much| in advance)?|many thanks|"
    r"thx|cheers|cordially|take care|all the best|with (?:appreciation|gratitude)|warmly|v/r|have a (?:great|good|nice) (?:day|weekend)|"
    r"let me know|talk soon|speak soon|looking forward(?: to [a-z ]{0,30})?|much appreciated|appreciate it|stay safe)"
    r"[\W_]*$")
_MOBILE = re.compile(
    r"(?i)^(?:sent from my (?:iphone|ipad|android|samsung|galaxy|mobile|pixel|phone|smartphone|verizon)|"
    r"sent from (?:yahoo mail|mail|outlook|gmail) for \w+|get outlook for (?:ios|android)|sent via the samsung|sent from mail for windows)")
DISCLAIMER = re.compile(
    r"(?i)confidentiality notice|privileged (?:and|&) confidential|"
    r"this (?:e-?mail(?: message)?|message|communication|transmission)(?: and any (?:files|attachments?)[^.]{0,40})?,? "
    r"(?:is|are|may contain|contains)\b[^.]{0,80}(?:confidential|privileged)|may contain (?:confidential|privileged|legally privileged)|"
    r"intended (?:only|solely) for the (?:use of the )?(?:individual|person|addressee|recipient|entity)|"
    r"if you (?:are not|have received this)[^.]{0,30}(?:intended recipient|in error)|wire fraud|"
    r"(?:never|do not) (?:wire|send) (?:funds|money)|attorney[- ]client|coverage (?:cannot|can ?not|may not|will not) be (?:bound|altered)")
_DELIM = re.compile(r"^(?:--|-- |—|__)\s*$")
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)


def _normalize(text: str) -> str:
    """Line ends, spaces, and Outlook's plain-text link targets: "www.example.com<https://...>" keeps the host only,
    and a "<mailto:...>" after the address it repeats is dropped."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ").translate(_INVISIBLE)
    text = re.sub(r"<mailto:[^>\s]*>", "", text)
    return re.sub(r"<https?://([^/>\s]+)[^>\s]*>", r" <\1>", text)


def _cut_quote(text: str) -> str:
    cut = min((m.start() for rx in _QUOTE + _FOOTER for m in [rx.search(text)] if m), default=len(text))
    return re.sub(r"(?:\n[ \t]*-{2,3}[ \t]*)+\s*$", "", text[:cut])


def _contact_cue(line: str) -> bool:
    return bool(_PHONE.search(line) or _URL.search(line) or re.search(r"@[\w-]+\.\w", line) or any(rx.search(line) for _, rx, _ in _LICENSES))


def _name_line(line: str) -> bool:
    return bool(re.fullmatch(r"[-~ ]*[A-Z][A-Za-z'’.-]*(?: [A-Z][A-Za-z'’.-]*){0,3}[ ,]*", line)) and len(line) <= 40


def _prose(line: str) -> bool:
    """A line of the message, not of a signature: long, or a sentence."""
    return len(line) > 80 or (len(line) > 40 and bool(re.search(r"[.?!:]$", line)))


def split_signature(text: str) -> tuple[str, str]:
    """(body, signature block) of the newest message in an email; HTML is turned into text first.

    The quoted chain and a mailing list's footer are dropped. The block starts after the last sign-off or at a ``--``
    line, whichever is first; else at "Sent from my iPhone" (with the name line above it); else it is the run of short
    lines around the last contact cue (a phone, a website, an address, a license) before any disclaimer, or the
    disclaimer itself. A message with none of these has no block ("").
    """
    if _looks_html(text):
        text = html_to_text(text)
    top = _cut_quote(_normalize(text)).rstrip()
    lines = top.split("\n")
    stripped = [line.strip() for line in lines]
    nonblank = [i for i, s in enumerate(stripped) if s]
    if not nonblank:
        return "", ""
    disclaimer = next((i for i in nonblank if i > nonblank[0] and DISCLAIMER.search(stripped[i])), None)
    tail_end = disclaimer if disclaimer is not None else len(lines)
    starts: list[tuple[int, int]] = []      # (block start, body end)
    dash = next((i for i in nonblank if _DELIM.match(stripped[i]) and i > nonblank[0]), None)
    if dash is not None:
        starts.append((dash + 1, dash))
    # The last sign-off, when what follows it is a short run of mostly short lines (a "Thanks!" that opens a message
    # is not one).
    signoff = next((i for i in reversed(nonblank) if nonblank[0] < i < tail_end and _SIGNOFF.match(stripped[i])
                    and sum(1 for j in nonblank if i < j < tail_end) <= 15
                    and sum(1 for j in nonblank if i < j < tail_end and len(stripped[j]) > 100) <= 2), None)
    if signoff is not None:
        starts.append((signoff + 1, signoff + 1))
    if not starts:
        mobile = next((i for i in nonblank if _MOBILE.match(stripped[i])), None)
        if mobile is not None:
            above = [i for i in nonblank if i < mobile]
            begin = above[-1] if above and _name_line(stripped[above[-1]]) and len(above) > 1 else mobile
            starts.append((begin, begin))
        else:
            # The last contact cue among the last 25 lines before any disclaimer, and the short lines above it.
            tail = [i for i in nonblank if i < tail_end][-25:]
            cue = next((i for i in reversed(tail) if i > nonblank[0] and len(stripped[i]) <= 120 and _contact_cue(stripped[i])), None)
            if cue is not None:
                begin, taken = cue, 1
                for i in reversed(range(nonblank[0] + 1, cue)):
                    if not stripped[i]:
                        continue
                    if _prose(stripped[i]) or taken >= 12:
                        break
                    begin, taken = i, taken + 1
                starts.append((begin, begin))
            elif disclaimer is not None:
                starts.append((disclaimer, disclaimer))
    if not starts:
        return top.strip(), ""
    begin, body_end = min(starts)
    block = "\n".join(line for line in lines[begin:] if not _DELIM.match(line.strip() or "x")).strip()
    return "\n".join(lines[:body_end]).strip(), block


# --- parse --------------------------------------------------------------------------------------------------------

_PHONE = re.compile(r"(?<![\d#])(?:\+?1[\s.-]?)?\(?([2-9]\d{2})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})(?:\s*(?:x|ext\.?)\s*\d{1,5})?(?!\d)")
_BUSINESS_LINE = re.compile(r"(?i)\b(office|main|tel|telephone|phone|direct|work|desk|fax|toll[- ]free|o|t|p|d|f|ph|w)\b\.?\s*[:.|-]?\s*$")
_MOBILE_LINE = re.compile(r"(?i)\b(cell|mobile|mob|m|c|text)\b\.?\s*[:.|-]?\s*$")
_TOLL_FREE = {"800", "833", "844", "855", "866", "877", "888"}
_URL = re.compile(r"(?i)\b(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+(?:com|net|org|us|biz|co|law|legal|realty|realtor|"
                  r"properties|homes|io|info|gov|edu|pro|agency|insurance|title|me|ly))\b(?:/[^\s<>)\]]*)?")
# Link-protection services rewrite every link in a message; their host is not the sender's website.
_WRAPPER = re.compile(r"(?i)emailprotection\.link|safelinks\.protection\.outlook\.com|urldefense|mimecast|linkprotect|"
                      r"cudasvc|clicktime|proofpoint|sendgrid\.net|list-manage\.com|mailchimp|hubspotlinks|ct\.sendgrid|"
                      r"awstrack\.me|eocampaign|constantcontact|rs6\.net|mandrillapp|mailgun|kiteworks")
_LINK_KINDS = (("linkedin", "linkedin.com"), ("facebook", "facebook.com"), ("instagram", "instagram.com"),
               ("twitter", "twitter.com"), ("x", "x.com"), ("youtube", "youtube.com"), ("tiktok", "tiktok.com"),
               ("calendly", "calendly.com"), ("zillow", "zillow.com"), ("yelp", "yelp.com"), ("nextdoor", "nextdoor.com"),
               ("google-business", "g.page"), ("bit.ly", "bit.ly"), ("hubspot-meetings", "meetings.hubspot.com"),
               ("realtor.com", "realtor.com"), ("redfin", "redfin.com"))
_ADDRESS = re.compile(
    r"(?i)\b\d{2,6}\s+(?:[NSEW]\.?\s+)?[A-Z0-9][\w.'-]*(?:\s+[A-Z0-9][\w.'-]*){0,4}\s+"
    r"(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place|Pkwy|Parkway|Cir|Circle|Walk|"
    r"Hwy|Highway|Sq|Square|Ter|Terrace|Trl|Trail|Loop|Plaza|Mall|Center)\b\.?|\bP\.?\s?O\.?\s+Box\s+\d+|\b(?:Suite|Ste\.?)\s*#?\s*\w+|"
    r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)*,?\s+(?:CA|California|NV|OR|AZ|TX|WA)\.?\s+\d{5}(?:-\d{4})?\b")
# (kind, pattern, role and weight): a license number is the strongest cue there is.
_LICENSES: tuple[tuple[LicenseKind, re.Pattern, tuple[tuple[SignatureRole, float], ...]], ...] = (
    (LicenseKind.CALBRE, re.compile(r"(?i)\bCal\s?BRE\b\s*(?:Lic(?:ense)?\.?\s*)?(?:#|No\.?|Number)?\s*:?\s*#?\s*(0?\d{7,8})\b"),
     ((R.REALTOR, 2.0), (R.PROPERTY_MANAGER, 0.8))),
    (LicenseKind.DRE, re.compile(r"(?i)\b(?:CA\s*|Cal\s?)?(?:DRE|BRE)\b\s*(?:Lic(?:ense)?\.?\s*)?(?:#|No\.?|Number)?\s*:?\s*#?\s*(0?\d{7,8})\b"),
     ((R.REALTOR, 2.0), (R.PROPERTY_MANAGER, 0.8))),
    (LicenseKind.NMLS, re.compile(r"(?i)\bNMLS\b\s*(?:ID|#|No\.?)?\s*:?\s*#?\s*(\d{3,10})\b"), ((R.LENDER, 3.0),)),
    (LicenseKind.BAR, re.compile(r"(?i)\b(?:(?:State\s+)?Bar\s*(?:No\.?|Number|#)|SBN)\s*:?\s*#?\s*(\d{4,7})\b"), ((R.ATTORNEY, 3.0),)),
    (LicenseKind.CSLB, re.compile(r"(?i)\b(?:CSLB|C\.S\.L\.B\.?|Contractor'?s?\s+Lic(?:ense)?\.?)\s*(?:Lic(?:ense)?\.?)?\s*(?:#|No\.?|Number)?"
                                  r"\s*:?\s*#?\s*(\d{5,7})\b"), ((R.VENDOR, 3.0),)),
    (LicenseKind.INSURANCE, re.compile(r"(?i)\b(?:(?:CA\s*)?(?:Ins(?:urance)?\.?\s*)?(?:Agency\s*)?Lic(?:ense)?\.?|DOI)\s*(?:#|No\.?|Number)?"
                                       r"\s*:?\s*(?:CA|California)?\s*#?\s*(\d[A-Z]\d{5})\b"), ((R.INSURER, 3.0),)),
    (LicenseKind.ESCROW, re.compile(r"(?i)\b(?:DFPI|DBO|Escrow)\s*(?:License|Lic\.?)\s*(?:#|No\.?)?\s*:?\s*#?\s*(\d[\d-]{4,11})\b"), ((R.TITLE_ESCROW, 3.0),)),
    # A bare "Lic. #123456" with no board named is most often a California contractor's number.
    (LicenseKind.CSLB, re.compile(r"(?i)\bLic(?:ense)?\.?\s*(?:#|No\.?|Number)\s*:?\s*#?\s*(\d{6,7})\b"), ((R.VENDOR, 1.5),)),
)
# Titles, in order; a more specific title first ("Resident Manager" before "Resident").
_TITLES: tuple[tuple[SignatureRole, float, re.Pattern], ...] = tuple((role, w, re.compile(p, re.I)) for role, w, p in (
    (R.ASSOCIATION_MANAGER, 2.5, r"\b(?:community (?:association )?manager|association manager|hoa manager|"
                                 r"CMCA|AMS|PCAM|CCAM|community management)\b"),
    (R.PROPERTY_MANAGER, 2.5, r"\b(?:(?:assistant |senior )?property manager|leasing (?:agent|manager|consultant|specialist|director)|"
                              r"rental (?:manager|specialist|coordinator)|resident manager|portfolio manager|tenant relations|"
                              r"maintenance coordinator)\b"),
    (R.TITLE_ESCROW, 2.5, r"\b(?:escrow (?:officer|assistant|manager|coordinator|secretary|processor)|title (?:officer|rep(?:resentative)?|"
                          r"examiner|assistant)|closing (?:officer|coordinator)|payoff (?:specialist|department))\b"),
    (R.REALTOR, 2.5, r"\b(?:realtor|real estate (?:agent|broker|salesperson|professional|advisor)|broker[- ]associate|"
                     r"sales associate|listing (?:agent|coordinator)|buyer'?s agent|transaction coordinator|managing broker|"
                     r"designated broker|broker of record)\b"),
    (R.ATTORNEY, 2.5, r"\b(?:attorney(?: at law)?|esq\.?|of counsel|counsel|paralegal|legal assistant|law clerk)\b"),
    (R.LENDER, 2.5, r"\b(?:loan officer|mortgage (?:loan )?(?:originator|advisor|consultant|banker|broker)|loan (?:originator|processor))\b"),
    (R.INSURER, 2.5, r"\b(?:insurance (?:agent|broker|advisor|specialist)|claims? (?:adjuster|examiner|representative|specialist)|"
                     r"adjuster|underwriter|CISR|CIC|CPCU|CRIS|personal lines|commercial lines)\b"),
    (R.GOVERNMENT, 2.5, r"\b(?:code enforcement|building inspector|city (?:clerk|manager|planner)|council ?member|planner|"
                        r"public works|deputy (?:clerk|assessor|tax collector))\b"),
    (R.VENDOR, 2.0, r"\b(?:estimator|project manager|superintendent|foreman|technician|service (?:manager|coordinator|advisor)|"
                    r"owner/operator|contractor|arborist|plumber|electrician|installer|field (?:manager|supervisor)|"
                    r"sales (?:rep(?:resentative)?|manager|consultant))\b"),
    (R.INDIVIDUAL, 2.0, r"\b(?:home ?owner|unit owner|owner of (?:unit|\d)|resident(?! manager)|tenant(?! relations))\b"),
    (R.BUSINESS, 1.0, r"\b(?:president|vice president|ceo|cfo|coo|founder|co-founder|principal|office manager|operations manager|"
                      r"general manager|director|account (?:manager|executive)|customer service|owner|manager|partner|"
                      r"administrator|coordinator|specialist|assistant)\b"),
))
# Company words, in order; a company line is one that names a firm.
_COMPANIES: tuple[tuple[SignatureRole, float, re.Pattern], ...] = tuple((role, w, re.compile(p, re.I)) for role, w, p in (
    (R.ASSOCIATION_MANAGER, 2.0, r"\b(?:association management|community management|hoa management|community association management)\b"),
    (R.PROPERTY_MANAGER, 2.0, r"\b(?:property management|property services|property mgmt|rentals?|leasing|residential management)\b"),
    (R.REALTOR, 2.0, r"\b(?:realty|real estate|realtors?|brokerage|keller williams|coldwell banker|re/?max|century 21|compass|"
                     r"exp realty|berkshire hathaway|sotheby'?s|redfin|lyon real estate|better homes and gardens|intero|corcoran|"
                     r"homesmart|real broker)\b"),
    (R.TITLE_ESCROW, 2.0, r"\b(?:escrow|title (?:company|insurance|co\.?|group)|title)\b"),
    (R.ATTORNEY, 2.0, r"\b(?:law (?:group|office|offices|firm|corporation)|attorneys?|LLP|A\.?P\.?L?\.?C\.?)\b|\blaw\b"),
    (R.INSURER, 2.0, r"\b(?:insurance|assurance|indemnity|underwriters|insurance services|insurance agency)\b"),
    (R.LENDER, 2.0, r"\b(?:mortgage|lending|home loans|bank|credit union|savings and loan)\b"),
    (R.GOVERNMENT, 2.0, r"\b(?:city of|county of|state of|department of|utility district|sanitation district|fire department)\b"),
    (R.PROPERTY_MANAGER, 1.0, r"\b(?:properties|property)\b"),
    (R.VENDOR, 1.5, r"\b(?:construction|contracting|contractors?|plumbing|roofing|electric(?:al)?|painting|landscap\w*|pest|hvac|"
                    r"heating|air conditioning|pool|tree|arbor\w*|gutters?|paving|asphalt|concrete|restoration|cleaning|janitorial|"
                    r"security|locksmith|doors?|windows?|fencing|builders?|inspections?|sprinklers?|fire protection|elevator|"
                    r"towing|waste|disposal|signs?|maintenance|handyman|flooring|masonry|solar)\b"),
    (R.BUSINESS, 1.0, r"\b(?:LLC|L\.L\.C\.|Inc\.?|Incorporated|Corp\.?|Corporation|Co\.|Company|Ltd\.?|LP|PC|Group|Associates|"
                      r"Partners|Enterprises|Services|Solutions|Agency)(?=\W|$)"),
))
# Words in the sender's domain (its first label).
_DOMAIN_WORDS: tuple[tuple[SignatureRole, re.Pattern], ...] = tuple((role, re.compile(p, re.I)) for role, p in (
    (R.ASSOCIATION_MANAGER, r"hoa(?:management|mgmt)|communitymanagement|associationmanagement"),
    (R.PROPERTY_MANAGER, r"propertymanagement|propertymgmt|pm$|rentals?|leasing|properties|property"),
    (R.REALTOR, r"realty|realestate|realtor|homes$|kw$|compass|remax|cbnorcal|coldwellbanker|exprealty|kwrealty"),
    (R.TITLE_ESCROW, r"escrow|title"),
    (R.ATTORNEY, r"law|legal|attorneys?|llp"),
    (R.INSURER, r"insurance|ins$|assurance|indemnity|insure"),
    (R.LENDER, r"mortgage|lending|loans?|bank|creditunion|cu$|fcu$"),
    (R.VENDOR, r"construction|plumbing|roofing|electric|painting|landscap|pest|hvac|builders?|contracting|gutter|paving|"
               r"clean|security|door|tree|sprinkler|janitorial|restoration|handyman"),
))
_DISCLAIMER_WORDS: tuple[tuple[SignatureRole, float, re.Pattern], ...] = tuple((role, w, re.compile(p, re.I)) for role, w, p in (
    (R.ATTORNEY, 1.5, r"attorney[- ]client|attorney work product"),
    (R.ATTORNEY, 0.3, r"privileged"),             # most corporate disclaimers say "confidential or privileged"
    (R.TITLE_ESCROW, 1.5, r"wire fraud|wiring instructions|(?:never|do not) (?:wire|send) (?:funds|money)|escrow"),
    (R.INSURER, 1.5, r"coverage (?:cannot|can ?not|may not|will not) be (?:bound|altered)|bind(?:ing)? coverage"),
    (R.LENDER, 1.0, r"equal housing lender|NMLS"),
    (R.REALTOR, 0.5, r"equal housing opportunity"),
))


def _phones(lines: list[str]) -> tuple[bool, list[Phone]]:
    found = False
    kept: list[Phone] = []
    for line in lines:
        for m in _PHONE.finditer(line):
            found = True
            before = line[:m.start()]
            area = m.group(1)
            number = f"({area}) {m.group(2)}-{m.group(3)}"
            if _MOBILE_LINE.search(before):
                continue
            label = _BUSINESS_LINE.search(before)
            if area in _TOLL_FREE:
                kept.append(Phone("toll-free", number))
            elif label:
                word = label.group(1).lower()
                word = {"o": "office", "t": "tel", "p": "phone", "d": "direct", "f": "fax", "ph": "phone", "w": "work",
                        "telephone": "tel"}.get(word, word)
                kept.append(Phone(word.replace(" ", "-"), number))
    return found, list(dict.fromkeys(kept))


def _host(value: str) -> str:
    host = re.sub(r"^[a-z]+://", "", value.lower()).split("/")[0]
    return host[4:] if host.startswith("www.") else host


def _fields(lines: list[str]) -> list[str]:
    """Each line split at its separators ("Jane Doe | Escrow Officer | Example Title")."""
    out: list[str] = []
    for line in lines:
        parts = re.split(r"\s+[|•·/]\s+|\s+[|•·]|[|•·]\s+|\s{3,}", re.sub(r"\s*<[^<>]*>", " ", line).strip())
        out += [f.strip(" ,;|/•·-[]") for f in parts if f.strip(" ,;|/•·-[]")]
    return out


def _fieldish(text: str) -> bool:
    """A signature field, not a sentence: short, capitalized, and not ending like prose."""
    t = text.strip()
    if not t or len(t) > 70 or len(t.split()) > 8 or not (t[0].isupper() or t[0].isdigit()) or re.search(r"[?!:]$", t):
        return False
    if t.endswith(".") and t.split()[-1].rstrip(".").lower() not in {"inc", "esq", "co", "corp", "ltd", "jr", "sr", "l.l.c", "p.c", "a.p.c"}:
        return False
    return not re.match(r"(?i)(?:please|i|we|you|it|this|that|if|thank|let|can|could|would|will)\b", t)


def _credentials_split(fieldtext: str) -> tuple[str, str]:
    """("Jane Doe", "Esq.") from "Jane Doe, Esq."."""
    head, _, tail = fieldtext.partition(",")
    return head.strip(), tail.strip()


def parse_signature(block: str, *, address: str = "", display_name: str = "") -> Signature:
    """The structured fields of a signature block, and the role they point to (see the module notes).

    ``address`` is the sender's email address (its domain is a cue: a consumer provider leans individual, a branded
    domain business); ``display_name`` stands in for the name when the block has none.
    """
    raw = [line.strip() for line in (block or "").split("\n")]
    mobile = any(_MOBILE.match(line) for line in raw if line)
    lines = [line for line in raw if line and not _MOBILE.match(line) and not _SIGNOFF.match(line)]
    disclaimer_at = next((i for i, line in enumerate(lines) if DISCLAIMER.search(line)), None)
    contact = lines if disclaimer_at is None else lines[:disclaimer_at]
    legal = " ".join(lines[disclaimer_at:]) if disclaimer_at is not None else ""
    # Long prose lines are not signature fields (a sentence left above the block).
    contact = [line for line in contact if len(line) <= 120]
    scores: dict[SignatureRole, float] = {}
    reasons: list[str] = []

    def cue(role: SignatureRole, weight: float, why: str) -> None:
        scores[role] = scores.get(role, 0.0) + weight
        if why not in reasons:
            reasons.append(why)

    text = "\n".join(contact)
    no_mail = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", " ", text)
    # Licenses.
    licenses: list[License] = []
    for kind, rx, roles in _LICENSES:
        for m in rx.finditer(no_mail):
            if any(lic.number == m.group(1) for lic in licenses):
                continue
            licenses.append(License(kind, m.group(1)))
            for role, w in roles:
                cue(role, w, f"license:{kind.value} {m.group(1)}")
    # Phones, address, links, website.
    has_phone, phones = _phones(contact)
    if any(line.lower().startswith("tel:") for line in contact) or "<tel:" in text:
        has_phone = True
    has_address = any(_ADDRESS.search(_PHONE.sub(" ", line)) for line in contact)
    links: list[str] = []
    sites: list[str] = []
    for m in _URL.finditer(no_mail):
        host = _host(m.group(0))
        kind = next((k for k, d in _LINK_KINDS if host == d or host.endswith("." + d)), None)
        if kind:
            if kind not in links:
                links.append(kind)
        elif host not in CONSUMER_DOMAINS and not re.fullmatch(r"[\d.]+", host) and not _WRAPPER.search(host):
            sites.append(host)
    # The sender's own site first ("www.example.com" for jordan@example.com), else the first one named.
    root = ".".join(address.rsplit("@", 1)[-1].lower().split(".")[-2:]) if "@" in address else ""
    website = next((h for h in sites if root and (h == root or h.endswith("." + root))), sites[0] if sites else "")
    # Fields: name, title, company.
    fields = _fields(contact)
    name = title = company = credentials = ""
    for f in fields:
        if (_PHONE.search(f) or "@" in f or _URL.search(f) or any(rx.search(f) for _, rx, _ in _LICENSES) or _ADDRESS.search(f)
                or not _fieldish(f)):
            continue
        head, creds = _credentials_split(f)
        is_title = next(((role, w, rx) for role, w, rx in _TITLES if rx.search(f)), None)
        is_company = next(((role, w, rx) for role, w, rx in _COMPANIES if rx.search(f)), None)
        # "Example Adjusting, LLC" is a company even when the words before the suffix are not a company word.
        head_named = any(rx.search(head) for _, _, rx in _TITLES + _COMPANIES) or (
            bool(creds) and any(rx.search(creds) for role, _, rx in _COMPANIES if role is R.BUSINESS))
        if head_named and not is_company and creds and not is_title:
            is_company = (R.BUSINESS, 1.0, None)
        # "Kal" above "Kal Example": the fuller name wins.
        if name and " " not in name and not head_named and _name_line(head) and head.split()[0] == name and not creds:
            name = head
            continue
        if not name and _name_line(head) and not head_named:
            if not re.search(r"(?i)\b(?:" + "|".join(["the", "and", "of", "unit", "suite", "office"]) + r")\b", head):
                name = head
                if creds:
                    for role, w, rx in _TITLES:
                        if rx.search(creds):
                            credentials = creds        # the title only when no line names one
                            cue(role, w, f"title:{creds}")
                            break
                continue
        if is_title and not title and (not is_company or is_title[1] >= 2.0) and len(f) <= 60:
            title = f
            cue(is_title[0], is_title[1], f"title:{f}")
            # "Escrow Officer, Example Title Company" and "Owner, Example Cleaning" name both.
            tail = f.split(",", 1)[1].strip() if "," in f else ""
            if tail and not company and (is_company or not any(rx.search(tail) for _, _, rx in _TITLES)):
                title, company = f.split(",", 1)[0].strip(), tail
            continue
        if is_company and not company and len(f) <= 70:
            company = f
    title = title or credentials
    for role, w, rx in _COMPANIES:
        if company and rx.search(company):
            cue(role, w, f"company:{company}")
            break
    if company and not scores.get(R.BUSINESS) and any(rx.search(company) for role, _, rx in _COMPANIES if role is R.BUSINESS):
        cue(R.BUSINESS, 1.0, "company suffix")
    if not name and display_name and _name_line(display_name.strip().strip('"')):
        name = display_name.strip().strip('"')
    # Title words outside the field that named it (a credential after a name, "Realtor®" on its own line).
    for f in fields:
        if not _fieldish(f) and not re.search(r"®", f):
            continue
        for role, w, rx in _TITLES:
            if role is not R.BUSINESS and rx.search(f) and not any(r.startswith("title:") and rx.search(r) for r in reasons):
                cue(role, w / 2, f"title word:{rx.search(f).group(0)}")
                break
    # The disclaimer.
    if legal:
        cue(R.BUSINESS, 1.0, "disclaimer")
        for role, w, rx in _DISCLAIMER_WORDS:
            if rx.search(legal):
                cue(role, w, f"disclaimer:{rx.search(legal).group(0).lower()}")
    # The sender's domain.
    domain = address.rsplit("@", 1)[-1].lower().strip(" >") if "@" in address else ""
    personal_domain = not domain or domain in CONSUMER_DOMAINS
    if domain in CONSUMER_DOMAINS:
        cue(R.INDIVIDUAL, 1.0, f"consumer domain:{domain}")
    elif domain:
        if domain.endswith(".gov") or ".ca.gov" in domain or domain.endswith(".ca.us"):
            cue(R.GOVERNMENT, 2.5, f"government domain:{domain}")
        else:
            cue(R.BUSINESS, 0.8, f"branded domain:{domain}")
            label = domain.split(".")[-2] if domain.count(".") >= 1 else domain
            for role, rx in _DOMAIN_WORDS:
                if rx.search(label):
                    cue(role, 1.0, f"domain word:{label}")
                    break
    if website and not domain.endswith(website) and website.endswith(".gov"):
        cue(R.GOVERNMENT, 1.0, f"government website:{website}")
    elif website:
        cue(R.BUSINESS, 0.5, f"website:{website}")
        label = website.split(".")[-2] if "." in website else website
        for role, rx in _DOMAIN_WORDS:
            if rx.search(label):
                cue(role, 0.8, f"website word:{label}")
                break
    if mobile:
        cue(R.INDIVIDUAL, 0.3, "sent from a phone")
    # A bare name reads as a person only from a personal mailbox: at a company's domain it says nothing.
    if personal_domain and (name or display_name) and not (title or company or licenses or website or legal or phones):
        cue(R.INDIVIDUAL, 1.0, "a name and nothing else")
        if name and " " not in name.strip():
            cue(R.INDIVIDUAL, 0.5, "first name only")
    role, confidence = _decide(scores)
    if not role.professional:
        phones = []
    return Signature(name=name, title=title, company=company, has_phone=has_phone, business_phones=tuple(phones),
                     website=website, licenses=tuple(licenses), has_address=has_address, links=tuple(links),
                     disclaimer=bool(legal), mobile=mobile, role=role, confidence=confidence, reasons=tuple(reasons))


def _decide(scores: dict[SignatureRole, float]) -> tuple[SignatureRole, float]:
    """The role with the most weight among the specific ones (ties go to the earlier role); else an unclear business,
    else an individual, else unknown. The confidence is that role's share of all the weight."""
    if not scores:
        return R.UNKNOWN, 0.0
    total = sum(scores.values())
    specific = [(scores[r], -i, r) for i, r in enumerate(SignatureRole) if r.professional and r is not R.BUSINESS and r in scores]
    business = scores.get(R.BUSINESS, 0.0)
    individual = scores.get(R.INDIVIDUAL, 0.0)
    best = max(specific, default=None)
    if best and best[0] >= 1.0 and best[0] + business >= individual:
        role, weight = best[2], best[0] + business * 0.5
    elif business + (best[0] if best else 0.0) >= 1.0 and business + (best[0] if best else 0.0) > individual:
        role, weight = R.BUSINESS, business
    elif individual > 0:
        role, weight = R.INDIVIDUAL, individual
    else:
        return R.UNKNOWN, 0.0
    return role, round(min(0.95, weight / (total + 0.5)), 2)


def read_signature(text: str, *, address: str = "", display_name: str = "") -> Signature:
    """Split and parse in one step. The body is dropped here: only the signature's fields leave this function."""
    _body, block = split_signature(text)
    return parse_signature(block, address=address, display_name=display_name)


__all__ = ["SignatureRole", "LicenseKind", "License", "Phone", "Signature", "CONSUMER_DOMAINS", "DISCLAIMER",
           "html_to_text", "split_signature", "parse_signature", "read_signature"]
