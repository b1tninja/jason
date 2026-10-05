"""Shared types for bill sources and attach-bills orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

def profile_org_id(org_id: int | None = None) -> int:
    """The PayHOA org id asked for, else the active profile's."""
    if org_id is not None:
        return org_id
    from jason.community import community

    return community().org_id


def __getattr__(name: str):
    if name == "DEFAULT_ORG_ID":
        return profile_org_id()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
DEFAULT_DATE_WINDOW_DAYS = 7


@dataclass(frozen=True)
class BillNeed:
    """A PayHOA transaction that needs a matching utility bill PDF."""

    amount_cents: int
    around: date
    window_days: int = DEFAULT_DATE_WINDOW_DAYS
    transaction_id: int = 0
    description: str = ""

    @property
    def key(self) -> tuple[int, str, int]:
        """Stable key for mapping resolve results back to this need."""
        return (self.transaction_id, self.around.isoformat(), self.amount_cents)


@dataclass
class ResolvedBill:
    """Source-agnostic bill handle after cache match or portal resolve."""

    source: str
    bill_id: str
    account_number: str
    bill_date: date
    amount_cents: int
    pdf_path: Path | None = None
    view_bill_token: str = field(default="", repr=False)   # the portal session's handle on the bill: never shown
    pdf_url: str = ""

    @property
    def has_pdf(self) -> bool:
        return self.pdf_path is not None and self.pdf_path.is_file()

    @property
    def identity(self) -> tuple[str, date, int]:
        return (self.account_number, self.bill_date, self.amount_cents)


@dataclass
class MatchResult:
    transaction_id: int
    amount_cents: int
    transaction_date: date
    description: str
    bill: Any = None
    status: str = "pending"
    detail: str = ""
    upload_url: str | None = None


@dataclass
class UploadReport:
    results: list[MatchResult] = field(default_factory=list)

    def summary(self) -> str:
        counts: dict[str, int] = {}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
        parts = [f"{k}={v}" for k, v in sorted(counts.items())]
        return f"{len(self.results)} transactions: " + ", ".join(parts)


def active_attachments(tx: dict[str, Any]) -> list[dict[str, Any]]:
    attachments = tx.get("attachments") or []
    return [a for a in attachments if not a.get("deletedAt")]


def need_matches_bill(
    need: BillNeed, *, amount_cents: int, bill_date: date
) -> bool:
    if amount_cents != need.amount_cents:
        return False
    return abs((bill_date - need.around).days) <= need.window_days
