from datetime import date

from jason.tasks.ownership_sheet import HEADER, OwnershipSheetRow, create_ownership_sheet, open_sheet, ownership_sheet_values


class _Sheets:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.updates: list[tuple[str, str]] = []

    def create(self, title: str):
        self.created.append(title)
        return {"spreadsheetId": "new-sheet-id"}

    def values_update(self, spreadsheet_id: str, range_a1: str, rows):
        self.updates.append((spreadsheet_id, range_a1))
        assert rows[0] == list(HEADER)
        return {"updatedRows": len(rows)}


def test_create_writes_a_new_spreadsheet_not_an_existing_one():
    row = OwnershipSheetRow(
        "20111700220010",
        "3044 MACON DR",
        date(2020, 6, 19).isoformat(),
        "GD",
        "202006190506",
        "WATT COMMUNITIES AT MYSTIQUE LLC",
        "ARKWRIGHT LENA E",
        True,
    )
    sheets = _Sheets()
    result = create_ownership_sheet(sheets, "Mystique ownership", [row])
    assert sheets.created == ["Mystique ownership"]
    assert sheets.updates == [("new-sheet-id", "A1")]
    assert result.spreadsheet_id == "new-sheet-id"
    assert result.url.endswith("/new-sheet-id")
    assert ownership_sheet_values([row])[1][4] == "202006190506"


def test_open_sheet_uses_the_given_browser():
    opened: list[str] = []

    def opener(url: str) -> bool:
        opened.append(url)
        return True

    assert open_sheet("https://docs.google.com/spreadsheets/d/abc", opener) is True
    assert opened == ["https://docs.google.com/spreadsheets/d/abc"]
