"""Sheets helper reads and writes value ranges."""

import json

import httpx

from jason.google.errors import GoogleError
from jason.google.sheets import GoogleSheets, parse_grid


class _Http:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []
        self.params: object | None = None
        self.body: object | None = None

    def get(self, url, *, params=None, headers=None):
        self.calls.append(("GET", url))
        self.params = params
        return self.responses.pop(0)

    def put(self, url, *, params=None, content=None, headers=None):
        self.calls.append(("PUT", url))
        self.params = params
        self.body = content
        return self.responses.pop(0)

    def close(self) -> None:
        return None


def _response(status: int, body: dict | bytes, *, text: str = "") -> httpx.Response:
    content = body if isinstance(body, bytes) else json.dumps(body).encode()
    return httpx.Response(status, content=content, text=text or content.decode())


def test_values_get_returns_body():
    http = _Http(
        [
            _response(
                200,
                {"range": "Sheet1!A1:B2", "values": [["Name", "Balance"], ["Ada", "10"]]},
            )
        ]
    )
    sheets = GoogleSheets("token", http=http)  # type: ignore[arg-type]
    body = sheets.values_get("sheet-1", "Sheet1!A1:B2")
    assert body["values"][0] == ["Name", "Balance"]
    assert http.calls[0] == (
        "GET",
        "https://sheets.googleapis.com/v4/spreadsheets/sheet-1/values/Sheet1%21A1%3AB2",
    )


def test_values_update_puts_user_entered_rows():
    http = _Http(
        [
            _response(
                200,
                {
                    "spreadsheetId": "sheet-1",
                    "updatedRange": "Sheet1!A1:B1",
                    "updatedRows": 1,
                },
            )
        ]
    )
    sheets = GoogleSheets("token", http=http)  # type: ignore[arg-type]
    rows = [["Ada", "10"]]
    body = sheets.values_update("sheet-1", "Sheet1!A1:B1", rows)
    assert body["updatedRows"] == 1
    assert http.calls[0] == (
        "PUT",
        "https://sheets.googleapis.com/v4/spreadsheets/sheet-1/values/Sheet1%21A1%3AB1",
    )
    assert http.params == {"valueInputOption": "USER_ENTERED"}
    assert json.loads(http.body) == {"values": rows}


def test_values_update_rejects_empty_rows():
    sheets = GoogleSheets("token", http=_Http([]))  # type: ignore[arg-type]
    try:
        sheets.values_update("sheet-1", "Sheet1!A1", [])
    except GoogleError as exc:
        assert "at least one" in str(exc)
    else:
        raise AssertionError("expected GoogleError")


def test_sheet_titles_and_grid_links():
    http = _Http(
        [
            _response(
                200,
                {"sheets": [{"properties": {"title": "Insurance"}}, {"properties": {"title": "Budget"}}]},
            ),
            _response(
                200,
                {
                    "sheets": [
                        {
                            "data": [
                                {
                                    "rowData": [
                                        {
                                            "values": [
                                                {"formattedValue": "Policy"},
                                                {"formattedValue": "HOA-1", "hyperlink": "https://drive.example/policy"},
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                },
            ),
        ]
    )
    sheets = GoogleSheets("token", http=http)  # type: ignore[arg-type]
    assert sheets.sheet_titles("sheet-1") == ["Insurance", "Budget"]
    grid = sheets.grid("sheet-1", "Insurance!A1:B2")
    assert grid[0][1] == {"value": "HOA-1", "link": "https://drive.example/policy"}
    assert "includeGridData" in str(http.params)


def test_parse_grid_skips_missing_cells():
    rows = parse_grid({"sheets": [{"data": [{"rowData": [{}]}]}]})
    assert rows == [[]]
