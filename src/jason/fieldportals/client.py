"""FieldPortals: the customer portal FieldRoutes (formerly PestRoutes) hosts for field-service companies.

Each company has its own subdomain (``proactive.fieldportals.com``). The portal is one PHP
session: the landing page embeds a CSRF token in its script, the login form posts username,
password, and company, and every page after that is a JSON call:

- ``POST /resources/delegates/buildDelegate`` with ``action=getPage&currentPage=<page>``
  returns ``{data, templates, init, page, loggedOut}``. ``data.customer`` carries the account:
  transactions (tickets and payments), subscriptions, linked properties, and, per page, the
  service history (``history``: the last 50 appointments with ticket and products used) or the
  documents and photos (``files`` and ``account``: signed S3 links that expire).
- ``POST /resources/delegates/actionDelegate.php`` runs an action: ``printInvoice`` (a ticket's
  invoice, the PDF base64 in ``data``), ``runChemicalUsageReport`` and ``getChemicalUsageReport``
  (the products applied in a date range, as an HTML table and as a PDF), ``runNewConditionsReport``
  (conditions the technicians found), and ``switchProperty`` (another property on the same master
  account).

Captured from ``proactive.fieldportals.com.har`` (September 29, 2026). This client only reads;
it never pays, uploads, or changes reminders.
"""

from __future__ import annotations

import base64
import json
import re
from datetime import date
from typing import Any

import httpx

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
CSRF_RE = re.compile(r"""x-csrf-token["']\s*,\s*["']([^"']+)["']""")
PAGES = ("home", "history", "billing", "account", "wallet", "files", "conditions", "chemicals")


class FieldPortalsError(Exception):
    """The portal answered with something this client does not understand."""


class FieldPortalsAuthError(FieldPortalsError):
    """Login refused, or the session ended."""


def us_day(value: date) -> str:
    return value.strftime("%m/%d/%Y")


