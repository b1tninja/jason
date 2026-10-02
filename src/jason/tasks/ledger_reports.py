"""PayHOA's own ledger reports, used to validate the treasurer's report PDFs in the library.

The treasurer's report is not written by hand: it is PayHOA's "Treasurer's Report" packet
(balance sheet, aging, budget performance, budget vs actual, profit vs loss, general ledger,
and the two bank reconciliations), run each month and saved as a PDF. So the document model
can be checked against its source:

- ``fetch`` reads every saved packet run (``/saved-reports``: name, criteria, completion time,
  the PDF's SHA-256) and a balance sheet as of every month end since the first run, and writes
  ``data/payhoa/saved-reports.json`` and ``data/payhoa/balance-sheets.json``. With ``download``
  it also saves each run's PDF the library does not hold. It changes nothing in PayHOA.
- ``validate`` matches each library copy to a run by its hash (an unmatched copy was edited or
  redacted after PayHOA produced it), resolves each run's period from its criteria, notes runs
  whose dates are not the month they are named for, and compares each report's printed bank
  balances with PayHOA's balance sheet for the same date today. A difference means the ledger
  was changed after the report went to the board.
"""

from __future__ import annotations

import calendar
import json
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

TREASURER_PACKET = "Treasurer's Report"
RUNS = "saved-reports.json"
SHEETS = "balance-sheets.json"
VALIDATION = "ledger-validation.json"


def _payhoa_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "payhoa"


def month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _day(value: str) -> date | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")[:19]).date()
    except ValueError:
        return None


def run_period(run: dict[str, Any]) -> tuple[str, list[str]]:
    """The month a packet run's balance sheet reports (``YYYY-MM``), and notes on dates that do not fit a monthly report."""
    notes: list[str] = []
    criteria = {c.get("report"): c.get("criteria") or {} for c in run.get("criteria") or []}
    sheet = criteria.get("balance-sheet", {})
    ledger = criteria.get("general-ledger", {})
    done = _day(run.get("completedAt") or "") or date.today()
    as_of = sheet.get("asOfDate", "PREVIOUS_MONTH_END")
    if as_of == "PREVIOUS_MONTH_END":
        year, month = (done.year, done.month - 1) if done.month > 1 else (done.year - 1, 12)
        period = f"{year}-{month:02d}"
    else:
        # A stored date is local midnight in UTC ("2026-04-30T07:00:00.000Z" is April 30 in California).
        day = _day(as_of)
        period = f"{day.year}-{day.month:02d}" if day else ""
        if day and day != month_end(day.year, day.month):
            notes.append(f"its balance sheet is as of {day.isoformat()}, not a month end")
    start, end = ledger.get("startDate", ""), ledger.get("endDate", "")
    if start and not start.startswith("PREVIOUS"):
        first, last = _day(start), _day(end)
        if first and last and (first.year, first.month) != (last.year, last.month):
            notes.append(f"its general ledger runs {first.isoformat()} to {last.isoformat()}, not one month")
    named = re.search(r"(20\d\d)-(\d\d)", run.get("name") or "")
    if named and period and f"{named.group(1)}-{named.group(2)}" != period:
        notes.append(f"it is named {named.group(1)}-{named.group(2)} but reports {period}")
    if not named and "August" not in (run.get("name") or ""):
        notes.append("its name carries no month")
    return period, notes


