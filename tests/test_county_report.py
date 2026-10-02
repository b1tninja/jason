from datetime import date

from jason.community.recorder import Conveyance, succession
from mystique.developers import DEVELOPERS
from jason.community.tax import (
    TaxAccount,
    TaxBill,
    reassessment,
    reassessment_for,
    reassessment_year_for,
)
from jason.tasks.county_report import (
    association_tax_values,
    create_county_report,
    deed_history_values,
    sale_price_values,
    taxes_due_values,
)
from jason.tasks.ownership_sheet import OwnershipSheetRow


def _bill(year: int, land: int, *, balance: int = 0, total: int = 0) -> TaxBill:
    return TaxBill(
        number=str(year),
        name=f"{year} Secured",
        year=year,
        land_cents=land,
        improvement_cents=0,
        balance_cents=balance,
        total_cents=total,
        ad_valorem_cents=total,
        direct_cents=0,
        net_assessed_cents=land,
    )


def test_the_latest_jump_past_two_percent_is_the_enrolled_figure():
    found = reassessment((
        _bill(2016, 15_140_500),
        _bill(2017, 20_000_000),
        _bill(2018, 20_400_000),
    ))
    assert found is not None
    assert found.year == 2017
    assert found.enrolled_cents == 20_000_000
    assert found.prior_year == 2016


def test_an_exact_two_percent_rise_is_not_a_reassessment():
    assert reassessment((_bill(2017, 10_000), _bill(2018, 10_200))) is None


def test_the_reassessment_year_follows_the_recording():
    assert reassessment_year_for(date(2020, 11, 13)) == 2021
    assert reassessment_year_for(date(2021, 1, 1)) == 2021
    assert reassessment_year_for(date(2021, 1, 2)) == 2022


def test_each_sale_gets_the_jump_that_follows_its_recording():
    bills = (
        _bill(2020, 16_402_800),
        _bill(2021, 33_000_000),
        _bill(2022, 33_660_000),
        _bill(2023, 50_082_000),
    )
    first = reassessment_for(bills, date(2020, 11, 13))
    assert first is not None
    assert first.year == 2021
    assert first.enrolled_cents == 33_000_000
    second = reassessment_for(bills, date(2022, 5, 12))
    assert second is not None
    assert second.year == 2023
    assert second.enrolled_cents == 50_082_000
    assert reassessment_for(bills, date(2024, 7, 1)) is None


def test_deed_history_marks_the_gap():
    history = succession(
        (
            Conveyance("202203180704", date(2022, 3, 18), ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("MYSTIQUE COMMUNITY ASSOCIATION",)),
            Conveyance("200605041076", date(2006, 5, 4), ("REYNEN & BARDIS COMMUNITIES INC",), ("WL HOMES LLC",)),
        ),
        apn="",
        developers=DEVELOPERS,
    )
    rows = deed_history_values(history)
    assert rows[0][1] == "Document No"
    assert rows[1][1] == "202203180704"
    assert rows[1][6] == ""
    assert rows[2][1] == "200605041076"
    assert rows[2][6] == "yes"


def test_sale_price_and_taxes_due_use_the_catalog():
    unit = TaxAccount(
        "201-1170-017-0001",
        "999 WHIMSICAL LN",
        "path",
        bills=(
            _bill(2016, 15_140_500, balance=0),
            _bill(2017, 20_000_000, balance=0, total=250_000),
            _bill(2025, 23_211_200, balance=34_785),
        ),
    )
    priced = TaxAccount(unit.apn, unit.address, unit.path, bills=unit.bills[:2])
    prices = sale_price_values((priced,))
    assert prices[1][2] == 2017
    assert prices[1][3] == "200000.00"
    due = taxes_due_values((unit,))
    assert due[1][2] == "due"
    assert due[1][4] == "347.85"
    assert due[1][5] == "0.00"

    older = TaxAccount(
        "201-1170-017-0001",
        "999 WHIMSICAL LN",
        "path",
        bills=(_bill(2024, 100, balance=50), _bill(2025, 100, balance=0)),
    )
    assert taxes_due_values((older,))[1][2] == "delinquent"
    assert taxes_due_values((older,))[1][5] == "0.50"


