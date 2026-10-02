"""SMUD: how its commercial bills read, and the CI-TOD1 tariff Mystique's meters are billed on.

Every Mystique SMUD account is on rate category CITS-0 (C&I Time-of-Day,
Secondary 0-20 kW) under Rate Schedule CI-TOD1. The prices below are the
schedule's own, as SMUD Resolution No. 25-06-15 (adopted June 19, 2025)
publishes them: effective May 1, 2025, January 1, 2026, and January 1,
2027, with the 2028 transition prices marked provisional ("subject to
future rate increases"). The board approved increases of 3 percent a year
for 2026 and 2027; the schedule moves more of the cost into the fixed and
demand charges and trims some energy prices, so a flat percentage on the
whole bill misstates it.

The bill's taxes are not SMUD's tariff: the Sacramento city utility users
tax (7.5 percent of the electric charges) and the California electrical
energy surcharge ($0.0003 per kWh), both reconciled against the bills.

Proration follows Section VII.B: when a period spans a price change, each
charge is split by the days on each side, the fixed and demand charges as a
share of the period, and SMUD prints each piece as its own line.
"""

from __future__ import annotations

import re
from dataclasses import replace
from dataclasses import dataclass
from datetime import date

from jason.community.symbols import Utility
from jason.community.utility import (
    Charge,
    ChargeKind,
    MeterRead,
    Price,
    Service,
    Tariff,
    UsageUnit,
    UtilityBill,
    UtilityProvider,
    cents,
    is_money,
    split_days,
    us_date,
)

SOURCE = "SMUD Rate Schedule CI-TOD1, Resolution No. 25-06-15 adopted June 19, 2025, effective June 20, 2025 (smud.org)"
MAY_2025, JAN_2026, JAN_2027, JAN_2028 = date(2025, 5, 1), date(2026, 1, 1), date(2027, 1, 1), date(2028, 1, 1)


def _prices(*values: float, provisional_2028: float | None = None) -> tuple[Price, ...]:
    found = tuple(Price(when, value) for when, value in zip((MAY_2025, JAN_2026, JAN_2027), values))
    if provisional_2028 is not None:
        found += (Price(JAN_2028, provisional_2028, provisional=True),)
    return found


CITS_0 = Tariff(
    Utility.SMUD,
    "CITS-0",
    SOURCE,
    {
        "fixed": _prices(40.30, 42.00, 43.85, provisional_2028=44.45),
        "demand": _prices(1.546, 2.389, 3.281, provisional_2028=4.101),
        "nonsummer_peak": _prices(0.1532, 0.1540, 0.1546, provisional_2028=0.1506),
        "nonsummer_off_peak": _prices(0.1377, 0.1346, 0.1312, provisional_2028=0.1237),
        "nonsummer_off_peak_saver": _prices(0.1295, 0.1244, 0.1186, provisional_2028=0.1092),
        "summer_peak": _prices(0.3049, 0.3246, 0.3449, provisional_2028=0.3558),
        "summer_off_peak": _prices(0.1448, 0.1465, 0.1482, provisional_2028=0.1453),
        # Not SMUD's tariff: the city's utility users tax on the electric charges and the state surcharge per kWh.
        "city_tax_rate": (Price(date(2009, 1, 1), 0.075),),
        "state_surcharge": (Price(date(2004, 1, 1), 0.0003),),
    },
)

SUMMER_MONTHS = (6, 7, 8, 9)
TOU_KEYS = ("summer_peak", "summer_off_peak", "nonsummer_peak", "nonsummer_off_peak", "nonsummer_off_peak_saver")

_TOU_NAMES = (
    ("nonsum off peak saver", "nonsummer_off_peak_saver"),
    ("non-summer off peak saver", "nonsummer_off_peak_saver"),
    ("non-summer off peak", "nonsummer_off_peak"),
    ("non-summer peak", "nonsummer_peak"),
    ("summer off peak", "summer_off_peak"),
    ("summer peak", "summer_peak"),
)


def tou_key(text: str) -> str:
    folded = text.casefold()
    for name, key in _TOU_NAMES:
        if name in folded:
            return key
    return ""


