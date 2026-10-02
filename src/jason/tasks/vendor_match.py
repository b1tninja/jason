"""Suggest vendor matches for bank transactions by name-in-description."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from jason.payhoa_tx import is_city_sac_transaction, is_smud_transaction


@dataclass
class VendorMatchSuggestion:
    transaction_id: int | None
    description: str
    matched_vendor_ids: list[int]
    matched_vendor_names: list[str]
    unique: bool
    excluded: bool = False
    exclusion_reason: str = ""


@dataclass
class VendorMatchReport:
    matches: list[VendorMatchSuggestion] = field(default_factory=list)
    unique_count: int = 0
    ambiguous_count: int = 0
    excluded_count: int = 0
    unmatched_count: int = 0

    def summary(self) -> str:
        return (
            f"unique={self.unique_count} ambiguous={self.ambiguous_count} "
            f"excluded={self.excluded_count} unmatched={self.unmatched_count}"
        )


def _vendor_name(vendor: Mapping[str, Any]) -> str:
    return str(
        vendor.get("name") or vendor.get("vendorName") or vendor.get("title") or ""
    ).strip()


def _vendor_id(vendor: Mapping[str, Any]) -> int | None:
    value = vendor.get("id") if vendor.get("id") is not None else vendor.get("vendorId")
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _vendors_from_bill_payments(
    bill_payments: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Extract vendor-like name records from bill-payment rows when present."""
    out: list[dict[str, Any]] = []
    for payment in bill_payments:
        name = _vendor_name(payment)
        vid = _vendor_id(payment)
        nested = payment.get("vendor")
        if not name and isinstance(nested, dict):
            name = _vendor_name(nested)
            vid = _vendor_id(nested)
        if name:
            out.append({"id": vid, "name": name})
    return out


def _merge_vendor_names(
    vendors: Iterable[Mapping[str, Any]],
    bill_payments: Iterable[Mapping[str, Any]] | None,
) -> list[tuple[int | None, str]]:
    named: list[tuple[int | None, str]] = []
    seen: set[str] = set()
    sources: list[Mapping[str, Any]] = list(vendors)
    if bill_payments is not None:
        sources.extend(_vendors_from_bill_payments(bill_payments))
    for vendor in sources:
        name = _vendor_name(vendor)
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        named.append((_vendor_id(vendor), name))
    return named


def match_vendors_in_transactions(
    transactions: Iterable[Mapping[str, Any]],
    vendors: Iterable[Mapping[str, Any]],
    *,
    bill_payments: Iterable[Mapping[str, Any]] | None = None,
) -> VendorMatchReport:
    """Match when a vendor name appears in the transaction description.

    Unique name matches are marked ``unique=True``. Ambiguous (2+) matches
    are reported but not auto-chosen. SMUD and City of Sacramento txs are
    excluded via ``is_smud_transaction`` / ``is_city_sac_transaction``.
    """
    named = _merge_vendor_names(vendors, bill_payments)
    matches: list[VendorMatchSuggestion] = []
    unique_count = ambiguous_count = excluded_count = unmatched_count = 0

    for tx in transactions:
        raw_id = tx.get("id")
        try:
            tx_id = int(raw_id) if raw_id is not None else None
        except (TypeError, ValueError):
            tx_id = None
        description = str(tx.get("description") or "")
        tx_dict = dict(tx)

        if is_smud_transaction(tx_dict):
            matches.append(
                VendorMatchSuggestion(
                    transaction_id=tx_id,
                    description=description,
                    matched_vendor_ids=[],
                    matched_vendor_names=[],
                    unique=False,
                    excluded=True,
                    exclusion_reason="smud",
                )
            )
            excluded_count += 1
            continue
        if is_city_sac_transaction(tx_dict):
            matches.append(
                VendorMatchSuggestion(
                    transaction_id=tx_id,
                    description=description,
                    matched_vendor_ids=[],
                    matched_vendor_names=[],
                    unique=False,
                    excluded=True,
                    exclusion_reason="city_sacramento",
                )
            )
            excluded_count += 1
            continue

        desc_upper = description.upper()
        hit_ids: list[int] = []
        hit_names: list[str] = []
        for vid, name in named:
            if name.upper() in desc_upper:
                hit_names.append(name)
                if vid is not None:
                    hit_ids.append(vid)

        if not hit_names:
            unmatched_count += 1
            matches.append(
                VendorMatchSuggestion(
                    transaction_id=tx_id,
                    description=description,
                    matched_vendor_ids=[],
                    matched_vendor_names=[],
                    unique=False,
                )
            )
            continue

        is_unique = len(hit_names) == 1
        if is_unique:
            unique_count += 1
        else:
            ambiguous_count += 1
        matches.append(
            VendorMatchSuggestion(
                transaction_id=tx_id,
                description=description,
                matched_vendor_ids=hit_ids,
                matched_vendor_names=hit_names,
                unique=is_unique,
            )
        )

    return VendorMatchReport(
        matches=matches,
        unique_count=unique_count,
        ambiguous_count=ambiguous_count,
        excluded_count=excluded_count,
        unmatched_count=unmatched_count,
    )


def suggest_vendor_matches(
    client: Any,
    org_id: int,
    *,
    transactions: Iterable[Mapping[str, Any]] | None = None,
    reviewed: bool | None = False,
) -> VendorMatchReport:
    """Load vendors (and bill-payments) then match against transactions.

    Calls ``list_vendors``, ``list_bill_payments`` (if present), and
    ``iter_transactions`` when ``transactions`` is not supplied.
    """
    vendors = list(client.list_vendors(org_id))
    bill_payments: list[Mapping[str, Any]] | None = None
    if hasattr(client, "list_bill_payments"):
        bill_payments = list(client.list_bill_payments(org_id))
    txs: Iterable[Mapping[str, Any]]
    if transactions is None:
        txs = list(client.iter_transactions(org_id, reviewed=reviewed))
    else:
        txs = transactions
    return match_vendors_in_transactions(
        txs, vendors, bill_payments=bill_payments
    )
