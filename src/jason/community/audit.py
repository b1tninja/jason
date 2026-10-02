"""Assertions a stored deed chain has to satisfy.

A chain is a claim: these instruments, in this order, carried the fee of
this parcel from the developer to the current owner. Each check here is one
thing that claim implies and that another record can contradict.

- Order: a deed is recorded after every prior it hands off from.
- Root: the oldest deed is a pinned developer's grant.
- Phase: that grant falls inside the phase window of the parcel's building,
  and the grantor is the developer that sold that phase. A building 3 unit
  the receiver's deed still held was sold by Mystique Builders instead.
- Calendar: every deed that reassesses lands on a bill that left the 2%
  track, and every sale-sized rise has a deed landing on it.
- Price: the consideration on a deed extract is near the base value the
  next bill enrolled.

A finding is not a verdict. It names the record to read next.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from jason.community.base import Developer
from jason.community.calendar import CalendarFinding, findings, reassessing_years
from jason.community.processes import family_transfer, twins
from jason.community.recorder import (
    ChainStep,
    FiledInstrument,
    OwnershipHistory,
    developer_for,
    owner_restatement,
)
from jason.community.reports import HeldUnits, PlanBlock, PublicReport, deed_in_phase, still_held
from jason.community.tax import TaxBill, enrolled_cents, reassessment_year_for

# A deed price and the base the next bill enrolled may differ by this many percent.
PRICE_TOLERANCE = 15


@dataclass(frozen=True)
class ChainFinding:
    """One contradiction between a chain and another record."""

    check: str
    detail: str
    number: str = ""
    year: int | None = None


@dataclass(frozen=True)
class ChainAudit:
    """Every finding for one parcel, and the years its deeds land on."""

    apn: str
    steps: int
    reassessing: dict[int, str]
    findings: tuple[ChainFinding, ...]

    @property
    def clean(self) -> bool:
        return not self.findings


def step_reassesses(step: ChainStep, history: OwnershipHistory) -> bool:
    """Whether the assessor sets a new base on this deed.

    A restatement into the owner's own trust, a transfer between family or
    affiliates, and a re-recording of an earlier deed on the chain do not.
    Everything else that moves the fee does.
    """
    item = step.conveyance
    if owner_restatement(item.grantors, item.grantees):
        return False
    if family_transfer(item.grantors, item.grantees):
        return False
    filed = tuple(_filed(other.conveyance) for other in history.steps)
    for _first, later in twins(filed):
        if later.number == item.number:
            return False
    return True


def reassessing_steps(history: OwnershipHistory) -> dict[int, str]:
    """Bill year each reassessing deed on this chain lands on."""
    return reassessing_years(
        tuple(
            (step.conveyance.number, step.conveyance.recorded, step_reassesses(step, history))
            for step in history.steps
        )
    )


def audit_chain(
    history: OwnershipHistory,
    *,
    developers: tuple[Developer, ...],
    report: PublicReport | None,
    blocks: tuple[PlanBlock, ...] = (),
    held: tuple[HeldUnits, ...] = (),
    bills: tuple[TaxBill, ...] | list[TaxBill] = (),
    prices: dict[str, int] | None = None,
    restoration_years: frozenset[int] | set[int] = frozenset(),
    current_instrument: date | None = None,
) -> ChainAudit:
    """Run every check on one stored chain.

    ``report`` is the public report for the parcel's building, or None when
    the building is unknown. ``prices`` map a document number to the
    consideration read from its extract, in cents. ``current_instrument`` is
    the recording date of the assessor's current deed: no sale lands after
    the bill year it lands on, so a later rise is never read as one.
    """
    prices = prices or {}
    found: list[ChainFinding] = []
    steps = sorted(history.steps, key=_oldest_first)
    found.extend(_order(history))
    root = steps[0] if steps else None
    if root is None:
        return ChainAudit(history.apn, 0, {}, (ChainFinding("root", "no deed is stored for this parcel"),))
    found.extend(_root(root, history, developers=developers, report=report, blocks=blocks, held=held))
    reassessing = reassessing_steps(history)
    first_conveyance = root.conveyance.recorded if developer_for(_first_grantor(root), developers) else None
    base = _base(steps, history, prices, bills)
    current_year = reassessment_year_for(current_instrument) if current_instrument is not None else None
    enrolled = _enrolled(bills)
    for item in findings(
        bills,
        reassessing,
        first_conveyance=first_conveyance,
        base=base,
        restoration_years=restoration_years,
        current_year=current_year,
    ):
        if item.kind == "deed without reassessment" and _priced_at_base(item, prices, enrolled):
            continue
        found.append(_from_calendar(item))
    found.extend(_prices(steps, prices, bills))
    return ChainAudit(history.apn, len(steps), reassessing, tuple(found))


def _priced_at_base(item: CalendarFinding, prices: dict[str, int], enrolled: dict[int, int]) -> bool:
    """A deed priced within tolerance of that year's enrolled value did land; the value just did not move."""
    price = prices.get(item.number)
    value = enrolled.get(item.year or 0)
    if not price or value is None:
        return False
    return abs(value - price) * 100 <= price * PRICE_TOLERANCE


