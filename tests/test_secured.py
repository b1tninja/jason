from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

from jason.community.recorder import Sacramento
from jason.community.secured import SecuredRoll
from jason.community.secured_store import SecuredCatalog
from jason.community.tax import TaxAccount
from jason.community.tax_store import TaxStore
from jason.tasks.sync_secured import sync_secured

HEADERS = [
    "MAPB",
    "PG",
    "PCL",
    "PSUB",
    "TAX_RATE_AREA",
    "SITUS_NUMBER",
    "SITUS_CITY",
    "SITUS_STREET",
    "SITUS_ZIP",
    "OWNER_CODE",
    "OWNER",
    "MAIL_ADDRESS",
    "MAIL_CITY",
    "MAIL_STATE",
    "MAIL_ZIP",
    "CARE_OF",
    "ZONING",
    "LAND_USE_CODE",
    "RECORDING_DATE",
    "RECORDING_PAGE",
    "DEED_TYPE",
    "LAND",
    "IM",
    "FIXTURE",
    "PP",
    "HO_EX",
    "EX",
    "VALUE_DT",
    "NGH",
    "ACTION_CODE",
]


def _cell(column: int, row: int, string_id: int) -> str:
    letters = ""
    number = column
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return f'<c r="{letters}{row}" t="s"><v>{string_id}</v></c>'


def _workbook(path: Path, rows: list[list[str]]) -> None:
    strings: list[str] = []
    index: dict[str, int] = {}

    def sid(value: str) -> int:
        if value not in index:
            index[value] = len(strings)
            strings.append(value)
        return index[value]

    sheet_rows = []
    for row_number, row in enumerate([HEADERS, *rows], start=1):
        cells = "".join(_cell(column, row_number, sid(value)) for column, value in enumerate(row, start=1))
        sheet_rows.append(f'<row r="{row_number}">{cells}</row>')
    shared = "".join(f"<si><t>{escape(value)}</t></si>" for value in strings)
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
    )
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"{shared}</sst>"
    )
    with ZipFile(path, "w") as book:
        book.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            "</Types>",
        )
        book.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        book.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="SECURED" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        book.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        book.writestr("xl/worksheets/sheet1.xml", sheet)
        book.writestr("xl/sharedStrings.xml", shared_xml)


def _row(**overrides: str) -> list[str]:
    values = {name: "" for name in HEADERS}
    values.update(
        MAPB="201",
        PG="1170",
        PCL="018",
        PSUB="0000",
        SITUS_NUMBER="3000",
        SITUS_STREET="MACON DR",
        SITUS_CITY="SACRAMENTO",
        SITUS_ZIP="95835",
        OWNER="MYSTIQUE COMMUNITY ASSOC",
        LAND_USE_CODE="AQ000A",
        LAND="20",
        IM="0",
        RECORDING_DATE="20070912",
    )
    values.update(overrides)
    return [values[name] for name in HEADERS]


def test_filter_returns_requested_parcels_in_order(tmp_path):
    path = tmp_path / "secured.xlsx"
    _workbook(
        path,
        [
            _row(),
            _row(
                PCL="017",
                PSUB="0001",
                SITUS_NUMBER="5651",
                SITUS_STREET="WHIMSICAL LN",
                OWNER="HOLLOWMERE JORDAN WESLEY",
                LAND_USE_CODE="A1F00A",
                LAND="90000",
                IM="150000",
            ),
        ],
    )
    roll = Sacramento.secured_roll(path)
    found = roll.filter(["201-1170-017-0001", "20111700180000", "20111700990000"])
    assert [row.apn for row in found] == ["20111700170001", "20111700180000"]
    common = found[1]
    assert common.owner == "MYSTIQUE COMMUNITY ASSOC"
    assert common.land_use == "AQ000A"
    assert common.situs == "3000 MACON DR, SACRAMENTO 95835"
    assert common.land_cents == 2000
    assert common.recording_date == date(2007, 9, 12)
    unit = found[0]
    assert unit.improvement_cents == 15000000


def test_mailing_address_is_the_county_bill_address(tmp_path):
    path = tmp_path / "secured.xlsx"
    _workbook(
        path,
        [
            _row(
                MAIL_ADDRESS="PO BOX 9",
                MAIL_CITY="SACRAMENTO",
                MAIL_STATE="CA",
                MAIL_ZIP="95814",
                CARE_OF="BOARD",
            )
        ],
    )
    parcel = next(iter(Sacramento.secured_roll(path)))
    assert parcel.mailing.lines == ("PO BOX 9", "SACRAMENTO, CA 95814")
    assert parcel.mailing.care_of == "BOARD"
    assert parcel.mails_to_situs is False


def test_blank_mail_street_uses_the_situs(tmp_path):
    path = tmp_path / "secured.xlsx"
    _workbook(path, [_row(MAIL_ADDRESS="", MAIL_CITY="", MAIL_STATE="", MAIL_ZIP="")])
    parcel = next(iter(Sacramento.secured_roll(path)))
    assert parcel.mailing.lines == ("3000 MACON DR", "SACRAMENTO, 95835")
    assert parcel.mails_to_situs is True


def test_secured_catalog_joins_to_a_tax_account_on_the_apn(tmp_path):
    path = tmp_path / "secured.xlsx"
    _workbook(
        path,
        [
            _row(
                MAIL_ADDRESS="PO BOX 9",
                MAIL_CITY="SACRAMENTO",
                MAIL_STATE="CA",
                MAIL_ZIP="95814",
                CARE_OF="BOARD",
            )
        ],
    )
    with TaxStore(tmp_path / "tax.db") as bills, SecuredCatalog(tmp_path / "secured.db") as roll:
        bills.upsert(
            TaxAccount(
                apn="201-1170-018-0000",
                address="3000 MACON DR SACRAMENTO, CA 95835",
                path="/Taxsys-GovHub/v0/items/example",
                amount_cents=0,
            )
        )
        result = sync_secured(roll, Sacramento.secured_roll(path), ("201-1170-018-0000", "20111700990000"))
        assert result.summary() == "parcels=1, missed=1"
        account = bills.get("20111700180000")
        assert account is not None
        record = roll.get(account.apn)
        assert record is not None
        assert record.apn == "20111700180000"
        assert record.mailing.lines == ("PO BOX 9", "SACRAMENTO, CA 95814")
        assert record.mailing.care_of == "BOARD"
        assert account.address == "3000 MACON DR SACRAMENTO, CA 95835"


def test_iter_skips_a_blank_parcel_key(tmp_path):
    path = tmp_path / "secured.xlsx"
    _workbook(path, [_row(MAPB="", PG="", PCL="", PSUB=""), _row()])
    assert [row.apn for row in Sacramento.secured_roll(path)] == ["20111700180000"]