class FieldPortals:
    """One company's customer portal. ``FieldPortals("proactive")`` is ProActive Pest Control's."""

    def __init__(self, subdomain: str, *, http: httpx.Client | None = None, timeout: float = 60.0) -> None:
        self.subdomain = subdomain
        self.base_url = f"https://{subdomain}.fieldportals.com"
        self._http = http or httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT})
        self._owns_http = http is None
        self._csrf = ""
        self._page = "home"
        self.logged_in = False

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> FieldPortals:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # --- session ---------------------------------------------------------------------------------

    def _read_csrf(self, html: str) -> None:
        found = CSRF_RE.search(html)
        if found:
            self._csrf = found.group(1)

    def login(self, username: str, password: str) -> dict[str, Any]:
        """Sign in and return the home page's JSON. Raises ``FieldPortalsAuthError`` when refused."""
        landing = self._http.get(f"{self.base_url}/landing/index", follow_redirects=True)
        if landing.status_code != 200:
            raise FieldPortalsError(f"landing page answered {landing.status_code}")
        self._read_csrf(landing.text)
        response = self._http.post(
            f"{self.base_url}/resources/session/login",
            data={"username": username, "password": password, "company": self.subdomain, "redirect": ""},
            headers={"Origin": self.base_url, "Referer": f"{self.base_url}/landing/index"},
            follow_redirects=False,
        )
        location = response.headers.get("location", "")
        if response.status_code not in (301, 302, 303) or not location.rstrip("/").endswith("/home"):
            raise FieldPortalsAuthError(f"{self.subdomain} portal refused the login (status {response.status_code})")
        home = self._http.get(f"{self.base_url}/home", headers={"Referer": f"{self.base_url}/landing/index"})
        self._read_csrf(home.text)
        self.logged_in = True
        return self.page("home")

    def _post(self, path: str, data: dict[str, Any], *, referer_page: str | None = None) -> dict[str, Any]:
        page = referer_page or self._page
        response = self._http.post(
            f"{self.base_url}{path}",
            data=data,
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "x-csrf-token": self._csrf,
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/{page}",
            },
            follow_redirects=False,
        )
        if response.status_code in (301, 302, 303, 307):
            raise FieldPortalsAuthError(f"{self.subdomain} portal session ended")
        if response.status_code != 200:
            raise FieldPortalsError(f"{path} answered {response.status_code}")
        try:
            body = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise FieldPortalsError(f"{path} did not answer JSON") from exc
        if isinstance(body, dict) and body.get("loggedOut"):
            raise FieldPortalsAuthError(f"{self.subdomain} portal session ended")
        return body

    # --- pages -----------------------------------------------------------------------------------

    def page(self, name: str) -> dict[str, Any]:
        """One portal page's JSON (``PAGES``). ``data.customer`` is the account as that page sees it."""
        if name not in PAGES:
            raise ValueError(f"unknown page {name!r}")
        # The portal renders the page shell first; the Referer names the page the data is for.
        self._page = name
        return self._post("/resources/delegates/buildDelegate", {"action": "getPage", "currentPage": name}, referer_page=name)

    def customer(self, name: str = "home") -> dict[str, Any]:
        return (self.page(name).get("data") or {}).get("customer") or {}

    def action(self, action: str, page: str, **params: Any) -> dict[str, Any]:
        self._page = page
        return self._post("/resources/delegates/actionDelegate.php", {**params, "action": action}, referer_page=page)

    # --- actions ---------------------------------------------------------------------------------

    def invoice_pdf(self, ticket_id: str | int) -> bytes:
        """A ticket's invoice as the portal prints it (a PDF)."""
        body = self.action("printInvoice", "billing", ticketID=str(ticket_id))
        data = body.get("data") or ""
        pdf = base64.b64decode(data) if data else b""
        if not pdf.startswith(b"%PDF"):
            raise FieldPortalsError(f"invoice {ticket_id} came back without a PDF")
        return pdf

    def chemical_usage_html(self, start: date, end: date) -> str:
        """The products applied from ``start`` to ``end``: the report's HTML table."""
        span = f"{us_day(start)} - {us_day(end)}"
        body = self.action("runChemicalUsageReport", "chemicals", chemDateFilter=span, persistedDateRange="",
                           appointmentID="0", startDate=us_day(start), endDate=us_day(end), suppressProducts="0")
        return str(body.get("html") or "")

    def chemical_usage_pdf(self, start: date, end: date) -> bytes:
        """The same report exported to PDF. Run ``chemical_usage_html`` for the range first."""
        span = f"{us_day(start)} - {us_day(end)}"
        body = self.action("getChemicalUsageReport", "chemicals", chemDateFilter=span, persistedDateRange="",
                           appointmentID="0", startDate=us_day(start), endDate=us_day(end))
        data = body.get("data") or ""
        pdf = base64.b64decode(data) if data else b""
        return pdf if pdf.startswith(b"%PDF") else b""

    def conditions_html(self, start: date, end: date) -> str:
        """Conditions the technicians recorded (found) from ``start`` to ``end``: the report's HTML."""
        span = f"{us_day(start)} - {us_day(end)}"
        body = self.action("runNewConditionsReport", "conditions", dateFoundFilter=span, persistedDateRange=span,
                           resolved="-1", responsibleParty="-1", advanceToggle="false",
                           dateFoundStartDate=us_day(start), dateFoundEndDate=us_day(end))
        return str(body.get("html") or "")

    def switch_property(self, customer_id: str | int) -> str:
        """Load another property on the same master account; returns its name."""
        body = self.action("switchProperty", self._page, customerID=str(customer_id))
        if not body.get("success", True):
            raise FieldPortalsError(f"could not switch to property {customer_id}")
        return str(body.get("customerName") or "")

    def download(self, url: str) -> bytes:
        """A document or photo from its signed link (S3 or CloudFront); the links carry their own authority."""
        response = httpx.get(url, timeout=60.0, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        if response.status_code != 200:
            raise FieldPortalsError(f"download answered {response.status_code}")
        return response.content


__all__ = ["FieldPortals", "FieldPortalsError", "FieldPortalsAuthError", "PAGES", "us_day"]
