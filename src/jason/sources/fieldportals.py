"""A vendor portal as a bill source: a PayHOA payment to the vendor gets the invoice the portal says it paid.

The vendor's bank line ("ORIG CO NAME:Pro Active Pest") routes a PayHOA transaction here. The portal's
own payment record (same amount, within the window) names the tickets it paid; the invoice for that
ticket, downloaded and checked by ``jason.tasks.vendor_portals``, is the attachment. Only invoices
already on disk are offered; ``sync_source`` runs the portal sync first when a payment needs one.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from jason.fieldportals.models import day
from jason.sources.types import BillNeed, ResolvedBill, need_matches_bill
from jason.tasks.vendor_portals import load_accounts, portal_root


class VendorPortalBillSource:
    """One ``VendorPortal`` from the specification, read from ``data/vendors/<key>``."""

    def __init__(self, portal: Any, data_dir: Path) -> None:
        self.portal = portal
        self.data_dir = Path(data_dir)
        self.name = portal.key

    def matches_transaction(self, tx: dict[str, Any]) -> bool:
        text = str(tx.get("description") or "").upper()
        rule = str((tx.get("transactionRule") or {}).get("name") or "").upper() if isinstance(tx.get("transactionRule"), dict) else ""
        return any(word in text or word in rule for word in self.portal.payhoa_words)

    def _bills(self) -> list[ResolvedBill]:
        """One bill per portal payment: the payment's day and amount, and the invoice PDF of the ticket it paid."""
        found: list[ResolvedBill] = []
        root = portal_root(self.data_dir, self.portal.key)
        for account in load_accounts(self.data_dir, self.portal.key):
            customer_id = account["customer"]["customer_id"]
            for tx in account["transactions"]:
                if tx["kind"] != "payment" or not tx["invoice_ids"] or not tx["day"]:
                    continue
                ticket = tx["invoice_ids"][0]
                pdf = root / customer_id / "invoices" / f"{ticket}.pdf"
                found.append(ResolvedBill(
                    source=self.name,
                    bill_id=ticket,
                    account_number=customer_id,
                    bill_date=date.fromisoformat(tx["day"]),
                    amount_cents=tx["payment_cents"],
                    pdf_path=pdf if pdf.is_file() else None,
                ))
        return found

    def find_cached(self, need: BillNeed) -> list[ResolvedBill]:
        return [b for b in self._bills() if need_matches_bill(need, amount_cents=b.amount_cents, bill_date=b.bill_date)]

    def resolve(self, needs: list[BillNeed], *, ensure_pdfs: bool = True) -> dict[tuple[int, str, int], ResolvedBill]:
        """Each need gets the closest unused portal payment of its amount; a payment serves one need."""
        used: set[str] = set()
        out: dict[tuple[int, str, int], ResolvedBill] = {}
        bills = self._bills()
        for need in sorted(needs, key=lambda n: n.around):
            candidates = [b for b in bills if b.bill_id not in used and b.has_pdf
                          and need_matches_bill(need, amount_cents=b.amount_cents, bill_date=b.bill_date)]
            if not candidates:
                continue
            chosen = min(candidates, key=lambda b: abs((b.bill_date - need.around).days))
            used.add(chosen.bill_id)
            out[need.key] = chosen
        return out

    def ensure_pdf(self, bill: ResolvedBill) -> Path:
        if bill.pdf_path is None or not bill.pdf_path.is_file():
            raise LookupError(f"{self.name} invoice {bill.bill_id} is not on disk; run jason vendors --sync")
        return bill.pdf_path


__all__ = ["VendorPortalBillSource", "day"]
