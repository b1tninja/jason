"""A vendor portal's billing against the PayHOA payments to that vendor, and against the invoices attached to them.

Each PayHOA payment to the vendor (its bank words, or its PayHOA vendor) is matched to the
portal's own payment record: the same amount, dated within a few days. The portal payment
names the ticket it paid and the property the ticket belongs to. Then:

- the payment has no portal payment (money the vendor's books do not show);
- it paid another property's ticket (a property on the association's master account that is
  not the association's own, such as an owner's unit);
- its category is not the vendor's budget line;
- nothing is attached, or the attachment is not the invoice for the ticket it paid (another
  invoice number, or a file that does not read as the vendor's invoice), or the same invoice is
  attached to two payments;
- and the other way: portal payments no PayHOA payment accounts for, and each property's balance.

Reads ``data/payhoa/transactions.json`` (``jason invoices --fetch``) and ``data/vendors/<key>``
(``jason vendors --sync``). Writes ``data/vendors/<key>/verification.json``. Changes nothing.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jason.tasks.vendor_portals import load_accounts, portal_root

VERIFICATION = "verification.json"
# The portal records a payment from a few days before the bank line (an ACH it initiated) to three weeks after it
# (a mailed check it deposited).
PORTAL_EARLIER_DAYS, PORTAL_LATER_DAYS = 10, 21
VOID = ("VOID/CANCEL", "VOID:", "CANCELLED")


@dataclass(frozen=True)
class PortalPayment:
    customer_id: str
    property_name: str
    day: date
    amount_cents: int
    tickets: tuple[str, ...]


def portal_payments(accounts: list[dict[str, Any]]) -> list[PortalPayment]:
    found = []
    for account in accounts:
        customer = account["customer"]
        for tx in account["transactions"]:
            if tx["kind"] == "payment" and tx["day"] and tx["payment_cents"]:
                found.append(PortalPayment(customer["customer_id"], customer["name"], date.fromisoformat(tx["day"]),
                                           tx["payment_cents"], tuple(tx["invoice_ids"])))
    return sorted(found, key=lambda p: p.day)


def vendor_transactions(snap: dict[str, Any], portal: Any) -> list[dict[str, Any]]:
    """PayHOA transactions paying this vendor: its bank words, or its vendor in PayHOA's directory. Deleted rows left out."""
    vendor_ids = {int(k) for k, v in (snap.get("vendors") or {}).items() if portal.vendor.split()[0].lower() in str(v).lower()
                  and any(w.split()[-1].lower() in str(v).lower() for w in portal.payhoa_words)}
    rows = []
    for tx in snap["transactions"]:
        if tx.get("deletedAt"):
            continue
        text = f"{tx.get('description') or ''} {((tx.get('transactionRule') or {}).get('name') or '') if isinstance(tx.get('transactionRule'), dict) else ''}".upper()
        if any(w in text for w in portal.payhoa_words) or (tx.get("vendorId") and int(tx["vendorId"]) in vendor_ids):
            rows.append(tx)
    return sorted(rows, key=lambda t: str(t.get("transactionDate")))


def _attached_invoices(data_dir: Path, tx: dict[str, Any]) -> list[dict[str, Any]]:
    """Each attachment on disk, read as this vendor's invoice: its number and total, or why not."""
    from jason.community.invoice_formats import INVOICE_FORMATS
    from jason.community.invoices import read_invoice
    from jason.tasks.invoice_review import local_attachment
    from jason.tasks.utilities import pdf_text

    found = []
    for raw in tx.get("attachments") or []:
        path = local_attachment(data_dir, tx, raw, {})
        entry: dict[str, Any] = {"file": str(raw.get("filename") or ""), "path": str(path) if path.is_file() else ""}
        if not path.is_file():
            entry["read"] = "not on disk"
        elif path.suffix.lower() != ".pdf":
            entry["read"] = f"{path.suffix} file"
        else:
            try:
                invoice = read_invoice(pdf_text(path), formats=INVOICE_FORMATS)
                entry.update({"number": invoice.number, "totalCents": invoice.total_cents, "method": invoice.method,
                              "read": "invoice" if invoice.number else "no invoice number"})
            except Exception as exc:  # an unreadable file is a finding, not a failure
                entry["read"] = f"unreadable: {exc}"
        found.append(entry)
    return found


