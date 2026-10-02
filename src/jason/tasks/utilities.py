"""Utility bills: parse the SMUD and City PDFs into the store, map accounts to meters and parcels,
flag abnormal usage, and forecast a year's cost against the budget.

The smud and i-doxs packages download the bills; this task reads the PDFs
they left under each account's folder (``Settings.smud_bills_dir`` and
``Settings.idoxs_bills_dir``) and writes ``data/utilities.db``. Everything
after the sync reads that store, so ``jason-mcp`` can answer without a portal.

The map from account to meter, size, service address, and parcel is what
the bills say. The specification adds only each account's purpose
(``Mystique.utility_accounts``) and the budget line each service is
budgeted under (``Mystique.utility_budget_lines``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from jason.community.city_utility import SacramentoUtilities
from jason.community.smud_utility import CITS_0, Smud
from jason.community.symbols import Utility
from jason.community.utility import Service, UtilityBill, UtilityProvider, dedupe_bills, service_points
from jason.community.city_utility import WATER_2019
from jason.community.utility_analysis import anomalies, usage_series
from jason.community.utility_forecast import backtest, forecast_electric, forecast_water, summarize
from jason.community.utility_store import UtilityStore

STORE_NAME = "utilities.db"
PROVIDERS: dict[Utility, UtilityProvider] = {Utility.SMUD: Smud(), Utility.CITY_OF_SACRAMENTO: SacramentoUtilities()}
PROPOSED_CITY_INCREASE_FROM = date(2027, 7, 1)

CAVEATS = (
    "SMUD's 2026 and 2027 CITS-0 prices are adopted (Resolution 25-06-15); its 2028 prices are provisional.",
    "The City's water prices are its July 1, 2019 schedule; the increases proposed from July 2027 are not adopted, "
    "so a water increase applies only when a scenario names one.",
    "Storm drainage and street sweeping grow at the yearly rate their own bills show.",
    "Usage is each calendar month's median usage per day over its last three covered years, priced at the rates in "
    "force on those days; it is not a sum of past bills or payments, so a late payment or a catch-up read does not move it.",
    "The backtest predicts this year's finished months from the bills before this year; its error is the forecast's yardstick.",
    "An anomaly is a reason to look at the meter, not a finding of a leak or a short.",
)


def store_path(data_dir: Path) -> Path:
    return Path(data_dir) / STORE_NAME


def bill_roots(settings: Any) -> dict[Utility, Path]:
    return {Utility.SMUD: Path(settings.smud_bills_dir), Utility.CITY_OF_SACRAMENTO: Path(settings.idoxs_bills_dir)}


def bill_files(roots: dict[Utility, Path]) -> list[tuple[Utility, str, Path]]:
    """Each bill PDF under an account folder. A file whose name does not start with its date (a test download) is skipped."""
    found: list[tuple[Utility, str, Path]] = []
    for utility, root in roots.items():
        if not root.is_dir():
            continue
        for folder in sorted(root.iterdir()):
            if not folder.is_dir() or not folder.name.isdigit():
                continue
            for pdf in sorted(folder.glob("*.pdf")):
                if pdf.name[:4].isdigit():
                    found.append((utility, folder.name, pdf))
    return found


def pdf_text(path: Path) -> str:
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError('PyMuPDF is not installed; pip install -e ".[pdf]"') from exc
    # A damaged colour profile is not a reason to print to the console; the text still reads.
    pymupdf.TOOLS.mupdf_display_errors(False)
    with pymupdf.open(str(path)) as doc:
        return "\n".join(page.get_text() for page in doc)


@dataclass
class SyncResult:
    parsed: int = 0
    unchanged: int = 0
    removed: int = 0
    unreadable: list[str] = field(default_factory=list)
    unreconciled: list[str] = field(default_factory=list)


def sync(roots: dict[Utility, Path], path: Path, *, full: bool = False, log: Callable[[str], None] | None = None) -> SyncResult:
    """Parse every new or changed bill PDF into the store; drop files that are gone from disk."""
    result = SyncResult()
    files = bill_files(roots)
    with UtilityStore(path) as store:
        known = store.known()
        live: set[str] = set()
        for utility, account, pdf in files:
            source = str(pdf.resolve())
            live.add(source)
            stat = pdf.stat()
            if not full and known.get(source) == (stat.st_size, stat.st_mtime):
                result.unchanged += 1
                continue
            try:
                text = pdf_text(pdf)
            except RuntimeError:
                raise
            except Exception as exc:  # a damaged download is reported, not fatal
                result.unreadable.append(f"{source}: {exc}")
                continue
            bill = PROVIDERS[utility].parse(text, account=account, bill_id=pdf.stem, source=source)
            store.save(bill, size=stat.st_size, mtime=stat.st_mtime)
            result.parsed += 1
            if not bill.reconciles:
                result.unreconciled.append(source)
            if log and result.parsed % 100 == 0:
                log(f"parsed {result.parsed} bills")
        gone = [s for s in known if s not in live and not Path(s).exists()]
        store.forget(gone)
        result.removed = len(gone)
    return result


def load_bills(path: Path, *, dedupe: bool = True) -> list[UtilityBill]:
    """Every stored bill, one per account and period (``dedupe=False`` keeps every file)."""
    with UtilityStore(path, readonly=True) as store:
        bills = store.bills()
    return dedupe_bills(bills) if dedupe else bills


def misfiled(bills: list[UtilityBill], *, tolerance_days: int = 5) -> list[dict[str, Any]]:
    """Files whose name dates a different bill than the one inside: the downloader saved an older bill under a newer name.

    The bill's own date is the record; the bill the name promises is missing until it is downloaded again.
    """
    rows = []
    for bill in bills:
        name = Path(bill.source).name
        try:
            named = date.fromisoformat(name[:10])
        except ValueError:
            continue
        if bill.bill_date and abs((bill.bill_date - named).days) > tolerance_days:
            rows.append({"provider": bill.provider.value, "account": bill.account, "file": name,
                         "namedDate": named.isoformat(), "billDate": bill.bill_date.isoformat()})
    rows.sort(key=lambda r: (r["provider"], r["namedDate"], r["account"]))
    return rows


def _labels(community: Any) -> dict[tuple[Utility, str], Any]:
    return {(a.utility, a.account): a for a in community.utility_accounts()}


def _day(value: date | None) -> str | None:
    return value.isoformat() if value else None


def service_map(bills: list[UtilityBill], community: Any) -> list[dict[str, Any]]:
    """Each account: its purpose from the specification, and its services, meters, sizes, address, and parcel from the bills."""
    labels = _labels(community)
    newest: dict[Utility, date] = {}
    for bill in bills:
        day = bill.period_end or bill.bill_date
        if day and day > newest.get(bill.provider, date.min):
            newest[bill.provider] = day
    grouped: dict[tuple[Utility, str], list] = {}
    for point in service_points(bills):
        grouped.setdefault((point.provider, point.account), []).append(point)
    last_bill: dict[tuple[Utility, str], UtilityBill] = {}
    for bill in sorted(bills, key=lambda b: b.period_end or date.min):
        last_bill[(bill.provider, bill.account)] = bill
    rows: list[dict[str, Any]] = []
    for key in sorted(set(grouped) | set(labels), key=lambda k: (k[0].value, k[1])):
        provider, account = key
        spec = labels.get(key)
        points = grouped.get(key, [])
        latest = last_bill.get(key)
        notes: list[str] = []
        if spec is None:
            notes.append("not in the specification: name its purpose in mystique/utilities.py")
        if not points:
            notes.append("in the specification, but no bills on disk")
        by_service: dict[Service, list] = {}
        for point in points:
            by_service.setdefault(point.service, []).append(point)
        for service, items in by_service.items():
            metered = sorted((p for p in items if p.meter), key=lambda p: p.first_bill or date.min)
            for before, after in zip(metered, metered[1:]):
                notes.append(f"{service.value} meter {before.meter} (last billed {_day(before.last_bill)}) "
                             f"replaced by {after.meter} (first billed {_day(after.first_bill)})")
        last_day = (latest.period_end or latest.bill_date) if latest else None
        active = bool(last_day and provider in newest and last_day >= newest[provider] - timedelta(days=75))
        if points and not active:
            notes.append(f"no bill in the 75 days before {provider.value}'s newest: closed, or its newest bills are misfiled or not downloaded")
        rows.append({
            "provider": provider.value,
            "account": account,
            "label": spec.label if spec else "",
            "building": int(spec.building) if spec and spec.building is not None else None,
            "serviceAddress": latest.service_address if latest else "",
            "parcel": latest.parcel if latest else "",
            "rateSchedule": latest.rate_schedule if latest else "",
            "active": active,
            "lastBill": _day(last_day),
            "services": [
                {"service": p.service.value, "meter": p.meter, "size": p.size, "firstBill": _day(p.first_bill),
                 "lastBill": _day(p.last_bill), "bills": p.bills}
                for p in sorted(points, key=lambda p: (p.service.value, p.first_bill or date.min))
            ],
            "notes": notes,
        })
    return rows


def anomaly_rows(bills: list[UtilityBill], community: Any, *, since: date | None = None) -> list[dict[str, Any]]:
    labels = _labels(community)
    rows = []
    for item in anomalies(usage_series(bills), since=since):
        spec = labels.get((item.point.provider, item.point.account))
        rows.append({**item.as_dict(), "label": spec.label if spec else ""})
    return rows


def usage_history(bills: list[UtilityBill], account: str, service: Service | None = None) -> list[dict[str, Any]]:
    """One account's metered usage bill by bill: period, usage, per day, and the service's cost."""
    rows = []
    for (provider, acct, svc), points in usage_series(bills).items():
        if acct != account or (service and svc is not service):
            continue
        for p in points:
            rows.append({"provider": provider.value, "service": svc.value, "billId": p.bill_id, "start": p.start.isoformat(),
                         "end": p.end.isoformat(), "days": p.days, "usage": p.usage, "unit": p.unit.value,
                         "perDay": round(p.per_day, 2), "costCents": p.cost_cents})
    rows.sort(key=lambda r: (r["service"], r["end"]))
    return rows


def _budget_lines(data_dir: Path, community: Any) -> dict[str, Any]:
    """The latest finance snapshot's budget and actual for each utility line, by service."""
    from jason.tasks.finance import latest_year, load

    year = latest_year(Path(data_dir))
    snap = load(Path(data_dir), year) if year else None
    if not snap:
        return {}
    items = {str(i.get("name")): i for i in (snap.get("expense") or {}).get("items", [])}
    found: dict[str, Any] = {"year": year, "throughMonth": snap.get("throughMonth"), "lines": {}}
    for service, name in community.utility_budget_lines().items():
        item = items.get(name)
        if item:
            found["lines"][service.value] = {"line": name, "budgetCents": item.get("expected"), "actualCents": item.get("actual")}
    return found


