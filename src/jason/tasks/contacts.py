"""Vendor contacts: what PayHOA's vendor directory has on file against who actually writes from each vendor.

Three sources, read side by side:

- PayHOA's vendor-info report (``data/payhoa/vendor-info.json``, from ``jason contacts --fetch``): each vendor's contact
  name, email, phone, website, and address as PayHOA has them;
- the business email Gmail holds (``data/gmail/correspondence.json``, from ``jason gmail --sync``): every address at a
  vendor's domain, with its display name, first and last date, and counts each way;
- the specification (``mystique/senders.py``): the sender row that names the vendor and the domains it writes from.

A vendor's domains are its sender row's, its PayHOA email's, and its website's. For each vendor the directory shows
the people who wrote from those domains, and what to change: an email PayHOA lacks, an address on file that never
appears in the email, a contact name no message carries, or a domain the sender row does not list. A domain with
business email that no vendor claims is matched to a PayHOA vendor by name where the words agree, and otherwise listed.

It reads disk only. PayHOA is changed by a person; jason writes nothing there.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from jason.tasks.gmail import PERSONAL, contacts as gmail_contacts
from jason.tasks.sources import money_in

VENDOR_INFO = "vendor-info.json"
# Mailboxes that are a department, not a person: shown, but never proposed as the contact name.
ROLE_BOXES = ("accounting", "billing", "ar", "info", "office", "admin", "service", "support", "noreply", "no-reply", "donotreply",
              "invoices", "invoice", "payments", "claims", "customerservice", "notifications", "mailer", "hello", "contact")
_STOP = {"inc", "llc", "co", "company", "the", "services", "service", "and", "of", "corp", "corporation", "pc", "group", "ltd"}


def fetch(client: Any, org_id: int, data_dir: Path) -> Path:
    """Save PayHOA's vendor-info report (read-only)."""
    data = client.vendor_info(org_id)
    path = Path(data_dir) / "payhoa" / VENDOR_INFO
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return path


def _rows(data_dir: Path) -> list[dict[str, Any]]:
    path = Path(data_dir) / "payhoa" / VENDOR_INFO
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows") if isinstance(data, dict) else data
    return [r for r in rows or [] if isinstance(r, dict) and (r.get("vendorName") or r.get("name"))]


def _domain_of(value: str) -> str:
    value = (value or "").strip().lower()
    if "@" in value:
        return value.rsplit("@", 1)[-1]
    host = re.sub(r"^[a-z]+://", "", value).split("/")[0]
    return host[4:] if host.startswith("www.") else host


