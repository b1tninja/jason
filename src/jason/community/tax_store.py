"""Local catalog of Sacramento County property-tax accounts and bills.

Sync writes what the public tax office returned: the account, each bill's
assessed value, and the levy lines on that bill. A later sync updates those
figures. Sale price is not stored. The countywide levy is 1% of the net
assessed value, and the direct charges are flat.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from jason.community.tax import TaxAccount, TaxBill, TaxLevy, parcel_number

_BILL_COLUMNS = (
    ("land_cents", "INTEGER"),
    ("improvement_cents", "INTEGER"),
    ("fixture_cents", "INTEGER"),
    ("personal_property_cents", "INTEGER"),
    ("homeowner_exemption_cents", "INTEGER"),
    ("other_exemption_cents", "INTEGER"),
    ("net_assessed_cents", "INTEGER"),
    ("tax_rate_area", "TEXT NOT NULL DEFAULT ''"),
    ("rate_e8", "INTEGER"),
    ("ad_valorem_cents", "INTEGER"),
    ("direct_cents", "INTEGER"),
    ("total_cents", "INTEGER"),
    ("payments_cents", "INTEGER"),
    ("balance_cents", "INTEGER"),
    ("pdf_path", "TEXT NOT NULL DEFAULT ''"),
    ("pdf_sha256", "TEXT NOT NULL DEFAULT ''"),
)


class TaxStore:
    """SQLite catalog of tax accounts, bill values, and levy lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                apn TEXT PRIMARY KEY,
                address TEXT NOT NULL DEFAULT '',
                path TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL DEFAULT '',
                public_url TEXT NOT NULL DEFAULT '',
                amount_cents INTEGER,
                assessee TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bills (
                apn TEXT NOT NULL REFERENCES accounts(apn),
                number TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                year INTEGER,
                land_cents INTEGER,
                improvement_cents INTEGER,
                fixture_cents INTEGER,
                personal_property_cents INTEGER,
                homeowner_exemption_cents INTEGER,
                other_exemption_cents INTEGER,
                net_assessed_cents INTEGER,
                tax_rate_area TEXT NOT NULL DEFAULT '',
                rate_e8 INTEGER,
                ad_valorem_cents INTEGER,
                direct_cents INTEGER,
                total_cents INTEGER,
                payments_cents INTEGER,
                balance_cents INTEGER,
                pdf_path TEXT NOT NULL DEFAULT '',
                pdf_sha256 TEXT NOT NULL DEFAULT '',
                synced_at TEXT NOT NULL,
                PRIMARY KEY (apn, number)
            );

            CREATE TABLE IF NOT EXISTS levies (
                apn TEXT NOT NULL,
                number TEXT NOT NULL,
                position INTEGER NOT NULL,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                code TEXT NOT NULL DEFAULT '',
                rate_e8 INTEGER,
                taxable_cents INTEGER,
                amount_cents INTEGER NOT NULL,
                PRIMARY KEY (apn, number, position),
                FOREIGN KEY (apn, number) REFERENCES bills(apn, number)
            );

            CREATE TABLE IF NOT EXISTS sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                accounts_synced INTEGER NOT NULL DEFAULT 0,
                bills_new INTEGER NOT NULL DEFAULT 0,
                missed INTEGER NOT NULL DEFAULT 0,
                errors_json TEXT NOT NULL DEFAULT '[]'
            );
            """
        )
        _ensure_bill_columns(self._conn)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> TaxStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def counts(self) -> dict[str, int]:
        """How many accounts and bills are stored."""
        accounts = self._conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        bills = self._conn.execute("SELECT COUNT(*) FROM bills").fetchone()[0]
        return {"accounts": int(accounts), "bills": int(bills)}

    def get(self, apn: str) -> TaxAccount | None:
        number = parcel_number(apn)
        row = self._conn.execute("SELECT * FROM accounts WHERE apn = ?", (number,)).fetchone()
        if row is None:
            return None
        bills = self._conn.execute(
            "SELECT * FROM bills WHERE apn = ? ORDER BY year DESC, number DESC",
            (number,),
        ).fetchall()
        levy_rows = self._conn.execute(
            """
            SELECT * FROM levies WHERE apn = ?
            ORDER BY number, position
            """,
            (number,),
        ).fetchall()
        return TaxAccount(
            apn=row["apn"],
            address=row["address"],
            path=row["path"],
            kind=row["kind"],
            public_url=row["public_url"],
            bills=tuple(_bill(bill, levy_rows) for bill in bills),
            amount_cents=row["amount_cents"],
            assessee=row["assessee"],
            description=row["description"],
        )

    def upsert(self, account: TaxAccount) -> int:
        """Write the account and any new bills. Returns how many bills were new."""
        now = _now()
        self._conn.execute(
            """
            INSERT INTO accounts (
                apn, address, path, kind, public_url, amount_cents, assessee, description, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(apn) DO UPDATE SET
                address = excluded.address,
                path = excluded.path,
                kind = excluded.kind,
                public_url = excluded.public_url,
                amount_cents = excluded.amount_cents,
                assessee = excluded.assessee,
                description = excluded.description,
                synced_at = excluded.synced_at
            """,
            (
                account.apn,
                account.address,
                account.path,
                account.kind,
                account.public_url,
                account.amount_cents,
                account.assessee,
                account.description,
                now,
            ),
        )
        new = 0
        for bill in account.bills:
            existing = self._conn.execute(
                "SELECT 1 FROM bills WHERE apn = ? AND number = ?",
                (account.apn, bill.number),
            ).fetchone()
            self._conn.execute(
                """
                INSERT INTO bills (
                    apn, number, name, year,
                    land_cents, improvement_cents, fixture_cents, personal_property_cents,
                    homeowner_exemption_cents, other_exemption_cents, net_assessed_cents,
                    tax_rate_area, rate_e8, ad_valorem_cents, direct_cents,
                    total_cents, payments_cents, balance_cents, pdf_path, pdf_sha256, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(apn, number) DO UPDATE SET
                    name = excluded.name,
                    year = excluded.year,
                    land_cents = excluded.land_cents,
                    improvement_cents = excluded.improvement_cents,
                    fixture_cents = excluded.fixture_cents,
                    personal_property_cents = excluded.personal_property_cents,
                    homeowner_exemption_cents = excluded.homeowner_exemption_cents,
                    other_exemption_cents = excluded.other_exemption_cents,
                    net_assessed_cents = excluded.net_assessed_cents,
                    tax_rate_area = excluded.tax_rate_area,
                    rate_e8 = excluded.rate_e8,
                    ad_valorem_cents = excluded.ad_valorem_cents,
                    direct_cents = excluded.direct_cents,
                    total_cents = excluded.total_cents,
                    payments_cents = excluded.payments_cents,
                    balance_cents = excluded.balance_cents,
                    pdf_path = CASE WHEN excluded.pdf_path != '' THEN excluded.pdf_path ELSE bills.pdf_path END,
                    pdf_sha256 = CASE WHEN excluded.pdf_sha256 != '' THEN excluded.pdf_sha256 ELSE bills.pdf_sha256 END,
                    synced_at = excluded.synced_at
                """,
                (
                    account.apn,
                    bill.number,
                    bill.name,
                    bill.year,
                    bill.land_cents,
                    bill.improvement_cents,
                    bill.fixture_cents,
                    bill.personal_property_cents,
                    bill.homeowner_exemption_cents,
                    bill.other_exemption_cents,
                    bill.net_assessed_cents,
                    bill.tax_rate_area,
                    bill.rate_e8,
                    bill.ad_valorem_cents,
                    bill.direct_cents,
                    bill.total_cents,
                    bill.payments_cents,
                    bill.balance_cents,
                    bill.pdf_path,
                    bill.pdf_sha256,
                    now,
                ),
            )
            self._conn.execute(
                "DELETE FROM levies WHERE apn = ? AND number = ?",
                (account.apn, bill.number),
            )
            for position, levy in enumerate(bill.levies):
                self._conn.execute(
                    """
                    INSERT INTO levies (
                        apn, number, position, kind, name, code, rate_e8, taxable_cents, amount_cents
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account.apn,
                        bill.number,
                        position,
                        levy.kind,
                        levy.name,
                        levy.code,
                        levy.rate_e8,
                        levy.taxable_cents,
                        levy.amount_cents,
                    ),
                )
            if existing is None:
                new += 1
        self._conn.commit()
        return new

    def start_run(self) -> int:
        cursor = self._conn.execute(
            "INSERT INTO sync_runs (started_at) VALUES (?)",
            (_now(),),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def finish_run(
        self,
        run_id: int,
        *,
        accounts_synced: int,
        bills_new: int,
        missed: int,
        errors: list[str],
    ) -> None:
        self._conn.execute(
            """
            UPDATE sync_runs SET
                finished_at = ?,
                accounts_synced = ?,
                bills_new = ?,
                missed = ?,
                errors_json = ?
            WHERE id = ?
            """,
            (_now(), accounts_synced, bills_new, missed, json.dumps(errors), run_id),
        )
        self._conn.commit()


def _bill(row: sqlite3.Row, levy_rows: list[sqlite3.Row]) -> TaxBill:
    lines = [
        TaxLevy(
            kind=levy["kind"],
            name=levy["name"],
            amount_cents=levy["amount_cents"],
            rate_e8=levy["rate_e8"],
            taxable_cents=levy["taxable_cents"],
            code=levy["code"],
        )
        for levy in levy_rows
        if levy["number"] == row["number"]
    ]
    return TaxBill(
        number=row["number"],
        name=row["name"],
        year=row["year"],
        land_cents=row["land_cents"],
        improvement_cents=row["improvement_cents"],
        fixture_cents=row["fixture_cents"],
        personal_property_cents=row["personal_property_cents"],
        homeowner_exemption_cents=row["homeowner_exemption_cents"],
        other_exemption_cents=row["other_exemption_cents"],
        net_assessed_cents=row["net_assessed_cents"],
        tax_rate_area=row["tax_rate_area"],
        rate_e8=row["rate_e8"],
        ad_valorem_cents=row["ad_valorem_cents"],
        direct_cents=row["direct_cents"],
        total_cents=row["total_cents"],
        payments_cents=row["payments_cents"],
        balance_cents=row["balance_cents"],
        levies=tuple(lines),
        pdf_path=row["pdf_path"],
        pdf_sha256=row["pdf_sha256"],
    )


def _ensure_bill_columns(conn: sqlite3.Connection) -> None:
    """Add valuation columns when this catalog was created before bill pages were stored."""
    have = {row["name"] for row in conn.execute("PRAGMA table_info(bills)")}
    for name, kind in _BILL_COLUMNS:
        if name not in have:
            conn.execute(f"ALTER TABLE bills ADD COLUMN {name} {kind}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
