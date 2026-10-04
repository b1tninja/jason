"""Contracts and proposals: who the parties are, what it costs, how long it runs, and whether the text shows it signed.

An executed contract not otherwise privileged is an association record (CIV 5200(a)(4)), and so is the board's written
approval of a vendor's proposal (CIV 5200(a)(5)); both are open to members for the current and the two previous fiscal
years (CIV 5210(a)(1)). A management agreement brings the managing agent's duties: the written statement a prospective
manager gives the board before the agreement (CIV 5375) and, for the association's funds, the trust account and the
board's prior written approval of large transfers (CIV 5380).

Contract layouts the reader knows (``contract``):

- ``nahs-roof-estimate``: North American Home Services' per-building roof estimates, DocuSigned, with the payment
  authorization page (the association's roof repair, 2023). The building subtotals must add to the authorized amount.
- ``contract``: every other agreement, read with the rule rows below: an agreement both sides sign (Bravo Security,
  Signal Service, Jensen, Helsing, Berding & Weil, Flock's order form), a vendor's form the customer signs (Pro Active
  Pest Control, North American Home Services' inspection agreement), an engagement letter (Newman CPA), and an accepted
  proposal or quote (CalPro, All Year Pressure Washing, Top Garden's bid).

Proposal layouts (``proposal``): ``nahs-roof-estimate`` again, then ``proposal`` for quotes and bids (All Year
Pressure Washing's quote, J.B. Bostick's PandaDoc proposal, Good Life Construction's JobTread proposal, Pro Elections'
letter with its two prices).

The vendor is the counterparty the specification names (``Mystique.senders()``) whose words appear first in the text;
a vendor the directory lacks is read from the letterhead.

Construction work brings the Contractors' State License Law: a licensee prints its license number on every bid and
contract (BPC 7030.5), and a home improvement contract asks a down payment of at most $1,000 or 10 percent of the price,
whichever is less, and no payment ahead of the work done or materials delivered (BPC 7159.5(a)(3), (5)). Whether a job
for the association is a home improvement (BPC 7151.2) the text cannot settle, so those findings are CHECKs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from jason.community.document_models import (
    DocumentModel,
    Finding,
    ModelContext,
    Severity,
    cents,
    date_after,
    dates_in,
    first,
    register,
    squash,
)
from jason.community.models.contracts_insurance import is_association, unit_count
from jason.community.models.contracts_signing import Execution, Signature, blank_date_after, read_signing
from jason.community.reviews import AS_OF, Reviewed
from jason.community.symbols import DocumentKind

SOON_DAYS = 60
RECORD = "CIV 5200(a)(4), 5210(a)(1)"


class ContractForm(Enum):
    AGREEMENT = "agreement"                  # both sides sign
    VENDOR_FORM = "vendor_form"              # the customer signs the vendor's form or order
    ENGAGEMENT_LETTER = "engagement_letter"  # a professional's letter the client countersigns
    ACCEPTED_PROPOSAL = "accepted_proposal"  # a proposal, quote, or bid the customer signs to accept


class Period(Enum):
    ONE_TIME = "one_time"
    VISIT = "visit"
    MONTH = "month"
    YEAR = "year"
    HOUR = "hour"
    UNIT = "unit"         # a price for each of something ("Price per unit to replace ...")
    PERCENT = "percent"   # a share of something (a contingency fee)


class StatementItem(Enum):
    """What CIV 5375 has a prospective managing agent's written statement give the board."""

    OWNERS = "owners, directors, and officers (5375(a))"
    LICENSES = "licenses held, with their dates (5375(b))"
    CERTIFICATIONS = "professional certifications and designations (5375(c))"
    AFFILIATES = "businesses it has an interest in or incentives from (5375(d))"
    REFERRAL_FEES = "referral fees from resale-document providers (5375(e))"


@dataclass(frozen=True)
class Price:
    label: str
    amount: int | None = None   # cents
    per: Period = Period.ONE_TIME
    percent: float | None = None


@dataclass(frozen=True)
class LineItem:
    description: str
    amount: int  # cents


@dataclass
class Contract:
    title: str = ""
    vendor: str = ""
    vendor_role: str = ""                  # the specification's word for the counterparty ("prior manager")
    client: str = ""
    form: ContractForm | None = None
    dated: date | None = None              # the date the document gives itself
    commencement_blank: bool = False       # "commencing on ________"
    signed_on: date | None = None
    execution: Execution | None = None
    signatures: tuple[Signature, ...] = ()
    envelopes: tuple[str, ...] = ()        # e-signature envelope or reference ids
    certified: bool = False                # a platform certificate says the envelope completed
    term_months: int | None = None
    auto_renews: bool = False
    renewal_months: int | None = None
    notice_days: int | None = None
    term_end: date | None = None           # the initial term's end
    current_term_end: date | None = None   # with the automatic renewals up to the as-of date; the as-of lens fills it, not the parse
    prices: tuple[Price, ...] = ()
    items: tuple[LineItem, ...] = ()
    total: int | None = None
    authorized: int | None = None          # an authorization form's amount
    validity_days: int | None = None
    scope: str = ""
    license: str = ""
    units: tuple[int, ...] = ()            # every count of the community's units the document states
    spending_limit: int | None = None      # a manager's unapproved-expenditure limit
    unlimited_transfers: bool = False      # a manager may move funds between accounts without regard to amount
    manager_statement: tuple[StatementItem, ...] = ()   # the CIV 5375 items a statement inside the agreement gives
    blank_signature_lines: int = 0


@dataclass
class Proposal:
    vendor: str = ""
    number: str = ""
    prepared_for: str = ""
    proposal_date: date | None = None
    valid_until: date | None = None
    validity_days: int | None = None
    scope: str = ""
    items: tuple[LineItem, ...] = ()
    options: tuple[LineItem, ...] = ()      # alternative prices ("if ballots are required")
    payment_schedule: tuple[LineItem, ...] = ()
    total: int | None = None
    price: int | None = None               # the total, or the lowest option
    accepted_on: date | None = None
    execution: Execution | None = None
    signatures: tuple[Signature, ...] = ()
    license: str = ""
    units: tuple[int, ...] = ()


# Rule rows ----------------------------------------------------------------------------------------------------------

