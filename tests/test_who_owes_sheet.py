"""Who-owes Google Sheet handoff builds unit/owner/balance/aging rows."""

from jason.tasks.who_owes import WhoOwesReport, WhoOwesRow
from jason.tasks.who_owes_sheet import (
    HEADER,
    who_owes_sheet_rows,
    write_who_owes_sheet,
)


class _Sheets:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, list[list[object]]]] = []

    def values_update(self, spreadsheet_id: str, range_a1: str, rows: list[list[object]]):
        self.calls.append((spreadsheet_id, range_a1, rows))
        return {
            "spreadsheetId": spreadsheet_id,
            "updatedRange": range_a1,
            "updatedRows": len(rows),
        }


def _sample_report() -> WhoOwesReport:
    return WhoOwesReport(
        rows=[
            WhoOwesRow(
                unit_id=10,
                unit_label="Lot 1",
                owner_name="Ada",
                unpaid_amount_cents=15000,
                past_due_balance_cents=500,
            ),
            WhoOwesRow(
                unit_id=11,
                unit_label="Lot 2",
                owner_name="Bob",
                unpaid_amount_cents=0,
                past_due_balance_cents=None,
            ),
        ],
        total_unpaid_cents=15000,
        unit_count=2,
    )


def test_who_owes_sheet_rows_header_and_dollars():
    values = who_owes_sheet_rows(_sample_report())
    assert values[0] == list(HEADER)
    assert values[1] == ["Lot 1", "Ada", 150.0, 5.0]
    assert values[2] == ["Lot 2", "Bob", 0.0, ""]


def test_who_owes_sheet_rows_accepts_row_list():
    row = WhoOwesRow(
        unit_id=1,
        unit_label="A",
        owner_name="X",
        unpaid_amount_cents=100,
        past_due_balance_cents=25,
    )
    values = who_owes_sheet_rows([row])
    assert values == [list(HEADER), ["A", "X", 1.0, 0.25]]


def test_write_who_owes_sheet_updates_values():
    sheets = _Sheets()
    result = write_who_owes_sheet(_sample_report(), sheets, "sheet-abc")
    assert result.spreadsheet_id == "sheet-abc"
    assert result.row_count == 2
    assert result.range_a1 == "A1"
    assert "rows=2" in result.summary()
    assert sheets.calls == [
        (
            "sheet-abc",
            "A1",
            [
                ["Unit", "Owner", "Balance", "Past due"],
                ["Lot 1", "Ada", 150.0, 5.0],
                ["Lot 2", "Bob", 0.0, ""],
            ],
        )
    ]


def test_write_who_owes_sheet_rejects_empty_spreadsheet_id():
    try:
        write_who_owes_sheet(_sample_report(), _Sheets(), "")
    except ValueError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("expected ValueError")
