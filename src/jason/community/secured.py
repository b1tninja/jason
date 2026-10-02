"""Sacramento County secured assessment roll.

The assessor publishes the column names in the secured-roll layout. This
workbook uses that header row. Map book, page, parcel, and sub-parcel join
into the fourteen-digit APN. Dollar columns are stored as integer cents.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Iterator
from xml.etree import ElementTree
from zipfile import ZipFile

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def document_stamp(recorded: date | None, page: str) -> str:
    """Assessor document number: recording date plus the roll's page.

    Page ``581`` on 2022-05-12 is ``202205120581``. A blank page is no number.
    """
    text = page.strip()
    if recorded is None or not text.isdigit():
        return ""
    return recorded.strftime("%Y%m%d") + text.zfill(4)

_MONEY = {
    "LAND": "land_cents",
    "IM": "improvement_cents",
    "FIXTURE": "fixture_cents",
    "PP": "personal_property_cents",
    "HO_EX": "homeowner_exemption_cents",
    "EX": "exemption_cents",
}


@dataclass(frozen=True)
class MailingAddress:
    """Where the county sends the tax bill."""

    street: str
    city: str = ""
    state: str = ""
    postal_code: str = ""
    care_of: str = ""

    @property
    def lines(self) -> tuple[str, ...]:
        """Street, then city, state, and postal code."""
        region = " ".join(part for part in (self.state, self.postal_code) if part)
        if self.city and region:
            city_line = f"{self.city}, {region}"
        else:
            city_line = self.city or region
        return tuple(part for part in (self.street, city_line) if part)


@dataclass(frozen=True)
class SecuredParcel:
    """One secured-roll row."""

    apn: str
    owner: str
    land_use: str
    situs_number: str = ""
    situs_street: str = ""
    situs_city: str = ""
    situs_zip: str = ""
    zoning: str = ""
    tax_rate_area: str = ""
    mail_address: str = ""
    mail_city: str = ""
    mail_state: str = ""
    mail_zip: str = ""
    care_of: str = ""
    deed_type: str = ""
    recording_page: str = ""
    recording_date: date | None = None
    land_cents: int = 0
    improvement_cents: int = 0
    fixture_cents: int = 0
    personal_property_cents: int = 0
    homeowner_exemption_cents: int = 0
    exemption_cents: int = 0

    @property
    def situs(self) -> str:
        street = " ".join(part for part in (self.situs_number, self.situs_street) if part)
        city = " ".join(part for part in (self.situs_city, self.situs_zip) if part)
        return ", ".join(part for part in (street, city) if part)

    @property
    def document(self) -> str:
        """Assessor document number: recording date plus the roll's page."""
        return document_stamp(self.recording_date, self.recording_page)

    @property
    def mailing(self) -> MailingAddress:
        """County mailing address. The situs is used when the roll has no mail street."""
        street = self.mail_address.strip()
        if street:
            return MailingAddress(street, self.mail_city, self.mail_state, self.mail_zip, self.care_of)
        situs_street = " ".join(part for part in (self.situs_number, self.situs_street) if part)
        return MailingAddress(situs_street, self.situs_city, self.mail_state, self.situs_zip, self.care_of)

    @property
    def mails_to_situs(self) -> bool:
        """True when the mail street is the property address."""
        mail = " ".join(self.mailing.street.upper().split())
        situs = " ".join(part for part in (self.situs_number, self.situs_street) if part).upper()
        if not mail or not situs:
            return False
        return mail.startswith(situs) or situs.startswith(mail)