def test_a_sale_row_keeps_the_current_document_number():
    account = TaxAccount("201-1170-017-0001", "999 WHIMSICAL LN", "path", bills=(_bill(2017, 20_000_000),))
    deed = OwnershipSheetRow(
        "20111700170001",
        "999 WHIMSICAL LN",
        "2017-03-24",
        "GD",
        "201703240140",
        "WATT COMMUNITIES AT MYSTIQUE LLC",
        "A BUYER",
        False,
    )
    row = sale_price_values((account,), (deed,))[1]
    assert row[6] == "201703240140"
    assert row[7] == "GD"


def test_a_stored_chain_prices_each_sale():
    account = TaxAccount(
        "201-1170-022-0015",
        "3024 MACON DR",
        "path",
        bills=(
            _bill(2020, 16_402_800),
            _bill(2021, 33_000_000),
            _bill(2022, 33_660_000),
            _bill(2023, 50_082_000),
        ),
    )
    history = succession(
        (
            Conveyance(
                "202205120581",
                date(2022, 5, 12),
                ("QUENBY ODILE",),
                ("UMBERLEIGH NYLE FENNIMORE-LUNE",),
            ),
            Conveyance(
                "202011131167",
                date(2020, 11, 13),
                ("WATT COMMUNITIES AT MYSTIQUE LLC",),
                ("QUENBY ODILE",),
            ),
        ),
        apn="20111700220015",
        developers=DEVELOPERS,
    )
    rows = sale_price_values((account,), histories=(history,))
    assert len(rows) == 3
    assert rows[1][6] == "202205120581"
    assert rows[1][2] == 2023
    assert rows[1][3] == "500820.00"
    assert rows[2][6] == "202011131167"
    assert rows[2][2] == 2021
    assert rows[2][3] == "330000.00"


def test_the_community_deed_chain_is_not_stored_as_a_parcel(tmp_path):
    from jason.community.ownership import OwnershipStore

    history = succession((
        Conveyance("200605041076", date(2006, 5, 4), ("REYNEN & BARDIS COMMUNITIES INC",), ("WL HOMES LLC",)),
    ))
    with OwnershipStore(tmp_path / "ownership.db") as store:
        store.remember_pinned(history)
        stored = store.pinned_history()
    assert stored is not None
    assert stored.apn == ""
    assert stored.numbers == ("200605041076",)


def test_association_taxes_list_each_bill():
    account = TaxAccount(
        "201-1170-018-0000",
        "3000 MACON DR",
        "path",
        bills=(_bill(2025, 2_000, balance=0, total=100),),
    )
    rows = association_tax_values((account,))
    assert rows[1][0] == "201-1170-018-0000"
    assert rows[1][2] == 2025
    assert rows[1][3] == "20.00"


def test_create_writes_each_tab():
    class Sheets:
        def __init__(self) -> None:
            self.titles: tuple[str, ...] = ()
            self.ranges: dict[str, list] = {}

        def create(self, title: str, sheet_titles: tuple[str, ...] | None = None) -> dict[str, str]:
            self.titles = sheet_titles or ()
            return {"spreadsheetId": "sheet-1"}

        def values_update(self, spreadsheet_id: str, range_a1: str, rows: list) -> dict[str, str]:
            self.ranges[range_a1] = rows
            return {}

    sheets = Sheets()
    history = succession((Conveyance("200605041076", date(2006, 5, 4), ("REYNEN & BARDIS COMMUNITIES INC",), ("WL HOMES LLC",)),))
    ownership = (OwnershipSheetRow("20111700180000", "3000 MACON DR", "2007-09-28", "GD", "200709281731", "WL HOMES LLC", "MYSTIQUE COMMUNITY ASSN", False),)
    report = create_county_report(
        sheets,
        "Mystique county",
        {
            "Ownership": [["APN"]],
            "Deed history": deed_history_values(history),
            "Association taxes": [["APN"]],
            "Sale prices": [["APN"]],
            "Taxes due": [["APN"]],
        },
    )
    assert sheets.titles == ("Ownership", "Deed history", "Association taxes", "Sale prices", "Taxes due")
    assert "'Deed history'!A1" in sheets.ranges
    assert report.url.endswith("/sheet-1")
    assert report.counts[1] == ("Deed history", 1)