def _enrolled(bills: tuple[TaxBill, ...] | list[TaxBill]) -> dict[int, int]:
    found: dict[int, int] = {}
    for bill in bills:
        value = enrolled_cents(bill)
        if bill.year is not None and value:
            found[bill.year] = max(found.get(bill.year, 0), value)
    return found


def _order(history: OwnershipHistory) -> list[ChainFinding]:
    found: list[ChainFinding] = []
    for step in history.steps:
        later = step.conveyance.recorded
        for prior in step.priors:
            earlier = history.step(prior)
            if earlier is None:
                found.append(ChainFinding("order", f"{step.conveyance.number} hands off from {prior}, which is not on the chain", step.conveyance.number))
                continue
            before = earlier.conveyance.recorded
            if later is not None and before is not None and before >= later:
                found.append(
                    ChainFinding(
                        "order",
                        f"{step.conveyance.number} recorded {later.isoformat()} hands off from {prior} recorded {before.isoformat()}",
                        step.conveyance.number,
                    )
                )
    return found


def _root(
    root: ChainStep,
    history: OwnershipHistory,
    *,
    developers: tuple[Developer, ...],
    report: PublicReport | None,
    blocks: tuple[PlanBlock, ...],
    held: tuple[HeldUnits, ...],
) -> list[ChainFinding]:
    item = root.conveyance
    developer = developer_for(_first_grantor(root), developers)
    if developer is None:
        return [ChainFinding("root", f"the oldest deed {item.number} is from {_first_grantor(root) or 'nobody'}, not a pinned developer", item.number)]
    found: list[ChainFinding] = []
    if report is None or item.recorded is None:
        return found
    if not deed_in_phase(item.recorded, report):
        found.append(
            ChainFinding(
                "phase",
                f"{item.number} recorded {item.recorded.isoformat()} is outside phase {report.phase}, "
                f"whose report issued {report.issued.isoformat() if report.issued else 'on an unknown day'} "
                f"and first conveyed {report.first_conveyance.isoformat()}",
                item.number,
            )
        )
    expected = report.developer
    if developer.name != expected:
        allowed = any(still_held(history.apn, blocks, bulk) for bulk in held)
        if not (allowed and any(still_held(history.apn, blocks, bulk) and _sold_by(bulk, developer) for bulk in held)):
            found.append(
                ChainFinding(
                    "developer",
                    f"{item.number} is from {developer.name}; phase {report.phase} was sold by {expected}",
                    item.number,
                )
            )
    return found


def _sold_by(bulk: HeldUnits, developer: Developer) -> bool:
    """A unit still held on the receiver's deed was sold by the builder who took it."""
    return developer.name == "Mystique Builders"


def _base(
    steps: list[ChainStep],
    history: OwnershipHistory,
    prices: dict[str, int],
    bills: tuple[TaxBill, ...] | list[TaxBill],
) -> tuple[int, int] | None:
    """The last priced sale before the first bill, as ``(bill year, cents)``."""
    years = sorted({bill.year for bill in bills if bill.year is not None and enrolled_cents(bill)})
    if not years:
        return None
    first = years[0]
    best: tuple[int, int] | None = None
    for step in steps:
        item = step.conveyance
        if item.recorded is None or not step_reassesses(step, history):
            continue
        year = reassessment_year_for(item.recorded)
        price = prices.get(item.number)
        if year <= first and price:
            best = (year, price)
    return best


def _prices(
    steps: list[ChainStep],
    prices: dict[str, int],
    bills: tuple[TaxBill, ...] | list[TaxBill],
) -> list[ChainFinding]:
    enrolled = _enrolled(bills)
    found: list[ChainFinding] = []
    for step in steps:
        item = step.conveyance
        price = prices.get(item.number)
        if not price or item.recorded is None:
            continue
        year = reassessment_year_for(item.recorded)
        value = enrolled.get(year)
        if value is None:
            continue
        if abs(value - price) * 100 > price * PRICE_TOLERANCE:
            found.append(
                ChainFinding(
                    "price",
                    f"{item.number} declares ${price // 100:,} and the {year} bill enrolled ${value // 100:,}",
                    item.number,
                    year,
                )
            )
    return found


def _from_calendar(item: CalendarFinding) -> ChainFinding:
    return ChainFinding("calendar", f"{item.kind}: {item.detail}", item.number, item.year)


def _first_grantor(step: ChainStep) -> str:
    for name in step.conveyance.grantors:
        if name.strip():
            return name
    return ""


def _oldest_first(step: ChainStep) -> tuple[date, str]:
    return (step.conveyance.recorded or date.min, step.conveyance.number)


def _filed(item) -> FiledInstrument:
    return FiledInstrument(item.number, item.recorded, "fee", item.grantors, item.grantees, item.cross_references)
