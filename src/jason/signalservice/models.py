"""The Signal Service customer portal as records: invoices, their lines, and work orders.

Each ``parse_*`` reads one page of the portal's server-rendered HTML (captured from
``portal.signalserviceinc.com.har``, October 3, 2026). Money is integer cents; days are dates.
The portal's payment-methods page is never read into a record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from html import unescape

from jason.fieldportals.models import cents, day

_TAG = re.compile(r"<[^>]+>")
_ROW = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.S | re.I)


def text(fragment: str) -> str:
    """A fragment's visible text, tags dropped and whitespace folded."""
    return re.sub(r"\s+", " ", unescape(_TAG.sub(" ", fragment))).strip()


def _rows(html: str) -> list[tuple[list[str], str]]:
    """Each body row of a page's tables: its cells' text, and the first link in the row."""
    found = []
    for row in _ROW.findall(html):
        cells = _CELL.findall(row)
        if not cells or "<th" in row.lower():
            continue
        link = re.search(r"""href=['"]([^'"]+)['"]""", row)
        found.append(([text(c) for c in cells], link.group(1) if link else ""))
    return found


@dataclass(frozen=True)
class InvoiceSummary:
    """A row of the invoice list."""

    number: str
    day: date | None
    paid: bool
    total_cents: int
    due_cents: int
    path: str


@dataclass(frozen=True)
class InvoiceLine:
    description: str
    site: str
    unit_cents: int
    quantity: str
    amount_cents: int


@dataclass(frozen=True)
class Invoice:
    number: str
    status: str
    day: date | None
    paid_day: date | None
    site: str
    remit_to: str
    lines: tuple[InvoiceLine, ...] = ()
    subtotal_cents: int = 0
    tax_cents: int = 0
    total_cents: int = 0
    applied_cents: int = 0
    due_cents: int = 0
    kind: str = ""
    pdf_path: str = ""
    intro: str = field(default="")


@dataclass(frozen=True)
class WorkOrder:
    number: str
    day: date | None
    manager: str
    summary: str
    site: str
    status: str


def list_pages(html: str) -> int:
    """How many pages the invoice list has (the pager's highest ``?page=N`` link; 1 without one)."""
    pages = [int(n) for n in re.findall(r"""\?page=(\d+)""", html)]
    return max(pages) if pages else 1


def parse_invoice_list(html: str) -> list[InvoiceSummary]:
    found = []
    for cells, link in _rows(html):
        if len(cells) < 5 or not link.startswith("/invoice/"):
            continue
        number, date_text, status, total, due = cells[:5]
        found.append(InvoiceSummary(number, day(date_text), status.upper() == "PAID", cents(total), cents(due), link))
    return found


def _label(html: str, name: str) -> str:
    """The value beside a ``Label:`` in the invoice header."""
    found = re.search(rf"{re.escape(name)}\s*</span>\s*<span[^>]*>(.*?)</span>\s*(?:</div>|<div)", html, re.S | re.I)
    return text(found.group(1)) if found else ""


def _total(html: str, name: str) -> int:
    found = re.search(rf"<span>\s*{re.escape(name)}\s*</span>\s*</div>\s*<div[^>]*>\s*<span>([^<]*)</span>", html, re.S | re.I)
    return cents(text(found.group(1))) if found else 0


def parse_invoice(html: str) -> Invoice:
    number = text(re.search(r"<h3[^>]*>(.*?)</h3>", html, re.S).group(1)) if re.search(r"<h3[^>]*>", html) else ""
    lines = []
    for cells, _ in _rows(html):
        if len(cells) == 5:
            lines.append(InvoiceLine(cells[0], cells[1], cents(cells[2]), cells[3], cents(cells[4])))
        elif len(cells) == 2 and "$" in cells[1]:
            # The older layout: "Basic Monitoring Service (...) (Qty: 3.00 @ $36.00 each)", amount.
            qty = re.search(r"Qty:\s*([\d.]+)\s*@\s*(\$[\d,.]+)", cells[0])
            lines.append(InvoiceLine(cells[0], "", cents(qty.group(2)) if qty else 0, qty.group(1) if qty else "", cents(cells[1])))
    heading = re.search(r"<h4[^>]*>\s*(Recurring|Items|Service|[A-Za-z ]+)\s*</h4>", html)
    intro = re.search(r"Type:\s*[^<]+", html)
    pdf = re.search(r"""href=['"](/invoice/[^'"]+/print/)['"]""", html)
    return Invoice(
        number=number,
        status=_label(html, "Status:"),
        day=day(_label(html, "Invoice Date:")),
        paid_day=day(_label(html, "Payment Date:")),
        site=_label(html, "Site:"),
        remit_to=_label(html, "Remit to:"),
        lines=tuple(lines),
        subtotal_cents=_total(html, "Subtotal"),
        tax_cents=_total(html, "Sales Tax"),
        total_cents=_total(html, "Total"),
        applied_cents=_total(html, "Payments Applied"),
        due_cents=_total(html, "Invoice Amount Due"),
        kind=text(heading.group(1)) if heading else "",
        pdf_path=pdf.group(1) if pdf else "",
        intro=text(intro.group(0)) if intro else "",
    )


def parse_work_orders(html: str) -> list[WorkOrder]:
    found = []
    for cells, _ in _rows(html):
        if len(cells) >= 6 and day(cells[1]):
            found.append(WorkOrder(cells[0], day(cells[1]), cells[2], cells[3], cells[4], cells[5]))
    return found


__all__ = ["Invoice", "InvoiceLine", "InvoiceSummary", "WorkOrder", "list_pages", "parse_invoice", "parse_invoice_list",
           "parse_work_orders", "text"]
