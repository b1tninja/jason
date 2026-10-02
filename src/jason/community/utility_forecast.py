"""A year's utility cost from predicted usage and the rates in force, month by calendar month.

The forecast does not add up past bills or payments. A payment's month says when the
treasurer paid, not when the water ran, and a bill's period straddles months, so a sum of
last year's bills carries last year's timing into next year: a late payment, a catch-up
read, a credit that zeroed a month. Instead:

1. Each metered service's usage is spread over the days its bills cover. A read after bills
   with no usage is spread over the whole unread stretch.
2. Each calendar month's usage per day is the median of that month in the last three years
   with enough coverage. Irrigation in July is judged against July, not against the year.
3. The month's usage is priced at the tariff on its days: SMUD's CITS-0 energy by time of
   day (each month's own mix), demand at the month's typical maximum kW, the fixed charge,
   tax, and surcharge; the City's water at its per-cubic-foot price.
4. Charges that do not depend on usage (the City's base, fire service, storm drainage, and
   street sweeping) are monthly rates: the latest bill's amount, grown at the rate its own
   history shows (storm and sweeping) or by the named water scenario (water and fire).
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

from jason.community.symbols import Utility
from jason.community.utility import ChargeKind, Service, Tariff, UsageUnit, UtilityBill
from jason.community.utility_analysis import UsagePoint, fixed_growth, usage_series

MIN_COVERAGE = 0.8
PRORATED = re.compile(r"\s*\(for \d+ days?\)", re.I)
WATER_SERVICES = (Service.WATER_DOMESTIC, Service.WATER_IRRIGATION, Service.FIRE_SERVICE)


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def spread(points: list[UsagePoint]) -> list[tuple[date, date, float]]:
    """(start, end, usage per day) spans. A zero-usage run and the read that follows are one span."""
    spans: list[tuple[date, date, float]] = []
    pending: list[UsagePoint] = []
    for point in sorted(points, key=lambda p: p.start):
        if point.usage == 0:
            pending.append(point)
            continue
        start = pending[0].start if pending else point.start
        days = (point.end - start).days + 1
        spans.append((start, point.end, point.usage / days if days else 0.0))
        pending = []
    # A trailing run with no read yet stays unknown rather than counting as zero use.
    return spans


def monthly_per_day(points: list[UsagePoint]) -> dict[tuple[int, int], float]:
    """Usage per day in each (year, month) the spans cover for at least ``MIN_COVERAGE`` of its days."""
    totals: dict[tuple[int, int], list[float]] = {}
    for start, end, per_day in spread(points):
        day = start
        while day <= end:
            key = (day.year, day.month)
            last = min(end, month_bounds(*key)[1])
            covered = (last - day).days + 1
            entry = totals.setdefault(key, [0.0, 0.0])
            entry[0] += per_day * covered
            entry[1] += covered
            day = last + timedelta(days=1)
    found: dict[tuple[int, int], float] = {}
    for (year, month), (usage, days) in totals.items():
        if days >= MIN_COVERAGE * calendar.monthrange(year, month)[1]:
            found[(year, month)] = usage / days
    return found


@dataclass(frozen=True)
class MonthProfile:
    """A calendar month's predicted usage per day and the years it rests on."""

    month: int
    per_day: float
    years: tuple[int, ...]


def usage_profile(points: list[UsagePoint], *, years: int = 3, before: int | None = None) -> dict[int, MonthProfile]:
    """Each calendar month's median usage per day over its last ``years`` covered years (before year ``before``).

    A month no year covers takes the median of the months that are covered.
    """
    by_month: dict[int, list[tuple[int, float]]] = {}
    for (year, month), per_day in monthly_per_day(points).items():
        if before is None or year < before:
            by_month.setdefault(month, []).append((year, per_day))
    profile: dict[int, MonthProfile] = {}
    for month, items in by_month.items():
        items.sort()
        recent = items[-years:]
        profile[month] = MonthProfile(month, median(v for _y, v in recent), tuple(y for y, _v in recent))
    if profile:
        fallback = median(p.per_day for p in profile.values())
        for month in range(1, 13):
            profile.setdefault(month, MonthProfile(month, fallback, ()))
    return profile


