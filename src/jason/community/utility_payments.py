"""Utility payments in PayHOA against the bills they paid: the right PDF attached, and the payment split by service.

Before jason fetched the bills from the portals and attached them itself,
the bills were attached by hand ("document-0 (12).pdf") and a payment was
sometimes left in one category instead of split into the charges it paid
(domestic water, irrigation, fire service, storm drainage, street
sweeping). This module reads that history. It never changes a transaction:
it says which payment paid which bills, whether the attachment is that bill,
and the split by budget line the bills support. A person makes any change.

A payment is one PayHOA transaction, or, once split, the child rows that
share its parent (PayHOA lists the children and hides the parent). The
bills are the portal downloads in the utility store, plus any attached PDF
the parsers can read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from jason.community.symbols import Utility
from jason.community.utility import Service, UtilityBill

SMUD_WORDS = ("SMUD",)
CITY_WORDS = ("CITY OF SACRAMEN", "CITY OF SACTO")
CITY_RULE, SMUD_RULE = "City of Sacramento", "SMUD"


def identify(text: str) -> tuple[Utility, str] | None:
    """The utility and account a bill's own text names, or None when the text is not a SMUD or City bill."""
    if "Your Electric Bill" in text or ("SMUD" in text and "Electricity Charges" in text):
        found = re.search(r"Account Number:\s*(\d{5,})", text)
        return (Utility.SMUD, found[1]) if found else None
    if "Utility Service Bill" in text or ("City of Sacramento" in text and "Service from" in text):
        found = re.search(r"^\s*(\d{10})\s*$", text, re.M)
        return (Utility.CITY_OF_SACRAMENTO, found[1]) if found else None
    return None


@dataclass(frozen=True)
class PaymentRow:
    tx_id: int
    category: str
    amount_cents: int


@dataclass(frozen=True)
class Attachment:
    attachment_id: int
    tx_id: int
    filename: str
    path: str = ""
    # What the file is: the bill it holds, or the document kind the classifier gave, or why it could not be read.
    bill: UtilityBill | None = None
    kind: str = ""


@dataclass
class Payment:
    key: int
    provider: Utility
    day: date
    amount_cents: int
    description: str
    rows: list[PaymentRow] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)

    @property
    def split(self) -> bool:
        return len(self.rows) > 1


def provider_of(tx: dict[str, Any]) -> Utility | None:
    text = str(tx.get("description") or "").upper()
    rule = str((tx.get("transactionRule") or {}).get("name") or "")
    if rule == SMUD_RULE or any(word in text for word in SMUD_WORDS):
        return Utility.SMUD
    if rule == CITY_RULE or any(word in text for word in CITY_WORDS):
        return Utility.CITY_OF_SACRAMENTO
    return None


def group_payments(transactions: list[dict[str, Any]], categories: dict[int, str],
                   attachments: dict[int, Attachment] | None = None) -> list[Payment]:
    """Utility transactions as payments: a standalone row, or the rows that share one parent. Oldest first."""
    found: dict[int, Payment] = {}
    for tx in transactions:
        provider = provider_of(tx)
        if provider is None or tx.get("deletedAt") or tx.get("excluded"):
            continue
        key = int(tx.get("parentId") or tx["id"])
        day = date.fromisoformat(str(tx["transactionDate"])[:10])
        payment = found.get(key)
        if payment is None:
            payment = found[key] = Payment(key, provider, day, 0, str(tx.get("description") or ""))
        payment.day = min(payment.day, day)
        payment.amount_cents += int(tx.get("amount") or 0)
        payment.rows.append(PaymentRow(int(tx["id"]), categories.get(int(tx.get("categoryId") or 0), str(tx.get("categoryId") or "")),
                                       int(tx.get("amount") or 0)))
        seen = {a.attachment_id for a in payment.attachments}
        for raw in tx.get("attachments") or []:
            ident = int(raw["id"])
            if ident in seen:
                continue
            seen.add(ident)
            known = (attachments or {}).get(ident)
            payment.attachments.append(known or Attachment(ident, int(tx["id"]), str(raw.get("filename") or "")))
    return sorted(found.values(), key=lambda p: (p.day, p.key))


