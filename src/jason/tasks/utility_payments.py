"""The utility payments in PayHOA and the PDFs attached to them, checked against the bills.

``fetch`` reads every transaction from PayHOA, keeps the SMUD and City of
Sacramento payments (split rows with their siblings), and downloads each
attachment the portals' own files do not already cover into
``data/payhoa/attachments/<transaction>/<attachment>-<name>``. It writes the
payments, without the attachments' signed links, to
``data/payhoa/utility-transactions.json``. It changes nothing in PayHOA.

``run_audit`` reads those files: it parses each attached PDF (a SMUD or City
bill joins the utility store; anything else is classified as a document),
matches each payment to the bills it paid, and writes
``data/payhoa/utility-audit.json``: the attachment and split findings, and
the split by budget line each payment's bills support. The treasurer makes
any correction in PayHOA.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jason.community.content import classify_text
from jason.community.utility import dedupe_bills
from jason.community.utility_payments import Attachment, audit, group_payments, identify, provider_of
from jason.community.utility_store import UtilityStore
from jason.tasks.utilities import PROVIDERS, bill_files, pdf_text, store_path

TRANSACTIONS = "utility-transactions.json"
AUDIT = "utility-audit.json"


def _payhoa_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "payhoa"


def attachment_path(data_dir: Path, tx_id: int, attachment_id: int, filename: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._() -]", "_", filename) or "file.pdf"
    return _payhoa_dir(data_dir) / "attachments" / str(tx_id) / f"{attachment_id}-{safe}"


def _flatten_categories(rows: list[dict[str, Any]]) -> dict[int, str]:
    names: dict[int, str] = {}
    stack = list(rows)
    while stack:
        row = stack.pop()
        if row.get("id") is not None:
            names[int(row["id"])] = str(row.get("name") or row.get("label") or "")
        stack.extend(row.get("children") or [])
    return names


def fetch(client: Any, org_id: int, data_dir: Path, roots: dict, *, log: Callable[[str], None] | None = None) -> dict[str, int]:
    """Read the utility payments and download the attachments the portal files do not cover. Read-only in PayHOA."""
    transactions = list(client.iter_transactions(org_id, per_page=1000))
    parents = {int(t["parentId"]) for t in transactions if t.get("parentId") and provider_of(t)}
    kept = [t for t in transactions if provider_of(t) or (t.get("parentId") and int(t["parentId"]) in parents)]
    categories = _flatten_categories(client.list_categories(org_id))
    # A list row can omit attachments its detail has; ask the detail before calling a payment bare.
    checked = 0
    for tx in kept:
        if not tx.get("attachments"):
            detail = client.get_transaction(org_id, int(tx["id"]))
            tx["attachments"] = detail.get("attachments") or []
            checked += 1
    portal = {pdf.name: pdf for _utility, _account, pdf in bill_files(roots)}
    downloaded = reused = present = failed = 0
    for tx in kept:
        for raw in tx.get("attachments") or []:
            name = str(raw.get("filename") or "")
            if name in portal:
                reused += 1
                continue
            dest = attachment_path(data_dir, int(tx["id"]), int(raw["id"]), name)
            if dest.is_file() and (not raw.get("filesize") or dest.stat().st_size == int(raw["filesize"])):
                present += 1
                continue
            url = raw.get("url")
            if not url:
                # Some list rows carry the attachment without its link; the detail has it.
                detail = client.get_transaction(org_id, int(tx["id"]))
                url = next((a.get("url") for a in detail.get("attachments") or [] if int(a.get("id") or 0) == int(raw["id"])), None)
            if not url:
                failed += 1
                continue
            try:
                # A signed S3 link: the client fetches it without the PayHOA bearer token.
                client.download_signed_url(url, dest)
            except Exception as exc:  # one expired or missing file is reported, not fatal
                failed += 1
                if log:
                    log(f"attachment {raw['id']} on transaction {tx['id']}: {exc}")
                continue
            downloaded += 1
            if log and downloaded % 50 == 0:
                log(f"downloaded {downloaded} attachments")
    for tx in kept:
        for raw in tx.get("attachments") or []:
            raw.pop("url", None)
    out = _payhoa_dir(data_dir) / TRANSACTIONS
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "syncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "categories": {str(k): v for k, v in sorted(categories.items())},
        "transactions": kept,
    }, indent=1, default=str), encoding="utf-8")
    return {"transactions": len(kept), "detailsChecked": checked, "downloaded": downloaded, "reused": reused, "present": present, "failed": failed}


def _read_attachments(data_dir: Path, transactions: list[dict[str, Any]], roots: dict, store: UtilityStore) -> dict[int, Attachment]:
    """Each attachment's content: the bill it holds (saved to the store), or its document kind."""
    portal = {pdf.name: pdf for _utility, _account, pdf in bill_files(roots)}
    known = store.known()
    found: dict[int, Attachment] = {}
    for tx in transactions:
        for raw in tx.get("attachments") or []:
            ident, name = int(raw["id"]), str(raw.get("filename") or "")
            path = portal.get(name) or attachment_path(data_dir, int(tx["id"]), ident, name)
            if not path.is_file():
                found[ident] = Attachment(ident, int(tx["id"]), name, "", None, "not on disk: PayHOA gave no download link, or --fetch has not run")
                continue
            if path.suffix.lower() != ".pdf":
                found[ident] = Attachment(ident, int(tx["id"]), name, str(path), None, f"{path.suffix or 'no'} file")
                continue
            try:
                text = pdf_text(path)
            except RuntimeError:
                raise
            except Exception as exc:  # a damaged file is reported, not fatal
                found[ident] = Attachment(ident, int(tx["id"]), name, str(path), None, f"unreadable: {exc}")
                continue
            who = identify(text)
            if who is None:
                kind, _why = classify_text(text) if text.strip() else (None, "")
                found[ident] = Attachment(ident, int(tx["id"]), name, str(path), None,
                                          kind.value if kind else ("no text layer (a scan)" if not text.strip() else "unclassified"))
                continue
            utility, account = who
            source = str(path.resolve())
            bill = PROVIDERS[utility].parse(text, account=account, bill_id=path.stem, source=source)
            stat = path.stat()
            if known.get(source) != (stat.st_size, stat.st_mtime):
                store.save(bill, size=stat.st_size, mtime=stat.st_mtime)
            found[ident] = Attachment(ident, int(tx["id"]), name, source, bill, "utility_bill")
    return found


