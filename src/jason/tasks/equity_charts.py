"""A spreadsheet that estimates each unit's value, equity, and appreciation.

Comps here are the community's own sales: the trailing twelve-month median
price across the community, and the same per building where a building had
sales. Three references are given for every unit, and none is an appraisal:

- the recent comps: the trailing median now, for the building when it has
  three or more sales in the window, else for the community;
- the indexed estimate: the unit's own last price carried forward by the
  ratio of the community median now to the community median when it sold;
- the assessor's current enrolled value, which trails the market by the
  Proposition 13 factor and is the floor a sale below it would reset.

A fourth reference adjusts for size. The assessor's residential
characteristics (living area, bedrooms, baths, year built) ride beside every
sale, so the market is also read in dollars per square foot and by bedroom
count, and a unit's size-adjusted estimate is its measured area at the
trailing median price per square foot.

Appreciation is the recent-comps estimate against the unit's last price,
in dollars, percent, and per year. Equity in the sense of value above a
loan cannot be read from public records, since a deed of trust does not
state the balance; the appreciation is the part the records support.

The Trend tab is the scatter of sale prices by building over time with the
moving averages drawn through it. The Unit lookup tab is the drill-down:
pick an address and the tab fills with that unit's figures, its sales, and
charts of its prices and its indexed value path against the community and
building medians. The charts are Sheets' own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Any

from jason.community.characteristics import FloorPlan, UnitCharacteristics, classify_plan
from jason.community.parcel_history import ParcelHistory
from jason.community.tax import parcel_number
from jason.tasks.unit_charts import _chart

EQUITY_TABS = (
    "Sales", "Market index", "Trend", "Unit values", "Building values", "By size", "By plan", "Unit paths",
    "Unit lookup", "Charts",
)
WINDOW_MONTHS = 12
BUILDING_MINIMUM = 3
# A building's comps widen to these windows, in turn, until it has enough sales.
BUILDING_WINDOWS = (12, 24, 36)
RECENT_MONTHS = 36
RECENT_YEARS = 5

# One color per building, shared by its sale points and its moving-average line.
BUILDING_COLORS: dict[int, tuple[float, float, float]] = {
    1: (0.12, 0.47, 0.71), 2: (1.0, 0.5, 0.05), 3: (0.17, 0.63, 0.17), 4: (0.84, 0.15, 0.16),
    5: (0.58, 0.4, 0.74), 6: (0.55, 0.34, 0.29), 7: (0.89, 0.47, 0.76), 8: (0.5, 0.5, 0.5),
}
COMMUNITY_COLOR = (0.1, 0.1, 0.1)
COMMUNITY_MEAN_COLOR = (0.45, 0.45, 0.45)


@dataclass
class EquityChartsReport:
    spreadsheet_id: str
    url: str
    counts: tuple[tuple[str, int], ...]
    charts: int

    def summary(self) -> str:
        tabs = " ".join(f"{name}={count}" for name, count in self.counts)
        return f"spreadsheet={self.spreadsheet_id} charts={self.charts} {tabs} url={self.url}"


@dataclass(frozen=True)
class Sale:
    recorded: date
    building: int
    address: str
    apn: str
    process: str
    price: int
    source: str
    living_sqft: int | None = None
    bedrooms: int | None = None
    baths: float | None = None
    year_built: int | None = None
    plan: str = ""

    @property
    def month(self) -> str:
        return f"{self.recorded.year}-{self.recorded.month:02d}"

    @property
    def per_sqft(self) -> int | None:
        """Cents per square foot of living area, or None without an area."""
        if not self.living_sqft:
            return None
        return int(round(self.price / self.living_sqft))


def _month_ordinal(year: int, month: int) -> int:
    return year * 12 + month - 1


def _months(first: date, last: date) -> list[str]:
    found: list[str] = []
    for ordinal in range(_month_ordinal(first.year, first.month), _month_ordinal(last.year, last.month) + 1):
        found.append(f"{ordinal // 12}-{ordinal % 12 + 1:02d}")
    return found


def _digits(value: str) -> str:
    return "".join(ch for ch in str(value) if ch.isdigit())


def unit_plan(item: ParcelHistory, unit: UnitCharacteristics | None, plans: tuple[FloorPlan, ...]) -> FloorPlan | None:
    """The developer's plan nearest the assessor's measured area, for the building's developer."""
    if unit is None:
        return None
    return classify_plan(unit, plans, item.developer)


def sales_of(
    histories: tuple[ParcelHistory, ...],
    characteristics: dict[str, UnitCharacteristics] | None = None,
    plans: tuple[FloorPlan, ...] = (),
) -> tuple[Sale, ...]:
    found: list[Sale] = []
    for item in histories:
        if item.association or not item.building:
            continue
        unit = (characteristics or {}).get(_digits(item.apn))
        plan = unit_plan(item, unit, plans)
        for step in item.sales:
            amount, source = step.price_or_base
            if amount and step.recorded:
                found.append(Sale(
                    step.recorded, item.building, item.address, item.apn, step.process, amount, source,
                    unit.living_sqft if unit else None, unit.bedrooms if unit else None, unit.baths if unit else None,
                    unit.year_built if unit else None, plan.name if plan else "",
                ))
    return tuple(sorted(found, key=lambda sale: (sale.recorded, sale.apn)))


def trailing(
    sales: tuple[Sale, ...],
    month: str,
    *,
    building: int | None = None,
    months: int = WINDOW_MONTHS,
    bedrooms: int | None = None,
    per_sqft: bool = False,
) -> tuple[int, int | None, int | None]:
    """Sales count, median, and mean in the ``months`` ending at ``month``, in cents.

    ``per_sqft`` reads dollars per square foot instead of price, over the
    sales that have a measured area. ``bedrooms`` keeps one bedroom count.
    """
    year, mon = int(month[:4]), int(month[5:7])
    end = _month_ordinal(year, mon)
    start = end - months + 1
    values: list[int] = []
    for sale in sales:
        if not start <= _month_ordinal(sale.recorded.year, sale.recorded.month) <= end:
            continue
        if building is not None and sale.building != building:
            continue
        if bedrooms is not None and sale.bedrooms != bedrooms:
            continue
        value = sale.per_sqft if per_sqft else sale.price
        if value:
            values.append(value)
    if not values:
        return 0, None, None
    return len(values), int(median(values)), int(sum(values) / len(values))


