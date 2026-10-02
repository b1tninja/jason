"""The City of Sacramento's utility bill: water, fire service, storm drainage, street sweeping, sewer.

A City bill groups its charges by service under "Service from <start> - <end>"
headings, each with its own period (the services are billed on staggered
dates), and closes each group with a subtotal. A metered group is followed
by its usage history and its meter reads: usage in cubic feet, the previous
and current read, the meter size, the meter number, the read difference,
gallons, and the multiplier. A compound meter prints one number with two
registers at different multipliers.

The tariff is the City's Exhibit A, Water Service Fees and Charges, whose
last scheduled step took effect July 1, 2019; the bills since still charge
exactly those prices ($1.4587 per 100 cubic feet; a 2-inch meter's base
charge $105.15, a 4-inch meter's $319.72; an 8-inch fire tap $160.85, a
6-inch $120.62). A rate study proposes increases beginning July 2027 through
2031 under a Proposition 218 process; no percentage is adopted, so a future
year is estimated with a scenario increase the caller names.
"""

from __future__ import annotations

import re
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
    us_date,
)

SOURCE = "City of Sacramento, Exhibit A Water Service Fees and Charges, column effective July 1, 2019 (cityofsacramento.gov)"
JULY_2019 = date(2019, 7, 1)

WATER_2019 = Tariff(
    Utility.CITY_OF_SACRAMENTO,
    "Water, metered and fire service",
    SOURCE,
    {
        "water_per_cubic_foot": (Price(JULY_2019, 0.014587),),
        "base_2in": (Price(JULY_2019, 105.15),),
        "base_4in": (Price(JULY_2019, 319.72),),
        "fire_6in": (Price(JULY_2019, 120.62),),
        "fire_8in": (Price(JULY_2019, 160.85),),
    },
)

_MONEY_LINE = re.compile(r"-?\$?[\d,]+\.\d\d")
_MONEY_AND_TEXT = re.compile(r"(-?\$?[\d,]+\.\d\d)\s+(\S.*)")
_USAGE = re.compile(r"([\d,]+)\s+cubic feet\s+@\s+\$?([\d.]+)\s+per cubic foot", re.I)
_DAYS = re.compile(r"\(for\s+(\d+)\s+days\)", re.I)


def service_of(text: str) -> Service:
    folded = text.casefold()
    if "irrigation" in folded:
        return Service.WATER_IRRIGATION
    if "fire service" in folded or "inch tap" in folded:
        return Service.FIRE_SERVICE
    if "storm drainage" in folded or "sq ft parcel" in folded:
        return Service.STORM_DRAINAGE
    if "street sweeping" in folded:
        return Service.STREET_SWEEPING
    if "sewer" in folded or "wastewater" in folded or "sewage" in folded:
        return Service.SEWER
    if "garbage" in folded or "solid waste" in folded or "recycl" in folded:
        return Service.GARBAGE
    if "water" in folded or "cubic feet" in folded or "base service charge" in folded:
        return Service.WATER_DOMESTIC
    return Service.OTHER


def _is_money(token: str) -> bool:
    return bool(_MONEY_LINE.fullmatch(token))


def _continues(token: str) -> bool:
    """A wrapped tail of the previous description ("rooms", "Area", "(for 12 days)", "Final")."""
    return token[:1].islower() or token.startswith("(") or token in ("Area", "Final") or bool(re.fullmatch(r"\d+ days\)", token))


