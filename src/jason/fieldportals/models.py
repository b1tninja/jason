"""The FieldPortals account as records: the customer, its properties and plan, its billing, its visits, its files.

Each ``from_*`` reads the portal's own JSON (``data.customer`` of a page) or report HTML.
Money is integer cents; days are dates. Payment methods (the wallet's cards and bank
profiles) are never read into a record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any


def cents(value: Any) -> int:
    """"272.50", "-250.00", 272.5, "" as cents."""
    if value is None or value == "":
        return 0
    text = str(value).replace("$", "").replace(",", "").strip()
    negative = text.startswith("-")
    text = text.lstrip("-")
    whole, _, frac = text.partition(".")
    amount = int(whole or "0") * 100 + int((frac + "00")[:2])
    return -amount if negative else amount


def day(value: Any) -> date | None:
    """"09/17/26", "7/22/26 7:54am PDT", "2026-09-17", "2026-09-17 08:19:48" as a date."""
    if not value:
        return None
    text = str(value).strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
    if m:
        year = int(m[3])
        if year < 0 or year == 1:
            return None
        return date(year + 2000 if year < 100 else year, int(m[1]), int(m[2]))
    return None


@dataclass(frozen=True)
class PortalCustomer:
    customer_id: str
    customer_number: str
    name: str
    address: str
    city: str
    state: str
    zip: str
    status: str
    balance_cents: int
    email: str = ""
    phone: str = ""

    @classmethod
    def from_json(cls, c: dict[str, Any]) -> PortalCustomer:
        return cls(str(c.get("customerID") or ""), str(c.get("customerNumber") or ""),
                   str(c.get("name") or c.get("welcomeName") or "").strip(), str(c.get("address") or ""),
                   str(c.get("city") or ""), str(c.get("state") or ""), str(c.get("zip") or ""),
                   "active" if str(c.get("status")) == "1" else "inactive", cents(c.get("balance")),
                   str(c.get("email") or ""), str(c.get("phoneNumber") or ""))


@dataclass(frozen=True)
class PortalProperty:
    """A property on the account's master account; the portal switches between them."""

    customer_id: str
    customer_number: str
    name: str
    address: str
    city: str
    master_account: str
    commercial: bool
    balance_cents: int

    @classmethod
    def from_json(cls, p: dict[str, Any]) -> PortalProperty:
        name = str(p.get("companyName") or "").strip() or " ".join(x for x in (p.get("fname"), p.get("lname")) if x).strip()
        return cls(str(p.get("customerID") or ""), str(p.get("customerNumber") or ""), name, str(p.get("address") or ""),
                   str(p.get("city") or ""), str(p.get("masterAccount") or ""), str(p.get("commercialAccount")) == "1",
                   cents(p.get("balance")))


@dataclass(frozen=True)
class Subscription:
    subscription_id: str
    title: str
    initial_cents: int
    recurring_cents: int
    sold: date | None
    schedule: tuple[str, ...] = ()

    @classmethod
    def from_json(cls, s: dict[str, Any]) -> Subscription:
        schedule = tuple(str(x.get("date") if isinstance(x, dict) else x) for x in (s.get("serviceSchedule") or []))
        return cls(str(s.get("subscriptionID") or ""), str(s.get("title") or ""), cents(s.get("initialPrice")),
                   cents(s.get("recurringCharge")), day(s.get("soldDate")), schedule)


@dataclass(frozen=True)
class PortalTransaction:
    """A billing line: a ticket (an invoice) or a payment against tickets."""

    kind: str
    day: date | None
    description: str
    charge_cents: int
    payment_cents: int
    balance_cents: int
    # A ticket's transaction ID is its ticket (invoice) number; its label is the appointment.
    ticket_id: str = ""
    appointment_id: str = ""
    # A payment names the tickets it paid.
    invoice_ids: tuple[str, ...] = ()

    @classmethod
    def from_json(cls, t: dict[str, Any]) -> PortalTransaction:
        kind = str(t.get("type") or "")
        invoices = tuple(x for x in re.split(r"[,\s]+", str(t.get("invoiceIDs") or "")) if x)
        ticket = kind == "ticket"
        return cls(kind, day(t.get("date")), str(t.get("description") or ""), cents(t.get("charge")),
                   cents(t.get("payment")), cents(t.get("balanceAmt") or t.get("balance")),
                   str(t.get("transactionID") or "") if ticket else "", str(t.get("label") or "") if ticket else "", invoices)

    @property
    def amount_cents(self) -> int:
        return self.charge_cents if self.kind == "ticket" else self.payment_cents


