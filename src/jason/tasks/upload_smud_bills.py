"""Match SMUD bill PDFs to unapproved PayHOA SMUD transactions and upload them."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from payhoa import PayhoaClient

from jason.config import DEFAULT_SMUD_CATEGORY_ID
from jason.smud_data import SmudBillStore
from jason.sources.attach import attach_bills
from jason.sources.registry import BillSourceRegistry
from jason.sources.smud import SmudBillSource
from jason.sources.types import (
    DEFAULT_DATE_WINDOW_DAYS,
    DEFAULT_ORG_ID,
    MatchResult,
    UploadReport,
    active_attachments,
)

__all__ = [
    "DEFAULT_DATE_WINDOW_DAYS",
    "DEFAULT_ORG_ID",
    "MatchResult",
    "UploadReport",
    "upload_smud_bills",
]

_active_attachments = active_attachments


def upload_smud_bills(
    client: PayhoaClient,
    bills: SmudBillStore,
    *,
    smud_client_factory: Callable[[], Any],
    org_id: int = DEFAULT_ORG_ID,
    date_window_days: int = DEFAULT_DATE_WINDOW_DAYS,
    dry_run: bool = False,
    approve: bool = False,
    smud_category_id: int | None = DEFAULT_SMUD_CATEGORY_ID,
) -> UploadReport:
    """Find unapproved SMUD txs, match cached bills, lazily fetch PDFs, upload."""
    registry = BillSourceRegistry(
        [
            SmudBillSource(
                bills,
                smud_client_factory,
                category_id=smud_category_id,
            )
        ]
    )
    return attach_bills(
        client,
        registry,
        org_id=org_id,
        date_window_days=date_window_days,
        dry_run=dry_run,
        approve=approve,
    )
