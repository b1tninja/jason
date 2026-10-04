"""The reserve studies on disk, read into funding plans, and set beside the budget and the bank.

Sources: every library document classified as a reserve study (``data/library/library.db``,
files under ``data/library/files``), and the PDFs in ``data/reserve-studies/`` (the updates
that arrive by email and are not in the library). The same file found twice is read once.

The brief answers the budget's questions: what the latest study asks the association to put
into reserves next year, what it expects to spend, whether the budget's transfer line and the
monthly transfers follow the plan, where the reserve accounts stand against the plan, and
when the next study with a site visit is due (Civil Code 5550: a site visit at least every
three years, a review every year). Jason reads; the board adopts the budget and the funding plan.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.reserve_study import ReserveStudy, StudyLevel, read_study

STUDIES_DIR = "reserve-studies"
# A PayHOA account name that reads as reserve money: a reserve account or a certificate of deposit.
RESERVE_NAME = re.compile(r"reserve|certificate|\bc/?d\b|\bcds?\b", re.I)
TRANSFER_LINE = "Transfer to Reserves"
ANALYST_LINE = "Reserve Analyst"

CAVEATS = (
    "Figures are the study's own; the study is an estimate by its preparer, and its percent funded uses the "
    "statute's formula (current cost times age over useful life), not the cash-flow plan's target.",
    "Planned expenditures are the study's schedule at inflated cost; an item the board has not bought stays planned.",
    "Reserve balances are Plaid's as PayHOA last refreshed them; the bank statement is the record.",
    "Adopting a contribution or a special assessment is the board's decision; the disclosure summary goes to members with the budget.",
)


def study_files(data_dir: Path) -> list[Path]:
    """Every reserve study PDF on disk: the library's classified studies and ``data/reserve-studies``. One per content."""
    data_dir = Path(data_dir)
    candidates: list[Path] = []
    store = data_dir / "library" / "library.db"
    if store.is_file():
        with sqlite3.connect(f"{store.resolve().as_uri()}?mode=ro", uri=True) as conn:
            for (path,) in conn.execute("SELECT path FROM documents WHERE kind = 'reserve_study'"):
                local = data_dir / "library" / "files" / path
                if local.is_file():
                    candidates.append(local)
    folder = data_dir / STUDIES_DIR
    if folder.is_dir():
        candidates.extend(sorted(folder.glob("*.pdf")))
    seen: set[str] = set()
    found: list[Path] = []
    for path in candidates:
        if path.suffix.lower() != ".pdf":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        found.append(path)
    return found


def load_studies(data_dir: Path) -> list[ReserveStudy]:
    """Each study, oldest fiscal year first."""
    studies = [read_study(path) for path in study_files(data_dir)]
    return sorted(studies, key=lambda s: (s.fiscal_year or 0, s.prepared or date.min))


def latest_study(studies: list[ReserveStudy]) -> ReserveStudy | None:
    """The study the brief reads its plan from: the latest with a projection, else the latest (``studies`` oldest first)."""
    if not studies:
        return None
    return max((s for s in studies if s.projection), key=lambda s: (s.fiscal_year or 0, s.prepared or date.min), default=studies[-1])


_LATEST: dict[str, tuple[tuple[tuple[str, int], ...], tuple[str, str]]] = {}


def latest_study_ref(data_dir: Path) -> dict[str, Any] | None:
    """The latest reserve study's ``DocRef`` (docs/console/doc-component.md): its PDF under the data folder
    (``file:reserve-studies/...`` or the library's copy), named by its fiscal year. None when no study is on disk. The
    choice is read once a version of the files (reading the studies parses each PDF); the reference, with its level, is
    built each time."""
    from jason.approvals.docref import file_ref

    files = study_files(data_dir)
    stamp = tuple((str(p), p.stat().st_mtime_ns) for p in files)
    key = str(Path(data_dir).resolve())
    cached = _LATEST.get(key)
    if cached is None or cached[0] != stamp:
        studies = sorted((read_study(p) for p in files), key=lambda s: (s.fiscal_year or 0, s.prepared or date.min))
        latest = latest_study(studies)
        rel = name = ""
        if latest is not None:
            try:
                rel = Path(latest.source).resolve().relative_to(Path(data_dir).resolve()).as_posix()
            except (OSError, ValueError):
                rel = ""
            name = f"Reserve study, fiscal year {latest.fiscal_year}" if latest.fiscal_year else ""
        cached = _LATEST[key] = (stamp, (rel, name))
    rel, name = cached[1]
    if not rel:
        return None
    try:
        return file_ref(rel, name=name or None, data_dir=data_dir)
    except ValueError:
        return None


