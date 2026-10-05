"""Cached City of Sacramento i-doxs bill metadata search and lazy PDF download."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from idoxs.db.repository import Repository
from idoxs.models import Bill
from idoxs.scrapers.bills import (
    BillNeedSpec,
    bill_filename,
    download_bill_pdf,
    resolve_bill_needs,
)


@dataclass(frozen=True)
class IdoxsBillMatch:
    bill_id: str
    account_number: str
    bill_date: date
    amount_cents: int
    pdf_path: Path | None
    view_bill_token: str = field(default="", repr=False)   # the portal session's handle on the bill: never shown
    list_control: str = ""
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


def _row_to_bill_match(row: dict) -> IdoxsBillMatch:
    pdf_raw = row.get("pdf_path") or ""
    pdf_path = Path(pdf_raw) if pdf_raw else None
    if pdf_path is not None and not pdf_path.is_file():
        pdf_path = None
    return IdoxsBillMatch(
        bill_id=str(row["bill_id"]),
        account_number=str(row["account_number"]),
        bill_date=_parse_date(row["bill_date"]),
        amount_cents=int(row["amount_cents"]),
        pdf_path=pdf_path,
        view_bill_token=str(row.get("view_bill_token") or ""),
        list_control=str(row.get("list_control") or ""),
        pdf_url=str(row.get("pdf_url") or ""),
    )


def _dedupe_identity(bills: list[IdoxsBillMatch]) -> list[IdoxsBillMatch]:
    seen: set[tuple[str, date, int]] = set()
    out: list[IdoxsBillMatch] = []
    for b in bills:
        key = (b.account_number, b.bill_date, b.amount_cents)
        if key in seen:
            continue
        seen.add(key)
        out.append(b)
    return out


class IdoxsBillStore:
    """Read/search i-doxs bills from the local SQLite cache."""

    def __init__(self, db_path: str | Path, bills_dir: str | Path) -> None:
        self.db_path = Path(db_path)
        self.bills_dir = Path(bills_dir)
        self.bills_dir.mkdir(parents=True, exist_ok=True)
        self._repo = Repository(self.db_path)

    def close(self) -> None:
        self._repo.close()

    def __enter__(self) -> IdoxsBillStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def find_bills(
        self,
        amount_cents: int,
        *,
        around: date | str | datetime,
        window_days: int = 7,
    ) -> list[IdoxsBillMatch]:
        around_date = _parse_date(around)
        rows = self._repo.find_bills_by_amount_near_date(
            amount_cents,
            around=around_date.isoformat(),
            window_days=window_days,
        )
        return _dedupe_identity([_row_to_bill_match(r) for r in rows])

    def get_bill(self, bill_id: str) -> IdoxsBillMatch | None:
        row = self._repo.get_bill(bill_id)
        if row is None:
            return None
        return _row_to_bill_match(row)

    def _persist_resolved(self, bill: Bill) -> IdoxsBillMatch:
        self._repo.upsert_bill(bill)
        if bill.view_bill_token:
            self._repo.update_bill_token(
                bill.bill_id, view_bill_token=bill.view_bill_token
            )
        dest = self.bills_dir / bill.account_number / bill_filename(bill)
        if dest.is_file():
            import hashlib

            digest = hashlib.sha256(dest.read_bytes()).hexdigest()
            self._repo.update_bill_pdf(
                bill.bill_id, pdf_path=str(dest), pdf_sha256=digest
            )
        row = self._repo.get_bill(bill.bill_id)
        assert row is not None
        return _row_to_bill_match(row)

    def resolve_needs(
        self,
        client,
        needs: list[tuple[int, date, int]],
        *,
        ensure_pdfs: bool = True,
    ) -> list[IdoxsBillMatch]:
        """Resolve (amount_cents, around, window_days) needs in one portal session."""
        specs = [
            BillNeedSpec(
                amount_cents=amount,
                around=around,
                window_days=window_days,
            )
            for amount, around, window_days in needs
        ]
        # Prefer bills that already have tokens / PDFs — only portal-resolve the rest.
        pending: list[BillNeedSpec] = []
        already: list[IdoxsBillMatch] = []
        for spec in specs:
            cached = self.find_bills(
                spec.amount_cents,
                around=spec.around,
                window_days=spec.window_days,
            )
            ready = next(
                (b for b in cached if b.has_pdf or b.view_bill_token),
                None,
            )
            if ready is not None and (ready.has_pdf or not ensure_pdfs):
                already.append(ready)
            elif ready is not None and ready.view_bill_token and ensure_pdfs:
                path = self.ensure_bill_pdf(ready, client)
                already.append(
                    IdoxsBillMatch(
                        bill_id=ready.bill_id,
                        account_number=ready.account_number,
                        bill_date=ready.bill_date,
                        amount_cents=ready.amount_cents,
                        pdf_path=path,
                        view_bill_token=ready.view_bill_token,
                        list_control=ready.list_control,
                        pdf_url=ready.pdf_url,
                    )
                )
            else:
                pending.append(spec)

        live = resolve_bill_needs(
            client,
            pending,
            download_pdfs=ensure_pdfs,
            bills_dir=self.bills_dir if ensure_pdfs else None,
        )
        for bill in live:
            already.append(self._persist_resolved(bill))
        return already

    def ensure_bill_pdf(self, bill: IdoxsBillMatch, client) -> Path:
        """Return local PDF path, downloading via idoxs client if needed."""
        if bill.has_pdf and bill.pdf_path is not None:
            return bill.pdf_path

        row = self._repo.find_bill_by_identity(
            bill.account_number,
            bill.bill_date.isoformat(),
            bill.amount_cents,
        )
        if row is None:
            row = self._repo.get_bill(bill.bill_id)
        if row is None:
            # Targeted portal resolve for this single need
            matches = self.resolve_needs(
                client,
                [(bill.amount_cents, bill.bill_date, 7)],
                ensure_pdfs=True,
            )
            if not matches or not matches[0].has_pdf:
                raise LookupError(f"Bill {bill.bill_id} not in cache")
            assert matches[0].pdf_path is not None
            return matches[0].pdf_path

        token = bill.view_bill_token or str(row.get("view_bill_token") or "")
        bill_id = str(row["bill_id"])
        bill_model = Bill(
            bill_id=bill_id,
            account_number=bill.account_number,
            bill_date=bill.bill_date.isoformat(),
            due_date=str(row.get("due_date") or ""),
            amount_cents=bill.amount_cents,
            view_bill_token=token,
            list_control="",
            pdf_url=bill.pdf_url or str(row.get("pdf_url") or ""),
        )

        if not bill_model.view_bill_token:
            matches = self.resolve_needs(
                client,
                [(bill.amount_cents, bill.bill_date, 7)],
                ensure_pdfs=True,
            )
            if matches and matches[0].has_pdf and matches[0].pdf_path:
                return matches[0].pdf_path
            row = self._repo.find_bill_by_identity(
                bill.account_number,
                bill.bill_date.isoformat(),
                bill.amount_cents,
            )
            if row:
                bill_model = Bill(
                    bill_id=str(row["bill_id"]),
                    account_number=bill.account_number,
                    bill_date=bill.bill_date.isoformat(),
                    due_date=str(row.get("due_date") or ""),
                    amount_cents=bill.amount_cents,
                    view_bill_token=str(row.get("view_bill_token") or ""),
                    list_control="",
                    pdf_url=str(row.get("pdf_url") or ""),
                )

        dest = self.bills_dir / bill.account_number / bill_filename(bill_model)
        path, digest = download_bill_pdf(client, bill_model, dest)
        self._repo.update_bill_pdf(bill_id, pdf_path=str(path), pdf_sha256=digest)
        if bill_model.view_bill_token:
            self._repo.update_bill_token(
                bill_id, view_bill_token=bill_model.view_bill_token
            )
        return path
