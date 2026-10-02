"""What each recorded instrument is, and the process it opens or closes.

The county index prints a filing code and a name on every instrument, and
two party lists: the "R" side that signs it away and the "E" side that
receives it. What those sides mean depends on the filing. On a grant deed
they are grantor and grantee. On a deed of trust they are trustor and
beneficiary. On a lien they are the debtor and the claimant. On a release
they swap. This module names each filing the community meets, the family
it belongs to, what its two sides are, and which process it opens, closes,
or advances.

A process is a lifecycle an instrument starts and a later one ends:

- An assessment lien (386) the association records against an owner ends
  with a release (655, 624), or escalates through a notice of default (531)
  and a notice of sale (543) to a trustee's deed (695) or a rescission (720).
- A utility lien (401) the city records against a customer ends with a
  termination (644).
- A tax default: the tax collector's notice of power to sell (802), five
  years after the first unpaid bill, ends with a rescission (720) when the
  bill is paid, or a tax deed (692) when it is not.
- A judgment or tax lien (376, 400) ends with a release (624, 619).
- A PACE assessment (387) stays until the agency releases it.
- A UCC fixture filing (368) ends with a termination (372). The secured
  party says what it is: a solar lessor or lender, the utility, or a bank.
- A mechanic's lien (389) a contractor records against the owner ends with
  a release (635, or a plain 624), or is bonded off (269, 270). The
  claimant has ninety days from recording to sue and record a notice of
  action (385), else the lien expires by Civil Code section 8460 and is
  unenforceable, though it stays of record until a release or a court order
  under section 8480. An extension (232) is a credit agreement that holds
  the deadline open. A withdrawal of lis pendens (651) ends the notice of
  action, not the lien.
- A loan: a deed of trust (230, 229, 231) is assigned (227), its trustee
  substituted (239), modified (235), subordinated (208), or partly released
  (614), and it ends with a reconveyance (238, 613), or it defaults (531),
  is noticed for sale (543), and ends in a trustee's deed (695, 694) or a
  deed in lieu (801). A rescission (720) or a cancelled default (616) cures
  the default and the loan stays open; only on a tax default does the
  rescission end the process.
- A judgment lien: an abstract of judgment (376, 405) or a judgment by
  default (717) opens it; a release of judgment (623) or of lien (624, 619)
  closes it; an order of sale (576) escalates it.
- A support lien: a notice of support judgment (406), an order for support
  payment (392), or a registered foreign support order (593) is a lien on
  the obligor's real property under Family Code section 4506, released by
  a release of judgment (623).
- A federal tax lien (379) ends with its release (631). The county's
  certificate of lien for unsecured taxes (381) ends with a release (623,
  624). A notice of special tax lien (407) is a community facilities
  district's standing charge on the parcel, not a delinquency.
- A county reimbursement agreement (183) the Department of Revenue
  Recovery records is a voluntary lien for county costs, released by 624.
- A notice of substandard building (398) the city records is code
  enforcement against the property, released by 619 or 624.

Owner events (a death affidavit, a power of attorney, a homestead), the
governing instruments (declaration, amendments, annexations, plans, maps),
and easements do not open a lifecycle; they are classified so a report can
say what they are.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from jason.community.index_cache import name_keeps
from jason.community.recorder import FiledInstrument


class Family(Enum):
    CONVEYANCE = "conveyance"
    LOAN = "loan"
    LIEN = "lien"
    RELEASE = "release"
    DEFAULT = "default"
    SALE = "sale"
    GOVERNING = "governing"
    PLAN = "plan"
    MAP = "map"
    NOTICE = "notice"
    VITAL = "vital"
    AUTHORITY = "authority"
    EASEMENT = "easement"
    OTHER = "other"


class Process(Enum):
    """The lifecycles a filing can open, advance, or close."""

    ASSESSMENT_LIEN = "assessment lien"
    UTILITY_LIEN = "utility lien"
    TAX_DEFAULT = "tax default"
    JUDGMENT_LIEN = "judgment lien"
    STATE_TAX_LIEN = "state tax lien"
    PACE_ASSESSMENT = "PACE assessment"
    FIXTURE_FILING = "fixture filing"
    MECHANICS_LIEN = "mechanics lien"
    SUPPORT_LIEN = "support lien"
    FEDERAL_TAX_LIEN = "federal tax lien"
    COUNTY_TAX_LIEN = "county unsecured tax lien"
    SPECIAL_TAX = "special tax lien"
    COUNTY_REIMBURSEMENT = "county reimbursement agreement"
    CODE_ENFORCEMENT = "code enforcement"
    OTHER_LIEN = "lien"
    LOAN = "loan"


# The law each lifecycle runs under, for a brief that has to say why a status is what it is.
PROCESS_NOTES: dict[Process, str] = {
    Process.ASSESSMENT_LIEN: "Civil Code sections 5650 to 5720: the notice of delinquent assessment follows the pre-lien notice, is released on payment, and can go to foreclosure only over the section 5720 threshold and by a board vote under section 5705.",
    Process.UTILITY_LIEN: "The city's utility billing lien on a delinquent account, under the city code; the city records a termination on payment.",
    Process.TAX_DEFAULT: "Revenue and Taxation Code section 3691: the tax collector's power to sell five years after default; a rescission follows redemption.",
    Process.JUDGMENT_LIEN: "Code of Civil Procedure section 697.310: a recorded abstract of judgment is a lien on the debtor's real property for ten years, released by an acknowledgment of satisfaction.",
    Process.SUPPORT_LIEN: "Family Code section 4506: a recorded support judgment is a lien on the obligor's real property until the agency releases it.",
    Process.STATE_TAX_LIEN: "Government Code section 7171: a state tax lien recorded with the county, released when paid.",
    Process.FEDERAL_TAX_LIEN: "26 U.S.C. sections 6321 and 6323: the notice of federal tax lien, released by a certificate under section 6325.",
    Process.COUNTY_TAX_LIEN: "Revenue and Taxation Code section 2191.3: the tax collector's certificate of lien for unpaid unsecured taxes.",
    Process.PACE_ASSESSMENT: "Streets and Highways Code section 5898.12 and following: a PACE assessment runs with the land and is paid on the tax bill until released.",
    Process.SPECIAL_TAX: "Government Code section 53328.3: a community facilities district's notice of special tax lien, a standing charge on the parcel rather than a delinquency.",
    Process.FIXTURE_FILING: "Commercial Code sections 9502 and 9334: a fixture filing recorded with the county; it lapses after five years unless continued under section 9515 and ends with a termination under section 9513.",
    Process.MECHANICS_LIEN: "Civil Code sections 8412 to 8494: recorded within the completion deadlines, sued on within ninety days under section 8460 or expired, released under section 8480 or bonded under section 8424.",
    Process.COUNTY_REIMBURSEMENT: "The county's Department of Revenue Recovery agreement to reimburse: a voluntary lien for county costs, released on payment.",
    Process.CODE_ENFORCEMENT: "Health and Safety Code section 17985 and the city code: a notice of substandard building recorded against the property, released on abatement.",
    Process.LOAN: "Civil Code section 2924 and following: a deed of trust; a notice of default, a notice of sale, a trustee's sale, and a reconveyance under section 2941 on payoff.",
    Process.OTHER_LIEN: "A lien the index names without a code family; read the image before saying what it secures.",
}


OPENS = "opens"
ADVANCES = "advances"
CLOSES = "closes"
ESCALATES = "escalates"
# A rescission or a cancelled default: the default ends and the lifecycle stays open.
CURES = "cures"

# Civil Code section 8460: a claim of lien must be sued on within this many days of recording.
MECHANICS_LIEN_DAYS = 90
# A recorded extension of credit (section 8460(b)) can hold the lien open this long after recording.
MECHANICS_EXTENSION_DAYS = 365


def today_for_status() -> date:
    """The day a lifecycle's status is read. Tests replace it."""
    return date.today()


