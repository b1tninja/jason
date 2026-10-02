"""Local SQLite catalog of PayHOA units, people, violations, requests, and documents."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(row: dict[str, Any]) -> str:
    return json.dumps(row, separators=(",", ":"), default=str)


def person_name(row: dict[str, Any]) -> str:
    profile = row.get("profile") if isinstance(row.get("profile"), dict) else {}
    given = str(profile.get("givenNames") or "").strip()
    family = str(profile.get("familyName") or "").strip()
    combined = f"{given} {family}".strip()
    if combined:
        return combined
    return str(row.get("name") or row.get("email") or "")


def unit_label(row: dict[str, Any]) -> str:
    title = str(row.get("title") or row.get("name") or "").strip()
    if title:
        return title
    address = row.get("address") if isinstance(row.get("address"), dict) else {}
    return str(address.get("line1") or row.get("streetAddress") or "")


def unit_address(row: dict[str, Any]) -> tuple[str, str, str, str]:
    address = row.get("address") if isinstance(row.get("address"), dict) else {}
    line1 = str(address.get("line1") or row.get("streetAddress") or "")
    city = str(address.get("city") or row.get("city") or "")
    state = str(address.get("region") or row.get("state") or "")
    postal = str(address.get("postalCode") or row.get("zip") or "")
    return line1, city, state, postal


class PayhoaCatalog:
    """Upsert PayHOA directory records for one organization."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._init()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> PayhoaCatalog:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _init(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS units (
                org_id INTEGER NOT NULL,
                id INTEGER NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                balance INTEGER,
                past_due_balance INTEGER,
                address_line1 TEXT NOT NULL DEFAULT '',
                city TEXT NOT NULL DEFAULT '',
                state TEXT NOT NULL DEFAULT '',
                postal_code TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                PRIMARY KEY (org_id, id)
            );
            CREATE TABLE IF NOT EXISTS people (
                org_id INTEGER NOT NULL,
                id INTEGER NOT NULL,
                user_id INTEGER,
                name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                is_admin INTEGER NOT NULL DEFAULT 0,
                balance INTEGER,
                raw_json TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                PRIMARY KEY (org_id, id)
            );
            CREATE TABLE IF NOT EXISTS violations (
                org_id INTEGER NOT NULL,
                id INTEGER NOT NULL,
                unit_id INTEGER,
                status TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                reported_at TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                PRIMARY KEY (org_id, id)
            );
            CREATE TABLE IF NOT EXISTS requests (
                org_id INTEGER NOT NULL,
                id INTEGER NOT NULL,
                form_id INTEGER,
                form_name TEXT NOT NULL DEFAULT '',
                unit_id INTEGER,
                membership_id INTEGER,
                status TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                PRIMARY KEY (org_id, id)
            );
            CREATE TABLE IF NOT EXISTS unit_contacts (
                org_id INTEGER NOT NULL,
                id INTEGER NOT NULL,
                unit_id INTEGER NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                PRIMARY KEY (org_id, id)
            );
            CREATE TABLE IF NOT EXISTS documents (
                org_id INTEGER NOT NULL,
                id INTEGER NOT NULL,
                parent_id INTEGER,
                file_name TEXT NOT NULL DEFAULT '',
                path TEXT NOT NULL DEFAULT '',
                directory INTEGER NOT NULL DEFAULT 0,
                public INTEGER NOT NULL DEFAULT 0,
                file_size INTEGER,
                raw_json TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                PRIMARY KEY (org_id, id)
            );
            """
        )
        self._conn.commit()

    def upsert_units(self, org_id: int, rows: list[dict[str, Any]]) -> int:
        synced = _now()
        for row in rows:
            line1, city, state, postal = unit_address(row)
            self._conn.execute(
                """
                INSERT INTO units (
                    org_id, id, label, balance, past_due_balance,
                    address_line1, city, state, postal_code, raw_json, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(org_id, id) DO UPDATE SET
                    label=excluded.label,
                    balance=excluded.balance,
                    past_due_balance=excluded.past_due_balance,
                    address_line1=excluded.address_line1,
                    city=excluded.city,
                    state=excluded.state,
                    postal_code=excluded.postal_code,
                    raw_json=excluded.raw_json,
                    synced_at=excluded.synced_at
                """,
                (
                    org_id,
                    int(row["id"]),
                    unit_label(row),
                    row.get("balance"),
                    row.get("pastDueBalance"),
                    line1,
                    city,
                    state,
                    postal,
                    _dumps(row),
                    synced,
                ),
            )
        self._conn.commit()
        return len(rows)

    def replace_unit_contacts(self, org_id: int, unit_id: int, rows: list[dict[str, Any]]) -> int:
        """A unit's "other contacts" (tenants, managers, anyone the board keeps for the unit who is not an owner),
        replacing what the catalog held for it: a contact removed in PayHOA is removed here. Not owners, and never an
        owner's second delivery: a broadcast's "other contacts" reaches them, the Mailroom does not."""
        synced = _now()
        self._conn.execute("DELETE FROM unit_contacts WHERE org_id = ? AND unit_id = ?", (org_id, int(unit_id)))
        for row in rows:
            self._conn.execute(
                "INSERT OR REPLACE INTO unit_contacts (org_id, id, unit_id, name, email, phone, created_at, updated_at, "
                "raw_json, synced_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (org_id, int(row["id"]), int(unit_id), str(row.get("name") or ""), str(row.get("email") or ""),
                 str(row.get("phone") or ""), str(row.get("createdAt") or ""), str(row.get("updatedAt") or ""),
                 _dumps(row), synced))
        self._conn.commit()
        return len(rows)

    def unit_contacts(self, org_id: int, unit_id: int | None = None) -> list[dict[str, Any]]:
        """The catalog's other contacts, for one unit or every unit."""
        sql = "SELECT unit_id, id, name, email, phone, created_at, updated_at FROM unit_contacts WHERE org_id = ?"
        args: list[Any] = [org_id]
        if unit_id is not None:
            sql += " AND unit_id = ?"
            args.append(int(unit_id))
        return [dict(r) for r in self._conn.execute(sql + " ORDER BY unit_id, id", args)]

    def upsert_people(self, org_id: int, rows: list[dict[str, Any]]) -> int:
        synced = _now()
        for row in rows:
            self._conn.execute(
                """
                INSERT INTO people (
                    org_id, id, user_id, name, email, is_admin, balance,
                    raw_json, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(org_id, id) DO UPDATE SET
                    user_id=excluded.user_id,
                    name=excluded.name,
                    email=excluded.email,
                    is_admin=excluded.is_admin,
                    balance=excluded.balance,
                    raw_json=excluded.raw_json,
                    synced_at=excluded.synced_at
                """,
                (
                    org_id,
                    int(row["id"]),
                    row.get("userId"),
                    person_name(row),
                    str(row.get("email") or ""),
                    1 if row.get("isAdmin") else 0,
                    row.get("balance"),
                    _dumps(row),
                    synced,
                ),
            )
        self._conn.commit()
        return len(rows)

    def upsert_violations(self, org_id: int, rows: list[dict[str, Any]]) -> int:
        synced = _now()
        for row in rows:
            title = str(row.get("title") or row.get("description") or "")
            reported = str(row.get("reportedAt") or row.get("createdAt") or "")
            self._conn.execute(
                """
                INSERT INTO violations (
                    org_id, id, unit_id, status, title, reported_at,
                    raw_json, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(org_id, id) DO UPDATE SET
                    unit_id=excluded.unit_id,
                    status=excluded.status,
                    title=excluded.title,
                    reported_at=excluded.reported_at,
                    raw_json=excluded.raw_json,
                    synced_at=excluded.synced_at
                """,
                (
                    org_id,
                    int(row["id"]),
                    row.get("unitId"),
                    str(row.get("status") or ""),
                    title,
                    reported,
                    _dumps(row),
                    synced,
                ),
            )
        self._conn.commit()
        return len(rows)

    def upsert_requests(
        self,
        org_id: int,
        rows: list[dict[str, Any]],
        *,
        form_names: dict[int, str] | None = None,
    ) -> int:
        synced = _now()
        names = form_names or {}
        for row in rows:
            form_id = row.get("formId")
            form_name = names.get(int(form_id), "") if form_id is not None else ""
            self._conn.execute(
                """
                INSERT INTO requests (
                    org_id, id, form_id, form_name, unit_id, membership_id,
                    status, created_at, raw_json, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(org_id, id) DO UPDATE SET
                    form_id=excluded.form_id,
                    form_name=excluded.form_name,
                    unit_id=excluded.unit_id,
                    membership_id=excluded.membership_id,
                    status=excluded.status,
                    created_at=excluded.created_at,
                    raw_json=excluded.raw_json,
                    synced_at=excluded.synced_at
                """,
                (
                    org_id,
                    int(row["id"]),
                    form_id,
                    form_name,
                    row.get("unitId"),
                    row.get("membershipId"),
                    str(row.get("status") or ""),
                    str(row.get("createdAt") or ""),
                    _dumps(row),
                    synced,
                ),
            )
        self._conn.commit()
        return len(rows)

    def upsert_documents(self, org_id: int, rows: list[dict[str, Any]]) -> int:
        synced = _now()
        for row in rows:
            self._conn.execute(
                """
                INSERT INTO documents (
                    org_id, id, parent_id, file_name, path, directory, public,
                    file_size, raw_json, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(org_id, id) DO UPDATE SET
                    parent_id=excluded.parent_id,
                    file_name=excluded.file_name,
                    path=excluded.path,
                    directory=excluded.directory,
                    public=excluded.public,
                    file_size=excluded.file_size,
                    raw_json=excluded.raw_json,
                    synced_at=excluded.synced_at
                """,
                (
                    org_id,
                    int(row["id"]),
                    row.get("parentId"),
                    str(row.get("fileName") or ""),
                    str(row.get("path") or ""),
                    1 if row.get("directory") else 0,
                    1 if row.get("public") else 0,
                    row.get("fileSize"),
                    _dumps(row),
                    synced,
                ),
            )
        self._conn.commit()
        return len(rows)

    def list_documents(self, org_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT raw_json FROM documents WHERE org_id = ? ORDER BY path, file_name",
            (org_id,),
        ).fetchall()
        return [json.loads(row["raw_json"]) for row in rows]

    def request_ids(self, org_id: int) -> list[int]:
        rows = self._conn.execute(
            "SELECT id FROM requests WHERE org_id = ? ORDER BY id",
            (org_id,),
        ).fetchall()
        return [int(row["id"]) for row in rows]

    def search_requests(
        self,
        org_id: int,
        *,
        status: str | None = None,
        statuses: tuple[str, ...] | None = None,
        form_name: str | None = None,
        form_names: tuple[str, ...] | None = None,
        exclude_statuses: frozenset[str] | None = None,
        unit_id: int | None = None,
        text: str | None = None,
        include_raw: bool = False,
        limit: int | None = 50,
    ) -> list[dict[str, Any]]:
        """Filter catalogued requests. ``text`` matches the stored JSON."""
        clauses = ["org_id = ?"]
        params: list[Any] = [org_id]
        if status:
            clauses.append("lower(status) = lower(?)")
            params.append(status)
        if statuses:
            marks = ",".join("?" for _ in statuses)
            clauses.append(f"lower(status) IN ({marks})")
            params.extend(item.lower() for item in statuses)
        if form_name:
            clauses.append("lower(form_name) = lower(?)")
            params.append(form_name)
        if form_names:
            marks = ",".join("?" for _ in form_names)
            clauses.append(f"form_name IN ({marks})")
            params.extend(form_names)
        if exclude_statuses:
            marks = ",".join("?" for _ in exclude_statuses)
            clauses.append(f"status NOT IN ({marks})")
            params.extend(exclude_statuses)
        if unit_id is not None:
            clauses.append("unit_id = ?")
            params.append(unit_id)
        if text:
            clauses.append("lower(raw_json) LIKE ?")
            params.append(f"%{text.lower()}%")
        sql = f"""
            SELECT id, form_name, status, unit_id, created_at, raw_json
            FROM requests
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id
        """
        if limit is not None:
            sql += " LIMIT ?"
            params.append(max(1, min(limit, 200)))
        rows = self._conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            raw = json.loads(row["raw_json"])
            item: dict[str, Any] = {
                "id": int(row["id"]),
                "formName": row["form_name"],
                "form_name": row["form_name"],
                "status": row["status"],
                "unitId": row["unit_id"],
                "unit_id": row["unit_id"],
                "createdAt": row["created_at"],
                "created_at": row["created_at"],
                "title": str(raw.get("title") or ""),
            }
            if include_raw:
                item["raw_json"] = row["raw_json"]
            out.append(item)
        return out

    def get_request(self, org_id: int, request_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT id, form_name, status, unit_id, created_at, raw_json
            FROM requests WHERE org_id = ? AND id = ?
            """,
            (org_id, request_id),
        ).fetchone()
        if row is None:
            return None
        raw = json.loads(row["raw_json"])
        return {
            "id": int(row["id"]),
            "formName": row["form_name"],
            "status": row["status"],
            "unitId": row["unit_id"],
            "createdAt": row["created_at"],
            "title": str(raw.get("title") or ""),
            "raw": raw,
        }

    def search_documents(
        self,
        org_id: int,
        *,
        path_prefix: str | None = None,
        name_contains: str | None = None,
        files_only: bool = True,
        limit: int | None = 100,
    ) -> list[dict[str, Any]]:
        """Filter the document library by path prefix and file name."""
        clauses = ["org_id = ?"]
        params: list[Any] = [org_id]
        if files_only:
            clauses.append("directory = 0")
        if path_prefix:
            prefix = path_prefix.replace("\\", "/").strip("/")
            clauses.append("(path = ? OR path LIKE ?)")
            params.extend([prefix, f"{prefix}/%"])
        if name_contains:
            clauses.append("lower(file_name) LIKE ?")
            params.append(f"%{name_contains.lower()}%")
        sql = f"""
            SELECT id, parent_id, directory, file_name, path, file_size, public
            FROM documents
            WHERE {' AND '.join(clauses)}
            ORDER BY path, file_name
        """
        if limit is not None:
            sql += " LIMIT ?"
            params.append(max(1, min(limit, 2000)))
        rows = self._conn.execute(sql, params).fetchall()
        return [
            {
                "id": int(row["id"]),
                "parentId": row["parent_id"],
                "directory": bool(row["directory"]),
                "fileName": row["file_name"],
                "path": row["path"],
                "fileSize": row["file_size"],
                "public": bool(row["public"]),
            }
            for row in rows
        ]

    def search_units(
        self,
        org_id: int,
        *,
        query: str | None = None,
        past_due_only: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = ["org_id = ?"]
        params: list[Any] = [org_id]
        if past_due_only:
            clauses.append("past_due_balance > 0")
        if query:
            clauses.append(
                "(lower(label) LIKE ? OR lower(address_line1) LIKE ?)"
            )
            needle = f"%{query.lower()}%"
            params.extend([needle, needle])
        params.append(max(1, min(limit, 500)))
        rows = self._conn.execute(
            f"""
            SELECT id, label, address_line1, city, postal_code, balance, past_due_balance
            FROM units
            WHERE {' AND '.join(clauses)}
            ORDER BY label
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def list_violations(
        self,
        org_id: int,
        *,
        status: str | None = None,
        unit_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = ["org_id = ?"]
        params: list[Any] = [org_id]
        if status:
            clauses.append("lower(status) = lower(?)")
            params.append(status)
        if unit_id is not None:
            clauses.append("unit_id = ?")
            params.append(unit_id)
        params.append(max(1, min(limit, 500)))
        rows = self._conn.execute(
            f"""
            SELECT id, unit_id, status, title, reported_at
            FROM violations
            WHERE {' AND '.join(clauses)}
            ORDER BY reported_at DESC, id
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def counts(self, org_id: int) -> dict[str, int]:
        out: dict[str, int] = {}
        for table in ("units", "people", "violations", "requests", "documents", "unit_contacts"):
            row = self._conn.execute(
                f"SELECT COUNT(*) AS c FROM {table} WHERE org_id = ?",
                (org_id,),
            ).fetchone()
            out[table] = int(row["c"])
        return out
