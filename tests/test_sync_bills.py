"""Unit tests for PayHOA-first sync-bills orchestration."""

from __future__ import annotations

from datetime import date
from typing import Any

from jason.sources.registry import BillSourceRegistry
from jason.sources.types import ResolvedBill
from jason.tasks.sync_bills import (
    PendingUtilityTx,
    sources_needing_sync,
    sync_bills,
)


class _FakeSource:
    def __init__(self, name: str, match_fn):
        self.name = name
        self._match_fn = match_fn
        self.resolve_calls: list = []

    def matches_transaction(self, tx: dict[str, Any]) -> bool:
        return self._match_fn(tx)

    def find_cached(self, need):
        return [
            ResolvedBill(
                source=self.name,
                bill_id=f"{self.name}-{need.amount_cents}",
                account_number="1",
                bill_date=need.around,
                amount_cents=need.amount_cents,
                pdf_path=None,
            )
        ]

    def resolve(self, needs, *, ensure_pdfs: bool = True):
        self.resolve_calls.append(list(needs))
        return {need.key: self.find_cached(need)[0] for need in needs}

    def ensure_pdf(self, bill: ResolvedBill):
        raise AssertionError("ensure_pdf should not run in dry-run")


class _FakePayhoa:
    def __init__(self, txs: list[dict[str, Any]]):
        self._txs = txs
        self.detail_calls: list[int] = []

    def iter_transactions(self, org_id: int, reviewed=False):
        del org_id, reviewed
        yield from self._txs

    def get_transaction(self, org_id: int, tx_id: int) -> dict[str, Any]:
        del org_id
        self.detail_calls.append(tx_id)
        for tx in self._txs:
            if int(tx["id"]) == tx_id:
                return tx
        return {"id": tx_id, "attachments": []}


def test_sources_needing_sync_skips_attached():
    pending = [
        PendingUtilityTx(1, 100, date(2026, 8, 1), "SMUD", "smud", True),
        PendingUtilityTx(2, 200, date(2026, 8, 1), "CITY", "idoxs", False),
        PendingUtilityTx(3, 300, date(2026, 8, 1), "SMUD", "smud", False),
    ]
    assert sources_needing_sync(pending) == ["idoxs", "smud"]


def test_sync_bills_payhoa_first_syncs_only_needed_sources():
    smud = _FakeSource("smud", lambda tx: "SMUD" in str(tx.get("description", "")).upper())
    idoxs = _FakeSource(
        "idoxs",
        lambda tx: "SACRAMEN" in str(tx.get("description", "")).upper(),
    )
    registry = BillSourceRegistry([smud, idoxs])
    client = _FakePayhoa(
        [
            {
                "id": 1,
                "amount": 5760,
                "transactionDate": "2026-08-31",
                "description": "ORIG CO NAME:SMUD",
                "approved": False,
                "attachments": [],
            },
            {
                "id": 2,
                "amount": 999,
                "transactionDate": "2026-08-31",
                "description": "AERO-LITE",
                "approved": False,
                "attachments": [],
            },
        ]
    )
    synced: list[str] = []

    def sync_source(name: str):
        synced.append(name)
        return type("R", (), {"summary": lambda self: f"synced {name}"})()

    report = sync_bills(
        client,
        registry,
        sync_source=sync_source,
        dry_run=False,
    )
    assert [p.source for p in report.pending] == ["smud"]
    assert report.sources_needed == ["smud"]
    assert synced == ["smud"]
    assert report.sources_synced == ["smud"]
    assert report.upload is not None
    assert len(report.upload.results) == 1


def test_sync_bills_dry_run_skips_portal_sync():
    smud = _FakeSource("smud", lambda tx: True)
    registry = BillSourceRegistry([smud])
    client = _FakePayhoa(
        [
            {
                "id": 9,
                "amount": 100,
                "transactionDate": "2026-08-31",
                "description": "SMUD",
                "approved": False,
                "attachments": [],
            }
        ]
    )
    synced: list[str] = []
    report = sync_bills(
        client,
        registry,
        sync_source=lambda name: synced.append(name),
        dry_run=True,
    )
    assert synced == []
    assert report.sources_needed == ["smud"]
    assert report.sources_synced == []
    assert "dry-run" in report.skipped_reason
    assert report.upload is not None
    assert report.upload.results[0].status == "matched"


def test_sync_bills_noop_when_nothing_pending():
    smud = _FakeSource("smud", lambda tx: "SMUD" in str(tx.get("description", "")).upper())
    registry = BillSourceRegistry([smud])
    client = _FakePayhoa(
        [
            {
                "id": 1,
                "amount": 50,
                "transactionDate": "2026-08-31",
                "description": "OTHER VENDOR",
                "approved": False,
                "attachments": [],
            }
        ]
    )
    synced: list[str] = []
    report = sync_bills(
        client,
        registry,
        sync_source=lambda name: synced.append(name),
    )
    assert report.pending == []
    assert report.sources_needed == []
    assert synced == []
    assert "no unreviewed" in report.skipped_reason
