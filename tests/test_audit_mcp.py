from datetime import date
from pathlib import Path

from jason.community.ownership import OwnershipStore
from jason.community.recorder import ChainStep, Conveyance, OwnershipHistory
from jason.community.tax import TaxAccount, TaxBill
from jason.community.tax_store import TaxStore
from jason.mcp.county import audit_chains

APN = "20111700170008"


def _deed(number, grantors, grantees, priors=()):
    recorded = date(int(number[:4]), int(number[4:6]), int(number[6:8]))
    return ChainStep(Conveyance(number, recorded, tuple(grantors), tuple(grantees), (), APN), tuple(priors))


def _bill(year, dollars):
    return TaxBill(str(year), f"{year} Secured Annual Bill", year=year, land_cents=dollars * 30, improvement_cents=dollars * 70)


def _seed(tmp_path: Path, values: tuple[tuple[int, int], ...]) -> None:
    with OwnershipStore(tmp_path / "ownership.db") as store:
        store.remember_history(
            OwnershipHistory(
                APN,
                (
                    _deed("201511130485", ("THISTLEWOOD ANSEL S",), ("WEXMOOR DAGNY T T", "MARROWDALE FENNA V"), ("201408010234",)),
                    _deed("201408010234", ("FARROWBY MARIT K", "FARROWBY TORVALD A"), ("THISTLEWOOD ANSEL S",), ("201204201319",)),
                    _deed("201204201319", ("DUNHOLLOW FLORIAN C", "DUNHOLLOW GREER S"), ("FARROWBY MARIT K", "FARROWBY TORVALD A"), ("200709281724",)),
                    _deed("200709281724", ("WL HOMES LLC",), ("DUNHOLLOW FLORIAN C", "DUNHOLLOW GREER S")),
                ),
            )
        )
    with TaxStore(tmp_path / "tax.db") as taxes:
        taxes.upsert(
            TaxAccount(
                "201-1170-017-0008",
                "5623 WHIMSICAL LN SACRAMENTO, CA 95835",
                "path",
                bills=tuple(_bill(year, dollars) for year, dollars in values),
            )
        )


def test_a_chain_in_step_with_the_bills_and_the_phase_audits_clean(tmp_path: Path):
    _seed(tmp_path, ((2013, 102_462), (2014, 104_511), (2015, 169_000), (2016, 215_000), (2017, 219_300)))
    found = audit_chains(data_dir=tmp_path)
    assert found["checked"] == 1 and found["clean"] == 1
    parcel = found["parcels"][0]
    assert parcel["apn"] == "201-1170-017-0008"
    assert parcel["phase"] == 1
    assert parcel["reassessing"] == {"2008": "200709281724", "2013": "201204201319", "2015": "201408010234", "2016": "201511130485"}
    assert audit_chains("201-1170-024-0001", data_dir=tmp_path)["checked"] == 0


def test_a_flat_year_under_a_sale_is_a_calendar_finding(tmp_path: Path):
    _seed(tmp_path, ((2013, 102_462), (2014, 104_511), (2015, 106_601), (2016, 215_000), (2017, 219_300)))
    found = audit_chains("20111700170008", data_dir=tmp_path)
    assert found["clean"] == 0
    checks = [(item["check"], item["number"], item["year"]) for item in found["parcels"][0]["findings"]]
    assert checks == [("calendar", "201408010234", 2015)]
