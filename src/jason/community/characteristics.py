"""What the assessor records about each unit's building, and the plan it matches.

The assessor's parcel viewer publishes residential characteristics for a
parcel: living area, bedrooms, baths, year built, floor level, garage area. Those
are the factors a sale price turns on besides the market month, so they ride
beside every sale in the value reports. ``UnitCharacteristics`` is one
parcel's record. ``CharacteristicsStore`` keeps them on disk. A ``FloorPlan``
is what the developer said it built; the assessor's living area is what it
measured. ``classify_plan`` names the plan whose stated area is nearest the
measured one, for the same developer and bedroom count, and only within
``PLAN_TOLERANCE``. A unit that matches no plan stays unclassified; its
measured area still counts.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

# A plan's stated area may differ from the assessor's by this fraction.
PLAN_TOLERANCE = 0.06


@dataclass(frozen=True)
class FloorPlan:
    """One plan a developer offered, as that developer stated it.

    ``developer`` is the pinned developer's name as ``Developer.name`` prints
    it. ``baths`` is unset when the source did not say. ``source`` names the
    document the figures came from.
    """

    name: str
    developer: str
    bedrooms: int
    living_sqft: int
    stories: int
    baths: float | None = None
    source: str = ""


@dataclass(frozen=True)
class UnitCharacteristics:
    """The assessor's residential characteristics for one parcel."""

    apn: str
    land_use: str = ""
    home_type: str = ""
    living_sqft: int | None = None
    bedrooms: int | None = None
    baths: float | None = None
    year_built: int | None = None
    effective_year_built: int | None = None
    floor_level: int | None = None
    first_floor_sqft: int | None = None
    second_floor_sqft: int | None = None
    garage_sqft: int | None = None
    parking_spaces: int | None = None
    fetched: date | None = None
    # ``floor_level`` is the viewer's FLOOR_LEVEL. On the 2007 condominium
    # buildings it reads 1 for two-story units, so it is not a story count.

    def per_sqft(self, cents: int | None) -> int | None:
        """Cents per square foot of living area, or None without an area."""
        if not cents or not self.living_sqft:
            return None
        return int(round(cents / self.living_sqft))


def parse_characteristics(payload: dict | None, apn: str = "", *, fetched: date | None = None) -> UnitCharacteristics | None:
    """Read the viewer's ``buildingcharacteristics`` payload. The primary home is the record."""
    if not isinstance(payload, dict):
        return None
    res = payload.get("resChars")
    if not isinstance(res, dict):
        return None
    homes = res.get("BuildingCharacteristics") or []
    homes = [home for home in homes if isinstance(home, dict)]
    primary = next((home for home in homes if str(home.get("TYPE_OF_HOME", "")).lower() == "primary"), homes[0] if homes else {})
    number = _digits(str(res.get("PARCEL_NUMBER") or apn))
    if not number:
        return None
    return UnitCharacteristics(
        apn=number,
        land_use=str(res.get("LAND_USE_CODE") or ""),
        home_type=str(primary.get("TYPE_OF_HOME") or ""),
        living_sqft=_int(primary.get("TOTAL_LIVING_SQ_FT")) or _int(res.get("AREA_FOR_MOD")),
        bedrooms=_int(primary.get("BEDROOM_COUNT")),
        baths=_float(primary.get("TOTAL_BATH_COUNT")),
        year_built=_int(primary.get("YEAR_BUILT")),
        effective_year_built=_int(primary.get("EFFECTIVE_YEAR_BUILT")),
        floor_level=_int(primary.get("FLOOR_LEVEL")),
        first_floor_sqft=_int(primary.get("FIRST_FLR_AREA")),
        second_floor_sqft=_int(primary.get("SECOND_FLOOR_AREA")),
        garage_sqft=_int(res.get("GARAGE_AREA")),
        parking_spaces=_int(res.get("PARKING_SPACES")),
        fetched=fetched or date.today(),
    )


