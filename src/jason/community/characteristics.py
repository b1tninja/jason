"""What the assessor records about each unit's building, and the plan it matches.

The assessor's parcel viewer publishes residential characteristics for a
parcel: living area, bedrooms, baths, year built, floor level, garage area. Those
are the factors a sale price turns on besides the market month, so they ride
beside every sale in the value reports. ``UnitCharacteristics`` is one
parcel's record (asspy's, as each county's assessor reads it). ``CharacteristicsStore`` keeps them on disk. A ``FloorPlan``
is what the developer said it built; the assessor's living area is what it
measured. ``classify_plan`` names the plan whose stated area is nearest the
measured one, for the same developer and bedroom count, and only within
``PLAN_TOLERANCE``. A unit that matches no plan stays unclassified; its
measured area still counts.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from asspy.core import UnitCharacteristics
from asspy.sacramento.assessor import parse_characteristics  # noqa: F401  (the Sacramento viewer's reader)

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


def per_sqft(unit: UnitCharacteristics, cents: int | None) -> int | None:
    """Cents per square foot of ``unit``'s living area, or None without an area."""
    if not cents or not unit.living_sqft:
        return None
    return int(round(cents / unit.living_sqft))


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