def fetch(client: Any, org_id: int, data_dir: Path, *, download: bool = False, library_hashes: set[str] | None = None,
          log: Callable[[str], None] | None = None) -> dict[str, int]:
    """Read the saved packet runs and a balance sheet for every month end since the first run. Read-only in PayHOA."""
    runs = client.saved_reports()
    kept = []
    downloaded = 0
    folder = _payhoa_dir(data_dir) / "saved-reports"
    for run in runs:
        uploaded = dict(run.get("uploadedFile") or {})
        url = uploaded.pop("downloadUrl", None)
        if download and url and uploaded.get("fileHash") not in (library_hashes or set()):
            dest = folder / f"{run['id']}-{re.sub(r'[^A-Za-z0-9._() -]', '_', uploaded.get('fileName') or 'report.pdf')}"
            if not dest.is_file():
                client.download_signed_url(url, dest)
                downloaded += 1
        kept.append({**run, "uploadedFile": uploaded})
    out = _payhoa_dir(data_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / RUNS).write_text(json.dumps({"fetchedAt": _now(), "runs": kept}, indent=1, default=str), encoding="utf-8")

    from payhoa.reports import balance_sheet_accounts

    periods = sorted({p for p, _n in (run_period(r) for r in kept if r.get("name", "").startswith(TREASURER_PACKET[:9])) if p})
    today = date.today()
    months: list[tuple[int, int]] = []
    if periods:
        year, month = (int(x) for x in periods[0].split("-"))
        while (year, month) < (today.year, today.month):
            months.append((year, month))
            year, month = (year, month + 1) if month < 12 else (year + 1, 1)
    sheets: dict[str, Any] = {}
    for year, month in months:
        end = month_end(year, month)
        report = client.balance_sheet(org_id, as_of=end.isoformat())
        sheets[f"{year}-{month:02d}"] = {"asOf": end.isoformat(), "lastUpdated": (report.get("extra") or {}).get("lastUpdated"),
                                         "accounts": balance_sheet_accounts(report)}
        if log:
            log(f"balance sheet {end.isoformat()}")
    (out / SHEETS).write_text(json.dumps({"fetchedAt": _now(), "sheets": sheets}, indent=1), encoding="utf-8")
    # The chart of accounts: each account's starting balance and date explain a history the balance sheets no longer show.
    chart = {kind: client.ledger_accounts(org_id, kind) for kind in ("assets", "liabilities", "equities")}
    (out / "ledger-accounts.json").write_text(json.dumps({"fetchedAt": _now(), **chart}, indent=1, default=str), encoding="utf-8")
    return {"runs": len(kept), "sheets": len(sheets), "downloaded": downloaded}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def library_reports(data_dir: Path) -> list[dict[str, Any]]:
    """The library's treasurer's reports: id, path, period, sha256, and the text the library read."""
    store = Path(data_dir) / "library" / "library.db"
    if not store.is_file():
        return []
    with sqlite3.connect(f"{store.resolve().as_uri()}?mode=ro", uri=True) as conn:
        rows = conn.execute("SELECT id, path, period, sha256 FROM documents WHERE kind = 'treasurer_report'").fetchall()
    found = []
    for ident, path, period, sha in rows:
        text_file = Path(data_dir) / "library" / "text" / f"{ident}.txt"
        found.append({"id": ident, "path": path, "period": period or "", "sha256": sha or "",
                      "text": text_file.read_text(encoding="utf-8", errors="ignore") if text_file.is_file() else ""})
    return found


def printed_amount(text: str, label: str) -> int | None:
    """The amount a report's balance sheet prints beside an account label (before "Total Assets"), in cents."""
    end = text.find("Total Assets")
    head = text[:end] if end > 0 else text[:8000]
    m = re.search(re.escape(label) + r"\s*\n?\s*(-?)\$?(-?[\d,]+\.\d\d)", head)
    if not m:
        return None
    cents = int(m.group(2).replace(",", "").replace(".", "").replace("-", ""))
    return -cents if (m.group(1) or m.group(2).startswith("-")) else cents