@dataclass(frozen=True)
class LienLife:
    """How long a recorded lien lasts unless renewed, counted from its newest recording.

    The index gives only the recording date. The statutes count from the
    judgment's entry or the tax's assessment, which come on or before the
    recording, so the end computed here is the latest the lien could last.
    """

    years: int
    extra_days: int
    law: str


LIEN_LIFE: dict[Process, LienLife] = {
    Process.JUDGMENT_LIEN: LienLife(10, 0, "Code of Civil Procedure section 697.310(b): ten years from entry of the judgment unless renewed under section 683.110 and the renewal recorded"),
    Process.STATE_TAX_LIEN: LienLife(10, 0, "Government Code section 7172: ten years from recording unless extended by a new notice"),
    Process.FEDERAL_TAX_LIEN: LienLife(10, 30, "26 U.S.C. section 6323(g): the notice lapses ten years and thirty days after assessment unless refiled"),
}


def _add_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # February 29
        return day.replace(year=day.year + years, day=28)


@dataclass(frozen=True)
class InstrumentClass:
    """One filing: what it is, what its two sides are, and what it does to a process."""

    code: str
    name: str
    family: Family
    r_side: str
    e_side: str
    process: Process | None = None
    effect: str = ""
    keywords: tuple[str, ...] = ()

    @property
    def opens(self) -> bool:
        return self.effect == OPENS

    @property
    def closes(self) -> bool:
        return self.effect == CLOSES


def _cls(code, name, family, r, e, process=None, effect="", keywords=()):
    return InstrumentClass(code, name, family, r, e, process, effect, tuple(keywords))


