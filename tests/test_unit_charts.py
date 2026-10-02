from jason.community import mystique
from jason.tasks.unit_charts import chart_requests, create_unit_chart_sheet, unit_chart_tabs


def test_the_unit_tabs_show_both_numberings_and_the_overlap():
    blocks = mystique().unit_blocks()
    tabs = unit_chart_tabs(blocks, ())
    units = tabs["Unit numbers"]
    assert units[0][:4] == ["Building", "Numbering", "Unit", "Parcel"] and len(units) == 82
    row = next(r for r in units[1:] if r[3] == "201-1170-024-0004")
    assert row[:3] == [3, "2007 plan", 24] and row[5] == "building 4 201-1170-025-0020" and row[6] == "yes"
    watt = next(r for r in units[1:] if r[3] == "201-1170-025-0020")
    assert watt[:3] == [4, "Watt numbering", 24] and watt[6] == "no"
    overlap = tabs["Overlap"]
    assert [r[0] for r in overlap[1:]] == list(range(21, 33))
    assert overlap[1][1:3] == [3, "201-1170-024-0001"] and overlap[1][4:6] == [4, "201-1170-025-0017"]
    number_map = tabs["Number map"]
    assert number_map[24] == [24, 3, 4] and number_map[1] == [1, "", 1] and number_map[91] == [91, 8, ""]
    per_unit = tabs["Parcels per unit"]
    assert per_unit[24] == [24, 2] and per_unit[5] == [5, 1] and per_unit[60] == [60, 0]


def test_chart_requests_anchor_three_charts_on_the_charts_tab():
    ids = {"Number map": 1, "Parcels per unit": 2, "Sales by building": 3, "Charts": 9}
    sizes = {"Number map": 93, "Parcels per unit": 93, "Sales by building": 50, "Sales by building columns": 12}
    requests = chart_requests(ids, sizes)
    assert len(requests) == 3
    kinds = [r["addChart"]["chart"]["spec"]["basicChart"]["chartType"] for r in requests]
    assert kinds == ["SCATTER", "COLUMN", "SCATTER"]
    first = requests[0]["addChart"]["chart"]
    assert first["position"]["overlayPosition"]["anchorCell"]["sheetId"] == 9
    assert len(first["spec"]["basicChart"]["series"]) == 2
    assert len(requests[2]["addChart"]["chart"]["spec"]["basicChart"]["series"]) == 8
    assert chart_requests({"Number map": 1}, sizes) == []


def test_the_sheet_is_created_filled_and_charted():
    class Sheets:
        def __init__(self):
            self.updates = []
            self.batches = []

        def create(self, title, *, sheet_titles=None):
            return {"spreadsheetId": "sheet1", "sheets": [{"properties": {"title": name, "sheetId": index}} for index, name in enumerate(sheet_titles)]}

        def values_update(self, spreadsheet_id, range_a1, rows):
            self.updates.append((range_a1, len(rows)))

        def batch_update(self, spreadsheet_id, requests):
            self.batches.append(requests)

    sheets = Sheets()
    tabs = unit_chart_tabs(mystique().unit_blocks(), ())
    report = create_unit_chart_sheet(sheets, "test", tabs)
    assert report.spreadsheet_id == "sheet1" and report.charts == 3
    assert [name for name, _ in report.counts] == ["Unit numbers", "Overlap", "Number map", "Parcels per unit", "Sales by building", "Charts"]
    assert sum(1 for r in sheets.batches[0] if "addChart" in r) == 3
    assert "charts=3" in report.summary()
