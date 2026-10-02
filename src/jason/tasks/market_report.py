"""The market page of the Markdown reports, and each unit's valuation for its page.

GitHub renders Mermaid and nothing else that draws, so the yearly series go
in ``xychart-beta`` blocks, each unit's standing goes in a ``quadrantChart``,
and the views Mermaid cannot draw (a scatter with moving averages through
it) are images ``report_charts`` renders. A year with no sales carries the
previous year's figure on the line charts, since an xychart series must hold
one value per year; the text under each chart says so.
"""

from __future__ import annotations

from datetime import date
from statistics import median
from typing import Any

from jason.community.characteristics import FloorPlan, UnitCharacteristics
from jason.community.parcel_history import ParcelHistory
from jason.community.property_report import Valuation, dollars
from jason.tasks.equity_charts import (
    Sale,
    bedroom_counts,
    building_values,
    by_plan_rows,
    market_index,
    sales_of,
    trailing,
    unit_values,
)

# Blue, orange, green, red: the palette every xychart on the page uses, named in its caption.
PALETTE = ("#1d4ed8", "#c2410c", "#15803d", "#b91c1c")
# Sales a bedroom count needs before it gets its own line.
BEDROOM_MINIMUM = 5


def market_markdown(
    histories: tuple[ParcelHistory, ...],
    characteristics: dict[str, UnitCharacteristics] | None = None,
    plans: tuple[FloorPlan, ...] = (),
    *,
    title: str,
    today: date | None = None,
    images: dict[str, str] | None = None,
) -> str:
    """The market over time, each unit's standing, and the buildings and plans."""
    today = today or date.today()
    sales = sales_of(histories, characteristics, plans)
    lines = [f"# {title}", ""]
    if not sales:
        lines.append("No priced sale on any chain.")
        return "\n".join(lines)
    buildings = tuple(sorted({sale.building for sale in sales}))
    values = unit_values(histories, today=today, characteristics=characteristics, plans=plans)
    index_rows = market_index(sales, buildings, today=today)
    now = f"{today.year}-{today.month:02d}"
    count, med, mean = trailing(sales, now)
    _c, sq, _ = trailing(sales, now, per_sqft=True)
    deed = sum(1 for sale in sales if sale.source == "deed")
    lines.append(
        f"{len(sales)} sales from {sales[0].recorded.isoformat()} to {sales[-1].recorded.isoformat()}, "
        f"{deed} priced by the deed and {len(sales) - deed} by the base the county enrolled. "
        + (f"In the last twelve months {count} sold, at a median of {dollars(med)} and a mean of {dollars(mean)}"
           + (f", {dollars(sq)} a square foot" if sq else "") + "."
           if med else "No sale in the last twelve months.")
    )
    lines.append("")
    years = list(range(sales[0].recorded.year, today.year + 1))
    lines += _section(
        "Sales each year",
        xychart("Sales recorded each year", years, [("bar", _counts(sales, years))], "Sales", palette=PALETTE[:1]),
        "Every sale on a chain, whether the deed or the base priced it.",
    )
    med_by_year = _yearly(sales, years, lambda s: s.price)
    mean_by_year = _yearly(sales, years, lambda s: s.price, mean=True)
    lines += _section(
        "Median and mean price each year",
        xychart("Sale price each year", years, [("line", med_by_year), ("line", mean_by_year)], "Dollars", palette=PALETTE[:2]),
        "Blue is the median, orange the mean. A year with no sales carries the previous year's figure.",
    )
    lines += _section(
        "Community index at each year's end",
        xychart("Trailing 12-month median, first month = 100", years, [("line", _year_end(index_rows, years, 4))], "Index", palette=PALETTE[:1]),
        "The trailing twelve-month median price in December of each year, or the latest month for the current year, against the first month with sales.",
    )
    # A bedroom count needs enough sales to make a line; one four-bedroom unit would draw a flat line from its own sale.
    beds = tuple(count_ for count_ in bedroom_counts(sales) if sum(1 for s in sales if s.bedrooms == count_) >= BEDROOM_MINIMUM)
    sq_series: list[tuple[str, list[float]]] = [("line", _yearly(sales, years, lambda s: s.per_sqft))]
    captions = ["Blue is every sale with a measured area"]
    for index_, count_ in enumerate(beds[:3]):
        sq_series.append(("line", _yearly(sales, years, lambda s, c=count_: s.per_sqft if s.bedrooms == c else None)))
        captions.append(f"{('orange', 'green', 'red')[index_]} is {count_} bedrooms")
    if any(v for _, values in sq_series for v in values):
        lines += _section(
            "Price per square foot each year",
            xychart("Median dollars per square foot each year", years, sq_series, "Dollars per sq ft", palette=PALETTE[:len(sq_series)]),
            ", ".join(captions) + ". A year with no sales of that kind carries the previous year's figure.",
        )
    quadrant = quadrant_chart(values)
    if quadrant:
        lines += _section(
            "Where each unit stands",
            quadrant,
            "Each point is a unit: left to right by its last price per square foot, bottom to top by its appreciation per year since it last sold, under the recent comps. Both axes run from the lowest unit to the highest. A unit that sold within the year has no yearly rate and is left out.",
        )
    lines.append("## By building")
    lines.append("")
    rollup = building_values(values, index_rows)
    lines += _table(rollup, (0, 1, 2, 6, 7, 9, 10, 12), money=(2, 10, 12))
    lines.append("")
    labels = [str(row[0]) for row in rollup[1:]]
    lines.append("```mermaid")
    lines.append(xychart("Median last price and median last price per square foot, by building", labels, [("bar", [_num(row[2]) for row in rollup[1:]])], "Dollars", palette=PALETTE[:1]))
    lines.append("```")
    lines.append("")
    lines.append("```mermaid")
    lines.append(xychart("Median last dollars per square foot, by building", labels, [("bar", [_num(row[10]) for row in rollup[1:]])], "Dollars per sq ft", palette=PALETTE[1:2]))
    lines.append("```")
    lines.append("")
    lines.append("## By plan")
    lines.append("")
    plan_rows = by_plan_rows(sales, values, plans, today=today)
    lines += _table(plan_rows, (0, 1, 2, 4, 6, 7, 8, 9, 10, 11, 12, 14), money=(9, 10, 11, 12))
    lines.append("")
    if images:
        lines.append("## Charts")
        lines.append("")
        lines.append("Rendered images, since Mermaid draws no scatter with lines through it.")
        lines.append("")
        for caption, path in images.items():
            lines.append(f"![{caption}]({path})")
            lines.append("")
    lines.append("The method, and what it is not, is in the ownership history note (mystique/notes/ownership-history.md) under Views. Comps are the community's own recorded sales; none of this is an appraisal.")
    lines.append("")
    return "\n".join(lines)


