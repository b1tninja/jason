"""City of Sacramento Citizen Access.

The public portal is Accela Citizen Access at
``aca-prod.accela.com/SACRAMENTO``. It searches building, planning, public
works, and operating permits, looks up parcels and addresses, and exports the
current result grid as CSV. Accela documents that export as the first 5,000
rows.

That portal is not the Accela Construct API (``https://apis.accela.com``).
Construct's ``POST /v4/search/records`` is documented at developer.accela.com
and needs an application the agency has authorized. Sacramento's Citizen
Access capture does not call it.

The public Search button is a full postback. A result grid's Download
results control posts again, and ``ExportCSV`` then requests
``Export2CSV.ashx``. The ``flag`` is that script's cache-buster: seconds
concatenated with minutes. The rows come from the session.

A record page lists conditions in the conditions grid and offers
Print/View Record through ``ReportParameter.aspx``. That page sends the
browser to ``ShowReport.aspx``, which returns the PDF. Documents, including
the application file, are a separate attachment list. ``fetch`` replaces
HTTP in tests.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import Enum
from html import unescape
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from typing import Callable
from urllib.parse import parse_qs, quote, unquote, urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


class Module(Enum):
    """Citizen Access tabs that search records. Values are the module query."""

    BUILDING = "Building"
    PLANNING = "Planning"
    PUBLIC_WORKS = "PublicWorks"
    OPERATING_PERMIT = "OperatingPermit"


class AccelaError(RuntimeError):
    """The portal returned a page the client could not use."""


_ORIGIN = "https://aca-prod.accela.com"
_ROOT = _ORIGIN + "/SACRAMENTO"
_TAB_LIST = "HOME|0|Building|1|Planning|2|PublicWorks|3|APO|4|OperatingPermit|5|CurrentTabIndex|"
_TAB_INDEX = {
    Module.BUILDING: "1",
    Module.PLANNING: "2",
    Module.PUBLIC_WORKS: "3",
    Module.OPERATING_PERMIT: "4",
}
_SEARCH = "ctl00$PlaceHolderMain$btnNewSearch"
_EXPORT = "ctl00$PlaceHolderMain$dgvPermitList$gdvPermitList$gdvPermitListtop4btnExport"
_SEARCH_TYPE = "ctl00$PlaceHolderMain$ddlSearchType"
_PARCEL_NUMBER = "ctl00$PlaceHolderMain$parcelLookupForm$txtAPO_Search_by_Parcel_ParcelNumber"
_ADDRESS_FROM = "ctl00$PlaceHolderMain$addressLookupForm$txtAPO_Search_by_Address_StreetNumber$ChildControl0"
_ADDRESS_TO = "ctl00$PlaceHolderMain$addressLookupForm$txtAPO_Search_by_Address_StreetNumber$ChildControl1"
_ADDRESS_DIRECTION = "ctl00$PlaceHolderMain$addressLookupForm$ddlAPO_Search_by_Address_Direction"
_ADDRESS_STREET = "ctl00$PlaceHolderMain$addressLookupForm$txtAPO_Search_by_Address_StreetName"
_ADDRESS_SUFFIX = "ctl00$PlaceHolderMain$addressLookupForm$ddlStreetSuffix"

_RECORD_FIELDS = {
    "permit_number": "ctl00$PlaceHolderMain$generalSearchForm$txtGSPermitNumber",
    "project_name": "ctl00$PlaceHolderMain$generalSearchForm$txtGSProjectName",
    "street_from": "ctl00$PlaceHolderMain$generalSearchForm$txtGSNumber$ChildControl0",
    "street_to": "ctl00$PlaceHolderMain$generalSearchForm$txtGSNumber$ChildControl1",
    "direction": "ctl00$PlaceHolderMain$generalSearchForm$ddlGSDirection",
    "street_name": "ctl00$PlaceHolderMain$generalSearchForm$txtGSStreetName",
    "street_suffix": "ctl00$PlaceHolderMain$generalSearchForm$ddlGSStreetSuffix",
    "parcel": "ctl00$PlaceHolderMain$generalSearchForm$txtGSParcelNo",
    "license_type": "ctl00$PlaceHolderMain$generalSearchForm$ddlGSLicenseType",
    "license_number": "ctl00$PlaceHolderMain$generalSearchForm$txtGSLicenseNumber",
    "first_name": "ctl00$PlaceHolderMain$generalSearchForm$txtGSFirstName",
    "last_name": "ctl00$PlaceHolderMain$generalSearchForm$txtGSLastName",
    "business_name": "ctl00$PlaceHolderMain$generalSearchForm$txtGSBusiName",
}

_CAP = re.compile(
    r"capID1=([^&\"']+)&(?:amp;)?capID2=([^&\"']+)&(?:amp;)?capID3=([^&\"']+)"
    r"(?:&(?:amp;)?agencyCode=([^&\"']+))?"
)
_MODULE = re.compile(r"Module=([^&\"']+)")
_PERMIT_NUMBER = re.compile(r'lblPermitNumber\d*"[^>]*>\s*([^<]+?)\s*<')
_SHOWING = re.compile(r"Showing\s+(\d+)-(\d+)\s+of\s+(\d+)")


def _result_showing(html: str):
    """The caption on the search grid, not the signed-in My Permits list."""
    marker = -1
    for token in (
        "dgvPermitList_gdvPermitList_gdvPermitListtop4btnExport",
        "dgvPermitList$gdvPermitList$gdvPermitListtop4btnExport",
    ):
        marker = html.find(token)
        if marker >= 0:
            break
    window = html[max(0, marker - 600) : marker] if marker >= 0 else ""
    return _SHOWING.search(window)
_MARK = re.compile(
    r"Marked as <span[^>]*>([^<]*)</span> on <span[^>]*>([^<]*)</span> by <span[^>]*>([^<]*)</span>"
)
_PARCEL_LABELS = {
    "Parcel Number:": "number",
    "Lot:": "lot",
    "Block:": "block",
    "Subdivision:": "subdivision",
    "Parcel Area:": "area",
    "Zoning:": "zoning",
}


@dataclass(frozen=True)
class CapId:
    """The three ids on a Citizen Access record URL."""

    id1: str
    id2: str
    id3: str
    agency: str = "SACRAMENTO"
    module: str = "Building"

    @classmethod
    def parse(cls, text: str, *, module: str = "Building") -> CapId:
        """``26BCM:00000:03422``."""
        parts = text.split(":")
        if len(parts) != 3 or not all(parts):
            raise AccelaError(f"A cap id is three parts separated by colons, not {text!r}")
        return cls(parts[0], parts[1], parts[2], module=module)


@dataclass(frozen=True)
class RecordQuery:
    """Fields on the module search form. Omitted dates keep the portal default."""

    permit_number: str = ""
    project_name: str = ""
    start: date | None = None
    end: date | None = None
    street_from: str = ""
    street_to: str = ""
    direction: str = ""
    street_name: str = ""
    street_suffix: str = ""
    parcel: str = ""
    license_type: str = ""
    license_number: str = ""
    first_name: str = ""
    last_name: str = ""
    business_name: str = ""


@dataclass(frozen=True)
class Permit:
    """One row of a record search. ``cap`` is set when that row was on the grid page."""

    number: str
    opened: date | None
    record_type: str
    description: str
    address: str
    status: str
    cap: CapId | None = None
    module: Module | None = None


@dataclass(frozen=True)
class SearchResult:
    """The CSV export, with cap ids merged from the grid that was on screen."""

    permits: tuple[Permit, ...]
    csv_text: str
    showing: tuple[int, int, int] | None = None


@dataclass(frozen=True)
class Fee:
    """One fee line on the record. Amounts are integer cents. ``when`` is the table's Date column, the invoice date: a
    fee invoiced in August and paid in September still reads August."""

    paid: bool
    when: date | None
    invoice: str
    amount_cents: int


@dataclass(frozen=True)
class ReviewMark:
    """One status line under a processing task."""

    status: str
    when: date | None
    by: str


@dataclass(frozen=True)
class ReviewTask:
    """A processing task and the marks under it."""

    name: str
    marks: tuple[ReviewMark, ...]


@dataclass(frozen=True)
class RelatedRecord:
    """One row of the related-records tree. ``depth`` is 1 for the parent."""

    number: str
    record_type: str
    project: str
    opened: date | None
    cap: CapId | None
    depth: int


@dataclass(frozen=True)
class Condition:
    """One condition on the record. ``applied`` is the date in the status line."""

    group: str
    kind: str
    name: str
    comment: str
    status: str
    severity: str
    applied: date | None


@dataclass(frozen=True)
class Report:
    """A Print/View Record link. ``report_id`` is the portal's reportID."""

    name: str
    report_type: str
    report_id: str


