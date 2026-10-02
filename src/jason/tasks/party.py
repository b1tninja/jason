"""Views across every store, by party and by what is waiting: the helpers behind ``jason party``, ``topics``,
``new-owners``, and ``open-items``.

- ``thread_topics``: what the association hears about, by topic (``Mystique.topic_rules()``): threads, units, recent
  and open ones; a topic three or more units raised in a year is a candidate for a notice or the new-owner packet.
- ``new_owners``: each unit whose latest deed recorded in the window, with the buyer's threads and topics, whether a
  PayHOA member holds the unit, its balance, and its requests.
- ``open_items``: what is waiting on the association: threads awaiting us, PayHOA requests pending, deadlines due or
  overdue, insurance findings, mail delivered and not scanned, letters to act on, and lien notices not paid.
- ``party_brief``: one unit (by address) or one counterparty (by name or domain) across the stores: the unit's owners
  by deed, PayHOA standing, requests, violations, threads, and letters; the counterparty's payments by year,
  documents and their payments, threads, letters, contacts, and the Drive files saved from its email.

Each reads what the other tasks saved and repeats their caveats; none changes anything anywhere.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

OPEN = ("awaiting us",)


def _threads(data_dir: Path, community: Any) -> dict[str, Any]:
    from jason.tasks.threads import threads

    return threads(data_dir, community)


def _catalog(data_dir: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """(units by upper-case label with balance and whether a member holds it, requests, violations) from PayHOA."""
    path = Path(data_dir) / "payhoa.db"
    if not path.is_file():
        return {}, [], []
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        units = {int(i): {"label": label.upper(), "balanceCents": bal, "pastDueCents": due, "members": 0}
                 for i, label, bal, due in conn.execute("SELECT id, label, balance, past_due_balance FROM units")}
        for (raw,) in conn.execute("SELECT raw_json FROM people"):
            try:
                owners = json.loads(raw or "{}").get("owners") or []
            except json.JSONDecodeError:
                owners = []
            for o in owners:
                unit = units.get(int(o.get("unitId") or 0))
                if unit is not None and not o.get("deletedAt"):
                    unit["members"] += 1
        requests = [{"unit": units.get(int(u or 0), {}).get("label", ""), "form": f, "status": s, "created": str(c or "")[:10], "id": i}
                    for i, u, f, s, c in conn.execute("SELECT id, unit_id, form_name, status, created_at FROM requests")]
        violations = [{"unit": units.get(int(u or 0), {}).get("label", ""), "title": t, "status": s, "reported": str(r or "")[:10]}
                      for u, t, s, r in conn.execute("SELECT unit_id, title, status, reported_at FROM violations")]
    finally:
        conn.close()
    return {u["label"]: u for u in units.values()}, requests, violations


def _unit_of(parties: list[str]) -> list[str]:
    """The unit labels an owner's, former owner's, or buyer's party label names."""
    found = []
    for p in parties:
        m = re.match(r"(?:owner|buyer|former owner) of (.+?)(?: \(conveyed [\d-]+\))?$", p)
        if m:
            found.extend(label.strip() for label in m.group(1).split(", "))
    return found


