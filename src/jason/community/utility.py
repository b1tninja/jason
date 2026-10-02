"""Utility bills as documents: what each bill charged, for which service and meter, over which period.

A utility bill is not a vendor invoice. It comes from an API the association
controls (SMUD's portal, the City's i-doxs portal), on a published tariff,
and it states its own period, meters, usage, and rates. So it can be parsed
into structure and checked: the charges must add to the total, and the
charges must follow from the usage at the tariff's prices.

- ``Service`` is what was delivered: electricity, domestic or irrigation
  water, fire service, storm drainage, street sweeping, sewer.
- ``Charge`` is one line: its service, its kind (usage, fixed, demand, tax,
  surcharge, adjustment), quantity, unit, rate, and amount in cents.
- ``MeterRead`` is one register of one meter: the reads, the multiplier,
  the usage.
- ``UtilityBill`` is the document: provider, account, period, service
  address, parcel, charges, reads, and the PDF it came from.
- ``Tariff`` holds a published rate schedule's prices by effective date, so a
  period's cost can be priced at any date and a future year estimated.
- ``UtilityProvider`` is what a utility implements: parse its bill text and
  know its tariff.

The map from an account to its meters and parcel is read from the bills
themselves (``service_points``); the specification only names what a bill
cannot say, such as which building a meter serves.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any

from jason.community.symbols import Utility


class Service(Enum):
    ELECTRIC = "electric"
    WATER_DOMESTIC = "water_domestic"
    WATER_IRRIGATION = "water_irrigation"
    FIRE_SERVICE = "fire_service"
    STORM_DRAINAGE = "storm_drainage"
    STREET_SWEEPING = "street_sweeping"
    SEWER = "sewer"
    GARBAGE = "garbage"
    OTHER = "other"


class ChargeKind(Enum):
    USAGE = "usage"
    FIXED = "fixed"
    DEMAND = "demand"
    TAX = "tax"
    SURCHARGE = "surcharge"
    ADJUSTMENT = "adjustment"


class UsageUnit(Enum):
    KWH = "kWh"
    KW = "kW"
    CUBIC_FEET = "cu ft"


GALLONS_PER_CUBIC_FOOT = 7.48052


@dataclass(frozen=True)
class Charge:
    service: Service
    kind: ChargeKind
    label: str
    amount_cents: int
    quantity: float | None = None
    unit: UsageUnit | None = None
    rate: float | None = None
    period_start: date | None = None
    period_end: date | None = None
    meter: str = ""
    # A time-of-day or season period ("summer peak"), when the tariff prices by one.
    tou: str = ""


@dataclass(frozen=True)
class MeterRead:
    meter: str
    service: Service
    unit: UsageUnit
    usage: float
    previous: float | None = None
    current: float | None = None
    multiplier: float | None = None
    size: str = ""
    # Which register of the meter, when it has several ("kW Maximum", "kW Peak").
    register: str = ""


@dataclass(frozen=True)
class UtilityBill:
    provider: Utility
    account: str
    bill_id: str
    bill_date: date | None
    total_cents: int
    period_start: date | None = None
    period_end: date | None = None
    charges: tuple[Charge, ...] = ()
    reads: tuple[MeterRead, ...] = ()
    rate_schedule: str = ""
    service_address: str = ""
    parcel: str = ""
    source: str = ""
    notes: tuple[str, ...] = ()
    # What the bill asked to be paid: the current charges plus any previous balance, less any credit. None when unread.
    due_cents: int | None = None

    @property
    def payable_cents(self) -> int:
        """The amount a payment of this bill should be: the amount due when the bill states it, else its charges."""
        return self.total_cents if self.due_cents is None else self.due_cents

    @property
    def days(self) -> int | None:
        if self.period_start and self.period_end:
            return (self.period_end - self.period_start).days + 1
        return None

    @property
    def charged_cents(self) -> int:
        return sum(charge.amount_cents for charge in self.charges)

    @property
    def reconciles(self) -> bool:
        """The charges add to the bill's current charges, within a cent per line for rounding."""
        return abs(self.charged_cents - self.total_cents) <= max(1, len(self.charges) // 4)

    def usage(self, service: Service | None = None, unit: UsageUnit | None = None) -> float:
        reads = [r for r in self.reads if (service is None or r.service is service) and (unit is None or r.unit is unit)]
        if reads:
            return sum(r.usage for r in reads)
        return sum(c.quantity or 0.0 for c in self.charges
                   if c.kind is ChargeKind.USAGE and (service is None or c.service is service) and (unit is None or c.unit is unit))

    def by_service(self) -> dict[Service, int]:
        found: dict[Service, int] = {}
        for charge in self.charges:
            found[charge.service] = found.get(charge.service, 0) + charge.amount_cents
        return found

    def by_kind(self) -> dict[ChargeKind, int]:
        found: dict[ChargeKind, int] = {}
        for charge in self.charges:
            found[charge.kind] = found.get(charge.kind, 0) + charge.amount_cents
        return found

    def service_period(self, service: Service) -> tuple[date | None, date | None]:
        for charge in self.charges:
            if charge.service is service and charge.period_start:
                return charge.period_start, charge.period_end
        return self.period_start, self.period_end


@dataclass(frozen=True)
class Price:
    """One component's price from an effective date. ``provisional`` marks a published future price 'subject to change'."""

    effective: date
    value: float
    provisional: bool = False


@dataclass(frozen=True)
class Tariff:
    """A rate schedule's prices by component and effective date, with its source.

    ``components`` maps a key ("fixed", "demand", "summer_peak", ...) to its
    prices, oldest first. ``price(key, on)`` is the price in force on a date.
    """

    utility: Utility
    schedule: str
    source: str
    components: dict[str, tuple[Price, ...]]

    def price(self, key: str, on: date) -> float:
        prices = self.components[key]
        current = None
        for item in prices:
            if item.effective <= on:
                current = item
        if current is None:
            raise KeyError(f"{self.schedule} {key} has no price before {on}")
        return current.value

    def provisional(self, key: str, on: date) -> bool:
        current = None
        for item in self.components[key]:
            if item.effective <= on:
                current = item
        return bool(current and current.provisional)

    def changes_between(self, start: date, end: date) -> list[date]:
        """Every effective date that falls inside the period, for proration."""
        return sorted({p.effective for prices in self.components.values() for p in prices if start < p.effective <= end})


def split_days(start: date, end: date, changes: list[date]) -> list[tuple[date, date, int]]:
    """The period cut at each price change: (from, to, days), inclusive of both ends."""
    pieces: list[tuple[date, date, int]] = []
    cursor = start
    for change in sorted(changes):
        if cursor < change <= end:
            pieces.append((cursor, change - timedelta(days=1), (change - cursor).days))
            cursor = change
    pieces.append((cursor, end, (end - cursor).days + 1))
    return pieces


class UtilityProvider(ABC):
    """A utility: how its bills read, and its tariffs."""

    utility: Utility

    @abstractmethod
    def parse(self, text: str, *, account: str, bill_id: str = "", bill_date: date | None = None, source: str = "") -> UtilityBill:
        """The bill's structure from its PDF text."""


@dataclass(frozen=True)
class ServicePoint:
    """One meter (or an unmetered service) on one account, as the bills describe it."""

    provider: Utility
    account: str
    service: Service
    meter: str = ""
    size: str = ""
    service_address: str = ""
    parcel: str = ""
    first_bill: date | None = None
    last_bill: date | None = None
    bills: int = 0


def service_points(bills) -> tuple[ServicePoint, ...]:
    """The account, meter, service, address, and parcel each bill states, merged across bills, newest facts kept."""
    found: dict[tuple, dict[str, Any]] = {}
    for bill in sorted(bills, key=lambda b: (b.bill_date or date.min)):
        seen: set[tuple] = set()
        for read in bill.reads:
            seen.add((read.service, read.meter, read.size))
        for charge in bill.charges:
            if charge.kind in (ChargeKind.USAGE, ChargeKind.FIXED) and not any(key[0] is charge.service for key in seen):
                seen.add((charge.service, charge.meter, ""))
        for service, meter, size in seen:
            key = (bill.provider, bill.account, service, meter)
            entry = found.setdefault(key, {"first": bill.bill_date, "bills": 0, "size": "", "address": "", "parcel": ""})
            entry["bills"] += 1
            entry["last"] = bill.bill_date
            entry["size"] = size or entry["size"]
            entry["address"] = bill.service_address or entry["address"]
            entry["parcel"] = bill.parcel or entry["parcel"]
    return tuple(
        ServicePoint(provider, account, service, meter, entry["size"], entry["address"], entry["parcel"], entry["first"], entry.get("last"), entry["bills"])
        for (provider, account, service, meter), entry in sorted(found.items(), key=lambda kv: (kv[0][0].value, kv[0][1], kv[0][2].value, kv[0][3]))
    )


@dataclass(frozen=True)
class UtilityAccount:
    """What a bill cannot say about an account: what it serves on the site.

    The meters, sizes, service address, and parcel come from the bills
    (``service_points``). The specification names the account's purpose
    ("Building 3 house meter", "ACA 5") and, when it serves one, the building.
    """

    utility: Utility
    account: str
    label: str
    building: Any = None


def dedupe_bills(bills) -> list[UtilityBill]:
    """One bill per account and period: a re-download or an attached copy of the same bill is kept once, the portal file first."""
    seen: set[tuple] = set()
    kept: list[UtilityBill] = []
    for bill in sorted(bills, key=lambda b: ("attachments" in b.source.replace("\\", "/").split("/"), b.source)):
        key = (bill.provider, bill.account, bill.period_start, bill.period_end, bill.bill_date, bill.total_cents)
        if key in seen:
            continue
        seen.add(key)
        kept.append(bill)
    return kept


_MONEY = re.compile(r"-?\$?\(?-?[\d,]+\.\d\d\)?")


def cents(text: str) -> int:
    """"$1,234.56", "-12.30", or "(12.30)" as integer cents."""
    raw = text.strip()
    negative = raw.startswith("-") or raw.startswith("(") or "-$" in raw
    digits = re.sub(r"[^\d.]", "", raw)
    whole, _, frac = digits.partition(".")
    value = int(whole or "0") * 100 + int((frac + "00")[:2])
    return -value if negative else value


def is_money(text: str) -> bool:
    return bool(_MONEY.fullmatch(text.strip()))


def us_date(text: str) -> date | None:
    """"07/10/26", "7/10/2026", or "July 01, 2026" as a date."""
    text = text.strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
    if m:
        year = int(m[3])
        return date(year + 2000 if year < 100 else year, int(m[1]), int(m[2]))
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", text)
    if m:
        months = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
        name = m[1].lower()
        if name in months:
            return date(int(m[3]), months.index(name) + 1, int(m[2]))
    return None


__all__ = [
    "Service", "ChargeKind", "UsageUnit", "Charge", "MeterRead", "UtilityBill", "Price", "Tariff", "UtilityProvider",
    "ServicePoint", "service_points", "UtilityAccount", "dedupe_bills", "split_days", "cents", "is_money", "us_date", "GALLONS_PER_CUBIC_FOOT", "field",
]