class Smud(UtilityProvider):
    """SMUD's commercial electric bill, read from its PDF text, and the CITS-0 tariff."""

    utility = Utility.SMUD
    tariff = CITS_0

    def parse(self, text: str, *, account: str, bill_id: str = "", bill_date: date | None = None, source: str = "") -> UtilityBill:
        bill = self._parse(text, account=account, bill_id=bill_id, bill_date=bill_date, source=source)
        return replace(bill, due_cents=smud_due(text))

    def _parse(self, text: str, *, account: str, bill_id: str = "", bill_date: date | None = None, source: str = "") -> UtilityBill:
        period = re.search(r"Bill Period:\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*-\s*(\d{1,2}/\d{1,2}/\d{2,4})", text)
        issued = re.search(r"Bill Issue Date:\s*(\d{1,2}/\d{1,2}/\d{2,4})", text)
        rate = re.search(r"Rate:\s*([^\n]+)", text)
        location = re.search(r"Location:\s*([^\n]+)\n([^\n]+)", text)
        total = re.search(r"A\) TOTAL ELECTRIC SERVICE CHARGES/CREDITS\s*\n\s*(\$?-?[\d,]+\.\d\d)", text)
        start = us_date(period[1]) if period else None
        end = us_date(period[2]) if period else None
        reads = tuple(self._reads(text))
        meter = next((r.meter for r in reads if r.unit is UsageUnit.KWH), "")
        return UtilityBill(
            Utility.SMUD, account, bill_id, us_date(issued[1]) if issued else bill_date,
            cents(total[1]) if total else 0, start, end, tuple(self._charges(text, start, end, meter)), reads,
            rate[1].strip() if rate else "", " ".join(location[1].split()) if location else "", "", source,
        )

    @staticmethod
    def _reads(text: str) -> list[MeterRead]:
        """The meter summary: kWh, maximum kW, and peak kW per meter."""
        i, j = text.find("Meter Summary"), text.find("Electricity Charges")
        if i < 0 or j < 0:
            return []
        tokens = [t.strip() for t in text[i:j].splitlines() if t.strip()]
        found: list[MeterRead] = []
        for index in range(len(tokens) - 2):
            meter, amount, kind = tokens[index], tokens[index + 1], tokens[index + 2]
            if not re.fullmatch(r"\d{6,9}", meter) or not re.fullmatch(r"[\d,]+(\.\d+)?", amount):
                continue
            value = float(amount.replace(",", ""))
            if kind == "kWh":
                found.append(MeterRead(meter, Service.ELECTRIC, UsageUnit.KWH, value))
            elif kind in ("kW Maximum", "kW Peak"):
                found.append(MeterRead(meter, Service.ELECTRIC, UsageUnit.KW, value, register=kind))
        return found

    @staticmethod
    def _charges(text: str, start: date | None, end: date | None, meter: str) -> list[Charge]:
        i = text.find("Electricity Charges")
        # The charges end at the footnote line or the total, whichever comes first: some PDFs put the payment stub,
        # with its amounts, between the charges and the total.
        ends = [k for k in (text.find("*See explanations", i), text.find("A) TOTAL", i)) if k > 0]
        j = min(ends) if ends else -1
        if i < 0 or j < 0:
            return []
        tokens = [t.strip() for t in text[i:j].splitlines() if t.strip()]
        header = ["Electricity Charges", "Item", "Usage", "Type", "Rate", "Amount"]
        tokens = [t for t in tokens if t not in header]
        found: list[Charge] = []
        index = 0
        while index < len(tokens):
            label = tokens[index]
            if label == "Power Factor":
                index += 2
                continue
            if label.startswith("Electricity Usage") or label.startswith("Maximum Demand Charge"):
                demand = label.startswith("Maximum Demand")
                nxt = tokens[index + 1] if index + 1 < len(tokens) else ""
                combined = re.fullmatch(r"([\d,]+(?:\.\d+)?)\s+(.+@)", nxt)
                if combined:
                    quantity, kind_text, rest = float(combined[1].replace(",", "")), combined[2], index + 2
                else:
                    quantity = float(nxt.replace(",", "")) if re.fullmatch(r"[\d,]+(\.\d+)?", nxt) else None
                    kind_text, rest = (tokens[index + 2] if index + 2 < len(tokens) else ""), index + 3
                rate_text = tokens[rest] if rest < len(tokens) else ""
                amount_text = tokens[rest + 1] if rest + 1 < len(tokens) else ""
                if not is_money(amount_text):
                    index += 1
                    continue
                found.append(Charge(
                    Service.ELECTRIC, ChargeKind.DEMAND if demand else ChargeKind.USAGE, label, cents(amount_text), quantity,
                    UsageUnit.KW if demand else UsageUnit.KWH, float(rate_text) if re.fullmatch(r"\d*\.\d+", rate_text) else None,
                    start, end, meter, "" if demand else tou_key(kind_text),
                ))
                index = rest + 2
                continue
            if index + 1 < len(tokens) and is_money(tokens[index + 1]) and not is_money(label):
                folded = label.casefold()
                kind = (ChargeKind.FIXED if "infrastructure fixed" in folded else ChargeKind.TAX if "tax" in folded
                        else ChargeKind.SURCHARGE if "surcharge" in folded else ChargeKind.ADJUSTMENT)
                found.append(Charge(Service.ELECTRIC, kind, label.rstrip("*"), cents(tokens[index + 1]), period_start=start, period_end=end, meter=meter))
                index += 2
                continue
            index += 1
        return found