@dataclass(frozen=True)
class MonthLine:
    provider: Utility
    account: str
    service: Service
    month: str
    usage: float
    unit: UsageUnit | None
    usage_cents: int
    fixed_cents: int
    provisional: bool = False
    basis: str = ""

    @property
    def cents(self) -> int:
        return self.usage_cents + self.fixed_cents


def _midpoint_month(bill: UtilityBill) -> int | None:
    if not bill.period_start or not bill.period_end:
        return None
    return (bill.period_start + (bill.period_end - bill.period_start) / 2).month


def tou_shares(bills: list[UtilityBill], *, years: int = 3, before: int | None = None) -> dict[int, dict[str, float]]:
    """Each calendar month's share of kWh by time-of-day key, within that month's season, from the bills centred on it."""
    from jason.community.smud_utility import SUMMER_MONTHS, tou_usage

    samples: dict[int, list[tuple[int, dict[str, float]]]] = {}
    for bill in bills:
        month = _midpoint_month(bill)
        if month is None or (before is not None and bill.period_end.year >= before):
            continue
        season = "summer" if month in SUMMER_MONTHS else "nonsummer"
        usage = {k: v for k, v in tou_usage(bill).items() if k.startswith(season)}
        total = sum(usage.values())
        if total > 0:
            samples.setdefault(month, []).append((bill.period_end.year, {k: v / total for k, v in usage.items()}))
    shares: dict[int, dict[str, float]] = {}
    for month, items in samples.items():
        items.sort(key=lambda item: item[0])
        recent = [s for _y, s in items[-years:]]
        keys = {k for s in recent for k in s}
        raw = {k: sum(s.get(k, 0.0) for s in recent) / len(recent) for k in keys}
        total = sum(raw.values()) or 1.0
        shares[month] = {k: v / total for k, v in raw.items()}
    return shares


def kw_profile(bills: list[UtilityBill], *, years: int = 3, before: int | None = None) -> dict[int, float]:
    """Each calendar month's typical maximum kW: the median of the recent bills centred on it."""
    from jason.community.smud_utility import max_kw

    samples: dict[int, list[tuple[int, float]]] = {}
    for bill in bills:
        month = _midpoint_month(bill)
        if month is None or (before is not None and bill.period_end.year >= before):
            continue
        samples.setdefault(month, []).append((bill.period_end.year, max_kw(bill)))
    return {m: median(v for _y, v in sorted(items)[-years:]) for m, items in samples.items()}


def _default_shares(month: int) -> dict[str, float]:
    from jason.community.smud_utility import SUMMER_MONTHS

    if month in SUMMER_MONTHS:
        return {"summer_off_peak": 0.8, "summer_peak": 0.2}
    return {"nonsummer_off_peak": 0.55, "nonsummer_off_peak_saver": 0.3, "nonsummer_peak": 0.15}


def forecast_electric(bills: list[UtilityBill], year: int, tariff: Tariff, *, years: int = 3, before: int | None = None) -> list[MonthLine]:
    """Each SMUD account's twelve calendar months: predicted kWh at its time-of-day mix, priced at ``tariff``."""
    from jason.community.smud_utility import estimate

    lines: list[MonthLine] = []
    smud = [b for b in bills if b.provider is Utility.SMUD and (before is None or (b.period_end and b.period_end.year < before))]
    active = active_accounts(smud)
    series = usage_series(smud)
    for (provider, account, service), points in series.items():
        if service is not Service.ELECTRIC or account not in active:
            continue
        own = [b for b in bills if b.provider is provider and b.account == account]
        profile = usage_profile(points, years=years, before=before)
        if not profile:
            continue
        shares = tou_shares(own, years=years, before=before)
        kw = kw_profile(own, years=years, before=before)
        for month in range(1, 13):
            start, end = month_bounds(year, month)
            days = (end - start).days + 1
            kwh = profile[month].per_day * days
            mix = shares.get(month) or _default_shares(month)
            est = estimate(tariff, start, end, {k: kwh * share for k, share in mix.items()}, kw.get(month, 0.0))
            lines.append(MonthLine(
                provider, account, service, f"{year}-{month:02d}", round(kwh, 1), UsageUnit.KWH,
                est.energy_cents + est.demand_cents + est.tax_cents + est.surcharge_cents, est.fixed_cents,
                est.provisional, "usage per day from " + (", ".join(str(y) for y in profile[month].years) or "the other months"),
            ))
    return lines


