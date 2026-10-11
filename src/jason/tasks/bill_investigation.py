"""What to try when a PayHOA payment has no bill: the investigation card's read (docs/console/handoff-mail-and-payment-attachments.md,
Part C).

For one unapproved transaction in the stored snapshot, ``investigate`` says what the payment is (the profile's rule that
selected its class, or that none did), searches every store already on disk for a document or proof of payment, says what
each search found with the store's age, and recommends **one** next step. It reads disk only: the snapshot, the county tax
catalog (``tax.db``), the library's readings, scanned mail, Gmail headers, and the vendor portals' ledgers. It calls no
PayHOA, county site, bill portal, Gmail, or Keeper, writes nothing, and never attaches. A search that would need a live site
is listed as ``not read`` with the command or the human step.

- A **document** (a bill, a statement) and **proof of payment** (a bank notice) are different things: a candidate says which,
  and a bank notice is never offered as the bill.
- ``confidence``: ``exact`` is the amount and a date inside the window; ``near`` is the amount alone, or a date outside the
  window; ``lead`` is a subject or a name only. A candidate is a lead until a person attaches it.
- A candidate in mail or Gmail is P2: without ``private`` its label says only that a message or letter names the amount, and
  it carries no subject, sender, or file.
- Names and amounts, never a body, never an owner's address. An APN is shown by its last four characters.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.payees import PayeeClass, payee_of, rule_of
from jason.tasks import bill_dry_run

WINDOW_DAYS = 7              # the attach engine's default (--date-window-days)
MAX_PER_SOURCE = 5           # a recurring amount matches many documents; the nearest few are shown, the rest counted
NOTICE_DAYS = 5              # a bank's "payment sent" notice is dated about the payment
MAIL_DAYS = 45               # a mailed tax bill arrives well before its payment

OUTCOMES = ("attached-bill", "attached-receipt-only", "not-our-bill", "waiting-for-mail", "escalated")

MAIL_KINDS = ("property tax bill", "government or tax notice", "utility bill", "vendor invoice or statement",
              "insurance policy, renewal, or invoice", "bank statement or notice")
CAVEATS = (
    "Every search is a read of a store already on disk, with that store's age; a search that needs a live site is listed as not read.",
    "A bank notice proves a payment was sent. It is not the bill, and is never offered as one.",
    "A candidate is a lead until a person attaches it. jason does not invent a match on a close amount.",
)


def _cents_text(cents: int) -> re.Pattern[str]:
    dollars, rest = divmod(abs(cents), 100)
    grouped = f"{dollars:,}"
    plain = str(dollars)
    both = {re.escape(f"{grouped}.{rest:02d}"), re.escape(f"{plain}.{rest:02d}")}
    return re.compile(r"(?<![\d.,])(?:" + "|".join(sorted(both)) + r")(?!\d)")


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _within(a: date | None, b: date | None, days: int) -> bool:
    return a is not None and b is not None and abs((a - b).days) <= days


def _gap(value: Any, day: date | None) -> int:
    d = _day(value)
    return abs((d - day).days) if d and day else 10**6


def _tried(source: str, result: str, note: str, read_at: str | None = None) -> dict[str, Any]:
    return {"source": source, "result": result, "readAt": read_at, "note": note}


def _store_time(path: Path, key: str = "syncedAt") -> str | None:
    """A JSON store's own stamp, from its head."""
    try:
        with path.open("r", encoding="utf-8") as f:
            head = f.read(4096)
    except OSError:
        return None
    found = re.search(r'"' + key + r'"\s*:\s*"([^"]+)"', head)
    return found.group(1) if found else None


def _result(found: list[dict[str, Any]]) -> str:
    if not found:
        return "none"
    return "near" if all(c["confidence"] != "exact" for c in found) else "exact" if len(found) == 1 else "ambiguous"


# --- the searches -----------------------------------------------------------------------------------------------------