def bedroom_counts(sales: tuple[Sale, ...]) -> tuple[int, ...]:
    return tuple(sorted({sale.bedrooms for sale in sales if sale.bedrooms}))


def market_index(sales: tuple[Sale, ...], buildings: tuple[int, ...], *, today: date | None = None) -> list[list[Any]]:
    """One row per month: community trailing count, median, mean, index, each building's trailing median,
    then the same market in dollars per square foot and by bedroom count."""
    today = today or date.today()
    beds = bedroom_counts(sales)
    header = ["Month", "Community sales (12 mo)", "Community median (12 mo)", "Community mean (12 mo)", "Index (first month = 100)"]
    header += [f"Building {number} median (12 mo)" for number in buildings]
    header += ["Community $/sq ft median (12 mo)"]
    header += [f"Building {number} $/sq ft (12 mo)" for number in buildings]
    header += [f"{count} bedroom median (12 mo)" for count in beds]
    header += [f"{count} bedroom $/sq ft (12 mo)" for count in beds]
    rows: list[list[Any]] = [header]
    if not sales:
        return rows
    base = None
    for month in _months(sales[0].recorded, today):
        count, med, mean = trailing(sales, month)
        if med is not None and base is None:
            base = med
        row: list[Any] = [
            "'" + month, count,
            round(med / 100, 2) if med is not None else "",
            round(mean / 100, 2) if mean is not None else "",
            round(med / base * 100, 1) if med is not None and base else "",
        ]
        for number in buildings:
            b_count, b_med, _ = trailing(sales, month, building=number)
            row.append(round(b_med / 100, 2) if b_med is not None and b_count >= BUILDING_MINIMUM else "")
        _count, sq_med, _ = trailing(sales, month, per_sqft=True)
        row.append(round(sq_med / 100, 2) if sq_med is not None else "")
        for number in buildings:
            b_count, b_med, _ = trailing(sales, month, building=number, per_sqft=True)
            row.append(round(b_med / 100, 2) if b_med is not None and b_count >= BUILDING_MINIMUM else "")
        for count_ in beds:
            _c, bed_med, _ = trailing(sales, month, bedrooms=count_)
            row.append(round(bed_med / 100, 2) if bed_med is not None else "")
        for count_ in beds:
            _c, bed_med, _ = trailing(sales, month, bedrooms=count_, per_sqft=True)
            row.append(round(bed_med / 100, 2) if bed_med is not None else "")
        rows.append(row)
    return rows


def building_comps(sales: tuple[Sale, ...], month: str, building: int | None, *, per_sqft: bool = False) -> tuple[int | None, str]:
    """The building's trailing median over the narrowest window with enough sales, and the basis used.

    Falls back to the community's twelve-month median, and says so.
    """
    if building is not None:
        for months in BUILDING_WINDOWS:
            count, med, _ = trailing(sales, month, building=building, months=months, per_sqft=per_sqft)
            if med is not None and count >= BUILDING_MINIMUM:
                return med, f"building {building}, {months} months, {count} sales"
    count, med, _ = trailing(sales, month, per_sqft=per_sqft)
    if med is not None:
        return med, f"community, {WINDOW_MONTHS} months, {count} sales"
    med = _median_at(sales, month, per_sqft=per_sqft)
    return med, "community, last month with sales" if med is not None else "none"


def _median_at(sales: tuple[Sale, ...], month: str, *, per_sqft: bool = False) -> int | None:
    """The community trailing median for ``month``, or the nearest earlier month that has one."""
    year, mon = int(month[:4]), int(month[5:7])
    ordinal = _month_ordinal(year, mon)
    first = _month_ordinal(sales[0].recorded.year, sales[0].recorded.month) if sales else ordinal
    while ordinal >= first:
        _count, med, _mean = trailing(sales, f"{ordinal // 12}-{ordinal % 12 + 1:02d}", per_sqft=per_sqft)
        if med is not None:
            return med
        ordinal -= 1
    return None


def trend_rows(sales: tuple[Sale, ...], buildings: tuple[int, ...], *, today: date | None = None) -> list[list[Any]]:
    """Every sale and every month on one dated axis, with the moving averages on every row.

    A sale row carries its price in its building's column; a month row only
    carries the averages, so the average lines run smoothly through months
    without sales. The building medians need three sales in the window.
    """
    today = today or date.today()
    header = ["Date", "Kind", "Address", "Building", "Price", "$ per sq ft",
              "Community median (12 mo)", "Community mean (12 mo)", "Community $/sq ft median (12 mo)"]
    header += [f"Building {number} median (12 mo)" for number in buildings]
    header += [f"Building {number} sale" for number in buildings]
    header += [f"Building {number} $/sq ft" for number in buildings]
    rows: list[list[Any]] = [header]
    if not sales:
        return rows
    entries: list[tuple[date, int, Sale | None]] = []
    for month in _months(sales[0].recorded, today):
        entries.append((date(int(month[:4]), int(month[5:7]), 1), 0, None))
    for sale in sales:
        entries.append((sale.recorded, 1, sale))
    entries.sort(key=lambda entry: (entry[0], entry[1], entry[2].apn if entry[2] else ""))
    for day, _order, sale in entries:
        month = f"{day.year}-{day.month:02d}"
        _c, med, mean = trailing(sales, month)
        _c, sq_med, _ = trailing(sales, month, per_sqft=True)
        row: list[Any] = [
            day.isoformat(), "sale" if sale else "month", sale.address if sale else "", sale.building if sale else "",
            round(sale.price / 100, 2) if sale else "", round(sale.per_sqft / 100, 2) if sale and sale.per_sqft else "",
            round(med / 100, 2) if med is not None else "",
            round(mean / 100, 2) if mean is not None else "",
            round(sq_med / 100, 2) if sq_med is not None else "",
        ]
        for number in buildings:
            b_count, b_med, _ = trailing(sales, month, building=number)
            row.append(round(b_med / 100, 2) if b_med is not None and b_count >= BUILDING_MINIMUM else "")
        for number in buildings:
            row.append(round(sale.price / 100, 2) if sale and sale.building == number else "")
        for number in buildings:
            row.append(round(sale.per_sqft / 100, 2) if sale and sale.building == number and sale.per_sqft else "")
        rows.append(row)
    return rows