_M = r"\$\s?[\d,]+(?:\.\d\d)?"
# (pattern with one money group, label, period); every match is a price, in text order.
PRICE_RULES: tuple[tuple[str, str, Period], ...] = (
    (rf"Total Fee:\s*({_M})", "total fee", Period.ONE_TIME),
    (rf"Contract Total:\s*({_M})", "contract total", Period.ONE_TIME),
    (rf"Annual Recurring Subtotal:\s*({_M})", "annual recurring", Period.YEAR),
    (rf"Total Monthly Charge:\s*({_M})", "total monthly charge", Period.MONTH),
    (rf"monthly service price of ({_M})", "monthly service price", Period.MONTH),
    (rf"(?<!Total )Monthly Charge:\s*({_M})", "monthly charge", Period.MONTH),
    (rf"Recurring Charge:\s*({_M})", "recurring charge per service", Period.VISIT),
    (rf"Regular Rate:\s*({_M})\s*/\s*per patrol", "per patrol", Period.VISIT),
    (rf"At \d+ Units:\s*({_M})", "base monthly fee", Period.MONTH),
    (rf"Quote Total\s*({_M})", "quote total", Period.ONE_TIME),
    (rf"fees for these services will be ({_M})", "fee estimate", Period.ONE_TIME),
    (rf"Irrigation Repairs:\s*({_M}) Per Hour", "irrigation repairs per hour", Period.HOUR),
)
PERCENT_RULES: tuple[tuple[str, str], ...] = (
    (r"fee shall be [a-z -]+\((\d+(?:\.\d+)?)%\) of the net recovery", "of the net recovery"),
)
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20,
          "thirty": 30, "sixty": 60, "ninety": 90}
# (pattern, what it sets); the first match of each kind wins.
TERM_RULES: tuple[tuple[str, str], ...] = (
    (r"initial (?:period|term) of (\d+) month", "term"),
    (r"original term of this Agreement is (\d+) months", "term"),
    (r"Initial Term:\s*(\d+) Months", "term"),
    (r"for a term of [a-z]+ \((\d+)\) months", "term"),
    (r"term of this agreement is MONTH to\s+MONTH", "monthly"),
    (r"Term \(if applicable\):\s*Yearly", "yearly"),
    (r"automatically renew for successive (\w+)-year periods", "renew-years"),
    (r"Renewal Term:\s*(\d+) Months", "renew-months"),
    (r"shall automatically renew for a like term", "renew-like"),
    (r"automatically renew on a month to month basis", "renew-monthly"),
    (r"service will continue until (\d+) day advance notice", "renew-monthly-notice"),
    (r"automatically renew for successive renewal terms", "renew-like"),
)
# Notice to end or not renew, where the clause states it; else the first "N days' written notice" near "terminate".
NOTICE_RULES: tuple[str, ...] = (
    r"no less than (\d+) days before the expiration",
    r"notice of non-renewal at least [a-z-]+ \((\d+)\) days prior",
    r"may cancel this agreement (\d+) days prior",
)
_NOTICE = re.compile(r"(\d+|thirty|sixty|ninety|fifteen|ten)\s*(?:\(\d+\)\s*)?(?:calendar\s+|business\s+)?days?[’']?\s*(?:advance\s+)?(?:prior\s+)?"
                     r"(?:written\s+)?notice", re.I)
# A title stands on one line; its words never run across a line break ("S\nESTIMATE" is a logo's letter and a title).
_TITLE = re.compile(r"^[ \t]*((?:[A-Z][A-Z&'’.,-]*[ \t]+){0,6}(?:AGREEMENT|CONTRACT|PROPOSAL|QUOTE|ESTIMATE|BID|ORDER FORM))"
                    r"(?:[ \t]+-[ \t]+[A-Z ]+)?[ \t]*$", re.M)
# A heading about the agreement, not its title ("PARTIES TO THE AGREEMENT", "SERVICES INCLUDED IN YOUR AGREEMENT").
_NOT_TITLE = re.compile(r"^(?:PARTIES|TERMS|SIGNATURES?|EXHIBIT|SCHEDULE)\b|\b(?:TO|OF|IN) (?:THE|THIS|YOUR)\b")
# A document that titles itself in mixed case, alone on a line ("Proposal", "Bid").
_PLAIN_TITLE = re.compile(r"^[ \t]*(Proposal|Bid|Estimate|Quote|Order Form|Engagement Letter)[ \t]*$", re.M)
# Work that takes a contractor's license: the licensee prints its number on every bid and contract (BPC 7030.5). An
# inspection, a service, or a consultation is not construction work.
CONTRACTOR_WORK = re.compile(r"roof(?!\s*inspection)|paint|stucco|asphalt|paving|concrete|seal ?coat|landscap|irrigation|plumb|"
                             r"electrical|fenc|construction|remodel|carpentry|dry ?rot|siding|gutter|repair", re.I)
NOT_CONTRACTOR_WORK = re.compile(r"inspection agreement|purpose of (?:the )?(?:roof )?inspection|engagement|legal services|"
                                 r"management service|election", re.I)
# What the work is, in the document's own words; the first that matches wins.
SCOPE_RULES = re.compile("|".join((
    r"^Re:\s*([^\n]+)",
    r"(?-i:SUBJECT):\s*([^\n]+)",
    r"Scope of Work\s*\n?\s*Description\s*([^\n]+)",
    r"Description\s*\nQty\s*\nUnit price\s*\nTotal price\s*\n([^\n]+)",
    r"\n([^\n]*Service Subscription)\n",
    r"Service:\s*\n?\s*([^\n]+)",
    r"PURPOSE OF INSPECTION\.\s*([^.]+\.)",
    r"Retention of MANAGER\.\s*([^.]{10,300}\.)",
    r"SCOPE OF ATTORNEYS[’'] SERVICES FOR CLIENT\s*\n\s*([^.]{10,300}\.)",
    r"DESCRIPTION\s*\nTOTAL\s*\n([^\n]+)",
    r"SCOPE OF SERVICES:\s*([^.]{10,300}\.)",
    r"Product and Services Description\s*\n(?:[^\n]*\n){0,6}?([^\n]*(?:Platform|Services)[^\n]*)",
    r"SCOPE OF WORK:\s*\n(?:[^\n]*\n){0,5}?\s*(Provide [^\n]+)",
)), re.I | re.M)
# A license number: the CSLB's (digits), or another board's with its letters ("License #: PR6993", a pest control operator).
# "California Contractors License No. 979670-B" and "CSLB# 1119271" print the number after "No." or "#"; a CSLB number may
# carry its classification after a hyphen, which is kept.
_LICENSE = re.compile(r"(?:Contractors?'?\s+License\s*(?:No\.?|Number|#)\s*:?|CSLB\s*(?:#|No\.?|License)\s*:?|License\s*(?:No\.?|#)?\s*:?|"
                      r"Lic\.?\s*#|CA STATE LICENSE #|License Number:?|C10)\s*([A-Z]{0,2}\d{5,7}(?:-[A-Z]{1,2}\d{0,2})?|[A-Z]{2}\d{4})\b",
                      re.I)
