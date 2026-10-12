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
import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HEARINGS = Path("zoom") / "hearings.json"
DECISION_DAYS = 14   # CIV 5855(f)


def key_of(row: dict[str, Any]) -> str:
    """A hearing's identity across runs: its day and address, as `save_hearing` keeps rows unique."""
    return f"{str(row.get('start', ''))[:10]}|{re.sub(r'[^a-z0-9]+', '-', str(row.get('address', '')).lower()).strip('-')}"


def new_handle() -> str:
    """An opaque handle for a hearing: random, so it says nothing of the day or the address and cannot be found by trying
    the association's addresses. The console and its URLs name a hearing by this, never by its key."""
    return "h-" + secrets.token_hex(4)


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


HANDLE_SHAPE = re.compile(r"h-[0-9a-f]{8}")


def is_handle(value: Any) -> bool:
    """Whether ``value`` has the shape of a handle ``new_handle`` makes: ``h-`` and eight lowercase hex digits."""
    return isinstance(value, str) and HANDLE_SHAPE.fullmatch(value) is not None


def ensure_handles(data_dir: Path) -> list[dict[str, Any]]:
    """The saved hearings as stored. It never writes: a reader (a console GET, the rule records' links) must not change the
    store. A hearing saved before handles has none, and the reader leaves it out of what it lists by handle; ``unmigrated``
    counts those, and ``mint_handles`` (``jason zoom --mint-handles --yes``) gives them theirs. The name is kept for callers."""
    return load(data_dir)


def general_title() -> str:
    """The matter in the statute's words (Civil Code 4935(e)): never the unit, the owner, or the violation."""
    from jason.community.models.meetings import ExecutiveSubject, executive_general_note

    return "Hearing on " + executive_general_note([ExecutiveSubject.DISCIPLINE])


def open_row(h: dict[str, Any]) -> dict[str, Any]:
    """A saved hearing as a caller outside the private view may read it: the handle, the general title, the days and the
    5855 clock. An allowlist, so a field added to the stored row stays out until someone decides it belongs here."""
    d = h.get("decision") or None
    return {"handle": h.get("handle", ""), "title": general_title(), "start": h.get("start", ""), "noticeBy": h.get("noticeBy", ""),
            "noticeOn": h.get("noticeOn", ""), "decisionByIfHeld": h.get("decisionByIfHeld", ""), "standing": h.get("standing", ""),
            "scheduled": bool(h.get("scheduled")),
            "decision": {"decidedOn": d["decidedOn"], "noticeDueBy": d["noticeDueBy"]} if d else None}


def unmigrated(data_dir: Path) -> int:
    """How many saved hearings have no handle yet."""
    return sum(1 for r in load(data_dir) if not r.get("handle"))


@_store_lock
def mint_handles(data_dir: Path, *, write: bool = False) -> dict[str, int]:
    """The one-off migration: give each saved hearing that lacks a ``handle`` a random one, written beside its key (the key
    stays as it was). Without ``write`` it only counts. Returns ``{"hearings", "unmigrated", "minted"}``."""
    rows = load(data_dir)
    fresh = [r for r in rows if not r.get("handle")]
    if write and fresh:
        for r in fresh:
            r["handle"] = new_handle()
        from jason.durable import durable_write

        durable_write(Path(data_dir) / HEARINGS, json.dumps({"hearings": sorted(rows, key=lambda r: r["start"])}, indent=1))
    return {"hearings": len(rows), "unmigrated": len(fresh), "minted": len(fresh) if write else 0}


def key_for_handle(data_dir: Path, handle: str) -> str:
    """The key of the hearing ``handle`` names; ``KeyError`` when it names none."""
    handle = str(handle or "").strip()
    row = next((r for r in load(data_dir) if handle and r.get("handle") == handle), None)
    if row is None:
        raise KeyError(handle)
    return key_of(row)


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
