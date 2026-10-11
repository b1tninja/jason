"""The county tax collector's payment receipts, trimmed and kept (``data/tax/receipts.json``).

The county's tax collector takes payment through Grant Street Group's GovHub platform (`mystique/docs/county-tax-portal.md`
in the profile's notes; `docs/adapters.md`). Its payment history gives a receipt for each payment made through the site:
a confirmation number, the time it posted, the tender, the billing party, and each paid item with its amount. That is the
county's own record of a payment, and it names the bill each item paid, so it is exact proof of payment for the bill
investigation (`jason.tasks.bill_investigation`).

This module reads a receipt a person saved (the JSON document the site returns) and keeps only what the investigation
needs:

- the **confirmation number** and the **posted time**;
- each paid **item**: its amount in integer cents, the parcel it paid (kept as given here, shown by its last four
  characters in a list), the bill's number and name, the tax year, and which installment;
- the **tender's type** and the **last four digits** of the bank account, never the account's name;
- the fee, in cents.

It drops the billing party's name, address, phone, and email, the delivery party, the user id, the processor details, the
bank account's name, and the item's long description (which prints the situs address). Nothing dropped is written anywhere.

The store is append only. A receipt is added once, by its confirmation number; a second import of the same receipt adds
nothing and changes nothing. The store's ``importedAt`` is the time of the latest import, so a reader can say how old the
store is, and each row carries its own ``importedAt`` and ``by``. Each change holds the store's lock (``jason.locks``).

It contacts nothing. A reader that would fetch receipts from the site needs a person's sign-in at a terminal
(``read_live_receipts`` raises ``NeedsSignIn``); none is built.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qs, urlparse

STORE = Path("tax") / "receipts.json"
LOCK = "tax-receipts"

CAVEATS = (
    "A receipt is the county's record of a payment made through its site. Only the fields the investigation needs are kept.",
    "The billing party and the bank account's name are never kept; the bank account is its last four digits.",
    "A parcel is shown by its last four characters in a list.",
)


class NeedsSignIn(RuntimeError):
    """The site's receipts are read behind a person's sign-in. None is built, and jason signs in to nothing."""


def read_live_receipts(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
    """Not built: reading the site needs a person's sign-in at a terminal and a refresh token held in the vault, neither
    of which has been tried. Import a receipt a person saved instead (``jason county-tax --import-receipts FILE``)."""
    raise NeedsSignIn("reading the county's receipts needs a person's sign-in at a terminal; "
                      "save a receipt from the site and import it with `jason county-tax --import-receipts FILE`")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(data_dir: Path | str) -> Path:
    return Path(data_dir) / STORE


def tail(value: Any, n: int = 4) -> str:
    """The last ``n`` characters of a parcel number (or any account), for a list."""
    return str(value or "").strip()[-n:]


def digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def cents(value: Any) -> int | None:
    """A dollar amount as printed ("7.00", "$1,234.50", 7) in integer cents. ``None`` when it is not an amount."""
    if value is None or isinstance(value, bool):
        return None
    text = str(value).replace("$", "").replace(",", "").strip()
    if not text:
        return None
    try:
        return int((Decimal(text) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    except InvalidOperation:
        return None


def _last_four(tender: Mapping[str, Any]) -> str:
    """The last four digits of the bank account: a field that holds them, else the ones its summary prints."""
    for key in ("last4", "lastFour", "accountLast4"):
        found = digits(tender.get(key))
        if len(found) >= 4:
            return found[-4:]
    summary = str(tender.get("summary") or "")
    found = re.search(r"(\d{4})\D*$", summary)
    return found.group(1) if found else ""


def _installment(path: str) -> str:
    try:
        return (parse_qs(urlparse(path).query).get("installment") or [""])[0]
    except ValueError:
        return ""


def _item(item: Mapping[str, Any]) -> dict[str, Any] | None:
    amount = cents(item.get("amount"))
    if amount is None:
        return None
    details = item.get("details") if isinstance(item.get("details"), Mapping) else {}
    custom = details.get("custom_parameters") if isinstance(details.get("custom_parameters"), Mapping) else {}
    parcel = re.search(r"Parcel\s*#\s*([0-9A-Za-z-]+)", str(details.get("description") or ""))
    year = digits(custom.get("tax_rate_year"))
    return {"amountCents": amount,
            "apn": (parcel.group(1) if parcel else str(details.get("apn") or item.get("apn") or "")).strip(),
            "bill": str(details.get("external_id") or "").strip(),
            "billName": str(details.get("display_name") or "").strip(),
            "year": int(year) if len(year) == 4 else None,
            "installment": _installment(str(item.get("path") or details.get("path") or ""))}


def parse_receipt(doc: Mapping[str, Any]) -> dict[str, Any]:
    """One receipt document, trimmed. Raises ``ValueError`` when it has no confirmation number."""
    if not isinstance(doc, Mapping):
        raise ValueError("a receipt is a JSON object")
    confirmation = str(doc.get("confirmationNumber") or doc.get("id") or "").strip()
    if not confirmation:
        raise ValueError("a receipt without a confirmation number")
    items: list[dict[str, Any]] = []
    fee = 0
    groups = [t for t in doc.get("transactions") or [] if isinstance(t, Mapping)]
    for group in groups or [doc]:
        fee += cents(group.get("fee")) or 0
        for raw in group.get("items") or []:
            row = _item(raw) if isinstance(raw, Mapping) else None
            if row is not None:
                items.append(row)
    total = sum(i["amountCents"] for i in items)
    if not items:
        total = cents(doc.get("amount") if doc.get("amount") is not None else doc.get("total")) or 0
    tender = doc.get("tender") if isinstance(doc.get("tender"), Mapping) else {}
    posted = str(doc.get("postedDatetime") or "").strip()
    try:
        datetime.fromisoformat(posted.replace("Z", "+00:00"))
    except ValueError:
        posted = ""
    return {"confirmation": confirmation, "postedAt": posted, "totalCents": total, "feeCents": fee,
            "tenderType": str(tender.get("type") or "").strip(), "tenderLast4": _last_four(tender), "items": items}


def receipts_from_list(payload: Any) -> tuple[list[dict[str, Any]], int]:
    """The trimmed receipts in a response, and how many entries could not be read (no confirmation number).

    ``payload`` is the list response (``{"results": [...], ...}``, whose ``results`` may be null), a bare list of receipts,
    or the per-receipt response (one receipt object).
    """
    if payload is None:
        return [], 0
    if isinstance(payload, Mapping):
        if "results" in payload or "confirmationNumber" not in payload and "id" not in payload:
            entries = payload.get("results") or []
        else:
            entries = [payload]
    elif isinstance(payload, (list, tuple)):
        entries = list(payload)
    else:
        raise ValueError("a receipt document is a JSON object or a list of them")
    out: list[dict[str, Any]] = []
    skipped = 0
    for entry in entries:
        try:
            out.append(parse_receipt(entry))
        except ValueError:
            skipped += 1
    return out, skipped


# --- the store --------------------------------------------------------------------------------------------------------

def load(data_dir: Path | str) -> list[dict[str, Any]]:
    path = _path(data_dir)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8")).get("receipts", [])
    except (OSError, ValueError):
        return []
    return [dict(r) for r in raw if isinstance(r, dict)]


def _save(data_dir: Path | str, rows: list[dict[str, Any]], imported_at: str) -> None:
    path = _path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"importedAt": imported_at, "receipts": rows}, indent=1), encoding="utf-8")
    tmp.replace(path)


def import_receipts(data_dir: Path | str, receipts: Iterable[Mapping[str, Any]], *, by: str,
                    now: datetime | None = None) -> dict[str, list[dict[str, Any]]]:
    """Append the trimmed ``receipts`` not yet held (by confirmation number). A receipt already held is left as it is.

    Returns ``{"added": [...], "already": [...]}``. ``by`` is required: it is kept with each added row.
    """
    from jason.locks import Resource, hold

    who = (by or "").strip()
    if not who:
        raise ValueError("--by NAME is required: it is kept with each receipt imported")
    stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    with hold(Resource.STORE, LOCK, timeout=60, purpose="county tax receipts: import"):
        rows = load(data_dir)
        held = {r.get("confirmation") for r in rows}
        added: list[dict[str, Any]] = []
        already: list[dict[str, Any]] = []
        for receipt in receipts:
            if receipt["confirmation"] in held:
                already.append(dict(receipt))
                continue
            row = {**receipt, "importedAt": stamp, "by": who}
            rows.append(row)
            held.add(receipt["confirmation"])
            added.append(row)
        if added:
            _save(data_dir, rows, stamp)
    return {"added": added, "already": already}


def posted_day(row: Mapping[str, Any]) -> date | None:
    try:
        return date.fromisoformat(str(row.get("postedAt") or "")[:10])
    except ValueError:
        return None


def money(value: int) -> str:
    return f"${value // 100:,}.{value % 100:02d}"


def lines(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """One line a receipt, its parcels by their last four characters."""
    out = []
    for r in rows:
        parcels = ", ".join(f"parcel ending {tail(i.get('apn'))} {money(int(i.get('amountCents') or 0))}"
                            for i in r.get("items") or []) or "no items listed"
        tender = f"; {r.get('tenderType') or 'tender'} ending {r['tenderLast4']}" if r.get("tenderLast4") else ""
        out.append(f"{r['confirmation']}  {str(r.get('postedAt') or '?')[:10]}  {money(int(r.get('totalCents') or 0))}  "
                   f"{parcels}{tender}; imported {str(r.get('importedAt') or '?')[:10]} by {r.get('by') or '?'}")
    return out


__all__ = ["CAVEATS", "LOCK", "STORE", "NeedsSignIn", "cents", "digits", "import_receipts", "lines", "load", "money",
           "parse_receipt", "posted_day", "read_live_receipts", "receipts_from_list", "tail"]
