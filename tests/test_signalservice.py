"""Signal Service portal: its HTML pages as records, the sign-in form, and the sync to disk."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from jason.signalservice.client import SignalService, SignalServiceAuthError, empty_page, login_form
from jason.signalservice.models import list_pages, parse_invoice, parse_invoice_list, parse_work_orders
from jason.tasks.signal_service import signal_brief, sync_signal

LIST = """<table><thead><tr><th>Invoice</th><th>Invoice date</th><th>Payment due date</th><th>Invoice amount</th><th>Amount due</th><th>Pay</th></tr></thead>
<tr class="row1"><td><a href='/invoice/I-900/'>I-900</a></td><td><span>09/16/2026</span></td><td><span class="badge">PAID</span></td><td class="money"><span>$480.00</span></td><td><span>$0.00</span></td><td></td></tr>
<tr><td><a href='/invoice/I-901/'>I-901</a></td><td><span>09/17/2026</span></td><td><span class="badge">DUE</span></td><td><span>$339.00</span></td><td><span>$339.00</span></td><td></td></tr>
</table><a href="?page=2">2</a>"""
LIST2 = LIST.replace("I-900", "I-800").replace("I-901", "I-801").replace('<a href="?page=2">2</a>', "")


def _detail(number: str, total: str, status: str = "Paid") -> str:
    return f"""<h3>{number}</h3>
<div class="d-table-row"><span class="x">Status:</span>
 <span class="y"><span class="badge">{status}</span></span></div>
<div class="d-table-row"><span class="x">Invoice Date:</span>
 <span class="y">09/16/2026</span></div>
<div class="d-table-row"><span class="x">Payment Date:</span>
 <span class="y">09/16/2026</span></div>
<div class="d-table-row"><span class="x">Remit to:</span>
 <span class="y">PO Box 1
Anytown, CA 90000</span></div>
<div class="d-table-row"><span class="x">Site:</span>
 <span class="y"><a href="#">Example HOA -Bldg. 1 (1)
