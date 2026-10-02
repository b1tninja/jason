"""Local store of parsed utility bills: each bill, its charges, and its meter reads.

The PDFs stay where the smud and i-doxs packages downloaded them. This store
holds what the parsers read from each file, keyed by the file's path, with
the file's size and modification time so a sync re-reads only what changed.
A mismatch between a bill's charges and its total is stored as read, not
corrected; ``reconciles`` says which bills add up.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from jason.community.symbols import Utility
from jason.community.utility import Charge, ChargeKind, MeterRead, Service, UsageUnit, UtilityBill

SCHEMA = """
CREATE TABLE IF NOT EXISTS bills (
    source TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    mtime REAL NOT NULL,
    provider TEXT NOT NULL,
    account TEXT NOT NULL,
    bill_id TEXT NOT NULL,
    bill_date TEXT,
    total_cents INTEGER NOT NULL,
    period_start TEXT,
    period_end TEXT,
    rate_schedule TEXT NOT NULL DEFAULT '',
    service_address TEXT NOT NULL DEFAULT '',
    parcel TEXT NOT NULL DEFAULT '',
    reconciles INTEGER NOT NULL,
    parsed_at TEXT NOT NULL,
    due_cents INTEGER
);
CREATE INDEX IF NOT EXISTS bills_account ON bills(provider, account, period_end);
CREATE TABLE IF NOT EXISTS charges (
    source TEXT NOT NULL REFERENCES bills(source) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    service TEXT NOT NULL,
    kind TEXT NOT NULL,
    label TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    quantity REAL,
    unit TEXT,
    rate REAL,
    period_start TEXT,
    period_end TEXT,
    meter TEXT NOT NULL DEFAULT '',
    tou TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (source, seq)
);
CREATE TABLE IF NOT EXISTS reads (
    source TEXT NOT NULL REFERENCES bills(source) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    meter TEXT NOT NULL,
    service TEXT NOT NULL,
    unit TEXT NOT NULL,
    usage REAL NOT NULL,
    previous REAL,
    current REAL,
    multiplier REAL,
    size TEXT NOT NULL DEFAULT '',
    register TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (source, seq)
);
"""


def _iso(day: date | None) -> str | None:
    return day.isoformat() if day else None


def _day(text: str | None) -> date | None:
    return date.fromisoformat(text) if text else None


class UtilityStore:
    """Parsed utility bills on disk. Open read-only for reports (``readonly=True``)."""

    def __init__(self, path: str | Path, *, readonly: bool = False) -> None:
        self.path = Path(path)
        if readonly:
            if not self.path.is_file():
                raise FileNotFoundError(f"{self.path} does not exist; run jason utilities --sync")
            self._conn = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.path)
            self._conn.executescript(SCHEMA)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> UtilityStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def known(self) -> dict[str, tuple[int, float]]:
        """Each stored file's size and modification time."""
        return {row["source"]: (row["size"], row["mtime"]) for row in self._conn.execute("SELECT source, size, mtime FROM bills")}

    def save(self, bill: UtilityBill, *, size: int, mtime: float) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM bills WHERE source = ?", (bill.source,))
            self._conn.execute(
                "INSERT INTO bills VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (bill.source, size, mtime, bill.provider.value, bill.account, bill.bill_id, _iso(bill.bill_date), bill.total_cents,
                 _iso(bill.period_start), _iso(bill.period_end), bill.rate_schedule, bill.service_address, bill.parcel,
                 int(bill.reconciles), datetime.now(timezone.utc).isoformat(timespec="seconds"), bill.due_cents),
            )
            self._conn.executemany(
                "INSERT INTO charges VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(bill.source, i, c.service.value, c.kind.value, c.label, c.amount_cents, c.quantity, c.unit.value if c.unit else None,
                  c.rate, _iso(c.period_start), _iso(c.period_end), c.meter, c.tou) for i, c in enumerate(bill.charges)],
            )
            self._conn.executemany(
                "INSERT INTO reads VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(bill.source, i, r.meter, r.service.value, r.unit.value, r.usage, r.previous, r.current, r.multiplier, r.size, r.register)
                 for i, r in enumerate(bill.reads)],
            )

    def forget(self, sources: list[str]) -> None:
        """Drop files that are gone from disk."""
        with self._conn:
            self._conn.executemany("DELETE FROM bills WHERE source = ?", [(s,) for s in sources])

    def bills(self, provider: Utility | None = None, account: str | None = None) -> list[UtilityBill]:
        """Every stored bill, rebuilt with its charges and reads, oldest period first."""
        where, args = [], []
        if provider:
            where.append("provider = ?")
            args.append(provider.value)
        if account:
            where.append("account = ?")
            args.append(account)
        sql = "SELECT * FROM bills" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY period_end, source"
        rows = self._conn.execute(sql, args).fetchall()
        charges: dict[str, list[Charge]] = {}
        for c in self._conn.execute("SELECT * FROM charges ORDER BY source, seq"):
            charges.setdefault(c["source"], []).append(Charge(
                Service(c["service"]), ChargeKind(c["kind"]), c["label"], c["amount_cents"], c["quantity"],
                UsageUnit(c["unit"]) if c["unit"] else None, c["rate"], _day(c["period_start"]), _day(c["period_end"]), c["meter"], c["tou"],
            ))
        reads: dict[str, list[MeterRead]] = {}
        for r in self._conn.execute("SELECT * FROM reads ORDER BY source, seq"):
            reads.setdefault(r["source"], []).append(MeterRead(
                r["meter"], Service(r["service"]), UsageUnit(r["unit"]), r["usage"], r["previous"], r["current"], r["multiplier"], r["size"], r["register"],
            ))
        return [
            UtilityBill(
                Utility(row["provider"]), row["account"], row["bill_id"], _day(row["bill_date"]), row["total_cents"],
                _day(row["period_start"]), _day(row["period_end"]), tuple(charges.get(row["source"], ())),
                tuple(reads.get(row["source"], ())), row["rate_schedule"], row["service_address"], row["parcel"], row["source"],
                (), row["due_cents"],
            )
            for row in rows
        ]

    def counts(self) -> dict[str, int]:
        found: dict[str, int] = {}
        for row in self._conn.execute("SELECT provider, COUNT(*) AS n, SUM(reconciles) AS ok FROM bills GROUP BY provider"):
            found[row["provider"]] = row["n"]
            found[f"{row['provider']}_reconciled"] = row["ok"] or 0
        return found


__all__ = ["UtilityStore"]