def _words(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", name.lower()) if len(w) >= 3 and w not in _STOP}


def _last_payments(data_dir: Path) -> dict[str, str]:
    path = Path(data_dir) / "payhoa" / "transactions.json"
    if not path.is_file():
        return {}
    snap = json.loads(path.read_text(encoding="utf-8"))
    vendors = {int(k): v for k, v in snap.get("vendors", {}).items()}
    last: dict[str, str] = {}
    for t in snap.get("transactions", []):
        name = vendors.get(int(t.get("vendorId") or 0))
        if not name or t.get("deletedAt") or money_in(t) or int(t.get("amount") or 0) <= 0:
            continue
        day = str(t.get("transactionDate") or "")[:10]
        last[name] = max(last.get(name, ""), day)
    return last


def _person(contact: dict[str, Any]) -> bool:
    box = contact["address"].split("@", 1)[0].lower()
    return not any(box == r or box.startswith(r + ".") or box.startswith(r + "_") for r in ROLE_BOXES)


def directory(data_dir: Path, community: Any, *, today: date | None = None) -> dict[str, Any]:
    day = today or date.today()
    rows = _rows(data_dir)
    people = gmail_contacts(data_dir)
    by_domain: dict[str, list[dict[str, Any]]] = {}
    for c in people:
        by_domain.setdefault(c["domain"], []).append(c)
    senders = {s.payhoa_vendor: s for s in community.senders() if s.payhoa_vendor}
    paid = _last_payments(data_dir)
    claimed: set[str] = set()
    vendors = []
    for row in rows:
        name = str(row.get("vendorName") or row.get("name") or "")
        sender = senders.get(name)
        on_file = {"contactName": str(row.get("contactName") or ""), "email": str(row.get("email") or "").strip(),
                   "phone": str(row.get("phone") or ""), "website": str(row.get("website") or "")}
        domains = set(sender.domains if sender else ())
        for value in (on_file["email"], on_file["website"]):
            host = _domain_of(value)
            if host and host not in PERSONAL:
                domains.add(host)
        claimed |= domains
        seen = sorted((c for d in domains for c in by_domain.get(d, [])), key=lambda c: c["last"], reverse=True)
        proposals: list[str] = []
        email = on_file["email"].lower()
        if seen:
            people_seen = [c for c in seen if _person(c)] or seen
            latest = people_seen[0]
            if not email:
                proposals.append(f"PayHOA has no email; {latest['address']} ({', '.join(latest['names'][:1]) or 'no name'}) wrote last on {latest['last'][:10]}")
            elif not any(c["address"] == email for c in seen):
                proposals.append(f"PayHOA's email {email} does not appear in the email; {latest['address']} does (last {latest['last'][:10]})")
            contact = on_file["contactName"].lower()
            if contact and not any(contact in " ".join(c["names"]).lower() for c in seen):
                names = [c["names"][0] for c in people_seen if c["names"]][:3]
                proposals.append(f"PayHOA's contact {on_file['contactName']} is on no message; the people writing are {', '.join(names) or '-'}")
            elif not contact and people_seen[0]["names"] and _person(people_seen[0]):
                proposals.append(f"PayHOA has no contact name; {people_seen[0]['names'][0]} wrote last")
        if sender and seen:
            missing = sorted({c["domain"] for c in seen} - set(sender.domains))
            if missing:
                proposals.append(f"add {', '.join(missing)} to the sender row for {sender.name} in mystique/senders.py")
        if not sender and paid.get(name):
            proposals.append("no sender row names this vendor in mystique/senders.py")
        vendors.append({"vendor": name, "sender": sender.name if sender else "", "onFile": on_file, "domains": sorted(domains),
                        "lastPayment": paid.get(name), "people": [{k: c[k] for k in ("address", "names", "first", "last", "wroteUs", "weWrote")}
                                                                  for c in seen[:6]],
                        "proposals": proposals})
    # Domains with business email that no vendor claims: matched to a vendor by name, else listed.
    names = {str(r.get("vendorName") or r.get("name") or ""): _words(str(r.get("vendorName") or r.get("name") or "")) for r in rows}
    unclaimed = []
    for domain, found in by_domain.items():
        if domain in claimed:
            continue
        label = re.sub(r"[^a-z0-9]", "", domain.split(".")[0])
        match = [n for n, words in names.items() if words and sum(1 for w in words if w in label) >= max(1, min(2, len(words)))]
        count = sum(c["wroteUs"] + c["weWrote"] for c in found)
        unclaimed.append({"domain": domain, "messages": count, "last": max(c["last"] for c in found)[:10],
                          "names": sorted({n for c in found for n in c["names"][:1]})[:4], "vendorByName": match[:1]})
    unclaimed.sort(key=lambda u: (not u["vendorByName"], -u["messages"]))
    active = [v for v in vendors if v["lastPayment"] and v["lastPayment"] >= f"{day.year - 2}"]
    return {
        "found": bool(rows),
        "asOf": day.isoformat(),
        "vendors": sorted(vendors, key=lambda v: (not v["proposals"], v["lastPayment"] is None, -(len(v["people"])), v["vendor"])),
        "activeWithoutEmail": [v["vendor"] for v in active if not v["people"]],
        "unclaimedDomains": unclaimed[:40],
        "caveats": [
            "The email is read by its headers; a person who wrote once is not necessarily the account contact.",
            "A proposal is for a person to make in PayHOA or in mystique/senders.py; jason changes neither.",
            "A department mailbox (accounting@, billing@) is shown but never proposed as a contact name.",
        ],
    }


def directory_lines(result: dict[str, Any]) -> list[str]:
    if not result["found"]:
        return ["No vendor-info report on disk; run jason contacts --fetch."]
    out = [f"Vendor contacts as of {result['asOf']}", ""]
    for v in result["vendors"]:
        if not v["proposals"] and not v["people"]:
            continue
        paid = f", last paid {v['lastPayment']}" if v["lastPayment"] else ""
        out.append(f"{v['vendor']}{paid}")
        f = v["onFile"]
        out.append(f"  on file: {f['contactName'] or '-'} | {f['email'] or '-'} | {f['phone'] or '-'}")
        for c in v["people"][:3]:
            out.append(f"  email:   {', '.join(c['names'][:1]) or '-'} <{c['address']}> {c['first'][:10]} to {c['last'][:10]}, "
                       f"{c['wroteUs']} in / {c['weWrote']} out")
        for p in v["proposals"]:
            out.append(f"  > {p}")
    if result["activeWithoutEmail"]:
        out.append("")
        out.append("Vendors paid in the last two years with no email found: " + ", ".join(result["activeWithoutEmail"]))
    if result["unclaimedDomains"]:
        out.append("")
        out.append("Business domains no vendor claims")
        for u in result["unclaimedDomains"][:25]:
            hint = f" -> PayHOA vendor {u['vendorByName'][0]}?" if u["vendorByName"] else ""
            out.append(f"  {u['domain']}: {u['messages']} messages, last {u['last']}; {', '.join(u['names'][:3])}{hint}")
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["fetch", "directory", "directory_lines"]
