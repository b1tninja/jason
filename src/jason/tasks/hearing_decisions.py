"""The board's decision after a disciplinary hearing, recorded once on the hearing's own row.

``jason hearing`` saves each planned hearing in ``data/zoom/hearings.json`` (one row per address and start). The
decision the board reaches is written here onto that row: the findings in the board's words, the day it decided,
and who recorded it. The written decision notice is due within fourteen days of the board's action (Civil Code
5855(f)); the notice itself is a filled copy of the decision-notice template that a person makes with
``jason letter … --yes`` and sends. jason records the decision and decides nothing.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HEARINGS = Path("zoom") / "hearings.json"
DECISION_DAYS = 14   # CIV 5855(f)


def key_of(row: dict[str, Any]) -> str:
    """A hearing's identity across runs: its day and address, as `save_hearing` keeps rows unique."""
    return f"{str(row.get('start', ''))[:10]}|{re.sub(r'[^a-z0-9]+', '-', str(row.get('address', '')).lower()).strip('-')}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(data_dir: Path) -> list[dict[str, Any]]:
    path = Path(data_dir) / HEARINGS
    return json.loads(path.read_text(encoding="utf-8")).get("hearings", []) if path.is_file() else []


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, "hearings", timeout=60, purpose=f"hearing decisions: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


@_store_lock
def record(data_dir: Path, key: str, *, findings: str, decided_on: str, by: str) -> dict[str, Any]:
    """Write the board's decision onto the hearing row ``key`` names. The findings are the board's words."""
    findings, by = findings.strip(), by.strip()
    if not findings:
        raise ValueError("the decision needs the board's findings, in its words")
    if not by:
        raise ValueError("the decision names who recorded it")
    day = date.fromisoformat(decided_on.strip())
    rows = load(data_dir)
    row = next((r for r in rows if key_of(r) == key), None)
    if row is None:
        raise KeyError(key)
    held = date.fromisoformat(str(row["start"])[:10])
    if day < held:
        raise ValueError(f"the decision ({day}) cannot come before the hearing ({held})")
    now = _now()
    earlier = row.get("decision")
    row["decision"] = {"findings": findings, "decidedOn": day.isoformat(), "noticeDueBy": (day + timedelta(days=DECISION_DAYS)).isoformat(),
                       "by": by, "recorded": now, "history": (earlier or {}).get("history", []) + [f"{now[:10]}: {'re-recorded' if earlier else 'recorded'} by {by}"]}
    path = Path(data_dir) / HEARINGS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"hearings": sorted(rows, key=lambda r: r["start"])}, indent=1), encoding="utf-8")
    return row
