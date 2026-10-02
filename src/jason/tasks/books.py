"""The association's books from PayHOA's general ledger, stored month by month and reported locally.

``sync`` asks PayHOA for the general ledger one month at a time (the captured
``POST /reports/general-ledger/json``) and keeps every row in ``data/payhoa/ledger.db``. The
ledger changes after the fact (late imports, re-dated entries, a re-based account), so each sync
re-reads the recent months, and ``--full`` re-reads them all; a month's rows are replaced whole.

Everything else reads the store: profit and loss, categories by month, vendors, cash flow,
balances, receivables without names, and queries (``jason.community.ledger``). ``check`` sets the
ledger's year-to-date category totals beside PayHOA's own budget-against-actual figures from the
last ``jason budget`` snapshot, so the two views of the same books can be seen to agree.
"""

from __future__ import annotations

import calendar
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jason.community.ledger import EXPENSE, INCOME, Entry, entries, profit_and_loss

STORE = "ledger.db"
SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    month TEXT NOT NULL,
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    account TEXT NOT NULL,
    day TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    memo TEXT NOT NULL,
    vendor TEXT NOT NULL,
    debit INTEGER NOT NULL,
    credit INTEGER NOT NULL,
    balance INTEGER NOT NULL,
    starting INTEGER NOT NULL,
    PRIMARY KEY (month, seq)
);
CREATE INDEX IF NOT EXISTS entries_day ON entries(day);
CREATE TABLE IF NOT EXISTS months (
    month TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    rows INTEGER NOT NULL,
    total_records INTEGER,
    last_updated TEXT
);
"""


def store_path(data_dir: Path) -> Path:
    return Path(data_dir) / "payhoa" / STORE


def months_between(first: str, last: str) -> list[str]:
    year, month = (int(x) for x in first.split("-"))
    end_year, end_month = (int(x) for x in last.split("-"))
    found = []
    while (year, month) <= (end_year, end_month):
        found.append(f"{year}-{month:02d}")
        year, month = (year, month + 1) if month < 12 else (year + 1, 1)
    return found


def sync(client: Any, org_id: int, data_dir: Path, *, first: str = "2024-01", recent: int = 4, full: bool = False,
         today: date | None = None, log: Callable[[str], None] | None = None) -> dict[str, int]:
    """Read the general ledger month by month into the store: every month not yet stored, and the last ``recent`` again."""
    from payhoa.reports import ledger_rows

    day = today or date.today()
    wanted = months_between(first, f"{day.year}-{day.month:02d}")
    path = store_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        have = {m for (m,) in conn.execute("SELECT month FROM months")}
        todo = [m for m in wanted if full or m not in have or m in wanted[-recent:]]
        rows_read = 0
        for month in todo:
            year, mon = (int(x) for x in month.split("-"))
            start, end = f"{month}-01", f"{month}-{calendar.monthrange(year, mon)[1]:02d}"
            report = client.general_ledger(org_id, start_date=start, end_date=end)
            rows = ledger_rows(report)
            conn.execute("DELETE FROM entries WHERE month = ?", (month,))
            conn.executemany("INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [
                (month, i, r["type"], r["label"], r["date"], r["description"], r["category"], r["memo"], r["vendor"],
                 r["debit"], r["credit"], r["balance"], int(r["starting"])) for i, r in enumerate(rows)])
            extra = report.get("extra") or {}
            conn.execute("INSERT OR REPLACE INTO months VALUES (?,?,?,?,?)",
                         (month, datetime.now(timezone.utc).isoformat(timespec="seconds"), len(rows), extra.get("totalRecords"), extra.get("lastUpdated")))
            conn.commit()
            rows_read += len(rows)
            if log:
                log(f"{month}: {len(rows)} rows")
    return {"months": len(todo), "rows": rows_read}


def load(data_dir: Path) -> list[Entry]:
    """Every stored ledger entry, oldest first."""
    path = store_path(data_dir)
    if not path.is_file():
        return []
    with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("SELECT * FROM entries ORDER BY day, month, seq")]
    return entries(rows)


def stored_months(data_dir: Path) -> list[dict[str, Any]]:
    path = store_path(data_dir)
    if not path.is_file():
        return []
    with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM months ORDER BY month")]


def check(data_dir: Path, items: list[Entry] | None = None) -> dict[str, Any]:
    """The ledger's year-to-date totals by category against PayHOA's budget-against-actual actuals (``jason budget``)."""
    from jason.tasks.finance import latest_year, load as load_snapshot

    year = latest_year(Path(data_dir))
    snap = load_snapshot(Path(data_dir), year) if year else None
    if not snap:
        return {"found": False, "note": "no finance snapshot; run jason budget"}
    items = items if items is not None else load(data_dir)
    through = int(snap.get("throughMonth") or 12)
    end = date(year, through, calendar.monthrange(year, through)[1])
    pl = profit_and_loss(items, date(year, 1, 1), end)
    rows = []
    for side, key, ledger in (("expense", "expenseYtd", pl["expense"]), ("revenue", "revenueYtd", pl["income"])):
        actual = {str(i.get("name")): int(i.get("actual") or 0) for i in (snap.get(key) or {}).get("items", [])
                  if i.get("id") and not i.get("rollup")}
        for name in sorted(set(actual) | set(ledger)):
            a, l = actual.get(name, 0), ledger.get(name, 0)
            if a or l:
                rows.append({"side": side, "category": name, "payhoaCents": a, "ledgerCents": l, "differenceCents": l - a})
    differ = [r for r in rows if abs(r["differenceCents"]) > 100]
    return {"found": True, "year": year, "through": end.isoformat(), "snapshotSyncedAt": snap.get("syncedAt"),
            "categories": len(rows), "agree": len(rows) - len(differ), "differ": differ}


def profit_loss_path(data_dir: Path, year: int) -> Path:
    return Path(data_dir) / "payhoa" / f"profit-loss-{year}.json"


def fetch_profit_loss(client: Any, org_id: int, data_dir: Path, year: int) -> Path:
    """PayHOA's own Profit vs Loss by Month for a year (``/reports/profit-vs-loss/by-month/0``), kept as PayHOA sent it."""
    report = client.profit_loss_by_month(org_id, start_date=f"{year}-01-01", end_date=f"{year}-12-31")
    path = profit_loss_path(data_dir, year)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "year": year,
                                "report": report}), encoding="utf-8")
    return path


