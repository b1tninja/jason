"""Orchestrate PayHOA unapproved txs → bill sources → PDF upload."""

from __future__ import annotations

from payhoa import PayhoaClient

from jason.payhoa_tx import parse_tx_date
from jason.sources.registry import BillSourceRegistry
from jason.sources.types import (
    DEFAULT_DATE_WINDOW_DAYS,
    profile_org_id,
    BillNeed,
    MatchResult,
    ResolvedBill,
    UploadReport,
    active_attachments,
)


def attach_bills(
    client: PayhoaClient,
    registry: BillSourceRegistry,
    *,
    org_id: int | None = None,
    date_window_days: int = DEFAULT_DATE_WINDOW_DAYS,
    dry_run: bool = False,
    approve: bool = False,
) -> UploadReport:
    """Scan unapproved txs once, route to sources, batch-resolve, upload PDFs."""
    org_id = profile_org_id(org_id)
    report = UploadReport()

    # need_key -> (need, source_name, result skeleton fields)
    pending: list[tuple[BillNeed, str]] = []
    # Pre-seed results for skipped / unrouted
    early: list[MatchResult] = []

    for tx in client.iter_transactions(org_id, reviewed=False):
        if tx.get("approved") is True:
            continue

        tx_id = int(tx["id"])
        amount = int(tx["amount"])
        tx_date = parse_tx_date(tx["transactionDate"])
        description = str(tx.get("description") or "")

        source = registry.route(tx)
        if source is None:
            continue

        detail = client.get_transaction(org_id, tx_id)
        if active_attachments(detail):
            early.append(
                MatchResult(
                    transaction_id=tx_id,
                    amount_cents=amount,
                    transaction_date=tx_date,
                    description=description,
                    status="skipped",
                    detail="already has attachment(s)",
                )
            )
            continue

        need = BillNeed(
            amount_cents=amount,
            around=tx_date,
            window_days=date_window_days,
            transaction_id=tx_id,
            description=description,
        )
        pending.append((need, source.name))

    report.results.extend(early)

    # Group needs by source
    by_source: dict[str, list[BillNeed]] = {}
    for need, source_name in pending:
        by_source.setdefault(source_name, []).append(need)

    # Cache match + batch resolve per source
    resolved_by_need: dict[tuple[int, str, int], ResolvedBill] = {}
    ambiguous: dict[tuple[int, str, int], str] = {}
    no_match: set[tuple[int, str, int]] = set()

    for source in registry.sources:
        needs = by_source.get(source.name) or []
        if not needs:
            continue

        # Unique cache assignment first (for dry-run reporting / ambiguity)
        used_identities: set[tuple] = set()
        to_resolve: list[BillNeed] = []
        for need in needs:
            candidates = [
                b
                for b in source.find_cached(need)
                if b.identity not in used_identities
            ]
            if not candidates:
                to_resolve.append(need)
                continue
            if len(candidates) > 1:
                # Still try resolve path if no unique identity; treat as ambiguous
                # only when multiple distinct identities remain.
                identities = {c.identity for c in candidates}
                if len(identities) > 1:
                    ambiguous[need.key] = ", ".join(
                        sorted({c.bill_id for c in candidates})
                    )
                    continue
            bill = candidates[0]
            used_identities.add(bill.identity)
            if bill.has_pdf or dry_run:
                resolved_by_need[need.key] = bill
            else:
                to_resolve.append(need)

        if dry_run:
            # For dry-run, also surface cache-only matches without PDFs as matched
            for need in to_resolve:
                candidates = [
                    b
                    for b in source.find_cached(need)
                    if b.identity not in used_identities
                    and need.key not in ambiguous
                ]
                if not candidates:
                    no_match.add(need.key)
                    continue
                identities = {c.identity for c in candidates}
                if len(identities) > 1:
                    ambiguous[need.key] = ", ".join(
                        sorted({c.bill_id for c in candidates})
                    )
                    continue
                bill = candidates[0]
                used_identities.add(bill.identity)
                resolved_by_need[need.key] = bill
            continue

        if to_resolve:
            got = source.resolve(to_resolve, ensure_pdfs=True)
            for need in to_resolve:
                if need.key in got:
                    resolved_by_need[need.key] = got[need.key]
                elif need.key not in ambiguous:
                    no_match.add(need.key)

    # Emit per-need results and upload
    for need, source_name in pending:
        source = registry.get(source_name)
        assert source is not None

        if need.key in ambiguous:
            report.results.append(
                MatchResult(
                    transaction_id=need.transaction_id,
                    amount_cents=need.amount_cents,
                    transaction_date=need.around,
                    description=need.description,
                    status="ambiguous",
                    detail=f"multiple bills: {ambiguous[need.key]}",
                )
            )
            continue

        bill = resolved_by_need.get(need.key)
        if bill is None:
            report.results.append(
                MatchResult(
                    transaction_id=need.transaction_id,
                    amount_cents=need.amount_cents,
                    transaction_date=need.around,
                    description=need.description,
                    status="no_match",
                    detail=(
                        f"no bill with amount {need.amount_cents} within "
                        f"±{need.window_days}d"
                    ),
                )
            )
            continue

        result = MatchResult(
            transaction_id=need.transaction_id,
            amount_cents=need.amount_cents,
            transaction_date=need.around,
            description=need.description,
            bill=bill,
            status="matched",
            detail=(
                f"bill {bill.bill_id} ({bill.bill_date}) "
                f"pdf={'yes' if bill.has_pdf else 'lazy'} "
                f"source={bill.source}"
            ),
        )

        if dry_run:
            report.results.append(result)
            continue

        try:
            pdf_path = (
                bill.pdf_path
                if bill.has_pdf and bill.pdf_path is not None
                else source.ensure_pdf(bill)
            )
            upload = client.upload_attachment(
                org_id, need.transaction_id, pdf_path
            )
            result.status = "uploaded"
            result.upload_url = (
                upload.get("url") if isinstance(upload, dict) else None
            )
            result.detail = f"uploaded {pdf_path.name} source={bill.source}"

            if approve:
                client.update_transaction(
                    org_id, need.transaction_id, approved=True
                )
                result.status = "approved"
                result.detail += "; approved"
        except Exception as exc:  # noqa: BLE001 — per-tx; continue others
            result.status = "error"
            result.detail = str(exc)

        report.results.append(result)

    return report