def align(txs: list[dict[str, Any]], paid: list[PortalPayment], attached: dict[int, set[str]]) -> dict[int, int]:
    """Pair PayHOA payments with portal payments of the same amount, in date order on both sides.

    Per amount, an order-preserving alignment that makes the most pairs within the window, then agrees most
    with the attached invoices, then keeps the dates closest. Returns transaction id -> index into ``paid``.
    """
    pairing: dict[int, int] = {}
    amounts = {int(tx.get("amount") or 0) for tx in txs}
    for amount in amounts:
        # Same-day payments of one amount are ordered by the invoice attached, and portal payments by ticket:
        # invoice numbers rise with time, so the order settles which paid which.
        left = sorted((tx for tx in txs if int(tx.get("amount") or 0) == amount),
                      key=lambda t: (str(t["transactionDate"])[:10], min(attached.get(int(t["id"])) or {"~"})))
        right = sorted((i for i, p in enumerate(paid) if p.amount_cents == amount), key=lambda i: (paid[i].day, paid[i].tickets))
        n, m = len(left), len(right)
        # best[i][j]: (pairs, attachment agreements, -total days) aligning left[:i] with right[:j].
        best = [[(0, 0, 0)] * (m + 1) for _ in range(n + 1)]
        step: dict[tuple[int, int], str] = {}
        for i in range(n + 1):
            for j in range(m + 1):
                if i == 0 and j == 0:
                    continue
                options = []
                if i > 0:
                    options.append((best[i - 1][j], "skip_tx"))
                if j > 0:
                    options.append((best[i][j - 1], "skip_portal"))
                if i > 0 and j > 0:
                    tx, pay = left[i - 1], paid[right[j - 1]]
                    when = date.fromisoformat(str(tx["transactionDate"])[:10])
                    lag = (pay.day - when).days
                    if -PORTAL_EARLIER_DAYS <= lag <= PORTAL_LATER_DAYS:
                        agree = 1 if set(pay.tickets) & attached.get(int(tx["id"]), set()) else 0
                        prev = best[i - 1][j - 1]
                        options.append(((prev[0] + 1, prev[1] + agree, prev[2] - abs(lag)), "pair"))
                best[i][j], step[(i, j)] = max(options, key=lambda o: o[0])
        i, j = n, m
        while i > 0 or j > 0:
            move = step[(i, j)]
            if move == "pair":
                pairing[int(left[i - 1]["id"])] = right[j - 1]
                i, j = i - 1, j - 1
            elif move == "skip_tx":
                i -= 1
            else:
                j -= 1
    return pairing