def thread_topics(data_dir: Path, community: Any, *, today: date | None = None, since_days: int = 365) -> dict[str, Any]:
    day = today or date.today()
    result = _threads(data_dir, community)
    since = (day - timedelta(days=since_days)).isoformat()
    recent = (day - timedelta(days=90)).isoformat()
    topics: dict[str, dict[str, Any]] = {}
    for r in result["rows"]:
        if r["status"] in ("notice", "internal"):
            continue
        units = _unit_of(r["parties"])
        for t in r.get("topics") or []:
            e = topics.setdefault(t, {"topic": t, "threads": 0, "inYear": 0, "last90Days": 0, "awaitingUs": 0, "units": set(),
                                      "unitsInYear": set(), "examples": []})
            e["threads"] += 1
            e["inYear"] += int(r["last"] >= since)
            e["last90Days"] += int(r["last"] >= recent)
            e["awaitingUs"] += int(r["status"] in OPEN)
            e["units"].update(units)
            if r["last"] >= since:
                e["unitsInYear"].update(units)
            if len(e["examples"]) < 5 and r["last"] >= recent:
                e["examples"].append({"last": r["last"], "subject": r["subject"][:80], "status": r["status"], "who": r["sender"] or ", ".join(r["parties"][:2])})
    rows = []
    for e in topics.values():
        rows.append({**e, "units": len(e["units"]), "unitsInYear": sorted(e["unitsInYear"]),
                     "faqCandidate": len(e["unitsInYear"]) >= 3})
    rows.sort(key=lambda e: (-e["inYear"], e["topic"]))
    untopiced = sum(1 for r in result["rows"] if r["status"] not in ("notice", "internal") and not r.get("topics"))
    return {"found": bool(rows), "asOf": day.isoformat(), "topics": rows, "threadsWithoutTopic": untopiced,
            "caveats": ["A topic is read from subject words and attachment names; a thread about two things carries two topics, and "
                        "a vague subject ('Hello', 'Couple of questions') carries none.",
                        "A topic three or more units raised in a year is a candidate for a notice, a rule clarification, or the "
                        "new-owner packet; it is not a finding that the rules are unclear."]}


def new_owners(data_dir: Path, community: Any, *, days: int = 365, today: date | None = None) -> dict[str, Any]:
    from jason.tasks.parties import PartyResolver

    day = today or date.today()
    resolver = PartyResolver(data_dir)
    units, requests, violations = _catalog(data_dir)
    result = _threads(data_dir, community)
    since = day - timedelta(days=days)
    rows = []
    for label, recorded in sorted(resolver.latest_deed.items(), key=lambda kv: kv[1], reverse=True):
        if recorded < since:
            continue
        mine = [r for r in result["rows"] if label in _unit_of(r["parties"]) and r["last"] >= (recorded - timedelta(days=60)).isoformat()]
        counts: dict[str, int] = {}
        for r in mine:
            for t in r.get("topics") or ["(no topic)"]:
                counts[t] = counts.get(t, 0) + 1
        unit = units.get(label, {})
        rows.append({"unit": label, "deedRecorded": recorded.isoformat(), "daysOwned": (day - recorded).days,
                     "memberInPayhoa": bool(unit.get("members")), "balanceCents": unit.get("balanceCents"),
                     "pastDueCents": unit.get("pastDueCents"), "threads": len(mine),
                     "awaitingUs": sum(1 for r in mine if r["status"] in OPEN), "topics": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
                     "requests": [r for r in requests if r["unit"] == label and r["created"] >= recorded.isoformat()],
                     "violations": [v for v in violations if v["unit"] == label and v["reported"] >= recorded.isoformat()],
                     "recentThreads": [{"last": r["last"], "subject": r["subject"][:80], "status": r["status"]} for r in mine[:8]]})
    return {"found": bool(resolver.latest_deed), "asOf": day.isoformat(), "days": days, "owners": rows,
            "caveats": ["A new owner is a unit whose latest deed recorded in the window; PayHOA may list the buyer later.",
                        "Threads are the buyer's by the address PayHOA links to the unit, or by the name on the deed, from 60 days "
                        "before the recording; a reply by phone or from another mailbox is not seen."]}


