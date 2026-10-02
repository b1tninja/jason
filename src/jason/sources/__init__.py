"""Bill source registry and attach-bills orchestration."""

from jason.sources.attach import attach_bills
from jason.sources.idoxs import IdoxsBillSource
from jason.sources.registry import BillSourceRegistry
from jason.sources.smud import SmudBillSource
from jason.sources.types import (
    DEFAULT_DATE_WINDOW_DAYS,
    BillNeed,
    MatchResult,
    ResolvedBill,
    UploadReport,
)

__all__ = [
    "BillNeed",
    "BillSourceRegistry",
    "DEFAULT_DATE_WINDOW_DAYS",
    "IdoxsBillSource",
    "MatchResult",
    "ResolvedBill",
    "SmudBillSource",
    "UploadReport",
    "attach_bills",
]
