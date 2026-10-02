"""What the legal group's models share: the Civil Code 5650 limits on late charges and interest, the site's street
addresses and parcel numbers read out of a text, and the former Davis-Stirling section numbers a template may still
cite.

Nothing here registers a model. The limits are the statute's, quoted from ``data/authorities/CIV/CIV-5650-5690.md``:
an assessment is delinquent 15 days after it is due (5650(b)); the late charge is at most 10 percent of the delinquent
assessment or $10, whichever is greater (5650(b)(2)); interest is at most 12 percent a year, starting 30 days after the
assessment is due (5650(b)(3)).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from enum import Enum

from jason.community.document_models import Finding, ModelContext, Severity
from jason.community.symbols import Building, Street

DELINQUENT_AFTER_DAYS = 15          # CIV 5650(b)
LATE_CHARGE_PERCENT = 10            # CIV 5650(b)(2)
LATE_CHARGE_FLOOR = 1000            # $10, CIV 5650(b)(2)
INTEREST_CAP_PERCENT = 12           # a year, CIV 5650(b)(3)
INTEREST_AFTER_DAYS = 30            # CIV 5650(b)(3)
PRE_LIEN_DAYS = 30                  # CIV 5660
LIEN_MAIL_DAYS = 10                 # CIV 5675(e)
RELEASE_DAYS = 21                   # CIV 5685(a)
FORECLOSURE_FLOOR = 180000          # $1,800, CIV 5720(b)


class ChargeKind(Enum):
    ASSESSMENT = "assessment"
    LATE_CHARGE = "late charge"
    INTEREST = "interest"
    COLLECTION_COST = "collection cost"
    ATTORNEY_FEE = "attorney fee"
    ADMIN_FEE = "administrative fee"
    REIMBURSEMENT = "reimbursement assessment"
    PAYMENT = "payment"
    CREDIT = "credit"
    BALANCE_FORWARD = "balance forward"
    OTHER = "other"


@dataclass(frozen=True)
class Charge:
    """One line of an itemized statement or an owner ledger. ``amount`` is signed cents: a payment or credit is
    negative. ``balance`` is the running balance the line prints, when it prints one."""

    posted: date | None
    description: str
    kind: ChargeKind
    amount: int
    balance: int | None = None


def charge_kind(description: str, amount: int = 0) -> ChargeKind:
    d = description.lower()
    if re.search(r"beginning balance|balance forward", d):
        return ChargeKind.BALANCE_FORWARD
    if re.search(r"credit|reversal|waive", d):
        return ChargeKind.CREDIT
    if re.search(r"payment|paid|receipt", d) and not re.search(r"late payment", d):
        return ChargeKind.PAYMENT
    if re.search(r"late", d):
        return ChargeKind.LATE_CHARGE
    if re.search(r"interest|finance charge", d):
        return ChargeKind.INTEREST
    if re.search(r"attorney|legal fee", d):
        return ChargeKind.ATTORNEY_FEE
    if re.search(r"collection|lien|pre-lien|recording|mailing", d):
        return ChargeKind.COLLECTION_COST
    if re.search(r"admin|management", d):
        return ChargeKind.ADMIN_FEE
    if re.search(r"reimburse", d):
        return ChargeKind.REIMBURSEMENT
    if re.search(r"assess|dues", d):
        return ChargeKind.ASSESSMENT
    return ChargeKind.OTHER


def total(charges, *kinds: ChargeKind) -> int:
    return sum(c.amount for c in charges if c.kind in kinds)


def late_charge_cap(assessment: int) -> int:
    """The most a late charge on one delinquent ``assessment`` (cents) may be: 10 percent or $10, whichever is greater
    (CIV 5650(b)(2)); the declaration may set less."""
    return max(math.ceil(assessment * LATE_CHARGE_PERCENT / 100), LATE_CHARGE_FLOOR)


def monthly_assessment(charges) -> int | None:
    """The commonest positive assessment line: the regular monthly installment."""
    amounts = [c.amount for c in charges if c.kind is ChargeKind.ASSESSMENT and c.amount > 0]
    if not amounts:
        return None
    return max(set(amounts), key=lambda a: (amounts.count(a), a))


def ledger_findings(charges, *, authority_prefix: str = "") -> list[Finding]:
    """The CIV 5650(b) checks every itemized ledger gets: late charges over the cap and monthly interest over one
    percent of the balance before it. A finding counts the lines; it names no owner."""
    found: list[Finding] = []
    over, several, high = ledger_counts(charges)
    largest = max((c.amount for c in charges if c.kind is ChargeKind.ASSESSMENT), default=0)
    if over:
        found.append(Finding("late-charge-over-cap", f"{over} late charge(s) exceed the greater of 10 percent of the delinquent amount "
                             "or $10; a lump may gather several months' charges", Severity.CHECK, "CIV 5650(b)(2)"))
    if several:
        found.append(Finding("late-charge-several-installments", f"{several} late charge(s) exceed 10 percent of one installment "
                             f"(${largest / 100:,.2f}) and stay within 10 percent of the balance; each should cover more than one "
                             "delinquent installment", Severity.CHECK, "CIV 5650(b)(2)"))
    if high:
        found.append(Finding("interest-over-cap", f"{high} interest charge(s) exceed one month at 12 percent a year on the balance before "
                             "them; the text may not show the balance the charge was figured on", Severity.CHECK, "CIV 5650(b)(3)"))
    return found


def ledger_counts(charges) -> tuple[int, int, int]:
    """Late charges over the CIV 5650(b)(2) cap, late charges that cover several installments, and interest lines over
    one month at 12 percent of the balance before them."""
    installments = [c.amount for c in charges if c.kind is ChargeKind.ASSESSMENT and c.amount > 0]
    largest = max(installments, default=0)
    over = several = high = 0
    previous = None
    for c in charges:
        if c.kind is ChargeKind.LATE_CHARGE and largest:
            # One late charge may cover several unpaid installments; the cap is 10 percent of what is delinquent.
            delinquent = max(largest, previous or 0)
            if c.amount > late_charge_cap(delinquent):
                over += 1
            elif c.amount > late_charge_cap(largest):
                several += 1
        if c.kind is ChargeKind.INTEREST and previous is not None and previous > 0 and c.amount > math.ceil(previous * INTEREST_CAP_PERCENT / 1200) + 1:
            high += 1
        if c.balance is not None:
            previous = c.balance
    return over, several, high


# The site's street addresses. The street words are the spec's ``Street`` members; the suffix may be spelled out.

_STREETS = {street.value.split()[0]: street.value for street in Street}
_SUFFIXES = {"DR": r"Dr(?:ive)?", "WALK": r"Walk", "LN": r"L(?:a)?n(?:e)?"}
_ADDRESS = re.compile(
    r"\b(\d{4})\s+(" + "|".join(sorted(_STREETS, key=len, reverse=True)) + r")\s+(?:"
    + "|".join(sorted({_SUFFIXES.get(s.value.split()[-1], re.escape(s.value.split()[-1])) for s in Street})) + r")\b\.?",
    re.I,
)


def site_address(text: str) -> str:
    """The first of the development's street addresses the text prints, as ``3022 ENCHANTED WALK``."""
    m = _ADDRESS.search(text or "")
    return f"{m.group(1)} {_STREETS[m.group(2).upper()]}" if m else ""


