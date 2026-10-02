"""Reading utility bills over time: usage per day, abnormal usage, and next year's cost.

Usage is compared per day, because billing periods run 26 to 36 days. A
bill is abnormal when its usage per day stands well above the same months
in earlier years (the season decides irrigation and air conditioning), or,
without an earlier year, above its own recent run. High usage on a water
service can be a leak; on an electric meter, a short, a stuck pump, or a
light left on. No usage at all on a service that always has some is flagged
too: a stopped meter or a closed valve.

Next year's cost is ``jason.community.utility_forecast``: predicted usage by
calendar month, priced at the rates in force, not a sum of past bills.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Iterable

from jason.community.symbols import Utility
from jason.community.utility import ChargeKind, Service, UsageUnit, UtilityBill

UNIT_OF = {Service.ELECTRIC: UsageUnit.KWH, Service.WATER_DOMESTIC: UsageUnit.CUBIC_FEET, Service.WATER_IRRIGATION: UsageUnit.CUBIC_FEET}
# Flag a bill whose usage per day is this many times its baseline, and at least this much more per day.
RATIO = {Service.ELECTRIC: 1.4, Service.WATER_DOMESTIC: 1.35, Service.WATER_IRRIGATION: 1.5}
MIN_EXCESS_PER_DAY = {Service.ELECTRIC: 3.0, Service.WATER_DOMESTIC: 150.0, Service.WATER_IRRIGATION: 300.0}


@dataclass(frozen=True)
class UsagePoint:
    provider: Utility
    account: str
    service: Service
    bill_id: str
    start: date
    end: date
    usage: float
    unit: UsageUnit
    cost_cents: int

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def per_day(self) -> float:
        return self.usage / self.days if self.days else 0.0


def usage_series(bills: Iterable[UtilityBill]) -> dict[tuple[Utility, str, Service], list[UsagePoint]]:
    """Each metered service's usage per bill, oldest first, with the service's own period and cost."""
    found: dict[tuple[Utility, str, Service], list[UsagePoint]] = {}
    for bill in bills:
        for service, unit in UNIT_OF.items():
            charges = [c for c in bill.charges if c.service is service]
            if not charges:
                continue
            usage = bill.usage(service, unit)
            start, end = bill.service_period(service)
            if start is None or end is None:
                continue
            cost = sum(c.amount_cents for c in charges)
            if service is Service.ELECTRIC:
                cost = bill.total_cents
            found.setdefault((bill.provider, bill.account, service), []).append(
                UsagePoint(bill.provider, bill.account, service, bill.bill_id, start, end, usage, unit, cost)
            )
    for points in found.values():
        points.sort(key=lambda p: p.end)
    return found


@dataclass(frozen=True)
class Anomaly:
    point: UsagePoint
    baseline_per_day: float
    ratio: float
    basis: str
    kind: str

    @property
    def excess(self) -> float:
        return (self.point.per_day - self.baseline_per_day) * self.point.days

    def as_dict(self) -> dict:
        p = self.point
        return {
            "provider": p.provider.value, "account": p.account, "service": p.service.value, "billId": p.bill_id,
            "start": p.start.isoformat(), "end": p.end.isoformat(), "usage": p.usage, "unit": p.unit.value,
            "perDay": round(p.per_day, 2), "baselinePerDay": round(self.baseline_per_day, 2), "ratio": round(self.ratio, 2),
            "excess": round(self.excess, 1), "basis": self.basis, "kind": self.kind,
        }


def _same_season(point: UsagePoint, earlier: UsagePoint) -> bool:
    """An earlier bill from a prior year whose period ends within about three weeks of the same calendar day."""
    if earlier.end.year >= point.end.year:
        return False
    delta = abs((point.end.replace(year=2000) - earlier.end.replace(year=2000)).days)
    return min(delta, 366 - delta) <= 21


def anomalies(series: dict[tuple[Utility, str, Service], list[UsagePoint]], *, since: date | None = None) -> list[Anomaly]:
    """Bills whose usage per day stands well above their baseline, and bills with no usage where there always is some."""
    found: list[Anomaly] = []
    for (_provider, _account, service), points in series.items():
        for index, point in enumerate(points):
            if since and point.end < since:
                continue
            history = points[:index]
            # A bill with no usage is a missed read, not a baseline.
            seasonal = [p.per_day for p in history if _same_season(point, p) and p.usage > 0]
            recent = [p.per_day for p in history if p.usage > 0][-6:]
            if seasonal:
                baseline, basis = median(seasonal), f"the same period in {len(seasonal)} earlier year(s)"
            elif len(recent) >= 4:
                baseline, basis = median(recent), f"the median of the {len(recent)} read bills before"
            else:
                continue
            if point.usage == 0 and baseline > 0 and all(p.usage > 0 for p in history[-6:]):
                found.append(Anomaly(point, baseline, 0.0, basis, "no usage: a stopped meter, a closed valve, or an estimated read"))
                continue
            if baseline <= 0:
                continue
            # A read after bills with no usage carries the whole stretch: judge it over the stretch.
            unread = []
            for earlier in reversed(history):
                if earlier.usage != 0:
                    break
                unread.append(earlier)
            if unread and point.usage > 0:
                days = point.days + sum(p.days for p in unread)
                spread = point.usage / days
                if spread / baseline < RATIO[service]:
                    found.append(Anomaly(point, baseline, spread / baseline, basis,
                                         f"catch-up read after {len(unread)} bill(s) with no usage: {spread:,.0f} per day over the "
                                         f"{days} days, within normal; the meter went unread or stuck, not a leak"))
                    continue
            ratio = point.per_day / baseline
            if ratio >= RATIO[service] and point.per_day - baseline >= MIN_EXCESS_PER_DAY[service]:
                what = "a leak or a broken irrigation line" if service is not Service.ELECTRIC else "a short, a stuck pump, or equipment left running"
                found.append(Anomaly(point, baseline, ratio, basis, f"high usage: check for {what}"))
    found.sort(key=lambda a: (a.point.end, a.point.account), reverse=True)
    return found


def fixed_growth(bills: list[UtilityBill]) -> dict[tuple[str, str], float]:
    """Each fixed charge's yearly growth: its median amount per bill in the first year seen against the last year seen.

    Keyed by (account, label). The City's fixed charges are flat per bill, not per day,
    so the bill is the unit. A partial-period line ("(for 12 days)") is left out. A
    charge seen for less than two years has no rate.
    """
    seen: dict[tuple[str, str], list[tuple[date, int]]] = {}
    for bill in bills:
        for charge in bill.charges:
            if charge.kind is not ChargeKind.FIXED or not charge.period_end or "(for" in charge.label:
                continue
            seen.setdefault((bill.account, charge.label), []).append((charge.period_end, charge.amount_cents))
    growth: dict[tuple[str, str], float] = {}
    for key, items in seen.items():
        items.sort()
        first_day, last_day = items[0][0], items[-1][0]
        years = (last_day - first_day).days / 365.25
        if years < 2:
            continue
        early = median(amount for day, amount in items if (day - first_day).days < 365)
        late = median(amount for day, amount in items if (last_day - day).days < 365)
        if early > 0 and late > 0:
            growth[key] = (late / early) ** (1 / (years - 1)) - 1
    return growth


__all__ = ["usage_series", "anomalies", "fixed_growth", "UsagePoint", "Anomaly"]