_UNITS = re.compile(r"# of residential living units:\s*(\d+)|(\d+) ownership\s+units|consist(?:s|ing) of (\d+) units|At (\d+) Units:", re.I)
_CLIENT = (
    r"and\s+([A-Z][^()\n]{2,80}?)\.?\s*\((?:the\s+)?[“\"]?Client[”\"]?\)",
    r"Client[’']s Name:\s*([^\n_]{3,80})",
    r"Customer:\s*\n?\s*([^\n]{3,80})",
    r"\nClient\s*\n\s*([^\n]{3,80})\n",
    r"Legal Entity Name:\s*\n?\s*([^\n]{3,80})",
    r"(?:\band|between)\s+([A-Z][A-Za-z ]{2,60}?(?:COMMUNITY ASSOCIATION|Community Association|Homeowners Association|HOA))\b",
)


def _money(value: int | None) -> str:
    return "?" if value is None else f"${value / 100:,.0f}" if value % 100 == 0 else f"${value / 100:,.2f}"


def _plain(text: str) -> str:
    return re.sub(r"[​ ]", " ", text or "")


def _number(word: str) -> int | None:
    word = word.lower()
    return int(word) if word.isdigit() else _WORDS.get(word)


def _add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    for d in (day.day, 30, 29, 28):
        try:
            return date(year, month, d)
        except ValueError:
            continue
    return day


_SKIP_KINDS = {"government agency", "utility", "bank", "owner or resident", "service platform", "title or escrow company",
               "another community association"}


def counterparty(text: str, context: ModelContext):
    """The specification's counterparty (a ``Sender``) whose words appear first in the text, not counting a name in an
    address block ("TO: RealManage", "Association c/o RealManage"), or None."""
    senders = ()
    if context.community is not None and hasattr(context.community, "senders"):
        try:
            senders = tuple(context.community.senders())
        except Exception:
            senders = ()
    folded = " " + re.sub(r"[^A-Z0-9]+", " ", _plain(text).upper()) + " "
    best = None
    for s in senders:
        if getattr(s.kind, "value", "") in _SKIP_KINDS:
            continue
        for word in s.words:
            key = " " + re.sub(r"[^A-Z0-9]+", " ", word.upper()).strip()
            for m in re.finditer(re.escape(key), folded):
                before = folded[max(0, m.start() - 30): m.start()]
                if re.search(r"\b(?:TO|C O|ATTN|BILLING CONTACT)\s*$|\bASSOCIATION\b", before) \
                        or re.match(r"\w*\s(?:COM|NET|ORG)\b", folded[m.end():]):  # an email or web address
                    continue
                if best is None or m.start() < best[0]:
                    best = (m.start(), s)
                break
    return best[1] if best else None


def vendor_of(text: str, context: ModelContext) -> str:
    """The counterparty the specification names whose words appear first in the text; else the company the letterhead
    or the parties clause names; else the website on the letterhead."""
    sender = counterparty(text, context)
    if sender is not None:
        return sender.name
    head = _plain(text)[:4000]
    for pattern in (r"\nCompany\s*\n\s*([^\n]{3,60})\n",
                    r"^\s*([A-Z][A-Za-z&.,' ]{2,60}?(?:,? Inc\.?|,? LLC|,? LLP|Company|Corporation|Group, Inc\.))\s*$",
                    r"by and between\s+([A-Z][A-Za-z&.' ]{2,60}?)\s*\(",
                    r"^\s*([A-Z][A-Za-z&' ]{2,40}(?:Security Services|SECURITY SERVICES|Landscaping|LANDSCAPING|Painting|Construction|"
                    r"Roofing|Plumbing|Electric|Pressure Washing|Pest Control|Paving|Cleaning|Elections))\b",
                    r"(?:Website|www)[:.]?\s*(?:www\.)?([A-Za-z0-9-]+\.com)"):
        m = re.search(pattern, head, re.M)
        if m:
            return squash(m.group(1)).rstrip(",")
    return ""


def _client(text: str) -> str:
    for pattern in _CLIENT:
        m = re.search(pattern, text)
        if m:
            value = squash(m.group(1)).strip(" ,.")
            if value and not re.fullmatch(r"_+", value):
                return value
    return ""


def _prices(text: str) -> list[Price]:
    found: list[tuple[int, Price]] = []
    for pattern, label, period in PRICE_RULES:
        for m in re.finditer(pattern, text, re.I):
            found.append((m.start(), Price(label, cents(m.group(1)), period)))
    for pattern, label in PERCENT_RULES:
        for m in re.finditer(pattern, text, re.I):
            found.append((m.start(), Price(label, None, Period.PERCENT, float(m.group(1)))))
    seen: set[tuple] = set()
    out = []
    for _at, p in sorted(found, key=lambda x: x[0]):
        key = (p.label, p.amount, p.percent)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _terms(text: str) -> tuple[int | None, bool, int | None, int | None]:
    """Initial term in months, whether it renews itself, the renewal term, and the notice to end it, in days."""
    flat = squash(text)
    term = renewal = notice = None
    renews = False
    for pattern, what in TERM_RULES:
        m = re.search(pattern, flat, re.I)
        if not m:
            continue
        if what == "term" and term is None:
            term = int(m.group(1))
        elif what == "monthly":
            term = term or 1
            renews, renewal = True, 1
        elif what == "yearly":
            term = term or 12
        elif what == "renew-years" and renewal is None:
            years = _number(m.group(1))
            renews, renewal = True, 12 * years if years else None
        elif what == "renew-months" and renewal is None:
            renews, renewal = True, int(m.group(1))
        elif what == "renew-like":
            renews = True
        elif what == "renew-monthly":
            renews, renewal = True, 1
        elif what == "renew-monthly-notice":
            renews, renewal = True, renewal or 1
            notice = int(m.group(1))
    if renews and renewal is None:
        renewal = term
    for pattern in NOTICE_RULES:
        m = re.search(pattern, flat, re.I)
        if m and notice is None:
            notice = int(m.group(1))
    for m in _NOTICE.finditer(flat):
        near = flat[max(0, m.start() - 160): m.end() + 160].lower()
        if notice is None and re.search(r"terminat|cancel|non-renewal|renew|discontinue", near):
            notice = _number(m.group(1))
    return term, renews, renewal, notice