def compare_months(items: list[Entry], payhoa_rows: list[dict[str, Any]], year: int) -> dict[str, Any]:
    """The ledger's category totals month by month against PayHOA's Profit vs Loss by Month (``category_totals`` rows).
    A category only one side has is listed by itself: PayHOA's "Uncategorized Account Credits" are unit-account
    credits with no category, and the ledger's income categories include prepayments the P&L does not."""
    from jason.community.ledger import by_month

    start, end = date(year, 1, 1), date(year, 12, 31)
    ours = {**by_month(items, INCOME, start, end), **by_month(items, EXPENSE, start, end)}
    differ, cells, only_payhoa = [], 0, []
    names = set()
    for row in payhoa_rows:
        names.add(row["name"])
        mine = ours.get(row["name"])
        if mine is None:
            if row["total"]:
                only_payhoa.append({"side": row["side"], "category": row["name"], "cents": row["total"]})
            continue
        for column, cents in row["columns"].items():
            month = f"{column[:4]}-{column[4:]}"
            cells += 1
            if mine.get(month, 0) != cents:
                differ.append({"category": row["name"], "month": month, "payhoaCents": cents, "ledgerCents": mine.get(month, 0),
                               "differenceCents": mine.get(month, 0) - cents})
    only_ledger = [{"category": name, "cents": sum(months.values())} for name, months in sorted(ours.items())
                   if name not in names and sum(months.values())]
    return {"year": year, "cells": cells, "agree": cells - len(differ), "differ": differ, "onlyPayhoa": only_payhoa, "onlyLedger": only_ledger}


def check_months(data_dir: Path, items: list[Entry] | None = None, year: int | None = None) -> dict[str, Any]:
    """``compare_months`` against the stored ``profit-loss-{year}.json`` (``jason books --sync`` fetches it)."""
    from payhoa.reports import category_totals

    items = items if items is not None else load(data_dir)
    year = year or (max(e.day for e in items).year if items else date.today().year)
    path = profit_loss_path(data_dir, year)
    if not path.is_file():
        return {"found": False, "note": f"no PayHOA profit and loss for {year}; run jason books --sync"}
    stored = json.loads(path.read_text(encoding="utf-8"))
    return {"found": True, "fetchedAt": stored.get("fetchedAt"), **compare_months(items, category_totals(stored["report"]), year)}


def dollars(cents: int | None) -> str:
    return "-" if cents is None else f"${cents / 100:,.2f}"


REPORTS = ("pl", "months", "vendors", "cashflow", "balances", "receivables", "check", "query")


