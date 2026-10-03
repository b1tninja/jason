"""The owner-information plan as the last run computed it, and a person's confirmations of it.

``jason owner-info`` reads PayHOA live and plans the tag writes an owner's answer calls for. The plan is saved here
(``data/payhoa/owner-info-plan.json``) as the read artifact of that run, so a page can show it without a PayHOA
call. A person confirms each write on the page; the confirmations (``owner-info-confirmations.json``) are the
record that someone looked, and the apply stays ``jason owner-info --apply --payhoa --yes`` from a terminal.
Nothing here writes to PayHOA.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLAN = Path("payhoa") / "owner-info-plan.json"
CONFIRMATIONS = Path("payhoa") / "owner-info-confirmations.json"
APPLY = "jason owner-info --apply --payhoa --yes"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_key(w: Any) -> str:
    """One write's identity across runs: its kind, target, and value; the label and reason may be reworded."""
    g = (lambda k: getattr(w, k)) if is_dataclass(w) else (lambda k: w[k])
    return f"{g('kind')}|{g('target')}|{g('value')}"


def _plain(x: Any) -> Any:
    return asdict(x) if is_dataclass(x) else dict(x)


def save_plan(data_dir: Path, *, summary: dict[str, Any], writes: list[Any], to_complete: list[Any], owners: list[Any],
              written: bool = False) -> Path:
    """Save what the run computed. ``written`` says the writes were just made, so none stands pending."""
    path = Path(data_dir) / PLAN
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "savedAt": _now(), "written": written, "summary": summary,
        "writes": [{**_plain(w), "key": write_key(w)} for w in writes],
        "toComplete": [{"submissionId": getattr(t, "submission_id", None) if is_dataclass(t) else t.get("submissionId"),
                        "unit": getattr(t, "unit", "") if is_dataclass(t) else t.get("unit", ""),
                        "name": getattr(t, "name", "") if is_dataclass(t) else t.get("name", ""),
                        "left": list(getattr(t, "left", []) if is_dataclass(t) else t.get("left", []))} for t in to_complete],
        "owners": [{"unit": getattr(o, "unit", ""), "name": getattr(o, "name", ""), "status": getattr(getattr(o, "status", None), "value", str(getattr(o, "status", ""))),
                    "delivery": getattr(o, "delivery", ""), "actions": list(getattr(o, "actions", []))} if is_dataclass(o) else dict(o) for o in owners],
    }
    path.write_text(json.dumps(body, indent=1), encoding="utf-8")
    return path


def load_plan(data_dir: Path) -> dict[str, Any] | None:
    path = Path(data_dir) / PLAN
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def load_confirmations(data_dir: Path) -> dict[str, dict[str, str]]:
    path = Path(data_dir) / CONFIRMATIONS
    return json.loads(path.read_text(encoding="utf-8")).get("confirmed", {}) if path.is_file() else {}


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, "owner-info-confirmations", timeout=60, purpose=f"owner info: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


@_store_lock
def confirm(data_dir: Path, key: str, *, by: str, confirmed: bool = True) -> dict[str, dict[str, str]]:
    """Record that ``by`` confirmed (or withdrew the confirmation of) one planned write, by its key."""
    plan = load_plan(data_dir)
    if plan is None or key not in {w["key"] for w in plan.get("writes", [])}:
        raise KeyError(key)
    by = by.strip()
    if confirmed and not by:
        raise ValueError("a confirmation names who confirmed it")
    rows = load_confirmations(data_dir)
    if confirmed:
        rows[key] = {"by": by, "on": _now()}
    else:
        rows.pop(key, None)
    path = Path(data_dir) / CONFIRMATIONS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"savedAt": _now(), "confirmed": rows}, indent=1), encoding="utf-8")
    return rows


def status(data_dir: Path) -> dict[str, Any]:
    """The plan with each write's confirmation beside it, and whether every write is confirmed."""
    plan = load_plan(data_dir)
    if plan is None:
        return {"found": False, "note": "no plan saved; run jason owner-info --apply (a dry run) to compute one"}
    confirmed = load_confirmations(data_dir)
    writes = [{**w, "confirmedBy": confirmed.get(w["key"], {}).get("by", ""), "confirmedOn": confirmed.get(w["key"], {}).get("on", "")} for w in plan["writes"]]
    pending = [w for w in writes if not w["confirmedBy"]]
    return {"found": True, "savedAt": plan["savedAt"], "written": plan.get("written", False), "summary": plan.get("summary", {}),
            "writes": writes, "pending": len(pending), "allConfirmed": not pending and bool(writes),
            "toComplete": plan.get("toComplete", []), "owners": plan.get("owners", []),
            "command": APPLY if writes and not plan.get("written") else "",
            "caveats": ["Each write is a PayHOA tag change an owner's answer calls for; a person confirms it here and applies it from a terminal.",
                        "An answer needing a person stays open; jason never deletes or edits an owner's submission."]}