def _items_by_chunks(section: str) -> list[LineItem]:
    """Line items in a section where each price stands on its own line after its description."""
    out = []
    chunk: list[str] = []
    for raw in section.split("\n"):
        line = squash(_plain(raw))
        m = re.fullmatch(r"\$\s?([\d,]+\.\d\d)", line)
        if m:
            # The item's title is a short line with its long description after it; else the last short line.
            words = [l for l in chunk if re.search(r"[A-Za-z]{3}", l)]
            short = [i for i, l in enumerate(words) if len(l.split()) <= 7 and not l.endswith(":")]
            titled = [i for i in short if i + 1 < len(words) and len(words[i + 1].split()) > 7]
            pick = titled[-1] if titled else short[-1] if short else 0
            description = words[pick] if words else ""
            if description:
                out.append(LineItem(description, cents(line)))
            chunk = []
        elif line:
            chunk.append(line)
    return out


def _table_items(text: str) -> list[LineItem]:
    """A quote's table: description, quantity, unit price, total price, one per line."""
    return [LineItem(squash(m.group(1)), cents(m.group(4)))
            for m in re.finditer(r"\n([^\n$]{4,})\n(\d+)\n(\$[\d,]+\.\d\d)\n(\$[\d,]+\.\d\d)\n", _plain(text))]


def _numbered_options(text: str) -> list[LineItem]:
    """Numbered priced options ("1. Exterior preparation & repainting ...\\n$64,800.00")."""
    return [LineItem(squash(m.group(1)), cents(m.group(2)))
            for m in re.finditer(r"^\s*\d\.\s+([^\n]{5,160})\n\s*(\$[\d,]+\.\d\d)\s*$", text, re.M)]


def _service_lines(text: str) -> list[LineItem]:
    """An alarm proposal's monthly service lines ("UL Primary Fire ...\\n$36.00 Existing service")."""
    return [LineItem(squash(m.group(1)), cents(m.group(2)))
            for m in re.finditer(r"^\s*\d+\s*\n([^\n$]{4,80})\n(\$[\d,]+\.\d\d) Existing service", text, re.M)]


def _units(text: str) -> tuple[int, ...]:
    return tuple(dict.fromkeys(int(next(g for g in m.groups() if g)) for m in _UNITS.finditer(text or "")))


def _title(text: str) -> str:
    """The document's own title: an upper-case heading near the top (else anywhere, as when a long addendum comes first),
    with the upper-case line before a one-word heading ("COMMERCIAL LEASE ... INSPECTION\\nAGREEMENT"); else a
    mixed-case title line ("Proposal")."""
    found: list[tuple[int, str]] = []
    for window in (text[:8000], text):
        found = [(m.start(), t) for m in _TITLE.finditer(window)
                 if not _NOT_TITLE.search(t := re.sub(r"\b(\w+(?: \w+)*) \1\b", r"\1", squash(m.group(1))))]
        if found:
            break
    titles: list[str] = []
    opening: list[str] = []   # a heading the parties clause follows ("... AGREEMENT\nTHIS ... AGREEMENT is made ...")
    for at, title in found:
        if " " not in title:
            before = text[:at].rstrip("\n \t").rsplit("\n", 1)[-1].strip()
            if before and not re.search(r"[a-z]", before) and len(re.findall(r"[A-Z]{3,}", before)) >= 2 and len(before.split()) <= 12:
                title = f"{squash(before)} {title}"
        if title not in titles:
            titles.append(title)
            if re.search(r"is made|entered into|by and between", text[at: at + 400], re.I):
                opening.append(title)
    if titles:
        return next((t for t in opening + titles if len(t.split()) >= 2), titles[0])
    plain = _PLAIN_TITLE.search(text[:3000])
    return plain.group(1) if plain else ""


def _price_period(label: str) -> Period:
    return Period.UNIT if re.search(r"\bper unit\b|\bunit (?:cost|price)\b|\beach\b", label, re.I) else Period.ONE_TIME


_STATEMENT = re.compile(r"Statement of Information|pursuant to (?:California )?Civil Code Section 5375|CIV(?:il Code)? §?\s*5375", re.I)
# (item, words in the statement that give it); a rule row per 5375 subdivision.
STATEMENT_RULES: tuple[tuple[StatementItem, str], ...] = (
    (StatementItem.OWNERS, r"Board of Directors is as follows|\bowners?\b|general partners?|shareholders?|\bofficers?\b|\bPresident\b"),
    (StatementItem.LICENSES, r"licen[sc]e"),
    (StatementItem.CERTIFICATIONS, r"certif|designation|credential"),
    (StatementItem.AFFILIATES, r"ownership interests?|profit.sharing|monetary incentives?|affiliated (?:business|compan)"),
    (StatementItem.REFERRAL_FEES, r"referral fee|third.party provider|Sections? 4528"),
)


def manager_statement(text: str) -> tuple[StatementItem, ...]:
    """The CIV 5375 items a managing agent's statement inside the agreement gives, read from the statement alone."""
    m = _STATEMENT.search(text)
    if not m:
        return ()
    end = re.search(r"IN\s+WITNESS\s+WHEREOF", text[m.end():])
    block = text[m.start(): m.end() + (end.start() if end else 6000)]
    return tuple(item for item, words in STATEMENT_RULES if re.search(words, block, re.I))


def contractor_work(*words: str) -> bool:
    """Whether the document is for work that takes a contractor's license, by its title, scope, and vendor."""
    joined = " ".join(w for w in words if w)
    return bool(CONTRACTOR_WORK.search(joined)) and not NOT_CONTRACTOR_WORK.search(joined)


def license_finding(license: str, *words: str) -> list[Finding]:
    if license or not contractor_work(*words):
        return []
    return [Finding("license-not-printed", "the text prints no contractor's license number for construction work; a licensee must "
                    "print it on every bid and contract, so look it up on the CSLB's site before the board signs", Severity.CHECK,
                    "BPC 7030.5")]


# The NAHS roof estimate --------------------------------------------------------------------------------------------

_NAHS = re.compile(r"ROOF INFO:\s*Building\s*\d", re.I)


def _nahs_items(text: str) -> list[LineItem]:
    out = []
    parts = re.split(r"ROOF INFO:\s*Building\s*", text)
    for part in parts[1:]:
        building = re.match(r"(\d+)", part)
        sub = re.search(r"SUBTOTAL:\s*\n?\s*\$([\d,]+(?:\.\d\d)?)", part)
        if building and sub:
            out.append(LineItem(f"Building {building.group(1)} roof repairs", cents("$" + sub.group(1))))
    return out


