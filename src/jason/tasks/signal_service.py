"""Sync Signal Service's customer portal to disk: its invoices, their lines, its work orders, and each invoice's PDF.

Under ``data/vendors/<key>/``:

- ``account.json``: every invoice (status, dates, site, lines, totals, what is due), the work orders,
  and which of the portal's other pages (proposals, recurring billing, files, eSign) held anything;
- ``invoices/<number>.pdf``: each invoice as the portal prints it, checked before it is kept: the PDF
  must print that invoice's number or total. One that does neither goes to ``invoices/_mismatch``.

A second run reads only invoices not yet on disk, plus any still unpaid. Nothing is changed in the
portal: jason never pays, and never opens the payment-methods or password pages.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jason.signalservice.client import PAGES, SignalService, SignalServiceError, empty_page
from jason.signalservice.models import Invoice
from jason.tasks.vendor_portals import _json_default, _pdf_text, portal_root

ACCOUNT = "account.json"


@dataclass
class SignalSyncResult:
    vendor: str
    invoices: int = 0
    invoices_read: int = 0
    pdfs_downloaded: int = 0
    pdfs_present: int = 0
    mismatches: list[str] = field(default_factory=list)
    work_orders: int = 0
    pages_with_content: list[str] = field(default_factory=list)

    def summary(self) -> str:
        extra = f"; also on: {', '.join(self.pages_with_content)}" if self.pages_with_content else ""
        return (f"{self.vendor}: {self.invoices} invoices ({self.invoices_read} read now), PDFs {self.pdfs_downloaded} new, "
                f"{self.pdfs_present} on disk, {len(self.mismatches)} refused; {self.work_orders} work orders{extra}")


def pdf_matches(pdf: bytes, invoice: Invoice) -> bool:
    """The PDF prints this invoice's number or its total."""
    body = _pdf_text(pdf)
    total = f"{invoice.total_cents / 100:,.2f}"
    return invoice.number in body or total in body


def load_account(data_dir: Path, key: str) -> dict[str, Any]:
    path = portal_root(data_dir, key) / ACCOUNT
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def sync_signal(client: SignalService, portal: Any, data_dir: Path, *, full: bool = False,
                log: Callable[[str], None] | None = None) -> SignalSyncResult:
    root = portal_root(data_dir, portal.key)
    (root / "invoices").mkdir(parents=True, exist_ok=True)
    result = SignalSyncResult(portal.vendor)
    known = {i["number"]: i for i in load_account(data_dir, portal.key).get("invoices", [])}
    details: list[Invoice] = []
    for row in client.invoices():
        previous = known.get(row.number)
        if previous and not full and previous["status"].upper() == "PAID" and row.paid:
            details.append(_from_json(previous))
            continue
        details.append(client.invoice(row.number))
        result.invoices_read += 1
    result.invoices = len(details)

    for invoice in details:
        path = root / "invoices" / f"{invoice.number}.pdf"
        if path.is_file() and not full:
            result.pdfs_present += 1
            continue
        try:
            pdf = client.invoice_pdf(invoice.number)
        except SignalServiceError as exc:
            result.mismatches.append(f"{invoice.number}: {exc}")
            continue
        ok = pdf_matches(pdf, invoice)
        target = path if ok else root / "invoices" / "_mismatch" / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pdf)
        if ok:
            result.pdfs_downloaded += 1
        else:
            result.mismatches.append(f"{invoice.number} ({invoice.day}): the PDF prints neither the number nor ${invoice.total_cents / 100:,.2f}")
        if log and result.pdfs_downloaded and result.pdfs_downloaded % 20 == 0:
            log(f"{portal.vendor}: {result.pdfs_downloaded} invoices")

    orders = client.work_orders()
    result.work_orders = len(orders)
    result.pages_with_content = [name for name in PAGES if not empty_page(client.page_html(name))]
    body = {
        "vendor": portal.vendor,
        "account": portal.account,
        "fetched": datetime.now(timezone.utc),
        "invoices": [asdict(i) for i in details],
        "work_orders": [asdict(o) for o in orders],
        "pages_with_content": result.pages_with_content,
    }
    (root / ACCOUNT).write_text(json.dumps(body, indent=1, default=_json_default), encoding="utf-8")
    return result


def _from_json(body: dict[str, Any]) -> Invoice:
    from jason.fieldportals.models import day
    from jason.signalservice.models import InvoiceLine

    return Invoice(**{**body, "day": day(body.get("day")), "paid_day": day(body.get("paid_day")),
                      "lines": tuple(InvoiceLine(**line) for line in body.get("lines", []))})


def signal_brief(data_dir: Path, portal: Any, *, today: date | None = None) -> dict[str, Any]:
    """What the portal says, from disk: balance, the last invoices, this year's billing, the latest work orders."""
    account = load_account(data_dir, portal.key)
    if not account:
        return {"found": False, "note": f"no {portal.key} portal data; run jason vendors --sync"}
    year = str((today or date.today()).year)
    invoices = sorted(account["invoices"], key=lambda i: i["day"] or "", reverse=True)
    return {
        "found": True,
        "vendor": portal.vendor,
        "service": portal.service,
        "budgetLine": portal.budget_line,
        "dueCents": sum(i["due_cents"] for i in invoices),
        "billedThisYearCents": sum(i["total_cents"] for i in invoices if (i["day"] or "")[:4] == year),
        "invoices": [{"number": i["number"], "date": i["day"], "status": i["status"], "totalCents": i["total_cents"],
                      "site": i["site"].split("(")[0].strip(), "lines": [x["description"] for x in i["lines"]]}
                     for i in invoices[:6]],
        "workOrders": sorted(account["work_orders"], key=lambda o: o["day"] or "", reverse=True)[:5],
        "pagesWithContent": account.get("pages_with_content", []),
        "fetched": account["fetched"],
    }


def signal_lines(brief: dict[str, Any]) -> list[str]:
    out = [f"{brief['vendor']} ({brief['service']}; budget line {brief['budgetLine']})",
           f"  due ${brief['dueCents'] / 100:,.2f}; billed this year ${brief['billedThisYearCents'] / 100:,.2f}; fetched {brief['fetched'][:16]}"]
    for i in brief["invoices"]:
        out.append(f"  {i['number']} {i['date']} {i['status']} ${i['totalCents'] / 100:,.2f} {i['site']}")
    for o in brief["workOrders"]:
        out.append(f"  {o['day']} {o['number']} {o['summary']} ({o['status']})")
    if brief["pagesWithContent"]:
        out.append("  also has: " + ", ".join(brief["pagesWithContent"]))
    return out


__all__ = ["sync_signal", "signal_brief", "signal_lines", "load_account", "pdf_matches", "SignalSyncResult"]
