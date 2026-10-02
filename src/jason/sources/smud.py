"""SMUD bill source adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jason.payhoa_tx import is_smud_transaction
from jason.smud_data import BillMatch, SmudBillStore
from jason.sources.types import BillNeed, ResolvedBill, need_matches_bill


class SmudBillSource:
    name = "smud"

    def __init__(
        self,
        store: SmudBillStore,
        client_factory,
        *,
        category_id: int | None = None,
    ) -> None:
        self._store = store
        self._client_factory = client_factory
        self._category_id = category_id

    def matches_transaction(self, tx: dict[str, Any]) -> bool:
        if self._category_id is None:
            return is_smud_transaction(tx)
        return is_smud_transaction(tx, smud_category_id=self._category_id)

    def _to_resolved(self, bill: BillMatch) -> ResolvedBill:
        return ResolvedBill(
            source=self.name,
            bill_id=bill.bill_id,
            account_number=bill.account_number,
            bill_date=bill.bill_date,
            amount_cents=bill.amount_cents,
            pdf_path=bill.pdf_path,
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
        # Map each need to a unique cached bill (identity-deduped).
        used: set[tuple[str, object, int]] = set()
        need_bills: list[tuple[BillNeed, BillMatch]] = []
        for need in needs:
            candidates = self._store.find_bills(
                need.amount_cents,
                around=need.around,
                window_days=need.window_days,
            )
            chosen = None
            for bill in candidates:
                key = (bill.account_number, bill.bill_date, bill.amount_cents)
                if key in used:
                    continue
                match_date = bill.due_date or bill.bill_date
                if need_matches_bill(
                    need, amount_cents=bill.amount_cents, bill_date=match_date
                ):
                    chosen = bill
                    used.add(key)
                    break
            if chosen is not None:
                need_bills.append((need, chosen))

        if not need_bills:
            return {}

        client = self._client_factory()
        refreshed = self._store.resolve_needs(
            client,
            [b for _, b in need_bills],
            ensure_pdfs=ensure_pdfs,
        )
        by_id = {b.bill_id: b for b in refreshed}
        out: dict[tuple[int, str, int], ResolvedBill] = {}
        for need, original in need_bills:
            bill = by_id.get(original.bill_id, original)
            out[need.key] = self._to_resolved(bill)
        return out

    def ensure_pdf(self, bill: ResolvedBill) -> Path:
        match = BillMatch(
            bill_id=bill.bill_id,
            account_number=bill.account_number,
            bill_date=bill.bill_date,
            amount_cents=bill.amount_cents,
            pdf_path=bill.pdf_path,
            pdf_url=bill.pdf_url,
        )
        return self._store.ensure_bill_pdf(match, self._client_factory())