def books_report(data_dir: Path, report: str, *, start: date | None = None, end: date | None = None, kind: str = "expense",
                 text: str = "", payee: str = "", category: str = "", account: str = "", minimum: int | None = None,
                 maximum: int | None = None, owners: bool = False, limit: int = 200) -> dict[str, Any]:
    """One report over the stored ledger, as a dict. ``report`` is one of ``REPORTS``."""
    from jason.community import ledger

    items = load(data_dir)
    if not items:
        return {"found": False, "note": "no ledger on disk; run jason books --sync"}
    last = max(e.day for e in items)
    start = start or date(last.year, 1, 1)
    end = end or last
    base = {"found": True, "report": report, "start": start.isoformat(), "end": end.isoformat(), "ledgerThrough": last.isoformat()}
    if report == "pl":
        return {**base, **ledger.profit_and_loss(items, start, end)}
    if report == "months":
        return {**base, "kind": kind, "months": ledger.by_month(items, ledger.INCOME if kind.startswith("inc") else ledger.EXPENSE, start, end)}
    if report == "vendors":
        return {**base, "vendors": ledger.vendors(items, start, end)[:limit]}
    if report == "cashflow":
        return {**base, "accounts": ledger.cash_flow(items, start, end)}
    if report == "balances":
        return {**base, "asOf": end.isoformat(), "balances": ledger.balances(items, end, owners=owners)}
    if report == "receivables":
        return {**base, **ledger.receivables(items, end)}
    if report == "check":
        return {**base, **check(data_dir, items), "months": check_months(data_dir, items, end.year)}
    if report == "query":
        rows = ledger.query(items, text=text, payee=payee, category=category, account=account, minimum=minimum, maximum=maximum,
                            start=start, end=end, owners=owners, limit=limit)
        return {**base, "rows": rows, "count": len(rows)}
    raise ValueError(f"report is one of {', '.join(REPORTS)}")


def report_lines(result: dict[str, Any]) -> list[str]:
    """A report as terminal lines."""
    if not result.get("found"):
        return [result.get("note", "no ledger")]
    out = [f"{result['report']} {result['start']} to {result['end']} (ledger through {result['ledgerThrough']})"]
    kind = result["report"]
    if kind == "pl":
        out.append(f"  income {dollars(result['incomeCents'])}, expense {dollars(result['expenseCents'])}, net {dollars(result['netCents'])}")
        out.extend(f"  income   {name:<36} {dollars(c):>14}" for name, c in result["income"].items())
        out.extend(f"  expense  {name:<36} {dollars(c):>14}" for name, c in result["expense"].items())
    elif kind == "months":
        for name, months in result["months"].items():
            out.append(f"  {name:<34} " + "  ".join(f"{m[2:]} {dollars(c)}" for m, c in months.items()))
    elif kind == "vendors":
        out.extend(f"  {v['payee'][:40]:<40} {dollars(v['cents']):>14} {v['payments']:>4} payments {v['first']} to {v['last']}  "
                   + ", ".join(v["categories"]) for v in result["vendors"])
    elif kind == "cashflow":
        for name, a in result["accounts"].items():
            out.append(f"  {name}: start {dollars(a['startCents'])}, in {dollars(a['inCents'])}, out {dollars(a['outCents'])}, end {dollars(a['endCents'])}")
            out.extend(f"      in   {k:<32} {dollars(v):>12}" for k, v in list(a["in"].items())[:8])
            out.extend(f"      out  {k:<32} {dollars(v):>12}" for k, v in list(a["out"].items())[:8])
    elif kind == "balances":
        out.extend(f"  {name:<60} {dollars(c):>14}" for name, c in result["balances"].items())
    elif kind == "receivables":
        out.append(f"  owed {dollars(result['owedCents'])} by {result['unitsOwing']} units; prepaid {dollars(result['prepaidCents'])} by {result['unitsPrepaid']} units")
    elif kind == "check":
        if result.get("found") is False:
            out.append(f"  {result.get('note')}")
        else:
            out.append(f"  {result['agree']} of {result['categories']} categories agree with PayHOA's budget against actual through {result['through']}")
            out.extend(f"  differs: {r['side']} {r['category']}: ledger {dollars(r['ledgerCents'])}, PayHOA {dollars(r['payhoaCents'])}" for r in result["differ"])
        months = result.get("months") or {}
        if not months.get("found"):
            out.append(f"  {months.get('note', 'no PayHOA profit and loss')}")
        else:
            out.append(f"  {months['agree']} of {months['cells']} category-months agree with PayHOA's Profit vs Loss by Month for {months['year']}")
            out.extend(f"  differs: {r['category']} {r['month']}: ledger {dollars(r['ledgerCents'])}, PayHOA {dollars(r['payhoaCents'])}"
                       for r in months["differ"])
            out.extend(f"  only in PayHOA's P&L: {r['category']} {dollars(r['cents'])}" for r in months["onlyPayhoa"])
            out.extend(f"  only in the ledger: {r['category']} {dollars(r['cents'])}" for r in months["onlyLedger"])
    elif kind == "query":
        out.extend(f"  {r['date']} {r['type'][:18]:<18} {r['account'][:28]:<28} {r['payee'][:30]:<30} "
                   f"{dollars(r['debitCents'] or -r['creditCents']):>12}  {r['description'][:60]}" for r in result["rows"])
        out.append(f"  {result['count']} rows")
    return out


__all__ = ["sync", "load", "stored_months", "check", "check_months", "compare_months", "fetch_profit_loss", "store_path", "months_between", "books_report", "report_lines", "REPORTS"]