def _twins(snap: dict[str, Any], tx: dict[str, Any], day: date | None) -> list[dict[str, Any]]:
    """The same amount on another transaction that has an attachment already: the bill may be filed under it."""
    out = []
    for other in snap.get("transactions") or []:
        if other.get("id") == tx.get("id") or int(other.get("amount") or 0) != int(tx["amount"]):
            continue
        if not [a for a in other.get("attachments") or [] if not a.get("deletedAt")]:
            continue
        d = _day(other.get("transactionDate"))
        out.append({"kind": "bill", "label": f"the attachment on transaction {other['id']}, the same amount",
                    "amountCents": int(tx["amount"]), "date": d.isoformat() if d else None, "dateMeaning": "sent",
                    "confidence": "lead", "evidence": "document",
                    "why": "the same amount was paid before and a bill is attached there: how that one was filed, "
                           "not this payment's bill", "link": f"transaction:{other['id']}"})
    return out


def _tax(data_dir: Path, tx: dict[str, Any], day: date | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = data_dir / "tax.db"
    if not path.is_file():
        return [], _tried("the county tax catalog", "not read", "no tax catalog on disk; `jason sync-tax` reads it")
    amount = int(tx["amount"])
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        stamp = conn.execute("SELECT MAX(synced_at) FROM bills").fetchone()[0]
        rows = conn.execute("SELECT apn, number, year, total_cents, payments_cents, balance_cents, pdf_path FROM bills").fetchall()
    except sqlite3.OperationalError:
        return [], _tried("the county tax catalog", "not read", "the catalog has no bills table; `jason sync-tax` fills it")
    finally:
        conn.close()
    out = []
    for r in rows:
        total = r["total_cents"]
        halves = {total // 2, total - total // 2} if total else set()
        which = ("the whole bill" if total == amount else "one installment (half the bill)" if amount in halves
                 else "a payment already on the bill" if r["payments_cents"] == amount else "")
        if not which:
            continue
        pdf = (data_dir / r["pdf_path"]) if r["pdf_path"] else None
        out.append({"kind": "tax-catalog", "label": f"tax bill {r['number']} ({r['year']}), parcel ending {str(r['apn'])[-4:]}",
                    "amountCents": amount, "date": None, "confidence": "exact", "evidence": "document",
                    "why": f"the amount is {which}", "hasPdf": bool(pdf and pdf.is_file()), "link": f"tax:{r['apn']}:{r['number']}"})
    return out, _tried("the county tax catalog", _result(out), f"{len(rows)} bills read", stamp)


def _library(data_dir: Path, tx: dict[str, Any], day: date | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        from jason.tasks.library import load

        rows = list(load(data_dir))
    except Exception:  # noqa: BLE001 - an unreadable library is no library
        return [], _tried("the library's readings", "not read", "no library on disk; `jason library` reads it")
    amount, out = int(tx["amount"]), []
    for row in rows:
        if row.get("confidential"):
            continue
        fields = row.get("fields") or {}
        hit = [k for k, v in fields.items() if re.search(r"amount|total|due|balance|payment", k, re.I)
               and isinstance(v, (int, float)) and not isinstance(v, bool)
               and (int(v) == amount or round(float(v) * 100) == amount)]
        if not hit:
            continue
        dates = [_day(v) for k, v in fields.items() if re.search(r"date|due", k, re.I)]
        near = any(_within(d, day, WINDOW_DAYS) for d in dates)
        out.append({"kind": "bill", "label": str(row.get("name") or "an unnamed document"), "amountCents": amount,
                    "date": next((d.isoformat() for d in dates if d), None), "confidence": "exact" if near else "near",
                    "evidence": "document", "why": f"the reading's {hit[0]} is this amount",
                    "doc": {"id": row.get("id"), "where": "library"}})
    return out, _tried("the library's readings", _result(out), f"{len(rows)} documents", None)


def _mail(data_dir: Path, tx: dict[str, Any], day: date | None, private: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        from jason.tasks.mail import load_items

        items = load_items(data_dir)
    except Exception:  # noqa: BLE001
        items = {}
    if not items:
        return [], _tried("paper mail", "not read", "no scanned mail on disk; `jason mail --sync` reads it")
    pattern, out = _cents_text(int(tx["amount"])), []
    for item in items.values():
        if item.get("kind") not in MAIL_KINDS or not pattern.search(str(item.get("text") or "")):
            continue
        d = _day(item.get("received"))
        out.append({"kind": "mail-scan", "label": (f"{item.get('kind')} from {item.get('from') or item.get('sender') or 'a sender'}"
                                                   if private else "a scanned letter names this amount"),
                    "amountCents": int(tx["amount"]), "date": d.isoformat() if d else None, "dateMeaning": "received",
                    "confidence": "exact" if _within(d, day, MAIL_DAYS) else "near", "evidence": "document",
                    "why": "the letter's text names this amount", **({"doc": {"id": item["mailId"], "where": "mail"}} if private else {})})
    return out, _tried("paper mail", _result(out), f"{len(items)} letters", None)


def _gmail(data_dir: Path, tx: dict[str, Any], day: date | None, private: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = data_dir / "gmail" / "correspondence.json"
    if not path.is_file():
        return [], _tried("Gmail headers", "not read", "no Gmail headers on disk; `jason gmail --sync` reads them")
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], _tried("Gmail headers", "not read", "the Gmail store could not be read")
    pattern, out = _cents_text(int(tx["amount"])), []
    for m in body.get("messages") or []:
        subject = str(m.get("subject") or "")
        if not pattern.search(subject):
            continue
        d = _day(m.get("at"))
        if not _within(d, day, NOTICE_DAYS):
            continue
        out.append({"kind": "bank-notice", "label": subject[:90] if private else "a message whose subject names this amount",
                    "amountCents": int(tx["amount"]), "date": d.isoformat() if d else None, "dateMeaning": "sent",
                    "confidence": "lead", "evidence": "payment-proof",
                    "why": "the subject names the amount near the payment date: proof a payment was sent, not the bill",
                    **({"link": f"gmail:{m.get('threadId')}"} if private else {})})
    return out, _tried("Gmail headers", _result(out), f"{len(body.get('messages') or [])} messages (headers only)", body.get("syncedAt"))


def _portals(data_dir: Path, community: Any, tx: dict[str, Any], day: date | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        from jason.tasks.invoice_review import vendor_ledgers

        ledgers = vendor_ledgers(data_dir, community)
    except Exception:  # noqa: BLE001
        ledgers = {}
    if not ledgers:
        return [], _tried("vendor portals", "not read", "no vendor portal ledgers on disk; `jason vendors --sync` reads them")
    amount, out = int(tx["amount"]), []
    for key, (_portal, pays) in ledgers.items():
        for p in pays:
            if p.amount_cents != amount:
                continue
            out.append({"kind": "portal-invoice", "label": f"{key}: a payment recorded in the portal",
                        "amountCents": amount, "date": p.day.isoformat(), "dateMeaning": "sent",
                        "confidence": "exact" if _within(p.day, day, WINDOW_DAYS) else "near", "evidence": "document",
                        "why": f"the portal's ledger records this amount, paying invoice {', '.join(p.invoice_ids) or 'unlisted'}",
                        "hasPdf": bool(p.invoice_files)})
    return out, _tried("vendor portals", _result(out), f"{sum(len(p) for _k, (_x, p) in ledgers.items())} payments", None)


# --- the card ---------------------------------------------------------------------------------------------------------

def _recommend(payee: PayeeClass, candidates: list[dict[str, Any]], tried: list[dict[str, Any]], routed: str | None) -> dict[str, Any]:
    docs = [c for c in candidates if c["evidence"] == "document" and c["confidence"] == "exact"]
    proofs = [c for c in candidates if c["evidence"] == "payment-proof"]
    if len(docs) == 1:
        c = docs[0]
        return {"action": f"Check {c['label']} against the payment, then attach it", "reason": c["why"] +
                " (a lead until you attach it; one document fits)", "command": None}
    if len(docs) > 1:
        return {"action": "Choose between the documents that fit; attach none until one is chosen",
                "reason": f"{len(docs)} documents fit the amount and the dates", "command": None}
    if routed:
        return {"action": f"Run the dry run for {routed}: it syncs only the sources with a payment waiting and tells you "
                          "whether one bill fits", "command": "jason sync-bills --dry-run",
                "reason": f"{routed} owns this payment; the bill is found by its own sync, not by this search"
                          + ("; the bank notice found is proof of payment only" if proofs else "")}
    if payee is PayeeClass.COUNTY_TAX:
        missing = any(t["source"] == "the county tax catalog" and t["result"] == "not read" for t in tried)
        return {"action": ("Read the county tax catalog, then look for this amount" if missing else
                           "Check the mail for a property tax bill, or download it from the county's site and attach it"),
                "command": "jason sync-tax",
                "reason": "a county tax collector's payment is found in the tax catalog or the mailed bill, not a utility portal"
                          + ("; the bank notice found is proof of payment only" if proofs else "")}
    if payee is PayeeClass.FIELD_VENDOR:
        return {"action": "Sync the vendor's portal and look for the invoice it paid", "command": "jason vendors --sync",
                "reason": "a field vendor's invoice is in its portal or filed from email"}
    if payee is PayeeClass.INSURANCE:
        return {"action": "Look in the insurance letters and the agency's email for the invoice", "command": None,
                "reason": "an insurer's invoice comes by the agency, signing service, or mail"}
    if proofs:
        return {"action": "Record the bank notice as proof of payment; the bill is still missing", "command": None,
                "reason": "only proof of payment was found; whether it satisfies the review is the treasurer's policy"}
    return {"action": "Hold for a person: no rule names this payee and no store holds a document for the amount",
            "command": None,
            "reason": "propose a payee row to the profile so the next one routes" if payee is PayeeClass.UNKNOWN
            else "nothing on disk matches; the payee's own site or a request for a copy is next"}


def investigate(data_dir: Path | str, community: Any, registry: Any, transaction_id: int, *, now: datetime | None = None,
                private: bool = False) -> dict[str, Any]:
    """The card for one unapproved transaction of the stored snapshot (``found: false`` when it is not there)."""
    root = Path(data_dir)
    now = now or datetime.now(timezone.utc)
    snap_path = root / bill_dry_run.SNAPSHOT
    if not snap_path.is_file():
        return {"found": False, "reason": "No PayHOA snapshot on disk.", "command": "jason invoices --fetch"}
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    tx = next((t for t in snap.get("transactions") or [] if int(t.get("id") or 0) == int(transaction_id)), None)
    if tx is None:
        return {"found": False, "reason": f"No transaction {transaction_id} in the snapshot of {snap.get('syncedAt')}.",
                "command": "jason invoices --fetch"}
    day = _day(tx.get("transactionDate"))
    rules = tuple(community.payee_rules())
    row, payee = rule_of(tx, rules), payee_of(tx, rules)
    source = registry.route(tx)
    routing = {"payeeClass": payee.value, "source": source.name if source else None,
               "byRule": (row.note or "a profile payee row") if row else None}
    tried = [_tried("the profile's payee rows", "none" if row is None else "exact",
                    "no row selects this payee: propose one" if row is None else f"selected by: {row.note or 'a payee row'}")]
    candidates: list[dict[str, Any]] = []
    for found, entry in (
        (_twins(snap, tx, day), _tried("other attachments of the same amount", "none", "", snap.get("syncedAt"))),
        _tax(root, tx, day), _library(root, tx, day), _mail(root, tx, day, private), _gmail(root, tx, day, private),
        _portals(root, community, tx, day),
    ):
        if entry["source"] == "other attachments of the same amount":
            entry["result"] = _result(found)
        if len(found) > MAX_PER_SOURCE:
            found.sort(key=lambda c: (c["confidence"] != "exact", _gap(c.get("date"), day)))
            entry["note"] = (entry["note"] + "; " if entry["note"] else "") + f"{len(found) - MAX_PER_SOURCE} more of the same amount not shown"
            found = found[:MAX_PER_SOURCE]
        candidates += found
        tried.append(entry)
    tried.append(_tried("the county's or a vendor's own site", "not read",
                        "jason reads no site when a page opens; a person downloads the bill, or a command reads the portal"))
    rank = {"exact": 0, "near": 1, "lead": 2}
    candidates.sort(key=lambda c: (c["evidence"] != "document", rank[c["confidence"]]))
    row_out = {"transactionId": int(tx["id"]), "amountCents": int(tx["amount"]), "date": day.isoformat() if day else None,
               "description": str(tx.get("description") or ""), "attachments": len([a for a in tx.get("attachments") or []
                                                                                    if not a.get("deletedAt")])}
    return {"found": True, "asOf": now.isoformat(timespec="seconds"), "snapshotSyncedAt": snap.get("syncedAt"),
            **row_out, "routing": routing, "tried": tried, "candidates": candidates,
            "recommend": _recommend(payee, candidates, tried, routing["source"]), "outcomes": list(OUTCOMES),
            "private": private, "caveats": list(CAVEATS)}


__all__ = ["CAVEATS", "OUTCOMES", "investigate"]
