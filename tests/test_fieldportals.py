"""FieldPortals (ProActive): the portal session, its records, the invoice check, and the PayHOA verification."""

from __future__ import annotations

import base64
import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from jason.fieldportals.client import FieldPortals, FieldPortalsAuthError
from jason.fieldportals.models import (
    PortalDocument,
    PortalTransaction,
    ServiceVisit,
    Subscription,
    applications_from_html,
    cents,
    day,
)

LANDING = '<script>xhr.setRequestHeader("x-csrf-token", "tok123");</script>'
CUSTOMER = {
    "customerID": "47362", "customerNumber": "47362", "name": "Mystique Community", "address": "3000 Macon Dr",
    "city": "Sacramento", "state": "CA", "zip": "95835", "status": "1", "balance": "0.00",
    "transactions": [
        {"transactionID": "2001325", "label": "1168672", "date": "09/17/26", "type": "ticket", "description": "Bi Weekly Service",
         "charge": "272.50", "payment": "", "balanceAmt": "0.00", "invoiceIDs": ""},
        {"transactionID": "", "label": "4", "date": "09/17/26", "type": "payment", "description": "Payment for invoice: 2001325",
         "charge": "", "payment": "272.50", "balanceAmt": "0.00", "invoiceIDs": "2001325"},
    ],
    "subscriptions": [{"subscriptionID": 51702, "title": "Bi Weekly Service", "initialPrice": "150.00", "recurringCharge": "272.50",
                       "soldDate": "12/29/2022", "serviceSchedule": ["9/30/26", "10/14/26"]}],
    "properties": [{"customerID": "47362", "customerNumber": "47362", "companyName": "Mystique Community", "address": "3000 Macon Dr",
                    "city": "Sacramento", "masterAccount": "47362", "commercialAccount": "1", "balance": "0.00"}],
    "services": [{"appointmentID": 1168672, "date": "09/17/26", "description": "Bi Weekly Service", "timeIn": "7:54 am",
                  "timeOut": "8:19 am", "serviceNotes": "Treated the perimeter.", "tech": {"name": "Tech One"},
                  "ticket": {"ticketID": "2001325", "total": 272.5, "balance": "0.00"},
                  "productsUsed": [{"name": "ALPINE WSG", "manufacturer": "BASF", "epaNumber": "499-561-ZA", "label": "Dinotefuran 40%",
                                    "amount": 250, "unit": "ozs", "concentratedAmount": 7.087, "concentratedUnit": "grams",
                                    "dilution": 0.1, "applicationMethod": "BackPack Sprayer",
                                    "treatedAreasNames": {"name": "Exterior"}, "targetPestsNames": [{"name": "Ants, Spiders"}]}]}],
    "documents": [{"documentID": "1165192", "dateAddedWithoutTime": "07/22/26", "description": "checked rodent station",
                   "appointmentID": "1125467", "url": "https://s3.amazonaws.com/PestRoutes/p-1.jpg?X-Amz-Signature=abc",
                   "addedByName": "Pro Active North", "serviceType": "Bi Weekly Service"}],
}


def _portal(handler) -> FieldPortals:
    return FieldPortals("proactive", http=httpx.Client(transport=httpx.MockTransport(handler)))


def _page_json(customer: dict | None = None, logged_out: bool = False) -> httpx.Response:
    return httpx.Response(200, text=json.dumps({"data": {"customer": customer or CUSTOMER}, "loggedOut": logged_out, "templates": {}}),
                          headers={"content-type": "text/html"})


def test_login_reads_the_csrf_token_and_every_call_sends_it() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path == "/landing/index":
            return httpx.Response(200, text=LANDING)
        if path == "/resources/session/login":
            return httpx.Response(302, headers={"location": "/home"})
        if path == "/home":
            return httpx.Response(200, text=LANDING)
        if path == "/resources/delegates/buildDelegate":
            return _page_json()
        if path == "/resources/delegates/actionDelegate.php":
            return httpx.Response(200, text=json.dumps({"data": base64.b64encode(b"%PDF-1.4 x").decode()}))
        return httpx.Response(404)

    portal = _portal(handler)
    home = portal.login("user", "secret")
    assert home["data"]["customer"]["customerID"] == "47362"
    login = next(r for r in seen if r.url.path == "/resources/session/login")
    assert b"company=proactive" in login.content
    delegate = [r for r in seen if r.url.path.startswith("/resources/delegates/")]
    assert delegate and all(r.headers["x-csrf-token"] == "tok123" for r in delegate)
    assert portal.invoice_pdf("2001325").startswith(b"%PDF")


def test_a_refused_login_and_an_ended_session_raise() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/landing/index":
            return httpx.Response(200, text=LANDING)
        return httpx.Response(302, headers={"location": "/landing/index?error=1"})

    with pytest.raises(FieldPortalsAuthError):
        _portal(refuse).login("user", "wrong")

    ended = _portal(lambda request: _page_json(logged_out=True))
    with pytest.raises(FieldPortalsAuthError):
        ended.page("history")


