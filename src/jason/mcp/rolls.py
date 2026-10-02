"""Property-tax and secured-roll tools.

Tax search is the county's public account index. It does not download bill
pages or write the local catalog. Stored tax accounts and secured-roll rows
are read from disk. The bulk roll is the assessor's workbook. A call returns
the parcels asked for, not the whole county. Amounts are integer cents.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jason.community.secured import SecuredParcel, SecuredRoll
from jason.community.secured_store import SecuredCatalog
from jason.community.tax import (
    SacramentoCountyTax,
    TaxAccount,
    TaxBill,
    parcel_number,
    reassessments,
)
from jason.community.tax_store import TaxStore
from jason.config import Settings


def tax_status(data_dir: Path | None = None) -> dict[str, Any]:
    """How many tax accounts and bills are already stored."""
    with _taxes(_data_dir(data_dir)) as store:
        return store.counts()


def tax_account(apn: str, data_dir: Path | None = None) -> dict[str, Any]:
    """The stored tax account for one parcel, newest bill first.

    Values are the assessed figures on each bill. The latest bill also lists
    its levy lines. This does not call the tax collector.
    """
    with _taxes(_data_dir(data_dir)) as store:
        account = store.get(apn)
    if account is None:
        return {"apn": parcel_number(apn), "found": False}
    return _account(account, bills=True)


def tax_reassessments(apn: str, data_dir: Path | None = None) -> dict[str, Any]:
    """Each bill year the enrolled value rose by more than the 2% factor.

    A reassessable sale shows in the bill for the next January 1, so a deed
    recorded in 2017 is the 2018 jump and ``saleYear`` is 2017. The enrolled
    value that year is the county base-year figure, near the price but not
    the deed consideration. A jump can also be a Proposition 8 restoration.
    A transfer between affiliates, a trust restatement, or a sale near the
    factored base leaves no jump. Unit bills start in 2013. This does not
    call the tax collector.
    """
    with _taxes(_data_dir(data_dir)) as store:
        account = store.get(apn)
    if account is None:
        return {"apn": parcel_number(apn), "found": False, "jumps": []}
    years = sorted({bill.year for bill in account.bills if bill.year is not None})
    return {
        "apn": parcel_number(apn),
        "found": True,
        "firstYear": years[0] if years else None,
        "lastYear": years[-1] if years else None,
        "jumps": [
            {
                "year": item.year,
                "saleYear": item.year - 1,
                "enrolledCents": item.enrolled_cents,
                "priorYear": item.prior_year,
                "priorEnrolledCents": item.prior_enrolled_cents,
            }
            for item in reassessments(account.bills)
        ],
    }


def tax_search(query: str, limit: int = 10) -> dict[str, Any]:
    """Search the public tax index by parcel number or address.

    Each hit is an account. Bill pages are not downloaded, and nothing is
    written to the local catalog.
    """
    return _tax_search(SacramentoCountyTax(), query, limit=limit)


def secured_status(data_dir: Path | None = None, roll: str = "") -> dict[str, Any]:
    """How many secured-roll rows are stored, and where the bulk workbook is."""
    root = _data_dir(data_dir)
    path = _roll_path(root, roll)
    with _secured(root) as catalog:
        counts = catalog.counts()
    counts["workbook"] = str(path)
    counts["workbookPresent"] = path.is_file()
    return counts


def secured_parcel(apn: str, data_dir: Path | None = None) -> dict[str, Any]:
    """One stored secured-roll row. The owner can be a year behind a sale."""
    with _secured(_data_dir(data_dir)) as catalog:
        parcel = catalog.get(apn)
    if parcel is None:
        return {"apn": parcel_number(apn), "found": False}
    body = _parcel(parcel)
    body["found"] = True
    return body


def secured_search(owner: str, data_dir: Path | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Stored secured-roll rows whose owner contains this text."""
    with _secured(_data_dir(data_dir)) as catalog:
        rows = catalog.matching(owner, limit=limit)
    return [_parcel(row) for row in rows]