@dataclass(frozen=True)
class Document:
    """One file on the record's attachment list."""

    name: str
    number: str
    kind: str
    size: str
    uploaded: date | None
    record_number: str


@dataclass(frozen=True)
class RecordDetail:
    """Fees, processing, conditions, reports, and related records for one cap."""

    cap: CapId
    fees_paid: tuple[Fee, ...]
    fees_unpaid: tuple[Fee, ...]
    tasks: tuple[ReviewTask, ...]
    related: tuple[RelatedRecord, ...]
    conditions: tuple[Condition, ...] = ()
    reports: tuple[Report, ...] = ()
    # The record page's heading, and its completed inspections.
    status: str = ""
    record_type: str = ""
    inspections: tuple = ()
    # The totals the fee tables print under their last row ("Total paid fees: $549.81"); None when not printed.
    paid_total_cents: int | None = None
    unpaid_total_cents: int | None = None

    @property
    def paid_cents(self) -> int:
        return sum(fee.amount_cents for fee in self.fees_paid)

    @property
    def fees_complete(self) -> bool:
        """The fee lines read add up to the totals the portal printed."""
        return all(total is None or total == read for total, read in
                   ((self.paid_total_cents, self.paid_cents), (self.unpaid_total_cents, self.unpaid_cents)))

    @property
    def unpaid_cents(self) -> int:
        return sum(fee.amount_cents for fee in self.fees_unpaid)


@dataclass(frozen=True)
class ParcelHit:
    """A parcel-result row. ``seq`` is ParcelSeq when the row is a detail link."""

    number: str
    seq: str = ""
    lot: str = ""
    block: str = ""
    target: str = ""


@dataclass(frozen=True)
class ParcelInfo:
    """The parcel detail page. Owner names are not published on this portal."""

    number: str
    lot: str
    block: str
    subdivision: str
    area: str
    zoning: str
    addresses: tuple[str, ...]


@dataclass(frozen=True)
class AddressHit:
    """One address row returned with its parcel number."""

    parcel_number: str
    address: str


@dataclass(frozen=True)
class Collection:
    """A signed-in user's collection."""

    id: str
    name: str