def _authorized(text: str) -> int | None:
    # Tesseract gives each cell its own line; a vision reading gives the form's table as "label | label" over
    # "value | value" ("PROPERTY ADDRESS: | AUTHORIZED AMOUNT:" then "3000 Macon Dr | 16,275").
    m = (re.search(r"\| AUTHORIZED AMOUNT:[^\n]*\n[^\n|]*\|\s*\$?([\d,]{3,})(?:\.\d\d)?\s*(?:\||\n)", text)
         or re.search(r"AUTHORIZED AMOUNT:\s*\n(?:[^\n]*\n){0,2}?\s*\$?([\d,]{3,})(?:\.\d\d)?\s*\n", text))
    return cents("$" + m.group(1)) if m else None


def _validity(text: str) -> int | None:
    m = re.search(r"(?:withdrawn|WITHDRAWN)(?: by us)? if not\s+accepted within (\d+) days|VALID FOR (\d+) DAYS", squash(text), re.I)
    return int(next(g for g in m.groups() if g)) if m else None


# Contracts ----------------------------------------------------------------------------------------------------------

_AGREEMENT_WORDS = re.compile(r"\bAGREEMENT\b|\bCONTRACT\b|ORDER FORM|engagement|PROPOSAL|QUOTE|ESTIMATE|\bBid\b", re.I)


def _form(text: str) -> ContractForm:
    if re.search(r"we are pleased to confirm our acceptance|engagement letter", text, re.I):
        return ContractForm.ENGAGEMENT_LETTER
    if re.search(r"IN\s+WITNESS\s+WHEREOF|The Parties have executed|AGREED AND ACCEPTED BY|Representative, [A-Z][a-z]+ [A-Z]", text):
        return ContractForm.AGREEMENT
    if re.search(r"Customer signed on|Please enter your First and Last Name", text, re.I):
        return ContractForm.VENDOR_FORM
    if re.search(r"Customer Acceptance|ACCEPTANCE OF PROPOSAL|By signing below, I agree to have the work|hereby accepted|DocuSigned by",
                 text, re.I):
        return ContractForm.ACCEPTED_PROPOSAL
    if re.search(r"\b(?:Bid|Estimate|Proposal|Quote)\b", text[:3000]):
        return ContractForm.ACCEPTED_PROPOSAL
    return ContractForm.AGREEMENT


def _date_right_after(label: str, text: str) -> date | None:
    """A date printed right after ``label`` (on the same or the next line), not one further on."""
    return date_after(label, text, window=24)


def _read_contract(text: str, context: ModelContext) -> Contract | None:
    text = _plain(text)
    if not _AGREEMENT_WORDS.search(text):
        return None
    r = Contract()
    r.title = _title(text)
    sender = counterparty(text, context)
    r.vendor = sender.name if sender is not None else vendor_of(text, context)
    r.vendor_role = getattr(sender, "role", "") if sender is not None else ""
    r.client = re.split(r"\s+c/o\b", _client(text), flags=re.I)[0].strip(" ,.")
    if not r.client and context.community is not None and is_association(text[:4000], context):
        r.client = str(getattr(context.community, "name", ""))
    r.form = _form(text)
    flat = squash(text)
    r.dated = (_date_right_after(r"entered into as of", flat) or _date_right_after(r"Proposal Date:?", flat)
               or _date_right_after(r"Quote Date", flat) or _date_right_after(r"Estimate\s+Date:?", flat)
               or _date_right_after(r"(?m)^[ \t]*Date:", text)
               or (dates_in(re.sub(r"Revised\s+\S+", "", squash(text[:400]))) or [None])[0])
    r.commencement_blank = blank_date_after(r"commenc(?:ing|e) on", text) or bool(re.search(r"is made this _{4,} day", text))
    signing = read_signing(text)
    r.signatures = signing.signatures
    r.envelopes = tuple(e.envelope_id for e in signing.envelopes if e.envelope_id)
    r.certified = signing.completed
    r.signed_on = signing.signed_on
    r.execution = signing.execution(one_side=r.form is not ContractForm.AGREEMENT)
    r.blank_signature_lines = signing.blank_lines
    r.term_months, r.auto_renews, r.renewal_months, r.notice_days = _terms(text)
    start = r.signed_on or r.dated
    if start and r.term_months:
        r.term_end = _add_months(start, r.term_months)   # the term running on a given day is the as-of lens's (``contract_term``)
    r.prices = tuple(_prices(text))
    items = _numbered_options(text) or _service_lines(text)
    r.items = tuple(items)
    if not r.prices and items:
        r.prices = tuple(Price(i.description, i.amount, _price_period(i.description)) for i in items)
    one_time = [p.amount for p in r.prices if p.per is Period.ONE_TIME and p.amount]
    r.total = one_time[0] if len(one_time) == 1 else next((p.amount for p in r.prices if p.label == "contract total"), None)
    r.validity_days = _validity(text)
    scope = SCOPE_RULES.search(text)
    r.scope = squash(next(g for g in scope.groups() if g)) if scope else r.title
    lic = _LICENSE.search(text)
    r.license = lic.group(1) if lic else ""
    r.units = _units(text)
    limit = re.search(r"single unapproved expenditure nor incur any obligation exceeding\s*(\$[\d,]+(?:\.\d\d)?)", squash(text))
    r.spending_limit = cents(limit.group(1)) if limit else None
    r.unlimited_transfers = bool(re.search(r"transfers of funds,?\s+without regard to (?:dollar )?amount", squash(text), re.I))
    r.manager_statement = manager_statement(text)
    return r


def _counterparty_ended(r) -> bool:
    return bool(re.search(r"\bprior\b|\bformer\b", r.vendor_role, re.I))


def current_term_end(r, as_of: date) -> date | None:
    """The end of the term running on ``as_of``: the initial term's end, rolled forward by the renewal period while the
    agreement renews itself."""
    if not r.term_end:
        return None
    end = r.term_end
    step = r.renewal_months or r.term_months
    while r.auto_renews and step and end < as_of:
        end = _add_months(end, step)
    return end


@AS_OF.check("contract-term", Contract, fields=("vendor_role", "dated", "commencement_blank", "term_months", "auto_renews",
                                                "renewal_months", "notice_days", "term_end"))