def secured_roll(apn: str = "", roll: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """Read the bulk secured workbook for one parcel, or for the community.

    An empty ``apn`` returns the association's units and common areas. The
    workbook is read from ``roll`` when that path is set, otherwise from
    ``secured_roll_public.xlsx`` beside the data directory. A missing file
    returns no rows.
    """
    root = _data_dir(data_dir)
    path = _roll_path(root, roll)
    if not path.is_file():
        return {"workbook": str(path), "found": False, "parcels": []}
    numbers = (apn,) if apn.strip() else _community_parcels()
    return _from_roll(SecuredRoll(path), numbers, workbook=str(path))


def _tax_search(client, query: str, *, limit: int = 10) -> dict[str, Any]:
    text = " ".join(query.split())
    if not text:
        return {"error": "Pass a parcel number or an address.", "accounts": []}
    cap = max(1, min(int(limit or 10), 20))
    rows = client.search(text)
    kept = rows[:cap]
    return {
        "query": text,
        "total": len(rows),
        "truncated": len(rows) > cap,
        "accounts": [_account(row, bills=False) for row in kept],
    }


def _from_roll(roll, apns: tuple[str, ...], *, workbook: str) -> dict[str, Any]:
    parcels = [_parcel(row) for row in roll.filter(apns)]
    return {"workbook": workbook, "found": True, "count": len(parcels), "parcels": parcels}


def _account(account: TaxAccount, *, bills: bool) -> dict[str, Any]:
    body: dict[str, Any] = {
        "apn": parcel_number(account.apn),
        "address": account.address,
        "assessee": account.assessee,
        "amountCents": account.amount_cents,
        "found": True,
    }
    if not bills:
        body["bills"] = len(account.bills)
        return body
    listed = [_bill(bill) for bill in account.bills]
    if account.bills:
        listed[0]["levies"] = [
            {
                "kind": levy.kind,
                "name": levy.name,
                "code": levy.code,
                "amountCents": levy.amount_cents,
            }
            for levy in account.bills[0].levies[:30]
        ]
    body["bills"] = listed
    return body


def _bill(bill: TaxBill) -> dict[str, Any]:
    return {
        "year": bill.year,
        "number": bill.number,
        "landCents": bill.land_cents,
        "improvementCents": bill.improvement_cents,
        "netAssessedCents": bill.net_assessed_cents,
        "adValoremCents": bill.ad_valorem_cents,
        "directCents": bill.direct_cents,
        "totalCents": bill.total_cents,
    }


def _parcel(parcel: SecuredParcel) -> dict[str, Any]:
    return {
        "apn": parcel_number(parcel.apn),
        "owner": parcel.owner,
        "situs": parcel.situs,
        "landUse": parcel.land_use,
        "deedType": parcel.deed_type,
        "recordingDate": parcel.recording_date.isoformat() if parcel.recording_date else "",
        "recordingPage": parcel.recording_page,
        "document": parcel.document,
        "landCents": parcel.land_cents,
        "improvementCents": parcel.improvement_cents,
        "netCents": parcel.land_cents + parcel.improvement_cents,
    }


def unit_characteristics(apn: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """The assessor's stored residential characteristics: living area, bedrooms, baths, year built, floor level.

    One parcel when ``apn`` is given, else every stored unit. The plan is the
    developer's plan nearest the measured area, or empty when none is within
    tolerance. Reads disk only; ``jason sync-characteristics`` fills the store.
    """
    from jason.community import mystique
    from jason.community.characteristics import CharacteristicsStore, classify_plan

    root = _data_dir(data_dir)
    path = root / "characteristics.db"
    if not path.is_file():
        return {"found": False, "count": 0, "units": [], "note": "run jason sync-characteristics"}
    community = mystique()
    plans = community.floor_plans()
    with CharacteristicsStore(path) as store:
        records = store.all()
    digits = "".join(ch for ch in apn if ch.isdigit())
    if digits:
        records = {key: value for key, value in records.items() if key == digits}
    units = []
    for key, unit in records.items():
        plan = classify_plan(unit, plans)
        units.append({
            "apn": parcel_number(key), "livingSqft": unit.living_sqft, "bedrooms": unit.bedrooms, "baths": unit.baths,
            "yearBuilt": unit.year_built, "floorLevel": unit.floor_level, "garageSqft": unit.garage_sqft,
            "plan": plan.name if plan else "", "planDeveloper": plan.developer if plan else "",
            "fetched": unit.fetched.isoformat() if unit.fetched else "",
        })
    return {"found": bool(units), "count": len(units), "units": units}


def _data_dir(data_dir: Path | None) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    return Settings.load().payhoa_catalog.parent


def _taxes(root: Path) -> TaxStore:
    return TaxStore(root / "tax.db")


def _secured(root: Path) -> SecuredCatalog:
    return SecuredCatalog(root / "secured.db")


def _roll_path(root: Path, roll: str) -> Path:
    if roll.strip():
        return Path(roll)
    beside = root.parent / "secured_roll_public.xlsx"
    if beside.is_file():
        return beside
    return root / "secured_roll_public.xlsx"


def _community_parcels() -> tuple[str, ...]:
    from jason.community import mystique

    return mystique().parcels()