class SacramentoCitizenAccess:
    """Sacramento Citizen Access. Public search does not send a password."""

    name = "Sacramento"
    agency = "SACRAMENTO"

    def __init__(self, fetch=None, *, clock=None) -> None:
        self._fetch = fetch if fetch is not None else _live_fetch()
        self._clock = clock or datetime.now

    def sign_in(self, username: str, password: str) -> bool:
        """Start a citizen session. The password is sent once and not stored."""
        self._request("GET", f"{_ROOT}/Login.aspx", None, {})
        payload = json.dumps({"Name": username, "Pwd": password, "IsRemember": 0})
        text = self._request(
            "POST",
            f"{_ROOT}/api/PublicUser/SignIn",
            payload,
            {"Content-Type": "application/json"},
        )
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AccelaError("Sign-in did not return JSON") from exc
        return data.get("type") == "success"

    def search(self, module: Module, query: RecordQuery | None = None) -> SearchResult:
        """Search one module and download the result CSV."""
        query = query or RecordQuery()
        url = _cap_home(module)
        form = read_form(self._request("GET", url, None, {}))
        if "__VIEWSTATE" not in form:
            raise AccelaError("The search page did not include a form")
        _apply_record_query(form, query)
        form["__EVENTTARGET"] = _SEARCH
        form["__EVENTARGUMENT"] = ""
        results = self._request("POST", url, urlencode(form), _form_headers(url))
        if "Error.aspx" in redirect_target(results):
            raise AccelaError("Citizen Access rejected the search")
        shown = _result_showing(results)
        showing = (int(shown.group(1)), int(shown.group(2)), int(shown.group(3))) if shown else None
        if _EXPORT not in results:
            heading = record_heading(results, module)
            if heading:
                return SearchResult(heading, "", showing)
            return SearchResult(permits_from_html(results, module), "", showing)
        form = read_form(results)
        form["__EVENTTARGET"] = _EXPORT
        form["__EVENTARGUMENT"] = ""
        self._request("POST", url, urlencode(form), _form_headers(url))
        moment = self._clock()
        flag = f"{moment.second}{moment.minute}"
        csv_text = self._request("GET", f"{_ROOT}/Export2CSV.ashx?flag={flag}", None, {"Referer": url})
        if "Permit Number" not in csv_text:
            return SearchResult(permits_from_html(results, module), "", showing)
        permits = attach_caps(parse_permits_csv(csv_text, module=module), results, module)
        return SearchResult(permits, csv_text, showing)

    def detail(self, cap: CapId, *, show_all: bool = False) -> RecordDetail:
        """Fees, processing marks, conditions, reports, and related records."""
        page = self._request("GET", _detail_url(cap), None, {})
        paid, paid_total = self._fees(cap, "DisplayFeePaid", lambda n: _fee_paid_body(cap, n), paid=True)
        unpaid, unpaid_total = self._fees(cap, "DisplayFeeNoPaid", lambda n: {"pageNum": n, "moduleName": cap.module}, paid=False)
        tasks = parse_tasks(
            self._page_method(cap, "GetProcessingData", {"agencyCode": cap.agency, "moduleName": cap.module})
        )
        related = parse_related(
            self._page_method(cap, "GetBuildCapTree", {"moduleName": cap.module, "isShowAll": show_all})
        )
        record_type, status = parse_record_status(page)
        return RecordDetail(
            cap,
            paid,
            unpaid,
            tasks,
            related,
            parse_conditions(page),
            parse_reports(page),
            status=status,
            record_type=record_type,
            inspections=parse_inspections(page),
            paid_total_cents=paid_total,
            unpaid_total_cents=unpaid_total,
        )

    def _fees(self, cap: CapId, method: str, body: Callable[[int], dict], *, paid: bool,
              max_pages: int = 20) -> tuple[tuple[Fee, ...], int | None]:
        """Every page of a fee table (five lines a page, turned by ``changePage``) and its printed total. The record
        page must be loaded first: the page methods answer 500 without it."""
        found: list[Fee] = []
        total: int | None = None
        number = 1
        while number <= max_pages:
            html = self._page_method(cap, method, body(number))
            found.extend(parse_fees(html, paid=paid))
            total = fee_total(html) if total is None else total
            if number >= fee_pages(html):
                break
            number += 1
        return tuple(found), total

    def documents(self, cap: CapId) -> tuple[Document, ...]:
        """Files attached to the record, including the application."""
        self._request("GET", _detail_url(cap), None, {})
        page = self._request("GET", _attachments_url(cap), None, {"Referer": _detail_url(cap)})
        return parse_documents(page)

    def download_report(self, cap: CapId, *, report_id: str = "") -> bytes:
        """The Print/View Record PDF. The record page has to be open in this session."""
        page = self._request("GET", _detail_url(cap), None, {})
        reports = parse_reports(page)
        if report_id:
            reports = tuple(item for item in reports if item.report_id == report_id)
        if not reports:
            raise AccelaError("This record has no report")
        report = reports[0]
        query = urlencode(
            {
                "Module": cap.module,
                "reportType": report.report_type,
                "reportID": report.report_id,
                "agencyCode": cap.agency,
            }
        )
        payload, headers = self._file(
            "GET",
            f"{_ROOT}/Report/ShowReport.aspx?{query}",
            None,
            {"Referer": _detail_url(cap)},
        )
        content_type = headers.get("Content-Type", headers.get("content-type", ""))
        if not payload.startswith(b"%PDF") and "pdf" not in content_type.lower():
            raise AccelaError("The report did not return a PDF")
        end = payload.rfind(b"%%EOF")
        if end >= 0:
            payload = payload[: end + len(b"%%EOF")]
        return payload

    def lookup_parcel(self, number: str) -> ParcelInfo | None:
        """Parcel information lookup. One hit returns the detail page."""
        hits, page = self._parcel_search(number)
        if len(hits) == 1 and hits[0].target:
            return self._open_parcel_row(page, hits[0].target)
        if len(hits) == 1 and hits[0].seq:
            return self.parcel(hits[0].number, seq=hits[0].seq)
        if page and parse_parcel(page) is not None:
            return parse_parcel(page)
        return None

    def find_parcels(self, number: str) -> tuple[ParcelHit, ...]:
        """Every parcel link a parcel-number search returned."""
        return self._parcel_search(number)[0]

    def parcel(self, number: str, *, seq: str = "") -> ParcelInfo | None:
        """The parcel detail page."""
        query = urlencode(
            {
                "ParcelSeq": seq,
                "ParcelUID": "",
                "sourceNumbs": "",
                "ParcelNum": number,
                "agencyCode": "",
            }
        )
        return parse_parcel(self._request("GET", f"{_ROOT}/APO/ParcelDetail.aspx?{query}", None, {}))

    def lookup_address(
        self,
        street: str,
        *,
        suffix: str = "",
        number_from: str = "",
        number_to: str = "",
        direction: str = "",
    ) -> tuple[AddressHit, ...]:
        """Address lookup. The default search type on the page is address."""
        url = _apo_url()
        form = read_form(self._request("GET", url, None, {}))
        form["__EVENTTARGET"] = _SEARCH
        form["__EVENTARGUMENT"] = ""
        form[_SEARCH_TYPE] = "0"
        form[_ADDRESS_STREET] = street
        form[_ADDRESS_SUFFIX] = suffix
        form[_ADDRESS_FROM] = number_from
        form[_ADDRESS_TO] = number_to
        form[_ADDRESS_DIRECTION] = direction
        body = self._request("POST", url, urlencode(form), _form_headers(url))
        target = redirect_target(body)
        if target:
            body = self._request("GET", _absolute(target), None, {})
        return parse_addresses(body)

    def collections(self) -> tuple[Collection, ...]:
        """Collections for the signed-in citizen. Anonymous sessions get an empty tuple."""
        html = self._request("GET", f"{_ROOT}/MyCollection/MyCollectionManagement.aspx", None, {})
        return parse_collections(html)

    def collection_records(self, collection_id: str) -> tuple[Permit, ...]:
        """Every record saved in one collection, following the list's "Next >" pages."""
        return self.collection(collection_id)[1]

    def collection(self, collection_id: str, *, max_pages: int = 30) -> tuple[CollectionSummary, tuple[Permit, ...]]:
        """A collection's totals (records, inspections by result, fees paid and due) and every record in it. The list
        shows ten records a page; each further page is the grid's "Next >" postback."""
        url = f"{_ROOT}/MyCollection/MyCollectionDetail.aspx?collectionId={quote(collection_id)}"
        html = self._request("GET", url, None, {})
        summary = parse_collection_summary(html)
        records = list(permits_from_html(html, Module.BUILDING))
        for _page in range(max_pages):
            target = next_page_target(html)
            if not target:
                break
            form = read_form(html)
            form["__EVENTTARGET"] = target
            form["__EVENTARGUMENT"] = ""
            html = self._request("POST", url, urlencode(form), _form_headers(url))
            seen = {record.number for record in records}
            more = [record for record in permits_from_html(html, Module.BUILDING) if record.number not in seen]
            if not more:
                break
            records.extend(more)
        return summary, tuple(records)

    def _parcel_search(self, number: str) -> tuple[tuple[ParcelHit, ...], str]:
        url = _apo_url()
        form = read_form(self._request("GET", url, None, {}))
        form["__EVENTTARGET"] = _SEARCH_TYPE
        form["__EVENTARGUMENT"] = ""
        form[_SEARCH_TYPE] = "1"
        switched = self._request("POST", url, urlencode(form), _form_headers(url))
        form = read_form(switched) if _is_html_document(switched) else apply_delta(form, switched)
        form["__EVENTTARGET"] = _SEARCH
        form["__EVENTARGUMENT"] = ""
        form[_SEARCH_TYPE] = "1"
        form[_PARCEL_NUMBER] = number
        body = self._request("POST", url, urlencode(form), _form_headers(url))
        target = redirect_target(body)
        if target:
            hit = _hit_from_query(target)
            return ((hit,) if hit else ()), ""
        grid = parse_parcel_grid(body)
        if grid:
            return grid, body
        return parse_parcel_links(body), body

    def _open_parcel_row(self, results_html: str, target: str) -> ParcelInfo | None:
        form = read_form(results_html)
        form["__EVENTTARGET"] = target
        form["__EVENTARGUMENT"] = ""
        opened = self._request("POST", _apo_url(), urlencode(form), _form_headers(_apo_url()))
        redirect = redirect_target(opened)
        if redirect:
            opened = self._request("GET", _absolute(redirect), None, {})
        return parse_parcel(opened)

    def _page_method(self, cap: CapId, name: str, payload: dict) -> str:
        text = self._request(
            "POST",
            f"{_ROOT}/Cap/CapDetail.aspx/{name}",
            json.dumps(payload),
            {
                "Content-Type": "application/json; charset=UTF-8",
                "Referer": _detail_url(cap),
            },
        )
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AccelaError(f"{name} did not return JSON") from exc
        value = data.get("d") if isinstance(data, dict) else ""
        return value if isinstance(value, str) else ""

    def _file(self, method: str, url: str, body: str | None, headers: dict[str, str]) -> tuple[bytes, dict[str, str]]:
        status, payload, response_headers = self._fetch(method, url, body, headers)
        if status >= 400:
            raise AccelaError(f"{method} {url} returned {status}")
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        return payload, response_headers

    def _request(self, method: str, url: str, body: str | None, headers: dict[str, str]) -> str:
        status, payload, _response_headers = self._fetch(method, url, body, headers)
        if status >= 400:
            raise AccelaError(f"{method} {url} returned {status}")
        if isinstance(payload, bytes):
            return payload.decode("utf-8", errors="replace")
        return payload


