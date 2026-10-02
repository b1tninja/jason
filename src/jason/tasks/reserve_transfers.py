"""The reserve accounts' transfers from the stored ledger, and for each borrowing the record Civil Code 5515 asks for.

Reads ``data/payhoa/ledger.db`` (``jason books --sync``), ``data/payhoa/ledger-accounts.json`` (``jason ledger --fetch``)
to name each ledger account's bank account, the bank accounts in ``mystique/banking.py``, and the classified library
(``jason library``). For each borrowing it looks for:

- the notice: an agenda within 60 days before the transfer with a "Notice of Intent to Borrow" item (5515(a), 4920);
- the finding: the minutes of that meeting (5515(c)); a DRAFT is not the approved minutes;
- the resolution: a resolution that authorizes borrowing and names the amount, or the one the agenda cites;
- the restoration: the unscheduled contributions that repay it, and whether they did within a year (5515(d)).

A document found is the library's copy; a document missing may be in the board's files and not yet in PayHOA. Nothing
here changes PayHOA or decides that the board met the statute.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from jason.community.base import AccountPurpose, ReserveLine
from jason.community.reserve_transfers import (
    Borrowing,
    MovementKind,
    Purpose,
    ReserveMovement,
    budget_months,
    explain,
    movements,
    repayments,
    schedule,
)

NOTICE = re.compile(r"notice of intent to borrow", re.I)
BORROW = re.compile(r"borrow", re.I)
CITED = re.compile(r"(Special Resolution\s*-\s*Borrowing[^\n]*)", re.I)


def budget_path(data_dir: Path, year: int) -> Path:
    return Path(data_dir) / "payhoa" / "budgets" / f"{year}.json"


def fetch_budgets(client: Any, org_id: int, data_dir: Path, years: list[int]) -> dict[int, int]:
    """PayHOA's budget for each year (``GET /budgets``), saved as sent. Read-only in PayHOA."""
    found = {}
    for year in years:
        tree = client.list_budgets(org_id, start_year=year)
        path = budget_path(data_dir, year)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(tree), encoding="utf-8")
        found[year] = len(tree.get("expense") or [])
    return found


def contribution_check(data_dir: Path, community: Any, moves: list[ReserveMovement], *, today: date) -> list[dict[str, Any]]:
    """Each budget year on disk: the reserve contribution and repayment budgeted month by month against the transfers
    that paid them (``schedule``), with the months short and the months paid late."""
    lines = community.reserve_budget_lines()
    contribution_line, repayment_line = lines.get(ReserveLine.CONTRIBUTION), lines.get(ReserveLine.REPAYMENT)
    if not contribution_line:
        return []
    out = []
    for path in sorted((Path(data_dir) / "payhoa" / "budgets").glob("*.json")):
        year = int(path.stem)
        tree = json.loads(path.read_text(encoding="utf-8"))
        through = (year, 12) if year < today.year else (today.year, today.month)
        rows = schedule(moves, budget_months(tree, contribution_line), budget_months(tree, repayment_line) if repayment_line else {},
                        through=through)
        if not rows:
            continue
        short = [r["month"] for r in rows if r["contributionPaidCents"] < r["contributionBudgetCents"]
                 and (int(r["month"][:4]), int(r["month"][5:])) < (today.year, today.month)]
        repay_short = [r["month"] for r in rows if r["repaymentPaidCents"] < r["repaymentBudgetCents"]]
        out.append({
            "year": year, "through": f"{through[0]}-{through[1]:02d}", "months": rows,
            "contributionBudgetCents": sum(r["contributionBudgetCents"] for r in rows),
            "contributionPaidCents": sum(r["contributionPaidCents"] for r in rows),
            "repaymentBudgetCents": sum(r["repaymentBudgetCents"] for r in rows),
            "repaymentPaidCents": sum(r["repaymentPaidCents"] for r in rows),
            "short": short, "repaymentShort": repay_short,
            "late": [{"month": r["month"], "daysLate": r["daysLate"]} for r in rows if r["daysLate"] > 0],
        })
    return out