123 Main St
Sacramento 95800</a></span></div>
<a href="/invoice/{number}/print/">Access PDF</a>
<h4>Recurring</h4>
<table><thead><tr><th>Description</th><th>Site</th><th>Unit Price</th><th>QTY</th><th>Amount</th></tr></thead><tbody>
<tr><td data-title="Description">Monitoring (10/01 to 12/31 @ $39.00 per Mo.)</td><td>123 Main St</td><td>$117.00</td><td>1.00</td><td>$117.00</td></tr>
<tr><td data-title="Description">Lease</td><td>123 Main St</td><td>$363.00</td><td>1.00</td><td>$363.00</td></tr>
</tbody></table>
<div class="row"><div><span>Subtotal</span></div><div><span>{total}</span></div></div>
<div class="row"><div><span>Sales Tax</span></div><div><span>$0.00</span></div></div>
<div class="row"><div><span>Total</span></div><div><span>{total}</span></div></div>
<div class="row"><div><span>Payments Applied</span></div><div><span>{total if status == "Paid" else "$0.00"}</span></div></div>
<div class="row"><div><span>Invoice Amount Due</span></div><div><span>{"$0.00" if status == "Paid" else total}</span></div></div>"""


OLD_DETAIL = """<h3>I-S-1</h3><span>Status:</span><span><span class="badge">Paid</span></span>
<table><tr><th>Description</th><th>Amount</th></tr>
<tr><td>Basic Monitoring Service (04/01/2024 - 06/30/2024) (Qty: 3.00 @ $36.00 each)</td><td>$108.00</td></tr></table>"""

ORDERS = """<table><tr><th>Number</th><th>Date</th><th>Account Manager</th><th>Summary</th><th>Address</th><th>Status</th></tr>
<tr><td data-title="Number">W-1</td><td>08/20/2026</td><td>A. Tech</td><td>Supervisory Alarm Signal</td><td>Example HOA -Bldg. 1</td><td><span>Done</span></td></tr></table>"""

LOGIN = """<form method="post" action="/login/"><input type="hidden" name="csrfmiddlewaretoken" value="tok">
<input type="text" name="email"><input type="password" name="pw"></form>"""


def test_invoice_list_and_pager() -> None:
    rows = parse_invoice_list(LIST)
    assert [(r.number, r.paid, r.total_cents, r.due_cents, r.path) for r in rows] == [
        ("I-900", True, 48000, 0, "/invoice/I-900/"), ("I-901", False, 33900, 33900, "/invoice/I-901/")]
    assert rows[0].day == date(2026, 9, 16)
    assert list_pages(LIST) == 2 and list_pages(LIST2) == 1


def test_invoice_detail() -> None:
    inv = parse_invoice(_detail("I-900", "$480.00"))
    assert (inv.number, inv.status, inv.day, inv.paid_day) == ("I-900", "Paid", date(2026, 9, 16), date(2026, 9, 16))
    assert "123 Main St" in inv.site and inv.remit_to.startswith("PO Box 1")
    assert (inv.subtotal_cents, inv.tax_cents, inv.total_cents, inv.applied_cents, inv.due_cents) == (48000, 0, 48000, 48000, 0)
    assert [(x.unit_cents, x.amount_cents) for x in inv.lines] == [(11700, 11700), (36300, 36300)]
    assert inv.pdf_path == "/invoice/I-900/print/" and inv.kind == "Recurring"


def test_older_invoice_layout_reads_quantity_and_unit() -> None:
    line = parse_invoice(OLD_DETAIL).lines[0]
    assert (line.unit_cents, line.quantity, line.amount_cents) == (3600, "3.00", 10800)


def test_work_orders_and_empty_pages() -> None:
    order = parse_work_orders(ORDERS)[0]
    assert (order.number, order.day, order.summary, order.status) == ("W-1", date(2026, 8, 20), "Supervisory Alarm Signal", "Done")
    assert empty_page("<table><tr><td>No available Documents at this time</td></tr></table>")
    assert not empty_page(ORDERS)


def test_login_form_is_read_not_assumed() -> None:
    assert login_form(LOGIN) == ("/login/", {"csrfmiddlewaretoken": "tok"}, "email", "pw")
    with pytest.raises(Exception):
        login_form("<form><input name='q'></form>")


def _client(handler) -> SignalService:
    return SignalService("portal.example.test", http=httpx.Client(transport=httpx.MockTransport(handler)))


def _portal_handler(unpaid_after: bool = False):
    calls: list[str] = []
    pdf = b"%PDF-1.4 invoice"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path + (f"?{request.url.query.decode()}" if request.url.query else "")
        calls.append(path)
        pages = {
            "/invoice/": LIST, "/invoice/?page=2": LIST2, "/workorder/": ORDERS,
            "/invoice/I-900/": _detail("I-900", "$480.00"), "/invoice/I-901/": _detail("I-901", "$339.00", "Due"),
            "/invoice/I-800/": _detail("I-800", "$480.00"), "/invoice/I-801/": _detail("I-801", "$339.00"),
            "/proposals/": "<p>none</p>", "/recurring-billing/": "<table></table>",
            "/files/": "<table><tr><td>No available files</td></tr></table>",
            "/esign/": "<table><tr><th>Name</th></tr><tr><td>Contract</td><td>Signed</td><td>01/01/2026</td><td></td></tr></table>",
        }
        if path.endswith("/print/"):
            return httpx.Response(200, content=pdf)
        return httpx.Response(200, text=pages[path]) if path in pages else httpx.Response(404)

    handler.calls = calls  # type: ignore[attr-defined]
    return handler


def test_login_refused_and_accepted() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=LOGIN)

    with pytest.raises(SignalServiceAuthError):
        _client(refuse).login("u", "p")

    def accept(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            assert b"email=u" in request.content and b"pw=p" in request.content and b"csrfmiddlewaretoken=tok" in request.content
            return httpx.Response(200, text='<a href="/logout/">Log out</a>')
        return httpx.Response(200, text=LOGIN)

    client = _client(accept)
    client.login("u", "p")
    assert client.logged_in


def test_session_end_is_an_auth_error() -> None:
    client = _client(lambda r: httpx.Response(302, headers={"location": "/login/"}))
    with pytest.raises(SignalServiceAuthError):
        client.invoices()


def test_sync_reads_every_page_and_keeps_paid_invoices_on_a_second_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("jason.tasks.signal_service._pdf_text", lambda pdf: "Invoice I-900 I-901 I-800 I-801 480.00 339.00")
    portal = SimpleNamespace(key="signal", vendor="Example Alarm", account="portal.example.test", budget_line="Fire Alarm",
                             service="monitoring")
    handler = _portal_handler()
    result = sync_signal(_client(handler), portal, tmp_path)
    assert (result.invoices, result.invoices_read, result.pdfs_downloaded, result.work_orders) == (4, 4, 4, 1)
    assert result.pages_with_content == ["esign"]
    assert (tmp_path / "vendors" / "signal" / "invoices" / "I-900.pdf").read_bytes().startswith(b"%PDF")

    handler2 = _portal_handler()
    again = sync_signal(_client(handler2), portal, tmp_path)
    # Paid invoices and their PDFs are not fetched again; the two the list shows as due are read once more.
    assert again.invoices_read == 2 and again.pdfs_downloaded == 0 and again.pdfs_present == 4
    assert not any(c.endswith("/print/") for c in handler2.calls)

    brief = signal_brief(tmp_path, portal, today=date(2026, 10, 3))
    assert brief["dueCents"] == 33900 and brief["billedThisYearCents"] == 2 * (48000 + 33900)
    assert brief["invoices"][0]["number"] in {"I-900", "I-901"} and brief["workOrders"][0]["number"] == "W-1"


def test_a_pdf_for_another_invoice_is_refused(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("jason.tasks.signal_service._pdf_text", lambda pdf: "Invoice X-1 total 1.00")
    portal = SimpleNamespace(key="signal", vendor="Example Alarm", account="h", budget_line="b", service="s")
    result = sync_signal(_client(_portal_handler()), portal, tmp_path)
    assert len(result.mismatches) == 4 and result.pdfs_downloaded == 0
    assert (tmp_path / "vendors" / "signal" / "invoices" / "_mismatch" / "I-900.pdf").is_file()