def read_form(html: str) -> dict[str, str]:
    """Posted fields on the Citizen Access form, including viewstate."""
    parser = _FormParser()
    parser.feed(html)
    return parser.fields


def parse_delta(payload: str) -> tuple[tuple[str, str, str], ...]:
    """ASP.NET AJAX delta: ``length|type|id|content|``."""
    items: list[tuple[str, str, str]] = []
    index = 0
    size = len(payload)
    while index < size:
        bar = payload.find("|", index)
        if bar < 0:
            break
        length_text = payload[index:bar]
        if not length_text.isdigit():
            break
        length = int(length_text)
        index = bar + 1
        bar = payload.find("|", index)
        if bar < 0:
            break
        kind = payload[index:bar]
        index = bar + 1
        bar = payload.find("|", index)
        if bar < 0:
            break
        ident = payload[index:bar]
        index = bar + 1
        content = payload[index : index + length]
        index += length
        if index < size and payload[index] == "|":
            index += 1
        items.append((kind, ident, content))
    return tuple(items)


def apply_delta(fields: dict[str, str], payload: str) -> dict[str, str]:
    """Copy ``fields`` and replace hidden fields the delta updated."""
    updated = dict(fields)
    for kind, ident, content in parse_delta(payload):
        if kind == "hiddenField" and ident:
            updated[ident] = content
    return updated