UNIT_VALUE_HEADER = [
    "Building", "Address", "Parcel", "Owners", "Last sale", "Years held", "Last price", "Price source",
    "Assessed value (latest bill)", "Community median now", "Building median now",
    "Estimate (indexed from last price)", "Estimate (recent comps)", "Appreciation $", "Appreciation %",
    "Appreciation % per year", "Rank in building", "Percentile in community", "Sales", "First price", "Since first sale %",
    "Community median when bought", "Comps basis",
    "Bedrooms", "Baths", "Living sq ft", "Year built", "Plan", "Last $/sq ft",
    "Community $/sq ft now (12 mo)", "Building $/sq ft now", "Estimate (size-adjusted comps)",
    "Size-adjusted appreciation %", "Size comps basis",
]


def unit_values(
    histories: tuple[ParcelHistory, ...],
    *,
    today: date | None = None,
    characteristics: dict[str, UnitCharacteristics] | None = None,
    plans: tuple[FloorPlan, ...] = (),
) -> list[list[Any]]:
    today = today or date.today()
    sales = sales_of(histories, characteristics, plans)
    now = f"{today.year}-{today.month:02d}"
    _count, community_now, _mean = trailing(sales, now)
    if community_now is None:
        community_now = _median_at(sales, now)
    _count, sq_now, _ = trailing(sales, now, per_sqft=True)
    if sq_now is None:
        sq_now = _median_at(sales, now, per_sqft=True)
    rows: list[list[Any]] = [list(UNIT_VALUE_HEADER)]
    body: list[list[Any]] = []
    for item in histories:
        if item.association or not item.steps:
            continue
        last = item.last_sale
        if last is None or last.recorded is None:
            continue
        unit = (characteristics or {}).get(_digits(item.apn))
        plan = unit_plan(item, unit, plans)
        last_price, source = last.price_or_base
        b_count, building_now, _ = trailing(sales, now, building=item.building) if item.building else (0, None, None)
        comps_now, comps_label = building_comps(sales, now, item.building)
        bought = _median_at(sales, f"{last.recorded.year}-{last.recorded.month:02d}") if last_price else None
        indexed = int(last_price * community_now / bought) if last_price and bought and community_now else None
        estimate = comps_now
        years = round((today - last.recorded).days / 365.25, 1)
        appreciation = (estimate - last_price) if estimate and last_price else None
        pct = (appreciation / last_price * 100) if appreciation is not None and last_price else None
        annual = ((estimate / last_price) ** (1 / years) - 1) * 100 if estimate and last_price and years >= 1 else None
        first = item.steps[0]
        first_price, _ = first.price_or_base
        since_first = ((estimate - first_price) / first_price * 100) if estimate and first_price else None
        assessed = _latest_enrolled(item)
        sqft = unit.living_sqft if unit else None
        last_sq = int(round(last_price / sqft)) if last_price and sqft else None
        sq_comps, sq_label = building_comps(sales, now, item.building, per_sqft=True) if sqft else (None, "no measured area")
        b_sq_count, b_sq_now, _ = trailing(sales, now, building=item.building, per_sqft=True) if item.building else (0, None, None)
        size_estimate = int(sq_comps * sqft) if sq_comps and sqft else None
        size_pct = ((size_estimate - last_price) / last_price * 100) if size_estimate and last_price else None
        body.append([
            item.building or "", item.address, parcel_number(item.apn), ", ".join(item.owners),
            last.recorded.isoformat(), years,
            round(last_price / 100, 2) if last_price else "", source,
            round(assessed / 100, 2) if assessed else "",
            round(community_now / 100, 2) if community_now else "",
            round(building_now / 100, 2) if building_now and b_count >= BUILDING_MINIMUM else "",
            round(indexed / 100, 2) if indexed else "",
            round(estimate / 100, 2) if estimate else "",
            round(appreciation / 100, 2) if appreciation is not None else "",
            round(pct, 1) if pct is not None else "",
            round(annual, 1) if annual is not None else "",
            "", "",
            len(item.sales),
            round(first_price / 100, 2) if first_price else "",
            round(since_first, 1) if since_first is not None else "",
            round(bought / 100, 2) if bought else "",
            comps_label,
            unit.bedrooms if unit and unit.bedrooms else "",
            unit.baths if unit and unit.baths else "",
            sqft or "",
            unit.year_built if unit and unit.year_built else "",
            plan.name if plan else "",
            round(last_sq / 100, 2) if last_sq else "",
            round(sq_now / 100, 2) if sq_now else "",
            round(b_sq_now / 100, 2) if b_sq_now and b_sq_count >= BUILDING_MINIMUM else "",
            round(size_estimate / 100, 2) if size_estimate else "",
            round(size_pct, 1) if size_pct is not None else "",
            sq_label,
        ])
    _rank(body)
    body.sort(key=lambda row: (row[0] or 0, row[1]))
    rows.extend(body)
    return rows


def _rank(body: list[list[Any]]) -> None:
    """Rank in building and percentile in community by appreciation percent, highest first."""
    scored = [row for row in body if row[14] != ""]
    by_building: dict[Any, list[list[Any]]] = {}
    for row in scored:
        by_building.setdefault(row[0], []).append(row)
    for rows in by_building.values():
        for index, row in enumerate(sorted(rows, key=lambda r: -r[14])):
            row[16] = index + 1
    ordered = sorted(scored, key=lambda r: r[14])
    total = len(ordered)
    for index, row in enumerate(ordered):
        row[17] = round(index / (total - 1) * 100) if total > 1 else 100


def _latest_enrolled(item: ParcelHistory) -> int | None:
    last = None
    for event in item.events:
        last = event.enrolled_cents
    if last:
        return last
    for step in reversed(item.steps):
        if step.enrolled_cents:
            return step.enrolled_cents
    return None


