from datetime import date

from jason.community.parcel_history import HistoryStep, ParcelHistory
from jason.tasks.sales_charts import PROCESSES, create_sales_chart_sheet, sales_chart_requests, sales_chart_tabs


def _step(order, number, process, grantors, grantees, *, developer="", price=None, base=None, year=None, reassesses=True):
    recorded = date(int(number[:4]), int(number[4:6]), int(number[6:8]))
    return HistoryStep(
        order, number, recorded, grantors, grantees, (), process, True, reassesses, developer,
        price, None, None, False, year, base, None, "handoff", "", "",
    )


def _parcel(apn, address, building, steps):
    return ParcelHistory(apn, address, None, building, None, "", "", steps[-1].number, steps[-1].recorded, (), steps, (), (), True, 2013, 2025)


def _units():
    one = _parcel("20111700990001", "200 SAMPLE LN", 8, (
        _step(1, "200709280101", "developer closing", ("WL HOMES LLC",), ("ALDERWICK",), developer="John Laing Homes", price=25_000_000),
        _step(2, "201204200202", "resale", ("ALDERWICK",), ("BRACKWATER",), price=10_000_000),
        _step(3, "201408010303", "resale", ("BRACKWATER",), ("DUNSMERE",), price=16_900_000, base=16_900_000, year=2015),
        _step(4, "201710300404", "restatement", ("DUNSMERE",), ("DUNSMERE TR",), reassesses=False),
    ))
    two = _parcel("20111700990002", "100 SAMPLE WALK", 3, (
        _step(1, "200805090505", "developer closing", ("WL HOMES LLC",), ("OLLIVANE",), developer="John Laing Homes"),
        _step(2, "201111210606", "foreclosure", ("ETS",), ("GMAC",)),
        _step(3, "201203270707", "reo resale", ("FNMA",), ("FENWHISTLE",), base=13_000_000, year=2013),
    ))
    return (one, two)


def test_the_tabs_count_conveyances_by_year_and_process():
    tabs = sales_chart_tabs(_units())
    conveyances = tabs["Conveyances"]
    assert len(conveyances) == 8 and conveyances[1][0] == "2007-09-28" and conveyances[1][5] == "developer closing"
    by_year = tabs["By year"]
    assert by_year[0][1:9] == list(PROCESSES)
    row_2012 = next(row for row in by_year[1:] if row[0] == 2012)
    assert row_2012[1 + PROCESSES.index("resale")] == 1 and row_2012[1 + PROCESSES.index("reo resale")] == 1
    assert row_2012[9] == 2 and row_2012[10] == 2 and row_2012[11] == 115000.0  # median of 100,000 and 130,000
    row_2017 = next(row for row in by_year[1:] if row[0] == 2017)
    assert row_2017[1 + PROCESSES.index("restatement")] == 1 and row_2017[10] == 0
    by_process = tabs["By process"]
    assert len(by_process) == 5  # four priced sales; the restatement, the unpriced closing, and the foreclosure are left out
    assert by_process[1][3] == 250000.0  # developer closing column
    building = tabs["By building"]
    assert [row[0] for row in building[1:]] == [3, 8]
    assert building[2][6] == 3 and building[2][7] == 2 and building[1][8] == 1
    tenure = tabs["Tenure"]
    assert [row[3] for row in tenure[1:4]] == ["ALDERWICK", "BRACKWATER", "DUNSMERE"] and tenure[1][6] == 4.6 and tenure[3][7] == "yes"
    assert tabs["Price vs base"][1][:2] == [169000.0, 169000.0] and tabs["Price vs base"][1][4] == 0.0


def test_the_chart_requests_cover_the_six_views():
    ids = {name: index for index, name in enumerate(("Conveyances", "By year", "By process", "By building", "Tenure", "Price vs base", "Charts"))}
    sizes = {name: 20 for name in ids}
    requests = sales_chart_requests(ids, sizes)
    kinds = [r["addChart"]["chart"]["spec"]["basicChart"]["chartType"] for r in requests]
    assert kinds == ["COLUMN", "LINE", "SCATTER", "COLUMN", "COLUMN", "SCATTER"]
    assert requests[0]["addChart"]["chart"]["spec"]["basicChart"]["stackedType"] == "STACKED"
    assert len(requests[2]["addChart"]["chart"]["spec"]["basicChart"]["series"]) == len(PROCESSES)


def test_the_sheet_is_created_and_charted():
    class Sheets:
        def __init__(self):
            self.batches = []

        def create(self, title, *, sheet_titles=None):
            return {"spreadsheetId": "s", "sheets": [{"properties": {"title": n, "sheetId": i}} for i, n in enumerate(sheet_titles)]}

        def values_update(self, spreadsheet_id, range_a1, rows):
            pass

        def batch_update(self, spreadsheet_id, requests):
            self.batches.append(requests)

    sheets = Sheets()
    report = create_sales_chart_sheet(sheets, "t", sales_chart_tabs(_units()))
    assert report.charts == 6 and "charts=6" in report.summary()
