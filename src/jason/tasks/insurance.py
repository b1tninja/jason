"""Each insurance policy's term, read against the carriers' letters and the premiums PayHOA paid.

The specification (``Mystique.insurance().policies``) is the policy sheet: kind, number and earlier numbers, the end of
the term in force (``renewal``), the carrier, program, and agent, and the PayHOA categories the premium is booked to.
This task joins it to two stores jason already keeps:

- the mail (``data/mail``): each letter that prints one of the policy's numbers, the dates it states, and whether it is a
  renewal bill, a conditional renewal, a non-renewal or cancellation, or a claim;
- PayHOA (``data/payhoa/transactions.json``): money out booked to the policy's categories. A flood payment belongs to the
  building whose NFIP policy number its bank line carries ("IND NAME:MYSTIQUE COMMUNITY ASS 5010000011"), else the
  building its memo or attachment names ("Invoice Flood Bldg 5 24-25.pdf"), else the building whose renewal bill prints
  its amount; one none of those places stays unplaced.
- the email (``data/gmail``, headers only): the agent's, program's, and carrier's messages about a renewal, a proposal,
  or a policy, which is where renewals are negotiated and signed.

Each policy gets a standing: in term, renewal bill received, next term paid, or past its term end with no premium for
the next one. A term runs from 90 days before its start (a premium is often paid ahead) to 275 days after. It reads disk
only; jason buys, renews, and cancels nothing.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from jason.community.invoices import money_values
from jason.tasks.sources import money_in

LEAD_DAYS = 90
# An email about a renewal: its subject or an attachment's name.
RENEWAL_EMAIL = re.compile(r"(?i)renew|proposal|quote|binder|bound|declaration|policy|invoice|premium|\b\d{2}-\d{2}\b")
SOON_DAYS = 60
NOTICE_WORDS = (
    ("conditional renewal", "conditional renewal"),
    ("non-renewal", "non-renewal"),
    ("nonrenewal", "non-renewal"),
    ("notice of cancellation", "cancellation"),
    ("intent to cancel", "cancellation"),
    ("renewal bill", "renewal bill"),
    ("renewal premium", "renewal bill"),
    ("notice of claim", "claim"),
    ("date of loss", "claim"),
)


def fold_number(number: str) -> str:
    """A policy number as OCR and typists vary it: letters and digits only, the letter O read as zero."""
    return re.sub(r"[^A-Z0-9]", "", number.upper()).replace("O", "0")


def _term_start(end: date) -> date:
    try:
        return end.replace(year=end.year - 1)
    except ValueError:
        return end - timedelta(days=365)


def _in_term(day: date, start: date) -> bool:
    return start - timedelta(days=LEAD_DAYS) <= day < start + timedelta(days=365 - LEAD_DAYS)


def _letters(data_dir: Path) -> list[dict[str, Any]]:
    from jason.tasks.mail import load_items, mail_dir

    root = mail_dir(data_dir)
    out = []
    for row in load_items(data_dir).values():
        text_file = root / row["mailId"] / "text.txt"
        text = text_file.read_text(encoding="utf-8") if text_file.is_file() else ""
        printed = {fold_number(n) for n in (row.get("facts") or {}).get("policies") or []}
        out.append({"row": row, "text": text, "folded": fold_number(text), "printed": printed})
    return out


def _notices(text: str) -> list[str]:
    low = text.lower()[:4000]
    found: list[str] = []
    for words, label in NOTICE_WORDS:
        if words in low and label not in found:
            found.append(label)
    return found


def _payments(data_dir: Path) -> tuple[list[dict[str, Any]], str]:
    path = Path(data_dir) / "payhoa" / "transactions.json"
    if not path.is_file():
        return [], ""
    snap = json.loads(path.read_text(encoding="utf-8"))
    categories = {int(k): v.get("name", "") for k, v in snap.get("categories", {}).items()}
    vendors = {int(k): v for k, v in snap.get("vendors", {}).items()}
    out = []
    for t in snap.get("transactions", []):
        amount = int(t.get("originalAmount") or t.get("amount") or 0)
        if amount <= 0 or t.get("deletedAt") or money_in(t):
            continue
        out.append({"txId": t["id"], "date": date.fromisoformat(str(t["transactionDate"])[:10]), "amountCents": int(t.get("amount") or 0),
                    "category": categories.get(int(t.get("categoryId") or 0), ""),
                    "payee": vendors.get(int(t.get("vendorId") or 0)) or str(t.get("description") or "")[:60],
                    # What can name the policy or the building: the bank line, the memo, and the attached files' names.
                    "said": " ".join([str(t.get("description") or ""), str(t.get("memo") or ""),
                                      *[str(a.get("filename") or a.get("name") or "") for a in t.get("attachments") or []]]),
                    "tx": t})
    return out, str(snap.get("syncedAt") or "")[:10]


def _attachment_texts(data_dir: Path, tx: dict[str, Any]) -> list[str]:
    from jason.tasks.invoice_review import best_text, local_attachment

    return [best_text(data_dir, local_attachment(data_dir, tx, raw, {})) for raw in tx.get("attachments") or []]


def _flood_key(policy: Any) -> str:
    return f"{policy.number}|{policy.building.value if policy.building else ''}"


_BUILDING = re.compile(r"(?i)\b(?:bldg|building)\.?\s*#?\s*(\d{1,2})\b")


def flood_policy_named(said: str, policies: list[Any]) -> str | None:
    """The flood policy a payment names: its NFIP number (or a prior number) in the bank line, else "Bldg N" in the memo
    or an attachment's name. None when it names neither, or names two buildings."""
    floods = [p for p in policies if p.kind.name == "FLOOD"]
    folded = fold_number(said)
    by_number = {_flood_key(p) for p in floods for n in p.numbers if len(fold_number(n)) >= 8 and fold_number(n) in folded}
    if len(by_number) == 1:
        return by_number.pop()
    buildings = {int(m) for m in _BUILDING.findall(said)}
    by_building = {_flood_key(p) for p in floods if p.building and int(p.building.value) in buildings}
    return by_building.pop() if len(by_building) == 1 else None