def forecast(bills: list[UtilityBill], year: int, *, water_increase: float = 0.0,
             increase_from: date = PROPOSED_CITY_INCREASE_FROM) -> dict[str, Any]:
    """A year's utility cost by calendar month: predicted usage at the rates in force, plus the monthly fixed charges."""
    electric = forecast_electric(bills, year, CITS_0)
    water = forecast_water(bills, year, water_price=WATER_2019, water_increase=water_increase, increase_from=increase_from)
    lines = electric + water
    by_account: dict[str, int] = {}
    for line in lines:
        key = f"{line.provider.value}:{line.account}"
        by_account[key] = by_account.get(key, 0) + line.cents
    total = summarize(lines)
    return {
        "year": year,
        "method": "predicted usage by calendar month at the rates in force",
        "waterIncrease": water_increase,
        "waterIncreaseFrom": increase_from.isoformat() if water_increase else None,
        "totalCents": total["totalCents"],
        "byService": total["byService"],
        "byMonth": total["byMonth"],
        "usage": total["usage"],
        "provisional": total["provisional"],
        "byAccount": dict(sorted(by_account.items())),
        "smud": summarize(electric),
        "city": summarize(water),
    }


def check(bills: list[UtilityBill], today: date) -> dict[str, Any]:
    """The backtest over this year's finished months (two months back, so every bill for them is in)."""
    through = today.month - 2
    if through < 1:
        return {}
    return {"year": today.year, "throughMonth": through,
            "byService": backtest(bills, today.year, through, electric=CITS_0, water=WATER_2019)}


