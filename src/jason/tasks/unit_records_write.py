"""The writes behind a unit's record and the loss packet: an owner's entry, its visibility, a person's confirmation.

All three go to jason's own store under ``<data>/<profile>/units/<unit>/`` (P2), under the store lock, and each names the
person who made it. jason confirms nothing and verifies nothing here: an entry is the person's own word with the
documents they attach, and a step is confirmed only by the person who says so. Nothing leaves the machine.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.loss_packet import STEP_COUNT
from jason.community.unit_record import ComponentKind, ComponentStatus, Visibility
from jason.tasks.unit_records_view import _unit_dir

_DAY = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
_TEXT_FIELDS = ("where", "replaces", "date", "contractor", "licence", "permit", "approval", "product", "model", "serial", "warranty")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _need_by(by: str) -> str:
    by = str(by or "").strip()
    if not by:
        raise ValueError("the record names who made it")
    return by


def _locked(unit: str, purpose: str):
    from jason.locks import Resource, hold

    return hold(Resource.STORE, f"unit-record-{unit}", timeout=60, purpose=purpose)


def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _strings(value: Any, label: str) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, (list, tuple)) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"{label} is a list of evidence addresses")
    return [v.strip() for v in value if v.strip()]


def add_entry(root: Path, unit: str, body: dict[str, Any], *, by: str) -> dict[str, Any]:
    """Add an improvement or replacement to a unit's record. ``component``, ``kind``, and ``what`` are required; the status
    is the owner's word (``upgrade`` by default; ``unknown`` and ``original`` are not an entry's to claim); the visibility
    defaults to private. ``ValueError`` for anything malformed (a 400)."""
    by = _need_by(by)
    unit_dir = _unit_dir(Path(root), unit)
    component = str(body.get("component", "")).strip()
    what = str(body.get("what", "")).strip()
    if not component or not what:
        raise ValueError("an entry names its component and what was done")
    try:
        kind = ComponentKind(str(body.get("kind", "")).strip())
    except ValueError:
        raise ValueError("kind is one of " + ", ".join(k.value for k in ComponentKind)) from None
    try:
        status = ComponentStatus(str(body.get("status", "upgrade")).strip())
    except ValueError:
        raise ValueError("status is one of " + ", ".join(s.value for s in ComponentStatus)) from None
    if status in (ComponentStatus.UNKNOWN, ComponentStatus.ORIGINAL):
        raise ValueError("an entry records a change: its status is not unknown or original")
    visibility = str(body.get("visibility", Visibility.PRIVATE.value)).strip()
    if visibility not in {v.value for v in Visibility}:
        raise ValueError("visibility is one of " + ", ".join(v.value for v in Visibility))
    cost = body.get("cost_cents")
    if cost is not None and (isinstance(cost, bool) or not isinstance(cost, int) or cost < 0):
        raise ValueError("cost is whole cents, not a negative number")
    date = str(body.get("date", "")).strip()
    if date and not _DAY.match(date):
        raise ValueError("date is YYYY, YYYY-MM, or YYYY-MM-DD")
    entry: dict[str, Any] = {
        "id": uuid.uuid4().hex[:12], "unit": unit, "component": component, "kind": kind.value, "what": what,
        "status": status.value, "visibility": visibility, "by": by, "at": _now(), "cost_cents": cost,
        "photos": _strings(body.get("photos"), "photos"), "docs": _strings(body.get("docs"), "docs"),
    }
    for field in _TEXT_FIELDS:
        entry[field] = str(body.get(field, "")).strip()
    with _locked(unit, "unit record: add an entry"):
        rows = _load(unit_dir / "entries.json", [])
        rows = rows if isinstance(rows, list) else []
        rows.append(entry)
        _save(unit_dir / "entries.json", rows)
    return entry


def set_visibility(root: Path, unit: str, entry_id: str, visibility: str, *, by: str) -> dict[str, Any]:
    """Change who may see one entry (private, shared, association). ``KeyError`` when the unit has no such entry."""
    by = _need_by(by)
    if visibility not in {v.value for v in Visibility}:
        raise ValueError("visibility is one of " + ", ".join(v.value for v in Visibility))
    unit_dir = _unit_dir(Path(root), unit)
    with _locked(unit, "unit record: change an entry's visibility"):
        rows = _load(unit_dir / "entries.json", [])
        entry = next((r for r in rows if isinstance(r, dict) and r.get("id") == entry_id), None) if isinstance(rows, list) else None
        if entry is None:
            raise KeyError(entry_id)
        history = list(entry.get("visibilityHistory") or []) + [f"{_now()}: {entry.get('visibility')} to {visibility} by {by}"]
        entry.update(visibility=visibility, visibilityHistory=history)
        _save(unit_dir / "entries.json", rows)
    return entry


def confirm_step(root: Path, unit: str, incident: str, step: int, *, shows: Any, by: str, note: str = "") -> dict[str, Any]:
    """A person's confirmation of one step of a packet: what they say the record shows, who, and when. Replaces that step's
    earlier confirmation. jason never confirms a step itself."""
    by = _need_by(by)
    if isinstance(step, bool) or not isinstance(step, int) or not 1 <= step <= STEP_COUNT:
        raise ValueError(f"step is a number from 1 to {STEP_COUNT}")
    saw = _strings(shows, "shows")
    if not saw:
        raise ValueError("a confirmation says what the record shows")
    incident = re.sub(r"[^A-Za-z0-9_.-]", "", incident or "") or "unit"
    path = _unit_dir(Path(root), unit) / "packets" / f"{incident}.json"
    with _locked(unit, "unit record: confirm a packet step"):
        saved = _load(path, {})
        saved = saved if isinstance(saved, dict) else {}
        steps = saved.setdefault("steps", {})
        steps[str(step)] = {"shows": saw, "confirmed_by": by, "confirmed_at": _now()}
        if note.strip():
            saved.setdefault("notes", {})[str(step)] = note.strip()
        _save(path, saved)
    return {"unit": unit, "incident": incident, "step": step, **steps[str(step)]}