def open_items(data_dir: Path, community: Any, *, days: int = 30, today: date | None = None) -> dict[str, Any]:
    day = today or date.today()
    since = (day - timedelta(days=days)).isoformat()
    items: dict[str, Any] = {}
    result = _threads(data_dir, community)
    try:
        from jason.tasks.replies import reply_needed

        judged = {o["threadId"]: o for o in reply_needed(data_dir, community, today=day, open_days=days)["open"]}
    except Exception:
        judged = {}
    awaiting = []
    for r in result["rows"]:
        if r["status"] not in OPEN or r["last"] < since:
            continue
        j = judged.get(r["threadId"], {})
        awaiting.append({"last": r["last"], "ageDays": r["ageDays"], "who": r["sender"] or ", ".join(r["parties"][:2]),
                         "subject": r["subject"][:90], "topics": r.get("topics") or [], "link": r["link"],
                         "likelyNeedsResponse": j.get("likelyNeedsResponse"), "pastUsualTime": j.get("pastUsualTime"),
                         "replyRate": (j.get("basis") or {}).get("replyRate")})
    # The threads the association's own history says it answers come first.
    awaiting.sort(key=lambda t: (not t["likelyNeedsResponse"], -(t["replyRate"] or 0), -t["ageDays"]))
    items["threadsAwaitingUs"] = awaiting
    _units, requests, _violations = _catalog(data_dir)
    items["requestsPending"] = sorted((r for r in requests if r["status"].lower() == "pending"), key=lambda r: r["created"])
    try:
        from jason.tasks.request_links import request_links

        items["emailedRequests"] = [{"last": d["last"], "unit": d["unit"], "title": d["title"], "form": d["form"], "threadId": d["threadId"]}
                                    for d in request_links(data_dir, community)["drafts"] if d["last"] >= since]
    except Exception:
        items["emailedRequests"] = []
    try:
        from jason.tasks.deadlines import calendar

        items["deadlines"] = [{"name": o["name"], "next": o["next"], "daysLeft": o["daysLeft"], "standing": o["standing"], "note": o.get("note", "")}
                              for o in calendar(data_dir, community, today=day)["obligations"] if o["standing"] in ("overdue", "due soon")]
    except Exception as exc:  # a store missing on disk leaves this list out, not the rest
        items["deadlines"] = [{"name": "deadlines not read", "note": str(exc)[:120]}]
    try:
        from jason.tasks.insurance import review

        items["insurance"] = [{"policy": p["kind"] + (f" building {p['building']}" if p["building"] else ""), "standing": p["standing"], "finding": f}
                              for p in review(data_dir, community, today=day)["policies"] for f in p["findings"]]
    except Exception as exc:
        items["insurance"] = [{"policy": "insurance not read", "finding": str(exc)[:120]}]
    try:
        from jason.tasks.gmail import notice_check

        check = notice_check(data_dir)
        items["mailNotScanned"] = [d for d in check.get("deliveredNotScanned") or [] if d["deliveredAt"][:10] >= (day - timedelta(days=90)).isoformat()]
    except Exception:
        items["mailNotScanned"] = []
    from jason.tasks.mail import load_items

    items["lettersToAct"] = sorted(({"received": r["received"][:10], "from": r.get("from"), "kind": r.get("kind"),
                                     "deadlines": [d["date"] for d in r.get("deadlines") or []], "mailId": r["mailId"]}
                                    for r in load_items(data_dir).values() if r.get("urgency") == "act" and (r.get("received") or "") >= since
                                    and not (r.get("source") or {}).get("misdirected")), key=lambda r: r["received"], reverse=True)
    try:
        from jason.tasks.mail_links import lien_notices

        items["lienNotices"] = [n for n in lien_notices(data_dir, community) if n["finding"] != "paid in full"]
    except Exception:
        items["lienNotices"] = []
    counts = {k: len(v) for k, v in items.items()}
    return {"found": True, "asOf": day.isoformat(), "days": days, "counts": counts, **items,
            "caveats": ["A thread awaiting us may have been answered by phone, in person, or from another mailbox.",
                        "A deadline, insurance, or lien item repeats its own report's caveats: a payment is evidence, not proof.",
                        "Jason answers, pays, and files nothing; each item is for a person."]}


def party_brief(query: str, data_dir: Path, community: Any, *, today: date | None = None) -> dict[str, Any]:
    """One unit (by address) or one counterparty (by name, PayHOA vendor, or email domain) across every store."""
    day = today or date.today()
    q = query.strip().upper()
    units, requests, violations = _catalog(data_dir)
    unit = next((label for label in units if label == q), None) or next((label for label in units if q and q in label), None)
    if unit:
        return _unit_brief(unit, data_dir, community, units, requests, violations, day)
    sender = next((s for s in community.senders() if q in s.name.upper() or q in s.payhoa_vendor.upper()
                   or any(q.lower() == d or q.lower().endswith("." + d) for d in s.domains)), None)
    if sender is not None:
        return _counterparty_brief(sender, data_dir, community, day)
    return {"found": False, "query": query,
            "hint": "a unit address (\"3024 MACON\"), a sender's name, its PayHOA vendor name, or its email domain",
            "units": [label for label in units if any(w in label for w in q.split())][:10]}


