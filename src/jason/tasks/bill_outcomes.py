"""What a person decided about a payment that had no bill: the investigation's outcome, kept (docs/console/handoff-mail-and-
payment-attachments.md, Part C). ``data/bills/investigations.json``.

The outcome is a person's word with their name and the day: ``attached-bill``, ``attached-receipt-only`` (proof of payment
linked; the bill PDF is still missing), ``not-our-bill``, ``waiting-for-mail``, or ``escalated``. It is append only: a later
outcome for the same transaction supersedes the earlier one in the view and never erases it, and nothing here touches PayHOA,
attaches a file, or approves a transaction. Whether a receipt may stand in for a bill at the treasurer's review is the
association's policy, not this file's: ``attached-receipt-only`` keeps the transaction listed in the invoice review.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jason.tasks.bill_investigation import OUTCOMES

STORE = Path("bills") / "investigations.json"
LOCK = "bill-investigations"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(data_dir: Path | str) -> list[dict[str, Any]]:
    path = Path(data_dir) / STORE
    if not path.is_file():
        return []
    try:
        return [dict(r) for r in json.loads(path.read_text(encoding="utf-8")).get("outcomes", []) if isinstance(r, dict)]
    except (OSError, ValueError):
        return []


def history(data_dir: Path | str, transaction_id: int) -> list[dict[str, Any]]:
    """Every outcome recorded for the transaction, oldest first; the last one stands."""
    return [r for r in load(data_dir) if r.get("transactionId") == int(transaction_id)]


def record(data_dir: Path | str, transaction_id: int, outcome: str, *, by: str, note: str = "", doc: str = "",
           now: str | None = None) -> dict[str, Any]:
    """Append a person's outcome for ``transaction_id``. ``doc`` is the record it points to (a library id), kept as given."""
    from jason.locks import Resource, hold

    by, note, doc = (by or "").strip(), (note or "").strip(), (doc or "").strip()
    if not by:
        raise ValueError("name who is recording this")
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome is one of: {', '.join(OUTCOMES)}")
    if any(ch.isspace() for ch in doc):
        raise ValueError("doc is a record's id, not words")
    if outcome in ("attached-bill", "attached-receipt-only") and not doc:
        raise ValueError(f"{outcome} names the record it points to (doc)")
    at = now or _now()
    row = {"transactionId": int(transaction_id), "outcome": outcome, "by": by, "at": at, "on": at[:10],
           **({"doc": doc} if doc else {}), **({"note": note[:300]} if note else {})}
    with hold(Resource.STORE, LOCK, timeout=60, purpose="bill investigation outcome"):
        rows = load(data_dir)
        rows.append(row)
        path = Path(data_dir) / STORE
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"savedAt": _now(), "outcomes": rows}, indent=1), encoding="utf-8")
        tmp.replace(path)
    return row


__all__ = ["OUTCOMES", "STORE", "history", "load", "record"]