@dataclass(frozen=True)
class ElectricEstimate:
    energy_cents: int
    demand_cents: int
    fixed_cents: int
    tax_cents: int
    surcharge_cents: int
    provisional: bool

    @property
    def total_cents(self) -> int:
        return self.energy_cents + self.demand_cents + self.fixed_cents + self.tax_cents + self.surcharge_cents


def season_of(day: date) -> str:
    return "summer" if day.month in SUMMER_MONTHS else "nonsummer"


def estimate(tariff: Tariff, start: date, end: date, tou_kwh: dict[str, float], max_kw: float = 0.0) -> ElectricEstimate:
    """A CITS-0 bill for a period, priced as SMUD prorates it: each price piece by its share of the period's days.

    ``tou_kwh`` gives kWh by time-of-day key. A key from the other season (a
    summer peak read priced in a non-summer piece) is priced at the season
    the piece falls in: peak as peak, off-peak and saver as off-peak.
    """
    days_total = (end - start).days + 1
    energy = demand = fixed = 0.0
    provisional = False
    # Cut the period at every price change and at the season boundaries (June 1, October 1).
    cuts = tariff.changes_between(start, end) + [
        date(year, month, 1) for year in range(start.year, end.year + 1) for month in (6, 10) if start < date(year, month, 1) <= end
    ]
    pieces = split_days(start, end, cuts)
    season_days = {"summer": 0, "nonsummer": 0}
    for piece_start, _piece_end, days in pieces:
        season_days[season_of(piece_start)] += days
    for piece_start, _piece_end, days in pieces:
        season = season_of(piece_start)
        for key, kwh in tou_kwh.items():
            # SMUD assigns each kWh to its season; a key is spread over its own season's days, or over all days
            # at the matching price when the period has none of its season (an estimate for another month).
            own = "summer" if key.startswith("summer") else "nonsummer"
            if season_days[own]:
                if own != season:
                    continue
                share_of_key = days / season_days[own]
                priced = key
            else:
                share_of_key = days / days_total
                priced = _in_season(key, season)
            energy += kwh * share_of_key * tariff.price(priced, piece_start)
            provisional |= tariff.provisional(priced, piece_start)
        share = days / days_total
        demand += max_kw * tariff.price("demand", piece_start) * share
        fixed += tariff.price("fixed", piece_start) * share
    subtotal = round(energy * 100) + round(demand * 100) + round(fixed * 100)
    tax = round(subtotal * tariff.price("city_tax_rate", start))
    surcharge = round(sum(tou_kwh.values()) * tariff.price("state_surcharge", start) * 100)
    return ElectricEstimate(round(energy * 100), round(demand * 100), round(fixed * 100), tax, surcharge, provisional)


def _in_season(key: str, season: str) -> str:
    if key.startswith(season + "_"):
        return key
    peak = key.endswith("_peak") and not key.endswith("off_peak")
    if season == "summer":
        return "summer_peak" if peak else "summer_off_peak"
    return "nonsummer_peak" if peak else "nonsummer_off_peak"


def tou_usage(bill: UtilityBill) -> dict[str, float]:
    """A bill's kWh by time-of-day key, summing the prorated lines."""
    found: dict[str, float] = {}
    for charge in bill.charges:
        if charge.kind is ChargeKind.USAGE and charge.tou and charge.quantity is not None:
            found[charge.tou] = found.get(charge.tou, 0.0) + charge.quantity
    return found


def max_kw(bill: UtilityBill) -> float:
    return max((r.usage for r in bill.reads if r.unit is UsageUnit.KW and r.register == "kW Maximum"), default=0.0)


def smud_due(text: str) -> int | None:
    """"Total Amount Due:" on the bill: a dollar amount, or "NO PAYMENT DUE" when a credit covers the charges."""
    found = re.search(r"Total Amount Due:\s*(NO PAYMENT DUE|-?\$[\d,]+\.\d\d)", text)
    if not found:
        return None
    return 0 if found[1] == "NO PAYMENT DUE" else cents(found[1])