def validate(data_dir: Path) -> dict[str, Any]:
    """Match the library's treasurer's reports to PayHOA's runs, and their printed balances to today's ledger."""
    runs_file, sheets_file = _payhoa_dir(data_dir) / RUNS, _payhoa_dir(data_dir) / SHEETS
    if not runs_file.is_file() or not sheets_file.is_file():
        return {"found": False, "note": "no ledger reports on disk; run jason ledger --fetch"}
    runs = json.loads(runs_file.read_text(encoding="utf-8"))["runs"]
    sheets = json.loads(sheets_file.read_text(encoding="utf-8"))["sheets"]
    library = library_reports(data_dir)
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for doc in library:
        if doc["sha256"]:
            by_hash.setdefault(doc["sha256"], []).append(doc)
    run_rows = []
    matched_hashes: set[str] = set()
    for run in runs:
        if not str(run.get("name") or "").startswith(TREASURER_PACKET[:9]):
            continue
        period, notes = run_period(run)
        file_hash = (run.get("uploadedFile") or {}).get("fileHash", "")
        copies = [d["path"] for d in by_hash.get(file_hash, [])]
        matched_hashes.add(file_hash)
        run_rows.append({"id": run["id"], "name": run["name"], "period": period, "completedAt": run.get("completedAt"),
                         "pages": run.get("totalPages"), "libraryCopies": copies, "notes": notes})
    # The library's copies that are no PayHOA run as generated: redacted, edited, or from elsewhere.
    altered = [{"path": d["path"], "period": d["period"]} for d in library if d["sha256"] and d["sha256"] not in matched_hashes]
    # A copy that is a run takes the run's period; any other copy has only its file name to go by.
    period_of_hash = {(r.get("uploadedFile") or {}).get("fileHash", ""): run_period(r)[0] for r in runs}
    # Where each account's balance stood at each month end, to recognise a copy filed under the wrong month.
    seen_at: dict[tuple[str, int], list[str]] = {}
    for period, sheet in sheets.items():
        for account in sheet["accounts"]:
            seen_at.setdefault((account["label"], account["cents"]), []).append(period)
    # Printed balances against the ledger as of the same month end, today.
    changes: list[dict[str, Any]] = []
    misfiled: list[dict[str, Any]] = []
    checked = 0
    for doc in library:
        period = period_of_hash.get(doc["sha256"]) or doc["period"]
        sheet = sheets.get(period)
        if not sheet or not doc["text"]:
            continue
        for account in sheet["accounts"]:
            if account["section"] != "Bank Accounts":
                continue
            printed = printed_amount(doc["text"], account["label"])
            if printed is None:
                continue
            checked += 1
            if printed == account["cents"]:
                continue
            elsewhere = [p for p in seen_at.get((account["label"], printed), []) if p != period]
            row = {"period": period, "periodFrom": "run" if doc["sha256"] in period_of_hash else "file name", "path": doc["path"],
                   "account": account["label"], "printedCents": printed, "ledgerCents": account["cents"], "asOf": sheet["asOf"]}
            if elsewhere and row["periodFrom"] == "file name":
                misfiled.append({**row, "matchesPeriods": elsewhere})
            else:
                changes.append(row)
    # Accounts a report printed that the ledger's balance sheet for that date no longer carries.
    labels = {a["label"] for sheet in sheets.values() for a in sheet["accounts"] if a["section"] == "Bank Accounts"}
    rewritten: list[dict[str, Any]] = []
    for doc in library:
        period = period_of_hash.get(doc["sha256"]) or doc["period"]
        sheet = sheets.get(period)
        if not sheet or not doc["text"] or doc["sha256"] not in period_of_hash:
            continue
        present = {_key(a["label"]) for a in sheet["accounts"]}
        for label in sorted(label for label in labels if _key(label) not in present):
            printed = printed_amount(doc["text"], label)
            if printed is not None and printed != 0:
                rewritten.append({"period": period, "account": label, "printedCents": printed, "path": doc["path"]})
    missing = [r for r in run_rows if not r["libraryCopies"]]
    result = {
        "found": True,
        "runs": run_rows,
        "runsMissingFromLibrary": [{"name": r["name"], "period": r["period"]} for r in missing],
        "libraryCopiesNotFromARun": altered,
        "balancesChecked": checked,
        "balanceChanges": _dedupe(changes),
        "copiesUnderAnotherMonth": _dedupe(misfiled),
        "accountsTheLedgerDropped": _dedupe_dropped(rewritten),
        "chart": _chart(data_dir),
        "latestSheet": _latest(sheets),
        "caveats": [
            "A library copy that matches no run by hash was changed after PayHOA produced it (a redacted copy is expected to).",
            "A printed balance that differs from today's balance sheet for the same date means the ledger was edited after "
            "the report was run; the report the board saw is the record of what it was told.",
        ],
    }
    (_payhoa_dir(data_dir) / VALIDATION).write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def _dedupe(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    kept = []
    for change in sorted(changes, key=lambda c: (c["period"], c["account"], c["path"])):
        key = (change["period"], change["account"], change["printedCents"])
        if key in seen:
            continue
        seen.add(key)
        kept.append(change)
    return kept


def _key(label: str) -> str:
    """An account label without its bank in parentheses, folded."""
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", "", label)).strip().casefold()


def _dedupe_dropped(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    kept = []
    for row in sorted(rows, key=lambda r: (r["account"], r["period"])):
        if (row["account"], row["period"]) in seen:
            continue
        seen.add((row["account"], row["period"]))
        kept.append(row)
    return kept


def _chart(data_dir: Path) -> list[dict[str, Any]]:
    """Asset accounts with their starting balance and date (``ledger-accounts.json``)."""
    path = _payhoa_dir(data_dir) / "ledger-accounts.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [{"id": a.get("id"), "label": a.get("label"), "startingBalanceCents": a.get("startingBalance"),
             "startingBalanceDate": a.get("startingBalanceDate"), "balanceCents": a.get("balance")}
            for a in data.get("assets", []) if not a.get("deletedAt")]


