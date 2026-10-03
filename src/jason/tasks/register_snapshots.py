"""A local snapshot of each register, so the board's columns can be edited in the UI between syncs.

``jason.tasks.registers.sync`` reads a register's Sheet and writes jason's columns; after each sync it saves what it saw
here, one file per register (``data/registers/<key>.json``): the columns with their owner and kind, the rows by key, and
the register's log. The UI edits a board-owned column in that snapshot (``edit``): the column must be the board's, the
value must fit the column's kind, the change is appended to the snapshot's log, and the row is marked ``pendingSync``.

Until the next ``jason registers --sync`` (or the owner's own sync, such as ``jason board --sheet``) pushes the edit, the
Sheet is behind the snapshot; the snapshot is a working copy, the Sheet and its log tab the record. A jason-owned column
is never edited here: jason's own run writes it.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.registers import Kind, Owner, Register

FOLDER = Path("registers")
STORE = "register-snapshots"
_KEY = re.compile(r"[^A-Za-z0-9_.-]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(data_dir: Path, key: str) -> Path:
    safe = _KEY.sub("-", key).strip("-")
    if not safe or safe == "registers":  # registers.json is the sync's own state
        raise ValueError(f"not a register key: {key!r}")
    return Path(data_dir) / FOLDER / f"{safe}.json"


def encode_columns(register: Register) -> list[dict[str, Any]]:
    return [{"name": c.name, "owner": c.owner.value, "kind": c.kind.value, "choices": list(c.choices)} for c in register.columns]


def save_snapshot(data_dir: Path, register: Register, rows: list[dict[str, Any]], log: list[dict[str, Any]] | None = None) -> Path:
    """What the sync saw: the rows as records, keyed by the first column. The log kept so far is carried over unless
    ``log`` replaces it; a row's ``pendingSync`` is cleared, since the sync has just run."""
    path = _path(data_dir, register.key)
    kept = load_snapshot(data_dir, register.key) or {}
    key = register.names[0]
    clean = []
    for row in rows:
        r = {name: row.get(name, "") for name in register.names}
        r[key] = str(row.get(key, "")).strip()
        if r[key]:
            clean.append(r)
    data = {"savedAt": _now(), "key": register.key, "title": register.title, "confidential": register.confidential,
            "columns": encode_columns(register), "rows": clean, "log": list(log if log is not None else kept.get("log", []))}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return path


def load_snapshot(data_dir: Path, key: str) -> dict[str, Any] | None:
    path = _path(data_dir, key)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("rows", [])
    data.setdefault("log", [])
    data.setdefault("columns", [])
    return data


def load_all(data_dir: Path) -> dict[str, dict[str, Any]]:
    """Every snapshot on disk, by register key."""
    folder = Path(data_dir) / FOLDER
    out: dict[str, dict[str, Any]] = {}
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*.json")):
        if path.stem == "registers":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("key"):
            data.setdefault("rows", [])
            data.setdefault("log", [])
            data.setdefault("columns", [])
            out[str(data["key"])] = data
    return out


def pending(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in snapshot.get("rows", []) if r.get("pendingSync")]


def pending_edits(data_dir: Path, register: Register) -> dict[str, dict[str, str]]:
    """The board's UI edits not yet pushed, as the sync's edits shape: row key -> {board column: value as a cell}."""
    snapshot = load_snapshot(data_dir, register.key)
    if snapshot is None:
        return {}
    key = register.names[0]
    board = [c.name for c in register.owned(Owner.BOARD)]
    out: dict[str, dict[str, str]] = {}
    for row in pending(snapshot):
        changed = set(row.get("pendingColumns") or [])
        for name in board:
            if name in changed:
                value = row.get(name, "")
                out.setdefault(str(row[key]), {})[name] = "" if value is None else ("TRUE" if value is True else "FALSE" if value is False else str(value))
    return out


def _coerce(column: dict[str, Any], value: Any) -> Any:
    """The value as the column's kind keeps it, or ``ValueError``. Empty clears any kind."""
    kind = Kind(column.get("kind", "text"))
    name = column["name"]
    if value is None or (isinstance(value, str) and not value.strip()):
        return False if kind is Kind.CHECKBOX else ""
    if kind is Kind.CHECKBOX:
        if isinstance(value, bool):
            return value
        word = str(value).strip().lower()
        if word in ("true", "yes", "1", "x"):
            return True
        if word in ("false", "no", "0"):
            return False
        raise ValueError(f"{name} is a checkbox: true or false")
    if kind is Kind.CHOICE:
        text = str(value).strip()
        choices = list(column.get("choices") or [])
        if choices and text not in choices:
            raise ValueError(f"{name} is one of {', '.join(choices)}")
        return text
    if kind is Kind.DATE:
        text = str(value).strip()
        try:
            date.fromisoformat(text)
        except ValueError:
            raise ValueError(f"{name} is a date, YYYY-MM-DD") from None
        return text
    if kind in (Kind.NUMBER, Kind.MONEY):
        if isinstance(value, bool):
            raise ValueError(f"{name} is a number")
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip().replace(",", "").lstrip("$")
        try:
            number = float(text)
        except ValueError:
            raise ValueError(f"{name} is a number") from None
        return int(number) if number == int(number) and "." not in text else number
    return str(value)


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, STORE, timeout=60, purpose=f"register snapshots: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


@_store_lock
def edit(data_dir: Path, register_key: str, row_key: str, column: str, value: Any, by: str = "") -> dict[str, Any]:
    """The board's edit of one cell in the snapshot. Refused (``ValueError``) for a jason-owned or unknown column, the
    key column, or a value that does not fit the column's kind; ``KeyError`` for a register or row not in the snapshot.
    Logged, and the row marked ``pendingSync`` until the next sync pushes it to the Sheet (until then the Sheet is
    behind). Returns the row as it now stands."""
    snapshot = load_snapshot(data_dir, register_key)
    if snapshot is None:
        raise KeyError(register_key)
    columns = {c["name"]: c for c in snapshot.get("columns", [])}
    if column not in columns:
        raise ValueError(f"{column}: not a column of {register_key}")
    if snapshot["columns"] and column == snapshot["columns"][0]["name"]:
        raise ValueError(f"{column} is the key; it never changes")
    if Owner(columns[column].get("owner", "jason")) is not Owner.BOARD:
        raise ValueError(f"{column}: jason's column; the board writes {', '.join(c['name'] for c in snapshot['columns'] if c.get('owner') == Owner.BOARD.value) or 'none'}")
    key_name = snapshot["columns"][0]["name"]
    row_key = str(row_key).strip()
    row = next((r for r in snapshot["rows"] if str(r.get(key_name, "")).strip() == row_key), None)
    if row is None:
        raise KeyError(row_key)
    after = _coerce(columns[column], value)
    before = row.get(column, "")
    if before == after:
        return dict(row)
    seen = _now()
    row[column] = after
    row["pendingSync"] = True
    row["pendingColumns"] = sorted(set(row.get("pendingColumns") or []) | {column})
    snapshot["log"].append({"seen": seen, "key": row_key, "column": column, "before": "" if before is None else before, "after": after,
                            "by": (by or "").strip() or "the board, in the UI"})
    snapshot["updatedAt"] = seen
    _path(data_dir, register_key).write_text(json.dumps(snapshot, indent=1), encoding="utf-8")
    return dict(row)


__all__ = ["FOLDER", "edit", "encode_columns", "load_all", "load_snapshot", "pending", "pending_edits", "save_snapshot"]