def classify_plan(unit: UnitCharacteristics, plans: tuple[FloorPlan, ...], developer: str = "") -> FloorPlan | None:
    """The plan whose stated area is nearest the measured one.

    Only plans of ``developer`` are read when it is given, and only plans with
    the unit's bedroom count when the assessor states one. The nearest plan
    wins when it is within ``PLAN_TOLERANCE`` of the measured area; an earlier
    plan wins a tie. Anything farther is a miss.
    """
    if not unit.living_sqft:
        return None
    best: tuple[int, int, FloorPlan] | None = None
    for order, plan in enumerate(plans):
        if developer and plan.developer != developer:
            continue
        if unit.bedrooms is not None and plan.bedrooms != unit.bedrooms:
            continue
        gap = abs(plan.living_sqft - unit.living_sqft)
        if gap > unit.living_sqft * PLAN_TOLERANCE:
            continue
        if best is None or (gap, order) < (best[0], best[1]):
            best = (gap, order, plan)
    return best[2] if best else None


class CharacteristicsStore:
    """SQLite memory of the assessor's characteristics for each parcel."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS characteristics (
                apn TEXT PRIMARY KEY,
                land_use TEXT NOT NULL DEFAULT '',
                home_type TEXT NOT NULL DEFAULT '',
                living_sqft INTEGER,
                bedrooms INTEGER,
                baths REAL,
                year_built INTEGER,
                effective_year_built INTEGER,
                floor_level INTEGER,
                first_floor_sqft INTEGER,
                second_floor_sqft INTEGER,
                garage_sqft INTEGER,
                parking_spaces INTEGER,
                fetched TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._conn.commit()

    def __enter__(self) -> "CharacteristicsStore":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    def remember(self, unit: UnitCharacteristics) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO characteristics (
                apn, land_use, home_type, living_sqft, bedrooms, baths, year_built, effective_year_built,
                floor_level, first_floor_sqft, second_floor_sqft, garage_sqft, parking_spaces, fetched
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _digits(unit.apn), unit.land_use, unit.home_type, unit.living_sqft, unit.bedrooms, unit.baths,
                unit.year_built, unit.effective_year_built, unit.floor_level, unit.first_floor_sqft,
                unit.second_floor_sqft, unit.garage_sqft, unit.parking_spaces,
                unit.fetched.isoformat() if unit.fetched else "",
            ),
        )
        self._conn.commit()

    def get(self, apn: str) -> UnitCharacteristics | None:
        row = self._conn.execute("SELECT * FROM characteristics WHERE apn = ?", (_digits(apn),)).fetchone()
        return _record(row) if row else None

    def all(self) -> dict[str, UnitCharacteristics]:
        rows = self._conn.execute("SELECT * FROM characteristics ORDER BY apn").fetchall()
        return {row["apn"]: _record(row) for row in rows}


def _record(row: sqlite3.Row) -> UnitCharacteristics:
    fetched = None
    if row["fetched"]:
        try:
            fetched = datetime.fromisoformat(row["fetched"]).date()
        except ValueError:
            fetched = None
    return UnitCharacteristics(
        apn=row["apn"], land_use=row["land_use"], home_type=row["home_type"], living_sqft=row["living_sqft"],
        bedrooms=row["bedrooms"], baths=row["baths"], year_built=row["year_built"],
        effective_year_built=row["effective_year_built"], floor_level=row["floor_level"],
        first_floor_sqft=row["first_floor_sqft"], second_floor_sqft=row["second_floor_sqft"],
        garage_sqft=row["garage_sqft"], parking_spaces=row["parking_spaces"], fetched=fetched,
    )


def _digits(value: str) -> str:
    return "".join(ch for ch in str(value) if ch.isdigit())


def _int(value: Any) -> int | None:
    try:
        number = int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None
    return number or None


def _float(value: Any) -> float | None:
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return number or None