FILINGS: tuple[InstrumentClass, ...] = (
    # Conveyances
    _cls("685", "GRANT DEED", Family.CONVEYANCE, "grantor", "grantee"),
    _cls("689", "QUITCLAIM DEED", Family.CONVEYANCE, "grantor", "grantee"),
    _cls("680", "DEED", Family.CONVEYANCE, "grantor", "grantee"),
    _cls("692", "TAX DEED", Family.SALE, "tax collector", "buyer", Process.TAX_DEFAULT, CLOSES),
    _cls("695", "TRUSTEES DEED UPON SALE", Family.SALE, "trustee and trustor", "buyer", Process.LOAN, CLOSES),
    _cls("694", "TRUSTEES DEED", Family.SALE, "trustee and trustor", "buyer", Process.LOAN, CLOSES),
    _cls("801", "DEED IN LIEU", Family.SALE, "owner", "lender", Process.LOAN, CLOSES),
    # Loans
    _cls("230", "DEED OF TRUST", Family.LOAN, "trustor", "beneficiary", Process.LOAN, OPENS),
    _cls("229", "CONSTRUCTION DEED OF TRUST", Family.LOAN, "trustor", "beneficiary", Process.LOAN, OPENS),
    _cls("231", "DEED OF TRUST ASSIGNMENT OF RENT", Family.LOAN, "trustor", "beneficiary", Process.LOAN, OPENS),
    _cls("227", "ASSIGNMENT OF DEED OF TRUST", Family.LOAN, "assignor", "assignee", Process.LOAN, ADVANCES),
    _cls("239", "SUBSTITUTION OF TRUSTEE", Family.LOAN, "owner", "new trustee", Process.LOAN, ADVANCES),
    _cls("238", "RECONVEYANCE", Family.RELEASE, "trustee", "owner", Process.LOAN, CLOSES),
    _cls("613", "PARTIAL RECONVEYANCE", Family.RELEASE, "trustee", "owner", Process.LOAN, CLOSES),
    _cls("658", "RELEASE OF ASSIGNMENT OF RENTS", Family.RELEASE, "lender", "owner", Process.LOAN, ADVANCES),
    _cls("531", "NOTICE OF DEFAULT", Family.DEFAULT, "debtor or claimant", "", None, ESCALATES),
    _cls("543", "NOTICE OF TRUSTEES SALE", Family.DEFAULT, "debtor or claimant", "", None, ESCALATES),
    _cls("720", "RESCISSION", Family.RELEASE, "claimant", "debtor", None, CURES),
    _cls("616", "CANCELLED DEFAULT", Family.DEFAULT, "debtor", "", None, CURES),
    _cls("208", "SUBORDINATION AGREEMENT", Family.LOAN, "owner and junior lender", "senior lender", Process.LOAN, ADVANCES),
    _cls("235", "MODIFICATION AGREEMENT", Family.LOAN, "owner", "lender", Process.LOAN, ADVANCES),
    _cls("257", "ASSIGNMENT OF RENTS", Family.LOAN, "owner", "lender", Process.LOAN, ADVANCES),
    _cls("614", "PARTIAL RELEASE", Family.RELEASE, "lender", "owner", Process.LOAN, ADVANCES),
    _cls("576", "ORDER OF SALE", Family.DEFAULT, "judgment debtor", "creditor", None, ESCALATES),
    _cls("542", "NOTICE OF INTENDED SALE", Family.DEFAULT, "owner or seller", "tax collector or buyer", None, ESCALATES),
    _cls("546", "REQUEST FOR NOTICE", Family.NOTICE, "requester", "", None, ""),
    # Liens
    _cls("386", "NOTICE OF ASSOCIATION LIEN", Family.LIEN, "owner", "association", Process.ASSESSMENT_LIEN, OPENS),
    _cls("655", "RELEASE OF ASSESSMENT OF ASSOCIATION LIEN", Family.RELEASE, "association", "owner", Process.ASSESSMENT_LIEN, CLOSES),
    _cls("401", "UTILITY BILLING LIEN", Family.LIEN, "customer", "utility", Process.UTILITY_LIEN, OPENS),
    _cls("644", "TERMINATION OF DELINQUENT UTILITY", Family.RELEASE, "utility", "customer", Process.UTILITY_LIEN, CLOSES),
    _cls("802", "NOTICE OF POWER TO SELL TAX-DEFAULTED PROPERTY", Family.DEFAULT, "owner", "tax collector", Process.TAX_DEFAULT, OPENS),
    _cls("376", "ABSTRACT OF JUDGMENT", Family.LIEN, "debtor", "creditor", Process.JUDGMENT_LIEN, OPENS),
    _cls("405", "ABSTRACT OF JUDGEMENT - UNSECURED", Family.LIEN, "debtor", "creditor", Process.JUDGMENT_LIEN, OPENS),
    _cls("717", "JUDGMENT BY DEFAULT", Family.LIEN, "debtor", "creditor", Process.JUDGMENT_LIEN, OPENS),
    _cls("623", "RELEASE OF JUDGMENT", Family.RELEASE, "creditor", "debtor", None, CLOSES),
    _cls("406", "NOTICE OF SUPPORT JUDGMENT", Family.LIEN, "obligor", "support agency", Process.SUPPORT_LIEN, OPENS),
    _cls("392", "ORDER FOR SUPPORT PAYMENT", Family.LIEN, "obligor", "support agency", Process.SUPPORT_LIEN, OPENS),
    _cls("593", "STATEMENT FOR REGISTRATION OF FOREIGN SUPPORT ORDER", Family.LIEN, "obligor", "support agency", Process.SUPPORT_LIEN, OPENS),
    _cls("379", "CERTIFICATE OF FEDERAL TAX LIEN", Family.LIEN, "taxpayer", "United States", Process.FEDERAL_TAX_LIEN, OPENS),
    _cls("631", "RELEASE OF FEDERAL TAX LIEN", Family.RELEASE, "United States", "taxpayer", Process.FEDERAL_TAX_LIEN, CLOSES),
    _cls("381", "CERTIFICATE OF TAX COLLECTORS LIEN", Family.LIEN, "taxpayer", "tax collector", Process.COUNTY_TAX_LIEN, OPENS),
    _cls("407", "NOTICE OF SPECIAL TAX LIEN", Family.LIEN, "owner", "district", Process.SPECIAL_TAX, OPENS),
    _cls("183", "AGREEMENT TO REIMBURSE", Family.LIEN, "debtor", "county", Process.COUNTY_REIMBURSEMENT, OPENS),
    _cls("398", "SUBSTANDARD BUILDING", Family.LIEN, "owner", "city", Process.CODE_ENFORCEMENT, OPENS),
    _cls("384", "LIEN", Family.LIEN, "debtor", "claimant", Process.OTHER_LIEN, OPENS),
    _cls("", "CHATTEL MORTGAGE", Family.LIEN, "debtor", "lender", Process.OTHER_LIEN, OPENS, keywords=("CHATTEL MORTGAGE",)),
    _cls("380", "CERTIFICATE OF SALE", Family.DEFAULT, "owner", "district or buyer", None, ESCALATES),
    _cls("365", "UCC AMENDMENT", Family.LIEN, "debtor", "secured party", Process.FIXTURE_FILING, ADVANCES),
    _cls("366", "UCC ASSIGNMENT", Family.LIEN, "debtor", "secured party", Process.FIXTURE_FILING, ADVANCES),
    _cls("367", "UCC CONTINUATION", Family.LIEN, "debtor", "secured party", Process.FIXTURE_FILING, ADVANCES),
    _cls("370", "UCC PARTIAL RELEASE", Family.RELEASE, "secured party", "debtor", Process.FIXTURE_FILING, ADVANCES),
    _cls("371", "UCC RELEASE", Family.RELEASE, "secured party", "debtor", Process.FIXTURE_FILING, CLOSES),
    _cls("400", "STATE TAX LIEN", Family.LIEN, "taxpayer", "state", Process.STATE_TAX_LIEN, OPENS),
    _cls("624", "RELEASE OF LIEN", Family.RELEASE, "claimant", "debtor", None, CLOSES),
    _cls("619", "RELEASE", Family.RELEASE, "claimant", "debtor", None, CLOSES),
    _cls("387", "NOTICE OF ASSESSMENT", Family.LIEN, "owner", "agency", Process.PACE_ASSESSMENT, OPENS),
    _cls("368", "UCC FINANCING STATEMENT", Family.LIEN, "debtor", "secured party", Process.FIXTURE_FILING, OPENS),
    _cls("372", "UCC TERMINATION", Family.RELEASE, "debtor", "secured party", Process.FIXTURE_FILING, CLOSES),
    _cls("389", "NOTICE OF CLAIM OR MECHANICS LIEN", Family.LIEN, "owner", "claimant", Process.MECHANICS_LIEN, OPENS),
    _cls("232", "EXTENSION MECHANICS LIEN", Family.LIEN, "owner", "claimant", Process.MECHANICS_LIEN, ADVANCES),
    _cls("635", "RELEASE OF MECHANICS LIEN", Family.RELEASE, "claimant", "owner", Process.MECHANICS_LIEN, CLOSES),
    _cls("269", "RELEASE OF LIEN BOND", Family.RELEASE, "principal", "claimant", None, CLOSES),
    _cls("270", "BONDS TO GUARANTEE MECHANIC LIEN", Family.RELEASE, "principal", "claimant", Process.MECHANICS_LIEN, CLOSES),
    _cls("385", "NOTICE OF ACTION", Family.DEFAULT, "plaintiff", "defendant", None, ESCALATES),
    _cls("223", "AMENDED NOTICE OF ACTION LIS PENDENS", Family.DEFAULT, "plaintiff", "defendant", None, ESCALATES),
    _cls("651", "WITHDRAWAL OF LIS PENDENS", Family.DEFAULT, "plaintiff", "defendant", None, ADVANCES),
    _cls("291", "CERTIFICATE OF PARTIAL DISCHARGE OF NOTICE OF PENDING ACTION", Family.DEFAULT, "plaintiff", "defendant", None, ADVANCES),
    _cls("305", "NOTICE OF CESSATION", Family.NOTICE, "owner", ""),
    _cls("539", "NOTICE OF NON RESPONSIBILITY", Family.NOTICE, "owner", ""),
    _cls("549", "NOTICE", Family.NOTICE, "subject", "party", None, ""),
    # Governing instruments
    _cls("162", "DECLARATION", Family.GOVERNING, "declarant", "", keywords=("DECLARATION",)),
    _cls("324", "DECLARATION OF RESTRICTION", Family.GOVERNING, "declarant", ""),
    _cls("220", "AMENDED RESTRICTION", Family.GOVERNING, "declarant", ""),
    _cls("225", "AMENDMENT", Family.GOVERNING, "declarant", ""),
    _cls("320", "DECLARATION OF ANNEXATION", Family.GOVERNING, "declarant", ""),
    _cls("478", "RESTRICTIVE COVENANT", Family.GOVERNING, "declarant", ""),
    _cls("499", "RESTRICTIVE COVENANT MODIFICATION", Family.GOVERNING, "declarant", ""),
    _cls("604", "CANCELLATION OF RESTRICTIONS", Family.GOVERNING, "declarant", ""),
    _cls("188", "COVENANT AND AGREEMENT", Family.GOVERNING, "covenantor", "covenantee"),
    _cls("446", "ARTICLES OF INCORPORATION", Family.GOVERNING, "corporation", ""),
    _cls("494", "BY LAWS", Family.GOVERNING, "association", ""),
    _cls("476", "RESOLUTION", Family.GOVERNING, "body", ""),
    _cls("301", "CONDOMINIUM PLAN", Family.PLAN, "owner", ""),
    _cls("240", "AMENDMENT TO CONDO PLAN", Family.PLAN, "owner", ""),
    _cls("435", "SUBDIVISION MAP", Family.MAP, "owner", ""),
    _cls("433", "PARCEL MAP", Family.MAP, "owner", ""),
    _cls("285", "CERTIFICATE OF CORRECTION", Family.MAP, "owner", ""),
    _cls("460", "LOT LINE ADJUSTMENT", Family.MAP, "owner", ""),
    _cls("307", "PLANS AND SPECIFICATIONS", Family.PLAN, "owner", ""),
    _cls("535", "NOTICE OF INTENDED BULK TRANSFER", Family.NOTICE, "seller", "buyer"),
    _cls("266", "NOTARY BOND", Family.OTHER, "notary", "surety"),
    _cls("181", "AGREEMENT", Family.OTHER, "party", "party"),
    _cls("195", "AGREEMENT TO SELL", Family.CONVEYANCE, "seller", "buyer"),
    _cls("199", "PARTNERSHIP", Family.OTHER, "partner", "partner"),
    _cls("306", "NOTICE OF COMPLETION", Family.NOTICE, "owner or builder", ""),
    # Owner events and rights
    # A living owner's estate plan, not a death: it names who takes the unit at death (Probate Code 5614). Read before the
    # death keyword below, which would otherwise match its name.
    _cls("697", "REVOCABLE TRANSFER ON DEATH DEED", Family.AUTHORITY, "transferor", "beneficiary", keywords=("TRANSFER ON DEATH",)),
    _cls("153", "AFFIDAVIT OF DEATH", Family.VITAL, "decedent", "survivor"),
    _cls("156", "AFFIDAVIT TERMINATING JOINT TENANCY", Family.VITAL, "decedent", "survivor"),
    _cls("151", "AFFIDAVIT", Family.VITAL, "affiant", "", keywords=("DEATH",)),
    _cls("466", "POWER OF ATTORNEY", Family.AUTHORITY, "principal", "attorney in fact"),
    _cls("555", "LETTERS OF ADMINISTRATION", Family.AUTHORITY, "estate", "administrator"),
    _cls("558", "LETTERS OF TESTAMENTARY", Family.AUTHORITY, "estate", "executor"),
    _cls("559", "ORDER", Family.AUTHORITY, "court or estate", "party"),
    _cls("", "DECLARATION OF HOMESTEAD", Family.AUTHORITY, "owner", "", keywords=("HOMESTEAD",)),
    _cls("190", "EASEMENT", Family.EASEMENT, "grantor", "grantee"),
    _cls("681", "EASEMENT DEED", Family.EASEMENT, "grantor", "grantee"),
    _cls("485", "RIGHT OF WAY", Family.EASEMENT, "grantor", "grantee"),
)