@dataclass(frozen=True)
class ProductUse:
    """One product applied on a visit, as the technician recorded it."""

    name: str
    manufacturer: str
    epa_number: str
    active_ingredient: str
    amount: float
    unit: str
    concentrated_amount: float
    concentrated_unit: str
    dilution_percent: float
    method: str
    areas: str
    target_pests: str

    @classmethod
    def from_json(cls, p: dict[str, Any]) -> ProductUse:
        areas = p.get("treatedAreasNames") or {}
        pests = p.get("targetPestsNames") or []
        return cls(str(p.get("name") or ""), str(p.get("manufacturer") or ""), str(p.get("epaNumber") or ""),
                   str(p.get("label") or ""), float(p.get("amount") or 0), str(p.get("unit") or ""),
                   float(p.get("concentratedAmount") or 0), str(p.get("concentratedUnit") or ""),
                   float(p.get("dilution") or 0), str(p.get("applicationMethod") or ""),
                   str(areas.get("name") if isinstance(areas, dict) else areas or ""),
                   ", ".join(str(x.get("name")) for x in pests if isinstance(x, dict)))


@dataclass(frozen=True)
class ServiceVisit:
    """One appointment: when, who, what was done, what was applied, and its ticket."""

    appointment_id: str
    day: date | None
    description: str
    technician: str
    time_in: str
    time_out: str
    notes: str
    ticket_id: str
    total_cents: int
    balance_cents: int
    products: tuple[ProductUse, ...] = ()

    @classmethod
    def from_json(cls, s: dict[str, Any]) -> ServiceVisit:
        ticket = s.get("ticket") or {}
        tech = s.get("tech") or {}
        return cls(str(s.get("appointmentID") or ""), day(s.get("date")), str(s.get("description") or ""),
                   str(tech.get("name") or " ".join(x for x in (tech.get("fname"), tech.get("lname")) if x)),
                   str(s.get("timeIn") or ""), str(s.get("timeOut") or ""), unescape(str(s.get("serviceNotes") or "")).strip(),
                   str(ticket.get("ticketID") or ""), cents(ticket.get("total")), cents(ticket.get("balance")),
                   tuple(ProductUse.from_json(p) for p in (s.get("productsUsed") or [])))


@dataclass(frozen=True)
class PortalDocument:
    """A file on the account: a service photo or a document, with its (expiring) signed link."""

    document_id: str
    added: date | None
    description: str
    appointment_id: str
    kind: str
    extension: str
    url: str
    added_by: str
    service_type: str

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> PortalDocument:
        url = str(d.get("url") or "")
        extension = url.split("?", 1)[0].rsplit(".", 1)[-1].lower() if "." in url.split("?", 1)[0] else ""
        kind = "photo" if extension in ("jpg", "jpeg", "png", "gif", "tif", "tiff", "heic") else "document"
        appointment = str(d.get("appointmentID") or "")
        return cls(str(d.get("documentID") or ""), day(d.get("dateAddedWithoutTime") or d.get("dateAdded")),
                   unescape(str(d.get("description") or "")).strip(), "" if appointment == "0" else appointment,
                   kind, extension, url, str(d.get("addedByName") or ""), str(d.get("serviceType") or ""))

    @property
    def filename(self) -> str:
        return f"{self.document_id}.{self.extension or 'bin'}"


@dataclass(frozen=True)
class ProductApplication:
    """A row of the chemical usage report: one product applied on one day."""

    day: date | None
    product: str
    epa_number: str
    diluted: str
    concentrated: str
    dilution: str
    active: str
    targets: str
    areas: str


class _Table(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def table_rows(html: str) -> list[list[str]]:
    """The body rows of an HTML table (header cells outside a row are skipped)."""
    parser = _Table()
    parser.feed(html or "")
    return parser.rows


def applications_from_html(html: str) -> list[ProductApplication]:
    """The chemical usage report's rows: product, EPA number, amounts, dilution, targets, areas, date applied."""
    found = []
    for row in table_rows(html):
        if len(row) < 9 or row[0] == "Product":
            continue
        product, epa, diluted, concentrated, dilution, active, targets, areas, applied = row[:9]
        found.append(ProductApplication(day(applied), product, epa, diluted, concentrated, dilution, active, targets, areas))
    return found


@dataclass
class PortalAccount:
    """Everything the portal says about one property, as of ``fetched``."""

    vendor: str
    subdomain: str
    fetched: datetime
    customer: PortalCustomer
    properties: list[PortalProperty] = field(default_factory=list)
    subscriptions: list[Subscription] = field(default_factory=list)
    transactions: list[PortalTransaction] = field(default_factory=list)
    services: list[ServiceVisit] = field(default_factory=list)
    documents: list[PortalDocument] = field(default_factory=list)
    applications: list[ProductApplication] = field(default_factory=list)

    @property
    def tickets(self) -> list[PortalTransaction]:
        return [t for t in self.transactions if t.kind == "ticket"]

    @property
    def payments(self) -> list[PortalTransaction]:
        return [t for t in self.transactions if t.kind == "payment"]


__all__ = [
    "cents", "day", "PortalCustomer", "PortalProperty", "Subscription", "PortalTransaction", "ProductUse",
    "ServiceVisit", "PortalDocument", "ProductApplication", "PortalAccount", "applications_from_html", "table_rows",
]
