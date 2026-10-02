"""Sacramento County property tax.

The public search is the Algolia index ``ca-sacramento.gsgx_property_tax``
on county-taxes.net. A hit's ``objectID`` is a GovHub payable path. That
GET returns the account amount, assessee, and owner period. Bill numbers
are the hit's child external ids. The account page links to each year's
bill, and that page lists the assessed value, the ad valorem levies, and
the flat direct charges.

The countywide levy is 1% of the net assessed value, and the other ad
valorem lines are a rate times that same value. Direct charges are dollar
amounts printed on the bill. They are not a percent of the sale price, and
they are not the same amount every year: each district sets its own.
``tax_split`` separates the two. ``direct_levies`` lines the charges up by
code, and ``follows_reassessment`` reports whether a charge scaled in a year
the enrolled value rose by more than the 2% factor. Login, cart, and
payment are a separate signed-in session and are not this client.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from html import unescape
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

SEARCH_URL = "https://ng9exqz0n7-dsn.algolia.net/1/indexes/*/queries"
APP_ID = "NG9EXQZ0N7"
# Search-only key shipped in the county-taxes.net page.
SEARCH_KEY = "abcfc8d1257b9d1e89d663fffe26b4ec"
INDEX = "ca-sacramento.gsgx_property_tax"
PAYABLE_URL = "https://govhub.com/svc/payables/v0/"
PAGE_URL = (
    "https://county-taxes.net/iframe-taxsys/"
    "sacramento-ca.county-taxes.com/govhub/property-tax/"
)
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
)

_YEAR = re.compile(r"^(\d{4})\b")
_BILL_HEADING = re.compile(r"(\d{4}) Secured Annual Bill #(\d+)", re.I)
_ROW = re.compile(r"<tr\b[^>]*>([\s\S]*?)</tr>", re.I)
_CELL = re.compile(r"<t[dh]\b[^>]*>([\s\S]*?)</t[dh]>", re.I)
_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class TaxLevy:
    """One line on a secured bill.

    ``kind`` is ``ad_valorem`` or ``direct``. ``rate_e8`` is the printed
    percent times 100,000,000, so 1.00000000% is 100000000. Direct charges
    have a code and no rate.
    """

    kind: str
    name: str
    amount_cents: int
    rate_e8: int | None = None
    taxable_cents: int | None = None
    code: str = ""


@dataclass(frozen=True)
class TaxBill:
    """One secured bill. Valuation and levies come from the bill page."""

    number: str
    name: str
    year: int | None = None
    land_cents: int | None = None
    improvement_cents: int | None = None
    fixture_cents: int | None = None
    personal_property_cents: int | None = None
    homeowner_exemption_cents: int | None = None
    other_exemption_cents: int | None = None
    net_assessed_cents: int | None = None
    tax_rate_area: str = ""
    rate_e8: int | None = None
    ad_valorem_cents: int | None = None
    direct_cents: int | None = None
    total_cents: int | None = None
    payments_cents: int | None = None
    balance_cents: int | None = None
    levies: tuple[TaxLevy, ...] = ()
    pdf_path: str = ""
    pdf_sha256: str = ""


@dataclass(frozen=True)
class TaxAccount:
    """One property-tax account. ``path`` is the GovHub payable object id."""

    apn: str
    address: str
    path: str
    kind: str = ""
    public_url: str = ""
    bills: tuple[TaxBill, ...] = ()
    amount_cents: int | None = None
    assessee: str = ""
    description: str = ""


class SacramentoCountyTax:
    """Sacramento County Tax Collector. Search: county-taxes.net. Payable: govhub.com."""

    name = "Sacramento"

    def search(self, query: str, *, fetch=None) -> tuple[TaxAccount, ...]:
        """Accounts matching an address or a parcel number."""
        poster = _search_post if fetch is None else fetch
        return accounts(poster(_search_url(), _search_body(query)))

    def account(self, apn: str, *, fetch=None, payable_fetch=None) -> TaxAccount | None:
        """The account for this parcel, with the GovHub amount and assessee filled in.

        ``fetch`` replaces the search POST. ``payable_fetch`` replaces the payable GET.
        A search miss stays a miss.
        """
        number = parcel_number(apn)
        digits = _digits(number)
        match = next((row for row in self.search(number, fetch=fetch) if _digits(row.apn) == digits), None)
        if match is None:
            return None
        try:
            return self.payable(match, fetch=payable_fetch)
        except Exception:
            if payable_fetch is not None:
                raise
            return match

    def payable(self, account: TaxAccount, *, fetch=None) -> TaxAccount:
        """Copy amount, assessee, and description from the GovHub payable onto ``account``."""
        if not account.path:
            return account
        getter = _payable_get if fetch is None else fetch
        payload = getter(_payable_url(account.path))
        if not payload:
            return account
        params = payload.get("custom_parameters") or {}
        return replace(
            account,
            amount_cents=_cents(payload.get("amount")),
            assessee=str(params.get("assessee") or ""),
            description=str(payload.get("description") or ""),
        )

    def statements(
        self,
        account: TaxAccount,
        *,
        fetch=None,
        bills_dir: str | Path | None = None,
        pdf_fetch=None,
    ) -> TaxAccount:
        """Fill each bill with the assessed value, levy lines, and print PDF.

        ``fetch`` replaces the HTML GET. ``pdf_fetch`` replaces the print GET
        and returns the PDF bytes. ``bills_dir`` is where those files are
        written, one directory per parcel. An account page with no bill links
        leaves the search bills as they are. One bill page that fails does
        not drop the bills that loaded.
        """
        if not account.path:
            return account
        getter = _page_get if fetch is None else fetch
        links = bill_links(getter(account_page(account.path)) or "")
        parsed: list[TaxBill] = []
        for link in links:
            try:
                page_url = bill_page(link)
                bill = parse_bill(getter(page_url) or "")
            except Exception:
                continue
            if not bill.number:
                continue
            if bills_dir is not None:
                bill = _attach_pdf(Path(bills_dir), account.apn, page_url, bill, pdf_fetch)
            parsed.append(bill)
        if not parsed:
            return account
        return replace(account, bills=_merge(account.bills, tuple(parsed)))


def account_page(path: str) -> str:
    """Iframe URL for the account summary. The path's item key is the base64 token."""
    key = path.split("/items/", 1)[-1].strip("/")
    token = base64.b64encode(key.encode("utf-8")).decode("ascii")
    return PAGE_URL + token


