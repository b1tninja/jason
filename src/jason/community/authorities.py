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
from jason.community.references import SECTION_NUMBER

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
    INTERPRETATION = "reading the law and the documents"
    LIFE_SAFETY = "fire and life safety systems"


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


class PublicationText(Enum):
    """What an agency publication's own text is, which decides how its text is searched."""

    REGULATION = "the adopted text of a regulation, or the forms it incorporates: searched as the law"
    GUIDANCE = "an agency's guidance: searched as reference, never quoted as the law"
    COMPILATION = "a compilation whose sections are exported as their own pages: not searched whole"


@dataclass(frozen=True)
class Publication:
    """An agency document Jason treats as authority but must fetch as a file."""

    title: str
    url: str
    why: str
    agency: str = "California Department of Real Estate"
    number: str = ""
    text: PublicationText = PublicationText.COMPILATION

    @property
    def text_filename(self) -> str:
        """The file its text is kept in, beside the PDF."""
        return self.filename[:-4] + ".txt"

    @property
    def filename(self) -> str:
        tail = self.url.rsplit("/", 1)[-1] or "publication.pdf"
        return tail if tail.lower().endswith(".pdf") else tail + ".pdf"


_GROUP = re.compile(r"^\s*(?P<code>Title\s+\d+\s+sections?|[A-Z]{2,5})\s+(?P<rest>.+)$")
_SPAN = re.compile(rf"^(?P<start>{SECTION_NUMBER})\s*(?:to|-|–)\s*(?P<end>{SECTION_NUMBER})$")
_ONE = re.compile(rf"^(?P<one>{SECTION_NUMBER})$")


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
    Authority("BPC", "11200", "11200", "the Subdivided Lands Act's sales contract: the legal description, the encumbrances, and the terms", Basis.DEVELOPER),
    Authority("BPC", "10081", "10081", "the Commissioner's action to enjoin a violation of the Real Estate Law or the Subdivided Lands Act", Basis.DEVELOPER),
    # The Subdivision Map Act, Gov. Code 66410-66499.58, by chapter: the local approval that comes before the public report.
    # One span over the whole Act stops at 66498.9 in lawlibrary's worker, and a chapter is a page a reader can hold.
    Authority("GOV", "66410", "66424.6", "the Subdivision Map Act, general provisions and definitions: what a subdivision is (66424) and what the Act covers", Basis.DEVELOPER),
    Authority("GOV", "66425", "66450", "the Subdivision Map Act, maps: when a tentative and final map or a parcel map is required (66426, 66428), condominium plans (66427)", Basis.DEVELOPER),
    Authority("GOV", "66451", "66472.1", "the Subdivision Map Act, procedure: the tentative map, review by other agencies, the final map, filing with the county recorder, and amending a map", Basis.DEVELOPER),
    Authority("GOV", "66473", "66498", "the Subdivision Map Act, requirements: grounds for denial, dedications, fees, soils reports, and monuments", Basis.DEVELOPER),
    Authority("GOV", "66498.1", "66498.9", "the Subdivision Map Act, development rights: how long an approved map's rights last", Basis.DEVELOPER),
    Authority("GOV", "66499", "66499.58", "the Subdivision Map Act, improvement security (66499), reversions, the ban on selling before a map (66499.30), and judicial review", Basis.DEVELOPER),
    Authority("CIV", "783", "783", "a condominium is an estate in real property, which the Map Act and the Subdivided Lands Act both rely on", Basis.DEVELOPER),
    Authority("CIV", "885.010", "885.060", "a condition in a grant of real property: why a declaration's \"conditions\" are read as covenants", Basis.DEVELOPER),
    Authority("CIV", "895", "945.5", "the Right to Repair Act: a builder's standards, warranty periods, and the claim process for new homes", Basis.DEVELOPER),
    Authority("CCP", "726", "726", "the one-action rule for a foreclosure and a deficiency, which an assessment lien is not bound by (CIV 5700)", Basis.DEVELOPER),
    Authority("CORP", "7210", "7215", "the board of a nonprofit mutual benefit corporation", Basis.GOVERNANCE),
    Authority("BPC", "7026", "7031", "contractor licensing: who needs a license, the license number a contract prints (7030.5), and an unlicensed contractor's pay", Basis.CONTRACTS),
    Authority("BPC", "7151", "7159.14", "home improvement contracts: the required terms, the down payment limit, and payment ahead of the work (7159.5)", Basis.CONTRACTS),
    Authority("HSC", "13195", "13199", "automatic fire extinguishing systems: the State Fire Marshal's inspection, testing, and maintenance "
              "regulations (13195) and who must be licensed to test and maintain them (13196.5), behind Title 19, Chapter 5",
              Basis.LIFE_SAFETY),
    Authority("CIV", "1549", "1633", "what a contract is and how one is made: the parties, consent, a lawful object, and "
              "consideration (1550), and when a contract must be in writing (1624)", Basis.CONTRACTS),
    Authority("CIV", "1667", "1670.5", "contracts the law will not enforce: exempting a party from its own fraud or willful "
              "injury (1668), and an unconscionable clause (1670.5)", Basis.CONTRACTS),
    Authority("CIV", "1671", "1671", "liquidated damages: when a sum the parties fixed in advance is enforceable", Basis.CONTRACTS),
    Authority("CIV", "1717", "1717", "a contract's attorney fee clause runs both ways, to whichever party prevails", Basis.CONTRACTS),
    Authority("CCP", "337", "337", "four years to sue on a written contract", Basis.CONTRACTS),
    Authority("CCP", "1281", "1281.2", "an agreement to arbitrate is enforced, and when a court orders arbitration", Basis.CONTRACTS),
    Authority("CORP", "8310", "8340", "corporate records and their inspection", Basis.RECORD),
    Authority("CCP", "1858", "1866", "construing a statute or instrument: give effect to all its provisions (1858), the "
              "intention pursued and the particular over the general (1859)", Basis.INTERPRETATION),
    Authority("CIV", "1635", "1661", "interpreting contracts, and so the CC&Rs: the whole read together to give effect to "
              "every part (1641), a reading that makes it lawful and operative (1643)", Basis.INTERPRETATION),
    Authority("CIV", "3509", "3548", "the maxims of jurisprudence, aids to just application (3509): an interpretation "
              "that gives effect is preferred to one that makes void (3541)", Basis.INTERPRETATION),
    Authority("GOV", "27293", "27293", "an instrument in a language other than English is not accepted for record without "
              "a certified English translation: a recorded instrument's words are English", Basis.INTERPRETATION),
    # Civil Code 5350(a) applies 7233 and 7234 to any contract or other transaction the board or a committee authorizes,
    # approves, or ratifies, incorporated or not; the meeting room's recusal rule (BoardRule.interested_in_quorum) cites them.
    Authority("CORP", "7230", "7238", "the directors' standards of conduct: the standard of care (7231), a transaction with an "
              "interested director (7233(a)) or a common director (7233(b)) and counting either toward a quorum (7234), which "
              "Civil Code 5350(a) applies to the association, loans to a director or officer (7235), directors' liability for "
              "approving an unlawful distribution (7236), and indemnifying an agent (7237)", Basis.GOVERNANCE),
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
                "how the Commissioner expects a reserve study and budget to be built", number="RE 25",
                text=PublicationText.GUIDANCE),
    Publication("Common Interest Development brochure", "https://www.dre.ca.gov/files/pdf/re39.pdf",
                "the Department's description of a CID, its association, and a buyer's obligations", number="RE 39",
                text=PublicationText.GUIDANCE),
    Publication("Regulations of the Real Estate Commissioner", CCR_SOURCE,
                "Title 10 of the California Code of Regulations, including the 2792 sections on subdivision governing documents and deliveries"),
    Publication("Real Estate Law and Subdivided Lands Law", "https://www.dre.ca.gov/files/pdf/relaw/relaw.pdf",
                "Business and Professions Code 10000 to 11288 as the Department publishes them, including the public report sections"),
)