def building_values(values: list[list[Any]], index_rows: list[list[Any]]) -> list[list[Any]]:
    header = [
        "Building", "Units valued", "Median last price", "Building median now (12 mo)", "Mean estimate", "Sum of estimates",
        "Mean appreciation %", "Mean appreciation % per year", "Units above their last price",
        "Mean living sq ft", "Median last $/sq ft", "Building $/sq ft now (12 mo)", "Mean size-adjusted estimate",
    ]
    rows: list[list[Any]] = [header]
    groups: dict[Any, list[list[Any]]] = {}
    for row in values[1:]:
        groups.setdefault(row[0], []).append(row)
    latest = index_rows[-1] if len(index_rows) > 1 else []

    def latest_of(name: str) -> Any:
        if latest and name in index_rows[0]:
            found = latest[index_rows[0].index(name)]
            return found if found not in (None, "") else ""
        return ""

    for building in sorted(groups, key=lambda b: (b == "", b)):
        rows_ = groups[building]
        last_prices = [r[6] for r in rows_ if r[6] != ""]
        estimates = [r[12] for r in rows_ if r[12] != ""]
        pcts = [r[14] for r in rows_ if r[14] != ""]
        annual = [r[15] for r in rows_ if r[15] != ""]
        areas = [r[25] for r in rows_ if r[25] != ""]
        last_sq = [r[28] for r in rows_ if r[28] != ""]
        size_estimates = [r[31] for r in rows_ if r[31] != ""]
        rows.append([
            building, len(rows_),
            round(median(last_prices), 2) if last_prices else "",
            latest_of(f"Building {building} median (12 mo)"),
            round(sum(estimates) / len(estimates), 2) if estimates else "",
            round(sum(estimates), 2) if estimates else "",
            round(sum(pcts) / len(pcts), 1) if pcts else "",
            round(sum(annual) / len(annual), 1) if annual else "",
            sum(1 for r in rows_ if r[13] != "" and r[13] > 0),
            round(sum(areas) / len(areas)) if areas else "",
            round(median(last_sq), 2) if last_sq else "",
            latest_of(f"Building {building} $/sq ft (12 mo)"),
            round(sum(size_estimates) / len(size_estimates), 2) if size_estimates else "",
        ])
    return rows


def sales_rows(sales: tuple[Sale, ...]) -> list[list[Any]]:
    rows: list[list[Any]] = [[
        "Recorded", "Month", "Building", "Address", "Parcel", "Process", "Price", "Price source",
        "Bedrooms", "Baths", "Living sq ft", "Year built", "Plan", "$ per sq ft",
    ]]
    for sale in sales:
        rows.append([
            sale.recorded.isoformat(), "'" + sale.month, sale.building, sale.address, parcel_number(sale.apn), sale.process,
            round(sale.price / 100, 2), sale.source,
            sale.bedrooms or "", sale.baths or "", sale.living_sqft or "", sale.year_built or "", sale.plan,
            round(sale.per_sqft / 100, 2) if sale.per_sqft else "",
        ])
    return rows


def by_size_rows(sales: tuple[Sale, ...], *, today: date | None = None) -> list[list[Any]]:
    """One row per sale with a measured area, for price against living area: a series per bedroom count,
    and one for the last five years."""
    today = today or date.today()
    beds = bedroom_counts(sales)
    header = ["Living sq ft", "Price", "$ per sq ft", "Recorded", "Address", "Building", "Bedrooms", "Plan", "Year built"]
    header += [f"{count} bedrooms" for count in beds] + [f"Last {RECENT_YEARS} years"]
    rows: list[list[Any]] = [header]
    cutoff = date(today.year - RECENT_YEARS, today.month, 1)
    for sale in sorted((s for s in sales if s.living_sqft), key=lambda s: (s.living_sqft or 0, s.recorded)):
        row: list[Any] = [
            sale.living_sqft, round(sale.price / 100, 2), round(sale.per_sqft / 100, 2) if sale.per_sqft else "",
            sale.recorded.isoformat(), sale.address, sale.building, sale.bedrooms or "", sale.plan, sale.year_built or "",
        ]
        for count in beds:
            row.append(round(sale.price / 100, 2) if sale.bedrooms == count else "")
        row.append(round(sale.price / 100, 2) if sale.recorded >= cutoff else "")
        rows.append(row)
    return rows


def by_plan_rows(
    sales: tuple[Sale, ...],
    values: list[list[Any]],
    plans: tuple[FloorPlan, ...],
    *,
    today: date | None = None,
) -> list[list[Any]]:
    """One row per plan, with the unclassified units grouped by bedroom count."""
    today = today or date.today()
    now = f"{today.year}-{today.month:02d}"
    header = [
        "Plan", "Developer", "Bedrooms", "Baths", "Stated sq ft", "Source", "Units", "Mean measured sq ft", "Sales",
        "Median price", "Median $/sq ft", f"Median price (last {RECENT_MONTHS} mo)", f"Median $/sq ft (last {RECENT_MONTHS} mo)",
        "Latest sale", "Mean appreciation %",
    ]
    rows: list[list[Any]] = [header]
    by_plan: dict[str, FloorPlan] = {plan.name: plan for plan in plans}
    labels: list[str] = [plan.name for plan in plans]

    def label_of(plan: str, bedrooms: Any, sqft: Any) -> str:
        """The plan, else the as-built type the assessor measured, so unmatched units still group."""
        if plan:
            return plan
        if bedrooms and sqft:
            return f"{bedrooms} bedrooms, {sqft} sq ft, no plan matched"
        return f"{bedrooms} bedrooms, no plan matched" if bedrooms else "no characteristics"

    units: dict[str, list[list[Any]]] = {}
    for row in values[1:]:
        units.setdefault(label_of(row[27], row[23], row[25]), []).append(row)
    sold: dict[str, list[Sale]] = {}
    for sale in sales:
        sold.setdefault(label_of(sale.plan, sale.bedrooms, sale.living_sqft), []).append(sale)
    for label in units:
        if label not in labels:
            labels.append(label)
    for label in sold:
        if label not in labels:
            labels.append(label)
    cutoff = _month_ordinal(int(now[:4]), int(now[5:7])) - RECENT_MONTHS + 1
    for label in labels:
        plan = by_plan.get(label)
        unit_rows = units.get(label, [])
        plan_sales = sold.get(label, [])
        if not unit_rows and not plan_sales:
            continue
        recent = [s for s in plan_sales if _month_ordinal(s.recorded.year, s.recorded.month) >= cutoff]
        prices = [s.price for s in plan_sales]
        per_sq = [s.per_sqft for s in plan_sales if s.per_sqft]
        recent_prices = [s.price for s in recent]
        recent_sq = [s.per_sqft for s in recent if s.per_sqft]
        areas = [r[25] for r in unit_rows if r[25] != ""]
        pcts = [r[14] for r in unit_rows if r[14] != ""]
        rows.append([
            label,
            plan.developer if plan else "",
            plan.bedrooms if plan else (unit_rows[0][23] if unit_rows and unit_rows[0][23] != "" else ""),
            plan.baths if plan and plan.baths else "",
            plan.living_sqft if plan else "",
            plan.source if plan else "",
            len(unit_rows),
            round(sum(areas) / len(areas)) if areas else "",
            len(plan_sales),
            round(median(prices) / 100, 2) if prices else "",
            round(median(per_sq) / 100, 2) if per_sq else "",
            round(median(recent_prices) / 100, 2) if recent_prices else "",
            round(median(recent_sq) / 100, 2) if recent_sq else "",
            max(s.recorded for s in plan_sales).isoformat() if plan_sales else "",
            round(sum(pcts) / len(pcts), 1) if pcts else "",
        ])
    return rows