def contract_term(r, as_of: date, _facts=None) -> Reviewed:
    """As of a date: the term running then (the record's ``current_term_end``), and whether the term has ended or when
    notice of non-renewal is due."""
    found: list[Finding] = []
    current = current_term_end(r, as_of)
    if r.term_end and not _counterparty_ended(r):
        counted = " (counted from the signing date)" if r.commencement_blank or not r.dated else ""
        if not r.auto_renews and r.term_end < as_of:
            found.append(Finding("term-ended", f"the {r.term_months}-month term ended {r.term_end}{counted}", Severity.INFO))
        elif r.auto_renews and current and r.commencement_blank and (r.renewal_months or 0) > 1:
            found.append(Finding("auto-renewal", f"renews itself for {r.renewal_months} months; the current term would end "
                                 f"{current}{counted}, with {r.notice_days or '?'} days' notice to end it", Severity.INFO))
        elif r.auto_renews and current and (r.renewal_months or 0) > 1:
            deadline = current - timedelta(days=r.notice_days or 0)
            left = (deadline - as_of).days
            found.append(Finding("auto-renewal", f"renews itself for {r.renewal_months} months at {current}{counted}; "
                                 f"notice of non-renewal is due by {deadline} ({left} days)",
                                 Severity.CHECK if 0 <= left <= SOON_DAYS else Severity.INFO))
    return Reviewed(tuple(found), {"current_term_end": current})


def contract_findings(r: Contract, context: ModelContext) -> list[Finding]:
    found: list[Finding] = []
    who = r.vendor or "the vendor"
    if r.execution is Execution.NOT_IN_TEXT:
        blanks = f" ({r.blank_signature_lines} blank signature or date lines)" if r.blank_signature_lines else ""
        found.append(Finding("unsigned-in-text", f"no signature shows in the text{blanks}; an image signature would not, so confirm the "
                             "executed copy is on file", Severity.CHECK, RECORD))
    elif r.execution is Execution.SIGNED_BY_ONE:
        names = ", ".join(s.name or s.title or "a signer" for s in r.signatures)
        found.append(Finding("partly-signed", f"only one side's signature shows ({names}); confirm the other side signed", Severity.CHECK,
                             RECORD))
    else:
        found.append(Finding("association-record", f"an executed contract with {who}: an association record open to members for the "
                             "current and two previous fiscal years", Severity.INFO, RECORD))
    if r.envelopes and not r.certified and not any(s.method and s.method.value == "pandadoc" for s in r.signatures):
        found.append(Finding("no-signing-certificate", f"the DocuSign envelope ({r.envelopes[0]}) has no certificate of completion in the "
                             "file; keep the certificate with the contract", Severity.INFO))
    if r.commencement_blank:
        found.append(Finding("commencement-blank", "the start date is left blank; the term and renewals cannot be counted from the "
                             "document", Severity.CHECK))
    if r.client and context.community is not None and not is_association(r.client, context):
        found.append(Finding("client-not-association", f"the contract names {r.client!r} as the client, not the association", Severity.CHECK))
    if _counterparty_ended(r):
        found.append(Finding("counterparty-ended", f"the specification lists {who} as {r.vendor_role.split(';')[0]}; the agreement's "
                             "renewal terms no longer run", Severity.INFO))
    elif r.term_end and r.auto_renews and (r.renewal_months or 0) <= 1:
        found.append(Finding("month-to-month", f"runs month to month; either side may end it with {r.notice_days or '?'} days' notice",
                             Severity.INFO))
    found.append(contract_term)   # the as-of lens's place: the term ended, or it renews itself and notice is due
    monthly = [p.amount for p in r.prices if p.label == "total monthly charge" and p.amount]
    if monthly and r.items and sum(i.amount for i in r.items) != sum(monthly):
        found.append(Finding("service-lines-differ", f"the service lines add to {_money(sum(i.amount for i in r.items))} a month; the "
                             f"proposal's monthly totals add to {_money(sum(monthly))}", Severity.CHECK))
    if r.authorized is not None and r.items:
        total = sum(i.amount for i in r.items)
        if total != r.authorized:
            found.append(Finding("authorized-differs", f"the items add to {_money(total)}; the payment authorization is for "
                                 f"{_money(r.authorized)}", Severity.PROBLEM))
    if r.validity_days and r.dated and r.signed_on:
        late = (r.signed_on - r.dated).days - r.validity_days
        if late > 0:
            found.append(Finding("accepted-after-validity", f"accepted {r.signed_on}, {late} days after the {r.validity_days}-day window "
                                 f"from {r.dated}; the price held only if the vendor agreed", Severity.INFO))
    spec_units = unit_count(context)
    wrong = [n for n in r.units if spec_units and n != spec_units]
    if wrong:
        found.append(Finding("unit-count", f"the document counts {', '.join(map(str, wrong))} units; the specification has {spec_units}",
                             Severity.CHECK))
    if re.search(r"(?<!landscape )management (?:service )?agreement", r.title, re.I):
        if r.manager_statement:
            gives = "; ".join(i.value for i in r.manager_statement)
            found.append(Finding("manager-statement", f"the agreement carries the managing agent's statement ({gives}); the statute has "
                                 "it reach the board before the agreement is entered into, within 90 days", Severity.INFO, "CIV 5375"))
            lacking = [i for i in StatementItem if i not in r.manager_statement]
            if lacking:
                cited = ", ".join(re.findall(r"5375(\(\w\))", " ".join(i.value for i in lacking)))
                found.append(Finding("manager-statement-incomplete", "the statement does not say " + "; ".join(i.value for i in lacking)
                                     + "; the statute asks for each, even when the answer is none", Severity.CHECK, f"CIV 5375{cited}"))
        else:
            found.append(Finding("manager-disclosure", "before a management agreement the prospective manager must give the board a "
                                 "written statement of its owners, licenses, certifications, affiliated businesses, and referral fees; "
                                 "confirm it is on file", Severity.CHECK, "CIV 5375"))
        if r.unlimited_transfers:
            found.append(Finding("transfers-without-approval", "the agreement lets the manager move funds between the association's "
                                 "accounts without regard to amount; transfers out of the reserve or operating accounts need the "
                                 "board's prior written approval above the lesser of $10,000 or 5% of budgeted income (51 or more "
                                 "separate interests)", Severity.CHECK, "CIV 5380(b)(6)(B)"))
        if r.spending_limit:
            found.append(Finding("spending-limit", f"the manager may spend up to {_money(r.spending_limit)} without prior board approval",
                                 Severity.INFO))
    if re.search(r"attorney|legal services", r.title + " " + r.scope, re.I):
        found.append(Finding("may-be-privileged", "a fee agreement with the association's lawyers; executed contracts are records only "
                             "when not otherwise privileged", Severity.INFO, "CIV 5200(a)(4)"))
    found += license_finding(r.license, r.title, r.scope, r.vendor)
    return found