def deleted_reserve_liabilities(data_dir: Path) -> list[dict[str, Any]]:
    """Liability accounts naming the reserve (a "Due to Reserves") that were deleted from PayHOA's chart of accounts.
    Deleting one removes its entries from every report, and with them the record of what operating owed the reserve."""
    path = Path(data_dir) / "payhoa" / "ledger-accounts.json"
    if not path.is_file():
        return []
    return [{"id": a.get("id"), "label": a.get("label"), "startingBalanceDate": a.get("startingBalanceDate"),
             "deletedAt": str(a.get("deletedAt"))[:10]}
            for a in json.loads(path.read_text(encoding="utf-8")).get("liabilities") or []
            if a.get("deletedAt") and "reserve" in str(a.get("label")).lower()]


def account_numbers(data_dir: Path) -> dict[str, str]:
    """Ledger account label -> the bank account's last four, from the chart of accounts ``jason ledger --fetch`` saved."""
    path = Path(data_dir) / "payhoa" / "ledger-accounts.json"
    if not path.is_file():
        return {}
    found = {}
    for acct in json.loads(path.read_text(encoding="utf-8")).get("assets") or []:
        owner = acct.get("owner") or {}
        if owner.get("last4"):
            found[str(acct["label"])] = str(owner["last4"])
    return found


def _dollars_pattern(cents: int) -> re.Pattern:
    whole = f"{cents // 100:,}"
    return re.compile(r"\$?\s*" + re.escape(whole) + r"(\.\d\d)?\b")


def documents(data_dir: Path, loan: Borrowing, *, notice_days: int = 60) -> dict[str, Any]:
    """The notice, minutes, and resolution the library holds for one borrowing."""
    from jason.tasks.library import load, text_for

    rows = load(Path(data_dir))
    day = loan.movement.day
    amount = _dollars_pattern(loan.movement.cents)

    def when(row) -> date | None:
        try:
            return date.fromisoformat(str(row.get("period") or "")[:10])
        except ValueError:
            return None

    notice = None
    for row in sorted((r for r in rows if r.get("kind") == "agenda"), key=lambda r: str(r.get("period")), reverse=True):
        meeting = when(row)
        if meeting and day - timedelta(days=notice_days) <= meeting <= day and NOTICE.search(text_for(Path(data_dir), row["id"])):
            text = text_for(Path(data_dir), row["id"])
            cited = CITED.search(text)
            notice = {"id": row["id"], "name": row["name"], "meeting": meeting.isoformat(),
                      "cites": re.sub(r"\s+", " ", cited.group(1)).strip(" .…") if cited else ""}
            break
    minutes = None
    if notice:
        found = [r for r in rows if r.get("kind") == "minutes" and str(r.get("period") or "")[:10] == notice["meeting"]]
        if found:
            row = found[0]
            minutes = {"id": row["id"], "name": row["name"], "draft": "draft" in row["name"].lower(),
                       "mentionsBorrowing": bool(BORROW.search(text_for(Path(data_dir), row["id"])))}
    resolution = None
    for row in (r for r in rows if r.get("kind") == "resolution"):
        text = text_for(Path(data_dir), row["id"])
        if BORROW.search(row["name"]) and amount.search(text):
            resolution = {"id": row["id"], "name": row["name"]}
            break
    return {"notice": notice, "minutes": minutes, "resolution": resolution}


def _move(m: ReserveMovement) -> dict[str, Any]:
    return {"day": m.day.isoformat(), "cents": m.cents, "account": m.account, "kind": m.kind.value, "purpose": m.purpose.value,
            "number": m.number, "memo": m.memo, "description": m.description[:90], "matched": m.matched}


