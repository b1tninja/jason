"""Sacramento County secured property tax bills, as the printed PDFs the library holds.

The county's bill pages (HTML) are read by ``jason.community.tax.parse_bill`` into ``TaxBill`` rows, and ``jason sync-tax``
stores them in ``data/tax.db``. The library keeps the printed bills instead: the common-area parcels' annual bills and the
"Delinquent Tax Bills" files that gather several years of one parcel. ``SacramentoTaxBillModel`` reads those PDFs into the
same ``TaxBill`` rows (with ``TaxLevy`` lines), so the existing helpers apply (``direct_levies``, ``tax_split``), and checks
each bill against the specification's parcels and the stored bill of the same number.

Two layouts: the internet copy with "AMOUNT TO PAY BOTH INSTALLMENTS" (2022 on), and the older bill with "FOR FISCAL YEAR
BEGINNING JULY 1" (2017 to 2021). A bill's number prints as eight digits ("23407325"); the county's bill pages number the
same bill "20230407325".

No Civil Code section governs a tax bill; the findings are leads for the treasurer.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jason.community.document_models import DocumentModel, Finding, ModelContext, Severity, register, squash
from jason.community.models.financial_common import dollars
from jason.community.reviews import RECORDS
from jason.community.tax import DirectLevy, TaxBill, TaxLevy, direct_levies, parcel_number
from jason.community.symbols import DocumentKind

TAX_DB = "tax.db"


@dataclass
class TaxBillDocument:
    apn: str = ""
    layout: str = ""
    delinquent_file: bool = False               # "Delinquent Tax Bills for ..."
    bills: tuple[TaxBill, ...] = ()             # oldest first
    printed_numbers: tuple[str, ...] = ()       # the eight-digit numbers as printed, in the order of ``bills``
    prior_delinquent: tuple[str, ...] = ()      # "2010-11": the years a bill says are delinquent
    levy_series: tuple[DirectLevy, ...] = field(default_factory=tuple)
    common_area: bool | None = None             # per the specification


_APN = re.compile(r"\b(\d{3}-\d{4}-\d{3}-\d{4})\b")
_DIRECT = re.compile(r"\b(0\d{3}) ((?:[A-Z0-9#&/.,'-]+ ){1,10}?)(\d{3}-\d{3}-\d{4}) ([\d,]*\.\d\d)\b")
_RATE = re.compile(r"\b(COUNTY WIDE 1%|(?:[A-Z]+ ){1,5}GOB)(?: 1)? (\d?\.\d{5})\b")


def stored_number(printed: str) -> str:
    """"23407325" -> "20230407325", the number the county's bill pages use."""
    return f"20{printed[:2]}0{printed[2:]}" if re.fullmatch(r"\d{8}", printed or "") else printed


def _bill(chunk: str) -> tuple[TaxBill, str, tuple[str, ...]] | None:
    apn = _APN.search(chunk)
    number = re.search(r"\d{3}-\d{4}-\d{3}-\d{4}\s*\n\s*(\d{8})\b", chunk)
    if not apn or not number:
        return None
    flat = squash(chunk)
    years = [int(a) for a, b in re.findall(r"\b(20\d\d)-(20\d\d)\b", flat) if int(b) == int(a) + 1]
    year = years[0] if years else None
    tra = re.search(r"^\s*(0\d{4})\s*$", chunk, re.M)
    levies = [TaxLevy("direct", squash(m.group(2)), int(m.group(4).replace(",", "").replace(".", "")), code=m.group(1))
              for m in _DIRECT.finditer(flat)]
    rates = [TaxLevy("ad_valorem", m.group(1).strip(), 0, rate_e8=round(float(m.group(2)) * 100_000_000)) for m in _RATE.finditer(flat)]
    total = None
    if "AMOUNT TO PAY BOTH INSTALLMENTS" in chunk:
        paid = re.findall(r"(20\d\d)\s*\n\s*\$\s*\n\s*([\d,]*\.\d\d)", chunk)
        total = int(paid[-1][1].replace(",", "").replace(".", "")) if paid else None
    else:
        first = re.search(r"\$\s*\n\s*([\d,]*\.\d\d)", chunk)
        total = int(first.group(1).replace(",", "").replace(".", "")) if first else None
    direct = sum(levy.amount_cents for levy in levies) if levies else None
    rate = sum(levy.rate_e8 or 0 for levy in rates) or None
    delinquent = tuple(dict.fromkeys(m.group(1) for m in re.finditer(r"(\d{4}-\d\d) PRIOR YEAR TAXES ARE DELINQUENT", flat)))
    name = f"{year} Secured Annual Bill #{stored_number(number.group(1))}" if year else ""
    bill = TaxBill(number=stored_number(number.group(1)), name=name, year=year, tax_rate_area=tra.group(1) if tra else "", rate_e8=rate,
                   direct_cents=direct, total_cents=total, levies=tuple(levies + rates))
    return bill, number.group(1), delinquent