def unit_paths(sales: tuple[Sale, ...], values: list[list[Any]], *, today: date | None = None) -> list[list[Any]]:
    """Each unit's indexed value month by month: its last price carried by the community median.

    The path is blank before the unit's first sale and resets at each sale.
    It is the per-unit moving average the records support, since one unit
    sells too rarely to average its own sales.
    """
    today = today or date.today()
    addresses = [row[1] for row in values[1:]]
    rows: list[list[Any]] = [["Month"] + addresses]
    if not sales:
        return rows
    by_address: dict[str, list[Sale]] = {}
    for sale in sales:
        by_address.setdefault(sale.address, []).append(sale)
    medians: dict[str, int | None] = {}

    def median_of(month: str) -> int | None:
        if month not in medians:
            medians[month] = _median_at(sales, month)
        return medians[month]

    for month in _months(sales[0].recorded, today):
        ordinal = _month_ordinal(int(month[:4]), int(month[5:7]))
        now = median_of(month)
        row: list[Any] = ["'" + month]
        for address in addresses:
            last = None
            for sale in by_address.get(address, []):
                if _month_ordinal(sale.recorded.year, sale.recorded.month) <= ordinal:
                    last = sale
            if last is None or now is None:
                row.append("")
                continue
            bought = median_of(last.month)
            row.append(round(last.price * now / bought / 100, 2) if bought else "")
        rows.append(row)
    return rows


LOOKUP_LABELS = [
    ("Building", 0), ("Parcel", 2), ("Owners", 3), ("Last sale", 4), ("Years held", 5), ("Last price", 6), ("Price source", 7),
    ("Assessed value (latest bill)", 8), ("Community median now", 9), ("Building median now", 10),
    ("Estimate, indexed from last price", 11), ("Estimate, recent comps", 12), ("Appreciation $", 13), ("Appreciation %", 14),
    ("Appreciation % per year", 15), ("Rank in building", 16), ("Percentile in community", 17), ("Sales on record", 18),
    ("First price", 19), ("Since first sale %", 20), ("Community median when bought", 21), ("Comps basis", 22),
    ("Bedrooms", 23), ("Baths", 24), ("Living sq ft", 25), ("Year built", 26), ("Plan", 27), ("Last $/sq ft", 28),
    ("Community $/sq ft now", 29), ("Building $/sq ft now", 30), ("Estimate, size-adjusted comps", 31),
    ("Size-adjusted appreciation %", 32), ("Size comps basis", 33),
]
# The figures run from row 3 down the label list; the sales history starts below them.
LOOKUP_HISTORY_ROW = 2 + len(LOOKUP_LABELS) + 2  # zero-based index of the "Sales history" header row
LOOKUP_MONTH_COLUMN = 14  # column O: the monthly table of medians, the unit's path, and its sales


def lookup_rows(first_address: str, months: int = 0) -> list[list[Any]]:
    """The Unit lookup tab: a picked address, its figures by formula, its sales, a chart table, and a month table."""
    def cell(column: int) -> str:
        return f"=IFERROR(INDEX('Unit values'!{_col(column)}:{_col(column)}, MATCH($B$1, 'Unit values'!$B:$B, 0)), \"\")"

    rows: list[list[Any]] = [["Unit", first_address, "", "Pick an address in B1. Everything below follows it."]]
    rows.append([])
    for label, column in LOOKUP_LABELS:
        rows.append([label, cell(column)])
    while len(rows) < LOOKUP_HISTORY_ROW:
        rows.append([])
    history = LOOKUP_HISTORY_ROW + 1  # one-based row of the first spill row
    header = ["Sales history"] + [""] * 8 + ["Month", "Unit price", "Community median (12 mo)", "Building median (12 mo)", ""]
    header += ["Month", "Community median (12 mo)", "Building median (12 mo)", "This unit, indexed value", "This unit, sale"]
    rows.append(header)
    first = history + 1
    rows.append([
        f"=IFERROR(FILTER(Sales!A:H, Sales!D:D=$B$1), \"\")", "", "", "", "", "", "", "", "",
        f"=IF(A{first}=\"\", \"\", B{first})",
        f"=IF(A{first}=\"\", \"\", G{first})",
        f"=IFERROR(IF(A{first}=\"\", \"\", VLOOKUP(B{first}, 'Market index'!A:C, 3, FALSE)), \"\")",
        f"=IFERROR(IF(A{first}=\"\", \"\", INDEX('Market index'!A:ZZ, MATCH(B{first}, 'Market index'!A:A, 0), MATCH(\"Building \"&$B$3&\" median (12 mo)\", 'Market index'!1:1, 0))), \"\")",
        "",
    ] + _month_formulas(first, 2))
    for offset in range(1, max(14, months)):
        row = first + offset
        line: list[Any] = ["", "", "", "", "", "", "", "", ""]
        if offset < 14:
            line += [
                f"=IF(A{row}=\"\", \"\", B{row})",
                f"=IF(A{row}=\"\", \"\", G{row})",
                f"=IFERROR(IF(A{row}=\"\", \"\", VLOOKUP(B{row}, 'Market index'!A:C, 3, FALSE)), \"\")",
                f"=IFERROR(IF(A{row}=\"\", \"\", INDEX('Market index'!A:ZZ, MATCH(B{row}, 'Market index'!A:A, 0), MATCH(\"Building \"&$B$3&\" median (12 mo)\", 'Market index'!1:1, 0))), \"\")",
                "",
            ]
        else:
            line += ["", "", "", "", ""]
        if offset < months:
            line += _month_formulas(row, 2 + offset)
        rows.append(line)
    return rows


