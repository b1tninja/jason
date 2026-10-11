"""The bill-attach queue: the unapproved PayHOA transactions that wait on a bill, from the stored snapshot.

``jason sync-bills`` reads PayHOA live, so a page cannot run it when it opens. The queue is read from what is on disk:
the PayHOA snapshot (``data/payhoa/transactions.json``, written by ``jason invoices --fetch``, with its ``syncedAt``),
routed offline with the profile's rules (``jason.sources.offline``), classed by the profile's payee rows
(``jason.community.payees``), and laid beside the last dry run a person ran (``jason.tasks.bill_dry_run``) when that run
was made against this snapshot. Nothing here calls PayHOA, a bill portal, Gmail, or Keeper, and nothing is written
(docs/console/handoff-mail-and-payment-attachments.md, Part B).

**What each row says.** ``status`` is the engine's own word where a dry run spoke for the row, and otherwise:
- ``already attached``: the snapshot lists an active attachment;
- ``unrouted``: no source owns it and no payee row selects it (class ``unknown``): a work item, not a log line;
- ``no bill expected``: a payee row says it is a transfer, a bank item, or a platform fee: the statement or the ledger is
  the record, so it is not a work item;
- ``no source yet``: a payee row selects a class (a county tax collector, an insurer) with no bill source to ask;
- ``not checked``: a source owns it and no dry run has looked since the snapshot.

A dry run older than the snapshot is not applied to a row: its words are kept beside as ``earlier`` and the page says so.
A ``matched`` row is a lead until a person attaches it.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.payees import PayeeClass, payee_of
from jason.tasks import bill_dry_run

REFRESH = "jason invoices --fetch"
DRY_RUN = "jason sync-bills --dry-run"
SOURCE_KEY = "payhoa-transactions"

STATUS_OF = {"matched": "matched", "ambiguous": "ambiguous", "no_match": "no match", "skipped": "already attached",
             "uploaded": "uploaded", "approved": "uploaded", "error": "error"}
CAVEATS = (
    "Read from the stored PayHOA snapshot; a transaction made since it was fetched is not listed. Nothing here calls PayHOA, "
    "a bill portal, or Gmail.",
    "A match is a lead until a person attaches it: the amount is exact, the date is within a window, and the bill must be the "
    "only one that fits. Which date matched depends on the source.",
    "An unrouted or no-source payment is not an error: jason does not know whose bill it is, and does not guess.",
)


def _day(value: Any) -> str:
    return str(value or "")[:10]


def _age_days(stamp: str, now: datetime) -> float | None:
    try:
        return (now - datetime.fromisoformat(stamp)).total_seconds() / 86400
    except (TypeError, ValueError):
        return None


def stale_after_days() -> float | None:
    """How old the snapshot may be before the page says so: the PayHOA transactions source's own default."""
    from jason.integrations.registry import cadence_for

    cad = cadence_for(SOURCE_KEY)
    return cad.stale_after_days if cad is not None else None


def _load_snapshot(data_dir: Path) -> dict[str, Any] | None:
    path = data_dir / bill_dry_run.SNAPSHOT
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _expense_like(tx: dict[str, Any], categories: dict[str, Any]) -> bool:
    """A payment the association made, as far as the snapshot says: not deleted, not a child line, not an income category."""
    if tx.get("deletedAt") or tx.get("parentId"):
        return False
    cat = categories.get(str(tx.get("categoryId"))) if tx.get("categoryId") is not None else None
    return not (isinstance(cat, dict) and cat.get("type") == "income")


def build(data_dir: Path | str, community: Any, registry: Any, *, now: datetime | None = None,
          stale_after: float | None = None) -> dict[str, Any]:
    """The queue. ``registry`` routes (``jason.sources.offline.routing_registry``); ``stale_after`` is in days."""
    root = Path(data_dir)
    now = now or datetime.now(timezone.utc)
    snap = _load_snapshot(root)
    if snap is None:
        return {"found": False, "asOf": now.isoformat(timespec="seconds"), "command": REFRESH,
                "reason": "No PayHOA snapshot on disk. The queue reads it; nothing here calls PayHOA.",
                "rows": [], "caveats": list(CAVEATS)}
    stamp = str(snap.get("syncedAt") or "")
    age = _age_days(stamp, now)
    limit = stale_after if stale_after is not None else stale_after_days()
    categories = snap.get("categories") or {}
    vendors = snap.get("vendors") or {}
    rules = tuple(community.payee_rules())

    run = bill_dry_run.load(root)
    current = bool(run) and run.get("snapshotSyncedAt") == stamp
    said = {int(r["transactionId"]): r for r in (run or {}).get("results", [])} if run else {}

    rows = []
    for tx in snap.get("transactions") or []:
        if tx.get("approved") is True or not _expense_like(tx, categories):
            continue
        source = registry.route(tx)
        payee = payee_of(tx, rules)
        active = [a for a in tx.get("attachments") or [] if not a.get("deletedAt")]
        row = {
            "transactionId": int(tx["id"]), "amountCents": int(tx["amount"]), "date": _day(tx.get("transactionDate")),
            "description": str(tx.get("description") or ""),
            "category": (categories.get(str(tx.get("categoryId"))) or {}).get("name"),
            "vendor": vendors.get(str(tx.get("vendorId"))) if tx.get("vendorId") is not None else None,
            "excluded": bool(tx.get("excluded")), "attachments": len(active),
            "source": source.name if source else None,
            "payeeClass": payee.value if payee is not PayeeClass.UNKNOWN or source is None else None,
            "dryRun": None, "earlier": None,
        }
        if active:
            row["status"] = "already attached"
        elif source is None and not payee.expects_bill:
            row["status"] = "no bill expected"
        elif source is None:
            row["status"] = "unrouted" if payee is PayeeClass.UNKNOWN else "no source yet"
        else:
            row["status"] = "not checked"
        spoke = said.get(row["transactionId"])
        if spoke and source is not None and not active:
            shown = {"status": STATUS_OF.get(spoke["status"], spoke["status"]), "detail": spoke.get("detail", ""),
                     "bill": spoke.get("bill")}
            if current:
                row["dryRun"], row["status"] = shown, shown["status"]
            else:
                row["earlier"] = shown
        rows.append(row)
    rows.sort(key=lambda r: (r["date"], r["transactionId"]), reverse=True)

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    needed = sorted({r["source"] for r in rows if r["source"] and r["status"] != "already attached"})
    return {
        "found": True, "asOf": now.isoformat(timespec="seconds"),
        "snapshot": {"syncedAt": stamp, "ageDays": None if age is None else round(age, 1), "staleAfterDays": limit,
                     "stale": bool(limit is not None and age is not None and age > limit), "command": REFRESH},
        "dryRun": None if not run else {"ranAt": run.get("ranAt"), "by": run.get("by") or None,
                                        "windowDays": run.get("windowDays"), "snapshotSyncedAt": run.get("snapshotSyncedAt"),
                                        "currentWithSnapshot": current, "command": DRY_RUN},
        "dryRunCommand": DRY_RUN, "sourcesNeeded": needed, "counts": counts,
        "withoutPdf": sum(1 for r in rows if r["attachments"] == 0), "rows": rows, "caveats": list(CAVEATS),
    }


__all__ = ["CAVEATS", "DRY_RUN", "REFRESH", "STATUS_OF", "build", "stale_after_days"]