def _latest(sheets: dict[str, Any]) -> dict[str, Any] | None:
    if not sheets:
        return None
    period = max(sheets)
    return {"period": period, **sheets[period]}


def ledger_reserves(data_dir: Path) -> dict[str, Any] | None:
    """Reserve accounts on PayHOA's latest month-end balance sheet (including a CD no bank feed reaches)."""
    path = _payhoa_dir(data_dir) / SHEETS
    if not path.is_file():
        return None
    latest = _latest(json.loads(path.read_text(encoding="utf-8"))["sheets"])
    if not latest:
        return None
    reserve = re.compile(r"reserve|certificate|\bc/?d\b|\bcds?\b", re.I)
    accounts = {a["label"]: a["cents"] for a in latest["accounts"] if a["section"] == "Bank Accounts" and reserve.search(a["label"])}
    return {"period": latest["period"], "asOf": latest["asOf"], "accounts": accounts, "totalCents": sum(accounts.values())}


def dollars(cents: int | None) -> str:
    return "-" if cents is None else f"${cents / 100:,.2f}"


def validation_lines(result: dict[str, Any]) -> list[str]:
    if not result.get("found"):
        return [result.get("note", "no validation")]
    runs = result["runs"]
    out = [f"{len(runs)} treasurer's report runs in PayHOA; {sum(1 for r in runs if r['libraryCopies'])} have a copy in the library "
           f"that matches by hash; {result['balancesChecked']} printed bank balances checked against the ledger"]
    if result["runsMissingFromLibrary"]:
        out.append("Runs with no identical copy in the library: " + ", ".join(f"{r['name']} ({r['period']})" for r in result["runsMissingFromLibrary"]))
    if result["libraryCopiesNotFromARun"]:
        out.append(f"{len(result['libraryCopiesNotFromARun'])} library copies match no run (redacted or edited after PayHOA produced them)")
    for run in runs:
        for note in run["notes"]:
            out.append(f"  run '{run['name']}' ({run['completedAt'][:10]}): {note}")
    if result.get("copiesUnderAnotherMonth"):
        out.append("Library copies whose balances are another month's (filed under the wrong month):")
        for c in result["copiesUnderAnotherMonth"]:
            out.append(f"  {c['path']}: {c['account']} {dollars(c['printedCents'])} is the ledger's figure for "
                       f"{', '.join(c['matchesPeriods'])}, not {c['period']}")
    dropped = result.get("accountsTheLedgerDropped") or []
    if dropped:
        by_account: dict[str, list[str]] = {}
        for row in dropped:
            by_account.setdefault(row["account"], []).append(row["period"])
        chart = {a["label"]: a for a in result.get("chart") or []}
        for account, periods in by_account.items():
            start = chart.get(account, {})
            why = (f"; the chart of accounts now starts it at {dollars(start.get('startingBalanceCents'))} on {start.get('startingBalanceDate')}"
                   if start.get("startingBalanceDate") else "")
            out.append(f"The reports printed '{account}' for {periods[0]} through {periods[-1]} ({len(periods)} months); PayHOA's "
                       f"balance sheets for those dates no longer carry it{why}.")
    if result["balanceChanges"]:
        out.append("Balances the ledger now reports differently for the same date (late-imported or re-dated transactions, or edits):")
        for c in result["balanceChanges"]:
            out.append(f"  {c['period']} {c['account']}: printed {dollars(c['printedCents'])}, ledger as of {c['asOf']} now "
                       f"{dollars(c['ledgerCents'])} (period from the {c['periodFrom']}; {c['path']})")
    latest = result.get("latestSheet")
    if latest:
        out.append(f"Latest balance sheet ({latest['asOf']}):")
        out.extend(f"  {a['section']}: {a['label']} {dollars(a['cents'])}" for a in latest["accounts"])
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["fetch", "validate", "run_period", "printed_amount", "ledger_reserves", "library_reports", "validation_lines"]
