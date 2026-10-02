"""The mail joined to jason's other records: where each sender still writes, escrow clocks, tax bills,
bank balances, and checks.

Each check reads a kind of letter against a store jason already keeps, so a letter is not only filed
but tested:

- **Address audit**: the addressee block of every letter against ``Mystique.mail_addresses()``. A sender
  still writing to the prior manager or to the property has an old address on file; a letter addressed
  "in care of" someone names who that sender thinks receives the association's mail.
- **Escrow requests**: Civil Code 4530(a)(1) gives the association 10 days from the mailing or delivery
  of a written request to provide the documents. The clock here starts on the day PostScanMail received
  the letter (delivery); a request mailed earlier started sooner.
- **Tax bills**: each parcel a county bill names, against the bill ``jason sync-tax`` stored for it: is the
  stored bill's total, or an installment, printed on the letter?
- **Bank statements**: the statement date, account ending, and ending balance each statement prints.
- **Checks**: the amounts a check prints, against the PayHOA deposits of the same amount in the 45 days
  after it arrived, and the category each deposit was booked to.

Readings are evidence. Jason does not respond to a request, pay a bill, or change an address.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from jason.community.invoices import money_values
from jason.postscanmail.models import AddressKind, MailKind, address_of, care_of
from jason.tasks.mail import load_items, mail_dir

ESCROW_DAYS = 10
CHECK_WINDOW_DAYS = 45


def _text(data_dir: Path, mail_id: str) -> str:
    path = mail_dir(data_dir) / mail_id / "text.txt"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _received(row: dict[str, Any]) -> date | None:
    return date.fromisoformat(row["received"][:10]) if row.get("received") else None


def address_audit(data_dir: Path, community: Any, *, months: int = 18, today: date | None = None) -> dict[str, Any]:
    """Each letter's addressee against the addresses of record; the recent letters that went to an old address."""
    day = today or date.today()
    since = (day - timedelta(days=months * 31)).isoformat()
    counts: dict[str, int] = {}
    old: list[dict[str, Any]] = []
    in_care: list[dict[str, Any]] = []
    for row in load_items(data_dir).values():
        text = _text(data_dir, row["mailId"])
        if not text:
            continue
        kind, label, block = address_of(text, community.mail_addresses())
        counts[kind.value] = counts.get(kind.value, 0) + 1
        if (row.get("received") or "") < since:
            continue
        entry = {"mailId": row["mailId"], "received": row["received"][:10], "from": row.get("from") or row.get("sender"),
                 "kind": row.get("kind"), "address": kind.value if kind is AddressKind.INCOMPLETE else (label or kind.value),
                 "block": block[:160]}
        if kind in (AddressKind.FORMER_MANAGER, AddressKind.PROPERTY, AddressKind.INCOMPLETE):
            old.append(entry)
        who = care_of(block)
        # "Care of: PMB 188" is the association's own box, not a third party.
        if who and not re.match(r"(?i)p\W?[mn]\W?b\b|mystique", who):
            in_care.append({**entry, "careOf": who})
    old.sort(key=lambda e: e["received"], reverse=True)
    return {"counts": counts, "since": since, "oldAddress": old, "inCareOf": in_care}


CURRENT_ZIP = "95814"
_OWN_NAME = re.compile(r"(?i)mystique\s+community\s+assoc(?:iation)?")
_SERVICE = re.compile(r"(?i)location:\s*$|service\s+address:?\s*$|premises:?\s*$")