def _subset(candidates: list[UtilityBill], target: int, limit: int = 24) -> list[UtilityBill] | None:
    """The oldest-first set of bills, at most one per account, whose totals sum to the payment."""
    pool = candidates[:limit]
    reach: dict[int, tuple[int, ...]] = {0: ()}
    for index, bill in enumerate(pool):
        if bill.payable_cents <= 0:
            continue
        for total, picked in list(reach.items()):
            new = total + bill.payable_cents
            if new > target or new in reach:
                continue
            if any(pool[i].account == bill.account for i in picked):
                continue
            reach[new] = picked + (index,)
        if target in reach:
            return [pool[i] for i in reach[target]]
    return None


def _catch_up(candidates: list[UtilityBill], target: int) -> list[UtilityBill] | None:
    """Consecutive unpaid bills of one account that sum to the payment: a late payment of two or three months at once."""
    by_account: dict[str, list[UtilityBill]] = {}
    for bill in candidates:
        by_account.setdefault(bill.account, []).append(bill)
    for items in by_account.values():
        for start in range(len(items)):
            total = 0
            for end in range(start, len(items)):
                total += items[end].payable_cents
                if total == target and end > start:
                    return items[start: end + 1]
                if total > target:
                    break
    return None


def match_payments(payments: list[Payment], bills: list[UtilityBill], *, before: int = 80, after: int = 3) -> dict[int, list[UtilityBill]]:
    """Each payment's bills: bills issued up to ``before`` days before it whose totals sum to it.

    The attached bill wins when its total is the payment's; then the unpaid bill of that total closest before the
    payment; then the oldest-first set of unpaid bills, one per account, that sums to it (a combined web payment).
    ``after`` allows only for a posting date a day or two ahead of the bill date. A bill pays once. A payment no set
    explains stays unmatched.
    """
    used: set[str] = set()
    matched: dict[int, list[UtilityBill]] = {}
    by_provider: dict[Utility, list[UtilityBill]] = {}
    for bill in bills:
        if bill.bill_date:
            by_provider.setdefault(bill.provider, []).append(bill)
    for items in by_provider.values():
        items.sort(key=lambda b: (b.bill_date, b.account))
    for payment in payments:
        window = [b for b in by_provider.get(payment.provider, [])
                  if b.source not in used and payment.day - timedelta(days=before) <= b.bill_date <= payment.day + timedelta(days=after)]
        single = [b for b in window if b.payable_cents == payment.amount_cents]
        if single:
            attached = {(a.bill.account, a.bill.bill_date) for a in payment.attachments if a.bill}
            single.sort(key=lambda b: ((b.account, b.bill_date) not in attached, abs((payment.day - b.bill_date).days)))
            chosen = [single[0]]
        else:
            chosen = _subset(window, payment.amount_cents) or _catch_up(window, payment.amount_cents) or []
        if chosen:
            matched[payment.key] = chosen
            used.update(b.source for b in chosen)
    return matched


def repeats(payments: list[Payment], matched: dict[int, list[UtilityBill]], *, days: int = 10) -> dict[int, Payment]:
    """An unmatched payment with the amount of a matched one a few days before it: the same bills paid twice."""
    found: dict[int, Payment] = {}
    for index, payment in enumerate(payments):
        if payment.key in matched:
            continue
        for earlier in reversed(payments[:index]):
            if (payment.day - earlier.day).days > days:
                break
            if (earlier.key in matched and earlier.provider is payment.provider and earlier.amount_cents == payment.amount_cents
                    and earlier not in found.values()):
                found[payment.key] = earlier
                break
    return found


