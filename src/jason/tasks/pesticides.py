"""Fetch each pesticide the vendor applied: EPA's registration, California's, the stamped label, and the safety data sheet.

For every product in the vendor portal's record (``jason vendors --sync``), under
``data/pesticides/<EPA key>/``:

- ``product.json``: EPA's record (the PPLS API: registrant, status, signal word, restricted use,
  active ingredients, the newest stamped label), California's (CalPEST: the registration the vendor
  recorded, its status and first date), where each document came from, and the SDS reading;
- ``label-epa-<date>.pdf``: the newest label EPA stamped as accepted;
- ``sds.pdf`` and ``label-specimen.pdf``: the manufacturer's current safety data sheet and specimen
  label (CDMS's library, or the manufacturer's own link), kept only when the sheet names the product.

The public APIs need no key. Nothing is sent but the registration number or the product name.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from jason.community.pesticides import EpaNumber, Registration, document_source, names_product, read_sds

PESTICIDES_DIR = "pesticides"
PPLS = "https://ordspub.epa.gov/ords/pesticides/cswu/ppls/{epa}"
EPA_LABEL = "https://www3.epa.gov/pesticides/chem_search/ppls/{file}"
CALPEST = "https://cdpr-ms-calpest-processing.azurewebsites.net/api/calpestsearch"
CDMS_PRODUCTS = "https://www.cdms.net/LabelsSDS/Home/ProductList"
CDMS_DOCUMENTS = "https://www.cdms.net/LabelsSDS/Home/DocumentList"
CDMS_FILE = "https://www.cdms.net/ldat/{file}"
USER_AGENT = "Mozilla/5.0 (jason HOA agent; pesticide label lookup)"


def pesticide_root(data_dir: Path) -> Path:
    return Path(data_dir) / PESTICIDES_DIR


def applied_products(data_dir: Path, portal: Any) -> list[tuple[str, str]]:
    """Each (product, EPA number as recorded) the vendor applied, from its chemical report and visit records."""
    from jason.tasks.vendor_portals import load_accounts

    found: dict[str, str] = {}
    for account in load_accounts(data_dir, portal.key):
        for app in account["applications"]:
            found.setdefault(app["product"], app["epa_number"])
        for visit in account["services"]:
            for product in visit["products"]:
                if product["epa_number"] and not found.get(product["name"]):
                    found[product["name"]] = product["epa_number"]
    return sorted(found.items())


@dataclass
class FetchResult:
    products: list[str] = field(default_factory=list)
    downloaded: int = 0
    present: int = 0
    skipped: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def summary(self) -> str:
        text = (f"{len(self.products)} products: {self.downloaded} documents downloaded, {self.present} on disk; "
                f"skipped {', '.join(self.skipped) or 'none'}")
        return text + "".join(f"\n  {p}" for p in self.problems)


def _pdf(http: httpx.Client, url: str) -> bytes:
    response = http.get(url)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise ValueError(f"not a PDF: {url}")
    return response.content


def _text(pdf: bytes) -> str:
    import pymupdf

    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


def _cdms_documents(http: httpx.Client, manufacturer: int, number: EpaNumber, product: str) -> tuple[dict | None, dict | None, str]:
    """(newest English SDS, newest specimen label, CDMS product name) for the product CDMS lists under this EPA number."""
    rows = http.get(CDMS_PRODUCTS, params={"manId": manufacturer}).json().get("Lst", [])
    candidates = [r for r in rows if (r.get("EPA") or "").strip() == number.epa]
    if not candidates:
        return None, None, ""
    chosen = next((r for r in candidates if names_product(r.get("Name") or "", product)), candidates[0])
    docs = http.get(CDMS_DOCUMENTS, params={"productId": chosen["Id"]}).json().get("Lst", [])

    def newest(kind: str) -> dict | None:
        rows = [d for d in docs if d.get("DocType") == kind and "en" in (d.get("LanguageCodes") or ["en"])
                and "espa" not in (d.get("Description") or "").lower()]
        dated = lambda d: (re.search(r"(\d{4}/\d{2}/\d{2})", d.get("Description") or "") or [None, ""])[1]  # noqa: E731
        return max(rows, key=lambda d: (dated(d), d.get("DocId") or 0)) if rows else None

    return newest("SDS"), newest("Specimen Label"), str(chosen.get("Name") or "")


def fetch_product(http: httpx.Client, root: Path, product: str, raw: str, *, refresh: bool = False) -> tuple[dict, int, int, list[str]]:
    number = EpaNumber.parse(raw)
    folder = root / number.key
    folder.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {"product": product, "recorded": raw, "epa": number.epa, "california": number.california,
                              "exempt": number.exempt, "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    downloaded = present = 0
    problems: list[str] = []

    def save(name: str, url: str) -> str:
        nonlocal downloaded, present
        path = folder / name
        if path.is_file() and not refresh:
            present += 1
            return path.name
        path.write_bytes(_pdf(http, url))
        downloaded += 1
        return path.name

    if number.registered:
        try:
            items = http.get(PPLS.format(epa=number.epa)).json().get("items") or []
            if items:
                registration = Registration.from_ppls(items[0])
                record["registration"] = asdict(registration)
                if registration.label_file:
                    stamp = registration.label_date.isoformat() if registration.label_date else "undated"
                    record["labelFile"] = save(f"label-epa-{stamp}.pdf", EPA_LABEL.format(file=registration.label_file))
            else:
                problems.append(f"{product}: EPA has no product {number.epa}")
        except (httpx.HTTPError, ValueError) as exc:
            problems.append(f"{product}: EPA lookup failed ({exc})")
        try:
            try:
                rows = http.post(CALPEST, json={"type": 5, "registrationnumber": number.epa}).json() or []
            except httpx.TimeoutException:
                # CalPEST's search is slow on a cold start; one retry.
                rows = http.post(CALPEST, json={"type": 5, "registrationnumber": number.epa}, timeout=120.0).json() or []
            wanted = number.california if number.california_code else ""
            ca = next((r for r in rows if r.get("registrationnumber") == wanted), None) if wanted else None
            ca = ca or next((r for r in rows if (r.get("status") or "").lower() == "active"), rows[0] if rows else None)
            if ca:
                record["californiaRegistration"] = {"number": ca.get("registrationnumber"), "name": ca.get("name"),
                                                    "status": ca.get("status"), "first": (ca.get("firstregistrationdate") or "")[:10],
                                                    "inactivated": (ca.get("inactivationdate") or "")[:10] or None,
                                                    "all": [{"number": r.get("registrationnumber"), "name": r.get("name"),
                                                             "status": r.get("status")} for r in rows]}
            else:
                problems.append(f"{product}: no California registration for {number.epa}")
        except (httpx.HTTPError, ValueError) as exc:
            problems.append(f"{product}: CalPEST lookup failed ({exc})")

    source = document_source(number, product)
    if source is None:
        problems.append(f"{product}: no known source for its safety data sheet")
    else:
        try:
            sds_url = label_url = ""
            if source.cdms:
                sds, label, listed = _cdms_documents(http, source.cdms, number, product)
                record["cdmsProduct"] = listed
                if sds:
                    sds_url = CDMS_FILE.format(file=sds["FileName"])
                    record["sdsListed"] = sds.get("Description")
                if label:
                    label_url = CDMS_FILE.format(file=label["FileName"])
            else:
                sds_url, label_url = source.sds, source.label
            if label_url:
                record["specimenLabelFile"] = save("label-specimen.pdf", label_url)
            if sds_url:
                record["sdsSource"] = sds_url
                record["sdsFile"] = save("sds.pdf", sds_url)
                reading = read_sds(_text((folder / "sds.pdf").read_bytes()))
                record["sds"] = asdict(reading)
                if reading.product and not names_product(reading.product, product):
                    problems.append(f"{product}: the safety data sheet names {reading.product!r}")
                    record["sdsNamesAnotherProduct"] = reading.product
            else:
                problems.append(f"{product}: no safety data sheet listed")
        except (httpx.HTTPError, ValueError) as exc:
            problems.append(f"{product}: document download failed ({exc})")
    (folder / "product.json").write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
    return record, downloaded, present, problems


def fetch_products(data_dir: Path, portal: Any, *, refresh: bool = False, http: httpx.Client | None = None,
                   log: Callable[[str], None] | None = None) -> FetchResult:
    """Every product the vendor applied, fetched into ``data/pesticides``. A trap or an unnumbered device is skipped."""
    root = pesticide_root(data_dir)
    result = FetchResult()
    client = http or httpx.Client(timeout=60.0, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    try:
        for product, raw in applied_products(data_dir, portal):
            number = EpaNumber.parse(raw)
            if not number.registered and not number.exempt:
                result.skipped.append(product)
                continue
            _record, downloaded, present, problems = fetch_product(client, root, product, raw, refresh=refresh)
            result.products.append(product)
            result.downloaded += downloaded
            result.present += present
            result.problems.extend(problems)
            if log:
                log(f"{product}: {downloaded} new, {present} on disk" + (f"; {len(problems)} problem(s)" if problems else ""))
    finally:
        if http is None:
            client.close()
    return result


def load_product(data_dir: Path, raw: str, product: str = "") -> dict[str, Any] | None:
    """The fetched record for a product, by the EPA number the vendor recorded."""
    path = pesticide_root(data_dir) / EpaNumber.parse(raw).key / "product.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


__all__ = ["fetch_products", "fetch_product", "applied_products", "load_product", "pesticide_root", "FetchResult"]
