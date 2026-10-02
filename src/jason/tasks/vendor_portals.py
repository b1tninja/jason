"""Sync a vendor's customer portal to disk: the account, its billing, its visits, its files, and its invoices.

For each ``VendorPortal`` in the specification, jason signs in with the Keeper record named by
its key, then for every property on the account (the master account first):

- ``account.json``: the customer, linked properties, plan, billing lines (tickets and payments),
  the service visits the history page lists (technician, times, notes, products applied), the
  documents and photos, the products applied by year (the chemical usage report), and the
  conditions report;
- ``invoices/<ticket>.pdf``: each ticket's invoice, checked before it is kept: the PDF must print
  that ticket's number and amount. A PDF that names another invoice goes to ``invoices/_mismatch``;
- ``files/<document>.<ext>``: each document and service photo (signed links, fetched right away);
- ``chemicals/<year>.pdf``: the product usage report as the portal exports it.

Under ``data/vendors/<key>/<customer id>/``. A second run downloads only what is missing (the
current year's report and anything new). Nothing is changed in the portal; jason never pays.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jason.fieldportals.client import FieldPortals, FieldPortalsError
from jason.fieldportals.models import (
    PortalAccount,
    PortalCustomer,
    PortalDocument,
    PortalProperty,
    PortalTransaction,
    ServiceVisit,
    Subscription,
    applications_from_html,
    table_rows,
)

VENDORS_DIR = "vendors"
ACCOUNT = "account.json"


def portal_root(data_dir: Path, key: str) -> Path:
    return Path(data_dir) / VENDORS_DIR / key


def read_portal_invoice(pdf: bytes) -> dict[str, Any]:
    """A FieldRoutes invoice's number, account, dates, and total, from its text."""
    from jason.community.invoice_formats import INVOICE_FORMATS
    from jason.community.invoices import read_invoice

    text = _pdf_text(pdf)
    invoice = read_invoice(text, formats=INVOICE_FORMATS)
    return {"number": invoice.number, "date": invoice.invoice_date, "total_cents": invoice.total_cents,
            "amounts": invoice.amounts, "method": invoice.method}


def _pdf_text(pdf: bytes) -> str:
    try:
        import pymupdf

        with pymupdf.open(stream=pdf, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc)
    except ImportError:
        from io import BytesIO

        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)


def invoice_matches(pdf: bytes, ticket: PortalTransaction) -> tuple[bool, str]:
    """The PDF prints this ticket's number and amount. Returns (matches, what it holds)."""
    read = read_portal_invoice(pdf)
    number = str(read["number"] or "")
    shows_amount = ticket.charge_cents in read["amounts"] or read["total_cents"] == ticket.charge_cents
    if number and number != ticket.ticket_id:
        return False, f"invoice {number}"
    if not number and not shows_amount:
        return False, "no invoice number and not the ticket's amount"
    if not shows_amount:
        return False, f"invoice {number} without the ticket's ${ticket.charge_cents / 100:,.2f}"
    return True, f"invoice {number}"


@dataclass
class PropertySync:
    customer_id: str
    name: str
    tickets: int = 0
    services: int = 0
    invoices_downloaded: int = 0
    invoices_present: int = 0
    invoice_mismatches: list[str] = field(default_factory=list)
    files_downloaded: int = 0
    files_present: int = 0
    files_failed: list[str] = field(default_factory=list)
    applications: int = 0
    conditions: int = 0


@dataclass
class PortalSyncResult:
    vendor: str
    properties: list[PropertySync] = field(default_factory=list)

    def summary(self) -> str:
        parts = []
        for p in self.properties:
            parts.append(
                f"{p.name} ({p.customer_id}): {p.tickets} tickets, {p.services} visits; invoices {p.invoices_downloaded} new, "
                f"{p.invoices_present} on disk, {len(p.invoice_mismatches)} refused; files {p.files_downloaded} new, "
                f"{p.files_present} on disk, {len(p.files_failed)} failed; {p.applications} product applications; "
                f"{p.conditions} conditions")
        return f"{self.vendor}: " + "; ".join(parts)


