"""Grant deeds: the developers' deeds of the common area and the units, and each resale since.

The record wraps ``jason.community.parsing`` (``GrantDeedMixin`` recognizes the form; ``apn_fields`` and ``unit_fields``
read the assessor number and the unit blank), ``jason.community.consideration`` (the granting clause and the documentary
transfer tax, county and city), and the recorder's stamp from ``jason.community.readings``. Sacramento County's tax is
fifty-five cents per five hundred dollars and the City of Sacramento's two dollars seventy-five per thousand, so the two
declared amounts must compute the same consideration (``consideration.deed_price``).

Many copies in the library are the title company's, sent to the association with its sale notice. They carry no county
stamp; a certified copy carries the title company's certification instead ("certified to be a true copy ... recorded
6/19/2019, Book 2019 0619, Page 681"), often handwritten, which a vision reading of page 1 makes legible. ``number`` is
taken from the stamp, then the certification, then the file name's number, and ``number_source`` says which; a number
from the name alone, or a certification that disagrees with the name, is a CHECK for a person with the county index. The
text may open with that vision reading, followed by the older text of the same pages (``layers``): the stamp, the parcel
numbers, the unit, and the taxes are read from the vision reading when it has them. Grantor and grantee are public
record; the record keeps them as the text gives them, and nothing here copies them elsewhere.

A unit number alone does not place a deed (two numberings reused the same numbers; the unit numbers note in ``mystique/notes/unit-numbers.md``). The check
only says when the deed's own unit and assessor number fit none of the specification's numberings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import date
from enum import Enum

from jason.community.consideration import deed_price, granting_clause
from jason.community.document_models import DocumentModel, Finding, ModelContext, Severity, amount_after, dates_in, register, squash
from jason.community.parsing import GrantDeedMixin, Page, Reading, apn_fields, unit_fields
from jason.community.readings import Relation
from jason.community.reports import parent_parcel, unit_parcels
from jason.community.symbols import DocumentKind

from .governing_shared import (
    Recording,
    citations,
    name_number,
    number_date,
    recording,
    recording_findings,
    spec_parcels,
    spec_unit_blocks,
)

_COUNTY_STEP_CENTS = 55  # per $500 of consideration (consideration.py)
_STATUTE_AS_TAX_CENTS = 11911  # R&T 11911 handwritten in the tax blank of an exempt deed, read as "$ 119.11"
_VISION_MARK = "--- ocr: ollama-vision ---"  # jason.tasks.library.VISION_MARK: a vision reading of the first pages comes first
_VISION_END = "--- end ocr: ollama-vision ---"  # jason.tasks.library.VISION_END: where the older text starts


class NumberSource(Enum):
    """Where ``number`` came from. The county's stamp is the record; a title company's certification repeats it by hand or
    by its own stamp; the file name is what a person typed when the copy was filed."""

    STAMP = "stamp"                              # the recorder's Doc# or BOOK/PAGE, whole
    SPACED = "spaced"                            # a Doc# whose digits OCR split
    STAMP_AND_NAME = "stamp and name"            # an old BOOK/PAGE stamp OCR mangled, completed from the file name
    CERTIFICATION = "certification"              # the title company's "certified to be a true copy ... recorded" block
    CERTIFICATION_AND_NAME = "certification and name"  # that block's date (or year and page) agrees with the file name's number
    NAME = "name"                                # nothing in the text: the file name's number


# A title company's certification of a copy: "CERTIFIED TO BE A TRUE COPY / RECORDED 6/19/2019 / BOOK 2019 0619 PAGE 681",
# "certified to be a true and exact copy of the original document recorded on 11/7/08 ... Instrument No.: 2008-1337",
# "Original Document Recorded on 5 9 2008 ... Instrument No.: ...". Often handwritten; a vision reading is what makes it legible.
_CERTIFICATION = re.compile(r"CERTIF(?:IED|Y)\b.{0,80}?\b(?:TRUE|EXACT|CORRECT)\b.{0,40}?\bCOPY\b|copy\s+of\s+the\s+original\s+docu\w*|"
                            r"Original\s+Document\s+Recorded", re.I)
_CERT_DATE = re.compile(r"RECORDED\s*(?:ON)?\s*:?\s*(\d{1,2})\s*[-/. ]\s*(\d{1,2})\s*[-/. ]\s*(\d{4}|\d{2})\b", re.I)
_CERT_DATE_WORDS = re.compile(r"RECORDED\s*(?:ON)?\s*:?\s*((?:January|February|March|April|May|June|July|August|September|October|"
                              r"November|December)\s+\d{1,2},?\s+\d{4})", re.I)
_CERT_BOOK = re.compile(r"\bBOOK\s*((?:\d[\s-]?){8})\s*,?\s*PAGE\s*(\d{1,4})\b", re.I)
_CERT_NUMBER = re.compile(r"(?:Instrument|Recording|Series|DEALER|Document)\s*(?:No\.?|Number|#)\s*:?\s*([\d][\d\s.$/-]{2,20}\d)", re.I)
_CERT_DASHED = re.compile(r"(?<!\d)((?:19|20)\d{2})\s?-\s?(\d{2})\s?-?\s?(\d{2})\s?-\s?(\d{1,4})(?!\d)")


@dataclass
class GrantDeedRecord:
    deed_type: str = "grant deed"          # or "trustee's deed upon sale", "quitclaim deed", "interspousal transfer deed"
    recording: Recording = field(default_factory=Recording)
    number: str = ""
    number_source: NumberSource | None = None   # the stamp, the title company's certification, or only the file name
    certification_differs: str = ""        # the title company's certification as read, when it disagrees with the file name
    corrects: str = ""                     # a re-recorded deed: what it corrects ("legal description")
    corrects_recorded: date | None = None  # and when the deed it corrects was recorded
    recorded: date | None = None
    requested_by: str = ""                 # "RECORDING REQUESTED BY": the title company, as printed
    apns: tuple[str, ...] = ()
    apn: str = ""
    unit: str = ""
    building: str = ""
    grantor: str = ""
    grantee: str = ""
    county_tax_cents: int | None = None
    city_tax_cents: int | None = None
    exempt: bool = False
    exemption: str = ""                    # the reason an exempt deed gives ("R&T 11911", "no consideration")
    consideration_cents: int | None = None
    dated: date | None = None
    declaration_cited: str = ""            # the CC&Rs the legal description makes the deed subject to
    plan_cited: str = ""                   # the condominium plan the unit is drawn on
    parent_parcel: bool = False
    common_area: bool = False
    sale_notice: bool = False              # the title company's "the following property has been sold" letter in the same file
    unpaid_debt_cents: int | None = None   # a trustee's deed: the debt the sale was for
    amount_paid_cents: int | None = None   # and what the buyer at the sale paid


def _repair(text: str) -> str:
    """Undo the scan slips that hide the granting clause and the CC&R citation: ``GRANT{S) ta`` and ``(book) 20070920,
    (page) 938``. Only those tokens change."""
    text = re.sub(r"G[,.]?RANT\s?[\{(\[]\s?[S$5]\s?[\)}\]]", "GRANT(S)", text)
    text = re.sub(r"\bH\W?reby(?=\s+GRANT)", "hereby", text)
    # "does hereby grant to" (no S) is the same clause; ``granting_clause`` wants the S.
    text = re.sub(r"(hereby\s+)(GRANT(?:\(S\)|S)?)\s+t[ao0]\b", lambda m: f"{m.group(1)}{m.group(2) if m.group(2)[-1] in 'Ss)' else m.group(2) + 'S'} to",
                  text, flags=re.I)
    text = re.sub(r"\b[6G]ook(?=\s+\d{8}\b)", "Book", text)   # "In 6ook 20070912"
    return re.sub(r"[\(\{]\s?(book|page)\s?[\)\}]", r"\1", text, flags=re.I)


def _cert_date(block: str) -> date | None:
    hit = _CERT_DATE.search(block)
    if hit:
        month, day, year = int(hit.group(1)), int(hit.group(2)), int(hit.group(3))
        try:
            return date(year + 2000 if year < 100 else year, month, day)
        except ValueError:
            return None
    hit = _CERT_DATE_WORDS.search(block)
    found = dates_in(hit.group(1)) if hit else []
    return found[0] if found else None


def _fits(page: str, legible: str) -> bool:
    """The name's page (``0856``) is what the certification's digits (``8576``, a vision slip) still show, in order."""
    page = page.lstrip("0")
    return bool(page) and _subsequence(page, legible)


def _subsequence(small: str, big: str) -> bool:
    it = iter(big)
    return all(ch in it for ch in small)


@dataclass(frozen=True)
class _Certified:
    number: str = ""
    source: NumberSource | None = None
    certified: bool = False
    differs: str = ""        # the certification's own reading, when it disagrees with the file name's number


def _certification(text: str, named: str) -> _Certified:
    """The number a title company's certification of the copy gives, and whether the copy is certified at all. The block
    prints the recording date and the book and page, the instrument number, or only the year and page (``2008-1337``);
    the date supplies the book. A file name's number that the block's date (or year) and legible digits agree with
    completes a block OCR or handwriting left partial. The block is often handwritten, and a vision reading misreads a
    handwritten day (``10/22/08`` for ``10/17/08``) as readily as a person mistypes a file name; when the two disagree the
    name's number stands and the certification's reading is kept for the finding."""
    flat = squash(text[:12000])
    certified = False
    for hit in _CERTIFICATION.finditer(flat):
        certified = True
        block = flat[hit.start(): hit.end() + 260]
        when = _cert_date(block)
        day = when.strftime("%Y%m%d") if when else ""
        full, legible = "", ""
        book, dashed, label = _CERT_BOOK.search(block), _CERT_DASHED.search(block), _CERT_NUMBER.search(block)
        if book:
            full, legible = re.sub(r"\D", "", book.group(1)) + book.group(2).zfill(4), book.group(2)
        elif dashed:
            full, legible = "".join(dashed.groups()[:3]) + dashed.group(4).zfill(4), dashed.group(4)
        elif label:
            digits = re.sub(r"\D", "", label.group(1))
            legible = digits
            if len(digits) == 12:
                full, legible = digits, digits[8:]
            elif day and digits.startswith(day) and len(digits) <= 12:   # "20100910/1231", or "NO. 20120327 IN BOOK PAGE 3215"
                page = digits[8:] or (re.search(r"\bPAGE\s*(\d{1,4})\b", block[label.end():], re.I) or [None, ""])[1]
                if page:
                    full, legible = day + page.zfill(4), page
            elif day and digits.startswith(day[:4]) and 1 <= len(digits) - 4 <= 4:   # "2008-1337": the year and the page
                full, legible = day + digits[4:].zfill(4), digits[4:]
        if full and (not number_date(full) or (day and full[:8] != day)):
            full = ""
        if named and full == named:
            return _Certified(named, NumberSource.CERTIFICATION, True)
        year_page = bool(named and not day and legible.startswith(named[:4]) and legible[4:].lstrip("0") == named[8:].lstrip("0"))
        if named and ((day and day == named[:8] and (not legible or _fits(named[8:], legible))) or year_page):
            return _Certified(named, NumberSource.CERTIFICATION_AND_NAME, True)
        reading = full or (f"{day} page {legible.lstrip('0')}" if day and legible else day)
        if named and reading:
            return _Certified(certified=True, differs=reading)
        if full:
            return _Certified(full, NumberSource.CERTIFICATION, True)
    return _Certified(certified=certified)


def layers(text: str) -> tuple[str, str]:
    """A text that opens with a vision reading of its first pages, split into that reading and the older text after it
    (which repeats those pages, OCR'd worse). The library marks the join with ``_VISION_END``. A text cached before the
    marker has none: the join is then where the old text repeats one of the reading's opening lines, or where its own
    ``# name`` header starts; when neither shows, the whole is the reading and the rest is empty. A text with no vision
    reading is all rest."""
    if not text.lstrip().startswith(_VISION_MARK):
        return "", text
    body = text.lstrip()[len(_VISION_MARK):].lstrip("\n")
    if _VISION_END in body:
        reading, _, rest = body.partition(_VISION_END)
        return reading.rstrip("\n") + "\n", rest.lstrip("\n")
    cuts = [m.start() + 2 for m in re.finditer(r"\n\n# [^\n]+\.\w{3,4}[ \t]*\n", body)]
    opening = [ln.strip() for ln in body.splitlines()[:10] if len(ln.strip()) >= 12][:3]
    for line in opening:
        start = body.find(line) + len(line)
        pattern = re.compile(r"\s+".join(re.escape(w) for w in line.split()), re.I)
        hit = pattern.search(body, max(start, 400))
        if hit:
            cuts.append(body.rfind("\n", 0, hit.start()) + 1)
    cut = min(cuts, default=0)
    return (body[:cut], body[cut:]) if cut else (body, "")


def copy_findings(rec: Recording, differs: str, name: str, *, authority: str = "") -> list[Finding]:
    """``recording_findings``, and where the number came from when it was not the county's stamp."""
    found = recording_findings(rec, name, authority=authority)
    if differs:
        found.append(Finding("certification-differs", f"the title company's certification reads {differs}; the file name gives "
                             f"{rec.number}: one is misread (the certification is often handwritten); check the county index",
                             Severity.CHECK))
    elif rec.number and rec.source == NumberSource.NAME.value:
        copy = ("a certified copy whose certification gives no number" if rec.certified_copy else
                "the blank recorder's box, a copy made before recording" if rec.unrecorded_copy else
                "a title company's copy, or a stamp OCR lost")
        found.append(Finding("number-from-name", f"no county stamp or title certification in the text ({copy}); the number and "
                             f"recording date are the file name's {rec.number}: confirm them in the county index", Severity.CHECK))
    return found


def copy_recording(text: str, name: str) -> tuple[Recording, str]:
    """The county's stamp (a vision reading of page 1, when there is one, comes first in the text and so wins); then the
    title company's certification; then the file name's number, marked as such. A title company's certified copy often
    carries no county stamp at all: the certification, or only the name, says where it was recorded. The second value
    is a certification's reading that disagrees with the name."""
    found = recording(re.sub(r"\bDoc\s+#\s*(?=\d)", "Doc# ", text.replace(_VISION_MARK, "", 1)), name)  # a vision reading prints "Doc # "
    if found.number:
        return found, ""
    named = name_number(name)
    cert = _certification(text, named)
    number, source = cert.number, cert.source
    if not number and named:
        number, source = named, NumberSource.NAME
    certified = cert.certified or found.certified_copy
    if not number:
        return replace(found, certified_copy=certified), cert.differs
    return replace(found, number=number, recorded=number_date(number), certified_copy=certified, source=source.value), cert.differs


def _city_consideration(county: int | None, city: int | None) -> int | None:
    """The consideration the city tax ($2.75 per $1,000, to the cent) computes, when the county tax (55 cents per $500 or
    fraction) rounds that same dollar up: ``$694.41`` is $252,513 and ``$278.30`` is 506 steps. ``deed_price`` compares the
    two at the county's whole step, which a price between steps misses."""
    if not county or not city or county % _COUNTY_STEP_CENTS:
        return None
    for dollars in sorted(range(city * 40 // 11 - 2, city * 40 // 11 + 3), key=lambda d: abs(d * 11 - city * 40)):
        if round(dollars * 11 / 40) == city and -(-dollars // 500) * _COUNTY_STEP_CENTS == county:
            return dollars * 100
    return None


def _county_from_city(city: int | None) -> int | None:
    """The county tax the city tax implies: its consideration rounded up to the next $500 step."""
    if not city:
        return None
    return -(-(city * 40 // 11) // 500) * _COUNTY_STEP_CENTS


def _deed_date(flat: str) -> date | None:
    """The deed's own date: "Dated: May 1, 2019", "Dated: 10/25/07", "Dated: January 21st 2008", or the continuation page's
    header ("Grant Deed - continued Date: 01/05/2012"). A trust's "Dated 17 January 2006" in a vesting is not it (no colon
    form, day first)."""
    for hit in _DATED.finditer(flat):
        words = re.sub(r"(\d)(?:st|nd|rd|th)\b", r"\1", hit.group(1))
        words = re.sub(r"^(\w+\s+\d{1,2})\s+(\d{4})$", r"\1, \2", words)
        numeric = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2}|\d{4})", words)
        if numeric:
            month, day, year = (int(g) for g in numeric.groups())
            try:
                return date(year + 2000 if year < 100 else year, month, day)
            except ValueError:
                continue
        found = dates_in(words)
        if found:
            return found[0]
    return None


def _names(context: str) -> str:
    """Which instrument the words just before a citation name: ``plan`` or ``declaration`` (the later mention wins)."""
    tail = context[-120:]
    plan = max((m.end() for m in re.finditer(r"Condominium\s+Plan|\bPlan\b", tail, re.I)), default=-1)
    decl = max((m.end() for m in re.finditer(r"Declaration|Covenants|CC&R", tail, re.I)), default=-1)
    return "" if plan == decl == -1 else ("declaration" if decl > plan else "plan")


def _plan_by_date(flat: str) -> str:
    """The plan's number when OCR broke it but the recording date before it reads: the digits that follow, stripped of the
    slips, are the number only when they begin with that date."""
    hit = _PLAN_DATED.search(flat)
    if not hit:
        return ""
    found = dates_in(re.sub(r"[^\w,]+", " ", hit.group(1)))
    digits = re.sub(r"\D", "", hit.group(2).translate(_DIGIT_SLIPS))
    return digits[:12] if found and len(digits) == 12 and digits.startswith(found[0].strftime("%Y%m%d")) else ""


def _apns(text: str) -> tuple[str, ...]:
    """``apn_fields`` reads the labeled number; an "APN#" label, or a bare book-page-parcel number, is the fallback. A
    developer's deed of many units lists ranges (``201-1170-022-0001 through 201-1170-022-0008``), which are expanded
    within one assessor's parcel; OCR's ``I`` for 1 and a lost hyphen are repaired inside the numbers only."""
    labeled = tuple(f.value for f in apn_fields(text))
    if labeled:
        return labeled
    # The head, and the list after each "APN:" label wherever it falls (a legal description's exhibit ends with one).
    head = "\n".join([text[:12000]] + [text[12000 + m.end(): 12000 + m.end() + 1500]
                                       for m in re.finditer(r"\bAPN'?S?\s*:", text[12000:], re.I)])
    head = re.sub(r"(?<=\d)\s?[�·]\s?(?=\d)", "-", head)
    head = re.sub(r"(?<=\d)\s?[Il|](?=[\s;,.-]|\d)", "1", head)
    found: list[str] = []
    for m in _BARE_APN.finditer(head):
        found.append("-".join(m.groups()))
        tail = _APN_THROUGH.match(head, m.end())
        if tail and tail.groups()[:3] == m.groups()[:3] and 0 < int(tail.group(4)) - int(m.group(4)) <= _MAX_RANGE:
            found += [f"{'-'.join(m.groups()[:3])}-{n:04d}" for n in range(int(m.group(4)) + 1, int(tail.group(4)))]
    return tuple(dict.fromkeys(found))


def _reading(text: str) -> Reading:
    return Reading("deed", (Page(1, text, "text"),), "text")


_DEED_TYPES = (
    ("trustee's deed upon sale", re.compile(r"TRUSTEE.?S\s+DEED(?:\s+UPON\s+SALE)?", re.I)),
    ("quitclaim deed", re.compile(r"QUIT\s?CLAIM\s+DEED", re.I)),
    ("interspousal transfer deed", re.compile(r"INTERSPOUSAL\s+TRANSFER", re.I)),
    ("grant deed", re.compile(r"\bGRANT\s+D[E3][E3]D\b", re.I)),
)
_PARTY_TAIL = re.compile(r"\s+(?:the\s+(?:following|real|land)\b|SEE\s+EXHIBIT|described\s+as\b|in\s+the\s+City\s+of\b|all\s+that\s+real\b).*$",
                         re.I)
_PLAN_NUMBER =re.compile(r"Condominium\s+Plan.{0,250}?(?:Document\s+No\.?\s*(\d{12})|Book\s+(\d{8}),?\s+(?:at\s+)?Page\s+(\d{1,4}))", re.I)
# "subject to the covenants, conditions and restrictions ... recorded September 20, 2007 as instrument number 20070920, page 938"
_CCRS_BOOK = re.compile(r"(?:Covenants|Declaration|Restrictions|CC&Rs?)\b.{0,200}?\b(?:Book|instrument\s+(?:number|No\.?))\s+(\d{8}),?\s+"
                        r"(?:at\s+)?Page\s+(\d{1,4})\b", re.I)
_DATED = re.compile(r"(?:\bDated:?|\bcontinued\s+Date:)\s*((?:January|February|March|April|May|June|July|August|September|October|"
                    r"November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-](?:\d{4}|\d{2})\b)", re.I)
_PLAN_DATED = re.compile(r"Condominium\s+Plan\b.{0,140}?\b((?:January|February|March|April|May|June|July|August|September|"
                         r"October|November|December)\W{1,3}\d{1,2}\W{0,3}\d{4})\W{0,3}as\W{0,3}Doc\S{0,10}\s*N\S{0,4}\s*(.{0,30}?)"
                         r"\s*(?:of\W{0,3}Off|\()", re.I)
_DIGIT_SLIPS = str.maketrans("OoQDlIi|!tLbSsBZz", "00001111111655822")   # what OCR prints for a digit
_APN_THROUGH = re.compile(r"\s+THROUGH\s+(\d{3})\s?-\s?(\d{4})\s?-\s?(\d{3})\s?-\s?(\d{4})(?![\d-])", re.I)
_MAX_RANGE = 60   # subparcels in one range: a building's units, not a runaway match
_LABELED_GRANT = re.compile(r"acknowledged,?\s+(.{3,500}?)\s*\(\W{0,3}Gra\w{2,4}or\W{0,3}\),?\s+(?:does\s+)?hereby\s+GRANTS?\s+to\s+"
                            r"(.{3,250}?)\s*\(\W{0,3}Grantee", re.I)
_RERECORDED = re.compile(r"re-?\s?recorded\s+to\s+correct\s+(?:the\s+)?(.{3,60}?)\s+of\s+the\s+(?:Grant\s+)?Deed\s+recorded\s+"
                         r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})",
                         re.I)
_BARE_APN =re.compile(r"(?<![\d-])(\d{3})\s?-\s?(\d{4})\s?-\s?(\d{3})\s?-\s?(\d{4})(?![\d-])")
_TRUSTEE_GRANT =re.compile(r"(?:^|\n)\s*([A-Z][^\n]{2,80}?),?\s+as\s+the\s+duly\s+appointed\s+Trustee.{0,400}?hereby\s+grant\s+without\s+"
                            r"covenant\s+or\s+warranty\s+to:?\s+(.{3,120}?)\s+herein\s+called\s+Grantee", re.I | re.S)


class GrantDeedModel(DocumentModel):
    kind = DocumentKind.GRANT_DEED
    name = "grant-deed"
    required = ("number", "recorded", "apn", "grantor", "grantee")

    def parse(self, text: str, context: ModelContext) -> GrantDeedRecord | None:
        text = _repair(text)
        trustee = _TRUSTEE_GRANT.search(text[:8000])
        if not GrantDeedMixin().detect(_reading(text)) and not trustee:
            return None
        flat = squash(text)
        r = GrantDeedRecord()
        r.deed_type = next((name for name, pattern in _DEED_TYPES if pattern.search(flat[:5000])), "grant deed")
        r.recording, r.certification_differs = copy_recording(text, context.name)
        r.number, r.recorded = r.recording.number, r.recording.recorded
        r.number_source = next((s for s in NumberSource if s.value == r.recording.source), None) if r.number else None
        hit = re.search(r"RECORDING\s+REQUESTED\s+BY:?\s+(.{3,60}?(?:Title|Escrow)(?:\s+(?:Insurance\s+)?(?:Company|Co\.|Inc\.?|Corporation))?)\b",
                        flat, re.I)
        r.requested_by = " ".join(hit.group(1).split()) if hit else ""
        r.requested_by = re.sub(r"^\W+", "", r.requested_by)
        # A vision reading of page 1 comes first; the older text repeats that page, often with the numbers garbled, so a
        # field the reading carries is taken from it alone and the rest is only a fallback.
        vision, rest = layers(text)
        r.apns = _apns(vision) or _apns(rest)
        r.apn = r.apns[0] if r.apns else ""
        units = unit_fields(vision) or unit_fields(rest)
        with_building = [i for i, f in enumerate(units) if f.name == "building"]
        if with_building:
            r.unit, r.building = units[with_building[0] - 1].value, units[with_building[0]].value
        elif units:
            r.unit = units[0].value
        labeled = _LABELED_GRANT.search(flat[:20000])
        if labeled:  # a receiver's or trustee's deed defines the parties: ... ("Grantor"), does hereby grant to ... ("Grantee")
            r.grantor = re.split(r"\s+IN\s+THE\s+MATTER\s+OF\b", labeled.group(1), maxsplit=1, flags=re.I)[0].strip(" ,.;")
            r.grantee = labeled.group(2).strip(" ,.;")
        else:
            r.grantor, r.grantee = (_PARTY_TAIL.sub("", p).strip(" ,.;:") for p in granting_clause(text))
            # "receipt af which Is hereby adcnawledged": the split on "acknowledged" missed, and the form's boxes came along.
            r.grantor = re.split(r"\b\w{2,6}ledged\b,?\s*", r.grantor, flags=re.I)[-1].strip(" ,.;·")
        if trustee and not r.grantee:
            r.grantor, r.grantee = " ".join(trustee.group(1).split()), " ".join(trustee.group(2).split())
        if r.deed_type == "trustee's deed upon sale":
            r.unpaid_debt_cents = amount_after(r"amount\s+of\s+the\s+unpaid\s+debt\s+was", flat)
            r.amount_paid_cents = amount_after(r"amount\s+paid\s+by\s+the\s+Grantee\s+was", flat)
        # ``deed_price`` takes the last city tax it sees, which on a doubled text is the older layer's slip.
        price = next((p for p in (deed_price(vision), deed_price(rest)) if p is not None and (p.county_tax_cents is not None or p.exempt)),
                     None) or deed_price(text)
        if price is not None:
            r.county_tax_cents, r.city_tax_cents, r.exempt, r.consideration_cents = (price.county_tax_cents, price.city_tax_cents,
                                                                                     price.exempt, price.price_cents)
        if r.county_tax_cents == _STATUTE_AS_TAX_CENTS:  # "R&T 11911" written in the blank, read as $119.11
            r.county_tax_cents, r.exempt, r.consideration_cents = None, True, None
        if r.consideration_cents is None and not r.exempt:
            r.consideration_cents = _city_consideration(r.county_tax_cents, r.city_tax_cents)
        if r.exempt:
            hit = re.search(r"(?:R\s?&\s?T|Revenue\s+and\s+Taxation\s+Code)\s*(?:Section\s*)?(\d{4,5}(?:\.\d)?)", flat, re.I)
            r.exemption = f"R&T {hit.group(1)}" if hit else ("no consideration" if re.search(r"no\s+consideration|gift", flat, re.I) else "")
        r.dated = _deed_date(flat)
        cited = citations(text, own=r.number)
        # The words nearest before a number say what it is: the plan's own number lost to OCR leaves the CC&Rs' citation
        # right after '("Plan"), and in the Restated Declaration', which is the declaration's, not the plan's.
        decl = [c.number for c in cited if _names(c.context) == "declaration"]
        plan = [c.number for c in cited if c.number not in decl and (c.relation is Relation.PLAN or re.search(r"\bPlan\b", c.title, re.I))]
        hit = _CCRS_BOOK.search(flat)
        r.declaration_cited = decl[0] if decl else (f"{hit.group(1)}{int(hit.group(2)):04d}" if hit else "")
        r.plan_cited = plan[0] if plan else ""
        if not r.plan_cited:  # the date before the number did not survive OCR ("Janubry i 6, 2019")
            hit = _PLAN_NUMBER.search(flat)
            if hit:
                r.plan_cited = hit.group(1) or f"{hit.group(2)}{int(hit.group(3)):04d}"
                r.plan_cited = "" if r.plan_cited == r.declaration_cited else r.plan_cited   # the plan's own number did not read
        if not r.plan_cited:  # "RECORDED JANUARY 16, 2019, AS_QQCUMENIJI.JP, 201-90--1161002": the date vouches for the digits
            r.plan_cited = _plan_by_date(flat)
        hit = _RERECORDED.search(flat[:8000])
        if hit:
            r.corrects = " ".join(hit.group(1).split()).lower()
            r.corrects_recorded = (dates_in(hit.group(2)) or [None])[0]
        r.parent_parcel = any(parent_parcel(a) for a in r.apns)
        r.common_area = bool(re.search(r"Association\s+Common\s+Area|A\.C\.A\.\s*\d", flat[:6000], re.I)) and not r.unit
        r.sale_notice = bool(re.search(r"has\s+been\s+sold\.?\s+Please\s+update|escrow\s+was\s+closed\s+on", flat, re.I))
        return r

    def check(self, r: GrantDeedRecord, context: ModelContext) -> list[Finding]:
        found = copy_findings(r.recording, r.certification_differs, context.name)
        if r.recorded and r.dated and r.recorded < r.dated:
            found.append(Finding("recorded-before-dated", f"recorded {r.recorded.isoformat()} before the deed's date "
                                 f"{r.dated.isoformat()}: one of the two is misread, or the deed misprints its year", Severity.CHECK))
        parcels = spec_parcels(context.community)
        pages = {p[:7] for p in parcels}
        earlier: list[str] = []
        for apn in r.apns:
            digits = re.sub(r"\D", "", apn)
            if parent_parcel(apn):
                found.append(Finding("parent-parcel", f"{apn} is a parent parcel (subparcel 0000): it names the land before the assessor "
                                     "split the building, not a unit", Severity.INFO))
            elif not parcels or digits in parcels:
                continue
            elif digits[:7] in pages:
                earlier.append(apn)
            else:
                found.append(Finding("apn-off-the-map-page", f"{apn} is not on the association's assessor map page (an OCR slip, or a "
                                     "parcel outside the association)", Severity.CHECK))
        if earlier:
            found.append(Finding("earlier-parcel-numbers", f"{len(earlier)} parcel number(s) on the association's map page that the current "
                                 f"roll no longer carries ({', '.join(earlier[:3])}{'...' if len(earlier) > 3 else ''}): an earlier "
                                 "subdivision of the building", Severity.INFO))
        blocks = spec_unit_blocks(context.community)
        if r.unit.isdigit() and len(r.apns) == 1 and not r.parent_parcel and blocks:  # one unit: a bulk deed's unit blank is one of many
            candidates = {number for _block, number in unit_parcels(int(r.unit), blocks)}
            if candidates and re.sub(r"\D", "", r.apn) not in candidates:
                found.append(Finding("unit-apn-mismatch", f"unit {r.unit} and {r.apn} fit none of the specification's unit numberings",
                                     Severity.CHECK))
        if r.county_tax_cents and r.county_tax_cents % _COUNTY_STEP_CENTS:
            implied = _county_from_city(r.city_tax_cents)
            hint = f"; the city tax ${r.city_tax_cents / 100:,.2f} computes ${implied / 100:,.2f}" if implied else ""
            found.append(Finding("county-tax-not-a-step", f"the county tax ${r.county_tax_cents / 100:,.2f} is not a multiple of $0.55 per "
                                 f"$500 (an OCR slip or a partial-interest deed){hint}", Severity.CHECK, "R&T 11911"))
        elif r.county_tax_cents and r.city_tax_cents and r.consideration_cents is None:
            found.append(Finding("transfer-taxes-disagree", f"the county tax ${r.county_tax_cents / 100:,.2f} and the city tax "
                                 f"${r.city_tax_cents / 100:,.2f} do not compute the same consideration", Severity.CHECK))
        if r.corrects:
            when = f" recorded {r.corrects_recorded.isoformat()}" if r.corrects_recorded else ""
            found.append(Finding("re-recorded", f"re-records the deed{when} to correct its {r.corrects}; both recordings stay of record, "
                                 "and the chain cites the corrected one", Severity.INFO))
        if r.sale_notice:
            found.append(Finding("sale-notice-attached", "the file also carries the title company's sale notice to the association (the "
                                 "new owner's mailing address belongs in the membership list)", Severity.INFO))
        return found


register(GrantDeedModel())

__all__ = ["GrantDeedRecord", "GrantDeedModel", "NumberSource", "copy_recording", "copy_findings", "layers"]
