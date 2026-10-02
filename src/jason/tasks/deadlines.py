"""The association's recurring deadlines (``jason deadlines``), each with when it was last done and when it is next due.

Reads ``Mystique.obligations()`` against PayHOA's payments on disk (``data/payhoa/transactions.json``), and adds the
insurance terms (``jason.tasks.insurance``) and the reserve study's site visit (``jason.tasks.reserves``). A fixed
yearly deadline is judged for each year PayHOA covers: done on time, done late (and how late), or no evidence. The
next deadline is marked due soon inside 60 days and overdue once it passes with no evidence. A deadline no store shows
is listed as such. It reads disk only and records nothing.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from jason.tasks.sources import money_in

from jason.community.obligations import Obligation, Standing

SOON_DAYS = 60


def _payments(data_dir: Path) -> tuple[list[dict[str, Any]], date | None, str]:
    path = Path(data_dir) / "payhoa" / "transactions.json"
    if not path.is_file():
        return [], None, ""
    snap = json.loads(path.read_text(encoding="utf-8"))
    categories = {int(k): v.get("name", "") for k, v in snap.get("categories", {}).items()}
    vendors = {int(k): v for k, v in snap.get("vendors", {}).items()}
    out = []
    first = None
    for t in snap.get("transactions", []):
        day = date.fromisoformat(str(t["transactionDate"])[:10])
        first = day if first is None or day < first else first
        if int(t.get("originalAmount") or t.get("amount") or 0) <= 0 or t.get("deletedAt") or money_in(t):
            continue
        payee = vendors.get(int(t.get("vendorId") or 0)) or ""
        out.append({"date": day, "amountCents": int(t.get("amount") or 0), "category": categories.get(int(t.get("categoryId") or 0), ""),
                    "text": f"{payee} {t.get('description') or ''}".upper(), "payee": payee or str(t.get("description") or "")[:50]})
    return out, first, str(snap.get("syncedAt") or "")[:10]


def evidence(obligation: Obligation, payments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The payments that show the obligation done: booked to one of its categories, or to a payee carrying its words."""
    found = [p for p in payments if p["category"] in obligation.categories or any(w.upper() in p["text"] for w in obligation.payee_words)]
    return sorted(found, key=lambda p: p["date"])


def _shown(p: dict[str, Any]) -> dict[str, Any]:
    return {"date": p["date"].isoformat(), "amountCents": p["amountCents"], "payee": p["payee"], "category": p["category"]}


def _fixed(ob: Obligation, found: list[dict[str, Any]], first: date | None, today: date) -> dict[str, Any]:
    history = []
    if first:
        for year in range(first.year, today.year + 2):
            due = ob.deadline(year)
            if due - timedelta(days=ob.window_days) < first or due > today:
                continue
            on_time = [p for p in found if due - timedelta(days=ob.window_days) <= p["date"] <= due]
            late = [p for p in found if due < p["date"] <= due + timedelta(days=ob.grace_days)]
            if on_time:
                history.append({"deadline": due.isoformat(), "standing": Standing.DONE.value, "evidence": [_shown(p) for p in on_time]})
            elif late:
                history.append({"deadline": due.isoformat(), "standing": Standing.LATE.value, "daysLate": (late[0]["date"] - due).days,
                                "evidence": [_shown(p) for p in late]})
            else:
                history.append({"deadline": due.isoformat(), "standing": Standing.MISSED.value, "evidence": []})
    nxt = ob.deadline(today.year) if ob.deadline(today.year) >= today else ob.deadline(today.year + 1)
    early = [p for p in found if nxt - timedelta(days=ob.window_days) <= p["date"] <= today]
    left = (nxt - today).days
    if early:
        standing = Standing.DONE
    else:
        standing = Standing.DUE_SOON if left <= SOON_DAYS else Standing.UPCOMING
    return {"next": nxt.isoformat(), "daysLeft": left, "standing": standing.value, "history": history,
            "lastDone": found[-1]["date"].isoformat() if found else None,
            "nextEvidence": [_shown(p) for p in early]}


def add_months(day: date, months: int) -> date:
    """``day`` moved ``months`` later, on the same day of the month or the month's last day."""
    import calendar as _calendar

    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    return date(year, month, min(day.day, _calendar.monthrange(year, month)[1]))