class NahsRoofEstimateContractModel(DocumentModel):
    kind = DocumentKind.CONTRACT
    name = "nahs-roof-estimate"
    required = ("vendor", "client", "dated", "items", "authorized", "signed_on")
    lens_checks = (contract_term,)

    def parse(self, text: str, context: ModelContext) -> Contract | None:
        if not _NAHS.search(text or ""):
            return None
        r = _read_contract(text, context)
        if r is None:
            return None
        r.form = ContractForm.ACCEPTED_PROPOSAL
        r.execution = read_signing(_plain(text)).execution(one_side=True)
        r.dated = date_after(r"\nDate:", text, window=30) or r.dated
        r.items = tuple(_nahs_items(text))
        r.total = sum(i.amount for i in r.items) or None
        r.prices = (Price("sum of the building estimates", r.total, Period.ONE_TIME),) if r.total else r.prices
        r.authorized = _authorized(text)
        r.scope = f"roof repairs on {len(r.items)} buildings"
        return r

    def check(self, r: Contract, context: ModelContext) -> list[Finding]:
        return contract_findings(r, context)


class ContractModel(DocumentModel):
    kind = DocumentKind.CONTRACT
    name = "contract"
    required = ("vendor", "client", "prices")
    lens_checks = (contract_term,)

    def parse(self, text: str, context: ModelContext) -> Contract | None:
        return _read_contract(text, context)

    def check(self, r: Contract, context: ModelContext) -> list[Finding]:
        return contract_findings(r, context)


# Proposals ----------------------------------------------------------------------------------------------------------

def _details_title(text: str) -> str:
    """JobTread's "PROPOSAL DETAILS": the first line after it that is not the job address, a price, or boilerplate."""
    m = re.search(r"PROPOSAL DETAILS\s*\n", text)
    if not m:
        return ""
    for line in text[m.end(): m.end() + 600].split("\n")[:5]:
        line = squash(line)
        if line and not re.search(r"\d{5}|^\$|additional work|^\d", line, re.I):
            return line
    return ""


def _read_proposal(text: str, context: ModelContext) -> Proposal | None:
    text = _plain(text)
    if not re.search(r"PROPOSAL|\bQUOTE\b|ESTIMATE|\bBid\b", text[:6000], re.I):
        return None
    r = Proposal()
    r.vendor = vendor_of(text, context)
    r.number = first(r"Quote Number\s*\n\s*([A-Z0-9-]+)", text) or first(r"Proposal No\.?\s*([A-Z0-9-]+)", text) or \
        first(r"^Proposal (\d+-\d+)\s*$", text, flags=re.M) or first(r"PROPOSAL #\s*\n(?:[^\n]*\n){0,2}?\s*[\d-]{8,10}\s*\n\s*([\d-]{4,})", text) or \
        first(r"Job ID:\s*([\d-]+)", text)
    r.prepared_for = first(r"PREPARED FOR\s*\n(?:[^\n]*\n)?\s*([^\n]*Association[^\n]*)", text) or first(r"BID TO:\s*\n(?:[^\n]*\n)?\s*([^\n]+)", text) \
        or first(r"Customer Details\s*\n(?:\s*\n)*(?:[^\n]*\n)?\s*([^\n]*Association[^\n]*)", text) or first(r"\n([^\n]*Community Association[^\n]*)\n", text)
    issue = re.search(r"Issue Date\s*\n\s*Expires", text)
    if issue:
        days = [d for d in dates_in(text[issue.end(): issue.end() + 4000])][:2]
        if len(days) == 2:
            r.proposal_date, r.valid_until = days
    r.proposal_date = r.proposal_date or date_after(r"Quote Date", text) or date_after(r"Proposal Date:?", text) or \
        date_after(r"DATE:\s*\n\s*PROPOSAL #\s*\n\s*ESTIMATOR", text) or date_after(r"\nDate:", text, window=30) or \
        (dates_in(squash(text)[:300]) or [None])[0]
    r.valid_until = r.valid_until or date_after(r"Valid Until", text)
    r.validity_days = _validity(text)
    if r.valid_until is None and r.validity_days and r.proposal_date:
        r.valid_until = r.proposal_date + timedelta(days=r.validity_days)
    r.scope = first(r"(?-i:SUBJECT):\s*([^\n]+)", text) or first(r"^RE:\s*(?:Proposal for\s+)?([^\n]+)", text, flags=re.M | re.I) \
        or first(r"Description\s*\nQty\s*\nUnit price\s*\nTotal price\s*\n([^\n]+)", text) \
        or first(r"Thank you for contacting [^\n]+ regarding the ([^\n(.]+)", text) or _details_title(text)
    total = re.search(r"Quote Total\s*(\$[\d,]+\.\d\d)|^\s*Total\s*\n\s*(\$[\d,]+\.\d\d)|^\s*TOTAL\s*\n\s*(\$[\d,]+\.\d\d)", text, re.M)
    r.total = cents(next(g for g in total.groups() if g)) if total else None
    r.options = tuple([LineItem(squash(m.group(1)), cents(m.group(2))) for m in re.finditer(r"TOTAL COST if ([^:\n]+):\s*(\$[\d,]+(?:\.\d\d)?)", text)]
                      + [LineItem(f"Option {m.group(1)}: {squash(m.group(2))}", cents(m.group(3).replace(" ", ""))) for m in
                         re.finditer(r"OPTION (\d+):\s*\n([^\n]+)\n(?:[^\n]*\n)?\s*FEE:\s*(\$\s*[\d,]+(?:\.\d\d)?)", text)])
    items = _table_items(text)
    if not items and total and re.search(r"^\s*Total\s*\n", text, re.M):
        items = _items_by_chunks(text[: total.start()])
    r.items = tuple(items or r.options)
    if not r.scope and r.items:
        r.scope = ", ".join(i.description for i in r.items[:6])
    schedule = re.search(r"PAYMENT SCHEDULE\s*\n(.*?)(?:This document|The above specifications)", text, re.S)
    r.payment_schedule = tuple(_items_by_chunks(schedule.group(1))) if schedule else ()
    r.price = r.total or (min(o.amount for o in r.options) if r.options else None)
    signing = read_signing(text)
    r.signatures = signing.signatures
    r.execution = signing.execution(one_side=True)
    r.accepted_on = signing.signed_on if r.execution is Execution.EXECUTED else None
    lic = _LICENSE.search(text)
    r.license = lic.group(1) if lic else ""
    r.units = _units(text)
    return r


