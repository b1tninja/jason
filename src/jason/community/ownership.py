"""Local record of each parcel's ownership instrument.

The assessor publishes the document number and its date. Compare those to this
store before calling the recorder. An unchanged date means the deed has not
changed, so the recorder is not fetched.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from jason.community.assessor import Parcel
from jason.community.base import Developer
from jason.community.recorder import ChainStep, Conveyance, OwnershipHistory

# The community grant-deed chain. Not an assessor parcel.
_PINNED = "pinned"


@dataclass(frozen=True)
class OwnershipRecord:
    apn: str
    document_number: str
    document_date: date
    grantors: tuple[str, ...] = ()
    grantees: tuple[str, ...] = ()
    document_type: str = ""

    @property
    def conveys(self) -> bool:
        """False for an instrument the assessor lists that moves no title: a death record."""
        return self.document_type.upper() not in ("DETH", "DEATH")


class OwnershipStore:
    """SQLite memory of the last ownership instrument seen for each parcel."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ownership (
                apn TEXT PRIMARY KEY,
                document_number TEXT NOT NULL,
                document_date TEXT NOT NULL,
                grantors TEXT NOT NULL DEFAULT '',
                grantees TEXT NOT NULL DEFAULT '',
                checked_at TEXT NOT NULL
            )
            """
        )
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(ownership)")}
        if "document_type" not in columns:
            self._conn.execute("ALTER TABLE ownership ADD COLUMN document_type TEXT NOT NULL DEFAULT ''")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chain (
                apn TEXT NOT NULL,
                document_number TEXT NOT NULL,
                recorded TEXT NOT NULL DEFAULT '',
                grantors TEXT NOT NULL DEFAULT '',
                grantees TEXT NOT NULL DEFAULT '',
                priors TEXT NOT NULL DEFAULT '',
                cited TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (apn, document_number)
            )
            """
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> OwnershipStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def records(self) -> tuple[OwnershipRecord, ...]:
        """Every stored parcel, in APN order."""
        rows = self._conn.execute("SELECT * FROM ownership ORDER BY apn").fetchall()
        return tuple(_record(row) for row in rows)

    def get(self, apn: str) -> OwnershipRecord | None:
        row = self._conn.execute("SELECT * FROM ownership WHERE apn = ?", (apn,)).fetchone()
        if row is None:
            return None
        return _record(row)

    def remember(self, parcel: Parcel, *, grantors: tuple[str, ...] = (), grantees: tuple[str, ...] = ()) -> None:
        if parcel.document_date is None or not parcel.document_number:
            return
        self._conn.execute(
            """
            INSERT INTO ownership (apn, document_number, document_date, grantors, grantees, checked_at, document_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(apn) DO UPDATE SET
                document_number = excluded.document_number,
                document_date = excluded.document_date,
                grantors = excluded.grantors,
                grantees = excluded.grantees,
                checked_at = excluded.checked_at,
                document_type = excluded.document_type
            """,
            (
                parcel.apn,
                parcel.document_number,
                parcel.document_date.isoformat(),
                "\n".join(grantors),
                "\n".join(grantees),
                datetime.now(timezone.utc).isoformat(),
                parcel.document_type,
            ),
        )
        self._conn.commit()

    def changed(self, parcel: Parcel) -> bool:
        """True when this parcel's recorded instrument is not the one we stored."""
        if parcel.document_date is None or not parcel.document_number:
            return True
        stored = self.get(parcel.apn)
        if stored is None:
            return True
        return (
            stored.document_number != parcel.document_number
            or stored.document_date != parcel.document_date
        )

    def remember_pinned(self, history: OwnershipHistory) -> None:
        """Store the community deed chain. It is not one parcel's title."""
        self.remember_history(OwnershipHistory(_PINNED, history.steps))

    def pinned_history(self, *, developers: tuple[Developer, ...] = ()) -> OwnershipHistory | None:
        """The stored community deed chain, with no parcel number attached."""
        found = self.parcel_history(_PINNED, developers=developers)
        if found is None:
            return None
        return OwnershipHistory("", found.steps, developers)

    def remember_history(self, history: OwnershipHistory) -> None:
        """Replace the stored document chain for this parcel."""
        if not history.apn:
            return
        self._conn.execute("DELETE FROM chain WHERE apn = ?", (history.apn,))
        for step in history.steps:
            item = step.conveyance
            self._conn.execute(
                """
                INSERT INTO chain (
                    apn, document_number, recorded, grantors, grantees, priors, cited
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    history.apn,
                    item.number,
                    item.recorded.isoformat() if item.recorded else "",
                    "\n".join(item.grantors),
                    "\n".join(item.grantees),
                    "\n".join(step.priors),
                    "\n".join(step.cited),
                ),
            )
        self._conn.commit()

    def parcel_history(
        self,
        apn: str,
        *,
        developers: tuple[Developer, ...] = (),
    ) -> OwnershipHistory | None:
        rows = self._conn.execute(
            """
            SELECT * FROM chain
            WHERE apn = ?
            ORDER BY recorded DESC, document_number DESC
            """,
            (apn,),
        ).fetchall()
        if not rows:
            return None
        steps = tuple(
            ChainStep(
                Conveyance(
                    row["document_number"],
                    date.fromisoformat(row["recorded"]) if row["recorded"] else None,
                    _lines(row["grantors"]),
                    _lines(row["grantees"]),
                    (),
                    row["apn"],
                ),
                _lines(row["priors"]),
                _lines(row["cited"]),
            )
            for row in rows
        )
        return OwnershipHistory(apn, steps, developers)

    def unit_histories(
        self,
        *,
        developers: tuple[Developer, ...] = (),
    ) -> tuple[OwnershipHistory, ...]:
        """Every stored parcel chain, in APN order. The community pin is left out."""
        rows = self._conn.execute(
            "SELECT DISTINCT apn FROM chain WHERE apn != ? ORDER BY apn", (_PINNED,)
        ).fetchall()
        found: list[OwnershipHistory] = []
        for row in rows:
            history = self.parcel_history(row["apn"], developers=developers)
            if history is not None:
                found.append(history)
        return tuple(found)

    def solved_numbers(self, *, developers: tuple[Developer, ...] = ()) -> frozenset[str]:
        """Document numbers on a chain that reaches one developer and has no gap.

        The community pin is included only when that chain is solved too.
        A forward search leaves this set out, so a sale already placed on a
        parcel is not offered again.
        """
        apns = self._conn.execute("SELECT DISTINCT apn FROM chain").fetchall()
        found: set[str] = set()
        for row in apns:
            history = self.parcel_history(row["apn"], developers=developers)
            if history is not None and history.reached_developer and not history.gaps:
                found.update(history.numbers)
        return frozenset(found)


def _lines(value: str) -> tuple[str, ...]:
    return tuple(part for part in str(value).split("\n") if part)


def _record(row) -> OwnershipRecord:
    keys = row.keys()
    return OwnershipRecord(
        row["apn"],
        row["document_number"],
        date.fromisoformat(row["document_date"]),
        _lines(row["grantors"]),
        _lines(row["grantees"]),
        str(row["document_type"] or "") if "document_type" in keys else "",
    )