_BY_CODE = {item.code: item for item in FILINGS if item.code}
_UNKNOWN = _cls("", "", Family.OTHER, "R", "E")


# The early walk labeled a row by what it did before the index's filing was stored.
_BY_KIND = {
    "fee": InstrumentClass("", "DEED (BY KIND)", Family.CONVEYANCE, "grantor", "grantee"),
    "lien": "230",
    "release": "238",
    "foreclosure": "695",
    "notice": "306",
    "death": "153",
}


def instrument_class(code: str = "", name: str = "", kind: str = "") -> InstrumentClass:
    """The class of a filing, by code, else by a keyword in its printed name, else by the walk's kind."""
    found = _BY_CODE.get(str(code or "").strip())
    if found is not None:
        return found
    upper = " ".join(str(name or "").upper().split())
    if not upper and kind in _BY_KIND:
        by_kind = _BY_KIND[kind]
        return by_kind if isinstance(by_kind, InstrumentClass) else _BY_CODE[by_kind]
    for item in FILINGS:
        if item.name and item.name == upper:
            return item
    for item in FILINGS:
        if any(word in upper for word in item.keywords):
            return item
    if "DEED OF TRUST" in upper:
        return _BY_CODE["230"]
    if "RECONVEYANCE" in upper:
        return _BY_CODE["238"]
    if "LIEN" in upper and "RELEASE" in upper:
        return _BY_CODE["624"]
    return InstrumentClass("", upper, Family.OTHER, "R", "E")