def account_addresses(community: Any, roots: dict | None) -> list[dict[str, Any]]:
    """The mailing address each utility account's latest bill prints, against the addresses of record.

    A bill prints the association's name at the service location ("Location: 3000 MACON DR") and in its mailing block;
    the mailing block is the name followed by an address that is not a service location or a parcel's premise line.
    """
    from jason.postscanmail.models import AddressKind, classify_address
    from jason.tasks.utilities import bill_files, pdf_text

    if not roots:
        return []
    latest: dict[tuple[str, str], Path] = {}
    for utility, account, path in bill_files(roots):
        latest[(utility.name, account)] = path
    rank = {AddressKind.CURRENT: 0, AddressKind.INCOMPLETE: 1, AddressKind.FORMER_MANAGER: 2, AddressKind.PROPERTY: 3}
    found = []
    for (provider, account), path in sorted(latest.items()):
        try:
            text = pdf_text(path)
        except Exception:
            continue
        blocks = []
        for m in _OWN_NAME.finditer(text):
            if _SERVICE.search(text[max(0, m.start() - 30):m.start()]):
                continue
            block = " ".join(text[m.end():m.end() + 90].split())
            # A premise line ("3000 MACON DR - Condominium 201-1170-018-0000") is the service location, not the mailing address.
            if re.search(r"(?i)condominium|\b\d{3}-\d{4}-\d{3}-\d{4}\b|^\s*account", block):
                continue
            kind, label = classify_address(block, community.mail_addresses())
            if kind in rank:
                blocks.append((rank[kind], kind, label, block))
        if not blocks:
            continue
        _r, kind, label, block = min(blocks, key=lambda b: b[0])
        problems = [] if kind is AddressKind.CURRENT else [kind.value]
        # The box's ZIP: a mistyped one ("95841" for "95814") can send the bill elsewhere.
        if kind in (AddressKind.CURRENT, AddressKind.INCOMPLETE):
            zips = re.findall(r"\b(9\d{4})\b", block)
            if zips and zips[0] != CURRENT_ZIP:
                problems.append(f"ZIP {zips[0]}, not {CURRENT_ZIP}")
        found.append({"provider": provider, "account": account, "bill": path.name, "address": "; ".join(problems) or kind.value,
                      "label": label, "block": block[:90], "ok": not problems})
    return found


def escrow_clocks(data_dir: Path, *, today: date | None = None) -> list[dict[str, Any]]:
    """Each escrow or title request with the 10-day window Civil Code 4530(a)(1) sets, counted from arrival."""
    day = today or date.today()
    found = []
    for row in load_items(data_dir).values():
        if row.get("kind") != MailKind.ESCROW.value or not _received(row):
            continue
        # Another association's request (it never names Mystique) starts no clock for this association.
        if (row.get("source") or {}).get("misdirected"):
            continue
        due = _received(row) + timedelta(days=ESCROW_DAYS)
        facts = row.get("facts") or {}
        found.append({"mailId": row["mailId"], "received": row["received"][:10], "from": row.get("from") or row.get("sender"),
                      "parcels": facts.get("ourParcels") or facts.get("parcels") or [], "escrows": facts.get("escrows") or [],
                      "dueBy": due.isoformat(), "daysLeft": (due - day).days, "open": due >= day})
    return sorted(found, key=lambda e: e["received"], reverse=True)


_BILL_NUMBER = re.compile(r"(?i)bill\s+number\W{0,3}(\d{8,11})")


def _stored_bill(bills, printed: str):
    """The stored bill a letter's bill number names: "24409890" is year 2024's bill "20240409890"."""
    for bill in bills:
        number = str(bill.number or "")
        if number == printed or (len(printed) == 8 and number.startswith("20" + printed[:2]) and number.endswith(printed[2:])):
            return bill
    return None


def delinquency_notices(data_dir: Path) -> list[dict[str, Any]]:
    """Each county notice of delinquent taxes, with the bill it names and whether the stored bill is paid now."""
    from jason.community.tax_store import TaxStore

    store_path = Path(data_dir) / "tax.db"
    found = []
    rows = [r for r in load_items(data_dir).values() if "delinquent" in " ".join(r.get("evidence") or []).lower()
            or "judicial foreclosure" in " ".join(r.get("evidence") or []).lower()]
    if not rows or not store_path.is_file():
        return found
    with TaxStore(store_path) as store:
        for row in rows:
            text = _text(data_dir, row["mailId"])
            printed = _BILL_NUMBER.search(text)
            for parcel in (row.get("facts") or {}).get("ourParcels") or []:
                account = store.get(parcel)
                bill = _stored_bill(account.bills if account else (), printed.group(1)) if printed else None
                paid = bill is not None and bill.balance_cents == 0 and (bill.payments_cents or 0) >= (bill.total_cents or 0) > 0
                found.append({"mailId": row["mailId"], "received": row["received"][:10], "parcel": parcel,
                              "billNumber": printed.group(1) if printed else None, "storedBill": bill.number if bill else None,
                              "billYear": bill.year if bill else None, "totalCents": bill.total_cents if bill else None,
                              "balanceCents": bill.balance_cents if bill else None, "paidNow": paid})
    return sorted(found, key=lambda e: (e["received"], e["parcel"]), reverse=True)