def run_audit(data_dir: Path, community: Any, roots: dict) -> dict[str, Any]:
    """Match every utility payment to its bills and check its attachment and split. Writes ``utility-audit.json``."""
    source = _payhoa_dir(data_dir) / TRANSACTIONS
    if not source.is_file():
        return {"found": False, "note": "no utility transactions on disk; run jason utilities --payments --fetch"}
    snap = json.loads(source.read_text(encoding="utf-8"))
    categories = {int(k): v for k, v in snap["categories"].items()}
    with UtilityStore(store_path(data_dir)) as store:
        attachments = _read_attachments(data_dir, snap["transactions"], roots, store)
        bills = dedupe_bills(store.bills())
    payments = group_payments(snap["transactions"], categories, attachments)
    rows = audit(payments, bills, community.utility_budget_lines())
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        side = summary.setdefault(row["provider"], {"payments": 0, "ok": 0, "noAttachment": 0, "wrongAttachment": 0,
                                                    "unmatched": 0, "notSplit": 0, "splitDiffers": 0})
        side["payments"] += 1
        side["ok"] += row["ok"]
        side["noAttachment"] += "no attachment" in row["findings"]
        side["wrongAttachment"] += any(f.startswith(("the attachments do not", "attached bill(s)", "attachment ")) for f in row["findings"])
        side["unmatched"] += "no set of bills on disk sums to this payment" in row["findings"]
        side["paidTwice"] = side.get("paidTwice", 0) + any(f.startswith("paid twice") for f in row["findings"])
        side["notSplit"] += row["split"] == "not split"
        side["splitDiffers"] += row["split"] in ("split differs from the bills", "one line expected; category differs", "amounts differ")
    result = {
        "found": True,
        "transactionsSyncedAt": snap.get("syncedAt"),
        "auditedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": summary,
        "payments": rows,
        "caveats": [
            "A payment is matched to the bills whose totals sum to it; a payment of a past-due balance or a partial payment stays unmatched.",
            "The expected split is the bills' charges by budget line. Jason does not change PayHOA; the treasurer applies a split.",
        ],
    }
    (_payhoa_dir(data_dir) / AUDIT).write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return result


def load_audit(data_dir: Path) -> dict[str, Any] | None:
    path = _payhoa_dir(data_dir) / AUDIT
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def attachment_refs(data_dir: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each audited payment's attachments with ``doc``, the ``DocRef`` of the copy kept under the data folder
    (``transactions/<year>/<month>/invoices/``), when the evidence opens it (docs/console/doc-component.md). A bill
    whose only copy is the portal's, outside the folder, has none. Changes ``rows`` in place and returns them."""
    from jason.tasks.invoice_review import document_refs

    return document_refs(data_dir, rows, store=TRANSACTIONS, field="attachments")


def dollars(cents: int | None) -> str:
    return "-" if cents is None else f"${cents / 100:,.2f}"


def audit_lines(result: dict[str, Any], *, only_problems: bool = True, limit: int = 60) -> list[str]:
    if not result.get("found"):
        return [result.get("note", "no audit")]
    out = [f"Transactions synced {result['transactionsSyncedAt']}"]
    for provider, s in result["summary"].items():
        out.append(f"  {provider}: {s['payments']} payments, {s['ok']} clean; {s['noAttachment']} without an attachment, "
                   f"{s['wrongAttachment']} with the wrong or an unreadable attachment, {s['unmatched']} not matched to bills, "
                   f"{s['notSplit']} not split, {s['splitDiffers']} split differently from the bills, {s.get('paidTwice', 0)} paid twice")
    shown = [r for r in result["payments"] if not only_problems or not r["ok"]]
    out.append("")
    for row in list(reversed(shown))[:limit]:
        paid = ", ".join(f"{p['account']} {p['billDate']}" for p in row["paid"]) or "no bills matched"
        out.append(f"{row['date']} {row['provider']} {dollars(row['amountCents'])}  paid: {paid}")
        for finding in row["findings"]:
            out.append(f"    - {finding}")
        if row["split"] not in ("matches the bills", "matches the bills' lines", "no bill to split by"):
            actual = "; ".join(f"{k} {dollars(v)}" for k, v in row["actualSplit"].items())
            expected = "; ".join(f"{k} {dollars(v)}" for k, v in row["expectedSplit"].items())
            out.append(f"      now:      {actual}")
            out.append(f"      expected: {expected}")
    if len(shown) > limit:
        out.append(f"... {len(shown) - limit} more in data/payhoa/{AUDIT}")
    return out


__all__ = ["fetch", "run_audit", "load_audit", "audit_lines", "attachment_path", "attachment_refs"]