def site_addresses(text: str) -> tuple[str, ...]:
    seen: list[str] = []
    for m in _ADDRESS.finditer(text or ""):
        a = f"{m.group(1)} {_STREETS[m.group(2).upper()]}"
        if a not in seen:
            seen.append(a)
    return tuple(seen)


def building_of(context: ModelContext, address: str) -> Building | None:
    """The spec's building for a street address, or None when the spec does not place it."""
    lookup = getattr(context.community, "building_for_address", None)
    if not address or lookup is None:
        return None
    try:
        row = lookup(address)
    except (TypeError, ValueError):
        return None
    return row.number if row is not None else None


def building_number(value: str | int | None) -> Building | None:
    try:
        return Building(int(value)) if value not in (None, "") else None
    except ValueError:
        return None


_APN = re.compile(r"\b(\d{3})\s?-\s?(\d{4})\s?-\s?(\d{3})\s?-\s?(\d{4})\b")


def apns_in(text: str) -> tuple[str, ...]:
    """Assessor parcel numbers written 201-1170-024-0007, as the spec's 14 digits."""
    seen: list[str] = []
    for m in _APN.finditer(text or ""):
        apn = "".join(m.groups())
        if apn not in seen:
            seen.append(apn)
    return tuple(seen)


def known_parcels(context: ModelContext) -> tuple[str, ...]:
    parcels = getattr(context.community, "parcels", None)
    if parcels is None:
        return ()
    try:
        return tuple(parcels())
    except TypeError:
        return ()


