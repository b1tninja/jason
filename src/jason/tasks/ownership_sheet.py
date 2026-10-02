"""Publish a new Google Sheet of ownership from county records.

The Membership workbook is left as it is. This creates a spreadsheet.
A parcel whose stored document date has not changed is written from the
local row and is not fetched from the recorder again.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jason.community.assessor import Parcel, SacramentoCountyAssessor
from jason.community.ownership import OwnershipStore
from jason.community.recorder import SacramentoCountyRecorder

HEADER = ("APN", "Address", "Date", "Type", "Document No", "Grantors", "Grantees")


@dataclass(frozen=True)
class OwnershipSheetRow:
    apn: str
    address: str
    document_date: str
    document_type: str
    document_number: str
    grantors: str
    grantees: str
    fetched: bool


@dataclass
class OwnershipSheetWrite:
    spreadsheet_id: str
    title: str
    row_count: int
    fetched: int
    url: str

    def summary(self) -> str:
        return (
            f"spreadsheet={self.spreadsheet_id} "
            f"rows={self.row_count} fetched={self.fetched} url={self.url}"
        )


def collect_ownership(
    apns: tuple[str, ...],
    store: OwnershipStore,
    *,
    assessor: SacramentoCountyAssessor | None = None,
    recorder: SacramentoCountyRecorder | None = None,
) -> tuple[OwnershipSheetRow, ...]:
    """Read each parcel from the assessor. Fetch the recorder only when the date changed."""
    office = assessor or SacramentoCountyAssessor()
    index = recorder or SacramentoCountyRecorder()
    rows: list[OwnershipSheetRow] = []
    for apn in apns:
        parcel = office.parcel(apn)
        if parcel is None:
            continue
        fetched = False
        if store.changed(parcel):
            office.ownership(apn, recorder=index, store=store)
            fetched = True
        stored = store.get(parcel.apn)
        rows.append(_row(parcel, stored.grantors if stored else (), stored.grantees if stored else (), fetched))
    return tuple(rows)


def _row(parcel: Parcel, grantors: tuple[str, ...], grantees: tuple[str, ...], fetched: bool) -> OwnershipSheetRow:
    recorded = parcel.document_date.isoformat() if parcel.document_date else ""
    return OwnershipSheetRow(
        parcel.apn,
        parcel.address,
        recorded,
        parcel.document_type,
        parcel.document_number,
        "\n".join(grantors),
        "\n".join(grantees),
        fetched,
    )


def ownership_sheet_values(rows: tuple[OwnershipSheetRow, ...] | list[OwnershipSheetRow]) -> list[list[Any]]:
    values: list[list[Any]] = [list(HEADER)]
    for row in rows:
        values.append(
            [row.apn, row.address, row.document_date, row.document_type, row.document_number, row.grantors, row.grantees]
        )
    return values


def open_sheet(url: str, opener: Any = None) -> bool:
    """Open the new spreadsheet. ``webbrowser`` is optional; a missing module skips the launch."""
    if opener is None:
        try:
            import webbrowser
        except ImportError:
            return False
        opener = webbrowser.open
    return bool(opener(url))


def create_ownership_sheet(sheets: Any, title: str, rows: tuple[OwnershipSheetRow, ...] | list[OwnershipSheetRow]) -> OwnershipSheetWrite:
    """Create a spreadsheet and write the rows. Does not open an existing file."""
    created = sheets.create(title)
    spreadsheet_id = str(created.get("spreadsheetId") or "")
    if not spreadsheet_id:
        raise ValueError("spreadsheet was not created")
    sheets.values_update(spreadsheet_id, "A1", ownership_sheet_values(rows))
    return OwnershipSheetWrite(
        spreadsheet_id=spreadsheet_id,
        title=title,
        row_count=len(rows),
        fetched=sum(1 for row in rows if row.fetched),
        url=f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
    )