def _unit_brief(label: str, data_dir: Path, community: Any, units: dict, requests: list, violations: list, day: date) -> dict[str, Any]:
    from jason.tasks.mail import load_items

    path = Path(data_dir) / "tax.db"
    apn = ""
    if path.is_file():
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            apn = next((a for a, addr in conn.execute("SELECT apn, address FROM accounts") if addr.upper().startswith(label + " ")), "")
        finally:
            conn.close()
    deeds = []
    chain = Path(data_dir) / "ownership.db"
    if apn and chain.is_file():
        conn = sqlite3.connect(f"file:{chain.as_posix()}?mode=ro", uri=True)
        try:
            deeds = [{"recorded": r, "document": n, "grantees": g.replace("\n", "; ")}
                     for r, n, g in conn.execute("SELECT recorded, document_number, grantees FROM chain WHERE apn = ? ORDER BY recorded DESC",
                                                 (re.sub(r"\D", "", apn),))]
        finally:
            conn.close()
    result = _threads(data_dir, community)
    mine = [r for r in result["rows"] if label in _unit_of(r["parties"])]
    letters = [{"received": r["received"][:10], "from": r.get("from"), "kind": r.get("kind"), "mailId": r["mailId"]}
               for r in load_items(data_dir).values()
               if any(label in str(a).upper() for a in (r.get("facts") or {}).get("addresses") or [])
               or (apn and re.sub(r"\D", "", apn) in [re.sub(r"\D", "", p) for p in (r.get("facts") or {}).get("parcels") or []])]
    topics: dict[str, int] = {}
    for r in mine:
        for t in r.get("topics") or []:
            topics[t] = topics.get(t, 0) + 1
    record: dict[str, Any] = {}
    if apn:
        try:
            from jason.mcp.county import unit_brief

            record = unit_brief(apn, data_dir)
        except Exception as exc:  # the county brief needs its own stores; the rest stands without it
            record = {"found": False, "error": str(exc)[:160]}
    u = units.get(label, {})
    return {"found": True, "kind": "unit", "unit": label, "apn": apn, "asOf": day.isoformat(),
            "payhoa": {"balanceCents": u.get("balanceCents"), "pastDueCents": u.get("pastDueCents"), "membersLinked": u.get("members", 0)},
            "deeds": deeds[:6],
            "requests": sorted((r for r in requests if r["unit"] == label), key=lambda r: r["created"], reverse=True),
            "violations": sorted((v for v in violations if v["unit"] == label), key=lambda v: v["reported"], reverse=True),
            "threads": {"count": len(mine), "awaitingUs": sum(1 for r in mine if r["status"] in OPEN), "topics": topics,
                        "recent": [{"last": r["last"], "subject": r["subject"][:80], "status": r["status"], "parties": r["parties"][:2]} for r in mine[:12]]},
            "letters": sorted(letters, key=lambda r: r["received"], reverse=True)[:12],
            "record": record,
            "caveats": ["Threads are the unit's by the owner's address in PayHOA or the name on a deed, as of each message's date.",
                        "The record section is the unit brief with its own caveats: a lien indexes a person, and no value figure is an appraisal."]}


