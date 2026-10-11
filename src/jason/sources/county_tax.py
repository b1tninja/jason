"""The county tax collector as a bill source: a PayHOA payment to the collector gets the tax bill its receipt paid.

A property tax bill has no date a bank payment lines up with (a taxpayer pays any day up to the delinquency date), so the
bill is found through the county's own **receipt** for the payment (``jason county-tax --import-receipts``), which has the
amount, the day it posted, and the bills it paid. The chain is strict, and each link must be unique:

1. the payment is the collector's (the profile's payee row says ``county-tax``; ``jason.community.payees``);
2. one imported receipt has the payment's amount (its total, or the total plus the fee), posted within the window of the
   payment's day, and was paid from one of the association's accounts when the payment or the profile says which;
3. the receipt names **one** bill the tax catalog holds (the parcel, and the bill's number or its tax year; a parcel with a
   single bill row is not enough);
4. that bill's PDF is on disk (``jason sync-tax``, or ``jason county-tax --import-bill``).

Anything short of that is no match, and the investigation (``jason.tasks.bill_investigation``) says what is missing. A receipt
that paid several bills would need one PDF of all of them; it is no match here and a person decides. Nothing here calls the
county's site: it reads the receipts and the catalog a person imported, and attaches nothing by itself (the attach engine does,
with ``--yes``).
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.payees import PayeeClass, payee_of
from jason.sources.types import BillNeed, ResolvedBill

NAME = "county-tax"


class CountyTaxBillSource:
    name = NAME

    def __init__(self, data_dir: Path | str, community: Any) -> None:
        self.data_dir = Path(data_dir)
        self._community = community

    # --- routing ------------------------------------------------------------------------------------------------------

    def matches_transaction(self, tx: dict[str, Any]) -> bool:
        try:
            return payee_of(tx, tuple(self._community.payee_rules())) is PayeeClass.COUNTY_TAX
        except Exception:  # noqa: BLE001 - a profile with no payee rows owns nothing
            return False

    # --- the stores -----------------------------------------------------------------------------------------------------

    def _bills(self) -> list[dict[str, Any]]:
        path = self.data_dir / "tax.db"
        if not path.is_file():
            return []
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute("SELECT apn, number, year, pdf_path FROM bills")]
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    def _own_fours(self) -> set[str]:
        try:
            return {str(a.suffix)[-4:] for a in self._community.bank_accounts() if getattr(a, "suffix", "")}
        except Exception:  # noqa: BLE001
            return set()

    @staticmethod
    def _bill_of(item: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any] | None:
        """The one catalog bill a paid item names: the parcel's digits and the bill's number, else its tax year."""
        from jason.tasks.tax_receipts import digits

        mine = [r for r in rows if digits(item.get("apn")) and digits(r["apn"]) == digits(item.get("apn"))]
        for narrowed in ([r for r in mine if item.get("bill") and r["number"] == item["bill"]],
                         [r for r in mine if item.get("year") and r["year"] == item["year"]]):
            if len(narrowed) == 1:
                return narrowed[0]
        return None

    def _receipts_for(self, need: BillNeed) -> list[dict[str, Any]]:
        from jason.tasks import tax_receipts as tr

        own = self._own_fours()
        out = []
        for r in tr.load(self.data_dir):
            total, fee = int(r.get("totalCents") or 0), int(r.get("feeCents") or 0)
            if total <= 0 or need.amount_cents not in (total, total + fee):
                continue
            posted = tr.posted_day(r)
            if posted is None or abs((posted - need.around).days) > need.window_days:
                continue
            four = str(r.get("tenderLast4") or "")
            if own and four and four not in own:
                continue                      # paid from an account that is not the association's
            out.append(r)
        return out

    # --- the BillSource protocol -----------------------------------------------------------------------------------------

    def find_cached(self, need: BillNeed) -> list[ResolvedBill]:
        rows = self._bills()
        found: list[ResolvedBill] = []
        for receipt in self._receipts_for(need):
            bills = {}
            for item in receipt.get("items") or []:
                bill = self._bill_of(item, rows)
                if bill is None:
                    bills = {}
                    break                       # an item the catalog cannot name: no unique bill
                bills[(bill["apn"], bill["number"])] = bill
            if len(bills) != 1:
                continue                        # several bills need one PDF of all of them: a person decides
            bill = next(iter(bills.values()))
            pdf = (self.data_dir / bill["pdf_path"]) if bill["pdf_path"] else None
            from jason.tasks import tax_receipts as tr

            posted: date = tr.posted_day(receipt) or need.around
            found.append(ResolvedBill(
                source=NAME, bill_id=f"{bill['number']} (receipt {receipt['confirmation']})", account_number=str(bill["apn"]),
                bill_date=posted, amount_cents=need.amount_cents,
                pdf_path=pdf if pdf and pdf.is_file() else None))
        return found

    def resolve(self, needs: list[BillNeed], *, ensure_pdfs: bool = True) -> dict[tuple[int, str, int], ResolvedBill]:
        """Each need gets its unique bill with a PDF on disk; a need with none, or two, gets nothing."""
        out: dict[tuple[int, str, int], ResolvedBill] = {}
        used: set[tuple] = set()
        for need in needs:
            fits = [b for b in self.find_cached(need) if b.has_pdf and b.identity not in used]
            if len({b.identity for b in fits}) == 1:
                used.add(fits[0].identity)
                out[need.key] = fits[0]
        return out

    def ensure_pdf(self, bill: ResolvedBill) -> Path:
        if bill.pdf_path is None or not bill.pdf_path.is_file():
            raise LookupError("the tax bill's PDF is not on disk; `jason sync-tax` reads it, or `jason county-tax --import-bill` "
                              "keeps one a person downloaded")
        return bill.pdf_path


__all__ = ["CountyTaxBillSource", "NAME"]