def collect(client: FieldPortals, vendor: str, subdomain: str, *, today: date) -> tuple[PortalAccount, str]:
    """The current property's account from the history and files pages and the reports. Returns (account, conditions html)."""
    history = client.customer("history")
    files = client.customer("files")
    customer = PortalCustomer.from_json(history)
    transactions = [PortalTransaction.from_json(t) for t in history.get("transactions") or []]
    days = [t.day for t in transactions if t.day]
    first = min(days) if days else today.replace(month=1, day=1)
    applications = []
    for year in range(first.year, today.year + 1):
        start, end = date(year, 1, 1), min(date(year, 12, 31), today)
        applications.extend(applications_from_html(client.chemical_usage_html(start, end)))
    conditions = client.conditions_html(first, today)
    account = PortalAccount(
        vendor=vendor,
        subdomain=subdomain,
        fetched=datetime.now(timezone.utc),
        customer=customer,
        properties=[PortalProperty.from_json(p) for p in history.get("properties") or []],
        subscriptions=[Subscription.from_json(s) for s in history.get("subscriptions") or []],
        transactions=transactions,
        services=[ServiceVisit.from_json(s) for s in history.get("services") or []],
        documents=[PortalDocument.from_json(d) for d in files.get("documents") or []],
        applications=applications,
    )
    return account, conditions


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def save_account(root: Path, account: PortalAccount, conditions_html: str) -> Path:
    folder = root / account.customer.customer_id
    folder.mkdir(parents=True, exist_ok=True)
    body = asdict(account)
    for doc in body["documents"]:
        # The signed link expires within hours; the file on disk is the record.
        doc["url"] = doc["url"].split("?", 1)[0]
    body["conditions"] = [row for row in table_rows(conditions_html) if row and row[0] != "No results found."]
    path = folder / ACCOUNT
    path.write_text(json.dumps(body, indent=1, default=_json_default), encoding="utf-8")
    (folder / "conditions.html").write_text(conditions_html, encoding="utf-8")
    return path


def sync_property(client: FieldPortals, vendor: str, subdomain: str, root: Path, *, today: date, full: bool = False,
                  log: Callable[[str], None] | None = None) -> PropertySync:
    account, conditions = collect(client, vendor, subdomain, today=today)
    folder = root / account.customer.customer_id
    result = PropertySync(account.customer.customer_id, account.customer.name, tickets=len(account.tickets),
                          services=len(account.services), applications=len(account.applications))
    save_account(root, account, conditions)
    result.conditions = len(json.loads((folder / ACCOUNT).read_text(encoding="utf-8"))["conditions"])

    # Files first: their links are signed and expire.
    files = folder / "files"
    for doc in account.documents:
        path = files / doc.filename
        if path.is_file() and not full:
            result.files_present += 1
            continue
        try:
            data = client.download(doc.url)
        except (FieldPortalsError, OSError) as exc:
            result.files_failed.append(f"{doc.document_id}: {exc}")
            continue
        files.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        result.files_downloaded += 1

    invoices = folder / "invoices"
    for ticket in account.tickets:
        if not ticket.ticket_id:
            continue
        path = invoices / f"{ticket.ticket_id}.pdf"
        if path.is_file() and not full:
            result.invoices_present += 1
            continue
        try:
            pdf = client.invoice_pdf(ticket.ticket_id)
        except FieldPortalsError as exc:
            result.invoice_mismatches.append(f"{ticket.ticket_id}: {exc}")
            continue
        ok, holds = invoice_matches(pdf, ticket)
        target = path if ok else invoices / "_mismatch" / f"{ticket.ticket_id}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pdf)
        if ok:
            result.invoices_downloaded += 1
        else:
            result.invoice_mismatches.append(f"{ticket.ticket_id} ({ticket.day}): the PDF holds {holds}")
        if log and result.invoices_downloaded and result.invoices_downloaded % 20 == 0:
            log(f"{account.customer.name}: {result.invoices_downloaded} invoices")

    chemicals = folder / "chemicals"
    years = sorted({a.day.year for a in account.applications if a.day})
    for year in years:
        path = chemicals / f"{year}.pdf"
        if path.is_file() and year < today.year and not full:
            continue
        start, end = date(year, 1, 1), min(date(year, 12, 31), today)
        client.chemical_usage_html(start, end)
        pdf = client.chemical_usage_pdf(start, end)
        if pdf:
            chemicals.mkdir(parents=True, exist_ok=True)
            path.write_bytes(pdf)
    return result


def sync_portal(client: FieldPortals, portal: Any, data_dir: Path, *, today: date | None = None, full: bool = False,
                log: Callable[[str], None] | None = None) -> PortalSyncResult:
    """Every property on the signed-in account, the master account first; the portal is left on the master account."""
    day = today or date.today()
    root = portal_root(data_dir, portal.key)
    result = PortalSyncResult(portal.vendor)
    home = client.customer("home")
    master = str(home.get("customerID") or "")
    properties = [PortalProperty.from_json(p) for p in home.get("properties") or []]
    order = [master] + [p.customer_id for p in properties if p.customer_id and p.customer_id != master]
    try:
        for customer_id in order:
            if customer_id != master:
                client.switch_property(customer_id)
            result.properties.append(sync_property(client, portal.vendor, portal.account, root, today=day, full=full, log=log))
    finally:
        if len(order) > 1:
            client.switch_property(master)
    return result