CLOSED_AFTER_DAYS = 75


def active_accounts(bills: list[UtilityBill]) -> set[str]:
    """Accounts billed within ``CLOSED_AFTER_DAYS`` of the provider's newest bill; an older account is closed."""
    newest = max((b.period_end for b in bills if b.period_end), default=None)
    if newest is None:
        return set()
    return {b.account for b in bills if b.period_end and (newest - b.period_end).days <= CLOSED_AFTER_DAYS}


def monthly_fixed(bills: list[UtilityBill]) -> dict[tuple[str, Service, str, int], tuple[int, date]]:
    """Each active account's monthly fixed charges as its latest bill states them.

    Keyed by (account, service, label, n): a bill can carry the same line twice (two 8-inch fire taps).
    Prorated pieces of one line are summed back into the month's charge.
    """
    active = active_accounts(bills)
    latest: dict[str, UtilityBill] = {}
    for bill in bills:
        if bill.account in active and bill.period_end and bill.period_end > (latest[bill.account].period_end if bill.account in latest else date.min):
            if any(c.kind is ChargeKind.FIXED for c in bill.charges):
                latest[bill.account] = bill
    found: dict[tuple[str, Service, str, int], tuple[int, date]] = {}
    for account, bill in latest.items():
        seen: dict[tuple[Service, str], int] = {}
        # A rate step inside the period splits a flat monthly line into prorated pieces
        # ("(for 28 days)", "(for 1 days)"); together they are that bill's monthly charge.
        pieces: dict[tuple[Service, str], int] = {}
        for charge in bill.charges:
            if charge.kind is not ChargeKind.FIXED:
                continue
            base = PRORATED.sub("", charge.label).strip()
            if base != charge.label:
                pieces[(charge.service, base)] = pieces.get((charge.service, base), 0) + charge.amount_cents
                continue
            n = seen.get((charge.service, charge.label), 0)
            seen[(charge.service, charge.label)] = n + 1
            found[(account, charge.service, charge.label, n)] = (charge.amount_cents, bill.period_end)
        for (service, base), cents in pieces.items():
            n = seen.get((service, base), 0)
            seen[(service, base)] = n + 1
            found[(account, service, base, n)] = (cents, bill.period_end)
    return found


def forecast_water(bills: list[UtilityBill], year: int, *, water_price: Tariff, water_increase: float = 0.0,
                   increase_from: date = date(2027, 7, 1), years: int = 3, before: int | None = None) -> list[MonthLine]:
    """Each City account's twelve calendar months: predicted cubic feet at the water price, plus each monthly fixed charge.

    ``water_increase`` raises water usage and water and fire fixed charges from ``increase_from`` (a scenario,
    not an adopted rate). Storm drainage and street sweeping grow at the rate their own bills show.
    """
    city = [b for b in bills if b.provider is Utility.CITY_OF_SACRAMENTO]
    if before is not None:
        city = [b for b in city if b.period_end and b.period_end.year < before]
    growth = fixed_growth(city)
    fixed = monthly_fixed(city)
    active = active_accounts(city)
    profiles: dict[tuple[str, Service], dict[int, MonthProfile]] = {}
    for (_provider, account, service), points in usage_series(city).items():
        if account in active:
            profiles[(account, service)] = usage_profile(points, years=years)
    lines: list[MonthLine] = []
    accounts = sorted({key[0] for key in fixed} | {a for a, _s in profiles})
    for account in accounts:
        for month in range(1, 13):
            start, _end = month_bounds(year, month)
            days = calendar.monthrange(year, month)[1]
            raised = 1 + water_increase if water_increase and start >= increase_from else 1.0
            per_service: dict[Service, list[float]] = {}
            for (acct, service), profile in profiles.items():
                if acct != account or not profile:
                    continue
                usage = profile[month].per_day * days
                price = water_price.price("water_per_cubic_foot", start) * raised
                entry = per_service.setdefault(service, [0.0, 0.0, 0.0])
                entry[0] += usage
                entry[1] += usage * price * 100
            for (acct, service, label, _n), (cents, as_of) in fixed.items():
                if acct != account:
                    continue
                if service in WATER_SERVICES:
                    amount = cents * raised
                else:
                    years_on = max(0.0, (start - as_of).days / 365.25)
                    amount = cents * (1 + growth.get((account, label), 0.0)) ** years_on
                per_service.setdefault(service, [0.0, 0.0, 0.0])[2] += amount
            for service, (usage, usage_cents, fixed_cents) in per_service.items():
                metered = service in (Service.WATER_DOMESTIC, Service.WATER_IRRIGATION)
                lines.append(MonthLine(
                    Utility.CITY_OF_SACRAMENTO, account, service, f"{year}-{month:02d}", round(usage, 1),
                    UsageUnit.CUBIC_FEET if metered else None, round(usage_cents), round(fixed_cents),
                    False, "usage per day by month, water price in force" if metered else "the latest monthly charge",
                ))
    return lines