def bill_pdf_dest(bills_dir: str | Path, apn: str, bill: TaxBill) -> Path:
    """``{parcel}/{year}-{bill number}.pdf`` under the tax bill directory."""
    year = str(bill.year) if bill.year else "supplemental"
    return Path(bills_dir) / parcel_number(apn) / f"{year}-{bill.number}.pdf"


def bill_page(url: str) -> str:
    """Iframe URL for a bill. The public ``/sacramento/property-tax`` link redirects through a session check."""
    if "/iframe-taxsys/" in url:
        return url
    tail = url.split("/property-tax/", 1)[-1]
    return PAGE_URL + tail


def bill_links(html: str) -> tuple[str, ...]:
    """Bill page URLs on an account summary, newest first, without print links."""
    found: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"""href=['"]([^'"]+)['"]""", html or "", re.I):
        url = match.group(1).split("#", 1)[0].split("?", 1)[0]
        if not re.search(r"/bills/[0-9A-Fa-f-]{36}$", url):
            continue
        if url in seen:
            continue
        seen.add(url)
        found.append(url)
    return tuple(found)


def parse_bill(html: str) -> TaxBill:
    """Assessed value, ad valorem lines, and direct charges from one bill page."""
    plain = " ".join(unescape(_TAG.sub(" ", html or "")).replace("\u200d", " ").split())
    heading = _BILL_HEADING.search(plain)
    year = int(heading.group(1)) if heading else None
    number = heading.group(2) if heading else ""
    name = f"{year} Secured Annual Bill #{number}" if year and number else ""
    rows = _rows(html or "")
    assessed = _after_header(rows, "Net Assessed Value")
    levies: list[TaxLevy] = []
    levies.extend(_ad_valorem(rows))
    levies.extend(_direct(rows))
    labeled = {label: _labeled(html or "", label) for label in (
        "Tax Rate Area:",
        "Tax Rate:",
        "Fixtures:",
        "homeowners exemption:",
        "other exemption:",
    )}
    return TaxBill(
        number=number,
        name=name,
        year=year,
        land_cents=_cell_money(assessed, 0),
        improvement_cents=_cell_money(assessed, 1),
        fixture_cents=_money(labeled["Fixtures:"]),
        personal_property_cents=_cell_money(assessed, 2),
        homeowner_exemption_cents=_money(labeled["homeowners exemption:"]),
        other_exemption_cents=_money(labeled["other exemption:"]),
        net_assessed_cents=_cell_money(assessed, 4),
        tax_rate_area=labeled["Tax Rate Area:"],
        rate_e8=_rate_e8(labeled["Tax Rate:"]),
        ad_valorem_cents=_row_amount(rows, "Total Ad Valorem Taxes"),
        direct_cents=_row_amount(rows, "Total Direct Charges and Special Assessments"),
        total_cents=_row_amount(rows, "Total"),
        payments_cents=_row_amount(rows, "Total payments made"),
        balance_cents=_row_amount(rows, "Balance due"),
        levies=tuple(levies),
    )


