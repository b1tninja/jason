"""A spreadsheet that charts the conveyance history.

Every deed on every chain is one row, with the process it completed, the
price the deed declared or the base the county enrolled, and the building.
From those rows: how many conveyances of each kind recorded each year, the
median price each year, each sale by date with one series per process, how
long each owner held, and the deed price against the enrolled base. The
charts are Sheets' own, drawn from the tabs beside them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Any

from jason.community.parcel_history import HistoryStep, ParcelHistory
from jason.community.tax import parcel_number
from jason.tasks.unit_charts import _chart

SALES_TABS = ("Conveyances", "By year", "By process", "By building", "Tenure", "Price vs base", "Charts")

PROCESSES = (
    "developer closing",
    "blanket release",
    "resale",
    "reo resale",
    "foreclosure",
    "excluded transfer",
    "re-recording",
    "restatement",
)


@dataclass
class SalesChartsReport:
    spreadsheet_id: str
    url: str
    counts: tuple[tuple[str, int], ...]
    charts: int

    def summary(self) -> str:
        tabs = " ".join(f"{name}={count}" for name, count in self.counts)
        return f"spreadsheet={self.spreadsheet_id} charts={self.charts} {tabs} url={self.url}"


def sales_chart_tabs(histories: tuple[ParcelHistory, ...]) -> dict[str, list[list[Any]]]:
    units = tuple(item for item in histories if not item.association)
    return {
        "Conveyances": _conveyances(units),
        "By year": _by_year(units),
        "By process": _by_process(units),
        "By building": _by_building(units),
        "Tenure": _tenure(units),
        "Price vs base": _price_vs_base(units),
        "Charts": [["Charts of the conveyance history, drawn from the tabs beside this one."]],
    }


def _label(step: HistoryStep) -> str:
    return step.process if step.process in PROCESSES else ("developer closing" if step.developer else "resale")


def _conveyances(units) -> list[list[Any]]:
    rows: list[list[Any]] = [[
        "Recorded", "Year", "Building", "Address", "Parcel", "Process", "From", "To",
        "Price", "Price source", "Enrolled base", "Bill year", "Placed by", "Document No",
    ]]
    for item in units:
        for step in item.steps:
            amount, source = step.price_or_base
            rows.append([
                step.recorded.isoformat() if step.recorded else "", step.recorded.year if step.recorded else "",
                item.building or "", item.address, parcel_number(item.apn), _label(step),
                ", ".join(step.grantors), ", ".join(step.grantees),
                round(amount / 100, 2) if amount else "", source,
                round(step.enrolled_cents / 100, 2) if step.enrolled_cents else "", step.bill_year or "",
                step.placement, step.number,
            ])
    rows[1:] = sorted(rows[1:], key=lambda row: (str(row[0]), row[13]))
    return rows


def _by_year(units) -> list[list[Any]]:
    """Counts per process per year, then sales, median and mean price."""
    years: dict[int, dict[str, int]] = {}
    prices: dict[int, list[int]] = {}
    for item in units:
        for step in item.steps:
            if step.recorded is None:
                continue
            year = step.recorded.year
            bucket = years.setdefault(year, {})
            label = _label(step)
            bucket[label] = bucket.get(label, 0) + 1
            amount, _source = step.price_or_base
            if step.reassesses and amount:
                prices.setdefault(year, []).append(amount)
    header = ["Year"] + list(PROCESSES) + ["All conveyances", "Priced sales", "Median price", "Mean price", "Lowest", "Highest"]
    rows: list[list[Any]] = [header]
    for year in sorted(years):
        bucket = years[year]
        found = prices.get(year, [])
        rows.append(
            [year]
            + [bucket.get(label, 0) for label in PROCESSES]
            + [sum(bucket.values()), len(found)]
            + ([round(median(found) / 100, 2), round(sum(found) / len(found) / 100, 2), round(min(found) / 100, 2), round(max(found) / 100, 2)] if found else ["", "", "", ""])
        )
    return rows


def _by_process(units) -> list[list[Any]]:
    """One row per priced sale: the date, then the price in the column of its process."""
    rows: list[list[Any]] = [["Recorded", "Address", "Document No"] + list(PROCESSES)]
    sales = []
    for item in units:
        for step in item.steps:
            amount, _source = step.price_or_base
            if step.recorded is None or not amount or not step.reassesses:
                continue
            sales.append((step.recorded, item.address, step.number, _label(step), amount))
    for recorded, address, number, label, amount in sorted(sales):
        row: list[Any] = [recorded.isoformat(), address, number] + [""] * len(PROCESSES)
        row[3 + PROCESSES.index(label)] = round(amount / 100, 2)
        rows.append(row)
    return rows


def _by_building(units) -> list[list[Any]]:
    rows: list[list[Any]] = [[
        "Building", "Units", "Developer", "First conveyance", "Last first conveyance", "Conveyances", "Sales",
        "Resales", "Foreclosures", "Median first price", "Median latest price", "Latest sale", "Mean years held",
    ]]
    groups: dict[int, list[ParcelHistory]] = {}
    for item in units:
        if item.building:
            groups.setdefault(item.building, []).append(item)
    for building in sorted(groups):
        items = groups[building]
        firsts = [item.steps[0] for item in items if item.steps]
        first_prices = [step.price_or_base[0] for step in firsts if step.price_or_base[0]]
        latest = [item.last_sale for item in items if item.last_sale]
        latest_prices = [step.price_or_base[0] for step in latest if step.price_or_base[0]]
        held = [years for item in items for years in _held_years(item)]
        rows.append([
            building, len(items), items[0].developer,
            min((step.recorded for step in firsts if step.recorded), default=None).isoformat() if firsts else "",
            max((step.recorded for step in firsts if step.recorded), default=None).isoformat() if firsts else "",
            sum(len(item.steps) for item in items), sum(len(item.sales) for item in items),
            sum(1 for item in items for step in item.steps if _label(step) in ("resale", "reo resale")),
            sum(1 for item in items for step in item.steps if _label(step) == "foreclosure"),
            round(median(first_prices) / 100, 2) if first_prices else "",
            round(median(latest_prices) / 100, 2) if latest_prices else "",
            max((step.recorded for step in latest if step.recorded), default=None).isoformat() if latest else "",
            round(sum(held) / len(held), 1) if held else "",
        ])
    return rows


def _held_years(item: ParcelHistory, today: date | None = None) -> list[float]:
    """Years each reassessing owner held the unit; the current owner counts to today."""
    today = today or date.today()
    found: list[float] = []
    sales = [step for step in item.steps if step.reassesses and step.recorded]
    for index, step in enumerate(sales):
        end = sales[index + 1].recorded if index + 1 < len(sales) else today
        found.append(round((end - step.recorded).days / 365.25, 1))
    return found


def _tenure(units) -> list[list[Any]]:
    rows: list[list[Any]] = [["Building", "Address", "Parcel", "Owner", "From", "To", "Years", "Current"]]
    today = date.today()
    for item in units:
        sales = [step for step in item.steps if step.reassesses and step.recorded]
        for index, step in enumerate(sales):
            end = sales[index + 1].recorded if index + 1 < len(sales) else None
            rows.append([
                item.building or "", item.address, parcel_number(item.apn), ", ".join(step.grantees),
                step.recorded.isoformat(), end.isoformat() if end else "",
                round(((end or today) - step.recorded).days / 365.25, 1), "" if end else "yes",
            ])
    return rows


def _price_vs_base(units) -> list[list[Any]]:
    rows: list[list[Any]] = [["Deed price", "Enrolled base", "Address", "Recorded", "Difference %"]]
    for item in units:
        for step in item.steps:
            if step.price_cents and step.enrolled_cents:
                rows.append([
                    round(step.price_cents / 100, 2), round(step.enrolled_cents / 100, 2), item.address,
                    step.recorded.isoformat() if step.recorded else "",
                    round((step.enrolled_cents - step.price_cents) * 100 / step.price_cents, 1),
                ])
    return rows


def sales_chart_requests(ids: dict[str, int], sizes: dict[str, int]) -> list[dict[str, Any]]:
    charts = ids.get("Charts")
    if charts is None:
        return []
    requests: list[dict[str, Any]] = []
    top = 2
    if "By year" in ids:
        n = sizes["By year"]
        request = _chart(
            "Conveyances recorded each year, by process", "COLUMN", ids["By year"], n,
            domain_col=0, series_cols=tuple(range(1, 1 + len(PROCESSES))),
            x_title="Year", y_title="Conveyances", anchor=(charts, top),
        )
        request["addChart"]["chart"]["spec"]["basicChart"]["stackedType"] = "STACKED"
        requests.append(request)
        top += 22
        requests.append(_chart(
            "Median and mean sale price each year", "LINE", ids["By year"], n,
            domain_col=0, series_cols=(len(PROCESSES) + 3, len(PROCESSES) + 4),
            x_title="Year", y_title="Dollars", anchor=(charts, top),
        ))
        top += 22
    if "By process" in ids:
        requests.append(_chart(
            "Every sale by date and price, one series per process", "SCATTER", ids["By process"], sizes["By process"],
            domain_col=0, series_cols=tuple(range(3, 3 + len(PROCESSES))),
            x_title="Recorded", y_title="Dollars", anchor=(charts, top),
        ))
        top += 22
    if "By building" in ids:
        requests.append(_chart(
            "Median first price and median latest price by building", "COLUMN", ids["By building"], sizes["By building"],
            domain_col=0, series_cols=(9, 10), x_title="Building", y_title="Dollars", anchor=(charts, top),
        ))
        top += 22
        requests.append(_chart(
            "Mean years held by building", "COLUMN", ids["By building"], sizes["By building"],
            domain_col=0, series_cols=(12,), x_title="Building", y_title="Years", anchor=(charts, top),
        ))
        top += 22
    if "Price vs base" in ids:
        requests.append(_chart(
            "Deed price against the base the county enrolled", "SCATTER", ids["Price vs base"], sizes["Price vs base"],
            domain_col=0, series_cols=(1,), x_title="Deed price", y_title="Enrolled base", anchor=(charts, top),
        ))
    return requests


def create_sales_chart_sheet(sheets: Any, title: str, tabs: dict[str, list[list[Any]]]) -> SalesChartsReport:
    names = tuple(name for name in SALES_TABS if name in tabs)
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
    for name in names:
        values = tabs[name]
        sheets.values_update(spreadsheet_id, f"'{name}'!A1", values)
        counts.append((name, max(0, len(values) - 1)))
        sizes[name] = len(values)
    requests = sales_chart_requests(ids, sizes)
    for name in names:
        if name != "Charts" and name in ids:
            requests.append({
                "updateSheetProperties": {
                    "properties": {"sheetId": ids[name], "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            })
    if requests:
        sheets.batch_update(spreadsheet_id, requests)
    return SalesChartsReport(
        spreadsheet_id,
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
        tuple(counts),
        sum(1 for request in requests if "addChart" in request),
    )