class SacramentoUtilities(UtilityProvider):
    """The City of Sacramento's utility bill, read from its PDF text."""

    utility = Utility.CITY_OF_SACRAMENTO
    tariff = WATER_2019

    def parse(self, text: str, *, account: str, bill_id: str = "", bill_date: date | None = None, source: str = "") -> UtilityBill:
        billed = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", text)
        # "Current Charges - Due <date>", or plain "Current Charges" when the account carries a credit.
        current = re.search(r"Current Charges(?: - Due [^\n]*)?\n\s*(-?\$?[\d,]+\.\d\d)", text)
        apn = re.search(r"\b(\d{3}-\d{4}-\d{3}-\d{4})\b", text)
        address = re.search(r"\n(\d+ [A-Z0-9 .]+?) - (?:Common Area|Condominium|[A-Z][A-Za-z ]+)\n", text)
        if address is None:
            address = re.search(r"Service Address:\s*([^\n]+)", text)
        charges: list[Charge] = []
        reads: list[MeterRead] = []
        starts: list[date] = []
        ends: list[date] = []
        seen_sections: set[tuple] = set()
        for match in re.finditer(r"Service from (\d{1,2}/\d{1,2}/\d{2,4}) - (\d{1,2}/\d{1,2}/\d{2,4})\n(.*?)\nSubtotal\n\s*(-?\$?[\d,]+\.\d\d)", text, re.S):
            start, end = us_date(match[1]), us_date(match[2])
            key = (match[1], match[2], match[3].strip(), match[4])
            # Page one repeats the first section of page two on some bills; a section is counted once.
            if key in seen_sections:
                continue
            seen_sections.add(key)
            if start:
                starts.append(start)
            if end:
                ends.append(end)
            section = self._section(match[3], start, end)
            charges.extend(section)
            tail = text[match.end(): match.end() + 1500]
            service = section[0].service if section else Service.OTHER
            reads.extend(self._reads(tail, service))
        return UtilityBill(
            Utility.CITY_OF_SACRAMENTO, account, bill_id, us_date(billed[1]) if billed else bill_date,
            cents(current[1]) if current else 0, min(starts) if starts else None, max(ends) if ends else None,
            tuple(charges), tuple(_dedupe_reads(reads)), "", " ".join(address[1].split()) if address else "",
            apn[1] if apn else "", source, (), city_due(text),
        )

    @staticmethod
    def _section(body: str, start: date | None, end: date | None) -> list[Charge]:
        tokens: list[str] = []
        for raw in body.splitlines():
            line = raw.strip()
            if not line:
                continue
            both = _MONEY_AND_TEXT.fullmatch(line)
            if both and not _USAGE.search(line):
                tokens.extend([both[1], both[2]])
            else:
                tokens.append(line)
        merged: list[str] = []
        for token in tokens:
            if merged and not _is_money(token) and not _is_money(merged[-1]) and _continues(token):
                merged[-1] = f"{merged[-1]} {token}"
            else:
                merged.append(token)
        found: list[Charge] = []
        name = ""
        pending: str | None = None

        def flush(description: str) -> None:
            nonlocal pending
            if pending is None:
                return
            text = f"{name} {description}".strip()
            service = service_of(text)
            usage = _USAGE.search(description)
            days = _DAYS.search(description)
            folded = text.casefold()
            if usage:
                kind, quantity, unit, rate = ChargeKind.USAGE, float(usage[1].replace(",", "")), UsageUnit.CUBIC_FEET, float(usage[2])
            else:
                # Word boundaries: "Property Related Fee" holds "late" and is a fee, not a late charge.
                kind = ChargeKind.ADJUSTMENT if re.search(r"\b(penalty|late (fee|charge)|adjustment|correction)\b", folded) else ChargeKind.FIXED
                quantity, unit, rate = None, None, None
            label = description or name
            if days:
                label = f"{label}"
            found.append(Charge(service, kind, label.strip() or name, cents(pending), quantity, unit, rate, start, end, "", ""))
            pending = None

        for token in merged:
            if _is_money(token):
                if pending is not None:
                    flush("")
                pending = token
            elif pending is not None:
                flush(token)
            else:
                name = token
        flush("")
        return found

    @staticmethod
    def _reads(tail: str, service: Service) -> list[MeterRead]:
        """Meter reads in groups of eight after the header: usage, previous, current, size, meter, difference, gallons, multiplier."""
        marker = tail.find("Gallons")
        stop = min([k for k in (tail.find("Service from"), tail.find("Account Number"), tail.find("Utility Services")) if k > 0] or [len(tail)])
        if marker < 0 or marker > stop:
            return []
        values = [t.strip() for t in tail[marker + len("Gallons"): stop].splitlines() if t.strip()]
        numbers: list[str] = []
        for value in values:
            if not re.fullmatch(r"[\d,]+(\.\d+)?", value):
                break
            numbers.append(value)
        found: list[MeterRead] = []
        for index in range(0, len(numbers) - 7, 8):
            usage, previous, current, size, meter, _diff, _gallons, multiplier = numbers[index: index + 8]
            found.append(MeterRead(
                meter, service, UsageUnit.CUBIC_FEET, float(usage.replace(",", "")), float(previous.replace(",", "")),
                float(current.replace(",", "")), float(multiplier.replace(",", "")), inches(size),
            ))
        return found


def city_due(text: str) -> int | None:
    """The stub's "Total Amount Due": the value after the account number, ahead of the current charges."""
    found = re.search(r"^\s*\d{10}\s*\n\s*(-?\$[\d,]+\.\d\d)\s*\n\s*-?\$[\d,]+\.\d\d", text, re.M)
    return cents(found[1]) if found else None


def inches(size: str) -> str:
    """A meter size as the City prints it ("4", "4.0", "1.50") in inches: 4", 1.5"."""
    value = float(size.replace(",", ""))
    return f'{value:g}"'


def _dedupe_reads(reads: list[MeterRead]) -> list[MeterRead]:
    seen: set[tuple] = set()
    kept: list[MeterRead] = []
    for read in reads:
        key = (read.meter, read.previous, read.current, read.multiplier)
        if key in seen:
            continue
        seen.add(key)
        kept.append(read)
    return kept