def expected_split(bills: list[UtilityBill], lines: dict[Service, str]) -> dict[str, int]:
    """The bills' charges by budget line; a service with no line is named by its service."""
    split: dict[str, int] = {}
    for bill in bills:
        for service, cents in bill.by_service().items():
            name = lines.get(service, f"({service.value})")
            split[name] = split.get(name, 0) + cents
    return {k: v for k, v in sorted(split.items()) if v}


def audit_payment(payment: Payment, bills: list[UtilityBill], lines: dict[Service, str], repeat_of: Payment | None = None,
                  repeat_bills: list[UtilityBill] | None = None) -> dict[str, Any]:
    """What is wrong with one payment's attachment and split, and the split its bills support."""
    findings: list[str] = []
    paid = {(b.account, b.bill_date) for b in bills}
    attached_bills = [a.bill for a in payment.attachments if a.bill]
    attached = {(b.account, b.bill_date) for b in attached_bills}
    if not payment.attachments:
        findings.append("no attachment")
    for a in payment.attachments:
        if a.bill is None:
            findings.append(f"attachment {a.filename!r} is not a {payment.provider.value} bill ({a.kind or 'not read'})")
        elif a.bill.provider is not payment.provider:
            findings.append(f"attachment {a.filename!r} is a {a.bill.provider.value} bill on a {payment.provider.value} payment")
    if repeat_of is not None:
        findings.append(f"paid twice: the {repeat_of.day.isoformat()} payment of the same amount already paid "
                        + ", ".join(f"{b.account} {b.bill_date}" for b in repeat_bills or []) + "; the next bills should show the credit")
    elif not bills:
        findings.append("no set of bills on disk sums to this payment")
    else:
        missing = paid - attached
        extra = attached - paid
        if payment.attachments and missing:
            findings.append("the attachments do not include the bill(s) paid: " + ", ".join(f"{a} {d}" for a, d in sorted(missing)))
        if extra:
            findings.append("attached bill(s) this payment did not pay: " + ", ".join(f"{a} {d}" for a, d in sorted(extra)))
    # Split by the bills paid; an attached bill stands in only when its total is the payment's.
    basis = bills or repeat_bills or (attached_bills if sum(b.payable_cents for b in attached_bills) == payment.amount_cents else [])
    if not bills and attached_bills and not basis:
        findings.append(f"the attached bill(s) ask ${sum(b.payable_cents for b in attached_bills) / 100:,.2f}, "
                        f"not the payment's ${payment.amount_cents / 100:,.2f}")
    expected = expected_split(basis, lines) if basis else {}
    actual: dict[str, int] = {}
    for row in payment.rows:
        actual[row.category] = actual.get(row.category, 0) + row.amount_cents
    split_state = "no bill to split by"
    if expected:
        if actual == expected:
            split_state = "matches the bills"
        elif sum(expected.values()) != payment.amount_cents and set(actual) == set(expected):
            # The payment is the amount due after a balance or a credit; the lines are right, the amounts cannot be.
            split_state = "matches the bills' lines"
        elif len(expected) == 1:
            split_state = "one line expected; category differs" if set(actual) != set(expected) else "amounts differ"
        elif not payment.split:
            split_state = "not split"
        else:
            split_state = "split differs from the bills"
    if split_state not in ("matches the bills", "matches the bills' lines", "no bill to split by"):
        findings.append(f"split: {split_state}")
    return {
        "key": payment.key,
        "provider": payment.provider.value,
        "date": payment.day.isoformat(),
        "amountCents": payment.amount_cents,
        "rows": [{"txId": r.tx_id, "category": r.category, "amountCents": r.amount_cents} for r in payment.rows],
        "attachments": [{"id": a.attachment_id, "filename": a.filename,
                         "bill": {"account": a.bill.account, "billDate": a.bill.bill_date.isoformat() if a.bill.bill_date else None,
                                  "totalCents": a.bill.total_cents} if a.bill else None, "kind": a.kind} for a in payment.attachments],
        "paid": [{"account": b.account, "billDate": b.bill_date.isoformat() if b.bill_date else None, "totalCents": b.total_cents,
                  "dueCents": b.due_cents,
                  "periodStart": b.period_start.isoformat() if b.period_start else None,
                  "periodEnd": b.period_end.isoformat() if b.period_end else None} for b in bills],
        "actualSplit": dict(sorted(actual.items())),
        "expectedSplit": expected,
        "split": split_state,
        "findings": findings,
        "ok": not findings,
    }