def utilities_brief(data_dir: Path, community: Any, *, year: int | None = None, water_increase: float = 0.0,
                    since: date | None = None, today: date | None = None) -> dict[str, Any]:
    """The whole utility picture from the store: accounts and meters, recent anomalies, the year's forecast against the budget."""
    path = store_path(data_dir)
    if not path.is_file():
        return {"found": False, "note": "no utility store; run jason utilities --sync"}
    files = load_bills(path, dedupe=False)
    bills = dedupe_bills(files)
    day = today or date.today()
    wanted = year or day.year + 1
    recent = since or day - timedelta(days=400)
    outlook = forecast(bills, wanted, water_increase=water_increase)
    outlook["backtest"] = check(bills, day)
    budget = _budget_lines(data_dir, community)
    comparison = []
    for service, cents in outlook["byService"].items():
        line = (budget.get("lines") or {}).get(service)
        comparison.append({"service": service, "forecastCents": cents, "budgetLine": line["line"] if line else None,
                           "budgetCents": line["budgetCents"] if line else None, "actualCents": line["actualCents"] if line else None})
    newest = {}
    for bill in bills:
        key = bill.provider.value
        if bill.period_end and bill.period_end.isoformat() > newest.get(key, ""):
            newest[key] = bill.period_end.isoformat()
    return {
        "found": True,
        "bills": len(bills),
        "unreconciled": [b.source for b in bills if not b.reconciles],
        "misfiled": misfiled(files),
        "newestPeriod": newest,
        "accounts": service_map(bills, community),
        "anomaliesSince": recent.isoformat(),
        "anomalies": anomaly_rows(bills, community, since=recent),
        "forecast": outlook,
        "budget": {"year": budget.get("year"), "throughMonth": budget.get("throughMonth"), "byService": comparison},
        "caveats": list(CAVEATS),
    }


