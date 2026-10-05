"""What the deed scans on disk say about each instrument.

A scan is the recorder's image of a deed. Its text extract beside it, a
``.pdf.md`` file, is what this module reads. The header prints a parcel
number: the unit parcel on a later deed, the parent parcel on a 2007 or
2008 John Laing deed. The legal description names the plan unit. The
mail-to block or the "commonly known as" line names the address. The
transfer-tax declaration computes the price.

The parcel number on the image is the placement proof. A parent parcel
places through the plan unit. An address is a candidate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from jason.community.base import NEVER, Street, alternation, street_words
from jason.community.consideration import DeedPrice, deed_price
from jason.community.recorder import document_numbers
from jason.community.reports import PlanBlock, parent_parcel, plan_block, plan_unit

_UNIT = re.compile(r"\bUNIT\s+(?:NO\.?\s*)?(\d{1,3})\b", re.IGNORECASE)
_TEXT = frozenset({".md", ".txt"})


def _apn(parcel_prefix: str) -> re.Pattern[str]:
    """A parcel number as a deed's header prints it: the association's map book and page
    (``Community.parcel_prefix()``, a dash or a space allowed after the book and after the page), then the block and the
    parcel, each captured. With no prefix, no parcel number is read."""
    if len(parcel_prefix) != 7 or not parcel_prefix.isdigit():
        return re.compile(NEVER)
    return re.compile(rf"{parcel_prefix[:3]}[-\s]?{parcel_prefix[3:]}[-\s]?(\d{{3}})[-\s]?(\d{{4}})")


def _address(streets: tuple[Street, ...]) -> re.Pattern[str]:
    """A unit's address as a deed prints it: a number, then the first word of one of the association's streets
    (``Community.streets()``). With no streets, no address is read."""
    return re.compile(rf"\b(\d{{4}})\s+({alternation(street_words(streets))})\b", re.IGNORECASE)


PARCEL = "parcel number"
UNIT = "plan unit"
ADDRESS = "address"


@dataclass(frozen=True)
class DeedScan:
    """One instrument's scan and what its text prints."""

    number: str
    path: Path
    source: str
    unit_parcels: tuple[str, ...]
    parent_parcels: tuple[str, ...]
    units: tuple[int, ...]
    addresses: tuple[str, ...]
    price: DeedPrice | None

    @property
    def price_cents(self) -> int | None:
        return self.price.price_cents if self.price is not None else None


def scan_folders(root: Path) -> tuple[tuple[str, Path], ...]:
    """The folders that hold scans, and the source each came from."""
    return (
        ("drive", root / "artifacts" / "site-docs" / "deeds"),
        ("payhoa", root / "payhoa-files" / "documents" / "Grant Deeds"),
    )


def scan_index(root: Path, streets: tuple[Street, ...] = (), *, parcel_prefix: str = "") -> dict[str, DeedScan]:
    """Every extract on disk, by document number. The first file for a number wins.

    ``streets`` are the association's (``Community.streets()``): an address
    is read only on one of them. ``parcel_prefix`` is its map book and page
    (``Community.parcel_prefix()``): a parcel number is read only under it.
    ``data/deed-prices.csv`` holds figures a
    person read off a scan whose text layer garbled the tax line. Such a row
    replaces the price the extract computed, and its note travels with the
    scan.
    """
    found: dict[str, DeedScan] = {}
    for source, folder in scan_folders(root):
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _TEXT:
                continue
            for number in document_numbers(path.name):
                if number in found:
                    continue
                found[number] = read_scan(number, path, source, streets=streets, parcel_prefix=parcel_prefix)
    for number, price in hand_read_prices(root / "deed-prices.csv").items():
        scan = found.get(number)
        if scan is None:
            continue
        found[number] = DeedScan(
            scan.number, scan.path, scan.source, scan.unit_parcels, scan.parent_parcels,
            scan.units, scan.addresses, price,
        )
    return found


def hand_read_prices(path: Path) -> dict[str, DeedPrice]:
    """Prices a person read off the scans, by document number.

    The file is CSV with ``number, county_tax_cents, city_tax_cents,
    price_cents, exempt, source, note``. Blank cents stay unknown. A row with
    no price and no exemption records that the deed declares nothing usable.
    """
    if not path.is_file():
        return {}
    import csv

    found: dict[str, DeedPrice] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            number = "".join(ch for ch in str(row.get("number") or "") if ch.isdigit())
            if len(number) != 12:
                continue
            found[number] = DeedPrice(
                _cents(row.get("county_tax_cents")),
                _cents(row.get("city_tax_cents")),
                str(row.get("exempt") or "").strip().lower() in ("1", "true", "yes"),
                _cents(row.get("price_cents")),
            )
    return found


def _cents(value: object) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def read_scan(number: str, path: Path, source: str = "", *, streets: tuple[Street, ...] = (), parcel_prefix: str = "") -> DeedScan:
    """Read one extract. An address is read only on one of ``streets`` (``Community.streets()``), and a parcel number
    only under ``parcel_prefix``, the association's map book and page (``Community.parcel_prefix()``)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    flat = " ".join(text.split())
    units: list[str] = []
    parents: list[str] = []
    for block, sub in _apn(parcel_prefix).findall(flat):
        digits = f"{parcel_prefix}{block}{sub}"
        target = parents if parent_parcel(digits) else units
        if digits not in target:
            target.append(digits)
    plan_units = tuple(dict.fromkeys(int(item) for item in _UNIT.findall(flat)))
    addresses = tuple(dict.fromkeys(f"{num} {street.upper()}" for num, street in _address(streets).findall(flat)))
    return DeedScan(number, path, source, tuple(units), tuple(parents), plan_units, addresses, deed_price(text))


def placement(scan: DeedScan, apn: str, blocks: tuple[PlanBlock, ...] = (), address: str = "") -> str:
    """How this scan places the instrument on ``apn``, or empty when it does not.

    The parcel number printed on the image is proof. The block's parent
    parcel with the parcel's plan unit in the legal description places it
    too, and only then: a later developer reused units 21 to 32 on other
    buildings, so a unit number with no parent parcel places nothing. An
    address that matches is a candidate and is reported as such. A scan that
    prints a different unit parcel, or the parent parcel with a different
    unit, contradicts the placement and returns ``"other parcel"`` or
    ``"other unit"``.
    """
    digits = "".join(ch for ch in apn if ch.isdigit())
    if digits in scan.unit_parcels:
        return PARCEL
    if scan.unit_parcels:
        return "other parcel"
    unit = plan_unit(digits, blocks)
    block = plan_block(digits, blocks)
    parents = set(block.parent_parcels) if block is not None else set()
    printed_parent = bool(parents) and bool(parents & set(scan.parent_parcels))
    if unit is not None and scan.units and printed_parent:
        if unit in scan.units:
            return UNIT
        return "other unit"
    if address and scan.addresses:
        street = " ".join(address.upper().split())[:4]
        if any(item.startswith(street) for item in scan.addresses):
            return ADDRESS
    return ""