@AS_OF.check("proposal-offer", Proposal, fields=("accepted_on", "valid_until"))
def proposal_offer(r, as_of: date, _facts=None) -> list[Finding]:
    """As of a date: whether an offer no one accepted is still open."""
    if r.accepted_on or not r.valid_until:
        return []
    if r.valid_until < as_of:
        return [Finding("offer-lapsed", f"no acceptance shows and the offer ran to {r.valid_until}", Severity.INFO)]
    return [Finding("offer-open", f"no acceptance shows; the offer is open to {r.valid_until} "
                    f"({(r.valid_until - as_of).days} days)", Severity.INFO)]


def proposal_findings(r: Proposal, context: ModelContext) -> list[Finding]:
    found: list[Finding] = []
    if r.accepted_on:
        found.append(Finding("accepted", f"accepted {r.accepted_on}; keep the board's written approval (minutes or a signed resolution) "
                             "with it", Severity.CHECK, "CIV 5200(a)(5)"))
        if r.valid_until and r.accepted_on > r.valid_until:
            found.append(Finding("accepted-after-validity", f"accepted {r.accepted_on}, after the offer's {r.valid_until} limit",
                                 Severity.INFO))
    elif not r.valid_until:
        found.append(Finding("no-acceptance", "no acceptance shows in the text and the proposal states no expiry", Severity.INFO))
    found.append(proposal_offer)   # the as-of lens's place: an offer no one accepted is open or has lapsed
    if r.items and r.total and len(r.items) > 1:
        added = sum(i.amount for i in r.items)
        if added != r.total:
            found.append(Finding("items-differ-from-total", f"the priced lines add to {_money(added)}, not the total {_money(r.total)} (some "
                                 "may be options)", Severity.CHECK))
    if r.payment_schedule and r.total:
        added = sum(i.amount for i in r.payment_schedule)
        if added != r.total:
            found.append(Finding("schedule-differs-from-total", f"the payment schedule adds to {_money(added)}, not the total "
                                 f"{_money(r.total)}", Severity.PROBLEM))
    spec_units = unit_count(context)
    wrong = [n for n in r.units if spec_units and n != spec_units]
    if wrong:
        found.append(Finding("unit-count", f"the proposal counts {', '.join(map(str, wrong))} units; the specification has {spec_units}",
                             Severity.CHECK))
    found += license_finding(r.license, r.scope, r.vendor, " ".join(i.description for i in r.items))
    found += payment_findings(r.payment_schedule, r.total or r.price)
    return found


DOWN_PAYMENT_LIMIT = 100_000   # cents: $1,000, or 10 percent of the price if less (BPC 7159.5(a)(3))
# A schedule line that is the down payment, and one billed before any work is done.
_DOWN_PAYMENT = re.compile(r"deposit|down payment", re.I)
_AHEAD_OF_WORK = re.compile(r"mobiliz|at signing|upon (?:signing|acceptance)|before (?:work|start)", re.I)


def payment_findings(schedule: tuple[LineItem, ...], price: int | None) -> list[Finding]:
    """A home improvement contract's down payment and payments ahead of the work (BPC 7159, 7159.5). Whether the work is a
    home improvement (BPC 7151.2) the text cannot settle, so each is a CHECK."""
    found: list[Finding] = []
    if not schedule or not price:
        return found
    down = next((i for i in schedule if _DOWN_PAYMENT.search(i.description)), None)
    limit = min(DOWN_PAYMENT_LIMIT, price // 10)
    if down is not None and down.amount > limit:
        found.append(Finding("down-payment-over-limit", f"the down payment {_money(down.amount)} is more than {_money(limit)}, the lesser "
                             "of $1,000 or 10 percent of the price, which a home improvement contract may ask", Severity.CHECK,
                             "BPC 7159.5(a)(3)"))
    for line in schedule:
        if line is not down and _AHEAD_OF_WORK.search(line.description):
            found.append(Finding("payment-ahead-of-work", f"{line.description!r} ({_money(line.amount)}, {line.amount / price:.0%} of the "
                                 "price) is billed before the work it pays for; beyond the down payment a home improvement contractor "
                                 "may not take payment ahead of the work done or materials delivered", Severity.CHECK, "BPC 7159.5(a)(5)"))
    return found


class NahsRoofEstimateProposalModel(DocumentModel):
    kind = DocumentKind.PROPOSAL
    name = "nahs-roof-estimate"
    required = ("vendor", "proposal_date", "items", "total")
    lens_checks = (proposal_offer,)

    def parse(self, text: str, context: ModelContext) -> Proposal | None:
        if not _NAHS.search(text or ""):
            return None
        r = _read_proposal(text, context)
        if r is None:
            return None
        r.items = tuple(_nahs_items(text))
        r.total = r.price = sum(i.amount for i in r.items) or None
        r.scope = f"roof repairs on {len(r.items)} buildings"
        return r

    def check(self, r: Proposal, context: ModelContext) -> list[Finding]:
        return proposal_findings(r, context)


_BILL = re.compile(r"\bINVOICE\s*(?:#|No\.?|Number|Date)|\bBalance Due\b|\bAmount Due\b|\bPayment Due\b|\bInvoice\b\s*\n?\s*#?\s*\d{3,}|"
                   r"\bReceipt\b|\bPaid\b\s+\$", re.I)
_OFFER = re.compile(r"\bProposal\b|\bEstimate\b|\bQuot(?:e|ation)\b|\bBid\b|\bScope of Work\b", re.I)


def _is_bill(text: str) -> bool:
    """An invoice or receipt, not an offer: its first page speaks of what is due and never of a proposal or estimate. The
    question sets found the proposal reader taking vendors' and cloud providers' invoices (September 30, 2026)."""
    head = (text or "")[:2500]
    return bool(_BILL.search(head)) and not _OFFER.search(head)


class ProposalModel(DocumentModel):
    kind = DocumentKind.PROPOSAL
    name = "proposal"
    required = ("vendor", "proposal_date", "price", "scope")
    lens_checks = (proposal_offer,)

    def parse(self, text: str, context: ModelContext) -> Proposal | None:
        if _is_bill(text):
            return None                            # a bill for work, not an offer of it (read by the invoice models)
        return _read_proposal(text, context)

    def check(self, r: Proposal, context: ModelContext) -> list[Finding]:
        return proposal_findings(r, context)


register(NahsRoofEstimateContractModel())
register(ContractModel())
register(NahsRoofEstimateProposalModel())
register(ProposalModel())

__all__ = ["ContractForm", "Period", "StatementItem", "Price", "LineItem", "Contract", "Proposal", "NahsRoofEstimateContractModel",
           "ContractModel", "NahsRoofEstimateProposalModel", "ProposalModel", "vendor_of", "manager_statement", "contractor_work",
           "payment_findings", "PRICE_RULES", "TERM_RULES", "STATEMENT_RULES", "CONTRACTOR_WORK"]
