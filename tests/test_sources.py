"""Unit tests for bill source registry and attach orchestration."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from jason.sources.attach import attach_bills
from jason.sources.registry import BillSourceRegistry
from jason.sources.types import BillNeed, ResolvedBill, need_matches_bill


class _FakeSource:
    def __init__(self, name: str, match_fn, cached: list[ResolvedBill] | None = None):
        self.name = name
        self._match_fn = match_fn
        self._cached = cached or []
        self.resolve_calls: list[list[BillNeed]] = []

    def matches_transaction(self, tx: dict[str, Any]) -> bool:
        return self._match_fn(tx)

    def find_cached(self, need: BillNeed) -> list[ResolvedBill]:
        return [
            b
            for b in self._cached
            if need_matches_bill(
                need, amount_cents=b.amount_cents, bill_date=b.bill_date
            )
        ]

    def resolve(
        self,
        needs: list[BillNeed],
        *,
        ensure_pdfs: bool = True,
    ) -> dict[tuple[int, str, int], ResolvedBill]:
        self.resolve_calls.append(list(needs))
        out: dict[tuple[int, str, int], ResolvedBill] = {}
        for need in needs:
            for bill in self.find_cached(need):
                out[need.key] = bill
                break
        return out

    def ensure_pdf(self, bill: ResolvedBill) -> Path:
        assert bill.pdf_path is not None
        return bill.pdf_path


class _FakePayhoa:
    def __init__(self, txs: list[dict[str, Any]]):
        self._txs = txs

    def iter_transactions(self, org_id: int, reviewed=False):
        del org_id, reviewed
        yield from self._txs

    def get_transaction(self, org_id: int, tx_id: int) -> dict[str, Any]:
        del org_id
        for tx in self._txs:
            if int(tx["id"]) == tx_id:
                return tx
        return {"id": tx_id, "attachments": []}


def test_need_matches_bill_window():
    need = BillNeed(amount_cents=100, around=date(2026, 6, 10), window_days=7)
    assert need_matches_bill(need, amount_cents=100, bill_date=date(2026, 6, 15))
    assert not need_matches_bill(need, amount_cents=100, bill_date=date(2026, 5, 1))
    assert not need_matches_bill(need, amount_cents=99, bill_date=date(2026, 6, 10))


def test_registry_routes_first_match():
    smud = _FakeSource(
        "smud",
        lambda tx: "SMUD" in str(tx.get("description", "")).upper(),
    )
    idoxs = _FakeSource(
        "idoxs",
        lambda tx: "SACRAMENTO" in str(tx.get("description", "")).upper(),
    )
    # SMUD description also contains nothing about sacramento
    registry = BillSourceRegistry([smud, idoxs])
    assert registry.route({"description": "SMUD payment"}).name == "smud"
    assert registry.route({"description": "CITY OF SACRAMENTO"}).name == "idoxs"
    assert registry.route({"description": "Other vendor"}) is None


def test_attach_bills_dry_run_uses_cache_no_resolve():
    bill = ResolvedBill(
        source="smud",
        bill_id="a-2026-06-01-100",
        account_number="a",
        bill_date=date(2026, 6, 1),
        amount_cents=100,
        pdf_path=None,
    )
    smud = _FakeSource(
        "smud",
        lambda tx: True,
        cached=[bill],
    )
    registry = BillSourceRegistry([smud])
    client = _FakePayhoa(
        [
            {
                "id": 1,
                "amount": 100,
                "transactionDate": "2026-06-05",
                "description": "SMUD",
                "approved": False,
                "attachments": [],
            }
        ]
    )
    report = attach_bills(client, registry, dry_run=True)
    assert len(report.results) == 1
    assert report.results[0].status == "matched"
    assert smud.resolve_calls == []


def test_attach_bills_skips_attachments():
    smud = _FakeSource("smud", lambda tx: True)
    registry = BillSourceRegistry([smud])
    client = _FakePayhoa(
        [
            {
                "id": 2,
                "amount": 50,
                "transactionDate": "2026-06-05",
                "description": "SMUD",
                "approved": False,
                "attachments": [{"id": 9, "deletedAt": None}],
            }
        ]
    )
    report = attach_bills(client, registry, dry_run=True)
    assert report.results[0].status == "skipped"