class SecuredRoll:
    """Read a secured-roll workbook one row at a time."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def __iter__(self) -> Iterator[SecuredParcel]:
        with ZipFile(self.path) as book:
            strings = _shared_strings(book)
            yield from _rows(book, strings)

    def filter(self, apns: Iterable[str]) -> tuple[SecuredParcel, ...]:
        """Rows whose APN is in ``apns``, in the order ``apns`` was given.

        A number that is not on the roll is omitted. Dashes are ignored.
        """
        order = [_digits(apn) for apn in apns]
        wanted = set(order)
        if not wanted:
            return ()
        found: dict[str, SecuredParcel] = {}
        for row in self:
            if row.apn in wanted and row.apn not in found:
                found[row.apn] = row
            if len(found) == len(wanted):
                break
        return tuple(found[apn] for apn in order if apn in found)


def _shared_strings(book: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in book.namelist():
        return []
    strings: list[str] = []
    for _event, elem in ElementTree.iterparse(book.open("xl/sharedStrings.xml"), events=("end",)):
        if elem.tag != _NS + "si":
            continue
        strings.append("".join((node.text or "") for node in elem.iter(_NS + "t")))
        elem.clear()
    return strings


def _rows(book: ZipFile, strings: list[str]) -> Iterator[SecuredParcel]:
    headers: list[str] = []
    context = ElementTree.iterparse(book.open("xl/worksheets/sheet1.xml"), events=("start", "end"))
    root = None
    for event, elem in context:
        if root is None:
            root = elem
            continue
        if event != "end" or elem.tag != _NS + "row":
            continue
        values = _row_values(elem, strings)
        elem.clear()
        root.clear()
        if not headers:
            headers = values
            continue
        fields = {name: values[index] if index < len(values) else "" for index, name in enumerate(headers)}
        parcel = _parcel(fields)
        if parcel is not None:
            yield parcel


def _row_values(row: ElementTree.Element, strings: list[str]) -> list[str]:
    values: list[str] = []
    for cell in row.findall(_NS + "c"):
        index = _column(cell.attrib.get("r", ""))
        while len(values) <= index:
            values.append("")
        values[index] = _cell(cell, strings)
    return values


def _cell(cell: ElementTree.Element, strings: list[str]) -> str:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        return "".join((node.text or "") for node in cell.iter(_NS + "t"))
    node = cell.find(_NS + "v")
    if node is None or node.text is None:
        return ""
    if kind == "s":
        return strings[int(node.text)]
    return node.text


def _column(ref: str) -> int:
    number = 0
    for char in ref:
        if not char.isalpha():
            break
        number = number * 26 + (ord(char.upper()) - 64)
    return number - 1


def _parcel(fields: dict[str, str]) -> SecuredParcel | None:
    parts = [fields.get(name, "") for name in ("MAPB", "PG", "PCL", "PSUB")]
    if not any(parts) or not all(part.isdigit() for part in parts if part):
        return None
    if not all(parts):
        return None
    money = {attr: _cents(fields.get(column, "")) for column, attr in _MONEY.items()}
    return SecuredParcel(
        apn=f"{parts[0].zfill(3)}{parts[1].zfill(4)}{parts[2].zfill(3)}{parts[3].zfill(4)}",
        owner=fields.get("OWNER", ""),
        land_use=fields.get("LAND_USE_CODE", ""),
        situs_number=fields.get("SITUS_NUMBER", ""),
        situs_street=fields.get("SITUS_STREET", ""),
        situs_city=fields.get("SITUS_CITY", ""),
        situs_zip=fields.get("SITUS_ZIP", ""),
        zoning=fields.get("ZONING", ""),
        tax_rate_area=fields.get("TAX_RATE_AREA", ""),
        mail_address=fields.get("MAIL_ADDRESS", ""),
        mail_city=fields.get("MAIL_CITY", ""),
        mail_state=fields.get("MAIL_STATE", ""),
        mail_zip=fields.get("MAIL_ZIP", ""),
        care_of=fields.get("CARE_OF", ""),
        deed_type=fields.get("DEED_TYPE", ""),
        recording_page=fields.get("RECORDING_PAGE", ""),
        recording_date=_date(fields.get("RECORDING_DATE", "")),
        **money,
    )


def _cents(value: str) -> int:
    text = value.strip()
    if not text:
        return 0
    negative = text.startswith("-")
    digits = text[1:] if negative else text
    if not digits.isdigit():
        return 0
    cents = int(digits) * 100
    return -cents if negative else cents


def _date(value: str) -> date | None:
    if len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def _digits(apn: str) -> str:
    return "".join(char for char in apn if char.isdigit())