def _percent(study: ReserveStudy) -> float | None:
    d = study.disclosure
    if d.percent_funded is not None:
        return d.percent_funded
    if d.projected_end_of_year_cents and d.required_end_of_year_cents:
        return round(d.projected_end_of_year_cents / d.required_end_of_year_cents, 3)
    return None


def history(studies: list[ReserveStudy]) -> list[dict[str, Any]]:
    return [{
        "fiscalYear": s.fiscal_year,
        "preparer": s.preparer,
        "prepared": s.prepared.isoformat() if s.prepared else None,
        "level": s.level.value if s.level else None,
        "units": s.units,
        "beginningBalanceCents": s.beginning_balance_cents or s.disclosure.current_balance_cents,
        "annualContributionCents": s.annual_contribution_cents,
        "requiredEndOfYearCents": s.disclosure.required_end_of_year_cents,
        "projectedEndOfYearCents": s.disclosure.projected_end_of_year_cents,
        "percentFunded": _percent(s),
        "sufficientFor30Years": s.disclosure.sufficient_for_30_years,
        "components": len(s.components),
        "source": Path(s.source).name,
        "notes": list(s.notes),
    } for s in studies]


# A balance-sheet line naming a reserve account ("Reserve Account (Chase)", "Reserve C/D (Chase)",
# "CD 7/3/26 (First Citizens Bank)"), not an income or expense line ("Reserves", "Reserve Analyst").
_ACCOUNT_LINE = re.compile(r"^[ \t]*((?:(?:Old\s+)?Reserve\s+(?:Account|C/?D)|C/?D\b|Certificate of Deposit|C/D Settlement)[^\n$]{0,60}?)\s*\n?\s*\$([\d,]+\.\d\d)", re.M | re.I)


def treasurer_reserves(data_dir: Path) -> dict[str, dict[str, Any]]:
    """Each month's reserve accounts as the association's treasurer's report lists them: {period: {accounts, total, source}}.

    Read from the library's text of documents classified as treasurer's reports. The report is the association's
    own record, and it carries accounts PayHOA cannot see (a certificate of deposit at another bank).
    """
    store = Path(data_dir) / "library" / "library.db"
    if not store.is_file():
        return {}
    found: dict[str, dict[str, Any]] = {}
    with sqlite3.connect(f"{store.resolve().as_uri()}?mode=ro", uri=True) as conn:
        rows = conn.execute("SELECT id, path, period FROM documents WHERE kind = 'treasurer_report' AND period != '' ORDER BY path").fetchall()
    for ident, path, period in rows:
        text_file = Path(data_dir) / "library" / "text" / f"{ident}.txt"
        if not text_file.is_file() or period in found:
            continue
        accounts: dict[str, int] = {}
        text = text_file.read_text(encoding="utf-8", errors="ignore")
        # The balance sheet comes first; transfers and reconciliations after "Total Assets" name the same accounts.
        end = text.find("Total Assets")
        for match in _ACCOUNT_LINE.finditer(text[:end] if end > 0 else text[:6000]):
            name = " ".join(match.group(1).split())
            accounts.setdefault(name, int(match.group(2).replace(",", "").replace(".", "")))
        if accounts:
            found[period] = {"accounts": accounts, "totalCents": sum(accounts.values()), "source": path}
    return dict(sorted(found.items()))