def _month_formulas(row: int, index_row: int) -> list[str]:
    """The month table's formulas for lookup row ``row`` reading Market index row ``index_row``."""
    month = f"O{row}"
    building = f"INDEX('Market index'!{index_row}:{index_row}, MATCH(\"Building \"&$B$3&\" median (12 mo)\", 'Market index'!$1:$1, 0))"
    path = f"INDEX('Unit paths'!{index_row}:{index_row}, MATCH($B$1, 'Unit paths'!$1:$1, 0))"
    sale = f"SUMIFS(Sales!$G:$G, Sales!$D:$D, $B$1, Sales!$B:$B, {month})"
    return [
        f"=IF('Market index'!A{index_row}=\"\", \"\", 'Market index'!A{index_row})",
        f"=IF({month}=\"\", \"\", 'Market index'!C{index_row})",
        f"=IFERROR(IF({month}=\"\", \"\", IF({building}=\"\", \"\", {building})), \"\")",
        f"=IFERROR(IF({month}=\"\", \"\", IF({path}=\"\", \"\", {path})), \"\")",
        f"=IFERROR(IF({month}=\"\", \"\", IF({sale}=0, \"\", {sale})), \"\")",
    ]


def _col(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def equity_chart_tabs(
    histories: tuple[ParcelHistory, ...],
    *,
    today: date | None = None,
    characteristics: dict[str, UnitCharacteristics] | None = None,
    plans: tuple[FloorPlan, ...] = (),
) -> dict[str, list[list[Any]]]:
    sales = sales_of(histories, characteristics, plans)
    buildings = tuple(sorted({sale.building for sale in sales}))
    index_rows = market_index(sales, buildings, today=today)
    values = unit_values(histories, today=today, characteristics=characteristics, plans=plans)
    first_address = values[1][1] if len(values) > 1 else ""
    return {
        "Sales": sales_rows(sales),
        "Market index": index_rows,
        "Trend": trend_rows(sales, buildings, today=today),
        "Unit values": values,
        "Building values": building_values(values, index_rows),
        "By size": by_size_rows(sales, today=today),
        "By plan": by_plan_rows(sales, values, plans, today=today),
        "Unit paths": unit_paths(sales, values, today=today),
        "Unit lookup": lookup_rows(first_address, len(index_rows) - 1),
        "Charts": [["Charts of value and appreciation, drawn from the tabs beside this one. The Unit lookup tab has its own charts for one unit."]],
    }


def _rgb(color: tuple[float, float, float]) -> dict[str, Any]:
    return {"rgbColor": {"red": color[0], "green": color[1], "blue": color[2]}}


def _points(color: tuple[float, float, float], size: int = 5) -> dict[str, Any]:
    return {"colorStyle": _rgb(color), "pointStyle": {"size": size, "shape": "CIRCLE"}}


def _line(color: tuple[float, float, float], width: int = 2, kind: str = "SOLID") -> dict[str, Any]:
    return {"colorStyle": _rgb(color), "lineStyle": {"type": kind, "width": width}, "pointStyle": {"size": 1, "shape": "CIRCLE"}}


def _styled(request: dict[str, Any], styles: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply one style per series, in order."""
    for series, style in zip(request["addChart"]["chart"]["spec"]["basicChart"]["series"], styles):
        series.update(style)
    return request


def _columns(header: list[str] | None, prefix: str, suffix: str) -> list[tuple[int, int]]:
    """(column, building) for every header shaped ``prefix N suffix``."""
    found: list[tuple[int, int]] = []
    for index, name in enumerate(header or []):
        if name.startswith(prefix) and name.endswith(suffix):
            middle = name[len(prefix):len(name) - len(suffix)].strip()
            if middle.isdigit():
                found.append((index, int(middle)))
    return found


def equity_chart_requests(
    ids: dict[str, int],
    sizes: dict[str, int],
    widths: dict[str, int],
    headers: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    headers = headers or {}
    requests: list[dict[str, Any]] = []
    charts = ids.get("Charts")
    lookup = ids.get("Unit lookup")
    if charts is not None:
        top = 2
        if "Market index" in ids:
            header = headers.get("Market index")
            n = sizes["Market index"]
            medians = _columns(header, "Building", "median (12 mo)") if header else [(col, 0) for col in range(5, widths.get("Market index", 5))]
            requests.append(_styled(_chart(
                "Trailing 12-month median sale price: community and buildings", "LINE", ids["Market index"], n,
                domain_col=0, series_cols=(2,) + tuple(col for col, _ in medians), x_title="Month", y_title="Dollars", anchor=(charts, top),
            ), [_line(COMMUNITY_COLOR, 3)] + [_line(BUILDING_COLORS.get(b, COMMUNITY_MEAN_COLOR)) for _, b in medians]))
            top += 22
            requests.append(_chart(
                "Community price index, first month = 100", "LINE", ids["Market index"], n,
                domain_col=0, series_cols=(4,), x_title="Month", y_title="Index", anchor=(charts, top),
            ))
            top += 22
            if header and "Community $/sq ft median (12 mo)" in header:
                sq = _columns(header, "Building", "$/sq ft (12 mo)")
                requests.append(_styled(_chart(
                    "Trailing 12-month median price per square foot: community and buildings", "LINE", ids["Market index"], n,
                    domain_col=0, series_cols=(header.index("Community $/sq ft median (12 mo)"),) + tuple(col for col, _ in sq),
                    x_title="Month", y_title="Dollars per sq ft", anchor=(charts, top),
                ), [_line(COMMUNITY_COLOR, 3)] + [_line(BUILDING_COLORS.get(b, COMMUNITY_MEAN_COLOR)) for _, b in sq]))
                top += 22
            beds = [index for index, name in enumerate(header or []) if name.endswith("bedroom median (12 mo)")]
            if beds:
                requests.append(_chart(
                    "Trailing 12-month median price by bedroom count", "LINE", ids["Market index"], n,
                    domain_col=0, series_cols=(2,) + tuple(beds), x_title="Month", y_title="Dollars", anchor=(charts, top),
                ))
                top += 22
        if "Trend" in ids and headers.get("Trend"):
            header = headers["Trend"]
            n = sizes["Trend"]
            points = _columns(header, "Building", "sale")
            medians = _columns(header, "Building", "median (12 mo)")
            per_sq = _columns(header, "Building", "$/sq ft")
            requests.append(_styled(_chart(
                "Sale prices by building over time, with the community moving average (12-month median and mean)", "SCATTER",
                ids["Trend"], n, domain_col=0,
                series_cols=tuple(col for col, _ in points) + (header.index("Community median (12 mo)"), header.index("Community mean (12 mo)")),
                x_title="Recorded", y_title="Dollars", anchor=(charts, top),
            ), [_points(BUILDING_COLORS.get(b, COMMUNITY_MEAN_COLOR)) for _, b in points] + [_line(COMMUNITY_COLOR, 3), _line(COMMUNITY_MEAN_COLOR, 2, "MEDIUM_DASHED")]))
            top += 22
            requests.append(_styled(_chart(
                "Sale prices by building over time, with each building's 12-month median (three sales or more)", "SCATTER",
                ids["Trend"], n, domain_col=0,
                series_cols=tuple(col for col, _ in points) + tuple(col for col, _ in medians),
                x_title="Recorded", y_title="Dollars", anchor=(charts, top),
            ), [_points(BUILDING_COLORS.get(b, COMMUNITY_MEAN_COLOR)) for _, b in points] + [_line(BUILDING_COLORS.get(b, COMMUNITY_MEAN_COLOR)) for _, b in medians]))
            top += 22
            if per_sq and "Community $/sq ft median (12 mo)" in header:
                requests.append(_styled(_chart(
                    "Price per square foot by building over time, with the community 12-month median", "SCATTER",
                    ids["Trend"], n, domain_col=0,
                    series_cols=tuple(col for col, _ in per_sq) + (header.index("Community $/sq ft median (12 mo)"),),
                    x_title="Recorded", y_title="Dollars per sq ft", anchor=(charts, top),
                ), [_points(BUILDING_COLORS.get(b, COMMUNITY_MEAN_COLOR)) for _, b in per_sq] + [_line(COMMUNITY_COLOR, 3)]))
                top += 22
        if "By size" in ids and headers.get("By size"):
            header = headers["By size"]
            series = [index for index, name in enumerate(header) if name.endswith("bedrooms") or name.startswith("Last ")]
            if series:
                requests.append(_chart(
                    "Sale price against living area, by bedroom count", "SCATTER", ids["By size"], sizes["By size"],
                    domain_col=0, series_cols=tuple(series), x_title="Living sq ft", y_title="Dollars", anchor=(charts, top),
                ))
                top += 22
        if "By plan" in ids and headers.get("By plan"):
            header = headers["By plan"]
            requests.append(_chart(
                "Median price per square foot by plan, all years and recent", "COLUMN", ids["By plan"], sizes["By plan"],
                domain_col=0, series_cols=(header.index("Median $/sq ft"), header.index(f"Median $/sq ft (last {RECENT_MONTHS} mo)")),
                x_title="Plan", y_title="Dollars per sq ft", anchor=(charts, top),
            ))
            top += 22
        if "Unit values" in ids:
            n = sizes["Unit values"]
            requests.append(_chart(
                "Appreciation since last purchase, by unit (recent comps against last price)", "BAR", ids["Unit values"], n,
                domain_col=1, series_cols=(14, 32), x_title="Address", y_title="Appreciation %", anchor=(charts, top),
            ))
            bar = requests[-1]["addChart"]["chart"]
            bar["position"]["overlayPosition"]["heightPixels"] = 1400
            bar["spec"]["basicChart"]["axis"] = [
                {"position": "BOTTOM_AXIS", "title": "Appreciation %"},
                {"position": "LEFT_AXIS", "title": "Address"},
            ]
            for series in bar["spec"]["basicChart"]["series"]:
                series["targetAxis"] = "BOTTOM_AXIS"
            top += 72
            requests.append(_chart(
                "Estimate against last price, by unit", "SCATTER", ids["Unit values"], n,
                domain_col=6, series_cols=(12, 11, 31), x_title="Last price", y_title="Estimate", anchor=(charts, top),
            ))
            top += 22
            requests.append(_chart(
                "Last price per square foot against living area, by unit", "SCATTER", ids["Unit values"], n,
                domain_col=25, series_cols=(28,), x_title="Living sq ft", y_title="Dollars per sq ft", anchor=(charts, top),
            ))
            top += 22
        if "Building values" in ids:
            requests.append(_chart(
                "Mean appreciation percent by building", "COLUMN", ids["Building values"], sizes["Building values"],
                domain_col=0, series_cols=(6, 7), x_title="Building", y_title="Percent", anchor=(charts, top),
            ))
            top += 22
            requests.append(_chart(
                "Median price per square foot by building: last sales and the market now", "COLUMN", ids["Building values"], sizes["Building values"],
                domain_col=0, series_cols=(10, 11), x_title="Building", y_title="Dollars per sq ft", anchor=(charts, top),
            ))
    if lookup is not None:
        history = LOOKUP_HISTORY_ROW
        requests.append(_chart(
            "This unit's sale prices against the community and building medians", "LINE", lookup, history + 15,
            domain_col=9, series_cols=(10, 11, 12), x_title="Month", y_title="Dollars", anchor=(lookup, 2),
        ))
        chart = requests[-1]["addChart"]["chart"]
        chart["spec"]["basicChart"]["domains"][0]["domain"]["sourceRange"]["sources"][0]["startRowIndex"] = history
        for series in chart["spec"]["basicChart"]["series"]:
            series["series"]["sourceRange"]["sources"][0]["startRowIndex"] = history
        chart["position"]["overlayPosition"]["anchorCell"]["columnIndex"] = 3
        chart["position"]["overlayPosition"]["widthPixels"] = 760
        months = max(sizes.get("Market index", 1) - 1, 1)
        col = LOOKUP_MONTH_COLUMN
        requests.append(_styled(_chart(
            "This unit's indexed value month by month, its sales, and the community and building medians", "LINE",
            lookup, history + 1 + months, domain_col=col, series_cols=(col + 3, col + 1, col + 2, col + 4),
            x_title="Month", y_title="Dollars", anchor=(lookup, 2),
        ), [_line((0.84, 0.15, 0.16), 3), _line(COMMUNITY_COLOR, 2), _line((0.12, 0.47, 0.71), 2, "MEDIUM_DASHED"),
            {"colorStyle": _rgb((0.84, 0.15, 0.16)), "lineStyle": {"type": "INVISIBLE", "width": 1}, "pointStyle": {"size": 8, "shape": "CIRCLE"}}]))
        chart = requests[-1]["addChart"]["chart"]
        chart["spec"]["basicChart"]["domains"][0]["domain"]["sourceRange"]["sources"][0]["startRowIndex"] = history
        for series in chart["spec"]["basicChart"]["series"]:
            series["series"]["sourceRange"]["sources"][0]["startRowIndex"] = history
        chart["position"]["overlayPosition"]["anchorCell"]["columnIndex"] = col + 6
        chart["position"]["overlayPosition"]["widthPixels"] = 900
        if "Unit values" in ids:
            requests.append({
                "setDataValidation": {
                    "range": {"sheetId": lookup, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 1, "endColumnIndex": 2},
                    "rule": {
                        "condition": {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": f"='Unit values'!$B$2:$B${sizes.get('Unit values', 2)}"}]},
                        "showCustomUi": True,
                        "strict": False,
                    },
                }
            })
    return requests


def date_format_requests(ids: dict[str, int], sizes: dict[str, int]) -> list[dict[str, Any]]:
    """Format the date columns as dates, since a typed ISO date is stored as a serial number."""
    targets = (
        ("Sales", 0, 1, 1, None), ("Unit values", 4, 5, 1, None), ("Trend", 0, 1, 1, None), ("By size", 3, 4, 1, None),
        ("By plan", 13, 14, 1, None),
        ("Unit lookup", 0, 1, LOOKUP_HISTORY_ROW + 1, None), ("Unit lookup", 1, 2, 5, 6),
    )
    requests: list[dict[str, Any]] = []
    for name, start, end, first_row, last_row in targets:
        if name not in ids:
            continue
        requests.append({
            "repeatCell": {
                "range": {"sheetId": ids[name], "startRowIndex": first_row, "endRowIndex": last_row or max(2, sizes.get(name, 2) + 20), "startColumnIndex": start, "endColumnIndex": end},
                "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}}},
                "fields": "userEnteredFormat.numberFormat",
            }
        })
    return requests


def create_equity_chart_sheet(sheets: Any, title: str, tabs: dict[str, list[list[Any]]], *, spreadsheet_id: str = "") -> EquityChartsReport:
    """Create the spreadsheet, or refresh an existing one when its id is given, then fill and chart it.

    A refresh clears every tab it fills and removes the charts drawn before,
    so the sheet ends as a fresh run would leave it.
    """
    names = tuple(name for name in EQUITY_TABS if name in tabs)
    clearing: list[dict[str, Any]] = []
    if spreadsheet_id:
        created = sheets.get(spreadsheet_id, fields="sheets.properties,sheets.charts.chartId")
        existing = {str(sheet.get("properties", {}).get("title")) for sheet in (created.get("sheets") or [])}
        missing = [name for name in names if name not in existing]
        if missing:
            sheets.batch_update(spreadsheet_id, [{"addSheet": {"properties": {"title": name}}} for name in missing])
        for sheet in created.get("sheets") or []:
            for chart in sheet.get("charts") or []:
                if chart.get("chartId") is not None:
                    clearing.append({"deleteEmbeddedObject": {"objectId": chart["chartId"]}})
            if str(sheet.get("properties", {}).get("title")) in names:
                clearing.append({"updateCells": {"range": {"sheetId": sheet["properties"]["sheetId"]}, "fields": "userEnteredValue"}})
        if clearing:
            sheets.batch_update(spreadsheet_id, clearing)
        created = sheets.get(spreadsheet_id, fields="sheets.properties")
    else:
        created = sheets.create(title, sheet_titles=names)
        spreadsheet_id = str(created.get("spreadsheetId") or "")
    if not spreadsheet_id:
        raise ValueError("spreadsheet was not created")
    ids = {
        str(sheet.get("properties", {}).get("title")): int(sheet.get("properties", {}).get("sheetId", 0))
        for sheet in (created.get("sheets") or [])
    }
    counts: list[tuple[str, int]] = []
    sizes: dict[str, int] = {}
    widths: dict[str, int] = {}
    headers: dict[str, list[str]] = {}
    for name in names:
        values = tabs[name]
        sheets.values_update(spreadsheet_id, f"'{name}'!A1", values)
        counts.append((name, max(0, len(values) - 1)))
        sizes[name] = len(values)
        widths[name] = len(values[0]) if values else 0
        headers[name] = [str(cell) for cell in values[0]] if values else []
    requests = equity_chart_requests(ids, sizes, widths, headers)
    requests.extend(date_format_requests(ids, sizes))
    for name in names:
        if name not in ("Charts", "Unit lookup") and name in ids:
            requests.append({
                "updateSheetProperties": {
                    "properties": {"sheetId": ids[name], "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            })
    if requests:
        sheets.batch_update(spreadsheet_id, requests)
    return EquityChartsReport(
        spreadsheet_id,
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
        tuple(counts),
        sum(1 for request in requests if "addChart" in request),
    )
