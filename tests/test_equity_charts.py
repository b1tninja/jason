from datetime import date

from jason.community.characteristics import FloorPlan, UnitCharacteristics
from jason.community.parcel_history import HistoryStep, ParcelHistory
from jason.tasks.equity_charts import (
    LOOKUP_HISTORY_ROW,
    LOOKUP_MONTH_COLUMN,
    UNIT_VALUE_HEADER,
    building_values,
    by_plan_rows,
    by_size_rows,
    create_equity_chart_sheet,
    date_format_requests,
    equity_chart_requests,
    equity_chart_tabs,
    lookup_rows,
    market_index,
    sales_of,
    trailing,
    trend_rows,
    unit_paths,
    unit_values,
)


def _step(order, number, process, grantees, *, price=None, base=None, developer="", reassesses=True):
    recorded = date(int(number[:4]), int(number[4:6]), int(number[6:8]))
    return HistoryStep(order, number, recorded, ("SELLER",), grantees, (), process, True, reassesses, developer, price, None, None, False, None, base, None, "handoff", "", "")


def _parcel(apn, address, building, steps, developer="Watt Communities at Mystique"):
    return ParcelHistory(apn, address, None, building, None, "", developer, steps[-1].number, steps[-1].recorded, (), steps, (), (), True, 2013, 2025)


def _units():
    return (
        _parcel("1", "A ST", 1, (_step(1, "202001150001", "developer closing", ("ONE",), price=30_000_000, developer="Watt"), _step(2, "202301150002", "resale", ("TWO",), price=40_000_000))),
        _parcel("2", "B ST", 1, (_step(1, "202002150003", "developer closing", ("THREE",), price=31_000_000, developer="Watt"),)),
        _parcel("3", "C ST", 1, (_step(1, "202003150004", "developer closing", ("FOUR",), price=32_000_000, developer="Watt"), _step(2, "202502150005", "resale", ("FIVE",), price=45_000_000))),
        _parcel("4", "D ST", 2, (_step(1, "202101150006", "developer closing", ("SIX",), base=35_000_000, developer="Watt"), _step(2, "202401150007", "restatement", ("SIX TR",), reassesses=False))),
    )


PLANS = (
    FloorPlan("Plan 1", "Watt Communities at Mystique", 3, 1_500, 2, baths=2.5),
    FloorPlan("Plan 4B", "Watt Communities at Mystique", 2, 1_326, 3, baths=2.5),
)

CHARACTERISTICS = {
    "1": UnitCharacteristics("1", living_sqft=1_500, bedrooms=3, baths=2.5, year_built=2020),
    "2": UnitCharacteristics("2", living_sqft=1_500, bedrooms=3, baths=2.5, year_built=2020),
    "3": UnitCharacteristics("3", living_sqft=1_000, bedrooms=2, baths=2.5, year_built=2020),
}

TODAY = date(2025, 9, 1)


