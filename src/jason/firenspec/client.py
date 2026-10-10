"""The reports portal at ``reports.firenspec.com``, a single-page app over Firebase callable functions.

Every call is ``POST https://us-central1-firenspec.cloudfunctions.net/<name>`` with ``{"data": {...}}`` and answers
``{"result": {...}}``. A portal is named by one UUID, the one in the QR code printed on each report
(``https://reports.firenspec.com/#/<uuid>``). The functions this client calls (found in the app's own script and
checked against a capture of October 3, 2026):

- ``publicGetPortalDetails {uuid}``: the vendor (``companyInfo``), the customer, and the site the code names;
- ``publicIsPortalPasswordProtected {customerID, companyID, siteID}``: whether the portal asks for a password;
- ``publicGetReportsForCustomerPortal {customerID, companyID}``: every report, newest first, grouped by kind;
- a report's PDF is ``https://reports.firenspec.com/viewReport.php?id=<url_uuid>``.

A portal may be protected by a password or by a code sent to a phone (``publicVerifyReportsPortalPassword``,
``publicInitTwoFactorForCustomerPortal``). This client never calls those: a protected portal raises
``FirenspecProtected`` and a person reads it. It only reads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import httpx

FUNCTIONS = "https://us-central1-firenspec.cloudfunctions.net"
VIEWER = "https://reports.firenspec.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


class FirenspecError(Exception):
    """The portal answered with something this client does not understand."""


class FirenspecProtected(FirenspecError):
    """The portal asks for a password or a phone code. jason does not enter either."""


@dataclass(frozen=True)
class PortalDetails:
    portal_uuid: str
    company_id: str
    company: str
    license: str
    customer_id: str
    customer: str
    site_id: str


@dataclass(frozen=True)
class Report:
    url_uuid: str                  # names the PDF
    uuid: str
    kind: str                      # the portal's group: inspection, timeline, decibel, summary
    template: str
    site_id: str
    site: str
    address: str
    uploader: str
    day: date | None
    completed: date | None

    @property
    def pdf_url(self) -> str:
        return f"{VIEWER}/viewReport.php?id={self.url_uuid}"


def _day(ms: Any) -> date | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).date()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def parse_details(portal_uuid: str, body: dict[str, Any]) -> PortalDetails:
    result = body.get("result") or {}
    if not result.get("success"):
        raise FirenspecError(f"no portal {portal_uuid}")
    company, customer = result.get("companyInfo") or {}, result.get("customerInfo") or {}
    return PortalDetails(portal_uuid, str(company.get("uuid") or ""), str(company.get("name") or ""),
                         str(company.get("license") or ""), str(customer.get("uuid") or ""),
                         str(customer.get("BillName") or ""), str(result.get("siteID") or ""))


def parse_reports(body: dict[str, Any]) -> list[Report]:
    result = body.get("result") or {}
    if not result.get("success"):
        raise FirenspecError("the portal listed no reports")
    found = []
    for kind, rows in (result.get("pdfs") or {}).items():
        for row in rows or []:
            if not row.get("url_uuid"):
                continue
            found.append(Report(str(row["url_uuid"]), str(row.get("uuid") or ""), kind, str(row.get("templateName") or ""),
                                str(row.get("siteID") or ""), str(row.get("siteName") or ""), str(row.get("siteAddress") or ""),
                                str(row.get("uploaderName") or ""), _day(row.get("date")),
                                _day(row.get("ticketCompletionDate"))))
    return found


class Firenspec:
    def __init__(self, *, http: httpx.Client | None = None, timeout: float = 60.0) -> None:
        self._http = http or httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT})

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Firenspec:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def call(self, name: str, **data: Any) -> dict[str, Any]:
        response = self._http.post(f"{FUNCTIONS}/{name}", json={"data": data}, headers={"Origin": VIEWER, "Referer": VIEWER + "/"})
        if response.status_code != 200:
            raise FirenspecError(f"{name}: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise FirenspecError(f"{name}: not JSON") from exc

    def details(self, portal_uuid: str) -> PortalDetails:
        if not UUID.match(portal_uuid or ""):
            raise FirenspecError(f"not a portal id: {portal_uuid!r}")
        return parse_details(portal_uuid, self.call("publicGetPortalDetails", uuid=portal_uuid))

    def protected(self, details: PortalDetails) -> bool:
        body = self.call("publicIsPortalPasswordProtected", customerID=details.customer_id, companyID=details.company_id,
                         siteID=details.site_id)
        return bool((body.get("result") or {}).get("isPasswordProtected"))

    def reports(self, details: PortalDetails) -> list[Report]:
        """Every report the portal lists for the customer. A protected portal raises ``FirenspecProtected``."""
        if self.protected(details):
            raise FirenspecProtected(f"portal {details.portal_uuid} ({details.customer}) is password protected")
        return parse_reports(self.call("publicGetReportsForCustomerPortal", customerID=details.customer_id,
                                       companyID=details.company_id))

    def report_pdf(self, report: Report) -> bytes:
        response = self._http.get(report.pdf_url)
        if response.status_code != 200 or not response.content.startswith(b"%PDF"):
            raise FirenspecError(f"{report.url_uuid}: HTTP {response.status_code}, not a PDF")
        return response.content


__all__ = ["Firenspec", "FirenspecError", "FirenspecProtected", "PortalDetails", "Report", "parse_details", "parse_reports"]
