"""The last dry run of ``jason sync-bills``, kept so the console can show it with its age.

``sync-bills --dry-run`` reads PayHOA live (every routed transaction, and its detail) and lists, for each, whether a bill
matches, is ambiguous, or is not found. That is too slow and too live to run when a page opens, so the result is written
here when a person runs it and the console reads the file (docs/console/handoff-mail-and-payment-attachments.md, "What the
queue reads"). It records which PayHOA snapshot was current when it ran, so a page can say a dry run is older than the
snapshot it is shown beside. A matched row is a lead until a person attaches it; nothing here uploads or approves.

``data/bills/last-dry-run.json``: names, amounts, dates, and bill ids only. No PDF, no account holder, no address.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE = Path("bills") / "last-dry-run.json"
SNAPSHOT = Path("payhoa") / "transactions.json"
_STAMP = re.compile(r'"syncedAt"\s*:\s*"([^"]+)"')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def snapshot_stamp(data_dir: Path | str) -> str:
    """The PayHOA snapshot's own ``syncedAt`` ("" when there is none); only its head is read."""
    path = Path(data_dir) / SNAPSHOT
    if not path.is_file():
        return ""
    with path.open("r", encoding="utf-8") as f:
        found = _STAMP.search(f.read(4096))
    return found.group(1) if found else ""


def _result(r: Any) -> dict[str, Any]:
    bill = getattr(r, "bill", None)
    return {"transactionId": r.transaction_id, "amountCents": r.amount_cents, "date": r.transaction_date.isoformat(),
            "status": r.status, "detail": r.detail,
            "bill": ({"id": bill.bill_id, "source": bill.source, "date": bill.bill_date.isoformat(),
                      "hasPdf": bool(bill.has_pdf)} if bill is not None else None)}


def record(data_dir: Path | str, report: Any, *, window_days: int, by: str = "", now: str | None = None) -> Path:
    """Keep ``report`` (a ``SyncBillsReport`` from a dry run) as the last dry run, replacing the one before it."""
    body = {
        "ranAt": now or _now(), "by": (by or "").strip(), "windowDays": window_days,
        "snapshotSyncedAt": snapshot_stamp(data_dir),
        "sourcesNeeded": list(report.sources_needed),
        "pending": [{"transactionId": p.transaction_id, "amountCents": p.amount_cents,
                     "date": p.transaction_date.isoformat(), "source": p.source, "hasAttachments": p.has_attachments}
                    for p in report.pending],
        "unrouted": [{"transactionId": u.transaction_id, "amountCents": u.amount_cents,
                      "date": u.transaction_date.isoformat(), "payee": u.payee, "hasAttachments": u.has_attachments}
                     for u in report.unrouted],
        "results": [_result(r) for r in (report.upload.results if report.upload else [])],
    }
    path = Path(data_dir) / STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(body, indent=1), encoding="utf-8")
    tmp.replace(path)
    return path


def load(data_dir: Path | str) -> dict[str, Any] | None:
    path = Path(data_dir) / STORE
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


__all__ = ["SNAPSHOT", "STORE", "load", "record", "snapshot_stamp"]