def review(data_dir: Path, community: Any, *, today: date | None = None) -> dict[str, Any]:
    """Every reserve movement explained, and each borrowing's 5515 record."""
    from jason.tasks.books import load

    items = load(Path(data_dir))
    if not items:
        return {"found": False, "note": "no ledger on disk; run jason books --sync"}
    numbers = account_numbers(Path(data_dir))
    accounts = community.bank_accounts()
    reserve_suffixes = {a.suffix for a in accounts if a.purpose is AccountPurpose.RESERVE}
    operating_suffixes = {a.suffix for a in accounts if a.purpose is AccountPurpose.OPERATING}
    reserve = {label: last4 for label, last4 in numbers.items() if last4 in reserve_suffixes}
    operating = {label for label, last4 in numbers.items() if last4 in operating_suffixes}
    if not reserve:
        return {"found": False, "note": "no ledger account is a pinned reserve account; run jason ledger --fetch"}
    moves = explain(movements(items, reserve, operating_suffixes), items, operating)
    loans = repayments(moves)
    day = today or date.today()
    rows = []
    for loan in loans:
        docs = documents(Path(data_dir), loan)
        gaps = []
        if not docs["notice"]:
            gaps.append("no agenda in the library gives notice of intent to borrow (5515(a))")
        if not docs["minutes"]:
            gaps.append("no minutes in the library for the meeting that considered it (5515(c) finding)")
        elif docs["minutes"]["draft"]:
            gaps.append("the library holds only DRAFT minutes of that meeting")
        if not docs["resolution"]:
            cited = (docs["notice"] or {}).get("cites")
            gaps.append(f"no resolution in the library authorizes it{f' (the agenda cites: {cited})' if cited else ''}")
        if not loan.repaid:
            gaps.append("no transfer back to the reserve restores it")
        if loan.outstanding_cents and day > loan.deadline:
            gaps.append(f"not restored within a year (due {loan.deadline.isoformat()}); a delay needs a noticed finding (5515(d))")
        elif loan.on_time is False:
            gaps.append(f"restored {loan.repaid_on.isoformat()}, after the year ended {loan.deadline.isoformat()} (5515(d))")
        rows.append({**_move(loan.movement), "deadline": loan.deadline.isoformat(), "repaidCents": loan.repaid_cents,
                     "outstandingCents": loan.outstanding_cents, "repaidOn": loan.repaid_on.isoformat() if loan.repaid_on else None,
                     "exactRepayment": loan.exact, "repayments": [_move(m) for m in loan.repaid], "documents": docs, "gaps": gaps})
    budget_years = contribution_check(Path(data_dir), community, moves, today=day)
    other_out = [_move(m) for m in moves if m.kind is MovementKind.WITHDRAWAL and m.purpose is not Purpose.BORROWING]
    unscheduled = [_move(m) for m in moves if m.purpose is Purpose.UNSCHEDULED and not any(m in l.repaid for l in loans)]
    return {
        "found": True, "ledgerThrough": max(e.day for e in items).isoformat(), "reserveAccounts": sorted(reserve),
        "borrowings": rows, "budgetYears": budget_years, "deletedReserveLiabilities": deleted_reserve_liabilities(Path(data_dir)), "otherWithdrawals": other_out, "unappliedContributions": unscheduled,
        "catchUps": [_move(m) for m in moves if m.purpose is Purpose.CATCH_UP],
        "investments": [_move(m) for m in moves if m.purpose is Purpose.INVESTMENT],
        "caveats": [
            "The ledger starts in January 2024; transfers made while the prior manager held the accounts are not in it.",
            "A repayment is matched by amount; the board's resolution says which borrowing a payment restored.",
            "A reimbursement is 5510(b) spending only when the expense was a reserve component in the study.",
            "A document missing from the library may be in the board's files; add it to the PayHOA library.",
            "Budgets are PayHOA's as `jason reserves --transfers --fetch` saved them; a year PayHOA has no budget for is not checked.",
        ],
    }


def dollars(cents: int | None) -> str:
    return "-" if cents is None else f"${cents / 100:,.2f}"