@dataclass(frozen=True)
class TaxSplit:
    """One bill, divided into the tax that follows value and the direct charges."""

    year: int | None
    enrolled_cents: int | None
    net_cents: int | None
    price_cents: int
    fixed_cents: int

    @property
    def total_cents(self) -> int:
        return self.price_cents + self.fixed_cents


@dataclass(frozen=True)
class RollRule:
    """A delinquent utility account the agency moves onto the secured tax bill as a direct charge.

    A claimant whose index name holds one of ``claimant_words`` records a
    utility lien; the delinquency then appears on the parcel's bill under
    ``code``. The bill is keyed to the parcel, so a paid bill with the
    charge settles the lien even when no termination is recorded.
    """

    code: str
    claimant_words: tuple[str, ...]
    agency: str

    def claims(self, claimant: tuple[str, ...]) -> bool:
        folded = " ".join(" ".join(name.upper().split()) for name in claimant)
        return any(word in folded for word in self.claimant_words)


@dataclass(frozen=True)
class RollCharge:
    """One delinquent-utility charge on a parcel's bill: the fiscal year, the code, the cents, and whether the bill is paid."""

    year: int
    code: str
    amount_cents: int
    paid: bool
    rule: RollRule | None = None


def roll_charges(bills, rules: tuple[RollRule, ...]) -> tuple[RollCharge, ...]:
    """The delinquent-utility charges on a parcel's bills, oldest first. A bill with no balance left is paid."""
    by_code = {rule.code: rule for rule in rules}
    found: list[RollCharge] = []
    for bill in bills:
        if bill.year is None:
            continue
        paid = bill.balance_cents is not None and bill.balance_cents <= 0 and bool(bill.total_cents)
        for levy in bill.levies:
            if levy.kind == "direct" and levy.code in by_code:
                found.append(RollCharge(bill.year, levy.code, levy.amount_cents, paid, by_code[levy.code]))
    found.sort(key=lambda charge: (charge.year, charge.code))
    return tuple(found)


@dataclass(frozen=True)
class DirectLevy:
    """One direct-charge code across the years it was billed. Amounts are ``(year, cents)``."""

    code: str
    name: str
    amounts: tuple[tuple[int, int], ...]

    @property
    def same_each_year(self) -> bool:
        """True when every billed year shows the same cents."""
        return len(self.amounts) > 1 and len({cents for _, cents in self.amounts}) == 1


@dataclass(frozen=True)
class Reassessment:
    """The latest year enrolled value rose by more than the 2% factor.

    ``enrolled_cents`` is the county base-year figure to compare to a sale price.
    It is the value the assessor enrolled, not the price on the deed.
    """

    year: int
    enrolled_cents: int
    prior_year: int
    prior_enrolled_cents: int


def reassessments(bills: tuple[TaxBill, ...] | list[TaxBill]) -> tuple[Reassessment, ...]:
    """Every year enrolled value rose by more than the 2% factor, oldest first.

    A rise of exactly 2% is the annual factor, not a sale. Supplemental bills
    without enrolled value are skipped.
    """
    enrolled: dict[int, int] = {}
    for bill in bills:
        if bill.year is None:
            continue
        value = enrolled_cents(bill)
        if value:
            enrolled[bill.year] = value
    found: list[Reassessment] = []
    years = sorted(enrolled)
    for prior, year in zip(years, years[1:]):
        if enrolled[year] * 100 <= enrolled[prior] * 102:
            continue
        found.append(Reassessment(year, enrolled[year], prior, enrolled[prior]))
    return tuple(found)


def reassessment(bills: tuple[TaxBill, ...] | list[TaxBill]) -> Reassessment | None:
    """Latest jump in enrolled value. A rise of exactly 2% is the annual factor, not a sale."""
    found = reassessments(bills)
    return found[-1] if found else None


