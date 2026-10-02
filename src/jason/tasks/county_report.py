"""One spreadsheet of county deed and tax reports. Tabs, not the Membership workbook.

Ownership is the assessor's current instrument. Deed history is the pinned
grant-deed chain. Association taxes are the common-area bills. Sale prices are
the enrolled value in the year it rose by more than 2% after each recording on
a stored chain. Taxes due marks an unpaid older year delinquent and the newest
year due.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jason.community.ownership import OwnershipHistory
from jason.community.tax import TaxAccount, enrolled_cents, reassessment, reassessment_for
from jason.tasks.ownership_sheet import OwnershipSheetRow, ownership_sheet_values

TABS = ("Ownership", "Deed history", "Association taxes", "Sale prices", "Taxes due")


@dataclass
class CountyReport:
    spreadsheet_id: str
    title: str
    url: str
    counts: tuple[tuple[str, int], ...]

    def summary(self) -> str:
        tabs = " ".join(f"{name}={count}" for name, count in self.counts)
        return f"spreadsheet={self.spreadsheet_id} {tabs} url={self.url}"


def dollars(cents: int | None) -> str:
    """Dollars and cents from an integer cent amount. Blank when unknown."""
    if cents is None:
        return ""
    sign = "-" if cents < 0 else ""
    amount = abs(cents)
    return f"{sign}{amount // 100}.{amount % 100:02d}"


def deed_history_values(history: OwnershipHistory) -> list[list[Any]]:
    """One row per instrument in the pinned chain, newest first."""
    rows: list[list[Any]] = [[
        "APN", "Document No", "Date", "Grantors", "Grantees", "Priors", "Gap",
    ]]
    gaps = set(history.gaps)
    for step in history.steps:
        item = step.conveyance
        rows.append([
            history.apn or item.apn,
            item.number,
            item.recorded.isoformat() if item.recorded else "",
            "\n".join(item.grantors),
            "\n".join(item.grantees),
            "\n".join(step.priors),
            "yes" if item.number in gaps else "",
        ])
    return rows


def association_tax_values(accounts: tuple[TaxAccount, ...] | list[TaxAccount]) -> list[list[Any]]:
    """Every stored bill for the association's common-area parcels."""
    rows: list[list[Any]] = [[
        "APN", "Address", "Year", "Enrolled", "Net assessed",
        "Ad valorem", "Direct", "Total", "Payments", "Balance",
    ]]
    for account in accounts:
        for bill in sorted(account.bills, key=lambda item: (item.year is None, -(item.year or 0))):
            rows.append([
                account.apn,
                account.address,
                "" if bill.year is None else bill.year,
                dollars(enrolled_cents(bill)),
                dollars(bill.net_assessed_cents),
                dollars(bill.ad_valorem_cents),
                dollars(bill.direct_cents),
                dollars(bill.total_cents),
                dollars(bill.payments_cents),
                dollars(bill.balance_cents),
            ])
    return rows


def sale_price_values(
    accounts: tuple[TaxAccount, ...] | list[TaxAccount],
    ownership: tuple[OwnershipSheetRow, ...] | list[OwnershipSheetRow] = (),
    histories: tuple[OwnershipHistory, ...] | list[OwnershipHistory] = (),
) -> list[list[Any]]:
    """Enrolled value after each sale on a stored chain.

    When ``histories`` has a parcel, every conveyance on that chain gets a row.
    The enrolled figure is the jump that follows that recording. When the
    catalog has no matching jump, the price columns stay blank. Parcels with
    no chain keep one row for the latest reassessment and the current document
    number from ``ownership``.
    """
    by_parcel = {_parcel_key(row.apn): row for row in ownership}
    by_history = {_parcel_key(item.apn): item for item in histories if item.apn}
    rows: list[list[Any]] = [[
        "APN", "Address", "Year", "Enrolled", "Prior year", "Prior enrolled",
        "Document No", "Type", "Recorded", "Grantors", "Grantees",
    ]]
    for account in accounts:
        key = _parcel_key(account.apn)
        history = by_history.get(key)
        if history is not None and history.steps:
            for step in history.steps:
                item = step.conveyance
                found = reassessment_for(account.bills, item.recorded)
                rows.append(_sale_row(account, found, item.number, "", item))
            continue
        deed = by_parcel.get(key)
        number = deed.document_number if deed else ""
        kind = deed.document_type if deed else ""
        found = reassessment(account.bills)
        rows.append(_sale_row(account, found, number, kind, None))
    return rows


def _sale_row(
    account: TaxAccount,
    found,
    number: str,
    kind: str,
    conveyance,
) -> list[Any]:
    recorded = ""
    grantors = ""
    grantees = ""
    if conveyance is not None:
        recorded = conveyance.recorded.isoformat() if conveyance.recorded else ""
        grantors = "\n".join(conveyance.grantors)
        grantees = "\n".join(conveyance.grantees)
    if found is None:
        return [
            account.apn, account.address, "", "", "", "",
            number, kind, recorded, grantors, grantees,
        ]
    return [
        account.apn,
        account.address,
        found.year,
        dollars(found.enrolled_cents),
        found.prior_year,
        dollars(found.prior_enrolled_cents),
        number,
        kind,
        recorded,
        grantors,
        grantees,
    ]


