"""City of Sacramento (i-doxs) bill source adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jason.idoxs_data import IdoxsBillMatch, IdoxsBillStore
from jason.payhoa_tx import is_city_sac_transaction
from jason.sources.types import BillNeed, ResolvedBill, need_matches_bill


class IdoxsBillSource:
    name = "idoxs"

    def __init__(
        self,
        store: IdoxsBillStore,
        client_factory,
        *,
        category_id: int | None = 1245485,
    ) -> None:
        self._store = store
        self._client_factory = client_factory
        self._category_id = category_id

    def matches_transaction(self, tx: dict[str, Any]) -> bool:
        return is_city_sac_transaction(tx, category_id=self._category_id)

    def _to_resolved(self, bill: IdoxsBillMatch) -> ResolvedBill:
        return ResolvedBill(
            source=self.name,
            bill_id=bill.bill_id,
            account_number=bill.account_number,
            bill_date=bill.bill_date,
            amount_cents=bill.amount_cents,
            pdf_path=bill.pdf_path,
            view_bill_token=bill.view_bill_token,
            pdf_url=bill.pdf_url,
        )

    def find_cached(self, need: BillNeed) -> list[ResolvedBill]:
        return [
            self._to_resolved(b)
            for b in self._store.find_bills(
                need.amount_cents,
                around=need.around,
                window_days=need.window_days,
            )
        ]

    def resolve(
        self,
        needs: list[BillNeed],
        *,
        ensure_pdfs: bool = True,
    ) -> dict[tuple[int, str, int], ResolvedBill]:
        if not needs:
            return {}

        client = self._client_factory()
        specs = [
            (n.amount_cents, n.around, n.window_days) for n in needs
        ]
        matches = self._store.resolve_needs(
            client, specs, ensure_pdfs=ensure_pdfs
        )

        # Assign each need a unique bill by identity
        used: set[tuple[str, object, int]] = set()
        out: dict[tuple[int, str, int], ResolvedBill] = {}
        for need in needs:
            for bill in matches:
                key = (bill.account_number, bill.bill_date, bill.amount_cents)
                if key in used:
                    continue
                if need_matches_bill(
                    need, amount_cents=bill.amount_cents, bill_date=bill.bill_date
                ):
                    used.add(key)
                    out[need.key] = self._to_resolved(bill)
                    break
            if need.key in out:
                continue
            # Fall back to cache-only match (metadata without portal hit)
            for bill in self.find_cached(need):
                key = bill.identity
                if key in used:
                    continue
                used.add(key)
                out[need.key] = bill
                break
        return out

    def ensure_pdf(self, bill: ResolvedBill) -> Path:
        match = IdoxsBillMatch(
            bill_id=bill.bill_id,
            account_number=bill.account_number,
            bill_date=bill.bill_date,
            amount_cents=bill.amount_cents,
            pdf_path=bill.pdf_path,
            view_bill_token=bill.view_bill_token,
            pdf_url=bill.pdf_url,
        )
        return self._store.ensure_bill_pdf(match, self._client_factory())
