"""The association's counterparties across its records: who writes to it, who it pays, and what kind of source each is.

Reads the sorted mail (``data/mail/items.json``) and the PayHOA transactions (``data/payhoa/transactions.json``)
against ``Mystique.senders()``:

- per named sender: its kind, level, and role; the letters it sent, by kind, and the latest; the PayHOA
  payments to it (by its vendor name, or its words in the bank line) and their total;
- the PayHOA vendors the specification does not name yet, and named senders whose vendor name PayHOA
  does not list;
- the letterheads no rule could name, most recent first: the next senders to add;
- other community associations the mail names: mail for another association in the box, or an agency's
  record for one of Mystique's accounts under another association's name.

It reads disk only and records nothing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jason.community.sources import SourceKind, fold


MONEY_IN_WORDS = ("FEDWIRE CREDIT", "DEPOSIT", "TRANSFER FROM", "CREDIT RETURN")


def money_in(tx: dict[str, Any]) -> bool:
    """A transaction that brought money in (a wire, a deposit, a transfer from another account), whatever its sign."""
    if int(tx.get("originalAmount") or tx.get("amount") or 0) < 0:
        return True
    return any(word in str(tx.get("description") or "").upper() for word in MONEY_IN_WORDS)


def _payments(data_dir: Path, community: Any) -> dict[str, dict[str, Any]]:
    """PayHOA money out, by named sender: payments and total cents, matched by vendor name or the sender's words."""
    path = Path(data_dir) / "payhoa" / "transactions.json"
    if not path.is_file():
        return {}
    snap = json.loads(path.read_text(encoding="utf-8"))
    vendors = {int(k): v for k, v in snap.get("vendors", {}).items()}
    by_vendor = {s.payhoa_vendor: s for s in community.senders() if s.payhoa_vendor}
    found: dict[str, dict[str, Any]] = {}
    for tx in snap.get("transactions", []):
        if int(tx.get("originalAmount") or tx.get("amount") or 0) <= 0 or tx.get("deletedAt"):
            continue
        # Money coming in (a wire, a deposit, a transfer from another account) is not a payment to the sender.
        if money_in(tx):
            continue
        sender = by_vendor.get(vendors.get(int(tx.get("vendorId") or 0), ""))
        if sender is None:
            text = fold(str(tx.get("description") or ""))
            sender = next((s for s in community.senders() if any(fold(w) in text for w in s.words if len(w) >= 6)), None)
        if sender is None:
            continue
        entry = found.setdefault(sender.name, {"payments": 0, "totalCents": 0, "latest": ""})
        entry["payments"] += 1
        entry["totalCents"] += int(tx.get("amount") or 0)
        entry["latest"] = max(entry["latest"], str(tx.get("transactionDate") or "")[:10])
    return found