def load_accounts(data_dir: Path, key: str) -> list[dict[str, Any]]:
    """Each property's saved account snapshot for a portal."""
    root = portal_root(data_dir, key)
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(root.glob(f"*/{ACCOUNT}"))]




def portal_brief(data_dir: Path, portal: Any, *, visits: int = 5, today: date | None = None) -> dict[str, Any]:
    """What the portal says, from disk: each property's plan and balance, the latest visits, products this year, files."""
    day = today or date.today()
    root = portal_root(data_dir, portal.key)
    accounts = load_accounts(data_dir, portal.key)
    if not accounts:
        return {"found": False, "note": f"no {portal.key} portal data; run jason vendors --sync"}
    properties = []
    for account in accounts:
        folder = root / account["customer"]["customer_id"]
        products: dict[str, dict[str, Any]] = {}
        for app in account["applications"]:
            if app["day"] and app["day"][:4] == str(day.year):
                entry = products.setdefault(app["product"], {"product": app["product"], "epa": app["epa_number"], "applications": 0, "last": ""})
                entry["applications"] += 1
                entry["last"] = max(entry["last"], app["day"])
        properties.append({
            "customerId": account["customer"]["customer_id"],
            "name": account["customer"]["name"],
            "address": account["customer"]["address"],
            "balanceCents": account["customer"]["balance_cents"],
            "plan": [{"title": s["title"], "recurringCents": s["recurring_cents"], "sold": s["sold"], "next": s["schedule"][:3]}
                     for s in account["subscriptions"]],
            "tickets": sum(1 for t in account["transactions"] if t["kind"] == "ticket"),
            "billedThisYearCents": sum(t["charge_cents"] for t in account["transactions"] if t["kind"] == "ticket" and (t["day"] or "")[:4] == str(day.year)),
            "visits": [{"date": v["day"], "service": v["description"], "technician": v["technician"], "in": v["time_in"],
                        "out": v["time_out"], "notes": v["notes"][:300], "products": [p["name"] for p in v["products"]],
                        "ticket": v["ticket_id"], "totalCents": v["total_cents"]} for v in account["services"][:visits]],
            "productsThisYear": sorted(products.values(), key=lambda p: p["product"]),
            "photos": sum(1 for d in account["documents"] if d["kind"] == "photo"),
            "documents": sum(1 for d in account["documents"] if d["kind"] == "document"),
            "invoicesOnDisk": len(list((folder / "invoices").glob("*.pdf"))),
            "conditions": len(account.get("conditions") or []),
            "fetched": account["fetched"],
        })
    verification = None
    path = root / "verification.json"
    if path.is_file():
        body = json.loads(path.read_text(encoding="utf-8"))
        verification = {"verifiedAt": body.get("verifiedAt"), **body.get("summary", {})}
    return {"found": True, "vendor": portal.vendor, "service": portal.service, "budgetLine": portal.budget_line,
            "properties": properties, "verification": verification}


def brief_lines(brief: dict[str, Any]) -> list[str]:
    if not brief.get("found"):
        return [brief.get("note", "no portal data")]
    out = [f"{brief['vendor']} ({brief['service']}; budget line {brief['budgetLine']})"]
    for p in brief["properties"]:
        plan = "; ".join(f"{s['title']} ${s['recurringCents'] / 100:,.2f} since {s['sold']}, next {', '.join(s['next'])}" for s in p["plan"])
        out.append(f"{p['name']} ({p['customerId']}, {p['address']}): balance ${p['balanceCents'] / 100:,.2f}; {plan or 'no plan'}")
        out.append(f"  {p['tickets']} tickets (${p['billedThisYearCents'] / 100:,.2f} this year), {p['invoicesOnDisk']} invoices on disk, "
                   f"{p['photos']} photos, {p['documents']} documents, {p['conditions']} conditions; fetched {p['fetched'][:16]}")
        for v in p["visits"]:
            out.append(f"  {v['date']} {v['service']} by {v['technician']} {v['in']}-{v['out']}: {', '.join(v['products']) or 'no products'}")
        if p["productsThisYear"]:
            out.append("  products this year: " + "; ".join(f"{x['product']} (EPA {x['epa']}) x{x['applications']}, last {x['last']}" for x in p["productsThisYear"]))
    v = brief.get("verification")
    if v:
        out.append(f"Verified against PayHOA {v['verifiedAt'][:16]}: {v['payhoaPayments']} payments, {v['clean']} clean, "
                   f"{v['withFindings']} with findings, {v['portalPaymentsNotInPayhoa']} portal payments not in PayHOA")
    return out


__all__ = ["portal_root", "sync_portal", "sync_property", "collect", "save_account", "load_accounts", "portal_brief",
           "brief_lines", "invoice_matches", "read_portal_invoice", "PortalSyncResult", "PropertySync"]