# Which processes a notice of default, a notice of sale, or a rescission can belong to,
# decided by who recorded it.
def _escalation_process(item: FiledInstrument, association: str) -> Process | None:
    parties = " ".join((*item.grantors, *item.grantees)).upper()
    if _tax_collector(item):
        return Process.TAX_DEFAULT
    if "CHILD SUPPORT" in parties:
        return Process.SUPPORT_LIEN
    if association and association.upper() in parties:
        return Process.ASSESSMENT_LIEN
    return Process.LOAN


def _tax_collector(item: FiledInstrument) -> bool:
    parties = " ".join((*item.grantors, *item.grantees)).upper()
    return "TAX COLLECTOR" in parties or ("COUNTY OF SAC" in parties and " TAX" in parties)


# Processes a release with no process of its own can close, newest first, before a loan.
_LIEN_PROCESSES = (
    Process.JUDGMENT_LIEN, Process.SUPPORT_LIEN, Process.STATE_TAX_LIEN, Process.FEDERAL_TAX_LIEN, Process.COUNTY_TAX_LIEN,
    Process.PACE_ASSESSMENT, Process.SPECIAL_TAX, Process.MECHANICS_LIEN, Process.ASSESSMENT_LIEN, Process.UTILITY_LIEN,
    Process.COUNTY_REIMBURSEMENT, Process.CODE_ENFORCEMENT, Process.OTHER_LIEN, Process.FIXTURE_FILING,
)