# The State Fire Marshal's adopted text of Title 19, Chapter 5 (operative August 28, 2014; Cornell LII prints the same
# 904, 904.1, and 904.2 in force on October 4, 2026), which adopts NFPA 25 (2011 edition) as the 2013 California
# Edition with its amendments, and the forms that regulation incorporates. The NFPA standards themselves are not
# freely published and are not on the shelf.
SFM = "California State Fire Marshal"
SFM_PUBLICATIONS: tuple[Publication, ...] = (
    Publication("Title 19, Chapter 5 and NFPA 25 California amendments, final text (2014)",
                "https://34c031f8-c9fd-4018-8c5a-4159cdff6b0d-cdn-endpoint.azureedge.net/-/media/osfm-website/what-we-do/"
                "code-development-and-analysis/title-19-development/finaltextofregs-nfpa25-2011_8-27-2014corrected_resubfinal.pdf",
                "who may inspect, test, and maintain water-based fire protection systems (19 CCR 904.1, 904.2), the frequencies "
                "as California amended NFPA 25's tables, records, tags, and reports to the fire authority",
                agency=SFM, text=PublicationText.REGULATION),
    Publication("Title 19 forms incorporated by reference (AES forms)",
                "https://34c031f8-c9fd-4018-8c5a-4159cdff6b0d-cdn-endpoint.azureedge.net/-/media/osfm-website/what-we-do/"
                "code-development-and-analysis/title-19-development/formsincorpbyreferencefinal.pdf",
                "the forms a sprinkler inspection is reported on: AES 2.1 (quarterly and annual), AES 2.2 (five-year), AES 10 "
                "(corrections), and the others 19 CCR 906.4 lists",
                agency=SFM, text=PublicationText.REGULATION),
)

# Every agency publication the shelf fetches.
PUBLICATIONS: tuple[Publication, ...] = DRE_PUBLICATIONS + SFM_PUBLICATIONS


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


_PART = re.compile(r"^(\d+)([a-z]*)$")


def number_key(value: str) -> tuple[float, ...]:
    """A section number as a comparable tuple, in the order the codes print them; a non-number sorts first.

    A dotted number compares part by part (2924.9 before 2924.10). A number that ends in a letter comes after the
    bare number and before its dotted ones, as the publication prints them: 2924, 2924a, 2924b, ..., 2924p, 2924.1."""
    key: list[float] = []
    for part in str(value).strip().lower().split("."):
        m = _PART.match(part)
        if not m:
            return (-1.0,)
        key.append(float(m.group(1)))
        if m.group(2):
            # Below every dotted part (a section number's dotted parts are whole numbers, 1 or more), in letter order.
            key.append(sum((ord(c) - 96) / 100 ** (i + 1) for i, c in enumerate(m.group(2))))
    return tuple(key)


def section_in(authority: Authority, number: str) -> bool:
    """Whether a section number falls inside the span."""
    key = number_key(number)
    return key != (-1.0,) and number_key(authority.start) <= key <= number_key(authority.end)
