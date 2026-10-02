"""Sheets API helper for reading and writing cell ranges."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx

from jason.google.errors import GoogleError

_API = "https://sheets.googleapis.com/v4"


class GoogleSheets:
    """Authenticated Sheets v4 client. Share the Drive client's access token."""

    def __init__(
        self,
        access_token: str,
        *,
        http: httpx.Client | None = None,
        owns_http: bool = False,
    ) -> None:
        if not access_token:
            raise GoogleError("missing access token")
        self._token = access_token
        self._http = http or httpx.Client(timeout=60.0)
        self._owns_http = http is None or owns_http

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def create(
        self, title: str, *, sheet_titles: tuple[str, ...] | None = None
    ) -> dict[str, Any]:
        """Create a new spreadsheet. Does not modify an existing file."""
        if not title.strip():
            raise GoogleError("missing spreadsheet title")
        body: dict[str, Any] = {"properties": {"title": title}}
        if sheet_titles:
            body["sheets"] = [
                {"properties": {"title": name}} for name in sheet_titles
            ]
        response = self._http.post(
            f"{_API}/spreadsheets",
            headers={**self._headers(), "Content-Type": "application/json"},
            content=json.dumps(body),
        )
        return _ok(response, f"creating spreadsheet {title}")

    def batch_update(
        self, spreadsheet_id: str, requests: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Apply spreadsheet edits such as row height and a frozen header."""
        if not requests:
            raise GoogleError("batch_update needs at least one request")
        response = self._http.post(
            f"{_API}/spreadsheets/{spreadsheet_id}:batchUpdate",
            headers={**self._headers(), "Content-Type": "application/json"},
            content=json.dumps({"requests": requests}),
        )
        return _ok(response, f"updating spreadsheet {spreadsheet_id}")

    def values_get(self, spreadsheet_id: str, range_a1: str) -> dict[str, Any]:
        """Read a range via spreadsheets.values.get."""
        url = self._values_url(spreadsheet_id, range_a1)
        response = self._http.get(url, headers=self._headers())
        return _ok(response, f"reading {spreadsheet_id} {range_a1}")

    def values_update(
        self,
        spreadsheet_id: str,
        range_a1: str,
        rows: list[list[Any]],
    ) -> dict[str, Any]:
        """Write a range via spreadsheets.values.update (USER_ENTERED)."""
        if not rows:
            raise GoogleError("values_update needs at least one row")
        url = self._values_url(spreadsheet_id, range_a1)
        response = self._http.put(
            url,
            params={"valueInputOption": "USER_ENTERED"},
            headers={**self._headers(), "Content-Type": "application/json"},
            content=json.dumps({"values": rows}),
        )
        return _ok(response, f"updating {spreadsheet_id} {range_a1}")

    def values_batch_update(self, spreadsheet_id: str, data: list[dict[str, Any]]) -> dict[str, Any]:
        """Write several ranges in one atomic request (``values:batchUpdate``, USER_ENTERED). ``data`` is
        ``[{"range": "Items!C7", "values": [["open"]]}, ...]``; cells outside them are untouched."""
        if not data:
            raise GoogleError("values_batch_update needs at least one range")
        response = self._http.post(
            f"{_API}/spreadsheets/{spreadsheet_id}/values:batchUpdate",
            headers={**self._headers(), "Content-Type": "application/json"},
            content=json.dumps({"valueInputOption": "USER_ENTERED", "data": data}),
        )
        return _ok(response, f"updating ranges of {spreadsheet_id}")

    def values_append(self, spreadsheet_id: str, range_a1: str, rows: list[list[Any]]) -> dict[str, Any]:
        """Append rows after the last row of a table (``values:append``, INSERT_ROWS); existing rows are untouched."""
        if not rows:
            raise GoogleError("values_append needs at least one row")
        response = self._http.post(
            self._values_url(spreadsheet_id, range_a1) + ":append",
            params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            headers={**self._headers(), "Content-Type": "application/json"},
            content=json.dumps({"values": rows}),
        )
        return _ok(response, f"appending to {spreadsheet_id} {range_a1}")

    def get(
        self,
        spreadsheet_id: str,
        *,
        ranges: list[str] | None = None,
        include_grid: bool = False,
        fields: str | None = None,
    ) -> dict[str, Any]:
        """Read spreadsheet metadata. ``include_grid`` returns cell values and links."""
        if not spreadsheet_id:
            raise GoogleError("missing spreadsheet_id")
        params: list[tuple[str, str]] = []
        for item in ranges or []:
            params.append(("ranges", item))
        if include_grid:
            params.append(("includeGridData", "true"))
        if fields:
            params.append(("fields", fields))
        response = self._http.get(
            f"{_API}/spreadsheets/{spreadsheet_id}",
            params=params or None,
            headers=self._headers(),
        )
        return _ok(response, f"reading spreadsheet {spreadsheet_id}")

    def sheet_titles(self, spreadsheet_id: str) -> list[str]:
        body = self.get(spreadsheet_id, fields="sheets.properties.title")
        titles: list[str] = []
        for sheet in body.get("sheets") or []:
            props = sheet.get("properties") if isinstance(sheet, dict) else None
            title = (props or {}).get("title") if isinstance(props, dict) else None
            if title:
                titles.append(str(title))
        return titles

    def grid(self, spreadsheet_id: str, range_a1: str) -> list[list[dict[str, str]]]:
        """Cell values and hyperlinks for one range. Empty cells are omitted from the tail."""
        body = self.get(
            spreadsheet_id,
            ranges=[range_a1],
            include_grid=True,
            fields="sheets.data.rowData.values(formattedValue,hyperlink)",
        )
        return parse_grid(body)

    def _values_url(self, spreadsheet_id: str, range_a1: str) -> str:
        if not spreadsheet_id:
            raise GoogleError("missing spreadsheet_id")
        if not range_a1:
            raise GoogleError("missing range")
        encoded = quote(range_a1, safe="")
        return f"{_API}/spreadsheets/{spreadsheet_id}/values/{encoded}"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}


def _ok(response: httpx.Response, action: str) -> dict[str, Any]:
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    if not response.is_success:
        message = ""
        error = body.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or "")
        detail = f": {message}" if message else ""
        raise GoogleError(f"HTTP {response.status_code} {action}{detail}")
    return body


def parse_grid(body: dict[str, Any]) -> list[list[dict[str, str]]]:
    """Turn a spreadsheets.get grid payload into rows of ``{value, link}``."""
    sheets = body.get("sheets") or []
    data = []
    if sheets and isinstance(sheets[0], dict):
        data = sheets[0].get("data") or []
    row_data = []
    if data and isinstance(data[0], dict):
        row_data = data[0].get("rowData") or []
    rows: list[list[dict[str, str]]] = []
    for raw in row_data:
        cells: list[dict[str, str]] = []
        values = raw.get("values") if isinstance(raw, dict) else None
        for cell in values or []:
            if not isinstance(cell, dict):
                cells.append({"value": "", "link": ""})
                continue
            cells.append(
                {
                    "value": str(cell.get("formattedValue") or ""),
                    "link": str(cell.get("hyperlink") or ""),
                }
            )
        rows.append(cells)
    return rows