@dataclass(frozen=True)
class Step:
    number: str
    recorded: date | None
    filing: str
    effect: str
    r_side: tuple[str, ...]
    e_side: tuple[str, ...]


@dataclass(frozen=True)
class Encumbrance:
    """One lifecycle: the instrument that opened it, what followed, and whether it is closed."""

    process: Process
    debtor: tuple[str, ...]
    claimant: tuple[str, ...]
    steps: tuple[Step, ...] = field(default_factory=tuple)

    @property
    def opened(self) -> Step:
        return self.steps[0]

    @property
    def status(self) -> str:
        last = self.steps[-1]
        if last.effect == CLOSES:
            return "closed"
        if self.process is Process.MECHANICS_LIEN:
            return self._mechanics_status()
        if last.effect != ESCALATES and self.process in LIEN_LIFE:
            end = self.unenforceable_after
            if end is not None and today_for_status() > end:
                return "lapsed"
        if last.effect == ESCALATES:
            if last.filing.startswith("531"):
                return "in default"
            if last.filing.startswith("576") or last.filing.startswith("542"):
                return "ordered for sale" if last.filing.startswith("576") else "noticed for tax sale"
            return "noticed for sale"
        return "open"

    def _mechanics_status(self) -> str:
        """Open, in suit, action withdrawn, or expired under Civil Code section 8460."""
        codes = [step.filing[:3] for step in self.steps]
        if "385" in codes or "223" in codes:
            last_action = max(index for index, code in enumerate(codes) if code in ("385", "223"))
            if any(code == "651" for code in codes[last_action + 1:]):
                return "action withdrawn"
            return "in suit"
        opened = self.opened.recorded
        if opened is None:
            return "open"
        window = MECHANICS_EXTENSION_DAYS if "232" in codes else MECHANICS_LIEN_DAYS
        if (today_for_status() - opened).days > window:
            return "expired"
        return "open"

    @property
    def unenforceable_after(self) -> date | None:
        """The last day the lien can be enforced: a mechanic's lien's suit deadline, or the end of a lien's statutory life.

        A lien with a life (``LIEN_LIFE``) counts from its newest opening or
        advancing step, since a renewal is recorded again.
        """
        life = LIEN_LIFE.get(self.process) if self.process is not None else None
        if life is not None:
            dates = [step.recorded for step in self.steps if step.recorded is not None and step.effect in (OPENS, ADVANCES)]
            if not dates:
                return None
            return _add_years(max(dates), life.years) + timedelta(days=life.extra_days)
        if self.process is not Process.MECHANICS_LIEN or self.opened.recorded is None:
            return None
        codes = [step.filing[:3] for step in self.steps]
        window = MECHANICS_EXTENSION_DAYS if "232" in codes else MECHANICS_LIEN_DAYS
        return self.opened.recorded + timedelta(days=window)

    @property
    def closed(self) -> date | None:
        last = self.steps[-1]
        return last.recorded if last.effect == CLOSES else None