def review_lines(result: dict[str, Any]) -> list[str]:
    if not result.get("found"):
        return [result.get("note", "no ledger")]
    out = [f"Reserve transfers through {result['ledgerThrough']} ({', '.join(result['reserveAccounts'])})", ""]
    out.append(f"Borrowings from the reserve (Civil Code 5515): {len(result['borrowings'])}")
    for b in result["borrowings"]:
        out.append(f"  {b['day']} {dollars(b['cents'])} to operating  memo: {b['memo'] or '-'}  transaction {b['number'] or '-'}")
        docs = b["documents"]
        if docs["notice"]:
            out.append(f"    notice:     {docs['notice']['name']} (meeting {docs['notice']['meeting']})")
        if docs["minutes"]:
            out.append(f"    minutes:    {docs['minutes']['name']}")
        if docs["resolution"]:
            out.append(f"    resolution: {docs['resolution']['name']}")
        if b["repayments"]:
            pays = ", ".join(f"{r['day']} {dollars(r['cents'])}" for r in b["repayments"])
            how = "exactly" if b["exactRepayment"] else "applied oldest first"
            out.append(f"    restored {dollars(b['repaidCents'])} ({how}): {pays}")
        out.append(f"    due back by {b['deadline']}; " + (f"restored {b['repaidOn']}" if b["repaidOn"] else f"outstanding {dollars(b['outstandingCents'])}"))
        out.extend(f"    ! {g}" for g in b["gaps"])
    for acct in result.get("deletedReserveLiabilities") or []:
        out.append(f"  ! the liability account {acct['label']!r} (id {acct['id']}, from {acct['startingBalanceDate']}) was deleted "
                   f"on {acct['deletedAt']}; its entries no longer show what operating owed the reserve")
    if result["budgetYears"]:
        out.append("")
        out.append("Budgeted reserve contributions against the transfers made:")
        for y in result["budgetYears"]:
            line = (f"  {y['year']} through {y['through']}: contribution budget {dollars(y['contributionBudgetCents'])}, "
                    f"paid {dollars(y['contributionPaidCents'])}")
            if y["repaymentBudgetCents"] or y["repaymentPaidCents"]:
                line += f"; repayment budget {dollars(y['repaymentBudgetCents'])}, paid {dollars(y['repaymentPaidCents'])}"
            out.append(line)
            if y["short"]:
                out.append(f"    ! months short: {', '.join(y['short'])}")
            if y["repaymentShort"]:
                out.append(f"    ! repayment months short: {', '.join(y['repaymentShort'])}")
            if y["late"]:
                out.append("    paid after the month: " + ", ".join(f"{l['month']} ({l['daysLate']} days)" for l in y["late"]))
    if result["otherWithdrawals"]:
        out.append("")
        out.append("Other withdrawals to operating:")
        for m in result["otherWithdrawals"]:
            why = f" ({m['matched']['day']} {m['matched']['description'][:50]})" if m["matched"] else ""
            out.append(f"  {m['day']} {dollars(m['cents']):>11}  {m['purpose']}{why}  memo: {m['memo'] or '-'}")
    if result["catchUps"]:
        out.append("")
        out.append("Catch-up contributions: " + ", ".join(f"{m['day']} {dollars(m['cents'])} ({m['memo']})" for m in result["catchUps"]))
    if result["unappliedContributions"]:
        out.append("")
        out.append("Unscheduled contributions no borrowing explains:")
        out.extend(f"  {m['day']} {dollars(m['cents'])}  memo: {m['memo'] or '-'}" for m in result["unappliedContributions"])
    if result["investments"]:
        out.append("")
        out.append("Moves to certificates of deposit: " + ", ".join(f"{m['day']} {dollars(m['cents'])}" for m in result["investments"]))
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["review", "review_lines", "documents", "account_numbers", "deleted_reserve_liabilities", "fetch_budgets", "contribution_check", "budget_path"]
