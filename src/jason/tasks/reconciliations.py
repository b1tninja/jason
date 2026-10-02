"""PayHOA's bank reconciliations: the bank's side of the books, month by month, and what never cleared.

A reconciliation matches a month's bank statement to PayHOA's register: the statement's beginning
and ending balances, the payments and deposits that cleared, and the register items still open.
``fetch`` reads every completed reconciliation and its report (``/reconciliations``,
``/reconciliations/{id}/report``) into ``data/payhoa/reconciliations.json``; it changes nothing.

``review`` reads that file and reports, per bank account:

- the months reconciled, and any month between the first and the latest with no reconciliation;
- each statement's ending balance beside the general ledger's balance for the same account and day
  (``jason books``), where the two disagree;
- register items that never cleared, oldest first, with their age: a payment recorded twice, a
  transfer booked on the wrong account, a voided invoice left as a deposit. The latest
  reconciliation's list is the current one.

A reconciliation is the treasurer's work; jason reads it and does not clear, void, or re-reconcile anything.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

FILE = "reconciliations.json"
STALE_DAYS = 60


def _path(data_dir: Path) -> Path:
    return Path(data_dir) / "payhoa" / FILE


def fetch(client: Any, org_id: int, data_dir: Path, *, log: Callable[[str], None] | None = None) -> dict[str, int]:
    """Read every reconciliation and its report. Read-only in PayHOA."""
    from payhoa.reports import reconciliation_rows, reconciliation_summary

    rows = []
    for rec in client.iter_reconciliations(org_id):
        report = client.reconciliation_report(org_id, int(rec["id"]))
        account = rec.get("unifiedBankAccount") or {}
        rows.append({"id": rec["id"], "account": account.get("friendlyName"), "accountId": account.get("id"), "last4": account.get("last4"),
                     "start": rec.get("startDate"), "end": rec.get("endDate"), "startingBalance": rec.get("startingBalance"),
                     "endingBalance": rec.get("endingBalance"), "totalPayments": rec.get("totalPayments"),
                     "totalDeposits": rec.get("totalDeposits"), "completedAt": rec.get("completedAt"),
                     "report": reconciliation_summary(report), "cleared": reconciliation_rows(report)})
        if log:
            log(f"{account.get('friendlyName')} {rec.get('endDate')}")
    path = _path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "reconciliations": rows},
                               indent=1, default=str), encoding="utf-8")
    return {"reconciliations": len(rows)}


def _month(day: str) -> str:
    return str(day)[:7]


def _months_between(first: str, last: str) -> list[str]:
    year, month = (int(x) for x in first.split("-"))
    end = tuple(int(x) for x in last.split("-"))
    found = []
    while (year, month) <= end:
        found.append(f"{year}-{month:02d}")
        year, month = (year, month + 1) if month < 12 else (year + 1, 1)
    return found


def review(data_dir: Path, *, today: date | None = None) -> dict[str, Any]:
    """Coverage, statement balances against the ledger, and the items still open, per bank account."""
    path = _path(data_dir)
    if not path.is_file():
        return {"found": False, "note": "no reconciliations on disk; run jason reconcile --fetch"}
    data = json.loads(path.read_text(encoding="utf-8"))
    recs = data["reconciliations"]
    day = today or date.today()
    ledger_items = None
    try:
        from jason.tasks.books import load

        ledger_items = load(Path(data_dir))
    except Exception:  # the ledger store is optional; the balance check is skipped without it
        ledger_items = None
    ledgers = ledger_accounts(Path(data_dir))
    accounts: dict[str, list[dict[str, Any]]] = {}
    for rec in recs:
        accounts.setdefault(str(rec["account"]), []).append(rec)
    out = []
    for name, items in sorted(accounts.items()):
        items.sort(key=lambda r: r["end"])
        months = sorted({_month(r["end"]) for r in items})
        gaps = [m for m in _months_between(months[0], months[-1]) if m not in months] if months else []
        latest = items[-1]
        open_items = []
        for kind in ("unreconciledPayments", "unreconciledDeposits"):
            for item in latest["report"].get(kind) or []:
                age = (day - date.fromisoformat(item["date"])).days if item.get("date") else None
                open_items.append({"kind": "payment" if kind.endswith("Payments") else "deposit", **item, "ageDays": age})
        open_items.sort(key=lambda i: i["date"])
        cleared = [row for rec in items for row in rec.get("cleared") or []]
        diagnose(open_items, cleared)
        mismatches = []
        ledger_account = ledgers.get(latest.get("accountId"))
        before_ledger = []
        if ledger_items and ledger_account:
            label, since = ledger_account
            for rec in items:
                if since and rec["end"] < since:
                    before_ledger.append(rec["end"])
                    continue
                ledger_balance = _ledger_balance(ledger_items, label, date.fromisoformat(rec["end"]))
                statement = int(rec.get("endingBalance") or 0)
                if ledger_balance is not None and ledger_balance != statement:
                    transit = in_transit(rec)
                    mismatches.append({"end": rec["end"], "statementCents": statement, "ledgerCents": ledger_balance,
                                       "differenceCents": ledger_balance - statement, "inTransitCents": transit,
                                       "explained": ledger_balance - statement == transit})
        summary = latest["report"].get("summary") or {}
        register = next((v for k, v in summary.items() if k.startswith("Register Balance")), None)
        out.append({
            "account": name, "last4": latest.get("last4"), "reconciled": len(items), "first": months[0] if months else None,
            "latest": latest["end"], "latestEndingCents": latest.get("endingBalance"), "registerBalanceCents": register,
            "gaps": gaps, "openItems": open_items,
            "staleOpenItems": [i for i in open_items if (i.get("ageDays") or 0) > STALE_DAYS],
            "openPaymentsCents": sum(i["amount"] for i in open_items if i["kind"] == "payment"),
            "openDepositsCents": sum(i["amount"] for i in open_items if i["kind"] == "deposit"),
            "discrepancies": latest["report"].get("discrepancies", 0),
            "ledgerAccount": ledger_account[0] if ledger_account else None,
            "ledgerSince": ledger_account[1] if ledger_account else None,
            "beforeLedger": len(before_ledger),
            "ledgerMismatches": mismatches,
        })
    return {"found": True, "fetchedAt": data.get("fetchedAt"), "accounts": out, "openTransfers": open_transfers(out),
            "caveats": ["Open items are the latest reconciliation's; clearing or voiding one is the treasurer's work in PayHOA.",
                        "The ledger balance for a day includes entries imported or re-dated after the month was reconciled."]}


_TRACE = re.compile(r"(?:TRACE#|transaction#):\s*(\d+)")
_COMPANY = re.compile(r"ORIG CO NAME:([^:]+?)\s+ORIG ID")


def trace_of(description: str) -> str:
    """The bank's number for a line: the ACH trace, or the online transfer's transaction number."""
    m = _TRACE.search(description)
    return m.group(1) if m else ""


def _payer(description: str) -> str:
    m = _COMPANY.search(description)
    return (m.group(1) if m else description[:24]).strip().casefold()


def bank_lines(items: list[dict[str, Any]], side_of) -> list[dict[str, Any]]:
    """Register pieces grouped into the bank lines they came from: pieces sharing a trace or transaction number are one
    line split across categories; a piece with no number is a line by itself. Each line has ``trace``, ``side``, ``date``,
    ``description``, ``amount`` (the pieces' sum), and ``pieces``."""
    lines: dict[Any, dict[str, Any]] = {}
    for n, item in enumerate(items):
        side, amount = side_of(item)
        trace = trace_of(item["description"])
        key = (trace, side) if trace else n
        line = lines.setdefault(key, {"trace": trace, "side": side, "date": item["date"], "description": item["description"],
                                      "amount": 0, "pieces": []})
        line["amount"] += amount
        line["pieces"].append(item)
    return list(lines.values())


def diagnose(open_items: list[dict[str, Any]], cleared: list[dict[str, Any]], *, days: int = 10) -> None:
    """Why each register item may never have cleared, from the account's cleared items. Sets ``reason``, ``trace``,
    ``splitOf`` (how many open pieces share the bank line), and ``twin`` (the cleared line it matched) on each item.

    Items are compared as bank lines (``bank_lines``), not pieces: a split line's $5.64 fire-service piece matches
    half the City's lines, while the line's total does not.

    - ``same bank line``: a cleared line carries the same trace or transaction number, so the register holds the bank line twice;
    - ``cleared twin``: a cleared line of the same total, side, and company within ``days`` under a different number:
      a second bank line for the same payment (paid twice, or reversed later) that the statement did not carry;
    - ``voided bill payment``: a deposit PayHOA made when a bill payment was voided, with no bank line behind it;
    - ``transfer``: a transfer between the association's accounts (``open_transfers`` pairs the two sides);
    - ``in transit``: dated in the last 45 days, so the next statement may carry it;
    - otherwise no reason is found, and the bank statement is the place to look.
    Each cleared line is a twin once. A reason is a lead for the treasurer, not a finding."""
    opened = bank_lines(open_items, lambda i: (i["kind"], i["amount"]))
    done = bank_lines(cleared, lambda r: ("payment", r["payment"]) if r["payment"] else ("deposit", r["deposit"]))
    used: set[int] = set()

    def take(line: dict[str, Any], test) -> dict[str, Any] | None:
        for n, row in enumerate(done):
            if n not in used and row["side"] == line["side"] and row["amount"] == line["amount"] and test(row):
                used.add(n)
                return row
        return None

    for line in opened:
        line["reason"], line["twin"] = "", None
        if line["trace"]:
            twin = take(line, lambda r, t=line["trace"]: r["trace"] == t)
            if twin:
                line["reason"], line["twin"] = "same bank line", twin
    for line in opened:
        if line["reason"]:
            continue
        when = date.fromisoformat(line["date"])
        twin = take(line, lambda r: _payer(r["description"]) == _payer(line["description"])
                    and abs((date.fromisoformat(r["date"]) - when).days) <= days)
        if twin:
            line["reason"], line["twin"] = "cleared twin", twin
        elif line["description"].startswith("Void/Cancel"):
            line["reason"] = "voided bill payment"
        elif re.match(r"Online Transfer (to|from) ", line["description"]):
            line["reason"] = "transfer"
        elif line["pieces"][0].get("ageDays") is not None and line["pieces"][0]["ageDays"] <= 45:
            line["reason"] = "in transit"
    for line in opened:
        twin = {k: line["twin"][k] for k in ("date", "description", "amount", "trace")} if line["twin"] else None
        for item in line["pieces"]:
            item.update({"trace": line["trace"], "splitOf": len(line["pieces"]), "lineCents": line["amount"],
                         "reason": line["reason"], "twin": twin})


def in_transit(rec: dict[str, Any]) -> int:
    """The net of a reconciliation's open items dated inside its own period (deposits less payments): money the register
    has and the statement did not yet show. A ledger balance that differs from the statement by exactly this is explained."""
    start, end = rec.get("start") or "", rec.get("end") or ""
    report = rec.get("report") or {}
    deposits = sum(i["amount"] for i in report.get("unreconciledDeposits") or [] if start <= i["date"] <= end)
    payments = sum(i["amount"] for i in report.get("unreconciledPayments") or [] if start <= i["date"] <= end)
    return deposits - payments


def open_transfers(accounts: list[dict[str, Any]], *, days: int = 3) -> list[dict[str, Any]]:
    """An open payment in one account and an open deposit of the same amount in another within ``days``: a transfer
    between the association's own accounts that neither statement shows. Each item pairs once."""
    payments = [(a["account"], i) for a in accounts for i in a["openItems"] if i["kind"] == "payment"]
    deposits = [(a["account"], i) for a in accounts for i in a["openItems"] if i["kind"] == "deposit"]
    used: set[int] = set()
    found = []
    for out_account, pay in payments:
        fits = [n for n, (in_account, dep) in enumerate(deposits)
                if n not in used and in_account != out_account and dep["amount"] == pay["amount"]
                and abs((date.fromisoformat(dep["date"]) - date.fromisoformat(pay["date"])).days) <= days]
        if not fits:
            continue
        # The transfer's own number on both sides pairs first.
        number = trace_of(pay["description"])
        n = next((n for n in fits if number and trace_of(deposits[n][1]["description"]) == number), fits[0])
        used.add(n)
        in_account, dep = deposits[n]
        found.append({"from": out_account, "to": in_account, "paid": pay["date"], "deposited": dep["date"],
                      "amount": pay["amount"], "description": pay["description"],
                      "recordedTwice": pay.get("reason") == dep.get("reason") == "same bank line"})
    return found


def ledger_accounts(data_dir: Path) -> dict[int, tuple[str, str | None]]:
    """PayHOA bank account id -> (the ledger account's label, its starting balance date), from ``ledger-accounts.json``
    (``jason ledger --fetch``). A reconciliation names the bank account; the ledger names its own asset account,
    and two ledger accounts can share a friendly name ("Operating Account" at Chase and at First Citizens)."""
    path = Path(data_dir) / "payhoa" / "ledger-accounts.json"
    if not path.is_file():
        return {}
    found = {}
    for acct in json.loads(path.read_text(encoding="utf-8")).get("assets") or []:
        if acct.get("deletedAt") or not acct.get("ownerId") or "UnifiedBankAccount" not in str(acct.get("ownerType")):
            continue
        found[int(acct["ownerId"])] = (str(acct["label"]), acct.get("startingBalanceDate"))
    return found


def _ledger_balance(items, label: str, day: date) -> int | None:
    """The general ledger's balance for one asset account on a day: its last running balance on or before the day."""
    from jason.community.ledger import BANK

    found = None
    for e in items:
        if e.type == BANK and e.account == label and e.day <= day:
            found = e.balance
    return found


def dollars(cents: int | None) -> str:
    return "-" if cents is None else f"${cents / 100:,.2f}"


def _reason_note(item: dict[str, Any]) -> str:
    reason = item.get("reason")
    if not reason:
        return ""
    twin = item.get("twin")
    split = f" (one of {item['splitOf']} pieces of bank line {item['trace']}, {dollars(item['lineCents'])})" if item.get("splitOf", 0) > 1 else ""
    return f"\n        -> {reason}{split}" + (f"; cleared {twin['date']}, bank number {twin['trace'] or 'none'}" if twin else "")


def review_lines(result: dict[str, Any]) -> list[str]:
    if not result.get("found"):
        return [result.get("note", "no reconciliations")]
    out = []
    for a in result["accounts"]:
        out.append(f"{a['account']} ...{a['last4']}: {a['reconciled']} reconciliations, {a['first']} to {a['latest'][:7]}; "
                   f"statement ending {dollars(a['latestEndingCents'])}, register {dollars(a['registerBalanceCents'])}")
        if a["gaps"]:
            out.append(f"  months with no reconciliation: {', '.join(a['gaps'])}")
        if a["openItems"]:
            out.append(f"  still open: {len(a['openItems'])} items, payments {dollars(a['openPaymentsCents'])}, deposits {dollars(a['openDepositsCents'])}")
            for item in a["openItems"]:
                out.append(f"    {item['date']} {item['kind']:<7} {dollars(item['amount']):>11}  {item['ageDays']} days  {item['description'][:60]}" + _reason_note(item))
        if a["beforeLedger"]:
            out.append(f"  {a['beforeLedger']} statements end before the ledger's starting balance for {a['ledgerAccount']} "
                       f"({a['ledgerSince']}); the ledger has no balance to compare")
        for m in a["ledgerMismatches"]:
            why = "the items in transit at month end" if m["explained"] else "not explained by the items in transit"
            out.append(f"  {m['end']}: statement {dollars(m['statementCents'])}, ledger now {dollars(m['ledgerCents'])} "
                       f"({'+' if m['differenceCents'] > 0 else ''}{dollars(m['differenceCents'])}; {why})")
        if a["ledgerAccount"] and not a["ledgerMismatches"] and a["reconciled"] > a["beforeLedger"]:
            out.append(f"  every statement since {a['ledgerSince']} agrees with the ledger's {a['ledgerAccount']}")
    if result.get("openTransfers"):
        out.append("")
        out.append("Transfers open on both sides:")
        for t in result["openTransfers"]:
            why = ("recorded twice: both sides cleared under the same number, so each register carries it again"
                   if t.get("recordedTwice") else "neither statement shows it")
            out.append(f"  {t['paid']} {dollars(t['amount'])} {t['from']} -> {t['to']}  {t['description'][:48]}; {why}")
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["fetch", "review", "review_lines"]