def review(data_dir: Path, community: Any, *, today: date | None = None) -> dict[str, Any]:
    """Every policy's term, letters, notices, premiums, and standing."""
    day = today or date.today()
    letters = _letters(data_dir)
    payments, synced = _payments(data_dir)
    from jason.tasks.gmail import correspondence

    email = correspondence(data_dir, community=community)
    policies = [p for p in community.insurance().policies]
    placed: set[int] = set()
    named = {p["txId"]: key for p in payments if (key := flood_policy_named(p["said"], policies)) is not None}
    # A flood payment whose line and names say nothing: what its attached notice says, read through its OCR text when
    # its text layer is glyph codes (the $1,196 of February 9, 2024 carries building 2's renewal notice, 5010000096).
    flood_categories = {c for p in policies if p.kind.name == "FLOOD" for c in p.premium_categories}
    for p in payments:
        if p["txId"] in named or p["category"] not in flood_categories:
            continue
        said = " ".join(_attachment_texts(data_dir, p["tx"]))
        if said and (key := flood_policy_named(said, policies)) is not None:
            named[p["txId"]] = key
    rows = []
    for policy in policies:
        numbers = {fold_number(n) for n in policy.numbers}
        mine = [l for l in letters if numbers and (numbers & l["printed"] or any(n in l["folded"] for n in numbers if len(n) >= 8))]
        mine.sort(key=lambda l: l["row"].get("received") or "")
        amounts = {a for l in mine for a in money_values(l["text"]) if a >= 1000}
        own = [p for p in payments if p["category"] in policy.premium_categories]
        if policy.kind.name == "FLOOD":
            me = _flood_key(policy)
            # Its number or its building named on the payment wins; the renewal bill's amount only places the rest.
            own = [p for p in own if named.get(p["txId"]) == me or (p["txId"] not in named and p["amountCents"] in amounts)]
            placed.update(p["txId"] for p in own)
        end = policy.renewal
        terms = []
        if end:
            for back in range(0, 3):
                term_end = end.replace(year=end.year - back) if not (end.month == 2 and end.day == 29) else end - timedelta(days=365 * back)
                start = _term_start(term_end)
                paid = [p for p in own if _in_term(p["date"], start)]
                terms.append({"start": start.isoformat(), "end": term_end.isoformat(), "paidCents": sum(p["amountCents"] for p in paid),
                              "payments": [{"date": p["date"].isoformat(), "amountCents": p["amountCents"], "payee": p["payee"]} for p in paid]})
            nxt = [p for p in own if _in_term(p["date"], end)]
        else:
            nxt = []
        letter_rows = []
        for l in mine:
            row = l["row"]
            letter_rows.append({"mailId": row["mailId"], "received": (row.get("received") or "")[:10], "from": row.get("from"),
                                "kind": row.get("kind"), "notices": _notices(l["text"]),
                                "dates": [d["date"] for d in row.get("deadlines") or []]})
        parties = {n for n in (policy.agent, policy.program, policy.carrier) if n}
        start = _term_start(end) if end else None
        mails = [m for m in email if m["sender"] in parties and start and m["at"][:10] >= (start - timedelta(days=LEAD_DAYS)).isoformat()
                 and RENEWAL_EMAIL.search(" ".join([m["subject"], *m["attachments"]]))]
        renewal_mail = [m for m in mails if end and m["at"][:10] >= (end - timedelta(days=120)).isoformat()]
        stated_ends = sorted({d for r in letter_rows if "renewal bill" in r["notices"] or "conditional renewal" in r["notices"]
                              for d in r["dates"]})
        notices = [r for r in letter_rows if set(r["notices"]) & {"conditional renewal", "non-renewal", "cancellation", "claim"}]
        findings: list[str] = []
        if not policy.number:
            standing = "no policy number on the sheet"
        elif end is None:
            standing = "no term end on the sheet"
        elif end > day:
            left = (end - day).days
            if nxt:
                standing = f"in term to {end}; next term paid {nxt[-1]['date']}"
            elif left <= SOON_DAYS:
                bill = [r for r in letter_rows if end.isoformat() in r["dates"]]
                standing = f"renews in {left} days ({end}); " + (f"renewal notice received {bill[-1]['received']}; " if bill else "no renewal notice in the mail; ") + "next term not paid"
            else:
                standing = f"in term to {end} ({left} days)"
        else:
            if nxt:
                standing = f"term ended {end}; next term paid {nxt[-1]['date']}"
            elif renewal_mail:
                last = renewal_mail[-1]
                standing = (f"term ended {end}; renewal handled by email (latest {last['at'][:10]}: {last['subject'][:60]}); "
                            f"no premium for the next term in PayHOA (synced {synced or 'never'})")
                findings.append("Record the new term's number, end date, and premium on the policy sheet once the policy arrives.")
            else:
                standing = f"term ended {end}; no premium for the next term in PayHOA (synced {synced or 'never'})"
                findings.append("Confirm with the agent that the policy renewed, and what it costs now.")
        later = [d for d in stated_ends if end and d > end.isoformat()]
        earlier = [d for d in stated_ends if end and d < end.isoformat() and d > day.isoformat()]
        if earlier:
            findings.append(f"A renewal notice states the term ends {earlier[-1]}, before the sheet's {end}: the sheet may carry the next term's date.")
        if later and not nxt:
            findings.append(f"A letter states {later[-1]}, after the sheet's {end}.")
        for n in notices:
            if "conditional renewal" in n["notices"] and n["received"] >= (_term_start(end).isoformat() if end else ""):
                findings.append(f"Conditional renewal from {n['from']} ({n['received']}): terms change at renewal; read the notice.")
        rows.append({"kind": policy.kind.value, "building": int(policy.building.value) if policy.building else None,
                     "number": policy.number, "priorNumbers": list(policy.prior_numbers), "termEnd": end.isoformat() if end else None,
                     "carrier": policy.carrier, "program": policy.program, "agent": policy.agent, "standing": standing,
                     "findings": findings, "terms": terms,
                     "nextTermPayments": [{"date": p["date"].isoformat(), "amountCents": p["amountCents"]} for p in nxt],
                     "letters": letter_rows[-8:], "letterCount": len(letter_rows), "notices": notices,
                     "email": [{"at": m["at"][:10], "direction": m["direction"], "from": m["sender"], "subject": m["subject"],
                                "attachments": m["attachments"]} for m in mails[-8:]]})
    unplaced = [{"date": p["date"].isoformat(), "amountCents": p["amountCents"], "payee": p["payee"]} for p in payments
                if p["category"] in flood_categories and p["txId"] not in placed and p["date"] >= day - timedelta(days=730)]
    claims = []
    for l in letters:
        if "claim" not in _notices(l["text"]):
            continue
        loss = re.search(r"(?i)date of loss\W{0,5}(\d{1,2}/\d{1,2}/\d{4})", l["text"])
        number = re.search(r"(?i)claim (?:number|no\.?)\W{0,5}([A-Z0-9-]{5,})", l["text"])
        claims.append({"mailId": l["row"]["mailId"], "received": (l["row"].get("received") or "")[:10], "from": l["row"].get("from"),
                       "dateOfLoss": loss.group(1) if loss else None, "claimNumber": number.group(1) if number else None,
                       "policies": sorted(l["printed"])})
    return {
        "found": bool(policies),
        "asOf": day.isoformat(),
        "paymentsSynced": synced,
        "policies": rows,
        "unplacedFloodPayments": unplaced,
        "claims": sorted(claims, key=lambda c: c["received"], reverse=True),
        "caveats": [
            "The policy sheet is the specification; a letter's number or date is a reading until a person confirms it.",
            "A term's premium is what PayHOA booked to the policy's categories between 90 days before the term and 275 days "
            "after; a premium booked elsewhere or paid by the agent is not seen.",
            "A flood payment is placed on the building whose NFIP number its bank line carries, else the building its memo or "
            "attachment names, else the building whose renewal bill prints its amount.",
            "Email is read by its headers: a subject says what a message is about, not what it agreed to.",
            "Jason buys, renews, and cancels nothing, and does not file or answer a claim.",
        ],
    }


