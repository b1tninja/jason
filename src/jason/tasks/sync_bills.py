"""PayHOA-first bill sync: inspect pending utility txs, sync only needed sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from payhoa import PayhoaClient

from jason.payhoa_tx import parse_tx_date
from jason.sources.attach import attach_bills
from jason.sources.registry import BillSourceRegistry
from jason.sources.types import UploadReport, active_attachments, profile_org_id


@dataclass(frozen=True)
class PendingUtilityTx:
    transaction_id: int
    amount_cents: int
    transaction_date: date
    description: str
    source: str
    has_attachments: bool = False


@dataclass
class SyncBillsReport:
    pending: list[PendingUtilityTx] = field(default_factory=list)
    sources_needed: list[str] = field(default_factory=list)
    sources_synced: list[str] = field(default_factory=list)
    sync_summaries: dict[str, str] = field(default_factory=dict)
    upload: UploadReport | None = None
    skipped_reason: str = ""

    def summary(self) -> str:
        lines = [
            f"pending_utility={len(self.pending)}",
            f"sources_needed={','.join(self.sources_needed) or '(none)'}",
            f"sources_synced={','.join(self.sources_synced) or '(none)'}",
        ]
        if self.skipped_reason:
            lines.append(f"skipped={self.skipped_reason}")
        if self.upload is not None:
            lines.append(self.upload.summary())
        return "\n".join(lines)


def list_pending_utility_transactions(
    client: PayhoaClient,
    registry: BillSourceRegistry,
    *,
    org_id: int | None = None,
    fetch_details: bool = True,
) -> list[PendingUtilityTx]:
    """Return unapproved PayHOA txs that route to a registered bill source."""
    org_id = profile_org_id(org_id)
    pending: list[PendingUtilityTx] = []
    for tx in client.iter_transactions(org_id, reviewed=False):
        if tx.get("approved") is True:
            continue
        source = registry.route(tx)
        if source is None:
            continue

        tx_id = int(tx["id"])
        has_attachments = False
        if fetch_details:
            detail = client.get_transaction(org_id, tx_id)
            has_attachments = bool(active_attachments(detail))

        pending.append(
            PendingUtilityTx(
                transaction_id=tx_id,
                amount_cents=int(tx["amount"]),
                transaction_date=parse_tx_date(tx["transactionDate"]),
                description=str(tx.get("description") or ""),
                source=source.name,
                has_attachments=has_attachments,
            )
        )
    return pending


def sources_needing_sync(pending: list[PendingUtilityTx]) -> list[str]:
    """Sources with at least one pending tx that still needs an attachment."""
    needed: list[str] = []
    seen: set[str] = set()
    for tx in pending:
        if tx.has_attachments:
            continue
        if tx.source in seen:
            continue
        seen.add(tx.source)
        needed.append(tx.source)
    return needed


def sync_bills(
    client: PayhoaClient,
    registry: BillSourceRegistry,
    *,
    sync_source: Callable[[str], Any],
    org_id: int | None = None,
    date_window_days: int = 7,
    dry_run: bool = False,
    approve: bool = False,
    skip_sync: bool = False,
    sources: list[str] | None = None,
) -> SyncBillsReport:
    """Inspect PayHOA first, sync only needed portals, then attach PDFs."""
    org_id = profile_org_id(org_id)
    if sources:
        registry = registry.filter(set(sources))

    pending = list_pending_utility_transactions(
        client, registry, org_id=org_id, fetch_details=True
    )
    needed = sources_needing_sync(pending)
    report = SyncBillsReport(pending=pending, sources_needed=list(needed))

    if not needed:
        report.skipped_reason = "no unreviewed utility txs without attachments"
        report.upload = UploadReport()
        return report

    if dry_run:
        report.skipped_reason = "dry-run (portal sync skipped)"
        report.upload = attach_bills(
            client,
            registry.filter(set(needed)),
            org_id=org_id,
            date_window_days=date_window_days,
            dry_run=True,
            approve=False,
        )
        return report

    if not skip_sync:
        for name in needed:
            result = sync_source(name)
            report.sources_synced.append(name)
            summary = getattr(result, "summary", None)
            report.sync_summaries[name] = (
                summary() if callable(summary) else str(result)
            )

    report.upload = attach_bills(
        client,
        registry.filter(set(needed)),
        org_id=org_id,
        date_window_days=date_window_days,
        dry_run=False,
        approve=approve,
    )
    return report