def ledger_month_ends(data_dir: Path) -> dict[str, dict[str, Any]]:
    """Reserve accounts on each of PayHOA's month-end balance sheets (``jason ledger --fetch``), in the shape
    ``treasurer_reserves`` gives: {period: {accounts, totalCents, source}}."""
    path = Path(data_dir) / "payhoa" / "balance-sheets.json"
    if not path.is_file():
        return {}
    found: dict[str, dict[str, Any]] = {}
    for period, sheet in json.loads(path.read_text(encoding="utf-8")).get("sheets", {}).items():
        accounts = {a["label"]: a["cents"] for a in sheet.get("accounts", [])
                    if a.get("section") == "Bank Accounts" and RESERVE_NAME.search(a["label"])}
        if accounts:
            found[period] = {"accounts": accounts, "totalCents": sum(accounts.values()), "source": "ledger"}
    return found


def account_key(label: str) -> str:
    """An account label without its bank in parentheses, folded: "Reserve C/D (Chase)" and "Reserve C/D" meet."""
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", "", label)).strip().casefold()


def merge_reserve_sources(printed: dict[str, dict[str, Any]], ledger: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Each month's reserve accounts from PayHOA's balance sheet, plus any account the treasurer's report printed that the
    ledger no longer carries for that date (its history was rewritten, as when an account's starting date moves)."""
    found: dict[str, dict[str, Any]] = {}
    for period in sorted(set(printed) | set(ledger)):
        mine = dict((ledger.get(period) or {}).get("accounts") or {})
        # "Reserve Account" (a 2024 report) and "Reserve Account (Chase)" (the ledger today) are one account.
        known = {account_key(k) for k in mine}
        missing = {k: v for k, v in ((printed.get(period) or {}).get("accounts") or {}).items() if account_key(k) not in known}
        if period in ledger:
            mine.update(missing)
            source = "ledger" if not missing else "ledger + report"
        else:
            source = "report"
        found[period] = {"accounts": mine, "totalCents": sum(mine.values()), "source": source,
                         "fromReportOnly": sorted(missing) if period in ledger else []}
    return found


def report_checks(studies: list[ReserveStudy], reports: dict[str, dict[str, Any]]) -> list[str]:
    """Each study's beginning balance against the treasurer's report for the December before its fiscal year."""
    found: list[str] = []
    for s in studies:
        started = s.beginning_balance_cents or s.disclosure.current_balance_cents
        report = reports.get(f"{(s.fiscal_year or 0) - 1}-12")
        if not started or not report:
            continue
        gap = report["totalCents"] - started
        if abs(gap) > max(100_000, report["totalCents"] * 0.05):
            listed = ", ".join(f"{name} ${cents / 100:,.2f}" for name, cents in report["accounts"].items())
            where = {"ledger": "PayHOA's balance sheet", "ledger + report": "PayHOA's balance sheet and the treasurer's report"}.get(
                report.get("source"), "the treasurer's report")
            found.append(f"The FY{s.fiscal_year} study starts {s.fiscal_year} at ${started / 100:,.0f}; {where} for "
                         f"December {s.fiscal_year - 1} holds ${report['totalCents'] / 100:,.2f} in reserve accounts ({listed}). "
                         f"The study's beginning balance is {'short' if gap > 0 else 'over'} by ${abs(gap) / 100:,.0f}, and its percent "
                         "funded moves with it.")
    return found


def checks(studies: list[ReserveStudy], units: int) -> list[str]:
    """What a person should look at: a wrong unit count, a plan the next study did not start from."""
    found: list[str] = []
    for s in studies:
        if s.units and s.units != units:
            found.append(f"The FY{s.fiscal_year} study by {s.preparer} counts {s.units} units; the association has {units}. "
                         "Its per-unit figures are off by that ratio.")
    for before, after in zip(studies, studies[1:]):
        if not before.fiscal_year or not after.fiscal_year or after.fiscal_year != before.fiscal_year + 1:
            continue
        row = before.year(after.fiscal_year - 1)
        planned = row.ending_balance_cents if row else before.disclosure.projected_end_of_year_cents
        started = after.beginning_balance_cents or after.disclosure.current_balance_cents
        if planned and started and planned == started:
            found.append(f"The FY{after.fiscal_year} study starts {after.fiscal_year} at ${started / 100:,.0f}, the FY{before.fiscal_year} "
                         f"study's projection to the dollar: it carried the old plan forward rather than the bank balance. "
                         "Compare it with the reserve accounts on January 1.")
        elif planned and started and abs(planned - started) > max(100_000, planned * 0.05):
            gap = started - planned
            found.append(f"The FY{before.fiscal_year} study projected ${planned / 100:,.0f} at the end of {before.fiscal_year}; "
                         f"the FY{after.fiscal_year} study starts {after.fiscal_year} at ${started / 100:,.0f} "
                         f"({'+' if gap > 0 else '-'}${abs(gap) / 100:,.0f}). Check {before.fiscal_year}'s reserve spending and "
                         "transfers, and that the beginning balance counts every reserve account.")
    return found


def site_visit_due(studies: list[ReserveStudy]) -> dict[str, Any]:
    """Civil Code 5550(a): a visual inspection at least once every three years; a review of the study every year."""
    visits = [s for s in studies if s.level in (StudyLevel.FULL, StudyLevel.UPDATE_WITH_SITE_VISIT) and s.prepared]
    last = max(visits, key=lambda s: s.prepared) if visits else None
    latest = max(studies, key=lambda s: (s.fiscal_year or 0, s.prepared or date.min)) if studies else None
    return {
        "lastSiteVisitStudy": last.prepared.isoformat() if last else None,
        "lastSiteVisitFiscalYear": last.fiscal_year if last else None,
        "nextSiteVisitForFiscalYear": (last.fiscal_year + 3) if last and last.fiscal_year else None,
        "nextReviewForFiscalYear": (latest.fiscal_year + 1) if latest and latest.fiscal_year else None,
    }


def _budget(data_dir: Path, community: Any) -> dict[str, Any]:
    from jason.tasks.finance import balances, latest_year, load

    year = latest_year(Path(data_dir))
    snap = load(Path(data_dir), year) if year else None
    if not snap:
        return {}
    items = {str(i.get("name")): i for i in (snap.get("expense") or {}).get("items", [])}
    ytd = {str(i.get("name")): i for i in (snap.get("expenseYtd") or {}).get("items", [])}
    reserve = [b for b in balances(snap, community.bank_accounts()) if b.purpose == "reserve"]
    named = {b.payhoa_name for b in balances(snap, community.bank_accounts()) if b.payhoa_name}
    line = items.get(TRANSFER_LINE) or {}
    return {
        "year": year,
        "throughMonth": snap.get("throughMonth"),
        "transferBudgetCents": line.get("expected"),
        "transferActualCents": (ytd.get(TRANSFER_LINE) or {}).get("actual"),
        "analystBudgetCents": (items.get(ANALYST_LINE) or {}).get("expected"),
        "reserveAccounts": [{"label": b.label, "suffix": b.suffix, "balanceCents": b.balance_cents} for b in reserve],
        "reserveBalanceCents": sum(b.balance_cents or 0 for b in reserve),
        "unnamedReserveAccounts": unnamed_reserve_accounts(Path(data_dir), snap, named),
        "syncedAt": snap.get("syncedAt"),
    }


def unnamed_reserve_accounts(data_dir: Path, snap: dict[str, Any], named: set[str]) -> list[dict[str, Any]]:
    """PayHOA accounts whose names read as reserve money but that the specification does not name.

    Each with its balance (often none: PayHOA lost the bank link) and its last activity from the transaction
    history, so a certificate of deposit that still earns interest is not left out of the reserve total.
    """
    history: dict[int, list[dict[str, Any]]] = {}
    path = Path(data_dir) / "payhoa" / "transactions.json"
    if path.is_file():
        for tx in json.loads(path.read_text(encoding="utf-8")).get("transactions", []):
            if tx.get("bankAccountId") is not None:
                history.setdefault(int(tx["bankAccountId"]), []).append(tx)
    found = []
    for row in snap.get("bankAccounts") or []:
        name = str(row.get("friendlyName") or "")
        if row.get("deletedAt") or name in named or not RESERVE_NAME.search(name):
            continue
        txs = sorted(history.get(int(row["id"]), []), key=lambda t: t["transactionDate"])
        interest = [t for t in txs if "interest" in str(t.get("description") or "").casefold()]
        found.append({
            "name": name,
            "balanceCents": row.get("plaidBalance") if row.get("plaidBalance") is not None else row.get("fcBalance"),
            "transactions": len(txs),
            "lastActivity": txs[-1]["transactionDate"][:10] if txs else None,
            "lastInterestCents": int(interest[-1]["amount"]) if interest else None,
            "lastInterestDate": interest[-1]["transactionDate"][:10] if interest else None,
        })
    return found


def reserve_brief(data_dir: Path, community: Any, *, year: int | None = None, today: date | None = None) -> dict[str, Any]:
    """The latest study's plan for ``year`` (default next year), beside the budget and the reserve accounts."""
    studies = load_studies(data_dir)
    if not studies:
        return {"found": False, "note": "no reserve study on disk; run jason library --fetch, or save the study under data/reserve-studies"}
    day = today or date.today()
    wanted = year or day.year + 1
    reports = merge_reserve_sources(treasurer_reserves(data_dir), ledger_month_ends(data_dir))
    latest_report = None
    if reports:
        period, report = list(reports.items())[-1]
        latest_report = {"period": period, **report}
    latest = latest_study(studies)
    plan = latest.year(wanted)
    now = latest.year(day.year)
    budget = _budget(data_dir, community)
    units = len(community.units())
    planned = latest.expenditures_in(wanted)
    brief: dict[str, Any] = {
        "found": True,
        "study": history([latest])[0],
        "year": wanted,
        "plan": None if plan is None else {
            "contributionCents": plan.contribution_cents,
            "monthlyCents": round(plan.contribution_cents / 12),
            "perUnitMonthlyCents": round(plan.contribution_cents / 12 / units) if units else None,
            "expendituresCents": plan.expenditures_cents,
            "interestCents": plan.interest_cents,
            "endingBalanceCents": plan.ending_balance_cents,
            "fullyFundedCents": plan.fully_funded_cents,
            "percentFunded": plan.percent_funded,
        },
        "plannedExpenditures": [{"category": e.category, "description": e.description, "costCents": e.cost_cents} for e in planned],
        "thisYear": None if now is None else {
            "year": day.year,
            "contributionCents": now.contribution_cents,
            "expendituresCents": now.expenditures_cents,
            "projectedEndCents": now.ending_balance_cents,
            "plannedExpenditures": [{"description": e.description, "costCents": e.cost_cents} for e in latest.expenditures_in(day.year)],
        },
        "budget": budget,
        "nextFiveYears": [asdict(row) for row in latest.projection if wanted <= row.year < wanted + 5],
        "history": history(studies),
        "treasurerReport": latest_report,
        "checks": checks(studies, units) + report_checks(studies, reports),
        "schedule": site_visit_due(studies),
        "caveats": list(CAVEATS),
    }
    for account in (budget or {}).get("unnamedReserveAccounts", []):
        if account["lastInterestDate"]:
            balance = "no balance in PayHOA" if account["balanceCents"] is None else f"${account['balanceCents'] / 100:,.2f} in PayHOA"
            brief["checks"].append(
                f"PayHOA lists '{account['name']}', which the specification does not name ({balance}); it last earned interest "
                f"of ${account['lastInterestCents'] / 100:,.2f} on {account['lastInterestDate']}. If it still holds reserve money, "
                "the reserve total above and a study's beginning balance leave it out. Its bank statement is the record.")
    if budget and now and budget.get("transferBudgetCents") is not None and budget.get("year") == day.year:
        gap = budget["transferBudgetCents"] - now.contribution_cents
        if abs(gap) > 100:
            brief["checks"].append(f"The {day.year} budget transfers ${budget['transferBudgetCents'] / 100:,.2f} to reserves; "
                                   f"the study's plan for {day.year} is ${now.contribution_cents / 100:,.2f}.")
    return brief


def dollars(cents: int | None) -> str:
    return "-" if cents is None else f"${cents / 100:,.2f}"


def brief_lines(brief: dict[str, Any]) -> list[str]:
    if not brief.get("found"):
        return [brief.get("note", "no reserve study")]
    s = brief["study"]
    out = [f"Latest study: FY{s['fiscalYear']} {s['level']} by {s['preparer']}, {s['prepared']} ({s['source']})"]
    plan = brief["plan"]
    if plan:
        out.append(f"{brief['year']} plan: contribute {dollars(plan['contributionCents'])} ({dollars(plan['monthlyCents'])} a month, "
                   f"{dollars(plan['perUnitMonthlyCents'])} per unit a month); spend {dollars(plan['expendituresCents'])}; "
                   f"end at {dollars(plan['endingBalanceCents'])}, {plan['percentFunded']:.0%} funded")
    for item in brief["plannedExpenditures"]:
        out.append(f"  planned {brief['year']}: {item['description']} {dollars(item['costCents'])}")
    now = brief.get("thisYear")
    budget = brief.get("budget") or {}
    if now:
        out.append(f"{now['year']}: the study planned {dollars(now['contributionCents'])} in and {dollars(now['expendituresCents'])} out, "
                   f"ending at {dollars(now['projectedEndCents'])}")
    if budget:
        out.append(f"Budget {budget['year']}: '{TRANSFER_LINE}' {dollars(budget.get('transferBudgetCents'))} budgeted, "
                   f"{dollars(budget.get('transferActualCents'))} through month {budget.get('throughMonth')}; "
                   f"reserve accounts now {dollars(budget.get('reserveBalanceCents'))} "
                   + "(" + ", ".join(f"{a['label']} {dollars(a['balanceCents'])}" for a in budget.get("reserveAccounts", [])) + ")")
    report = brief.get("treasurerReport")
    if report:
        source = {"ledger": "PayHOA balance sheet", "ledger + report": "PayHOA balance sheet and treasurer's report"}.get(
            report.get("source"), "Treasurer's report")
        out.append(f"{source} {report['period']}: reserve accounts {dollars(report['totalCents'])} ("
                   + ", ".join(f"{name} {dollars(cents)}" for name, cents in report["accounts"].items()) + ")")
    sched = brief["schedule"]
    out.append(f"Last study with a site visit: FY{sched['lastSiteVisitFiscalYear']} ({sched['lastSiteVisitStudy']}); "
               f"next site visit due for FY{sched['nextSiteVisitForFiscalYear']}; next review for FY{sched['nextReviewForFiscalYear']}")
    out.append("")
    out.append("Studies")
    for h in brief["history"]:
        pct = f"{h['percentFunded']:.0%}" if h["percentFunded"] is not None else "-"
        out.append(f"  FY{h['fiscalYear']} {h['preparer']:<28} {h['level'] or '-':<26} begin {dollars(h['beginningBalanceCents']):>12} "
                   f"contribute {dollars(h['annualContributionCents']):>12}  {pct:>4} funded  units {h['units'] or '-'}")
    if brief["checks"]:
        out.append("")
        out.extend(f"! {c}" for c in brief["checks"])
    out.append("")
    out.extend(f"* {c}" for c in brief["caveats"])
    return out


__all__ = ["treasurer_reserves", "ledger_month_ends", "merge_reserve_sources", "report_checks", "study_files", "load_studies", "history", "checks", "site_visit_due", "reserve_brief", "brief_lines", "latest_study", "latest_study_ref"]
