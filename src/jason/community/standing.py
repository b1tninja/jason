"""A parcel's standing beyond title: its taxes, and the events in its owners' lives.

The tax collector records nothing until a bill has gone unpaid for five
fiscal years, when the notice of power to sell (802) goes on. The bills
themselves show the delinquency the day after the second installment is
late, so they are the earlier warning. A year with no bill on file is its
own signal: while a parcel is tax-defaulted the county serves a redemption
page in place of the annual bill, which is what happened to the common
areas before the 2023 notice.

An owner's life shows in the index as an affidavit of death (153, 156), a
power of attorney (466), a declaration of homestead, or a deed into the
owner's own trust. None moves the fee to a new owner, but each says who can
act for the parcel now, and a death affidavit names the survivor the
membership record should carry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from jason.community.filings import Family, instrument_class, same_party
from jason.community.recorder import FiledInstrument
from jason.community.tax import TaxBill

# Revenue and Taxation Code section 3691: a parcel is subject to the power to
# sell five years after it becomes tax-defaulted, on July 1.
DEFAULT_YEARS = 5


@dataclass(frozen=True)
class TaxStanding:
    """What the bills say about a parcel's taxes."""

    first_year: int | None
    last_year: int | None
    missing_years: tuple[int, ...]
    unpaid: tuple[tuple[int, int], ...]
    delinquent: tuple[tuple[int, int], ...]

    @property
    def status(self) -> str:
        if self.delinquent:
            return "delinquent"
        if self.unpaid:
            return "due"
        if self.missing_years:
            return "gap in the bills"
        return "paid"

    @property
    def oldest_delinquent(self) -> int | None:
        return min((year for year, _ in self.delinquent), default=None)

    @property
    def power_to_sell(self) -> date | None:
        """The July 1 the tax collector may notice the parcel for sale, if nothing is paid."""
        oldest = self.oldest_delinquent
        if oldest is None:
            return None
        return date(oldest + 1 + DEFAULT_YEARS, 7, 1)


def tax_standing(bills: tuple[TaxBill, ...] | list[TaxBill]) -> TaxStanding:
    """Read the annual bills: unpaid, delinquent, and years with no bill on file.

    The newest year with a balance is due. An older year with a balance is
    delinquent. A year between the first and last bill with no total is a
    gap, and a gap on a common-area parcel is the years the county carried
    it as tax-defaulted.
    """
    yearly = [bill for bill in bills if bill.year is not None]
    if not yearly:
        return TaxStanding(None, None, (), (), ())
    years = sorted({bill.year for bill in yearly})
    newest = years[-1]
    totals: dict[int, int | None] = {}
    balances: dict[int, int] = {}
    for bill in yearly:
        if bill.total_cents is not None:
            totals[bill.year] = (totals.get(bill.year) or 0) + bill.total_cents
        if bill.balance_cents:
            balances[bill.year] = balances.get(bill.year, 0) + bill.balance_cents
    missing = tuple(year for year in range(years[0], years[-1] + 1) if totals.get(year) is None)
    unpaid = tuple(sorted((year, cents) for year, cents in balances.items() if year == newest))
    delinquent = tuple(sorted((year, cents) for year, cents in balances.items() if year < newest))
    return TaxStanding(years[0], years[-1], missing, unpaid, delinquent)


@dataclass(frozen=True)
class OwnerEvent:
    """An instrument about an owner that moves no title."""

    owner: str
    number: str
    recorded: date | None
    filing: str
    kind: str
    parties: tuple[str, ...]
    during_tenure: bool
    still_on_title: bool


def owner_events(load_naming, steps: tuple, *, current_owners: tuple[str, ...] = ()) -> tuple[OwnerEvent, ...]:
    """The vital and authority instruments naming each owner on ``steps``, oldest first.

    ``still_on_title`` is set on a death affidavit whose decedent is still a
    grantee on the newest deed, which is the membership record's cue.
    """
    plain = [getattr(step, "conveyance", step) for step in steps]
    found: list[OwnerEvent] = []
    seen: set[str] = set()
    spans = [
        (name, step.recorded, plain[index + 1].recorded if index + 1 < len(plain) else None)
        for index, step in enumerate(plain) for name in step.grantees if name.strip()
    ]
    for name, _start, _until in spans:
        for item in load_naming(name):
            klass = instrument_class(item.filing_code, item.filing_name, item.kind)
            if klass.family not in (Family.VITAL, Family.AUTHORITY) or item.number in seen:
                continue
            seen.add(item.number)
            when = item.recorded
            # The same owner on two steps has two spans; an event inside either is during their ownership.
            during = any(
                same_party(owner, name) and when is not None and start is not None and when >= start and (until is None or when <= until)
                for owner, start, until in spans
            )
            decedent = klass.family is Family.VITAL and any(same_party(name, party) for party in item.grantors)
            on_title = decedent and any(same_party(name, owner) for owner in current_owners)
            found.append(
                OwnerEvent(
                    name, item.number, when, f"{klass.code} {klass.name}".strip(), _kind(klass, decedent),
                    tuple(dict.fromkeys((*item.grantors, *item.grantees))), during, on_title,
                )
            )
    found.sort(key=lambda event: (event.recorded or date.min, event.number))
    return tuple(found)


def _kind(klass, decedent: bool) -> str:
    if klass.family is Family.VITAL:
        return "death of this owner" if decedent else "death of a co-owner; this owner survives"
    if "HOMESTEAD" in klass.name:
        return "homestead declared"
    if klass.code == "466":
        return "power of attorney"
    if klass.code == "697":
        return "transfer on death deed: names who takes the unit at the owner's death; revocable, and no death has occurred"
    if klass.code in ("555", "558"):
        return "estate opened; the administrator or executor acts for the owner"
    if klass.code == "559":
        return "court order naming this owner"
    return klass.name.lower()