def redirect_target(payload: str) -> str:
    """The ``pageRedirect`` path, or empty when the body is a results page."""
    for kind, _ident, content in parse_delta(payload):
        if kind == "pageRedirect" and content:
            return unquote(content)
    return ""


def parse_permits_csv(text: str, *, module: Module) -> tuple[Permit, ...]:
    """Rows of an ``Export2CSV`` body. A leading truncation note is skipped."""
    rows = list(csv.reader(io.StringIO(text)))
    while rows and not any(cell.strip() == "Permit Number" for cell in rows[0]):
        rows = rows[1:]
    if not rows:
        return ()
    header = [cell.strip() for cell in rows[0]]
    found: list[Permit] = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        data = {header[i]: row[i].strip() for i in range(min(len(header), len(row))) if header[i]}
        found.append(
            Permit(
                number=data.get("Permit Number", ""),
                opened=_mdy(data.get("Date", "")),
                record_type=data.get("Record Type", ""),
                description=data.get("Description", ""),
                address=data.get("Address", ""),
                status=data.get("Status", ""),
                module=module,
            )
        )
    return tuple(found)


def record_heading(html: str, module: Module) -> tuple[Permit, ...]:
    """The record page a one-hit search opens: number, type, status, and cap."""
    number = re.search(r'lblPermitNumber"[^>]*>\s*([^<]+)', html)
    if number is None:
        return ()
    record_type = re.search(r'lblPermitType"[^>]*>\s*([^<]+)', html)
    status = re.search(r'lblRecordStatus"[^>]*>\s*([^<]+)', html)
    return (
        Permit(
            unescape(number.group(1)).strip().rstrip(":"),
            None,
            unescape(record_type.group(1)).strip() if record_type else "",
            "",
            "",
            unescape(status.group(1)).strip() if status else "",
            _cap_in(html, module),
            _module_in(html, module),
        ),
    )


def permits_from_html(html: str, module: Module) -> tuple[Permit, ...]:
    """Permit number, date, and cap id from a result grid; and, where the grid's row labels them (a collection's list),
    its type, description, address, and status."""
    found: list[Permit] = []
    matches = list(_PERMIT_NUMBER.finditer(html))
    for n, match in enumerate(matches):
        # This row's cap link and date sit before its number; start after the previous number so a short row does not
        # take the previous row's.
        window_start = max(matches[n - 1].end() if n else 0, match.start() - 900)
        window = html[window_start : match.end()]
        cap = _cap_in(window, module)
        opened = _mdy(_nearby_date(window))
        # The rest of this row: from the number to the next row's number.
        row = html[match.end() : matches[n + 1].start() if n + 1 < len(matches) else match.end() + 4000]
        found.append(
            Permit(
                number=unescape(match.group(1)).strip(),
                opened=opened,
                record_type=_row_label(row, "lblType"),
                description=_row_label(row, "lblDescription"),
                address=_row_label(row, "lblAddress"),
                status=_row_label(row, "lblStatus"),
                cap=cap,
                module=_module_in(window, module),
            )
        )
    return tuple(found)


def _row_label(row: str, name: str) -> str:
    match = re.search(rf'_{name}"[^>]*>([\s\S]*?)</span>', row)
    return _text(match.group(1)) if match else ""


@dataclass(frozen=True)
class CollectionSummary:
    """A collection's header: its records, inspections by result, and fees paid and due (integer cents)."""

    records: int | None
    inspections: int | None
    inspections_by: dict
    fees_paid_cents: int | None
    fees_due_cents: int | None


def parse_collection_summary(html: str) -> CollectionSummary:
    """``Total Records``, ``Inspections Summary``, and ``Fees Summary`` at the top of MyCollectionDetail.aspx."""
    text = re.sub(r"\s+", " ", _plain(html))
    records = re.search(r"Total Records:\s*(\d+)", text)
    inspections = re.search(r"Inspections Summary:\s*(\d+)\s*\(([^)]*)\)", text)
    fees = re.search(r"Fees Summary:\s*\$([\d,]+\.\d{2})\s*Paid\s*,\s*\$([\d,]+\.\d{2})\s*Due", text)
    by = {}
    if inspections:
        by = {kind.strip().lower(): int(count) for count, kind in re.findall(r"(\d+)\s+([A-Za-z][A-Za-z ]*?)\s*(?:,|$)", inspections.group(2))}
    return CollectionSummary(
        int(records.group(1)) if records else None,
        int(inspections.group(1)) if inspections else None,
        by,
        _cents(fees.group(1)) if fees else None,
        _cents(fees.group(2)) if fees else None,
    )


def next_page_target(html: str, grid: str = "gdvPermitList") -> str:
    """The ``__doPostBack`` target of a grid's "Next >" link, or "" on the last page."""
    for target, label in re.findall(
        r"__doPostBack\((?:&#39;|')([^'&]+)(?:&#39;|'),(?:&#39;|')(?:&#39;|')\)\"?>\s*([^<]*)<", html
    ):
        if grid in target and unescape(label).strip().startswith("Next"):
            return target
    return ""


@dataclass(frozen=True)
class Inspection:
    """One completed inspection on the record."""

    when: date | None
    kind: str
    result: str


def parse_inspections(html: str) -> tuple[Inspection, ...]:
    """The completed inspections grid on a record page; empty when the page says there are none."""
    match = re.search(r'id="ctl00_PlaceHolderMain_InspectionList_gvListCompleted"[\s\S]*?</table>', html)
    if match is None or "no completed inspections" in match.group(0).lower():
        return ()
    found: list[Inspection] = []
    for row in re.findall(r"<tr\b[^>]*>([\s\S]*?)</tr>", match.group(0)):
        text = _text(row)
        day = re.search(r"\d{1,2}/\d{1,2}/\d{4}", text)
        if day is None:
            continue
        rest = text.replace(day.group(0), "").strip()
        result = next((word for word in ("Approved", "Denied", "Cancelled", "Partial", "Passed", "Failed") if word.lower() in rest.lower()), "")
        found.append(Inspection(_mdy(day.group(0)), rest[:160], result))
    return tuple(found)


