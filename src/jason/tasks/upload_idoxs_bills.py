"""Match i-doxs bill PDFs to unapproved City of Sacramento PayHOA transactions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from payhoa import PayhoaClient

from jason.config import DEFAULT_IDOXS_CATEGORY_ID
from jason.idoxs_data import IdoxsBillStore
from jason.sources.attach import attach_bills
from jason.sources.idoxs import IdoxsBillSource
from jason.sources.registry import BillSourceRegistry
from jason.sources.types import (
    DEFAULT_DATE_WINDOW_DAYS,
    DEFAULT_ORG_ID,
    UploadReport,
)


def upload_idoxs_bills(
    client: PayhoaClient,
    bills: IdoxsBillStore,
    *,
    idoxs_client_factory: Callable[[], Any],
    org_id: int = DEFAULT_ORG_ID,
    date_window_days: int = DEFAULT_DATE_WINDOW_DAYS,
    dry_run: bool = False,
    approve: bool = False,
    category_id: int | None = DEFAULT_IDOXS_CATEGORY_ID,
) -> UploadReport:
    """Find unapproved City of Sacramento txs, match cached bills, upload PDFs."""
    registry = BillSourceRegistry(
        [
            IdoxsBillSource(
                bills,
                idoxs_client_factory,
                category_id=category_id,
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
