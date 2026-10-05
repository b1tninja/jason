"""A spreadsheet that draws the unit numbering and the sales.

One tab per table and one tab of charts. The first chart puts every unit
number on the bottom axis against its building, once for the 2007 plan and
once for Watt's numbering, so the twelve numbers that sit on two buildings
show as two points in one column. The second counts parcels per unit
number, a flat line of ones with a step of twos from 21 to 32. The third
draws each sale as a point by date and price, one series per building, with
the enrolled base standing in where the deed gave no price.

Values go in as the user would type them, so a date is a date. The charts
are Sheets' own, added with ``addChart``; nothing is drawn as an image.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jason.community.parcel_history import ParcelHistory
from jason.community.reports import PlanBlock, plan_unit, unit_parcels
from jason.community.tax import parcel_number

CHART_TABS = ("Unit numbers", "Overlap", "Number map", "Parcels per unit", "Sales by building", "Charts")


@dataclass
class UnitChartsReport:
    spreadsheet_id: str
    url: str
    counts: tuple[tuple[str, int], ...]
    charts: int

    def summary(self) -> str:
        tabs = " ".join(f"{name}={count}" for name, count in self.counts)
        return f"spreadsheet={self.spreadsheet_id} charts={self.charts} {tabs} url={self.url}"


def unit_chart_tabs(
    blocks: tuple[PlanBlock, ...],
    histories: tuple[ParcelHistory, ...],
) -> dict[str, list[list[Any]]]:
    """The five data tabs. The Charts tab is empty and holds the charts."""
    address = {item.apn: item.address for item in histories}
    return {
        "Unit numbers": _unit_rows(blocks, address),
        "Overlap": _overlap_rows(blocks, address),
        "Number map": _number_map(blocks),
        "Parcels per unit": _parcels_per_unit(blocks),
        "Sales by building": _sales_by_building(histories),
        "Charts": [["The charts on this tab are drawn from the other tabs. Building 3 and buildings 4 and 5 share unit numbers 21 to 32."]],
    }


def _unit_rows(blocks, address) -> list[list[Any]]:
    rows: list[list[Any]] = [["Building", "Numbering", "Unit", "Parcel", "Address", "Same number on", "Places a deed by unit"]]
    for block in sorted(blocks, key=lambda item: int(item.building)):
        if not block.book_page:                 # a block on no map page names no parcel
            continue
        for sub in range(block.first_subparcel, block.first_subparcel + block.count):
            apn = block.parcel(sub)
            unit = plan_unit(apn, blocks)
            others = [
                f"building {int(other.building)} {parcel_number(other_apn)}"
                for other, other_apn in unit_parcels(unit or 0, blocks)
                if other_apn != apn
            ]
            rows.append([
                int(block.building), block.plan, unit, parcel_number(apn), address.get(apn, ""),
                "; ".join(others), "yes" if block.parent_parcels else "no",
            ])
    return rows


def _overlap_rows(blocks, address) -> list[list[Any]]:
    rows: list[list[Any]] = [["Unit", "2007 plan building", "2007 plan parcel", "2007 plan address", "Watt building", "Watt parcel", "Watt address"]]
    top = max((block.last_unit for block in blocks), default=0)
    for unit in range(1, top + 1):
        found = unit_parcels(unit, blocks)
        if len(found) < 2:
            continue
        plan = [(block, apn) for block, apn in found if block.plan == "2007 plan"]
        watt = [(block, apn) for block, apn in found if block.plan != "2007 plan"]
        if not plan or not watt:
            continue
        rows.append([
            unit, int(plan[0][0].building), parcel_number(plan[0][1]), address.get(plan[0][1], ""),
            int(watt[0][0].building), parcel_number(watt[0][1]), address.get(watt[0][1], ""),
        ])
    return rows


def _number_map(blocks) -> list[list[Any]]:
    """Unit number against building, one column per numbering, for the scatter chart."""
    rows: list[list[Any]] = [["Unit", "2007 plan building", "Watt building"]]
    top = max((block.last_unit for block in blocks), default=0)
    for unit in range(1, top + 1):
        plan = ""
        watt = ""
        for block, _apn in unit_parcels(unit, blocks):
            if block.plan == "2007 plan":
                plan = int(block.building)
            else:
                watt = int(block.building)
        rows.append([unit, plan, watt])
    return rows


def _parcels_per_unit(blocks) -> list[list[Any]]:
    rows: list[list[Any]] = [["Unit", "Parcels with this number"]]
    top = max((block.last_unit for block in blocks), default=0)
    for unit in range(1, top + 1):
        rows.append([unit, len(unit_parcels(unit, blocks))])
    return rows


def _sales_by_building(histories) -> list[list[Any]]:
    """One row per sale: the date, then the price in the column of its building."""
    buildings = sorted({item.building for item in histories if item.building and not item.association})
    header = ["Recorded", "Address", "Parcel", "Source"] + [f"Building {number}" for number in buildings]
    rows: list[list[Any]] = [header]
    sales = []
    for item in histories:
        if item.association or not item.building:
            continue
        for step in item.sales:
            amount, source = step.price_or_base
            if not amount or step.recorded is None:
                continue
            sales.append((step.recorded, item.address, parcel_number(item.apn), source, item.building, amount))
    for recorded, address, apn, source, building, amount in sorted(sales):
        row: list[Any] = [recorded.isoformat(), address, apn, source] + [""] * len(buildings)
        row[4 + buildings.index(building)] = round(amount / 100, 2)
        rows.append(row)
    return rows


def chart_requests(ids: dict[str, int], sizes: dict[str, int]) -> list[dict[str, Any]]:
    """The three ``addChart`` requests, anchored down the Charts tab."""
    charts = ids.get("Charts")
    if charts is None:
        return []
    requests: list[dict[str, Any]] = []
    top = 2
    number_map = ids.get("Number map")
    if number_map is not None:
        n = sizes.get("Number map", 1)
        requests.append(_chart(
            "Unit numbers by building: the 2007 plan and Watt's numbering",
            "SCATTER", number_map, n, domain_col=0, series_cols=(1, 2),
            x_title="Unit number", y_title="Building", anchor=(charts, top),
        ))
        top += 22
    per_unit = ids.get("Parcels per unit")
    if per_unit is not None:
        n = sizes.get("Parcels per unit", 1)
        requests.append(_chart(
            "Parcels that carry each unit number (two from 21 to 32)",
            "COLUMN", per_unit, n, domain_col=0, series_cols=(1,),
            x_title="Unit number", y_title="Parcels", anchor=(charts, top),
        ))
        top += 22
    sales = ids.get("Sales by building")
    if sales is not None:
        n = sizes.get("Sales by building", 1)
        width = sizes.get("Sales by building columns", 4)
        requests.append(_chart(
            "Sale prices by building (deed price, or the enrolled base where the deed gave none)",
            "SCATTER", sales, n, domain_col=0, series_cols=tuple(range(4, width)),
            x_title="Recorded", y_title="Dollars", anchor=(charts, top),
        ))
    return requests


def _chart(title, kind, sheet_id, rows, *, domain_col, series_cols, x_title, y_title, anchor) -> dict[str, Any]:
    def span(col: int) -> dict[str, Any]:
        return {"sourceRange": {"sources": [{
            "sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": rows,
            "startColumnIndex": col, "endColumnIndex": col + 1,
        }]}}

    return {
        "addChart": {
            "chart": {
                "spec": {
                    "title": title,
                    "basicChart": {
                        "chartType": kind,
                        "legendPosition": "BOTTOM_LEGEND",
                        "headerCount": 1,
                        "axis": [
                            {"position": "BOTTOM_AXIS", "title": x_title},
                            {"position": "LEFT_AXIS", "title": y_title},
                        ],
                        "domains": [{"domain": span(domain_col)}],
                        "series": [{"series": span(col), "targetAxis": "LEFT_AXIS"} for col in series_cols],
                    },
                },
                "position": {
                    "overlayPosition": {
                        "anchorCell": {"sheetId": anchor[0], "rowIndex": anchor[1], "columnIndex": 0},
                        "widthPixels": 1000,
                        "heightPixels": 400,
                    }
                },
            }
        }
    }


def create_unit_chart_sheet(sheets: Any, title: str, tabs: dict[str, list[list[Any]]]) -> UnitChartsReport:
    """Create the spreadsheet, fill the tabs, and add the charts."""
    names = tuple(name for name in CHART_TABS if name in tabs)
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
    sizes["Sales by building columns"] = len(tabs["Sales by building"][0]) if tabs.get("Sales by building") else 4
    requests = chart_requests(ids, sizes)
    for name in names:
        if name == "Charts" or name not in ids:
            continue
        requests.append({
            "updateSheetProperties": {
                "properties": {"sheetId": ids[name], "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        })
    if requests:
        sheets.batch_update(spreadsheet_id, requests)
    return UnitChartsReport(
        spreadsheet_id,
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
        tuple(counts),
        sum(1 for request in requests if "addChart" in request),
    )