def test_records_read_the_portal_json() -> None:
    ticket, payment = (PortalTransaction.from_json(t) for t in CUSTOMER["transactions"])
    assert (ticket.kind, ticket.ticket_id, ticket.appointment_id, ticket.charge_cents) == ("ticket", "2001325", "1168672", 27250)
    assert (payment.payment_cents, payment.invoice_ids, payment.day) == (27250, ("2001325",), date(2026, 9, 17))
    visit = ServiceVisit.from_json(CUSTOMER["services"][0])
    assert visit.ticket_id == "2001325" and visit.products[0].epa_number == "499-561-ZA" and visit.products[0].target_pests == "Ants, Spiders"
    doc = PortalDocument.from_json(CUSTOMER["documents"][0])
    assert (doc.kind, doc.filename, doc.added) == ("photo", "1165192.jpg", date(2026, 7, 22))
    plan = Subscription.from_json(CUSTOMER["subscriptions"][0])
    assert plan.recurring_cents == 27250 and plan.sold == date(2022, 12, 29)
    assert cents("-250.00") == -25000 and day("11/30/-0001") is None


def test_chemical_report_rows() -> None:
    html = ("<table><thead><th>Product</th></thead><tr><td>ALPINE WSG</td><td>499-561-ZA</td><td>250.000 ozs</td>"
            "<td>7.0874 grams</td><td>0.1 %</td><td>Not Specified</td><td>Ants</td><td>Exterior</td><td>2026-09-17</td></tr></table>")
    (row,) = applications_from_html(html)
    assert row.product == "ALPINE WSG" and row.day == date(2026, 9, 17) and row.areas == "Exterior"


def test_invoice_check_refuses_another_ticket() -> None:
    pymupdf = pytest.importorskip("pymupdf")
    from jason.tasks.vendor_portals import invoice_matches

    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for line in ("Invoice", "INVOICE NO.", "ACCOUNT NUMBER", "2001325", "47362", "INVOICE DATE", "09/17/2026",
                 "Invoice", "Total", "$272.50", "Pro Active North"):
        page.insert_text((72, y), line)
        y += 14
    pdf = doc.tobytes()
    ticket = PortalTransaction("ticket", date(2026, 9, 17), "", 27250, 0, 0, "2001325")
    assert invoice_matches(pdf, ticket) == (True, "invoice 2001325")
    other = PortalTransaction("ticket", date(2026, 9, 2), "", 27250, 0, 0, "1977892")
    assert invoice_matches(pdf, other)[0] is False


def test_alignment_pairs_in_order_and_lets_the_attachment_break_a_same_day_tie() -> None:
    from jason.tasks.vendor_verify import PortalPayment, align

    paid = [PortalPayment("47362", "M", date(2025, 5, 18), 25000, ("1291219",)),
            PortalPayment("47362", "M", date(2025, 5, 18), 25000, ("1306983",)),
            PortalPayment("47362", "M", date(2025, 6, 2), 25000, ("1320000",))]
    txs = [{"id": 2, "transactionDate": "2025-05-19 00:00:00", "amount": 25000},
           {"id": 1, "transactionDate": "2025-05-19 00:00:00", "amount": 25000},
           {"id": 3, "transactionDate": "2025-06-03 00:00:00", "amount": 25000}]
    pairing = align(txs, paid, {1: {"1291219"}, 2: {"1306983"}})
    assert pairing == {1: 0, 2: 1, 3: 2}


def test_bill_source_routes_the_vendor_and_offers_the_checked_invoice(tmp_path: Path) -> None:
    from jason.community import mystique
    from jason.sources.fieldportals import VendorPortalBillSource
    from jason.sources.types import BillNeed

    portal = mystique().vendor_portals()[0]
    folder = tmp_path / "vendors" / "proactive" / "47362"
    (folder / "invoices").mkdir(parents=True)
    (folder / "invoices" / "2001325.pdf").write_bytes(b"%PDF-1.4")
    account = {"customer": {"customer_id": "47362"}, "transactions": [
        {"kind": "payment", "day": "2026-09-17", "payment_cents": 27250, "invoice_ids": ["2001325"]}]}
    (folder / "account.json").write_text(json.dumps(account), encoding="utf-8")
    source = VendorPortalBillSource(portal, tmp_path)
    assert source.matches_transaction({"description": "ORIG CO NAME:Pro Active Pest ORIG ID:00109847"})
    assert not source.matches_transaction({"description": "ORIG CO NAME:SMUD"})
    need = BillNeed(27250, date(2026, 9, 18), transaction_id=18716519)
    (bill,) = source.resolve([need]).values()
    assert bill.bill_id == "2001325" and source.ensure_pdf(bill).name == "2001325.pdf"


def test_settings_find_any_record_uid(tmp_path: Path) -> None:
    from jason.config import Settings

    env = tmp_path / ".env"
    env.write_text('keeper_username = "a@b.c"\nproactive_record_uid = "UID123"\n', encoding="utf-8")
    assert Settings.load(env).record_uid("proactive") == "UID123"
    assert Settings.load(env).record_uid("nobody") == ""
