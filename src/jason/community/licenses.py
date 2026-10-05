"""License numbers a document prints, and whose they are.

A licensed vendor prints its number where the law asks (a contractor on every bid, contract, and invoice, BPC 7030.5;
an alarm company, a pest control company, a real estate broker on theirs), so the number is a party's identity a name
cannot give: two firms can share a name, never a license. It is also the key to the licensing board's public record:
whether the license is current, its classifications, its bond, and its discipline.

``find_licenses(text)`` reads every mention with the ``KINDS`` rows, in order; the first row that claims a span wins.
Each row names the board, how its numbers look, and where a person checks one. The holder is the business name the
mention sits beside (a letterhead, an invoice's header, a signature block). A number with no board named ("License
#123456") is kept as unspecified, with the board it most likely belongs to, for a person to confirm.

jason reads the number. It does not look the license up: the board's page is the authority, and a reading is a lead.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class Board(Enum):
    CSLB = "Contractors State License Board"
    DRE = "Department of Real Estate"
    BSIS = "Bureau of Security and Investigative Services"
    SPCB = "Structural Pest Control Board"
    CDI = "Department of Insurance"
    STATE_BAR = "State Bar of California"
    NMLS = "Nationwide Multistate Licensing System"
    DFPI = "Department of Financial Protection and Innovation"
    CBA = "California Board of Accountancy"
    BPELSG = "Board for Professional Engineers, Land Surveyors, and Geologists"
    CAB = "California Architects Board"
    DIR = "Department of Industrial Relations (public works contractor registration)"
    NOTARY = "a notary commission"
    LOCAL = "a city or county business license"
    OUT_OF_STATE = "another state's licensing board"
    CERTIFICATION = "a professional certification (not a license)"
    UNSPECIFIED = "no board named"


# Where a person checks a number. A board without a page that takes the number shows its search page.
VERIFY: dict[Board, str] = {
    Board.CSLB: "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/LicenseDetail.aspx?LicNum={number}",
    Board.DRE: "https://www2.dre.ca.gov/PublicASP/pplinfo.asp?License_id={number}",
    Board.STATE_BAR: "https://apps.calbar.ca.gov/attorney/Licensee/Detail/{number}",
    Board.NMLS: "https://www.nmlsconsumeraccess.org/",
    Board.BSIS: "https://search.dca.ca.gov/",
    Board.SPCB: "https://search.dca.ca.gov/",
    Board.CBA: "https://search.dca.ca.gov/",
    Board.BPELSG: "https://search.dca.ca.gov/",
    Board.CAB: "https://search.dca.ca.gov/",
    Board.CDI: "https://www.insurance.ca.gov/",
    Board.DFPI: "https://dfpi.ca.gov/",
    Board.DIR: "https://www.dir.ca.gov/public-works/contractor-registration.html",
}


@dataclass(frozen=True)
class LicenseKind:
    key: str
    label: str
    board: Board
    pattern: str                      # group "number"; optional groups "cls" (a classification) and "where" (a state)
    jurisdiction: str = "CA"
    note: str = ""


_N = r"(?:No\.?|Number|Num\.?|#)"
# The rows, in order: a more specific row before a general one (an alarm operator's "ACO" before a bare "License #").
KINDS: tuple[LicenseKind, ...] = (
    LicenseKind("out-of-state-contractor", "a contractor's license in another state", Board.OUT_OF_STATE,
                rf"\b(?P<where>AZ|NV|OR|WA|ID)\s+(?:ROC\s+)?(?:Contractor'?s?\s+)?Lic(?:ense)?\.?\s*(?P<cls>[A-Z]{{1,2}}-?\d{{1,3}})?"
                rf"\s*{_N}?\s*:?\s*(?P<number>\d{{5,7}})", jurisdiction=""),
    LicenseKind("cslb", "a California contractor's license", Board.CSLB,
                rf"(?:\b(?:CA|California)\s+(?:State\s+)?(?:Contractor'?s?\s+)?Lic(?:ense)?\.?|\bContractor[’'`]?s?\s+Lic(?:ense)?\.?|"
                rf"\bCSLB|\bC\.S\.L\.B\.?|Class\s+[AB]\s+(?:California\s+)?contractor'?s\s+license|\bContractor:)"
                rf"\s*(?P<cls>C-?\d{{1,2}}(?:/C-?\d{{1,2}})*|[AB](?=\s))?\s*{_N}?\s*:?\s*#?\s*(?P<number>0?\d{{5,7}})"
                rf"(?:-(?P<cls2>[A-Z]{{1,2}}\d{{0,2}}))?\b"),
    LicenseKind("cslb-class-first", "a California contractor's license, its classification first", Board.CSLB,
                r"(?<![\w-])(?P<cls>C-?(?:1|2|4|5|6|7|8|9|10|11|12|13|15|16|17|20|21|22|23|27|28|29|31|32|33|34|35|36|38|39|"
                r"42|43|45|46|47|49|50|51|53|54|55|57|60|61)(?:/C-?\d{1,2})*)\s+#?\s*(?P<number>\d{6,7})\b"),
    LicenseKind("alarm-operator", "an alarm company operator's license", Board.BSIS,
                rf"\bACO[\s-]*{_N}?\s*:?\s*(?P<number>\d{{3,6}})\b"),
    LicenseKind("private-patrol", "a private patrol operator's license", Board.BSIS,
                rf"\bPPO[\s-]*{_N}?\s*:?\s*(?P<number>\d{{3,6}})\b"),
    LicenseKind("pest-control", "a structural pest control company or operator license", Board.SPCB,
                rf"(?:\bLic(?:ense)?\.?|\bSPCB|\bRegistration|\bOperator)\s*{_N}?\s*:?\s*(?P<number>(?:PR|OPR|FR|RR)\s?\d{{3,6}})\b"),
    LicenseKind("real-estate", "a real estate broker's or salesperson's license", Board.DRE,
                rf"\b(?:CA\s*)?(?:DRE|Cal\s?BRE|BRE)\b\s*(?:Lic(?:ense)?\.?\s*)?{_N}?\s*:?\s*#?\s*(?P<number>0?\d{{7,8}})\b"),
    LicenseKind("mortgage", "a mortgage lender's or originator's NMLS id", Board.NMLS,
                rf"\bNMLS\b\s*(?:ID|{_N})?\s*:?\s*#?\s*(?P<number>\d{{3,10}})\b"),
    LicenseKind("attorney", "an attorney's State Bar number", Board.STATE_BAR,
                rf"\b(?:(?:State\s+)?Bar\s*{_N}|SBN)\s*:?\s*#?\s*(?P<number>\d{{4,7}})\b"),
    LicenseKind("insurance", "an insurance agent's or broker's license", Board.CDI,
                rf"(?:\bCA\s+)?(?:Insurance\s+)?(?:\bLic(?:ense)?\.?|\bCDI|\bDOI)\s*{_N}?\s*:?\s*#?\s*(?P<number>0[A-Z0-9]\d{{5}})\b"),
    LicenseKind("escrow", "an escrow agent's license", Board.DFPI,
                rf"\b(?:DFPI|DBO|Escrow)\s*(?:License|Lic\.?)\s*{_N}?\s*:?\s*#?\s*(?P<number>\d[\d-]{{4,11}})\b"),
    LicenseKind("accountant", "a CPA's or CPA firm's license", Board.CBA,
                rf"\bCPA\s+(?:Lic(?:ense)?\.?|Firm)\s*{_N}?\s*:?\s*#?\s*(?P<number>(?:COR|PAR)?\s?\d{{4,6}})\b"),
    LicenseKind("engineer", "a professional engineer's or geologist's license", Board.BPELSG,
                rf"(?:Civil|Structural|Geotechnical|Professional|Mechanical|Electrical)\s+Engineer[^\n]{{0,40}}?(?:{_N}|License)\s*:?\s*"
                rf"(?P<number>(?:C|S|GE|M|E)\s?-?\s?\d{{4,6}})\b|\b(?:RCE|R\.C\.E\.|P\.E\.)\s*{_N}?\s*:?\s*(?P<number2>\d{{4,6}})\b"),
    LicenseKind("architect", "an architect's license", Board.CAB,
                rf"Architect[^\n]{{0,40}}?(?:{_N}|License)\s*:?\s*(?P<number>C\s?-?\s?\d{{4,6}})\b"),
    LicenseKind("public-works", "a public works contractor registration", Board.DIR,
                rf"\bDIR\s*(?:Reg(?:istration)?\.?)?\s*{_N}?\s*:?\s*(?P<number>\d{{10}})\b"),
    LicenseKind("notary", "a notary public's commission", Board.NOTARY,
                rf"Notary[\s\S]{{0,240}}?(?:Commission|License)\s*{_N}\s*:?\s*#?\s*(?P<number>\d{{6,8}})\b", jurisdiction=""),
    LicenseKind("certification", "a professional certification or designation", Board.CERTIFICATION,
                r"\b(?P<cls>CCAM(?:-[A-Z]{2})?|CMCA|PCAM|AMS|RS|PRA|CPM)\b[^\n]{0,160}?Registration\s*#\s*(?P<number>\d{2,9})\b"),
    LicenseKind("business-license", "a city or county business license", Board.LOCAL,
                rf"\b(?:City|County|Business)\s+(?:Business\s+)?Lic(?:ense)?\.?\s*{_N}?\s*:?\s*#?\s*(?P<number>(?=[\w-]*\d)[A-Z0-9][\w-]{{3,15}})\b|"
                rf"\bLic\.?\s*#\s*(?P<number2>\d{{4,6}}-\d{{4,6}})\b"),
    LicenseKind("unspecified", "a license number with no board named", Board.UNSPECIFIED,
                rf"(?<![\w-])(?:Lic(?:ense)?\.?\s*{_N}\s*:?|License\s*:|License\s*#?\s*:?)\s*#?\s*(?P<number>\d{{5,7}})\b",
                note="six or seven digits are most often a California contractor's (CSLB) number; confirm on the board's page"),
)
_RX = [(k, re.compile(k.pattern, re.I)) for k in KINDS]
_STATES = {"AZ": "Arizona", "NV": "Nevada", "OR": "Oregon", "WA": "Washington", "ID": "Idaho"}
# A text this long with no page breaks is a packet read as one page (a month's report): its opening is the packager's,
# so no mention takes it as a letterhead. The longest single agreement in the library was about 96,000 characters.
UNPAGED_PACKET_CHARS = 120_000

# A business name: capitalized words ending in a company suffix ("Example Roofing Company, Inc.", "EXAMPLE ALARM, INC.").
_COMPANY = re.compile(r"((?:[A-Z][\w&.'’\-]*\s+){0,6}?[A-Z][\w&.'’\-]*,?\s+(?i:Inc|LLC|L\.L\.C|Corp|Corporation|Company|"
                      r"Co(?=[.,])|LLP|Ltd|Group|Services|Enterprises)\b\.?(?:,?\s+(?i:Inc|LLC|L\.L\.C|Corp|Ltd)\b\.?)?)")
_NOT_A_HOLDER = re.compile(r"association|\bHOA\b|homeowners|non-?profit|mutual\s+benefit|\bbank\b|insurance\s+processing|"
                           r"bond(?:ing)?\b|fidelity|surety|condominiums?\b|insurance\s+company|casualty|underwriters|"
                           r"workers\s+compensation", re.I)
_ENVELOPE_ID = re.compile(r"^[0-9A-F]{4,}(?:-[0-9A-F]{4,})+$|^\d[\d-]{5,}$", re.I)
# A name that follows one of these is the customer, the insured, or a bond's obligee, not the license's holder.
_CUSTOMER_BEFORE = re.compile(r"(?:bill(?:ed)?\s*to|sold\s*to|ship\s*to|c/o|attn\.?|customer|insured|obligee|"
                              r"certificate\s+holder|to)\s*:?\s*$", re.I)
# Form words a name can pick up from the line above it ("Initial", "President", a signature block's labels).
_LEADING_NOISE = re.compile(r"^(?:(?:Initial|Initials|President|Signature|By|Name|Title|Date|Company|Commercial|Contractor|"
                            r"Contractors|Owner|Agent|Approved|Accepted|Vendor|Licensee|Proposal|Quote|Quotation|Invoice|"
                            r"Estimate|Agreement|Contract|Bid|Page)\b[:.]?\s+)+", re.I)


@dataclass(frozen=True)
class LicenseMention:
    kind: str                         # the row's key ("cslb", "alarm-operator")
    label: str
    board: Board
    number: str
    classification: str = ""          # a CSLB class ("C-10", "B"), a certification ("CCAM")
    jurisdiction: str = "CA"
    holder: str = ""                  # the business name beside the mention, "" when none is near
    quote: str = ""
    start: int = 0
    end: int = 0
    verify: str = ""                  # where a person checks it
    note: str = ""

    @property
    def key(self) -> tuple[str, str]:
        """One license, however often it is printed: its board and its number."""
        return (self.board.name, re.sub(r"[\s-]", "", self.number).upper())

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["board"] = self.board.value
        return raw


def _clean(raw: str) -> str:
    name = " ".join(raw.split()).strip(" ,")
    # A name starts after the last full stop of the sentence it was run into ("... IS PART OF THIS CONTRACT. JB Bostick
    # Company"); a stop after an initial or an abbreviation ("T.E.S.C.", "Co.") is not a sentence's end.
    name = re.split(r"(?<=[a-z]{2}|[A-Z]{2})[.!?]\s+(?=[A-Z])", name)[-1]
    name = _LEADING_NOISE.sub("", name)
    words = [w for w in name.split() if not _ENVELOPE_ID.match(w.strip(".,"))]
    name = " ".join(words)
    # An all-caps name ("SUMMIT ROOFING COMPANY, INC.") is only its all-caps words: the words before it on the same
    # line ("... Whimsical Lane Mystique Community") are an address or the customer.
    if words and words[-1].strip(".,").isupper():
        tail = []
        for w in reversed(words):
            if not (w.strip(".,&'’-").isupper() or w in ("&",)):
                break
            tail.insert(0, w)
        name = " ".join(tail) if len(tail) >= 2 else name
    return name


# "Services", "Group", and "Enterprises" also end ordinary phrases ("Recurring Services", "We Do Offer Services"): a name
# with one of them needs no function word or common adjective among its words.
_WEAK_SUFFIX = re.compile(r"\b(?:Services|Group|Enterprises)\.?$", re.I)
_PHRASE_WORDS = {"we", "do", "our", "your", "offer", "offers", "recurring", "additional", "other", "total", "monthly",
                 "annual", "general", "all", "any", "these", "those", "the following", "and", "for", "of", "provide",
                 "providing", "statements", "reconciliation", "management", "financial", "accounting"}


_CUSTOMERS: dict[int, frozenset[str]] = {}


def _after_care_of(text: str, m: re.Match[str]) -> bool:
    """A name the match starts at the "O" of "C/O" ("C/O The Example Group" read as "O The Example Group")."""
    return m.group(1).startswith(("O ", "o ")) and text[max(0, m.start() - 2):m.start()].lower().endswith("c/")


def customers(text: str) -> frozenset[str]:
    """The names a text gives as the customer anywhere ("Bill To: Example Management, Inc.", "Association c/o Example
    Group"): such a name is the customer wherever else it appears in the same text, not a license's holder."""
    key = hash(text)
    if key not in _CUSTOMERS:
        found = set()
        for m in _COMPANY.finditer(text):
            if _CUSTOMER_BEFORE.search(text[max(0, m.start() - 40):m.start()]) or _after_care_of(text, m):
                found.add(re.sub(r"^[Oo]\s+", "", _clean(m.group(1))).lower())
        if len(_CUSTOMERS) > 64:
            _CUSTOMERS.clear()
        _CUSTOMERS[key] = frozenset(n for n in found if n)
    return _CUSTOMERS[key]


def _names(text: str, lo: int, hi: int):
    """The business names in ``text[lo:hi]`` that could hold a license: not the association, a bank, or a bond's obligee,
    and not a customer named after "Bill To" or "c/o" here or anywhere in the text."""
    known_customers = customers(text)
    for m in _COMPANY.finditer(text, lo, hi):
        name = _clean(m.group(1))
        if _NOT_A_HOLDER.search(name) or len(name) < 5 or name.count(" ") == 0:
            continue
        if _WEAK_SUFFIX.search(name):
            before = name.split()[:-1]
            corporate = re.match(r",?\s+(?:Inc|LLC|L\.L\.C|Corp|Ltd)\b", text[m.end():m.end() + 8])
            if any(w.lower().strip(",.") in _PHRASE_WORDS for w in before) or (len(before) < 2 and not corporate):
                continue
        if (_CUSTOMER_BEFORE.search(text[max(0, m.start() - 40):m.start()]) or _after_care_of(text, m)
                or name.lower() in known_customers or re.sub(r"^[Oo]\s+", "", name).lower() in known_customers):
            continue
        yield m, name


_ADDRESS_LINE = re.compile(r"^\s*(?:\d{2,6}\s+[A-Z0-9][\w.]*(?:\s+[\w.#]+){0,6}|P\.?\s?O\.?\s+Box\s+\d+)", re.I)
_DOC_WORDS = re.compile(r"^(?:quote|quotation|invoice|estimate|proposal|bid|agreement|contract|page\b|statement|receipt|"
                        r"work\s+order|order\s+form|customer|bill\s+to|ship\s+to|date|description|terms)\b", re.I)


def letterhead_line(text: str, lines: int = 14) -> str:
    """A letterhead with no company suffix ("All Year Pressure Washing", "Top Garden Landscaping"): among a page's first
    lines, a short title-case line with no digits, followed within three lines by a street or PO Box address. Not a
    document's own heading ("QUOTE", "Bid"), the association, or a customer block."""
    rows = [r.strip() for r in (text or "").splitlines() if r.strip()][:lines]
    for n, row in enumerate(rows):
        words = row.split()
        if not 2 <= len(words) <= 6 or re.search(r"\d|@|:", row) or _DOC_WORDS.match(row) or _NOT_A_HOLDER.search(row):
            continue
        if not all(w[:1].isupper() or w.lower() in ("&", "and", "of", "the") for w in words):
            continue
        if n and re.search(r"bill\s*to|c/o|customer|prepared\s+for|attn", rows[n - 1], re.I):
            continue
        if any(_ADDRESS_LINE.match(r) for r in rows[n + 1:n + 4]):
            return " ".join(words)
    return ""


def page_of(text: str, pos: int) -> tuple[int, int]:
    """The page holding ``pos``: between form feeds, the page breaks a PDF's text keeps. A text with none is one page."""
    start = text.rfind("\f", 0, pos) + 1
    end = text.find("\f", pos)
    return start, (len(text) if end < 0 else end)


def document_holder(text: str, head: int = 2500) -> str:
    """The business a page or document is from: the first eligible business name in its opening, else its letterhead
    line (``letterhead_line``)."""
    text = text or ""
    found = next((name for _, name in _names(text, 0, min(len(text), head))), "")
    return found or letterhead_line(text[:head])


def _holder(text: str, start: int, end: int, window: int = 260, after: int = 90) -> str:
    """The business name nearest the mention on its own page, skipping the association, banks, and customers: up to
    ``window`` characters before it (a letterhead or a header precedes its license), and only ``after`` characters after
    it (the same line or the next: "ACO 1234 EXAMPLE ALARM, INC."). Further down are other items' lines. A name on the
    next page of a packet belongs to the next item."""
    best: tuple[int, str] = (10 ** 9, "")
    ps, pe = page_of(text, start)
    lo = max(ps, start - window)
    for m, name in _names(text, lo, min(pe, end + after)):
        if _NOT_A_HOLDER.search(name) or len(name) < 5 or name.count(" ") == 0 and name.lower().startswith(("company", "co")):
            continue
        if _CUSTOMER_BEFORE.search(text[max(0, m.start() - 40):m.start()]):
            continue
        distance = start - m.end() if m.end() <= start else m.start() - end
        if 0 <= distance < best[0] or (distance < 0 and best[0] > 0):
            best = (max(distance, 0), name)
    return best[1]


def _number(m: re.Match[str]) -> str:
    groups = m.groupdict()
    return " ".join((groups.get("number") or groups.get("number2") or "").split())


def find_licenses(text: str) -> list[LicenseMention]:
    """Every license mention in ``text``, in order. A span one row claimed is not read again by a later row."""
    text = text or ""
    taken: list[tuple[int, int]] = []
    out: list[LicenseMention] = []
    letterheads: dict[tuple[int, int], str] = {}
    for kind, rx in _RX:
        for m in rx.finditer(text):
            s, e = m.span()
            if any(ts < e and s < te for ts, te in taken):
                continue
            number = _number(m)
            if not number:
                continue
            groups = m.groupdict()
            cls = " ".join(p for p in (groups.get("cls") or "", groups.get("cls2") or "") if p).upper()
            cls = re.sub(r"^C(\d)", r"C-\1", cls).replace("/C", "/C-").replace("C--", "C-")
            where = (groups.get("where") or "").upper()
            jurisdiction = _STATES.get(where, where) or kind.jurisdiction
            if kind.board is Board.NOTARY:
                state = re.search(r"STATE\s+OF\s+([A-Z][A-Za-z]{2,20})\b", m.group(0), re.I)
                jurisdiction = (state.group(1).title() if state else
                                "California" if re.search(r"Calif|C\.?llfornla|Califomia", m.group(0), re.I) else "")
            verify = VERIFY.get(kind.board, "")
            digits = re.sub(r"\D", "", number)
            if kind.board is Board.CSLB:
                verify = verify.format(number=digits.lstrip("0") or digits)
            elif "{number}" in verify:
                verify = verify.format(number=digits)
            if kind.board is Board.UNSPECIFIED and 5 <= len(digits) <= 7:
                verify = VERIFY[Board.CSLB].format(number=digits)
            # A notary's commission and a certification are a person's: no business holds them.
            holder = "" if kind.board in (Board.NOTARY, Board.CERTIFICATION) else _holder(text, s, e)
            note = kind.note
            # The letterhead of the mention's own page: a packet (a month's financial report with its invoices inside)
            # keeps its page breaks, so an invoice's license takes the invoice's letterhead, not the packager's.
            unpaged_packet = "\f" not in text and len(text) > UNPAGED_PACKET_CHARS
            if not holder and kind.board not in (Board.NOTARY, Board.CERTIFICATION) and not unpaged_packet:
                ps, pe = page_of(text, s)
                if (ps, pe) not in letterheads:
                    # A page of a packet has its letterhead in its first lines; lower down are ledger lines that name
                    # other vendors. A single document's opening is read further.
                    letterheads[(ps, pe)] = document_holder(text[ps:pe], head=600 if "\f" in text else 2500)
                holder = letterheads[(ps, pe)]
                note = (note + "; " if note else "") + "holder read from the page's letterhead" if holder else note
            out.append(LicenseMention(kind.key, kind.label, kind.board, number, cls, jurisdiction,
                                      holder, " ".join(m.group(0).split())[:200], s, e, verify, note))
            taken.append((s, e))
    return sorted(out, key=lambda x: x.start)


def resolve(mentions: list[LicenseMention]) -> list[LicenseMention]:
    """An unspecified number that another mention names with its board ("License #123456" here, "Contractor's License
    #123456" there) is that board's license: the board is taken from the mention that names it."""
    from dataclasses import replace

    named = {re.sub(r"\D", "", m.number): m for m in mentions if m.board not in (Board.UNSPECIFIED, Board.LOCAL)}
    out = []
    for m in mentions:
        other = named.get(re.sub(r"\D", "", m.number)) if m.board is Board.UNSPECIFIED else None
        out.append(replace(m, kind=other.kind, label=other.label, board=other.board, verify=other.verify,
                           classification=m.classification or other.classification,
                           note="the board named where the same number is printed elsewhere") if other else m)
    return out


def by_license(mentions: list[LicenseMention]) -> list[LicenseMention]:
    """One mention per license (board and number), the first that names a holder, else the first."""
    seen: dict[tuple[str, str], LicenseMention] = {}
    for m in mentions:
        if m.key not in seen or (not seen[m.key].holder and m.holder):
            seen[m.key] = m
    return list(seen.values())


__all__ = ["Board", "VERIFY", "LicenseKind", "KINDS", "LicenseMention", "find_licenses", "by_license"]