def sources_report(data_dir: Path, community: Any) -> dict[str, Any]:
    from jason.tasks.mail import load_items

    items = list(load_items(data_dir).values())
    paid = _payments(data_dir, community)
    rows = []
    for sender in community.senders():
        letters = [r for r in items if (r.get("source") or {}).get("name") == sender.name]
        kinds: dict[str, int] = {}
        for r in letters:
            kinds[r.get("kind", "")] = kinds.get(r.get("kind", ""), 0) + 1
        money = paid.get(sender.name, {})
        rows.append({"name": sender.name, "kind": sender.kind.value, "level": sender.level.value if sender.level else None,
                     "role": sender.role, "payhoaVendor": sender.payhoa_vendor, "letters": len(letters),
                     "latestLetter": max((r.get("received") or "")[:10] for r in letters) if letters else None,
                     "letterKinds": dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
                     "payments": money.get("payments", 0), "paidCents": money.get("totalCents", 0), "latestPayment": money.get("latest")})
    by_kind: dict[str, int] = {}
    for r in items:
        kind = (r.get("source") or {}).get("kind") or SourceKind.UNKNOWN.value
        by_kind[kind] = by_kind.get(kind, 0) + 1
    vendors_path = Path(data_dir) / "payhoa" / "transactions.json"
    directory = set(json.loads(vendors_path.read_text(encoding="utf-8")).get("vendors", {}).values()) if vendors_path.is_file() else set()
    named_vendors = {s.payhoa_vendor for s in community.senders() if s.payhoa_vendor}
    unknown = sorted(((r.get("received") or "")[:10], r["mailId"], r.get("kind"), (r.get("from") or "")[:70]) for r in items
                     if (r.get("source") or {}).get("kind") == SourceKind.UNKNOWN.value)
    associations: dict[str, list[dict[str, Any]]] = {}
    for r in items:
        for name in (r.get("source") or {}).get("otherAssociations") or []:
            key = fold(name).replace(" ", "")
            associations.setdefault(key, []).append({"name": name, "mailId": r["mailId"], "received": (r.get("received") or "")[:10],
                                                     "from": r.get("from"), "kind": r.get("kind")})
    others = []
    for entries in associations.values():
        entries.sort(key=lambda e: e["received"], reverse=True)
        senders = sorted({e["from"] or "" for e in entries})
        others.append({"association": entries[0]["name"], "letters": len(entries), "latest": entries[0]["received"],
                       "first": entries[-1]["received"], "from": senders[:4], "mailIds": [e["mailId"] for e in entries][:10]})
    others.sort(key=lambda o: (-o["letters"], o["association"]))
    return {
        "found": True,
        "mailBySourceKind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1])),
        "senders": sorted(rows, key=lambda r: (r["kind"], -(r["letters"] + r["payments"]), r["name"])),
        "payhoaVendorsNotNamed": sorted(directory - named_vendors),
        "namedVendorsNotInPayhoa": sorted(named_vendors - directory) if directory else [],
        "unknownLetterheads": [{"received": d, "mailId": m, "kind": k, "letterhead": h} for d, m, k, h in reversed(unknown)][:25],
        "otherAssociations": others,
        "caveats": [
            "A sender is named by the words its letterhead or bank line carries; OCR can hide them, and an unknown letterhead is "
            "a sender to add to mystique/senders.py, not a finding.",
            "Mail naming another association may be misdirected (it belongs to them), or an agency's record for Mystique's account "
            "under their name; read the letter.",
        ],
    }


def dollars(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def report_lines(report: dict[str, Any]) -> list[str]:
    out = ["Mail by kind of source: " + ", ".join(f"{k} {n}" for k, n in report["mailBySourceKind"].items()), ""]
    kind = None
    for row in report["senders"]:
        if not row["letters"] and not row["payments"]:
            continue
        if row["kind"] != kind:
            kind = row["kind"]
            out.append(kind[:1].upper() + kind[1:])
        paid = f"; paid {row['payments']}x {dollars(row['paidCents'])}, latest {row['latestPayment']}" if row["payments"] else ""
        letters = f"{row['letters']} letters, latest {row['latestLetter']}" if row["letters"] else "no letters"
        level = f" ({row['level']})" if row["level"] else ""
        role = f" — {row['role']}" if row["role"] else ""
        out.append(f"  {row['name']}{level}: {letters}{paid}{role}")
    if report["payhoaVendorsNotNamed"]:
        out.append("")
        out.append("PayHOA vendors the specification does not name yet: " + ", ".join(report["payhoaVendorsNotNamed"]))
    if report["otherAssociations"]:
        out.append("")
        out.append("Other associations the mail names")
        for o in report["otherAssociations"]:
            span = o["latest"] if o["first"] == o["latest"] else f"{o['first']} to {o['latest']}"
            out.append(f"  {o['association']}: {o['letters']} letters, {span}; from {', '.join(f for f in o['from'] if f)[:80]}")
    if report["unknownLetterheads"]:
        out.append("")
        out.append(f"Letterheads no rule names ({len(report['unknownLetterheads'])} shown, newest first)")
        for u in report["unknownLetterheads"][:12]:
            out.append(f"  {u['received']} mail {u['mailId']} {u['kind']}: {u['letterhead']}")
    out.append("")
    out.extend(f"* {c}" for c in report["caveats"])
    return out


__all__ = ["sources_report", "report_lines", "money_in"]