def dollars(cents: int | None) -> str:
    if cents is None:
        return "-"
    return f"${cents / 100:,.2f}"


def brief_lines(brief: dict[str, Any]) -> list[str]:
    """The brief as terminal lines."""
    if not brief.get("found"):
        return [brief.get("note", "no utility store")]
    out = [f"{brief['bills']} bills; newest periods {brief['newestPeriod']}; {len(brief['unreconciled'])} do not add up"]
    if brief["misfiled"]:
        out.append(f"{len(brief['misfiled'])} files hold an older bill than their name says (download again):")
        out.extend(f"  {m['account']} {m['file']} holds the {m['billDate']} bill" for m in brief["misfiled"])
    out.append("")
    out.append("Accounts")
    for row in brief["accounts"]:
        meters = ", ".join(sorted({f"{s['service']} {s['meter']} {s['size']}".strip() for s in row["services"] if s["meter"]}))
        state = "" if row["active"] else f" (last bill {row['lastBill']})"
        out.append(f"  {row['provider']:<9} {row['account']:<11} {row['label'] or '(unlabeled)'}{state}")
        out.append(f"            {row['serviceAddress']} {row['parcel']}  {meters}".rstrip())
        for note in row["notes"]:
            out.append(f"            note: {note}")
    out.append("")
    out.append(f"Anomalies since {brief['anomaliesSince']}")
    for a in brief["anomalies"]:
        out.append(f"  {a['end']} {a['label'] or a['account']}: {a['service']} {a['perDay']}/day vs {a['baselinePerDay']} ({a['basis']}); {a['kind']}")
    f = brief["forecast"]
    out.append("")
    scenario = f", City water +{f['waterIncrease']:.0%} from {f['waterIncreaseFrom']}" if f["waterIncrease"] else ""
    out.append(f"Forecast {f['year']}{scenario}: {dollars(f['totalCents'])} ({f['method']})")
    budget = brief["budget"]
    for row in budget["byService"]:
        against = f"; {budget['year']} budget {dollars(row['budgetCents'])} ({row['budgetLine']})" if row["budgetLine"] else "; no budget line"
        out.append(f"  {row['service']:<17} {dollars(row['forecastCents']):>12}{against}")
    for name, amount in f.get("usage", {}).items():
        out.append(f"  predicted {name}: {amount:,.0f}")
    test = f.get("backtest") or {}
    if test:
        out.append(f"Backtest: {test['year']} January through month {test['throughMonth']}, predicted from earlier bills")
        for service, row in test["byService"].items():
            err = f"{row['error']:+.1%}" if row["error"] is not None else "-"
            out.append(f"  {service:<17} predicted {dollars(row['predictedCents']):>12}  actual {dollars(row['actualCents']):>12}  {err}")
    out.append("")
    out.extend(f"* {c}" for c in brief["caveats"])
    return out


__all__ = ["sync", "load_bills", "misfiled", "service_map", "anomaly_rows", "usage_history", "forecast", "utilities_brief", "brief_lines", "store_path", "bill_roots"]
