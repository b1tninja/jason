from datetime import date
from pathlib import Path

from jason.community.assessor import Parcel
from jason.community.ownership import OwnershipStore
from jason.community.recorder import Conveyance, expand_anchors
from jason.mcp.county import compare_parties, expand_deed_anchors, read_deed
from mystique.developers import DEVELOPERS

UNIT_A = "20111700170001"
UNIT_B = "20111700170002"


def _deed(number: str, recorded: date, grantors: tuple[str, ...], grantees: tuple[str, ...], apn: str = "") -> Conveyance:
    return Conveyance(number, recorded, grantors, grantees, (), apn)


def test_a_chain_that_reaches_an_anchor_drops_out_of_the_pool():
    developer = _deed("200605041076", date(2006, 5, 4), ("WL HOMES LLC",), ("OSTWICK CORIN",))
    middle = _deed("201102010742", date(2011, 2, 1), ("OSTWICK CORIN",), ("PELLINGHAM ELIO",), UNIT_A)
    current = _deed("201712140854", date(2017, 12, 14), ("PELLINGHAM ELIO",), ("PELLINGHAM ELIO",), UNIT_A)
    loose = _deed("202001010001", date(2020, 1, 1), ("SOMEONE ELSE",), ("OTHER PARTY",), UNIT_B)
    found = expand_anchors(
        (developer, middle, current, loose),
        currents=((UNIT_A, current.number), (UNIT_B, loose.number)),
        developers=DEVELOPERS,
    )
    assert found.solved == ((UNIT_A, current.number, (current.number, middle.number, developer.number)),)
    assert found.open_deeds == ((UNIT_B, loose.number),)
    assert found.remaining == (loose.number,)
    assert middle.number not in found.remaining


def test_a_deed_that_joins_two_parcels_stays_a_candidate():
    developer = _deed("200605041076", date(2006, 5, 4), ("WL HOMES LLC",), ("PLACE",))
    first = _deed("201201010001", date(2012, 1, 1), ("PLACE",), ("BUYER",), UNIT_A)
    second = _deed("201201010002", date(2012, 1, 2), ("PLACE",), ("BUYER",), UNIT_B)
    later = _deed("201801010001", date(2018, 1, 1), ("BUYER",), ("NEXT",))
    found = expand_anchors(
        (developer, first, second, later),
        developers=DEVELOPERS,
    )
    assert later.number in found.remaining
    assert found.contested == ((later.number, (first.number, second.number)),)
    assert first.number not in found.remaining
    assert second.number not in found.remaining


def test_a_different_parcel_does_not_hand_off():
    developer = _deed("200605041076", date(2006, 5, 4), ("WL HOMES LLC",), ("OSTWICK CORIN",))
    middle = _deed("201102010742", date(2011, 2, 1), ("OSTWICK CORIN",), ("PELLINGHAM ELIO",), UNIT_A)
    other = _deed("201801010001", date(2018, 1, 1), ("PELLINGHAM ELIO",), ("SOMEONE",), UNIT_B)
    found = expand_anchors((developer, middle, other), developers=DEVELOPERS)
    assert other.number in found.remaining
    assert found.contested == ()


def test_compare_parties_uses_the_chain_equality():
    assert compare_parties("FENNA V MARROWDALE", "FENNA VAN MARROWDALE") == {
        "equal": True,
        "candidates": [{"short": "V", "long": "VAN"}],
    }
    assert compare_parties("WATT COMMUNITIES LLC", "WATT COMMUNITIES AT MYSTIQUE LLC")["equal"] is False


def test_read_deed_returns_the_consideration_on_disk(tmp_path: Path):
    folder = tmp_path / "artifacts" / "site-docs" / "deeds"
    folder.mkdir(parents=True)
    (folder / "GD 202011041576.pdf.md").write_text(
        "acknowledged, WATT COMMUNITIES AT MYSTIQUE LLC hereby GRANT(S) to QUENBY ODILE "
        "the land described. Documentary transfer tax is $363.00 city tax is $907.50",
        encoding="utf-8",
    )
    found = read_deed("202011041576", data_dir=tmp_path)
    assert found["found"] is True
    assert found["priceCents"] == 33_000_000
    assert found["grantor"] == "WATT COMMUNITIES AT MYSTIQUE LLC"
    assert found["grantee"] == "QUENBY ODILE"