def xychart(title: str, categories: list[Any], series: list[tuple[str, list[float]]], y_title: str, *, palette: tuple[str, ...] = PALETTE) -> str:
    """A Mermaid ``xychart-beta`` block body. Every series holds one value per category; a missing value is 0."""
    rows = [
        '%%{init: {"themeVariables": {"xyChart": {"plotColorPalette": "' + ", ".join(palette) + '"}}}}%%',
        "xychart-beta",
        f'    title "{title}"',
        "    x-axis [" + ", ".join(str(c) for c in categories) + "]",
    ]
    numbers = [v for _, values in series for v in values if v is not None]
    if numbers:
        low, high = min(numbers), max(numbers)
        if all(kind == "line" for kind, _ in series) and low > 0:
            pad = max((high - low) * 0.1, high * 0.02)
            rows.append(f'    y-axis "{y_title}" {_axis(low - pad)} --> {_axis(high + pad)}')
        else:
            rows.append(f'    y-axis "{y_title}"')
    else:
        rows.append(f'    y-axis "{y_title}"')
    for kind, values in series:
        rows.append(f"    {kind} [" + ", ".join(_axis(v if v is not None else 0) for v in values) + "]")
    return "\n".join(rows)


def quadrant_chart(values: list[list[Any]]) -> str:
    """A Mermaid ``quadrantChart`` of the units: last price per square foot against appreciation percent per year."""
    points = [(row[1], row[28], row[15]) for row in values[1:] if row[28] != "" and row[15] != ""]
    if len(points) < 2:
        return ""
    xs = [p[1] for p in points]
    ys = [p[2] for p in points]
    rows = [
        "quadrantChart",
        '    title Last price per square foot against appreciation per year since the last sale',
        f'    x-axis "{dollars(int(min(xs) * 100))} a foot" --> "{dollars(int(max(xs) * 100))} a foot"',
        f'    y-axis "{min(ys):+.1f}% a year" --> "{max(ys):+.1f}% a year"',
        "    quadrant-1 Paid more, gained",
        "    quadrant-2 Paid less, gained",
        "    quadrant-3 Paid less, lost ground",
        "    quadrant-4 Paid more, lost ground",
    ]
    seen: set[str] = set()
    for address, x, y in points:
        label = _short(address)
        while label in seen:
            label += " ."
        seen.add(label)
        rows.append(f'    "{label}": [{_unit(x, xs):.2f}, {_unit(y, ys):.2f}]')
    return "\n".join(rows)


