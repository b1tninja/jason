"""Pull Sacramento County property tax for known parcels into the local catalog."""

from __future__ import annotations

from dataclasses import dataclass, field

from jason.community.tax import SacramentoCountyTax
from jason.community.tax_store import TaxStore


@dataclass
class TaxSyncResult:
    accounts_synced: int = 0
    bills_new: int = 0
    missed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [
            f"accounts={self.accounts_synced}",
            f"bills_new={self.bills_new}",
            f"missed={len(self.missed)}",
        ]
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        return ", ".join(parts)


def sync_tax(
    store: TaxStore,
    office: SacramentoCountyTax,
    parcels: tuple[str, ...] | list[str],
    *,
    fetch=None,
    payable_fetch=None,
    page_fetch=None,
    pdf_fetch=None,
    bills_dir=None,
) -> TaxSyncResult:
    """Look up each parcel and upsert the account, its bill values, levies, and PDFs.

    ``fetch``, ``payable_fetch``, ``page_fetch``, and ``pdf_fetch`` replace
    the office HTTP calls in tests. ``bills_dir`` is where print PDFs are
    written, one directory per parcel. A parcel the index does not know is a
    miss. A bill page that fails is an error, and the account from search is
    still saved. One parcel's error does not stop the rest.
    """
    result = TaxSyncResult()
    run_id = store.start_run()
    for apn in parcels:
        try:
            account = office.account(apn, fetch=fetch, payable_fetch=payable_fetch)
        except Exception as exc:
            result.errors.append(f"{apn}: {exc}")
            continue
        if account is None:
            result.missed.append(apn)
            continue
        try:
            account = office.statements(
                account,
                fetch=page_fetch,
                bills_dir=bills_dir,
                pdf_fetch=pdf_fetch,
            )
        except Exception as exc:
            result.errors.append(f"{apn}: {exc}")
        result.bills_new += store.upsert(account)
        result.accounts_synced += 1
    store.finish_run(
        run_id,
        accounts_synced=result.accounts_synced,
        bills_new=result.bills_new,
        missed=len(result.missed),
        errors=result.errors,
    )
    return result