def _interval(ob: Obligation, found: list[dict[str, Any]], today: date) -> dict[str, Any]:
    last = found[-1]["date"] if found else None
    # The record's own date wins over the payment for it; only a payment half an interval (at most a year) later is a
    # later round.
    later = timedelta(days=min(365, ob.months * 30 // 2))
    if ob.done_on is not None and (last is None or last < ob.done_on + later):
        last = ob.done_on
    if last:
        nxt = add_months(last, ob.months)
    else:
        nxt = ob.first_due
    if nxt is None:
        standing, left = Standing.MISSED, None
    else:
        left = (nxt - today).days
        standing = Standing.OVERDUE if left < 0 else Standing.DUE_SOON if left <= SOON_DAYS else Standing.UPCOMING
    return {"next": nxt.isoformat() if nxt else None, "daysLeft": left, "standing": standing.value,
            "lastDone": last.isoformat() if last else None, "history": [_shown(p) for p in found[-4:]]}


def calendar(data_dir: Path, community: Any, *, today: date | None = None) -> dict[str, Any]:
    day = today or date.today()
    payments, first, synced = _payments(data_dir)
    rows = []
    for ob in community.obligations():
        base = {"name": ob.name, "authority": ob.authority, "note": ob.note,
                "rule": f"yearly by {ob.deadline(day.year):%B} {ob.day}" if ob.fixed else
                ob.cadence() if ob.months else "listed"}
        if not ob.tracked:
            nxt = ob.deadline(day.year) if ob.fixed and ob.deadline(day.year) >= day else ob.deadline(day.year + 1) if ob.fixed else None
            rows.append({**base, "standing": Standing.UNTRACKED.value, "next": nxt.isoformat() if nxt else None,
                         "daysLeft": (nxt - day).days if nxt else None, "lastDone": None, "history": []})
            continue
        found = evidence(ob, payments)
        if not ob.fixed and not ob.months:
            rows.append({**base, "rule": "listed", "standing": Standing.LISTED.value, "next": None, "daysLeft": None,
                         "lastDone": found[-1]["date"].isoformat() if found else None, "history": [_shown(p) for p in found[-6:]]})
            continue
        rows.append({**base, **(_fixed(ob, found, first, day) if ob.fixed else _interval(ob, found, day))})
    # Insurance: each policy's term end, with its standing from the insurance review.
    try:
        from jason.tasks.insurance import review

        for p in review(data_dir, community, today=day)["policies"]:
            if not p["termEnd"]:
                continue
            end = date.fromisoformat(p["termEnd"])
            paid = bool(p["nextTermPayments"])
            left = (end - day).days
            # A term that ended without the next one bound is overdue, even while the renewal is under way by email (the
            # note says so): the policy lapses on its date, whoever is late.
            standing = Standing.DONE if paid else Standing.OVERDUE if left < 0 else Standing.DUE_SOON if left <= SOON_DAYS else Standing.UPCOMING
            label = p["kind"].replace("_", " ") + (f" building {p['building']}" if p["building"] else "")
            rows.append({"name": f"Insurance renewal: {label} ({p['number']})", "authority": "the policy term; Civil Code 5300(b)(9) summary",
                         "rule": "yearly at the term's end", "note": p["standing"], "next": p["termEnd"], "daysLeft": left,
                         "standing": standing.value, "lastDone": (p["nextTermPayments"] or [{}])[-1].get("date"), "history": []})
    except Exception as exc:  # the calendar still stands without the insurance rows
        rows.append({"name": "Insurance renewals", "authority": "", "rule": "", "note": f"not read: {exc}", "next": None, "daysLeft": None,
                     "standing": Standing.UNTRACKED.value, "lastDone": None, "history": []})
    # The reserve study: a site visit at least every three years (Civil Code 5550(a)), reviewed every year.
    try:
        from jason.tasks.reserves import load_studies, site_visit_due

        due = site_visit_due(load_studies(data_dir))
        if due["nextSiteVisitForFiscalYear"]:
            fiscal = int(due["nextSiteVisitForFiscalYear"])
            # The study for a fiscal year goes with the budget report, due by December 1 of the year before.
            deadline = date(fiscal - 1, 12, 1)
            left = (deadline - day).days
            rows.append({"name": f"Reserve study with a site visit, for FY{fiscal % 100:02d}", "authority": "Civil Code 5550(a): every three years, reviewed yearly",
                         "rule": "every 3 years", "note": f"last site visit study {due['lastSiteVisitStudy']} (FY{int(due['lastSiteVisitFiscalYear']) % 100:02d})",
                         "next": deadline.isoformat(), "daysLeft": left,
                         "standing": (Standing.OVERDUE if left < 0 else Standing.DUE_SOON if left <= SOON_DAYS else Standing.UPCOMING).value,
                         "lastDone": due["lastSiteVisitStudy"], "history": []})
    except Exception as exc:
        rows.append({"name": "Reserve study", "authority": "Civil Code 5550", "rule": "", "note": f"not read: {exc}", "next": None,
                     "daysLeft": None, "standing": Standing.UNTRACKED.value, "lastDone": None, "history": []})
    order = {Standing.OVERDUE.value: 0, Standing.DUE_SOON.value: 1, Standing.UPCOMING.value: 2, Standing.UNTRACKED.value: 3,
             Standing.LISTED.value: 4, Standing.DONE.value: 5}
    rows.sort(key=lambda r: (order.get(r["standing"], 5), r["next"] or "9999"))
    late = [{"name": r["name"], **h} for r in rows for h in r.get("history", []) if isinstance(h, dict) and h.get("standing") in
            (Standing.LATE.value, Standing.MISSED.value)]
    return {
        "found": bool(rows),
        "asOf": day.isoformat(),
        "paymentsFrom": first.isoformat() if first else None,
        "paymentsSynced": synced,
        "obligations": rows,
        "lateOrMissed": late,
        "caveats": [
            "A payment in the obligation's PayHOA category is evidence it was done, not proof: a filing, an inspection "
            "report, or a notice is the record.",
            "A year before PayHOA's first transaction is not judged.",
            "A deadline no store shows (the budget report, the reviewed statement) is listed so a person can check it.",
        ],
    }


def calendar_lines(result: dict[str, Any]) -> list[str]:
    out = [f"Calendar as of {result['asOf']} (PayHOA {result['paymentsFrom'] or '?'} to {result['paymentsSynced'] or '?'})", ""]
    for r in result["obligations"]:
        when = f"{r['next']} ({r['daysLeft']} days)" if r["next"] and r["daysLeft"] is not None else (r["next"] or "-")
        last = f"; last {r['lastDone']}" if r.get("lastDone") else ""
        out.append(f"[{r['standing']}] {r['name']}: {when}{last}")
        if r.get("note"):
            out.append(f"    {r['note']}")
    if result["lateOrMissed"]:
        out.append("")
        out.append("Past deadlines done late or with no evidence")
        for h in result["lateOrMissed"]:
            detail = f"{h['daysLate']} days late ({h['evidence'][0]['date']})" if h.get("daysLate") is not None else "no payment found"
            out.append(f"  {h['deadline']} {h['name']}: {detail}")
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["calendar", "calendar_lines", "evidence"]
