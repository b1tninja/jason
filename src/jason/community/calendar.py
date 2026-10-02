"""The tax bills as a calendar of sales.

The assessor sets a new base value on a change in ownership, and that value
first appears in the bill for the next January 1. So a deed recorded in 2017
is the 2018 bill. Between sales the enrolled value may rise by the 2% factor
and no more. That bound sorts every other rise:

- A rise in the year the building was finished is construction being
  enrolled, not a sale. It precedes the developer's first conveyance.
- A rise that stays at or under the factored base from the last sale is a
  Proposition 8 restoration after a temporary decline. It can be large.
- A rise a little above that ceiling is an improvement being added.
- A rise well above the ceiling with no deed behind it is a sale the chain
  does not have.

A sale priced under the factored base shows as a decline, not a rise, and a
sale near it shows nothing at all. A parent-to-child transfer, an
interspousal deed, a trust restatement, and a transfer between affiliates
that keeps the same proportional interests are excluded from reassessment and
show nothing. Bills only start in 2013 for the unit parcels, so nothing before
the first bill can be read here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from jason.community.tax import TaxBill, enrolled_cents, reassessment_year_for

# Proposition 13 annual factor, as a percent.
_FACTOR = 102
# A rise past the factored ceiling by less than this many percent is an improvement.
_IMPROVEMENT = 110
# A fall past this many percent of the prior value is a decline.
_DECLINE = 98
# The assessor rounds to the dollar; a rise inside this many cents of the factor is the factor.
_SLACK = 100

CONSTRUCTION = "construction"
RESTORATION = "restoration"
IMPROVEMENT = "improvement"
SALE = "sale"
DECLINE = "decline"


@dataclass(frozen=True)
class CalendarEvent:
    """One bill year whose enrolled value left the 2% track."""

    year: int
    enrolled_cents: int
    prior_year: int
    prior_enrolled_cents: int
    kind: str
    number: str = ""

    @property
    def sale_year(self) -> int:
        """The year a deed would have to be recorded to land on this bill."""
        return self.year - 1


@dataclass(frozen=True)
class CalendarFinding:
    """Where the deeds and the bills disagree."""

    kind: str
    detail: str
    year: int | None = None
    number: str = ""


def enrolled_by_year(bills: tuple[TaxBill, ...] | list[TaxBill]) -> dict[int, int]:
    """The annual enrolled value per bill year. A supplemental bill has none.

    When a year has more than one bill with a value, the larger one is the
    annual bill; a supplemental carries only the difference.
    """
    found: dict[int, int] = {}
    for bill in bills:
        if bill.year is None:
            continue
        value = enrolled_cents(bill)
        if value:
            found[bill.year] = max(found.get(bill.year, 0), value)
    return found


def reassessing_years(steps: tuple[tuple[str, date | None, bool], ...]) -> dict[int, str]:
    """Bill year each reassessing deed lands on: ``{year: document number}``.

    ``steps`` are ``(number, recorded, reassesses)``. A deed that does not
    reassess, or has no date, lands nowhere. When two deeds land on one year,
    the later recording keeps the year.
    """
    found: dict[int, str] = {}
    dated = sorted(
        (recorded, number) for number, recorded, reassesses in steps if reassesses and recorded is not None
    )
    for recorded, number in dated:
        found[reassessment_year_for(recorded)] = number
    return found


def classify(
    bills: tuple[TaxBill, ...] | list[TaxBill],
    reassessing: dict[int, str] | None = None,
    *,
    first_conveyance: date | None = None,
    base: tuple[int, int] | None = None,
    restoration_years: frozenset[int] | set[int] = frozenset(),
    current_year: int | None = None,
) -> tuple[CalendarEvent, ...]:
    """Every year the enrolled value left the 2% track, and what each one is.

    A year that a reassessing deed lands on, and that rose or fell, is that
    deed's sale. A rise before or on the developer's first bill is
    construction. A rise under the factored ceiling from the last sale is a
    restoration; a little over is an improvement; well over is a sale with no
    deed. A fall with no deed is a decline.

    ``base`` is ``(year, cents)`` of the last sale before the first bill,
    usually the price on that deed, so a value reduced under Proposition 8
    on the first bill is not mistaken for the base. Without it the first
    bill is the base. ``restoration_years`` are bill years the whole
    community rose in with no deeds behind it; a rise in one of those years
    with no deed is a restoration whatever its size. ``current_year`` is the
    bill year the assessor's current instrument lands on: nothing sold after
    it, so a later rise is a restoration or an improvement, never a sale.
    When the base is not known and no sale has shown yet, a rise cannot be
    told from a restoration and is read as one.
    """
    reassessing = reassessing or {}
    enrolled = enrolled_by_year(bills)
    years = sorted(enrolled)
    if not years:
        return ()
    built = reassessment_year_for(first_conveyance) if first_conveyance is not None else None
    base_year, base_value = years[0], enrolled[years[0]]
    known = False
    if base is not None and base[0] <= years[0] and base[1] > 0:
        base_year, base_value = base
        known = True
    found: list[CalendarEvent] = []
    for prior, year in zip(years, years[1:]):
        before, after = enrolled[prior], enrolled[year]
        rose = after > _factored(before, 1) + _SLACK
        fell = after * 100 < before * _DECLINE
        number = reassessing.get(year, "")
        kind = ""
        if number and (rose or fell):
            kind = SALE
        elif number:
            continue
        elif rose and built is not None and year <= built:
            kind = CONSTRUCTION
        elif rose:
            ceiling = _factored(base_value, year - base_year)
            settled = current_year is not None and year > current_year
            if after <= ceiling + _SLACK or year in restoration_years:
                kind = RESTORATION
            elif not known:
                # The base is a reduced value; a rise past it is the restoration
                # of a base this series never showed.
                kind = RESTORATION
            elif after * 100 <= ceiling * _IMPROVEMENT or settled:
                kind = IMPROVEMENT
            else:
                kind = SALE
        elif fell:
            kind = DECLINE
        if not kind:
            continue
        found.append(CalendarEvent(year, after, prior, before, kind, number))
        if kind in (SALE, CONSTRUCTION):
            base_year, base_value, known = year, after, True
        elif kind in (RESTORATION, IMPROVEMENT) and not known:
            # The restored value is the best base in hand. It never exceeds the
            # true factored base, so the ceiling from it stays honest.
            base_year, base_value = year, after
    return tuple(found)


def findings(
    bills: tuple[TaxBill, ...] | list[TaxBill],
    reassessing: dict[int, str],
    *,
    first_conveyance: date | None = None,
    base: tuple[int, int] | None = None,
    restoration_years: frozenset[int] | set[int] = frozenset(),
    current_year: int | None = None,
) -> tuple[CalendarFinding, ...]:
    """Where a chain and its bills disagree.

    A sale-sized rise with no deed landing on it is a deed the chain lacks.
    A reassessing deed whose bill year is covered, with no rise and no fall
    that year, is either an excluded transfer, a sale at the factored base,
    or a deed on another parcel; it is reported so a person decides which.
    A deed that lands before the first bill or after the last cannot be
    checked and is not reported.
    """
    enrolled = enrolled_by_year(bills)
    years = sorted(enrolled)
    events = classify(
        bills,
        reassessing,
        first_conveyance=first_conveyance,
        base=base,
        restoration_years=restoration_years,
        current_year=current_year,
    )
    found: list[CalendarFinding] = []
    for event in events:
        if event.kind == SALE and not event.number:
            found.append(
                CalendarFinding(
                    "sale without deed",
                    f"enrolled value rose to ${event.enrolled_cents // 100:,} in the {event.year} bill, "
                    f"so a deed recorded in {event.sale_year} is missing",
                    year=event.year,
                )
            )
    landed = {event.year for event in events if event.number}
    for year, number in sorted(reassessing.items()):
        if not years or year <= years[0] or year > years[-1] or year not in enrolled or (year - 1) not in enrolled:
            continue
        if year in landed:
            continue
        found.append(
            CalendarFinding(
                "deed without reassessment",
                f"{number} lands on the {year} bill and the enrolled value kept the 2% track: "
                "an excluded transfer, a price at the factored base, or another parcel's deed",
                year=year,
                number=number,
            )
        )
    return tuple(found)


def rose_without_deed(
    bills: tuple[TaxBill, ...] | list[TaxBill],
    reassessing: dict[int, str],
) -> frozenset[int]:
    """Bill years this parcel rose past the factor with no deed landing on them.

    Counted across the community, a year most parcels rose in is a market
    restoration, not a run of unrecorded sales.
    """
    enrolled = enrolled_by_year(bills)
    years = sorted(enrolled)
    found: set[int] = set()
    for prior, year in zip(years, years[1:]):
        if year in reassessing:
            continue
        if enrolled[year] > _factored(enrolled[prior], 1) + _SLACK:
            found.add(year)
    return frozenset(found)


def community_restoration_years(
    parcels: tuple[tuple[tuple[TaxBill, ...] | list[TaxBill], dict[int, str]], ...],
    *,
    share: int = 50,
) -> frozenset[int]:
    """Bill years at least ``share`` percent of covered parcels rose in with no deed.

    ``parcels`` are ``(bills, reassessing)`` pairs. A parcel is covered for a
    year when it has that bill and the one before.
    """
    covered: dict[int, int] = {}
    rose: dict[int, int] = {}
    for bills, reassessing in parcels:
        enrolled = enrolled_by_year(bills)
        years = sorted(enrolled)
        for year in years[1:]:
            covered[year] = covered.get(year, 0) + 1
        for year in rose_without_deed(bills, reassessing):
            rose[year] = rose.get(year, 0) + 1
    return frozenset(year for year, count in rose.items() if count * 100 >= covered[year] * share)


def _factored(value: int, years: int) -> int:
    """``value`` grown by the 2% factor for ``years`` years, in integer cents."""
    grown = value
    for _ in range(max(0, years)):
        grown = (grown * _FACTOR + 50) // 100
    return grown
