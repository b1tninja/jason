"""The bill-attach queue (``GET /api/bill-attach``; docs/console/handoff-mail-and-payment-attachments.md, Part B): the
unapproved PayHOA transactions that wait on a bill, from the stored snapshot, routed offline and laid beside the last dry
run a person ran. Read only, for a signed-in roster person (amounts and payees are P1).

It reads disk only: the snapshot ``jason invoices --fetch`` wrote, the profile's rules, and the dry run ``jason sync-bills
--dry-run`` kept. It calls no PayHOA, bill portal, Gmail, or Keeper, and attaches nothing: the sync and the attach are a
person's commands, shown with ``Command``. See ``jason.tasks.bill_queue``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

Args = dict[str, str]


def _settings() -> Any:
    try:
        from jason.config import Settings

        return Settings.load()
    except Exception:  # noqa: BLE001 - no .env: no category overrides, the profile's own rules
        return None


def bill_attach(args: Args) -> dict[str, Any]:
    """``GET /api/bill-attach[?source=&status=]``: the queue, optionally one source or one status."""
    from jason.community import community
    from jason.mcp.county import _data_dir
    from jason.sources.offline import routing_registry
    from jason.tasks import bill_queue
    from jason.web.access import signed_in

    signed_in()
    root, c = Path(_data_dir(None)), community()
    out = bill_queue.build(root, c, routing_registry(c, _settings(), root))
    if out.get("found"):
        source, status = (args.get("source") or "").strip(), (args.get("status") or "").strip()
        if source:
            out["rows"] = [r for r in out["rows"] if r["source"] == source]
        if status:
            out["rows"] = [r for r in out["rows"] if r["status"] == status]
    return out


__all__ = ["bill_attach"]
