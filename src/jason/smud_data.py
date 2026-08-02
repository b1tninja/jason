"""Cached SMUD bill metadata search and lazy PDF download."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from smud.db.repository import Repository
from smud.models import Bill
from smud.scrapers.billing import bill_filename, download_bill_pdf


@dataclass(frozen=True)
class BillMatch:
    bill_id: str
    account_number: str
    bill_date: date
    amount_cents: int
    pdf_path: Path | None
    pdf_url: str = ""

    @property
    def has_pdf(self) -> bool:
        return self.pdf_path is not None and self.pdf_path.is_file()


def _parse_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    elif " " in text:
        text = text.split(" ", 1)[0]
    return date.fromisoformat(text[:10])


def _row_to_bill_match(row: dict) -> BillMatch:
    pdf_raw = row.get("pdf_path") or ""
    pdf_path = Path(pdf_raw) if pdf_raw else None
    if pdf_path is not None and not pdf_path.is_file():
        pdf_path = None
    return BillMatch(
        bill_id=str(row["bill_id"]),
        account_number=str(row["account_number"]),
        bill_date=_parse_date(row["bill_date"]),
        amount_cents=int(row["amount_cents"]),
        pdf_path=pdf_path,
        pdf_url=str(row.get("pdf_url") or ""),
    )


class SmudBillStore:
    """Read/search SMUD bills from the local SQLite cache."""

    def __init__(self, db_path: str | Path, bills_dir: str | Path) -> None:
        self.db_path = Path(db_path)
        self.bills_dir = Path(bills_dir)
        self.bills_dir.mkdir(parents=True, exist_ok=True)
        self._repo = Repository(self.db_path)

    def close(self) -> None:
        self._repo.close()

    def __enter__(self) -> SmudBillStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def find_bills(
        self,
        amount_cents: int,
        *,
        around: date | str | datetime,
        window_days: int = 7,
    ) -> list[BillMatch]:
        around_date = _parse_date(around)
        rows = self._repo.find_bills_by_amount_near_date(
            amount_cents,
            around=around_date.isoformat(),
            window_days=window_days,
        )
        return [_row_to_bill_match(r) for r in rows]

    def get_bill(self, bill_id: str) -> BillMatch | None:
        row = self._repo.get_bill(bill_id)
        if row is None:
            return None
        return _row_to_bill_match(row)

    def resolve_needs(
        self,
        client,
        bills: list[BillMatch],
        *,
        ensure_pdfs: bool = True,
    ) -> list[BillMatch]:
        """Refresh PDFs for cached bills, one live scrape per account."""
        if not ensure_pdfs:
            return list(bills)

        from smud.scrapers.billing import scrape_bills

        by_account: dict[str, list[BillMatch]] = {}
        for bill in bills:
            by_account.setdefault(bill.account_number, []).append(bill)

        out: list[BillMatch] = []
        for account, account_bills in by_account.items():
            if all(b.has_pdf for b in account_bills):
                out.extend(account_bills)
                continue
            client.select_account(account)
            live_bills = scrape_bills(client, account)
            for bill in account_bills:
                if bill.has_pdf and bill.pdf_path is not None:
                    out.append(bill)
                    continue
                live = next(
                    (b for b in live_bills if b.bill_id == bill.bill_id),
                    None,
                )
                if live is None:
                    live = next(
                        (
                            b
                            for b in live_bills
                            if b.amount_cents == bill.amount_cents
                            and b.bill_date == bill.bill_date.isoformat()
                        ),
                        None,
                    )
                if live is not None:
                    self._repo.upsert_bill(live)
                    bill_model = live
                else:
                    row = self._repo.get_bill(bill.bill_id)
                    pdf_url = bill.pdf_url or (row or {}).get("pdf_url") or ""
                    if not pdf_url:
                        raise ValueError(
                            f"Bill {bill.bill_id} not on live billing page "
                            "and has no pdf_url"
                        )
                    bill_model = Bill(
                        bill_id=bill.bill_id,
                        account_number=bill.account_number,
                        bill_date=bill.bill_date.isoformat(),
                        due_date=str((row or {}).get("due_date") or ""),
                        amount_cents=bill.amount_cents,
                        period_start=str((row or {}).get("period_start") or ""),
                        period_end=str((row or {}).get("period_end") or ""),
                        pdf_url=pdf_url,
                    )
                if not bill_model.pdf_url:
                    raise ValueError(
                        f"Bill {bill.bill_id} has no pdf_url after refresh"
                    )
                dest = (
                    self.bills_dir / bill.account_number / bill_filename(bill_model)
                )
                path, digest = download_bill_pdf(client, bill_model, dest)
                self._repo.update_bill_pdf(
                    bill.bill_id, pdf_path=str(path), pdf_sha256=digest
                )
                out.append(
                    BillMatch(
                        bill_id=bill.bill_id,
                        account_number=bill.account_number,
                        bill_date=bill.bill_date,
                        amount_cents=bill.amount_cents,
                        pdf_path=path,
                        pdf_url=bill_model.pdf_url,
                    )
                )
        return out

    def ensure_bill_pdf(self, bill: BillMatch, client) -> Path:
        """Return local PDF path, downloading via SMUD client if needed."""
        if bill.has_pdf and bill.pdf_path is not None:
            return bill.pdf_path
        resolved = self.resolve_needs(client, [bill], ensure_pdfs=True)
        if not resolved or not resolved[0].has_pdf or resolved[0].pdf_path is None:
            raise LookupError(f"Bill {bill.bill_id} not in cache")
        return resolved[0].pdf_path