def _counterparty_brief(sender: Any, data_dir: Path, community: Any, day: date) -> dict[str, Any]:
    from jason.tasks.contacts import directory
    from jason.tasks.gmail import contacts as gmail_contacts
    from jason.tasks.mail import load_items
    from jason.tasks.sources import money_in

    by_year: dict[str, dict[str, int]] = {}
    last_payment = None
    path = Path(data_dir) / "payhoa" / "transactions.json"
    if path.is_file() and sender.payhoa_vendor:
        snap = json.loads(path.read_text(encoding="utf-8"))
        vendors = {int(k): v for k, v in snap.get("vendors", {}).items()}
        from jason.community.sources import fold

        words = [fold(w) for w in sender.words if len(w) >= 6]
        for t in snap.get("transactions", []):
            if t.get("deletedAt") or money_in(t) or int(t.get("amount") or 0) <= 0:
                continue
            # The vendor PayHOA books it to, or the sender's words in the bank line ("Good Life Fire Restora CA").
            vendor = vendors.get(int(t.get("vendorId") or 0))
            if vendor != sender.payhoa_vendor and (vendor or not any(w in fold(str(t.get("description") or "")) for w in words)):
                continue
            year = str(t["transactionDate"])[:4]
            e = by_year.setdefault(year, {"payments": 0, "totalCents": 0})
            e["payments"] += 1
            e["totalCents"] += int(t["amount"])
            last_payment = max(last_payment or "", str(t["transactionDate"])[:10])
    documents: list[dict[str, Any]] = []
    copies = Path(data_dir) / "reports" / "copies.json"
    if copies.is_file():
        for r in json.loads(copies.read_text(encoding="utf-8")).get("rows", []):
            if r["issuer"] == sender.name:
                documents.append({"issued": r["issued"], "number": r["number"], "totalCents": r["totalCents"], "channels": r["channels"],
                                  "payment": (r["payment"] or {}).get("how") or "none found"})
    documents.sort(key=lambda d: d["issued"] or "", reverse=True)
    result = _threads(data_dir, community)
    mine = [r for r in result["rows"] if r["sender"] == sender.name]
    letters = [{"received": r["received"][:10], "kind": r.get("kind"), "urgency": r.get("urgency"), "mailId": r["mailId"]}
               for r in load_items(data_dir).values() if (r.get("source") or {}).get("name") == sender.name]
    people = [c for c in gmail_contacts(data_dir) if any(c["domain"] == d or c["domain"].endswith("." + d) for d in sender.domains)]
    on_file = next((v for v in directory(data_dir, community).get("vendors", []) if v["vendor"] == sender.payhoa_vendor), None)
    drive: list[str] = []
    links = Path(data_dir) / "drive" / "gmail-links.json"
    if links.is_file():
        for link in json.loads(links.read_text(encoding="utf-8")).get("links", []):
            if any(any(m.get("from") == d or str(m.get("from", "")).endswith("." + d) for d in sender.domains) for m in link["messages"]):
                drive.append(link["drivePath"])
    return {"found": True, "kind": "counterparty", "name": sender.name, "sourceKind": sender.kind.value, "role": sender.role,
            "payhoaVendor": sender.payhoa_vendor, "domains": list(sender.domains), "asOf": day.isoformat(),
            "payments": {"byYear": dict(sorted(by_year.items())), "last": last_payment},
            "documents": {"count": len(documents), "withoutPayment": sum(1 for d in documents if d["payment"] == "none found"), "recent": documents[:10]},
            "threads": {"count": len(mine), "awaitingUs": sum(1 for r in mine if r["status"] in OPEN),
                        "awaitingThem": sum(1 for r in mine if r["status"] == "awaiting them"),
                        "recent": [{"last": r["last"], "subject": r["subject"][:80], "status": r["status"]} for r in mine[:12]]},
            "letters": sorted(letters, key=lambda r: r["received"], reverse=True)[:12],
            "contacts": {"onFile": (on_file or {}).get("onFile"), "proposals": (on_file or {}).get("proposals", []),
                         "people": sorted(({"name": (c["names"] or [""])[0], "address": c["address"], "last": c["last"][:10],
                                            "wroteUs": c["wroteUs"], "weWrote": c["weWrote"]} for c in people), key=lambda c: c["last"], reverse=True)[:8]},
            "driveSavedFromEmail": sorted(set(drive))[:20],
            "caveats": ["Payments are PayHOA's money out to the vendor name; a transfer in is not a payment.",
                        "A document without a payment may be paid under another vendor name, by the agent, or not yet due.",
                        "Threads and contacts are read from email headers only."]}