def encumbrances(
    items: tuple[FiledInstrument, ...] | list[FiledInstrument],
    *,
    association: str = "",
) -> tuple[Encumbrance, ...]:
    """Pair the lien-family instruments in ``items`` into lifecycles, oldest first.

    A closing or escalating instrument joins the newest open lifecycle of its
    process whose debtor it names, or whose opening instrument it cites. One
    that joins nothing starts a lifecycle of its own, so a release with no
    lien in hand is still shown. ``association`` is the leading name of the
    association, used to read a notice of default or a rescission the
    association recorded as part of an assessment lien.
    """
    ordered = sorted(items, key=lambda item: (item.recorded or date.min, item.number))
    found: list[list[Step]] = []
    meta: list[tuple[Process, tuple[str, ...], tuple[str, ...]]] = []
    for item in ordered:
        klass = instrument_class(item.filing_code, item.filing_name, item.kind)
        if klass.family not in (Family.LOAN, Family.LIEN, Family.RELEASE, Family.DEFAULT, Family.SALE):
            continue
        if klass.code == "542" and not _tax_collector(item):
            continue  # a business bulk-sale notice, not a lien step
        process = klass.process or _escalation_process(item, association)
        if klass.family == Family.SALE and klass.process is Process.LOAN and not _looks_like_loan_sale(item):
            process = _escalation_process(item, association)
        step = Step(item.number, item.recorded, f"{klass.code} {klass.name}".strip(), klass.effect or ADVANCES, item.grantors, item.grantees)
        if klass.opens and not klass.family == Family.SALE:
            found.append([step])
            meta.append((process, item.grantors, item.grantees))
            continue
        target = _join(
            found, meta, process, item, klass, loose=klass.process is None,
            any_process=klass.code in _ACTION_CODES or (klass.process is None and klass.effect in (CLOSES, CURES, ESCALATES)),
        )
        if target is not None and klass.process is None:
            process = meta[target][0]
        if klass.effect == CURES and target is not None and meta[target][0] is Process.TAX_DEFAULT:
            step = Step(step.number, step.recorded, step.filing, CLOSES, step.r_side, step.e_side)
        if target is None:
            found.append([step])
            debtor, claimant = (item.grantees, item.grantors) if klass.closes else (item.grantors, item.grantees)
            meta.append((process, debtor, claimant))
        else:
            found[target].append(step)
    return tuple(
        Encumbrance(process, debtor, claimant, tuple(steps))
        for steps, (process, debtor, claimant) in zip(found, meta)
    )


_ACTION_CODES = ("385", "223", "651", "291")


