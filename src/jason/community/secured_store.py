"""Local catalog of secured-roll rows for the association's parcels.

This file is separate from the tax-bill catalog. Both are keyed by the
fourteen-digit APN, so a bill account joins to its roll row on that number.

The county publishes this roll once a year, so the owner and mailing address
can be stale. A newer assessor document date means the parcel sold after the
roll was printed. The name and mailing address on that row are then the
seller's, not the buyer's. Compare ``recording_date`` with the ownership
document date before treating the roll as current title. That comparison is
not done here.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from jason.community.secured import SecuredParcel


class SecuredCatalog:
    """SQLite copy of the secured-roll rows we keep."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS parcels (
                apn TEXT PRIMARY KEY,
                owner TEXT NOT NULL DEFAULT '',
                care_of TEXT NOT NULL DEFAULT '',
                land_use TEXT NOT NULL DEFAULT '',
                situs_number TEXT NOT NULL DEFAULT '',
                situs_street TEXT NOT NULL DEFAULT '',
                situs_city TEXT NOT NULL DEFAULT '',
                situs_zip TEXT NOT NULL DEFAULT '',
                zoning TEXT NOT NULL DEFAULT '',
                tax_rate_area TEXT NOT NULL DEFAULT '',
                mail_address TEXT NOT NULL DEFAULT '',
                mail_city TEXT NOT NULL DEFAULT '',
                mail_state TEXT NOT NULL DEFAULT '',
                mail_zip TEXT NOT NULL DEFAULT '',
                deed_type TEXT NOT NULL DEFAULT '',
                recording_page TEXT NOT NULL DEFAULT '',
                recording_date TEXT NOT NULL DEFAULT '',
                land_cents INTEGER NOT NULL DEFAULT 0,
                improvement_cents INTEGER NOT NULL DEFAULT 0,
                fixture_cents INTEGER NOT NULL DEFAULT 0,
                personal_property_cents INTEGER NOT NULL DEFAULT 0,
                homeowner_exemption_cents INTEGER NOT NULL DEFAULT 0,
                exemption_cents INTEGER NOT NULL DEFAULT 0,
                synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                parcels_synced INTEGER NOT NULL DEFAULT 0,
                missed INTEGER NOT NULL DEFAULT 0,
                errors_json TEXT NOT NULL DEFAULT '[]'
            );
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SecuredCatalog:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def counts(self) -> dict[str, int]:
        """How many secured-roll rows are stored."""
        parcels = self._conn.execute("SELECT COUNT(*) FROM parcels").fetchone()[0]
        return {"parcels": int(parcels)}

    def matching(self, text: str, *, limit: int = 20) -> tuple[SecuredParcel, ...]:
        """Rows whose owner contains ``text``. The match ignores case."""
        needle = "".join(ch for ch in text if ch not in "%_").strip()
        if not needle:
            return ()
        cap = max(1, min(limit, 40))
        rows = self._conn.execute(
            """
            SELECT apn FROM parcels
            WHERE UPPER(owner) LIKE ? ESCAPE '\\'
            ORDER BY apn
            LIMIT ?
            """,
            (f"%{needle.upper()}%", cap),
        ).fetchall()
        found = []
        for row in rows:
            parcel = self.get(row["apn"])
            if parcel is not None:
                found.append(parcel)
        return tuple(found)

    def get(self, apn: str) -> SecuredParcel | None:
        row = self._conn.execute(
            "SELECT * FROM parcels WHERE apn = ?",
            (_apn(apn),),
        ).fetchone()
        if row is None:
            return None
        recorded = row["recording_date"]
        return SecuredParcel(
            apn=row["apn"],
            owner=row["owner"],
            land_use=row["land_use"],
            situs_number=row["situs_number"],
            situs_street=row["situs_street"],
            situs_city=row["situs_city"],
            situs_zip=row["situs_zip"],
            zoning=row["zoning"],
            tax_rate_area=row["tax_rate_area"],
            mail_address=row["mail_address"],
            mail_city=row["mail_city"],
            mail_state=row["mail_state"],
            mail_zip=row["mail_zip"],
            care_of=row["care_of"],
            deed_type=row["deed_type"],
            recording_page=row["recording_page"],
            recording_date=date.fromisoformat(recorded) if recorded else None,
            land_cents=row["land_cents"],
            improvement_cents=row["improvement_cents"],
            fixture_cents=row["fixture_cents"],
            personal_property_cents=row["personal_property_cents"],
            homeowner_exemption_cents=row["homeowner_exemption_cents"],
            exemption_cents=row["exemption_cents"],
        )

    def upsert(self, parcel: SecuredParcel) -> None:
        recorded = parcel.recording_date.isoformat() if parcel.recording_date else ""
        self._conn.execute(
            """
            INSERT INTO parcels (
                apn, owner, care_of, land_use, situs_number, situs_street, situs_city, situs_zip,
                zoning, tax_rate_area, mail_address, mail_city, mail_state, mail_zip,
                deed_type, recording_page, recording_date, land_cents, improvement_cents,
                fixture_cents, personal_property_cents, homeowner_exemption_cents, exemption_cents,
                synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(apn) DO UPDATE SET
                owner = excluded.owner,
                care_of = excluded.care_of,
                land_use = excluded.land_use,
                situs_number = excluded.situs_number,
                situs_street = excluded.situs_street,
                situs_city = excluded.situs_city,
                situs_zip = excluded.situs_zip,
                zoning = excluded.zoning,
                tax_rate_area = excluded.tax_rate_area,
                mail_address = excluded.mail_address,
                mail_city = excluded.mail_city,
                mail_state = excluded.mail_state,
                mail_zip = excluded.mail_zip,
                deed_type = excluded.deed_type,
                recording_page = excluded.recording_page,
                recording_date = excluded.recording_date,
                land_cents = excluded.land_cents,
                improvement_cents = excluded.improvement_cents,
                fixture_cents = excluded.fixture_cents,
                personal_property_cents = excluded.personal_property_cents,
                homeowner_exemption_cents = excluded.homeowner_exemption_cents,
                exemption_cents = excluded.exemption_cents,
                synced_at = excluded.synced_at
            """,
            (
                _apn(parcel.apn),
                parcel.owner,
                parcel.care_of,
                parcel.land_use,
                parcel.situs_number,
                parcel.situs_street,
                parcel.situs_city,
                parcel.situs_zip,
                parcel.zoning,
                parcel.tax_rate_area,
                parcel.mail_address,
                parcel.mail_city,
                parcel.mail_state,
                parcel.mail_zip,
                parcel.deed_type,
                parcel.recording_page,
                recorded,
                parcel.land_cents,
                parcel.improvement_cents,
                parcel.fixture_cents,
                parcel.personal_property_cents,
                parcel.homeowner_exemption_cents,
                parcel.exemption_cents,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()

    def start_run(self) -> int:
        cursor = self._conn.execute(
            "INSERT INTO sync_runs (started_at) VALUES (?)",
            (datetime.now(timezone.utc).isoformat(),),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def finish_run(self, run_id: int, *, parcels_synced: int, missed: int, errors: list[str]) -> None:
        self._conn.execute(
            """
            UPDATE sync_runs SET
                finished_at = ?,
                parcels_synced = ?,
                missed = ?,
                errors_json = ?
            WHERE id = ?
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                parcels_synced,
                missed,
                json.dumps(errors),
                run_id,
            ),
        )
        self._conn.commit()


def _apn(value: str) -> str:
    return "".join(char for char in value if char.isdigit())