def valuations(values: list[list[Any]]) -> dict[str, Valuation]:
    """Each unit's valuation from the Unit values rows, by address."""
    per_building: dict[Any, int] = {}
    for row in values[1:]:
        if row[16] != "":
            per_building[row[0]] = per_building.get(row[0], 0) + 1
    found: dict[str, Valuation] = {}
    for row in values[1:]:
        found[row[1]] = Valuation(
            last_price=_cents(row[6]), source=str(row[7]), comps=_cents(row[12]), comps_basis=str(row[22]),
            indexed=_cents(row[11]), size_estimate=_cents(row[31]), size_basis=str(row[33]),
            per_sqft=_cents(row[28]), community_per_sqft=_cents(row[29]),
            appreciation_pct=row[14] if row[14] != "" else None, annual_pct=row[15] if row[15] != "" else None,
            rank=row[16] if row[16] != "" else None, building_units=per_building.get(row[0]),
            percentile=row[17] if row[17] != "" else None, assessed=_cents(row[8]),
        )
    return found


def _section(heading: str, chart: str, caption: str) -> list[str]:
    return [f"## {heading}", "", "```mermaid", chart, "```", "", caption, ""]


def _counts(sales: tuple[Sale, ...], years: list[int]) -> list[float]:
    return [float(sum(1 for sale in sales if sale.recorded.year == year)) for year in years]


def _yearly(sales: tuple[Sale, ...], years: list[int], key, *, mean: bool = False) -> list[float | None]:
    """The median (or mean) of ``key`` over each year's sales in dollars, carried forward through empty years."""
    found: list[float | None] = []
    last: float | None = None
    for year in years:
        values = [key(sale) for sale in sales if sale.recorded.year == year]
        values = [v for v in values if v]
        if values:
            last = round((sum(values) / len(values) if mean else median(values)) / 100, 2)
        found.append(last)
    return found


def _year_end(index_rows: list[list[Any]], years: list[int], column: int) -> list[float | None]:
    """The column's value on the last row of each year, carried forward through empty years."""
    by_year: dict[int, float] = {}
    for row in index_rows[1:]:
        month = str(row[0]).lstrip("'")
        if row[column] not in ("", None):
            by_year[int(month[:4])] = float(row[column])
    found: list[float | None] = []
    last: float | None = None
    for year in years:
        last = by_year.get(year, last)
        found.append(last)
    return found


def _table(rows: list[list[Any]], columns: tuple[int, ...], *, money: tuple[int, ...] = ()) -> list[str]:
    header = rows[0]
    lines = ["| " + " | ".join(str(header[c]) for c in columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows[1:]:
        cells = []
        for c in columns:
            value = row[c]
            if c in money and value != "":
                cells.append(dollars(int(round(float(value) * 100))))
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def _num(value: Any) -> float | None:
    return float(value) if value not in ("", None) else None


def _axis(value: float) -> str:
    return str(int(round(value))) if abs(value - round(value)) < 0.005 else f"{value:.2f}"


def _unit(value: float, values: list[float]) -> float:
    low, high = min(values), max(values)
    if high == low:
        return 0.5
    return min(0.98, max(0.02, (value - low) / (high - low)))


def _short(address: str) -> str:
    """``3024 MACON DR`` becomes ``3024 Macon``: the number and the first word of the street."""
    words = address.split()
    if len(words) >= 2:
        return f"{words[0]} {words[1].title()}"
    return address.title()


def _cents(value: Any) -> int | None:
    if value in ("", None):
        return None
    return int(round(float(value) * 100))