def parse_record_status(html: str) -> tuple[str, str]:
    """(record type, record status) from a record page's heading: ``Record COM-2616861: Commercial Repair-Maintenance
    Record Status: Ready-to-Issue``."""
    text = re.sub(r"\s+", " ", _plain(html))
    match = re.search(r"Record\s+[A-Z]{2,5}-\d{5,}\s*:\s*(.+?)\s+Record Status:\s*(.+?)\s+(?:Add to collection|Record Info)", text)
    return (match.group(1).strip(), match.group(2).strip()) if match else ("", "")


def attach_caps(permits: tuple[Permit, ...], html: str, module: Module) -> tuple[Permit, ...]:
    """Fill ``cap`` on CSV rows whose permit number is linked on the grid."""
    by_number = {row.number: row for row in permits_from_html(html, module)}
    attached: list[Permit] = []
    for permit in permits:
        grid = by_number.get(permit.number)
        if grid is None:
            attached.append(permit)
            continue
        attached.append(replace(permit, cap=grid.cap, opened=permit.opened or grid.opened))
    return tuple(attached)


def parse_fees(html: str, *, paid: bool) -> tuple[Fee, ...]:
    """Invoice rows in a fee table. An empty ``d`` is no fees."""
    if not html.strip():
        return ()
    found: list[Fee] = []
    for row in re.findall(r'<tr class="ACA_TabRow_(?:Odd|Even)[^"]*">([\s\S]*?)</tr>', html):
        cells = [_text(cell) for cell in re.findall(r"<td\b[^>]*>([\s\S]*?)</td>", row)]
        cells = [cell for cell in cells if cell]
        if len(cells) < 3 or _mdy(cells[0]) is None:
            continue
        found.append(Fee(paid, _mdy(cells[0]), cells[1], _cents(cells[2])))
    return tuple(found)


def fee_pages(html: str) -> int:
    """The last page of a fee table: the highest ``changePage('n')`` in its pager, 1 when there is none."""
    return max((int(n) for n in re.findall(r"changePage\((?:'|&#39;)(\d+)", html)), default=1)


def fee_total(html: str) -> int | None:
    """``Total paid fees: $549.81`` or ``Total outstanding fees: $0.00`` under a fee table."""
    match = re.search(r"Total (?:paid|outstanding) fees:\s*\$([\d,]+\.\d{2})", _text(html))
    return _cents(match.group(1)) if match else None


def parse_tasks(html: str) -> tuple[ReviewTask, ...]:
    """Processing tasks. Each task is the cell before its "Marked as" lines."""
    if not html.strip():
        return ()
    tasks: list[ReviewTask] = []
    for part in re.split(r"width='770px'\s*>", html)[1:]:
        name = unescape(part.split("</td>", 1)[0]).strip()
        marks = tuple(
            ReviewMark(unescape(status).strip(), _mdy(when), unescape(who).strip())
            for status, when, who in _MARK.findall(part)
        )
        if name:
            tasks.append(ReviewTask(name, marks))
    return tuple(tasks)


def parse_related(html: str) -> tuple[RelatedRecord, ...]:
    """Rows of ``tableCapTreeList``. ``depth`` counts the ``_001_001`` name."""
    if not html.strip():
        return ()
    parts = re.split(r'<tr name="(_\d+(?:_\d+)*)"', html)
    found: list[RelatedRecord] = []
    pairs = iter(parts[1:])
    for name, chunk in zip(pairs, pairs):
        number = re.search(r">\s*([A-Z][A-Z0-9]{1,5}-\d+)\s*<", chunk)
        if number is None:
            continue
        cells = re.findall(
            r"</table></td>\s*<td[^>]*>\s*([^<]*)\s*</td>\s*<td[^>]*>\s*([^<]*)\s*</td>",
            chunk,
        )
        record_type, project = ("", "")
        if cells:
            record_type, project = cells[0][0].strip(), cells[0][1].strip()
        opened = re.search(r'class="ACA_NShot">\s*(\d{2}/\d{2}/\d{4})', chunk)
        found.append(
            RelatedRecord(
                number.group(1),
                unescape(record_type),
                unescape(project).strip(),
                _mdy(opened.group(1) if opened else ""),
                _cap_in(chunk, Module.BUILDING),
                name.count("_"),
            )
        )
    return tuple(found)


def parse_conditions(html: str) -> tuple[Condition, ...]:
    """Conditions of the record. The status line is ``Applied | Required | date``."""
    found: list[Condition] = []
    for match in re.finditer(r'lblGeneralConditionsInfo"[^>]*>([\s\S]*?)</span>', html):
        divs = [
            _text(piece)
            for piece in re.findall(r"<div\b[^>]*>([\s\S]*?)</div>", match.group(1))
        ]
        divs = [piece for piece in divs if piece]
        if not divs:
            continue
        prefix = html[: match.start()]
        status_line = divs[-1] if len(divs) > 1 else ""
        parts = [part.strip() for part in status_line.split("|")] if "|" in status_line else []
        while len(parts) < 3:
            parts.append("")
        found.append(
            Condition(
                group=_last_label(prefix, "lblGeneralConditionsGroupName"),
                kind=_last_label(prefix, "lblGeneralConditionsType"),
                name=divs[0],
                comment=divs[1] if len(divs) > 2 else "",
                status=parts[0],
                severity=parts[1],
                applied=_mdy(parts[2]),
            )
        )
    return tuple(found)


