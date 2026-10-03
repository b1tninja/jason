"""The board's written finding on each borrowing from the reserve, recorded once beside the ledger's facts.

``reserve_transfers`` sorts the ledger and searches the library for each borrowing's notice, minutes, and resolution
(Civil Code 5515). The finding itself, why the transfer is needed and when and how it is repaid (5515(c)), or that a
delay in restoring it is in the association's best interest (5515(d)), is in the minutes, and the library may not
hold them. So the finding is written here in the board's words, in jason's own ``data/payhoa/reserve-findings.json``,
one record per borrowing (``<day>|<transaction number>``): the text, which finding it is, the meeting that made it,
the day it was recorded, and by whom. Whether the statute was met is the board's call; jason records and decides
nothing.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

STORE = Path("payhoa") / "reserve-findings.json"


class FindingKind(Enum):
    AT_BORROWING = "finding at borrowing"            # CIV 5515(c): why, and when and how it is repaid
    LATE_RESTORATION = "finding for a late restoration"   # CIV 5515(d): the delay is in the association's best interest


KINDS = tuple(k.value for k in FindingKind)
AUTHORITY = {FindingKind.AT_BORROWING.value: "CIV 5515(c)", FindingKind.LATE_RESTORATION.value: "CIV 5515(d)"}
_KEY = re.compile(r"^\d{4}-\d{2}-\d{2}\|.+$")


def key_of(borrowing: dict[str, Any]) -> str:
    """A borrowing's identity across runs: its day and its transaction number."""
    return f"{str(borrowing.get('day', ''))[:10]}|{borrowing.get('number', '')}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(data_dir: Path) -> dict[str, dict[str, Any]]:
    """The recorded findings by borrowing key; none when the store is absent."""
    path = Path(data_dir) / STORE
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8")).get("findings", {})
    return dict(raw) if isinstance(raw, dict) else {}


def save(data_dir: Path, items: dict[str, dict[str, Any]]) -> Path:
    path = Path(data_dir) / STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"savedAt": _now(), "findings": items}, indent=1), encoding="utf-8")
    return path


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, "reserve-findings", timeout=60, purpose=f"reserve findings: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


@_store_lock
def record(data_dir: Path, key: str, *, finding: str, kind: str, made_on: str, by: str, meeting: str) -> dict[str, Any]:
    """Record the board's finding on the borrowing ``key`` names, or replace the one recorded. The words are the board's."""
    key, finding, by, kind = str(key).strip(), str(finding).strip(), str(by).strip(), str(kind).strip().lower()
    if not _KEY.match(key):
        raise ValueError("the key is <day>|<transaction number>, the day YYYY-MM-DD")
    borrowed = date.fromisoformat(key[:10])
    if not finding:
        raise ValueError("the finding is the board's words; it cannot be empty")
    if kind not in KINDS:
        raise ValueError(f"kind is one of {', '.join(KINDS)}")
    if not by:
        raise ValueError("the finding names who recorded it")
    held = date.fromisoformat(str(meeting).strip())
    made = date.fromisoformat(str(made_on).strip())
    if made < held:
        raise ValueError(f"the finding ({made}) cannot be recorded before the meeting that made it ({held})")
    if kind == FindingKind.LATE_RESTORATION.value and held < borrowed:
        raise ValueError(f"a finding for a late restoration ({held}) cannot come before the borrowing ({borrowed})")
    items = load(data_dir)
    now = _now()
    earlier = items.get(key)
    history = list((earlier or {}).get("history", [])) + [f"{now[:10]}: {'re-recorded' if earlier else 'recorded'} {kind} by {by}"]
    items[key] = {"key": key, "finding": finding, "kind": kind, "authority": AUTHORITY[kind], "madeOn": made.isoformat(), "by": by,
                  "meeting": held.isoformat(), "recorded": now, "history": history}
    save(data_dir, items)
    return items[key]