def county_figures(d, records) -> dict[str, Any] | None:
    """From the stored tax catalog (``jason sync-tax``): for each of the document's bills, by number, the tax office's
    direct levies, total, and balance for the same parcel and bill, or None when the catalog lacks the bill. None when
    there is no catalog on disk, the document has no bills, or the catalog cannot be read."""
    if records.data_dir is None:
        return None
    path = Path(records.data_dir) / TAX_DB
    if not path.is_file() or not d.bills:
        return None
    out: dict[str, Any] = {}
    try:
        with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            for bill in d.bills:
                row = conn.execute("SELECT direct_cents, total_cents, balance_cents FROM bills WHERE apn = ? AND number = ?",
                                   (d.apn, bill.number)).fetchone()
                out[str(bill.number)] = None if row is None else {k: row[k] for k in ("direct_cents", "total_cents", "balance_cents")}
    except sqlite3.Error:
        return None
    return out


@RECORDS.check("bills-per-county", TaxBillDocument, fields=("apn", "bills"), facts=county_figures, dated=False)
def bills_per_county(d, _as_of, county: dict[str, Any] | None) -> list[Finding]:
    """Each bill against the tax office's figures ``jason sync-tax`` stored for the same bill number."""
    if county is None:
        return []
    found: list[Finding] = []
    for bill in d.bills:
        row = county[str(bill.number)]
        if row is None:
            found.append(Finding("not-in-tax-store", f"the {bill.year} bill {bill.number} is not in the stored tax catalog; run "
                                 "jason sync-tax", Severity.INFO))
            continue
        if row["direct_cents"] is not None and bill.direct_cents is not None and row["direct_cents"] != bill.direct_cents:
            found.append(Finding("direct-differs-from-county", f"the {bill.year} bill's direct levies are {dollars(bill.direct_cents)}; "
                                 f"the county's bill page says {dollars(row['direct_cents'])}", Severity.CHECK))
        if row["balance_cents"] is not None:
            if row["balance_cents"] > 0:
                found.append(Finding("unpaid-per-county", f"the county shows {dollars(row['balance_cents'])} still due on the "
                                     f"{bill.year} bill", Severity.CHECK))
            else:
                found.append(Finding("paid-per-county", f"the county shows the {bill.year} bill paid", Severity.INFO))
    return found


class SacramentoTaxBillModel(DocumentModel):
    kind = DocumentKind.TAX_BILL
    name = "sacramento-secured-bill"
    required = ("apn", "bills")
    lens_checks = (bills_per_county,)

    def parse(self, text: str, context: ModelContext) -> TaxBillDocument | None:
        text = text or ""
        if "SECURED PROPERTY TAX BILL" not in text or not _APN.search(text):
            return None
        d = TaxBillDocument()
        d.apn = _APN.search(text).group(1)
        d.layout = "internet copy (2022 on)" if "AMOUNT TO PAY BOTH INSTALLMENTS" in text else "annual bill (2017 to 2021)"
        d.delinquent_file = bool(re.search(r"delinquent tax bills", context.name or "", re.I))
        read: dict[str, tuple[TaxBill, str]] = {}
        delinquent: list[str] = []
        for chunk in re.split(r"INTERNET COPY", text):
            found = _bill(chunk)
            if not found:
                continue
            bill, printed, late = found
            read.setdefault(bill.number, (bill, printed))
            delinquent += late
        ordered = sorted(read.values(), key=lambda pair: (pair[0].year or 0, pair[0].number))
        d.bills = tuple(b for b, _ in ordered)
        d.printed_numbers = tuple(p for _, p in ordered)
        d.prior_delinquent = tuple(dict.fromkeys(delinquent))
        d.levy_series = direct_levies(d.bills)
        commons = getattr(context.community, "common_areas", None)
        try:
            common = {parcel_number(p) for p in (commons() if callable(commons) else commons or ())}
            d.common_area = d.apn in common if common else None
        except Exception:
            d.common_area = None
        return d

    def check(self, d: TaxBillDocument, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        parcels = getattr(context.community, "parcels", None)
        try:
            known = {parcel_number(p) for p in (parcels() if callable(parcels) else parcels or ())}
        except Exception:
            known = set()
        if known and d.apn not in known:
            found.append(Finding("unknown-parcel", f"parcel {d.apn} is not one of the association's parcels in the specification",
                                 Severity.CHECK))
        elif d.common_area is False:
            found.append(Finding("unit-parcel", f"parcel {d.apn} is a unit; its tax bill is the owner's, not the association's", Severity.INFO))
        for years in d.prior_delinquent:
            found.append(Finding("prior-year-delinquent", f"the bill states the {years} taxes on parcel {d.apn} are delinquent",
                                 Severity.PROBLEM))
        for bill in d.bills:
            ad_valorem = [levy for levy in bill.levies if levy.kind == "ad_valorem"]
            if bill.total_cents is not None and bill.direct_cents is not None and not ad_valorem and bill.total_cents != bill.direct_cents:
                found.append(Finding("total-not-direct", f"the {bill.year} bill totals {dollars(bill.total_cents)}; its direct levies add to "
                                     f"{dollars(bill.direct_cents)}", Severity.CHECK))
        for series in d.levy_series:
            if len({cents for _, cents in series.amounts}) > 1:
                amounts = ", ".join(f"{year} {dollars(cents)}" for year, cents in series.amounts)
                found.append(Finding("levy-changed", f"direct levy {series.code} {series.name}: {amounts}", Severity.INFO))
        found.append(bills_per_county)   # the records lens's place: the tax office's stored figures for each bill
        return found


register(SacramentoTaxBillModel())

__all__ = ["TaxBillDocument", "SacramentoTaxBillModel", "stored_number"]