def parse_reports(html: str) -> tuple[Report, ...]:
    """Print/View Record links on the record page."""
    found: list[Report] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"print_onclick\(&#39;(?P<url>[^'&]*ReportParameter\.aspx\?[^']+?)&#39;(?P<rest>[^>]*)>",
        re.I,
    )
    for match in pattern.finditer(html):
        url = unescape(match.group("url"))
        query = parse_qs(url.split("?", 1)[-1])
        report_id = (query.get("reportID") or [""])[0]
        if not report_id or report_id in seen:
            continue
        seen.add(report_id)
        titles = re.findall(r'title="([^"]*)"', match.group("rest"))
        found.append(
            Report(
                unescape(titles[0]).strip() if titles else "",
                (query.get("reportType") or [""])[0],
                report_id,
            )
        )
    return tuple(found)


def parse_documents(html: str) -> tuple[Document, ...]:
    """Rows of the attachment list. ``number`` is the document number."""
    found: list[Document] = []
    for piece in html.split('lblFileName">')[1:]:
        name, _, rest = piece.partition("</span>")
        number = re.search(r"ViewDocumentDetails\(\s*'[^']*'\s*,\s*'(\d+)'", rest)
        found.append(
            Document(
                name=unescape(name).strip(),
                number=number.group(1) if number else "",
                kind=_label(rest, "lblType"),
                size=_label(rest, "lblSize"),
                uploaded=_mdy(_label(rest, "lblUploadDate")),
                record_number=_label(rest, "lblRecordNumber"),
            )
        )
    return tuple(found)


def parse_parcel(html: str) -> ParcelInfo | None:
    """Parcel detail labels and the address list."""
    lines = [line.strip() for line in _plain(html).splitlines() if line.strip()]
    values = {key: "" for key in _PARCEL_LABELS.values()}
    label_lines = set(_PARCEL_LABELS)
    for index, line in enumerate(lines):
        key = _PARCEL_LABELS.get(line)
        if key is None or index + 1 >= len(lines):
            continue
        nxt = lines[index + 1]
        if nxt not in label_lines and not nxt.endswith(":"):
            values[key] = nxt
    addresses = tuple(
        re.sub(r"\s+", " ", unescape(item)).strip()
        for item in re.findall(r"lbAddress[\s\S]*?<strong>\s*([^<]+?)\s*</strong>", html)
    )
    if not values["number"] and not addresses:
        return None
    return ParcelInfo(
        values["number"],
        values["lot"],
        values["block"],
        values["subdivision"],
        values["area"],
        values["zoning"],
        addresses,
    )


def parse_parcel_grid(html: str) -> tuple[ParcelHit, ...]:
    """Parcel-number rows. Opening one posts ``target``."""
    found: list[ParcelHit] = []
    pattern = re.compile(
        r"PostBackOptions\(&quot;(ctl00\$PlaceHolderMain\$RefParcelLookUpList\$dgvRefParcelLookUpList\$ctl\d+\$lbParcelNumber)&quot;"
        r"[\s\S]*?<strong>\s*([^<]+?)\s*</strong>"
        r"[\s\S]*?lblLot\">([^<]*)</span>"
        r"[\s\S]*?lblBlock\">([^<]*)</span>"
    )
    for target, number, lot, block in pattern.findall(html):
        found.append(ParcelHit(unescape(number).strip(), lot=unescape(lot).strip(), block=unescape(block).strip(), target=target))
    return tuple(found)


def parse_parcel_links(html: str) -> tuple[ParcelHit, ...]:
    """``ParcelDetail.aspx`` links on a multi-parcel result."""
    found: list[ParcelHit] = []
    seen: set[tuple[str, str]] = set()
    for match in re.finditer(r"ParcelDetail\.aspx\?([^\"']+)", html):
        hit = _hit_from_query(match.group(1))
        if hit is None or (hit.number, hit.seq) in seen:
            continue
        seen.add((hit.number, hit.seq))
        found.append(hit)
    return tuple(found)


def parse_addresses(html: str) -> tuple[AddressHit, ...]:
    """Address rows. A parcel detail row includes the parcel number; a search row may not."""
    found: list[AddressHit] = []
    seen: set[str] = set()
    for parcel_number, address in re.findall(
        r'lblParcelNumber">([^<]*)</span>[\s\S]{0,900}?lbAddress[\s\S]*?<strong>\s*([^<]+?)\s*</strong>',
        html,
    ):
        text = re.sub(r"\s+", " ", unescape(address)).strip()
        if text and text not in seen:
            seen.add(text)
            found.append(AddressHit(unescape(parcel_number).strip(), text))
    for address in re.findall(
        r"lblFullAddress&quot;[\s\S]{0,500}?<strong>\s*([^<]+?)\s*</strong>",
        html,
    ):
        text = re.sub(r"\s+", " ", unescape(address)).strip()
        if text and text not in seen:
            seen.add(text)
            found.append(AddressHit("", text))
    return tuple(found)


def parse_collections(html: str) -> tuple[Collection, ...]:
    """Links to ``MyCollectionDetail.aspx``."""
    found: list[Collection] = []
    for collection_id, inner in re.findall(
        r'href="[^"]*MyCollectionDetail\.aspx\?collectionId=(\d+)"[^>]*>([\s\S]*?)</a>',
        html,
    ):
        name = _text(inner)
        found.append(Collection(collection_id, name))
    return tuple(found)


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.fields: dict[str, str] = {}
        self._select: str | None = None
        self._options: list[str] = []
        self._selected: str | None = None
        self._option: str | None = None
        self._textarea: str | None = None
        self._textarea_data: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value for key, value in attrs}
        if tag == "input":
            name = attr.get("name")
            if not name or "disabled" in attr:
                return
            kind = (attr.get("type") or "").lower()
            if kind in {"submit", "button", "image", "reset"}:
                return
            if kind in {"checkbox", "radio"}:
                if "checked" in attr:
                    self.fields[name] = attr.get("value") or "on"
                return
            self.fields[name] = attr.get("value") or ""
        elif tag == "select":
            self._select = attr.get("name")
            self._options = []
            self._selected = None
        elif tag == "option" and self._select:
            self._option = attr.get("value") or ""
            self._options.append(self._option)
            if "selected" in attr:
                self._selected = self._option
        elif tag == "textarea":
            self._textarea = attr.get("name")
            self._textarea_data = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "select" and self._select:
            if self._selected is not None:
                self.fields[self._select] = self._selected
            elif self._options:
                self.fields[self._select] = self._options[0]
            self._select = None
        elif tag == "textarea" and self._textarea:
            self.fields[self._textarea] = "".join(self._textarea_data)
            self._textarea = None

    def handle_data(self, data: str) -> None:
        if self._textarea is not None:
            self._textarea_data.append(data)