def reassessment_year_for(recorded: date) -> int:
    """Tax year whose January 1 lien date first follows this recording.

    A deed dated January 1 is on that year's lien date. Any later day waits
    for the next January 1.
    """
    if recorded.month == 1 and recorded.day == 1:
        return recorded.year
    return recorded.year + 1


def reassessment_for(
    bills: tuple[TaxBill, ...] | list[TaxBill],
    recorded: date | None,
) -> Reassessment | None:
    """Enrolled jump that follows this recording. Blank when the catalog has none.

    The sale price is the enrolled value in that year, not the deed
    consideration. When ``recorded`` is missing, there is no match.
    """
    if recorded is None:
        return None
    target = reassessment_year_for(recorded)
    for found in reassessments(bills):
        if found.year == target:
            return found
    return None


def enrolled_cents(bill: TaxBill) -> int | None:
    """Land, improvements, fixtures, and personal property, before exemptions."""
    parts = (
        bill.land_cents,
        bill.improvement_cents,
        bill.fixture_cents,
        bill.personal_property_cents,
    )
    if all(part is None for part in parts):
        return None
    return sum(part or 0 for part in parts)


def ad_valorem_cents(net_cents: int, rate_e8: int) -> int:
    """Price-dependent tax. ``rate_e8`` is the printed percent times 100,000,000.

    100000000 is 1%, so the countywide line is one percent of the net value.
    """
    return (net_cents * rate_e8 + 5_000_000_000) // 10_000_000_000


def tax_split(bill: TaxBill) -> TaxSplit:
    """Ad valorem follows the net assessed value. Direct charges are this year's fixed levies."""
    if bill.ad_valorem_cents is None:
        price = sum(levy.amount_cents for levy in bill.levies if levy.kind == "ad_valorem")
    else:
        price = bill.ad_valorem_cents
    if bill.direct_cents is None:
        fixed = sum(levy.amount_cents for levy in bill.levies if levy.kind == "direct")
    else:
        fixed = bill.direct_cents
    return TaxSplit(bill.year, enrolled_cents(bill), bill.net_assessed_cents, price, fixed)


def direct_levies(bills: tuple[TaxBill, ...] | list[TaxBill]) -> tuple[DirectLevy, ...]:
    """Direct charges from these bills, one series per code, oldest year first."""
    order: list[str] = []
    names: dict[str, str] = {}
    amounts: dict[str, list[tuple[int, int]]] = {}
    ordered = sorted(bills, key=lambda bill: (bill.year is None, bill.year or 0, bill.number))
    for bill in ordered:
        if bill.year is None:
            continue
        for levy in bill.levies:
            if levy.kind != "direct" or not levy.code:
                continue
            if levy.code not in amounts:
                order.append(levy.code)
                amounts[levy.code] = []
            names[levy.code] = levy.name
            amounts[levy.code].append((bill.year, levy.amount_cents))
    return tuple(DirectLevy(code, names[code], tuple(amounts[code])) for code in order)


def follows_reassessment(levy: DirectLevy, bills: tuple[TaxBill, ...] | list[TaxBill]) -> bool | None:
    """Whether this charge scaled with enrolled value when that value rose past the 2% factor.

    None when these bills have no such year, or the code was not billed on both
    sides of it. A charge that stays put while the value jumps does not follow
    the sale price.
    """
    enrolled: dict[int, int] = {}
    for bill in bills:
        if bill.year is None:
            continue
        value = enrolled_cents(bill)
        if value:
            enrolled[bill.year] = value
    years = sorted(enrolled)
    by_year = dict(levy.amounts)
    seen = False
    for prior, year in zip(years, years[1:]):
        if enrolled[year] * 100 <= enrolled[prior] * 102:
            continue
        if prior not in by_year or year not in by_year:
            continue
        seen = True
        expected = by_year[prior] * enrolled[year]
        scaled = by_year[year] * enrolled[prior]
        if expected and abs(scaled - expected) * 100 <= expected * 15:
            return True
    if not seen:
        return None
    return False


def parcel_number(apn: str) -> str:
    """Dashed Sacramento parcel number. Fourteen digits become ``000-0000-000-0000``."""
    digits = _digits(apn)
    if len(digits) == 14:
        return f"{digits[0:3]}-{digits[3:7]}-{digits[7:10]}-{digits[10:14]}"
    return apn.strip()