def actual_by_month(bills: list[UtilityBill], year: int) -> dict[tuple[str, Service], dict[str, int]]:
    """What the bills charged for each calendar month of ``year``, each charge prorated over its own period's days.

    The yardstick for a backtest: the cost of the service in the month it was used, not the month it was paid.
    """
    found: dict[tuple[str, Service], dict[str, int]] = {}
    for bill in bills:
        for charge in bill.charges:
            start = charge.period_start or bill.period_start
            end = charge.period_end or bill.period_end
            if not start or not end:
                continue
            days = (end - start).days + 1
            day = start
            while day <= end:
                last = min(end, month_bounds(day.year, day.month)[1])
                if day.year == year:
                    share = charge.amount_cents * ((last - day).days + 1) / days
                    key = (bill.provider.value, charge.service)
                    month = f"{day.year}-{day.month:02d}"
                    found.setdefault(key, {})[month] = found.get(key, {}).get(month, 0) + round(share)
                day = last + timedelta(days=1)
    return found


def backtest(bills: list[UtilityBill], year: int, through_month: int, *, electric: Tariff, water: Tariff) -> dict[str, dict]:
    """Predict January through ``through_month`` of ``year`` from the bills before it, against what those months cost.

    Each service: predicted and actual cents, and the error as a fraction of actual.
    """
    months = {f"{year}-{m:02d}" for m in range(1, through_month + 1)}
    predicted: dict[str, int] = {}
    for line in forecast_electric(bills, year, electric, before=year) + forecast_water(bills, year, water_price=water, before=year):
        if line.month in months:
            predicted[line.service.value] = predicted.get(line.service.value, 0) + line.cents
    actual: dict[str, int] = {}
    for (_provider, service), by_month in actual_by_month(bills, year).items():
        actual[service.value] = actual.get(service.value, 0) + sum(v for m, v in by_month.items() if m in months)
    return {
        service: {"predictedCents": predicted.get(service, 0), "actualCents": actual.get(service, 0),
                  "error": round((predicted.get(service, 0) - actual[service]) / actual[service], 3) if actual.get(service) else None}
        for service in sorted(set(predicted) | set(actual))
    }


def summarize(lines: list[MonthLine]) -> dict:
    """Totals by service and by month, integer cents, with usage by service."""
    by_service: dict[str, int] = {}
    by_month: dict[str, int] = {}
    usage: dict[str, float] = {}
    for line in lines:
        by_service[line.service.value] = by_service.get(line.service.value, 0) + line.cents
        by_month[line.month] = by_month.get(line.month, 0) + line.cents
        if line.unit is not None:
            key = f"{line.service.value} ({line.unit.value})"
            usage[key] = round(usage.get(key, 0.0) + line.usage, 1)
    return {"totalCents": sum(by_service.values()), "byService": dict(sorted(by_service.items())),
            "byMonth": dict(sorted(by_month.items())), "usage": dict(sorted(usage.items())),
            "provisional": any(line.provisional for line in lines)}


__all__ = [
    "spread", "monthly_per_day", "usage_profile", "MonthProfile", "MonthLine", "tou_shares", "kw_profile",
    "forecast_electric", "forecast_water", "monthly_fixed", "active_accounts", "actual_by_month", "backtest", "summarize", "month_bounds",
]