def _apply_record_query(form: dict[str, str], query: RecordQuery) -> None:
    for name, field in _RECORD_FIELDS.items():
        form[field] = getattr(query, name)
    if query.start is not None:
        form["ctl00$PlaceHolderMain$generalSearchForm$txtGSStartDate"] = query.start.strftime("%m/%d/%Y")
    if query.end is not None:
        form["ctl00$PlaceHolderMain$generalSearchForm$txtGSEndDate"] = query.end.strftime("%m/%d/%Y")


def _form_headers(referer: str) -> dict[str, str]:
    return {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": referer,
    }


def _fee_paid_body(cap: CapId, page: int = 1) -> dict:
    return {
        "pageNum": page,
        "moduleName": cap.module,
        "reportName": "",
        "receiptNbr": "",
        "reportID": "0",
        "displayReceiptReport": False,
    }


def _cap_home(module: Module) -> str:
    query = urlencode(
        {
            "module": module.value,
            "TabName": module.value,
            "TabList": _TAB_LIST + _TAB_INDEX[module],
        }
    )
    return f"{_ROOT}/Cap/CapHome.aspx?{query}"


def _apo_url() -> str:
    query = urlencode({"TabName": "APO", "TabList": _TAB_LIST + "4"})
    return f"{_ROOT}/APO/APOLookup.aspx?{query}"


def _attachments_url(cap: CapId) -> str:
    query = urlencode(
        {
            "iframeid": "ctl00_PlaceHolderMain_attachmentEdit",
            "module": cap.module,
            "isInConfirm": "False",
            "isdetail": "True",
            "isaccountmanager": "False",
            "isAdmin": "False",
            "isPeopleDocument": "",
            "agencyCode": cap.agency,
            "isForConditionDocument": "N",
        }
    )
    return f"{_ROOT}/FileUpload/AttachmentsList.aspx?{query}"


def _detail_url(cap: CapId) -> str:
    query = urlencode(
        {
            "Module": cap.module,
            "TabName": cap.module,
            "capID1": cap.id1,
            "capID2": cap.id2,
            "capID3": cap.id3,
            "agencyCode": cap.agency,
            "IsToShowInspection": "",
        }
    )
    return f"{_ROOT}/Cap/CapDetail.aspx?{query}"


def _is_html_document(body: str) -> bool:
    head = body.lstrip()[:20].lower()
    return head.startswith("<!doctype") or head.startswith("<html") or head.startswith("<form") or head.startswith("<input")


def _absolute(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if path.startswith("/"):
        return _ORIGIN + path
    return _ROOT + "/" + path


def _hit_from_query(raw: str) -> ParcelHit | None:
    query = parse_qs(unescape(raw.replace("&amp;", "&")).split("?", 1)[-1])
    number = (query.get("ParcelNum") or [""])[0]
    if not number:
        return None
    return ParcelHit(number, (query.get("ParcelSeq") or [""])[0])


def _cap_in(html: str, module: Module) -> CapId | None:
    match = _CAP.search(html)
    if match is None:
        return None
    return CapId(
        unquote(match.group(1)),
        unquote(match.group(2)),
        unquote(match.group(3)),
        agency=unquote(match.group(4) or "SACRAMENTO"),
        module=_module_in(html, module).value,
    )


def _module_in(html: str, default: Module) -> Module:
    match = _MODULE.search(html)
    if match is None:
        return default
    value = unquote(match.group(1))
    for module in Module:
        if module.value.lower() == value.lower():
            return module
    return default


def _label(html: str, ident: str) -> str:
    match = re.search(rf'{ident}">\s*([^<]*)', html)
    return unescape(match.group(1)).strip() if match else ""


def _last_label(html: str, ident: str) -> str:
    found = re.findall(rf'{ident}"[^>]*>\s*([^<]+)', html)
    return unescape(found[-1]).strip() if found else ""


def _nearby_date(html: str) -> str:
    match = re.search(r'lblUpdatedTime"[^>]*>\s*(\d{2}/\d{2}/\d{4})', html)
    return match.group(1) if match else ""


def _mdy(value: str) -> date | None:
    text = value.strip()
    if not text:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _cents(value: str) -> int:
    cleaned = value.replace("$", "").replace(",", "").strip()
    negative = cleaned.startswith("-") or cleaned.startswith("(")
    cleaned = cleaned.strip("()")
    if cleaned.startswith("-"):
        cleaned = cleaned[1:]
    dollars, _, fraction = cleaned.partition(".")
    if not dollars and not fraction:
        return 0
    amount = int(dollars or "0") * 100 + int((fraction + "00")[:2])
    return -amount if negative else amount


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def _plain(html: str) -> str:
    text = re.sub(r"(?is)<(br|tr|div|p|li|h1|td|th)[^>]*>", "\n", html)
    return unescape(re.sub(r"<[^>]+>", "", text))


def _live_fetch():
    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))

    def fetch(method: str, url: str, body: str | None, headers: dict[str, str]):
        sent = {"User-Agent": "jason SacramentoCitizenAccess", "Accept": "*/*"}
        sent.update(headers)
        data = body.encode("utf-8") if body is not None else None
        request = Request(url, data=data, headers=sent, method=method)
        with opener.open(request, timeout=60) as response:
            return response.status, response.read(), {key: value for key, value in response.headers.items()}

    return fetch