def test_read_deed_prefers_the_text_extract_over_the_scanned_pdf(tmp_path: Path):
    folder = tmp_path / "artifacts" / "site-docs" / "deeds"
    folder.mkdir(parents=True)
    (folder / "GD 202011041576.pdf").write_bytes(b"%PDF-1.4 binary, not the extract")
    (folder / "GD 202011041576.pdf.md").write_text(
        "acknowledged, WATT COMMUNITIES AT MYSTIQUE LLC hereby GRANT(S) to QUENBY ODILE "
        "the land described. Documentary transfer tax is $363.00 city tax is $907.50",
        encoding="utf-8",
    )
    found = read_deed("202011041576", data_dir=tmp_path)
    assert found["file"] == "GD 202011041576.pdf.md"
    assert found["priceCents"] == 33_000_000


def test_expand_deed_anchors_solves_a_current_deed_against_the_pinned_chain(tmp_path: Path):
    developer = _deed("200605041076", date(2006, 5, 4), ("WL HOMES LLC",), ("OSTWICK CORIN",))
    from jason.community.recorder import ChainStep, OwnershipHistory

    with OwnershipStore(tmp_path / "ownership.db") as store:
        store.remember_pinned(OwnershipHistory("pinned", (ChainStep(developer),)))
        store.remember(
            Parcel(UNIT_A, "", "GD", "Grant Deed", "20110201", "0742", date(2011, 2, 1)),
            grantors=("OSTWICK CORIN",),
            grantees=("PELLINGHAM ELIO",),
        )
    found = expand_deed_anchors(data_dir=tmp_path)
    assert found["solved"] == [
        {"apn": "201-1170-017-0001", "current": "201102010742", "path": ["201102010742", "200605041076"]}
    ]
    assert found["open"] == []
    assert found["remaining"] == []


def test_expand_deed_anchors_uses_the_stored_unit_chain(tmp_path: Path):
    """A resale whose stored chain already reaches the developer is solved, not open."""
    from jason.community.recorder import ChainStep, OwnershipHistory

    grant = _deed("200805071322", date(2008, 5, 7), ("WL HOMES LLC",), ("KESTRELTON BRAM L",))
    resale = _deed("201009101231", date(2010, 9, 10), ("KESTRELTON BRAM L",), ("YARROWBY COSMO A",))
    with OwnershipStore(tmp_path / "ownership.db") as store:
        store.remember_history(
            OwnershipHistory(UNIT_A, (ChainStep(resale, priors=("200805071322",)), ChainStep(grant)))
        )
        store.remember(
            Parcel(UNIT_A, "", "GD", "Grant Deed", "20100910", "1231", date(2010, 9, 10)),
            grantors=("KESTRELTON BRAM L",),
            grantees=("YARROWBY COSMO A",),
        )
    found = expand_deed_anchors(data_dir=tmp_path)
    assert found["open"] == []
    assert found["solved"] == [
        {"apn": "201-1170-017-0001", "current": "201009101231", "path": ["201009101231", "200805071322"]}
    ]


def test_read_deed_also_reads_the_payhoa_library_export(tmp_path: Path):
    folder = tmp_path / "payhoa-files" / "documents" / "Grant Deeds"
    folder.mkdir(parents=True)
    (folder / "GD 201408010234.pdf.md").write_text(
        "acknowledged, FARROWBY MARIT K hereby GRANT(S) to THISTLEWOOD ANSEL S the land described. "
        "documentary transfer tax is $178.20 city tax is $445.50",
        encoding="utf-8",
    )
    found = read_deed("201408010234", data_dir=tmp_path)
    assert found["found"] is True
    assert found["file"] == "GD 201408010234.pdf.md"
    assert found["priceCents"] == 16_200_000


def test_a_unit_number_lists_every_parcel_it_can_mean():
    from jason.mcp.county import unit_number

    both = unit_number(24)
    assert both["ambiguous"] is True
    assert [(p["apn"], p["building"], p["placesByUnit"]) for p in both["parcels"]] == [
        ("201-1170-024-0004", 3, True),
        ("201-1170-025-0020", 4, False),
    ]
    one = unit_number(91)
    assert one["ambiguous"] is False and one["parcels"][0]["apn"] == "201-1170-017-0011"
    assert unit_number(99)["parcels"] == []