def accounts(payload: dict | None) -> tuple[TaxAccount, ...]:
    """Read Algolia ``results[0].hits``. A null body is an empty tuple."""
    results = (payload or {}).get("results") or []
    hits = results[0].get("hits") if results and isinstance(results[0], dict) else None
    if not hits:
        return ()
    found: list[TaxAccount] = []
    for hit in hits:
        row = _account(hit)
        if row is not None:
            found.append(row)
    return tuple(found)


def _account(hit: dict) -> TaxAccount | None:
    apn = str(hit.get("external_id") or "")
    path = str(hit.get("objectID") or "")
    if not apn or not path:
        return None
    params = hit.get("custom_parameters") or {}
    return TaxAccount(
        apn=apn,
        address=str(hit.get("display_name") or ""),
        path=path,
        kind=str(params.get("external_type") or ""),
        public_url=str(params.get("public_url") or ""),
        bills=_bills(hit.get("child_groups") or []),
    )


def _bills(groups: list) -> tuple[TaxBill, ...]:
    found: list[TaxBill] = []
    for group in groups:
        for child in (group or {}).get("children") or []:
            number = str(child.get("external_id") or "")
            if not number:
                continue
            name = str(child.get("display_name") or "")
            year_match = _YEAR.match(name)
            found.append(TaxBill(number, name, int(year_match.group(1)) if year_match else None))
    return tuple(found)


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _merge(existing: tuple[TaxBill, ...], parsed: tuple[TaxBill, ...]) -> tuple[TaxBill, ...]:
    """Page order, with a search bill kept when that year was not on the page."""
    used: set[str] = set()
    merged: list[TaxBill] = []
    for bill in parsed:
        if not bill.number or bill.number in used:
            continue
        prior = next((item for item in existing if item.number == bill.number), None)
        if prior is not None and not bill.name:
            bill = replace(bill, name=prior.name, year=bill.year or prior.year)
        merged.append(bill)
        used.add(bill.number)
    for bill in existing:
        if bill.number not in used:
            merged.append(bill)
    return tuple(merged)


def _rows(html: str) -> list[list[str]]:
    found: list[list[str]] = []
    for row in _ROW.findall(html):
        cells: list[str] = []
        for cell in _CELL.findall(row):
            text = unescape(_TAG.sub(" ", cell))
            text = " ".join(text.split())
            if text:
                cells.append(text)
        if cells:
            found.append(cells)
    return found


def _after_header(rows: list[list[str]], header: str) -> list[str]:
    for index, row in enumerate(rows):
        if header in row and index + 1 < len(rows):
            return rows[index + 1]
    return []


def _ad_valorem(rows: list[list[str]]) -> list[TaxLevy]:
    return _levy_rows(rows, "Taxing authority", "ad_valorem")


def _direct(rows: list[list[str]]) -> list[TaxLevy]:
    return _levy_rows(rows, "Levying authority", "direct")


def _levy_rows(rows: list[list[str]], header: str, kind: str) -> list[TaxLevy]:
    start = next((index for index, row in enumerate(rows) if header in row), None)
    if start is None:
        return []
    found: list[TaxLevy] = []
    for row in rows[start + 1 :]:
        name = row[0]
        if name.startswith("Total"):
            break
        if kind == "ad_valorem" and len(row) >= 4:
            amount = _money(row[3])
            if amount is None:
                continue
            found.append(TaxLevy(kind, name, amount, _rate_e8(row[1]), _money(row[2])))
        elif kind == "direct" and len(row) >= 4:
            amount = _money(row[3])
            if amount is None:
                continue
            found.append(TaxLevy(kind, name, amount, code=row[1]))
    return found


def _row_amount(rows: list[list[str]], label: str) -> int | None:
    for row in rows:
        if row and row[0] == label and len(row) >= 2:
            return _money(row[-1])
    return None


def _cell_money(row: list[str], index: int) -> int | None:
    if index >= len(row):
        return None
    return _money(row[index])


def _labeled(html: str, label: str) -> str:
    pattern = (
        r"class=['\"]col label['\"][^>]*>\s*"
        + re.escape(label)
        + r"\s*</div>\s*<div class=['\"]col value['\"][^>]*>\s*([^<]+)"
    )
    match = re.search(pattern, html, re.I)
    return " ".join(match.group(1).split()) if match else ""


def _money(value) -> int | None:
    """Dollars, with or without a ``$`` and commas, as integer cents."""
    if value is None:
        return None
    return _cents(str(value).replace("$", "").replace(",", "").strip())