def unit_count(context: ModelContext) -> int | None:
    units = getattr(context.community, "units", None)
    if units is None:
        return None
    try:
        return len(units() if callable(units) else units)
    except TypeError:
        return None


# The Davis-Stirling Act sat at Civil Code 1350 to 1378 until Stats. 2012, Ch. 180 moved it to 4000 to 6150.

_FORMER = re.compile(r"(?:Civil Code|Civ\.? Code|C\.C\.)\s*(?:Section|Sec\.|§+)?\s*(13[5-7]\d(?:\.\d+)?)\b"
                     r"|Section\s+(13[5-7]\d(?:\.\d+)?)\s+(?:et seq\.?\s+)?of the Civil Code", re.I)


def former_sections(text: str) -> tuple[str, ...]:
    seen: list[str] = []
    for m in _FORMER.finditer(text or ""):
        s = m.group(1) or m.group(2)
        if s not in seen:
            seen.append(s)
    return tuple(seen)


def former_sections_finding(sections, data_dir=None) -> list[Finding]:
    if not sections:
        return []
    where = ""
    if data_dir is not None:
        from jason.community.succession import now_at

        found = [f for f in (now_at(data_dir, s) for s in sections) if f]
        where = ("; " + "; ".join(found)) if found else ""
    return [Finding("cites-former-sections", f"cites former Civil Code section(s) {', '.join(sections)}; the Davis-Stirling Act now "
                    f"sits at Civil Code 4000 to 6150 (Stats. 2012, Ch. 180){where}", Severity.CHECK)]


_CIV = re.compile(r"(?:Civil Code|Civ\.? Code|Civ\.)\s*(?:Section|Sections|Sec\.|§+)?\s*(\d{4}(?:\.\d+)?)(?:\s*\(\s*([a-z0-9]+)\s*\))?", re.I)


def civil_code_citations(text: str) -> tuple[str, ...]:
    """Current Civil Code sections the text cites (4000 and up), as ``CIV 5660``."""
    seen: list[str] = []
    for m in _CIV.finditer(text or ""):
        if float(m.group(1)) < 1800 or m.group(1).startswith("13"):
            continue
        cite = f"CIV {m.group(1)}"
        if cite not in seen:
            seen.append(cite)
    return tuple(seen)


def words_to_cents(text: str) -> int | None:
    """"Two Hundred Forty-nine Thousand Four Hundred Ten & 26/100" as cents (a bond or check writes the sum out)."""
    small = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                                        "fifteen sixteen seventeen eighteen nineteen".split())}
    tens = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
    m = re.search(r"((?:(?:[A-Za-z]+)[\s-]+){1,14}?)(?:and|&)\s*(\d{1,2})\s*/\s*100", text or "", re.I)
    if not m:
        return None
    words = re.findall(r"[a-z]+", m.group(1).lower())
    value = current = 0
    seen = False
    for w in words:
        if w in small:
            current += small[w]
        elif w in tens:
            current += tens[w]
        elif w == "hundred":
            current *= 100
        elif w in ("thousand", "million"):
            value += current * (1000 if w == "thousand" else 1_000_000)
            current = 0
        else:
            if seen:
                break
            continue
        seen = True
    if not seen:
        return None
    return (value + current) * 100 + int(m.group(2))


def days_between(a: date | None, b: date | None) -> int | None:
    return (b - a).days if a and b else None


__all__ = ["ChargeKind", "Charge", "charge_kind", "total", "late_charge_cap", "monthly_assessment", "ledger_findings", "ledger_counts", "site_address",
           "site_addresses", "building_of", "building_number", "apns_in", "known_parcels", "unit_count", "former_sections",
           "former_sections_finding", "civil_code_citations", "words_to_cents", "days_between", "DELINQUENT_AFTER_DAYS",
           "LATE_CHARGE_PERCENT", "LATE_CHARGE_FLOOR", "INTEREST_CAP_PERCENT", "INTEREST_AFTER_DAYS", "PRE_LIEN_DAYS",
           "LIEN_MAIL_DAYS", "RELEASE_DAYS", "FORECLOSURE_FLOOR"]