def audit(payments: list[Payment], bills: list[UtilityBill], lines: dict[Service, str]) -> list[dict[str, Any]]:
    matched = match_payments(payments, bills)
    twice = repeats(payments, matched)
    rows = []
    for p in payments:
        earlier = twice.get(p.key)
        earlier_bills = matched.get(earlier.key, []) if earlier else []
        confirmed, notes = credit_evidence(p, earlier_bills, bills) if earlier else (False, [])
        row = audit_payment(p, matched.get(p.key, []), lines, earlier if confirmed else None, earlier_bills if confirmed else None)
        if earlier and not confirmed:
            row["findings"].append(f"same amount as the {earlier.day.isoformat()} payment, and the next bill shows no credit for it: "
                                   "it may have paid an older balance; check the account history")
        row["findings"].extend(notes)
        rows.append(row)
    return rows


def credit_evidence(payment: Payment, paid: list[UtilityBill], bills: list[UtilityBill]) -> tuple[bool, list[str]]:
    """For a payment that repeats an earlier one: each account's next bill, and whether its credit covers the repeat.

    Confirmed when every account's next bill asked for its charges less the repeated payment (or nothing, when the
    payment covers the charges), within a dollar. When that next bill on file came more than 45 days after the bill paid
    twice, a month's bill is missing between them: the credit paid it, and any remainder shows on the bill on file (SMUD's
    April 2024 bills are past its portal's two years; the May bills show the remainders).
    """
    notes: list[str] = []
    confirmed = bool(paid)
    share = payment.amount_cents // max(1, len({b.account for b in paid}))
    for account in sorted({b.account for b in paid}):
        later = sorted((b for b in bills if b.provider is payment.provider and b.account == account and b.bill_date
                        and b.bill_date > payment.day), key=lambda b: b.bill_date)
        if not later or later[0].due_cents is None:
            confirmed = False
            notes.append(f"evidence: no later {account} bill with an amount due on disk")
            continue
        nxt = later[0]
        credit = nxt.total_cents - nxt.due_cents
        last_paid = max((b.bill_date for b in paid if b.account == account and b.bill_date), default=None)
        gap = last_paid is not None and (nxt.bill_date - last_paid).days > 45
        if gap and credit > 0:
            notes.append(f"evidence: no {account} bill on disk between {last_paid} and {nxt.bill_date}; the {nxt.bill_date} bill "
                         f"asked ${nxt.due_cents / 100:,.2f} against ${nxt.total_cents / 100:,.2f} of charges, the rest of the "
                         "second payment's credit after it paid the missing month")
        elif credit >= min(share, nxt.total_cents) - 100:
            notes.append(f"evidence: the {nxt.bill_date} bill for {account} asked ${nxt.due_cents / 100:,.2f} "
                         f"against ${nxt.total_cents / 100:,.2f} of charges, the credit from the second payment")
        else:
            confirmed = False
            notes.append(f"evidence: the {nxt.bill_date} bill for {account} asked ${nxt.due_cents / 100:,.2f} "
                         f"against ${nxt.total_cents / 100:,.2f} of charges; that is not the second payment's credit")
    return confirmed, notes


__all__ = ["identify", "Payment", "PaymentRow", "Attachment", "group_payments", "match_payments", "expected_split", "audit_payment", "audit", "provider_of", "repeats", "credit_evidence"]
