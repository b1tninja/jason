"""Signal Service's customer portal (``portal.signalserviceinc.com``): a Django site of server-rendered pages.

One session cookie and a CSRF token on every form. There is no JSON API: the invoice list
(``/invoice/?page=N``, 20 a page), each invoice (``/invoice/<number>/``) and its PDF
(``/invoice/<number>/print/``), the work orders (``/workorder/``), and the empty-until-used
proposals, recurring billing, files, and eSign pages are HTML to parse.

The sign-in page was not in the capture, so ``login`` reads the form itself: its action, its hidden
fields, and its text and password inputs. This client only reads. It never calls the password-change
page, the payment-methods page, or an invoice's Pay form.
"""

from __future__ import annotations

import re
from html import unescape
from typing import Any

import httpx

from jason.signalservice.models import (
    Invoice,
    InvoiceSummary,
    WorkOrder,
    list_pages,
    parse_invoice,
    parse_invoice_list,
    parse_work_orders,
)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
PAGES = ("proposals", "recurring-billing", "files", "esign")


class SignalServiceError(Exception):
    """The portal answered with something this client does not understand."""


class SignalServiceAuthError(SignalServiceError):
    """Login refused, or the session ended."""


def _inputs(form: str) -> list[dict[str, str]]:
    found = []
    for tag in re.findall(r"<input\b[^>]*>", form, re.I):
        attrs = {k.lower(): unescape(v) for k, v in re.findall(r"""([\w-]+)\s*=\s*["']([^"']*)["']""", tag)}
        if attrs.get("name"):
            found.append(attrs)
    return found


def login_form(html: str) -> tuple[str, dict[str, str], str, str]:
    """The sign-in form: (action, hidden fields, username field name, password field name)."""
    for form in re.findall(r"<form\b.*?</form>", html, re.S | re.I):
        fields = _inputs(form)
        password = next((f["name"] for f in fields if f.get("type", "").lower() == "password"), "")
        if not password:
            continue
        user = next((f["name"] for f in fields if f.get("type", "text").lower() in ("text", "email")), "")
        action = re.search(r"""<form\b[^>]*\baction=["']([^"']*)["']""", form, re.I)
        hidden = {f["name"]: f.get("value", "") for f in fields if f.get("type", "").lower() == "hidden"}
        return (action.group(1) if action else ""), hidden, user, password
    raise SignalServiceError("no sign-in form on the page")


class SignalService:
    """One association's account on the portal. ``SignalService("portal.signalserviceinc.com")``."""

    def __init__(self, host: str = "portal.signalserviceinc.com", *, http: httpx.Client | None = None, timeout: float = 60.0) -> None:
        self.base_url = f"https://{host}"
        self._http = http or httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=False)
        self._owns_http = http is None
        self.logged_in = False

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> SignalService:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # --- session ---------------------------------------------------------------------------------

    def login(self, username: str, password: str, *, path: str = "/") -> None:
        """Sign in through the portal's own form. Raises ``SignalServiceAuthError`` when refused."""
        landing = self._http.get(f"{self.base_url}{path}", follow_redirects=True)
        try:
            action, hidden, user_field, password_field = login_form(landing.text)
        except SignalServiceError:
            if self._signed_in(landing.text):
                self.logged_in = True
                return
            raise
        target = str(landing.url.join(action)) if action else str(landing.url)
        response = self._http.post(
            target, data={**hidden, user_field: username, password_field: password},
            headers={"Referer": str(landing.url), "Origin": self.base_url}, follow_redirects=True)
        if response.status_code != 200 or not self._signed_in(response.text):
            raise SignalServiceAuthError("the Signal Service portal refused the login")
        self.logged_in = True

    @staticmethod
    def _signed_in(html: str) -> bool:
        return "/logout/" in html

    def _get(self, path: str) -> httpx.Response:
        response = self._http.get(f"{self.base_url}{path}", follow_redirects=False)
        if response.status_code in (301, 302, 303, 307):
            raise SignalServiceAuthError("the Signal Service portal session ended")
        if response.status_code != 200:
            raise SignalServiceError(f"{path} answered {response.status_code}")
        return response

    # --- pages -----------------------------------------------------------------------------------

    def invoices(self) -> list[InvoiceSummary]:
        """Every invoice in the list, page by page."""
        first = self._get("/invoice/").text
        found = parse_invoice_list(first)
        for page in range(2, list_pages(first) + 1):
            found.extend(parse_invoice_list(self._get(f"/invoice/?page={page}").text))
        return found

    def invoice(self, number: str) -> Invoice:
        return parse_invoice(self._get(f"/invoice/{number}/").text)

    def invoice_pdf(self, number: str) -> bytes:
        """An invoice as the portal prints it (a PDF)."""
        pdf = self._get(f"/invoice/{number}/print/").content
        if not pdf.startswith(b"%PDF"):
            raise SignalServiceError(f"invoice {number} came back without a PDF")
        return pdf

    def work_orders(self) -> list[WorkOrder]:
        return parse_work_orders(self._get("/workorder/").text)

    def page_html(self, name: str) -> str:
        """One of the pages that fill in only when the vendor uses them (``PAGES``)."""
        if name not in PAGES:
            raise ValueError(f"unknown page {name!r}")
        return self._get(f"/{name}/").text


def empty_page(html: str) -> bool:
    """A listing page with nothing on it ("No available ...", or a table with no body rows)."""
    from jason.signalservice.models import _rows

    return not _rows(html) or bool(re.search(r"No available", html))


__all__: list[Any] = ["SignalService", "SignalServiceError", "SignalServiceAuthError", "PAGES", "login_form", "empty_page"]
