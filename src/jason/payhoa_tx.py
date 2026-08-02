"""PayHOA transaction normalization, SMUD filtering, dump, and probes."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from payhoa import PayhoaClient

ReviewedFilter = Literal[False, True, "all"]


def parse_tx_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    elif " " in text:
        text = text.split(" ", 1)[0]
    return date.fromisoformat(text[:10])


def is_smud_transaction(
    tx: dict[str, Any],
    *,
    smud_category_id: int | None = 1245405,
) -> bool:
    """Client-side SMUD identity (never match other vendors)."""
    rule = tx.get("transactionRule") or {}
    if isinstance(rule, dict) and str(rule.get("name", "")).upper() == "SMUD":
        return True
    description = str(tx.get("description") or "")
    if "SMUD" in description.upper():
        return True
    if smud_category_id is not None and tx.get("categoryId") == smud_category_id:
        return True
    return False


def is_city_sac_transaction(
    tx: dict[str, Any],
    *,
    category_id: int | None = 1245485,
) -> bool:
    """Client-side City of Sacramento utilities identity (never SMUD)."""
    rule = tx.get("transactionRule") or {}
    rule_name = str(rule.get("name") or "") if isinstance(rule, dict) else ""
    description = str(tx.get("description") or "")
    # SMUD is exclusive
    if rule_name.upper() == "SMUD" or "SMUD" in description.upper():
        return False

    if "SACRAMENTO" in rule_name.upper():
        return True

    desc = description.upper()
    if "CITY OF SACRAMENTO" in desc:
        return True
    if "SACRAMENTO UTIL" in desc:
        return True
    # ACH-style payee text
    if "SACRAMENTO" in desc and any(
        token in desc for token in ("UTIL", "WATER", "CITY OF", "CASH CONCENTRAT")
    ):
        return True

    if category_id is not None and tx.get("categoryId") == category_id:
        return True
    return False


def normalize_transaction(
    tx: dict[str, Any],
    *,
    smud_category_id: int | None = 1245405,
) -> dict[str, Any]:
    rule = tx.get("transactionRule") or {}
    rule_name = ""
    rule_id = tx.get("transactionRuleId")
    if isinstance(rule, dict):
        rule_name = str(rule.get("name") or "")
        rule_id = rule.get("id", rule_id)
    attachments = tx.get("attachments") or []
    active = [a for a in attachments if not a.get("deletedAt")]
    tx_date = tx.get("transactionDate")
    try:
        date_str = parse_tx_date(tx_date).isoformat() if tx_date else ""
    except ValueError:
        date_str = str(tx_date or "")

    return {
        "id": tx.get("id"),
        "amount_cents": tx.get("amount"),
        "transaction_date": date_str,
        "description": tx.get("description") or "",
        "approved": tx.get("approved"),
        "category_id": tx.get("categoryId"),
        "transaction_rule_id": rule_id,
        "transaction_rule_name": rule_name,
        "vendor_id": tx.get("vendorId"),
        "attachment_count_list": len(active),
        "is_smud_candidate": is_smud_transaction(
            tx, smud_category_id=smud_category_id
        ),
    }


def iter_payhoa_transactions(
    client: PayhoaClient,
    org_id: int,
    *,
    reviewed: ReviewedFilter = False,
    search: str = "",
):
    reviewed_arg: bool | None
    if reviewed == "all":
        reviewed_arg = None
    else:
        reviewed_arg = bool(reviewed)
    yield from client.iter_transactions(
        org_id, reviewed=reviewed_arg, search=search
    )


def list_normalized_transactions(
    client: PayhoaClient,
    org_id: int,
    *,
    reviewed: ReviewedFilter = False,
    search: str = "",
    smud_category_id: int | None = 1245405,
    raw: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tx in iter_payhoa_transactions(
        client, org_id, reviewed=reviewed, search=search
    ):
        if raw:
            rows.append(tx)
        else:
            rows.append(
                normalize_transaction(tx, smud_category_id=smud_category_id)
            )
    return rows


def dump_transactions(
    client: PayhoaClient,
    org_id: int,
    path: str | Path,
    *,
    reviewed: ReviewedFilter = False,
    search: str = "",
    smud_category_id: int | None = 1245405,
    raw: bool = False,
    fmt: Literal["jsonl", "json"] = "jsonl",
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list_normalized_transactions(
        client,
        org_id,
        reviewed=reviewed,
        search=search,
        smud_category_id=smud_category_id,
        raw=raw,
    )
    if fmt == "json":
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    else:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    return path


def probe_transactions(
    client: PayhoaClient,
    org_id: int,
    *,
    smud_category_id: int | None = 1245405,
) -> list[dict[str, Any]]:
    """Run live list/search probes and return summary rows."""
    results: list[dict[str, Any]] = []

    def summarize(name: str, txs: list[dict[str, Any]], *, error: str | None = None):
        if error:
            results.append(
                {
                    "probe": name,
                    "ok": False,
                    "error": error,
                    "total": 0,
                    "smud_candidates": 0,
                    "sample_ids": [],
                }
            )
            return
        smud = [
            t
            for t in txs
            if is_smud_transaction(t, smud_category_id=smud_category_id)
        ]
        results.append(
            {
                "probe": name,
                "ok": True,
                "error": None,
                "total": len(txs),
                "smud_candidates": len(smud),
                "sample_ids": [t.get("id") for t in smud[:5]],
            }
        )

    # Baseline: unreviewed
    try:
        unreviewed = list(
            client.iter_transactions(org_id, reviewed=False)
        )
        summarize("reviewed=false", unreviewed)
    except Exception as exc:
        summarize("reviewed=false", [], error=str(exc))
        unreviewed = []

    # search=SMUD on unreviewed
    for term in ("SMUD", "smud"):
        name = f'reviewed=false search="{term}"'
        try:
            txs = list(
                client.iter_transactions(org_id, reviewed=False, search=term)
            )
            summarize(name, txs)
        except Exception as exc:
            summarize(name, [], error=str(exc))

    # search=SMUD without reviewed filter
    try:
        txs = list(client.iter_transactions(org_id, search="SMUD"))
        summarize('search="SMUD" (no reviewed filter)', txs)
    except Exception as exc:
        summarize('search="SMUD" (no reviewed filter)', [], error=str(exc))

    # Client-side SMUD on unreviewed (ground truth for matcher)
    summarize(
        "reviewed=false + client SMUD filter",
        [
            t
            for t in unreviewed
            if is_smud_transaction(t, smud_category_id=smud_category_id)
        ],
    )

    # transactionFilters metadata
    try:
        filters = client.transaction_filters(org_id)
        vendors = filters.get("vendors")
        results.append(
            {
                "probe": "transactionFilters",
                "ok": True,
                "error": None,
                "total": len(vendors) if isinstance(vendors, list) else 0,
                "smud_candidates": 0,
                "sample_ids": [],
                "keys": list(filters.keys()),
            }
        )
    except Exception as exc:
        results.append(
            {
                "probe": "transactionFilters",
                "ok": False,
                "error": str(exc),
                "total": 0,
                "smud_candidates": 0,
                "sample_ids": [],
            }
        )

    return results