def tax_bill_checks(data_dir: Path) -> list[dict[str, Any]]:
    """Each county tax bill by mail against the stored bill for its parcel."""
    from jason.community.tax_store import TaxStore

    store_path = Path(data_dir) / "tax.db"
    if not store_path.is_file():
        return []
    found = []
    with TaxStore(store_path) as store:
        for row in load_items(data_dir).values():
            if row.get("kind") != MailKind.TAX_BILL.value:
                continue
            amounts = set(money_values(_text(data_dir, row["mailId"])))
            for parcel in (row.get("facts") or {}).get("ourParcels") or []:
                account = store.get(parcel)
                bills = account.bills if account else ()
                if not bills:
                    found.append({"mailId": row["mailId"], "received": row["received"][:10], "parcel": parcel, "stored": None,
                                  "finding": "no stored bill for this parcel; run jason sync-tax"})
                    continue
                # The bill number the letter prints (by the parcel in the header, or labeled), else any stored year's bill
                # whose total or an installment the letter prints.
                text = _text(data_dir, row["mailId"])
                apn = f"{parcel[:3]}-{parcel[3:7]}-{parcel[7:10]}-{parcel[10:]}"
                printed = re.search(re.escape(apn) + r"\s+(\d{8})\b", text) or _BILL_NUMBER.search(text)
                match = _stored_bill(bills, printed.group(1)) if printed else None
                how = "bill number" if match else ""
                if match is None:
                    for bill in bills:
                        total = bill.total_cents or 0
                        if total and (total in amounts or total // 2 in amounts or (total + 1) // 2 in amounts):
                            match, how = bill, "amount"
                            break
                paid = match is not None and match.balance_cents == 0 and (match.payments_cents or 0) >= (match.total_cents or 0) > 0
                found.append({"mailId": row["mailId"], "received": row["received"][:10], "parcel": parcel,
                              "billYear": match.year if match else None, "storedTotalCents": match.total_cents if match else None,
                              "matchedBy": how, "paidNow": paid, "shown": match is not None,
                              "finding": "" if match else "neither a stored bill's number nor its total or installment is printed on "
                                                          "this letter (a supplemental or corrected bill, a notice, or an OCR misread)"})
    return sorted(found, key=lambda e: (e["received"], e["parcel"]), reverse=True)


_STATEMENT_DATE = re.compile(r"(?i)statement\s+date\D{0,20}(\d{1,2}/\d{1,2}/\d{2,4})")
_ENDING = re.compile(r"(?i)ending\s+(?:account\s+)?balance\D{0,40}?(\d{1,2}/\d{1,2}/\d{2,4})?\D{0,20}?\$\s?([\d,]+\.\d\d)")
# A masked account number ("******3118", "XXXX3118", "#4043" after OCR), or "Account Number Ending In 8253".
_ACCOUNT_END = re.compile(r"(?:[*xX#]{2,}\s?(\d{4})\b|ending\s+in\s+(\d{4})\b)", re.I)


def bank_statements(data_dir: Path) -> list[dict[str, Any]]:
    """Each bank statement by mail: statement date, account ending, and the ending balance it prints."""
    found = []
    for row in load_items(data_dir).values():
        if row.get("kind") != MailKind.BANK.value:
            continue
        text = _text(data_dir, row["mailId"])
        when = _STATEMENT_DATE.search(text)
        ending = _ENDING.search(text)
        accounts = sorted({a or b for a, b in _ACCOUNT_END.findall(text)})
        found.append({"mailId": row["mailId"], "received": row["received"][:10], "from": row.get("from") or row.get("sender"),
                      "statementDate": when.group(1) if when else None, "accounts": accounts,
                      "endingBalanceCents": money_values("$" + ending.group(2))[0] if ending else None})
    return sorted(found, key=lambda e: e["received"], reverse=True)


def check_deposits(data_dir: Path) -> list[dict[str, Any]]:
    """Each check by mail against PayHOA deposits of an amount it prints, within 45 days after it arrived."""
    source = Path(data_dir) / "payhoa" / "transactions.json"
    if not source.is_file():
        return []
    snap = json.loads(source.read_text(encoding="utf-8"))
    categories = {int(k): v for k, v in snap["categories"].items()}
    deposits = [t for t in snap["transactions"] if int(t.get("originalAmount") or t.get("amount") or 0) < 0
                or "deposit" in str(t.get("description") or "").lower()]
    found = []
    for row in load_items(data_dir).values():
        if row.get("kind") != MailKind.CHECK.value or not _received(row):
            continue
        amounts = {a for a in money_values(_text(data_dir, row["mailId"])) if a >= 100}
        start, end = _received(row), _received(row) + timedelta(days=CHECK_WINDOW_DAYS)
        matches = []
        for t in deposits:
            day = date.fromisoformat(str(t["transactionDate"])[:10])
            if start - timedelta(days=3) <= day <= end and abs(int(t.get("amount") or 0)) in amounts:
                category = categories.get(int(t.get("categoryId") or 0), {})
                matches.append({"txId": t["id"], "date": day.isoformat(), "amountCents": abs(int(t["amount"])),
                                "category": category.get("name", ""), "categoryType": category.get("type", "")})
        found.append({"mailId": row["mailId"], "received": row["received"][:10], "from": row.get("from") or row.get("sender"),
                      "deposits": matches, "finding": "" if matches else "no PayHOA deposit of an amount this check prints within 45 days"})
    return sorted(found, key=lambda e: e["received"], reverse=True)


def _notice_amount(text: str) -> int:
    """The largest dollar amount a preliminary notice prints, as cents; OCR splits digits ("§ 1 9,377.00")."""
    joined = re.sub(r"(?<=\d) (?=[\d,])", "", text)
    found = [int(m.group(1).replace(",", "")) * 100 + int(m.group(2)) for m in re.finditer(r"[$§S]\s*([\d,]{1,9})\.(\d{2})\b", joined)]
    return max(found, default=0)


def lien_notices(data_dir: Path, community: Any = None) -> list[dict[str, Any]]:
    """Each preliminary notice or lien claim by mail against PayHOA payments to its claimant.

    A 20-day preliminary notice (Civil Code 8200) keeps a claimant's right to record a lien; paying the claimant settles
    it. The claimant is the letter's named sender, or with ``community`` the named sender whose words follow the form's
    "CLAIMANT" line. Payments from 120 days before the notice to a year after count.
    """
    source = Path(data_dir) / "payhoa" / "transactions.json"
    snap = json.loads(source.read_text(encoding="utf-8")) if source.is_file() else {"transactions": [], "vendors": {}}
    vendors = {int(k): v for k, v in snap.get("vendors", {}).items()}
    found = []
    for row in load_items(data_dir).values():
        if row.get("kind") != MailKind.LIEN_NOTICE.value or not _received(row):
            continue
        received = _received(row)
        claimant = (row.get("source") or {}).get("name") or ""
        vendor = (row.get("source") or {}).get("payhoaVendor") or ""
        text = _text(data_dir, row["mailId"])
        amount = _notice_amount(text)
        at = text.upper().find("CLAIMANT")
        if not vendor and community is not None and at >= 0:
            from jason.community.sources import resolve

            named = resolve("", text[at:at + 600], community.senders(), wide=600)[0]
            if named is not None:
                claimant, vendor = named.name, named.payhoa_vendor
        paid = []
        for t in snap["transactions"]:
            if not vendor or vendors.get(int(t.get("vendorId") or 0)) != vendor or t.get("deletedAt"):
                continue
            if int(t.get("originalAmount") or t.get("amount") or 0) <= 0:
                continue
            day = date.fromisoformat(str(t["transactionDate"])[:10])
            if received - timedelta(days=120) <= day <= received + timedelta(days=365):
                paid.append({"txId": t["id"], "date": day.isoformat(), "amountCents": int(t["amount"])})
        total = sum(p["amountCents"] for p in paid)
        if not vendor:
            finding = "claimant not named in the specification; match it to a vendor by hand"
        elif amount and total >= amount:
            finding = "paid in full"
        elif paid:
            finding = "paid in part"
        else:
            finding = "no payment to the claimant found"
        found.append({"mailId": row["mailId"], "received": received.isoformat(), "urgency": row.get("urgency"), "claimant": claimant,
                      "noticeCents": amount, "paidCents": total, "payments": sorted(paid, key=lambda p: p["date"]), "finding": finding})
    return sorted(found, key=lambda e: e["received"], reverse=True)


def mail_links(data_dir: Path, community: Any, *, today: date | None = None, roots: dict | None = None) -> dict[str, Any]:
    """Every join at once, for the brief and the MCP. ``roots`` (the utility bill folders) adds each account's mailing address."""
    return {
        "addresses": address_audit(data_dir, community, today=today),
        "accountAddresses": account_addresses(community, roots),
        "escrow": escrow_clocks(data_dir, today=today),
        "taxBills": tax_bill_checks(data_dir),
        "delinquencyNotices": delinquency_notices(data_dir),
        "bankStatements": bank_statements(data_dir),
        "checks": check_deposits(data_dir),
        "lienNotices": lien_notices(data_dir, community),
        "caveats": [
            "A preliminary notice paid in full leaves no lien right; whether a claim was recorded is the mechanics_liens tool's "
            "question, not the mail's.",
            "The escrow clock starts on the day PostScanMail received the request; Civil Code 4530 counts from mailing or "
            "delivery, so a request mailed earlier started sooner.",
            "An address, balance, or amount is read from OCR'd text; check the PDF before acting on it.",
            "Jason does not answer requests, pay bills, or change an address with a sender.",
        ],
    }


def links_lines(links: dict[str, Any]) -> list[str]:
    out = []
    audit = links["addresses"]
    out.append("Where the mail is addressed: " + ", ".join(f"{k} {n}" for k, n in sorted(audit["counts"].items(), key=lambda kv: -kv[1])))
    if audit["oldAddress"]:
        out.append(f"  Letters since {audit['since']} addressed to an old or incomplete address (give these senders the full current one):")
        seen: set[str] = set()
        for e in audit["oldAddress"]:
            key = f"{(e['from'] or '')[:28]}|{e['address']}"
            if key in seen:
                continue
            seen.add(key)
            out.append(f"    {e['received']} {(e['from'] or '-')[:40]:<40} {e['address']}")
    wrong = [a for a in links.get("accountAddresses") or [] if not a["ok"]]
    if links.get("accountAddresses"):
        out.append(f"  Utility accounts' mailing address on their latest bill: {len(links['accountAddresses']) - len(wrong)} current, {len(wrong)} to fix")
        for a in wrong:
            out.append(f"    {a['provider']} {a['account']}: {a['address']} ({a['block'][:60]})")
    for e in audit["inCareOf"][:8]:
        out.append(f"  {e['received']} {(e['from'] or '-')[:40]:<40} addressed in care of {e['careOf']}")
    if links["escrow"]:
        out.append("")
        out.append("Escrow requests (Civil Code 4530(a)(1): 10 days from delivery)")
        for e in links["escrow"][:10]:
            state = f"{e['daysLeft']} days left" if e["open"] else f"window closed {e['dueBy']}"
            out.append(f"  {e['received']} {(e['from'] or '-')[:34]:<34} parcels {', '.join(e['parcels']) or '-'}; escrow {', '.join(e['escrows'][:1]) or '-'}; {state}")
    misses = [t for t in links["taxBills"] if not t.get("shown")]
    if links["taxBills"]:
        out.append("")
        out.append(f"Tax bills by mail: {len(links['taxBills'])} parcel readings; {len(misses)} do not print the stored bill")
        for t in misses[:8]:
            out.append(f"  {t['received']} parcel {t['parcel']}: {t['finding']}")
    notices = links.get("delinquencyNotices") or []
    if notices:
        out.append("")
        out.append("County notices of delinquent taxes, against the stored bills now")
        for n in notices:
            state = ("paid now" if n["paidNow"] else f"balance ${(n['balanceCents'] or 0) / 100:,.2f}") if n["storedBill"] else "bill not found in the tax store"
            out.append(f"  {n['received']} parcel {n['parcel']} bill {n['billNumber'] or '?'} ({n['billYear'] or '-'}): {state}")
    if links["bankStatements"]:
        out.append("")
        out.append("Bank statements by mail")
        for s in links["bankStatements"][:8]:
            bal = f"${s['endingBalanceCents'] / 100:,.2f}" if s["endingBalanceCents"] is not None else "-"
            out.append(f"  {s['received']} {(s['from'] or '-')[:30]:<30} statement {s['statementDate'] or '-'} account ...{','.join(s['accounts']) or '?'} ending {bal}")
    if links["checks"]:
        out.append("")
        out.append("Checks by mail against PayHOA deposits")
        for c in links["checks"]:
            dep = "; ".join(f"{d['date']} ${d['amountCents'] / 100:,.2f} booked to {d['category'] or 'no category'}" for d in c["deposits"]) or c["finding"]
            out.append(f"  {c['received']} {(c['from'] or '-')[:34]:<34} {dep}")
    if links.get("lienNotices"):
        out.append("")
        out.append("Preliminary notices and lien claims by mail, against payments to the claimant")
        for n in links["lienNotices"]:
            amount = f"${n['noticeCents'] / 100:,.2f}" if n["noticeCents"] else "amount not read"
            out.append(f"  {n['received']} {(n['claimant'] or '-')[:30]:<30} notice {amount}; paid ${n['paidCents'] / 100:,.2f}: {n['finding']}")
    out.append("")
    out.extend(f"* {c}" for c in links["caveats"])
    return out


__all__ = ["address_audit", "escrow_clocks", "tax_bill_checks", "delinquency_notices", "bank_statements", "check_deposits",
           "lien_notices", "mail_links", "links_lines"]