def verify(data_dir: Path, portal: Any) -> dict[str, Any]:
    data_dir = Path(data_dir)
    snap_path = data_dir / "payhoa" / "transactions.json"
    accounts = load_accounts(data_dir, portal.key)
    if not accounts:
        return {"found": False, "note": f"no {portal.key} portal data; run jason vendors --sync"}
    if not snap_path.is_file():
        return {"found": False, "note": "no PayHOA transaction snapshot; run jason invoices --fetch"}
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    categories = snap.get("categories") or {}
    master = next((a for a in accounts if a["customer"]["customer_id"] == (a["properties"][0]["master_account"] if a["properties"] else "")), accounts[0])
    master_id = master["customer"]["customer_id"]
    root = portal_root(data_dir, portal.key)
    paid = portal_payments(accounts)
    txs = vendor_transactions(snap, portal)
    attachments = {int(tx["id"]): _attached_invoices(data_dir, tx) for tx in txs}
    live = [tx for tx in txs if not any(word in str(tx.get("description") or "").upper() for word in VOID)]
    pairing = align(live, paid, {i: {a.get("number") for a in found if a.get("number")} for i, found in attachments.items()})
    used: set[int] = set(pairing.values())
    rows: list[dict[str, Any]] = []
    invoice_uses: dict[str, list[int]] = defaultdict(list)
    for tx in txs:
        amount = int(tx.get("amount") or 0)
        when = date.fromisoformat(str(tx["transactionDate"])[:10])
        description = str(tx.get("description") or "")
        if any(word in description.upper() for word in VOID):
            rows.append({"transactionId": int(tx["id"]), "date": when.isoformat(), "amountCents": amount,
                         "description": description[:80], "category": None, "portalPaymentDate": None, "ticket": "",
                         "property": "", "portalInvoice": None, "attachments": [], "void": True,
                         "findings": [], "note": "a void: it reverses the bill payment it names"})
            continue
        category = (categories.get(str(tx.get("categoryId"))) or {}).get("name") if isinstance(categories.get(str(tx.get("categoryId"))), dict) else categories.get(str(tx.get("categoryId")))
        findings: list[str] = []
        attached = attachments[int(tx["id"])]
        numbers = [a.get("number") for a in attached if a.get("number")]
        index = pairing.get(int(tx["id"]))
        match = (index, paid[index]) if index is not None else None
        ticket = ""
        property_id = ""
        if match is None:
            if amount > 0:
                findings.append("no portal payment of this amount near this date")
        else:
            pay = match[1]
            ticket = pay.tickets[0] if pay.tickets else ""
            property_id = pay.customer_id
            if pay.customer_id != master_id:
                findings.append(f"paid the ticket of another property on the master account: {pay.property_name} ({pay.customer_id})")
        if amount > 0 and category != portal.budget_line:
            findings.append(f"category {category or '(none)'}, not {portal.budget_line}")
        for number in set(numbers):
            invoice_uses[number].append(int(tx["id"]))
        if amount > 0:
            if not attached:
                findings.append("no invoice attached")
            elif match and not set(match[1].tickets) & set(numbers):
                shown = ", ".join(f"{a['file']} ({'invoice ' + a['number'] if a.get('number') else a['read']})" for a in attached)
                findings.append(f"the vendor applied this payment to invoice {', '.join(match[1].tickets)}; attached: {shown}")
        portal_pdf = root / property_id / "invoices" / f"{ticket}.pdf" if ticket and property_id else None
        rows.append({
            "transactionId": int(tx["id"]), "date": when.isoformat(), "amountCents": amount,
            "description": str(tx.get("description") or "")[:80], "category": category,
            "portalPaymentDate": match[1].day.isoformat() if match else None, "ticket": ticket, "property": property_id,
            "portalInvoice": str(portal_pdf) if portal_pdf and portal_pdf.is_file() else None,
            "attachments": attached, "findings": findings,
        })
    for number, ids in invoice_uses.items():
        if len(ids) > 1:
            for row in rows:
                if row["transactionId"] in ids:
                    row["findings"].append(f"invoice {number} is also attached to transaction(s) "
                                           + ", ".join(str(i) for i in ids if i != row["transactionId"]))
    unmatched_portal = [{"property": p.property_name, "customerId": p.customer_id, "date": p.day.isoformat(),
                         "amountCents": p.amount_cents, "tickets": list(p.tickets)} for i, p in enumerate(paid) if i not in used]
    properties = [{"customerId": a["customer"]["customer_id"], "name": a["customer"]["name"], "address": a["customer"]["address"],
                   "balanceCents": a["customer"]["balance_cents"], "tickets": sum(1 for t in a["transactions"] if t["kind"] == "ticket"),
                   "billedCents": sum(t["charge_cents"] for t in a["transactions"] if t["kind"] == "ticket"),
                   "paidCents": sum(t["payment_cents"] for t in a["transactions"] if t["kind"] == "payment")} for a in accounts]
    result = {
        "found": True,
        "vendor": portal.vendor,
        "verifiedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "payhoaSnapshot": snap.get("syncedAt"),
        "properties": properties,
        "payments": rows,
        "portalPaymentsNotInPayhoa": unmatched_portal,
        "summary": {
            "payhoaPayments": sum(1 for r in rows if r["amountCents"] > 0 and not r.get("void")),
            "voids": sum(1 for r in rows if r.get("void")),
            "clean": sum(1 for r in rows if r["amountCents"] > 0 and not r.get("void") and not r["findings"]),
            "withFindings": sum(1 for r in rows if r["findings"]),
            "portalPaymentsNotInPayhoa": len(unmatched_portal),
        },
        "caveats": [
            "A portal payment made by card or by the owner never reaches the association's bank; a portal payment not in "
            "PayHOA is a question, not an error.",
            "Findings are for the treasurer; jason does not recategorize, re-attach, or pay.",
        ],
    }
    (root / VERIFICATION).write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def verify_lines(result: dict[str, Any], *, limit: int = 40) -> list[str]:
    if not result.get("found"):
        return [result.get("note", "nothing to verify")]
    s = result["summary"]
    out = [f"{result['vendor']}: {s['payhoaPayments']} PayHOA payments, {s['clean']} clean, {s['withFindings']} with findings; "
           f"{s['portalPaymentsNotInPayhoa']} portal payments not in PayHOA"]
    for p in result["properties"]:
        out.append(f"  property {p['name']} ({p['customerId']}, {p['address']}): {p['tickets']} tickets, billed "
                   f"${p['billedCents'] / 100:,.2f}, paid ${p['paidCents'] / 100:,.2f}, balance ${p['balanceCents'] / 100:,.2f}")
    shown = [r for r in result["payments"] if r["findings"]]
    for r in list(reversed(shown))[:limit]:
        out.append(f"{r['date']} ${r['amountCents'] / 100:,.2f} ticket {r['ticket'] or '-'} (PayHOA {r['transactionId']})")
        out.extend(f"    - {f}" for f in r["findings"])
    if result["portalPaymentsNotInPayhoa"]:
        out.append("Portal payments not in PayHOA:")
        for p in result["portalPaymentsNotInPayhoa"][-limit:]:
            out.append(f"  {p['date']} ${p['amountCents'] / 100:,.2f} {p['property']} tickets {', '.join(p['tickets'])}")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["verify", "verify_lines", "portal_payments", "vendor_transactions"]
