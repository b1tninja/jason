"""Email threads as work: whose move it is, and what else happened around each one.

Reads the message headers ``jason gmail --sync`` stored (``data/gmail/correspondence.json``) and groups them by Gmail
thread. A thread's last message decides whose move it is:

- **awaiting us**: the last message came in and nothing went out after it (never answered, or answered before and
  written to again);
- **awaiting them**: the last message went out, answering or asking, and nothing came back;
- **notice**: an automated sender (no-reply, notifications, a mailer) with nothing asked of us in the subject;
- **internal**: only the association's own addresses.

Each thread is then read beside the association's other records, over its span (14 days before its first message to
60 days after its last):

- payments: the PayHOA payments to the thread's named sender (``Sender.domains``, ``payhoa_vendor``);
- letters: the paper mail from the same sender;
- documents: the invoices and bills among its attachments (``jason copies``) and the payment each is matched to;
- Drive: the files saved from its messages (``jason drive --gmail``);
- owners: for an owner's thread, the PayHOA requests and violations on that owner's unit, with their status.

A correlation is a lead for a person, not a finding: an email and a payment in the same weeks are not proof that one
answered the other. Jason reads mail and sends none; an owner's address is never kept, only the unit it belongs to.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jason.community.topics import topics_of

BEFORE_DAYS = 14
AFTER_DAYS = 60
AUTOMATED = re.compile(r"(?i)^(no-?reply|do-?not-?reply|notifications?|notify|mailer|mailer-daemon|alerts?|updates?|info|news|newsletters?|"
                       r"marketing|email|e-?bills?|billing|billing-noreply|statements?|receipts?|orders?|support|hello|team|"
                       r"account|accounts|security|calendar-notification|drive-shares-dm-noreply|comments-noreply)[@.+_-]")
# Subjects of mail a system sends to say something happened, not to ask anything.
AUTOMATED_SUBJECT = re.compile(r"(?i)\bebill\b|e-bill|one-time passcode|verification code|security alert|recurring payment|"
                               r"payment (?:received|confirmation|scheduled)|your order|order (?:has|is)|newsletter|"
                               r"headlines|webinar|shared with you|invitation:|accepted:|declined:|updated invitation|"
                               r"multi-factor|sign-in|password|^(?:shipped|ordered|delivered|arriving)\b|"
                               r"has been sent out for signature|^[^:]+ between .+ and |performance report|quarterly insights|"
                               r"security risks|open items list|keep your .+ running")
ASKS = re.compile(r"(?i)action required|response needed|please (?:review|sign|respond|confirm|provide|approve)|additional documents|"
                  r"past due|overdue|final notice|request(?:ed)?\b|signature (?:needed|required)|approval (?:needed|required)|"
                  r"new comment")
# A bulk-mail subdomain sends newsletters and receipts: email.cityofsacramento.org, emt.sherwin-williams.com.
BULK_HOST = re.compile(r"(?i)@(?:email|emt|e|em|mail|mailer|news|newsletter|info|marketing|comms|notify|notifications)\.")
REPORT = "threads.json"


def _day(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date() if value else None
    except ValueError:
        return None


def _payments(data_dir: Path) -> list[dict[str, Any]]:
    from jason.tasks.sources import money_in

    path = Path(data_dir) / "payhoa" / "transactions.json"
    if not path.is_file():
        return []
    snap = json.loads(path.read_text(encoding="utf-8"))
    vendors = {int(k): v for k, v in snap.get("vendors", {}).items()}
    return [{"id": int(t["id"]), "date": date.fromisoformat(str(t["transactionDate"])[:10]), "amountCents": int(t.get("amount") or 0),
             "vendor": vendors.get(int(t.get("vendorId") or 0)) or ""}
            for t in snap.get("transactions", []) if not t.get("deletedAt") and not money_in(t) and int(t.get("amount") or 0) > 0]


def _unit_activity(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Requests and violations by unit label, from the PayHOA catalog."""
    path = Path(data_dir) / "payhoa.db"
    if not path.is_file():
        return {}
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    found: dict[str, list[dict[str, Any]]] = {}
    try:
        units = {int(i): label for i, label in conn.execute("SELECT id, label FROM units")}
        for unit_id, form, status, created in conn.execute("SELECT unit_id, form_name, status, created_at FROM requests"):
            found.setdefault(units.get(int(unit_id or 0), ""), []).append(
                {"what": "request", "title": form, "status": status, "date": str(created or "")[:10]})
        for unit_id, title, status, reported in conn.execute("SELECT unit_id, title, status, reported_at FROM violations"):
            found.setdefault(units.get(int(unit_id or 0), ""), []).append(
                {"what": "violation", "title": title, "status": status, "date": str(reported or "")[:10]})
    finally:
        conn.close()
    return found