def _join(found, meta, process, item: FiledInstrument, klass: InstrumentClass, *, loose: bool = False, any_process: bool = False) -> int | None:
    """The index of the newest open lifecycle this instrument continues, or None.

    A citation of the opening instrument joins whatever process it is. Then
    the debtor's name joins the newest open lifecycle of the same process.
    A notice of default or a rescission that names only the claimant (the
    association's own filings do) joins that claimant's newest open lien.
    A notice of action names the parties to a suit, not a process, so with
    ``any_process`` it joins the newest open lifecycle naming either party,
    a mechanic's lien before a loan.
    """
    names = (*item.grantors, *item.grantees)
    for index in range(len(found) - 1, -1, -1):
        if found[index][-1].effect != CLOSES and found[index][0].number in item.cross_references:
            return index
    if any_process:
        # A lien process before a loan, since a release or an order names the debtor and not the code it ends.
        for wanted in (*_LIEN_PROCESSES, Process.TAX_DEFAULT, Process.LOAN):
            for index in range(len(found) - 1, -1, -1):
                own_process, debtor, claimant = meta[index]
                if found[index][-1].effect == CLOSES or own_process is not wanted:
                    continue
                if any(same_party(a, b) for a in (*debtor, *claimant) for b in names):
                    return index
        return None
    for index in range(len(found) - 1, -1, -1):
        steps = found[index]
        own_process, debtor, _claimant = meta[index]
        if own_process is not process or steps[-1].effect == CLOSES:
            continue
        if any(same_party(a, b) for a in debtor for b in names):
            return index
    if loose:
        for index in range(len(found) - 1, -1, -1):
            steps = found[index]
            own_process, _debtor, claimant = meta[index]
            if own_process is not process or steps[-1].effect == CLOSES:
                continue
            if any(same_party(a, b) for a in claimant for b in names):
                return index
    return None


def same_party(left: str, right: str) -> bool:
    """``name_keeps`` either way, or the same surname and given name with an initial or suffix dropped."""
    if name_keeps(left, right) or name_keeps(right, left):
        return True
    one = [token for token in left.upper().split() if token not in _ROLE_WORDS]
    two = [token for token in right.upper().split() if token not in _ROLE_WORDS]
    if len(one) < 2 or len(two) < 2:
        return False
    if len(one) == len(two):
        # "DOE JOHN Q" and "DOE JOHN QUINCY" are the same length; either may carry the initial.
        return _initials_fit(one, two) or _initials_fit(two, one)
    return _initials_fit(one, two) if len(one) < len(two) else _initials_fit(two, one)


class NameMatch(Enum):
    """How closely a filing's party name matches the owner's name on the deed."""

    FULL = "the filing spells the owner's name as the deed does"
    PARTIAL = "the names agree as far as the shorter goes: a middle initial, or a middle name dropped"
    BARE = "the filing gives only a surname and a given name; it could be a namesake"


_COMPANY_WORDS = frozenset({"LLC", "INC", "CORP", "CO", "LP", "LTD", "BANK", "BK", "TRUST", "TR", "ASSN", "ASSOCIATION", "COMPANY"})


def name_match(owner: str, party: str) -> NameMatch | None:
    """How ``party`` on a filing matches ``owner`` on the deed, or None when ``same_party`` says they differ.

    A person the deed names with a middle name or initial, named on the
    filing by surname and given name alone, is ``BARE``: "LINDQVIST ROBERT" is
    Robert J. Lindqvist and Robert Alan Lindqvist alike. When the deed itself
    gives only two words, the filing cannot say more than the deed, and a
    match on both is ``FULL``. A company name is judged on its words.
    """
    if not same_party(owner, party):
        return None
    words = party.upper().split()
    company = any(word in _COMPANY_WORDS for word in words)
    mine = [w for w in owner.upper().split() if w not in _ROLE_WORDS]
    theirs = [w for w in words if w not in _ROLE_WORDS]
    if len(theirs) <= 2 < len(mine) and not company:
        return NameMatch.BARE
    return NameMatch.FULL if mine == theirs or company else NameMatch.PARTIAL


def _initials_fit(short: list[str], long: list[str]) -> bool:
    """Every word of ``short`` past the surname and given name is in ``long``, or is an initial of a word there."""
    if short[0] != long[0] or short[1] != long[1]:
        return False
    rest = long[2:]
    return all(
        token in long or (len(token) == 1 and any(word.startswith(token) for word in rest))
        for token in short[2:]
        if token not in _SUFFIXES
    )


_ROLE_WORDS = frozenset({"TRUSTEE", "TRUST", "LLC", "INC", "CORP", "TR", "ETC", "FMLY", "FAMILY"})
_SUFFIXES = frozenset({"JR", "SR", "II", "III"})


def _looks_like_loan_sale(item: FiledInstrument) -> bool:
    return bool(item.cross_references) or any("TR" in name.upper().split() or "TRUSTEE" in name.upper() or "RECON" in name.upper() for name in item.grantors)


def naming(items: tuple[FiledInstrument, ...] | list[FiledInstrument], party: str) -> tuple[FiledInstrument, ...]:
    """The instruments that name ``party`` on either side, under ``same_party``."""
    return tuple(item for item in items if any(same_party(party, name) for name in (*item.grantors, *item.grantees)))


def party_is(item: FiledInstrument, party: str) -> str:
    """Which side of ``item`` names ``party``: ``R``, ``E``, both, or empty."""
    on_r = any(same_party(party, name) for name in item.grantors)
    on_e = any(same_party(party, name) for name in item.grantees)
    if on_r and on_e:
        return "R and E"
    return "R" if on_r else ("E" if on_e else "")
