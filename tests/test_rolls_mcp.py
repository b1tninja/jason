from datetime import date
from pathlib import Path

from jason.community.secured import SecuredParcel, document_stamp
from jason.community.secured_store import SecuredCatalog
from jason.community.tax import TaxAccount, TaxBill
from jason.community.tax_store import TaxStore
from jason.mcp.rolls import (
    _from_roll,
    _tax_search,
    secured_search,
    secured_status,
    tax_account,
    tax_reassessments,
)


def test_the_roll_page_is_the_document_number():
    assert document_stamp(date(2022, 5, 12), "581") == "202205120581"
    assert document_stamp(date(2022, 5, 12), "") == ""
    parcel = SecuredParcel("20111700220015", "QUENBY", "R", recording_page="317", recording_date=date(2022, 5, 12))
    assert parcel.document == "202205120317"


def test_a_stored_tax_account_lists_the_bill(tmp_path: Path):
    account = TaxAccount(
        "201-1170-017-0001",
        "5651 WHIMSICAL LN",
        "path",
        bills=(
            TaxBill(
                "100",
                "2024 Secured",
                year=2024,
                land_cents=10_000,
                improvement_cents=20_000,
                net_assessed_cents=30_000,
                total_cents=400,
            ),
        ),
    )
    with TaxStore(tmp_path / "tax.db") as store:
        store.upsert(account)
    found = tax_account("20111700170001", data_dir=tmp_path)
    assert found["found"] is True
    assert found["bills"][0]["netAssessedCents"] == 30_000
    assert found["bills"][0]["landCents"] == 10_000


def test_tax_reassessments_are_the_years_after_a_sale(tmp_path: Path):
    def bill(year: int, land: int, improvement: int) -> TaxBill:
        return TaxBill(
            str(year),
            f"{year} Secured",
            year=year,
            land_cents=land,
            improvement_cents=improvement,
            net_assessed_cents=land + improvement,
        )

    account = TaxAccount(
        "201-1170-017-0011",
        "5611 WHIMSICAL LN",
        "path",
        bills=(
            bill(2016, 5_000_000, 10_783_284),  # 2% factor from 2015
            bill(2015, 5_000_000, 10_473_808),  # 2% factor from 2014
            bill(2014, 5_000_000, 10_170_400),  # jump: sold in 2013
            bill(2013, 4_000_000, 7_760_000),
            TaxBill("s", "2014 Supplemental", year=2014),  # no enrolled value
        ),
    )
    with TaxStore(tmp_path / "tax.db") as store:
        store.upsert(account)
    found = tax_reassessments("20111700170011", data_dir=tmp_path)
    assert found["found"] is True
    assert (found["firstYear"], found["lastYear"]) == (2013, 2016)
    assert [(item["year"], item["saleYear"]) for item in found["jumps"]] == [(2014, 2013)]
    assert found["jumps"][0]["enrolledCents"] == 15_170_400
    assert tax_reassessments("20111700170099", data_dir=tmp_path) == {
        "apn": "201-1170-017-0099",
        "found": False,
        "jumps": [],
    }


def test_tax_search_returns_accounts_without_downloading_bills():
    class Client:
        def search(self, query: str):
            return (
                TaxAccount("201-1170-017-0001", "5651 WHIMSICAL LN", "path"),
                TaxAccount("201-1170-017-0002", "5647 WHIMSICAL LN", "path"),
                TaxAccount("201-1170-017-0003", "5643 WHIMSICAL LN", "path"),
            )

    found = _tax_search(Client(), "whimsical", limit=2)
    assert found["total"] == 3
    assert found["truncated"] is True
    assert found["accounts"][0]["bills"] == 0
    assert found["accounts"][0]["apn"] == "201-1170-017-0001"


def test_secured_search_matches_the_owner(tmp_path: Path):
    with SecuredCatalog(tmp_path / "secured.db") as catalog:
        catalog.upsert(
            SecuredParcel(
                "20111700170001",
                "HOLLOWMERE JORDAN WESLEY",
                "R",
                land_cents=10_000,
                improvement_cents=20_000,
            )
        )
    found = secured_search("hollowmere", data_dir=tmp_path)
    assert found[0]["owner"] == "HOLLOWMERE JORDAN WESLEY"
    assert found[0]["netCents"] == 30_000
    assert found[0]["apn"] == "201-1170-017-0001"


def test_the_bulk_roll_returns_only_the_asked_parcels():
    class Roll:
        def filter(self, apns):
            assert tuple(apns) == ("20111700170001",)
            return (
                SecuredParcel(
                    "20111700170001",
                    "HOLLOWMERE JORDAN WESLEY",
                    "R",
                    deed_type="GD",
                    recording_page="123",
                    recording_date=date(2016, 3, 15),
                ),
            )

    found = _from_roll(Roll(), ("20111700170001",), workbook="secured_roll_public.xlsx")
    assert found["found"] is True
    assert found["count"] == 1
    assert found["parcels"][0]["owner"] == "HOLLOWMERE JORDAN WESLEY"
    assert found["parcels"][0]["document"] == "201603150123"


def test_a_missing_workbook_is_reported(tmp_path: Path):
    found = secured_status(data_dir=tmp_path, roll=str(tmp_path / "missing.xlsx"))
    assert found["parcels"] == 0
    assert found["workbookPresent"] is False