def _dollars(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def review_lines(result: dict[str, Any]) -> list[str]:
    out = [f"Insurance as of {result['asOf']} (PayHOA synced {result['paymentsSynced'] or 'never'})", ""]
    for p in result["policies"]:
        label = p["kind"] + (f" building {p['building']}" if p["building"] else "")
        out.append(f"{label}: {p['number'] or '-'}  {p['carrier'] or ''}".rstrip())
        out.append(f"  {p['standing']}")
        paid = [t for t in p["terms"] if t["paidCents"]]
        if paid:
            out.append("  premiums: " + "; ".join(f"{t['start'][:7]} to {t['end'][:7]} {_dollars(t['paidCents'])}" for t in paid))
        for f in p["findings"]:
            out.append(f"  ! {f}")
        for m in p.get("email", [])[-3:]:
            files = f" [{', '.join(m['attachments'][:2])}]" if m["attachments"] else ""
            out.append(f"  email {m['at']} {m['direction']}: {m['subject'][:70]}{files}")
    if result["unplacedFloodPayments"]:
        out.append("")
        out.append("Flood payments nothing places on a building (no NFIP number, building, or renewal bill amount)")
        for u in result["unplacedFloodPayments"]:
            out.append(f"  {u['date']} {_dollars(u['amountCents'])} {u['payee']}")
    if result["claims"]:
        out.append("")
        out.append("Claims in the mail")
        for c in result["claims"]:
            out.append(f"  {c['received']} {c['from'] or '-'}: loss {c['dateOfLoss'] or '?'}, claim {c['claimNumber'] or '?'}, policy {', '.join(c['policies']) or '?'}")
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["review", "review_lines", "fold_number"]
