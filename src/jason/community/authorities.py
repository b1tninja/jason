"""The legal authorities Jason's duties, records, and processes rest on, and where their words come from.

A duty cites sections. A lien process cites a code. The developer file
cites the Subdivided Lands Act and the Commissioner's regulations. This
module turns those citations into ``Authority`` spans lawlibrary exports
from the current session publication, so the words of the law sit in the
catalog as their own shelf, apart from the pages Jason writes about them.
A citation lawlibrary cannot serve (a regulation in Title 10, a federal
statute, a DRE manual) stays on the list as a pointer with the official
source that holds it. A page Jason wrote is never an authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from jason.community.duties import DUTIES

# The codes lawlibrary's California shelf holds, by the abbreviation the Legislature prints.
LAWLIBRARY_CODES = frozenset({
    "BPC", "CCP", "CIV", "COM", "CONS", "CORP", "EDC", "ELEC", "EVID", "FAC", "FAM", "FGC", "FIN", "GOV", "HNC", "HSC",
    "INS", "LAB", "MVC", "PCC", "PEN", "PRC", "PROB", "PUC", "RTC", "SHC", "UIC", "VEH", "WAT", "WIC",
})
LEGINFO_SECTION = "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode={code}&sectionNum={section}."
# Title 10 as the Department of Real Estate publishes it; the Office of Administrative Law's host is govt.westlaw.com/calregs.
CCR_SOURCE = "https://www.dre.ca.gov/files/pdf/relaw/regs.pdf"


class Shelf(Enum):
    STATUTE = "a California statute in the lawlibrary publication"
    ACT = "a named act lawlibrary outlines, exported by article"
    REGULATION = "a California regulation; the Office of Administrative Law posts Title 10"
    FEDERAL = "a federal statute; not on the California shelf"
    PUBLICATION = "an agency publication, fetched from the agency"


class Basis(Enum):
    DUTY = "a duty"
    RECORD = "the records article"
    PROCESS = "a recorded-instrument process"
    SOLAR = "the solar program"
    DEVELOPER = "the developer file"
    GOVERNANCE = "the corporation"
    CONTRACTS = "vendor contracts"


@dataclass(frozen=True)
class Authority:
    """One span of law Jason relies on. ``start == end`` is a single section."""

    code: str
    start: str
    end: str
    why: str
    basis: Basis
    shelf: Shelf = Shelf.STATUTE
    source: str = ""
    title: str = ""

    @property
    def citation(self) -> str:
        if self.start == self.end:
            return f"{self.code} {self.start}"
        return f"{self.code} {self.start}-{self.end}"

    @property
    def slug(self) -> str:
        return re.sub(r"[^A-Za-z0-9.]+", "-", self.citation).strip("-")

    @property
    def exportable(self) -> bool:
        return self.shelf in (Shelf.STATUTE, Shelf.ACT) and self.code in LAWLIBRARY_CODES

    @property
    def official(self) -> str:
        if self.source:
            return self.source
        if self.code in LAWLIBRARY_CODES:
            return LEGINFO_SECTION.format(code=self.code, section=self.start)
        return ""


@dataclass(frozen=True)
class Publication:
    """An agency document Jason treats as authority but must fetch as a file."""

    title: str
    url: str
    why: str
    agency: str = "California Department of Real Estate"
    number: str = ""

    @property
    def filename(self) -> str:
        tail = self.url.rsplit("/", 1)[-1] or "publication.pdf"
        return tail if tail.lower().endswith(".pdf") else tail + ".pdf"


_GROUP = re.compile(r"^\s*(?P<code>Title\s+\d+\s+sections?|[A-Z]{2,5})\s+(?P<rest>.+)$")
_SPAN = re.compile(r"^(?P<start>\d+(?:\.\d+)*)\s*(?:to|-|–)\s*(?P<end>\d+(?:\.\d+)*)$")
_ONE = re.compile(r"^(?P<one>\d+(?:\.\d+)*)$")


def parse_statutes(text: str, why: str, basis: Basis) -> tuple[Authority, ...]:
    """Read a duty's citation string ("CIV 4150, 4205, 4250 to 4275; BPC 11504") into spans.

    Groups are separated by semicolons and start with a code. "Title 10
    sections" is the Commissioner's regulations, a pointer rather than an
    export. An unreadable group is skipped rather than guessed.
    """
    found: list[Authority] = []
    for group in text.split(";"):
        match = _GROUP.match(group.strip())
        if not match:
            continue
        code = match.group("code")
        shelf, source = Shelf.STATUTE, ""
        if code.lower().startswith("title"):
            code = f"{code.split()[1]} CCR"
            shelf, source = Shelf.REGULATION, CCR_SOURCE
        for piece in match.group("rest").split(","):
            piece = piece.strip().rstrip(".")
            span = _SPAN.match(piece)
            one = _ONE.match(piece)
            if span:
                found.append(Authority(code, span.group("start"), span.group("end"), why, basis, shelf, source))
            elif one:
                found.append(Authority(code, one.group("one"), one.group("one"), why, basis, shelf, source))
    return tuple(found)


def duty_authorities() -> tuple[Authority, ...]:
    """Every span the duty registry cites, in registry order."""
    found: list[Authority] = []
    for duty in DUTIES:
        found.extend(parse_statutes(duty.sections, f"{duty.anchor}: {duty.keeps_straight}", Basis.DUTY))
    return tuple(found)


# Spans the recorded-instrument processes and the developer file rest on. PROCESS_NOTES says the same in prose.
PROCESS_AUTHORITIES: tuple[Authority, ...] = (
    Authority("CIV", "5650", "5740", "assessment collection: the pre-lien notice, the lien, its release, and foreclosure", Basis.PROCESS),
    Authority("CIV", "2924", "2924.26", "a deed of trust in default: notice of default, notice of sale, and the trustee's sale", Basis.PROCESS),
    Authority("CIV", "2941", "2941", "reconveyance when the loan is paid", Basis.PROCESS),
    Authority("CIV", "8400", "8494", "mechanic's lien: recording deadlines, the ninety-day enforcement window, release, and the release bond", Basis.PROCESS),
    Authority("CCP", "697.310", "697.410", "an abstract of judgment as a lien on real property, and its release", Basis.PROCESS),
    Authority("FAM", "4506", "4506", "a support judgment as a lien on the obligor's real property", Basis.PROCESS),
    Authority("GOV", "7170", "7174", "state tax lien recorded with the county", Basis.PROCESS),
    Authority("RTC", "2191.3", "2191.6", "the tax collector's certificate of lien for unsecured taxes", Basis.PROCESS),
    Authority("RTC", "3691", "3691", "the tax collector's power to sell tax-defaulted property", Basis.PROCESS),
    Authority("SHC", "5898.12", "5898.32", "PACE assessment contracts that run with the land", Basis.PROCESS),
    Authority("GOV", "53328.3", "53328.3", "a community facilities district's notice of special tax lien", Basis.PROCESS),
    Authority("COM", "9334", "9334", "priority of a security interest in fixtures", Basis.PROCESS),
    Authority("COM", "9502", "9502", "what a fixture filing contains", Basis.PROCESS),
    Authority("COM", "9513", "9515", "termination and continuation of a financing statement", Basis.PROCESS),
    Authority("HSC", "17985", "17985", "a recorded notice of substandard building", Basis.PROCESS),
    Authority("26 USC", "6321", "6325", "the federal tax lien and its release certificate", Basis.PROCESS, Shelf.FEDERAL,
              "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section6321"),
    Authority("PUC", "2869", "2869", "the recorded notice of a solar energy system contract", Basis.SOLAR),
    Authority("CIV", "714", "714.1", "solar energy systems and what an association may restrict", Basis.SOLAR),
    Authority("CIV", "4746", "4746", "solar on a common-area roof in a common interest development", Basis.SOLAR),
    Authority("BPC", "11000", "11023", "the Subdivided Lands Act: the public report and what the subdivider delivers", Basis.DEVELOPER),
    Authority("CORP", "7210", "7215", "the board of a nonprofit mutual benefit corporation", Basis.GOVERNANCE),
    Authority("BPC", "7026", "7031", "contractor licensing: who needs a license, the license number a contract prints (7030.5), and an unlicensed contractor's pay", Basis.CONTRACTS),
    Authority("BPC", "7151", "7159.14", "home improvement contracts: the required terms, the down payment limit, and payment ahead of the work (7159.5)", Basis.CONTRACTS),
    Authority("CORP", "8310", "8340", "corporate records and their inspection", Basis.RECORD),
)

# Named acts lawlibrary outlines; each is exported one page per article so a passage stays with its heading.
@dataclass(frozen=True)
class Act:
    name: str
    code: str
    why: str
    basis: Basis


ACTS: tuple[Act, ...] = (
    Act("davis-stirling", "CIV", "the Davis-Stirling Common Interest Development Act, Civil Code 4000 to 6150", Basis.DUTY),
)

# Agency publications Jason treats as authority. They are fetched as files, never rewritten.
DRE_PUBLICATIONS: tuple[Publication, ...] = (
    Publication("Reserve Study Guidelines for Homeowner Association Budgets", "https://www.dre.ca.gov/files/pdf/re25.pdf",
                "how the Commissioner expects a reserve study and budget to be built", number="RE 25"),
    Publication("Common Interest Development brochure", "https://www.dre.ca.gov/files/pdf/re39.pdf",
                "the Department's description of a CID, its association, and a buyer's obligations", number="RE 39"),
    Publication("Regulations of the Real Estate Commissioner", CCR_SOURCE,
                "Title 10 of the California Code of Regulations, including the 2792 sections on subdivision governing documents and deliveries"),
    Publication("Real Estate Law and Subdivided Lands Law", "https://www.dre.ca.gov/files/pdf/relaw/relaw.pdf",
                "Business and Professions Code 10000 to 11288 as the Department publishes them, including the public report sections"),
)


def authorities() -> tuple[Authority, ...]:
    """The duty spans, then the process spans, with exact duplicates dropped."""
    seen: set[tuple[str, str, str]] = set()
    found: list[Authority] = []
    for item in (*duty_authorities(), *PROCESS_AUTHORITIES):
        key = (item.code, item.start, item.end)
        if key in seen:
            continue
        seen.add(key)
        found.append(item)
    return tuple(found)


def pointers() -> tuple[Authority, ...]:
    """The authorities lawlibrary cannot export: regulations and federal law, each with its official source."""
    return tuple(item for item in authorities() if not item.exportable)


def number_key(value: str) -> tuple[float, ...]:
    """A dotted section number as a comparable tuple; a non-number sorts first."""
    try:
        return tuple(float(part) for part in str(value).split("."))
    except ValueError:
        return (-1.0,)


def section_in(authority: Authority, number: str) -> bool:
    """Whether a section number falls inside the span."""
    key = number_key(number)
    return key != (-1.0,) and number_key(authority.start) <= key <= number_key(authority.end)
