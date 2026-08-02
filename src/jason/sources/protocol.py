"""BillSource protocol for registered utility bill providers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from jason.sources.types import BillNeed, ResolvedBill


@runtime_checkable
class BillSource(Protocol):
    """A registered bill provider (SMUD, City of Sacramento / i-doxs, …)."""

    @property
    def name(self) -> str: ...

    def matches_transaction(self, tx: dict[str, Any]) -> bool:
        """True if this source owns the PayHOA transaction."""
        ...

    def find_cached(self, need: BillNeed) -> list[ResolvedBill]:
        """Bills in the local cache matching amount/date window."""
        ...

    def resolve(
        self,
        needs: list[BillNeed],
        *,
        ensure_pdfs: bool = True,
    ) -> dict[tuple[int, str, int], ResolvedBill]:
        """Resolve needs in one portal session.

        Returns a map of BillNeed.key -> ResolvedBill for satisfied needs.
        """
        ...

    def ensure_pdf(self, bill: ResolvedBill) -> Path:
        """Return a local PDF path, downloading if needed."""
        ...
