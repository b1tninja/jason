"""Write a who-owes report into a Google Sheet for human review.

This is a handoff surface only: Jason writes unit/owner/balance/aging rows
for a person to review. It does not submit anything to a collection agency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from jason.tasks.who_owes import WhoOwesReport, WhoOwesRow

HEADER = ("Unit", "Owner", "Balance", "Past due")
DEFAULT_RANGE = "A1"


@dataclass
class WhoOwesSheetWrite:
    spreadsheet_id: str
    range_a1: str
    row_count: int
    updated: dict[str, Any]

    def summary(self) -> str:
        return (
            f"spreadsheet={self.spreadsheet_id} "
            f"rows={self.row_count} "
            f"range={self.range_a1}"
        )


def _cents_to_sheet(value: int | None) -> float | str:
    if value is None:
        return ""
    return value / 100


def who_owes_sheet_rows(
    rows: Sequence[WhoOwesRow] | WhoOwesReport,
) -> list[list[Any]]:
    """Build header + data rows: unit, owner, balance, past due (dollars)."""
    source: Iterable[WhoOwesRow]
    if isinstance(rows, WhoOwesReport):
        source = rows.rows
    else:
        source = rows
    out: list[list[Any]] = [list(HEADER)]
    for row in source:
        out.append(
            [
                row.unit_label,
                row.owner_name,
                _cents_to_sheet(row.unpaid_amount_cents),
                _cents_to_sheet(row.past_due_balance_cents),
            ]
        )
    return out


def write_who_owes_sheet(
    report: WhoOwesReport | Sequence[WhoOwesRow],
    sheets: Any,
    spreadsheet_id: str,
    *,
    range_a1: str = DEFAULT_RANGE,
) -> WhoOwesSheetWrite:
    """Overwrite ``range_a1`` with a clear header row and who-owes data.

    Balance and Aging are unpaid and past-due amounts from the report,
    written as dollars (PayHOA stores integer cents).
    """
    if not spreadsheet_id:
        raise ValueError("google_sheets_spreadsheet_id is empty")
    values = who_owes_sheet_rows(report)
    updated = sheets.values_update(spreadsheet_id, range_a1, values)
    data_rows = len(values) - 1
    return WhoOwesSheetWrite(
        spreadsheet_id=spreadsheet_id,
        range_a1=range_a1,
        row_count=data_rows,
        updated=updated if isinstance(updated, dict) else {},
    )