def _rate_e8(value: str) -> int | None:
    """Printed percent as an integer. 1.00000000% is 100000000."""
    text = str(value or "").strip().rstrip("%").strip()
    if not text or not text.replace(".", "", 1).isdigit():
        return None
    whole, _, frac = text.partition(".")
    return int(whole or "0") * 100_000_000 + int((frac + "00000000")[:8])


def _attach_pdf(
    bills_dir: Path,
    apn: str,
    page_url: str,
    bill: TaxBill,
    pdf_fetch,
) -> TaxBill:
    """Write the print PDF for this bill. A print that fails leaves the bill without a file."""
    dest = bill_pdf_dest(bills_dir, apn, bill)
    if dest.is_file() and dest.read_bytes()[:5] == b"%PDF":
        data = dest.read_bytes()
    else:
        getter = _pdf_get if pdf_fetch is None else pdf_fetch
        try:
            data = getter(page_url.rstrip("/") + "/print")
        except Exception:
            return bill
        if not isinstance(data, (bytes, bytearray)) or not bytes(data).startswith(b"%PDF"):
            return bill
        data = bytes(data)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return replace(
        bill,
        pdf_path=str(dest),
        pdf_sha256=hashlib.sha256(data).hexdigest(),
    )


def _page_get(url: str) -> str:
    """Bill HTML. The county edge rejects urllib, and curl is the client that is accepted."""
    return _curl(url, "text/html,application/xhtml+xml").decode("utf-8", "replace")


def _pdf_get(url: str) -> bytes:
    """Bill print PDF."""
    return _curl(url, "application/pdf")


def _curl(url: str, accept: str) -> bytes:
    """GET bytes. Later pages in one sync need the cookie the first response sets."""
    curl = shutil.which("curl")
    if curl is None:
        raise RuntimeError("curl is required to read a county tax bill page")
    jar = _cookie_jar()
    command = [
        curl,
        "-fsS",
        "-L",
        "--max-time",
        "60",
        "-b",
        jar,
        "-c",
        jar,
        "-A",
        _UA,
        "-H",
        f"Accept: {accept}",
        "-H",
        "Accept-Language: en-US,en;q=0.9",
        "-H",
        "Referer: https://county-taxes.net/",
        url,
    ]
    completed = _run_curl(command)
    if completed.returncode != 0:
        time.sleep(2)
        completed = _run_curl(command)
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(detail or f"tax page failed ({completed.returncode})")
    return completed.stdout


def _run_curl(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(command, capture_output=True, check=False)


def _cookie_jar() -> str:
    global _COOKIE_JAR
    if _COOKIE_JAR is None:
        _COOKIE_JAR = str(Path(tempfile.gettempdir()) / "jason-county-taxes-cookies.txt")
    return _COOKIE_JAR


_COOKIE_JAR: str | None = None


def _cents(value) -> int | None:
    """Dollars from the payable (``"7.00"`` or ``0``) as integer cents."""
    if value is None or value == "":
        return None
    text = str(value).strip()
    negative = text.startswith("-")
    text = text[1:] if negative else text
    if not text or not text.replace(".", "", 1).isdigit():
        return None
    whole, _, frac = text.partition(".")
    cents = int(whole or "0") * 100 + int((frac + "00")[:2])
    return -cents if negative else cents


def _search_url() -> str:
    query = urlencode(
        {
            "x-algolia-api-key": SEARCH_KEY,
            "x-algolia-application-id": APP_ID,
        }
    )
    return f"{SEARCH_URL}?{query}"


def _search_body(query: str) -> dict:
    return {
        "requests": [
            {
                "indexName": INDEX,
                "query": query,
                "hitsPerPage": 15,
                "attributesToRetrieve": [
                    "external_id",
                    "display_name",
                    "objectID",
                    "custom_parameters",
                    "child_groups",
                ],
                "attributesToHighlight": [],
            }
        ]
    }


def _payable_url(path: str) -> str:
    return PAYABLE_URL + quote(path.lstrip("/"), safe="")


def _search_post(url: str, body: dict) -> dict | None:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "text/plain",
            "Origin": "https://county-taxes.net",
            "Referer": "https://county-taxes.net/",
        },
    )
    return _read_json(request)


def _payable_get(url: str) -> dict | None:
    request = Request(
        url,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://county-taxes.net",
            "Referer": "https://county-taxes.net/",
        },
    )
    return _read_json(request)


def _read_json(request: Request) -> dict | None:
    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8").strip()
    if not body or body == "null":
        return None
    parsed = json.loads(body)
    return parsed if isinstance(parsed, dict) else None