def _email_documents(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """The documents in the copies catalog that have an email copy, by the message id in the copy's path."""
    path = Path(data_dir) / "reports" / "copies.json"
    if not path.is_file():
        return {}
    found: dict[str, list[dict[str, Any]]] = {}
    for row in json.loads(path.read_text(encoding="utf-8")).get("rows", []):
        for c in [row["best"], *row["others"]]:
            m = re.search(r"gmail[\\/]files[\\/]([^\\/]+)[\\/]", c["ref"])
            if m:
                found.setdefault(m.group(1), []).append({"issuer": row["issuer"], "number": row["number"], "totalCents": row["totalCents"],
                                                         "payment": row["payment"]})
    return found


def _drive_saves(data_dir: Path) -> dict[str, list[str]]:
    path = Path(data_dir) / "drive" / "gmail-links.json"
    if not path.is_file():
        return {}
    found: dict[str, list[str]] = {}
    for link in json.loads(path.read_text(encoding="utf-8")).get("links", []):
        for m in link["messages"]:
            found.setdefault(m["messageId"], []).append(link["drivePath"])
    return found


def status_of(messages: list[dict[str, Any]], today: date) -> tuple[str, int]:
    """(status, days since the last message) for a thread's messages, oldest first."""
    last = messages[-1]
    age = (today - (_day(last["at"]) or today)).days
    parties = {p for m in messages for p in m.get("parties") or []}
    if parties <= {"association"}:
        return "internal", age
    def automated(m: dict[str, Any]) -> bool:
        senders = [p[1] for p in m.get("people") or [] if p[2] == "from"]
        return m["direction"] == "in" and (any(AUTOMATED.match(a) or BULK_HOST.search(a) for a in senders)
                                           or bool(AUTOMATED_SUBJECT.search(m.get("subject", ""))))

    if all(automated(m) for m in messages) and not any(ASKS.search(m.get("subject", "")) for m in messages):
        return "notice", age
    if last["direction"] == "in":
        return "awaiting us", age
    return "awaiting them", age


def threads(data_dir: Path, community: Any, *, today: date | None = None) -> dict[str, Any]:
    from jason.tasks.gmail import CORRESPONDENCE, _load, sender_of
    from jason.tasks.mail import load_items

    day = today or date.today()
    messages = _load(data_dir, CORRESPONDENCE).get("messages") or []
    senders = tuple(community.senders())
    rules = tuple(getattr(community, "topic_rules", lambda: ())())
    payments = _payments(data_dir)
    letters = list(load_items(data_dir).values())
    units = _unit_activity(data_dir)
    documents = _email_documents(data_dir)
    saves = _drive_saves(data_dir)
    by_thread: dict[str, list[dict[str, Any]]] = {}
    for m in messages:
        by_thread.setdefault(m["threadId"], []).append(m)
    rows = []
    for thread_id, items in by_thread.items():
        items.sort(key=lambda m: m["at"])
        status, age = status_of(items, day)
        first, last = _day(items[0]["at"]), _day(items[-1]["at"])
        lo, hi = (first or day) - timedelta(days=BEFORE_DAYS), (last or day) + timedelta(days=AFTER_DAYS)
        domains = sorted({d for m in items for d in m.get("domains") or []})
        named = sender_of(domains, senders)
        parties = sorted({p for m in items for p in m.get("parties") or []} - {"association"})
        related: dict[str, Any] = {}
        if named is not None and named.payhoa_vendor:
            paid = [p for p in payments if p["vendor"] == named.payhoa_vendor and lo <= p["date"] <= hi]
            if paid:
                related["payments"] = [{"date": p["date"].isoformat(), "amountCents": p["amountCents"], "txId": p["id"]} for p in paid[:8]]
        if named is not None:
            mail = [r for r in letters if (r.get("source") or {}).get("name") == named.name
                    and r.get("received") and lo <= date.fromisoformat(r["received"][:10]) <= hi]
            if mail:
                related["letters"] = [{"mailId": r["mailId"], "received": r["received"][:10], "kind": r.get("kind")} for r in mail[:8]]
        docs = [d for m in items for d in documents.get(m["messageId"], [])]
        if docs:
            related["documents"] = docs[:8]
        saved = sorted({p for m in items for p in saves.get(m["messageId"], [])})
        if saved:
            related["drive"] = saved[:8]
        for party in parties:
            if party.startswith("owner of "):
                for label in party[len("owner of "):].split(", "):
                    near = [a for a in units.get(label, []) if a["date"] and lo.isoformat() <= a["date"] <= hi.isoformat()]
                    if near:
                        related.setdefault("unit", []).extend({**a, "unit": label} for a in near)
        rows.append({"threadId": thread_id, "subject": items[0].get("subject") or "(no subject)", "status": status, "ageDays": age,
                     "first": items[0]["at"][:10], "last": items[-1]["at"][:10], "messages": len(items),
                     "inbound": sum(1 for m in items if m["direction"] == "in"), "outbound": sum(1 for m in items if m["direction"] == "out"),
                     "sender": named.name if named else "", "senderKind": named.kind.value if named else "",
                     "parties": parties[:6], "domains": domains[:6],
                     "topics": [t.value for t in topics_of(" | ".join([*{m.get("subject") or "" for m in items},
                                                                       *{a for m in items for a in m.get("attachments") or []}]), rules)],
                     "attachments": sorted({a for m in items for a in m.get("attachments") or []})[:10],
                     "link": f"https://mail.google.com/mail/u/0/#all/{thread_id}", "related": related})
    order = {"awaiting us": 0, "awaiting them": 1, "notice": 2, "internal": 3}
    rows.sort(key=lambda r: (order.get(r["status"], 9), -int(r["last"].replace("-", "") or 0)))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    result = {
        "found": bool(rows),
        "asOf": day.isoformat(),
        "threads": len(rows),
        "byStatus": counts,
        "rows": rows,
        "caveats": [
            "Whose move it is comes from the last message's direction; a reply by phone, in person, or from another mailbox "
            "is not seen, so an 'awaiting us' thread may already be handled.",
            "A payment, letter, request, or violation in the same weeks is a lead, not proof that it answered the thread.",
            "An owner's address is never stored; an owner's thread names only the unit PayHOA links to that address.",
        ],
    }
    out = Path(data_dir) / "reports" / REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def thread_lines(result: dict[str, Any], *, status: str = "", days: int = 120, limit: int = 40, party: str = "") -> list[str]:
    out = [f"{result['threads']} threads as of {result['asOf']}: " + ", ".join(f"{k} {n}" for k, n in result["byStatus"].items()), ""]
    shown = 0
    for r in result["rows"]:
        if status and r["status"] != status:
            continue
        # One party's threads ("3024 MACON", "LaBarre"): its unit or domain, or the named sender.
        if party and not any(party.lower() in p.lower() for p in [*r["parties"], r["sender"], *r["domains"]]):
            continue
        if not status and r["status"] in ("notice", "internal"):
            continue
        if r["ageDays"] > days:
            continue
        who = r["sender"] or ", ".join(r["parties"][:2]) or "-"
        out.append(f"[{r['status']}, {r['ageDays']}d] {r['last']} {who[:40]}: {r['subject'][:70]} ({r['messages']} msgs)")
        rel = r["related"]
        if rel.get("payments"):
            p = rel["payments"][-1]
            out.append(f"    payments: {len(rel['payments'])}, latest {p['date']} ${p['amountCents'] / 100:,.2f}")
        if rel.get("letters"):
            out.append(f"    letters: {', '.join(l['received'] for l in rel['letters'][:3])}")
        if rel.get("documents"):
            d = rel["documents"][0]
            paid = (d.get("payment") or {}).get("how", "no payment found")
            out.append(f"    documents: {d['issuer'] or '-'} {d['number'] or ''} (payment {paid})")
        if rel.get("drive"):
            out.append(f"    saved to Drive: {rel['drive'][0]}" + (f" (+{len(rel['drive']) - 1})" if len(rel["drive"]) > 1 else ""))
        for a in rel.get("unit", [])[:3]:
            out.append(f"    {a['unit']}: {a['what']} {a['title'][:40]} ({a['status']}, {a['date']})")
        shown += 1
        if shown >= limit:
            break
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["threads", "thread_lines", "status_of"]