def party_lines(brief: dict[str, Any]) -> list[str]:
    if not brief.get("found"):
        return [f"Nothing named {brief.get('query')!r}; try {brief.get('hint')}."] + ([f"  units: {', '.join(brief['units'])}"] if brief.get("units") else [])
    out: list[str] = []
    t = brief["threads"]
    if brief["kind"] == "unit":
        p = brief["payhoa"]
        out.append(f"{brief['unit']} (parcel {brief['apn'] or '?'})")
        bal = f"${(p['balanceCents'] or 0) / 100:,.2f}"
        out.append(f"  PayHOA: balance {bal}, past due ${(p['pastDueCents'] or 0) / 100:,.2f}, {p['membersLinked']} member(s) linked")
        for d in brief["deeds"][:3]:
            out.append(f"  deed {d['recorded']} to {d['grantees'][:60]}")
        for r in brief["requests"][:5]:
            out.append(f"  request {r['created']} {r['form']} ({r['status']})")
        for v in brief["violations"][:5]:
            out.append(f"  violation {v['reported']} {v['title'][:50]} ({v['status']})")
        out.append(f"  email: {t['count']} threads, {t['awaitingUs']} awaiting us; topics " + ", ".join(f"{k} {n}" for k, n in t["topics"].items()))
    else:
        out.append(f"{brief['name']} ({brief['sourceKind']}{', ' + brief['role'] if brief['role'] else ''})")
        years = ", ".join(f"{y} {e['payments']}x ${e['totalCents'] / 100:,.2f}" for y, e in brief["payments"]["byYear"].items())
        out.append(f"  paid: {years or 'nothing in PayHOA'}; last {brief['payments']['last'] or '-'}")
        d = brief["documents"]
        out.append(f"  documents: {d['count']}, {d['withoutPayment']} with no payment found")
        out.append(f"  email: {t['count']} threads, {t['awaitingUs']} awaiting us, {t['awaitingThem']} awaiting them")
        for c in brief["contacts"]["people"][:4]:
            out.append(f"  contact {c['name'] or '-'} <{c['address']}> last {c['last']}")
        for prop in brief["contacts"]["proposals"][:3]:
            out.append(f"  > {prop}")
        if brief["driveSavedFromEmail"]:
            out.append(f"  saved to Drive from its email: {len(brief['driveSavedFromEmail'])} files")
    for r in t["recent"][:8]:
        out.append(f"    {r['last']} [{r['status']}] {r['subject']}")
    for l in brief["letters"][:5]:
        out.append(f"  letter {l['received']} {l['kind']}")
    out.append("")
    out.extend(f"* {c}" for c in brief["caveats"])
    return out


def open_lines(result: dict[str, Any]) -> list[str]:
    out = [f"Open items as of {result['asOf']}: " + ", ".join(f"{k} {n}" for k, n in result["counts"].items()), ""]
    for d in result["deadlines"]:
        out.append(f"[deadline {d.get('standing', '')}] {d['name']}: {d.get('next') or '-'} {d.get('note', '')[:80]}")
    for i in result["insurance"]:
        out.append(f"[insurance] {i['policy']}: {i['finding'][:110]}")
    for l in result["lettersToAct"][:10]:
        out.append(f"[letter] {l['received']} {(l['from'] or '-')[:40]} ({l['kind']}) {', '.join(l['deadlines'][:2])}")
    for n in result["lienNotices"]:
        out.append(f"[lien notice] {n['received']} {n['claimant'] or '-'}: {n['finding']}")
    for r in result["requestsPending"][:15]:
        out.append(f"[request] {r['created']} {r['unit'] or '-'}: {r['form']}")
    for r in result.get("emailedRequests", [])[:15]:
        out.append(f"[emailed request, not in PayHOA] {r['last']} {r['unit']}: {r['title'][:60]} -> {r['form']} ({r['threadId']})")
    for m in result["mailNotScanned"][:10]:
        out.append(f"[mail] delivered {m['deliveredAt'][:10]}, not scanned")
    for t in result["threadsAwaitingUs"][:30]:
        mark = "likely needs a reply, " if t.get("likelyNeedsResponse") else ""
        out.append(f"[email {mark}{t['ageDays']}d] {t['who'][:40]}: {t['subject'][:70]}")
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["thread_topics", "new_owners", "open_items", "party_brief", "party_lines", "open_lines"]
