"""A person's choice for one piece of paper mail, recorded once, where the mail-triage page reads it.

``jason mail --sync`` keeps what the mail service received and scanned. What to do with each envelope (scan it, forward
it, shred it, discard it, or keep it at the service) is a person's choice, made at the mail service, which may bill
for it. The choice is written here, in ``data/mail/triage.json``, one record per mail id. jason scans, forwards, shreds,
and discards nothing; it records the choice the person makes and acts on at the service.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

STORE = Path("mail") / "triage.json"


class Choice(Enum):
    SCAN = "scan"
    FORWARD = "forward"
    SHRED = "shred"
    DISCARD = "discard"
    KEEP = "keep"


CHOICES = tuple(c.value for c in Choice)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(data_dir: Path) -> dict[str, dict[str, Any]]:
    """The recorded choices by mail id."""
    path = Path(data_dir) / STORE
    if not path.is_file():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")).get("items", {}))


def save(data_dir: Path, items: dict[str, dict[str, Any]]) -> Path:
    path = Path(data_dir) / STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"savedAt": _now(), "items": items}, indent=1), encoding="utf-8")
    return path


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, "mail-triage", timeout=60, purpose=f"mail triage: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


@_store_lock
def choose(data_dir: Path, mail_id: str, *, choice: str, by: str, note: str = "") -> dict[str, Any]:
    """Record a person's choice for ``mail_id``; a later choice replaces it and the history keeps the change."""
    mail_id, choice, by, note = str(mail_id).strip(), choice.strip().lower(), by.strip(), note.strip()
    if not mail_id:
        raise ValueError("the choice names the mail item")
    if choice not in CHOICES:
        raise ValueError(f"choice is one of {', '.join(CHOICES)}")
    if not by:
        raise ValueError("the choice names who made it")
    items = load(data_dir)
    earlier = items.get(mail_id)
    now = _now()
    line = f"{now[:10]}: {earlier['choice']} -> {choice} by {by}" if earlier and earlier.get("choice") != choice else f"{now[:10]}: {choice} by {by}"
    items[mail_id] = {"mailId": mail_id, "choice": choice, "by": by, "on": now, "note": note,
                      "history": list((earlier or {}).get("history", [])) + [line]}
    save(data_dir, items)
    return items[mail_id]