def test_sales_and_the_trailing_median():
    sales = sales_of(_units())
    assert [(s.recorded.isoformat(), s.price // 100, s.source) for s in sales][:2] == [("2020-01-15", 300000, "deed"), ("2020-02-15", 310000, "deed")]
    assert trailing(sales, "2020-12") == (3, 31_000_000, 31_000_000)
    assert trailing(sales, "2020-12", building=2) == (0, None, None)
    assert trailing(sales, "2025-09")[0] == 1 and trailing(sales, "2025-09")[1] == 45_000_000


def test_sales_carry_the_assessor_factors_and_the_plan():
    sales = sales_of(_units(), CHARACTERISTICS, PLANS)
    first = sales[0]
    assert first.living_sqft == 1_500 and first.bedrooms == 3 and first.plan == "Plan 1" and first.per_sqft == 20_000
    c_st = next(s for s in sales if s.address == "C ST")
    assert c_st.plan == "" and c_st.per_sqft == 32_000  # 1,000 sq ft matches no Watt plan; the area still counts
    d_st = next(s for s in sales if s.address == "D ST")
    assert d_st.living_sqft is None and d_st.per_sqft is None
    assert trailing(sales, "2020-12", per_sqft=True) == (3, 20_667, 24_222)
    assert trailing(sales, "2020-12", bedrooms=2) == (1, 32_000_000, 32_000_000)


def test_the_market_index_runs_month_by_month_with_a_building_column():
    sales = sales_of(_units())
    rows = market_index(sales, (1, 2), today=TODAY)
    assert rows[0][:5] == ["Month", "Community sales (12 mo)", "Community median (12 mo)", "Community mean (12 mo)", "Index (first month = 100)"]
    assert rows[1][0] == "'2020-01" and rows[1][2] == 300000.0 and rows[1][4] == 100.0
    # The apostrophe keeps the month as text in Sheets; a bare "2020-01" would be entered as a date serial.
    dec = next(row for row in rows if row[0] == "'2020-12")
    assert dec[1] == 3 and dec[2] == 310000.0 and dec[5] == 310000.0 and dec[6] == ""  # building 1 has three sales, building 2 none
    assert rows[-1][0] == "'2025-09"


def test_the_market_index_reads_price_per_square_foot_and_bedrooms():
    sales = sales_of(_units(), CHARACTERISTICS, PLANS)
    rows = market_index(sales, (1, 2), today=TODAY)
    header = rows[0]
    assert header[7:] == [
        "Community $/sq ft median (12 mo)", "Building 1 $/sq ft (12 mo)", "Building 2 $/sq ft (12 mo)",
        "2 bedroom median (12 mo)", "3 bedroom median (12 mo)", "2 bedroom $/sq ft (12 mo)", "3 bedroom $/sq ft (12 mo)",
    ]
    dec = next(row for row in rows if row[0] == "'2020-12")
    assert dec[7] == 206.67 and dec[8] == 206.67 and dec[9] == "" and dec[10] == 320000.0 and dec[11] == 305000.0


def test_the_trend_tab_puts_sales_and_months_on_one_axis():
    sales = sales_of(_units(), CHARACTERISTICS, PLANS)
    rows = trend_rows(sales, (1, 2), today=TODAY)
    header = rows[0]
    assert header[9:] == ["Building 1 median (12 mo)", "Building 2 median (12 mo)", "Building 1 sale", "Building 2 sale", "Building 1 $/sq ft", "Building 2 $/sq ft"]
    assert rows[1][:2] == ["2020-01-01", "month"] and rows[2][:2] == ["2020-01-15", "sale"]
    sale = rows[2]
    assert sale[2] == "A ST" and sale[4] == 300000.0 and sale[5] == 200.0 and sale[11] == 300000.0 and sale[12] == "" and sale[13] == 200.0
    assert sale[6] == 300000.0  # the community median rides on the sale row too, so the line runs through it
    march = next(row for row in rows if row[0] == "2020-03-15")
    assert march[9] == 310000.0  # three building 1 sales by March, so its median appears
    assert all(row[9] == "" for row in rows if row[0] < "2020-03-01")  # the window is read by month, so March's row already holds March's sale


def test_unit_values_estimate_appreciation_and_rank():
    rows = unit_values(_units(), today=TODAY)
    assert rows[0] == UNIT_VALUE_HEADER
    by_address = {row[1]: row for row in rows[1:]}
    one = by_address["A ST"]
    assert one[4] == "2023-01-15" and one[6] == 400000.0 and one[7] == "deed"
    assert one[9] == 450000.0  # community median now is the one 2025 sale
    assert one[12] == 450000.0 and one[13] == 50000.0 and one[14] == 12.5
    assert by_address["B ST"][16] == 1 and by_address["C ST"][16] == 3  # rank in building by appreciation
    assert one[19] == 300000.0 and one[20] == 50.0
    assert one[22] == "community, 12 months, 1 sales"  # building 1 never reaches three sales in 36 months
    assert one[23:] == ["", "", "", "", "", "", "", "", "", "", "no measured area"]
    six = by_address["D ST"]
    assert six[6] == 350000.0 and six[7] == "base" and six[18] == 1
    assert six[17] in (0, 33, 67, 100)
    buildings = building_values(rows, market_index(sales_of(_units()), (1, 2), today=TODAY))
    assert buildings[1][0] == 1 and buildings[1][1] == 3 and buildings[1][8] == 2  # C ST sold this year at the comp itself
    assert buildings[2][0] == 2 and buildings[2][3] == ""


def test_unit_values_add_the_size_adjusted_estimate():
    rows = unit_values(_units(), today=TODAY, characteristics=CHARACTERISTICS, plans=PLANS)
    by_address = {row[1]: row for row in rows[1:]}
    one = by_address["A ST"]
    assert one[23:28] == [3, 2.5, 1500, 2020, "Plan 1"]
    assert one[28] == 266.67  # 400,000 over 1,500 sq ft
    assert one[29] == 450.0  # the one 2025 sale, C ST at 450 a foot
    assert one[31] == 675000.0 and one[32] == 68.8 and one[33] == "community, 12 months, 1 sales"
    assert by_address["D ST"][25] == "" and by_address["D ST"][31] == "" and by_address["D ST"][33] == "no measured area"
    buildings = building_values(rows, market_index(sales_of(_units(), CHARACTERISTICS, PLANS), (1, 2), today=TODAY))
    assert buildings[0][9:] == ["Mean living sq ft", "Median last $/sq ft", "Building $/sq ft now (12 mo)", "Mean size-adjusted estimate"]
    assert buildings[1][9] == 1333 and buildings[1][10] == 266.67


def test_by_size_by_plan_and_the_unit_paths():
    sales = sales_of(_units(), CHARACTERISTICS, PLANS)
    size = by_size_rows(sales, today=TODAY)
    assert size[0][9:] == ["2 bedrooms", "3 bedrooms", "Last 5 years"]
    assert size[1][0] == 1000 and size[1][9] == 320000.0 and size[1][10] == ""
    assert [row[11] for row in size[1:]].count("") == 3  # 2020 sales fall outside the last five years from 2025-09
    values = unit_values(_units(), today=TODAY, characteristics=CHARACTERISTICS, plans=PLANS)
    plan = by_plan_rows(sales, values, PLANS, today=TODAY)
    labels = [row[0] for row in plan[1:]]
    assert labels == ["Plan 1", "2 bedrooms, 1000 sq ft, no plan matched", "no characteristics"]
    assert plan[1][1:5] == ["Watt Communities at Mystique", 3, 2.5, 1500] and plan[1][6] == 2 and plan[1][8] == 3 and plan[1][9] == 310000.0
    assert plan[2][2] == 2 and plan[2][8] == 2 and plan[2][13] == "2025-02-15"
    paths = unit_paths(sales, values, today=TODAY)
    assert paths[0] == ["Month", "A ST", "B ST", "C ST", "D ST"]
    jan = paths[1]
    assert jan[0] == "'2020-01" and jan[1] == 300000.0 and jan[2] == "" and jan[4] == ""
    dec = next(row for row in paths if row[0] == "'2020-12")
    assert dec[1] == 310000.0  # 300,000 carried by 310,000 over the 300,000 median when it sold
    assert paths[-1][1] == 450000.0  # the 2023 resale at 400,000 carried by 450,000 over 400,000


def test_the_lookup_tab_and_the_requests():
    rows = lookup_rows("A ST", 3)
    assert rows[0][1] == "A ST" and rows[2][0] == "Building" and rows[2][1].startswith("=IFERROR(INDEX('Unit values'!A:A")
    assert rows[LOOKUP_HISTORY_ROW][0] == "Sales history" and rows[LOOKUP_HISTORY_ROW][9] == "Month"
    assert rows[LOOKUP_HISTORY_ROW][LOOKUP_MONTH_COLUMN:] == ["Month", "Community median (12 mo)", "Building median (12 mo)", "This unit, indexed value", "This unit, sale"]
    first = LOOKUP_HISTORY_ROW + 1
    assert rows[first][0].startswith("=IFERROR(FILTER(Sales!A:H, Sales!D:D=$B$1)")
    assert rows[first][12].startswith(f"=IFERROR(IF(A{first + 1}=")
    assert rows[first + 1][9] == f'=IF(A{first + 2}="", "", B{first + 2})'
    assert rows[first][LOOKUP_MONTH_COLUMN] == "=IF('Market index'!A2=\"\", \"\", 'Market index'!A2)"
    assert "SUMIFS(Sales!$G:$G" in rows[first + 2][LOOKUP_MONTH_COLUMN + 4]
    assert len(rows[first + 3]) == 14  # three months of formulas, then the plain spill rows
    tabs = equity_chart_tabs(_units(), today=TODAY, characteristics=CHARACTERISTICS, plans=PLANS)
    assert list(tabs) == ["Sales", "Market index", "Trend", "Unit values", "Building values", "By size", "By plan", "Unit paths", "Unit lookup", "Charts"]
    ids = {name: index for index, name in enumerate(tabs)}
    sizes = {name: len(rows) for name, rows in tabs.items()}
    widths = {name: len(rows[0]) for name, rows in tabs.items()}
    headers = {name: [str(cell) for cell in rows[0]] for name, rows in tabs.items()}
    requests = equity_chart_requests(ids, sizes, widths, headers)
    kinds = [r["addChart"]["chart"]["spec"]["basicChart"]["chartType"] for r in requests if "addChart" in r]
    assert kinds == ["LINE", "LINE", "LINE", "LINE", "SCATTER", "SCATTER", "SCATTER", "SCATTER", "COLUMN", "BAR", "SCATTER", "SCATTER", "COLUMN", "COLUMN", "LINE", "LINE"]
    charts = [r["addChart"]["chart"] for r in requests if "addChart" in r]
    trend = charts[4]["spec"]["basicChart"]
    assert trend["domains"][0]["domain"]["sourceRange"]["sources"][0]["sheetId"] == ids["Trend"]
    assert trend["series"][0]["pointStyle"] == {"size": 5, "shape": "CIRCLE"} and "lineStyle" not in trend["series"][0]
    assert trend["series"][-2]["lineStyle"] == {"type": "SOLID", "width": 3} and trend["series"][-1]["lineStyle"]["type"] == "MEDIUM_DASHED"
    paired = charts[5]["spec"]["basicChart"]["series"]
    assert paired[0]["colorStyle"] == paired[2]["colorStyle"]  # building 1's points and its median line share a color
    bar = charts[9]["spec"]["basicChart"]
    assert all(series["targetAxis"] == "BOTTOM_AXIS" for series in bar["series"])
    monthly = charts[-1]
    assert monthly["spec"]["basicChart"]["domains"][0]["domain"]["sourceRange"]["sources"][0]["startColumnIndex"] == LOOKUP_MONTH_COLUMN
    assert monthly["spec"]["basicChart"]["series"][-1]["lineStyle"]["type"] == "INVISIBLE"
    assert monthly["spec"]["basicChart"]["series"][0]["series"]["sourceRange"]["sources"][0]["endRowIndex"] == LOOKUP_HISTORY_ROW + 1 + (sizes["Market index"] - 1)
    assert [r["repeatCell"]["range"]["sheetId"] for r in date_format_requests(ids, sizes)] == [
        ids["Sales"], ids["Unit values"], ids["Trend"], ids["By size"], ids["By plan"], ids["Unit lookup"], ids["Unit lookup"],
    ]
    assert tabs["Sales"][1][1].startswith("'") and tabs["Market index"][1][0].startswith("'")
    validation = next(r for r in requests if "setDataValidation" in r)
    assert validation["setDataValidation"]["rule"]["condition"]["type"] == "ONE_OF_RANGE"

    class Sheets:
        def __init__(self):
            self.batches = []
            self.gets = []

        def create(self, title, *, sheet_titles=None):
            return {"spreadsheetId": "s", "sheets": [{"properties": {"title": n, "sheetId": i}} for i, n in enumerate(sheet_titles)]}

        def get(self, spreadsheet_id, fields=""):
            self.gets.append(fields)
            sheets = [{"properties": {"title": n, "sheetId": i}} for i, n in enumerate(("Sales", "Unit lookup", "Charts"))]
            sheets[2]["charts"] = [{"chartId": 77}]
            return {"spreadsheetId": spreadsheet_id, "sheets": sheets}

        def values_update(self, spreadsheet_id, range_a1, rows):
            pass

        def batch_update(self, spreadsheet_id, requests):
            self.batches.append(requests)

    report = create_equity_chart_sheet(Sheets(), "t", tabs)
    assert report.charts == 16
    refreshed = Sheets()
    report = create_equity_chart_sheet(refreshed, "t", tabs, spreadsheet_id="existing")
    assert report.spreadsheet_id == "existing"
    added = refreshed.batches[0]
    assert [r["addSheet"]["properties"]["title"] for r in added] == ["Market index", "Trend", "Unit values", "Building values", "By size", "By plan", "Unit paths"]
    clearing = refreshed.batches[1]
    assert {"deleteEmbeddedObject": {"objectId": 77}} in clearing
    assert sum(1 for r in clearing if "updateCells" in r) == 3  # the three tabs that already existed are cleared