def _parcel_key(apn: str) -> str:
    return "".join(character for character in apn if character.isdigit())


def taxes_due_values(accounts: tuple[TaxAccount, ...] | list[TaxAccount]) -> list[list[Any]]:
    """Newest bill is due. An unpaid older year is delinquent."""
    rows: list[list[Any]] = [[
        "APN", "Address", "Status", "Year", "Due", "Delinquent",
    ]]
    for account in accounts:
        status, year, due, delinquent = _due(account)
        rows.append([
            account.apn,
            account.address,
            status,
            "" if year is None else year,
            dollars(due),
            dollars(delinquent),
        ])
    return rows


def _due(account: TaxAccount) -> tuple[str, int | None, int, int]:
    yearly = [bill for bill in account.bills if bill.year is not None]
    if not yearly:
        return "", None, 0, 0
    newest = max(bill.year for bill in yearly if bill.year is not None)
    due = 0
    delinquent = 0
    for bill in yearly:
        balance = bill.balance_cents or 0
        if bill.year == newest:
            due += balance
        elif balance > 0:
            delinquent += balance
    if delinquent > 0:
        status = "delinquent"
    elif due > 0:
        status = "due"
    else:
        status = "paid"
    return status, newest, due, delinquent


def ownership_on_file(
    store: Any, apns: tuple[str, ...]
) -> tuple[OwnershipSheetRow, ...]:
    """Current instruments already in the ownership database. No assessor call."""
    rows: list[OwnershipSheetRow] = []
    for apn in apns:
        record = store.get(apn)
        if record is None:
            continue
        rows.append(
            OwnershipSheetRow(
                record.apn,
                "",
                record.document_date.isoformat(),
                "",
                record.document_number,
                "\n".join(record.grantors),
                "\n".join(record.grantees),
                False,
            )
        )
    return tuple(rows)


def histories_on_file(
    store: Any,
    apns: tuple[str, ...],
    *,
    developers: tuple = (),
) -> tuple[OwnershipHistory, ...]:
    """Stored grant-deed chains for these parcels. A missing chain is skipped."""
    found: list[OwnershipHistory] = []
    for apn in apns:
        history = store.parcel_history(apn, developers=developers)
        if history is None:
            history = store.parcel_history(
                "".join(character for character in apn if character.isdigit()),
                developers=developers,
            )
        if history is not None:
            found.append(history)
    return tuple(found)


def summarize_tabs(tabs: dict[str, list[list[Any]]]) -> str:
    """Row counts for each tab, excluding the header."""
    return " ".join(f"{name}={max(0, len(rows) - 1)}" for name, rows in tabs.items())


def accounts_for(store: Any, apns: tuple[str, ...]) -> tuple[TaxAccount, ...]:
    """Catalog accounts for these parcels, in that order. A missing parcel is skipped."""
    found: list[TaxAccount] = []
    for apn in apns:
        account = store.get(apn)
        if account is not None:
            found.append(account)
    return tuple(found)


def report_tabs(
    ownership: tuple[OwnershipSheetRow, ...] | list[OwnershipSheetRow],
    history: OwnershipHistory,
    common_taxes: tuple[TaxAccount, ...] | list[TaxAccount],
    unit_taxes: tuple[TaxAccount, ...] | list[TaxAccount],
    *,
    unit_histories: tuple[OwnershipHistory, ...] | list[OwnershipHistory] = (),
) -> dict[str, list[list[Any]]]:
    return {
        "Ownership": ownership_sheet_values(ownership),
        "Deed history": deed_history_values(history),
        "Association taxes": association_tax_values(common_taxes),
        "Sale prices": sale_price_values(unit_taxes, ownership, unit_histories),
        "Taxes due": taxes_due_values(tuple(common_taxes) + tuple(unit_taxes)),
    }


def create_county_report(sheets: Any, title: str, tabs: dict[str, list[list[Any]]]) -> CountyReport:
    """Create a spreadsheet with one tab per report. Does not open an existing file."""
    names = tuple(name for name in TABS if name in tabs)
    created = sheets.create(title, sheet_titles=names)
    spreadsheet_id = str(created.get("spreadsheetId") or "")
    if not spreadsheet_id:
        raise ValueError("spreadsheet was not created")
    counts: list[tuple[str, int]] = []
    for name in names:
        values = tabs[name]
        sheets.values_update(spreadsheet_id, f"'{name}'!A1", values)
        counts.append((name, max(0, len(values) - 1)))
    return CountyReport(
        spreadsheet_id=spreadsheet_id,
        title=title,
        url=f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
        counts=tuple(counts),
    )
