"""Who owns the rooftop solar on each unit, read from the UCC fixture filings.

A developer that sells a unit with leased solar has the lessor record a UCC
financing statement (368) against the buyer, naming the lessor as secured
party; a termination (372) ends it when the lease is bought out or the
system transfers. A buyer who purchased the panels outright has no filing.
The county indexes a fixture filing by the debtor's name, not the parcel,
so a unit's filings are the lifecycles that name its owners.

A UCC filing is not only solar. The same code covers a bank's fixture
lien, the utility's financing, and a solar loan. ``classify_secured_party``
reads the secured party: the program's own lessors first, then a solar
lessor, a solar lender, the utility, a bank, or other. ``solar_record``
then states one unit's standing: the lease is on the current owner, on a
prior owner only, terminated, or never filed. Absence of a filing is not
proof of purchase, since a filing can be missed or never recorded; the
record says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from jason.community.filings import Encumbrance, Process, same_party


@dataclass(frozen=True)
class SolarProgram:
    """The developer's shared-solar arrangement: which buildings, and the lessors that file against buyers.

    ``lessors`` are the secured-party names the index prints. ``index_queries``
    are the leading words a county-wide search uses to fetch every filing
    those lessors recorded. ``servicer`` names who services the leases now.
    """

    name: str
    developer: str
    buildings: tuple[int, ...]
    lessors: tuple[str, ...]
    index_queries: tuple[str, ...]
    servicer: str = ""
    note: str = ""

    def covers(self, building: int | None) -> bool:
        return building is not None and int(building) in tuple(int(b) for b in self.buildings)

    def is_lessor(self, name: str) -> bool:
        return any(same_party(lessor, name) for lessor in self.lessors)


class SecuredPartyKind(Enum):
    PROGRAM_LESSOR = "the developer program's solar lessor"
    SOLAR_LESSOR = "a solar lessor"
    SOLAR_LENDER = "a solar lender"
    UTILITY = "the utility"
    LENDER = "a bank or finance company"
    OTHER = "other"


@dataclass(frozen=True)
class SecuredPartyRule:
    kind: SecuredPartyKind
    words: tuple[str, ...]


# Read in order against the secured party's index spelling. The program's own lessors are read first.
SECURED_PARTY_RULES: tuple[SecuredPartyRule, ...] = (
    SecuredPartyRule(SecuredPartyKind.SOLAR_LENDER, ("LOANPAL", "GOODLEAP", "MOSAIC", "DIVIDEND", "SUNLIGHT FIN")),
    SecuredPartyRule(SecuredPartyKind.SOLAR_LESSOR, ("SUNRUN", "TESLA", "SOLARCITY", "SUNNOVA", "SUNSTREET", "SUNSTRONG", "VIVINT", "SUNPOWER", "SOLAR")),
    SecuredPartyRule(SecuredPartyKind.UTILITY, ("SACTO MUNI UTILY", "SMUD", "SACRAMENTO MUNICIPAL", "PG&E", "PACIFIC GAS")),
    SecuredPartyRule(SecuredPartyKind.LENDER, ("BANK", " BK", "CAPITAL", "FINL", "FINANCIAL", "CREDIT UNION", "FUNDING", "LENDING", "MORTGAGE")),
)


def classify_secured_party(names: tuple[str, ...], program: SolarProgram | None = None) -> SecuredPartyKind:
    """What kind of secured party a fixture filing names. The first rule that matches wins."""
    if program is not None and any(program.is_lessor(name) for name in names):
        return SecuredPartyKind.PROGRAM_LESSOR
    blob = " " + " ".join(" ".join(name.upper().split()) for name in names) + " "
    for rule in SECURED_PARTY_RULES:
        if any(word in blob for word in rule.words):
            return rule.kind
    return SecuredPartyKind.OTHER


class SolarStanding(Enum):
    LEASE_ON_CURRENT_OWNER = "leased: the lessor's filing stands against the current owner"
    LEASE_NOTICE_ONLY = "a recorded notice of the solar contract names the current owner, with no fixture filing found"
    LEASE_ON_PRIOR_OWNER = "a lease filing stands against a prior owner and none against the current one"
    LEASE_TERMINATED = "a lease filing was recorded and later terminated"
    NO_FILING = "no lease filing found: purchased, or a filing the index does not show"
    OUTSIDE_PROGRAM = "outside the developer's solar program"


@dataclass(frozen=True)
class SolarFiling:
    """One lifecycle a program lessor recorded against an owner of the unit."""

    number: str
    recorded: date | None
    lessor: str
    owner: str
    status: str
    closed: date | None
    during_tenure: bool
    steps: tuple[str, ...]


@dataclass(frozen=True)
class SolarNotice:
    """A notice of the solar contract the lessor recorded against an owner (Public Utilities Code section 2869)."""

    number: str
    recorded: date | None
    lessor: str
    owner: str
    during_tenure: bool


@dataclass(frozen=True)
class SolarRecord:
    program: str
    standing: SolarStanding
    filings: tuple[SolarFiling, ...] = ()
    current_filing: SolarFiling | None = None
    note: str = ""
    notices: tuple[SolarNotice, ...] = ()

    @property
    def lessor(self) -> str:
        if self.current_filing is not None:
            return self.current_filing.lessor
        return self.filings[-1].lessor if self.filings else ""

    @property
    def leased(self) -> bool:
        return self.standing is SolarStanding.LEASE_ON_CURRENT_OWNER


def solar_record(
    building: int | None,
    current_owners: tuple[str, ...],
    liens,
    program: SolarProgram,
    *,
    sales: tuple[date, ...] = (),
    notices: tuple[SolarNotice, ...] = (),
) -> SolarRecord:
    """One unit's solar standing from the lifecycles that name its owners.

    ``liens`` are the parcel's ``ParcelLien`` rows. ``sales`` are the dates
    the unit sold, used to say when a termination fell on the day of a sale.
    """
    if not program.covers(building):
        return SolarRecord(program.name, SolarStanding.OUTSIDE_PROGRAM, note="Buildings outside the program have no shared system to transfer.")
    filings: list[SolarFiling] = []
    for lien in liens:
        e: Encumbrance = lien.encumbrance
        if e.process is not Process.FIXTURE_FILING or classify_secured_party(e.claimant, program) is not SecuredPartyKind.PROGRAM_LESSOR:
            continue
        lessor = next((name for name in e.claimant if program.is_lessor(name)), e.claimant[0] if e.claimant else "")
        filings.append(SolarFiling(
            e.opened.number, e.opened.recorded, lessor, lien.owner, e.status, e.closed, lien.during_tenure,
            tuple(f"{step.filing} {step.number}" for step in e.steps),
        ))
    filings.sort(key=lambda f: (f.recorded or date.min, f.number))
    on_current = [f for f in filings if f.status != "closed" and any(same_party(f.owner, name) for name in current_owners)]
    if on_current:
        current = on_current[-1]
        return SolarRecord(program.name, SolarStanding.LEASE_ON_CURRENT_OWNER, tuple(filings), current,
                           f"Escrow should carry the lease to the buyer; the lessor is {current.lessor}.", notices)
    notice_current = [n for n in notices if any(same_party(n.owner, name) for name in current_owners)]
    if notice_current:
        last_notice = notice_current[-1]
        return SolarRecord(program.name, SolarStanding.LEASE_NOTICE_ONLY, tuple(filings), None,
                           f"A notice of the solar contract recorded {last_notice.recorded} by {last_notice.lessor} names the current owner; the fixture filing may be under another spelling or unrecorded. Treat the lease as standing.", notices)
    open_prior = [f for f in filings if f.status != "closed" and f.during_tenure]
    if open_prior:
        last = open_prior[-1]
        return SolarRecord(program.name, SolarStanding.LEASE_ON_PRIOR_OWNER, tuple(filings), None,
                           f"The filing against {last.owner} was never terminated and no filing names the current owner; ask the lessor whether the lease transferred or was bought out.", notices)
    closed = [f for f in filings if f.status == "closed" and f.during_tenure]
    if closed:
        last = closed[-1]
        when = ""
        sold = next((day for day in sales if last.closed and abs((last.closed - day).days) <= 3), None)
        if sold is not None:
            when = f" on the day of the {sold.isoformat()} sale, a buyout or transfer at escrow"
        return SolarRecord(program.name, SolarStanding.LEASE_TERMINATED, tuple(filings), None,
                           f"The filing against {last.owner} was terminated{when}; the current owner has no filing.", notices)
    return SolarRecord(program.name, SolarStanding.NO_FILING, tuple(filings), None,
                       "The first buyer chose to lease or to purchase; with no lessor filing, purchase is likely, but the index can miss a filing.", notices)


def solar_notices(load_naming, steps: tuple, program: SolarProgram) -> tuple[SolarNotice, ...]:
    """The recorded notices of the solar contract (filing 549) that name an owner on ``steps`` and a program lessor."""
    found: list[SolarNotice] = []
    seen: set[str] = set()
    plain = [getattr(step, "conveyance", step) for step in steps]
    spans = [
        (name, step.recorded, plain[index + 1].recorded if index + 1 < len(plain) else None)
        for index, step in enumerate(plain) for name in step.grantees if name.strip()
    ]
    for name, _start, _until in spans:
        for item in load_naming(name):
            if item.number in seen or item.filing_code != "549":
                continue
            lessor = next((party for party in item.grantees if program.is_lessor(party)), "")
            if not lessor or not any(same_party(name, party) for party in item.grantors):
                continue
            seen.add(item.number)
            # The same owner on two steps has two spans; a notice inside either is during their ownership.
            during = any(
                same_party(owner, party) and item.recorded is not None and start is not None and item.recorded >= start and (until is None or item.recorded <= until)
                for owner, start, until in spans for party in item.grantors
            )
            found.append(SolarNotice(item.number, item.recorded, lessor, name, during))
    found.sort(key=lambda n: (n.recorded or date.min, n.number))
    return tuple(found)


def shared_filings(records: dict[str, SolarRecord]) -> dict[str, tuple[str, ...]]:
    """Units whose current lease filing also stands for another unit, by key.

    The index names the debtor, not the unit, so an owner of several units
    shows the same filing on each. One of them is leased; the record cannot
    say which. The value is the other keys that share the filing.
    """
    by_number: dict[str, list[str]] = {}
    for key, record in records.items():
        if record.current_filing is not None:
            by_number.setdefault(record.current_filing.number, []).append(key)
    found: dict[str, tuple[str, ...]] = {}
    for keys in by_number.values():
        if len(keys) > 1:
            for key in keys:
                found[key] = tuple(other for other in keys if other != key)
    return found
